# -*- coding: utf-8 -*-
"""LDA · Batch B-14 双方法独立锚数值核（v0.9.94 · 腿① 续加锚稀释 terminal）

四族 16 道（B233-B248）。每族均为**新方程类 / 新数值方法类**，
开工前已过「同源体检」（2026-09-17 本批**实际 grep 全仓**占用扫描，非凭记忆）：

  A. 定常对流–扩散方程（一维，指数边界层）· 中心差分三对角        B233-B236（4 道）
       eq     : −ε θ'' + u θ' = 0, θ(0)=0, θ(1)=1, Pe = u/ε
       golden : 初等闭式 θ(x) = (e^{Pe·x} − 1)/(e^{Pe} − 1)（观测 x*=0.9）
       cand   : 均匀网格 h=1/n 三点中心差分 + Thomas，取 x*=0.9（恒为格点）
  B. 第二类 Fredholm 积分方程（退化/可分核）· Nyström 求积        B237-B240（4 道）
       eq     : φ(x) = f(x) + λ∫₀¹K(x,t)φ(t)dt, K = Σ a_k(x) b_k(t)（可分）
       golden : 退化核 resolvent 解析解（小规模线性代数闭式）
       cand   : 均匀节点梯形权重 Nyström ⇒ 稠密 (I−λWK)φ = f 求解
  C. 三次样条插值逼近光滑函数 · 逼近论（新类）                    B241-B244（4 道）
       golden : 初等/反三角/指数/有理闭式在 x₀ 的精确值
       cand   : 均匀节点自然三次样条（三对角解 M_j）+ 分段求值
  D. 非线性两点边值问题 · 打靶法（RK4 + 割线/二分）               B245-B248（4 道）
       golden : 四族非线性 ODE 的初等闭式解（幂/正切/对数）
       cand   : 以未知初斜率 s 打靶命中右端 BC，取 x*=0.5 处数值解

======================================================================
同源体检记录（三条红线逐条核）
----------------------------------------------------------------------
① 数值同源 —— 既有 250 道锚已占用的特殊函数/常量（**grep 全仓实测**）：
   `ai_zeros`(B-6) / `jv,yv,spherical_jn`(B-5,B-8,mie) / `ellipe,ellipk,fresnel,
   mathieu_a,mathieu_b`(B-10) / `erfc`(B30) / `zeta,voigt_profile`(B-11) /
   `leggauss,laggauss,hermgauss,chebgauss,roots_jacobi`(B-12) /
   `gamma`(B-13 仅作 golden 表达)。
   ⇒ 本批**完全不用 scipy.special**：A 用初等指数闭式、B 用 2×2/3×3 线性代数闭式、
     C 用初等/反三角/指数/有理闭式、D 用幂/正切/对数初等闭式。**零特殊函数依赖**。
   全仓 grep `advection|convection|peclet|upwind|迎风|对流` 仅 1 命中（B-10 报告里
   「未来可打的候选」注记）、`fredholm|nystrom` 仅 B-13 文档/数值核中**用于区分**
   的注释、`spline|CubicSpline|pchip|akima` 命中全为 `lda_agent` κ_c 标定表
   **双线性查表工具**（无锚用它作验证方法）、`shooting|打靶|solve_bvp|两点边值`
   仅 vendor/INSTALL.md 无关命中。
② 结构同源 —— 已占用的方程/数值方法类（grep 实测）：
   本征值问题（B-5/6/7/9/10/11 族 A + B-12 族 C）、时间推进抛物型（B-10 族 D
   Crank–Nicolson、B-11 族 B RK4）、稳态边值 ODE 三对角 FDM（**B29 散热鳍**）、
   1D 波动方程本征、FDTD leapfrog、FFT 拍频(B14)、Bragg 转移矩阵(B15/B35/B64)、
   复合 Simpson 求积（B-10/B-11 全族）、正交多项式高斯求积（B-12 族 A）、
   连分数（B-12 族 B）、代数求根 DK（B-12 族 C）、₂F₁ Euler 积分（B-12 族 D）、
   分数阶 GL 卷积（B-13 族 A）、矩阵指数 scaling–squaring（B-13 族 B）、
   梯度下降优化（B-13 族 C）、**第二类 Volterra 分块梯形递推（B-13 族 D）**、
   2D 泊松五点差分（`lda_solver/drift_diffusion_2d._solve_poisson_drift_diffusion`）、
   **2D 化学-工艺漂移-扩散自洽 Poisson–Boltzmann（`lda_solver/drift_diffusion_1d`）**。
   ⇒ 本批四类**均未被占用**：
     A = **一阶导数（对流项）参与的对流–扩散 ODE 边值问题**（B29 是**纯扩散**常系数
         `−k T'' = q`；本族含**一阶 convective 算子** ⇒ 精确解为**指数边界层**而非
         `drift_diffusion_*` 的半导体自洽 Poisson 强耦合系统：本族**无 Poisson 耦合、
         无载流子、标量线性、常系数** ⇒ 既非同源也非结构同源）
     B = **第二类 Fredholm 积分方程**（B-13 是 Volterra：**上限变** ⇒ 三角核**前向递推**；
         Fredholm 是**全核** ⇒ 必须解全局稠密线性系统；两者的核结构、可解性理论
         （Fredholm 二择一 vs Volterra 唯一解）与数值格式均不同）
     C = **插值/逼近论**（B-12 族 A 是**求积**——选节点算面积；本族是**插值**——选节点
         重建函数再取点值；数学对象、误差阶来源（f⁗ 的 t²(1−t)² 因子）与判据均不同）
     D = **两点边值问题 + 打靶法**（B-11 族 B 是**初值问题**的固定时间 RK4 积分，*无外层
         根查找*；本族的求解对象是 BVP，必须外层割线/二分把初斜率调到命中右端 BC）
③ golden 不是近似式 —— A 为初等指数闭式；B 为 2×2/3×3 线性代数精确解；
   C 为初等/反三角/指数/有理精确值；D 为幂/正切/对数初等闭式解。
   **本批 golden 无一是截断级数/微扰展开/经验拟合/数值反演常数。**

被否候选（记入报告 §2）：
   · Biot–Savart 数值积分（静磁学螺线管）—— 1/R² 核近奇性 + 与 B-10/B-11 求积类近 ⇒ 否
   · Reynolds 润滑方程（摩擦学）—— 与族 A 同为「1D 变系数 ODE BVP + 三对角 FD」，
     族内重复 ⇒ 否（让位给 Fredholm / 样条 / 打靶三条新类）
   · 三次样条求积（∫S(x)dx）—— 与 B-12 族 A 高斯求积同属「求积」类（结构同源）⇒ 否
   · Kronig–Penney 周期势能带 —— 与 B-10 Mathieu（周期系数 Hill ODE 本征）结构同源 ⇒ 否
   · QR 迭代求矩阵本征值 —— **无自然离散化参数** ⇒ 判据 D 无参可扫；且本征值问题已被
     B-5/6/7/9/10/11 占用 ⇒ 否
   · 共轭梯度 / Jacobi 迭代线性求解 —— 与族 B 同属「线性方程组求解」；且单分量误差
     非保证单调（CG 只保证 A-范数误差单调，全网用 A-范数则必须引用 golden ⇒ 自证桩）⇒ 否
   · Romberg/Richardson 外推求积 —— 光滑被积函数下超收敛 ⇒ 残差直接沉双精度地板
     （B-10/B-13 血案）；且与 B-12 求积类近 ⇒ 否
   · 3D Laplace / 2D 泊松有限差分 + SOR —— 与 `drift_diffusion_2d._solve_poisson_
     drift_diffusion` 结构同源（B-13 已否，本轮复否）⇒ 否
   · 蒙特卡洛积分 —— 非确定性 ⇒ 违反报告确定性铁律 ⇒ 否

血案规避（写进代码注释，源自 B-14 本轮**三次试探**实测 + B-6..B-13 血案表）：
   1. 【差分系数符号写反 ⇒ 静默解错方程】族 A 首版把 `u/(2h)` 两项符号写反：
      特征根由 r=(1+Pe·h/2)/(1−Pe·h/2)≈e^{Pe·h} 变成 1/1.105（即**下风向**解），
      残差恒 **0.175**（=精确解−下风向解）且**与 n 完全无关**。
      **特征指纹：残差与离散参数无关（常数）⇒ 不是离散误差，是解错了方程。**
   2. 【打靶法括号搜索对爆破解零除崩】`s ∈ [−6,+6]` 两侧都发散 ⇒ fh−fl = nan/0 ⇒
      `ZeroDivisionError` ⇒ 改「网格扫符号变化 + 有限性过滤 + 割线/二分混合」。
   3. 【右端 BC 填错 ⇒ 收敛到另一支解】B248 应 y(1)=0 却误填 ln2 ⇒ 残差恒 **0.3466**。
      **特征指纹同 1：残差与 n 无关。**
   4. 【参数化前必验自由度】`y''=6y²` 在 y(0)=1 下解**唯一**（c=±1，仅 c=1 正则）⇒
      右端值 y1 **不可自由扰动** ⇒ 改用**形状参数 β** 参数化：解的族为 `(1+βx)^{−2}`
      对应方程 `y''=6β²y²`、右端 `y(1)=(1+β)^{−2}` ⇒ β 成为合法自由参数。
   5. 【点值插值误差含 t²(1−t)² 因子 ⇒ 残差非单调】族 C 原选点 x₀=0.3773 落在 dyadic
      格点 3/8 邻域 ⇒ 随 n 加倍 t 剧烈变化 ⇒ 残差比值在 0.73~5683 之间乱跳（非单调）。
      ⇒ **改为自动搜索 x₀**（约束：严格单调 + 相邻比值 ∈[8,32] + |f(x₀)|≥0.35 +
      末残差 >1e-13 + 首残差 < tol/10）。
   6. 【零响应键近亲：观测点落在边界层平台区】族 A 取 x*=0.7 时，Pe=20 的解
      θ=0.00248 已在边界层内趋于 0、对 Pe 不敏感 ⇒ 反向信号仅 **0.11×tol**（Pe=10 仅
      1.29×）⇒ **观测点移至边界层敏感区 x*=0.9**（信号回升至 2.45×/3.50×）。
   7. 【golden 量级 < tol ⇒ 锚变松】族 C 原 `cos(4πx)@0.6245` 的 golden=0.00628
      **小于 tol=0.01** ⇒ 候选取 0 都能过 ⇒ 换 `exp(0.5x)·sin(4x)@0.4585`（值 1.214）。
   8. 默认档位须避开 **run_d_criterion_smoke ③「基线残差 > 1e-12」**：族 A n=640
      （3.5e-7~2.2e-5）、族 B n=512（3.2e-7~2.7e-5）、族 C n=64（1.9e-9~4.1e-8）、
      族 D n=32（1.9e-8~2.6e-7）—— **最薄者仍留 1.9e-8/1e-12 = 19000× 余量**。
   9. 【判据 D 扫描网格必须让观测点恒为格点】族 A 取值走 `th[int(round(x*n))]`（取整吸附，
      与 B-10 同源血案）；若扫描网格取 n=16/32/64/…（x*·n=14.4/28.8/57.6 非整数）⇒ 每档
      吸附偏移不同、残差被 O(h) 量化误差污染 ⇒ **单调性破裂**（实测 6.2e-2 → 1.6e-2 → 1.6e-2
      → 4.0e-3 → 4.0e-3 成对持平）。**扫描网格 n 必须是 10 的倍数**（本模块取
      20/40/80/160/320/640）⇒ 残差链比值恒 ~4.00、严格单调。
      **一般规则：凡观测点按 `round(x*n)` 取值的锚，其判据 D 扫描网格必须满足 x*·n ∈ ℤ。**
"""
from __future__ import annotations

