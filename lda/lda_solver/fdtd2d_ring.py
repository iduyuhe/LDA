"""LDA · 环形谐振器 FDTD 仿真核（D-27：2D add-drop 环形，CW 稳态透射谱）。

补上 D-11 标注的「环形 FDTD 求解核」：把环形谱形闭环从纯解析引擎升级为
**真实 FDTD 仿真 + 解析锚对拍**（对齐 D-03 布拉格镜的 FDTD↔TMM 模式）。

物理模型：2D TM（E_z 标量）add-drop 环形谐振器——圆心 O、半径 R、环带
芯宽 w 的圆环，下方 bus（输入→thru）、上方 bus（drop）。下 bus 注入导模，
逐波长 CW 稳态，DFT 测 thru/drop 端口功率 → drop 透射谱出现谐振峰（等间距
= FSR），与解析环形传递函数 FSR=λ²/(n_g·2πR) 对拍。

工程决策（原型实测结论）：
  - **CW 稳态法优于宽带脉冲 FFT**：高 Q 谐振衰减慢，FFT 窗截断泄漏产生
    假峰（原型 n_g,fdtd=6.2 非物理）；逐波长 CW + DFT 信号干净，
    FSR 与解析偏差 ~2%（R=6µm 实测）。
  - 2D 平板波导群折射率接近材料折射率（无垂直限制），解析用 n_g≈n_core
    即可（实测 FSR=18.0 vs 解析 18.31nm）。
  - torch GPU 后端（2D 网格 ~400² 时每波长 ~10-20s）；numpy 兜底小网格。

铁律不变：LLM 不进判决路径；PASS 由死标量比对（FDTD 峰 ↔ 解析 FSR）决定。
"""
from __future__ import annotations

import math
import os
from typing import Dict, List, Optional, Tuple

import numpy as np

_SOLVER_DIR = os.path.dirname(os.path.abspath(__file__))


def _sponge_1d_import():
    import sys
    if _SOLVER_DIR not in sys.path:
        sys.path.insert(0, _SOLVER_DIR)
    from fdtd3d import _sponge_1d
    return _sponge_1d


def build_add_drop_ring_field(R_um: float, w_um: float, gap_um: float,
                              n_core: float, n_clad: float, dl: float,
                              clad_extra_um: float = 3.0):
    """构造 2D add-drop 环形谐振器折射率平方场 (N,N)。

    环形（圆心原点、半径 R、环带宽 w）+ 下 bus（y=−(R+gap+w/2)）+ 上 bus
    （y=+...，drop）。返回 (eps2, dl, N, ybus)。
    """
    L = R_um + gap_um + w_um + clad_extra_um
    N = int(round(2.0 * L / dl))
    xs = (np.arange(N) - N / 2.0) * dl
    X, Y = np.meshgrid(xs, xs)
    rr = np.sqrt(X ** 2 + Y ** 2)
    ring = (rr >= R_um - w_um / 2.0) & (rr <= R_um + w_um / 2.0)
    ybus = R_um + gap_um + w_um / 2.0
    bus_dn = np.abs(Y - (-ybus)) <= w_um / 2.0
    bus_up = np.abs(Y - (+ybus)) <= w_um / 2.0
    eps2 = np.full((N, N), n_clad ** 2)
    eps2[ring | bus_dn | bus_up] = n_core ** 2
    return eps2, dl, N, ybus


def _cell_for_y(N: int, y_um: float, dl: float) -> int:
    """物理坐标 y → 格号（xs=(arange(N)-N/2)*dl）。"""
    return int(round(N / 2.0 + y_um / dl))


