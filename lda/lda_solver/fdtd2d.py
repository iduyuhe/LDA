"""LDA · L3 自研 2D FDTD 求解核（TEz 模式）— C 级自主，机器优先接口。

与 fdtd1d 同族：零外部依赖（仅 numpy / math）、梯度海绵吸收边界、参考跑归一化
绝对标度。升维到 2D（Yee 网格：Ez / Hx / Hy），验证锚沿用 tmm.py 物理定律锚——
通过"二维问题在 y 方向平移不变时退化为一维"的极限做交叉校验，再加点源柱面波
|Ez|·√r 常数作为真·二维校验（同时验证四向海绵无回反射）。

三铁律（1D 已验证，2D 沿用）：
  1. 软源须全程开启：ramp 渐入后恒 1.0 到 nsteps 结束，绝不在 DFT 测量窗口前关闭。
  2. 固定网格 + 最薄有限层整数吸附：整谱同一 dl，使几何不随 λ 漂移。
  3. 透射定标用"无结构参考跑归一化" T=(nL/n0)·|E_real/E_ref|²，共模误差在比值中抵消。

机器优先：solve_spectrum(spec) 与 fdtd1d / tmm 同签名，便于 ORACLE 直接比对。
"""
from __future__ import annotations

import math

import numpy as np


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------
def _build_interior(layers, dl, buf):
    """构造沿 x 的内层折射率剖面（不含两端海绵）。

    返回 (prof, n0, nL)：prof 长度 = Nint = buf + Σ有限层 + buf；
    左 buf 格为 n0（入射均匀区），右 buf 格为 nL（出射均匀区）。
    """
    n0 = float(layers[0][1])
    nL = float(layers[-1][1])
    finite = [(th, n) for th, n in layers[1:-1] if not math.isinf(th)]
    prof = [n0] * buf
    for th, n in finite:
        nc = max(1, int(round(th / dl)))
        prof += [n] * nc
    prof += [nL] * buf
    return prof, n0, nL


def _sponge_1d(n, sponge, sig_max):
    """一维二次型海绵 sigma 剖面（内边缘 0 → 外边缘 sig_max）。"""
    s = np.zeros(n, dtype=float)
    if sponge < 1 or n < 2:
        return s
    xs = np.arange(sponge)
    left = sig_max * ((sponge - 1 - xs) / (sponge - 1)) ** 2
    right = sig_max * (xs / (sponge - 1)) ** 2
    s[:sponge] = left
    s[-sponge:] = right
    return s


def _grid_constants(wl, dl_factor, courant):
    """返回 (dl, dt, omega, k0)。2D CFL 上限 dt = dl·courant/√2（c=1）。"""
    dl = wl / dl_factor
    c = 1.0
    dt = dl * courant / math.sqrt(2.0)
    omega = 2.0 * math.pi / wl
    k0 = omega / c
    return dl, dt, omega, k0


