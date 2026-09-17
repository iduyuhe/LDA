# -*- coding: utf-8 -*-
"""Batch B-17 数值核：三族 16 道（B281-B296）。

设计纪律（同源 B-14/B-15/B-16）：每道锚 = 一个**确定性解析闭式 golden** 对拍一个**不同源真实
数值法候选**；候选自身带离散档位，收敛阶可实测（判据 D：首项 >1e-13、末项 < tol、**严格单调**）。

三族 16 道（B281-B296）
------------------------------------------------------------------------------------------
· 族 A（B281-B286，6 道）**线性受迫阻尼 ODE · 指数时间差分（ETD2）**
  方程：y'(t) = −a·y(t) + b·cos(ωt)，y(0) = y0
  golden：y(t) = (y0 − C)·e^{−a t} + C·cos(ωt) + D·sin(ωt)，C = a·b/(a²+ω²)、D = b·ω/(a²+ω²)
          （齐次 + 特解的**初等闭式**，代入为精确恒等式）
  cand  ：**指数时间差分 ETD2**——把线性部分 e^{−a h} 精确积分、forcing 段内线性插值：
          y_{n+1} = e^{z}·y_n + h·[φ₁(z)·g_n + φ₂(z)·(g_{n+1} − g_n)]，z = −a·h
          φ₁(z) = (e^z − 1)/z、φ₂(z) = (e^z − 1 − z)/z²（实现走 `expm1` 防小 z 相消）
  ⚠️ 与已占用时间推进法**方法学不同源**：B-10 族 D = Crank–Nicolson（梯形）、B-11 族 B / B-15 族 A
     = 经典 RK4（分段多项式导数加权）、B-15 族 D = 分裂步 Fourier（谱精确线性步 + 相位非线性步）、
     B-16 族 A = 显式 RK4 + 二阶中心差分。本族把**线性算子精确对角化**（e^{z} 解析），
     误差只来自 forcing 的段内线性化 ⇒ **指数积分器类，既有 298 道锚零占用**。
  收敛：h²（实测比值 4.000/4.000/4.000）
  观测：t = T 处 y(T)；参数档 (a, b, ω, y0, T)
· 族 B（B287-B291，5 道）**Zernike 圆域模态 RMS 波前 · 极坐标均匀中点求积**
  问题：单位圆盘上光学波前 W(ρ,θ) = Σ_j a_j·Z_j(ρ,θ)（Zernike 基在 (1/π)∫∫·ρdρdθ 内积下正交归一）
  golden：RMS = sqrt(a₁² + a₂²)（Parseval 恒等式；**算术闭式**，非截断近似）
  cand  ：**极坐标均匀中点求积**——ρ 向中点、θ 向中点，Nth = max(2·Nr, 64)，离散 Jac(ρ)
  ⚠️ 与已占用求积类**不同构造**：B-10/B-11 全族 = 一维复合 Simpson（等距节点代数权重）、
     B-11 族 = 四维稠密张量 Simpson、B-12 族 A = 一维正交多项式 Gauss 节点。本族是**圆域二维
     极坐标中点求积**（含 ρ 权重、θ 方向周期中点），节点构造与被积域均不同。
  收敛：h_ρ²（实测比值 → 3.99~4.00）
  观测：波前 RMS；参数档 (n₁,m₁,a₁,n₂,m₂,a₂)
  🔴 硬约束：Zernike 要求 **0 ≤ m ≤ n 且 n−m 为偶数**（n/m 异奇偶时 R_n^m 非法）。
· 族 C（B292-B296，5 道）**Duffing 硬化振子 · 四阶组合辛积分（Yoshida）**
  方程：ẍ + a·x + β·x³ = 0（x(0) = A、ẋ(0) = 0，β > 0 硬化 ⇒ 微腔 Kerr 非线性 / MEMS 谐振子）
  golden：x(t) = A·cn(ω·t, m)，ω² = a + β·A²、m = β·A²/(2·ω²)（**Jacobi 椭圆函数精确解**）
  cand  ：**Yoshida 四阶组合辛积分**——S₂(z₁h)·S₂(z₀h)·S₂(z₁h)，S₂ = 速度 Verlet 半步（2z₁+z₀ = 1），
          组合映射保持辛结构 ⇒ 无长期能量漂移
  ⚠️ 与已占用方法**不同源**：B-11 族 B = 经典 RK4（Runge–Kutta 显式）作用于 Kepler 轨道；
     B-11 已否「1D 波动方程 leapfrog」是因为**PDE 蛙跳 ≡ 仓内 fdtd1d/传输线求解器**（方程同源），
     而本族是**非线性 ODE 粒子的组合辛积分器**（负时间步、辛映射组合），方程类与构造均不同。
  收敛：h⁴（实测比值 15.95~16.00）
  观测：t* 处位移 x(t*)；参数档 (A, a, β, t*)
  🔴 硬约束：① `scipy.special.ellipj` 仅接受 0 ≤ m ≤ 1 ⇒ **全族限硬化（β > 0）**，软化档（m < 0）域外。
            ② t* 必须取扫描步长的公倍数（h = t*/n 严格整除），否则 n = round(t*/h) 量化污染比值。

同源体检（2026-09-17 本批**实际 grep 全仓** 5 批关键词扫描，排 `lda_cuda_venv`/`node_modules`/`vendor`）
------------------------------------------------------------------------------------------
① 数值同源 —— 既有 298 道锚已占用的特殊函数（grep 实测）：`ellipe`（B-10 椭圆积分）、`exp1`/`expn`
   （B-16 族 B）、`fresnel`（B-10 族 C）、`gamma`（B-13）、`mathieu_a`（B-10 族 A）、
   `roots_jacobi`（B-12 族 A）、`spherical_jn`（B-6）、`voigt_profile`（B-11）、`zeta`（B-11）；
   零点类：Bessel J₀ 零点（B-5）、球 Bessel 零点（B-5/B-6）、**Airy 零点（B-6/B115-B117）**、
   tan/cot 超越根（B-567/B-16）。
   ⇒ 本批**新引入 `scipy.special.ellipj`（Jacobi 椭圆函数 cn）**：与 B-10 族的**完全椭圆积分**
   `ellipe`/`ellipk` 不是同一个函数（前者是椭圆**函数**、后者是椭圆**积分**值）⇒ 数值源不同。
   族 A/B 全程只用初等函数（exp/cos/sin/sqrt/factorial），不引入任何新特殊函数。
② 结构同源 —— 已占用的方程类 / 数值方法类（逐批数值核 docstring 全量交叉核对）：
   本征值问题（B-5/6/7/8/9/10/11 族 A + B-12 族 C）、时间推进抛物型（B-10 族 D Crank–Nicolson、
   B-11 族 B RK4、B-15 族 D 分裂步）、稳态边值 ODE 三对角 FDM（B29）、1D 波动本征（TL 波导）、
   Bragg/Bloch 转移矩阵（B15/B35/B64）、复合 Simpson 求积（B-10/B-11 全族）、正交多项式高斯求积
   （B-12 族 A）、连分数（B-12 族 B）、Durand–Kerner 代数求根（B-12 族 C）、₂F₁ Euler 积分（B-12 族 D）、
   分数阶 GL 卷积（B-13 族 A）、矩阵指数 scaling–squaring（B-13 族 B）、梯度下降（B-13 族 C）、
   Volterra 分块梯形（B-13 族 D）、定常对流–扩散中心差分（B-14 族 A）、Fredholm Nyström（B-14 族 B）、
   三次样条插值（B-14 族 C）、非线性 BVP 打靶（B-14 族 D）、延迟 ODE RK4+Hermite（B-15 族 A）、
   双调和 ∇⁴ 13 点（B-15 族 B）、一阶双曲特征线（B-15 族 C）、Burgers RK4+CD（B-16 族 A）、
   2D 泊松五点差分（`lda_solver/drift_diffusion_2d`）、**Numerov 散射（B49）**。
   ⇒ 本批三族**均不落上述任何一类**：A = 指数积分器（零占用）；B = 圆域极坐标二维中点求积；
   C = 组合辛积分器（零占用）。
③ golden 不是近似式 —— A 为齐次+特解拼合的**初等闭式**（无截断）；B 为 Parseval **算术恒等式**；
   C 为 Jacobi **椭圆函数精确解**（非线性方程的精确解，非摄动/渐近式）。

被否候选（记入报告 §2.3 + 本文档）
------------------------------------------------------------------------------------------
· Airy 函数 / 线性势本征 —— **数值同源**：Airy 零点已被 B-6（B115-B117）占用（B-11 报告已明确列为否）。
· Lambert W 解 w·e^w = z —— B-12 已判「该方程即 W 的定义式 ⇒ 循环同义反复」⇒ 否。
· KdV / sine-Gordon 孤子 —— 与 **B-15 族 D（NLSE 孤子，sech 精确解）** 结构同源 ⇒ 否。
· Numerov 法 —— **已被 B49（方势垒透射双基 Numerov 散射）占用** ⇒ 方法同源。
· 截断 Taylor 幂级数法 —— **已被 B-13 族 B（矩阵指数 scaling–squaring 的截断 Taylor）占用** ⇒ 否。
· 几何多重网格 / 共轭梯度 / SOR 迭代线性求解 —— B-14 §2.3 已否「CG/Jacobi（线性求解类已占用）」、
  B-13/B-14 已否「2D 泊松五点差分 + SOR/Gauss–Seidel ≡ `drift_diffusion_2d`」，B-15 复核同结论 ⇒ 否。
· Struve H_n 定义级数部分和 —— 阶乘收敛（超几何）⇒ 残差 **沉噪声地板**，与 B-16 已否「复围道留数
  指数收敛 ⇒ 沉地板」同型 ⇒ 否。
· 稀疏网格 Smolyak 求积 —— 光滑被积下超收敛 ⇒ 沉地板（B-10/B-14 已否「Romberg–Richardson 超收敛」）⇒ 否。
· Sinkhorn / 熵正则最优输运 —— 熵正则 ε 偏差不随离散细化消失，golden（无正则 W₂）与候选非同源极限 ⇒ 否。
· Radon 断层重建 —— 本质为沿直线的二维数值求积（与 B-10/B-11 求积类近）⇒ 否。
· Orr–Sommerfeld 稳定性 —— 4 阶广义本征问题，与本征值族（B-5/6/7/9/10/11 族 A）结构同源 ⇒ 否。
· 混沌映射 Lyapunov 指数 / 分形维数盒计数 —— 有限时间估计含 O(1/√N) 涨落且非单调 ⇒ 判据 D 不可用 ⇒ 否。
· 蒙特卡洛类 —— 非确定性 ⇒ 否（B-14 已列）。

本批血案（实测，写进代码注释）
------------------------------------------------------------------------------------------
1. **Zernike n/m 奇偶性**：n−m 为奇数时 R_n^m 无定义（负幂/半整幂），整数除法会**静默**给出错误多项式
   ⇒ 原型中 (5,−2) 档残差恒 ~0.89 且不下降（看起来「不收敛」，实为索引非法）。已加显式断言。
2. **`scipy.special.ellipj` 定义域**：仅接受 0 ≤ m ≤ 1 ⇒ 软化 Duffing（β<0 ⇒ m<0）返回 NaN
   ⇒ 全族限硬化。
3. **Yoshida 组合系数**：四阶组合要求 **2z₁ + z₀ = 1**（z₁ = 1/(2−2^{1/3})、z₀ = −2^{1/3}/(2−2^{1/3})）。
   内联组合步时漏乘 z₁（外两步用裸 h）⇒ 时间增量 = (2+z₀)h = 0.298h ⇒ 残差恒 ~0.2、比值 1.00。
4. **观测时刻量化**：h = t*/n 必须严格整除（t* 取各扫描步长的公倍数），否则 n = round(t*/h)
   引入 O(h) 量化误差 ⇒ 比值被污染（实测 11.27 / 14.29 / 17.50 乱跳）。
5. **反向标定逐锚核验**：族 C 在小 a / 大 A 档 β 的响应会掉到 1.4×tol 以下（实测 1.08×/1.37×）
   ⇒ 选档须逐锚核 sig（零响应键须移出 `_PERTURB_KEYS`）。
6. **族 A 的 φ₁/φ₂ 数值**：小 z 时 (e^z − 1) 直接相减损失精度 ⇒ 实现走 `math.expm1`。

定档纪律：每族**默认离散档 = 扫描网格末端**（否则默认路径残差被放大、余量崩到 ~1×，B-15 口径）。
"""
import math