import math

import numpy as np

PI = math.pi


# ======================================================================
# 通用：三对角 Thomas 求解（纯 numpy，O(n)）
# ======================================================================


def _thomas(lo, dg, up, rhs):
    """解三对角线性系统（lo 次对角 / dg 主对角 / up 超对角；lo[0] 与 up[-1] 不用）。"""
    N = len(dg)
    cp = np.zeros(N)
    dp = np.zeros(N)
    cp[0] = up[0] / dg[0]
    dp[0] = rhs[0] / dg[0]
    for i in range(1, N):
        m = dg[i] - lo[i] * cp[i - 1]
        cp[i] = up[i] / m
        dp[i] = (rhs[i] - lo[i] * dp[i - 1]) / m
    x = np.zeros(N)
    x[-1] = dp[-1]
    for i in range(N - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]
    return x


# ======================================================================
# 族 A · 定常对流–扩散方程（B233-B236）
# ======================================================================
#   −ε θ'' + u θ' = 0,  θ(0)=0, θ(1)=1,  Pe = u/ε > 0
#   精确解： θ(x) = (e^{Pe·x} − 1)/(e^{Pe} − 1)
#   （工程含义：一维定常对流–扩散的**指数边界层**，Pe 越大边界层越薄）
#   关键：一阶项系数**必须**为 lo=−ε/h² − u/(2h)、up=−ε/h² + u/(2h)。
#   写反 ⇒ 特征根变 1/[(1+Pe·h/2)/(1−Pe·h/2)]（下风向解），残差与 n 无关（血案 1）。

