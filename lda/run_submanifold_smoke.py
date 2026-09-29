#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""D-127 · 「非通用但浅」的可编程子流形设计 · 门禁 smoke。

把 D-121 的「可编程性前沿 = 参数计数 ⌊N/2⌋·D」升级为**机器实测的可及自由度**：
在深度预算 D 下，求**最大化可达子流形维数**（雅可比秩）的层序列设计。

判据分组（A–G）：
  A 词汇/契约（层原语 · 匹配判定正反向 · 枚举计数 · 参数/上界闭式 · 披露）
  B 可及自由度实测（dim ≤ 上界 · 砖墙达上界 · 🔴 O-only 饱和 2N · 门多≠自由度高 · 空序列 · 层内对易）
  C 设计最优性（N=4 全穷举 · N=6 beam 反证 · O-heavy 对照 · 随机基线 · 契约护栏）
  D 通用前沿（D* = N · dim(D*−1) < N² · 单调 · 与 D-121 紧界/门数一致）
  E 跨模块层一致性（`rect_mesh` 自己的 Clements 层 ⇒ 匹配 + dim = N²；`temporal_mesh` 判定一致）
  F 诚实边界 + 红线（实测秩稳定 · 披露齐备 · 零 SDK · 判决全死标量 · ★反面★非恒真）
  G 报告一体化（`dof_curve` / `saturation_witness` 自洽）

🔴 立场：断言**事实**，包括不利事实 ——
   B3/B4 断言「O-only 门数更多却 dim 恒为 2N」（D-121 §2b 的定量版）；
   F2 断言「最优性证据**只在已搜索空间**」（不宣称全局证明）。

🔴 抗突变致病态：**全部实测集中在 `_collect()` 一处、经 `_safe()` 收口** ⇒
   任一突变把测量打成异常时，相关判据**具名 [FAIL]**，而不是崩成 exit=99（D-124/D-126 血案）。
运行：python lda/run_submanifold_smoke.py
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import numpy as np  # noqa: E402

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_l2 import mzi_mesh_matmul as MMM              # noqa: E402
from lda_qeda import rect_mesh as RM                   # noqa: E402
from lda_qeda import submanifold as SM                 # noqa: E402
from lda_qeda import temporal_mesh as TM               # noqa: E402

PASS = 0
FAIL = 0
check = make_check(globals(), return_ok=True,
                   detail_fmt="  —— {d}", detail_on="fail")

NS = (4, 6, 8)
_BANNED = ("qiskit", "cirq", "pennylane", "strawberryfields", "thewalrus", "qutip")
_EXC = "测量异常（突变致病态）"


def _raises(fn):
    try:
        fn()
    except Exception:
        return True
    return False


def _safe(fn, default=None):
    try:
        return True, fn()
    except Exception:                                       # noqa: BLE001
        return False, default


def _rect_layers(n):
    """平台主权矩形网格的**匹配图案**（用于跨模块核对）。"""
    layers, _D = RM.rectangular_mesh_layers(MMM.dft_matrix(n))
    return tuple(tuple(sorted((int(j), int(j) + 1) for (j, _t, _p) in L)) for L in layers)


def _collect(ns):
    """一次性收集全部实测表（B/D/E/F 节共用；异常由调用方 `_safe` 收口）。"""
    out = {}
    for n in ns:
        rp = _rect_layers(n)
        out[n] = {
            "bw": [SM.reachable_dim_report(n, SM.brick_wall_layers(n, d), n_samples=1)
                   for d in range(0, n + 1)],
            "oo": [SM.reachable_dim_report(n, SM.o_only_layers(n, d), n_samples=1)
                   for d in range(0, n + 1)],
            "wit": SM.saturation_witness(n, 3),
            "fr": SM.universality_frontier(n, d_max=n + 1, n_samples=1),
            "rect": rp,
            "rect_dim": SM.reachable_dim(n, rp, n_samples=1),
            "bw_sizes": [SM.layer_gate_count(L) for L in SM.brick_wall_layers(n, n)],
            "rect_sizes": [SM.layer_gate_count(p) for p in rp],
            "seed_set": sorted({SM.reachable_dim(n, SM.brick_wall_layers(n, 5), seed=s)
                                for s in (0, 1, 2)}),
            "o3": SM.reachable_dim(n, SM.o_only_layers(n, 3), n_samples=1),
            "bw3": SM.reachable_dim(n, SM.brick_wall_layers(n, 3), n_samples=1),
        }
    return out


