# -*- coding: utf-8 -*-
"""Batch B-16 双方法独立锚数值核（v0.9.96 · P1-1 路径 B 扩基续十五 · 腿① 续加锚稀释 terminal）

本批 16 道（B265-B280），**三族**（批次内族数不固定，承 B-10 的 5/6/2/3 先例）：

  · 族 A（B265-B270，6 道）**Burgers 方程 tanh 行波精确解**
      方程  u_t + u·u_x = ν·u_xx   （非线性对流–扩散 PDE，新方程类）
      行波解 u(x,t) = c·[1 − tanh(c(x − c·t − x₀)/(2ν))] — 代入得恒等式：
        u_t = cBk·sech²、u·u_x = −ABk·sech² + B²k·sech²·tanh、ν·u_xx = 2νBk²·sech²·tanh
        令 A = c、B = 2νk 逐项抵消 ⇒ 精确解（不需要任何近似）
      golden = c·[1 − tanh(c·ξ/(2ν))]，ξ = x* − c·T − x₀ 取 0.5（过渡区中心附近，灵敏度最佳）
      cand   = 显式 RK4 + 二阶中心差分（对流）/ 二阶中心差分（扩散）时间推进到 t = T
      域 [−40, 40] 两端 Dirichlet（左 2c、右 0）—— 边界距观测点 40 个单位，
      T = 4 时波速 ~1、扩散长度 √(2νT) ≈ 2 ⇒ 边界反射/耗散均到不了观测点。

  · 族 B（B271-B275，5 道）**广义指数积分 E_n(x)**
      E_n(x) = ∫₁^∞ e^{−xt}/t^n dt（n = 1 时即 E1(x)）—— 新特殊函数类
      golden = scipy.special.exp1 / expn（范式同 B-10 的 mathieu_a、B-11 的 zeta/voigt_profile）
      cand   = 区间 [1, M] 截断 + 复合 Simpson 数值求积（M = 60，e^{−x·60} ≲ 1e−18）

  · 族 C（B276-B280，5 道）**Haar 小波多分辨投影（MRA）**
      f_p(x) = x^p on [0,1)；V_J 上正交投影 = 每段 [a,b] (h = 2^{−J}) 的段内平均
      golden = (1/h)∫_a^b x^p dx = (b^{p+1} − a^{p+1})/((p+1)·h)  — 初等闭式
      cand   = 从 2^K 个等距采样出发，逐层 Haar 低通 c ← (c[0::2] + c[1::2])/2 降到 J 层
      ⇒ 等权平均（左端点矩形）⇒ 残差 O(2^{−K})，一阶收敛（标称一阶）

------------------------------------------------------------------------------------------
【同源体检】（限定 `lda/`，排除 lda_cuda_venv / node_modules / vendor；**实际 grep 全仓**）

  ① Burgers / 非线性对流–扩散：`burgers|激波|shock|traveling_wave|eikonal|fast_marching|
     level_set|水平集|rayleigh_ritz|manning|eckart`
     ⇒ 命中仅 3 处，**全部无关**：`detector_bandwidth_true.py` 的 Ramo–Shockley（人名）、
       `_batch_b15_numeric.py:89` 的「Godunov（Riemann 求解器）—— 激波处格式退化 O(h^{1/2})」
       （B-15 **被否候选**的记录文本，非实现）。
     ⇒ Burgers / 行波 / 非线性抛物 **零占用** ✅
  ② 广义指数积分：`exp1|expn|expi\\(|指数积分|exponential_integral`
     ⇒ 命中仅 `_batch_b13_numeric.py` 的 `_k_exp1`（Volterra 核 **e^{−x}**，名字撞车、对象不同）。
     ⇒ E_n / E1 / Ei **零占用** ✅
  ③ Haar 多分辨：`wavelet|小波|haar|daubechies|multiresolution|多分辨`
     ⇒ 命中仅 `golden.py:313` 的「**Haar 平均态保真度**」——那是量子通信的 **Haar 随机态**
       （S 系列锚的平均态保真度一阶系数），与 Haar **小波**是完全不同的对象。
     ⇒ Haar 小波 / MRA **零占用** ✅
  ④ 顺带核验并**主动弃用**的两族（避免踩同域）：
     · `landau|zener|rabi|二能级|tdse` ⇒ 命中 20+ 处，全是 `lda_agent/*` 的 **QEDA 设计引擎**
       （JC 模型读出的真空拉比分裂 `rabi_split_ghz`、驱动场 Rabi/AC Stark、D-43/D-88），
       属**设计模块**而非验证锚；但同域风险不可忽略 ⇒ **放弃 Landau–Zener 候选**。
     · `dipole|偶极|antenna|天线|radiation_pattern|方向图` ⇒ `mie_solver.py` 的 Rayleigh
       **散射**偶极子极限（Q_scat = (8/3)x⁴r²，与天线辐射不同对象）+ `lda_l2` 的相控阵
       **市场数据** + `golden_product_benchmarks` 把「天线辐射/光束控制」列入**黑箱负面清单**
       ⇒ **放弃偶极子天线候选**。

【本批被否候选（同源体检不通过）】
  ① 非定常 2D 抛物 **ADI**（交替方向隐式）—— 与 B-10 族 D「线性扩散基础解热核（Crank–Nicolson
     时间推进）」**同算子 ∂_t − D∇²**，仅维度与离散格式不同 ⇒ 结构同源 ⇒ 否。
  ② **TMM 多层膜 / 方势垒传输矩阵** —— 把**均匀层**离散成 N 子层时每段 TMM 精确 ⇒ 残差恒 0，
     撞判据 D「代数恒等」红线（与 B-10 Mathieu-FG 同型失败模式）⇒ 否。
  ③ **有限体积 / Godunov** —— B-15 已否（守恒律激波处 O(h^{1/2})，单调性易破）⇒ 否。
  ④ **复围道留数积分** —— 解析函数在圆周上梯形求积**指数收敛** ⇒ 残差沉地板，与自证桩不可区分 ⇒ 否。
  ⑤ **Kirsch 圆孔应力集中** —— 若走 Airy 应力函数则 ≡ B-15 族 B 的双调和 ∇⁴ 算子（同算子）⇒ 否；
     若走 Navier 位移法则需在不规则孔边界上离散 2 阶**向量**系统，边界处理成本 ≈ 重开一道锚 ⇒ 否。
  ⑥ **Eckart / Manning–Rosen 势束缚态** —— 与 B-9 族 B「Hulthen 势 3D s-wave」同为
     「解析可解势 + 径向 Schrödinger」，且 B-9 族 D 已占 sech²+tanh 类 ⇒ 结构同源 ⇒ 否。
  ⑦ **一维弹性波 / 传输线方程（Telegrapher）** —— 与 B-15 族 C「一阶双曲输运」同型 ⇒ 否。
  ⑧ **Pöschl–Teller 势** —— 纯 sech² 与 B-9 族 D「Rosen–Morse II（sech² + tanh）」同势族 ⇒ 否。
  ⑨ **Laplace 数值反演（Talbot/Stehfest）** —— B-13 已否（超收敛沉地板）⇒ 否。
  ⑩ **蒙特卡洛类** —— 非确定性 ⇒ 否。

【本批血案】（实测补充，见下方各函数 docstring；编号与报告 §6 对齐）
------------------------------------------------------------------------------------------
"""
import numpy as np
from scipy import special as _sp

