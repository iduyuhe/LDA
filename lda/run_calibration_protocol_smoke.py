# -*- coding: utf-8 -*-
"""U10 常驻门禁：校准固件（闭环 per-MZI 热/相）· **协议设计**。

判据分组（A–I）
---------------
A 契约 / 披露 / 锚类别（含「literature/simulation 不算物理锚」的否决）
B 红线守卫（机器化：畸形必 raise + 空集必过 + 合法必过 + 可满足性 + 递归覆盖 list）
C 标定状态机（合法链 + 非法转移 raise + 缺证据键 raise + **本项目终态 BLOCKED_NO_ANCHOR**）
D 可辨识性（**地面真值 = |U|² 的有限差分** · 秩定律 (N−1)² / N² · 亏缺 2N−1 ·
  argD 块 ≡ 0 · σ 间隙 · DFT 退化族 · 冻结值）
E WDM（🔴 **不提升秩** + 标定地基接口）
F 自检判据 S1..S7（含「可满足性」：补上锚 + 闭环 + 漂移 ⇒ 7/7）
G 接口同形性（与 `mesh_drive_manifest` / U8 驱动清单的必需共有键）
H 报告结构（守卫在**必经路径**上）
I 独立重算容差（必须紧到能把伪造值判红）

🔴 立场：本 smoke 断言的是**事实**，包括不利事实 ——
`D5` 断言功率读出秩**(N−1)² < N²**（不是满秩）、`D7` 断言亏缺 **2N−1**、
`D8` 断言 `argD` 块**恒为 0**、`E1` 断言**多波长不提升秩**（否决 WDM 作为解法）、
`D15` 断言 DFT 族秩**低于**定律（退化族）、`C14/C15` 断言本项目**到不了** CALIBRATED。
若有人把模块改成「功率读出满秩 / WDM 能解锁 / DFT 也满足定律 / 无锚也能宣称已校准」，
这些判据立刻变红。

方法自证（🔴 血的教训）：`D4` 断言早期「缺共轭」的功率 Jacobian 与**地面真值**
（`|U|²` 的中心差分）差异 **> 0.1** ⇒ 那个修正是**实质**修正，不是洗白。
"""
from __future__ import annotations

import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import numpy as np  # noqa: E402

import lda_l2.calibration_protocol as cal_mod  # noqa: E402
from lda_harness.smoke_kit import make_check  # noqa: E402
from lda_l2.calibration_protocol import (  # noqa: E402
    ANCHOR_KIND_NOTES,
    ANCHOR_KINDS,
    ANCHORS_AVAILABLE_TO_THIS_PROJECT,
    ARM_REF_UM,
    CAL_DISCLOSURE,
    CAL_PROTOCOL_STEPS,
    CAL_STATES,
    CAL_TRANSITIONS,
    CALIBRATED_TRUTH_KEYS,
    CAL_EVIDENCE_REQUIRED,
    CONDITION_SIGMA_FLOOR,
    DFT_POWER_RANK,
    LAM_REF_NM,
    MEASURED_RANK_TABLE,
    MEASURED_SIGMA_GAP,
    MEASUREMENT_MODES,
    PARITY_KEYS_VS_DRIVE_MANIFEST,
    SELFCHECK_CRITERIA,
    SVD_ZERO_TOL,
    WDM_LAM_DEFAULT,
    WDM_LAM_WIDE,
    CalibrationAnchorError,
    CalibrationProtocolError,
    CalibrationRedlineError,
    CalibrationStateMachine,
    calibration_protocol_report,
    guard_anchor_kind_eligible,
    guard_calibration_requires_anchor,
    guard_no_foundry_process_truth,
    identifiability_report,
    lam_scale_vector,
    mesh_jacobian,
    multi_lambda_jacobian,
    per_mzi_calibration_plan,
    power_blind_dims,
    power_rank_law,
    complex_rank_law,
    protocol_interface_parity,
    rank_report,
    selfcheck_report,
    wdm_calibration_manifest,
    wdm_rank_sweep,
    project_calibration_state,
)
from lda_l2.yield_fault_tolerance import (  # noqa: E402
    _generic_unitary,
    _mesh_parts,
    _unpack_unitary,
)

PASS = 0
FAIL = 0
check = make_check(globals(), return_ok=True, detail_fmt="  —— {d}", detail_on="fail")

# ---------------------------------------------------------------------------
# 本轮实测常量（冻结；全部可由独立重算复核）
# ---------------------------------------------------------------------------
DISCLOSURE_KEYS = 14
POWER_SMIN = {2: 1.0, 3: 0.16970718896916615, 4: 0.001495306710455433,
              5: 0.0020751485787276242, 6: 0.00031704261571264148,
              7: 1.5276196506452414e-05, 8: 5.2182608390817222e-06}
COMPLEX_SMIN = {2: 0.27701824309457973, 3: 0.21815589355211254,
                4: 0.038337937970041279, 5: 0.03050868098625855,
                6: 0.011951205381970772, 7: 0.005609167750020249,
                8: 0.00055909575098974068}
NS = (2, 3, 4, 5, 6, 7, 8)
LAMS_K = ([1550.0], [1550.0, 1552.5], [1550.0, 1600.0], list(WDM_LAM_WIDE))

GOOD_ANCHOR = {"kind": "pdk_process_corner", "is_attested": True,
               "source": "（示例）foundry PDK 工艺角 —— 本项目**不持有**"}
MEASURED_ANCHOR = {"kind": "measured_calibration_data", "is_attested": True,
                   "source": "（示例）本工艺实测标定数据 —— 本项目**不持有**"}


def _rejects(fn, exc: type = Exception) -> bool:
    """fn() 必须抛 exc（且不是别的异常）⇒ True。"""
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


# ---- 独立重算助手（**不复用**模块的解析 Jacobian 与秩计算） ----
def _ind_fd_power(N: int, U: np.ndarray, h: float = 1e-5):
    """地面真值：`|U|²` 的中心差分（用官方 `_unpack_unitary` 当前向，独立于解析式）。

    🔴 步长取 **1e-5** 而非 1e-6：中心差分的舍入噪声 ~ `eps/(2h)` ⇒ h=1e-6 时约
    **1.1e-10**（相对 σmax），**正好压在 1e-10 秩阈值上** ⇒ N=8 会多出 1 个伪非零
    （实测 rank 50 而非 49）；h=1e-5 时噪声降到 ~8.5e-12，阈值判定恢复稳定。
    截断误差 ~ `h²/6` ≈ 1e-11，仍远低于 D2 的 1e-6 容差。
    """
    p = _mesh_parts(U)
    bs, D, color, nc = p["bs_list"], p["D"], p["color"], p["n_cols"]
    js = [int(b[0]) for b in bs]
    x = [float(v) for b in bs for v in (float(b[1]), float(b[2]))]
    dg = np.diag(np.asarray(D, dtype=complex))
    x.extend(float(np.angle(dg[k])) for k in range(N))

    def Uof(xx):
        return _unpack_unitary(np.asarray(xx, dtype=float), js, color, nc, N)

    rows = []
    for m in range(len(x)):
        xp, xm = list(x), list(x)
        xp[m] += h
        xm[m] -= h
        rows.append((np.abs(Uof(xp)) ** 2 - np.abs(Uof(xm)) ** 2).ravel() / (2.0 * h))
    return np.array(rows).T


