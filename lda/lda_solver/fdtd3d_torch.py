"""LDA · L3 自研 3D FDTD 求解核 —— PyTorch 可切换 GPU/CPU 后端（C 级自主）。

设计目标：与 `fdtd3d.py`（纯 numpy  sovereign 核）**逐位等价**的物理，
但用张量化（切片式 curl）替代 Python 内循环，可在 GPU 上大规模并行。
`device` 参数：'cuda'（默认，若可用）或 'cpu' —— 一行切换，无需改算法。

几何构造复用 numpy 参考实现的底层函数（_build_interior / _sponge_1d /
_grid_constants / _avg_sigma），保证折射率剖面、海绵、damp 系数与参考
实现完全一致；仅"每步六分量更新 + 软源 + DFT 累积"改为 PyTorch 张量算子。

验证锚沿用：tmm.py 一维退化（y/z-PBC）+ 点源球面波 |Ez|·r 常数。
"""

from __future__ import annotations

import math

import numpy as np
import torch

import fdtd3d as base  # numpy sovereign 参考实现（几何构造源）


# ---------------------------------------------------------------------------
# 张量化差分算子（与 base._fwd / _bwd / _avg_sigma 逐位对应）
# ---------------------------------------------------------------------------
def _fwd_t(f, axis, pbc):
    """前向差分 f[i+1]-f[i]。pbc 用 roll 环绕；非 pbc 末层差分为 0。"""
    if pbc:
        return torch.roll(f, -1, dims=axis) - f
    ndim = f.dim()
    out = torch.zeros_like(f)
    sl = [slice(None)] * ndim
    sl[axis] = slice(0, -1)
    sl_next = [slice(None)] * ndim
    sl_next[axis] = slice(1, None)
    out[tuple(sl)] = f[tuple(sl_next)] - f[tuple(sl)]
    return out


def _bwd_t(f, axis, pbc):
    """后向差分 f[i]-f[i-1]。pbc 用 roll 环绕；非 pbc 首层差分为 0。"""
    if pbc:
        return f - torch.roll(f, 1, dims=axis)
    ndim = f.dim()
    out = torch.zeros_like(f)
    sl = [slice(None)] * ndim
    sl[axis] = slice(1, None)
    sl_prev = [slice(None)] * ndim
    sl_prev[axis] = slice(None, -1)
    out[tuple(sl)] = f[tuple(sl)] - f[tuple(sl_prev)]
    return out


def _avg_sigma_t(sigma, axis, pbc):
    """H 节点 sigma：取偏移轴两侧均值；非 pbc 首层取边缘值。"""
    if pbc:
        return 0.5 * (sigma + torch.roll(sigma, 1, dims=axis))
    ndim = sigma.dim()
    out = torch.zeros_like(sigma)
    sl = [slice(None)] * ndim
    sl[axis] = slice(1, None)
    sl_prev = [slice(None)] * ndim
    sl_prev[axis] = slice(None, -1)
    out[tuple(sl)] = 0.5 * (sigma[tuple(sl)] + sigma[tuple(sl_prev)])
    sl0 = [slice(None)] * ndim
    sl0[axis] = 0
    out[tuple(sl0)] = sigma[tuple(sl0)]
    return out


