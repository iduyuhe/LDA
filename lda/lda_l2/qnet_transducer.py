# -*- coding: utf-8 -*-
"""J5 量子网络与接口征程 · **M3 能力层：微波-光换能器**（`qnet_transducer`）。

定位：M0（`qnet_channel` + `qnet_distribution`）解决**分发侧**、M1（`qnet_source`）解决**源侧**、
      M2（`qnet_repeater`）解决**中继侧**；本层解决**跨频段接口**——把**微波**（超导量子处理器
      的工作频段）与**光**（光纤网络的传输频段）接起来，即「**跨频段转换效率 η 有多高**」
      （缺口 **G-QNET-4**）。没有这一环，量子处理器再强也出不了机房。

物理链（三因子 · 与数值核 B522 同律）：
  ① 协同度          `C = 4G²/(κ_mw·γ_mech)`（**复用 `lda_l2.qs_m3c.cooperativity_from_g`**）
  ② 协同度极限效率  `η_peak = 4C/(1+C)²`（阻抗匹配最优档 · C=1 时达 1）
  ③ 有限探测带侧带重叠  `η_band = N(Ω_c)/D`（**硬件带宽受限** ⇒ 只有带内侧带被接收）
     `L_x(ω)=γ/((ω−ω_x)²+γ²)` · 微波腔中心 −Δ / 光腔中心 +Δ / 同半宽 γ
     `N(Ω)=∫_{−Ω}^{Ω}L_aL_b dω` · `D=∫_{−∞}^{∞}L_aL_b dω`
  ⇒ `η_total = η_peak · η_band`

🔴 **本层用「复留数 + 复对数」闭式**（`_band_overlap_residue`），而数值核 B522 用
  **「分层 log+arctan」闭式**（两个 4×4 幂次匹配系数）——**两条独立推导**在自检里逐位对拍
  （相对差 < 1e-12）⇒ 互证而非重复实现。

🔴 **净增 0 登记（如实 · 章程 §5 硬纪律②预警的「跨量级」族）**：**换能专属噪声光子数**
  `n_add = (1−η)/(2η)`（量子极限 · 「半量子」项）是**纯代数式**（无离散化误差）⇒ 判据 D 不成立
  ⇒ **不立锚**，只作能力层。🔴 **与 B514 的避让**：B514 = **分布式放大链**附加噪声 Caves 极限
  `(η/g)(1−e^{−gL})`（**级联/行波**构型 · 含长度积分）；本条是**单节点换能器**的量子极限
  `(1−η)/(2η)`（无长度积分 · 不同构型/不同标量）⇒ 不重复计数。

🔴 **诚实边界**：G / κ_mw / γ_mech / γ / Δ / Ω_c 为**设计示例量级**（非任何实测换能器件）；
  只建模**两洛伦兹响应 × 有限探测带**这一最小骨架（未含机械模热噪声谱、多模复用、脉冲泵浦
  时序、非线性饱和、双向同时工作、暗计数）⇒ 只支撑预算与量级，**不作制造/性能宣称**。
  零商业依赖（纯 `math` + `cmath`；零 RNG）；**LLM 不进判决路径**。
"""

from __future__ import annotations

import cmath
import math
from typing import Dict

__all__ = [
    "QNET_TRANSDUCER_CALIBER",
    "DEFAULT_G_RAD_S",
    "DEFAULT_KAPPA_MW_RAD_S",
    "DEFAULT_GAMMA_MECH_RAD_S",
    "DEFAULT_HALFWIDTH_RAD_S",
    "DEFAULT_DETUNING_HALF_RAD_S",
    "DEFAULT_BAND_HALF_RAD_S",
    "cooperativity",
    "peak_efficiency",
    "band_overlap",
    "transducer_efficiency",
    "added_noise_photons",
    "transducer_report",
    "selfcheck_qnet_transducer",
]

