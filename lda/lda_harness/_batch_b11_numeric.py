# -*- coding: utf-8 -*-
"""LDA · Batch B-11 双方法独立锚数值核（v0.9.91 · 腿① 续加锚稀释 terminal）

四族 16 道（B185-B200）。每族均为**新方程类 / 新特殊函数类 / 新物理域**，
开工前已过「同源体检」（2026-09-17 本批**实际 grep 全仓**占用扫描，非凭记忆）：

  A. 量子统计积分与 ζ 函数（玻色/费米/声子）            B185-B188（4 道）
       golden : 闭式 Γ(s)ζ(s)（π⁴/15、2ζ(3)、(3/2)ζ(3)、4π⁴/15）
       cand   : x→t=x/(1+x) 换元把 ∫₀^∞ 归约为 [0,1] 上的复合 Simpson（纯离散化误差）
  B. 经典二体轨道（Kepler 定律，中心力 ODE）           B189-B192（4 道）
       golden : 初等闭式（T=2π√(a³/μ)、L=√(μa(1−e²))、v_p=√(μ(2/r_p−1/a))）
       cand   : 中心力轨道 ODE 的 RK4 时间积分（观测由数值轨迹导出）
  C. 辐射传热角系数（view factor，辐射换热积分）        B193-B196（4 道）
       golden : 解析闭式（平行等尺寸矩形 / 垂直共边矩形）
       cand   : 4D 张量积复合 Simpson 直接求积 F₁₂=(1/A₁)∫∫cosθ₁cosθ₂/(πR²)dA₂dA₁
  D. Voigt 谱线轮廓（多普勒 ⊗ 洛伦兹，Faddeeva 特殊函数） B197-B200（4 道）
       golden : scipy.special.voigt_profile（wofz/Faddeeva 机器精度）
       cand   : 卷积定义式的复合 Simpson（Gaussian ⊗ Lorentzian）

======================================================================
同源体检记录（三条红线逐条核）
----------------------------------------------------------------------
① 数值同源 —— 既有 202 道锚已占用的特殊函数（**grep 全仓实测**）：
   `ai_zeros`（B-6 三角阱）、`jv/yv`（B-8）、`spherical_jn/yn`（mie_solver）、
   `ellipe/ellipk/fresnel/mathieu_a/mathieu_b`（B-10）、实自变量 `erfc`（B30 读出保真度链）。
   ⇒ 本批**避开 Airy / Bessel / 球 Bessel / Legendre(关联) / Mathieu / 椭圆积分 / Fresnel / erfc**。
   本批新用 `scipy.special.zeta` / `scipy.special.voigt_profile` —— 全仓 grep **No matches**（新特殊函数类）。
② 结构同源 —— 已占用的方程/数值方法类（grep 实测）：
   本征值问题（B-5/B-6/B-7/B-9/B-10 族 A）、时间推进抛物型（B-10 族 D）、
   稳态边值 ODE 三对角 FDM（**B29 散热鳍 cosh**）、1D 波动方程本征（TL 波导，verification_adapters）、
   2D/3D 拉普拉斯本征 Kronecker（B-6/B-7）、Numerov 散射（B49）、
   EM FDTD `leapfrog`（lda_solver/fdtd*）、FFT 拍频（B14）、Bragg/Bloch（B15/B35/B64）。
   ⇒ 本批四类**均未被占用**：
     A = 量子统计积分（**无势函数、无本征值、无时间推进**，纯无穷区间求积）
     B = 中心力轨道 ODE 时间积分（**不含网格离散化的本征值/边值**；与 fdtd leapfrog 的 Maxwell
         时间步进不同方程；与 B-10 族 D 扩散（抛物型、耗散）不同——本族为哈密顿保守系统，
         观测为轨道要素 T/L/v_p 而非浓度剖面）
     C = 辐射换热角系数（**新物理域**：辐射传热，项目全仓 grep「角系数/view factor/辐射传热」零命中）
     D = Voigt 谱线（**新特殊函数类**；与 B30 的**实自变量** erfc 不同函数、不同物理量——
         Voigt 是复自变量 Faddeeva/wofz 的卷积结果，物理为**光谱线型**而非读出保真度）
③ golden 不是近似式 —— A 为 Γ(s)ζ(s) 严格闭式；B 为 Kepler 解析解；C 为精确解析积分结果；
   D 为 scipy 机器精度特殊函数。**本批 golden 无一是截断级数/微扰展开/经验拟合**。

被否候选（记入报告 §2）：
   · Airy 函数/三角势阱（数值同源 B-6）
   · 关联 Legendre（数值同源 B-6 刚性转子）
   · 1D 波动方程 leapfrog（结构同源 fdtd1d/传输线求解器）
   · 1D 稳态传导边值 + 三对角 FDM（结构同源 B29 散热鳍）
   · 光栅/单缝衍射 FFT（结构同源 B14/B15）
   · Kelvin 函数 ber/bei（结构同源 Bessel 族——ber/bei ≡ J 的复自变量）
   · 开普勒方程数值求根（收敛到机器精度 ⇒ 判据 D 撞「代数恒等」红线）

血案规避（写进代码注释，源自 B-6/B-8/B-9/B-10 血案表）：
   1. 无穷区间**必须换元归约到有限区间**再求积——直接截断 ∫₀^∞ 会把「截断误差」混进残差
      且不随 n 收敛（B-10 血案 4 的近亲）。本批族 A 用 t=x/(1+x)（两端 integrand→0）。
   2. 换元后 integrand 在 x→0 处 x^{s-1} ⇒ s≥3 时端点严格为 0（**无端点奇性**）；
      s 选择使 x^{s-2}→0。
   3. 采样**禁用格点吸附**（B-10 血案 3）：族 B 的周期/近心点用**三次 Hermite 插值**定位穿越
      （线性插值仅 O(h²) 且实测非单调——B192 血案：残差链 7.4e-10→5.6e-9 反弹）。
   4. 族 B 的观测取**固定绝对时刻**或**守恒量**，**绝不用 golden 反推的时刻**（C4 红线）。
   5. 判据 D **必须扫候选自身离散参数**（族 A/C/D 扫 n；族 B 扫 dt），且参数窗口须落在
      **离散误差主导区**（B-10 血案 2「超收敛 round-off 地板」）——本批全部先扫窗再定档。
   6. 4D 张量积求积内存 (n+1)⁴：n=16→83521、n=32→1.19M，安全；但族 C 垂直共边需 n≥64，
      n≥96 时整块数组达 ~700MB–2.2GB（**内存墙**）⇒ 改为**按 x 分块累加**（每片 (n+1)³，7MB）。
   7. 族 C 垂直共边被积函数在**共边角点**（x=z=0, y₁=y₂）按 ~xz/(πR⁴) 发散 ⇒ 4D 均匀 Simpson
      仅 **O(n⁻¹)** 收敛（n=64 残差 2.7e-3，余量 3.7×；n=96 → 1.8e-3，余量 5.6×）。**这是本族的
      固有性质**（非缺陷）：慢收敛恰是「真数值方法、非代数恒等」的正面证据，不许靠放 tol 掩盖。
   8. 默认定档须避开**噪声地板**（B-10 血案 2 的近亲）：
      · B192（a=2 ⇒ T≈17.77，绝对时刻大 ⇒ 穿越时刻 round-off 地板抬到 ~2e-13）：
        原定 dt=0.002 残差 2.13e-13 **正落地板** ⇒ 改 **dt=0.008**（残差 8.78e-12，地板以上 ~44×）。
      · B199（σ<γ 极光滑）原定 n=64 残差 **2.78e-17 落地板** ⇒ 改 **n=32**（残差 1.23e-9）。
      · 族 C 垂直共边 n≥64；族 D B198 n≥24（n≤20 时高斯峰欠采样 ⇒ 残差链抖动，非单调）。
   9. **积分窗不足 ⇒ 参数扰动下候选直接崩**：族 B 原 `_T_MAX=30.0` 恰好只够 a=2
      的 1.5 个周期（T≈17.77 ⇒ 近心点穿越 @8.9/26.7）。反向测试按 C5 把 a×1.1
      ⇒ T≈28.9、1.5 周期 = 43.4 > 30 ⇒ 穿越不足 2 次 ⇒ `_orbit_period` 抛
      RuntimeError（候选在扰动下「崩」而非「FAIL」——同样不合格）。改 `_T_MAX=90.0`（覆盖 a≤4.4）。
  10. **零响应键（“假参数”）**：① 周期锨（B189/B192）的 e 与 T 无关（Kepler 第三定律）
      ⇒ e×1.1 信号恒 0；② 线心锨（B197/B199）x≡0 ⇒ x×1.1 恒为 0。处置 = 从
      `default_params` 撤出这些键（它们仍作 golden/候选的形参默认值）。
  11. **逐锚 tol 收紧 + 基线残差避开 1e-12 地板**：族 C/D 指标动态范围小
      （~0.07–0.29），绝对 tol=0.01 会掩没 10% 扰动信号 ⇒ 逐锚收紧至 0.001–0.005（见
      `_TOL_BY_BID`）；且 `run_d_criterion_smoke` ③ 断言「基线残差 > 1e-12」⇒ B197
      原 n=64 残差 1.68e-13 会新踩红灯 ⇒ 定档降到 n=48（残差 1.26e-10）。

球极限/极限自检：族 A 见 `_self_test` 的恒等式自检；族 B 见圆轨道极限（e=0）与面积速率守恒；
族 C 见**互易性 F₁₂A₁=F₂₁A₂** 与已知文献值（平行 1×1@1 ≈ 0.1998、垂直共边 1×1 ≈ 0.2000）；
族 D 见 γ→0 高斯极限与 σ→0 洛伦兹极限。
"""
from __future__ import annotations

