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

# v0.9.15（P0-2）：混合态警告 —— 部分锚题已接独立候选，其余仍是自证桩。
# 此时既不能说「全部已验证」（44 道仍是 |diff|≡0），也不能说「零验证」
# （4 道确由独立求解器判出）。必须按题分列，否则又是另一种失真。
_MIXED_WARNING = (
    "> ⚠️ **本报告不构成验证结论**：本次运行中 **{n_ind} 项**由**独立候选求解器**"
    "判出（计入 `summary.verified`）；{tail}"
    "把「N/N 通过」整体读作「N 项已验证」是误读：真正被验证的只有那 {n_ind} 项。"
)

# 三分类下「其余项」的措辞：自证桩与降级锚性质不同，不能混为一谈
#   自证桩  = candidate≡golden，|diff|≡0，零验证价值
#   降级锚  = 跑了真独立求解器，但与 golden 几何不同源/精度不足 ⇒ 仅量级参考
_MIXED_TAIL_STUB_ONLY = (
    "其余 **{n_stub} 项**仍走 ReferenceCandidate 占位自证——候选值即黄金值、"
    "「误差」列恒为 0、恒 PASS，**零验证价值**。")
_MIXED_TAIL_WITH_DEGRADED = (
    "其余项中 **{n_stub} 项**走 ReferenceCandidate 占位自证（候选值即黄金值、"
    "「误差」列恒为 0、恒 PASS，**零验证价值**），**{n_deg} 项**为降级量级参考"
    "（有独立候选但与 golden 几何不同源/精度不足，**不进死标量判决**）。")

# C-1 口径分裂诚实披露（v0.9.30 · T-5）：路径①（本报告默认）与路径②（--ai）是两套候选体系，
# 对外只写一个数字会制造「宣称 vs 可复现」缺口。在路径①报告里显式交代路径②的口径。
_DUAL_PATH_NOTE = (
    "> 📌 **两条判决路径口径不同（C-1 诚实披露 · v0.9.30 · T-5）**：本报告的 `verified` "
    "来自**路径①**（`IndependentCandidateRouter`，方法学不同源的独立频域候选）。\n"
    "> **路径②** `run_harness.py --ai`（L3 AI 写内核 demo，离线回退 `_local_approx`）实测 "
    "`verified=2/48`（仅 B1/B4 真实现且 PASS，余 46 道为 `return golden` 自证桩）。\n"
    "> 两路径候选体系本就不同，**均为如实口径、不构成虚报**；对外「独立候选 {n_ind}/48」特指路径①。")


def is_self_consistent(meta):
    """判断本次运行是否走占位自证候选（candidate≡golden）。"""
    if not meta:
        return True  # 未声明候选来源时按最保守处理
    sc = meta.get("self_consistent")
    if sc is not None:
        return bool(sc)
    name = str(meta.get("candidate", "ReferenceCandidate"))
    return any(s in name for s in SELF_CONSISTENT_CANDIDATES)


def candidate_class_counts(results):
    """统计候选**三分类**（v0.9.16 · P0-3）——全库唯一口径。

    返回 (n_strict, n_degraded, n_stub, n_class_marked)：
      n_class_marked == 0 表示本次运行未按题标注三分类（旧路径：L3 AI /
      Perturbed / L1 协议层）→ 调用方须退化到 `independence_counts` 的二态口径。

    为什么需要它：`independent` 只是二态布尔，无法区分
      degraded_ordinal（有独立候选、跑了真求解器，但不进死标量判决）与
      self_consistent_stub（candidate≡golden）。此前只能把 degraded 算进 stub，
      于是「三分类 43」与「路径② 44」两套口径打架，只能靠注释解释。
    """
    from .harness import (CANDIDATE_CLASS_STRICT, CANDIDATE_CLASS_DEGRADED,
                          CANDIDATE_CLASS_STUB)
    cls = [getattr(r, "candidate_class", None) for r in results]
    marked = [c for c in cls if c]
    return (marked.count(CANDIDATE_CLASS_STRICT),
            marked.count(CANDIDATE_CLASS_DEGRADED),
            marked.count(CANDIDATE_CLASS_STUB),
            len(marked))


def independence_counts(results):
    """统计独立性标注（二态口径，兼容旧路径）。

    返回 (n_independent, n_marked, n_stub)：
      n_marked == 0 表示本次运行**未按题标注**独立性（旧路径：L3 AI / Perturbed /
      L1 协议层等）→ 报告沿用旧的整体布尔判定，行为与 v0.9.14 及之前完全一致。
      n_marked  > 0 表示走了 IndependentCandidateRouter，按题精确统计。

    ⚠️ n_stub 在三分类可用时取**真实自证桩数**（degraded 不再混进来）；
    三分类不可用时退化为 len(results) − n_independent（旧行为）。
    """
    marked = [r for r in results if getattr(r, "independent", None) is not None]
    n_ind = sum(1 for r in marked if r.independent)
    _n_strict, _n_deg, _n_stub, _n_cls = candidate_class_counts(results)
    n_stub = _n_stub if _n_cls else len(results) - n_ind
    return n_ind, len(marked), n_stub


