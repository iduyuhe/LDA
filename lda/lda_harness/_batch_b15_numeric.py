"""Batch B-15 数值核：四族 16 道（B249-B264）。每族均为**新方程类 / 新数值方法类**，
与既有 266 道锚（B1-B248）**方程 / 算子 / 方法均不同源**。

设计纪律（同源 B-14）：每道锚 = 一个**确定性解析闭式 golden** 对拍 一个**不同源真实数值法候选**。
golden 必须是闭式精确解（非截断级数 / 非微扰展开 / 非经验拟合），候选须带**离散参数**且
收敛阶可实测（判据 D：首项 >1e-13、末项 < tol、**严格单调**）。

四族 16 道（B249-B264）
----------------------------------------------------------------------
A. 延迟泛函微分方程（DDE）· 分步法（method of steps）              B249-B252（4 道）
   方程：y'(t) = -α·y(t-τ)，τ = TAU = 0.25（模块常数），α = r·e^{-rτ}
   golden：y(t) = e^{-r t}（初等指数闭式；α 按上式标定使该函数精确成解）
   cand  ：分步递推 + 步内 **RK4（y 无关 ⇒ 退化为 Simpson 求积）+ 三次 Hermite 历史插值**
   观测：t = T = 1.2（固定）；参数 r ∈ {1.0, 0.75, 1.25, 1.5}
   收敛：h^4（实测比值恒 ~16.00）

B. Kirchhoff 薄板静力弯曲（双调和方程，4 阶椭圆算子）· 13 点差分    B253-B256（4 道）
   方程：D·∇⁴w = q(x,y)，简支（w=0 且 ∇²w=0 于边界），q = q0·sinπx·sinπy（[0,1]²）
   golden：w = q0/(D π⁴ (1/a²+1/b²)²)·sinπx·sinπy ⇒ 中心值 = q0/(4π⁴D)（初等闭式）
   cand  ：13 点双调和差分（∇⁴_h ≡ 5 点 Laplacian 复合）+ 简支 ghost 消去 w_ghost = -w_mirror
   观测：板中心 (0.5, 0.5)；参数 q0 ∈ {100,150,200,250}
   收敛：h²（实测比值 4.176 → 4.001）

C. 一维线性输运方程（一阶双曲型）· 半拉格朗日特征线法              B257-B260（4 道）
   方程：∂u/∂t + c·∂u/∂x = 0，周期域 [0,1)
   golden：u = u0(x - c t)（洛伦兹脉冲刚性平移 u0(x)=1/(1+25(x-0.5)²)，初等闭式）
   cand  ：特征线逆追踪（x_j - CFL·h，**非格点**）+ 4 点立方 Lagrange 重构（周期回绕）
   观测：x* ∈ {0.40, 0.30}，t* = T = 0.5，CFL = c·dt/h = 0.5（**非整数 ⇒ 不退化为纯平移**）
   收敛：h³（累计插值误差 ∝ m·h⁴ ∝ h³；实测比值 → 8.00）

D. 聚焦非线性 Schrödinger 方程 · 基态孤子 · 分裂步 Fourier（Strang） B261-B264（4 道）
   方程：i·u_t + u_xx + 2|u|²u = 0，周期域 [0,40)
   golden：u = A·sech(A(x-x0))·e^{iA²t} ⇒ 观测量 Re u(x*,T) = A·sech(A(x*-x0))·cos(A²T)
   cand  ：**算子分裂**（NL(dt/2) → L(dt) → NL(dt/2)，NL 相位 = 2|u|²dt）+ FFT 谱精确线性步
   观测：(x*, t*) = (19.6, 3.0)；参数 A ∈ {0.90,1.00,1.10,1.20}，x0 = 20.0
   收敛：dt²（实测比值 → 4.00）

----------------------------------------------------------------------
同源体检（本批第一道闸，v0.9.95 立）——**实际 grep 全仓**（限定 lda/，排除 venv/node_modules/vendor）
----------------------------------------------------------------------
① 数值同源 —— 既有 266 道锚已占用的特殊函数 / 方程类 / 方法类（逐批数值核族清单全量提取交叉核对，
   见 B-2..B-14 各模块 docstring）：
   本征值问题（B-5/6/7/8/9/10/11 族 A + B-12 族 C）、时间推进抛物型（B-10 族 D Crank-Nicolson、
   B-11 族 B RK4）、稳态边值 ODE 三对角 FDM（**B29 散热鳍**）、1D 波动方程本征（TL 波导）、
   Numerov 散射（**B49**）、EM FDTD `leapfrog`（lda_solver/fdtd*）、FFT 拍频（B14）、
   Bragg/Bloch 转移矩阵（B15/B35/B64）、复合 Simpson 求积（B-10/B-11 全族）、
   正交多项式高斯求积（B-12 族 A）、连分数（B-12 族 B）、代数求根 DK（B-12 族 C）、
   ₂F₁ Euler 积分（B-12 族 D）、分数阶 GL 卷积（B-13 族 A）、矩阵指数 scaling–squaring（B-13 族 B）、
   梯度下降优化（B-13 族 C）、Volterra 分块梯形递推（B-13 族 D）、
   定常对流–扩散中心差分（B-14 族 A）、Fredholm Nyström（B-14 族 B）、
   三次样条插值（B-14 族 C）、非线性 BVP 打靶（B-14 族 D）、
   2D 泊松五点差分（`lda_solver/drift_diffusion_2d.py`）。
   ⇒ 本批四族**均不落上述任何一类**：
   A = 泛函（延迟）微分方程 + 分步递推（既有锚全为常微分 / 偏微分 / 积分 / 代数）；且延迟项
       使 RHS 依赖**历史插值**，与 B-14 族 D 的「无延迟打靶」**不同方程**。
   B = **4 阶椭圆偏微分算子**（双调和 ∇⁴）——既有锚的 4 阶算子仅 B-9 族 A（Euler-Bernoulli
       **1 维 ODE** 本征值），B-13/B-14 的 2D 算子为**2 阶**（五点 Poisson）⇒ 阶数 + 维度双不同。
   C = **一阶双曲型**（特征线 / 半拉格朗日）。🔴 关键：`_batch_b11_numeric.py:47` 已把
       「**1D 波动方程 leapfrog**」列为**已否候选**（结构同源 fdtd1d/传输线求解器）——本族
       **不是** leapfrog / 不是 Yee 网格 / 不是二阶双曲；是**一阶**标量输运的**特征线逆追踪 +
       局部 Lagrange 重构**。与 B-14 族 A（定常对流–扩散 ODE 边值 + 中心差分）**不同**（非定常、
       无扩散、无三对角求解）；与 B-14 族 C（样条插值逼近函数）**不同**（主方法为输运推进，
       重构用 4 点局部 Lagrange 而非自然样条）。
   D = **非线性色散 PDE**（NLSE）+ **算子分裂 / 谱方法**。既有锚的时间推进仅 B-10 族 D（线性
       抛物）与 B-11 族 B（哈密顿 ODE）⇒ 非线性色散 PDE 为**新方程类**；分裂步 Fourier 与
       FDTD leapfrog / Chebyshev 配点（B-13 谱类）**不同**。

② 结构同源 —— grep 命中实测：
   · `biharmonic|双调和|薄板|plate_bend|kirchhoff_plate` 全仓（lda/）**0 命中** ⇒ FREE。
   · `lyapunov|sylvester|riccati|gramian|矩阵方程` 5 命中，**全为** `lda/lda_solver/mie_solver.py`
     的 Riccati-Bessel 递推 ψ_n=z·j_n / χ_n=−z·y_n（Mie 系数用）⇒ 与 Lyapunov 矩阵方程无关 ⇒ FREE。
   · `delay|delayed|延迟|dde|method_of_steps|历史插值` 22 命中，**全为**「延迟导入 / OFDR 群延迟 /
     TTD 真延时线」⇒ **无一是延迟微分方程** ⇒ 新。
   · `hyperbolic|双曲|leapfrog|蛙跳|d.?alembert|达朗贝尔|telegrapher|传输线方程|波动方程` 51 命中
     ⇒ 其中 `_batch_b11_numeric.py:47` 明确把 1D 波动 leapfrog 列为已否 ⇒ 本批**放弃**该族（改 C）。
   · `volterra|fredholm`、`spectral|collocation`、`interpolation|spline|shooting` 均已被既有锚占满
     ⇒ 本批四族**均不触碰**。

③ golden 非截断近似 —— 本批 16 道 golden **全部为初等闭式**：
   指数 e^{-rT} / 有理 1/(1+25(x-0.5)²) / 正弦-双曲 sech / 正弦 q0/(4π⁴D)；
   **无一是截断级数 / 微扰展开 / 渐近展开 / 经验拟合 / 查表插值**。

----------------------------------------------------------------------
选族阶段被否候选（9 项，逐条附否决理由）
----------------------------------------------------------------------
  · 1D 波动方程（达朗贝尔 + 显式蛙跳）——`_batch_b11_numeric.py:47` 已列已否：结构同源
    fdtd1d / 传输线求解器（Yee leapfrog）。
  · 三次样条求积 / Nyström 积分方程 —— ≡ B-12 求积类 / B-14 族 B。
  · 双曲型守恒律 Godunov（Riemann 求解器）—— 激波处格式退化 O(h^{1/2})，判据 D 单调性易破。
  · NLSE 用 Chebyshev 谱配点求解 —— ≡ B-13 谱配点类（改用分裂步 Fourier）。
  · 连续 Lyapunov / Sylvester 矩阵方程 —— 直接法残差落机器精度（**代数恒等红线**，
    判据 D 窗口不成立）；迭代法（Jacobi/Richardson）属**线性求解类**，B-14 §2.3 已否 CG/Jacobi。
  · Stefan 相变相似解 / Black-Scholes 期权闭式 —— golden 均走 **erf / erfc**（N(·) = ½erfc），
    ≡ B30 特殊函数同源。
  · Padé / 有理函数逼近 —— ≡ B-12 族 B 连分数（有理逼近同族）。
  · 反问题（Tikhonov 正则化最小二乘）—— 固定正则子 ⇒ 残差随 n 收敛停滞于正则偏差，
    判据 D「末项 < tol 且严格单调」不成立；耦合 α(h) → 0 则又回到病态离散。
  · 自适应求积 / Romberg 外推 —— 超收敛 ⇒ 残差落 round-off 地板（B-10 血案 5）。

----------------------------------------------------------------------
本轮血案（9 条，均已规避并固化为实现约束）
----------------------------------------------------------------------
 1. 【非线性相位因子漏 2 ⇒ 方案与被验证方程不一致】族 D 首版把 NLSE 非线性步写成
    `u * exp(i|u|²dt)`（正确为 `exp(2i|u|²dt)`）⇒ 等效相位速率错成 A²/2 ⇒ 残差恒 ~1.38
    且**不随 dt 下降**（比值 → 0.99）。**指纹：残差对离散参数零收敛 ⇒ 必为方程/系数不一致，
    而非收敛慢。** 修 `2|u|²` 后比值恒 ~4.00。
 2. 【周期镜像地板】族 D 取 L=20 时残差在 n≥1024 处收敛停滞（~1e-5）；**NX 加倍（250→1000）
    完全无变化** ⇒ 证明地板非空间离散 ⇒ 改 **L=40**（镜像距离加倍，sech 尾巴 e^{-20}→e^{-40}）。
    一般规则：周期域上「局部化解 vs 无限域闭式」的对比，域长必须让镜像尾巴低于目标 tol 的
    1e-6 量级，否则判据 D 会在细档处**假平台**。
 3. 【分步法步长超延迟】族 A 扫描含 n=4（h=0.3 > τ=0.25）⇒ 首步 RK4 级就要取 y(t-τ) 且
    t-τ>0，此时历史点**尚未算出** ⇒ IndexError。**分步法硬约束 h ≤ τ** ⇒ 扫描下界
    n ≥ T/τ = 4.8 ⇒ 取 n ≥ 8（模块内加 `if h > TAU: raise` 守卫）。
 4. 【历史插值因果越界】族 A 的 `hist()` 首版把上界 clamp 写成「全网格长度 - 2」而非
    「**已算出点数 - 2**」⇒ 读到未来点 ⇒ IndexError；且 `ys`/`ds` 追加不同步会使 clamp
    基准错位（以 `len(ys)` 为准时 `ds[j+1]` 越界）⇒ **clamp 必须以 `len(ds)` 为准**。
 5. 【参数化必须让特征根成为闭式，且扰动必须可放大】族 A 首版取**临界延迟** τ=π/(2α)
    （特征根纯虚 ⇒ 初等三角闭式 cos(αt)）：虽数学漂亮，但 **α ×1.1 的信号仅 0.25×tol**
    ⇒ 被反向判据（须 >1.4×tol）直接否掉。改「**指数衰减解**」参数化（α = r·e^{-rτ} 标定
    ⇒ y = e^{-rt}）后信号升至 **2.72~3.50×tol**。
    一般规则：**振荡解的指标对参数不敏感（导数 ∝ 1/T），指数解的指标敏感（相对灵敏度 ∝ rT）**。
 6. 【零响应键：延迟 τ 对 golden 恒零响应】族 A 的 golden = e^{-rT} **不含 τ**（τ 只影响
    候选的离散过程）⇒ 若把 τ 注册进 `_PERTURB_KEYS`，×1.1 信号恒 0 ⇒ 稀释 C3/C5
    （B-11 血案 8 同源）。**处置：τ 降为模块常数 TAU=0.25**（不入 `default_params`）。
 7. 【余量不足】族 B 默认档 n=128 时余量仅 **155×**（低于 B-14 实测底线 366×）⇒ 默认档
    提到 **n=256** ⇒ 余量 **621×~1552×**。
 8. 【观测点落平台区 ⇒ 反向信号贴门槛】族 C 的 B257（c=0.5）在 x*=0.30 处落洛伦兹脉冲
    半高处，T 键 ×1.1 信号仅 **1.44×tol**（贴 1.4× 门槛）⇒ 观测点移到 **x*=0.40**（信号
    回升 **2.47×tol**）。（B-14 血案 6 的近亲：观测点必须落在**梯度敏感区**。）
 9. 【整数 CFL 退化为纯平移 ⇒ 残差恒 0】族 C 若取 c·dt/h ∈ ℤ，则特征线逆追踪的落点恰为
    格点，4 点 Lagrange 重构**恰等于格点值** ⇒ 残差恒 0（**代数恒等红线**，判据 D 判 BAD）。
    本族固定 **CFL = 0.5**（落点恒在半格点 ⇒ 重构权重为常数 (-1/16, 9/16, 9/16, -1/16)），
    并要求步数 m = cTn/CFL = c·n 为整数（观则时刻与格点严格对齐，避免时间插值污染）。
    一般规则：**特征线 / 半拉格朗日类的离散参数扫描必须同时满足「落点非格点」与
    「观测时刻恰为格点」**。
"""

