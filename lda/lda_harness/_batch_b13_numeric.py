# -*- coding: utf-8 -*-
"""LDA · Batch B-13 双方法独立锚数值核（v0.9.93 · 腿① 续加锚稀释 terminal）

四族 16 道（B217-B232）。每族均为**新数值方法类 / 新方程类 / 新算子类**，
开工前已过「同源体检」（2026-09-17 本批**实际 grep 全仓**占用扫描，非凭记忆）：

  A. 分数阶微积分 · Grünwald–Letnikov 数值分数阶导数         B217-B220（4 道）
       golden : 初等闭式 Riemann–Liouville 分数阶导数
                D^α[t^p] = Γ(p+1)/Γ(p+1−α)·t^{p−α}（p=0 用 Γ(1−α) 特例）
       cand   : GL 卷积差分 h^{−α}Σ w_k f(t−kh)（w_0=1, w_k=w_{k−1}(k−1−α)/k）
  B. 矩阵指数 · 自研 scaling–squaring + 截断 Taylor           B221-B224（4 道）
       golden : 状态转移矩阵 exp(At) 的初等闭式（cos/sin/e^{−at}）
       cand   : 缩放-平方 exp(At) ≈ [Σ_{k≤n}(At/2^s)^k/k!]^{2^s}
  C. 变分极值 · 固定步长梯度下降求一维极小                    B225-B228（4 道）
       golden : 解析极小值（−a/4 / 2√a / −e^{b−1} / c−c·ln c）
       cand   : x_{k+1}=x_k−η·f'(x_k) 迭代 k 步后取 f(x_k)
  D. 第二类 Volterra 积分方程 · 分块梯形递推                  B229-B232（4 道）
       golden : φ(x) 的初等闭式（差核可解出 [1−λe^{−(1−λ)x}]/(1−λ)、cosh(√λx) 等）
       cand   : 均匀网格 h=x/n 上的分块梯形递推（含 k=j 隐式项移项）

======================================================================
同源体检记录（三条红线逐条核）
----------------------------------------------------------------------
① 数值同源 —— 既有 234 道锚已占用的特殊函数/常量（**grep 全仓实测**）：
   `ai_zeros`（B-6 三角阱）、`jv/yv/spherical_jn/yn`（B-5/B-8/mie_solver）、
   `ellipe/ellipk/fresnel/mathieu_a/mathieu_b`（B-10）、`erfc`（B30）、
   `zeta`+`voigt_profile`（B-11）、`leggauss/laggauss/hermgauss/chebgauss/roots_jacobi`
   （B-12）。
   ⇒ 本批**避开 Airy / Bessel / 球 Bessel / Mathieu / 椭圆积分 / Fresnel / erfc / ζ /
     Voigt / 全部经典正交多项式节点**。
   本批新用 `scipy.special.gamma`（**仅作 golden 闭式表达**，非候选引擎）与纯 numpy
   差分/矩阵幂/梯度迭代 —— 全仓 grep
   `grunwald|caputo|fractional|分数阶|fredholm|volterra|nystrom|积分方程|
    matrix_exp|scaling_squaring|expm|sor_iter|gauss_seidel|solve_poisson|
    talbot|stehfest|inverse_laplace|kramers|pade|collocation|谱方法` **全部 No matches**。
② 结构同源 —— 已占用的方程/数值方法类（grep 实测）：
   本征值问题（B-5/6/7/9/10/11 族 A）、时间推进抛物型（B-10 族 D Crank–Nicolson、
   B-11 族 B RK4）、稳态边值 ODE 三对角 FDM（**B29 散热鳍**）、1D 波动方程本征（TL 波导）、
   Numerov 散射（**B49**）、EM FDTD `leapfrog`（lda_solver/fdtd*）、FFT 拍频（B14）、
   Bragg/Bloch 转移矩阵（B15/B35/B64）、复合 Simpson 求积（B-10/B-11 全族）、
   正交多项式高斯求积（B-12 族 A）、连分数（B-12 族 B）、代数求根 DK（B-12 族 C）、
   ₂F₁ Euler 积分（B-12 族 D）、**2D 泊松五点差分（`lda_solver/drift_diffusion_2d.
   _solve_poisson_drift_diffusion`，T1-B 漂移-扩散内核）**。
   ⇒ 本批四类**均未被占用**：
     A = **分数阶（非整数阶）微分算子**（GL 卷积权 w_k=Γ(k−α)/(Γ(−α)Γ(k+1))；
         与整数阶差分/求积**不同算子**，且是**非局部**算子 ⇒ 与既有全部锚不同源）
     B = **矩阵函数数值计算**（矩阵指数 scaling–squaring；既有锚全为标量或本征值，
         无「矩阵解析函数」类；也不等于「本征值问题」——不求本征，直接算矩阵函数）
     C = **一维无约束变分极值（数值优化）**（梯度下降；既有锚**没有一个**是「求极值」
         类——本征值/求根/求积/积分方程均不同；极值是**变分原理**的直接对象）
     D = **第二类 Volterra 积分方程**（积分方程 ≠ 微分方程；Volterra 的上限变结构
         使其可**前向递推**，与 Fredholm 的全局线性系统不同；既有无积分方程类）
③ golden 不是近似式 —— A 为 Γ 比值初等闭式；B 为 cos/sin/指数初等闭式；
   C 为解析极小值（有理/幂/超越初等组合）；D 为积分方程解析解（有理/双曲初等）。
   **本批 golden 无一是截断级数/微扰展开/经验拟合/数值反演常数**。

被否候选（记入报告 §2）：
   · Airy 方程 / 线性势本征值 —— golden Airy 零点与 **B-6 三角势阱**同源（数值同源）⇒ 否
   · 不完全 Gamma Γ(n,x) / 误差函数族 —— `erfc` 已被 **B30** 占用（数值同源）⇒ 否
   · 合流超几何 M(a,b,z) —— 与 **B-12 族 D（₂F₁ Euler 积分表示）**结构同源
     （同为超几何型 Euler 积分 + 求积）⇒ 否
   · Laplace 逆变换 Talbot / Gaver–Stehfest —— 指数收敛 ⇒ 残差**直接沉到双精度地板**
     （B-10 血案「超收敛 round-off 地板」）⇒ 判据 D 窗口立不起 ⇒ 否
   · 复步长微分法（complex-step differentiation）—— 对**任意**步长都给机器精度导数
     ⇒ 残差恒 ~1e-16，与自证桩 |Δ|≡0 不可区分（代数恒等型陷阱）⇒ 否
   · Wynn ε / Aitken Δ² 序列加速 —— 对 Aitken 型（近几何）级数**精确**加速 ⇒ 残差塌到
     地板；且与 B-12 族 B 连分数同属「序列/函数加速」类（结构同源）⇒ 否
   · 2D 泊松五点差分 + SOR 迭代 —— 与 `drift_diffusion_2d._solve_poisson_drift_diffusion`
     （T1-B 漂移-扩散内核）结构同源（同为本征/椭圆型离散泊松求解）⇒ 否
   · 蒙特卡洛积分 —— 非确定性 ⇒ 违反报告确定性铁律 ⇒ 否

血案规避（写进代码注释，源自 B-6..B-12 血案表）：
   1. 【格点吸附】族 A 的 GL 步长必须**整除**观测点：一律取 h=t/n（n 为扫描参数），
      否则 t−kh 被吸附到最近格点 ⇒ 残差被 O(h) 量化误差主导（B-10 血案 8 近亲）。
   2. 【round-off 地板】族 B 的 scaling–squaring 平方次数 s 会**放大舍入 ×2^s**：
      s=8 时 n≥5 的残差已沉到 4.77e-15 地板且**非严格单调**（B221/B223/B224 实测
      1.06e-12→4.77e-15→4.77e-15 平坦）⇒ 扫描上限收到 **n≤4**，默认档 n=3。
   3. 【running-min 平坦段】族 C **原设计用黄金分割/斐波那契搜索**，其「已评估点最小值」
      序列**每两步才更新一次**（重用点较优 ⇒ 该步残差不变）⇒ 判据 D 的严格单调不成立
      （实测 B225 链 1.08e-3,1.08e-3,6.18e-5,… 有平坦段）⇒ **改固定步长梯度下降**：
      f 沿负梯度方向下降 ⇒ f(x_k) 序列**可证单调**（本批四锚实测链严格单调）。
   4. 【隐式项漏移项】族 D 的分块梯形含 k=j 项（被积函数在 t=x_j 取值 ⇒ 权重 h/2）：
      K(0)≠0 时该项含未知量 φ_j，**必须移项**（φ_j(1−λhK(0)/2)=…）；漏项产生系统偏差。
   5. 【零响应键】B218 原取 t=1 且只扰 α ⇒ 信号仅 **0.07×tol**（Γ 在 1.5 附近平坦 +
      t^{1−α}≡1）⇒ 判据 C5 窗口不成立 ⇒ 改 **t=2.0** 放大信号至 5.8×tol。
   6. 默认档位须避开 **run_d_criterion_smoke ③「基线残差 > 1e-12」**：族 B 默认 n=3
      （残差 2.1e-9~5.9e-8）、族 C 默认 k=12（1.9e-10~1.7e-4）均留 >100× 余量。
"""
from __future__ import annotations

