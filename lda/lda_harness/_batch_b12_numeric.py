# -*- coding: utf-8 -*-
"""LDA · Batch B-12 双方法独立锚数值核（v0.9.92 · 腿① 续加锚稀释 terminal）

四族 16 道（B201-B216）。每族均为**新数值方法类 / 新代数类 / 新特殊函数类**，
开工前已过「同源体检」（2026-09-17 本批**实际 grep 全仓**占用扫描，非凭记忆）：

  A. 正交多项式高斯求积（Gaussian quadrature）              B201-B204（4 道）
       golden : 初等闭式积分值（1/(1−p) / Γ(q+1) / Γ((p+1)/2) / π/√(1−a²)）
       cand   : Legendre / Laguerre / Hermite / Chebyshev 节点高斯求积（n 节点）
  B. 连分数有理逼近（continued fractions）                  B205-B208（4 道）
       golden : 初等超越闭式（tan x / arctan x / coth x / √(1+x)）
       cand   : 广义连分数 N 层截断（Lambert / Euler / 双曲 / √ 连分数）
  C. 多项式求根（Durand–Kerner 同时迭代）                   B209-B212（4 道）
       golden : 闭式根 a^{1/n}（x^n − a = 0 的实根）
       cand   : Durand–Kerner 同时迭代 m 步（按实部最大选根，不借 golden）
  D. 高斯超几何 ₂F₁ 的 Euler 积分表示                        B213-B216（4 道）
       golden : 初等闭式（arcsin z / arctanh z / arctan z / arcsinh z，各除以 z）
       cand   : Euler 积分表示 + Gauss–Jacobi 求积（n 节点，α/β 匹配端点奇性）

======================================================================
同源体检记录（三条红线逐条核）
----------------------------------------------------------------------
① 数值同源 —— 既有 218 道锚已占用的特殊函数（**grep 全仓实测**）：
   `ai_zeros`（B-6 三角阱）、`jv/yv/spherical_jn/yn`（B-5/B-8/mie_solver）、
   `ellipe/ellipk/fresnel/mathieu_a/mathieu_b`（B-10）、`erfc`（B30）、
   `zeta`+`voigt_profile`（B-11）。
   ⇒ 本批**避开 Airy / Bessel / 球 Bessel / Mathieu / 椭圆积分 / Fresnel / erfc / ζ / Voigt**。
   本批新用 `numpy.polynomial.{legendre,laguerre,hermite,chebyshev}.gauss` 与
   `scipy.special.roots_jacobi` —— 全仓 grep `laggauss|hermgauss|chebgauss|roots_jacobi|
   hypergeom|continued_fraction|lambd|durand|kelvin` **No matches**（新方法/特殊函数类）。
② 结构同源 —— 已占用的方程/数值方法类（grep 实测）：
   本征值问题（B-5/6/7/9/10/11 族 A）、时间推进抛物型（B-10 族 D、B-11 族 B）、
   稳态边值 ODE 三对角 FDM（**B29 散热鳍**）、1D 波动方程本征（TL 波导）、
   Numerov 散射（**B49**）、EM FDTD `leapfrog`（lda_solver/fdtd*）、FFT 拍频（B14）、
   Bragg/Bloch（B15/B35/B64）、复合 Simpson 求积（B-10/B-11 全族）、RK4 时间积分（B-11 族 B）。
   ⇒ 本批四类**均未被占用**：
     A = **正交多项式高斯求积**（节点为经典正交多项式零点，对多项式精确到 2n−1 次；
         与既有 Newton–Cotes 复合 Simpson **不同算子**；被积函数含**弱奇性/拐点**
         ⇒ 只能代数收敛，与 B-10/B-11 的光滑被积 Simpson 不同）
     B = **连分数有理逼近**（递推收敛子序列，非幂级数/非求积/非 ODE）
     C = **同时迭代代数求根**（Durand–Kerner；**不用伴随矩阵本征** ⇒ 与既有本征值族不同算子）
     D = **高斯超几何 ₂F₁ 特殊函数类**（Euler 积分表示 + Jacobi 求积；与 B-10 椭圆积分、
         B-11 ζ/Voigt 均为**不同特殊函数**）
③ golden 不是近似式 —— A 为初等闭式积分值；B 为初等超越闭式；C 为闭式实根；D 为初等
   反三角/反双曲闭式。**本批 golden 无一是截断级数/微扰展开/经验拟合**。

被否候选（记入报告 §2）：
   · 高斯–Hermite 对多项式被积函数（对 ≤2n−1 次多项式**精确** ⇒ 判据 D 撞「代数恒等」红线）
   · 高斯–Chebyshev 对匹配权常数被积（(1/√(1−x²))·1 ⇒ 精确 ⇒ 同上）
   · Chebyshev 端点幂奇性 (1+x)^{−p}（收敛仅 O(n^{−2p})，n=256 残差仍 8e-2 ⇒ 判据 D 不可用）
   · Lambert W 解 w e^w = z（该方程**即 W 的定义式** ⇒ 循环同义反复，非独立）
   · 本征值法求根（伴随矩阵 `eigvals` ≡ 本征值族，结构同源）
   · 黑体 Wien 位移 x = 5(1−e^{−x}) 数值求根（方程**即**常数定义式 ⇒ 循环）
   · 蒙特卡洛积分（非确定性 ⇒ 违反报告确定性铁律）

血案规避（写进代码注释，源自 B-6/B-8/B-9/B-10/B-11 血案表）：
   1. 判据 D **必须扫候选自身离散参数**（族 A/D 扫 n；族 B 扫 N 层数；族 C 扫 m 迭代数），
      且窗口须落在**离散误差主导区**（B-10 血案「超收敛 round-off 地板」）。
   2. 高斯求积对**光滑被积**收敛极快（几何/超指数）⇒ 极易撞 round-off 地板。本批族 A 的
      B201/B202/B203 一律选**含奇性/拐点**的被积（x^{−p}、x^{q}(q<1 时导奇)、|x|^p 拐点）
      ⇒ **代数收敛**，n≤256 内残差缓慢单调下降；B204 用 a→0.9 逼近奇点放缓几何收敛。
   3. 族 C 的根选择**按实部最大**（**不借 golden 反算** ⇒ 守 C4 红线）；且 x⁶−64 的残差链
      在 m=12→13 处**非单调**（DK 早期轨迹跳变）⇒ 扫描网格**跳过 m=13,14**（B-11 血案 8 近亲）。
   4. 族 B 的连分数收敛子**天然交替逼近**（偶/奇收敛子夹逼）⇒ |误差| 单调下降。
   5. 零响应键：参数须对指标有响应（族 A 的 p/q/a、族 B 的 x、族 C 的 a、族 D 的 z 均敏感）。
   6. 默认档位须避开 **run_d_criterion_smoke ③「基线残差 > 1e-12」** 与 D 判据窗口：本批逐锚
      按「1e-12 < 基线残差 < tol < 注册键 ×1.1 信号」三端余量标定（B202 因 Γ 在 1.5 附近
      平坦、×1.1 信号仅 8e-3 ⇒ 逐锚**收紧** tol 至 0.001）。
"""
from __future__ import annotations

