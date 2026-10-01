# -*- coding: utf-8 -*-
"""LDA · 电子计算征程 E13 · **2D MOS 漂移扩散输运**（补 I–V / 亚阈值摆幅）。

============================================================================
为什么存在（E13 · 电子计算征程）
----------------------------------------------------------------------------
E12 交付了 2D MOS **自洽泊松**（四端分段 BC + 电子准费米势分裂），短沟道
roll-off / DIBL 已由 2D 数值解自然涌现 —— 但它是**准平衡静电求解**，
`device_2d.short_channel_capability_report()` 明确登记「**不含输运 ⇒ 不产 I-V**」。

E13 把这一格补上：解稳态漂移扩散（Gummel）⇒ 产出 I_d(V_g, V_d)、
**亚阈值摆幅 SS**、I_on/I_off、**恒定电流法 V_th**。

============================================================================
复用纪律（两侧各有一半，本模块 = 焊接，不复制第二份）
----------------------------------------------------------------------------
· 输运侧（复用 `lda_solver/drift_diffusion_2d.py`）：
  `_bernoulli`（SG 函数论核心）· SG 通量形式 1 · 「已知端移入 RHS」的 Dirichlet 装配法
· 几何侧（复用 `lda_solver/mos_2d.py`）：
  `mos2d_device`（幂律非均匀网格 + 变系数 FV 泊松 + in_ox 掩码）· `_dir_matrix`
  （几何定后缓存「Dirichlet 行已恒等」的矩阵）· `mos2d_dirichlet`（四端取值表 + 接触优先序）
· 量纲/常数：`drift_diffusion_1d`（全 SI）
🔴 **不改任何既有模块的数值行为**（E1–E12 全部数字与判据不动）。

============================================================================
三个本质缺口（E13 解决；E11-b/E12 都没有）
----------------------------------------------------------------------------
① **连续性 BC 从「两端标量」→「节点集 mask」**：MOS 的接触是
   源（x=0 整列 Si）/ 漏（x=Lx 整列 Si）/ 衬底（y=Ty 整行），**外加栅跨度无载流子**。
② **氧化层内无载流子**：连续性方程**只在 Si 节点上解**（氧化层节点逐出未知量集），
   Si↔SiO₂ 界面取**无通量 Neumann**。否则会解出伪载流子、电流从栅漏走。
③ **接触准费米势 BC**：接触钉 `φ_n = φ_p = V_接触`（无限复合中心 ⇒ n·p = n_i²）⇒
   `n_k = n_i·e^{(ψ_k − V_c)/V_T}`、`p_k = n_i·e^{(V_c − ψ_k)/V_T}`。
   这个**统一式**自动给出 n⁺ 区 n=N_SD、p 区 p=N_A（因为 ψ_k 由掺杂决定），无需分支。

============================================================================
数值要点
----------------------------------------------------------------------------
· y 网格**非均匀**（mos_2d 幂律加密，Si 表面首格 ≈ 0.15 nm ⇒ **反型层可解析**）
  ⇒ SG 装配必须**逐边取间距** `h_y[j] = y[j+1]-y[j]`，不能像 dd2d 那样假定均匀 dy。
· 边结构固定 ⇒ **预计算 (row, col) 与边表**，每轮只更新 data / RHS（向量化，避免
  Python 逐边循环拖垮 Gummel）。
· 冷暖启动：V_g 扫描时用上一解暖启动。🔴 E12 教训：**有暖启动就不再跑 continuation**
  （continuation 只为冷启动存在，否则首步从 V_g/steps 起跳反而远离暖解）。

============================================================================
🔴 红线与诚实边界
----------------------------------------------------------------------------
· **T1 候选**：本模块全部数值输出 `is_oracle=False`；golden 见
  `ecore/device_transport.py` 的判据（**SS ≥ 60 mV/dec 是物理定律锚**）。
· 仍是**漂移扩散（DD）框架** ⇒ 不含量子修正 / 速度饱和 / 隧穿 / 弹道输运；
  **深亚阈值 SS 不受影响**（那里由玻尔兹曼尾决定），但 **I_on 偏高、I_off 偏低**。
· **迁移率为常数**（无场依赖退化 / 无表面散射）⇒ `I_on` 绝对值**不可当器件性能**，
  只作相对趋势与 SS / 亚阈值判据。
· 无 LDD / halo / 应变 / 栅重叠；参数为公开典型量级占位（**非 PDK**，无实测锚）。
· 2D 仿真 = **每单位宽度电流**（A/m），不是绝对安培。
· 不报 TOPS / TOPS-W / fJ/op；**EAR 744.23**（成熟节点 / 非先进用途）。
· 依赖 scipy ⇒ 调用方（`ecore/device_transport.py`）须**函数内惰性导入**本模块。
"""
from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

try:                                                    # 包内导入
    from .drift_diffusion_1d import EPS_SI, K_B, N_I, Q_E
    from .drift_diffusion_2d import MU_N, MU_P
    from .drift_diffusion_2d import _bernoulli as _bern
    from .mos_2d import (
        BOLTZ_CLIP, EPS_OX, N_A_DEFAULT, PSI_FLOOR, T_OX_DEFAULT, VFB_DEFAULT,
        _dir_matrix, _initial_guess, mos2d_device, phi_f,
    )
    from .redline import T1_OUTPUT_IS_ORACLE, guard_t1_not_oracle
except ImportError:                                     # 脚本直跑
    from lda_solver.drift_diffusion_1d import EPS_SI, K_B, N_I, Q_E  # type: ignore
    from lda_solver.drift_diffusion_2d import MU_N, MU_P  # type: ignore
    from lda_solver.drift_diffusion_2d import _bernoulli as _bern  # type: ignore
    from lda_solver.mos_2d import (  # type: ignore
        BOLTZ_CLIP, EPS_OX, N_A_DEFAULT, PSI_FLOOR, T_OX_DEFAULT, VFB_DEFAULT,
        _dir_matrix, _initial_guess, mos2d_device, phi_f,
    )
    from lda_solver.redline import T1_OUTPUT_IS_ORACLE, guard_t1_not_oracle  # type: ignore

_REDLINE_EXPORTS = (T1_OUTPUT_IS_ORACLE, guard_t1_not_oracle)