import math

import numpy as np
from scipy.special import voigt_profile as _voigt_profile
from scipy.special import zeta as _rzeta

PI = math.pi

# ======================================================================
# 通用：复合 Simpson（n 必须偶数）
# ======================================================================


def _simpson(f, a, b, n):
    """复合 Simpson 求积（区间 [a,b]，n 等分；n 自动取偶）。"""
    n = int(n)
    if n % 2:
        n += 1
    x = np.linspace(a, b, n + 1)
    y = np.asarray(f(x), dtype=float)
    h = (b - a) / float(n)
    return h / 3.0 * (y[0] + y[-1] + 4.0 * y[1:-1:2].sum() + 2.0 * y[2:-2:2].sum())


def _w_simpson(n):
    """1D 复合 Simpson 权重向量（n+1 项，n 偶）。"""
    n = int(n)
    w = np.ones(n + 1)
    w[1:-1:2] = 4.0
    w[2:-1:2] = 2.0
    return w


# ======================================================================
# 族 A · 量子统计积分与 ζ 函数（B185-B188）
# ======================================================================
# 物理背景（均为量子统计/固体物理的经典积分，量纲已归一）：
#   B185  I = ∫₀^∞ x³/(e^x−1) dx = π⁴/15        —— 黑体辐射能量密度系数（Stefan–Boltzmann，
#          u = 8π⁵k⁴/(15h³c³)·T⁴ = 4σT⁴/c，系数即本积分/π² 组合）
#   B186  I = ∫₀^∞ x²/(e^x−1) dx = 2ζ(3)        —— 黑体光子数密度系数（n_ph ∝ ζ(3)·T³）
#   B187  I = ∫₀^∞ x²/(e^x+1) dx = (3/2)ζ(3)    —— 费米气体低温 T² 比热系数（Sommerfeld 展开）
#   B188  I = ∫₀^∞ x⁴e^x/(e^x−1)² dx = 4π⁴/15   —— 德拜固体低温 T³ 热容系数
#     （∫₀^∞ x^{s-1}e^x/(e^x−1)²dx = Γ(s)ζ(s−1)，s=5 ⇒ Γ(5)ζ(4) = 24·π⁴/90 = 4π⁴/15）
# 换元：t = x/(1+x) ⇔ x = t/(1−t)，dx = dt/(1−t)²，把 ∫₀^∞ 归约为 ∫₀¹。
# 数值稳定：一律用 exp(−x) 写法，避免 exp(x) 溢出。


def _f_bose(x, s):
    """x^{s-1}/(e^x − 1)（玻色分布，数值稳定写法）。"""
    x = np.asarray(x, dtype=float)
    out = np.zeros_like(x)
    m = x > 1e-12
    xx = x[m]
    ex = np.exp(-xx)
    out[m] = xx ** (s - 1.0) * ex / (1.0 - ex)
    return out


def _f_fermi(x, s):
    """x^{s-1}/(e^x + 1)（费米分布，数值稳定写法）。"""
    x = np.asarray(x, dtype=float)
    out = np.zeros_like(x)
    m = x > 1e-12
    xx = x[m]
    ex = np.exp(-xx)
    out[m] = xx ** (s - 1.0) * ex / (1.0 + ex)
    return out


