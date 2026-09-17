# -*- coding: utf-8 -*-
"""Batch B-18 数值核：三族 16 道（B297-B312）。

设计纪律（同源 B-14~B-17）：每道锚 = 一个**确定性解析闭式 golden** 对拍一个**不同源真实数值法
候选**；候选自带离散档位，收敛阶可实测（判据 D：首项 >1e-13、末项 < tol、**严格单调**）。

三族 16 道（B297-B312）
------------------------------------------------------------------------------------------
· 族 A（B297-B302，6 道）**振荡积分 · Filon 型分段二次求积**
  目标：I(ω,a) = ∫₀¹ cos(ω t)·e^{a t} dt（振荡被积函数）
  golden：I = [e^a·(a·cos ω + ω·sin ω) − a]/(a² + ω²)
          （Re[(e^{a+iω}−1)/(a+iω)] 的**初等闭式**，非截断近似）
  cand  ：**Filon 型求积**——把 [0,1] 按 2h 一段分组，段内对 e^{at} 作**二次 Lagrange 插值**，
          段内 ∫cos(ω(x₀+s))·s^p ds (p=0,1,2) 走**解析原函数**（分部积分闭式）⇒ 误差只来自插值
  ⚠️ 与已占用求积类**机制不同**：B-10 族 C/族 B、B-16 族 B = 复合 Simpson / 截断积分；
  B-11 族 C = 四维张量 Simpson；B-12 族 A = 一维正交多项式 Gauss 节点；B-17 族 B = 圆域极坐标
  中点求积。本族**利用振荡结构本身**（段内解析积 cos 核），属 Filon 类，既有 314 道锚零占用。
  收敛：h⁴（实测比值 15.84~16.22）
  观测：t=1 处积分值；参数档 (ω, a)
· 族 B（B303-B307，5 道）**非线性 ODE · Gauss–Legendre 2 级隐式 RK（4 阶，A-稳定）**
  方程：y'(t) = −a·e^{−y(t)}，y(0) = y0（超越闭式解，非有理 ⇒ 无 Padé 超收敛）
  golden：y(T) = ln(e^{y0} − a·T)（**超越初等闭式**：dy/e^{−y} = −a dt ⇒ e^y = e^{y0} − aT）
  cand  ：**Gauss–Legendre 2 级隐式 RK**（Butcher c=[1/2∓√3/6]、A=[[1/4,1/4−√3/6],[1/4+√3/6,1/4]]、
          b=[1/2,1/2]）——每步 2×2 非线性隐式方程走 **Newton 迭代**（解析雅可比）
  ⚠️ 与已占用方法**不同源**：B-14 族 D / B-15 族 D / B-11 族 B / B-16 族 A = **显式** RK4（初值或
  打靶）；本族是**隐式单步**（A-稳定、需 Newton 解隐式方程）——稳定性理论、每步代价、Butcher
  表均不同 ⇒ 隐式 RK 类，既有 314 道锚零占用。
  收敛：h⁴（实测比值 15.29~15.99）
  观测：t=T 处 y(T)；参数档 (a, y0, T)
· 族 C（B308-B312，5 道）**非线性 ODE · Adams–Bashforth 4 阶线性多步**
  方程：y'(t) = −a·sin(y(t))，y(0) = y0（阻尼弛豫 / RSJ 型）
  golden：y(T) = 2·arctan(tan(y0/2)·e^{−a T})（**超越初等闭式**：dy/sin y = −a dt ⇒ tan(y/2) 演化）
  cand  ：**Adams–Bashforth 4 阶线性多步**（y_{n+1} = y_n + h/24·(55f_n − 59f_{n−1} + 37f_{n−2} − 9f_{n−3})），
          前 3 步用同阶 RK4 启动（启动项同阶 h⁴，不主导全局阶）
  ⚠️ 与已占用方法**不同源**：本族是**多步法**（依赖 4 个历史点、需启动器、稳定性域完全不同），
  而 B-14 族 D / B-15 族 D / B-16 族 A 是**单步** RK4；B-17 族 A = 指数积分器（线性算子精确化）、
  B-17 族 C = 辛积分器（保结构）。⇒ 线性多步类，既有 314 道锚零占用。
  收敛：h⁴（实测比值 15.09~16.25）
  观测：t=T 处 y(T)；参数档 (a, y0, T)

同源体检（实际 grep 全仓 lda/，排除 lda_cuda_venv/node_modules/vendor）
------------------------------------------------------------------------------------------
① 数值同源 —— 无：`filon|oscillatory|stationary_phase|振荡积分` 仅撞 B-10 报告文本（Fresnel 振荡积分
   特殊函数，对象不同）；`hilbert|kramers|kronig|principal_value|主值|奇异积分` 仅撞「复平方根取主值」
   与 B-13 报告文本；`abel_transform|schwarz|christoffel|conformal_map` 零命中；
   `bdf|adams_bashforth|multistep|implicit_rk|radau|A-stable` 仅撞颜色码 `#38bdf8`（假阳性）；
   `lobatto|diff_matrix|谱微分|spectral_diffusion` 零命中；`fokker|langevin|随机微分` 零命中。
② 结构同源 —— 复核：`eval_legendre|递推关系|clenshaw` 仅撞 B-13 报告「No matches」记录文本；
   `bem|galerkin|rayleigh_ritz` 仅撞 B-16 报告被否候选记录；`spectral|collocation|谱方法` 命中
   B-15 报告「已被既有锚占满」⇒ **谱方法类已占，本批主动避用**；`rk4|kutta` 命中 B-3/B-5/B-14
   数值核 + `lindblad_gate_fidelity.py` ⇒ **显式 RK4 / Lindblad 域已占，本批避用**。
③ golden 非截断近似 —— 三族 golden 全部为**初等闭式**（Re[指数商]、对数、arctan 复合），
   代入方程/定义均为精确恒等式，无级数截断、无微扰展开。

被否候选（本批实测/复核）
------------------------------------------------------------------------------------------
① Chebyshev 谱微分（微分矩阵）—— 谱方法类已被 B-13/B-15 判占用 ⇒ 否
② Cauchy 主值 / Kramers–Kronig 积分 —— 对称删心退化 O(h)、Lorentzian 与 B-11 族 D Voigt 同源 ⇒ 否
③ 线性多步法 + 有理解方程（y'=−ay²）—— Padé 超收敛（实测比值 52~64 非 4）⇒ 换超越解
④ Kramers–Kronig 与 Voigt 共享吸收线型 ⇒ 数值同源 ⇒ 否
⑤ 数值 Laplace 前向变换 —— 结构同源（截断 + 复合 Simpson ≡ B-16 族 B）⇒ 否
⑥ Chebyshev 谱配点 —— 已占 ⇒ 否
⑦ Ornstein–Uhlenbeck / Fokker–Planck —— 扩散方程 ≡ B-10 族 D ⇒ 否
⑧ 蒙特卡洛 —— 非确定性 ⇒ 否
⑨ 迭代线性求解（CG/Jacobi/SOR/多重网格）—— 整类已否 ⇒ 否
⑩ 超收敛类（Talbot/Stehfest、Romberg、Smolyak、复围道留数）—— 沉地板 ⇒ 否

血案（本批 / 复用）
------------------------------------------------------------------------------------------
① **有理解 ⇒ Padé 超收敛**：y'=−a·y² 的解是有理函数，GL 隐式 RK 实测比值 52~64（≈2^6）而非 16，
   且 n=64 残差 5.8e-14 **会撞 `d_criterion` ③「基线残差 >1e-12」红灯** ⇒ 换超越闭式方程
   y'=−a·e^{−y}（比值恢复 15.29~15.99），扫描网格下调为 n=[4,8,16,32]。
② **golden 量级须 ≥13.5×tol**：族 A 原档 (2.70,0.80) 的 g=0.01998 = 2.0×tol、族 B 原档 (1.00,0.80,1.20)
   的 g=0.02522 = 2.5×tol、族 C 原档 (1.10,0.90,1.80) 的 g=0.1332 = 13.3×tol ⇒ 三档全换。
③ **定档必须 = 扫描网格末端**：族 A 128/族 B 32/族 C 256，与扫描末端一致。
④ **Filon 段内 ∫cos·s^p 必须走解析原函数**（分部积分闭式）——若改用数值积该子积分，误差阶被其
   主导 ⇒ 比值崩到 2。
⑤ **GL 隐式 RK 的 Newton 迭代须用解析雅可比 ∂f/∂y = a·e^{−y}**（数值差分雅可比在 h 大时精度不足）。
⑥ **AB4 启动项与主式同阶（h⁴）**——启动器若降阶（如隐式欧拉）会把全局阶拖到 O(h)。

定档纪律：候选默认离散档 = 扫描网格末端（A: N=128 / B: n=32 / C: n=256），任何改动须同步。
"""

