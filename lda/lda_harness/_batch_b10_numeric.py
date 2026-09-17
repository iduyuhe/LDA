# -*- coding: utf-8 -*-
"""Batch B-10 双方法独立锚数值核（路径 B 扩基续九 · v0.9.90 · 继续稀释 terminal）

四族（目标全 strict，纯内部确定性扩基）：
  A. Mathieu 方程特征值（周期系数 ODE；MEMS 参数激励 / 屈曲）      B169-B173（5 道）
       golden: scipy.special.mathieu_a/b(m, q)（IEEE Mathieu 特征值，机器精度）
       cand  : 半周期 [0,π/2] **P1-FEM 广义本征**（BC 组合选族）
       BC 映射：(N,N)→a₀,a₂,…；(N,D)→a₁,a₃,…；(D,N)→b₁,b₃,…；(D,D)→b₂,b₄,…
       🔴 本族是**新方程类**：周期系数（Hill 方程特例 y''+(a−2q·cos2x)y=0），
          既有 186 道锚全为常系数（Dirichlet 盒 / 谐振子 / 库仑 / 数值势阱）。
  B. 椭圆积分（第一/二类）与椭球静电去极化因子（初等闭式）        B174-B179（6 道）
       B174/B175: 椭圆截面几何周长 L = 4a·E(m)，m = 1 − b²/a²（a=2/3 µm, b=1 µm）
       B176/B177: 大摆角单摆周期比 T/T₀ = (2/π)·K(m)，m = sin²(θ₀/2)（θ₀=135°/150°）
       B178: 扁椭球（a=b>c）c 轴去极化因子 N_c = (1/e²)[1 − (1/e)·asin(e)·√(1−e²)]
       B179: 长椭球（a>b=c）a 轴去极化因子 N_a = ((1−e²)/e³)[½·ln((1+e)/(1−e)) − e]
       cand  : **复合 Simpson 求积**（s→t 解析变换 + 解析标度还原）——纯数值积分，
               不调用任何特殊函数
       🔴 **新特殊函数类**：椭圆积分 E(m)/K(m)。既有锚已占用 erfc(B30)/Γ/Bessel
          J 零点/球 Bessel/Legendre/Airy（全未含椭圆积分），三者互不同源。
  C. Fresnel（Cornu）积分——衍射半波带                            B180-B181（2 道）
       golden: scipy.special.fresnel(u) ⇒ (S, C)
       cand  : 复合 Simpson ∫₀^u cos(πt²/2)dt / ∫₀^u sin(πt²/2)dt（振荡被积）
       🔴 **新特殊函数类**：Fresnel 积分，既有锚无。
  D. 线性扩散方程基础解（热核）+ **时间推进格式**验证               B182-B184（3 道）
       golden: 中心归一高斯基础解 R(x) = C(x,t)/C(0,t) = exp(−x²/(4Dt))（精确）
       cand  : 有限域 [0,L] **双端零通量（Neumann ghost）Crank-Nicolson 时间推进**
               的同一归一剖面（相邻格点线性插值取值）
       取参：D=1e-18 m²/s、t₀=600 s、t₁=1800 s、x = 50/120/200 nm、M=4000、nt=960
       🔴 本族是**新数值方法类**：时间推进（marching）。既有 186 道锚全为本征值 /
          稳态求解，**无一做时间积分**。与 B29（稳态散热鳍**椭圆** ODE，非时间相关）、
          T1-B（漂移-扩散**稳态** Gummel：含漂移项 + 泊松耦合 + 非线性迭代）
          **均不同**（本族无漂移项、无泊松耦合、无非线性迭代、纯抛物型时间推进）。
       🔴 同源体检被否候选：半导体扩散 C = Cs·erfc(x/2√(Dt)) —— **数值同源**
          （erfc 已被 B30 占用）+ **结构同源**（项目已有 T1-B 漂移-扩散内核）
          ⇒ 改用**高斯基础解（热核）**：公式不同（Gaussian ≠ erfc）、问题不同
          （有限剂量守恒扩散 ≠ 恒定表面源半无限扩散）。

同源体检（本批第一道闸，v0.9.90 立）：机械盘点既有 186 道锚占用的特殊函数 / 方程类
（1D/2D/3D Dirichlet 盒、1D/2D/3D 及各向异性谐振子、Coulomb/氢（径向/2D/高激发）、
Bessel J 零点、球 Bessel 零点、Legendre、Airy 三角阱、方势阱/方垒、Pöschl-Teller、
Morse、Hulthen、Rosen-Morse II、Marcatili 超越方程、转移矩阵多层膜、Bragg、AB 环、
4 阶梁、Fock-Darwin、erfc(B30)、热光鳍(B29)）：
  A：周期系数 ODE（新）· B：椭圆积分/椭球静电（新）· C：Fresnel 振荡积分（新）·
  D：抛物型时间推进（新方法类）。
  被否候选：① 半导体扩散 erfc（见 D 族说明）。
            ② **Carlson 椭球积分**（scipy `elliprd`/`elliprf`）作 golden —— **数值同源**
               （与既有特殊函数库共依赖）⇒ 改**初等反正弦/对数闭式**作 golden。
            ③ **Mathieu 的 Floquet 三对角（FG）矩阵**作候选 —— 与 scipy `mathieu_a/b`
               在 N=8 即一致到 1e-16 ⇒ **判据 D 撞「代数恒等」红线**（残差不随离散
               参数单调变化 ⇒ 非独立数值方法）⇒ 改**半周期 P1-FEM 广义本征**。

方法学独立：每道锚 golden 走「特殊函数机器精度值 / 初等闭式」，候选走
「FEM 广义本征 / 复合求积 / 时间推进」——两者不同源；残差 = 离散化误差
（持久、判据 D 响应），非代数恒等（B28 血案）、非纯数值沉底（B10 血案）。

🔴 血案规避（承接 B-5 / B-6 / B-7 / B-8 / B-9）：
  1) **一律弃用 `scipy.linalg.eigh(subset_by_index=...)`**（B-6 off-by-one 血案）。
     本模块族 A 用**稠密广义本征** `scipy.linalg.eigh(K, M, eigvals_only=True)`
     + `np.sort` 取全谱第 k 个（N=800 ⇒ 401/801 阶，规模可控）；族 D 用
     `scipy.linalg.solve_banded` 解三对角方程组。
  2) **Mathieu FG 矩阵红线**（B-10 血案）：见上被否候选 ③。改用**半周期 P1-FEM**：
     刚度阵 A[i,i]=2/h、A[i,i±1]=−1/h；集中质量阵 M[i,i]=h；**Neumann 端点自然
     边界修正 A[i,i]=1/h 且 M[i,i]=h/2**（Dirichlet 端点仅 M=h，节点被剔除）。
     残差 ~1e-7..1e-4 且严格 O(h²)（近 N=800 时）。
  3) **椭球积分的标度陷阱**（B-10 血案）：Gauss-Legendre 直接对 s∈[0,∞) 求积时被积
     函数尺度 ~a⁻²≈1e-14 ⇒ 求积结果归零。改用 **s→t 解析变换**（s = c²t/(1−t) 或
     s = b²t/(1−t)）+ 复合 Simpson，并按变换后的**解析标度**还原：
       扁椭球 N_c = (A/2)·∫₀¹ (1−t)^½/[A(1−t)+t] dt，A=(a/c)²
       长椭球 N_a = (ar/2)·∫₀¹ (1−t)^½/[A(1−t)+t]^{3/2} dt，A=(a/b)²=ar²
     🔴 血案细节：标度若漏掉 a/c 或写成 (a²/2)（仅在 c=1 时巧合正确），
        非单位轴比下会偏 6.25× 量级。
  4) **CN 扩散单端 Dirichlet 血案**（B-10）：自由扩散（有限剂量）必须是**双端零通量**
     （ghost `Cp[0]=Cp[2]`、`Cp[M+2]=Cp[M]`；行 0 超对角改 −2r、末行次对角改 −2r），
     单端固定 Dirichlet 会引入 **17% 系统偏差**。
     **一步保持性自检**：以解析解为初值走 1 步，M=500 时 max rel dev 1.1e-5 /
     M=2000 时 6.9e-7（确认差分算子与边界 ghost 正确）。
     🔴 **采样点禁用格点吸附**：`int(round(x/h))` 会让残差退化为**格点量化误差**
     （O(h)，随 M 不单调 —— M=2000 三点恰压在格点上残差极小、M=3000 偏 1.3% ⇒
     残差跃至 6.6e-3、余量只剩 1.5×）。**必须相邻两格点线性插值**。
     🔴 **x 取值须逐点验单调**：归一比值 R(x)=C(x)/C(0) 的误差含分子/分母**同源
     相消**，个别 (x, M) 组合会出现巧合极小（实测 x=100 nm 在 M=500 时残差
     1.1e-4 反而小于 M=1000 的 2.75e-4 ⇒ 非单调）。本模块取 **x=50/120/200 nm**
     （逐点扫描确认全单调、且余量 ≥499×）。
  5) **`default_params` 键集必须 ⊆ golden 形参集**（B-7 血案）：态指标（m/ar/kind）
     收在 golden/cand 的硬编码或默认形参里，避免 `**params` 展开时 `TypeError`。
  6) **超收敛 ⇒ round-off 地板假象**（B-10 新增体检）：族 B 的椭圆/单摆被积函数解析
     且近似周期光滑，Simpson 呈**超收敛** —— 椭圆周长 n=32 时残差**恰为 0.0**
     （判据 D 会误判为「代数恒等」）、n=64 时仅 1.8e-15（噪声地板）；
     θ₀=90° 单摆 n=20 亦残差归零。**取 n 时必须落在离散误差主导区**（残差 ≫ 2.2e-16
     且随 n 单调）：椭圆 n=12、单摆 n=16 ⇒ 残差 7.9e-8..3.8e-5。
     🔴 教训：求积类候选的 n **不是越大越好**；n 过大 = 用机器精度掩盖数值方法。
  7) **候选形参单位必须与 golden 一致**（B-10 血案）：族 D 初版 `diffusion_ratio_cn`
     按 µm 换算而 golden 走 nm ⇒ 索引 25000 越界。统一形参单位 = nm。
"""

