"""LDA · T1 电学/TCAD 数值内核（C 级第一天自主）· 1D p-n 结漂移-扩散+连续性（热平衡）。

🔴 主权边界（T1 分层解锁 · 研发规划 §1.1 / §3 T1-B）：
- 本模块为 T1 数值内核（载流子输运 PDE），**C 级第一天自主**实现：
  泊松方程（有限差分 + 阻尼牛顿求电势 φ）+ 自洽玻尔兹曼统计
  （热平衡下漂移-扩散退化为 n=n_i·exp(φ/V_T), p=n_i·exp(−φ/V_T)）
  求解载流子浓度分布 N(x)/P(x)。
- **零外部依赖**（仅 numpy）；**不 import 任何 A 级美系商业求解器**
  （Sentaurus / Lumerical DEVICE / COMSOL 半导体），**不 import DEVSIM**
  （B 级，仅作同几何同边界双向标定的外部 ORACLE，见 T1-B-W3）。
- 🔴 **T1 输出不作 ORACLE（红线）**：本模块解出的 N(x)/P(x)/φ(x) 仅为
  **候选（candidate）**，判决仍由物理定律锚 / 教科书闭式 golden（Sze
  耗尽近似）/ foundry 实测 / 公开文献定。`T1_OUTPUT_IS_ORACLE=False`
  为铁律开关；`guard_t1_not_oracle()` 为反向测试守卫。
- 🔴 **EAR 744.23 成熟节点用途声明**：本内核声明仅用于成熟节点 /
  非先进用途半导体器件设计仿真。见 docs/ 合规件（T1-B-W3）。

物理（Sze《Physics of Semiconductor Devices》§2.2 突变 p-n 结，热平衡）：
- 泊松：d²φ/dx² = −(q/ε)(n − p + N_D − N_A)
- 电中性 + 质量作用 + 费米平坦 ⇒ n=n_i·exp(φ/V_T), p=n_i·exp(−φ/V_T)
- 单变量非线性泊松边值问题（仅 φ 未知），有限差分 + 阻尼牛顿求解。
- golden（Sze 闭式耗尽近似）：V_bi=V_T·ln(N_A·N_D/n_i²)；
  W=√(2ε·V_bi/q·(N_A+N_D)/(N_A·N_D))；峰值电场 E_max=q·N_D·x_n/ε。

与 golden 的方法学独立性（判据 D 真数值）：
- golden = 解析耗尽近似（突变结、耗尽区 n,p≈0）
- cand   = 自洽玻尔兹曼统计数值解（耗尽区少数载流子指数衰减，非严格 0）
⇒ 二者物理同源（同一泊松+统计），方法独立（解析近似 vs 全场数值），
  |cand−golden| 反映耗尽近似的固有截断误差，随网格加密单调收敛。
LLM 不进判决路径。
"""
from __future__ import annotations

import math

import numpy as np

# ---- 物理常数（SI） ----
Q_E = 1.602176634e-19          # 电子电荷 (C)
EPS0 = 8.854187817e-12         # 真空介电 (F/m)
EPS_SI = 11.7 * EPS0          # Si 相对介电
K_B = 1.380649e-23             # 玻尔兹曼 (J/K)
T_KELVIN = 300.0
V_T = K_B * T_KELVIN / Q_E    # 热电压 ≈ 0.02585 V
N_I = 1.0e16                   # Si 本征载流子浓度 (m^-3, ≈1e10 cm^-3)

# 🔴 红线开关：T1 输出永不作 ORACLE
T1_OUTPUT_IS_ORACLE = False

# 掺杂默认值（典型突变结，非对称 p+n）
N_A_DEFAULT = 1.0e23           # 受主 (m^-3, 1e17 cm^-3)
N_D_DEFAULT = 1.0e22           # 施主 (m^-3, 1e16 cm^-3)
L_DEFAULT = 4.0e-6             # 器件总长 (m, 4 µm)
JUNCTION_FRAC = 0.5            # 突变结位置（居中）


def doping_profile(x: np.ndarray, N_A: float, N_D: float, x0: float):
    """突变结掺杂剖面对角（受主 p 侧 x<x0，施主 n 侧 x>x0）。"""
    NA = np.where(x < x0, N_A, 0.0)
    ND = np.where(x > x0, N_D, 0.0)
    return NA, ND