import math

import numpy as np

__all__ = [
    "golden_b297", "cand_b297", "golden_b298", "cand_b298", "golden_b299", "cand_b299",
    "golden_b300", "cand_b300", "golden_b301", "cand_b301", "golden_b302", "cand_b302",
    "golden_b303", "cand_b303", "golden_b304", "cand_b304", "golden_b305", "cand_b305",
    "golden_b306", "cand_b306", "golden_b307", "cand_b307",
    "golden_b308", "cand_b308", "golden_b309", "cand_b309", "golden_b310", "cand_b310",
    "golden_b311", "cand_b311", "golden_b312", "cand_b312",
    "_golden_by_bid", "_cand_by_bid", "_self_test",
]


# ==========================================================================================
# 族 A · 振荡积分 + Filon 型分段二次求积（B297-B302）
# ==========================================================================================
def _filon_exact(w, a):
    """I = ∫₀¹ cos(ω t)·e^{a t} dt 的初等闭式。

    Re[∫₀¹ e^{(a+iω)t} dt] = Re[(e^{a+iω} − 1)/(a + iω)]
                           = [e^a·(a·cos ω + ω·sin ω) − a]/(a² + ω²)
    ω→0 时退化为 (e^a − 1)/a；a→0 时退化为 sin ω/ω —— 两极限均无奇性。
    """
    return (math.exp(a) * (a * math.cos(w) + w * math.sin(w)) - a) / (a * a + w * w)