QNET_TRANSDUCER_CALIBER = "microwave_optical_transduction_efficiency__unitless"

_TWO_PI = 2.0 * math.pi

#: 耦合 G（rad/s · 2π×5 MHz）
DEFAULT_G_RAD_S = _TWO_PI * 5.0e6
#: 微波腔衰减 κ_mw（rad/s · 2π×2 MHz）
DEFAULT_KAPPA_MW_RAD_S = _TWO_PI * 2.0e6
#: 机械模衰减 γ_mech（rad/s · 2π×2 MHz）
DEFAULT_GAMMA_MECH_RAD_S = _TWO_PI * 2.0e6
#: 两腔洛伦兹半宽 γ（rad/s · 2π×1 MHz）
DEFAULT_HALFWIDTH_RAD_S = _TWO_PI * 1.0e6
#: 半失配 Δ（rad/s · 2π×10 MHz）
DEFAULT_DETUNING_HALF_RAD_S = _TWO_PI * 10.0e6
#: 探测带半宽 Ω_c（rad/s · 2π×5 MHz）
DEFAULT_BAND_HALF_RAD_S = _TWO_PI * 5.0e6


def cooperativity(g_coupling: float = DEFAULT_G_RAD_S,
                  kappa_mw: float = DEFAULT_KAPPA_MW_RAD_S,
                  gamma_mech: float = DEFAULT_GAMMA_MECH_RAD_S) -> float:
    """① 协同度 `C = 4G²/(κ_mw·γ_mech)` —— **复用 `qs_m3c.cooperativity_from_g`**（同律）。"""
    for nm, v in (("G", g_coupling), ("κ_mw", kappa_mw), ("γ_mech", gamma_mech)):
        if not float(v) > 0.0:
            raise ValueError("%s 须 > 0" % nm)
    from lda_l2.qs_m3c import cooperativity_from_g
    return float(cooperativity_from_g(float(g_coupling), float(kappa_mw),
                                      float(gamma_mech)))


def peak_efficiency(c_val: float) -> float:
    """② 协同度极限效率 `η_peak = 4C/(1+C)²`（C=1 ⇒ 1；C→0/∞ ⇒ 0）。"""
    c = float(c_val)
    if c <= 0.0:
        raise ValueError("协同度 C 须 > 0")
    return float(4.0 * c / (1.0 + c) ** 2)


def _band_overlap_residue(band_half: float, detuning_half: float,
                          halfwidth: float) -> float:
    """③a `N(Ω)=∫_{−Ω}^{Ω}L_aL_b dω` —— **复留数 + 复对数**（共轭对虚部精确相消）。"""
    a, b, g = -float(detuning_half), float(detuning_half), float(halfwidth)
    poles = [complex(a, g), complex(a, -g), complex(b, g), complex(b, -g)]
    tot = 0.0 + 0.0j
    for i, z in enumerate(poles):
        den = 1.0 + 0.0j
        for j, z2 in enumerate(poles):
            if i != j:
                den *= (z - z2)
        tot += (1.0 / den) * (cmath.log(band_half - z) - cmath.log(-band_half - z))
    return float((g * g * tot).real)


def _full_overlap(detuning_half: float, halfwidth: float) -> float:
    """③b `D=∫_{−∞}^{∞}L_aL_b dω = π[γb/R_a + γa/R_b]`（对称档 ⇒ `πγ/(2(Δ²+γ²))`）。"""
    d, g = float(detuning_half), float(halfwidth)
    ra = complex(-2.0 * d, g) ** 2 + g ** 2
    rb = complex(2.0 * d, g) ** 2 + g ** 2
    return float((math.pi * (g / ra + g / rb)).real)