import math

import numpy as np
from scipy.linalg import eigh, solve_banded
from scipy.special import ellipe, ellipk, fresnel, mathieu_a, mathieu_b

# ---------------------------------------------------------------------------
# 单位 / 常数（族 D 的扩散系数为归一化示意，非 PDK 声明）
# ---------------------------------------------------------------------------
NM = 1.0e-9
PI = math.pi

# 族 D 默认物理设置（归一化扩散模型：绝对物性为示意、非 PDK 声明）
_D_DIFF = 1.0e-18        # m²/s，归一化扩散系数
_D_T0 = 600.0            # s，初值时刻（解析高斯）
_D_T1 = 1800.0           # s，目标时刻
_D_L_UM = 4.0            # µm，有限域长度（≫ 扩散长度，边界反射可忽略）
_D_M = 4000              # 空间节点数
_D_NT = 960              # 时间步数（r = D·dt/(2h²) = 0.625）


# ===========================================================================
# 通用：复合 Simpson 求积（纯数值，不调用特殊函数）
# ===========================================================================
def _simpson(f, a: float, b: float, n: int) -> float:
    """复合 Simpson 求积（n 为子区间数，自动取偶；端点含 a、b）。"""
    if n % 2:
        n += 1
    x = np.linspace(a, b, n + 1)
    y = f(x)
    h = (b - a) / n
    return float(h / 3.0 * (y[0] + y[-1] + 4.0 * y[1:-1:2].sum() + 2.0 * y[2:-2:2].sum()))