def _filon_ap(phi, w, L, p):
    """段内解析子积分 ∫₀^L cos(phi + ω s)·s^p ds（p = 0,1,2），分部积分闭式。"""
    wL = phi + w * L
    if p == 0:
        return (math.sin(wL) - math.sin(phi)) / w
    if p == 1:
        return L * math.sin(wL) / w + (math.cos(wL) - math.cos(phi)) / (w * w)
    return (L * L * math.sin(wL) / w + 2.0 * L * math.cos(wL) / (w * w)
            - 2.0 * math.sin(wL) / (w ** 3) + 2.0 * math.sin(phi) / (w ** 3))


def _filon_quad(w, a, N):
    """Filon 型求积：每 2h 一段，段内对 e^{at} 作二次 Lagrange 插值后**解析**积 cos 核。

    段 [x₀, x₀+2h] 上 g(t)=e^{at} 的二次插值在局部坐标 s∈[0,2h] 下为
      g ≈ g₀·L₀(s) + g₁·L₁(s) + g₂·L₂(s)
      L₀ = (s² − 3h·s + 2h²)/(2h²)、L₁ = (−s² + 2h·s)/h²、L₂ = (s² − h·s)/(2h²)
    ⇒ 段积分 = c₀·A₀ + c₁·A₁ + c₂·A₂，其中 A_p 走 `_filon_ap` 闭式，
      c₂ = (g₀/2 − g₁ + g₂/2)/h²、c₁ = (−3g₀/2 + 2g₁ − g₂/2)/h、c₀ = g₀。
    """
    h = 1.0 / N
    ih = 1.0 / h
    g = lambda t: math.exp(a * t)          # noqa: E731
    tot = 0.0
    for k in range(N // 2):
        x0 = 2 * k * h
        g0 = g(x0)
        g1 = g(x0 + h)
        g2 = g(x0 + 2 * h)
        phi = w * x0
        L = 2.0 * h
        c2 = (0.5 * g0 - g1 + 0.5 * g2) * ih * ih
        c1 = (-1.5 * g0 + 2.0 * g1 - 0.5 * g2) * ih
        tot += (g0 * _filon_ap(phi, w, L, 0)
                + c1 * _filon_ap(phi, w, L, 1)
                + c2 * _filon_ap(phi, w, L, 2))
    return tot


def golden_b297(w=1.30, a=2.00):
    return _filon_exact(w, a)


def cand_b297(w=1.30, a=2.00, N=128):
    return _filon_quad(w, a, N)


def golden_b298(w=1.10, a=2.40):
    return _filon_exact(w, a)


def cand_b298(w=1.10, a=2.40, N=128):
    return _filon_quad(w, a, N)


def golden_b299(w=4.10, a=1.50):
    return _filon_exact(w, a)


def cand_b299(w=4.10, a=1.50, N=128):
    return _filon_quad(w, a, N)


def golden_b300(w=0.90, a=2.50):
    return _filon_exact(w, a)


def cand_b300(w=0.90, a=2.50, N=128):
    return _filon_quad(w, a, N)


def golden_b301(w=3.30, a=1.10):
    return _filon_exact(w, a)


def cand_b301(w=3.30, a=1.10, N=128):
    return _filon_quad(w, a, N)


def golden_b302(w=2.10, a=1.90):
    return _filon_exact(w, a)


def cand_b302(w=2.10, a=1.90, N=128):
    return _filon_quad(w, a, N)


# ==========================================================================================
# 族 B · Gauss–Legendre 2 级隐式 RK（4 阶，A-稳定）（B303-B307）
# ==========================================================================================
_GL_C = [0.5 - math.sqrt(3.0) / 6.0, 0.5 + math.sqrt(3.0) / 6.0]
_GL_A = [[0.25, 0.25 - math.sqrt(3.0) / 6.0], [0.25 + math.sqrt(3.0) / 6.0, 0.25]]


def _gl_exact(a, y0, T):
    """y' = −a·e^{−y}, y(0)=y0 的超越初等闭式：e^y dy = −a dt ⇒ y(T) = ln(e^{y0} − aT)。"""
    return math.log(math.exp(y0) - a * T)


def _gl_implicit_rk4(a, y0, T, n):
    """Gauss–Legendre 2 级隐式 RK（4 阶）——每步 2×2 非线性隐式方程走 Newton（解析雅可比）。"""
    h = T / n
    y = y0
    f = lambda v: -a * math.exp(-v)        # noqa: E731
    dfdy = lambda v: a * math.exp(-v)      # noqa: E731
    for _s in range(n):
        k = np.array([f(y), f(y)], float)
        for _it in range(200):
            g1 = y + h * (_GL_A[0][0] * k[0] + _GL_A[0][1] * k[1])
            g2 = y + h * (_GL_A[1][0] * k[0] + _GL_A[1][1] * k[1])
            F = np.array([k[0] - f(g1), k[1] - f(g2)], float)
            d1 = dfdy(g1)
            d2 = dfdy(g2)
            J = np.array([[1.0 - h * _GL_A[0][0] * d1, -h * _GL_A[0][1] * d1],
                          [-h * _GL_A[1][0] * d2, 1.0 - h * _GL_A[1][1] * d2]], float)
            dk = np.linalg.solve(J, -F)
            k = k + dk
            if abs(dk[0]) + abs(dk[1]) < 1e-16:
                break
        y = y + h * 0.5 * (k[0] + k[1])
    return float(y)


def golden_b303(a=0.80, y0=0.50, T=1.00):
    return _gl_exact(a, y0, T)


def cand_b303(a=0.80, y0=0.50, T=1.00, n=32):
    return _gl_implicit_rk4(a, y0, T, n)


def golden_b304(a=0.50, y0=1.00, T=1.50):
    return _gl_exact(a, y0, T)


def cand_b304(a=0.50, y0=1.00, T=1.50, n=32):
    return _gl_implicit_rk4(a, y0, T, n)


def golden_b305(a=1.20, y0=0.40, T=0.80):
    return _gl_exact(a, y0, T)


def cand_b305(a=1.20, y0=0.40, T=0.80, n=32):
    return _gl_implicit_rk4(a, y0, T, n)


def golden_b306(a=0.90, y0=0.60, T=1.10):
    return _gl_exact(a, y0, T)


def cand_b306(a=0.90, y0=0.60, T=1.10, n=32):
    return _gl_implicit_rk4(a, y0, T, n)


def golden_b307(a=0.70, y0=0.90, T=1.30):
    return _gl_exact(a, y0, T)


def cand_b307(a=0.70, y0=0.90, T=1.30, n=32):
    return _gl_implicit_rk4(a, y0, T, n)



# ==========================================================================================
# 族 C · Adams–Bashforth 4 阶线性多步（B308-B312）
# ==========================================================================================
def _ab4_exact(a, y0, T):
    """y' = −a·sin(y), y(0)=y0 的超越初等闭式。

    dy/sin y = −a dt ⇒ ln|tan(y/2)| = −a t + C ⇒ y(T) = 2·arctan(tan(y0/2)·e^{−a T})。
    """
    return 2.0 * math.atan(math.tan(y0 / 2.0) * math.exp(-a * T))


def _ab4_integrate(a, y0, T, n):
    """Adams–Bashforth 4 阶线性多步；前 3 步用同阶 RK4 启动（启动项 h⁴，不主导全局阶）。"""
    h = T / n
    f = lambda v: -a * math.sin(v)         # noqa: E731
    ys = [y0]
    for _s in range(3):
        y = ys[-1]
        k1 = f(y)
        k2 = f(y + 0.5 * h * k1)
        k3 = f(y + 0.5 * h * k2)
        k4 = f(y + h * k3)
        ys.append(y + h * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0)
    for _s in range(3, n):
        ys.append(ys[-1] + h / 24.0 * (55.0 * f(ys[-1]) - 59.0 * f(ys[-2])
                                       + 37.0 * f(ys[-3]) - 9.0 * f(ys[-4])))
    return ys[-1]


def golden_b308(a=0.60, y0=1.30, T=1.20):
    return _ab4_exact(a, y0, T)


def cand_b308(a=0.60, y0=1.30, T=1.20, n=256):
    return _ab4_integrate(a, y0, T, n)


def golden_b309(a=0.90, y0=1.10, T=1.60):
    return _ab4_exact(a, y0, T)


def cand_b309(a=0.90, y0=1.10, T=1.60, n=256):
    return _ab4_integrate(a, y0, T, n)


def golden_b310(a=0.40, y0=1.50, T=2.00):
    return _ab4_exact(a, y0, T)


def cand_b310(a=0.40, y0=1.50, T=2.00, n=256):
    return _ab4_integrate(a, y0, T, n)


def golden_b311(a=0.75, y0=1.20, T=1.40):
    return _ab4_exact(a, y0, T)


def cand_b311(a=0.75, y0=1.20, T=1.40, n=256):
    return _ab4_integrate(a, y0, T, n)


def golden_b312(a=0.85, y0=1.00, T=1.60):
    return _ab4_exact(a, y0, T)


def cand_b312(a=0.85, y0=1.00, T=1.60, n=256):
    return _ab4_integrate(a, y0, T, n)


# ==========================================================================================
# 参数表 / 调度表 / 自检
# ==========================================================================================
_TOL = 0.01

_BIDS_A = ["B297", "B298", "B299", "B300", "B301", "B302"]
_BIDS_B = ["B303", "B304", "B305", "B306", "B307"]
_BIDS_C = ["B308", "B309", "B310", "B311", "B312"]
_ALL_BIDS = _BIDS_A + _BIDS_B + _BIDS_C

# 逐锚 tol（本批全部 0.01；golden 量级下限 ≈ 0.164 ⇒ 16.4×tol，未放宽）
_TOL_BY_BID = {bid: 0.01 for bid in _ALL_BIDS}

# 反向扰动键（连续物理参数；离散档位不作扰动键）
_PERTURB_KEYS = {}
for _b in _BIDS_A:
    _PERTURB_KEYS[_b] = ("w", "a")
for _b in _BIDS_B:
    _PERTURB_KEYS[_b] = ("a", "y0")
for _b in _BIDS_C:
    _PERTURB_KEYS[_b] = ("a", "y0")

_DEFAULT_PARAMS = {
    "B297": dict(w=1.30, a=2.00),
    "B298": dict(w=1.10, a=2.40),
    "B299": dict(w=4.10, a=1.50),
    "B300": dict(w=0.90, a=2.50),
    "B301": dict(w=3.30, a=1.10),
    "B302": dict(w=2.10, a=1.90),
    "B303": dict(a=0.80, y0=0.50, T=1.00),
    "B304": dict(a=0.50, y0=1.00, T=1.50),
    "B305": dict(a=1.20, y0=0.40, T=0.80),
    "B306": dict(a=0.90, y0=0.60, T=1.10),
    "B307": dict(a=0.70, y0=0.90, T=1.30),
    "B308": dict(a=0.60, y0=1.30, T=1.20),
    "B309": dict(a=0.90, y0=1.10, T=1.60),
    "B310": dict(a=0.40, y0=1.50, T=2.00),
    "B311": dict(a=0.75, y0=1.20, T=1.40),
    "B312": dict(a=0.85, y0=1.00, T=1.60),
}

# 候选自身的离散参数键 + 扫描网格（定档取末端）
_DISC_KEY = {}
for _b in _BIDS_A:
    _DISC_KEY[_b] = "N"
for _b in _BIDS_B:
    _DISC_KEY[_b] = "n"
for _b in _BIDS_C:
    _DISC_KEY[_b] = "n"

_SCAN_GRID = {}
for _b in _BIDS_A:
    _SCAN_GRID[_b] = [16, 32, 64, 128]
for _b in _BIDS_B:
    _SCAN_GRID[_b] = [4, 8, 16, 32]
for _b in _BIDS_C:
    _SCAN_GRID[_b] = [32, 64, 128, 256]

_GOLDEN_FN = {
    "B297": golden_b297, "B298": golden_b298, "B299": golden_b299,
    "B300": golden_b300, "B301": golden_b301, "B302": golden_b302,
    "B303": golden_b303, "B304": golden_b304, "B305": golden_b305,
    "B306": golden_b306, "B307": golden_b307,
    "B308": golden_b308, "B309": golden_b309, "B310": golden_b310,
    "B311": golden_b311, "B312": golden_b312,
}

_CAND_FN = {
    "B297": cand_b297, "B298": cand_b298, "B299": cand_b299,
    "B300": cand_b300, "B301": cand_b301, "B302": cand_b302,
    "B303": cand_b303, "B304": cand_b304, "B305": cand_b305,
    "B306": cand_b306, "B307": cand_b307,
    "B308": cand_b308, "B309": cand_b309, "B310": cand_b310,
    "B311": cand_b311, "B312": cand_b312,
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

    checks = []
    # A: ω→0 ⇒ I = (e^a − 1)/a
    checks.append(("A ω→0 极限 = (e^a−1)/a",
                   abs(golden_b297(w=0.0, a=2.0) - (math.exp(2.0) - 1.0) / 2.0) < 1e-14))
    # A: a→0 ⇒ I = sin ω/ω
    checks.append(("A a→0 极限 = sin ω/ω",
                   abs(golden_b297(w=1.30, a=0.0) - math.sin(1.30) / 1.30) < 1e-14))
    # A: 第三方交叉（scipy.integrate.quad）
    try:
        from scipy.integrate import quad as _quad
        _q = _quad(lambda t: math.cos(1.30 * t) * math.exp(2.00 * t), 0.0, 1.0)[0]
        checks.append(("A 与 scipy.integrate.quad 交叉 <1e-10", abs(golden_b297() - _q) < 1e-10))
    except Exception:
        checks.append(("A 与 scipy.integrate.quad 交叉 <1e-10", False))
    # B: T=0 ⇒ y0
    checks.append(("B T=0 退化为初值 y0", abs(golden_b303(T=0.0) - 0.50) < 1e-14))
    # B: a=0 ⇒ y0
    checks.append(("B a=0 退化为初值 y0", abs(golden_b303(a=0.0) - 0.50) < 1e-14))
    # B: 小 aT ⇒ y0 − aT·e^{−y0}
    _sm = golden_b303(a=1e-9, T=1.0)
    checks.append(("B 小 aT 极限 = y0 − aT·e^{−y0}",
                   abs(_sm - (0.50 - 1e-9 * math.exp(-0.50))) < 1e-15))
    # C: a=0 ⇒ y0
    checks.append(("C a=0 退化为初值 y0", abs(golden_b308(a=0.0) - 1.30) < 1e-14))
    # C: 小 y0 ⇒ y0·e^{−aT}（线性衰减极限）
    _lin = golden_b308(y0=1e-6)
    checks.append(("C 小 y0 极限 = y0·e^{−aT}",
                   abs(_lin - 1e-6 * math.exp(-0.60 * 1.20)) < 1e-16))
    # C: 第三方交叉（scipy.integrate.solve_ivp DOP853）
    try:
        from scipy.integrate import solve_ivp as _ivp
        _sol = _ivp(lambda t, y: [-0.60 * math.sin(y[0])], [0.0, 1.20], [1.30],
                    rtol=1e-13, atol=1e-15, method="DOP853")
        checks.append(("C 与 scipy.solve_ivp(DOP853) 交叉 <1e-10",
                       abs(golden_b308() - float(_sol.y[0][-1])) < 1e-10))
    except Exception:
        checks.append(("C 与 scipy.solve_ivp(DOP853) 交叉 <1e-10", False))

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
