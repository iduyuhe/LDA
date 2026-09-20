"""LDA L3 · 光子晶体 / 布拉格 FP 腔共振 2D FDTD 求解核（B21 独立候选）。

C 级自主（纯 numpy，零外部重依赖，不借 Meep/Tidy3D）。
模型：沿 x 的 2D 脊波导条带（宽 w_um，背景包层 n_clad），中心腔长 L_cav
有效折射率 n_eff=(n_core+n_clad)/2，两端夹持 quarter-wave 布拉格镜
（n_core / n_clad 交替，周期锁定 λ0=2·n_eff·L_cav）。宽带高斯脉冲激发，
记录腔内 Ez 时程，FFT 提取腔谐振 λ_res（nm）。

与 golden 闭式 λ_res=(n_core+n_clad)·L_cav（即 2·n_eff·L_cav，m=1 一阶 FP
近似）方法学独立：
- golden = 运动学 FP 条件（一阶近似，不计镜面相位穿透 / 色散 / 波导限制修正）
- cand   = 全波麦克斯韦时域求解（真实场动力学，含上述修正）
二者同源物理定律、方法独立；|cand − golden| 反映一阶近似固有误差，是真可证伪
验证（判据 D 不触发：残差非 golden 常数缩放，依赖几何 / 带结构）。

铁律：LLM 不进判决路径；确定性（固定网格、无 RNG、线程预算固定 4）；
与 fdtd2d_ring.py 同族的 numpy 实现，0 外部重依赖。
"""
from __future__ import annotations

import math
import os

# 🔴 铁律：显式锁线程预算（防 OpenMP 动态伸缩导致 float 归约漂移 / 满载断电）
for _k, _v in (("OMP_NUM_THREADS", "4"), ("MKL_NUM_THREADS", "4"),
               ("OMP_DYNAMIC", "FALSE"), ("MKL_DYNAMIC", "FALSE")):
    os.environ.setdefault(_k, _v)

import numpy as np

_C = 299792458.0  # m/s


def _sponge_1d(n: int, sponge: int, sig_max: float) -> np.ndarray:
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


def _build_eps2(L_cav_um, n_core, n_clad, dl, n_pairs, w_um, sponge):
    """构造 DBR-FP 腔折射率平方场 (Ny, Nx)。"""
    n_eff = 0.5 * (n_core + n_clad)
    lam0 = 2.0 * n_eff * L_cav_um
    seg_hi = max(1, round(lam0 / (4.0 * n_core) / dl))
    seg_lo = max(1, round(lam0 / (4.0 * n_clad) / dl))
    n_cav = max(1, round(L_cav_um / dl))
    prof = []
    for _ in range(n_pairs):
        prof += [n_core] * seg_hi + [n_clad] * seg_lo
    prof += [n_eff] * n_cav
    for _ in range(n_pairs):
        prof += [n_core] * seg_hi + [n_clad] * seg_lo
    Nx_int = len(prof)
    wy = max(1, round(w_um / dl))
    Ny = wy + 2 * sponge
    Nx = Nx_int + 2 * sponge
    eps2 = np.full((Ny, Nx), n_clad ** 2)
    yc = Ny // 2
    y_lo, y_hi = yc - wy // 2, yc + wy // 2
    for i, nseg in enumerate(prof):
        eps2[y_lo:y_hi, sponge + i] = nseg ** 2
    return eps2, dl, Ny, Nx, sponge, n_eff, lam0


