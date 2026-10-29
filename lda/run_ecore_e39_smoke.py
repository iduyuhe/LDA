#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E39 门禁：**多 track 通道路由模型 + 可锚几何判据**（消化 E38g 负结果）。

## 本门禁守什么
E38g 证「单 track 网格零 slack ⇒ 全局协商 collapse 2.9%」。E39 把这条结构性缺口的**根因**
抽成一维可判定的几何律，并机核它：

> **最少平行轨道数 == 通道密度 d**（左边界算法最优性定理：区间图完美 ⇒ 色数==最大团==d）；
> **多 track 可布通 ⇔ T ≥ d**。

⇒ 「单 track 布不通」不再是玄学：`T=1 且 d>1 ⇒ 布通率<1`（E38g 复现），`T≥d ⇒ 1.0`（解锁）。

| # | 守护 | 金标 |
|---|---|---|
| B1 | 实现正确 | `dmtrack_self_check` 全绿（密度三法互证 + 左边界==d + 阈值 + 反向探针 + 确定性） |
| B2 | 密度三法互证 | brute(O(n·span)) == 事件扫描线 == 坐标压缩差分数组，逐实例逐位相等 + 已知答案锚 |
| B3 | 左边界最优性 | 左边界算法轨道数 == 通道密度 d（区间图完美 · 逐实例） |
| B4 | 多 track 阈值 | `T≥d ⇒ 1.0`、`T<d ⇒ <1.0`（阈值恰在 d） |
| B5 | **消化 E38g（headline）** | `T=1 且 d=6 ⇒ 布通率≈1/6<1`（E38g 布不通复现）+ `T=d=6 ⇒ 1.0`（多 track 解锁） |
| B6 | 反向探针（必红） | D1 强制每网独占一条轨 ⇒ 轨道数>d（判据有牙）；D2 漏算一条区间 ⇒ d 变小 |
| B0 | 耗时 | < 阈值（本门禁纯组合、亚秒） |

## 诚实口径
- 一维水平通道模型（不含 2D 竖直约束/单元高度/引脚接入）；整数坐标/单位轨距。
- **不复现 E38g 的 2D 墙效应**（只抽出一维可精确判定的子结构）；不宣称真实芯片可布通率。
- **净增 0 锚**（`claimable=False`）：密度/轨道数是整数精确量、`resid≡0`，硬做 ledger 锚会因平台
  「非登记锚 resid>0 / zero_resid 棘轮=0」被判自证桩而红 ⇒ 本判据以**门禁几何律**形态落地，
  而非伪造非零残差的锚（诚实边界，见 `dmtrack.DMTRACK_DISCLOSURE.why_gate_not_ledger`）。
"""

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import dmtrack as MT      # noqa: E402
from lda_harness.smoke_kit import make_check  # noqa: E402

AN_ELAPSED_MAX_S = 60.0    # 纯组合、亚秒级；阈值留大余量

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


def main():
    t0 = time.time()
    print("=" * 78)
    print("E39 · 多 track 通道路由模型 + 可锚几何判据（消化 E38g 负结果）")
    print("=" * 78)

    r = MT.dmtrack_self_check(verbose=True)

    # B1 总自检
    check("B1 实现正确：dmtrack_self_check 全绿（密度三法/左边界/阈值/反向探针/确定性）",
          r["ok"], (r.get("problems") or [])[:4])

    # B2 密度三法互证（逐实例）+ 已知答案锚
    all_agree = all(c["agree"] for c in r["density_checks"])
    known_ok = (MT.brute_max_overlap([(0, 2), (2, 4), (0, 4)]) == 2
                and MT.brute_max_overlap([(0, 3), (1, 4), (2, 5), (3, 6)]) == 3)
    check("B2 密度三法互证（brute==sweep==diff_array 逐实例 ∧ 已知答案 d=2/3）",
          all_agree and known_ok,
          [(c["k"], c["brute"], c["sweep"], c["diff"]) for c in r["density_checks"] if not c["agree"]] or "all agree")

    # B3 左边界最优性（轨道数 == d，逐实例）
    all_opt = all(c["optimal"] for c in r["left_edge_checks"])
    check("B3 左边界最优性：轨道数 == 通道密度 d（区间图完美 · 逐实例）",
          all_opt,
          [(c["k"], c["d"], c["tracks"]) for c in r["left_edge_checks"] if not c["optimal"]] or "all optimal")

    # B4 多 track 阈值（T≥d→1.0，T<d→<1.0）
    d6 = r["d6"]
    thr = r["thresholds"]
    ok_ge = all(t["routability"] == 1.0 for t in thr if t["T"] >= d6)
    ok_lt = all(t["routability"] < 1.0 for t in thr if t["T"] < d6)
    check("B4 多 track 阈值：T≥d⇒1.0 ∧ T<d⇒<1.0（d=%d；阈值=%s）"
          % (d6, [(t["T"], round(t["routability"], 3)) for t in thr]),
          ok_ge and ok_lt)

    # B5 headline：E38g 复现（T=1<1）+ 多 track 解锁（T=d=1.0）
    check("B5 🔴 消化 E38g：T=1 且 d=%d ⇒ 布通率 %.3f <1（单 track 布不通复现）∧ T=d ⇒ %.3f ==1.0（多 track 解锁）"
          % (d6, r["e38g_T1_routability"], r["unlock_Td_routability"]),
          r["e38g_reproduced"] and r["unlock_Td_routability"] == 1.0)

    # B6 反向探针（必红）
    p1 = r["probes"]["d1_forced"]
    p2 = r["probes"]["d2"]
    check("B6 反向探针：D1 强制每网独占一条轨⇒轨道数(%d)>d(%d) ∧ D2 漏算一条区间⇒d 变小(%d<%d)"
          % (p1["forced_tracks"], p1["d"], p2["tampered_d"], p2["true_d"]),
          p1["detected"] and p2["detected"])

    dt = time.time() - t0
    check("B0 门禁耗时 %.2f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, dt)
    print("-" * 78)
    print("E39 · 通过 %d · 失败 %d · 耗时 %.2f s" % (PASS, FAIL, dt))
    if FAIL:
        print("FAIL — E39 多 track 几何判据出现问题，按上方 [FAIL] 项修复")
        return 1
    print("E39 全绿 · 多 track 通道路由几何律：轨道数==密度 d（左边界最优性）· T=1 复现 E38g 布不通 · "
          "T≥d 解锁 100% · 净增 0 锚（整数精确量 resid≡0，以门禁几何律形态落地）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
