#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E38e 门禁（D-229）：**摊开 ×K 的可测边界 + 失败模式诊断（并修正 E38d 的根因判断）**。

## 本门禁守什么
E38d 收尾断言「三要素齐备仍 38.7% ⇒ 瓶颈是网络密度/布线容量 ⇒ 需更大 die（摊开 ×K）」。
E38e 去兑现它：摊开**确实有效**（K=2/面积×4 → 66.67%、K=3/面积×9 → 94.26%，越过 90%），
但**利用率几乎不动**（27.8%→27.9%→32.4%）、`fail_source_blocked` **全程为 0** ⇒
残余失败**全是墙切断**，根因是**贪心 L 型走线的墙效应**，不是 E38d 说的「容量/密度」。

| # | 守护 | 金标 |
|---|---|---|
| B1 | 跨档一致 | K=1 布通率 == E38d 已发布 38.7%（±0.5%）⇒ 没换口径 |
| B2 | 精确性 | K=1 `n_truncated == 0`（截断点只能当下界） |
| B3 | 失败二分恒等 | `fail_source_blocked + fail_walled == n_nets - n_routed` |
| B4 | 摊开改善 | K=2 布通率 ≥ K=1，且 K=2 也零截断 |
| B5 | 成本 ∝ K² | `expanded(K=2)/expanded(K=1)` ∈ [2.5, 6] |
| B6 | **利用率未被摊开缓解** | `|util(K=2) − util(K=1)| ≤ 5pp`（本档核心反直觉事实） |
| B7 | 截断可判（有牙） | 紧预算 `max_expand=2000` ⇒ `n_truncated > 0` 且布通率显著下降 |
| B8 | 搜索器一致 | 符号网格 BFS vs A 星 `|Δ| ≤ 5%` |
| B9 | 自检内部一致 | 跨档/二分/成本/截断/K=3 对拍 全无问题 |
| B10 | K=3 离线点对拍 | 94.26% ≥ 90% 且 面积 ×9 < E37 符号 ×14.6 且 `fail_source_blocked=0` |

## 诚实口径
- **摊开曲线（精确·零截断·同 1359 网）**：K=1 38.70% → K=2/面积×4 66.67% → **K=3/面积×9 94.26%**。
  ⇒ 真实三要素只需 ×3 摊开即越过 90%，且小于 E37 符号密度所需的 ×14.6。
- **K=3 是离线一次性测量（1038 s），本门禁不复算**（复算命令见 `DSPREAD_DISCLOSURE["repro_k3"]`）；
  门禁复算 K=1(~92s) 与 K=2(~350s)。K=4（~10⁹ 扩展）未测。
- 「墙效应」是「无路 + 68% 网格空闲 + `fail_source_blocked=0`」的逻辑必然，但**未逐网定位墙**、
  **未实现破解墙的路由器**。
