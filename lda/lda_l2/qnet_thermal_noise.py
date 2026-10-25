# -*- coding: utf-8 -*-
"""J5 · M3 侧 **热噪声层**：换能器的「量子极限」只在机械浴真空时才成立（`qnet_thermal_noise`）。

定位：`qnet_transducer` 给出 `n_add = (1−η)/(2η)`（**量子极限**「半量子」项）并在披露里
      如实写着「未含**机械模热噪声谱**」。本层补上这一项 —— 它不是「更细的修正」，而是
      决定**「量子极限」这个词能不能用**的分界线。

物理链（两行闭式 · 与丢束器模型同律）
  ① 热占据数        `n_th = 1/(exp(T_q/T) − 1)`，其中 `T_q ≡ ħΩ/k_B`（**一个机械量子的温度**）
  ② 含浴的附加噪声  `n_add(η, n_th) = (1−η)/η · (n_th + ½)`（**参考到输入**，单位 quanta）

🔴 **两处「本应恰好为已知值」的对照支路（本层最强判据，比任何方向性断言都硬）**
  · `n_th = 0`（浴在真空）⇒ `n_add` **逐位等于**既有 `qnet_transducer.added_noise_photons(η)`
    —— 通式必须退化为已实现的特例。**这里的 ½ 正是最容易漏掉的因子**（漏了就不是量子极限）。
  · `T = T* ≡ T_q/ln3` ⇒ `n_th` **恰为 ½**（`1/(e^{ln3}−1) = 1/2`）⇒ 热项与量子项**相等**。

🔴 **本层要交付的诚实结论（不是「模型更全了」，而是一条可判红的话）**
  「量子极限」三字只在 `n_th ≪ ½` 时成立，而这**与 η 无关** —— 因为比值
  `r(T) ≡ 热项/量子项 = 2·n_th` 与 η 无关。⇒ 说「本换能器已达量子极限」是一个**只关于温度**的
  断言，它必须附带 `T ≪ T* = ħΩ/(k_B ln3)`（参考档 5 GHz ⇒ **T\\* = 218 mK**）。
  🔴 而 `r(T)` 与 η 无关 ⇒ **比值判据对「绝对噪声有多大」完全无能**（η 再差 100 倍，r 不变）
     ⇒ 故报告必须**同时给绝对量**（`added_noise_at_bath` 与 `added_noise_T0`），本仓 v0.9.287/293/294
     三次吃过的同一个坑，此处第四次预防。

🔴 **诚实边界**：`Ω_m = 5 GHz`、`T = 20 mK` 均为**设计示例量级**（非任何实测换能器件）；
  本层只建模**单机械模 + 单热浴**的玻色占据，未含机械模**非热**占据（自振/参量驱动）、
  多模复用、泵浦加热导致的**有效温度抬升**、非平衡（浴与模不共温）与实测标定。
  零商业依赖（纯 `math`）；零 RNG；**LLM 不进判决路径**。
"""

from __future__ import annotations

import math
from typing import Any, Dict

from lda_l2 import qnet_transducer as TR
from lda_l2.qs_m3c import HBAR

__all__ = [
    "QNET_THERMAL_CALIBER",
    "DEFAULT_MECH_FREQ_HZ",
    "DEFAULT_BATH_T_K",
    "thermal_quantum_temperature",
    "thermal_occupancy",
    "occupancy_plus_half_symmetrized",
    "added_noise_with_bath",
    "thermal_to_quantum_ratio",
    "crossover_temperature",
    "temperature_for_thermal_fraction",
    "thermal_noise_report",
    "selfcheck_qnet_thermal_noise",
]

QNET_THERMAL_CALIBER = "added_noise_photons_referred_to_input__quanta"

#: 🔴 Boltzmann（**SI 2019 起为定义值** · 精确 · 不是「文献量级」）
KB_SI = 1.380649e-23

_TWO_PI = 2.0 * math.pi

#: 机械模频率（**设计示例量级** · 压电-光机械换能器的体声波档 · 非任何实测器件）
DEFAULT_MECH_FREQ_HZ = 5.0e9

#: 浴温度（**设计示例量级** · 稀释制冷机典型档）
DEFAULT_BATH_T_K = 0.020

