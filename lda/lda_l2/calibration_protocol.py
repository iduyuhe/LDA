# -*- coding: utf-8 -*-
"""U10 · 校准固件（闭环 per-MZI 热/相）—— **协议设计**（设计层交付，不做能力宣称）。

背景（内部总结 §4.2 U10 / §4.3 依赖图 / §4.4 执行序）
-------------------------------------------------------
MZI 网格的**刚需**是逐 MZI 标定（把每条臂的热/相调到目标值）。但 §4.2 判它是
「**最不能靠仿真解锁的一项**」：

> 🔴 **必须有物理锚**（真 PDK 工艺角 或 实测标定数据）⇒ 设计层只能做
> 「标定流程与自检协议」的设计，**不能宣称已校准**。

本模块**只交付三件**（§4.2 原文列的三件），不做第四件：

  ① **标定协议** —— 有序步骤表（含每步的输入/输出/**阻断条件**）+ 状态机。
  ② **自检判据** —— S1..S7 七条，机器可判；缺锚时 S5 必红。
  ③ **WDM 标定地基的接口定义** —— 与 `mesh_pnr.mesh_drive_manifest` **同形**
     （`n_mzi` / `n_out` / `mzi` / `out` 四个必需共有键机器可判）。
  ④ **不做**（明确拒绝）—— 不宣称「已校准」；不碰 foundry 工艺真值；
     不把仿真当标定证据；不假装闭环已闭合。

🔴 红线（**机器守卫**，不是文字承诺）
--------------------------------------
| 守卫 | 语义 | 触发 |
|---|---|---|
| `guard_no_foundry_process_truth` | 载荷**键名**不得含 foundry/TCAD/工艺角 令牌；且 `pdk_process_truth_used` 必须为假 | raise `CalibrationRedlineError` |
| `guard_anchor_kind_eligible` | 锚 `kind` 必须 ∈ `ANCHOR_KINDS`（**不含** literature / simulation）且 `is_attested is True` | raise `CalibrationAnchorError` |
| `guard_calibration_requires_anchor` | 任何 `claim == "calibrated"` 的声明**必须**绑定合格物理锚 | raise `CalibrationAnchorError` |

🔴 本模块最硬的四条结论（全部**不利**，机器可证）
---------------------------------------------------
① **纯功率（强度）读出在结构上不可解**。单波长功率 Jacobian 秩 = **(N−1)²**
   （一般位置取等），亏缺 = **2N−1**：
     · **N 维**是 `argD`（输出相位）—— 其 Jacobian 块**恒为 0**（与 λ 无关，
       机器可证的结构事实：`|U|²` 不含输出相位）；
     · 另 **(N−1) 维**位于 (θ, φ) 内部。
   ⇒ 与 U6「结构冗余 = 0」、U7「编译层自由度 = 0」**同族**：这是**结构**障碍，
   **软件/算法不可修复**。
② **多波长（WDM）不提升秩**。K = 1/2/4（间隔 0 → 100 nm）秩**恒为 (N−1)²**
   ⇒ 「WDM 标定地基」**不是**解锁路径（这条**否决**了它作为解法）。
③ **相位敏感（复场）读出单波长即满秩 N²**，且 σmin/σmax 改善 25.6× / 37.7× /
   107.1×（N = 4 / 6 / 8）⇒ 标定固件**必须**基于相干探测（至少一路相位参考）。
④ **秩定律是「一般位置」结论、不是全称**：DFT 族因退化角秩更低
   （N = 4: 8 < 9 · N = 6: 21 < 25 · N = 8: 44 < 49）—— 与 U6 记录的
   「DFT 在某些 N 下分解出现退化角」**同源**。

方法自证（🔴 血的教训，见下）
-------------------------------
早期版本的功率 Jacobian 写成 `2·Re(U ⊙ dU)`（**少了共轭**）⇒ 那不是 `|U|²` 的
导数；更糟的是差分验证用了**同一个错式** ⇒ 「解析 vs 差分一致」是**循环验证**，
无法暴露该错。现版本：
  · 解析式 = `2·Re(conj(U) ⊙ dU)`；
  · 地面真值 = **`|U|²` 的中心差分**（真实可观测量本身，不复用任何解析式）；
  · 二者对 N = 2..8 全部一致（相对差 ≤ 4.8e-10，见 smoke D 组）。
另外列序必须以 **`bs_list` 下标**为键 —— `b[0]` 是**模式对下标 j**（不同列可重复），
拿它当唯一键会导致列**重复 + 缺失**，秩被压成 ~N（污染）。

耗时：纯解析（零 FDTD / 零查表）⇒ 单次 < 0.02s（可进 CI core）。
"""
from __future__ import annotations

import cmath
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

# 复用 U6 的**已证前向模型**与**确定性测试资产**（无 RNG ⇒ 跨机逐位可复现）
from lda_l2.yield_fault_tolerance import (
    _forward_unitary,
    _generic_unitary,
    _mesh_parts,
)

# ---------------------------------------------------------------------------
# 1. 交付边界 / 锚类别 / 披露
# ---------------------------------------------------------------------------
#: 测量方案。`power` = 平方律（强度）探测；`complex` = 相位敏感（相干）探测。
MEASUREMENT_MODES: Tuple[str, ...] = ("power", "complex")

MODE_NOTES: Dict[str, str] = {
    "power": "平方律探测：可观测量 = |U|²（单波长 N² 个实数）",
    "complex": "相位敏感（相干）探测：可观测量 = Re/Im U（需相位参考/LO）",
}

DETECTOR_REQUIREMENTS: Dict[str, Tuple[str, ...]] = {
    "power": ("每输出端口一个平方律探测器",),
    "complex": ("相干探测", "相位参考（LO / 参考臂）", "两路正交读出"),
}

#: 🔴 可接受的**物理锚**类别。**不含** `"literature"` / `"simulation"` / `"assumption"`
#: —— §4.2 原文只承认「真 PDK 工艺角 或 实测标定数据」。
ANCHOR_KINDS: Tuple[str, ...] = ("pdk_process_corner", "measured_calibration_data")

#: 🔴 用 **(kind, note) 元组**而不是 dict —— 因为 `"pdk_process_corner"` 作为**键**
#: 会被 `guard_no_foundry_process_truth` 的键扫描判违规（`process_corner` 是 forbidden
#: 令牌）⇒ 任何一个把本表塞进受守卫载荷的调用者都会撞上「守卫对合法内容恒红」的坑。
#: 元组形式从**形状**上消除该陷阱（kind 只作为 `ANCHOR_KINDS` 的**值**出现）。
ANCHOR_KIND_NOTES: Tuple[Tuple[str, str], ...] = (
    ("pdk_process_corner", "foundry PDK 的工艺角真值（需 NDA / 准入）"),
    ("measured_calibration_data", "本器件/本工艺的**实测**标定数据（含不确定度）"),
)

#: 🔴 本项目**拥有的**物理锚 —— **空集**（这是诚实边界，不是待办）。
ANCHORS_AVAILABLE_TO_THIS_PROJECT: Tuple[str, ...] = ()

#: 参考波长（nm）。与 U1/U4/U8 同源约定。
LAM_REF_NM: float = 1550.0

#: SVD 零空间判据：相对奇异值 < 该阈值视为 0。实测「真零」约 1e-16..1e-17，
#: 「最小非零」在 N=8 功率下仍有 5.2e-6 ⇒ 阈值 1e-10 落在**两个量级之间的深谷**里
#: （实测间隙 4.5e10，见 `MEASURED_SIGMA_GAP`）⇒ 判据不敏感于阈值微调。
SVD_ZERO_TOL: float = 1e-10

#: 🔴 **设计占位阈值（非实测）**：σmin/σmax 地板。
#: 取 1e-4 使一般位置 N=8 的**功率**读出被判病态（5.218e-6 < 1e-4），
#: 而复场读出通过（5.591e-4 > 1e-4）。真实阈值须由 PDK 探测器噪声底标定 ——
#: 本项目无锚 ⇒ 该阈值**不可引用为规格**（`CAL_DISCLOSURE["conditioning"]`）。
CONDITION_SIGMA_FLOOR: float = 1e-4