import math

import numpy as np
from scipy.special import gamma as _gamma

PI = math.pi


# ======================================================================
# 族 A · Grünwald–Letnikov 数值分数阶导数（B217-B220）
# ======================================================================
# 物理/数学背景（Riemann–Liouville 分数阶导数，下限 0，t>0）：
#   D^α[t^p] = Γ(p+1)/Γ(p+1−α) · t^{p−α}     （p ≥ 0，α ∈ (0,1)）
#   p=0 时退化为 D^α[1] = t^{−α}/Γ(1−α)
# GL 数值格式（非局部卷积，h=t/n）：
#   D^α f(t) ≈ h^{−α} Σ_{k=0}^{n} w_k f(t−kh),  w_0=1, w_k = w_{k−1}·(k−1−α)/k


def _gl_weights(alpha, n):
    """GL 卷积权 w_k = Γ(k−α)/(Γ(−α)Γ(k+1))，用三项递推稳定生成（非阶乘展开）。"""
    w = np.empty(int(n) + 1)
    w[0] = 1.0
    for k in range(1, int(n) + 1):
        w[k] = w[k - 1] * (k - 1 - alpha) / k
    return w


def _gl_deriv(p, alpha, t, n):
    """GL 近似 D^α[t^p]（h=t/n 精确整除，避免格点吸附）。"""
    n = int(n)
    h = float(t) / n
    w = _gl_weights(alpha, n)
    k = np.arange(n + 1)
    f = np.power(np.maximum(float(t) - k * h, 0.0), p)
    return float(np.sum(w * f) / h ** alpha)