import math

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

__all__ = [
    "golden_b249", "cand_b249", "golden_b250", "cand_b250",
    "golden_b251", "cand_b251", "golden_b252", "cand_b252",
    "golden_b253", "cand_b253", "golden_b254", "cand_b254",
    "golden_b255", "cand_b255", "golden_b256", "cand_b256",
    "golden_b257", "cand_b257", "golden_b258", "cand_b258",
    "golden_b259", "cand_b259", "golden_b260", "cand_b260",
    "golden_b261", "cand_b261", "golden_b262", "cand_b262",
    "golden_b263", "cand_b263", "golden_b264", "cand_b264",
]

# ======================================================================
# 族 A：延迟泛函微分方程（DDE）· 分步法 + 三次 Hermite 历史插值
# ======================================================================

TAU = 0.25          # 延迟（模块常数；对 golden 零响应 ⇒ 不入 default_params，见血案 6）
_A_T = 1.2          # 观测时刻 t = T（四锚共用）


def _dde_alpha(r):
    """延迟反馈增益：α = r·e^{-rτ}（按此标定使 y = e^{-rt} 精确成解）。"""
    return r * math.exp(-r * TAU)


def _hermite(y0, d0, y1, d1, h, s):
    """[0,h] 上三次 Hermite（值 + 一阶导两端点）⇒ 局部四阶。"""
    t = s / h
    return ((2.0 * t ** 3 - 3.0 * t ** 2 + 1.0) * y0
            + (t ** 3 - 2.0 * t ** 2 + t) * h * d0
            + (-2.0 * t ** 3 + 3.0 * t ** 2) * y1
            + (t ** 3 - t ** 2) * h * d1)