__all__ = [
    # 族 A · Burgers tanh 行波
    "golden_b265", "golden_b266", "golden_b267", "golden_b268", "golden_b269", "golden_b270",
    "cand_b265", "cand_b266", "cand_b267", "cand_b268", "cand_b269", "cand_b270",
    # 族 B · 广义指数积分
    "golden_b271", "golden_b272", "golden_b273", "golden_b274", "golden_b275",
    "cand_b271", "cand_b272", "cand_b273", "cand_b274", "cand_b275",
    # 族 C · Haar 小波多分辨投影
    "golden_b276", "golden_b277", "golden_b278", "golden_b279", "golden_b280",
    "cand_b276", "cand_b277", "cand_b278", "cand_b279", "cand_b280",
]

# ==========================================================================================
# 族 A · Burgers 方程 tanh 行波（B265-B270）
# ==========================================================================================
_A_T = 4.0          # 推进到 t = T
_A_DOM = 40.0       # 半域：[-_A_DOM, +_A_DOM]
_A_SHIFT = 0.5      # ξ = x* − cT − x₀ 固定为 +0.5（落过渡区，避免平台饱和）


def _burgers_x0(c, T, xstar):
    """由「观测点恒落过渡区中心偏上 0.5」反解初值位置 x₀。"""
    return xstar - c * T - _A_SHIFT


def _burgers_exact(x, t, c, nu, x0):
    return c * (1.0 - np.tanh(c * (x - c * t - x0) / (2.0 * nu)))


def _burgers_rhs(u, h, nu, c):
    """du/dt = −u·u_x + ν·u_xx（二阶中心差分；两端 Dirichlet，故边界导数为 0）。"""
    r = np.zeros_like(u)
    up, u0, um = u[2:], u[1:-1], u[:-2]
    ux = (up - um) / (2.0 * h)
    uxx = (up - 2.0 * u0 + um) / (h * h)
    r[1:-1] = -u0 * ux + nu * uxx
    return r


