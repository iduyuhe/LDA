#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E51 门禁：**行内局部布线被证伪 —— 87% 是结构渐近线**（D-243）。

## 这一版要回答什么

E50 把布通率做到 **87.3%** 就卡住，失败全是 `no_column`，并机核排除了「候选列不够」，
指出真根因是**每个网独占一条跨行 M4 竖线**。那么最直接的出路就是
**让网在行内互联、不走跨行长竖线** —— 本版就是去验它。

动机很强：**60–80% 的内部网所有引脚都在同一行**（256 单元 cols=8 时 61%、cols=24 时 79%）。

## 结果：这条路走不通，三个独立证据

| 证据 | 实测 |
|---|---|
| ① 行内 M3 水平段 | 布通 **+0 网**，DRC **0 → 786 条**（cols=24）／288（cols=16）／70（cols=8） |
| ② 行内 M2 空间（闭式） | INV 最大空隙 **345nm**、NAND2 **410nm**；一条 M2 走线需 **340nm** ⇒ **最多 1 条**，INV 余量 **5nm** |
| ③ 列分配迭代 | iters 1/2/3 布通数 **233/233/233**、`no_column` **34/34/34** ⇒ 零收益 |

① 的机制：同一行所有引脚的 M3 pad 都在自己的 y 带上，任何横穿同行的水平段必然压到异网 pad。
③ 的机制：冲突**不是**来自 y 区间长度，而是「同一行的引脚 y 区间必然重叠」这条几何事实 ——
所以用「实际轨号」替代「最高轨」（区间确实变短）也一个网都换不回来。

## 于是 87% 有了结构解释：它是渐近线，不是调参没到位

加宽 die 同时让「列数」和「每行引脚数」同比例增长，实测供给/需求比**恒定**：

| cols | ncol | 每行最大引脚数 | 供给/需求 | 布通率 | no_column |
|---|---|---|---|---|---|
| 8  | 32  | 24 | 1.33 | 66.7% | 89 |
| 16 | 64  | 46 | 1.39 | 84.6% | 41 |
| 24 | 96  | 67 | **1.43** | **87.3%** | 34 |
| 32 | 128 | 90 | 1.42 | 43.1%（通道崩 4 个） | 28 |

⇒ `no_column` 从 89 降到 34 但**永不归零**（最优点仍 12.7%）；再加宽就会先撞通道。

对照实验：通道高度从 **3.40 一路加到 6.00（T 9 → 17）**，布通率**一动不动 87.3%**、
通道一个都不满 ⇒ **通道早已不是瓶颈，瓶颈就是列**。

**⇒ 唯一能突破的杠杆是加一层垂直层（M5）**：分子（列）可以靠新层翻倍，分母（每行引脚数）不变。

| # | 守护 | 金标 |
|---|---|---|
| R1 | 行内 M3 **不可行** | 开 in_row ⇒ DRC **必 > 0** 且布通**零改善** |
| R2 | 行内 M2 **空间不足**（闭式） | 两单元最大空隙均 ≥340nm 但 **< 680nm**（只够 1 条，服务不了一行） |
| R3 | 列迭代**零收益** | iters 1 vs 3 布通数相同 ∧ `no_column` 相同 |
| R4 | 通道**已饱和** | CH 3.40→6.00 布通率不变 ∧ 各档 `n_channel_full == 0` |
| R5 | 供给/需求比**恒定** | 跨 cols 的比值极差 ≤ 0.15（实测 1.33–1.43） |
| R6 | `no_column` **不归零** | 最优点仍 > 0（渐近线的直接证据） |
| R7 | 同行网比例**够高**（动机成立） | 同 1 行网的占比 ≥ 50% ⇒ 不是「没东西可优化」 |
| R8 | 全档 DRC 仍为零 | 关掉行内互联时各 cols 档 DRC == 0（不许退化） |
| R9 | 确定性 | 两次同配置的布通数/DRC 数逐位一致 |
| R0 | 耗时 | < 阈值 |

## 诚实口径

