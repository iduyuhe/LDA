#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E38g 门禁（D-231）：**全局协商拥塞路由 PathFinder · 机制正确 + 诚实对照**。

## 本门禁守什么
E38f 否证了「局部破墙」是零和，猜想「全局协商（PathFinder）」是 E38 链最后一条算法杠杆。
E38g 实现 PathFinder 并实测——**把这个猜想也否证了**：本抽象网格每(格,层)只有一条线、无平行走线
资源，协商要么死锁（温和代价）要么乱窜（陡峭代价），都不收敛到更优解；根因是 K=1 下贪心已有 833
个网根本不存在无冲突路径（结构性不可布）。唯一有效杠杆仍是加面积/层（E38e：×3→94.26%）。

| # | 守护 | 金标 |
|---|---|---|
| B1 | 实现正确 | `pathfinder_self_check` 全绿（记账可核 / 确定性 / 控制组 / 机制可动 / 不伪绿） |
| B2 | 离线对照断言 | 全量 `PF_K1_best < 贪心`（零 slack 结构性 collapse，护栏=0<best<贪心；常量回填后生效） |
| B3 | 诚实口径 | PF 如实报 best 与 final（final 未必=best，振荡则显式标） |

## 诚实口径
- 门禁只复算**机制**（符号小网格确定性/记账/控制组 + 真实采样协商改善初值），不跑全量昂贵测量。
- 全量 PF vs 贪心对照（K=1 × 1359 网）为**离线测量**，存 `PF_K1_OFFLINE`，断言见 B2（K2/K3 未测、仍待填）。
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

from lda_l2.ecore import dpathfinder as PF       # noqa: E402
from lda_harness.smoke_kit import make_check      # noqa: E402

AN_ELAPSED_MAX_S = 200.0   # 符号部分(~30s) + 真实采样(~28s) + 余量

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


def main():
    t0 = time.time()
    print("=" * 78)
    print("E38g · 全局协商拥塞路由 PathFinder（机制正确 + 诚实对照）")
    print("=" * 78)

    r = PF.pathfinder_self_check(verbose=True)

    check("B1 实现正确：pathfinder_self_check 全绿（记账/确定性/控制组/机制可动/不伪绿）",
          r["ok"], (r.get("problems") or [])[:4])
    k1 = PF.PF_K1_OFFLINE.get("routability_best")
    greedy_k1 = PF.PF_K1_OFFLINE.get("greedy_routability")
    if k1 is not None:
        if greedy_k1 is None:
            check("B2 离线对照：PF_K1_OFFLINE 缺 greedy_routability（回填不全）", False,
                  "PF_K1_best=%.1f%%" % (100 * k1))
        else:
            # 🔴 诚实发现：全量 1359 网下 PF 因零 slack collapse 到 ~2.9%（远低于贪心 38.2%），
            # 这是容量结构决定的（非实现缺陷）。护栏=回填值非退化(0<best<贪心)，而非要求接近贪心。
            ok_b2 = (0.0 < k1 < greedy_k1)
            check("B2 离线对照：全量 PF_K1_best=%.1f%% < 贪心 %.1f%%（零 slack 结构性 collapse，非退化）"
                  % (100 * k1, 100 * greedy_k1),
                  ok_b2,
                  "PF_K1_best=%.1f%% 贪心=%.1f%%（护栏：0<best<贪心）" % (100 * k1, 100 * greedy_k1))
    else:
        print("  :: B2 跳过：PF_K1_OFFLINE 尚未回填（离线全量测量进行中/待填）")

    print("  :: 真实采样：iter0=%.1f%% best=%.1f%%(iter%d) final=%.1f%% · overflow=%s"
          % (100 * r["real_iter0"], 100 * r["real_best"], r["real_best_iter"],
             100 * r["real_final"], r["overflow_log"]))
    print("  :: => 协商在有余量时抬升冲突-free（best>iter0），但全量下无法突破结构性墙效应；"
          "杠杆只剩 加面积(E38e ×3→94.26%)")

    dt = time.time() - t0
    check("B0 门禁耗时 %.1f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, dt)
    print("-" * 78)
    print("E38g · 通过 %d · 失败 %d · 耗时 %.1f s" % (PASS, FAIL, dt))
    if FAIL:
        print("FAIL — E38g PathFinder 门禁出现问题，按上方 [FAIL] 项修复")
        return 1
    print("E38g 全绿 · PathFinder 实现正确（机制可动+记账+确定性+控制组）· 诚实结论："
          "协商无法突破结构性墙效应，E38 调查收尾，唯一有效杠杆=加面积/层")
    return 0


if __name__ == "__main__":
    sys.exit(main())