#: 默认 WDM 栅格（nm）：与 U1/U4 的 WDM 口径同量级。
WDM_LAM_DEFAULT: Tuple[float, ...] = (1550.0, 1552.5)
WDM_LAM_WIDE: Tuple[float, ...] = (1500.0, 1533.333333333333, 1566.666666666666, 1600.0)

#: 驱动臂长参考（µm）——与 U8 `ARM_REF_UM` / `mesh_drive_manifest` 默认一致。
ARM_REF_UM: float = 1000.0

#: 披露表（smoke 断言键数）。**逐条是可判事实**，不是免责声明套话。
CAL_DISCLOSURE: Dict[str, str] = {
    "capability": "本模块只交付**标定协议 / 自检判据 / 接口定义**，**不宣称已校准**。",
    "anchor": "标定固件**必须有物理锚**（PDK 工艺角 或 实测标定数据）；本项目**一个都没有**。",
    "identifiability": (
        "纯功率读出单波长可辨识维数仅 **(N−1)²**（一般位置），亏缺 **2N−1**；"
        "其中输出相位 **N 维恒不可观测**。"),
    "wdm": (
        "多波长（K = 1/2/4、间隔 0 → 100 nm）**不提升秩**（实测恒为 (N−1)²）"
        "⇒ WDM 标定地基**不是**解锁路径。"),
    "phase_sensitive": (
        "相位敏感（相干）读出单波长即**满秩 N²**；σmin/σmax 改善 "
        "25.6× / 37.7× / 107.1×（N = 4/6/8）。"),
    "conditioning": (
        "功率读出 σmin/σmax 在 N=(2,3,4,6,8) 上塌陷：1.0 → 1.70e−1 → 1.50e−3 → "
        "3.17e−4 → 5.22e−6（8 为全域最小）。🔴 **不是全序单调**：σmin(N=4) < "
        "σmin(N=5)＝2.08e−3（如实记录）。σ 地板 1e−4 是**设计占位**、非 PDK 规格。"),
    "degenerate_family": (
        "秩定律是**一般位置**结论：DFT 族因退化角秩更低（N=4: 8 · N=6: 21 · N=8: 44）"
        "—— 与 U6「DFT 退化角」同源。"),
    "no_foundry": "不碰 foundry 工艺真值（无 NDA / 无 TCAD 真值 / 无准入）。",
    "no_simulation_authority": (
        "仿真**不构成**标定证据（T1 铁律）：本项目所有数值均为**设计预算/结构结论**。"),
    "closed_loop": (
        "per-MZI 闭环**未闭合**（`closed_loop_enabled=False`）⇒ 热串扰矩阵与工艺角"
        "未知 ⇒ 环路增益/稳定性不可证明，闭合无授权。"),
    "thermal_crosstalk": "热串扰矩阵未知 ⇒ 标定**顺序与收敛性未被证明**（只能给协议骨架）。",
    "drift": "漂移再标定周期**无实测支撑** ⇒ 只能给协议占位，**不可引用为指标**。",
    "verdict": (
        "本项目状态 = `BLOCKED_NO_ANCHOR`（诚实：协议已设计，物理锚缺失 ⇒ "
        "**永远不可**宣称 calibrated）。"),
    "interface": (
        "WDM 标定地基只给**接口**（与 `mesh_drive_manifest` 同形机器可判），"
        "**不是**可用标定方案。"),
}


class CalibrationProtocolError(Exception):
    """U10 协议层通用错误（非法状态转移 / 空输入 / 结构不符）。"""


class CalibrationRedlineError(CalibrationProtocolError):
    """触碰红线（foundry 工艺真值 / 伪造锚）。"""


class CalibrationAnchorError(CalibrationProtocolError):
    """锚缺失或不合格 ⇒ 不得据此宣称 calibrated。"""


# ---------------------------------------------------------------------------
# 2. 红线守卫（机器化）
# ---------------------------------------------------------------------------
_FORBIDDEN_PROCESS_TOKENS: Tuple[str, ...] = (
    "foundry", "tcad", "process_corner", "process_truth", "pdk_truth",
    "silicon_truth", "tapeout_truth", "工艺角", "工艺真值", "实测工艺",
)

#: 声明键（**自身即含 forbidden 令牌** ⇒ 扫描时必须豁免，否则守卫按构造恒红）。
_PDK_TRUTH_FLAG = "pdk_process_truth_used"


def _scan_keys(payload: Any, hits: List[str], path: str = "$") -> None:
    """递归收集**键名**命中 forbidden 令牌的路径。

    🔴 豁免 `_PDK_TRUTH_FLAG` 自身 —— 它是**必需**的声明键，若判它违规，
    守卫将按构造恒红 = 无用护栏（U8 血案同型）。该键的真假由
    `_collect_flag_values` 单独判。
    """
    if isinstance(payload, dict):
        for k, v in payload.items():
            key = str(k)
            if key == _PDK_TRUTH_FLAG:
                continue
            kl = key.lower()
            for tok in _FORBIDDEN_PROCESS_TOKENS:
                if tok in kl:
                    hits.append("%s.%s (令牌 %r)" % (path, key, tok))
                    break
            _scan_keys(v, hits, "%s.%s" % (path, key))
    elif isinstance(payload, (list, tuple)):
        for idx, v in enumerate(payload):
            _scan_keys(v, hits, "%s[%d]" % (path, idx))


def _collect_flag_values(payload: Any, out: List[Any]) -> None:
    """**任意深度**收集声明键的值（递归，不只顶层）。"""
    if isinstance(payload, dict):
        for k, v in payload.items():
            if str(k) == _PDK_TRUTH_FLAG:
                if isinstance(v, dict):
                    out.append(any(bool(x) for x in v.values()))
                else:
                    out.append(bool(v))
            _collect_flag_values(v, out)
    elif isinstance(payload, (list, tuple)):
        for v in payload:
            _collect_flag_values(v, out)


def guard_no_foundry_process_truth(payload: Any, where: str = "U10") -> None:
    """🔴 红线：载荷**键名**不得承载 foundry/TCAD/工艺角 真值，且声明键必须为假。

    只扫**键名**（散文里出现 "foundry" 属正常技术表述，不应触发 —— 见 smoke `B5`）。
    """
    hits: List[str] = []
    _scan_keys(payload, hits)
    if hits:
        raise CalibrationRedlineError(
            "%s：正文载荷键名承载 foundry 工艺真值（%s）—— 违反红线（无 NDA / 无准入）"
            % (where, "; ".join(hits)))
    flags: List[Any] = []
    _collect_flag_values(payload, flags)
    truthy = [f for f in flags if f]
    if truthy:
        raise CalibrationRedlineError(
            "%s：`%s` 被声明为真（共 %d 处）—— 本项目**无任何** PDK 工艺真值"
            % (where, _PDK_TRUTH_FLAG, len(truthy)))


def guard_anchor_kind_eligible(anchor: Any, where: str = "U10") -> None:
    """锚必须 `kind ∈ ANCHOR_KINDS` 且 `is_attested is True`。

    🔴 `literature` / `simulation` / `assumption` **不是**物理锚（§4.2 原文）。

    🔴 自纠（血案）：字段名原为 `is_true_process_truth`，**含 forbidden 令牌
    `process_truth`** ⇒ 被 `guard_no_foundry_process_truth` 的键扫描判违规 ⇒
    **守卫对唯一合法路径恒红（不可满足）**。已改名为 `is_attested`
    （语义保持：锚已坐实＝本项目真的持有 PDK 工艺角真值或实测标定数据）。
    smoke `B22` 钉住「合法锚 + 键扫描守卫**可满足**」。
    """
    if not isinstance(anchor, dict):
        raise CalibrationAnchorError(
            "%s：锚必须是 dict（含 kind / is_attested），收到 %s"
            % (where, type(anchor).__name__))
    kind = str(anchor.get("kind", ""))
    if kind not in ANCHOR_KINDS:
        raise CalibrationAnchorError(
            "%s：锚 kind=%r 不在可接受集合 %s 内 —— 文献/仿真**不算**物理锚"
            % (where, kind, list(ANCHOR_KINDS)))
    if anchor.get("is_attested") is not True:
        raise CalibrationAnchorError(
            "%s：锚 kind=%s 但 is_attested != True ⇒ 未坐实 ⇒ "
            "不得据此宣称 calibrated" % (where, kind))


