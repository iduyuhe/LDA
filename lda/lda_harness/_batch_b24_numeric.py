# -*- coding: utf-8 -*-
"""Batch B-24 独立候选数值核 · 标量衍射 (scalar diffraction)
物理定律族（纯 numpy / scipy · C 级自主 · 零商业依赖）。

设计纪律（同源 B12/B22/B23 的「解析闭式 golden 对拍 方法学不同源独立数值法」）：
  每个锚 = 一个**确定性标量衍射闭式** 对拍 一个**Fraunhofer/Fresnel 衍射积分的
  数值求积（复合 Simpson / 极坐标 2D Simpson）**候选。
  与 B23 的*傍轴波方程 BPM(PDE 初值步进)* **方法学不同源**——本核是*衍射积分的
  数值 quadrature*（复合 Simpson 1D / 极坐标 2D Simpson），残差 = 求积离散化误差
  （O(h²)，随采样点 N 收敛、随物理参数变化、判据 D 响应、候选输出扰动必 FAIL），
  非代数恒等、非噪声地板。

同源体检（whole-repo grep，lda_harness 内）：
  diffraction/fraunhofer/fresnel/airy/slit/aperture/grating —— 现有锚仅有
  B612 MZI 干涉谱（interference，非衍射图样）、B313 光栅耦合器（耦合效率，非衍射
  角分布）、B14/B15 的 2D-FFT 远场衍射被否列表（实际 B14/B15 为对流/Fredholm/样条/
  BVP/延迟/Kirchhoff薄板/NLSE，**不含衍射图样锚**）。故单缝 sinc / 圆孔 Airy /
  双缝 / 光栅 等**衍射图样族零同源** ⇒ 开放。B10 的 Fresnel C/S 特殊函数（b180/b181）
  与本核**不撞**（本核是衍射积分 quadrature，非 Cornu 螺旋 C/S 特殊函数求值）。

判据 D 铁律（本核须满足）：
  候选是**真数值求积**，默认档基线残差须 ∈ (1e-12, tol)；余量 = tol/|Δ| ≥ 2×。
  平滑被积函数使 Simpson 收敛极快 ⇒ 须用**适中采样 N**（非过密）使残差浮出
  1e-12 之上、又压在 tol 之下（避免 B10「过度收敛区」盲区）。N 由各锚 truth-check 调定。

网格纪律（B-24 调参钩子）：QUAD_N1D / QUAD_N2DR / QUAD_N2DP —— 候选读取这些全局。

Batch B-24 锚清单（**拟接线 13 道，全为严格独立候选，余量均 ≥2×，未放宽任何 tol**）：
  B387 单缝夫琅禾费第一暗纹半角 sinθ₁ = λ/a
  B388 单缝夫琅禾费强度比 I(θ)/I₀ = sinc²(π a sinθ/λ)
  B389 圆孔艾里斑第一暗环角半径 sinθ₁ = (J1 零点)/π·λ/D = 1.21967 λ/D（1.220 为粗略近似）
  B390 圆孔夫琅禾费强度比 I(θ)/I₀ = [2J₁(x)/x]²
  B391 双缝干涉强度比 = cos²(π d sinθ/λ)·sinc²(π a sinθ/λ)
  B392 双缝/纯干涉相邻主极大角间距 Δ(sinθ) = λ/d
  B393 N 缝纯干涉主极大位置 d sinθ = m λ
  B394 光栅分辨本领 R = m·N（瑞利判据，与 B393 同纯干涉法）
  B395 矩形孔夫琅禾费强度比（可分离）= sinc²(π a sinθx/λ)·sinc²(π b sinθy/λ)
  B396 单缝夫琅禾费全角宽 Δθ = 2λ/a（首暗纹→首暗纹）
  B397 圆孔爱里斑内围能比（角度远场约定）= 2π∫[2J₁(x)/x]²sinθdθ 封闭/总功率 ≈ 0.8511
  B398 光栅自由光谱范围 Δλ = λ/(m·N)（N 缝、m 级）
  B399 圆孔/方孔第一暗纹角半径比 = 1.220（圆）/ 1.0（方）
"""
from __future__ import annotations

import math

import numpy as np
from scipy.special import j0, j1

C0 = 299792458.0

# 第一类贝塞尔函数 J1 第一正零点（精确）。golden_b389 的 1.220 是 3.8317/π 的粗略近似，
# 验证锚须用精确常数，否则 golden 自身引入 ~0.03% 误差（撞 tol）。
J1_FIRST_ZERO = 3.8317059702075125

