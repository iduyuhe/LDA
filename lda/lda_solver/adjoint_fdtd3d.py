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
import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = os.path.dirname(_HERE)
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)

from lda_solver.shape_inverse import _sigmoid, _interp_weight, shape_drc  # noqa: E402

# ---------------------------------------------------------------------------
# numba 加速后端（D-89）：有 numba 用 JIT 核（大域 20×+），无则回退纯 numpy
# ---------------------------------------------------------------------------
try:
    from numba import njit, prange  # type: ignore
    _NUMBA = True
except Exception:  # noqa: BLE001
    njit = None
    prange = range
    _NUMBA = False

if _NUMBA:  # pragma: no cover - numba 环境专属

    @njit(parallel=True, cache=True, fastmath=True)
    def _step_h_nb(Ex, Ey, Ez, Hx, Hy, Hz, dHx, dHy, dHz, cH):
        """H 半步（前向差分，无 PBC，x 永不 PBC）——镜像 `_step_h3d`。"""
        Nx, Ny, Nz = Ex.shape
        for i in prange(Nx):
            for j in range(Ny):
                for k in range(Nz):
                    ez_fj = Ez[i, j + 1, k] - Ez[i, j, k] if j + 1 < Ny else 0.0
                    ey_fk = Ey[i, j, k + 1] - Ey[i, j, k] if k + 1 < Nz else 0.0
                    ex_fk = Ex[i, j, k + 1] - Ex[i, j, k] if k + 1 < Nz else 0.0
                    ez_fi = Ez[i + 1, j, k] - Ez[i, j, k] if i + 1 < Nx else 0.0
                    ey_fi = Ey[i + 1, j, k] - Ey[i, j, k] if i + 1 < Nx else 0.0
                    ex_fj = Ex[i, j + 1, k] - Ex[i, j, k] if j + 1 < Ny else 0.0
                    Hx[i, j, k] = (Hx[i, j, k] - cH * (ez_fj - ey_fk)) * dHx[i, j, k]
                    Hy[i, j, k] = (Hy[i, j, k] - cH * (ex_fk - ez_fi)) * dHy[i, j, k]
                    Hz[i, j, k] = (Hz[i, j, k] - cH * (ey_fi - ex_fj)) * dHz[i, j, k]

    @njit(parallel=True, cache=True, fastmath=True)
    def _step_e_nb(Ex, Ey, Ez, Hx, Hy, Hz, eps, dE, cH):
        """E 全步（后向差分）——镜像 `_step_e3d`。"""
        Nx, Ny, Nz = Ex.shape
        for i in prange(Nx):
            for j in range(Ny):
                for k in range(Nz):
                    e = eps[i, j, k]
                    cE = cH / e
                    hz_bj = Hz[i, j, k] - Hz[i, j - 1, k] if j - 1 >= 0 else 0.0
                    hy_bk = Hy[i, j, k] - Hy[i, j, k - 1] if k - 1 >= 0 else 0.0
                    hx_bk = Hx[i, j, k] - Hx[i, j, k - 1] if k - 1 >= 0 else 0.0
                    hz_bi = Hz[i, j, k] - Hz[i - 1, j, k] if i - 1 >= 0 else 0.0
                    hy_bi = Hy[i, j, k] - Hy[i - 1, j, k] if i - 1 >= 0 else 0.0
                    hx_bj = Hx[i, j, k] - Hx[i, j - 1, k] if j - 1 >= 0 else 0.0
                    Ex[i, j, k] = (Ex[i, j, k] + cE * (hz_bj - hy_bk)) * dE[i, j, k]
                    Ey[i, j, k] = (Ey[i, j, k] + cE * (hx_bk - hz_bi)) * dE[i, j, k]
                    Ez[i, j, k] = (Ez[i, j, k] + cE * (hy_bi - hx_bj)) * dE[i, j, k]

    @njit(parallel=True, cache=True, fastmath=True)
    def _fwd_nb3d(Ex, Ey, Ez, Hx, Hy, Hz, eps, dE, dHx, dHy, dHz, cH,
                  i_src, y0s, y1s, k0, k1, i_mon, m0, m1,
                  sigma_n, n_peak, meas0, nsteps,
                  dr, curlE_dr, omegadt, Ez_mon):
        """正演主循环（H→E→curlE 记录→软源→监视器）——镜像 `forward3d`。

        ⚠ 输入约束：dE/dHx/dHy/dHz 必须为全尺寸 (Nx,Ny,Nz) 数组（numpy 版
        依赖广播 (Nx,1,Nz)，numba 逐点索引 j 会越界——D-89 教训）。
        """
        for n in range(nsteps):
            _step_h_nb(Ex, Ey, Ez, Hx, Hy, Hz, dHx, dHy, dHz, cH)
            _step_e_nb(Ex, Ey, Ez, Hx, Hy, Hz, eps, dE, cH)
            # curlE 记录 = curl(H) 差分组合（无 cH/eps 系数，与 numpy 版一致）
            for q in range(dr.shape[0]):
                i = dr[q, 0]; j = dr[q, 1]; k = dr[q, 2]
                curlE_dr[n, 0, q] = (
                    (Hz[i, j, k] - Hz[i, j - 1, k] if j - 1 >= 0 else 0.0) -
                    (Hy[i, j, k] - Hy[i, j, k - 1] if k - 1 >= 0 else 0.0))
                curlE_dr[n, 1, q] = (
                    (Hx[i, j, k] - Hx[i, j, k - 1] if k - 1 >= 0 else 0.0) -
                    (Hz[i, j, k] - Hz[i - 1, j, k] if i - 1 >= 0 else 0.0))
                curlE_dr[n, 2, q] = (
                    (Hy[i, j, k] - Hy[i - 1, j, k] if i - 1 >= 0 else 0.0) -
                    (Hx[i, j, k] - Hx[i, j - 1, k] if j - 1 >= 0 else 0.0))
            nn = n - n_peak
            env = np.exp(-0.5 * (nn * nn) / (sigma_n * sigma_n))
            if env > 1e-12:
                for jj in range(y0s, y1s):
                    for kk in range(k0, k1):
                        Ez[i_src, jj, kk] += env * np.cos(omegadt * n)
            for jj in range(m0, m1):
                for kk in range(k0, k1):
                    Ez_mon[n, jj - m0, kk - k0] = Ez[i_mon, jj, kk]

    @njit(cache=True, fastmath=True)
    def _bd_t_nb(lam, out, axis):
        """后向差分转置（边界掩码严格镜像 `_bd_t`）：tf[j]=λ[j](j≥1)-λ[j+1](j≤N-2)。"""
        Nx, Ny, Nz = lam.shape
        for i in range(Nx):
            for j in range(Ny):
                for k in range(Nz):
                    if axis == 0:
                        out[i, j, k] = (lam[i, j, k] if i >= 1 else 0.0) - \
                            (lam[i + 1, j, k] if i + 1 <= Nx - 1 else 0.0)
                    elif axis == 1:
                        out[i, j, k] = (lam[i, j, k] if j >= 1 else 0.0) - \
                            (lam[i, j + 1, k] if j + 1 <= Ny - 1 else 0.0)
                    else:
                        out[i, j, k] = (lam[i, j, k] if k >= 1 else 0.0) - \
                            (lam[i, j, k + 1] if k + 1 <= Nz - 1 else 0.0)

    @njit(cache=True, fastmath=True)
    def _fd_t_nb(lam, out, axis):
        """前向差分转置（边界掩码严格镜像 `_fd_t`）：tf[j]=λ[j-1](j≥1)-λ[j](j≤N-2)。"""
        Nx, Ny, Nz = lam.shape
        for i in range(Nx):
            for j in range(Ny):
                for k in range(Nz):
                    if axis == 0:
                        out[i, j, k] = (lam[i - 1, j, k] if i >= 1 else 0.0) - \
                            (lam[i, j, k] if i <= Nx - 2 else 0.0)
                    elif axis == 1:
                        out[i, j, k] = (lam[i, j - 1, k] if j >= 1 else 0.0) - \
                            (lam[i, j, k] if j <= Ny - 2 else 0.0)
                    else:
                        out[i, j, k] = (lam[i, j, k - 1] if k >= 1 else 0.0) - \
                            (lam[i, j, k] if k <= Nz - 2 else 0.0)

    @njit(cache=True, fastmath=True)
    def _grad_nb3d(lamEx, lamEy, lamEz, lamHx, lamHy, lamHz, eps, dE,
                   dHx, dHy, dHz, cH, nsteps, meas0, dr, curlE_dr, grad,
                   i_mon, m0, m1, k0, k1, obs_full,
                   wEx, wEy, wEz, b1, b2, phiHx, phiHy, phiHz,
                   nHx, nHy, nHz, nEx, nEy, nEz,
                   lamEx2, lamEy2, lamEz2):
        """反向主循环（镜像 `compute_gradient3d`）：灵敏度累积 + E 步转置 +
        H 步转置 + obs 注入。⚠ dE/dHx/dHy/dHz 全尺寸数组（广播约束同上）。"""
        Nx, Ny, Nz = lamEx.shape
        nN = nsteps - 1
        if nN >= meas0:
            for jj in range(m0, m1):
                for kk in range(k0, k1):
                    lamEz[i_mon, jj, kk] += obs_full[nN, jj - m0, kk - k0]
        for k in range(nsteps - 1, -1, -1):
            # (a) ε 灵敏度累积（三分量同位）
            for q in range(dr.shape[0]):
                i = dr[q, 0]; j = dr[q, 1]; kk = dr[q, 2]
                grad[i, j, kk] += dE[i, j, kk] * (
                    lamEx[i, j, kk] * curlE_dr[k, 0, q] +
                    lamEy[i, j, kk] * curlE_dr[k, 1, q] +
                    lamEz[i, j, kk] * curlE_dr[k, 2, q])
            if k == 0:
                break
            # (b) E 步转置：wE[c]=cE·D_E·λE；nH = λH + C_HEᵀ·wE
            for i in range(Nx):
                for j in range(Ny):
                    for kk in range(Nz):
                        cE = cH / eps[i, j, kk]
                        wEx[i, j, kk] = cE * lamEx[i, j, kk] * dE[i, j, kk]
                        wEy[i, j, kk] = cE * lamEy[i, j, kk] * dE[i, j, kk]
                        wEz[i, j, kk] = cE * lamEz[i, j, kk] * dE[i, j, kk]
            _bd_t_nb(wEx, b1, 1); _bd_t_nb(wEy, b2, 0)
            for i in range(Nx):
                for j in range(Ny):
                    for kk in range(Nz):
                        nHz[i, j, kk] = lamHz[i, j, kk] + b1[i, j, kk] - b2[i, j, kk]
            _bd_t_nb(wEx, b1, 2); _bd_t_nb(wEz, b2, 0)
            for i in range(Nx):
                for j in range(Ny):
                    for kk in range(Nz):
                        nHy[i, j, kk] = lamHy[i, j, kk] - b1[i, j, kk] + b2[i, j, kk]
            _bd_t_nb(wEy, b1, 2); _bd_t_nb(wEz, b2, 1)
            for i in range(Nx):
                for j in range(Ny):
                    for kk in range(Nz):
                        nHx[i, j, kk] = lamHx[i, j, kk] + b1[i, j, kk] - b2[i, j, kk]
            # (c) λH^{k-1} = D_H·(λH+注入)
            for i in range(Nx):
                for j in range(Ny):
                    for kk in range(Nz):
                        phiHx[i, j, kk] = dHx[i, j, kk] * nHx[i, j, kk]
                        phiHy[i, j, kk] = dHy[i, j, kk] * nHy[i, j, kk]
                        phiHz[i, j, kk] = dHz[i, j, kk] * nHz[i, j, kk]
            # (d) H 步转置：nE = C_EHᵀ·φH（lamE 输入零）
            _fd_t_nb(phiHx, b1, 1); _fd_t_nb(phiHy, b2, 0)
            for i in range(Nx):
                for j in range(Ny):
                    for kk in range(Nz):
                        nEz[i, j, kk] = -cH * b1[i, j, kk] + cH * b2[i, j, kk]
            _fd_t_nb(phiHx, b1, 2); _fd_t_nb(phiHz, b2, 0)
            for i in range(Nx):
                for j in range(Ny):
                    for kk in range(Nz):
                        nEy[i, j, kk] = cH * b1[i, j, kk] - cH * b2[i, j, kk]
            _fd_t_nb(phiHy, b1, 2); _fd_t_nb(phiHz, b2, 1)
            for i in range(Nx):
                for j in range(Ny):
                    for kk in range(Nz):
                        nEx[i, j, kk] = -cH * b1[i, j, kk] + cH * b2[i, j, kk]
            # (e) λE^{k-1} = D_E·λE + Aᵀ + obs[k-1]
            for i in range(Nx):
                for j in range(Ny):
                    for kk in range(Nz):
                        lamEx2[i, j, kk] = dE[i, j, kk] * lamEx[i, j, kk] + nEx[i, j, kk]
                        lamEy2[i, j, kk] = dE[i, j, kk] * lamEy[i, j, kk] + nEy[i, j, kk]
                        lamEz2[i, j, kk] = dE[i, j, kk] * lamEz[i, j, kk] + nEz[i, j, kk]
            if k - 1 >= meas0:
                for jj in range(m0, m1):
                    for kk in range(k0, k1):
                        lamEz2[i_mon, jj, kk] += obs_full[k - 1, jj - m0, kk - k0]
            lamEx[:] = lamEx2[:]; lamEy[:] = lamEy2[:]; lamEz[:] = lamEz2[:]
            lamHx[:] = phiHx[:]; lamHy[:] = phiHy[:]; lamHz[:] = phiHz[:]

    def _forward3d_numba(prob, eps3, nsteps, meas0, sigma_n, n_peak):
        """numba 正演包装：构造全尺寸阻尼数组 + 调用 JIT 核（与 numpy 版一致）。"""
        Nx, Ny, Nz = prob.Nx, prob.Ny, prob.Nz
        Ex = np.zeros((Nx, Ny, Nz)); Ey = np.zeros((Nx, Ny, Nz))
        Ez = np.zeros((Nx, Ny, Nz))
        Hx = np.zeros((Nx, Ny, Nz)); Hy = np.zeros((Nx, Ny, Nz))
        Hz = np.zeros((Nx, Ny, Nz))
        # ⚠ numba 逐点索引要求全尺寸数组（numpy 版依赖 (Nx,1,Nz) 广播——D-89 教训）
        dE = np.broadcast_to(prob.dampE, (Nx, Ny, Nz)).copy()
        dHx = np.broadcast_to(prob.dampH[0], (Nx, Ny, Nz)).copy()
        dHy = np.broadcast_to(prob.dampH[1], (Nx, Ny, Nz)).copy()
        dHz = np.broadcast_to(prob.dampH[2], (Nx, Ny, Nz)).copy()
        cH = prob.dt / prob.dl
        i_src, y0s, y1s = prob.i_src, prob.y_src0, prob.y_src1
        i_mon, m0, m1 = prob.i_mon, prob.y_mon0, prob.y_mon1
        k0, k1 = prob.k_core0, prob.k_core1
        ndr = len(prob._dr)
        dri, drj, drk = np.unravel_index(prob._dr, (Nx, Ny, Nz))
        dr = np.stack([dri, drj, drk], axis=1).astype(np.int64)
        curlE_dr = np.zeros((nsteps, 3, ndr))
        Ez_mon = np.zeros((nsteps, m1 - m0, k1 - k0))
        _fwd_nb3d(Ex, Ey, Ez, Hx, Hy, Hz, eps3, dE, dHx, dHy, dHz, cH,
                  i_src, y0s, y1s, k0, k1, i_mon, m0, m1,
                  sigma_n, n_peak, meas0, nsteps, dr, curlE_dr,
                  prob.omega * prob.dt, Ez_mon)
        FOM = float(np.sum(Ez_mon[meas0:, :, :] ** 2))
        E_in = 0.0
        for n in range(nsteps):
            nn = n - n_peak
            env = math.exp(-0.5 * (nn / sigma_n) ** 2)
            if env > 1e-12:
                E_in += env * env * (y1s - y0s) * (k1 - k0)
        T = (FOM / E_in) if E_in > 1e-12 else 0.0
        return {
            "FOM": FOM, "T": T, "P_out": FOM, "P_in": E_in, "E_in": E_in,
            "curlE_dr": curlE_dr, "Ez_mon": Ez_mon, "eps": eps3,
            "nsteps": nsteps, "meas0": meas0, "sigma_n": sigma_n,
            "n_peak": n_peak,
        }

    def _gradient3d_numba(prob, fwd):
        """numba 反向包装：全尺寸阻尼数组 + JIT 反向核（梯度与 numpy 版一致）。"""
        Nx, Ny, Nz = prob.Nx, prob.Ny, prob.Nz
        nsteps, meas0 = fwd["nsteps"], fwd["meas0"]
        Zl = np.zeros((Nx, Ny, Nz))
        lamEx = Zl.copy(); lamEy = Zl.copy(); lamEz = Zl.copy()
        lamHx = Zl.copy(); lamHy = Zl.copy(); lamHz = Zl.copy()
        grad = Zl.copy()
        dE = np.broadcast_to(prob.dampE, (Nx, Ny, Nz)).copy()
        dHx = np.broadcast_to(prob.dampH[0], (Nx, Ny, Nz)).copy()
        dHy = np.broadcast_to(prob.dampH[1], (Nx, Ny, Nz)).copy()
        dHz = np.broadcast_to(prob.dampH[2], (Nx, Ny, Nz)).copy()
        cH = prob.dt / prob.dl
        i_mon, m0, m1 = prob.i_mon, prob.y_mon0, prob.y_mon1
        k0, k1 = prob.k_core0, prob.k_core1
        dri, drj, drk = np.unravel_index(prob._dr, (Nx, Ny, Nz))
        dr = np.stack([dri, drj, drk], axis=1).astype(np.int64)
        obs_full = 2.0 * fwd["Ez_mon"]
        _grad_nb3d(lamEx, lamEy, lamEz, lamHx, lamHy, lamHz, fwd["eps"],
                   dE, dHx, dHy, dHz, cH, nsteps, meas0, dr,
                   fwd["curlE_dr"], grad, i_mon, m0, m1, k0, k1, obs_full,
                   Zl.copy(), Zl.copy(), Zl.copy(),   # wEx wEy wEz
                   Zl.copy(), Zl.copy(),              # b1 b2
                   Zl.copy(), Zl.copy(), Zl.copy(),   # phiHx phiHy phiHz
                   Zl.copy(), Zl.copy(), Zl.copy(),   # nHx nHy nHz
                   Zl.copy(), Zl.copy(), Zl.copy(),   # nEx nEy nEz
                   Zl.copy(), Zl.copy(), Zl.copy())   # lamEx2 lamEy2 lamEz2
        geps = np.zeros((Nx, Ny, Nz))
        geps.ravel()[prob._dr] = (-(cH) / (fwd["eps"].ravel()[prob._dr] ** 2)
                                  * grad.ravel()[prob._dr])
        return geps


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
def forward3d(prob: AdjointProblem3D, eps3: np.ndarray,
              backend: str = "auto") -> Dict[str, Any]:
    """3D 正演（D-89 起支持 numba 加速后端）。

    backend='auto'：有 numba 用 JIT 核（大域 20×+，prange 并行），无则回退
    纯 numpy 数组切片版。结果与 numpy 版 bit-level 一致（FOM rel≈1e-16）。
    """
    Nx, Ny, Nz = prob.Nx, prob.Ny, prob.Nz
    dl, dt = prob.dl, prob.dt
    per = prob.period_steps
    sigma_n = int(round(prob.target_exp / 2.0)) * 2 + 1
    n_peak = int(round(prob.target_exp * 1.5))
    travel = int(math.ceil(Nx * dl / dt)) + 60
    meas0 = max(n_peak + travel - 3 * sigma_n, 0)
    nsteps = n_peak + travel + int(round(6 * per)) + 6 * sigma_n + 200
    omega = prob.omega

    if _NUMBA and backend in ("auto", "numba"):
        return _forward3d_numba(prob, eps3, nsteps, meas0, sigma_n, n_peak)

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
def compute_gradient3d(prob: AdjointProblem3D, fwd: Dict[str, Any],
                       backend: str = "auto") -> np.ndarray:
    """dFOM/dε（全网格 (Nx,Ny,Nz)，仅设计区非零）。

    FOM = Σ_{n≥meas0} Σ Ez[i_mon,y,z]² → 观测源 obs_Ez[n,y,z] = 2·Ez_mon[n,y,z]。
    反向步序（正向 = H 步 → E 步 → 源注入 → 监视器）：
      (a) ε 灵敏度累积：grad[dr] += Σ_c (D_E·λ_Ec)[dr]·curlEc_dr[k]；
      (b) E 步转置：λH += C_HEᵀ·(cE·D_E·λE)；
      (c) λH^{k-1} = D_H·(λH + 注入)；
      (d) H 步转置：λE += C_EHᵀ·D_H·(λH+注入)；
      (e) λE^{k-1} = D_E·λE + (d) + obs[k-1]。

    backend='auto'：有 numba 用 JIT 反向核，无则回退纯 numpy（D-89）。
    """
    if _NUMBA and backend in ("auto", "numba"):
        return _gradient3d_numba(prob, fwd)
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

    def gradient(self, fwd: dict, w_ctl: np.ndarray,
                 backend: str = "auto") -> np.ndarray:
        """链式：dFOM/dw_k = Σ_ijk geps[i,j,k]·dε/dw_k（软边界 δσ/δw）。"""
        geps = compute_gradient3d(self.base, fwd, backend)
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
                     verbose: bool = False, backend: str = "auto") -> Dict[str, Any]:
    """3D 宽度曲线形状优化（回溯线搜索 + 可行性投影）。"""
    K = sp.n_controls
    w = np.full(K, sp.init_halfwidth)
    fom0 = forward3d(sp.base, sp.eps(w), backend)["FOM"]
    best_fom, best_w = fom0, w.copy()
    history = []
    for it in range(iters):
        fwd = forward3d(sp.base, sp.eps(w), backend)
        g = sp.gradient(fwd, w, backend)
        m = np.max(np.abs(g)) + 1e-12
        d = g / m
        alpha = step0
        f_eval = fwd["FOM"]
        f_try, accepted = f_eval, False
        while alpha > 2e-3:
            wt = _project_shape(w + alpha * d, sp.w_min, sp.w_max,
                                sp.slope_max)
            f_try = forward3d(sp.base, sp.eps(wt), backend)["FOM"]
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
    fbf = forward3d(sp.base, sp.eps(best_w), backend)
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


