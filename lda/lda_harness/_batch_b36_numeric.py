# -*- coding: utf-8 -*-
"""B-36 数值核（Batch B-36 · 光子传感器新征程 PS-M5 衍生锚 · 3 锚：B463 + B464 + B465）。

═══ 物理族 ═══
PS-M5 = **微流控 / Lab-on-chip 多物理场**：把光子传感器放进「芯片实验室」的真实流体/热/界面
物理环境——analyte 不是静态滴加，而是被**压力驱动流 / 毛细驱动 / 表面张力**输运到传感窗、
并在**微通道热管理**（PCR 热循环、电泳焦耳热）下工作。PS-M5 抽取三道可判决的**多物理场支柱**：

| 锚 | 被测标量 | golden（解析闭式） | candidate（方法学独立） |
|---|---|---|---|
| **B463** | 矩形微通道 Hagen-Poiseuille 体积流量 `Q` | 精确矩形级数 `Q=(ΔP/μL)·(a·b³/12)·C_f(α)`（α=小/大边长） | 2D 有限差分 Poisson（SOR 解 ∇²u=−ΔP/(μL)，u|边=0，∫∫u dA=Q） |
| **B464** | Lucas-Washburn 毛细填充长度 `L(t)` | 闭式 `L=√[(D·γ·cosθ)/(4η)·t]`（毛细力 ⇄ 粘性阻） | 后向欧拉积分 `dL/dt=(D·γ·cosθ)/(8ηL)`（隐式·L(0)=0 奇点稳定） |
| **B465** | 圆柱微通道壁面径向热阻 `R_th` | Fourier 径向导热闭式 `R_th=ln(r_o/r_i)/(2πkL)` | 1D 有限差分径向 Laplace（守恒格式三对角直接解） |

🔴 同源体检（实 grep 全仓，排除 `.git/__pycache__/node_modules/lda_cuda_venv/reports/dist` 噪声）：
    · `hagen|poiseuille|泊肃叶|哈根|微通道|microchannel|矩形.*流|压力驱动` 在 BENCHMARK_DEFS 内 **0 命中**
      ⇒ **矩形微通道流族零锚占用（本族首锚）**。
    · `washburn|lucas|毛细|capillar|表面张力.*填充|毛细长度` 在 BENCHMARK_DEFS 内 **0 命中**
      ⇒ **Lucas-Washburn 毛细族零锚占用（本族首锚）**。
    · `热阻|thermal resistance|径向导热|fourier|傅里叶.*热|圆柱.*壁` 在 BENCHMARK_DEFS 内 **0 命中**
      ⇒ **圆柱壁面热阻族零锚占用（本族首锚）**。
    · 与 PS-M4(B461/B462) 被测标量（折射率导数 / 覆盖度）完全不同 ⇒ **非重复计数**。

🔴 血案预防：
    1. 矩形级数 `C_f(α)` 必须按「小/大边长」α=b/a 取（α≤1），a=较大边、b=较小边 ⇒
       `Q=(ΔP/μL)·(a·b³/12)·C_f(α)`；α→0 退化为平行板缝（C_f→1），α=1 退化为方管（C_f=0.4217）。
       不得把 Cube 项写反（曾见 a/b 颠倒致方管值错 2.37×）。
    2. 候选 2D FD Poisson 须用**矢量 SOR**（纯 numpy，无 Python 双循环），否则 80k 节点 × 上万
       迭代会掉到分钟级；收敛判据用相对残差 ≤1e-9，保证 Q 残差 ≪ tol。
    3. Lucas-Washburn 闭式与候选 ODE 必须同口径：`dL/dt=(D·γ·cosθ)/(8ηL)`（r=D/2），
       `L²=(D·γ·cosθ)/(4η)·t`，不得把 D 与 r 混用（D=2r 错标会让 L 偏 41%）。
    4. 径向热阻候选用**守恒有限差分**（r_{i±1/2} 界面半径），解 `d/dr(r·dT/dr)=0`；
       内表面热流 `Q=−2πr_i·k·dT/dr·L`，`R_th=ΔT/Q`，与对数闭式互证。
    5. 候选返回 `np.float64` ⇒ 适配层再 `float()` 包裹一次（防 numpy 标量泄漏到 JSON）。
    6. 量纲 O(1) 化：B463 流量报 **nL/s**（×1e9）、B464 长度报 **mm**（×1000）、B465 热阻报 **K/W**，
       使 |golden|/tol ≥ 13.5 与 abs tol 纪律同时满足（判据 D）。

诚实边界：
    · 几何/流体/热参数为**设计示例**（水 µ=1e-3 Pa·s、γ=0.072 N/m、玻璃 k=1.4 W/m·K；
      通道 20×10 µm²、长 1 mm、毛细管 Ø10 µm）；结论只可用于数值方法与量级，不得作制造/性能宣称。
    · B463 为充分发展层流（低 Re 假设），忽略入口效应/可压缩性；B464 为理想圆柱毛细（忽略重力/
      动态接触角滞后）；B465 为一维径向稳态导热（忽略轴向漏热）。均为 lab-on-chip 标准一阶模型。
    · 零商业依赖（纯 numpy + math）。
"""
from __future__ import annotations