# ---- 默认量（公开惯例 / 公开典型量级 · 非 PDK）----
V_DD_DEFAULT = 1.0                 # 电源电压 (V) —— I_on/I_off 提取口径（公开惯例）
I_REF_A_PER_M = 100.0e-9           # 恒定电流法参考电流缺省（A/**每米宽度**）
I_REF_NORM_A = 100.0e-9            # 经典恒流法参考电流（100 nA · 按 W/L 归一化的分子）
VG_MAX_DEFAULT = 1.2               # V_g 扫描上限 (V)
VG_STEP_DEFAULT = 0.10             # V_g 扫描步长 (V)
SS_FIT_LO_A_PER_M = 1.0e-9         # SS 拟合窗口下界 (A/m，每单位宽度)
SS_FIT_HI_A_PER_M = 1.0e-4         # SS 拟合窗口上界 (A/m)
SS_THERMAL_LIMIT_MV_DEC = 60.0     # 🔴 室温热极限 kT/q·ln10（物理定律锚）


# ===========================================================================
# ① Si-only 装配（掩码 + 边表预计算）
# ===========================================================================
def transport_masks(dev: Dict) -> Dict:
    """把器件切成「Si 节点集 / 接触节点集」，并预计算 Si–Si 边表。

    返回 dict：
      si        : bool (nx*ny,) Si 节点掩码
      pos       : int  (nx*ny,) Si 节点在压缩编号（0..n_si-1）中的位置（非 Si = -1）
      n_si      : int
      contact_kind : str (nx*ny,) 每节点接触类型（"src"/"drn"/"sub"/"gate"/""）
      contact_V : float (nx*ny,) 接触偏压（非接触 0）
      edges     : (ks, ms, hs, axis) Si–Si 边（压缩编号；ks<... 无序，双向）
      edge_isfirst : bool —— 该边是否「x 方向」
      contact_bool : bool (n_si,) 该 Si 节点是否接触（连续性方程的 Dirichlet 行）
    """
    if "tmask" in dev:
        return dev["tmask"]
    _dir_matrix(dev)          # 🔴 先触发布局装配：`i_gate_nodes` 由它懒写入 dev
    nx, ny = int(dev["nx"]), int(dev["ny"])
    n = nx * ny
    in_ox_2d = dev["in_ox"]
    si2d = ~in_ox_2d
    si = si2d.flatten()
    pos = np.full(n, -1, dtype=np.int64)
    si_idx = np.flatnonzero(si)
    pos[si_idx] = np.arange(si_idx.size, dtype=np.int64)
    n_si = int(si_idx.size)

    ids = np.arange(n).reshape(nx, ny)
    NA2d, ND2d = dev["NA"], dev["ND"]
    kind = np.full(n, "", dtype=object)
    cv = np.zeros(n)
    # 🔴 E13 接触定义（对 mos_2d 的关键修正）：**源/漏接触只覆盖 n⁺ 岛**。
    #    E12 把源/漏**整列**都当作接触并钉 n⁺ 电位 —— 那一列的下部是 p 型衬底，
    #    等价于把「源-体结」**短路**（强制二者 ψ 相同）。静电求解里影响有限，
    #    但输运求解里会注入巨大假电流（实测 I_off 180 A/m、源漏守恒 rel=1.0）。
    #    物理：源/漏金属只接 n⁺ 区；p 体由**衬底接触**控制（j=ny-1 整行钉 ψ_bulk）。
    for j in range(ny):
        if ND2d[0, j] > NA2d[0, j]:
            kind[ids[0, j]] = "src"
        if ND2d[nx - 1, j] > NA2d[nx - 1, j]:
            kind[ids[nx - 1, j]] = "drn"
    for i in range(nx):
        if kind[ids[i, ny - 1]] == "":
            kind[ids[i, ny - 1]] = "sub"
    # 栅顶行（仅栅跨度）：氧化层 ⇒ 不是导电接触（下面 `np.where(si, ...)` 会清掉）
    i_lo, i_hi = dev["i_gate_nodes"]
    for i in range(i_lo, i_hi + 1):
        if kind[ids[i, 0]] == "":
            kind[ids[i, 0]] = "gate"
    # 只在 Si 节点上保留接触（氧化层节点不是导电接触）
    kind = np.where(si, kind, "")

    # ---- Si–Si 边表（压缩编号）----
    ks: list = []
    ms: list = []
    hs: list = []
    ax: list = []
    for i in range(nx):
        for j in range(ny):
            k = int(ids[i, j])
            if not si[k]:
                continue
            if i + 1 < nx and si[int(ids[i + 1, j])]:
                ks.append(int(pos[k])); ms.append(int(pos[int(ids[i + 1, j])]))
                hs.append(float(dev["x"][i + 1] - dev["x"][i])); ax.append(True)
            if j + 1 < ny and si[int(ids[i, j + 1])]:
                ks.append(int(pos[k])); ms.append(int(pos[int(ids[i, j + 1])]))
                hs.append(float(dev["y"][j + 1] - dev["y"][j])); ax.append(False)
    info = {
        "si": si, "pos": pos, "n_si": n_si,
        "kind": kind, "contact_V": cv,
        "ks": np.asarray(ks, dtype=np.int64),
        "ms": np.asarray(ms, dtype=np.int64),
        "hs": np.asarray(hs, dtype=float),
        "axis_x": np.asarray(ax, dtype=bool),
        "contact_bool": np.asarray([kind[int(k)] != "" for k in si_idx], dtype=bool),
    }
    dev["tmask"] = info
    return info


def _contact_potentials(mask: Dict, Vg: float, Vd: float, Vb: float, Vs: float,
                        dev: Dict) -> Tuple[np.ndarray, np.ndarray]:
    """接触准费米势（φ_n = φ_p = V_接触）铺成全场数组。

    非接触 Si 节点与氧化层节点初值取「源侧 0 → 漏侧 V_d」的按 x 线性过渡
    （与 mos_2d 的静态 ramp 同构；沟道内 n 可忽略 ⇒ 过渡形状不敏感）。
    """
    ny = int(dev["ny"])
    xr = np.clip((dev["x"] - dev["geom"]["x_gate_lo"]) / max(dev["geom"]["Lg"], 1e-30),
                 0.0, 1.0)
    ph = np.repeat(xr, ny) * float(Vd)
    k = mask["kind"]
    ph[k == "src"] = float(Vs)
    ph[k == "drn"] = float(Vd)
    ph[k == "sub"] = float(Vb)
    ph[k == "gate"] = 0.0                    # 栅：无载流子，占位
    return ph.copy(), ph.copy()