def ring_port_power(eps2: np.ndarray, dl: float, wl_um: float,
                    n_core: float, n_clad: float, w_um: float, ybus_um: float,
                    transient_cycles: int = 2000, M_cycles: int = 60,
                    sponge: int = 40, courant: float = 0.95,
                    backend: str = "auto") -> Tuple[float, float]:
    """单波长 CW 稳态：下 bus 注入导模，DFT 测 thru/drop 端口功率。

    backend：auto（有 GPU 用 torch）/ torch / numpy。
    返回 (drop_power, thru_power)（DFT 复振幅模方，相对量）。
    """
    import sys
    if _SOLVER_DIR not in sys.path:
        sys.path.insert(0, _SOLVER_DIR)
    _sponge_1d = _sponge_1d_import()

    N = eps2.shape[0]
    c = 1.0
    omega = 2.0 * math.pi / wl_um
    dt = dl * courant / math.sqrt(2.0)

    n0 = n_clad
    sig_max = 12.0 * 3.0 * (n0 ** 2) / (dt * sponge)
    sx = _sponge_1d(N, sponge, sig_max)
    sy = _sponge_1d(N, sponge, sig_max)
    sigma = np.minimum(sx[:, None] + sy[None, :], sig_max)
    dampE = 1.0 / (1.0 + dt * sigma / eps2)

    y_src_cell = _cell_for_y(N, -ybus_um, dl)
    sig_cells = max(2.0, w_um / 2.0 / dl)
    ys = (np.arange(N) - y_src_cell) / sig_cells
    prof = np.exp(-(ys ** 2) / 2.0)
    x_src = sponge + 6
    x_meas = N - sponge - 6
    y_thru = y_src_cell
    y_drop = _cell_for_y(N, +ybus_um, dl)

    if backend == "auto":
        try:
            import torch
            backend = "torch" if torch.cuda.is_available() else "numpy"
        except Exception:
            backend = "numpy"

    period = int(round(2.0 * math.pi / (omega * dt)))
    nsteps = transient_cycles * period + M_cycles * period
    meas0 = transient_cycles * period
    nmeas = M_cycles * period

    if backend == "torch":
        return _cw_torch(eps2, dl, dt, omega, dampE, prof, x_src,
                         y_thru, y_drop, x_meas, nsteps, meas0, nmeas, N)
    return _cw_numpy(eps2, dl, dt, omega, dampE, prof, x_src,
                     y_thru, y_drop, x_meas, nsteps, meas0, nmeas, N)


def _cw_numpy(eps2, dl, dt, omega, dampE, prof, x_src,
              y_thru, y_drop, x_meas, nsteps, meas0, nmeas, N):
    E = np.zeros((N, N))
    Hx = np.zeros((N, N - 1))
    Hy = np.zeros((N - 1, N))
    inv_dl = 1.0 / dl
    re_thru = im_thru = re_drop = im_drop = 0.0
    for n in range(nsteps):
        t = n * dt
        Hx -= dt * (E[:, 1:] - E[:, :-1]) * inv_dl
        Hy += dt * (E[1:, :] - E[:-1, :]) * inv_dl
        dHy_dx = (Hy[1:, :] - Hy[:-1, :]) * inv_dl
        dHx_dy = (Hx[:, 1:] - Hx[:, :-1]) * inv_dl
        E[1:N - 1, 1:N - 1] += (dt / eps2[1:N - 1, 1:N - 1]) * (
            dHy_dx[0:N - 2, 1:N - 1] - dHx_dy[1:N - 1, 0:N - 2])
        E *= dampE
        env = (n / 200.0) if n < 200 else 1.0
        E[:, x_src] += env * prof * math.sin(omega * t) * 0.1
        if n >= meas0:
            cw = math.cos(omega * t)
            sw = -math.sin(omega * t)
            vt = float(E[y_thru, x_meas])
            vd = float(E[y_drop, x_meas])
            re_thru += vt * cw; im_thru += vt * sw
            re_drop += vd * cw; im_drop += vd * sw
    return (re_drop ** 2 + im_drop ** 2), (re_thru ** 2 + im_thru ** 2)


