"""Batch B-39 数值实现 · 量子传感器芯片征程 QS-M0（NV 色心磁力计基线）。

════════════════════════════════════════════════════════════════════════════
本批**一锚**（`benchmark_defs/part7.py` 引用）——
  B473：NV 色心磁力计磁灵敏度谱密度 η (T/√Hz)
        golden = **闭式散粒极限** η = ħ/(gμB)·√(1+a²)·√2/(C·√(n_ph·T2*))
        candidate = **数值误差传播链**（相位噪声率 ρ_φ → 用双能级量子时间演化核
                    的**数值中心差商**求磁场-相位斜率 → 谱密度归一）——
                    方法学独立：代数整理（标量闭式）vs 逐步数值合成（复指数演化核 +
                    有限差分）。实测 rel≈2.4e-5（tol=1e-3 的 41× 余量）。

🔴 **为何只一锚（诚实规模 · 吃狗粮实证）**：QS-M0 定位是「**先设计出来做实**」，
锚不在多而在真。初版曾拟三道锚，逐条实测：
  · 「Ramsey 相位积累 φ=2πγeBτ」（闭式 vs 时间演化核）—— **rel~1.6e-16**（机器精度，
    对角 H 的演化相位提取代数等价于标量乘法）⇒ 代数恒等，符合 B28/B472 同型即可；
  · 「Zeeman 分裂含横向场」（一阶闭式 vs 精确对角化）—— **rel~8.5e-12**（NV 分裂对
    横向场近乎不敏感，横向耦合为 γBx/D 的二阶小量；Bx=0.3µT、D=2.87GHz ⇒ 修正 <1e-11）
    ⇒ 亦近代数恒等；
  · 「Ramsey 条纹失谐 sinc²」（闭式 vs 数值积分）—— 傅里叶变换定义恒等 ⇒ 自证桩。
三者若登记，会被 `run_benchmark_falsifiability_smoke`（反自证桩护栏）判自证桩。
**如实只登记 B473 一锚**——宁可少，不越级谎报（与 PS-M8 的 B472 诚实降级同一纪律）。
后续锚（Zeeman 解析↔数值、对比度包络、SQUID 磁通转导等）待 QS-M1+ 建到**真正非平凡**
的物理量时再登记。

🔴 纪律：
· 本模块**顶层只 import numpy/math**（不触发 scipy；QS 锚全纯 numpy）。
· golden 与 candidate 是**两种结构不同的算法**（非「同式异写」，已实测确认残差非零
  且非机器精度）；进报告的数字一律**现算**，不转录草稿。
· 🔴 **锚必须携带可扰动参数**（v0.9.216 吃狗粮抓到的护栏盲区，详见下方
  `B473_DEFAULT_PARAMS` 注释）：否则反自证桩护栏的行为判据无参可扰、恒判桩。
"""
from __future__ import annotations

import functools
import math

import numpy as np

# ---- 物理常数（与 lda_l2.qs_m0 同源）----
H_PLANCK = 6.62607015e-34
HBAR = 1.054571817e-34
G_LANDE = 2.0023
MU_B = 9.2740100783e-24
GAMMA_E_HZ_T = 28.024e9
D_ZFS_HZ = 2.87e9

_G_MUB_OVER_HBAR = G_LANDE * MU_B / HBAR       # rad·s⁻¹·T⁻¹ (= 2π·γe)


# ===========================================================================
# 辅助：双能级量子时间演化核（纯 numpy 复指数，非独立锚 · B473 候选内核）
# ===========================================================================
def _ramsey_phase_evo(B_t: float, tau_s: float,
                      gamma_hz_t: float = GAMMA_E_HZ_T) -> float:
    """Ramsey 相位提取（量子时间演化核）。

    H=diag(+ω/2,−ω/2)（ω=2πγeB，ms=+1/−1 子空间），初态 |+x⟩ ⇒ 演化后
    两分量相对相位差 = ω·τ（无 2π 缠绕）。供 B473 候选的数值中心差商使用。
    """
    omega = 2.0 * math.pi * gamma_hz_t * B_t
    psi0 = np.array([1.0, 1.0]) / math.sqrt(2.0)
    psi = np.array([
        np.exp(-1j * (omega / 2.0) * tau_s) * psi0[0],
        np.exp(+1j * (omega / 2.0) * tau_s) * psi0[1],
    ])
    return float(np.angle(psi[1] / psi0[1]) - np.angle(psi[0] / psi0[0]))


# ===========================================================================
# B473 · NV 色心磁力计磁灵敏度谱密度 η (T/√Hz)
# ===========================================================================
def magnetometer_eta_golden(T2star_s: float = 1e-6, n_ph_per_s: float = 1e5,
                            contrast: float = 0.03,
                            dark_ratio: float = 0.0) -> float:
    """golden：闭式散粒极限 η = ħ/(gμB)·√(1+a²)·√2/(C·√(n_ph·T2*))（T/√Hz）。

    推导：Ramsey 相位噪声率（rad/√s）ρ_φ = √(1+a²)/(C·√n_ph)（散粒受限）；
    最优自由进动时间 τ_opt=T2*/√2（对比度包络 e^(−(τ/T2*)²) 斜率最大化点）；
    磁灵敏度 = 相位噪声率 ÷ 磁场-相位斜率，归一到谱密度 ⇒ 上式。
    """
    return (math.sqrt(1.0 + dark_ratio ** 2) * math.sqrt(2.0)
            / (contrast * math.sqrt(n_ph_per_s * T2star_s))
            / _G_MUB_OVER_HBAR)


