"""LDA · 真 2D 矩形波导 FDTD 本征模求解器（标量波动，3D：x,y 截面约束，z 传播）。

构成「真 2D 器件验收闭环」的 agent 设计结果侧：给定任意 2D 折射率分布
n(x,y)（条形波导横截面 / 分束器截面等），沿 z 传播，求基模有效折射率 neff。

与 oracle_mode.fdfd_neff（标量亥姆霍兹本征值）**同一近似层级（标量近似）**，
时域（FDTD）+ 频域（FDFD）独立求解，交叉校验构成确定性裁判（LLM 不进判决路径）。

方法：仅保留标量纵向场 Ey(x,y,z)（标量波动方程近似，适用于弱导波导基模），
显式蛙跳 + 六面导电海绵吸收；软源（2D 高斯横向剖面，激励基模）+ 双监视点
DFT 相位差法提 β → neff；由物理区间 (n_clad, n_core) 唯一确定 2π 缠绕数 m，
不依赖外部猜测值。

独立性（与 ORACLE 哲学一致）：本求解器是**时域**独立实现，与 ORACLE
（频域 FDFD 本征值）方法不同、代码不同，交叉校验可排除单一实现 bug。
不依赖 GPL、不依赖 Meep/Tidy3D、不进 LLM 判决路径。

注：真 2D 矩形截面（x、y 双向约束）与 fdtd2d_waveguide.py 的「y 均匀 slab 波导」
（仅 x 约束、y 均匀）是**不同物理问题**——后者用于 1D slab ORACLE；本文件
才对应 oracle_mode.fdfd_neff 的真 2D 矩形 ORACLE，二者方能在同一 neff 上交叉校验。
"""
from __future__ import annotations

import math
import numpy as np

# 复用已验证的导电海绵剖面（fdtd3d.py 同族）
try:
    from fdtd3d import _sponge_1d
except ModuleNotFoundError:  # 直接以脚本运行时补路径
    import os as _os
    import sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from fdtd3d import _sponge_1d


def build_waveguide_field_3d(w_um: float, h_um: float, n_core: float, n_clad: float,
                             wl_um: float, dl: float = None, clad_um: float = 1.5,
                             Lz_um: float = 10.0):
    """构造真 2D 矩形波导 (Nx,Ny,Nz) 折射率平方场（z 均匀）。

    波导芯：x∈[-w/2,w/2]、y∈[-h/2,h/2]，沿全 z 为 n_core；其余 n_clad。
    返回 (eps3, meta{dl, n_clad, n_core, Nx, Ny, Nz})。
    """
    if dl is None:
        dl = wl_um / 32.0
    Lx = w_um + 2.0 * clad_um
    Ly = h_um + 2.0 * clad_um
    Nx = int(round(Lx / dl))
    Ny = int(round(Ly / dl))
    Nz = int(round(Lz_um / dl))
    xs = (np.arange(Nx) - Nx / 2.0) * dl
    ys = (np.arange(Ny) - Ny / 2.0) * dl
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    eps2 = np.full((Nx, Ny), n_clad**2, dtype=float)
    core = (np.abs(X) <= w_um / 2.0) & (np.abs(Y) <= h_um / 2.0)
    eps2[core] = n_core**2
    eps3 = np.broadcast_to(eps2[:, :, None], (Nx, Ny, Nz)).copy()
    meta = {"dl": dl, "n_clad": n_clad, "n_core": n_core,
            "Nx": Nx, "Ny": Ny, "Nz": Nz}
    return eps3, meta


