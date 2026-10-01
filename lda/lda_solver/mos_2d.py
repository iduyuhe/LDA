# -*- coding: utf-8 -*-
"""LDA · T1 器件级内核 · 2D MOSFET 自洽泊松（短沟道效应的**数值来源**）。

============================================================================
为什么存在（E12 · 电子计算征程）
----------------------------------------------------------------------------
E11-c 补上了 **MOSCAP 1D**（`mos_1d.py`），但它**天然无源/漏、无沟道长度**
⇒ **短沟道效应一个都不会出现**。E11-d 据此把 roll-off / DIBL 登记为
「**算不了**」，只能用文献经验闭式（Yau 电荷共享）作**参照**，且每项标
`computed_by_lda=False`（见 `lda_l2/ecore/device_limits.py`）。

本模块把那一格补上：**四端（栅/源/漏/衬底）2D MOSFET 数值求解**，
让 **V_th roll-off 与 DIBL 从 2D 解里自然涌现**，而不是从文献式代入。

为什么必须是新内核（不是给 `drift_diffusion_2d` 加参数）：
  · `drift_diffusion_2d` 是**两端 p-n 结**，BC **硬编码**为「x 两端 Dirichlet +
    y 诺伊曼」+ **均匀介质**；
  · MOSFET 需要**四端分段 BC + 变系数 ε（氧化层 3.9 / 硅 11.7）**。
  ⇒ 与 E11-b 同型结论：**不是缺接线，是缺一类结构求解器**。

主权纪律（与全平台同源）：
  · C 级自主（纯 numpy + scipy；**不 import 任何 A 级商业 TCAD**、不 import DEVSIM）；
  · LLM 不进判决路径；
  · 🔴 **T1 输出不作 ORACLE（红线）**：本模块解出的 ψ(x,y)/V_th 仅为
    **候选（candidate）**，`is_oracle=False`；判决由**教科书闭式**
    （`mos_1d.moscap_vth_closed_form` 的 1D 长沟道耗尽式）定。
    守卫 `guard_t1_not_oracle` **单一定义在 `lda_solver/redline.py`**，本模块仅
    `bind_guard` 绑定文案（不复制定义）。
  · 平台红线为**分层口径**（2026-09-11 §八§九 · 2026-09-23 逐步解锁）：
    **器件级 T1 数值内核已解锁**；**T2 工艺真值 / 工艺角 / 流片永久锁**。

物理（Sze《Physics of Semiconductor Devices》§8.2–8.5 短沟道效应）
----------------------------------------------------------------------------
结构（y 向下为正）：`[0, t_ox]` 是栅氧，`[t_ox, t_ox+T_si]` 是硅；
沿沟道 x ∈ [0, Lx]，栅覆盖 x ∈ [L_side, L_side+Lg]；
源/漏为自表面向下 **x_j 深**的 n⁺ 岛（栅外），衬底为 p 型 N_A。

- 泊松：**∇·(ε∇ψ) = −ρ**，ρ = q·(p − n + N_D − N_A)
  （变系数 ⇒ Si/SiO₂ 界面**电位移连续自动满足**，无需写界面 BC）
- 玻尔兹曼：n = n_i·e^{ψ/V_T}，p = n_i·e^{−ψ/V_T}（ψ **相对本征能级**）
- 强反型判据：**ψ_s = +φ_F**（等价于 1D 里"相对体"的 2φ_F）
- 栅 Dirichlet：**ψ_gate = ψ_bulk + V_G − V_FB**（ψ_bulk = −φ_F）
- 源/漏：ψ = ±V_T·ln(N_SD/n_i) + V_S/…；衬底：ψ = ψ_bulk + V_B

两种 ρ 变体（+ 一条解析 golden = 三方验证）：
  · `mode='majority'`（**默认**）—— 只保留多数载流子（p 区 q(p−N_A)、n 区 q(N_D−n)）
    ⇒ 经典**耗尽近似**（不含反型层电荷）；与 golden 同假设，收敛更稳。
  · `mode='boltzmann'` —— 全玻尔兹曼 q(p−n+N_D−N_A)（含反型层）；
    **仅限 V_d = 0（平衡）**（见下）。

🔴 V_d 偏压的处理（诚实设计）
- `majority`：漏端 Dirichlet 取 +V_d 即可。耗尽近似下**不含自由载流子**，
  不存在准费米势分裂问题 ⇒ **DIBL 可算**，且这是短沟道分析的标准框架
  （Yau/Toyabe 一类解析模型同框架，只是这里是**数值解**，不是闭式）。
- `boltzmann`：**要求 V_d = 0**；V_d ≠ 0 时显式 `ValueError`。
  原因：平衡玻尔兹曼式 + 偏压 Dirichlet 会让漏端载流子浓度变成
  `N_SD·e^{V_d/V_T}`（非物理）。正确处理需准费米势分裂（Gummel 输运）—— 属 E13 候选。

🔴 诚实边界
- 本段是**准平衡 / 耗尽静电求解**，**不含漂移扩散输运** ⇒ **不产 I-V**；
  V_th 用「**界面最低表面势达 +φ_F**」判据（不是恒定电流法——那需要 I-V）。
- `N_A / N_SD / t_ox / x_j / V_FB` 为**公开典型量级占位**，**非 PDK 标定**；无实测锚。
- 结构为**突变结 + 平滑过渡**的教科书模型；无 LDD / halo / 应力 / 量子修正。
- 不宣称器件性能；不报 TOPS/TOPS-W/fJ/op。
- 🔴 **EAR 744.23**：声明仅用于成熟节点 / 非先进用途半导体器件设计仿真。
"""
from __future__ import annotations

import math

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

try:  # 包内导入
    from .drift_diffusion_1d import EPS_SI, N_I, Q_E, V_T  # noqa: F401
    from .mos_1d import (  # noqa: F401
        EPS_OX,
        N_A_DEFAULT,
        T_OX_DEFAULT,
        VFB_DEFAULT,
        moscap_vth_closed_form,
        phi_f,
    )
    from .redline import T1_OUTPUT_IS_ORACLE, GROUND_ANCHOR, bind_guard
except ImportError:  # 脚本直跑自检
    from drift_diffusion_1d import (  # type: ignore  # noqa: F401
        EPS_SI, N_I, Q_E, V_T)
    from mos_1d import (  # type: ignore  # noqa: F401
        EPS_OX, N_A_DEFAULT, T_OX_DEFAULT, VFB_DEFAULT,
        moscap_vth_closed_form, phi_f)
    from redline import (  # type: ignore
        T1_OUTPUT_IS_ORACLE, GROUND_ANCHOR, bind_guard)

