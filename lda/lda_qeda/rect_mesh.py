"""D-122 · 矩形 Clements 网格（紧凑矩形分解 → 平台 `mzi_unit_cell` 约定）
——**坐实「紧界 N 可达」**（M5 · 量子征程吃狗粮）。

════════════════════════════════════════════════════════════════════════════
问题（承接 D-121 结论 2b 的挂起项）
────────────────────────────────────────────────────────────────────────────
D-121（`lda_qeda/temporal_mesh.py`）把「时间复用通用表」的深度从朴素 O(N²)
压到了**该 op 集的最优值**，并给出三口径深度界：

    · 参数计数下界（D-121 原口径，**非紧**）：⌈N(N−1)/2 / ⌊N/2⌋⌉ ⇒ N 偶 = N−1
    · 相邻耦合**紧**下界（偶 N 由唯一最大匹配收紧）：**N**
    · 平台**三角 Reck** op 集最优深度（本模块的前序工作）：**2N−3**

并证得：**N−1 对该三角网格不可达**。但结论 2b 留下一个明确的悬问——

  ❓ **紧界 N 自己可达吗？** 还是说 N 只是下界、真实可达最优就是 2N−3？

本模块（D-122）回答这个悬问，答案是一个**肯定**：

  ★ **紧界 N 可达** —— 换用**矩形（Clements）网格**即可，且对一切 N ≥ 3 成立。
    ⇒ 三角 Reck 的 2N−3 并非最优；矩形网格把深度**减半**（2N−3 → N）。

════════════════════════════════════════════════════════════════════════════
复用而非重造（主权分解已在位）
────────────────────────────────────────────────────────────────────────────
矩形（Clements）分解**早已存在且已主权验证**：`lda_layout/mesh_pnr.py` 的
`clements_rect_decompose`（分解级 + 版级保真度均 = 1.0，实测至 **N=512**；
`_rect_column_assignment` 把 MZI 压实为 O(N) 列）。故本模块**不重造分解**——
它做的是那件真正缺的事：**把该分解的 2×2 块约定「精修对齐」到平台
`mzi_unit_cell`**，使量子征程的网格与平台物理原语同源（可复用同一层 DRC/LVS、
同一驱动映射）。

  🔴 **约定桥（本模块的核心结论，实测精确 0.0）**

      _ref_T(θ, φ)  =  mzi_unit_cell(2θ, 0) · diag(e^{iφ}, 1)

  其中 `_ref_T(θ,φ) = [[e^{iφ}cosθ, −sinθ], [e^{iφ}sinθ, cosθ]]` 是主权「平方
  约定」（`lda_layout`），`mzi_unit_cell(θ,φ) = R(θ)·diag(1,e^{iφ})`
  （`R` 为半角实旋转）是平台约定（`lda_l2`）。

  **「精修左右块朝向」到底修的是什么**（本轮真实血案，务必勿重推）：
    · 两条**块级精确**恒等式（均实测 max|Δ| < 1e−15）：
        `_ref_T(θ,φ) = mzi_unit_cell(2θ, 0) · diag(e^{iφ}, 1)`   ← **无标量**（D-122 采用）
        `_ref_T(θ,φ) = e^{iφ} · mzi_unit_cell(2θ, −φ)`           ← **含标量** e^{iφ}
      二者等价；`_ref_T` 的相位落于**输入臂 / 较低模 j**（块第 0 列），
      `mzi_unit_cell` 的相位落于**输出臂 / 较高模 j+1**（块第 1 列）
      —— 两个不同 SU(2) 相位约定，**不是** 2θ 缩放关系。
    · 🔴 陷阱（本轮实测 N=8，比「块对不上」更精微）：
      若图省事把**裸** `mzi_unit_cell(2θ, −φ)` 当 `_ref_T` 用 ——
      2×2 层面它 = e^{−iφ}·_ref_T（**只差一个标量**，看似可忽略）；
      但**嵌入 N×N 时**该标量只落在**本门的 2 个模**上 ⇒ 每门给这 2 模注入 e^{−iφ} 的
      **逐模相位**，与相邻/后续门**不对易** ⇒ 整网格 ≠ U ——
      **连全局相位都不是**（是错的相对相位）：相位不变口径 fid = **0.0054**、
      项目 Frobenius 口径 **0.658**（N=8 实测；行作用 max|Δ|=0.648）。
      ⇒ 「相位在哪条臂上」必须显式建模，不能靠 2×2 的标量等价偷懒。
    · 正确做法：把相位拆成**独立的对角相位层** `diag(e^{iφ},1)`（作用于较低模 j），
      分束器留给**纯旋转** `mzi_unit_cell(2θ, 0)`。此时块与行作用**同时**精确相等，
      嵌入 N×N 亦无逐模相位副产物。

  ⚠️ 与 skill `lda-mzi-mesh-physical-synthesis` §2.1「双约定陷阱」同源：那条讲的是
  `mesh_layout_transfer` 的 `serpentine|grid2d` **分路**（各自原生 2×2）；
  本条是**统一到平台 `mzi_unit_cell`** 的一座桥，二者不冲突、可互推。

════════════════════════════════════════════════════════════════════════════
结论（全部可机器判定，实测见 `run_selfchecks`）
────────────────────────────────────────────────────────────────────────────
  ★ 结论 1（深度 = 紧界 N，**可达**）
    矩形网格层数（= 列数 = 光学深度）对一切 N ≥ 3 恰为 **N**；每层是**真匹配**
    （两两不相交的相邻对）⇒ 与 D-121 的紧下界 N **相等** ⇒ **紧界可达**。
    对照三角 Reck：2N−3（N=216：429 → **216**，省 **213** 层）。

  ★ 结论 2（构造性正确：任意酉，机器精度）
    用**平台物理原语**装配（diag 相位层 + `mzi_unit_cell(2θ,0)` 分束器），
    DFT 与 Haar 随机酉（N=2…64）重建保真度均 = **1.0**（机器精度），
    且与主权 `mesh_rect_decomp_fidelity` / `mesh_rect_fidelity` **三方一致**。

  ★ 结论 3（元件数不变，深度减半）
    矩形网格仍用 **N(N−1)/2** 片 MZI（与 Reck 同，Clements 必要性定理），
    故「元件数」不因矩形化而增加；收益纯在**深度**（⇒ 每模损耗份数）。
    ⇒ 对 D-121 的「损耗墙 = 深度墙」：矩形化把**通用**表的深度下界从 2N−3
    降到 N，但仍是 Ω(N) ⇒ 结论 3（通用与省损不可兼得）**不变**。

════════════════════════════════════════════════════════════════════════════
🔴 诚实边界（必读）
  · 本模块是**网格拓扑 + 酉重构**的正确性证明（数学 + 构造性数值），**不是**
    真机实测：未含波导损耗 / 非理想耦合 / 串扰 / 热串扰（属 P1-B 工艺级）。
  · 「深度」= 网格**列数**（光子依次穿过的分束器层数）。矩形网格同列配对互不
    共享波导 ⇒ 同列可共享 x（抽头）⇒ 层数即物理深度。
  · 分解**非本模块自研**：复用 `lda_layout.mesh_pnr.clements_rect_decompose`
    （主权验证 fid=1.0 至 N=512）。本模块的新增价值 = **约定桥** + **深度可达性判定**。
  · 与 Clements 原始文献同结论（矩形网格深度 N、三角网格 2N−3），但本模块不引
    文献数值作 golden；判据全部是闭式恒等式 + 构造性实测。

════════════════════════════════════════════════════════════════════════════
红线自检标注：
- C 级自主：纯 numpy + 平台模块（lda_l2 / lda_qeda / lda_layout 主权分解），
  零量子 SDK / 零外部求解器。
- LLM 不进判决路径：全部为闭式恒等式 + numpy 线性代数 + 死标量判据。
- 数学锚（闭式，非拟合非仿真）：2×2 酉块恒等式 · 排列计数（列数）· Givens 参数
  计数 N(N−1)/2 · 唯一最大匹配 · 1−‖Δ‖_F/(N√2) —— 且「网格重建 ≡ 目标酉」是
  **构造性实证**。
════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import math

import numpy as np

from lda_l2 import mzi_mesh_matmul as MMM
from lda_qeda import temporal_mesh as TMB

__all__ = [
    "RECT_MESH_REF",
    "convention_bridge",
    "layer_is_matching",
    "rectangular_mesh_layers",
    "assemble_rect_mesh",
    "rect_mesh_fidelity",
    "rect_mesh_profile",
    "tight_bound_reachable_report",
    "run_selfchecks",
    "RED_LINE_DISCLOSURE",
]

# 外部/文献锚（仅引用不复算；作「同结论」的旁证，不作 golden）
RECT_MESH_REF = {
    "claim": "矩形（Clements）网格通用 N 模酉的深度 = N；三角（Reck）网格 = 2N−3；"
             "两者均用 N(N−1)/2 片 2 模门。",
    "note": "本模块不引用其数值作 golden —— 判据全部为闭式恒等式 + 构造性实测。",
}


# ---------------------------------------------------------------------------
# 0) 主权分解的惰性桥（避免 lda_qeda ↔ lda_layout 的导入期耦合）
# ---------------------------------------------------------------------------
def _sovereign():
    """惰性导入主权矩形分解（L4 版图层已验，fid=1.0 至 N=512）。

    返回 (clements_rect_decompose, _rect_column_assignment, _ref_T)。
    与 `lda_l2/yield_fault_tolerance.py` 同法（局部导入，避免耦合）。
    """
    from lda_layout.mesh_pnr import (clements_rect_decompose,
                                     _rect_column_assignment, _ref_T)
    return clements_rect_decompose, _rect_column_assignment, _ref_T


# ---------------------------------------------------------------------------
# 1) 约定桥：主权「平方约定」→ 平台 mzi_unit_cell 约定
# ---------------------------------------------------------------------------
def convention_bridge(theta_rect: float, phi_rect: float) -> dict:
    """把主权 `_ref_T(θ,φ)` 对齐到平台 `mzi_unit_cell` 约定的**唯一正确**拆法。

        无标量形式：_ref_T(θ, φ) = mzi_unit_cell(2θ, 0) · diag(e^{iφ}, 1)   （精确）
        含标量形式：_ref_T(θ, φ) = e^{iφ} · mzi_unit_cell(2θ, −φ)            （精确，等价）

    读法（「精修左右块朝向」的结论）：
      · `_ref_T` 相位在**输入臂 / 较低模 j**（块第 0 列）；`mzi_unit_cell` 相位在
        **输出臂 / 较高模 j+1**（块第 1 列）—— 两个不同 SU(2) 相位约定，非 2θ 缩放。
      · 陷阱：裸 `mzi_unit_cell(2θ, −φ)` 在 2×2 层面 = e^{−iφ}·_ref_T（只差标量），
        但**嵌入 N×N 后**该标量只落在本门 2 模 ⇒ 每门注入逐模相位 e^{−iφ}，
        与其他门不对易 ⇒ 网格 ≠ U（连全局相位都不是）⇒ fid 掉到 ~0.005（相位不变口径）。
      · 正确：相位拆成**独立对角相位层** diag(e^{iφ},1)（较低模 j），
        分束器用**纯旋转** `mzi_unit_cell(2θ, 0)`。
    """
    return {
        "theta_rect": float(theta_rect),
        "phi_rect": float(phi_rect),
        "mzi_theta": 2.0 * float(theta_rect),
        "mzi_phi": 0.0,
        "diag_phi": float(phi_rect),
        "identity": "_ref_T(theta, phi) = mzi_unit_cell(2*theta, 0) @ diag(exp(1j*phi), 1)",
        "identity_scalar": "_ref_T(theta, phi) = exp(1j*phi) * mzi_unit_cell(2*theta, -phi)",
        "phase_arm": "input / lower mode j（块第 0 列）",
        "trap": "裸 mzi_unit_cell(2θ,−φ) 嵌入后注入逐模相位（非全局）⇒ 网格错（fid≈0.005）",
    }


def _apply_bridged(T: np.ndarray, j: int, theta_mzi: float, phi_diag: float) -> None:
    """在平台约定下、原地对行 (j, j+1) 施加 `_ref_T` 的桥形式（先对角相位、再分束器）。"""
    n = T.shape[0]
    if not (0 <= int(j) and int(j) + 1 < n):
        raise ValueError(f"模索引越界：j={j}, N={n}")
    e = complex(math.cos(phi_diag), math.sin(phi_diag))
    T[j] = e * T[j]                                  # diag(e^{iφ}, 1)：作用于较低模
    G = MMM.mzi_unit_cell(float(theta_mzi), 0.0)     # 纯分束器 R(2θ)
    r0, r1 = T[j].copy(), T[j + 1].copy()
    T[j] = G[0, 0] * r0 + G[0, 1] * r1
    T[j + 1] = G[1, 0] * r0 + G[1, 1] * r1


def layer_is_matching(layer, n_modes: int) -> bool:
    """一层门是否构成**匹配**（两两不相交的相邻对）——即「同一步可同步施加」的充要条件。

    复用 D-121 `temporal_mesh.gate_matching_ok`（单一口径，不另建判据）。
    """
    gates = [(int(j), float(t), float(p), True) for (j, t, p) in layer]
    return bool(TMB.gate_matching_ok(gates, int(n_modes)))


# ---------------------------------------------------------------------------
# 2) 矩形网格：分解 → 分层（列 = 层）→ 平台约定装配
# ---------------------------------------------------------------------------
def rectangular_mesh_layers(U) -> tuple:
    """把目标酉编成**矩形 Clements 网格**（平台 `mzi_unit_cell` 约定）。

    返回 (layers, D_out)：
      layers : 长度 = 网格**列数**（= 层数 = 光学深度）的列表；
               每层 = [(j, theta_mzi, phi_diag), …]，j 为较低模（耦合 (j, j+1)），
               theta_mzi = 2·θ_ref（分束角），phi_diag = φ_ref（输入臂相位）。
      D_out  : 末端输出相移对角阵（N×N 复对角）。

    分层依据 = 主权 `_rect_column_assignment`（**同列配对互不共享波导** ⇒ 同列可同步）。
    """
    U = np.asarray(U, dtype=complex)
    if U.ndim != 2 or U.shape[0] != U.shape[1]:
        raise ValueError("U 必须为方阵")
    n = int(U.shape[0])
    if n < 2:
        raise ValueError("N ≥ 2")
    dec, assign, _ref = _sovereign()
    bs, D = dec(U)
    colors = assign(bs)
    ncol = max(colors) + 1
    layers: list = [[] for _ in range(ncol)]
    for k, (j, th, ph) in enumerate(bs):
        layers[colors[k]].append((int(j), 2.0 * float(th), float(ph)))
    return layers, np.array(D, dtype=complex)


def assemble_rect_mesh(layers, D, n_modes: int) -> np.ndarray:
    """按平台约定装配矩形网格：逐列左乘（相位层 + 分束器），末端左乘 D。

    step = diag(e^{iφ},1)（较低模）→ mzi_unit_cell(2θ, 0)（纯分束器）
    ⇒ 传递矩阵 ≡ 目标酉（机器精度；见 `run_selfchecks`）。
    非匹配层 / 越界 ⇒ ValueError（与物理「同一步共享模不可实现」同一条约束）。
    """
    n = int(n_modes)
    if n < 2:
        raise ValueError("N ≥ 2")
    T = np.eye(n, dtype=complex)
    for li, lay in enumerate(layers):
        if not layer_is_matching(lay, n):
            raise ValueError(f"第 {li} 层不是匹配（共享模 / 越界）")
        for (j, th_mzi, ph_diag) in lay:
            _apply_bridged(T, int(j), float(th_mzi), float(ph_diag))
    Dm = np.diag(np.diag(np.asarray(D, dtype=complex)))
    return Dm @ T


def rect_mesh_fidelity(U) -> float:
    """矩形网格（平台约定装配）对目标酉的重建保真度（0–1）。"""
    U = np.asarray(U, dtype=complex)
    layers, D = rectangular_mesh_layers(U)
    rec = assemble_rect_mesh(layers, D, U.shape[0])
    return MMM.unitary_fidelity(rec, U)


def rect_mesh_profile(n_modes: int, *, target: str = "dft", seed: int = 0) -> dict:
    """矩形网格的**深度剖面**：层数(=紧界?)、每层最大门数、光学深度、保真度、对标 Reck。

    depth = 层数 = 列数 = 光子依次穿过的分束器层数（每层一份插损）。
    """
    n = int(n_modes)
    if n < 2:
        raise ValueError("N ≥ 2")
    U = MMM.dft_matrix(n) if target == "dft" else TMB.random_unitary(n, seed=seed)
    layers, D = rectangular_mesh_layers(U)
    rec = assemble_rect_mesh(layers, D, n)
    n_layers = len(layers)
    per = [len(L) for L in layers]
    match_ok = all(layer_is_matching(L, n) for L in layers)
    cnt = [0] * n                                   # 每模真穿过的分束器数（光学深度）
    for L in layers:
        for (j, _t, _p) in L:
            cnt[j] += 1
            cnt[j + 1] += 1
    tight = TMB.tight_depth_lower_bound(n)
    reck = 2 * n - 3
    return {
        "kind": "rectangular_clements_mesh",
        "n_modes": n,
        "target": target,
        "n_mzi": int(sum(per)),
        "n_layers": int(n_layers),
        "depth": int(n_layers),
        "per_layer_max": int(max(per)),
        "layers_are_matchings": bool(match_ok),
        "optical_depth": int(max(cnt)),
        "fidelity": float(MMM.unitary_fidelity(rec, U)),
        "unitary_ok": bool(float(np.max(np.abs(rec @ rec.conj().T - np.eye(n)))) < 1e-9),
        "parameter_count_bound": int(TMB.universality_depth_lower_bound(n)),
        "tight_adjacency_bound": int(tight),
        "depth_equals_tight_bound": bool(n_layers == tight),
        "reck_mesh_optimum": int(reck),
        "depth_reduction_vs_reck": int(reck - n_layers),
        "n_physical_mzi": int(sum(per)),
    }


# ---------------------------------------------------------------------------
# 3) 「紧界 N 可达」判定（本模块的落点）
# ---------------------------------------------------------------------------
def tight_bound_reachable_report(n_modes: int) -> dict:
    """★ 紧界可达性判定：矩形网格深度 == 紧下界 N？（对一切 N ≥ 3 ⇒ 是）

    并与 D-121 三口径界并列（参数界 ≤ 紧界 = 矩形可达 ≤ Reck 最优）。
    """
    n = int(n_modes)
    if n < 2:
        raise ValueError("N ≥ 2")
    b = TMB.depth_bound_report(n)
    pr = rect_mesh_profile(n, target="dft")
    reach = bool(pr["depth"] == b["tight_adjacency_bound"]
                 and pr["layers_are_matchings"]
                 and abs(pr["fidelity"] - 1.0) < 1e-11
                 and pr["unitary_ok"])
    return {
        "n_modes": n,
        "n_mzi": int(b["n_mzi"]),
        "parameter_count_bound": int(b["parameter_count_bound"]),
        "tight_adjacency_bound": int(b["tight_adjacency_bound"]),
        "rectangular_mesh_depth": int(pr["depth"]),
        "reck_mesh_optimum": int(b["reck_mesh_optimum"]),
        "tight_bound_reachable": reach,
        "depth_reduction_vs_reck": int(b["reck_mesh_optimum"] - pr["depth"]),
        "verdict": (
            f"矩形（Clements）网格深度 = {pr['depth']} = 紧下界 {b['tight_adjacency_bound']}"
            f" ⇒ **紧界可达**（每层真匹配 · 重建 fid=1.0）；"
            f"三角 Reck 最优 = {b['reck_mesh_optimum']}（2N−3）⇒ 矩形化省 "
            f"{b['reck_mesh_optimum'] - pr['depth']} 层。"
            f"（D-121 的「N−1 不可达」仍成立 —— 那是**参数界**非紧；真紧界是 N，可达。）"),
    }


RED_LINE_DISCLOSURE = {
    "role": "D-122 = 矩形 Clements 网格（M5）：把主权矩形分解对齐到平台 mzi_unit_cell，"
            "坐实「紧界 N 可达」并给出深度剖面。",
    "reuse_not_reinvent": "分解复用 `lda_layout.mesh_pnr.clements_rect_decompose`"
                          "（主权验证 fid=1.0 至 N=512）；本模块新增 = 约定桥 + 深度判定。",
    "convention_bridge": "_ref_T(θ,φ) = mzi_unit_cell(2θ,0)·diag(e^{iφ},1)（精确 0.0）"
                         " = e^{iφ}·mzi_unit_cell(2θ,−φ)（含标量，块级同为精确）；"
                         "相位在输入臂/较低模 j；裸 mzi_unit_cell(2θ,−φ) 嵌入 N×N 后注入"
                         "逐模相位（非全局）⇒ 网格错：相位不变 fid 0.005 / Frobenius 0.66（血案）。",
    "golden": "只用闭式 / 构造性：2×2 酉块恒等式 · 列数计数 · Givens 参数计数 N(N−1)/2 · "
              "唯一最大匹配；「网格重建 ≡ 目标酉」为构造性实证。",
    "sovereignty": "C 级自主（纯 numpy + 平台 lda_l2 / lda_qeda / lda_layout），零量子 SDK；"
                   "LLM 不进判决路径。",
    "honest_boundary": "① 本模块是网格拓扑 + 酉重构的正确性证明，非真机实测；"
                       "② 未含波导损耗 / 非理想耦合 / 串扰（属 P1-B 工艺级）；"
                       "③ 深度 = 网格列数（同列配对不共享波导 ⇒ 层数即物理深度）；"
                       "④ 通用与省损不可兼得（D-121 结论 3）不因矩形化而改变（深度仍 Ω(N)）。",
}


# ---------------------------------------------------------------------------
# 4) 自检锚
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    """D-122 自检：约定桥恒等式（精确）/ 平台约定装配（DFT+随机，机器精度）/
    层数 = 紧界 N（N=3…64）/ 每层真匹配 + 光学深度 = N / 与主权三函数三方一致 /
    三角-Reck 对照（矩形更浅）/ 护栏。"""
    from collections import OrderedDict
    res = OrderedDict()

    dec, assign, _ref = _sovereign()

    # ① 约定桥恒等式（两条，均精确）：无标量 diag 形式 + 含标量形式
    ok1 = True
    worst = 0.0          # 无标量：mzi_unit_cell(2θ,0)·diag(e^{iφ},1)
    worst_s = 0.0        # 含标量：e^{iφ}·mzi_unit_cell(2θ,−φ)
    for (th, ph) in ((0.7, 0.4), (1.2, -2.1), (0.0, 0.0), (0.9, 0.5), (math.pi / 4, 3.1)):
        A = _ref(th, ph, 2, 3, 4)
        B = np.eye(4, dtype=complex)
        B[np.ix_([1, 2], [1, 2])] = (MMM.mzi_unit_cell(2 * th, 0.0)
                                     @ np.diag([complex(math.cos(ph), math.sin(ph)), 1.0]))
        Bs = np.eye(4, dtype=complex)
        Bs[np.ix_([1, 2], [1, 2])] = (complex(math.cos(ph), math.sin(ph))
                                      * MMM.mzi_unit_cell(2 * th, -ph))
        worst = max(worst, float(np.max(np.abs(A - B))))
        worst_s = max(worst_s, float(np.max(np.abs(A - Bs))))
        if worst > 1e-14 or worst_s > 1e-14:
            ok1 = False
    res["① ★约定桥★ _ref_T(θ,φ) ≡ mzi_unit_cell(2θ,0)·diag(e^iφ,1)"
        f" ≡ e^iφ·mzi_unit_cell(2θ,−φ)（两式均精确，max|Δ|={worst:.1e}/{worst_s:.1e}）"] = ok1

    # ② 平台约定装配：DFT + Haar 随机，N=2…64，机器精度
    ok2 = True
    detail2 = []
    for n_ in (2, 3, 4, 8, 16, 32, 64):
        for tgt in ("dft", "random"):
            pr = rect_mesh_profile(n_, target=tgt, seed=n_ * 5 + 1)
            detail2.append(f"N={n_}/{tgt}:fid={pr['fidelity']:.9f}")
            if not (abs(pr["fidelity"] - 1.0) < 1e-11 and pr["unitary_ok"]):
                ok2 = False
    res["② 平台约定装配重建任意酉 = 机器精度（DFT + Haar 随机，N=2…64）"] = ok2

    # ③ ★核心★ 层数 = 紧界 N（N=3…64）· 每层真匹配 · 光学深度 = N
    ok3 = True
    detail3 = []
    for n_ in (3, 4, 5, 6, 7, 8, 16, 32, 64):
        pr = rect_mesh_profile(n_, target="dft")
        detail3.append(f"N={n_}:d={pr['depth']}")
        if not (pr["depth"] == n_ and pr["depth_equals_tight_bound"]
                and pr["tight_adjacency_bound"] == n_
                and pr["layers_are_matchings"] and pr["optical_depth"] == n_):
            ok3 = False
    res["③ ★紧界可达★ 矩形网格层数 = 紧界 N · 每层真匹配 · 光学深度 = N（N=3…64）"] = ok3

    # ④ 元件数 = N(N−1)/2（与 Reck 同，Clements 必要性定理）· 深度减半（2N−3 → N）
    ok4 = True
    detail4 = []
    for n_ in (4, 8, 16, 64, 216):
        pr = rect_mesh_profile(n_, target="dft")
        detail4.append(f"N={n_}:{pr['reck_mesh_optimum']}→{pr['depth']}（省 "
                       f"{pr['depth_reduction_vs_reck']}）")
        if not (pr["n_mzi"] == n_ * (n_ - 1) // 2
                and pr["depth"] == n_ and pr["reck_mesh_optimum"] == 2 * n_ - 3
                and pr["depth_reduction_vs_reck"] == n_ - 3):
            ok4 = False
    res["④ 元件数仍 = N(N−1)/2 · 深度 2N−3 → N（矩形化只省深度，不增元件）"] = ok4

    # ⑤ 跨模块桥：本模块装配 ≡ 主权 mesh_rect_decomp_fidelity ≡ mesh_rect_fidelity
    from lda_layout.mesh_pnr import mesh_rect_decomp_fidelity, mesh_rect_fidelity
    ok5 = True
    detail5 = []
    for n_ in (4, 8, 16):
        U_ = TMB.random_unitary(n_, seed=n_ + 101)
        bs_, D_ = dec(U_)
        f_dec = float(mesh_rect_decomp_fidelity(bs_, D_, U_))
        f_mesh = float(mesh_rect_fidelity(bs_, D_, U_))
        f_mine = float(rect_mesh_fidelity(U_))
        detail5.append(f"N={n_}:mine={f_mine:.13f}/dec={f_dec:.13f}/mesh={f_mesh:.13f}")
        if not (abs(f_dec - 1.0) < 1e-12 and abs(f_mesh - 1.0) < 1e-12
                and abs(f_mine - f_mesh) < 1e-11):
            ok5 = False
    res["⑤ 跨模块桥：平台约定装配 ≡ 主权 mesh_rect_decomp/mesh_rect_fidelity（三方一致）"] = ok5

    # ⑥ 三角 Reck 对照：矩形（N）严格浅于三角 Reck 最优（2N−3）
    ok6 = True
    detail6 = []
    for n_ in (4, 8, 16, 64):
        sh = TMB.temporal_shallow_profile(n_, target="dft")
        pr = rect_mesh_profile(n_, target="dft")
        detail6.append(f"N={n_}:reck={sh['shallow_depth']} vs rect={pr['depth']}")
        if not (sh["shallow_depth"] == 2 * n_ - 3 and pr["depth"] == n_
                and pr["depth"] < sh["shallow_depth"]):
            ok6 = False
    res["⑥ 三角 Reck 最优 = 2N−3 严格深于 矩形 N ⇒ 矩形网格才是深度最优"] = ok6

    # ⑦ 紧界可达判定（报告口径）与三口径自洽
    ok7 = True
    detail7 = []
    for n_ in (2, 4, 8, 216):
        rep = tight_bound_reachable_report(n_)
        detail7.append(f"N={n_}:{rep['parameter_count_bound']}/"
                       f"{rep['tight_adjacency_bound']}={rep['rectangular_mesh_depth']}/"
                       f"{rep['reck_mesh_optimum']}")
        if not (rep["parameter_count_bound"] <= rep["tight_adjacency_bound"]
                == rep["rectangular_mesh_depth"] <= rep["reck_mesh_optimum"]):
            ok7 = False
        if n_ >= 3 and rep["tight_bound_reachable"] is not True:
            ok7 = False
    res["⑦ 紧界可达判定：参数界 ≤ 紧界 = 矩形可达 ≤ Reck 最优（含 216：215/216/429）"] = ok7

    # ⑧ 护栏：非方阵 / N<2 / 非匹配层 / 越界 ⇒ ValueError
    guard8 = True
    for bad in ((lambda: rectangular_mesh_layers(np.ones((2, 3), dtype=complex))),
                (lambda: rectangular_mesh_layers(np.eye(1, dtype=complex))),
                (lambda: assemble_rect_mesh([[(0, 0.3, 0.1), (0, 0.2, 0.0)]],
                                            np.eye(4), 4)),
                (lambda: assemble_rect_mesh([[(5, 0.3, 0.1)]], np.eye(4), 4)),
                (lambda: assemble_rect_mesh([], np.eye(1), 1))):
        try:
            bad()
            guard8 = False
        except ValueError:
            pass
    res["⑧ 护栏：非方阵 / N<2 / 非匹配层（共享模） / 越界 ⇒ 抛 ValueError"] = guard8

    # ⑨ 判决无 LLM：深度/界全为 int，保真度为 float（死标量）
    rep = tight_bound_reachable_report(216)
    res["⑨ 判决无 LLM：深度/界全为 int · 可达性为 bool（死标量，零模型调用）"] = (
        isinstance(rep["rectangular_mesh_depth"], int)
        and isinstance(rep["tight_adjacency_bound"], int)
        and isinstance(rep["tight_bound_reachable"], bool))

    if verbose:
        for k, v in res.items():
            print(f"[{'PASS' if v else 'FAIL'}] {k}")
        print("② 明细：" + " · ".join(detail2))
        print("③ 明细：" + " · ".join(detail3))
        print("④ 明细：" + " · ".join(detail4))
        print("⑤ 明细：" + " · ".join(detail5))
        print("⑥ 明细：" + " · ".join(detail6))
        print("⑦ 明细：" + " · ".join(detail7))
    return bool(all(res.values()))


if __name__ == "__main__":
    ok = run_selfchecks(verbose=True)
    print(f"rect_mesh 自检：{'全 PASS' if ok else '有 FAIL'}")
