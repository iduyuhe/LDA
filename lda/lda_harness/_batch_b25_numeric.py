# -*- coding: utf-8 -*-
"""Batch B-25 独立候选数值核 · 静电学 & 静磁学（有限源库仑 / Biot–Savart 求积）
物理定律族（纯 numpy / scipy · C 级自主 · 零商业依赖）。

设计纪律（同源 B12/B22/B23/B24 的「解析闭式 golden 对拍 方法学不同源独立数值法」）：
  每个锚 = 一个**有限源电磁场闭式** 对拍 一个**库仑势 / Biot–Savart 线·面积分（复合
  Simpson）**候选。与已占族（氢/Morse/Rosen-Morse 的 FD Schrödinger、B11 玻色积分、
  B14 耦合器、B23 旁轴 BPM、B24 衍射积分）**方法学不同源**——本核是*静电/静磁有限源
  的求积*（1D/2D 复合 Simpson 线·面积分），残差 = 求积离散化误差（O(h⁴)，随采样点 N
  收敛、随物理参数变化、判据 D 响应、候选输出扰动必 FAIL），非代数恒等、非噪声地板。

同源体检（whole-repo grep，限定 lda/ 排除三方噪声）：
  biot|savart|magnetic_field|ampere|gauss_law|electric_field|charged_ring|charged_disk|
  line_charge|current_loop|dipole_field|magnetostat|shell_theorem|spherical_shell
  → **No matches**（全仓零命中）。确认静电/静磁有限源族不与任何已占锚同源 ⇒ 开放。

判据 D 铁律（本核须满足）：
  候选是**真数值求积**，默认档基线残差须 ∈ (1e-12, tol)；余量 = tol/|Δ| ≥ 2×。
  平滑被积函数使 Simpson 收敛极快 ⇒ 须用**适中采样 N**（非过密）使残差浮出 1e-12 之上、
  又压在 tol 之下（避免「过度收敛区」盲区）。N 由 truth-check 调定（见底部 QUAD_* 钩子）。

退化陷阱回避（B-24 血案同族）：
  对称源**轴线上**被积函数常为常数 ⇒ 残差沉机器精度 ⇒ 撞判据 D ③ 恒等式地板。
  本核**刻意选用 off-axis / 非对称几何**使被积函数真变化：
    · 带电圆盘 on-axis：环贡献 z/(z²+r²)^{3/2}·r 随 r 变化（非守恒）；
    · 球壳 off-axis：观则点不在轴/球心 ⇒ 距离随 θ,φ 变化；
    · 圆环 off-axis（B409/B412）：φ 积分被积函数随 φ 变化（非守恒）；
    · 所有直导线段（B406/B407/B408/B411）：沿导线距离变化。
  因此全程无「on-axis 圆环常数被积」退化，残差浮于 1e-12 之上。

单位约定：本核吸收常数 KE = 1/(4π ε₀) = 1、MU0 = 1（纯比例缩放，golden 与 cand 同用，
比较有效）。实际物理量由 default_params 给定（SI 量级缩放，无单位依赖）。

Batch B-25 锚清单（13 道，B400–B412，全为严格独立候选，余量均 ≥2×，未放宽任何 tol）：
  静电学（库仑，有限源）：
    B400 带电圆盘轴线场 E(z) = 2πσ(1 − z/√(z²+R²))
    B401 带电圆环（ washer, a..b）轴线场 E(z) = 2πσ(z/√(z²+a²) − z/√(z²+b²))
    B402 有限长线电荷（垂直平分线）场 E = λL/(a√((L/2)²+a²))
    B403 有限长线电荷（端点延伸线）场 E = λL/(a√(L²+a²))
    B404 均匀带电球壳外点场（壳定理 ⇒ 点电荷等价）|E| = Q/(ρ²+z²)
    B405 两平行异号有限线电荷（中点）场 E = 2λL/((d/2)√((L/2)²+(d/2)²))
  静磁学（Biot–Savart，有限电流）：
    B406 有限长直导线（垂直距离 d）磁场 B = I L/(4π d√((L/2)²+d²))
    B407 正方形电流环（中心）磁场 B = 2√2 I/(π a)
    B408 正 N 边形电流环（中心）磁场 B = I N tan(π/N)/(2π R)
    B409 圆形电流环 off-axis 轴向分量 B_z（椭圆积分 K,E 闭式 vs Biot–Savart 求积）
    B410 有限长螺线管（轴线）磁场 B = (nI/2)[(z+L/2)/√(R²+(z+L/2)²) − (z−L/2)/√(R²+(z−L/2)²)]
    B411 两反向平行有限直导线（中点）磁场 B = I L/(π d√((L/2)²+(d/2)²))
    B412 圆形电流环 off-axis 径向分量 B_ρ（椭圆积分 K,E 闭式 vs Biot–Savart 求积）
"""
from __future__ import annotations

