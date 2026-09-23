# -*- coding: utf-8 -*-
"""U6 常驻门禁：良率 / 容错映射（Yield / fault-tolerance mapping）· L2 设计层。

判据分组（A–L）
---------------
A 契约 / 披露（10 键齐全 + 常量自洽）
B 自由度账不变量（n_params == n_dof ⇒ **结构冗余 = 0**；N=2/3/4/8/16）
C 域校验（非法参数**必 raise**）+「合法必过」
D 前向 / 保真度不变量（`fid_ideal == 1` 机器精度 · **独立实现交叉验证**）
E 单点故障扫描（三 fatal 模式：**每个站点都掉** ⇒ 反向护栏「无冗余必掉」）
F 重编译上界（三 fatal 模式：`f_best < 1` ⇒ **软件不可修复**）
G θ 漂移**可**精确重编译（双向对照：与 F 组构成「可修 vs 不可修」判别）
H **N=2 严格闭式锚**（θ≡0 ⇒ 可达集 = 对角子群）· 闭式 ↔ 数值交叉验证
I 冗余良率（三方案闭式自洽 + 面积代价 + **dual_mesh 交叉点 N=6**）
J 对 PDK 的规格反解（`required_p_for_yield` 闭式核对 + **单调性**）
K 冗余盈亏平衡（判据 = **开关失效率**，不是 MZI 失效率）+ 独立重算
L 汇总报告结构完整

🔴 立场：本 smoke 断言的是**事实**，包括不利事实 ——
`B1` 断言「结构冗余 = 0」，`F1` 断言「硬失效**不可**精确重编译」，
`I2` 断言「站点热备在 p_switch≈p 时**净亏**」，`K1` 断言「冗余是否值得由**开关**
失效率决定」。若有人把模块改成「软件可修复故障 / 站点热备有净收益 / 有结构冗余」，
这些判据立刻变红。
"""
from __future__ import annotations

import cmath
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import numpy as np  # noqa: E402

from lda_harness.smoke_kit import make_check  # noqa: E402
from lda_l2.yield_fault_tolerance import (  # noqa: E402
    CALIBRATABLE_MODES,
    DEFAULT_DRIFT_RAD,
    DEFAULT_FAULT_PROB,
    DEFAULT_SWITCH_PROB,
    FATAL_MODES,
    FAULT_MODES,
    REDUNDANCY_SCHEMES,
    TARGET_GRID_YIELD,
    YIELD_DISCLOSURE,
    FaultToleranceError,
    _generic_unitary,
    _mesh_parts,
    _fidelity,
    _forward_unitary,
    closed_form_best_diagonal,
    fault_tolerance_report,
    inject_fault,
    mesh_redundancy_audit,
    redundancy_break_even,
    repair_upper_bound,
    required_p_for_yield,
    scheme_reliability,
    single_fault_scan,
    yield_curve,
)

PASS = 0
FAIL = 0
check = make_check(globals(), return_ok=True, detail_fmt="  —— {d}",
                   detail_on="fail")

# ---------------------------------------------------------------------------
# 本轮实测常量（GEN = `_generic_unitary`，一般位置 · 无 RNG）
# —— 用于把结论「钉死」；突变立刻越出容差。
# ---------------------------------------------------------------------------
AUDIT_N = (2, 3, 4, 8, 16)
AUDIT_EXPECT = {2: (4, 1), 3: (9, 3), 4: (16, 6), 8: (64, 28), 16: (256, 120)}

N2_CF_FID = 0.45843460296921246
N2_CF_DIAG_SUM = 0.82682768295554188
N2_CF_RES = 1.53177825878581930

G4_BAR = (0.65988163503733688, 0.73728793934807368, 0.70080811943791954, 2, 0)
G4_CROSS = (0.88494794918970265, 0.98134802194387816, 0.92938226810007019, 0, 2)
G4_PHI = (0.74838940028776602, 0.96010513169386991, 0.84308303323114708, 2, 1)
G4_REP = {
    "stuck_bar": (0.65988163503733688, 0.66019878510644148),
    "stuck_cross": (0.98134802194387816, 0.98138062285668870),
    "phi_dead": (0.74838940028776602, 0.98138301499633207),
}
G4_DRIFT = (0.99500008333291667, 0.99999999999999778)
G8_BAR_REP_K = 18
G8_BAR_REP = (0.82335829057222831, 0.82377582996547827)
# 🔴 **N=8 stuck_bar 的 `fid_best_repair` 不是确定性量** —— 优化器触 `max_nfev=800`
#    **未收敛**（`bound_kind` = 可达下界），其**迭代终点依赖 BLAS 归约顺序** ⇒ 跨线程
#    实测三档（2026-09-23 发布门禁抓出）：
#      · 默认（不注入线程 env）  0.82377582996547827
#      · 钉 1 线程              0.8237761308434008
#      · CI 口径（10 线程）      0.8237773247341804
#    ⇒ **跨度 1.4948e-6 ≫ `TOL_OPT`（1e-9）** ⇒ 对该量做位级断言是**判据写错**（不是
#    平台漂移）。⇒ 只能用**线程带** `TOL_OPT_NOCONV` 判定；`fid_naive`（收敛前量）跨
#    线程**逐位相同**，仍用 `TOL_OPT`。
#    注：**不得**为迁就判据把 `max_nfev` 调大以「凑收敛」—— 那会改掉 U6 的结论
#    （「触预算未收敛 ⇒ 只报下界、不冒充上界」）。
G8_BAR_REP_THREAD_BAND = (0.82377582996547827, 0.8237761308434008, 0.8237773247341804)
G8_BAR_REP_FROZEN_MID = 0.8237765