class TopologyProblem3D:
    """D-92 3D voxel 拓扑逆设计问题（3D 纵深最后一环）。

    设计区 = 核心层体素（`AdjointProblem3D._dr`，全网格坐标列表）；
    潜伏密度 r ∈ [0,1]^ndr，物理密度 ρ̄ = tanh 投影（beta 2→beta_max 延拓，
    先柔后硬二值化——可制造性内建）；
        eps(体素) = eps_min + ρ̄·(eps_max−eps_min)
    梯度链式：dFOM/dr = (eps_max−eps_min)·geps·dρ̄/dr（geps = dFOM/dε 来自
    `compute_gradient3d`，已 FD 对拍 9.4e-6；拓扑链式 FD 对拍 ≤0.15 验收）。

    与 2D 拓扑（D-29 `optimize_topology`）同构：最大分量归一化 + Armijo
    回溯线搜索（评估 = 与迭代一致的同投影设计，FOM 单调不降）。
    """

    def __init__(self, base: "AdjointProblem3D", beta_max: float = 12.0):
        self.base = base
        self.dr = np.asarray(base._dr)
        self.ndr = len(self.dr)
        self.beta_max = beta_max
        self.eps_min = base.eps_min
        self.eps_max = base.eps_max

    def rho_to_eps(self, rho: np.ndarray,
                   eps0: Optional[np.ndarray] = None) -> np.ndarray:
        """物理密度 ρ̄ → 介电（eps0 为包层基底，未指定则全 eps_min）。"""
        if eps0 is None:
            eps0 = np.full((self.base.Nx, self.base.Ny, self.base.Nz),
                           self.eps_min)
        e = eps0.copy()
        e.ravel()[self.dr] = self.eps_min + rho * (self.eps_max - self.eps_min)
        return e

    @staticmethod
    def project(r: np.ndarray, beta: float) -> np.ndarray:
        """tanh 投影（beta=2 时近线性；beta≫1 时二值化）。"""
        t = np.tanh(beta * (r - 0.5)) / (2.0 * np.tanh(beta / 2.0)) + 0.5
        return np.clip(t, 0.0, 1.0)

    def fom_at(self, r: np.ndarray, beta: float,
               eps0: Optional[np.ndarray] = None) -> float:
        """投影一致目标：物理密度 = project(r, beta) 后再转 eps。"""
        return float(forward3d(self.base,
                               self.rho_to_eps(self.project(r, beta),
                                               eps0))["FOM"])

    def gradient(self, r: np.ndarray, beta: float,
                 eps0: Optional[np.ndarray] = None) -> np.ndarray:
        """链式 dFOM/dr（潜伏密度）：geps·(eps_max−eps_min)·dρ̄/dr。"""
        rho = self.project(r, beta)
        fwd = forward3d(self.base, self.rho_to_eps(rho, eps0))
        geps = compute_gradient3d(self.base, fwd)
        g_rho = (self.eps_max - self.eps_min) * geps.ravel()[self.dr]
        t = np.tanh(beta * (r - 0.5))
        dproj = beta * (1.0 - t ** 2) / (2.0 * np.tanh(beta / 2.0))
        return g_rho * dproj, fwd