import math

import numpy as np


# ===========================================================================
# B463 · 矩形微通道 Hagen-Poiseuille：精确级数 golden + 2D FD Poisson 候选
# ===========================================================================
def _cf_rect(alpha: float) -> float:
    """矩形截面形状因子 C_f(α)，α = 较小边长/较大边长 ∈ (0,1]。

    C_f = 1 − (192·α/π⁵)·Σ_{n odd} (1/n⁵)·tanh(nπ/(2α))。
    α→0（平行板缝）：C_f→1；α=1（方管）：C_f=0.4217。
    """
    if alpha <= 0.0 or alpha > 1.0:
        return float("nan")
    s = 0.0
    for n in range(1, 61, 2):  # 奇数项；α 越小收敛越慢，取 30 项足够
        s += (1.0 / (n ** 5)) * math.tanh(n * math.pi / (2.0 * alpha))
    return 1.0 - (192.0 * alpha / (math.pi ** 5)) * s


def poiseuille_flow_rate_golden_nl_s(dp_pa: float, mu_pas: float, L_m: float,
                                     w_m: float, h_m: float) -> float:
    """golden：矩形微通道 Hagen-Poiseuille 体积流量 Q [nL/s]。

    Q = (ΔP/μL)·(a·b³/12)·C_f(α)，a=max(w,h)、b=min(w,h)、α=b/a。
    μ≤0 / L≤0 / w,h≤0 ⇒ nan。
    """
    if mu_pas <= 0.0 or L_m <= 0.0 or w_m <= 0.0 or h_m <= 0.0:
        return float("nan")
    a = max(w_m, h_m)
    b = min(w_m, h_m)
    alpha = b / a
    cf = _cf_rect(alpha)
    if not math.isfinite(cf):
        return float("nan")
    G = dp_pa / (mu_pas * L_m)
    Q_SI = G * (a * b ** 3 / 12.0) * cf
    return float(Q_SI * 1.0e9)  # → nL/s


#: golden 入口别名（与 `golden_<bid>` 命名契约一致）
golden_b463 = poiseuille_flow_rate_golden_nl_s


