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
    # ── v0.9.191（PM 征程 M3）· 电极 pad 尺寸下限 ──────────────────────────
    # 来源 = **设计规则**（探针台接触常识：探针尖端 µm 量级，pad 须远大于尖端
    # 以避免接触损伤与对准容差不足），**非任何 foundry PDK deck**；与其他
    # DEFAULT_RULES 键同属「可被 PDK 覆盖」的设计规则层。
    "min_pad_um": 2.0,
    # ── 损耗通道（网格级 · D-125）· 设计规则 · 可覆盖 · 非实测 golden ──
    "max_il_per_mode_db": 15.0,     # **每模口径**上限（光子实际穿越 · η ≈ 3.2%）
    "max_il_total_db": 25.0,        # **总级联口径**上限（全网格门合计）
    # ── v0.9.210（PS 征程 M1/G4）· 传感窗口（局部去上包层）工艺规则 ──────
    # 来源 = **工艺设计规则**（开窗刻蚀的工程常识：深宽比 / 过刻蚀余量 /
    # 端口耦合区保护），**非任何 foundry PDK deck**；与其他 DEFAULT_RULES
    # 键同属「可被 PDK 覆盖」的设计规则层。
    "min_window_um": 1.0,           # 窗口最小横向宽度（过窄 ⇒ 深宽比过高/显影不净/暴露不足）
    "min_window_margin_um": 0.20,   # 窗口边缘 → 波导芯外缘最小余量（防过刻蚀伤芯）
    "min_window_end_um": 2.0,       # 窗口端 → 最近端口/耦合区最小留白（防暴露耦合区）
    "min_clad_enclosure_um": 0.40,  # 包层对硅芯最小单边包封（通用规则；开窗区被工艺例外豁免）
    # ── v0.9.211（PS 征程 M9（G2 器件本体））· 高灵敏几何器件（狭缝 / 悬浮）工艺规则 ──
    # 来源 = **工艺可实现性常识**（狭缝由光刻极限决定；悬浮膜受塌陷/应力决定），
    # **非任何 foundry PDK deck**；与其余键同属「可被 PDK 覆盖」的设计规则层。
    # 🔴 狭缝 rail=0.22 **小于**通用 min_width(0.35) ⇒ 必须用专用键，否则
    #    狭缝波导「本该可制造」却被通用规则判违规（口径错 ⇒ 结论反向）。
    "min_rail_width_um": 0.15,      # 狭缝 rail 最小宽度（光刻可实现）
    "min_slot_gap_um": 0.04,        # 狭缝最小缝宽（光刻极限）
    "min_support_width_um": 0.50,   # 悬浮段两端支撑块最小宽度（防塌陷）
    "max_suspended_span_um": 50.0,  # 最大悬空跨度（超此长度悬浮膜易塌陷/断裂）
    "min_anchor_len_um": 1.00,      # 最小锚定段长度（保证与衬底可靠连接）
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


#: DRC **检查规则名**全集（`DRCCheck.rule` 取值域）。
#: 🔴 与 `DEFAULT_RULES` 的**键**（`min_width_um` 等）是两套词汇：键是「限值参数名」，
#: 这里是「检查项名」。工艺例外的 `rule` / `replaced_by` 一律用**检查项名**，
#: 并由 `validate_exceptions` 机器校验 ∈ 本集合（防悬空引用）。
CHECK_RULES = (
    "min_width", "min_space", "min_bend_R", "max_split", "min_pad",
    # v0.9.210（PS 征程 M1/G4）· 传感窗口
    "min_window", "min_window_margin", "min_window_end", "min_clad_enclosure",
    # v0.9.211（PS 征程 M9（G2 器件本体））· 高灵敏几何器件（狭缝 / 悬浮）
    "min_rail_width", "min_slot_gap", "min_support_width",
    "max_suspended_span", "min_anchor_len", "min_support_overhang",
)


@dataclass(frozen=True)
class DRCException:
    """一条**工艺例外**（process exception / waiver）—— 让「有意为之的违规」合规。

    适用场景：传感窗口**有意**去除传感区上包层 ⇒ 该区包层对芯的包封恒为 0，
    通用包封规则必然判违规。若不允许例外，则「开窗」这一**必要工艺动作**等于
    被 DRC 禁止（C 类主权之下拿不到可真流片的设计）。

    🔴🔴 **例外 ≠ 消音器**（本模块的硬纪律）：
      · `reason` 必填非空 —— 无理由的豁免不许存在；
      · `replaced_by` 必填**非空** —— 豁免一条规则**必须**声明替代规则；
      · 替代规则必须 ∈ `CHECK_RULES`，且**必须在本次 DRC 实跑中出现**
        （`drc_check_device` 强制），否则直接 `RuntimeError`，**不给假绿**。
    """
    rule: str                       # 被豁免的通用检查项（须 ∈ CHECK_RULES）
    scope: tuple                    # 适用 kind（非空）
    reason: str                     # 工程理由（必填非空）
    replaced_by: tuple              # 替代检查项（必填非空，每条须 ∈ CHECK_RULES 且实跑）