# ===========================================================================
# 族 A：Mathieu 方程特征值（周期系数 ODE）（B169-B173）
#   y'' + (a − 2q·cos 2x)·y = 0
#   golden: scipy.special.mathieu_a(m,q) / mathieu_b(m,q)（机器精度）
#   cand  : 半周期 [0,π/2] P1-FEM 广义本征（BC 组合选族）
#       弱形式 −y'' + 2q·cos2x·y = a·y ⇒ (A_stiff + M·V)·v = a·M·v
#       A[i,i]=2/h、A[i,i±1]=−1/h；M[i,i]=h；Neumann 端点 A=1/h、M=h/2
# ===========================================================================
def mathieu_char_fem(q: float, m: int, kind: str, N: int = 800) -> float:
    """候选：半周期 P1-FEM 广义本征求 Mathieu 特征值 a_m 或 b_m。

    kind='a' ⇒ 偶族（cos 型）→ mathieu_a；kind='b' ⇒ 奇族（sin 型）→ mathieu_b。
    🔴 Neumann 端 = 弱形式自然边界（A=1/h、M=h/2）；Dirichlet 端剔除节点。
    """
    if kind == "a":
        bc0 = "N"
        bc1 = "N" if (m % 2 == 0) else "D"
        k = m // 2
    else:
        bc0 = "D"
        bc1 = "N" if (m % 2 == 1) else "D"
        k = (m - 1) // 2
    L = PI / 2.0
    h = L / N
    if bc0 == "N" and bc1 == "N":
        nodes = np.arange(0, N + 1)
    elif bc0 == "N" and bc1 == "D":
        nodes = np.arange(0, N)
    elif bc0 == "D" and bc1 == "N":
        nodes = np.arange(1, N + 1)
    else:
        nodes = np.arange(1, N)
    x = nodes * h
    n = len(nodes)
    A = np.zeros((n, n))
    M = np.zeros((n, n))
    for i in range(n):
        A[i, i] = 2.0 / h
        M[i, i] = h
        if i + 1 < n:
            A[i, i + 1] = -1.0 / h
            A[i + 1, i] = -1.0 / h
    if bc0 == "N":
        A[0, 0] = 1.0 / h
        M[0, 0] = 0.5 * h
    if bc1 == "N":
        A[-1, -1] = 1.0 / h
        M[-1, -1] = 0.5 * h
    V = 2.0 * q * np.cos(2.0 * x)
    K = A + np.diag(M.diagonal() * V)
    w = np.sort(np.real(eigh(K, M, eigvals_only=True)))
    return float(w[k])


def cand_mathieu(kind, m, q, N: int = 800) -> float:
    """候选工厂：Mathieu 特征值 a_m / b_m（无量纲）。"""
    return mathieu_char_fem(float(q), int(m), str(kind), N=int(N))


def golden_b169(q: float = 1.0) -> float:
    """Mathieu 偶族特征值 a₀(q)。"""
    return float(mathieu_a(0, q))