Y_NONE = {4: 0.99401498001499400, 8: 0.97237474437709559,
          16: 0.88686718758606375}
Y_SPARE = {4: 0.99400901594002378, 8: 0.97234751825180588}
Y_DUAL = {4: 0.99199240916846732, 8: 0.98336840639079204,
          16: 0.95609532628369798}
REQP_NONE = {4: 0.00167365385231044, 8: 0.00035887615473829,
             16: 8.374929161147904e-05}
REQP_DUAL = {8: 0.00061002066394916, 16: 0.0002799098951171141}
BE_SPARE_1E3 = 0.0009990009990010205
BE_DUAL8_1E3 = 0.0017017106483002142
DUAL_CROSSOVER = {4: False, 5: False, 6: True, 8: True}

TOL_EXACT = 1e-12      # 解析量
TOL_OPT = 1e-9         # 优化器输出（**已收敛**的，跨 BLAS 稳健）
TOL_OPT_NOCONV = 1e-5  # 优化器输出（**触预算未收敛**的 ⇒ 只判线程带；实测跨度
                       # 1.4948e-6 ⇒ 余量 6.7×。见 `G8_BAR_REP_THREAD_BAND` 注释）


# ---------------------------------------------------------------------------
# 独立重算助手（不同代码路径）
# ---------------------------------------------------------------------------
def _ind_T(theta, phi, j, N):
    """独立构造 N×N 的 ref_T（显式矩阵），与 `_ref_T` 同约定但独立实现。"""
    T = np.eye(N, dtype=complex)
    T[j, j] = cmath.exp(1j * phi) * math.cos(theta)
    T[j, j + 1] = -math.sin(theta)
    T[j + 1, j] = cmath.exp(1j * phi) * math.sin(theta)
    T[j + 1, j + 1] = math.cos(theta)
    return T


def _ind_forward(bs_list, D, N):
    """独立前向：逐 op 左乘显式矩阵（**不用** `_ref_T_apply_rows` 的行更新）。"""
    from lda_layout.mesh_pnr import _rect_column_assignment
    color = list(_rect_column_assignment(bs_list))
    n_cols = max(color) + 1 if color else 0
    buckets = [[] for _ in range(n_cols)]
    for i, row in enumerate(bs_list):
        buckets[color[i]].append((int(row[0]), float(row[1]), float(row[2])))
    U = np.eye(N, dtype=complex)
    for c in range(n_cols):
        for (j, th, ph) in buckets[c]:
            U = _ind_T(th, ph, j, N) @ U
    return np.diag(np.diag(np.asarray(D, dtype=complex))) @ U


def _ind_fid(U_rec, U_t):
    """独立保真度：用迹恒等式 ||A||_F² = Re tr(A†A)，**不用** np.linalg.norm。"""
    N = int(U_t.shape[0])
    R = np.asarray(U_rec) - np.asarray(U_t)
    fro = math.sqrt(max(0.0, float(np.real(np.trace(R.conj().T @ R)))))
    return float(max(0.0, 1.0 - fro / (N * math.sqrt(2.0))))


def _ind_yield(N, p, scheme, p_sw):
    M = N * (N - 1) // 2
    if scheme == "none":
        return (1.0 - p) ** M
    if scheme == "site_spare":
        return ((1.0 - p_sw) * (1.0 - p * p)) ** M
    return ((1.0 - p_sw) ** (2 * N)) * (1.0 - (1.0 - (1.0 - p) ** M) ** 2)


def _ind_reqp_none(N, y):
    M = N * (N - 1) // 2
    return 1.0 - y ** (1.0 / M)


def _ind_cf(U):
    """独立闭式：sqrt(2N - 2Σ|U_kk|)/(N√2)。"""
    N = int(U.shape[0])
    s = float(np.sum(np.abs(np.diag(np.asarray(U, dtype=complex)))))
    res = math.sqrt(max(0.0, 2.0 * N - 2.0 * s))
    return float(max(0.0, 1.0 - res / (N * math.sqrt(2.0)))), res