def _f_debye(x, s):
    """x^{s-1}·e^x/(e^x − 1)²（德拜热容被积，数值稳定写法）。"""
    x = np.asarray(x, dtype=float)
    out = np.zeros_like(x)
    m = x > 1e-12
    xx = x[m]
    ex = np.exp(-xx)
    out[m] = xx ** (s - 1.0) * ex / (1.0 - ex) ** 2
    return out


def _reduce_01(F, s, t):
    """把 ∫₀^∞ F(x,s)dx 的 integrand 搬到 t∈[0,1]（x=t/(1−t)）。"""
    t = np.asarray(t, dtype=float)
    t = np.clip(t, 1e-15, 1.0 - 1e-15)
    x = t / (1.0 - t)
    return F(x, s) / (1.0 - t) ** 2


def _bose_moment(s, n):
    """候选：∫₀^∞ x^{s-1}/(e^x−1)dx（换元 + 复合 Simpson）。"""
    return float(_simpson(lambda t: _reduce_01(_f_bose, s, t), 0.0, 1.0, n))


def _fermi_moment(s, n):
    """候选：∫₀^∞ x^{s-1}/(e^x+1)dx（换元 + 复合 Simpson）。"""
    return float(_simpson(lambda t: _reduce_01(_f_fermi, s, t), 0.0, 1.0, n))


def _debye_moment(s, n):
    """候选：∫₀^∞ x^{s-1}e^x/(e^x−1)²dx（换元 + 复合 Simpson）。"""
    return float(_simpson(lambda t: _reduce_01(_f_debye, s, t), 0.0, 1.0, n))


def golden_b185(s: float = 4.0) -> float:
    """玻色矩 ∫₀^∞ x^{s−1}/(e^x−1)dx = Γ(s)ζ(s)（s=4 ⇒ π⁴/15 黑体能量密度）。"""
    return float(math.gamma(s) * _rzeta(s))


def golden_b186(s: float = 3.0) -> float:
    """玻色矩 ∫₀^∞ x^{s−1}/(e^x−1)dx = Γ(s)ζ(s)（s=3 ⇒ 2ζ(3) 光子数密度）。"""
    return float(math.gamma(s) * _rzeta(s))


def golden_b187(s: float = 3.0) -> float:
    """费米矩 ∫₀^∞ x^{s−1}/(e^x+1)dx = (1−2^{1−s})Γ(s)ζ(s)（s=3 ⇒ (3/2)ζ(3)）。"""
    return float((1.0 - 2.0 ** (1.0 - s)) * math.gamma(s) * _rzeta(s))


def golden_b188(s: float = 5.0) -> float:
    """德拜矩 ∫₀^∞ x^{s−1}e^x/(e^x−1)²dx = Γ(s)ζ(s−1)（s=5 ⇒ 4π⁴/15）。"""
    return float(math.gamma(s) * _rzeta(s - 1.0))


# ======================================================================
# 族 B · 经典二体轨道（Kepler 定律，B189-B192）
# ======================================================================
# μ = GM = 1（归一）。中心力 ODE：r'' = −μ r/|r|³。
# 初值取远心点（在 Kepler 椭圆上，非 golden 反算）：
#   r_apo = a(1+e)、v_apo = √(μ(1−e)/(a(1+e)))（纯切向）。
# 观测（全部由**数值轨迹**导出）：
#   ① 周期 T：近心点（y 由负穿正）连续两次穿越的时刻差
#   ② 近心点距离 r_p = min|r|（Hermite 插值定位于穿越时刻）
#   ③ 近心点速率 v_p：近心点穿越时刻的 |v|（Hermite 插值）
# golden：T = 2π√(a³/μ)、r_p = a(1−e)、v_p = √(μ(2/r_p − 1/a))。
# 🔴 B190 血案：初版用「角动量 L」作观测 ⇒ 守恒量在 RK4 下几乎精确 ⇒ 残差 1.5e-12 直落
#    机器精度地板（1e-15），与自证桩 |Δ|≡0 不可区分 ⇒ 判据 D 红。改 **r_p**（穿越插值量，可标定）。

_MU = 1.0
_T_MAX = 90.0          # 积分窗口（绝对，纯数值界，不用 golden 推导）
#   🔴 B-11 血案 9：原 30.0 恰好只够 a=2 的 1.5 个周期（T≈17.77 ⇒ 2 次近心点穿越 @8.9/26.7）。
#   反向测试按 C5 把物理参数 ×1.1（a→2.2 ⇒ T≈28.9，1.5 周期 = 43.4 > 30）⇒ 穿越不足 2 次 ⇒
#   `_orbit_period` 抛 RuntimeError（候选在扰动下「崩」而非「FAIL」）。改 90.0 覆盖 a ≤ 4.4。


def _kepler_rhs(s):
    x, y, vx, vy = s
    r2 = x * x + y * y
    r3 = r2 * math.sqrt(r2)
    return np.array([vx, vy, -_MU * x / r3, -_MU * y / r3], dtype=float)


def _kepler_orbit(a, ecc, dt):
    """从远心点出发的 RK4 轨道积分，返回 (t, x, y, vx, vy) 数组。"""
    r_apo = a * (1.0 + ecc)
    v_apo = math.sqrt(_MU * (1.0 - ecc) / (a * (1.0 + ecc)))
    s = np.array([r_apo, 0.0, 0.0, -v_apo], dtype=float)
    n_steps = int(math.ceil(_T_MAX / dt))
    T = np.empty(n_steps + 1)
    S = np.empty((n_steps + 1, 4))
    T[0] = 0.0
    S[0] = s
    for i in range(n_steps):
        k1 = _kepler_rhs(s)
        k2 = _kepler_rhs(s + 0.5 * dt * k1)
        k3 = _kepler_rhs(s + 0.5 * dt * k2)
        k4 = _kepler_rhs(s + dt * k3)
        s = s + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        T[i + 1] = (i + 1) * dt
        S[i + 1] = s
    return T, S


def _hermite_eval(t0, y0, v0, t1, y1, v1, t):
    """三次 Hermite 插值在 t∈[t0,t1] 处取值（O(h⁴) 精度）。"""
    h = t1 - t0
    if h == 0.0:
        return y0
    s = (t - t0) / h
    s2 = s * s
    s3 = s2 * s
    h00 = 2.0 * s3 - 3.0 * s2 + 1.0
    h10 = s3 - 2.0 * s2 + s
    h01 = -2.0 * s3 + 3.0 * s2
    h11 = s3 - s2
    return y0 * h00 + h * v0 * h10 + y1 * h01 + h * v1 * h11


