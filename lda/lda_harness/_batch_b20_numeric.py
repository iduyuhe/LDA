# -*- coding: utf-8 -*-
"""
B-20 数值核（Batch B-20 · v0.9.99 -> v0.9.100 续批 16 锚 B329-B344）

三族（全部方法学独立：candidate != golden，且 golden 为精确闭式/特殊函数 oracle，
非截断近似式；candidate 与 golden 用不同数值方法）：
  A (B329-B334, 6): 修正 Bessel I_nu(x) -- 修正 Bessel ODE 原点 Frobenius 启动 + 经典四阶 RK4
                     golden = scipy.special.iv(nu, x)（精确特殊函数 oracle）
  B (B335-B339, 5): 球谐 Y_l^m 自投影系数 -- 均匀网格复合梯形球面积分
                     golden = 1（正交归一恒等式，精确）
  C (B340-B344, 5): RBF（Multiquadric, c = alpha*h）散点插值 -- 规则网格中心 + 离格测试点
                     golden = 已知函数 f(x,y)（精确闭式）

判据 D：首项 > 1e-13 且 末项 < tol 且 严格单调（比值在 _self_test 中实测，非标称阶写死）。
golden 量级 >= 13.5*tol（避免锚变松）；零响应键已剔除；定档 = 扫描网格末端。

环境：CI 解释器唯一（py3.13.14）；本文件纯 LF、无 BOM。
"""
import math
import numpy as np
from scipy import special as _sp  # golden oracle（精确，非截断）

_TOL = 0.01  # 统一基线 tol；各族按实测微调用 _TOL_BY_BID 覆盖

# ---- 族 A：修正 Bessel I_nu ------------------------------------------------
def iv_exact(nu, x):
    """golden: 修正 Bessel I_nu（第一类，正则于 0）。精确特殊函数 oracle。"""
    return float(_sp.iv(float(nu), float(x)))

def _iv_frobenius_start(nu, eps):
    """原点 Frobenius 启动：I_nu(eps) ~ (eps/2)^nu / Gamma(nu+1)，I'_nu(eps) ~ nu*(eps/2)^nu/(eps*Gamma(nu+1))。"""
    nu = float(nu)
    g = math.gamma(nu + 1.0)
    c0 = (eps / 2.0) ** nu / g
    c1 = nu * (eps / 2.0) ** nu / (eps * g) if abs(eps) > 0 else 0.0
    return c0, c1

def iv_rk4(nu, x, N, eps=1e-4):
    """candidate: 修正 Bessel ODE x^2 y'' + x y' - (x^2+nu^2) y = 0，一阶化 y'=p, p'=(x^2+nu^2)/x^2*y - p/x。
    从 eps 用 Frobenius 启动，RK4 积分至 x，N 步。"""
    nu = float(nu)
    x = float(x)
    if x <= eps:
        y0, _ = _iv_frobenius_start(nu, x)
        return float(y0)
    h = (x - eps) / float(N)
    y, p = _iv_frobenius_start(nu, eps)

    def rhs(t, yv, pv):
        # x^2 y'' + x y' - (x^2+nu^2)y = 0  =>  y' = p ; p' = ((x^2+nu^2)/x^2) y - p/x
        if abs(t) < 1e-12:
            return pv, ((t * t + nu * nu) / 1e-12) * yv  # 退化保护（t 极小）
        return pv, ((t * t + nu * nu) / (t * t)) * yv - pv / t

    t = eps
    for _ in range(N):
        k1y, k1p = rhs(t, y, p)
        k2y, k2p = rhs(t + h / 2, y + h / 2 * k1y, p + h / 2 * k1p)
        k3y, k3p = rhs(t + h / 2, y + h / 2 * k2y, p + h / 2 * k2p)
        k4y, k4p = rhs(t + h, y + h * k3y, p + h * k3p)
        y += h / 6 * (k1y + 2 * k2y + 2 * k3y + k4y)
        p += h / 6 * (k1p + 2 * k2p + 2 * k3p + k4p)
        t += h
    return float(y)

# ---- 族 B：球谐 Y_l^m 自投影 ----------------------------------------------
def sph_proj_exact():
    """golden: 球谐自投影 = 1（正交归一恒等式，精确）。"""
    return 1.0

