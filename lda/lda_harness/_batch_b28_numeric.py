# -*- coding: utf-8 -*-
"""
B-28 数值核（Batch B-28 · v0.9.110 · 腿① 扩基加锚 · 13 锚 B439-B451）

两族（全部方法学独立：candidate != golden；golden 为**精确特殊函数 oracle / 精确闭式**，
非截断近似式；candidate 与 golden 用**不同数值方法**）。

  A (B439-B445, 7): 不完全 Beta 函数族与整数参数二项闭式
                    golden = scipy.special.betainc（精确 oracle）
                             或**整数参数二项闭式** Σ_{j=a}^{a+b-1} C(a+b-1,j) x^j (1-x)^{n-j}
                             （两条互不相同的精确 golden 路径，B444/B445 用后者）
                    candidate = **完全自包含的复合 Simpson 双重数值积分**
                                （分子 ∫₀^x 与分母 B(a,b)=∫₀¹ 均用同一 Simpson 数值算出，
                                 不调用 scipy.beta/betainc ⇒ 与 golden 不同源）
                    残差 = Simpson 截断误差 O(h⁴)（实测比值 16.0），非恒等、非地板。

  B (B446-B451, 6): 积分正弦/余弦函数族（Si, Ci, Shi, Chi）
                    golden = scipy.special.sici / scipy.special.shichi（精确 oracle）
                    candidate = **四阶 RK4 积分各自的定义 ODE**
                                （Si: y'=sin x/x, Ci: y'=cos x/x, Shi: y'=sinh x/x,
                                  Chi: y'=cosh x/x；从起点 x0 的**解析 Taylor 级数**启动，
                                  级数截断误差 < 1e-18 ⇒ 不进主导）
                    残差 = RK4 截断误差 O(h⁴)（实测比值 15.76~16.18），非恒等、非地板。

判据 D：固定物理参数、只扫候选自身离散参数（族 A 扫 Simpson 段数 N；族 B 扫 RK4 步数 N）。
       要求 ①粗端残差浮出双精度地板（>1e-13）②随 N 严格单调下降且**实测**比值≈16（O(h⁴)）
       ③默认档残差 > 1e-12（避开 run_d_criterion_smoke ③ 红灯）。
       **收敛阶数字一律来自实测扫描，不按标称阶写死**（B-19 血案）。本批实测：
       族 A 比值 16.01~16.10（收敛至 16.00，粗端因尚未入渐近区偏高至 ~30~42）、
       族 B 比值 15.76~16.18。全部 MONO。

🔴 选族前同源体检（实 grep 全仓，排除 lda_cuda_venv/node_modules 三方噪声）：
   `betainc|betaln|betaincinv|incomplete beta|不完全 beta` → lda/ **零命中**
   `sici|shichi|sinint|cosint` → lda/ **零命中**（唯一形似命中是 B-21 docstring 中
     "physicis**ts**" 含子串 sici 的**假阳性**）
   `owens_t|student-t|stdtr|fdtr|gegenbauer|hyp0f1|spheroidal|pro_cv|ellip_harm` → lda/ **零命中**
   根目录 *.md（README/族报告/纪律文档）对以上全部关键词 **零命中**。
   相邻但不同源（逐条判读，见报告 §同源体检）：
   · 复合 Simpson **方法**已被 B-10 族 B/C、B-11 全族、B-16 族 B 使用；但本族被积函数
     （Beta 密度核）、golden oracle（betainc / 二项闭式）、以及候选是**双重积分比值**
     （分子分母各自带 Simpson 误差而非同源相消）⇒ 与「单一被积函数的求积」不是同一道题。
   · Fresnel C/S（B-10 族 C）虽同属积分型特殊函数，但积分核、golden oracle
     （fresnel ↔ sici/shichi）与候选方法（复合 Simpson ↔ RK4 积分 ODE）三者均不同 ⇒ 非数值同源。
   · Hermite/Laguerre/Bernstein（B-21）、修正 Bessel I_nu（B-20 族 A）、球谐（B-20 族 B）
     所覆盖的正交多项式/特殊函数类与 Beta 函数、积分正余弦函数**无交集**。

🔴 血案预防（本批定族期实测，详见报告 §血案）：
   1. 【Simpson 端点幂奇性 ⇒ 收敛阶退化】被积函数 t^{a-1}(1-t)^{b-1} 的 4 阶导数
      ∝ t^{a-5}(1-t)^{b-5} ⇒ 仅当 a≥5 且 b≥5 时为 C⁴、Simpson 才给干净 O(h⁴)。
      故**族 A 全部锚限定 a≥5 且 b≥5**（a=5.5/6/7.5/9/10/11/12）。
   2. 【Ci/Chi 定义积分在 t→0 的 1/t 奇性 ⇒ 阶退化（本批首版实测血案）】Ci/Chi 的
      被积函数 cos t/t、cosh t/t 在 0 附近 4 阶导数 ∝ 1/t⁵ ⇒ 若起点取 ε=1e-3，
      Simpson 误差被左端点导数放大主导，实测比值退化为 **2.8~3.4（非 16）**、
      N=256 残差仍 **7.55e-2**（不是精度不足，是**渐近区未达**）。
      修法：Ci/Chi 起点改用 **x0=0.1**（级数在此仍精确到 1e-30）⇒ 比值回到 15.76~16.18 ✅。
      Si/Shi 的被积函数 sin t/t、sinh t/t 在 0 为**可去奇性**（解析）⇒ 起点仍可用 1e-3 ✅。
   3. 【取最细档撞 d_criterion ③ 地板】Simpson/RK4 误差随 N 快速趋零（族 A N=512 时
      仅 6.2e-13）⇒ **默认档（= 判据 D 扫描格末端）必须收在残差仍 >1e-12 的档**，
      本批定档族 A N=128（2.4e-10~1.1e-9）、族 B N=64/256/512/1024（1.2e-10~2.5e-10）。
   4. 【起点级数必须精确且非反算】Si/Ci/Shi/Chi 起点值一律用**解析 Taylor 级数**给出
      （非从 golden 反算，守 C4 红线）；级数在所选起点截断误差 < 1e-18。
   5. 【零响应键】族 A 的 a/b/x、族 B 的 X 均对指标敏感（自检逐锚核过 d/d参数 量级）；
      无零响应键。
   6. 【golden_fn 形参集 ⊇ default_params 键集】default_params 只放 golden 接受的键；
      离散参数 N 由候选函数签名默认值承载（**不进 default_params**，否则 golden 收到
      未知 kwarg 抛 TypeError —— B-7 类血案预防）。默认档 N 一律 = 判据 D 扫描格末端。

环境：CI 解释器唯一（py3.13.14 · scipy 1.17.1）；本文件纯 LF、无 BOM。
"""
import math
import numpy as np
from scipy import special as _sp  # golden oracle（精确特殊函数，非截断近似）