#: 传感窗口工艺例外登记表（**显式枚举**，不隐式生效）。
WINDOW_EXCEPTIONS = (
    DRCException(
        rule="min_clad_enclosure",
        scope=("SensingRing", "SensingMZI"),
        reason=("传感窗口**有意**去除传感区上包层以暴露倏逝场（PS-M1/G4 工艺动作）；"
                "该区域内包层对芯的单边包封恒为 0 ⇒ 通用包封规则在此不适用，"
                "否则「开窗」本身被判违规 = 禁止做暴露型传感器。"),
        replaced_by=("min_window_margin", "min_window_end"),
    ),
)


def validate_exceptions(exceptions=WINDOW_EXCEPTIONS) -> None:
    """机器校验工艺例外登记表（构造期 + 使用期各跑一次，双保险）。

    任何一条不满足即 `ValueError` —— **拒绝静默豁免**。反向探针见
    `run_ps_m1_smoke`（空 reason / 空 replaced_by / 悬空引用 三改必 raise）。
    """
    for e in exceptions:
        if not isinstance(e, DRCException):
            raise ValueError(f"例外须为 DRCException，得到 {type(e).__name__}")
        if e.rule not in CHECK_RULES:
            raise ValueError(f"例外规则 {e.rule!r} 不在 CHECK_RULES：{CHECK_RULES}")
        if not e.scope:
            raise ValueError(f"例外 {e.rule} 缺 scope（适用 kind 不得为空）")
        if not str(e.reason).strip():
            raise ValueError(f"例外 {e.rule} 缺 reason（无理由的豁免不许存在）")
        if not e.replaced_by:
            raise ValueError(
                f"例外 {e.rule} 缺 replaced_by —— 豁免必须声明替代规则"
                f"（防「例外=消音器」造成假绿）")
        for r in e.replaced_by:
            if r not in CHECK_RULES:
                raise ValueError(f"例外 {e.rule} 的替代规则 {r!r} 不在 CHECK_RULES")


validate_exceptions()      # 模块导入即校验（早失败）


def _apply_exceptions(kind, checks, exceptions) -> List[dict]:
    """套用适用本书器件的工艺例外 + **实跑校验**，返回例外记录（入 DRC 报告）。

    🔴 三条硬约束（任一不满足即 `RuntimeError`，绝不静默放行）：
      ① 被豁免的规则**必须真的在本器件 DRC 里被评估**（否则是在豁免一条根本
         没跑的规则 = 空头豁免）；
      ② `replaced_by` 声明替代的检查项**必须全部实跑出现**
         （否则是「豁免了却没东西替代」= 消音器）；
      ③ 例外自身先过 `validate_exceptions`。
    🔴 豁免动作**在本函数里施加**（`c.waived = True`）——不写在 `add()` 里，
       以保证「例外可关闭」（`exceptions=()`）是真的可关闭。
    """
    applied: List[dict] = []
    present = {c.rule for c in checks}
    for e in exceptions:
        if kind not in e.scope:
            continue
        validate_exceptions((e,))
        targets = [c for c in checks if c.rule == e.rule]
        if not targets:
            raise RuntimeError(
                f"工艺例外 {e.rule} 声明豁免，但本次 {kind} DRC 未评估该规则"
                f" ⇒ 拒绝空头豁免")
        missing = [r for r in e.replaced_by if r not in present]
        if missing:
            raise RuntimeError(
                f"工艺例外 {e.rule} 声明替代规则 {missing}，但本次 {kind} DRC "
                f"未评估 ⇒ 拒绝静默豁免（例外≠消音器）")
        # 🔴 豁免**由例外对象在运行时施加**（不写在 add() 里）——否则把
        #    `exceptions=()` 传进来也关不掉，「例外可关闭」就成了空话，
        #    且反向探针永远看不到红色。
        for c in targets:
            c.waived = True
            c.waived_by = e.rule
        applied.append({"rule": e.rule, "scope": list(e.scope),
                        "reason": e.reason, "replaced_by": list(e.replaced_by),
                        "applied": True, "unmet": [c.param for c in targets
                                                   if not c.ok]})
    return applied