def golden_b217(alpha: float = 0.5, t: float = 1.0) -> float:
    """D^α[1] = t^{−α}/Γ(1−α)（α=0.5, t=1 ⇒ 1/√π）。"""
    return float(t ** (-alpha) / _gamma(1.0 - alpha))


def golden_b218(alpha: float = 0.5, t: float = 2.0) -> float:
    """D^α[t] = Γ(2)/Γ(2−α)·t^{1−α}（α=0.5, t=2 ⇒ √2/Γ(1.5)）。"""
    return float(_gamma(2.0) / _gamma(2.0 - alpha) * t ** (1.0 - alpha))


def golden_b219(alpha: float = 0.5, t: float = 1.0) -> float:
    """D^α[t³] = Γ(4)/Γ(4−α)·t^{3−α}（α=0.5, t=1 ⇒ 6/Γ(3.5)）。"""
    return float(_gamma(4.0) / _gamma(4.0 - alpha) * t ** (3.0 - alpha))


def golden_b220(alpha: float = 0.25, t: float = 1.0) -> float:
    """D^α[t²] = Γ(3)/Γ(3−α)·t^{2−α}（α=0.25, t=1 ⇒ 2/Γ(2.75)）。"""
    return float(_gamma(3.0) / _gamma(3.0 - alpha) * t ** (2.0 - alpha))