_XS_A = 0.9  # 观测点（边界层敏感区；n 取 10 的倍数 ⇒ 恒为格点，避免格点吸附）


def _conv_exact(pe, x=_XS_A):
    """精确解 (e^{Pe x} − 1)/(e^{Pe} − 1)。"""
    pe = float(pe)
    return float((math.exp(pe * x) - 1.0) / (math.exp(pe) - 1.0))


def _conv_central(pe, n, x=_XS_A):
    """三点中心差分 + Thomas（二阶精度 O(h²)）。"""
    n = int(n)
    h = 1.0 / n
    u = float(pe)
    N = n + 1
    lo = np.zeros(N)
    dg = np.zeros(N)
    up = np.zeros(N)
    rhs = np.zeros(N)
    dg[0] = 1.0
    rhs[0] = 0.0          # θ(0) = 0
    dg[n] = 1.0
    rhs[n] = 1.0          # θ(1) = 1
    for i in range(1, n):
        lo[i] = -1.0 / h ** 2 - u / (2.0 * h)
        dg[i] = 2.0 / h ** 2
        up[i] = -1.0 / h ** 2 + u / (2.0 * h)
    th = _thomas(lo, dg, up, rhs)
    return float(th[int(round(x * n))])


def golden_b233(pe: float = 3.5) -> float:
    """θ(0.9) 的闭式，(e^{0.9Pe} − 1)/(e^{Pe} − 1)（Pe=3.5 ⇒ 0.695492768）。"""
    return _conv_exact(pe)


def cand_b233(pe: float = 3.5, n: int = 640) -> float:
    """中心差分三对角（n=640 ⇒ 二阶收敛，余量 1.8e4×）。"""
    return _conv_central(pe, n)


def golden_b234(pe: float = 5.0) -> float:
    """θ(0.9) 闭式（Pe=5 ⇒ 0.603861499）。"""
    return _conv_exact(pe)


def cand_b234(pe: float = 5.0, n: int = 640) -> float:
    return _conv_central(pe, n)


def golden_b235(pe: float = 10.0) -> float:
    """θ(0.9) 闭式（Pe=10 ⇒ 0.367850742）。"""
    return _conv_exact(pe)


def cand_b235(pe: float = 10.0, n: int = 640) -> float:
    return _conv_central(pe, n)


def golden_b236(pe: float = 20.0) -> float:
    """θ(0.9) 闭式（Pe=20 ⇒ 0.135335281）。"""
    return _conv_exact(pe)


def cand_b236(pe: float = 20.0, n: int = 640) -> float:
    return _conv_central(pe, n)


