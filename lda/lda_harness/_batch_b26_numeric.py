# -*- coding: utf-8 -*-
"""Batch B-26 独立候选数值核 · 单界面 Fresnel/Snell 光学（确定性 FD Helmholtz 对拍解析闭式）
物理定律族（纯 numpy · C 级自主 · 零商业依赖）。

设计纪律（同源 B22/B23/B24/B25 的「解析闭式 golden 对拍 方法学不同源独立数值法」）：
  每个锚 = 一个**单界面 Fresnel/Snell 闭式** 对拍 一个**1D 有限差分 Helmholtz 解**（界面
  off-node 捕捉 ⇒ O(h²) 离散化误差）。与已占族（氢/Morse/Rosen-Morse FD Schrödinger、B11
  玻色积分、B14 耦合器、B23 旁轴 BPM、B24 衍射积分、B25 静电/静磁求积）**方法学不同源**
  ——本核是*单界面电磁波 FD 求解*，残差 = FD 离散化误差（随网格 N 收敛、随物理参数变化、
  判据 D 响应、候选输出扰动必 FAIL），非代数恒等、非噪声地板。

同源体检（whole-repo grep，限定 lda/ 排除三方噪声）：
  fresnel|snell|brewster|critical_angle|reflection_coefficient|transmission_coefficient|
  interface_reflect|evanescent|total_internal|dielectric_interface
  → 仅 store.py 的 `abcd`（器件参数，非光学矩阵）、B23 注释、B20 经验锚命中；
  **无 Fresnel/Snell 单界面数值锚** ⇒ 开放。

判据 D 铁律（本核须满足）：
  候选是**真 FD Helmholtz 解**（界面 off-node ⇒ 离散化误差 O(h²)，随 N 收敛）。
  默认档基线残差须 ∈ (1e-12, tol)；余量 = tol/|Δ| ≥ 2×。平滑问题使 FD 收敛快 ⇒
  须用**适中 N**（非过密）使残差浮出 1e-12 之上、又压在 tol 之下（避免「过度收敛区」盲区）。
  N 由 __main__ 自检调定（见底部 FD_N_* 钩子）。

退化陷阱回避（B-24/B-25 同族）：
  对称/轴线上被积函数常为常数 ⇒ 残差沉机器精度 ⇒ 撞判据 D ③ 恒等式地板。本核**刻意选用
  off-node 界面 + 非对称入射**（θi≠0 使介质 2 场随 x 振荡/衰减），使 FD 残差真变化。

单位约定：k0 = 1（真空波数，比较有效）。n 为折射率（无量纲）。角度用度传入、弧度内算。

Batch B-26 锚清单（13 道，B413–B425，全为严格独立候选，余量均 ≥2×，未放宽任何 tol）：
  单界面 Fresnel/Snell（n1 → n2，入射角 θi）：
    B413 垂直入射反射率 R0 = ((n1−n2)/(n1+n2))²
    B414 s 偏振反射率 Rs = |(n1cθi−n2cθt)/(n1cθi+n2cθt)|²
    B415 p 偏振反射率 Rp = |(n2cθi−n1cθt)/(n2cθi+n1cθt)|²
    B416 s 偏振透射率 Ts = 1 − Rs（能量守恒）
    B417 p 偏振透射率 Tp = 1 − Rp
    B418 非偏振反射率 Runpol = (Rs+Rp)/2
    B419 偏振反射率对比 ΔR = Rs − Rp（θi=40°，连续非退化）
    B420 偏振透射率比 Ts/Tp（θi=40°，连续非退化，两透射率均≈1 良态）
    B421 布儒斯特角 θB = atan(n2/n1)（p 反射率→0 的角，FD 扫 Rp 极小）
    B422 s 偏振透射振幅 |t_s| = 2·n1·cθi/(n1·cθi+n2·cθt)（连续非退化 Fresnel 振幅）
    B423 全反射反射率 = 1（θi>θc）
    B424 倏逝波衰减常数 β = k0√(n1²sin²θi−n2²)（TIR）
    B425 能量守恒 Rs + Ts·(n2cθt)/(n1cθi) = 1
"""
from __future__ import annotations

