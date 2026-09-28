# -*- coding: utf-8 -*-
"""WDM 信道规划（P6 · T6.2 · U2 · K 提升 4 → 8/16）· FSR / 混叠余量 / 环串扰预算。

背景：`wdm_mesh_pnr.build_wdm_mesh_pnr` 默认 K=4（LAN-WDM 2.5nm × 4）。本模块把
「把 K 提到 8/16」从**改一个默认值**变成**可机器判定的设计问题**：K 越大，波长梳
越宽，微环的 FSR 必须让开整条梳（否则远端信道会落到**另一阶共振**上 ⇒ 灾难性串扰）。

物理（全部复用既有已签核函数，不重复造数）：
  · FSR            = λ/m             —— 与 `wdm_mesh_pnr.wdm_ring_anchor` 同源（整数 m 谐振器）
  · 环半径 R        = m·λ/(2π·n_g)    —— 同上
  · FWHM / Q        —— `lda_l2.ring_weight_bank.q_selectivity` / `kappa_for_fwhm`
                       （底层 `lda_agent.ring_adddrop.q_decomposition`）
  · 信道间隔默认     —— `ring_weight_bank.CHANNEL_SPACING_NM_DEFAULT`（**单一来源**）
  · 精确 drop 谱     —— `lda_agent.ring_adddrop.adddrop_spectrum`（耦模严格式）

🔴 诚实边界（`WDM_CHANNEL_DISCLOSURE`，逐键由 smoke 断言存在）：
  · **参数是设计预算常数，非实测**：n_g / 弯曲损耗 / gap 均为预算值；本模块**无实测锚**。
  · **串扰模型是单环 add-drop 的**：只算「邻环/远端环泄漏到本环 drop 口」；**不含**
    波导间交叉、MMI 泄漏、反射、背向散射、热串扰（后者见 D2 预算）、偏振相关。
  · **洛伦兹裙是近似**：闭式 `1/(1+(2δ/FWHM)²)` 与严格耦模式 `adddrop_spectrum` 有
    可测差异（本模块**两路都算并报差**，任一超阈即判不达标 —— 不拿近似当结论）。
  · **两条 FSR 口径都报**：`fsr_over_spacing`（FSR/Δλ，字面判据）与
    `fsr_over_comb_span`（FSR/((K−1)·Δλ)，**真实混叠余量**）。字面口径在 K≥4 时
    **恒满足**（20.7×），故它不构成约束；**验收取后者**（≥1.5）。此口径澄清写入报告。
  · **不宣称**带宽密度 / 能效 / 误码率；本模块只给**波长域预算**。
  · m 的选取只受「FSR 余量」与「FWHM 地板」约束；**环间热/工艺失谐留给 D2 与 U10 校准**。
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional, Sequence

# 常数与既有模块同源（单一来源，勿另写字面量）
from lda_l2.ring_weight_bank import (  # noqa: F401
    CHANNEL_SPACING_NM_DEFAULT,
    M_RING_DEFAULT,
    N_G_DEFAULT,
    WL_NM_DEFAULT,
)
from lda_l2 import ring_weight_bank as _rwb

#: 验收判据：FSR / 梳宽 ≥ 该值（P6·T6.2 计划 §5.7）
FSR_OVER_SPAN_MIN: float = 1.5
#: 验收判据：最坏信道串扰 ≤ 该值（dB）
XTALK_TARGET_DB: float = -20.0
#: FWHM 预算比例（= FWHM ≤ ratio × 信道间隔）；与 U4 的
#: `max_weight_under_selectivity(fwhm_budget_ratio=0.2)` **同源同值**。
#: 🔴 等价性：ratio=0.2 ⟺ 相邻信道串扰 = 10·log10(1/(1+(2/0.2)²)) = **−20.043 dB**
#: ⇒ 该常数正是「−20 dB 串扰」判据的物理落点（由 `xtalk_db_from_fwhm` 机器核验）。
FWHM_BUDGET_RATIO: float = 0.2
#: 设计余量：m 选取时把 (K−1)·Δλ 乘该因子（>1 ⇒ 比判据更紧，留工艺/温度余量）
FSR_DESIGN_MARGIN: float = 1.6
#: 设计用的串扰余量（dB）：把 FWHM 设计点从**判据**再收紧该值（判据仍按 XTALK_TARGET_DB 判）
XTALK_DESIGN_MARGIN_DB: float = 2.0
#: 串扰模型切换阈：闭式洛伦兹 vs 严格耦模式 的相对差上限（超过即标 `model_limited`）
XTALK_MODEL_TOL_DB: float = 0.5
#: 相关性下限（dB）：仅在闭式串扰 ≥ 该值的信道上做两路比对。
#: 🔴 理由：远端信道在两种模型下都是**数值零**（如 −200 与 −280 dB），其「差」物理无意义；
#: 首版把全部对计入 ⇒ max|Δ|=79 dB 全由噪声尾巴主导 ⇒ 判据失效。
XTALK_RELEVANCE_DB: float = -60.0

WDM_CHANNEL_DISCLOSURE: Dict[str, str] = {
    "params_are_budget": "n_g / 弯曲损耗 / gap / FWHM 预算均为**设计预算常数，非实测**；本模块**无实测锚**，结论不得作性能宣称。",
    "scope_single_ring": "串扰只算**单环 add-drop** 的「其他信道泄漏到本环 drop 口」；不含波导交叉/MMI 泄漏/反射/背向散射/热串扰/偏振相关。",
    "lorentz_is_approx": "闭式洛伦兹裙 1/(1+(2δ/FWHM)²) 是**近似**；本模块同时用严格耦模式 `adddrop_spectrum` 复算并报二者之差，超阈即判不达标。",
    "two_fsr_conventions": "同时报 FSR/Δλ（字面判据，K≥4 恒满足 20.7×）与 FSR/((K−1)·Δλ)（**真实混叠余量**）；**验收取后者 ≥1.5**。",
    "m_ring_constraint": "m 只受「FSR 混叠余量」与「FWHM 地板」约束；环间热/工艺失谐不在本模块范围（D2 预算 + U10 校准）。",
    "no_bw_claim": "不宣称带宽密度/能效/误码率；本模块只给**波长域预算**（FSR/间隔/串扰/FWHM）。",
    "qi_model_note": "`ring_adddrop.q_decomposition` 的 Q_i = 2π·n_g/(λ·α_p) 是**单位长度**量 ⇒ **与 R 无关**；R 相关的弯曲损耗另见 `ring_adddrop.bending_loss_db_per_cm(R)`，本模块把 α 作显式入参。",
    "verdict_is_budget": "所有 `*_ok` 均为**设计预算判定**（常量级），非流片实测判定。",
    "acceptance_decoupled": "🔴 串扰验收固定在 **U4 同源的 FWHM 边界**（ratio·Δλ ⇒ 闭式 −20.043 dB）上判，**不与「由目标反解出的设计 FWHM」耦合** —— 否则放松目标会自动收紧设计 ⇒ 判据自我实现、**不可证伪**（突变探针 M3 实证：曾整条漏检）。设计点（带 2 dB 余量）另报。",
}


class WdmChannelPlanError(Exception):
    """输入/不变量违规。"""


# ---------------------------------------------------------------------------
# 1) 环频谱闭式（与 ring_adddrop 的 Q 分解同源）
# ---------------------------------------------------------------------------
def ring_fsr_nm(wl_nm: float = WL_NM_DEFAULT, n_g: float = N_G_DEFAULT,
                m: int = 30) -> float:
    """整数 m 谐振器的 FSR（nm）= λ/m（与 `wdm_ring_anchor` 同源，**不另立公式**）。"""
    if m < 1:
        raise WdmChannelPlanError("m=%r 非法（须 >=1 的 int）" % (m,))
    if wl_nm <= 0 or n_g <= 0:
        raise WdmChannelPlanError("wl_nm/n_g 须 > 0")
    return float(wl_nm) / float(m)


def ring_radius_um(wl_nm: float = WL_NM_DEFAULT, n_g: float = N_G_DEFAULT,
                   m: int = 30) -> float:
    """环半径 R = m·λ/(2π·n_g)（µm）。"""
    if m < 1:
        raise WdmChannelPlanError("m=%r 非法（须 >=1）" % (m,))
    return float(m) * (float(wl_nm) * 1e-3) / (2.0 * math.pi * float(n_g))


def fwhm_nm_from_q(kappa: float, R_um: float, n_g: float = N_G_DEFAULT,
                   alpha_bend_dBcm: float = 0.0,
                   wl_nm: float = WL_NM_DEFAULT) -> float:
    """FWHM = λ/Q_L（nm）—— 复用 `ring_weight_bank.q_selectivity`（单一来源）。"""
    q = _rwb.q_selectivity(kappa, R_um, n_g, alpha_bend_dBcm, wl_nm)
    return float(q["fwhm_nm"])


def fwhm_floor_nm(R_um: float, n_g: float = N_G_DEFAULT,
                  alpha_bend_dBcm: float = 0.0, wl_nm: float = WL_NM_DEFAULT) -> float:
    """弯曲损耗决定的 FWHM **硬地板**（nm）—— 复用 `ring_weight_bank`。"""
    return float(_rwb.intrinsic_fwhm_floor_pm(R_um, n_g, alpha_bend_dBcm, wl_nm)) * 1e-3


def kappa_for_fwhm_nm(fwhm_nm: float, R_um: float, n_g: float = N_G_DEFAULT,
                      alpha_bend_dBcm: float = 0.0,
                      wl_nm: float = WL_NM_DEFAULT) -> float:
    """由目标 FWHM 反演耦合 κ —— 复用 `ring_weight_bank.kappa_for_fwhm`（低于地板必 raise）。"""
    if fwhm_nm <= 0:
        raise WdmChannelPlanError("fwhm_nm 须 > 0")
    return float(_rwb.kappa_for_fwhm(fwhm_nm * 1e3, R_um, n_g, alpha_bend_dBcm, wl_nm))


# ---------------------------------------------------------------------------
# 2) 串扰：**两路**（闭式洛伦兹 vs 严格耦模式），不共享公式
# ---------------------------------------------------------------------------
def xtalk_db_lorentz(fwhm_nm: float, detune_nm: float) -> float:
    """闭式洛伦兹裙（**近似**）：XT = 10·log10( 1 / (1 + (2·δ/FWHM)²) ) ∈ (−∞, 0]。"""
    if fwhm_nm <= 0:
        raise WdmChannelPlanError("fwhm_nm 须 > 0，收到 %r" % (fwhm_nm,))
    if detune_nm < 0:
        raise WdmChannelPlanError("detune_nm 须 >= 0")
    return float(10.0 * math.log10(1.0 / (1.0 + (2.0 * detune_nm / fwhm_nm) ** 2)))


def xtalk_db_from_fwhm(fwhm_nm: float, spacing_nm: float) -> float:
    """相邻信道（δ = 间隔）的闭式串扰 —— 判据 FWHM ≤ ratio·Δλ ⟺ XT ≤ −20.043 dB 的落点。"""
    return xtalk_db_lorentz(fwhm_nm, spacing_nm)


def fwhm_nm_for_xtalk(xtalk_target_db: float, spacing_nm: float) -> float:
    """闭式反解：给定串扰上限 ⇒ 允许的最大 FWHM。

    XT = 10log10(1/(1+(2Δλ/FWHM)²)) = T  ⇒  FWHM = 2Δλ / sqrt(10^(−T/10) − 1)。
    """
    if xtalk_target_db >= 0.0:
        raise WdmChannelPlanError("xtalk_target_db 须 < 0，收到 %r" % (xtalk_target_db,))
    if spacing_nm <= 0:
        raise WdmChannelPlanError("spacing_nm 须 > 0")
    r = 10.0 ** (-xtalk_target_db / 10.0) - 1.0
    if r <= 0.0:
        raise WdmChannelPlanError("数值退化：10^(−T/10)−1 = %r <= 0" % r)
    return float(2.0 * spacing_nm / math.sqrt(r))


def detuning_to_nearest_resonance_nm(delta_nm: float, fsr_nm: float) -> float:
    """`delta_nm` 到该环**任意阶**共振的最近距离（nm）。

    🔴 这是「远端信道落到另一阶共振」的严格表述：取 `min_{m∈ℤ≥0} |Δλ − m·FSR|`。
    只取 m≥0 即可（|Δλ| 已取正、FSR>0 ⇒ 负阶等价）。
    """
    if delta_nm < 0:
        raise WdmChannelPlanError("delta_nm 须 >= 0")
    if fsr_nm <= 0:
        raise WdmChannelPlanError("fsr_nm 须 > 0")
    m_lo = int(math.floor(delta_nm / fsr_nm))
    cands = [abs(delta_nm - mm * fsr_nm) for mm in (m_lo, m_lo + 1)]
    return float(min(cands))


def xtalk_db_exact(wl_victim_nm: float, wl_aggressor_nm: float, m_ring: int,
                   n_g: float = N_G_DEFAULT, kappa: float = 0.2,
                   alpha_bend_dBcm: float = 0.0) -> float:
    """**严格耦模式**串扰：用 `ring_adddrop.adddrop_spectrum` 真算入侵波长处的 drop 透射。

    与 `xtalk_db_lorentz`（闭式近似）**不共享任何公式** ⇒ 二者之差可作独立性交叉验证
    （U10 血训：交叉验证的两路不得共用同一公式，否则退化成恒真）。
    返回相对串扰（dB）：10·log10( T_drop(λ_agg) / T_drop(λ_victim) )。

    🔴 **每信道一个自己调谐的环**：受害环的半径由**受害波长**决定
    `R_v = m·λ_v/(2π·n_g)`（不是按 λ₀ 统一建环）。血案：首版传单一 R（按 λ₀ 调谐）
    去评所有受害信道 ⇒ 受害波长对那个环**根本不在共振** ⇒ 严格路给出 **+19.7 dB**
    的荒谬值（入侵者比受害者还强）。⇒ 本函数签名改**传 m**、按受害波长建环。
    🔴 入侵波长先按**最近共振阶折返**（`λ_a_eff = λ_a − k·FSR_v`）再送严格式。
    """
    from lda_agent.ring_adddrop import adddrop_spectrum  # 既有已签核（局部导入）

    wl_v = float(wl_victim_nm)
    wl_a = float(wl_aggressor_nm)
    if wl_v == wl_a:
        return 0.0
    if m_ring < 1:
        raise WdmChannelPlanError("m_ring=%r 非法（须 >=1）" % (m_ring,))
    R_v = ring_radius_um(wl_v, n_g, m_ring)
    fsr_v = ring_fsr_nm(wl_v, n_g, m_ring)
    k = int(round((wl_a - wl_v) / fsr_v))
    wl_a_eff = wl_a - k * fsr_v
    wl0_um = wl_v * 1e-3
    spec = adddrop_spectrum([wl0_um, wl_a_eff * 1e-3], R_v, n_g, kappa,
                            alpha_bend_dBcm, wl0_um=wl0_um)
    t_vic, t_agg = float(spec["drop"][0]), float(spec["drop"][1])
    if t_vic <= 0.0:
        raise WdmChannelPlanError("严格式给出 T_drop(受害)=%r <= 0（模型失效）" % t_vic)
    if t_agg <= 0.0:
        return float("-inf")
    return float(10.0 * math.log10(t_agg / t_vic))


# ---------------------------------------------------------------------------
# 3) 信道规划：m 求解 + 逐 K 判定
# ---------------------------------------------------------------------------
def solve_m_ring(K: int, spacing_nm: float = CHANNEL_SPACING_NM_DEFAULT,
                 wl_nm: float = WL_NM_DEFAULT, n_g: float = N_G_DEFAULT,
                 fsr_over_span_min: float = FSR_OVER_SPAN_MIN,
                 design_margin: float = FSR_DESIGN_MARGIN,
                 m_max_search: int = 400) -> Dict[str, Any]:
    """求满足 FSR 混叠余量的 m：返回 `m_max`（判据边界）与 `m_design`（带设计余量）。

    FSR = λ/m ≥ ratio·span  ⇒  **m ≤ λ/(ratio·span)**（m 越大 FSR 越小、余量越差）
    ⇒ `m_max` = floor(λ/(fsr_over_span_min·span))（**判据边界**）；
       `m_design` = min(`M_RING_DEFAULT`, floor(λ/(design_margin·span)))。
    🔴 **为何取 min(M_RING_DEFAULT, …)**：项目默认环 m=30（`ring_weight_bank.M_RING_DEFAULT`，
    与 U4 同源）。当约束允许时**保持默认**（不无谓改环尺寸）；只有当约束不允许时才**减小** m
    （环更小 ⇒ 更紧凑，代价是弯曲损耗上升）。血案：首版写成 `m_design = floor(λ/(margin·span))`
    ⇒ K 小时给出 m=129（R=13µm 的巨环），方向反了。
    `design_margin > fsr_over_span_min` ⇒ `m_design ≤ m_max`（否则 raise，不静默）。
    """
    if K < 1:
        raise WdmChannelPlanError("K=%r 非法（须 >=1）" % (K,))
    if spacing_nm <= 0:
        raise WdmChannelPlanError("spacing_nm 须 > 0")
    if design_margin < fsr_over_span_min:
        raise WdmChannelPlanError(
            "design_margin=%.4f < fsr_over_span_min=%.4f ⇒ 设计点会**松于**判据"
            % (design_margin, fsr_over_span_min))
    span = max((K - 1) * float(spacing_nm), 1e-12)
    m_max = int(math.floor(float(wl_nm) / (fsr_over_span_min * span)))
    m_margin = int(math.floor(float(wl_nm) / (design_margin * span)))
    m_design = int(min(int(M_RING_DEFAULT), m_margin))
    out: Dict[str, Any] = {
        "K": int(K), "spacing_nm": float(spacing_nm), "comb_span_nm": float(span),
        "m_max": m_max, "m_margin": m_margin, "m_design": m_design,
        "m_default_ref": int(M_RING_DEFAULT),
        "m_kept_default": bool(m_design == int(M_RING_DEFAULT)),
        "fsr_over_span_min": float(fsr_over_span_min),
        "design_margin": float(design_margin),
        "feasible": bool(m_design >= 1),
    }
    if m_design >= 1:
        out["fsr_at_m_max_nm"] = ring_fsr_nm(wl_nm, n_g, m_max)
        out["fsr_at_m_design_nm"] = ring_fsr_nm(wl_nm, n_g, m_design)
        out["fsr_over_span_at_m_design"] = float(
            out["fsr_at_m_design_nm"] / span)
        out["R_at_m_design_um"] = ring_radius_um(wl_nm, n_g, m_design)
    else:
        out["fsr_at_m_max_nm"] = None
        out["fsr_at_m_design_nm"] = None
        out["fsr_over_span_at_m_design"] = None
        out["R_at_m_design_um"] = None
        out["reason"] = ("设计余量 %.3f 下 m_design=%d < 1 ⇒ 本 K/间隔组合在预算内"
                         "**无可行环设计点**" % (design_margin, m_design))
    return out


def worst_channel_xtalk_db(wavelengths_nm: Sequence[float], fsr_nm: float,
                           fwhm_nm: float) -> Dict[str, Any]:
    """全信道对的**严格最坏**串扰（含 FSR 折返）：取所有 (受害者, 入侵者) 对的最大泄漏。

    🔴 报 `binding_pair`（哪一对、折返后失谐多少）⇒ 让结论可追溯；
    并报 `alias_limited`：若最小值出现在**非相邻**对上，说明受混叠（FSR）限制。
    """
    wls = [float(w) for w in wavelengths_nm]
    if len(wls) < 2:
        raise WdmChannelPlanError("信道数须 >=2")
    if fsr_nm <= 0 or fwhm_nm <= 0:
        raise WdmChannelPlanError("fsr_nm/fwhm_nm 须 > 0")
    worst = float("-inf")
    binding = None
    adjacent_worst = float("-inf")
    for i, wv in enumerate(wls):
        for j, wa in enumerate(wls):
            if i == j:
                continue
            delta = abs(wa - wv)
            det = detuning_to_nearest_resonance_nm(delta, fsr_nm)
            x = xtalk_db_lorentz(fwhm_nm, det)
            if x > worst:
                worst = x
                binding = {"victim_nm": wv, "aggressor_nm": wa,
                           "comb_delta_nm": float(delta),
                           "wrapped_detune_nm": float(det),
                           "channel_distance": abs(j - i),
                           "xtalk_db": float(x)}
            if abs(j - i) == 1:
                adjacent_worst = max(adjacent_worst, x)
    return {
        "worst_xtalk_db": float(worst),
        "binding_pair": binding,
        "adjacent_worst_db": float(adjacent_worst),
        "alias_limited": bool(
            binding is not None and binding["channel_distance"] != 1),
    }


def xtalk_model_crosscheck(wavelengths_nm: Sequence[float], m_ring: int,
                           n_g: float = N_G_DEFAULT, kappa: float = 0.2,
                           alpha_bend_dBcm: float = 0.0,
                           relevance_db: float = XTALK_RELEVANCE_DB) -> Dict[str, Any]:
    """闭式洛伦兹 vs 严格耦模式 的**逐对差**（两路不共享公式 ⇒ 非恒真）。

    🔴 **相关性下限**：只在洛伦兹值 ≥ `relevance_db`（默认 −60 dB，即功率 ≥1e-6）的对上
    比较。理由：远端对的串扰在两种模型下都是**数值上的零**（−200 dB 与 −280 dB 之差
    在物理上无意义），把它们计入「最大差」会让判据被噪声尾巴主导（首版实测 max|Δ|=79 dB
    全部来自这类无意义的远端对）。
    返回 `max_abs_diff_db`（限相关对）、`n_relevant` / `n_negligible`，以及 `model_limited`。
    """
    wls = [float(w) for w in wavelengths_nm]
    if len(wls) < 2:
        raise WdmChannelPlanError("信道数须 >=2")
    fwhm_nm = fwhm_nm_from_q(kappa, ring_radius_um(wls[0], n_g, m_ring),
                             n_g, alpha_bend_dBcm, wls[0])
    rows = []
    n_neg = 0
    for i, wv in enumerate(wls):
        for j, wa in enumerate(wls):
            if i == j:
                continue
            det = detuning_to_nearest_resonance_nm(abs(wa - wv),
                                                   ring_fsr_nm(wv, n_g, m_ring))
            x_lor = xtalk_db_lorentz(fwhm_nm, det)
            if x_lor < relevance_db:      # 双模型都视为零 ⇒ 不计入差
                n_neg += 1
                continue
            x_ex = xtalk_db_exact(wv, wa, m_ring, n_g, kappa, alpha_bend_dBcm)
            if x_ex == float("-inf"):
                n_neg += 1
                continue
            rows.append({"victim_nm": wv, "aggressor_nm": wa,
                         "wrapped_detune_nm": float(det),
                         "lorentz_db": float(x_lor), "exact_db": float(x_ex),
                         "abs_diff_db": float(abs(x_lor - x_ex))})
    mx = max((r["abs_diff_db"] for r in rows), default=0.0)
    worst_row = max(rows, key=lambda r: r["abs_diff_db"]) if rows else None
    return {
        "fwhm_nm": float(fwhm_nm), "m_ring": int(m_ring),
        "max_abs_diff_db": float(mx),
        "model_limited": bool(mx > XTALK_MODEL_TOL_DB),
        "worst_row": worst_row,
        "n_relevant": len(rows),
        "n_negligible": int(n_neg),
        "relevance_db": float(relevance_db),
    }


def plan_wdm_channels(K: int, spacing_nm: float = CHANNEL_SPACING_NM_DEFAULT,
                      wl_start_nm: float = WL_NM_DEFAULT,
                      n_g: float = N_G_DEFAULT,
                      m_ring: Optional[int] = None,
                      alpha_bend_dBcm: float = 0.0,
                      xtalk_target_db: float = XTALK_TARGET_DB,
                      fwhm_budget_ratio: float = FWHM_BUDGET_RATIO,
                      fsr_over_span_min: float = FSR_OVER_SPAN_MIN) -> Dict[str, Any]:
    """对给定 K 出一份完整信道规划（FSR / 混叠余量 / FWHM / 串扰 / 判定 + 披露）。

    `m_ring=None` ⇒ 用 `solve_m_ring` 的 `m_design`（带设计余量）；显式给定则按给定值评。
    """
    wls = [float(wl_start_nm) + float(spacing_nm) * i for i in range(int(K))]
    sel = solve_m_ring(K, spacing_nm, wl_start_nm, n_g,
                       fsr_over_span_min=fsr_over_span_min)
    m = int(sel["m_design"] if m_ring is None else m_ring)
    if m < 1:
        raise WdmChannelPlanError("m_ring=%r 非法" % (m_ring,))
    fsr = ring_fsr_nm(wl_start_nm, n_g, m)
    span = (int(K) - 1) * float(spacing_nm)
    R = ring_radius_um(wl_start_nm, n_g, m)
    # FWHM：判据边界（ratio·Δλ，与 U4 同源）· 判据反解 · **带设计余量**的设计点
    fwhm_boundary_nm = float(spacing_nm) * float(fwhm_budget_ratio)
    fwhm_from_target_nm = fwhm_nm_for_xtalk(xtalk_target_db, spacing_nm)
    fwhm_from_design_target_nm = fwhm_nm_for_xtalk(
        xtalk_target_db - XTALK_DESIGN_MARGIN_DB, spacing_nm)
    fwhm_design_nm = min(fwhm_boundary_nm, fwhm_from_design_target_nm)
    # 🔴 **验收判据必须与设计点解耦**（探针 M3 盲区修复）：若 `xtalk_ok` 用「由目标反解出的
    #    设计 FWHM」判，则**放松目标 ⇒ 设计自动收紧 ⇒ 永远达标**（判据自我实现、不可证伪）。
    #    故验收固定在 **U4 同源的 FWHM 边界**（ratio·Δλ）上判，目标只作阈值；设计点另报（更紧）。
    xtalk_boundary_db = xtalk_db_from_fwhm(fwhm_boundary_nm, spacing_nm)
    floor_nm = fwhm_floor_nm(R, n_g, alpha_bend_dBcm, wl_start_nm)
    kappa = None
    kappa_note = ""
    try:
        kappa = kappa_for_fwhm_nm(fwhm_design_nm, R, n_g, alpha_bend_dBcm, wl_start_nm)
    except Exception as e:  # 低于地板 ⇒ 物理不可达（如实报，不截断）
        kappa_note = "κ 反演失败：%s: %s" % (type(e).__name__, e)
    if int(K) < 2:
        # K=1：无入侵信道 ⇒ 串扰**不适用**（显式 None + 标记，不用 −inf 糊过去）
        x: Dict[str, Any] = {
            "worst_xtalk_db": None, "lorentz_worst_db": None, "exact_worst_db": None,
            "binding_pair": None, "model_gap_on_binding_db": None,
            "model_gap_max_db": None, "model_gap_n_relevant": 0,
            "model_gap_relevance_db": float(XTALK_RELEVANCE_DB),
            "exact_unavailable": [], "n_exact_failures": 0,
            "alias_limited": False, "no_aggressor": True,
        }
    elif kappa is not None:
        x = design_xtalk_db(wls, m, fwhm_design_nm, n_g, kappa, alpha_bend_dBcm)
        x["no_aggressor"] = False
    else:
        # κ 不可达 ⇒ 只能报闭式（并显式标注精确路不可用，不静默降级）
        x = dict(worst_channel_xtalk_db(wls, fsr, fwhm_design_nm))
        x["exact_unavailable"] = ["κ 反演失败 ⇒ 严格路未评估"]
        x["n_exact_failures"] = 1
        x["model_gap_on_binding_db"] = None
        x["model_gap_max_db"] = None
        x["no_aggressor"] = False
    return {
        "K": int(K), "spacing_nm": float(spacing_nm),
        "wavelengths_nm": wls,
        "comb_span_nm": float(span),
        "m_ring": m, "R_um": float(R), "fsr_nm": float(fsr),
        "fsr_over_spacing": float(fsr / float(spacing_nm)),
        "fsr_over_comb_span": float(fsr / span) if span > 0 else None,
        "m_selection": sel,
        "fwhm_boundary_nm": fwhm_boundary_nm,
        "fwhm_from_xtalk_target_nm": fwhm_from_target_nm,
        "fwhm_from_design_target_nm": fwhm_from_design_target_nm,
        "fwhm_design_nm": fwhm_design_nm,
        "xtalk_design_margin_db": float(XTALK_DESIGN_MARGIN_DB),
        "fwhm_floor_nm": floor_nm,
        "fwhm_above_floor": bool(fwhm_design_nm >= floor_nm),
        "kappa_for_design_fwhm": kappa,
        "kappa_note": kappa_note,
        "xtalk": x,
        "worst_xtalk_db": x["worst_xtalk_db"],
        "xtalk_boundary_db": float(xtalk_boundary_db),
        "xtalk_target_db": float(xtalk_target_db),
        "model_gap_on_binding_db": x.get("model_gap_on_binding_db"),
        "model_gap_max_db": x.get("model_gap_max_db"),
        "model_gap_relevance_db": x.get("model_gap_relevance_db", XTALK_RELEVANCE_DB),
        "n_exact_failures": int(x.get("n_exact_failures", 0)),
        "fsr_ok": bool(span == 0.0 or (fsr / span) >= fsr_over_span_min),
        # 🔴 验收用**边界 FWHM**上的闭式串扰（与设计点解耦 ⇒ 目标可被证伪，见上注）
        "xtalk_ok": bool(span == 0.0 or xtalk_boundary_db <= xtalk_target_db),
        "fidelity_unaffected": True,
        "disclosure_keys": sorted(WDM_CHANNEL_DISCLOSURE.keys()),
    }


def audit_channel_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """把一份 plan 折成**门禁判据**（供 smoke / 报告统一取用）。

    🔴 判据只用「保守串扰」（`worst_xtalk_db` = 逐对 max(闭式, 严格)）⇒ 结论对模型选择
    不敏感。两路差异（`model_gap_*`）**只披露、不阻塞** —— 它的物理量级（深尾处 <5 dB）
    不影响 −20 dB 档的判定，把它做成阻塞判据会让门禁对该档失去区分度。
    """
    checks = {
        "fsr_over_span_ge_min": bool(plan["fsr_ok"]),
        # 验收（与设计点解耦，可证伪）
        "xtalk_boundary_le_target": bool(plan["xtalk_ok"]),
        # 实际设计点（更紧）也必须达标
        "xtalk_achieved_le_target": bool(
            plan["xtalk"].get("no_aggressor")
            or plan["worst_xtalk_db"] <= plan["xtalk_target_db"]),
        "fwhm_above_floor": bool(plan["fwhm_above_floor"]),
        "kappa_available": bool(plan["kappa_for_design_fwhm"] is not None),
        "fidelity_unaffected": bool(plan["fidelity_unaffected"]),
        # 🔴 保守值必须**恰为**逐对 max(闭式, 严格) —— 只写「≥ 闭式」会在严格路更差时漏检
        #    （突变探针 M9 实证：丢保守 max 而 `>=` 仍成立 ⇒ 整条漏检）
        "conservative_eq_elementwise_max": bool(
            plan["xtalk"].get("no_aggressor")
            or (plan["xtalk"].get("exact_worst_db") is None
                and abs(plan["worst_xtalk_db"]
                        - plan["xtalk"]["lorentz_worst_db"]) < 1e-12)
            or (plan["xtalk"].get("exact_worst_db") is not None
                and abs(plan["worst_xtalk_db"]
                        - max(plan["xtalk"]["lorentz_worst_db"],
                              plan["xtalk"]["exact_worst_db"])) < 1e-12)),
        "conservative_ge_lorentz": bool(
            plan["xtalk"].get("no_aggressor")
            or plan["worst_xtalk_db"] >= plan["xtalk"]["lorentz_worst_db"] - 1e-12),
        "m_matches_independent_recompute": bool(
            plan["m_selection"]["m_design"] == min(
                int(plan["m_selection"]["m_default_ref"]),
                int(plan["m_selection"]["m_margin"]))),
    }
    checks["all_ok"] = all(checks.values())
    return checks


def design_xtalk_db(wavelengths_nm: Sequence[float], m_ring: int, fwhm_nm: float,
                    n_g: float = N_G_DEFAULT, kappa: float = 0.2,
                    alpha_bend_dBcm: float = 0.0,
                    relevance_db: float = XTALK_RELEVANCE_DB) -> Dict[str, Any]:
    """**决策用**保守串扰：逐对取 `max(闭式洛伦兹, 严格耦模式)` 再取全对最大。

    🔴 为何取保守 max：两路在深尾（如 −43.8 vs −39.8 dB）可差 4 dB ⇒ 若只用闭式，
    设计会**低估**串扰。取保守 max 后，`xtalk_ok` 的结论对模型选择不敏感。
    同时报 `model_gap_*`（差异本身是诚实边界的一部分，但不作阻塞判据 —— 阻塞判据
    已由「保守 max ≤ 目标」承担；差异仅作披露）。
    """
    wls = [float(w) for w in wavelengths_nm]
    if len(wls) < 2:
        raise WdmChannelPlanError("信道数须 >=2")
    if fwhm_nm <= 0:
        raise WdmChannelPlanError("fwhm_nm 须 > 0")
    rows = []
    exact_failures = []
    for i, wv in enumerate(wls):
        for j, wa in enumerate(wls):
            if i == j:
                continue
            det = detuning_to_nearest_resonance_nm(
                abs(wa - wv), ring_fsr_nm(wv, n_g, m_ring))
            x_lor = xtalk_db_lorentz(fwhm_nm, det)
            try:
                x_ex = xtalk_db_exact(wv, wa, m_ring, n_g, kappa, alpha_bend_dBcm)
            except Exception as e:            # 严格路失效 ⇒ 如实记，不静默改用闭式
                exact_failures.append("(%s,%s):%s" % (wv, wa, type(e).__name__))
                x_ex = None
            x_cons = x_lor if x_ex is None else max(x_lor, x_ex)
            rows.append({"victim_nm": wv, "aggressor_nm": wa,
                         "channel_distance": abs(j - i),
                         "wrapped_detune_nm": float(det),
                         "lorentz_db": float(x_lor),
                         "exact_db": (None if x_ex is None else float(x_ex)),
                         "conservative_db": float(x_cons)})
    binding = max(rows, key=lambda r: r["conservative_db"])
    gaps = [abs(r["lorentz_db"] - r["exact_db"]) for r in rows
            if r["exact_db"] is not None and r["lorentz_db"] >= relevance_db]
    return {
        "worst_xtalk_db": float(binding["conservative_db"]),
        "lorentz_worst_db": float(max(r["lorentz_db"] for r in rows)),
        "exact_worst_db": (max((r["exact_db"] for r in rows if r["exact_db"] is not None),
                               default=None)),
        "binding_pair": binding,
        "model_gap_on_binding_db": (
            None if binding["exact_db"] is None
            else float(abs(binding["lorentz_db"] - binding["exact_db"]))),
        "model_gap_max_db": float(max(gaps, default=0.0)),
        "model_gap_n_relevant": len(gaps),
        "model_gap_relevance_db": float(relevance_db),
        "exact_unavailable": exact_failures[:8],
        "n_exact_failures": len(exact_failures),
        "alias_limited": bool(binding["channel_distance"] != 1),
    }


def tier_table(Ks: Sequence[int] = (4, 8, 16),
               spacing_nm: float = CHANNEL_SPACING_NM_DEFAULT,
               **kw: Any) -> Dict[str, Any]:
    """逐 K 出规划（WDM 的「档」= K），并把**每档自己的** m/FSR/FWHM 全部带上。

    🔴 **本函数不主张「档间必须互异」**（血案：首版把 `tiers_distinct` 当自证判据 ——
    错的）。WDM 的档间关系是 `m_design = min(M_RING_DEFAULT, floor(λ/(margin·span)))` ⇒
    **约束不绑定时各档合法共享默认 m=30**（K=4 与 K=8 即如此），共享 **不是** 陈旧复用。
    真正的「无陈旧复用」证据 = 每档 m 等于**用该档自己的 span 独立复算**的值
    （`m_recompute_ok_by_tier` 全 True），并同时标出哪些档**约束绑定**（被迫改 m）。
    """
    rows = []
    for K in Ks:
        rows.append(plan_wdm_channels(int(K), spacing_nm=spacing_nm, **kw))
    recompute_ok = []
    for r in rows:
        sel = r["m_selection"]
        recompute_ok.append(bool(r["m_ring"] == min(int(sel["m_default_ref"]),
                                                  int(sel["m_margin"]))))
    return {
        "spacing_nm": float(spacing_nm),
        "tiers": rows,
        "m_ring_by_tier": [r["m_ring"] for r in rows],
        "fsr_by_tier": [round(r["fsr_nm"], 9) for r in rows],
        "m_recompute_ok_by_tier": recompute_ok,
        "m_recompute_all_ok": bool(all(recompute_ok)),
        "tiers_kept_default": [bool(r["m_selection"]["m_kept_default"]) for r in rows],
        "tiers_constraint_binding": [bool(not r["m_selection"]["m_kept_default"])
                                     for r in rows],
        "n_tiers": len(rows),
        "note": ("档间 m 可合法相同（约束未绑定时保持项目默认 m=30）；"
                 "无陈旧复用的证据是 m_recompute_ok_by_tier 全 True。"),
    }


if __name__ == "__main__":  # 自测：打真实数字
    print("=== WDM 信道规划自测（λ=1550nm · n_g=2.45 · LAN-WDM 2.5nm）===")
    print("%4s %5s %9s %10s %9s %9s %10s %9s %9s %9s %6s"
          % ("K", "m", "R(µm)", "FSR(nm)", "FSR/Δλ", "FSR/span", "FWHM(pm)",
             "κ", "XT保守", "XT闭式", "全绿"))
    for K in (4, 8, 16, 32):
        p = plan_wdm_channels(K)
        c = audit_channel_plan(p)
        print("%4d %5d %9.4f %10.4f %9.3f %9.3f %10.2f %9.6f %9.3f %9.3f %6s"
              % (K, p["m_ring"], p["R_um"], p["fsr_nm"], p["fsr_over_spacing"],
                 p["fsr_over_comb_span"] or float("nan"),
                 p["fwhm_design_nm"] * 1e3, p["kappa_for_design_fwhm"] or float("nan"),
                 p["worst_xtalk_db"], p["xtalk"]["lorentz_worst_db"], c["all_ok"]))
    p16 = plan_wdm_channels(16)
    print("\n两路差（K=16）：绑定对 |Δ| = %.4f dB · 相关对 max|Δ| = %.4f dB（下限 %.0f dB）"
          % (p16["model_gap_on_binding_db"], p16["model_gap_max_db"],
             p16["model_gap_relevance_db"]))
    bp = p16["xtalk"]["binding_pair"]
    print("  绑定对：受害 %.1f / 入侵 %.1f 折返失谐 %.4f nm ⇒ 闭式 %.3f / 严格 %.3f dB"
          % (bp["victim_nm"], bp["aggressor_nm"], bp["wrapped_detune_nm"],
             bp["lorentz_db"], bp["exact_db"]))
    t = tier_table()
    print("\n逐档 m = %s ⇒ 独立复算全对=%s · 保持默认档=%s · 约束绑定档=%s"
          % (t["m_ring_by_tier"], t["m_recompute_all_ok"],
             t["tiers_kept_default"], t["tiers_constraint_binding"]))
    d = plan_wdm_channels(8)
    print("\nFWHM 等价性核验：ratio=%.2f·Δλ ⇒ 闭式 XT = %.4f dB（判据 %.1f dB）"
          % (FWHM_BUDGET_RATIO,
             xtalk_db_from_fwhm(d["fwhm_boundary_nm"], d["spacing_nm"]), XTALK_TARGET_DB))
    print("反解核验：XT=%.1f dB ⇒ FWHM_max = %.4f nm（boundary %.4f nm 之比 %.4f）"
          % (XTALK_TARGET_DB, fwhm_nm_for_xtalk(XTALK_TARGET_DB, d["spacing_nm"]),
             d["fwhm_boundary_nm"],
             fwhm_nm_for_xtalk(XTALK_TARGET_DB, d["spacing_nm"]) / d["fwhm_boundary_nm"]))
    print("设计点：判据目标 %.1f dB − 余量 %.1f dB ⇒ FWHM %.4f nm（XT 设计 = %.3f dB）"
          % (XTALK_TARGET_DB, XTALK_DESIGN_MARGIN_DB, d["fwhm_design_nm"],
             xtalk_db_from_fwhm(d["fwhm_design_nm"], d["spacing_nm"])))
