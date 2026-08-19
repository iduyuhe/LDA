"""LDA · L2-B 性能升维 · 3D FDTD 的 Numba-CPU JIT 加速核（与 fdtd3d.py 物理完全一致）。

设计目标：把已验证的主权 3D 求解核（fdtd3d.py 纯 numpy 版）从"验证核"推向"生产级
性能核"的第一步。GPU 不在本机，但 Numba CPU 并行 JIT 这个切片完全在能力圈内、可立即
实测 speedup，并为后续 CUDA 后端验证逻辑与收益曲线。

物理一致性铁律（与 fdtd3d.py 逐字节等价）：
  - 3D CFL：dt = dl·courant/√3（c=1）。
  - 六分量 leapfrog：H 更新系数 dt/dl（无 ε）；E 更新系数 dt/(eps·dl)（缺 dl 即波阻抗错配）。
  - PBC 退化：仅 y/z 方向环绕（x 永不 PBC），用取模 % 替代 np.roll。
  - 梯度海绵：dampE/dampHx/Hy/Hz 预计算（时间恒定）；H 节点 σ 取两轴均值 ×0.5（不可相加）。
  - 软源全程开：ramp 渐入后恒 1.0，绝不早于 DFT 窗口关闭。
  - 参考跑归一化 T=(nL/n0)·|E_real/E_ref|²；ORACLE 同 fdtd3d.py（tmm 一维退化 + 球面波 |Ez|·r）。

并行安全：以 i（传播轴，最大维）做 prange。phase1 只写 H、phase2 只写 E，跨相位读的是
已写定的数组，无写-写/写-读竞争。

公开接口（与 fdtd3d.py 同签名，便于 1:1 替换跑 selfcheck）：
  solve_spectrum_numba(spec, ...)        → 透射谱
  run_greens_test_numba(wl=..., ...)     → 球面波 [(r, |Ez|·r), ...]
"""
from __future__ import annotations

import math

import numpy as np
from numba import njit, prange

from fdtd3d import (_avg_sigma, _build_interior, _grid_constants, _sponge_1d)