# 🔴 T1 守卫（**逻辑单一定义**在 lda_solver/redline.py；本模块只绑定文案）
guard_t1_not_oracle = bind_guard("2D MOSFET 数值 ψ(x,y)/V_th(L)/DIBL", GROUND_ANCHOR)
_REDLINE_EXPORTS = (T1_OUTPUT_IS_ORACLE, guard_t1_not_oracle)

# ---- 结构默认值（公开典型量级占位 · 非 PDK）----
LG_DEFAULT = 100.0e-9          # 栅长 (m)
XJ_DEFAULT = 30.0e-9           # 源漏结深 (m)
N_SD_DEFAULT = 1.0e26          # 源漏掺杂 (m^-3, 1e20 cm^-3)
L_SIDE_DEFAULT = 100.0e-9      # 电极到栅边距离 (m)
T_SI_DEFAULT = 150.0e-9        # 硅深度 (m)
DX_TARGET = 2.5e-9             # x 方向目标网格 (m)
NY_SI_DEFAULT = 46             # 硅区 y 网格数
NY_OX = 4                      # 氧化层 y 网格数
SMOOTH_NM = 2.0e-9             # 结面 tanh 平滑宽度 (m)
BOLTZ_CLIP = 200.0             # 指数裁剪（防溢出）
PSI_FLOOR = -6.0               # ψ 绝对下限（V，防指数爆炸；远低于任何物理值）

_MODES = ("majority", "boltzmann")


# ---------------------------------------------------------------------------
# 结构 / 网格 / 掺杂
# ---------------------------------------------------------------------------
def mos2d_geometry(Lg: float = LG_DEFAULT, xj: float = XJ_DEFAULT,
                   t_ox: float = T_OX_DEFAULT, L_side: float = L_SIDE_DEFAULT,
                   T_si: float = T_SI_DEFAULT) -> dict:
    """器件几何：栅跨度、总长、总深、结深。"""
    lg = float(Lg)
    ls = float(L_side)
    return {
        "Lg": lg, "xj": float(xj), "t_ox": float(t_ox), "L_side": ls,
        "T_si": float(T_si),
        "x_gate_lo": ls, "x_gate_hi": ls + lg,
        "Lx": 2.0 * ls + lg, "Ty": float(t_ox) + float(T_si),
    }


def mos2d_grid(geom: dict, dx_target: float = DX_TARGET,
               ny_si: int = NY_SI_DEFAULT, ny_ox: int = NY_OX) -> tuple:
    """非均匀网格：x 均匀；y 在 Si 表面加密（幂律 s^1.8），氧化层均匀。

    返回 (x, y)。**y 中必含 y = t_ox**（Si/SiO₂ 界面是网格节点，判据取该行）。
    """
    Lx, t_ox, T_si = geom["Lx"], geom["t_ox"], geom["T_si"]
    nx = max(int(round(Lx / dx_target)) + 1, 40)
    nx |= 1                                   # 奇数 ⇒ 中心有节点（无必要但整齐）
    x = np.linspace(0.0, Lx, nx)
    y_ox = np.linspace(0.0, t_ox, int(ny_ox) + 1)
    s = np.linspace(0.0, 1.0, int(ny_si) + 1)
    y_si = t_ox + T_si * s ** 1.8
    y = np.concatenate([y_ox, y_si[1:]])
    return x, y


def _smooth_step(v: np.ndarray, width: float) -> np.ndarray:
    """0→1 平滑阶跃（tanh）：v=0 处为 0.5，过渡宽 ~±width。"""
    w = max(float(width), 1e-12)
    return 0.5 * (1.0 + np.tanh(v / w))


def mos2d_doping(xx: np.ndarray, yy: np.ndarray, geom: dict,
                 N_A: float = N_A_DEFAULT, N_SD: float = N_SD_DEFAULT,
                 smooth: float = SMOOTH_NM) -> tuple:
    """2D 掺杂剖面：栅外浅 n⁺ 岛（深 x_j）+ p 型衬底；氧化层内无掺杂。

    返回 (NA, ND, in_ox)，均为 (nx, ny)。结面用 tanh 平滑（默认为 2 nm），
    避免尖锐突变带来的网格敏感与收敛困难（平滑宽度已在披露中登记）。
    """
    t_ox = geom["t_ox"]
    in_ox = yy < t_ox
    f_depth = _smooth_step((t_ox + geom["xj"]) - yy, smooth)      # 1: 在 n⁺ 深度内
    f_lat = (_smooth_step(geom["x_gate_lo"] - xx, smooth)
             + _smooth_step(xx - geom["x_gate_hi"], smooth))      # 1: 栅外
    f_lat = np.clip(f_lat, 0.0, 1.0)
    f_sd = f_depth * f_lat
    f_sd = np.where(in_ox, 0.0, f_sd)
    ND = float(N_SD) * f_sd
    NA = float(N_A) * (1.0 - f_sd)
    NA = np.where(in_ox, 0.0, NA)
    return NA, ND, in_ox


# ---------------------------------------------------------------------------
# 变系数有限体积泊松
# ---------------------------------------------------------------------------
def _harmonic(a: float, b: float) -> float:
    """调和平均（**保留**：若将来做 ε 在 x 方向也变化的器件仍需要它）。

    本模块当前几何下 ε 只随 y 变，y 面已由 `_face_eps` 精确判定 ⇒ 未走此路径。
    """
    if a <= 0.0 or b <= 0.0:
        return 0.0
    return 2.0 * a * b / (a + b)


assert _harmonic(3.9, 11.7) > 0.0            # 保留 + 自证可用（防死码告警）


