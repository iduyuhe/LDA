#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E37 门禁（D-224）：**DRC/LVS 校验器硬化 + 2 层 L 路由清零负结果**。

## 本门禁守什么
E37 的目标是「给 L 路由加 track 分配以消 baseline DRC」。实测**否定**了这个目标，但把
否定过程做成可复核的门禁——这就是本门禁的价值（诚实负结果 + 校验器硬化）：

| # | 守护对象 | 金标 |
|---|---|---|
| B1 | 校验器等价 `ddrc_lvs.checker_equiv_self_check` | `fast_drc`/`fast_lvs` 与原生 `run_drc`/`run_lvs` **逐位一致**（DRC+LVS 总数与分类一致） |
| B2 | 负结果 `ddetail.track_self_check` | track 分配把 via 违例修到 0；但**拥堵不可行**（每行 clique≫通道，真清零需 ≥5× 面积） |
| B3 | 拥堵量化 `ddetail.congestion_analysis` | 报告每行 clique / 通道容量 / 面积-清零比 |

## 探针要求（C1–C4，每个必须打红）
- **C1** 注入异网重叠金属 ⇒ `fast_drc` 必红 min_spacing
- **C2** 注入悬空过孔 ⇒ `fast_drc` 必红 via_floating
- **C3** 注入过窄金属(<W_MIN) ⇒ `fast_drc` 必红 min_width
- **C4** 删某 2 端网的 M3 段 ⇒ `fast_lvs` 必红 net_disconnected/pin_not_reached