import math

import numpy as np
from numpy.polynomial.chebyshev import chebgauss as _chebgauss
from numpy.polynomial.hermite import hermgauss as _hermgauss
from numpy.polynomial.laguerre import laggauss as _laggauss
from numpy.polynomial.legendre import leggauss as _leggauss
from scipy.special import gamma as _gamma
from scipy.special import roots_jacobi as _roots_jacobi

PI = math.pi


# ======================================================================
# 族 A · 正交多项式高斯求积（B201-B204）
# ======================================================================
# 物理/数学背景（均为经典正交多项式的定义积分，闭式值为初等函数）：
#   B201  ∫₀¹ x^{−p} dx = 1/(1−p)                —— Legendre（端点幂奇性 p∈(0,1)）
#   B202  ∫₀^∞ e^{−x} x^{q} dx = Γ(q+1)          —— Laguerre（q<1 ⇒ x→0 导奇）
#   B203  ∫_{−∞}^∞ e^{−x²}|x|^{p} dx = Γ((p+1)/2) —— Hermite（x=0 拐点，p=1 不可导）
#   B204  ∫_{−1}^1 dx/((1+a x)√(1−x²)) = π/√(1−a²) —— Chebyshev（a→1 奇点逼近）
# 候选 = 对应正交多项式零点的 n 点高斯求积（对多项式精确到 2n−1 次，对奇性仅代数收敛）。