def _dde_solve(r, T, n):
    """分步法：m 步（h = T/n ≤ τ），步内 RK4（RHS 与 y 无关 ⇒ 退化为 Simpson），
    历史 y(t-τ) 用「已算出点」的三次 Hermite 插值；t-τ ≤ 0 用解析历史 e^{-rt}。"""
    a = _dde_alpha(r)
    h = T / n
    if h > TAU:
        raise ValueError("分步法要求 h<=tau：h=%.6f tau=%.6f（n 需 >= %.1f）"
                         % (h, TAU, T / TAU))
    ts = [i * h for i in range(n + 1)]
    ys = [1.0]                      # y(0) = e^0
    ds = [-r]                       # y'(0) = -r（解析历史在 t<=0 处精确）

    def hist(s):
        if s <= 0.0:
            return math.exp(-r * s)
        j = int(s / h)
        if j > len(ds) - 2:         # 只用已算出的历史点（血案 4：因果越界）
            j = len(ds) - 2
        if j < 0:
            j = 0
        return _hermite(ys[j], ds[j], ys[j + 1], ds[j + 1], h, s - ts[j])

    for k in range(n):
        t = ts[k]
        y = ys[k]
        k1 = -a * hist(t - TAU)
        k2 = -a * hist(t + 0.5 * h - TAU)
        k3 = k2
        k4 = -a * hist(t + h - TAU)
        ys.append(y + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4))
        ds.append(-a * hist(t + h - TAU))
    return ys[-1]