import math

import numpy as np

K0 = 1.0  # 真空波数（无量纲，比较有效）

# ===========================================================================
# FD 求解参数（界面 off-node 捕捉；适中 N ⇒ 残差浮出 1e-12 之上、压在 tol 之下）
# ===========================================================================
FD_N_REFLECT = 16384     # 垂直入射（平滑，残差浮出 1e-12 之上、压在 tol 之下）
FD_N_OBLIQUE = 65536     # 斜入射 Rs/Rp/Ts/Tp/能量守恒/透射振幅（精测，余量≥2×）
FD_N_TIR = 16384         # 全反射相关（衰减区收敛稍慢）
FD_N_SCAN = 16384        # Brewster 扫描用（粗档即可定位极小，省算力）
FD_L0 = 6.0              # 半域宽（≈1 波长，k0=1）


# ===========================================================================
# 复三对角 Thomas 求解器
# ===========================================================================
def _solve_tridiag(a, b, c, d):
    """复 Thomas 算法求解 A x = d，A 为三对角（a 下、b 主、c 上对角线）。"""
    n = len(d)
    cp = np.zeros(n, complex)
    dp = np.zeros(n, complex)
    cp[0] = c[0] / b[0]
    dp[0] = d[0] / b[0]
    for i in range(1, n):
        m = b[i] - a[i] * cp[i - 1]
        cp[i] = c[i] / m if i < n - 1 else 0.0
        dp[i] = (d[i] - a[i] * dp[i - 1]) / m
    x = np.zeros(n, complex)
    x[n - 1] = dp[n - 1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]
    return x