def _hermite_cross(t0, y0, v0, t1, y1, v1):
    """[t0,t1] 内 y=0 的根（三次 Hermite + 二分，O(h⁴) 精度；🔴 禁格点吸附，B-10 血案 3）。"""
    h = t1 - t0
    if h <= 0.0:
        return t0

    def H(s):
        s2 = s * s
        s3 = s2 * s
        h00 = 2.0 * s3 - 3.0 * s2 + 1.0
        h10 = s3 - 2.0 * s2 + s
        h01 = -2.0 * s3 + 3.0 * s2
        h11 = s3 - s2
        return y0 * h00 + h * v0 * h10 + y1 * h01 + h * v1 * h11

    flo = H(0.0)
    fhi = H(1.0)
    if flo == 0.0:
        return t0
    if fhi == 0.0:
        return t1
    if flo * fhi > 0.0:
        # 退化（Hermite 在区间内未变号）：退回线性插值
        return t0 + (-y0 / (y1 - y0)) * h if y1 != y0 else t0
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        fm = H(mid)
        if flo * fm <= 0.0:
            fhi = fm
            hi = mid
        else:
            flo = fm
            lo = mid
    return t0 + 0.5 * (lo + hi) * h


def _peri_times(T, S):
    """近心点穿越时刻（y 由负穿正），三次 Hermite 定位（O(h⁴)；禁格点吸附）。"""
    y = S[:, 1]
    vy = S[:, 3]
    idx = np.where((y[:-1] < 0.0) & (y[1:] >= 0.0))[0]
    return [_hermite_cross(T[i], y[i], vy[i], T[i + 1], y[i + 1], vy[i + 1]) for i in idx]


def _peri_index(T, t0):
    """由穿越时刻 t0 反查其所在区间下标 k（t0∈[T[k],T[k+1]]）。"""
    k = int(math.floor(t0 / (T[1] - T[0])))
    return min(max(k, 0), len(T) - 2)


def _orbit_period(a, ecc, dt):
    """候选：数值轨道周期 T（近心点-近心点）。"""
    T, S = _kepler_orbit(a, ecc, dt)
    tc = _peri_times(T, S)
    if len(tc) < 2:
        raise RuntimeError("积分窗内近心点穿越不足 2 次（加长 _T_MAX 或减小 dt）")
    return float(tc[1] - tc[0])


def _orbit_r_peri(a, ecc, dt):
    """候选：数值轨迹的近心点距离 r_p = min|r|（Hermite 插值定位于穿越时刻）。"""
    T, S = _kepler_orbit(a, ecc, dt)
    tc = _peri_times(T, S)
    if not tc:
        raise RuntimeError("积分窗内无近心点穿越")
    t0 = tc[0]
    k = _peri_index(T, t0)
    xs = _hermite_eval(T[k], S[k, 0], S[k, 2], T[k + 1], S[k + 1, 0], S[k + 1, 2], t0)
    ys = _hermite_eval(T[k], S[k, 1], S[k, 3], T[k + 1], S[k + 1, 1], S[k + 1, 3], t0)
    return float(math.hypot(xs, ys))


def _orbit_v_peri(a, ecc, dt):
    """候选：数值轨迹在近心点时刻的速率 |v|（Hermite 插值定位）。"""
    T, S = _kepler_orbit(a, ecc, dt)
    tc = _peri_times(T, S)
    if not tc:
        raise RuntimeError("积分窗内无近心点穿越")
    t0 = tc[0]
    k = _peri_index(T, t0)
    vx = _hermite_eval(T[k], S[k, 2], _kepler_rhs(S[k])[2], T[k + 1], S[k + 1, 2],
                       _kepler_rhs(S[k + 1])[2], t0)
    vy = _hermite_eval(T[k], S[k, 3], _kepler_rhs(S[k])[3], T[k + 1], S[k + 1, 3],
                       _kepler_rhs(S[k + 1])[3], t0)
    return float(math.hypot(vx, vy))


def golden_b189(a: float = 1.0, ecc: float = 0.6) -> float:
    """Kepler 轨道周期 T = 2π√(a³/μ)（a=1.0, e=0.6）。"""
    return float(2.0 * PI * math.sqrt(a ** 3 / _MU))


def golden_b190(a: float = 1.0, ecc: float = 0.6) -> float:
    """Kepler 近心点距离 r_p = a(1−e)（a=1.0, e=0.6）。"""
    return float(a * (1.0 - ecc))


def golden_b191(a: float = 1.0, ecc: float = 0.6) -> float:
    """Kepler 近心点速率 v_p = √(μ(2/r_p − 1/a))（a=1.0, e=0.6）。"""
    rp = a * (1.0 - ecc)
    return float(math.sqrt(_MU * (2.0 / rp - 1.0 / a)))


def golden_b192(a: float = 2.0, ecc: float = 0.3) -> float:
    """Kepler 轨道周期 T = 2π√(a³/μ)（a=2.0, e=0.3）。"""
    return float(2.0 * PI * math.sqrt(a ** 3 / _MU))


# ======================================================================
# 族 C · 辐射传热角系数（view factor，B193-B196）
# ======================================================================
# 定义：F₁₂ = (1/A₁)∫_{A₁}∫_{A₂} cosθ₁cosθ₂/(πR²) dA₂dA₁
# golden：解析闭式（Siegel & Howell / Modest 标准式）
#   · 平行同轴**等尺寸**矩形（a×b，间距 c）：X=a/c, Y=b/c
#   · 垂直**共边**矩形（a×c 与 b×c，共享长 c 的边）：A=a/c, B=b/c
# cand：4D 张量积复合 Simpson 直接求积（各方向 n 等分）
# 已知文献值自检：平行 1×1@1 ≈ 0.1998；垂直共边 1×1 ≈ 0.2000。


def _vf_parallel_rect(X, Y):
    """平行同轴等尺寸矩形角系数闭式（X=a/c, Y=b/c）。"""
    S = math.sqrt
    t1 = math.log(S((1.0 + X * X) * (1.0 + Y * Y) / (1.0 + X * X + Y * Y)))
    t2 = X * S(1.0 + Y * Y) * math.atan(X / S(1.0 + Y * Y))
    t3 = Y * S(1.0 + X * X) * math.atan(Y / S(1.0 + X * X))
    t4 = -X * math.atan(X) - Y * math.atan(Y)
    return (2.0 / (PI * X * Y)) * (t1 + t2 + t3 + t4)