# ---------------------------------------------------------------------------
# Numba 融合更新核（六分量 leapfrog + 海绵阻尼 + 软源 + DFT 累积）
# ---------------------------------------------------------------------------
@njit(parallel=True, cache=True, fastmath=True)
def _fdtd3d_core(Ex, Ey, Ez, Hx, Hy, Hz,
                 eps, dampE, dampHx, dampHy, dampHz,
                 dl, dt, pbc_y, pbc_z,
                 i_src, src_j, src_k, src_is_plane, src_val,
                 probes, re, im, cos_wt, sin_wt, do_dft):
    Nx, Ny, Nz = Ex.shape
    cH = dt / dl

    # 非 PBC 边界约定必须与 fdtd3d.py 的 _fwd/_bwd 逐字节一致：
    #   _fwd（前向差分）：最后格返回 0（整段差分为 0），绝不返回 -f_here
    #   _bwd（后向差分）：最前格返回 0，绝不返回 +f_here
    # PBC 用取模环绕。x 轴永不 PBC。

    # ---- Phase 1: H 更新（读 E，写 H）----
    for i in prange(Nx):
        for j in range(Ny):
            for k in range(Nz):
                # 前向差分（沿 j / k / i）
                ez_fj = (Ez[i, (j + 1) % Ny, k] - Ez[i, j, k]) if pbc_y else (
                    Ez[i, j + 1, k] - Ez[i, j, k] if j + 1 < Ny else 0.0)
                ez_fk = (Ez[i, j, (k + 1) % Nz] - Ez[i, j, k]) if pbc_z else (
                    Ez[i, j, k + 1] - Ez[i, j, k] if k + 1 < Nz else 0.0)
                ez_fi = Ez[i + 1, j, k] - Ez[i, j, k] if i + 1 < Nx else 0.0
                ey_fk = (Ey[i, j, (k + 1) % Nz] - Ey[i, j, k]) if pbc_z else (
                    Ey[i, j, k + 1] - Ey[i, j, k] if k + 1 < Nz else 0.0)
                ey_fi = Ey[i + 1, j, k] - Ey[i, j, k] if i + 1 < Nx else 0.0
                ex_fk = (Ex[i, j, (k + 1) % Nz] - Ex[i, j, k]) if pbc_z else (
                    Ex[i, j, k + 1] - Ex[i, j, k] if k + 1 < Nz else 0.0)
                ex_fj = (Ex[i, (j + 1) % Ny, k] - Ex[i, j, k]) if pbc_y else (
                    Ex[i, j + 1, k] - Ex[i, j, k] if j + 1 < Ny else 0.0)

                # Hx -= cH*(dEz/dy - dEy/dz)
                curlx = ez_fj - ey_fk
                Hx[i, j, k] = (Hx[i, j, k] - cH * curlx) * dampHx[i, j, k]
                # Hy -= cH*(dEx/dz - dEz/dx)
                curly = ex_fk - ez_fi
                Hy[i, j, k] = (Hy[i, j, k] - cH * curly) * dampHy[i, j, k]
                # Hz -= cH*(dEy/dx - dEx/dy)
                curlz = ey_fi - ex_fj
                Hz[i, j, k] = (Hz[i, j, k] - cH * curlz) * dampHz[i, j, k]

    # ---- Phase 2: E 更新（读 H，写 E）----
    for i in prange(Nx):
        for j in range(Ny):
            for k in range(Nz):
                eijk = eps[i, j, k]
                cE = cH / eijk
                # 后向差分（沿 j / k / i）—— 必须为 f[i] - f[i-1]，边界首格为 0
                hz_bj = (Hz[i, j, k] - Hz[i, (j - 1) % Ny, k]) if pbc_y else (
                    Hz[i, j, k] - Hz[i, j - 1, k] if j - 1 >= 0 else 0.0)
                hz_bk = (Hz[i, j, k] - Hz[i, j, (k - 1) % Nz]) if pbc_z else (
                    Hz[i, j, k] - Hz[i, j, k - 1] if k - 1 >= 0 else 0.0)
                hz_bi = Hz[i, j, k] - Hz[i - 1, j, k] if i - 1 >= 0 else 0.0
                hy_bk = (Hy[i, j, k] - Hy[i, j, (k - 1) % Nz]) if pbc_z else (
                    Hy[i, j, k] - Hy[i, j, k - 1] if k - 1 >= 0 else 0.0)
                hy_bi = Hy[i, j, k] - Hy[i - 1, j, k] if i - 1 >= 0 else 0.0
                hx_bk = (Hx[i, j, k] - Hx[i, j, (k - 1) % Nz]) if pbc_z else (
                    Hx[i, j, k] - Hx[i, j, k - 1] if k - 1 >= 0 else 0.0)
                hx_bj = (Hx[i, j, k] - Hx[i, (j - 1) % Ny, k]) if pbc_y else (
                    Hx[i, j, k] - Hx[i, j - 1, k] if j - 1 >= 0 else 0.0)

                # Ex += cE*(dHz/dy - dHy/dz)
                curl_ex = hz_bj - hy_bk
                Ex[i, j, k] = (Ex[i, j, k] + cE * curl_ex) * dampE[i, j, k]
                # Ey += cE*(dHx/dz - dHz/dx)
                curl_ey = hx_bk - hz_bi
                Ey[i, j, k] = (Ey[i, j, k] + cE * curl_ey) * dampE[i, j, k]
                # Ez += cE*(dHy/dx - dHx/dy)
                curl_ez = hy_bi - hx_bj
                Ez[i, j, k] = (Ez[i, j, k] + cE * curl_ez) * dampE[i, j, k]

    # ---- 软源注入（E 更新之后、DFT 之前，与 fdtd3d.py 顺序一致）----
    if src_val != 0.0:
        if src_is_plane:
            for j in range(Ny):
                for k in range(Nz):
                    Ez[i_src, j, k] += src_val
        else:
            Ez[i_src, src_j, src_k] += src_val

    # ---- DFT 累积（测量窗口内）----
    if do_dft:
        for p in range(probes.shape[0]):
            pi = probes[p, 0]
            pj = probes[p, 1]
            pk = probes[p, 2]
            v = Ez[pi, pj, pk]
            re[p] += v * cos_wt
            im[p] -= v * sin_wt