def band_overlap(band_half: float = DEFAULT_BAND_HALF_RAD_S,
                 detuning_half: float = DEFAULT_DETUNING_HALF_RAD_S,
                 halfwidth: float = DEFAULT_HALFWIDTH_RAD_S) -> float:
    """③ 归一化侧带重叠 `η_band = N(Ω_c)/D ∈ (0, 1]`（Ω_c→∞ ⇒ 1；Ω_c→0 ⇒ 0）。"""
    for nm, v in (("Ω_c", band_half), ("Δ", detuning_half), ("γ", halfwidth)):
        if not float(v) > 0.0:
            raise ValueError("%s 须 > 0" % nm)
    return float(_band_overlap_residue(band_half, detuning_half, halfwidth)
                 / _full_overlap(detuning_half, halfwidth))


def transducer_efficiency(g_coupling: float = DEFAULT_G_RAD_S,
                          kappa_mw: float = DEFAULT_KAPPA_MW_RAD_S,
                          gamma_mech: float = DEFAULT_GAMMA_MECH_RAD_S,
                          halfwidth: float = DEFAULT_HALFWIDTH_RAD_S,
                          detuning_half: float = DEFAULT_DETUNING_HALF_RAD_S,
                          band_half: float = DEFAULT_BAND_HALF_RAD_S) -> float:
    """换能效率 `η = η_peak(C)·η_band(Ω_c; Δ, γ)`（与数值核 B522 golden **同律**）。"""
    c_val = cooperativity(g_coupling, kappa_mw, gamma_mech)
    return float(peak_efficiency(c_val)
                 * band_overlap(band_half, detuning_half, halfwidth))


def added_noise_photons(eta: float) -> float:
    """换能专属噪声（量子极限「半量子」项）`n_add = (1−η)/(2η)`（**纯代数 ⇒ 不立锚**）。

    🔴 **与 B514 的避让**：B514 是**分布式放大链** Caves 极限 `(η/g)(1−e^{−gL})`（级联构型 ·
    含长度积分）；本条是**单节点换能器**量子极限（无长度积分）⇒ 构型与标量均不同。
    """
    e = float(eta)
    if not 0.0 < e <= 1.0:
        raise ValueError("转换效率 η 须落在 (0, 1]")
    return float((1.0 - e) / (2.0 * e))


def transducer_report() -> Dict[str, float]:
    """换能能力层报告（三因子一次给全 · 零重计算）。"""
    c_val = cooperativity()
    eta_peak = peak_efficiency(c_val)
    eta_band = band_overlap()
    eta = eta_peak * eta_band
    return {
        "cooperativity": float(c_val),
        "peak_efficiency": float(eta_peak),
        "band_overlap": float(eta_band),
        "efficiency": float(eta),
        "added_noise_photons": added_noise_photons(eta),
        "detuning_over_halfwidth": float(DEFAULT_DETUNING_HALF_RAD_S
                                         / DEFAULT_HALFWIDTH_RAD_S),
        "band_over_halfwidth": float(DEFAULT_BAND_HALF_RAD_S / DEFAULT_HALFWIDTH_RAD_S),
        "caliber": QNET_TRANSDUCER_CALIBER,
    }


