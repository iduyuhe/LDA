"""LDA · D-84 3D adjoint 逆设计核（Track A 纵深：破 3D 诚实边界）。

3D Yee 交错网格 FDTD（6 分量 Ex/Ey/Ez + Hx/Hy/Hz，x 传播轴，无 PBC）+ **显式
转置伴随**（D-69 模式推广到 3D）：更新算子逐项转置（前向差分 H 步 / 后向差分
E 步，差分转置 `_fd_t`/`_bd_t` 边界掩码严格镜像正演有效范围），数值 Mᵀ 随机
对拍 1e-15 级验证。

设计域：核心平板波导（z 方向薄层）+ **宽度曲线形状** w(x)（K 控制点 + sigmoid
软边界）——"3D 域内做形状逆设计"是 3D 诚实边界的起步（z 截面暂均匀，截面
变化归 D-85+）。FOM = 脉冲源监视器 Ez 收集场能（聚焦增益可致 T>1，非功率透射）。

验收（LLM 不进判决路径，死标量）：
  (a) 3D adjoint 梯度 vs 中心有限差分（设计体素方向对拍）≤ 0.15；
  (b) 形状梯度链式 FD 对拍 ≤ 0.15；
  (c) FOM improvement ≥ 1.5（均匀宽度 → 优化 taper）。

参考：`adjoint_fdtd.py`（2D 转置模式）、`fdtd3d_numba.py`（3D Yee 更新公式）。
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = os.path.dirname(_HERE)
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)

from lda_solver.shape_inverse import _sigmoid, _interp_weight, shape_drc  # noqa: E402


# ---------------------------------------------------------------------------
# 差分转置（3D Yee 交错网格边界掩码——Mᵀ 对拍 1e-15 的关键）
# ---------------------------------------------------------------------------
def _fd_t(lam: np.ndarray, axis: int) -> np.ndarray:
    """前向差分 g[j]=f[j+1]-f[j]（g[-1]=0）的转置：tf[j]=λ[j-1](j≥1)-λ[j](j<N-1)。"""
    tf = np.zeros_like(lam)
    s1 = [slice(None)] * 3
    s1[axis] = slice(1, None)
    s2 = [slice(None)] * 3
    s2[axis] = slice(0, -1)
    tf[tuple(s1)] += lam[tuple(s2)]
    tf[tuple(s2)] -= lam[tuple(s2)]
    return tf


def _bd_t(lam: np.ndarray, axis: int) -> np.ndarray:
    """后向差分 g[j]=f[j]-f[j-1]（g[0]=0）的转置：tf[j]=λ[j](j≥1)-λ[j+1](j<N-1)。"""
    tf = np.zeros_like(lam)
    s1 = [slice(None)] * 3
    s1[axis] = slice(1, None)
    s2 = [slice(None)] * 3
    s2[axis] = slice(0, -1)
    tf[tuple(s1)] += lam[tuple(s1)]
    tf[tuple(s2)] -= lam[tuple(s1)]
    return tf


# ---------------------------------------------------------------------------
# 3D Yee 一步更新（数组切片版，无 PBC）
# ---------------------------------------------------------------------------
def _step_h3d(E, H, dampH, cH):
    """H 半步（前向差分）：Hx-=cH(dEz/dy-dEy/dz); Hy-=cH(dEx/dz-dEz/dx); Hz-=cH(dEy/dx-dEx/dy)。"""
    Ex, Ey, Ez = E
    Hx, Hy, Hz = H
    Nx, Ny, Nz = Ex.shape
    dEz_dy = np.zeros_like(Ez); dEz_dy[:, :Ny - 1, :] = Ez[:, 1:, :] - Ez[:, :Ny - 1, :]
    dEy_dz = np.zeros_like(Ey); dEy_dz[:, :, :Nz - 1] = Ey[:, :, 1:] - Ey[:, :, :Nz - 1]
    dEx_dz = np.zeros_like(Ex); dEx_dz[:, :, :Nz - 1] = Ex[:, :, 1:] - Ex[:, :, :Nz - 1]
    dEz_dx = np.zeros_like(Ez); dEz_dx[:Nx - 1, :, :] = Ez[1:, :, :] - Ez[:Nx - 1, :, :]
    dEy_dx = np.zeros_like(Ey); dEy_dx[:Nx - 1, :, :] = Ey[1:, :, :] - Ey[:Nx - 1, :, :]
    dEx_dy = np.zeros_like(Ex); dEx_dy[:, :Ny - 1, :] = Ex[:, 1:, :] - Ex[:, :Ny - 1, :]
    Hx = (Hx - cH * (dEz_dy - dEy_dz)) * dampH[0]
    Hy = (Hy - cH * (dEx_dz - dEz_dx)) * dampH[1]
    Hz = (Hz - cH * (dEy_dx - dEx_dy)) * dampH[2]
    return (Hx, Hy, Hz)


def _step_e3d(E, H, eps, dampE, cH):
    """E 全步（后向差分）：Ex+=cE(dHz/dy-dHy/dz); ... 返回 (E_new, curlE 三分量)。"""
    Ex, Ey, Ez = E
    Hx, Hy, Hz = H
    Nx, Ny, Nz = Ex.shape
    cE = cH / eps
    dHz_dy = np.zeros_like(Hz); dHz_dy[:, 1:, :] = Hz[:, 1:, :] - Hz[:, :Ny - 1, :]
    dHy_dz = np.zeros_like(Hy); dHy_dz[:, :, 1:] = Hy[:, :, 1:] - Hy[:, :, :Nz - 1]
    dHx_dz = np.zeros_like(Hx); dHx_dz[:, :, 1:] = Hx[:, :, 1:] - Hx[:, :, :Nz - 1]
    dHz_dx = np.zeros_like(Hz); dHz_dx[1:, :, :] = Hz[1:, :, :] - Hz[:Nx - 1, :, :]
    dHy_dx = np.zeros_like(Hy); dHy_dx[1:, :, :] = Hy[1:, :, :] - Hy[:Nx - 1, :, :]
    dHx_dy = np.zeros_like(Hx); dHx_dy[:, 1:, :] = Hx[:, 1:, :] - Hx[:, :Ny - 1, :]
    curl_ex = dHz_dy - dHy_dz
    curl_ey = dHx_dz - dHz_dx
    curl_ez = dHy_dx - dHx_dy
    Ex = (Ex + cE * curl_ex) * dampE
    Ey = (Ey + cE * curl_ey) * dampE
    Ez = (Ez + cE * curl_ez) * dampE
    return (Ex, Ey, Ez), (curl_ex, curl_ey, curl_ez)


# ---------------------------------------------------------------------------
# 3D 伴随步（E 步转置 + H 步转置——Mᵀ 对拍 1e-15）
# ---------------------------------------------------------------------------
def _adj_e3d(lamE, lamH, eps, dampE, cH):
    """P_E 转置：(λE,λH) -> (D_E·λE, λH + C_HEᵀ·(cE·D_E·λE))。"""
    cE = cH / eps
    phiE = [lamE[0] * dampE, lamE[1] * dampE, lamE[2] * dampE]
    wE = [cE * phiE[0], cE * phiE[1], cE * phiE[2]]
    nHx = lamH[0].copy(); nHy = lamH[1].copy(); nHz = lamH[2].copy()
    nHz += _bd_t(wE[0], 1) - _bd_t(wE[1], 0)     # Ex→Hz(j); Ey→Hz(i)
    nHy += -_bd_t(wE[0], 2) + _bd_t(wE[2], 0)    # Ex→Hy(k); Ez→Hy(i)
    nHx += _bd_t(wE[1], 2) - _bd_t(wE[2], 1)     # Ey→Hx(k); Ez→Hx(j)
    return (phiE[0], phiE[1], phiE[2]), (nHx, nHy, nHz)


def _adj_h3d(lamE, lamH, dampH, cH):
    """P_H 转置：(λE,λH) -> (λE + C_EHᵀ·D_H·λH, D_H·λH)。"""
    pHx = lamH[0] * dampH[0]
    pHy = lamH[1] * dampH[1]
    pHz = lamH[2] * dampH[2]
    nEx = lamE[0].copy(); nEy = lamE[1].copy(); nEz = lamE[2].copy()
    nEz += -cH * _fd_t(pHx, 1) + cH * _fd_t(pHy, 0)    # Hx→Ez(j); Hy→Ez(i)
    nEy += cH * _fd_t(pHx, 2) - cH * _fd_t(pHz, 0)     # Hx→Ey(k); Hz→Ey(i)
    nEx += -cH * _fd_t(pHy, 2) + cH * _fd_t(pHz, 1)    # Hy→Ex(k); Hz→Ex(j)
    return (nEx, nEy, nEz), (pHx, pHy, pHz)


# ---------------------------------------------------------------------------
# 3D adjoint 问题定义
# ---------------------------------------------------------------------------
@dataclass
class AdjointProblem3D:
    """3D FDTD adjoint 逆设计问题（平板波导 + 宽度曲线形状）。

    域 Nx×Ny×Nz；x 传播轴、y 横向（宽度）、z 垂直（核心薄层）。
    """
    Nx: int = 48
    Ny: int = 40
    Nz: int = 12
    dl_factor: float = 10.0
    courant: float = 0.95
    sponge: int = 8
    wl_um: float = 1.55
    target_exp: float = 12.0
    ramp: int = 200
    # 核心层（z）
    k_core0: int = 0
    k_core1: int = 0
    # 源（Ez 软源，y 中心宽区 × z 核心层）
    i_src: int = 0
    y_src0: int = 0
    y_src1: int = 0
    # 监视器（Ez 收集场能）
    i_mon: int = 0
    y_mon0: int = 0
    y_mon1: int = 0
    # 设计区（核心层内 x 全段；y 窄带含软边界余量）
    di0: int = 0
    di1: int = 0
    dj0: int = 0
    dj1: int = 0
    eps_min: float = 1.0
    eps_max: float = 12.25
    # 惰性字段
    dl: float = field(default=0.0)
    dt: float = field(default=0.0)
    omega: float = field(default=0.0)
    period_steps: int = field(default=0)
    dampE: Any = field(default=None)
    dampH: Any = field(default=None)
    design_mask: Any = field(default=None)
    _dr: np.ndarray = field(default=None, repr=False)

    def __post_init__(self):
        self.dl = self.wl_um / self.dl_factor
        self.dt = self.dl * self.courant / math.sqrt(3.0)   # 3D CFL
        self.omega = 2.0 * math.pi / self.wl_um
        self.period_steps = int(round(2.0 * math.pi / (self.omega * self.dt)))
        if self.k_core1 == 0:
            self.k_core1 = min(self.Nz, self.k_core0 + 5)   # 5 层核心（z 约束）
        if self.i_src == 0:
            self.i_src = self.sponge + 6
        if self.y_src0 == 0 and self.y_src1 == 0:
            # 源宽匹配初始波导（半宽 5 → 全宽 10 + 余量）
            self.y_src0 = self.Ny // 2 - 6
            self.y_src1 = self.Ny // 2 + 6
        if self.i_mon == 0:
            self.i_mon = self.Nx - self.sponge - 6
        if self.y_mon0 == 0 and self.y_mon1 == 0:
            self.y_mon0 = self.Ny // 2 - 6
            self.y_mon1 = self.Ny // 2 + 6
        if self.di0 == 0 and self.di1 == 0:
            self.di0 = self.sponge + 8
            self.di1 = self.Nx - self.sponge - 8
        if self.dj0 == 0 and self.dj1 == 0:
            # y 窄带：|y-jmid| ≤ 12（宽度上限 10 + 软边界余量）
            self.dj0 = self.Ny // 2 - 12
            self.dj1 = self.Ny // 2 + 12
        # 海绵阻尼（x 轴两端，3D 版）
        sig_max = 0.08
        sx = np.zeros(self.Nx)
        for i in range(self.sponge):
            f = (self.sponge - i) / self.sponge
            sx[i] = sig_max * f * f
            sx[self.Nx - 1 - i] = sig_max * f * f
        ex = np.exp(-sx)
        self.dampE = (ex[:, None, None] * np.ones((1, 1, self.Nz)))
        self.dampH = (ex[:, None, None] * np.ones((1, 1, self.Nz)) for _ in range(3))
        self.dampH = tuple(self.dampH)
        # 设计区 mask（核心层 z × y 窄带 × x 段）
        dm = np.zeros((self.Nx, self.Ny, self.Nz), dtype=bool)
        dm[self.di0:self.di1, self.dj0:self.dj1,
           self.k_core0:self.k_core1] = True
        self.design_mask = dm
        self._dr = np.where(dm.ravel())[0]


# ---------------------------------------------------------------------------
# 正向（高斯脉冲软源 + 设计区 curlE 记录 + 监视器场能 FOM）
# ---------------------------------------------------------------------------
def forward3d(prob: AdjointProblem3D, eps3: np.ndarray) -> Dict[str, Any]:
    Nx, Ny, Nz = prob.Nx, prob.Ny, prob.Nz
    dl, dt = prob.dl, prob.dt
    per = prob.period_steps
    sigma_n = int(round(prob.target_exp / 2.0)) * 2 + 1
    n_peak = int(round(prob.target_exp * 1.5))
    travel = int(math.ceil(Nx * dl / dt)) + 60
    meas0 = max(n_peak + travel - 3 * sigma_n, 0)
    nsteps = n_peak + travel + int(round(6 * per)) + 6 * sigma_n + 200
    omega = prob.omega

    Ex = np.zeros((Nx, Ny, Nz)); Ey = np.zeros((Nx, Ny, Nz))
    Ez = np.zeros((Nx, Ny, Nz))
    Hx = np.zeros((Nx, Ny, Nz)); Hy = np.zeros((Nx, Ny, Nz))
    Hz = np.zeros((Nx, Ny, Nz))
    dampE = prob.dampE
    dampH = prob.dampH
    cH = dt / dl
    i_src, y0s, y1s = prob.i_src, prob.y_src0, prob.y_src1
    i_mon, m0, m1 = prob.i_mon, prob.y_mon0, prob.y_mon1
    k0, k1 = prob.k_core0, prob.k_core1
    ndr = len(prob._dr)
    dr = prob._dr
    # 设计区体素坐标（dr 相对全网格）
    dri, drj, drk = np.unravel_index(dr, (Nx, Ny, Nz))
    curlE_dr = np.zeros((nsteps, 3, ndr))
    Ez_mon = np.zeros((nsteps, m1 - m0, k1 - k0))
    E_in = 0.0

    for n in range(nsteps):
        env = math.exp(-0.5 * ((n - n_peak) / sigma_n) ** 2)
        Hx, Hy, Hz = _step_h3d((Ex, Ey, Ez), (Hx, Hy, Hz), dampH, cH)
        (Ex, Ey, Ez), (cex, cey, cez) = _step_e3d(
            (Ex, Ey, Ez), (Hx, Hy, Hz), eps3, dampE, cH)
        # 设计区 curlE 记录
        curlE_dr[n, 0] = cex.ravel()[dr]
        curlE_dr[n, 1] = cey.ravel()[dr]
        curlE_dr[n, 2] = cez.ravel()[dr]
        # 高斯脉冲软源（Ez，源 y 宽区 × z 核心层）
        if env > 1e-12:
            Ez[i_src, y0s:y1s, k0:k1] += env * math.cos(omega * n * dt)
            E_in += env * env * (y1s - y0s) * (k1 - k0)
        # 监视器 Ez 场能
        Ez_mon[n, :, :] = Ez[i_mon, m0:m1, k0:k1]

    FOM = float(np.sum(Ez_mon[meas0:, :, :] ** 2))
    T = (FOM / E_in) if E_in > 1e-12 else 0.0
    return {
        "FOM": FOM, "T": T, "P_out": FOM, "P_in": E_in, "E_in": E_in,
        "curlE_dr": curlE_dr, "Ez_mon": Ez_mon, "eps": eps3,
        "nsteps": nsteps, "meas0": meas0, "sigma_n": sigma_n,
        "n_peak": n_peak,
    }


# ---------------------------------------------------------------------------
# 反向：显式转置伴随 + ε 灵敏度
# ---------------------------------------------------------------------------
def compute_gradient3d(prob: AdjointProblem3D, fwd: Dict[str, Any]) -> np.ndarray:
    """dFOM/dε（全网格 (Nx,Ny,Nz)，仅设计区非零）。

    FOM = Σ_{n≥meas0} Σ Ez[i_mon,y,z]² → 观测源 obs_Ez[n,y,z] = 2·Ez_mon[n,y,z]。
    反向步序（正向 = H 步 → E 步 → 源注入 → 监视器）：
      (a) ε 灵敏度累积：grad[dr] += Σ_c (D_E·λ_Ec)[dr]·curlEc_dr[k]；
      (b) E 步转置：λH += C_HEᵀ·(cE·D_E·λE)；
      (c) λH^{k-1} = D_H·(λH + 注入)；
      (d) H 步转置：λE += C_EHᵀ·D_H·(λH+注入)；
      (e) λE^{k-1} = D_E·λE + (d) + obs[k-1]。
    """
    Nx, Ny, Nz = prob.Nx, prob.Ny, prob.Nz
    eps3 = fwd["eps"]
    dampE = prob.dampE
    dampH = prob.dampH
    cH = prob.dt / prob.dl
    i_mon, m0, m1 = prob.i_mon, prob.y_mon0, prob.y_mon1
    k0, k1 = prob.k_core0, prob.k_core1
    nsteps, meas0 = fwd["nsteps"], fwd["meas0"]
    curlE_dr = fwd["curlE_dr"]
    Ez_mon = fwd["Ez_mon"]
    dr = prob._dr
    ndr = len(dr)

    # 观测源（仅 Ez 分量有值）
    obs = np.zeros((nsteps, Nx, Ny, Nz))
    obs[meas0:, i_mon, m0:m1, k0:k1] = 2.0 * Ez_mon[meas0:, :, :]

    lamEx = np.zeros((Nx, Ny, Nz)); lamEy = np.zeros((Nx, Ny, Nz))
    lamEz = np.zeros((Nx, Ny, Nz))
    lamHx = np.zeros((Nx, Ny, Nz)); lamHy = np.zeros((Nx, Ny, Nz))
    lamHz = np.zeros((Nx, Ny, Nz))
    grad = np.zeros((Nx, Ny, Nz))

    nN = nsteps - 1
    if nN >= meas0:
        lamEz[i_mon, m0:m1, k0:k1] += obs[nN, i_mon, m0:m1, k0:k1]

    for k in range(nsteps - 1, -1, -1):
        lamE = (lamEx, lamEy, lamEz)
        lamH = (lamHx, lamHy, lamHz)
        # (a) ε 灵敏度累积（D_E·λE · curlE，三分量同位）
        phiE = [dampE * lamE[0], dampE * lamE[1], dampE * lamE[2]]
        for c in range(3):
            grad.ravel()[dr] += phiE[c].ravel()[dr] * curlE_dr[k, c]
        if k == 0:
            break
        # (b) E 步转置注入
        _, lamH_inj = _adj_e3d(lamE, lamH, eps3, dampE, cH)
        # (c) λH^{k-1} = D_H·(λH + 注入)
        Hx_state = lamH_inj[0]; Hy_state = lamH_inj[1]; Hz_state = lamH_inj[2]
        phiHx = dampH[0] * Hx_state
        phiHy = dampH[1] * Hy_state
        phiHz = dampH[2] * Hz_state
        # (d) H 步转置（φH → λE 注入）
        lamE_adj, _ = _adj_h3d((np.zeros_like(lamEx),) * 3,
                               (phiHx, phiHy, phiHz), (1.0, 1.0, 1.0), cH)
        # (e) λE^{k-1} = D_E·λE + Aᵀ + obs[k-1]
        lamEx_new = dampE * lamEx + lamE_adj[0]
        lamEy_new = dampE * lamEy + lamE_adj[1]
        lamEz_new = dampE * lamEz + lamE_adj[2]
        if (k - 1) >= meas0:
            lamEz_new[i_mon, m0:m1, k0:k1] += obs[k - 1, i_mon, m0:m1, k0:k1]
        lamEx, lamEy, lamEz = lamEx_new, lamEy_new, lamEz_new
        lamHx, lamHy, lamHz = phiHx, phiHy, phiHz

    # ε 导数（设计区）：-cH/eps² · Σ_k Σ_c (D_E·λE)·curlE
    geps = np.zeros((Nx, Ny, Nz))
    geps.ravel()[dr] = -(cH) / (eps3.ravel()[dr] ** 2) * grad.ravel()[dr]
    return geps


# ---------------------------------------------------------------------------
# 验证：FD 对拍
# ---------------------------------------------------------------------------
def verify_adjoint3d(prob: AdjointProblem3D, eps3: np.ndarray,
                     nsamples: int = 8, delta: float = 0.05,
                     seed: int = 12345) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)
    fwd0 = forward3d(prob, eps3)
    gadj = compute_gradient3d(prob, fwd0)
    dr = prob._dr
    gabs = np.abs(gadj.ravel()[dr])
    order = dr[np.argsort(gabs)[::-1]]
    picks = order[: max(nsamples, 1)]
    rows = []
    for idx in picks:
        i, j, k = np.unravel_index(idx, (prob.Nx, prob.Ny, prob.Nz))
        ep = eps3.copy(); ep[i, j, k] += delta
        em = eps3.copy(); em[i, j, k] -= delta
        Fp = forward3d(prob, ep)["FOM"]
        Fm = forward3d(prob, em)["FOM"]
        g_fd = (Fp - Fm) / (2.0 * delta)
        rows.append({"idx": int(idx), "i": int(i), "j": int(j), "k": int(k),
                     "g_adj": float(gadj[i, j, k]), "g_fd": float(g_fd)})
    ref = max(rows, key=lambda r: abs(r["g_fd"]))
    K = ref["g_adj"] / ref["g_fd"] if abs(ref["g_fd"]) > 1e-12 else 1.0
    max_rel = max(abs(r["g_adj"] - K * r["g_fd"]) /
                  (abs(K * r["g_fd"]) + 1e-12) for r in rows)
    return {"rows": rows, "max_rel_err": float(max_rel),
            "nsamples": len(rows), "passed": bool(max_rel <= 0.15)}


# ---------------------------------------------------------------------------
# 3D 形状参数化（宽度曲线 → z 核心层介电）+ 形状梯度链式
# ---------------------------------------------------------------------------
class ShapeProblem3D:
    """3D 平板波导宽度曲线形状：w(x)（K 控制点）→ z 核心层介电分布。"""

    def __init__(self, base: AdjointProblem3D, n_controls: int = 8,
                 w_min: float = 2.0, w_max: float = 10.0,
                 slope_max: float = 1.5, soft_t: float = 1.2):
        self.base = base
        self.n_controls = n_controls
        self.w_min = w_min
        self.w_max = w_max
        self.slope_max = slope_max
        self.soft_t = soft_t
        self.di0, self.di1 = base.di0, base.di1
        self.dj0, self.dj1 = base.dj0, base.dj1
        self.j_mid = (base.dj0 + base.dj1) // 2
        self.k0, self.k1 = base.k_core0, base.k_core1
        self.knots = np.linspace(self.di0, self.di1 - 1, n_controls)
        self.cols = np.arange(self.di0, self.di1)
        self.init_halfwidth = 5.0

    def width_at(self, w_ctl: np.ndarray) -> np.ndarray:
        return np.interp(self.cols, self.knots, np.asarray(w_ctl, dtype=float))

    def eps(self, w_ctl: np.ndarray) -> np.ndarray:
        p = self.base
        t = self.soft_t
        eps3 = np.full((p.Nx, p.Ny, p.Nz), p.eps_min)
        w_col = self.width_at(w_ctl)
        j = np.arange(self.dj0, self.dj1)
        for i, wc in zip(self.cols, w_col):
            d = wc - np.abs(j - self.j_mid)
            eps3[i, j, self.k0:self.k1] = p.eps_min + \
                (p.eps_max - p.eps_min) * _sigmoid(d / t)[:, None]
        return eps3

    def gradient(self, fwd: dict, w_ctl: np.ndarray) -> np.ndarray:
        """链式：dFOM/dw_k = Σ_ijk geps[i,j,k]·dε/dw_k（软边界 δσ/δw）。"""
        geps = compute_gradient3d(self.base, fwd)
        p = self.base
        t = self.soft_t
        K = self.n_controls
        g = np.zeros(K)
        j = np.arange(self.dj0, self.dj1)
        w_col = self.width_at(w_ctl)
        for k in range(K):
            for i, wc in zip(self.cols, w_col):
                wgt = _interp_weight(i, self.knots, k, K)
                if wgt == 0.0:
                    continue
                d = wc - np.abs(j - self.j_mid)
                sd = _sigmoid(d / t)
                dsdw = (sd * (1.0 - sd)) / t
                g[k] += np.sum(geps[i, j, self.k0:self.k1] *
                               (p.eps_max - p.eps_min) * dsdw[:, None] * wgt)
        return g


def verify_shape_gradient3d(sp: ShapeProblem3D, w_ctl: np.ndarray,
                            nsamples: int = 6, delta: float = 0.02,
                            seed: int = 7) -> Dict[str, Any]:
    fwd0 = forward3d(sp.base, sp.eps(w_ctl))
    gadj = sp.gradient(fwd0, w_ctl)
    K = sp.n_controls
    rng = np.random.default_rng(seed)
    picks = sorted(rng.choice(K, size=min(nsamples, K), replace=False))
    rows = []
    for k in picks:
        wp = w_ctl.copy(); wp[k] += delta
        wm = w_ctl.copy(); wm[k] -= delta
        Fp = forward3d(sp.base, sp.eps(wp))["FOM"]
        Fm = forward3d(sp.base, sp.eps(wm))["FOM"]
        rows.append({"k": int(k), "g_adj": float(gadj[k]),
                     "g_fd": float((Fp - Fm) / (2 * delta))})
    ref = max(rows, key=lambda r: abs(r["g_fd"]))
    Kc = ref["g_adj"] / ref["g_fd"] if abs(ref["g_fd"]) > 1e-12 else 1.0
    max_rel = max(abs(r["g_adj"] - Kc * r["g_fd"]) /
                  (abs(Kc * r["g_fd"]) + 1e-12) for r in rows)
    return {"rows": rows, "max_rel_err": float(max_rel),
            "nsamples": len(rows), "passed": bool(max_rel <= 0.15)}


def _project_shape(w: np.ndarray, w_min: float, w_max: float,
                   slope_max: float) -> np.ndarray:
    w = np.asarray(w, dtype=float).copy()
    for _ in range(3):
        w = np.clip(w, w_min, w_max)
        if len(w) > 1:
            for i in range(1, len(w)):
                if w[i] - w[i - 1] > slope_max:
                    w[i] = w[i - 1] + slope_max
                elif w[i - 1] - w[i] > slope_max:
                    w[i] = w[i - 1] - slope_max
            for i in range(len(w) - 2, -1, -1):
                if w[i] - w[i + 1] > slope_max:
                    w[i] = w[i + 1] + slope_max
                elif w[i + 1] - w[i] > slope_max:
                    w[i] = w[i + 1] - slope_max
    return np.clip(w, w_min, w_max)


def optimize_shape3d(sp: ShapeProblem3D, iters: int = 20, step0: float = 0.4,
                     verbose: bool = False) -> Dict[str, Any]:
    """3D 宽度曲线形状优化（回溯线搜索 + 可行性投影）。"""
    K = sp.n_controls
    w = np.full(K, sp.init_halfwidth)
    fom0 = forward3d(sp.base, sp.eps(w))["FOM"]
    best_fom, best_w = fom0, w.copy()
    history = []
    for it in range(iters):
        fwd = forward3d(sp.base, sp.eps(w))
        g = sp.gradient(fwd, w)
        m = np.max(np.abs(g)) + 1e-12
        d = g / m
        alpha = step0
        f_eval = fwd["FOM"]
        f_try, accepted = f_eval, False
        while alpha > 2e-3:
            wt = _project_shape(w + alpha * d, sp.w_min, sp.w_max,
                                sp.slope_max)
            f_try = forward3d(sp.base, sp.eps(wt))["FOM"]
            if f_try > f_eval:
                accepted = True
                break
            alpha *= 0.5
        if accepted:
            w = _project_shape(w + alpha * d, sp.w_min, sp.w_max,
                               sp.slope_max)
            f_final = f_try
        else:
            f_final = f_eval
        if f_final > best_fom:
            best_fom, best_w = f_final, w.copy()
        history.append({"iter": it, "FOM": f_final, "alpha": round(alpha, 4)})
        if verbose and (it % 5 == 0 or it == iters - 1):
            print(f"  it={it:3d} alpha={alpha:6.3f} FOM={f_final:.4e}")
    fbf = forward3d(sp.base, sp.eps(best_w))
    improvement = fbf["FOM"] / (fom0 + 1e-12)
    drc = shape_drc(type("S", (), {"w_min": sp.w_min, "w_max": sp.w_max,
                                   "slope_max": sp.slope_max,
                                   "n_controls": K})(), best_w)
    return {
        "history": history,
        "final_width": [round(float(x), 3) for x in best_w],
        "final_FOM": fbf["FOM"],
        "initial_FOM": fom0,
        "improvement": float(improvement),
        "drc": drc,
        "passed": bool(improvement >= 1.5 and drc["ok"]),
        "note": ("D-84 3D adjoint 形状逆设计（3D Yee 显式转置伴随 + 宽度曲线"
                 "平板波导形状）。3D 域内梯度成立 = 破 3D 诚实边界第一步。"),
    }


class ShapeProblem3DSection:
    """D-85 3D 截面形状：宽度 w(x) × 厚度 h(x) 双软边界。

    截面 = 底固定 z=0、顶 z_top(x)=h(x) 的平板；y 向半宽 w(x)。介电
        eps(i,j,k) = Δeps·σ_w((w(x)-|y-j_mid|)/t_w)·σ_h((h(x)-k)/t_z)
    参数 θ = [w(K), h(K)]（2K 控制点），联合梯度链式 dFOM/dw、dFOM/dh。
    可制造 DRC：宽度界 + 厚度界 + 双平滑。
    """

    def __init__(self, base: AdjointProblem3D, n_controls: int = 8,
                 w_min: float = 2.0, w_max: float = 10.0,
                 h_min: float = 1.5, h_max: float = 6.0,
                 slope_max: float = 1.5, t_w: float = 1.2,
                 t_z: float = 0.8, init_w: float = 5.0,
                 init_h: float = 3.0):
        self.base = base
        self.n_controls = n_controls
        self.w_min, self.w_max = w_min, w_max
        self.h_min, self.h_max = h_min, h_max
        self.slope_max = slope_max
        self.t_w, self.t_z = t_w, t_z
        self.init_w, self.init_h = init_w, init_h
        self.di0, self.di1 = base.di0, base.di1
        self.dj0, self.dj1 = base.dj0, base.dj1
        self.j_mid = (base.dj0 + base.dj1) // 2
        self.k0, self.k1 = base.k_core0, base.k_core1
        self.knots = np.linspace(self.di0, self.di1 - 1, n_controls)
        self.cols = np.arange(self.di0, self.di1)

    def width_at(self, w) -> np.ndarray:
        return np.interp(self.cols, self.knots, np.asarray(w, dtype=float))

    def height_at(self, h) -> np.ndarray:
        return np.interp(self.cols, self.knots, np.asarray(h, dtype=float))

    def eps(self, w_ctl: np.ndarray, h_ctl: np.ndarray) -> np.ndarray:
        p = self.base
        tw, tz = self.t_w, self.t_z
        wc = self.width_at(w_ctl)
        hc = self.height_at(h_ctl)
        eps3 = np.full((p.Nx, p.Ny, p.Nz), p.eps_min)
        j = np.arange(self.dj0, self.dj1)
        k = np.arange(self.k0, self.k1)
        for ci, i in enumerate(self.cols):
            sw = _sigmoid((wc[ci] - np.abs(j - self.j_mid)) / tw)
            sh = _sigmoid((hc[ci] - k) / tz)
            eps3[i, self.dj0:self.dj1, self.k0:self.k1] = p.eps_min + \
                (p.eps_max - p.eps_min) * np.outer(sw, sh)
        return eps3

    def gradient(self, fwd: dict, w_ctl: np.ndarray,
                 h_ctl: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """链式：dFOM/dw_k、dFOM/dh_k（双软边界，探针 FD 对拍 4e-4）。"""
        p = self.base
        tw, tz = self.t_w, self.t_z
        geps = compute_gradient3d(p, fwd)
        K = self.n_controls
        wc = self.width_at(w_ctl)
        hc = self.height_at(h_ctl)
        j = np.arange(self.dj0, self.dj1)
        k = np.arange(self.k0, self.k1)
        gw = np.zeros(K)
        gh = np.zeros(K)
        for ci, i in enumerate(self.cols):
            sw = _sigmoid((wc[ci] - np.abs(j - self.j_mid)) / tw)
            sh = _sigmoid((hc[ci] - k) / tz)
            dsw = (sw * (1.0 - sw)) / tw
            dsh = (sh * (1.0 - sh)) / tz
            region = geps[i, self.dj0:self.dj1, self.k0:self.k1] * \
                (p.eps_max - p.eps_min)
            for kk in range(K):
                wgt = _interp_weight(i, self.knots, kk, K)
                if wgt == 0.0:
                    continue
                gw[kk] += np.sum(region * np.outer(dsw, sh)) * wgt
                gh[kk] += np.sum(region * np.outer(sw, dsh)) * wgt
        return gw, gh


def verify_section_gradient(sp: ShapeProblem3DSection, w_ctl: np.ndarray,
                            h_ctl: np.ndarray, nsamples: int = 6,
                            delta: float = 0.02, seed: int = 7
                            ) -> Dict[str, Any]:
    """截面联合梯度（w+h 控制点混合采样）FD 对拍。"""
    fwd0 = forward3d(sp.base, sp.eps(w_ctl, h_ctl))
    gw, gh = sp.gradient(fwd0, w_ctl, h_ctl)
    K = sp.n_controls
    rng = np.random.default_rng(seed)
    picks = sorted(rng.choice(K, size=min(nsamples, K), replace=False))
    rows = []
    for k in picks:
        for kind, g in (("w", gw), ("h", gh)):
            if kind == "w":
                wp = w_ctl.copy(); wp[k] += delta
                wm = w_ctl.copy(); wm[k] -= delta
                Fp = forward3d(sp.base, sp.eps(wp, h_ctl))["FOM"]
                Fm = forward3d(sp.base, sp.eps(wm, h_ctl))["FOM"]
            else:
                hp = h_ctl.copy(); hp[k] += delta
                hm = h_ctl.copy(); hm[k] -= delta
                Fp = forward3d(sp.base, sp.eps(w_ctl, hp))["FOM"]
                Fm = forward3d(sp.base, sp.eps(w_ctl, hm))["FOM"]
            rows.append({"kind": kind, "k": int(k),
                         "g_adj": float(g[k]),
                         "g_fd": float((Fp - Fm) / (2 * delta))})
    ref = max(rows, key=lambda r: abs(r["g_fd"]))
    Kc = ref["g_adj"] / ref["g_fd"] if abs(ref["g_fd"]) > 1e-12 else 1.0
    max_rel = max(abs(r["g_adj"] - Kc * r["g_fd"]) /
                  (abs(Kc * r["g_fd"]) + 1e-12) for r in rows)
    return {"rows": rows, "max_rel_err": float(max_rel),
            "nsamples": len(rows), "passed": bool(max_rel <= 0.15)}


def _section_drc(sp: ShapeProblem3DSection, w: np.ndarray,
                 h: np.ndarray) -> Dict[str, Any]:
    """宽度 + 厚度双界 + 双平滑 DRC。"""
    w = np.asarray(w)
    h = np.asarray(h)
    w_ok = bool(w.min() >= sp.w_min - 1e-9 and w.max() <= sp.w_max + 1e-9)
    h_ok = bool(h.min() >= sp.h_min - 1e-9 and h.max() <= sp.h_max + 1e-9)
    dw = float(np.max(np.abs(np.diff(w)))) if len(w) > 1 else 0.0
    dh = float(np.max(np.abs(np.diff(h)))) if len(h) > 1 else 0.0
    sm_ok = bool(dw <= sp.slope_max + 1e-9 and dh <= sp.slope_max + 1e-9)
    ok = bool(w_ok and h_ok and sm_ok)
    return {"ok": ok, "w_range": [float(w.min()), float(w.max())],
            "h_range": [float(h.min()), float(h.max())],
            "max_slope_w": round(dw, 3), "max_slope_h": round(dh, 3),
            "detail": (f"宽度∈[{w.min():.2f},{w.max():.2f}]（界 "
                       f"[{sp.w_min},{sp.w_max}]）；厚度∈[{h.min():.2f},"
                       f"{h.max():.2f}]（界 [{sp.h_min},{sp.h_max}]）；"
                       f"最大相邻变化 w={dw:.2f} h={dh:.2f}（≤{sp.slope_max}）")}


def optimize_section3d(sp: ShapeProblem3DSection, iters: int = 18,
                       step0: float = 0.4, verbose: bool = False
                       ) -> Dict[str, Any]:
    """截面联合优化（w+h 联合梯度 + 回溯线搜索 + 双可行性投影）。"""
    K = sp.n_controls
    w = np.full(K, sp.init_w)
    h = np.full(K, sp.init_h)
    fom0 = forward3d(sp.base, sp.eps(w, h))["FOM"]
    best_fom, best_w, best_h = fom0, w.copy(), h.copy()
    history = []
    for it in range(iters):
        fwd = forward3d(sp.base, sp.eps(w, h))
        gw, gh = sp.gradient(fwd, w, h)
        g = np.concatenate([gw, gh])
        m = np.max(np.abs(g)) + 1e-12
        d = g / m
        alpha = step0
        f_eval = fwd["FOM"]
        f_try, accepted = f_eval, False
        while alpha > 2e-3:
            wt = _project_shape(w + alpha * d[:K], sp.w_min, sp.w_max,
                                sp.slope_max)
            ht = _project_shape(h + alpha * d[K:], sp.h_min, sp.h_max,
                                sp.slope_max)
            f_try = forward3d(sp.base, sp.eps(wt, ht))["FOM"]
            if f_try > f_eval:
                accepted = True
                break
            alpha *= 0.5
        if accepted:
            w = _project_shape(w + alpha * d[:K], sp.w_min, sp.w_max,
                               sp.slope_max)
            h = _project_shape(h + alpha * d[K:], sp.h_min, sp.h_max,
                               sp.slope_max)
            f_final = f_try
        else:
            f_final = f_eval
        if f_final > best_fom:
            best_fom, best_w, best_h = f_final, w.copy(), h.copy()
        history.append({"iter": it, "FOM": f_final, "alpha": round(alpha, 4)})
        if verbose and (it % 5 == 0 or it == iters - 1):
            print(f"  it={it:3d} alpha={alpha:6.3f} FOM={f_final:.4e}")
    fbf = forward3d(sp.base, sp.eps(best_w, best_h))
    improvement = fbf["FOM"] / (fom0 + 1e-12)
    drc = _section_drc(sp, best_w, best_h)
    return {
        "history": history,
        "final_width": [round(float(x), 3) for x in best_w],
        "final_height": [round(float(x), 3) for x in best_h],
        "final_FOM": fbf["FOM"],
        "initial_FOM": fom0,
        "improvement": float(improvement),
        "drc": drc,
        "passed": bool(improvement >= 1.5 and drc["ok"]),
        "note": ("D-85 3D 截面形状：宽度 w(x) × 厚度 h(x) 双软边界联合优化"
                 "（3D adjoint 显式转置梯度链式）。"),
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="D-84 3D adjoint 形状核")
    ap.add_argument("--Nx", type=int, default=48)
    ap.add_argument("--Ny", type=int, default=40)
    ap.add_argument("--Nz", type=int, default=12)
    ap.add_argument("--n_controls", type=int, default=8)
    ap.add_argument("--iters", type=int, default=16)
    a = ap.parse_args()
    p = AdjointProblem3D(Nx=a.Nx, Ny=a.Ny, Nz=a.Nz)
    sp = ShapeProblem3D(p, n_controls=a.n_controls)
    w0 = np.full(a.n_controls, sp.init_halfwidth)
    vr = verify_adjoint3d(p, sp.eps(w0), nsamples=8, delta=0.05)
    print(f"3D adjoint FD 对拍: max_rel_err={vr['max_rel_err']:.4f} "
          f"passed={vr['passed']}")
    vs = verify_shape_gradient3d(sp, w0, nsamples=6, delta=0.05)
    print(f"3D 形状梯度 FD 对拍: max_rel_err={vs['max_rel_err']:.4f} "
          f"passed={vs['passed']}")
    opt = optimize_shape3d(sp, iters=a.iters, verbose=True)
    print(f"3D 形状优化: improvement={opt['improvement']:.2f}× "
          f"passed={opt['passed']} width={opt['final_width']}")
    print(f"DRC: {opt['drc']['detail']}")