## 诚实口径
track 路由的**总 DRC（913k）≥ 基线（204k）是已知诚实事实**——因为引脚接入压在稠密共享
行/列上，2 层 L 路由在本密度装不下。本门禁**不**要求 track 低于基线（那不是本层次能达到的），
只断言：① 校验器与原生等价且能抓突变；② via 真被修到 0；③ 拥堵量化证明清零需 ≥5× 面积。
清零留给真实 maze/multilayer router（下一段），明确不在此宣称。
"""

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import ddetail as DD          # noqa: E402
from lda_l2.ecore import ddrc_lvs as DL          # noqa: E402
from lda_l2.ecore import dctrl as CT             # noqa: E402
from lda_l2.ecore import dplac as PL             # noqa: E402
from lda_harness.smoke_kit import make_check     # noqa: E402

AN_ELAPSED_MAX_S = 300.0   # 本门禁耗时上界（含 track_route + fast_drc on ~10k shapes，见末行）

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


def _nl():
    return CT.build()["netlist"]


# ---------------------------------------------------------------------------
# B1–B3 · 金标
# ---------------------------------------------------------------------------
def b1_checker_equiv():
    r = DL.checker_equiv_self_check(verbose=True)
    check("B1 校验器等价：fast_drc/fast_lvs 与原生 run_drc/run_lvs 逐位一致（含探针）",
          r["ok"], (r.get("problems") or [])[:3])
    print("  :: DRC=%d (%s) · LVS=%d (%s)"
          % (r["baseline_drc"], r["drc_breakdown"],
             r["baseline_lvs"], r["lvs_breakdown"]))


def b2_track_negative():
    r = DD.track_self_check(verbose=True)
    check("B2 负结果：via 违例=0 且 拥堵不可行（真清零需 ≥5× 面积）",
          r["ok"], (r.get("problems") or [])[:3])
    c = r["congestion"]
    print("  :: base_drc=%d track_drc=%d(信息·不判红) via=%d clique_max=%d cap=%d area×%.1f"
          % (r["baseline_drc"], r["track_drc"], r["track_via_violations"],
             c["clique_max"], c["capacity_per_row"], c["area_to_zero_ratio"]))


def b3_congestion():
    nl = _nl()
    p = PL.place(nl)
    c = DD.congestion_analysis(nl, p)
    # 金标：容量与通道自洽；clique 远大于容量（在本密度）；面积比 = 需要行高/现行高
    ok = (c["capacity_per_row"] >= 1
          and c["channel_um"] > 0
          and c["clique_max"] >= c["capacity_per_row"]
          and abs(c["area_to_zero_ratio"] - c["need_row_pitch_um"] / c["row_pitch_um"]) < 1e-6)
    check("B3 拥堵量化：每行 clique / 通道容量 / 面积-清零比 自洽",
          ok, "clique=%d cap=%d area×%.2f" % (c["clique_max"], c["capacity_per_row"],
                                              c["area_to_zero_ratio"]))
    print("  :: rows=%d row_pitch=%.2fµm channel=%.2fµm  need_row_pitch=%.2fµm"
          % (c["rows"], c["row_pitch_um"], c["channel_um"], c["need_row_pitch_um"]))


# ---------------------------------------------------------------------------
# 🔴 突变探针 C1–C4（独立重注入，直接打 fast checker；每个必须**打红**）
# ---------------------------------------------------------------------------
def c1_short_overlap():
    """C1 · 注入异网同层重叠金属 ⇒ fast_drc 必红 min_spacing。"""
    nl = _nl()
    p = PL.place(nl)
    dr = DD.detail_route(nl, p)
    h = next((s for s in dr.shapes
              if s.layer == DD.L_M3 and (s.x1 - s.x0) >= 3.0 * DL.W_MIN), None)
    if h is None:
        check("C1 突变探针：无足够长 H 段", False, "no H segment")
        return
    bad = list(dr.shapes)
    bad.append(DD._rect(DD.L_M3, h.x0, h.y0 + 0.01, h.x1, h.y0 + 0.01 + DD.W_ROUTE,
                        net="__short__", kind="metal"))
    caught = any(v[0] == "min_spacing" for v in DL.fast_drc(bad)["violations"])
    check("C1 突变探针：异网同层重叠 ⇒ fast_drc 必红 min_spacing", caught, "")


def c2_floating_via():
    """C2 · 注入悬空过孔 ⇒ fast_drc 必红 via_floating。"""
    nl = _nl()
    p = PL.place(nl)
    dr = DD.detail_route(nl, p)
    bad = list(dr.shapes)
    bad.append(DD._rect(DD.L_VIA2, 9999.0, 9999.0, 9999.0 + DD.VIA, 9999.0 + DD.VIA,
                        net="__badvia__", kind="via"))
    caught = any(v[0] == "via_floating" for v in DL.fast_drc(bad)["violations"])
    check("C2 突变探针：悬空过孔 ⇒ fast_drc 必红 via_floating", caught, "")


def c3_narrow_metal():
    """C3 · 注入过窄金属(<W_MIN) ⇒ fast_drc 必红 min_width。"""
    nl = _nl()
    p = PL.place(nl)
    dr = DD.detail_route(nl, p)
    h = next((s for s in dr.shapes
              if s.layer == DD.L_M3 and (s.x1 - s.x0) >= 3.0 * DL.W_MIN), None)
    if h is None:
        check("C3 突变探针：无足够长 H 段", False, "no H segment")
        return
    bad = list(dr.shapes)
    bad.append(DD._rect(DD.L_M3, h.x0, h.y0, h.x1, h.y0 + 0.05,
                        net="__narrow__", kind="metal"))
    caught = any(v[0] == "min_width" for v in DL.fast_drc(bad)["violations"])
    check("C3 突变探针：过窄金属(<W_MIN) ⇒ fast_drc 必红 min_width", caught, "")


def c4_net_break():
    """C4 · 删某 2 端网的 M3 段 ⇒ fast_lvs 必红 net_disconnected/pin_not_reached。"""
    nl = _nl()
    p = PL.place(nl)
    dr = DD.detail_route(nl, p)
    target = None
    for net, pts in dr.net_pins.items():
        if len(pts) == 2 and any(s.net == net and s.layer == DD.L_M3 for s in dr.shapes):
            target = net
            break
    if target is None:
        check("C4 突变探针：无可用 2 端网", False, "no two-pin net with M3")
        return
    bad = [s for s in dr.shapes if not (s.net == target and s.layer == DD.L_M3)]
    r = DL.fast_lvs(bad, dr.net_pins)
    caught = any(pr[0] in ("net_disconnected", "pin_not_reached")
                 and len(pr) > 1 and pr[1] == target for pr in r["problems"])
    check("C4 突变探针：删 2 端网 M3 段 ⇒ fast_lvs 必红 断连", caught, "")


def main():
    t0 = time.time()
    print("=" * 78)
    print("E37 · DRC/LVS 校验器硬化 + 2 层 L 路由清零负结果")
    print("=" * 78)
    b1_checker_equiv()
    b2_track_negative()
    b3_congestion()
    c1_short_overlap()
    c2_floating_via()
    c3_narrow_metal()
    c4_net_break()

    dt = time.time() - t0
    check("B0 门禁耗时 %.1f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, dt)
    print("-" * 78)
    print("E37 · 通过 %d · 失败 %d · 耗时 %.1f s" % (PASS, FAIL, dt))
    if FAIL:
        print("FAIL — E37 校验器硬化/负结果出现问题，按上方 [FAIL] 项修复")
        return 1
    print("E37 全绿 · fast≡native 校验器 + via 清零 + 拥堵不可行负结果 · "
          "3 金标 + 4 突变探针全打红")
    return 0


if __name__ == "__main__":
    sys.exit(main())
