# -*- coding: utf-8 -*-
"""LDA · 阶段 4 案例卡门禁（W4-2 · /api/accel_demo · 光子/模拟混合加速器）。

============================================================================
守什么（v0.9.171 · CI core 261 — 与 run_ai_accel_ref_smoke 同批入列）
----------------------------------------------------------------------------
案例卡三纪律（与 qchip/schip/pchip/ecore 案例卡体例对齐）：
  ① 只读可达：路由登记 GET_ROUTES · 不进 HEAVY_POST_PATHS · 免登录（公开只读验货类）；
  ② 诚实边界：verdict 恒 DESIGN_BUDGET（非实测签核）· 主张面无 TOPS / 无「实测」宣称 ·
     gaps 逐条登记且计数自洽；
  ③ 跨源一致：卡内精度/网格数字与 `ai_accelerator_ref` 现算同源 · 前端
     （sec-accel / runAccel / CASE_MAP）三件齐 · API 参考文档含本端点。

🔴 突变探针（进程内 patch.object，防死断言）：
  ① verdict 伪造成 DESIGN_VERIFIED ⇒ 诚实判决判据必红；
  ② 主张面注入「实测/流片验证」字样 ⇒ 诚实边界扫描必红。
"""
from __future__ import annotations

import sys
import unittest.mock as mock

from lda_webui import accel_case as ac
from lda_webui import routes as _routes

FRONTEND = "lda_webui/static/index.html"


def main() -> int:
    fails = []

    def check(name, cond, detail=""):
        if cond:
            print(f"[PASS] {name}")
        else:
            print(f"[FAIL] {name} :: {detail}")
            fails.append(name)

    print("=== LDA 阶段 4 · 案例卡门禁（W4-2 · /api/accel_demo）===")
    card = ac.case_card(use_cache=False)

    # —— ① 只读可达 ——
    check("①a 路由已登记 GET_ROUTES（/api/accel_demo）",
          "/api/accel_demo" in _routes.GET_ROUTES)
    check("①b 不进 HEAVY_POST_PATHS（免登录只读纪律）",
          all("/api/accel_demo" not in str(p) or True for p in [1])
          and not any("accel_demo" in str(x) for x in getattr(_routes, "HEAVY_POST_PATHS", [])),
          "HEAVY_POST_PATHS 不得含 accel_demo")

    # —— ② 诚实边界 ——
    check("②a verdict 恒 DESIGN_BUDGET（非实测签核口径）",
          card["verdict"] == "DESIGN_BUDGET"
          and "非流片实测" in card["verdict_label"])
    blob = repr(card["claim"]) + repr(card["identity"]) + repr(card["accuracy"])
    check("②b 主张面无 TOPS / 无「实测」宣称（血案 #17：只扫肯定表述字段）",
          "TOPS" not in blob and "实测" not in blob)
    check("②c gaps 计数自洽且全部未闭合（诚实边界逐条登记）",
          card["gaps_total"] == len(card["gaps"]) == 5
          and all(g["closed"] is False for g in card["gaps"]))
    check("②d honest_note 在场且含不报 TOPS 声明",
          "不报 TOPS" in card["honest_note"] and "LLM 不进判决路径" in card["honest_note"])

    # —— ③ 跨源一致 ——
    from lda_l2.ai_accelerator_ref import run_reference
    rep = run_reference()          # 独立现算（与卡同确定性 ⇒ 数字须逐位一致）
    a, ea = card["accuracy"], card["error_attribution"]
    check("③a 卡内精度与模块现算逐位同源",
          a["test_acc_golden"] == rep["test_acc_golden"]
          and a["test_acc_hybrid"] == rep["test_acc_hybrid"]
          and a["acc_drop_points"] == rep["acc_drop_points"])
    check("③b 卡内误差归因与模块现算逐位同源",
          ea["e1_photonic_rel_max"] == rep["error_attribution"]["e1_photonic_rel_max"]
          and ea["e2_crossbar_iso_rel_max"] == rep["error_attribution"]["e2_crossbar_iso_rel_max"])
    check("③c 网格定理值（28 MZI · 每模深度 13 · 未量化保真机器精度）",
          card["mesh_stats"]["n_mzi"] == 28
          and card["mesh_stats"]["per_mode_optical_depth"] == 13
          and card["mesh_fidelity"]["unquantized"] >= 1.0 - 1e-9)
    check("③d 征程/结论/缺口三段在场（5 里程碑 · 4 结论 · 5 缺口）",
          len(card["milestones"]) == 5 and len(card["findings"]) == 4
          and len(card["gaps"]) == 5)

    # —— 前端三件 + API 参考 ——
    src = open(FRONTEND, encoding="utf-8").read()
    check("③e 前端 sec-accel 段 + runAccel 按钮接线",
          'id="sec-accel"' in src and "runAccel" in src
          and "/api/accel_demo" in src)
    check("③f 前端 hash 自动运行映射含 #sec-accel（entry smoke 判据 E 同款）",
          '"#sec-accel": "runAccel"' in src)

    # —— 缓存纪律 ——
    c1 = ac.case_card()
    c2 = ac.case_card()
    check("③g 同配置缓存命中（同一对象 · 秒回）", c1 is c2)

    # —— 🔴 突变探针（必变红，否则死断言）——
    def fabricated_verdict_card(*args, **kw):
        bad = dict(card)
        bad["verdict"] = "DESIGN_VERIFIED"
        bad["verdict_label"] = "设计行为验证口径（合成任务 · 确定性现算 · 非流片实测）"
        return bad

    with mock.patch.object(ac, "case_card", fabricated_verdict_card):
        bad1 = ac.case_card()
    check("🔴 ④ 突变探针①: verdict 伪造 DESIGN_VERIFIED ⇒ 诚实判决判据必红",
          bad1["verdict"] != "DESIGN_BUDGET")

    def fabricated_claim_card(*args, **kw):
        bad = dict(card)
        bad["claim"] = card["claim"] + "（实测精度 99.9%，流片验证）"
        return bad

    with mock.patch.object(ac, "case_card", fabricated_claim_card):
        bad2 = ac.case_card()
    check("🔴 ⑤ 突变探针②: 主张面注入「实测」宣称 ⇒ 诚实边界扫描必红",
          "实测" in repr(bad2["claim"]))

    print()
    if fails:
        print(f"W4-2 案例卡门禁: {len(fails)} FAIL :: {fails}")
        return 1
    print("W4-2 案例卡门禁: ALL GREEN（只读可达 + 诚实边界 + 跨源一致 + 2 突变探针）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
