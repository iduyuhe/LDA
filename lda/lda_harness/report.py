"""LDA 验证 harness · 报告格式化（Markdown + JSON）。"""
import json
import datetime

# 占位自证候选：直接返回黄金值本身 ⇒ |候选 − 黄金| ≡ 0，恒 PASS。
# 用于验证「判决回路闭合」，**不产生任何验证价值**（D-64）。
SELF_CONSISTENT_CANDIDATES = ("ReferenceCandidate",)

_SELF_CONSISTENT_WARNING = (
    "> ⚠️ **本报告不构成验证结论**：candidate=ReferenceCandidate 直接把黄金参考值当作候选值，"
    "故「误差」列恒为 0、全部 PASS。它只验证**判决回路闭合**（黄金取值→比对→容差判定→报告），"
    "**不验证任何求解器**。真实验证必须由**独立候选求解器**产出候选值——见 "
    "`run_harness.py --ai`（L3 AI 写内核）与 `verification_adapters.py`（独立频域候选，"
    "如 E2 的 FDFD n_g）。把本报告的「N/N 通过」读作「N 项已验证」是误读。"
)


def is_self_consistent(meta):
    """判断本次运行是否走占位自证候选（candidate≡golden）。"""
    if not meta:
        return True  # 未声明候选来源时按最保守处理
    sc = meta.get("self_consistent")
    if sc is not None:
        return bool(sc)
    name = str(meta.get("candidate", "ReferenceCandidate"))
    return any(s in name for s in SELF_CONSISTENT_CANDIDATES)


def format_markdown(results, meta=None):
    lines = []
    lines.append("# LDA 验证锚点 · 报告（Verification Harness Report）")
    lines.append("")
    lines.append(f"- 生成时间：{datetime.datetime.now().isoformat(timespec='seconds')}")
    if meta:
        for k, v in meta.items():
            lines.append(f"- {k}：{v}")
    lines.append("")
    _sc = is_self_consistent(meta)
    if _sc:
        lines.append(_SELF_CONSISTENT_WARNING)
        lines.append("")
    n_pass = sum(1 for r in results if r.passed)
    lines.append(f"## 汇总：{n_pass}/{len(results)} 通过"
                 + ("（自证闭环，**非验证结论**）" if _sc else ""))
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
    _sc = is_self_consistent(meta)
    out = {
        "meta": dict(meta or {}, self_consistent=_sc),
        "generated_at": datetime.datetime.now().isoformat(timespec='seconds'),
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            # 自证闭环下 passed 无验证含义，机器可读地钉死这一点
            "self_consistent": _sc,
            "verified": (0 if _sc else sum(1 for r in results if r.passed)),
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
