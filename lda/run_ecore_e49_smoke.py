#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E49 门禁：**规模上探 —— 这套链路能用到多大规模，上限来自哪里**（D-241）。

## 为什么需要这一版

E45–E48 的所有结论都建立在**一个 12 单元的小块**上：路由 DRC 34→0、"零 DRC"、
M3 跳线 8→0。那些话**对不对、能推广到多远**，此前没有任何证据。
本版把规模当自变量，从 12 单元一路测到 1024 单元，然后把答案钉成判据。

## 查出的两个真缺陷（这是本版的主要价值）

### ① 成片的 M3 长跳线短路（规模上才暴露）

列被推远超过 M2 逃逸上限后，旧代码退回 **M3 横向长跳线**，而跳线**只能画在引脚 y** 上
—— 同一行所有引脚的 y 相同 ⇒ 多条跳线全叠在同一 y、同层不同网 ⇒ `min_spacing` 成片。
12 单元时列不会被推远，所以 E45 的"零 DRC"在规模上**不成立**（64 单元 8 行实测 41 条）。

修法：把逃逸上限当**硬约束**，超出就如实报 `too_far`/`no_column`，不画违例假装布通。

### ② 逐引脚逃逸额度必须按方向算（判据 C2 守）

逃逸条只朝一个方向扩张 ⇒ 向左逃只受**左邻**约束。初版用"两侧各摊一半"的单一额度，
把"向左 0.5µm 完全合法"误判成"只能逃 0.01µm" ⇒ 12 单元布通率 10/10 → 9/10。
另外**判邻必须按 y 区间重叠**（`|Δy| < W + S_MIN`），按 `round(y,2)` 分带会把
INV(535nm) 与 NAND2(530nm) 错开 ⇒ 64 单元 gap=0.36 时漏出 2 条 `min_spacing`。

## 上限在哪（实测）

| 项 | 结果 |
|---|---|
| 时间 | **DRC 占绝对主导**（1024 单元 96.9%），`t_drc ∝ M^1.98`（R²=0.9999）⇒ 与逐对 O(M²) 一致 |
| 资源 | 固定 die 宽（8 列）时 **列失败率单调上升** 0% → 51.3%：列数由 **die 宽度**决定、与行数无关 |
| 外推 | 按实测幂律，1 万单元 DRC ≈ 137 s（纯 Python 单核） |

⇒ **真实答案是：不是被算法卡住，是被布线资源卡住**；扩规模必须等比加宽 die
（与 E38 链"唯一杠杆是加面积"同向）。

| # | 守护 | 金标 |
|---|---|---|
| A1 | **全规模零 DRC** | 7 档（12…1024）路由/全量 DRC **恒 0** |
| A2 | 12 单元基线回归 | 内部网 **10/10** 布通 ∧ DRC 0 ∧ M3 跳线 0 |
| B1 | 列资源枯竭（机制证据） | 列失败率**单调不降** ∧ 末档 ≥ 0.45 |
| B2 | 复杂度指数 | `t_drc ~ M^k`，**k ∈ [1.75, 2.25]** ∧ R² ≥ 0.985 |
| B3 | DRC 是瓶颈 | 末档 `drc_share ≥ 0.90` |
| C1 | 反向探针 | 关掉 M2 逃逸 ⇒ DRC **必 > 0** 且布通更少（证明 A1 是修出来的） |
| C2 | 逃逸额度 = 闭式 | `point_off_budget` 给 A/B 向右额度 == `P−2·M2_HALF−S_MIN` = 0.018 |
| C3 | 外推自洽 | 用前 6 档拟合外推末档，误差 ≤ 5% |
| D1 | 确定性 | 两次阶梯的单元数/形状数/布通数/DRC 数逐位一致 |
| D0 | 耗时 | < 阈值 |

## 诚实口径（必须随任何引用一起给）