# ---------------------------------------------------------------------------
# 几何构造（复用 numpy 参考实现的底层函数，保证完全一致）
# ---------------------------------------------------------------------------
def _build_geometry_planewave(layers, wl, dl_factor, courant, sponge,
                              target_exp, ny, nz, pbc_yz):
    """返回 (eps, sigma, dampE, dampHx, dampHy, dampHz, dl, dt, omega,
    n0, nL, buf, Nint, Nx, Ny, Nz) 的 numpy 数组（随后转 torch）。"""
    n0 = float(layers[0][1])
    nL = float(layers[-1][1])
    dl, dt, omega, _ = base._grid_constants(wl, dl_factor, courant)
    buf = max(20, int(round(3.0 / dl)))
    prof, _, _ = base._build_interior(layers, dl, buf)
    Nint = len(prof)
    Nx = Nint + 2 * sponge
    Ny = ny
    Nz = nz
    eps = np.empty((Nx, Ny, Nz), dtype=float)
    eps[:sponge] = n0 ** 2
    prof_arr = np.array(prof, dtype=float) ** 2
    eps[sponge:sponge + Nint, :, :] = prof_arr[:, None, None]
    eps[sponge + Nint:, :, :] = nL ** 2

    sig_max = target_exp * 3.0 * (n0 ** 2) / (dt * sponge)
    sx = base._sponge_1d(Nx, sponge, sig_max)
    if pbc_yz:
        sigma = np.outer(sx, np.ones(Ny * Nz)).reshape(Nx, Ny, Nz)
    else:
        sy = base._sponge_1d(Ny, sponge, sig_max)
        sz = base._sponge_1d(Nz, sponge, sig_max)
        sigma = (np.outer(sx, np.ones(Ny * Nz)).reshape(Nx, Ny, Nz)
                 + np.outer(np.ones(Nx), np.outer(sy, np.ones(Nz))).reshape(Nx, Ny, Nz)
                 + np.outer(np.ones(Nx * Ny), sz).reshape(Nx, Ny, Nz))
    sigma = np.minimum(sigma, sig_max)

    dampE = 1.0 / (1.0 + dt * sigma / eps)
    dampHx = 1.0 / (1.0 + 0.5 * dt * (base._avg_sigma(sigma, 1, pbc_yz) + base._avg_sigma(sigma, 2, pbc_yz)))
    dampHy = 1.0 / (1.0 + 0.5 * dt * (base._avg_sigma(sigma, 0, False) + base._avg_sigma(sigma, 2, pbc_yz)))
    dampHz = 1.0 / (1.0 + 0.5 * dt * (base._avg_sigma(sigma, 0, False) + base._avg_sigma(sigma, 1, pbc_yz)))
    return eps, sigma, dampE, dampHx, dampHy, dampHz, dl, dt, omega, n0, nL, buf, Nint, Nx, Ny, Nz


def _build_geometry_greens(n, wl, N, sponge, dl_factor, courant, target_exp):
    """均匀介质点源球面波几何（全非 PBC，六向海绵）。"""
    dl, dt, omega, _ = base._grid_constants(wl, dl_factor, courant)
    Nx = Ny = Nz = N
    eps = np.full((Nx, Ny, Nz), n ** 2, dtype=float)
    sig_max = target_exp * 3.0 * (n ** 2) / (dt * sponge)
    sx = base._sponge_1d(Nx, sponge, sig_max)
    sy = base._sponge_1d(Ny, sponge, sig_max)
    sz = base._sponge_1d(Nz, sponge, sig_max)
    sigma = (np.outer(sx, np.ones(Ny * Nz)).reshape(Nx, Ny, Nz)
             + np.outer(np.ones(Nx), np.outer(sy, np.ones(Nz))).reshape(Nx, Ny, Nz)
             + np.outer(np.ones(Nx * Ny), sz).reshape(Nx, Ny, Nz))
    sigma = np.minimum(sigma, sig_max)
    dampE = 1.0 / (1.0 + dt * sigma / eps)
    dampHx = 1.0 / (1.0 + 0.5 * dt * (base._avg_sigma(sigma, 1, False) + base._avg_sigma(sigma, 2, False)))
    dampHy = 1.0 / (1.0 + 0.5 * dt * (base._avg_sigma(sigma, 0, False) + base._avg_sigma(sigma, 2, False)))
    dampHz = 1.0 / (1.0 + 0.5 * dt * (base._avg_sigma(sigma, 0, False) + base._avg_sigma(sigma, 1, False)))
    return eps, sigma, dampE, dampHx, dampHy, dampHz, dl, dt, omega


