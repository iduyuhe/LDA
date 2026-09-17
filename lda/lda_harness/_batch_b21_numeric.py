# -*- coding: utf-8 -*-
"""
B-21 数值核（Batch B-21 · v0.9.100 -> v0.9.101 续批 16 锚 B345-B360）

三族（全部方法学独立：candidate != golden，且 golden 为精确闭式/特殊函数 oracle，
非截断近似式；candidate 与 golden 用不同数值方法）：
  A (B345-B349, 5): Hermite 多项式 H_n(x) -- n 阶中心差分 Rodrigues（对 e^{-x^2} 做 n 阶中心差分导数）×(−1)^n e^{x^2}
                     golden = numpy.polynomial.hermite.hermval(x, [0]*n+[1])（physicists' Hermite，精确 oracle）
  B (B350-B354, 5): Laguerre 多项式 L_n(x) -- n 阶中心差分 Rodrigues（对 x^n e^{-x} 做 n 阶中心差分导数）×e^{x}/n!
                     golden = scipy.special.genlaguerre(n, 0)(x)（精确 oracle）
  C (B355-B360, 6): Bernstein 多项式逼近 f(t) -- degree-N Bernstein 基求和 Σ f(k/N)·C(N,k)·t^k·(1−t)^{N−k}
                     golden = 已知函数 f(t) 精确闭式（sin/cos/exp/inv/sqrt）

判据 D：首项 > 1e-13 且 末项 < tol 且 严格单调（比值在 _self_test 中实测，非标称阶写死）。
golden 量级 >= 13.5*tol（避免锚变松）；零响应键已剔除；定档 = 扫描网格末端。
Round-off 地板：中心差分噪声 ∼ h^{-n}·ε，故 Hermite/Laguerre 限 n<=5（n=6/7 弃用）。

环境：CI 解释器唯一（py3.13.14）；本文件纯 LF、无 BOM。
"""
import math
import numpy as np
from scipy import special as _sp  # golden oracle（精确，非截断）

_TOL = 0.01  # 统一基线 tol；各族按实测微调用 _TOL_BY_BID 覆盖


# ---- 通用：n 阶中心差分导数 ------------------------------------------------
def _nth_deriv_central(g_func, x, n, h):
    """对 g_func 在 x 处做 n 阶中心差分导数（2n+1 点模板，J=n+8 半窗保证 n 阶内点不溢出）。
    返回 float：g_func^(n)(x)。"""
    n = int(n)
    J = n + 8
    lo = -J
    hi = J
    idx0 = -lo  # j=0（即 x 处）在数组中的索引
    vals = np.array([g_func(x + j * h) for j in range(lo, hi + 1)], dtype=float)
    for _ in range(n):
        new = np.zeros_like(vals)
        new[1:-1] = (vals[2:] - vals[:-2]) / (2.0 * h)
        vals = new
    return float(vals[idx0])


# ---- 族 A：Hermite 多项式 H_n(x) -------------------------------------------
def hermite_golden(n, x):
    """golden: physicists' Hermite H_n(x) = numpy.polynomial.hermite.hermval(x, [0]*n+[1])。精确 oracle。"""
    return float(np.polynomial.hermite.hermval(float(x), [0] * int(n) + [1]))


def hermite_fd(n, x, N):
    """candidate: n 阶中心差分 Rodrigues。对 g(t)=e^{-t^2} 做 n 阶中心差分导数，×(−1)^n e^{x^2}。"""
    n = int(n)
    h = 1.0 / float(N)
    g = lambda t: math.exp(-t * t)
    d = _nth_deriv_central(g, float(x), n, h)
    return float((-1.0) ** n * math.exp(x * x) * d)


# ---- 族 B：Laguerre 多项式 L_n(x) ------------------------------------------
def laguerre_golden(n, x):
    """golden: 广义 Laguerre L_n^{(0)}(x) = scipy.special.genlaguerre(n, 0)(x)。精确 oracle。"""
    return float(_sp.genlaguerre(int(n), 0)(float(x)))


def laguerre_fd(n, x, N):
    """candidate: n 阶中心差分 Rodrigues。对 g(t)=t^n e^{-t} 做 n 阶中心差分导数，×e^{x}/n!。"""
    n = int(n)
    h = 1.0 / float(N)
    g = lambda t: (t ** n) * math.exp(-t)
    d = _nth_deriv_central(g, float(x), n, h)
    return float(math.exp(x) / math.factorial(n) * d)