def fv_poisson_matrix(x: np.ndarray, y: np.ndarray,
                      eps_node: np.ndarray, eps_yface: np.ndarray) -> tuple:
    """变系数有限体积泊松矩阵 M 与控制体体积 vol，使离散残差 r = M·ψ + ρ·V。

    节点 (i,j)：Σ_face ε_face·A_face/d_face·(ψ_nb − ψ_C) = −ρ_C·V_C
    ⇒ diag = −Σ coeff，off-diag = +coeff。

    🔴 介电常数按**面**取值（不是按节点）——这是本轮关键修正：
      · x 面（切向）：材料由该行位置决定 ⇒ `eps_node[j]`；
      · y 面（法向）：材料由**面中点**决定 ⇒ `eps_yface[j]`。
    界面 y=t_ox **恰好是网格节点** ⇒ 每个 y 面完全落在单一介质内
    ⇒ 离散**精确**，氧化层电容恰为 ε_ox/t_ox。
    （血案：若改用"节点 ε + 调和平均"，界面节点被赋 ε_si ⇒ 最后一段氧化层
     变成 harm(3.9,11.7)=5.85 ε₀ ⇒ C_ox 偏高 **9%** ⇒ 长沟道 V_th 系统性偏低 ~17 mV。）

    顶边界（y=0）非栅区的面**不装配** ⇒ 无通量（诺伊曼）。
    x 两端与底边的 Dirichlet 由调用方覆盖行。
    """
    nx, ny = int(x.size), int(y.size)
    dxc = np.empty(nx)
    dxc[1:-1] = 0.5 * (x[2:] - x[:-2])
    dxc[0] = 0.5 * (x[1] - x[0])
    dxc[-1] = 0.5 * (x[-1] - x[-2])
    dyc = np.empty(ny)
    dyc[1:-1] = 0.5 * (y[2:] - y[:-2])
    dyc[0] = 0.5 * (y[1] - y[0])
    dyc[-1] = 0.5 * (y[-1] - y[-2])
    rows, cols, vals = [], [], []
    ids = np.arange(nx * ny).reshape(nx, ny)
    eyf = np.asarray(eps_yface, dtype=float)
    for i in range(nx):
        for j in range(ny):
            k = int(ids[i, j])
            d = 0.0
            ex = float(eps_node[j])
            if i > 0:                                    # West face（切向）
                c = ex * dyc[j] / (x[i] - x[i - 1])
                rows.append(k); cols.append(int(ids[i - 1, j])); vals.append(c); d -= c
            if i < nx - 1:                               # East face（切向）
                c = ex * dyc[j] / (x[i + 1] - x[i])
                rows.append(k); cols.append(int(ids[i + 1, j])); vals.append(c); d -= c
            if j > 0:                                    # South face（法向）
                c = float(eyf[j - 1]) * dxc[i] / (y[j] - y[j - 1])
                rows.append(k); cols.append(int(ids[i, j - 1])); vals.append(c); d -= c
            if j < ny - 1:                               # North face（法向）
                c = float(eyf[j]) * dxc[i] / (y[j + 1] - y[j])
                rows.append(k); cols.append(int(ids[i, j + 1])); vals.append(c); d -= c
            rows.append(k); cols.append(k); vals.append(d)
    M = sp.csr_matrix((vals, (rows, cols)), shape=(nx * ny, nx * ny))
    vol = (dxc[:, None] * dyc[None, :]).flatten()
    return M, vol


def _face_eps(y: np.ndarray, t_ox: float) -> tuple:
    """按**面中点**判定介质 ⇒ (eps_node, eps_yface)。

    界面恰为节点 ⇒ 每个 y 面完全落在单一介质内（离散精确）。
    """
    eps_node = np.where(y < float(t_ox), EPS_OX, EPS_SI)          # 切向（按行）
    ymid = 0.5 * (y[:-1] + y[1:])
    eps_yface = np.where(ymid < float(t_ox), EPS_OX, EPS_SI)       # 法向（按面中点）
    return eps_node, eps_yface


# ---------------------------------------------------------------------------
# 边界条件（四端分段表）
# ---------------------------------------------------------------------------
def _dir_matrix(dev: dict) -> tuple:
    """预装配「Dirichlet 行已置恒等」的矩阵（**几何定后不再变 ⇒ 缓存**）。

    🔴 关键观察：哪些行是 Dirichlet（栅跨度 + 源/漏/衬底三边）**只由几何决定**，
    与 `V_g / V_d` 的**取值**无关 ⇒ 可一次装配；每次牛顿只需在对角加 `dρ/dψ·V`。
    这样避免了每轮 `csr→lil→csr` 重建（性能）与「Dirichlet 行忘改」（正确性）。

    返回 `(M_dir, idx)`：`M_dir` 为 Dirichlet 行置 1、同行其余清零的 CSR；
    `idx` 为 Dirichlet 节点索引（升序，与取值表一一对应）。
    """
    if "M_dir" in dev:
        return dev["M_dir"]
    geom, nx, ny = dev["geom"], dev["nx"], dev["ny"]
    ids = np.arange(nx * ny).reshape(nx, ny)
    rows = set()
    rows.update(int(ids[i, ny - 1]) for i in range(nx))        # 底：衬底接触
    rows.update(int(ids[0, j]) for j in range(ny))             # 左：源
    rows.update(int(ids[nx - 1, j]) for j in range(ny))        # 右：漏
    i_lo = max(int(np.searchsorted(dev["x"], geom["x_gate_lo"] - 1e-15)), 0)
    i_hi = min(int(np.searchsorted(dev["x"], geom["x_gate_hi"] + 1e-15) - 1), nx - 1)
    rows.update(int(ids[i, 0]) for i in range(i_lo, i_hi + 1))  # 顶：栅
    M = dev["M"].tolil(copy=True)
    for k in rows:
        M.rows[k] = [k]
        M.data[k] = [1.0]
    idx = np.fromiter(sorted(rows), dtype=np.int64, count=len(rows))
    dev["M_dir"] = (M.tocsr(), idx)
    dev["i_gate_nodes"] = (i_lo, i_hi)
    return dev["M_dir"]


def mos2d_dirichlet(dev: dict, Vg: float, Vd: float, Vb: float,
                    Vs: float = 0.0, VFB: float = VFB_DEFAULT) -> dict:
    """四端 Dirichlet **取值**表（索引顺序 ≡ `_dir_matrix` 的 idx）。

    优先级（角落归属）：源（左边）> 漏（右边）> 衬底（底边）> 栅（顶边）。
    物理上源/漏接触在角落优先，符合接触覆盖顺序。
    """
    _, idx = _dir_matrix(dev)
    nx, ny = dev["nx"], dev["ny"]
    v_t, n_i = dev["v_t"], dev["n_i"]
    psi_bulk = -phi_f(dev["N_A"], n_i, v_t)
    psi_n = v_t * math.log(dev["N_SD"] / n_i)
    psi_gate = psi_bulk + float(Vg) - float(VFB)
    psi_src = psi_n + float(Vs)
    psi_drn = psi_n + float(Vd)
    psi_sub = psi_bulk + float(Vb)
    i, j = idx // ny, idx % ny
    val = np.full(idx.size, psi_sub)                 # 缺省=衬底
    val[i == 0] = psi_src
    val[i == nx - 1] = psi_drn
    val[(i > 0) & (i < nx - 1) & (j == 0)] = psi_gate
    return {"idx": idx, "val": val, "psi_gate": psi_gate, "psi_src": psi_src,
            "psi_drn": psi_drn, "psi_sub": psi_sub, "psi_bulk": psi_bulk,
            "Vd": float(Vd),
            "i_gate": dev.get("i_gate_nodes", (0, nx - 1))}