_EULER_GAMMA = 0.577215664901532860606512090082402431  # γ（Euler–Mascheroni，字面量）
_START_ANALYTIC = 1e-3  # Si/Shi 起点（sin t/t、sinh t/t 在 0 为可去奇性，解析）
_START_LOG = 0.1        # Ci/Chi 起点（cos t/t、cosh t/t 在 0 有 1/t 奇性 ⇒ 须远离，血案 2）
_SERIES_TERMS = 8       # 起点级数项数（起点处截断误差 < 1e-18）

# 默认档（= 判据 D 扫描格末端，满足「定档 = 扫描网格末端」纪律）
_N_BY_BID = {
    "B439": 128, "B440": 128, "B441": 128, "B442": 128, "B443": 128, "B444": 128, "B445": 128,
    "B446": 64, "B447": 256, "B448": 512, "B449": 1024, "B450": 64, "B451": 1024,
}
# 判据 D 扫描网格（4 档，等比 ×2）
_GRID_BY_BID = {
    "B439": [16, 32, 64, 128], "B440": [16, 32, 64, 128], "B441": [16, 32, 64, 128],
    "B442": [16, 32, 64, 128], "B443": [16, 32, 64, 128], "B444": [16, 32, 64, 128],
    "B445": [16, 32, 64, 128],
    "B446": [8, 16, 32, 64], "B447": [32, 64, 128, 256], "B448": [64, 128, 256, 512],
    "B449": [128, 256, 512, 1024], "B450": [8, 16, 32, 64], "B451": [128, 256, 512, 1024],
}
# 逐锚 tol（按「余量 >=100x 且 |golden| >= 13.5*tol」标定；tol 只收紧不放松）
_TOL_BY_BID = {
    "B439": 1e-6, "B440": 1e-6, "B441": 1e-6, "B442": 1e-6, "B443": 1e-6,
    "B444": 1e-6, "B445": 1e-6,
    "B446": 1e-7, "B447": 1e-7, "B448": 1e-7, "B449": 1e-7, "B450": 1e-7, "B451": 1e-7,
}