# ======================================================================
# 族 B · 第二类 Fredholm 积分方程（可分核）· Nyström 求积（B237-B240）
# ======================================================================
#   φ(x) = f(x) + λ ∫₀¹ K(x,t) φ(t) dt,   K(x,t) = Σ_k a_k(x) b_k(t)（**可分**）
#   解析解： φ(x) = f(x) + λ · a(x)ᵀ c,   c = (I − λA)^{−1} d
#            A_{ij} = ∫₀¹ b_i(t) a_j(t) dt,  d_i = ∫₀¹ b_i(t) f(t) dt
#   （A、d 均为**手算解析**的精确有理/指数值 —— golden 不是数值积分近似）
#   候选：均匀节点 Nyström ⇒ φ_i = f_i + λ Σ_j w_j K(x_i,x_j) φ_j（稠密系统）
#   与 B-13 族 D（Volterra 三角核**前向递推**）不同：本例必须解**全局**稠密系统。

_XS_B = 0.5


def _fred_parts(kind):
    """返回 (A, a(x) 向量化, b(t) 向量化)：lin2 = 1 + x t；lin3 = 1 + x t + x²t²。"""
    if kind == 'lin2':
        A = np.array([[1.0, 0.5], [0.5, 1.0 / 3.0]])
        af = lambda x: np.vstack([np.ones_like(x), x])
        bf = lambda t: np.vstack([np.ones_like(t), t])
    elif kind == 'lin3':
        A = np.array([[1.0, 0.5, 1.0 / 3.0],
                      [0.5, 1.0 / 3.0, 0.25],
                      [1.0 / 3.0, 0.25, 0.2]])
        af = lambda x: np.vstack([np.ones_like(x), x, x * x])
        bf = lambda t: np.vstack([np.ones_like(t), t, t * t])
    else:
        raise ValueError(kind)
    return A, af, bf


def _fred_d(kind, fkind):
    """d_i = ∫₀¹ b_i(t) f(t) dt 的**解析**值。"""
    if kind == 'lin2':
        base = np.array([1.0, 1.0 / 3.0])  # ∫ t^i dt, i=0,1
    elif kind == 'lin3':
        base = np.array([1.0, 1.0 / 3.0, 0.2])
    else:
        raise ValueError(kind)
    if fkind == 'one':
        return np.array([1.0, 0.5]) if kind == 'lin2' else np.array([1.0, 0.5, 1.0 / 3.0])
    if fkind == 'exp':                      # f = e^x
        return np.array([math.e - 1.0, 1.0])
    if fkind == 'cos':                      # f = cos(πx)：∫cos=0, ∫t cos(πt)=−2/π²
        return np.array([0.0, -2.0 / PI ** 2])
    if fkind == 'x':
        return np.array([0.5, 1.0 / 3.0])
    if fkind == 'x2':                       # f = x²：∫t²=1/3, ∫t³=1/4
        return np.array([1.0 / 3.0, 0.25])
    raise ValueError(fkind)
    return base  # pragma: no cover


def _fred_f(fkind):
    """f(x) 的 numpy 函数。"""
    return {
        'one': lambda x: np.ones_like(x),
        'exp': lambda x: np.exp(x),
        'cos': lambda x: np.cos(PI * x),
        'x': lambda x: np.asarray(x, dtype=float),
        'x2': lambda x: np.asarray(x, dtype=float) ** 2,
    }[fkind]


def _fredholm_exact(lam, kind, fkind):
    """退化核解析解 φ(x*)（小规模线性代数，精确）。"""
    A, af, bf = _fred_parts(kind)
    d = _fred_d(kind, fkind)
    c = np.linalg.solve(np.eye(len(d)) - float(lam) * A, d)
    f0 = float(_fred_f(fkind)(np.array([_XS_B]))[0])
    return float(f0 + float(lam) * float(np.dot(af(np.array([_XS_B]))[:, 0], c)))


def _fredholm_nystrom(lam, n, kind, fkind):
    """Nyström 求积（均匀节点 + 梯形权重）⇒ 稠密线性求解。"""
    n = int(n)
    h = 1.0 / n
    xs = np.linspace(0.0, 1.0, n + 1)
    w = np.full(n + 1, h)
    w[0] *= 0.5
    w[-1] *= 0.5
    ax = _fred_parts(kind)[1](xs)
    bx = _fred_parts(kind)[2](xs)
    K = np.zeros((n + 1, n + 1))
    for k in range(ax.shape[0]):
        K += np.outer(ax[k], bx[k])
    fv = _fred_f(fkind)(xs)
    phi = np.linalg.solve(np.eye(n + 1) - float(lam) * (w[None, :] * K), fv)
    return float(phi[int(round(_XS_B * n))])


def golden_b237(lam: float = 0.5) -> float:
    """K=1+xt, f=1, λ=0.5 ⇒ φ(0.5)=77/28≈2.705882353。"""
    return _fredholm_exact(lam, 'lin2', 'one')


def cand_b237(lam: float = 0.5, n: int = 512) -> float:
    return _fredholm_nystrom(lam, n, 'lin2', 'one')


def golden_b238(lam: float = 0.9) -> float:
    """K=1+xt, f=e^x, λ=0.9 ⇒ φ(0.5)≈−12.543502293。"""
    return _fredholm_exact(lam, 'lin2', 'exp')