def _oheavy(ns):
    """O-heavy 变体：尽量多用最大匹配 O，其余用次大匹配（N=6/8，D=4/5，全部 r）。"""
    res = {}
    for n in ns:
        second = SM.path_matchings(n)[1]
        for d in (4, 5):
            bw = SM.reachable_dim(n, SM.brick_wall_layers(n, d), n_samples=1)
            for r in range(d + 1):
                seq = tuple([SM.odd_pairs(n)] * r + [second] * (d - r))
                res[(n, d, r)] = (SM.reachable_dim(n, seq, n_samples=1), bw)
    return res


def _types_ok():
    r = SM.reachable_dim_report(4, SM.brick_wall_layers(4, 4), n_samples=1)
    return all(isinstance(r[k], int) for k in ("dim", "saturation_bound", "n_gates",
                                               "param_count", "universal_dim", "depth"))


def _order_ok():
    n, ga, gb, psi = 4, (0.3, 0.7), (1.1, 2.0), (0.2, 0.4, 0.6, 0.8)
    xa = np.array([ga[0], ga[1], gb[0], gb[1], psi[0], psi[1], psi[2], psi[3]])
    xb = np.array([gb[0], gb[1], ga[0], ga[1], psi[0], psi[1], psi[2], psi[3]])
    Ua = SM.build_submanifold_unitary(n, (((0, 1), (2, 3)),), xa)
    Ub = SM.build_submanifold_unitary(n, (((2, 3), (0, 1)),), xb)
    return bool(np.max(np.abs(Ua - Ub)) < 1e-12)


def _matching_agree(ns):
    ok = True
    for n in ns:
        for pat in (SM.odd_pairs(n), SM.even_pairs(n), ((0, 1), (1, 2)), ((0, 1), (3, 4))):
            g = [(j, 0.0, 0.0, False) for (j, _q) in pat]
            ok = ok and (TM.gate_matching_ok(g, n) == SM.layer_is_matching(n, pat))
    return ok