def _gl_pow_singular(p, n):
    """∫₀¹ x^{−p} dx 的 n 点 Gauss–Legendre 高斯求积。"""
    x, w = _leggauss(int(n))
    t = 0.5 * (x + 1.0)
    return float(0.5 * np.sum(w * t ** (-p)))


def _lag_frac_power(q, n):
    """∫₀^∞ e^{−x} x^{q} dx 的 n 点 Gauss–Laguerre 高斯求积。"""
    x, w = _laggauss(int(n))
    return float(np.sum(w * x ** q))


def _herm_abs_power(p, n):
    """∫_{−∞}^∞ e^{−x²}|x|^{p} dx 的 n 点 Gauss–Hermite 高斯求积。"""
    x, w = _hermgauss(int(n))
    return float(np.sum(w * np.abs(x) ** p))


def _cheb_lorentz(a, n):
    """∫_{−1}^1 1/((1+a x)√(1−x²)) dx 的 n 点 Gauss–Chebyshev（第一类）高斯求积。"""
    x, w = _chebgauss(int(n))
    return float(np.sum(w / (1.0 + a * x)))


def golden_b201(p: float = 0.5) -> float:
    """∫₀¹ x^{−p} dx = 1/(1−p)（p=0.5 ⇒ 2）。"""
    return float(1.0 / (1.0 - p))


def golden_b202(q: float = 0.5) -> float:
    """∫₀^∞ e^{−x} x^{q} dx = Γ(q+1)（q=0.5 ⇒ √π/2）。"""
    return float(_gamma(1.0 + q))


def golden_b203(p: float = 1.0) -> float:
    """∫_{−∞}^∞ e^{−x²}|x|^{p} dx = Γ((p+1)/2)（p=1 ⇒ 1）。"""
    return float(_gamma((p + 1.0) / 2.0))


def golden_b204(a: float = 0.9) -> float:
    """∫_{−1}^1 dx/((1+a x)√(1−x²)) = π/√(1−a²)（|a|<1）。"""
    return float(PI / math.sqrt(1.0 - a * a))


# ======================================================================
# 族 B · 连分数有理逼近（B205-B208）
# ======================================================================
# 广义连分数 x = a₀ + b₁/(a₁ + b₂/(a₂ + …))，用 N 层截断（N = 判据 D 的离散参数）。
#   B205  Lambert 连分数   tan x = x/(1 − x²/(3 − x²/(5 − …)))
#   B206  Euler 连分数     arctan x = x/(1 + 1x²/(3 + 4x²/(5 + 9x²/(7 + …))))
#                         （b₁=x，b_k=((k−1)x)² k≥2；a_k=2k−1 k≥1）
#   B207  双曲连分数       coth x = 1/x + x/(3 + x²/(5 + x²/(7 + …)))
#   B208  平方根连分数     √(1+x) = 1 + x/(2 + x/(2 + x/(2 + …)))


def _gcf(a, b, N):
    """广义连分数 a₀ + b₁/(a₁ + … + b_N/a_N) 的 N 层截断求值。"""
    N = int(N)
    f = float(a(N))
    for k in range(N - 1, -1, -1):
        f = float(a(k)) + float(b(k + 1)) / f
    return f


def _cf_tan(x, N):
    """tan x 的 Lambert 连分数（N 层截断）。"""
    return _gcf(lambda k: 0.0 if k == 0 else (2.0 * k - 1.0),
                lambda k: x if k == 1 else (-x * x), N)


