# -*- coding: utf-8 -*-
"""LDA 光联接模块征程 · **M2b（G-OI5）**：多通道均衡 · 热调 · 热串扰 Γ · 工艺偏差良率 · 封装容差。

M2 = 规模 × 形态 × 物理落地（8×200G PAM4 / LPO 无 DSP / 真 GDS）。**M2b = 把「设计 ⟷ 版图 ⟷ 工艺 ⟷ 封装」
四层真正咬成一条闭环**，而不是再堆一个孤立功能：

    版图坐标 → 热耦合 Θ → Γ 矩阵 → 串扰 → 环路预算
    工艺偏差 σ → 谐振偏移 → 良率（MC ⟷ 闭式 Q 双通道）
    封装对准 + 温度 → GC 耦合效率 → 容差预算（闭式 ⟷ 数值扫描双通道）
    逐 lane 工艺离散 → 逐 lane CTLE → 眼高平坦化（多通道均衡的真落点）

🔴 **本轮题眼（由 M2 口径直接推出，非新增主张）**：M2 已登记「LPO = 模块内**无 DSP**」，而
FFE/DFE 是**数字**、在 DSP 里跑 ⇒ **LPO 形态只能有模拟 CTLE（连续时间线性均衡，位于 TIA 前）**；
`retimed`（有模块 DSP）才可用 CTLE + FFE。这不是免责声明，是**可判红的约束**
（`equalizer_for_form` + 探针 P3，见 `run_oi_m2b_smoke.py`）。

🔴 诚实边界（红线 `docs/lda_active_device_redline_clarification_2026-09-10.md` §四 A 档）：
  · 全部 **A 档闭式 / 行为级**：不碰电-光耦合增益真值（T2 锁）· 不用 A 级商业工具 · 不流片。
  · 🔴 **不报 TOPS / TOPS-W / fJ/op / pJ/bit** ⇒ 热调只登记 **mW/lane 功耗**，**不做**任何
    「比特能效」换算（Pπ 是功耗量，不是能效量）。
  · 工艺偏差 σ / 对准预算 / 温窗是**设计者显式声明的统计规格锚**，**不是 foundry 真值**（T2 锁死区）
    ⇒ `verdict` 恒 `DESIGN_BUDGET`，**不得**宣称「实测工艺能力」或「流片良率」。
  · 器件为 L0/L1 解析 / 行为模型，参数为公开文献典型量级占位（**非 PDK**），**无实测锚**。

与既有模块的关系（🔴 **一律复用，不重抄常量** —— M2 血案 #3「跨档照抄设计常量 ⇒ 同源不同步」）：
  · 奈奎斯特 / 波长栅 / 环区数 m：`oi_m2`（**互锁判据**锁住「常量 ⟷ 派生源」）。
  · 调谐斜率 S = λ·(dn/dT)·R_th/n_eff：`lda_agent.tunable_wdm`（单一真源，直接 import）。
  · 抽头 / 眼 / Q：`oi_m1._channel_taps`（M2b 经 `h_extra` 接入 CTLE，**单一实现**）。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from lda_l2 import oi_m1 as _M1
from lda_l2 import oi_m2 as _M2

# ═════════════════════════════════════════════════════════════════════════════
# 0) 直通 M2 的单一真源（🔴 不重抄 —— 抄了就是血案 #3 重演）
# ═════════════════════════════════════════════════════════════════════════════
NYQUIST_200G_GHZ = _M2.NYQUIST_200G_GHZ          # 53.125 GHz（同源）
PAM4_BAUD_200G_GBD = _M2.PAM4_BAUD_200G_GBD      # 106.25 GBd（同源）
RING_M_2B = _M2.OI_M2_PROCESS["ring_m"]          # 268（互锁：≠ M1 的 129）

# 热材料常数：**import 单一真源**，不写第二份
from lda_agent.tunable_wdm import (  # noqa: E402
    DN_DT_SI as _DN_DT,
    N_EFF_TUNE as _N_EFF_TUNE,
    R_TH_DEFAULT as _R_TH_DEFAULT,
    _tuning_slope_nm_per_mw as _tuning_slope,
)


# ═════════════════════════════════════════════════════════════════════════════
# 1) 规格锚 / 声明窗口（防口径静默写错 —— M1 血案同族：值本身错时原判据全绿）
# ═════════════════════════════════════════════════════════════════════════════
OI_M2B_PROCESS: Dict[str, Any] = {
    "n_lanes": 8,
    "wl0_nm": _M2.OI_M2_PROCESS["wl0_nm"],             # 1311（O-band 主设计点）
    "spacing_nm": _M2.OI_M2_PROCESS["spacing_nm"],     # 4.5（≈800 GHz 栅）
    "ring_m": RING_M_2B,                               # 268（**不是** 129）
    "ring_n_eff": _N_EFF_TUNE,                         # 2.4（SOI 条形波导）
    "ring_n_g": 4.2,           # SOI 群折射率（与 tunable_wdm 的 n_g 用量级一致）
    "f_mod_nom_ghz": _M2.OI_M2_PROCESS["f_mod_ghz"],   # 105（200G 档）
    "f_tia_ghz": _M2.OI_M2_PROCESS["f_tia_ghz"],       # 125
    # 均衡（逐 lane 工艺离散是「多通道均衡」的成因）
    "lane_spread_pct": 0.03,      # 各 lane 调制器带宽 ±3% 工艺离散
    "ctle_boost_db": 6.0,         # 奈奎斯特处目标提升
    # 工艺偏差（🔴 设计者声明窗口 · 非 foundry 真值 · T2 锁死区）
    "sigma_dn_eff": 5.0e-4,       # n_eff 偏差 σ
    "resonance_tol_nm": 1.5,      # |Δλ₀| 判定窗（信道间隔 4.5 nm 的 1/3）
    # 封装 / 对准
    "w_fiber_um": 5.2,            # 单模光纤 1/e² 半径（MFD≈10.4 µm）
    # 🔴 首版缺陷（自检抓出）：把**裸硅条波导**模场 2.2 µm 当成 GC 出口模场 ⇒
    # 模场失配固有损耗 −10log₁₀η_m = **2.88 dB**，直接吃掉 1 dB 对准预算 ⇒ 容差不可达。
    # 真物理：GC 的作用**正是**把波导模场经锥形/衍射扩展到接近光纤 ⇒ 出口等效模场 ≈3.5 µm
    # ⇒ 固有失配底降到 0.66 dB，预算才立得住。
    "w_waveguide_um": 3.5,         # **GC 出口等效** 1/e² 模场半径（占位，非 PDK）
    "gc_l_eff_um": 30.0,           # 角度失配等效长度
    "align_il_budget_db": 1.0,     # 对准 IL 预算
    "alpha_si_per_k": 2.6e-6,      #  Si 热膨胀系数
}

# 锚窗口（取值越界 ⇒ 判 FAIL，不允许静默写错）
_BANDS: Dict[str, Tuple[float, float]] = {
    "nyquist_ghz": (53.0, 53.25),
    "wl0_nm": (1300.0, 1320.0),
    "spacing_nm": (4.0, 5.2),
    "ring_m": (260.0, 276.0),
    "f_mod_ghz": (100.0, 112.0),
    "ctle_boost_db": (3.0, 12.0),
    "sigma_dn_eff": (5.0e-5, 3.0e-3),
    "resonance_tol_nm": (1.0, 2.0),
    "w_fiber_um": (4.0, 7.0),
    "w_waveguide_um": (2.5, 4.5),
    "align_il_budget_db": (0.5, 2.0),
}

# 温区（商用光模块典型工作温区 · 规格锚第 ④ 层）
TEMP_WINDOW_C: Tuple[float, float] = (-5.0, 70.0)


def _in_band(key: str, value: float) -> bool:
    lo, hi = _BANDS[key]
    return lo <= float(value) <= hi


# ═════════════════════════════════════════════════════════════════════════════
# 2) 🔴 形态 → 均衡方案（本轮题眼：LPO 无 DSP ⇒ 只能模拟 CTLE）
# ═════════════════════════════════════════════════════════════════════════════
EQ_PROFILES: Dict[str, Dict[str, Any]] = {
    "lpo": {
        "ctle": True,
        "ffe": False,
        "needs_dsp": False,
        "label": "LPO（模块内无 DSP）⇒ **仅**模拟 CTLE（TIA 前连续时间线性均衡）",
        "note": "FFE/DFE 是数字均衡、在模块 DSP 里跑 ⇒ LPO 拿不到，拿就是自相矛盾。",
    },
    "retimed": {
        "ctle": True,
        "ffe": True,
        "needs_dsp": True,
        "label": "重定时（有模块 DSP）⇒ CTLE + 数字 FFE",
        "note": "级联 FEC 的内码也在这颗 DSP 里（M2 口径）。",
    },
}

_EQ_WHITELIST: Tuple[str, ...] = ("ctle", "ffe", "needs_dsp")


def equalizer_for_form(form: str) -> Dict[str, Any]:
    """形态 → 可用均衡手段。**反向判据的靶子**：让 lpo 拿到 ffe 必红（探针 P3）。"""
    if form not in EQ_PROFILES:
        raise ValueError("未知形态：%r（应为 'lpo' | 'retimed'）" % (form,))
    return dict(EQ_PROFILES[form])


# ═════════════════════════════════════════════════════════════════════════════
# 3) ① 多通道均衡：CTLE 闭式（频响 / boost 反解 / 噪声 penalty）
# ═════════════════════════════════════════════════════════════════════════════
def ctle_mag(f_hz: Any, f_z_hz: float, f_p_hz: float) -> np.ndarray:
    """CTLE 幅度：|H(f)| = [(1+(f/f_z)²)/(1+(f/f_p)²)]^½ （f_p > f_z ⇒ 高频 boost）。"""
    f = np.asarray(f_hz, dtype=float)
    if f_p_hz <= 0.0 or f_z_hz <= 0.0:
        raise ValueError("CTLE 极点/零点必须为正")
    if f_z_hz > f_p_hz:
        raise ValueError("f_z 必须 ≤ f_p（否则不是 boost，而是低通衰减）")
    return np.sqrt((1.0 + (f / f_z_hz) ** 2) / (1.0 + (f / f_p_hz) ** 2))


def ctle_h(f_hz: Any, f_z_hz: float, f_p_hz: float) -> np.ndarray:
    """CTLE **复传输函数** `H(f) = (1 + j·f/f_z)/(1 + j·f/f_p)`（幅度 ≡ `ctl_mag`）。

    抽头注入必须用**复数**（含相位）：零/极点对既有幅度提升也带来相位与群延迟，
    只乘幅度会把 CTLE 当成纯幅度滤波 ⇒ 抽头/ISI/BER 全偏。`|H| ≡ ctle_mag` 由
    自检互锁（两实现同源不同式 ⇒ 不是「同源相等」假判据）。"""
    f = np.asarray(f_hz, dtype=float)
    return (1.0 + 1j * f / float(f_z_hz)) / (1.0 + 1j * f / float(f_p_hz))


def f_z_for_boost(f_nyq_hz: float, f_p_hz: float, boost_db: float) -> float:
    """给定奈奎斯特处目标 boost（dB）⇒ **闭式反解**零点 f_z（CTLE 抽头设计）。

        G(F)² = 10^(boost/10) = (1+F²/c²)/(1+F²/a²)  ⇒  c = F / √(10^(b/10)(1+F²/a²) − 1)
    """
    a, F, g2 = float(f_p_hz), float(f_nyq_hz), 10.0 ** (float(boost_db) / 10.0)
    denom = g2 * (1.0 + (F / a) ** 2) - 1.0
    if denom <= 0.0:
        raise ValueError("目标 boost 不可达（boost 过低 / f_p 过小）")
    return F / math.sqrt(denom)


def ctle_noise_penalty_db(f_z_hz: float, f_p_hz: float, f_nyq_hz: float) -> float:
    """CTLE 噪声 penalty（golden = 解析积分）：

        penalty = 10·log10( ∫₀^F G(f)² df / F )        G = CTLE 幅度（f_p > f_z ⇒ boost）

    即「**相对平坦响应**（G ≡ 1，integral = F ⇒ penalty ≡ 0）的**超额噪声带宽**」——
    均衡抬高频段必然同时抬噪声 ⇒ penalty 必须 **> 0**（首版错在把 `"基准"` 取成 G(F)²，
    得到 −2.86 dB 的**负惩罚**（物理上不可能：平坦 CTLE 才是 0 基准）⇒ 判据
    「0 < penalty < 20」当场红掉；本条已由门禁抓出并修正，见 T8/P1）。

    🔴 退化自检：f_z = f_p（flat）⇒ G≡1 ⇒ penalty ≡ 0 dB（判据必须能落到 0，不是恒绿）。
    """
    c, a, F = float(f_z_hz), float(f_p_hz), float(f_nyq_hz)
    if F <= 0.0:
        raise ValueError("噪声积分上限 F 必须为正（空区间不得当作恒 0 的假绿）")
    integral = (a * a / (c * c)) * (F + (c * c - a * a) * math.atan(F / a) / a)
    return 10.0 * math.log10(integral / F)


def _nbw_numeric(f_z_hz: float, f_p_hz: float, f_nyq_hz: float,
                 n: int = 200001) -> float:
    """CTLE 噪声带宽的**第二独立通道**（trapz 数值积分，与解析原函数对拍）。

    🔴 与 `ctl_noise_penalty_db` **同口径**（都被 /F）：两条通道比的是**积分值本身**
    （同一被积函数、两种求积法），不是「同源码跑两遍」；平坦退化下两者都必须 → F ⇒ 0 dB。
    """
    F = float(f_nyq_hz)
    f = np.linspace(0.0, F, n)
    g2 = (1.0 + (f / f_z_hz) ** 2) / (1.0 + (f / f_p_hz) ** 2)
    integ = float(np.trapezoid(g2, f)) if hasattr(np, "trapezoid") \
        else float(np.trapz(g2, f))
    return integ


def lane_f_mod_ghz(n_lanes: Optional[int] = None,
                   spread_pct: Optional[float] = None) -> np.ndarray:
    """逐 lane 调制器带宽（工艺离散 ±spread）⇒ **多通道均衡的成因**：
    各 lane 倾斜不同，单一 CTLE 无法同时平坦 ⇒ 必须逐 lane 抽头（词条「多通道」的落点）。"""
    p = OI_M2B_PROCESS
    n = int(p["n_lanes"] if n_lanes is None else n_lanes)
    sp = float(p["lane_spread_pct"] if spread_pct is None else spread_pct)
    u = np.linspace(-1.0, 1.0, n)
    return float(p["f_mod_nom_ghz"]) * (1.0 + sp * u)


def _channel_gain_db(f_mod_hz: float, f_pd_hz: float, f_tia_hz: float,
                     f_hz: float) -> float:
    """EO 链（`oi_m1.eo_s21_complex` 单一实现）在指定频率的幅度（dB）。"""
    h = _M1.eo_s21_complex(float(f_hz), float(f_mod_hz), float(f_pd_hz), float(f_tia_hz))
    return 20.0 * math.log10(max(abs(h), 1e-30))


def lane_ctle_design(n_lanes: Optional[int] = None, boost_db: Optional[float] = None,
                     f_nyq_ghz: Optional[float] = None) -> Dict[str, Any]:
    """逐 lane CTLE 抽头设计 —— 「多通道均衡」的真解向量。

    🔴 首版缺陷（自检抓出）：目标 boost 对所有 lane 取同一个 ⇒ 解出的 f_z 逐 lane **完全相同**，
    「多通道均衡」退化成「单通道均衡 ×N」的摆设。真物理是：**各 lane 因工艺离散（f_mod 不同）
    在奈奎斯特处的信道损耗不同** ⇒ 要让均衡后**总增益拉平**，每个 lane 该补的 boost 不同：

        boost_i = boost_nom + (loss_ref − loss_i)      （loss 用 `oi_m1.eo_s21_complex` 实算）

    ⇒ f_z_i 逐 lane 真不同。

    🔴 **v0.9.185 修 F3**：首版把「各 lane 均衡后总增益相等」当成**成效判据**，但它恰是
    `f_z_for_boost` 反解的**往返恒等式**（改物理常量不红 ⇒ 假判据）。现在如实分成两层：
      · `design_roundtrip_flat` —— **设计方程自洽**（往返恒等式，弱）；
      · `lane_equalization_flatness()` —— **信道成效**（独立重算：逐 lane 真信道的 ISI）。
    """
    p = OI_M2B_PROCESS
    F = (NYQUIST_200G_GHZ if f_nyq_ghz is None else float(f_nyq_ghz)) * 1e9
    a = float(p["f_tia_ghz"]) * 1e9                       # 最后一个极点 = TIA
    f_pd = float(_M2.OI_M2_PROCESS["f_pd_ghz"]) * 1e9
    nom = float(p["f_mod_nom_ghz"]) * 1e9
    b_nom = float(p["ctle_boost_db"] if boost_db is None else boost_db)
    loss_ref = _channel_gain_db(nom, f_pd, a, F)
    lanes: List[Dict[str, Any]] = []
    for i, fm in enumerate(lane_f_mod_ghz(n_lanes)):
        fm_hz = float(fm) * 1e9
        loss_i = _channel_gain_db(fm_hz, f_pd, a, F)
        b_i = b_nom + (loss_ref - loss_i)
        z = f_z_for_boost(F, a, b_i)
        boost_achieved = 10.0 * math.log10((1.0 + (F / z) ** 2) / (1.0 + (F / a) ** 2))
        lanes.append({
            "lane": i, "f_mod_ghz": float(fm),
            "channel_loss_db": -loss_i,
            "boost_db": b_i,
            "f_z_hz": z, "f_p_hz": a,
            "noise_penalty_db": ctle_noise_penalty_db(z, a, F),
            "boost_achieved_db": boost_achieved,
            # 均衡后总增益（dB）：信道 + CTLE ⇒ 逐 lane 应相等（平坦化判据的靶子）
            "total_gain_at_nyquist_db": loss_i + boost_achieved,
        })
    tot = [x["total_gain_at_nyquist_db"] for x in lanes]
    np_ = [x["noise_penalty_db"] for x in lanes]
    return {"lanes": lanes, "n_lanes": len(lanes),
            "noise_penalty_min_db": min(np_), "noise_penalty_max_db": max(np_),
            "total_gain_min_db": min(tot), "total_gain_max_db": max(tot),
            "total_gain_spread_db": max(tot) - min(tot),
            # 🔴 **v0.9.185 修 F3（如实标注）**：`total_gain_i ≡ loss_i + boost_achieved_i
            #    ≡ b_nom + loss_ref`，而 `boost_achieved_i` 恰是 `f_z_for_boost` 反解的**逆**
            #    ⇒ 逐 lane 相等是**往返恒等式**（改任何物理常量都不红）。它证明的是
            #    「**设计方程自洽**」，**不是**「信道被真正拉平」。
            #    ⇒ 信道成效改由 `lane_equalization_flatness()`（**独立重算**：逐 lane
            #    真信道的时域抽头 ISI）判定，门禁 T10 / 探针 P11 守护。
            "design_roundtrip_flat": bool(max(tot) - min(tot) < 1e-6),
            "design_roundtrip_note": (
                "total_gain 逐 lane 相等 = f_z_for_boost 反解的往返恒等式（非信道成效）"),
            "boost_distinct": len({round(x["boost_db"], 9) for x in lanes}) == len(lanes),
            "spread_pct": float(p["lane_spread_pct"]),
            "f_nyquist_ghz": NYQUIST_200G_GHZ}


def lane_isi_residual(lanes: Sequence[Dict[str, Dict[str, Any]]],
                      f_mod_hz: Optional[float] = None,
                      f_pd_hz: Optional[float] = None,
                      f_tia_hz: Optional[float] = None,
                      beta2_s2_m: float = 0.0, L_m: float = 0.0,
                      baud_hz: Optional[float] = None,
                      sigma_tx_s: float = 0.0,
                      f_z_perturb_rel: float = 0.0,
                      flat_tol: float = 1e-3) -> Dict[str, Any]:
    """逐 lane 均衡后 **ISI residual**（抽头能量和 = 归一化干扰上界，闭式口径）。

    🔴 复用 `oi_m1._channel_taps` 单一实现，CTLE 经 `h_extra` 接入（上游 M1 已开该接线点）。

    🔴 **v0.9.185 修 F4（多通道退化）**：首版签名 `f_mod_hz: float` 用**单一标称信道**
    跑**全部 lane**，与 `lane["f_mod_ghz"]`（逐 lane 工艺离散 101.85…108.15 GHz）
    **自相矛盾** ⇒ 门禁测的是「8×同一信道 + 8 个不同 CTLE」，**没有**检验「逐 lane
    信道被各自均衡」。现在 `f_mod_hz=None`（默认）⇒ **逐 lane 用自身 `f_mod_ghz`**；
    传标量则退化到旧口径（显式保留以便对照），`channel_source` **如实回报**来源。

    `f_z_perturb_rel` 供门禁探针制造「某 lane 的 CTLE 零点被设计错」的真 bug。
    """
    per_lane_ch = f_mod_hz is None
    out: List[Dict[str, Any]] = []
    for lane in lanes:
        z = float(lane["f_z_hz"]) * (1.0 + float(f_z_perturb_rel))
        p_ = float(lane["f_p_hz"])
        fm = float(lane["f_mod_ghz"]) * 1e9 if per_lane_ch else float(f_mod_hz)
        # 🔴 CTLE 在 `oi_m1._channel_taps` **自己的频栅**上求值（callable 契约），
        #    频栅分辨率 df = baud/(n_taps+8)：取 n_taps=512 ⇒ df≈0.2 GHz（奈奎斯特处
        #    约 260 点），足以解析 f_z/f_p 形态；窗口 = 520 符号 ≈ 4.9 ns。
        taps = _M1._channel_taps(f_mod_hz=fm, f_pd_hz=f_pd_hz, f_tia_hz=f_tia_hz,
                                 beta2_s2_m=beta2_s2_m, L_m=L_m, baud_hz=baud_hz,
                                 sigma_tx_s=sigma_tx_s, n_taps=512, os=64,
                                 h_extra=lambda fq: ctle_h(fq, z, p_))
        res = float(np.sum(np.abs(taps[1:]) ** 2))
        out.append({"lane": lane["lane"], "taps": taps.tolist(),
                    "f_mod_ghz_used": (float(lane["f_mod_ghz"]) if per_lane_ch
                                       else float(f_mod_hz) / 1e9),
                    "isi_residual": res, "cursor": float(taps[0])})
    residuals = [x["isi_residual"] for x in out]
    spread = max(residuals) - min(residuals)
    return {"per_lane": out, "n_lanes": len(out),
            "channel_source": ("per_lane(f_mod_ghz)" if per_lane_ch
                               else "scalar(f_mod_hz)"),
            "isi_min": min(residuals), "isi_max": max(residuals),
            "isi_spread": spread,
            "isi_flat_ok": bool(spread <= flat_tol)}


def lane_equalization_flatness(n_lanes: Optional[int] = None,
                               boost_db: Optional[float] = None,
                               f_nyq_ghz: Optional[float] = None,
                               f_z_perturb_rel: float = 0.0) -> Dict[str, Any]:
    """多通道均衡**成效**（🔴 **独立重算**，v0.9.185 修 F3）。

    🔴 **为何需要它**：`lane_ctle_design` 的 `total_gain_*` 是 `f_z_for_boost` 反解的
    **往返恒等式**（改物理常量不红）⇒ 它只证明「设计方程自洽」，**不证明**「信道被真正
    拉平」。本函数走 `lane_isi_residual`（**时域抽头**，逐 lane **真信道**）⇒ 若某 lane
    的 f_z 被设计错，其 residual 会真变 ⇒ **能变红**（门禁 P11 靶子）。

    `f_z_perturb_rel` 供探针制造「某 lane CTLE 零点打偏」的真 bug（透传给逐 lane 循环）。
    """
    des = lane_ctle_design(n_lanes, boost_db, f_nyq_ghz)
    f_pd = float(_M2.OI_M2_PROCESS["f_pd_ghz"]) * 1e9
    f_tia = float(OI_M2B_PROCESS["f_tia_ghz"]) * 1e9
    baud = PAM4_BAUD_200G_GBD * 1e9
    iso = lane_isi_residual(des["lanes"], None, f_pd, f_tia, 0.0, 0.0, baud,
                            f_z_perturb_rel=f_z_perturb_rel)
    return {"design": des, "flatness": iso,
            "equalization_flat_ok": bool(iso["isi_flat_ok"]),
            "isi_spread": float(iso["isi_spread"]),
            "channel_source": iso["channel_source"]}


# ═════════════════════════════════════════════════════════════════════════════
# 4) ② 热调：Pπ / 调谐斜率进链路（🔴 只登记功耗，不动能效）
# ═════════════════════════════════════════════════════════════════════════════
def ring_radius_um() -> float:
    """环半径（复用 M2 规划解，单一真源）：R = m·λ/(2π·n_g)。"""
    plan = _M2.plan_m2_rings()
    r = plan.get("ring_R_um") or (plan.get("best") or {}).get("R_um")
    if r is None:
        for k in ("R_um", "ring_R_um", "best_R_um"):
            if plan.get(k) is not None:
                r = plan[k]
                break
    return float(r)


def tuning_slope_nm_per_mw(wl_nm: Optional[float] = None) -> float:
    """调谐斜率 S = λ·(dn/dT)·R_th/n_eff（nm/mW）—— **单一真源 = tunable_wdm**。"""
    wl = float(OI_M2B_PROCESS["wl0_nm"] if wl_nm is None else wl_nm)
    return float(_tuning_slope(wl, _DN_DT, _R_TH_DEFAULT, _N_EFF_TUNE))


def p_pi_mw(heater_frac: float = 0.25) -> Dict[str, Any]:
    """热光 **Pπ（mW）**：`power_for_pi` 单一真源；加热器长度由**环周长派生**（不写死）。"""
    from lda_design.active_models import power_for_pi  # noqa: E402（单一真源 import）
    r_um = ring_radius_um()
    l_heater = heater_frac * 2.0 * math.pi * r_um
    wl_um = float(OI_M2B_PROCESS["wl0_nm"]) / 1000.0
    return {"p_pi_mw": float(power_for_pi(l_heater, wl_um)),
            "heater_length_um": float(l_heater), "ring_R_um": r_um,
            "heater_frac": float(heater_frac),
            "S_nm_per_mW": tuning_slope_nm_per_mw()}


def thermal_tune_budget(n_lanes: Optional[int] = None,
                        residual_detune_nm: Optional[float] = None,
                        heater_frac: float = 0.25) -> Dict[str, Any]:
    """热调预算：环需从初始失谐调谐到信道 ⇒ **调谐功耗 mW/lane**。

        P_tune = Pπ · |Δλ_residual| / FSR        （线性区，A 档行为级）

    🔴 口径纪律：输出**只有功耗（mW）**，**没有** fJ/bit / pJ/bit / 能效比（红线禁出）。
    """
    p = OI_M2B_PROCESS
    n = int(p["n_lanes"] if n_lanes is None else n_lanes)
    pp = p_pi_mw(heater_frac)
    ppi = float(pp["p_pi_mw"])
    fsr = _ring_fsr_nm()
    det = float(p["spacing_nm"] / 3.0 if residual_detune_nm is None else residual_detune_nm)
    p_tune = ppi * abs(det) / fsr
    return {"p_pi_mw": ppi, "heater_length_um": pp["heater_length_um"],
            "ring_R_um": pp["ring_R_um"], "S_nm_per_mW": pp["S_nm_per_mW"],
            "FSR_nm": fsr, "residual_detune_nm": det,
            "p_tune_mw_per_lane": p_tune, "p_tune_total_mw": p_tune * n,
            "n_lanes": n,
            "unit_note": "mW（功耗口径）· 不换算能效比"}


def _ring_fsr_nm() -> float:
    """环 FSR（nm）—— **单一真源** = `lda_agent.wdm_system.fsr_nm`。

    🔴 F7（v0.9.185）：首版 import 失败时 `return OI_M2B_PROCESS["spacing_nm"]`（= **4.5 nm**），
    而真值 **4.891789 nm** ⇒ 静默偏 8.0%，`P_tune` 与「∝Δλ」判据**照绿**。**回退已删**
    （失败即 raise），并加 `no_fsr_fallback_ok()` 把「用的不是回退常量」变成机器可查。
    """
    from lda_agent.wdm_system import fsr_nm          # noqa: E402（单一真源 · 回退已删）
    return float(fsr_nm(float(OI_M2B_PROCESS["wl0_nm"]), ring_radius_um(),
                        OI_M2B_PROCESS["ring_n_g"]))


def no_fsr_fallback_ok() -> bool:
    """🔴 F7（v0.9.185）：`_ring_fsr_nm()` 必须**不等于** `spacing_nm` 回退常量。

    真值 4.891789 ≠ 回退 4.5 ⇒ 若回退分支复活（被静默触发），本判据必红（探针 P12 靶子）。
    """
    return abs(_ring_fsr_nm() - float(OI_M2B_PROCESS["spacing_nm"])) > 0.1


# ═════════════════════════════════════════════════════════════════════════════
# 5) ③ 热串扰 Γ 矩阵（🔴 版图绑定：坐标来自 G-OI2 builder 的 placement）
# ═════════════════════════════════════════════════════════════════════════════
_R_TH0_K_PER_MW = 1.0        # 归一化热阻尺度（对数场口径；与 R_th 分离以便版图绑定）
_D_REF_UM = 400.0            # 热场参考距离（超过它耦合视为 0）


def ring_positions_from_layout(n_lanes: Optional[int] = None) -> List[Tuple[float, float]]:
    """从 **G-OI2 真版图**提取 Rx 环坐标（Γ 矩阵的版图绑定源）。

    🔴 绝不写死坐标：版图一变，Γ 必须跟着变（判据：Γ 随版图坐标真变化）。
    """
    from lda_layout import oi_transceiver_pnr as _PNR  # noqa: E402
    b = _PNR.build_oi_transceiver_pnr(n_lanes=int(
        OI_M2B_PROCESS["n_lanes"] if n_lanes is None else n_lanes))
    pl = b["placement"]
    n = int(OI_M2B_PROCESS["n_lanes"] if n_lanes is None else n_lanes)
    pos: List[Tuple[float, float]] = []
    for i in range(n):
        t = pl.get("ring%d" % i)
        if t is None:
            raise KeyError("版图 placement 缺 ring%d（G-OI2 builder 接口变了）" % i)
        pos.append((float(t[0]), float(t[1])))
    return pos


def thermal_coupling_log(d_um: float, d_ref_um: float = _D_REF_UM,
                         r_th0: float = _R_TH0_K_PER_MW) -> float:
    """二维薄片稳态热场的**对数解**（golden）：Θ = r_th0·ln(d_ref/d)。

    物理：2D 稳态点热源温升 ∝ ln(R/r)（Carslaw–Jaeger 薄片解），d→d_ref ⇒ 0。
    🔴 退化自检：d = d_ref ⇒ Θ = 0；d < d_ref ⇒ Θ > 0。
    """
    d = max(float(d_um), 1e-6)
    dref = float(d_ref_um)
    if d >= dref:
        return 0.0
    return float(r_th0) * math.log(dref / d)


def thermal_network_coupling(pos_um: Sequence[Tuple[float, float]],
                             grid: int = 24, extent_um: float = 520.0,
                             r_th0: float = _R_TH0_K_PER_MW) -> np.ndarray:
    """热耦合矩阵 Θ 的**第二独立通道**：有限差分热网络（拉普拉斯 G·T = P）。

    规则网格 + 四邻热导 ⇒ 解 T = G⁺P ⇒ Θ_ij = T_i / P_j。与对数解析解是**两条独立
    方法**（离散网络 ⟷ 解析场），差别在离散化偏差 ⇒ 判据取「**随网格加密单调收敛**」
    （真物理判据，不是同源码相等）。

    🔴 首版两处建模错误（门禁 T18 抓出）：
      1. **热导写成 `g = r_th0/step`** ⇒ 有效热导 k_eff = g·step = r_th0 与步长无关？
         不对：离散方程 `4T_i − ΣT_nb = P/k` 中 `g ≡ k`，于是 `g` 必须**一步长无关**地
         等于二维热导 `k = 1/(2π·r_th0)`；用 `r_th0/step` 会让**解出的连续问题随网格改变**
         ⇒ 相对误差恒 0.503（12/24/48 完全不降，假收敛）。
      2. **坐标系错配**：版图坐标（本版 Rx 环在 `y = −260`）与网络域 `[0, extent]²`
         不同框 ⇒ 最近节点落在**接地边界**上，注入功率被接地吃掉 ⇒ 整个网络解 ≈ 0。
         ⇒ 域必须以**版图质心**为中心，与版图同坐标系。
    """
    n = len(pos_um)
    if n == 0:
        return np.zeros((0, 0))
    k_eff = 1.0 / (2.0 * math.pi * float(r_th0))   # 二维热导（与对数场自洽）
    _cx = float(np.mean([float(q[0]) for q in pos_um]))
    _cy = float(np.mean([float(q[1]) for q in pos_um]))
    x0, y0 = _cx - extent_um / 2.0, _cy - extent_um / 2.0
    step = extent_um / max(grid - 1, 1)
    idx_of: Dict[Tuple[int, int], int] = {}
    for gx_ in range(grid):
        for gy_ in range(grid):
            idx_of[(gx_, gy_)] = len(idx_of)
    N = grid * grid
    G = np.zeros((N, N))
    for gx_ in range(grid):
        for gy_ in range(grid):
            i = idx_of[(gx_, gy_)]
            for dx_, dy_ in ((1, 0), (0, 1)):
                nx_, ny_ = gx_ + dx_, gy_ + dy_
                if nx_ < grid and ny_ < grid:
                    j = idx_of[(nx_, ny_)]
                    g = k_eff                       # 🔴 一步长无关（见 docstring）
                    G[i, j] -= g
                    G[j, i] -= g
                    G[i, i] += g
                    G[j, j] += g
    # 边界接地（恒温参考）
    for gx_ in range(grid):
        for gy_ in range(grid):
            if gx_ in (0, grid - 1) or gy_ in (0, grid - 1):
                G[idx_of[(gx_, gy_)], :] = 0.0
                G[:, idx_of[(gx_, gy_)]] = 0.0
                G[idx_of[(gx_, gy_)], idx_of[(gx_, gy_)]] = 1.0
    inv = np.linalg.pinv(G)
    # 节点坐标
    nodes = np.array([[x0 + gx_ * step, y0 + gy_ * step] for gx_ in range(grid)
                      for gy_ in range(grid)], dtype=float)
    nearest = [int(np.argmin(np.hypot(nodes[:, 0] - px, nodes[:, 1] - py)))
               for (px, py) in pos_um]
    theta = np.zeros((n, n))
    for j in range(n):                      # j 注入单位功率
        p = np.zeros(N)
        p[nearest[j]] = 1.0
        t = inv @ p
        for i in range(n):
            theta[i, j] = t[nearest[i]]
    return theta


def crosstalk_gamma(pos_um: Optional[Sequence[Tuple[float, float]]] = None,
                    r_th0: float = _R_TH0_K_PER_MW,
                    d_ref_um: float = _D_REF_UM) -> Dict[str, Any]:
    """热串扰 **Γ 矩阵**（nm/mW）：Γ_ij = S_i · Θ_ij，Θ 由**版图坐标**对数解析解给。

    三条**闭式物理律**判据（golden，非同源码相等）：
      1. 对称性 Γ_ij = Γ_ji（热传导互易，非对称布局下仍须成立）
      2. 单调性 Γ_ij 随版图距离严格递减（≥3 组距离对）
      3. 对角最大 Γ_ii ≥ Γ_ij (i≠j)（自身加热最强）
    """
    if pos_um is None:
        pos_um = ring_positions_from_layout()
    pos = [(float(a), float(b)) for (a, b) in pos_um]
    n = len(pos)
    S = tuning_slope_nm_per_mw()
    d = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            dist = math.hypot(pos[i][0] - pos[j][0], pos[i][1] - pos[j][1])
            d[i, j] = dist
    theta = np.array([[thermal_coupling_log(d[i, j], d_ref_um, r_th0) for j in range(n)]
                      for i in range(n)])
    gamma = theta * S
    sym = bool(np.allclose(gamma, gamma.T, atol=1e-12, rtol=1e-9))
    diag_max = bool(np.all(np.diag(gamma) >= gamma - 1e-12))
    mono_pairs = [(i, j) for i in range(n) for j in range(n) if i != j]
    mono = all(d[i, a] < d[i, b] <= d_ref_um + 1e-9
               and theta[i, a] > theta[i, b]
               for i in range(n) for (a, b) in mono_pairs if d[i, a] < d[i, b])
    return {"positions_um": pos, "n": n, "dist_um": d.tolist(),
            "theta_k_per_mw": theta.tolist(), "gamma_nm_per_mw": gamma.tolist(),
            "S_nm_per_mW": S,
            "symmetric_ok": sym, "diagonal_max_ok": diag_max, "monotonic_ok": mono,
            "max_offdiag_nm_per_mW": float(np.max(gamma - np.diag(np.diag(gamma))))
            if n > 1 else 0.0}


# ═════════════════════════════════════════════════════════════════════════════
# 6) ④ 工艺偏差 → 良率（MC ⟷ 闭式 Φ 双通道；🔴 MC 不是 golden）
# ═════════════════════════════════════════════════════════════════════════════
def resonance_shift_nm(dn_eff: Any) -> np.ndarray:
    """环谐振偏移闭式：λ = 2π·n_eff·R/m ⇒ dλ = λ·δn_eff/n_eff。"""
    p = OI_M2B_PROCESS
    neff = float(p["ring_n_eff"])
    wl = float(p["wl0_nm"])
    return np.asarray(dn_eff, dtype=float) * wl / neff


def yield_closed_form(sigma_dn_eff: Optional[float] = None,
                      tol_nm: Optional[float] = None) -> Dict[str, Any]:
    """良率**闭式（golden）**：Δλ ~ N(0, σ_λ) ⇒

        yield = P(|Δλ| < tol) = erf( tol / (σ_λ·√2) )
    """
    p = OI_M2B_PROCESS
    s_dn = float(p["sigma_dn_eff"] if sigma_dn_eff is None else sigma_dn_eff)
    tol = float(p["resonance_tol_nm"] if tol_nm is None else tol_nm)
    sigma_nm = float(np.mean(np.abs(resonance_shift_nm(s_dn)))) if s_dn != 0.0 else 0.0
    if s_dn == 0.0:
        y = 1.0 if tol > 0.0 else 0.0
    else:
        y = math.erf(tol / (sigma_nm * math.sqrt(2.0)))
    return {"sigma_dn_eff": s_dn, "sigma_resonance_nm": sigma_nm,
            "tol_nm": tol, "yield": y, "golden": "closed-form erf"}


def yield_monte_carlo(n_samples: int = 20000, seed: int = 20261002,
                      sigma_dn_eff: Optional[float] = None,
                      tol_nm: Optional[float] = None) -> Dict[str, Any]:
    """良率 **MC 第二通道**（固定 seed ⇒ 可复现）。

    🔴 纪律：MC 是采样近似，**不是 golden**；golden 是 `yield_closed_form` 的闭式 erf。
    """
    p = OI_M2B_PROCESS
    s_dn = float(p["sigma_dn_eff"] if sigma_dn_eff is None else sigma_dn_eff)
    tol = float(p["resonance_tol_nm"] if tol_nm is None else tol_nm)
    rng = np.random.default_rng(seed)
    dn = rng.normal(0.0, s_dn, int(n_samples))
    dl = resonance_shift_nm(dn)
    frac = float(np.mean(np.abs(dl) < tol))
    return {"n_samples": int(n_samples), "seed": int(seed),
            "sigma_dn_eff": s_dn, "tol_nm": tol, "yield": frac,
            "sigma_resonance_nm": float(np.std(dl)),
            "channel": "monte_carlo"}


# ═════════════════════════════════════════════════════════════════════════════
# 7) ⑤ 封装容差：GC 对准（横向/角度/模场失配）+ 温度漂移
# ═════════════════════════════════════════════════════════════════════════════
def gc_coupling_efficiency(dx_um: float = 0.0, theta_rad: float = 0.0,
                           dz_um: float = 0.0,
                           w1_um: Optional[float] = None,
                           w2_um: Optional[float] = None,
                           l_eff_um: Optional[float] = None) -> Dict[str, Any]:
    """光栅耦合器耦合效率（高斯 1/e² 模场口径，**全部闭式**）：

        η_dx = exp(−2·dx²/(w₁²+w₂²))        横向失配
        η_θ  = exp(−2·(θ·L_eff)²/(w₁²+w₂²)) 角度失配（等效横向）
        η_m  = (2·w₁·w₂/(w₁²+w₂²))²         模场失配（与 dx 无关的**常数底**）
        η    = η_dx·η_m·η_θ·η_dz
    """
    p = OI_M2B_PROCESS
    w1 = float(p["w_fiber_um"] if w1_um is None else w1_um)
    w2 = float(p["w_waveguide_um"] if w2_um is None else w2_um)
    l_eff = float(p["gc_l_eff_um"] if l_eff_um is None else l_eff_um)
    sm = w1 * w1 + w2 * w2
    eta_dx = math.exp(-2.0 * dx_um * dx_um / sm)
    eta_th = math.exp(-2.0 * (theta_rad * l_eff) ** 2 / sm)
    eta_m = (2.0 * w1 * w2 / sm) ** 2
    eta_dz = math.exp(-2.0 * dz_um * dz_um / (2.0 * sm)) if dz_um else 1.0
    eta = eta_dx * eta_th * eta_m * eta_dz
    return {"dx_um": dx_um, "theta_rad": theta_rad, "dz_um": dz_um,
            "w1_um": w1, "w2_um": w2,
            "eta_dx": eta_dx, "eta_theta": eta_th, "eta_mode": eta_m, "eta_dz": eta_dz,
            "eta": eta, "il_db": -10.0 * math.log10(eta) if eta > 0 else float("inf"),
            "w_sum_sq_um2": sm}


def alignment_tolerance_budget(il_budget_db: Optional[float] = None) -> Dict[str, Any]:
    """对准容差预算：给定**对准附加** IL 预算 ⇒ **闭式反解** dx_max。

    🔴 首版缺陷（自检抓出）：把 η_m（模场失配底，与 dx 无关）也算进预算 ⇒
    w₁=5.2 / w₂=2.2 的底损耗 **2.88 dB** 使得 1 dB 预算在 dx=0 处就已被吃光 ⇒ dx_max = ∞。
    真口径：**预算只管「对准失配」那一份**，模场失配底另立为「与对准无关的固有损耗」披露：

        η_target = 10^(−IL/10)                       （对准部分）
        dx_max   = √[ −(w₁²+w₂²)/2 · ln η_target ]   （闭式反解）
    """
    p = OI_M2B_PROCESS
    il = float(p["align_il_budget_db"] if il_budget_db is None else il_budget_db)
    sm = float(p["w_fiber_um"]) ** 2 + float(p["w_waveguide_um"]) ** 2
    eta_m = (2.0 * float(p["w_fiber_um"]) * float(p["w_waveguide_um"]) / sm) ** 2
    eta_target = 10.0 ** (-il / 10.0)
    dx_max = math.sqrt(-sm * 0.5 * math.log(eta_target)) if eta_target < 1.0 else float("inf")
    # 第二独立通道：数值扫描（不解析反解，直接扫 dx 找「对准 IL」越界点）
    xs = np.linspace(0.0, 12.0, 24001)
    ils_dx = -10.0 * np.log10(np.maximum(np.exp(-2.0 * xs ** 2 / sm), 1e-18))
    cross = xs[int(np.argmax(ils_dx > il))] if np.any(ils_dx > il) else float("inf")
    # 回代自检：dx_max 处的**对准 IL** 必须恰等于预算
    back = gc_coupling_efficiency(dx_um=dx_max)
    return {"il_budget_db": il, "eta_mode": eta_m,
            "il_mode_mismatch_db": -10.0 * math.log10(eta_m),
            "eta_target": eta_target,
            "dx_max_um": dx_max, "dx_max_numeric_um": float(cross),
            "dx_back_substitute_align_il_db": -10.0 * math.log10(back["eta_dx"]),
            "dx_back_substitute_total_il_db": back["il_db"],
            "unit_note": "µm（对准容差）"}


def gc_center_wl_nm(t_c: float, wl0_nm: Optional[float] = None) -> float:
    """GC 中心波长随温度漂移（热光 + 热膨胀闭式）：λ_c(T) = λ₀[1 + (dn/dT/n_eff + α)·ΔT]。"""
    p = OI_M2B_PROCESS
    wl0 = float(p["wl0_nm"] if wl0_nm is None else wl0_nm)
    dT = float(t_c)
    drift = (float(_DN_DT) / float(p["ring_n_eff"]) + float(p["alpha_si_per_k"])) * dT
    return wl0 * (1.0 + drift)


# GC 出射光栅几何（O-band 垂直出射 ⇒ sinθ = λ/Λ − n_eff = 0 自洽）
GC_GAP_UM = 0.2
GC_N_EFF = 2.4


def gc_walkoff_wl_um(dlam_um: float, gc_period_um: float = None,
                     n_eff: float = GC_N_EFF) -> float:
    """GC 波长⇒出射角的依赖 ⇒ 走完 gap 的横向偏移（闭式）。

        λ/Λ = n_eff + sinθ  ⇒  cosθ·dθ = dλ/Λ  ⇒  Δθ = Δλ/(Λ·cosθ)
        Δx   = gap·Δθ

    取 Λ = λ₀/n_eff ⇒ 设计点 sinθ = 0（垂直出射），cosθ = 1 ⇒ Δθ = Δλ/Λ。
    """
    lam = float(OI_M2B_PROCESS["wl0_nm"]) / 1000.0
    L = lam / n_eff if gc_period_um is None else float(gc_period_um)
    sin_t = lam / L - n_eff
    cos_t = math.sqrt(max(1.0 - sin_t ** 2, 0.0))
    dtheta = float(dlam_um) / (L * cos_t) if cos_t > 0 else float("inf")
    return GC_GAP_UM * dtheta


def temp_drift_budget(t_lo: Optional[float] = None, t_hi: Optional[float] = None) -> Dict[str, Any]:
    """封装**温度容差预算**：温窗内 λ_c 漂移 ⇒ 出射角漂移 ⇒ gap 内横向走偏 Δx。

    Δλ(T) = λ₀·(dn/dT/n_eff + α)·ΔT（热光 + 热膨胀，闭式）⇒ Δx = gap·Δλ/(Λ·cosθ)。

    🔴 首版缺陷（自检抓出）：用「(Δλ/λ)² 小偏移近似」折算 η 漂移 ⇒ 量级 ~1e-14、毫无工程意义。
    改用**光栅出射角**真物理（GC 的波长—角度依赖才是温漂进入对准链路的正确通道）。
    """
    lo, hi = TEMP_WINDOW_C if (t_lo is None and t_hi is None) else (float(t_lo), float(t_hi))
    wl_lo, wl_hi = gc_center_wl_nm(lo), gc_center_wl_nm(hi)
    dlam_um = abs(wl_hi - wl_lo) / 1000.0
    dx_drift_um = gc_walkoff_wl_um(dlam_um)
    tol = alignment_tolerance_budget()["dx_max_um"]
    frac = float(dx_drift_um) / tol if tol > 0 else float("inf")
    return {"t_lo_c": lo, "t_hi_c": hi, "wl_lo_nm": wl_lo, "wl_hi_nm": wl_hi,
            "dlam_nm": abs(wl_hi - wl_lo), "dlam_um": dlam_um,
            "dx_drift_um": dx_drift_um, "dx_tolerance_um": tol,
            "frac_of_tolerance": frac, "in_tolerance": bool(frac <= 1.0),
            "unit_note": "µm（横向走偏）"}


# ═════════════════════════════════════════════════════════════════════════════
# 8) 诚实边界 + 自检
# ═════════════════════════════════════════════════════════════════════════════
OI_M2B_DISCLOSURE: Dict[str, str] = {
    "verdict": "DESIGN_BUDGET",
    "scope": "M2b：多通道均衡（CTLE 形态映射）· 热调功耗 · 热串扰 Γ · 工艺偏差良率 · 封装容差",
    "golden": "闭式物理律（CTLE 解析积分 / 对数热场 / 热网络有限差分 / 闭式 erf / 高斯重叠解析）",
    "not_golden": "MC 采样是第二通道，不是 golden；接收 SNR 是设计输入假设",
    "no_pdk": "器件参数为公开文献典型量级占位（非 PDK），无实测锚",
    "no_t2": "工艺偏差 σ / 温窗为设计者声明窗口，非 foundry 真值（T2 锁死）",
    "no_energy": "🔴 不报 TOPS / TOPS-W / fJ/op / pJ/bit；热调只登记 mW 功耗",
    "no_dsp_lpo": "LPO 形态无 FFE/DFE（模块内无 DSP）—— 形态映射约束，可判红",
    "gamma_scale": ("🔴 Γ 矩阵为**归一化对数场口径**（`_R_TH0_K_PER_MW` / `_D_REF_UM` 均无实测锚）"
                    "⇒ **绝对量级未标定**；三条物理律（互易/单调递减/对角最大）只是**结构性质**，"
                    "不得当热串扰定量结论对外宣称。**对角 Γ_ii 是 d→0 的钳位伪值**"
                    "（真自热 ≈ S·1mW = 0.1016 nm/mW，伪值 2.0124 nm/mW，偏大 ~20×）"
                    "——自热请用调谐斜率 S，**勿用 Γ_ii**。"),
}

_EFFECT_BANNED = ("fJ/", "pJ/bit", "TOPS-W", "能效比", "J/op")


def honest_boundary_ok() -> bool:
    """🔴 禁词只扫**肯定式宣称面**（本项目纪律：否定式声明是豁免，否则自己扫自己必红）。

    本模块的免责条款正是 `no_energy`（原文含 `fJ/op` / `pJ/bit` / `TOPS-W`）⇒ 该键**排除**，
    其余披露面（verdict/scope/golden/not_golden/no_pdk/no_t2/no_dsp_lpo/gamma_scale）
    逐条按**肯定式宣称面**扫，任一含能效词即红。
    """
    txt = " ".join(v for k, v in OI_M2B_DISCLOSURE.items() if k != "no_energy")
    return not any(b in txt for b in _EFFECT_BANNED)


def oi_m2b_self_check(verbose: bool = True) -> Dict[str, Any]:
    """模块内自检（被 `run_oi_m2b_smoke.py` 复用为互锁判据的一环）。"""
    checks: List[Tuple[str, bool]] = []

    # 1) 规格锚窗口
    checks.append(("M2b 规格锚：奈奎斯特落窗", _in_band("nyquist_ghz", NYQUIST_200G_GHZ)))
    checks.append(("M2b 规格锚：λ₀ 落窗", _in_band("wl0_nm", OI_M2B_PROCESS["wl0_nm"])))
    checks.append(("M2b 规格锚：信道间隔落窗", _in_band("spacing_nm", OI_M2B_PROCESS["spacing_nm"])))
    # 2) 🔴 环区数互锁（M2 血案 #3：抄 M1 的 129 ⇒ 版图与预算不同参）
    checks.append(("M2b 互锁：ring_m 与 OI_M2_PROCESS 同源",
                   int(OI_M2B_PROCESS["ring_m"]) == int(_M2.OI_M2_PROCESS["ring_m"])))
    checks.append(("M2b 互锁：ring_m ≠ M1 的 129（不跨档抄）",
                   int(OI_M2B_PROCESS["ring_m"]) != 129))
    checks.append(("M2b 互锁：ring_m 落窗", _in_band("ring_m", OI_M2B_PROCESS["ring_m"])))
    # 3) 形态映射
    lpo, ret = equalizer_for_form("lpo"), equalizer_for_form("retimed")
    checks.append(("M2b 形态：lpo 只有 CTLE 无 FFE（无 DSP ⇒ 不能数字均衡）",
                   bool(lpo["ctle"]) and not bool(lpo["ffe"]) and not bool(lpo["needs_dsp"])))
    checks.append(("M2b 形态：retimed 可 CTLE+FFE（有 DSP）",
                   bool(ret["ctle"]) and bool(ret["ffe"]) and bool(ret["needs_dsp"])))
    # 4) CTLE 闭式 + 退化
    F = NYQUIST_200G_GHZ * 1e9
    a = float(OI_M2B_PROCESS["f_tia_ghz"]) * 1e9
    z = f_z_for_boost(F, a, float(OI_M2B_PROCESS["ctle_boost_db"]))
    checks.append(("M2b CTLE：boost 反解 ⇒ 回代幅度恰等于目标（互锁）",
                   abs(10.0 * math.log10((1.0 + (F / z) ** 2) / (1.0 + (F / a) ** 2))
                       - float(OI_M2B_PROCESS["ctle_boost_db"])) < 1e-6))
    checks.append(("M2b CTLE：噪声 penalty 解析积分 ⟷ trapz 数值积分（第二通道）",
                   abs(ctle_noise_penalty_db(z, a, F)
                       - 10.0 * math.log10(_nbw_numeric(z, a, F) / F)) < 1e-3))
    checks.append(("M2b CTLE 退化：f_z=f_p（flat）⇒ penalty ≡ 0 dB",
                   abs(ctle_noise_penalty_db(a, a, F)) < 1e-9))
    # 5) 逐 lane 多通道
    des = lane_ctle_design()
    checks.append(("M2b 多通道：逐 lane 抽头数 == lane 数",
                   len(des["lanes"]) == int(OI_M2B_PROCESS["n_lanes"])))
    checks.append(("M2b 多通道：各 lane 目标 boost 真不同（不再是「单通道均衡 ×N」摆设）",
                   bool(des["boost_distinct"])))
    checks.append(("M2b 多通道：逐 lane f_z 真不同（工艺离散 ⇒ 多通道均衡非摆设）",
                   len({round(x["f_z_hz"], 6) for x in des["lanes"]})
                   == int(OI_M2B_PROCESS["n_lanes"])))
    checks.append(("M2b 多通道：设计方程往返自洽（total_gain ≡ b_nom+loss_ref；弱判据，如实标注）",
                   bool(des["design_roundtrip_flat"])))
    _flat = lane_equalization_flatness()
    checks.append(("M2b 多通道：**均衡成效**（独立重算 · 逐 lane 真信道 ISI 拉平）",
                   bool(_flat["equalization_flat_ok"])
                   and _flat["channel_source"] == "per_lane(f_mod_ghz)"))
    # 6) 热调（功耗口径）
    tb = thermal_tune_budget()
    _d0 = tb["residual_detune_nm"]
    _p2 = thermal_tune_budget(residual_detune_nm=2.0 * _d0)["p_tune_mw_per_lane"]
    checks.append(("M2b 热调：P_tune ∝ 剩余失谐（P = Pπ·Δλ/FSR，闭式线性）",
                   abs(_p2 - 2.0 * tb["p_tune_mw_per_lane"]) < 1e-12))
    checks.append(("M2b 热调：只出 mW 不出能效（honest_boundary）", honest_boundary_ok()))
    checks.append(("M2b 热调：FSR 走单一真源 `fsr_nm`（回退常量 4.5 nm 分支已删 · 修 F7）",
                   no_fsr_fallback_ok()))
    # 7) Γ 三条物理律
    g = crosstalk_gamma()
    checks.append(("M2b Γ：对称（热传导互易）", g["symmetric_ok"]))
    checks.append(("M2b Γ：对角最大（自身加热最强）", g["diagonal_max_ok"]))
    checks.append(("M2b Γ：随距离单调递减", g["monotonic_ok"]))
    # 8) 良率双通道
    yc, ym = yield_closed_form(), yield_monte_carlo()
    checks.append(("M2b 良率：闭式 erf ⟷ MC 第二通道（|Δ| < 1e-2）",
                   abs(yc["yield"] - ym["yield"]) < 1e-2))
    checks.append(("M2b 良率：σ=0 ⇒ yield=1（退化）",
                   abs(yield_closed_form(sigma_dn_eff=0.0)["yield"] - 1.0) < 1e-12))
    checks.append(("M2b 良率：tol=0 ⇒ yield=0（边界）",
                   abs(yield_closed_form(tol_nm=0.0)["yield"]) < 1e-12))
    # 9) 封装容差
    ab = alignment_tolerance_budget()
    checks.append(("M2b 封装：闭式反解 dx_max ⟷ 数值扫描（|Δ| < 0.05 µm）",
                   abs(ab["dx_max_um"] - ab["dx_max_numeric_um"]) < 0.05))
    checks.append(("M2b 封装：dx_max 回代「对准 IL」== 预算（闭式 ⟷ 回代互锁）",
                   abs(ab["dx_back_substitute_align_il_db"] - ab["il_budget_db"]) < 1e-6))
    checks.append(("M2b 封装：dx=0 时 η = η_m（无失配只剩模场失配底）",
                   abs(gc_coupling_efficiency(dx_um=0.0)["eta"]
                       - gc_coupling_efficiency(dx_um=0.0)["eta_mode"]) < 1e-12))
    checks.append(("M2b 封装：预算先扣模场失配底（模场底 < 预算 ⇒ 容差可达）",
                   ab["il_mode_mismatch_db"] < ab["il_budget_db"]))
    tdb = temp_drift_budget()
    checks.append(("M2b 封装温漂：Δx/gap·Δλ/(Λcosθ) 走偏落在对准容差内",
                   bool(tdb["in_tolerance"])))

    checks.append(("M2b 诚实边界：披露面无禁出词（TOPS-W/fJ/pJ-bit/能效比）",
                   honest_boundary_ok()))

    ok = all(c[1] for c in checks)
    if verbose:
        for name, good in checks:
            print(("  [%s] " % ("PASS" if good else "FAIL")) + name)
        print("-" * 70)
        print("M2b 自检：%d PASS / %d FAIL / 共 %d 项" %
              (sum(1 for _, x in checks if x), sum(1 for _, x in checks if not x), len(checks)))
    return {"ok": ok, "checks": checks,
            "n_pass": sum(1 for _, x in checks if x), "n_fail": sum(1 for _, x in checks if not x)}


if __name__ == "__main__":
    r = oi_m2b_self_check()
    raise SystemExit(0 if r["ok"] else 1)