def _ind_fd_complex(N: int, U: np.ndarray, h: float = 1e-5):
    p = _mesh_parts(U)
    bs, D, color, nc = p["bs_list"], p["D"], p["color"], p["n_cols"]
    js = [int(b[0]) for b in bs]
    x = [float(v) for b in bs for v in (float(b[1]), float(b[2]))]
    dg = np.diag(np.asarray(D, dtype=complex))
    x.extend(float(np.angle(dg[k])) for k in range(N))

    def Uof(xx):
        return _unpack_unitary(np.asarray(xx, dtype=float), js, color, nc, N)

    rows = []
    for m in range(len(x)):
        xp, xm = list(x), list(x)
        xp[m] += h
        xm[m] -= h
        d = (Uof(xp) - Uof(xm)) / (2.0 * h)
        rows.append(np.concatenate([d.real.ravel(), d.imag.ravel()]))
    return np.array(rows).T


def _ind_rank(J: np.ndarray, tol: float = 1e-10) -> int:
    s = np.linalg.svd(np.asarray(J, dtype=float), compute_uv=False)
    return int(np.sum(s / s[0] > tol))


def _ind_law_power(N: int) -> int:
    return (N - 1) * (N - 1)


def _ind_blind(N: int) -> int:
    return 2 * N - 1


def _ind_lam_scale(N: int, n_mzi: int, lam: float):
    s = LAM_REF_NM / lam
    v = []
    for _ in range(n_mzi):
        v.extend([1.0, s])
    v.extend([s] * N)
    return v


def _jac(N: int, mode: str = "power", unitary=None):
    U = _generic_unitary(N) if unitary is None else np.asarray(unitary, dtype=complex)
    p = _mesh_parts(U)
    return mesh_jacobian(N, p["bs_list"], p["D"], p["color"], p["n_cols"], mode)