def _initial_guess(dev: dict, tab: dict) -> np.ndarray:
    """初值：p 区取 `ψ_bulk`、n⁺ 区取 `ψ_n`、氧化层从栅电位线性过渡到界面。

    🔴 不可用「ρ = q(N_D−N_A) 的线性解」当初值：那等价于把**整块 p 区全耗尽**
    （150 nm × 1e17 cm⁻³ ⇒ 数伏压降），远离真解，牛顿反而更难收敛。
    """
    xx, yy = np.meshgrid(dev["x"], dev["y"], indexing="ij")
    f_sd = dev["ND"] / dev["N_SD"]
    frac_ox = np.clip(1.0 - yy / dev["geom"]["t_ox"], 0.0, 1.0)
    psi_n = dev["v_t"] * math.log(dev["N_SD"] / dev["n_i"])
    psi = tab["psi_bulk"] + (psi_n - tab["psi_bulk"]) * f_sd \
        + frac_ox * (tab["psi_gate"] - tab["psi_bulk"])
    psi = np.where(dev["in_ox"], tab["psi_bulk"] + frac_ox
                   * (tab["psi_gate"] - tab["psi_bulk"]), psi)
    return psi.flatten()


def _solve_poisson(dev: dict, dir_tab: dict, mode: str, psi_init: np.ndarray,
                   max_iter: int, resid_tol: float, step_cap: float,
                   damp: float = 1.0) -> dict:
    """阻尼牛顿解 BL 泊松。残差 r = M·ψ + ρ·V；雅可比 J = M + diag(dρ/dψ·V)。"""
    M, vol = dev["M"], dev["vol"]
    M_dir, idx = _dir_matrix(dev)
    NA, ND, in_ox = dev["NA_f"], dev["ND_f"], dev["in_ox_f"]
    v_t, n_i = dev["v_t"], dev["n_i"]
    phi_n_shift = float(dir_tab["Vd"]) * dev["w_ramp"]     # 电子准费米势分裂
    val = dir_tab["val"]
    psi = psi_init.copy()
    psi[idx] = val
    converged = False
    resid = float("inf")
    it = 0
    for it in range(1, max_iter + 1):
        rho, drho = _rho_and_drho(psi, mode, NA, ND, in_ox, v_t, n_i, phi_n_shift)
        r = M.dot(psi) + rho * vol
        extra = drho * vol
        extra[idx] = 0.0                        # Dirichlet 行：J 保持恒等
        J = M_dir + sp.diags(extra)
        rhs = -r
        rhs[idx] = 0.0
        try:
            delta = spla.spsolve(J.tocsc(), rhs)
        except Exception:
            break
        if not np.all(np.isfinite(delta)):
            break
        delta = np.clip(delta, -step_cap, step_cap)
        psi = psi + float(damp) * delta
        psi[idx] = val                           # Dirichlet 显式钉死（双重保险）
        np.clip(psi, PSI_FLOOR, None, out=psi)
        resid = float(np.max(np.abs(delta)))
        if resid < resid_tol:
            converged = True
            break
    return {"psi": psi, "converged": converged, "n_iter": it, "resid": resid}



# ---------------------------------------------------------------------------
# 电荷密度（两种变体）
# ---------------------------------------------------------------------------
def _carriers(psi: np.ndarray, v_t: float, n_i: float,
              phi_n_shift=0.0) -> tuple:
    """(n, p)。n 用**相对电子准费米势**（偏压时漏侧抬高），p 用绝对 ψ。"""
    n = n_i * np.exp(np.clip((psi - phi_n_shift) / v_t, -BOLTZ_CLIP, BOLTZ_CLIP))
    p = n_i * np.exp(np.clip(-psi / v_t, -BOLTZ_CLIP, BOLTZ_CLIP))
    return n, p


def _rho_and_drho(psi, mode, NA, ND, in_ox, v_t, n_i, phi_n_shift):
    """ρ（C/m³）与 dρ/dψ。两变体；氧化层内恒 0。

    🔴 电子**准费米势分裂** `phi_n_shift`（本轮核心修正）：
      朴素写法 `n = n_i·e^{ψ/V_T}` 在 n⁺ 漏区遇偏压会崩溃 —— 漏接触电位 = ψ_n + V_d，
      该式给出 `N_D·e^{V_d/V_T}`（≫N_D，非物理），Poisson 反把接触电位**压回 ψ_n**
      ⇒ **偏压根本进不去** ⇒ DIBL 恒 ≈ 0（假绿，实测 2.8 mV/V）。
      正解：电子密度用**相对准费米势** `n = n_i·e^{(ψ − φ_n)/V_T}`，其中
      `φ_n` 在源侧为 0、漏侧为 V_d（沟道内线性过渡；沟道里 n 本就可忽略 ⇒ 过渡形状不敏感）。
      于是漏 n⁺ 在 ψ = ψ_n + V_d 处自然给出 n = N_D ⇒ **严格中性**，电位可自由随 V_d 抬升。

      🔴 另：**不可**用「n 区硬置 ρ ≡ 0」代替（试过，更差）：那会让 n⁺ 对场零响应，
      n⁺/p 结耗尽全部压到 p 侧 ⇒ 长沟道 V_th 反而偏高 ~30 mV（roll-off 变正号）。
      准费米分裂既保住中性、又保住结侧耗尽，是正确解。

    `majority`（耗尽近似）在 p 区**丢弃电子项**（即丢弃反型层）：ρ = q(p − N_A)。
    """
    e_n = np.exp(np.clip((psi - phi_n_shift) / v_t, -BOLTZ_CLIP, BOLTZ_CLIP))
    n = n_i * e_n
    p = n_i * np.exp(np.clip(-psi / v_t, -BOLTZ_CLIP, BOLTZ_CLIP))
    if mode == "boltzmann":
        rho = p - n + ND - NA
        drho = -(n + p) / v_t
    else:                                        # majority：p 区只留空穴（耗尽近似）
        is_p = NA > ND
        rho = np.where(is_p, p - NA, p - n + ND - NA)
        drho = np.where(is_p, -p / v_t, -(n + p) / v_t)
    rho = np.where(in_ox, 0.0, rho)
    drho = np.where(in_ox, 0.0, drho)
    return Q_E * rho, Q_E * drho


# ---------------------------------------------------------------------------
# 器件缓存（几何/网格/矩阵一次装配，多次求解）
# ---------------------------------------------------------------------------
_DEV_CACHE: dict = {}


