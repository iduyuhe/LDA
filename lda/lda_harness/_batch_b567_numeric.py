# -*- coding: utf-8 -*-
"""Batch B5/B6/B7 独立候选数值核（纯 numpy/scipy · C 级自主 · 零商业依赖）。

设计纪律（同 B16 `_batch_b16_rib_mmi.py` / B8 `eme_taper` 的「同一物理对象 +
方法学不同源」对拍）：
  每道锚 = 一个**几何无关的设计守则/唯象黄金** 对拍 一个**首原理的真实求解器**。
  残差 = 建模差异（持久、随参数变化、判据 D 响应、反向扰动 FAIL），
  不是「代数恒等」（B28 血案）也不是「纯数值误差沉底」（B10 血案）。

本批锚清单（3 道，原 design_rule_anchor 自证桩）：
  B5  Y 分支(1×2) 分束插入损耗 —— golden 唯象拟合 3.0+0.4(θ/10)²
      vs 双芯超模 EME 全场传播（严格，不套任何成像/拟合因子）
  B6  光栅耦合器峰值耦合效率 —— golden 设计守则常数 0.5
      vs 首原理分解 η_dir(辐射对称) × η_ov(高斯⊗指数模场重叠) × F(占空比傅里叶)
         × M(光栅方程相位匹配)
  B7  波导交叉串扰 —— **本批不接线**（golden 侧离线 2D FDTD 经诊断不收敛/被近场
      辐射污染，见 `crossing_crosstalk_dB` 的 docstring 与证据；方法学独立候选
      `crossing_crosstalk_dB` 已实现备查，待 golden 修复后方可升格）

⚠️ 运行环境：本模块须在 `lda/` 在 sys.path 时导入（`_ensure_paths()` 已保证）。
"""
from __future__ import annotations

import math

import numpy as np

_C0 = 299792458.0
_IDEAL_SPLIT_DB = 10.0 * math.log10(2.0)      # 3.0103 dB —— 理想 1×2 几何必然

# ---------------------------------------------------------------------------
# 通用：EIM 垂直降维（对称平板 TE0 解析超越方程）
# ---------------------------------------------------------------------------
def _te0_neff_slab(t: float, wl: float, n_f: float, n_c: float) -> float:
    """对称平板 TE0 有效折射率（u·tan u = sqrt(V²−u²)，brentq 严格求根）。"""
    from scipy.optimize import brentq
    k0 = 2.0 * math.pi / wl
    V = 0.5 * t * k0 * math.sqrt(n_f ** 2 - n_c ** 2)
    hi = min(V, 0.5 * math.pi) - 1e-9
    if hi <= 1e-9:
        raise ValueError(f"V={V:.4f} 过小，TE0 无解")
    f = lambda u: u * math.tan(u) - math.sqrt(max(V ** 2 - u ** 2, 0.0))
    u = brentq(f, 1e-12, hi, xtol=1e-14, rtol=1e-15)
    return float(math.sqrt(n_f ** 2 - (u / (0.5 * t * k0)) ** 2))


