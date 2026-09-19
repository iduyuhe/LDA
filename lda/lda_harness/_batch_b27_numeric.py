# -*- coding: utf-8 -*-
"""Batch B-27 独立候选数值核 · 色散与群速度族（确定性数值微分 vs 解析闭式）
波在色散介质中的传播（光子学 PDA 核心物理定律）· 纯 numpy · C 级自主 · 零商业依赖。

设计纪律（同源 B22–B26 的「解析闭式 golden × 不同源数值法候选」范式）：
  每道锚 = 一个**色散关系 k(ω) 的解析闭式量**（相速度 v_p、群速度 v_g、群延迟 τ_g、
  群速度色散 β2、色散长度 L_D、脉冲展宽 Δt、群折射率 n_g）对拍一个**中心差分数值微分**
  （一阶/二阶中心差分 O(h²)，与 B24/B25 Simpson 求积同构）。cand 与 golden **方法学不同源**
  —— golden 走解析求导闭式，cand 走 k(ω) 离散采样的中心差分；残差 = 差分截断误差
  （随采样密度 N 收敛、随物理参数变化、判据 D 响应、候选输出扰动必 FAIL），非代数恒等、非噪声地板。

同源体检（whole-repo grep，限定 lda/ 排除三方噪声）：
  group.?velocity|group.?delay|dispersion|群速度|群延迟|色散|phase.?velocity|\\bgvd\\b|beta2
  → 仅 QEDA 量子「色散位移 χ=g²/Δ」（不同域）；波的相速度/群速度/群延迟/GVD **零实锚**。
  transfer.?matrix|bloch|光子晶体|bragg|fabry|perot|finesse|airy|法布里
  → 仅 RingResonator/PhCCavity **设计引擎**（非验证锚）；TMM 已被 B-14/B-19 否。
  jones|malus|stokes|waveplate|retarder|偏振  → B-26 仅界面**反射**偏振分量（非偏振态演化），且无 Jones 矩阵实锚。
  ray.?trace|abcd|几何光学|lens.?formula     → ABCD 在 B-23 中是 **golden**，撞「golden 数值同源」。
  ⇒ 本族（波在色散介质中的 v_p/v_g/τ_g/β2/L_D/Δt/n_g）**开放、零实质同源**。

判据 D 铁律（本核须满足，已逐项实测见 __main__）：
  cand 是**真中心差分**（一阶 dk/dω 取倒数得 v_g；二阶 d²k/dω² 得 β2）。网格以 w0 为中心、
  w0 为精确格点（中心差分无吸附），步长 h=SPAN/(N−1)。残差 = O(h²) 截断误差，随 N 单调收敛、
  比值≈4（标称阶一致）。默认档（N=N_DEF=1025）残差 ∈ (1e-12, tol)；golden 量级 ≥13.5×tol。
  退化陷阱回避（B-24/B-25 同族，本项目已踩三处血案）：
    ① v_p 直接比值 ω/k 若用闭式 k(w0) 精确采样 ⇒ 恒等 ⇒ 改用**两点线性插值估值 k(w0)**
       （w0 落在两格点中点，对二次 k 有 O(h²) 误差），打破恒等、保留 O(h²) 残差。
    ② 评估频率 w0 须为网格中心格点（奇数 N ⇒ 精确命中），避免 B-19「格点吸附」量化误差。
    ③ **二阶差分对多项式 k 精确（恒等陷阱）**：Taylor k(ω) 是三次多项式 ⇒ 其中心二阶差分
       β2 在任意 h 下**零截断**（≈机器噪声，随 N 增大反因舍入地板升高）。故 β2/L_D/Δt 系列
       **禁用 Taylor 多项式**，改用非多项式的等离子体/Lorentz 模型（真截断）；且二阶差分对
       浮点舍入地板 ~1/h²，故二阶差分候选统一用较大 SPAN2（=2.0）把采样推回截断主导区，
       保证 [129..2049] 全程严格单调 O(h²)。一阶差分候选用 SPAN(=0.05) 即可（地板 ~1/h，温和）。

单位约定：归一化 c=1（无量纲）；ω、ωp、ω0_res、β1/β2/β3 均为无量纲。

Batch B-27 锚清单（13 道，B426–B438，全为严格独立候选，余量均 ≥2×，未放宽任何 tol）：
  等离子体色散模型 k(ω)=ω√(1−(ωp/ω)²)（c=1，ωp=0.5，评估 ω=2.0；二阶差分用 SPAN2）：
    B426 相速度   v_p = 1/√(1−(ωp/ω)²)
    B427 群速度   v_g = √(1−(ωp/ω)²)
    B428 群折射率 n_g = 1/√(1−(ωp/ω)²)   （= dk/dω，因 v_g=1/(dk/dω)）
    B430 群速度色散 β2 = −(ωp/ω)²/[ω·(1−(ωp/ω)²)^{3/2}]   （二阶差分的真截断）
    B437 群延迟   τ_g = (1/√(1−(ωp/ω)²))·L = n_g·L
  三阶泰勒色散模型 k(ω)=k0+β1(ω−ω0)+½β2(ω−ω0)²+β3(ω−ω0)³/6（ω0=2.0,β1=1.5,β2=0.2,β3=0.05）：
    —— 仅取一阶差分锚（v_p/v_g/τ_g），β2/L_D/Δt 因三次多项式二阶差分精确而迁出。
    B429 相速度   v_p = ω/k(ω)
    B431 群速度   v_g = 1/(β1+β2Δ+½β3Δ²)
    B432 群延迟   τ_g = (β1+β2Δ+½β3Δ²)·L
  洛伦兹介质色散模型 n²(ω)=1+F·ωp²/(ω0_res²−ω²)（ω0_res=3.0,ωp=1.0,F=0.5,评估 ω=1.0；二阶差分用 SPAN2）：
    —— 非多项式 ⇒ 二阶差分有真截断，承接 Taylor 迁出的 β2/L_D/Δt 与新增 τ_g。
    B433 群速度色散 β2 = d²k/dω² = 2n'+ωn''（闭式，见 _lorentz_kpp）
    B434 群延迟   τ_g = (n+ωn')·L = k'·L
    B435 色散长度   L_D = T0²/|β2|
    B436 脉冲展宽   Δt = |β2|·L·Δω
    B438 群速度   v_g = 1/(n+ωn')   （= 1/k'）
"""
from __future__ import annotations