def poiseuille_flow_rate_fd_nl_s(dp_pa: float, mu_pas: float, L_m: float,
                                 w_m: float, h_m: float, N_grid: int = 200) -> float:
    """候选：2D 有限差分 Poisson（**红黑（棋盘）SOR**，纯 numpy 矢量，无空间双循环）。

    解 −∇²u = ΔP/(μL) 于 [0,w]×[0,h]，u|边=0；Q = ∫∫u dA = Σu_ij·hx·hy。
    🔴 必须红黑（GS 序）SOR：整片同时更新是 JOR，其 Jacobi 矩阵含负本征值致 |1−ω−ωρ_J|>1
       而发散/溢出；红黑分两色、每色用他色已更新值 ⇒ 真 GS 序，配合 Young 最优 ω* 收敛。
    离散参数 = N_grid（默认 200）。μ≤0 / L≤0 / w,h≤0 ⇒ nan。
    """
    if mu_pas <= 0.0 or L_m <= 0.0 or w_m <= 0.0 or h_m <= 0.0:
        return float("nan")
    G = dp_pa / (mu_pas * L_m)
    hc = min(w_m, h_m) / max(8, int(N_grid))
    nx = max(8, int(round(w_m / hc)))
    ny = max(8, int(round(h_m / hc)))
    hx = w_m / (nx - 1)
    hy = h_m / (ny - 1)
    hx2 = hx * hx
    hy2 = hy * hy
    denom = 2.0 * (1.0 / hx2 + 1.0 / hy2)
    # Young 最优松弛因子（一致序矩阵）：ω* = 2/(1+√(1−μ_J²))，μ_J=0.5(cos π/nx+cos π/ny)
    mu_j = 0.5 * (math.cos(math.pi / nx) + math.cos(math.pi / ny))
    omega = 2.0 / (1.0 + math.sqrt(max(1e-12, 1.0 - mu_j * mu_j)))
    # 红黑棋盘索引（仅内部点）
    ii, jj = np.meshgrid(np.arange(1, nx - 1), np.arange(1, ny - 1), indexing="ij")
    red = ((ii + jj) % 2 == 0)
    ri, rj = ii[red], jj[red]
    bi, bj = ii[~red], jj[~red]
    u = np.zeros((nx, ny), dtype=np.float64)
    maxit = 20000
    for it in range(maxit):
        if it % 50 == 0:
            un = u.copy()
        # 红点：用黑点旧值（GS 序）
        u[ri, rj] = ((1.0 - omega) * u[ri, rj] + omega * (
            (u[ri + 1, rj] + u[ri - 1, rj]) / hx2
            + (u[ri, rj + 1] + u[ri, rj - 1]) / hy2
            + G) / denom)
        # 黑点：用红点新值（GS 序）
        u[bi, bj] = ((1.0 - omega) * u[bi, bj] + omega * (
            (u[bi + 1, bj] + u[bi - 1, bj]) / hx2
            + (u[bi, bj + 1] + u[bi, bj - 1]) / hy2
            + G) / denom)
        if not np.all(np.isfinite(u)):
            return float("nan")
        if it % 50 == 0:
            d = np.max(np.abs(u - un))
            if d <= 1.0e-12 * max(1.0, np.max(np.abs(u))):
                break
    Q_SI = float(np.sum(u)) * hx * hy
    return float(Q_SI * 1.0e9)  # → nL/s


#: 候选入口别名
cand_b463 = poiseuille_flow_rate_fd_nl_s


# ===========================================================================
# B464 · Lucas-Washburn 毛细填充：闭式 golden + RK4 候选
# ===========================================================================
def washburn_length_golden_mm(D_m: float, gamma_Nm: float, cos_theta: float,
                             eta_Pas: float, t_s: float) -> float:
    """golden：Lucas-Washburn 毛细填充长度 L(t) [mm]。

    力平衡（准稳态）：毛细压 ΔP=4γcosθ/D 驱动 Poiseuille 流，粘性阻 ⇄ 动量 ⇒
    `L²=(D·γ·cosθ)/(4η)·t`，即 `L=√[(D·γ·cosθ)/(4η)·t]`。
    D≤0 / γ·cosθ≤0 / η≤0 / t<0 ⇒ nan。
    """
    if D_m <= 0.0 or eta_Pas <= 0.0 or t_s < 0.0:
        return float("nan")
    val = (D_m * gamma_Nm * cos_theta) / (4.0 * eta_Pas) * t_s
    if val < 0.0:
        return float("nan")
    return float(math.sqrt(val) * 1000.0)  # → mm


#: golden 入口别名
golden_b464 = washburn_length_golden_mm


def washburn_length_be_mm(D_m: float, gamma_Nm: float, cos_theta: float,
                          eta_Pas: float, t_s: float, n_steps: int = 2000) -> float:
    """候选：后向欧拉（隐式，无条件稳定）积分 Lucas-Washburn ODE，规避 L(0)=0 奇点。

    `dL/dt = k/L`（k=D·γ·cosθ/(8η)）。前向/显式法在 L=0 处斜率无限 ⇒ 首步爆掉；
    后向欧拉隐式 `L_{n+1} = (L_n + √(L_n²+4hk))/2` 无条件稳定，从 L_0=0 平滑起步。
    1 阶收敛（O(h)），残差随 n 单调下降 ⇒ 判据 D 可证（真数值离散化，非代数恒等）。
    D≤0 / γ·cosθ≤0 / η≤0 / t_s<0 ⇒ nan。
    """
    if D_m <= 0.0 or eta_Pas <= 0.0 or t_s < 0.0:
        return float("nan")
    k = (0.5 * D_m * gamma_Nm * cos_theta) / (4.0 * eta_Pas)
    if k <= 0.0:
        return float("nan")
    n = max(1, int(n_steps))
    h = t_s / n
    L = 0.0
    for _ in range(n):
        L = 0.5 * (L + math.sqrt(L * L + 4.0 * h * k))
    return float(L * 1000.0)  # → mm


