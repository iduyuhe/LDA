"""Phase 3 统计锚 smoke：S7 蒙特卡洛分布锚（红线 + 防自证）。

覆盖：
  ① 蒙特卡洛均值收敛于解析 10.5（|mean−10.5|<0.15，采样噪声界）
  ② 分布方向正确（p5 < 解析 < p95——损耗随机增大 margin 变差）
  ③ 种子可复现（同种子两次运行逐样本一致——统计锚判决前提）
  ④ 🔴 红线断言：判决路径零 LLM（statistical_anchor 模块不引用任何
     agent/llm 模块；harness S7 的 oracle_kind 为确定性统计量）
  ⑤ S7 harness reference PASS（golden 自洽）
  ⑥ 扰动负例：损耗整体 +1dB → 分布下移 → candidate 偏离 golden > tol 被 FAIL 抓
  ⑦ 题库计数 45（B1-B27 27 + E1-E7 7 + S1-S11 11）
  ⑧ S8 OSNR 统计锚（模板复用：Jensen 方向 + golden 收敛）
  ⑨ 蒙特卡洛收敛性（N 扫描收敛带）

运行：python run_statistical_anchor_smoke.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.benchmarks import BENCHMARK_DEFS, BENCHMARK_ORDER
from lda_harness.golden import golden_value
from lda_harness.harness import VerificationHarness
from lda_harness.statistical_anchor import (
    distribution_report, margin_stats, monte_carlo_margins,
    s7_statistical_margin_anchor, s8_statistical_osnr_anchor,
    monte_carlo_osnr, osnr_distribution_report, convergence_scan,
)
from lda_harness.verification_adapters import build_harness_specs

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
    print("Phase 3 统计锚 smoke（S7 蒙特卡洛分布 · 红线 + 防自证）")

    # ① 均值收敛于解析值（独立手算参照，非调用被测）
    r = distribution_report()
    analytic = 10.5  # S1 解析 margin：0 − 6 − 3 − 0.5 + 20
    check("均值收敛于解析 10.5（N=2000 采样噪声 <0.15）",
          abs(r["stats"]["mean"] - analytic) < 0.15,
          f"mean={r['stats']['mean']}")

    # ② 分布方向：p5 < 解析 < p95（最坏情况维度）
    check("分布方向正确（p5 < 解析 < p95）",
          r["direction_ok"], f"p5={r['stats']['p5']} p95={r['stats']['p95']}")
    check("p5 显著低于 mean（损耗增大方向 margin 变差）",
          (r["stats"]["mean"] - r["stats"]["p5"]) > 0.5,
          f"Δ={r['stats']['mean'] - r['stats']['p5']:.3f}")

    # ③ 种子可复现（判决前提）
    m1 = monte_carlo_margins(seed=42)
    m2 = monte_carlo_margins(seed=42)
    check("种子 42 可复现（逐样本一致）", m1 == m2)
    m3 = monte_carlo_margins(seed=7)
    check("不同种子分布不同（随机性真实存在）", m1 != m3)

    # ④ 红线断言：判决路径零 LLM（只检查 import 语句——docstring/注释
    #    提及 LLM 属说明文字非引用；真正引用必然出现在 import 行）
    src_lines = open(os.path.join(os.path.dirname(__file__),
                                  "lda_harness", "statistical_anchor.py"),
                     encoding="utf-8").read().splitlines()
    imports = [ln for ln in src_lines
               if ln.strip().startswith(("import ", "from "))]
    banned = [w for w in ("llm", "agent", "openai", "anthropic", "gpt")
              if any(w.lower() in ln.lower() for ln in imports)]
    check("红线：statistical_anchor import 零 LLM/agent", not banned,
          f"banned={banned}" if banned else "仅标准库 import")
    specs, _ = build_harness_specs()
    s7s = [x for x in specs if x.spec_id == "S7"]
    check("S7 oracle 为确定性统计量（非 LLM oracle）",
          len(s7s) == 1 and s7s[0].oracle_kind != "llm_judge",
          f"oracle_kind={s7s[0].oracle_kind if s7s else '?'}")

    # ⑤ S7 harness reference PASS（golden 自洽）
    harness = VerificationHarness(BENCHMARK_DEFS)
    s7_specs = [s for s in harness.resolve_specs(None) if s.get("id") == "S7"]
    from lda_harness.harness import ReferenceCandidate
    cand = ReferenceCandidate()
    res = harness.run(s7_specs, cand)
    check("S7 reference PASS（golden 自洽）",
          res[0].passed, f"{res[0].candidate} vs {res[0].golden}")

    # ⑥ 扰动负例：损耗整体 +1dB → 分布下移 → FAIL 被抓
    margins_bad = monte_carlo_margins(
        grating_db=-4.0, wg_loss_db_cm=4.0, ring_il_db=-1.5)  # 各损耗 +1dB
    bad_mean = margin_stats(margins_bad)["mean"]
    golden = s7_statistical_margin_anchor()
    # 手算：total=−4×2−4×1−1.5=−13.5 → margin=0−13.5+20=6.5
    check("扰动负例：损耗+1dB 分布下移（mean≈6.5）",
          abs(bad_mean - 6.5) < 0.3, f"mean={bad_mean}")
    check("扰动负例：偏离 golden > tol 被 FAIL 抓（防自证门禁）",
          abs(bad_mean - golden) > 0.15,
          f"Δ={abs(bad_mean - golden):.3f} > 0.15")

    # ⑦ 题库计数 46（B27 27 + E7 7 + S12 12）
    b_ids = [b for b in BENCHMARK_ORDER if b.startswith("B")]
    e_ids = [b for b in BENCHMARK_ORDER if b.startswith("E")]
    s_ids = [b for b in BENCHMARK_ORDER if b.startswith("S")]
    check("题库 46 题（B1-B27 27 + E1-E7 7 + S1-S12 12）",
          len(BENCHMARK_ORDER) == 46 and len(b_ids) == 27
          and len(e_ids) == 7 and len(s_ids) == 12,
          f"总={len(BENCHMARK_ORDER)} B={len(b_ids)} E={len(e_ids)} S={len(s_ids)}")

    # ⑧ S8 OSNR 统计锚（模板复用验证）
    r8 = osnr_distribution_report()
    check("S8 golden 收敛于解析 46.93（P_sig 线性保持）",
          abs(r8["stats"]["mean"] - r8["analytic_osnr_dB"]) < 0.15,
          f"mean={r8['stats']['mean']} analytic={r8['analytic_osnr_dB']}")
    check("S8 Jensen 方向（NF 非线性：均值≤解析，物理真实）",
          r8["jensen_ok"],
          f"mean={r8['stats']['mean']} ≤ {r8['analytic_osnr_dB']}")
    check("S8 p5 携带最坏情况（Δ>0.5dB）",
          (r8["stats"]["mean"] - r8["stats"]["p5"]) > 0.5,
          f"Δ={r8['stats']['mean'] - r8['stats']['p5']:.3f}")
    g8 = s8_statistical_osnr_anchor()
    check("S8 种子 7 可复现", g8 == s8_statistical_osnr_anchor())

    # ⑨ 蒙特卡洛收敛性（N 扫描收敛带——采样充分性死标量）
    c = convergence_scan()
    check("收敛性 N 扫描（500→4000 收敛带 <0.05）",
          c["converged"], f"spread={c['spread']} means={c['means']}")

    # ⑩ v0.8.42 S12 阵列分布锚（锚+统计混合 · 抓单点锚盲区）
    from lda_harness.array_distribution_anchor import (
        array_insertion_loss_anchor, array_fidelity_anchor,
        array_distribution_verdict,
        s12_array_distribution_report, s12_array_distribution_verdict)
    m_il, vals_il = array_insertion_loss_anchor(8, seed=42)
    r12 = s12_array_distribution_report(kind="insertion_loss", seed=42)
    check("S12 正例：8 通道插损分布 ACCEPT（均值/下界/离群三锚 AND）",
          s12_array_distribution_verdict(kind="insertion_loss", seed=42) == 1.0
          and r12["verdict"] == "ACCEPT",
          f"mean={r12['stats']['mean']} checks={[c['ok'] for c in r12['checks']]}")
    r12b = s12_array_distribution_report(kind="insertion_loss", seed=42)
    # 反例：注入单通道离群（14dB，均值仍≈9——单点锚盲区）
    bad_vals = list(vals_il)
    bad_vals[3] = 14.0
    r12b = array_distribution_verdict(
        bad_vals, golden_mean=9.0, tol_mean=0.3,
        golden_min=6.0, tol_min=0.5, outlier_margin=2.0)
    check("S12 反例：单通道离群 REJECT（单点锚盲区被离群锚抓住）",
          r12b["verdict"] == "REJECT"
          and not [c for c in r12b["checks"] if c["name"] == "离群锚"][0]["ok"],
          f"max={r12b['stats']['max']}")
    m_f, vals_f = array_fidelity_anchor(8, seed=7)
    r12f = s12_array_distribution_report(kind="fidelity", seed=7)
    check("S12 保真度 kind：8 比特读出分布 ACCEPT",
          s12_array_distribution_verdict(kind="fidelity", seed=7) == 1.0,
          f"mean={r12f['stats']['mean']}")

    print(f"\n统计锚 smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