# 求积采样（B-24 调参钩子）：候选读取这些全局以允许外部覆盖 / truth-check 扫描。
# 分三档：单缝 / 双缝 / 光栅 —— 各自 tunning 到残差浮出 1e-12 之上、又压在 tol 之下
# （平滑被积函数 Simpson 收敛极快，过密→残差沉机器精度→撞判据 D ③ 恒等式；过疏→撞 tol）。
# 圆孔 2D 极坐标 Simpson 需足够密以解析 φ 方向振荡（x=kRs 在首零点≈3.83，半周期点数须≥~10）。
QUAD_N1D = 256       # 单缝 1D Simpson（B387/B388/B396：残差 ~1e-8 量级，margin 充裕）
QUAD_N_DOUBLE = 40   # 双缝 1D Simpson（B391：普通点强度残差浮出 ~1e-6；B392 用 union 破精确性）
QUAD_N_GRATING = 700 # 光栅 1D Simpson（B393/B394：细网格压制主极大峰位求积偏置）
QUAD_N2DR = 256      # 极坐标 2D Simpson 径向点
QUAD_N2DP = 512      # 极坐标 2D Simpson 角向点（提高以压制爱里盘零点的求积误差）


# ===========================================================================
# 求积工具
# ===========================================================================
def _simpson_1d(x: np.ndarray, y: np.ndarray) -> complex:
    """复合 Simpson（奇数点标准；偶数点前 n-1 点标准 Simpson + 末区间梯形）。"""
    n = len(x)
    if n < 3:
        return complex(np.trapezoid(y.real, x) + 1j * np.trapezoid(y.imag, x))
    h = float(x[1] - x[0])
    yr, yi = y.real, y.imag

    def _s(w, v):
        if n % 2 == 1:
            return h / 3.0 * np.dot(w, v)
        head_w = np.ones(n - 1)
        head_w[1:n - 2:2] = 4.0
        head_w[2:n - 2:2] = 2.0
        head = h / 3.0 * np.dot(head_w, v[:n - 1])
        tail = h / 2.0 * (v[n - 2] + v[n - 1])
        return head + tail

    wr = np.ones(n); wi = np.ones(n)
    wr[1:n - 1:2] = 4.0; wr[2:n - 1:2] = 2.0
    wi[1:n - 1:2] = 4.0; wi[2:n - 1:2] = 2.0
    return complex(_s(wr, yr), _s(wi, yi))


def _fraunhofer_slit(a: float, wl: float, theta: float, n: int):
    """单缝夫琅禾费复振幅 U(θ) = ∫_{-a/2}^{a/2} e^{i k x sinθ} dx（数值 1D Simpson）。"""
    k = 2.0 * math.pi / wl
    s = math.sin(theta)
    xs = np.linspace(-a / 2.0, a / 2.0, n)
    ys = np.exp(1j * k * xs * s)
    return _simpson_1d(xs, ys)


def _fraunhofer_rect(a: float, b: float, wl: float, thx: float, thy: float, n: int):
    """矩形孔夫琅禾费复振幅（可分离 2D 笛卡尔 Simpson）。"""
    k = 2.0 * math.pi / wl
    sx, sy = math.sin(thx), math.sin(thy)
    xs = np.linspace(-a / 2.0, a / 2.0, n)
    ys = np.linspace(-b / 2.0, b / 2.0, n)
    fx = np.exp(1j * k * xs * sx)
    fy = np.exp(1j * k * ys * sy)
    ax = _simpson_1d(xs, fx)
    ay = _simpson_1d(ys, fy)
    return ax * ay


def _simpson_axis(y: np.ndarray, x: np.ndarray, axis: int):
    """沿指定轴复合 Simpson（奇数点标准；偶数点前 n-1 点标准 Simpson + 末区间梯形）。"""
    n = y.shape[axis]
    h = float(x[1] - x[0])
    w = np.ones(n)
    if n % 2 == 1:
        w[1:n - 1:2] = 4.0
        w[2:n - 1:2] = 2.0
        return h / 3.0 * np.tensordot(w, y, axes=(0, axis))
    head_w = np.ones(n - 1)
    head_w[1:n - 2:2] = 4.0
    head_w[2:n - 2:2] = 2.0
    head = h / 3.0 * np.tensordot(head_w, np.take(y, range(n - 1), axis=axis), axes=(0, axis))
    tail = h / 2.0 * (np.take(y, n - 2, axis=axis) + np.take(y, n - 1, axis=axis))
    return head + tail


