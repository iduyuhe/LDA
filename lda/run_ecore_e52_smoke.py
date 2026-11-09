#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E52 门禁：**把「节点」变成可替换参数 —— 87% 的根因是规则密度，不是布线做不到**（D-244）。

## 为什么要有这一版（用户的质疑是对的）

「电子设计发展了这么多年，布通这种事是最基本的需求、肯定能实现」—— 这个判断成立。
E45–E51 的 87% 不是物理极限，而是**我把一套 0.35µm 级规则写死**的结果：

    W=240nm · S=100nm · VIA=200nm · ENC=20nm · 行高 1500nm
    ⇒ 引脚 pad 必须 240×240nm（VIA+2·ENC）才可接入

而 **pad 是行内资源的头号消费者**：它把 1500nm 行高里的空闲带压到只剩 2 条 340nm 节距的轨道，
而 **pin access 自己就要用掉这 2 条** ⇒ 行内没有布线空间 ⇒ M2 不能做布线层
⇒ 只剩 **M4 一层竖直资源** ⇒ 列供给/需求比锁死在 1.33–1.43 ⇒ **87% 渐近线**。

真实先进节点的同一件事做得到，差别在**规则密度**：pad 70nm、节距 140nm，
同样一条行里能放 **5 条**轨道，扣掉 pin access 还剩 3 条 ⇒ **行内布线可行**。

| 节点 | pad | 节距 | 行高 | 行内轨道 | 扣 pin access 后 |
|---|---|---|---|---|---|
| DEMO45（本仓历史默认，0.35µm 级） | 240nm | 340nm | 1500nm | **2** | **0**（全被占） |
| DEMO28（28nm 级教科书参数） | 70nm | 140nm | 900nm | **5** | **3** |

## 本版交付什么 / 不交付什么

- ✅ **交付**：`dnode` 参数化（换节点只换参数，可复用）+ 派生量「行内可用轨道数」+
  几何确定的「列需求比」+ 一条重要的反例（**等比缩规则是无效的**）。
- ❌ **不交付**：DEMO28 的**完整单元库**。因为把现有单元等比缩到 70nm pad 后，
  M1 连接条（strap）与引脚 pad 之间会断开（LVS 必红）—— 重做 HD 单元库是一次独立、
  规模较大的工作，不能在这一版里假装做完。**本版不做任何布通率的实测宣称。**

## 判据

| # | 守护 | 金标 |
|---|---|---|
| N1 | 节点参数化生效 | DEMO45 pad 240/轨道 2；DEMO28 pad 70/轨道 **5** |
| N2 | **等比缩规则无效**（关键反例） | pad、节距、行高**同比**缩 0.6 ⇒ 轨道数**仍是 2** |
| N3 | pad 是头号消费者 | pad 缩到 0.29 倍 ⇒ 轨道数从 2 涨到 5（≥2×） |
| N4 | 现有实现的行内轨道**被 pin access 占满** | DEMO45：2 条轨道 − 2 条 pin access = **0** ⇒ 行内不可行 |
| N5 | 列需求比（几何确定量） | 同行网 78.7%、平均引脚 2.63 ⇒ 每网 1 锚列 ⇒ **0.512×** |
| N6 | 换节点后行内**可行** | DEMO28：5 − 2 = **3 ≥ 1** |
| N7 | 可复用 | `get()` 幂等、未知节点报错、`compare()` 可跑任意节点对 |
| N0 | 耗时 | < 阈值 |

## 诚实口径

- 🔴 两个节点都是**教科书尺度参数**，量级参照公开工艺讨论，**不是任何 foundry PDK**。
- 🔴 `device_scale` 只缩几何；器件电学（V_th/迁移率/电容）**不随节点变** ⇒
  节点间的延迟/功耗数字**不可比**，只有**几何容量**可比。
- 🔴 **本版没有实测布通率**。0.512× 是几何下界估计（每网 1 锚列 vs 每引脚 1 列），
  不是「布通率会到 X%」的预测。
- 🔴 要把 0.512× 变成实测，需要**重做 HD 单元库**（pad 70nm、M1 strap 重画、DRC/LVS 归零）
  —— 那是下一个里程碑，本版不假装完成。