def verified_count(results, self_consistent):
    """计算「真被验证」的项数 —— 全库唯一权威口径。

    - 按题标注过独立性（router / L3 路由）⇒ 只有**独立候选判出且通过**的算数
    - 未标注（旧路径）⇒ 沿用整体布尔：自证则 0，否则等于 passed
    """
    n_ind, n_marked, _n_stub = independence_counts(results)
    if n_marked:
        return sum(1 for r in results
                   if r.passed and getattr(r, "independent", False))
    return 0 if self_consistent else sum(1 for r in results if r.passed)


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
    _n_ind, _n_marked, _n_stub = independence_counts(results)
    _n_strict, _n_deg, _n_stub_cls, _n_cls = candidate_class_counts(results)
    if _n_marked:
        # 混合态（有独立 + 有自证/降级）→ 分列陈述；全独立 → 无需警告
        if _n_ind and (_n_stub or _n_deg):
            _tail = ((_MIXED_TAIL_WITH_DEGRADED if _n_deg else _MIXED_TAIL_STUB_ONLY)
                     .format(n_stub=_n_stub, n_deg=_n_deg))
            lines.append(_MIXED_WARNING.format(n_ind=_n_ind, tail=_tail))
            # C-1 口径分裂诚实披露（v0.9.30 · T-5）：仅在路径①报告里交代路径②口径，
            # 避免两份报告各说各话、读者误以为「23 vs 2」是虚报。
            _cand_name = str((meta or {}).get("candidate", ""))
            if "IndependentCandidateRouter" in _cand_name:
                lines.append(_DUAL_PATH_NOTE.format(n_ind=_n_ind))
            lines.append("")
    elif _sc:
        lines.append(_SELF_CONSISTENT_WARNING)
        lines.append("")
    n_pass = sum(1 for r in results if r.passed)
    if _n_marked and _n_ind:
        # 措辞必须区分「独立候选项数」与「其中真正通过（=已验证）的项数」，
        # 否则独立候选失败时，汇总行会把「7 项独立」说成「7 项已验证」。
        _n_verified = sum(1 for r in results
                          if r.passed and getattr(r, "independent", False))
        _deg_txt = (f" · {_n_deg} 项降级量级参考（不进判决）" if _n_deg else "")
        _suffix = (f"（独立候选 {_n_ind} 项中 **{_n_verified} 项通过=已验证** · "
                   f"{_n_stub} 项自证闭环{_deg_txt}，**非验证结论**）")
    elif _n_marked or _sc:
        _suffix = "（自证闭环，**非验证结论**）"
    else:
        _suffix = ""
    lines.append(f"## 汇总：{n_pass}/{len(results)} 通过" + _suffix)
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
    _n_ind, _n_marked, _n_stub = independence_counts(results)
    _n_strict, _n_deg, _n_stub_cls, _n_cls = candidate_class_counts(results)
    _verified = verified_count(results, _sc)
    if not _n_marked:
        _n_stub = len(results) if _sc else 0
    out = {
        "meta": dict(meta or {}, self_consistent=_sc),
        "generated_at": datetime.datetime.now().isoformat(timespec='seconds'),
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            # 自证闭环下 passed 无验证含义，机器可读地钉死这一点
            "self_consistent": _sc,
            "verified": _verified,
            # 自证桩项数：外部验货者据此判断「48 项里到底几项真被验证过」
            "self_consistent_stub_count": _n_stub,
            "independent_candidate_count": _n_ind,
            # v0.9.16（P0-3）：三分类一并机器可读输出，杜绝「路径② 44 vs 三分类 43」
            # 两套口径打架时只能靠散文注释解释。未标注三分类时（旧路径）为 null。
            "candidate_class_totals": ({
                "strict_independent": _n_strict,
                "degraded_ordinal": _n_deg,
                "self_consistent_stub": _n_stub_cls,
            } if _n_cls else None),
        },
        "results": [
            {
                "id": r.bid, "metric": r.metric, "oracle": r.oracle,
                "source": r.source, "golden": r.golden,
                "candidate": r.candidate,
                "tol": r.tol, "passed": r.passed, "note": r.note,
                # True=独立候选（进判决）/ False=降级或自证 / null=未标注（旧路径）
                "independent": getattr(r, "independent", None),
                # 三分类：strict_independent / degraded_ordinal /
                #        self_consistent_stub / null（旧路径未标注）
                "candidate_class": getattr(r, "candidate_class", None),
            }
            for r in results
        ],
    }
    return json.dumps(out, indent=2, ensure_ascii=False)
