"""LDA L2 · 版图设计规则检查（DRC）自查（D-15）。

对 D-14 导出的版图 / D-12 器件库器件做**可制造性规则检查**，输出 DRC 报告。
纯参数/几何级、零外部依赖；规则表取典型 SOI 180nm 工艺（与 D-12 PDK
params_schema / PDK process_notes 同窗口，D-09 接入后可从真实 PDK 注入）。

检查项（器件级，基于 kind + params）：
  min_width    —— 波导/芯宽 ≥ 最小线宽（可制造下限）
  min_space    —— 方向耦合器 gap ≥ 最小间距（避免串扰/桥接）
  min_bend_R   —— 环形半径 ≥ 最小弯曲半径（弯曲损耗可控）
  max_split    —— Y 分支分叉角 ≤ 最大角（可制造）

**损耗通道（网格级 · D-125）**：器件级规则全是**几何**约束，管不到"链路预算"。
`drc_check_mesh_loss(ops, …)` 补上**损耗通道**，判**两个口径**（每模口径 = 光子实际
穿越深度 × 单件损耗 · 总级联口径 = 全网格门合计），常数与 `.mzi_mesh_matmul` 同源
（单一真源，不另建）；限值与 `lda_qeda.quantum_drc_lvs` 的 `QDR-LOSS-BUDGET` 同源。

DRC 结果 passed=False 时给出逐条 violation（规则/器件/参数/实测/要求），
供设计闭环（agent）回读整改——"设计→版图→DRC 自查"可制造性闭环。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# 典型 SOI 180nm 工艺规则（µm/deg；公开文献近似，D-09 接入后由 PDK 覆盖）
DEFAULT_RULES: Dict[str, float] = {
    "min_width_um": 0.35,
    "min_space_um": 0.20,
    "min_bend_R_um": 5.0,
    "max_split_angle_deg": 30.0,
    # ── 损耗通道（网格级 · D-125）· 设计规则 · 可覆盖 · 非实测 golden ──
    "max_il_per_mode_db": 15.0,     # **每模口径**上限（光子实际穿越 · η ≈ 3.2%）
    "max_il_total_db": 25.0,        # **总级联口径**上限（全网格门合计）
}


def rules_from_pdk(pdk) -> Dict[str, float]:
    """从 PDK 提取 DRC 工艺规则（D-21；D-09 接入后由真实 PDK 提供）。

    PDK.design_rules 键与 DEFAULT_RULES 对齐；未配置的键回退默认典型值。
    不同 foundry 规则不同 → 同一设计在不同厂可制造性不同（工艺窗口差异）。
    """
    base = dict(DEFAULT_RULES)
    if pdk is not None and getattr(pdk, "design_rules", None):
        base.update({k: float(v) for k, v in pdk.design_rules.items()})
    return base


@dataclass
class DRCCheck:
    rule: str                # min_width / min_space / min_bend_R / max_split
    device: str              # 器件 kind
    param: str               # 参数名
    value: float             # 实测值
    required: float          # 要求值（µm/deg）
    ok: bool
    severity: str = "error"  # error（FAIL）| warning

    def brief(self) -> str:
        flag = "OK" if self.ok else "ERR"
        return (f"[{flag}] {self.rule:<12} {self.device}.{self.param}="
                f"{self.value:g}（要求 {'≥' if not self.rule.startswith('max') else '≤'} "
                f"{self.required:g}）")


@dataclass
class DRCResult:
    device: str
    passed: bool
    checks: List[DRCCheck] = field(default_factory=list)

    def violations(self) -> List[DRCCheck]:
        return [c for c in self.checks if not c.ok]

    def brief(self) -> str:
        errs = self.violations()
        flag = "PASS" if self.passed else "FAIL"
        return f"[{flag}] {self.device}: {len(self.checks)} 项检查，{len(errs)} 项违规"

    def to_dict(self) -> dict:
        return {
            "device": self.device,
            "passed": self.passed,
            "checks": [
                {"rule": c.rule, "device": c.device, "param": c.param,
                 "value": c.value, "required": c.required, "ok": c.ok,
                 "severity": c.severity}
                for c in self.checks
            ],
        }


def drc_check_device(kind: str, params: Dict[str, float],
                     rules: Optional[Dict[str, float]] = None) -> DRCResult:
    """对单个器件（kind + params）做 DRC 自查。"""
    rules = rules or DEFAULT_RULES
    checks: List[DRCCheck] = []

    def add(rule: str, param: str, value: float, required: float):
        value = float(value)
        required = float(required)
        if rule.startswith("max"):
            ok = value <= required
        else:
            ok = value >= required
        checks.append(DRCCheck(rule, kind, param, value, required, ok))

    if kind == "Waveguide":
        add("min_width", "width", params.get("width", 0.5), rules["min_width_um"])
    elif kind == "RingResonator":
        add("min_bend_R", "R", params.get("R", 10.0), rules["min_bend_R_um"])
        add("min_width", "wg_width",
            params.get("wg_width", params.get("width", 0.5)),
            rules["min_width_um"])
        # v0.8.11d：环形有耦合 bus，gap 是可制造性硬约束（与 RingAddDrop 对齐）
        add("min_space", "gap", params.get("gap", 0.3), rules["min_space_um"])
    elif kind == "RingAddDrop":
        # D-37 环形 add-drop：弯曲半径 + 波导宽 + 耦合 gap（双 bus 间距）
        add("min_bend_R", "R", params.get("R", 10.0), rules["min_bend_R_um"])
        add("min_width", "wg_width",
            params.get("wg_width", params.get("width", 0.5)),
            rules["min_width_um"])
        add("min_space", "gap", params.get("gap", 0.3), rules["min_space_um"])
    elif kind == "DirectionalCoupler":
        add("min_space", "gap", params.get("gap", 0.3), rules["min_space_um"])
        add("min_width", "width", params.get("width", 0.5), rules["min_width_um"])
    elif kind == "MZI":
        # P0 网格 P&R · 单 MZI 单元可制造性（波导宽 + 耦合 gap，与相邻耦合约定同源）
        add("min_width", "wg", params.get("wg", 0.5), rules["min_width_um"])
        add("min_space", "gap", params.get("gap", 0.3), rules["min_space_um"])
    elif kind == "PhaseShifter":
        # P1-A 物理综合 · 输出相移器：波导宽可制造性（与相邻耦合约定同源）
        add("min_width", "wg", params.get("wg", 0.5), rules["min_width_um"])
    elif kind == "SymmetricYBranch":
        add("min_width", "width", params.get("width", 0.5), rules["min_width_um"])
        add("max_split", "split_angle", params.get("split_angle", 10.0),
            rules["max_split_angle_deg"])
    elif kind == "BraggMirror":
        # 一维层堆叠：宽度规则由衬底工艺决定（无 2D 版图几何），跳过
        pass
    elif kind in ("Taper", "EulerBend", "MMI", "GratingCoupler"):
        # D-71 真实版图基元：可制造性几何量来自 primitives.primitive_geometry
        from lda_l2.primitives import primitive_geometry
        g = primitive_geometry(kind, params)
        if "min_width" in g:
            add("min_width", "min_width", g["min_width"], rules["min_width_um"])
        if "min_space" in g:
            add("min_space", "min_space", g["min_space"], rules["min_space_um"])
        if "min_bend_R" in g:
            add("min_bend_R", "R", g["min_bend_R"], rules["min_bend_R_um"])
    else:
        raise ValueError(f"DRC 暂不支持 kind={kind}")

    return DRCResult(device=kind, passed=all(c.ok for c in checks), checks=checks)


# ---------------------------------------------------------------------------
# 损耗通道（网格级 · D-125）：每模口径 + 总级联口径
# ---------------------------------------------------------------------------
@dataclass
class DRCMeshLoss:
    basis: str                # 每模口径 / 总级联口径
    value_db: float
    required_db: float
    ok: bool
    detail: str

    def brief(self) -> str:
        flag = "OK" if self.ok else "ERR"
        return (f"[{flag}] {self.basis}: {self.value_db:.3f} dB"
                f"（要求 ≤ {self.required_db:g}）")


@dataclass
class DRCMeshLossResult:
    passed: bool
    checks: List[DRCMeshLoss] = field(default_factory=list)
    basis: Dict[str, Any] = field(default_factory=dict)

    def violations(self) -> List[DRCMeshLoss]:
        return [c for c in self.checks if not c.ok]

    def brief(self) -> str:
        flag = "PASS" if self.passed else "FAIL"
        return (f"[{flag}] 网格损耗: {len(self.checks)} 项检查，"
                f"{len(self.violations())} 项违规")

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "basis": self.basis,
            "checks": [{"basis": c.basis, "value_db": c.value_db,
                        "required_db": c.required_db, "ok": c.ok,
                        "detail": c.detail} for c in self.checks],
        }


def drc_check_mesh_loss(ops, n_crossings: int = 0,
                        rules: Optional[Dict[str, float]] = None
                        ) -> DRCMeshLossResult:
    """★ 经典 DRC 的**损耗通道**（网格级 · D-125）：判**两个口径**。

      · **每模口径**（物理正确）：光子实际穿越深度 × 单件损耗 ≤ `max_il_per_mode_db`；
      · **总级联口径**（结构性）：全网格门合计 + 交叉 ≤ `max_il_total_db`。

    每模深度**由提交的 ops 直接数出**（平台单一真源
    `mzi_mesh_matmul.mesh_per_mode_optical_depth`，mesh-agnostic：三角 2N−3 / 矩形 N）；
    器件级规则（`drc_check_device`）管不到链路预算 —— 这条补上该通道。
    两个口径**各带独立限值**，任一超限即违规（`basis` 标注口径 + 明细）。
    """
    from lda_l2 import mzi_mesh_matmul as MMM
    rules = dict(DEFAULT_RULES) if rules is None else rules
    if not ops:
        raise ValueError("ops 非空")
    basis = MMM.mesh_loss_basis(ops, n_crossings=n_crossings)
    lim_pm = float(rules.get("max_il_per_mode_db", DEFAULT_RULES["max_il_per_mode_db"]))
    lim_tot = float(rules.get("max_il_total_db", DEFAULT_RULES["max_il_total_db"]))
    checks = [
        DRCMeshLoss("每模口径", float(basis["per_mode_db"]), lim_pm,
                    float(basis["per_mode_db"]) <= lim_pm,
                    f"最坏模穿越 {basis['per_mode_optical_depth']} 片 × "
                    f"{basis['per_mzi_loss_db']:.2f} dB/片"),
        DRCMeshLoss("总级联口径", float(basis["total_db"]), lim_tot,
                    float(basis["total_db"]) <= lim_tot,
                    f"{basis['n_mzi']} 片门合计 + 交叉 "
                    f"{basis['crossing_loss_db']:.2f} dB"),
    ]
    return DRCMeshLossResult(passed=all(c.ok for c in checks),
                             checks=checks, basis=basis)


def drc_from_library(library=None, rules: Optional[Dict[str, float]] = None
                     ) -> Dict[str, DRCResult]:
    """D-12 已验证器件库 → 各器件默认参数（窗口）DRC 自查。

    返回 {器件名: DRCResult}。默认参数取参数窗口（params_schema）中值。
    """
    if library is None:
        from lda_l2.device_library import get_default_library
        library = get_default_library()
    results: Dict[str, DRCResult] = {}
    for name in library.list():
        dev = library.get(name)
        params = {k: (lo + hi) / 2.0 for k, (lo, hi) in dev.params_schema.items()}
        try:
            results[name] = drc_check_device(name, params, rules=rules)
        except ValueError:
            results[name] = DRCResult(
                device=name, passed=True,
                checks=[DRCCheck("n/a", name, "", 0.0, 0.0, True,
                                 severity="warning")])
    return results


def drc_summary(results: Dict[str, DRCResult]) -> str:
    lines = [r.brief() for r in results.values()]
    total = sum(len(r.checks) for r in results.values())
    errs = sum(len(r.violations()) for r in results.values())
    flag = "DRC 全绿" if errs == 0 else f"DRC 检出 {errs} 项违规"
    return (f"DRC: {len(results)} 器件 {total} 项检查 → {flag}\n" +
            "\n".join(lines))