def golden_b170(q: float = 1.0) -> float:
    """Mathieu 偶族特征值 a₁(q)。"""
    return float(mathieu_a(1, q))


def golden_b171(q: float = 1.0) -> float:
    """Mathieu 奇族特征值 b₁(q)。"""
    return float(mathieu_b(1, q))


def golden_b172(q: float = 1.0) -> float:
    """Mathieu 奇族特征值 b₂(q)。"""
    return float(mathieu_b(2, q))


def golden_b173(q: float = 1.0) -> float:
    """Mathieu 偶族特征值 a₂(q)。"""
    return float(mathieu_a(2, q))


# ===========================================================================
# 族 B：椭圆积分与椭球静电去极化因子（B174-B179）
#   golden: scipy.special.ellipe/ellipk（机器精度）+ 初等反正弦/对数闭式
#   cand  : 复合 Simpson（s→t 解析变换 + 解析标度还原）
# ===========================================================================
def ellipse_perimeter_closed(a_um: float, b_um: float) -> float:
    """golden：椭圆截面几何周长（µm），L = 4a·E(m)，m = 1 − b²/a²。"""
    m = 1.0 - (b_um / a_um) ** 2
    return 4.0 * a_um * float(ellipe(m))


def ellipse_perimeter_simpson(a_um: float, b_um: float, n: int = 12) -> float:
    """候选：复合 Simpson 4·∫₀^{π/2} √(a²sin²θ + b²cos²θ) dθ（µm）。

    🔴 与 golden 的差异：golden 走椭圆积分 E(m) 特殊函数；候选走纯数值求积。
    🔴 **n=12 而非 n=64**（B-10 血案）：本被积函数解析且近似周期光滑，Simpson
       呈**超收敛** —— n=32 时残差恰好归零（= 代数恒等假象）、n=64 时仅 1.8e-15
       （round-off 地板）。取 n=12 ⇒ 残差 7.9e-8（a=2,b=1）/ 1.3e-5（a=3,b=1），
       浮出噪声地板 3.5e8× 且随 n **单调**下降（真离散误差）。
    """
    f = lambda th: np.sqrt(a_um * a_um * np.sin(th) ** 2 + b_um * b_um * np.cos(th) ** 2)
    return 4.0 * _simpson(f, 0.0, PI / 2.0, n)


def pendulum_ratio_closed(theta0_rad: float) -> float:
    """golden：大摆角单摆周期比 T/T₀ = (2/π)·K(m)，m = sin²(θ₀/2)。"""
    m = math.sin(theta0_rad / 2.0) ** 2
    return (2.0 / PI) * float(ellipk(m))


def pendulum_ratio_simpson(theta0_rad: float, n: int = 16) -> float:
    """候选：复合 Simpson (2/π)·∫₀^{π/2} dθ/√(1 − m·sin²θ)。

    🔴 **n=16**（B-10 血案）：θ₀=90° 时本积分收敛极快（n=20 即撞 round-off
       地板、残差归零）；θ₀ 越接近 180° 收敛越慢（m→1 端点近奇异）。
       取 n=16 并按 θ₀ = 135° / 150° 取参 ⇒ 残差 3.7e-7 / 3.8e-5（均浮出地板
       ≥1e9×，且随 n 单调下降）。
    """
    m = math.sin(theta0_rad / 2.0) ** 2
    f = lambda th: 1.0 / np.sqrt(1.0 - m * np.sin(th) ** 2)
    return (2.0 / PI) * _simpson(f, 0.0, PI / 2.0, n)


def oblate_Nc_closed(ar: float) -> float:
    """golden：扁椭球（a=b>c）c 轴去极化因子 N_c，ar = a/c > 1。

    N_c = (1/e²)·[1 − (1/e)·asin(e)·√(1−e²)]，e = √(1 − 1/ar²)。
    """
    e = math.sqrt(1.0 - 1.0 / ar ** 2)
    return (1.0 / e ** 2) * (1.0 - (math.sqrt(1.0 - e ** 2) / e) * math.asin(e))


def prolate_Na_closed(ar: float) -> float:
    """golden：长椭球（a>b=c）a 轴去极化因子 N_a，ar = a/b > 1。

    N_a = ((1−e²)/e³)·[½·ln((1+e)/(1−e)) − e]，e = √(1 − 1/ar²)。
    """
    e = math.sqrt(1.0 - 1.0 / ar ** 2)
    return ((1.0 - e ** 2) / e ** 3) * (0.5 * math.log((1.0 + e) / (1.0 - e)) - e)


def oblate_Nc_simpson(ar: float, n: int = 256) -> float:
    """候选：扁椭球 N_c = (A/2)·∫₀¹ (1−t)^½/[A(1−t)+t] dt，A = ar²。

    🔴 s→t 解析变换（s = c²·t/(1−t)）后的**解析标度** A/2 已含轴比，
       漏掉即偏 (a/c)² 量级（B-10 标度血案）。
    """
    A = ar * ar
    f = lambda t: (1.0 - t) ** 0.5 / (A * (1.0 - t) + t)
    return 0.5 * A * _simpson(f, 0.0, 1.0, n)