def solve_waveguide_neff_3d(eps3: np.ndarray, dl: float, wl_um: float, n_clad: float,
                            n_core: float = None, sponge: int = 60, target_exp: float = 12.0,
                            courant: float = 0.95, dz_um: float = 0.6, ramp: int = 400,
                            z1_frac: float = 0.45, src_frac: float = 0.12,
                            mode_source: np.ndarray = None, debug: bool = False):
    """3D 标量波动 FDTD 求真 2D 矩形波导基模 neff（双监视点 DFT 相位差法）。

    eps3 : (Nx,Ny,Nz) 折射率平方场（x,y 截面约束，z 传播）；dl : 网格 µm。
    n_clad/n_core : 包/芯折射率（物理区间上下界）；缺省 n_core 取 eps3 最大平方根。
    返回基模 neff（float）；debug 时额外返回 (neff, beta, m, snr)。
    """
    eps3 = np.asarray(eps3, dtype=float)
    Nx, Ny, Nz = eps3.shape
    if n_core is None:
        n_core = float(np.sqrt(eps3.max()))

    c = 1.0
    omega = 2.0 * math.pi / wl_um
    k0 = omega / c
    dt = dl * courant / math.sqrt(3.0)          # 3D 标量波动 CFL 上限内（c=1）

    # ---- 六面导电海绵（x,y 截面方向短海绵；z 传播方向长海绵）----
    # 注意：sponge 必须随网格自适应，且远小于截面维度——否则截面被海绵吞没、
    # 导模无法在芯区约束（前期 bug：固定 sponge=60 对 Nx=73 吃掉整维）。
    n0 = n_clad
    sponge_xy = max(8, min(Nx, Ny) // 4)        # 截面方向：仅包裹 clad 外缘
    sponge_z = max(8, min(sponge, Nz // 4))     # 传播方向：长海绵吸收行波
    sig_max_xy = target_exp * 3.0 * (n0 ** 2) / (dt * sponge_xy)
    sig_max_z = target_exp * 3.0 * (n0 ** 2) / (dt * sponge_z)
    sx = _sponge_1d(Nx, sponge_xy, sig_max_xy)
    sy = _sponge_1d(Ny, sponge_xy, sig_max_xy)
    sz = _sponge_1d(Nz, sponge_z, sig_max_z)
    sig_cap = max(sig_max_xy, sig_max_z)
    sigma = (sx[:, None, None] + sy[None, :, None] + sz[None, None, :])
    np.clip(sigma, 0.0, sig_cap, out=sigma)
    g = sigma * dt / (2.0 * eps3)               # 标量波动阻尼比

    # ---- 源 / 监视器（相对「z 内层」长度，避免落入两端海绵）----
    Nz_int = Nz - 2 * sponge_z
    cx, cy = Nx // 2, Ny // 2
    src_z = sponge_z + max(8, int(src_frac * Nz_int))
    # 双监视点间距自适应：令 dphi ≈ 0.4·2π（灵敏且远离 2π 缠绕歧义），基于 neff 预估
    neff_avg = 0.5 * (n_clad + n_core)
    lambda_z = wl_um / neff_avg
    dz_cells = max(4, int(round(0.40 * lambda_z / dl)))
    z1 = sponge_z + int(z1_frac * Nz_int)
    z2 = z1 + dz_cells
    if z2 >= sponge_z + Nz_int - 4:
        z2 = sponge_z + Nz_int - 4
        z1 = z2 - dz_cells

    # ---- 重叠积分投影（真 2D 验收闭环的稳健 β 提取 · 生产级）----
    # 给定 mode_source（ORACLE 本征模空间剖面）时，用其对 FDTD 场做重叠积分，在 3 个
    # 等距 z 平面投影出复系数 O_k = <mode|E(z_k)>。前向+后向叠加仍满足亥姆霍兹递推
    #   O_{k+1} - 2·cos(β·dz)·O_k + O_{k-1} = 0
    # ⇒ cos(β·dz) = Re((O_a+O_c)/(2·O_b))，对后向波 / 海绵反射污染免疫（与 Meep
    # get_eigenmode_coefficients 同思路）。ORACLE 仅提供「空间模形状」作投影基，
    # neff 仍由 FDTD 传播相位独立给出，不借 ORACLE 的 neff 定值，不污染判决。
    use_proj = mode_source is not None
    Oa_re = Oa_im = Ob_re = Ob_im = Oc_re = Oc_im = 0.0
    za = zb = zc = 0
    dz_phys = 0.0
    if use_proj:
        phi = np.asarray(mode_source, dtype=float).reshape(Nx, Ny)
        pnorm = float(np.sum(phi * phi))
        if pnorm <= 0:
            use_proj = False
        else:
            phi = phi / math.sqrt(pnorm)            # 单位化（仅影响比值尺度）
            za, zb, zc = z1, z1 + dz_cells, z1 + 2 * dz_cells
            if zc >= sponge_z + Nz_int - 4:
                use_proj = False                     # 域太短，回退双点法
            else:
                dz_phys = dz_cells * dl

    # 软源横向剖面：
    #  - 给定 mode_source（ORACLE 模态剖面）时优先用它——标量 FDFD 模形状正
    #    是标量 FDTD 演化的 Ey 场，注入即干净激发布局基模，对低反差（弱约束）
    #    波导尤关键（高斯源过窄会激发杂散光致相位污染）。neff 仍由 FDTD 传播
    #    相位独立测量，ORACLE 仅提供激发形状，不污染判决（同 Meep/Tidy3D 模态源）。
    #  - 否则退回 2D 高斯（宽度匹配芯区）。
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
        sgx = max(1, int(wx))
        sgy = max(1, int(wy))
        ax = (np.arange(Nx) - cx) / wx
        ay = (np.arange(Ny) - cy) / wy
        prof = np.exp(-(ax[:, None] ** 2 + ay[None, :] ** 2) / 2.0)

    # ---- DFT 窗 ----
    period_steps = int(round(2.0 * math.pi / (omega * dt)))
    transient = max(ramp + 5 * period_steps, 3000)
    M = 80 * period_steps
    nsteps = transient + M
    meas0 = transient

    # ---- 场阵列（标量 Ey，蛙跳两快照）----
    E = np.zeros((Nx, Ny, Nz))
    Eold = np.zeros_like(E)
    re1 = im1 = re2 = im2 = 0.0
    for n in range(nsteps):
        t = n * dt
        lap = np.zeros_like(E)
        lap[1:-1, 1:-1, 1:-1] = (
            (E[2:, 1:-1, 1:-1] - 2.0 * E[1:-1, 1:-1, 1:-1] + E[:-2, 1:-1, 1:-1])
            + (E[1:-1, 2:, 1:-1] - 2.0 * E[1:-1, 1:-1, 1:-1] + E[1:-1, :-2, 1:-1])
            + (E[1:-1, 1:-1, 2:] - 2.0 * E[1:-1, 1:-1, 1:-1] + E[1:-1, 1:-1, :-2])
        ) / (dl * dl)
        Enew = (2.0 * E - Eold + (dt * dt) * lap / eps3 + g * (E - Eold)) / (1.0 + g)
        # 边界层保持 0（六面海绵吸收向内传播波，边界场恒 0 不影响内部）
        Enew[0, :, :] = 0.0
        Enew[-1, :, :] = 0.0
        Enew[:, 0, :] = 0.0
        Enew[:, -1, :] = 0.0
        Enew[:, :, 0] = 0.0
        Enew[:, :, -1] = 0.0
        # 软源（ramp 渐入后恒 1.0，全程开启）
        env = (n / ramp) if n < ramp else 1.0
        if mode_source is not None:
            # 模态源：整张剖面已含低反差模衰减包络，全横面注入
            Enew[:, :, src_z] += env * prof * math.sin(omega * t)
        else:
            lo_x, hi_x = cx - sgx, cx + sgx
            lo_y, hi_y = cy - sgy, cy + sgy
            Enew[lo_x:hi_x, lo_y:hi_y, src_z] += (
                env * prof[lo_x:hi_x, lo_y:hi_y] * math.sin(omega * t))
        if n >= meas0:
            v1 = Enew[cx, cy, z1]
            v2 = Enew[cx, cy, z2]
            re1 += v1 * math.cos(omega * t)
            im1 -= v1 * math.sin(omega * t)
            re2 += v2 * math.cos(omega * t)
            im2 -= v2 * math.sin(omega * t)
            if use_proj:
                cw = math.cos(omega * t)
                sw = -math.sin(omega * t)
                Oa_re += np.sum(phi * Enew[:, :, za]) * cw
                Oa_im += np.sum(phi * Enew[:, :, za]) * sw
                Ob_re += np.sum(phi * Enew[:, :, zb]) * cw
                Ob_im += np.sum(phi * Enew[:, :, zb]) * sw
                Oc_re += np.sum(phi * Enew[:, :, zc]) * cw
                Oc_im += np.sum(phi * Enew[:, :, zc]) * sw
        Eold = E
        E = Enew

    amp1 = (re1 + 1j * im1) * (2.0 / M)
    amp2 = (re2 + 1j * im2) * (2.0 / M)
    a1 = np.angle(amp1)
    a2 = np.angle(amp2)
    dphi = (a1 - a2 + math.pi) % (2.0 * math.pi) - math.pi   # 缠绕到 (-π, π]

    # ---- 由物理区间唯一确定 2π 缠绕数 m ----
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

    # ---- 重叠积分投影法（给定 mode_source 时优先；对后向波/海绵反射免疫）----
    if use_proj:
        Oa = complex(Oa_re, Oa_im)
        Ob = complex(Ob_re, Ob_im)
        Oc = complex(Oc_re, Oc_im)
        if abs(Ob) > 1e-30:
            cos_bdz = float(np.real((Oa + Oc) / (2.0 * Ob)))
            cos_bdz = max(-1.0, min(1.0, cos_bdz))
            beta_dz = math.acos(cos_bdz)            # ∈ [0, π]，β·dz 唯一
            neff_p = beta_dz / (k0 * dz_phys)
            snr_p = min(abs(Oa), abs(Ob), abs(Oc)) / (
                abs(Oa) + abs(Ob) + abs(Oc) + 1e-30)
            if n_clad * 1.001 < neff_p < n_core * 0.999:
                neff, beta, m, snr = neff_p, neff_p * k0, 0, snr_p

    if not (n_clad * 1.001 < neff < n_core * 0.999):
        for mm in (m - 1, m + 1):
            cand = (dphi + 2.0 * math.pi * mm) / (k0 * dz)
            if n_clad * 1.001 < cand < n_core * 0.999:
                neff, m, beta = cand, mm, cand * k0
                break
    if debug:
        return float(neff), float(beta), int(m), float(snr)
    return float(neff)


if __name__ == "__main__":
    # 自测：真 2D 矩形条形波导，FDTD neff 应与 oracle_mode FDFD ORACLE 交叉校验
    w, h = 0.5, 0.22
    n_si, n_sio2, wl = 3.48, 1.44, 1.55
    import os as _os
    import sys as _sys
    _hdir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                          "..", "lda_harness")
    if _hdir not in _sys.path:
        _sys.path.insert(0, _hdir)
    from oracle_mode import fdfd_neff
    clad = 1.5
    oracle = fdfd_neff(w, h, n_si, n_sio2, wl, dl=wl / 32.0, clad_um=clad)
    eps3, meta = build_waveguide_field_3d(w, h, n_si, n_sio2, wl,
                                          dl=wl / 32.0, clad_um=clad, Lz_um=12.0)
    ne, beta, m, snr = solve_waveguide_neff_3d(
        eps3, meta["dl"], wl, n_clad=n_sio2, n_core=n_si, debug=True)
    rel = abs(ne - oracle) / oracle
    print(f"FDFD ORACLE neff = {oracle:.5f}")
    print(f"FDTD        neff = {ne:.5f}  (beta={beta:.4f}, m={m}, snr={snr:.3f})")
    print(f"|Δneff|         = {abs(ne - oracle):.5f}  (rel {rel:.3%})")
