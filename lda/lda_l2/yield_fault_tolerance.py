# -*- coding: utf-8 -*-
"""U6 · 良率 / 容错映射（Yield / fault-tolerance mapping）—— **条件式设计**。

背景（§4.2 U6）
--------------
内部总结 §4.2 对 U6 的验收判据是「注入 f% 故障 ⇒ 遮蔽后保真度 ≥ 目标 ·
反向护栏：无冗余必掉」，并预先标注风险：**缺少 foundry 良率真值 ⇒ 结论只能
是条件式的，须显式标假设**。

本模块做什么
------------
1. **自由度账（严格可证）**：Clements 矩形网格的参数个数与 U(N) 的实自由度
   **恰好相等**：

       n_dof    = N^2                       （U(N) 实维数）
       n_mzi    = N(N-1)/2
       n_params = 2*n_mzi + N = N^2         （每 MZI 两个角 + N 个末端输出相移）

   ⇒ `redundancy_margin = 0`，**结构冗余为零**。推论：任一 MZI 的**一个**参数
   被硬冻结（耦合器断裂 / 相移器失效）⇒ 可用参数 N^2-1 < N^2 ⇒ 对一般 U
   **精确可达性丢失** ⇒ **软件无法修复**（编译层没有自由度可以「绕开」失效站点
   —— 与 U7 证到的「编译层对 IL_var 自由度 = 0」同源）。⇒ 冗余只能来自**硬件**。

2. **故障模型（参数化 · 显式标为假设）**：`p`（器件级失效率）与 `p_switch`
   （选择开关失效率）**都是假设，不是实测**。三种失效模式：

   - `stuck_bar`  耦合器卡在直通（θ≡0，相移器仍可控）⇒ 冻结 1 个参数
   - `stuck_cross` 耦合器卡在交叉（θ≡π/2）        ⇒ 冻结 1 个参数
   - `phi_dead`   相移器失效（φ≡0，耦合器仍可控）  ⇒ 冻结 1 个参数
   - `drift`      θ 偏置 δ（**可标定**）            ⇒ 参数全自由

3. **实测（不是推算）**：
   - `single_fault_scan` —— 对每个站点做朴素注入，测保真度掉多少（反向护栏：
     全部站点都掉）；
   - `repair_upper_bound` —— **重编译上界**：冻结该参数后，对**其余全部参数**
     做最小二乘优化，看「最优重编译」能不能救回来。三种 fatal 模式实测
     `f_best < 1`（自由度账的预测），`drift` 实测可回到 1（可标定）。

4. **冗余方案的条件式良率**（解析 · 面积代价显式）：
   - `none`       无冗余：`Y = (1-p)^M`，`M = N(N-1)/2` ⇒ **指数崩塌**；
   - `site_spare` 站点 1:1 热备 + 1×2 选择开关：`Y = [(1-p_sw)(1-p^2)]^M`；
   - `dual_mesh`  整网格双模 + N 入 N 出 1×2 开关：
     `Y = (1-p_sw)^(2N) * [1 - (1-(1-p)^M)^2]`。

   实测结论（见 smoke）：**在 p_sw ≈ p 的现实假设下，`site_spare` 净收益≈0
   （开关与 MZI 同量级失效率时，串在路上的开关抵消了并联收益）；`dual_mesh`
   在 M ≫ 2N 的大 N 才转正**（N=16: 0.887 → 0.956 @ p=1e-3）。
   ⇒ **冗余该不该做，是「开关失效率」决定的，不是「MZI 失效率」决定的**。

5. **把「无锚宣称」换成「对 PDK 的规格要求」**：`required_p_for_yield(N, Y*)`
   反解出「要达 Y* 网格良率，MZI 器件级失效率须 ≤ p*」——这是**可写进 PDK
   规格、将来可实测回填**的数字，而不是一句能力宣称。

诚实边界：见 `YIELD_DISCLOSURE`。本模块**不跑 FDTD / 不做 3D / 不碰 foundry
工艺真值（红线）**，也**不宣称任何良率数字是实测真值**——全部数字都是
「给定假设 p 的条件式结论」。
"""
from __future__ import annotations

import cmath
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# 常量（全部为**假设 / 参数**，非实测）
# ---------------------------------------------------------------------------
#: 器件级失效率假设（per MZI / per switch）—— 🔴 假设，非实测。
DEFAULT_FAULT_PROB = 1.0e-3
#: 选择开关失效率假设—— 🔴 假设，非实测（现实中与 MZI 同量级）。
DEFAULT_SWITCH_PROB = 1.0e-3
#: θ 漂移代表值（rad）—— 1.15°，属**可标定**类。
DEFAULT_DRIFT_RAD = 0.02
#: 重编译上界优化的最大函数评估数（确定性，与随机无关）。
REPAIR_MAX_NFEV = 6000
#: 目标网格良率（用于反解对 PDK 的器件失效率要求）。
TARGET_GRID_YIELD = 0.99