def prolate_Na_simpson(ar: float, n: int = 256) -> float:
    """候选：长椭球 N_a = (ar/2)·∫₀¹ (1−t)^½/[A(1−t)+t]^{3/2} dt，A = ar²。"""
    A = ar * ar
    f = lambda t: (1.0 - t) ** 0.5 / (A * (1.0 - t) + t) ** 1.5
    return 0.5 * ar * _simpson(f, 0.0, 1.0, n)


def golden_b174(a_um: float = 2.0, b_um: float = 1.0) -> float:
    """椭圆截面周长（a=2 µm, b=1 µm）（µm）。"""
    return ellipse_perimeter_closed(a_um, b_um)


def golden_b175(a_um: float = 3.0, b_um: float = 1.0) -> float:
    """椭圆截面周长（a=3 µm, b=1 µm）（µm）。"""
    return ellipse_perimeter_closed(a_um, b_um)


def golden_b176(theta0_deg: float = 135.0) -> float:
    """大摆角单摆周期比 T/T₀（θ₀=135°）。"""
    return pendulum_ratio_closed(math.radians(theta0_deg))


def golden_b177(theta0_deg: float = 150.0) -> float:
    """大摆角单摆周期比 T/T₀（θ₀=150°）。"""
    return pendulum_ratio_closed(math.radians(theta0_deg))


def golden_b178(ar: float = 2.0) -> float:
    """扁椭球去极化因子 N_c（ar = a/c = 2 ⇒ N_a = N_b = (1−N_c)/2）。"""
    return oblate_Nc_closed(ar)


def golden_b179(ar: float = 2.0) -> float:
    """长椭球去极化因子 N_a（ar = a/b = 2 ⇒ N_b = N_c = (1−N_a)/2）。"""
    return prolate_Na_closed(ar)


def cand_ellipse_perimeter(a_um, b_um) -> float:
    """候选工厂：椭圆截面周长（µm）。"""
    return ellipse_perimeter_simpson(float(a_um), float(b_um))


def cand_pendulum(theta0_deg) -> float:
    """候选工厂：大摆角单摆周期比。"""
    return pendulum_ratio_simpson(math.radians(float(theta0_deg)))


def cand_oblate_Nc(ar) -> float:
    """候选工厂：扁椭球去极化因子 N_c。"""
    return oblate_Nc_simpson(float(ar))


def cand_prolate_Na(ar) -> float:
    """候选工厂：长椭球去极化因子 N_a。"""
    return prolate_Na_simpson(float(ar))


# ===========================================================================
# 族 C：Fresnel（Cornu）积分（B180-B181）
#   C(u)=∫₀^u cos(πt²/2)dt、S(u)=∫₀^u sin(πt²/2)dt
#   golden: scipy.special.fresnel(u) ⇒ (S, C)；cand: 复合 Simpson
# ===========================================================================
def fresnel_C_closed(u: float) -> float:
    """golden：Fresnel 余弦积分 C(u)。"""
    return float(fresnel(u)[1])


def fresnel_S_closed(u: float) -> float:
    """golden：Fresnel 正弦积分 S(u)。"""
    return float(fresnel(u)[0])


def fresnel_C_simpson(u: float, n: int = 64) -> float:
    """候选：复合 Simpson ∫₀^u cos(πt²/2) dt。"""
    return _simpson(lambda t: np.cos(PI * t * t / 2.0), 0.0, u, n)


def fresnel_S_simpson(u: float, n: int = 64) -> float:
    """候选：复合 Simpson ∫₀^u sin(πt²/2) dt。"""
    return _simpson(lambda t: np.sin(PI * t * t / 2.0), 0.0, u, n)


def golden_b180(u: float = 1.0) -> float:
    """Fresnel 余弦积分 C(u=1.0)。"""
    return fresnel_C_closed(u)


def golden_b181(u: float = 1.0) -> float:
    """Fresnel 正弦积分 S(u=1.0)。"""
    return fresnel_S_closed(u)


def cand_fresnel_C(u) -> float:
    """候选工厂：Fresnel 余弦积分 C(u)。"""
    return fresnel_C_simpson(float(u))


def cand_fresnel_S(u) -> float:
    """候选工厂：Fresnel 正弦积分 S(u)。"""
    return fresnel_S_simpson(float(u))


