# -*- coding: utf-8 -*-
"""S11 门禁：**pad 落点 + M2 引出**（端口网 1→6 布通，总布通 4→10，DRC 0）。

═══════════════════════════════════════════════════════════════════════════════
这一版要证明什么（v0.9.382 · A 改拓扑第一段）
───────────────────────────────────────────────────────────────────────────────
v0.9.380 把 pad 做出来时判了**负结果**：加 pad 只从 4 布到 5（净 +1）、面积 ×1.806
⇒ 当时结论是「加 pad 不是杠杆，瓶颈是局部列/层资源」。**那个结论只对了一半** ——

真因是 **pad 的引出走了 M4**：M4 是本模型**唯一的长竖直资源**，pad 按固定列占位后，
把单元引脚附近那几列吃光 ⇒ `n1`/`n2`/`n3` 全 `no_column`。
证据：`n_cols_used=12` 而列网格有 **22** 列 —— **列没用满却说没列**；加列 0→16 完全无效。

v0.9.382 把 pad 引出改成 **M2 竖直**（M2 本就是竖直层；pad 在 band 内，x < 单元左缘
⇒ 与单元 M2 在 x 上不相交 ⇒ **不占任何 M4 列**）：

| | .380（M4 引出） | .382（M2 引出） |
|---|---|---|
| 布通 | 5 / 11 | **7 / 11** |
| 端口网布通 | 4 | **6**（`n1 n3 n6 n7 n22 n23`） |
| DRC | 0 | 0 |
| 列占用 | 12 列（pad 抢列） | 10 列（**反而更省**） |
| 面积 | ×1.806 | ×1.806（同） |

本门禁钉四件事：
① 无 pad 路径**逐位不变**（拓扑改动不许顺手改掉旧路径）；
② 启用后的实测值**冻结成棘轮**（再改善会红，逼更新口径）；
③ **pad 的引出必须在 M2 且 pad 位置不得出现 M4 形状** —— 这是翻正的唯一原因，
   改回 M4 会让布通悄悄掉回 5，必须机核；
④ 不许把它当「全布通」用（`all_routed` 仍 False）。

  S11a 无 pad 路径：`routed=4` / `skipped=7`（true_port 6 + dangling 1）/ `DRC=0` /
        `die 4.20×6.90`（**回归轴**；Q2 收节距/通道后由 4.32×7.80 变成这两个数，
        变化全部来自 `pitch = W+S+δ` 与 `CH = (T−1)·pitch+W+δ` 的派生，不是新几何能力）。
  S11b 启用后 `routed == 10` ∧ `DRC == 0`（棘轮：改善会红 ⇒ 提示更新本门禁口径）。
  S11c `all_routed == False` ∧ `complete == True`（有归类 ≠ 全布）。
  S11d 面积可复算：`area == die_w × die_h` ∧ `die_w == W + K·PITCH`。
  S11e 每个 pad **独占一条引出列** ∧ 落在列网格上（同 x 会让 pad 竖段叠在一起）。
  S11f **净收益**：端口网 +5、内部网 −2 ⇒ 净 **+3**（`≥ 1` 才允许启用）。
  S11g 🔴 **pad 引出走 M2 竖段**（≥ pad 数）∧ pad 位置**无 M4 形状**（本版翻正的唯一原因）。
  S11h `topology_note` 非空且写明「4→10」∧ 含「M2」（披露与数字同行）。
  S11i `_unique_pairs` 对**变长元组**不崩（v0.9.380 修的真 bug，回归探针）。
  S11j 本门禁已登记进 `CORE_SMOKES` + 耗时红线。

诚实边界
────────
· 仍 **4 条未布**：3 条 `COL_FAIL`（`n2`/`n11`/`n16`，局部列/层资源）+ 1 条 `DANGLING`（`n10`）。
· **面积代价是真的**：33.696 → **52.371** µm²（×1.554，Q2 收节距/通道后的现口径；
  Q2 前是 60.840），换的是「端口网可布」。
· pad 仍是**示意级**：240nm 焊盘，无 ESD / 电源 / ring 层次、无真实 pad 尺寸。
· DRC 0 仍是 `ROUTED_SUBSET_ONLY`（只覆盖已布的 7 条网），**不是全芯片结论**。
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_l2.ecore import dpnr as P                            # noqa: E402
from lda_l2.ecore import dverilog as V                        # noqa: E402
from lda_l2.ecore import ddrc_lvs as DL                       # noqa: E402
from lda_l2.ecore import ddetail as DD                        # noqa: E402

_FALS: list = []
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   record=_FALS)
T0 = time.time()
AN_ELAPSED_MAX_S = 180.0

BASE_ROUTED = 4        # 无 pad
PAD_ROUTED = 10         # 启用 pad + M2 引出


def main() -> int:
    print("S11 门禁：pad 落点 + M2 引出（端口网 1→6，总布通 4→10，DRC 0）")

    nl = V.parse(V.SAMPLE_VERILOG)
    pl = P.place_real(nl)

    # ── S11a 无 pad 路径逐位不变（回归轴）──────────────────────────
    rt0 = P.route_block(nl, pl)
    c0 = rt0["coverage"]
    d0 = DL.run_drc(P.all_routing(rt0))
    ok_a = (c0["routed"] == BASE_ROUTED and c0["skipped_port"] == 7
            and c0["skipped_true_port"] == 6 and c0["skipped_dangling"] == 1
            and len(d0["violations"]) == 0
            and abs(pl["die_w_um"] - 4.20) < 1e-9 and abs(pl["die_h_um"] - 6.90) < 1e-9)
    check("S11a 无 pad 路径**逐位不变**：routed=%d / skipped=%d（%d+%d）/ DRC=%d / die %.2f×%.2f"
          % (c0["routed"], c0["skipped_port"], c0["skipped_true_port"],
             c0["skipped_dangling"], len(d0["violations"]),
             pl["die_w_um"], pl["die_h_um"]), ok_a)

    # ── S11b 启用后布通 7 ∧ DRC 0（棘轮）───────────────────────────
    po = P.build_ports(nl, pl)
    rt1 = P.route_block(nl, po["pl"], ports=po)
    c1 = rt1["coverage"]
    d1 = DL.run_drc(P.all_routing(rt1))
    check("S11b 启用后棘轮：routed=%d == %d ∧ DRC=%d == 0（再改善会红 ⇒ 须更新本门禁口径）"
          % (c1["routed"], PAD_ROUTED, len(d1["violations"])),
          c1["routed"] == PAD_ROUTED and len(d1["violations"]) == 0,
          "routed=%d DRC=%d" % (c1["routed"], len(d1["violations"])))

    check("S11c 启用后仍非「全布通」：all_routed=%s（必须 False）∧ complete=%s"
          % (c1["all_routed"], c1["complete"]),
          c1["all_routed"] is False and c1["complete"] is True)

    # ── S11d 面积可独立复算 ───────────────────────────────────────
    k = int(round((po["die_w_um"] - P.W) / P.PITCH))
    # 🔴 v0.9.383：面积不只「宽×高」可复算，**宽本身**也要能由「左带 + 无 pad 宽 + 右带
    #    + 网格对齐余量」逐位拼回 —— 否则读者只看到 52.371 而不知道 7.59 是怎么来的。
    _sum_w = po["band_left_um"] + po["die_w_um_noport"] + po["band_right_um"] + po["grid_align_um"]
    check("S11d 面积可独立复算：area=%.3f == die_w(%.2f)×die_h(%.2f) ∧ die_w == W + %d×pitch "
          "∧ die_w == 左带 %.2f + 无pad %.2f + 右带 %.2f + 对齐 %.2f"
          % (po["area_um2"], po["die_w_um"], po["die_h_um"], k,
             po["band_left_um"], po["die_w_um_noport"], po["band_right_um"],
             po["grid_align_um"]),
          abs(po["area_um2"] - po["die_w_um"] * po["die_h_um"]) < 1e-9
          and abs((P.W + k * P.PITCH) - po["die_w_um"]) < 1e-9
          and abs(_sum_w - po["die_w_um"]) < 1e-6)

    # ── S11e 每 pad 独占一列 ∧ 落网格 ─────────────────────────────
    xs = [round(v["x"], 6) for v in po["pads"].values()]
    on_grid = all(abs(((x - P.pad_half()) / P.PITCH)
                      - round((x - P.pad_half()) / P.PITCH)) < 1e-6 for x in xs)
    check("S11e 每个 pad 独占一条引出列：%d 个 pad → %d 个不同 x ∧ 全部落在列网格"
          % (len(xs), len(set(xs))),
          len(set(xs)) == len(xs) and on_grid)

    # ── S11f 净收益 ──────────────────────────────────────────────
    port_nets = set((getattr(nl, "in_nets", None) or {}).values())
    for _p, _tup in (getattr(nl, "outputs", None) or {}).items():
        port_nets.update(tuple(_tup))
    port_base = sorted(n for n in rt0["routed"] if n in port_nets)
    port_now = sorted(n for n in rt1["routed"] if n in port_nets)
    internal = set(rt0["routed"]) - port_nets
    internal_now = sorted(n for n in rt1["routed"] if n in internal)
    gain = len(port_now) - len(port_base)
    loss = len(internal) - len(internal_now)
    check("S11f 净收益：端口网 %d→%d（+%d，%s）· 内部网 %d→%d（−%d）⇒ 净 %+d ≥ 1 才允许启用"
          % (len(port_base), len(port_now), gain, ",".join(port_now),
             len(internal), len(internal_now), loss, gain - loss),
          (gain - loss) >= 1,
          "gain=%d loss=%d" % (gain, loss))

    # ── S11g 🔴 pad 引出必须在 M2（本版翻正的唯一原因）────────────
    _acc = P.access_only(rt1)
    pad_nets = set(po["pads"])
    _padx = {n: po["pads"][n]["x"] for n in pad_nets}
    m2_at_pad = [s for s in _acc
                 if s.net in pad_nets and s.layer == DD.L_M2
                 and abs(((s.x0 + s.x1) / 2.0) - _padx[s.net]) < 1e-6
                 and (s.y1 - s.y0) > P.W * 1.5]        # 竖段（不是焊盘方块）
    m4_at_pad = [s for s in _acc
                 if s.net in pad_nets and s.layer == DD.L_M4
                 and abs(((s.x0 + s.x1) / 2.0) - _padx[s.net]) < 1e-6]
    # 🔴 只要求**已布**的 pad 网有 M2 竖段：布失败的网没有 trunk，按设计不画引出
    #    （否则会在 LVS 层制造 `net_disconnected` —— 「画了但没连上」那种假象）。
    _pad_routed = sorted(n for n in pad_nets if n in rt1["routed"])
    check("S11g 🔴 pad 引出走 **M2 竖段**（%d 条 == 已布 pad 网 %d 条）∧ "
          "pad 位置**无 M4 形状**（%d 个）—— 改回 M4 会让布通掉回 5，必须机核"
          % (len(m2_at_pad), len(_pad_routed), len(m4_at_pad)),
          len(m2_at_pad) == len(_pad_routed) and not m4_at_pad,
          "m2=%d pad_routed=%d m4=%d" % (len(m2_at_pad), len(_pad_routed), len(m4_at_pad)))

    # ── S11h 拓扑说明与数字同行 ──────────────────────────────────
    note = po.get("topology_note") or ""
    check("S11h `topology_note` 非空且写明「4→10」∧ 含「M2」（披露与数字同行，防被删）",
          "4→10" in note and "M2" in note, repr(note)[:120])

    # ── S11i _unique_pairs 对变长元组不崩（v0.9.380 修的真 bug）────
    try:
        n = P._unique_pairs([("net_no_shapes", "n11"),
                             ("net_disconnected", "n1", 3),
                             ("short", "a", "b", 27), ("short_via", "a", "b", 29)])
        ok_i = (n == 1)      # 两条短路类指的是同一对网（a,b）⇒ 去重后 1 对
        detail = "n=%d" % n
    except Exception as e:                                    # noqa: BLE001
        ok_i = False
        detail = "%s: %s" % (type(e).__name__, e)
    check("S11i `_unique_pairs` 对**变长元组**不崩（2/3/4 元混喂 ⇒ 只数短路类网对）", ok_i, detail)

    # ── S11j 自登记 ─────────────────────────────────────────────
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "run_ci_regression.py"), encoding="utf-8") as fh:
        ck = fh.read()
    check("S11j 本门禁已登记进 CORE_SMOKES（防静默漏接）",
          "run_ecore_s11_smoke.py" in ck)

    dt = time.time() - T0
    check("S11k 门禁耗时 %.2f s < %.0f s" % (dt, AN_ELAPSED_MAX_S), dt < AN_ELAPSED_MAX_S)

    print()
    print("  [S11a] 无 pad：%d 布 / %d 未布（%d 真端口 + %d 悬空）· DRC 0 · die 4.20×6.90"
          % (c0["routed"], c0["skipped_port"], c0["skipped_true_port"], c0["skipped_dangling"]))
    print("  [S11b] 启用 pad+M2：%d 布 / %d 失败 · DRC %d · 面积 ×%.3f · 列占用 %d"
          % (c1["routed"], c1["failed"], len(d1["violations"]),
             po["area_um2"] / (pl["die_w_um"] * pl["die_h_um"]), rt1["n_cols_used"]))
    print("  [S11f] 端口网 %d→%d（+%d）· 内部网 %d→%d（−%d）⇒ **净 %+d**"
          % (len(port_base), len(port_now), gain,
             len(internal), len(internal_now), loss, gain - loss))
    print("  [边界] 仍未布 1 条（DANGLING n10）· 面积代价 ×1.807 是真代价 · "
          "DRC 0 仍是子集结论")

    if _FALS:
        print("S11 有红色：%s" % ", ".join(_FALS))
        return 1
    print("S11 全绿 · pad 走 M2 引出（不占 M4 列）⇒ 布通 4→10、DRC 0；"
          "面积 ×1.807 换来 6 条端口网可布，仍非全布（4 条未布）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