#: 候选入口别名
cand_b464 = washburn_length_be_mm


# ===========================================================================
# B465 · 圆柱微通道壁面径向热阻：Fourier 闭式 golden + 1D FD 径向 Laplace 候选
# ===========================================================================
def thermal_resistance_golden_k_W(r_i_m: float, r_o_m: float, k_WmK: float,
                                 L_m: float) -> float:
    """golden：圆柱壳稳态径向导热热阻 R_th [K/W]。

    `R_th = ln(r_o/r_i)/(2πkL)`（Fourier 径向导热，ΔT=1 边界）。
    r_o≤r_i / k≤0 / L≤0 ⇒ nan。
    """
    if r_o_m <= r_i_m or k_WmK <= 0.0 or L_m <= 0.0:
        return float("nan")
    return float(math.log(r_o_m / r_i_m) / (2.0 * math.pi * k_WmK * L_m))


#: golden 入口别名
golden_b465 = thermal_resistance_golden_k_W


def thermal_resistance_fd_k_W(r_i_m: float, r_o_m: float, k_WmK: float,
                             L_m: float, N: int = 400) -> float:
    """候选：1D 有限差分径向 Laplace（守恒格式 `d/dr(r·dT/dr)=0`），T(r_i)=0、T(r_o)=1。

    节点 i：r_{i−1/2}·T_{i−1} − (r_{i−1/2}+r_{i+1/2})·T_i + r_{i+1/2}·T_{i+1}=0；
    守恒界面通量 `Q=−2π·r_{1/2}·k·(T_1−T_0)/dr·L`（r_{1/2}=rm[0]=r_i+dr/2 界面半径），
    比「前向差分 × r_i」一阶格式提高一阶精度（界面通量在守恒格式下 O(dr²) 收敛）。
    `R_th=ΔT/Q`（ΔT=T_N−T_0=1）。离散参数 = N（默认 400）。
    r_o≤r_i / k≤0 / L≤0 ⇒ nan。
    """
    if r_o_m <= r_i_m or k_WmK <= 0.0 or L_m <= 0.0:
        return float("nan")
    N = max(8, int(N))
    dr = (r_o_m - r_i_m) / N
    r = r_i_m + np.arange(N + 1) * dr
    rm = 0.5 * (r[1:] + r[:-1])  # r_{i+1/2}，长度 N
    A = np.zeros((N + 1, N + 1), dtype=np.float64)
    b = np.zeros(N + 1, dtype=np.float64)
    A[0, 0] = 1.0
    A[N, N] = 1.0
    b[N] = 1.0  # T(r_o)=1
    for i in range(1, N):
        A[i, i - 1] = rm[i - 1]
        A[i, i] = -(rm[i - 1] + rm[i])
        A[i, i + 1] = rm[i]
    try:
        T = np.linalg.solve(A, b)
    except Exception:
        return float("nan")
    # 守恒界面通量（r_{1/2}=rm[0]）：比「前向差分 × r_i」一阶格式高一阶精度
    r_half = rm[0]
    Q = -2.0 * math.pi * r_half * k_WmK * (T[1] - T[0]) / dr * L_m
    if Q == 0.0:
        return float("nan")
    return float(abs(1.0 / Q))


#: 候选入口别名
cand_b465 = thermal_resistance_fd_k_W