#: 硬失效模式（冻结 1 个参数 ⇒ 自由度 N^2-1 < N^2 ⇒ 不可精确重编译）。
FATAL_MODES: Tuple[str, ...] = ("stuck_bar", "stuck_cross", "phi_dead")
#: 可标定模式（参数全自由 ⇒ 可精确重编译）。
CALIBRATABLE_MODES: Tuple[str, ...] = ("drift",)
#: 全部失效模式。
FAULT_MODES: Tuple[str, ...] = FATAL_MODES + CALIBRATABLE_MODES

#: 冗余方案。
REDUNDANCY_SCHEMES: Tuple[str, ...] = ("none", "site_spare", "dual_mesh")

#: 披露键（smoke 须断言全部存在）。
YIELD_DISCLOSURE: Dict[str, str] = {
    "scope": (
        "只做**网格级**（N×N Clements 矩形网格）的失效传播与冗余良率核算；"
        "不含光源/探测/驱动电学/封装/热串扰的失效率，不含 wafer-level 缺陷密度模型。"
    ),
    "fault_model_is_assumption_not_measurement": (
        "🔴 p（器件级失效率）与 p_switch（选择开关失效率）**都是假设**，本模块"
        "不产生也不验证任何实测失效率。全部良率数字都是「给定 p 的条件式结论」。"
    ),
    "no_foundry_yield_truth": (
        "🔴 缺 foundry 良率真值（需流片 + 圆片级测试，属项目红线「封测产线不做」"
        "与 U14 未解锁项）⇒ **本模块的结论只能是条件式的，不是能力宣称**。"
    ),
    "no_structural_redundancy": (
        "🔴 结构冗余 = 0（实测 n_params = 2*n_mzi + N = N^2 = n_dof）。"
        "Clements 矩形网格是**恰好定解**的参数化，没有冗余参数可以吸收失效。"
    ),
    "software_cannot_repair": (
        "🔴 任一硬失效模式冻结 1 个参数 ⇒ 可用参数 N^2-1 < N^2 ⇒ 一般 U 精确可达性"
        "丢失（实测 `repair_upper_bound` 的 f_best < 1）⇒ **软件/编译层无法修复**"
        "（与 U7 的「编译层对 IL_var 自由度 = 0」同源）⇒ 冗余只能来自硬件。"
    ),
    "repair_bound_is_numerical_local_min": (
        "`repair_upper_bound` 给的是**数值局部解**（确定性最小二乘，固定初值、"
        "无随机）；`converged=False` 表示触到 max_nfev 预算 ⇒ 该值是"
        "**可达保真度的下界**而非上界。它足以证伪「可精确修复」"
        "（f_best < 1），不足以宣称「这就是最优」。"
    ),
    "closed_form_anchor_scope": (
        "`closed_form_best_diagonal` 是**仅 N=2 成立**的严格闭式锚：此时网格只有"
        "1 个 MZI，θ≡0 ⇒ 可达集 = 全部对角酉 ⇒ 最佳保真度有闭式解。N>=3 无此"
        "闭式，只能给结构论证 + 数值佐证（不得把 N=2 的严格性外推到 N>=3）。"
    ),
    "drift_is_calibratable_not_fatal": (
        "θ 漂移（`drift`）冻结的是**设定值偏差**而非自由度 ⇒ 参数全自由 ⇒ 实测可"
        "精确重编译回 f = 1。⇒ 漂移问题的解法是**校准固件（U10）**，不是冗余；"
        "但 U10 需要物理锚，本模块**不宣称已校准**。"
    ),
    "area_cost_excluded_from_yield": (
        "良率公式只给**可靠性**，面积代价（`footprint_multiplier` / `mzi_multiplier`）"
        "单列。两者必须一起看：`site_spare` 面积 ×2 而净收益≈0（见 smoke 实测）。"
    ),
    "no_fdtd_no_3d": (
        "不跑 FDTD、不做 3D 电磁、不重新签核（几何不变 ⇒ DRC/LVS 结论继承既有结果）。"
    ),
    "ledger_unchanged": (
        "不扩基 · 零锚改动 · 账本零变化；本模块只读既有已证资产"
        "（`mesh_pnr.clements_rect_decompose` / `_rect_column_assignment` / "
        "`_ref_T_apply_rows` / `mesh_rect_fidelity`），不修改其行为。"
    ),
}


class FaultToleranceError(Exception):
    """U6 域校验失败（不静默返回可疑值）。"""


