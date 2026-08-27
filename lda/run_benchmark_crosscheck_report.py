"""LDA 基准对照验证闭环报告（v0.8.29 · 薄壳 re-export）。

实现已提取到正式包模块 `lda_harness/benchmark_report`（使 `lda report`
CLI 在生产 wheel 安装后也能导入）。本脚本保留为 CLI 入口壳，供 CI 与
直接 `python run_benchmark_crosscheck_report.py` 调用，行为不变。

运行：python run_benchmark_crosscheck_report.py [--out reports] [--quick]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.benchmark_report import run_crosscheck, _fmt_report  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="LDA 基准对照验证闭环报告")
    ap.add_argument("--out", default=os.path.join(_HERE, "reports"), help="输出目录")
    ap.add_argument("--quick", action="store_true", help="仅解析快引擎子集（CI）")
    args = ap.parse_args(argv)

    print("=" * 70)
    print("LDA 基准对照验证闭环报告（跨源死标量对照）")
    print("=" * 70)
    data = run_crosscheck(quick=args.quick)

    os.makedirs(args.out, exist_ok=True)
    md_path = os.path.join(args.out, "benchmark_crosscheck_report.md")
    js_path = os.path.join(args.out, "benchmark_crosscheck_report.json")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(_fmt_report(data))
    with open(js_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    s = data["summary"]
    print(f"引擎 {s['engines_passed']}/{s['engines_total']} PASS · "
          f"rel max={s['rel_max_pct']}% median={s['rel_median_pct']}%")
    print(f"报告: {md_path}")
    print(f"数据: {js_path}")
    return 0 if s["engines_passed"] == s["engines_total"] else 1


if __name__ == "__main__":
    sys.exit(main())