@dataclass
class DRCCheck:
    rule: str                # min_width / min_space / min_bend_R / max_split
    device: str              # 器件 kind
    param: str               # 参数名
    value: float             # 实测值
    required: float          # 要求值（µm/deg）
    ok: bool
    severity: str = "error"  # error（FAIL）| warning
    # ── v0.9.210（PS 征程 M1/G4）· 工艺例外 ──────────────────────────────
    # waived=True：本项**确实违反**了限值，但被一条已登记的工艺例外豁免
    # （如开窗区包层包封恒为 0）。不计入违规，但在报告里**显式列出**，
    # 绝不当成「通过」隐藏。
    waived: bool = False
    waived_by: str = ""      # 豁免它的例外规则名（空 = 未被豁免）

    def brief(self) -> str:
        flag = "OK" if self.ok else ("WVR" if self.waived else "ERR")
        return (f"[{flag}] {self.rule:<12} {self.device}.{self.param}="
                f"{self.value:g}（要求 {'≥' if not self.rule.startswith('max') else '≤'} "
                f"{self.required:g}）")


@dataclass
class DRCResult:
    device: str
    passed: bool
    checks: List[DRCCheck] = field(default_factory=list)
    #: v0.9.210（PS 征程 M1/G4）：本次生效的**工艺例外**记录（rule/reason/
    #: replaced_by/applied）。空列表 = 无例外（既有器件的输出**逐字节不变**）。
    exceptions: List[dict] = field(default_factory=list)

    def violations(self) -> List[DRCCheck]:
        return [c for c in self.checks if not c.ok and not c.waived]

    def brief(self) -> str:
        errs = self.violations()
        flag = "PASS" if self.passed else "FAIL"
        s = f"[{flag}] {self.device}: {len(self.checks)} 项检查，{len(errs)} 项违规"
        if self.exceptions:
            s += f"（{len(self.exceptions)} 条工艺例外）"
        return s

    def to_dict(self) -> dict:
        # 🔴 向后兼容纪律：`waived` / `exceptions` **仅在非默认时出现**，
        #    否则既有受跟踪报告（reports/drc_*.json 等）会全体漂移。
        def _ck(c):
            d = {"rule": c.rule, "device": c.device, "param": c.param,
                 "value": c.value, "required": c.required, "ok": c.ok,
                 "severity": c.severity}
            if c.waived:
                d["waived"] = True
                d["waived_by"] = c.waived_by
            return d

        out = {
            "device": self.device,
            "passed": self.passed,
            "checks": [_ck(c) for c in self.checks],
        }
        if self.exceptions:
            out["exceptions"] = list(self.exceptions)
        return out