# ---------------------------------------------------------------------------
# 1) 自由度账（结构冗余 = 0，可严格证明）
# ---------------------------------------------------------------------------
def mesh_redundancy_audit(N: int) -> Dict[str, Any]:
    """Clements 矩形网格的**参数量 vs 自由度**账 —— 结构冗余严格为 0。

    n_dof    = N^2                     U(N) 实维数
    n_mzi    = N(N-1)/2
    n_params = 2*n_mzi + N = N^2       每 MZI(θ,φ) + N 个末端输出相移 D[k,k]

    ⇒ `redundancy_margin = 0`；任一参数被硬冻结 ⇒ 可用参数 < 自由度
      ⇒ 一般 U 精确不可达。
    """
    if int(N) < 2:
        raise FaultToleranceError("N 必须 >= 2（N=%r）" % (N,))
    N = int(N)
    n_mzi = N * (N - 1) // 2
    n_params = 2 * n_mzi + N
    n_dof = N * N
    return {
        "N": N,
        "n_dof": n_dof,
        "n_mzi": n_mzi,
        "n_params": n_params,
        "redundancy_margin": n_params - n_dof,
        "structural_redundancy": bool(n_params > n_dof),
        "params_per_dof": (float(n_params) / float(n_dof)),
        "params_after_one_fatal_fault": n_params - 1,
        "deficit_after_one_fatal_fault": n_dof - (n_params - 1),
        "note": (
            "恰好定解（n_params == n_dof）⇒ 零结构冗余 ⇒ 硬失效不可软件修复；"
            "该结论与 U7「编译层对 IL_var 自由度 = 0」同源（网格拓扑唯一决定）。"
        ),
    }


# ---------------------------------------------------------------------------
# 2) 故障注入（对已证分解做**值替换**，不改拓扑）
# ---------------------------------------------------------------------------
def inject_fault(bs_list: Sequence[Sequence[float]], k: int,
                 mode: str = "stuck_bar", delta: float = 0.0) -> List[Tuple[int, float, float]]:
    """把第 `k` 个 MZI 置为失效（朴素注入，无补偿）。

    - `stuck_bar`   : θ→0，φ 保留（相移器仍可控）
    - `stuck_cross` : θ→π/2，φ 保留
    - `phi_dead`    : φ→0，θ 保留
    - `drift`       : θ→θ+delta（可标定）
    """
    if mode not in FAULT_MODES:
        raise FaultToleranceError("未知失效模式 %r（可选 %r）" % (mode, FAULT_MODES))
    n = len(bs_list)
    if not (0 <= int(k) < n):
        raise FaultToleranceError("站点下标越界 k=%r（0..%d）" % (k, n - 1))
    out: List[Tuple[int, float, float]] = []
    for i, row in enumerate(bs_list):
        j = int(row[0])
        th = float(row[1])
        ph = float(row[2])
        if i == int(k):
            if mode == "stuck_bar":
                th = 0.0
            elif mode == "stuck_cross":
                th = math.pi / 2.0
            elif mode == "phi_dead":
                ph = 0.0
            elif mode == "drift":
                th = th + float(delta)
        out.append((j, th, ph))
    return out


# ---------------------------------------------------------------------------
# 3) 前向 / 保真度（与 mesh_pnr 同约定）
# ---------------------------------------------------------------------------
def _mesh_parts(U: np.ndarray) -> Dict[str, Any]:
    """取出 2D 压实网格的分解件与列序（全部来自既有已证资产）。"""
    from lda_layout.mesh_pnr import (clements_rect_decompose,
                                     _rect_column_assignment)
    U = np.asarray(U, dtype=complex)
    bs_list, D = clements_rect_decompose(U)
    color = list(_rect_column_assignment(bs_list))
    return {
        "N": int(U.shape[0]),
        "bs_list": [(int(b[0]), float(b[1]), float(b[2])) for b in bs_list],
        "D": np.asarray(D, dtype=complex),
        "color": color,
        "n_cols": max(color) + 1 if color else 0,
        "n_mzi": len(bs_list),
    }


def _forward_unitary(bs_list, D, N: int) -> np.ndarray:
    """按 2D 压实列序施加 ref_T，末端乘 D —— 与 `mesh_rect_fidelity` 同约定。"""
    from lda_layout.mesh_pnr import _ref_T_apply_rows, _rect_column_assignment
    color = list(_rect_column_assignment(bs_list))
    n_cols = max(color) + 1 if color else 0
    buckets: List[List[Tuple[int, float, float]]] = [[] for _ in range(n_cols)]
    for i, row in enumerate(bs_list):
        buckets[color[i]].append((int(row[0]), float(row[1]), float(row[2])))
    U = np.eye(N, dtype=complex)
    for c in range(n_cols):
        for (j, th, ph) in buckets[c]:
            _ref_T_apply_rows(U, th, ph, j)
    return np.diag(np.diag(np.asarray(D, dtype=complex))) @ U