def _burgers_solve(c, nu, n, T=_A_T, xstar=0.0):
    """显式 RK4 + 二阶中心差分；dt 取 0.4×min(CFL, 扩散稳定限) 保稳。

    血案①：中心差分对流的稳定前提是**网格 Peclet < 2**（Pe = c·h/ν）。
    本批最细档 h = 80/1600 = 0.05、max(c/ν) = 1.4/0.6 ⇒ Pe = 0.117，安全。
    """
    x = np.linspace(-_A_DOM, _A_DOM, n + 1)
    h = 2.0 * _A_DOM / n
    x0 = _burgers_x0(c, T, xstar)
    u = _burgers_exact(x, 0.0, c, nu, x0)
    umax = 2.0 * c
    dt = 0.4 * min(h / umax, h * h / (2.0 * nu))
    nt = int(np.ceil(T / dt))
    dt = T / nt
    for _ in range(nt):
        k1 = _burgers_rhs(u, h, nu, c)
        k2 = _burgers_rhs(u + 0.5 * dt * k1, h, nu, c)
        k3 = _burgers_rhs(u + 0.5 * dt * k2, h, nu, c)
        k4 = _burgers_rhs(u + dt * k3, h, nu, c)
        u = u + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        u[0] = 2.0 * c
        u[-1] = 0.0
    i = int(round((xstar + _A_DOM) / h))
    return float(u[i])


def _golden_burgers(c, nu, T=_A_T, xstar=0.0):
    xi = _A_SHIFT
    return float(c * (1.0 - np.tanh(c * xi / (2.0 * nu))))


def _cand_burgers(c, nu, T=_A_T, xstar=0.0, n=1600):
    return _burgers_solve(c, nu, n, T=T, xstar=xstar)


def golden_b265(c=1.0, nu=0.5, T=_A_T, xstar=0.0):
    return _golden_burgers(c, nu, T, xstar)


def cand_b265(c=1.0, nu=0.5, T=_A_T, xstar=0.0, n=1600):
    return _cand_burgers(c, nu, T, xstar, n)


def golden_b266(c=1.2, nu=0.5, T=_A_T, xstar=0.0):
    return _golden_burgers(c, nu, T, xstar)


def cand_b266(c=1.2, nu=0.5, T=_A_T, xstar=0.0, n=1600):
    return _cand_burgers(c, nu, T, xstar, n)


def golden_b267(c=0.9, nu=0.45, T=_A_T, xstar=0.0):
    return _golden_burgers(c, nu, T, xstar)


def cand_b267(c=0.9, nu=0.45, T=_A_T, xstar=0.0, n=1600):
    return _cand_burgers(c, nu, T, xstar, n)


def golden_b268(c=1.4, nu=0.6, T=_A_T, xstar=0.0):
    return _golden_burgers(c, nu, T, xstar)


def cand_b268(c=1.4, nu=0.6, T=_A_T, xstar=0.0, n=1600):
    return _cand_burgers(c, nu, T, xstar, n)


def golden_b269(c=1.0, nu=0.4, T=_A_T, xstar=0.0):
    return _golden_burgers(c, nu, T, xstar)


def cand_b269(c=1.0, nu=0.4, T=_A_T, xstar=0.0, n=1600):
    return _cand_burgers(c, nu, T, xstar, n)


def golden_b270(c=1.1, nu=0.5, T=_A_T, xstar=0.0):
    return _golden_burgers(c, nu, T, xstar)


def cand_b270(c=1.1, nu=0.5, T=_A_T, xstar=0.0, n=1600):
    return _cand_burgers(c, nu, T, xstar, n)


# ==========================================================================================
# 族 B · 广义指数积分 E_n(x) = ∫₁^∞ e^{−xt}/t^n dt（B271-B275）
# ==========================================================================================
_B_M = 60.0    # 积分上限：x ≥ 0.3 ⇒ e^{−x·60} ≤ 1.4e−18（远低于双精度地板）


def _expn_simpson(nn, x, N):
    """复合 Simpson 求 ∫₁^M e^{−xt}/t^n dt，2N+1 个节点（N 段，步长 (M−1)/N）。

    血案②：**截断上限 M 必须让尾部残值落到机器精度之下**——被积函数尾部 ~e^{−xM}，
    x 越小衰减越慢（本批最小 x = 0.3）⇒ 若沿用常见 M=40 则尾部 ~6e−6，会**盖住**
    最细档的离散误差，使判据 D 的末项停在 1e−5 而非 < tol。取 M = 60 后尾部 ≤ 1.4e−18。
    """
    t = np.linspace(1.0, _B_M, 2 * N + 1)
    f = np.exp(-x * t) / np.power(t, float(nn))
    w = np.ones(2 * N + 1)
    w[1:-1:2] = 4.0
    w[2:-1:2] = 2.0
    return float((_B_M - 1.0) / (6.0 * float(N)) * np.dot(w, f))


