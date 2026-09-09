"""T0-1 多目标帕累托排序护栏：反向测试必须会响（防常数假绿）。

覆盖：
  ① 确定性：两次运行同序（无随机无 LLM）
  ② 🔴 权重反转：power 权重高 vs margin 权重高，top 候选必须翻转
     （这是 T0-1 的核心验收：改变成本/功耗权重，Pareto 前沿必须位移）
  ③ 帕累托 front 正确性：被支配候选落在更差 front
  ④ 🔴 反常数假绿：权重变 ⇒ 至少一候选加权分数变（否则权重形同虚设）
  ⑤ 兼容 schema：输出含 rank/proposal/screening/screening_summary/pareto_front

运行：python run_pareto_rank_smoke.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.proposal_compiler import (
    compile_proposal, feasible_domain, rank_proposals_pareto,
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


def _cand(p_tx: float, wg_length_cm: float = 1.0,
          spacing: float = 100.0, bw: float = 50.0) -> dict:
    return compile_proposal({
        "p_tx_dbm": p_tx, "wg_length_cm": wg_length_cm,
        "channel_spacing_ghz": spacing, "filter_bw_ghz": bw,
    })


def main() -> int:
    print("T0-1 多目标帕累托排序护栏（反向测试）")

    # 候选：A 低功耗低余量；B 高功耗高余量；C 被 B 支配
    A = _cand(0.0)
    B = _cand(6.0)
    C = _cand(6.0, wg_length_cm=3.0)  # 同功耗但更长波导→余量更差 ⇒ 被 B 支配
    cands = [A, B, C]
    feas = [feasible_domain(c)["feasible"] for c in cands]
    check("构造候选全部可行（不触发 S1 剪枝）", all(feas), f"feasible={feas}")

    # ① 确定性
    r1 = [r["screening_summary"] for r in rank_proposals_pareto(cands)]
    r2 = [r["screening_summary"] for r in rank_proposals_pareto(cands)]
    check("① 排序确定性（重跑同序）", r1 == r2, f"{len(r1)} 项")

    # ② 🔴 权重反转（核心验收）
    power_heavy = {"power": 100.0, "cost": 0.0, "area": 0.0, "margin": 0.0, "p5": 0.0}
    margin_heavy = {"power": 0.0, "cost": 0.0, "area": 0.0, "margin": 100.0, "p5": 0.0}
    top_power = rank_proposals_pareto(cands, weights=power_heavy)[0]["proposal"]
    top_margin = rank_proposals_pareto(cands, weights=margin_heavy)[0]["proposal"]
    flipped = (top_power["link_spec"]["p_tx_dbm"]
               != top_margin["link_spec"]["p_tx_dbm"])
    check("② 🔴 权重反转：power 优先 top ≠ margin 优先 top（前沿位移）",
          flipped,
          f"power-top.p_tx={top_power['link_spec']['p_tx_dbm']} "
          f"vs margin-top.p_tx={top_margin['link_spec']['p_tx_dbm']}")

    # ③ 帕累托 front：C 被 B 支配 ⇒ C 的 front 比 B 差
    ranked = rank_proposals_pareto(cands)
    front_of = {r["proposal"]["link_spec"]["p_tx_dbm"]: r["pareto_front"]
                for r in ranked}
    # B 与 C 同 p_tx=6，用 wg_length 区分
    b_front = next(r["pareto_front"] for r in ranked
                   if r["proposal"]["link_spec"]["p_tx_dbm"] == 6.0
                   and r["proposal"]["link_spec"]["wg_length_cm"] == 1.0)
    c_front = next(r["pareto_front"] for r in ranked
                   if r["proposal"]["link_spec"]["p_tx_dbm"] == 6.0
                   and r["proposal"]["link_spec"]["wg_length_cm"] == 3.0)
    check("③ 帕累托 front：被支配候选 C 落在更差 front（> B）",
          c_front > b_front, f"B.front={b_front} C.front={c_front}")

    # ④ 🔴 反常数假绿：权重变 ⇒ 分数变
    from lda_harness.proposal_compiler import (
        _pareto_objective_vector, _weighted_scores, screen_proposal,
    )
    scored = [(c, screen_proposal(c)) for c in cands]
    vecs = [_pareto_objective_vector(c, s) for c, s in scored]
    sc_p = _weighted_scores(vecs, power_heavy)
    sc_m = _weighted_scores(vecs, margin_heavy)
    scores_changed = any(abs(sc_p[i] - sc_m[i]) > 1e-9 for i in sc_p)
    check("④ 🔴 权重变⇒分数变（权重非装饰）", scores_changed,
          f"Δsc[0]={abs(sc_p[0]-sc_m[0]):.4f}")

    # ⑤ 兼容 schema
    ok_schema = all(
        set(r.keys()) >= {"rank", "proposal", "screening",
                          "pareto_front", "screening_summary"}
        for r in ranked)
    check("⑤ 输出 schema 兼容（含 pareto_front）", ok_schema)

    print(f"\n结果：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