import numpy as np
from scipy import special

__all__ = [
    "golden_b281", "cand_b281", "golden_b282", "cand_b282", "golden_b283", "cand_b283",
    "golden_b284", "cand_b284", "golden_b285", "cand_b285", "golden_b286", "cand_b286",
    "golden_b287", "cand_b287", "golden_b288", "cand_b288", "golden_b289", "cand_b289",
    "golden_b290", "cand_b290", "golden_b291", "cand_b291",
    "golden_b292", "cand_b292", "golden_b293", "cand_b293", "golden_b294", "cand_b294",
    "golden_b295", "cand_b295", "golden_b296", "cand_b296",
    "_golden_by_bid", "_cand_by_bid", "_self_test",
]


# ==========================================================================================
# 族 A · 线性受迫阻尼 ODE + 指数时间差分 ETD2（B281-B286）
# ==========================================================================================
def _forced_exact(a, b, w, y0, T):
    """y' = −a·y + b·cos(ωt) 的初等精确解在 t=T 的取值。

    特解 y_p = C·cos ωt + D·sin ωt（C = ab/(a²+ω²)、D = bω/(a²+ω²)）代入方程精确成立；
    齐次解按 y(0) = y0 定常数 ⇒ y(T) = (y0 − C)·e^{−aT} + C·cos ωT + D·sin ωT。
    """
    C = a * b / (a * a + w * w)
    D = b * w / (a * a + w * w)
    return float((y0 - C) * math.exp(-a * T) + C * math.cos(w * T) + D * math.sin(w * T))


