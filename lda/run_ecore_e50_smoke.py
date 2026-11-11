#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E50 门禁：**等比加宽 die 换布通率 —— 会被通道容量吃掉，最优点在中间**（D-242）。

## 这一版要验的话

E49 的结论是「上限来自布线资源、扩规模必须**等比加宽 die**」。但那句话只在一维
（cols 固定 8、只改规模）上测过。本版把 **cols（die 宽度）** 与 **CH（通道高）**
当两个独立杠杆做二维扫描，看「加宽」到底能换回多少布通率、代价多大、上限在哪。

## 结果：E49 那句话**被修正**（不是被推翻）

| CH | T | cols=4 | 8 | 12 | 16 | 20 | 24 | 32 | 峰值 |
|---|---|---|---|---|---|---|---|---|---|
| 1.60 | 4 | 51% | **57%** | 54% | 33% | 24% | 8% | **0%** | 56.9% @ cols=8 |
| 2.20 | 6 | 52% | 67% | 70% | **73%** | 63% | 62% | 11% | 73.0% @ cols=16 |
| 2.80 | 8 | 51% | 67% | 70% | 85% | **86%** | 78% | 43% | 85.8% @ cols=20 |
| 3.40 | 9 | 51% | 67% | 70% | 85% | 86% | **87%** | 43% | 87.3% @ cols=24 |

- **加宽 die 单独做是负收益**：CH=1.60 时 cols 8→32 布通率 **56.9% → 0.0%**。
  机制：cols 增大 ⇒ rows 减小 ⇒ **通道数减少**（每行上方一条），而 T 不变 ⇒ 通道先崩。
  ⇒ 「必须等比加宽 die」**必须补一句「同时加高通道」**，否则是负收益。
- **每一条切片都是单峰**（判据 W1）⇒ 最优点真实存在，不是调参手感。
- **最优点随 CH 上移**：cols 8 → 16 → 20 → 24（判据 W3），峰值同步抬升 56.9% → 87.3%（W2）。
- 越过最优点必崩：cols=32 时通道只剩 8 条、**4 个通道超容量（覆盖 124 网）** ⇒ 43%。

## 代价（Pareto，256 单元）

| 档 | 面积 | 布通率 | 面积增幅 |
|---|---|---|---|
| 默认 cols=4/CH=1.60 | 1152 µm² | 51.3% | — |
| 默认 cols=8/CH=1.60（E49 用的） | 1161 µm² | 56.9% | +0.8% |
| **80% 档** cols=16/CH=2.80 | **1650 µm²** | 84.6% | **+42%** |
| **85% 档** cols=20/CH=2.80 | **1691 µm²** | 85.8% | **+46%** |
| 最优点 cols=24/CH=3.40 | 1980 µm² | 87.3% | +71% |

⇒ **边际收益在 cols≈20–24 / CH≈2.8–3.4 见顶**；再加宽只换到 +1.5pp 却多付 25% 面积。

## 🔴 剩下的 ~13% 为什么救不回来（判据 W6 钉住）

把 `M2_JOG_MAX` 从 0.72 提到 2.16（每引脚**候选列 5 → 13**，2.6×），
`no_column` 只从 **34 → 32**、布通只多 **2 个网** ⇒ **「候选列不够」这个解释被证伪**。
真根因是**每个网独占一条跨行 M4 竖线**（星形拓扑：每网一条 trunk，竖线从引脚跨到通道），
列再多也分不过来。⇒ 出路是**加一层垂直层（M5）**或**行内局部布线**，本仓都还没做。