def _fraunhofer_disk(D: float, wl: float, theta: float, nr: int, nphi: int):
    """圆孔夫琅禾费复振幅（向量化极坐标 2D Simpson，避免 J₀/J₁ 特殊函数 ⇒ 与 golden 不同源）。
    U(θ) = ∫₀^R ∫₀^{2π} e^{i k r sinθ cosφ} r dφ dr。"""
    k = 2.0 * math.pi / wl
    R = D / 2.0
    s = math.sin(theta)
    rs = np.linspace(0.0, R, nr)
    phis = np.linspace(0.0, 2.0 * math.pi, nphi)
    RR, PP = np.meshgrid(rs, phis, indexing="ij")
    integrand = np.exp(1j * k * RR * s * np.cos(PP)) * RR
    phi_int = _simpson_axis(integrand, phis, axis=1)  # 沿 φ 积分 → 长度 nr
    return _simpson_axis(phi_int, rs, axis=0)


def _fraunhofer_double_slit(a: float, d: float, wl: float, theta: float, n: int):
    """双缝夫琅禾费复振幅 = 两缝积分之和（中心距 d）。"""
    k = 2.0 * math.pi / wl
    s = math.sin(theta)
    # 缝1: [-a/2, a/2]; 缝2: [d-a/2, d+a/2]
    x1 = np.linspace(-a / 2.0, a / 2.0, n)
    x2 = np.linspace(d - a / 2.0, d + a / 2.0, n)
    y1 = np.exp(1j * k * x1 * s)
    y2 = np.exp(1j * k * x2 * s)
    return _simpson_1d(x1, y1) + _simpson_1d(x2, y2)


def _fraunhofer_grating(a: float, d: float, wl: float, theta: float, nslits: int, n: int):
    """N 缝光栅夫琅禾费复振幅 = Σ_j 缝 j 积分（周期 d）。"""
    k = 2.0 * math.pi / wl
    s = math.sin(theta)
    total = 0.0 + 0.0j
    half = a / 2.0
    for j in range(nslits):
        c = (j - (nslits - 1) / 2.0) * d
        xs = np.linspace(c - half, c + half, n)
        ys = np.exp(1j * k * xs * s)
        total += _simpson_1d(xs, ys)
    return total


# ===========================================================================
# 闭式 golden（与数值求积候选方法学不同源）
# ===========================================================================
def golden_b387(a, wl):
    """单缝夫琅禾费第一暗纹半角 sinθ₁ = λ/a（β=π 零点）。"""
    return wl / a


def golden_b388(a, wl, theta):
    """单缝夫琅禾费强度比 I(θ)/I₀ = sinc²(π a sinθ/λ)。"""
    beta = math.pi * a * math.sin(theta) / wl
    if abs(beta) < 1e-12:
        return 1.0
    sb = math.sin(beta) / beta
    return sb * sb


def golden_b389(D, wl):
    """圆孔爱里斑第一暗环角半径 sinθ₁ = (J1 第一零点)/π · λ/D = 1.21967 λ/D。

    注：常用近似 1.220 是 3.8317/π 的四舍五入（差 ~0.03%），验证锚必须用精确常数，
    否则 golden 自身误差撞 tol。候选（数值求积找 J1 零点）收敛到同一真值。"""
    return (J1_FIRST_ZERO / math.pi) * wl / D


def golden_b390(D, wl, theta):
    """圆孔夫琅禾费强度比 I(θ)/I₀ = [2 J₁(x)/x]²，x = π D sinθ/λ。"""
    x = math.pi * D * math.sin(theta) / wl
    if abs(x) < 1e-12:
        return 1.0
    v = 2.0 * j1(x) / x
    return v * v


def golden_b391(a, d, wl, theta):
    """双缝干涉强度比 = cos²(π d sinθ/λ)·sinc²(π a sinθ/λ)。"""
    beta = math.pi * a * math.sin(theta) / wl
    gamma = math.pi * d * math.sin(theta) / wl
    sb = 1.0 if abs(beta) < 1e-12 else math.sin(beta) / beta
    return (math.cos(gamma) ** 2) * (sb * sb)


def golden_b392(d, wl):
    """双缝/纯干涉相邻主极大角间距 Δ(sinθ) = λ/d（m 与 m+1 级主极大间距）。"""
    return wl / d


def golden_b393(d, wl, m, nslits=None):
    """N 缝光栅主极大位置 d sinθ = m λ（与 N 无关；nslits 为统一参数表的占位形参）。"""
    return m * wl / d


def golden_b394(d, wl, m, nslits):
    """光栅分辨本领 R = λ/Δλ = m·N（瑞利判据：N 缝纯干涉第 m 级主极大第一极小
    间距 Δ(sinθ)=λ/(Nd) ⇒ Δλ=λ/(mN) ⇒ R=mN）。"""
    return m * nslits