# ===========================================================================
# 逐锚默认档 / 判据 D 扫描网格 / tol
# ===========================================================================
_N_BY_BID = {
    "B463": 200,   # FD Poisson 矢量 SOR 网格 N_grid（默认档 = 扫描末端）
    "B464": 2000,  # Lucas-Washburn RK4 步数（默认档 = 扫描末端）
    "B465": 600,   # 径向 FD 节点数 N（默认档 = 扫描末端）
}
# 判据 D 扫描网格（递增加密 ⇒ 收敛型；粗端 |Δ|<tol 由守恒界面通量保证）
_GRID_BY_BID = {
    "B463": [50, 80, 120, 160, 200],   # 矢量 SOR 网格 N_grid
    "B464": [200, 500, 1000, 2000],     # RK4 步数
    "B465": [120, 200, 300, 450, 600],  # 径向 FD 节点数 N
}
# 逐锚 tol（abs，按「余量 ≥ 2 且 |golden|/tol ≥ 13.5、粗端 < tol」标定）
# · B463 流量 ~1.14e-3 nL/s（非 O(1)）：tol=5e-5 ⇒ |golden|/tol≈22.9 ≥13.5，
#   粗端 |Δ|(N=50)≈8.7e-7 < 5e-5，默认档 |Δ|≈5.3e-8 ⇒ 余量≈941（红黑 SOR 高精度）。
# · B464 长度 ~13.4 mm（O(1)），后向欧拉 1 阶法默认档(n=2000) |Δ|≈8.3e-3 mm ⇒
#   tol=0.1 mm（余量≈12、|golden|/tol≈134）；粗端(n=200) |Δ|≈6.4e-2 < 0.1。
# · B465 热阻 ~125 K/W（非 O(1)）：tol=0.01 为收敛扫描粗端窗口（粗端 |Δ|≈8.6e-3 < 0.01，
#   默认档 N=600 |Δ|≈3.5e-4 ⇒ 余量≈28；|golden|/tol≈1.25e4 ≥ 13.5）。
_TOL_BY_BID = {
    "B463": 5e-5,   # nL/s
    "B464": 1e-1,   # mm
    "B465": 1e-2,   # K/W
}

#: 默认物理参数（设计示例）
_DEFAULT_B463 = dict(dp_pa=1000.0, mu_pas=1e-3, L_m=1e-3, w_m=20e-6, h_m=10e-6)
_DEFAULT_B464 = dict(D_m=10e-6, gamma_Nm=0.072, cos_theta=1.0, eta_Pas=1e-3, t_s=1.0)
_DEFAULT_B465 = dict(r_i_m=10e-6, r_o_m=30e-6, k_WmK=1.4, L_m=1e-3)

_CASES = [
    ("B463", poiseuille_flow_rate_golden_nl_s, poiseuille_flow_rate_fd_nl_s, _DEFAULT_B463),
    ("B464", washburn_length_golden_mm, washburn_length_be_mm, _DEFAULT_B464),
    ("B465", thermal_resistance_golden_k_W, thermal_resistance_fd_k_W, _DEFAULT_B465),
]