def cand_b217(alpha: float = 0.5, t: float = 1.0, n: int = 3200) -> float:
    """D^α[1]（GL 卷积差分 n 段，h=t/n）。"""
    return _gl_deriv(0.0, alpha, t, n)


def cand_b218(alpha: float = 0.5, t: float = 2.0, n: int = 3200) -> float:
    """D^α[t]（GL 卷积差分 n 段，h=t/n）。"""
    return _gl_deriv(1.0, alpha, t, n)


def cand_b219(alpha: float = 0.5, t: float = 1.0, n: int = 3200) -> float:
    """D^α[t³]（GL 卷积差分 n 段，h=t/n）。"""
    return _gl_deriv(3.0, alpha, t, n)


def cand_b220(alpha: float = 0.25, t: float = 1.0, n: int = 3200) -> float:
    """D^α[t²]（GL 卷积差分 n 段，h=t/n）。"""
    return _gl_deriv(2.0, alpha, t, n)


# ======================================================================
# 族 B · 矩阵指数 scaling–squaring + 截断 Taylor（B221-B224）
# ======================================================================
# exp(At) = [exp(At/2^s)]^{2^s} ≈ [Σ_{k=0}^{n} (At/2^s)^k/k!]^{2^s}
# 四道分别取不同 2×2 矩阵与观测元：
#   B221 A=[[0,−1],[1,0]]     观 exp(At)[0,1] = −sin t
#   B222 A=[[0,−2.5],[2.5,0]] 观 exp(At)[0,1] = −sin(2.5t)
#   B223 A=diag(−1,−2)        观 exp(At)[0,0] = e^{−t}
#   B224 A=[[0,1],[−2,−3]]    观 exp(At)[0,0] = 2e^{−t} − e^{−2t}（本征值 −1,−2）


_A221 = np.array([[0.0, -1.0], [1.0, 0.0]])
_A222 = np.array([[0.0, -2.5], [2.5, 0.0]])
_A223 = np.array([[-1.0, 0.0], [0.0, -2.0]])
_A224 = np.array([[0.0, 1.0], [-2.0, -3.0]])


def _mat_exp_ss(A, t, n, s=8):
    """自研 scaling–squaring：先 Taylor 截断 n 项，再自乘 s 次（s 固定为 8）。"""
    A = np.asarray(A, dtype=float)
    d = A.shape[0]
    B = A * (float(t) / (2.0 ** int(s)))
    T = np.eye(d)
    term = np.eye(d)
    for k in range(1, int(n) + 1):
        term = term @ B / k
        T = T + term
    for _ in range(int(s)):
        T = T @ T
    return T


def _entry(A, t, n, i, j):
    return float(_mat_exp_ss(A, t, n)[i, j])


def cand_b221(t: float = 1.0, n: int = 3) -> float:
    """exp(At)[0,1]（A=[[0,−1],[1,0]]，scaling–squaring）。"""
    return _entry(_A221, t, n, 0, 1)


def cand_b222(t: float = 1.0, n: int = 3) -> float:
    """exp(At)[0,1]（A=[[0,−2.5],[2.5,0]]）。"""
    return _entry(_A222, t, n, 0, 1)


def cand_b223(t: float = 1.5, n: int = 3) -> float:
    """exp(At)[0,0]（A=diag(−1,−2)）。"""
    return _entry(_A223, t, n, 0, 0)


def cand_b224(t: float = 1.0, n: int = 3) -> float:
    """exp(At)[0,0]（A=[[0,1],[−2,−3]]，本征值 −1,−2）。"""
    return _entry(_A224, t, n, 0, 0)