# ---------------------------------------------------------------------------
# 核心步进（张量化，零 Python 网格内循环）
# ---------------------------------------------------------------------------
def _fdtd3d_core(eps_t, dampE_t, dampHx_t, dampHy_t, dampHz_t,
                 dl, dt, omega, ramp, nsteps, transient,
                 i_src, src_j, src_k, src_is_plane,
                 probes, nmeas, device, pbc_y, pbc_z):
    Nx, Ny, Nz = eps_t.shape
    Ex = torch.zeros((Nx, Ny, Nz), device=device, dtype=torch.float64)
    Ey = torch.zeros((Nx, Ny, Nz), device=device, dtype=torch.float64)
    Ez = torch.zeros((Nx, Ny, Nz), device=device, dtype=torch.float64)
    Hx = torch.zeros((Nx, Ny, Nz), device=device, dtype=torch.float64)
    Hy = torch.zeros((Nx, Ny, Nz), device=device, dtype=torch.float64)
    Hz = torch.zeros((Nx, Ny, Nz), device=device, dtype=torch.float64)

    cH = dt / dl
    cE = cH  # 实际 E 更新再除以 eps（张量）
    nprobe = len(probes)
    re_t = torch.zeros(nprobe, device=device, dtype=torch.float64)
    im_t = torch.zeros(nprobe, device=device, dtype=torch.float64)
    probes_i = [p[0] for p in probes]
    probes_j = [p[1] for p in probes]
    probes_k = [p[2] for p in probes]

    for n in range(nsteps):
        t = n * dt
        # ---- H 更新（半步）----
        Hx = (Hx - cH * (_fwd_t(Ez, 1, pbc_y) - _fwd_t(Ey, 2, pbc_z))) * dampHx_t
        Hy = (Hy - cH * (_fwd_t(Ex, 2, pbc_z) - _fwd_t(Ez, 0, False))) * dampHy_t
        Hz = (Hz - cH * (_fwd_t(Ey, 0, False) - _fwd_t(Ex, 1, pbc_y))) * dampHz_t
        # ---- E 更新（全步）----
        Ex = (Ex + (cE / eps_t) * (_bwd_t(Hz, 1, pbc_y) - _bwd_t(Hy, 2, pbc_z))) * dampE_t
        Ey = (Ey + (cE / eps_t) * (_bwd_t(Hx, 2, pbc_z) - _bwd_t(Hz, 0, False))) * dampE_t
        Ez = (Ez + (cE / eps_t) * (_bwd_t(Hy, 0, False) - _bwd_t(Hx, 1, pbc_y))) * dampE_t
        # ---- 软源（全程开：ramp 渐入后恒 1.0）----
        env = 1.0 if n >= ramp else (n / ramp)
        if env > 0.0:
            src = env * math.cos(omega * t)
            if src_is_plane:
                Ez[i_src, :, :] = Ez[i_src, :, :] + src
            else:
                Ez[i_src, src_j, src_k] = Ez[i_src, src_j, src_k] + src
        # ---- DFT 累积（测量窗口，GPU 上累积后末次回传）----
        if n >= transient:
            wt = omega * t
            cw = math.cos(wt)
            sw = math.sin(wt)
            for p in range(nprobe):
                v = Ez[probes_i[p], probes_j[p], probes_k[p]]
                re_t[p] = re_t[p] + v * cw
                im_t[p] = im_t[p] - v * sw

    return (re_t + 1j * im_t) * (2.0 / nmeas)


def _to_device(arr, device):
    return torch.from_numpy(np.ascontiguousarray(arr)).to(device=device, dtype=torch.float64)


# ---------------------------------------------------------------------------
# 平面波（分层膜）求解 —— 退化为一维时由 tmm.py 校验
# ---------------------------------------------------------------------------
def _run_planewave_torch(layers, wl, device, dl_factor=80.0, courant=0.95,
                         ramp=400, sponge=320, target_exp=12.0, ny=2, nz=2,
                         pbc_yz=True, debug=False):
    (eps, sigma, dampE, dampHx, dampHy, dampHz, dl, dt, omega, n0, nL, buf,
     Nint, Nx, Ny, Nz) = _build_geometry_planewave(
        layers, wl, dl_factor, courant, sponge, target_exp, ny, nz, pbc_yz)

    eps_t = _to_device(eps, device)
    dampE_t = _to_device(dampE, device)
    dampHx_t = _to_device(dampHx, device)
    dampHy_t = _to_device(dampHy, device)
    dampHz_t = _to_device(dampHz, device)

    i_src = sponge + 20
    i_mon = sponge + Nint - buf // 2
    jc = Ny // 2
    kc = Nz // 2

    period_steps = int(round(2.0 * math.pi / (omega * dt)))
    transient = max(ramp + 5 * period_steps, 4000)
    M = 80 * period_steps
    nsteps = transient + M

    with torch.no_grad():  # FDTD 无需 autograd；关闭后避免每步建图（GPU/CPU 均大幅加速）
        amp = _fdtd3d_core(eps_t, dampE_t, dampHx_t, dampHy_t, dampHz_t,
                           dl, dt, omega, ramp, nsteps, transient,
                           i_src, 0, 0, True, [(i_mon, jc, kc)], M,
                           device, pbc_yz, pbc_yz)
    amp = amp[0].item()  # 已是 Python complex
    if debug:
        return amp, None
    return amp