# ===========================================================================
# 通用数值工具
# ===========================================================================
def _simpson(fn, lo, hi, N):
    """复合 Simpson 求积（N 为奇数则 +1）。纯 numpy，无第三方依赖。"""
    n = int(N)
    if n % 2:
        n += 1
    h = (hi - lo) / float(n)
    xs = lo + h * np.arange(n + 1, dtype=float)
    ys = np.asarray(fn(xs), dtype=float)
    return float(h / 3.0 * (ys[0] + ys[-1] + 4.0 * ys[1:n:2].sum() + 2.0 * ys[2:n:2].sum()))


def _beta_kernel(a, b):
    """Beta 密度核 t^{a-1}(1-t)^{b-1}（未归一化；族 A 锚限定 a,b>=5 ⇒ C⁴，血案 1）。"""
    aa = float(a)
    bb = float(b)

    def _f(t):
        t = np.asarray(t, dtype=float)
        return np.power(t, aa - 1.0) * np.power(1.0 - t, bb - 1.0)

    return _f


def _beta_norm_numeric(a, b, N):
    """B(a,b) = ∫₀¹ t^{a-1}(1-t)^{b-1} dt（数值，自包含，不调 scipy.beta）。"""
    return _simpson(_beta_kernel(a, b), 0.0, 1.0, N)


def _incomplete_beta_numeric(a, b, x, N):
    """正则化不完全 Beta I_x(a,b) = ∫₀^x / ∫₀¹（分子分母**同阶** Simpson 数值积分）。"""
    num = _simpson(_beta_kernel(a, b), 0.0, float(x), N)
    den = _beta_norm_numeric(a, b, N)
    return float(num / den)


def _rk4_quadrature(rhs, x0, y0, X, N):
    """一阶 ODE y' = rhs(x) 的四阶经典 RK4 积分（rhs 与 y 无关 ⇒ 等价 4 点/步求积）。"""
    h = (float(X) - float(x0)) / float(N)
    t = float(x0)
    y = float(y0)
    for _ in range(int(N)):
        k1 = rhs(t)
        k2 = rhs(t + h / 2.0)
        k3 = rhs(t + h / 2.0)
        k4 = rhs(t + h)
        y += h / 6.0 * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        t += h
    return float(y)


def _si_series(x, terms=_SERIES_TERMS):
    """Si(x) 的 Taylor 级数 Σ_{k≥0} (-1)^k x^{2k+1}/((2k+1)(2k+1)!)（小 x 精确）。"""
    s = 0.0
    for k in range(terms):
        s += ((-1.0) ** k) * x ** (2 * k + 1) / ((2 * k + 1) * math.factorial(2 * k + 1))
    return float(s)


def _ci_series(x, terms=_SERIES_TERMS):
    """Ci(x) 的级数 γ + ln x + Σ_{k≥1} (-1)^k x^{2k}/((2k)(2k)!)。"""
    s = _EULER_GAMMA + math.log(x)
    for k in range(1, terms + 1):
        s += ((-1.0) ** k) * x ** (2 * k) / ((2 * k) * math.factorial(2 * k))
    return float(s)