import math

import numpy as np
from scipy.special import ellipk, ellipe

# 单位约定：吸收常数使 golden 与 cand 同比例（比较有效）。
KE = 1.0    # 1/(4π ε₀)
MU0 = 1.0   # μ₀

# ===========================================================================
# 求积工具（复合 Simpson；奇数点标准，偶数点末区间梯形）
# ===========================================================================
def _simpson_1d(x: np.ndarray, y: np.ndarray) -> float:
    """复合 Simpson（1D，标量）。奇数点标准 1/3；偶数点前 3 子区间用 3/8 余 1/3。

    注意：早期版本偶数点用「末区间梯形」会丢失交界子区间权重 ⇒ O(h) 误差（仅在对称
    被积函数上巧合收敛）。此处用 3/8+1/3 标准复合 Simpson，偶数点亦达 O(h⁴)。
    """
    n = len(x)
    if n < 3:
        return float(np.trapezoid(y, x))
    h = float(x[1] - x[0])
    yr = np.asarray(y, float)
    if n % 2 == 1:
        w = np.ones(n)
        w[1:n - 1:2] = 4.0
        w[2:n - 1:2] = 2.0
        return float(h / 3.0 * np.dot(w, yr))
    s38 = 3.0 * h / 8.0 * (yr[0] + 3.0 * yr[1] + 3.0 * yr[2] + yr[3])
    rem = yr[3:]
    m = len(rem)
    w = np.ones(m)
    w[1:m - 1:2] = 4.0
    w[2:m - 1:2] = 2.0
    return float(s38 + h / 3.0 * np.dot(w, rem))


def _simpson_axis(y: np.ndarray, x: np.ndarray, axis: int):
    """沿指定轴复合 Simpson（返回该轴积分后的降维数组）。奇数点 1/3；偶数点 3/8+1/3。"""
    n = y.shape[axis]
    h = float(x[1] - x[0])
    if n < 3:
        return h / 2.0 * (np.take(y, 0, axis=axis) + np.take(y, n - 1, axis=axis))
    if n % 2 == 1:
        w = np.ones(n)
        w[1:n - 1:2] = 4.0
        w[2:n - 1:2] = 2.0
        return h / 3.0 * np.tensordot(w, y, axes=(0, axis))
    s38 = 3.0 * h / 8.0 * (np.take(y, 0, axis=axis) + 3.0 * np.take(y, 1, axis=axis)
                           + 3.0 * np.take(y, 2, axis=axis) + np.take(y, 3, axis=axis))
    rem = np.take(y, range(3, n), axis=axis)
    m = n - 3
    w = np.ones(m)
    w[1:m - 1:2] = 4.0
    w[2:m - 1:2] = 2.0
    return s38 + h / 3.0 * np.tensordot(w, rem, axes=(0, axis))


def _biot_straight(p0, p1, I, point, n):
    """有限直导线段 Biot–Savart 向量积分（复合 Simpson 沿 t∈[0,1]）。

    返回 3 向量 B。用于 B406/B407/B408/B411 的线段组合。"""
    p0 = np.asarray(p0, float)
    p1 = np.asarray(p1, float)
    pt = np.asarray(point, float)
    ts = np.linspace(0.0, 1.0, n)
    P = p0[None, :] + ts[:, None] * (p1 - p0)[None, :]
    dl = (p1 - p0)
    r = pt[None, :] - P
    mag = np.sqrt(np.sum(r * r, axis=1))
    cross = np.cross(dl, r)
    integ = (MU0 * I / (4.0 * math.pi)) * cross / (mag ** 3)[:, None]
    return np.array([_simpson_axis(integ[:, k], ts, axis=0) for k in range(3)])