def _vf_perp_rect_common_edge(A, B):
    """垂直共边矩形角系数闭式（A=a/c, B=b/c；共边长度 c 已归一）。"""
    S = math.sqrt
    AB = A * A + B * B
    t1 = A * math.atan(1.0 / A) + B * math.atan(1.0 / B) - S(AB) * math.atan(1.0 / S(AB))
    lg = math.log(
        ((1.0 + A * A) * (1.0 + B * B) / (1.0 + AB))
        * (A * A * (1.0 + AB) / ((1.0 + A * A) * AB)) ** (A * A)
        * (B * B * (1.0 + AB) / ((1.0 + B * B) * AB)) ** (B * B)
    )
    return (1.0 / (PI * A)) * (t1 + 0.25 * lg)


def cand_vf_parallel_rect(a, b, c, n):
    """候选：平行同轴等尺寸矩形 F₁₂（4D 张量积复合 Simpson）。"""
    n = int(n)
    x = np.linspace(0.0, a, n + 1)
    y = np.linspace(0.0, b, n + 1)
    DX = x[:, None] - x[None, :]          # (nx,nx)
    DY = y[:, None] - y[None, :]          # (ny,ny)
    R2 = (DX[:, None, :, None] ** 2) + (DY[None, :, None, :] ** 2) + c * c
    I = c * c / (PI * R2 * R2)            # cosθ₁cosθ₂/(πR²) = c²/(πR⁴)
    w = _w_simpson(n)
    W = (w[:, None, None, None] * w[None, :, None, None]
         * w[None, None, :, None] * w[None, None, None, :])
    hx = a / n
    hy = b / n
    tot = float(np.sum(I * W)) * (hx / 3.0) * (hy / 3.0) * (hx / 3.0) * (hy / 3.0)
    return float(tot / (a * b))


def cand_vf_perp_rect_common_edge(a, b, c, n):
    """候选：垂直共边矩形 F₁₂（4D 张量积复合 Simpson，**分块累加版**）。

    几何：A₁ 在 z=0 平面 x∈[0,a], y∈[0,c]；A₂ 在 x=0 平面 z∈[0,b], y∈[0,c]。
    R² = x² + (y₂−y₁)² + z²；cosθ₁ = z/R（A₁ 法向 ẑ）、cosθ₂ = x/R（A₂ 法向 x̂）。

    🔴 B-11 血案 7（族 C 慢收敛 + 内存墙）：被积函数在**共边角点**（x=z=0 且 y₁=y₂）处
    按 ~xz/(πR⁴) 发散（R→0）⇒ 4D 均匀 Simpson 仅 **O(n⁻¹)** 收敛（实测 n=64 残差 2.7e-3，
    余量仅 3.7；想靠加大 n 提升余量时，整块 (n+1)⁴ 数组在 n≥96 时达 ~700MB–2.2GB（内存墙）。
    正解 = **按 x 方向分块累加**：每片只建 (n+1)³ 数组（n=96 时 97³≈9.1e5，7MB），
    数值恒等于整块版（实测 4D vs chunk 差 ≤ 1e-16）⇒ 既破内存墙又便于把 n 推到 96。
    共边角点 R²=0 且分子 xz 亦为 0（0/0）⇒ 用 `np.divide(..., where=R²>0, out=0)` 取极限 0。
    """
    n = int(n)
    w = _w_simpson(n)
    xs = np.linspace(0.0, a, n + 1)
    ys = np.linspace(0.0, c, n + 1)
    zs = np.linspace(0.0, b, n + 1)
    DY2 = (ys[:, None] - ys[None, :]) ** 2      # (ny,ny)
    Zrow = zs[None, None, :]                    # (1,1,nz)
    Z2 = Zrow * Zrow
    WY = w[:, None] * w[None, :]                # (ny,ny) y 方向权重
    acc = 0.0
    for i in range(n + 1):
        x = xs[i]
        R2 = x * x + DY2[:, :, None] + Z2       # (ny,ny,nz)
        num = x * Zrow                          # xz（共边角点 x=0 或 z=0 ⇒ 分子为 0）
        I = np.divide(num, PI * R2 * R2, out=np.zeros_like(R2),
                      where=R2 > 0.0)           # cosθ₁cosθ₂/(πR²)=xz/(πR⁴)
        acc += w[i] * float(np.einsum('ij,ijk,k->', WY, I, w))
    hx, hy, hz = a / n, c / n, b / n
    tot = acc * (hx / 3.0) * (hy / 3.0) * (hy / 3.0) * (hz / 3.0)
    return float(tot / (a * c))


def golden_b193(a: float = 1.0, b: float = 1.0, c: float = 1.0) -> float:
    """平行同轴等尺寸矩形角系数 F₁₂（a=b=c=1）。"""
    return float(_vf_parallel_rect(a / c, b / c))


def golden_b194(a: float = 1.0, b: float = 2.0, c: float = 1.0) -> float:
    """平行同轴等尺寸矩形角系数 F₁₂（a=1, b=2, c=1）。"""
    return float(_vf_parallel_rect(a / c, b / c))


def golden_b195(a: float = 1.0, b: float = 1.0, c: float = 1.0) -> float:
    """垂直共边矩形角系数 F₁₂（A=B=1）。"""
    return float(_vf_perp_rect_common_edge(a / c, b / c))


def golden_b196(a: float = 2.0, b: float = 1.0, c: float = 1.0) -> float:
    """垂直共边矩形角系数 F₁₂（A=2, B=1）。"""
    return float(_vf_perp_rect_common_edge(a / c, b / c))


# ======================================================================
# 族 D · Voigt 谱线轮廓（多普勒 ⊗ 洛伦兹，B197-B200）
# ======================================================================
# 物理：同时受高斯（多普勒）与洛伦兹（碰撞/自然）展宽的谱线轮廓
#   V(x;σ,γ) = ∫₋∞^∞ G(τ;σ)·L(x−τ;γ) dτ，
#   G(τ) = exp(−τ²/2σ²)/(σ√(2π))，L(u) = (γ/π)/(u²+γ²)。
# golden：scipy.special.voigt_profile（= Re[w(z)]/(σ√(2π))，wofz/Faddeeva 机器精度）。
# cand  ：卷积定义式复合 Simpson。**截断窗 [−12σ, 12σ]**（高斯 e^{−72}≈1e-32 使窗尾可忽略）；
#         洛伦兹尾部虽 1/u² 慢衰减，但被高斯因子切断 ⇒ 截断误差 ~1e-32，残差纯为离散化误差。


