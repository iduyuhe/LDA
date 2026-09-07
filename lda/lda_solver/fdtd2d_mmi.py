"""2D TEz 时域有限差分（FDTD）求解核 + MMI 1×2 过量损耗。

用途
----
为实证锚 **E5（E-MMI-1X2-EL，MMI 1×2 过量损耗，golden 0.05 dB / tol 0.1 dB）**
提供一条**与 EME 方法学独立**的第二求解路线，用于对账：

    EME（代数本征模展开，``mmi_eme.py``）  vs  本模块（时域全场 Yee 步进）

两者共享的只有「2D-EIM 抽象 + 横向离散栅格」；传播方式完全不同（EME 用
解析 exp(iβL) 传播，FDTD 用离散麦克斯韦方程时域推进）。因此
**它们的分歧 = 数值缺陷；它们的一致 = 2D-EIM 抽象本身的性质**。

单位制与离散
------------
归一化 ε0 = µ0 = c0 = 1，µ_r ≡ 1，ε = n²。场分量 Ez（节点）
/ Hx（y 半格）/ Hy（x 半格）。更新式：

    ∂Ez/∂t = (1/ε)(∂Hy/∂x − ∂Hx/∂y)
    ∂Hx/∂t = −∂Ez/∂y
    ∂Hy/∂t = +∂Ez/∂x

CFL：波速 c = 1/n，最苛刻处为包层 n_clad ⇒ dt ≤ dl·n_clad/√2。
本模块取 ``dt = 0.9·dl``（n_clad=1.44 时 = CFL 上限的 88%）。

吸收层
------
阻抗匹配海绵：E 与 H **按同一速率** s = σ/ε 阻尼。因 µ_r≡1，匹配条件
σ* = σ/ε 恰好等价于「E、H 同率衰减」；s 沿法向二次渐升，避免突变反射。

🔴 历史教训（v0.9.56 第一版 FDTD 失败，实现已废弃重写）
----------------------------------------------------
第一版报「直波导导模沿线衰减 0.7 dB/µm 且非单调」，曾据此判定 FDTD 不可用。
v0.9.57 重写时定位到**两处测量/实现缺陷，均非 FDTD 方法本身的病**：

1. **本征求解器带状存储用错**：scipy ``eig_banded`` 对称三对角应为 ``(u+1, N)``
   = ``(2, N)``，误传 ``(3, N)`` ⇒ 解出 n_eff≈16（真值 2.57）。本模块改为
   复用 ``mmi_eme.slab_modes``（稠密 ``eigh``，已与解析超越方程交叉校验）。
2. **控制实验的监测面落在波包内部**：入射监测面取 x=6 µm，而波包中心 x=5 µm、
   σ=1.6 µm ⇒ 下游约 27% 的能量**根本不会穿过该面**，被误读成"能量沿程增长"。
   两监测面全部移到波包下游后，实测 **10 µm 上 −0.00001 dB**（见
   ``straight_waveguide_conservation``）。

⇒ 铁律：**控制实验失败时，先怀疑测量布置与本征求解器，再怀疑方法。**
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np

try:                                     # 包内导入（lda_solver 作为包）
    from .mmi_eme import (N_CLAD_2D, N_CORE_2D, MMI_L_UM, MMI_W_UM,
                          slab_modes, _guide_eps)
except ImportError:                      # 脚本直连（sys.path 已含 lda_solver）
    from mmi_eme import (N_CLAD_2D, N_CORE_2D, MMI_L_UM, MMI_W_UM,
                         slab_modes, _guide_eps)

__all__ = [
    "DT_RATIO", "Fdtd2DTe", "sponge_rate", "build_epsilon",
    "waveguide_mode", "straight_waveguide_conservation",
    "mmi_excess_loss_fdtd", "cross_check_with_eme",
]

DT_RATIO = 0.9          # dt = DT_RATIO * dl


# --------------------------------------------------------------------- 网格
def _odd(n: int) -> int:
    """🔴 强制奇数网格数。

    横向必须**关于 y=0 严格对称**：``(j − (N−1)/2)·dl`` 只有当 N 为奇数时
    才含 y=0 节点。N 为偶数 ⇒ 整个结构被平移 dl/2，MMI 有效宽度由 W 变成
    W−dl（如 W=2.8、dl=0.05 ⇒ 2.775 µm，0.9% 偏差）。对本锚这种干涉型器件，
    0.9% 宽度误差 ⇒ L_π 偏 1.8% ⇒ excess 偏 ~0.4 dB，**足以伪造出"两法对账
    一致"的假象**（v0.9.57 实测：未修正前 dl=0.05 两法差 0.03 dB，dl=0.025
    差 1.18 dB —— 前者纯属巧合）。对账对象 ``mmi_eme.build_basis`` 用的正是
    ``Ny = int(round(...)) | 1``，本函数必须与之对齐。
    """
    return int(n) | 1


def _y_nodes(ny: int, dl: float) -> np.ndarray:
    return (np.arange(_odd(ny)) - (_odd(ny) - 1) / 2.0) * dl


def _x_nodes(nx: int, dl: float) -> np.ndarray:
    return np.arange(nx) * dl


def build_epsilon(nx: int, ny: int, dl: float, n_core: float, n_clad: float,
                  regions: Sequence[Tuple[float, float, float, float]]
                  ) -> np.ndarray:
    """按 Ez 节点栅格化矩形高折射率区。regions = [(x0, x1, y_center, width)]。

    栅格化准则与本模块对账对象 ``mmi_eme._guide_eps`` **完全一致**
    （``|y − y_center| ≤ w/2``），保证两条路线比的是同一个离散结构。
    """
    xs = _x_nodes(nx, dl)[:, None] * np.ones((1, ny))
    ys = np.ones((nx, 1)) * _y_nodes(ny, dl)[None, :]
    eps = np.full((nx, ny), n_clad ** 2, dtype=np.float64)
    for (x0, x1, yc, w) in regions:
        eps[(np.abs(ys - yc) <= w / 2.0) & (xs >= x0) & (xs <= x1)] = n_core ** 2
    return eps


def sponge_rate(nx: int, ny: int, dl: float, n_cells: int,
                s_max: float = 3.0, order: int = 2) -> np.ndarray:
    """阻抗匹配海绵的衰减率场 s(x, y) = σ/ε（1/时间）。

    E 与 H 按同一 s 阻尼即满足匹配条件（µ_r ≡ 1 ⇒ σ* = σ/ε）；
    s 沿法向按 ``order`` 次幂渐升，避免界面突变反射。
    """
    s = np.zeros((nx, ny))
    if n_cells <= 0:
        return s
    ix = np.arange(nx)
    px = s_max * np.maximum(np.clip((n_cells - ix) / n_cells, 0.0, 1.0),
                            np.clip((ix - (nx - 1 - n_cells)) / n_cells,
                                    0.0, 1.0)) ** order
    iy = np.arange(ny)
    py = s_max * np.maximum(np.clip((n_cells - iy) / n_cells, 0.0, 1.0),
                            np.clip((iy - (ny - 1 - n_cells)) / n_cells,
                                    0.0, 1.0)) ** order
    return np.maximum(px[:, None], py[None, :])


def waveguide_mode(ys: np.ndarray, w_um: float, y_center: float, dl: float,
                   wl_um: float, n_core: float, n_clad: float
                   ) -> Tuple[float, np.ndarray]:
    """单根波导基模 → (n_eff, φ)，φ 欧氏归一（与 EME 同一约定）。"""
    eps = _guide_eps(ys, w_um, y_center, n_core, n_clad)
    neff, modes = slab_modes(eps, dl, wl_um, n_clad)
    if modes.shape[1] == 0:
        raise ValueError("波导无导模（几何/折射率不支持束缚模）")
    m = np.asarray(modes[:, 0], dtype=float)
    if abs(float(m.min())) > abs(float(m.max())):
        m = -m
    return float(neff[0]), m


# ----------------------------------------------------------------- Yee 核心
class Fdtd2DTe:
    """2D TEz（Ez, Hx, Hy）Yee 步进器，含阻抗匹配海绵。"""

    def __init__(self, eps: np.ndarray, dl: float,
                 dt_ratio: float = DT_RATIO, s: np.ndarray | None = None):
        self.eps = eps
        self.nx, self.ny = eps.shape
        self.dl = dl
        self.dt = dt_ratio * dl
        # CFL：dt ≤ dl·n_clad/√2（n_clad = sqrt(min ε)）
        n_min = math.sqrt(float(eps.min()))
        if self.dt >= dl * n_min / math.sqrt(2.0):
            raise ValueError(
                f"CFL 违反：dt={self.dt:.5g} ≥ dl·n_min/√2="
                f"{dl * n_min / math.sqrt(2.0):.5g}")
        self.Ez = np.zeros((self.nx, self.ny))
        self.Hx = np.zeros((self.nx, self.ny - 1))
        self.Hy = np.zeros((self.nx - 1, self.ny))
        self.s = np.zeros_like(eps) if s is None else s
        half = self.dt * self.s / 2.0
        self.fE = (1.0 - half) / (1.0 + half)
        self.cE = (self.dt / self.eps) / (1.0 + half)
        sHx = 0.5 * (self.s[:, :-1] + self.s[:, 1:])
        hHx = self.dt * sHx / 2.0
        self.fHx = (1.0 - hHx) / (1.0 + hHx)
        self.cHx = self.dt / (1.0 + hHx)
        sHy = 0.5 * (self.s[:-1, :] + self.s[1:, :])
        hHy = self.dt * sHy / 2.0
        self.fHy = (1.0 - hHy) / (1.0 + hHy)
        self.cHy = self.dt / (1.0 + hHy)
        self._curl = np.zeros_like(self.Ez)

    def step(self) -> None:
        Ez, Hx, Hy, dl = self.Ez, self.Hx, self.Hy, self.dl
        curl = self._curl
        curl[1:-1, 1:-1] = ((Hy[1:, 1:-1] - Hy[:-1, 1:-1])
                            - (Hx[1:-1, 1:] - Hx[1:-1, :-1])) / dl
        Ez[1:-1, 1:-1] = (self.fE[1:-1, 1:-1] * Ez[1:-1, 1:-1]
                          + self.cE[1:-1, 1:-1] * curl[1:-1, 1:-1])
        Hx[:, :] = self.fHx * Hx - self.cHx * (Ez[:, 1:] - Ez[:, :-1]) / dl
        Hy[:, :] = self.fHy * Hy + self.cHy * (Ez[1:, :] - Ez[:-1, :]) / dl

    def hy_at_node(self, ix: int) -> np.ndarray:
        """Hy 从 x 半格插值到 Ez 节点 ix。"""
        if 0 < ix < self.nx - 1:
            return 0.5 * (self.Hy[ix - 1, :] + self.Hy[ix, :])
        return self.Hy[0, :] if ix == 0 else self.Hy[-1, :]

    def poynting_x(self, ix: int) -> float:
        """穿过 x = ix·dl 平面的瞬时功率 ∫ −Ez·Hy dy（前向为正）。"""
        return float(-np.sum(self.Ez[ix, :] * self.hy_at_node(ix)) * self.dl)

    def field_energy(self) -> float:
        """域内场能 ½∫(ε|E|² + |H|²)（µ_r ≡ 1）。"""
        Hy_n = np.zeros_like(self.Ez)
        Hy_n[1:-1, :] = 0.5 * (self.Hy[:-1, :] + self.Hy[1:, :])
        Hx_n = np.zeros_like(self.Ez)
        Hx_n[:, 1:-1] = 0.5 * (self.Hx[:, :-1] + self.Hx[:, 1:])
        return float(0.5 * np.sum(self.eps * self.Ez ** 2
                                  + Hy_n ** 2 + Hx_n ** 2) * self.dl ** 2)

    def launch_mode_packet(self, phi: np.ndarray, n_eff: float,
                           x_center: float, sigma: float, wl_um: float
                           ) -> None:
        """在波导内注入一个**纯前向**导模高斯波包作为初值（无需源项）。

        取 Ez = Re{φ(y)·F(x)·e^{iβx}}（e^{−iωt} 约定），则由 Maxwell
            Hy = −(β/ωµ)·Ez = −n_eff·Ez ，  Hx = (1/ω)·φ'(y)·F(x)·sin(βx)
        （包络缓变近似，忽略 F' 项）。符号错会导致波包倒行，
        故 ``straight_waveguide_conservation`` 对该式常驻把关。
        """
        k0 = 2.0 * math.pi / wl_um
        beta, om = k0 * n_eff, k0
        xs = _x_nodes(self.nx, self.dl)
        F = np.exp(-0.5 * ((xs - x_center) / sigma) ** 2)
        Ez0 = np.outer(F * np.cos(beta * xs), phi)
        Hs = np.outer(F * np.sin(beta * xs), np.gradient(phi, self.dl)) / om
        self.Ez[:, :] = Ez0
        self.Hx[:, :] = 0.5 * (Hs[:, 1:] + Hs[:, :-1])
        self.Hy[:, :] = -n_eff * 0.5 * (Ez0[1:, :] + Ez0[:-1, :])


# ----------------------------------------------- 控制实验 C1：直波导保幅
def straight_waveguide_conservation(dl: float = 0.05, Lx: float = 30.0,
                                    Ly: float = 6.0, w_um: float = 0.5,
                                    n_core: float = N_CORE_2D,
                                    n_clad: float = N_CLAD_2D,
                                    wl_um: float = 1.55,
                                    x_center: float = 4.0, sigma: float = 1.2,
                                    x_mon: Sequence[float] = (12.0, 22.0),
                                    t_max: float | None = None,
                                    sponge_um: float = 1.2
                                    ) -> Dict[str, float]:
    """🔴 闸门：无损直波导中，两个监测面的**时间积分能流**必须相等。

    这是本求解核唯一不可绕过的自证：通不过就没有资格判任何锚题。
    注意两个监测面都必须位于**初始波包下游**（见模块 docstring 教训 2）。
    """
    nx, ny = int(round(Lx / dl)), _odd(int(round(Ly / dl)))
    ys = _y_nodes(ny, dl)
    eps = build_epsilon(nx, ny, dl, n_core, n_clad, [(0.0, Lx, 0.0, w_um)])
    s = sponge_rate(nx, ny, dl, int(round(sponge_um / dl)))
    sim = Fdtd2DTe(eps, dl, DT_RATIO, s)
    n_eff, phi = waveguide_mode(ys, w_um, 0.0, dl, wl_um, n_core, n_clad)
    sim.launch_mode_packet(phi, n_eff, x_center, sigma, wl_um)
    if t_max is None:
        t_max = 2.0 * (max(x_mon) + 4.0) * n_eff
    nsteps = int(round(t_max / sim.dt))
    idx = [int(round(x / dl)) for x in x_mon]
    e_start = sim.field_energy()
    flux = [0.0] * len(idx)
    for _ in range(nsteps):
        sim.step()
        for k, i in enumerate(idx):
            flux[k] += sim.poynting_x(i) * sim.dt
    span = abs(x_mon[-1] - x_mon[0])
    ratios = [flux[k] / flux[0] for k in range(len(idx))]
    return {
        "n_eff": float(n_eff),
        "flux": [float(f) for f in flux],
        "ratios": [float(r) for r in ratios],
        "db_total": float(-10.0 * math.log10(max(ratios[-1], 1e-300))),
        "db_per_um": float(-10.0 * math.log10(max(ratios[-1], 1e-300))
                           / max(span, 1e-12)),
        "span_um": float(span),
        "energy_initial": e_start,
        "energy_residual": sim.field_energy(),
        "nsteps": nsteps,
    }


# ------------------------------------------------------- MMI 1×2 过量损耗
def mmi_excess_loss_fdtd(dl: float = 0.05, L_mmi: float = MMI_L_UM,
                         W_mmi: float = MMI_W_UM, w_um: float = 0.5,
                         out_gap: float = 0.9,
                         n_core: float = N_CORE_2D, n_clad: float = N_CLAD_2D,
                         wl_um: float = 1.55,
                         Lx: float = 50.0, Ly: float = 6.0,
                         x_in: float = 9.0, x0: float = 16.0,
                         x_out: Sequence[float] = (43.5, 47.0),
                         x_center: float = 3.0, sigma: float = 1.2,
                         t_max: float = 1200.0, t_gate: float = 40.0,
                         t_ends: Sequence[float] = (900.0, 1000.0,
                                                    1100.0, 1200.0),
                         sponge_um: float = 1.2) -> Dict[str, object]:
    """MMI 1×2 过量损耗（dB）：短脉冲激励 + **单频 DFT + 方向性通量**。

    三个设计要点（每条都对应一个已修的真实缺陷）：

    1. **功率取方向性 Poynting 通量** P = −½Re(Ã_E·conj(Ã_H))，而非
       |Σφ·Ẽ|²。后者**不区分传播方向**——晚到的回程光会被相干叠加进
       输出幅度，实测可让远端监测面比近端"少 0.3 dB 损耗"（物理上不可能）。
       对 F·e^{iβx} + B·e^{−iβx}，通量式给出 ½n_eff(|F|²−|B|²)，自动剔除 B。
    2. **线性系统 ⇒ 脉冲带宽不影响单色传输函数提取**，故可用短脉冲一次跑出
       λ=1.55 µm 响应；入射监测面用时间窗排除 MMI 反射（反射回到该面需
       2·(x0−x_in)·n_g，远晚于入射脉冲）。
    3. **时程只跑一次，多个截断点共用**（`t_ends`）⇒ 免费拿到收敛表，
       判据可断言"结果不随 t_max 漂移"。

    🔴 **长尾是物理的，不是数值缺陷**（诊断见 ``_diag_tail`` 结论）：MMI 段内
    被全反射困住的高角度光线，轴向群速 ≈ cos(59.1°)·c/n（临界角
    arcsin(1.44/2.80) = 30.9° ⇒ 与轴夹角 59.1°），走完 27 µm 需 ≈147 个
    时间单位；实测残余场能衰减常数 τ ≈ 150，与之一致。实测收敛轨迹：

        t_end: 200 → 300 → 400 → 600 → 800 → 1000 → 1200
        dB   : 4.17 → 4.47 → 4.05 → 3.88 → 3.81 → 4.00 → 3.98

    即 **t_max < 900 时结果尚在 ±0.3 dB 摆动**，必须跑到 1200 才稳
    （900→1200 波动仅 0.027 dB）。故默认 t_max=1200，且 `t_end_drift_db`
    是判据必查字段。
    """
    nx, ny = int(round(Lx / dl)), _odd(int(round(Ly / dl)))
    ys = _y_nodes(ny, dl)
    y_split = out_gap / 2.0 + w_um / 2.0
    x1 = x0 + L_mmi
    regions = [(0.0, x0, 0.0, w_um),
               (x0, x1, 0.0, W_mmi),
               (x1, Lx, +y_split, w_um),
               (x1, Lx, -y_split, w_um)]
    eps = build_epsilon(nx, ny, dl, n_core, n_clad, regions)
    s = sponge_rate(nx, ny, dl, int(round(sponge_um / dl)))
    sim = Fdtd2DTe(eps, dl, DT_RATIO, s)

    n_eff, phi_in = waveguide_mode(ys, w_um, 0.0, dl, wl_um, n_core, n_clad)
    _, phi_up = waveguide_mode(ys, w_um, +y_split, dl, wl_um, n_core, n_clad)
    _, phi_dn = waveguide_mode(ys, w_um, -y_split, dl, wl_um, n_core, n_clad)
    sim.launch_mode_packet(phi_in, n_eff, x_center, sigma, wl_um)

    om = 2.0 * math.pi / wl_um
    nsteps = int(round(t_max / sim.dt))
    i_in = int(round(x_in / dl))
    i_out = [int(round(x / dl)) for x in x_out]
    ts = np.arange(nsteps) * sim.dt
    n_port = len(i_out)
    # 每个监测面记 (E 投影, H 投影)：E 用于幅度，H 用于定向
    e_in = np.zeros(nsteps); h_in = np.zeros(nsteps)
    e_p = np.zeros((nsteps, n_port, 2)); h_p = np.zeros((nsteps, n_port, 2))
    for it in range(nsteps):
        sim.step()
        e_in[it] = np.dot(sim.Ez[i_in, :], phi_in)
        h_in[it] = np.dot(sim.hy_at_node(i_in), phi_in)
        for k, i in enumerate(i_out):
            hy = sim.hy_at_node(i)
            e_p[it, k, 0] = np.dot(sim.Ez[i, :], phi_up)
            e_p[it, k, 1] = np.dot(sim.Ez[i, :], phi_dn)
            h_p[it, k, 0] = np.dot(hy, phi_up)
            h_p[it, k, 1] = np.dot(hy, phi_dn)

    phase = np.exp(1j * om * ts)
    gate = (ts <= t_gate).astype(float)
    # 入射：门内只有前向波 ⇒ 通量即 |F|²（归一化因子 n_eff·dl/2 在比值中约掉）
    ae_in = np.sum(e_in * gate * phase) * sim.dt
    ah_in = np.sum(h_in * gate * phase) * sim.dt
    p_in = float(-0.5 * (ae_in * np.conj(ah_in)).real)
    if p_in <= 0:
        raise RuntimeError("入射通量为非正 —— 前向波包初值符号或门控有误")

    conv = {}
    for t_end in t_ends:
        m = ts <= t_end
        ph = phase[m]
        a_up = np.einsum('t,tp->p', ph, e_p[m][:, :, 0]) * sim.dt
        h_up = np.einsum('t,tp->p', ph, h_p[m][:, :, 0]) * sim.dt
        a_dn = np.einsum('t,tp->p', ph, e_p[m][:, :, 1]) * sim.dt
        h_dn = np.einsum('t,tp->p', ph, h_p[m][:, :, 1]) * sim.dt
        p_up = -0.5 * (a_up * np.conj(h_up)).real
        p_dn = -0.5 * (a_dn * np.conj(h_dn)).real
        ports = {}
        for k, xk in enumerate(x_out):
            pk = float(p_up[k] + p_dn[k])
            T = pk / p_in
            ports[float(xk)] = {
                "value": float(-10.0 * math.log10(max(T, 1e-300))),
                "T": float(T),
                "balance": float(abs(p_up[k] - p_dn[k])
                                 / max(abs(p_up[k] + p_dn[k]), 1e-300)),
            }
        conv[float(t_end)] = {
            "ports": ports,
            "value": ports[float(min(x_out))]["value"],
            "T": ports[float(min(x_out))]["T"],
            "spread_db": float(max(p["value"] for p in ports.values())
                               - min(p["value"] for p in ports.values())),
        }
    best = conv[float(max(t_ends))]
    vals = [conv[float(t)]["value"] for t in t_ends]
    return {
        "value": best["value"], "T": best["T"],
        "ports": best["ports"],
        "convergence": {str(k): v for k, v in conv.items()},
        "t_end_drift_db": float(max(vals) - min(vals)),
        "t_ends": [float(t) for t in t_ends],
        "spread_db": best["spread_db"],
        "n_eff_in": float(n_eff), "y_split_um": float(y_split),
        "nx": nx, "ny": ny, "nsteps": nsteps, "dt": sim.dt, "dl": dl,
        "energy_residual": sim.field_energy(),
        "p_in": p_in,
    }


def discrete_axial_beta(eps_y: np.ndarray, dl: float, wl_um: float,
                        dt_ratio: float = DT_RATIO
                        ) -> Tuple[np.ndarray, np.ndarray]:
    """Yee 二维离散色散下的**轴向波数** β̃_m（与 EME 的半离散 β_m = √λ_m 对照）。

    对横向本征模（[D2 + k0²ε]φ = λ_m φ，λ_m = β_m²）有 −D2φ = (k0²ε − λ_m)φ，
    故 ⟨φ|−D2|φ⟩ = k0²⟨ε⟩_m − λ_m。投影到该模的离散色散为

        ⟨ε⟩_m·sin²(ωdt/2)/dt² = sin²(β̃·dl/2)/dl² + ¼(k0²⟨ε⟩_m − λ_m)

    🔴 **ε 因子不可漏**：漏掉会解出完全错误的分支（实测会给 β̃≈3.9 而真值 11.3）。

    ✅ **已用 FDTD 直接实测验证**（`_measure_beta` 方法：直平板波导多监测面
    DFT 相位拟合，5 µm 大间距 + 解析值定 2π 整数）：

        dl=0.05  实测 11.44009  解析 11.44015  （差 6e-5）
        dl=0.02  实测 11.32310  解析 11.32308  （差 2e-5）
    """
    k0 = 2.0 * math.pi / wl_um
    neff, modes = slab_modes(eps_y, dl, wl_um, math.sqrt(float(eps_y.min())))
    lam = (k0 * neff) ** 2
    dt = dt_ratio * dl
    om = k0
    out = np.full(len(neff), float("nan"))
    for m in range(modes.shape[1]):
        e_avg = float(np.sum(modes[:, m] ** 2 * eps_y))
        s = dl * dl * (e_avg * math.sin(om * dt / 2.0) ** 2 / dt ** 2
                       - 0.25 * (k0 * k0 * e_avg - lam[m]))
        if 0.0 < s < 1.0:
            out[m] = 2.0 * math.asin(math.sqrt(s)) / dl
    return neff, out


def beat_dispersion_error(dl: float = 0.05, W_mmi: float = MMI_W_UM,
                          wl_um: float = 1.55, n_core: float = N_CORE_2D,
                          n_clad: float = N_CLAD_2D, Ly: float = 6.0,
                          db_per_rel_err: float = 20.0) -> Dict[str, float]:
    """FDTD 二阶数值色散对 **MMI 拍长**的影响（判"FDTD 够不够格"的尺子）。

    EME 用半离散 β_m，FDTD 用离散 β̃_m；两者拍长 (β_0−β_1) 的相对差即
    **纯数值色散**误差。实测近似

        相对拍长误差 ≈ 1721·dl²   （dl 单位 µm，已验证 O(dl²) 标度）

    再用 EME 实测灵敏度（L_π 相对误差 ε ⇒ excess 摆动约 20·ε dB）折算成 dB。
    """
    ny = _odd(int(round(Ly / dl)))
    ys = _y_nodes(ny, dl)
    eps = _guide_eps(ys, W_mmi, 0.0, n_core, n_clad)
    k0 = 2.0 * math.pi / wl_um
    neff, bt = discrete_axial_beta(eps, dl, wl_um)
    if np.isnan(bt[0]) or np.isnan(bt[1]):
        raise ValueError("该网格下无法解出离散轴向波数（网格过粗或 CFL 违反）")
    d_exact = k0 * (neff[0] - neff[1])
    d_fdtd = bt[0] - bt[1]
    rel = (d_fdtd - d_exact) / d_exact
    est_db = abs(db_per_rel_err * rel)
    # 由 相对误差(百分数) ≈ 1721·dl² 反解：达到 target dB 所需 dl。
    # 🔴 1721 是**百分数**系数，分数形式为 17.21·dl²，此处必须用分数形式。
    def _dl_for(target_db: float) -> float:
        rel_t = target_db / db_per_rel_err
        if rel_t <= 0:
            return float("inf")
        return math.sqrt(rel_t / 17.21)
    return {
        "dl": float(dl),
        "beat_exact": float(d_exact), "beat_fdtd": float(d_fdtd),
        "relative_error": float(rel),
        "est_excess_error_db": float(est_db),
        "dl_for_0p03dB_um": float(_dl_for(0.03)),
        "dl_for_0p1dB_um": float(_dl_for(0.1)),
        "n_eff_0": float(neff[0]), "beta_tilde_0": float(bt[0]),
    }


def cross_check_with_eme(dl: float = 0.05, **kw) -> Dict[str, float]:
    """同一离散结构下 FDTD 与 EME 的对账（返回两者之差）。"""
    from mmi_eme import mmi_excess_loss          # 延迟导入，避免循环依赖
    f = mmi_excess_loss_fdtd(dl=dl, **kw)
    e = mmi_excess_loss(dl=dl, **{k: v for k, v in kw.items()
                                  if k in ("L_mmi", "W_mmi", "w_um", "out_gap",
                                           "n_core", "n_clad", "wl_um")})
    return {
        "fdtd_db": float(f["value"]), "eme_db": float(e["value"]),
        "delta_db": float(abs(f["value"] - e["value"])),
        "fdtd_T": float(f["T"]), "eme_T": float(e["T"]),
        "dl": dl,
    }


if __name__ == "__main__":
    import json
    print("== 控制实验 C1：直波导保幅 ==")
    print(json.dumps(straight_waveguide_conservation(dl=0.05), indent=2))
    print("== MMI 1×2 过量损耗（FDTD vs EME 对账）==")
    print(json.dumps(cross_check_with_eme(dl=0.05), indent=2))