# ---------------------------------------------------------------------------
# 平面波（分层膜）求解 —— 与 _run_planewave 物理逐字节一致
# ---------------------------------------------------------------------------
def run_planewave_numba(layers, wl, dl_factor=80.0, courant=0.95, ramp=400,
                        sponge=320, target_exp=12.0, ny=2, nz=2, pbc_yz=True,
                        debug=False):
    n0 = float(layers[0][1])
    nL = float(layers[-1][1])
    finite = [(th, n) for th, n in layers[1:-1] if not math.isinf(th)]

    if finite:
        th_min = min(th for th, n in finite)
        base_dl = wl / dl_factor
        k = max(2, int(round(th_min / base_dl)))
        dl = th_min / k
    else:
        dl = wl / dl_factor
    dl, dt, omega, k0 = _grid_constants(wl, dl_factor, courant)
    buf = max(20, int(round(3.0 / dl)))

    prof, _, _ = _build_interior(layers, dl, buf)
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
    sx = _sponge_1d(Nx, sponge, sig_max)
    if pbc_yz:
        sigma = np.outer(sx, np.ones(Ny * Nz)).reshape(Nx, Ny, Nz)
    else:
        sy = _sponge_1d(Ny, sponge, sig_max)
        sz = _sponge_1d(Nz, sponge, sig_max)
        sigma = (np.outer(sx, np.ones(Ny * Nz)).reshape(Nx, Ny, Nz)
                 + np.outer(np.ones(Nx), np.outer(sy, np.ones(Nz))).reshape(Nx, Ny, Nz)
                 + np.outer(np.ones(Nx * Ny), sz).reshape(Nx, Ny, Nz))
    sigma = np.minimum(sigma, sig_max)

    dampE = 1.0 / (1.0 + dt * sigma / eps)
    dampHx = 1.0 / (1.0 + 0.5 * dt * (_avg_sigma(sigma, 1, pbc_yz) + _avg_sigma(sigma, 2, pbc_yz)))
    dampHy = 1.0 / (1.0 + 0.5 * dt * (_avg_sigma(sigma, 0, False) + _avg_sigma(sigma, 2, pbc_yz)))
    dampHz = 1.0 / (1.0 + 0.5 * dt * (_avg_sigma(sigma, 0, False) + _avg_sigma(sigma, 1, pbc_yz)))

    i_src = sponge + 20
    i_mon = sponge + Nint - buf // 2
    jc = Ny // 2
    kc = Nz // 2

    period_steps = int(round(2.0 * math.pi / (omega * dt)))
    transient = max(ramp + 5 * period_steps, 4000)
    M = 80 * period_steps
    nsteps = transient + M
    meas0 = transient
    nmeas = M

    Ex = np.zeros((Nx, Ny, Nz))
    Ey = np.zeros((Nx, Ny, Nz))
    Ez = np.zeros((Nx, Ny, Nz))
    Hx = np.zeros((Nx, Ny, Nz))
    Hy = np.zeros((Nx, Ny, Nz))
    Hz = np.zeros((Nx, Ny, Nz))

    probes = np.array([[i_mon, jc, kc]], dtype=np.int64)
    re = np.zeros(1)
    im = np.zeros(1)

    pbc_y = pbc_yz
    pbc_z = pbc_yz

    for n in range(nsteps):
        t = n * dt
        env = 1.0 if n >= ramp else (n / ramp)
        src_val = env * math.cos(omega * t) if env > 0.0 else 0.0
        cos_wt = math.cos(omega * t)
        sin_wt = math.sin(omega * t)
        do_dft = (n >= meas0)
        _fdtd3d_core(Ex, Ey, Ez, Hx, Hy, Hz, eps, dampE, dampHx, dampHy, dampHz,
                     dl, dt, pbc_y, pbc_z, i_src, 0, 0, True, src_val,
                     probes, re, im, cos_wt, sin_wt, do_dft)

    amp = (re[0] + 1j * im[0]) * (2.0 / nmeas)
    if debug:
        return amp, np.max(np.abs(Ez), axis=(1, 2))
    return amp


def solve_spectrum_numba(spec, dl_factor=80.0, courant=0.95, ramp=400, sponge=320,
                         target_exp=12.0, ny=2, nz=2, angle=0.0):
    """与 fdtd3d.solve_spectrum 同签名；内部调用 Numba 加速核。"""
    layers = spec["layers"]
    wls = spec["wavelengths_um"]
    n0 = float(layers[0][1])
    nL = float(layers[-1][1])
    Ts = []
    for wl in wls:
        E_real = run_planewave_numba(layers, wl, dl_factor, courant, ramp,
                                     sponge, target_exp, ny, nz, pbc_yz=(angle == 0.0))
        ref_layers = [(th, n0) for th, n in layers]
        E_ref = run_planewave_numba(ref_layers, wl, dl_factor, courant, ramp,
                                    sponge, target_exp, ny, nz, pbc_yz=(angle == 0.0))
        if abs(E_ref) > 1e-12:
            T = (nL / n0) * abs(E_real / E_ref) ** 2
        else:
            T = 0.0
        Ts.append(float(T))
    return {
        "wavelengths_um": list(wls),
        "transmission": Ts,
        "source": "fdtd3d-numba",
        "note": "3D FDTD (全 Yee) Numba-CPU JIT 加速核，参考跑归一化绝对标度",
    }


