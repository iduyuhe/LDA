"""LDA · 真 2D 波导 FDTD 求解器（agent 设计结果侧，C 级自主，纯 numpy）。

在 (x,z) 平面做 2D-TE FDTD（标量 E_y 主分量；H_x/H_z 面内）：x 为横向受限方向，
z 为传播方向，y 均匀（⇒ 等效 slab 波导）。条形波导芯 x∈[-w/2,w/2]、沿 z 均匀，
与「闭式 slab ORACLE（_slab_te_neff，x 受限、y/z 均匀，TE 极化）」几何严格一致。

求解范式**复用** lda_solver/fdtd3d.py 已验证的 3D 核心边界与测量手段：
  · 导电海绵吸收边界：dampE = 1/(1+dt·σ/ε)，H 节点 σ 取邻轴均值（0.5·(σ_a+σ_b)），
    sig_max = target_exp·3·n0²/(dt·sponge)，梯度二次剖面 —— 阻抗匹配、无回反射；
  · 软源全程开启（ramp 渐入后恒 1.0，绝不早于 DFT 测量窗关闭）；
  · 整数周期 DFT 测量，双监视点相位差求 β：Δφ = angle(A1) − angle(A2) = β·Δz。
    两监视点共用同一时窗，周期舍入引入的相位漂移在差值中**完全抵消**，对回波稳健。

β 提取无缠绕歧义：取 Δz < λ0/(2·(n_core−n_clad))·2π 上限（≈0.76µm 量级），
使物理允许区间 (n_clad, n_core) 对应 β·Δz 跨度 < 2π，从而唯一确定 2π 缠绕数 m，
**不依赖任何外部猜测值**即可独立定出 neff。

独立性（与 ORACLE 哲学一致）：本求解器是**时域**独立实现，与 ORACLE
（频域 FDFD / 闭式 slab）方法不同、代码不同，交叉校验可排除单一实现 bug。
不依赖 GPL、不进 LLM 判决路径。
"""
from __future__ import annotations

import math
import numpy as np

# 复用已验证的导电海绵剖面与 σ 均值工具（fdtd3d.py 同族，机器优先接口）。
try:
    from fdtd3d import _sponge_1d, _avg_sigma
except ModuleNotFoundError:  # 直接以脚本运行时补路径
    import os as _os
    import sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from fdtd3d import _sponge_1d, _avg_sigma


def build_waveguide_field(w_um: float, n_core: float, n_clad: float, wl_um: float,
                          dl: float = None, clad_x_um: float = 1.5,
                          Lz_um: float = 10.0):
    """构造 (x,z) 条形波导折射率平方场 (Nx_int, Nz_int) 与网格 dl（仅内层，不含海绵）。

    波导芯：x∈[-w/2, w/2]、全 z 为 n_core；其余 n_clad。y 均匀（2D 假设）。
    返回 (eps2_int, dl)。
    """
    if dl is None:
        dl = wl_um / 32.0
    Nx_int = int(round((w_um + 2.0 * clad_x_um) / dl))
    Nz_int = int(round(Lz_um / dl))
    xs = (np.arange(Nx_int) - Nx_int / 2.0) * dl
    eps2_int = np.full((Nx_int, Nz_int), n_clad**2, dtype=float)
    core = np.abs(xs) <= w_um / 2.0
    eps2_int[core, :] = n_core**2
    return eps2_int, dl