def _contact_carriers(mask: Dict, psi: np.ndarray, dev: Dict) -> Tuple[np.ndarray, np.ndarray]:
    """接触节点的载流子密度 BC（φ_n = φ_p = V_c ⇒ n·p = n_i²）。

    `n = n_i·e^{(ψ_k − V_c)/V_T}`、`p = n_i·e^{(V_c − ψ_k)/V_T}`：
    统一式，自动给出 n⁺ 区 n=N_SD、p 区 p=N_A（ψ_k 由掺杂决定）。
    """
    v_t, n_i = dev["v_t"], dev["n_i"]
    cv = mask["contact_V"]
    reach = mask["contact_bool"]
    n = np.zeros(mask["n_si"])
    p = np.zeros(mask["n_si"])
    si_idx = np.flatnonzero(mask["si"])
    psi_si = psi[si_idx]
    vv = cv[si_idx]
    arg_n = np.clip((psi_si - vv) / v_t, -BOLTZ_CLIP, BOLTZ_CLIP)
    arg_p = np.clip((vv - psi_si) / v_t, -BOLTZ_CLIP, BOLTZ_CLIP)
    n[reach] = n_i * np.exp(arg_n[reach])
    p[reach] = n_i * np.exp(arg_p[reach])
    return n, p


def _set_contact_V(mask: Dict, Vd: float, Vb: float, Vs: float) -> None:
    """把接触偏压写进掩码（按接触类型）。"""
    k = mask["kind"]
    cv = mask["contact_V"]
    cv[k == "src"] = float(Vs)
    cv[k == "drn"] = float(Vd)
    cv[k == "sub"] = float(Vb)
    cv[k == "gate"] = 0.0


def _dir_matrix_nplus(dev: Dict) -> Tuple:
    """泊松 Dirichlet 行集合（**源/漏只含 n⁺ 节点**）—— E13 接触建模修正。

    与 `mos_2d._dir_matrix`（源/漏**整列**）的差异：把整列钉成 n⁺ 平衡电位
    等价于**短路源-体结**。静电求解影响有限，输运求解会产生巨大假电流。
    本函数把 Dirichlet 集合改为：**衬底整行 + 源/漏列的 n⁺ 部分 + 栅跨度顶行**。
    （**不改** `mos_2d` 自身 —— E12 的 24 判据与其数值行为完全不动。）

    返回 `(M_dir, idx)`：Dirichlet 行置 1 的 CSR + 升序节点索引。
    """
    if "M_dir_tr" in dev:
        return dev["M_dir_tr"]
    _dir_matrix(dev)                     # 触发装配：填充 i_gate_nodes
    nx, ny = int(dev["nx"]), int(dev["ny"])
    ids = np.arange(nx * ny).reshape(nx, ny)
    NA2d, ND2d = dev["NA"], dev["ND"]
    rows = {int(ids[i, ny - 1]) for i in range(nx)}            # 衬底：整行
    for j in range(ny):
        if ND2d[0, j] > NA2d[0, j]:
            rows.add(int(ids[0, j]))                           # 源：仅 n⁺
        if ND2d[nx - 1, j] > NA2d[nx - 1, j]:
            rows.add(int(ids[nx - 1, j]))                      # 漏：仅 n⁺
    i_lo, i_hi = dev["i_gate_nodes"]
    rows.update(int(ids[i, 0]) for i in range(i_lo, i_hi + 1))  # 栅：跨度内顶行
    M = dev["M"].tolil(copy=True)
    for k in rows:
        M.rows[k] = [k]
        M.data[k] = [1.0]
    idx = np.fromiter(sorted(rows), dtype=np.int64, count=len(rows))
    dev["M_dir_tr"] = (M.tocsr(), idx)
    return dev["M_dir_tr"]


def transport_dirichlet(dev: Dict, Vg: float, Vd: float, Vb: float,
                        Vs: float = 0.0, VFB: float = VFB_DEFAULT) -> Dict:
    """四端 Dirichlet **取值**表（配合 `_dir_matrix_nplus` 的 idx 顺序）。

    取值（物理：各接触的欧姆平衡电位 + 偏压）：
      · 衬底（整行）  `ψ_bulk + V_b`
      · 源 n⁺ 节点    `ψ_n + V_s`
      · 漏 n⁺ 节点    `ψ_n + V_d`
      · 栅（跨度内）   `ψ_bulk + V_g − V_FB`
    于是连续性 BC 的统一式 `n = n_i·e^{(ψ_k − V_c)/V_T}` 自动给出
    n⁺ 接触 `n = N_SD`、衬底接触 `n = n_i²/N_A` —— 两段都严格正确。
    """
    _, idx = _dir_matrix_nplus(dev)
    nx, ny = int(dev["nx"]), int(dev["ny"])
    v_t, n_i = dev["v_t"], dev["n_i"]
    psi_bulk = -phi_f(dev["N_A"], n_i, v_t)
    psi_n = v_t * math.log(dev["N_SD"] / n_i)
    psi_gate = psi_bulk + float(Vg) - float(VFB)
    psi_src = psi_n + float(Vs)
    psi_drn = psi_n + float(Vd)
    psi_sub = psi_bulk + float(Vb)
    i, j = idx // ny, idx % ny
    val = np.full(idx.size, psi_sub)
    val[i == 0] = psi_src                    # idx 里 i==0 的只可能是 n⁺（见 _dir_matrix_nplus）
    val[i == nx - 1] = psi_drn
    val[(i > 0) & (i < nx - 1) & (j == 0)] = psi_gate
    return {"idx": idx, "val": val, "psi_gate": psi_gate, "psi_src": psi_src,
            "psi_drn": psi_drn, "psi_sub": psi_sub, "psi_bulk": psi_bulk,
            "Vd": float(Vd), "i_gate": dev["i_gate_nodes"],
            "n_contact_nodes": int(idx.size)}


