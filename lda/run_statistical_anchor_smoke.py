"""Phase 3 统计锚 smoke：S7 蒙特卡洛分布锚（红线 + 防自证）。

覆盖：
  ① 蒙特卡洛均值收敛于解析 10.5（|mean−10.5|<0.15，采样噪声界）
  ② 分布方向正确（p5 < 解析 < p95——损耗随机增大 margin 变差）
  ③ 种子可复现（同种子两次运行逐样本一致——统计锚判决前提）
  ④ 🔴 红线断言：判决路径零 LLM（statistical_anchor 模块不引用任何
     agent/llm 模块；harness S7 的 oracle_kind 为确定性统计量）
  ⑤ S7 harness reference PASS（golden 自洽）
  ⑥ 扰动负例：损耗整体 +1dB → 分布下移 → candidate 偏离 golden > tol 被 FAIL 抓
  ⑦ 题库计数 50（B1-B30 30 + E1-E7 7 + S1-S13 13）
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

    # ⑦ 题库计数 47（B27 27 + E7 7 + S13 13）
    b_ids = [b for b in BENCHMARK_ORDER if b.startswith("B")]
    e_ids = [b for b in BENCHMARK_ORDER if b.startswith("E")]
    s_ids = [b for b in BENCHMARK_ORDER if b.startswith("S")]
    check("题库 50 题（B1-B30 30 + E1-E7 7 + S1-S13 13）",
          len(BENCHMARK_ORDER) == 50 and len(b_ids) == 30
          and len(e_ids) == 7 and len(s_ids) == 13,
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

    # ⑪ v0.8.44 B3 相关簇锚（系统级簇漂移——单点锚/离群锚的最后一类盲区）
    from lda_harness.array_distribution_anchor import (
        array_distribution_verdict, cluster_drift)
    # 纯盲区：16 通道，通道 5-7 连续 3 通道 +1.0~1.2dB——均值/下界/离群三锚全过
    vals_c = [9.0] * 16
    for i, off in ((5, 1.0), (6, 1.1), (7, 1.2)):
        vals_c[i] = 9.0 + off
    r_old3 = array_distribution_verdict(
        vals_c, golden_mean=9.0, tol_mean=0.3,
        golden_min=6.0, tol_min=0.5, outlier_margin=2.0)
    r_new4 = array_distribution_verdict(
        vals_c, golden_mean=9.0, tol_mean=0.3,
        golden_min=6.0, tol_min=0.5, outlier_margin=2.0,
        cluster_dev=0.8, min_cluster=3)
    check("B3 盲区确认：旧三锚 ACCEPT（均值/下界/离群全过）",
          r_old3["verdict"] == "ACCEPT", f"{r_old3['verdict']}")
    check("B3 相关簇锚唯一捕获：四锚 REJECT（簇锚 False 其他 True）",
          r_new4["verdict"] == "REJECT"
          and all(c["ok"] for c in r_new4["checks"]
                  if c["name"] != "相关簇锚")
          and not [c for c in r_new4["checks"]
                   if c["name"] == "相关簇锚"][0]["ok"],
          f"checks={[(c['name'], c['ok']) for c in r_new4['checks']]}")
    cd = cluster_drift(vals_c, 0.8, 3)
    check("B3 簇检测原语：3 通道连续同向（均值偏离 1.1）",
          cd["drift"] and cd["max_cluster_len"] == 3,
          f"{cd}")
    # 正例不误伤（既有 S12 配置含簇锚）
    r12_ok = s12_array_distribution_report("insertion_loss", seed=42)
    check("B3 正例不误伤：配置簇锚后插损正例仍 ACCEPT",
          r12_ok["verdict"] == "ACCEPT"
          and [c for c in r12_ok["checks"]
               if c["name"] == "相关簇锚"][0]["ok"],
          f"{r12_ok['verdict']}")

    # ⑫ v0.9.1 S13 设计良率锚（DFY · 解析闭式 ↔ 蒙特卡洛双算法互证）
    from lda_harness.yield_anchor import (
        monte_carlo_yield, nominal_ring_length, s13_design_yield_anchor,
        yield_analytic, yield_report, yield_vs_tolerance_scan)

    rep = yield_report()
    y_an, y_mc = rep["yield_analytic"], rep["yield_monte_carlo"]
    # ① 核心判决：两种独立算法（解析积分 / 数值采样）偏差 ≤ 1 个百分点
    check("S13 解析↔蒙特卡洛互证（|Δ| ≤ 0.01）",
          rep["cross_check_ok"],
          f"解析={y_an} MC={y_mc} Δ={rep['cross_delta']:.6f}")
    # ② 判别力：良率不得恒等于 1（否则锚无分辨率，正态容差下应约 95%）
    check("S13 良率落在有判别力区间（0.8 < Y < 0.999）",
          0.8 < y_an < 0.999, f"Y_analytic={y_an}")
    # ③ DFY 物理正确性：工艺容差放大 → 良率单调下降
    scan = yield_vs_tolerance_scan()
    check("S13 良率随工艺容差单调下降（DFY 判别力）",
          scan["monotone_decreasing"],
          " > ".join(f"{r['sigma_rel']*100:g}%:{r['yield_analytic']:.3f}"
                     for r in scan["rows"]))
    # ④ 逐点互证：扫描的每个 σ 上解析与 MC 都要吻合（不只默认点）
    worst = max(r["cross_delta"] for r in scan["rows"])
    check("S13 全扫描点互证一致（max Δ ≤ 0.01）", worst <= 0.01,
          f"maxΔ={worst:.6f}")
    # ⑤ 规格窗口放宽 → 良率上升（客户可理解的 trade-off 方向）
    y_tight = yield_analytic(delta=0.01)
    y_loose = yield_analytic(delta=0.03)
    check("S13 规格窗口放宽 → 良率上升", y_loose > y_tight,
          f"δ=1%:{y_tight:.4f} < δ=3%:{y_loose:.4f}")
    # ⑥ 种子可复现（统计锚判决前提）
    y1 = s13_design_yield_anchor()
    y2 = s13_design_yield_anchor()
    check("S13 固定种子可复现（两次调用逐位一致）", y1 == y2, f"{y1} == {y2}")
    # ⑦ 物理合理性：环长 µm 量级、样本 FSR 均值逼近名义 17.5nm
    l0 = nominal_ring_length()
    check("S13 物理合理性（L0 为 µm 量级、FSR 样本均值≈17.5nm）",
          1e3 < l0 < 1e6 and abs(rep["diagnostics"]["fsr_mean_nm"] - 17.5) < 0.05,
          f"L0={l0/1e3:.2f}µm FSR_mean={rep['diagnostics']['fsr_mean_nm']}nm")
    # ⑧ 极端容差：收紧到 0.2% → 高良率；放大到 4% → 显著劣化
    y_hi = yield_analytic(sigma_rel=0.002)
    y_lo = yield_analytic(sigma_rel=0.04)
    check("S13 容差收紧/放大两端行为正确", y_hi > 0.999 and y_lo < 0.7,
          f"σ=0.2%:{y_hi:.4f}  σ=4%:{y_lo:.4f}")
    # ⑨ harness S13 reference PASS（golden 自洽，复用 S7 同款构造）
    from lda_harness.harness import ReferenceCandidate
    h13 = VerificationHarness(BENCHMARK_DEFS)
    spec_s13 = [s for s in h13.resolve_specs(None) if s.get("id") == "S13"]
    check("S13 已注册进 harness 题库", len(spec_s13) == 1,
          f"specs={len(spec_s13)}")
    if spec_s13:
        res13 = h13.run(spec_s13, ReferenceCandidate())[0]
        check("S13 harness reference PASS（golden 自洽）",
              res13.passed, f"{res13.candidate} vs {res13.golden}")
    # ⑩ 红线：判决路径零 LLM（用 AST 查真实 import 依赖，不受注释文本干扰——
    #    注：docstring 里出现的"LLM 不进判决路径"是声明而非依赖，文本匹配会误伤）
    import ast
    import inspect
    from lda_harness import yield_anchor as _ya_mod
    _tree = ast.parse(inspect.getsource(_ya_mod))
    _imported: list = []
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.Import):
            _imported += [a.name for a in _n.names]
        elif isinstance(_n, ast.ImportFrom):
            _imported.append(_n.module or "")
    _bad = [m for m in _imported
            if any(k in m.lower() for k in ("llm", "openai", "agent", "torch"))]
    check("S13 红线：yield_anchor 零 LLM/agent 依赖（AST 查 import）",
          not _bad, f"imports={_imported}")

    print(f"\n统计锚 smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