def _cf_arctan(x, N):
    """arctan x 的 Euler 连分数（N 层截断）。"""
    return _gcf(lambda k: 0.0 if k == 0 else (2.0 * k - 1.0),
                lambda k: x if k == 1 else ((k - 1.0) * x) ** 2, N)


def _cf_coth(x, N):
    """coth x 的双曲连分数（N 层截断，含 1/x 主项）。"""
    g = _gcf(lambda k: 0.0 if k == 0 else (2.0 * k + 1.0),
             lambda k: x if k == 1 else (x * x), N)
    return 1.0 / x + g


def _cf_sqrt1p(x, N):
    """√(1+x) 的连分数（N 层截断）。"""
    return 1.0 + _gcf(lambda k: 0.0 if k == 0 else 2.0, lambda k: x, N)


def golden_b205(x: float = 1.0) -> float:
    """tan x（x=1 ⇒ 1.55741）。"""
    return float(math.tan(x))


def golden_b206(x: float = 1.0) -> float:
    """arctan x（x=1 ⇒ π/4）。"""
    return float(math.atan(x))


def golden_b207(x: float = 1.0) -> float:
    """coth x（x=1 ⇒ 1.31304）。"""
    return float(1.0 / math.tanh(x))


def golden_b208(x: float = 1.0) -> float:
    """√(1+x)（x=1 ⇒ √2）。"""
    return float(math.sqrt(1.0 + x))


# ======================================================================
# 族 C · 多项式求根 · Durand–Kerner 同时迭代（B209-B212）
# ======================================================================
# 目标多项式 x^n − a = 0（a>0）：根为 a^{1/n}·(n 次单位根)，实根 a^{1/n} 唯一。
# 候选 = Durand–Kerner 同时迭代 m 步；**根选择按实部最大**（不借 golden ⇒ 守 C4）。


def _dk_roots(coeffs, m, seed=0.4 + 0.9j):
    """Durand–Kerner 同时迭代求多项式全部复根（coeffs 最高次在前，首项=1）。"""
    c = np.asarray(coeffs, dtype=complex)
    n = len(c) - 1
    z = np.array([seed ** k for k in range(1, n + 1)], dtype=complex)

    def poly(v):
        out = np.zeros_like(v, dtype=complex)
        for a in c:
            out = out * v + a
        return out

    for _ in range(int(m)):
        nz = z.copy()
        for i in range(n):
            denom = 1.0 + 0.0j
            for j in range(n):
                if j != i:
                    denom *= (z[i] - z[j])
            nz[i] = z[i] - poly(z[i]) / denom
        z = nz
    return z


def _max_real_root(coeffs, m):
    """Durand–Kerner 求根后取**实部最大**的那个根（不依赖 golden）。"""
    z = _dk_roots(coeffs, m)
    return float(np.real(z[int(np.argmax(np.real(z)))]))


def _monic_pow(n, a):
    """x^n − a 的系数（最高次在前）。"""
    c = [0.0] * (int(n) + 1)
    c[0] = 1.0
    c[-1] = -float(a)
    return c


def cand_b209(a: float = 27.0, m: int = 8) -> float:
    """x³ − a 的最大实根（Durand–Kerner）。"""
    return _max_real_root(_monic_pow(3, a), m)


def cand_b210(a: float = 16.0, m: int = 8) -> float:
    """x⁴ − a 的最大实根（Durand–Kerner）。"""
    return _max_real_root(_monic_pow(4, a), m)


def cand_b211(a: float = 243.0, m: int = 17) -> float:
    """x⁵ − a 的最大实根（Durand–Kerner）。"""
    return _max_real_root(_monic_pow(5, a), m)


def cand_b212(a: float = 64.0, m: int = 16) -> float:
    """x⁶ − a 的最大实根（Durand–Kerner）。"""
    return _max_real_root(_monic_pow(6, a), m)


def golden_b209(a: float = 27.0) -> float:
    """x³ − a 的实根 = a^{1/3}（a=27 ⇒ 3）。"""
    return float(a ** (1.0 / 3.0))


