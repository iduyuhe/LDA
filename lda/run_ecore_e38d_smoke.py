#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E38d 门禁（D-228）：**细引脚接入逃逸 + 现实线距联调 + 容量结论**。

## 本门禁守什么
E38c 把布通率抬到 9.7%（真实单元，2 层），残余瓶颈判为「粗引脚接入」。E38d 补上最后两件真实条件
（细引脚接入逃逸 + 现实线距 0.24µm）并联调，量化「三要素齐备能到多少」。

| # | 守护 | 金标 |
|---|---|---|
| B1 | 引脚接入单调 | routability(r=4) ≥ routability(r=0) |
| B2 | 层数单调 | 跨单元布线 routability(4L) ≥ (2L) |
| B3 | 线距单调 | routability(0.24 细) ≥ (0.36 粗) |
| B4 | 联调 ≥ 单要素 | 三要素齐备 ≥ 仅真实单元面积 |
| B5 | **诚实** | 联调布通率仍 < 90%（容量受限，非 100%，防伪绿） |

## 诚实口径
三要素齐备（真实单元 0.266 + 细引脚接入 r=4 + 现实线距 0.24 + 4 层 + 跨单元布线）联调 → **~38.7%**，
vs 符号 3.8% / 仅真实单元 9.7%。**仍 <100%** —— 瓶颈已从「引脚接入/线距」迁到**网络密度/布线容量**
（1359 网 vs 46µm die）。要真正可布通需**更大的 die（摊开 ×K，E37 的 ×N 面积）**；真实三要素下所需
K 应远小于 E37 符号密度下的 ×14.6。这是 E38d 的诚实结论。
"""

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import dpinaccess as PA       # noqa: E402
from lda_harness.smoke_kit import make_check    # noqa: E402

AN_ELAPSED_MAX_S = 300.0   # 含联调真实布线(~75s)+仅真实单元(~15s)+符号单调探针，实测见末行

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


def main():
    t0 = time.time()
    print("=" * 78)
    print("E38d · 细引脚接入逃逸 + 现实线距联调 + 容量结论")
    print("=" * 78)

    r = PA.pinaccess_self_check(verbose=True)

    check("B1 引脚接入单调：routability(r=4) ≥ routability(r=0)",
          r["access_r4"] >= r["access_r0"] - 1e-9,
          "r0=%.1f%% r4=%.1f%%" % (100 * r["access_r0"], 100 * r["access_r4"]))
    check("B2 层数单调：跨单元布线 4L ≥ 2L",
          r["layers_4l"] >= r["layers_2l"] - 1e-9,
          "2L=%.1f%% 4L=%.1f%%" % (100 * r["layers_2l"], 100 * r["layers_4l"]))
    check("B3 线距单调：0.24µm(细) ≥ 0.36µm(粗)",
          r["pitch_real"] >= r["access_r4"] - 1e-9,
          "粗=%.1f%% 细=%.1f%%" % (100 * r["access_r4"], 100 * r["pitch_real"]))
    check("B4 联调 ≥ 单要素：三要素齐备 ≥ 仅真实单元",
          r["combined"] >= r["real_only_2l"] - 1e-9,
          "仅真实单元=%.1f%% 联调=%.1f%%" % (100 * r["real_only_2l"], 100 * r["combined"]))
    check("B5 诚实：联调布通率仍 <90%（容量受限，非 100%）",
          r["combined"] < 0.9, "%.1f%%" % (100 * r["combined"]))
    check("B6 自检内部无问题（三单调/联调/诚实 全一致）", r["ok"],
          (r.get("problems") or [])[:3])

    print("  :: 符号 %.1f%% -> 仅真实单元 %.1f%% -> 三要素联调 %.1f%%（die %.0fx%.0f）· 仍非 100%%"
          % (100 * r["access_r0"], 100 * r["real_only_2l"], 100 * r["combined"],
             r["die_w"], r["die_h"]))

    dt = time.time() - t0
    check("B0 门禁耗时 %.1f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, dt)
    print("-" * 78)
    print("E38d · 通过 %d · 失败 %d · 耗时 %.1f s" % (PASS, FAIL, dt))
    if FAIL:
        print("FAIL — E38d 引脚接入/线距联调出现问题，按上方 [FAIL] 项修复")
        return 1
    print("E38d 全绿 · 三要素单调 + 联调 38.7% · 诚实结论：仍未可布通，瓶颈=网络密度/布线容量，需更大 die")
    return 0


if __name__ == "__main__":
    sys.exit(main())
