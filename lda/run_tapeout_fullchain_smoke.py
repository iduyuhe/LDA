#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""流片全链路收口 smoke（DRC → 几何 DRC → 工艺角 → 性能角 → 寄生 → LVS）· v0.9.60

**为什么需要它**：`run_tapeout_smoke.py` 只覆盖了 S1-S3（参数级 DRC + DRC 工艺角）
和 S5 接口，**S3.5 寄生 / S3.6 几何 DRC / S3b 性能角 / S4 LVS 这四段的「在管道里
真的跑起来」没有端到端证据**——它们各自有独立 smoke，但「管道接对了没有」没人测。
本 smoke 把四段实跑路径逐条钉死，并对**每一条**配反向个案（证明判据会响）。

补齐的三处链路缺口（2026-09-08 DRC 全链路盘点实测确认）：
- **S3.6 几何级 DRC 缺失**：管道此前只有**参数级** DRC（查器件窗口参数），
  传了 GDS 也只做寄生、不做几何检查 ⇒ 版图多边形的最小线宽/间距/面积无人查。
- **零元素 GDS 会假绿**：层次化 GDS 若未展开引用（v0.9.33 P0-1 血案），
  解析出 0 元素、什么都没查却 all_pass=True。此处显式判 FAIL 并诚实标注。
- **S3b 性能角缺失**：管道里的「工艺角」只是**缩放参数后复检 DRC**（规则角），
  `corner_performance` 的**性能漂移**评估（FSR/f01 随角落漂移）从未接入管道。

**诚实边界（钉死语义，防后人误读）**：几何寄生越界**不进 accepted 硬门**
（设计侧几何护栏，不替代 foundry 签核）——本 smoke 显式断言这一语义。

CI core 136→137。
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA = os.path.dirname(_HERE)
for _p in (_LDA, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lda_pdk.tapeout_pipeline import (                            # noqa: E402
    run_tapeout_pipeline, tapeout_to_dict,
)
from lda_harness.lvs_anchor import build_lvs_case                 # noqa: E402
from lda_harness.benchmarks import BENCHMARK_DEFS                 # noqa: E402
from lda_l2.gds_export import (                                   # noqa: E402
    boundary, gds_library, layout_elements, path,
)

_FAILED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> bool:
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}" + (f"  |  {detail}" if detail else ""))
    if not cond:
        _FAILED.append(name)
    return cond


DEV = {"RingAddDrop": {"R": 10.0, "gap": 0.3, "width": 0.5}}
GOOD_GDS = gds_library("LDA-CHAIN", {
    "RingAddDrop": layout_elements("RingAddDrop", DEV["RingAddDrop"])})
PERF_OK = [{"device": "RingResonator", "bid": "B4",
            "params": dict(BENCHMARK_DEFS["B4"]["default_params"]),
            "tol_pct": 15.0, "domain": "photon"}]


