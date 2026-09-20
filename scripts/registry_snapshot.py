# -*- coding: utf-8 -*-
"""注册表快照判据（R3 前置 · 为 F-08 巨石拆分提供机器可验的"零漂移"基线）。

背景
----
`lda_harness/benchmarks.py`（≈6635 行）与 `lda_harness/verification_adapters.py`
（≈6789 行）是本仓库两个巨石模块（2026-09-19 代码审计 F-08）。拆分（波次 2）的
最大风险不是"拆不开"，而是**拆的过程中悄悄改变注册表的内容或顺序**——
`BENCHMARK_ORDER` 决定遍历序，`BENCHMARK_DEFS`/`BENCHMARK_CANDIDATES`/
`_PHYSICAL_LAW` 决定语义。一旦漂移，账本三分类会静默变化而无人察觉
（"标签≠行为" 的镜像：拆完看着全绿，账本已换）。

本脚本把注册表导出为**规范化快照**（含逐项 sha256），供：
  - 拆前：`python scripts/registry_snapshot.py --out before.json`
  - 拆后：`python scripts/registry_snapshot.py --check before.json`
          逐项一致 ⇒ PASS；任何增删/改序/改候选名 ⇒ FAIL 并列出差异键。

用法
----
    python scripts/registry_snapshot.py --out  baseline.json
    python scripts/registry_snapshot.py --check baseline.json

注：本脚本**只读**注册表，不修改任何锚、不触碰判决路径。LLM 不进判决路径。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_LDA = os.path.join(_ROOT, "lda")
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

_KEYS = ("benchmark_order", "benchmark_defs_keys", "benchmark_candidates",
         "physical_law", "counts", "sha256")


def _snapshot():
    """读取三处注册表并规范化（只读）。"""
    from lda_harness import benchmarks, golden, verification_adapters

    order = list(benchmarks.BENCHMARK_ORDER)
    defs_keys = list(benchmarks.BENCHMARK_DEFS.keys())
    cand = verification_adapters.BENCHMARK_CANDIDATES
    cand_items = [[k, getattr(v, "__name__", type(v).__name__)] for k, v in cand.items()]
    law = sorted(golden._PHYSICAL_LAW)  # noqa: SLF001 (判据需读模块私有登记集)

    snap = {
        "benchmark_order": order,
        "benchmark_defs_keys": defs_keys,
        "benchmark_candidates": cand_items,
        "physical_law": law,
        "counts": {
            "benchmark_order": len(order),
            "benchmark_defs": len(defs_keys),
            "benchmark_candidates": len(cand_items),
            "physical_law": len(law),
        },
    }
    canon = json.dumps(snap, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    snap["sha256"] = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    return snap


def _brief(v):
    if isinstance(v, list):
        return "%d 项 %s" % (len(v), v[:6])
    return repr(v)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="LDA 注册表快照：导出/校验（F-08 巨石拆分判据）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--out", metavar="PATH", help="导出快照到 JSON")
    g.add_argument("--check", metavar="PATH", help="与既有快照逐项比对")
    args = ap.parse_args(argv)

    snap = _snapshot()

    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(snap, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        print("快照已写出：%s" % args.out)
        print("  counts=%s" % json.dumps(snap["counts"], ensure_ascii=False))
        print("  sha256=%s" % snap["sha256"])
        return 0

    with open(args.check, "r", encoding="utf-8") as fh:
        old = json.load(fh)

    diffs = [k for k in _KEYS if old.get(k) != snap.get(k)]
    if diffs:
        print("FAIL — 注册表与快照漂移，差异键：%s" % diffs)
        for key in diffs:
            print("  [%s] 快照 = %s" % (key, _brief(old.get(key))))
            print("  [%s] 当前 = %s" % (key, _brief(snap.get(key))))
        return 1

    print("PASS — 注册表与快照逐项一致（counts=%s）" %
          json.dumps(snap["counts"], ensure_ascii=False))
    print("  sha256=%s" % snap["sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
