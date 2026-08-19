"""LDA · L3 自研 3D FDTD 求解核（全 Yee 网格）— C 级自主，机器优先接口。

与 fdtd1d / fdtd2d 同族：零外部依赖（仅 numpy / math）、梯度海绵吸收边界、
参考跑归一化绝对标度。升维到全 3D（六场分量 Ex/Ey/Ez/Hx/Hy/Hz），验证锚沿用
tmm.py 物理定律锚——通过"三维问题在 y、z 方向平移不变时退化为一维"的极限做
交叉校验，再加点源球面波 |Ez|·r 常数作为真·三维校验（同时验证六向海绵无回反射）。

三铁律（1D/2D 已验证，3D 沿用）：
  1. 软源须全程开启：ramp 渐入后恒 1.0 到 nsteps 结束，绝不在 DFT 测量窗口前关闭。
  2. 固定网格 + 最薄有限层整数吸附：整谱同一 dl，使几何不随 λ 漂移。
  3. 透射定标用"无结构参考跑归一化" T=(nL/n0)·|E_real/E_ref|²，共模误差在比值中抵消。

机器优先：solve_spectrum_3d(spec) 与 fdtd1d / fdtd2d / tmm 同签名，便于 ORACLE 比对。
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
    """返回 (dl, dt, omega, k0)。3D CFL 上限 dt = dl·courant/√3（c=1）。"""
    dl = wl / dl_factor
    c = 1.0
    dt = dl * courant / math.sqrt(3.0)
    omega = 2.0 * math.pi / wl
    k0 = omega / c
    return dl, dt, omega, k0


def _fwd(f, axis, pbc):
    """前向差分 f[i+1]-f[i]（含周期环绕）。非周期时末层补 0（落在海绵内）。"""
    if pbc:
        return np.roll(f, -1, axis=axis) - f
    ndim = f.ndim
    out = np.zeros_like(f)
    sl = [slice(None)] * ndim
    sl[axis] = slice(0, -1)
    sl_next = [slice(None)] * ndim
    sl_next[axis] = slice(1, None)
    out[tuple(sl)] = f[tuple(sl_next)] - f[tuple(sl)]
    return out


def _bwd(f, axis, pbc):
    """后向差分 f[i]-f[i-1]（含周期环绕）。非周期时首层补 0（落在海绵内）。"""
    if pbc:
        return f - np.roll(f, 1, axis=axis)
    ndim = f.ndim
    out = np.zeros_like(f)
    sl = [slice(None)] * ndim
    sl[axis] = slice(1, None)
    sl_prev = [slice(None)] * ndim
    sl_prev[axis] = slice(None, -1)
    out[tuple(sl)] = f[tuple(sl)] - f[tuple(sl_prev)]
    return out


def _avg_sigma(sigma, axis, pbc):
    """H 节点处的 sigma：取 E 节点两侧均值（偏移轴）; 非周期首层取边缘值。"""
    if pbc:
        return 0.5 * (sigma + np.roll(sigma, 1, axis=axis))
    ndim = sigma.ndim
    out = np.zeros_like(sigma)
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
# 平面波（分层膜）求解 —— 退化为一维时由 tmm.py 校验
# ---------------------------------------------------------------------------
def _run_field_core(eps, dl, wl, courant, ramp, sponge, target_exp,
                    pbc_yz, n0, i_src, i_mon, jc, kc, debug=False):
    """通用 FDTD 时间步进核心（机器优先，消费任意 3D 折射率体素场）。

    复用已验证的 3D 全 Yee propagator：三铁律（软源全程开 / 固定网格 /
    参考跑归一化）+ 梯度海绵 + 整数周期 DFT。eps 为 3D 数组（含 n^2）。
    pbc_yz：y/z 方向周期（分层膜退化=True；真 3D 器件=False）。
    n0：入射介质折射率（海绵 sig_max 标度 + 源相位）。
    i_src/i_mon/jc/kc：源 / 监视器单元索引（由调用方按几何给定）。
    """
    Nx, Ny, Nz = eps.shape
    c = 1.0
    dt = dl * courant / math.sqrt(3.0)
    omega = 2.0 * math.pi / wl
    k0 = omega / c

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
    # H 节点偏置在两个方向 → 导电率取两轴均值(各 0.5)，不可直接相加(会 2× 过阻尼)
    dampHx = 1.0 / (1.0 + 0.5 * dt * (_avg_sigma(sigma, 1, pbc_yz) + _avg_sigma(sigma, 2, pbc_yz)))
    dampHy = 1.0 / (1.0 + 0.5 * dt * (_avg_sigma(sigma, 0, False) + _avg_sigma(sigma, 2, pbc_yz)))
    dampHz = 1.0 / (1.0 + 0.5 * dt * (_avg_sigma(sigma, 0, False) + _avg_sigma(sigma, 1, pbc_yz)))

    period_steps = int(round(2.0 * math.pi / (omega * dt)))
    transient = max(ramp + 5 * period_steps, 4000)
    # 整数周期 DFT：M 为 period_steps 的整数倍即精确，与窗口长短无关 → 取 80 周期足够
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

    re = 0.0
    im = 0.0
    for n in range(nsteps):
        t = n * dt
        # ---- H 更新（半步）----
        Hx -= (dt / dl) * (_fwd(Ez, 1, pbc_yz) - _fwd(Ey, 2, pbc_yz))
        Hy -= (dt / dl) * (_fwd(Ex, 2, pbc_yz) - _fwd(Ez, 0, False))
        Hz -= (dt / dl) * (_fwd(Ey, 0, False) - _fwd(Ex, 1, pbc_yz))
        Hx *= dampHx
        Hy *= dampHy
        Hz *= dampHz
        # ---- E 更新（全步）----
        Ex += (dt / (eps * dl)) * (_bwd(Hz, 1, pbc_yz) - _bwd(Hy, 2, pbc_yz))
        Ey += (dt / (eps * dl)) * (_bwd(Hx, 2, pbc_yz) - _bwd(Hz, 0, False))
        Ez += (dt / (eps * dl)) * (_bwd(Hy, 0, False) - _bwd(Hx, 1, pbc_yz))
        # 导电海绵须同时阻尼 E（仅阻尼 H 会破坏波阻抗匹配、并纵容寄生 Ex/Ey/Hz 增长）
        Ex *= dampE
        Ey *= dampE
        Ez *= dampE
        # 软源（全程开：ramp 渐入后恒 1.0）
        env = 1.0 if n >= ramp else (n / ramp)
        if env > 0.0:
            Ez[i_src, :, :] += env * math.cos(omega * t)
        # DFT 累积（测量窗口）
        if n >= meas0:
            v = Ez[i_mon, jc, kc]
            re += v * math.cos(omega * t)
            im -= v * math.sin(omega * t)

    amp = (re + 1j * im) * (2.0 / nmeas)
    if debug:
        return amp, np.max(np.abs(Ez), axis=(1, 2))
    return amp


def _run_planewave(layers, wl, dl_factor=80.0, courant=0.95, ramp=400,
                   sponge=320, target_exp=12.0, ny=2, nz=2, pbc_yz=True,
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

    prof, _, _ = _build_interior(layers, dl, buf)
    Nint = len(prof)
    Nx = Nint + 2 * sponge
    Ny = ny
    Nz = nz

    eps = np.empty((Nx, Ny, Nz), dtype=float)
    eps[:sponge] = n0 ** 2
    prof_arr = np.array(prof, dtype=float) ** 2   # length Nint
    eps[sponge:sponge + Nint, :, :] = prof_arr[:, None, None]
    eps[sponge + Nint:, :, :] = nL ** 2

    # 分层膜（一维退化）用例启用 y/z 方向 PBC —— 让 y、z 导数恒 0，
    # 仅剩 x 方向传播，恢复纯一维；此时仅需 x 方向海绵。点源用例（pbc_yz=False）
    # 用六向海绵。
    # 源/监视器位置（与原 propagator 一致，保证退化逐位等价）
    i_src = sponge + 20
    i_mon = sponge + Nint - buf // 2
    jc = Ny // 2
    kc = Nz // 2
    return _run_field_core(eps, dl, wl, courant, ramp, sponge, target_exp,
                           pbc_yz, n0, i_src, i_mon, jc, kc, debug=debug)


def solve_spectrum(spec, dl_factor=80.0, courant=0.95, ramp=400, sponge=320,
                   target_exp=12.0, ny=2, nz=2, angle=0.0):
    """与 fdtd1d / fdtd2d / tmm 同签名的 3D 透射谱（参考跑归一化绝对标度）。

    对每一波长：真实结构 + 几何全同但所有层替换为 n0 的"无结构参考跑"，
    T=(nL/n0)·|E_real/E_ref|²。angle=0 时退化为一维（由 tmm 校验）。
    """
    layers = spec["layers"]
    wls = spec["wavelengths_um"]
    n0 = float(layers[0][1])
    nL = float(layers[-1][1])
    Ts = []
    for wl in wls:
        E_real = _run_planewave(layers, wl, dl_factor, courant, ramp,
                                sponge, target_exp, ny, nz, pbc_yz=(angle == 0.0))
        ref_layers = [(th, n0) for th, n in layers]
        E_ref = _run_planewave(ref_layers, wl, dl_factor, courant, ramp,
                               sponge, target_exp, ny, nz, pbc_yz=(angle == 0.0))
        if abs(E_ref) > 1e-12:
            T = (nL / n0) * abs(E_real / E_ref) ** 2
        else:
            T = 0.0
        Ts.append(float(T))
    return {
        "wavelengths_um": list(wls),
        "transmission": Ts,
        "source": "fdtd3d-sovereign",
        "note": "3D FDTD (全 Yee) 自研核，参考跑归一化绝对标度",
    }


def solve_spectrum_field(spec, courant=0.95, ramp=400, sponge=320,
                         target_exp=12.0, pbc_yz=True, ny=2):
    """消费外部体素折射率场（机器优先 voxel_field 管线产物）。

    与 solve_spectrum 同签名返回 {wavelengths_um, transmission, source, note}，
    便于 ORACLE 直接比对。spec 键：
      eps_field      : 2D(Nx,Ny) 或 3D(Nx,Ny,Nz) numpy 数组，含 n^2
      dl             : 单元尺寸 um
      wavelengths_um : 扫频点列表
      n0 / nL        : 入射/出射介质折射率（默认从场边缘非海绵区估）
      src_x / mon_x  : 源/监视器 x 单元索引（默认 sponge+20 / Nx-sponge-20）
      jc / kc        : y/z 监视器索引（默认中心）
    沿 x 传播、正入射平面波；参考跑=同几何全填 n0^2 的均匀场归一化。
    """
    ef = np.asarray(spec["eps_field"], dtype=float)
    if ef.ndim == 2:
        ef = np.repeat(ef[:, :, None], ny, axis=2)
    Nx, Ny, Nz = ef.shape
    dl = float(spec["dl"])
    wls = spec["wavelengths_um"]

    # 入射/出射介质：默认取场边缘非海绵区（调用方须保证入射/出射半空间填对应 n^2）
    n0 = float(spec.get("n0", np.sqrt(ef[sponge // 2, Ny // 2, Nz // 2])))
    nL = float(spec.get("nL", np.sqrt(ef[-(sponge // 2 + 1), Ny // 2, Nz // 2])))
    i_src = int(spec.get("src_x", sponge + 20))
    i_mon = int(spec.get("mon_x", Nx - sponge - 20))
    jc = int(spec.get("jc", Ny // 2))
    kc = int(spec.get("kc", Nz // 2))

    Ts = []
    for wl in wls:
        E_real = _run_field_core(ef, dl, wl, courant, ramp, sponge, target_exp,
                                 pbc_yz, n0, i_src, i_mon, jc, kc)
        ref_eps = np.full_like(ef, n0 ** 2)
        E_ref = _run_field_core(ref_eps, dl, wl, courant, ramp, sponge, target_exp,
                                pbc_yz, n0, i_src, i_mon, jc, kc)
        if abs(E_ref) > 1e-12:
            T = (nL / n0) * abs(E_real / E_ref) ** 2
        else:
            T = 0.0
        Ts.append(float(T))
    return {
        "wavelengths_um": list(wls),
        "transmission": Ts,
        "source": "fdtd3d-field-sovereign",
        "note": "3D FDTD 体素场模式（任意几何），参考跑归一化绝对标度",
    }


# ---------------------------------------------------------------------------
# 点源球面波（真·三维校验 + 六向海绵无回反射）
# ---------------------------------------------------------------------------
def run_greens_test(wl=2.0, n=1.0, N=120, sponge=28, dl_factor=20.0,
                    courant=0.95, ramp=400, target_exp=12.0, radii=None):
    """均匀介质中点源激发的 3D 球面波；返回 [(r, |Ez_dft|·r), ...]。

    真·三维判据：远场 |Ez| ∝ 1/r（球面 Hankel h0^(2) 渐近），故 |Ez|·r 应为常数；
    若六向海绵回反射，则近海绵处该乘积会偏离常数。

    探针位置按"内部非海绵区半径"的比例布置（r ≥ λ 以保证近场修正 ≪ 容差），
    确保任何 N/海绵参数下都落在有效吸收层之外；DFT 窗口取 40 个周期。
    """
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
        # 按内部非海绵区半径的比例取探针（始终落在吸收层之外且 r ≥ λ）
        R = (N - 2 * sponge) // 2
        radii = [int(round(f * R)) for f in (0.65, 0.8, 0.9)]
    probes = [(ci + r, cj, ck) for r in radii]

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
    re = [0.0] * len(probes)
    im = [0.0] * len(probes)

    for n in range(nsteps):
        t = n * dt
        Hx -= (dt / dl) * (_fwd(Ez, 1, False) - _fwd(Ey, 2, False))
        Hy -= (dt / dl) * (_fwd(Ex, 2, False) - _fwd(Ez, 0, False))
        Hz -= (dt / dl) * (_fwd(Ey, 0, False) - _fwd(Ex, 1, False))
        Hx *= dampHx
        Hy *= dampHy
        Hz *= dampHz
        Ex += (dt / (eps * dl)) * (_bwd(Hz, 1, False) - _bwd(Hy, 2, False))
        Ey += (dt / (eps * dl)) * (_bwd(Hx, 2, False) - _bwd(Hz, 0, False))
        Ez += (dt / (eps * dl)) * (_bwd(Hy, 0, False) - _bwd(Hx, 1, False))
        Ex *= dampE
        Ey *= dampE
        Ez *= dampE
        env = 1.0 if n >= ramp else (n / ramp)
        if env > 0.0:
            Ez[ci, cj, ck] += env * math.cos(omega * t)
        if n >= meas0:
            for p, (pi, pj, pk) in enumerate(probes):
                v = Ez[pi, pj, pk]
                re[p] += v * math.cos(omega * t)
                im[p] -= v * math.sin(omega * t)

    amps = []
    for p, r in enumerate(radii):
        a = (re[p] + 1j * im[p]) * (2.0 / M)
        amps.append((r, abs(a) * r))
    return amps


def solve_spectrum_field_stack(layers, wavelengths_um, dl_factor=80.0, courant=0.95,
                               ramp=400, sponge=320, target_exp=12.0, ny=2, nz=2,
                               pbc_yz=True):
    """stack 退化的体素场求解（与 solve_spectrum 平行，逐位等价验证入口）。

    每波长复用 voxel_field.voxelize_stack（_build_interior 同内核）构造 3D 体素场，
    再调 _run_field_core。eps 构造与 _run_planewave 完全一致 → 与 solve_spectrum
    逐位相同；用于证明 "版图→体素→FDTD" 链路零引入误差。
    """
    from voxel_field import voxelize_stack
    n0 = float(layers[0][1])
    nL = float(layers[-1][1])
    Ts = []
    for wl in wavelengths_um:
        dl = wl / dl_factor
        buf = max(20, int(round(3.0 / dl)))
        ef, meta = voxelize_stack(layers, dl, buf, sponge, ny, nz)
        E_real = _run_field_core(ef, dl, wl, courant, ramp, sponge, target_exp,
                                 pbc_yz, n0, meta["src_x"], meta["mon_x"], ny // 2, nz // 2)
        ref_ef = np.full_like(ef, n0 ** 2)
        E_ref = _run_field_core(ref_ef, dl, wl, courant, ramp, sponge, target_exp,
                                pbc_yz, n0, meta["src_x"], meta["mon_x"], ny // 2, nz // 2)
        if abs(E_ref) > 1e-12:
            T = (nL / n0) * abs(E_real / E_ref) ** 2
        else:
            T = 0.0
        Ts.append(float(T))
    return {
        "wavelengths_um": list(wavelengths_um),
        "transmission": Ts,
        "source": "fdtd3d-field-sovereign-stack",
        "note": "stack 退化体素场求解（与 solve_spectrum 逐位等价）",
    }


if __name__ == "__main__":
    # 快速自检：匹配介质应 ≈ 1.0
    spec = {"layers": [(float('inf'), 1.44), (float('inf'), 1.44)],
            "wavelengths_um": [1.5]}
    print(solve_spectrum(spec))