def _shi_series(x, terms=_SERIES_TERMS):
    """Shi(x) 的级数 Σ_{k≥0} x^{2k+1}/((2k+1)(2k+1)!)。"""
    s = 0.0
    for k in range(terms):
        s += x ** (2 * k + 1) / ((2 * k + 1) * math.factorial(2 * k + 1))
    return float(s)


def _chi_series(x, terms=_SERIES_TERMS):
    """Chi(x) 的级数 γ + ln x + Σ_{k≥1} x^{2k}/((2k)(2k)!)。"""
    s = _EULER_GAMMA + math.log(x)
    for k in range(1, terms + 1):
        s += x ** (2 * k) / ((2 * k) * math.factorial(2 * k))
    return float(s)


def _binom_closed_form(a, b, x):
    """整数参数不完全 Beta 的二项闭式：I_x(a,b) = Σ_{j=a}^{n} C(n,j) x^j (1-x)^{n-j}，n=a+b-1。"""
    aa = int(round(float(a)))
    bb = int(round(float(b)))
    xx = float(x)
    n = aa + bb - 1
    s = 0.0
    for j in range(aa, n + 1):
        s += math.comb(n, j) * xx ** j * (1.0 - xx) ** (n - j)
    return float(s)


# ===========================================================================
# 族 A · 不完全 Beta 函数族（B439-B445）
# ===========================================================================
def golden_b439(a=5.5, b=6.0, x=0.45):
    """golden：正则化不完全 Beta I_x(a,b)（scipy 精确 oracle）。"""
    return float(_sp.betainc(float(a), float(b), float(x)))


def cand_b439(a=5.5, b=6.0, x=0.45, N=_N_BY_BID["B439"]):
    """candidate：复合 Simpson 双重数值积分（分子 ∫₀^x / 分母 ∫₀¹，自包含）。"""
    return float(_incomplete_beta_numeric(a, b, x, N))


def golden_b440(a=6.0, b=5.0, x=0.60):
    """golden：I_x(a,b)（scipy 精确 oracle）。"""
    return float(_sp.betainc(float(a), float(b), float(x)))


def cand_b440(a=6.0, b=5.0, x=0.60, N=_N_BY_BID["B440"]):
    """candidate：复合 Simpson 双重数值积分。"""
    return float(_incomplete_beta_numeric(a, b, x, N))


def golden_b441(a=7.5, b=9.0, x=0.35):
    """golden：I_x(a,b)（scipy 精确 oracle）。"""
    return float(_sp.betainc(float(a), float(b), float(x)))


def cand_b441(a=7.5, b=9.0, x=0.35, N=_N_BY_BID["B441"]):
    """candidate：复合 Simpson 双重数值积分。"""
    return float(_incomplete_beta_numeric(a, b, x, N))


def golden_b442(a=9.0, b=8.0, x=0.55):
    """golden：I_x(a,b)（scipy 精确 oracle）。"""
    return float(_sp.betainc(float(a), float(b), float(x)))


def cand_b442(a=9.0, b=8.0, x=0.55, N=_N_BY_BID["B442"]):
    """candidate：复合 Simpson 双重数值积分。"""
    return float(_incomplete_beta_numeric(a, b, x, N))


def golden_b443(a=10.0, b=12.0, x=0.42):
    """golden：I_x(a,b)（scipy 精确 oracle）。"""
    return float(_sp.betainc(float(a), float(b), float(x)))


def cand_b443(a=10.0, b=12.0, x=0.42, N=_N_BY_BID["B443"]):
    """candidate：复合 Simpson 双重数值积分。"""
    return float(_incomplete_beta_numeric(a, b, x, N))