# ---------------------------------------------------------------------------
# 平面波（分层膜）求解 —— 退化为一维时由 tmm.py 校验
# ---------------------------------------------------------------------------
def _run_planewave(layers, wl, angle=0.0, dl_factor=40.0, courant=0.95,
                   ramp=400, sponge=200, target_exp=12.0, ny=8, pbc_y=True,
                   debug=False):
    n0 = float(layers[0][1])
    nL = float(layers[-1][1])
    finite = [(th, n) for th, n in layers[1:-1] if not math.isinf(th)]

    # 固定网格（最薄有限层整数吸附）
    if finite:
        th_min = min(th for th, n in finite)
        base_dl = wl / dl_factor
        k = max(2, int(round(th_min / base_dl)))
        dl = th_min / k
    else:
        dl = wl / dl_factor
    dl, dt, omega, k0 = _grid_constants(wl, dl_factor, courant)
    # 缓冲区按物理尺寸（3µm）换算为格数，使源/监视器间距与分辨率无关
    buf = max(20, int(round(3.0 / dl)))
    ky = k0 * math.sin(angle)

    prof, _, _ = _build_interior(layers, dl, buf)
    Nint = len(prof)
    Nx = Nint + 2 * sponge
    Ny = ny

    eps2d = np.empty((Nx, Ny), dtype=float)
    eps2d[:sponge] = n0 ** 2
    prof2 = np.outer(np.array(prof, dtype=float) ** 2, np.ones(Ny))
    eps2d[sponge:sponge + Nint, :] = prof2
    eps2d[sponge + Nint:, :] = nL ** 2

    # 海绵：分层膜（一维退化）用例启用 y 方向 PBC —— 让 y 导数恒 0、
    # Hx 恒 0，恢复纯一维传播；此时仅需 x 方向海绵。点源用例（pbc_y=False）
    # 用四向海绵（Ny 需足够大）。
    sig_max = target_exp * 3.0 * (n0 ** 2) / (dt * sponge)
    sx = _sponge_1d(Nx, sponge, sig_max)
    if pbc_y:
        sigma = np.outer(sx, np.ones(Ny))          # 仅 x 方向海绵
    else:
        sy = _sponge_1d(Ny, sponge, sig_max)
        sigma = np.outer(sx, np.ones(Ny)) + np.outer(np.ones(Nx), sy)
    sigma = np.minimum(sigma, sig_max)

    dampE = 1.0 / (1.0 + dt * sigma / eps2d)
    if pbc_y:
        # Hx 边在 y 方向环绕：sigma 仅 x 相关 → sigHx = sigma（全）
        sigHx = sigma
        # Hy 边在 x 方向（无环绕）：0.5*(sigma[i]+sigma[i+1])，外边缘取 sigma
        edges = 0.5 * (sx[:-1] + sx[1:])
        edges = np.append(edges, sx[-1])
        sigHy = np.outer(edges, np.ones(Ny))
    else:
        sigHx = 0.5 * (sigma[:, :-1] + sigma[:, 1:])
        sigHy = 0.5 * (sigma[:-1, :] + sigma[1:, :])
        sigHx = np.pad(sigHx, ((0, 0), (0, 1)), mode='edge')
        sigHy = np.pad(sigHy, ((0, 1), (0, 0)), mode='edge')
    dampHx = 1.0 / (1.0 + dt * sigHx)
    dampHy = 1.0 / (1.0 + dt * sigHy)

    i_src = sponge + 20
    i_mon = sponge + Nint - buf // 2
    jc = Ny // 2

    period_steps = int(round(2.0 * math.pi / (omega * dt)))
    transient = max(ramp + 5 * period_steps, 4000)
    M = 140 * period_steps
    nsteps = transient + M
    meas0 = transient
    nmeas = M

    Ez = np.zeros((Nx, Ny))
    Hx = np.zeros((Nx, Ny))
    Hy = np.zeros((Nx, Ny))
    yj = np.arange(Ny) * dl

    re = 0.0
    im = 0.0
    for n in range(nsteps):
        t = n * dt
        if pbc_y:
            # H 更新（半步），y 方向环绕
            dEzdy = np.roll(Ez, -1, axis=1) - Ez
            Hx -= (dt / dl) * dEzdy
            dEzdx = Ez[1:, :] - Ez[:-1, :]
            Hy[:-1, :] += (dt / dl) * dEzdx
            Hx *= dampHx
            Hy *= dampHy
            # E 更新（全步，x 内部、y 全周期）
            dHydx = Hy[1:, :] - Hy[:-1, :]
            dHxdy = np.roll(Hx, -1, axis=1) - Hx
            Ez[1:Nx - 1, :] += (dt / dl) / eps2d[1:Nx - 1, :] * (
                dHydx[0:Nx - 2, :] - dHxdy[1:Nx - 1, :])
        else:
            dEzdy = Ez[:, 1:] - Ez[:, :-1]
            Hx[:, :Ny - 1] -= (dt / dl) * dEzdy
            dEzdx = Ez[1:, :] - Ez[:-1, :]
            Hy[:-1, :] += (dt / dl) * dEzdx
            Hx *= dampHx
            Hy *= dampHy
            dHydx = Hy[1:, :] - Hy[:-1, :]
            dHxdy = Hx[:, 1:] - Hx[:, :-1]
            Ez[1:Nx - 1, 1:Ny - 1] += (dt / dl) / eps2d[1:Nx - 1, 1:Ny - 1] * (
                dHydx[0:Nx - 2, 1:Ny - 1] - dHxdy[1:Nx - 1, 0:Ny - 2])
        # 软源（全程开：ramp 渐入后恒 1.0）
        env = 1.0 if n >= ramp else (n / ramp)
        if env > 0.0:
            Ez[i_src, :] += env * np.cos(omega * t - ky * yj)
        # DFT 累积（测量窗口）
        if n >= meas0:
            v = Ez[i_mon, jc]
            re += v * math.cos(omega * t)
            im -= v * math.sin(omega * t)

    amp = (re + 1j * im) * (2.0 / nmeas)
    if debug:
        return amp, np.max(np.abs(Ez), axis=1)
    return amp


def solve_spectrum(spec, dl_factor=80.0, courant=0.95, ramp=400, sponge=200,
                   target_exp=12.0, ny=8, angle=0.0):
    """与 fdtd1d / tmm 同签名的 2D 透射谱（参考跑归一化绝对标度）。

    对每一波长：真实结构 + 几何全同但所有层替换为 n0 的"无结构参考跑"，
    T=(nL/n0)·|E_real/E_ref|²。angle=0 时退化为一维（由 tmm 校验）。
    """
    layers = spec["layers"]
    wls = spec["wavelengths_um"]
    n0 = float(layers[0][1])
    nL = float(layers[-1][1])
    Ts = []
    for wl in wls:
        E_real = _run_planewave(layers, wl, angle, dl_factor, courant,
                                ramp, sponge, target_exp, ny, pbc_y=(angle == 0.0))
        ref_layers = [(th, n0) for th, n in layers]
        E_ref = _run_planewave(ref_layers, wl, angle, dl_factor, courant,
                               ramp, sponge, target_exp, ny, pbc_y=(angle == 0.0))
        if abs(E_ref) > 1e-12:
            T = (nL / n0) * abs(E_real / E_ref) ** 2
        else:
            T = 0.0
        Ts.append(float(T))
    return {
        "wavelengths_um": list(wls),
        "transmission": Ts,
        "source": "fdtd2d-sovereign",
        "note": "2D FDTD (TEz) 自研核，参考跑归一化绝对标度",
    }


