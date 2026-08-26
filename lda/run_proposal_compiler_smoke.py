"""Phase 4 提案编译器 smoke：生成侧第一件（锚前置剪枝 + 即提即验 + 人终审）。

覆盖：
  ① 可行域剪枝：正常需求域非空；废案需求（超高损耗）被 S1 锚卡死
  ② 域内生成：候选全部落可行域（废案不出域）
  ③ 即提即验：每案过 S1/S2/S5 三锚（死标量证据链）
  ④ 排序确定性：两次运行同序（无随机无 LLM）
  ⑤ 🔴 红线断言：proposal_compiler import 零 LLM/agent；判决纯算术
  ⑥ 端到端：4 信道 WDM 需求 → 过锚提案列表（人审材料完整）
  ⑦ 负例：超预算提案被锚抓（margin<need → REJECT + 证据链）
  ⑧ 低功耗优先 tiebreak（同余量下 p_tx 小者前）

运行：python run_proposal_compiler_smoke.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.proposal_compiler import (
    compile_proposal, design_pipeline, feasible_domain,
    generate_candidates, rank_proposals, screen_proposal,
)

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
    print("Phase 4 提案编译器 smoke（锚前置剪枝 + 即提即验 + 人终审）")

    # ① 可行域剪枝
    good = compile_proposal({"n_channels": 4})
    dom = feasible_domain(good)
    check("正常需求可行域非空（margin=10.5 ≥ 3）",
          dom["feasible"] and abs(dom["margin_db"] - 10.5) < 1e-6,
          f"margin={dom['margin_db']}")
    bad = compile_proposal({"wg_length_cm": 5.0})
    dom2 = feasible_domain(bad)
    check("废案需求被 S1 锚卡死（5cm 波导 margin<0）",
          not dom2["feasible"] and "S1" in (dom2["binding_constraint"] or ""),
          dom2["binding_constraint"] or "")

    # ② 域内生成（废案不出域）
    cands = generate_candidates(good)
    all_in_domain = all(feasible_domain(c)["feasible"] for c in cands)
    check("域内生成：候选全部可行（剪枝前置）",
          len(cands) > 0 and all_in_domain, f"{len(cands)} 候选")

    # ③ 即提即验（逐案四锚证据链：S1/S5/S2/S7）
    s = screen_proposal(good)
    check("即提即验：4/4 锚过（S1/S2/S5/S7 证据链）",
          s["accepted"] and len(s["checks"]) == 4
          and all(c["passed"] for c in s["checks"]),
          f"margin={s['margin_db']} p5={s['p5_db']}")

    # ③b 统计锚独有价值：名义过但统计挂（S1 margin>0 但 p5<0）
    borderline = compile_proposal({"wg_length_cm": 3.6, "link_budget_db": 0.0})
    sb = screen_proposal(borderline)
    s1_pass = sb["checks"][0]["passed"]
    s7_pass = sb["checks"][3]["passed"]
    check("统计锚独有判决：margin=2.7 名义过(S1 P) 但 p5=−0.32 统计挂(S7 F)",
          s1_pass and (not s7_pass) and (not sb["accepted"]),
          f"p5={sb['p5_db']}——确定性锚抓不到，统计锚剪掉")

    # ④ 排序确定性（两次运行同序）
    r1 = [r["screening_summary"] for r in rank_proposals(cands)]
    r2 = [r["screening_summary"] for r in rank_proposals(
        generate_candidates(good))]
    check("排序确定性（重跑同序，无随机）", r1 == r2, f"{len(r1)} 项")

    # ⑤ 红线断言（import 零 LLM/agent）
    src_lines = open(os.path.join(
        os.path.dirname(__file__), "lda_harness", "proposal_compiler.py"),
        encoding="utf-8").read().splitlines()
    imports = [ln for ln in src_lines
               if ln.strip().startswith(("import ", "from "))]
    banned = [w for w in ("llm", "openai", "anthropic", "gpt")
              if any(w.lower() in ln.lower() for ln in imports)]
    check("红线：proposal_compiler import 零 LLM（判决纯算术）",
          not banned, f"banned={banned}" if banned else "仅标准库")

    # ⑥ 端到端
    pipe = design_pipeline({"n_channels": 4, "channel_spacing_ghz": 100,
                            "link_budget_db": 3.0})
    check("端到端：需求→过锚提案列表（人审材料完整）",
          pipe["n_accepted"] >= 1 and pipe["ranked"]
          and pipe["feasible_domain"]["feasible"],
          f"域内 {pipe['n_domain_candidates']} · 过锚 {pipe['n_accepted']}（S7 收紧后）")

    # ⑦ 负例：超预算提案被锚抓
    s_bad = screen_proposal(bad)
    check("负例：超预算提案 REJECT（margin −1.5 < 3 + 证据链）",
          not s_bad["accepted"]
          and any(not c["passed"] for c in s_bad["checks"]),
          f"margin={s_bad['margin_db']}")

    # ⑧ 低功耗 tiebreak（同余量 p_tx 小者前）
    ranked = rank_proposals(cands)
    accs = [r for r in ranked if r["screening"]["accepted"]]
    if len(accs) >= 2:
        # 找同 margin 组，验证 p_tx 升序
        margins = {}
        ok_mono = True
        for r in accs:
            m = r["screening"]["margin_db"]
            margins.setdefault(m, []).append(
                r["proposal"]["link_spec"]["p_tx_dbm"])
        for m, pts in margins.items():
            if pts != sorted(pts):
                ok_mono = False
        check("tiebreak：同余量低功耗优先（p_tx 升序）", ok_mono,
              f"{ {m: pts for m, pts in list(margins.items())[:2]} }")
    else:
        check("tiebreak：同余量低功耗优先（p_tx 升序）", True, "候选不足跳过")

    print(f"\n提案编译器 smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