# ===========================================================================
# ② Si-only Scharfetter–Gummel 连续性方程
# ===========================================================================
def _continuity_sg_si(flag: str, psi: np.ndarray, mask: Dict,
                      dev: Dict) -> np.ndarray:
    """解稳态连续性 ∇·J = 0（SG 离散，**只在 Si 节点上**）。

    变量 = Si 节点上的载流子密度（压缩编号）；ψ 固定（Gummel 解耦）。

    🔴 与 `drift_diffusion_2d._solve_continuity_sg` 的两点差异（本模块的必要扩展）：
      ① **未知量集 = Si 节点**（氧化层节点逐出）⇒ Si↔SiO₂ 界面自然成为 Neumann；
         边只装配「两端皆 Si」的（氧化层边根本不进 edge 表）。
      ② **y 网格非均匀** ⇒ 每条边按自己的 `h` 取系数（mos_2d 的 y 是幂律加密网格）。
    BC 处理沿用 dd2d 的「已知端移入 RHS」法：接触节点在最后统一置恒等，
    其耦合项从对侧行的 RHS 扣除（避免 Dirichlet 行污染矩阵、产生伪通量）。
    """
    ks, ms, hs = mask["ks"], mask["ms"], mask["hs"]
    n_si = mask["n_si"]
    reach = mask["contact_bool"]
    v_t = dev["v_t"]
    mu = MU_N if flag == "n" else MU_P
    g = Q_E * mu * v_t                       # q·μ·V_T

    si_idx = np.flatnonzero(mask["si"])
    eta = psi[si_idx] / v_t                  # Si 节点上的 ψ/V_T（压缩编号）
    a_km = _bern(eta[ks] - eta[ms])          # B(η_k − η_m)
    a_mk = _bern(eta[ms] - eta[ks])          # B(η_m − η_k)
    w = g / hs                               # 逐边 q·μ·V_T/h

    bk = reach[ks]
    bm = reach[ms]
    grp_nn = ~bk & ~bm                       # 两端皆未知：装配四项
    grp_kd = bk & ~bm                        # k 已知 ⇒ 行 m 保留对角 + RHS 修正
    grp_md = ~bk & bm                        # m 已知 ⇒ 行 k 保留对角 + RHS 修正
    # 两端皆已知 ⇒ 不装配（行将被置恒等）

    # 电子：行 k 自 +w·a_km / 邻 m −w·a_mk；行 m 自 +w·a_mk / 邻 k −w·a_km
    # 空穴：镜像（自 −w·a_mk / 邻 m +w·a_km；行 m 自 −w·a_km / 邻 k +w·a_mk）
    if flag == "n":
        s_kk, s_km, s_mm, s_mk = w * a_km, -w * a_mk, w * a_mk, -w * a_km
        # 已知端移入 RHS 的系数（= −(w·c_other)）
        r_kd = w * a_km          # 行 m：b[m] += w·a_km·v_k
        r_md = w * a_mk          # 行 k：b[k] += w·a_mk·v_m
    else:
        s_kk, s_km, s_mm, s_mk = -w * a_mk, w * a_km, -w * a_km, w * a_mk
        r_kd = -w * a_mk         # 行 m：b[m] += −w·a_mk·v_k
        r_md = -w * a_km         # 行 k：b[k] += −w·a_km·v_m

    # ---- 装配（向量化：按边分组，四槽一起收集）----
    # 四槽定义（边 e 的两端 k=ks[e], m=ms[e]）：
    #   "kk"→(row k, col k) · "km"→(row k, col m) · "mm"→(row m, col m) · "mk"→(row m, col k)
    smap = {"kk": s_kk, "km": s_km, "mm": s_mm, "mk": s_mk}
    rows, cols, vals = [], [], []
    for grp, slots in ((grp_nn, ("kk", "km", "mm", "mk")),
                       (grp_kd, ("mm",)),
                       (grp_md, ("kk",))):
        idx = np.flatnonzero(grp)
        if idx.size == 0:
            continue
        for tag in slots:
            row_node = ks[idx] if tag in ("kk", "km") else ms[idx]
            col_node = ks[idx] if tag in ("kk", "mk") else ms[idx]
            rows.append(row_node)
            cols.append(col_node)
            vals.append(smap[tag][idx])
    R = np.concatenate(rows) if rows else np.zeros(0, dtype=np.int64)
    C = np.concatenate(cols) if cols else np.zeros(0, dtype=np.int64)
    V = np.concatenate(vals) if vals else np.zeros(0)
    M = sp.csr_matrix((V, (R, C)), shape=(n_si, n_si)).tolil()
    # ---- RHS：已知端移入（b[对侧行] += r·(已知值)）----
    b = np.zeros(n_si)
    if np.any(grp_kd):
        idx = np.flatnonzero(grp_kd)
        np.add.at(b, ms[idx], r_kd[idx] * _bc_arr(flag, mask, dev, psi)[ks[idx]])
    if np.any(grp_md):
        idx = np.flatnonzero(grp_md)
        np.add.at(b, ks[idx], r_md[idx] * _bc_arr(flag, mask, dev, psi)[ms[idx]])
    # ---- 接触行置恒等 ----
    bcv = _bc_arr(flag, mask, dev, psi)
    for kk in np.flatnonzero(reach):
        M.rows[int(kk)] = [int(kk)]
        M.data[int(kk)] = [1.0]
        b[int(kk)] = bcv[int(kk)]
    try:
        sol = spla.spsolve(M.tocsc(), b)
    except Exception:
        return np.full(n_si, np.nan)
    if not np.all(np.isfinite(sol)):
        return np.full(n_si, np.nan)
    return np.asarray(sol, dtype=float)


def _bc_arr(flag: str, mask: Dict, dev: Dict, psi: np.ndarray) -> np.ndarray:
    """接触载流子 BC（压缩编号数组）—— `n`/`p` 二选一。

    依赖当前 ψ（`n_k = n_i·e^{(ψ_k−V_c)/V_T}`）⇒ **每轮 Gummel 重算**（不能缓存）。
    """
    n_arr, p_arr = _contact_carriers(mask, psi, dev)
    return n_arr if flag == "n" else p_arr


# ===========================================================================
# ③ Gummel 泊松内环（φ_n / φ_p 为**逐节点数组**）
# ===========================================================================
def _solve_poisson_gummel(dev: Dict, dir_tab: Dict, phi_n: np.ndarray,
                          phi_p: np.ndarray, psi_init: np.ndarray,
                          max_iter: int = 40, resid_tol: float = 1e-8,
                          step_cap: float = 0.15, damp: float = 1.0) -> Dict:
    """阻尼牛顿解 BL 泊松，ρ = q(p − n + N_D − N_A)，
    `n = n_i·e^{(ψ−φ_n)/V_T}`、`p = n_i·e^{(φ_p−ψ)/V_T}`（**逐节点**准费米势）。

    🔴 与 mos_2d `_solve_poisson` 的唯一区别：那里的 φ_n 是 `V_d·w_ramp`（静态
    线性 ramp），这里是 Gummel 每轮由 n/p 反推的**数组**。矩阵结构（M_dir 缓存 +
    每轮只加对角）与残差/雅可比定义完全一致。

    雅可比符号（E12 血案，本轮再次守住）：`dρ/dψ = −（q/V_T)(n+p)` ⇒
    `J = M_dir + diag(dρ/dψ·V)`（**加**，不是减）。
    """
    M, vol = dev["M"], dev["vol"]
    M_dir, idx = _dir_matrix_nplus(dev)
    NA, ND, in_ox = dev["NA_f"], dev["ND_f"], dev["in_ox_f"]
    v_t, n_i = dev["v_t"], dev["n_i"]
    val = dir_tab["val"]
    psi = psi_init.copy()
    psi[idx] = val
    converged = False
    resid = float("inf")
    it = 0
    for it in range(1, max_iter + 1):
        e_n = np.exp(np.clip((psi - phi_n) / v_t, -BOLTZ_CLIP, BOLTZ_CLIP))
        e_p = np.exp(np.clip((phi_p - psi) / v_t, -BOLTZ_CLIP, BOLTZ_CLIP))
        n = n_i * e_n
        p = n_i * e_p
        rho = Q_E * (p - n + ND - NA)
        drho = -(Q_E / v_t) * (n + p)
        rho = np.where(in_ox, 0.0, rho)
        drho = np.where(in_ox, 0.0, drho)
        r = M.dot(psi) + rho * vol
        extra = drho * vol
        extra[idx] = 0.0
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
        psi[idx] = val
        np.clip(psi, PSI_FLOOR, None, out=psi)
        resid = float(np.max(np.abs(delta)))
        if resid < resid_tol:
            converged = True
            break
    return {"psi": psi, "converged": converged, "n_iter": it, "resid": resid}