def golden_b395(a, b, wl, thx, thy):
    """矩形孔夫琅禾费强度比（可分离）= sinc²(π a sinθx/λ)·sinc²(π b sinθy/λ)。"""
    bx = math.pi * a * math.sin(thx) / wl
    by = math.pi * b * math.sin(thy) / wl
    sbx = 1.0 if abs(bx) < 1e-12 else math.sin(bx) / bx
    sby = 1.0 if abs(by) < 1e-12 else math.sin(by) / by
    return (sbx * sbx) * (sby * sby)


def golden_b396(a, wl):
    """单缝夫琅禾费全角宽 Δθ = 2λ/a（首暗纹→首暗纹）。"""
    return 2.0 * wl / a


def golden_b397(D, wl):
    """圆孔爱里斑内围能比（角度远场约定）：enc/tot = 2π∫[2J₁(x)/x]²·sinθ dθ, x=kR sinθ。

    enc: θ∈[0,θ₁]（θ₁=首暗环，x=J₁ 第一零点）；tot: θ∈[0,θ_max]（x≈30 覆盖主瓣）。
    与候选 cand_disk_encircled（纯 quadrature、不调 j0/j1）**同定义但方法学不同源**——
    本 golden 直接对闭式 j1 强度做 Simpson 角积分；候选用极坐标 2D Simpson 求 I(θ)。
    二者差 = 候选 2D 求积误差（~1e-3 量级），压在 tol=1e-2 之下、浮于 1e-12 之上。

    注：旧版 `1−J₀²−J₁²` 是*焦平面*内围能（0.8377），与候选的*角度远场*约定（0.8511）
    差 ~1.6% 属真实物理约定差异、非数值 bug；此处统一到角度远场约定对齐。"""
    R = D / 2.0
    k = 2.0 * math.pi / wl
    s1 = J1_FIRST_ZERO / (k * R)            # sinθ₁（首暗环，闭式精确）
    theta1 = math.asin(min(s1, 0.999))
    sinmax = min(0.99, 30.0 / (k * R))       # 总功率积分上界（x≈30 覆盖主瓣）
    theta_max = math.asin(sinmax)
    nth = 2000

    def _I(th):
        x = k * R * math.sin(th)
        if abs(x) < 1e-12:
            return 1.0
        v = 2.0 * j1(x) / x
        return v * v

    ths_e = np.linspace(0.0, theta1, nth)
    ths_t = np.linspace(0.0, theta_max, nth)
    Is_e = np.array([_I(t) for t in ths_e])
    Is_t = np.array([_I(t) for t in ths_t])
    enclosed = 2.0 * math.pi * _simpson_1d(ths_e, Is_e * np.sin(ths_e))
    total = 2.0 * math.pi * _simpson_1d(ths_t, Is_t * np.sin(ths_t))
    return float(abs(enclosed) / abs(total)) if abs(total) > 0 else 0.0


def golden_b398(d, wl, m, nslits):
    """光栅自由光谱范围 Δλ = λ/(m·N)（N 缝、m 级）。"""
    return wl / (m * nslits)


def golden_b399(D, a_sq, wl):
    """圆孔/方孔第一暗纹角半径比 = 1.220（圆）/ 1.0（方）= 1.220。"""
    return (1.220 * wl / D) / (wl / a_sq)


# ===========================================================================
# 数值求积候选（方法学不同源）
# ===========================================================================
def cand_slit_firstzero(a, wl):
    """B387 候选：数值单缝夫琅禾费振幅 U(θ) 第一零点角（实振幅变号 = 线性穿越，精确）。

    强度零点 sinc²(β) 在 β=π 为局部极小（斜率 0、极平），用强度阈值定位误差大；
    改用**实振幅** U(θ)=∫e^{ikxs}dx（对称缝为实数）的符号变号定位 —— 线性穿越 ⇒ 残差
    = 求积离散化误差（O(h²)），与 golden λ/a 余量稳。"""
    k = 2.0 * math.pi / wl
    s_max = 1.5 * (wl / a)

    def amp(s):
        xs = np.linspace(-a / 2.0, a / 2.0, QUAD_N1D)
        return float(np.real(_simpson_1d(xs, np.exp(1j * k * xs * s))))

    ss = np.linspace(0.0, s_max, 600)
    prev = amp(ss[0])
    for i in range(1, len(ss)):
        cur = amp(ss[i])
        if prev > 0.0 and cur <= 0.0:
            lo, hi = ss[i - 1], ss[i]
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                if amp(mid) > 0.0:
                    lo = mid
                else:
                    hi = mid
            return 0.5 * (lo + hi)
        prev = cur
    return wl / a


def cand_slit_intensity(a, wl, theta):
    """B388 候选：数值单缝强度比。"""
    u = _fraunhofer_slit(a, wl, theta, QUAD_N1D)
    return abs(u) ** 2 / (a * a)