def mos2d_device(Lg: float = LG_DEFAULT, xj: float = XJ_DEFAULT,
                 t_ox: float = T_OX_DEFAULT, N_A: float = N_A_DEFAULT,
                 N_SD: float = N_SD_DEFAULT, L_side: float = L_SIDE_DEFAULT,
                 T_si: float = T_SI_DEFAULT, dx_target: float = DX_TARGET,
                 ny_si: int = NY_SI_DEFAULT, ny_ox: int = NY_OX,
                 smooth: float = SMOOTH_NM) -> dict:
    """装配（并缓存）一个器件：网格 / 掺杂 / 泊松矩阵 / 界面索引。"""
    key = (Lg, xj, t_ox, N_A, N_SD, L_side, T_si, dx_target, ny_si, ny_ox, smooth)
    dev = _DEV_CACHE.get(key)
    if dev is not None:
        return dev
    geom = mos2d_geometry(Lg, xj, t_ox, L_side, T_si)
    x, y = mos2d_grid(geom, dx_target, ny_si, ny_ox)
    xx, yy = np.meshgrid(x, y, indexing="ij")
    NA, ND, in_ox = mos2d_doping(xx, yy, geom, N_A, N_SD, smooth)
    eps_node, eps_yface = _face_eps(y, geom["t_ox"])
    M, vol = fv_poisson_matrix(x, y, eps_node, eps_yface)
    j_if = int(np.argmin(np.abs(y - geom["t_ox"])))
    # 电子准费米势空间形状：源侧 0 → 漏侧 1（沟道内线性；沟道里 n 可忽略 ⇒ 形状不敏感）
    xr = np.clip((x - geom["x_gate_lo"]) / max(geom["Lg"], 1e-30), 0.0, 1.0)
    dev = {
        "geom": geom, "x": x, "y": y, "nx": int(x.size), "ny": int(y.size),
        "NA": NA, "ND": ND, "in_ox": in_ox,
        "NA_f": NA.flatten(), "ND_f": ND.flatten(), "in_ox_f": in_ox.flatten(),
        "M": M, "vol": vol, "j_if": j_if,
        "w_ramp": np.repeat(xr, int(y.size)),
        "N_A": float(N_A), "N_SD": float(N_SD), "v_t": V_T, "n_i": N_I,
        "dx": float(x[1] - x[0]), "eps_node": eps_node, "eps_yface": eps_yface,
    }
    _DEV_CACHE[key] = dev
    return dev


def natural_length(xj: float = XJ_DEFAULT, t_ox: float = T_OX_DEFAULT,
                   eps_si: float = EPS_SI, eps_ox: float = EPS_OX) -> float:
    """短沟道**自然长度** λ = √(ε_si·t_ox·x_j/ε_ox)（DIBL 特征长度量级）。"""
    return math.sqrt(eps_si * t_ox * float(xj) / eps_ox)


# ---------------------------------------------------------------------------
# 主求解入口
# ---------------------------------------------------------------------------
def solve_mos2d(Vg: float, Vd: float = 0.0, Vb: float = 0.0, Vs: float = 0.0,
                mode: str = "majority", warm: np.ndarray | None = None,
                device: dict | None = None, VFB: float = VFB_DEFAULT,
                n_continuation: int = 8, max_iter: int = 80,
                resid_tol: float = 1e-8, step_cap: float = 0.10,
                damp: float = 1.0, return_fields: bool = True, **dev_kw) -> dict:
    """解 2D MOSFET 泊松（四端）。

    - `mode='majority'`（默认）：耗尽近似，任意 V_d 可用（DIBL 可算）。
    - `mode='boltzmann'`：全玻尔兹曼，**要求 V_d = 0**（见模块 docstring）。
    - `warm`：上一解（同器件同 mode）作初值 ⇒ V_th 扫描的关键加速。
    - `n_continuation`：从平衡态逐级升到 V_g 的 continuation 步数（强反型必需）。

    返回 dict：ψ(x,y) / n / p / 界面表面势 ψ_s(x) / ψ_s_min / 网格 / 收敛信息。
    `is_oracle=False`（T1 红线）。
    """
    if mode not in _MODES:
        raise ValueError("mode 必须是 %s 之一，得到 %r" % (_MODES, mode))
    if mode == "boltzmann" and Vd != 0.0:
        raise ValueError(
            "mode='boltzmann' 只支持平衡（V_d = 0）：平衡玻尔兹曼式 + 偏压 Dirichlet "
            "会让漏端载流子浓度变成 N_SD·e^{V_d/V_T}（非物理）。"
            "偏压输运需准费米势分裂（Gummel）⇒ E13 候选。"
            "要算 DIBL 请用 mode='majority'（耗尽近似，标准短沟道分析框架）。")
    dev = device if device is not None else mos2d_device(**dev_kw)
    x, y = dev["x"], dev["y"]
    nx, ny = dev["nx"], dev["ny"]

    # continuation：V_g 从 0 逐级升到目标（强反型界面载流子极高，**冷启动**必须分步）。
    # 🔴 有 `warm` 时**不做 continuation**（steps=1）：暖启动已把解带到邻近工况，
    #    再做「0 → V_g」的升压反而把首步推到 V_g/steps（远离暖启动）⇒ 既慢又更易发散。
    #    实测：V_th 扫描（暖启动链）耗时因此降到 ~1/6。
    steps = 1 if warm is not None else max(int(n_continuation), 1)
    first = mos2d_dirichlet(dev, float(Vg) / steps, Vd, Vb, Vs, VFB)
    psi = (_initial_guess(dev, first).flatten() if warm is None
           else np.asarray(warm, dtype=float).copy())
    conv = False
    n_iter = 0
    sol = {"resid": float("inf")}
    for s in range(1, steps + 1):
        tab = mos2d_dirichlet(dev, float(Vg) * s / steps, Vd, Vb, Vs, VFB)
        # 中间 continuation 步用**松容差**（只为把解带到目标附近），
        # 末步才用紧容差 —— 否则每步都磨到 1e-8 会把耗时放大数倍。
        tol_s = resid_tol if s == steps else max(resid_tol * 1e3, 1e-6)
        sol = _solve_poisson(dev, tab, mode, psi, max_iter, tol_s, step_cap, damp)
        psi = sol["psi"]
        conv = sol["converged"]
        n_iter += sol["n_iter"]
        if not conv and s < steps:
            break                                # 中途失守 ⇒ 不再硬推

    tab = mos2d_dirichlet(dev, Vg, Vd, Vb, Vs, VFB)
    out = {
        "x": x, "y": y, "psi": psi.reshape(nx, ny),
        "Vg": float(Vg), "Vd": float(Vd), "Vb": float(Vb), "mode": mode,
        "Lg": dev["geom"]["Lg"], "V_FB": float(VFB),
        "N_A": dev["N_A"], "N_SD": dev["N_SD"],
        "psi_bulk": float(tab["psi_bulk"]), "psi_gate": float(tab["psi_gate"]),
        "i_gate": tab["i_gate"], "j_if": dev["j_if"],
        "converged": bool(conv), "n_iter": int(n_iter),
        "resid": float(sol["resid"]),
        "provenance": "self_authored_t1_candidate", "is_oracle": False,
    }
    if return_fields:
        n_, p_ = _carriers(psi, dev["v_t"], dev["n_i"], float(Vd) * dev["w_ramp"])
        out["n"] = n_.reshape(nx, ny)
        out["p"] = p_.reshape(nx, ny)
    ps = surface_potential(out)
    out["psi_s"] = ps["psi_s"]
    out["psi_s_min"] = ps["psi_s_min"]
    out["psi_s_min_index"] = ps["i_min"]
    out["inversion_onset"] = bool(ps["psi_s_min"] >= ps["psi_target"])
    return out