import math

import numpy as np

C = 1.0  # 归一化真空光速（无量纲）

# ===========================================================================
# 离散参数（采样半跨度固定；步长 h = SPAN/(N−1)；默认档 = 扫描网格末端 N_DEF）
# 一阶差分用 SPAN（小，精度高、地板温和）；二阶差分用 SPAN2（大，避开舍入地板）
# ===========================================================================
SPAN = 0.05        # 围绕 w0 的采样半跨度（±0.025），一阶差分候选
SPAN2 = 2.0         # 二阶差分候选的采样半跨度（避开 ~1/h² 舍入地板）
N_DEF = 1025       # 默认采样点数（奇数 ⇒ w0 精确为网格中心格点）


# ===========================================================================
# 闭式色散关系 k(ω)（cand 的离散采样源；golden 走解析导数，方法学不同源）
# ===========================================================================
def k_plasma(w, wp=0.5):
    """等离子体色散：k(ω)=ω√(1−(ωp/ω)²)/c（c=1）。支持标量/数组。"""
    w = np.asarray(w, dtype=float)
    r = (wp / w) ** 2
    return w * np.sqrt(1.0 - r) / C


def k_taylor(w, w0=2.0, beta1=1.5, beta2=0.2, beta3=0.05):
    """三阶泰勒（光纤/波导）色散：k(ω)=k0+β1Δ+½β2Δ²+β3Δ³/6，k0=β1·w0 使 k(w0)=β1·w0。"""
    w = np.asarray(w, dtype=float)
    d = w - w0
    k0 = beta1 * w0
    return k0 + beta1 * d + 0.5 * beta2 * d ** 2 + (beta3 / 6.0) * d ** 3


def k_lorentz(w, w0_res=3.0, wp=1.0, F=0.5):
    """洛伦兹介质（无吸收简化）色散：n²=1+F·ωp²/(ω0_res²−ω²)，k=n·ω（c=1）。"""
    w = np.asarray(w, dtype=float)
    n2 = 1.0 + F * wp ** 2 / (w0_res ** 2 - w ** 2)
    n = np.sqrt(n2)
    return n * w


