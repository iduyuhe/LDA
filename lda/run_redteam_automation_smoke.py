"""红队自动化 + 假独立护栏（T0 LLM 接口 · 多智能体纪律）。

两件事：
① 假独立纪律（用户硬要求）：红队出题模型必须 ≠ 生成器模型。
   若 LDA_LLM_MODEL 与 LDA_REDTEAM_MODEL 都配置且相同 → FAIL
   （同源 = 第二意见是同一个脑子 = 假独立）。
   红队未配 LLM → 规则式红队（天然不同源，跳过模型比较，PASS）。

② 红队自动化骨架：程序化生成越界/边界对抗命题注入生成器，
   断言 LLM 输出经 validate_params 钳制 + 四锚剪枝后不泄漏「通过锚但未检出」的非法设计
   （锚不豁免任何生成器；覆盖面对比：对抗命题下管线仍全过 feasible_domain）。

降级语义：未配置 LDA_LLM_* → propose() 返回 [] → 对抗注入断言自然成立（空集合）。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_agent.llm_proposer import LLMProposer
from lda_harness.proposal_compiler import (
    compile_proposal,
    design_pipeline,
    feasible_domain,
    generate_candidates,
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


def main():
    print("红队自动化 + 假独立护栏")
    print("=" * 56)

    gen_model = os.environ.get("LDA_LLM_MODEL")
    rt_model = os.environ.get("LDA_REDTEAM_MODEL")

    # ① 假独立纪律
    if gen_model and rt_model:
        check("假独立：红队模型 ≠ 生成器模型",
              gen_model != rt_model,
              f"gen={gen_model} rt={rt_model}")
    elif gen_model and not rt_model:
        check("假独立：红队未配 LLM → 规则式红队（天然不同源，跳过模型比较）",
              True, "rule-based redteam, no shared source")
    else:
        check("假独立：生成器未配 LLM → 红队不适用",
              True, "no generator llm configured")

    # ② 对抗命题注入（越界 / 边界）—— 验证生成器在攻击下不泄漏非法设计
    adversarial = [
        {"n_channels": 4, "p_tx_dbm": 999.0, "channel_spacing_ghz": 50.0,
         "filter_bw_ghz": 25.0, "wg_length_cm": 1.0},          # 越界功率
        {"n_channels": 4, "p_tx_dbm": 0.0, "channel_spacing_ghz": 50.0,
         "filter_bw_ghz": 999.0, "wg_length_cm": 1.0},        # 越界带宽 > 间隔
        {"n_channels": 4, "p_tx_dbm": 0.0, "channel_spacing_ghz": 50.0,
         "filter_bw_ghz": 25.0, "wg_length_cm": -3.0},         # 负波导长
    ]

    proposer = LLMProposer()
    for i, req in enumerate(adversarial):
        cands = proposer.propose(req, n=3)
        # LLM 返回候选必须全部通过结构校验（越界参数被钳制/丢弃）
        bad = [c for c in cands if not proposer.validate_params(c)]
        check(f"红队出题[{i}]：LLM 不返回越界候选",
              len(bad) == 0,
              f"returned={len(cands)} bad={len(bad)}")

    # ③ 规则式红队对照：物理不可行命题直接编译，断言 feasible_domain 全拒
    #    （验证「锚不豁免」——S1 余量 / S2 碰撞 / S5 最坏 三种物理约束真生效）
    #    注：单参数工程越界（如 p_tx=999）由生成侧 validate_params 钳制（见 ②），
    #    feasible_domain 只查物理链路约束，故红队 ③ 用物理不可行命题测锚。
    physically_infeasible = [
        {"n_channels": 4, "p_tx_dbm": 0.0, "channel_spacing_ghz": 25.0,
         "filter_bw_ghz": 50.0, "wg_length_cm": 1.0},                       # S2 碰撞：bw > spacing
        {"n_channels": 4, "p_tx_dbm": -20.0, "channel_spacing_ghz": 50.0,
         "filter_bw_ghz": 25.0, "wg_length_cm": 10.0},                     # S1 余量不足
        {"n_channels": 4, "p_tx_dbm": -30.0, "channel_spacing_ghz": 50.0,
         "filter_bw_ghz": 25.0, "wg_length_cm": 1.0},                      # S5 最坏情况 < 0
    ]
    all_rejected = True
    detail_bits = []
    for i, req in enumerate(physically_infeasible):
        prop = compile_proposal(req)
        if feasible_domain(prop)["feasible"]:
            all_rejected = False
            detail_bits.append(f"prop{i}:passed")
    check("规则式红队：物理不可行命题经 feasible_domain 全部拒绝（锚不豁免）",
          all_rejected,
          ("clean" if all_rejected else ";".join(detail_bits)))

    # ④ 覆盖面对比 sanity：正常命题下管线仍产出 ≥1 接受点
    normal = design_pipeline({"n_channels": 4}, generator="grid")
    check("红队 sanity：正常命题下管线产出 ≥1 接受点（攻击未破坏基线）",
          normal["n_accepted"] >= 1,
          f"n_accepted={normal['n_accepted']}")

    print("=" * 56)
    print(f"红队自动化 smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