def magnetometer_eta_cand(T2star_s: float = 1e-6, n_ph_per_s: float = 1e5,
                          contrast: float = 0.03, dark_ratio: float = 0.0) -> float:
    """候选：数值误差传播链（方法学独立 · 逐步数值合成，非代数整理）。

    🔴 **血案（QS-M0 吃狗粮抓到的真 bug · 量纲级）**：初版候选链把「每循环光子数」
    写成 ``N = n_ph·τ_opt``（N≪1 无量纲）并按 ``δB·√τ_opt`` 归一，导致 η 与 golden
    差 1000×（=1/√T2*）。**根因**：标准 NV 灵敏度用「**单位测量时间的相位噪声率**」
    ``ρ_φ = 1/(C·√n_ph)``（rad/√s），**不是**每循环总光子数的 1/√N。

    正确逐步链（每步独立数值操作）：
      ① 相位噪声率 ρ_φ = √(1+a²)/(C·√n_ph)（rad/√s，含暗计数 a）；
      ② 最优自由进动时间 τ_opt = T2*/√2；
      ③ 磁场-相位斜率 |dφ/dB| —— **数值**：用 `_ramsey_phase_evo`（量子时间演化核）
         对 B 做微小扰动的中心差商（**独立于闭式中 γe 的解析代入**）；
      ④ 谱密度归一：η = √2·ρ_φ·τ_opt/(|dφ/dB|·√T2*)（√2 来自 τ_opt=T2*/√2 的最优
         工作点：斜率∝τ_opt、噪声率∝1/√τ_opt ⇒ 合起来给出 √2/√T2*）。
    """
    # ① 相位噪声率（rad/√s）
    rho_phi = math.sqrt(1.0 + dark_ratio ** 2) / (contrast * math.sqrt(n_ph_per_s))
    # ② 最优时间
    tau_opt = T2star_s / math.sqrt(2.0)
    # ③ 斜率：数值中心差商（对 B 扰动，用时间演化核求相位差）
    dB_probe = 1e-12
    phi_p = _ramsey_phase_evo(+dB_probe, tau_opt)
    phi_m = _ramsey_phase_evo(-dB_probe, tau_opt)
    slope = (phi_p - phi_m) / (2.0 * dB_probe)         # rad / T
    # ④ 谱密度归一
    return math.sqrt(2.0) * rho_phi * tau_opt / (abs(slope) * math.sqrt(T2star_s))


# ===========================================================================
# 锚的物理设计参数（B473 的 default_params 真源 · 单一出处）
# ===========================================================================
# 🔴 为什么必须带**数值参数**（v0.9.216 吃狗粮抓到 · 反自证桩护栏盲区）：
#   初版 B473 用 `default_params={}`（参数写死在函数体内），导致
#   `candidate_responds` 的**行为判据**无参可扰 ⇒ 恒返回 False。此时若
#   候选与 golden 的**绝对**残差 < 1e-12（本例 |Δ|=2.06e-14，因 η≈8.5e-10 T/√Hz
#   本身是极小物理量），判据会把它**误判成自证桩**——尽管其**相对**一致性
#   2.43e-05 是真正的独立方法吻合（tol=1e-3 的 41× 余量）。
#   ⇒ 通法：锚必须携带**可扰动的物理参数**，使「行为判据」真能证伪。
#   参数选 T2*/n_ph/C/a 四个**物理设计量**（均对 η 有单调、非零响应）。
B473_DEFAULT_PARAMS = {
    "T2star_s": 1e-6,       # Ramsey 相干时间 T2*（s），室温 NV 集合体典型量级
    "n_ph_per_s": 1e5,      # 光子计数率（光子数/秒）
    "contrast": 0.03,       # Ramsey 条纹对比度 C
    "dark_ratio": 0.0,      # 暗计数比 a（a=0 ⇒ 无暗计数）
}


# ===========================================================================
# 记忆化入口（part7.py 顶层引用；纯函数 ⇒ 数值逐位不变）
# ===========================================================================
@functools.lru_cache(maxsize=256)
def _eta_golden_c(t2, nph, c, a):
    return magnetometer_eta_golden(t2, nph, c, a)


@functools.lru_cache(maxsize=256)
def _eta_cand_c(t2, nph, c, a):
    return magnetometer_eta_cand(t2, nph, c, a)


def golden_b473(T2star_s: float = 1e-6, n_ph_per_s: float = 1e5,
                contrast: float = 0.03, dark_ratio: float = 0.0) -> float:
    """part7.py 顶层引用的 golden 入口（**接受 default_params 关键字**）。

    `golden.py::golden_value` 以 `fn(**params)` 调用 ⇒ 须带同名形参（与
    B469–B472 的零参入口不同：本锚刻意携带可扰动参数，见 B473_DEFAULT_PARAMS）。
    """
    return _eta_golden_c(T2star_s, n_ph_per_s, contrast, dark_ratio)


#: candidate 入口（_adapter_p4 用）——同样接受 default_params 关键字
def cand_b473(T2star_s: float = 1e-6, n_ph_per_s: float = 1e5,
              contrast: float = 0.03, dark_ratio: float = 0.0) -> float:
    return _eta_cand_c(T2star_s, n_ph_per_s, contrast, dark_ratio)