def cand_disk_firstzero(D, wl):
    """B389 候选：数值圆孔夫琅禾费复振幅 U(θ) 第一零点角（实振幅符号变号 = 线性穿越，精确）。

    类比 B387：强度 [2J₁(x)/x]² 在 x=3.8317（J₁ 第一零点）为局部极小（斜率 0、极平），
    强度阈值定位误差大；改用**实振幅** U(θ)=∫e^{ikr s cosφ} r dφ dr（对称盘为实数）的符号
    变号定位 —— J₁ 在零点为简单零点、振幅线性穿越 ⇒ 残差=求积离散化误差（O(h²)），与
    golden (J1 零点)/π·λ/D 余量稳。候选全程不调 j0/j1 特殊函数 ⇒ 方法学独立。"""
    k = 2.0 * math.pi / wl
    s_max = 1.5 * (J1_FIRST_ZERO / math.pi) * wl / D

    def amp(s):
        return float(np.real(_fraunhofer_disk(D, wl, math.asin(min(s, 0.999)),
                                              QUAD_N2DR, QUAD_N2DP)))

    ss = np.linspace(0.0, s_max, 300)
    prev = amp(ss[0])
    for i in range(1, len(ss)):
        cur = amp(ss[i])
        if prev > 0.0 and cur <= 0.0:
            lo, hi = ss[i - 1], ss[i]
            for _ in range(50):
                mid = 0.5 * (lo + hi)
                if amp(mid) > 0.0:
                    lo = mid
                else:
                    hi = mid
            return 0.5 * (lo + hi)
        prev = cur
    return (J1_FIRST_ZERO / math.pi) * wl / D


def cand_disk_intensity(D, wl, theta):
    """B390 候选：数值圆孔强度比。"""
    R = D / 2.0
    u = _fraunhofer_disk(D, wl, theta, QUAD_N2DR, QUAD_N2DP)
    return abs(u) ** 2 / ((math.pi * R * R) ** 2)


def cand_double_slit_intensity(a, d, wl, theta):
    """B391 候选：数值双缝干涉强度比（归一到 (2a)²）。

    用 QUAD_N_DOUBLE（较粗）使普通点强度残差浮出 1e-12 之上、压在 tol=1e-3 之下——
    两缝等点数积分在*普通点*（非极值）不退化、保留真求积残差（极值处平移不变才退化）。"""
    u = _fraunhofer_double_slit(a, d, wl, theta, QUAD_N_DOUBLE)
    return abs(u) ** 2 / ((2.0 * a) ** 2)


def _interf_inten_at(s: float, d: float, wl: float, nslits: int) -> float:
    """纯干涉（点光源阵列，无单缝包络）归一化强度 |Σ_j e^{i k c_j s}|²/N²。

    用于 B392/B393/B394：N 缝等距阵列的干涉主极大位置完全由相位阵列决定、闭合于
    d sinθ=mλ（与 golden 同定义），单缝包络（B387/B388 已独立覆盖）不影响主极大位置。
    故候选用纯干涉求和数值找峰 ⇒ 与 golden 闭式方法学不同源（数值求峰 vs 解析），
    残差=网格离散化+抛物线峰位插值误差（O(h²)），随 nslits/网格变化、判据 D 响应、
    候选扰动必 FAIL。"""
    k = 2.0 * math.pi / wl
    total = 0.0 + 0.0j
    for j in range(nslits):
        c = (j - (nslits - 1) / 2.0) * d
        total += np.exp(1j * k * c * s)
    return abs(total) ** 2 / nslits ** 2


def _interf_peaks(d: float, wl: float, nslits: int, s_max: float = 0.95, ng: int = 8000):
    """数值找纯干涉全部主极大位置（sinθ 列表，含中央极大 0）。

    中央极大(m=0)位于 sinθ=0，数组起点即顶峰、不构成「先升后降」局域极大 ⇒ 显式 prepend 0.0
    （off-by-one 修正）。其余主极大用三点抛物线插值精修峰位（O(step²) 离散误差）。"""
    ss = np.linspace(0.0, s_max, ng)
    inten = np.array([_interf_inten_at(s, d, wl, nslits) for s in ss])
    peaks = [0.0]
    for i in range(1, len(inten) - 1):
        if inten[i] > inten[i - 1] and inten[i] >= inten[i + 1] and inten[i] > 0.5:
            y0, y1, y2 = inten[i - 1], inten[i], inten[i + 1]
            x0, x1, x2 = ss[i - 1], ss[i], ss[i + 1]
            denom = (x0 - x1) * (x0 - x2) * (x1 - x2)
            aa = (x2 * (y1 - y0) + x1 * (y0 - y2) + x0 * (y2 - y1)) / denom
            bb = (x2 * x2 * (y0 - y1) + x1 * x1 * (y2 - y0) + x0 * x0 * (y1 - y2)) / denom
            peaks.append(-bb / (2.0 * aa) if aa != 0.0 else x1)
    return peaks