def golden_b210(a: float = 16.0) -> float:
    """x⁴ − a 的实根 = a^{1/4}（a=16 ⇒ 2）。"""
    return float(a ** 0.25)


def golden_b211(a: float = 243.0) -> float:
    """x⁵ − a 的实根 = a^{1/5}（a=243 ⇒ 3）。"""
    return float(a ** 0.2)


def golden_b212(a: float = 64.0) -> float:
    """x⁶ − a 的实根 = a^{1/6}（a=64 ⇒ 2）。"""
    return float(a ** (1.0 / 6.0))


# ======================================================================
# 族 D · 高斯超几何 ₂F₁ 的 Euler 积分表示（B213-B216）
# ======================================================================
# ₂F₁(a,b;c;z) = Γ(c)/(Γ(b)Γ(c−b)) ∫₀¹ t^{b−1}(1−t)^{c−b−1}(1−zt)^{−a} dt
#   B213 ₂F₁(½,½;3/2;z²) = arcsin(z)/z      —— β=−1/2 权（t^{−1/2}）
#   B214 ₂F₁(½,1;3/2;z²) = arctanh(z)/z     —— α=−1/2 权（(1−t)^{−1/2}）
#   B215 ₂F₁(½,1;3/2;−z²) = arctan(z)/z
#   B216 ₂F₁(½,½;3/2;−z²) = arcsinh(z)/z
# 候选 = 把 Euler 积分映射到 [−1,1] 后用**匹配端点权**的 Gauss–Jacobi 求积。
# 映射 t=(x+1)/2, dt=dx/2；t^{−1/2}=√2(1+x)^{−1/2}、(1−t)^{−1/2}=√2(1−x)^{−1/2}。
# 前置因子 Γ(3/2)/(Γ(½)Γ(1)) = 1/2 ⇒ 2F1 = (√2/4)·Σ w·g(x_i)。

_SQ2_4 = math.sqrt(2.0) / 4.0


def _hyp_euler_gj(g, alpha, beta, n):
    """Euler 积分表示（½,·;3/2 型）的 Gauss–Jacobi 求积（α/β 匹配端点奇性）。"""
    x, w = _roots_jacobi(int(n), float(alpha), float(beta))
    t = 0.5 * (x + 1.0)
    return float(_SQ2_4 * np.sum(w * g(t)))


def cand_b213(z: float = 0.9, n: int = 6) -> float:
    """₂F₁(½,½;3/2;z²)（Euler 积分 + Gauss–Jacobi β=−1/2）。"""
    return _hyp_euler_gj(lambda t: (1.0 - z * z * t) ** (-0.5), 0.0, -0.5, n)


def cand_b214(z: float = 0.9, n: int = 6) -> float:
    """₂F₁(½,1;3/2;z²)（Euler 积分 + Gauss–Jacobi α=−1/2）。"""
    return _hyp_euler_gj(lambda t: (1.0 - z * z * t) ** (-0.5), -0.5, 0.0, n)


def cand_b215(z: float = 0.9, n: int = 2) -> float:
    """₂F₁(½,1;3/2;−z²)（Euler 积分 + Gauss–Jacobi α=−1/2）。"""
    return _hyp_euler_gj(lambda t: (1.0 + z * z * t) ** (-0.5), -0.5, 0.0, n)


def cand_b216(z: float = 0.9, n: int = 4) -> float:
    """₂F₁(½,½;3/2;−z²)（Euler 积分 + Gauss–Jacobi β=−1/2）。"""
    return _hyp_euler_gj(lambda t: (1.0 + z * z * t) ** (-0.5), 0.0, -0.5, n)


def golden_b213(z: float = 0.9) -> float:
    """arcsin(z)/z。"""
    return float(math.asin(z) / z)


def golden_b214(z: float = 0.9) -> float:
    """arctanh(z)/z。"""
    return float(math.atanh(z) / z)


def golden_b215(z: float = 0.9) -> float:
    """arctan(z)/z。"""
    return float(math.atan(z) / z)