# ===========================================================================
# ④ 终端电流（SG 守恒电流跨接触平面）
# ===========================================================================
def terminal_current(flag: str, psi: np.ndarray, carrier_si: np.ndarray,
                     mask: Dict, dev: Dict, side: str = "drain") -> float:
    """跨接触前最后一条 Si 内边的 SG 守恒电流（沿 y 积分），单位 A/m。

    `∇·J = 0 ⇒` 电流沿 x 守恒 ⇒ 取接触前最后一条内边即可（避免 `np.gradient`
    数值噪声，与 dd2d 同法）。`side="drain"` 取 (nx−2)→(nx−1) 边；
    `side="source"` 取 (0)→(1) 边（用于**源≡漏守恒**判据）。

    🔴 **两端不再取负**：`∇·J=0` ⇒ `J_x` 在器件内**是同一个常数**
    （1D 极限下严格；2D 下 J_y≠0 但 x 向净通量仍守恒）⇒ 两个截面上的 `J_x`
    应当**数值相等**，这正是 G4 判据的内容。初版误加 `−J` 导致
    `conservation_rel = 2.0`（电流反号），已修正。
    """
    nx, ny = int(dev["nx"]), int(dev["ny"])
    ids = np.arange(nx * ny).reshape(nx, ny)
    pos = mask["pos"]
    si2d = ~dev["in_ox"]
    si_idx = np.flatnonzero(mask["si"])
    eta = psi[si_idx] / dev["v_t"]
    mu = MU_N if flag == "n" else MU_P
    g = Q_E * mu * dev["v_t"]
    tot = 0.0
    for j in range(ny):
        if not (si2d[0, j] and si2d[1, j]):
            continue
        if not (si2d[nx - 2, j] and si2d[nx - 1, j]):
            continue
        if side == "source":
            i0, i1 = 0, 1
        else:
            i0, i1 = nx - 2, nx - 1
        k = int(pos[int(ids[i0, j])])
        m = int(pos[int(ids[i1, j])])
        h = float(dev["x"][i1] - dev["x"][i0])
        dy = float(dev["y"][j + 1] - dev["y"][j]) if j + 1 < ny \
            else float(dev["y"][j] - dev["y"][j - 1])
        a_km = float(_bern(eta[k] - eta[m]))
        a_mk = float(_bern(eta[m] - eta[k]))
        if flag == "n":
            J = (g / h) * (carrier_si[k] * a_km - carrier_si[m] * a_mk)
        else:
            J = (g / h) * (carrier_si[m] * a_km - carrier_si[k] * a_mk)
        tot += J * dy
    return float(tot)


def drain_current(psi: np.ndarray, n_si: np.ndarray, p_si: np.ndarray,
                  mask: Dict, dev: Dict) -> Dict:
    """漏端总电流 = 电子 + 空穴（A/m），并给出源端作守恒校验。"""
    jn_d = terminal_current("n", psi, n_si, mask, dev, "drain")
    jp_d = terminal_current("p", psi, p_si, mask, dev, "drain")
    jn_s = terminal_current("n", psi, n_si, mask, dev, "source")
    jp_s = terminal_current("p", psi, p_si, mask, dev, "source")
    I_d = jn_d + jp_d
    I_s = jn_s + jp_s
    denom = max(abs(I_d), abs(I_s), 1e-30)
    return {"I_d": float(I_d), "I_s": float(I_s),
            "I_n_drain": float(jn_d), "I_p_drain": float(jp_d),
            "conservation_rel": float(abs(I_d - I_s) / denom)}


# ===========================================================================
# ⑤ Gummel 主循环（MOS 版）
# ===========================================================================
def _phi_from_carriers(psi: np.ndarray, n_si: np.ndarray, p_si: np.ndarray,
                       mask: Dict, dev: Dict) -> Tuple[np.ndarray, np.ndarray]:
    """由 (ψ, n, p) 反推准费米势场（Si 上取值，氧化层置 0）。

    `φ_n = ψ − V_T·ln(n/n_i)`、`φ_p = ψ + V_T·ln(p/n_i)`（玻尔兹曼反演）。
    接触节点处由 BC 保证反推回 `V_接触`（自洽）。
    """
    v_t, n_i = dev["v_t"], dev["n_i"]
    si_idx = np.flatnonzero(mask["si"])
    n_safe = np.maximum(n_si, 1e-40)
    p_safe = np.maximum(p_si, 1e-40)
    psi_si = psi[si_idx]
    ph_n = np.zeros(psi.size)
    ph_p = np.zeros(psi.size)
    ph_n[si_idx] = psi_si - v_t * np.log(n_safe / n_i)
    ph_p[si_idx] = psi_si + v_t * np.log(p_safe / n_i)
    return ph_n, ph_p