def _fidelity(U_rec: np.ndarray, U_target: np.ndarray) -> float:
    """与 `mesh_pnr.mesh_rect_fidelity` 逐式一致：1 - ||ΔU||_F/(N·√2)，下限 0。"""
    N = int(U_target.shape[0])
    err = float(np.linalg.norm(np.asarray(U_rec) - np.asarray(U_target))) / (N * math.sqrt(2.0))
    return float(max(0.0, 1.0 - err))


def _pack_params(bs_list, D) -> np.ndarray:
    """[θ,φ]×n_mzi ++ [arg D[k,k]]×N。"""
    x: List[float] = []
    for row in bs_list:
        x.append(float(row[1]))
        x.append(float(row[2]))
    x.extend(float(np.angle(np.diag(np.asarray(D, dtype=complex))[k]))
             for k in range(len(D)))
    return np.array(x, dtype=float)


def _unpack_unitary(x: np.ndarray, js: Sequence[int], color: Sequence[int],
                    n_cols: int, N: int) -> np.ndarray:
    """由完整参数向量（冻结位已被调用方写死）重建 U。"""
    from lda_layout.mesh_pnr import _ref_T_apply_rows
    n_mzi = len(js)
    buckets: List[List[Tuple[int, float, float]]] = [[] for _ in range(n_cols)]
    for m in range(n_mzi):
        th = float(x[2 * m])
        ph = float(x[2 * m + 1])
        buckets[color[m]].append((int(js[m]), th, ph))
    U = np.eye(N, dtype=complex)
    for c in range(n_cols):
        for (j, th, ph) in buckets[c]:
            _ref_T_apply_rows(U, th, ph, j)
    dph = x[2 * n_mzi: 2 * n_mzi + N]
    Dv = np.array([cmath.exp(1j * float(a)) for a in dph], dtype=complex)
    return np.diag(Dv) @ U


# ---------------------------------------------------------------------------
# 4) 单点故障扫描（朴素注入 · 反向护栏「无冗余必掉」）
# ---------------------------------------------------------------------------
def single_fault_scan(U: np.ndarray, mode: str = "stuck_bar",
                      delta: float = 0.0) -> Dict[str, Any]:
    """对**每一个**站点做朴素单点注入，测保真度损失分布。"""
    if mode not in FAULT_MODES:
        raise FaultToleranceError("未知失效模式 %r" % (mode,))
    p = _mesh_parts(U)
    N, bs, D, n_mzi = p["N"], p["bs_list"], p["D"], p["n_mzi"]
    U_target = np.asarray(U, dtype=complex)
    fid_ideal = _fidelity(_forward_unitary(bs, D, N), U_target)
    rows = []
    for k in range(n_mzi):
        bad = inject_fault(bs, k, mode=mode, delta=delta)
        f = _fidelity(_forward_unitary(bad, D, N), U_target)
        rows.append({"k": k, "j": bs[k][0], "fidelity": f,
                     "loss": fid_ideal - f})
    fids = [r["fidelity"] for r in rows]
    worst = min(rows, key=lambda r: r["fidelity"])
    best = max(rows, key=lambda r: r["fidelity"])
    return {
        "mode": mode,
        "delta": float(delta),
        "N": N,
        "n_mzi": n_mzi,
        "fid_ideal": fid_ideal,
        "fid_min": min(fids),
        "fid_max": max(fids),
        "fid_mean": float(sum(fids) / len(fids)),
        "worst_k": worst["k"],
        "best_k": best["k"],
        "all_sites_degrade": bool(all(r["fidelity"] < fid_ideal for r in rows)),
        "n_sites_degraded": int(sum(1 for r in rows if r["fidelity"] < fid_ideal)),
        "per_site": rows,
        "honest_note": (
            "朴素注入（无可补偿）⇒ 这是「无冗余」的下界；上界见 repair_upper_bound。"
        ),
    }