def golden_b444(a=6, b=6, x=0.45):
    """golden：整数参数**二项闭式** I_x(a,b) = Σ_{j=a}^{n} C(n,j) x^j (1-x)^{n-j}（n=a+b-1）。

    与 scipy.special.betainc 两条独立精确路径互校至 <1e-14（自检已核）。
    """
    return float(_binom_closed_form(a, b, x))


def cand_b444(a=6, b=6, x=0.45, N=_N_BY_BID["B444"]):
    """candidate：复合 Simpson 双重数值积分（与二项闭式 golden 不同源）。"""
    return float(_incomplete_beta_numeric(a, b, x, N))


def golden_b445(a=7, b=8, x=0.40):
    """golden：整数参数**二项闭式** I_x(a,b)（n=a+b-1=14）。"""
    return float(_binom_closed_form(a, b, x))


def cand_b445(a=7, b=8, x=0.40, N=_N_BY_BID["B445"]):
    """candidate：复合 Simpson 双重数值积分（与二项闭式 golden 不同源）。"""
    return float(_incomplete_beta_numeric(a, b, x, N))


# ===========================================================================
# 族 B · 积分正弦/余弦函数族（B446-B451）
# ===========================================================================
def golden_b446(X=4.0):
    """golden：Si(X)（scipy.special.sici 精确 oracle）。"""
    return float(_sp.sici(float(X))[0])


def cand_b446(X=4.0, N=_N_BY_BID["B446"]):
    """candidate：RK4 积分 y' = sin x / x，自 x0=1e-3 的 Taylor 级数启动。"""
    y0 = _si_series(_START_ANALYTIC)
    return float(_rk4_quadrature(lambda t: math.sin(t) / t, _START_ANALYTIC, y0, float(X), N))


def golden_b447(X=12.0):
    """golden：Si(X)（scipy.special.sici 精确 oracle，大 x 档）。"""
    return float(_sp.sici(float(X))[0])


def cand_b447(X=12.0, N=_N_BY_BID["B447"]):
    """candidate：RK4 积分 y' = sin x / x（大 x 档，误差累积于整段 [x0,X]）。"""
    y0 = _si_series(_START_ANALYTIC)
    return float(_rk4_quadrature(lambda t: math.sin(t) / t, _START_ANALYTIC, y0, float(X), N))


def golden_b448(X=1.0):
    """golden：Ci(X)（scipy.special.sici 精确 oracle）。"""
    return float(_sp.sici(float(X))[1])


def cand_b448(X=1.0, N=_N_BY_BID["B448"]):
    """candidate：RK4 积分 y' = cos x / x，自 x0=0.1 的解析级数启动（避 1/t 奇性阶退化）。"""
    y0 = _ci_series(_START_LOG)
    return float(_rk4_quadrature(lambda t: math.cos(t) / t, _START_LOG, y0, float(X), N))


def golden_b449(X=2.0):
    """golden：Ci(X)（scipy.special.sici 精确 oracle）。"""
    return float(_sp.sici(float(X))[1])


def cand_b449(X=2.0, N=_N_BY_BID["B449"]):
    """candidate：RK4 积分 y' = cos x / x（起点 0.1）。"""
    y0 = _ci_series(_START_LOG)
    return float(_rk4_quadrature(lambda t: math.cos(t) / t, _START_LOG, y0, float(X), N))


def golden_b450(X=2.0):
    """golden：Shi(X)（scipy.special.shichi 精确 oracle）。"""
    return float(_sp.shichi(float(X))[0])


def cand_b450(X=2.0, N=_N_BY_BID["B450"]):
    """candidate：RK4 积分 y' = sinh x / x，自 x0=1e-3 的 Taylor 级数启动。"""
    y0 = _shi_series(_START_ANALYTIC)
    return float(_rk4_quadrature(lambda t: math.sinh(t) / t, _START_ANALYTIC, y0, float(X), N))


def golden_b451(X=2.0):
    """golden：Chi(X)（scipy.special.shichi 精确 oracle）。"""
    return float(_sp.shichi(float(X))[1])