def guard_calibration_requires_anchor(claim: Any, where: str = "U10") -> None:
    """🔴 **U10 核心门**：任何「已校准」声明必须绑定合格物理锚，否则 raise。

    非 calibrated 的声明（如 `claim="protocol_designed"`）**直接放行** —— 门只拦
    越界声明（这样守卫**可满足**，不是恒红）。
    """
    if not isinstance(claim, dict):
        raise CalibrationProtocolError(
            "%s：claim 必须是 dict，收到 %s" % (where, type(claim).__name__))
    tag = str(claim.get("claim", "")).strip().lower()
    if tag not in ("calibrated", "已校准"):
        return
    anchor = claim.get("anchor")
    if anchor is None:
        raise CalibrationAnchorError(
            "%s：宣称 calibrated 但**未绑定**物理锚（anchor=None）—— T1 违规"
            % where)
    guard_anchor_kind_eligible(anchor, where=where)


# ---------------------------------------------------------------------------
# 3. 解析 Jacobian（乘积法则；🔴 功率行**必须带共轭**）
# ---------------------------------------------------------------------------
def _Tmat(N: int, j: int, th: float, ph: float) -> np.ndarray:
    """单个 MZI 的显式 2×2 块（与 `mesh_pnr._ref_T_apply_rows` 同约定）。"""
    T = np.eye(N, dtype=complex)
    c, s, e = math.cos(th), math.sin(th), cmath.exp(1j * ph)
    T[j, j] = e * c
    T[j, j + 1] = -s
    T[j + 1, j] = e * s
    T[j + 1, j + 1] = c
    return T


def _dTdtheta(N: int, j: int, th: float, ph: float) -> np.ndarray:
    T = np.zeros((N, N), dtype=complex)
    c, s, e = math.cos(th), math.sin(th), cmath.exp(1j * ph)
    T[j, j] = e * (-s)
    T[j, j + 1] = -c
    T[j + 1, j] = e * c
    T[j + 1, j + 1] = -s
    return T


def _dTdphi(N: int, j: int, th: float, ph: float) -> np.ndarray:
    T = np.zeros((N, N), dtype=complex)
    c, s, e = math.cos(th), math.sin(th), cmath.exp(1j * ph)
    T[j, j] = 1j * e * c
    T[j + 1, j] = 1j * e * s
    return T


def _apply_order(bs_list: Sequence[Sequence[float]], color: Sequence[int],
                 n_cols: int) -> List[Tuple[int, int, float, float]]:
    """应用序（按列桶、桶内按 `bs_list` 下标升序）—— 与 `_forward_unitary` 逐位同序。

    返回 `[(bs_index, j, th, ph), ...]`。🔴 键是 **bs_index**，不是 `j`
    （`j` 是模式对下标，不同列可重复 ⇒ 拿它当键会列重复+缺失）。
    """
    buckets: List[List[Tuple[int, int, float, float]]] = [[] for _ in range(n_cols)]
    for i, b in enumerate(bs_list):
        buckets[color[i]].append((i, int(b[0]), float(b[1]), float(b[2])))
    seq: List[Tuple[int, int, float, float]] = []
    for c in range(n_cols):
        seq.extend(buckets[c])
    return seq


def mesh_params(N: int, bs_list: Sequence[Sequence[float]],
                D: np.ndarray) -> np.ndarray:
    """参数向量 `x = [θ, φ]×n_mzi ++ [arg D[k,k]]×N`（与 U6 `_pack_params` 同式）。"""
    x: List[float] = []
    for b in bs_list:
        x.append(float(b[1]))
        x.append(float(b[2]))
    dg = np.diag(np.asarray(D, dtype=complex))
    x.extend(float(np.angle(dg[k])) for k in range(len(dg)))
    return np.array(x, dtype=float)


def _jacobian_blocks(N: int, bs_list: Sequence[Sequence[float]], D: np.ndarray,
                     color: Sequence[int], n_cols: int
                     ) -> Tuple[np.ndarray, List[np.ndarray]]:
    """返回 `(U, [∂U/∂x_m])`，**列序 == 参数序**（θ,φ 交替、bs_index 升序、尾接 argD）。"""
    seq = _apply_order(bs_list, color, n_cols)
    pos_of_i = {i: s for s, (i, _, _, _) in enumerate(seq)}
    n_ops = len(seq)
    Ub: List[np.ndarray] = [np.eye(N, dtype=complex)]
    Ts: List[np.ndarray] = []
    for (_, j, th, ph) in seq:
        T = _Tmat(N, j, th, ph)
        Ts.append(T)
        Ub.append(T @ Ub[-1])
    R: List[Optional[np.ndarray]] = [None] * (n_ops + 1)
    R[n_ops] = np.eye(N, dtype=complex)
    for s in range(n_ops - 1, -1, -1):
        R[s] = R[s + 1] @ Ts[s]                       # type: ignore[operator]
    Dm = np.diag(np.diag(np.asarray(D, dtype=complex)))
    U = Dm @ Ub[n_ops]
    cols: List[np.ndarray] = []
    for i in range(len(bs_list)):
        s = pos_of_i[i]
        _, j, th, ph = seq[s]
        for dT in (_dTdtheta(N, j, th, ph), _dTdphi(N, j, th, ph)):
            cols.append(Dm @ (R[s + 1] @ dT @ Ub[s]))   # type: ignore[operator]
    dk = np.angle(np.diag(np.asarray(D, dtype=complex)))
    for k in range(N):
        dU = np.zeros((N, N), dtype=complex)
        dU[k, :] = 1j * cmath.exp(1j * dk[k]) * Ub[n_ops][k, :]
        cols.append(dU)
    return U, cols


def mesh_jacobian(N: int, bs_list: Sequence[Sequence[float]], D: np.ndarray,
                  color: Sequence[int], n_cols: int,
                  mode: str = "power") -> Dict[str, Any]:
    """网格 Jacobian（列序 == 参数序）。

    🔴 功率行 = `2·Re(conj(U) ⊙ dU)` —— **共轭不可省**：`|U_kl|²` 的导数就是
    `2·Re(conj(U_kl)·dU_kl)`。早期写成 `2·Re(U ⊙ dU)` 得到的是**另一个量**
    （对 argD 与 φ 列给出假的非零值 ⇒ 秩结论整体污染）。
    """
    if mode not in MEASUREMENT_MODES:
        raise CalibrationProtocolError("未知测量方案 %r（可选 %s）"
                                       % (mode, list(MEASUREMENT_MODES)))
    U, cols = _jacobian_blocks(N, bs_list, D, color, n_cols)
    if mode == "power":
        rows = [2.0 * (np.conj(U) * dU).real.ravel() for dU in cols]
    else:
        rows = [np.concatenate([dU.real.ravel(), dU.imag.ravel()]) for dU in cols]
    J = np.array(rows).T
    return {"J": J, "U": U, "n_params": len(cols), "n_ops": len(bs_list),
            "mode": mode,
            "n_observables": int(J.shape[0]),
            "n_argd": N, "n_mzi": len(bs_list)}


def power_jacobian(N: int, bs_list, D, color, n_cols) -> np.ndarray:
    return mesh_jacobian(N, bs_list, D, color, n_cols, "power")["J"]


def complex_jacobian(N: int, bs_list, D, color, n_cols) -> np.ndarray:
    return mesh_jacobian(N, bs_list, D, color, n_cols, "complex")["J"]


def lam_scale_vector(N: int, bs_list: Sequence[Sequence[float]],
                     lam_nm: float) -> np.ndarray:
    """色散缩放（U1 约定）：**θ 无色散**；φ 与 argD 按 `λ_ref/λ` 缩放。"""
    if lam_nm <= 0.0:
        raise CalibrationProtocolError("波长必须 > 0，收到 %r" % (lam_nm,))
    s = LAM_REF_NM / float(lam_nm)
    v: List[float] = []
    for _ in bs_list:
        v.extend([1.0, s])
    v.extend([s] * N)
    return np.array(v, dtype=float)