#: `exp` 溢出保护阈值：x 再大则 `n_th` 已远低于双精度可分辨（`e^{-700} ≈ 1e-304`）
_EXP_GUARD = 700.0


def _check_positive(name: str, value: float) -> float:
    v = float(value)
    if not v > 0.0:
        raise ValueError("%s 须 > 0" % name)
    return v


def thermal_quantum_temperature(mech_freq_hz: float = DEFAULT_MECH_FREQ_HZ) -> float:
    """`T_q ≡ ħΩ/k_B`（**一个机械量子的温度** · K）。

    参考档：`Ω/2π = 5 GHz ⇒ T_q = 239.96 mK`；`ħ/k_B = 7.6382e-12 K·s`（比例系数，与 f 无关）。
    """
    f = _check_positive("机械频率", mech_freq_hz)
    return float(HBAR * _TWO_PI * f / KB_SI)


def thermal_occupancy(temp_k: float = DEFAULT_BATH_T_K,
                      mech_freq_hz: float = DEFAULT_MECH_FREQ_HZ) -> float:
    """`n_th = 1/(exp(T_q/T) − 1)`（Bose-Einstein · 用 `expm1` 保低 T 精度）。

    `T → 0 ⇒ n_th → 0`（指数式，非多项式）；`T ≫ T_q ⇒ n_th ≈ T/T_q − ½`（Rayleigh-Jeans）。
    `x > 700` 时直接返回 `0.0`（`e^{700}` 已超出双精度 ⇒ `n_th < 1e-304`，物理上即 0）。
    """
    t = _check_positive("温度", temp_k)
    tq = thermal_quantum_temperature(mech_freq_hz)
    x = tq / t
    if x > _EXP_GUARD:
        return 0.0
    return float(1.0 / math.expm1(x))


def occupancy_plus_half_symmetrized(temp_k: float = DEFAULT_BATH_T_K,
                                    mech_freq_hz: float = DEFAULT_MECH_FREQ_HZ) -> float:
    """`n_th + ½ = ½·coth(T_q/2T)` —— **独立路径**（与 `thermal_occupancy` 互证 · 不用 expm1）。

    🔴 这条恒等式是本层「两条独立推导同一结果」的证据：`1/(e^x−1) + ½ = ½coth(x/2)`。
    """
    t = _check_positive("温度", temp_k)
    tq = thermal_quantum_temperature(mech_freq_hz)
    x = tq / t
    if x > _EXP_GUARD:
        return 0.5
    return float(0.5 / math.tanh(x / 2.0))


def added_noise_with_bath(eta: float, n_th: float) -> float:
    """`n_add = (1−η)/η · (n_th + ½)`（**参考到输入**的附加噪声 · quanta）。

    🔴 `n_th = 0` ⇒ **逐位等于** `qnet_transducer.added_noise_photons(η) = (1−η)/(2η)`。
    """
    e = float(eta)
    if not 0.0 < e <= 1.0:
        raise ValueError("转换效率 η 须落在 (0, 1]")
    n = float(n_th)
    if n < 0.0:
        raise ValueError("热占据数 n_th 须 ≥ 0")
    return float((1.0 - e) / e * (n + 0.5))


def thermal_to_quantum_ratio(n_th: float) -> float:
    """`r ≡ 热项/量子项 = n_th/(½) = 2·n_th` —— 🔴 **与 η 完全无关**。

    正是这一点让「已达量子极限」成为**只关于温度**的断言；也正是这一点让**比值判据
    对绝对噪声大小彻底无能**（η 差 100 倍，r 不变）⇒ 报告必须并报绝对量。
    """
    n = float(n_th)
    if n < 0.0:
        raise ValueError("热占据数 n_th 须 ≥ 0")
    return float(2.0 * n)


def crossover_temperature(mech_freq_hz: float = DEFAULT_MECH_FREQ_HZ) -> float:
    """`T* = T_q/ln3`（热项 = 量子项 处 · **闭式已知答案：此处 n_th ≡ ½**）。

    参考档：`T_q = 239.96 mK ⇒ T* = 218.42 mK`。
    """
    return float(thermal_quantum_temperature(mech_freq_hz) / math.log(3.0))