def cand_b238(lam: float = 0.9, n: int = 512) -> float:
    return _fredholm_nystrom(lam, n, 'lin2', 'exp')


def golden_b239(lam: float = 0.4) -> float:
    """K=1+xt+x²t², f=1, λ=0.4 ⇒ φ(0.5)≈2.217351712。"""
    return _fredholm_exact(lam, 'lin3', 'one')


def cand_b239(lam: float = 0.4, n: int = 512) -> float:
    return _fredholm_nystrom(lam, n, 'lin3', 'one')


def golden_b240(lam: float = 0.8) -> float:
    """K=1+xt, f=cos(πx), λ=0.8 ⇒ φ(0.5)≈6.079271019。"""
    return _fredholm_exact(lam, 'lin2', 'cos')


def cand_b240(lam: float = 0.8, n: int = 512) -> float:
    return _fredholm_nystrom(lam, n, 'lin2', 'cos')


# ======================================================================
# 族 C · 三次样条插值逼近（B241-B244）
# ======================================================================
#   自然三次样条：内点方程 M_{j−1} + 4M_j + M_{j+1} = 6·Δ²y_j / h²,  M_0 = M_n = 0
#   分段求值 S(x) = M_j a³/6h + M_{j+1} b³/6h + (y_j − M_j h²/6)a/h + (y_{j+1} − M_{j+1}h²/6)b/h
#   （a = x_{j+1} − x, b = x − x_j）
#   ★ x₀ 必须自动搜索确定（血案 5：点值误差含 t²(1−t)² 因子，x₀ 落格点邻域 ⇒ 非单调）。

_FUNCS = {
    'e05s4': (lambda x: np.exp(0.5 * x) * np.sin(4 * x), 'exp(0.5x)·sin(4x)'),
    'at3': (lambda x: np.arctan(3 * x), 'arctan(3x)'),
    'e2x': (lambda x: np.exp(2 * x), 'exp(2x)'),
    'rec': (lambda x: 1.0 / (0.5 + x), '1/(0.5+x)'),
}


def _spline_natural(f, n, xq):
    """均匀节点自然三次样条在 xq 处求值（n 为区间数）。"""
    n = int(n)
    h = 1.0 / n
    xk = np.linspace(0.0, 1.0, n + 1)
    yk = f(xk)
    N = n + 1
    lo = np.zeros(N)
    dg = np.ones(N)
    up = np.zeros(N)
    rhs = np.zeros(N)
    for i in range(1, n):
        lo[i] = 1.0
        dg[i] = 4.0
        up[i] = 1.0
        rhs[i] = 6.0 * (yk[i + 1] - 2.0 * yk[i] + yk[i - 1]) / h ** 2
    M = _thomas(lo, dg, up, rhs)
    j = int(math.floor(xq / h))
    j = min(max(j, 0), n - 1)
    a = xk[j + 1] - xq
    b = xq - xk[j]
    return float(M[j] * a ** 3 / (6.0 * h) + M[j + 1] * b ** 3 / (6.0 * h)
                 + (yk[j] - M[j] * h ** 2 / 6.0) * a / h
                 + (yk[j + 1] - M[j + 1] * h ** 2 / 6.0) * b / h)


def _c_val(fkind, xq):
    return float(_FUNCS[fkind][0](np.array([xq]))[0])


def golden_b241(xq: float = 0.4585) -> float:
    """exp(0.5x)·sin(4x) 在 x₀=0.4585 的精确值 1.214344511。"""
    return _c_val('e05s4', xq)


def cand_b241(xq: float = 0.4585, n: int = 64) -> float:
    return _spline_natural(_FUNCS['e05s4'][0], n, xq)


def golden_b242(xq: float = 0.4165) -> float:
    """arctan(3x) 在 x₀=0.4165 的精确值 0.895860215。"""
    return _c_val('at3', xq)


def cand_b242(xq: float = 0.4165, n: int = 64) -> float:
    return _spline_natural(_FUNCS['at3'][0], n, xq)


def golden_b243(xq: float = 0.3960) -> float:
    """exp(2x) 在 x₀=0.3960 的精确值 2.207807629。"""
    return _c_val('e2x', xq)


def cand_b243(xq: float = 0.3960, n: int = 64) -> float:
    return _spline_natural(_FUNCS['e2x'][0], n, xq)


def golden_b244(xq: float = 0.6040) -> float:
    """1/(0.5+x) 在 x₀=0.6040 的精确值 0.905797101。"""
    return _c_val('rec', xq)


def cand_b244(xq: float = 0.6040, n: int = 64) -> float:
    return _spline_natural(_FUNCS['rec'][0], n, xq)


# ======================================================================
# 族 D · 非线性两点边值问题 · 打靶法（B245-B248）
# ======================================================================
#   候选：把 y''=f(x,y,y') 化为一阶系统 (y, z=y')，以未知初斜率 s 从 x=0 用 **RK4**
#   积分 n 步，用「网格找符号变化 + 割线/二分混合」把 y(1) 调到给定右端 BC。
#   四族闭式（**均以形状/边界参数自由参数化**，见血案 4）：
#     B245  y''=6β²y²,  y(0)=1, y(1)=(1+β)^{−2}      ⇒ y=(1+βx)^{−2}
#     B246  y''=2β²y³,  y(0)=1, y(1)=(1+β)^{−1}      ⇒ y=(1+βx)^{−1}
#     B247  y''=2yy',   y(0)=0, y(1)=√c·tan√c        ⇒ y=√c·tan(√c x)
#     B248  y''+(y')²=0, y(0)=0, y(1)=y1             ⇒ y=ln(1+x(e^{y1}−1))

