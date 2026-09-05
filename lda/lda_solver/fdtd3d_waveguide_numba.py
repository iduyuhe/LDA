"""WG 标量 3D FDTD 的 numba-CPU 后端（T-8 去 GPU）。

背景（v0.9.38 实测）：
  `fdtd3d_waveguide.solve_waveguide_neff_3d`（纯 numpy）在 70×65×124 网格、
  nsteps=6520 下实测 **389.0s** —— 这是 DeviceLibrary live 验收里唯一真正跑不动
  的重项（DC 15.3s / YB 19.1s / Bragg 19.9s / Ring <0.1s）。

做法（**不改物理，只换计算后端**）：
  把同一个「三场蛙跳 + 六面海绵阻尼 + 软源 + 双点 DFT + 三面重叠积分投影」
  循环用 numba njit(parallel) 重写，逐行对应 numpy 版。物理网格 dl、海绵
  target_exp、源 ramp、测量窗 M、transient 全部沿用生产默认值 ⇒ **数值结果
  必须与 numpy 版一致**（交叉验证判据：neff 相对差 ≤ 1e-9，见
  `run_device_library_smoke.py` 与 `docs/`）。

纪律（IRONLAWS）：
  - numba 是**可选加速**，不是硬依赖：缺失/编译失败一律回退 numpy，行为不变。
  - 本模块**不参与判决语义**：只提供同一物理量的更快实现；判定仍由
    `verification_spec` 的 compare_fn + 契约 tol 做出，LLM 不进判决路径。
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

import numpy as np

# 双路兜底（IRONLAWS：包内模块相对导入 + 可选依赖不硬依赖）
try:  # pragma: no cover - 导入形态取决于调用方 sys.path
    from .fdtd3d import _sponge_1d
except Exception:  # noqa: BLE001
    try:
        from fdtd3d import _sponge_1d
    except Exception:  # noqa: BLE001
        _sponge_1d = None  # type: ignore[assignment]

try:  # pragma: no cover
    from numba import njit, prange

    HAVE_NUMBA = True
    NUMBA_IMPORT_ERROR = ""
except Exception as _e:  # noqa: BLE001
    HAVE_NUMBA = False
    NUMBA_IMPORT_ERROR = f"{type(_e).__name__}: {_e}"

    def njit(*_a, **_k):  # type: ignore[misc]
        def _deco(f):
            return f

        return _deco

    prange = range  # type: ignore[assignment]


# ---------------------------------------------------------------- numba 核
@njit(cache=True, parallel=True, nogil=True)
def _wg_core(eps3, g, prof, phi, dl, dt, omega, cx, cy,
             src_z, z1, z2, za, zb, zc, use_proj,
             nsteps, ramp, meas0, M):
    """标量波动三场蛙跳 + 阻尼海绵 + 软源 + DFT（与 numpy 版逐行对应）。

    返回 (re1, im1, re2, im2, Oa_re, Oa_im, Ob_re, Ob_im, Oc_re, Oc_im)。
    三场用引用轮转（tmp/Eprev/Ecur/Enext），每步零拷贝。
    """
    Nx, Ny, Nz = eps3.shape
    Eprev = np.zeros((Nx, Ny, Nz))
    Ecur = np.zeros((Nx, Ny, Nz))
    Enext = np.zeros((Nx, Ny, Nz))
    re1 = im1 = re2 = im2 = 0.0
    Oa_re = Oa_im = Ob_re = Ob_im = Oc_re = Oc_im = 0.0
    dt2 = dt * dt
    inv_dl2 = 1.0 / (dl * dl)

    for n in range(nsteps):
        t = n * dt
        # ---- 3D 拉普拉斯（仅内部；边界层恒 0）----
        for i in prange(1, Nx - 1):
            for j in range(1, Ny - 1):
                for k in range(1, Nz - 1):
                    e = Ecur[i, j, k]
                    lap = ((Ecur[i + 1, j, k] - 2.0 * e + Ecur[i - 1, j, k])
                           + (Ecur[i, j + 1, k] - 2.0 * e + Ecur[i, j - 1, k])
                           + (Ecur[i, j, k + 1] - 2.0 * e + Ecur[i, j, k - 1])
                           ) * inv_dl2
                    eo = Eprev[i, j, k]
                    gg = g[i, j, k]
                    Enext[i, j, k] = (2.0 * e - eo + dt2 * lap / eps3[i, j, k]
                                      + gg * (e - eo)) / (1.0 + gg)
        # ---- 六面边界恒 0（海绵吸收向内传播波）----
        for j in range(Ny):
            for k in range(Nz):
                Enext[0, j, k] = 0.0
                Enext[Nx - 1, j, k] = 0.0
        for i in range(Nx):
            for k in range(Nz):
                Enext[i, 0, k] = 0.0
                Enext[i, Ny - 1, k] = 0.0
        for i in range(Nx):
            for j in range(Ny):
                Enext[i, j, 0] = 0.0
                Enext[i, j, Nz - 1] = 0.0
        # ---- 软源（ramp 渐入后恒 1.0，全程开启）----
        env = (n / ramp) if n < ramp else 1.0
        s = env * math.sin(omega * t)
        for i in range(Nx):
            for j in range(Ny):
                Enext[i, j, src_z] += s * prof[i, j]
        # ---- DFT 窗（双点 + 三面投影）----
        if n >= meas0:
            ct = math.cos(omega * t)
            st = -math.sin(omega * t)
            v1 = Enext[cx, cy, z1]
            v2 = Enext[cx, cy, z2]
            re1 += v1 * ct
            im1 += v1 * st
            re2 += v2 * ct
            im2 += v2 * st
            if use_proj:
                sa = 0.0
                sb = 0.0
                sc = 0.0
                for i in range(Nx):
                    for j in range(Ny):
                        p = phi[i, j]
                        sa += p * Enext[i, j, za]
                        sb += p * Enext[i, j, zb]
                        sc += p * Enext[i, j, zc]
                Oa_re += sa * ct
                Oa_im += sa * st
                Ob_re += sb * ct
                Ob_im += sb * st
                Oc_re += sc * ct
                Oc_im += sc * st
        # ---- 三场轮转（引用交换）----
        tmp = Eprev
        Eprev = Ecur
        Ecur = Enext
        Enext = tmp

    return (re1, im1, re2, im2, Oa_re, Oa_im, Ob_re, Ob_im, Oc_re, Oc_im)


# ---------------------------------------------------------------- 前置量准备
def _prepare(eps3: np.ndarray, dl: float, wl_um: float, n_clad: float,
             n_core: Optional[float], sponge: int, target_exp: float,
             courant: float, z1_frac: float, src_frac: float,
             mode_source: Optional[np.ndarray], ramp: int,
             M_periods: int, transient_min: int) -> Dict[str, Any]:
    """复刻 numpy 版的前置量（海绵 / 源剖面 / 监视面 / 步数），供两个后端共用。"""
    eps3 = np.asarray(eps3, dtype=float)
    Nx, Ny, Nz = eps3.shape
    if n_core is None:
        n_core = float(np.sqrt(eps3.max()))
    omega = 2.0 * math.pi / wl_um
    k0 = omega
    dt = dl * courant / math.sqrt(3.0)
    n0 = n_clad

    sponge_xy = max(8, min(Nx, Ny) // 4)
    sponge_z = max(8, min(sponge, Nz // 4))
    sig_xy = target_exp * 3.0 * (n0 ** 2) / (dt * sponge_xy)
    sig_z = target_exp * 3.0 * (n0 ** 2) / (dt * sponge_z)
    sx = _sponge_1d(Nx, sponge_xy, sig_xy)
    sy = _sponge_1d(Ny, sponge_xy, sig_xy)
    sz = _sponge_1d(Nz, sponge_z, sig_z)
    sig_cap = max(sig_xy, sig_z)
    sigma = (sx[:, None, None] + sy[None, :, None] + sz[None, None, :])
    np.clip(sigma, 0.0, sig_cap, out=sigma)
    g = sigma * dt / (2.0 * eps3)

    Nz_int = Nz - 2 * sponge_z
    cx, cy = Nx // 2, Ny // 2
    src_z = sponge_z + max(8, int(src_frac * Nz_int))
    neff_avg = 0.5 * (n_clad + n_core)
    dz_cells = max(4, int(round(0.40 * (wl_um / neff_avg) / dl)))
    z1 = sponge_z + int(z1_frac * Nz_int)
    z2 = z1 + dz_cells
    if z2 >= sponge_z + Nz_int - 4:
        z2 = sponge_z + Nz_int - 4
        z1 = z2 - dz_cells

    use_proj = mode_source is not None
    za = zb = zc = 0
    dz_phys = 0.0
    phi = np.zeros((Nx, Ny))
    if use_proj:
        phi = np.asarray(mode_source, dtype=float).reshape(Nx, Ny)
        pnorm = float(np.sum(phi * phi))
        if pnorm <= 0:
            use_proj = False
        else:
            phi = phi / math.sqrt(pnorm)
            za, zb, zc = z1, z1 + dz_cells, z1 + 2 * dz_cells
            if zc >= sponge_z + Nz_int - 4:
                use_proj = False
            else:
                dz_phys = dz_cells * dl

    prof = np.zeros((Nx, Ny))
    if mode_source is not None:
        prof = np.asarray(mode_source, dtype=float).reshape(Nx, Ny)
        pmax = float(np.max(np.abs(prof)))
        if pmax > 0:
            prof = prof / pmax
    else:
        core_mask = eps3[:, :, 0] > (n_clad ** 2 + n_core ** 2) / 2.0
        rows = np.where(core_mask.any(axis=1))[0]
        cols = np.where(core_mask.any(axis=0))[0]
        if rows.size > 1 and cols.size > 1:
            wx = max(2.0, (rows.max() - rows.min() + 1) / 2.0)
            wy = max(2.0, (cols.max() - cols.min() + 1) / 2.0)
        else:
            wx = wy = max(2.0, min(Nx, Ny) * 0.1)
        ax = (np.arange(Nx) - cx) / wx
        ay = (np.arange(Ny) - cy) / wy
        prof = np.exp(-(ax[:, None] ** 2 + ay[None, :] ** 2) / 2.0)

    period_steps = int(round(2.0 * math.pi / (omega * dt)))
    M = M_periods * period_steps
    transient = max(ramp + 5 * period_steps, transient_min)
    return dict(eps3=eps3, g=g, prof=prof, phi=phi, dl=dl, dt=dt, omega=omega,
                k0=k0, cx=cx, cy=cy, src_z=src_z, z1=z1, z2=z2,
                za=za, zb=zb, zc=zc, use_proj=use_proj, dz_phys=dz_phys,
                nsteps=transient + M, ramp=ramp, meas0=transient, M=M,
                n_core=n_core, period_steps=period_steps,
                grid_shape=(Nx, Ny, Nz), grid_cells=Nx * Ny * Nz)


def _postprocess(P: Dict[str, Any], acc: Tuple[float, ...]
                 ) -> Tuple[float, float, int]:
    """DFT → 相位差 / 三面投影 → neff；与 numpy 版同公式同 m 缠绕判据。"""
    (re1, im1, re2, im2, Oa_re, Oa_im, Ob_re, Ob_im, Oc_re, Oc_im) = acc
    M = P["M"]
    k0 = P["k0"]
    n_clad = P["n_clad"]
    n_core = P["n_core"]
    dl = P["dl"]
    amp1 = (re1 + 1j * im1) * (2.0 / M)
    amp2 = (re2 + 1j * im2) * (2.0 / M)
    dphi = (np.angle(amp1) - np.angle(amp2) + math.pi) % (2.0 * math.pi) - math.pi
    dz = (P["z2"] - P["z1"]) * dl
    m_low = math.ceil((n_clad * k0 * dz - dphi) / (2.0 * math.pi) - 1e-9)
    m_high = math.floor((n_core * k0 * dz - dphi) / (2.0 * math.pi) + 1e-9)
    if m_high < m_low:
        m = int(round(((n_clad + n_core) / 2.0 * k0 * dz - dphi) / (2.0 * math.pi)))
    else:
        m = m_low
    neff = (dphi + 2.0 * math.pi * m) / (k0 * dz)
    snr = min(abs(amp1), abs(amp2)) / (abs(amp1) + abs(amp2) + 1e-30)

    if P["use_proj"]:
        Oa = complex(Oa_re, Oa_im)
        Ob = complex(Ob_re, Ob_im)
        Oc = complex(Oc_re, Oc_im)
        if abs(Ob) > 1e-30:
            cos_bdz = float(np.real((Oa + Oc) / (2.0 * Ob)))
            cos_bdz = max(-1.0, min(1.0, cos_bdz))
            beta_dz = math.acos(cos_bdz)
            neff_p = beta_dz / (k0 * P["dz_phys"])
            if n_clad * 1.001 < neff_p < n_core * 0.999:
                neff = neff_p
                snr = min(abs(Oa), abs(Ob), abs(Oc)) / (
                    abs(Oa) + abs(Ob) + abs(Oc) + 1e-30)
    if not (n_clad * 1.001 < neff < n_core * 0.999):
        for mm in (m - 1, m + 1):
            cand = (dphi + 2.0 * math.pi * mm) / (k0 * dz)
            if n_clad * 1.001 < cand < n_core * 0.999:
                neff, m = cand, mm
                break
    return float(neff), float(snr), int(m)


# ---------------------------------------------------------------- 对外接口
def solve_waveguide_neff_3d_numba(eps3: np.ndarray, dl: float, wl_um: float,
                                  n_clad: float, n_core: Optional[float] = None,
                                  sponge: int = 60, target_exp: float = 12.0,
                                  courant: float = 0.95, dz_um: float = 0.6,
                                  ramp: int = 400, z1_frac: float = 0.45,
                                  src_frac: float = 0.12,
                                  mode_source: Optional[np.ndarray] = None,
                                  debug: bool = False,
                                  M_periods: int = 80,
                                  transient_min: int = 3000
                                  ):
    """numba-CPU 版 WG neff 求解（与 numpy 版同物理、同默认参数）。

    debug=True 时返回 (neff, beta, m, snr)；否则返回 float。
    """
    if not HAVE_NUMBA:
        raise RuntimeError(f"numba 不可用（{NUMBA_IMPORT_ERROR}）")
    P = _prepare(eps3, dl, wl_um, n_clad, n_core, sponge, target_exp, courant,
                 z1_frac, src_frac, mode_source, ramp, M_periods, transient_min)
    P["n_clad"] = n_clad
    acc = _wg_core(P["eps3"], P["g"], P["prof"], P["phi"], P["dl"], P["dt"],
                   P["omega"], P["cx"], P["cy"], P["src_z"], P["z1"], P["z2"],
                   P["za"], P["zb"], P["zc"], P["use_proj"], P["nsteps"],
                   P["ramp"], P["meas0"], P["M"])
    neff, snr, m = _postprocess(P, acc)
    if debug:
        return float(neff), float(neff * P["k0"]), int(m), float(snr)
    return float(neff)


def backend_info() -> Dict[str, Any]:
    """供诚实披露：当前 numba 可用性 + 错误原因。"""
    return {"have_numba": HAVE_NUMBA, "import_error": NUMBA_IMPORT_ERROR}