# ===========================================================================
# 求积采样（B-25 调参钩子）：候选读取这些全局以允许外部覆盖 / truth-check 扫描。
# 适中 N ⇒ 残差浮出 1e-12 之上、压在 tol 之下。
# ===========================================================================
# 分档调参（修正 Simpson 后收敛 O(N⁻⁴)，故平滑积分用较小 N 避免沉 1e-12 地板，
# 尖峰积分用较大 N 使残差浮出 1e-12 之上、压在 tol 之下）：
QUAD_N_DISK = 80      # 圆盘/圆环（平滑 1D，N 过大即沉地板）
QUAD_N1D = 300        # 尖峰 1D（线电荷/单导线/螺线管/双线，收敛较慢）
QUAD_N_THETA = 301    # 球壳 2D Simpson（θ）
QUAD_N_PHI = 301      # 球壳 2D Simpson（φ）
QUAD_N_SEG = 40       # 直导线段（B407/B408/B411，平滑）
QUAD_N_PHI_LOOP = 200  # 圆环 off-axis 1D 环绕 Simpson（B409/B412）


# ===========================================================================
# 闭式 golden（与数值求积候选方法学不同源）
# ===========================================================================
def golden_b400(R, sigma, z):
    """带电圆盘轴线场 E(z) = 2πσ(1 − z/√(z²+R²))（z>0）。"""
    return 2.0 * math.pi * sigma * (1.0 - z / math.sqrt(z * z + R * R))


def golden_b401(a, b, sigma, z):
    """带电圆环（washer, 内 a 外 b）轴线场 E(z) = 2πσ(z/√(z²+a²) − z/√(z²+b²))（b>a, z>0）。"""
    return 2.0 * math.pi * sigma * (z / math.sqrt(z * z + a * a) - z / math.sqrt(z * z + b * b))


def golden_b402(L, lam, a):
    """有限长线电荷（垂直平分线）场 E = λL/(a·√((L/2)²+a²))。"""
    return lam * L / (a * math.sqrt((L / 2.0) ** 2 + a * a))


def golden_b403(L, lam, a):
    """有限长线电荷（端点延伸线，垂足在一端）场 E = λL/(a·√(L²+a²))。"""
    return lam * L / (a * math.sqrt(L * L + a * a))


def golden_b404(R, Q, rho, z):
    """均匀带电球壳外点场（壳定理 ⇒ 点电荷等价）|E| = KE·Q/(ρ²+z²)。"""
    r2 = rho * rho + z * z
    return KE * Q / r2


def golden_b405(L, lam, d):
    """两平行异号有限线电荷（中点）场 E = 2·λL/((d/2)·√((L/2)²+(d/2)²))。"""
    return 2.0 * lam * L / ((d / 2.0) * math.sqrt((L / 2.0) ** 2 + (d / 2.0) ** 2))


def golden_b406(L, I, d):
    """有限长直导线（垂直距离 d）磁场 B_z = I L/(4π d√((L/2)²+d²))。"""
    return I * L / (4.0 * math.pi * d * math.sqrt((L / 2.0) ** 2 + d * d))


def golden_b407(a, I):
    """正方形电流环（中心）磁场 B = 2√2 I/(π a)。"""
    return 2.0 * math.sqrt(2.0) * I / (math.pi * a)


def golden_b408(N, R, I):
    """正 N 边形电流环（中心，外接半径 R）磁场 B = I N tan(π/N)/(2π R)。"""
    return I * N * math.tan(math.pi / N) / (2.0 * math.pi * R)


def golden_b409(R, I, rho, z):
    """圆形电流环 off-axis 轴向分量 B_z（椭圆积分 K,E 闭式）。

    k² = 4Rρ/((R+ρ)²+z²)；B_z = (μ₀I/2π)·1/√((R+ρ)²+z²)·
         [K(k) + (R²−ρ²−z²)/((R−ρ)²+z²)·E(k)]。
    golden 用 ellipk/ellipe（特殊函数），与候选 Simpson 求积方法学不同源。"""
    k2 = 4.0 * R * rho / ((R + rho) ** 2 + z * z)
    Kk = ellipk(k2)
    Ek = ellipe(k2)
    denom = math.sqrt((R + rho) ** 2 + z * z)
    bracket = Kk + ((R * R - rho * rho - z * z) / ((R - rho) ** 2 + z * z)) * Ek
    return (MU0 * I / (2.0 * math.pi)) * bracket / denom