# ===========================================================================
# 族 D：线性扩散方程基础解（热核）+ 时间推进格式验证（B182-B184）
#   ∂C/∂t = D·∂²C/∂x²，有限域 [0,L] 双端零通量（质量守恒）
#   golden: R(x) = C(x,t)/C(0,t) = exp(−x²/(4Dt))（精确，中心归一）
#   cand  : Crank-Nicolson 时间推进（双端 Neumann ghost）的同一归一剖面
#   🔴 一步保持性自检见 _self_test（IC=解析解走 1 步 ⇒ dev ~1e-5）
# ===========================================================================
def _cn_step(Ch: np.ndarray, D: float, dt: float, h: float, n: int) -> np.ndarray:
    """一步 Crank-Nicolson（双端零通量；三对角 solve_banded）。

    🔴 行 0 超对角 −2r、末行次对角 −2r（ghost 反射 ⇒ 系数翻倍）；
       单端固定 Dirichlet 会引入 17% 系统偏差（B-10 血案）。
    """
    r = D * dt / (2.0 * h * h)
    ab = np.zeros((3, n))
    ab[1, :] = 1.0 + 2.0 * r
    ab[0, 1] = -2.0 * r
    ab[0, 2:] = -r
    ab[2, :-2] = -r
    ab[2, n - 2] = -2.0 * r
    rhs = np.empty(n)
    rhs[0] = (1.0 - 2.0 * r) * Ch[0] + 2.0 * r * Ch[1]
    rhs[1:n - 1] = r * Ch[:n - 2] + (1.0 - 2.0 * r) * Ch[1:n - 1] + r * Ch[2:n]
    rhs[n - 1] = 2.0 * r * Ch[n - 2] + (1.0 - 2.0 * r) * Ch[n - 1]
    return solve_banded((1, 1), ab, rhs)


def _cn_run(D: float, t0: float, t1: float, M: int, nt: int,
            L_um: float, Q: float) -> tuple:
    """时间推进返回 (C, h)；C 长度 M+1（节点 0..M，x=0..L）。"""
    L = L_um * 1.0e-6
    h = L / M
    n = M + 1
    x = np.arange(n) * h
    C = Q / math.sqrt(4.0 * PI * D * t0) * np.exp(-x * x / (4.0 * D * t0))
    dt = (t1 - t0) / nt
    for _ in range(nt):
        C = _cn_step(C, D, dt, h, n)
    return C, h


def diffusion_ratio_closed(x_m: float, D: float = _D_DIFF, t1: float = _D_T1) -> float:
    """golden：中心归一高斯基础解 R(x) = exp(−x²/(4Dt))（精确）。"""
    return math.exp(-x_m * x_m / (4.0 * D * t1))


def diffusion_ratio_cn(x_nm: float, D: float = _D_DIFF, t0: float = _D_T0,
                       t1: float = _D_T1, M: int = _D_M, nt: int = _D_NT,
                       Q: float = 1.0, L_um: float = _D_L_UM) -> float:
    """候选：CN 时间推进后的中心归一浓度 R = C(x,t₁)/C(0,t₁)。

    🔴 归一化在**候选自身解**上做（分子分母同源），不注入 golden 信息。
    🔴 形参单位为 **nm**（与 golden_b182/183/184 一致）——初版误按 µm 换算
       ⇒ 索引 25000 越界（B-10 血案）。
    🔴 **采样点必须线性插值**（B-10 血案）：初版把 x 吸附到最近格点
       （`int(round(x/h))`）⇒ 残差被**格点量化误差**主导（O(h) 量级，且随 M
       不单调：M=2000 时三点恰好压在格点上、残差极小；M=3000 时偏 1.3% ⇒
       残差跃至 6.6e-3，余量只剩 1.5×）。改为相邻两格点线性插值后，
       残差回归纯 O(h²) 离散误差且随 M 单调。
    """
    C, h = _cn_run(D, t0, t1, M, nt, L_um, Q)
    xi = x_nm * NM / h
    i0 = int(math.floor(xi))
    if i0 >= M:
        return float(C[M] / C[0])
    w = xi - i0
    val = (1.0 - w) * C[i0] + w * C[i0 + 1]
    return float(val / C[0])


def golden_b182(x_nm: float = 50.0) -> float:
    """归一扩散剖面 R(x)，x=50 nm，t=1800 s。"""
    return diffusion_ratio_closed(x_nm * NM)


def golden_b183(x_nm: float = 120.0) -> float:
    """归一扩散剖面 R(x)，x=120 nm，t=1800 s。"""
    return diffusion_ratio_closed(x_nm * NM)


def golden_b184(x_nm: float = 200.0) -> float:
    """归一扩散剖面 R(x)，x=200 nm，t=1800 s。"""
    return diffusion_ratio_closed(x_nm * NM)


def cand_diffusion(x_nm) -> float:
    """候选工厂：CN 时间推进的中心归一扩散剖面。"""
    return diffusion_ratio_cn(float(x_nm))