def _grid(window: float, dx: float) -> np.ndarray:
    """横向均匀网格（格心偏置半格，关于 x=0 对称）。"""
    N = int(round(window / dx))
    if N % 2:
        N += 1
    return (np.arange(N) - N // 2) * dx


def _multicore_profile(x: np.ndarray, centers, w: float, n_core: float,
                       n_clad: float) -> np.ndarray:
    """多芯横向折射率剖面（**亚网格面积加权**，可自动处理芯合并）。

    🔴 面积加权不可改成硬判据：芯宽与 dx 同量级时硬判据会把渐变离散成突跳，
    使损耗与几何无关（同 eme_taper._index_profile 的血案）。
    """
    h = float(x[1] - x[0])
    lo, hi = x - 0.5 * h, x + 0.5 * h
    ov = np.zeros_like(x)
    for c in centers:
        a, b = c - 0.5 * w, c + 0.5 * w
        ov = ov + np.clip(np.minimum(hi, b) - np.maximum(lo, a), 0.0, None)
    ov = np.clip(ov, 0.0, h)          # 芯重叠区不得重复计面积（并集）
    f = ov / h
    return np.sqrt(f * n_core ** 2 + (1.0 - f) * n_clad ** 2)


def _slab_modes(x, n_prof, k0, m_modes):
    """一维横向 Helmholtz 本征解（复用 lda_solver.eme_taper 的生产档实现）。"""
    try:
        from lda_solver.eme_taper import slab_modes
    except ImportError:
        import eme_taper  # type: ignore
        slab_modes = eme_taper.slab_modes
    return slab_modes(x, n_prof, k0, m_modes)


# ===========================================================================
# B5 · Y 分支(1×2) 分束插入损耗（双芯超模 EME）
# ===========================================================================
# 几何约定（spec 未给锥长 ⇒ 取标准中性约定，已写入 note）：
#   输入波导宽 w；分叉为两臂（各宽 w），中心间距 d(z) 由 0 单调增至 d_f = 2w
#   （两臂中心分离 2w ⇒ 芯间留一个 w 的缝）。半张角 tan(θ/2) = (d_f/2)/L_f。
#   d < w 时两芯重叠 ⇒ 单一加宽芯 = Y 分支锥尖的物理（非拼接近似）。
B5_D_F_FACTOR = 2.0
B5_M_MODES = 24
B5_DX_UM = 0.02
B5_WINDOW_UM = 12.0
B5_DZ_UM = 0.1


def ybranch_split_loss_dB(w_core: float, h_core: float, n_si: float,
                          n_clad: float, wl: float,
                          theta_deg: float) -> float:
    """Y 分支 1×2 分束插入损耗(dB) —— 双芯超模 EME 全场传播求解。

    物理：分束损耗 = 理想均分几何下限 3.0103 dB + 过量损耗。
    过量损耗来自锥区**非绝热模式转换**（输入基模 → 局部超模系的投影损失）。

    数值路径（与 golden 的唯象拟合式完全不同源）：
      ① EIM 把垂向结构（h_core/n_si/n_clad）降维成横向问题中的芯折射率；
      ② 锥区按 z 切片，每片解**完整横向 Helmholtz 本征问题**（无旁轴假设）；
      ③ 输入基模沿片内精确模态传播 exp(−iβ·dz)，片间用模式重叠矩阵投影；
      ④ 末片全部导模功率和 T ⇒ 分束损耗 = 3.0103 − 10·log10(T)。

    🔴 诚实边界（写进 note，不得省略）：
      * EIM 降维 ⇒ 不含垂向辐射与极化耦合；只算前向模式（忽略背向反射，
        反射只会**增加**损耗 ⇒ 本候选对 golden 不会虚高成「比理想还好」）。
      * 锥长由 (w, θ) 与「末臂间距 = 2w」约定唯一确定，属**设计约定**而非唯一
        几何；θ 相同、约定不同则锥长不同（已如实登记）。
      * 实测残差 = golden 唯象拟合式的固有粗糙度（拟合把 excess 估成 0.4·(θ/10)²
        量级，严格 EME 给出 ~0.01–0.06 dB）—— 非零、有界、随 θ 单调、物理。
    """
    w = float(w_core)
    d_f = B5_D_F_FACTOR * w
    half_ang = math.radians(0.5 * float(theta_deg))
    L_f = d_f / (2.0 * math.tan(half_ang)) if half_ang > 0 else 1e6
    n_eff_v = _te0_neff_slab(float(h_core), float(wl), float(n_si), float(n_clad))

    nsl = max(20, int(round(L_f / B5_DZ_UM)))
    dz_eff = L_f / nsl
    x = _grid(B5_WINDOW_UM, B5_DX_UM)
    k0 = 2.0 * math.pi / float(wl)

    ds = d_f * ((np.arange(nsl) + 0.5) / nsl)
    modes = [_slab_modes(x, _multicore_profile(x, (-0.5 * d, 0.5 * d), w,
                                               n_eff_v, float(n_clad)), k0,
                         B5_M_MODES) for d in ds]

    c = np.zeros(len(modes[0][1]), dtype=np.complex128)
    c[0] = 1.0
    for j, (phis, betas) in enumerate(modes):
        c = c * np.exp(-1j * betas * dz_eff)
        if j + 1 < len(modes):
            O = (modes[j + 1][0].T @ phis) * B5_DX_UM
            c = O @ c
    T = float(np.sum(np.abs(c) ** 2))
    return float(_IDEAL_SPLIT_DB - 10.0 * math.log10(max(T, 1e-12)))


# ===========================================================================
# B6 · 光栅耦合器峰值耦合效率（首原理分解）
# ===========================================================================
# 分解：η = η_dir · η_ov · F(ff) · M(Λ,λ,θ)
#   η_dir = 1/2  —— 无底部反射镜、上下包层对称 ⇒ 一阶衍射向上/向下功率相等
#                  （对称性给出的结果，非经验常数）
#   η_ov  —— 光栅辐射场（振幅 ∝ exp(−α z/2)，均匀光栅的指数衰减）与单模光纤
#            高斯模（MFD=10.4µm）的**模场重叠**，对 α 取设计最优（「峰值」语义）
#   F(ff) = sin(π·ff)  —— 方波光栅介电常数一阶傅里叶强度（归一化，ff=0.5 → 1）
#   M     = exp(−(Δβ·L_g/2)²) —— 光栅方程相位匹配因子
MFD_UM = 10.4
B6_N_GRATING_PERIODS = 20
B6_OV_Z_POINTS = 4000


def _gauss_exp_overlap(alpha_um_inv: float, w0: float, offset: float,
                       L: float) -> float:
    """归一化模场重叠 |∫E_g E_f dz|² / (∫|E_g|²·∫|E_f|²)。"""
    z = np.linspace(0.0, L, B6_OV_Z_POINTS)
    Eg = np.exp(-alpha_um_inv * z / 2.0)
    Ef = np.exp(-((z - offset) / w0) ** 2)
    num = np.trapezoid(Eg * Ef, z) ** 2
    den = np.trapezoid(Eg ** 2, z) * np.trapezoid(Ef ** 2, z)
    return float(num / den)


def _best_overlap(w0: float = MFD_UM / 2.0) -> float:
    """对光栅辐射强度 α 取设计最优的模场重叠（峰值语义）。"""
    L = 20.0 * w0
    best = 0.0
    for a in np.linspace(0.02, 1.2, 600):
        v = _gauss_exp_overlap(float(a), w0, w0, L)
        if v > best:
            best = v
    return best


B6_OV_OPT = None


def grating_coupler_eff(wl: float, n_si: float, n_clad: float, period: float,
                        ff: float, theta_deg: float) -> float:
    """光栅耦合器峰值耦合效率 —— 方向性 × 模场重叠 × 傅里叶强度 × 相位匹配。"""
    global B6_OV_OPT
    if B6_OV_OPT is None:
        B6_OV_OPT = _best_overlap()

    k0 = 2.0 * math.pi / float(wl)
    th = math.radians(float(theta_deg))
    # 光栅方程（一阶辐射耦合通道）相位匹配所需 n_eff
    n_req = float(wl) / float(period) + float(n_clad) * math.sin(th)
    # 光栅区等效介质折射率
    n_g = math.sqrt(float(ff) * float(n_si) ** 2
                    + (1.0 - float(ff)) * float(n_clad) ** 2)
    dbeta = k0 * (n_g - n_req)
    L_g = B6_N_GRATING_PERIODS * float(period)
    eta_phase = math.exp(-(dbeta * L_g / 2.0) ** 2)
    # 方波光栅一阶傅里叶强度（归一化）
    F = abs(math.sin(math.pi * float(ff)))
    eta_dir = 0.5
    return float(eta_dir * B6_OV_OPT * F * eta_phase)


# ===========================================================================
# B7 · 波导交叉串扰（v0.9.82 接线：golden 语义订正为守则锚 −40 dB）
# ===========================================================================
def crossing_crosstalk_dB(w_core: float, gap: float, wl: float,
                          n_si: float, n_clad: float) -> float:
    """90° 交叉串扰(dB) —— 双波导超模/CMT 模型（方法学独立于场级 FDTD）。

    物理：gap 相隔的两臂构成耦合段，耦合系数 κ = π·(n_even − n_odd)/λ
    （超模拍），串扰 = sin²(κ·L_eff)；n_even/n_odd 由双芯横向剖面
    Helmholtz 本征解**严格**给出（不读 golden、无待标定系数）。

    v0.9.82 接线（原「未接线」状态已解除）：B7 的 golden 由
    `oracle_field._fdtd2d_crossing`（离线 2D FDTD）**撤出调度**并降级为
    机理诊断量 —— 该 2D 降维（裸十字）与其**锚定器件**（同几何的 taper
    优化交叉，实证语料 E-SOI-CROSS-XT = −41±2 dB）相差 20~30 dB；加 taper
    展宽仅改善 3.6 dB；源位置深扫 ±3 dB 无收敛趋势（2D 线源辐射不匹配真实
    3D 波导激励）。golden 现为设计守则锚 −40 dB（有 E7 实证背书）。
    本候选默认给 **−35.36 dB**，|diff| = 4.64 < tol 5.0 ⇒ 升 Tier-3。
    证据链见 `P1-1_B7_golden_fix_report.md`。

    ⚠️ 诚实边界：
      1. 残差 4.64 dB 占 tol 窗口 **93%** —— **边缘通过**；
      2. L_eff = 芯宽 是交叉耦合段的量级估计（非严格场解）；
      3. `gap` 在 90° 十字的几何语义原锚未定义，本模型按「两臂间距」解释
         （gap 0.1/0.2/0.3 → −24.96/−35.36/−45.72 dB，仅供趋势参考）；
      4. 与锚定器件 −41±2 dB 的彻底对齐需 3D 全波 + 真实 taper 版图。
    """
    w = float(w_core)
    d = w + float(gap)
    x = _grid(8.0, 0.01)
    k0 = 2.0 * math.pi / float(wl)
    n_prof = _multicore_profile(x, (-0.5 * d, 0.5 * d), w,
                               float(n_si), float(n_clad))
    phis, betas = _slab_modes(x, n_prof, k0, 8)
    n_e = float(betas[0].real) / k0
    n_o = float(betas[1].real) / k0
    kappa = math.pi * abs(n_e - n_o) / float(wl)
    L_eff = w                                    # 交叉耦合等效长度 ~ 芯宽
    T = math.sin(kappa * L_eff) ** 2
    return float(10.0 * math.log10(max(T, 1e-14)))
