"""创新超市 smoke（v0.8.34 · 创新超市 · 前瞻预研货架红线下护栏）。

三守护（与全局红线一致）：
  ① 每条组合可分解到已锚定基元（composition 全部 ∈ GOLDEN_IDS）——禁止含未锚定基元；
  ② 每条结构可行 + 系统预算不破（design_pipeline 复用 system_type 已验证闭环）；
  ③ honest_tier 必填且 = "前瞻预研"——CI 绝不输出"已流片验证"字样。

运行：python run_innovation_market_smoke.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_l2.innovation_market import (
    evaluate_all, to_markdown, save_library_json,
    HONEST_TIER, HONEST_BANNER,
)
from lda_l2.golden_product_benchmarks import DEFAULT_BENCHMARKS

GOLDEN_IDS = {b.product_id for b in DEFAULT_BENCHMARKS}

_PASS = 0
_FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    mark = "PASS" if cond else "FAIL"
    if cond:
        _PASS += 1
    else:
        _FAIL += 1
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))


def main() -> int:
    print("Phase 2 创新超市 smoke（前瞻预研货架 · 红线下护栏）")
    print(HONEST_BANNER)
    results = evaluate_all()
    n_total = len(results)
    n_ok = sum(1 for r in results if r.get("feasible") and not r.get("error"))

    for r in results:
        sid = r["id"]
        err = r.get("error")
        # 守护①：composition 全部已锚定
        comp = r.get("composition", [])
        unanchored = [c for c in comp if c not in GOLDEN_IDS]
        check(f"{sid}：组合可分解到已锚定基元（{', '.join(comp)}）",
              not unanchored,
              "" if not unanchored else f"未锚定 {unanchored}")
        # 守护②：结构可行 + 预算不破（无 error 且 feasible）
        check(f"{sid}：结构可行 + 系统预算不破（可上架）",
              (err is None) and bool(r.get("feasible")),
              r.get("summary", err or ""))
        # 守护③：honest_tier 必填 = 前瞻预研
        check(f"{sid}：honest_tier = 前瞻预研（CI 不宣称流片验证）",
              r.get("honest_tier") == HONEST_TIER,
              r.get("honest_tier", ""))

    # 库落盘 + 目录生成（B 生态播种素材）
    lib = save_library_json()
    report = to_markdown(results)
    out_md = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                          "docs", "innovation_market.md")
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n库已落盘: {lib}")
    print(f"目录已写: {out_md}")
    print(f"汇总: {n_ok}/{n_total} 货架通过结构可行检查")

    if n_ok < n_total or _FAIL:
        print("FAIL: 存在未达标货架或护栏破")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