def _etd2(a, b, w, y0, T, n):
    """指数时间差分 ETD2：精确线性步 + forcing 段内线性插值（步长 h = T/n）。

    y_{n+1} = e^{z}·y_n + h·[φ₁(z)·g_n + φ₂(z)·(g_{n+1} − g_n)],  z = −a·h
    φ₁(z) = (e^z − 1)/z = expm1(z)/z、φ₂(z) = (e^z − 1 − z)/z² = (expm1(z) − z)/z²。
    误差来源**只有 forcing 的段内线性化**（常数 forcing 时格式精确）⇒ 全局 O(h²)。
    """
    n = int(n)
    h = float(T) / n
    z = -a * h
    e = math.exp(z)
    phi1 = math.expm1(z) / z
    phi2 = (math.expm1(z) - z) / (z * z)
    y = float(y0)
    for i in range(n):
        t0 = i * h
        g0 = b * math.cos(w * t0)
        g1 = b * math.cos(w * (t0 + h))
        y = e * y + h * (phi1 * g0 + phi2 * (g1 - g0))
    return float(y)


def golden_b281(a=0.60, b=2.00, w=1.30, y0=1.50, T=2.00):
    """受迫阻尼 ODE 初等闭式（t = T）。"""
    return _forced_exact(a, b, w, y0, T)


