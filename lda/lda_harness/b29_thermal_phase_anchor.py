"""B29 热光相移效率锚（D-73 升格 · v0.9.39 · T-9 接线空白点 #1）。

物理：热光相移器沿传播方向的稳态温度分布由 1D 散热鳍（fin）方程控制——
对称加热器 [0,L]、两端接指数衰减引线（热量沿波导轴向外扩散）：

    θ'' - m²θ = -m²θ_p ,   θ_p = P/(L·h_p) ,   m = 1/healing_length

闭式（绝缘中心对称 + 引线匹配）：

    θ(z) = θ_p - θ_p·exp(-mL/2)·cosh(m·(z-L/2))
    ∫θ dz = θ_p·(L - (1-exp(-mL))/m)

相位 Δφ = 2π/λ·(dn/dT)·∫θ dz；golden = degrees(Δφ) @ P = 1 mW。

判定身份：确定性物理定律闭式（golden_with_source 标 'physical-law'）。
候选见 `lda_solver/thermal_phase_efficiency.py`（同 PDE 三对角 FDM + 梯形积分，
方法学独立、判据 D 真数值收敛）。

数值约定（归一化鳍模型，绝对温标为示意、非 PDK 声明）：
  λ=1.55µm, dn/dT=1.86e-4/K, h_p=1.0 W/K（横向下导热导）,
  healing_length=100µm, L=1mm, P=1mW ⇒ θ_avg≈0.9K, 效率≈38.9°/mW。
LLM 不进判决路径。
"""
import math


def b29_thermal_phase_efficiency(lambda_um: float = 1.55,
                                  dn_dt: float = 1.86e-4,
                                  h_p: float = 1.0,
                                  healing_length_um: float = 100.0,
                                  L_um: float = 1000.0,
                                  P_mw: float = 1.0) -> float:
    """热光相移效率（度/毫瓦）：1D 散热鳍 PDE 解析闭式。

    golden = degrees(2π/λ·dn/dT·∫θ(z)dz) 在 P=1mW。
    """
    lam = lambda_um * 1e-6
    Lm = L_um * 1e-6
    m = 1.0 / (healing_length_um * 1e-6)
    theta_p = (P_mw * 1e-3) / (Lm * h_p)
    int_theta = theta_p * (Lm - (1.0 - math.exp(-m * Lm)) / m)
    phase_rad = 2.0 * math.pi / lam * dn_dt * int_theta
    return math.degrees(phase_rad)


def b29_thermal_phase_report(lambda_um: float = 1.55, dn_dt: float = 1.86e-4,
                             h_p: float = 1.0, healing_length_um: float = 100.0,
                             L_um: float = 1000.0, P_mw: float = 1.0) -> dict:
    g = b29_thermal_phase_efficiency(lambda_um, dn_dt, h_p,
                                      healing_length_um, L_um, P_mw)
    return {
        "metric": "phase_efficiency_deg_per_mW",
        "value": g,
        "note": ("1D 散热鳍稳态 PDE 解析闭式（cosh 积分）：热光相移器在 P=1mW "
                 "下的相移效率（度/毫瓦）。golden=确定性物理定律；候选=同 PDE "
                 "FDM 数值解（判据 D 真收敛）。"),
    }
