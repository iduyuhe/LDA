#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""WebUI 验证账本(VMM) 端点 + 前端接线 smoke · C 方向（信任机制）

验收：
  - GET /api/verification_ledger 的 vmm 块真实由生产代码推导（非写死常数），
    且对外账本口径自洽、与 README 账本(26/1/25、低置信 15、provenance 6 类)一致。
  - 前端 public.html 确实接线到该端点（fetch + 渲染 VMM 段），删接线即 FAIL。

运行：python lda/run_webui_verification_ledger_smoke.py
"""
import os
import sys

LDA_ROOT = os.path.dirname(os.path.abspath(__file__))
if LDA_ROOT not in sys.path:
    sys.path.insert(0, LDA_ROOT)

from lda_webui import routes  # 生产路径（非副本）


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
    check("严格独立 == 26（文档账本）", tiers.get("strict_independent") == 26, tiers)
    check("降级量级参考 == 1（文档账本）", tiers.get("degraded_ordinal") == 1, tiers)
    check("自证桩 == 25（文档账本）", tiers.get("self_certified") == 25, tiers)
    check("三分类和 == 52 锚总数", sum(tiers.values()) == 52, tiers)
    check("逐锚明细 == 52 条", len(pa) == 52, len(pa))

    # ---- 3. provenance 6 类 + 低置信不变量（必要验证纪律）----
    expect_prov = {"external_textbook", "external_empirical", "independent_cross_check",
                   "design_rule_anchor", "self_authored_closed_form",
                   "self_authored_closed_form_with_check"}
    # 模型定义 6 类；填充集是 6 类宇宙的子集（external_textbook 当前 0 锚亦合法）。
    # 真不变量：不出现未知 provenance + 各类计数和 == 52 锚总数。
    check("provenance 均为 6 类宇宙子集（无未知来源泄漏）",
          set(bp.keys()) <= expect_prov, list(bp.keys()))
    check("provenance 各类计数和 == 52 锚总数", sum(bp.values()) == 52, (bp, sum(bp.values())))
    check("低置信自写闭式 == 15（必要验证集）", len(lc) == 15, len(lc))
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
