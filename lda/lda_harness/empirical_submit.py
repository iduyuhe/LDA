#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D-10 真实测量语料补登工具（CLI）。

为退休专家 / 晶圆厂 / 社区贡献者提供「实测语料登记」入口，与
`.github/ISSUE_TEMPLATE/empirical_measurement.yml` 同源。三种落地方式：

  1. `--out issue`  ：生成符合 issue 模板结构的 Markdown 正文，供在 GitHub
     网页 / `gh issue create` 提交（默认，不写本地文件，最安全）。
  2. `--out bank`   ：把记录追加到本地语料库（默认 seed_empirical.json，
     可用 `--bank PATH` 指定增量文件），自动去重 + 溯源。
  3. `--out both`   ：两者都做。

红线：本工具只负责「登记 + 校验 + 溯源」，不触及求解器判决路径；
citation 必填（无引用不予收录），与 EmpiricalMeasurement.validate 一致。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from lda_harness.empirical_bank import (  # noqa: E402
    EmpiricalCorpus, EmpiricalMeasurement,
)

DEFAULT_BANK = os.path.join(HERE, "seed_empirical.json")


def build_measurement(args):
    geometry = {}
    if args.geometry:
        geometry = json.loads(args.geometry)
    tags = [t.strip() for t in (args.tags or "").split(";") if t.strip()]
    return EmpiricalMeasurement(
        id=args.id, device=args.device, metric=args.metric,
        measured_value=float(args.measured_value),
        uncertainty_abs=float(args.uncertainty_abs),
        fab_source=args.fab_source, citation=args.citation,
        method=args.method or "", geometry=geometry, tags=tags,
    )


def render_issue_md(m: EmpiricalMeasurement) -> str:
    """生成与 empirical_measurement.yml 字段同构的 Markdown 正文。"""
    geom = json.dumps(m.geometry, ensure_ascii=False) if m.geometry else ""
    return (
        f"### 实测语料提交\n\n"
        f"- **语料 ID**：{m.id}\n"
        f"- **器件**：{m.device}\n"
        f"- **指标**：{m.metric}\n"
        f"- **实测值**：{m.measured_value}\n"
        f"- **不确定度 σ**：{m.uncertainty_abs}\n"
        f"- **来源（fab / 文献 / PDK）**：{m.fab_source}\n"
        f"- **引用（必填，可追溯）**：{m.citation}\n"
        f"- **测量方法**：{m.method or '—'}\n"
        f"- **几何与材料参数**：{geom or '—'}\n"
        f"- **标签**：{'、'.join(m.tags) or '—'}\n"
    )


def append_to_bank(m: EmpiricalMeasurement, bank_path: str, contributor: str,
                   overwrite: bool):
    """把记录追加到语料库文件（自动去重 + 溯源）。返回 ImportResult 式 dict。"""
    if os.path.exists(bank_path):
        corpus = EmpiricalCorpus.load(bank_path)
    else:
        corpus = EmpiricalCorpus()
    st = corpus.add(m, contributor=contributor, source_file=bank_path,
                    overwrite=overwrite)
    if st == "added":
        corpus.to_json(bank_path, wrap=True)
    return {"status": st, "total": corpus.stats()["total"]}


def cmd_submit(args):
    m = build_measurement(args)
    try:
        m.validate()
    except ValueError as e:
        print(f"[校验失败] {e}", file=sys.stderr)
        return 2

    out = args.out
    if out in ("issue", "both"):
        print("=== 可粘贴到 GitHub Issue 的正文 ===")
        print(render_issue_md(m))
        # 若环境有 gh 且用户显式要求，直接创建 issue
        if args.gh:
            import subprocess
            body = render_issue_md(m).replace('"', '\\"')
            title = f"[实测语料] {m.id}"
            r = subprocess.run(
                ["gh", "issue", "create", "--title", title, "--body", body,
                 "--label", "empirical-corpus,data-submission"],
                capture_output=True, text=True)
            print(r.stdout or r.stderr)

    if out in ("bank", "both"):
        if args.dry_run:
            print(f"[dry-run] 校验通过，将追加到 {args.bank}（contributor={args.contributor}）")
            return 0
        res = append_to_bank(m, args.bank, args.contributor, args.overwrite)
        print(f"[bank] {res['status']} → 语料库共 {res['total']} 条（{args.bank}）")
    return 0


def cmd_template(args):
    print("CSV 批量补登模板表头（另见 lda/lda_harness/examples/corpus_template.csv）：")
    print("id,device,metric,measured_value,uncertainty_abs,fab_source,citation,"
          "method,geometry,tags")
    print("\n单条补登：")
    print('  python empirical_submit.py submit --id E-XXX --device "..." '
          '--metric n_eff --measured_value 2.63 --uncertainty_abs 0.02 '
          '--fab_source "..." --citation "..." [--out issue|bank|both]')
    return 0


def cmd_validate(args):
    if not os.path.exists(args.bank):
        print(f"文件不存在: {args.bank}", file=sys.stderr)
        return 2
    corpus = EmpiricalCorpus.load(args.bank)
    bad = 0
    for m in corpus._items.values():
        try:
            m.validate()
        except ValueError as e:
            bad += 1
            print(f"  [INVALID] {m.id}: {e}")
    print(f"校验完成：{corpus.stats()['total']} 条，非法 {bad} 条")
    return 1 if bad else 0


def build_parser():
    p = argparse.ArgumentParser(description="LDA 真实测量语料补登工具 (D-10)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("submit", help="补登一条实测语料")
    s.add_argument("--id", required=True)
    s.add_argument("--device", required=True)
    s.add_argument("--metric", required=True)
    s.add_argument("--measured_value", required=True)
    s.add_argument("--uncertainty_abs", required=True)
    s.add_argument("--fab_source", required=True)
    s.add_argument("--citation", required=True)
    s.add_argument("--method", default="")
    s.add_argument("--geometry", default="")
    s.add_argument("--tags", default="")
    s.add_argument("--out", choices=["issue", "bank", "both"], default="issue")
    s.add_argument("--bank", default=DEFAULT_BANK)
    s.add_argument("--contributor", default="cli-submitter")
    s.add_argument("--overwrite", action="store_true")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--gh", action="store_true", help="若 gh CLI 可用，直接创建 issue")
    s.set_defaults(func=cmd_submit)

    t = sub.add_parser("template", help="打印补登模板")
    t.set_defaults(func=cmd_template)

    v = sub.add_parser("validate", help="校验语料库文件")
    v.add_argument("--bank", default=DEFAULT_BANK)
    v.set_defaults(func=cmd_validate)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