def solve_mos2d_iv_point(Vg: float, Vd: float = 0.05, Vb: float = 0.0,
                         Vs: float = 0.0, device: Optional[Dict] = None,
                         VFB: float = VFB_DEFAULT, max_outer: int = 60,
                         damp: float = 0.5, resid_tol: float = 1e-4,
                         poisson_max_iter: int = 40, poisson_resid_tol: float = 1e-8,
                         step_cap: float = 0.15, warm: Optional[np.ndarray] = None,
                         return_fields: bool = True, **dev_kw) -> Dict:
    """解 2D MOS 漂移扩散**单工作点**（Gummel 交替：泊松 ⟷ 连续性）。

    🔴 与 E12 静电解的差别：这里解**电子/空穴连续性方程** ⇒ 有真实电流。
    🔴 冷暖启动：`warm` = 上一工作点的 ψ（V_g 扫描时的关键加速）。
       **有 warm 就不再跑 continuation**（E12 血案：continuation 只为冷启动存在，
       否则首步从 V_g/steps 起跳反而远离暖解）。

    返回 dict：psi / n / p（Si 上）/ I_d / I_s / 电流守恒 / 收敛信息。
    全部数值输出 `is_oracle=False`（T1 红线）。
    """
    dev = device if device is not None else mos2d_device(**dev_kw)
    mask = transport_masks(dev)
    _set_contact_V(mask, Vd, Vb, Vs)
    tab = transport_dirichlet(dev, Vg, Vd, Vb, Vs, VFB)

    if warm is not None:
        psi = np.asarray(warm, dtype=float).copy()
    else:
        psi = _initial_guess(dev, tab)
    psi = psi.copy()
    psi[tab["idx"]] = tab["val"]

    phi_n, phi_p = _contact_potentials(mask, Vg, Vd, Vb, Vs, dev)
    n_si = np.zeros(mask["n_si"])
    p_si = np.zeros(mask["n_si"])

    converged = False
    diff = float("inf")
    outer = 0
    for outer in range(1, int(max_outer) + 1):
        sol_p = _solve_poisson_gummel(dev, tab, phi_n, phi_p, psi,
                                      max_iter=poisson_max_iter,
                                      resid_tol=poisson_resid_tol,
                                      step_cap=step_cap)
        psi_new = sol_p["psi"]
        diff = float(np.max(np.abs(psi_new - psi)))
        psi = psi + float(damp) * (psi_new - psi)
        psi[tab["idx"]] = tab["val"]
        np.clip(psi, PSI_FLOOR, None, out=psi)

        n_new = _continuity_sg_si("n", psi, mask, dev)
        p_new = _continuity_sg_si("p", psi, mask, dev)
        if not (np.all(np.isfinite(n_new)) and np.all(np.isfinite(p_new))):
            break
        n_si, p_si = n_new, p_new
        phi_n, phi_p = _phi_from_carriers(psi, n_si, p_si, mask, dev)
        if diff < resid_tol:
            converged = True
            break

    # 收敛保护：用最终 ψ 再解一次连续性，确保 n/p 与 ψ 严格自洽（电流守恒）
    n_chk = _continuity_sg_si("n", psi, mask, dev)
    p_chk = _continuity_sg_si("p", psi, mask, dev)
    if np.all(np.isfinite(n_chk)) and np.all(np.isfinite(p_chk)):
        n_si, p_si = n_chk, p_chk

    cur = drain_current(psi, n_si, p_si, mask, dev)
    out = {
        "Vg": float(Vg), "Vd": float(Vd), "Vb": float(Vb), "Vs": float(Vs),
        "V_FB": float(VFB), "Lg": float(dev["geom"]["Lg"]),
        "I_d": cur["I_d"], "I_s": cur["I_s"],
        "I_n_drain": cur["I_n_drain"], "I_p_drain": cur["I_p_drain"],
        "conservation_rel": cur["conservation_rel"],
        "converged": bool(converged), "n_outer": int(outer), "dpsi": float(diff),
        "n_si": int(mask["n_si"]),
        "provenance": "self_authored_t1_candidate", "is_oracle": False,
    }
    if return_fields:
        sidev = _side_dim(dev)
        out["psi"] = psi.reshape(dev["nx"], dev["ny"])
        out["n_map"] = _si_to_map(n_si, mask, dev)
        out["p_map"] = _si_to_map(p_si, mask, dev)
        out["side_m"] = sidev
    return out


def _side_dim(dev: Dict) -> float:
    """2D 仿真的「宽度方向」尺寸（= y 向器件总深，仅用于口径说明，非 W）。"""
    return float(dev["geom"]["Ty"])


def _si_to_map(v_si: np.ndarray, mask: Dict, dev: Dict) -> np.ndarray:
    """Si 压缩编号向量 → (nx, ny) 全场图（氧化层节点填 NaN）。"""
    out = np.full(dev["nx"] * dev["ny"], np.nan)
    out[np.flatnonzero(mask["si"])] = v_si
    return out.reshape(dev["nx"], dev["ny"])


# ===========================================================================
# ⑥ I–V 扫描 / 亚阈值摆幅 / 恒定电流法 Vth
# ===========================================================================
def sweep_id_vg(Vd: float = 0.05, Vg_list=None, Vb: float = 0.0, Vs: float = 0.0,
                device: Optional[Dict] = None, VFB: float = VFB_DEFAULT,
                vg_max: float = VG_MAX_DEFAULT, vg_step: float = VG_STEP_DEFAULT,
                **kw) -> Dict:
    """扫 V_g 得转移特性 I_d(V_g)（**暖启动链式**：前一点解作后一点初值）。

    返回 {points: [{Vg, I_d, I_s, conservation_rel, converged, n_outer}], ...}
    """
    dev = device if device is not None else mos2d_device(**kw.pop("dev_kw", {}))
    if Vg_list is None:
        k = int(round(float(vg_max) / max(float(vg_step), 1e-9)))
        Vg_list = [round(i * float(vg_step), 6) for i in range(k + 1)]
    pts = []
    warm = None
    for vg in Vg_list:
        s = solve_mos2d_iv_point(vg, Vd=Vd, Vb=Vb, Vs=Vs, device=dev, VFB=VFB,
                                 warm=warm, return_fields=True, **kw)
        warm = s["psi"].flatten()
        pts.append({k2: s[k2] for k2 in
                    ("Vg", "I_d", "I_s", "conservation_rel", "converged", "n_outer",
                     "dpsi")})
    return {"Vd": float(Vd), "points": pts, "Lg": float(dev["geom"]["Lg"]),
            "is_oracle": False}


