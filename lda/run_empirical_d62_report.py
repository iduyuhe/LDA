"""D-62 实证大数据锚 验收报告生成器 → lda/reports/empirical_d62.json。

报告维度：①双 ground 结构（物理定律 B1-B18 + 实证锚 E1-E3）；②实证锚题
golden=实测语料（跨多源可溯源）；③语料评审流端到端；④诚实边界。
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.benchmarks import BENCHMARK_DEFS
from lda_harness.verification_adapters import build_harness_specs, _load_empirical_anchor
from lda_pdk.empirical import (
    submit_measurement, review_measurement, land_measurement,
    measurement_stats, list_landed_measurements,
)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", "empirical_d62.json")

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append({"name": name, "ok": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('| ' + detail) if detail else ''}")


def main():
    # ① 双 ground 结构
    anchor = _load_empirical_anchor()
    # D-63：E 题分 A 级（empirical，可公开溯源）与 B 级（empirical_unverified，待溯源）
    e_bench = {b: d for b, d in BENCHMARK_DEFS.items()
               if d.get("anchor") in ("empirical", "empirical_unverified")}
    e_trace = {b: d for b, d in e_bench.items() if d.get("anchor") == "empirical"}
    check("双 ground：48 题（B1-B28 物理定律 + E1-E7 实证 + S1-S13 系统）",
          len(BENCHMARK_DEFS) == 48 and len(e_bench) == 7,
          f"total={len(BENCHMARK_DEFS)} empirical={sorted(e_bench)}")
    # D-64：E2 换用可公开溯源的实测群折射率语料（E-SIN-NG-300）→ 升 A 级。
    # D-66：E1 原 n_eff=2.63 经逐字核实为错值 → 改判 n_g 实测锚 E-SOI-NG-220
    #       （4.18，arXiv:2011.03273）→ **E1 同步升 A 级**。
    #       至此 A 级 7 道 / B 级 0 道，全部走「必须可溯源」的严格门禁。
    check("实证锚题 golden 全部可 resolve（D-66 后 A 级 7 道，B 级清零）",
          all(anchor.resolve(d.get("empirical_id"),
                             require_traceable=(d.get("anchor") == "empirical"))[0]
              is not None for d in e_bench.values())
          and len(e_trace) == 7,
          f"A级={sorted(e_trace)} | golden="
          f"{ {b: anchor.resolve(d.get('empirical_id'), require_traceable=(d.get('anchor') == 'empirical'))[0] for b, d in e_bench.items()} }")

    # ② 语料溯源完整性（seed 5 条全部 citation 可追溯）
    corpus = anchor.corpus
    no_cite = [m.id for m in corpus._items.values() if not m.citation]
    no_fab = [m.id for m in corpus._items.values() if not m.fab_source]
    check("语料溯源完整性（citation/fab_source 全可追溯）",
          not no_cite and not no_fab, f"total={len(corpus._items)}")

    # ③ 评审流端到端（临时库）
    tmp = tempfile.mkdtemp(prefix="lda_d62_report_")
    pp = os.path.join(tmp, "empirical_proposals.json")
    cp = os.path.join(tmp, "empirical_contributions.json")
    # D-63 来源边界：citation 须含 DOI/arXiv/公开 URL 方可收录
    PAY = {"id": "E-REPORT-1", "device": "环形谐振器", "metric": "FSR_nm",
           "measured_value": 9.20, "uncertainty_abs": 0.08, "fab_source": "公开测试",
           "citation": "S. Sridaran & S. A. Bhave, Opt. Express 18(4), 3850-3857 (2010), "
                       "https://opg.optica.org/oe/viewmedia.cfm?URI=oe-18-4-3850",
           "proposed_by": "社区"}
    r0 = submit_measurement(PAY, proposals_path=pp)
    r1 = review_measurement("E-REPORT-1", "approve", "杜玉河", "citation 可追溯", proposals_path=pp)
    r2 = land_measurement("E-REPORT-1", proposals_path=pp, corpus_path=cp)
    check("语料评审流端到端（提交→评审→落地）",
          r0["status"] == "accepted_pending" and r1["status"] == "approved"
          and r2["status"] == "landed",
          f"submit={r0['status']} review={r1['status']} land={r2['status']}")
    landed = list_landed_measurements(corpus_path=cp)
    check("落地语料落盘（empirical_contributions.json 结构）",
          len(landed) == 1 and landed[0]["id"] == "E-REPORT-1"
          and "provenance" in landed[0] and "reviewer" in landed[0]["provenance"],
          str(landed[0].get("provenance")))
    s = measurement_stats(proposals_path=pp)
    check("评审流状态自洽", s["total"] == 1 and s["by_status"]["landed"] == 1, str(s))

    # ④ 诚实边界（快照）
    summary = {
        "total_benchmarks": len(BENCHMARK_DEFS),
        "physical_law": 18,
        "empirical_anchor": 3,
        "seed_corpus": len(corpus._items),
        "review_flow": s,
        "honest_boundary": "种子语料为公开文献/PDK 量级（citation 可追溯）；真实晶圆厂 "
                           "NDA 流片实测属发动期联动，经「具名人工评审（LLM 不进判决路径）"
                           "→ 落库」流持续流入；落库(live)≠进版本控制，权威语料以维护者 "
                           "git 提交为准；比对=|candidate−measured|≤σ（死标量）。",
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "checks": CHECKS}, f, indent=2, ensure_ascii=False)
    print("-" * 60)
    npass = sum(1 for c in CHECKS if c["ok"])
    print(f"实证锚报告：{npass}/{len(CHECKS)} PASS → {OUT}")
    return 0 if npass == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