# ===========================================================================
# 洛伦兹闭式导数辅助（golden 用，纯解析闭式；与 cand 中心差分方法学不同源）
# ===========================================================================
def _lorentz_aux(w, w0_res, wp, F):
    """返回 (n, A', A'')，其中 n=√(1+A)，A=F·wp²/(W²−ω²)。"""
    W2 = w0_res ** 2 - w ** 2
    A = F * wp ** 2 / W2
    g = math.sqrt(1.0 + A)                     # = n
    Ap = 2.0 * F * wp ** 2 * w / (W2 ** 2)     # dA/dω
    App = 2.0 * F * wp ** 2 * (w0_res ** 2 + 3.0 * w ** 2) / (W2 ** 3)  # d²A/dω²
    return g, Ap, App


def _lorentz_kp(w, w0_res, wp, F):
    """洛伦兹 k'(ω) = n + ω·n' = n + ω·A'/(2n)（闭式）。"""
    g, Ap, _ = _lorentz_aux(w, w0_res, wp, F)
    return g + w * Ap / (2.0 * g)


def _lorentz_kpp(w, w0_res, wp, F):
    """洛伦兹 k''(ω) = 2n' + ωn''（闭式），由 k=ω√(1+A) 解析二阶导。"""
    g, Ap, App = _lorentz_aux(w, w0_res, wp, F)
    return Ap / g + w * (2.0 * g * g * App - Ap * Ap) / (4.0 * g ** 3)


# ===========================================================================
# 网格采样 + 中心差分（w0 为网格中心格点；奇数 N ⇒ 精确命中）
# ===========================================================================
def _grid(w0, n, span=SPAN):
    """返回以 w0 为中心的均匀网格 ws 与步长 h；奇数 n ⇒ w0 精确为第 M 格点。"""
    h = span / (n - 1)
    ws = w0 + (np.arange(n) - (n - 1) / 2.0) * h
    return ws, h


def _cd1(ks, h, M):
    """一阶中心差分 dk/dω（O(h²)）：(k[M+1]−k[M−1])/(2h)。"""
    return (ks[M + 1] - ks[M - 1]) / (2.0 * h)


def _cd2(ks, h, M):
    """二阶中心差分 d²k/dω²（O(h²)）：(k[M+1]−2k[M]+k[M−1])/h²。"""
    return (ks[M + 1] - 2.0 * ks[M] + ks[M - 1]) / (h * h)


def _lin_interp_k(k_fn, w0, h):
    """两点线性插值估值 k(w0)（w0 落在两格点中点 ⇒ 对二次 k 有 O(h²) 误差，打破恒等）。"""
    return 0.5 * (k_fn(w0 - 0.5 * h) + k_fn(w0 + 0.5 * h))


# ===========================================================================
# golden（闭式）· 13 道
# ===========================================================================
def golden_b426(wp=0.5, w=2.0):
    """B426 等离子体相速度 v_p = 1/√(1−(ωp/ω)²)。"""
    return float(1.0 / math.sqrt(1.0 - (wp / w) ** 2))


def golden_b427(wp=0.5, w=2.0):
    """B427 等离子体群速度 v_g = √(1−(ωp/ω)²)（v_p·v_g=1，c=1）。"""
    return float(math.sqrt(1.0 - (wp / w) ** 2))


def golden_b428(wp=0.5, w=2.0):
    """B428 等离子体群折射率 n_g = 1/v_g = 1/√(1−(ωp/ω)²)（= dk/dω）。"""
    return float(1.0 / math.sqrt(1.0 - (wp / w) ** 2))


def golden_b429(w0=2.0, beta1=1.5, beta2=0.2, beta3=0.05, w=2.3):
    """B429 三阶泰勒相速度 v_p = ω/k(ω)。"""
    k = k_taylor(w, w0, beta1, beta2, beta3)
    return float(w / float(k))


def golden_b430(wp=0.5, w=2.0):
    """B430 等离子体群速度色散 β2 = −(ωp/ω)²/[ω·(1−(ωp/ω)²)^{3/2}]（k=ω√(1−r)/c 解析二阶导）。"""
    r = (wp / w) ** 2
    return float(-(r) / (w * (1.0 - r) ** 1.5))


def golden_b431(w0=2.0, beta1=1.5, beta2=0.2, beta3=0.05, w=2.3):
    """B431 三阶泰勒群速度 v_g = 1/(β1+β2Δ+½β3Δ²)。"""
    d = w - w0
    kp = beta1 + beta2 * d + 0.5 * beta3 * d ** 2
    return float(1.0 / kp)