- 本档净增 0 锚、`claimable=False`：交付的是诊断与判据，不是可签核结果。
"""

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import dspread as S          # noqa: E402
from lda_harness.smoke_kit import make_check   # noqa: E402

AN_ELAPSED_MAX_S = 700.0   # K=1(~92s) + K=2(~350s) + 紧预算探针 + 符号探针，实测见末行

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


def main():
    t0 = time.time()
    print("=" * 78)
    print("E38e · 摊开 ×K 的可测边界 + 失败模式诊断（修正 E38d 根因判断）")
    print("=" * 78)

    r = S.spread_self_check(verbose=True, K_extra=2.0)
    k1, k2, tight = r["k1"], r["extra"], r["tight"]

    check("B1 跨档一致：K=1 布通率 == E38d 已发布 38.7%（±0.5%）",
          abs(k1["routability"] - S.E38D_PUBLISHED_COMBINED) <= 0.005,
          "K=1=%.2f%% 发布值=%.1f%%" % (100 * k1["routability"], 100 * S.E38D_PUBLISHED_COMBINED))
    check("B2 精确性：K=1 零截断（布通率是精确值而非下界）",
          k1["n_truncated"] == 0, "truncated=%d" % k1["n_truncated"])
    check("B3 失败二分恒等：src_blocked + walled == 未布网数",
          k1["fail_source_blocked"] + k1["fail_walled"] == k1["n_nets"] - k1["n_routed"],
          "src=%d wall=%d 未布=%d" % (k1["fail_source_blocked"], k1["fail_walled"],
                                     k1["n_nets"] - k1["n_routed"]))
    ok_k2 = (k2 is not None) and (k2["routability"] >= k1["routability"] - 1e-9) \
        and (k2["n_truncated"] == 0)
    check("B4 摊开改善：K=2（面积 ×4）布通率 ≥ K=1，且零截断",
          ok_k2, "K=1=%.2f%% K=2=%.2f%% trunc2=%s"
          % (100 * k1["routability"], 100 * k2["routability"], k2["n_truncated"]))
    ratio = (k2["expanded"] / k1["expanded"]) if k1["expanded"] else 0.0
    check("B5 成本 ∝ K²：expanded(K=2)/expanded(K=1) ∈ [%.1f, %.1f]"
          % (S.COST_RATIO_MIN, S.COST_RATIO_MAX),
          S.COST_RATIO_MIN <= ratio <= S.COST_RATIO_MAX, "ratio=%.2f" % ratio)
    check("B6 利用率未被摊开缓解：|util(K=2) − util(K=1)| ≤ %.0fpp（本档核心事实）"
          % (100 * S.UTIL_DRIFT_MAX),
          abs(k2["util"] - k1["util"]) <= S.UTIL_DRIFT_MAX,
          "util1=%.1f%% util2=%.1f%%" % (100 * k1["util"], 100 * k2["util"]))
    check("B7 截断可判（有牙）：max_expand=2000 ⇒ 必报截断且布通率显著下降",
          tight["n_truncated"] > 0 and tight["routability"] < k1["routability"] - 0.01,
          "tight=%.1f%% trunc=%d" % (100 * tight["routability"], tight["n_truncated"]))
    check("B8 搜索器一致：符号网格 BFS vs A* |Δ| ≤ 5%",
          abs(r["symbol_bfs"] - r["symbol_astar"]) <= 0.05,
          "BFS=%.2f%% A*=%.2f%%" % (100 * r["symbol_bfs"], 100 * r["symbol_astar"]))
    check("B9 自检内部无问题（跨档/二分/成本/截断/K=3 对拍 全一致）", r["ok"],
          (r.get("problems") or [])[:3])
    k3 = r["k3_offline"]
    check("B10 K=3 离线点对拍：≥90%% 且 面积 ×%.0f < E37 符号 ×%.1f 且 fail_source=0"
          % (k3["area_factor"], S.E37_SYMBOLIC_AREA_FACTOR),
          k3["routability"] >= 0.9 and k3["area_factor"] < S.E37_SYMBOLIC_AREA_FACTOR
          and k3["fail_source_blocked"] == 0,
          "K=3=%.2f%% 面积×%.0f（离线 %.0fs，门禁不复算）"
          % (100 * k3["routability"], k3["area_factor"], k3["seconds"]))

    print("  :: 摊开 ×1 %.1f%% -> ×2（面积 ×4）%.1f%% -> ×3（面积 ×9）%.1f%%（离线）· "
          "util %.1f%% -> %.1f%% -> %.1f%%（几乎不动）· fail_source 全程 0"
          % (100 * k1["routability"], 100 * k2["routability"], 100 * k3["routability"],
             100 * k1["util"], 100 * k2["util"], 100 * k3["util"]))
    print("  :: => 摊开 ×3/面积 ×9 即越过 90%（< E37 符号的 ×14.6）· 但残余失败全是墙切断 ⇒ 根因是墙效应")

    dt = time.time() - t0
    check("B0 门禁耗时 %.1f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, dt)
    print("-" * 78)
    print("E38e · 通过 %d · 失败 %d · 耗时 %.1f s" % (PASS, FAIL, dt))
    if FAIL:
        print("FAIL — E38e 摊开/失败诊断出现问题，按上方 [FAIL] 项修复")
        return 1
    print("E38e 全绿 · 摊开 38.7%->66.7%(×2)->94.3%(×3/面积×9) · 利用率几乎不升 + fail_source 全程 0 "
          "=> 修正 E38d：根因是墙效应，不只靠加面积")
    return 0


if __name__ == "__main__":
    sys.exit(main())