| # | 守护 | 金标 |
|---|---|---|
| W1 | 最优点真实存在 | 4 个 CH 切片的布通率**全部单峰**（先升后降） |
| W2 | 通道是主瓶颈 | 峰值布通率随 CH **单调上升**（56.9 → 87.3%） |
| W3 | 最优点随 CH 上移 | 最优 cols 单调不降（8 → 16 → 20 → 24） |
| W4 | 加宽单独做是负收益 | CH=1.60 下 cols=32 的布通率 < cols=8 的 **50%**（实测 0%） |
| W5 | 面积代价 | Pareto 前沿单调；85% 档最小面积 ≈1691 µm²（+46%） |
| W6 | **证伪「候选列不够」** | jog 2.6× ⇒ 多布通 ≤5 网 |
| W7 | 最优点 DRC 仍为零 | 各 CH 的最优档 **DRC == 0** |
| W8 | 最优点有界 | 64/128/256 单元的最优 cols 均落在 **[16, 24]** |
| W9 | 确定性 | 两次扫描同配置的布通数/DRC 数逐位一致 |
| W0 | 耗时 | < 阈值 |

## 诚实口径

- 🔴 测的是**当前实现 + 当前几何**（INV+NAND2 / 自建 LDA-DEMO45 / **每网一条 M3 trunk 的星形拓扑**）。
  换拓扑（maze/steiner）、换层数、换单元库都要重测。
- 🔴「加宽单独做是负收益」依赖**「通道数 == 行数」这条实现约定**；真实设计的通道与行不一一对应。
- 🔴 最优点位置**随规模漂移**（64/256 单元实测 cols≈20/24），不是常数；只断言「存在且在 [16,24]」。
- 🔴 面积是**裸排布面积**（含单元间距与通道高），不含 IO/电源环/keep-out。
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

from lda_l2.ecore import dwidth as DW     # noqa: E402
from lda_l2.ecore import dctrl as CT      # noqa: E402
from lda_harness.smoke_kit import make_check  # noqa: E402

AN_ELAPSED_MAX_S = 180.0
#: 85% 布通率档的面积窗口（实测 1691 µm²，相对默认 1152 是 +46%）。
#: 🔴 v0.9.404：原来写绝对上限 `1800 µm²` —— 它随单元面积漂（pMOS 加宽后单元 +13%，
#: 这个数立刻顶穿）。判据要说的是「为拿 85% 布通率要多付多少面积」⇒ 用**倍率**，与尺寸无关。
AREA_85_MAX_RATIO = 1.45
#: 「加宽单独做」的崩坏阈值：cols=32 的布通率必须低于 cols=8 的一半。
SLOW_CH = 1.60
#: 最优点 cols 的合法区间（随规模漂移，但有界）。
BEST_COLS_LO, BEST_COLS_HI = 16, 24
#: jog 探针允许的最大增益（若超过这个数，「候选列不够」就不能被证伪）。
JOG_GAIN_MAX = 5

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