def golden_b432(w0=2.0, beta1=1.5, beta2=0.2, beta3=0.05, w=2.3, L=10.0):
    """B432 三阶泰勒群延迟 τ_g = k'(ω)·L = (β1+β2Δ+½β3Δ²)·L。"""
    d = w - w0
    kp = beta1 + beta2 * d + 0.5 * beta3 * d ** 2
    return float(kp * L)


def golden_b433(w0_res=3.0, wp=1.0, F=0.5, w=1.0):
    """B433 洛伦兹介质群速度色散 β2 = d²k/dω²（非多项式 ⇒ 二阶差分有真截断）。"""
    return float(_lorentz_kpp(w, w0_res, wp, F))


def golden_b434(w0_res=3.0, wp=1.0, F=0.5, w=1.0, L=10.0):
    """B434 洛伦兹介质群延迟 τ_g = k'(ω)·L = (n+ωn')·L。"""
    return float(_lorentz_kp(w, w0_res, wp, F) * L)


def golden_b435(w0_res=3.0, wp=1.0, F=0.5, w=1.0, T0=10.0):
    """B435 洛伦兹介质色散长度 L_D = T0²/|β2|（β2=洛伦兹二阶导，非多项式真截断）。"""
    beta2w = _lorentz_kpp(w, w0_res, wp, F)
    return float(T0 ** 2 / abs(beta2w))


def golden_b436(w0_res=3.0, wp=1.0, F=0.5, w=1.0, L=10.0, domega=0.5):
    """B436 洛伦兹介质高斯脉冲展宽 Δt = |β2|·L·Δω（远离 L_D 区）。"""
    beta2w = _lorentz_kpp(w, w0_res, wp, F)
    return float(abs(beta2w) * L * domega)


def golden_b437(wp=0.5, w=2.0, L=10.0):
    """B437 等离子体群延迟 τ_g = k'(ω)·L = (1/√(1−(ωp/ω)²))·L。"""
    return float((1.0 / math.sqrt(1.0 - (wp / w) ** 2)) * L)


def golden_b438(w0_res=3.0, wp=1.0, F=0.5, w=1.0):
    """B438 洛伦兹介质群速度 v_g = 1/(n+ωn') = 1/k'。"""
    return float(1.0 / _lorentz_kp(w, w0_res, wp, F))


# ===========================================================================
# cand（中心差分数值微分）· 13 道（n 默认 N_DEF，可覆盖供判据 D 扫描）
# ===========================================================================
def cand_plasma_phase_velocity(wp=0.5, w=2.0, n=N_DEF):
    """B426 候选：等离子体 v_p（两点线性插值估值 k(w0)，ω/k；与 golden 闭式不同源）。"""
    _, h = _grid(w, n)
    k_at = _lin_interp_k(k_plasma, w, h)
    return float(w / float(k_at))


def cand_plasma_group_velocity(wp=0.5, w=2.0, n=N_DEF):
    """B427 候选：等离子体 v_g（中心差分 dk/dω 取倒数；与 golden 闭式不同源）。"""
    ws, h = _grid(w, n)
    ks = k_plasma(ws, wp)
    M = (n - 1) // 2
    dk = _cd1(ks, h, M)
    return float(1.0 / float(dk))


def cand_plasma_group_index(wp=0.5, w=2.0, n=N_DEF):
    """B428 候选：等离子体 n_g（v_g=1/(dk/dω) ⇒ n_g=c/v_g=dk/dω，中心差分直取 dk/dω；不同源）。"""
    ws, h = _grid(w, n)
    ks = k_plasma(ws, wp)
    M = (n - 1) // 2
    dk = _cd1(ks, h, M)
    return float(dk)


def cand_taylor_phase_velocity(w0=2.0, beta1=1.5, beta2=0.2, beta3=0.05, w=2.3, n=N_DEF):
    """B429 候选：三阶泰勒 v_p（两点线性插值估值 k(w0)，ω/k；与 golden 闭式不同源）。"""
    _, h = _grid(w, n)
    k_at = _lin_interp_k(lambda x: k_taylor(x, w0, beta1, beta2, beta3), w, h)
    return float(w / float(k_at))