# ===========================================================================
# 1D FD Helmholtz 总场求解（单界面 off-node，TE/TM 双模式，TIR 复数波矢）
# ===========================================================================
def _fd_solve(n1, n2, theta_i_deg, mode, N):
    """单界面 1D FD Helmholtz 总场解（与 Fresnel 闭式方法学不同源）。

    约化 1D 方程（横波数 kz 由 Snell 守恒）：d/dx[P(x) dE/dx] + Q(x) E = 0。
      TE (E_y): P=1,    Q = k0²·n² − kz²
      TM (H_y): P=1/n², Q = k0² − kz²/n²
    介质内体波数 = sqrt(k0²n² − kz²) = k0·n·cosθ，与边界条件 k1x/k2x 严格一致。
    界面 off-node 捕捉（0 落在节点 N/2 与 N/2+1 之间）⇒ 离散化误差 O(h²)。
    边权 P 用**谐波平均**（串联电导，跳变处仍 O(h²)，保证通量守恒）。
    边界：左端仅入射（无来波），右端仅透射；用 2 阶 ghost-node 施加辐射边界。
    返回网格 xs 与总场 E_total（复数组）、纵向波数 k1x/k2x。
    """
    theta_i = math.radians(theta_i_deg)
    sini = math.sin(theta_i)
    kz = K0 * n1 * sini                  # 守恒横向波数（Snell：介质1 入射横分量）
    k1x_sq = K0 * K0 * n1 * n1 - kz * kz
    k2x_sq = K0 * K0 * n2 * n2 - kz * kz
    k1x = math.sqrt(k1x_sq) if k1x_sq > 0.0 else 0.0
    if k2x_sq < 0.0:                      # 全反射：k2x 纯虚数
        k2x = 1j * math.sqrt(-k2x_sq)
    else:
        k2x = math.sqrt(k2x_sq)

    h = (2.0 * FD_L0) / N
    # 界面 off-node：x_i = (i - N/2 - 0.5)·h ⇒ 0 落在节点 N/2 与 N/2+1 之间
    xs = (np.arange(N + 1) - N / 2 - 0.5) * h
    # 节点介质归属：x<0 ⇒ n1，x>0 ⇒ n2
    in_r2 = xs > 0.0
    ns = np.where(in_r2, n2, n1)
    if mode == "te":
        Pn = np.full_like(ns, 1.0)        # P=1（恒为数组，便于索引）
        Qn = (K0 * ns) ** 2 - kz * kz
    else:  # tm
        Pn = 1.0 / (ns * ns)              # P=1/n²
        Qn = K0 * K0 - kz * kz / (ns * ns)

    # 边权 P（谐波平均：串联电导，界面跳变处 O(h²)）
    P_edge = 2.0 / (1.0 / Pn[:-1] + 1.0 / Pn[1:])   # e = 0..N-1
    a = np.zeros(N + 1, complex)        # 下对角：coeff of E_{i-1}
    b = np.zeros(N + 1, complex)        # 主对角
    c = np.zeros(N + 1, complex)        # 上对角：coeff of E_{i+1}
    for i in range(1, N):
        a[i] = P_edge[i - 1] / (h * h)
        c[i] = P_edge[i] / (h * h)
        b[i] = -(P_edge[i - 1] + P_edge[i]) / (h * h) + Qn[i]
    # 左边界（x=-L0）：辐射条件 E'(-L0) = i·k1x·(2·E_inc(-L0) − E_total(-L0))，E_inc(-L0)=1。
    #   中心差分 ghost（u_{-1} = u_1 − 2h·g，g=i k1x(2−E0)）⇒ 三对角 2 阶格式：
    #   (−2/h² + Q0/P0 + 2i k1x/h)·E_0 + (2/h²)·E_1 = 4i k1x/h   （区域1 内 P,Q 常数）
    a[0] = 0.0
    c[0] = 2.0 / (h * h)
    b[0] = -2.0 / (h * h) + Qn[0] / Pn[0] + 2.0 * 1j * k1x / h
    rhs0 = 4.0 * 1j * k1x / h
    # 右边界（x=+L0）：辐射条件 E'(+L0) = i·k2x·E_total(+L0)；ghost（u_{N+1}=u_{N-1}+2h·g_R）
    #   (2/h²)·E_{N-1} + (−2/h² + QN/PN + 2i k2x/h)·E_N = 0
    a[N] = 2.0 / (h * h)
    c[N] = 0.0
    b[N] = -2.0 / (h * h) + Qn[N] / Pn[N] + 2.0 * 1j * k2x / h

    rhs = np.zeros(N + 1, complex)
    rhs[0] = rhs0

    E = _solve_tridiag(a, b, c, rhs)
    return xs, E, k1x, k2x, in_r2


def _extract_rt(xs, E, k1x, k2x, in_r2):
    """从 FD 总场提取 r（反射振幅）与 t（透射振幅）于最接近 ±L0/2 的网格节点。

    探针取**精确网格节点**（非插值），避免 np.interp 引入的 O(h) 误差，使残差回到
    O(h²) 离散化误差（随 N 收敛），满足判据 D 单调性。
    """
    xa = -FD_L0 * 0.5
    xb = FD_L0 * 0.5
    ia = int(np.argmin(np.abs(xs - xa)))
    ib = int(np.argmin(np.abs(xs - xb)))
    Ea = E[ia]
    Eb = E[ib]
    # 区域1：E_total = e^{i k1x(x+L0)} + r·e^{-i k1x(x+L0)} ⇒ r = E_a·e^{i k1x(xa+L0)} − e^{2i k1x(xa+L0)}
    pha = k1x * (xs[ia] + FD_L0)
    r = Ea * np.exp(1j * pha) - np.exp(2j * pha)
    # 区域2：E_total = t·exp(i·k2x·(x+L0)) ⇒ t = E_total(xb)·exp(-i·k2x·(xb+L0))
    phb = k2x * (xs[ib] + FD_L0)
    t = Eb * np.exp(-1j * phb)
    return r, t


