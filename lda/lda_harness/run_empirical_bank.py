"""LDA 实证大数据锚 · 命令行演示/入口。

用法：
  python run_empirical_bank.py                               # 加载种子，打印统计 + 跑演示候选比对
  python run_empirical_bank.py --check E-SOI-NG-220 --candidate 4.15
  python run_empirical_bank.py --out reports

说明：
  实测语料（corpus）作为「实证大数据锚」：候选求解器输出对照真实测量，
  比对 = |candidate - measured| ≤ uncertainty（tol 默认取不确定度）。
  LLM 不进判决路径。对抗性题库（adversarial）为开放提交接口（种子已含
  4 题，社区/退休专家/晶圆厂可继续追加）。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from empirical_bank import (
    EmpiricalCorpus, AdversarialBenchmarkBank, EmpiricalAnchor,
)

SEED = os.path.join(HERE, "seed_empirical.json")

# 演示用候选求解器输出（模拟 AI 写内核的结果）
# D-66（2026-09-01）：5 条语料经逐字核实后全部升级为 A 级可溯源实测，
#   其中 3 条语义改判（metric 换了量）：
#     E-SOI-NEFF-220  n_eff 2.63（错值）→ E-SOI-NG-220    n_g 4.18±0.05
#     E-SIN-NEFF-300  n_eff 1.53        → E-SIN-NG-1200   n_g 2.2834±0.05
#     E-YBRANCH-LOSS  split_loss 3.4dB  → 同 id，改 excess_loss_dB 0.28±0.02
#     E-RING-FSR      9.15nm（反算值）  → 同 id，改实测 8.6±0.1 nm
#     E-GRATING-EFF   0.45（无出处）    → 同 id，改实测 0.42±0.05
DEMO_CANDIDATES = {
    "E-SOI-NG-220": 4.15,     # 接近实测 4.18±0.05 → PASS
    "E-SIN-NG-1200": 2.40,    # 偏离实测 2.2834±0.05 → FAIL（演示实证锚抓偏离）
    "E-YBRANCH-LOSS": 0.29,   # 接近实测 0.28±0.02 → PASS
    "E-RING-FSR": 8.55,       # 接近实测 8.6±0.1 → PASS
    "E-GRATING-EFF": 0.52,    # 偏离实测 0.42±0.05 → FAIL（演示实证锚抓偏离）
}


def main():
    ap = argparse.ArgumentParser(description="LDA 实证大数据锚")
    ap.add_argument("--check", default=None, help="用 corpus 实测作 golden 校验候选（id）")
    ap.add_argument("--candidate", type=float, default=None, help="候选求解器输出值")
    ap.add_argument("--seed", default=SEED, help="种子 JSON 路径")
    ap.add_argument("--out", default=os.path.join(HERE, "reports"), help="报告目录")
    args = ap.parse_args()

    with open(args.seed, "r", encoding="utf-8") as f:
        data = json.load(f)
    corpus = EmpiricalCorpus(data.get("corpus", []))
    bank = AdversarialBenchmarkBank(data.get("adversarial", []))
    anchor = EmpiricalAnchor(corpus)

    print("=== 实证大数据锚 · 种子加载 ===")
    print("corpus 统计:", corpus.stats())
    print("adversarial 统计:", bank.stats())

    os.makedirs(args.out, exist_ok=True)

    if args.check:
        m = corpus.get(args.check)
        if not m:
            print(f"无此实测语料: {args.check}")
            return
        cand = args.candidate if args.candidate is not None else DEMO_CANDIDATES.get(args.check)
        val, source, note = anchor.resolve(args.check)
        passed = abs(cand - val) <= m.uncertainty_abs
        print(f"\n--- 校验 {args.check} ---")
        print(f"实测={val} ±{m.uncertainty_abs} | 候选={cand} | 误差={abs(cand-val):.4g} | {'PASS' if passed else 'FAIL'}")
        print(f"来源: {note}")
        return

    # 默认：跑全部演示候选比对
    print("\n=== 候选求解器 vs 实测语料（实证锚）===")
    n_pass = 0
    rows = []
    for mid, cand in DEMO_CANDIDATES.items():
        m = corpus.get(mid)
        if not m:
            continue
        val, source, note = anchor.resolve(mid)
        passed = abs(cand - val) <= m.uncertainty_abs
        n_pass += 1 if passed else 0
        rows.append((mid, m.metric, val, m.uncertainty_abs, cand, abs(cand - val), passed))
        print(f"  {mid:18s} {m.metric:14s} 实测={val:.4g}±{m.uncertainty_abs} 候选={cand:.4g} 误差={abs(cand-val):.4g} {'✅' if passed else '❌'}")

    print(f"\n演示候选比对：{n_pass}/{len(rows)} 通过（实证锚作 golden，LLM 不进判决路径）")

    print("\n=== 开放对抗性题库（雷③信任墙）===")
    for b in bank._items.values():
        print(f"  {b.id:18s} [{','.join(b.tags)}] {b.title} (tol={b.tol})")

    md = ["# LDA 实证大数据锚 · 报告", "",
          f"- corpus 条目: {corpus.stats()['total']}",
          f"- adversarial 题目: {bank.stats()['total']}", "",
          "## 候选 vs 实测（实证锚）", "",
          "| id | metric | 实测 | ±σ | 候选 | 误差 | 判定 |",
          "|---|---|---|---|---|---|---|"]
    for mid, metric, val, sigma, cand, err, passed in rows:
        md.append(f"| {mid} | {metric} | {val:.4g} | {sigma} | {cand:.4g} | {err:.4g} | {'PASS' if passed else 'FAIL'} |")
    md.append("")
    md.append("## 对抗性题库")
    for b in bank._items.values():
        md.append(f"- **{b.id}** ({b.title}): {b.desc} [tol={b.tol}]")
    md.append("")
    md.append("*实证锚=真实器件测量语料；LLM 不进判决路径。种子为公开文献量级，须社区/退休专家补真实测量。*")
    md_path = os.path.join(args.out, "empirical_anchor_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"\n报告已写入：{md_path}")


if __name__ == "__main__":
    main()