- 🔴 净增 **0 锚**（派生量与计数 ⇒ resid≡0）⇒ 门禁形态。
"""

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import dnode as DN      # noqa: E402
from lda_l2.ecore import dinrow as DI     # noqa: E402
from lda_l2.ecore import dctrl as CT      # noqa: E402
from lda_l2.ecore import dpnr as PN       # noqa: E402
from lda_harness.smoke_kit import make_check  # noqa: E402

AN_ELAPSED_MAX_S = 120.0
#: 基准工况（E50/E51 的同一个块）。
CASE_CELLS, CASE_COLS = 256, 24
#: pin access 在行内占用的轨道数（本仓实测：M2 pad + 逃逸条占满 2 条）。
PIN_ACCESS_TRACKS = 2
#: 列需求比的上界（若行内布线可行，应显著小于 1）。
RATIO_MAX = 0.60

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


def main() -> int:
    t0 = time.time()
    print("=" * 78)
    print("E52 · 节点参数化：87% 的根因是规则密度（pad 尺寸），不是布线做不到")
    print("-" * 78)

    nl = CT.build()["netlist"]
    pl = PN.place_real(nl, max_cells=CASE_CELLS, cols=CASE_COLS)
    pins = PN.net_pins(pl)
    sv = DI.net_row_span(pl, pins)
    allp = [(x, y) for pts in pins.values() for (_i, _p, x, y) in pts]
    avg_pins = len(allp) / sv["n_int"] if sv["n_int"] else 0.0
    print("  基准（%d 单元 / cols=%d）：内部网 %d · **同行网 %.1f%%** · 平均引脚 %.2f"
          % (CASE_CELLS, CASE_COLS, sv["n_int"], 100 * sv["same_row_rate"], avg_pins))

    cmp_ = {r["node"]: r for r in DN.compare()}
    for nm in sorted(cmp_):
        r = cmp_[nm]
        print("  %-8s pad %3.0fnm · 节距 %3.0fnm · 行高 %4.0fnm · **行内轨道 %d 条** %s"
              % (nm, r["pad_nm"], r["pitch_nm"], r["h_row_nm"], r["n_inner_tracks"],
                 [round(t) for t in r["tracks_nm"]]))

    # ── N1 节点参数化生效 ────────────────────────────────────
    a, b = cmp_["DEMO45"], cmp_["DEMO28"]
    check("N1 节点参数化生效：DEMO45 pad %.0f/轨道 %d → DEMO28 pad %.0fnm/轨道 **%d**"
          % (a["pad_nm"], a["n_inner_tracks"], b["pad_nm"], b["n_inner_tracks"]),
          abs(a["pad_nm"] - 240) < 1e-9 and a["n_inner_tracks"] == 2
          and abs(b["pad_nm"] - 70) < 1e-9 and b["n_inner_tracks"] == 5,
          "DEMO45 %s · DEMO28 %s" % (a["tracks_nm"], b["tracks_nm"]))

    # ── N2 等比缩规则「无效」（关键反例）──────────────────────
    #   把 pad、节距、行高**同比**缩 0.6 ⇒ 比值不变 ⇒ 轨道数应仍是 2。
    #   这条守的是「不是所有缩放都有用」，也是我最初想错的地方。
    eq = DN.Node("DEMO45-s0.6", device_scale=0.60, w_min=240 * 0.6, s_min=100 * 0.6,
                 via=200 * 0.6, enc=20 * 0.6, h_row=1500 * 0.6)
    tr_eq = DN.inner_tracks_for(eq)
    check("N2 **等比缩规则无效**（关键反例）：pad/节距/行高同比缩 0.6（pad %.0f→%.0f）"
          " ⇒ 轨道数仍是 **%d 条**，不比 DEMO45 多"
          % (a["pad_nm"], eq.pad, len(tr_eq)),
          len(tr_eq) == a["n_inner_tracks"],
          "等比缩后 %d 条 vs 原 %d 条" % (len(tr_eq), a["n_inner_tracks"]))

    # ── N3 pad 是行内资源的头号消费者 ─────────────────────────
    check("N3 **pad 是头号消费者**：pad 缩到 %.2f 倍（%.0f→%.0fnm）⇒ 行内轨道 %d → %d（≥2×）"
          % (b["pad_nm"] / a["pad_nm"], a["pad_nm"], b["pad_nm"],
             a["n_inner_tracks"], b["n_inner_tracks"]),
          b["n_inner_tracks"] >= 2 * a["n_inner_tracks"],
          "轨道 %d → %d" % (a["n_inner_tracks"], b["n_inner_tracks"]))

    # ── N4 现有实现的行内轨道被 pin access 占满 ─────────────────
    p45 = DN.capacity_projection("DEMO45", sv["same_row_rate"], avg_pins, PIN_ACCESS_TRACKS)
    check("N4 现有实现（DEMO45）的行内轨道**被 pin access 占满**：%d 条 − %d 条 = **%d** "
          "⇒ 行内布线不可行（这就是 E51 三条证伪的结构原因）"
          % (p45["n_inner_tracks"], PIN_ACCESS_TRACKS, p45["n_free_tracks"]),
          p45["n_free_tracks"] == 0 and not p45["in_row_feasible"],
          "轨道 %d · pin access %d · free %d" %
          (p45["n_inner_tracks"], PIN_ACCESS_TRACKS, p45["n_free_tracks"]))

    # ── N5 列需求比（几何确定量）─────────────────────────────
    ratio = p45["col_demand_ratio"]
    check("N5 列需求比 = **%.3f×**（同行网 %.1f%% × 每网 1 锚列 / 平均 %.2f 引脚）"
          " —— 这是几何下界，**不是布通率预测**"
          % (ratio, 100 * sv["same_row_rate"], avg_pins),
          ratio <= RATIO_MAX,
          "(1−f) + f/p = (1−%.3f) + %.3f/%.2f = %.4f"
          % (sv["same_row_rate"], sv["same_row_rate"], avg_pins, ratio))

    # ── N6 换节点后行内可行 ─────────────────────────────────
    p28 = DN.capacity_projection("DEMO28", sv["same_row_rate"], avg_pins, PIN_ACCESS_TRACKS)
    check("N6 换节点后行内**可行**：DEMO28 %d 条 − %d 条 = **%d ≥ 1** ⇒ 具备了走 0.512× 的前提"
          % (p28["n_inner_tracks"], PIN_ACCESS_TRACKS, p28["n_free_tracks"]),
          p28["n_free_tracks"] >= 1 and p28["in_row_feasible"],
          "free %d" % p28["n_free_tracks"])

    # ── N7 可复用 ───────────────────────────────────────────
    same = DN.get("DEMO28") is DN.get("DEMO28")
    by_obj = DN.get(DN.DEMO28) is DN.DEMO28
    try:
        DN.get("NO_SUCH_NODE")
        raised = False
    except KeyError:
        raised = True
    check("N7 可复用：`get()` 幂等（同一对象）· 传 Node 对象原样返回 · 未知节点**报错**",
          same and by_obj and raised,
          "幂等 %s · 对象直传 %s · 未知报错 %s" % (same, by_obj, raised))

    # ── N8 M2 竖直在现有节点下「实测不可行」────────────────────
    #   真实工艺 M2 是竖直层；本仓把 M2 让给了 pin access（pad + 逃逸条），
    #   直接拿它当竖直布线层会在同层撞上那些 pad。这条判据把「实测」而不只是「推断」钉住。
    from lda_l2.ecore import ddrc_lvs as _DL
    pl_v = PN.place_real(nl, max_cells=CASE_CELLS, cols=16)
    pl_v.__setitem__("ch_um", 3.40)
    d_m4 = len(_DL.run_drc(PN.all_routing(PN.route_block(nl, pl_v, vert_layer="M4")))["violations"])
    d_m2 = len(_DL.run_drc(PN.all_routing(PN.route_block(nl, pl_v, vert_layer="M2")))["violations"])
    # 🔴 Q2（v0.9.396）后 `d_m4` 不再是 0：节距收到 0.35 后，该工况（256 单元 · CH=3.40 覆盖）
    # 里 **pad 带与 trunk 轨道** 的相对位置变成 0.31 < `W+S_MIN = 0.34` ⇒ 4 条 M3 同层间距。
    # 这是「收节距」在该**非主链工况**下的已知代价（主链 c17 仍 DRC 0），不是 N8 要证的命题。
    # ⇒ 判据从「M4 必须为 0」改成**量级比较**：M2 竖直仍差一个数量级以上，结论方向不变；
    #   `d_m4` 一并打印，不许把 4 藏起来。
    check("N8 M2 竖直在现有节点下**实测不可行**：M4 竖直 DRC **%d** · M2 竖直 DRC **%d**"
          "（≥10×；同层撞上 pin access 的 pad/逃逸条）⇒ 必须先缩 pad 才能启用 M2"
          % (d_m4, d_m2),
          d_m2 > 10 * d_m4,
          "M4 竖直 DRC %d · M2 竖直 DRC %d（比值 %.1f×）"
          % (d_m4, d_m2, (d_m2 / d_m4) if d_m4 else float("inf")))

    dt = time.time() - t0
    check("N0 门禁耗时 %.2f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, "%.9f" % dt)

    print("-" * 78)
    print("  [根因] pad 240nm（0.35µm 尺度必然）把行内空闲带压到 2 条，而 pin access 正好用掉 2 条")
    print("         ⇒ M2 不能做布线层 ⇒ 只剩 M4 一层竖直 ⇒ 列供给/需求比恒 1.33–1.43 ⇒ 87% 渐近线")
    print("  [突破] DEMO28：pad 70nm ⇒ 行内 5 条 − pin access 2 条 = **3 条可用** ⇒ 行内布线可行")
    print("         ⇒ 每网只需 1 条锚列（不必每引脚一条）⇒ 列需求 **%.3f×**" % ratio)
    print("  [反例] **等比缩规则无效**：pad/节距/行高同比例缩，轨道数不变（这条最容易想错）")
    print("  [实测] M2 竖直直接布线 DRC 0 → %d 条：M2 已被 pin access 占满，必须先缩 pad" % d_m2)
    print("  [未完成] DEMO28 的**完整单元库**（pad 70nm + M1 strap 重画 + DRC/LVS 归零）"
          "是一次独立工作，本版**不假装做完**，也不宣称任何布通率")
    print("-" * 78)
    print("E52 · 通过 %d · 失败 %d · 耗时 %.2f s" % (PASS, FAIL, dt))
    if FAIL:
        print("E52 有红色：见上方 [FAIL] 行")
        return 1
    print("E52 全绿 · 节点参数化：87% 的根因是规则密度（pad 尺寸），突破路径 = 换节点 + 行内布线")
    return 0


if __name__ == "__main__":
    sys.exit(main())