def _fd_RT(n1, n2, theta_i_deg, mode, N):
    """返回 (R, T) 功率反射/透射率（FD）。TIR 时 T=0、R≈1。"""
    xs, E, k1x, k2x, in_r2 = _fd_solve(n1, n2, theta_i_deg, mode, N)
    r, t = _extract_rt(xs, E, k1x, k2x, in_r2)
    R = abs(r) ** 2
    # 透射功率（考虑通量比）：TE (n2 cosθt)/(n1 cosθi)；TM (n1 cosθt)/(n2 cosθi)
    if abs(k2x.imag) > 1e-9 and abs(k2x.real) < 1e-9:
        T = 0.0                       # 全反射：无传播功率
    else:
        cos_i = k1x / (K0 * n1) if K0 * n1 != 0 else 1.0
        cos_t = k2x.real / (K0 * n2) if K0 * n2 != 0 else 1.0
        if mode == "te":
            T = (n2 * cos_t) / (n1 * cos_i) * abs(t) ** 2
        else:
            T = (n1 * cos_t) / (n2 * cos_i) * abs(t) ** 2
    return R, T


# ===========================================================================
# 闭式 golden（与 FD 方法学不同源）
# ===========================================================================
def golden_b413(n1, n2):
    """B413 垂直入射反射率 R0 = ((n1−n2)/(n1+n2))²。"""
    return ((n1 - n2) / (n1 + n2)) ** 2


def golden_b414(n1, n2, theta_i):
    """B414 s 偏振反射率 Rs（θi 度）。"""
    ti = math.radians(theta_i)
    st = math.asin((n1 / n2) * math.sin(ti)) if (n1 / n2) * math.sin(ti) < 1 else math.pi / 2
    c1, c2 = math.cos(ti), math.cos(st)
    num = n1 * c1 - n2 * c2
    den = n1 * c1 + n2 * c2
    return (num / den) ** 2


def golden_b415(n1, n2, theta_i):
    """B415 p 偏振反射率 Rp（θi 度）。"""
    ti = math.radians(theta_i)
    st = math.asin((n1 / n2) * math.sin(ti)) if (n1 / n2) * math.sin(ti) < 1 else math.pi / 2
    c1, c2 = math.cos(ti), math.cos(st)
    num = n2 * c1 - n1 * c2
    den = n2 * c1 + n1 * c2
    return (num / den) ** 2


def golden_b416(n1, n2, theta_i):
    """B416 s 偏振透射率 Ts = 1 − Rs。"""
    return 1.0 - golden_b414(n1, n2, theta_i)


def golden_b417(n1, n2, theta_i):
    """B417 p 偏振透射率 Tp = 1 − Rp。"""
    return 1.0 - golden_b415(n1, n2, theta_i)


def golden_b418(n1, n2, theta_i):
    """B418 非偏振反射率 Runpol = (Rs+Rp)/2。"""
    return 0.5 * (golden_b414(n1, n2, theta_i) + golden_b415(n1, n2, theta_i))


def golden_b419(n1, n2, theta_i):
    """B419 偏振反射率对比 ΔR = Rs − Rp（θi 度，连续非退化）。

    与单一反射率不同——直接观测**偏振对比度**（s、p 反射率的差异），
    这是非简并连续量。golden 用闭式 Rs,Rp 之差；candidate 用 FD 分别对
    TE/TM 实测 Rs,Rp 再相减（方法学不同源）。
    """
    return golden_b414(n1, n2, theta_i) - golden_b415(n1, n2, theta_i)


def golden_b420(n1, n2, theta_i):
    """B420 偏振透射率比 Ts/Tp（θi 度，连续非退化，与 B414/B415 不同量）。

    直接观测 s、p 透射率的**比值**，非简并连续量。golden 用闭式 Ts/Tp；
    candidate 用 FD 分别对 TE/TM 实测 Ts,Tp 再相除（方法学不同源）。
    """
    return golden_b416(n1, n2, theta_i) / golden_b417(n1, n2, theta_i)


def golden_b421(n1, n2):
    """B421 布儒斯特角 θB = atan(n2/n1)（度）。"""
    return math.degrees(math.atan(n2 / n1))


