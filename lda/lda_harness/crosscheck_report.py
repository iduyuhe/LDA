"""LDA 对照报告飞轮（v0.8.30 · 可重复多源对照报表生成器）。

把「基准对照验证闭环」固化为**可重复飞轮**：一键产出 Markdown + JSON 对照
报表（设计包 vs 解析锚 / 实证锚 / 第三方 ORACLE 死标量对照），并记录到
`reports/crosscheck_history/` 形成时间序列，便于「覆盖度只增不减」趋势监控
与院校说服素材积累。

与 `benchmark_report.run_crosscheck` 的关系：本模块是**飞轮外壳**（时间戳、
历史归档、覆盖度 diff、CI 可调用），底层仍是同一份死标量对照逻辑（不重复
实现判决）。

用法：
  python -m lda.lda_harness.crosscheck_report [--quick] [--out DIR]
  或 CLI：lda report --out DIR [--quick]
红线：全部死标量（LLM 不进判决路径）；诚实边界——原理验证级非流片级。
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional


def _coverage_score(data: Dict[str, Any]) -> Dict[str, Any]:
    """从 crosscheck 数据提取覆盖度指标（供趋势监控）。"""
    rows = data.get("rows", [])
    n = len(rows)
    n_passed = sum(1 for r in rows if r.get("passed"))
    n_analytical = sum(1 for r in rows if r.get("analytical_rel_pct") is not None)
    cov = data.get("corpus_coverage", {})
    n_covered = sum(1 for c in cov.values() if c.get("covered"))
    n_loss_rel = sum(1 for c in cov.values() if c.get("rel_pct") is not None)
    return {
        "engines_total": n,
        "engines_passed": n_passed,
        "with_analytical_rel": n_analytical,
        "empirical_covered": n_covered,
        "empirical_with_rel": n_loss_rel,
        "honest": data.get("honest_note", ""),
    }


def build_report(quick: bool = False,
                  out_dir: str = "reports",
                  archive: bool = True) -> Dict[str, Any]:
    """生成对照报告（Markdown + JSON），可选归档历史快照。

    返回 {md_path, json_path, snapshot, score}。
    """
    from lda_harness.benchmark_report import run_crosscheck, _fmt_report

    data = run_crosscheck(quick=quick)
    os.makedirs(out_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    md_path = os.path.join(out_dir, f"benchmark_crosscheck_report.md")
    js_path = os.path.join(out_dir, f"benchmark_crosscheck_report.json")
    md = _fmt_report(data)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(js_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    snapshot = {
        "ts": ts,
        "quick": quick,
        "score": _coverage_score(data),
    }
    result: Dict[str, Any] = {
        "md_path": md_path, "json_path": js_path,
        "snapshot": snapshot, "score": snapshot["score"],
    }

    if archive:
        hist_dir = os.path.join(out_dir, "crosscheck_history")
        os.makedirs(hist_dir, exist_ok=True)
        hist_path = os.path.join(hist_dir, f"crosscheck_{ts}.json")
        with open(hist_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        result["history_path"] = hist_path
        # 覆盖度趋势（读历史最近一条做 diff）
        try:
            files = sorted(f for f in os.listdir(hist_dir) if f.endswith(".json"))
            if len(files) >= 2:
                prev = json.load(open(os.path.join(hist_dir, files[-2]), encoding="utf-8"))
                cur = snapshot["score"]
                p = prev["score"]
                result["delta"] = {
                    "engines_passed": cur["engines_passed"] - p["engines_passed"],
                    "empirical_covered": cur["empirical_covered"] - p["empirical_covered"],
                    "empirical_with_rel": cur["empirical_with_rel"] - p["empirical_with_rel"],
                }
        except Exception:
            pass
    return result


def print_summary(r: Dict[str, Any]) -> None:
    s = r["score"]
    print(f"# LDA 基准对照验证闭环报告（飞轮）")
    print(f"- 引擎 {s['engines_passed']}/{s['engines_total']} PASS · "
          f"解析锚 rel {s['with_analytical_rel']} 项 · "
          f"实证语料覆盖 {s['empirical_covered']}/9（含 rel {s['empirical_with_rel']}）")
    if r.get("delta"):
        d = r["delta"]
        print(f"- 较上次：引擎通过 {d['engines_passed']:+} · "
              f"实证覆盖 {d['empirical_covered']:+} · 实证 rel {d['empirical_with_rel']:+}")
    print(f"- 诚实边界：{s['honest'][:100]}...")
    print(f"报告: {r['md_path']}")
    print(f"数据: {r['json_path']}")
    if r.get("history_path"):
        print(f"归档: {r['history_path']}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="LDA 对照报告飞轮")
    ap.add_argument("--quick", action="store_true", help="仅快引擎子集")
    ap.add_argument("--out", default="reports", help="输出目录")
    ap.add_argument("--no-archive", action="store_true", help="不归档历史快照")
    a = ap.parse_args()
    r = build_report(quick=a.quick, out_dir=a.out, archive=not a.no_archive)
    print_summary(r)
