"""LLM 生成器价值实证护栏（T0 LLM 接口 · 成轮评估）。

核心判据（可证伪，防「开了等于没开」的假绿）：
  LLM 开启后，合并候选的帕累托前沿（front==1 且 accepted）必须出现
  **网格未覆盖的新参数组合**——否则 LLM 无增值，判 FAIL。

降级语义（与 LLMProposer 一致）：
  未配置 LDA_LLM_* → propose() 返回 [] → 合并集 == 网格集 →
  跳过「Pareto 位移」断言（标记 SKIP），仅跑网格基线 sanity（不崩、有接受点）。

红线不变：LLM 只出参数，判决全在四锚；本护栏只评估「增值」，不进判决路径。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.proposal_compiler import (
    generate_candidates,
    rank_proposals_pareto,
)

_PASS = 0
_FAIL = 0


def check(name, cond, detail=""):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  [PASS] {name}  ({detail})")
    else:
        _FAIL += 1
        print(f"  [FAIL] {name}  ({detail})")


def _param_key(c):
    # 注：channel_spacing_ghz / filter_bw_ghz 存于 req_source，不在 link_spec
    rs = c.get("req_source", {})
    ls = c["link_spec"]
    return (
        round(float(rs.get("p_tx_dbm", ls.get("p_tx_dbm", 0.0))), 2),
        round(float(rs.get("channel_spacing_ghz", 0.0)), 2),
        round(float(rs.get("filter_bw_ghz", 0.0)), 2),
        round(float(ls.get("wg_length_cm", 0.0)), 2),
    )


def _front1_accepted(cands):
    ranked = rank_proposals_pareto(cands)
    return {_param_key(r["proposal"])
            for r in ranked
            if r["pareto_front"] == 1 and r["screening"]["accepted"]}


def main():
    print("LLM 生成器价值实证护栏")
    print("=" * 56)

    req = {"n_channels": 4, "p_tx_dbm": 0.0, "channel_spacing_ghz": 50.0,
           "filter_bw_ghz": 25.0, "wg_length_cm": 1.0}

    llm_enabled = bool(os.environ.get("LDA_LLM_BASE")
                       and os.environ.get("LDA_LLM_KEY"))

    grid_cands = generate_candidates(req, generator="grid")
    llm_cands = generate_candidates(req, generator="llm")

    g_all = {_param_key(c) for c in grid_cands}
    g_f1 = _front1_accepted(grid_cands)
    m_f1 = _front1_accepted(llm_cands)

    # ① 网格基线 sanity（无论是否配 LLM 都要成立）
    check("网格基线：确定性生成产出 ≥1 接受点",
          len(g_f1) >= 1, f"front1_accepted={len(g_f1)}")

    if not llm_enabled:
        # ② 未配置 LLM → 跳过位移断言（降级网格），标记 SKIP 不算失败
        check("价值实证：LLM 未配置 → 跳过 Pareto 位移断言（降级网格基线 OK）",
              True, f"grid_front1={len(g_f1)} (SKIP value-assert, wire LLM to enable)")
        print(f"\n网格基线前沿点：{sorted(g_f1)}")
        print("提示：配置 LDA_LLM_BASE/LDA_LLM_KEY/LDA_LLM_MODEL 后重跑，"
              "本护栏将断言 LLM 贡献网格外新非支配点。")
    else:
        # ② LLM 已配置 → 必须真增值，否则 FAIL（可证伪核心）
        novel = m_f1 - g_all
        check("价值实证：LLM 开启后 Pareto 前沿出现网格未覆盖的新非支配点",
              len(novel) >= 1,
              f"grid_front1={len(g_f1)} llm_front1={len(m_f1)} novel={sorted(novel)}")
        if novel:
            print(f"  → LLM 新增前沿点：{sorted(novel)}")

    print("=" * 56)
    print(f"LLM 价值实证 smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