def solve_waveguide_neff(eps2_int: np.ndarray, dl: float, wl_um: float,
                         n_clad: float, n_core: float = None,
                         src_frac: float = 0.12, sponge: int = 80,
                         target_exp: float = 12.0, courant: float = 0.95,
                         dz_um: float = 0.6, ramp: int = 400,
                         z1_frac: float = 0.45, debug: bool = False):
    """(x,z) 2D-TE FDTD 求条形波导基模 neff（双监视点 DFT 相位差法）。

    eps2_int : (Nx_int, Nz_int) 内层折射率平方场（x 横向, z 传播）；不含海绵。
    dl       : 网格 µm；wl_um : 真空波长 µm。
    n_clad   : 包层折射率（海绵 sig_max 标度 + 物理区间下界）。
    n_core   : 芯折射率（物理区间上界）；缺省取 eps2 最大平方根。
    dz_um    : 两监视点间距（µm），须 < λ0/(2·(n_core−n_clad))·2π 保证唯一缠绕。
    z1_frac  : 上游监视点 z 位置（占内层比例）。
    返回基模 neff（float）。debug 时额外返回 (neff, beta, m, snr)。
    """
    eps2_int = np.asarray(eps2_int, dtype=float)
    Nx_int, Nz_int = eps2_int.shape
    if n_core is None:
        n_core = float(np.sqrt(eps2_int.max()))

    c = 1.0
    omega = 2.0 * math.pi / wl_um
    k0 = omega / c
    dt = dl * courant / math.sqrt(2.0)          # 2D Courant 上限内（c=1）

    # ---- 全网格（内层 + 四向导电海绵）----
    Nx = Nx_int + 2 * sponge
    Nz = Nz_int + 2 * sponge
    eps2 = np.full((Nx, Nz), n_clad**2, dtype=float)
    # 芯沿 z 贯通（含 z 海绵区）：导模被 z 海绵**渐变吸收**，避免在波导端面产生
    # 法布里-珀罗反射（端面突变=镜面），否则稳态场含多程回波 → β 测量严重失真。
    core_x = eps2_int[:, 0]                       # (Nx_int,) 芯在 x 的剖面（y/z 均匀）
    eps2[sponge:sponge + Nx_int, :] = core_x[:, None]

    n0 = n_clad
    sig_max = target_exp * 3.0 * (n0 ** 2) / (dt * sponge)
    sx = _sponge_1d(Nx, sponge, sig_max)
    sz = _sponge_1d(Nz, sponge, sig_max)
    sigma = np.minimum(sx[:, None] + sz[None, :], sig_max)

    dampE = 1.0 / (1.0 + dt * sigma / eps2)
    # Hx 偏置在 z → 取 z 轴 σ 均值（切片到 Nz-1）；Hz 偏置在 x → 取 x 轴 σ 均值（切片到 Nx-1）
    avg_x = _avg_sigma(sigma, 0, False)
    avg_z = _avg_sigma(sigma, 1, False)
    dampHz = 1.0 / (1.0 + 0.5 * dt * avg_x[:Nx - 1, :])
    dampHx = 1.0 / (1.0 + 0.5 * dt * avg_z[:, :Nz - 1])

    # ---- 源 / 监视器位置 ----
    cx = sponge + Nx_int // 2                     # 芯中心 x
    src_z = sponge + max(8, int(src_frac * Nz_int))
    z1 = sponge + int(z1_frac * Nz_int)
    dz_cells = int(round(dz_um / dl))
    z2 = z1 + dz_cells
    # 安全护栏：监视点须落在内层（远离右端海绵）
    if z2 >= sponge + Nz_int - 4:
        z2 = sponge + Nz_int - 4
        z1 = z2 - dz_cells

    # 软源横向高斯包络：宽度匹配芯区（偶模 TE0，中心峰值）为主激发导模。
    # 关键：源宽须 ≈ 芯半宽，过宽会激发包层辐射 / 宽束，污染 β 测量（非单调）。
    core_mask = eps2_int > (n_clad ** 2 + n_core ** 2) / 2.0
    core_rows = np.where(core_mask.any(axis=1))[0]
    if core_rows.size > 1:
        core_w_cells = core_rows.max() - core_rows.min() + 1
        sigma_cells = max(2.0, core_w_cells / 2.0)
    else:                                       # 均匀介质（无芯）：用适中宽度
        sigma_cells = max(2.0, Nx_int * 0.1)
    xs_c = (np.arange(Nx) - cx) / sigma_cells
    prof = np.exp(-(xs_c ** 2) / 2.0)

    # ---- DFT 窗 ----
    period_steps = int(round(2.0 * math.pi / (omega * dt)))
    transient = max(ramp + 5 * period_steps, 3000)
    M = 80 * period_steps
    nsteps = transient + M
    meas0 = transient

    # ---- 场阵列（Yee）----
    E = np.zeros((Nx, Nz))          # 标量 E_y
    Hx = np.zeros((Nx, Nz - 1))     # 偏置 z
    Hz = np.zeros((Nx - 1, Nz))     # 偏置 x

    re1 = im1 = 0.0
    re2 = im2 = 0.0
    for n in range(nsteps):
        t = n * dt
        # H 更新（半步）
        dE_dz = (E[:, 1:] - E[:, :-1]) / dl
        Hx -= dt * dE_dz
        dE_dx = (E[1:, :] - E[:-1, :]) / dl
        Hz += dt * dE_dx
        Hx *= dampHx
        Hz *= dampHz
        # E 更新（全步，内层节点）
        dHz_dx = (Hz[1:, :] - Hz[:-1, :]) / dl
        dHx_dz = (Hx[:, 1:] - Hx[:, :-1]) / dl
        E[1:Nx - 1, 1:Nz - 1] += (dt / eps2[1:Nx - 1, 1:Nz - 1]) * (
            dHz_dx[0:Nx - 2, 1:Nz - 1] - dHx_dz[1:Nx - 1, 0:Nz - 2])
        E *= dampE
        # 软源（ramp 渐入后恒 1.0，全程开启）
        if n < ramp:
            env = n / ramp
        else:
            env = 1.0
        lo, hi = cx - int(sigma_cells), cx + int(sigma_cells)
        E[lo:hi, src_z] += env * prof[lo:hi] * math.sin(omega * t)
        # DFT 累积（测量窗）
        if n >= meas0:
            v1 = E[cx, z1]
            v2 = E[cx, z2]
            re1 += v1 * math.cos(omega * t)
            im1 -= v1 * math.sin(omega * t)
            re2 += v2 * math.cos(omega * t)
            im2 -= v2 * math.sin(omega * t)

    nmeas = M
    amp1 = (re1 + 1j * im1) * (2.0 / nmeas)
    amp2 = (re2 + 1j * im2) * (2.0 / nmeas)
    a1 = np.angle(amp1)
    a2 = np.angle(amp2)
    dphi = (a1 - a2 + math.pi) % (2.0 * math.pi) - math.pi   # 缠绕到 (-π, π]

    # ---- 由物理区间唯一确定 2π 缠绕数 m ----
    dz = (z2 - z1) * dl
    # neff = (dphi + 2π m) / (k0 dz)，m 使 neff ∈ (n_clad, n_core)
    m_low = math.ceil((n_clad * k0 * dz - dphi) / (2.0 * math.pi) - 1e-9)
    m_high = math.floor((n_core * k0 * dz - dphi) / (2.0 * math.pi) + 1e-9)
    if m_high < m_low:
        # 数值越界兜底：取中点最近整数
        m = int(round(((n_clad + n_core) / 2.0 * k0 * dz - dphi) / (2.0 * math.pi)))
    else:
        m = m_low
    neff = (dphi + 2.0 * math.pi * m) / (k0 * dz)
    beta = neff * k0

    # 信噪比诊断（两监视点振幅一致性）
    snr = min(abs(amp1), abs(amp2)) / (abs(amp1) + abs(amp2) + 1e-30)

    if not (n_clad * 1.001 < neff < n_core * 0.999):
        # 异常兜底：尝试邻位 m
        for mm in (m - 1, m + 1):
            cand = (dphi + 2.0 * math.pi * mm) / (k0 * dz)
            if n_clad * 1.001 < cand < n_core * 0.999:
                neff, m, beta = cand, mm, cand * k0
                break
    if debug:
        return float(neff), float(beta), int(m), float(snr)
    return float(neff)


if __name__ == "__main__":
    # 自测：500nm Si 条形波导 @1550nm（y 均匀 slab）→ 与闭式 slab ORACLE 比对
    w, n_si, n_sio2, wl = 0.5, 3.48, 1.44, 1.55
    import os as _os
    import sys as _sys
    _hdir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                          "..", "lda_harness")
    if _hdir not in _sys.path:
        _sys.path.insert(0, _hdir)
    from oracle_mode import _slab_te_neff
    # 注意：slab ORACLE 的 a 为「半厚」，条形波导全宽 w ⇒ 半厚 a = w/2
    oracle = _slab_te_neff(n_si, n_sio2, w / 2.0, wl)
    eps2_int, dl = build_waveguide_field(w, n_si, n_sio2, wl)
    ne_fdtd, beta, m, snr = solve_waveguide_neff(
        eps2_int, dl, wl, n_clad=n_sio2, n_core=n_si, debug=True)
    rel = abs(ne_fdtd - oracle) / oracle
    print(f"slab ORACLE neff = {oracle:.5f}")
    print(f"FDTD        neff = {ne_fdtd:.5f}  (beta={beta:.4f}, m={m}, snr={snr:.3f})")
    print(f"相对误差        = {rel:.4%}")