def multi_lambda_jacobian(N: int, bs_list: Sequence[Sequence[float]], D: np.ndarray,
                          color: Sequence[int], n_cols: int, x: np.ndarray,
                          lams_nm: Sequence[float],
                          mode: str = "power") -> np.ndarray:
    """多波长堆叠 Jacobian：每个 λ 的块**按链式法则**乘该 λ 的缩放向量。"""
    lams = [float(l) for l in lams_nm]
    if not lams:
        raise CalibrationProtocolError("波长列表不能为空")
    blocks: List[np.ndarray] = []
    for lam in lams:
        sv = lam_scale_vector(N, bs_list, lam)
        xk = np.asarray(x, dtype=float) * sv
        bs2: List[Tuple[int, float, float]] = []
        k = 0
        for b in bs_list:
            bs2.append((int(b[0]), float(xk[2 * k]), float(xk[2 * k + 1])))
            k += 1
        n_mzi = len(bs_list)
        dph = xk[2 * n_mzi:2 * n_mzi + N]
        D2 = np.diag(np.array([cmath.exp(1j * float(a)) for a in dph], dtype=complex))
        Jk = mesh_jacobian(N, bs2, D2, color, n_cols, mode)["J"]
        blocks.append(Jk * sv[None, :])
    return np.vstack(blocks)


# ---------------------------------------------------------------------------
# 4. 秩定律 / 冻结实测值 / 可辨识性诊断
# ---------------------------------------------------------------------------
def power_rank_law(N: int) -> int:
    """**一般位置**功率（强度）读出秩上界 = (N−1)²（= 双随机流形维数）。"""
    return (N - 1) ** 2


def complex_rank_law(N: int) -> int:
    """相位敏感读出秩 = N²（满秩）。"""
    return N * N


def power_blind_dims(N: int) -> int:
    """功率读出的盲维数 = N² − (N−1)² = **2N−1**。"""
    return 2 * N - 1


#: 🔴 冻结实测值（`_generic_unitary` 族；全精度）：N → (功率秩, 功率 σmin/σmax,
#: 复场秩, 复场 σmin/σmax, n_mzi)。来源：本轮 `u10_probe9` 实测。
MEASURED_RANK_TABLE: Dict[int, Tuple[int, float, int, float, int]] = {
    2: (1, 1.0, 4, 0.27701824309457973, 1),
    3: (4, 0.16970718896916615, 9, 0.21815589355211254, 3),
    4: (9, 0.001495306710455433, 16, 0.038337937970041279, 6),
    5: (16, 0.0020751485787276242, 25, 0.03050868098625855, 10),
    6: (25, 0.00031704261571264148, 36, 0.011951205381970772, 15),
    7: (36, 1.5276196506452414e-05, 49, 0.005609167750020249, 21),
    8: (49, 5.2182608390817222e-06, 64, 0.00055909575098974068, 28),
}

#: 功率 σ 间隙（N → (σ_r/σmax, σ_{r+1}/σmax, 间隙)）：真零 ~1e-16..1e-17 与
#: 最小非零之间的**深谷**（1e10..1e13 量级）⇒ 秩判据不敏感于阈值微调。
MEASURED_SIGMA_GAP: Dict[int, Tuple[float, float, float]] = {
    4: (0.001495306710455433, 7.8339592204626731e-17, 19087496735362.383),
    6: (0.00031704261571264148, 8.2528667770547884e-17, 3841605884080.2578),
    8: (5.2182608390817222e-06, 1.1666316361913579e-16, 44729293096.469673),
}

#: 🔴 **退化族**证据：DFT 酉的功率秩**低于** (N−1)²（N=4/6/8）—— 与 U6
#: 「DFT 在某些 N 下分解出现退化角」同源 ⇒ 秩定律是**一般位置**结论。
DFT_POWER_RANK: Dict[int, int] = {2: 1, 3: 4, 4: 8, 5: 16, 6: 21, 7: 36, 8: 44}


def rank_report(J: np.ndarray, tol: float = SVD_ZERO_TOL) -> Dict[str, Any]:
    """奇异值谱 → 秩 / 亏缺 / σmin / 条件数。σmin 取**最小非零**（相对 σmax）。"""
    s = np.linalg.svd(np.asarray(J, dtype=float), compute_uv=False)
    smax = float(s[0]) if s.size else 0.0
    if smax <= 0.0:
        raise CalibrationProtocolError("Jacobian 全零 ⇒ 无奇异值信息")
    nz = s[s / smax > tol]
    rank = int(nz.size)
    smin = float(nz[-1] / smax) if rank else 0.0
    nxt = float(s[rank] / smax) if rank < s.size else 0.0
    return {
        "rank": rank, "n_singular": int(s.shape[0]),
        "n_rows": int(np.asarray(J).shape[0]), "n_cols": int(np.asarray(J).shape[1]),
        "sigma_max": smax, "sigma_min_nonzero_ratio": smin,
        "sigma_next_ratio": nxt, "gap": (smin / nxt) if nxt > 0.0 else float("inf"),
        "cond": (1.0 / smin) if smin > 0.0 else float("inf"),
        "tol": float(tol),
    }


def _unitary_of(N: int, unitary: Optional[np.ndarray]) -> np.ndarray:
    return _generic_unitary(N) if unitary is None else np.asarray(unitary, dtype=complex)


def identifiability_report(N: int, mode: str = "power",
                           lams_nm: Optional[Sequence[float]] = None,
                           unitary: Optional[np.ndarray] = None,
                           tol: float = SVD_ZERO_TOL) -> Dict[str, Any]:
    """U10 设计层核心诊断：**这个测量方案能不能定出参数**。

    🔴 结论对**功率读出**是**否决性**的：秩 = (N−1)²、亏缺 2N−1，
    且 `argD` 块**恒为 0** ⇒ 输出相位 N 维**永不可观测**（加 λ 也不行）。
    """
    U = _unitary_of(N, unitary)
    parts = _mesh_parts(U)
    bs, D, color, n_cols = parts["bs_list"], parts["D"], parts["color"], parts["n_cols"]
    x = mesh_params(N, bs, D)
    lams = list(lams_nm) if lams_nm else [LAM_REF_NM]
    J = multi_lambda_jacobian(N, bs, D, color, n_cols, x, lams, mode)
    rep = rank_report(J, tol)
    rep["n_params"] = int(x.size)
    rep["deficit"] = int(x.size) - rep["rank"]
    single = multi_lambda_jacobian(N, bs, D, color, n_cols, x, [LAM_REF_NM], mode)
    block = single[:, 2 * parts["n_mzi"]:]
    argd_max = float(np.max(np.abs(block))) if block.size else 0.0
    law = power_rank_law(N) if mode == "power" else complex_rank_law(N)
    return {
        "N": int(N), "mode": mode, "lams_nm": lams, "n_lambda": len(lams),
        "n_mzi": int(parts["n_mzi"]), "n_cols": int(n_cols),
        "n_params": int(x.size), "rank": rep["rank"], "rank_law": int(law),
        "law_holds": bool(rep["rank"] == law),
        "deficit": rep["deficit"],
        "blind_dims": (power_blind_dims(N) if mode == "power" else 0),
        "argd_block_max": argd_max,
        "argd_invisible": bool(argd_max <= 1e-14),
        "argd_blind_dims": int(N),
        "sigma_min_ratio": rep["sigma_min_nonzero_ratio"],
        "sigma_next_ratio": rep["sigma_next_ratio"],
        "sigma_gap": rep["gap"], "cond": rep["cond"],
        "identifiable": bool(rep["rank"] == x.size),
        "meets_sigma_floor": bool(rep["sigma_min_nonzero_ratio"] >= CONDITION_SIGMA_FLOOR),
        "verdict": _verdict(mode, rep, x.size),
    }


def _verdict(mode: str, rep: Dict[str, Any], n_params: int) -> str:
    if rep["rank"] == n_params:
        return "identifiable" if rep["sigma_min_nonzero_ratio"] >= CONDITION_SIGMA_FLOOR \
            else "identifiable-but-ill-conditioned"
    if mode == "power":
        return "power-only-structurally-unidentifiable"
    return "unidentifiable"


