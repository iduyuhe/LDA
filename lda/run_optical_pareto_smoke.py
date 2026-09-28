# -*- coding: utf-8 -*-
"""P6 · T6.1 常驻门禁：光域 Pareto（MAC 吞吐 / 面积 / 光损耗 / 精度）· L2 系统级。

判据分组（A–K）
---------------
A 契约 / 披露（10 键齐全 + 关键立场字面出现 + 架构枚举）
B 表结构与算术（行数 · 吞吐 K·N² · 面积双架构 · ratio=1/K —— **全部独立重算**）
C 与 U1 交叉核验（用 U1 真函数比面积算术 —— **防「自己算算自己」的循环验证**）
D 物理单调性（N↑ ⇒ 面积↑、IL↑；**K 变 ⇒ 网格内 IL 严格不变**；deg_max 规律）
E Pareto 支配结构（独立重算支配关系 · front 非退化 · **front 不含 tiled** · 每个 tiled 被 shared 支配）
F 反向护栏（放宽损耗 / 收紧面积 ⇒ 面**必须移动**；两端极端行为正确）
G 能效守卫·**必 raise**（畸形反例：顶层键 / 嵌套键 / TOPS-W 键）
H 能效守卫·**合法必过**（空载荷 / 纯散文值 / 合法键 / 本模块全表）—— 铁律 8
I 输入域校验（N<2 / K<1 / arch 非法 ⇒ 必 raise；边界合法 ⇒ 必过）
J 结论钉死（面积落在窄带内 · IL 闭式独立重算一致 · front 恒等）
K 判据有效性自证（**注入伪造 tiled 面积 ⇒ E3 必红**，证明「front 不含 tiled」非恒真）

🔴 `make_check` 的真实签名是 **`check(name, cond, detail="")`（名字在前）** ——
本文件首版误写成 `check(cond, name, detail)` ⇒ `cond` 位收到**非空字符串**（恒真）
⇒ **35 条判据整体假绿**，靠 stdout 里的 `[PASS] False` 才发现。修正如本版。

🔴 立场：本 smoke 断言的是**事实**，包括**不利事实** ——
`E3`/`E4` 断言「在本三轴目标空间下**共享网格严格支配独立面**」、`D3` 断言「K 只买面积、
不买网格内 IL」、`H4` 断言「**零能效数字**」。若有人改成「独立面更优 / K 能降 IL /
补上 pJ/bit」，这些判据立刻变红。
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402
from lda_l2.optical_pareto import (  # noqa: E402
    ALPHA_PROP_DEFAULT,
    ALPHA_TAP_DEFAULT,
    ARCH_SHARED,
    ARCH_TILED,
    ARCHS,
    DEFAULT_KS,
    DEFAULT_NS,
    GAP_DEFAULT,
    OPTICAL_PARETO_DISCLOSURE,
    RAIL_PITCH_DEFAULT,
    OpticalParetoError,
    assert_no_energy_metrics,
    dominance_report,
    loss_relax_reverse_guard,
    optical_metrics,
    optical_pareto_table,
    pareto_front,
    u1_area_crosscheck,
)

PASS = 0
FAIL = 0
check = make_check(globals(), return_ok=True, detail_fmt="  —— {d}",
                   detail_on="fail")

N_TABLE = len(ARCHS) * len(DEFAULT_NS) * len(DEFAULT_KS)   # 2 × 4 × 5 = 40


def _raises(fn, exc=OpticalParetoError):
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


def main():  # noqa: C901
    print("=== P6 · T6.1 光域 Pareto 门禁 ===")

    t = optical_pareto_table(precision_bits=8.1328)

    # ---------------------------------------------------------------- A 契约
    print("--- A 契约 / 披露 ---")
    check("A1 披露 10 键齐全（防有人悄悄删掉诚实声明）",
          len(OPTICAL_PARETO_DISCLOSURE) == 10,
          "%d 键" % len(OPTICAL_PARETO_DISCLOSURE))
    blob = " ".join(OPTICAL_PARETO_DISCLOSURE.values())
    check("A2 披露含「不判决能效」与 pJ/bit 字面（红线可读）",
          "不判决能效" in blob and "pJ/bit" in blob)
    check("A3 架构枚举 == (shared, tiled)", tuple(ARCHS) == (ARCH_SHARED, ARCH_TILED),
          str(ARCHS))

    # ------------------------------------------------------------ B 结构算术
    print("--- B 表结构与算术（独立重算）---")
    check("B1 行数 == |archs|×|Ns|×|Ks|", t["n_rows"] == N_TABLE,
          "got %d want %d" % (t["n_rows"], N_TABLE))
    bad_tp = [r for r in t["rows"] if r["macs_per_pass"] != r["K"] * r["N"] * r["N"]]
    check("B2 吞吐 == K·N²（逐行独立重算）", not bad_tp, "违例 %d" % len(bad_tp))

    from lda_layout.mesh_pnr import build_mesh_pnr, dft_matrix
    plane = {}
    for N in DEFAULT_NS:
        plane[N] = float(build_mesh_pnr(dft_matrix(N), rail_pitch=RAIL_PITCH_DEFAULT,
                                        layout_mode="grid2d")["footprint_um2"])
    bad_area = []
    for r in t["rows"]:
        want = plane[r["N"]] * (1 if r["arch"] == ARCH_SHARED else r["K"])
        if abs(r["area_um2"] - want) > 1e-9 * max(1.0, want):
            bad_area.append((r["arch"], r["N"], r["K"], r["area_um2"], want))
    check("B3 面积 == 单面(shared) / K×单面(tiled)（独立重算）", not bad_area,
          "违例 %d %s" % (len(bad_area), bad_area[:2]))
    bad_ratio = [r for r in t["rows"]
                 if abs(r["area_ratio_vs_naive"] - 1.0 / r["K"]) > 1e-12]
    check("B4 area_ratio_vs_naive ≡ 1/K", not bad_ratio, "违例 %d" % len(bad_ratio))

    # ---------------------------------------------------------- C U1 交叉核验
    print("--- C U1 交叉核验（防「自己算自己」）---")
    xc = u1_area_crosscheck(N=16, K=4)
    check("C1 面积算术 ≡ U1 真函数（rel_err < 1e-12）",
          xc["consistent"] and xc["shared_rel_err"] < 1e-12
          and xc["tiled_rel_err"] < 1e-12,
          "shared=%.3e tiled=%.3e" % (xc["shared_rel_err"], xc["tiled_rel_err"]))
    check("C2 U1 area_ratio_vs_naive == 0.25（K=4）",
          abs(xc["u1_area_ratio_vs_naive"] - 0.25) < 1e-12,
          "%.6f" % xc["u1_area_ratio_vs_naive"])

    # ---------------------------------------------------------- D 物理单调性
    print("--- D 物理单调性 ---")
    sh = {N: [r for r in t["rows"]
              if r["arch"] == ARCH_SHARED and r["K"] == 1 and r["N"] == N][0]
          for N in DEFAULT_NS}
    area_seq = [sh[N]["area_um2"] for N in DEFAULT_NS]
    il_seq = [sh[N]["il_worst_db"] for N in DEFAULT_NS]
    check("D1 N↑ ⇒ 单面面积严格增",
          all(a < b for a, b in zip(area_seq, area_seq[1:])),
          str([round(a / 1e3, 2) for a in area_seq]))
    check("D2 N↑ ⇒ 网格内 IL 严格增",
          all(a < b for a, b in zip(il_seq, il_seq[1:])),
          str([round(a, 4) for a in il_seq]))
    by_nk = {}
    for r in t["rows"]:
        if r["arch"] == ARCH_SHARED:
            by_nk.setdefault(r["N"], set()).add(round(r["il_worst_db"], 12))
    check("D3 🔴 K 变化 ⇒ 网格内 IL **严格不变**（K 只买面积，不买 IL）",
          all(len(v) == 1 for v in by_nk.values()),
          str({k: sorted(v) for k, v in by_nk.items()}))
    # 实测事实：N>=4 时 deg_max == N；N=2 时 deg_max == 1（= N-1）
    expect_deg = {N: (1 if N == 2 else N) for N in DEFAULT_NS}
    check("D4 deg_max == N（N>=4）/ 1（N=2）—— grid2d 压实口径",
          all(sh[N]["deg_max"] == expect_deg[N] for N in DEFAULT_NS),
          str({N: sh[N]["deg_max"] for N in DEFAULT_NS}))

    # ------------------------------------------------------- E 支配结构（重算）
    print("--- E Pareto 支配结构 ---")
    rep = dominance_report(t["rows"])
    check("E1 front 非退化（自由度 ≠ 0）且如实报 note",
          rep["front_size"] >= 2 and not rep["degenerate_single_point"],
          "size=%d note=%s" % (rep["front_size"], rep["freedom_note"][:70]))
    front = rep["front_rows"]

    def _dom(a, b):  # 独立重算支配（不 import 模块私有 _dominates）
        return (a["macs_per_pass"] >= b["macs_per_pass"]
                and a["area_um2"] <= b["area_um2"]
                and a["il_worst_db"] <= b["il_worst_db"]
                and (a["macs_per_pass"] > b["macs_per_pass"]
                     or a["area_um2"] < b["area_um2"]
                     or a["il_worst_db"] < b["il_worst_db"]))

    not_dom = [r for r in front if any(_dom(o, r) for o in t["rows"] if o is not r)]
    check("E2 front 每点均**非支配**（独立重算支配关系）",
          not not_dom, "被支配 %d" % len(not_dom))
    check("E3 🔴 front **不含 tiled**（三轴下共享网格严格优）",
          all(r["arch"] == ARCH_SHARED for r in front),
          str(sorted({r["arch"] for r in front})))
    tiled_rows = [r for r in t["rows"] if r["arch"] == ARCH_TILED]
    undom_tiled = [r for r in tiled_rows
                   if not any(_dom(o, r) for o in t["rows"] if o is not r)]
    check("E4 每个 tiled 点都被某个 shared 点支配", not undom_tiled,
          "未被支配的 tiled = %s" % [(r["N"], r["K"]) for r in undom_tiled][:3])

    # --------------------------------------------------------- F 反向护栏
    print("--- F 反向护栏（面必须移动）---")
    g1 = loss_relax_reverse_guard()
    check("F1 放宽损耗上限 ⇒ front **必须移动**",
          g1["moved"] and g1["n_kept_tight"] < g1["n_kept_relaxed"],
          "tight=%d → relaxed=%d moved=%s"
          % (g1["n_kept_tight"], g1["n_kept_relaxed"], g1["moved"]))
    f_base = pareto_front(t["rows"])
    f_tight = pareto_front(t["rows"], area_max_um2=0.001)
    f_loose = pareto_front(t["rows"], area_max_um2=1e12)
    key = lambda rs: [(r["arch"], r["N"], r["K"]) for r in rs]      # noqa: E731
    check("F2 收紧面积上限 ⇒ front 必须移动", key(f_tight) != key(f_base),
          "tight=%d base=%d" % (len(f_tight), len(f_base)))
    check("F3 两端极端行为正确（全剔除 ⇒ 空；极宽 ⇒ 与无约束 front 逐点相同）",
          len(pareto_front(t["rows"], area_max_um2=1e-9)) == 0
          and key(f_loose) == key(f_base),
          "empty=%d loose=%d base=%d"
          % (len(pareto_front(t["rows"], area_max_um2=1e-9)), len(f_loose), len(f_base)))

    # ------------------------------------------------- G 能效守卫 · 必 raise
    print("--- G 能效守卫（必 raise）---")
    check("G1 顶层键 pj_per_bit ⇒ 必 raise",
          _raises(lambda: assert_no_energy_metrics({"pj_per_bit": 3.0})))
    check("G2 嵌套（list→dict）深层能效键 ⇒ 必 raise",
          _raises(lambda: assert_no_energy_metrics({"a": [{"b": {"energy_per_mac": 1}}]})))
    check("G3 键含 TOPS/W ⇒ 必 raise",
          _raises(lambda: assert_no_energy_metrics({"x": {"TOPS/W": 12}})))

    # --------------------------------------------- H 能效守卫 · 合法必过（铁律 8）
    print("--- H 能效守卫（合法必过）---")
    check("H1 空载荷 ⇒ 必过", not _raises(lambda: assert_no_energy_metrics({})))
    check("H2 纯散文载荷（**值**里含 pJ/bit）⇒ 必过（只扫键不扫值）",
          not _raises(lambda: assert_no_energy_metrics(
              {"note": "本模块不判决能效 pJ/bit（电域主导）"})))
    check("H3 合法键载荷 ⇒ 必过",
          not _raises(lambda: assert_no_energy_metrics(
              {"macs_per_pass": 16, "area_um2": 1.0, "il_worst_db": 0.2})))
    check("H4 🔴 本模块**全表**零能效键名（零能效数字，机器可查）",
          not _raises(lambda: assert_no_energy_metrics(t)))

    # -------------------------------------------------------------- I 输入域
    print("--- I 输入域校验 ---")
    check("I1 N<2 ⇒ 必 raise", _raises(lambda: optical_metrics(1, 4)))
    check("I2 K<1 ⇒ 必 raise", _raises(lambda: optical_metrics(4, 0)))
    check("I3 arch 非法 ⇒ 必 raise",
          _raises(lambda: optical_metrics(4, 4, arch="mesh")))
    check("I4 边界合法（N=2,K=1）⇒ 必过", not _raises(lambda: optical_metrics(2, 1)))

    # ------------------------------------------------------------ J 结论钉死
    print("--- J 结论钉死 ---")
    a16 = plane[16]
    check("J1 N=16 单面面积落在 35k–37k µm² 窄带（**默认布局是 7.1× ⇒ 会立刻越界**）",
          35000.0 < a16 < 37000.0, "%.3f µm²" % a16)
    il16 = sh[16]["il_worst_db"]
    want16 = (ALPHA_PROP_DEFAULT
              * (sh[16]["L_bus_um"] + 16 * (RAIL_PITCH_DEFAULT - GAP_DEFAULT)) / 1e4
              + 16 * ALPHA_TAP_DEFAULT)
    check("J2 N=16 IL ≡ 闭式独立重算（α_prop·L/1e4 + n_tap·α_tap）",
          abs(il16 - want16) < 1e-9, "%.12f vs %.12f" % (il16, want16))
    want_front = [(ARCH_SHARED, 2, 16), (ARCH_SHARED, 4, 16),
                  (ARCH_SHARED, 8, 16), (ARCH_SHARED, 16, 16)]
    check("J3 front 恒等（K=16 全档 + N 四档）", rep["front"] == want_front,
          str(rep["front"]))

    # --------------------------------------------------- K 判据有效性自证
    print("--- K 判据有效性自证 ---")
    fake = [dict(r) for r in t["rows"]]
    for r in fake:              # 把 tiled 伪造成「面积 = 单面」（假装独立面不花钱）
        if r["arch"] == ARCH_TILED:
            r["area_um2"] = plane[r["N"]]
    fp = pareto_front(fake)
    check("K1 注入伪造 tiled 面积 ⇒ E3 的判据**必红**（证明「front 不含 tiled」非恒真）",
          any(r["arch"] == ARCH_TILED for r in fp),
          "伪造后 front 架构 = %s" % sorted({r["arch"] for r in fp}))

    print("=" * 74)
    print("P6 · T6.1 光域 Pareto：%d PASS / %d FAIL" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