def _gauss(tt, sigma):
    return np.exp(-tt * tt / (2.0 * sigma * sigma)) / (sigma * math.sqrt(2.0 * PI))


def _lorentz(uu, gamma):
    return (gamma / PI) / (uu * uu + gamma * gamma)


def _voigt_conv(x, sigma, gamma, n):
    """候选：Voigt 轮廓（数值卷积，复合 Simpson）。

    🔴 血案规避（本批新增）：直接对 τ∈[−12σ,12σ] 均匀采样时，被积函数含**洛伦兹尖峰**
    （宽 ~γ）；γ≪σ 时粗网格会「跳过」尖峰 ⇒ 残差**非单调**（B200 实测 1.05e-1→1.52e-2→8.75e-4→
    **1.46e-2** 反弹）。正解 = **解析换元 τ = x + γ·sinh(u)**：
        L(x−τ) dτ = (γ/π)/(γ²sinh²u+γ²) · γcosh u du = sech(u)/π · du
    ⇒ 洛伦兹因子被解析积掉，被积函数化为 G(x+γ sinh u)·sech(u)/π（u 上光滑、指数衰减）。
    积分限 u∈[−U,U]，U = asinh(12σ/γ)（覆盖高斯 12σ 支撑）。
    """
    U = math.asinh(12.0 * sigma / gamma)

    def f(uu):
        tau = x + gamma * np.sinh(uu)
        return _gauss(tau, sigma) * (1.0 / np.cosh(uu)) / PI

    return float(_simpson(f, -U, U, n))


def golden_b197(sigma: float = 1.0, gamma: float = 1.0, x: float = 0.0) -> float:
    """Voigt 轮廓（σ=1.0, γ=1.0, x=0）。"""
    return float(_voigt_profile(x, sigma, gamma))


def golden_b198(sigma: float = 1.0, gamma: float = 0.5, x: float = 2.0) -> float:
    """Voigt 轮廓（σ=1.0, γ=0.5, x=2.0）。"""
    return float(_voigt_profile(x, sigma, gamma))


def golden_b199(sigma: float = 0.5, gamma: float = 2.0, x: float = 0.0) -> float:
    """Voigt 轮廓（σ=0.5, γ=2.0, x=0）。"""
    return float(_voigt_profile(x, sigma, gamma))


def golden_b200(sigma: float = 2.0, gamma: float = 0.5, x: float = 3.0) -> float:
    """Voigt 轮廓（σ=2.0, γ=0.5, x=3.0）。"""
    return float(_voigt_profile(x, sigma, gamma))


# ======================================================================
# 锚表 / 容差 / 候选分派
# ======================================================================

_TOL = 0.01                     # 缺省容差（对外 harness 的 tol 以 benchmarks.py 为准）
# 🔴 B-11 血案 10（逐锚 tol 收紧）：族 C/D 的指标动态范围只有 ~0.07–0.29 ⇒ 绝对
#   tol=0.01 相当于 3–14% **相对**容差，会把 10% 参数扰动的信号（~1e-3–3e-2）淹没
#   ⇒ 该锚对参数扰动「零判别力」（同 B-10 对 B10 的处理：tol 由 0.01 收紧 1e-8）。
#   逐锚收紧，保证两端各有余量：baseline 残差 < tol < 注册扰动键 ×1.1 信号。
_TOL_BY_BID = {
    "B185": 0.01, "B186": 0.01, "B187": 0.01, "B188": 0.01,
    "B189": 0.01, "B190": 0.01, "B191": 0.01, "B192": 0.01,
    "B193": 0.001, "B194": 0.001,      # 平行角系数（残差 7.8e-7 / 3.2e-6）
    "B195": 0.005, "B196": 0.005,      # 垂直共边角系数（残差 1.8e-3 / 1.7e-3，各 2.8×）
    "B197": 0.002, "B198": 0.002,      # Voigt（残差 1.3e-10 / 6.9e-10）
    "B199": 0.001, "B200": 0.001,      # Voigt（残差 1.2e-9 / 1.9e-9）
}

# 🔴 反向测试注册键（C5：key ×1.1 的信号必须 > tol；本表按 **±10% 双向** 实测标定）。
#   ✅ 注册 = 双向信号均 > tol 且余量 ≥1.4×；❌ 弱键 = 双向或单向 < tol
#   **如实登记、不掩盖、不用弱键充数** —— 见 B-11 报告 §6。
#   · B195：a 2.54/2.85× ✅注册；b 1.21/1.44×、c 1.29/1.47× 属**薄键**（>tol 但 <1.5×），
#     不依赖、仅登记。
#   · B196：a 1.88/2.21× ✅注册；b 1.03/1.16× 薄键；**c 0.89/1.00× ❌弱键**。
#   · B198：x 8.0/9.5×、sigma 3.6/4.0× ✅注册；**gamma 0.74/0.84× ❌弱键**（γ≪σ
#     时线翼由高斯主导，γ 失敏——物理上正确）。
#   · B200：x 11/12×、sigma 3.9/5.5× ✅注册；**gamma 0.11/0.14× ❌弱键**（同 B198 机理，
#     且 x=3 深在线翼）。
_PERTURB_KEYS = {
    "B185": ("s",), "B186": ("s",), "B187": ("s",), "B188": ("s",),
    "B189": ("a",), "B190": ("a", "ecc"), "B191": ("a", "ecc"), "B192": ("a",),
    "B193": ("a", "b", "c"), "B194": ("a", "b", "c"),
    "B195": ("a",), "B196": ("a",),
    "B197": ("gamma", "sigma"), "B198": ("sigma", "x"),
    "B199": ("gamma", "sigma"), "B200": ("sigma", "x"),
}

# 每锚物理参数（= benchmarks.py 的 default_params；harness 以 golden_fn(**params) 调）
_DEFAULT_PARAMS = {
    "B185": {"s": 4.0}, "B186": {"s": 3.0}, "B187": {"s": 3.0}, "B188": {"s": 5.0},
    # 🔴 周期锚（B189/B192）**只暴露 a**：Kepler 第三定律 T=2π√(a³/μ) 与 e 无关
    #    （e 固定于候选内部 0.6 / 0.3）。避免出现「×1.1 零响应」的冗余键（C3/C5）。
    "B189": {"a": 1.0}, "B190": {"a": 1.0, "ecc": 0.6},
    "B191": {"a": 1.0, "ecc": 0.6}, "B192": {"a": 2.0},
    "B193": {"a": 1.0, "b": 1.0, "c": 1.0}, "B194": {"a": 1.0, "b": 2.0, "c": 1.0},
    "B195": {"a": 1.0, "b": 1.0, "c": 1.0}, "B196": {"a": 2.0, "b": 1.0, "c": 1.0},
    # 🔴 线心锚（B197/B199）x≡0 **不暴露**：×1.1 恒为 0（零响应键）；敏感参数 = σ / γ。
    "B197": {"sigma": 1.0, "gamma": 1.0},
    "B198": {"sigma": 1.0, "gamma": 0.5, "x": 2.0},
    "B199": {"sigma": 0.5, "gamma": 2.0},
    "B200": {"sigma": 2.0, "gamma": 0.5, "x": 3.0},
}


