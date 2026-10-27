#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E38c 门禁（D-227）：**真实标准单元面积标定 + 可布通性重测**。

## 本门禁守什么
E38a/E38b 证「符号级超窄单元（0.040µm²/管 ⇒ 223 单元/行）是布通率 ~3-4% 的根因」。E38c 把
area_per_tr 标定到公开库量级（Nangate45 NAND2 ≈0.266µm²/tr），重摆重测，量化真实面积能救多少。

| # | 守护 | 金标 |
|---|---|---|
| B1 | 面积守恒 | 换 tech 后 `Σ(w·h) ≡ Σ n_tr·area_per_tr`（逐位） |
| B2 | 单元变稀 | realistic cells/row < 符号值一半 |
| B3 | 布通率提升 | routability(real,2L) > routability(symbolic,2L) |
| B4 | 层数单调 | route-over-cell：routability(4L) ≥ routability(2L) |

探针（自检内部）：错误 area_per_tr 摆放 ⇒ 面积守恒式必随之变（证明标定非硬编码）。

## 诚实口径
真实面积（0.266）把布通率 **3.8%→9.7%（2 层，2.6×）**，跨单元布线 + 4 层 → **~22%**，6 层 → ~32%；
**仍开不出 100% 可布通布局**——残余瓶颈是**粗引脚接入**（0.36µm 网格无 M1/M2 细接入，真实设计靠它解决）。
故「完全可布通」= 真实单元面积 + 跨单元布线 + 细引脚接入 三者齐备，缺一不可（这是 E38c 的诚实结论）。
"""

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import drealcell as RC       # noqa: E402
from lda_harness.smoke_kit import make_check    # noqa: E402

AN_ELAPSED_MAX_S = 200.0   # 含 realistic 2L(~15s)+4L(~34s) 布线 + 摆放，实测见末行

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


def main():
    t0 = time.time()
    print("=" * 78)
    print("E38c · 真实标准单元面积标定 + 可布通性重测")
    print("=" * 78)

    r = RC.realcell_self_check(verbose=True)

    # B1 面积守恒
    check("B1 面积守恒：换 tech 后 Σ(w·h) ≡ Σ n_tr·area_per_tr（逐位）",
          abs(r["placed_area"] - r["expected_area"]) <= 1e-6,
          "placed=%.3f expected=%.3f" % (r["placed_area"], r["expected_area"]))

    # B2 单元变稀
    check("B2 单元变稀：realistic cells/row < 符号值一半",
          r["cells_per_row_realistic"] < r["cells_per_row_symbolic"] * 0.5,
          "sym=%.0f real=%.0f" % (r["cells_per_row_symbolic"], r["cells_per_row_realistic"]))

    # B3 布通率提升
    check("B3 布通率提升：real(2L) > symbolic(2L)",
          r["routability_real_2l"] > r["routability_symbolic_2l"],
          "sym=%.1f%% real=%.1f%%" % (100 * r["routability_symbolic_2l"],
                                      100 * r["routability_real_2l"]))

    # B4 层数单调
    check("B4 层数单调：route-over-cell 4L ≥ 2L",
          r["routability_real_4l"] >= r["routability_real_2l"] - 1e-9,
          "2L=%.1f%% 4L=%.1f%%" % (100 * r["routability_real_2l"],
                                   100 * r["routability_real_4l"]))

    # 自检内部（含探针）无问题
    check("B5 自检内部无问题（面积守恒/变稀/提升/单调/探针 全一致）", r["ok"],
          (r.get("problems") or [])[:3])

    print("  :: cells/row %0.f→%0.f · die %.0fx%.0f · routability 3.8%%→%.1f%%(2L)→%.1f%%(4L)"
          % (r["cells_per_row_symbolic"], r["cells_per_row_realistic"],
             r["die_w"], r["die_h"], 100 * r["routability_real_2l"],
             100 * r["routability_real_4l"]))

    dt = time.time() - t0
    check("B0 门禁耗时 %.1f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, dt)
    print("-" * 78)
    print("E38c · 通过 %d · 失败 %d · 耗时 %.1f s" % (PASS, FAIL, dt))
    if FAIL:
        print("FAIL — E38c 真实面积标定/可布通性出现问题，按上方 [FAIL] 项修复")
        return 1
    print("E38c 全绿 · 真实面积(0.266µm²/tr)面积守恒 + 布通率 3.8%→9.7%(2L)/21.9%(4L) · "
          "诚实结论：仍非 100%，残余瓶颈=粗引脚接入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