def selfcheck_qnet_transducer() -> Dict[str, bool]:
    """换能能力层自检（含与 `qs_m3c` 逐位对拍 · 与数值核 B522 跨模块互证）。"""
    checks: Dict[str, bool] = {}
    r = transducer_report()

    # ① 协同度：与 qs_m3c 同律（逐位）
    try:
        from lda_l2.qs_m3c import cooperativity_from_g
        checks["cooperativity_matches_qs_m3c"] = bool(
            abs(cooperativity() - cooperativity_from_g(DEFAULT_G_RAD_S,
                                                      DEFAULT_KAPPA_MW_RAD_S,
                                                      DEFAULT_GAMMA_MECH_RAD_S)) < 1e-15)
    except Exception:
        checks["cooperativity_matches_qs_m3c"] = False

    # ② η_peak 极限与极值
    checks["peak_efficiency_at_c1_is_unity"] = bool(abs(peak_efficiency(1.0) - 1.0) < 1e-15)
    checks["peak_efficiency_le_one"] = bool(r["peak_efficiency"] <= 1.0)
    checks["peak_efficiency_monotone_up_then_down"] = bool(
        peak_efficiency(0.1) < peak_efficiency(1.0) > peak_efficiency(100.0))

    # ③ η_band 极限与单调性
    checks["band_overlap_in_unit_interval"] = bool(0.0 < r["band_overlap"] <= 1.0)
    checks["band_overlap_to_one_at_wide_band"] = bool(
        abs(band_overlap(DEFAULT_HALFWIDTH_RAD_S * 1.0e5) - 1.0) < 1e-6)
    checks["band_overlap_monotone_in_band"] = bool(
        band_overlap(DEFAULT_BAND_HALF_RAD_S * 0.5) < r["band_overlap"]
        < band_overlap(DEFAULT_BAND_HALF_RAD_S * 2.0))
    checks["band_overlap_decreasing_in_detuning"] = bool(
        band_overlap(detuning_half=DEFAULT_DETUNING_HALF_RAD_S * 0.5)
        > r["band_overlap"]
        > band_overlap(detuning_half=DEFAULT_DETUNING_HALF_RAD_S * 2.0))

    # ④ 三因子合成自洽
    checks["efficiency_equals_product"] = bool(
        abs(r["efficiency"] - r["peak_efficiency"] * r["band_overlap"]) < 1e-18)

    # ⑤ 跨模块互证：本层复留数式 ≡ 数值核 B522 的 log+arctan 式（相对差 < 1e-12）
    try:
        from lda_harness import _batch_j5_numeric as J5
        g521 = J5.golden_b522()
        rel = abs(transducer_efficiency() - g521) / max(abs(g521), 1e-300)
        checks["matches_b522_golden_rel_lt_1e-12"] = bool(rel < 1e-12)
        checks["matches_b522_default_params"] = bool(
            abs(J5.B522_DEFAULT_PARAMS["band_half_rad_s"] - DEFAULT_BAND_HALF_RAD_S) < 1e-3)
    except Exception:
        checks["matches_b522_golden_rel_lt_1e-12"] = False
        checks["matches_b522_default_params"] = False

    # ⑥ 换能专属噪声（纯代数 · 不立锚）性质
    checks["added_noise_positive_and_decreasing"] = bool(
        added_noise_photons(0.01) > added_noise_photons(0.5) > added_noise_photons(1.0) >= 0.0)
    checks["added_noise_at_unity_is_zero"] = bool(abs(added_noise_photons(1.0)) < 1e-15)

    # 反向探针：非法入参必抛
    def _raises(fn):
        try:
            fn()
        except ValueError:
            return True
        return False

    checks["reverse_bad_cooperativity_raise"] = bool(_raises(lambda: cooperativity(0.0)))
    checks["reverse_bad_band_raise"] = bool(_raises(lambda: band_overlap(0.0)))
    checks["reverse_bad_eta_raise"] = bool(_raises(lambda: added_noise_photons(0.0)))
    return checks


def main() -> int:  # pragma: no cover
    checks = selfcheck_qnet_transducer()
    bad = [k for k, v in checks.items() if not v]
    for k, v in checks.items():
        print("  [%s] %s" % ("PASS" if v else "FAIL", k))
    r = transducer_report()
    print("\nC = %.12e  η_peak = %.12e  η_band = %.12e  η = %.12e"
          % (r["cooperativity"], r["peak_efficiency"], r["band_overlap"], r["efficiency"]))
    print("n_add = %.6e  ·  Δ/γ = %.1f  ·  Ω_c/γ = %.1f"
          % (r["added_noise_photons"], r["detuning_over_halfwidth"],
             r["band_over_halfwidth"]))
    print("自检：%s（FAIL=%s）" % ("ALL PASS" if not bad else "FAIL", bad or "无"))
    return 0 if not bad else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