# ---------------------------------------------------------------------------
# 5) 重编译上界（冻结 1 参数后，对**其余全部参数**做确定性最小二乘）
# ---------------------------------------------------------------------------
def repair_upper_bound(U: np.ndarray, k: int, mode: str = "stuck_bar",
                       delta: float = 0.0,
                       max_nfev: int = REPAIR_MAX_NFEV) -> Dict[str, Any]:
    """最优重编译上界：诚实回答「软件能不能救回来」。

    冻结方式（决定自由度账）：
      - `stuck_bar`   : 冻结 θ_k = 0      ⇒ 可用参数 N^2-1
      - `stuck_cross` : 冻结 θ_k = π/2    ⇒ 可用参数 N^2-1
      - `phi_dead`    : 冻结 φ_k = 0      ⇒ 可用参数 N^2-1
      - `drift`       : **不冻结**；初值 θ_k = θ_ideal + δ（未标定的实际值）
                        ⇒ 可用参数 N^2 ⇒ 应可回到 f = 1

    返回 f_naive（朴素）与 f_best（最优重编译），以及是否可达 1。
    """
    from scipy.optimize import least_squares
    if mode not in FAULT_MODES:
        raise FaultToleranceError("未知失效模式 %r" % (mode,))
    p = _mesh_parts(U)
    N, bs, D, color = p["N"], p["bs_list"], p["D"], p["color"]
    n_cols, n_mzi = p["n_cols"], p["n_mzi"]
    if not (0 <= int(k) < n_mzi):
        raise FaultToleranceError("站点下标越界 k=%r（0..%d）" % (k, n_mzi - 1))
    k = int(k)
    U_target = np.asarray(U, dtype=complex)
    js = [b[0] for b in bs]
    x0 = _pack_params(bs, D)
    free = np.ones(x0.size, dtype=bool)
    frozen_desc = "无（参数全自由）"
    if mode in ("stuck_bar", "stuck_cross"):
        x0[2 * k] = 0.0 if mode == "stuck_bar" else math.pi / 2.0
        free[2 * k] = False
        frozen_desc = "θ_%d（耦合器卡死）" % k
    elif mode == "phi_dead":
        x0[2 * k + 1] = 0.0
        free[2 * k + 1] = False
        frozen_desc = "φ_%d（相移器失效）" % k
    elif mode == "drift":
        x0[2 * k] = x0[2 * k] + float(delta)
        frozen_desc = "无（漂移偏置可被吸收）"

    idx_free = np.where(free)[0]

    def expand(xf: np.ndarray) -> np.ndarray:
        x = x0.copy()
        x[idx_free] = xf
        return x

    def resid(xf: np.ndarray) -> np.ndarray:
        Urec = _unpack_unitary(expand(xf), js, color, n_cols, N)
        R = Urec - U_target
        return np.concatenate([R.real.ravel(), R.imag.ravel()])

    f_naive = _fidelity(_unpack_unitary(x0, js, color, n_cols, N), U_target)
    xf0 = x0[idx_free]
    sol = least_squares(resid, xf0, method="trf", max_nfev=int(max_nfev))
    f_best = _fidelity(_unpack_unitary(expand(sol.x), js, color, n_cols, N),
                       U_target)
    n_free = int(idx_free.size)
    converged = bool(getattr(sol, "success", False))
    return {
        "mode": mode,
        "delta": float(delta),
        "N": N,
        "k": k,
        "frozen": frozen_desc,
        "n_params_total": int(x0.size),
        "n_params_free": n_free,
        "n_dof": N * N,
        "params_shortfall": int(N * N - n_free),
        "fid_ideal": _fidelity(_forward_unitary(bs, D, N), U_target),
        "fid_naive": f_naive,
        "fid_best_repair": f_best,
        "exactly_recoverable": bool(f_best >= 1.0 - 1e-9),
        "repair_gain": f_best - f_naive,
        "nfev": int(sol.nfev),
        "converged": converged,
        "bound_kind": "可达上界（已收敛）" if converged else "可达下界（触预算未收敛）",
        "honest_note": (
            "确定性 trf（固定初值、无随机）：f_best < 1 足以证伪「可精确修复」；"
            "`converged=False` 时该值只是可达保真度的**下界**。"
        ),
    }