def cand_b281(a=0.60, b=2.00, w=1.30, y0=1.50, T=2.00, n=1600):
    """ETD2 候选（扩散末端档 n = 1600）。"""
    return _etd2(a, b, w, y0, T, n)


def golden_b282(a=0.80, b=1.50, w=2.10, y0=2.00, T=1.50):
    """受迫阻尼 ODE 初等闭式（t = T）。"""
    return _forced_exact(a, b, w, y0, T)


def cand_b282(a=0.80, b=1.50, w=2.10, y0=2.00, T=1.50, n=1600):
    """ETD2 候选。"""
    return _etd2(a, b, w, y0, T, n)


def golden_b283(a=1.20, b=2.50, w=1.70, y0=1.00, T=2.50):
    """受迫阻尼 ODE 初等闭式（t = T）。"""
    return _forced_exact(a, b, w, y0, T)


def cand_b283(a=1.20, b=2.50, w=1.70, y0=1.00, T=2.50, n=1600):
    """ETD2 候选。"""
    return _etd2(a, b, w, y0, T, n)


def golden_b284(a=0.45, b=1.80, w=3.10, y0=2.20, T=1.20):
    """受迫阻尼 ODE 初等闭式（t = T）。"""
    return _forced_exact(a, b, w, y0, T)


def cand_b284(a=0.45, b=1.80, w=3.10, y0=2.20, T=1.20, n=1600):
    """ETD2 候选。"""
    return _etd2(a, b, w, y0, T, n)


def golden_b285(a=0.95, b=2.20, w=1.90, y0=1.30, T=1.80):
    """受迫阻尼 ODE 初等闭式（t = T）。"""
    return _forced_exact(a, b, w, y0, T)


def cand_b285(a=0.95, b=2.20, w=1.90, y0=1.30, T=1.80, n=1600):
    """ETD2 候选。"""
    return _etd2(a, b, w, y0, T, n)


def golden_b286(a=0.70, b=1.60, w=2.60, y0=1.80, T=2.20):
    """受迫阻尼 ODE 初等闭式（t = T）。"""
    return _forced_exact(a, b, w, y0, T)


def cand_b286(a=0.70, b=1.60, w=2.60, y0=1.80, T=2.20, n=1600):
    """ETD2 候选。"""
    return _etd2(a, b, w, y0, T, n)


