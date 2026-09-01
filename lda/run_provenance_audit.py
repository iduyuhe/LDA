"""D-63 实证语料「来源边界」合规审计。

来源边界（用户 2026-09-01 拍板）：
    仅限 ①公开论文 ②公开 datasheet ③公开测量数据集；且必须可公开溯源。

本脚本对实证语料库做**机器可判**的溯源分级审计（纯字符串解析，无网络 I/O、
无 AI 判断），输出：
    - 语料库 A/B/X 三级分布与可溯源占比
    - 不合格（B/X 级）语料清单 —— 这些**禁止作 golden 进判决路径**
    - 各实证锚题（E1-E7）所用语料的溯源等级

用途：CI 门禁 / 对外披露「实证锚的可信度底数」/ 整改跟踪。

用法：
    python lda/run_provenance_audit.py [--json 输出路径] [--min-ratio 0.80]
退出码：0=达标（A 级占比 ≥ --min-ratio），1=未达标。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.empirical_bank import EmpiricalCorpus          # noqa: E402
from lda_harness.provenance import audit_items, classify_citation  # noqa: E402
from lda_harness.benchmarks import BENCHMARK_DEFS               # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SEED = os.path.join(HERE, "lda_harness", "seed_empirical.json")


def build_report(seed_path=DEFAULT_SEED):
    corpus = EmpiricalCorpus.load(seed_path)
    rep = audit_items(corpus._items.values())

    # 各实证锚题所用语料的溯源状态
    anchors = []
    for bid in sorted(k for k in BENCHMARK_DEFS if k.startswith("E")):
        d = BENCHMARK_DEFS[bid]
        eid = d.get("empirical_id")
        m = corpus.get(eid) if eid else None
        info = classify_citation(m.citation, m.source_url) if m else {
            "tier": "X", "traceable": False, "locator_kind": "none", "locator": None}
        declared = d.get("anchor")
        anchors.append({
            "bench_id": bid,
            "title": d.get("title", ""),
            "corpus_id": eid,
            "declared_anchor": declared,
            "tier": info["tier"],
            "locator_kind": info["locator_kind"],
            "locator": info["locator"],
            "traceable": info["traceable"],
            "measured_value": (m.measured_value if m else None),
            "consistent": (info["traceable"] == (declared == "empirical")),
        })
    rep["anchors"] = anchors
    rep["anchors_traceable"] = sum(1 for a in anchors if a["traceable"])
    rep["seed_path"] = seed_path
    return rep


def main():
    ap = argparse.ArgumentParser(description="实证语料来源边界合规审计")
    ap.add_argument("--seed", default=DEFAULT_SEED, help="语料库 JSON 路径")
    ap.add_argument("--json", default=None, help="报告输出路径（不指定则只打印）")
    ap.add_argument("--min-ratio", type=float, default=0.90,
                    help="A 级占比达标线（默认 0.90；D-66 后语料库已 100%% A 级，"
                         "此基线为审计宽松下限，提交门禁仍强制 100%% B级零容忍）")
    args = ap.parse_args()

    rep = build_report(args.seed)
    ok = rep["traceable_ratio"] >= args.min_ratio

    print("=" * 68)
    print("LDA 实证语料 · 来源边界合规审计（D-63）")
    print("=" * 68)
    print(f"语料库：{rep['seed_path']}")
    print(f"总计 {rep['total']} 条 | A级(可公开溯源) {rep['by_tier']['A']} · "
          f"B级(量级参考) {rep['by_tier']['B']} · X级(无来源) {rep['by_tier']['X']}")
    print(f"A 级占比 {rep['traceable_ratio']*100:.1f}%（达标线 {args.min_ratio*100:.0f}%）"
          f" → {'达标' if ok else '未达标'}")
    print()
    print("--- 实证锚题溯源状态 ---")
    for a in rep["anchors"]:
        flag = "A" if a["traceable"] else "B"
        mark = "OK " if a["traceable"] else "!! "
        print(f"  {mark}[{flag}] {a['bench_id']} <- {a['corpus_id']:<18} "
              f"value={a['measured_value']} locator={str(a['locator'])[:40]}")
    print(f"  可溯源锚题：{rep['anchors_traceable']}/{len(rep['anchors'])}")
    print()
    if rep["untraceable"]:
        print("--- 不合格语料（B/X 级，禁止作 golden 进判决）---")
        for r in rep["untraceable"]:
            print(f"  [{r['tier']}] {r['id']:<20} {r['citation'][:56]!r}")
        print()
    print("=" * 68)
    print(f"审计结论：{'PASS' if ok else 'FAIL'}")

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=2, ensure_ascii=False)
        print(f"报告已写入：{args.json}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