# ---------------------------------------------------------------------------
# 点源柱面波（真·二维校验 + 四向海绵无回反射）
# ---------------------------------------------------------------------------
def run_greens_test(wl=2.0, n=1.0, N=320, sponge=60, dl_factor=40.0,
                    courant=0.95, ramp=400, target_exp=12.0, radii=None):
    """均匀介质中点源激发的 2D 柱面波；返回 [(r, |Ez_dft|·√r), ...]。

    真·二维判据：远场 |Ez| ∝ 1/√r（Hankel H0^(2) 渐近），故 |Ez|·√r 应为常数；
    若四向海绵回反射，则近海绵处该乘积会偏离常数。

    探针位置按"内部非海绵区半径"的比例布置，确保任何 N/海绵参数下都落在
    有效吸收层之外；DFT 窗口取 40 个周期（频率已知，足够抑制频谱泄漏）。
    """
    dl, dt, omega, _ = _grid_constants(wl, dl_factor, courant)
    Nx = Ny = N
    eps2d = np.full((Nx, Ny), n ** 2, dtype=float)

    sig_max = target_exp * 3.0 * (n ** 2) / (dt * sponge)
    sx = _sponge_1d(Nx, sponge, sig_max)
    sy = _sponge_1d(Ny, sponge, sig_max)
    sigma = np.outer(sx, np.ones(Ny)) + np.outer(np.ones(Nx), sy)
    sigma = np.minimum(sigma, sig_max)

    dampE = 1.0 / (1.0 + dt * sigma / eps2d)
    sigHx = 0.5 * (sigma[:, :-1] + sigma[:, 1:])
    sigHy = 0.5 * (sigma[:-1, :] + sigma[1:, :])
    dampHx = np.ones((Nx, Ny)); dampHx[:, :Ny - 1] = 1.0 / (1.0 + dt * sigHx)
    dampHy = np.ones((Nx, Ny)); dampHy[:Nx - 1, :] = 1.0 / (1.0 + dt * sigHy)

    ci = cj = N // 2
    if radii is None:
        # 按内部非海绵区半径的比例取探针（始终落在吸收层之外）
        R = (N - 2 * sponge) // 2
        radii = [int(round(f * R)) for f in (0.45, 0.6, 0.75, 0.9)]
    probes = [(ci + r, cj) for r in radii]

    period_steps = int(round(2.0 * math.pi / (omega * dt)))
    transient = max(ramp + 5 * period_steps, 4000)
    M = 40 * period_steps
    nsteps = transient + M
    meas0 = transient

    Ez = np.zeros((Nx, Ny))
    Hx = np.zeros((Nx, Ny))
    Hy = np.zeros((Nx, Ny))
    re = [0.0] * len(probes)
    im = [0.0] * len(probes)

    for n in range(nsteps):
        t = n * dt
        dEzdy = Ez[:, 1:] - Ez[:, :-1]
        Hx[:, :Ny - 1] -= (dt / dl) * dEzdy
        dEzdx = Ez[1:, :] - Ez[:-1, :]
        Hy[:-1, :] += (dt / dl) * dEzdx
        Hx *= dampHx
        Hy *= dampHy
        dHydx = Hy[1:, :] - Hy[:-1, :]
        dHxdy = Hx[:, 1:] - Hx[:, :-1]
        Ez[1:Nx - 1, 1:Ny - 1] += (dt / dl) / eps2d[1:Nx - 1, 1:Ny - 1] * (
            dHydx[0:Nx - 2, 1:Ny - 1] - dHxdy[1:Nx - 1, 0:Ny - 2])
        env = 1.0 if n >= ramp else (n / ramp)
        if env > 0.0:
            Ez[ci, cj] += env * math.cos(omega * t)
        if n >= meas0:
            for p, (pi, pj) in enumerate(probes):
                v = Ez[pi, pj]
                re[p] += v * math.cos(omega * t)
                im[p] -= v * math.sin(omega * t)

    amps = []
    for p, r in enumerate(radii):
        a = (re[p] + 1j * im[p]) * (2.0 / M)
        amps.append((r, abs(a) * math.sqrt(r)))
    return amps


if __name__ == "__main__":
    # 快速自检：匹配介质应 ≈ 1.0
    spec = {"layers": [(float('inf'), 1.44), (float('inf'), 1.44)],
            "wavelengths_um": [1.5]}
    print(solve_spectrum(spec))