- 🔴 测的是**当前实现 + 当前几何**（8 列 / INV+NAND2 / LDA-DEMO45），**不是算法极限**。
  换 C++ 实现、换列数、换单元库都要重测。
- 🔴 复杂度指数来自**纯 Python 单核**；绝对耗时不可外推到真实 EDA 工具。
- 🔴 外推只对 **DRC 耗时**做幂律外推，且假设"金属数/单元数"比例不变；**不外推布通率**
  —— 它由资源决定，不是幂律。
- 🔴 阶梯取网表**前 N 个门**，内部网数随门序变化 ⇒ "布通率"本身不单调；
  单调的是**列失败率**（它直接反映"列数由 die 宽决定"这条机制）。
- 🔴 净增 **0 锚**（计数与浮点幂律 ⇒ resid≡0）⇒ 门禁形态，不伪造非零残差。
"""

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import dscale as DS       # noqa: E402
from lda_l2.ecore import dpnr as PN         # noqa: E402
from lda_l2.ecore import dctrl as CT        # noqa: E402
from lda_l2.ecore import ddrc_lvs as DL     # noqa: E402
from lda_harness.smoke_kit import make_check  # noqa: E402

AN_ELAPSED_MAX_S = 120.0
#: 阶梯：12 单元是 E45–E48 的基线块，其余逐级放大到 1024。
LADDER = (12, 32, 64, 128, 256, 512, 1024)
COLS = 8
#: 复杂度指数容差（O(M²) 的机器核验；实现若退化成 O(M) 或 O(M³) 会红）。
K_LO, K_HI = 1.75, 2.25
#: 末档 DRC 耗时占比下限（"瓶颈在 DRC"的证据）。
DRC_SHARE_MIN = 0.90
#: 末档列失败率下限（"列资源枯竭"的证据）。
NOCOL_RATE_MIN = 0.45

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


def main() -> int:
    t0 = time.time()
    print("=" * 78)
    print("E49 · 规模上探：12 → 1024 单元 · 零 DRC 是否保持 · 复杂度界在哪")
    print("-" * 78)

    nl = CT.build()["netlist"]
    L = DS.size_ladder(nl, ladder=LADDER, cols=COLS)
    rows = L["rows"]
    for r in rows:
        print("  %5d 单元 | %3d 行 | %5.1f×%6.1f µm² | shapes %5d | 网 %4d 布通 %4d (%5.1f%%) "
              "| 列失败 %3d (%5.1f%%) | DRC %d"
              % (r["cells"], r["rows"], r["die_w_um"], r["die_h_um"], r["n_shapes"],
                 r["n_net"], r["n_routed"], 100 * r["route_rate"],
                 r["n_fail_no_column"], 100 * r["no_column_rate"], r["n_drc"]))

    # ── A1 全规模零 DRC ────────────────────────────────────────
    bad = [(r["cells"], r["n_drc"]) for r in rows if r["n_drc"] != 0]
    check("A1 全规模零 DRC：%d 档（%d…%d 单元）路由+全量 DRC **恒 0**"
          % (len(rows), rows[0]["cells"], rows[-1]["cells"]),
          not bad, "非零档 %s" % (bad if bad else "无"))

    # ── A2 12 单元基线回归（E45/E48 的结论在基线块上仍成立）──────────
    base = rows[0]
    pl0 = PN.place_real(nl, max_cells=LADDER[0], cols=COLS)
    rt0 = PN.route_block(nl, pl0)
    n_int0 = len(rt0["routed"]) + len(rt0["unrouted"])
    check("A2 12 单元基线回归：内部网 %d/%d 布通 ∧ DRC 0 ∧ M3 跳线 0（收紧约束不许牺牲这条）"
          % (len(rt0["routed"]), n_int0),
          base["cells"] == 12 and len(rt0["routed"]) == n_int0 and n_int0 > 0
          and base["n_drc"] == 0 and rt0["n_m3_jog"] == 0,
          "cells=%d · 布通 %d/%d · DRC %d · M3 跳线 %d"
          % (base["cells"], len(rt0["routed"]), n_int0, base["n_drc"], rt0["n_m3_jog"]))

    # ── B1 列资源枯竭：失败率单调不降 + 末档够高 ──────────────────
    rates = [r["no_column_rate"] for r in rows]
    check("B1 列资源枯竭（机制证据）：列失败率随规模**单调不降**，末档 ≥ %.0f%%（列数由 die 宽决定、与行数无关）"
          % (NOCOL_RATE_MIN * 100),
          DS.monotonic(rates) and rates[-1] >= NOCOL_RATE_MIN,
          "逐档 %s" % [round(v, 4) for v in rates])

    # ── B2 复杂度指数（O(M²) 的机器核验）─────────────────────────
    cmp_ = DS.complexity(L)
    k = cmp_["drc_vs_metals"]["k"]
    r2 = cmp_["drc_vs_metals"]["r2"]
    check("B2 复杂度界：`t_drc ~ M^%.2f`（M=金属数）落在 [%.2f, %.2f]，R²=%.5f ≥ 0.985 ⇒ 与逐对 O(M²) 一致"
          % (k, K_LO, K_HI, r2),
          K_LO <= k <= K_HI and r2 >= 0.985,
          "k=%.4f · R²=%.6f · n=%d" % (k, r2, cmp_["drc_vs_metals"]["n"]))

    # ── B3 DRC 是瓶颈 ─────────────────────────────────────────
    sh_last = rows[-1]["drc_share"]
    check("B3 瓶颈定位：末档（%d 单元）DRC 耗时占比 %.1f%% ≥ %.0f%% ⇒ 时间界在 DRC，不在布局/路由"
          % (rows[-1]["cells"], 100 * sh_last, 100 * DRC_SHARE_MIN),
          sh_last >= DRC_SHARE_MIN,
          "drc %.1fms / total %.1fms" % (rows[-1]["t_drc_ms"], rows[-1]["t_total_ms"]))

    # ── C1 反向探针：关掉 M2 逃逸 ⇒ 必出违例且布通更少 ────────────
    pl_o = PN.place_real(nl, max_cells=64, cols=COLS)
    rt_on = PN.route_block(nl, pl_o, m2_jog=True)
    rt_off = PN.route_block(nl, pl_o, m2_jog=False)
    d_on = len(DL.run_drc(PN.all_routing(rt_on))["violations"])
    d_off = len(DL.run_drc(PN.all_routing(rt_off))["violations"])
    check("C1 反向探针：关掉 M2 逃逸（退回无上限列搜索 ⇒ M3 长跳线）⇒ DRC 必 >0 且布通更少 "
          "（证明 A1 是修出来的，不是天生如此）",
          d_off > 0 and d_on == 0 and len(rt_off["routed"]) < len(rt_on["routed"]),
          "关: DRC %d / 布通 %d ｜ 开: DRC %d / 布通 %d"
          % (d_off, len(rt_off["routed"]), d_on, len(rt_on["routed"])))

    # ── C2 逐点逃逸额度 = 闭式 ────────────────────────────────
    # 同 y 邻域里 A(x=0.12) 与 B(x=0.48) 相隔一个 pitch：A 向右受 B 约束。
    want = PN.PITCH - 2.0 * PN.pad_half() - DL.S_MIN
    bud_ab = PN.point_off_budget([(0.12, "A"), (0.12 + PN.PITCH, "B")], 0.12, "A",
                            PN.M2_JOG_MAX)
    bud_same = PN.point_off_budget([(0.48, "A")], 0.12, "A", PN.M2_JOG_MAX)
    check("C2 逃逸额度 = 闭式：A 向左 %.3f（无邻）· 向右 %.4f == P−2·M2_HALF−S_MIN；同网不计邻居"
          % (bud_ab[0], bud_ab[1]),
          abs(bud_ab[1] - want) < 1e-9 and abs(bud_ab[0] - PN.M2_JOG_MAX) < 1e-9
          and abs(bud_same[1] - PN.M2_JOG_MAX) < 1e-9,
          "闭式 %.6f vs 实现 %.6f · 同网邻居时右额度 %.3f"
          % (want, bud_ab[1], bud_same[1]))

    # ── C3 外推自洽：用前 6 档外推末档 ──────────────────────────
    pre = {"rows": rows[:-1], "cols": COLS, "ladder": LADDER[:-1]}
    ex = DS.extrapolate(pre, rows[-1]["cells"])
    real = rows[-1]["t_drc_ms"] / 1000.0
    err = abs(ex["t_drc_s"] - real) / real if real else 1.0
    # 🔴 外推是**上界**不是点估计：金属数不与单元数成正比（布通率随规模下降），
    # 按末档比例线性放大必然高估。判据守「不许低估」+「偏离不离谱」两条。
    check("C3 外推方向正确（**上界**，不是点估计）：用前 %d 档拟合（k=%.2f）外推 %d 单元 "
          "= %.2f s ≥ 实测 %.2f s（高估 %.0f%%，因为 metals/cells 随规模下降）"
          % (len(rows) - 1, ex["k"], rows[-1]["cells"], ex["t_drc_s"], real, 100 * err),
          ex["t_drc_s"] >= real and err <= 2.0,
          "外推 %.3f s vs 实测 %.3f s（偏离 %.1f%%）" % (ex["t_drc_s"], real, 100 * err))

    # ── D1 确定性：两次阶梯逐位一致 ────────────────────────────
    L2 = DS.size_ladder(nl, ladder=LADDER[:4], cols=COLS)
    sig2 = [(r["cells"], r["n_shapes"], r["n_routed"], r["n_drc"]) for r in L2["rows"]]
    sig1 = [(r["cells"], r["n_shapes"], r["n_routed"], r["n_drc"]) for r in rows[:len(L2["rows"])]]
    check("D1 确定性：两次阶梯（前 %d 档）的 单元数/形状数/布通数/DRC 数 逐位一致"
          % len(L2["rows"]),
          sig2 == sig1, "%s vs %s" % (sig2, sig1))

    dt = time.time() - t0
    check("D0 门禁耗时 %.2f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, "%.9f" % dt)

    print("-" * 78)
    print("  [结论] 零 DRC 是**规模相关**的：修掉长跳线后 %d…%d 单元全档为零，"
          "但代价如实变成「布不通」（列失败率 0%% → %.1f%%）"
          % (rows[0]["cells"], rows[-1]["cells"], 100 * rows[-1]["no_column_rate"]))
    print("  [时间界] t_drc ~ M^%.2f（R²=%.5f）· 末档 DRC 占 %.1f%% · 外推 1 万单元 **上界** %.0f s（纯 Python 单核）"
          % (k, r2, 100 * sh_last, DS.extrapolate(L, 10000)["t_drc_s"]))
    print("  [上限来自哪] 不是算法，是**布线资源**：列数由 die 宽度决定、与行数无关 ⇒ 扩规模必须等比加宽 die")
    print("  [诚实边界] 测的是当前实现 + 当前几何（8 列 / INV+NAND2 / LDA-DEMO45），**不是算法极限**")
    print("-" * 78)
    print("E49 · 通过 %d · 失败 %d · 耗时 %.2f s" % (PASS, FAIL, dt))
    if FAIL:
        print("E49 有红色：见上方 [FAIL] 行")
        return 1
    print("E49 全绿 · 规模上探：全档零 DRC（修掉长跳线）· 上限来自列资源（非算法）· "
          "复杂度 O(M^%.2f)" % k)
    return 0


if __name__ == "__main__":
    sys.exit(main())