def golden_b221(t: float = 1.0) -> float:
    """−sin t（t=1 ⇒ −0.8414710）。"""
    return float(-math.sin(t))


def golden_b222(t: float = 1.0) -> float:
    """−sin(2.5t)（t=1 ⇒ −0.5984721）。"""
    return float(-math.sin(2.5 * t))


def golden_b223(t: float = 1.5) -> float:
    """e^{−t}（t=1.5 ⇒ 0.2231302）。"""
    return float(math.exp(-t))


def golden_b224(t: float = 1.0) -> float:
    """2e^{−t} − e^{−2t}（t=1 ⇒ 0.6004236）。"""
    return float(2.0 * math.exp(-t) - math.exp(-2.0 * t))


# ======================================================================
# 族 C · 变分极值 · 固定步长梯度下降（B225-B228）
# ======================================================================
# 变分原理：极小化能量泛函 f(x)，解析极值已知（golden）；候选只用 f 的梯度迭代。
#   B225 f=a(x⁴/4−x²/2)   x₀=1.5 η=0.25  f*=−a/4        （非谐双阱势）
#   B226 f=a/x+x          x₀=3.0 η=0.30  f*=2√a         （AM–GM / 最优输运）
#   B227 f=x ln x − b x   x₀=2.0 η=0.30  f*=−e^{b−1}    （自由能 / Gibbs 熵项）
#   B228 f=e^x − c x      x₀=0.0 η=0.30  f*=c−c·ln c    （指数型势）


def _gd(f, fp, x0, eta, k):
    """固定步长梯度下降 k 步，返回终点的函数值（running value 沿下降方向单调）。"""
    x = float(x0)
    for _ in range(int(k)):
        x = x - float(eta) * float(fp(x))
    return float(f(x))


def _f225(x, a):
    return a * (x ** 4 / 4.0 - x ** 2 / 2.0)


def _fp225(x, a):
    return a * (x ** 3 - x)


def _f226(x, a):
    return a / x + x


def _fp226(x, a):
    return 1.0 - a / (x * x)


def _f227(x, b):
    return x * math.log(x) - b * x


def _fp227(x, b):
    return math.log(x) + 1.0 - b


def _f228(x, c):
    return math.exp(x) - c * x


def _fp228(x, c):
    return math.exp(x) - c


def cand_b225(a: float = 1.0, k: int = 12) -> float:
    """a(x⁴/4−x²/2) 的数值极小值（梯度下降 k 步）。"""
    return _gd(lambda x: _f225(x, a), lambda x: _fp225(x, a), 1.5, 0.25, k)


def cand_b226(a: float = 1.0, k: int = 12) -> float:
    """a/x + x 的数值极小值（梯度下降 k 步）。"""
    return _gd(lambda x: _f226(x, a), lambda x: _fp226(x, a), 3.0, 0.30, k)


def cand_b227(b: float = 0.5, k: int = 12) -> float:
    """x ln x − b x 的数值极小值（梯度下降 k 步）。"""
    return _gd(lambda x: _f227(x, b), lambda x: _fp227(x, b), 2.0, 0.30, k)


def cand_b228(c: float = 2.0, k: int = 12) -> float:
    """e^x − c x 的数值极小值（梯度下降 k 步）。"""
    return _gd(lambda x: _f228(x, c), lambda x: _fp228(x, c), 0.0, 0.30, k)


def golden_b225(a: float = 1.0) -> float:
    """a(x⁴/4−x²/2) 的解析极小值 −a/4（a=1 ⇒ −0.25）。"""
    return float(-a / 4.0)


def golden_b226(a: float = 1.0) -> float:
    """a/x + x 的解析极小值 2√a（a=1 ⇒ 2）。"""
    return float(2.0 * math.sqrt(a))


def golden_b227(b: float = 0.5) -> float:
    """x ln x − b x 的解析极小值 −e^{b−1}（b=0.5 ⇒ −e^{−0.5}）。"""
    return float(-math.exp(b - 1.0))