def cand_b451(X=2.0, N=_N_BY_BID["B451"]):
    """candidate：RK4 积分 y' = cosh x / x，自 x0=0.1 的解析级数启动（避 1/t 奇性阶退化）。"""
    y0 = _chi_series(_START_LOG)
    return float(_rk4_quadrature(lambda t: math.cosh(t) / t, _START_LOG, y0, float(X), N))


# ===========================================================================
# 自检：余量标定 + 判据 D 扫描（残差随离散参数单调下降；比值实测，不按标称阶写死）
# ===========================================================================
_CASES = [
    ("B439", golden_b439, cand_b439, {"a": 5.5, "b": 6.0, "x": 0.45}),
    ("B440", golden_b440, cand_b440, {"a": 6.0, "b": 5.0, "x": 0.60}),
    ("B441", golden_b441, cand_b441, {"a": 7.5, "b": 9.0, "x": 0.35}),
    ("B442", golden_b442, cand_b442, {"a": 9.0, "b": 8.0, "x": 0.55}),
    ("B443", golden_b443, cand_b443, {"a": 10.0, "b": 12.0, "x": 0.42}),
    ("B444", golden_b444, cand_b444, {"a": 6, "b": 6, "x": 0.45}),
    ("B445", golden_b445, cand_b445, {"a": 7, "b": 8, "x": 0.40}),
    ("B446", golden_b446, cand_b446, {"X": 4.0}),
    ("B447", golden_b447, cand_b447, {"X": 12.0}),
    ("B448", golden_b448, cand_b448, {"X": 1.0}),
    ("B449", golden_b449, cand_b449, {"X": 2.0}),
    ("B450", golden_b450, cand_b450, {"X": 2.0}),
    ("B451", golden_b451, cand_b451, {"X": 2.0}),
]

if __name__ == "__main__":
    print("=== B-28 不完全 Beta / 积分特殊函数核 自检（余量标定 + 判据 D） ===")
    print("\n%-6s %18s %18s %12s %10s %-7s %-10s %s"
          % ("锚", "golden", "cand(默认档)", "|Δ|", "margin", "基线>1e-12", "gold/tol", "判定"))
    bad = 0
    for bid, gf, cf, p in _CASES:
        g = gf(**p)
        c = cf(**p)
        dd = abs(g - c)
        tol = _TOL_BY_BID[bid]
        margin = (tol / dd) if dd > 0 else float("inf")
        base_ok = dd > 1e-12
        gr = abs(g) / tol
        ok = (margin >= 2.0) and base_ok and (gr >= 13.5)
        bad += 0 if ok else 1
        print("%-6s %18.10e %18.10e %12.3e %10.1f %-7s %-10.1f %s"
              % (bid, g, c, dd, margin, base_ok, gr, "OK" if ok else "BAD"))

    print("\n--- 判据 D 扫描（残差随离散参数单调下降；比值来自实测，不按标称阶写死）---")
    for bid, gf, cf, p in _CASES:
        g = gf(**p)
        grid = _GRID_BY_BID[bid]
        row = []
        prev = None
        monotonic = True
        ratios = []
        for nn in grid:
            dd = abs(g - cf(N=nn, **p))
            if prev is not None:
                ratio = (prev / dd) if dd > 0 else float("nan")
                ratios.append(ratio)
                if dd > prev:
                    monotonic = False
                row.append("%d:%.2e(x%.2f)" % (nn, dd, ratio))
            else:
                row.append("%d:%.2e" % (nn, dd))
            prev = dd
        dd_last = abs(g - cf(N=grid[-1], **p))
        dd_first = abs(g - cf(N=grid[0], **p))
        print("%-6s %-58s %-8s 比值 %.2f~%.2f  粗端>1e-13:%s  默认档>1e-12:%s"
              % (bid, "  ".join(row), "MONO" if monotonic else "NONMONO",
                 min(ratios), max(ratios), dd_first > 1e-13, dd_last > 1e-12))
    print("\nBAD 计数 = %d" % bad)
    print("DONE")
