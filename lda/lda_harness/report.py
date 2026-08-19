"""LDA 验证 harness · 报告格式化（Markdown + JSON）。"""
import json
import datetime


def format_markdown(results, meta=None):
    lines = []
    lines.append("# LDA 验证锚点 · 报告（Verification Harness Report）")
    lines.append("")
    lines.append(f"- 生成时间：{datetime.datetime.now().isoformat(timespec='seconds')}")
    if meta:
        for k, v in meta.items():
            lines.append(f"- {k}：{v}")
    lines.append("")
    n_pass = sum(1 for r in results if r.passed)
    lines.append(f"## 汇总：{n_pass}/{len(results)} 通过")
    lines.append("")
    lines.append("| 题号 | 指标 | 真值来源 | 黄金值 | 候选值 | 误差 | 容差 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in results:
        if r.golden is None or r.candidate is None:
            err = "—"
            gv = "—"
            cv = "—"
        else:
            err = f"{abs(r.candidate - r.golden):.4g}"
            gv = f"{r.golden:.6g}"
            cv = f"{r.candidate:.6g}"
        verdict = "✅ PASS" if r.passed else "❌ FAIL"
        lines.append(
            f"| {r.bid} | {r.metric} | {r.source} | {gv} | {cv} | {err} | {r.tol:.4g} | {verdict} |")
    lines.append("")
    fails = [r for r in results if not r.passed]
    if fails:
        lines.append("## 未通过项")
        for r in fails:
            lines.append(f"- **{r.bid}**（{r.metric}）：{r.note or '候选值与黄金参考偏差超容差'}")
        lines.append("")
    lines.append("---")
    lines.append("*本报告由 LDA 验证 harness 生成；黄金参考为确定性物理定律锚（非 AI）。*")
    return "\n".join(lines)


def format_json(results, meta=None):
    out = {
        "meta": meta or {},
        "generated_at": datetime.datetime.now().isoformat(timespec='seconds'),
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
        },
        "results": [
            {
                "id": r.bid, "metric": r.metric, "oracle": r.oracle,
                "source": r.source, "golden": r.golden,
                "candidate": r.candidate,
                "tol": r.tol, "passed": r.passed, "note": r.note,
            }
            for r in results
        ],
    }
    return json.dumps(out, indent=2, ensure_ascii=False)