def main() -> int:
    t0 = time.time()
    print("=" * 78)
    print("E50 · 等比加宽 die：换得到多少布通率、代价多大、上限在哪")
    print("-" * 78)

    nl = CT.build()["netlist"]
    G = DW.width_sweep(nl)
    for ch in DW.CH_GRID:
        sl = DW.slice_at(G, ch)
        print("  CH=%.2f (T=%d) | %s | 峰值 %.1f%% @ cols=%d · 面积 %.0f µm²"
              % (ch, sl[0]["t_tracks"],
                 "  ".join("c%d:%.0f%%" % (r["cols"], 100 * r["route_rate"]) for r in sl),
                 100 * DW.best_of(sl)["route_rate"], DW.best_of(sl)["cols"],
                 DW.best_of(sl)["area_um2"]))

    slices = {ch: DW.slice_at(G, ch) for ch in DW.CH_GRID}
    bests = {ch: DW.best_of(slices[ch]) for ch in DW.CH_GRID}

    # ── W1 最优点存在（每条切片单峰）──────────────────────────
    uni = {ch: DW.is_unimodal([r["route_rate"] for r in slices[ch]]) for ch in DW.CH_GRID}
    check("W1 最优点真实存在：%d 个通道高切片的布通率**全部单峰**（先升后降）⇒ 不是调参手感"
          % len(DW.CH_GRID),
          all(uni.values()), "单峰: %s" % {("%.2f" % k): v for k, v in uni.items()})

    # ── W2 通道是主瓶颈：峰值随 CH 单调上升 ────────────────────
    peaks = [bests[ch]["route_rate"] for ch in DW.CH_GRID]
    check("W2 通道是主瓶颈：峰值布通率随 CH **单调上升**（%.1f%% → %.1f%%）"
          % (100 * peaks[0], 100 * peaks[-1]),
          DW.monotonically_non_increasing([-p for p in peaks]) or
          all(peaks[i + 1] >= peaks[i] - 1e-9 for i in range(len(peaks) - 1)),
          "峰值 %s" % [round(100 * p, 1) for p in peaks])

    # ── W3 最优点随 CH 上移 ───────────────────────────────────
    best_cols = [bests[ch]["cols"] for ch in DW.CH_GRID]
    check("W3 最优点随 CH 上移：最优 cols 单调不降（%s）⇒ 通道越松就越该加宽"
          % " → ".join(str(c) for c in best_cols),
          all(best_cols[i + 1] >= best_cols[i] for i in range(len(best_cols) - 1)),
          "最优 cols %s" % best_cols)

    # ── W4 加宽单独做是负收益 ─────────────────────────────────
    sl = slices[SLOW_CH]
    r_lo = sl[0]["route_rate"]
    r_hi = sl[-1]["route_rate"]
    check("W4 加宽单独做是**负收益**：CH=%.2f 下 cols %d→%d 的布通率 %.1f%% → %.1f%%"
          "（通道数随行数一起减少，T 不变 ⇒ 通道先崩）"
          % (SLOW_CH, sl[0]["cols"], sl[-1]["cols"], 100 * r_lo, 100 * r_hi),
          r_hi < 0.5 * r_lo,
          "cols=%d %.1f%% vs cols=%d %.1f%%"
          % (sl[0]["cols"], 100 * r_lo, sl[-1]["cols"], 100 * r_hi))

    # ── W5 面积代价（Pareto + 85% 档最小面积）──────────────────
    par = DW.pareto(G["rows"])
    rates = [r["route_rate"] for r in par]
    m85 = DW.min_area_for(G["rows"], 0.85)
    base_area = min(r["area_um2"] for r in G["rows"])
    ok_par = all(rates[i + 1] > rates[i] - 1e-9 for i in range(len(rates) - 1))
    _m85_ratio = (m85["area_um2"] / base_area) if m85 else 0.0
    check("W5 面积代价：Pareto 前沿 %d 个不劣点、布通率单调；85%% 档最小面积 %.0f µm²"
          "（+%.0f%% vs %.0f ⇒ 倍率 %.2f ≤ %.2f）"
          % (len(par), m85["area_um2"] if m85 else -1,
             100 * ((m85["area_um2"] / base_area - 1) if m85 else 0), base_area,
             _m85_ratio, AREA_85_MAX_RATIO),
          ok_par and m85 is not None and _m85_ratio <= AREA_85_MAX_RATIO,
          "85%% 档: %s" % (("%.0f µm² @ cols=%d CH=%.2f (%.1f%%)"
                            % (m85["area_um2"], m85["cols"], m85["ch_um"],
                               100 * m85["route_rate"])) if m85 else "无"))

    # ── W6 证伪「候选列不够」──────────────────────────────────
    jp = DW.jog_probe(nl)
    check("W6 证伪「候选列不够」：jog 放大到 %.2f（候选列 %d→%d，%.1f×）只多布通 **%d 个网**、"
          "no_column 只降 %d ⇒ 根因是**每网独占跨行 M4 竖线**，不是候选列数"
          % (jp["samples"][-1]["jog_um"], jp["samples"][0]["n_cand"], jp["samples"][-1]["n_cand"],
             jp["cand_ratio"], jp["gain_nets"], jp["nocol_drop"]),
          jp["cand_ratio"] >= 2.0 and jp["gain_nets"] <= JOG_GAIN_MAX,
          "增益 %d 网 ≤ %d · no_column %d→%d"
          % (jp["gain_nets"], JOG_GAIN_MAX,
             jp["samples"][0]["n_no_column"], jp["samples"][-1]["n_no_column"]))

    # ── W7 最优点 DRC 仍为零 ─────────────────────────────────
    drc_bad = {ch: bests[ch]["n_drc"] for ch in DW.CH_GRID if bests[ch]["n_drc"] != 0}
    check("W7 最优点 DRC 仍为零：%d 个通道高的最优档路由 DRC 全 == 0"
          "（加宽/加高不许把 E49 的零 DRC 弄回来）" % len(DW.CH_GRID),
          not drc_bad, "非零档 %s" % (drc_bad if drc_bad else "无"))

    # ── W8 最优点有界（随规模漂移但不乱跑）──────────────────────
    drift = []
    for n in (64, 128, 256):
        r = [DW.probe_config(nl, n, c, DW.CH_GRID[-1]) for c in DW.COLS_GRID if c <= n]
        drift.append(DW.best_of(r))
    cols_seq = [d["cols"] for d in drift]
    check("W8 最优点随规模漂移但**有界**：[64,128,256] 单元的最优 cols = %s，全部落在 [%d, %d]"
          % (cols_seq, BEST_COLS_LO, BEST_COLS_HI),
          all(BEST_COLS_LO <= c <= BEST_COLS_HI for c in cols_seq),
          "cols %s · 布通 %s" % (cols_seq, [round(100 * d["route_rate"], 1) for d in drift]))

    # ── W9 确定性 ────────────────────────────────────────────
    G2 = DW.width_sweep(nl, cells=DW.CASE_CELLS,
                        cols_grid=(8, 16, 24), ch_grid=(1.60, 3.40))
    sig = lambda Gx: [(r["cols"], r["ch_um"], r["n_routed"], r["n_drc"]) for r in Gx["rows"]]  # noqa: E731
    sig2 = sig(G2)
    sig1 = [s for s in sig(G) if s[0] in (8, 16, 24) and s[1] in (1.60, 3.40)]
    check("W9 确定性：两次扫描同配置的 (cols, CH, 布通数, DRC 数) 逐位一致",
          sig2 == sig1, "%s vs %s" % (sig2, sig1))

    dt = time.time() - t0
    check("W0 门禁耗时 %.2f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, "%.9f" % dt)

    print("-" * 78)
    print("  [结论] 加宽 die **不是免费的**：单做会崩（CH=1.60 下 57%%→0%%），"
          "必须**同时加高通道**；最优点 %d 单元在 cols≈%d"
          % (DW.CASE_CELLS, bests[DW.CH_GRID[-1]]["cols"]))
    print("  [代价] %.1f%% → %.1f%% 布通率，面积 %.0f → %.0f µm²（+%.0f%%）"
          % (100 * bests[DW.CH_GRID[0]]["route_rate"], 100 * bests[DW.CH_GRID[-1]]["route_rate"],
             bests[DW.CH_GRID[0]]["area_um2"], bests[DW.CH_GRID[-1]]["area_um2"],
             100 * (bests[DW.CH_GRID[-1]]["area_um2"] / bests[DW.CH_GRID[0]]["area_um2"] - 1)))
    print("  [上限] 剩余 ~13% 救不回来：候选列 2.6× 只多 2 网 ⇒ 根因是**每网独占跨行 M4 竖线**，"
          "出路是加层(M5)或行内局部布线")
    print("-" * 78)
    print("E50 · 通过 %d · 失败 %d · 耗时 %.2f s" % (PASS, FAIL, dt))
    if FAIL:
        print("E50 有红色：见上方 [FAIL] 行")
        return 1
    print("E50 全绿 · 宽度/通道权衡：最优点真实存在（单峰）· 加宽必须配套加高 · "
          "剩余失败根因是跨行 M4 竖线")
    return 0


if __name__ == "__main__":
    sys.exit(main())
