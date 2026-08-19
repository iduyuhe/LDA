"""LDA · 真 2D 矩形波导 FDTD 本征模求解器（矢量 3D 全 Yee，z 传播）。

复用 fdtd3d.py 已验证的矢量 Yee propagator（selfcheck 5/5），把传播方向改为 z、
源改为 Ey 基模剖面（TE 极化）、监视器改为 z 向双平面 DFT 相位差，求基模 neff。
与 oracle_mode.fdfd_neff（标量亥姆霍兹本征模 ORACLE）交叉校验，构成真 2D 器件验收闭环。

为什么不用标量单分量波动：真 2D（x,y 双向约束）波导中，单一 Ey 分量随 y 变化会
违反无源区 ∇·E=0，标量波动方程不自洽 → 数值失真（前期标量版 neff 偏差 16~55%）。
矢量 3D 全 Yee（六分量）对真 2D 数学自洽（∇·D=0 自动满足），是正确模型。

FDFD ORACLE 为标量近似（纵向 Ez 亥姆霍兹），矢量效应使其与精确 FDTD 差几个百分点，
交叉校验公差据此设定（约 3~5%）。
"""
from __future__ import annotations

import math
import numpy as np

try:
    from fdtd3d import (_fwd, _bwd, _sponge_1d, _avg_sigma, _grid_constants)
except ModuleNotFoundError:  # 直接以脚本运行时补路径
    import os as _os
    import sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from fdtd3d import (_fwd, _bwd, _sponge_1d, _avg_sigma, _grid_constants)


