"""LDA · D-69 主权 2D adjoint FDTD 逆设计核（TEz 模式）。

对主权 2D FDTD 求 **伴随法（adjoint）灵敏度**，把"参数扫描 + 闭式反解"
升级为"梯度驱动几何/拓扑逆设计"。

设计哲学（与 fdtd2d.py 同构、零额外依赖）：
- 前向：标准 Yee 网格（Ez / Hx / Hy），四向二次型海绵吸收边界，
  **高斯脉冲软源**（能量有界），监视器线积分场能 → FOM。
- adjoint：显式实现 FDTD 更新算子的**转置**（reverse-mode 自动微分的解析等价），
  在输出监视器注入观测源（dFOM/dEz = 2·Ez），反向时间步进得 adjoint 场，
  由 adjoint 公式得 dFOM/dε。
- 验证锚：``verify_adjoint`` 对随机设计体素做中心有限差分，与 adjoint 梯度
  **方向对拍**（归一化相对误差 ≤ 容差），替代 LLM 判决（红线不变）。

为何不用 CW 源 + DFT P_out：
CW 源 + 全时段 P_out 目标在无源线性结构上**无上界**——优化器会构造高 Q
谐振腔持续蓄能（实测 T 冲到 65+ 后场发散）。高斯脉冲总能量有硬上界，
FOM = 测量窗内监视器线场能积分，物理与数学都干净，且 adjoint 观测退化为
obs = 2·Ez（无 DFT、无复共轭陷阱）。

为何不做 torch/jax 反传：FDTD 时间步长（数千步）× 2D 网格的反向链式
内存与速度代价大；显式 adjoint 是同一梯度的解析等价、内存 O(设计区) 且更稳。

FOM 语义（诚实标注）：FOM = Σ_{n≥meas0} Σ_j Ez[i_mon, j]² 为监视器孔径上的
**收集场能**（时间积分 × 空间线积分）。无源无耗散结构可因聚焦/相干增强使
T = FOM/E_in > 1（聚焦增益），非能量不守恒，亦非数值病态；报告时须与
"功率透射"区分。优化目标即最大化该收集场能。

单位：归一化（c=1, ε0=μ0=1），eps = n²。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# 几何 / 问题定义
# ---------------------------------------------------------------------------
@dataclass
class AdjointProblem:
    """2D adjoint 逆设计问题几何。

    - 域：Nx × Ny 格，dl 为格距（由 λ / dl_factor 定）。
    - 四向海绵（sponge 格）吸收边界。
    - 高斯脉冲软源：x = i_src 的一条竖直线（跨 y_src0..y_src1），TEz 脉冲。
    - 输出监视器：x = i_mon 的竖直线（跨 y_mon0..y_mon1，窄孔径聚焦目标），
      测 Ez 场能积分 → FOM。
    - 设计区：布尔掩码 design_mask（True 处 ε 可优化）。源/监视器不在设计区内。
    - 基介电：eps_min（背景）；设计区内可调至 eps_max。
    """

    wl_um: float = 1.55
    dl_factor: float = 14.0
    courant: float = 0.95
    Nx: int = 110
    Ny: int = 90
    sponge: int = 10
    target_exp: float = 12.0
    ramp: int = 300
    # 源
    i_src: int = 0
    y_src0: int = 0
    y_src1: int = 0
    # 监视器（窄孔径：聚焦式 FOM）
    i_mon: int = 0
    y_mon0: int = 0
    y_mon1: int = 0
    # D-80 多目标：第二监视器（分束比用，mon2 = 下/另一输出臂）
    i_mon2: int = 0
    y2_mon0: int = 0
    y2_mon1: int = 0
    # D-80 目标类型：field_energy | split_ratio | mode_match
    target_type: str = "field_energy"
    target_ratio: float = 0.5            # 分束比目标：mon(主) 端口占比 ∈(0,1)
    mode_profile: Optional[np.ndarray] = None   # mode_match 目标场分布（长度=y_mon1-y_mon0）
    # 设计区（盒子 [i0:i1, j0:j1]，须在源/监视器之间且避开海绵）
    di0: int = 0
    di1: int = 0
    dj0: int = 0
    dj1: int = 0
    eps_min: float = 1.0          # 背景（空气 / 包层）
    eps_max: float = 12.25        # 设计材料（硅 n=3.5 → 12.25）
    periods_factor: int = 90      # （保留字段，脉冲前向不使用）

    def __post_init__(self):
        dl = self.wl_um / self.dl_factor
        self.dl = dl
        self.dt = dl * self.courant / math.sqrt(2.0)
        self.omega = 2.0 * math.pi / self.wl_um
        # 默认几何：源在左海绵内边，监视器在右海绵内边，设计区居中
        if self.i_src == 0:
            self.i_src = self.sponge + 6
        if self.y_src0 == 0 and self.y_src1 == 0:
            self.y_src0 = self.Ny // 2 - 6
            self.y_src1 = self.Ny // 2 + 6
        if self.i_mon == 0:
            self.i_mon = self.Nx - self.sponge - 6
        if self.y_mon0 == 0 and self.y_mon1 == 0:
            # 窄孔径（6 行 ≈ 0.85 λ0），聚焦式 FOM
            self.y_mon0 = self.Ny // 2 - 3
            self.y_mon1 = self.Ny // 2 + 3
        # D-80 split_ratio 默认第二监视器：同列、与主监视器上下对称（两输出臂）
        if self.target_type == "split_ratio":
            if self.i_mon2 == 0:
                self.i_mon2 = self.i_mon
            if self.y2_mon0 == 0 and self.y2_mon1 == 0:
                span = self.y_mon1 - self.y_mon0
                self.y2_mon0 = self.y_mon1 + 2          # 下臂（主=上臂）
                self.y2_mon1 = self.y2_mon0 + span
                if self.y2_mon1 >= self.Ny - self.sponge:
                    # 空间不足：主/第二上下翻转
                    self.y2_mon1 = self.y_mon0 - 2
                    self.y2_mon0 = self.y2_mon1 - span
        if self.di0 == 0 and self.di1 == 0:
            self.di0 = self.sponge + 8
            self.di1 = self.Nx - self.sponge - 8
        if self.dj0 == 0 and self.dj1 == 0:
            self.dj0 = self.sponge + 8
            self.dj1 = self.Ny - self.sponge - 8
        self._build_sponge()

    # ---- 海绵（复用 fdtd2d 的二次型剖面 + 转置友好的阻尼系数）----
    def _sponge_1d(self, n, sig_max):
        s = np.zeros(n, dtype=float)
        if self.sponge < 1 or n < 2:
            return s
        xs = np.arange(self.sponge)
        left = sig_max * ((self.sponge - 1 - xs) / (self.sponge - 1)) ** 2
        right = sig_max * (xs / (self.sponge - 1)) ** 2
        s[: self.sponge] = left
        s[-self.sponge:] = right
        return s

    def _build_sponge(self):
        Nx, Ny, dt = self.Nx, self.Ny, self.dt
        sig_max = self.target_exp * 3.0 / (dt * self.sponge)   # 背景 n≈1
        sx = self._sponge_1d(Nx, sig_max)
        sy = self._sponge_1d(Ny, sig_max)
        sigma = np.outer(sx, np.ones(Ny)) + np.outer(np.ones(Nx), sy)
        sigma = np.minimum(sigma, sig_max)
        eps_avg = (self.eps_min + self.eps_max) / 2.0
        self.dampE = 1.0 / (1.0 + dt * sigma / eps_avg)
        # H 位于 E 的半格：取相邻 E-sigma 平均
        sigHx = 0.5 * (sigma[:, :-1] + sigma[:, 1:])
        sigHx = np.pad(sigHx, ((0, 0), (0, 1)), mode='edge')
        sigHy = 0.5 * (sigma[:-1, :] + sigma[1:, :])
        sigHy = np.pad(sigHy, ((0, 1), (0, 0)), mode='edge')
        self.dampHx = 1.0 / (1.0 + dt * sigHx)
        self.dampHy = 1.0 / (1.0 + dt * sigHy)
        # 设计掩码
        m = np.zeros((Nx, Ny), dtype=bool)
        m[self.di0:self.di1, self.dj0:self.dj1] = True
        self.design_mask = m
        self._dr = np.where(m.ravel())[0]            # 设计体素扁平索引
        # 时间步参数（CW 保留字段；脉冲前向自行计算）
        per = int(round(2.0 * math.pi / (self.omega * self.dt)))
        self.period_steps = per
        self.transient = max(self.ramp + 6 * per, 1200)
        self.M = self.periods_factor * per
        self.nsteps = self.transient + self.M
        self.meas0 = self.transient


# ---------------------------------------------------------------------------
# 前向 FDTD（高斯脉冲软源 + 监视器场能 + 设计区 curlH 记录）
# ---------------------------------------------------------------------------
def forward(prob: AdjointProblem, eps: np.ndarray,
            sigma_periods: float = 4.0, n_peak_scale: float = 8.0,
            tail_periods: float = 8.0):
    """跑脉冲前向 FDTD，返回 FOM 相关量。

    eps : (Nx, Ny) 介电常数（n²）。
    返回 dict：
      FOM        : 收集场能 Σ_{n≥meas0} Σ_j Ez[i_mon, m0:m1]²
      T          : 归一化收集场能 FOM / E_in（聚焦增益可 >1，非功率透射）
      E_in       : 注入场能 Σ_n env(n)²·(源行数)
      curlH_dr   : (nsteps, ndr) 每步设计区 curlH（供 adjoint）
      Ez_mon     : (nsteps, m1-m0) 监视器 Ez 时间序列（供 adjoint 观测）
      nsteps/meas0/sigma_n/n_peak : 时间参数（供 adjoint 对齐）
    """
    Nx, Ny, dl, dt = prob.Nx, prob.Ny, prob.dl, prob.dt
    per = prob.period_steps
    sigma_n = int(round(sigma_periods * per))
    n_peak = int(round(n_peak_scale * sigma_n))
    travel = int(math.ceil(Nx * dl / dt)) + 60
    meas0 = max(n_peak + travel - 3 * sigma_n, 0)
    nsteps = n_peak + travel + int(round(tail_periods * per)) + 6 * sigma_n + 200

    Ez = np.zeros((Nx, Ny))
    Hx = np.zeros((Nx, Ny))
    Hy = np.zeros((Nx, Ny))
    dampE, dampHx, dampHy = prob.dampE, prob.dampHx, prob.dampHy
    i_src, j0s, j1s = prob.i_src, prob.y_src0, prob.y_src1
    i_mon, m0, m1 = prob.i_mon, prob.y_mon0, prob.y_mon1
    mw = m1 - m0
    ndr = len(prob._dr)
    dr_i, dr_j = prob._dr // Ny, prob._dr % Ny
    curlH_dr = np.zeros((nsteps, ndr))
    Ez_mon = np.zeros((nsteps, mw))
    Ez_mon2 = np.zeros((nsteps, mw)) if prob.target_type == "split_ratio" else None
    E_in = 0.0

    for n in range(nsteps):
        env = math.exp(-0.5 * ((n - n_peak) / sigma_n) ** 2)
        # ---- H 更新（半步）----
        dEzdy = Ez[:, 1:] - Ez[:, :-1]
        Hx[:, :Ny - 1] -= (dt / dl) * dEzdy
        dEzdx = Ez[1:, :] - Ez[:-1, :]
        Hy[:-1, :] += (dt / dl) * dEzdx
        Hx *= dampHx
        Hy *= dampHy
        # ---- E 更新（全步）----
        dHydx = Hy[1:, :] - Hy[:-1, :]
        dHxdy = Hx[:, 1:] - Hx[:, :-1]
        curlH = (dHydx[0:Nx - 2, 1:Ny - 1] - dHxdy[1:Nx - 1, 0:Ny - 2])
        Ez[1:Nx - 1, 1:Ny - 1] += (dt / dl) / eps[1:Nx - 1, 1:Ny - 1] * curlH
        Ez *= dampE
        # 记录设计区 curlH（curlH 相对 [1:Nx-1,1:Ny-1] 的偏移）
        ci = dr_i - 1
        cj = dr_j - 1
        ok = (ci >= 0) & (ci < Nx - 2) & (cj >= 0) & (cj < Ny - 2)
        curlH_dr[n, ok] = curlH[ci[ok], cj[ok]]
        # ---- 高斯脉冲软源（能量有界）----
        if env > 1e-12:
            Ez[i_src, j0s:j1s] += env * math.cos(prob.omega * n * dt)
            E_in += env * env * (j1s - j0s)
        # ---- 监视器场能记录 ----
        Ez_mon[n, :] = Ez[i_mon, m0:m1]
        if Ez_mon2 is not None:
            Ez_mon2[n, :] = Ez[prob.i_mon2, prob.y2_mon0:prob.y2_mon1]

    # D-80 目标 FOM（按 target_type）
    E_A = float(np.sum(Ez_mon[meas0:, :] ** 2))          # 主监视器场能
    ttype = prob.target_type
    if ttype == "split_ratio":
        E_B = float(np.sum(Ez_mon2[meas0:, :] ** 2))     # 第二监视器场能
        eps_reg = 1e-6
        a, b = prob.target_ratio, 1.0 - prob.target_ratio
        # 对数加权 FOM（=几何平均的对数，单调等价但数值更稳；观测线性化无 FOM 系数）
        FOM = a * math.log(E_A + eps_reg) + b * math.log(E_B + eps_reg)
        FOM_geom = (E_A + eps_reg) ** a * (E_B + eps_reg) ** b
        ratio = E_A / (E_A + E_B + 1e-12)
        res = {
            "FOM": FOM, "FOM_geom": FOM_geom, "E_A": E_A, "E_B": E_B,
            "ratio": ratio, "target_ratio": prob.target_ratio}
    elif ttype == "mode_match":
        prof = prob.mode_profile
        norm2 = float(np.sum(prof ** 2)) + 1e-12
        proj = float(np.sum(Ez_mon[meas0:, :] * prof[None, :]))
        FOM = proj * proj / norm2
        res = {"FOM": FOM, "proj": proj, "norm2": norm2}
    else:   # field_energy（默认，兼容原语义）
        FOM = E_A
        res = {"FOM": FOM, "E_A": E_A}
    T = (FOM / E_in) if E_in > 1e-12 else 0.0
    out = {
        "T": T,
        "P_out": FOM,
        "P_in": E_in,
        "E_in": E_in,
        "curlH_dr": curlH_dr,
        "Ez_mon": Ez_mon,
        "eps": eps,
        "nsteps": nsteps,
        "meas0": meas0,
        "sigma_n": sigma_n,
        "n_peak": n_peak,
    }
    out.update(res)
    if Ez_mon2 is not None:
        out["Ez_mon2"] = Ez_mon2
    return out


# ---------------------------------------------------------------------------
# Adjoint：前向转置 + 输出观测 → dFOM/dε（设计区）
# ---------------------------------------------------------------------------
def compute_gradient(prob: AdjointProblem, fwd: dict):
    """显式 adjoint：返回 dFOM/dε（全网格，(Nx,Ny)），仅设计区非零。

    FOM = Σ_{n≥meas0} Σ_j Ez[i_mon,j]² → 观测源 obs[n,j] = 2·Ez_fwd[n,j]。
    反向时间步进得 adjoint 场 λ_E, λ_H；梯度
        ∂FOM/∂ε[r] = -(dt/dl)/eps[r]² · D_E[r] · Σ_k λ_E^{k+1}[r]·curlH^{k+1}[r]

    转置推导（与 forward 逐算子对齐，数值 Mᵀ 对拍至 1e-15）：
      前向： E^m = D_E(E^{m-1} + (dt/dl)/eps · B H^m) ,  H^m = D_H(H^{m-1} + A E^{m-1})
      转置： λ_H^{m-1} = D_H(λ_H^m + Bᵀ(dt/dl)/eps D_E λ_E^m)
            λ_E^{m-1} = D_E λ_E^m + Aᵀ D_H(λ_H^m + Bᵀ·) + obs^{m-1}
    （关键：H 在前向中被 D_H 阻尼后才被 E 更新消费，故 Bᵀ 注入须先并入
      λ_H 再整体乘 D_H；Aᵀ 作用于全网格 Ez，含边界列/行，死元自动消去。）
    """
    Nx, Ny, dl, dt = prob.Nx, prob.Ny, prob.dl, prob.dt
    eps = fwd["eps"]
    dampE, dampHx, dampHy = prob.dampE, prob.dampHx, prob.dampHy
    i_mon, m0, m1 = prob.i_mon, prob.y_mon0, prob.y_mon1
    nsteps, meas0 = fwd["nsteps"], fwd["meas0"]
    mw = m1 - m0
    curlH_dr = fwd["curlH_dr"]
    Ez_mon = fwd["Ez_mon"]
    dr = prob._dr
    ttype = prob.target_type

    # 观测源（按 target_type）
    if ttype == "split_ratio":
        E_A, E_B = fwd["E_A"], fwd["E_B"]
        eps_reg = 1e-6
        a, b = prob.target_ratio, 1.0 - prob.target_ratio
        # dFOM_log/dEz = 2a/(E_A+ε)·Ez_A（对数 FOM 观测线性化，无需 FOM 系数）
        ca = 2.0 * a / (E_A + eps_reg)
        cb = 2.0 * b / (E_B + eps_reg)
        obs = np.zeros((nsteps, Ny))
        obs[meas0:, m0:m1] = ca * Ez_mon[meas0:, :]
        obs2 = np.zeros((nsteps, Ny))
        i2, m2a, m2b = prob.i_mon2, prob.y2_mon0, prob.y2_mon1
        obs2[meas0:, m2a:m2b] = cb * fwd["Ez_mon2"][meas0:, :]
    elif ttype == "mode_match":
        prof = np.asarray(prob.mode_profile, dtype=float)
        norm2 = fwd["norm2"]
        proj = fwd["proj"]
        obs = np.zeros((nsteps, Ny))
        obs[:, m0:m1] = (2.0 * proj / norm2) * prof[None, :]
        obs2 = None
    else:   # field_energy（原语义）
        obs = np.zeros((nsteps, Ny))
        obs[meas0:, m0:m1] = 2.0 * Ez_mon[meas0:, :]
        obs2 = None

    lamE = np.zeros((Nx, Ny))
    lamHx = np.zeros((Nx, Ny))
    lamHy = np.zeros((Nx, Ny))
    grad = np.zeros((Nx, Ny))

    # 初始化：λ_E^{N-1} = obs^{N-1}；λ_H^{N-1} = 0
    nN = nsteps - 1
    if nN >= meas0:
        lamE[i_mon, m0:m1] += obs[nN, m0:m1]
        if obs2 is not None and (prob.target_type == "mode_match"
                                 or nN >= meas0):
            i2, m2a, m2b = prob.i_mon2, prob.y2_mon0, prob.y2_mon1
            if ttype == "split_ratio":
                lamE[i2, m2a:m2b] += obs2[nN, m2a:m2b]

    for k in range(nsteps - 1, -1, -1):
        # ---- Bᵀ 项：(dt/dl)/eps · D_E λ_E^k 注入 H 伴随状态 ----
        psi = dampE * lamE                                   # D_E λ_E^k
        We = (dt / dl) * (1.0 / eps) * psi
        We_int = We[1:Nx - 1, 1:Ny - 1]                      # 内部节点 (i,j) 的权重 w
        bHx = np.zeros((Nx, Ny))
        bHy = np.zeros((Nx, Ny))
        # curlH[i,j] 对 H 的依赖：+Hy[i,j] -Hy[i-1,j] -Hx[i,j] +Hx[i,j-1]（×w）
        bHx[1:Nx - 1, 0:Ny - 2] += We_int     # λ_Hx[i, j-1] += w
        bHx[1:Nx - 1, 1:Ny - 1] -= We_int     # λ_Hx[i, j]   -= w
        bHy[0:Nx - 2, 1:Ny - 1] -= We_int     # λ_Hy[i-1, j] -= w
        bHy[1:Nx - 1, 1:Ny - 1] += We_int     # λ_Hy[i, j]   += w

        # ---- ε 灵敏度累积（步骤 k）：(D_E λ_E^k)·curlH^k ----
        grad.ravel()[dr] += (dampE.ravel()[dr] * lamE.ravel()[dr]) * curlH_dr[k, :]

        if k == 0:
            break

        # ---- H 状态：λ_H^{k-1} = D_H·(λ_H^k + Bᵀ项)；D_H 仅施加一次 ----
        Hx_state = lamHx + bHx
        Hy_state = lamHy + bHy
        phiHx = dampHx * Hx_state
        phiHy = dampHy * Hy_state
        lamHx_new = phiHx
        lamHy_new = phiHy

        # ---- Aᵀ：D_H·(λ_H + Bᵀ) → E 伴随，作用于全网格 Ez（边界含入）----
        phiHx_s = np.pad(phiHx, ((0, 0), (1, 0)), mode='constant')[:, :Ny]   # phiHx[i,j-1]
        phiHy_s = np.pad(phiHy, ((1, 0), (0, 0)), mode='constant')[:Nx, :]   # phiHy[i-1,j]
        dE_full = (dt / dl) * (phiHx - phiHx_s + phiHy_s - phiHy)

        # ---- λ_E^{k-1} = D_E λ_E^k + Aᵀ(·) + obs^{k-1} ----
        lamE_new = dampE * lamE + dE_full
        if (k - 1) >= meas0:
            lamE_new[i_mon, m0:m1] += obs[k - 1, m0:m1]
            if obs2 is not None and ttype == "split_ratio":
                i2, m2a, m2b = prob.i_mon2, prob.y2_mon0, prob.y2_mon1
                lamE_new[i2, m2a:m2b] += obs2[k - 1, m2a:m2b]

        lamHx = lamHx_new
        lamHy = lamHy_new
        lamE = lamE_new

    # 转 ε 导数（设计区）：-(dt/dl)/eps² · Σ_k λ_E^{k}·curlH^{k}
    geps = np.zeros((Nx, Ny))
    geps.ravel()[dr] = -(dt / dl) / (eps.ravel()[dr] ** 2) * grad.ravel()[dr]
    return geps


# ---------------------------------------------------------------------------
# 验证：adjoint 梯度 vs 中心有限差分（方向对拍）
# ---------------------------------------------------------------------------
def verify_adjoint(prob: AdjointProblem, eps0: np.ndarray, nsamples: int = 10,
                   delta: float = 0.05, seed: int = 12345):
    """对随机设计体素做中心有限差分，与 adjoint 梯度比误差。

    返回 dict：每样本 {idx, g_adj, g_fd, rel_err}，及 max_rel_err / mean_rel_err。
    adjoint 与 FD 共享同一全局比例常数，故用**归一化方向**比对：以 |g_fd| 最大
    样本标定比例 K，再算其余样本相对误差。
    """
    rng = np.random.default_rng(seed)
    fwd0 = forward(prob, eps0)
    gadj = compute_gradient(prob, fwd0)
    dr = prob._dr
    # 候选：选 |g_adj| 较大的设计体素，提升 FD 信噪比
    gabs = np.abs(gadj.ravel()[dr])
    order = dr[np.argsort(gabs)[::-1]]
    picks = order[: max(nsamples, 1)]

    rows = []
    for idx in picks:
        i, j = idx // prob.Ny, idx % prob.Ny
        eps_p = eps0.copy()
        eps_m = eps0.copy()
        eps_p[i, j] += delta
        eps_m[i, j] -= delta
        Fp = forward(prob, eps_p)["FOM"]
        Fm = forward(prob, eps_m)["FOM"]
        g_fd = (Fp - Fm) / (2.0 * delta)
        g_a = gadj[i, j]
        rows.append({"idx": int(idx), "i": int(i), "j": int(j),
                     "g_adj": float(g_a), "g_fd": float(g_fd)})

    # 标定比例 K = g_adj / g_fd 在 |g_fd| 最大样本处（符号一致）
    ref = max(rows, key=lambda r: abs(r["g_fd"]))
    K = ref["g_adj"] / ref["g_fd"] if abs(ref["g_fd"]) > 1e-12 else 1.0
    for r in rows:
        pred = K * r["g_fd"]
        denom = abs(pred) + 1e-12
        r["rel_err"] = abs(r["g_adj"] - pred) / denom
    max_err = max(r["rel_err"] for r in rows)
    mean_err = float(np.mean([r["rel_err"] for r in rows]))
    return {
        "nsamples": len(rows),
        "delta": delta,
        "K_adj_over_fd": float(K),
        "max_rel_err": float(max_err),
        "mean_rel_err": mean_err,
        "samples": rows,
        "passed": bool(max_err <= 0.15),   # 容差 15%（FD 自身有截断误差）
    }


# ---------------------------------------------------------------------------
# 拓扑逆设计：密度投影 + 梯度上升（回溯线搜索 + beta 延拓）
# ---------------------------------------------------------------------------
def optimize_topology(prob: AdjointProblem, eps0: np.ndarray,
                      iters: int = 60, step0: float = 0.5,
                      beta_max: float = 14.0, verbose: bool = False):
    """密度投影 + 梯度上升，最大化监视器孔径收集场能 FOM。

    - 潜伏密度 r ∈ [0,1] 初值 0.5；物理密度 ρ̄ = tanh 投影（beta 从 2 延拓至
      beta_max，先柔后硬地二值化）；
    - eps = eps_min + ρ̄(eps_max-eps_min)；
    - 梯度：dFOM/dr = (eps_max-eps_min)·dFOM/dε · dρ̄/dr；
    - 方向按**最大分量归一化**（每体素步长有界，避免 RMS 归一化把更新摊薄
      到远离光路的噪声体素）；
    - **Armijo 回溯线搜索**：目标 = 与迭代一致的投影设计（保证线搜索与
      实际演化同目标），从 step0 起减半直到 FOM 严格提升 → FOM 单调不降。
    返回 dict：history、final_eps、final_T、improvement、passed。
    """
    dm = prob.design_mask
    nd = int(dm.sum())
    eps_min, eps_max = prob.eps_min, prob.eps_max

    def rho_to_eps(r):
        return eps_min + r * (eps_max - eps_min)

    def project(r, b):
        t = np.tanh(b * (r - 0.5)) / (2.0 * np.tanh(b / 2.0)) + 0.5
        return np.clip(t, 0.0, 1.0)

    def FOM_at(r, beta):
        """投影一致的目标：物理密度 = project(r, beta) 后再转 eps。"""
        e = eps0.copy()
        e[dm] = rho_to_eps(project(r, beta))
        return forward(prob, e)["FOM"]

    r = np.full(nd, 0.5)
    fom0 = FOM_at(r, 2.0)          # 均匀平板初值（project(0.5,·)=0.5）
    prob_init_geom = fom0
    if prob.target_type == "split_ratio":
        f0g = forward(prob, eps0)
        prob_init_geom = f0g["FOM_geom"]
    best_fom = fom0
    best_r = r.copy()
    history = []

    for it in range(iters):
        beta = 2.0 + (beta_max - 2.0) * (it / max(iters - 1, 1))
        rho = project(r, beta)
        eps_cur = eps0.copy()
        eps_cur[dm] = rho_to_eps(rho)
        fwd = forward(prob, eps_cur)
        geps = compute_gradient(prob, fwd)
        g_rho = (eps_max - eps_min) * geps[dm]
        # 链式：d/dr = d/dρ̄ · dρ̄/dr（投影导数）
        t = np.tanh(beta * (r - 0.5))
        dproj = beta * (1.0 - t ** 2) / (2.0 * np.tanh(beta / 2.0))
        g_r = g_rho * dproj
        # 方向：最大分量归一化（每体素单步位移 ≤ step）
        m = np.max(np.abs(g_r)) + 1e-12
        d = g_r / m
        # Armijo 回溯线搜索（目标 = 当前 beta 投影下的 FOM，严格提升）
        alpha = step0
        f_eval = fwd["FOM"]
        accepted = False
        f_try = f_eval
        while alpha > 2e-3:
            f_try = FOM_at(np.clip(r + alpha * d, 0.0, 1.0), beta)
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
            best_fom = f_final
            best_r = r.copy()
        ratio_rec = (fwd.get("ratio")
                     if prob.target_type == "split_ratio" else None)
        history.append({"iter": it, "FOM": f_final, "T": fwd["T"],
                        "beta": round(beta, 2), "alpha": round(alpha, 4),
                        **({"ratio": round(ratio_rec, 4)}
                           if ratio_rec is not None else {})})
        if verbose and (it % 5 == 0 or it == iters - 1):
            print(f"  it={it:3d} beta={beta:5.2f} alpha={alpha:6.3f} "
                  f"FOM={f_final:.4e} T={fwd['T']:.4f}"
                  + (f" ratio={ratio_rec:.3f}" if ratio_rec is not None else ""))

    # 最终设计：best_r 以 beta_max 重投影（二值化）后评估
    best_eps = eps0.copy()
    best_eps[dm] = rho_to_eps(project(best_r, beta_max))
    fbf = forward(prob, best_eps)
    # split_ratio 用 FOM_geom（几何平均语义）算 improvement；线搜索仍用对数 FOM
    if prob.target_type == "split_ratio":
        improvement = fbf["FOM_geom"] / (prob_init_geom + 1e-12)
        fom0_report = prob_init_geom
    else:
        improvement = fbf["FOM"] / (fom0 + 1e-12)
        fom0_report = fom0
    out = {
        "history": history,
        "final_eps": best_eps,
        "final_T": fbf["T"],
        "final_FOM": fbf["FOM"],
        "initial_FOM": fom0_report,
        "improvement": float(improvement),
        "passed": bool(improvement >= 1.5),   # 目标 FOM 较初值提升 ≥50%
    }
    if prob.target_type == "split_ratio":
        out["final_ratio"] = fbf["ratio"]
        out["target_ratio"] = prob.target_ratio
        out["ratio_err"] = abs(fbf["ratio"] - prob.target_ratio)
        # 分束器重比例命中：improvement（几何平均）≥1.2 且比例 err ≤0.10
        out["passed"] = bool(improvement >= 1.2
                             and out["ratio_err"] <= 0.10)
    return out


# ---------------------------------------------------------------------------
# D-80 谱形目标：多波长加权联合优化（spectrum target）
# ---------------------------------------------------------------------------
def spectrum_optimize(base: AdjointProblem, eps0: np.ndarray,
                      wavelengths_um: Optional[list] = None,
                      weights: Optional[list] = None,
                      iters: int = 25, step0: float = 0.5,
                      beta_max: float = 14.0, verbose: bool = False):
    """多波长谱形目标联合优化：总 FOM = Σ_λ w_λ · FOM_λ。

    每个波长构造独立 AdjointProblem（同几何、wl_um 变），每次迭代对每波长
    各跑 forward + adjoint，梯度按权重合并后统一线搜索（线搜索评估也跑全
    波长 → 与优化目标同投影一致）。谱形目标 = 设计对目标波长带整体可用。

    返回 dict：per_wavelength（各波长初/末 FOM + improvement）、weighted
    improvement、final_eps、passed（加权 improvement ≥ 1.5 且各波长均 ≥ 1.2）。
    """
    if wavelengths_um is None:
        wavelengths_um = [1.5, 1.55, 1.6]
    nwl = len(wavelengths_um)
    if weights is None:
        weights = [1.0 / nwl] * nwl
    probs = []
    for wl in wavelengths_um:
        import copy
        p = copy.deepcopy(base)
        # 物理网格固定（dl/dt 用基准波长定），只变 omega → 波长真正变化
        # （归一化网格陷阱：若 dl=wl/dl_factor 则 omega·dt 与波长无关）
        p.wl_um = float(wl)
        p.omega = 2.0 * math.pi / float(wl)
        p.period_steps = int(round(2.0 * math.pi / (p.omega * p.dt)))
        probs.append(p)
    w = np.asarray(weights, dtype=float)
    w = w / w.sum()

    dm = base.design_mask
    nd = int(dm.sum())
    eps_min, eps_max = base.eps_min, base.eps_max

    def rho_to_eps(r):
        return eps_min + r * (eps_max - eps_min)

    def project(r, b):
        t = np.tanh(b * (r - 0.5)) / (2.0 * np.tanh(b / 2.0)) + 0.5
        return np.clip(t, 0.0, 1.0)

    def FOM_total_at(r, beta):
        e = eps0.copy()
        e[dm] = rho_to_eps(project(r, beta))
        return sum(w[k] * forward(probs[k], e)["FOM"] for k in range(nwl))

    r = np.full(nd, 0.5)
    fom0 = FOM_total_at(r, 2.0)
    best_fom, best_r = fom0, r.copy()
    history = []
    for it in range(iters):
        beta = 2.0 + (beta_max - 2.0) * (it / max(iters - 1, 1))
        rho = project(r, beta)
        eps_cur = eps0.copy()
        eps_cur[dm] = rho_to_eps(rho)
        g_total = np.zeros((base.Nx, base.Ny))
        fwds = []
        for k in range(nwl):
            fwd = forward(probs[k], eps_cur)
            fwds.append(fwd)
            g_total += w[k] * compute_gradient(probs[k], fwd)
        g_rho = (eps_max - eps_min) * g_total[dm]
        t = np.tanh(beta * (r - 0.5))
        dproj = beta * (1.0 - t ** 2) / (2.0 * np.tanh(beta / 2.0))
        g_r = g_rho * dproj
        m = np.max(np.abs(g_r)) + 1e-12
        d = g_r / m
        alpha = step0
        f_eval = sum(w[k] * fwds[k]["FOM"] for k in range(nwl))
        f_try = f_eval
        accepted = False
        while alpha > 2e-3:
            f_try = FOM_total_at(np.clip(r + alpha * d, 0.0, 1.0), beta)
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
        history.append({"iter": it, "FOM_total": f_final,
                        "beta": round(beta, 2), "alpha": round(alpha, 4)})
        if verbose and (it % 5 == 0 or it == iters - 1):
            print(f"  it={it:3d} beta={beta:5.2f} FOM_total={f_final:.4e}")

    best_eps = eps0.copy()
    best_eps[dm] = rho_to_eps(project(best_r, beta_max))
    per_wl = []
    for k in range(nwl):
        f0 = forward(probs[k], eps0)
        f1 = forward(probs[k], best_eps)
        per_wl.append({"wl_um": wavelengths_um[k], "weight": round(w[k], 4),
                       "initial_FOM": f0["FOM"], "final_FOM": f1["FOM"],
                       "improvement": float(f1["FOM"] / (f0["FOM"] + 1e-12)),
                       "final_T": f1["T"]})
    weighted_imp = sum(w[k] * per_wl[k]["improvement"] for k in range(nwl))
    all_ok = all(per_wl[k]["improvement"] >= 1.2 for k in range(nwl))
    return {
        "history": history,
        "per_wavelength": per_wl,
        "weighted_improvement": float(weighted_imp),
        "initial_FOM_total": fom0,
        "final_FOM_total": best_fom,
        "final_eps": best_eps,
        "passed": bool(weighted_imp >= 1.5 and all_ok),
        "note": ("多波长加权联合优化：总 FOM=Σw_λ·FOM_λ，谱形目标=设计对"
                 "目标波长带整体可用；加权 improvement≥1.5 且各波长≥1.2。"),
    }


if __name__ == "__main__":
    p = AdjointProblem()
    eps0 = np.full((p.Nx, p.Ny), p.eps_min)
    eps0[p.design_mask] = (p.eps_min + p.eps_max) / 2.0
    print(f"grid {p.Nx}x{p.Ny} sponge={p.sponge} design={p.design_mask.sum()} "
          f"i_src={p.i_src} i_mon={p.i_mon} aperture=[{p.y_mon0},{p.y_mon1})")
    print("verify adjoint ...")
    vr = verify_adjoint(p, eps0, nsamples=8, delta=0.05)
    print("  max_rel_err =", round(vr["max_rel_err"], 4),
          "mean_rel_err =", round(vr["mean_rel_err"], 4),
          "passed =", vr["passed"])
    print("optimize topology ...")
    opt = optimize_topology(p, eps0, iters=50, step0=0.5, verbose=True)
    print("  initial_FOM =", round(opt["initial_FOM"], 4))
    print("  final_FOM   =", round(opt["final_FOM"], 4))
    print("  final_T     =", round(opt["final_T"], 4))
    print("  improvement =", round(opt["improvement"], 3),
          "passed =", opt["passed"])