def wdm_rank_sweep(N: int, lam_sets: Optional[Sequence[Sequence[float]]] = None,
                   mode: str = "power",
                   unitary: Optional[np.ndarray] = None) -> Dict[str, Any]:
    """🔴 **WDM 不能解锁**：K 从 1 增长到 |λ 集| 时秩**不变**（实测）。"""
    sets = list(lam_sets) if lam_sets else [[LAM_REF_NM], list(WDM_LAM_DEFAULT),
                                            [LAM_REF_NM, 1600.0], list(WDM_LAM_WIDE)]
    U = _unitary_of(N, unitary)
    parts = _mesh_parts(U)
    bs, D, color, n_cols = parts["bs_list"], parts["D"], parts["color"], parts["n_cols"]
    x = mesh_params(N, bs, D)
    rows: List[Dict[str, Any]] = []
    for lams in sets:
        rep = rank_report(multi_lambda_jacobian(N, bs, D, color, n_cols, x, lams, mode))
        rows.append({"K": len(lams), "lams_nm": [float(l) for l in lams],
                     "span_nm": float(max(lams) - min(lams)),
                     "rank": rep["rank"], "deficit": int(x.size) - rep["rank"]})
    return {
        "N": int(N), "mode": mode, "n_params": int(x.size), "sweep": rows,
        "rank_gain_per_lambda": int(rows[-1]["rank"] - rows[0]["rank"]),
        "rank_constant": bool(len({r["rank"] for r in rows}) == 1),
        "honest_note": (
            "色散把 θ 与 φ/argD 分开，但 **argD 块对任何 λ 都恒为 0**（|U|² 不含输出相位），"
            "且 (θ,φ) 内的 N−1 维盲方向在实测的所有 K/间隔下**均未消失** ⇒ "
            "WDM 不是解锁路径（对 (N−1)² 秩障碍无贡献）。"),
    }


def forward_consistency(N: int, unitary: Optional[np.ndarray] = None) -> Dict[str, Any]:
    """方法自证 A：解析前向 `U` 与官方 `_forward_unitary` 是否逐位一致。"""
    U = _unitary_of(N, unitary)
    parts = _mesh_parts(U)
    bs, D, color, n_cols = parts["bs_list"], parts["D"], parts["color"], parts["n_cols"]
    jac = mesh_jacobian(N, bs, D, color, n_cols, "power")
    dU = float(np.max(np.abs(jac["U"] - _forward_unitary(bs, D, N))))
    return {"N": int(N), "max_abs_diff": dU, "exact": bool(dU <= 1e-14)}


# ---------------------------------------------------------------------------
# 5. 标定状态机（协议骨架）
# ---------------------------------------------------------------------------
CAL_STATES: Tuple[str, ...] = (
    "UNCALIBRATED", "PROTOCOL_DESIGNED", "IDENTIFIABILITY_VERIFIED",
    "ANCHOR_BOUND", "CALIBRATED", "BLOCKED_NO_ANCHOR", "STALE", "FAILED",
)

CAL_TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    "UNCALIBRATED": ("PROTOCOL_DESIGNED", "FAILED"),
    "PROTOCOL_DESIGNED": ("IDENTIFIABILITY_VERIFIED", "BLOCKED_NO_ANCHOR", "FAILED"),
    "IDENTIFIABILITY_VERIFIED": ("ANCHOR_BOUND", "BLOCKED_NO_ANCHOR", "FAILED"),
    "ANCHOR_BOUND": ("CALIBRATED", "FAILED"),
    "CALIBRATED": ("STALE", "FAILED"),
    "BLOCKED_NO_ANCHOR": ("ANCHOR_BOUND", "FAILED"),
    "STALE": ("ANCHOR_BOUND", "FAILED"),
    "FAILED": (),
}

#: 🔴 **单一真值来源**：进入 `CALIBRATED` 必须为真的布尔证据键。
#: `CAL_EVIDENCE_REQUIRED` 与 `advance()` 都从它派生。
#: 血案（本轮突变探针实测）：曾把 `drift_checked` 只从 `CAL_EVIDENCE_REQUIRED`
#: 里删掉 ⇒ 24 项突变探针**抓不住**（GREEN —— 判据缺口），因为 `advance()` 里
#: 另有一份硬编码元组。⇒ 收敛为单一真值来源 + 加「派生一致」判据（smoke `C20`）。
CALIBRATED_TRUTH_KEYS: Tuple[str, ...] = (
    "scheme_identifiable", "closed_loop_converged", "drift_checked")

#: 🔴 进入这些状态所需的**证据键**（缺一即 raise）。
CAL_EVIDENCE_REQUIRED: Dict[Tuple[str, str], Tuple[str, ...]] = {
    ("UNCALIBRATED", "PROTOCOL_DESIGNED"): ("protocol_steps",),
    ("PROTOCOL_DESIGNED", "IDENTIFIABILITY_VERIFIED"): ("scheme_identifiable",),
    ("IDENTIFIABILITY_VERIFIED", "ANCHOR_BOUND"): ("anchor",),
    ("BLOCKED_NO_ANCHOR", "ANCHOR_BOUND"): ("anchor",),
    ("STALE", "ANCHOR_BOUND"): ("anchor",),
    ("ANCHOR_BOUND", "CALIBRATED"): ("anchor",) + CALIBRATED_TRUTH_KEYS,
}


class CalibrationStateMachine:
    """标定**流程**状态机（只做流程骨架，不做能力宣称）。

    🔴 关键门：进入 `ANCHOR_BOUND` / `CALIBRATED` 必须提供合格物理锚；
    进入 `CALIBRATED` 还必须给出**闭环收敛**与**漂移复检**证据。
    本项目无锚 ⇒ 终态 `BLOCKED_NO_ANCHOR`。
    """

    def __init__(self, initial: str = "UNCALIBRATED") -> None:
        if initial not in CAL_STATES:
            raise CalibrationProtocolError("未知初始状态 %r" % (initial,))
        self._state = initial
        self._history: List[Tuple[str, Optional[str]]] = [(initial, None)]

    @property
    def state(self) -> str:
        return self._state

    def history(self) -> List[Tuple[str, Optional[str]]]:
        return list(self._history)

    def legal_targets(self) -> Tuple[str, ...]:
        return CAL_TRANSITIONS[self._state]

    def advance(self, target: str, evidence: Optional[Dict[str, Any]] = None) -> str:
        if target not in CAL_STATES:
            raise CalibrationProtocolError("未知目标状态 %r" % (target,))
        if target not in self.legal_targets():
            raise CalibrationProtocolError(
                "非法转移 %s → %s（合法目标 %s）"
                % (self._state, target, list(self.legal_targets())))
        ev: Dict[str, Any] = dict(evidence or {})
        for key in CAL_EVIDENCE_REQUIRED.get((self._state, target), ()):  # 缺键即挡
            if key not in ev:
                raise CalibrationProtocolError(
                    "%s → %s 需要证据键 %r（当前证据 %s）"
                    % (self._state, target, key, sorted(ev)))
        if "anchor" in CAL_EVIDENCE_REQUIRED.get((self._state, target), ()):
            guard_anchor_kind_eligible(ev.get("anchor"), where="%s→%s" % (self._state, target))
        if target == "CALIBRATED":
            # 🔴 双重门：既要锚，也要「已宣称 calibrated」通过核心门。
            guard_calibration_requires_anchor(
                {"claim": "calibrated", "anchor": ev.get("anchor")},
                where="%s→CALIBRATED" % self._state)
            # 🔴 布尔证据从 **单一真值来源** 派生（不在此另写一份硬编码元组）。
            for key in CALIBRATED_TRUTH_KEYS:
                if ev.get(key) is not True:
                    raise CalibrationProtocolError(
                        "%s→CALIBRATED 要求 %s is True，收到 %r" % (self._state, key, ev.get(key)))
        self._state = target
        self._history.append((target, str(ev.get("reason", "")) or None))
        return self._state

    def can_claim_calibrated(self) -> bool:
        return self._state == "CALIBRATED"