def _golden_expn(nn, x):
    return float(_sp.exp1(x)) if int(nn) == 1 else float(_sp.expn(int(nn), x))


def _cand_expn(nn, x, N):
    return _expn_simpson(nn, x, N)


def golden_b271(nn=1, x=0.3):
    return _golden_expn(nn, x)


def cand_b271(nn=1, x=0.3, N=80):
    return _cand_expn(nn, x, N)


def golden_b272(nn=1, x=0.6):
    return _golden_expn(nn, x)


def cand_b272(nn=1, x=0.6, N=80):
    return _cand_expn(nn, x, N)


def golden_b273(nn=1, x=1.0):
    return _golden_expn(nn, x)


def cand_b273(nn=1, x=1.0, N=80):
    return _cand_expn(nn, x, N)


def golden_b274(nn=2, x=0.5):
    return _golden_expn(nn, x)


def cand_b274(nn=2, x=0.5, N=80):
    return _cand_expn(nn, x, N)


def golden_b275(nn=2, x=1.0):
    return _golden_expn(nn, x)


def cand_b275(nn=2, x=1.0, N=80):
    return _cand_expn(nn, x, N)


# ==========================================================================================
# 族 C · Haar 小波多分辨投影（B276-B280）
# ==========================================================================================
def _haar_avg(p, J, k, K):
    """从 2^K 等距采样出发，逐层 Haar 低通 c ← (c[0::2] + c[1::2])/2 降到 V_J，取第 k 段系数。

    血案③：**Haar 低通的等权平均是「左端点矩形」，一阶收敛（O(2^{−K})），不是二阶**——
    因为降采样只用到 2^{K−J} 个**位于段左端点**的采样值（x_i = i/2^K 中 i 为
    k·2^{K−J} … (k+1)2^{K−J}−1），没有右端点配对。故判据 D 的比值应为 **~2**（K +1 ⇒ 残差 ÷2），
    写成 4 会被误判为「收敛阶与算法不符」。若想要二阶，须改用梯形配对而非 Haar 块平均。
    """
    m = 2 ** K
    xs = np.arange(m, dtype=float) / float(m)
    c = np.power(xs, float(p))
    for _j in range(K, J, -1):
        c = 0.5 * (c[0::2] + c[1::2])
    return float(c[k])


def _golden_haar(p, J, k):
    """V_J 上正交投影 = 段内平均：(1/h)∫_a^b x^p dx = (b^{p+1} − a^{p+1})/((p+1)h)。"""
    h = 2.0 ** (-J)
    a = float(k) * h
    b = float(k + 1) * h
    return float((b ** (p + 1.0) - a ** (p + 1.0)) / ((p + 1.0) * h))


def _cand_haar(p, J, k, K):
    return _haar_avg(p, J, k, K)


def golden_b276(p=0.5, J=3, k=3):
    return _golden_haar(p, J, k)


def cand_b276(p=0.5, J=3, k=3, K=13):
    return _cand_haar(p, J, k, K)


def golden_b277(p=0.5, J=4, k=7):
    return _golden_haar(p, J, k)


def cand_b277(p=0.5, J=4, k=7, K=13):
    return _cand_haar(p, J, k, K)


def golden_b278(p=0.75, J=3, k=5):
    return _golden_haar(p, J, k)


def cand_b278(p=0.75, J=3, k=5, K=13):
    return _cand_haar(p, J, k, K)


def golden_b279(p=1.5, J=3, k=2):
    return _golden_haar(p, J, k)


def cand_b279(p=1.5, J=3, k=2, K=13):
    return _cand_haar(p, J, k, K)


def golden_b280(p=2.0, J=4, k=9):
    return _golden_haar(p, J, k)


def cand_b280(p=2.0, J=4, k=9, K=13):
    return _cand_haar(p, J, k, K)


# ==========================================================================================
# 参数表 / 调度表 / 自检
# ==========================================================================================
_TOL = 0.01

_BIDS_A = ["B265", "B266", "B267", "B268", "B269", "B270"]
_BIDS_B = ["B271", "B272", "B273", "B274", "B275"]
_BIDS_C = ["B276", "B277", "B278", "B279", "B280"]
_ALL_BIDS = _BIDS_A + _BIDS_B + _BIDS_C