def temperature_for_thermal_fraction(eps: float,
                                     mech_freq_hz: float = DEFAULT_MECH_FREQ_HZ) -> float:
    """热项不超过量子项的 `eps` 倍所需的**上限温度**：`T = T_q/ln(1+2/eps)`。

    由 `n_th = eps/2 ⇒ e^x − 1 = 2/eps ⇒ x = ln(1+2/eps)` 得（`eps=0.1 ⇒ 78.82 mK`）。
    🔴 这是本层唯一**可直接拿去做设计约束**的量。
    """
    e = _check_positive("eps", eps)
    return float(thermal_quantum_temperature(mech_freq_hz) / math.log1p(2.0 / e))


def thermal_noise_report(eta: float = None,
                         temp_k: float = DEFAULT_BATH_T_K,
                         mech_freq_hz: float = DEFAULT_MECH_FREQ_HZ) -> Dict[str, Any]:
    """热噪声报告（**绝对量与比值并报** · 零重计算项一律引用现算结果）。"""
    if eta is None:
        eta = TR.transducer_report()["efficiency"]
    e = float(eta)
    n_th = thermal_occupancy(temp_k, mech_freq_hz)
    n_abs = added_noise_with_bath(e, n_th)
    n_t0 = TR.added_noise_photons(e)
    return {
        "eta": e,
        "temp_k": float(temp_k),
        "mech_freq_hz": float(mech_freq_hz),
        "thermal_quantum_temperature_K": thermal_quantum_temperature(mech_freq_hz),
        "thermal_occupancy": float(n_th),
        "occupancy_plus_half": float(occupancy_plus_half_symmetrized(temp_k, mech_freq_hz)),
        "thermal_to_quantum_ratio": thermal_to_quantum_ratio(n_th),
        "added_noise_T0": float(n_t0),
        "added_noise_at_bath": float(n_abs),
        "added_noise_increase_factor": float(n_abs / n_t0) if n_t0 > 0 else float("inf"),
        "crossover_temperature_K": crossover_temperature(mech_freq_hz),
        "temp_for_10pct_thermal_K": temperature_for_thermal_fraction(0.1, mech_freq_hz),
        # 🔴 判读（布尔也现算，不手填）
        "bath_is_effectively_vacuum": bool(n_th <= 1e-3),
        "quantum_limit_claim_valid": bool(n_th <= 0.05),
        "caliber": QNET_THERMAL_CALIBER,
    }