def golden_b228(c: float = 2.0) -> float:
    """e^x − c x 的解析极小值 c − c·ln c（c=2 ⇒ 2 − 2ln2）。"""
    return float(c - c * math.log(c))


# ======================================================================
# 族 D · 第二类 Volterra 积分方程 · 分块梯形递推（B229-B232）
# ======================================================================
# φ(x) = 1 + λ∫₀^x K(x−t)φ(t)dt（差核），解析解：
#   B229 K=e^{−(x−t)} λ=0.5 x=1    ⇒ φ=[1−λe^{−(1−λ)x}]/(1−λ)
#   B230 K=e^{−(x−t)} λ=0.8 x=1.5  ⇒ 同式
#   B231 K=e^{−2(x−t)} λ=1.0 x=1   ⇒ φ=[2−λe^{−(2−λ)x}]/(2−λ)
#   B232 K=x−t λ=1.0 x=1          ⇒ φ''=λφ ⇒ φ=cosh(√λ x)


def _k_exp1(s):
    return np.exp(-s)


def _k_exp2(s):
    return np.exp(-2.0 * s)


def _k_iden(s):
    return s


def _volterra(lam, x, n, kernel):
    """分块梯形递推解第二类 Volterra 方程（k=j 项为隐式，移项后前向递推）。"""
    n = int(n)
    h = float(x) / n
    phi = np.empty(n + 1)
    phi[0] = 1.0
    k0 = float(kernel(0.0))
    for j in range(1, n + 1):
        xj = j * h
        s = 0.5 * float(kernel(xj)) * phi[0]
        if j > 1:
            ks = np.arange(1, j) * h
            s += float(np.sum(kernel(xj - ks) * phi[1:j]))
        phi[j] = (1.0 + lam * h * s) / (1.0 - 0.5 * lam * h * k0)
    return float(phi[n])


def cand_b229(lam: float = 0.5, n: int = 1024) -> float:
    """K=e^{−(x−t)}、λ=0.5、x=1 的 φ(1)（分块梯形 n 段）。"""
    return _volterra(lam, 1.0, n, _k_exp1)


def cand_b230(lam: float = 0.8, n: int = 1024) -> float:
    """K=e^{−(x−t)}、λ=0.8、x=1.5 的 φ(1.5)（分块梯形 n 段）。"""
    return _volterra(lam, 1.5, n, _k_exp1)


def cand_b231(lam: float = 1.0, n: int = 1024) -> float:
    """K=e^{−2(x−t)}、λ=1、x=1 的 φ(1)（分块梯形 n 段）。"""
    return _volterra(lam, 1.0, n, _k_exp2)


def cand_b232(lam: float = 1.0, n: int = 1024) -> float:
    """K=x−t、λ=1、x=1 的 φ(1)=cosh(1)（分块梯形 n 段）。"""
    return _volterra(lam, 1.0, n, _k_iden)


def golden_b229(lam: float = 0.5) -> float:
    """[1−λe^{−(1−λ)}]/(1−λ)（λ=0.5 ⇒ 1.3934693）。"""
    return float((1.0 - lam * math.exp(-(1.0 - lam))) / (1.0 - lam))


def golden_b230(lam: float = 0.8) -> float:
    """[1−λe^{−1.5(1−λ)}]/(1−λ)（λ=0.8 ⇒ 2.0367271）。"""
    return float((1.0 - lam * math.exp(-1.5 * (1.0 - lam))) / (1.0 - lam))


def golden_b231(lam: float = 1.0) -> float:
    """[2−λe^{−(2−λ)}]/(2−λ)（λ=1 ⇒ 2−e^{−1}）。"""
    return float((2.0 - lam * math.exp(-(2.0 - lam))) / (2.0 - lam))


def golden_b232(lam: float = 1.0) -> float:
    """cosh(√λ)（λ=1 ⇒ cosh 1）。"""
    return float(math.cosh(math.sqrt(lam)))


