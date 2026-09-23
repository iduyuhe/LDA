# -*- coding: utf-8 -*-
"""U7 常驻门禁：损耗感知编译（Loss-aware compilation）· L2 设计层。

判据分组（A–K）
---------------
A 契约 / 披露（9 键齐全 + 关键结论必须出现在披露文本里）
B 几何不变量（deg 多集 = {N/2, N/2, N…N} · deg_span = N/2 · n_cols = N · L_bus > col_pitch）
C 域校验（非法参数**必 raise**）+「合法必过」
D 格点 DP 可达范围（与 deg_min/deg_max 自洽 + **暴力枚举独立重算**）
E 精确核算 vs 保守口径（dIL_per_tap 恒定 · 闭式自洽 · reduction >= 20%）
F 保守上界**机器化证伪**（D1 `IL_short` 不可实现 · ratio 随 N 增长 · 阈值双向）
G 结构性零自由度（10 种合法变换下 deg 多集不变）
H 变长列（真实降 L_bus >= 4% · **但 IL_var 不变** —— 双向判据）
I 既有口径漂移对照（D1 文档含 1.3 余量 vs manifest 实现不含）
J 保真度 / DRC / LVS **不退化**
K 独立重算 + 突变探针友好性（容差紧到能把伪造值判红）

🔴 立场：本 smoke 断言的是**事实**，包括不利事实 ——
`A3`/`G1`/`H2` 断言「编译层对 IL_var **零自由度**」「deg 多集**不变**」「变长列**不改 IL_var**」，
`E1` 断言 `dIL_per_tap` 在三个 N 上**恒定**，`E4` 断言高估倍率**趋 2 而不越 2**，
`F1` 断言 D1 的 `IL_short` **不可实现**。若有人把模块改成「找到了更优布局 / IL_var 可控 /
短路径可实现」，这些判据立刻变红。
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402
from lda_l2.loss_aware_compile import (  # noqa: E402
    ALPHA_PROP_DEFAULT,
    ALPHA_TAP_DEFAULT,
    COL_GAP_DEFAULT,
    D1_TAP_SWITCH_MARGIN,
    GAP_DEFAULT,
    LC_MARGIN_DEFAULT,
    LOSS_AWARE_DISCLOSURE,
    MIN_INFEASIBLE_RATIO,
    RAIL_PITCH_DEFAULT,
    LossAwareCompileError,
    area_loss_tradeoff,
    conservative_overestimate,
    d1_conservative_io,
    deg_multiset_invariance,
    il_db,
    il_per_port_direct_bus,
    loss_aware_compile_report,
    manifest_io_comparison,
    ntap_reachable_range,
    path_length_um,
    percol_adaptive_width,
    rail_geometry,
    refute_short_path_infeasible,
)

PASS = 0
FAIL = 0
check = make_check(globals(), return_ok=True, detail_on="fail")

# ---------------------------------------------------------------------------
# 本轮实测常量（DFT(N) · grid2d · rail_pitch=4.0 · alpha_prop=2.0 · alpha_tap=0.05）
# —— 用于把结论「钉死」；突变会立刻越出容差。
# ---------------------------------------------------------------------------
NS = (4, 8, 16)
L_BUS = {4: 145.333333333, 8: 278.653408516, 16: 551.122843858}
COL_PITCH = {4: 30.333333333, 8: 31.831676065, 16: 32.945177741}
X_MAX = {4: 155.333333333, 8: 288.653408516, 16: 561.122843858}
L_OVER_CP = {4: 4.791208791, 8: 8.753965954, 16: 16.728482942}
DEG = {4: [2, 4, 4, 2], 8: [4] + [8] * 6 + [4], 16: [8] + [16] * 14 + [8]}
DEG_SPAN = {4: 2, 8: 4, 16: 8}
N_MZI = {4: 6, 8: 28, 16: 120}
D1_IL_FULL = {4: 0.224066667, 8: 0.510730682, 16: 1.085224569}
D1_IL_SHORT = {4: 0.056066667, 8: 0.056366335, 16: 0.056589036}
D1_VAR_IO = {4: 0.168000000, 8: 0.454364346, 16: 1.028635533}
EXACT_VAR = {4: 0.101480000, 8: 0.202960000, 16: 0.405920000}
EXACT_MEAN = {4: 0.181286667, 8: 0.410910682, 16: 0.871324569}
IL_MIN_PHYS = {4: 0.130546667, 8: 0.258690682, 16: 0.516144569}
INFEAS_RATIO = {4: 2.328418549, 8: 4.589453629, 16: 9.120928883}
OVER_X = {4: 1.655498620, 8: 2.238689133, 16: 2.534084384}
REDUCTION = {4: 0.395952381, 8: 0.553310022, 16: 0.605380150}
VARCOL_RED = {4: 0.063873626, 8: 0.060961497, 16: 0.049371793}
VARCOL_WIDTH = {4: 113.583333333, 8: 239.129355444, 16: 501.097843798}
WIDTH_FIXED = {4: 121.333333333, 8: 254.653408516, 16: 527.122843858}
MANIFOLD_GAP = {4: 0.045, 8: 0.105, 16: 0.225}
IL_MEAN_DELTA = {4: -0.001550000, 8: -0.003104811, 16: -0.005205000}

#: 每个 MZI 的「单位抽头损耗」= alpha_prop*(rail_pitch-gap)/1e4 + alpha_tap
DIL_PER_TAP = 0.050740000
D_RAIL_GAP = RAIL_PITCH_DEFAULT - GAP_DEFAULT          # 3.7 µm
PDK = {"alpha_prop_db_cm": ALPHA_PROP_DEFAULT, "alpha_tap_db": ALPHA_TAP_DEFAULT}


def _rejects(fn, exc: type = Exception) -> bool:
    """fn() 必须抛 exc（且不是别的异常）⇒ True。"""
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


# ---------------------------------------------------------------------------
# 独立重算（不复用模块函数）
# ---------------------------------------------------------------------------
def _ind_Lpath(n_tap, L_bus_um, rp=RAIL_PITCH_DEFAULT, g=GAP_DEFAULT):
    return L_bus_um + n_tap * (rp - g)


def _ind_il(n_tap, L_bus_um, ap=ALPHA_PROP_DEFAULT, at=ALPHA_TAP_DEFAULT,
            rp=RAIL_PITCH_DEFAULT, g=GAP_DEFAULT):
    return ap * _ind_Lpath(n_tap, L_bus_um, rp, g) / 1e4 + n_tap * at


def _ind_d1_var_io(L_bus_um, col_pitch_um, deg_mean,
                   ap=ALPHA_PROP_DEFAULT, at=ALPHA_TAP_DEFAULT, margin=D1_TAP_SWITCH_MARGIN):
    IL_full = ap * L_bus_um / 1e4 + deg_mean * margin * at
    IL_short = ap * col_pitch_um / 1e4 + 1.0 * at
    return IL_full - IL_short


def _ind_varcol_width(ops, lc_margin=LC_MARGIN_DEFAULT, col_gap=COL_GAP_DEFAULT):
    from lda_layout.mesh_pnr import coupler_length_from_theta
    per = {}
    for row in ops:
        th = float(row[1])
        c = int(row[3])
        Lu = coupler_length_from_theta(2.0 * th) + 2.0 * lc_margin
        per[c] = max(per.get(c, -1.0), Lu)
    return sum(per[c] + col_gap for c in per)


def _ind_dp_enum(ops, N):
    """暴力递归枚举所有 rail 轨迹（仅小 N）—— 独立于模块的逐列 DP。"""
    cols = {}
    for row in ops:
        cols.setdefault(int(row[3]), set()).add(int(row[0]))
    order = sorted(cols)
    best = [10 ** 9, -1]

    def rec(i, k, acc):
        if i == len(order):
            best[0] = min(best[0], acc)
            best[1] = max(best[1], acc)
            return
        js = cols[order[i]]
        has = (k in js) or ((k - 1) in js)
        rec(i + 1, k, acc + (1 if has else 0))
        if k in js and k + 1 < N:
            rec(i + 1, k + 1, acc + 1)
        if (k - 1) in js and k - 1 >= 0:
            rec(i + 1, k - 1, acc + 1)

    for k0 in range(N):
        rec(0, k0, 0)
    return best[0], best[1]


def main():  # noqa: C901
    import numpy as np
    from lda_layout.mesh_pnr import build_mesh_pnr

    br, geo, d1, ex, rf, ov, vw, mc = {}, {}, {}, {}, {}, {}, {}, {}
    for N in NS:
        U = np.fft.fft(np.eye(N)).astype(complex) / math.sqrt(N)
        br[N] = build_mesh_pnr(U, rail_pitch=RAIL_PITCH_DEFAULT, layout_mode="grid2d")
        geo[N] = rail_geometry(br[N])
        d1[N] = d1_conservative_io(br[N], PDK)
        ex[N] = il_per_port_direct_bus(br[N], PDK)
        rf[N] = refute_short_path_infeasible(br[N], PDK)
        ov[N] = conservative_overestimate(br[N], PDK)
        vw[N] = percol_adaptive_width(br[N])
        mc[N] = manifest_io_comparison(br[N], PDK)

    # ================================================= A 契约 / 披露 / 常量
    need = {"scope", "parameterized_not_measured", "physical_lower_bound_not_layout_gain",
            "compile_degree_of_freedom_is_zero", "varcol_reduces_mean_not_var",
            "dp_is_geometric_not_photonic", "no_fdtd_no_3d", "honest_verdict_on_target",
            "d1_doc_vs_manifest_io_margin"}
    check("A1 披露项键齐全（9 项，防被悄悄删）",
          need.issubset(set(LOSS_AWARE_DISCLOSURE.keys())),
          "missing=%s" % sorted(need - set(LOSS_AWARE_DISCLOSURE.keys())))
    check("A2 🔴 披露「physical_lower_bound_not_layout_gain」明写这是**口径精确化 / 不是更优布局**",
          "口径精确化" in LOSS_AWARE_DISCLOSURE["physical_lower_bound_not_layout_gain"]
          and "不是" in LOSS_AWARE_DISCLOSURE["physical_lower_bound_not_layout_gain"])
    check("A3 🔴 披露「compile_degree_of_freedom_is_zero」明写编译层对 IL_var **自由度为 0**",
          "真实自由度为 0" in LOSS_AWARE_DISCLOSURE["compile_degree_of_freedom_is_zero"])
    check("A4 披露「varcol_reduces_mean_not_var」明写变长列对 IL_var **零贡献**",
          "零贡献" in LOSS_AWARE_DISCLOSURE["varcol_reduces_mean_not_var"])
    check("A5 披露「dp_is_geometric_not_photonic」明写 DP 是**几何可达**非实际光路",
          "几何可达" in LOSS_AWARE_DISCLOSURE["dp_is_geometric_not_photonic"])
    check("A6 🔴 披露「d1_doc_vs_manifest_io_margin」记录既有 1.3 余量口径漂移",
          "1.3" in LOSS_AWARE_DISCLOSURE["d1_doc_vs_manifest_io_margin"]
          and "manifest" in LOSS_AWARE_DISCLOSURE["d1_doc_vs_manifest_io_margin"])
    check("A7 🔴 披露「honest_verdict_on_target」明写原验收判据**不可达 / 不声称达标**",
          "不可达" in LOSS_AWARE_DISCLOSURE["honest_verdict_on_target"]
          and "不声称达标" in LOSS_AWARE_DISCLOSURE["honest_verdict_on_target"])
    check("A8 披露「no_fdtd_no_3d」明写不跑 FDTD / 不做 3D",
          "不跑 FDTD" in LOSS_AWARE_DISCLOSURE["no_fdtd_no_3d"]
          and "3D" in LOSS_AWARE_DISCLOSURE["no_fdtd_no_3d"])
    check("A9 披露「parameterized_not_measured」明写参数化估算（L3）非实测",
          "L3" in LOSS_AWARE_DISCLOSURE["parameterized_not_measured"])
    check("A10 常量：MIN_INFEASIBLE_RATIO=2.0 · margin=1.3 · alpha=(2.0, 0.05)",
          abs(MIN_INFEASIBLE_RATIO - 2.0) < 1e-12
          and abs(D1_TAP_SWITCH_MARGIN - 1.3) < 1e-12
          and abs(ALPHA_PROP_DEFAULT - 2.0) < 1e-12
          and abs(ALPHA_TAP_DEFAULT - 0.05) < 1e-12)

    # ==================================================== B 几何不变量
    check("B1 deg 多集 = {N/2, N/2, N…N}（三 N 逐一核对，结构不变量）",
          all(sorted(geo[N]["deg"]) == sorted(DEG[N]) for N in NS),
          "got=%s" % {N: geo[N]["deg"] for N in NS})
    check("B2 deg_span = N/2（三 N）",
          all(geo[N]["deg_span"] == DEG_SPAN[N] == N // 2 for N in NS),
          "got=%s" % {N: geo[N]["deg_span"] for N in NS})
    check("B3 n_cols = N（ASAP 着色最小列数）",
          all(geo[N]["n_cols"] == N for N in NS),
          "got=%s" % {N: geo[N]["n_cols"] for N in NS})
    check("B4 L_bus > col_pitch **严格**（三 N）—— 直总线几何的硬事实",
          all(geo[N]["L_bus_um"] > geo[N]["col_pitch_um"] for N in NS),
          "got=%s" % {N: geo[N]["L_bus_over_col_pitch"] for N in NS})
    check("B5 L_bus 钉住（三 N，容差 1e-6）",
          all(abs(geo[N]["L_bus_um"] - L_BUS[N]) < 1e-6 for N in NS),
          "got=%s" % {N: geo[N]["L_bus_um"] for N in NS})
    check("B6 col_pitch 钉住 + L_bus/col_pitch 钉住（三 N）",
          all(abs(geo[N]["col_pitch_um"] - COL_PITCH[N]) < 1e-6
              and abs(geo[N]["L_bus_over_col_pitch"] - L_OVER_CP[N]) < 1e-6 for N in NS),
          "got=%s" % {N: geo[N]["col_pitch_um"] for N in NS})
    check("B7 x_max = L_bus + MESH_X0(10.0) 且 n_mzi = N(N-1)/2",
          all(abs(br[N]["x_max_um"] - X_MAX[N]) < 1e-6
              and geo[N]["n_mzi"] == N_MZI[N] == N * (N - 1) // 2 for N in NS))

    # ================================================ C 域校验 + 合法必过
    good = {"N": 4, "ops": [(0, 0.3, 0.1, 0)], "x_max_um": 100.0, "pitch_um": 20.0}
    check("C1 rail_geometry 缺 ops ⇒ raise", _rejects(
        lambda: rail_geometry({"N": 4, "x_max_um": 1.0, "pitch_um": 1.0}), LossAwareCompileError))
    check("C2 rail_geometry N<2 ⇒ raise", _rejects(
        lambda: rail_geometry({"N": 1, "ops": [(0, 0.1, 0.0, 0)], "x_max_um": 9.0, "pitch_um": 1.0}),
        LossAwareCompileError))
    check("C3 rail_geometry col_pitch<=0 ⇒ raise", _rejects(
        lambda: rail_geometry({"N": 4, "ops": [(0, 0.1, 0.0, 0)], "x_max_um": 9.0, "pitch_um": 0.0}),
        LossAwareCompileError))
    check("C4 rail_geometry j 越界 ⇒ raise", _rejects(
        lambda: rail_geometry({"N": 4, "ops": [(3, 0.1, 0.0, 0)], "x_max_um": 9.0, "pitch_um": 1.0}),
        LossAwareCompileError))
    check("C5 path_length_um n_tap<0 ⇒ raise", _rejects(
        lambda: path_length_um(-0.5, 100.0), LossAwareCompileError))
    check("C6 il_db alpha<0 ⇒ raise", _rejects(
        lambda: il_db(3.0, 100.0, -1.0, 0.05), LossAwareCompileError))
    check("C7 rail_pitch < gap ⇒ raise（几何非法）", _rejects(
        lambda: path_length_um(3.0, 100.0, rail_pitch=0.2, gap=0.3), LossAwareCompileError))
    check("C8 d1_conservative_io margin<=0 ⇒ raise", _rejects(
        lambda: d1_conservative_io(good, PDK, tap_switch_margin=0.0), LossAwareCompileError))
    check("C9 ntap_reachable_range 空 ops ⇒ raise", _rejects(
        lambda: ntap_reachable_range([], 4), LossAwareCompileError))
    check("C10 deg_multiset_invariance 非法 port_perm ⇒ raise", _rejects(
        lambda: deg_multiset_invariance(np.eye(4, dtype=complex), port_perm=[0, 1, 1, 3]),
        LossAwareCompileError))
    check("C11 percol_adaptive_width 非 grid2d ⇒ raise", _rejects(
        lambda: percol_adaptive_width({"N": 4, "ops": [(0, 0.3, 0.1, 0)],
                                       "x_max_um": 100.0, "pitch_um": 20.0,
                                       "layout_mode": "serpentine"}), LossAwareCompileError))
    check("C12 合法必过：正常 build_result 全链路不 raise",
          rail_geometry(br[4])["N"] == 4
          and path_length_um(2.0, 50.0) > 50.0
          and il_db(0.0, 50.0, 2.0, 0.05) > 0.0
          and d1_conservative_io(br[4], PDK)["IL_var_io_db"] > 0.0)
    check("C13 🔴 D1 口径**域边界**：deg_mean 过小 ⇒ IL_full <= IL_short 必 raise（不静默返回负方差）",
          _rejects(lambda: d1_conservative_io(
              {"N": 4, "ops": [(0, 0.3, 0.1, 0)], "x_max_um": 100.0, "pitch_um": 20.0},
              PDK), LossAwareCompileError))

    # ============================================== D 格点 DP 可达范围
    dp = {N: ntap_reachable_range(geo[N]["ops"], N) for N in NS}
    check("D1 DP n_tap_min == deg_min（三 N，模型自洽）",
          all(dp[N]["n_tap_min"] == geo[N]["deg_min"] for N in NS),
          "got=%s" % {N: (dp[N]["n_tap_min"], geo[N]["deg_min"]) for N in NS})
    check("D2 DP n_tap_max == deg_max（三 N）",
          all(dp[N]["n_tap_max"] == geo[N]["deg_max"] for N in NS),
          "got=%s" % {N: (dp[N]["n_tap_max"], geo[N]["deg_max"]) for N in NS})
    check("D3 DP n_tap 范围 = [N/2, N]（三 N，钉住）",
          all(dp[N]["n_tap_min"] == N // 2 and dp[N]["n_tap_max"] == N for N in NS),
          "got=%s" % {N: (dp[N]["n_tap_min"], dp[N]["n_tap_max"]) for N in NS})
    _mn, _mx = _ind_dp_enum(geo[4]["ops"], 4)
    check("D4 🔴 暴力枚举独立重算 DP（N=4）⇒ 完全一致",
          (_mn, _mx) == (dp[4]["n_tap_min"], dp[4]["n_tap_max"]),
          "enum=(%d,%d) dp=(%d,%d)" % (_mn, _mx, dp[4]["n_tap_min"], dp[4]["n_tap_max"]))

    # ======================================= E 精确核算 vs 保守口径
    check("E1 🔴 dIL_per_tap 在三个 N 上**恒定** = 0.05074（= 2.0*3.7/1e4 + 0.05）",
          all(abs(ex[N]["dIL_per_tap_db"] - DIL_PER_TAP) < 1e-9 for N in NS),
          "got=%s" % {N: ex[N]["dIL_per_tap_db"] for N in NS})
    check("E2 闭式自洽：exact_var == deg_span * dIL_per_tap（三 N，容差 1e-12 相对）",
          all(abs(ex[N]["IL_var_ports_db"] - DEG_SPAN[N] * DIL_PER_TAP) < 1e-12 for N in NS),
          "got=%s" % {N: ex[N]["IL_var_ports_db"] for N in NS})
    check("E3 exact_var / exact_mean 钉住（三 N）",
          all(abs(ex[N]["IL_var_ports_db"] - EXACT_VAR[N]) < 1e-9
              and abs(ex[N]["IL_mean_db"] - EXACT_MEAN[N]) < 1e-9 for N in NS))
    check("E4 🔴 IL_var 相对 D1 保守口径下降 **>= 20%**（三 N —— 验收判据）",
          all(ov[N]["reduction_ratio"] >= 0.20 for N in NS),
          "got=%s" % {N: round(100.0 * ov[N]["reduction_ratio"], 2) for N in NS})
    check("E5 高估倍率 monotone 递增且**始终 < 2.6**（渐近 1.3*2 —— D1 文档含 1.3 轨切换余量）",
          OVER_X[4] < OVER_X[8] < OVER_X[16] < 2.6
          and all(abs(ov[N]["overestimate_x"] - OVER_X[N]) < 1e-8 for N in NS),
          "got=%s" % {N: ov[N]["overestimate_x"] for N in NS})
    ov_impl = {N: d1_conservative_io(br[N], PDK, 1.0)["IL_var_io_db"]
               / ex[N]["IL_var_ports_db"] for N in NS}
    check("E5b 🔴 去掉 1.3 余量（复现 manifest 实现口径）后高估倍率渐近 **2.0**（三 N 均 < 2）",
          all(ov_impl[N] < 2.0 for N in NS) and ov_impl[4] < ov_impl[8] < ov_impl[16],
          "got=%s" % {N: round(ov_impl[N], 6) for N in NS})
    check("E6 下降率随 N 单调递增（39.6% < 55.3% < 60.5%）",
          REDUCTION[4] < REDUCTION[8] < REDUCTION[16]
          and all(abs(ov[N]["reduction_ratio"] - REDUCTION[N]) < 1e-8 for N in NS))

    # ====================================== F 保守上界机器化证伪
    check("F1 🔴 D1 的 IL_short（col_pitch + 1 tap）**物理不可实现**（三 N）",
          all(rf[N]["short_path_infeasible"] is True for N in NS))
    check("F2 🔴 infeasible_ratio >= MIN_INFEASIBLE_RATIO 且随 N **单调递增**",
          all(rf[N]["infeasible_ratio"] >= MIN_INFEASIBLE_RATIO for N in NS)
          and INFEAS_RATIO[4] < INFEAS_RATIO[8] < INFEAS_RATIO[16]
          and all(abs(rf[N]["infeasible_ratio"] - INFEAS_RATIO[N]) < 1e-8 for N in NS),
          "got=%s" % {N: rf[N]["infeasible_ratio"] for N in NS})
    check("F3 物理最小 IL 钉住（= deg_min 个抽头 + 全宽）",
          all(abs(rf[N]["IL_min_physical_db"] - IL_MIN_PHYS[N]) < 1e-9 for N in NS))
    check("F4 🔴 阈值确实在起作用（造两反例：ratio=1.5 判否 / 实测判是）",
          (1.5 >= MIN_INFEASIBLE_RATIO) is False
          and (INFEAS_RATIO[4] >= MIN_INFEASIBLE_RATIO) is True)
    check("F5 D1 IL_full / IL_short / var_io 三值钉住（D1 §二 公式复算）",
          all(abs(d1[N]["IL_full_db"] - D1_IL_FULL[N]) < 1e-9
              and abs(d1[N]["IL_short_db"] - D1_IL_SHORT[N]) < 1e-9
              and abs(d1[N]["IL_var_io_db"] - D1_VAR_IO[N]) < 1e-9 for N in NS))

    # ==================================== G 结构性零自由度
    inv8 = deg_multiset_invariance(np.fft.fft(np.eye(8)).astype(complex) / math.sqrt(8))
    inv16 = deg_multiset_invariance(np.fft.fft(np.eye(16)).astype(complex) / math.sqrt(16))
    check("G1 🔴 deg 多集在 10 种合法变换下**完全不变**（N=8 与 N=16）",
          inv8["invariant"] is True and inv16["invariant"] is True,
          "N8=%s N16=%s" % (inv8["invariant"], inv16["invariant"]))
    check("G2 变体数 = 10，且多集 = {N/2, N/2, N…N}",
          inv8["n_variants"] == 10 and sorted(inv8["deg_multiset"]) == sorted(DEG[8])
          and sorted(inv16["deg_multiset"]) == sorted(DEG[16]))
    rep16 = loss_aware_compile_report(br[16], PDK, U=np.fft.fft(np.eye(16)).astype(complex) / 4.0)
    check("G3 🔴 report.compile_dof.real_dof_for_il_var == 0（编译层零自由度）",
          rep16["compile_dof"]["real_dof_for_il_var"] == 0
          and rep16["compile_dof"]["deg_multiset_invariant"] is True)
    check("G4 report 的 dp_consistent_with_deg 为 True（DP 与几何交叉核对）",
          rep16["dp_consistent_with_deg"] is True)

    # ============================================ H 变长列（双向）
    check("H1 变长列真实降 L_bus >= 4%（三 N）",
          all(vw[N]["L_bus_reduction_ratio"] >= 0.04 for N in NS),
          "got=%s" % {N: round(100.0 * vw[N]["L_bus_reduction_ratio"], 2) for N in NS})
    check("H2 🔴 变长列对 IL_var **零贡献**（tradeoff.il_var_identical True，三 N）",
          all(area_loss_tradeoff(br[N], PDK)["il_var_identical"] is True for N in NS))
    check("H3 变长列使 IL_mean **下降**（delta < 0，三 N）",
          all(abs(area_loss_tradeoff(br[N], PDK)["il_mean_delta_db"] - IL_MEAN_DELTA[N]) < 1e-9
              for N in NS),
          "got=%s" % {N: area_loss_tradeoff(br[N], PDK)["il_mean_delta_db"] for N in NS})
    check("H4 vw.affects_il_var is False 且 变长列总宽钉住（三 N）",
          all(vw[N]["affects_il_var"] is False
              and abs(vw[N]["width_varcol_um"] - VARCOL_WIDTH[N]) < 1e-6
              and abs(vw[N]["width_fixed_um"] - WIDTH_FIXED[N]) < 1e-6 for N in NS))

    # ====================================== I 既有口径漂移对照
    check("I1 gap = deg_mean * 0.3 * alpha_tap（三 N，机器化记录既有 1.3 漂移）",
          all(abs(mc[N]["gap_db"] - MANIFOLD_GAP[N]) < 1e-9 for N in NS),
          "got=%s" % {N: mc[N]["gap_db"] for N in NS})
    check("I2 D1 文档口径 > manifest 实现口径（更保守）",
          all(mc[N]["d1_doc_var_io_db"] > mc[N]["manifest_impl_var_io_db"] for N in NS))
    check("I3 默认采用 D1 文档口径（tap_switch_margin == 1.3）",
          abs(d1[8]["tap_switch_margin"] - D1_TAP_SWITCH_MARGIN) < 1e-12)

    # ========================================== J 保真度/DRC/LVS 不退化
    check("J1 版级保真度 = 1.0（三 N，机器精度）",
          all(abs(br[N]["fidelity"] - 1.0) < 1e-15
              and abs(br[N]["layout_fidelity"] - 1.0) < 1e-15 for N in NS))
    check("J2 DRC PASS（三 N）", all(br[N]["drc_pass"] is True for N in NS))
    check("J3 LVS ACCEPT（三 N）",
          all(br[N]["lvs_verdict"] == "ACCEPT" for N in NS),
          "got=%s" % {N: br[N]["lvs_verdict"] for N in NS})

    # ======================= K 独立重算 + 突变探针友好性（反向护栏）
    # 容差锁紧：任何伪造（哪怕改 1%）都会被立刻判红 —— 护栏证明自己会响。
    check("K1 🔴 独立重算 L_path（相对容差 1e-12）",
          all(abs(_ind_Lpath(n, geo[16]["L_bus_um"])
                  - path_length_um(n, geo[16]["L_bus_um"]))
              / max(path_length_um(n, geo[16]["L_bus_um"]), 1e-30) <= 1e-12
              for n in (geo[16]["deg_min"], geo[16]["deg_max"])))
    check("K2 🔴 独立重算 IL（相对容差 1e-12，含 il_db 与 il_per_port_direct_bus）",
          all(abs(_ind_il(n, geo[16]["L_bus_um"]) - il_db(n, geo[16]["L_bus_um"],
                                                          ALPHA_PROP_DEFAULT, ALPHA_TAP_DEFAULT))
              / max(il_db(n, geo[16]["L_bus_um"], ALPHA_PROP_DEFAULT, ALPHA_TAP_DEFAULT), 1e-30)
              <= 1e-12 for n in (geo[16]["deg_min"], geo[16]["deg_max"]))
          and abs(_ind_il(geo[8]["deg_max"], geo[8]["L_bus_um"])
                  - max(p["IL_db"] for p in ex[8]["per_port"])) < 1e-12)
    check("K3 🔴 独立重算 D1 var_io（三 N，相对容差 1e-12）",
          all(abs(_ind_d1_var_io(geo[N]["L_bus_um"], geo[N]["col_pitch_um"], geo[N]["deg_mean"])
                  - d1[N]["IL_var_io_db"]) / d1[N]["IL_var_io_db"] <= 1e-12 for N in NS))
    check("K4 🔴 独立重算变长列总宽（三 N，相对容差 1e-12）",
          all(abs(_ind_varcol_width(geo[N]["ops"]) - vw[N]["width_varcol_um"])
              / vw[N]["width_varcol_um"] <= 1e-12 for N in NS))
    check("K5 容差分级：L_bus 钉住用 1e-6（改 1e-5 µm 即红）· reduction 用 1e-8",
          abs(geo[16]["L_bus_um"] - L_BUS[16]) < 1e-6
          and abs(ov[16]["reduction_ratio"] - REDUCTION[16]) < 1e-8)
    check("K6 🔴 「零自由度」断言是**双向**的（若模块声称 real_dof>0 必红）",
          rep16["compile_dof"]["real_dof_for_il_var"] == 0
          and (rep16["compile_dof"]["real_dof_for_il_var"] > 0) is False)
    check("K7 🔴 「不可实现」断言是**双向**的（若把 IL_short 抬到 >= 物理最小必红）",
          all(rf[N]["short_path_infeasible"] is True for N in NS)
          and (rf[16]["IL_short_d1_db"] >= rf[16]["IL_min_physical_db"]) is False)

    total = PASS + FAIL
    print("-" * 74)
    print("loss_aware_compile smoke：%d PASS / %d FAIL / 共 %d 项" % (PASS, FAIL, total))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
