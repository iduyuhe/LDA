"""B30 读出保真度锚（readout_fidelity 零覆盖 · v0.9.39 · T-9 接线空白点 #2）。

物理（Krantz 2019 色散读出链）：
    SNR = 2·χ_rad·√(n̄·η·t_m/(κ_rad·(1+2N_amp)))
    ε   = ½·erfc(SNR/√2)                       （|0⟩/|1⟩ 单发误判概率）
    F   = (1-ε + (1-ε)·(1-t_m/T1))/2          （含 T1 污染的单发读出保真度）

golden = 上述闭式（确定性物理定律，'physical-law'）。
候选见 `lda_solver/readout_fidelity_quad.py`（误判概率 ε 的高斯重叠数值积分，
与 erfc 闭式方法学独立；判据 D 真数值收敛）。

工作点：取中等 SNR（SNR≈2.2, ε≈1.4e-2）而非 t_m* 饱和区——饱和区 ε≈4e-5，
±10% 参数扰动在 tol 内不可见（反向测试失敏）。固定 t_m_s 给出 SNR≈2.2：
t_m_s ≈ [SNR/(2χ_rad)]²·κ_rad·(1+2N_amp)/(n̄·η)。

默认参数：χ=0.05GHz, κ_r=0.005GHz, n̄=2, η=0.5, N_amp=5, t_m_s=4.236705e-9s,
T1=20µs ⇒ SNR=2.20, ε=1.39e-2, F=0.98599。
LLM 不进判决路径。
"""
import math


def b30_readout_fidelity(chi_ghz: float = 0.05, kappa_r_ghz: float = 0.005,
                         nbar: float = 2.0, eta: float = 0.5, N_amp: float = 5.0,
                         t_m_s: float = 4.236705e-9, T1_s: float = 20e-6) -> float:
    """单发读出保真度 F（erfc 闭式链）。"""
    chi_rad = 2.0 * math.pi * chi_ghz * 1e9
    kap_rad = 2.0 * math.pi * kappa_r_ghz * 1e9
    snr = 2.0 * chi_rad * math.sqrt(
        nbar * eta * t_m_s / (kap_rad * (1.0 + 2.0 * N_amp)))
    eps = 0.5 * math.erfc(snr / math.sqrt(2.0))
    F = (1.0 - eps + (1.0 - eps) * (1.0 - t_m_s / T1_s)) / 2.0
    return float(F)


def b30_readout_report(chi_ghz: float = 0.05, kappa_r_ghz: float = 0.005,
                       nbar: float = 2.0, eta: float = 0.5, N_amp: float = 5.0,
                       t_m_s: float = 4.236705e-9, T1_s: float = 20e-6) -> dict:
    chi_rad = 2.0 * math.pi * chi_ghz * 1e9
    kap_rad = 2.0 * math.pi * kappa_r_ghz * 1e9
    snr = 2.0 * chi_rad * math.sqrt(
        nbar * eta * t_m_s / (kap_rad * (1.0 + 2.0 * N_amp)))
    eps = 0.5 * math.erfc(snr / math.sqrt(2.0))
    F = (1.0 - eps + (1.0 - eps) * (1.0 - t_m_s / T1_s)) / 2.0
    return {
        "metric": "readout_fidelity_F",
        "value": float(F),
        "snr": float(snr),
        "eps": float(eps),
        "note": ("色散读出 SNR→erfc 闭式链（Krantz 2019）：单发读出保真度 F。"
                 "golden=确定性物理定律；候选=误判概率 ε 的高斯重叠数值积分"
                 "（判据 D 真收敛）。"),
    }