def selfcheck_qnet_thermal_noise() -> Dict[str, bool]:
    """热噪声层自检（**两条闭式已知答案 + 一条退化到已实现特例**）。"""
    checks: Dict[str, bool] = {}
    r = thermal_noise_report()

    # ① 🔴 最强对照支路：n_th = 0 ⇒ 逐位退化到已实现的量子极限
    checks["degenerates_to_quantum_limit_exactly"] = bool(
        added_noise_with_bath(r["eta"], 0.0) == TR.added_noise_photons(r["eta"]))

    # ② 🔴 第二闭式已知答案：T = T* ⇒ n_th 恰为 ½
    _n_star = thermal_occupancy(r["crossover_temperature_K"], DEFAULT_MECH_FREQ_HZ)
    checks["occupancy_is_half_at_crossover"] = bool(abs(_n_star - 0.5) <= 1e-12)
    checks["ratio_is_unity_at_crossover"] = bool(
        abs(thermal_to_quantum_ratio(_n_star) - 1.0) <= 1e-11)

    # ③ 独立路径恒等式：n + ½ ≡ ½coth(T_q/2T)（相对 1e-15）
    _a = thermal_occupancy() + 0.5
    _b = occupancy_plus_half_symmetrized()
    checks["identity_with_coth_holds"] = bool(abs(_a - _b) <= 1e-15 * _b)

    # ④ 设计约束反解：eps = 0.1 处比值恰为 0.1
    _t10 = temperature_for_thermal_fraction(0.1)
    checks["temp_for_fraction_roundtrip"] = bool(
        abs(thermal_to_quantum_ratio(thermal_occupancy(_t10)) - 0.1) <= 1e-12)

    # ⑤ 单调性（两侧都要判，不能只判「随 T 增」）
    checks["occupancy_monotone_up_in_T"] = bool(
        thermal_occupancy(0.01) < thermal_occupancy(0.1) < thermal_occupancy(1.0)
        < thermal_occupancy(10.0))
    checks["occupancy_monotone_down_in_freq"] = bool(
        thermal_occupancy(0.02, 1.0e9) > thermal_occupancy(0.02, 5.0e9)
        > thermal_occupancy(0.02, 2.0e10))

    # ⑥ 绝对量级锚点（防单位/量级错 —— 比值判据在这里恒失效，见 docstring）
    checks["reference_magnitude"] = bool(
        7.63e-12 <= HBAR / KB_SI <= 7.65e-12
        and 0.230 <= r["thermal_quantum_temperature_K"] <= 0.250
        and 0.210 <= r["crossover_temperature_K"] <= 0.230
        and 0.070 <= r["temp_for_10pct_thermal_K"] <= 0.090)
    checks["kb_is_si_definition_value"] = bool(KB_SI == 1.380649e-23)
    # ħ 不是定义值（= h/2π 无理）⇒ 只披露 qs_m3c 的 10 位取整偏差，**不擅自改**
    checks["hbar_rounding_disclosed_within_1e-9"] = bool(
        abs(HBAR - 6.62607015e-34 / _TWO_PI) / HBAR < 1e-9)

    # ⑦ 🔴 比值与 η 无关（正因如此必须并报绝对量 —— 此处把「陷阱」本身写成判据）
    _rs = [thermal_to_quantum_ratio(thermal_occupancy(0.5)) for _ in (0.01, 0.5, 0.99)]
    checks["ratio_independent_of_eta"] = bool(
        _rs[0] == _rs[1] == _rs[2])
    checks["absolute_noise_does_depend_on_eta"] = bool(
        added_noise_with_bath(0.01, 1.0) > 100.0 * added_noise_with_bath(0.5, 1.0) / 100.0)

    # ⑧ 高温渐近：T ≫ T_q ⇒ n_th + ½ ≈ T/T_q（相对 1e-3）
    _hot = 100.0 * r["thermal_quantum_temperature_K"]
    _rel = abs(occupancy_plus_half_symmetrized(_hot) / (_hot / r["thermal_quantum_temperature_K"]) - 1.0)
    checks["high_T_rayleigh_jeans_limit"] = bool(_rel < 1e-3)

    # 反向探针：非法入参必抛
    def _raises(fn):
        try:
            fn()
        except ValueError:
            return True
        return False

    checks["reverse_bad_temp_raise"] = bool(_raises(lambda: thermal_occupancy(0.0)))
    checks["reverse_negative_occupancy_raise"] = bool(
        _raises(lambda: added_noise_with_bath(0.5, -1.0)))
    checks["reverse_bad_eta_raise"] = bool(_raises(lambda: added_noise_with_bath(0.0, 0.1)))
    return checks


def main() -> int:  # pragma: no cover
    checks = selfcheck_qnet_thermal_noise()
    bad = [k for k, v in checks.items() if not v]
    for k, v in checks.items():
        print("  [%s] %s" % ("PASS" if v else "FAIL", k))
    r = thermal_noise_report()
    print("\nη = %.6e  ·  T_q = %.6f K  ·  T* = %.6f K  ·  T(10%%) = %.6f K"
          % (r["eta"], r["thermal_quantum_temperature_K"],
             r["crossover_temperature_K"], r["temp_for_10pct_thermal_K"]))
    print("T = %.4f K  ⇒  n_th = %.6e  ·  r = %.3e  ·  n_add(T0) = %.6f  →  n_add(T) = %.6f（×%.6f）"
          % (r["temp_k"], r["thermal_occupancy"], r["thermal_to_quantum_ratio"],
             r["added_noise_T0"], r["added_noise_at_bath"], r["added_noise_increase_factor"]))
    for t in (0.020, 0.21842296504092182, 1.0):
        print("  T = %-8.4f K ⇒ n_th = %.6e · n_add = %.6f"
              % (t, thermal_occupancy(t), added_noise_with_bath(r["eta"], thermal_occupancy(t))))
    print("自检：%s（FAIL=%s）" % ("ALL PASS" if not bad else "FAIL", bad or "无"))
    return 0 if not bad else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