def golden_b410(L, R, n, I, z):
    """有限长螺线管（轴线）磁场 B = (nI/2)[(z+L/2)/√(R²+(z+L/2)²) − (z−L/2)/√(R²+(z−L/2)²)]。"""
    f1 = (z + L / 2.0) / math.sqrt(R * R + (z + L / 2.0) ** 2)
    f2 = (z - L / 2.0) / math.sqrt(R * R + (z - L / 2.0) ** 2)
    return (MU0 * n * I / 2.0) * (f1 - f2)


def golden_b411(L, I, d):
    """两反向平行有限直导线（中点）磁场 B = I L/(π d√((L/2)²+(d/2)²))（两导线各距 d/2）。"""
    return I * L / (math.pi * d * math.sqrt((L / 2.0) ** 2 + (d / 2.0) ** 2))


def golden_b412(R, I, rho, z):
    """圆形电流环 off-axis 径向分量 B_ρ（椭圆积分 K,E 闭式）。

    B_ρ = (μ₀I z)/(2π ρ)·1/√((R+ρ)²+z²)·[−K(k) + (R²+ρ²+z²)/((R−ρ)²+z²)·E(k)]。
    观点在 (ρ,0,z)（x 轴方向为径向），golden 给出有符号 B_ρ，cand 取 B_x 对拍。"""
    k2 = 4.0 * R * rho / ((R + rho) ** 2 + z * z)
    Kk = ellipk(k2)
    Ek = ellipe(k2)
    denom = math.sqrt((R + rho) ** 2 + z * z)
    bracket = -Kk + ((R * R + rho * rho + z * z) / ((R - rho) ** 2 + z * z)) * Ek
    return (MU0 * I * z / (2.0 * math.pi * rho)) * bracket / denom


# ===========================================================================
# 数值求积候选（方法学不同源）
# ===========================================================================
def cand_disk(R, sigma, z):
    """B400 候选：数值积分带电圆盘环贡献（Simpson 1D over r）。"""
    rs = np.linspace(0.0, R, QUAD_N_DISK)
    integ = 2.0 * math.pi * sigma * z * rs / (z * z + rs * rs) ** 1.5
    return float(_simpson_1d(rs, integ))


def cand_washer(a, b, sigma, z):
    """B401 候选：数值积分带电圆环（a..b, Simpson 1D over r）。"""
    rs = np.linspace(a, b, QUAD_N_DISK)
    integ = 2.0 * math.pi * sigma * z * rs / (z * z + rs * rs) ** 1.5
    return float(_simpson_1d(rs, integ))


def cand_line_bisector(L, lam, ad):
    """B402 候选：数值积分有限长线电荷垂直平分线 y 分量（Simpson 1D over x）。"""
    xs = np.linspace(-L / 2.0, L / 2.0, QUAD_N1D)
    integ = lam * ad / (xs * xs + ad * ad) ** 1.5
    return float(_simpson_1d(xs, integ))


def cand_line_endon(L, lam, ad):
    """B403 候选：数值积分有限长线电荷（端点延伸线）y 分量（Simpson 1D over x∈[0,L]）。"""
    xs = np.linspace(0.0, L, QUAD_N1D)
    integ = lam * ad / (xs * xs + ad * ad) ** 1.5
    return float(_simpson_1d(xs, integ))


def cand_shell(R, Q, rho, z):
    """B404 候选：数值积分均匀带电球壳外点场（2D Simpson over θ,φ），返回 |E|。

    off-axis 观点 (ρ,0,z) ⇒ 距离随 θ,φ 变化（非轴/球心对称 ⇒ 被积函数真变化，
    无退化）。候选全程不调特殊函数 ⇒ 方法学独立。"""
    thetas = np.linspace(0.0, math.pi, QUAD_N_THETA)
    phis = np.linspace(0.0, 2.0 * math.pi, QUAD_N_PHI)
    TH, PH = np.meshgrid(thetas, phis, indexing="ij")
    sx = R * np.sin(TH) * np.cos(PH)
    sy = R * np.sin(TH) * np.sin(PH)
    sz = R * np.cos(TH)
    rx = rho - sx
    ry = 0.0 - sy
    rz = z - sz
    rmag = np.sqrt(rx * rx + ry * ry + rz * rz)
    dq = (Q / (4.0 * math.pi)) * np.sin(TH)  # = σ dA 系数（R² 抵消）
    Ex = KE * dq * rx / rmag ** 3
    Ey = KE * dq * ry / rmag ** 3
    Ez = KE * dq * rz / rmag ** 3
    Ex_t = _simpson_axis(Ex, phis, axis=1)
    Ey_t = _simpson_axis(Ey, phis, axis=1)
    Ez_t = _simpson_axis(Ez, phis, axis=1)
    Ex_i = _simpson_axis(Ex_t, thetas, axis=0)
    Ey_i = _simpson_axis(Ey_t, thetas, axis=0)
    Ez_i = _simpson_axis(Ez_t, thetas, axis=0)
    return float(math.sqrt(Ex_i ** 2 + Ey_i ** 2 + Ez_i ** 2))


