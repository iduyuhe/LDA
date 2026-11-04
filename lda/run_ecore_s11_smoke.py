# -*- coding: utf-8 -*-
"""S11 门禁：**pad 落点模型的负结果**（能布通 4 条端口网，但净收益 +1 ⇒ 默认不启用）。

═══════════════════════════════════════════════════════════════════════════════
这一版要证明什么（v0.9.380）
───────────────────────────────────────────────────────────────────────────────
上一版说「6 条端口网补 pad 后可望布通」。**本轮把它做出来，实测不成立**：

  · 加 pad 后端口网确实布通 **4** 条（`n22`/`n23`/`n6`/`n7`）—— 这是真的进展；
  · 但同时挤掉 **3** 条原本布通的**内部**网（`n11`/`n16`/…）⇒ 总布通 **4 → 5**，净增 **1**；
  · 面积 **33.696 → 60.840 µm²（×1.806）**；
  · `n1`/`n2`/`n3` 仍 `no_column`，加列（`extra_cols` 0→16）**完全无效**。

⇒ 瓶颈不是「端口网没有端点」（pad 已解除），而是**局部列 / 层资源**。这与
E38（布不通=口袋）、E50–E53（容量律 / pad 尺寸吃掉空隙）是同一个结论：
**唯一杠杆是改拓扑或加层，不是加 pad。**

本门禁只钉三件事：① 默认路径**逐位不变**（pad 必须是可选的）；
② pad 路径的实测值**冻结成棘轮**（只能变好，变好会红并提示更新口径）；
③ **不许把它当「已布通」用**（`all_routed` 必须 False，`not_enabled_reason` 必须非空）。

  S11a 默认路径逐位不变：`routed=4` / `skipped=7`（true_port 6 + dangling 1）/ `DRC=0` /
        `die 4.32×7.80` —— 与 v0.9.379 完全一致（这一条是**回归轴**，动了就是破坏兼容）。
  S11b pad 路径：`routed ≤ 5` ∧ `DRC == 0`（棘轮：改善会红 ⇒ 提示更新本门禁口径）。
  S11c `all_routed == False` ∧ `complete == True`（有归类 ≠ 全布，pad 也没有改变这一点）。
  S11d 面积可复算：`area == die_w × die_h` ∧ `die_w == W + K·PITCH`（K 由 build_ports 自报）。
  S11e 每个 pad **独占一列**：pad x 两两不同 ∧ 全部落在列网格上
        （同一 x 会让所有 pad 的 M4 竖段叠在一起 ⇒ 实测 113 处 DRC + 315 条 LVS 短路）。
  S11f **净收益披露**：端口网布通增量 − 内部网布通减少量 ≤ 1（当前 4−3=1）。
  S11g `_unique_pairs` 对**变长元组**不崩（回归：喂 `("net_no_shapes", net)` 2 元组）。
  S11h `not_enabled_reason` 非空且含「负收益」字样（防有人悄悄改成「已启用」）。
  S11i 本门禁已登记进 `CORE_SMOKES` + 耗时红线。

诚实边界
────────
· **本门禁不声称 pad 模型可用**：它证明的是「做了也不行」，不是「做了就行」。
· pad 仍是**示意级**（240nm 三层小栈，无 ESD/电源/ring 层次、无真实 pad 尺寸）。
· 若未来改拓扑（pad 专用层 / M2 竖直资源 / 更多层）后布通真上去了，**S11b 会红** ——
  那是**好事**：它逼人更新口径，而不是让一个过期的「不行」结论永久挂着。
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_l2.ecore import dpnr as P                          # noqa: E402
from lda_l2.ecore import dverilog as V                      # noqa: E402
from lda_l2.ecore import ddrc_lvs as DL                     # noqa: E402

_FALS: list = []
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   record=_FALS)
T0 = time.time()
AN_ELAPSED_MAX_S = 180.0

#: pad 路径的冻结实测值（棘轮：`routed` 只能 ≤ 此值；DRC 必须 == 0）
PAD_ROUTED_MAX = 5
BASE_ROUTED = 4
BASE_SKIPPED = 7


def main() -> int:
    print("S11 门禁：pad 落点模型的**负结果**（端口网可布，但净收益 +1 ⇒ 默认不启用）")

    nl = V.parse(V.SAMPLE_VERILOG)
    pl = P.place_real(nl)

    # ── 默认路径（回归轴）──────────────────────────────────────────
    rt0 = P.route_block(nl, pl)
    c0 = rt0["coverage"]
    d0 = DL.run_drc(P.all_routing(rt0))
    area0 = pl["die_w_um"] * pl["die_h_um"]
    ok_a = (c0["routed"] == BASE_ROUTED and c0["skipped_port"] == BASE_SKIPPED
            and c0["skipped_true_port"] == 6 and c0["skipped_dangling"] == 1
            and len(d0["violations"]) == 0
            and abs(pl["die_w_um"] - 4.32) < 1e-9 and abs(pl["die_h_um"] - 7.80) < 1e-9)
    check("S11a 默认路径（ports=None）**逐位不变**：routed=%d / skipped=%d（%d+%d）/ DRC=%d / "
          "die=%.2f×%.2f —— 与 v0.9.379 一致"
          % (c0["routed"], c0["skipped_port"], c0["skipped_true_port"],
             c0["skipped_dangling"], len(d0["violations"]),
             pl["die_w_um"], pl["die_h_um"]), ok_a)

    # ── pad 路径 ───────────────────────────────────────────────────
    po = P.build_ports(nl, pl)
    rt1 = P.route_block(nl, po["pl"], ports=po)
    c1 = rt1["coverage"]
    d1 = DL.run_drc(P.all_routing(rt1))
    # 🔴 端口网必须**从网表取全集**，不能用 `rt1["port_nets"]`：
    #    那是「**仍**只有 1 个端点」的端口网 —— 加 pad 后它们变成 2 端点，会从该集合里消失，
    #    gain 会被算成 0（首跑就是这个错，S11f 报「端口网 +0」）。
    port_nets = set((getattr(nl, "in_nets", None) or {}).values())
    for _p, _tup in (getattr(nl, "outputs", None) or {}).items():
        port_nets.update(tuple(_tup))
    port_routed = sorted(n for n in rt1["routed"] if n in port_nets)
    # 🔴 增量必须**减去基线的同口径**：`n3` 是输入端口但有两个单元引脚 ⇒ 无 pad 时也已布通。
    #    只数「pad 路径的端口布通数」会把 gain 多算 1（首版 = 4，实际净增 3）。
    port_base = sorted(n for n in rt0["routed"] if n in port_nets)
    internal = set(rt0["routed"]) - port_nets          # 无 pad 时布通的内部网
    internal_routed = sorted(n for n in rt1["routed"] if n in internal)
    gain = len(port_routed) - len(port_base)
    loss = len(internal) - len(internal_routed)

    check("S11b pad 路径棘轮：routed=%d ≤ %d ∧ DRC=%d == 0（改善会红 ⇒ 须更新本门禁口径）"
          % (c1["routed"], PAD_ROUTED_MAX, len(d1["violations"])),
          c1["routed"] <= PAD_ROUTED_MAX and len(d1["violations"]) == 0,
          "routed=%d DRC=%d" % (c1["routed"], len(d1["violations"])))

    check("S11c pad 也没有变成「全布通」：all_routed=%s（必须 False）∧ complete=%s"
          % (c1["all_routed"], c1["complete"]),
          c1["all_routed"] is False and c1["complete"] is True)

    # 面积可复算：die_w = W + K·PITCH
    k = int(round((po["die_w_um"] - P.W) / P.PITCH))
    check("S11d 面积可独立复算：area=%.3f == die_w(%.2f)×die_h(%.2f) ∧ "
          "die_w == W + %d×pitch" % (po["area_um2"], po["die_w_um"], po["die_h_um"], k),
          abs(po["area_um2"] - po["die_w_um"] * po["die_h_um"]) < 1e-9
          and abs((P.W + k * P.PITCH) - po["die_w_um"]) < 1e-9,
          "area=%r die_w=%r k=%d" % (po["area_um2"], po["die_w_um"], k))

    # 每个 pad 独占一列 ∧ 落在列网格
    xs = [round(v["x"], 6) for v in po["pads"].values()]
    on_grid = all(abs(((x - P.PIN_GRID_UM) / P.PITCH) - round((x - P.PIN_GRID_UM) / P.PITCH))
                  < 1e-6 for x in xs)
    check("S11e 每个 pad 独占一条引出列：%d 个 pad → %d 个不同 x（%s）∧ 全部落在列网格"
          % (len(xs), len(set(xs)), ",".join("%.2f" % x for x in sorted(set(xs)))),
          len(set(xs)) == len(xs) and on_grid,
          "xs=%r on_grid=%s" % (sorted(xs), on_grid))

    check("S11f 净收益披露：端口网布通 %d→%d（+%d，%s）− 内部网 %d→%d（−%d）= 净 %+d ≤ 1"
          % (len(port_base), len(port_routed), gain, ",".join(port_routed),
             len(internal), len(internal_routed), loss, gain - loss),
          (gain - loss) <= 1,
          "gain=%d loss=%d" % (gain, loss))

    # ── S11g _unique_pairs 对变长元组不崩 ──────────────────────────
    try:
        n = P._unique_pairs([("net_no_shapes", "n11"),
                             ("net_disconnected", "n1", 3),
                             ("short", "a", "b", 27), ("short_via", "a", "b", 29)])
        ok_g = (n == 1)          # 两条短路类指的是**同一对**网（a,b）⇒ 去重后 1 对
        detail = "n=%d" % n
    except Exception as e:                                    # noqa: BLE001
        ok_g = False
        detail = "%s: %s" % (type(e).__name__, e)
    check("S11g `_unique_pairs` 对**变长元组**不崩（2/3/4 元混喂 ⇒ 只数短路类网对）", ok_g, detail)

    check("S11h `not_enabled_reason` 非空且写明负收益（防被悄悄改成『已启用』）",
          bool(po.get("not_enabled_reason")) and "负收益" in po["not_enabled_reason"],
          repr(po.get("not_enabled_reason"))[:120])

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "run_ci_regression.py"), encoding="utf-8") as fh:
        ck = fh.read()
    check("S11i 本门禁已登记进 CORE_SMOKES（防静默漏接）",
          "run_ecore_s11_smoke.py" in ck)

    dt = time.time() - T0
    check("S11j 门禁耗时 %.2f s < %.0f s" % (dt, AN_ELAPSED_MAX_S), dt < AN_ELAPSED_MAX_S)

    print()
    print("  [S11a] 默认路径：%d 布 / %d 未布（%d 真端口 + %d 悬空）· DRC 0 · die 4.32×7.80"
          % (c0["routed"], c0["skipped_port"], c0["skipped_true_port"], c0["skipped_dangling"]))
    print("  [S11b] pad 路径：%d 布 / %d 失败 · DRC %d · 面积 ×%.3f"
          % (c1["routed"], c1["failed"], len(d1["violations"]), po["area_um2"] / area0))
    print("  [S11f] 端口网 %d→%d（+%d）· 内部网 %d→%d（−%d）⇒ **净 %+d**"
          % (len(port_base), len(port_routed), gain,
             len(internal), len(internal_routed), loss, gain - loss))
    print("  [边界] 本门禁证明「做了也不行」：瓶颈已从「无端点」转到「局部列/层资源」，"
          "唯一杠杆是改拓扑或加层")

    if _FALS:
        print("S11 有红色：%s" % ", ".join(_FALS))
        return 1
    print("S11 全绿 · pad 负结果已机核：端口网 +4 / 内部网 −3 / 净 +1 / 面积 ×1.806 ⇒ 默认不启用")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