# ---------------------------------------------------------------------------
# 点源球面波（真·三维校验 + 六向海绵无回反射）—— 与 run_greens_test 物理逐字节一致
# ---------------------------------------------------------------------------
def run_greens_test_numba(wl=2.0, n=1.0, N=120, sponge=28, dl_factor=20.0,
                          courant=0.95, ramp=400, target_exp=12.0, radii=None):
    dl, dt, omega, _ = _grid_constants(wl, dl_factor, courant)
    Nx = Ny = Nz = N
    eps = np.full((Nx, Ny, Nz), n ** 2, dtype=float)

    sig_max = target_exp * 3.0 * (n ** 2) / (dt * sponge)
    sx = _sponge_1d(Nx, sponge, sig_max)
    sy = _sponge_1d(Ny, sponge, sig_max)
    sz = _sponge_1d(Nz, sponge, sig_max)
    sigma = (np.outer(sx, np.ones(Ny * Nz)).reshape(Nx, Ny, Nz)
             + np.outer(np.ones(Nx), np.outer(sy, np.ones(Nz))).reshape(Nx, Ny, Nz)
             + np.outer(np.ones(Nx * Ny), sz).reshape(Nx, Ny, Nz))
    sigma = np.minimum(sigma, sig_max)

    dampE = 1.0 / (1.0 + dt * sigma / eps)
    dampHx = 1.0 / (1.0 + 0.5 * dt * (_avg_sigma(sigma, 1, False) + _avg_sigma(sigma, 2, False)))
    dampHy = 1.0 / (1.0 + 0.5 * dt * (_avg_sigma(sigma, 0, False) + _avg_sigma(sigma, 2, False)))
    dampHz = 1.0 / (1.0 + 0.5 * dt * (_avg_sigma(sigma, 0, False) + _avg_sigma(sigma, 1, False)))

    ci = cj = ck = N // 2
    if radii is None:
        R = (N - 2 * sponge) // 2
        radii = [int(round(f * R)) for f in (0.65, 0.8, 0.9)]
    probes = np.array([(ci + r, cj, ck) for r in radii], dtype=np.int64)

    period_steps = int(round(2.0 * math.pi / (omega * dt)))
    transient = max(ramp + 5 * period_steps, 4000)
    M = 40 * period_steps
    nsteps = transient + M
    meas0 = transient

    Ex = np.zeros((Nx, Ny, Nz))
    Ey = np.zeros((Nx, Ny, Nz))
    Ez = np.zeros((Nx, Ny, Nz))
    Hx = np.zeros((Nx, Ny, Nz))
    Hy = np.zeros((Nx, Ny, Nz))
    Hz = np.zeros((Nx, Ny, Nz))
    re = np.zeros(len(probes))
    im = np.zeros(len(probes))

    pbc_y = False
    pbc_z = False

    for n in range(nsteps):
        t = n * dt
        env = 1.0 if n >= ramp else (n / ramp)
        src_val = env * math.cos(omega * t) if env > 0.0 else 0.0
        cos_wt = math.cos(omega * t)
        sin_wt = math.sin(omega * t)
        do_dft = (n >= meas0)
        _fdtd3d_core(Ex, Ey, Ez, Hx, Hy, Hz, eps, dampE, dampHx, dampHy, dampHz,
                     dl, dt, pbc_y, pbc_z, ci, cj, ck, False, src_val,
                     probes, re, im, cos_wt, sin_wt, do_dft)

    amps = []
    for p, r in enumerate(radii):
        a = (re[p] + 1j * im[p]) * (2.0 / M)
        amps.append((r, abs(a) * r))
    return amps


if __name__ == "__main__":
    # 快速自检：匹配介质应 ≈ 1.0（同时触发 Numba 编译）
    spec = {"layers": [(float('inf'), 1.44), (float('inf'), 1.44)],
            "wavelengths_um": [1.5]}
    print("numba spectrum:", solve_spectrum_numba(spec))