# ---------------------------------------------------------------------------
# 5b) 严格闭式锚（**仅 N=2**）：stuck_bar ⇒ 网格退化为对角酉
# ---------------------------------------------------------------------------
def closed_form_best_diagonal(U: np.ndarray) -> Dict[str, Any]:
    """**严格闭式**：N=2 · `stuck_bar`（θ≡0）⇒ 可达集 = 全部 2×2 对角酉。

    此时 `U_rec = D · diag(e^{iφ}, 1) = diag(d0·e^{iφ}, d1)`（φ 可吸收进 d0）
    ⇒ 可达集**恰为**全部对角酉。最优对角逼近（相位最优性 ⇒ d_k = U_kk/|U_kk|）：

        min_D ||U - D||_F^2 = Σ_k (1-|U_kk|)^2  +  Σ_{k!=l} |U_kl|^2
                            = 2N - 2·Σ_k |U_kk|          （用 ||U||_F^2 = N）
        f_best = 1 - sqrt(2N - 2·Σ_k |U_kk|) / (N·sqrt(2))

    ⚠️ 第二项 `Σ_{k!=l}|U_kl|^2` 是**不可消除**的（对角酉改不动非对角元）；
    漏掉它会得到偏乐观的闭式（本轮自纠：数值重编译先给出正确值，交叉验证
    抓出闭式漏项 —— 见 CHANGELOG v0.9.127）。

    推论（严格）：`f_best = 1` ⟺ U 本身是对角酉；对非对角占优的 U
    （一般位置 |U_kk| ≈ 1/sqrt(N)）必有 f_best < 1 ⇒ **精确不可达**。
    ⇒ 这是「软件不可修复」在 N=2 上的**严格证明**；N>=3 无此闭式，只有
    结构论证（自由度 N^2-1 < N^2）+ 数值佐证 —— 见 `YIELD_DISCLOSURE`。
    """
    U = np.asarray(U, dtype=complex)
    N = int(U.shape[0])
    d = np.abs(np.diag(U))
    s = float(np.sum(d))
    offdiag_energy = float(np.sum(np.abs(U) ** 2) - np.sum(d ** 2))
    res_sq = 2.0 * N - 2.0 * s
    res = math.sqrt(res_sq) if res_sq > 0.0 else 0.0
    err = res / (N * math.sqrt(2.0))
    return {
        "N": N,
        "diag_abs": [float(x) for x in d],
        "diag_abs_min": float(d.min()),
        "diag_abs_mean": float(d.mean()),
        "diag_abs_sum": s,
        "offdiag_energy": offdiag_energy,
        "residual_fro": float(res),
        "fid_best_diagonal": float(max(0.0, 1.0 - err)),
        "exactly_reachable": bool(res <= 1e-12),
        "honest_note": (
            "严格闭式（相位最优性 + 非对角项不可消除），但**只对 N=2 成立**"
            "（此时网格仅 1 个 MZI，θ≡0 把可达集压成对角子群）；不得外推 N>=3。"
        ),
    }


# ---------------------------------------------------------------------------
# 6) 冗余方案的条件式良率（解析）
# ---------------------------------------------------------------------------
def scheme_reliability(N: int, p: float, scheme: str,
                       p_switch: float = DEFAULT_SWITCH_PROB) -> Dict[str, Any]:
    """给定假设 (p, p_switch)，算某冗余方案的网格良率与面积代价。

    - `none`       : Y = (1-p)^M                              · 面积 ×1
    - `site_spare` : Y = [(1-p_sw)(1-p^2)]^M                  · MZI ×2 + M 开关
    - `dual_mesh`  : Y = (1-p_sw)^(2N) · [1-(1-(1-p)^M)^2]    · MZI ×2 + 2N 开关
    """
    if scheme not in REDUNDANCY_SCHEMES:
        raise FaultToleranceError("未知冗余方案 %r（可选 %r）" % (scheme, REDUNDANCY_SCHEMES))
    audit = mesh_redundancy_audit(N)
    M = audit["n_mzi"]
    p = float(p)
    p_sw = float(p_switch)
    if not (0.0 <= p < 1.0) or not (0.0 <= p_sw < 1.0):
        raise FaultToleranceError("失效率须落在 [0,1)：p=%r p_switch=%r" % (p, p_sw))
    if scheme == "none":
        Y = (1.0 - p) ** M
        mult, n_sw = 1.0, 0
    elif scheme == "site_spare":
        q = (1.0 - p_sw) * (1.0 - p * p)
        Y = q ** M
        mult, n_sw = 2.0, M
    else:  # dual_mesh
        mesh_ok = (1.0 - p) ** M
        Y = ((1.0 - p_sw) ** (2 * N)) * (1.0 - (1.0 - mesh_ok) ** 2)
        mult, n_sw = 2.0, 2 * N
    return {
        "N": N,
        "scheme": scheme,
        "p": p,
        "p_switch": p_sw,
        "n_mzi": M,
        "n_switch": n_sw,
        "yield": float(Y),
        "unreliability": float(1.0 - Y),
        "mzi_multiplier": mult,
        "footprint_multiplier": mult,
        "note": "良率仅为**条件式**（给定假设 p / p_switch）；面积代价须与良率同看。",
    }


def required_p_for_yield(N: int, target_yield: float = TARGET_GRID_YIELD,
                         scheme: str = "none") -> Dict[str, Any]:
    """反解「要达 target 网格良率，器件级失效率须 ≤ p*」—— 可写进 PDK 规格的硬数字。

    - `none`      : (1-p)^M >= Y*            ⇒ p* = 1 - Y*^(1/M)
    - `site_spare`: [(1-p)(1-p^2)]^M >= Y*   ⇒ 数值二分（p_switch = p，最保守）
    - `dual_mesh` : 数值二分（p_switch = p）
    """
    if scheme not in REDUNDANCY_SCHEMES:
        raise FaultToleranceError("未知冗余方案 %r" % (scheme,))
    if not (0.0 < float(target_yield) < 1.0):
        raise FaultToleranceError("目标良率须在 (0,1)：%r" % (target_yield,))
    M = mesh_redundancy_audit(N)["n_mzi"]
    tgt = float(target_yield)
    if scheme == "none":
        p_star = 1.0 - tgt ** (1.0 / M)
        detail = "闭式：p* = 1 - Y*^(1/M)"
    else:
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if scheme_reliability(N, mid, scheme, p_switch=mid)["yield"] >= tgt:
                lo = mid
            else:
                hi = mid
        p_star = lo
        detail = "二分（最保守假设 p_switch = p）"
    return {
        "N": N,
        "scheme": scheme,
        "target_yield": tgt,
        "n_mzi": M,
        "required_device_failure_prob": float(p_star),
        "required_device_yield": float(1.0 - p_star),
        "detail": detail,
        "note": (
            "🔴 这是**对 PDK 的规格要求**（将来可实测回填），不是能力宣称；"
            "当前无 foundry 良率真值 ⇒ 只能作为条件式设计输入。"
        ),
    }