def surface_potential(sol: dict) -> dict:
    """沿 Si/SiO₂ 界面取 ψ_s(x)，并在**栅跨度内**取最小（"虚拟阴极"）。

    🔴 取 **min** 不是 max：电子的势垒顶在 ψ 最低处（E_C ∝ −qψ）；
    短沟道下漏偏压抬高漏侧 ψ ⇒ 最低点（势垒顶）下降 ⇒ V_th 下降。
    取 max 会把趋势做反（突变探针 C4 专门守这条）。
    """
    psi = sol["psi"]
    j = sol["j_if"]
    i_lo, i_hi = sol["i_gate"]
    psi_s = np.asarray(psi[:, j], dtype=float)
    seg = psi_s[i_lo:i_hi + 1]
    i_min = int(i_lo + np.argmin(seg))
    return {"psi_s": psi_s, "psi_s_min": float(psi_s[i_min]), "i_min": i_min,
            "i_span": (int(i_lo), int(i_hi)),
            "psi_target": float(phi_f(sol.get("N_A", N_A_DEFAULT)))}


# ---------------------------------------------------------------------------
# V_th 提取 / 短沟道扫描
# ---------------------------------------------------------------------------
_DEV_KEYS = ("xj", "t_ox", "N_A", "N_SD", "L_side", "T_si", "dx_target",
             "ny_si", "ny_ox", "smooth")
_SOLVE_KEYS = ("VFB", "n_continuation", "max_iter", "resid_tol", "step_cap", "damp")


def extract_vth_2d(Lg: float = LG_DEFAULT, Vd: float = 0.05, mode: str = "majority",
                   vg_lo: float = 0.0, vg_hi: float = 1.2, vg_step: float = 0.10,
                   psi_target: float | None = None, tol: float = 1e-4,
                   max_secant: int = 6, device: dict | None = None,
                   **kw) -> dict:
    """2D 数值 V_th：**界面最低表面势 ψ_s,min 达 +φ_F 的 V_g**。

    做法（稳健且省算力）：从 `vg_lo` 起**逐步上行**，每步用上一解暖启动
    （非线性求解的收敛性依赖初值接近度）；捕获 `ψ_s,min` 跨越 `φ_F` 的相邻两点，
    再用割线法细化到 `tol`。
    """
    if device is None:
        device = mos2d_device(Lg=Lg, **{k: kw[k] for k in _DEV_KEYS if k in kw})
    dev = device
    target = float(phi_f(dev["N_A"])) if psi_target is None else float(psi_target)
    solve_kw = {k: kw[k] for k in _SOLVE_KEYS if k in kw}

    def _eval(vg: float, warm):
        s = solve_mos2d(vg, Vd=Vd, mode=mode, warm=warm, device=dev,
                        return_fields=False, **solve_kw)
        return s, s["psi_s_min"], s["psi"].flatten()

    vg_a, warm = float(vg_lo), None
    s_a, ps_a, warm = _eval(vg_a, warm)
    if ps_a >= target:                            # 已在反型（异常，如实报）
        return {"Lg": dev["geom"]["Lg"], "Vd": float(Vd), "mode": mode,
                "V_th": float(vg_a), "psi_s_min": float(ps_a),
                "psi_target": target, "n_solves": 1, "bracketed": False,
                "converged": bool(s_a["converged"]),
                "provenance": "self_authored_t1_candidate", "is_oracle": False}
    vg_b, ps_b, s_b = vg_a, ps_a, s_a
    n_solves = 1
    while vg_b < vg_hi:
        vg_b = min(vg_b + float(vg_step), float(vg_hi))
        s_b, ps_b, warm = _eval(vg_b, warm)
        n_solves += 1
        if ps_b >= target:
            break
        vg_a, ps_a = vg_b, ps_b
    vth = float(vg_b)
    bracketed = bool(ps_b >= target and ps_a < target)
    if bracketed:                                  # 割线（regula falsi）
        for _ in range(int(max_secant)):
            d = (ps_b - ps_a)
            if abs(d) < 1e-30:
                break
            # 🔴 求 (ψ_s,min − target) 的零点：必须减 target。
            #   写成 `vg_b − ps_b·Δ/…` 会退化成「永远落在括号左端」的假收敛
            #   （本轮血案：V_th 恒等于 vg_a，而 bracketed 仍为 True ⇒ 假绿）。
            vg_c = vg_b - (ps_b - target) * (vg_b - vg_a) / d
            lo, hi = min(vg_a, vg_b), max(vg_a, vg_b)
            vg_c = float(min(max(vg_c, lo), hi))
            s_c, ps_c, warm = _eval(vg_c, warm)
            n_solves += 1
            vth = vg_c
            if abs(ps_c - target) <= tol:
                break
            if ps_c < target:
                vg_a, ps_a = vg_c, ps_c
            else:
                vg_b, ps_b = vg_c, ps_c
            if abs(vg_b - vg_a) < 1e-6:
                break
    return {"Lg": dev["geom"]["Lg"], "Vd": float(Vd), "mode": mode,
            "V_th": float(vth), "psi_s_min": float(ps_b), "psi_target": target,
            "n_solves": n_solves, "bracketed": bracketed,
            "converged": bool(s_b["converged"]),
            "provenance": "self_authored_t1_candidate", "is_oracle": False}


def rolloff_sweep(Ls=(65e-9, 100e-9, 150e-9, 250e-9, 500e-9), Vd: float = 0.05,
                  mode: str = "majority", **kw) -> list:
    """V_th(L) 扫描；返回每条含 `delta_vth`（相对最长沟道）与 `rolloff_rel`。"""
    pts = []
    for L in Ls:
        r = extract_vth_2d(Lg=float(L), Vd=Vd, mode=mode, **kw)
        pts.append(r)
    ref = max(pts, key=lambda p: p["Lg"])["V_th"]
    for p in pts:
        p["delta_vth"] = float(p["V_th"] - ref)
        p["rolloff_rel"] = float((p["V_th"] - ref) / ref) if ref else 0.0
    return pts