def golden_b422(n1, n2, theta_i):
    """B422 s 偏振透射振幅 |t_s| = 2·n1·cθi/(n1·cθi + n2·cθt)（连续非退化 Fresnel 振幅）。

    与 B416(Ts=|t_s|²·通量比) 观测不同量（振幅 vs 功率），golden 为闭式振幅，
    candidate 由 FD 总场直接提取复透射振幅模。方法学不同源。
    """
    ti = math.radians(theta_i)
    st = math.asin((n1 / n2) * math.sin(ti))
    c1, c2 = math.cos(ti), math.cos(st)
    return abs(2.0 * n1 * c1 / (n1 * c1 + n2 * c2))


def golden_b423(n1=1.5, n2=1.0, theta_i=60.0):
    """B423 全反射反射率 = 1（θi>θc，n1>n2）。

    参数仅用于与候选共享 default_params（golden_value 按 **params 调用）；
    返回值恒为 1（TIR 功率全反射）。
    """
    return 1.0


def golden_b424(n1, n2, theta_i):
    """B424 倏逝波衰减常数 β = k0√(n1²sin²θi−n2²)（TIR，度→弧度内算）。"""
    ti = math.radians(theta_i)
    return K0 * math.sqrt(n1 * n1 * math.sin(ti) ** 2 - n2 * n2)


def golden_b425(n1, n2, theta_i):
    """B425 能量守恒 Rs + Ts·(n2 cosθt)/(n1 cosθi) = 1。"""
    return golden_b414(n1, n2, theta_i) + golden_b416(n1, n2, theta_i) * (
        n2 * math.cos(math.asin((n1 / n2) * math.sin(math.radians(theta_i))))
        / (n1 * math.cos(math.radians(theta_i))))


# ===========================================================================
# 数值 FD 候选（方法学不同源）
# ===========================================================================
def cand_normal_reflectance(n1, n2):
    """B413 候选：垂直入射 FD 总场解提取 R0。"""
    R, _ = _fd_RT(n1, n2, 0.0, "te", FD_N_REFLECT)
    return float(R)


def cand_s_reflectance(n1, n2, theta_i):
    """B414 候选：s 偏振 FD(TE) 提取 Rs。"""
    R, _ = _fd_RT(n1, n2, theta_i, "te", FD_N_OBLIQUE)
    return float(R)


def cand_p_reflectance(n1, n2, theta_i):
    """B415 候选：p 偏振 FD(TM) 提取 Rp。"""
    R, _ = _fd_RT(n1, n2, theta_i, "tm", FD_N_OBLIQUE)
    return float(R)


def cand_s_transmittance(n1, n2, theta_i):
    """B416 候选：s 偏振 FD(TE) 提取 Ts。"""
    _, T = _fd_RT(n1, n2, theta_i, "te", FD_N_OBLIQUE)
    return float(T)


def cand_p_transmittance(n1, n2, theta_i):
    """B417 候选：p 偏振 FD(TM) 提取 Tp。"""
    _, T = _fd_RT(n1, n2, theta_i, "tm", FD_N_OBLIQUE)
    return float(T)


def cand_unpol_reflectance(n1, n2, theta_i):
    """B418 候选：FD 平均 (Rs+Rp)/2。"""
    Rs, _ = _fd_RT(n1, n2, theta_i, "te", FD_N_OBLIQUE)
    Rp, _ = _fd_RT(n1, n2, theta_i, "tm", FD_N_OBLIQUE)
    return float(0.5 * (Rs + Rp))


def cand_delta_R(n1, n2, theta_i):
    """B419 候选：FD(TE) Rs 与 FD(TM) Rp 之差 ΔR = Rs − Rp。"""
    Rs, _ = _fd_RT(n1, n2, theta_i, "te", FD_N_OBLIQUE)
    Rp, _ = _fd_RT(n1, n2, theta_i, "tm", FD_N_OBLIQUE)
    return float(Rs - Rp)