_XS_D = 0.5


def _rk4(f, y0, s, n, xstar):
    """RK4 积分 (y,z)=(y,y')，返回 (y(1), y(xstar))。"""
    h = 1.0 / n
    y = float(y0)
    z = float(s)
    x = 0.0
    ys = None
    for _ in range(n):
        k1y = z
        k1z = f(x, y, z)
        k2y = z + 0.5 * h * k1z
        k2z = f(x + 0.5 * h, y + 0.5 * h * k1y, z + 0.5 * h * k1z)
        k3y = z + 0.5 * h * k2z
        k3z = f(x + 0.5 * h, y + 0.5 * h * k2y, z + 0.5 * h * k2z)
        k4y = z + h * k3z
        k4z = f(x + h, y + h * k3y, z + h * k3z)
        y += h / 6.0 * (k1y + 2.0 * k2y + 2.0 * k3y + k4y)
        z += h / 6.0 * (k1z + 2.0 * k2z + 2.0 * k3z + k4z)
        x += h
        if abs(x - xstar) < 1e-12:
            ys = y
    return y, ys


def _shoot(f, y0, y1, n, s_lo, s_hi, ngrid=160):
    """网格扫符号变化 + 有限性过滤 + 割线/二分混合（血案 2：对爆破解鲁棒）。"""
    def g(s):
        try:
            v = _rk4(f, y0, s, n, _XS_D)[0]
        except (OverflowError, FloatingPointError):
            return float('nan')
        if not math.isfinite(v):
            return float('nan')
        return v - y1

    grid = np.linspace(s_lo, s_hi, ngrid)
    vals = [g(s) for s in grid]
    lo = hi = None
    for i in range(ngrid - 1):
        va, vb = vals[i], vals[i + 1]
        if math.isfinite(va) and math.isfinite(vb) and va * vb < 0.0:
            lo, hi = float(grid[i]), float(grid[i + 1])
            break
    if lo is None:
        raise RuntimeError('打靶法未找到括号（y1=%r）' % (y1,))
    fl, fh = g(lo), g(hi)
    for _ in range(200):
        den = fh - fl
        if abs(den) < 1e-300:
            break
        s = hi - fh * (hi - lo) / den
        if not (lo < s < hi):
            s = 0.5 * (lo + hi)
        fs = g(s)
        if abs(fs) < 1e-15:
            break
        if fs * fl < 0.0:
            hi, fh = s, fs
        else:
            lo, fl = s, fs
    return _rk4(f, y0, s, n, _XS_D)[1]


def _f245(x, y, z):
    return 6.0 * y ** 2


def golden_b245(beta: float = 1.0) -> float:
    """y''=6β²y², y(0)=1, y(1)=(1+β)^{−2} ⇒ y(0.5)=(1+0.5β)^{−2}（β=1 ⇒ 4/9）。"""
    return float((1.0 + float(beta) * _XS_D) ** -2)


def cand_b245(beta: float = 1.0, n: int = 32) -> float:
    beta = float(beta)
    return _shoot(_f245, 1.0, (1.0 + beta) ** -2, n, -6.0, -0.05)


def _f246(x, y, z):
    return 2.0 * y ** 3


def golden_b246(beta: float = 1.0) -> float:
    """y''=2β²y³, y(0)=1, y(1)=(1+β)^{−1} ⇒ y(0.5)=(1+0.5β)^{−1}（β=1 ⇒ 2/3）。"""
    return float((1.0 + float(beta) * _XS_D) ** -1)


def cand_b246(beta: float = 1.0, n: int = 32) -> float:
    beta = float(beta)
    return _shoot(_f246, 1.0, (1.0 + beta) ** -1, n, -6.0, -0.05)


def _f247(x, y, z):
    return 2.0 * y * z


def golden_b247(cc: float = 1.0) -> float:
    """y''=2yy', y(0)=0, y(1)=√c·tan√c ⇒ y(0.5)=√c·tan(0.5√c)（c=1 ⇒ tan 0.5）。"""
    rc = math.sqrt(float(cc))
    return float(rc * math.tan(rc * _XS_D))


def cand_b247(cc: float = 1.0, n: int = 32) -> float:
    cc = float(cc)
    return _shoot(_f247, 0.0, math.sqrt(cc) * math.tan(math.sqrt(cc)), n, 0.05, 2.0)


def _f248(x, y, z):
    return -(z * z)


def golden_b248(y1: float = 1.0) -> float:
    """y''+(y')²=0, y(0)=0, y(1)=y1 ⇒ y(0.5)=ln(1+0.5(e^{y1}−1))（y1=1 ⇒ ln(1+(e−1)/2)）。"""
    return float(math.log(1.0 + _XS_D * (math.exp(float(y1)) - 1.0)))


def cand_b248(y1: float = 1.0, n: int = 32) -> float:
    y1 = float(y1)
    return _shoot(_f248, 0.0, y1, n, 0.05, 12.0)


# ======================================================================
# 锚表 / 容差 / 候选分派
# ======================================================================

_TOL = 0.01