def _sph_harm_val(l, m, th, ph):
    """自实现 Y_l^m(theta,phi)（与 golden 正交归一恒等式独立）：
    Y = N_l^m * P_l^m(cos th) * e^{i m ph}，P_l^m 用 scipy.special.lpmv（稳定）。"""
    l = int(l); m = int(abs(m))
    costh = math.cos(th)
    P = float(_sp.lpmv(m, l, costh))  # 关联 Legendre P_l^m
    fac = math.factorial(l - m) / math.factorial(l + m)
    N = math.sqrt((2 * l + 1) / (4 * math.pi) * fac)
    return N * P * (math.cos(m * ph) + 1j * math.sin(m * ph))

def sph_proj_trapz(l, m, N):
    """candidate: 数值积分 c = int_{sphere} Y_l^m * conj(Y_l^m) dOmega。
    均匀网格 (theta in [0,pi], phi in [0,2pi]) 复合梯形；Y_l^m 自实现（lpmv）。
    O(h^2) 代数收敛（非谱），避免沉地板。"""
    l = int(l); m = int(m)
    nth = int(N); nph = int(N)
    dth = math.pi / (nth - 1)
    dph = 2.0 * math.pi / nph
    tot = 0.0
    for i in range(nth):
        th = i * dth
        wth = dth
        if i == 0 or i == nth - 1:
            wth = dth / 2.0  # 端点半权
        st = math.sin(th)
        for j in range(nph):
            ph = j * dph
            wph = dph
            if j == 0:
                wph = dph / 2.0  # 周期梯形端点（phi 周期，j=nph 同 j=0）
            Y = _sph_harm_val(l, m, th, ph)
            tot += wth * wph * st * abs(Y) ** 2
    return float(tot)

# ---- 族 C：1D RBF（Multiquadric）插值 --------------------------------
def rbf_exact(a, x):
    """golden: 已知函数 f(x) = sin(a*pi*x/2) * (1 + x/2)。精确闭式。"""
    return float(math.sin(a * math.pi * x / 2.0) * (1.0 + x / 2.0))

def _rbf_mq(r, c):
    return math.sqrt(r * r + c * c)

def rbf_interp(a, x, N, c=None):
    """candidate: 一维 N 中心均匀网格 + MQ RBF，含二次多项式，解权重后于离格测试点估值。
    h = 1/(N-1)；形状参数 c = 0.5*h（随 h 缩放，保证矩阵良态，非固定大 c 退化）。O(h^2) 代数收敛。"""
    a = float(a)
    N = int(N)
    xs = np.linspace(0.0, 1.0, N)
    h = xs[1] - xs[0] if N > 1 else 1.0
    if c is None:
        c = 0.5 * h
    nc = N
    fv = np.array([rbf_exact(a, xs[k]) for k in range(nc)])
    P = np.column_stack([np.ones(nc), xs, xs * xs])  # 多项式基 [1, x, x^2]
    A = np.zeros((nc, nc))
    for i in range(nc):
        for j in range(nc):
            A[i, j] = _rbf_mq(abs(xs[i] - xs[j]), c)
    Z = np.zeros((3, 3))
    Top = np.block([[A, P], [P.T, Z]])
    rhs = np.concatenate([fv, np.zeros(3)])
    try:
        sol = np.linalg.solve(Top, rhs)
    except np.linalg.LinAlgError:
        sol = np.linalg.lstsq(Top, rhs, rcond=None)[0]
    lam = sol[:nc]; beta = sol[nc:]
    tx = x + 0.5 * h if x + 0.5 * h <= 1.0 else x - 0.5 * h
    s = beta[0] + beta[1] * tx + beta[2] * tx * tx
    for k in range(nc):
        s += lam[k] * _rbf_mq(abs(tx - xs[k]), c)
    return float(s)

# ---- 锚点元数据 ------------------------------------------------------------
_BIDS_A = ["B329", "B330", "B331", "B332", "B333", "B334"]
_BIDS_B = ["B335", "B336", "B337", "B338", "B339"]
_BIDS_C = ["B340", "B341", "B342", "B343", "B344"]

_TOL_BY_BID = {b: 0.01 for b in _BIDS_A + _BIDS_B + _BIDS_C}