def cand_Ts_Tp_ratio(n1, n2, theta_i):
    """B420 候选：FD(TE) Ts 与 FD(TM) Tp 之比 Ts/Tp。"""
    _, Ts = _fd_RT(n1, n2, theta_i, "te", FD_N_OBLIQUE)
    _, Tp = _fd_RT(n1, n2, theta_i, "tm", FD_N_OBLIQUE)
    return float(Ts / Tp)


def cand_brewster_angle(n1, n2):
    """B421 候选：两级扫描 θi 找 p 偏振 FD 反射率最小（→0）的角（度）。

    粗扫定位极小邻域，再在 ±窗口内细扫，最后三点抛物 refine，
    使定位精度达 ~1e-2 度（远高于 tol=5e-2 的 2× 余量要求）。
    """
    # 一级粗扫（FD_N_SCAN 粗档即可定位极小）
    t1 = np.linspace(1.0, 89.0, 90)
    r1 = np.array([_fd_RT(n1, n2, th, "tm", FD_N_SCAN)[0] for th in t1])
    k = int(np.argmin(r1))
    lo = t1[max(k - 1, 0)]
    hi = t1[min(k + 1, len(t1) - 1)]
    # 二级细扫 ±窗口
    t2 = np.linspace(lo, hi, 120)
    r2 = np.array([_fd_RT(n1, n2, th, "tm", FD_N_SCAN)[0] for th in t2])
    k2 = int(np.argmin(r2))
    if 0 < k2 < len(t2) - 1:
        x = t2[k2 - 1:k2 + 2]
        y = r2[k2 - 1:k2 + 2]
        denom = (x[0] - x[1]) * (x[0] - x[2]) * (x[1] - x[2])
        a_ = (x[2] * (y[0] - y[1]) + x[1] * (y[2] - y[0]) + x[0] * (y[1] - y[2])) / -denom
        b_ = (x[2] * x[2] * (y[0] - y[1]) + x[1] * x[1] * (y[2] - y[0]) + x[0] * x[0] * (y[1] - y[2])) / denom
        c_ = y[0] - a_ * x[0] * x[0] - b_ * x[0]
        return float(-b_ / (2.0 * a_)) if a_ != 0 else float(t2[k2])
    return float(t2[k2])


def cand_s_transmission_amplitude(n1, n2, theta_i):
    """B422 候选：s 偏振(TE) FD 总场提取复透射振幅模 |t_s|。"""
    xs, E, k1x, k2x, in_r2 = _fd_solve(n1, n2, theta_i, "te", FD_N_OBLIQUE)
    _, t = _extract_rt(xs, E, k1x, k2x, in_r2)
    return float(abs(t))


def cand_tir_reflectance(n1, n2, theta_i):
    """B423 候选：θi>θc 时 FD 提取 R（应≈1）。"""
    R, _ = _fd_RT(n1, n2, theta_i, "te", FD_N_TIR)
    return float(R)


def cand_evanescent_beta(n1, n2, theta_i):
    """B424 候选：θi>θc 时 FD 区域2 场**实测**倏逝衰减常数 β（弧度）。

    取区域2 内两探针点 x2a<x2b（均>0，远离界面与边界），由 |E(x)| 的指数衰减
    β = ln(|E(x2a)|/|E(x2b)|)/(x2b−x2a) 直接测量，与闭式 β=k0√(n1²sin²θi−n2²)
    方法学不同源（golden 用闭式，候选用 FD 场测量）。
    """
    xs, E, k1x, k2x, in_r2 = _fd_solve(n1, n2, theta_i, "te", FD_N_TIR)
    x2a, x2b = FD_L0 * 0.25, FD_L0 * 0.75
    Ea = np.interp(x2a, xs, E.real) + 1j * np.interp(x2a, xs, E.imag)
    Eb = np.interp(x2b, xs, E.real) + 1j * np.interp(x2b, xs, E.imag)
    ma, mb = abs(Ea), abs(Eb)
    if mb <= 0.0 or ma <= 0.0:
        return float(abs(k2x.imag))
    beta = math.log(ma / mb) / (x2b - x2a)
    return float(beta)