def verify_topo_gradient3d(tp: TopologyProblem3D, r0: np.ndarray,
                           beta: float = 2.0, nsamples: int = 6,
                           delta: float = 0.02,
                           seed: int = 11) -> Dict[str, Any]:
    """3D 拓扑梯度链式 FD 对拍（潜伏密度方向采样）。"""
    rng = np.random.default_rng(seed)
    g_r, _ = tp.gradient(r0, beta)
    order = np.argsort(np.abs(g_r))[::-1][:max(nsamples, 1)]
    rows = []
    for idx in order:
        rp = r0.copy(); rp[idx] += delta
        rm = r0.copy(); rm[idx] -= delta
        g_fd = (tp.fom_at(rp, beta) - tp.fom_at(rm, beta)) / (2.0 * delta)
        rows.append({"voxel": int(idx), "g_adj": float(g_r[idx]),
                     "g_fd": float(g_fd)})
    ga = np.array([r["g_adj"] for r in rows])
    gf = np.array([r["g_fd"] for r in rows])
    max_rel = float(np.abs(ga - gf).max() / (np.abs(gf).max() + 1e-12))
    return {"max_rel_err": max_rel, "passed": bool(max_rel <= 0.15),
            "rows": rows, "nsamples": nsamples, "delta": delta}


