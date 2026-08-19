"""LDA · 多端口耦合器件 FDTD 求解器（标量波动，3D：x,y 截面约束，z 传播）。

D-01：把 1.8 的「真 2D 波导验收范式」扩展为「含耦合的多端口器件」——
方向耦合器（双平行波导）与对称 Y 分支分束器（1×2）。

与 oracle_coupler.py（频域 FDFD 超模法 / 对称性定理）**同一近似层级（标量近似）**，
时域（FDTD）+ 频域/解析（ORACLE）独立求解，交叉校验构成确定性裁判（LLM 不进判决路径）。

方法：仅保留标量纵向场 Ey(x,y,z)，显式蛙跳 + 六面导电海绵吸收；软源（ORACLE 提供
波导 A 基模剖面）注入后，在多个 z 平面上对 A/B 芯区做 DFT 复振幅 → 功率占比曲线，
用于提取耦合长度 / 分束平衡度。

独立性（与 ORACLE 哲学一致）：本求解器是**时域**独立实现，与 ORACLE（频域 FDFD
超模 / 对称性定理）方法不同、代码不同，交叉校验可排除单一实现 bug。不依赖 GPL、
不依赖 Meep/Tidy3D、不进 LLM 判决路径。
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


# ---------------------------------------------------------------------------
# 几何构造
# ---------------------------------------------------------------------------
def build_coupler_field_3d(w_um: float, h_um: float, gap_um: float,
                           n_core: float, n_clad: float, wl_um: float,
                           dl: float = None, clad_um: float = 3.0,
                           Lz_um: float = 16.0):
    """构造方向耦合器 (Nx,Ny,Nz) 折射率平方场（z 均匀）。

    两同尺寸矩形波导（宽 w、高 h）沿 x 并排，中心距 = w_um + gap_um；
    波导 A 在 x<0 侧，波导 B 在 x>0 侧。返回 (eps3, meta)，
    meta 含 mask_a / mask_b（(Nx,Ny) 波导 A/B 芯区布尔掩膜，供功率积分）。
    """
    if dl is None:
        dl = wl_um / 24.0
    Lx = 2.0 * w_um + gap_um + 2.0 * clad_um
    Ly = h_um + 2.0 * clad_um
    Nx = int(round(Lx / dl))
    Ny = int(round(Ly / dl))
    Nz = int(round(Lz_um / dl))
    xs = (np.arange(Nx) - Nx / 2.0) * dl
    ys = (np.arange(Ny) - Ny / 2.0) * dl
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    xa = -(w_um + gap_um) / 2.0          # 波导 A 中心（x<0）
    xb = +(w_um + gap_um) / 2.0          # 波导 B 中心（x>0）
    core_a = (np.abs(X - xa) <= w_um / 2.0) & (np.abs(Y) <= h_um / 2.0)
    core_b = (np.abs(X - xb) <= w_um / 2.0) & (np.abs(Y) <= h_um / 2.0)
    eps2 = np.full((Nx, Ny), n_clad**2, dtype=float)
    eps2[core_a | core_b] = n_core**2
    eps3 = np.broadcast_to(eps2[:, :, None], (Nx, Ny, Nz)).copy()
    meta = {"dl": dl, "n_clad": n_clad, "n_core": n_core,
            "Nx": Nx, "Ny": Ny, "Nz": Nz,
            "mask_a": core_a, "mask_b": core_b,
            "xa_um": xa, "xb_um": xb, "gap_um": gap_um,
            "w_um": w_um, "h_um": h_um, "clad_um": clad_um}
    return eps3, meta


def build_ybranch_field_3d(w_um: float, h_um: float, n_core: float, n_clad: float,
                           wl_um: float, sep_um: float = 1.6,
                           l_in_um: float = 3.0, l_trans_um: float = 6.0,
                           l_out_um: float = 4.0, dl: float = None,
                           clad_um: float = 3.0):
    """构造对称 Y 分支 1×2 分束器 (Nx,Ny,Nz) 折射率平方场。

    沿 z：输入段（单波导 @x=0，长 l_in_um）→ 过渡段（两臂线性分开，长 l_trans_um）
    → 输出段（两臂相距 sep_um，长 l_out_um）。臂 A 在 x<0 侧、臂 B 在 x>0 侧。
    返回 (eps3, meta)，meta 含 mask_a/mask_b（(Nx,Ny) 输出段两臂芯区掩膜）与
    l_out_start_um（输出段起始 z，供功率测量采样）。
    """
    if dl is None:
        dl = wl_um / 24.0
    Lx = 2.0 * w_um + sep_um + 2.0 * clad_um
    Ly = h_um + 2.0 * clad_um
    Lz = l_in_um + l_trans_um + l_out_um
    Nx = int(round(Lx / dl))
    Ny = int(round(Ly / dl))
    Nz = int(round(Lz / dl))
    xs = (np.arange(Nx) - Nx / 2.0) * dl
    ys = (np.arange(Ny) - Ny / 2.0) * dl
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    zs = (np.arange(Nz) + 0.5) * dl          # 每个切片中心 z
    n_in = int(round(l_in_um / dl))
    n_tr = int(round(l_trans_um / dl))
    half_h = h_um / 2.0
    eps3 = np.full((Nx, Ny, Nz), n_clad**2, dtype=float)
    for iz in range(Nz):
        z = zs[iz]
        if z < l_in_um:
            core = (np.abs(X) <= w_um / 2.0) & (np.abs(Y) <= half_h)
        elif z < l_in_um + l_trans_um:
            s = sep_um / 2.0 * (z - l_in_um) / l_trans_um      # 臂半间距线性增长
            core = ((np.abs(X - (-s)) <= w_um / 2.0) |
                    (np.abs(X - (+s)) <= w_um / 2.0)) & (np.abs(Y) <= half_h)
        else:
            s = sep_um / 2.0
            core = ((np.abs(X - (-s)) <= w_um / 2.0) |
                    (np.abs(X - (+s)) <= w_um / 2.0)) & (np.abs(Y) <= half_h)
        eps3[:, :, iz][core] = n_core**2
    # 输出段臂掩膜（用于功率测量）
    s = sep_um / 2.0
    mask_a = (np.abs(X - (-s)) <= w_um / 2.0) & (np.abs(Y) <= half_h)
    mask_b = (np.abs(X - (+s)) <= w_um / 2.0) & (np.abs(Y) <= half_h)
    meta = {"dl": dl, "n_clad": n_clad, "n_core": n_core,
            "Nx": Nx, "Ny": Ny, "Nz": Nz,
            "mask_a": mask_a, "mask_b": mask_b,
            "sep_um": sep_um, "l_in_um": l_in_um,
            "l_trans_um": l_trans_um, "l_out_um": l_out_um,
            "l_out_start_um": l_in_um + l_trans_um,
            "w_um": w_um, "h_um": h_um, "clad_um": clad_um}
    return eps3, meta


# ---------------------------------------------------------------------------
# 多端口功率测量 FDTD
# ---------------------------------------------------------------------------
def solve_port_powers_3d(eps3: np.ndarray, dl: float, wl_um: float,
                         n_clad: float, n_core: float,
                         src_prof: np.ndarray, mask_a: np.ndarray, mask_b: np.ndarray,
                         src_um: float = None, z_sample_um=None,
                         sponge: int = 60, target_exp: float = 12.0,
                         courant: float = 0.95, ramp: int = 400,
                         M_cycles: int = 40, debug: bool = False):
    """标量 3D FDTD：注入波导 A 基模，在多个 z 平面测 A/B 芯区稳态功率占比。

    返回 (fracA, fracB, z_um, pa, pb)：
      fracA/fracB : (nz_s,) 波导 A/B 芯区功率占比（Pa/(Pa+Pb) 归一化，对源强/损耗不敏感）
      z_um        : (nz_s,) 采样面绝对 z 坐标（µm）
      pa/pb       : (nz_s,) 原始功率（DFT 复振幅模方和，可看相对损耗）

    src_um 为源平面绝对 z（缺省取 z 内层 12%）；z_sample_um 为测量面绝对 z 列表
    （缺省在 z 内层 40%~85% 均匀取 9 面）。
    """
    eps3 = np.asarray(eps3, dtype=float)
    Nx, Ny, Nz = eps3.shape

    c = 1.0
    omega = 2.0 * math.pi / wl_um
    dt = dl * courant / math.sqrt(3.0)

    # 六面导电海绵（截面短海绵 + 传播向长海绵，同 fdtd3d_waveguide）
    n0 = n_clad
    sponge_xy = max(8, min(Nx, Ny) // 4)
    sponge_z = max(8, min(sponge, Nz // 4))
    sig_max_xy = target_exp * 3.0 * (n0 ** 2) / (dt * sponge_xy)
    sig_max_z = target_exp * 3.0 * (n0 ** 2) / (dt * sponge_z)
    sx = _sponge_1d(Nx, sponge_xy, sig_max_xy)
    sy = _sponge_1d(Ny, sponge_xy, sig_max_xy)
    sz = _sponge_1d(Nz, sponge_z, sig_max_z)
    sig_cap = max(sig_max_xy, sig_max_z)
    sigma = (sx[:, None, None] + sy[None, :, None] + sz[None, None, :])
    np.clip(sigma, 0.0, sig_cap, out=sigma)
    g = sigma * dt / (2.0 * eps3)

    Nz_int = Nz - 2 * sponge_z
    if src_um is None:
        src_z = sponge_z + max(8, int(0.12 * Nz_int))
    else:
        src_z = int(round(src_um / dl))
        src_z = max(sponge_z + 4, min(src_z, Nz - sponge_z - 4))
    if z_sample_um is None:
        fracs = np.linspace(0.40, 0.85, 9)
        z_samps = [sponge_z + int(f * Nz_int) for f in fracs]
    else:
        z_samps = [max(sponge_z + 4, min(int(round(zu / dl)), Nz - sponge_z - 4))
                   for zu in z_sample_um]
    nz_s = len(z_samps)

    # 源剖面归一化（峰值 1）
    prof = np.asarray(src_prof, dtype=float).reshape(Nx, Ny)
    pmax = float(np.max(np.abs(prof)))
    if pmax > 0:
        prof = prof / pmax
    mask_a = np.asarray(mask_a, dtype=bool).reshape(Nx, Ny)
    mask_b = np.asarray(mask_b, dtype=bool).reshape(Nx, Ny)

    # DFT 窗
    period_steps = int(round(2.0 * math.pi / (omega * dt)))
    transient = max(ramp + 5 * period_steps, 3000)
    M = M_cycles * period_steps
    nsteps = transient + M

    E = np.zeros((Nx, Ny, Nz))
    Eold = np.zeros_like(E)
    reA = np.zeros(nz_s); imA = np.zeros(nz_s)
    reB = np.zeros(nz_s); imB = np.zeros(nz_s)
    for n in range(nsteps):
        t = n * dt
        lap = np.zeros_like(E)
        lap[1:-1, 1:-1, 1:-1] = (
            (E[2:, 1:-1, 1:-1] - 2.0 * E[1:-1, 1:-1, 1:-1] + E[:-2, 1:-1, 1:-1])
            + (E[1:-1, 2:, 1:-1] - 2.0 * E[1:-1, 1:-1, 1:-1] + E[1:-1, :-2, 1:-1])
            + (E[1:-1, 1:-1, 2:] - 2.0 * E[1:-1, 1:-1, 1:-1] + E[1:-1, 1:-1, :-2])
        ) / (dl * dl)
        Enew = (2.0 * E - Eold + (dt * dt) * lap / eps3 + g * (E - Eold)) / (1.0 + g)
        Enew[0, :, :] = 0.0
        Enew[-1, :, :] = 0.0
        Enew[:, 0, :] = 0.0
        Enew[:, -1, :] = 0.0
        Enew[:, :, 0] = 0.0
        Enew[:, :, -1] = 0.0
        env = (n / ramp) if n < ramp else 1.0
        Enew[:, :, src_z] += env * prof * math.sin(omega * t)
        if n >= transient:
            cw = math.cos(omega * t)
            sw = -math.sin(omega * t)
            for i, zi in enumerate(z_samps):
                Es = Enew[:, :, zi]
                sa = float(np.sum(Es * mask_a))
                sb = float(np.sum(Es * mask_b))
                reA[i] += sa * cw; imA[i] += sa * sw
                reB[i] += sb * cw; imB[i] += sb * sw
        Eold = E
        E = Enew

    pa = reA ** 2 + imA ** 2
    pb = reB ** 2 + imB ** 2
    tot = pa + pb
    eps = 1e-30
    fracA = pa / (tot + eps)
    fracB = pb / (tot + eps)
    z_um = np.array([zs * dl for zs in z_samps])
    if debug:
        return fracA, fracB, z_um, pa, pb, src_z * dl
    return fracA, fracB, z_um, pa, pb


def solve_port_powers_3d_torch(eps3: np.ndarray, dl: float, wl_um: float,
                               n_clad: float, n_core: float,
                               src_prof: np.ndarray,
                               mask_a: np.ndarray, mask_b: np.ndarray,
                               src_um: float = None, z_sample_um=None,
                               sponge: int = 60, target_exp: float = 12.0,
                               courant: float = 0.95, ramp: int = 400,
                               M_cycles: int = 40, dtype="float32",
                               debug: bool = False, soft_source: bool = False,
                               transient: int = None):
    """标量 3D FDTD（torch GPU 后端）：注入波导 A 基模，多 z 平面测 A/B 功率占比。

    与 solve_port_powers_3d 同一套时域方法、同一近似层级，仅后端换成 torch；
    ORACLE 交叉校验的独立性在「时域 vs 频域」层面，后端切换不影响独立性。
    GPU 显存需求：网格 cell 数 × ~6 数组 × 4 字节（fp32）；20M cells ≈ 480MB。
    """
    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    torch.manual_seed(0)

    eps3 = np.asarray(eps3, dtype=float)
    Nx, Ny, Nz = eps3.shape
    c = 1.0
    omega = 2.0 * math.pi / wl_um
    dt = dl * courant / math.sqrt(3.0)

    n0 = n_clad
    sponge_xy = max(8, min(Nx, Ny) // 4)
    sponge_z = max(8, min(sponge, Nz // 4))
    sig_max_xy = target_exp * 3.0 * (n0 ** 2) / (dt * sponge_xy)
    sig_max_z = target_exp * 3.0 * (n0 ** 2) / (dt * sponge_z)
    sx = _sponge_1d(Nx, sponge_xy, sig_max_xy)
    sy = _sponge_1d(Ny, sponge_xy, sig_max_xy)
    sz = _sponge_1d(Nz, sponge_z, sig_max_z)
    sig_cap = max(sig_max_xy, sig_max_z)
    sigma = (sx[:, None, None] + sy[None, :, None] + sz[None, None, :])
    np.clip(sigma, 0.0, sig_cap, out=sigma)
    g = sigma * dt / (2.0 * eps3)

    Nz_int = Nz - 2 * sponge_z
    if src_um is None:
        src_z = sponge_z + max(8, int(0.12 * Nz_int))
    else:
        src_z = int(round(src_um / dl))
        src_z = max(sponge_z + 4, min(src_z, Nz - sponge_z - 4))
    if z_sample_um is None:
        fracs = np.linspace(0.40, 0.85, 9)
        z_samps = [sponge_z + int(f * Nz_int) for f in fracs]
    else:
        z_samps = [max(sponge_z + 4, min(int(round(zu / dl)), Nz - sponge_z - 4))
                   for zu in z_sample_um]
    nz_s = len(z_samps)

    prof = np.asarray(src_prof, dtype=float).reshape(Nx, Ny)
    pmax = float(np.max(np.abs(prof)))
    if pmax > 0:
        prof = prof / pmax
    mask_a = np.asarray(mask_a, dtype=bool).reshape(Nx, Ny)
    mask_b = np.asarray(mask_b, dtype=bool).reshape(Nx, Ny)

    # 转 torch（移到 GPU 一次）
    tdtype = torch.float32 if dtype == "float32" else torch.float64
    T = lambda a: torch.from_numpy(np.ascontiguousarray(a)).to(dev, tdtype)
    E = torch.zeros(Nx, Ny, Nz, dtype=tdtype, device=dev)
    Eold = torch.zeros_like(E)
    lap = torch.empty_like(E)
    eps_t = T(eps3)
    g_t = T(g)
    prof_t = T(prof)
    inv_dl2 = float(1.0 / (dl * dl))
    dt2 = float(dt * dt)
    src_plane = torch.zeros(Nx, Ny, Nz, dtype=tdtype, device=dev)
    src_plane[:, :, src_z] = prof_t
    soft = soft_source

    period_steps = int(round(2.0 * math.pi / (omega * dt)))
    if transient is None:
        transient = max(ramp + 5 * period_steps, 3000)
    M = M_cycles * period_steps
    nsteps = transient + M

    # 能流（坡印廷）功率测量：S_z = Im(E*·∂zE)（DFT 复振幅），驻波/反波对净能流无贡献。
    # 每采样面累积复场 A 与 ∂zA（相邻平面差分），避免 |E|² 被驻波污染。
    Ere = torch.zeros(nz_s, Nx, Ny, dtype=tdtype, device=dev)
    Eim = torch.zeros_like(Ere)
    dEre = torch.zeros_like(Ere)
    dEim = torch.zeros_like(Ere)
    s_list = z_samps
    inv2dl = 0.5 / dl

    for n in range(nsteps):
        t = n * dt
        # 3D 拉普拉斯（torch 切片，GPU 并行）
        lap[1:-1, 1:-1, 1:-1] = (
            (E[2:, 1:-1, 1:-1] - 2.0 * E[1:-1, 1:-1, 1:-1] + E[:-2, 1:-1, 1:-1])
            + (E[1:-1, 2:, 1:-1] - 2.0 * E[1:-1, 1:-1, 1:-1] + E[1:-1, :-2, 1:-1])
            + (E[1:-1, 1:-1, 2:] - 2.0 * E[1:-1, 1:-1, 1:-1] + E[1:-1, 1:-1, :-2])
        ) * inv_dl2
        Enew = (2.0 * E - Eold + dt2 * lap / eps_t + g_t * (E - Eold)) / (1.0 + g_t)
        Enew[0, :, :] = 0.0
        Enew[-1, :, :] = 0.0
        Enew[:, 0, :] = 0.0
        Enew[:, -1, :] = 0.0
        Enew[:, :, 0] = 0.0
        Enew[:, :, -1] = 0.0
        env = (n / ramp) if n < ramp else 1.0
        if soft:
            # 软源：电流注入（dt²/ε 归一），不强制源平面场值 → 反波大幅减弱
            Enew += (dt2 / eps_t) * (env * math.sin(omega * t) * src_plane)
        else:
            Enew[:, :, src_z] += (env * math.sin(omega * t)) * prof_t
        if n >= transient:
            cw = math.cos(omega * t)
            sw = -math.sin(omega * t)
            for i, zi in enumerate(s_list):
                E0 = Enew[:, :, zi]
                dE = (Enew[:, :, zi + 1] - Enew[:, :, zi - 1]) * inv2dl
                Ere[i] += E0 * cw; Eim[i] += E0 * sw
                dEre[i] += dE * cw; dEim[i] += dE * sw
        Eold = E
        E = Enew

    if dev == "cuda":
        torch.cuda.synchronize()
    # S_z = Im(A*·∂zA)；A 为 DFT 复振幅（与复场差共轭），故 S_z = Eim·dEre − Ere·dEim（前向为正）
    Sz = Eim * dEre - Ere * dEim                       # (nz_s, Nx, Ny)
    ma_t2 = T(mask_a.astype(np.float32))                # (Nx,Ny)
    mb_t2 = T(mask_b.astype(np.float32))
    pa = (Sz * ma_t2).sum((1, 2)).cpu().numpy()         # (nz_s,)
    pb = (Sz * mb_t2).sum((1, 2)).cpu().numpy()
    tot = pa + pb
    eps = 1e-30
    fracA = pa / (tot + eps)
    fracB = pb / (tot + eps)
    z_um = np.array([zs * dl for zs in z_samps])
    if debug:
        return fracA, fracB, z_um, pa, pb, src_z * dl
    return fracA, fracB, z_um, pa, pb


def solve_supermode_projection_3d_torch(eps3: np.ndarray, dl: float, wl_um: float,
                                        n_clad: float, n_core: float,
                                        src_prof: np.ndarray,
                                        mode_s: np.ndarray, mode_a: np.ndarray,
                                        src_um: float = None, z_sample_um=None,
                                        sponge: int = 60, target_exp: float = 12.0,
                                        courant: float = 0.95, ramp: int = 400,
                                        M_cycles: int = 40, dtype="float32",
                                        soft_source: bool = False,
                                        transient: int = None):
    """标量 3D FDTD（torch GPU）：注入波导 A 基模，多 z 平面做超模投影。

    对每个采样面提取对称超模 φs 与反对称超模 φa 的复投影系数（DFT）：
      O_s(z) = Σ φs·E(z)，O_a(z) = Σ φa·E(z)
    前向传播下 O_s ∝ A_s⁺·e^{iβs z}、O_a ∝ A_a⁺·e^{iβa z}，相位差即超模拍频。
    由调用方用亥姆霍兹递推 / 相位拟合提取 βs、βa → κ = (βs−βa)/2（对反波免疫，
    与 1.8 的投影法同哲学）。ORACLE 仅提供「超模空间形状」作投影基，κ 仍由
    FDTD 传播相位独立给出，不借 ORACLE 定值，不污染判决。

    返回 (Os, Oa, z_um)：Os/Oa 为 (nz_s,) 复数数组，z_um 为采样面绝对 z（µm）。
    """
    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    torch.manual_seed(0)

    eps3 = np.asarray(eps3, dtype=float)
    Nx, Ny, Nz = eps3.shape
    c = 1.0
    omega = 2.0 * math.pi / wl_um
    dt = dl * courant / math.sqrt(3.0)

    n0 = n_clad
    sponge_xy = max(8, min(Nx, Ny) // 4)
    sponge_z = max(8, min(sponge, Nz // 4))
    sig_max_xy = target_exp * 3.0 * (n0 ** 2) / (dt * sponge_xy)
    sig_max_z = target_exp * 3.0 * (n0 ** 2) / (dt * sponge_z)
    sx = _sponge_1d(Nx, sponge_xy, sig_max_xy)
    sy = _sponge_1d(Ny, sponge_xy, sig_max_xy)
    sz = _sponge_1d(Nz, sponge_z, sig_max_z)
    sig_cap = max(sig_max_xy, sig_max_z)
    sigma = (sx[:, None, None] + sy[None, :, None] + sz[None, None, :])
    np.clip(sigma, 0.0, sig_cap, out=sigma)
    g = sigma * dt / (2.0 * eps3)

    Nz_int = Nz - 2 * sponge_z
    if src_um is None:
        src_z = sponge_z + max(8, int(0.12 * Nz_int))
    else:
        src_z = int(round(src_um / dl))
        src_z = max(sponge_z + 4, min(src_z, Nz - sponge_z - 4))
    if z_sample_um is None:
        fracs = np.linspace(0.40, 0.85, 9)
        z_samps = [sponge_z + int(f * Nz_int) for f in fracs]
    else:
        z_samps = [max(sponge_z + 4, min(int(round(zu / dl)), Nz - sponge_z - 4))
                   for zu in z_sample_um]
    nz_s = len(z_samps)

    prof = np.asarray(src_prof, dtype=float).reshape(Nx, Ny)
    pmax = float(np.max(np.abs(prof)))
    if pmax > 0:
        prof = prof / pmax
    phi_s = np.asarray(mode_s, dtype=float).reshape(Nx, Ny)
    phi_a = np.asarray(mode_a, dtype=float).reshape(Nx, Ny)

    tdtype = torch.float32 if dtype == "float32" else torch.float64
    T = lambda a: torch.from_numpy(np.ascontiguousarray(a)).to(dev, tdtype)
    E = torch.zeros(Nx, Ny, Nz, dtype=tdtype, device=dev)
    Eold = torch.zeros_like(E)
    lap = torch.empty_like(E)
    eps_t = T(eps3)
    g_t = T(g)
    prof_t = T(prof)
    ps_t = T(phi_s)
    pa_t = T(phi_a)
    inv_dl2 = float(1.0 / (dl * dl))
    dt2 = float(dt * dt)
    # 软源（电流注入）层：软源反射远小于硬源（硬源强制源平面场值→阻抗不连续→强反波）
    src_plane = torch.zeros(Nx, Ny, Nz, dtype=tdtype, device=dev)
    src_plane[:, :, src_z] = prof_t
    soft = soft_source

    period_steps = int(round(2.0 * math.pi / (omega * dt)))
    if transient is None:
        transient = max(ramp + 5 * period_steps, 3000)
    M = M_cycles * period_steps
    nsteps = transient + M

    # 每采样面累积超模投影复系数（DFT）
    reS = torch.zeros(nz_s, dtype=tdtype, device=dev)
    imS = torch.zeros_like(reS)
    reA = torch.zeros_like(reS)
    imA = torch.zeros_like(reS)
    s_list = z_samps

    for n in range(nsteps):
        t = n * dt
        lap[1:-1, 1:-1, 1:-1] = (
            (E[2:, 1:-1, 1:-1] - 2.0 * E[1:-1, 1:-1, 1:-1] + E[:-2, 1:-1, 1:-1])
            + (E[1:-1, 2:, 1:-1] - 2.0 * E[1:-1, 1:-1, 1:-1] + E[1:-1, :-2, 1:-1])
            + (E[1:-1, 1:-1, 2:] - 2.0 * E[1:-1, 1:-1, 1:-1] + E[1:-1, 1:-1, :-2])
        ) * inv_dl2
        Enew = (2.0 * E - Eold + dt2 * lap / eps_t + g_t * (E - Eold)) / (1.0 + g_t)
        Enew[0, :, :] = 0.0
        Enew[-1, :, :] = 0.0
        Enew[:, 0, :] = 0.0
        Enew[:, -1, :] = 0.0
        Enew[:, :, 0] = 0.0
        Enew[:, :, -1] = 0.0
        env = (n / ramp) if n < ramp else 1.0
        if soft:
            # 软源：电流注入（dt²/ε 归一），不强制源平面场值 → 反波大幅减弱
            Enew += (dt2 / eps_t) * (env * math.sin(omega * t) * src_plane)
        else:
            Enew[:, :, src_z] += (env * math.sin(omega * t)) * prof_t
        if n >= transient:
            cw = math.cos(omega * t)
            sw = -math.sin(omega * t)
            for i, zi in enumerate(s_list):
                Es = Enew[:, :, zi]
                os_ = float(torch.sum(ps_t * Es))
                oa_ = float(torch.sum(pa_t * Es))
                reS[i] += os_ * cw; imS[i] += os_ * sw
                reA[i] += oa_ * cw; imA[i] += oa_ * sw
        Eold = E
        E = Enew

    if dev == "cuda":
        torch.cuda.synchronize()
    Os = (reS + 1j * imS).cpu().numpy()
    Oa = (reA + 1j * imA).cpu().numpy()
    z_um = np.array([zs * dl for zs in z_samps])
    return Os, Oa, z_um


if __name__ == "__main__":
    # 自测：方向耦合器几何 + 功率测量快速冒烟（小网格）
    w, h = 0.5, 0.22
    n_si, n_sio2, wl = 3.48, 1.44, 1.55
    eps3, meta = build_coupler_field_3d(w, h, 0.3, n_si, n_sio2, wl,
                                        dl=wl / 24.0, Lz_um=16.0)
    print("coupler:", meta["Nx"], "x", meta["Ny"], "x", meta["Nz"],
          " maskA=", int(meta["mask_a"].sum()), " maskB=", int(meta["mask_b"].sum()))
    # 高斯源（宽度匹配芯区）注入波导 A，验证流程可跑
    Nx, Ny = meta["Nx"], meta["Ny"]
    xs = (np.arange(Nx) - Nx / 2.0) * meta["dl"]
    ys = (np.arange(Ny) - Ny / 2.0) * meta["dl"]
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    prof = np.exp(-((X - meta["xa_um"]) ** 2 + Y ** 2) / (2.0 * (w / 2.0) ** 2))
    fa, fb, zu, pa, pb = solve_port_powers_3d(
        eps3, meta["dl"], wl, n_sio2, n_si, prof,
        meta["mask_a"], meta["mask_b"], M_cycles=10)
    print("fracA:", np.round(fa, 3))
    print("fracB:", np.round(fb, 3))
    print("z_um:", np.round(zu, 2))
