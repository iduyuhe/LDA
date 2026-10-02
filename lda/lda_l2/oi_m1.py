# -*- coding: utf-8 -*-
"""LDA 光联接模块征程 · M1（800G 收发器 · 频域 / 时域预算）。

M0（`oi_module.py`）= 链路预算（**功率**）；M1 = 在功率预算之上补 **频域（带宽）**
与 **时域（色散 / 眼）** 两维，闭合 G-OI3（级电光行为模型）：

  · **G-OI3-a EO S21**：调制器（RC 闭式 + 行波设计参数，A 档）· 探测器（τ=RC，同 B33 式）
                       · TIA（单极点，**复用** `eic_behavioral`）→ 级联得链路 EO S21 / `f_3dB`。
  · **G-OI3-b 眼图 / BER**：符号间隔冲激响应抽头 → 三眼 + Q + BER
                       （golden = 闭式 Q 函数 `0.375·erfc(Q/√2)`）。
  · **G-OI3-c 驱动-TIA 协同**：**复用** `lda_l2.eic_behavioral`（驱动阶跃 + TIA 单极点）。
  · **G-OI3-d 光纤色散**：β₂ 相位算子 + 高斯脉冲展宽闭式 `σ₁² = σ₀² + (β₂L)²/(4σ₀²)`。
  · **G-OI1 信道规划（梳齿规避）**：平台既有 `channel_capacity` 用「FSR > 信道跨度」——
    该条件**充分非必要**；在 LDA DRC（R ≥ 5 µm）下 FSR 上限 ≈ 18 nm，8×4.5 nm 跨度
    31.5 nm 必违反，但**梳齿规避**（选 m 使各环梳齿距目标信道偏移最大化）仍可把偏移
    做到 ~1.24 nm ≫ 线宽 ⇒ 隔离 **39.5 dB**（M0 默认 m=170/gap=0.3 时为 **−0.9 dB**，崩溃）。

🔴 诚实边界（红线 `docs/lda_active_device_redline_clarification_2026-09-10.md` §四 A 档）：
  · 全部为 **闭式物理律 / 行为级**（A 档）：**不碰** 电-光耦合增益真值（T2 锁）· 不用 A 级商业工具 · 不流片。
  · 🔴 **BER = 光链路预算级闭式估计**（golden = 闭式 Q 函数），**不含** SerDes / DSP / FEC / 均衡 / CDR
    —— 与 `eic_behavioral.EIC_DISCLOSURE`（排除 **EIC 电路级** BER）**显式分层**（不同层：本模块=光通道预算）。
  · 🔴 **接收 SNR 是设计输入假设**（非实测噪声预算）；免该假设的指标另给 `required_snr_db`。
  · `verdict` 恒 `DESIGN_BUDGET`；**不报** TOPS / TOPS-W / fJ/op。
  · 器件为 **L0/L1 解析 / 行为模型**，参数为公开文献典型量级占位（**非 PDK**），**无实测锚**。

🔧 随本征程同时修掉的 **M0 遗留平台缺陷**（见 `oi_module.py` 内注释与 CHANGELOG）：
  1. `transceiver_m0_budget` 曾**硬编码 m=170**（与 `build_transceiver_m0(m=...)` 脱钩
     ⇒ 换 m 装配时闭式(A)与级联(B)静默分歧）→ 现为显式入参。
  2. `build_transceiver_m0` 的 B4（FSR）目标曾把 λ 以「1.55 当 nm」传入 `fsr_nm`
     ⇒ 目标恒为 0.0 nm → 现传 `channels_nm[i]`（nm），目标 9.118 nm。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from lda_l2.eic_behavioral import tia_bandwidth_hz  # 单极点 TIA（复用，不复制）

C_M_S = 2.99792458e8


# ─────────────────────────────────────────────────────────────────────────────
# 设计常数（公开文献典型量级占位 · **非 PDK**）
# ─────────────────────────────────────────────────────────────────────────────
OI_M1_PROCESS: Dict[str, float] = {
    "r_electrode_ohm": 20.0,     # 调制器电极串联电阻
    "c_junction_fF": 120.0,      # 结电容
    "c_electrode_fF": 30.0,      # 电极寄生电容
    "n_g": 4.2,                  # 群折射率
    "f_mod_ghz": 55.0,           # 调制器 EO 3dB 带宽（行波设计目标；本模型不解析行波电极）
    "f_pd_ghz": 60.0,            # 探测器 3dB 带宽（τ=RC 口径）
    "r_f_ohm": 350.0,            # TIA 反馈电阻（100G 档）
    "c_f_fF": 5.0,               # TIA 反馈电容
    "d_ps_nm_km": 17.0,          # SMF 色散系数 @ C-band（O-band ≈ 0）
    "wl_nm": 1550.0,             # 参考波长
    "baud_gbd": 53.125,          # 100G PAM4 符号率（线速率 106.25 Gb/s，FEC 后净 100 Gb/s）
    "n_lanes": 8,                # 800G = 8×100G
    "spacing_nm": 4.5,           # LWDM ≈ 800 GHz 间隔
    "wl0_nm": 1550.0,            # 首信道波长（C-band 主设计点）
    "reach_km": 2.0,             # 设计跨度（C-band 主点；O-band 对照更长）
    "snr_db": 28.0,              # 🔴 **设计输入假设**（满幅信噪比 · 接收端电 SNR）；非实测噪声预算
    "tx_sigma_frac": 0.25,       # 源脉冲 RMS σ₀ = frac × T_sym（时域源宽；供色散展宽闭式对拍）
    "tau_driver_ps": 2.5,        # 🔴 驱动一阶时间常数设计目标（100G 档；非实测）
    "ring_m": 129,               # 环区数 m（R≈7.58 µm；由 `plan_lwdm_channels` 梳齿规避搜索给出）
    "ring_gap_um": 0.55,         # bus 耦合 gap（窄线宽 ⇒ 抑制梳齿重叠窜扰）
}

# 设计点预设：C-band 主 + O-band 对照（杜先生 2026-10-02 定调）
# 🔴 `expect` 为门禁消费的**声明式期望**：新增设计点必须显式声明，否则门禁判 FAIL
#    （防「新成员静默进盲区」）。取值：`pass`（预算内）· `disp_limited`（色散主导、SNR 不可达）。
SPEC_POINTS: List[Dict[str, Any]] = [
    {"key": "C_2km", "band": "C", "wl_nm": 1550.0, "d_ps_nm_km": 17.0,
     "reach_km": 2.0, "role": "main", "expect": "pass",
     "note": "主设计点：C-band 2 km（色散可见但预算内）"},
    {"key": "C_10km", "band": "C", "wl_nm": 1550.0, "d_ps_nm_km": 17.0,
     "reach_km": 10.0, "role": "limit", "expect": "disp_limited",
     "note": "设计边界：C-band 10 km（色散主导 ⇒ 促「改 O-band 或加 EDC」结论）"},
    {"key": "O_2km", "band": "O", "wl_nm": 1310.0, "d_ps_nm_km": 0.0,
     "reach_km": 2.0, "role": "control", "expect": "pass",
     "note": "对照：O-band 1310 nm 近零色散"},
    {"key": "O_10km", "band": "O", "wl_nm": 1310.0, "d_ps_nm_km": 0.0,
     "reach_km": 10.0, "role": "control", "expect": "pass",
     "note": "对照：O-band 10 km 仍近零色散（对照 C-band 长距）"},
]


# ─────────────────────────────────────────────────────────────────────────────
# 1) 一阶单极点工具（闭式 golden）
# ─────────────────────────────────────────────────────────────────────────────
def first_order_mag(f_hz: float, f3db_hz: float) -> float:
    """一阶低通幅频 `|H(f)| = 1/√(1+(f/f_3dB)²)`。"""
    return 1.0 / math.sqrt(1.0 + (f_hz / f3db_hz) ** 2)


def modulator_bandwidth_hz(r_ohm: Optional[float] = None,
                           c_total_f: Optional[float] = None,
                           n_g: Optional[float] = None,
                           arm_um: Optional[float] = None) -> Dict[str, float]:
    """调制器**集总** RC + 渡越限制的 3dB 带宽（闭式 · golden 可验）。

      τ_RC  = R·(C_j + C_e)   → f_RC  = 1/(2π τ_RC)
      τ_tr  = L_arm / v_g     → f_tr  = 1/(2π τ_tr)，v_g = c/n_g
      τ_mod = √(τ_RC² + τ_tr²) → f_mod = 1/(2π τ_mod)   （独立两限 → 均方合成）

    🔴 诚实边界：这是**集总下界**；真实高速 Si MZM 用**行波电极 + 速度匹配**，实测带宽更高。
    M1 的 EO 链路默认用 `OI_M1_PROCESS["f_mod_ghz"]`（行波设计参数），本函数作**下界交叉核对**。
    """
    p = OI_M1_PROCESS
    r = p["r_electrode_ohm"] if r_ohm is None else r_ohm
    c = (((p["c_junction_fF"] + p["c_electrode_fF"]) * 1e-15)
         if c_total_f is None else c_total_f)
    ng = p["n_g"] if n_g is None else n_g
    arm = (1e3 if arm_um is None else arm_um)  # 默认 1 mm 臂
    tau_rc = r * c
    v_g = C_M_S / ng
    tau_tr = (arm * 1e-6) / v_g
    tau = math.sqrt(tau_rc ** 2 + tau_tr ** 2)
    return {
        "f_rc_hz": 1.0 / (2.0 * math.pi * tau_rc),
        "f_transit_hz": 1.0 / (2.0 * math.pi * tau_tr),
        "tau_rc_s": tau_rc, "tau_tr_s": tau_tr,
        "f_mod_lumped_hz": 1.0 / (2.0 * math.pi * tau),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2) 链路 EO S21（调制器 × 探测器 × TIA 级联）
# ─────────────────────────────────────────────────────────────────────────────
def eo_s21_complex(f_hz: float, f_mod_hz: float, f_pd_hz: float,
                   f_tia_hz: float) -> complex:
    """级联 EO 频响 `H(f) = Πᵢ 1/(1 + j f/fᵢ)`（三个单极点，i ∈ {mod,pd,tia}）。"""
    h = 1.0 + 0j
    for fi in (f_mod_hz, f_pd_hz, f_tia_hz):
        h *= 1.0 / (1.0 + 1j * f_hz / fi)
    return h


def eo_s21_f3db_hz(f_mod_hz: float, f_pd_hz: float, f_tia_hz: float,
                   tol: float = 1e-9) -> float:
    """级联 EO S21 的 −3 dB 带宽 = 解 `|H(f)| = 1/√2`（几何二分 · 严格）。

    golden 交叉点：**单极点**时 f_3dB ≡ fᵢ（由门禁断言该退化）。
    """
    target = 1.0 / math.sqrt(2.0)
    lo, hi = 1.0, max(f_mod_hz, f_pd_hz, f_tia_hz) * 100.0
    for _ in range(300):
        mid = math.sqrt(lo * hi)  # 几何中点（跨数量级更稳）
        if abs(hi - lo) <= tol * mid:
            return mid
        if abs(eo_s21_complex(mid, f_mod_hz, f_pd_hz, f_tia_hz)) >= target:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)


# ─────────────────────────────────────────────────────────────────────────────
# 3) 光纤色散
# ─────────────────────────────────────────────────────────────────────────────
def beta2_s2_per_m(d_ps_nm_km: float, wl_nm: float) -> float:
    """色散系数 D → β₂：`β₂ = −(λ²/(2πc))·D`（D 单位 ps/(nm·km) → s/m²）。"""
    d_si = d_ps_nm_km * 1e-12 / (1e-9 * 1e3)  # ps/(nm·km) → s/m²
    lam = wl_nm * 1e-9
    return -(lam ** 2 / (2.0 * math.pi * C_M_S)) * d_si


def dispersion_broadening_s(sigma0_s: float, beta2_s2_m: float, L_m: float) -> float:
    """高斯脉冲经色散后 RMS 展宽闭式 golden：`σ₁² = σ₀² + (β₂L)²/(4σ₀²)`。"""
    return math.sqrt(sigma0_s ** 2 + (beta2_s2_m * L_m) ** 2 / (4.0 * sigma0_s ** 2))


def dispersion_penalty_db(sigma0_s: float, beta2_s2_m: float, L_m: float,
                          baud_gbd: float) -> float:
    """色散代价（dB）· 预算级：`10·log10(1 + (Δσ/(T_sym/4))²)`，Δσ = σ₁−σ₀。

    🔴 预算级经验口径（**非**实测 penalty），close 于工程常用「展宽/符号周期」判据。
    """
    sigma1 = dispersion_broadening_s(sigma0_s, beta2_s2_m, L_m)
    d_sig = sigma1 - sigma0_s
    t_sym = 1.0 / (baud_gbd * 1e9)
    return 10.0 * math.log10(1.0 + (d_sig / (t_sym / 4.0)) ** 2)


# ─────────────────────────────────────────────────────────────────────────────
# 4) 时域 PAM4 眼 / BER（符号间隔冲激响应抽头法 · numpy）
# ─────────────────────────────────────────────────────────────────────────────
_PAM4_LEVELS = (-3.0, -1.0, 1.0, 3.0)   # 电平（等间距 2，满幅 6）
# 🔴 「电平→序号」映射不在模块级另写一份：由 `_PAM4_LEVELS` **单一真源**在调用点派生
#    （U10 血案：同一映射两处各写一份 ⇒ 只改一处仍全绿 / 探针抓不住）。


def _gray2(i: int) -> int:
    return i ^ (i >> 1)


def _channel_taps(f_mod_hz: float, f_pd_hz: float, f_tia_hz: float,
                  beta2_s2_m: float, L_m: float, baud_hz: float,
                  sigma_tx_s: float = 0.0,
                  n_taps: int = 32, os: int = 64,
                  h_extra: Optional["object"] = None) -> np.ndarray:
    """信道**符号间隔冲激响应抽头**（因果 · cursor 归一化为 1）。

    由 `H(f) = H_tx(f) × EO S21(f) × 色散(f)` 经 IFFT 得 `h(t)`，再在符号间隔取抽头
    `taps[j] = h(pk + j·T_sym)/h(pk)`：`taps[0] ≡ 1`（cursor）· `taps[j>0]`（ISI 抽头）。

    · `H_tx(f) = exp(−ω²σ₀²/2)`：**源脉冲**（高斯，RMS = σ₀）—— 缺它则色散展宽闭式
      `σ₁² = σ₀² + (β₂L)²/(4σ₀²)`（§3，方法学独立）与时域仿真**不同源**、不可对拍。
    """
    tsym = 1.0 / baud_hz
    n_pts = (n_taps + 8) * os
    dt = tsym / os
    freqs = np.fft.rfftfreq(n_pts, d=dt)
    w = 2.0 * math.pi * freqs
    h = (1.0 / (1.0 + 1j * freqs / f_mod_hz)
         * 1.0 / (1.0 + 1j * freqs / f_pd_hz)
         * 1.0 / (1.0 + 1j * freqs / f_tia_hz))
    if sigma_tx_s > 0.0:
        h = h * np.exp(-0.5 * (w * sigma_tx_s) ** 2)
    if beta2_s2_m != 0.0 and L_m != 0.0:
        h = h * np.exp(1j * (beta2_s2_m * L_m / 2.0) * w ** 2)
    if h_extra is not None:
        # M2b 接线点：把**额外级联频响**（如模拟 CTLE）乘进来，抽头/眼/BER 全部随之更新。
        # 默认 None ⇒ 本函数行为与历史逐位一致（M1 门禁不受影响）。
        #
        # 🔴 契约（外部频栅 ≠ 本函数频栅，绝不用插值糊过去）：
        #    `h_extra` 必须是 **callable(freqs) → 复数频响**，在本函数**自己的频栅**
        #    `freqs`（长 `freqs.size`）上求值后逐点乘入。形状不符直接报错失败，
        #    避免「静默广播/静默插值」把 CTLE 形态画错 —— 抽头/BER 全跟着错，
        #    而**源头判据仍然全绿**（本项目反复踩的坑：假绿）。
        if not callable(h_extra):
            raise TypeError("h_extra 必须是 callable(freqs)->complex（不得直接传数组，"
                            "外部频栅与本函数频栅不同步）")
        h_extra_h = np.asarray(h_extra(freqs), dtype=complex)
        if h_extra_h.shape != h.shape:
            raise ValueError("h_extra 求值结果与信道频栅形状不符：%s vs %s"
                             % (h_extra_h.shape, h.shape))
        h = h * h_extra_h
    ht = np.fft.irfft(h, n=n_pts)
    # 🔴 级联多极点冲激响应在 t=0 为 0（峰在其后）⇒ 必须按**峰值**对齐取抽头
    pk = int(np.argmax(np.abs(ht)))
    taps = np.array([ht[pk + j * os] if (pk + j * os) < n_pts else 0.0
                     for j in range(n_taps)], dtype=float)
    cursor = taps[0] if abs(taps[0]) > 1e-12 else 1.0
    return taps / cursor


def _eye_metrics(samp: np.ndarray, sym_idx: np.ndarray) -> List[Dict[str, float]]:
    """三眼指标：相邻电平对之间的 Q = (μ_up−μ_low)/(σ_up+σ_low)。"""
    out = []
    for a, b in ((0, 1), (1, 2), (2, 3)):
        lo = samp[sym_idx == a]
        hi = samp[sym_idx == b]
        mu_lo, mu_hi = float(np.mean(lo)), float(np.mean(hi))
        s_lo = float(np.std(lo)) or 1e-12
        s_hi = float(np.std(hi)) or 1e-12
        out.append({"lo_level": _PAM4_LEVELS[a], "hi_level": _PAM4_LEVELS[b],
                    "mu_lo": mu_lo, "mu_hi": mu_hi,
                    "eye_height": mu_hi - mu_lo,
                    "sigma": 0.5 * (s_lo + s_hi),
                    "q": (mu_hi - mu_lo) / (s_lo + s_hi)})
    return out


def _pam4_decide(samp: np.ndarray) -> np.ndarray:
    """PAM4 判决：门限取 `_PAM4_LEVELS` **相邻电平中点**（单一真源派生）。

    等间距电平（−3,−1,+1,+3）时门限即 −2/0/+2（与 M1 初版数值一致），但改为派生后
    电平定义在**唯一一处**（U10 血案：同一判据两处各写一份 ⇒ 突变探针抓不住）。
    """
    lv = np.asarray(_PAM4_LEVELS, dtype=float)
    thr = 0.5 * (lv[:-1] + lv[1:])
    dec = np.empty_like(samp)
    dec[samp < thr[0]] = lv[0]
    for k in range(1, len(thr)):
        dec[(samp >= thr[k - 1]) & (samp < thr[k])] = lv[k]
    dec[samp >= thr[-1]] = lv[-1]
    return dec


def pam4_link_sim(baud_gbd: Optional[float] = None, f_mod_ghz: Optional[float] = None,
                  f_pd_ghz: Optional[float] = None, f_tia_ghz: Optional[float] = None,
                  d_ps_nm_km: Optional[float] = None, L_km: Optional[float] = None,
                  wl_nm: Optional[float] = None, n_sym: int = 8192, n_taps: int = 32,
                  os: int = 64, snr_db: Optional[float] = None, seed: int = 0,
                  sigma_tx_frac: Optional[float] = None,
                  flatten_channel: bool = False, no_dispersion: bool = False
                  ) -> Dict[str, Any]:
    """PAM4 时域链路预算：符号间隔抽头 → 采样 → 三眼 + Q + BER。

    · `snr_db` 缺省取 `OI_M1_PROCESS["snr_db"]`（**设计输入假设**，非实测噪声预算）。
    · 候选：**时域 MC**（Gray 解码比特计数得 `ber_mc`）。
    · golden：**AWGN 无 ISI**（`flatten_channel=True, no_dispersion=True`）⇒ `taps≈[1,0,…]`
      ⇒ 理论 `Q = Δ/(2σ)`（Δ=2）、`BER = 0.375·erfc(Q/√2)`（PAM4 Gray 闭式），与 MC 一致。
    """
    p = OI_M1_PROCESS
    baud = (p["baud_gbd"] if baud_gbd is None else baud_gbd) * 1e9
    wl = p["wl_nm"] if wl_nm is None else wl_nm
    snr = p["snr_db"] if snr_db is None else snr_db
    stx_frac = p["tx_sigma_frac"] if sigma_tx_frac is None else sigma_tx_frac
    tsym = 1.0 / baud
    sigma_tx = stx_frac * tsym
    dcoef = 0.0 if no_dispersion else (p["d_ps_nm_km"] if d_ps_nm_km is None else d_ps_nm_km)
    L_km_eff = p["reach_km"] if L_km is None else L_km
    fmod = (p["f_mod_ghz"] if f_mod_ghz is None else f_mod_ghz) * 1e9
    fpd = (p["f_pd_ghz"] if f_pd_ghz is None else f_pd_ghz) * 1e9
    ftia = (tia_bandwidth_hz(p["r_f_ohm"], p["c_f_fF"] * 1e-15)
            if f_tia_ghz is None else f_tia_ghz * 1e9)
    if flatten_channel:
        fmod = fpd = ftia = 1e18
    beta2 = 0.0 if (no_dispersion or flatten_channel) else beta2_s2_per_m(dcoef, wl)
    L_m_eff = 0.0 if flatten_channel else L_km_eff * 1e3
    taps = _channel_taps(fmod, fpd, ftia, beta2, L_m_eff, baud, sigma_tx,
                         n_taps, os)

    rng = np.random.default_rng(seed)
    sym_idx = rng.integers(0, 4, size=n_sym)
    a = np.array(_PAM4_LEVELS, dtype=float)[sym_idx]
    y = np.zeros(n_sym)
    for j in range(n_taps):
        if abs(taps[j]) < 1e-9:
            continue
        y[j:] += taps[j] * a[: n_sym - j]          # y[k] += taps[j]·a[k−j]
    sigma = 6.0 / (10.0 ** (snr / 20.0))           # 噪声 σ（满幅 6 定义 SNR）
    y = y + rng.normal(0.0, sigma, size=n_sym)

    eyes = _eye_metrics(y, sym_idx)
    q_min = min(e["q"] for e in eyes)
    # PAM4 Gray 闭式：每门限 p = ½·erfc(Q/√2)；4 电平均值 SER=1.5p、BER=SER/2 ⇒ 0.375·erfc
    ber_closed = 0.375 * float(np.mean(
        [math.erfc(e["q"] / math.sqrt(2.0)) for e in eyes]))
    dec = _pam4_decide(y)
    # MC 比特误码（Gray 解码）；电平→序号映射由 `_PAM4_LEVELS` 单一真源派生
    idx_of = {float(v): i for i, v in enumerate(_PAM4_LEVELS)}
    tx_bit = np.array([_gray2(idx_of[float(v)]) for v in a])
    rx_bit = np.array([_gray2(idx_of[float(v)]) for v in dec])
    bit_errs = int(sum(bin(int(d)).count("1") for d in (tx_bit ^ rx_bit)))
    ber_mc = bit_errs / (2.0 * n_sym)
    return {
        "baud_gbd": baud / 1e9, "wl_nm": wl, "reach_km": L_km_eff,
        "f_mod_ghz": fmod / 1e9, "f_pd_ghz": fpd / 1e9, "f_tia_ghz": ftia / 1e9,
        "f_3db_eo_ghz": eo_s21_f3db_hz(fmod, fpd, ftia) / 1e9,
        "snr_db": snr, "noise_sigma": sigma, "sigma_tx_s": sigma_tx,
        "eyes": eyes, "q_min": q_min,
        "ber_closed": ber_closed, "ber_mc": ber_mc, "bit_errors": bit_errs,
        "isi_taps": [float(t) for t in taps[:8]],
        "d_ps_nm_km": dcoef, "beta2_s2_per_m": beta2,
        "flat": flatten_channel, "no_disp": no_dispersion,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4b) 免 SNR 假设的灵敏度指标（所需 SNR / 代价）· 与 §3 闭式色散代价独立对拍
# ─────────────────────────────────────────────────────────────────────────────
_PAM4_BER_COEF = 0.375               # PAM4 Gray 闭式系数（4 电平平均 SER=1.5p、BER=SER/2）
# 🔴 公开规格锚（外部标准 = 限值口径，可用；**非 LDA 成就、非仿真值**）：
#   KP4 FEC = RS(544,514) over GF(2^10)，t=15 符号纠错（IEEE 802.3bs/df · Clause 91）。
#   公开一致的 **pre-FEC BER 门限 ≈ 2.4e-4**（Keysight《数据中心向 224Gbps 演进》应用笔记；
#   Vitex 800G 验收指南；Heather Technologies IEEE 802.3 FEC 对照表 —— 三源独立一致）。
#   ⚠️ 2026-10-02 修正：此处曾误写 2.4e-2（差 100×），会把「所需 SNR」整体低估约 5 dB
#   （20.92dB vs 正确 26.24dB），使设计点显得远比真实宽松 ⇒ 由 C13 规格锚 + 探针 P6 锁死。
TARGET_BER_KP4 = 2.4e-4              # KP4 pre-FEC BER 门限（IEEE 802.3bs/df RS(544,514)）
# 合理性区间（工业共识 ~26 dB，**非 golden**，仅防量级漂移的护栏窗口）
_KP4_REQUIRED_SNR_BAND_DB = (25.0, 27.5)


def _erfcinv(y: float, lo: float = 0.0, hi: float = 40.0, iters: int = 200) -> float:
    """erfc 的单调反函数（二分实现；**不引入 scipy 依赖**）。"""
    if not (0.0 < y < 1.0):
        raise ValueError("erfcinv 定义域 y∈(0,1)，得 %r" % (y,))
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if math.erfc(mid) > y:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def ideal_required_snr_db(target_ber: float = TARGET_BER_KP4) -> float:
    """**golden 闭式**：AWGN 无 ISI 下达到 `target_ber` 所需 SNR（dB）。

    `Q_req = √2·erfcinv(ber/0.375)`；又 `Q = 眼高/(σ_lo+σ_hi) = 2/(2σ) = 1/σ`、
    `σ = 6/10^(snr/20)`（满幅 6 定义 SNR）⇒ `snr = 20·log10(6·Q_req)`。
    """
    q_req = math.sqrt(2.0) * _erfcinv(target_ber / _PAM4_BER_COEF)
    return 20.0 * math.log10(6.0 * q_req)


def required_snr_db(target_ber: float = TARGET_BER_KP4, snr_lo_db: float = 6.0,
                    snr_hi_db: float = 60.0, **sim_kw: Any) -> Dict[str, Any]:
    """达到 `target_ber` 所需的最小接收 SNR（dB）—— **免「设计 SNR」假设** 的灵敏度指标。

    对 `pam4_link_sim(...)["ber_closed"](snr_db)` 二分（BER 随 SNR 单调降；固定 seed 时
    噪声实现随 σ 线性缩放 ⇒ 该函数光滑单调）。若 `snr_hi_db` 仍未达标 ⇒ 该构型在
    **预算级无 DSP/EDC 模型**下**眼被 ISI 闭合、SNR 不可达**（这本身是设计结论）。
    """
    def _ber(s: float) -> float:
        return pam4_link_sim(snr_db=s, **sim_kw)["ber_closed"]

    b_hi = _ber(snr_hi_db)
    if b_hi > target_ber:
        return {"target_ber": target_ber, "snr_db": float(snr_hi_db),
                "reachable": False, "ber_at": b_hi, "snr_hi_db": float(snr_hi_db)}
    lo, hi = snr_lo_db, snr_hi_db
    for _ in range(24):
        mid = 0.5 * (lo + hi)
        if _ber(mid) > target_ber:
            lo = mid
        else:
            hi = mid
    return {"target_ber": target_ber, "snr_db": float(hi), "reachable": True,
            "ber_at": _ber(hi), "snr_hi_db": float(snr_hi_db)}


# ─────────────────────────────────────────────────────────────────────────────
# 4c) G-OI3-c 驱动–TIA 协同（**复用** eic_behavioral，不重复实现）
# ─────────────────────────────────────────────────────────────────────────────
def driver_tia_cosim(n_lanes: Optional[int] = None,
                     tau_driver_s: Optional[float] = None,
                     baud_gbd: Optional[float] = None,
                     r_f_ohm: Optional[float] = None,
                     c_f_fF: Optional[float] = None) -> Dict[str, Any]:
    """驱动–TIA 协同预算：驱动阶跃（闭式 ⟷ RK4 两法对照）+ TIA 单极点带宽。

    · 上升时延 `10%→90%` = `τ·ln9`（闭式）→ 折算 **UI 占比**（设计目标 ≪ 1 UI）。
    · TIA −3 dB 带宽 vs Nyquist（`baud/2`）。
    🔴 承接 `eic_behavioral.EIC_DISCLOSURE`：无噪声/非线性/温度/失配 ⇒ 只作**斜率与带宽预算**；
      **零能效数字**；`τ_driver` 为设计目标，非实测。
    """
    from lda_l2.eic_behavioral import (driver_step_rk4, TAU_DRIVER_S_DEFAULT,
                                       tia_bandwidth_hz as _tia_bw)
    p = OI_M1_PROCESS
    n = p["n_lanes"] if n_lanes is None else n_lanes
    tau = (p["tau_driver_ps"] * 1e-12) if tau_driver_s is None else tau_driver_s
    baud = (p["baud_gbd"] if baud_gbd is None else baud_gbd) * 1e9
    rf = p["r_f_ohm"] if r_f_ohm is None else r_f_ohm
    cf = (p["c_f_fF"] * 1e-15) if c_f_fF is None else c_f_fF

    t10_cf = -tau * math.log(1.0 - 0.1)          # v(t) = V_dd(1−e^{−t/τ}) 反解
    t90_cf = -tau * math.log(1.0 - 0.9)
    rise_cf = t90_cf - t10_cf

    # RK4 独立对照（数值积分 · 不同源）：求 v(t) 首越 0.9·V_dd 的时刻
    vdd, n_scan = 2.0, 4000
    dt = 6.0 * tau / n_scan
    t90_rk = None
    for i in range(1, n_scan + 1):
        ti = i * dt
        if driver_step_rk4(ti, tau_s=tau, v_dd=vdd, n_steps=max(1, i)) >= 0.9 * vdd:
            t90_rk = ti
            break

    tsym = 1.0 / baud
    f_tia = _tia_bw(rf, cf)
    return {
        "n_lanes": n, "tau_driver_s": tau,
        "tau_driver_module_default_s": TAU_DRIVER_S_DEFAULT,
        "rise_10_90_s": rise_cf, "rise_10_90_ui": rise_cf / tsym,
        "t90_closed_form_s": t90_cf, "t90_rk4_s": t90_rk,
        "t90_abs_diff_s": (abs(t90_cf - t90_rk) if t90_rk is not None else None),
        "f_tia_hz": f_tia, "f_tia_ghz": f_tia / 1e9,
        "tia_over_nyquist": f_tia / (baud / 2.0),
        "driver_fast_enough": rise_cf / tsym < 0.5,
        "tia_wide_enough": f_tia / (baud / 2.0) > 1.0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5) 800G 收发器装配（复用 M0）
# ─────────────────────────────────────────────────────────────────────────────
def m1_channels(n_lanes: Optional[int] = None, spacing_nm: Optional[float] = None,
                wl0_nm: Optional[float] = None) -> List[float]:
    """LWDM 信道栅（默认 8 通道 · 4.5 nm ≈ 800 GHz 间隔 · C-band 起 1550 nm）。"""
    p = OI_M1_PROCESS
    n = p["n_lanes"] if n_lanes is None else n_lanes
    sp = p["spacing_nm"] if spacing_nm is None else spacing_nm
    w0 = p["wl0_nm"] if wl0_nm is None else wl0_nm
    return [round(w0 + sp * i, 4) for i in range(n)]


def min_comb_detune_nm(channels_nm: List[float], Rs: List[float],
                       n_g: float = 4.2) -> float:
    """**梳齿规避**判据：各环谐振梳齿距「非自身信道波长」的最小偏移（nm）。

    `detune = min_{i≠j} |λ_j + k·FSR_j − λ_i|`（k 取最近整数）。
    🔴 平台既有 `wdm_system.channel_capacity` 用「FSR > 信道跨度」作判据 —— 那是
    **充分非必要**条件；真正的必要条件是本偏移 ≫ 环线宽。M1 暴露：在 LDA DRC
    （`min_bend_R_um = 5.0`）下 FSR 上限 ≈ 18 nm，8×4.5 nm 跨度 31.5 nm 必然违反
    「FSR > 跨度」，但**梳齿规避**仍可把偏移做到 ~1.2 nm ≫ 线宽 ⇒ 隔离反而更高。
    """
    ch = [float(c) for c in channels_nm]
    from lda_agent.wdm_system import fsr_nm
    ds = []
    for i, li in enumerate(ch):
        cand = []
        for j, lj in enumerate(ch):
            if j == i:
                continue
            f = fsr_nm(lj, Rs[j], n_g)
            k = round((li - lj) / f)
            cand.append(abs(lj + k * f - li))
        ds.append(min(cand))
    return float(min(ds))


def plan_lwdm_channels(n_lanes: Optional[int] = None, spacing_nm: Optional[float] = None,
                       wl0_nm: Optional[float] = None, n_g: float = 4.2,
                       gap_um: Optional[float] = None, r_min_um: Optional[float] = None,
                       gap_scan: Optional[List[float]] = None,
                       xt_min_db: float = 15.0, il_max_db: float = 3.0
                       ) -> Dict[str, Any]:
    """LWDM 信道规划（**梳齿规避**搜索）—— 补平台短板 G-OI1 的真解（M1 新增能力）。

    在 DRC 允许的 m 范围内扫 m（以及可选 gap 列表），以「梳齿距目标信道的最小偏移」
    最大化为目标，再用 `lda_agent.wdm_system.system_metrics`（L0 add-drop 解析模型）
    **实证** 每信道 drop IL 与最坏邻道隔离 XT。返回按 (min_xt ↓, max_il ↑) 排序的解集。

    🔴 诚实边界：这是**信道规划**（几何/波长指派）能力，物理仍由既有 L0 环模型给出
    （无 FDTD 标定、无实测锚）；`min_bend_R_um` 取自 `lda_l2.drc.DEFAULT_RULES`。
    """
    from lda_agent.wdm_system import (inverse_ring_for_channel, fsr_nm,
                                      system_metrics)
    from lda_l2.drc import DEFAULT_RULES
    p = OI_M1_PROCESS
    n = p["n_lanes"] if n_lanes is None else n_lanes
    sp = p["spacing_nm"] if spacing_nm is None else spacing_nm
    w0 = p["wl0_nm"] if wl0_nm is None else wl0_nm
    g0 = p["ring_gap_um"] if gap_um is None else gap_um
    rmin = DEFAULT_RULES["min_bend_R_um"] if r_min_um is None else r_min_um
    gaps = [g0] if gap_scan is None else list(gap_scan)
    ch = [round(w0 + sp * i, 4) for i in range(n)]
    span = ch[-1] - ch[0]

    m_lo = int(math.ceil(rmin * 2.0 * math.pi * n_g / (min(ch) * 1e-3)))  # R≥r_min ⇒ m≥m_lo
    sols: List[Dict[str, Any]] = []
    for m in range(m_lo, 3 * m_lo + 1):
        Rs = [inverse_ring_for_channel(c * 1e-3, n_g, m) for c in ch]
        if min(Rs) < rmin:
            continue
        fsr_min = min(fsr_nm(c, R, n_g) for c, R in zip(ch, Rs))
        det = min_comb_detune_nm(ch, Rs, n_g)
        for g in gaps:
            mt = system_metrics(ch, Rs, g, n_g)
            mx_il, mn_xt = max(mt["il_drop_db"]), min(mt["xt_min_db"])
            if mx_il <= il_max_db and mn_xt >= xt_min_db:
                sols.append({
                    "m": m, "R_um": round(Rs[0], 4), "gap_um": float(g),
                    "min_fsr_nm": round(fsr_min, 3), "min_comb_detune_nm": round(det, 4),
                    "min_xt_db": round(mn_xt, 2), "max_il_drop_db": round(mx_il, 3),
                    "fsr_gt_span": bool(fsr_min > span),
                })
    sols.sort(key=lambda s: (-s["min_xt_db"], s["max_il_drop_db"], -s["min_comb_detune_nm"]))
    # 「FSR > 跨度」规则在 DRC 下的可达性：最大 FSR 出现在最小 m（= m_lo，R 最小）
    fsr_max = fsr_nm(min(ch), inverse_ring_for_channel(min(ch) * 1e-3, n_g, m_lo), n_g)
    return {
        "channels_nm": ch, "span_nm": round(span, 2), "n_lanes": n,
        "spacing_nm": sp, "n_g": n_g, "r_min_um": rmin,
        "m_lo": m_lo, "n_solutions": len(sols),
        "best": (sols[0] if sols else None),
        "top": sols[:8],
        "max_fsr_at_rmin_nm": round(fsr_max, 3),
        "fsr_rule_rejects_span": bool(fsr_max < span),
    }


def build_transceiver_m1(n_lanes: Optional[int] = None,
                         channels_nm: Optional[List[float]] = None) -> Any:
    """装配 800G 收发器 LinkModel（**复用** `oi_module.build_transceiver_m0`）。

    🔴 环参数取 `OI_M1_PROCESS["ring_m"] / ["ring_gap_um"]`（梳齿规避规划解），
    与 `transceiver_m1_budget` 的入参**同源**（否则闭式/级联会静默分歧）。
    """
    from lda_l2.oi_module import build_transceiver_m0
    p = OI_M1_PROCESS
    n = p["n_lanes"] if n_lanes is None else n_lanes
    if channels_nm is None:
        channels_nm = m1_channels(n)
    return build_transceiver_m0(n_lanes=n, channels_nm=channels_nm,
                                gap=p["ring_gap_um"], m=p["ring_m"])


def transceiver_m1_budget(link: Any, channels_nm: List[float],
                          baud_gbd: Optional[float] = None,
                          snr_db: Optional[float] = None,
                          d_ps_nm_km: Optional[float] = None,
                          reach_km: Optional[float] = None,
                          wl_nm: Optional[float] = None, seed: int = 0,
                          with_required_snr: bool = True) -> Dict[str, Any]:
    """M1 链路预算 = M0 功率预算 + 每信道 频域（EO S21）+ 时域（色散 / 眼 / BER）。

    · `snr_db` 缺省取 `OI_M1_PROCESS["snr_db"]`（**设计输入假设**，非实测噪声预算）。
    · 每信道额外给 **免假设** 的 `required_snr_db`（达 KP4 门限所需 SNR）与
      `sim_penalty_db`（相对 AWGN 理想所需 SNR 的差）—— 与 §3 闭式 `disp_penalty_db` **方法学独立对拍**。
    """
    from lda_l2.oi_module import transceiver_m0_budget
    p = OI_M1_PROCESS
    baud = p["baud_gbd"] if baud_gbd is None else baud_gbd
    snr = p["snr_db"] if snr_db is None else snr_db
    reach = p["reach_km"] if reach_km is None else reach_km
    dcoef = p["d_ps_nm_km"] if d_ps_nm_km is None else d_ps_nm_km
    wl_ref = p["wl_nm"] if wl_nm is None else wl_nm
    # 🔴 m / gap 必须与 `build_transceiver_m1` 同源，否则闭式(A)与级联(B)静默分歧
    m0 = transceiver_m0_budget(link, channels_nm, gap=p["ring_gap_um"], m=p["ring_m"])
    snr_ideal = ideal_required_snr_db(TARGET_BER_KP4)

    per = []
    for pc in m0["per_channel"]:
        wl = pc["channel_nm"] if wl_nm is None else wl_nm
        sim = pam4_link_sim(baud_gbd=baud, d_ps_nm_km=dcoef, L_km=reach,
                            wl_nm=wl, snr_db=snr, seed=seed + pc["lane"])
        beta2 = beta2_s2_per_m(dcoef, wl)
        t_sym = 1.0 / (baud * 1e9)
        sigma0 = p["tx_sigma_frac"] * t_sym  # 等效源脉冲 RMS（与 sim 内同源）
        dtau = dispersion_broadening_s(sigma0, beta2, reach * 1e3) - sigma0
        pen_db = dispersion_penalty_db(sigma0, beta2, reach * 1e3, baud)
        req = (required_snr_db(TARGET_BER_KP4, baud_gbd=baud, d_ps_nm_km=dcoef,
                               L_km=reach, wl_nm=wl, seed=seed + pc["lane"])
               if with_required_snr else None)
        per.append({
            "lane": pc["lane"], "channel_nm": pc["channel_nm"],
            "il_db": pc["il_b_db"], "isolation_db": pc["isolation_db"],
            "f_3db_eo_ghz": sim["f_3db_eo_ghz"],
            "eye_min_height": min(e["eye_height"] for e in sim["eyes"]),
            "q_min": sim["q_min"],
            "ber_closed": sim["ber_closed"], "ber_mc": sim["ber_mc"],
            "disp_tau_ps": dtau * 1e12, "disp_penalty_db": pen_db,
            "required_snr_db": (req["snr_db"] if req else None),
            "required_snr_reachable": (req["reachable"] if req else None),
            "sim_penalty_db": ((req["snr_db"] - snr_ideal)
                               if (req and req["reachable"]) else None),
        })
    n_lanes = len(per)
    return {
        "n_lanes": n_lanes, "channels_nm": channels_nm,
        "aggregate_gbps": n_lanes * 100.0, "baud_gbd": baud, "reach_km": reach,
        "d_ps_nm_km": dcoef, "snr_db": snr, "wl_ref_nm": wl_ref,
        "per_channel": per, "m0": m0,
        "worst_q": min(x["q_min"] for x in per),
        "worst_ber_closed": max(x["ber_closed"] for x in per),
        "worst_isolation_db": min((x["isolation_db"] for x in per), default=None),
        "b19_passivity": m0["b19_passivity"],
        "mod_lumped": modulator_bandwidth_hz(),
        "f_tia_ghz": tia_bandwidth_hz(p["r_f_ohm"], p["c_f_fF"] * 1e-15) / 1e9,
        "snr_ideal_db": snr_ideal, "target_ber": TARGET_BER_KP4,
        "driver_tia": driver_tia_cosim(n_lanes=n_lanes, baud_gbd=baud),
    }


def m1_budget_all_points(**kw: Any) -> Dict[str, Any]:
    """按 `SPEC_POINTS`（C-band 主 + O-band 对照）逐点跑 M1 链路预算。

    复用**同一** 8 通道 LinkModel 装配（`build_transceiver_m1`）—— 换波段只改
    `wl_nm` / `d_ps_nm_km` / `reach_km` 三个物理量，其余口径完全一致。
    """
    link = build_transceiver_m1()
    out: Dict[str, Any] = {}
    for sp in SPEC_POINTS:
        out[sp["key"]] = transceiver_m1_budget(
            link, m1_channels(), wl_nm=sp["wl_nm"], d_ps_nm_km=sp["d_ps_nm_km"],
            reach_km=sp["reach_km"], **kw)
        out[sp["key"]]["spec"] = dict(sp)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 6) 诚实对标（体例照 photonic_compute_benchmarks · 光子侧）
# ─────────────────────────────────────────────────────────────────────────────
PUBLIC_LANDMARKS: List[Dict[str, Any]] = [
    {"name": "800G-LR8（8×100G PAM4 · O-band · 10 km）", "family": "pluggable_optics",
     "dimension": "aggregate_rate", "value": 800.0, "unit": "Gb/s",
     "source": "IEEE 802.3ck / OIF 800G 公开规格族", "verified": False,
     "note": "架构族对齐项（8 通道并行）；**非 LDA 成就**，仅作同族维度参照。"},
    {"name": "800G-FR8（8×100G PAM4 · LWDM · 2 km）", "family": "pluggable_optics",
     "dimension": "aggregate_rate", "value": 800.0, "unit": "Gb/s",
     "source": "OIF 800G-FR8 公开规格族", "verified": False,
     "note": "LWDM 间隔族；与 M1 设计点同族（8×100G PAM4）。"},
    {"name": "单通道 100G PAM4 符号率 53.125 GBd", "family": "pluggable_optics",
     "dimension": "baud_rate", "value": 53.125, "unit": "GBd",
     "source": "IEEE 802.3ck 公开规格", "verified": False,
     "note": "M1 每通道符号率设计点来源。"},
]

LDA_CAPABILITIES: List[Dict[str, Any]] = [
    {"capability": "级联 EO S21（调制器×探测器×TIA）与 −3 dB 带宽评估",
     "level": "design_budget", "note": "闭式单极点级联（A 档）；非实测频响。"},
    {"capability": "驱动–TIA 协同预算（上升时延 UI / TIA 带宽余量）",
     "level": "design_budget", "note": "复用 eic_behavioral 行为级（无噪声/非线性）；非实测。"},
    {"capability": "光纤色散预算（β₂ 相位 + 高斯展宽闭式）",
     "level": "design_budget", "note": "SMF D 常数；非实测色散代价。"},
    {"capability": "PAM4 三眼 / Q / 链路预算级 BER 与**所需 SNR（KP4 门限）**估计",
     "level": "design_budget", "note": "闭式 Q 函数 golden；不含 SerDes/DSP/FEC/均衡/CDR。"},
    {"capability": "LWDM **梳齿规避**信道规划（环区数 m 搜索 ⇒ 最坏邻道隔离 / drop IL）",
     "level": "design_budget", "note": "几何/波长指派；物理为既有 L0 add-drop 解析模型，无 FDTD 标定。"},
]

NON_CLAIMED: List[str] = [
    "不宣称任何 TOPS / TOPS-W / fJ/op / 能效（既无功耗模型亦无实测硅）。",
    "不做数值超越比较：LDA 是设计&验证 EDA，非收发器芯片；对比仅在架构族与设计质量方法论维度。",
    "BER 为**光通道预算级**闭式估计，**非**实测误码率；不含 FEC/均衡/时钟恢复。",
    "接收 SNR 为**设计输入假设**（非实测噪声预算）；器件为 L0/L1 解析/行为模型，参数非 PDK，无实测锚。",
]

OI_M1_DISCLOSURE: Dict[str, str] = {
    "level": "A 档闭式 / 行为级（红线 §四 A 档授权同族）：EO S21 · 色散 · 眼/Q/BER 均为闭式物理律。",
    "not_redline": "不碰电-光耦合增益真值（T2 锁）· 不用 A 级商业工具 · 不流片。",
    "ber_layer": ("🔴 BER = **光链路预算级闭式估计**（golden = 闭式 Q 函数）。与 "
                  "`eic_behavioral.EIC_DISCLOSURE`（排除 **EIC 电路级** SerDes/DSP/BER）**显式分层**："
                  "本模块只含**光通道**带宽 + 色散 + 接收噪声，**不含** SerDes/DSP/FEC/均衡/CDR。"),
    "snr_is_input": ("🔴 **接收 SNR 是设计输入假设**（`OI_M1_PROCESS['snr_db']`，满幅信噪比），"
                     "**不是**实测噪声预算、也非由功率预算推出的灵敏度；无实测锚。"
                     "免该假设的指标另给 `required_snr_db`（达 KP4 门限所需 SNR）与"
                     "`sim_penalty_db`（相对 AWGN 理想的代价）。"),
    "no_energy": "🔴 **零能效数字**：不报 TOPS / TOPS-W / fJ/op。",
    "verdict": "恒 `DESIGN_BUDGET`；非流片实测、非实测签核。",
    "params": "参数为公开文献典型量级占位（非 PDK）；器件 L0/L1，无实测锚。",
}


def honest_boundary_ok() -> bool:
    """护栏：**能力宣称面**（`LDA_CAPABILITIES` + `PUBLIC_LANDMARKS`）不得含任何能效/TOPS 字样。

    体例照 ecore `scale_bench.honest_boundary_ok`：只守「**能力宣称**」面；
    `NON_CLAIMED` / `OI_M1_DISCLOSURE` 是**否定语境**（「不宣称任何 …」「不报 …」）⇒ 不参与本判据
    （否则正确的自我否定会被误判成违规 —— E12/E13/E17 血案同族）。
    突变探针 = 向 `LDA_CAPABILITIES` 注入 fabricated 指标（如 "76 TOPS/W"）⇒ 本判据必红。
    """
    blob = repr(LDA_CAPABILITIES) + repr(PUBLIC_LANDMARKS)
    for tok in ("TOPS", "TOPS-W", "TOPS/W", "fJ/op", "pJ/bit", "W/op"):
        if tok in blob:
            return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# 7) 自检
# ─────────────────────────────────────────────────────────────────────────────
def oi_m1_self_check(verbose: bool = True) -> Dict[str, Any]:
    checks: List[Tuple[str, bool]] = []
    # 1) 一阶单极点：f_3dB 处幅值 1/√2
    checks.append(("单极点 f_3dB 处 |H|=1/√2",
                   abs(first_order_mag(1e9, 1e9) - 1 / math.sqrt(2)) < 1e-12))
    # 2) 级联 f_3dB 退化：仅一个极点 ⇒ ≡ 极点频率
    f0 = 45e9
    checks.append(("级联 EO S21 单极点退化 (f_3dB≡fᵢ)",
                   abs(eo_s21_f3db_hz(f0, 1e18, 1e18) - f0) / f0 < 1e-3))
    # 3) 色散：D=0 ⇒ σ₁=σ₀
    s0 = 0.25 / (53.125e9)
    checks.append(("D=0 ⇒ 无展宽 σ₁=σ₀",
                   abs(dispersion_broadening_s(s0, 0.0, 2e3) - s0) < 1e-30))
    # 4) 色散单调：L↑ ⇒ σ₁↑
    b2 = beta2_s2_per_m(17.0, 1550.0)
    checks.append(("色散 σ₁ 随 L 单调增",
                   dispersion_broadening_s(s0, b2, 1e4)
                   > dispersion_broadening_s(s0, b2, 1e3)))
    # 5) PAM4 golden：平坦信道（无 ISI）BER_closed ≈ BER_mc
    g = pam4_link_sim(flatten_channel=True, no_dispersion=True, snr_db=20.0,
                      n_sym=8192, seed=1)
    rel = abs(g["ber_closed"] - g["ber_mc"]) / max(g["ber_closed"], 1e-12)
    checks.append((f"PAM4 平坦 BER_closed ≈ BER_mc（rel {rel:.2%}）", rel < 0.25))
    # 6) 眼高（平坦）≈ 电平间距 2
    checks.append(("平坦信道眼高 ≈ 2（电平间距）",
                   all(abs(e["eye_height"] - 2.0) < 0.1 for e in g["eyes"])))
    # 7) golden 对拍：平坦信道的「所需 SNR」⟷ 闭式解析（两法独立）
    req_flat = required_snr_db(TARGET_BER_KP4, flatten_channel=True,
                               no_dispersion=True, seed=1)
    d_snr = abs(req_flat["snr_db"] - ideal_required_snr_db(TARGET_BER_KP4))
    checks.append((f"所需SNR: 仿真⟷闭式 一致（Δ {d_snr:.3f} dB）", d_snr < 0.3))
    # 8) 驱动–TIA 协同：闭式 ⟷ RK4 + 上升 UI + TIA 余量
    dt_ = driver_tia_cosim()
    checks.append(("驱动 t90: 闭式⟷RK4 一致（rel<1e-3）",
                   dt_["t90_abs_diff_s"] is not None
                   and dt_["t90_abs_diff_s"] / dt_["t90_closed_form_s"] < 1e-3))
    checks.append((f"驱动上升 {dt_['rise_10_90_ui']:.2f} UI <0.5 且 TIA "
                   f"{dt_['tia_over_nyquist']:.2f}×Nyquist",
                   dt_["driver_fast_enough"] and dt_["tia_wide_enough"]))
    # 9) 梳齿规避规划：搜索解 ⟷ 设计常量 一致（防常量漂移）
    plan = plan_lwdm_channels()
    bp = plan["best"] or {}
    checks.append((f"信道规划: 搜索解 m={bp.get('m')} gap={bp.get('gap_um')} "
                   f"⟷ 常量 m={OI_M1_PROCESS['ring_m']} "
                   f"gap={OI_M1_PROCESS['ring_gap_um']}",
                   bool(bp) and bp.get("m") == OI_M1_PROCESS["ring_m"]
                   and abs(bp.get("gap_um", -1) - OI_M1_PROCESS["ring_gap_um"]) < 1e-9))
    # 10) 梳齿规避**有效**（对 M0 默认 m=170/gap=0.30 的 8 信道必红 —— 探针先证能变红）
    from lda_l2.oi_module import build_transceiver_m0, transceiver_m0_budget
    ch8 = m1_channels(8)
    link_pre = build_transceiver_m0(n_lanes=8, channels_nm=ch8, gap=0.30, m=170)
    iso_pre = min(pc["isolation_db"]
                  for pc in transceiver_m0_budget(link_pre, ch8, gap=0.30,
                                                  m=170)["per_channel"])
    checks.append((f"规划有效: M1 minXT {bp.get('min_xt_db')}dB ≥15 且 "
                   f"M0默认 {iso_pre:.1f}dB <15（探针能变红）",
                   bool(bp) and bp.get("min_xt_db", 0) >= 15.0 and iso_pre < 15.0))
    checks.append(("单 FSR 规则会拒该跨度（暴露平台旧判据过保守）",
                   bool(plan["fsr_rule_rejects_span"])))
    # 11) B19 无源无增益 + 800G 聚合 + 隔离达标
    link = build_transceiver_m1()
    rep = transceiver_m1_budget(link, ch8)
    checks.append(("B19 无源无增益 |T|≤1（8 通道）", rep["b19_passivity"]))
    checks.append(("800G 聚合 = 8×100G", rep["aggregate_gbps"] == 800.0))
    checks.append((f"8 通道隔离 ≥ 15 dB（实际 {rep['worst_isolation_db']:.1f} dB）",
                   rep["worst_isolation_db"] >= 15.0))
    checks.append(("近端预算: 闭式≡级联（≤0.05 dB）",
                   all(pc["il_ab_diff_db"] <= 0.05
                       for pc in rep["m0"]["per_channel"])))
    # 12) 设计点结论（C-band 主 + O-band 对照）· 两法同向
    pts = m1_budget_all_points(seed=0)
    c2, c10, o2 = pts["C_2km"], pts["C_10km"], pts["O_2km"]
    p_c2 = c2["per_channel"][0]["disp_penalty_db"]
    p_c10 = c10["per_channel"][0]["disp_penalty_db"]
    p_o2 = o2["per_channel"][0]["disp_penalty_db"]
    checks.append((f"C_2km 代价 {p_c2:.2f}dB <1.5 且 sim 代价 "
                   f"{c2['per_channel'][0]['sim_penalty_db']:.2f}dB <1.5（两法同向）",
                   p_c2 < 1.5 and (c2["per_channel"][0]["sim_penalty_db"] or 0) < 1.5))
    checks.append((f"C_10km: 闭式代价 {p_c10:.2f}dB >6 且 sim 所需SNR 不可达（两法同向）",
                   p_c10 > 6.0
                   and c10["per_channel"][0]["required_snr_reachable"] is False))
    checks.append((f"O_2km/O_10km 闭式代价 ≡0（{p_o2:.2f}dB）",
                   abs(p_o2) < 1e-9
                   and abs(pts["O_10km"]["per_channel"][0]["disp_penalty_db"]) < 1e-9))
    # 13) 诚实护栏
    checks.append(("诚实护栏无 TOPS/能效字样", honest_boundary_ok()))
    ok = all(v for _, v in checks)
    if verbose:
        print("=== OI M1 自检 ===")
        for name, v in checks:
            print(f"  [{'PASS' if v else 'FAIL'}] {name}")
        print(f"  8×C-band 2km: f_3dB(EO)={rep['per_channel'][0]['f_3db_eo_ghz']:.2f}GHz "
              f"worstQ={rep['worst_q']:.2f} worstBER={rep['worst_ber_closed']:.2e} "
              f"隔离≥{rep['worst_isolation_db']:.1f}dB 聚合={rep['aggregate_gbps']:.0f}Gb/s")
        for k in ("C_2km", "C_10km", "O_2km"):
            pc = pts[k]["per_channel"][0]
            rs = pc["required_snr_db"]
            sp_ = pc["sim_penalty_db"]
            print(f"  {k:7s} λ={pts[k]['wl_ref_nm']:.0f}nm L={pts[k]['reach_km']}km: "
                  f"Q={pts[k]['worst_q']:.2f} BER={pts[k]['worst_ber_closed']:.2e} "
                  f"色散代价(闭式)={pc['disp_penalty_db']:.2f}dB "
                  f"所需SNR={('不可达' if not pc['required_snr_reachable'] else f'{rs:.2f}dB')}"
                  f" sim代价={('—' if sp_ is None else f'{sp_:.2f}dB')}")
    return {"ok": ok, "checks": checks, "report": rep, "spec_points": pts}


if __name__ == "__main__":
    r = oi_m1_self_check()
    raise SystemExit(0 if r["ok"] else 1)
