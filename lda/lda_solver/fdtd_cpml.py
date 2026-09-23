"""LDA · L3 自研 FDTD 的 CFS-PML 吸收核 + 回反射测量（G11「真 PML」）。

## 本模块回答一个问题

**「换掉梯度海绵、上真 PML，回反射到底降了多少？」—— 用可复现的数字回答，
而不是引用文献。**

方法（经典 PML 反射测量的机器化，Taflove §7.9 的口径）：

    · 退化一维几何：沿**吸收轴**传播，其余轴取 PBC 且横向均匀 ⇒ 无横向色散
    · 软源打**高斯包络脉冲**（带载波），监视点在源与左边界之间
    · 直接**时域门控**：入射波到达时间 `t_inc`、左边界回波到达时间
      `t_ref = t_inc + 2·d_left` 可解析算出 ⇒ 两个互不重叠的窗口
    · **Γ = √(ΣE²_ref / ΣE²_inc)**（同点测，比值 ⇒ 无需绝对定标，
      这正是本项目「参考跑归一化」纪律在本测量里的同构形式）

⇒ **Γ 是比值，不是声称**。没有吸收器时（`n_abs=0`，边界退化为截断差分 ⇒ 全反射）
Γ ≈ 1 —— 该事实由 smoke ⑨ 钉成断言，用来证明「这台测量仪对有没有吸收敏感」。

## 为什么 CPML 有判据 D，而 ∇-海绵「天然」没有

CPML 的 σ_max 若取经典最优式 `σ_opt ∝ 1/L`，则**反射与层厚无关**（设计目标）
⇒ 扫层厚残差不变 ⇒ 无判据 D。**判据 D 必须显式固定 σ_max 再扫层厚**：
固定 σ_max 时总光学厚度 ∝ L ⇒ 回反射随层厚**严格单调降**。

▸ 对照组的 ∇-海绵（本仓既有实现）其 `sig_max = target_exp·3·ε_bg/(dt·N_pml)`
  ∝ 1/N_pml ⇒ **σ·L 恒定** ⇒ 其回反射对层厚**近似不响应**。所以本 smoke
  只对 CPML 声称判据 D，对海绵**如实登记实测序列**（不冒充）。

## 边界与纪律

- **只增不改**：本模块**不修改** `fdtd2d.py` / `fdtd3d.py` 一行。改默认吸收器
  = 改全部 FDTD 依赖锚的数值 ⇒ 属另一项决策（须重跑锚验证），不属本批。
- **忠实对照**：海绵模式的阻尼装配**逐条对齐**既有实现（2D 只阻尼 H、3D 同时
  阻尼 E 与 H；H 的阻尼取「该分量导数轴」上的半格平均）—— 否则对照无意义。
- 与 `cpml.py` 同一归一化约定（c = ε₀ = μ₀ = 1）。
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from cpml import (DEFAULT_ALPHA_MAX, DEFAULT_KAPPA_MAX,  # noqa: E402
                  DEFAULT_ORDER, cpml_axis, null_axis)
from fdtd3d import _avg_sigma, _sponge_1d  # noqa: E402

__all__ = ["run_pulse_2d", "run_pulse_3d", "measure_reflection"]


# ---------------------------------------------------------------------------
# 差分算子（PBC ⇒ 环绕；否则截断，末节点落在吸收层内）
# ---------------------------------------------------------------------------
def _diff(f, axis, pbc):
    """前向差分 f[i+1] − f[i]。"""
    if pbc:
        return np.roll(f, -1, axis=axis) - f
    out = np.zeros_like(f)
    sl_o = [slice(None)] * f.ndim
    sl_n = [slice(None)] * f.ndim
    sl_o[axis] = slice(0, -1)
    sl_n[axis] = slice(1, None)
    out[tuple(sl_o)] = f[tuple(sl_n)] - f[tuple(sl_o)]
    return out


def _bdiff(f, axis, pbc):
    """后向差分 f[i] − f[i−1]。"""
    if pbc:
        return f - np.roll(f, 1, axis=axis)
    out = np.zeros_like(f)
    sl_n = [slice(None)] * f.ndim
    sl_p = [slice(None)] * f.ndim
    sl_n[axis] = slice(1, None)
    sl_p[axis] = slice(None, -1)
    out[tuple(sl_n)] = f[tuple(sl_n)] - f[tuple(sl_p)]
    return out


def _rs(v, axis, ndim):
    """把一维系数摊成可广播形状。"""
    shape = [1] * ndim
    shape[axis] = v.shape[0]
    return v.reshape(shape)


def _pulse(t, t0, tau, omega):
    """高斯包络带载波脉冲（软源波形）。"""
    z = (t - t0) / tau
    return math.exp(-z * z) * math.cos(omega * (t - t0))


# ---------------------------------------------------------------------------
# 每轴吸收系数装配
# ---------------------------------------------------------------------------
def _axis_coefs(n, mode, absorber, dt, dl, n_abs, sigma_max, order,
                kappa_max, alpha_max, r_target, sponge_target_exp, eps_bg):
    """一个轴上的吸收系数。mode='pbc' ⇒ 空吸收器（σ=0, κ=1）。"""
    if mode == "pbc":
        return null_axis(n)
    if absorber == "cpml":
        return cpml_axis(n, n_abs, dt, dl, order=order, kappa_max=kappa_max,
                         alpha_max=alpha_max, sigma_max=sigma_max,
                         r_target=r_target)
    # ∇-海绵（既有实现的忠实对照）：σ 剖面走 _sponge_1d，**不带** CPML 系数
    #  ⇒ 以空吸收器为底（b≡1 / c≡0 / κ≡1）保证时间步进核只有一条代码路径。
    sig_max = (sponge_target_exp * 3.0 * eps_bg / (dt * n_abs)
               if n_abs >= 1 else 0.0)
    out = null_axis(n)
    out["n_abs"] = int(n_abs)
    out["sigma"] = _sponge_1d(n, n_abs, sig_max)
    out["sigma_max"] = float(sig_max)
    out["null"] = False
    out["sponge"] = True
    return out


def _sponge_damps(cax, modes, shape, dt, dim, eps):
    """海绵阻尼数组（**逐条对齐既有实现**）。

    规则（由 fdtd2d / fdtd3d 的既有装配反推，见模块 docstring 的「忠实对照」）：
      · σ_total = Σ_{吸收轴} σ_axis（广播相加）
      · H 分量 F 的阻尼 = 1/(1 + (1/n_d)·dt·Σ_{a∈F 的导数轴} avg(σ_total, a))
        —— n_d = F 的导数轴个数（2D 为 1、3D 为 2）
      · E 的阻尼 = 1/(1 + dt·σ_total/ε)（**仅 3D**；fdtd2d 只阻尼 H）
    """
    stot = np.zeros(shape, dtype=float)
    for a in range(dim):
        if modes[a] == "pbc":
            continue
        stot = stot + _rs(cax[a]["sigma"], a, dim)
    stot = np.minimum(stot, max((cax[a].get("sigma_max", 0.0) for a in range(dim)),
                                default=0.0))
    out = {"sigma_total": stot}
    if dim == 2:
        out["dampHx"] = 1.0 / (1.0 + dt * _avg_sigma(stot, 1, False))   # Hx 导数轴 = y
        out["dampHy"] = 1.0 / (1.0 + dt * _avg_sigma(stot, 0, False))   # Hy 导数轴 = x
    else:
        out["dampHx"] = 1.0 / (1.0 + 0.5 * dt * (
            _avg_sigma(stot, 1, False) + _avg_sigma(stot, 2, False)))
        out["dampHy"] = 1.0 / (1.0 + 0.5 * dt * (
            _avg_sigma(stot, 0, False) + _avg_sigma(stot, 2, False)))
        out["dampHz"] = 1.0 / (1.0 + 0.5 * dt * (
            _avg_sigma(stot, 0, False) + _avg_sigma(stot, 1, False)))
        out["dampE"] = 1.0 / (1.0 + dt * stot / eps)
    return out


# ---------------------------------------------------------------------------
# 2D TEz 脉冲推进（吸收轴 = axis，另一轴 PBC 且横向均匀）
# ---------------------------------------------------------------------------
def run_pulse_2d(axis, absorber, n_abs, n_long, dl, wl, courant, tau, t0,
                 nsteps, i_src, i_mon, order=DEFAULT_ORDER,
                 kappa_max=DEFAULT_KAPPA_MAX, alpha_max=DEFAULT_ALPHA_MAX,
                 sigma_max=None, r_target=1e-8, sponge_target_exp=12.0,
                 eps_bg=1.0, trans=2):
    """返回 (trace, info)：monitor 处 Ez 的时域波形（门控测量的原始数据）。"""
    dt = dl * courant / math.sqrt(2.0)
    omega = 2.0 * math.pi / wl
    shape = tuple(n_long if a == axis else trans for a in range(2))
    modes = ["pbc" if a != axis else "absorb" for a in range(2)]
    pbc = [m == "pbc" for m in modes]

    cax = [_axis_coefs(shape[a], modes[a], absorber, dt, dl, n_abs, sigma_max,
                       order, kappa_max, alpha_max, r_target, sponge_target_exp,
                       eps_bg) for a in range(2)]
    eps = np.full(shape, eps_bg, dtype=float)

    zero = np.zeros(shape)
    Ez = zero.copy()
    Hx = zero.copy()
    Hy = zero.copy()
    psi_hx_y = zero.copy()      # Hx 的 ∂Ez/∂y
    psi_hy_x = zero.copy()      # Hy 的 ∂Ez/∂x
    psi_e_x = zero.copy()       # Ez 的 ∂Hy/∂x
    psi_e_y = zero.copy()       # Ez 的 ∂Hx/∂y

    kh = [_rs(cax[a]["kappa_h"], a, 2) for a in range(2)]
    bh = [_rs(cax[a]["b_h"], a, 2) for a in range(2)]
    ch = [_rs(cax[a]["c_h"], a, 2) for a in range(2)]
    ke = [_rs(cax[a]["kappa_e"], a, 2) for a in range(2)]
    be = [_rs(cax[a]["b_e"], a, 2) for a in range(2)]
    ce = [_rs(cax[a]["c_e"], a, 2) for a in range(2)]

    damp = (_sponge_damps(cax, modes, shape, dt, 2, eps)
            if absorber == "sponge" else None)

    sl = []
    for a in range(2):
        sl.append(slice(0, shape[a]) if pbc[a] else slice(1, shape[a] - 1))
    sl = tuple(sl)

    trace = np.zeros(nsteps, dtype=float)
    for n in range(nsteps):
        t = n * dt
        # ---- H 半步 ----
        dEz_dy = _diff(Ez, 1, pbc[1])
        psi_hx_y = bh[1] * psi_hx_y + ch[1] * dEz_dy
        Hx -= (dt / dl) * (dEz_dy / kh[1] + psi_hx_y)
        dEz_dx = _diff(Ez, 0, pbc[0])
        psi_hy_x = bh[0] * psi_hy_x + ch[0] * dEz_dx
        Hy += (dt / dl) * (dEz_dx / kh[0] + psi_hy_x)
        if damp is not None:
            Hx *= damp["dampHx"]
            Hy *= damp["dampHy"]
        # ---- E 全步 ----
        dHy_dx = _bdiff(Hy, 0, pbc[0])
        psi_e_x = be[0] * psi_e_x + ce[0] * dHy_dx
        dHx_dy = _bdiff(Hx, 1, pbc[1])
        psi_e_y = be[1] * psi_e_y + ce[1] * dHx_dy
        Ez[sl] += (dt / (eps[sl] * dl)) * (
            (dHy_dx / ke[0] + psi_e_x)[sl] - (dHx_dy / ke[1] + psi_e_y)[sl])
        # ---- 软源（沿 PBC 轴的线源 ⇒ 退化 1D 传播）----
        s = _pulse(t, t0, tau, omega)
        if axis == 0:
            Ez[i_src, :] += s
        else:
            Ez[:, i_src] += s
        # ---- 监视 ----
        trace[n] = float(np.mean(Ez[i_mon, :] if axis == 0 else Ez[:, i_mon]))

    return trace, {"dt": dt, "dl": dl, "shape": shape, "modes": modes}


# ---------------------------------------------------------------------------
# 门控测量
# ---------------------------------------------------------------------------
def _gated(trace, dt, tc, w):
    """窗口 [tc−w, tc+w] 内的峰值与能量。"""
    i0 = max(0, int(round((tc - w) / dt)))
    i1 = min(len(trace), int(round((tc + w) / dt)) + 1)
    if i1 <= i0:
        return 0.0, 0.0, (i0, i1)
    seg = trace[i0:i1]
    return float(np.max(np.abs(seg))), float(np.sum(seg * seg)), (i0, i1)


def measure_reflection(dim=2, axis=0, absorber="cpml", n_abs=40, *,
                       wl=2.0, dl_factor=40, courant=0.95, tau_periods=1.5,
                       n_long=None, order=DEFAULT_ORDER,
                       kappa_max=DEFAULT_KAPPA_MAX, alpha_max=DEFAULT_ALPHA_MAX,
                       sigma_max=None, r_target=1e-8, sponge_target_exp=12.0,
                       window_slack=1.0, return_trace=False):
    """测量吸收轴边界回反射系数 Γ。

    Γ = √(ΣE²_回波 / ΣE²_入射)，**同点比值** ⇒ 无需绝对定标。
    几何：源在 `i_src`，监视在 `i_mon = i_src − 60格`；左边界回波到达
    `t_ref = t_inc + 2·i_src·dl`；右边界回波到达时间一并算出并**断言与左回波
    窗口不重叠**（否则测量不可信 ⇒ 直接报错，不静默）。
    """
    dl = wl / float(dl_factor)
    dt = dl * courant / (math.sqrt(2.0) if dim == 2 else math.sqrt(3.0))
    tau = tau_periods * wl
    t0 = 6.0 * tau
    if n_long is None:
        n_long = 1600
    gap = 60
    i_src = int(n_long) // 4
    i_mon = i_src - gap
    if i_mon < 1:
        raise ValueError("n_long 太小：监视点落在边界上")

    # 🔴 时标必须用**脉冲前沿**（t0 − 5τ，包络 exp(−25) ≈ 1.4e-11 ⇒ 低于双精度
    #    相对分辨率），不能用脉冲中心：脉冲尾部会先于中心到达吸收层 ⇒ 其回波会
    #    **先**回到监视点，污染入射窗。首版用中心定时 ⇒ 入射窗混入 8e-2 回波；
    #    改用 3τ 后残差降到 1.5e-6（仍非零）⇒ 取 5τ 才够「逐位」。
    t_front = t0 - 5.0 * tau
    t_inc = t0 + (i_src - i_mon) * dl
    # 回波中心到达时间：脉冲中心抵达边界后**折返 i_mon 格**回到监视点
    # （首版误写成 2·i_src·dl，等于假定监视点贴边界 ⇒ 回波窗整体偏移 6 个时间单位）
    t_ref = t_inc + 2.0 * i_mon * dl
    w = 2.5 * tau + 0.5 * n_abs * dl + window_slack
    # 最早可能的回波到达（从吸收层**内边缘**折返）—— 入射窗必须早于它
    t_refl_min = (t_front + (i_src - n_abs) * dl + (i_mon - n_abs) * dl)
    t_refl_other = t_front + 2.0 * (n_long - 1 - i_src) * dl

    if t_inc <= w:
        raise ValueError("入射窗被 t=0 截断：t_inc %.3f ≤ w %.3f" % (t_inc, w))
    if t_inc + w > t_refl_min:
        raise ValueError("入射窗混入回波：%.3f > 最早回波 %.3f（须缩小 w）"
                         % (t_inc + w, t_refl_min))
    if t_ref - t_inc <= 2.0 * w:
        raise ValueError("入射窗与回波窗重叠：%.3f ≤ 2w %.3f"
                         % (t_ref - t_inc, 2.0 * w))
    if t_refl_other - t_ref <= 2.0 * w:
        raise ValueError("另一端回波进入回波窗：%.3f ≤ 2w %.3f"
                         % (t_refl_other - t_ref, 2.0 * w))
    d_left = i_src * dl
    if d_left <= n_abs * dl + 2.0 * tau:
        raise ValueError("源离边界太近：d_left %.3f ≤ 吸收层 %.3f + 脉冲 %.3f"
                         % (d_left, n_abs * dl, 2.0 * tau))

    nsteps = int(math.ceil((t_ref + w + 2.0) / dt)) + 2
    fn = run_pulse_2d if dim == 2 else run_pulse_3d
    trace, info = fn(axis, absorber, n_abs, n_long, dl, wl, courant, tau, t0,
                     nsteps, i_src, i_mon, order=order, kappa_max=kappa_max,
                     alpha_max=alpha_max, sigma_max=sigma_max,
                     r_target=r_target, sponge_target_exp=sponge_target_exp)

    a_inc, e_inc, wi = _gated(trace, dt, t_inc, w)
    a_ref, e_ref, wr = _gated(trace, dt, t_ref, w)
    gamma = math.sqrt(e_ref / e_inc) if e_inc > 0.0 else float("inf")
    gamma_peak = a_ref / a_inc if a_inc > 0.0 else float("inf")
    out = {
        "dim": dim, "axis": axis, "absorber": absorber, "n_abs": n_abs,
        "dl": dl, "dt": dt, "n_long": n_long, "nsteps": nsteps,
        "t_inc": t_inc, "t_ref": t_ref, "t_ref_other": t_refl_other,
        "t_refl_min": t_refl_min, "window": w,
        # 无回波污染的时间窗（用于「传播子逐位一致」断言）
        "idx_pure": int(min(len(trace), math.floor(t_refl_min / dt))),
        "gamma": gamma, "gamma_peak": gamma_peak,
        "incident_peak": a_inc, "reflected_peak": a_ref,
        "idx_inc": wi, "idx_ref": wr,
        "sigma_max": (float(sigma_max) if sigma_max is not None
                      else (0.0 if absorber != "cpml" else float(
                          cpml_axis(n_long, n_abs, dt, dl, order=order,
                                    kappa_max=kappa_max, alpha_max=alpha_max,
                                    r_target=r_target)["sigma_max"]))),
        "modes": info["modes"], "shape": info["shape"],
    }
    if return_trace:
        out["trace"] = trace
    return out


# ---------------------------------------------------------------------------
# 3D 全 Yee 脉冲推进（吸收轴 = axis，另两轴 PBC 且横向均匀）
# ---------------------------------------------------------------------------
def run_pulse_3d(axis, absorber, n_abs, n_long, dl, wl, courant, tau, t0,
                 nsteps, i_src, i_mon, order=DEFAULT_ORDER,
                 kappa_max=DEFAULT_KAPPA_MAX, alpha_max=DEFAULT_ALPHA_MAX,
                 sigma_max=None, r_target=1e-8, sponge_target_exp=12.0,
                 eps_bg=1.0, trans=2):
    """返回 (trace, info)：monitor 处 Ez 的时域波形（2D 版的 3D 全 Yee 同构）。"""
    dt = dl * courant / math.sqrt(3.0)
    omega = 2.0 * math.pi / wl
    shape = tuple(n_long if a == axis else trans for a in range(3))
    modes = ["pbc" if a != axis else "absorb" for a in range(3)]
    pbc = [m == "pbc" for m in modes]

    cax = [_axis_coefs(shape[a], modes[a], absorber, dt, dl, n_abs, sigma_max,
                       order, kappa_max, alpha_max, r_target, sponge_target_exp,
                       eps_bg) for a in range(3)]
    eps = np.full(shape, eps_bg, dtype=float)

    zero = np.zeros(shape)
    Ex, Ey, Ez = zero.copy(), zero.copy(), zero.copy()
    Hx, Hy, Hz = zero.copy(), zero.copy(), zero.copy()
    # 源 / 监视用的 E 分量：必须与传播轴垂直（见步进循环里的血案注释）
    src_f = (Ex, Ey, Ez)[(axis + 1) % 3]
    # H 侧 ψ（导数在 H 节点 ⇒ 半格系数）
    ph_xy, ph_xz = zero.copy(), zero.copy()      # ∂Ez/∂y · ∂Ey/∂z
    ph_yz, ph_yx = zero.copy(), zero.copy()      # ∂Ex/∂z · ∂Ez/∂x
    ph_zx, ph_zy = zero.copy(), zero.copy()      # ∂Ey/∂x · ∂Ex/∂y
    # E 侧 ψ（导数在 E 节点 ⇒ 整格系数）
    pe_zy, pe_yz = zero.copy(), zero.copy()      # ∂Hz/∂y · ∂Hy/∂z
    pe_xz, pe_zx = zero.copy(), zero.copy()      # ∂Hx/∂z · ∂Hz/∂x
    pe_yx, pe_xy = zero.copy(), zero.copy()      # ∂Hy/∂x · ∂Hx/∂y

    kh = [_rs(cax[a]["kappa_h"], a, 3) for a in range(3)]
    bh = [_rs(cax[a]["b_h"], a, 3) for a in range(3)]
    ch = [_rs(cax[a]["c_h"], a, 3) for a in range(3)]
    ke = [_rs(cax[a]["kappa_e"], a, 3) for a in range(3)]
    be = [_rs(cax[a]["b_e"], a, 3) for a in range(3)]
    ce = [_rs(cax[a]["c_e"], a, 3) for a in range(3)]

    damp = (_sponge_damps(cax, modes, shape, dt, 3, eps)
            if absorber == "sponge" else None)
    inv_eps_dl = dt / (eps * dl)

    sl = tuple(slice(0, shape[a]) if pbc[a] else slice(1, shape[a] - 1)
               for a in range(3))

    trace = np.zeros(nsteps, dtype=float)
    for n in range(nsteps):
        t = n * dt
        # ---- H 半步 ----
        dEz_dy = _diff(Ez, 1, pbc[1])
        dEy_dz = _diff(Ey, 2, pbc[2])
        ph_xy = bh[1] * ph_xy + ch[1] * dEz_dy
        ph_xz = bh[2] * ph_xz + ch[2] * dEy_dz
        Hx -= (dt / dl) * ((dEz_dy / kh[1] + ph_xy) - (dEy_dz / kh[2] + ph_xz))

        dEx_dz = _diff(Ex, 2, pbc[2])
        dEz_dx = _diff(Ez, 0, pbc[0])
        ph_yz = bh[2] * ph_yz + ch[2] * dEx_dz
        ph_yx = bh[0] * ph_yx + ch[0] * dEz_dx
        Hy -= (dt / dl) * ((dEx_dz / kh[2] + ph_yz) - (dEz_dx / kh[0] + ph_yx))

        dEy_dx = _diff(Ey, 0, pbc[0])
        dEx_dy = _diff(Ex, 1, pbc[1])
        ph_zx = bh[0] * ph_zx + ch[0] * dEy_dx
        ph_zy = bh[1] * ph_zy + ch[1] * dEx_dy
        Hz -= (dt / dl) * ((dEy_dx / kh[0] + ph_zx) - (dEx_dy / kh[1] + ph_zy))
        if damp is not None:
            Hx *= damp["dampHx"]
            Hy *= damp["dampHy"]
            Hz *= damp["dampHz"]
        # ---- E 全步 ----
        dHz_dy = _bdiff(Hz, 1, pbc[1])
        dHy_dz = _bdiff(Hy, 2, pbc[2])
        pe_zy = be[1] * pe_zy + ce[1] * dHz_dy
        pe_yz = be[2] * pe_yz + ce[2] * dHy_dz
        Ex[sl] += inv_eps_dl[sl] * ((dHz_dy / ke[1] + pe_zy)[sl]
                                    - (dHy_dz / ke[2] + pe_yz)[sl])

        dHx_dz = _bdiff(Hx, 2, pbc[2])
        dHz_dx = _bdiff(Hz, 0, pbc[0])
        pe_xz = be[2] * pe_xz + ce[2] * dHx_dz
        pe_zx = be[0] * pe_zx + ce[0] * dHz_dx
        Ey[sl] += inv_eps_dl[sl] * ((dHx_dz / ke[2] + pe_xz)[sl]
                                    - (dHz_dx / ke[0] + pe_zx)[sl])

        dHy_dx = _bdiff(Hy, 0, pbc[0])
        dHx_dy = _bdiff(Hx, 1, pbc[1])
        pe_yx = be[0] * pe_yx + ce[0] * dHy_dx
        pe_xy = be[1] * pe_xy + ce[1] * dHx_dy
        Ez[sl] += inv_eps_dl[sl] * ((dHy_dx / ke[0] + pe_yx)[sl]
                                    - (dHx_dy / ke[1] + pe_xy)[sl])
        if damp is not None:
            Ex *= damp["dampE"]
            Ey *= damp["dampE"]
            Ez *= damp["dampE"]
        # ---- 软源（垂直吸收轴的平面源 ⇒ 退化 1D 传播）----
        # 🔴 源的偏振必须是**与传播轴垂直**的 E 分量：沿 z 传播时 Ez 是**纵向**
        #    分量、根本不辐射（首版实测 e_inc ≡ 0 ⇒ Γ = inf）。取「循环下一位」
        #    的 E 分量即可（x→Ey / y→Ez / z→Ex 全部垂直于传播轴）。
        s = _pulse(t, t0, tau, omega)
        if axis == 0:
            src_f[i_src, :, :] += s
        elif axis == 1:
            src_f[:, i_src, :] += s
        else:
            src_f[:, :, i_src] += s
        # ---- 监视 ----
        if axis == 0:
            trace[n] = float(np.mean(src_f[i_mon, :, :]))
        elif axis == 1:
            trace[n] = float(np.mean(src_f[:, i_mon, :]))
        else:
            trace[n] = float(np.mean(src_f[:, :, i_mon]))

    return trace, {"dt": dt, "dl": dl, "shape": shape, "modes": modes}


if __name__ == "__main__":
    # 快速自检：只打印实测值，不做判据（判据在 run_cpml_absorber_smoke.py）
    print("=" * 78)
    print("fdtd_cpml 自检：CPML vs 梯度海绵（层厚 40）· 无吸收对照")
    print("=" * 78)
    for d in (2, 3):
        for ax in range(d):
            gs = measure_reflection(dim=d, axis=ax, absorber="sponge", n_abs=40)
            gc = measure_reflection(dim=d, axis=ax, absorber="cpml", n_abs=40,
                                    sigma_max=18.0)
            gn = measure_reflection(dim=d, axis=ax, absorber="cpml", n_abs=0)
            print("dim=%d axis=%s  Γ_sponge=%.6e  Γ_cpml=%.6e  改善 %.1f×  "
                  "Γ_无吸收=%.4f  (nsteps=%d shape=%s)"
                  % (d, "xyz"[ax], gs["gamma"], gc["gamma"],
                     gs["gamma"] / gc["gamma"] if gc["gamma"] > 0
                     else float("inf"),
                     gn["gamma"], gc["nsteps"], gc["shape"]))

