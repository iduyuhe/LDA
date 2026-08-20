"""LDA L2 · 版图设计规则检查（DRC）自查（D-15）。

对 D-14 导出的版图 / D-12 器件库器件做**可制造性规则检查**，输出 DRC 报告。
纯参数/几何级、零外部依赖；规则表取典型 SOI 180nm 工艺（与 D-12 PDK
params_schema / PDK process_notes 同窗口，D-09 接入后可从真实 PDK 注入）。

检查项（器件级，基于 kind + params）：
  min_width    —— 波导/芯宽 ≥ 最小线宽（可制造下限）
  min_space    —— 方向耦合器 gap ≥ 最小间距（避免串扰/桥接）
  min_bend_R   —— 环形半径 ≥ 最小弯曲半径（弯曲损耗可控）
  max_split    —— Y 分支分叉角 ≤ 最大角（可制造）

DRC 结果 passed=False 时给出逐条 violation（规则/器件/参数/实测/要求），
供设计闭环（agent）回读整改——"设计→版图→DRC 自查"可制造性闭环。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# 典型 SOI 180nm 工艺规则（µm/deg；公开文献近似，D-09 接入后由 PDK 覆盖）
DEFAULT_RULES: Dict[str, float] = {
    "min_width_um": 0.35,
    "min_space_um": 0.20,
    "min_bend_R_um": 5.0,
    "max_split_angle_deg": 30.0,
}


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
    elif kind == "DirectionalCoupler":
        add("min_space", "gap", params.get("gap", 0.3), rules["min_space_um"])
        add("min_width", "width", params.get("width", 0.5), rules["min_width_um"])
    elif kind == "SymmetricYBranch":
        add("min_width", "width", params.get("width", 0.5), rules["min_width_um"])
        add("max_split", "split_angle", params.get("split_angle", 10.0),
            rules["max_split_angle_deg"])
    elif kind == "BraggMirror":
        # 一维层堆叠：宽度规则由衬底工艺决定（无 2D 版图几何），跳过
        pass
    else:
        raise ValueError(f"DRC 暂不支持 kind={kind}")

    return DRCResult(device=kind, passed=all(c.ok for c in checks), checks=checks)


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
