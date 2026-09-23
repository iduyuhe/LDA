# -*- coding: utf-8 -*-
"""U8 · 非易失权重后端（PCM / Sb₂Se₃）—— **条件式设计**（设计接口 + 参数化预算）。

背景（内部总结 §4.2 U8 / §4.3 依赖图 / §4.4 执行序第 6 项）
------------------------------------------------------------
「权重物理化」的第三条路：**相变材料（PCM）** 取代热光相移器。
热调的痛点是**静态功耗**（每个 MZI 常年通电以维持相位）；PCM 的相变态**非易失**
⇒ 静态功耗 ≈ 0，只在写入时耗能。§4.2 判该路「收益最大，但**锚最弱**」。

🔴 本项目对 PCM **一个实测器件参数都没有**。故本模块**只做两件事**，不做第三件：

  ① **设计接口** —— 把「相位 φ」映射到「晶化率 c → 电平号 → 文献损耗」。
     与 `lda_layout.mesh_pnr.mesh_drive_manifest` 的 `φ → V` **同形**，
     只是把驱动量从「电压」换成「晶化率」；与 U4 `ring_weight_bank` 的
     权重库接口**同键**（见 `backend_interface_parity`）。
  ② **参数化预算** —— 位深 / retention / endurance / 静态功耗省量 / break-even。
  ③ **不做**（明确拒绝）—— 不宣称「已实现非易失权重」「已达 7-bit」「已校准」；
     不碰 foundry 工艺真值；不跑 FDTD；不做热-电-光闭环。

红线（**机器守卫**，不是文字承诺）
------------------------------------
| 守卫 | 语义 | 触发 |
|---|---|---|
| `guard_no_foundry_process_truth` | 载荷**键名**不得含 foundry/TCAD/工艺角 令牌；且 `foundry_process_truth_used` 必须为假 | raise `NonvolatileRedlineError` |
| `guard_all_anchors_are_not_measured` | 任何锚被标 `is_measured_by_this_project=True` | raise（本项目无 PCM 实测 ⇒ 「已实测」声明本身即 T1 违规） |
| `require_numeric_anchor` | 文献锚缺该字段（如 GST 的 dB/π —— 文献只给「3×3 限制」不给数字） | raise（**宁缺毋滥，绝不外推**） |

🔴 与 U4 的**域政策差异**（不是双标，是物理不同）
----------------------------------------------------
U4 对 `κ ∉ [0,1]` **一律 raise、绝不截断**（因为 κ>1 是**模型失效**，截断会把模型失效
伪装成器件饱和）。本模块对相位**允许 wrap**：`φ mod 2π` 是**精确**的相位周期等价
（`e^{iφ}` 不变），不是近似。故 `c_for_phase(..., wrap=True)` 是合法设计操作，
`wrap=False` 时越域则 raise。两条政策各自正确，差别来自「等价是精确的还是近似的」。

🔴 本模块最硬的三条结论（都是**不利**结论，机器可证）
-------------------------------------------------------
① **PCM 的幅度域动态范围只有 0.2 dB**（= 2 × 0.1 dB/π 文献锚）⇒ 它是**相位**元件，
   **不是**幅度衰减元件 —— 与 U4 微环（a=0.9913 ⇒ 0.038 dB）**同类**缺陷，只是大 5.3×。
② **静态功耗省量是 100% 但绝对瓦数不可引用** —— 项目内部两个热功耗口径相差
   **12.96×**（B29 物理锚 4.630 mW/mm vs P2 工艺假设 60.0 mW/mm）⇒ 只有**比值**
   有意义，绝对 W 不具引用效力。
③ **位深 7-bit 是文献值、不是本项目标定值** —— 与 U4 的「绝对定标差 39.5×」**同源**：
   可达位深取决于 PDK，本项目未标定。

耗时：纯解析（零 FDTD / 零查表）⇒ 单次 < 0.05s（可进 CI core）。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# 1. 文献锚登记表（🔴 全部 `is_measured_by_this_project=False`）
# ---------------------------------------------------------------------------
#: 允许的锚来源类别。**不含** `"measurement"` —— 本项目没有 PCM 实测，
#: 故「measurement」不是可选项，任何此类声明都会被守卫拒绝。
PROVENANCE_KINDS: Tuple[str, ...] = ("literature", "assumption")

#: 文献锚（来源 = 内部总结 §市场对比，公开文献汇总；**均非本项目实测**）。
#:
#: 🔴 两条「无数字」政策：
#:   · `GST.il_db_per_pi = None` —— 文献只给「晶态高损耗 ⇒ 交叉阵列被限制在 3×3
#:     量级」这一定性结论，**不给 dB/π**。本模块**拒绝发明数字**：凡需要该字段的
#:     数值预算一律 `require_numeric_anchor` 报错。
#:   · `retention/endurance` 标 `*_is_lower_bound=True` —— 「>10yr」「>1e8 次」是
#:     **下界**，不是中心值；外推到 20 年地平线**无据**（`retention_budget` 会如实报 False）。
LITERATURE_ANCHORS: Dict[str, Dict[str, Any]] = {
    "Sb2Se3": {
        "provenance": "literature",
        "is_measured_by_this_project": False,
        "signal": "内部总结 §市场对比（器件研究前沿 · 公开文献汇总）",
        "quote": "Sb₂Se₃ PCM：7-bit、retention >10yr、耐久 >1e8 次、~0.1 dB/π",
        "levels_bits": 7.0,
        "retention_years": 10.0,
        "retention_is_lower_bound": True,
        "endurance_cycles": 1.0e8,
        "endurance_is_lower_bound": True,
        "il_db_per_pi": 0.1,
        "crossbar_limit": None,
    },
    "GST": {
        "provenance": "literature",
        "is_measured_by_this_project": False,
        "signal": "内部总结 §市场对比（器件研究前沿 · 公开文献汇总）",
        "quote": "GST 因晶态高损耗，交叉阵列被限制在 3×3 量级",
        "levels_bits": None,          # 🔴 文献未给 ⇒ 不发明
        "retention_years": None,      # 🔴 文献未给 ⇒ 不发明
        "retention_is_lower_bound": None,
        "endurance_cycles": None,     # 🔴 文献未给 ⇒ 不发明
        "endurance_is_lower_bound": None,
        "il_db_per_pi": None,         # 🔴 文献未给 dB/π ⇒ 不发明
        "crossbar_limit": 3,          # 引用性约束（定性），**非**数值建模
    },
    "ModeConverter2026": {
        "provenance": "literature",
        "is_measured_by_this_project": False,
        "signal": "内部总结 §市场对比（Nature 2026 可编程模式转换器）",
        "quote": "Nature 2026 可编程模式转换器 5-bit",
        "levels_bits": 5.0,
        "retention_years": None,
        "retention_is_lower_bound": None,
        "endurance_cycles": None,
        "endurance_is_lower_bound": None,
        "il_db_per_pi": None,
        "crossbar_limit": None,
        "note": "🔴 它是**模式转换器**、不是权重元件 ⇒ 只作**位深量级**参照，不作权重后端。",
    },
}

MATERIALS: Tuple[str, ...] = tuple(LITERATURE_ANCHORS.keys())
DEFAULT_MATERIAL = "Sb2Se3"

#: 🔴 **设计预算（假设）**：单个 PCM 相移器覆盖 [0, 2π] 全摆幅。
#: 这不是文献值、更不是实测值 —— 文献只给「~0.1 dB/π」，未给「一个器件能做多少 π」。
PHASE_FULL_SWING_RAD: float = 2.0 * math.pi

#: 晶化率全域（0 = 非晶、1 = 全晶）。
C_MIN: float = 0.0
C_MAX: float = 1.0

#: B29 热光相移效率**物理锚**实测值（° / mW @ P=1mW、默认鳍模型参数）。
#: 来源：`lda_harness.b29_thermal_phase_anchor.b29_thermal_phase_efficiency()`。
#: 🔴 B29 自身注明「绝对温标为示意、**非 PDK 声明**」⇒ 由它导出的绝对功率继承该限制。
THERMAL_PHASE_EFF_DEG_PER_MW: float = 38.88019612769657

#: π 相移所需电功率（mW）= 180° / 效率。B29 模型对 P **线性** ⇒ 该值即 P_π。
THERMAL_PHASE_PI_POWER_MW: float = 180.0 / THERMAL_PHASE_EFF_DEG_PER_MW

#: 项目内部**另一个**热功耗口径（P2 工艺层假设）：热 VOA 偏置。
#: 来源：`lda_layout.mesh_pnr.equalizer_p2_manifest` 的 `voa_thermal_mw / voa_len_um` 默认值。
#: 🔴 用于**内部口径一致性体检**（见 `power_baseline_consistency`），不作主口径。
P2_VOA_THERMAL_MW: float = 15.0
P2_VOA_LEN_UM: float = 250.0

#: 参照臂长（µm）—— 与 `mesh_drive_manifest(ps_arm_um=1000.0)` / U4 `PS_ARM_UM_DEFAULT` 同源。
ARM_REF_UM: float = 1000.0

#: WDM 共享网格参照规模（U1 实测：K=4 × N=16 ⇒ 120 MZI + 16 输出相移器）。
WDM_N_MZI_REF: int = 120
WDM_N_OUT_REF: int = 16

#: 🔴 **假设值**（非实测）：写入时功率 / 热调静态功率之比。
#: 用于 break-even 占空比闭式；绝对写入能耗本项目无锚 ⇒ 只用**比值**。
WRITE_POWER_RATIO_DEFAULT: float = 10.0

#: 🔴 **假设值**（非实测）：单次写入耗时（s）。
WRITE_TIME_S_DEFAULT: float = 1.0e-6

#: 诚实边界声明（smoke 断言键集完整，防被悄悄删）
NVM_DISCLOSURE: Dict[str, str] = {
    "scope": (
        "只做「PCM 相变相移器作非易失权重后端」的**设计层**建模："
        "φ→c 映射 / 位深预算 / retention·endurance 外推 / 静态功耗省量 / break-even。"
        "不做器件级签核、不做热-电-光闭环、不做写入策略与时序、不做可靠性验证。"
    ),
    "literature_anchor_not_measurement": (
        "🔴 **文献锚 ≠ 实测**：本模块全部器件级数字（7-bit / >10yr / >1e8 次 / 0.1 dB/π）"
        "来自**公开文献汇总**（内部总结 §市场对比），本项目**未做任何 PCM 器件表征**。"
        "文中所有结论都是**条件式**的，条件即「文献值成立」。"
    ),
    "no_foundry_process_truth": (
        "🔴 **红线**：不碰 foundry 工艺真值（无 NDA / 无准入 / 无 TCAD 真值）。"
        "机器守卫 `guard_no_foundry_process_truth()` 在报告生成必经路径上运行。"
    ),
    "no_capability_claim": (
        "🔴 **不做能力宣称**：不声明「已实现非易失权重」「已达 7-bit」「已校准」「已省电」。"
        "本模块交付的是**设计接口 + 参数化预算**，不是能力证明（§4.2 U8 判据原文："
        "「先做设计接口 + 参数化预算，不做能力宣称」）。"
    ),
    "phase_element_not_attenuator": (
        "🔴 PCM 的**幅度域动态范围只有 0.2 dB**（= 2 × 0.1 dB/π 文献锚）⇒ 它是**相位**元件，"
        "**不是**幅度衰减元件。与 U4 微环（a=0.9913 ⇒ 仅 0.038 dB）**同类**缺陷，只是大 5.26×。"
        "⇒ 二者都只能做「相位/非负标量」类权重，不能做宽带可变衰减器。"
    ),
    "full_swing_is_design_assumption": (
        "🔴 **设计预算（假设）**：[0, 2π] 全摆幅是**假设**，非文献值、非实测值。"
        "文献只给「~0.1 dB/π」，未给「一个器件能覆盖多少 π」。改变该假设会线性改变位深与损耗预算。"
    ),
    "bit_depth_is_literature_not_calibrated": (
        "🔴 **位深 7-bit 是文献值、不是本项目标定值** —— 与 U4 的「绝对定标差 39.5×」**同源**："
        "可达位深取决于 PDK 与实际写入策略，本项目未标定。dB 域的「位深 == 文献位深」"
        "是**线性模型的恒等式**（不是测得），只能证明模型自洽、不能证明器件达标。"
    ),
    "power_baseline_order_level_uncertainty": (
        "🔴 **功耗基线本身有量级级不确定度**：项目内部两个热功耗口径相差 **12.96×**"
        "（B29 物理锚 4.630 mW/mm vs P2 工艺假设 60.0 mW/mm）。且 B29 自述「绝对温标为示意、"
        "非 PDK 声明」⇒ **绝对瓦数不可引用**，只有「静态功耗省 100%」这一**比值**结论有效。"
    ),
    "zero_static_power_is_inference_not_measurement": (
        "🔴 **零静态功耗是器件物理推论（非易失），不是本项目实测**：无实物、无光测、无老化台。"
        "写入能耗亦无锚（只用**假设比值** `WRITE_POWER_RATIO_DEFAULT`）⇒ break-even 是条件式。"
    ),
    "retention_endurance_are_lower_bounds": (
        "🔴 「>10yr」「>1e8 次」是**下界**（`*_is_lower_bound=True`），不是中心值 ⇒ "
        "外推到 20 年地平线**无据**（`retention_budget` 如实报 `meets_horizon=False`）。"
        "本模块不做加速老化、不出寿命保证。"
    ),
    "material_choice_is_tradeoff_not_free_win": (
        "🔴 材料选择是**取舍**不是免费收益：GST 因晶态高损耗把交叉阵列限制在 **3×3 量级**"
        "（引用性定性约束）；Sb₂Se₃ 低损耗（0.1 dB/π）但文献只给到 7-bit。"
        "本模块对 GST **不给任何数值预算**（文献未给 dB/π ⇒ 拒绝发明数字）。"
    ),
    "no_fdtd_no_3d_no_closed_loop": (
        "本模块**不跑 FDTD、不做 3D、不做热-电-光闭环**：纯解析（线性混合模型 + 文献常数）。"
        "波导模式/模式重叠/多模干涉等物理细节**不在**本模块范围内。"
    ),
    "ledger_unchanged": (
        "本模块**零锚改动、零账本变化**：不新增验证锚、不改 `_PHYSICAL_LAW`、不改 golden。"
        "文献锚**不构成**验证锚（T2 真值永久锁）。"
    ),
}


class NonvolatileBackendError(Exception):
    """参数越界 / 缺锚 / 前置条件不满足（不是「数值不达标」）。"""


class NonvolatileRedlineError(NonvolatileBackendError):
    """🔴 红线违规（承载 foundry 工艺真值 / 声称已实测）。

    继承自 `NonvolatileBackendError` 以便调用方一处捕获；语义上代表**边界**被触碰，
    区别于普通的数值输入错误。
    """


# ---------------------------------------------------------------------------
# 2. 红线守卫（机器化，非文字承诺）
# ---------------------------------------------------------------------------
#: 载荷**键名**禁止出现的工艺真值令牌（小写比较）。
#: 🔴 只扫**键名**、不扫散文值 —— 否则本模块自身的披露文本（明写「不碰 foundry」）
#: 会误触发。这是**有意**的设计；smoke 用一对正反例把「不扫散文」钉住。
_FORBIDDEN_PROCESS_TOKENS: Tuple[str, ...] = (
    "foundry", "tcad", "process_corner", "process_truth", "pdk_truth",
    "silicon_truth", "tapeout_truth", "工艺角", "工艺真值", "实测工艺",
)

#: 必须在报告中显式为假的声明键。
#: 🔴 该键名**本身**含禁令牌（foundry / process_truth）⇒ 键扫描必须**显式豁免**它，
#: 否则守卫「按构造恒红」= 无用护栏。豁免是有意设计，smoke 用一对正反例钉住。
_FOUNDRY_TRUTH_FLAG = "foundry_process_truth_used"


def _scan_keys(payload: Any, hits: List[str], path: str = "$") -> None:
    """递归收集载荷中命中禁令牌的**键名**（不进散文值；豁免声明键本身）。"""
    if isinstance(payload, dict):
        for k, v in payload.items():
            if str(k) == _FOUNDRY_TRUTH_FLAG:
                continue                      # 声明键单独判（见下）
            ks = str(k).lower()
            for tok in _FORBIDDEN_PROCESS_TOKENS:
                if tok in ks:
                    hits.append("%s.%s" % (path, k))
                    break
            _scan_keys(v, hits, "%s.%s" % (path, k))
    elif isinstance(payload, (list, tuple)):
        for i, v in enumerate(payload):
            _scan_keys(v, hits, "%s[%d]" % (path, i))


def _collect_flag_values(payload: Any, out: List[Any]) -> None:
    """递归收集任意深度上 `_FOUNDRY_TRUTH_FLAG` 的值。"""
    if isinstance(payload, dict):
        for k, v in payload.items():
            if str(k) == _FOUNDRY_TRUTH_FLAG:
                out.append(v)
            _collect_flag_values(v, out)
    elif isinstance(payload, (list, tuple)):
        for v in payload:
            _collect_flag_values(v, out)


def guard_no_foundry_process_truth(payload: Any, where: str = "U8") -> None:
    """🔴 红线守卫：非易失权重后端的**设计层载荷**不得承载 foundry 工艺真值。

    判两件事：
      ① 递归**键名**命中 `_FORBIDDEN_PROCESS_TOKENS` ⇒ raise
         （**豁免**声明键 `_FOUNDRY_TRUTH_FLAG` 自身 —— 否则守卫恒红、等于没有）；
      ② 任意深度出现 `_FOUNDRY_TRUTH_FLAG` 且为真值 ⇒ raise（本项目无 foundry 准入）。

    空载荷 / 合法载荷 ⇒ 静默通过（「合法必过」）。
    """
    hits: List[str] = []
    _scan_keys(payload, hits)
    if hits:
        raise NonvolatileRedlineError(
            "红线违规（%s）：载荷键名承载 foundry 工艺真值 —— %s。"
            "本项目无 NDA / 无 foundry 准入 ⇒ 设计层不得出现该字段。" % (where, "; ".join(hits)))
    flags: List[Any] = []
    _collect_flag_values(payload, flags)
    truthy = [f for f in flags if f]
    if truthy:
        raise NonvolatileRedlineError(
            "红线违规（%s）：`%s`=%r（共 %d 处为真）—— 本项目**没有** foundry 工艺真值，"
            "该声明本身即 T1 铁律违规。" % (where, _FOUNDRY_TRUTH_FLAG, truthy[0], len(truthy)))


def guard_all_anchors_are_not_measured(
        anchors: Optional[Dict[str, Dict[str, Any]]] = None,
        where: str = "U8") -> None:
    """🔴 红线守卫：任何锚都不得声明「本项目已实测」。

    每个锚必须满足：`provenance ∈ PROVENANCE_KINDS` 且
    `is_measured_by_this_project is False`。违反 ⇒ `NonvolatileRedlineError`。
    """
    src = LITERATURE_ANCHORS if anchors is None else anchors
    for name, a in src.items():
        prov = a.get("provenance")
        if prov not in PROVENANCE_KINDS:
            raise NonvolatileRedlineError(
                "红线违规（%s）：锚 %r 的 provenance=%r 不在允许类别 %s 内。"
                % (where, name, prov, PROVENANCE_KINDS))
        if a.get("is_measured_by_this_project") is not False:
            raise NonvolatileRedlineError(
                "红线违规（%s）：锚 %r 标 is_measured_by_this_project=%r —— "
                "本项目**没有**任何 PCM 器件实测，「已实测」声明本身即 T1 违规。"
                % (where, name, a.get("is_measured_by_this_project")))


def require_numeric_anchor(mat: str, field: str) -> float:
    """取锚的**数值**字段；缺失（`None`）⇒ raise（**宁缺毋滥，绝不外推**）。"""
    a = _anchor(mat)
    if field not in a:
        raise NonvolatileBackendError("锚 %r 无字段 %r" % (mat, field))
    val = a[field]
    if val is None:
        raise NonvolatileBackendError(
            "锚 %r 的字段 %r 为 None（文献未给数字，如 GST 的 dB/π）⇒ "
            "本模块拒绝发明数字，宁缺毋滥。原始引用：%s" % (mat, field, a.get("quote")))
    return float(val)


def _anchor(mat: str) -> Dict[str, Any]:
    if mat not in LITERATURE_ANCHORS:
        raise NonvolatileBackendError(
            "未知材料 %r（可选 %s）" % (mat, list(MATERIALS)))
    return LITERATURE_ANCHORS[mat]


# ---------------------------------------------------------------------------
# 3. 器件级编程态模型（透射率-编程态曲线）
# ---------------------------------------------------------------------------
#: 线性混合模型 = **设计层假设**（有效介质近似的线性化）。
#: 🔴 与文献锚「~0.1 dB/π」是**两件事**：锚给的是「每 π 相移的损耗」，
#: 线性混合给的是「损耗随晶化率如何增长」。前者是文献值，后者是模型假设。
_MIXING_MODEL = "linear_in_crystallinity"


def _check_c(c: float) -> None:
    if not (C_MIN <= c <= C_MAX):
        raise NonvolatileBackendError(
            "晶化率 c 必须 ∈ [%.1f, %.1f]（收到 %.6f）—— 越域是**模型失效**而非器件饱和，"
            "本模块拒绝静默截断（与 U4 `κ ∉ [0,1] 必 raise` 同政策）。" % (C_MIN, C_MAX, c))


def phase_rad(c: float, mat: str = DEFAULT_MATERIAL) -> float:
    """φ(c) = c · 2π —— 相移随晶化率**线性**增长（设计层假设，见 `_MIXING_MODEL`）。"""
    _check_c(c)
    _anchor(mat)
    return c * PHASE_FULL_SWING_RAD


def il_db(c: float, mat: str = DEFAULT_MATERIAL) -> float:
    """IL(c) = (φ(c)/π) · `il_db_per_pi`（**文献锚**：Sb₂Se₃ 0.1 dB/π）。

    域：c ∈ [0,1]；缺 `il_db_per_pi`（GST）⇒ raise。
    """
    _check_c(c)
    per_pi = require_numeric_anchor(mat, "il_db_per_pi")
    return (phase_rad(c, mat) / math.pi) * per_pi


def transmittance(c: float, mat: str = DEFAULT_MATERIAL) -> float:
    """T(c) = 10^(−IL(c)/10) ∈ [T(1), 1] —— **非负**实权重（与 U4 「权重非负」同政策）。"""
    return 10.0 ** (-il_db(c, mat) / 10.0)


def wrap_phase(phi_rad: float) -> float:
    """把相位折到 [0, 2π) —— **精确**等价（`e^{iφ}` 不变），不是近似。"""
    return phi_rad % PHASE_FULL_SWING_RAD


def c_for_phase(phi_rad: float, mat: str = DEFAULT_MATERIAL,
                wrap: bool = True) -> float:
    """φ → c 的**闭式反演**：c = (φ mod 2π)/2π。

    `wrap=True`（默认）：越域相位折回（**精确**等价）。`wrap=False`：越域 ⇒ raise。
    🔴 与 U4 的「绝不截断」政策不同 —— 那里的截断会把**模型失效**伪装成器件饱和；
    这里的 wrap 是**精确**的周期等价。两条政策各自的物理不同。
    """
    _anchor(mat)
    if not isinstance(phi_rad, (int, float)) or not math.isfinite(float(phi_rad)):
        raise NonvolatileBackendError("相位必须是有限实数，收到 %r" % (phi_rad,))
    p = float(phi_rad)
    if wrap:
        p = wrap_phase(p)
    elif not (0.0 <= p <= PHASE_FULL_SWING_RAD):
        raise NonvolatileBackendError(
            "相位 %.6f rad 在 [0, 2π] 之外且 wrap=False ⇒ raise（不静默折回）" % p)
    return p / PHASE_FULL_SWING_RAD


def c_for_il_db(il_target_db: float, mat: str = DEFAULT_MATERIAL) -> float:
    """IL → c 的闭式反演（需 `il_db_per_pi` 非 None）。越出 [0, IL_max] ⇒ raise。"""
    per_pi = require_numeric_anchor(mat, "il_db_per_pi")
    il_max = (PHASE_FULL_SWING_RAD / math.pi) * per_pi
    if not (0.0 <= il_target_db <= il_max):
        raise NonvolatileBackendError(
            "目标插损 %.6f dB 在可达区间 [0, %.6f] dB 之外 ⇒ 物理不可达（非数值问题）"
            % (il_target_db, il_max))
    return (il_target_db / il_max if il_max > 0 else 0.0) + 0.0   # +0.0 消 −0.0


def c_for_transmittance(t_target: float, mat: str = DEFAULT_MATERIAL) -> float:
    """T → c 的闭式反演。T ∈ [T(1), 1] 之外 ⇒ raise。"""
    if not (0.0 < t_target <= 1.0):
        raise NonvolatileBackendError("透射率必须 ∈ (0, 1]，收到 %r" % (t_target,))
    return c_for_il_db(-10.0 * math.log10(t_target), mat)


def programming_window(mat: str = DEFAULT_MATERIAL) -> Dict[str, Any]:
    """可编程窗口：c / φ / IL / 幅度 的**可达区间**与幅度域动态范围。

    🔴 关键（不利）结论就在这里：`attenuation_dynamic_range_db` 对 Sb₂Se₃ **只有 0.2 dB**
    ⇒ PCM 是相位元件，不是衰减元件。
    """
    per_pi = require_numeric_anchor(mat, "il_db_per_pi")
    il_max = (PHASE_FULL_SWING_RAD / math.pi) * per_pi
    t_min = 10.0 ** (-il_max / 10.0)
    return {
        "mat": mat,
        "mixing_model": _MIXING_MODEL,
        "c_range": [C_MIN, C_MAX],
        "phi_range_rad": [0.0, PHASE_FULL_SWING_RAD],
        "il_range_db": [0.0, il_max],
        "amplitude_range": [t_min, 1.0],
        "attenuation_dynamic_range_db": il_max,
        "il_db_per_pi": per_pi,
        "weight_nonnegative_only": True,
        "note": (
            "幅度域动态范围仅 %.4f dB ⇒ 本器件是**相位**元件。"
            "全摆幅来自 PHASE_FULL_SWING_RAD=2π（**设计假设**）。" % il_max),
    }


# ---------------------------------------------------------------------------
# 4. 位深预算（dB 域自洽性 + 线性 T 域口径对照）
# ---------------------------------------------------------------------------
def level_budget(mat: str = DEFAULT_MATERIAL, bits: Optional[float] = None,
                 n_sweep: int = 2001) -> Dict[str, Any]:
    """多级（bit）预算。

    · **dB 域**：模型对 c 线性 ⇒ 步长恒定 ⇒ 可达位深 **恒等于**所用位深
      （`bits_db == bits_used` 到机器精度）。这是**模型恒等式**，只能证明自洽、
      **不能**证明器件达标（见披露 `bit_depth_is_literature_not_calibrated`）。
    · **线性 T 域**：T(c) 是指数 ⇒ `|dT/dc| ∝ T` 在 c=0 处最大 ⇒ **单点口径高估**
      （与 U4 「单点导数骗人」同构，但幅度小得多：PCM 只有 1.023×，U4 微环是 1.52×）。

    位深来源：`bits=None` ⇒ 取**文献锚**（`bits_source="literature"`）；
    显式传入 ⇒ `bits_source="override"`（调用方自担，报告如实标注）。
    """
    a = _anchor(mat)
    if bits is None:
        bits_used = require_numeric_anchor(mat, "levels_bits")
        src = "literature"
    else:
        bits_used = float(bits)
        src = "override"
    if bits_used <= 0:
        raise NonvolatileBackendError("位深必须 > 0，收到 %r" % (bits_used,))
    levels = 2.0 ** bits_used
    dc = (C_MAX - C_MIN) / levels
    dr_db = il_db(C_MAX, mat)
    phi_step = PHASE_FULL_SWING_RAD / levels
    il_step = dr_db / levels

    # 自洽性（模型恒等式）
    bits_db = math.log2(dr_db / il_step) if il_step > 0 else float("inf")

    # 线性 T 域的档位极差 vs 单点口径（逐档扫，不解析偷懒）
    t_hi, t_lo = transmittance(C_MIN, mat), transmittance(C_MAX, mat)
    t_range = t_hi - t_lo
    kappa = math.log(10.0) / 10.0 * dr_db       # |dT/dc| = kappa · T(c)
    max_slope, mid_slope = 0.0, 0.0
    mid_target = 0.5 * (C_MIN + C_MAX)
    best_d = None
    for i in range(n_sweep):
        c = C_MIN + (C_MAX - C_MIN) * i / (n_sweep - 1)
        s = kappa * transmittance(c, mat)
        if s > max_slope:
            max_slope = s
        d = abs(c - mid_target)
        if best_d is None or d < best_d:
            best_d, mid_slope = d, s
    bits_t_point = math.log2(t_range / (max_slope * dc)) if max_slope > 0 else 0.0
    bits_t_range = math.log2(t_range / (mid_slope * dc)) if mid_slope > 0 else 0.0
    return {
        "mat": mat, "bits_source": src,
        "bits_literature": a.get("levels_bits"), "bits_used": bits_used,
        "levels": levels, "dc": dc,
        "phi_step_rad": phi_step,
        "il_step_db": il_step,
        "dynamic_range_db": dr_db,
        "bits_db": bits_db,
        "bits_db_is_model_identity": True,
        "t_domain": {
            "t_range": t_range, "max_slope_per_c": max_slope,
            "mid_slope_per_c": mid_slope,
            "bits_t_point": bits_t_point, "bits_t_range": bits_t_range,
            "point_overestimates_x": (max_slope / mid_slope) if mid_slope > 0 else None,
        },
        "honest_note": (
            "dB 域位深 %.6f 与所用位深 %.6f 的相等性是**线性模型的恒等式**（不是测得）；"
            "线性 T 域的单点口径高估 %.6f×（远小于 U4 微环的 1.52×，因 IL∝c 线性 ⇒ T 仅弱指数）。"
            % (bits_db, bits_used,
               (max_slope / mid_slope) if mid_slope > 0 else float("nan"))),
    }


def phase_error_max_rad(bits: float) -> float:
    """N-bit 量化在 [0, 2π] 上的**最大**相位误差（= 半步）= π/2^bits。"""
    if bits <= 0:
        raise NonvolatileBackendError("位深必须 > 0，收到 %r" % (bits,))
    return PHASE_FULL_SWING_RAD / (2.0 * 2.0 ** bits)


def bits_for_phase_error(err_rad: float,
                         phi_span_rad: float = PHASE_FULL_SWING_RAD) -> Dict[str, Any]:
    """由「可容忍的最大相位误差」反解位深（设计接口的**反问题**）。

    `levels = ceil(phi_span / (2·err))`；返回**向上取整**的整数位深与真实最大误差。

    🔴 边界语义：要求**严格优于** N-bit 半步（哪怕只小 1e-9）⇒ 必须 N+1 bit。

    🔴 **不需要浮点容差**（早期版本曾加 `PHASE_ERR_REL_TOL`，**已删**）：
    分子分母都是 2 的幂次缩放（`2π/(2·2^bits)`），IEEE 下「恰等于 N-bit 半步」的输入
    给出**精确整数** `n_raw = 2^bits`（实测 128.000000000000000）⇒ `ceil` 恰得 N。
    该容差**无法被任何突变探针证明其必要**（探针 `M09` 删除它后判据仍全绿）⇒
    按铁律「没验证过的护栏不算护栏」**删除**，不留死护栏。
    """
    if err_rad <= 0:
        raise NonvolatileBackendError("误差容限必须 > 0，收到 %r" % (err_rad,))
    if phi_span_rad <= 0:
        raise NonvolatileBackendError("相位跨度必须 > 0，收到 %r" % (phi_span_rad,))
    n_raw = phi_span_rad / (2.0 * err_rad)
    levels = int(math.ceil(n_raw))
    bits = int(math.ceil(math.log2(levels)))
    real_err = phi_span_rad / (2.0 * 2.0 ** bits)
    return {"err_rad": err_rad, "phi_span_rad": phi_span_rad,
            "levels_raw": n_raw, "levels_required": levels, "bits_required": bits,
            "err_at_bits_rad": real_err, "err_at_bits_deg": math.degrees(real_err),
            "within_budget": bool(real_err <= err_rad + 1e-15)}


def quantize_phase(phi_rad: float, bits: float,
                   mat: str = DEFAULT_MATERIAL) -> Dict[str, Any]:
    """把相位量化到 N-bit 电平，返回电平号 / c / 量化相位 / 误差 / 该电平插损。"""
    if bits <= 0:
        raise NonvolatileBackendError("位深必须 > 0，收到 %r" % (bits,))
    levels = 2.0 ** bits
    p = wrap_phase(phi_rad)
    idx = int(round(p / PHASE_FULL_SWING_RAD * levels)) % int(levels)
    p_q = idx / levels * PHASE_FULL_SWING_RAD
    c_q = p_q / PHASE_FULL_SWING_RAD
    return {"phi_rad": phi_rad, "phi_wrapped_rad": p,
            "level_index": idx, "n_levels": int(levels),
            "phi_quant_rad": p_q, "c_required": c_q,
            "err_rad": abs(p_q - p), "err_deg": math.degrees(abs(p_q - p)),
            "il_db": il_db(c_q, mat)}


# ---------------------------------------------------------------------------
# 5. retention / endurance 预算（**纯文献外推**，显式标「下界≠中心值」）
# ---------------------------------------------------------------------------
def retention_budget(mat: str = DEFAULT_MATERIAL,
                     horizon_years: float = 20.0) -> Dict[str, Any]:
    """retention 预算。

    🔴 文献锚是「**>**10yr」（下界）⇒ `meets_horizon` 只在 `horizon ≤ 10` 时为真；
    20 年地平线**无据** ⇒ 如实报 `False`，不外推、不插值。
    """
    if horizon_years <= 0:
        raise NonvolatileBackendError("地平线必须 > 0，收到 %r" % (horizon_years,))
    a = _anchor(mat)
    ry = a.get("retention_years")
    per_pi_ok = a.get("il_db_per_pi") is not None
    meets = bool(ry is not None and horizon_years <= ry)
    return {
        "mat": mat, "horizon_years": horizon_years,
        "retention_years_anchor": ry,
        "retention_is_lower_bound": a.get("retention_is_lower_bound"),
        "meets_horizon": meets,
        "anchor_available": bool(ry is not None and per_pi_ok),
        "note": (
            ("锚 %s 年（%s）≥ 地平线 %.1f 年 ⇒ 在「文献值成立」的前提下满足。"
             % (ry, "下界" if a.get("retention_is_lower_bound") else "中心值", horizon_years))
            if meets else
            ("🔴 地平线 %.1f 年**超出**锚（%s）⇒ 外推无据，如实报不满足。"
             % (horizon_years,
                ("无锚" if ry is None else "%.1f 年%s" % (ry, " 下界" if a.get("retention_is_lower_bound") else ""))))),
        "disclosed": "retention 是文献下界，本项目未做加速老化 / 未出寿命保证",
    }


def endurance_budget(mat: str = DEFAULT_MATERIAL, writes_per_day: float = 1.0,
                     horizon_years: float = 10.0) -> Dict[str, Any]:
    """endurance 预算：`required = writes_per_day · 365 · horizon`。"""
    if writes_per_day < 0:
        raise NonvolatileBackendError("写入频次必须 ≥ 0，收到 %r" % (writes_per_day,))
    if horizon_years <= 0:
        raise NonvolatileBackendError("地平线必须 > 0，收到 %r" % (horizon_years,))
    a = _anchor(mat)
    ec = a.get("endurance_cycles")
    required = writes_per_day * 365.0 * horizon_years
    margin = (ec / required) if (ec is not None and required > 0) else None
    return {
        "mat": mat, "writes_per_day": writes_per_day,
        "horizon_years": horizon_years,
        "writes_total_required": required,
        "endurance_cycles_anchor": ec,
        "endurance_is_lower_bound": a.get("endurance_is_lower_bound"),
        "margin_x": margin,
        "meets_endurance": bool(ec is not None and required <= ec),
        "note": ("🔴 无锚（文献未给 endurance）⇒ 不作判断" if ec is None else
                 ("余量 %.3f×" % margin)),
        "disclosed": "endurance 是文献下界；本模块不做加速老化、不出寿命保证",
    }


def endurance_break_even_writes_per_day(mat: str = DEFAULT_MATERIAL,
                                        horizon_years: float = 10.0) -> Dict[str, Any]:
    """endurance **盈亏平衡**写入频次闭式：`writes* = endurance / (365 · horizon)`。"""
    if horizon_years <= 0:
        raise NonvolatileBackendError("地平线必须 > 0，收到 %r" % (horizon_years,))
    ec = require_numeric_anchor(mat, "endurance_cycles")
    w_star = ec / (365.0 * horizon_years)
    return {"mat": mat, "horizon_years": horizon_years,
            "endurance_cycles_anchor": ec,
            "writes_per_day_star": w_star,
            "note": ("写入频次 < %.1f 次/天 ⇒ 在 %.1f 年地平线内不超耐久（文献下界口径）"
                     % (w_star, horizon_years)),
            "disclosed": "闭式来自文献 endurance 下界，非实测"}


# ---------------------------------------------------------------------------
# 6. 设计接口（与 `mesh_pnr.mesh_drive_manifest` / U4 权重库**同形**）
# ---------------------------------------------------------------------------
#: 与 `mesh_drive_manifest` 必须**共有**的键（同形性的机器判据）。
PARITY_KEYS_VS_DRIVE_MANIFEST: Tuple[str, ...] = ("n_mzi", "n_out", "mzi", "out")

#: 与 U4 `weight_bank_from_weights` 必须**共有**的键。
PARITY_KEYS_VS_WEIGHT_BANK: Tuple[str, ...] = ("weights", "entries", "honest_note")


def nvm_drive_manifest(phis: Sequence[float], mat: str = DEFAULT_MATERIAL,
                       bits: Optional[float] = None,
                       n_mzi: Optional[int] = None) -> Dict[str, Any]:
    """把相位清单映射成**驱动清单**（与 `mesh_drive_manifest` 的 `φ→V` 同形）。

    差异（有意，且被披露）：
      · 驱动量是**晶化率 c** + **电平号 level**，不是电压 V（PCM 是非易失 ⇒ 无保持电压）；
      · 额外报**量化误差**（N-bit 电平 vs 连续相位）；
      · **不报**功耗（PCM 静态功耗恒为 0）—— 「不报」而非「报 0」，避免读者误以为测过。

    `n_mzi=None` ⇒ 全部相位都算作 MZI 内部相移（`mzi` 在前、`out` 为空）；
    传入 `n_mzi`（< len(phis)）⇒ 前 `n_mzi` 项入 `mzi`、其余入 `out`（含末端 D）。
    """
    phs = [float(p) for p in phis]
    if not phs:
        raise NonvolatileBackendError("相位清单不能为空")
    if bits is None:
        bits_used = require_numeric_anchor(mat, "levels_bits")
    else:
        bits_used = float(bits)
    n = len(phs)
    if n_mzi is None:
        n_mzi_eff, n_out_eff = n, 0
    else:
        if not (0 <= int(n_mzi) <= n):
            raise NonvolatileBackendError("n_mzi=%r 必须在 [0, %d] 内" % (n_mzi, n))
        n_mzi_eff, n_out_eff = int(n_mzi), n - int(n_mzi)
    entries = []
    for i, p in enumerate(phs):
        q = quantize_phase(p, bits_used, mat)
        q["role"] = "mzi" if i < n_mzi_eff else "out"
        entries.append(q)
    return {
        "mat": mat, "bits": bits_used, "n_levels": int(2.0 ** bits_used),
        "n_phase_total": n, "n_mzi": n_mzi_eff, "n_out": n_out_eff,
        "mzi": [e for e in entries if e["role"] == "mzi"],
        "out": [e for e in entries if e["role"] == "out"],
        "max_err_rad": max(e["err_rad"] for e in entries),
        "max_err_deg": max(e["err_deg"] for e in entries),
        "static_power_mw": 0.0,
        "static_power_reported": False,
        "honest_note": (
            "驱动量是**晶化率/电平号**（非易失 ⇒ 无保持电压），**不报**功耗 —— "
            "PCM 静态功耗为 0 是**器件物理推论**（未实测）。量化误差是 N-bit 电平的"
            "**固有**误差（最大 π/2^N），不是器件误差模型。"),
        "disclosed": "本清单是**设计接口**产物，不构成能力宣称；绝对电平映射需 PDK 标定",
    }


def weight_bank_from_weights(weights: Sequence[float], wl_nm: Any = 1550.0,
                             mat: str = DEFAULT_MATERIAL,
                             bits: Optional[float] = None) -> Dict[str, Any]:
    """与 U4 `ring_weight_bank.weight_bank_from_weights` **同形**的权重库映射。

    语义：每个 `w` 是**非负幅度**目标（与 U4 同）。映射 `w → IL → c → 电平号`。
    🔴 因幅度域动态范围只有 0.2 dB，**大部分 w < 0.955 都不可达** ⇒ 逐项**显式标注**
    `reachable=False` 与 `unreachable_reason`，**不静默外推**（与 U4 同政策）。
    """
    ws = [float(x) for x in weights]
    if not ws:
        raise NonvolatileBackendError("权重向量不能为空")
    if bits is None:
        bits_used = require_numeric_anchor(mat, "levels_bits")
    else:
        bits_used = float(bits)
    wls = ([float(wl_nm)] * len(ws)) if isinstance(wl_nm, (int, float)) else \
        [float(x) for x in wl_nm]
    if len(wls) != len(ws):
        raise NonvolatileBackendError(
            "wl_nm 长度 %d != weights 长度 %d" % (len(wls), len(ws)))
    win = programming_window(mat)
    t_floor = win["amplitude_range"][0]
    entries: List[Dict[str, Any]] = []
    for w, wl in zip(ws, wls):
        rec: Dict[str, Any] = {"w_target": w, "wl_nm": wl, "mat": mat,
                               "weight_nonnegative_only": True}
        if not (0.0 < w <= 1.0):
            rec.update({"reachable": False, "c_required": None, "il_db": None,
                        "level_index": None, "n_levels": int(2.0 ** bits_used),
                        "quantized_w": None, "rel_err": None,
                        "unreachable_reason": "权重须 ∈ (0, 1]，收到 %r" % (w,)})
            entries.append(rec)
            continue
        if w < t_floor:
            rec.update({"reachable": False, "c_required": None, "il_db": None,
                        "level_index": None, "n_levels": int(2.0 ** bits_used),
                        "quantized_w": None, "rel_err": None,
                        "unreachable_reason": (
                            "w=%.6f 低于可达下限 %.6f（= 10^(−%.4f/10)，受文献损耗锚约束）"
                            % (w, t_floor, win["attenuation_dynamic_range_db"]))})
            entries.append(rec)
            continue
        c = c_for_transmittance(w, mat)
        il = -10.0 * math.log10(w) + 0.0        # +0.0 消 −0.0
        idx = int(round(c * 2.0 ** bits_used)) % int(2.0 ** bits_used)
        c_q = idx / 2.0 ** bits_used
        w_q = transmittance(c_q, mat)
        rec.update({"reachable": True, "c_required": c, "il_db": il,
                    "level_index": idx, "n_levels": int(2.0 ** bits_used),
                    "quantized_w": w_q,
                    "rel_err": abs(w_q - w) / w,
                    "unreachable_reason": None})
        entries.append(rec)
    n_out = sum(1 for e in entries if not e["reachable"])
    return {
        "backend": "pcm_phase_change", "mat": mat, "bits": bits_used,
        "weights": ws, "n_channels": len(entries), "entries": entries,
        "n_unreachable": n_out, "all_reachable": bool(n_out == 0),
        "reachable_window": {"amplitude": list(win["amplitude_range"]),
                             "il_db": list(win["il_range_db"]),
                             "attenuation_dynamic_range_db":
                                 win["attenuation_dynamic_range_db"]},
        "honest_note": (
            "权重 → IL → c 的换算是**闭式**的；但幅度可达窗口仅 %.4f dB ⇒ "
            "%d/%d 个目标权重不可达并已**显式标注**（不静默外推）。"
            "绝对权重未标定（与 U4 的 39.5× 问题同源）。"
            % (win["attenuation_dynamic_range_db"], n_out, len(entries))),
        "disclosed": "本权重库是**设计接口**产物；绝对定标需 PDK + 实测，本项目未标定",
    }


def backend_interface_parity() -> Dict[str, Any]:
    """**同形性机器判据**：与 `mesh_pnr.mesh_drive_manifest` + U4 `ring_weight_bank` 比键集。

    返回三组键集（本模块 / 驱动清单 / U4 权重库）与 **必需共有键** 的命中情况。
    🔴 差异必须**被解释**而不是被容忍 —— `only_*` 字段把差异显式列出。
    """
    import numpy as np

    from lda_layout.mesh_pnr import mesh_drive_manifest      # 局部导入
    from lda_l2.ring_weight_bank import weight_bank_from_weights as u4_bank

    dm = mesh_drive_manifest([(0, 0.1, 0.2, 0)], np.eye(1, dtype=complex),
                             ps_arm_um=ARM_REF_UM)
    mine = nvm_drive_manifest([0.1, 0.2], mat=DEFAULT_MATERIAL)
    u4 = u4_bank([0.02, 0.04], wl_nm=[1550.0, 1552.5])
    mine_bank = weight_bank_from_weights([0.99], mat=DEFAULT_MATERIAL)

    dm_keys, mine_keys, u4_keys, mb_keys = set(dm), set(mine), set(u4), set(mine_bank)
    mz_need = set(PARITY_KEYS_VS_DRIVE_MANIFEST)
    wb_need = set(PARITY_KEYS_VS_WEIGHT_BANK)
    return {
        "drive_manifest_keys": sorted(dm_keys),
        "nvm_manifest_keys": sorted(mine_keys),
        "drive_manifest_shared": sorted(dm_keys & mine_keys),
        "drive_manifest_required": sorted(mz_need),
        "drive_manifest_required_ok": bool(mz_need <= mine_keys),
        "drive_manifest_only_nvm": sorted(mine_keys - dm_keys),
        "drive_manifest_only_dm": sorted(dm_keys - mine_keys),
        "weight_bank_keys": sorted(u4_keys),
        "weight_bank_shared": sorted(u4_keys & mb_keys),
        "weight_bank_required": sorted(wb_need),
        "weight_bank_required_ok": bool(wb_need <= mb_keys),
        "expected_semantic_diff": {
            "drive": "驱动量：V（热光）→ c / level（PCM 非易失）；PCM 额外报量化误差、不报功耗",
            "bank": "U4 用 κ/FWHM/选择性（波长维）；PCM 用 c/电平号/IL（材料维）",
        },
        "honest_note": (
            "同形 ≠ 同物理：本模块与 U4/mesh_pnr **共用调用形状**（便于同名替换实验），"
            "但器件量、可达区间与失效模式完全不同，二者**不可互换**。"),
    }


# ---------------------------------------------------------------------------
# 7. 静态功耗核算（收益的**唯一**来源）
# ---------------------------------------------------------------------------
def thermal_phase_pi_power_mw(
        eff_deg_per_mw: float = THERMAL_PHASE_EFF_DEG_PER_MW) -> float:
    """热光相移器的 π 相移功率（mW）= 180 / η。B29 模型对 P 线性 ⇒ 常数。"""
    if eff_deg_per_mw <= 0:
        raise NonvolatileBackendError("效率必须 > 0，收到 %r" % (eff_deg_per_mw,))
    return 180.0 / eff_deg_per_mw


def power_baseline_consistency() -> Dict[str, Any]:
    """🔴 **内部口径一致性体检**：B29 物理锚 vs P2 工艺假设。

    两个口径都属项目内部、都用于「热功耗」，但相差 **12.96×**（按单位长度比）
    ⇒ 结论：**绝对瓦数不可引用**；只有「静态功耗省 100%」这一**比值**结论成立。
    """
    b29_per_mm = thermal_phase_pi_power_mw() / (ARM_REF_UM / 1000.0)
    p2_per_mm = P2_VOA_THERMAL_MW / (P2_VOA_LEN_UM / 1000.0)
    ratio = p2_per_mm / b29_per_mm
    return {
        "b29_anchor_mw_per_mm": b29_per_mm,
        "p2_assumption_mw_per_mm": p2_per_mm,
        "ratio_p2_over_b29": ratio,
        "within_one_order_of_magnitude": bool(ratio < 10.0),
        "b29_self_disclaimer": "B29 自述「绝对温标为示意、非 PDK 声明」",
        "note": (
            "🔴 项目内部两个热功耗口径相差 **%.2f×/mm**（B29 物理锚 %.4f vs P2 工艺假设 %.2f）"
            "⇒ 功耗基线本身有**量级级**不确定度 ⇒ **绝对瓦数不可引用**，"
            "只有比值（省 100%% 静态功耗）有意义。" % (ratio, b29_per_mm, p2_per_mm)),
    }


def static_power_saving(n_mzi: int = WDM_N_MZI_REF, n_out: int = WDM_N_OUT_REF,
                        eff_deg_per_mw: float = THERMAL_PHASE_EFF_DEG_PER_MW,
                        mat: str = DEFAULT_MATERIAL) -> Dict[str, Any]:
    """静态功耗省量：热调（每相移器常年通电）→ PCM（非易失，静态 0）。

    🔴 省量**恒为 100%**（器件物理推论），但**绝对瓦数继承基线的量级级不确定度**
    （见 `power_baseline_consistency`）⇒ 报告同时给出「不可引用」声明。
    """
    if n_mzi < 0 or n_out < 0:
        raise NonvolatileBackendError("器件数必须 ≥ 0（收到 n_mzi=%r, n_out=%r）"
                                      % (n_mzi, n_out))
    _anchor(mat)
    p_pi = thermal_phase_pi_power_mw(eff_deg_per_mw)
    n_phase = int(n_mzi) + int(n_out)
    p_thermal = n_phase * p_pi
    return {
        "mat": mat, "n_mzi": int(n_mzi), "n_out": int(n_out), "n_phase_total": n_phase,
        "p_pi_mw": p_pi,
        "thermal_static_power_mw": p_thermal,
        "nvm_static_power_mw": 0.0,
        "saved_mw": p_thermal,
        "saving_ratio": 1.0,
        "absolute_mw_quotable": False,
        "note": (
            "热调静态功耗 %.3f mW（= %d 个相移器 × %.4f mW/π）；PCM 静态 **0** ⇒ "
            "省量 100%%。🔴 绝对 mW **不可引用**（基线有量级级不确定度，见 "
            "`power_baseline_consistency`）。" % (p_thermal, n_phase, p_pi)),
        "disclosed": "零静态功耗是器件物理推论（非易失），本项目**未实测**",
    }


def write_power_break_even(p_write_over_p_static: float = WRITE_POWER_RATIO_DEFAULT,
                           t_write_s: float = WRITE_TIME_S_DEFAULT) -> Dict[str, Any]:
    """写入功率 **盈亏平衡占空比** 闭式。

    NVM 平均功耗 = `d · k · P_static`（`d` = 写入占空比、`k` = 写入功率/静态功率）
    ⇒ NVM 胜当且仅当 `d · k < 1` ⇒ **`d* = 1/k`**。
    等价地：重写周期若长于 `k · t_write`，NVM 恒胜。
    """
    if p_write_over_p_static <= 0:
        raise NonvolatileBackendError("功率比必须 > 0，收到 %r" % (p_write_over_p_static,))
    if t_write_s <= 0:
        raise NonvolatileBackendError("写入耗时必须 > 0，收到 %r" % (t_write_s,))
    d_star = 1.0 / p_write_over_p_static
    interval_star = p_write_over_p_static * t_write_s
    return {
        "p_write_over_p_static": p_write_over_p_static,
        "t_write_s": t_write_s,
        "duty_star": d_star,
        "reprogram_interval_star_s": interval_star,
        "nvm_wins_below_duty": bool(d_star > 0),
        "note": (
            "🔴 `k=%.3f` 与 `t_write=%.2e s` 都是**假设值**（本项目无写入能耗锚）⇒ "
            "结论是**条件式**的：写入占空比 < %.6f（等价：重写周期 > %.3e s）则 NVM 胜。"
            % (p_write_over_p_static, t_write_s, d_star, interval_star)),
        "disclosed": "绝对写入能耗无锚 ⇒ 只用**假设比值**，不引用绝对焦耳数",
    }


def cross_backend_comparison(mat: str = DEFAULT_MATERIAL,
                             bits: Optional[float] = None) -> Dict[str, Any]:
    """与 **U4 微环权重库** / **U7 损耗口径** 的同源对照（防跨模块口径漂移）。

    🔴 本函数**跨模块取数**（局部导入）⇒ 上游常量一旦漂移，本模块的对照结论会失真；
    smoke 用固定值断言把该漂移**变成红灯**。
    """
    from lda_l2.loss_aware_compile import ALPHA_PROP_DEFAULT   # 局部导入
    from lda_l2.ring_weight_bank import gap_knob_bits

    lb = level_budget(mat, bits=bits)
    gb = gap_knob_bits(alpha_bend_dBcm=None)
    a_ceiling = gb["weight_ceiling_a"]
    u4_att_dr = -10.0 * math.log10(a_ceiling)
    u8_att_dr = lb["dynamic_range_db"]
    arm_cm = ARM_REF_UM / 1e4
    thermal_arm_prop_loss = ALPHA_PROP_DEFAULT * arm_cm
    pcm_full_swing_il = il_db(C_MAX, mat)
    return {
        "u4_gap_bits_range": gb["bits_range"],
        "u4_gap_bits_point": gb["bits_point"],
        "u4_point_overestimates_x": gb["point_overestimates_x"],
        "u8_bits_db": lb["bits_db"],
        "bits_ratio_u8_over_u4": lb["bits_db"] / gb["bits_range"],
        "u4_weight_ceiling_a": a_ceiling,
        "u4_att_dynamic_range_db": u4_att_dr,
        "u8_att_dynamic_range_db": u8_att_dr,
        "att_dr_ratio_u8_over_u4": u8_att_dr / u4_att_dr,
        "alpha_prop_db_cm": ALPHA_PROP_DEFAULT,
        "arm_ref_um": ARM_REF_UM,
        "thermal_arm_prop_loss_db": thermal_arm_prop_loss,
        "pcm_full_swing_il_db": pcm_full_swing_il,
        "pcm_il_over_thermal_arm_loss": pcm_full_swing_il / thermal_arm_prop_loss,
        "note": (
            "① 位深：PCM 文献 %.1f bit **低于** U4 微环档位极差 %.4f bit ⇒ "
            "PCM 的优势在**功耗**不在分辨率。② 幅度域动态范围：PCM %.4f dB 比 U4 %.4f dB "
            "大 %.2f×，但**二者都是相位/非负标量元件**，都不能做宽带衰减器。"
            "③ 🔴 热光臂传播损耗 %.4f dB 与 PCM 全 2π 文献损耗 %.4f dB **恰好相等**——"
            "这是**圆整数字的巧合**（`2.0 dB/cm × 0.1cm` 与 `2 × 0.1 dB/π` 都等于 0.2），"
            "**不构成物理等价**，仅作刻度体检，**不可当设计收益引用**。"
            % (lb["bits_used"], gb["bits_range"], u8_att_dr, u4_att_dr,
               u8_att_dr / u4_att_dr, thermal_arm_prop_loss, pcm_full_swing_il)),
    }


# ---------------------------------------------------------------------------
# 8. 总报告
# ---------------------------------------------------------------------------
def nonvolatile_backend_report(mat: str = DEFAULT_MATERIAL,
                               bits: Optional[float] = None,
                               horizon_years: float = 20.0,
                               writes_per_day: float = 1.0,
                               n_mzi: int = WDM_N_MZI_REF,
                               n_out: int = WDM_N_OUT_REF,
                               n_sweep: int = 2001) -> Dict[str, Any]:
    """U8 条件式设计**总报告**（红线守卫在必经路径上运行）。

    🔴 `guard_no_foundry_process_truth` + `guard_all_anchors_are_not_measured`
    在函数入口运行 ⇒ 「红线是机器化的」不是文字承诺。
    """
    guard_all_anchors_are_not_measured()
    payload: Dict[str, Any] = {
        "mat": mat,
        "anchor": dict(_anchor(mat)),
        "programming_window": programming_window(mat),
        "level_budget": level_budget(mat, bits=bits, n_sweep=n_sweep),
        "retention": retention_budget(mat, horizon_years),
        "endurance": endurance_budget(mat, writes_per_day),
        "endurance_break_even": (
            endurance_break_even_writes_per_day(mat, 10.0)
            if LITERATURE_ANCHORS[mat].get("endurance_cycles") is not None else None),
        "static_power": static_power_saving(n_mzi, n_out, mat=mat),
        "power_baseline": power_baseline_consistency(),
        "write_break_even": write_power_break_even(),
        "cross_backend": cross_backend_comparison(mat, bits=bits),
        "guard_declaration": {_FOUNDRY_TRUTH_FLAG: False,
                              "anchors_measured_by_this_project": False},
        "disclosure": dict(NVM_DISCLOSURE),
        # 🔴 散文（含「foundry」等词）单独放，**不进**守卫扫描对象 —— 守卫只扫键名。
        "prose": {
            "redline": "不碰 foundry 工艺真值（无 NDA / 无 TCAD 真值 / 无准入）。",
            "capability": "不做能力宣称：本报告是设计接口 + 参数化预算。",
        },
    }
    # 🔴 红线守卫在必经路径上：扫**除 prose / disclosure 外的结构化载荷**。
    guard_no_foundry_process_truth(
        {k: v for k, v in payload.items() if k not in ("prose", "disclosure")},
        where="nonvolatile_backend_report")
    return payload


if __name__ == "__main__":       # pragma: no cover - 人工自测入口
    import json

    print("== U8 非易失权重后端（PCM / Sb₂Se₃）· 条件式设计 ==")
    print("锚:", sorted(LITERATURE_ANCHORS))
    for m in MATERIALS:
        a = LITERATURE_ANCHORS[m]
        print("  %-18s provenance=%-11s measured=%s bits=%s il/π=%s crossbar≤%s"
              % (m, a["provenance"], a["is_measured_by_this_project"],
                 a["levels_bits"], a["il_db_per_pi"], a["crossbar_limit"]))

    print("\n-- 可编程窗口（Sb₂Se₃）--")
    win = programming_window()
    print("  c∈%s φ∈[0,%.6f] IL∈[0,%.4f]dB 幅度∈[%.6f,1] ⇒ 幅度动态范围 %.4f dB"
          % (win["c_range"], win["phi_range_rad"][1], win["il_range_db"][1],
             win["amplitude_range"][0], win["attenuation_dynamic_range_db"]))

    print("\n-- 位深预算 --")
    lb = level_budget()
    print("  来源=%s 位深=%.1f 电平=%.0f Δc=%.10f Δφ=%.10f rad ΔIL=%.10f dB"
          % (lb["bits_source"], lb["bits_used"], lb["levels"], lb["dc"],
             lb["phi_step_rad"], lb["il_step_db"]))
    print("  dB 域位深=%.10f（模型恒等）· T 域 单点=%.6f 档位极差=%.6f ⇒ 高估 %.6f×"
          % (lb["bits_db"], lb["t_domain"]["bits_t_point"],
             lb["t_domain"]["bits_t_range"], lb["t_domain"]["point_overestimates_x"]))

    print("\n-- retention / endurance --")
    for h in (5.0, 10.0, 20.0):
        rb = retention_budget(horizon_years=h)
        print("  retention %5.1f yr ⇒ meets=%s" % (h, rb["meets_horizon"]))
    eb = endurance_budget(writes_per_day=1.0)
    print("  1 次/天 × 10yr ⇒ 需 %.0f 次 · 锚 %.2e · 余量 %.1f× · meets=%s"
          % (eb["writes_total_required"], eb["endurance_cycles_anchor"],
             eb["margin_x"], eb["meets_endurance"]))
    be = endurance_break_even_writes_per_day()
    print("  盈亏平衡写入频次 = %.1f 次/天（10yr 地平线）" % be["writes_per_day_star"])

    print("\n-- 静态功耗 --")
    pb = power_baseline_consistency()
    print("  B29 %.4f mW/mm vs P2 %.2f mW/mm ⇒ 相差 %.2f× · 同量级=%s"
          % (pb["b29_anchor_mw_per_mm"], pb["p2_assumption_mw_per_mm"],
             pb["ratio_p2_over_b29"], pb["within_one_order_of_magnitude"]))
    sp = static_power_saving()
    print("  N=16 网格（%d MZI + %d 输出）⇒ 热调静态 %.3f mW · PCM 静态 0 · 省 %.0f%%"
          % (sp["n_mzi"], sp["n_out"], sp["thermal_static_power_mw"],
             100.0 * sp["saving_ratio"]))
    wb = write_power_break_even()
    print("  break-even 占空比 d*=%.6f（重写周期 > %.3e s 则 NVM 胜）"
          % (wb["duty_star"], wb["reprogram_interval_star_s"]))

    print("\n-- 跨后端对照（U4 / U7）--")
    cb = cross_backend_comparison()
    print("  位深: U8 %.4f vs U4 %.4f ⇒ 比 %.4f" % (cb["u8_bits_db"],
                                                  cb["u4_gap_bits_range"],
                                                  cb["bits_ratio_u8_over_u4"]))
    print("  幅度动态范围: U8 %.4f dB vs U4 %.4f dB ⇒ 比 %.4f"
          % (cb["u8_att_dynamic_range_db"], cb["u4_att_dynamic_range_db"],
             cb["att_dr_ratio_u8_over_u4"]))
    print("  热光臂传播损耗 %.4f dB vs PCM 全摆幅文献损耗 %.4f dB ⇒ 比 %.4f"
          % (cb["thermal_arm_prop_loss_db"], cb["pcm_full_swing_il_db"],
             cb["pcm_il_over_thermal_arm_loss"]))

    print("\n-- 设计接口（与 mesh_drive_manifest 同形）--")
    dm = nvm_drive_manifest([0.0, 0.5, 1.0, 3.0 * math.pi / 2.0], n_mzi=2)
    print("  n_phase=%d n_mzi=%d n_out=%d bits=%.0f max_err=%.6f rad (%.4f°)"
          % (dm["n_phase_total"], dm["n_mzi"], dm["n_out"], dm["bits"],
             dm["max_err_rad"], dm["max_err_deg"]))
    for e in dm["mzi"] + dm["out"]:
        print("    φ=%8.5f → lvl %3d/%d c=%.8f φq=%8.5f err=%.6f IL=%.6f dB [%s]"
              % (e["phi_rad"], e["level_index"], e["n_levels"], e["c_required"],
                 e["phi_quant_rad"], e["err_rad"], e["il_db"], e["role"]))

    print("\n-- 权重库（与 U4 同形；幅度域极窄 ⇒ 多数不可达）--")
    bk = weight_bank_from_weights([1.0, 0.99, 0.97, 0.5])
    print("  可达 %d/%d" % (bk["n_channels"] - bk["n_unreachable"], bk["n_channels"]))
    for e in bk["entries"]:
        print("    w=%.4f ⇒ 可达=%s c=%s lvl=%s IL=%s"
              % (e["w_target"], e["reachable"],
                 ("%.8f" % e["c_required"]) if e["c_required"] is not None else "—",
                 e["level_index"], e["il_db"]))
    print(" ", bk["honest_note"])

    print("\n-- 红线守卫自证 --")
    for name, fn in (("畸形载荷（含 foundry 键）",
                      lambda: guard_no_foundry_process_truth({"foundry_corner": 1})),
                     ("空载荷（合法必过）",
                      lambda: guard_no_foundry_process_truth({})),
                     ("散文值含 foundry（**不**应触发）",
                      lambda: guard_no_foundry_process_truth({"note": "不碰 foundry"}))):
        try:
            fn()
            print("  %-32s ⇒ 通过" % name)
        except NonvolatileRedlineError as exc:
            print("  %-32s ⇒ raise %s" % (name, type(exc).__name__))

    print("\n-- GST：无数字 ⇒ 拒绝数值预算 --")
    try:
        level_budget("GST")
        print("  level_budget(GST) ⇒ 竟然没 raise（异常！）")
    except NonvolatileBackendError as exc:
        print("  level_budget(GST) ⇒ raise：%s" % str(exc)[:90])
    print("  GST 可用信息只有定性约束 crossbar_limit=%s"
          % LITERATURE_ANCHORS["GST"]["crossbar_limit"])

    print("\n披露键（%d）: %s" % (len(NVM_DISCLOSURE), sorted(NVM_DISCLOSURE)))
    print(json.dumps(nonvolatile_backend_report()["level_budget"],
                     ensure_ascii=False, indent=1)[:400])