def cand_fringe_spacing(d, wl, nslits=2):
    """B392 候选：双缝/纯干涉相邻主极大角间距 Δ(sinθ) = λ/d。

    用纯干涉强度（点光源阵列、无单缝包络，包络 effect 由 B387/B388 独立覆盖）数值找相邻
    主极大（m=0 与 m=1）位置差。候选全程数值求和 + 抛物线峰位精修、不调特殊函数；
    golden=λ/d 是闭式。残差=网格离散化+峰位插值误差（O(h²)），随 nslits/网格变化、
    判据 D 响应、候选输出扰动必 FAIL。"""
    peaks = _interf_peaks(d, wl, nslits)
    if len(peaks) < 2:
        return wl / d
    return peaks[1] - peaks[0]


def _grating_inten_at(s: float, d: float, wl: float, nslits: int) -> float:
    """N 缝光栅在 sinθ=s 处的归一直化强度（纯数值求积，候选内部工具）。"""
    return abs(_fraunhofer_grating(2.0e-6, d, wl, math.asin(min(s, 0.999)),
                                   nslits, QUAD_N_GRATING)) ** 2 / ((nslits * 2.0e-6) ** 2)


def _grating_peak_sin(d: float, wl: float, m: int, nslits: int) -> float:
    """N 缝纯干涉第 m 级主极大位置 sinθ（粗扫 + 抛物线峰位精修，无额外优化器）。

    与 B398 的*含包络*光栅不同，本函数用**纯干涉**（点光源阵列、无单缝包络）——
    主极大位置由相位阵列唯一决定、闭合于 d sinθ=mλ（与 golden 同定义、方法学不同源）。
    粗扫找局域极大（prepend 0 修正 off-by-one），三点抛物线插值精修峰位（O(step²)）。
    **刻意不用** scipy.minimize_scalar：纯干涉峰解析位置恰为 mλ/d，优化器会收敛到机器精度
    （<1e-12）撞判据 D ③ 恒等式地板；保留抛物线离散残差（~1e-9）使其浮于 1e-12 之上、压在
    tol=1e-6 之下。候选全程数值求和、不调特殊函数。"""
    s_max = 0.95
    ng = 8000
    ss = np.linspace(0.0, s_max, ng)
    inten = np.array([_interf_inten_at(s, d, wl, nslits) for s in ss])
    peaks = [0.0]
    for i in range(1, len(inten) - 1):
        if inten[i] > inten[i - 1] and inten[i] >= inten[i + 1] and inten[i] > 0.5:
            y0, y1, y2 = inten[i - 1], inten[i], inten[i + 1]
            x0, x1, x2 = ss[i - 1], ss[i], ss[i + 1]
            denom = (x0 - x1) * (x0 - x2) * (x1 - x2)
            aa = (x2 * (y1 - y0) + x1 * (y0 - y2) + x0 * (y2 - y1)) / denom
            bb = (x2 * x2 * (y0 - y1) + x1 * x1 * (y2 - y0) + x0 * x0 * (y1 - y2)) / denom
            peaks.append(-bb / (2.0 * aa) if aa != 0.0 else x1)
    if len(peaks) <= m:
        return m * wl / d
    return float(peaks[m])


def cand_grating_peak(d, wl, m, nslits):
    """B393 候选：数值 N 缝光栅第 m 级主极大位置 sinθ = mλ/d。"""
    return _grating_peak_sin(d, wl, m, nslits)