def _thomas_solve(b: np.ndarray, a: np.ndarray, c: np.ndarray,
                  d: np.ndarray) -> np.ndarray:
    """Thomas 算法解三对角系统 A·x=d。

    b: 主对角(长 n)；a: 下对角(长 n-1, a[i]=x[i-1] 系数)；c: 上对角(长 n-1)。
    """
    n = len(b)
    cp = np.zeros(n)
    dp = np.zeros(n)
    x = np.zeros(n)
    cp[0] = c[0] / b[0]
    dp[0] = d[0] / b[0]
    for i in range(1, n):
        m = b[i] - a[i - 1] * cp[i - 1]
        if abs(m) < 1e-300:
            m = 1e-300
        cp[i] = c[i] / m if i < n - 1 else 0.0
        dp[i] = (d[i] - a[i - 1] * dp[i - 1]) / m
    x[n - 1] = dp[n - 1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]
    return x


def solve_pn_junction_1d(N_A: float = N_A_DEFAULT, N_D: float = N_D_DEFAULT,
                         L: float = L_DEFAULT, n_grid: int = 400,
                         x0: float | None = None, eps: float = EPS_SI,
                         n_i: float = N_I, v_t: float = V_T,
                         max_iter: int = 400, resid_tol: float = 1e-8,
                         step_cap: float = 0.05) -> dict:
    """自研 1D p-n 结热平衡载流子分布（T1 内核候选）。

    返回 dict：x / phi / n / p / V_bi / W / x_n / x_p / E_max / dx /
                provenance("self_authored_t1_candidate") / is_oracle(False)。

    🔴 红线自检：纯 numpy 自洽泊松求解，无光子有源物理、无 A 级求解器、
    无 DEVSIM import ⇒ 不破主权/验证纪律红线。输出 is_oracle=False。
    """
    if x0 is None:
        x0 = L * JUNCTION_FRAC
    x = np.linspace(0.0, L, n_grid)
    dx = x[1] - x[0]
    NA, ND = doping_profile(x, N_A, N_D, x0)
    # 边界费米势（bulk 接触）
    phi_p = -v_t * math.log(N_A / n_i)   # p 侧
    phi_n = v_t * math.log(N_D / n_i)    # n 侧
    V_bi = phi_n - phi_p
    # 初始猜测：线性插值
    phi = np.linspace(phi_p, phi_n, n_grid)
    M = n_grid
    off = 1.0 / dx ** 2
    n_int = M - 2
    a_sub = np.full(n_int - 1, off)        # 下对角
    c_sup = np.full(n_int - 1, off)        # 上对角
    cap = step_cap                         # 牛顿步长限幅（防 sinh 强非线性震荡）
    converged = False
    for _ in range(max_iter):
        # 自洽玻尔兹曼统计：n=n_i·exp(φ/V_T), p=n_i·exp(−φ/V_T)
        # ⇒ n − p = n_i·(exp(φ/V_T) − exp(−φ/V_T)) = 2·n_i·sinh(φ/V_T)
        n = n_i * np.exp(phi / v_t)
        p = n_i * np.exp(-phi / v_t)
        # 泊松残差 R = lap + (q/ε)(n − p + N_D − N_A)
        lap = (np.roll(phi, -1) - 2.0 * phi + np.roll(phi, 1)) / dx ** 2
        lap[0] = (phi[1] - 2.0 * phi[0] + phi_p) / dx ** 2
        lap[-1] = (phi_n - 2.0 * phi[-1] + phi[-2]) / dx ** 2
        R = lap + (Q_E / eps) * (p - n + ND - NA)
        # 牛顿雅可比（内部点）：∂R_i/∂φ_i = −2/dx² − (q/ε)(2·n_i/V_T)·cosh(φ_i/V_T)
        diag = -2.0 * off + (Q_E / eps) * (-2.0 * n_i / v_t) * np.cosh(phi / v_t)[1:M - 1]
        d_int = R[1:M - 1]
        delta = _thomas_solve(diag, a_sub, c_sup, d_int)
        delta = np.clip(delta, -cap, cap)
        phi_new = phi.copy()
        phi_new[1:M - 1] = phi[1:M - 1] - delta
        phi_new[0] = phi_p
        phi_new[-1] = phi_n
        if np.max(np.abs(phi_new - phi)) < resid_tol:
            phi = phi_new
            converged = True
            break
        phi = phi_new
    # 载流子（自洽玻尔兹曼统计）
    n = n_i * np.exp(phi / v_t)
    p = n_i * np.exp(-phi / v_t)
    # 电场（−dφ/dx，中心差）
    E = -np.gradient(phi, dx)
    E_max = float(np.max(np.abs(E)))
    # 耗尽宽度边界：耗尽区（近结）载流子极小、bulk 侧升到 N_D（或 N_A）。
    # 边界 = 该侧「最大 x 处载流子仍 < N_D/e（或 N_A/e）」（耗尽区外缘）。
    n_side = x > x0
    p_side = x < x0
    x_n = float(np.where(n[n_side] < N_D / np.e, x[n_side], -np.inf).max())
    x_p = float(np.where(p[p_side] < N_A / np.e, x[p_side], -np.inf).max())
    W = x_n - x_p
    return {
        "x": x, "phi": phi, "n": n, "p": p,
        "V_bi": float(V_bi), "W": float(W), "x_n": float(x_n),
        "x_p": float(x_p), "E_max": E_max, "dx": float(dx),
        "provenance": "self_authored_t1_candidate",
        "is_oracle": False,
        "converged": converged,
    }


