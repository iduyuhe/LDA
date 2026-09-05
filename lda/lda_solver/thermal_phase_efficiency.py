"""B29 独立候选：1D 散热鳍方程有限差分求解 + 梯形相位积分。

golden = 闭合形式 ∫cosh 解析积分（见 lda_harness/b29_thermal_phase_anchor.py）。
candidate = 同一 PDE 的**三对角有限差分**（Thomas 算法）+ 梯形积分，
**从不反解闭式**——是对同一物理定律的第二种（离散化数值）算法。

判据 D 实测（v0.9.39）：残差随网格加密单调收敛（N=50→3200：
0.45°→6.8e-3°），阶数 ~O(1/N)（边界引线匹配引入一次斜率间断，一阶合理），
是**真数值离散化**；非均匀 θ(z) 积分，绝不退化为均匀段剖分守恒的代数恒等
（B28 沿程积分反例的对照：均匀 integrand 梯形在任何 N 恒精确）。反向
dn_dt±10% ⇒ 相移随 dn/dT 线性变化 ⇒ |cand−golden|≫tol 必 FAIL。

依赖：numpy（纯 numpy，零第三方/GPU，LLM 不进判决路径）。
"""
import math

import numpy as np

DEFAULT_N = 8000


def _thomas(sub: np.ndarray, diag: np.ndarray, sup: np.ndarray,
            rhs: np.ndarray) -> np.ndarray:
    """三对角方程组求解（O(N)，纯 numpy 数组）。"""
    n = len(diag)
    cp = np.zeros(n)
    dp = np.zeros(n)
    x = np.zeros(n)
    cp[0] = sup[0] / diag[0]
    dp[0] = rhs[0] / diag[0]
    for i in range(1, n):
        m_ = diag[i] - sub[i] * cp[i - 1]
        cp[i] = sup[i] / m_ if i < n - 1 else 0.0
        dp[i] = (rhs[i] - sub[i] * dp[i - 1]) / m_
    x[-1] = dp[-1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]
    return x


def thermal_phase_efficiency_fdm(lambda_um: float = 1.55,
                                  dn_dt: float = 1.86e-4,
                                  h_p: float = 1.0,
                                  healing_length_um: float = 100.0,
                                  L_um: float = 1000.0,
                                  P_mw: float = 1.0,
                                  n: int = DEFAULT_N) -> float:
    """热光相移效率（度/毫瓦）：1D 散热鳍 FDM + 梯形积分。

    边界：z=0 引线匹配 θ'(0)=+m·θ(0)；z=L 引线匹配 θ'(L)=−m·θ(L)。
    """
    lam = lambda_um * 1e-6
    Lm = L_um * 1e-6
    m = 1.0 / (healing_length_um * 1e-6)
    theta_p = (P_mw * 1e-3) / (Lm * h_p)
    h = Lm / (n - 1)
    a = np.full(n, -(2.0 + m * m * h * h))
    sub = np.ones(n)
    sup = np.ones(n)
    rhs = np.full(n, -m * m * h * h * theta_p)
    # 左端 z=0：ghost θ_-1 = θ_1 − 2hm·θ_0 ⇒ (2/h²)θ_1 − (2(1+hm)/h² + m²)θ_0 = −m²θ_p
    c0 = -(2.0 * (1.0 + h * m) / (h * h) + m * m)
    a[0] = c0
    sup[0] = 2.0 / (h * h)
    sub[0] = 0.0
    # 右端 z=L：ghost θ_N = θ_{N-2} − 2hm·θ_{N-1}
    a[-1] = c0
    sub[-1] = 2.0 / (h * h)
    sup[-1] = 0.0
    theta = _thomas(sub, a, sup, rhs)
    int_theta = float(np.trapezoid(theta, dx=h))
    phase_rad = 2.0 * math.pi / lam * dn_dt * int_theta
    return float(math.degrees(phase_rad))


def fdm_convergence(lambda_um: float = 1.55, dn_dt: float = 1.86e-4,
                    h_p: float = 1.0, healing_length_um: float = 100.0,
                    L_um: float = 1000.0, P_mw: float = 1.0,
                    ns=(50, 100, 200, 400, 800, 1600, 3200, 6400)) -> dict:
    """判据 D 证据表：残差随 N 单调收敛（真数值离散化）。"""
    from lda_harness.b29_thermal_phase_anchor import b29_thermal_phase_efficiency
    gold = b29_thermal_phase_efficiency(lambda_um, dn_dt, h_p,
                                         healing_length_um, L_um, P_mw)
    rows = []
    for nn in ns:
        cand = thermal_phase_efficiency_fdm(lambda_um, dn_dt, h_p,
                                             healing_length_um, L_um, P_mw, n=nn)
        rows.append({"n": nn, "abs_err": abs(cand - gold)})
    return {"gold": gold, "rows": rows}