# 逐锚 tol：本批指标量级（族 A 0.135~0.695；族 B −12.54~6.08；族 C 0.906~2.208；
# 族 D 0.444~0.667）——**每一锚的 |golden| 均 ≥ 13.5× tol**，统一 tol=0.01 即可
# （血案 7：族 C 原 cos(4πx) 方案 golden=0.00628 < tol ⇒ 已换函数，非放宽 tol）。
# worst-case 余量 B240 366×；最弱反向信号 B246 2.15× tol（>1.4× 门槛）。
_TOL_BY_BID = {
    "B233": 0.01, "B234": 0.01, "B235": 0.01, "B236": 0.01,
    "B237": 0.01, "B238": 0.01, "B239": 0.01, "B240": 0.01,
    "B241": 0.01, "B242": 0.01, "B243": 0.01, "B244": 0.01,
    "B245": 0.01, "B246": 0.01, "B247": 0.01, "B248": 0.01,
}

# 反向测试注册键（C5：key ×1.1 的信号须 > tol；族 A 观测点已移到边界层敏感区 x*=0.9，
# 避免血案 6「观测点落边界层平台区 ⇒ 信号 0.11×tol」）
_PERTURB_KEYS = {
    "B233": ("pe",), "B234": ("pe",), "B235": ("pe",), "B236": ("pe",),
    "B237": ("lam",), "B238": ("lam",), "B239": ("lam",), "B240": ("lam",),
    "B241": ("xq",), "B242": ("xq",), "B243": ("xq",), "B244": ("xq",),
    "B245": ("beta",), "B246": ("beta",), "B247": ("cc",), "B248": ("y1",),
}

# 每锚物理参数（= benchmarks.py 的 default_params；harness 以 golden_fn(**params) 调）
_DEFAULT_PARAMS = {
    "B233": {"pe": 3.5}, "B234": {"pe": 5.0}, "B235": {"pe": 10.0}, "B236": {"pe": 20.0},
    "B237": {"lam": 0.5}, "B238": {"lam": 0.9}, "B239": {"lam": 0.4}, "B240": {"lam": 0.8},
    "B241": {"xq": 0.4585}, "B242": {"xq": 0.4165}, "B243": {"xq": 0.3960}, "B244": {"xq": 0.6040},
    "B245": {"beta": 1.0}, "B246": {"beta": 1.0}, "B247": {"cc": 1.0}, "B248": {"y1": 1.0},
}

# bid -> (golden_fn, cand_fn, 默认离散参数, 离散参数名, 参数标签)
_CASES = {
    # ---- 族 A：定常对流–扩散（中心差分） ----
    "B233": (golden_b233, cand_b233, 640, "n", "对流-扩散 Pe=3.5, θ(0.9)"),
    "B234": (golden_b234, cand_b234, 640, "n", "对流-扩散 Pe=5, θ(0.9)"),
    "B235": (golden_b235, cand_b235, 640, "n", "对流-扩散 Pe=10, θ(0.9)"),
    "B236": (golden_b236, cand_b236, 640, "n", "对流-扩散 Pe=20, θ(0.9)"),
    # ---- 族 B：Fredholm 第二类可分核（Nyström） ----
    "B237": (golden_b237, cand_b237, 512, "n", "Fredholm K=1+xt, f=1, λ=0.5, φ(0.5)"),
    "B238": (golden_b238, cand_b238, 512, "n", "Fredholm K=1+xt, f=e^x, λ=0.9, φ(0.5)"),
    "B239": (golden_b239, cand_b239, 512, "n", "Fredholm K=1+xt+x²t², f=1, λ=0.4, φ(0.5)"),
    "B240": (golden_b240, cand_b240, 512, "n", "Fredholm K=1+xt, f=cosπx, λ=0.8, φ(0.5)"),
    # ---- 族 C：三次样条插值逼近（自然样条） ----
    "B241": (golden_b241, cand_b241, 64, "n", "样条逼近 exp(0.5x)sin(4x), x₀=0.4585"),
    "B242": (golden_b242, cand_b242, 64, "n", "样条逼近 arctan(3x), x₀=0.4165"),
    "B243": (golden_b243, cand_b243, 64, "n", "样条逼近 exp(2x), x₀=0.3960"),
    "B244": (golden_b244, cand_b244, 64, "n", "样条逼近 1/(0.5+x), x₀=0.6040"),
    # ---- 族 D：非线性两点边值（打靶法） ----
    "B245": (golden_b245, cand_b245, 32, "n", "BVP y''=6β²y², β=1, y(0.5)"),
    "B246": (golden_b246, cand_b246, 32, "n", "BVP y''=2β²y³, β=1, y(0.5)"),
    "B247": (golden_b247, cand_b247, 32, "n", "BVP y''=2yy', c=1, y(0.5)"),
    "B248": (golden_b248, cand_b248, 32, "n", "BVP y''+(y')²=0, y1=1, y(0.5)"),
}


def _golden_by_bid(bid):
    """按 bid 算 golden（物理参数取 _DEFAULT_PARAMS）。"""
    return _CASES[bid][0](**_DEFAULT_PARAMS[bid])


def _cand_by_bid(bid, disc=None):
    """按 bid 算候选：物理参数取 _DEFAULT_PARAMS，离散参数 disc 可覆盖（默认取定档）。"""
    _g, cf, dd, dn, _lbl = _CASES[bid]
    kw = dict(_DEFAULT_PARAMS[bid])
    kw[dn] = dd if disc is None else disc
    return cf(**kw)