def subthreshold_swing(pts, lo_rel: float = 1.0e-7, hi_rel: float = 1.0e-3,
                       i_max: Optional[float] = None) -> Dict:
    """亚阈值摆幅 SS = dV_g / d(log10 |I_d|)（mV/dec）—— 窗口内最小二乘拟合。

    🔴 **窗口按 `I_max` 的相对量级取**（跨器件/栅长可移植）。血案：绝对窗口
    `[1e-9, 1e-4] A/m` 在 0.1 µm 器件上**一个点都不落**（实测 I_on ≈ 1.2e3 A/m、
    I_off ≈ 1.5e-3 A/m）⇒ `SS = nan`，看起来像"没算出来"，其实是**窗口错位**。
    相对口径：`|I_d| ∈ [i_max·lo_rel, i_max·hi_rel]`（默认 7 → 3 个数量级）。

    物理锚：**扩散机制下 SS ≥ 60 mV/dec**（室温 `kT/q·ln10`）—— 见判据 G1。
    """
    mags = [abs(p["I_d"]) for p in pts if p["converged"]]
    if not mags:
        return {"SS_mv_dec": float("nan"), "n_points": 0, "method": "no_converged"}
    imax = float(i_max) if i_max is not None else max(mags)
    I_lo, I_hi = imax * float(lo_rel), imax * float(hi_rel)
    xs, ys = [], []
    for p in pts:
        mag = abs(p["I_d"])
        if I_lo <= mag <= I_hi and p["converged"]:
            xs.append(float(p["Vg"]))
            ys.append(math.log10(mag))
    if len(xs) < 2:
        return {"SS_mv_dec": float("nan"), "n_points": len(xs),
                "window_a_per_m": [I_lo, I_hi], "method": "insufficient"}
    if len(xs) == 2:
        ss = (xs[1] - xs[0]) / (ys[1] - ys[0]) * 1e3
        method = "two_point"
    else:
        A = np.vstack([np.asarray(xs), np.ones(len(xs))]).T
        slope, _ = np.linalg.lstsq(A, np.asarray(ys), rcond=None)[0]
        ss = 1.0 / slope * 1e3
        method = "least_squares"
    return {"SS_mv_dec": float(ss), "n_points": len(xs),
            "window_a_per_m": [float(I_lo), float(I_hi)],
            "i_max_a_per_m": imax, "method": method,
            "Vg_span": [min(xs), max(xs)], "logI_span": [min(ys), max(ys)],
            "abnormal_below_thermal_limit": bool(ss < SS_THERMAL_LIMIT_MV_DEC)}


def i_on_off(pts, v_dd: float = V_DD_DEFAULT) -> Dict:
    """I_on / I_off（取扫描两端；`V_g=0` 为 off、`V_g=max` 为 on）。"""
    if not pts:
        return {"I_on": float("nan"), "I_off": float("nan"), "ratio": float("nan")}
    i_off = abs(pts[0]["I_d"])
    i_on = abs(pts[-1]["I_d"])
    return {"I_on": float(i_on), "I_off": float(i_off),
            "ratio": float(i_on / i_off) if i_off > 0 else float("inf"),
            "V_dd_note": float(v_dd)}


def vth_constant_current(pts, i_ref: Optional[float] = None,
                         lg_m: Optional[float] = None,
                         i_ref_0_a: float = I_REF_NORM_A) -> Dict:
    """**恒定电流法** V_th：`|I_d| = i_ref` 处的 V_g（log 域线性插值）。

    🔴 `i_ref` 缺省 = `i_ref_0_a / Lg`（默认 `i_ref_0_a = 100 nA`）—— 这是把经典
    判据 `I_d = 100 nA × (W/L)` 按 **`W = 1 m`（2D 仿真的"每米宽度"口径）** 归一后的
    结果，单位 A/m。**必须随 Lg 变**：若用固定绝对电流，不同栅长的 V_th 就不可比
    （短沟道电流大、长沟道电流小，同一 i_ref 落在完全不同的工作点）。
    这是**教科书惯例口径，非标定**。与 E12 的「界面最低表面势达 +φ_F」表面势法
    **互相独立** ⇒ 可作交叉验证（判据 G6）。
    """
    if i_ref is None:
        i_ref = (float(i_ref_0_a) / float(lg_m)) if lg_m else I_REF_A_PER_M
        auto = True
    else:
        auto = False
    for i in range(1, len(pts)):
        a, b = pts[i - 1], pts[i]
        ia, ib = abs(a["I_d"]), abs(b["I_d"])
        if ia < i_ref <= ib and ia > 0.0 and ib > 0.0:
            t = (math.log10(i_ref) - math.log10(ia)) / (math.log10(ib) - math.log10(ia))
            return {"V_th_cc_v": float(a["Vg"] + t * (b["Vg"] - a["Vg"])),
                    "i_ref_a_per_m": float(i_ref), "i_ref_auto": bool(auto),
                    "interpolated": True,
                    "bracket": [float(a["Vg"]), float(b["Vg"])]}
    return {"V_th_cc_v": float("nan"), "i_ref_a_per_m": float(i_ref),
            "i_ref_auto": bool(auto), "interpolated": False, "bracket": None}


# ===========================================================================
# ⑦ 教科书闭式 golden（科学原理层公共品 · 可作 golden）
# ===========================================================================
def ss_closed_form(N_A: float = N_A_DEFAULT, t_ox: float = T_OX_DEFAULT,
                   t_kelvin: float = 300.0, eps_si: float = EPS_SI,
                   eps_ox: float = EPS_OX, n_i: float = N_I) -> Dict:
    """**教科书亚阈值摆幅闭式**（耗尽近似）—— 判据 G2 的 golden。

        SS = (k_B·T/q)·ln10 · (1 + C_d/C_ox)
        C_d  = ε_si / W_dm,  W_dm = √(2·ε_si·2φ_F/(q·N_A))
        C_ox = ε_ox / t_ox

    🔴 **为什么不是「SS → 60」**：`60 mV/dec`（`(kT/q)·ln10`）是**理想极限**，
    只在 `C_d → 0` 时达到（FD-SOI / 双栅 / 极薄体）。**体硅器件因体效应**
    （`C_d/C_ox > 0`）收敛到 **> 60 的平台**。实测（本内核 · N_A=1e17 cm⁻³ ·
    t_ox=4 nm）：`L_g = 1 µm` ⇒ **SS = 68.18 mV/dec**，本闭式 ⇒ **66.41 mV/dec**
    （**rel 2.7 %**）—— 这是一条独立的「教科书闭式 ⟷ 数值输运」交叉验证。

    60 的正确角色是**硬下限**（判据 G1：任何数值解 < 60 即数值假象），不是渐近目标。
    """
    v_t = K_B * float(t_kelvin) / Q_E
    phi_f = v_t * math.log(float(N_A) / n_i)
    w_dm = math.sqrt(2.0 * eps_si * 2.0 * phi_f / (Q_E * float(N_A)))
    c_d = eps_si / w_dm
    c_ox = eps_ox / float(t_ox)
    ratio = c_d / c_ox
    ss_ideal = v_t * math.log(10.0) * 1e3
    return {"SS_mv_dec": float(ss_ideal * (1.0 + ratio)),
            "SS_ideal_mv_dec": float(ss_ideal),
            "Cd_over_Cox": float(ratio), "W_dm_m": float(w_dm),
            "phi_F_v": float(phi_f),
            "C_d_f_per_m2": float(c_d), "C_ox_f_per_m2": float(c_ox),
            "provenance": "textbook_closed_form_subthreshold", "is_oracle": True}