def _cw_torch(eps2, dl, dt, omega, dampE, prof, x_src,
              y_thru, y_drop, x_meas, nsteps, meas0, nmeas, N):
    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    torch.manual_seed(0)
    tdtype = torch.float32
    T = lambda a: torch.from_numpy(np.ascontiguousarray(a)).to(dev, tdtype)  # noqa: E731
    E = torch.zeros(N, N, dtype=tdtype, device=dev)
    Hx = torch.zeros(N, N - 1, dtype=tdtype, device=dev)
    Hy = torch.zeros(N - 1, N, dtype=tdtype, device=dev)
    eps_t = T(eps2)
    dE_t = T(dampE)
    prof_t = T(prof)
    inv_dl = 1.0 / dl
    dtf = float(dt)
    re_thru = im_thru = re_drop = im_drop = 0.0
    for n in range(nsteps):
        t = n * dt
        Hx -= dtf * (E[:, 1:] - E[:, :-1]) * inv_dl
        Hy += dtf * (E[1:, :] - E[:-1, :]) * inv_dl
        dHy_dx = (Hy[1:, :] - Hy[:-1, :]) * inv_dl
        dHx_dy = (Hx[:, 1:] - Hx[:, :-1]) * inv_dl
        E[1:N - 1, 1:N - 1] += (dtf / eps_t[1:N - 1, 1:N - 1]) * (
            dHy_dx[0:N - 2, 1:N - 1] - dHx_dy[1:N - 1, 0:N - 2])
        E *= dE_t
        env = (n / 200.0) if n < 200 else 1.0
        E[:, x_src] += env * prof_t * math.sin(omega * t) * 0.1
        if n >= meas0:
            cw = math.cos(omega * t)
            sw = -math.sin(omega * t)
            vt = float(E[y_thru, x_meas])
            vd = float(E[y_drop, x_meas])
            re_thru += vt * cw; im_thru += vt * sw
            re_drop += vd * cw; im_drop += vd * sw
    if dev == "cuda":
        torch.cuda.synchronize()
    return (re_drop ** 2 + im_drop ** 2), (re_thru ** 2 + im_thru ** 2)


def ring_transmission_spectrum(R_um: float, w_um: float, gap_um: float,
                               n_core: float, n_clad: float,
                               wavelengths_um: List[float],
                               dl_factor: float = 20.0,
                               transient_cycles: int = 2000,
                               M_cycles: int = 60,
                               backend: str = "auto") -> Dict:
    """逐波长 CW 稳态 → drop/thru 透射功率谱（完整入口）。"""
    dl = 1.55 / dl_factor  # 固定网格（扫描波长不变）
    eps2, dl, N, ybus = build_add_drop_ring_field(
        R_um, w_um, gap_um, n_core, n_clad, dl)
    drop_list, thru_list = [], []
    for wl in wavelengths_um:
        pd, pt = ring_port_power(eps2, dl, wl, n_core, n_clad, w_um, ybus,
                                 transient_cycles=transient_cycles,
                                 M_cycles=M_cycles, backend=backend)
        drop_list.append(pd)
        thru_list.append(pt)
    # 归一化 drop（相对最大）
    dmax = max(drop_list) or 1.0
    return {
        "R_um": R_um, "w_um": w_um, "gap_um": gap_um,
        "n_core": n_core, "n_clad": n_clad,
        "wavelengths_um": wavelengths_um,
        "drop_power": drop_list,
        "thru_power": thru_list,
        "drop_normalized": [d / dmax for d in drop_list],
        "dl_um": dl,
    }


def find_resonances(spec: Dict, min_frac: float = 0.10) -> List[float]:
    """drop 谱谐振峰检测：局部最大 + 强度 ≥ min_frac×max 且 ≥3×邻域中位。

    返回谐振波长列表（升序）。
    """
    wls = list(spec["wavelengths_um"])
    drop = list(spec["drop_power"])
    med = float(np.median(drop))
    mx = float(np.max(drop))
    peaks = []
    for i in range(1, len(drop) - 1):
        if drop[i] > drop[i - 1] and drop[i] > drop[i + 1] \
                and drop[i] >= min_frac * mx and drop[i] >= 3.0 * med:
            # 抛物线插值精确定位
            y0, y1, y2 = drop[i - 1], drop[i], drop[i + 1]
            denom = (y0 - 2.0 * y1 + y2)
            if abs(denom) < 1e-30:
                x_peak = wls[i]
            else:
                delta = 0.5 * (y0 - y2) / denom
                x_peak = wls[i] + delta * (wls[i + 1] - wls[i - 1]) / 2.0
            peaks.append(x_peak)
    peaks.sort()
    return peaks


def fsr_from_resonances(peaks: List[float]) -> float:
    """峰间距中位数 → FSR（µm）。"""
    if len(peaks) < 2:
        return 0.0
    spac = [peaks[i + 1] - peaks[i] for i in range(len(peaks) - 1)]
    return float(np.median(spac))