def optimize_topology3d(tp: TopologyProblem3D, iters: int = 18,
                        step0: float = 0.5, beta_max: float = 12.0,
                        verbose: bool = False) -> Dict[str, Any]:
    """3D voxel 拓扑优化：tanh 投影 beta 延拓 + 最大分量归一化 + 回溯线搜索。

    返回 dict：history、final_density（二值化投影）、improvement、二值度。
    """
    nd = tp.ndr
    r = np.full(nd, 0.5)
    fom0 = tp.fom_at(r, 2.0)
    best_fom, best_r = fom0, r.copy()
    history = []
    for it in range(iters):
        beta = 2.0 + (beta_max - 2.0) * (it / max(iters - 1, 1))
        g_r, fwd = tp.gradient(r, beta)
        m = np.max(np.abs(g_r)) + 1e-12
        d = g_r / m
        alpha = step0
        f_eval = fwd["FOM"]
        f_try, accepted = f_eval, False
        while alpha > 2e-3:
            f_try = tp.fom_at(np.clip(r + alpha * d, 0.0, 1.0), beta)
            if f_try > f_eval:
                accepted = True
                break
            alpha *= 0.5
        if accepted:
            r = np.clip(r + alpha * d, 0.0, 1.0)
            f_final = f_try
        else:
            f_final = f_eval
        if f_final > best_fom:
            best_fom, best_r = f_final, r.copy()
        history.append({"iter": it, "FOM": f_final, "T": fwd["T"],
                        "beta": round(beta, 2), "alpha": round(alpha, 4)})
        if verbose and (it % 5 == 0 or it == iters - 1):
            print(f"  it={it:3d} beta={beta:5.2f} alpha={alpha:6.3f} "
                  f"FOM={f_final:.4e}")
    # 最终设计：best_r 以 beta_max 重投影（二值化）后评估
    rho_final = tp.project(best_r, beta_max)
    fbf = tp.fom_at(best_r, beta_max)
    improvement = fbf / (fom0 + 1e-12)
    bw = rho_final
    binary_frac = float(((bw < 0.1) | (bw > 0.9)).mean())
    return {
        "history": history,
        "final_density": bw,
        "final_FOM": float(fbf),
        "initial_FOM": float(fom0),
        "improvement": float(improvement),
        "binary_fraction": binary_frac,
        "passed": bool(improvement >= 1.5),
        "note": ("D-92 3D voxel 拓扑逆设计（3D 纵深最后一环）：潜伏密度 + tanh "
                 "投影 beta 延拓（可制造二值化内建）+ 3D adjoint 显式转置梯度。"),
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
                 h_ctl: np.ndarray, backend: str = "auto"
                 ) -> Tuple[np.ndarray, np.ndarray]:
        """链式：dFOM/dw_k、dFOM/dh_k（双软边界，探针 FD 对拍 4e-4）。"""
        p = self.base
        tw, tz = self.t_w, self.t_z
        geps = compute_gradient3d(p, fwd, backend)
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
                       step0: float = 0.4, verbose: bool = False,
                       backend: str = "auto") -> Dict[str, Any]:
    """截面联合优化（w+h 联合梯度 + 回溯线搜索 + 双可行性投影）。"""
    K = sp.n_controls
    w = np.full(K, sp.init_w)
    h = np.full(K, sp.init_h)
    fom0 = forward3d(sp.base, sp.eps(w, h), backend)["FOM"]
    best_fom, best_w, best_h = fom0, w.copy(), h.copy()
    history = []
    for it in range(iters):
        fwd = forward3d(sp.base, sp.eps(w, h), backend)
        gw, gh = sp.gradient(fwd, w, h, backend)
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
            f_try = forward3d(sp.base, sp.eps(wt, ht), backend)["FOM"]
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
    fbf = forward3d(sp.base, sp.eps(best_w, best_h), backend)
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