# ======================================================================
# 自检
# ======================================================================


def _self_test():
    print("=" * 76)
    print("Batch B-14 数值核自检（16 锚）")
    print("=" * 76)

    print("\n[闭式极限自检] 候选在细档下应收敛到 golden 闭式")
    print("  A1 对流-扩散 Pe=5 n=5120   : %.12f  闭式=%.12f"
          % (_conv_central(5.0, 5120), _conv_exact(5.0)))
    print("  A2 对流-扩散 Pe=20 n=5120  : %.12f  闭式=%.12f"
          % (_conv_central(20.0, 5120), _conv_exact(20.0)))
    print("  B1 Fredholm K=1+xt n=2048  : %.12f  闭式=%.12f"
          % (_fredholm_nystrom(0.5, 2048, 'lin2', 'one'), _fredholm_exact(0.5, 'lin2', 'one')))
    print("  B2 Fredholm K=lin3 n=2048  : %.12f  闭式=%.12f"
          % (_fredholm_nystrom(0.4, 2048, 'lin3', 'one'), _fredholm_exact(0.4, 'lin3', 'one')))
    print("  C1 样条 exp(2x) n=1024     : %.12f  闭式=%.12f"
          % (_spline_natural(_FUNCS['e2x'][0], 1024, 0.3960), _c_val('e2x', 0.3960)))
    print("  C2 样条 1/(0.5+x) n=1024   : %.12f  闭式=%.12f"
          % (_spline_natural(_FUNCS['rec'][0], 1024, 0.6040), _c_val('rec', 0.6040)))
    print("  D1 BVP y''=2β²y³ n=512     : %.12f  闭式=%.12f"
          % (cand_b246(1.0, 512), golden_b246(1.0)))
    print("  D2 BVP y''+(y')²=0 n=512   : %.12f  闭式=%.12f"
          % (cand_b248(1.0, 512), golden_b248(1.0)))

    print("\n[主表] golden / candidate / 残差 / 余量")
    rows = []
    for bid in _CASES:
        label = _CASES[bid][4]
        g = _golden_by_bid(bid)
        c = _cand_by_bid(bid)
        d = abs(c - g)
        rows.append((bid, label, g, c, d, _TOL_BY_BID[bid] / d if d > 0 else float("inf")))
    worst = None
    for bid, label, g, c, d, mar in sorted(rows):
        print("  %s %-44s g=%.9f c=%.9f |Δ|=%.3e 余量=%.1f×" % (bid, label, g, c, d, mar))
        if worst is None or mar < worst[1]:
            worst = (bid, mar)
    print("  最小余量: %s %.1f×" % worst)

    print("\n[反向信号] 注册键 ×1.1 ⇒ 信号量 / 与 tol 比（须 >1.4×）")
    weakest = None
    for bid in sorted(_CASES):
        g = _golden_by_bid(bid)
        sigs = []
        for k in _PERTURB_KEYS[bid]:
            p2 = dict(_DEFAULT_PARAMS[bid])
            p2[k] = p2[k] * 1.1
            g2 = _CASES[bid][0](**p2)
            sigs.append(abs(g2 - g))
        r = min(sigs) / _TOL_BY_BID[bid] if sigs else float("nan")
        print("  %s keys=%s 信号=%s  min信号/tol=%.2f"
              % (bid, _PERTURB_KEYS[bid], " ".join("%.3e" % s for s in sigs), r))
        if weakest is None or r < weakest[1]:
            weakest = (bid, r)
    print("  最弱反向信号: %s %.2f×tol" % weakest)

    print("\n[判据 D] 只扫候选离散参数（残差须浮出噪声地板且单调收敛）")
    scans = {
        "B233": [20, 40, 80, 160, 320, 640], "B234": [20, 40, 80, 160, 320, 640],
        "B235": [20, 40, 80, 160, 320, 640], "B236": [20, 40, 80, 160, 320, 640],
        "B237": [16, 32, 64, 128, 256, 512], "B238": [16, 32, 64, 128, 256, 512],
        "B239": [16, 32, 64, 128, 256, 512], "B240": [16, 32, 64, 128, 256, 512],
        "B241": [8, 16, 32, 64, 128, 256], "B242": [8, 16, 32, 64, 128, 256],
        "B243": [8, 16, 32, 64, 128, 256], "B244": [8, 16, 32, 64, 128, 256],
        "B245": [4, 8, 16, 32], "B246": [4, 8, 16, 32],
        "B247": [4, 8, 16, 32], "B248": [4, 8, 16, 32],
    }
    allok = True
    for bid in sorted(scans):
        g = _golden_by_bid(bid)
        ds = [abs(_cand_by_bid(bid, p_) - g) for p_ in scans[bid]]
        mono = all(ds[i + 1] < ds[i] for i in range(len(ds) - 1))
        ok = (ds[0] > 1e-13) and (ds[-1] < _TOL_BY_BID[bid]) and mono
        allok = allok and ok
        print("  %s %s 首=%.3e 末=%.3e 单调=%s" % (bid, "OK " if ok else "BAD", ds[0], ds[-1], mono))
        print("      残差链: " + " ".join("%.2e" % d for d in ds))

    print("\nALL_OK=%s" % allok)
    return allok


if __name__ == "__main__":
    _self_test()
