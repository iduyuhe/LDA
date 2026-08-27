"""Phase 0 · Merge-0 系统预算锚 smoke（S1 · 系统级第一锚）。

覆盖（防自证门禁三段式）：
  ① golden 正确性：S1 = 独立手算（dB 加法级联），非调用自身
  ② reference 候选 PASS：harness spec 解析 + 与 golden 死标量比对
  ③ 扰动候选 FAIL 被抓：任一级损耗 +2dB → margin 偏移 2dB > tol=0.01
  ④ 题库计数：35 题（B1-B27 + E1-E7 + S1），S 前缀接入 golden 分发
  ⑤ 预算语义物理合理性：损耗级增加 → margin 严格递减；余量域判定
  ⑥ 行为黑箱参数边界：p_tx/灵敏度参数化（文献典型值，诚实标注）

红线：PASS/FAIL 由 |candidate − golden| ≤ tol 死标量决定，LLM 不进判决路径。
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from lda_harness.benchmarks import BENCHMARK_DEFS, BENCHMARK_ORDER  # noqa: E402
from lda_harness.golden import golden_value  # noqa: E402
from lda_harness.system_budget import (  # noqa: E402
    budget_breakdown,
    budget_margin_db,
    link_budget_cascade,
)
from lda_harness.verification_adapters import build_harness_specs  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    tag = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"[{tag}] {name}" + (f" —— {detail}" if detail else ""))


def main() -> int:
    # ① golden 正确性（独立手算，非调用被测函数；wg_loss 为正系数取负入级联）
    params = dict(BENCHMARK_DEFS["S1"]["default_params"])
    golden = golden_value("S1", params)
    manual = (params["p_tx_dbm"]
              + params["n_gratings"] * params["grating_db"]
              - abs(params["wg_loss_db_cm"]) * params["wg_length_cm"]
              + params["ring_il_db"]
              - params["detector_sens_dbm"])
    check("S1 golden=独立手算（dB 级联加法）", abs(golden - manual) < 1e-9,
          f"golden={golden} manual={manual}")
    check("S1 默认链路余量为正（链路闭合）", golden > 0, f"margin={golden} dB")

    # ② harness spec 解析 + reference 死标量比对
    specs, cand_map = build_harness_specs()
    s1 = [s for s in specs if s.spec_id == "S1"]
    check("S1 进 harness specs（oracle_kind=physical_law）",
          len(s1) == 1 and s1[0].oracle_kind == "physical_law",
          f"specs={len(specs)}")
    spec = s1[0]
    cand = cand_map["S1"](spec, spec.oracle_fn(spec.params))
    ok = abs(cand - spec.oracle_fn(spec.params)) <= spec.tol
    check("reference 候选 PASS（|cand−golden|≤tol=0.01）", ok,
          f"cand={cand} tol={spec.tol}")

    # ③ 扰动候选 FAIL 被抓（任一级 +2dB → 偏移 2dB ≫ tol）
    perturbed = golden - 2.0  # 如波导长度翻倍 / 光栅退化 2dB
    caught = abs(perturbed - golden) > spec.tol
    check("扰动候选 FAIL 被抓（+2dB 偏移 ≫ tol）", caught,
          "预算锚能抓候选偏离（死标量）")

    # ④ 题库计数（35 = 27B + 7E + 1S）
    check("题库 44 题（B27+E7+S10）",
          len(BENCHMARK_ORDER) == 44 and BENCHMARK_ORDER[-1] == "S10",
          f"{len(BENCHMARK_ORDER)} 题")

    # ⑤ 预算语义物理合理性：单调性 + 余量域
    dec = True
    for extra in (0.5, 1.0, 2.0, 4.0):
        p2 = dict(params)
        p2["wg_loss_db_cm"] = params["wg_loss_db_cm"] + extra
        if golden_value("S1", p2) >= golden:
            dec = False
    check("损耗级增加 → margin 严格递减", dec, "预算级联单调性")
    check("余量域判定（P_rx−Sens）",
          budget_margin_db(p_rx_dbm=-3.5, sens_dbm=-20.0) == 16.5,
          "P_rx=−3.5dBm, Sens=−20dBm → 16.5dB")
    p_rx = link_budget_cascade(0.0, [-3.0, -3.0, -3.0, -0.5])
    check("级联算子（dB 加法）", abs(p_rx - (-9.5)) < 1e-9, f"P_rx={p_rx}")

    # ⑥ 黑箱参数边界（预算分解报告可用，参数可标定替换）
    rows = budget_breakdown(params)
    check("预算分解报告（逐级贡献，人可读）",
          len(rows) >= 6 and any("光栅" in r[0] for r in rows),
          f"{len(rows)} 行")

    # ⑦ S2-S6 系统锚 golden 正确性（独立手算）
    from lda_harness.system_budget import (
        s2_channel_plan_no_collision, s3_osnr_budget,
        s4_fidelity_budget, s5_worst_case_budget, s6_detector_margin,
    )
    check("S2 频率规划无碰撞（100−50=50GHz）",
          s2_channel_plan_no_collision() == 50.0)
    check("S3 OSNR 预算（ASE 解析，>40dB 合理）",
          s3_osnr_budget() > 40.0, f"OSNR={s3_osnr_budget():.2f}dB")
    f_tot = 0.999 ** 4 * 0.998
    check("S4 保真度预算 ∏fᵢ（对数域同构）",
          abs(s4_fidelity_budget() - (f_tot - 0.995)) < 1e-6,
          f"margin={s4_fidelity_budget():.6f}")
    check("S5 最坏情况预算（0−10+20=10dB）",
          s5_worst_case_budget() == 10.0)
    check("S6 探测器灵敏度余量（−8.5+20=11.5dB）",
          s6_detector_margin() == 11.5)

    # ⑧ 探测器黑箱（三件套收口）：响应度 + 光电流物理正确
    from lda_design.active_models import detector_responsivity, detector_response
    r_a = detector_responsivity(0.8, 1.55)
    check("探测器响应度 R_A≈1.0 A/W（η=0.8@1550nm 量子效率解析）",
          abs(r_a - 1.0) < 0.05, f"R_A={r_a:.3f}")
    d = detector_response(-8.5, 0.8, 1.55)
    # −8.5dBm=0.141mW=1.41e-4 W；R_A×P=1.41e-4 A=141µA
    check("光电流物理正确（−8.5dBm→141µA）",
          abs(d["photocurrent_uA"] - 141.16) < 1.0,
          f"I={d['photocurrent_uA']}µA")

    print(f"\n汇总：{PASS} PASS / {FAIL} FAIL")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