def golden_b249(r, T=_A_T):
    """y(T) = e^{-rT}（α = r e^{-rτ} 标定下的精确解）。"""
    return math.exp(-r * T)


def cand_b249(r, T=_A_T, n=64):
    return _dde_solve(r, T, n)


def golden_b250(r, T=_A_T):
    return math.exp(-r * T)


def cand_b250(r, T=_A_T, n=64):
    return _dde_solve(r, T, n)


def golden_b251(r, T=_A_T):
    return math.exp(-r * T)


def cand_b251(r, T=_A_T, n=64):
    return _dde_solve(r, T, n)


def golden_b252(r, T=_A_T):
    return math.exp(-r * T)


def cand_b252(r, T=_A_T, n=64):
    return _dde_solve(r, T, n)


# ======================================================================
# 族 B：Kirchhoff 薄板静力弯曲（双调和）· 13 点差分（简支）
# ======================================================================

_B_OFFS = [(0, 0, 20.0),
           (1, 0, -8.0), (-1, 0, -8.0), (0, 1, -8.0), (0, -1, -8.0),
           (1, 1, 2.0), (1, -1, 2.0), (-1, 1, 2.0), (-1, -1, 2.0),
           (2, 0, 1.0), (-2, 0, 1.0), (0, 2, 1.0), (0, -2, 1.0)]