# ======================================================================
# 锚表 / 容差 / 候选分派
# ======================================================================

_TOL = 0.01

# 逐锚 tol：本批指标量级（族 A 0.56~1.81；族 B −0.84~0.60；族 C −0.61~2.0；族 D 1.39~2.04）
#   统一 tol=0.01；worst-case 余量 B219 28×（收紧≠放宽）。仅 B226 因残差链末端 1.67e-4
#   仍留 60× 余量，无需逐锚收紧；B219 保持与家族一致。
_TOL_BY_BID = {
    "B217": 0.01, "B218": 0.01, "B219": 0.01, "B220": 0.01,
    "B221": 0.01, "B222": 0.01, "B223": 0.01, "B224": 0.01,
    "B225": 0.01, "B226": 0.01, "B227": 0.01, "B228": 0.01,
    "B229": 0.01, "B230": 0.01, "B231": 0.01, "B232": 0.01,
}

# 反向测试注册键（C5：key ×1.1 的信号须 > tol；B218 因 Γ 在 1.5 附近平坦改 t=2.0）
_PERTURB_KEYS = {
    "B217": ("alpha",), "B218": ("alpha",), "B219": ("alpha",), "B220": ("alpha",),
    "B221": ("t",), "B222": ("t",), "B223": ("t",), "B224": ("t",),
    "B225": ("a",), "B226": ("a",), "B227": ("b",), "B228": ("c",),
    "B229": ("lam",), "B230": ("lam",), "B231": ("lam",), "B232": ("lam",),
}

# 每锚物理参数（= benchmarks.py 的 default_params；harness 以 golden_fn(**params) 调）
_DEFAULT_PARAMS = {
    "B217": {"alpha": 0.5, "t": 1.0}, "B218": {"alpha": 0.5, "t": 2.0},
    "B219": {"alpha": 0.5, "t": 1.0}, "B220": {"alpha": 0.25, "t": 1.0},
    "B221": {"t": 1.0}, "B222": {"t": 1.0}, "B223": {"t": 1.5}, "B224": {"t": 1.0},
    "B225": {"a": 1.0}, "B226": {"a": 1.0}, "B227": {"b": 0.5}, "B228": {"c": 2.0},
    "B229": {"lam": 0.5}, "B230": {"lam": 0.8}, "B231": {"lam": 1.0}, "B232": {"lam": 1.0},
}