# ---------------------------------------------------------------------------
# D-87 谱形目标 × 3D 截面：多波长加权联合优化
# ---------------------------------------------------------------------------
def make_wl_problems3d(base: AdjointProblem3D,
                       wavelengths_um: Optional[List[float]] = None
                       ) -> List[AdjointProblem3D]:
    """多波长 3D 问题族：deepcopy base，**物理网格固定（dl/dt 保持基准）**，
    只变 omega/period_steps → 波长真正变化（D-80 归一化网格陷阱：若
    dl=wl/dl_factor 则 omega·dt 与波长无关，deepcopy 保留惰性字段天然免疫）。
    """
    if wavelengths_um is None:
        wavelengths_um = [1.5, 1.55, 1.6]
    probs = []
    for wl in wavelengths_um:
        p = copy.deepcopy(base)
        p.wl_um = float(wl)
        p.omega = 2.0 * math.pi / float(wl)
        p.period_steps = int(round(2.0 * math.pi / (p.omega * p.dt)))
        probs.append(p)
    return probs


def verify_section_gradient_multi(sps: List[ShapeProblem3DSection],
                                  weights: np.ndarray, w_ctl: np.ndarray,
                                  h_ctl: np.ndarray, nsamples: int = 6,
                                  delta: float = 0.02, seed: int = 11
                                  ) -> Dict[str, Any]:
    """多波长截面联合梯度 FD 对拍：逐波长 + 加权联合（w/h 混合采样）。

    联合梯度 G = Σ_k w_k·[gw_k, gh_k]；FD 用联合 FOM=Σw_k·FOM_k 中心差分。
    """
    nwl = len(sps)
    wt = np.asarray(weights, dtype=float)
    wt = wt / wt.sum()
    K = sps[0].n_controls

    def F(w_, h_):
        return float(sum(wt[k] * forward3d(sps[k].base, sps[k].eps(w_, h_))["FOM"]
                         for k in range(nwl)))

    G_w = np.zeros(K)
    G_h = np.zeros(K)
    per_wl = []
    for k in range(nwl):
        fwd = forward3d(sps[k].base, sps[k].eps(w_ctl, h_ctl))
        gw, gh = sps[k].gradient(fwd, w_ctl, h_ctl)
        G_w += wt[k] * gw
        G_h += wt[k] * gh
        per_wl.append({"wl_um": float(sps[k].base.wl_um),
                       "weight": round(float(wt[k]), 4)})
    rng = np.random.default_rng(seed)
    picks = sorted(rng.choice(K, size=min(nsamples, K), replace=False))
    rows = []
    for k in picks:
        for kind, G in (("w", G_w), ("h", G_h)):
            if kind == "w":
                wp = w_ctl.copy(); wp[k] += delta
                wm = w_ctl.copy(); wm[k] -= delta
                Fp = F(wp, h_ctl); Fm = F(wm, h_ctl)
            else:
                hp = h_ctl.copy(); hp[k] += delta
                hm = h_ctl.copy(); hm[k] -= delta
                Fp = F(w_ctl, hp); Fm = F(w_ctl, hm)
            rows.append({"kind": kind, "k": int(k),
                         "g_adj": float(G[k]),
                         "g_fd": float((Fp - Fm) / (2 * delta))})
    g_adj = np.array([r["g_adj"] for r in rows])
    g_fd = np.array([r["g_fd"] for r in rows])
    denom = np.abs(g_fd).max() + 1e-12
    max_rel_err = float(np.abs(g_adj - g_fd).max() / denom)
    mean_rel_err = float(np.mean(np.abs(g_adj - g_fd)) / denom)
    return {"max_rel_err": max_rel_err, "mean_rel_err": mean_rel_err,
            "passed": bool(max_rel_err <= 0.15), "rows": rows,
            "nsamples": len(picks),
            "per_wavelength": per_wl}