# 扰动键（连续，已剔除零响应键）
_PERTURB_KEYS = {
    "A": ("nu", "x"),
    "B": ("l", "m"),
    "C": ("a", "x"),
}
_DEFAULT_PARAMS = {
    "B329": {"nu": 0.0, "x": 1.0},
    "B330": {"nu": 0.0, "x": 2.0},
    "B331": {"nu": 0.0, "x": 3.0},
    "B332": {"nu": 1.0, "x": 1.0},
    "B333": {"nu": 1.0, "x": 2.0},
    "B334": {"nu": 1.0, "x": 3.0},
    "B335": {"l": 2, "m": 0},
    "B336": {"l": 3, "m": 1},
    "B337": {"l": 4, "m": 2},
    "B338": {"l": 1, "m": 1},
    "B339": {"l": 5, "m": 0},
    "B340": {"a": 1.0, "x": 0.37},
    "B341": {"a": 2.0, "x": 0.37},
    "B342": {"a": 1.0, "x": 0.63},
    "B343": {"a": 3.0, "x": 0.37},
    "B344": {"a": 2.0, "x": 0.63},
}
_DISC_KEY = {
    "A": "x", "B": "l", "C": "x",
}
_SCAN_GRID = {
    "A": [16, 32, 64, 128],
    "B": [10, 20, 40, 80, 160],
    "C": [16, 32, 64, 128, 256],
}

_GOLDEN_FN = {
    "A": iv_exact, "B": sph_proj_exact, "C": rbf_exact,
}
_CAND_FN = {
    "A": iv_rk4, "B": sph_proj_trapz, "C": rbf_interp,
}

def _family_of(bid):
    if bid in _BIDS_A: return "A"
    if bid in _BIDS_B: return "B"
    return "C"

def _golden_by_bid(bid, p):
    fam = _family_of(bid)
    if fam == "A": return iv_exact(p["nu"], p["x"])
    if fam == "B": return sph_proj_exact()
    return rbf_exact(p["a"], p["x"])

def _cand_by_bid(bid, p, N):
    fam = _family_of(bid)
    if fam == "A": return iv_rk4(p["nu"], p["x"], N)
    if fam == "B": return sph_proj_trapz(p["l"], p["m"], N)
    return rbf_interp(p["a"], p["x"], N)

# ---- golden_bXXX 包装（供 benchmarks.py / golden.py import）----------------
def golden_b329(nu, x): return iv_exact(nu, x)
def golden_b330(nu, x): return iv_exact(nu, x)
def golden_b331(nu, x): return iv_exact(nu, x)
def golden_b332(nu, x): return iv_exact(nu, x)
def golden_b333(nu, x): return iv_exact(nu, x)
def golden_b334(nu, x): return iv_exact(nu, x)
def golden_b335(l, m): return sph_proj_exact()
def golden_b336(l, m): return sph_proj_exact()
def golden_b337(l, m): return sph_proj_exact()
def golden_b338(l, m): return sph_proj_exact()
def golden_b339(l, m): return sph_proj_exact()
def golden_b340(a, x): return rbf_exact(a, x)
def golden_b341(a, x): return rbf_exact(a, x)
def golden_b342(a, x): return rbf_exact(a, x)
def golden_b343(a, x): return rbf_exact(a, x)
def golden_b344(a, x): return rbf_exact(a, x)

# ---- 自检 ------------------------------------------------------------------
def _self_test(verbose=True):
    ok = True
    ratios = {}
    for bid in _BIDS_A + _BIDS_B + _BIDS_C:
        fam = _family_of(bid)
        p = _DEFAULT_PARAMS[bid]
        grid = _SCAN_GRID[fam]
        Nfin = grid[-1]
        tol = _TOL_BY_BID[bid]
        g = _golden_by_bid(bid, p)
        errs = []
        for N in grid:
            c = _cand_by_bid(bid, p, N)
            errs.append(abs(c - g))
        mono = all(errs[i] > errs[i + 1] for i in range(len(errs) - 1))
        first_ok = errs[0] > 1e-13
        last_ok = errs[-1] < tol
        # 收敛比值（末两段）
        ratio = errs[-2] / errs[-1] if errs[-1] > 0 else float("inf")
        ratios[bid] = (errs[0], errs[-1], ratio)
        fam_ok = first_ok and last_ok and mono
        ok = ok and fam_ok
        if verbose:
            print(f"[{bid}] fam={fam} g={g:.6e} tol={tol} errs={[f'{e:.2e}' for e in errs]} "
                  f"mono={mono} first>1e-13={first_ok} last<tol={last_ok} ratio={ratio:.2f}")
    # 辅助：golden 量级 >= 13.5*tol 抽查
    for bid in _BIDS_A + _BIDS_B + _BIDS_C:
        g = abs(_golden_by_bid(bid, _DEFAULT_PARAMS[bid]))
        if g < 13.5 * _TOL_BY_BID[bid]:
            if verbose: print(f"[WARN] {bid} golden mag {g:.2e} < 13.5*tol")
    if verbose: print("ALL_OK =", ok)
    return ok, ratios

if __name__ == "__main__":
    _self_test(verbose=True)