# ----------------------------------------------------------------------
# 候选入口（物理参数 + 离散参数），供 verification_adapters 直接调用。
# 与 B-10 的 cand_mathieu(kind, order, q) 同构：物理参数进、标量出。
# ----------------------------------------------------------------------
def cand_b185(s: float = 4.0, n: int = 64) -> float:
    """候选 B185：玻色矩（换元 t=x/(1+x) + 复合 Simpson）。"""
    return _bose_moment(float(s), n)


def cand_b186(s: float = 3.0, n: int = 64) -> float:
    """候选 B186：玻色矩 ∫x²/(e^x−1)（复合 Simpson）。"""
    return _bose_moment(float(s), n)


def cand_b187(s: float = 3.0, n: int = 64) -> float:
    """候选 B187：费米矩 ∫x^{s−1}/(e^x+1)（复合 Simpson）。"""
    return _fermi_moment(float(s), n)


def cand_b188(s: float = 5.0, n: int = 64) -> float:
    """候选 B188：德拜矩 ∫x^{s−1}e^x/(e^x−1)²（复合 Simpson）。"""
    return _debye_moment(float(s), n)


def cand_b189(a: float = 1.0, ecc: float = 0.6, dt: float = 0.008) -> float:
    """候选 B189：Kepler 轨道周期（中心力 ODE 的 RK4 时间积分）。"""
    return _orbit_period(float(a), float(ecc), dt)


def cand_b190(a: float = 1.0, ecc: float = 0.6, dt: float = 0.008) -> float:
    """候选 B190：Kepler 近心点距离 r_p（RK4 + 三次 Hermite 穿越定位）。"""
    return _orbit_r_peri(float(a), float(ecc), dt)


def cand_b191(a: float = 1.0, ecc: float = 0.6, dt: float = 0.008) -> float:
    """候选 B191：Kepler 近心点速率 v_p（RK4 + 三次 Hermite 插值）。"""
    return _orbit_v_peri(float(a), float(ecc), dt)


def cand_b192(a: float = 2.0, ecc: float = 0.3, dt: float = 0.008) -> float:
    """候选 B192：Kepler 轨道周期（a=2,e=0.3；RK4 时间积分）。"""
    return _orbit_period(float(a), float(ecc), dt)


def cand_b193(a: float = 1.0, b: float = 1.0, c: float = 1.0, n: int = 16) -> float:
    """候选 B193：平行同轴等尺寸矩形角系数（4D 张量积复合 Simpson）。"""
    return cand_vf_parallel_rect(float(a), float(b), float(c), n)


def cand_b194(a: float = 1.0, b: float = 2.0, c: float = 1.0, n: int = 16) -> float:
    """候选 B194：平行同轴等尺寸矩形角系数（4D 复合 Simpson）。"""
    return cand_vf_parallel_rect(float(a), float(b), float(c), n)


def cand_b195(a: float = 1.0, b: float = 1.0, c: float = 1.0, n: int = 96) -> float:
    """候选 B195：垂直共边矩形角系数（4D 分块累加复合 Simpson）。"""
    return cand_vf_perp_rect_common_edge(float(a), float(b), float(c), n)


def cand_b196(a: float = 2.0, b: float = 1.0, c: float = 1.0, n: int = 96) -> float:
    """候选 B196：垂直共边矩形角系数（4D 分块累加复合 Simpson）。"""
    return cand_vf_perp_rect_common_edge(float(a), float(b), float(c), n)


def cand_b197(sigma: float = 1.0, gamma: float = 1.0, x: float = 0.0, n: int = 48) -> float:
    """候选 B197：Voigt 轮廓（sinh 换元 + 复合 Simpson 数值卷积）。

    n=48（残差 1.26e-10）：n=64 掉到 1.68e-13，会被 `run_d_criterion_smoke` ③
    「基线残差 > 1e-12」判为新红灯（B-11 血案 11）。
    """
    return _voigt_conv(float(x), float(sigma), float(gamma), n)


def cand_b198(sigma: float = 1.0, gamma: float = 0.5, x: float = 2.0, n: int = 64) -> float:
    """候选 B198：Voigt 轮廓（数值卷积）。"""
    return _voigt_conv(float(x), float(sigma), float(gamma), n)


def cand_b199(sigma: float = 0.5, gamma: float = 2.0, x: float = 0.0, n: int = 32) -> float:
    """候选 B199：Voigt 轮廓（数值卷积，n=32 避开噪声地板）。"""
    return _voigt_conv(float(x), float(sigma), float(gamma), n)


def cand_b200(sigma: float = 2.0, gamma: float = 0.5, x: float = 3.0, n: int = 64) -> float:
    """候选 B200：Voigt 轮廓（数值卷积）。"""
    return _voigt_conv(float(x), float(sigma), float(gamma), n)


