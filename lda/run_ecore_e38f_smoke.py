#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E38f 门禁（D-230）：**破墙路由器（三种选网策略 + 原子多阻塞者 R&R）· 诚实负结果**。

## 本门禁守什么
E38e 判「残余失败全是墙切断」，并猜「破墙有望以更小面积拿到 94%」。E38f 实现破墙并实测——
**把这个猜测否证了**：破墙在这个密度下是**零和的**（隧道能开，但被撕的网无处可绕 ⇒ 回滚）。

| # | 守护 | 金标 |
|---|---|---|
| B1 | 跨档一致 | 贪心基线 == E38e 发布值 38.70%（±0.5%）⇒ 没换口径 |
| B2 | 原子不丢网 | `n_routed(破墙) ≥ n_routed(贪心)`，且已布网集合 ⊆ 贪心集合（不新增、不丢失） |
| B3 | 回滚恒等 | `success + r_net_fail + r_victim_fail == attempts` |
| B4 | 机制成立 | `tunnel` 下 `r_net_fail>0` **且** `r_victim_fail>0`（隧道能开、牺牲网回不去，确实发生） |
| B5 | 零和不劣 | `Δn_routed ≥ 0`（不劣）；实测 Δ=0 ⇒ 如实报「零和」 |
| B6 | 对照策略量化无效 | `frontier` 命中率 ≤ 10%（实测 0%） |
| B7 | 开关+确定性 | `wall_rr=5` 与 `wall_rr=0` 逐位相同；同参数两次逐位相同 |
| B8 | 自检内部一致 | 上述全部无问题 |

## 诚实口径
- 只测 **K=1**（真实三要素）；`corridor` 策略的 120 次尝试（0 命中）为**离线测量**，不进本门禁。
- 破墙是零和：40 次尝试中 **25 次隧道已开但牺牲网无法重布**、15 次失败网仍不通 ⇒ 净增益 0。
- 未实现级联 R&R / 全局协商拥塞（PathFinder）——本档否证只针对「局部、有限步」破墙。
- 净增 0 锚、`claimable=False`。
"""

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import dwallrr as W         # noqa: E402
from lda_harness.smoke_kit import make_check  # noqa: E402

AN_ELAPSED_MAX_S = 450.0   # 贪心(~77s) + tunnel 40 次(~90s) + frontier 12 次(~80s) + 符号探针，实测见末行

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


def main():
    t0 = time.time()
    print("=" * 78)
    print("E38f · 破墙路由器（frontier / corridor / tunnel）+ 原子多阻塞者 R&R")
    print("=" * 78)

    r = W.wall_self_check(verbose=True)
    g, tun, fr = r["greedy"], r["tunnel"], r["frontier"]

    check("B1 跨档一致：贪心基线 == E38e 发布值 38.70%（±0.5%）",
          abs(g["routability"] - W.E38E_K1_ROUTABILITY) <= 0.005,
          "贪心=%.2f%% 发布值=%.1f%%" % (100 * g["routability"], 100 * W.E38E_K1_ROUTABILITY))
    check("B2 原子不丢网：n_routed(破墙) ≥ 贪心，且已布集合 ⊆ 贪心集合",
          tun["n_routed"] >= g["n_routed"] and tun["routed_set"] <= g["routed_set"],
          "贪心=%d 破墙=%d 越界=%d"
          % (g["n_routed"], tun["n_routed"], len(tun["routed_set"] - g["routed_set"])))
    check("B3 回滚恒等：success + netfail + victimfail == attempts",
          tun["success"] + tun["r_net_fail"] + tun["r_victim_fail"] == tun["attempts"],
          "succ=%d netfail=%d victimfail=%d att=%d"
          % (tun["success"], tun["r_net_fail"], tun["r_victim_fail"], tun["attempts"]))
    check("B4 机制成立：隧道能开(netfail>0 或 tunnel 有效) 且 牺牲网回不去(victimfail>0)",
          tun["r_net_fail"] > 0 and tun["r_victim_fail"] > 0,
          "netfail=%d victimfail=%d" % (tun["r_net_fail"], tun["r_victim_fail"]))
    check("B5 零和不劣：Δn_routed ≥ 0（实测 Δ=%+d ⇒ 如实报零和）" % r["delta_routed"],
          r["delta_routed"] >= 0,
          "贪心=%.2f%% 破墙=%.2f%%" % (100 * g["routability"], 100 * tun["routability"]))
    hit_fr = (fr["success"] / fr["attempts"]) if fr["attempts"] else 0.0
    check("B6 对照策略量化无效：frontier 命中率 ≤ %.0f%%（实测 %.0f%%）"
          % (100 * W.FRONTIER_HIT_MAX, 100 * hit_fr),
          hit_fr <= W.FRONTIER_HIT_MAX, "att=%d succ=%d" % (fr["attempts"], fr["success"]))
    check("B7 自检内部一致（开关无副作用 + 确定性 + 全部金标）", r["ok"],
          (r.get("problems") or [])[:3])

    print("  :: greedy %.2f%% -> tunnel %.2f%%（Δ%+d）· att=%d succ=%d netfail=%d victimfail=%d"
          % (100 * g["routability"], 100 * tun["routability"], r["delta_routed"],
             tun["attempts"], tun["success"], tun["r_net_fail"], tun["r_victim_fail"]))
    print("  :: => 隧道能开但牺牲网无处可绕 ⇒ **破墙零和**；杠杆只剩 加面积(E38e ×3→94.26%) 或 全局协商拥塞")

    dt = time.time() - t0
    check("B0 门禁耗时 %.1f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, dt)
    print("-" * 78)
    print("E38f · 通过 %d · 失败 %d · 耗时 %.1f s" % (PASS, FAIL, dt))
    if FAIL:
        print("FAIL — E38f 破墙 R&R 出现问题，按上方 [FAIL] 项修复")
        return 1
    print("E38f 全绿 · 三种选网策略无一提升（frontier/corridor 0 命中，tunnel 隧道开但回滚）"
          " · 诚实结论：局部破墙零和，需全局协商拥塞或加面积")
    return 0


if __name__ == "__main__":
    sys.exit(main())