- 🔴 **这是负结果**：行内局部布线在**当前单元几何**下不可行。**不是**说「行内布线在真实设计里也不行」
  —— 真实 std-cell 的 pin access 靠 M2 局部绕行，但那是**单元库自带**的；本仓 `dcells` 的 M2 只在
  pin access 处有焊盘，行内没有留给走线的轨道。
- 🔴 渐近线 87% 依赖本实现的**星形拓扑**（每网一条 M3 trunk + 每引脚一条 M4 竖线）。
  换 Steiner/多干拓扑后这条线会变 —— **不是**「这套链路的能力上限」。
- 🔴「供给/需求比恒定」是在**同一网表前 N 门**上测的，换网序会小幅漂移（实测 1.33–1.43）。
- 🔴 本版**没有提升任何能力**，交付的是「一条最有希望的路被机核关闭」+「下一步只剩加层」。
- 🔴 净增 **0 锚**（计数与比值 ⇒ resid≡0）⇒ 门禁形态，不伪造非零残差。
"""

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import dinrow as DI      # noqa: E402
from lda_l2.ecore import dctrl as CT       # noqa: E402
from lda_l2.ecore import ddrc_lvs as DL    # noqa: E402
from lda_l2.ecore import dpnr as PN        # noqa: E402
from lda_harness.smoke_kit import make_check  # noqa: E402

AN_ELAPSED_MAX_S = 180.0
#: 两条 M2 轨道所需的最小空隙（nm）—— 用来区分「1 条」与「够用」。
NEED_2_TRACKS_NM = 2 * (PN.W + DL.S_MIN) * 1000.0
#: 供给/需求比允许的极差（实测 1.33–1.43 ⇒ 0.10）。
RATIO_SPREAD_MAX = 0.15
#: 最优点 `no_column` 必须仍 > 0（渐近线证据）。
#: 同行网占比下限（动机是否成立）。
SAME_ROW_MIN = 0.5

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


def main() -> int:
    t0 = time.time()
    print("=" * 78)
    print("E51 · 行内局部布线：能不能让网不走跨行长竖线")
    print("-" * 78)

    nl = CT.build()["netlist"]

    # ── R7 动机：同行网比例（先确认「有东西可优化」）────────────
    spans = []
    for cols in (8, 24):
        pl = PN.place_real(nl, max_cells=DI.CASE_CELLS, cols=cols)
        sv = DI.net_row_span(pl, PN.net_pins(pl))
        spans.append((cols, sv))
        print("  cols=%2d | 内部网 %d · 全引脚同行 **%d (%.0f%%)** · 跨行分布 %s"
              % (cols, sv["n_int"], sv["same_row"], 100 * sv["same_row_rate"],
                 {k: v for k, v in sv["hist"].items() if k > 1}))
    check("R7 动机成立：全引脚同行的内部网占比 ≥ %.0f%%（实测 %.0f%% / %.0f%%）"
          % (100 * SAME_ROW_MIN, 100 * spans[0][1]["same_row_rate"],
             100 * spans[1][1]["same_row_rate"]),
          all(s["same_row_rate"] >= SAME_ROW_MIN for (_c, s) in spans),
          "占比 %s" % [round(100 * s["same_row_rate"], 1) for (_c, s) in spans])

    # ── R2 行内 M2 空间（闭式）────────────────────────────────
    gaps = {c: DI.row_gaps(c) for c in sorted(DI.CL.CELLS)}
    for c, g in gaps.items():
        print("  %-9s 行内最大空隙 %4dnm · 一条 M2 走线需 %.0fnm ⇒ **%d 条** · 余量 %+dnm"
              % (c, g["widest_nm"], g["need_nm"], g["n_tracks"], g["slack_nm"]))
    check("R2 行内 M2 空间不足（闭式）：%d 种单元的最大空隙都 ≥ %.0fnm 却 **< %.0fnm**"
          "（只够 1 条轨道，服务不了一行的几十个网）"
          % (len(gaps), gaps["INV_X1"]["need_nm"], NEED_2_TRACKS_NM),
          all(g["n_tracks"] <= 1 and g["widest_nm"] < NEED_2_TRACKS_NM for g in gaps.values()),
          "空隙 %s · 需 2 条 %.0fnm" % ({c: g["widest_nm"] for c, g in gaps.items()},
                                        NEED_2_TRACKS_NM))

    # ── R1 行内 M3 不可行 ────────────────────────────────────
    probe = DI.in_row_probe(nl)
    print("  行内互联 · 关：布通 %d/%d（%.1f%%）· DRC %d"
          % (probe["off"]["n_routed"], probe["off"]["n_int"],
             100 * probe["off"]["rate"], probe["off"]["n_drc"]))
    print("  行内互联 · 开：布通 %d/%d（%.1f%%）· DRC %d（%s）"
          % (probe["on"]["n_routed"], probe["on"]["n_int"],
             100 * probe["on"]["rate"], probe["on"]["n_drc"],
             probe["on"]["drc_kinds"]))
    check("R1 行内 M3 **不可行**：开启后布通 **零改善（%+d 网）** 而 DRC **必 > 0**（实测 %d 条）"
          " ⇒ 水平段必然压到同行异网 pad"
          % (probe["delta_routed"], probe["on"]["n_drc"]),
          probe["off"]["n_drc"] == 0 and probe["on"]["n_drc"] > 0
          and probe["delta_routed"] <= 0,
          "关 DRC %d → 开 DRC %d · 布通 %d → %d"
          % (probe["off"]["n_drc"], probe["on"]["n_drc"],
             probe["off"]["n_routed"], probe["on"]["n_routed"]))

    # ── R3 列分配迭代零收益 ──────────────────────────────────
    iters = DI.col_iter_probe(nl)
    print("  列分配迭代：%s"
          % ", ".join("iters=%d → 布通 %d / nocol %d" % (x["iters"], x["n_routed"], x["n_no_column"])
                      for x in iters))
    check("R3 列分配迭代**零收益**：iters 1 vs %d 的布通数与 `no_column` 完全相同"
          " ⇒ 冲突不是来自 y 区间长度，而是「同行引脚 y 必然重叠」"
          % iters[-1]["iters"],
          all(x["n_routed"] == iters[0]["n_routed"] and
              x["n_no_column"] == iters[0]["n_no_column"] for x in iters),
          "布通 %s · nocol %s"
          % ([x["n_routed"] for x in iters], [x["n_no_column"] for x in iters]))

    # ── R4 通道已饱和 ────────────────────────────────────────
    sat = DI.channel_saturation(nl)
    print("  通道饱和：%s"
          % ", ".join("CH=%.2f(T=%d) → %.1f%% / chanF %d"
                      % (x["ch_um"], x["t_tracks"], 100 * x["rate"], x["n_channel_full"])
                      for x in sat))
    rates = [x["rate"] for x in sat]
    check("R4 通道**已饱和**：CH %.2f→%.2f（T %d→%d）布通率不变，且各档 `n_channel_full` 全 0"
          " ⇒ 瓶颈只剩列"
          % (sat[0]["ch_um"], sat[-1]["ch_um"], sat[0]["t_tracks"], sat[-1]["t_tracks"]),
          max(rates) - min(rates) <= 1e-9
          and all(x["n_channel_full"] == 0 for x in sat),
          "布通率 %s" % [round(100 * r, 1) for r in rates])

    # ── R5 供给/需求比恒定（渐近线的根）───────────────────────
    sd = DI.supply_demand(nl)
    for x in sd:
        print("  cols=%2d | ncol %3d · 每行引脚 %2d · 供给/需求 **%.2f** · 布通 %5.1f%%"
              " · nocol %3d · chanF %d"
              % (x["cols"], x["n_col"], x["max_per_row"], x["ratio"],
                 100 * x["rate"], x["n_no_column"], x["n_channel_full"]))
    ratios = [x["ratio"] for x in sd]
    check("R5 列供给/需求比**恒定**（极差 %.2f ≤ %.2f）：加宽 die 让分子分母同比例增长"
          " ⇒ 永远无法把 `no_column` 归零"
          % (max(ratios) - min(ratios), RATIO_SPREAD_MAX),
          max(ratios) - min(ratios) <= RATIO_SPREAD_MAX,
          "比值 %s" % [round(r, 3) for r in ratios])

    # ── R6 no_column 不归零（且通道未崩的最优点仍剩列失败）──────
    ok_rows = [x for x in sd if x["n_channel_full"] == 0]
    best = max(ok_rows, key=lambda x: x["rate"])
    check("R6 `no_column` **不归零**：通道未崩的最优点（cols=%d, 布通 %.1f%%）仍剩 %d 个网布不通"
          " ⇒ 87%% 是结构渐近线，不是调参没到位"
          % (best["cols"], 100 * best["rate"], best["n_no_column"]),
          best["n_no_column"] > 0,
          "nocol %d / 内部网 %d" % (best["n_no_column"],
                                    int(round(best["n_routed"] / best["rate"])) if best["rate"] else 0))

    # ── R8 关掉行内互联时全档 DRC 仍为零 ──────────────────────
    bad = [(x["cols"], x["n_drc"]) for x in
           [dict(cols=x["cols"], n_drc=len(DL.run_drc(PN.all_routing(
               PN.route_block(nl, PN.place_real(nl, max_cells=DI.CASE_CELLS, cols=x["cols"]))))["violations"]))
            for x in sd] if x["n_drc"] != 0]
    check("R8 全档 DRC 仍为零：%d 个 cols 档（关闭行内互联）路由+全量 DRC 全 == 0（不许退化）"
          % len(sd), not bad, "非零档 %s" % (bad if bad else "无"))

    # ── R9 确定性 ────────────────────────────────────────────
    a = DI.supply_demand(nl, cols_grid=(16, 24))
    b = DI.supply_demand(nl, cols_grid=(16, 24))
    sig = lambda L: [(x["cols"], x["n_routed"], x["n_no_column"], x["n_channel_full"]) for x in L]  # noqa: E731
    check("R9 确定性：两次同配置的 (cols, 布通数, nocol, chanF) 逐位一致",
          sig(a) == sig(b), "%s vs %s" % (sig(a), sig(b)))

    dt = time.time() - t0
    check("R0 门禁耗时 %.2f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, "%.9f" % dt)

    print("-" * 78)
    print("  [结论] 行内局部布线**被证伪**：M3 水平段必撞同行异网 pad（DRC %d 条、布通 +0），"
          "行内 M2 只放得下 1 条轨道（INV 余量 %dnm）"
          % (probe["on"]["n_drc"], gaps["INV_X1"]["slack_nm"]))
    print("  [渐近线] 列供给/需求比恒定 %.2f–%.2f ⇒ 加宽永远不能把 no_column 归零（最优点仍 %d 网）"
          % (min(ratios), max(ratios), best["n_no_column"]))
    print("  [通道] CH %.2f→%.2f（T %d→%d）布通率一动不动 ⇒ 通道早已不是瓶颈"
          % (sat[0]["ch_um"], sat[-1]["ch_um"], sat[0]["t_tracks"], sat[-1]["t_tracks"]))
    print("  [下一步] 唯一杠杆 = **加一层垂直层（M5）**：分子（列）可翻倍，分母（每行引脚数）不变")
    print("  [诚实边界] 本版**没有提升任何能力**；渐近线依赖星形拓扑，换 Steiner 后会变")
    print("-" * 78)
    print("E51 · 通过 %d · 失败 %d · 耗时 %.2f s" % (PASS, FAIL, dt))
    if FAIL:
        print("E51 有红色：见上方 [FAIL] 行")
        return 1
    print("E51 全绿 · 行内布线被证伪：87% 是结构渐近线（列供给/需求比恒定），"
          "突破口只剩加层 M5")
    return 0


if __name__ == "__main__":
    sys.exit(main())