def main() -> int:
    print("=" * 80)
    print("D-127 「非通用但浅」的可编程子流形设计 · 可及自由度 = 雅可比秩")
    print("=" * 80)

    ok_tab, TAB = _safe(lambda: _collect(NS))
    T = TAB if ok_tab else {}

    # ---------------------------------------------------------------- A 词汇/契约
    print("--- A 词汇/契约（层原语 · 匹配 · 闭式）---")
    ok_self, self_ok = _safe(lambda: SM.run_selfchecks(verbose=False), False)
    check("A1 `lda_qeda.submanifold` 模块自检 13/13 PASS", ok_self and self_ok is True,
          "层/门数/参数/上界/实测秩/饱和见证/前沿/护栏/披露")

    ok_a2, a2 = _safe(lambda: (
        SM.layer_gate_count(SM.odd_pairs(4)) == 2
        and SM.layer_gate_count(SM.even_pairs(4)) == 1
        and SM.layer_is_matching(4, SM.odd_pairs(4)) is True
        and SM.layer_is_matching(4, ((0, 1), (1, 2))) is False
        and SM.layer_is_matching(4, ((0, 1), (3, 4))) is False))
    check("A2 层原语 + 匹配判定正反向：非匹配（共享模）与越界均 False", ok_a2 and a2)

    ok_a3, a3 = _safe(lambda: (len(SM.path_matchings(4)), len(SM.path_matchings(6)),
                              len(SM.path_matchings(8))))
    check("A3 P_N 匹配枚举计数：N=4 ⇒ 5 · N=6 ⇒ 13 · N=8 ⇒ 34（含空层）",
          ok_a3 and a3 == (5, 13, 34), "N=4/6/8 = %s" % (a3,))

    ok_a4, a4 = _safe(lambda: (
        SM.param_count(8, SM.brick_wall_layers(8, 8)) == 64
        and SM.brick_wall_gate_count(8, 8) == 28
        and SM.saturation_bound(8, SM.brick_wall_layers(8, 8)) == 64
        and all(SM.brick_wall_gate_count(n, d) == SM.n_gates(SM.brick_wall_layers(n, d))
                for n in NS for d in range(10))))
    check("A4 参数/上界闭式：P = 2g+N · 上界 = min(2g+N, N²)（N=8,D=8：g=28,P=64,ub=64）",
          ok_a4 and a4)

    check("A5 披露 ≥9 条且含 dim_is_measured/search_is_bounded/kinematics_only/even_n_note/no_llm",
          len(SM.SUBMANIFOLD_DISCLOSURE) >= 9
          and all(isinstance(v, str) and v.strip() for v in SM.SUBMANIFOLD_DISCLOSURE.values())
          and all(k in SM.SUBMANIFOLD_DISCLOSURE for k in
                  ("dim_is_measured", "search_is_bounded", "kinematics_only",
                   "even_n_note", "no_llm")),
          "keys=%d" % len(SM.SUBMANIFOLD_DISCLOSURE))

    # ---------------------------------------------------------------- B 实测自由度
    print("--- B 可及自由度实测（dim = 雅可比秩）---")
    b1_ok = b2_ok = b3_ok = ok_tab
    b2_det, b3_det = {}, {}
    for n in NS:
        t = T.get(n, {})
        if not t:
            continue
        for r in (t.get("bw") or []) + (t.get("oo") or []):
            b1_ok = b1_ok and r["dim"] <= r["saturation_bound"]
        b2_ok = b2_ok and all(r["dim"] == r["saturation_bound"] for r in (t.get("bw") or []))
        b3_ok = b3_ok and all(r["dim"] == 2 * n for r in (t.get("oo") or [])[1:])
        b2_det[n] = [r["dim"] for r in (t.get("bw") or [])]
        b3_det[n] = t.get("oo", [{}])[3]["dim"] if len(t.get("oo") or []) > 3 else None
    check("B1 dim ≤ 上界 min(2g+N, N²)（砖墙与 O-only 逐 N 逐 D）", b1_ok, "" if ok_tab else _EXC)
    check("B2 ★砖墙逐点达上界★ dim ≡ min(2·g_bw + N, N²)（N=4/6/8，D=0..N）",
          b2_ok, ("逐档 dim=%s" % b2_det) if ok_tab else _EXC)
    check("B3 🔴 O-only **饱和**：dim ≡ 2N（与 D 无关；块对角 ⇒ 可达集 = (U(2))^{N/2}）",
          b3_ok, ("逐 N dim(D=3)=%s（应为 2N）" % b3_det) if ok_tab else _EXC)

    check("B4 ★门多 ≠ 自由度高★ 存在 D 使 O-only 门数更多而 dim 更小（逐 N 见证）",
          ok_tab and all(T[n]["wit"]["deltas"]["o_dim_is_2N"]
                         and T[n]["wit"]["deltas"]["dim_gain_bw_over_o"] > 0
                         and T[n]["wit"]["o_only"]["n_gates"] > T[n]["wit"]["brick_wall"]["n_gates"]
                         for n in NS),
          ("D=3 逐 N 增益=%s" % {n: T[n]["wit"]["deltas"]["dim_gain_bw_over_o"] for n in NS})
          if ok_tab else _EXC)

    ok_b5, b5 = _safe(lambda: (SM.reachable_dim(4, tuple()), SM.reachable_dim(4, ((),)),
                              SM.reachable_dim(6, tuple())))
    check("B5 空序列（无门）⇒ dim = N（可达集只有相移屏 · 零门仍有 N 维）",
          ok_b5 and b5 == (4, 4, 6), "N=4/4/6 ⇒ %s" % (b5,))

    ok_b6, b6 = _safe(_order_ok)
    check("B6 层内对易：同层两不相交门**交换顺序**（参数跟对走）⇒ 传递矩阵逐位相同",
          ok_b6 and b6 is True)

    # ---------------------------------------------------------------- C 设计最优性
    print("--- C 设计最优性（穷举 / beam / 对照）---")
    ok_c1, EX = _safe(lambda: {d: SM.design_shallow(4, d, method="exhaustive",
                                                    max_exhaustive=4000, n_samples=1)
                               for d in (1, 2, 3, 4)})
    check("C1 ★真·最优★ N=4 穷举全部匹配序列（D=1..4）⇒ **无序列优于砖墙**且最佳 = 上界",
          ok_c1 and all(EX[d]["beats_brick_wall"] is False
                        and EX[d]["best_dim"] == EX[d]["brick_wall"]["dim"]
                        and EX[d]["best_dim"] == EX[d]["best_bound"] for d in EX),
          ("逐 D 组合数=%s" % {d: EX[d]["combinations"] for d in EX}) if ok_c1 else _EXC)

    ok_c2, BM = _safe(lambda: {d: SM.design_shallow(6, d, method="beam", beam_width=4,
                                                   n_samples=1) for d in (2, 3, 4)})
    check("C2 beam(4) 反证：N=6 / D=2..4 最佳已知 ≤ 砖墙（beats=False）",
          ok_c2 and all(BM[d]["beats_brick_wall"] is False for d in BM),
          ("逐 D beam dim=%s vs 砖墙=%s" % ({d: BM[d]["best_dim"] for d in BM},
                                           {d: BM[d]["brick_wall"]["dim"] for d in BM}))
          if ok_c2 else _EXC)

    ok_c3, OH = _safe(lambda: _oheavy((6, 8)))
    check("C3 O-heavy 变体（多用最大匹配 O）⇒ dim 不超砖墙（N=6/8，D=4/5，全部 r）",
          ok_c3 and all(v[0] <= v[1] for v in OH.values()),
          ("共 %d 个变体" % len(OH)) if ok_c3 else _EXC)

    ok_c4, RD = _safe(lambda: {n: SM.design_shallow(n, 5, method="random", n_trials=40,
                                                   seed=n, n_samples=1) for n in (6, 8)})
    check("C4 随机层序列基线（40 次）⇒ 最佳 ≤ 砖墙（设计有意义，非碰巧）",
          ok_c4 and all(RD[n]["beats_brick_wall"] is False for n in RD),
          ("逐 N (随机,砖墙)=%s" % {n: (RD[n]["best_dim"], RD[n]["brick_wall"]["dim"])
                                   for n in RD}) if ok_c4 else _EXC)

    check("C5 契约护栏：method 非法 ⇒ raise · exhaustive 超组合上限 ⇒ raise",
          _raises(lambda: SM.design_shallow(4, 1, method="zzz"))
          and _raises(lambda: SM.design_shallow(8, 6, method="exhaustive", max_exhaustive=10)))

    # ---------------------------------------------------------------- D 通用前沿
    print("--- D 通用前沿（D* = N）---")
    check("D1 ★前沿★ D* = N（N=4/6/8 逐点）",
          ok_tab and all(T[n]["fr"]["d_star"] == n for n in NS),
          ("逐 N D*=%s" % {n: T[n]["fr"]["d_star"] for n in NS}) if ok_tab else _EXC)
    check("D2 dim(D*) = N² 且 dim(D*−1) < N²（⇒ **参数界 N−1 不可达**）",
          ok_tab and all(T[n]["fr"]["dim_by_depth"][n] == n * n
                         and T[n]["fr"]["dim_at_d_star_minus_1"] < n * n for n in NS),
          ("逐 N dim(D*−1)=%s" % {n: T[n]["fr"]["dim_at_d_star_minus_1"] for n in NS})
          if ok_tab else _EXC)
    check("D3 砖墙 dim 随 D **非减**（逐 N 单调）",
          ok_tab and all(all(T[n]["fr"]["dim_by_depth"][d] <= T[n]["fr"]["dim_by_depth"][d + 1]
                             for d in range(len(T[n]["fr"]["dim_by_depth"]) - 1)) for n in NS))
    ok_d4, d4 = _safe(lambda: {n: (TM.tight_depth_lower_bound(n), T[n]["fr"]["d_star"])
                               for n in NS})
    check("D4 与 D-121 **紧界**一致：`tight_depth_lower_bound(N)` == D*（逐 N）",
          ok_tab and ok_d4 and all(v[0] == v[1] for v in d4.values()),
          ("逐 N (TM,本模块)=%s" % d4) if ok_d4 else _EXC)
    ok_d5, d5 = _safe(lambda: {n: (TM.universality_gate_count(n),
                                   SM.brick_wall_gate_count(n, n)) for n in NS})
    check("D5 与 D-121 **门数**一致：`universality_gate_count` == 砖墙 g(N,N) == N(N−1)/2",
          ok_d5 and all(v[0] == v[1] and v[0] == n * (n - 1) // 2 for n, v in d5.items()),
          ("逐 N=%s" % {n: v[0] for n, v in d5.items()}) if ok_d5 else _EXC)

    # ---------------------------------------------------------------- E 跨模块层一致
    print("--- E 跨模块层一致性（rect_mesh / temporal_mesh）---")
    check("E1 `rect_mesh.rectangular_mesh_layers` 的层数 ≡ N（= D*）且逐层均为**匹配**",
          ok_tab and all(len(T[n]["rect"]) == n
                         and all(SM.layer_is_matching(n, p) for p in T[n]["rect"]) for n in NS),
          ("逐 N 层数=%s" % {n: len(T[n]["rect"]) for n in NS}) if ok_tab else _EXC)
    check("E2 ★平台自己的 Clements 层 ⇒ dim = N²★（主权分解的匹配图案喂给实测秩）",
          ok_tab and all(T[n]["rect_dim"] == n * n for n in NS),
          ("逐 N dim=%s" % {n: T[n]["rect_dim"] for n in NS}) if ok_tab else _EXC)
    check("E3 ★砖墙 ≡ 平台 Clements 层尺寸序★（逐层门数 [N/2, N/2−1, …] 逐位一致）",
          ok_tab and all(T[n]["rect_sizes"] == T[n]["bw_sizes"] for n in NS),
          ("逐 N 尺寸序=%s" % {n: T[n]["rect_sizes"] for n in NS}) if ok_tab else _EXC)
    ok_e4, e4 = _safe(lambda: (_matching_agree(NS),
                              all(TM.adjacency_max_matching(n)["max_matching_size"]
                                  == len(SM.odd_pairs(n))
                                  and TM.adjacency_max_matching(n)["unique_max_matching"] is True
                                  for n in NS)))
    check("E4 `temporal_mesh.gate_matching_ok` 与 `layer_is_matching` **判定一致**"
          "（含反例）· 且 |O| == 最大匹配尺寸", ok_e4 and e4[0] and e4[1])

    # ---------------------------------------------------------------- F 诚实 + 红线
    print("--- F 诚实边界 + 红线 ---")
    check("F1 实测秩**对随机种子稳定**（每 N 三 seed 同值 ⇒ 秩是一般性质，非偶然）",
          ok_tab and all(len(T[n]["seed_set"]) == 1 for n in NS),
          ("逐 N 取值集=%s" % {n: T[n]["seed_set"] for n in NS}) if ok_tab else _EXC)
    _disc = SM.SUBMANIFOLD_DISCLOSURE
    check("F2 诚实：`search_is_bounded` 明标「只在 N≤8/D≤6 搜索、不宣称全局最优」+"
          "`kinematics_only` 不含损耗/噪声 + `dim_is_measured` 明标实测",
          "N ≤ 8" in _disc.get("search_is_bounded", "")
          and "不含" in _disc.get("kinematics_only", "")
          and "实测" in _disc.get("dim_is_measured", ""))
    ok_src, _src = _safe(lambda: open(os.path.join(_HERE, "lda_qeda", "submanifold.py"),
                                      encoding="utf-8").read(), "")
    ok_ty, ty = _safe(_types_ok)
    check("F3 红线：零量子 SDK 令牌 · 判决全为 int/float/bool（死标量）",
          ok_src and not any(b in _src.lower() for b in _BANNED) and ok_ty and ty is True)
    ok_f4, f4 = _safe(lambda: (
        isinstance(SM.saturation_bound(6, SM.brick_wall_layers(6, 3)), int)
        and isinstance(SM.reachable_dim(6, SM.brick_wall_layers(6, 3), n_samples=1), int)
        and isinstance(SM.reachable_dim_report(
            6, SM.brick_wall_layers(6, 6), n_samples=1)["universal"], bool)))
    check("F4 上界/秩/通用位均为死标量（int · bool），无字符串判决", ok_f4 and f4)
    check("F5 ★反面★ 判据非恒真：D=3 时 O-only 与砖墙 dim **严格不同**"
          "（8 vs 14 / 12 vs 22 / 16 vs 30）",
          ok_tab and all(T[n]["o3"] < T[n]["bw3"] for n in NS),
          ("逐 N (O,砖墙)=%s" % {n: (T[n]["o3"], T[n]["bw3"]) for n in NS})
          if ok_tab else _EXC)

    # ---------------------------------------------------------------- G 报告一体化
    print("--- G 报告一体化 ---")
    ok_g1, CUR = _safe(lambda: SM.dof_curve(6, n_samples=1))
    check("G1 `dof_curve` 逐行自洽：dim ≤ 上界 · universal ⟺ dim == N²",
          ok_g1 and len(CUR["rows"]) == 7
          and all(r["bw_dim"] <= r["bw_bound"]
                  and (r["bw_universal"] == (r["bw_dim"] == 36)) for r in CUR["rows"]))
    ok_g2, SW = _safe(lambda: SM.saturation_witness(8, 5, n_samples=1))
    check("G2 `saturation_witness` 自洽：O-only dim = 2N · 砖墙增益 > 0 · 门数比 > 1",
          ok_g2 and SW["deltas"]["o_dim_is_2N"] and SW["deltas"]["dim_gain_bw_over_o"] > 0
          and SW["deltas"]["gate_count_ratio_o_over_bw"] > 1.0
          and "门多 ≠ 自由度高" in SW["verdict"])

    print()
    print("=" * 80)
    print("D-127 可编程子流形门禁 smoke：%d PASS / %d FAIL / 共 %d 项" % (PASS, FAIL, PASS + FAIL))
    print("=" * 80)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