# bid -> (golden_fn, cand_fn, 默认离散参数, 离散参数名, 参数标签)
_CASES = {
    # ---- 族 A：量子统计积分与 ζ 函数 ----
    "B185": (golden_b185, cand_b185, 64, "n", "bose s=4（黑体能量密度 π⁴/15）"),
    "B186": (golden_b186, cand_b186, 64, "n", "bose s=3（光子数密度 2ζ(3)）"),
    "B187": (golden_b187, cand_b187, 64, "n", "fermi s=3（费米 T² 比热 (3/2)ζ(3)）"),
    "B188": (golden_b188, cand_b188, 64, "n", "debye s=5（德拜 T³ 热容 4π⁴/15）"),
    # ---- 族 B：Kepler 二体轨道 ----
    "B189": (golden_b189, cand_b189, 0.008, "dt", "周期 T（a=1,e=0.6）"),
    "B190": (golden_b190, cand_b190, 0.008, "dt", "近心点距离 r_p（a=1,e=0.6）"),
    "B191": (golden_b191, cand_b191, 0.008, "dt", "近心点速率 v_p（a=1,e=0.6）"),
    "B192": (golden_b192, cand_b192, 0.008, "dt", "周期 T（a=2,e=0.3）"),
    # ---- 族 C：辐射传热角系数 ----
    "B193": (golden_b193, cand_b193, 16, "n", "平行 1×1@1"),
    "B194": (golden_b194, cand_b194, 16, "n", "平行 1×2@1"),
    "B195": (golden_b195, cand_b195, 96, "n", "垂直共边 1×1"),
    "B196": (golden_b196, cand_b196, 96, "n", "垂直共边 2×1"),
    # ---- 族 D：Voigt 谱线 ----
    "B197": (golden_b197, cand_b197, 48, "n", "σ=1,γ=1,x=0"),
    "B198": (golden_b198, cand_b198, 64, "n", "σ=1,γ=0.5,x=2"),
    "B199": (golden_b199, cand_b199, 32, "n", "σ=0.5,γ=2,x=0"),
    "B200": (golden_b200, cand_b200, 64, "n", "σ=2,γ=0.5,x=3"),
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
    print("Batch B-11 数值核自检（16 锚）")
    print("=" * 76)

    # ---- 极限/恒等式自检 ----
    print("\n[极限自检]")
    a1 = _bose_moment(4.0, 2000)
    print("  A1 玻色 s=4 数值=%.12f  π⁴/15=%.12f  差=%.3e" % (a1, PI ** 4 / 15.0, abs(a1 - PI ** 4 / 15.0)))
    # 恒等式：∫x³/(e^x−1)dx / ∫x²/(e^x−1)dx = π⁴/(30ζ(3)) ≈ 2.7011
    r = _bose_moment(4.0, 2000) / _bose_moment(3.0, 2000)
    print("  A2 比值 π⁴/(30ζ(3))=%.9f  数值=%.9f" % (PI ** 4 / (30.0 * _rzeta(3.0)), r))
    # 费米/玻色比：[(3/2)ζ(3)]/[2ζ(3)] = 0.75
    fr = _fermi_moment(3.0, 2000) / _bose_moment(3.0, 2000)
    print("  A3 费米/玻色比 期望=0.75  数值=%.9f" % fr)
    # 圆轨道极限：e=0 ⇒ L = √(μa)，v = √(μ/a)
    T0, S0 = _kepler_orbit(1.0, 0.0, 0.002)
    tc0 = _peri_times(T0, S0)
    print("  B1 圆轨道周期 数值=%.9f  期望 2π=%.9f" % (tc0[1] - tc0[0] if len(tc0) > 1 else float("nan"), 2 * PI))
    # 互易性：平行等尺寸 F₁₂ = F₂₁ 自动（同式）；垂直共边用 A₁ 归一，检查 F*A₁ 与反演
    print("  C1 平行 1×1@1 闭式=%.9f（文献 ≈0.1998）" % _vf_parallel_rect(1.0, 1.0))
    print("  C1 垂直共边 1×1 闭式=%.9f（文献 ≈0.2000）" % _vf_perp_rect_common_edge(1.0, 1.0))
    # γ→0 高斯极限
    v_gl = _voigt_conv(0.0, 1.0, 1e-8, 4000)
    print("  D1 γ→0 极限 数值=%.9f  高斯峰 1/(σ√2π)=%.9f" % (v_gl, 1.0 / math.sqrt(2 * PI)))

    # ---- 主表 ----
    print("\n[主表] golden / candidate / 残差 / 余量")
    rows = []
    for bid in _CASES:
        label = _CASES[bid][4]
        g = _golden_by_bid(bid)
        c = _cand_by_bid(bid)
        d = abs(c - g)
        rows.append((bid, label, g, c, d,
                     _TOL_BY_BID[bid] / d if d > 0 else float("inf")))
    for bid, label, g, c, d, mar in sorted(rows):
        print("  %s %-34s g=%.9f c=%.9f |Δ|=%.3e 余量=%.1f×" % (bid, label, g, c, d, mar))

    # ---- 判据 D：只扫候选自身离散参数 ----
    print("\n[判据 D] 只扫候选离散参数（残差须浮出噪声地板且单调收敛）")
    scans = {
        "B185": ([16, 24, 32, 48, 64, 96, 128], golden_b185),
        "B186": ([16, 24, 32, 48, 64, 96, 128], golden_b186),
        "B187": ([16, 24, 32, 48, 64, 96, 128], golden_b187),
        "B188": ([16, 24, 32, 48, 64, 96, 128], golden_b188),
        "B189": ([0.128, 0.064, 0.032, 0.016, 0.008, 0.004], golden_b189),
        "B190": ([0.128, 0.064, 0.032, 0.016, 0.008, 0.004], golden_b190),
        "B191": ([0.128, 0.064, 0.032, 0.016, 0.008, 0.004], golden_b191),
        "B192": ([0.512, 0.256, 0.128, 0.064, 0.032, 0.016, 0.008], golden_b192),
        "B193": ([8, 12, 16, 24, 32, 48], golden_b193),
        "B194": ([8, 12, 16, 24, 32, 48], golden_b194),
        "B195": ([16, 24, 32, 48, 64, 96], golden_b195),
        "B196": ([16, 24, 32, 48, 64, 96], golden_b196),
        "B197": ([8, 12, 16, 24, 32, 48], golden_b197),
        "B198": ([24, 28, 32, 40, 48, 64, 96], golden_b198),
        "B199": ([8, 12, 16, 24, 32], golden_b199),
        "B200": ([8, 12, 16, 24, 32, 48, 64], golden_b200),
    }
    allok = True
    for bid in sorted(scans):
        params, gf = scans[bid]
        g = gf(**_DEFAULT_PARAMS[bid])
        ds = []
        for p_ in params:
            ds.append(abs(_cand_by_bid(bid, p_) - g))
        mono = all(ds[i + 1] < ds[i] for i in range(len(ds) - 1))
        ratios = [ds[i] / ds[i + 1] if ds[i + 1] > 0 else float("inf") for i in range(len(ds) - 1)]
        ok = (ds[0] > 1e-13) and (ds[-1] < _TOL_BY_BID[bid]) and mono
        allok = allok and ok
        print("  %s %s  首=%.3e 末=%.3e 单调=%s 最小衰减=%.2f×"
              % (bid, "OK " if ok else "BAD", ds[0], ds[-1], mono, min(ratios)))
        print("      残差链: " + " ".join("%.2e" % d for d in ds))

    print("\nALL_OK=%s" % allok)
    return allok


if __name__ == "__main__":
    _self_test()