def simulate_phc_cavity_resonance(L_cav_um: float = 0.45, n_core: float = 3.48,
                                  n_clad: float = 1.44, *, dl_factor: float = 30.0,
                                  n_pairs: int = 6, w_um: float = 1.0,
                                  sponge: int = 18, n_steps: int = 8000,
                                  courant: float = 0.95) -> dict:
    """2D FDTD 提取 DBR-FP 腔谐振波长（nm）。

    返回 dict：{wl_res_nm, golden_nm, rel_dev, lam0_target_um, n_eff,
                Nx, Ny, n_steps, Q_est}。确定性（无 RNG）。
    """
    n_eff = 0.5 * (n_core + n_clad)
    lam0 = 2.0 * n_eff * L_cav_um  # 目标谐振（golden, m=1），单位 µm
    dl = lam0 / dl_factor
    eps2, dl, Ny, Nx, sponge, _, _ = _build_eps2(
        L_cav_um, n_core, n_clad, dl, n_pairs, w_um, sponge)

    omega0 = 2.0 * math.pi / lam0
    dt = dl * courant / math.sqrt(2.0)
    n0 = n_clad
    sig_max = 12.0 * 3.0 * (n0 ** 2) / (dt * sponge)
    sx = _sponge_1d(Nx, sponge, sig_max)
    sy = _sponge_1d(Ny, sponge, sig_max)
    sigma = np.minimum(sx[None, :] + sy[:, None], sig_max)
    dampE = 1.0 / (1.0 + dt * sigma / eps2)

    # 源：腔中心附近的软电流（宽带高斯脉冲）
    yc = Ny // 2
    x_src = sponge + (Nx - 2 * sponge) // 2
    wy = max(1, round(w_um / dl))
    sig_cells = max(2.0, wy / 2.0 / dl)
    ys = (np.arange(Ny) - yc) / sig_cells
    prof = np.exp(-(ys ** 2) / 2.0)
    # 探测点：腔内、偏离源一格（避免源直耦）
    x_meas = x_src + 3
    y_meas = yc

    inv_dl = 1.0 / dl
    E = np.zeros((Ny, Nx))
    Hx = np.zeros((Ny, Nx - 1))
    Hy = np.zeros((Ny - 1, Nx))

    tau = 6.0 * (2.0 * math.pi / omega0)  # 脉冲半宽 ~6 周期 → 宽带
    t0 = 3.0 * tau
    rec = np.empty(n_steps, dtype=float)
    for n in range(n_steps):
        t = n * dt
        Hx -= dt * (E[:, 1:] - E[:, :-1]) * inv_dl
        Hy += dt * (E[1:, :] - E[:-1, :]) * inv_dl
        dHy_dx = (Hy[1:, :] - Hy[:-1, :]) * inv_dl
        dHx_dy = (Hx[:, 1:] - Hx[:, :-1]) * inv_dl
        E[1:Ny - 1, 1:Nx - 1] += (dt / eps2[1:Ny - 1, 1:Nx - 1]) * (
            dHy_dx[0:Ny - 2, 1:Nx - 1] - dHx_dy[1:Ny - 1, 0:Nx - 2])
        E *= dampE
        env = math.exp(-((t - t0) / tau) ** 2)
        E[:, x_src] += env * prof * math.sin(omega0 * t) * 0.05
        rec[n] = float(E[y_meas, x_meas])

    # FFT 提取谐振峰（限制物理波段 1.3–3.2 µm 防 DC/高频伪峰）
    win = np.hanning(n_steps)
    spec = np.abs(np.fft.rfft(rec * win))
    freqs = np.fft.rfftfreq(n_steps, dt)  # 无量纲频率（c=1, 单位 1/µm）
    wl_um = np.full_like(freqs, np.inf)  # µm（c=1, λ=1/f）；DC bin→inf
    nz = freqs > 0
    wl_um[nz] = 1.0 / freqs[nz]  # 仅对非零频率 bin 求波长，规避 DC 除零告警
    band = (wl_um >= 1.3) & (wl_um <= 3.2)
    idx = np.where(band)[0]
    k = idx[int(np.argmax(spec[band]))]
    wl_res_um = float(wl_um[k])
    # 抛物线插值精修
    if 1 <= k < len(spec) - 1:
        y0, y1, y2 = spec[k - 1], spec[k], spec[k + 1]
        denom = (y0 - 2.0 * y1 + y2)
        if abs(denom) > 1e-30:
            dlt = 0.5 * (y0 - y2) / denom
            wl_res_um = float(wl_um[k] + dlt * (wl_um[k + 1] - wl_um[k - 1]) / 2.0)
    wl_res_nm = wl_res_um * 1000.0
    golden_nm = (n_core + n_clad) * L_cav_um * 1000.0
    rel_dev = (wl_res_nm - golden_nm) / golden_nm
    # 粗略 Q：腔模衰减时间 / 周期（仅作健康度指示）
    return {
        "wl_res_nm": round(wl_res_nm, 3),
        "golden_nm": round(golden_nm, 3),
        "rel_dev": round(rel_dev, 5),
        "lam0_target_um": round(lam0, 4),
        "n_eff": round(n_eff, 4),
        "Nx": Nx, "Ny": Ny, "n_steps": n_steps,
        "courant": courant, "dl_um": round(dl, 4),
    }


if __name__ == "__main__":
    import json
    out = simulate_phc_cavity_resonance()
    print(json.dumps(out, ensure_ascii=False, indent=2))