def ss_vs_length_closed_form(Ls_nm=(65.0, 100.0, 250.0, 1000.0),
                             **kw) -> Dict:
    """闭式 SS(L) —— 长沟道**与 L 无关**（平台），仅作数值结果的对照基准。"""
    g = ss_closed_form(**kw)
    return {"SS_platform_mv_dec": g["SS_mv_dec"],
            "points": [{"Lg_nm": float(L), "SS_closed_mv_dec": g["SS_mv_dec"]}
                       for L in Ls_nm],
            "is_oracle": True}


# ===========================================================================
# ⑧ 自检（轻量 · 门禁同源调用）
# ===========================================================================
def run_selfchecks(verbose: bool = True) -> bool:
    """模块自检：掩码 / 接触定义 / 平衡零电流 / 收敛+守恒 / 闭式 / V_d 单调。"""
    msgs = []

    def chk(name, cond, det=""):
        msgs.append((name, bool(cond), det))
        return bool(cond)

    ok = True
    dev = mos2d_device(Lg=100e-9)
    m = transport_masks(dev)

    # ① Si 节点集 = 总节点 − 氧化层节点
    n_ox = int(dev["in_ox"].sum())
    ok &= chk("① Si 掩码：n_si = 总节点 − 氧化层节点",
              m["n_si"] == dev["nx"] * dev["ny"] - n_ox,
              "n_si=%d（总 %d − 氧化层 %d）" % (m["n_si"], dev["nx"] * dev["ny"], n_ox))

    # ② 接触定义：源/漏只含 n⁺（E13 修正）+ 衬底
    kinds = sorted({k for k in m["kind"] if k})
    n_plus = int((dev["ND"] > dev["NA"]).flatten()[np.flatnonzero(m["si"])].sum())
    n_src = int((m["kind"] == "src").sum())
    ok &= chk("② 接触定义：源/漏**只含 n⁺**（不整列）+ 衬底",
              kinds == ["drn", "src", "sub"] and n_src <= n_plus,
              "kinds=%s · src=%d ≤ n⁺ 总数 %d" % (kinds, n_src, n_plus))

    # ③ 平衡（V_d = 0）⇒ 漏端电流 ≈ 0（无假注入）
    s0 = solve_mos2d_iv_point(-0.5, Vd=0.0, device=dev, return_fields=False)
    ok &= chk("③ 平衡（V_d=0）漏端电流 ≈ 0 ⇒ 无假注入通道",
              abs(s0["I_d"]) < 1e-7,
              "|I_d| = %.3e A/m" % abs(s0["I_d"]))

    # ④ 工作点收敛 + 电流守恒（大电流点，避免低电流下相对判据失效）
    s1 = solve_mos2d_iv_point(0.8, Vd=0.05, device=dev, return_fields=False)
    ok &= chk("④ 工作点收敛 + 电流守恒（源≡漏 · rel < 1e-3）",
              s1["converged"] and s1["conservation_rel"] < 1e-3,
              "I_d=%.4e · rel=%.2e · outer=%d" % (s1["I_d"], s1["conservation_rel"],
                                                  s1["n_outer"]))

    # ⑤ 教科书 SS 闭式：> 60（体效应）且 < 200（量级合理）
    g = ss_closed_form()
    ok &= chk("⑤ 教科书 SS 闭式 ∈ (60, 200) mV/dec（体效应 ⇒ 高于理想极限）",
              60.0 < g["SS_mv_dec"] < 200.0,
              "SS=%.2f（理想 %.2f · Cd/Cox=%.4f）"
              % (g["SS_mv_dec"], g["SS_ideal_mv_dec"], g["Cd_over_Cox"]))

    # ⑥ 低 V_d 线性区：I_d 随 V_d 单调增
    a = solve_mos2d_iv_point(0.6, Vd=0.02, device=dev, return_fields=False)
    b = solve_mos2d_iv_point(0.6, Vd=0.10, device=dev, return_fields=False)
    ok &= chk("⑥ 低 V_d 线性区：I_d 随 V_d 单调增",
              abs(b["I_d"]) > abs(a["I_d"]) > 0.0,
              "Vd=0.02→%.3e · Vd=0.10→%.3e A/m" % (a["I_d"], b["I_d"]))

    if verbose:
        for nm, c, det in msgs:
            print(("  [PASS] " if c else "  [FAIL] ") + nm + ((" :: " + det) if det else ""))
        print("  —— mos_2d_transport 自检 %d/%d ——"
              % (sum(1 for _, c, _ in msgs if c), len(msgs)))
    return ok


if __name__ == "__main__":
    print("=== mos_2d_transport 自检 ===")
    run_selfchecks(verbose=True)
    print("=== 教科书 SS 闭式（golden）===")
    gg = ss_closed_form()
    print("  SS = %.2f mV/dec（理想 %.2f · W_dm = %.2f nm · Cd/Cox = %.4f）"
          % (gg["SS_mv_dec"], gg["SS_ideal_mv_dec"], gg["W_dm_m"] * 1e9,
             gg["Cd_over_Cox"]))
    print("=== 转移特性 I_d(V_g)（Lg = 100 nm · V_d = 0.05 V）===")
    dev = mos2d_device(Lg=100e-9)
    vg = [round(-0.6 + 0.05 * i, 4) for i in range(33)]
    sw = sweep_id_vg(Vd=0.05, Vg_list=vg, device=dev)
    print("   %6s %14s %11s" % ("Vg(V)", "I_d(A/m)", "cons_rel"))
    for p in sw["points"][::3]:
        print("   %+6.2f %14.4e %11.2e" % (p["Vg"], p["I_d"], p["conservation_rel"]))
    ss = subthreshold_swing(sw["points"])
    print("  SS = %.2f mV/dec（%s · %d 点 · 窗口 %.1e..%.1e A/m）"
          % (ss["SS_mv_dec"], ss["method"], ss["n_points"],
             ss["window_a_per_m"][0], ss["window_a_per_m"][1]))
    print("  V_th(恒流法 · 100nA×(1m/Lg)) = %.4f V"
          % vth_constant_current(sw["points"], lg_m=100e-9)["V_th_cc_v"])