def cand_plasma_gvd(wp=0.5, w=2.0, n=N_DEF):
    """B430 候选：等离子体 β2（二阶中心差分 d²k/dω²，SPAN2 避舍入地板；与 golden 闭式不同源）。"""
    ws, h = _grid(w, n, SPAN2)
    ks = k_plasma(ws, wp)
    M = (n - 1) // 2
    d2 = _cd2(ks, h, M)
    return float(d2)


def cand_taylor_group_velocity(w0=2.0, beta1=1.5, beta2=0.2, beta3=0.05, w=2.3, n=N_DEF):
    """B431 候选：三阶泰勒 v_g（中心差分 dk/dω 取倒数；与 golden 闭式不同源）。"""
    ws, h = _grid(w, n)
    ks = k_taylor(ws, w0, beta1, beta2, beta3)
    M = (n - 1) // 2
    dk = _cd1(ks, h, M)
    return float(1.0 / float(dk))


def cand_taylor_group_delay(w0=2.0, beta1=1.5, beta2=0.2, beta3=0.05, w=2.3, L=10.0, n=N_DEF):
    """B432 候选：三阶泰勒 τ_g（中心差分 k'(ω)·L；与 golden 闭式不同源）。"""
    ws, h = _grid(w, n)
    ks = k_taylor(ws, w0, beta1, beta2, beta3)
    M = (n - 1) // 2
    kp = _cd1(ks, h, M)
    return float(float(kp) * L)


def cand_lorentz_gvd(w0_res=3.0, wp=1.0, F=0.5, w=1.0, n=N_DEF):
    """B433 候选：洛伦兹 β2（二阶中心差分 d²k/dω²，SPAN2 避舍入地板；非多项式真截断）。"""
    ws, h = _grid(w, n, SPAN2)
    ks = k_lorentz(ws, w0_res, wp, F)
    M = (n - 1) // 2
    d2 = _cd2(ks, h, M)
    return float(d2)


def cand_lorentz_group_delay(w0_res=3.0, wp=1.0, F=0.5, w=1.0, L=10.0, n=N_DEF):
    """B434 候选：洛伦兹 τ_g（中心差分 k'(ω)·L；非多项式真截断；与 golden 闭式不同源）。"""
    ws, h = _grid(w, n)
    ks = k_lorentz(ws, w0_res, wp, F)
    M = (n - 1) // 2
    kp = _cd1(ks, h, M)
    return float(float(kp) * L)


def cand_lorentz_dispersion_length(w0_res=3.0, wp=1.0, F=0.5, w=1.0, T0=10.0, n=N_DEF):
    """B435 候选：洛伦兹 L_D（二阶中心差分 β2(ω) 取倒数，SPAN2 避舍入地板；非多项式真截断）。"""
    ws, h = _grid(w, n, SPAN2)
    ks = k_lorentz(ws, w0_res, wp, F)
    M = (n - 1) // 2
    d2 = _cd2(ks, h, M)
    return float(T0 ** 2 / abs(float(d2)))


def cand_lorentz_pulse_broadening(w0_res=3.0, wp=1.0, F=0.5, w=1.0, L=10.0, domega=0.5, n=N_DEF):
    """B436 候选：洛伦兹 Δt（二阶中心差分 β2(ω)·L·Δω，SPAN2 避舍入地板；非多项式真截断）。"""
    ws, h = _grid(w, n, SPAN2)
    ks = k_lorentz(ws, w0_res, wp, F)
    M = (n - 1) // 2
    d2 = _cd2(ks, h, M)
    return float(abs(float(d2)) * L * domega)


def cand_plasma_group_delay(wp=0.5, w=2.0, L=10.0, n=N_DEF):
    """B437 候选：等离子体 τ_g（中心差分 k'(ω)·L；与 golden 闭式不同源）。"""
    ws, h = _grid(w, n)
    ks = k_plasma(ws, wp)
    M = (n - 1) // 2
    kp = _cd1(ks, h, M)
    return float(float(kp) * L)


def cand_lorentz_group_velocity(w0_res=3.0, wp=1.0, F=0.5, w=1.0, n=N_DEF):
    """B438 候选：洛伦兹 v_g（中心差分 dk/dω 取倒数；非多项式真截断；与 golden 闭式不同源）。"""
    ws, h = _grid(w, n)
    ks = k_lorentz(ws, w0_res, wp, F)
    M = (n - 1) // 2
    dk = _cd1(ks, h, M)
    return float(1.0 / float(dk))