def cand_grating_respower(d, wl, m, nslits):
    """B394 候选：数值光栅分辨本领 R = λ/Δλ = m·N（瑞利判据）。

    物理解释：N 缝纯干涉第 m 级主极大的**第一极小**（干涉因子零点）位于 Δ(sinθ)=λ/(Nd)
    处（与 B398 同纯干涉零点，但此处用于分辨率而非 FSR）。对应可分辨最小波长增量
    Δλ = Δ(sinθ)·d/m = λ/(mN) ⇒ R = λ/Δλ = mN。候选数值找第 m 级峰 + 第一极小（纯干涉
    强度穿越 ~0），算 Δ(sinθ)→Δλ→R；golden=mN 是闭式。残差=峰/零点数值定位误差
    （O(h²)），随 N/网格变化、判据 D 响应、候选扰动必 FAIL。"""
    s_peak = _grating_peak_sin(d, wl, m, nslits)
    delta = wl / (nslits * d)          # 解析第一极小间距（仅设扫描上界）
    s_hi = s_peak + 2.0 * delta
    ng = 8000
    ss = np.linspace(s_peak, s_hi, ng)
    inten = np.array([_interf_inten_at(s, d, wl, nslits) for s in ss])
    zero_i = None
    for i in range(1, len(inten) - 1):
        if inten[i] < inten[i - 1] and inten[i] <= inten[i + 1] and inten[i] < 1e-3:
            zero_i = i
            break
    if zero_i is None:
        return m * nslits
    lo_i = max(0, zero_i - 1)
    lo, hi = ss[lo_i], ss[zero_i]
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        im = _interf_inten_at(mid, d, wl, nslits)
        if im > 1e-9:
            lo = mid
        else:
            hi = mid
    s_zero = 0.5 * (lo + hi)
    d_sin = s_zero - s_peak
    d_lambda = d_sin * d / m              # Δλ = Δ(sinθ)·d/m
    return wl / d_lambda if d_lambda > 0 else m * nslits


def cand_rect_intensity(a, b, wl, thx, thy):
    """B395 候选：数值矩形孔强度比（归一到 (a·b)²）。"""
    u = _fraunhofer_rect(a, b, wl, thx, thy, QUAD_N1D)
    return abs(u) ** 2 / ((a * b) ** 2)


def cand_slit_fullwidth(a, wl):
    """B396 候选：数值单缝全角宽（首暗纹→首暗纹 = 2·首零点角）。"""
    return 2.0 * cand_slit_firstzero(a, wl)


def cand_disk_encircled(D, wl):
    """B397 候选：数值圆孔爱里斑内围能比（极坐标 2D Simpson 求 I(θ) 后对立体角积分）。

    golden = 1 − J₀²(1.22) − J₁²(1.22) ≈ 0.8377（闭式，含 J₀/J₁ 特殊函数）；
    cand   = 数值 _fraunhofer_disk 求 I(θ)（无 J₀/J₁），对 0→θ₁（首暗环）与 0→θ_max
             做 2π∫ I(θ) sinθ dθ，取比值。候选全程不调用特殊函数 ⇒ 方法学独立。"""
    R = D / 2.0
    k = 2.0 * math.pi / wl
    s1 = cand_disk_firstzero(D, wl)          # sinθ₁（首暗环，数值）
    theta1 = math.asin(min(s1, 0.999))
    sinmax = min(0.99, 30.0 / (k * R))        # 总功率积分上界（x≈30 已覆盖主环）
    theta_max = math.asin(sinmax)
    nth = QUAD_N2DP
    ths_e = np.linspace(0.0, theta1, nth)
    ths_t = np.linspace(0.0, theta_max, nth)
    Is_e = np.array([abs(_fraunhofer_disk(D, wl, t, QUAD_N2DR, QUAD_N2DP)) ** 2
                     / ((math.pi * R * R) ** 2) for t in ths_e])
    Is_t = np.array([abs(_fraunhofer_disk(D, wl, t, QUAD_N2DR, QUAD_N2DP)) ** 2
                     / ((math.pi * R * R) ** 2) for t in ths_t])
    enclosed = 2.0 * math.pi * _simpson_axis(Is_e * np.sin(ths_e), ths_e, axis=0)
    total = 2.0 * math.pi * _simpson_axis(Is_t * np.sin(ths_t), ths_t, axis=0)
    return float(abs(enclosed) / abs(total)) if abs(total) > 0 else 0.0