def _ind_be_spare(p):
    """site_spare 盈亏平衡的闭式：p_sw* = 1 - (1-p)/(1-p²)。"""
    return 1.0 - (1.0 - p) / (1.0 - p * p)


def _rejects(fn, exc=FaultToleranceError):
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


def _close(a, b, tol):
    return abs(float(a) - float(b)) <= tol


def main():  # noqa: C901
    # 注：`check` 由 `make_check(globals(), ...)` 直接写模块 globals，
    # 无需 `global PASS, FAIL`（写了会被 pyflakes 判 F824 型「unused global」）。
    U4 = _generic_unitary(4)
    U8 = _generic_unitary(8)
    U2 = _generic_unitary(2)

    # ======================= A 契约 / 披露
    check("A1 YIELD_DISCLOSURE 齐全且非空（11 键）",
          len(YIELD_DISCLOSURE) == 11
          and all(isinstance(v, str) and v.strip() for v in YIELD_DISCLOSURE.values()),
          "keys=%d" % len(YIELD_DISCLOSURE))
    check("A2 🔴 披露含「故障模型是假设非实测」",
          "fault_model_is_assumption_not_measurement" in YIELD_DISCLOSURE
          and "假设" in YIELD_DISCLOSURE["fault_model_is_assumption_not_measurement"])
    check("A3 🔴 披露含「无 foundry 良率真值 ⇒ 结论条件式」",
          "no_foundry_yield_truth" in YIELD_DISCLOSURE
          and "条件式" in YIELD_DISCLOSURE["no_foundry_yield_truth"])
    check("A4 🔴 披露含「结构冗余 = 0」",
          "no_structural_redundancy" in YIELD_DISCLOSURE
          and "N^2" in YIELD_DISCLOSURE["no_structural_redundancy"])
    check("A5 🔴 披露含「软件不可修复（与 U7 同源）」",
          "software_cannot_repair" in YIELD_DISCLOSURE
          and "U7" in YIELD_DISCLOSURE["software_cannot_repair"])
    check("A6 披露含「闭式锚仅 N=2」+「漂移属可标定（U10）」",
          "closed_form_anchor_scope" in YIELD_DISCLOSURE
          and "N=2" in YIELD_DISCLOSURE["closed_form_anchor_scope"]
          and "drift_is_calibratable_not_fatal" in YIELD_DISCLOSURE
          and "U10" in YIELD_DISCLOSURE["drift_is_calibratable_not_fatal"])
    check("A7 模式常量自洽（fatal 3 + calibratable 1 = modes 4，互斥）",
          set(FATAL_MODES) | set(CALIBRATABLE_MODES) == set(FAULT_MODES)
          and not (set(FATAL_MODES) & set(CALIBRATABLE_MODES))
          and len(FAULT_MODES) == 4)
    check("A8 冗余方案常量 = (none, site_spare, dual_mesh)",
          tuple(REDUNDANCY_SCHEMES) == ("none", "site_spare", "dual_mesh"))
    check("A9 缺省假设自洽（p = p_switch = 1e-3 · 漂移 0.02 rad）",
          DEFAULT_FAULT_PROB == 1.0e-3 and DEFAULT_SWITCH_PROB == 1.0e-3
          and _close(DEFAULT_DRIFT_RAD, 0.02, 0.0)
          and _close(TARGET_GRID_YIELD, 0.99, 0.0))

    # ======================= B 自由度账不变量
    ok_b = True
    for N in AUDIT_N:
        a = mesh_redundancy_audit(N)
        nd, nm = AUDIT_EXPECT[N]
        ok_b = ok_b and a["n_dof"] == nd and a["n_mzi"] == nm \
            and a["n_params"] == nd and a["redundancy_margin"] == 0 \
            and a["structural_redundancy"] is False
    check("B1 🔴 结构冗余 = 0（n_params == n_dof == N²，五个 N）", ok_b)
    check("B2 🔴 一次硬失效 ⇒ 可用参数 N²-1，缺口恰为 1",
          all(mesh_redundancy_audit(N)["deficit_after_one_fatal_fault"] == 1
              and mesh_redundancy_audit(N)["params_after_one_fatal_fault"]
              == N * N - 1 for N in AUDIT_N))
    check("B3 独立重算：n_dof == N² · n_mzi == N(N-1)/2 · n_params == 2*n_mzi+N",
          all(mesh_redundancy_audit(N)["n_dof"] == N * N
              and mesh_redundancy_audit(N)["n_mzi"] == N * (N - 1) // 2
              and mesh_redundancy_audit(N)["n_params"] == 2 * (N * (N - 1) // 2) + N
              for N in AUDIT_N))

    # ======================= C 域校验（必 raise）+ 合法必过
    bs4 = _mesh_parts(U4)["bs_list"]
    check("C1 N<2 必 raise", _rejects(lambda: mesh_redundancy_audit(1)))
    check("C2 未知失效模式必 raise（inject / scan / repair 三处）",
          _rejects(lambda: inject_fault(bs4, 0, mode="bogus"))
          and _rejects(lambda: single_fault_scan(U4, mode="bogus"))
          and _rejects(lambda: repair_upper_bound(U4, 0, mode="bogus")))
    check("C3 站点下标越界必 raise（k = n_mzi / 空序列）",
          _rejects(lambda: inject_fault(bs4, len(bs4)))
          and _rejects(lambda: inject_fault([], 0))
          and _rejects(lambda: repair_upper_bound(U4, len(bs4), mode="stuck_bar")))
    check("C4 失效率越域必 raise（p >= 1 或 < 0；p_switch 同）",
          _rejects(lambda: scheme_reliability(4, 1.5, "none"))
          and _rejects(lambda: scheme_reliability(4, -0.1, "none"))
          and _rejects(lambda: scheme_reliability(4, 1e-3, "none", p_switch=1.0)))
    check("C5 未知冗余方案必 raise（reliability / required_p）",
          _rejects(lambda: scheme_reliability(4, 1e-3, "bogus"))
          and _rejects(lambda: required_p_for_yield(4, scheme="bogus")))
    check("C6 目标良率越域必 raise（0 与 1 都是开区间端点）",
          _rejects(lambda: required_p_for_yield(4, target_yield=1.0))
          and _rejects(lambda: required_p_for_yield(4, target_yield=0.0)))
    check("C7 对 none 方案求盈亏平衡必 raise",
          _rejects(lambda: redundancy_break_even(4, scheme="none")))
    check("C8 合法必过：inject 保长且仅改 k 位",
          (lambda out: len(out) == len(bs4)
           and all(int(out[i][0]) == int(bs4[i][0]) and
                   (out[i][1] == bs4[i][1] and out[i][2] == bs4[i][2]) != (i == 0)
                   for i in range(len(bs4))))(inject_fault(bs4, 0, mode="stuck_bar")))
    check("C9 合法必过：p = p_switch = 0 ⇒ 三方案良率全 = 1；"
          "单 p=0 但开关非理想 ⇒ 冗余方案 < 1（开关代价被如实计入）",
          all(_close(scheme_reliability(4, 0.0, s, p_switch=0.0)["yield"], 1.0, 1e-15)
              for s in REDUNDANCY_SCHEMES)
          and _close(scheme_reliability(4, 0.0, "none")["yield"], 1.0, 1e-15)
          and scheme_reliability(4, 0.0, "dual_mesh")["yield"] < 1.0
          and scheme_reliability(4, 0.0, "site_spare")["yield"] < 1.0)
    check("C10 合法必过：对角酉在 N=2 闭式下精确可达",
          closed_form_best_diagonal(np.diag([1.0 + 0j, cmath.exp(0.3j)]))
          ["exactly_reachable"] is True)

    # ======================= D 前向 / 保真度不变量
    ok_d1 = True
    ok_d2 = True
    for N in (3, 4, 6, 8):
        for mk in (_generic_unitary,):
            U = mk(N)
            p = _mesh_parts(U)
            f = _fidelity(_forward_unitary(p["bs_list"], p["D"], N), U)
            ok_d1 = ok_d1 and f >= 1.0 - 1e-12
            ok_d2 = ok_d2 and _close(
                _ind_fid(_ind_forward(p["bs_list"], p["D"], N), U), f, TOL_EXACT)
    check("D1 fid_ideal == 1（机器精度，一般位置酉 N=3/4/6/8）", ok_d1)
    check("D2 🔴 独立实现交叉验证（显式矩阵乘 vs 行更新，容差 1e-12）", ok_d2)
    check("D3 退化角计数 = 0（一般位置酉无 θ≡0 / θ≡π/2）",
          all(sum(1 for b in _mesh_parts(_generic_unitary(N))["bs_list"]
                  if abs(b[1]) < 1e-12 or abs(b[1] - math.pi / 2) < 1e-12) == 0
              for N in (4, 8)))

    # ======================= E 单点故障扫描（反向护栏「无冗余必掉」）
    sc4 = {m: single_fault_scan(U4, mode=m) for m in FATAL_MODES}
    check("E1 🔴 无冗余必掉：三 fatal 模式下**每个站点**都掉（N=4）",
          all(sc4[m]["all_sites_degrade"] is True for m in FATAL_MODES)
          and all(sc4[m]["n_sites_degraded"] == sc4[m]["n_mzi"]
                  for m in FATAL_MODES))
    check("E2 N=4 扫描常量锁（stuck_bar min/max/mean/worst/best）",
          _close(sc4["stuck_bar"]["fid_min"], G4_BAR[0], TOL_EXACT)
          and _close(sc4["stuck_bar"]["fid_max"], G4_BAR[1], TOL_EXACT)
          and _close(sc4["stuck_bar"]["fid_mean"], G4_BAR[2], TOL_EXACT)
          and sc4["stuck_bar"]["worst_k"] == G4_BAR[3]
          and sc4["stuck_bar"]["best_k"] == G4_BAR[4])
    check("E3 N=4 扫描常量锁（stuck_cross / phi_dead）",
          _close(sc4["stuck_cross"]["fid_min"], G4_CROSS[0], TOL_EXACT)
          and _close(sc4["stuck_cross"]["fid_max"], G4_CROSS[1], TOL_EXACT)
          and sc4["stuck_cross"]["worst_k"] == G4_CROSS[3]
          and _close(sc4["phi_dead"]["fid_min"], G4_PHI[0], TOL_EXACT)
          and _close(sc4["phi_dead"]["fid_max"], G4_PHI[1], TOL_EXACT)
          and sc4["phi_dead"]["worst_k"] == G4_PHI[3])
    check("E4 独立重算：扫描每站点保真度（容差 1e-12，全站点）",
          all(_close(_ind_fid(_ind_forward(
                  inject_fault(bs4, r["k"], mode="stuck_bar"), p4D, 4), U4),
              r["fidelity"], TOL_EXACT)
              for r in sc4["stuck_bar"]["per_site"]
              for p4D in [_mesh_parts(U4)["D"]]))
    check("E5 N=8：三 fatal 模式同样全站点都掉",
          all(single_fault_scan(U8, mode=m)["all_sites_degrade"] is True
              for m in FATAL_MODES))
    # 🔴 本轮突变探针抓出的**覆盖缺口**：`inject_fault` 的 drift 分支此前无任何判据
    #    经过（只有 repair_upper_bound 内部直接改 x0）⇒ 把该分支置空也全绿。
    #    本判据补上：漂移扫描必须掉，且与重编译路径的 naive 值**逐位一致**。
    dr4 = single_fault_scan(U4, mode="drift", delta=DEFAULT_DRIFT_RAD)
    check("E6 θ 漂移扫描：全站点均掉（min=max=mean 退化）· "
          "与重编译路径 naive 值逐位一致（容差 1e-12）",
          dr4["all_sites_degrade"] is True
          and _close(dr4["fid_min"], G4_DRIFT[0], TOL_EXACT)
          and _close(dr4["fid_max"], dr4["fid_min"], TOL_EXACT)
          and _close(dr4["per_site"][sc4["stuck_bar"]["worst_k"]]["fidelity"],
                     repair_upper_bound(U4, sc4["stuck_bar"]["worst_k"],
                                        mode="drift",
                                        delta=DEFAULT_DRIFT_RAD)["fid_naive"],
                     TOL_EXACT))
    check("E7 独立重算漂移扫描（inject_fault(drift) 路径，容差 1e-12）",
          all(_close(_ind_fid(_ind_forward(
                  inject_fault(bs4, r["k"], mode="drift",
                               delta=DEFAULT_DRIFT_RAD), p4D2, 4), U4),
              r["fidelity"], TOL_EXACT)
              for r in dr4["per_site"]
              for p4D2 in [_mesh_parts(U4)["D"]]))

    # ======================= F 重编译上界（软件不可修复）
    k4 = sc4["stuck_bar"]["worst_k"]
    rep4 = {m: repair_upper_bound(U4, k4, mode=m) for m in FATAL_MODES}
    check("F1 🔴 三 fatal 模式：f_best < 1 ⇒ **软件不可精确修复**",
          all(rep4[m]["exactly_recoverable"] is False
              and rep4[m]["fid_best_repair"] < 1.0 for m in FATAL_MODES))
    check("F2 🔴 参数缺口恰为 1（free = N²-1 = 15/16）",
          all(rep4[m]["params_shortfall"] == 1 and rep4[m]["n_params_free"] == 15
              and rep4[m]["n_params_total"] == 16 for m in FATAL_MODES))
    check("F3 N=4 重编译常量锁（naive / best 三模式）",
          all(_close(rep4[m]["fid_naive"], G4_REP[m][0], TOL_OPT)
              and _close(rep4[m]["fid_best_repair"], G4_REP[m][1], TOL_OPT)
              for m in FATAL_MODES))
    check("F4 重编译收益有限（fid_best - fid_naive < 0.24，且 >= 0）",
          all(0.0 <= rep4[m]["repair_gain"] < 0.24 for m in FATAL_MODES),
          "gains=%s" % {m: round(rep4[m]["repair_gain"], 6) for m in FATAL_MODES})
    rep8 = repair_upper_bound(U8, G8_BAR_REP_K, mode="stuck_bar", max_nfev=800)
    # 🔴 结构性不变量（**跨线程不变**，判据主力）：仍未到 1、不可精确修复、且重编译
    #    只带来极小收益（实测跨度 1.49e-6 内，收益 ≈ 4.19e-4 ≪ 1e-3）⇒「软件救不回」。
    # 🔴 `fid_best_repair` 触预算**未收敛** ⇒ 只判**线程带**（位级断言是本轮修掉的缺陷）。
    check("F5 N=8 stuck_bar：f_best 仍 < 1（即使未收敛也足以证伪）",
          rep8["fid_best_repair"] < 1.0 and rep8["exactly_recoverable"] is False
          and 0.0 <= (rep8["fid_best_repair"] - rep8["fid_naive"]) < 1e-3
          and _close(rep8["fid_naive"], G8_BAR_REP[0], TOL_OPT)
          and abs(rep8["fid_best_repair"] - G8_BAR_REP_FROZEN_MID) < TOL_OPT_NOCONV
          and (max(G8_BAR_REP_THREAD_BAND) - min(G8_BAR_REP_THREAD_BAND)) < TOL_OPT_NOCONV,
          "fid_naive=%.17g fid_best=%.17g gain=%.3e band=%s(tol=%.1e)"
          % (rep8["fid_naive"], rep8["fid_best_repair"],
             rep8["fid_best_repair"] - rep8["fid_naive"],
             "[" + ", ".join("%.17g" % v for v in G8_BAR_REP_THREAD_BAND) + "]",
             TOL_OPT_NOCONV))
    check("F6 🔴 未收敛时 `bound_kind` 如实标为「下界」（不冒充上界）",
          rep8["converged"] is False and "下界" in rep8["bound_kind"])
    check("F7 🔴 双向：若声称可精确修复必红（exactly_recoverable is False）",
          (rep4["stuck_bar"]["exactly_recoverable"] is True) is False)

    # ======================= G θ 漂移可精确重编译（对照）
    rd4 = repair_upper_bound(U4, k4, mode="drift", delta=DEFAULT_DRIFT_RAD)
    rd8 = repair_upper_bound(U8, G8_BAR_REP_K, mode="drift",
                             delta=DEFAULT_DRIFT_RAD)
    check("G1 🔴 θ 漂移（参数全自由 N²/N²）⇒ **可**精确重编译回 1",
          rd4["exactly_recoverable"] is True
          and rd4["fid_best_repair"] >= 1.0 - TOL_OPT
          and rd4["n_params_free"] == rd4["n_params_total"] == 16
          and rd8["exactly_recoverable"] is True
          and rd8["fid_best_repair"] >= 1.0 - TOL_OPT)
    check("G2 漂移未标定时确实掉（naive < 1）· 常量锁",
          _close(rd4["fid_naive"], G4_DRIFT[0], TOL_OPT)
          and _close(rd4["fid_best_repair"], G4_DRIFT[1], TOL_OPT)
          and rd4["fid_naive"] < 1.0)
    check("G3 🔴 判别性对照：fatal 不可修 vs drift 可修（同一站点同一注入点）",
          rep4["stuck_bar"]["exactly_recoverable"] is False
          and rd4["exactly_recoverable"] is True
          and rep4["stuck_bar"]["k"] == rd4["k"] == k4)

    # ======================= H N=2 严格闭式锚
    cf = closed_form_best_diagonal(U2)
    rn2 = repair_upper_bound(U2, 0, mode="stuck_bar")
    check("H1 🔴 闭式 ↔ 数值**逐位一致**（容差 1e-9）",
          _close(cf["fid_best_diagonal"], rn2["fid_best_repair"], TOL_OPT),
          "cf=%.17f num=%.17f" % (cf["fid_best_diagonal"], rn2["fid_best_repair"]))
    check("H2 N=2 闭式常量锁（Σ|U_kk| / 残差 / f_best）",
          _close(cf["diag_abs_sum"], N2_CF_DIAG_SUM, TOL_EXACT)
          and _close(cf["residual_fro"], N2_CF_RES, TOL_EXACT)
          and _close(cf["fid_best_diagonal"], N2_CF_FID, TOL_EXACT))
    check("H3 🔴 一般位置的 N=2 U 精确**不可达**（θ≡0 只到对角子群）",
          cf["exactly_reachable"] is False and cf["offdiag_energy"] > 1.0)
    check("H4 独立重算闭式（容差 1e-12）",
          _close(_ind_cf(U2)[0], cf["fid_best_diagonal"], TOL_EXACT)
          and _close(_ind_cf(U2)[1], cf["residual_fro"], TOL_EXACT))
    check("H5 残差恒等式 2N - 2Σ|U_kk| == offdiag_energy + Σ(1-|U_kk|)²",
          _close(cf["offdiag_energy"]
                 + sum((1.0 - x) ** 2 for x in cf["diag_abs"]),
                 cf["residual_fro"] ** 2, 1e-12))

    # ======================= I 冗余良率
    check("I1 三方案良率常量锁（N=4/8/16）",
          _close(scheme_reliability(4, 1e-3, "none")["yield"], Y_NONE[4], TOL_EXACT)
          and _close(scheme_reliability(8, 1e-3, "none")["yield"], Y_NONE[8], TOL_EXACT)
          and _close(scheme_reliability(16, 1e-3, "none")["yield"], Y_NONE[16], TOL_EXACT)
          and _close(scheme_reliability(4, 1e-3, "site_spare")["yield"], Y_SPARE[4], TOL_EXACT)
          and _close(scheme_reliability(8, 1e-3, "site_spare")["yield"], Y_SPARE[8], TOL_EXACT)
          and _close(scheme_reliability(4, 1e-3, "dual_mesh")["yield"], Y_DUAL[4], TOL_EXACT)
          and _close(scheme_reliability(8, 1e-3, "dual_mesh")["yield"], Y_DUAL[8], TOL_EXACT)
          and _close(scheme_reliability(16, 1e-3, "dual_mesh")["yield"], Y_DUAL[16], TOL_EXACT))
    check("I2 🔴 站点热备在 p_switch = p 时**净亏**（三 N 全部）",
          all(scheme_reliability(N, 1e-3, "site_spare")["yield"]
              < scheme_reliability(N, 1e-3, "none")["yield"]
              for N in (4, 8, 16)))
    check("I3 🔴 dual_mesh 交叉点 = N=6（N<=5 净亏 / N>=6 净赚）",
          all((scheme_reliability(N, 1e-3, "dual_mesh")["yield"]
               > scheme_reliability(N, 1e-3, "none")["yield"]) is DUAL_CROSSOVER[N]
              for N in DUAL_CROSSOVER))
    check("I4 面积代价如实单列（none ×1 / 备 ×2；开关数 0 / M / 2N）",
          scheme_reliability(8, 1e-3, "none")["footprint_multiplier"] == 1.0
          and scheme_reliability(8, 1e-3, "site_spare")["footprint_multiplier"] == 2.0
          and scheme_reliability(8, 1e-3, "dual_mesh")["footprint_multiplier"] == 2.0
          and scheme_reliability(8, 1e-3, "none")["n_switch"] == 0
          and scheme_reliability(8, 1e-3, "site_spare")["n_switch"] == 28
          and scheme_reliability(8, 1e-3, "dual_mesh")["n_switch"] == 16)
    check("I5 独立重算三方案良率（容差 1e-15）",
          all(_close(_ind_yield(N, 1e-3, s, 1e-3),
                     scheme_reliability(N, 1e-3, s)["yield"], 1e-15)
              for N in (4, 8, 16) for s in REDUNDANCY_SCHEMES))
    check("I6 yield_curve 形状 = |N|×|p|×|schemes|（默认 p_switch=p 与显式 p_switch 两分支）",
          len(yield_curve([4, 8], [1e-3, 1e-2])) == 2 * 2 * 3
          and len(yield_curve([4, 8], [1e-3, 1e-2], p_switch=5e-4)) == 12
          and _close(yield_curve([4], [1e-3], ("none",), p_switch=0.0)[0]["yield"],
                     Y_NONE[4], TOL_EXACT)
          and _close(yield_curve([4], [1e-3], ("dual_mesh",), p_switch=0.0)[0]["yield"],
                     1.0 - (1.0 - Y_NONE[4]) ** 2, TOL_EXACT))
    check("I7 各返回 dict 的语义键齐全（note / honest_note 不落空）",
          bool(scheme_reliability(4, 1e-3, "none")["note"].strip())
          and bool(required_p_for_yield(4)["note"].strip())
          and bool(redundancy_break_even(4, "site_spare")["note"].strip())
          and bool(single_fault_scan(U4, mode="stuck_bar")["honest_note"].strip())
          and bool(repair_upper_bound(U4, 0, mode="stuck_bar")["honest_note"].strip())
          and bool(closed_form_best_diagonal(U2)["honest_note"].strip())
          and bool(mesh_redundancy_audit(4)["note"].strip()))

    # ======================= J 对 PDK 的规格反解
    check("J1 none 方案反解闭式核对（N=4/8/16，容差 1e-15）",
          all(_close(required_p_for_yield(N, scheme="none")["required_device_failure_prob"],
                     _ind_reqp_none(N, TARGET_GRID_YIELD), 1e-15)
              for N in (4, 8, 16)))
    check("J2 规格常量锁（none N=4/8/16 · dual_mesh N=8/16）",
          _close(required_p_for_yield(4, scheme="none")["required_device_failure_prob"],
                 REQP_NONE[4], TOL_EXACT)
          and _close(required_p_for_yield(8, scheme="none")["required_device_failure_prob"],
                     REQP_NONE[8], TOL_EXACT)
          and _close(required_p_for_yield(16, scheme="none")["required_device_failure_prob"],
                     REQP_NONE[16], TOL_EXACT)
          and _close(required_p_for_yield(8, scheme="dual_mesh")["required_device_failure_prob"],
                     REQP_DUAL[8], 1e-12)
          and _close(required_p_for_yield(16, scheme="dual_mesh")["required_device_failure_prob"],
                     REQP_DUAL[16], 1e-12))
    check("J3 🔴 单调性：M ↑ ⇒ 规格严（p*(4) > p*(8) > p*(16)，none）",
          required_p_for_yield(4, scheme="none")["required_device_failure_prob"]
          > required_p_for_yield(8, scheme="none")["required_device_failure_prob"]
          > required_p_for_yield(16, scheme="none")["required_device_failure_prob"])
    check("J4 🔴 dual_mesh 在 N=16 反而**放宽**规格（p* 变大 ⇒ 冗余买了器件容差）",
          required_p_for_yield(16, scheme="dual_mesh")["required_device_failure_prob"]
          > required_p_for_yield(16, scheme="none")["required_device_failure_prob"]
          and required_p_for_yield(16, scheme="dual_mesh")["required_device_failure_prob"]
          > required_p_for_yield(16, scheme="site_spare")["required_device_failure_prob"])
    check("J5 反解自洽：把 p* 代回良率 == target（容差 1e-12）",
          all(_close(scheme_reliability(N, required_p_for_yield(
                  N, scheme="none")["required_device_failure_prob"], "none")["yield"],
              TARGET_GRID_YIELD, 1e-12) for N in (4, 8, 16)))

    # ======================= K 冗余盈亏平衡（判据 = 开关，不是 MZI）
    be_sp = redundancy_break_even(8, "site_spare")
    be_du = redundancy_break_even(8, "dual_mesh")
    check("K1 🔴 site_spare 盈亏平衡闭式核对（p=1e-3 ⇒ p_sw* ≈ 9.990e-4）",
          _close(be_sp["rows"][2]["max_switch_prob_for_parity"], BE_SPARE_1E3, 1e-15)
          and _close(_ind_be_spare(1e-3), BE_SPARE_1E3, 1e-15))
    check("K2 🔴 p_sw* < p ⇒ **现实中（开关与 MZI 同量级失效率）冗余净亏**",
          all(r["max_switch_prob_for_parity"] < r["p"] for r in be_sp["rows"]),
          "rows=%s" % [(r["p"], round(r["max_switch_prob_for_parity"], 8))
                        for r in be_sp["rows"]])
    check("K3 dual_mesh 盈亏平衡常量锁（N=8 · p=1e-3 ⇒ 1.7017e-3）",
          _close(be_du["rows"][2]["max_switch_prob_for_parity"], BE_DUAL8_1E3, 1e-15))
    check("K4 🔴 dual_mesh 允许的开关失效率**高于 p**（大 N 下冗余真能买器件容差）",
          be_du["rows"][2]["max_switch_prob_for_parity"] > be_du["rows"][2]["p"]
          and be_du["rows"][2]["n_switch"] == 16)
    check("K5 独立重算：p_sw* 代回 ⇒ 良率恰等于无冗余（容差 1e-12，四档 p）",
          all(_close(scheme_reliability(8, r["p"], "site_spare",
                                        p_switch=r["max_switch_prob_for_parity"])["yield"],
                     r["yield_none"], 1e-12) for r in be_sp["rows"]))

    # ======================= L 汇总报告结构
    rep = fault_tolerance_report(U4)
    need = ("N", "n_mzi", "worst_site", "drift_probe_site", "audit",
            "single_fault_scans", "repair_bounds", "closed_form_anchor_n2",
            "yield_curve_at_p", "required_p", "break_even", "disclosure")
    check("L1 report 结构完整（12 键）",
          all(k in rep for k in need) and rep["N"] == 4 and rep["n_mzi"] == 6)
    check("L2 report 内子结构完整（三 fatal 扫描 + 三 fatal 修复 + drift）",
          set(rep["single_fault_scans"]) == set(FATAL_MODES)
          and set(rep["repair_bounds"]) == set(FATAL_MODES) | {"drift"}
          and set(rep["required_p"]) == set(REDUNDANCY_SCHEMES)
          and set(rep["break_even"]) == {"site_spare", "dual_mesh"})
    check("L3 report 的 worst_site 按**各模式各自**取（不自相矛盾）",
          all(rep["worst_site"][m] == rep["single_fault_scans"][m]["worst_k"]
              for m in FATAL_MODES)
          and rep["drift_probe_site"] == rep["worst_site"]["stuck_bar"])
    check("L4 report 内 disclosure 是副本（不与模块常量同一对象）",
          rep["disclosure"] == YIELD_DISCLOSURE
          and rep["disclosure"] is not YIELD_DISCLOSURE)
    check("L5 🔴 report 的 audit 结论仍是「结构冗余 = 0」（不可被覆写）",
          rep["audit"]["redundancy_margin"] == 0
          and rep["audit"]["structural_redundancy"] is False)

    total = PASS + FAIL
    print("-" * 74)
    print("yield_fault_tolerance smoke：%d PASS / %d FAIL / 共 %d 项"
          % (PASS, FAIL, total))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