def _biharmonic_center(q0, dp, n):
    """[0,1]² 简支薄板 D∇⁴w = q0·sinπx·sinπy 的中心挠度。

    13 点双调和模板（≡ 5 点 Laplacian 复合）；简支边界 w=0 且 ∇²w=0，
    后者在边界点处给出 ghost 关系 w_{-1,j} = -w_{1,j}（血案见 B-9 符号纪律）。
    """
    m = n - 1
    N = m * m
    h = 1.0 / n
    rows, cols, vals = [], [], []
    rhs = np.zeros(N)
    for i in range(1, n):
        for j in range(1, n):
            r = (i - 1) * m + (j - 1)
            for di, dj, cf in _B_OFFS:
                a, b = i + di, j + dj
                if a < 0:                       # ghost：w_{-1,j} = -w_{1,j}
                    rows.append(r); cols.append(j - 1); vals.append(-cf)
                elif a > n:                     # ghost：w_{n+1,j} = -w_{n-1,j}
                    rows.append(r); cols.append((n - 2) * m + (j - 1)); vals.append(-cf)
                elif b < 0:
                    rows.append(r); cols.append((i - 1) * m); vals.append(-cf)
                elif b > n:
                    rows.append(r); cols.append((i - 1) * m + (n - 2)); vals.append(-cf)
                elif a == 0 or a == n or b == 0 or b == n:
                    pass                        # 边界 w = 0
                else:
                    rows.append(r); cols.append((a - 1) * m + (b - 1)); vals.append(cf)
            rhs[r] = (h ** 4) * q0 * math.sin(math.pi * i * h) * math.sin(math.pi * j * h) / dp
    A = sp.csr_matrix((vals, (rows, cols)), shape=(N, N))
    w = spla.spsolve(A, rhs)
    ic = n // 2
    return float(w[(ic - 1) * m + (ic - 1)])


def golden_b253(q0, dp=1.0):
    """中心挠度 w(a/2,b/2) = q0/(D π⁴ (1/a²+1/b²)²)，a=b=1 ⇒ q0/(4π⁴D)。"""
    return q0 / (4.0 * math.pi ** 4 * dp)


def cand_b253(q0, dp=1.0, n=256):
    return _biharmonic_center(q0, dp, n)


def golden_b254(q0, dp=1.0):
    return q0 / (4.0 * math.pi ** 4 * dp)


def cand_b254(q0, dp=1.0, n=256):
    return _biharmonic_center(q0, dp, n)


def golden_b255(q0, dp=1.0):
    return q0 / (4.0 * math.pi ** 4 * dp)