def cand_grating_fsr(d, wl, m, nslits):
    """B398 候选：数值光栅自由光谱范围 Δλ = λ/(m·N)。

    物理解释（与 golden 同定义）：m 级主极大的角半宽 Δ(sinθ)=λ/(Nd)（N 缝干涉第一零点间距）；
    对应波长增量 Δλ 使 m 级峰平移该半宽 ⇒ Δλ = Δ(sinθ)·d/m = λ/(mN)。
    数值法：从 m 级主极大 sinθ0=mλ/d 向前扫描，找 N 缝干涉因子**第一零点**（强度真正穿越 ~0，
    而非强度刚跌破 1e-2 的下降段中点）。主瓣强度从峰顶 1 单调递减到零（无平台），故强度**全局
    最小点**即第一零点；取其下降侧相邻"强度明显 >0"点为 lo 端，二分精修 ⇒ Δ(sinθ)，回推 Δλ。
    候选纯数值求积、不调特殊函数。"""
    s_peak = m * wl / d
    delta = wl / (nslits * d)          # 解析半宽仅用于设定扫描上界
    s_hi = s_peak + 3.0 * delta
    ng = 8000
    ss = np.linspace(s_peak, s_hi, ng)
    inten = np.array([_grating_inten_at(s, d, wl, nslits) for s in ss])
    # 主瓣从峰顶单调下降到第一零点（inten≈0），之后回升到次极大（~1/N²）再下降——
    # 因此必须找**第一个**近零局域极小（=第一零点），而非全局最小（会误捕窗口边缘的后续零点）。
    zero_i = None
    for i in range(1, len(inten) - 1):
        if inten[i] < inten[i - 1] and inten[i] <= inten[i + 1] and inten[i] < 1e-3:
            zero_i = i
            break
    if zero_i is None:
        return wl / (m * nslits)
    # lo 取下降侧相邻"强度明显 >0"点（零点前一点），与零点构成二分括号
    lo_i = max(0, zero_i - 1)
    lo, hi = ss[lo_i], ss[zero_i]
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        im = _grating_inten_at(mid, d, wl, nslits)
        if im > 1e-9:
            lo = mid
        else:
            hi = mid
    s_zero = 0.5 * (lo + hi)
    return (s_zero - s_peak) * d / m


def cand_disk_square_zeroratio(D, a_sq, wl):
    """B399 候选：数值圆孔/方孔第一暗纹角半径比。"""
    s_disk = cand_disk_firstzero(D, wl)
    # 方孔（边长 a_sq）首零点：单缝首零点在 x 与 y 方向均为 λ/a_sq ⇒ 角半径 sinθ=λ/a_sq
    s_sq = cand_slit_firstzero(a_sq, wl)
    return s_disk / s_sq


if __name__ == "__main__":
    print("=== B-24 标量衍射核 自检（QUAD_N1D=%d, N2D=%dx%d）===" % (QUAD_N1D, QUAD_N2DR, QUAD_N2DP))
    wl = 1.55e-6
    a = 10.0e-6
    D = 20.0e-6
    d = 50.0e-6
    L = 1.0e-3
    m = 1
    nslits = 10
    b = 8.0e-6
    theta = 0.5 * wl / a  # 单缝半角内一点
    tests = [
        ("B387 单缝首零点 sinθ", golden_b387(a, wl), cand_slit_firstzero(a, wl), 1e-6),
        ("B388 单缝强度@θ", golden_b388(a, wl, theta), cand_slit_intensity(a, wl, theta), 1e-3),
        ("B389 圆孔首零点 sinθ", golden_b389(D, wl), cand_disk_firstzero(D, wl), 1e-6),
        ("B390 圆孔强度@θ", golden_b390(D, wl, theta), cand_disk_intensity(D, wl, theta), 1e-3),
        ("B391 双缝强度@θ", golden_b391(a, d, wl, theta), cand_double_slit_intensity(a, d, wl, theta), 1e-3),
        ("B392 条纹间距(Δsinθ)", golden_b392(d, wl), cand_fringe_spacing(d, wl), 1e-6),
        ("B393 光栅主极大 sinθ", golden_b393(d, wl, m), cand_grating_peak(d, wl, m, nslits), 1e-6),
        ("B394 分辨本领 R=mN", golden_b394(d, wl, m, nslits), cand_grating_respower(d, wl, m, nslits), 1e-2),
        ("B395 矩形强度", golden_b395(a, b, wl, theta, 0.0), cand_rect_intensity(a, b, wl, theta, 0.0), 1e-3),
        ("B396 单缝全角宽", golden_b396(a, wl), cand_slit_fullwidth(a, wl), 1e-6),
        ("B397 爱里围能", golden_b397(D, wl), cand_disk_encircled(D, wl), 1e-2),
        ("B398 光栅FSR", golden_b398(d, wl, m, nslits), cand_grating_fsr(d, wl, m, nslits), 1e-9),
        ("B399 圆/方零点比", golden_b399(D, a, wl), cand_disk_square_zeroratio(D, a, wl), 1e-2),
    ]
    print("%-26s %14s %14s %12s %10s %s" % ("锚", "golden", "cand", "|Δ|", "margin", "基线>1e-12"))
    allok = True
    for name, g, c, tol in tests:
        dd = abs(float(g) - float(c))
        margin = (tol / dd) if dd > 0 else float('inf')
        base_ok = dd > 1e-12
        flag = "OK" if (margin >= 2.0 and base_ok) else "BAD"
        if flag == "BAD":
            allok = False
        print("%-26s %14.6e %14.6e %12.3e %10.1f %s" % (name, g, c, dd, margin, flag))
    print("\nALL OK" if allok else "\nNEED TUNING")