def project_calibration_state(N: int = 8, mode: str = "complex",
                              lams_nm: Optional[Sequence[float]] = None,
                              anchor: Optional[Dict[str, Any]] = None,
                              closed_loop_converged: bool = False,
                              drift_checked: bool = False) -> Dict[str, Any]:
    """把**本项目真实现状**灌进状态机 ⇒ 诚实终态（默认 = `BLOCKED_NO_ANCHOR`）。"""
    m = CalibrationStateMachine()
    m.advance("PROTOCOL_DESIGNED", {"protocol_steps": len(CAL_PROTOCOL_STEPS)})
    ident = identifiability_report(N, mode=mode, lams_nm=lams_nm)
    if ident["identifiable"]:
        m.advance("IDENTIFIABILITY_VERIFIED",
                  {"scheme_identifiable": True,
                   "reason": "mode=%s N=%d 满秩 %d" % (mode, N, ident["rank"])})
    else:
        m.advance("FAILED", {"reason": "方案在结构上不可辨识：mode=%s N=%d 秩=%d<%d（亏缺 %d）"
                                       % (mode, N, ident["rank"], ident["n_params"],
                                          ident["deficit"])})
    blocked: List[str] = []
    if m.state == "IDENTIFIABILITY_VERIFIED":
        if anchor is None:
            blocked.append("physical_anchor_absent")
            m.advance("BLOCKED_NO_ANCHOR",
                      {"reason": "无物理锚（PDK 工艺角 / 实测标定数据均缺）"})
        else:
            m.advance("ANCHOR_BOUND", {"anchor": anchor})
            m.advance("CALIBRATED", {"anchor": anchor, "scheme_identifiable": True,
                                     "closed_loop_converged": bool(closed_loop_converged),
                                     "drift_checked": bool(drift_checked)})
    return {
        "state": m.state, "history": m.history(),
        "can_claim_calibrated": m.can_claim_calibrated(),
        "blocked_by": blocked,
        "identifiability": ident,
        "anchors_available": list(ANCHORS_AVAILABLE_TO_THIS_PROJECT),
        "honest_note": (
            "协议**已设计**且方案可辨识性**已机器自检**，但物理锚缺失 ⇒ "
            "状态停在 `BLOCKED_NO_ANCHOR`：**不可**宣称 calibrated，"
            "也**不可**把本状态机的任何中间态写成「已校准」。"),
    }


# ---------------------------------------------------------------------------
# 6. 标定协议步骤表 + 自检判据（S1..S7）
# ---------------------------------------------------------------------------
CAL_PROTOCOL_STEPS: Tuple[Dict[str, Any], ...] = (
    {"id": "P1", "name": "绑定物理锚",
     "input": ("PDK 工艺角真值", "本工艺实测标定数据"),
     "output": "锚记录（kind ∈ ANCHOR_KINDS + is_attested=True）",
     "requires_anchor": True, "blocking": True,
     "blocked_reason": "本项目无 NDA / 无实测标定 ⇒ 锚缺失（唯一硬阻断）"},
    {"id": "P2", "name": "选定读出方案并做可辨识性自检",
     "input": ("网格拓扑（bs_list/D）", "λ 栅格", "探测方案 power|complex"),
     "output": "`identifiability_report`（秩 / 亏缺 / σmin / 盲维）",
     "requires_anchor": False, "blocking": True,
     "blocked_reason": "功率读出秩 (N−1)² < N² ⇒ 该方案**不可**用于全参标定"},
    {"id": "P3", "name": "逐 MZI 粗调（开环，按网格拓扑序）",
     "input": ("θ/φ 目标", "分解列序"),
     "output": "粗调后的驱动清单（与 `mesh_drive_manifest` 同形）",
     "requires_anchor": True, "blocking": True,
     "blocked_reason": "绝对驱动量（Vπ·L / 热效率）来自 PDK 或实测 ⇒ 无锚则量纲不可落地"},
    {"id": "P4", "name": "建立相位参考（相干读出）",
     "input": ("参考臂 / LO", "正交读出"),
     "output": "复场可观测量（Re/Im U）",
     "requires_anchor": False, "blocking": True,
     "blocked_reason": "无相位参考则退化为功率读出 ⇒ 结构性不可解（结论②）"},
    {"id": "P5", "name": "闭环收敛（per-MZI 热/相）",
     "input": ("复场观测", "逐 MZI 执行器"),
     "output": "收敛判据（残差 ≤ 目标）",
     "requires_anchor": True, "blocking": True,
     "blocked_reason": "热串扰矩阵与工艺角未知 ⇒ 环路增益/稳定性不可证明（结论：不授权闭合）"},
    {"id": "P6", "name": "全网格保真度验收",
     "input": ("复场 / 功率矩阵", "目标 U"),
     "output": "保真度 ≥ 目标（判据同 `mesh_rect_fidelity`）",
     "requires_anchor": True, "blocking": True,
     "blocked_reason": "验收阈值须由实测重复性给出 ⇒ 无锚只能给占位阈值"},
    {"id": "P7", "name": "漂移再标定",
     "input": ("历史标定点", "环境条件"),
     "output": "再标定周期（含不确定度）",
     "requires_anchor": True, "blocking": False,
     "blocked_reason": "周期须由本器件实测漂移率给出 ⇒ 本项目只能给**占位**、不可引用"},
)

SELFCHECK_CRITERIA: Tuple[Tuple[str, str], ...] = (
    ("S1", "方案**满秩可解**（rank == n_params == N²）"),
    ("S2", "盲维审计自洽（功率: 盲维 == 2N−1 且 argD 块 ≡ 0；复场: 盲维 == 0 且 argD 块 ≠ 0）"),
    ("S3", "σmin/σmax ≥ 地板（地板为**设计占位**、非 PDK 规格）"),
    ("S4", "物理锚已绑定（kind ∈ ANCHOR_KINDS 且 is_attested）"),
    ("S5", "闭环收敛证据（per-MZI 残差 ≤ 目标）"),
    ("S6", "漂移复检已完成（周期由实测给出）"),
    ("S7", "可宣称 calibrated（= S1..S6 全过 + 核心门放行）"),
)


def selfcheck_report(N: int = 8, mode: str = "complex",
                     lams_nm: Optional[Sequence[float]] = None,
                     anchor: Optional[Dict[str, Any]] = None,
                     closed_loop_converged: bool = False,
                     drift_checked: bool = False) -> Dict[str, Any]:
    """自检判据报告：S1..S7 逐条机器判定（本项目预期 S4/S5/S6/S7 红）。"""
    ident = identifiability_report(N, mode=mode, lams_nm=lams_nm)
    anchor_ok = False
    anchor_reason = "未提供锚"
    if anchor is not None:
        try:
            guard_anchor_kind_eligible(anchor, where="selfcheck")
            anchor_ok, anchor_reason = True, "锚合格（%s）" % anchor.get("kind")
        except CalibrationAnchorError as exc:
            anchor_reason = str(exc)

    checks: List[Dict[str, Any]] = []

    def add(cid: str, desc: str, ok: bool, detail: str) -> None:
        checks.append({"id": cid, "desc": desc, "ok": bool(ok), "detail": detail})

    add("S1", SELFCHECK_CRITERIA[0][1], bool(ident["identifiable"]),
        "rank=%d n_params=%d 定律=%d mode=%s N=%d"
        % (ident["rank"], ident["n_params"], ident["rank_law"], mode, N))
    if mode == "power":
        s2_ok = bool(ident["blind_dims"] == power_blind_dims(N) and ident["argd_invisible"])
        s2_detail = ("功率：盲维=%d 期望=%d argD块max=%.2e（应 ≡0）"
                     % (ident["blind_dims"], power_blind_dims(N), ident["argd_block_max"]))
    else:
        s2_ok = bool(ident["blind_dims"] == 0 and not ident["argd_invisible"])
        s2_detail = ("复场：盲维=%d 期望=0 argD块max=%.2e（应 ≠0 ⇒ 输出相位可观测）"
                     % (ident["blind_dims"], ident["argd_block_max"]))
    add("S2", SELFCHECK_CRITERIA[1][1], s2_ok, s2_detail)
    add("S3", SELFCHECK_CRITERIA[2][1], ident["meets_sigma_floor"],
        "σmin/σmax=%.4e 地板=%.1e" % (ident["sigma_min_ratio"], CONDITION_SIGMA_FLOOR))
    add("S4", SELFCHECK_CRITERIA[3][1], anchor_ok, anchor_reason)
    add("S5", SELFCHECK_CRITERIA[4][1], bool(closed_loop_converged),
        "closed_loop_converged=%r（热串扰未知 ⇒ 不授权闭合）" % closed_loop_converged)
    add("S6", SELFCHECK_CRITERIA[5][1], bool(drift_checked),
        "drift_checked=%r（无实测漂移率 ⇒ 周期只能占位）" % drift_checked)
    gate = all(c["ok"] for c in checks[:6])
    if anchor is not None and anchor_ok:
        try:
            guard_calibration_requires_anchor({"claim": "calibrated", "anchor": anchor})
        except CalibrationAnchorError as exc:
            gate, anchor_reason = False, str(exc)
    add("S7", SELFCHECK_CRITERIA[6][1], bool(gate and anchor_ok),
        "S1..S6 全过=%s 且锚合格=%s" % (gate, anchor_ok))
    n_pass = sum(1 for c in checks if c["ok"])
    return {
        "N": int(N), "mode": mode, "checks": checks,
        "n_pass": n_pass, "n_total": len(checks),
        "passes_calibration_gate": bool(all(c["ok"] for c in checks)),
        "verdict": ("calibrated-claimable" if all(c["ok"] for c in checks)
                    else "not-calibrated-claimable"),
        "honest_note": (
            "S1（满秩可解）是**结构门**：功率读出恒不过（秩 (N−1)² < N² = n_params）"
            "⇒ 只能改**测量方案**（相干读出），软件/算法不可修（与 U6「结构冗余 = 0」、"
            "U7「编译层自由度 = 0」同族）。S4（物理锚）是本项目**唯一**不可由"
            "仿真/算法补齐的项 —— 这正是 §4.2 判 U10「最不能靠仿真解锁」的机器化表述。"),
    }


