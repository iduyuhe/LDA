"""LLM 红队实证护栏（T0 LLM 接口 · 蓝队生成 / 红队出题闭环）。

闭环：蓝队(DeepSeek 生成器)出候选 → 红队(GLM)出对抗候选 → 每个攻击经
三层判卷（结构校验 validate_params → 可行域 feasible_domain → 四锚 screen_proposal）。

死标量（红队自身可证伪，同构「生态/智能体出题，锚判卷」）：
  hit_rate = 被锚确认的真实缺陷数 / 出题数   （目标 0：健康管线不应有攻击漏过）
  attack_ratio = 管线拒收攻击数 / 出题数     （红队是否真在对抗，目标 ≥0.3）
  coverage = 意图攻击的锚种类数             （目标 ≥2：红队须多角覆盖）
  假独立：红队模型 ≠ 生成器模型             （防同源假独立）

降级：未配置 LDA_REDTEAM_* → 跳过 LLM 出题断言（标记 SKIP），仅跑假独立 sanity。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_agent.llm_proposer import LLMProposer
from lda_agent.redteam_proposer import RedTeamProposer
from lda_harness.proposal_compiler import (
    compile_proposal,
    feasible_domain,
    generate_candidates,
    screen_proposal,
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
    print("LLM 红队实证护栏（蓝队生成 / 红队出题）")
    print("=" * 56)

    req = {"n_channels": 4, "p_tx_dbm": 0.0, "channel_spacing_ghz": 50.0,
           "filter_bw_ghz": 25.0, "wg_length_cm": 1.0}

    gen_model = os.environ.get("LDA_LLM_MODEL")
    rt_model = os.environ.get("LDA_REDTEAM_MODEL")
    rt_enabled = bool(os.environ.get("LDA_REDTEAM_BASE", os.environ.get("LDA_LLM_BASE"))
                     and os.environ.get("LDA_REDTEAM_KEY"))

    # ① 假独立纪律（与规则式红队护栏同源判据）
    if gen_model and rt_model:
        check("假独立：红队模型 ≠ 生成器模型",
              gen_model != rt_model, f"gen={gen_model} rt={rt_model}")
    else:
        check("假独立：未同时配置两模型 → 跳过模型比较", True,
              f"gen={gen_model} rt={rt_model}")

    if not rt_enabled:
        check("红队出题：LDA_REDTEAM_* 未配置 → 跳过 LLM 出题断言（降级规则式）",
              True, "wire LDA_REDTEAM_BASE/KEY to enable")
        print(f"\n提示：配置 LDA_REDTEAM_BASE/LDA_REDTEAM_KEY/LDA_REDTEAM_MODEL 后重跑，"
              "本护栏将断言 GLM 出题经三层判卷零漏过。")
        print("=" * 56)
        print(f"LLM 红队实证 smoke：{_PASS} PASS / {_FAIL} FAIL")
        return 1 if _FAIL else 0

    # ② 蓝队出候选（供红队上下文；未配则退网格）
    blue = generate_candidates(req, generator="llm")
    blue_summary = f"蓝队候选数={len(blue)}"

    # ③ 红队出题
    red = RedTeamProposer()
    attacks = red.propose_attacks(req, blue_candidates=blue, n=8)
    n_proposed = len(attacks)
    check("红队出题：GLM 返回 ≥1 对抗候选", n_proposed >= 1,
          f"n_proposed={n_proposed} source={red.last_source}")

    # ④ 三层判卷 + 死标量
    # 判卷口径（防常数假绿 / 良性滑过误报）：
    #  - 出题数 n_proposed
    #  - 钳制(越界) n_clamped：结构非法，一眼钳掉（红队弱攻击，无价值）
    #  - 命中(被锚拒) n_caught：结构合法但被 feasible_domain/四锚 拦下 = 红队真在攻击
    #  - 良性滑过 n_slip_benign：红队生成的本是合法设计，管线接受 = 红队没攻击到（诊断，非缺陷）
    #  - 确认缺陷 confirmed_defects：出题带 target 锚，且该锚独立复算违规却仍被管线接受
    #    （健康管线 accepted⟹全锚过 ⇒ 恒为 0；一旦回归破坏 accepted 逻辑才会 >0）
    # 死标量：attack_ratio = (n_clamped+n_caught) / n_proposed（管线拒收攻击占比，红队是否真在对抗）
    #         hit_rate    = confirmed_defects / n_proposed（被锚确认的真实缺陷率，目标 0）
    proposer = LLMProposer()  # 复用其 validate_params 作结构钳制判据
    n_clamped = 0
    n_caught = 0
    n_slip_benign = 0
    confirmed_defects = 0
    anchors_hit = set()        # 实际被某锚拦下的锚种类（诊断用）
    intended_targets = set()   # 红队意图攻击的锚种类（覆盖度=多角打法）
    defect_examples = []
    for atk in attacks:
        tgt = atk.get("target")
        if tgt:
            intended_targets.add(tgt)
        if not proposer.validate_params(atk):
            n_clamped += 1
            continue
        prop = compile_proposal({**req, **atk})
        fd = feasible_domain(prop)
        scr = screen_proposal(prop)
        passed_all = fd["feasible"] and scr["accepted"]
        if not passed_all:
            n_caught += 1
            for ch in scr["checks"]:
                if not ch["passed"]:
                    anchors_hit.add(ch["anchor"])
        else:
            # 滑过：管线全过。是缺陷吗？仅当出题明确 target 且该锚独立复算仍违规
            is_defect = False
            if tgt:
                tgt_check = next((c for c in scr["checks"]
                                 if c["anchor"].startswith(tgt)), None)
                # 健康管线 accepted⟹tgt_check.passed=True；此处仅作回归护栏
                if tgt_check is not None and not tgt_check["passed"]:
                    is_defect = True
            if is_defect:
                confirmed_defects += 1
                defect_examples.append(atk)
            else:
                n_slip_benign += 1

    n_rejected_total = n_clamped + n_caught
    attack_ratio = (n_rejected_total / n_proposed) if n_proposed else 0.0
    hit_rate = (confirmed_defects / n_proposed) if n_proposed else 0.0
    coverage = len(intended_targets)  # 红队意图攻击角度多样性（稳定，非依赖偶然命中）

    check("红队确认缺陷=0（出题带 target 且被锚漏过的真实管线漏洞；健康=0）",
          confirmed_defects == 0,
          f"confirmed_defects={confirmed_defects} hit_rate={hit_rate:.2f}")
    check("红队真在对抗：管线拒收攻击占比 ≥0.3（非全生成良性设计）",
          attack_ratio >= 0.3,
          f"attack_ratio={attack_ratio:.2f} n_rejected={n_rejected_total}")
    check("红队深度攻击 ≥1（至少 1 个在界内、被四锚拦下的智能攻击，非全越界垃圾）",
          n_caught >= 1,
          f"n_caught={n_caught}")
    check("红队覆盖：意图攻击 ≥2 种锚（多角打法，非单一向量）",
          coverage >= 2,
          f"intended_targets={sorted(intended_targets)}")
    check("红队质量：非全为越界垃圾（至少部分攻击结构合法、真去撞锚）",
          n_clamped < n_proposed,
          f"n_clamped={n_clamped} n_proposed={n_proposed}")

    if defect_examples:
        print(f"  ⚠ 确认缺陷（需修复管线）：{defect_examples}")

    print("-" * 56)
    print(f"  出题数={n_proposed}  钳制={n_clamped}  命中(被锚拒)={n_caught}  "
          f"良性滑过={n_slip_benign}  确认缺陷={confirmed_defects}")
    print(f"  attack_ratio={attack_ratio:.2f}  hit_rate={hit_rate:.2f}  "
          f"意图角度={sorted(intended_targets)}  实际命中锚={sorted(anchors_hit)}  {blue_summary}")
    print("=" * 56)
    print(f"LLM 红队实证 smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