def ring_fsr_analytic_nm(R_um: float, n_g: float, wl0_um: float) -> float:
    """解析 FSR(nm) = λ²/(n_g·2πR)·1000（与 ring_loop / golden B11 同式）。"""
    return (wl0_um ** 2) / (n_g * 2.0 * math.pi * R_um) * 1000.0


def run_ring_fdtd(R_um: float = 6.0, w_um: float = 0.5, gap_um: float = 0.3,
                  n_core: float = 3.48, n_clad: float = 1.44,
                  wl0_um: float = 1.55, n_points: int = 21,
                  dl_factor: float = 20.0, transient_cycles: int = 2500,
                  M_cycles: int = 80, tol_rel: float = 0.30,
                  backend: str = "auto") -> Dict:
    """D-27 环形 FDTD 谱形验收闭环（完整入口）。

    扫描范围 [wl0−span, wl0+span]（span=2.2×解析 FSR，加密 n_points 点 +
    抛物线插值精确定位谐振峰）。
    验收（死代码判定）：
      1. drop 谱谐振峰 ≥ 3
      2. FSR(FDTD) 与解析 FSR(n_g=n_core) 相对偏差 ≤ tol_rel
      3. thru 谐振处凹陷（可选提示）
    """
    fsr_nm = ring_fsr_analytic_nm(R_um, n_core, wl0_um)
    span_um = 2.2 * fsr_nm / 1000.0
    wavelengths_um = [round(wl0_um + (i / (n_points - 1) - 0.5) * 2.0 * span_um, 4)
                      for i in range(n_points)]
    spec = ring_transmission_spectrum(
        R_um, w_um, gap_um, n_core, n_clad, wavelengths_um,
        dl_factor=dl_factor, transient_cycles=transient_cycles,
        M_cycles=M_cycles, backend=backend)
    peaks = find_resonances(spec)
    fsr_fdtd_um = fsr_from_resonances(peaks)
    fsr_an = fsr_nm / 1000.0
    rel = abs(fsr_fdtd_um - fsr_an) / fsr_an if fsr_an > 0 else float("inf")
    passed = len(peaks) >= 3 and fsr_fdtd_um > 0 and rel <= tol_rel
    return {
        "R_um": R_um, "n_points": n_points,
        "peaks_um": peaks,
        "fsr_fdtd_nm": round(fsr_fdtd_um * 1000.0, 3),
        "fsr_analytic_nm": round(fsr_nm, 3),
        "fsr_rel_dev": round(rel, 4),
        "tol_rel": tol_rel,
        "accepted": passed,
        "spectrum": spec,
        "verdict": _verdict(R_um, peaks, fsr_fdtd_um, fsr_nm, rel, passed),
    }


def _verdict(R_um, peaks, fsr_fdtd_um, fsr_nm, rel, passed) -> str:
    if passed:
        return (f"环形 FDTD 谱形验收 PASS：R={R_um}µm，drop 谱 {len(peaks)} 个谐振峰，"
                f"FSR(FDTD)={fsr_fdtd_um*1000:.2f}nm vs 解析 {fsr_nm:.2f}nm"
                f"（相对 {rel*100:.1f}% ≤ 容差）。真实 FDTD 仿真 ↔ 解析锚一致，"
                f"结果已可由「人」验收。")
    return (f"环形 FDTD 谱形未达标：峰数={len(peaks)}，FSR 偏差 {rel*100:.1f}%"
            f"（峰 {[round(p,4) for p in peaks]}）。请检查 R/gap/扫描范围/transient。")


if __name__ == "__main__":
    import json
    rep = run_ring_fdtd(R_um=6.0, n_points=11, transient_cycles=2000, M_cycles=60)
    print("peaks:", [round(p, 4) for p in rep["peaks_um"]])
    print("FSR_fdtd=%.3fnm  FSR_analytic=%.3fnm  rel=%.3f  accepted=%s"
          % (rep["fsr_fdtd_nm"], rep["fsr_analytic_nm"], rep["fsr_rel_dev"],
             rep["accepted"]))
    print(rep["verdict"])
    print(json.dumps(rep, ensure_ascii=False, indent=2)[:1200])