def main() -> int:
    print("=== 流片全链路收口 smoke（v0.9.60）===")

    # ── ① 全输入：四段全部**实跑**且 ACCEPT ────────────────────────────
    link, placement, routes = build_lvs_case("consistent")
    r = run_tapeout_pipeline(DEV, gds=GOOD_GDS, link=link,
                             placement=placement, routes=routes,
                             perf_cases=PERF_OK)
    check("① 全输入 ACCEPT（DRC+角+几何DRC+性能角+LVS 五段全过）",
          r.accepted, f"accepted={r.accepted}")
    check("①-b S3.5 寄生实跑（非跳过，total_r>0）",
          r.parasitic_result.total_r_ohm > 0
          and "跳过" not in r.parasitic_result.honest_note,
          f"R={r.parasitic_result.total_r_ohm:.2f}Ω "
          f"C={r.parasitic_result.total_c_ff:.3f}fF")
    check("①-c S3.6 几何 DRC 实跑且元素数>0",
          r.geometry_drc_result.passed and r.geometry_drc_result.n_elements > 0
          and "跳过" not in r.geometry_drc_result.honest_note,
          f"n={r.geometry_drc_result.n_elements} passed={r.geometry_drc_result.passed}")
    check("①-d S3b 性能角实跑（漂移>0，非恒零）",
          len(r.perf_corners) == 1 and r.perf_corners[0].passed
          and r.perf_corners[0].max_drift_pct > 0,
          f"drift={r.perf_corners[0].max_drift_pct:.3f}%")
    check("①-e S4 LVS 实跑 ACCEPT",
          r.lvs_result.get("verdict") == "ACCEPT", str(r.lvs_result.get("verdict")))
    check("①-f honest_note 逐段披露实跑/跳过（五段键名齐备）",
          all(k in r.honest_note for k in ("S3.5", "S3.6", "S3b", "S4")),
          r.honest_note[:150])

    # ── ② 反向：几何版图违规 → S3.6 FAIL 且阻断 accepted ────────────────
    bad = gds_library("BAD", {"thin": [boundary(
        1, [(0.0, 0.0), (5.0, 0.0), (5.0, 0.04), (0.0, 0.04)])]})
    r2 = run_tapeout_pipeline(DEV, gds=bad)
    check("② 几何违规（线宽 0.04µm）→ S3.6 FAIL 且 accepted=False",
          (not r2.geometry_drc_result.passed) and (not r2.accepted),
          f"geom={r2.geometry_drc_result.passed} accepted={r2.accepted} "
          f"v={r2.geometry_drc_result.violations[:1]}")

    # ── ③ 反向：零元素 GDS（层次化未展开）→ 判 FAIL 不假绿 ───────────────
    r3 = run_tapeout_pipeline(DEV, gds=gds_library("EMPTY", {"TOP": []}))
    check("③ 零元素 GDS → S3.6 FAIL（防 v0.9.33 层次化假绿）且 accepted=False",
          (not r3.geometry_drc_result.passed) and (not r3.accepted)
          and r3.geometry_drc_result.n_elements == 0,
          f"n={r3.geometry_drc_result.n_elements} accepted={r3.accepted}")

    # ── ④ 反向：LVS 错连 → REJECT 且阻断 accepted ───────────────────────
    _, pl2, rt2 = build_lvs_case("misconnect")
    _, _, _ = pl2, rt2, _
    link_m, placement_m, routes_m = build_lvs_case("misconnect")
    r4 = run_tapeout_pipeline(DEV, link=link_m, placement=placement_m,
                              routes=routes_m)
    check("④ LVS 错连 → REJECT 且 accepted=False",
          r4.lvs_result.get("verdict") == "REJECT" and (not r4.accepted),
          f"{r4.lvs_result.get('verdict')} accepted={r4.accepted}")

    # ── ⑤ 反向：性能角收紧 tol → FAIL 且阻断 accepted ────────────────────
    r5 = run_tapeout_pipeline(DEV, perf_cases=[
        {"device": "RingResonator", "bid": "B4",
         "params": dict(BENCHMARK_DEFS["B4"]["default_params"]),
         "tol_pct": 0.01, "domain": "photon"}])
    check("⑤ 性能角 tol=0.01% → FAIL 且 accepted=False（死标量判决）",
          (not r5.perf_corners[0].passed) and (not r5.accepted)
          and r5.perf_corners[0].max_drift_pct > 0.01,
          f"drift={r5.perf_corners[0].max_drift_pct:.4f}% accepted={r5.accepted}")

    # ── ⑥ 反向：未登记 bid → 显式记错、不静默、阻断 accepted ──────────────
    r6 = run_tapeout_pipeline(DEV, perf_cases=[
        {"device": "XX", "bid": "B99", "params": {"x": 1.0}, "tol_pct": 10.0}])
    check("⑥ 未登记 bid → error 非空且 accepted=False（不静默）",
          bool(r6.perf_corners[0].error) and (not r6.accepted),
          str(r6.perf_corners[0].error)[:60])

    # ── ⑦ 反向：不传 gds / perf_cases → 诚实 SKIP，不阻断 ─────────────────
    r7 = run_tapeout_pipeline(DEV)
    check("⑦ 不传 gds/perf → S3.6、S3b 诚实跳过且 accepted 不受影响",
          "跳过" in r7.geometry_drc_result.honest_note
          and len(r7.perf_corners) == 0 and r7.accepted,
          f"accepted={r7.accepted} n_perf={len(r7.perf_corners)}")

    # ── ⑧ 语义钉死：几何寄生越界**不进** accepted 硬门（防后人误改）─────────
    # 注意：金属互连在 RC 表里是 layer=11（见 parasitic_rc.DEFAULT_RC_SHEET），
    # 不是 GDS 常量 LIB_LAYER_METAL=3；用 3 会被判「未知层·R 未建模」=0Ω。
    long_metal = gds_library("LONG", {
        "m": [path(11, 0.5, [(0.0, 0.0), (20000.0, 0.0)])]})
    r8 = run_tapeout_pipeline(DEV, gds=long_metal)
    check("⑧ 寄生越界 → parasitic.passed=False 但 accepted 仍 True"
          "（几何护栏，非 foundry 签核）",
          (not r8.parasitic_result.passed) and r8.accepted,
          f"para={r8.parasitic_result.passed} R={r8.parasitic_result.total_r_ohm:.0f}Ω "
          f"accepted={r8.accepted}")

    # ── ⑨ 契约：tapeout_to_dict 输出新字段（WebUI/API 消费路径）─────────────
    d = tapeout_to_dict(r)
    check("⑨ tapeout_to_dict 含 geometry_drc_result / perf_corners 两段",
          isinstance(d.get("geometry_drc_result"), dict)
          and d["geometry_drc_result"].get("passed") is True
          and len(d.get("perf_corners", [])) == 1,
          f"keys={[k for k in ('geometry_drc_result','perf_corners') if k in d]}")

    print("\n=== 流片全链路收口 smoke: "
          + ("ALL GREEN" if not _FAILED else f"{len(_FAILED)} FAIL") + " ===")
    if _FAILED:
        for n in _FAILED:
            print("   FAIL:", n)
    return 0 if not _FAILED else 1


if __name__ == "__main__":
    sys.exit(main())