def cand_twoline(L, lam, d):
    """B405 候选：数值积分两平行异号有限线电荷（中点）y 分量（Simpson 1D）。"""
    xs = np.linspace(-L / 2.0, L / 2.0, QUAD_N1D)
    # 导线1 (+λ 在 y=+d/2)：y 分量 = -λ (d/2)/(x²+(d/2)²)^{3/2}
    integ1 = -lam * (d / 2.0) / (xs * xs + (d / 2.0) ** 2) ** 1.5
    # 导线2 (-λ 在 y=-d/2)：y 分量同向（均指向 -y）
    integ2 = -lam * (d / 2.0) / (xs * xs + (d / 2.0) ** 2) ** 1.5
    return float(abs(_simpson_1d(xs, integ1) + _simpson_1d(xs, integ2)))


def cand_wire(L, I, d):
    """B406 候选：数值积分有限长直导线（垂直距离 d）B_z（Simpson 1D over x）。"""
    xs = np.linspace(-L / 2.0, L / 2.0, QUAD_N1D)
    integ = (MU0 * I / (4.0 * math.pi)) * d / (xs * xs + d * d) ** 1.5
    return float(_simpson_1d(xs, integ))


def cand_square(a, I):
    """B407 候选：数值积分正方形电流环（4 边 Biot–Savart Simpson）B_z。"""
    h = a / 2.0
    verts = [(-h, -h, 0.0), (h, -h, 0.0), (h, h, 0.0), (-h, h, 0.0)]
    B = np.zeros(3)
    for k in range(4):
        p0 = verts[k]
        p1 = verts[(k + 1) % 4]
        B = B + _biot_straight(p0, p1, I, (0.0, 0.0, 0.0), QUAD_N_SEG)
    return float(abs(B[2]))


def cand_polygon(N, R, I):
    """B408 候选：数值积分正 N 边形电流环（N 边 Biot–Savart Simpson）B_z。"""
    verts = [(R * math.cos(2.0 * math.pi * k / N),
              R * math.sin(2.0 * math.pi * k / N), 0.0) for k in range(N)]
    B = np.zeros(3)
    for k in range(N):
        p0 = verts[k]
        p1 = verts[(k + 1) % N]
        B = B + _biot_straight(p0, p1, I, (0.0, 0.0, 0.0), QUAD_N_SEG)
    return float(abs(B[2]))


def cand_loop_Bz(R, I, rho, z):
    """B409 候选：数值积分圆形电流环 off-axis 轴向分量 B_z（Simpson 1D over φ）。

    参数化环 (R cosφ, R sinφ, 0)，观点 (ρ,0,z)；dB_z 系数 = R²−Rρ cosφ。
    被积函数随 φ 变化（off-axis）⇒ Simpson 真离散化误差；候选不调 K/E 特殊函数 ⇒ 独立。"""
    phis = np.linspace(0.0, 2.0 * math.pi, QUAD_N_PHI_LOOP)
    cphi = np.cos(phis)
    sphi = np.sin(phis)
    rx = rho - R * cphi
    ry = -R * sphi
    rmag = np.sqrt(rx * rx + ry * ry + z * z)
    dz = (R * R - R * rho * cphi)
    integ = (MU0 * I / (4.0 * math.pi)) * dz / rmag ** 3
    return float(_simpson_1d(phis, integ))


def cand_solenoid(L, R, n, I, z):
    """B410 候选：数值积分有限长螺线管（轴线）B_z（Simpson 1D over z' 堆叠环）。"""
    zps = np.linspace(-L / 2.0, L / 2.0, QUAD_N1D)
    integ = (MU0 * n * I * R * R / 2.0) / (R * R + (z - zps) ** 2) ** 1.5
    return float(_simpson_1d(zps, integ))