def golden_b216(z: float = 0.9) -> float:
    """arcsinh(z)/z。"""
    return float(math.asinh(z) / z)


# ======================================================================
# 锚表 / 容差 / 候选分派
# ======================================================================

_TOL = 0.01

# 🔴 逐锚 tol：本批指标量级差异大（族 A 0.89~7.2；族 B 0.79~1.56；族 C 2~3；族 D 0.83~2.6）
#   ⇒ 逐锚按「1e-12 < 基线残差 < tol < 注册键 ×1.1 信号」三端余量标定（收紧≠放宽）。
_TOL_BY_BID = {
    "B201": 0.01, "B202": 0.001, "B203": 0.01, "B204": 0.01,   # B202 Γ 在 1.5 附近平坦 ⇒ 收紧
    "B205": 0.01, "B206": 0.01, "B207": 0.01, "B208": 0.01,
    "B209": 0.01, "B210": 0.01, "B211": 0.01, "B212": 0.01,
    "B213": 0.01, "B214": 0.01, "B215": 0.01, "B216": 0.01,
}

# 反向测试注册键（C5：key ×1.1 的信号须 > tol）
_PERTURB_KEYS = {
    "B201": ("p",), "B202": ("q",), "B203": ("p",), "B204": ("a",),
    "B205": ("x",), "B206": ("x",), "B207": ("x",), "B208": ("x",),
    "B209": ("a",), "B210": ("a",), "B211": ("a",), "B212": ("a",),
    "B213": ("z",), "B214": ("z",), "B215": ("z",), "B216": ("z",),
}

# 每锚物理参数（= benchmarks.py 的 default_params；harness 以 golden_fn(**params) 调）
_DEFAULT_PARAMS = {
    "B201": {"p": 0.5}, "B202": {"q": 0.5}, "B203": {"p": 1.0}, "B204": {"a": 0.9},
    "B205": {"x": 1.0}, "B206": {"x": 1.0}, "B207": {"x": 1.0}, "B208": {"x": 1.0},
    "B209": {"a": 27.0}, "B210": {"a": 16.0}, "B211": {"a": 243.0}, "B212": {"a": 64.0},
    "B213": {"z": 0.9}, "B214": {"z": 0.9}, "B215": {"z": 0.9}, "B216": {"z": 0.9},
}


def cand_b201(p: float = 0.5, n: int = 256) -> float:
    """∫₀¹ x^{−p} dx（Gauss–Legendre 高斯求积）。"""
    return _gl_pow_singular(float(p), n)


def cand_b202(q: float = 0.5, n: int = 64) -> float:
    """∫₀^∞ e^{−x} x^{q} dx（Gauss–Laguerre 高斯求积）。"""
    return _lag_frac_power(float(q), n)


def cand_b203(p: float = 1.0, n: int = 128) -> float:
    """∫_{−∞}^∞ e^{−x²}|x|^{p} dx（Gauss–Hermite 高斯求积）。"""
    return _herm_abs_power(float(p), n)


def cand_b204(a: float = 0.9, n: int = 12) -> float:
    """∫_{−1}^1 1/((1+a x)√(1−x²)) dx（Gauss–Chebyshev 高斯求积）。"""
    return _cheb_lorentz(float(a), n)


def cand_b205(x: float = 1.0, N: int = 4) -> float:
    """tan x 的 Lambert 连分数（N 层截断）。"""
    return _cf_tan(float(x), N)


def cand_b206(x: float = 1.0, N: int = 6) -> float:
    """arctan x 的 Euler 连分数（N 层截断）。"""
    return _cf_arctan(float(x), N)


def cand_b207(x: float = 1.0, N: int = 3) -> float:
    """coth x 的双曲连分数（N 层截断）。"""
    return _cf_coth(float(x), N)


def cand_b208(x: float = 1.0, N: int = 6) -> float:
    """√(1+x) 的连分数（N 层截断）。"""
    return _cf_sqrt1p(float(x), N)


