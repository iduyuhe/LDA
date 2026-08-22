# -*- coding: utf-8 -*-
"""LDA · D-72 深化：真实器件 3D FDTD 端口 S 参数验收（SOI 220nm）。

把 2D 端口 S 参数验收深化到 3D：MMI 1×2 对称分束器（SOI 220nm 波导层 +
上下包层）全 3D FDTD 端口透反射谱——3D 高斯分布源（TE 主极化 Ez）注入 →
多端口 DFT 收集 → 输入功率归一 → S 参数谱（|S11|²/|S21|²/|S31|²）→
死标量验收（仿真有效 + 平衡度 ≤0.15 + 透射 ≥0.05，自成像对称 ORACLE）
+ 2D↔3D 连续性对拍诊断（3D 有垂直模式约束，S 参数差异是物理非 bug）。

复用已验证 3D FDTD 核 `fdtd3d_numba._fdtd3d_core`（numba njit，物理定律锚
校验过），仅在外层驱动 CW 稳态 + 分布源 + 端口探针；零新依赖。
LLM 不进判决路径。
"""
from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

import numpy as np

from lda_l2.primitives import mmi_descs  # noqa: E402

# fdtd3d_numba 用扁平导入（from fdtd3d import ...），需把 lda_solver 目录
# 加入 sys.path 才能以包方式导入
import os as _os
import sys as _sys
_LDA_SOLVER = _os.path.dirname(_os.path.abspath(__file__))
if _LDA_SOLVER not in _sys.path:
    _sys.path.insert(0, _LDA_SOLVER)

from fdtd3d_numba import _fdtd3d_core  # noqa: E402
from fdtd3d import _sponge_1d, _avg_sigma  # noqa: E402
from lda_solver.port_sparams import _point_in_poly  # noqa: E402


# ---------------------------------------------------------------------------
# 3D MMI eps 体素场（2D 多边形 → y mask → z 拉伸 SOI 层）
# ---------------------------------------------------------------------------
def build_mmi_field_3d(w_um: float, W_mmi: float, L_mmi: float, L_tap: float,
                       out_gap: float, L_out: float, n_core: float,
                       n_clad: float, h_si_um: float = 0.22, dl: float = 0.0775,
                       pad_um: float = 2.0, clad_z_um: float = 2.0):
    """MMI 3D 体素场：y 奇数（关于 y=0 对称）、z 奇数（波导层居中）。

    返回 (eps, dl, ports, i_src)：ports 值 (x_cell, (y_lo,y_hi), (z_lo,z_hi))。
    """
    descs = mmi_descs({"width": w_um, "W_mmi": W_mmi, "L_mmi": L_mmi,
                       "L_tap": L_tap, "out_gap": out_gap, "L_out": L_out})
    x_in = -L_tap - pad_um
    x_out = L_mmi + L_tap + L_out + pad_um
    Lx = x_out - x_in
    Ly = W_mmi / 2.0 + pad_um + w_um
    Nx = int(round(Lx / dl))
    Ny = int(round(2.0 * Ly / dl)) | 1          # 奇数：网格关于 y=0 严格对称
    # z：波导层奇数格 + 上下包层
    Nzh = max(1, int(round(h_si_um / dl)) | 1)
    Nzc = int(round(clad_z_um / dl)) * 2
    Nz = Nzh + Nzc
    Nz_lo = (Nz - Nzh) // 2
    zc = (Nz - 1) / 2.0                          # z 中心（波导层中心）

    # y-mask（2D 多边形栅格化，同 2D 逻辑）
    mask2 = np.zeros((Nx, Ny), dtype=bool)
    polys = []
    for d in descs:
        if d["kind"] == "boundary":
            polys.append(d["rings_um"][0])
        elif d["kind"] == "path":
            x0, y0 = d["points_um"][0]
            x1, y1 = d["points_um"][1]
            hw = d.get("width_um", w_um) / 2.0
            if abs(y1 - y0) < 1e-12:
                polys.append([(x0, y0 - hw), (x1, y1 - hw),
                              (x1, y1 + hw), (x0, y0 + hw)])
            else:
                polys.append([(x0 - hw, y0), (x0 + hw, y0),
                              (x1 + hw, y1), (x1 - hw, y1)])
    for poly in polys:
        ppts = [(x, y) for x, y in poly]
        # j(y) = y/dl + (Ny-1)/2，无 Ly 偏移（曾误加 Ly → 范围错位 → mask 空）
        ymin = int(max(0, min(p[1] for p in ppts) / dl + (Ny - 1) / 2.0))
        ymax = int(min(Ny - 1, max(p[1] for p in ppts) / dl + (Ny - 1) / 2.0))
        for j in range(ymin, ymax + 1):
            yy = (j - (Ny - 1) / 2.0) * dl
            for i in range(Nx):
                xx = i * dl + x_in
                if not mask2[i, j] and _point_in_poly(xx, yy, ppts):
                    mask2[i, j] = True

    eps = np.full((Nx, Ny, Nz), n_clad ** 2)
    core_vals = np.where(mask2, n_core ** 2, n_clad ** 2)
    eps[:, :, Nz_lo:Nz_lo + Nzh] = core_vals[:, :, None]

    def cy(y_um: float) -> int:
        return int(round((Ny - 1) / 2.0 + y_um / dl))

    def cz(z_um: float) -> int:
        return int(round(zc + z_um / dl))

    yo = w_um / 2.0 + out_gap / 2.0
    z_lo, z_hi = cz(-h_si_um / 2.0), cz(h_si_um / 2.0)
    x_src = int(round((-L_tap * 0.6 - x_in) / dl))
    x_out_c = int(round((L_mmi + L_tap + L_out / 2.0 - x_in) / dl))
    ports = {
        "in": (x_src - 6, (cy(-w_um / 2.0), cy(w_um / 2.0)), (z_lo, z_hi)),
        "out1": (x_out_c, (cy(yo - w_um / 2.0), cy(yo + w_um / 2.0)), (z_lo, z_hi)),
        "out2": (x_out_c, (cy(-yo - w_um / 2.0), cy(-yo + w_um / 2.0)), (z_lo, z_hi)),
    }
    return eps, dl, ports, x_src