# bid -> (golden_fn, cand_fn, 默认离散参数, 离散参数名, 参数标签)
_CASES = {
    # ---- 族 A：Grünwald–Letnikov 分数阶导数 ----
    "B217": (golden_b217, cand_b217, 3200, "n", "D^0.5[1]=1/√(πt), t=1"),
    "B218": (golden_b218, cand_b218, 3200, "n", "D^0.5[t]=√2/Γ(1.5), t=2"),
    "B219": (golden_b219, cand_b219, 3200, "n", "D^0.5[t³]=6/Γ(3.5), t=1"),
    "B220": (golden_b220, cand_b220, 3200, "n", "D^0.25[t²]=2/Γ(2.75), t=1"),
    # ---- 族 B：矩阵指数 scaling–squaring ----
    "B221": (golden_b221, cand_b221, 3, "n", "exp(At)[0,1]=−sin t, t=1"),
    "B222": (golden_b222, cand_b222, 3, "n", "exp(At)[0,1]=−sin(2.5t), t=1"),
    "B223": (golden_b223, cand_b223, 3, "n", "exp(At)[0,0]=e^{−t}, t=1.5"),
    "B224": (golden_b224, cand_b224, 3, "n", "exp(At)[0,0]=2e^{−t}−e^{−2t}, t=1"),
    # ---- 族 C：变分极值（梯度下降） ----
    "B225": (golden_b225, cand_b225, 12, "k", "a(x⁴/4−x²/2) 极小 −a/4, a=1"),
    "B226": (golden_b226, cand_b226, 12, "k", "a/x+x 极小 2√a, a=1"),
    "B227": (golden_b227, cand_b227, 12, "k", "x ln x−b x 极小 −e^{b−1}, b=0.5"),
    "B228": (golden_b228, cand_b228, 12, "k", "e^x−c x 极小 c−c ln c, c=2"),
    # ---- 族 D：第二类 Volterra 积分方程 ----
    "B229": (golden_b229, cand_b229, 1024, "n", "Volterra K=e^{−(x−t)}, λ=0.5, x=1"),
    "B230": (golden_b230, cand_b230, 1024, "n", "Volterra K=e^{−(x−t)}, λ=0.8, x=1.5"),
    "B231": (golden_b231, cand_b231, 1024, "n", "Volterra K=e^{−2(x−t)}, λ=1, x=1"),
    "B232": (golden_b232, cand_b232, 1024, "n", "Volterra K=x−t, λ=1, x=1"),
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
    print("Batch B-13 数值核自检（16 锚）")
    print("=" * 76)

    print("\n[闭式极限自检] 候选在细档下应收敛到 golden 闭式")
    print("  A1 D^0.5[1] n=12800        : %.12f  1/√π=%.12f"
          % (_gl_deriv(0.0, 0.5, 1.0, 12800), golden_b217()))
    print("  A2 D^0.5[t³] n=12800       : %.12f  6/Γ(3.5)=%.12f"
          % (_gl_deriv(3.0, 0.5, 1.0, 12800), golden_b219()))
    print("  B1 exp(At)[0,1] n=12       : %.12f  −sin1=%.12f"
          % (_entry(_A221, 1.0, 12, 0, 1), -math.sin(1.0)))
    print("  B2 exp(At)[0,0] n=12       : %.12f  2e^{−1}−e^{−2}=%.12f"
          % (_entry(_A224, 1.0, 12, 0, 0), 2.0 * math.exp(-1.0) - math.exp(-2.0)))
    print("  C1 a/x+x 极小 k=40         : %.12f  2√1=%.12f"
          % (cand_b226(1.0, 40), 2.0))
    print("  C2 e^x−2x 极小 k=40        : %.12f  c−c ln c=%.12f"
          % (cand_b228(2.0, 40), golden_b228()))
    print("  D1 Volterra K=e^{−(x−t)} n=8192 : %.12f  闭式=%.12f"
          % (_volterra(0.5, 1.0, 8192, _k_exp1), golden_b229()))
    print("  D2 Volterra K=x−t n=8192   : %.12f  cosh1=%.12f"
          % (_volterra(1.0, 1.0, 8192, _k_iden), math.cosh(1.0)))

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
        "B217": ([50, 100, 200, 400, 800, 1600, 3200], golden_b217),
        "B218": ([50, 100, 200, 400, 800, 1600, 3200], golden_b218),
        "B219": ([50, 100, 200, 400, 800, 1600, 3200], golden_b219),
        "B220": ([50, 100, 200, 400, 800, 1600, 3200], golden_b220),
        "B221": ([1, 2, 3, 4], golden_b221),
        "B222": ([1, 2, 3, 4], golden_b222),
        "B223": ([1, 2, 3, 4], golden_b223),
        "B224": ([1, 2, 3, 4], golden_b224),
        "B225": ([1, 2, 3, 4, 5, 6, 8, 10, 12], golden_b225),
        "B226": ([1, 2, 3, 4, 5, 6, 8, 10, 12], golden_b226),
        "B227": ([1, 2, 3, 4, 5, 6, 8, 10, 12], golden_b227),
        "B228": ([1, 2, 3, 4, 5, 6, 8, 10, 12], golden_b228),
        "B229": ([8, 16, 32, 64, 128, 256, 512, 1024], golden_b229),
        "B230": ([8, 16, 32, 64, 128, 256, 512, 1024], golden_b230),
        "B231": ([8, 16, 32, 64, 128, 256, 512, 1024], golden_b231),
        "B232": ([8, 16, 32, 64, 128, 256, 512, 1024], golden_b232),
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