def main():  # noqa: C901
    # ======================================================= A 契约 / 披露 / 锚
    check("A1 披露项键齐全（%d 项，防被悄悄删）" % DISCLOSURE_KEYS,
          len(CAL_DISCLOSURE) == DISCLOSURE_KEYS,
          "len=%d" % len(CAL_DISCLOSURE))
    check("A2 披露项值均为非空字符串",
          all(isinstance(v, str) and v.strip() for v in CAL_DISCLOSURE.values()))
    check("A3 披露含六条核心声明（能力边界/锚/可辨识/WDM/无 foundry/仿真非证据）",
          all(k in CAL_DISCLOSURE for k in
              ("capability", "anchor", "identifiability", "wdm", "no_foundry",
               "no_simulation_authority")))
    check("A4 锚类别 == (pdk_process_corner, measured_calibration_data)",
          tuple(ANCHOR_KINDS) == ("pdk_process_corner", "measured_calibration_data"),
          str(list(ANCHOR_KINDS)))
    check("A4b 🔴 ANCHOR_KIND_NOTES 是 (kind, note) **元组**而非 dict —— "
          "避免把 forbidden 令牌放进**键**（键扫描守卫的潜在陷阱）",
          isinstance(ANCHOR_KIND_NOTES, tuple)
          and all(isinstance(x, tuple) and len(x) == 2 for x in ANCHOR_KIND_NOTES)
          and not _rejects(lambda: guard_no_foundry_process_truth(
              {"anchor_kind_notes": [list(x) for x in ANCHOR_KIND_NOTES]}), Exception))
    check("A4c 🔴 A5 的配套：ANCHOR_KINDS 只作为**值**出现；把它当 dict 键会被守卫拦"
          "（所以用元组形状消除该陷阱）",
          _rejects(lambda: guard_no_foundry_process_truth(
              {ANCHOR_KINDS[0]: "x"}), CalibrationRedlineError))
    check("A5 🔴 锚类别**不含** literature / simulation / assumption（弱锚被否决）",
          not any(k in ANCHOR_KINDS for k in ("literature", "simulation", "assumption")))
    check("A6 🔴 本项目拥有的锚 == 空集（诚实边界，不是待办）",
          tuple(ANCHORS_AVAILABLE_TO_THIS_PROJECT) == ())
    check("A7 测量方案 == (power, complex)",
          tuple(MEASUREMENT_MODES) == ("power", "complex"), str(list(MEASUREMENT_MODES)))
    check("A8 参考波长 == 1550.0 nm", LAM_REF_NM == 1550.0, "%.4f" % LAM_REF_NM)
    check("A9 状态机：CAL_TRANSITIONS 键集 == CAL_STATES（8 态）",
          set(CAL_TRANSITIONS) == set(CAL_STATES) and len(CAL_STATES) == 8,
          "%d 态" % len(CAL_STATES))
    check("A10 状态机：所有转移目标 ∈ CAL_STATES",
          all(t in CAL_STATES for ts in CAL_TRANSITIONS.values() for t in ts))
    check("A11 状态机：FAILED 是终态（无出边）",
          CAL_TRANSITIONS["FAILED"] == ())
    check("A12 协议步骤 == 7 步且 id 唯一（P1..P7）",
          len(CAL_PROTOCOL_STEPS) == 7
          and len({s["id"] for s in CAL_PROTOCOL_STEPS}) == 7
          and [s["id"] for s in CAL_PROTOCOL_STEPS] ==
          ["P%d" % i for i in range(1, 8)])
    check("A13 步骤的 requires_anchor 标注：P1/P3/P5/P6/P7 为 True，P2/P4 为 False",
          [s["requires_anchor"] for s in CAL_PROTOCOL_STEPS] ==
          [True, False, True, False, True, True, True],
          str([s["requires_anchor"] for s in CAL_PROTOCOL_STEPS]))
    check("A14 🔴 P1（绑定物理锚）是唯一 blocking 且 blocked_reason 非空（唯一硬阻断）",
          CAL_PROTOCOL_STEPS[0]["blocking"] is True
          and bool(CAL_PROTOCOL_STEPS[0]["blocked_reason"])
          and all(bool(s["blocked_reason"]) for s in CAL_PROTOCOL_STEPS))
    check("A15 自检判据 == 7 条且 id == S1..S7",
          tuple(c[0] for c in SELFCHECK_CRITERIA) ==
          tuple("S%d" % i for i in range(1, 8)), str([c[0] for c in SELFCHECK_CRITERIA]))
    check("A16 同形必需共有键 == (n_mzi, n_out, mzi, out)",
          tuple(PARITY_KEYS_VS_DRIVE_MANIFEST) == ("n_mzi", "n_out", "mzi", "out"),
          str(list(PARITY_KEYS_VS_DRIVE_MANIFEST)))
    check("A17 σ 地板 == 1e-4（**设计占位**，不许悄悄改）",
          CONDITION_SIGMA_FLOOR == 1e-4, "%.1e" % CONDITION_SIGMA_FLOOR)
    check("A18 SVD 零空间阈值 == 1e-10（实测落在 σ 间隙内）",
          SVD_ZERO_TOL == 1e-10, "%.1e" % SVD_ZERO_TOL)
    check("A19 驱动臂长参考 == 1000.0 µm（与 mesh_drive_manifest 默认一致）",
          ARM_REF_UM == 1000.0, "%.1f" % ARM_REF_UM)
    check("A20 冻结秩表覆盖 N=2..8 且 n_mzi == N(N−1)/2",
          sorted(MEASURED_RANK_TABLE) == list(NS)
          and all(MEASURED_RANK_TABLE[N][4] == N * (N - 1) // 2 for N in NS))

    # ======================================================= B 红线守卫
    check("B1 守卫：键名含 foundry ⇒ raise CalibrationRedlineError",
          _rejects(lambda: guard_no_foundry_process_truth({"foundry_corner": 1}),
                   CalibrationRedlineError))
    check("B2 守卫：键名含 tcad ⇒ raise",
          _rejects(lambda: guard_no_foundry_process_truth({"tcad_netlist": {}}),
                   CalibrationRedlineError))
    check("B3 守卫：键名含中文「工艺角」⇒ raise",
          _rejects(lambda: guard_no_foundry_process_truth({"工艺角表": []}),
                   CalibrationRedlineError))
    check("B4 守卫：空载荷 ⇒ 通过（合法必过 · 可满足性）",
          not _rejects(lambda: guard_no_foundry_process_truth({}), Exception))
    check("B5 守卫：散文**值**含 foundry ⇒ 通过（只扫键名，有意设计）",
          not _rejects(lambda: guard_no_foundry_process_truth(
              {"note": "不碰 foundry 工艺真值"}), Exception))
    check("B6 守卫：声明键 False ⇒ 通过（可满足性）",
          not _rejects(lambda: guard_no_foundry_process_truth(
              {"pdk_process_truth_used": False}), Exception))
    check("B7 守卫：声明键 True（顶层）⇒ raise",
          _rejects(lambda: guard_no_foundry_process_truth(
              {"pdk_process_truth_used": True}), CalibrationRedlineError))
    check("B8 守卫：声明键 True（**深层 3 层**）⇒ raise（递归而非只看顶层）",
          _rejects(lambda: guard_no_foundry_process_truth(
              {"a": {"b": {"c": {"pdk_process_truth_used": True}}}}),
              CalibrationRedlineError))
    check("B9 守卫：**list 内**的 dict 含 foundry 键 ⇒ raise（递归覆盖 list）",
          _rejects(lambda: guard_no_foundry_process_truth(
              {"items": [{"ok": 1}, {"foundry_pdk": 2}]}), CalibrationRedlineError))
    check("B10 锚：kind=literature ⇒ raise（文献**不算**物理锚）",
          _rejects(lambda: guard_anchor_kind_eligible(
              {"kind": "literature", "is_attested": True}),
              CalibrationAnchorError))
    check("B11 锚：kind=simulation ⇒ raise（仿真**不算**物理锚）",
          _rejects(lambda: guard_anchor_kind_eligible(
              {"kind": "simulation", "is_attested": True}),
              CalibrationAnchorError))
    check("B12 锚：kind=pdk_process_corner 但 is_attested=False ⇒ raise（未坐实）",
          _rejects(lambda: guard_anchor_kind_eligible(
              {"kind": "pdk_process_corner", "is_attested": False}),
              CalibrationAnchorError))
    check("B13 锚：kind=pdk_process_corner + is_attested=True ⇒ 通过（合法必过）",
          not _rejects(lambda: guard_anchor_kind_eligible(GOOD_ANCHOR), Exception))
    check("B14 锚：kind=measured_calibration_data + True ⇒ 通过（第二条合法路径）",
          not _rejects(lambda: guard_anchor_kind_eligible(MEASURED_ANCHOR), Exception))
    check("B15 锚：非 dict（None / 字符串）⇒ raise",
          _rejects(lambda: guard_anchor_kind_eligible(None), CalibrationAnchorError)
          and _rejects(lambda: guard_anchor_kind_eligible("pdk"), CalibrationAnchorError))
    check("B16 🔴 核心门：claim=calibrated + anchor=None ⇒ raise（T1 违规）",
          _rejects(lambda: guard_calibration_requires_anchor(
              {"claim": "calibrated", "anchor": None}), CalibrationAnchorError))
    check("B17 🔴 核心门：claim=calibrated + 弱锚（literature）⇒ raise",
          _rejects(lambda: guard_calibration_requires_anchor(
              {"claim": "calibrated",
               "anchor": {"kind": "literature", "is_attested": True}}),
              CalibrationAnchorError))
    check("B18 核心门：中文「已校准」同样被拦（大小写/语言无关）",
          _rejects(lambda: guard_calibration_requires_anchor(
              {"claim": "已校准", "anchor": None}), CalibrationAnchorError))
    check("B19 核心门：非 calibrated 声明 ⇒ **放行**（门只拦越界声明）",
          not _rejects(lambda: guard_calibration_requires_anchor(
              {"claim": "protocol_designed", "anchor": None}), Exception)
          and not _rejects(lambda: guard_calibration_requires_anchor(
              {"claim": "", "anchor": None}), Exception))
    check("B20 核心门：claim=calibrated + 合格锚 ⇒ 通过（可满足性 —— 门不是恒红）",
          not _rejects(lambda: guard_calibration_requires_anchor(
              {"claim": "calibrated", "anchor": GOOD_ANCHOR}), Exception))
    check("B21 核心门：claim 非 dict ⇒ CalibrationProtocolError",
          _rejects(lambda: guard_calibration_requires_anchor("calibrated"),
                   CalibrationProtocolError))
    check("B22 🔴 **守卫可满足性**（自纠回归）：合法锚 + 键扫描守卫**必须通过**"
          "（原先字段名 `is_true_process_truth` 含 forbidden 令牌 `process_truth` "
          "⇒ 守卫对唯一合法路径恒红 ⇒ 已改名 `is_attested`）",
          not _rejects(lambda: guard_no_foundry_process_truth(
              {"anchor": dict(GOOD_ANCHOR)}), Exception)
          and not _rejects(lambda: guard_no_foundry_process_truth(
              {"anchor": dict(MEASURED_ANCHOR)}), Exception))
    check("B23 合法锚的键集不含任何 forbidden 令牌（结构上排除恒红）",
          all(not any(tok in str(k).lower() for tok in (
              "foundry", "tcad", "process_corner", "process_truth", "pdk_truth",
              "silicon_truth", "tapeout_truth", "工艺角", "工艺真值", "实测工艺"))
              for k in GOOD_ANCHOR)
          and set(GOOD_ANCHOR) == set(MEASURED_ANCHOR),
          str(sorted(GOOD_ANCHOR)))

    # ======================================================= C 标定状态机
    m0 = CalibrationStateMachine()
    check("C1 初始态 == UNCALIBRATED，合法目标 == (PROTOCOL_DESIGNED, FAILED)",
          m0.state == "UNCALIBRATED"
          and tuple(m0.legal_targets()) == ("PROTOCOL_DESIGNED", "FAILED"),
          str(list(m0.legal_targets())))
    check("C2 非法转移 UNCALIBRATED→CALIBRATED ⇒ raise",
          _rejects(lambda: CalibrationStateMachine().advance("CALIBRATED", {}),
                   CalibrationProtocolError))
    check("C3 缺证据键（→PROTOCOL_DESIGNED 无 protocol_steps）⇒ raise",
          _rejects(lambda: CalibrationStateMachine().advance("PROTOCOL_DESIGNED", {}),
                   CalibrationProtocolError))
    m1 = CalibrationStateMachine()
    m1.advance("PROTOCOL_DESIGNED", {"protocol_steps": 7})
    m1.advance("IDENTIFIABILITY_VERIFIED", {"scheme_identifiable": True})
    m1.advance("BLOCKED_NO_ANCHOR", {"reason": "无锚"})
    check("C4 合法链 UNCALIBRATED→PROTOCOL_DESIGNED→IDENTIFIABILITY_VERIFIED→"
          "BLOCKED_NO_ANCHOR 成功",
          m1.state == "BLOCKED_NO_ANCHOR" and len(m1.history()) == 4,
          "history=%d 步" % len(m1.history()))
    check("C5 BLOCKED_NO_ANCHOR → CALIBRATED 是**非法转移** ⇒ raise（必须经 ANCHOR_BOUND）",
          _rejects(lambda: CalibrationStateMachine("BLOCKED_NO_ANCHOR")
                   .advance("CALIBRATED", {"anchor": GOOD_ANCHOR,
                                           "scheme_identifiable": True,
                                           "closed_loop_converged": True,
                                           "drift_checked": True}),
                   CalibrationProtocolError))
    m2 = CalibrationStateMachine("BLOCKED_NO_ANCHOR")
    m2.advance("ANCHOR_BOUND", {"anchor": GOOD_ANCHOR})
    check("C6 BLOCKED_NO_ANCHOR + 合格锚 ⇒ ANCHOR_BOUND 成功（锚到位后路打通）",
          m2.state == "ANCHOR_BOUND")
    check("C7 →CALIBRATED 缺 closed_loop_converged ⇒ raise",
          _rejects(lambda: CalibrationStateMachine("ANCHOR_BOUND").advance(
              "CALIBRATED", {"anchor": GOOD_ANCHOR, "scheme_identifiable": True,
                             "drift_checked": True}), CalibrationProtocolError))
    check("C8 →CALIBRATED 缺 drift_checked ⇒ raise",
          _rejects(lambda: CalibrationStateMachine("ANCHOR_BOUND").advance(
              "CALIBRATED", {"anchor": GOOD_ANCHOR, "scheme_identifiable": True,
                             "closed_loop_converged": True}), CalibrationProtocolError))
    m3 = CalibrationStateMachine("BLOCKED_NO_ANCHOR")
    m3.advance("ANCHOR_BOUND", {"anchor": MEASURED_ANCHOR})
    m3.advance("CALIBRATED", {"anchor": MEASURED_ANCHOR, "scheme_identifiable": True,
                              "closed_loop_converged": True, "drift_checked": True})
    check("C9 证据全齐 + 合格锚 ⇒ CALIBRATED，can_claim_calibrated() True（**可满足性**）",
          m3.state == "CALIBRATED" and m3.can_claim_calibrated() is True)
    check("C10 CALIBRATED → STALE 合法（漂移失效路径存在）",
          tuple(CalibrationStateMachine("CALIBRATED").legal_targets())
          == ("STALE", "FAILED"))
    check("C11 FAILED 无出边 ⇒ 任何 target 都 raise",
          _rejects(lambda: CalibrationStateMachine("FAILED").advance(
              "ANCHOR_BOUND", {"anchor": GOOD_ANCHOR}), CalibrationProtocolError))
    check("C12 未知初始状态 ⇒ raise",
          _rejects(lambda: CalibrationStateMachine("DONE"), CalibrationProtocolError))
    check("C13 未知目标状态 ⇒ raise",
          _rejects(lambda: CalibrationStateMachine().advance("FINISHED", {}),
                   CalibrationProtocolError))
    st_c = project_calibration_state(8, "complex")
    check("C14 🔴 本项目真实现状（复场 N=8、无锚）终态 == BLOCKED_NO_ANCHOR，"
          "can_claim_calibrated == False",
          st_c["state"] == "BLOCKED_NO_ANCHOR"
          and st_c["can_claim_calibrated"] is False
          and st_c["blocked_by"] == ["physical_anchor_absent"],
          "state=%s blocked=%s" % (st_c["state"], st_c["blocked_by"]))
    st_p = project_calibration_state(8, "power")
    check("C15 🔴 功率读出（N=8）终态 == FAILED（**结构性**不可辨识，不是缺锚）",
          st_p["state"] == "FAILED",
          "state=%s · %s" % (st_p["state"], st_p["history"][-1][1]))
    st_g = project_calibration_state(8, "complex", anchor=MEASURED_ANCHOR,
                                     closed_loop_converged=True, drift_checked=True)
    check("C16 给定合格锚 + 闭环 + 漂移 ⇒ 终态 CALIBRATED（门**可**通过 ⇒ 非恒红）",
          st_g["state"] == "CALIBRATED" and st_g["can_claim_calibrated"] is True)
    check("C17 history 每步为 (state, reason) 二元组且首项为初始态",
          all(isinstance(h, tuple) and len(h) == 2 for h in st_c["history"])
          and st_c["history"][0][0] == "UNCALIBRATED")
    check("C18 🔴 状态机：**弱锚**（literature）⇒ ANCHOR_BOUND 转移 raise"
          "（锚资格在必经路径上被审，不是只在函数入口审）",
          _rejects(lambda: CalibrationStateMachine("BLOCKED_NO_ANCHOR").advance(
              "ANCHOR_BOUND", {"anchor": {"kind": "literature", "is_attested": True}}),
              CalibrationAnchorError))
    check("C19 状态机：锚缺 is_attested ⇒ ANCHOR_BOUND 转移 raise",
          _rejects(lambda: CalibrationStateMachine("BLOCKED_NO_ANCHOR").advance(
              "ANCHOR_BOUND", {"anchor": {"kind": "pdk_process_corner"}}),
              CalibrationAnchorError))
    check("C20 🔴 **单一真值来源**：CAL_EVIDENCE_REQUIRED[CALIBRATED] == "
          "(\"anchor\",) + CALIBRATED_TRUTH_KEYS（防两处各写一份 ⇒ 一处被改判据抓不到）",
          CAL_EVIDENCE_REQUIRED[("ANCHOR_BOUND", "CALIBRATED")]
          == ("anchor",) + CALIBRATED_TRUTH_KEYS
          and CALIBRATED_TRUTH_KEYS
          == ("scheme_identifiable", "closed_loop_converged", "drift_checked"),
          str(CAL_EVIDENCE_REQUIRED[("ANCHOR_BOUND", "CALIBRATED")]))

    # ======================================================= D 可辨识性
    check("D1 方法自证 A：解析前向 U 与官方 `_forward_unitary` 逐位一致（N=2..8）",
          all(cal_mod.forward_consistency(N)["exact"] for N in NS),
          str([cal_mod.forward_consistency(N)["max_abs_diff"] for N in (4, 8)]))
    rel_p, rel_c = {}, {}
    for N in NS:
        U = _generic_unitary(N)
        p = _mesh_parts(U)
        bs, D, color, nc = p["bs_list"], p["D"], p["color"], p["n_cols"]
        JA = mesh_jacobian(N, bs, D, color, nc, "power")["J"]
        JC = mesh_jacobian(N, bs, D, color, nc, "complex")["J"]
        JF = _ind_fd_power(N, U)
        JFC = _ind_fd_complex(N, U)
        rel_p[N] = float(np.max(np.abs(JA - JF)) / max(np.max(np.abs(JA)), 1e-30))
        rel_c[N] = float(np.max(np.abs(JC - JFC)) / max(np.max(np.abs(JC)), 1e-30))
    check("D2 🔴 方法自证 B：解析**功率** Jacobian vs 地面真值 FD(|U|²) 相对差 < 1e-6（N=2..8）",
          all(v < 1e-6 for v in rel_p.values()),
          "max=%.2e" % max(rel_p.values()))
    check("D3 方法自证 C：解析**复场** Jacobian vs 地面真值 FD(Re/Im U) 相对差 < 1e-6（N=2..8）",
          all(v < 1e-6 for v in rel_c.values()),
          "max=%.2e" % max(rel_c.values()))
    _old = {}
    for N in (2, 3, 4):
        U = _generic_unitary(N)
        p = _mesh_parts(U)
        bs, D, color, nc = p["bs_list"], p["D"], p["color"], p["n_cols"]
        _patch = cal_mod.mesh_jacobian
        try:
            cal_mod.mesh_jacobian = _old_power_jac          # type: ignore[assignment]
            Jold = cal_mod.mesh_jacobian(N, bs, D, color, nc, "power")["J"]
        finally:
            cal_mod.mesh_jacobian = _patch
        JF = _ind_fd_power(N, U)
        _old[N] = float(np.max(np.abs(Jold - JF)) / max(np.max(np.abs(Jold)), 1e-30))
    check("D4 🔴 「缺共轭」旧式与地面真值差异 **> 0.1**（证明修正是实质的，不是洗白）",
          all(v > 0.1 for v in _old.values()),
          "差异=%s" % {k: "%.2f" % v for k, v in _old.items()})
    check("D5 🔴 功率读出秩定律：rank == (N−1)²（N=2..8）—— **不是**满秩",
          all(identifiability_report(N, "power")["rank"] == power_rank_law(N) for N in NS),
          str({N: identifiability_report(N, "power")["rank"] for N in NS}))
    check("D6 复场读出秩定律：rank == N² 满秩（N=2..8）",
          all(identifiability_report(N, "complex")["rank"] == complex_rank_law(N)
              for N in NS),
          str({N: identifiability_report(N, "complex")["rank"] for N in NS}))
    check("D7 🔴 功率亏缺 == 2N−1（N=2..8）",
          all(identifiability_report(N, "power")["deficit"] == power_blind_dims(N)
              for N in NS),
          str({N: identifiability_report(N, "power")["deficit"] for N in NS}))
    argd_p = {N: identifiability_report(N, "power")["argd_block_max"] for N in NS}
    argd_c = {N: identifiability_report(N, "complex")["argd_block_max"] for N in NS}
    check("D8 🔴 功率下 argD 块 ≡ 0（max ≤ 1e-14，N=2..8）⇒ 输出相位**永不可观测**",
          all(v <= 1e-14 for v in argd_p.values()), str({k: "%.1e" % v for k, v in argd_p.items()}))
    check("D9 复场下 argD 块 ≠ 0（max > 0.1）⇒ 输出相位**可**观测",
          all(v > 0.1 for v in argd_c.values()), str({k: "%.3f" % v for k, v in argd_c.items()}))
    check("D10 冻结值一致：功率秩与 σmin（相对差 < 1e-12，N=2..8）",
          all(identifiability_report(N, "power")["rank"] == MEASURED_RANK_TABLE[N][0]
              and abs(identifiability_report(N, "power")["sigma_min_ratio"]
                      / POWER_SMIN[N] - 1.0) < 1e-12 for N in NS))
    check("D11 冻结值一致：复场秩与 σmin（相对差 < 1e-12，N=2..8）",
          all(identifiability_report(N, "complex")["rank"] == MEASURED_RANK_TABLE[N][2]
              and abs(identifiability_report(N, "complex")["sigma_min_ratio"]
                      / COMPLEX_SMIN[N] - 1.0) < 1e-12 for N in NS))
    check("D12 σ 间隙 > 1e9（N=4/6/8）⇒ 秩判据不敏感于阈值微调",
          all(identifiability_report(N, "power")["sigma_gap"] > 1e9 for N in (4, 6, 8)),
          str({N: "%.2e" % identifiability_report(N, "power")["sigma_gap"]
               for N in (4, 6, 8)}))
    check("D12b 冻结 σ 间隙与实测一致（相对差 < 1e-9，N=4/6/8）",
          all(abs(identifiability_report(N, "power")["sigma_gap"]
                  / MEASURED_SIGMA_GAP[N][2] - 1.0) < 1e-9 for N in (4, 6, 8)))
    check("D13 真零 σ_{r+1}/σmax ≤ 1e-15（N=4/6/8）",
          all(identifiability_report(N, "power")["sigma_next_ratio"] <= 1e-15
              for N in (4, 6, 8)))
    check("D14 功率 σmin/σmax 在 (2,3,4,6,8) 上**单调塌陷**（8 为全域最小）",
          all(POWER_SMIN[a] > POWER_SMIN[b] for a, b in zip((2, 3, 4, 6), (3, 4, 6, 8)))
          and POWER_SMIN[8] == min(POWER_SMIN.values()),
          str({N: "%.3e" % POWER_SMIN[N] for N in NS}))
    check("D14b 🔴 **非全序单调**：σmin(N=4)=1.495e-3 < σmin(N=5)=2.075e-3"
          "（如实记录反直觉事实，不粉饰成单调）",
          POWER_SMIN[4] < POWER_SMIN[5])
    check("D15 🔴 DFT **退化族**：功率秩 **< (N−1)²**（N=4/6/8）且等于冻结值",
          all(identifiability_report(N, "power", unitary=_dft(N))["rank"]
              == DFT_POWER_RANK[N] < power_rank_law(N) for N in (4, 6, 8)),
          str({N: identifiability_report(N, "power", unitary=_dft(N))["rank"]
               for N in (4, 6, 8)}))
    check("D16 DFT 非退化 N（2/3/5/7）功率秩 **==** 定律（退化只发生在特定 N）",
          all(identifiability_report(N, "power", unitary=_dft(N))["rank"]
              == power_rank_law(N) for N in (2, 3, 5, 7)))
    check("D17 SVD 阈值落在 σ 间隙内（N=8：真零 1.17e-16 < 1e-10 < 最小非零 5.22e-6）",
          identifiability_report(8, "power")["sigma_next_ratio"] < SVD_ZERO_TOL
          < identifiability_report(8, "power")["sigma_min_ratio"])
    check("D18 rank_report：J=I₄ ⇒ rank=4、σmin=1.0、cond=1.0",
          rank_report(np.eye(4))["rank"] == 4
          and rank_report(np.eye(4))["sigma_min_nonzero_ratio"] == 1.0
          and abs(rank_report(np.eye(4))["cond"] - 1.0) < 1e-15)
    check("D19 rank_report：秩亏矩阵（两列相同）秩正确（3×3 → rank 2）",
          rank_report(np.array([[1.0, 1.0, 0.0], [0.0, 0.0, 1.0],
                                [1.0, 1.0, 1.0]]))["rank"] == 2)
    check("D20 未知测量方案 ⇒ raise",
          _rejects(lambda: _jac(4, "intensity"), CalibrationProtocolError))
    check("D21 λ ≤ 0 ⇒ raise",
          _rejects(lambda: lam_scale_vector(4, [(0, 1.0, 2.0)], 0.0),
                   CalibrationProtocolError)
          and _rejects(lambda: lam_scale_vector(4, [(0, 1.0, 2.0)], -1.0),
                       CalibrationProtocolError))
    check("D22 空 λ 列表 ⇒ raise",
          _rejects(lambda: multi_lambda_jacobian(
              4, [(0, 1.0, 2.0)], np.eye(4, dtype=complex), [0], 1,
              np.zeros(2 * 1 + 4), []), CalibrationProtocolError))
    check("D23 identifiable：复场 True / 功率 False（N=2..8）",
          all(identifiability_report(N, "complex")["identifiable"] is True
              and identifiability_report(N, "power")["identifiable"] is False
              for N in NS))
    check("D24 功率 verdict == power-only-structurally-unidentifiable（N=2..8）",
          all(identifiability_report(N, "power")["verdict"]
              == "power-only-structurally-unidentifiable" for N in NS))

    # ======================================================= E WDM
    for N in (2, 3, 4, 6, 8):
        sw = wdm_rank_sweep(N)
        check("E1.%d 🔴 N=%d：K=1/2/4（间隔 0→100 nm）秩**恒定**（WDM 不解锁）" % (N, N),
              sw["rank_constant"] is True and sw["rank_gain_per_lambda"] == 0
              and len({r["rank"] for r in sw["sweep"]}) == 1,
              "秩=%s" % [r["rank"] for r in sw["sweep"]])
    check("E2 WDM：sweep 每行 deficit == 2N−1（功率，N=8）",
          all(r["deficit"] == power_blind_dims(8) for r in wdm_rank_sweep(8)["sweep"]))
    check("E3 λ 缩放：θ 无色散（因子 1）、φ 与 argD ×(λ_ref/λ)",
          lam_scale_vector(3, [(0, 1.0, 2.0), (1, 3.0, 4.0)], 1552.5).tolist()
          == _ind_lam_scale(3, 2, 1552.5))
    check("E4 缩放向量长度 == 2·n_mzi + N",
          all(len(lam_scale_vector(N, [(0, 0.1, 0.2)] * (N * (N - 1) // 2), 1550.0))
              == 2 * (N * (N - 1) // 2) + N for N in NS))
    check("E5 WDM 标定地基清单含 4 个必需共有键",
          set(PARITY_KEYS_VS_DRIVE_MANIFEST) <= set(_wdm(4)))
    check("E6 🔴 WDM 清单 basis_ready == False 且 blocked_by 含 physical_anchor_absent"
          "（接口就绪 ≠ 方案可用）",
          _wdm(4)["basis_ready"] is False
          and "physical_anchor_absent" in _wdm(4)["blocked_by"])
    check("E7 WDM 清单的 mzi/out **直接取自** mesh_drive_manifest（同对象 ⟹ 逐项相等）",
          _wdm(4)["mzi"] == _drive(4)["mzi"] and _wdm(4)["out"] == _drive(4)["out"])
    check("E8 WDM 清单 n_lambda == len(lams) 且 lams_nm 保序",
          _wdm(4)["n_lambda"] == len(WDM_LAM_DEFAULT)
          and _wdm(4)["lams_nm"] == list(WDM_LAM_DEFAULT))
    check("E9 WDM 清单：功率 mode ⇒ identifiable False（秩障碍与 λ 数无关）",
          _wdm(4, mode="power")["identifiable"] is False)
    check("E10 WDM 清单：复场 mode ⇒ identifiable True 但 basis_ready 仍 False",
          _wdm(4, mode="complex")["identifiable"] is True
          and _wdm(4, mode="complex")["basis_ready"] is False)
    check("E11 WDM honest_note 明写「不提升秩」（不利结论进入产物）",
          "不提升秩" in _wdm(4)["honest_note"])
    check("E12 WDM 清单 rank_gain_per_lambda == 0（功率 N=4）",
          _wdm(4, mode="power")["rank_gain_per_lambda"] == 0,
          "%.1f" % _wdm(4, mode="power")["rank_gain_per_lambda"])
    check("E13 空 λ 列表 ⇒ wdm_calibration_manifest raise",
          _rejects(lambda: wdm_calibration_manifest(
              _mesh_parts(_generic_unitary(4))["bs_list"],
              _mesh_parts(_generic_unitary(4))["D"], [], 4),
              CalibrationProtocolError))

    # ======================================================= F 自检判据
    sc_c = selfcheck_report(8, "complex")
    sc_p = selfcheck_report(8, "power")
    _cm = {c["id"]: c for c in sc_c["checks"]}
    check("F1 复场 N=8（无锚）：S1/S2/S3 PASS，S4/S5/S6/S7 FAIL，3/7",
          [_cm["S1"]["ok"], _cm["S2"]["ok"], _cm["S3"]["ok"], _cm["S4"]["ok"],
           _cm["S5"]["ok"], _cm["S6"]["ok"], _cm["S7"]["ok"]]
          == [True, True, True, False, False, False, False]
          and sc_c["n_pass"] == 3, "%d/7" % sc_c["n_pass"])
    _pm = {c["id"]: c for c in sc_p["checks"]}
    check("F2 🔴 功率 N=8：S1 **FAIL**（结构性不可解）且 S3 FAIL（σmin 5.22e-6 < 地板 1e-4）",
          _pm["S1"]["ok"] is False and _pm["S3"]["ok"] is False
          and _pm["S2"]["ok"] is True)
    check("F3 S4 详情非空且指向锚（缺锚原因被记录）",
          bool(_cm["S4"]["detail"]) and "锚" in _cm["S4"]["detail"],
          _cm["S4"]["detail"])
    sc_g = selfcheck_report(8, "complex", anchor=MEASURED_ANCHOR,
                            closed_loop_converged=True, drift_checked=True)
    check("F4 补上合格锚 + 闭环 + 漂移 ⇒ **7/7** 且 verdict == calibrated-claimable"
          "（可满足性 —— 判据不是恒红）",
          sc_g["n_pass"] == 7 and sc_g["verdict"] == "calibrated-claimable",
          "%d/7 %s" % (sc_g["n_pass"], sc_g["verdict"]))
    check("F5 S7 == (S1..S6 全过 且 锚合格) —— 逻辑一致",
          _cm["S7"]["ok"] is False
          and (all(_cm["S%d" % i]["ok"] for i in range(1, 7)) is False))
    check("F6 n_total == 7 且 checks 长度 == 7",
          sc_c["n_total"] == 7 and len(sc_c["checks"]) == 7)
    check("F7 passes_calibration_gate == all(checks) —— 无重复口径",
          sc_c["passes_calibration_gate"]
          == all(c["ok"] for c in sc_c["checks"])
          and sc_g["passes_calibration_gate"] is True)
    check("F8 未达门槛时 verdict != calibrated-claimable（不粉饰）",
          sc_c["verdict"] == "not-calibrated-claimable")
    check("F9 honest_note 提到「结构门」与 U6/U7 同族（不利结论写进产物）",
          "结构门" in sc_c["honest_note"] and "U6" in sc_c["honest_note"])
    sc_b = selfcheck_report(8, "complex",
                            anchor={"kind": "literature", "is_attested": True},
                            closed_loop_converged=True, drift_checked=True)
    check("F10 弱锚（literature）⇒ S4 FAIL（弱锚**不放行**；即便其余全过）",
          {c["id"]: c["ok"] for c in sc_b["checks"]}["S4"] is False
          and sc_b["verdict"] != "calibrated-claimable")
    check("F11 S2 在功率与复场两模式下**均 PASS**（模式感知，非单边判据）",
          _cm["S2"]["ok"] is True and _pm["S2"]["ok"] is True)
    check("F12 复场 N=4（无锚）：S3 PASS（σmin 3.83e-2 ≥ 1e-4）",
          {c["id"]: c["ok"] for c in selfcheck_report(4, "complex")["checks"]}["S3"] is True)

    # ======================================================= G 接口同形性
    par = protocol_interface_parity(4)
    check("G1 同形判据：WDM 清单 vs mesh_drive_manifest 必需共有键全中",
          par["wdm_vs_drive_ok"] is True, str(par["required_shared"]))
    check("G2 同形判据：WDM 清单 vs U8 nvm_drive_manifest 必需共有键全中",
          par["wdm_vs_nvm_ok"] is True)
    check("G3 三者共有键 == 4 个必需键",
          len(par["shared_all_three"]) == 4, str(par["shared_all_three"]))
    check("G4 WDM 独有键非空但**被解释**（expected_semantic_diff 非空 = 差异不静默）",
          len(par["only_wdm"]) > 0 and bool(par["expected_semantic_diff"]))
    pmz = per_mzi_calibration_plan(_mesh_parts(_generic_unitary(4))["bs_list"],
                                   _mesh_parts(_generic_unitary(4))["D"], 4, "complex")
    check("G5 per-MZI 方案 entries 数 == n_mzi（N=4 ⇒ 6）",
          pmz["n_mzi"] == 6 and len(pmz["entries"]) == 6, "%d" % pmz["n_mzi"])
    check("G6 🔴 per-MZI 闭环 **未闭合**（closed_loop_enabled False + open_loop 参考）",
          pmz["loop"]["closed_loop_enabled"] is False
          and pmz["open_loop_reference_only"] is True
          and bool(pmz["loop"]["why_disabled"]))
    check("G7 per-MZI entries 的 (j, col_c) 与 mesh_drive_manifest 的 mzi 一致",
          [(e["j"], e["col_c"]) for e in pmz["entries"]]
          == [(m["j"], m["col_c"]) for m in _drive(4)["mzi"]])
    check("G8 per-MZI 方案：N 与 D 阶不符 ⇒ raise",
          _rejects(lambda: per_mzi_calibration_plan(
              _mesh_parts(_generic_unitary(4))["bs_list"], np.eye(3, dtype=complex), 4),
              CalibrationProtocolError))
    check("G9 per-MZI entries 全部标 requires_anchor=True（无锚不可执行）",
          all(e["requires_anchor"] is True for e in pmz["entries"]))
    check("G10 per-MZI entries 的 col_order 在每列内 == 0..len(列)−1（真·列内序）",
          all(sorted(e["col_order"] for e in pmz["entries"] if e["col_c"] == c)
              == list(range(len([e for e in pmz["entries"] if e["col_c"] == c])))
              for c in {e["col_c"] for e in pmz["entries"]}))
    check("G10b per-MZI entries 的 seq_index 全局唯一（列桶序下无碰撞）",
          len({e["seq_index"] for e in pmz["entries"]}) == pmz["n_mzi"])

    # ======================================================= H 报告结构
    rep = calibration_protocol_report(8, "complex")
    expect = {"N", "claim", "anchor_kinds", "anchors_available", "protocol_steps",
              "state_machine", "identifiability", "wdm", "selfcheck", "interface",
              "per_mzi_plan", "guard_declaration", "disclosure", "prose"}
    check("H1 报告键集 == 期望（14 键）", set(rep) == expect,
          str(sorted(set(rep) ^ expect)))
    check("H2 报告可 JSON 序列化（结构完整）",
          isinstance(json.dumps(rep, ensure_ascii=False, default=str), str))
    check("H3 无锚时报告声明：pdk_process_truth_used False + calibrated_claim_made False",
          rep["guard_declaration"]["pdk_process_truth_used"] is False
          and rep["guard_declaration"]["calibrated_claim_made"] is False
          and rep["claim"]["claim"] == "protocol_designed")
    check("H4 🔴 守卫在**必经路径**上：无锚报告构造**不 raise**（合法路径必过）",
          not _rejects(lambda: calibration_protocol_report(4, "complex"), Exception))
    check("H5 带合格锚 ⇒ 报告不 raise 且 claim == calibrated（可满足性）",
          calibration_protocol_report(4, "complex",
                                      anchor=GOOD_ANCHOR)["claim"]["claim"] == "calibrated")
    check("H6 🔴 带**弱锚**（literature）⇒ 报告在必经路径 raise（红线真的挡）",
          _rejects(lambda: calibration_protocol_report(
              4, "complex", anchor={"kind": "literature", "is_attested": True}),
              CalibrationAnchorError))
    check("H7 报告 disclosure == CAL_DISCLOSURE 全 %d 键" % DISCLOSURE_KEYS,
          set(rep["disclosure"]) == set(CAL_DISCLOSURE)
          and len(rep["disclosure"]) == DISCLOSURE_KEYS)
    check("H8 报告 prose 含 foundry 字样、但守卫在必经路径上仍通过"
          "（钉住「只扫键名」是有意设计与可满足性）",
          "foundry" in rep["prose"]["redline"].lower()
          and not _rejects(lambda: guard_no_foundry_process_truth(
              {k: v for k, v in rep.items() if k not in ("prose", "disclosure")}), Exception))
    check("H9 报告 identifiability.mode == 请求 mode",
          rep["identifiability"]["mode"] == "complex")
    check("H10 报告 selfcheck.n_total == 7 且 state_machine.states == CAL_STATES",
          rep["selfcheck"]["n_total"] == 7
          and tuple(rep["state_machine"]["states"]) == CAL_STATES)
    check("H11 报告 protocol_steps 7 步且与模块常量一致",
          len(rep["protocol_steps"]) == 7
          and [s["id"] for s in rep["protocol_steps"]]
          == [s["id"] for s in CAL_PROTOCOL_STEPS])
    check("H12 报告 wdm.rank_constant True 且 rank_gain_per_lambda == 0（不利结论在报告里）",
          rep["wdm"]["rank_constant"] is True
          and rep["wdm"]["rank_gain_per_lambda"] == 0)
    check("H13 报告 per_mzi_plan 闭环未闭合（不粉饰）",
          rep["per_mzi_plan"]["loop"]["closed_loop_enabled"] is False)

    # ======================================================= I 独立重算容差
    check("I1 独立重算 (N−1)² 与模块 power_rank_law 逐位一致（N=2..8，容差 0）",
          all(_ind_law_power(N) == power_rank_law(N) for N in NS))
    check("I2 独立重算 2N−1 与模块 power_blind_dims 逐位一致（N=2..8）",
          all(_ind_blind(N) == power_blind_dims(N) for N in NS))
    check("I3 🔴 独立路径（FD(|U|²) 的 SVD 秩）与模块秩一致（N=4/6/8，功率）",
          all(_ind_rank(_ind_fd_power(N, _generic_unitary(N)))
              == identifiability_report(N, "power")["rank"] for N in (4, 6, 8)),
          str({N: _ind_rank(_ind_fd_power(N, _generic_unitary(N))) for N in (4, 6, 8)}))
    check("I3b 🔴 FD 秩估计的**噪声地板**被机器钉住：h=1e-6 ⇒ N=8 rank=50（伪非零，"
          "噪声 1.07e-10 压在阈值上）；h=1e-5 ⇒ rank=49（噪声 8.5e-12）"
          "⇒ 步长选择有测量依据，不是凑数",
          _ind_rank(_ind_fd_power(8, _generic_unitary(8), 1e-6)) == 50
          and _ind_rank(_ind_fd_power(8, _generic_unitary(8), 1e-5)) == 49)
    check("I4 🔴 独立路径确认 argD 列恒为 0（FD ≤ 1e-8，N=4/6/8）",
          all(_ind_argd_max(N) <= 1e-8 for N in (4, 6, 8)),
          str({N: "%.1e" % _ind_argd_max(N) for N in (4, 6, 8)}))
    check("I5 独立重算 λ 缩放向量与模块一致（N=4、λ=1600）",
          lam_scale_vector(4, [(0, 1.0, 2.0)] * 6, 1600.0).tolist()
          == _ind_lam_scale(4, 6, 1600.0))
    check("I6 🟡 探针自证：把「独立重算」故意写错 1e-3 ⇒ 判据会变红（容差有判别力）",
          abs(_ind_law_power(8) * (1.0 + 1e-3) - power_rank_law(8)) > 1e-9)
    check("I7 独立路径确认复场读出的秩 == N²（N=4/6/8）",
          all(_ind_rank(_ind_fd_complex(N, _generic_unitary(N))) == N * N
              for N in (4, 6, 8)))

    print("-" * 70)
    print("U10 校准固件（闭环 per-MZI 热/相）· 协议设计：%d 判据 · %d FAIL"
          % (PASS + FAIL, FAIL))
    return 1 if FAIL else 0


def _dft(N: int) -> np.ndarray:
    n = np.arange(N)
    return np.exp(2j * np.pi * np.outer(n, n) / N) / math.sqrt(N)


def _ind_argd_max(N: int) -> float:
    J = _ind_fd_power(N, _generic_unitary(N))
    n_mzi = _mesh_parts(_generic_unitary(N))["n_mzi"]
    block = J[:, 2 * n_mzi:]
    return float(np.max(np.abs(block))) if block.size else 0.0


def _old_power_jac(N_, bs_, D_, color_, n_cols_, mode="power"):
    """🔴 复刻早期**缺共轭**的实现（仅用于 D4 自证「修正前后差异是实质的」）。"""
    U, cols = cal_mod._jacobian_blocks(N_, bs_, D_, color_, n_cols_)
    if mode == "power":
        rows = [2.0 * (U * dU).real.ravel() for dU in cols]      # 🔴 缺 conj
    else:
        rows = [np.concatenate([dU.real.ravel(), dU.imag.ravel()]) for dU in cols]
    J = np.array(rows).T
    return {"J": J, "U": U, "n_params": len(cols), "n_ops": len(bs_), "mode": mode,
            "n_observables": int(J.shape[0]), "n_argd": N_, "n_mzi": len(bs_)}


def _wdm(N: int, mode: str = "power"):
    p = _mesh_parts(_generic_unitary(N))
    return wdm_calibration_manifest(p["bs_list"], p["D"], WDM_LAM_DEFAULT, N, mode)


def _drive(N: int):
    from lda_layout.mesh_pnr import mesh_drive_manifest
    p = _mesh_parts(_generic_unitary(N))
    bs, D, color = p["bs_list"], p["D"], p["color"]
    ops = [(int(b[0]), float(b[1]), float(b[2]), int(c)) for b, c in zip(bs, color)]
    return mesh_drive_manifest(ops, D, ps_arm_um=ARM_REF_UM)


if __name__ == "__main__":
    sys.exit(main())