def yield_curve(N_list: Sequence[int], p_list: Sequence[float],
                schemes: Sequence[str] = ("none", "site_spare", "dual_mesh"),
                p_switch: Optional[float] = None) -> List[Dict[str, Any]]:
    """(N, p, scheme) 网格上的良率表（条件式）。`p_switch=None` ⇒ 取 `p`（最保守）。"""
    out: List[Dict[str, Any]] = []
    for N in N_list:
        for p in p_list:
            psw = float(p) if p_switch is None else float(p_switch)
            for s in schemes:
                out.append(scheme_reliability(int(N), float(p), s, p_switch=psw))
    return out


def redundancy_break_even(N: int, scheme: str = "site_spare") -> Dict[str, Any]:
    """冗余是否值得：解「p_switch 需多低，冗余才不亏」。

    判据 = `yield_redundant >= yield_none`（同 p 下）。
    - `site_spare` 闭式可解：(1-p_sw)(1-p^2) >= (1-p) ⇒ p_sw <= 1 - (1-p)/(1-p^2)
    - `dual_mesh` 用二分。
    """
    if scheme not in REDUNDANCY_SCHEMES or scheme == "none":
        raise FaultToleranceError("只对 site_spare / dual_mesh 求盈亏平衡")
    M = mesh_redundancy_audit(N)["n_mzi"]
    rows = []
    for p in (1e-5, 1e-4, 1e-3, 1e-2):
        y_none = (1.0 - p) ** M
        n_sw = M if scheme == "site_spare" else 2 * N
        # 找最大 p_sw 使冗余良率 >= 无冗余良率
        lo, hi = 0.0, 1.0
        if scheme_reliability(N, p, scheme, p_switch=0.0)["yield"] < y_none:
            psw_star = -1.0            # 即使理想开关也亏
        else:
            for _ in range(200):
                mid = 0.5 * (lo + hi)
                if scheme_reliability(N, p, scheme, p_switch=mid)["yield"] >= y_none:
                    lo = mid
                else:
                    hi = mid
            psw_star = lo
        rows.append({
            "p": p,
            "yield_none": float(y_none),
            "n_switch": n_sw,
            "max_switch_prob_for_parity": float(psw_star),
            "parity_impossible_even_with_ideal_switch": bool(psw_star < 0.0),
        })
    return {
        "N": N,
        "scheme": scheme,
        "n_mzi": M,
        "rows": rows,
        "note": (
            "`max_switch_prob_for_parity` = 选择开关失效率的盈亏平衡上限："
            "**高于它，冗余就是净亏**（面积 ×2 已付、良率反而更低）。"
            "现实中开关与 MZI 同量级失效率 ⇒ 该值决定冗余该不该做。"
        ),
    }


# ---------------------------------------------------------------------------
# 7) 汇总报告
# ---------------------------------------------------------------------------
def fault_tolerance_report(U: np.ndarray, p: float = DEFAULT_FAULT_PROB,
                           p_switch: float = DEFAULT_SWITCH_PROB,
                           delta: float = DEFAULT_DRIFT_RAD) -> Dict[str, Any]:
    """U6 汇总：自由度账 + 三模式单点扫描 + 重编译上界 + 条件式良率 + PDK 规格。

    重编译上界按**各模式各自的 worst site** 取（避免把 bar 的最坏站点套到
    cross/phi_dead 上，导致数字不自洽）。
    """
    q = _mesh_parts(U)
    N, n_mzi = q["N"], q["n_mzi"]
    scans = {m: single_fault_scan(U, mode=m, delta=delta) for m in FATAL_MODES}
    repairs = {m: repair_upper_bound(U, scans[m]["worst_k"], mode=m, delta=delta)
               for m in FATAL_MODES}
    drift_site = scans["stuck_bar"]["worst_k"]
    repairs["drift"] = repair_upper_bound(U, drift_site, mode="drift", delta=delta)
    curve = yield_curve([N], [p], p_switch=p_switch)
    return {
        "N": N,
        "n_mzi": n_mzi,
        "worst_site": {m: scans[m]["worst_k"] for m in FATAL_MODES},
        "drift_probe_site": drift_site,
        "audit": mesh_redundancy_audit(N),
        "single_fault_scans": scans,
        "repair_bounds": repairs,
        "closed_form_anchor_n2": closed_form_best_diagonal(_generic_unitary(2)),
        "yield_curve_at_p": curve,
        "required_p": {s: required_p_for_yield(N, scheme=s)
                       for s in REDUNDANCY_SCHEMES},
        "break_even": {s: redundancy_break_even(N, scheme=s)
                       for s in ("site_spare", "dual_mesh")},
        "disclosure": dict(YIELD_DISCLOSURE),
    }