def cand_b255(q0, dp=1.0, n=256):
    return _biharmonic_center(q0, dp, n)


def golden_b256(q0, dp=1.0):
    return q0 / (4.0 * math.pi ** 4 * dp)


def cand_b256(q0, dp=1.0, n=256):
    return _biharmonic_center(q0, dp, n)


# ======================================================================
# 族 C：一维线性输运方程（一阶双曲型）· 半拉格朗日特征线法
# ======================================================================

_CFL = 0.5
_W4 = (-1.0 / 16.0, 9.0 / 16.0, 9.0 / 16.0, -1.0 / 16.0)   # 4 点立方 Lagrange 在半格点


def _u0(x):
    """洛伦兹脉冲初值（初等闭式）。"""
    x = x % 1.0
    return 1.0 / (1.0 + 25.0 * (x - 0.5) ** 2)


def _transport(c, T, xs, n):
    """半拉格朗日：m 步，每步 u_j <- U(x_j - CFL·h)（4 点立方 Lagrange，周期回绕）。

    m = round(cT/(CFL·h)) = c·n/CFL·... ⇒ 取 cT/(CFL·h) 的整数（观则时刻恰为格点）。
    """
    h = 1.0 / n
    m = int(round(c * T / (_CFL * h)))
    xi = np.arange(n) * h
    u = 1.0 / (1.0 + 25.0 * (xi - 0.5) ** 2)
    for _ in range(m):
        u = (_W4[0] * np.roll(u, 2) + _W4[1] * np.roll(u, 1)
             + _W4[2] * u + _W4[3] * np.roll(u, -1))
    return float(u[int(round(xs * n)) % n])


def golden_b257(c, T=0.5, xs=0.40):
    """u(x*,T) = u0(x* - cT)（特征线刚性平移闭式）。"""
    return _u0(xs - c * T)


def cand_b257(c, T=0.5, xs=0.40, n=320):
    return _transport(c, T, xs, n)


def golden_b258(c, T=0.5, xs=0.30):
    return _u0(xs - c * T)


def cand_b258(c, T=0.5, xs=0.30, n=320):
    return _transport(c, T, xs, n)


def golden_b259(c, T=0.5, xs=0.30):
    return _u0(xs - c * T)


def cand_b259(c, T=0.5, xs=0.30, n=320):
    return _transport(c, T, xs, n)


def golden_b260(c, T=0.5, xs=0.30):
    return _u0(xs - c * T)


def cand_b260(c, T=0.5, xs=0.30, n=320):
    return _transport(c, T, xs, n)


# ======================================================================
# 族 D：聚焦 NLSE 基态孤子 · 分裂步 Fourier（Strang）
# ======================================================================

_D_L = 40.0                                  # 域长（L=40：镜像尾巴 e^{-40} 远低于 tol）
_D_NX = 500
_D_DX = _D_L / _D_NX
_D_X0 = 20.0                                 # 孤子中心（默认）
_D_XS_I = 245                                # 观测点索引 ⇒ x* = 19.6
_D_T = 3.0                                   # 观测时刻
_D_XS = _D_XS_I * _D_DX
_D_K = 2.0 * math.pi * np.fft.fftfreq(_D_NX, d=_D_DX)
_D_XG = np.arange(_D_NX) * _D_DX


def _nlse_real(A, x0, T, n):
    """分裂步 Fourier：Strang（NL(dt/2) → L(dt) → NL(dt/2)），NL 相位 = 2|u|²dt。"""
    u = (A / np.cosh(A * (_D_XG - x0))).astype(complex)
    dt = T / n
    lin = np.exp(-1j * _D_K * _D_K * dt)
    for _ in range(n):
        u = u * np.exp(0.5j * 2.0 * np.abs(u) ** 2 * dt)
        u = np.fft.ifft(lin * np.fft.fft(u))
        u = u * np.exp(0.5j * 2.0 * np.abs(u) ** 2 * dt)
    return float(np.real(u[_D_XS_I]))


def golden_b261(A, x0=_D_X0, T=_D_T):
    """Re u(x*,T) = A·sech(A(x*-x0))·cos(A²T)（孤子闭式）。"""
    return A / math.cosh(A * (_D_XS - x0)) * math.cos(A * A * T)


def cand_b261(A, x0=_D_X0, T=_D_T, n=2048):
    return _nlse_real(A, x0, T, n)


def golden_b262(A, x0=_D_X0, T=_D_T):
    return A / math.cosh(A * (_D_XS - x0)) * math.cos(A * A * T)