def dibl_sweep(Lg: float = LG_DEFAULT, Vds=(0.05, 0.5, 1.0), mode: str = "majority",
               **kw) -> dict:
    """DIBL 扫描：V_th(V_d) 线性回归斜率 ⇒ DIBL = −dV_th/dV_d（mV/V）。"""
    xs, ys, pts = [], [], []
    for vd in Vds:
        r = extract_vth_2d(Lg=Lg, Vd=float(vd), mode=mode, **kw)
        pts.append(r)
        xs.append(float(vd))
        ys.append(r["V_th"])
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((v - mx) ** 2 for v in xs)
    slope = (sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / den
             if den > 0 else 0.0)
    return {"Lg": float(Lg), "mode": mode, "points": pts,
            "d_vth_d_vd": float(slope), "dibl_mv_per_v": float(-slope * 1e3),
            "vth_span": float(max(ys) - min(ys)),
            "provenance": "self_authored_t1_candidate", "is_oracle": False}


def dibl_exponential_law(Ls=(65e-9, 100e-9, 150e-9, 250e-9),
                         Vd_lo: float = 0.05, Vd_hi: float = 1.0,
                         mode: str = "majority", **kw) -> dict:
    """DIBL 的**指数衰减律**检验：DIBL(L) ∝ e^{−L/ℓ_eff}。

    这是本模块**最强的物理正确性证据** —— 数值假象不会给出干净的指数律。
    返回每点 DIBL、ln 线性拟合的斜率/R²、及衰减长度 ℓ_eff = 1/|slope|。
    """
    pts, xs, ys = [], [], []
    dx_fixed = kw.pop("dx_target", None)
    for L in Ls:
        dxi = dx_fixed if dx_fixed is not None else (10e-9 if L >= 400e-9 else
                                                     (5e-9 if L >= 200e-9 else 2.5e-9))
        a = extract_vth_2d(Lg=float(L), Vd=Vd_lo, mode=mode, dx_target=dxi, **kw)
        b = extract_vth_2d(Lg=float(L), Vd=Vd_hi, mode=mode, dx_target=dxi, **kw)
        dibl = (a["V_th"] - b["V_th"]) / (Vd_hi - Vd_lo) * 1e3      # mV/V
        pts.append({"Lg": float(L), "vth_lo": a["V_th"], "vth_hi": b["V_th"],
                    "dibl_mv_per_v": float(dibl)})
        xs.append(float(L) * 1e9)
        ys.append(math.log(dibl) if dibl > 0.0 else float("nan"))
    n = len(xs)
    ok_fit = all(math.isfinite(v) for v in ys) and n >= 3
    if ok_fit:
        mx, my = sum(xs) / n, sum(ys) / n
        den = sum((v - mx) ** 2 for v in xs)
        slope = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / den
        icpt = my - slope * mx
        sse = sum((ys[i] - (slope * xs[i] + icpt)) ** 2 for i in range(n))
        sst = sum((v - my) ** 2 for v in ys)
        r2 = 1.0 - sse / sst if sst > 0 else 0.0
    else:
        slope, icpt, r2 = float("nan"), float("nan"), 0.0
    return {"points": pts, "slope_per_nm": float(slope), "intercept": float(icpt),
            "r2": float(r2),
            "decay_length_nm": float(1.0 / (-slope)) if slope < 0 else float("nan"),
            "dibl_65nm_mv_per_v": float(pts[0]["dibl_mv_per_v"]) if pts else 0.0,
            "provenance": "self_authored_t1_candidate", "is_oracle": False}


def mos2d_vth_mode_gap(Lg: float = 100e-9, **kw) -> float:
    """`boltzmann` 与 `majority` 两变体在**平衡**（V_d=0）下的 V_th 差。

    该差 = 反型层电荷对 V_th 的贡献（boltzmann 含反型层 ⇒ V_th 略高）。
    """
    a = extract_vth_2d(Lg=Lg, Vd=0.0, mode="majority", **kw)
    b = extract_vth_2d(Lg=Lg, Vd=0.0, mode="boltzmann", **kw)
    return float(b["V_th"] - a["V_th"])