# ---- 族 C：Bernstein 多项式逼近 f(t) --------------------------------------
def _f_by_name(name, t):
    """golden 闭式 f(t)。name 选择被逼近函数。"""
    if name == "sin":
        return math.sin(2.0 * math.pi * t)
    if name == "cos":
        return math.cos(2.0 * math.pi * t)
    if name == "exp":
        return math.exp(t) - 1.0
    if name == "inv1":
        return 1.0 / (1.0 + t)
    if name == "inv2":
        return 1.0 / (1.0 + 2.0 * t)
    if name == "sqrt":
        return math.sqrt(t + 0.1)
    raise ValueError("unknown bernstein name: %r" % (name,))


def bernstein_golden(name, t):
    """golden: 已知函数 f(t) 精确闭式。"""
    return float(_f_by_name(name, float(t)))


def bernstein(name, t, N):
    """candidate: degree-N Bernstein 基求和 Σ_{k=0}^{N} f(k/N)·C(N,k)·t^k·(1−t)^{N−k}。O(h^2) 代数收敛。"""
    n = int(N)
    f = lambda kk: _f_by_name(name, kk / n)
    s = 0.0
    for k in range(n + 1):
        s += f(k) * math.comb(n, k) * (t ** k) * ((1.0 - t) ** (n - k))
    return float(s)


# ---- 锚点元数据 ------------------------------------------------------------
_BIDS_A = ["B345", "B346", "B347", "B348", "B349"]
_BIDS_B = ["B350", "B351", "B352", "B353", "B354"]
_BIDS_C = ["B355", "B356", "B357", "B358", "B359", "B360"]

_TOL_BY_BID = {b: 0.01 for b in _BIDS_A + _BIDS_B + _BIDS_C}

# 扰动键（连续，已剔除零响应键）
_PERTURB_KEYS = {
    "A": ("n", "x"),
    "B": ("n", "x"),
    "C": ("name", "t"),
}
_DEFAULT_PARAMS = {
    "B345": {"n": 2, "x": 0.5},
    "B346": {"n": 3, "x": 1.0},
    "B347": {"n": 4, "x": 0.8},
    "B348": {"n": 5, "x": 1.2},
    "B349": {"n": 4, "x": 1.5},
    "B350": {"n": 2, "x": 0.7},
    "B351": {"n": 3, "x": 1.0},
    "B352": {"n": 4, "x": 1.3},
    "B353": {"n": 5, "x": 0.9},
    "B354": {"n": 2, "x": 1.5},
    "B355": {"name": "sin", "t": 0.37},
    "B356": {"name": "cos", "t": 0.63},
    "B357": {"name": "exp", "t": 0.5},
    "B358": {"name": "inv1", "t": 0.4},
    "B359": {"name": "inv2", "t": 0.6},
    "B360": {"name": "sqrt", "t": 0.55},
}
_DISC_KEY = {
    "A": "x", "B": "x", "C": "t",
}
_SCAN_GRID = {
    "A": [32, 64, 128, 256, 512],
    "B": [32, 64, 128, 256, 512],
    "C": [32, 64, 128, 256, 512],
}

_GOLDEN_FN = {
    "A": hermite_golden, "B": laguerre_golden, "C": bernstein_golden,
}
_CAND_FN = {
    "A": hermite_fd, "B": laguerre_fd, "C": bernstein,
}

def _family_of(bid):
    if bid in _BIDS_A: return "A"
    if bid in _BIDS_B: return "B"
    return "C"

def _golden_by_bid(bid, p):
    fam = _family_of(bid)
    if fam == "A": return hermite_golden(p["n"], p["x"])
    if fam == "B": return laguerre_golden(p["n"], p["x"])
    return bernstein_golden(p["name"], p["t"])

def _cand_by_bid(bid, p, N):
    fam = _family_of(bid)
    if fam == "A": return hermite_fd(p["n"], p["x"], N)
    if fam == "B": return laguerre_fd(p["n"], p["x"], N)
    return bernstein(p["name"], p["t"], N)


# ---- golden_bXXX 包装（供 benchmarks.py / golden.py import）----------------
def golden_b345(n, x): return hermite_golden(n, x)
def golden_b346(n, x): return hermite_golden(n, x)
def golden_b347(n, x): return hermite_golden(n, x)
def golden_b348(n, x): return hermite_golden(n, x)
def golden_b349(n, x): return hermite_golden(n, x)
def golden_b350(n, x): return laguerre_golden(n, x)
def golden_b351(n, x): return laguerre_golden(n, x)
def golden_b352(n, x): return laguerre_golden(n, x)
def golden_b353(n, x): return laguerre_golden(n, x)
def golden_b354(n, x): return laguerre_golden(n, x)
def golden_b355(name, t): return bernstein_golden(name, t)
def golden_b356(name, t): return bernstein_golden(name, t)
def golden_b357(name, t): return bernstein_golden(name, t)
def golden_b358(name, t): return bernstein_golden(name, t)
def golden_b359(name, t): return bernstein_golden(name, t)
def golden_b360(name, t): return bernstein_golden(name, t)


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