# ---------------------------------------------------------------------------
# 7. WDM 标定地基接口（与 `mesh_drive_manifest` 同形）
# ---------------------------------------------------------------------------
#: 同形性**必需共有键**（机器可判；差异必须被解释而不是被容忍）。
PARITY_KEYS_VS_DRIVE_MANIFEST: Tuple[str, ...] = ("n_mzi", "n_out", "mzi", "out")


def wdm_calibration_manifest(bs_list: Sequence[Sequence[float]], D: np.ndarray,
                             lams_nm: Sequence[float], N: int,
                             mode: str = "power") -> Dict[str, Any]:
    """WDM 标定地基的**接口定义**（只管形状与色散约定，不宣称可用）。

    🔴 `basis_ready` 恒为 `False`（缺物理锚）——接口就绪 ≠ 方案可用。
    """
    from lda_layout.mesh_pnr import _rect_column_assignment, mesh_drive_manifest

    color = list(_rect_column_assignment(bs_list))
    ops = [(int(b[0]), float(b[1]), float(b[2]), int(c)) for b, c in zip(bs_list, color)]
    drive = mesh_drive_manifest(ops, D, ps_arm_um=ARM_REF_UM)
    lams = [float(l) for l in lams_nm]
    if not lams:
        raise CalibrationProtocolError("λ 列表不能为空")
    sweep = wdm_rank_sweep(N, [lams[:k] for k in range(1, len(lams) + 1)], mode,
                           unitary=_forward_unitary(bs_list, D, N))
    return {
        "lams_nm": lams, "n_lambda": len(lams), "lam_ref_nm": LAM_REF_NM,
        "n_mzi": drive["n_mzi"], "n_out": drive["n_out"],
        "mzi": drive["mzi"], "out": drive["out"],
        "ps_arm_um": drive["ps_arm_um"],
        "mode": mode,
        "dispersion_model": "theta: 无色散；phi/argD: ×(λ_ref/λ)",
        "wave_grid_ranks": sweep["sweep"],
        "rank_gain_per_lambda": sweep["rank_gain_per_lambda"],
        "identifiable": bool(identifiability_report(N, mode=mode, lams_nm=lams,
                                                   unitary=_forward_unitary(bs_list, D, N)
                                                   )["identifiable"]),
        "basis_ready": False,
        "blocked_by": ["physical_anchor_absent"],
        "honest_note": (
            "接口与 `mesh_drive_manifest` **同形**（共用 %s）⇒ 可做同名替换实验；"
            "但多波长**不提升秩**（实测增益 %d）⇒ 它**不是**解锁路径，只是把色散"
            "这一维**参数化**下来。" % (list(PARITY_KEYS_VS_DRIVE_MANIFEST),
                                    sweep["rank_gain_per_lambda"])),
        "disclosed": "本清单是**接口定义**产物，不构成能力宣称；可用性需物理锚 + 实测。",
    }


def per_mzi_calibration_plan(bs_list: Sequence[Sequence[float]], D: np.ndarray,
                             N: int, mode: str = "complex") -> Dict[str, Any]:
    """逐 MZI 标定方案（**开环骨架**；闭环 `closed_loop_enabled=False`）。"""
    from lda_layout.mesh_pnr import _rect_column_assignment

    if int(N) != int(np.asarray(D).shape[0]):
        raise CalibrationProtocolError("N=%d 与 D 的阶 %d 不符" % (N, np.asarray(D).shape[0]))
    color = list(_rect_column_assignment(bs_list))
    n_cols = max(color) + 1 if color else 0
    seq = _apply_order(bs_list, color, n_cols)
    seq_index = {i: s for s, (i, _, _, _) in enumerate(seq)}
    col_order: Dict[int, int] = {}
    counter: Dict[int, int] = {}
    for (i, _, _, _) in seq:
        c = int(color[i])
        col_order[i] = counter.get(c, 0)
        counter[c] = col_order[i] + 1
    entries: List[Dict[str, Any]] = []
    for i, b in enumerate(bs_list):
        entries.append({
            "i": int(i), "j": int(b[0]), "col_c": int(color[i]),
            "seq_index": int(seq_index[i]),
            "col_order": int(col_order[i]),
            "theta_target_rad": float(b[1]), "phi_target_rad": float(b[2]),
            "actuator": "per-MZI 热相（thermal）",
            "observable": ("复场 Re/Im U" if mode == "complex" else "|U|²（**结构性不可解**）"),
            "requires_anchor": True,
            "closed_loop_gain": None,
        })
    return {
        "n_mzi": len(entries), "mode": mode, "entries": entries,
        "open_loop_reference_only": True,
        "loop": {
            "actuator": "per-MZI 热相",
            "sensor": "输出端口" + ("复场（相干）" if mode == "complex" else "功率"),
            "feedback": "残差 → 逐 MZI 增量修正",
            "closed_loop_enabled": False,
            "why_disabled": (
                "热串扰矩阵 + 工艺角 + 探测器噪声底**均未知** ⇒ 环路增益/稳定性"
                "不可证明；且无物理锚 ⇒ T1 禁止闭合。"),
        },
        "honest_note": (
            "本方案给的是**协议骨架与通道枚举**（与 `mesh_drive_manifest` 的通道集"
            "一致），不是可直接执行的固件；执行需 P1（物理锚）先过。"),
    }


def protocol_interface_parity(N: int = 4) -> Dict[str, Any]:
    """**同形性机器判据**：WDM 标定清单 vs `mesh_drive_manifest` vs U8 驱动清单。"""
    from lda_layout.mesh_pnr import mesh_drive_manifest
    from lda_l2.nonvolatile_weight_backend import (
        DEFAULT_MATERIAL, nvm_drive_manifest)

    U = _generic_unitary(N)
    parts = _mesh_parts(U)
    bs, D, color = parts["bs_list"], parts["D"], parts["color"]
    wdm = wdm_calibration_manifest(bs, D, WDM_LAM_DEFAULT, N, "complex")
    ops = [(int(b[0]), float(b[1]), float(b[2]), int(c)) for b, c in zip(bs, color)]
    dm = mesh_drive_manifest(ops, D, ps_arm_um=ARM_REF_UM)
    nvm = nvm_drive_manifest([0.1, 0.2], mat=DEFAULT_MATERIAL)

    need = set(PARITY_KEYS_VS_DRIVE_MANIFEST)
    wk, dk, nk = set(wdm), set(dm), set(nvm)
    return {
        "wdm_keys": sorted(wk), "drive_manifest_keys": sorted(dk),
        "nvm_manifest_keys": sorted(nk),
        "required_shared": sorted(need),
        "wdm_vs_drive_ok": bool(need <= wk and need <= dk),
        "wdm_vs_nvm_ok": bool(need <= nk),
        "shared_all_three": sorted(wk & dk & nk),
        "only_wdm": sorted(wk - dk),
        "expected_semantic_diff": {
            "drive": "驱动量是**电压 V**（热光）；U10 清单是**协议通道枚举**（含色散/读出）",
            "nvm": "U8 驱动量是**晶化率 c / 电平号**（非易失）；与 U10 的通道语义不同",
        },
        "honest_note": (
            "同形 ≠ 同物理：三者共用**信道枚举形状**（便于同名替换实验），"
            "但器件量、可达区间与阻断条件完全不同，**不可互换**。"),
    }