def solve_spectrum_torch(spec, device=None, dl_factor=80.0, courant=0.95,
                         ramp=400, sponge=320, target_exp=12.0, ny=2, nz=2,
                         angle=0.0):
    """与 fdtd3d.solve_spectrum 同签名；device=None 自动选 cuda（若可用）否则 cpu。"""
    if device is None:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    layers = spec["layers"]
    wls = spec["wavelengths_um"]
    n0 = float(layers[0][1])
    nL = float(layers[-1][1])
    pbc_yz = (angle == 0.0)
    Ts = []
    for wl in wls:
        E_real = _run_planewave_torch(layers, wl, device, dl_factor, courant,
                                      ramp, sponge, target_exp, ny, nz, pbc_yz)
        ref_layers = [(th, n0) for th, n in layers]
        E_ref = _run_planewave_torch(ref_layers, wl, device, dl_factor, courant,
                                     ramp, sponge, target_exp, ny, nz, pbc_yz)
        if abs(E_ref) > 1e-12:
            T = (nL / n0) * abs(E_real / E_ref) ** 2
        else:
            T = 0.0
        Ts.append(float(T))
    return {
        "wavelengths_um": list(wls),
        "transmission": Ts,
        "source": "fdtd3d-torch-" + device,
        "note": "3D FDTD (全 Yee) PyTorch %s 后端，参考跑归一化绝对标度" % device,
    }


# ---------------------------------------------------------------------------
# 点源球面波（真·三维校验 + 六向海绵无回反射）
# ---------------------------------------------------------------------------
def run_greens_test_torch(wl=2.0, n=1.0, N=120, sponge=28, dl_factor=20.0,
                          courant=0.95, ramp=400, target_exp=12.0,
                          radii=None, device=None):
    """与 fdtd3d.run_greens_test 同签名；返回 [(r, |Ez_dft|·r), ...]。"""
    if device is None:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    (eps, sigma, dampE, dampHx, dampHy, dampHz, dl, dt, omega) = \
        _build_geometry_greens(n, wl, N, sponge, dl_factor, courant, target_exp)

    eps_t = _to_device(eps, device)
    dampE_t = _to_device(dampE, device)
    dampHx_t = _to_device(dampHx, device)
    dampHy_t = _to_device(dampHy, device)
    dampHz_t = _to_device(dampHz, device)

    ci = cj = ck = N // 2
    if radii is None:
        R = (N - 2 * sponge) // 2
        radii = [int(round(f * R)) for f in (0.65, 0.8, 0.9)]
    probes = [(ci + r, cj, ck) for r in radii]

    period_steps = int(round(2.0 * math.pi / (omega * dt)))
    transient = max(ramp + 5 * period_steps, 4000)
    M = 40 * period_steps
    nsteps = transient + M

    with torch.no_grad():  # FDTD 无需 autograd；关闭后避免每步建图（GPU/CPU 均大幅加速）
        amps_t = _fdtd3d_core(eps_t, dampE_t, dampHx_t, dampHy_t, dampHz_t,
                              dl, dt, omega, ramp, nsteps, transient,
                              ci, cj, ck, False, probes, M,
                              device, False, False)
    amps = []
    for p, r in enumerate(radii):
        a = amps_t[p].item()  # 已是 Python complex
        amps.append((r, abs(a) * r))
    return amps


if __name__ == "__main__":
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    print("device =", dev)
    spec = {"layers": [(float('inf'), 1.44), (float('inf'), 1.44)],
            "wavelengths_um": [1.5]}
    print("matched T =", solve_spectrum_torch(spec, device=dev))