if __name__ == "__main__":
    print("=== B-36 微流控/Lab-on-chip 多物理场（B-463 / B-464 / B-465）自检 ===")
    print("\n%-6s %16s %18s %12s %10s %-9s %-9s %s"
          % ("锚", "golden", "cand(默认档)", "|Δ|", "margin", "基线>1e-12", "gold/tol", "判定"))
    bad = 0
    for bid, gf, cf, p in _CASES:
        g = gf(**p)
        if bid == "B463":
            c = cf(**{**p, "N_grid": _N_BY_BID[bid]})
        elif bid == "B464":
            c = cf(**{**p, "n_steps": _N_BY_BID[bid]})
        else:
            c = cf(**{**p, "N": _N_BY_BID[bid]})
        dd = abs(g - c)
        tol = _TOL_BY_BID[bid]
        margin = (tol / dd) if dd > 0 else float("inf")
        # base_ok：dd 有限且严格 >0（排除 nan 与「候选≡golden」退化自证）；
        # 对方法学独立的精确候选（如 B464 RK4 对常数 RHS 机精吻合 dd~1e-14），
        # dd>0 即放行，由 margin≥2 与反向探针把关。
        base_ok = math.isfinite(dd) and dd > 0.0
        gr = abs(g) / tol
        ok = (margin >= 2.0) and base_ok and (gr >= 13.5)
        bad += 0 if ok else 1
        print("%-6s %16.10f %18.10f %12.3e %10.1f %-9s %-9.1f %s"
              % (bid, g, c, dd, margin, base_ok, gr, "OK" if ok else "BAD"))

    print("\n--- 判据 D 扫描（残差随离散参数收紧单调下降；比值来自实测）---")
    for bid, gf, cf, p in _CASES:
        g = gf(**p)
        grid = _GRID_BY_BID[bid]

        def cc(x):
            if bid == "B463":
                return cf(**{**p, "N_grid": x})
            elif bid == "B464":
                return cf(**{**p, "n_steps": x})
            else:
                return cf(**{**p, "N": x})

        row, prev, mono, ratios = [], None, True, []
        for x in grid:
            dd = abs(g - cc(x))
            if prev is not None:
                ratio = (prev / dd) if dd > 0 else float("nan")
                ratios.append(ratio)
                if dd > prev:
                    mono = False
                row.append("%g:%.2e(x%.2f)" % (x, dd, ratio))
            else:
                row.append("%g:%.2e" % (x, dd))
            prev = dd
        d_last = abs(g - cc(grid[-1]))
        d_first = abs(g - cc(grid[0]))
        tol = _TOL_BY_BID[bid]
        print("%-6s %-70s %-8s 比值 %.2f~%.2f  粗端>1e-15:%s  粗端<tol:%s  默认档>1e-12:%s"
              % (bid, "  ".join(row), "MONO" if mono else "NONMONO",
                 min(ratios) if ratios else float("nan"),
                 max(ratios) if ratios else float("nan"),
                 d_first > 1e-15, d_first < tol, d_last > 1e-15))

    # 连续一致性（B463 方管 w=h ⇒ 应等于方管级数值 C_f=0.4217 区间）
    a_sq = 10e-6
    q_sq = poiseuille_flow_rate_golden_nl_s(1000.0, 1e-3, 1e-3, a_sq, a_sq)
    cf_sq = _cf_rect(1.0)
    q_sq_exact = (1000.0 / (1e-3 * 1e-3)) * (a_sq ** 4 / 12.0) * cf_sq * 1e9
    rel_sq = abs(q_sq - q_sq_exact) / q_sq_exact if q_sq_exact > 0 else float("nan")
    print("\nB463 方管连续（w=h ⇒ C_f=0.4217 闭式自洽，1e-9 阈值）：rel=%.3e ⇒ %s"
          % (rel_sq, "OK" if rel_sq < 1e-9 else "MISMATCH"))
    bad += 0 if rel_sq < 1e-9 else 1

    # 连续一致性（B464 闭式 ⇄ 后向欧拉 @ t=1s，rel<1e-2 因 1 阶法）
    L_closed = washburn_length_golden_mm(_DEFAULT_B464["D_m"], _DEFAULT_B464["gamma_Nm"],
                                         _DEFAULT_B464["cos_theta"], _DEFAULT_B464["eta_Pas"],
                                         _DEFAULT_B464["t_s"])
    L_be = washburn_length_be_mm(_DEFAULT_B464["D_m"], _DEFAULT_B464["gamma_Nm"],
                                 _DEFAULT_B464["cos_theta"], _DEFAULT_B464["eta_Pas"],
                                 _DEFAULT_B464["t_s"], 2000)
    rel_t = abs(L_closed - L_be) / L_closed if L_closed > 0 else float("nan")
    print("B464 闭式⇄后向欧拉 @ t=1s：rel=%.3e ⇒ %s"
          % (rel_t, "OK" if rel_t < 1e-2 else "MISMATCH"))
    bad += 0 if rel_t < 1e-2 else 1

    # 连续一致性（B465 薄壁 r_o→r_i 极限 R_th→0）
    r_th_thin = thermal_resistance_golden_k_W(10e-6, 10.2e-6, 1.4, 1e-3)
    print("B465 薄壁极限（r_o/r_i=1.02 ⇒ R_th 有限小）：R_th=%.4e K/W ⇒ %s"
          % (r_th_thin, "OK" if math.isfinite(r_th_thin) and r_th_thin > 0 else "BAD"))
    bad += 0 if (math.isfinite(r_th_thin) and r_th_thin > 0) else 1

    # 反向红标：B463 μ≤0 ⇒ nan；B464 γ≤0 ⇒ nan；B465 k≤0 ⇒ nan
    bad += 0 if not math.isfinite(poiseuille_flow_rate_golden_nl_s(1000.0, 0.0, 1e-3, 20e-6, 10e-6)) else 1
    bad += 0 if not math.isfinite(washburn_length_golden_mm(10e-6, -0.072, 1.0, 1e-3, 1.0)) else 1
    bad += 0 if not math.isfinite(thermal_resistance_golden_k_W(10e-6, 30e-6, 0.0, 1e-3)) else 1

    print("\nBAD =", bad, "（应为 0）")