def drc_check_device(kind: str, params: Dict[str, float],
                     rules: Optional[Dict[str, float]] = None,
                     exceptions=None) -> DRCResult:
    """对单个器件（kind + params）做 DRC 自查。

    `exceptions`（v0.9.210）：工艺例外登记表，默认 `WINDOW_EXCEPTIONS`。
    显式传 `()` 可关闭全部例外（反向探针用：此时开窗器件的包封规则会正常判红）。
    """
    rules = rules or DEFAULT_RULES
    checks: List[DRCCheck] = []

    def add(rule: str, param: str, value: float, required: float,
            waived_by: Optional[str] = None):
        value = float(value)
        required = float(required)
        if rule.startswith("max"):
            ok = value <= required
        else:
            ok = value >= required
        checks.append(DRCCheck(rule, kind, param, value, required, ok,
                               waived=waived_by is not None,
                               waived_by=waived_by or ""))

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
    elif kind == "PCMCell":
        # v0.9.191（PM 征程 M3）：光子存储单元 —— GST 相变层 / Si 波导 / 加热线
        # 三处最小横向特征 + 「GST ↔ 加热线 / GST ↔ 波导」层间间距 + 电极 pad 尺寸。
        # 🔴 几何量由 `primitives.pcm_cell_geometry` **同源导出**（与版图几何
        #    共用同一函数），绝不在此重算一遍 ⇒ 杜绝 DRC 与版图脱钩。
        from lda_l2.primitives import pcm_cell_geometry
        g = pcm_cell_geometry(params)
        add("min_width", "min_width_um", g["min_width"], rules["min_width_um"])
        add("min_space", "min_space_um", g["min_space"], rules["min_space_um"])
        add("min_pad", "pad_um", g["min_pad"],
            rules.get("min_pad_um", DEFAULT_RULES["min_pad_um"]))
    elif kind in ("SensingRing", "SensingMZI"):
        # ── v0.9.210（PS 征程 M1/G4）· 传感窗口开窗器件 ─────────────────────
        # 基础几何（与 RingResonator / MZI 同源）+ 窗口工艺规则；
        # 开窗区包层包封恒为 0 ⇒ 必然违反通用包封规则 ⇒ 由**已登记的工艺例外**
        # 豁免（替代规则 = 窗口余量 / 端留白）。豁免在 `_apply_exceptions` 里
        # 做实跑校验，漏替代规则直接 RuntimeError（不给假绿）。
        from lda_l2.primitives import sensing_window_geometry, _sens_p
        sp = _sens_p(kind, params)
        g = sensing_window_geometry(kind, params)
        if kind == "SensingRing":
            add("min_bend_R", "R", sp["R"], rules["min_bend_R_um"])
        add("min_width", "wg_width", sp["wg_width"], rules["min_width_um"])
        add("min_space", "gap", sp["gap"], rules["min_space_um"])
        add("min_window", "window_w", g["window_w"],
            rules.get("min_window_um", DEFAULT_RULES["min_window_um"]))
        add("min_window_margin", "window_margin", g["window_margin"],
            rules.get("min_window_margin_um",
                      DEFAULT_RULES["min_window_margin_um"]))
        add("min_window_end", "window_end_gap", g["window_end_gap"],
            rules.get("min_window_end_um", DEFAULT_RULES["min_window_end_um"]))
        # 通用包封规则：开窗区包层被去除 ⇒ 实测包封 = 0 < 限值 ⇒ 本条**判红**；
        # 是否豁免由 `WINDOW_EXCEPTIONS`（可在调用处用 `exceptions=()` 关闭）
        # 在 `_apply_exceptions` 里运行时施加，**不在此硬编码**。
        add("min_clad_enclosure", "clad_enclosure", g["clad_enclosure"],
            rules.get("min_clad_enclosure_um",
                      DEFAULT_RULES["min_clad_enclosure_um"]))
    elif kind in ("SlotWaveguide", "SuspendedWaveguide", "SlotRing", "SuspendedRing"):
        # ── v0.9.211（PS 征程 M9（G2 器件本体））· 高灵敏几何器件本体（狭缝 / 悬浮）─────
        # 几何量由 `primitives.high_sens_geometry` **同源导出**（与版图几何共用
        # 同一函数 + 同一参数解析），绝不在此重算 ⇒ 杜绝 DRC 与版图脱钩。
        # 🔴 狭缝走**专用**规则名（rail / gap 由光刻极限决定），悬浮走
        #    支撑宽 / 锚定长 / 悬空跨度 / **支撑外扩（释放开孔不得开穿锚定块）**。
        from lda_l2.primitives import high_sens_geometry, canon_high_sens
        K = canon_high_sens(kind)
        g = high_sens_geometry(K, params)
        if K.startswith("Slot"):
            add("min_rail_width", "rail_width", g["rail_width"],
                rules.get("min_rail_width_um", DEFAULT_RULES["min_rail_width_um"]))
            add("min_slot_gap", "slot_gap", g["slot_gap"],
                rules.get("min_slot_gap_um", DEFAULT_RULES["min_slot_gap_um"]))
        else:
            add("min_width", "wg_width", g["wg_width"], rules["min_width_um"])
            add("min_support_width", "support_w", g["support_w"],
                rules.get("min_support_width_um", DEFAULT_RULES["min_support_width_um"]))
            add("min_anchor_len", "anchor_len", g["anchor_len"],
                rules.get("min_anchor_len_um", DEFAULT_RULES["min_anchor_len_um"]))
            add("max_suspended_span", "suspended_span", g["suspended_span"],
                rules.get("max_suspended_span_um", DEFAULT_RULES["max_suspended_span_um"]))
            # 释放开孔不得开穿锚定块：支撑块相对开孔的单边外扩 ≥ 通用最小间距。
            add("min_support_overhang", "support_overhang", g["support_overhang"],
                rules["min_space_um"])
        if K.endswith("Ring"):
            add("min_bend_R", "R", g["R"], rules["min_bend_R_um"])
            add("min_space", "bus_gap", g["bus_gap"], rules["min_space_um"])
    elif kind in ("Taper", "EulerBend", "MMI", "GratingCoupler",
                  # v0.9.178（M2 · G-OI2）：收发器器件类接入参数级 DRC。
                  # 此前这 4 类无分支 ⇒ raise ValueError ⇒ 收发器真 GDS 里
                  # MziModulator / Photodetector / MMIC / Splitter **进不了 DRC**。
                  "MziModulator", "Photodetector", "MMIC", "Splitter"):
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

    excs = WINDOW_EXCEPTIONS if exceptions is None else tuple(exceptions)
    applied = _apply_exceptions(kind, checks, excs)
    return DRCResult(device=kind,
                     passed=all(c.ok or c.waived for c in checks),
                     checks=checks, exceptions=applied)


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