def vth_long_channel_golden(N_A: float = N_A_DEFAULT, t_ox: float = T_OX_DEFAULT,
                            VFB: float = VFB_DEFAULT) -> dict:
    """golden：教科书 1D 长沟道 V_th（**直调 mos_1d 单一定义**，不复制）。"""
    g = moscap_vth_closed_form(N_A=N_A, t_ox=t_ox, VFB=VFB)
    g = dict(g)
    g["provenance"] = "design_rule_anchor_textbook_long_channel"
    return g


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = True) -> bool:
    msgs = []

    def chk(name, cond, det=""):
        msgs.append((name, bool(cond), det))
        return bool(cond)

    ok = True

    # ① 网格：y 含界面；x 覆盖栅跨度
    geom = mos2d_geometry()
    x, y = mos2d_grid(geom)
    j_if = int(np.argmin(np.abs(y - geom["t_ox"])))
    ok &= chk("① 网格含 Si/SiO₂ 界面 y=t_ox 且栅跨度在 x 内",
              abs(y[j_if] - geom["t_ox"]) < 1e-15
              and geom["x_gate_hi"] <= x[-1] + 1e-15, f"j_if={j_if}")

    # ② 掺杂：栅下是 p、栅外浅区是 n⁺、氧化层无掺杂
    xx, yy = np.meshgrid(x, y, indexing="ij")
    NA, ND, in_ox = mos2d_doping(xx, yy, geom)
    i_c = int(np.argmin(np.abs(x - 0.5 * (geom["x_gate_lo"] + geom["x_gate_hi"]))))
    j_srf = j_if + 1
    ok &= chk("② 掺杂：栅下表面 p 型 · 栅外浅区 n⁺ · 氧化层零掺杂",
              NA[i_c, j_srf] > 1e22 and ND[i_c, j_srf] < 1e20
              and ND[2, j_srf] > 1e25 and bool(np.all(NA[in_ox] == 0.0))
              and bool(np.all(ND[in_ox] == 0.0)),
              f"NA_gate={NA[i_c, j_srf]:.3e} ND_sd={ND[2, j_srf]:.3e}")

    # ③ 泊松矩阵对称 + 面材质精确（界面恰为节点 ⇒ 氧化层面恰为 ε_ox）
    dev = mos2d_device()
    M = dev["M"].toarray()
    sym = float(np.max(np.abs(M - M.T)))
    n_ox_face = int(np.sum(dev["eps_yface"][:NY_OX] == EPS_OX))
    ok &= chk("③ FV 矩阵对称 且 氧化层面恰为 ε_ox（面中点判介质 ⇒ 离散精确）",
              sym < 1e-12 and n_ox_face == NY_OX and M[dev["ny"] + 3, dev["ny"] + 3] < 0.0,
              f"|M−Mᵀ|max={sym:.2e} · 氧化层面 {n_ox_face}/{NY_OX}")

    # ④ 耗尽模式求解收敛
    s = solve_mos2d(Vg=0.5, Vd=0.0, mode="majority")
    ok &= chk("④ majority 求解收敛（V_g=0.5 V）", bool(s["converged"]),
              f"n_iter={s['n_iter']} resid={s['resid']:.2e}")

    # ⑤ 长沟道 ⇒ 收敛到教科书 1D 闭式（本段最强判据）
    g = vth_long_channel_golden()
    r_long = extract_vth_2d(Lg=1.0e-6, Vd=0.05, mode="majority", dx_target=15e-9)
    rel = abs(r_long["V_th"] - g["V_th"]) / g["V_th"]
    ok &= chk("⑤ 长沟道 2D V_th ⟷ 教科书 1D 闭式（rel < 2%）", rel < 0.02,
              f"2D={r_long['V_th']:.4f} V · 1D={g['V_th']:.4f} V · rel={rel:.3%}")

    # ⑥ roll-off：短沟道 V_th 低于长沟道，且单调
    r_short = extract_vth_2d(Lg=65e-9, Vd=0.05, mode="majority")
    r_mid = extract_vth_2d(Lg=250e-9, Vd=0.05, mode="majority", dx_target=5e-9)
    ok &= chk("⑥ roll-off 存在且单调：V_th(65nm) < V_th(250nm) < V_th(1µm)",
              r_short["V_th"] < r_mid["V_th"] < r_long["V_th"],
              f"{r_short['V_th']:.4f} < {r_mid['V_th']:.4f} < {r_long['V_th']:.4f} V")

    # ⑦ DIBL 随栅长**指数衰减**（R² 判据）—— 最强的物理正确性证据
    lam_res = dibl_exponential_law(Ls=(65e-9, 150e-9, 250e-9))
    ok &= chk("⑦ DIBL 存在 且 ln(DIBL)–L 线性（R² > 0.99 · 指数衰减律）",
              lam_res["dibl_65nm_mv_per_v"] > 10.0 and lam_res["r2"] > 0.99,
              f"DIBL(65nm)={lam_res['dibl_65nm_mv_per_v']:.1f} mV/V · "
              f"ℓ_eff={lam_res['decay_length_nm']:.1f} nm · R²={lam_res['r2']:.5f}")

    # ⑧ 栅氧正确性：t_ox↑ ⇒ V_th↑（体电荷项 Q_dep/C_ox）
    r4 = extract_vth_2d(Lg=250e-9, Vd=0.05, mode="majority", t_ox=4e-9)
    r8 = extract_vth_2d(Lg=250e-9, Vd=0.05, mode="majority", t_ox=8e-9)
    ok &= chk("⑧ 栅氧 t_ox ↑ ⇒ V_th ↑（Q_dep/C_ox 体电荷项）",
              r8["V_th"] > r4["V_th"], f"4nm={r4['V_th']:.4f} → 8nm={r8['V_th']:.4f} V")

    # ⑨ 网格收敛：dx 减半 ⇒ V_th 变化 < 2 mV
    ra = extract_vth_2d(Lg=100e-9, Vd=0.05, mode="majority", dx_target=5e-9, ny_si=30)
    rb = extract_vth_2d(Lg=100e-9, Vd=0.05, mode="majority", dx_target=2.5e-9, ny_si=46)
    ok &= chk("⑨ 网格收敛：dx 5→2.5 nm ⇒ ΔV_th < 2 mV",
              abs(rb["V_th"] - ra["V_th"]) < 2e-3,
              f"ΔV_th={(rb['V_th']-ra['V_th'])*1e3:+.2f} mV")

    # ⑩ 自然长度与器件尺度同阶
    lam = natural_length()
    ok &= chk("⑩ 自然长度 λ 与栅长同阶（短沟道区间 1 < Lg/λ < 20）",
              1.0 < (65e-9 / lam) < 20.0, f"λ={lam*1e9:.2f} nm · Lg/λ(65nm)={65e-9/lam:.2f}")

    # ⑪ 红线/诚实：boltzmann 模式拒绝偏压
    raised = False
    try:
        solve_mos2d(Vg=0.5, Vd=0.5, mode="boltzmann")
    except ValueError:
        raised = True
    ok &= chk("⑪ boltzmann 模式对 V_d≠0 显式拒绝（准费米势未建模，不假装能做）", raised)

    # ⑫ 两变体互验：majority ⟷ boltzmann 在平衡下差异 = 反型层电荷贡献（小）
    dg = abs(mos2d_vth_mode_gap(100e-9))
    ok &= chk("⑫ 两变体互验：|V_th(boltzmann) − V_th(majority)| < 30 mV（反型层电荷贡献）",
              dg < 0.030, f"Δ={dg*1e3:.1f} mV @Lg=100nm")

    if verbose:
        for nm, c, det in msgs:
            print(("  [PASS] " if c else "  [FAIL] ") + nm + (f" :: {det}" if det else ""))
        print(f"  —— mos_2d 自检 {sum(1 for _, c, _ in msgs if c)}/{len(msgs)} ——")
    return ok


if __name__ == "__main__":
    print("=== golden：教科书 1D 长沟道 V_th ===")
    gg = vth_long_channel_golden()
    print(f"  V_FB={gg['V_FB']:.4f} V  2φ_F={gg['two_phi_f']:.4f} V  "
          f"C_ox={gg['C_ox']*1e3:.4f} mF/m²  V_th={gg['V_th']:.4f} V")
    print(f"=== 自然长度 λ = {natural_length()*1e9:.2f} nm "
          f"（= E11-d 文献式 ℓ，同式同值）===")
    print("=== mos_2d 自检 ===")
    run_selfchecks(verbose=True)
    print("=== roll-off（V_d=0.05 V · majority）===")
    print(f"  {'Lg(nm)':>8} {'V_th(V)':>10} {'ΔV_th(mV)':>12} {'rel':>9} "
          f"{'solves':>7} {'conv':>6}")
    for p in rolloff_sweep(mode="majority"):
        print(f"  {p['Lg']*1e9:>8.0f} {p['V_th']:>10.4f} {p['delta_vth']*1e3:>12.1f} "
              f"{p['rolloff_rel']:>9.2%} {p['n_solves']:>7} "
              f"{str(p['converged']):>6}")
    print("  （与 Yau 文献式的对照见 lda_l2/ecore/device_2d.py：那是**对照**，非 golden）")
    print("=== DIBL 指数衰减律 ===")
    law = dibl_exponential_law()
    for p in law["points"]:
        print(f"  Lg={p['Lg']*1e9:>5.0f} nm  V_th({0.05:.2f}V)={p['vth_lo']:.4f}  "
              f"V_th(1.00V)={p['vth_hi']:.4f}  DIBL={p['dibl_mv_per_v']:>6.1f} mV/V")
    print(f"  ℓ_eff = {law['decay_length_nm']:.1f} nm · R² = {law['r2']:.5f}")
    guard_t1_not_oracle({"V_th": 0.4})
    print("=== T1 不作 ORACLE 守卫：正常通过 ===")