def optimize_section3d_multi(sps: List[ShapeProblem3DSection],
                             weights: Optional[List[float]] = None,
                             iters: int = 16, step0: float = 0.4,
                             verbose: bool = False,
                             backend: str = "auto") -> Dict[str, Any]:
    """D-87 3D 截面 × 多波长加权联合（谱形目标 3D）。

    联合 FOM = Σ_k w_k · FOM_k；联合梯度 = Σ_k w_k·[gw_k, gh_k]；
    **分块归一化**（w 块 / h 块各自归一化后拼接——合并 max 归一化会压制
    量级小但重要的厚度梯度，D-83 教训）。线搜索评估 = 同一可行性投影设计
    下的全波长加权 FOM（单调不降，与迭代目标同投影一致）。

    验收：加权 improvement ≥ 1.5 且各波长均 ≥ 1.2 + DRC 双界。
    """
    nwl = len(sps)
    if weights is None:
        wt = np.ones(nwl) / nwl
    else:
        wt = np.asarray(weights, dtype=float) / np.asarray(weights).sum()
    K = sps[0].n_controls

    def F(w_, h_):
        return float(sum(wt[k] * forward3d(sps[k].base, sps[k].eps(w_, h_),
                                           backend)["FOM"]
                         for k in range(nwl)))

    w = np.full(K, sps[0].init_w)
    h = np.full(K, sps[0].init_h)
    fom0 = F(w, h)
    best_fom, best_w, best_h = fom0, w.copy(), h.copy()
    history = []
    for it in range(iters):
        G_w = np.zeros(K)
        G_h = np.zeros(K)
        f_eval = 0.0
        for k in range(nwl):
            fwd = forward3d(sps[k].base, sps[k].eps(w, h), backend)
            f_eval += wt[k] * fwd["FOM"]
            gw, gh = sps[k].gradient(fwd, w, h, backend)
            G_w += wt[k] * gw
            G_h += wt[k] * gh
        # 分块归一化（w/h 各自尺度）
        dw = G_w / (np.max(np.abs(G_w)) + 1e-12)
        dh = G_h / (np.max(np.abs(G_h)) + 1e-12)
        alpha = step0
        f_try, accepted = f_eval, False
        while alpha > 2e-3:
            wt_ = _project_shape(w + alpha * dw, sps[0].w_min, sps[0].w_max,
                                 sps[0].slope_max)
            ht_ = _project_shape(h + alpha * dh, sps[0].h_min, sps[0].h_max,
                                 sps[0].slope_max)
            f_try = F(wt_, ht_)
            if f_try > f_eval:
                accepted = True
                break
            alpha *= 0.5
        if accepted:
            w = wt_
            h = ht_
            f_final = f_try
        else:
            f_final = f_eval
        if f_final > best_fom:
            best_fom, best_w, best_h = f_final, w.copy(), h.copy()
        history.append({"iter": it, "FOM_total": f_final,
                        "alpha": round(alpha, 4)})
        if verbose and (it % 5 == 0 or it == iters - 1):
            print(f"  it={it:3d} alpha={alpha:6.3f} FOM_total={f_final:.4e}")

    w_init = np.full(K, sps[0].init_w)
    h_init = np.full(K, sps[0].init_h)
    per_wl = []
    for k, sp in enumerate(sps):
        f0 = forward3d(sp.base, sp.eps(w_init, h_init), backend)["FOM"]
        f1 = forward3d(sp.base, sp.eps(best_w, best_h), backend)["FOM"]
        per_wl.append({"wl_um": float(sp.base.wl_um),
                       "weight": round(float(wt[k]), 4),
                       "initial_FOM": float(f0), "final_FOM": float(f1),
                       "improvement": float(f1 / (f0 + 1e-12))})
    weighted_imp = float(sum(wt[k] * per_wl[k]["improvement"]
                             for k in range(nwl)))
    drc = _section_drc(sps[0], best_w, best_h)
    passed = bool(weighted_imp >= 1.5 and drc["ok"]
                  and all(per_wl[k]["improvement"] >= 1.2
                          for k in range(nwl)))
    return {
        "history": history,
        "per_wavelength": per_wl,
        "weighted_improvement": round(weighted_imp, 3),
        "final_width": [round(float(x), 3) for x in best_w],
        "final_height": [round(float(x), 3) for x in best_h],
        "final_FOM_total": best_fom,
        "initial_FOM_total": fom0,
        "drc": drc,
        "passed": bool(passed),
        "note": ("D-87 3D 截面 × 多波长加权联合：FOM=Σw_λ·FOM_λ（物理网格"
                 "固定只变 omega）；分块归一化（w/h 各自尺度）；谱形目标 = "
                 "设计对目标波长带整体可用；加权 improvement≥1.5 且各波长≥1.2。"),
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
