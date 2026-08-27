"""产品级基准对照库 smoke（v0.8.32 · 实证锚产品级扩展 + B 生态播种）。

落点：A/B 阶段内可做的「产品级验证」，不碰 C 闸门。
动作：LDA 引擎规格驱动再设计 + 数值复现 → 对标已公开验证 golden 死标量。
出口：全部 PASS 才退出 0；任一 FAIL/SKIP 记失败（CI 计数守护）。

红线：LLM 不进判决；比对为死标量 rel。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_l2.golden_product_benchmarks import (  # noqa: E402
    evaluate_all, to_markdown, save_library_json, HONEST_BANNER,
)


def main() -> int:
    # 1) 落盘库（可增量扩展：社区/文献贡献追加条目）
    lib = save_library_json()
    # 2) 全量评估
    results = evaluate_all()
    n_total = len(results)
    n_pass = sum(1 for r in results if r.get("passed_all"))

    print("=" * 68)
    print("LDA 产品级基准对照库（实证锚产品级扩展 + B 生态播种素材）")
    print(HONEST_BANNER)
    print("=" * 68)
    for r in results:
        if r.get("error"):
            print(f"\n[ERROR] {r['product_id']}: {r['error']}")
            continue
        status = "PASS" if r.get("passed_all") else "FAIL"
        print(f"\n[{status}] {r['product_id']} · {r['device_type']}")
        print(f"  来源: {r['source_kind']} | {r['source_ref']}")
        print(f"  引擎: {r['engine']} | 模型: {r['model']}")
        for row in r["rows"]:
            tag = "OK" if row["passed"] else "X"
            print(f"   - {row['name']}: replica={row['replica']}{row['unit']} "
                  f"vs golden={row['golden']}{row['unit']} (tol±{row['tol']}) -> {tag}")

    # 3) 生成对照报告（B 生态播种硬核素材）
    report = to_markdown(results)
    out_md = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                          "docs", "golden_product_benchmarks_report.md")
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n报告已写: {out_md}")
    print(f"库已落盘: {lib}")
    print(f"\n汇总: {n_pass}/{n_total} 产品级对标 PASS")

    if n_pass < n_total:
        print("FAIL: 存在未达标对标")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