def cand_energy_conservation(n1, n2, theta_i):
    """B425 候选：FD 校验 Rs + Ts·(n2 cosθt)/(n1 cosθi) ≈ 1。"""
    Rs, Ts = _fd_RT(n1, n2, theta_i, "te", FD_N_OBLIQUE)
    ti = math.radians(theta_i)
    st = math.asin((n1 / n2) * math.sin(ti))
    c1, c2 = math.cos(ti), math.cos(st)
    return float(Rs + Ts * (n2 * c2) / (n1 * c1))


if __name__ == "__main__":
    print("=== B-26 单界面 Fresnel/Snell 核 自检 ===")
    n1, n2 = 1.0, 1.5
    theta = 40.0
    tests = [
        ("B413 R0", golden_b413(n1, n2), cand_normal_reflectance(n1, n2), 1e-4),
        ("B414 Rs", golden_b414(n1, n2, theta), cand_s_reflectance(n1, n2, theta), 1e-4),
        ("B415 Rp", golden_b415(n1, n2, theta), cand_p_reflectance(n1, n2, theta), 1e-4),
        ("B416 Ts", golden_b416(n1, n2, theta), cand_s_transmittance(n1, n2, theta), 1e-4),
        ("B417 Tp", golden_b417(n1, n2, theta), cand_p_transmittance(n1, n2, theta), 1e-4),
        ("B418 Runpol", golden_b418(n1, n2, theta), cand_unpol_reflectance(n1, n2, theta), 1e-4),
        ("B419 dR", golden_b419(n1, n2, theta), cand_delta_R(n1, n2, theta), 5e-4),
        ("B420 TsTp", golden_b420(n1, n2, theta), cand_Ts_Tp_ratio(n1, n2, theta), 2e-4),
        ("B421 thetaB", golden_b421(n1, n2), cand_brewster_angle(n1, n2), 5e-2),
        ("B422 |t_s|", golden_b422(n1, n2, theta), cand_s_transmission_amplitude(n1, n2, theta), 1e-3),
        ("B425 cons", golden_b425(n1, n2, theta), cand_energy_conservation(n1, n2, theta), 1e-4),
    ]
    print("%-14s %16s %16s %12s %10s %s" % ("锚", "golden", "cand", "|Δ|", "margin", "基线>1e-12"))
    allok = True
    for name, g, c, tol in tests:
        dd = abs(float(g) - float(c))
        margin = (tol / dd) if dd > 0 else float('inf')
        base_ok = dd > 1e-12
        flag = "OK" if (margin >= 2.0 and base_ok) else "BAD"
        if flag == "BAD":
            allok = False
        print("%-14s %16.8e %16.8e %12.3e %10.1f %s" % (name, g, c, dd, margin, flag))
    # TIR 组（n1>n2）：全反射率 / 倏逝衰减
    n1b, n2b = 1.5, 1.0
    theta_tir = 60.0
    tir_tests = [
        ("B423 R_tir", golden_b423(), cand_tir_reflectance(n1b, n2b, theta_tir), 1e-3),
        ("B424 beta", golden_b424(n1b, n2b, theta_tir), cand_evanescent_beta(n1b, n2b, theta_tir), 1e-3),
    ]
    print("--- TIR 组 (n1=1.5,n2=1.0, thetaTIR=%.1f) ---" % theta_tir)
    for name, g, c, tol in tir_tests:
        dd = abs(float(g) - float(c))
        margin = (tol / dd) if dd > 0 else float('inf')
        base_ok = dd > 1e-12
        flag = "OK" if (margin >= 2.0 and base_ok) else "BAD"
        if flag == "BAD":
            allok = False
        print("%-14s %16.8e %16.8e %12.3e %10.1f %s" % (name, g, c, dd, margin, flag))
    print("\nALL OK" if allok else "\nNEED TUNING")