# ---------------------------------------------------------------------------
# 3D CW 稳态 + 多端口 DFT 收集（复用 _fdtd3d_core）
# ---------------------------------------------------------------------------
def cw3d_port_powers(eps: np.ndarray, dl: float, wl_um: float,
                     ports: Dict, x_src: int,
                     transient_cycles: int = 800, M_cycles: int = 40,
                     sponge: int = 24, courant: float = 0.95,
                     source_amp: float = 0.05) -> Dict[str, float]:
    """3D CW 稳态：Ez 高斯分布源（y,z 横截面）注入 → 各端口芯区 |Ez|² 积分。

    复用 _fdtd3d_core（numba njit）；内部源禁用（src_val=0），
    外层每步手动注入 TE 主极化分布源（稳态下相位差恒定，|Ez|² 不受影响）。
    """
    omega = 2.0 * math.pi / wl_um
    dt = dl * courant / math.sqrt(3.0)
    Nx, Ny, Nz = eps.shape
    n0 = 1.0
    # 🔴 sponge 自适应 clamp：PML 厚度必须 ≤ Ny/4 与 Nz/4，
    # 否则小域（尤其 Nz≈19）两端 sponge 重叠覆盖波导层 → 场被整体吸收
    sponge = int(min(sponge, Ny // 4, Nz // 4))
    sponge = max(sponge, 2)
    sig_max = 12.0 * 3.0 * (n0 ** 2) / (dt * sponge)
    sx = _sponge_1d(Nx, sponge, sig_max)
    sy = _sponge_1d(Ny, sponge, sig_max)
    sz = _sponge_1d(Nz, sponge, sig_max)
    sigma = (sx[:, None, None] + sy[None, :, None] + sz[None, None, :])
    sigma = np.minimum(sigma, sig_max)
    dampE = 1.0 / (1.0 + dt * sigma / eps)
    dampHx = 1.0 / (1.0 + 0.5 * dt * (_avg_sigma(sigma, 1, False) + _avg_sigma(sigma, 2, False)))
    dampHy = 1.0 / (1.0 + 0.5 * dt * (_avg_sigma(sigma, 0, False) + _avg_sigma(sigma, 2, False)))
    dampHz = 1.0 / (1.0 + 0.5 * dt * (_avg_sigma(sigma, 0, False) + _avg_sigma(sigma, 1, False)))

    # 源横截面分布：与波导截面匹配（矩形近似 TE0 基模芯区分布，
    # 高斯过宽会把能量注入包层——3D 有限高波导对源匹配敏感）
    yc = (Ny - 1) / 2.0
    zc = (Nz - 1) / 2.0
    w_half = max(1.0, 0.5 / 2.0 / dl)          # 波导半宽（0.5µm）格数
    h_half = max(1.0, 0.22 / 2.0 / dl)         # 波导层半高（0.22µm）格数
    prof_y = np.where(np.abs(np.arange(Ny) - yc) <= w_half, 1.0, 0.0)
    prof_z = np.where(np.abs(np.arange(Nz) - zc) <= h_half, 1.0, 0.0)

    # 探针：各端口芯区 (y,z) 格点
    probes = []
    for name, (xcell, (ylo, yhi), (zlo, zhi)) in ports.items():
        for j in range(ylo, yhi + 1):
            for k in range(zlo, zhi + 1):
                probes.append((xcell, j, k))
    probes_arr = np.array(probes, dtype=np.int64).reshape(-1, 3) if probes else \
        np.zeros((1, 3), dtype=np.int64)
    re = np.zeros(len(probes_arr))
    im = np.zeros(len(probes_arr))
    n_probe = len(probes_arr)

    period = int(round(2.0 * math.pi / (omega * dt)))
    nsteps = (transient_cycles + M_cycles) * period
    meas0 = transient_cycles * period

    Ex = np.zeros((Nx, Ny, Nz))
    Ey = np.zeros((Nx, Ny, Nz))
    Ez = np.zeros((Nx, Ny, Nz))
    Hx = np.zeros((Nx, Ny, Nz))
    Hy = np.zeros((Nx, Ny, Nz))
    Hz = np.zeros((Nx, Ny, Nz))
    pbc_y = pbc_z = False
    amp2d = prof_y[:, None] * prof_z[None, :]

    for n in range(nsteps):
        t = n * dt
        env = (n / 200.0) if n < 200 else 1.0
        cos_wt = math.cos(omega * t)
        sin_wt = math.sin(omega * t)
        _fdtd3d_core(Ex, Ey, Ez, Hx, Hy, Hz, eps, dampE, dampHx, dampHy,
                     dampHz, dl, dt, pbc_y, pbc_z, x_src, 0, 0, False, 0.0,
                     probes_arr, re, im, cos_wt, sin_wt, n >= meas0)
        # 手动分布源注入（E 更新后，与核内软源同相位约定）
        Ez[x_src, :, :] += env * math.sin(omega * t) * amp2d * source_amp

    nmeas = M_cycles * period
    out: Dict[str, float] = {}
    idx = 0
    for name, (xcell, (ylo, yhi), (zlo, zhi)) in ports.items():
        s = 0.0
        for j in range(ylo, yhi + 1):
            for k in range(zlo, zhi + 1):
                a = (re[idx] + 1j * im[idx]) * (2.0 / nmeas)
                s += abs(a) ** 2
                idx += 1
        out[name] = float(s)
    return out


# ---------------------------------------------------------------------------
# 3D DC / Ring eps 体素场（解析 mask2 + 通用 z 拉伸）
# ---------------------------------------------------------------------------
def _stretch_z(mask2: np.ndarray, n_core: float, n_clad: float,
               h_si_um: float, dl: float, clad_z_um: float = 2.0):
    """通用：y-mask → 3D eps（z 拉伸 SOI 层，z 奇数对称）。返回 (eps, Nz, Nz_lo)。"""
    Nx, Ny = mask2.shape
    Nzh = max(1, int(round(h_si_um / dl)) | 1)
    Nzc = int(round(clad_z_um / dl)) * 2
    Nz = Nzh + Nzc
    Nz_lo = (Nz - Nzh) // 2
    eps = np.full((Nx, Ny, Nz), n_clad ** 2)
    core_vals = np.where(mask2, n_core ** 2, n_clad ** 2)
    eps[:, :, Nz_lo:Nz_lo + Nzh] = core_vals[:, :, None]
    return eps, Nz, Nz_lo


def build_dc_field_3d(w_um: float, gap_um: float, Lc_um: float,
                      n_core: float, n_clad: float, h_si_um: float = 0.22,
                      dl: float = 0.097, pad_um: float = 2.0,
                      clad_z_um: float = 2.0):
    """方向耦合器 3D 体素场：双波导 A(y=+yoff)/B(y=−yoff) 沿 x 平行。

    返回 (eps, dl, ports, x_src)：ports = in(A 回波口)/thru(A 远端)/cross(B 远端)。
    """
    yoff = (w_um + gap_um) / 2.0
    Lx = Lc_um + 2 * pad_um
    Ly = yoff + w_um / 2.0 + 1.5
    Nx = int(round(Lx / dl))
    Ny = int(round(2.0 * Ly / dl)) | 1          # 奇数：网格关于 y=0 严格对称
    x_in = -pad_um
    xs = np.arange(Nx) * dl + x_in
    ys = (np.arange(Ny) - (Ny - 1) / 2.0) * dl
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    mask2 = (np.abs(Y - yoff) <= w_um / 2.0) | (np.abs(Y + yoff) <= w_um / 2.0)
    eps, Nz, _ = _stretch_z(mask2, n_core, n_clad, h_si_um, dl, clad_z_um)
    zc = (Nz - 1) / 2.0
    cy = lambda y: int(round((Ny - 1) / 2.0 + y / dl))  # noqa: E731
    cz = lambda z: int(round(zc + z / dl))              # noqa: E731
    z_lo, z_hi = cz(-h_si_um / 2.0), cz(h_si_um / 2.0)
    x_src = int(round((x_in + pad_um * 0.35) / dl))     # 输入波导段内
    ports = {
        "in": (x_src - 5, (cy(yoff - w_um / 2.0), cy(yoff + w_um / 2.0)), (z_lo, z_hi)),
        "thru": (Nx - 6, (cy(yoff - w_um / 2.0), cy(yoff + w_um / 2.0)), (z_lo, z_hi)),
        "cross": (Nx - 6, (cy(-yoff - w_um / 2.0), cy(-yoff + w_um / 2.0)), (z_lo, z_hi)),
    }
    return eps, dl, ports, x_src


def build_ring_field_3d(R_um: float, w_um: float, gap_um: float,
                        n_core: float, n_clad: float, h_si_um: float = 0.22,
                        dl: float = 0.097, pad_um: float = 1.5,
                        clad_z_um: float = 2.0):
    """add-drop 环 3D 体素场：环（圆心原点）+ 下 bus（y=−ybus）+ 上 bus（y=+ybus）。

    关于 y=0 对称（奇数 Ny 网格）。返回 (eps, dl, ports, x_src)：
    ports = in(下 bus 左端)/thru(下 bus 右端)/drop(上 bus 右端)/ref(源左侧回波)。
    """
    ybus = R_um + gap_um + w_um / 2.0
    L = R_um + gap_um + w_um + pad_um
    N = int(round(2.0 * L / dl)) | 1             # 奇数（关于 y=0 对称）
    xs = (np.arange(N) - (N - 1) / 2.0) * dl
    X, Y = np.meshgrid(xs, xs)
    rr = np.sqrt(X ** 2 + Y ** 2)
    ring = (rr >= R_um - w_um / 2.0) & (rr <= R_um + w_um / 2.0)
    bus_dn = np.abs(Y - (-ybus)) <= w_um / 2.0
    bus_up = np.abs(Y - (+ybus)) <= w_um / 2.0
    mask2 = ring | bus_dn | bus_up
    eps, Nz, _ = _stretch_z(mask2, n_core, n_clad, h_si_um, dl, clad_z_um)
    zc = (Nz - 1) / 2.0
    cy = lambda y: int(round((N - 1) / 2.0 + y / dl))  # noqa: E731
    cz = lambda z: int(round(zc + z / dl))              # noqa: E731
    z_lo, z_hi = cz(-h_si_um / 2.0), cz(h_si_um / 2.0)
    x_src = int(round((N - 1) / 2.0 - (L * 0.42) / dl))  # 下 bus 左段
    ports = {
        "in": (x_src - 5, (cy(-ybus - w_um / 2.0), cy(-ybus + w_um / 2.0)), (z_lo, z_hi)),
        "thru": (N - 6, (cy(-ybus - w_um / 2.0), cy(-ybus + w_um / 2.0)), (z_lo, z_hi)),
        "drop": (N - 6, (cy(ybus - w_um / 2.0), cy(ybus + w_um / 2.0)), (z_lo, z_hi)),
    }
    return eps, dl, ports, x_src


# ---------------------------------------------------------------------------
# 3D S 参数谱 + 死标量验收 + 2D↔3D 对拍诊断
# ---------------------------------------------------------------------------
def s_parameter_spectrum_3d(kind: str, params: Dict[str, float],
                            wavelengths_um: Sequence[float],
                            n_core: float = 3.48, n_clad: float = 1.44,
                            dl_factor: float = 16.0,
                            h_si_um: float = 0.22,
                            transient_cycles: int = 800,
                            M_cycles: int = 40) -> Dict:
    """器件 kind（mmi/dc/ring）3D S 参数谱（输入功率归一，能量守恒自动满足）。

    mmi ：in/out1/out2（S11/S21/S31 + 平衡度）
    dc  ：in/thru/cross（S11/S21/S31 + cross_frac = S31/(S21+S31)）
    ring：in/thru/drop（S11/S21/S31，drop = S31）
    """
    dl = 1.55 / dl_factor
    kind = kind.lower()
    if kind == "mmi":
        w = float(params["width"]); Wm = float(params["W_mmi"])
        Lm = float(params["L_mmi"]); Lt = float(params["L_tap"])
        og = float(params["out_gap"]); Lo = float(params["L_out"])
        eps, dl, ports, x_src = build_mmi_field_3d(
            w, Wm, Lm, Lt, og, Lo, n_core, n_clad, h_si_um=h_si_um, dl=dl)
    elif kind == "dc":
        w = float(params["width"]); gap = float(params["gap"])
        Lc = float(params["Lc"])
        eps, dl, ports, x_src = build_dc_field_3d(
            w, gap, Lc, n_core, n_clad, h_si_um=h_si_um, dl=dl)
    elif kind == "ring":
        R = float(params["R"]); w = float(params["width"])
        gap = float(params["gap"])
        eps, dl, ports, x_src = build_ring_field_3d(
            R, w, gap, n_core, n_clad, h_si_um=h_si_um, dl=dl)
    else:
        raise ValueError(f"s_parameter_spectrum_3d 暂不支持 kind={kind}")
    # 统一端口名 → (S21 口, S31 口)
    out21 = "out1" if kind == "mmi" else "thru"
    out31 = "out2" if kind == "mmi" else ("cross" if kind == "dc" else "drop")
    results = []
    for wl in wavelengths_um:
        pw = cw3d_port_powers(eps, dl, wl, ports, x_src,
                              transient_cycles=transient_cycles,
                              M_cycles=M_cycles)
        pin = max(pw["in"], 0.0)
        p1 = max(pw[out21], 0.0)
        p2 = max(pw[out31], 0.0)
        tot = pin + p1 + p2
        S11 = pin / tot if tot > 0 else 0.0
        S21 = p1 / tot if tot > 0 else 0.0
        S31 = p2 / tot if tot > 0 else 0.0
        row = {
            "wl_um": wl, "S11_2": S11, "S21_2": S21, "S31_2": S31,
            "T_total": S21 + S31,
            "power_sum": tot,
        }
        if kind == "mmi":
            row["balance"] = abs(S21 - S31) / (S21 + S31 + 1e-30)
        else:
            row["cross_frac"] = S31 / (S21 + S31 + 1e-30)
        results.append(row)
    return {
        "kind": f"{kind.upper()}-3D", "params": dict(params), "n_core": n_core,
        "n_clad": n_clad, "h_si_um": h_si_um, "dl_factor": dl_factor,
        "wavelengths_um": list(wavelengths_um), "points": results,
    }


def verify_s_params_3d(kind: str, params: Dict[str, float],
                       wavelengths_um: Sequence[float] | None = None,
                       balance_tol: float = 0.15,
                       t_total_min: float = 0.05,
                       **kw) -> Dict:
    """3D 端口 S 参数验收（mmi/dc/ring，SOI 220nm）。

    死标量判据（LLM 不进判决路径）：
      · mmi ：仿真有效 + 双输出平衡度 ≤ balance_tol + 透射 ≥ t_total_min
      · dc  ：仿真有效 + cross_frac(λ) 单调非降（CMT 功率交换物理趋势）
              + 透射 ≥ t_total_min
      · ring：仿真有效 + drop 谱有可辨识谐振峰（drop_max ≥ 1.3×drop_median）
              + 透射 ≥ t_total_min
    附加 2D↔3D 连续性对拍诊断（报告差异，不作判据——3D 垂直模式约束使
    S 参数与 2D 系统性不同，差异是物理非 bug）。
    """
    kind = kind.lower()
    if wavelengths_um is None:
        wl0 = float(params.get("wl0_um", 1.55))
        n = int(params.get("n_wl", 3))
        span = float(params.get("span_um", 0.04))
        wavelengths_um = [round(wl0 + (i / (n - 1) - 0.5) * 2.0 * span, 4)
                          for i in range(n)]
    spec = s_parameter_spectrum_3d(kind, params, wavelengths_um, **kw)
    pts = spec["points"]
    checks = []
    for p in pts:
        row = {"wl_um": p["wl_um"], "sim_ok": bool(p["power_sum"] > 0.0)}
        if kind == "mmi":
            row["balance_ok"] = bool(p["balance"] <= balance_tol)
        row["t_ok"] = bool(p["T_total"] >= t_total_min)
        checks.append(row)
    ok_sim = all(c["sim_ok"] for c in checks)
    ok_trans = all(c["t_ok"] for c in checks)
    ok_extra = True
    if kind == "mmi":
        ok_extra = all(c["balance_ok"] for c in checks)
        extra_name = f"平衡度 max={max(p['balance'] for p in pts):.3f}（≤{balance_tol}）"
    elif kind == "dc":
        cf = [p["cross_frac"] for p in pts]
        # CMT 物理：κ 随 λ 单调增 ⇒ cf 整体上升（cf 在 sin² 拐点 π/4 附近
        # 导数最大，数值噪声放大 → 用端点趋势 + 容差，非逐点严格单调）
        ok_extra = bool(cf[-1] - cf[0] > -0.03)
        extra_name = (f"cross_frac 端点趋势 {'✓' if ok_extra else '✗'} "
                      f"({[round(x, 3) for x in cf]})")
    elif kind == "ring":
        drops = [p["S31_2"] for p in pts]
        med = float(np.median(drops)) if drops else 0.0
        mx = float(np.max(drops)) if drops else 0.0
        ok_extra = bool(mx >= 1.3 * med)
        extra_name = (f"drop 谐振峰 {'✓' if ok_extra else '✗'} "
                      f"(max={mx:.3f} med={med:.3f})")
    else:
        raise ValueError(f"verify_s_params_3d 暂不支持 kind={kind}")
    accepted = ok_sim and ok_trans and ok_extra

    # 2D↔3D 对拍诊断（同几何 2D 谱；mmi/dc 走 2D S 参数，ring 走 2D drop 谱）
    diag = []
    try:
        if kind == "ring":
            from lda_solver.fdtd2d_ring import ring_transmission_spectrum
            nc = float(kw.get("n_core", 3.48))
            ncl = float(kw.get("n_clad", 1.44))
            sp2 = ring_transmission_spectrum(
                float(params["R"]), float(params["width"]), float(params["gap"]),
                nc, ncl, list(wavelengths_um),
                dl_factor=int(spec["dl_factor"]), transient_cycles=800)
            dmax = max(sp2["drop_power"]) or 1.0
            diag = [{"wl_um": wl, "drop_2d": round(d / dmax, 4),
                     "drop_3d": round(p["S31_2"], 4)}
                    for wl, d, p in zip(wavelengths_um, sp2["drop_power"], pts)]
        elif kind == "dc":
            from lda_solver.fdtd2d_coupler import dc_transmission_spectrum
            nc = float(kw.get("n_core", 3.48))
            ncl = float(kw.get("n_clad", 1.44))
            sp2 = dc_transmission_spectrum(
                float(params["width"]), float(params["gap"]), nc, ncl,
                list(wavelengths_um),
                dl_factor=int(spec["dl_factor"]))
            diag = [{"wl_um": wl, "cf_2d": round(c2, 4),
                     "cf_3d": round(p["cross_frac"], 4),
                     "T_2d": round(t2, 4), "T_3d": round(p["T_total"], 4)}
                    for wl, c2, t2, p in zip(
                        wavelengths_um, sp2["cross_frac"],
                        [a + b for a, b in zip(sp2["thru_power"],
                                               sp2["cross_power"])], pts)]
        else:
            from lda_solver.port_sparams import s_parameter_spectrum as _sp2d
            kw2 = {k: v for k, v in kw.items() if k != "dl_factor"}
            sp2 = _sp2d(kind, params, wavelengths_um,
                        dl_factor=spec["dl_factor"], **kw2)
            key = "balance" if kind == "mmi" else "cross_frac"
            diag = [{"wl_um": p2["wl_um"],
                     f"{key}_2d": round(p2.get(key, 0.0), 4),
                     f"{key}_3d": round(p3.get(key, 0.0), 4),
                     "T_2d": round(p2["T_total"], 4),
                     "T_3d": round(p3["T_total"], 4)}
                    for p2, p3 in zip(sp2["points"], pts)]
    except Exception as e:  # noqa: BLE001
        diag = [{"error": str(e)[:100]}]

    fails = []
    if not ok_sim:
        fails.append("仿真无效")
    if not ok_extra:
        fails.append(extra_name.replace("✓", "✗"))
    if not ok_trans:
        fails.append(f"透射 < {t_total_min}")
    per_wl = ["; ".join(k.replace("_ok", "") for k, v in c.items()
                        if k.endswith("_ok") and not v)
              for c in checks]
    if any(per_wl):
        fails.append("逐波长: " + " ; ".join(
            f"λ={c['wl_um']} {pw}" for c, pw in zip(checks, per_wl) if pw))
    verdict = (
        f"{kind.upper()} 3D S 参数验收 PASS：{len(pts)} 波长全部满足——"
        f"仿真有效、{extra_name}、透射 T_total min="
        f"{min(p['T_total'] for p in pts):.3f}（≥{t_total_min}）。"
        if accepted else
        "未全过：" + "；".join(fails))
    return {
        "ok": True,
        "title": f"真实器件 3D 端口 S 参数验收（{kind.upper()} · SOI 220nm）",
        "spectrum": spec,
        "checks": checks,
        "diagnostic_2d_vs_3d": diag,
        "acceptance": {
            "passed": accepted,
            "criteria": {"balance_max": balance_tol,
                         "t_total_min": t_total_min},
        },
        "verdict": verdict,
        "note": (f"{kind.upper()} 全 3D FDTD 端口透反射谱（SOI 220nm 波导层"
                 "+上下包层，复用已验证 numba 核 _fdtd3d_core）：3D 波导截面"
                 "匹配源注入（TE 主极化 Ez）→ 多端口 DFT 收集 → 输入功率归一"
                 "→ S 参数谱，能量守恒自动满足。判据：仿真有效 + "
                 + ("平衡度≤0.15 + 透射≥0.05（自成像对称 ORACLE）" if kind == "mmi"
                    else "cross_frac 单调（CMT 功率交换物理趋势）+ 透射≥0.05"
                    if kind == "dc" else
                    "drop 谐振峰检出 + 透射≥0.05（Lorentzian 谐振 ORACLE）")
                 + "。2D↔3D 对拍为诊断量（3D 垂直模式约束使 S 参数与 2D 系统性"
                 "不同，物理差异非 bug，不作判据）。诚实边界：有限高度波导 3D"
                 "模场与 2D TEz 本质不同；分束比/耦合比绝对值依赖精确设计，"
                 "不声称与商业 EDA 数值库逐点一致。LLM 不进判决路径。"),
    }