# ==========================================================================================
# 族 B · Zernike 圆域模态 RMS 波前 + 极坐标均匀中点求积（B287-B291）
# ==========================================================================================
def _zernike_R(n, m, rho):
    """Zernike 径向多项式 R_n^m(ρ)，要求 0 ≤ m ≤ n 且 n−m 为偶数（血案 1）。"""
    if (n - m) % 2 != 0 or m < 0 or m > n:
        raise ValueError("Zernike 要求 0<=m<=n 且 n-m 为偶数，收到 n=%r m=%r" % (n, m))
    s = np.zeros_like(rho)
    for k in range((n - m) // 2 + 1):
        c = (((-1.0) ** k) * math.factorial(n - k)
             / (math.factorial(k) * math.factorial((n + m) // 2 - k)
                * math.factorial((n - m) // 2 - k)))
        s = s + c * rho ** (n - 2 * k)
    return s


def _zernike_eval(n1, m1, a1, n2, m2, a2, rho, th):
    """双模态波前 W = a₁·Z_{n₁}^{m₁} + a₂·Z_{n₂}^{m₂}（正交归一化：m=0 用 sqrt(n+1)、m>0 用 sqrt(2(n+1))）。"""
    W = np.zeros_like(rho)
    for (n, m, a) in ((n1, m1, a1), (n2, m2, a2)):
        mm = abs(m)
        nrm = math.sqrt(n + 1.0) if mm == 0 else math.sqrt(2.0 * (n + 1.0))
        ang = 1.0 if mm == 0 else (np.cos(mm * th) if m > 0 else np.sin(mm * th))
        W = W + a * nrm * _zernike_R(n, mm, rho) * ang
    return W


def _zernike_rms_disc(n1, m1, a1, n2, m2, a2, Nr):
    """单位圆盘上极坐标**均匀中点**求积 ⇒ 波前 RMS（Nth = max(2·Nr, 64)，θ 方向周期中点）。

    (1/π)∫∫ W² ρ dρ dθ ≈ (1/Nr)·(2π/Nth)/π · Σ W²(ρ_mid, θ_mid)·ρ_mid
    """
    Nr = int(Nr)
    Nth = max(2 * Nr, 64)
    rho = (np.arange(Nr) + 0.5) / Nr
    th = 2.0 * np.pi * (np.arange(Nth) + 0.5) / Nth
    RR, TT = np.meshgrid(rho, th, indexing="ij")
    W = _zernike_eval(n1, m1, a1, n2, m2, a2, RR, TT)
    val = float((W * W * RR).sum()) * (1.0 / Nr) * (2.0 * np.pi / Nth) / np.pi
    return math.sqrt(val)


def golden_b287(n1=2, m1=0, a1=0.60, n2=4, m2=0, a2=0.45):
    """正交归一 Zernike 基下 RMS = sqrt(a₁² + a₂²)（Parseval 恒等式）。"""
    return float(math.sqrt(a1 * a1 + a2 * a2))


def cand_b287(n1=2, m1=0, a1=0.60, n2=4, m2=0, a2=0.45, Nr=160):
    """极坐标中点求积候选（Nr = 160 为扫描末端档）。"""
    return _zernike_rms_disc(n1, m1, a1, n2, m2, a2, Nr)


def golden_b288(n1=2, m1=-2, a1=0.55, n2=4, m2=2, a2=0.48):
    """正交归一 Zernike 基下 RMS = sqrt(a₁² + a₂²)。"""
    return float(math.sqrt(a1 * a1 + a2 * a2))


def cand_b288(n1=2, m1=-2, a1=0.55, n2=4, m2=2, a2=0.48, Nr=160):
    """极坐标中点求积候选。"""
    return _zernike_rms_disc(n1, m1, a1, n2, m2, a2, Nr)


def golden_b289(n1=3, m1=1, a1=0.62, n2=5, m2=-3, a2=0.44):
    """正交归一 Zernike 基下 RMS = sqrt(a₁² + a₂²)。"""
    return float(math.sqrt(a1 * a1 + a2 * a2))


def cand_b289(n1=3, m1=1, a1=0.62, n2=5, m2=-3, a2=0.44, Nr=160):
    """极坐标中点求积候选。"""
    return _zernike_rms_disc(n1, m1, a1, n2, m2, a2, Nr)


def golden_b290(n1=4, m1=0, a1=0.58, n2=6, m2=-4, a2=0.46):
    """正交归一 Zernike 基下 RMS = sqrt(a₁² + a₂²)。"""
    return float(math.sqrt(a1 * a1 + a2 * a2))


def cand_b290(n1=4, m1=0, a1=0.58, n2=6, m2=-4, a2=0.46, Nr=160):
    """极坐标中点求积候选。"""
    return _zernike_rms_disc(n1, m1, a1, n2, m2, a2, Nr)


def golden_b291(n1=5, m1=5, a1=0.64, n2=7, m2=-1, a2=0.42):
    """正交归一 Zernike 基下 RMS = sqrt(a₁² + a₂²)。"""
    return float(math.sqrt(a1 * a1 + a2 * a2))


def cand_b291(n1=5, m1=5, a1=0.64, n2=7, m2=-1, a2=0.42, Nr=160):
    """极坐标中点求积候选。"""
    return _zernike_rms_disc(n1, m1, a1, n2, m2, a2, Nr)


# ==========================================================================================
# 族 C · Duffing 硬化振子 + 四阶组合辛积分（Yoshida）（B292-B296）
# ==========================================================================================
# Yoshida 四阶组合系数：S₂(z₁h)·S₂(z₀h)·S₂(z₁h)，满足 2z₁ + z₀ = 1（血案 3）
_YOSHIDA_Z1 = 1.0 / (2.0 - 2.0 ** (1.0 / 3.0))
_YOSHIDA_Z0 = -(2.0 ** (1.0 / 3.0)) / (2.0 - 2.0 ** (1.0 / 3.0))


def _duffing_exact(A, a, beta, tstar):
    """ẍ + a·x + β·x³ = 0（x(0)=A, ẋ(0)=0, β>0）的 Jacobi cn 精确解在 t* 的取值。

    首次积分：½ẋ² + ½a x² + ¼β x⁴ = ½a A² + ¼β A⁴ ⇒ 解写为 cn：
    x(t) = A·cn(ω t, m)，ω² = a + βA²、m = βA²/(2ω²)（标准化 cn 的模为 m = k²）。
    """
    w2 = a + beta * A * A
    w = math.sqrt(w2)
    m = beta * A * A / (2.0 * w2)
    if not (0.0 <= m <= 1.0):
        raise ValueError("ellipj 要求 0<=m<=1（软化 Duffing 的 m<0 域外，血案 2）：m=%r" % m)
    return float(A * special.ellipj(w * tstar, m)[1])


def _duffing_yoshida4(A, a, beta, tstar, n):
    """四阶组合辛积分（Yoshida）：每大步 n 个组合步，h = t*/n 严格整除（血案 4）。"""
    n = int(n)
    h = float(tstar) / n
    s1 = _YOSHIDA_Z1 * h
    s0 = _YOSHIDA_Z0 * h

    def f(x):
        return -a * x - beta * x * x * x

    x = float(A)
    v = 0.0
    for _ in range(n):
        v += 0.5 * s1 * f(x)
        x += s1 * v
        v += 0.5 * s1 * f(x)
        v += 0.5 * s0 * f(x)
        x += s0 * v
        v += 0.5 * s0 * f(x)
        v += 0.5 * s1 * f(x)
        x += s1 * v
        v += 0.5 * s1 * f(x)
    return float(x)


def golden_b292(A=1.00, a=0.25, beta=1.20, tstar=0.64):
    """Duffing 硬化振子 Jacobi cn 精确解（t = t*）。"""
    return _duffing_exact(A, a, beta, tstar)


def cand_b292(A=1.00, a=0.25, beta=1.20, tstar=0.64, n=64):
    """Yoshida 四阶组合辛积分候选（n = 64 为扫描末端档）。"""
    return _duffing_yoshida4(A, a, beta, tstar, n)


def golden_b293(A=1.00, a=0.40, beta=1.20, tstar=0.64):
    """Duffing 硬化振子 Jacobi cn 精确解（t = t*）。"""
    return _duffing_exact(A, a, beta, tstar)


def cand_b293(A=1.00, a=0.40, beta=1.20, tstar=0.64, n=64):
    """Yoshida 四阶组合辛积分候选。"""
    return _duffing_yoshida4(A, a, beta, tstar, n)


def golden_b294(A=1.00, a=0.60, beta=1.20, tstar=0.64):
    """Duffing 硬化振子 Jacobi cn 精确解（t = t*）。"""
    return _duffing_exact(A, a, beta, tstar)


def cand_b294(A=1.00, a=0.60, beta=1.20, tstar=0.64, n=64):
    """Yoshida 四阶组合辛积分候选。"""
    return _duffing_yoshida4(A, a, beta, tstar, n)


def golden_b295(A=0.90, a=0.25, beta=1.60, tstar=0.64):
    """Duffing 硬化振子 Jacobi cn 精确解（t = t*）。"""
    return _duffing_exact(A, a, beta, tstar)


def cand_b295(A=0.90, a=0.25, beta=1.60, tstar=0.64, n=64):
    """Yoshida 四阶组合辛积分候选。"""
    return _duffing_yoshida4(A, a, beta, tstar, n)


def golden_b296(A=0.90, a=0.40, beta=1.60, tstar=0.64):
    """Duffing 硬化振子 Jacobi cn 精确解（t = t*）。"""
    return _duffing_exact(A, a, beta, tstar)


def cand_b296(A=0.90, a=0.40, beta=1.60, tstar=0.64, n=64):
    """Yoshida 四阶组合辛积分候选。"""
    return _duffing_yoshida4(A, a, beta, tstar, n)


# ==========================================================================================
# 参数表 / 调度表 / 自检
# ==========================================================================================
_TOL = 0.01

_BIDS_A = ["B281", "B282", "B283", "B284", "B285", "B286"]
_BIDS_B = ["B287", "B288", "B289", "B290", "B291"]
_BIDS_C = ["B292", "B293", "B294", "B295", "B296"]
_ALL_BIDS = _BIDS_A + _BIDS_B + _BIDS_C

# 逐锚 tol（本批全部 0.01；golden 量级下限 ≈ 0.177 ⇒ 17.7×tol，未放宽）
_TOL_BY_BID = {bid: 0.01 for bid in _ALL_BIDS}

# 反向扰动键（连续物理参数；n₁/m₁/n₂/m₂、离散档位不作扰动键）
_PERTURB_KEYS = {}
for _b in _BIDS_A:
    _PERTURB_KEYS[_b] = ("a", "w")
for _b in _BIDS_B:
    _PERTURB_KEYS[_b] = ("a1", "a2")
for _b in _BIDS_C:
    _PERTURB_KEYS[_b] = ("A", "beta", "tstar")

_DEFAULT_PARAMS = {
    "B281": dict(a=0.60, b=2.00, w=1.30, y0=1.50, T=2.00),
    "B282": dict(a=0.80, b=1.50, w=2.10, y0=2.00, T=1.50),
    "B283": dict(a=1.20, b=2.50, w=1.70, y0=1.00, T=2.50),
    "B284": dict(a=0.45, b=1.80, w=3.10, y0=2.20, T=1.20),
    "B285": dict(a=0.95, b=2.20, w=1.90, y0=1.30, T=1.80),
    "B286": dict(a=0.70, b=1.60, w=2.60, y0=1.80, T=2.20),
    "B287": dict(n1=2, m1=0, a1=0.60, n2=4, m2=0, a2=0.45),
    "B288": dict(n1=2, m1=-2, a1=0.55, n2=4, m2=2, a2=0.48),
    "B289": dict(n1=3, m1=1, a1=0.62, n2=5, m2=-3, a2=0.44),
    "B290": dict(n1=4, m1=0, a1=0.58, n2=6, m2=-4, a2=0.46),
    "B291": dict(n1=5, m1=5, a1=0.64, n2=7, m2=-1, a2=0.42),
    "B292": dict(A=1.00, a=0.25, beta=1.20, tstar=0.64),
    "B293": dict(A=1.00, a=0.40, beta=1.20, tstar=0.64),
    "B294": dict(A=1.00, a=0.60, beta=1.20, tstar=0.64),
    "B295": dict(A=0.90, a=0.25, beta=1.60, tstar=0.64),
    "B296": dict(A=0.90, a=0.40, beta=1.60, tstar=0.64),
}

# 候选自身的离散参数键 + 扫描网格（定档取末端）
_DISC_KEY = {}
for _b in _BIDS_A:
    _DISC_KEY[_b] = "n"
for _b in _BIDS_B:
    _DISC_KEY[_b] = "Nr"
for _b in _BIDS_C:
    _DISC_KEY[_b] = "n"

_SCAN_GRID = {}
for _b in _BIDS_A:
    _SCAN_GRID[_b] = [200, 400, 800, 1600]
for _b in _BIDS_B:
    _SCAN_GRID[_b] = [20, 40, 80, 160]
for _b in _BIDS_C:
    _SCAN_GRID[_b] = [8, 16, 32, 64]

_GOLDEN_FN = {
    "B281": golden_b281, "B282": golden_b282, "B283": golden_b283,
    "B284": golden_b284, "B285": golden_b285, "B286": golden_b286,
    "B287": golden_b287, "B288": golden_b288, "B289": golden_b289,
    "B290": golden_b290, "B291": golden_b291,
    "B292": golden_b292, "B293": golden_b293, "B294": golden_b294,
    "B295": golden_b295, "B296": golden_b296,
}

_CAND_FN = {
    "B281": cand_b281, "B282": cand_b282, "B283": cand_b283,
    "B284": cand_b284, "B285": cand_b285, "B286": cand_b286,
    "B287": cand_b287, "B288": cand_b288, "B289": cand_b289,
    "B290": cand_b290, "B291": cand_b291,
    "B292": cand_b292, "B293": cand_b293, "B294": cand_b294,
    "B295": cand_b295, "B296": cand_b296,
}


def _golden_by_bid(bid, params=None):
    p = dict(_DEFAULT_PARAMS[bid])
    if params:
        p.update(params)
    return _GOLDEN_FN[bid](**p)


def _cand_by_bid(bid, disc=None, params=None):
    p = dict(_DEFAULT_PARAMS[bid])
    if params:
        p.update(params)
    if disc is not None:
        p[_DISC_KEY[bid]] = disc
    return _CAND_FN[bid](**p)


def _radial_poly(n, m):
    """R_n^m(ρ) 的多项式表示（numpy.polynomial，供精确内积用）。"""
    coef = np.zeros(n + 1)
    for k in range((n - m) // 2 + 1):
        c = (((-1.0) ** k) * math.factorial(n - k)
             / (math.factorial(k) * math.factorial((n + m) // 2 - k)
                * math.factorial((n - m) // 2 - k)))
        coef[n - 2 * k] += c
    return np.polynomial.Polynomial(coef)


def _zernike_inner(n1, m1, n2, m2):
    """正交内积 (1/π)∫∫ Z_{n₁}^{m₁}·Z_{n₂}^{m₂} ρ dρ dθ 的**解析**值（ρ 向多项式精确积分 + θ 向解析）。

    用于自检「基是否正交归一」——比数值求积更严（不引入 O(h²) 求积误差）。
    """
    if abs(m1) != abs(m2):
        return 0.0
    if m1 > 0 and m2 < 0 or m1 < 0 and m2 > 0:
        return 0.0                      # cos·sin 交叉项
    if m1 != m2:
        return 0.0                      # cos·cos / sin·sin 且阶不同 ⇒ 0
    # 径向精确积分 ∫₀¹ R_{n₁}^{m} R_{n₂}^{m} ρ dρ
    P = (_radial_poly(n1, abs(m1)) * _radial_poly(n2, abs(m2))
         * np.polynomial.Polynomial([0.0, 1.0]))     # 含 ρ 权重
    _anti = P.integ()                                # 原函数（integ() 第二位置为积分常数，非上限）
    rad = float(_anti(1.0) - _anti(0.0))
    ang = 2.0 * np.pi if m1 == 0 else np.pi
    nrm1 = math.sqrt(n1 + 1.0) if m1 == 0 else math.sqrt(2.0 * (n1 + 1.0))
    nrm2 = math.sqrt(n2 + 1.0) if m2 == 0 else math.sqrt(2.0 * (n2 + 1.0))
    return float(nrm1 * nrm2 * rad * ang / np.pi)


def _self_test(verbose=True):
    """权威判据 D 扫描 + 反向信号 + 余量 + 闭式极限自检。"""
    all_ok = True
    min_margin = (None, 1e18)
    min_sig = (None, 1e18)
    min_abs_g = (None, 1e18)
    for bid in _ALL_BIDS:
        g = _golden_by_bid(bid)
        tol = _TOL_BY_BID[bid]
        ds = [abs(_cand_by_bid(bid, disc=d) - g) for d in _SCAN_GRID[bid]]
        mono = all(ds[i + 1] < ds[i] for i in range(len(ds) - 1))
        ok = (ds[0] > 1e-13) and (ds[-1] < tol) and mono
        sig = 0.0
        for key in _PERTURB_KEYS[bid]:
            v = _DEFAULT_PARAMS[bid][key]
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                continue
            p2 = dict(_DEFAULT_PARAMS[bid])
            p2[key] = float(v) * 1.1
            sig = max(sig, abs(_golden_by_bid(bid, p2) - g))
        margin = tol / ds[-1] if ds[-1] > 0 else float("inf")
        sigx = sig / tol
        if margin < min_margin[1]:
            min_margin = (bid, margin)
        if sigx < min_sig[1]:
            min_sig = (bid, sigx)
        if abs(g) < min_abs_g[1]:
            min_abs_g = (bid, abs(g))
        all_ok = all_ok and ok
        if verbose:
            print("%s g=%+.6f tol=%.4f margin=%8.1fx sig=%5.2fx mono=%-5s ds=%s %s"
                  % (bid, g, tol, margin, sigx, mono,
                     "[" + ", ".join("%.3e" % d for d in ds) + "]",
                     "OK" if ok else "**FAIL**"))

    # ---- 闭式极限自检 ----
    checks = []
    # A: ω→0 ⇒ 正弦项消失 ⇒ y = y0 e^{−aT} + (b/a)(1 − e^{−aT})
    lim_a = golden_b281(a=0.6, b=2.0, w=0.0, y0=1.5, T=2.0)
    want_a = 1.5 * math.exp(-1.2) + (2.0 / 0.6) * (1.0 - math.exp(-1.2))
    checks.append(("A ω→0 极限 = 一阶惯性环节阶跃", abs(lim_a - want_a) < 1e-14))
    # A: a→0 ⇒ y = y0 + (b/ω) sin(ωT)
    lim_b = golden_b281(a=0.0, b=2.0, w=1.3, y0=1.5, T=2.0)
    want_b = 1.5 + (2.0 / 1.3) * math.sin(1.3 * 2.0)
    checks.append(("A a→0 极限 = 纯受迫 y0+(b/ω)sin(ωT)", abs(lim_b - want_b) < 1e-14))
    # B: 单模态 ⇒ RMS = |a1|
    checks.append(("B 单模态 RMS = a1", abs(golden_b287(a1=0.6, a2=0.0) - 0.6) < 1e-15))
    # B: 正交归一性（同一模态内积 = 1；不同模态 = 0）
    checks.append(("B 内积 <Z_2^0,Z_2^0> = 1", abs(_zernike_inner(2, 0, 2, 0) - 1.0) < 1e-6))
    checks.append(("B 内积 <Z_2^0,Z_4^0> = 0", abs(_zernike_inner(2, 0, 4, 0)) < 1e-6))
    checks.append(("B 内积 <Z_3^1,Z_5^-3> = 0", abs(_zernike_inner(3, 1, 5, -3)) < 1e-6))
    # C: β→0 ⇒ 简谐振子 x = A cos(√a t)
    checks.append(("C β→0 极限 = A·cos(√a·t*)",
                   abs(golden_b292(a=0.25, beta=0.0) - 1.0 * math.cos(0.5 * 0.64)) < 1e-14))
    # C: a=0 ⇒ m = 1/2 精确
    m0 = (1.0 * 1.2) / (2.0 * (0.0 + 1.2))
    checks.append(("C a=0 ⇒ m = 1/2 精确", abs(m0 - 0.5) < 1e-15))
    # C: 周期关系 T_period = 4K(m)/ω（cn 的半周期 ⇒ 四分之一周期）
    w2 = 0.25 + 1.2 * 1.0
    mm = 1.2 / (2.0 * w2)
    tp = 4.0 * float(special.ellipk(mm)) / math.sqrt(w2)
    checks.append(("C 周期 4K(m)/ω 与 cn 零点一致",
                   abs(golden_b292(tstar=tp / 4.0)) < 1e-12))
    for name, ok in checks:
        print("  [climit] %-42s %s" % (name, "OK" if ok else "**FAIL**"))
        all_ok = all_ok and ok

    print("MIN_MARGIN %s %.1fx | MIN_SIG %s %.2fx | MIN_|g| %s %.6f"
          % (min_margin[0], min_margin[1], min_sig[0], min_sig[1], min_abs_g[0], min_abs_g[1]))
    print("ALL_OK=%s" % all_ok)
    return all_ok


if __name__ == "__main__":
    import sys
    _r = _self_test()
    print("SELFTEST_ALL_OK=%s" % _r)
    sys.exit(0 if _r else 1)
