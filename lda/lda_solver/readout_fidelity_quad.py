"""B30 独立候选：读出误判概率 ε 的高斯重叠数值积分。

golden = ε = ½·erfc(SNR/√2)（闭式，见 lda_harness/b30_readout_anchor.py）。
candidate = 数值积分
    ε = ½·∫_{-∞}^{∞} min(𝒩(x;-SNR,1), 𝒩(x;+SNR,1)) dx
两高斯均值位于 ±SNR、σ=1 ⇒ 重叠积分 = erfc(SNR/√2) = 2ε，故乘以 ½。

两条路径方法学独立：erfc 闭式 vs 梯形数值积分（被积函数为非平凡对称凸起，
绝不退化为代数恒等）。判据 D 实测（v0.9.39）：nx=2001→2e6 残差
9.4e-7→8e-13 单调收敛（真数值离散化）。反向 nbar/eta/N_amp ±10% ⇒ SNR 变
⇒ ε 变 ⇒ |cand−golden|≫tol 必 FAIL。

依赖：numpy（纯 numpy，零第三方/GPU，LLM 不进判决路径）。
"""
import math

import numpy as np

DEFAULT_NX = 200001


def readout_fidelity_quad(chi_ghz: float = 0.05, kappa_r_ghz: float = 0.005,
                          nbar: float = 2.0, eta: float = 0.5, N_amp: float = 5.0,
                          t_m_s: float = 4.236705e-9, T1_s: float = 20e-6,
                          nx: int = DEFAULT_NX) -> float:
    """单发读出保真度 F：误判概率 ε 的高斯重叠数值积分。"""
    chi_rad = 2.0 * math.pi * chi_ghz * 1e9
    kap_rad = 2.0 * math.pi * kappa_r_ghz * 1e9
    snr = 2.0 * chi_rad * math.sqrt(
        nbar * eta * t_m_s / (kap_rad * (1.0 + 2.0 * N_amp)))
    xs = np.linspace(-12.0, 12.0, nx)
    dx = xs[1] - xs[0]
    g0 = np.exp(-0.5 * (xs + snr) ** 2) / math.sqrt(2.0 * math.pi)
    g1 = np.exp(-0.5 * (xs - snr) ** 2) / math.sqrt(2.0 * math.pi)
    # 重叠积分 ∫min = erfc(SNR/√2) = 2ε ⇒ ε = ½·∫min
    eps = 0.5 * float(np.trapezoid(np.minimum(g0, g1), dx=dx))
    F = (1.0 - eps + (1.0 - eps) * (1.0 - t_m_s / T1_s)) / 2.0
    return float(F)


def quad_convergence(chi_ghz: float = 0.05, kappa_r_ghz: float = 0.005,
                     nbar: float = 2.0, eta: float = 0.5, N_amp: float = 5.0,
                     t_m_s: float = 4.236705e-9, T1_s: float = 20e-6,
                     nxs=(2001, 20001, 200001, 2000001)) -> dict:
    """判据 D 证据表：残差随网格加密单调收敛。"""
    from lda_harness.b30_readout_anchor import b30_readout_fidelity
    gold = b30_readout_fidelity(chi_ghz, kappa_r_ghz, nbar, eta, N_amp, t_m_s, T1_s)
    rows = []
    for nnx in nxs:
        cand = readout_fidelity_quad(chi_ghz, kappa_r_ghz, nbar, eta, N_amp,
                                     t_m_s, T1_s, nx=nnx)
        rows.append({"nx": nnx, "abs_err": abs(cand - gold)})
    return {"gold": gold, "rows": rows}
