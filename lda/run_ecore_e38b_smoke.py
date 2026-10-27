#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E38b 门禁（D-226）：**多轮 R&R + 完整密度曲线 + 多层对比（容量研究）**。

## 本门禁守什么
E38a 已证真实符号布局在两层网格上布通率仅 ~3%（主因是布局密度）。E38b 量化「路由技巧能救多少」：
R&R、加层、摊开密度各把布通率抬到多少。核心不是"布通"，是**诚实量化边际收益 + 证明都救不了**。

| # | 守护 | 金标 |
|---|---|---|
| B1 | 控制组 | 稀疏合成 100% 布通（路由器有效） |
| B2 | R&R 原子性 | `routed(R&R) ≥ routed(贪心)`（rip 后必还原，绝不丢网） |
| B3 | 多层单调 | `routability(layers=4) ≥ routability(layers=2)` |
| B4 | 密度单调 | `routability(×4) ≥ routability(×1)`（放大不劣） |

## 探针（必须打红）
- **C1** 用异网终端围死某网 ⇒ 必报未布（非静默丢）

## 诚实口径
实测（K=1）：R&R **3.8%→3.8%**（终端拥挤所致，非占用拥塞 ⇒ R&R 无效）；加 2 层 **3.8%→7.2%**
（约翻倍但远不够）；摊开 ×2/×3/×4 → 5.6/6.8/7.7%（面积 ×4/9/16 仍 <8%）。**结论：路由技巧
（R&R / 加层 / 温和摊开）都救不了，根因是符号级超窄单元密度（cells/node@K1≈0.5），正路是换真实
单元面积。** ⚠️ `max_expand=40000` 在 K≥3 截断长路径 ⇒ 大 K 布通率为**保守下界**。本模块是抽象容量
研究（只报连通性布通率，不产 GDS），与 E38a 的两层真实几何互补。
"""

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import ddroute_rr as R        # noqa: E402
from lda_harness.smoke_kit import make_check    # noqa: E402

AN_ELAPSED_MAX_S = 200.0   # 含 ×1~×4 密度扫描（K=4 ~32s）+ R&R + 层对比，实测见末行

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


def main():
    t0 = time.time()
    print("=" * 78)
    print("E38b · 多轮 R&R + 完整密度曲线 + 多层对比（容量研究）")
    print("=" * 78)

    r = R.route_rr_self_check(verbose=True)

    # B1 控制组
    check("B1 控制组：稀疏合成 100% 布通（路由器有效）",
          r["control_routability"] >= 1.0, "%.0f%%" % (100 * r["control_routability"]))

    # B2 R&R 原子性（绝不丢网）
    check("B2 R&R 原子性：routed(R&R) ≥ routed(贪心)（rip 后必还原，不丢网）",
          r["rr_n_routed"] >= r["greedy_n_routed"],
          "greedy=%d R&R=%d" % (r["greedy_n_routed"], r["rr_n_routed"]))

    # B3 多层单调
    lay = r["layers"]
    check("B3 多层单调：layers=4 布通率 ≥ layers=2（同密度加层不劣）",
          lay[1]["routability"] >= lay[0]["routability"] - 1e-9,
          "2=%.1f%% 4=%.1f%%" % (100 * lay[0]["routability"], 100 * lay[1]["routability"]))

    # B4 密度单调
    dens = r["density"]
    check("B4 密度单调：放大布局布通率非减（放大→不可布通缓解）",
          dens[-1]["routability"] >= dens[0]["routability"] - 1e-9,
          " ".join("×%g→%.1f%%" % (d["spread"], 100 * d["routability"]) for d in dens))

    # 报告（诚实数字）
    print("  :: greedy=%.1f%% · R&R=%.1f%% · layers2/4=%.1f%%/%.1f%% · dens(area×1/4/9/16)=%s"
          % (100 * r["greedy_routability"], 100 * r["rr_routability"],
             100 * lay[0]["routability"], 100 * lay[1]["routability"],
             "/".join("%.1f%%" % (100 * d["routability"]) for d in dens)))

    # C1 围死网必报未布
    from collections import defaultdict
    KIND2 = R.make_layers(2)
    wterm = defaultdict(set)
    wterm[(0, 0)].add("w")
    wterm[(5, 0)].add("w")
    for i in range(1, 5):
        for j in range(3):
            wterm[(i, j)].add("__wall__")
    occ = [{} for _ in KIND2]
    c1 = R._route_net({(0, 0), (5, 0)}, "w", 6, 3, KIND2, occ, wterm, 40000)
    check("C1 突变探针：围死网 ⇒ 必报未布（非静默丢）", c1 is None, "")

    # 自检内部问题（若有）
    check("B5 自检内部无问题（控制/R&R/层/密度 全一致）", r["ok"], (r.get("problems") or [])[:3])

    dt = time.time() - t0
    check("B0 门禁耗时 %.1f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, dt)
    print("-" * 78)
    print("E38b · 通过 %d · 失败 %d · 耗时 %.1f s" % (PASS, FAIL, dt))
    if FAIL:
        print("FAIL — E38b R&R/密度/多层出现问题，按上方 [FAIL] 项修复")
        return 1
    print("E38b 全绿 · R&R 原子不丢网 + 层/密度单调 · 量化结论：R&R/加层/温和摊开都救不了，密度是根")
    return 0


if __name__ == "__main__":
    sys.exit(main())