def sze_pn_junction_closed_form(N_A: float = N_A_DEFAULT, N_D: float = N_D_DEFAULT,
                                 L: float = L_DEFAULT, x0: float | None = None,
                                 eps: float = EPS_SI, n_i: float = N_I,
                                 v_t: float = V_T) -> dict:
    """Sze 教科书闭式耗尽近似（golden，确定性物理定律锚）。

    返回 V_bi / W / x_n / x_p / E_max / 几何位置（x0 为结，居中默认）。
    """
    if x0 is None:
        x0 = L * JUNCTION_FRAC
    V_bi = v_t * math.log(N_A * N_D / (n_i * n_i))
    W = math.sqrt(2.0 * eps * V_bi / Q_E * (N_A + N_D) / (N_A * N_D))
    x_n = W * N_A / (N_A + N_D)
    x_p = W * N_D / (N_A + N_D)
    E_max = Q_E * N_D * x_n / eps
    return {
        "V_bi": float(V_bi), "W": float(W), "x_n": float(x_n),
        "x_p": float(x_p), "E_max": float(E_max),
        "x_n_pos": float(x0 + x_n), "x_p_pos": float(x0 - x_p),
        "provenance": "design_rule_anchor_sze_depletion",
    }


def guard_t1_not_oracle(solution: dict, force_oracle: bool = False) -> bool:
    """🔴 T1 输出不作 ORACLE 反向测试守卫。

    - 正常调用：断言 solution['is_oracle']==False（候选，非真值）。
    - 反向（force_oracle=True 模拟有人把 T1 输出当 ORACLE 喂判决回路）：
      必须 raise RuntimeError（守卫必响），否则破红线。
    """
    if force_oracle:
        # 反向测试：若判决回路误用 T1 数值解为 ORACLE ⇒ 守卫拒绝
        raise RuntimeError(
            "T1 输出禁止作为 ORACLE：数值 N(x)/P(x) 仅作候选，"
            "死标量判决须由物理定律锚/文献/foundry 实测定。")
    if solution.get("is_oracle", False):
        raise RuntimeError("T1 解被错误标记为 ORACLE（is_oracle=True）")
    return True


if __name__ == "__main__":
    # 自检：网格收敛 + golden 比对（Sze 耗尽近似）
    gold = sze_pn_junction_closed_form()
    print("=== Sze 闭式 golden ===")
    print(f"  V_bi={gold['V_bi']:.4f} V  W={gold['W']*1e9:.3f} nm  "
          f"x_n={gold['x_n']*1e9:.3f} nm  E_max={gold['E_max']/1e5:.3f} kV/cm")
    print("=== 自研数值 cand（网格收敛） ===")
    print(f"  {'n_grid':>7} {'dx(nm)':>8} {'E_max(kV/cm)':>14} "
          f"{'|ΔE|/E':>10} {'W(nm)':>10} {'|ΔW|/W':>10}")
    prev_errE = None
    for ng in (200, 400, 800, 1600):
        sol = solve_pn_junction_1d(n_grid=ng)
        errE = abs(sol["E_max"] - gold["E_max"]) / gold["E_max"]
        errW = abs(sol["W"] - gold["W"]) / gold["W"]
        mono = "" if prev_errE is None else ("↓收敛" if errE < prev_errE else "↑发散!")
        print(f"  {ng:>7} {sol['dx']*1e9:>8.2f} {sol['E_max']/1e5:>14.3f} "
              f"{errE:>10.4%} {sol['W']*1e9:>10.2f} {errW:>10.4%} {mono}")
        prev_errE = errE
    # 反向：N_A 改 +10% ⇒ V_bi/E_max 必变
    sol_ref = solve_pn_junction_1d()
    sol_pert = solve_pn_junction_1d(N_A=N_A_DEFAULT * 1.1)
    dE = abs(sol_pert["E_max"] - sol_ref["E_max"]) / sol_ref["E_max"]
    print(f"=== 反向 N_A×1.1 ⇒ E_max 变化 {dE:.3%}（须 ≫ tol） ===")
    # 守卫
    guard_t1_not_oracle(sol_ref)
    print("=== T1 不作 ORACLE 守卫：正常通过；反向必 raise ===")
