#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""WebUI 验证账本(VMM) 端点 + 前端接线 smoke · C 方向（信任机制）

验收：
  - GET /api/verification_ledger 的 vmm 块真实由生产代码推导（非写死常数），
    且对外账本口径自洽、与 README「当前账本」段(严格独立 31 / 降级 1 / 自证桩 23
    / 三类和 55、低置信 13、provenance 6 类宇宙)一致。🔴 总数类断言一律**动态**
    推导（`len(BENCHMARK_DEFS)`），仅「文档账本」显式数字作第二把锁。
  - 前端 public.html 确实接线到该端点（fetch + 渲染 VMM 段），删接线即 FAIL。

运行：python lda/run_webui_verification_ledger_smoke.py
"""
import os
import sys

LDA_ROOT = os.path.dirname(os.path.abspath(__file__))
if LDA_ROOT not in sys.path:
    sys.path.insert(0, LDA_ROOT)

from lda_webui import routes  # 生产路径（非副本）
from lda_harness.benchmarks import BENCHMARK_DEFS

# 动态锚总数：题库增长时自动跟随。🔴 铁律「等价断言 + 会增长集合 = 定时炸弹」
# ⇒ 总数类断言一律动态推导，只有「文档账本」的显式数字保留为第二把锁。
_N_ANCHORS = len(BENCHMARK_DEFS)
# 文档账本（README「当前账本」段 · v0.9.73）：严格独立 31 · 降级 1 · 自证桩 23。
# 由 run_three_class_consistency_smoke.py 守护「README ≡ harness ≡ 端点」三面一致；
# 此处显式数字作第二把锁——账本若漂移必须显式同步，不允许静默通过。
_DOC_TIERS = {"strict_independent": 31, "degraded_ordinal": 1, "self_certified": 23}
_DOC_LOW_CONF = 13


def main() -> int:
    passed = failed = 0

    def check(name, cond, extra=""):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            failed += 1
            print(f"  [FAIL] {name} {extra}")

    print("=== WebUI 验证账本(VMM) 端点 + 前端接线 smoke ===")

    # ---- 1. 生产端点真实推导 ----
    status, body = routes.h_verification_ledger(None, {}, {}, "/api/verification_ledger")
    check("端点返回 200", status == 200, status)
    vmm = (body or {}).get("vmm") or {}
    check("vmm 块存在且非 stale", bool(vmm) and not vmm.get("stale"), vmm.get("error", ""))

    tiers = vmm.get("tiers") or {}
    bp = vmm.get("by_provenance") or {}
    lc = vmm.get("low_confidence_self_authored") or []
    pa = vmm.get("per_anchor") or {}

    # ---- 2. 与 README 文档账本交叉核对（非同式复算，是外部事实锚）----
    check("严格独立 == %d（文档账本）" % _DOC_TIERS["strict_independent"],
          tiers.get("strict_independent") == _DOC_TIERS["strict_independent"], tiers)
    check("降级量级参考 == %d（文档账本）" % _DOC_TIERS["degraded_ordinal"],
          tiers.get("degraded_ordinal") == _DOC_TIERS["degraded_ordinal"], tiers)
    check("自证桩 == %d（文档账本）" % _DOC_TIERS["self_certified"],
          tiers.get("self_certified") == _DOC_TIERS["self_certified"], tiers)
    check("三分类和 == %d 锚总数（动态）" % _N_ANCHORS, sum(tiers.values()) == _N_ANCHORS,
          (tiers, _N_ANCHORS))
    check("逐锚明细 == %d 条（动态）" % _N_ANCHORS, len(pa) == _N_ANCHORS, len(pa))

    # ---- 3. provenance 6 类 + 低置信不变量（必要验证纪律）----
    expect_prov = {"external_textbook", "external_empirical", "independent_cross_check",
                   "design_rule_anchor", "self_authored_closed_form",
                   "self_authored_closed_form_with_check"}
    # 模型定义 6 类；填充集是 6 类宇宙的子集（external_textbook 当前 0 锚亦合法）。
    # 真不变量：不出现未知 provenance + 各类计数和 == 锚总数。
    check("provenance 均为 6 类宇宙子集（无未知来源泄漏）",
          set(bp.keys()) <= expect_prov, list(bp.keys()))
    check("provenance 各类计数和 == %d 锚总数（动态）" % _N_ANCHORS,
          sum(bp.values()) == _N_ANCHORS, (bp, sum(bp.values())))
    check("低置信自写闭式 == %d（必要验证集）" % _DOC_LOW_CONF, len(lc) == _DOC_LOW_CONF, len(lc))
    check("低置信数 == by_provenance[self_authored_closed_form]",
          bp.get("self_authored_closed_form") == len(lc), (bp.get("self_authored_closed_form"), len(lc)))

    # ---- 4. 前端接线（删接线必 FAIL，守「标签≠行为」）----
    html_path = os.path.join(LDA_ROOT, "lda_webui", "static", "public.html")
    html = ""
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
    check("public.html 存在", bool(html))
    check("public.html fetch 到 /api/verification_ledger（接线）",
          'fetch("/api/verification_ledger")' in html, "未找到 fetch 接线")
    check("public.html 渲染 VMM 段（renderVMM 函数）",
          "renderVMM" in html, "未找到 VMM 渲染函数")
    check("public.html 含『可证伪』命题陈述",
          "可证伪" in html, "未找到可证伪陈述")

    print(f"\n结果：{passed} PASS / {failed} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