def cand_twowire(L, I, d):
    """B411 候选：数值积分两反向平行有限直导线（中点）B_z（各距 d/2，Simpson 1D）。"""
    xs = np.linspace(-L / 2.0, L / 2.0, QUAD_N1D)
    integ = (MU0 * I / (4.0 * math.pi)) * (d / 2.0) / (xs * xs + (d / 2.0) ** 2) ** 1.5
    # 两导线反向平行 ⇒ 中点 B_z 同向叠加（取绝对值）
    return float(2.0 * abs(_simpson_1d(xs, integ)))


def cand_loop_Brho(R, I, rho, z):
    """B412 候选：数值积分圆形电流环 off-axis 径向分量 B_ρ（= B_x，观点在 x 轴；Simpson 1D over φ）。

    dB_x 系数 = R z cosφ。被积函数随 φ 变化 ⇒ Simpson 真离散化误差；候选不调 K/E ⇒ 独立。
    返回有符号 B_x（与 golden 有符号 B_ρ 对拍）。"""
    phis = np.linspace(0.0, 2.0 * math.pi, QUAD_N_PHI_LOOP)
    cphi = np.cos(phis)
    sphi = np.sin(phis)
    rx = rho - R * cphi
    ry = -R * sphi
    rmag = np.sqrt(rx * rx + ry * ry + z * z)
    dx = R * cphi * z
    integ = (MU0 * I / (4.0 * math.pi)) * dx / rmag ** 3
    return float(_simpson_1d(phis, integ))


if __name__ == "__main__":
    print("=== B-25 静电/静磁有限源核 自检（N1D=%d, Nθ×Nφ=%dx%d, Nseg=%d, Nloop=%d）==="
          % (QUAD_N1D, QUAD_N_THETA, QUAD_N_PHI, QUAD_N_SEG, QUAD_N_PHI_LOOP))
    R = 0.05
    sigma = 1.0
    z = 0.10
    a_in = 0.03
    b_out = 0.08
    L = 0.20
    lam = 1.0
    ad = 0.04
    Q = 1.0
    rho = 0.02
    d = 0.04
    I = 1.0
    N = 6
    Rp = 0.10
    zl = 0.05
    n = 100.0
    Rsol = 0.05
    Lsol = 0.30
    tests = [
        ("B400 圆盘轴线E", golden_b400(R, sigma, z), cand_disk(R, sigma, z), 1e-6),
        ("B401 圆环轴线E", golden_b401(a_in, b_out, sigma, z), cand_washer(a_in, b_out, sigma, z), 1e-6),
        ("B402 线电荷平分E", golden_b402(L, lam, ad), cand_line_bisector(L, lam, ad), 1e-6),
        ("B403 线电荷端E", golden_b403(L, lam, ad), cand_line_endon(L, lam, ad), 1e-5),
        ("B404 球壳外点E", golden_b404(R, Q, rho, z), cand_shell(R, Q, rho, z), 1e-3),
        ("B405 两线电荷E", golden_b405(L, lam, d), cand_twoline(L, lam, d), 1e-6),
        ("B406 直导线B", golden_b406(L, I, d), cand_wire(L, I, d), 1e-6),
        ("B407 方环B", golden_b407(0.10, I), cand_square(0.10, I), 1e-3),
        ("B408 多边形环B", golden_b408(N, Rp, I), cand_polygon(N, Rp, I), 1e-3),
        ("B409 环offaxis_Bz", golden_b409(R, I, rho, zl), cand_loop_Bz(R, I, rho, zl), 1e-6),
        ("B410 螺线管B", golden_b410(Lsol, Rsol, n, I, zl), cand_solenoid(Lsol, Rsol, n, I, zl), 1e-5),
        ("B411 两导线B", golden_b411(L, I, d), cand_twowire(L, I, d), 1e-6),
        ("B412 环offaxis_Bρ", golden_b412(R, I, rho, zl), cand_loop_Brho(R, I, rho, zl), 1e-6),
    ]
    print("%-22s %14s %14s %12s %10s %s" % ("锚", "golden", "cand", "|Δ|", "margin", "基线>1e-12"))
    allok = True
    for name, g, c, tol in tests:
        dd = abs(float(g) - float(c))
        margin = (tol / dd) if dd > 0 else float('inf')
        base_ok = dd > 1e-12
        flag = "OK" if (margin >= 2.0 and base_ok) else "BAD"
        if flag == "BAD":
            allok = False
        print("%-22s %14.6e %14.6e %12.3e %10.1f %s" % (name, g, c, dd, margin, flag))
    print("\nALL OK" if allok else "\nNEED TUNING")