def solve_waveguide_neff_vec(eps3: np.ndarray, dl: float, wl_um: float, n_clad: float,
                             n_core: float = None, sponge_xy: int = 24, sponge_z: int = 40,
                             target_exp: float = 12.0, courant: float = 0.95,
                             dz_um: float = 0.6, ramp: int = 400, z1_frac: float = 0.45,
                             src_frac: float = 0.12,                              mode_profile: bool = False,
                             mode_source: np.ndarray = None, pbc_xy: bool = True,
                             debug: bool = False, capture_field: bool = False):
    """矢量 3D 全 Yee FDTD 求真 2D 矩形波导基模 neff（z 传播，双监视点相位差）。

    eps3 : (Nx,Ny,Nz) 折射率平方场（波导芯在 x,y 矩形截面，z 均匀 = 沿 z 传播）。
    dl   : 网格 µm；wl_um : 真空波长 µm；n_clad/n_core : 包/芯折射率。
    返回基模 neff；debug 时额外返回 (neff, beta, m, snr)。
    """
    eps3 = np.asarray(eps3, dtype=float)
    Nx, Ny, Nz = eps3.shape
    if n_core is None:
        n_core = float(np.sqrt(eps3.max()))

    c = 1.0
    omega = 2.0 * math.pi / wl_um
    k0 = omega / c
    dt = dl * courant / math.sqrt(3.0)           # 3D CFL 上限内（c=1）

    # ---- 六面导电海绵（x,y 截面方向短海绵；z 传播方向长海绵）----
    # 自适应：海绵必须远小于截面/传播维度，否则截面被吞没→场被全阻尼（前期 bug）。
    n0 = n_clad
    sponge_z = max(8, min(sponge_z, Nz // 4))
    sig_max_z = target_exp * 3.0 * (n0 ** 2) / (dt * sponge_z)
    sz = _sponge_1d(Nz, sponge_z, sig_max_z)
    if pbc_xy:
        sigma = sz[None, None, :].copy()
        sig_cap = sig_max_z
    else:
        sponge_xy = max(8, min(Nx, Ny) // 4)
        sig_max_xy = target_exp * 3.0 * (n0 ** 2) / (dt * sponge_xy)
        sx = _sponge_1d(Nx, sponge_xy, sig_max_xy)
        sy = _sponge_1d(Ny, sponge_xy, sig_max_xy)
        sig_cap = max(sig_max_xy, sig_max_z)
        sigma = (sx[:, None, None] + sy[None, :, None] + sz[None, None, :])
        np.clip(sigma, 0.0, sig_cap, out=sigma)
    dampE = 1.0 / (1.0 + dt * sigma / eps3)
    # H 节点偏置两轴均值（各 0.5），不可直接相加（会 2× 过阻尼）
    pbc_x = pbc_y = pbc_xy
    pbc_z = False
    dampHx = 1.0 / (1.0 + 0.5 * dt * (_avg_sigma(sigma, 1, pbc_y) + _avg_sigma(sigma, 2, pbc_z)))
    dampHy = 1.0 / (1.0 + 0.5 * dt * (_avg_sigma(sigma, 0, pbc_x) + _avg_sigma(sigma, 2, pbc_z)))
    dampHz = 1.0 / (1.0 + 0.5 * dt * (_avg_sigma(sigma, 0, pbc_x) + _avg_sigma(sigma, 1, pbc_y)))

    # ---- 源 / 监视器（相对 z 内层长度，避免落入两端海绵）----
    Nz_int = Nz - 2 * sponge_z
    cx, cy = Nx // 2, Ny // 2
    src_z = sponge_z + max(8, int(src_frac * Nz_int))
    neff_avg = 0.5 * (n_clad + n_core)
    lambda_z = wl_um / neff_avg
    dz_cells = max(4, int(round(0.40 * lambda_z / dl)))
    z1 = sponge_z + int(z1_frac * Nz_int)
    z2 = z1 + dz_cells
    if z2 >= sponge_z + Nz_int - 4:
        z2 = sponge_z + Nz_int - 4
        z1 = z2 - dz_cells

    # 软源横向剖面：2D 高斯（中心峰，宽度匹配芯区，主激发基模）
    core_mask = eps3[:, :, 0] > (n_clad ** 2 + n_core ** 2) / 2.0
    rows = np.where(core_mask.any(axis=1))[0]
    cols = np.where(core_mask.any(axis=0))[0]
    if rows.size > 1 and cols.size > 1:
        wx = max(2.0, (rows.max() - rows.min() + 1) / 2.0)
        wy = max(2.0, (cols.max() - cols.min() + 1) / 2.0)
    else:
        wx = wy = max(2.0, min(Nx, Ny) * 0.1)
    sgx = max(1, int(wx))
    sgy = max(1, int(wy))
    ax = (np.arange(Nx) - cx) / wx
    ay = (np.arange(Ny) - cy) / wy
    prof = np.exp(-(ax[:, None] ** 2 + ay[None, :] ** 2) / 2.0)

    # ---- DFT 窗 ----
    period_steps = int(round(2.0 * math.pi / (omega * dt)))
    transient = max(ramp + 5 * period_steps, 4000)
    M = 80 * period_steps
    nsteps = transient + M
    meas0 = transient

    # ---- 矢量 Yee 场 ----
    Ex = np.zeros((Nx, Ny, Nz))
    Ey = np.zeros_like(Ex)
    Ez = np.zeros_like(Ex)
    Hx = np.zeros_like(Ex)
    Hy = np.zeros_like(Ex)
    Hz = np.zeros_like(Ex)

    re1 = im1 = re2 = im2 = 0.0
    _samples = []
    for n in range(nsteps):
        t = n * dt
        # H 更新（半步）
        Hx -= (dt / dl) * (_fwd(Ez, 1, pbc_y) - _fwd(Ey, 2, pbc_z))
        Hy -= (dt / dl) * (_fwd(Ex, 2, pbc_z) - _fwd(Ez, 0, pbc_x))
        Hz -= (dt / dl) * (_fwd(Ey, 0, pbc_x) - _fwd(Ex, 1, pbc_y))
        Hx *= dampHx
        Hy *= dampHy
        Hz *= dampHz
        # E 更新（全步）
        Ex += (dt / (eps3 * dl)) * (_bwd(Hz, 1, pbc_y) - _bwd(Hy, 2, pbc_z))
        Ey += (dt / (eps3 * dl)) * (_bwd(Hx, 2, pbc_z) - _bwd(Hz, 0, pbc_x))
        Ez += (dt / (eps3 * dl)) * (_bwd(Hy, 0, pbc_x) - _bwd(Hx, 1, pbc_y))
        Ex *= dampE
        Ey *= dampE
        Ez *= dampE
        # 软源：Ey 横向极化、垂直 z 传播方向。
        #  mode_source(2D): 用 ORACLE(FDFD) 本征模剖面作模态注入（最干净，
        #    主激发基模、抑制辐射模；β 仍由 FDTD 独立传播测量）；
        #  mode_profile=True：乘 2D 高斯（匹配芯区）作模式匹配注入；
        #  else：全平面波（横向无调制，复用 fdtd3d 平面波范式，用于均匀介质诊断）。
        env = 1.0 if n >= ramp else n / ramp
        if env > 0.0:
            if mode_source is not None:
                Ey[:, :, src_z] += (env * mode_source * math.cos(omega * t))
            elif mode_profile:
                Ey[:, :, src_z] += (env * prof * math.cos(omega * t))
            else:
                Ey[:, :, src_z] += env * math.cos(omega * t)
        if n >= meas0:
            v1 = Ey[cx, cy, z1]
            v2 = Ey[cx, cy, z2]
            re1 += v1 * math.cos(omega * t)
            im1 -= v1 * math.sin(omega * t)
            re2 += v2 * math.cos(omega * t)
            im2 -= v2 * math.sin(omega * t)
            if debug and (n - meas0) % period_steps == 0:
                _samples.append((n, float(Ey[cx, cy, z1]), float(np.max(np.abs(Ey)))))

    amp1 = (re1 + 1j * im1) * (2.0 / M)
    amp2 = (re2 + 1j * im2) * (2.0 / M)
    a1 = np.angle(amp1)
    a2 = np.angle(amp2)
    dphi = (a1 - a2 + math.pi) % (2.0 * math.pi) - math.pi

    # 由物理区间唯一确定 2π 缠绕数 m
    dz = (z2 - z1) * dl
    m_low = math.ceil((n_clad * k0 * dz - dphi) / (2.0 * math.pi) - 1e-9)
    m_high = math.floor((n_core * k0 * dz - dphi) / (2.0 * math.pi) + 1e-9)
    if m_high < m_low:
        m = int(round(((n_clad + n_core) / 2.0 * k0 * dz - dphi) / (2.0 * math.pi)))
    else:
        m = m_low
    neff = (dphi + 2.0 * math.pi * m) / (k0 * dz)
    beta = neff * k0
    snr = min(abs(amp1), abs(amp2)) / (abs(amp1) + abs(amp2) + 1e-30)
    if not (n_clad * 1.001 < neff < n_core * 0.999):
        for mm in (m - 1, m + 1):
            cand = (dphi + 2.0 * math.pi * mm) / (k0 * dz)
            if n_clad * 1.001 < cand < n_core * 0.999:
                neff, m, beta = cand, mm, cand * k0
                break
    if debug:
        print(f"[diag] a1={a1:.4f} a2={a2:.4f} dphi={dphi:.4f} dz={dz:.4f} "
              f"|amp1|={abs(amp1):.4f} |amp2|={abs(amp2):.4f} m={m} "
              f"src_z={src_z} z1={z1} z2={z2} Nz_int={Nz_int}")
        if capture_field:
            return float(neff), float(beta), int(m), float(snr), Ey[:, :, z1].copy()
        return float(neff), float(beta), int(m), float(snr)
    if capture_field:
        return float(neff), Ey[:, :, z1].copy()
    return float(neff)


if __name__ == "__main__":
    w, h = 0.5, 0.22
    n_si, n_sio2, wl = 3.48, 1.44, 1.55
    import os as _os
    import sys as _sys
    _hdir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                          "..", "lda_harness")
    if _hdir not in _sys.path:
        _sys.path.insert(0, _hdir)
    from oracle_mode import fdfd_neff
    from fdtd3d_waveguide import build_waveguide_field_3d
    clad = 1.2
    dl = wl / 24.0
    oracle = fdfd_neff(w, h, n_si, n_sio2, wl, dl=dl, clad_um=clad)
    eps3, meta = build_waveguide_field_3d(w, h, n_si, n_sio2, wl,
                                          dl=dl, clad_um=clad, Lz_um=8.0)
    ne, beta, m, snr = solve_waveguide_neff_vec(
        eps3, meta["dl"], wl, n_clad=n_sio2, n_core=n_si, debug=True)
    rel = abs(ne - oracle) / oracle
    print(f"FDFD ORACLE neff = {oracle:.5f}")
    print(f"FDTD(vec)   neff = {ne:.5f}  (beta={beta:.4f}, m={m}, snr={snr:.3f})")
    print(f"|Δneff|         = {abs(ne - oracle):.5f}  (rel {rel:.3%})")