def cand_b262(A, x0=_D_X0, T=_D_T, n=2048):
    return _nlse_real(A, x0, T, n)


def golden_b263(A, x0=_D_X0, T=_D_T):
    return A / math.cosh(A * (_D_XS - x0)) * math.cos(A * A * T)


def cand_b263(A, x0=_D_X0, T=_D_T, n=2048):
    return _nlse_real(A, x0, T, n)


def golden_b264(A, x0=_D_X0, T=_D_T):
    return A / math.cosh(A * (_D_XS - x0)) * math.cos(A * A * T)


def cand_b264(A, x0=_D_X0, T=_D_T, n=2048):
    return _nlse_real(A, x0, T, n)


# ======================================================================
# 表：tol / 反向键 / 物理参数 / 定档
# ======================================================================

_TOL = 0.01

# 逐锚 tol：本批指标量级（族 A 0.165~0.407；族 B 0.257~0.642；族 C 0.246~0.941；
# 族 D −0.916~−0.411）——**每一锚的 |golden| 均 ≥ 16.5× tol**，统一 tol=0.01 即可。
# worst-case 余量 B256 621×；最弱反向信号 B253 2.33× tol（>1.4× 门槛）。
_TOL_BY_BID = {
    "B249": 0.01, "B250": 0.01, "B251": 0.01, "B252": 0.01,
    "B253": 0.01, "B254": 0.01, "B255": 0.01, "B256": 0.01,
    "B257": 0.01, "B258": 0.01, "B259": 0.01, "B260": 0.01,
    "B261": 0.01, "B262": 0.01, "B263": 0.01, "B264": 0.01,
}

# 反向测试注册键（C5：key ×1.1 的信号须 > 1.4×tol）
# · 族 A 只注册 r / T：**τ 对 golden 零响应**（golden = e^{-rT} 不含 τ）⇒ 已降为模块常数
#   TAU（血案 6）。
# · 族 D 只注册 A / x0：T 是**弱响应键**（×1.1 信号仅 0.24×tol）⇒ 不入 default_params。
_PERTURB_KEYS = {
    "B249": ("r", "T"), "B250": ("r", "T"), "B251": ("r", "T"), "B252": ("r", "T"),
    "B253": ("q0", "dp"), "B254": ("q0", "dp"), "B255": ("q0", "dp"), "B256": ("q0", "dp"),
    "B257": ("c", "T", "xs"), "B258": ("c", "T", "xs"),
    "B259": ("c", "T", "xs"), "B260": ("c", "T", "xs"),
    "B261": ("A", "x0"), "B262": ("A", "x0"), "B263": ("A", "x0"), "B264": ("A", "x0"),
}

# 每锚物理参数（= benchmarks.py 的 default_params；harness 以 golden_fn(**params) 调）
_DEFAULT_PARAMS = {
    "B249": {"r": 1.0, "T": 1.2}, "B250": {"r": 0.75, "T": 1.2},
    "B251": {"r": 1.25, "T": 1.2}, "B252": {"r": 1.5, "T": 1.2},
    "B253": {"q0": 100.0, "dp": 1.0}, "B254": {"q0": 150.0, "dp": 1.0},
    "B255": {"q0": 200.0, "dp": 1.0}, "B256": {"q0": 250.0, "dp": 1.0},
    "B257": {"c": 0.5, "T": 0.5, "xs": 0.40}, "B258": {"c": 1.0, "T": 0.5, "xs": 0.30},
    "B259": {"c": 1.5, "T": 0.5, "xs": 0.30}, "B260": {"c": 2.0, "T": 0.5, "xs": 0.30},
    "B261": {"A": 0.90, "x0": 20.0}, "B262": {"A": 1.00, "x0": 20.0},
    "B263": {"A": 1.10, "x0": 20.0}, "B264": {"A": 1.20, "x0": 20.0},
}