# ===========================================================================
# 自测：16/16 golden ↔ cand 残差非零 + 判据 D（物理参数 ×1.1 双向同步偏移）
#       + 族 A/B/D 的极限自检 + 离散参数收敛扫描（严格判据 D）
# ===========================================================================
_CASES = [
    # (锚号, golden_thunk, cand_thunk, D 参数字典)
    ("B169", lambda: golden_b169(1.0),       lambda: cand_mathieu("a", 0, 1.0),      {"q": 1.0}),
    ("B170", lambda: golden_b170(1.0),       lambda: cand_mathieu("a", 1, 1.0),      {"q": 1.0}),
    ("B171", lambda: golden_b171(1.0),       lambda: cand_mathieu("b", 1, 1.0),      {"q": 1.0}),
    ("B172", lambda: golden_b172(1.0),       lambda: cand_mathieu("b", 2, 1.0),      {"q": 1.0}),
    ("B173", lambda: golden_b173(1.0),       lambda: cand_mathieu("a", 2, 1.0),      {"q": 1.0}),
    ("B174", lambda: golden_b174(2.0, 1.0),  lambda: cand_ellipse_perimeter(2.0, 1.0), {"a_um": 2.0}),
    ("B175", lambda: golden_b175(3.0, 1.0),  lambda: cand_ellipse_perimeter(3.0, 1.0), {"a_um": 3.0}),
    ("B176", lambda: golden_b176(135.0),     lambda: cand_pendulum(135.0),           {"theta0_deg": 135.0}),
    ("B177", lambda: golden_b177(150.0),     lambda: cand_pendulum(150.0),           {"theta0_deg": 150.0}),
    ("B178", lambda: golden_b178(2.0),       lambda: cand_oblate_Nc(2.0),            {"ar": 2.0}),
    ("B179", lambda: golden_b179(2.0),       lambda: cand_prolate_Na(2.0),           {"ar": 2.0}),
    ("B180", lambda: golden_b180(1.0),       lambda: cand_fresnel_C(1.0),            {"u": 1.0}),
    ("B181", lambda: golden_b181(1.0),       lambda: cand_fresnel_S(1.0),            {"u": 1.0}),
    ("B182", lambda: golden_b182(50.0),      lambda: cand_diffusion(50.0),           {"x_nm": 50.0}),
    ("B183", lambda: golden_b183(120.0),     lambda: cand_diffusion(120.0),          {"x_nm": 120.0}),
    ("B184", lambda: golden_b184(200.0),     lambda: cand_diffusion(200.0),          {"x_nm": 200.0}),
]

_TOL = 0.01   # 与 benchmarks.py 各锚 tol 一致（判据 D 余量基准）


def _self_test() -> None:
    print("=== B-10 数值核自测（v0.9.90）===")

    # ---- 极限自检 ----
    # A: q→0 时 Mathieu 退化为常系数，P1-FEM 在此**节点精确**（a₀,a₁,b₁,b₂,a₂ = 0,1,1,4,4）
    print("[自检 A] q→0 退化（应精确 = 0/1/1/4/4）："
          f" a₀={cand_mathieu('a', 0, 0.0):.2e} a₁={cand_mathieu('a', 1, 0.0):.2e}"
          f" b₁={cand_mathieu('b', 1, 0.0):.2e} b₂={cand_mathieu('b', 2, 0.0):.2e}"
          f" a₂={cand_mathieu('a', 2, 0.0):.2e}")
    # B: 球极限 ar→1 时 N→1/3；求和律 N_c+2N_a=1
    ar1 = 1.0 + 1e-6
    print(f"[自检 B] 球极限 N_c(ar→1) = {oblate_Nc_closed(ar1):.9f}"
          f" / N_a(ar→1) = {prolate_Na_closed(ar1):.9f}（应 = 1/3 = {1/3:.9f}）")
    nc = oblate_Nc_closed(2.0)
    print(f"[自检 B] 求和律 N_c + 2·N_a = {nc + 2.0 * (1.0 - nc) / 2.0:.12f}（应 = 1）")
    # D: 一步保持性（IC=解析解，走 1 步）
    for Mt in (500, 2000):
        C1, hh = _cn_run(_D_DIFF, _D_T0 - 1.0, _D_T0, Mt, 1, _D_L_UM, 1.0)
        xg = np.arange(Mt + 1) * hh
        ana = 1.0 / math.sqrt(4.0 * PI * _D_DIFF * _D_T0) * np.exp(-xg ** 2 / (4.0 * _D_DIFF * _D_T0))
        dev = float(np.max(np.abs(C1 - ana)) / np.max(ana))
        print(f"[自检 D] 一步保持性 M={Mt}: max rel dev = {dev:.3e}")

    # ---- 主表 ----
    print(f"{'锚号':<6}{'golden':>18}{'cand':>18}{'|diff|':>14}{'余量×':>10}  判据D")
    nz = 0
    worst = (0.0, "")
    for bid, g, c, dpar in _CASES:
        gv, cv = g(), c()
        diff = abs(gv - cv)
        p0 = next(iter(dpar))
        d2 = dict(dpar)
        d2[p0] = dpar[p0] * 1.1
        gv2 = _golden_by_bid(bid, d2)
        cv2 = _cand_by_bid(bid, d2)
        crit = (abs(gv2 - gv) > 0.0) and (abs(cv2 - cv) > 0.0)
        margin = _TOL / diff if diff > 0 else float("inf")
        nz += 1 if diff > 0 else 0
        if diff > worst[0]:
            worst = (diff, bid)
        print(f"{bid:<6}{gv:>18.9f}{cv:>18.9f}{diff:>14.3e}{margin:>10.1f}  "
              f"{'OK' if crit else 'FAIL'}")
    print("-" * 76)
    print(f"非零残差：{nz}/16    worst = {worst[1]} |d|={worst[0]:.3e}"
          f"（tol {_TOL}，余量 {_TOL / worst[0]:.1f}×）")

    # ---- 离散参数收敛扫描（严格判据 D：单调、残差逐次下降） ----
    print("\n[判据 D · 离散参数]")
    print("  A Mathieu a₀(q=1) FEM N: " + " ".join(
        f"N={N}:{abs(golden_b169(1.0) - cand_mathieu('a', 0, 1.0, N=N)):.2e}"
        for N in (50, 100, 200, 400, 800)))
    print("  B 椭圆周长(a=2,b=1) Simpson n: " + " ".join(
        f"n={n}:{abs(golden_b174(2.0, 1.0) - ellipse_perimeter_simpson(2.0, 1.0, n)):.2e}"
        for n in (4, 6, 8, 10, 12, 16)))
    print("  B 单摆 T/T₀(150°) Simpson n: " + " ".join(
        f"n={n}:{abs(golden_b177(150.0) - pendulum_ratio_simpson(math.radians(150.0), n)):.2e}"
        for n in (4, 8, 12, 16, 24)))
    print("  B 扁椭球 N_c(ar=2) Simpson n: " + " ".join(
        f"n={n}:{abs(golden_b178(2.0) - oblate_Nc_simpson(2.0, n)):.2e}"
        for n in (16, 32, 64, 128, 256)))
    print("  C Fresnel C(u=1) Simpson n: " + " ".join(
        f"n={n}:{abs(golden_b180(1.0) - fresnel_C_simpson(1.0, n)):.2e}"
        for n in (8, 16, 32, 64, 128)))
    print("  D 归一剖面 R(120nm) CN M (nt=0.24M): " + " ".join(
        f"M={M}:{abs(golden_b183(120.0) - diffusion_ratio_cn(120.0, M=M, nt=int(M * 0.24))):.2e}"
        for M in (500, 1000, 2000, 4000, 8000)))