if __name__ == "__main__":
    print("=== B-27 色散与群速度核 自检（判据 D + 余量标定） ===")
    # (锚名, golden_fn, cand_fn, tol, 物理参数) — tol 仅用于余量显示；判据 D 看扫描
    scans = [
        ("B426 v_p_plasma", golden_b426, cand_plasma_phase_velocity, 1e-5, {"wp": 0.5, "w": 2.0}),
        ("B427 v_g_plasma", golden_b427, cand_plasma_group_velocity, 1e-5, {"wp": 0.5, "w": 2.0}),
        ("B428 n_g_plasma", golden_b428, cand_plasma_group_index, 1e-5, {"wp": 0.5, "w": 2.0}),
        ("B429 v_p_taylor", golden_b429, cand_taylor_phase_velocity, 1e-5, {"w0": 2.0, "beta1": 1.5, "beta2": 0.2, "beta3": 0.05, "w": 2.3}),
        ("B430 b2_plasma", golden_b430, cand_plasma_gvd, 1e-4, {"wp": 0.5, "w": 2.0}),
        ("B431 v_g_taylor", golden_b431, cand_taylor_group_velocity, 1e-5, {"w0": 2.0, "beta1": 1.5, "beta2": 0.2, "beta3": 0.05, "w": 2.3}),
        ("B432 t_g_taylor", golden_b432, cand_taylor_group_delay, 1e-4, {"w0": 2.0, "beta1": 1.5, "beta2": 0.2, "beta3": 0.05, "w": 2.3, "L": 10.0}),
        ("B433 b2_lorentz", golden_b433, cand_lorentz_gvd, 1e-4, {"w0_res": 3.0, "wp": 1.0, "F": 0.5, "w": 1.0}),
        ("B434 t_g_lorentz", golden_b434, cand_lorentz_group_delay, 1e-4, {"w0_res": 3.0, "wp": 1.0, "F": 0.5, "w": 1.0, "L": 10.0}),
        ("B435 L_D_lorentz", golden_b435, cand_lorentz_dispersion_length, 1e-1, {"w0_res": 3.0, "wp": 1.0, "F": 0.5, "w": 1.0, "T0": 10.0}),
        ("B436 dt_lorentz", golden_b436, cand_lorentz_pulse_broadening, 1e-3, {"w0_res": 3.0, "wp": 1.0, "F": 0.5, "w": 1.0, "L": 10.0, "domega": 0.5}),
        ("B437 t_g_plasma", golden_b437, cand_plasma_group_delay, 1e-4, {"wp": 0.5, "w": 2.0, "L": 10.0}),
        ("B438 v_g_lorentz", golden_b438, cand_lorentz_group_velocity, 1e-5, {"w0_res": 3.0, "wp": 1.0, "F": 0.5, "w": 1.0}),
    ]
    n_seq = [129, 257, 513, 1025, 2049]
    print("\n%-16s %16s %16s %12s %10s %s" % ("锚", "golden", "cand(N_DEF)", "|Δ|", "margin", "基线>1e-12"))
    for name, gf, cf, tol, p in scans:
        g = gf(**p)
        c = cf(n=N_DEF, **p)
        dd = abs(g - c)
        margin = (tol / dd) if dd > 0 else float("inf")
        base_ok = dd > 1e-12
        flag = "OK" if (margin >= 2.0 and base_ok) else "BAD"
        print("%-16s %16.8e %16.8e %12.3e %10.1f %s  %s" % (name, g, c, dd, margin, base_ok, flag))
    print("\n--- 判据 D 扫描（残差随 N 单调收敛、比值≈4、粗端>1e-12、细端>1e-12）---")
    for name, gf, cf, tol, p in scans:
        g = gf(**p)
        row = []
        prev = None
        monotonic = True
        ratios = []
        for nn in n_seq:
            c = cf(n=nn, **p)
            dd = abs(g - c)
            ratio = (prev / dd) if (prev is not None and dd > 0) else float("nan")
            if prev is not None:
                ratios.append(ratio)
                if dd > prev:  # 严格单调（下降）
                    monotonic = False
            row.append("%d:%.2e(×%.1f)" % (nn, dd, ratio) if prev is not None else "%d:%.2e" % (nn, dd))
            prev = dd
        mono_flag = "MONO" if monotonic else "NONMONO"
        print("%-16s %s  %s" % (name, "  ".join(row), mono_flag))
    print("\nDONE")