# bid -> (golden_fn, cand_fn, 默认离散参数, 离散参数名, 参数标签)
_CASES = {
    # ---- 族 A：延迟泛函微分方程（分步法） ----
    "B249": (golden_b249, cand_b249, 64, "n", "DDE 指数衰减解 r=1.0, y(1.2)"),
    "B250": (golden_b250, cand_b250, 64, "n", "DDE 指数衰减解 r=0.75, y(1.2)"),
    "B251": (golden_b251, cand_b251, 64, "n", "DDE 指数衰减解 r=1.25, y(1.2)"),
    "B252": (golden_b252, cand_b252, 64, "n", "DDE 指数衰减解 r=1.5, y(1.2)"),
    # ---- 族 B：双调和薄板（13 点差分） ----
    "B253": (golden_b253, cand_b253, 256, "n", "双调和薄板 q0=100 中心挠度"),
    "B254": (golden_b254, cand_b254, 256, "n", "双调和薄板 q0=150 中心挠度"),
    "B255": (golden_b255, cand_b255, 256, "n", "双调和薄板 q0=200 中心挠度"),
    "B256": (golden_b256, cand_b256, 256, "n", "双调和薄板 q0=250 中心挠度"),
    # ---- 族 C：一维输运（半拉格朗日特征线） ----
    "B257": (golden_b257, cand_b257, 320, "n", "输运 u_t+cu_x=0 c=0.5, u(0.40,0.5)"),
    "B258": (golden_b258, cand_b258, 320, "n", "输运 c=1.0, u(0.30,0.5)"),
    "B259": (golden_b259, cand_b259, 320, "n", "输运 c=1.5, u(0.30,0.5)"),
    "B260": (golden_b260, cand_b260, 320, "n", "输运 c=2.0, u(0.30,0.5)"),
    # ---- 族 D：NLSE 孤子（分裂步 Fourier） ----
    "B261": (golden_b261, cand_b261, 2048, "n", "NLSE 孤子 A=0.90, Re u(19.6,3)"),
    "B262": (golden_b262, cand_b262, 2048, "n", "NLSE 孤子 A=1.00, Re u(19.6,3)"),
    "B263": (golden_b263, cand_b263, 2048, "n", "NLSE 孤子 A=1.10, Re u(19.6,3)"),
    "B264": (golden_b264, cand_b264, 2048, "n", "NLSE 孤子 A=1.20, Re u(19.6,3)"),
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
    print("Batch B-15 数值核自检（16 锚）")
    print("=" * 76)

    print("\n[闭式极限自检] 候选在细档下应收敛到 golden 闭式")
    print("  A1 DDE r=1.0 n=512         : %.12f  闭式=%.12f"
          % (_dde_solve(1.0, _A_T, 512), golden_b249(1.0)))
    print("  A2 DDE r=1.5 n=512         : %.12f  闭式=%.12f"
          % (_dde_solve(1.5, _A_T, 512), golden_b252(1.5)))
    print("  B1 双调和 q0=100 n=512     : %.12f  闭式=%.12f"
          % (_biharmonic_center(100.0, 1.0, 512), golden_b253(100.0)))
    print("  B2 双调和 q0=250 n=512     : %.12f  闭式=%.12f"
          % (_biharmonic_center(250.0, 1.0, 512), golden_b256(250.0)))
    print("  C1 输运 c=1.0 n=640        : %.12f  闭式=%.12f"
          % (_transport(1.0, 0.5, 0.30, 640), golden_b258(1.0)))
    print("  C2 输运 c=2.0 n=640        : %.12f  闭式=%.12f"
          % (_transport(2.0, 0.5, 0.30, 640), golden_b260(2.0)))
    print("  D1 NLSE A=1.00 n=8192      : %.12f  闭式=%.12f"
          % (_nlse_real(1.00, _D_X0, _D_T, 8192), golden_b262(1.00)))
    print("  D2 NLSE A=0.90 n=8192      : %.12f  闭式=%.12f"
          % (_nlse_real(0.90, _D_X0, _D_T, 8192), golden_b261(0.90)))

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
        "B249": [8, 16, 32, 64], "B250": [8, 16, 32, 64],
        "B251": [8, 16, 32, 64], "B252": [8, 16, 32, 64],
        "B253": [4, 8, 16, 32, 64, 128, 256], "B254": [4, 8, 16, 32, 64, 128, 256],
        "B255": [4, 8, 16, 32, 64, 128, 256], "B256": [4, 8, 16, 32, 64, 128, 256],
        "B257": [20, 40, 80, 160, 320], "B258": [20, 40, 80, 160, 320],
        "B259": [20, 40, 80, 160, 320], "B260": [20, 40, 80, 160, 320],
        "B261": [32, 64, 128, 256, 512, 1024, 2048],
        "B262": [32, 64, 128, 256, 512, 1024, 2048],
        "B263": [32, 64, 128, 256, 512, 1024, 2048],
        "B264": [32, 64, 128, 256, 512, 1024, 2048],
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