# ---------------------------------------------------------------------------
# 自测
# ---------------------------------------------------------------------------
def _demo_unitary(N: int) -> np.ndarray:
    """确定性 DFT 酉（复现 U7 / U1 同源用例，无随机）。"""
    n = np.arange(N)
    return np.exp(2j * np.pi * np.outer(n, n) / N) / math.sqrt(N)


def _generic_unitary(N: int) -> np.ndarray:
    """确定性「一般位置」酉 —— 逐对 Givens 旋转，角度取黄金比哈希（**无 RNG**）。

    DFT 在某些 N 下分解会出现退化角（θ≡0/π/2），会把失效注入的结论稀释；
    本函数给 smoke 提供一个**一般位置**的对照酉，且跨机器逐位可复现
    （不依赖 LAPACK QR 的实现细节）。
    """
    g = (1.0 + 5.0 ** 0.5) / 2.0
    U = np.eye(N, dtype=complex)
    for m in range(N - 1):
        for n in range(m + 1, N):
            th = (0.5 + 0.37 * (((m * N + n) * g) % 1.0)) * (math.pi / 2.0)
            ph = 2.0 * math.pi * ((((m + 1) * 7 + (n + 1) * 13) * g) % 1.0)
            G = np.eye(N, dtype=complex)
            c, s, e = math.cos(th), math.sin(th), cmath.exp(1j * ph)
            G[m, m] = e * c
            G[m, n] = -s
            G[n, m] = e * s
            G[n, n] = c
            U = G @ U
    return U


if __name__ == "__main__":
    np.set_printoptions(precision=17)
    # 严格闭式锚（N=2）vs 数值重编译上界 —— 交叉验证
    U2 = _generic_unitary(2)
    cf = closed_form_best_diagonal(U2)
    rb = repair_upper_bound(U2, 0, mode="stuck_bar")
    print("N=2 闭式 f_best=%.17f  数值 f_best=%.17f  差=%.3e  可达=%s"
          % (cf["fid_best_diagonal"], rb["fid_best_repair"],
             abs(cf["fid_best_diagonal"] - rb["fid_best_repair"]),
             cf["exactly_reachable"]))
    for N in (4, 8):
        U = _demo_unitary(N)
        a = mesh_redundancy_audit(N)
        print("N=%d  n_dof=%d n_mzi=%d n_params=%d margin=%d"
              % (N, a["n_dof"], a["n_mzi"], a["n_params"], a["redundancy_margin"]))
        for mode in FATAL_MODES:
            s = single_fault_scan(U, mode=mode)
            print("   scan %-11s fid_min=%.17f mean=%.17f all_drop=%s"
                  % (mode, s["fid_min"], s["fid_mean"], s["all_sites_degrade"]))
        k = single_fault_scan(U, mode="stuck_bar")["worst_k"]
        for mode in FATAL_MODES:
            r = repair_upper_bound(U, k, mode=mode)
            print("   repair %-11s free=%d/%d naive=%.17f best=%.17f exact=%s conv=%s"
                  % (mode, r["n_params_free"], r["n_params_total"],
                     r["fid_naive"], r["fid_best_repair"],
                     r["exactly_recoverable"], r["converged"]))
        rd = repair_upper_bound(U, k, mode="drift", delta=DEFAULT_DRIFT_RAD)
        print("   repair drift       free=%d/%d naive=%.17f best=%.17f exact=%s"
              % (rd["n_params_free"], rd["n_params_total"],
                 rd["fid_naive"], rd["fid_best_repair"], rd["exactly_recoverable"]))
        for s in REDUNDANCY_SCHEMES:
            rel = scheme_reliability(N, DEFAULT_FAULT_PROB, s)
            print("   yield %-11s Y=%.10f  area x%.1f  sw=%d"
                  % (s, rel["yield"], rel["footprint_multiplier"], rel["n_switch"]))
        print("   required_p(0.99):",
              {s: round(required_p_for_yield(N, scheme=s)["required_device_failure_prob"], 10)
               for s in REDUNDANCY_SCHEMES})