# ---------------------------------------------------------------------------
# 8. 报告入口（红线守卫在必经路径上运行）
# ---------------------------------------------------------------------------
def calibration_protocol_report(N: int = 8, mode: str = "complex",
                                lams_nm: Optional[Sequence[float]] = None,
                                unitary: Optional[np.ndarray] = None,
                                anchor: Optional[Dict[str, Any]] = None
                                ) -> Dict[str, Any]:
    """U10 协议设计**总报告**。

    🔴 `guard_no_foundry_process_truth` 在函数入口运行 ⇒ 红线是**机器化**的。
    """
    U = _unitary_of(N, unitary)
    parts = _mesh_parts(U)
    bs, D = parts["bs_list"], parts["D"]
    lams = list(lams_nm) if lams_nm else [LAM_REF_NM]
    # 🔴 声明式 claim：有锚 ⇒ 真的走一次核心门（并校验锚）；无锚 ⇒ 登记为**非宣称**。
    claim: Dict[str, Any] = {"claim": ("calibrated" if anchor is not None
                                       else "protocol_designed"), "anchor": anchor}
    payload: Dict[str, Any] = {
        "N": int(N),
        "claim": dict(claim),
        "anchor_kinds": list(ANCHOR_KINDS),
        "anchors_available": list(ANCHORS_AVAILABLE_TO_THIS_PROJECT),
        "protocol_steps": [dict(s) for s in CAL_PROTOCOL_STEPS],
        "state_machine": {
            "states": list(CAL_STATES),
            "transitions": {k: list(v) for k, v in CAL_TRANSITIONS.items()},
        },
        "identifiability": identifiability_report(N, mode=mode, lams_nm=lams,
                                                  unitary=U),
        "wdm": wdm_rank_sweep(N, None, "power", unitary=U),
        "selfcheck": selfcheck_report(N, mode=mode, lams_nm=lams, anchor=anchor),
        "interface": wdm_calibration_manifest(bs, D, lams, N, mode=mode),
        "per_mzi_plan": per_mzi_calibration_plan(bs, D, N, mode=mode),
        "guard_declaration": {_PDK_TRUTH_FLAG: False,
                              "anchors_measured_by_this_project": False,
                              "calibrated_claim_made": bool(anchor is not None)},
        "disclosure": dict(CAL_DISCLOSURE),
        # 🔴 散文（含 foundry / PDK 等词）单独放，**不进**键扫描对象 —— 守卫只扫键名。
        "prose": {
            "redline": "不碰 foundry 工艺真值（无 NDA / 无准入）。",
            "capability": "不做能力宣称：本报告是协议 + 自检判据 + 接口定义。",
        },
    }
    guard_no_foundry_process_truth(
        {k: v for k, v in payload.items() if k not in ("prose", "disclosure")},
        where="calibration_protocol_report")
    guard_calibration_requires_anchor(claim, where="calibration_protocol_report")
    return payload


if __name__ == "__main__":       # pragma: no cover - 人工自测入口
    print("== U10 校准固件（闭环 per-MZI 热/相）· 协议设计 ==")
    print("锚类别（可接受）: %s" % list(ANCHOR_KINDS))
    print("本项目拥有锚: %s  ⇐ 空集（诚实边界）"
          % (list(ANCHORS_AVAILABLE_TO_THIS_PROJECT) or "无"))

    print("\n-- 方法自证 A：解析前向 vs 官方前向 --")
    for N in (2, 3, 4, 6, 8):
        fc = forward_consistency(N)
        print("  N=%d max|ΔU|=%.3e exact=%s" % (N, fc["max_abs_diff"], fc["exact"]))

    print("\n-- 可辨识性（秩定律 + σ 间隙）--")
    for N in (2, 3, 4, 5, 6, 7, 8):
        ip = identifiability_report(N, "power")
        ic = identifiability_report(N, "complex")
        print("  N=%2d 功率 r=%2d/%3d 亏缺=%2d 盲维=%2d σmin=%.4e rel.差=%.2e | "
              "复场 r=%2d/%3d σmin=%.4e"
              % (N, ip["rank"], ip["rank_law"], ip["deficit"], ip["blind_dims"],
                 ip["sigma_min_ratio"],
                 ip["rank"] - MEASURED_RANK_TABLE[N][0],
                 ic["rank"], ic["rank_law"], ic["sigma_min_ratio"]))
    print("  DFT 退化族（功率秩 vs 定律）: %s"
          % {(n, DFT_POWER_RANK[n], power_rank_law(n)) for n in sorted(DFT_POWER_RANK)})

    print("\n-- 🔴 WDM 不提升秩 --")
    sw = wdm_rank_sweep(8)
    for r in sw["sweep"]:
        print("  K=%d span=%6.1f nm ⇒ rank=%d（亏缺 %d）"
              % (r["K"], r["span_nm"], r["rank"], r["deficit"]))
    print("  每 λ 增益 = %d · 秩恒定 = %s" % (sw["rank_gain_per_lambda"], sw["rank_constant"]))

    print("\n-- 状态机（本项目真实现状）--")
    st = project_calibration_state(8, "complex")
    print("  终态 = %s  可宣称 calibrated = %s  阻断 = %s"
          % (st["state"], st["can_claim_calibrated"], st["blocked_by"]))
    for s, why in st["history"]:
        print("    → %-24s %s" % (s, why or ""))

    print("\n-- 自检判据 S1..S7（复场 N=8，无锚）--")
    sc = selfcheck_report(8, "complex")
    for c in sc["checks"]:
        print("  %s %-4s %s | %s" % ("PASS" if c["ok"] else "FAIL", c["id"],
                                     c["detail"], c["desc"][:34]))
    print("  ⇒ %d/%d · verdict=%s" % (sc["n_pass"], sc["n_total"], sc["verdict"]))
    print("  功率 N=8（对照）: %s" % selfcheck_report(8, "power")["verdict"])

    print("\n-- 红线守卫自证 --")
    for name, fn in (("畸形载荷（含 foundry 键）",
                      lambda: guard_no_foundry_process_truth({"foundry_corner": 1})),
                     ("空载荷（合法必过）",
                      lambda: guard_no_foundry_process_truth({})),
                     ("声明键 False（合法必过）",
                      lambda: guard_no_foundry_process_truth({_PDK_TRUTH_FLAG: False})),
                     ("深层声明键 True（必 raise）",
                      lambda: guard_no_foundry_process_truth({"a": {"b": {_PDK_TRUTH_FLAG: True}}})),
                     ("散文值含 foundry（**不**应触发）",
                      lambda: guard_no_foundry_process_truth({"note": "不碰 foundry"}))):
        try:
            fn()
            print("  %-34s ⇒ 通过" % name)
        except CalibrationRedlineError as exc:
            print("  %-34s ⇒ raise %s" % (name, type(exc).__name__))

    print("\n-- 核心门：无锚不得宣称 calibrated --")
    for name, claim in (("claim=calibrated + anchor=None",
                         {"claim": "calibrated", "anchor": None}),
                        ("claim=calibrated + anchor.kind=literature",
                         {"claim": "calibrated",
                          "anchor": {"kind": "literature", "is_attested": True}}),
                        ("claim=protocol_designed（**放行**）",
                         {"claim": "protocol_designed", "anchor": None})):
        try:
            guard_calibration_requires_anchor(claim)
            print("  %-42s ⇒ 通过" % name)
        except CalibrationAnchorError as exc:
            print("  %-42s ⇒ raise：%s" % (name, str(exc)[:70]))

    print("\n-- 接口同形性 --")
    par = protocol_interface_parity(4)
    print("  WDM vs drive=%s  WDM vs U8=%s  三者共有=%s"
          % (par["wdm_vs_drive_ok"], par["wdm_vs_nvm_ok"], par["shared_all_three"]))

    print("\n披露键（%d）: %s" % (len(CAL_DISCLOSURE), sorted(CAL_DISCLOSURE)))