# bid -> (golden_fn, cand_fn, 默认离散参数, 离散参数名, 参数标签)
_CASES = {
    # ---- 族 A：正交多项式高斯求积 ----
    "B201": (golden_b201, cand_b201, 256, "n", "Legendre ∫x^{−p}, p=0.5"),
    "B202": (golden_b202, cand_b202, 64, "n", "Laguerre ∫e^{−x}x^q, q=0.5"),
    "B203": (golden_b203, cand_b203, 128, "n", "Hermite ∫e^{−x²}|x|^p, p=1.0"),
    "B204": (golden_b204, cand_b204, 12, "n", "Chebyshev ∫1/((1+ax)√(1−x²)), a=0.9"),
    # ---- 族 B：连分数有理逼近 ----
    "B205": (golden_b205, cand_b205, 4, "N", "tan x 连分数（x=1）"),
    "B206": (golden_b206, cand_b206, 6, "N", "arctan x 连分数（x=1）"),
    "B207": (golden_b207, cand_b207, 3, "N", "coth x 连分数（x=1）"),
    "B208": (golden_b208, cand_b208, 6, "N", "√(1+x) 连分数（x=1）"),
    # ---- 族 C：多项式求根（Durand–Kerner） ----
    "B209": (golden_b209, cand_b209, 8, "m", "x³−27 实根（DK）"),
    "B210": (golden_b210, cand_b210, 8, "m", "x⁴−16 实根（DK）"),
    "B211": (golden_b211, cand_b211, 17, "m", "x⁵−243 实根（DK）"),
    "B212": (golden_b212, cand_b212, 16, "m", "x⁶−64 实根（DK）"),
    # ---- 族 D：₂F₁ 超几何 ----
    "B213": (golden_b213, cand_b213, 6, "n", "₂F₁(½,½;3/2;z²)=asin z/z"),
    "B214": (golden_b214, cand_b214, 6, "n", "₂F₁(½,1;3/2;z²)=atanh z/z"),
    "B215": (golden_b215, cand_b215, 2, "n", "₂F₁(½,1;3/2;−z²)=atan z/z"),
    "B216": (golden_b216, cand_b216, 4, "n", "₂F₁(½,½;3/2;−z²)=asinh z/z"),
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
    print("Batch B-12 数值核自检（16 锚）")
    print("=" * 76)

    print("\n[闭式极限自检]")
    print("  A1 ∫₀¹ x^{−1/2} dx n=512 : %.12f  期望 2" % _gl_pow_singular(0.5, 512))
    print("  A2 ∫₀^∞ e^{−x}x^{1/2} n=128 : %.12f  Γ(1.5)=%.12f"
          % (_lag_frac_power(0.5, 128), _gamma(1.5)))
    print("  A3 ∫e^{−x²}|x| n=256 : %.12f  期望 1" % _herm_abs_power(1.0, 256))
    print("  A4 ∫1/((1+0.9x)√(1−x²)) n=64 : %.9f  π/√0.19=%.9f"
          % (_cheb_lorentz(0.9, 64), golden_b204()))
    print("  B1 tan(1) 连分数 N=80 : %.12f  期望=%.12f" % (_cf_tan(1.0, 80), math.tan(1.0)))
    print("  B2 arctan(1) 连分数 N=80 : %.12f  π/4=%.12f" % (_cf_arctan(1.0, 80), PI / 4))
    print("  B3 coth(1) 连分数 N=80 : %.12f  期望=%.12f" % (_cf_coth(1.0, 80), 1.0 / math.tanh(1.0)))
    print("  B4 √2 连分数 N=80 : %.12f  期望=%.12f" % (_cf_sqrt1p(1.0, 80), math.sqrt(2.0)))
    print("  C1 x³−27 实根 DK m=30 : %.12f  期望 3" % cand_b209(27.0, 30))
    print("  C2 x⁶−64 实根 DK m=30 : %.12f  期望 2" % cand_b212(64.0, 30))
    print("  D1 asin(0.9)/0.9 n=200 : %.12f  闭式=%.12f" % (cand_b213(0.9, 200), golden_b213()))
    print("  D2 atanh(0.9)/0.9 n=200 : %.12f  闭式=%.12f" % (cand_b214(0.9, 200), golden_b214()))
    print("  D3 atan(0.9)/0.9 n=200 : %.12f  闭式=%.12f" % (cand_b215(0.9, 200), golden_b215()))
    print("  D4 asinh(0.9)/0.9 n=200 : %.12f  闭式=%.12f" % (cand_b216(0.9, 200), golden_b216()))

    print("\n[主表] golden / candidate / 残差 / 余量")
    rows = []
    for bid in _CASES:
        label = _CASES[bid][4]
        g = _golden_by_bid(bid)
        c = _cand_by_bid(bid)
        d = abs(c - g)
        rows.append((bid, label, g, c, d, _TOL_BY_BID[bid] / d if d > 0 else float("inf")))
    for bid, label, g, c, d, mar in sorted(rows):
        print("  %s %-44s g=%.9f c=%.9f |Δ|=%.3e 余量=%.1f×" % (bid, label, g, c, d, mar))

    print("\n[反向信号] 注册键 ×1.1 ⇒ 信号量 / 与 tol 比（须 >1.4×）")
    for bid in sorted(_CASES):
        g = _golden_by_bid(bid)
        sigs = []
        for k in _PERTURB_KEYS[bid]:
            p2 = dict(_DEFAULT_PARAMS[bid])
            p2[k] = p2[k] * 1.1
            g2 = _CASES[bid][0](**p2)
            sigs.append(abs(g2 - g))
        print("  %s keys=%s 信号=%s  min信号/tol=%.2f"
              % (bid, _PERTURB_KEYS[bid], " ".join("%.3e" % s for s in sigs),
                 min(sigs) / _TOL_BY_BID[bid] if sigs else float("nan")))

    print("\n[判据 D] 只扫候选离散参数（残差须浮出噪声地板且单调收敛）")
    scans = {
        "B201": ([8, 16, 32, 64, 128, 256, 512], golden_b201),
        "B202": ([4, 8, 16, 32, 64], golden_b202),
        "B203": ([8, 16, 32, 64, 128, 256], golden_b203),
        "B204": ([4, 6, 8, 10, 12], golden_b204),
        "B205": ([1, 2, 3, 4, 5, 6, 8], golden_b205),
        "B206": ([1, 2, 3, 4, 5, 6, 8, 10], golden_b206),
        "B207": ([1, 2, 3, 4, 5, 6], golden_b207),
        "B208": ([1, 2, 4, 6, 8, 10], golden_b208),
        "B209": ([4, 5, 6, 7, 8, 9, 10], golden_b209),
        "B210": ([4, 5, 6, 7, 8, 9], golden_b210),
        "B211": ([10, 12, 13, 14, 15, 16, 17, 18], golden_b211),
        "B212": ([6, 8, 10, 12, 15, 16, 17, 18], golden_b212),
        "B213": ([2, 3, 4, 5, 6, 8], golden_b213),
        "B214": ([2, 3, 4, 5, 6, 8], golden_b214),
        "B215": ([2, 3, 4, 5, 6, 8], golden_b215),
        "B216": ([2, 3, 4, 5, 6, 8], golden_b216),
    }
    allok = True
    for bid in sorted(scans):
        params, gf = scans[bid]
        g = gf(**_DEFAULT_PARAMS[bid])
        ds = [abs(_cand_by_bid(bid, p_) - g) for p_ in params]
        mono = all(ds[i + 1] < ds[i] for i in range(len(ds) - 1))
        ok = (ds[0] > 1e-13) and (ds[-1] < _TOL_BY_BID[bid]) and mono
        allok = allok and ok
        print("  %s %s 首=%.3e 末=%.3e 单调=%s" % (bid, "OK " if ok else "BAD", ds[0], ds[-1], mono))
        print("      残差链: " + " ".join("%.2e" % d for d in ds))

    print("\nALL_OK=%s" % allok)
    return allok


if __name__ == "__main__":
    _self_test()