def _golden_by_bid(bid: str, dpar: dict) -> float:
    if bid == "B169":
        return golden_b169(dpar["q"])
    if bid == "B170":
        return golden_b170(dpar["q"])
    if bid == "B171":
        return golden_b171(dpar["q"])
    if bid == "B172":
        return golden_b172(dpar["q"])
    if bid == "B173":
        return golden_b173(dpar["q"])
    if bid == "B174":
        return golden_b174(dpar["a_um"], 1.0)
    if bid == "B175":
        return golden_b175(dpar["a_um"], 1.0)
    if bid == "B176":
        return golden_b176(dpar["theta0_deg"])
    if bid == "B177":
        return golden_b177(dpar["theta0_deg"])
    if bid == "B178":
        return golden_b178(dpar["ar"])
    if bid == "B179":
        return golden_b179(dpar["ar"])
    if bid == "B180":
        return golden_b180(dpar["u"])
    if bid == "B181":
        return golden_b181(dpar["u"])
    if bid == "B182":
        return golden_b182(dpar["x_nm"])
    if bid == "B183":
        return golden_b183(dpar["x_nm"])
    if bid == "B184":
        return golden_b184(dpar["x_nm"])
    raise KeyError(bid)


def _cand_by_bid(bid: str, dpar: dict) -> float:
    if bid == "B169":
        return cand_mathieu("a", 0, dpar["q"])
    if bid == "B170":
        return cand_mathieu("a", 1, dpar["q"])
    if bid == "B171":
        return cand_mathieu("b", 1, dpar["q"])
    if bid == "B172":
        return cand_mathieu("b", 2, dpar["q"])
    if bid == "B173":
        return cand_mathieu("a", 2, dpar["q"])
    if bid == "B174":
        return cand_ellipse_perimeter(dpar["a_um"], 1.0)
    if bid == "B175":
        return cand_ellipse_perimeter(dpar["a_um"], 1.0)
    if bid == "B176":
        return cand_pendulum(dpar["theta0_deg"])
    if bid == "B177":
        return cand_pendulum(dpar["theta0_deg"])
    if bid == "B178":
        return cand_oblate_Nc(dpar["ar"])
    if bid == "B179":
        return cand_prolate_Na(dpar["ar"])
    if bid == "B180":
        return cand_fresnel_C(dpar["u"])
    if bid == "B181":
        return cand_fresnel_S(dpar["u"])
    if bid == "B182":
        return cand_diffusion(dpar["x_nm"])
    if bid == "B183":
        return cand_diffusion(dpar["x_nm"])
    if bid == "B184":
        return cand_diffusion(dpar["x_nm"])
    raise KeyError(bid)


if __name__ == "__main__":
    _self_test()