# 逐锚 tol（本批全部 0.01；golden 量级下限 ≈ 0.16 ⇒ ≥16×tol，未放宽）
_TOL_BY_BID = {bid: 0.01 for bid in _ALL_BIDS}

# 反向扰动键（连续物理参数；nn/J/k 为离散档位、不作扰动键）
_PERTURB_KEYS = {}
for _b in _BIDS_A:
    _PERTURB_KEYS[_b] = ("c", "nu")
for _b in _BIDS_B:
    _PERTURB_KEYS[_b] = ("x",)
for _b in _BIDS_C:
    _PERTURB_KEYS[_b] = ("p",)

_DEFAULT_PARAMS = {
    "B265": dict(c=1.0, nu=0.5),
    "B266": dict(c=1.2, nu=0.5),
    "B267": dict(c=0.9, nu=0.45),
    "B268": dict(c=1.4, nu=0.6),
    "B269": dict(c=1.0, nu=0.4),
    "B270": dict(c=1.1, nu=0.5),
    "B271": dict(nn=1, x=0.3),
    "B272": dict(nn=1, x=0.6),
    "B273": dict(nn=1, x=1.0),
    "B274": dict(nn=2, x=0.5),
    "B275": dict(nn=2, x=1.0),
    "B276": dict(p=0.5, J=3, k=3),
    "B277": dict(p=0.5, J=4, k=7),
    "B278": dict(p=0.75, J=3, k=5),
    "B279": dict(p=1.5, J=3, k=2),
    "B280": dict(p=2.0, J=4, k=9),
}

# 候选自身的离散参数键 + 扫描网格（定档取末端）
_DISC_KEY = {}
for _b in _BIDS_A:
    _DISC_KEY[_b] = "n"
for _b in _BIDS_B:
    _DISC_KEY[_b] = "N"
for _b in _BIDS_C:
    _DISC_KEY[_b] = "K"

_SCAN_GRID = {}
for _b in _BIDS_A:
    _SCAN_GRID[_b] = [200, 400, 800, 1600]
for _b in _BIDS_B:
    _SCAN_GRID[_b] = [10, 20, 40, 80]
for _b in _BIDS_C:
    _SCAN_GRID[_b] = [10, 11, 12, 13]

_GOLDEN_FN = {
    "B265": golden_b265, "B266": golden_b266, "B267": golden_b267,
    "B268": golden_b268, "B269": golden_b269, "B270": golden_b270,
    "B271": golden_b271, "B272": golden_b272, "B273": golden_b273,
    "B274": golden_b274, "B275": golden_b275,
    "B276": golden_b276, "B277": golden_b277, "B278": golden_b278,
    "B279": golden_b279, "B280": golden_b280,
}

_CAND_FN = {
    "B265": cand_b265, "B266": cand_b266, "B267": cand_b267,
    "B268": cand_b268, "B269": cand_b269, "B270": cand_b270,
    "B271": cand_b271, "B272": cand_b272, "B273": cand_b273,
    "B274": cand_b274, "B275": cand_b275,
    "B276": cand_b276, "B277": cand_b277, "B278": cand_b278,
    "B279": cand_b279, "B280": cand_b280,
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

    # ---- 闭式极限自检 ----
    checks = []
    # A: ν→∞ ⇒ tanh→0 ⇒ u→c（均匀流极限）
    checks.append(("A ν→∞ 极限 u→c", abs(golden_b265(c=1.0, nu=1.0e7) - 1.0) < 1e-6))
    # B: 递推 n·E_{n+1}(x) = e^{−x} − x·E_n(x)（scipy 值域内）
    for (nn, x) in [(1, 0.5), (2, 1.0), (1, 2.0)]:
        lhs = float(nn) * _golden_expn(nn + 1, x)
        rhs = np.exp(-x) - x * _golden_expn(nn, x)
        checks.append(("B 递推 nE_{n+1}=e^-x−xE_n (n=%d,x=%.1f)" % (nn, x), abs(lhs - rhs) < 1e-12))
    # B: E1 与 exp1 在 x=1 的已知值
    checks.append(("B E1(1)=0.2193839344", abs(_golden_expn(1, 1.0) - 0.21938393439552029) < 1e-14))
    # C: p=1 ⇒ 段内平均 = 段中点 (k+0.5)h
    for (J, k) in [(3, 3), (4, 7)]:
        want = (k + 0.5) * 2.0 ** (-J)
        checks.append(("C p=1 线性段内平均=中点 (J=%d,k=%d)" % (J, k),
                       abs(_golden_haar(1.0, J, k) - want) < 1e-15))
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
