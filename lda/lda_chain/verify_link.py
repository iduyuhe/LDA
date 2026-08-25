"""LDA P1-M4 · 链路设计→验证闭环 CLI 入口（双 ground 上提）。

用法
----
    python -m lda_chain.verify_link \
        --type wdm --channels 1.53,1.55,1.57,1.59 \
        --R 10 --gap 0.3 --kappa 0.05 --alpha 2.5 \
        --out <dir>

行为
----
    1. 链路规划（LinkModel：netlist + 放置 + 自动布线）
    2. 链路级联仿真（解析级联 + 布线损耗计入）
    3. 物理定律锚上提为 harness B19（无源无增益，经 VerificationHarness 死标量比对）
    4. 能量守恒诊断（无损特例）+ 无缺模型 + 布线完整
    5. 落盘 chip.gds + chip_report.json（含 B19 harness 判定）

诚实边界：链路级仅物理定律锚，缺系统级实证语料 → 不判 E 题。
LLM 不进判决路径（确定性级联 + 死标量比对）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict


def _build_spec(args) -> Dict[str, Any]:
    spec: Dict[str, Any] = {"type": args.type}
    if args.channels:
        spec["channels_um"] = [float(x) for x in args.channels.split(",") if x.strip()]
    if args.R is not None:
        spec["R_um"] = args.R
    if args.Rs:
        spec["Rs_um"] = [float(x) for x in args.Rs.split(",") if x.strip()]
    if args.gap is not None:
        spec["gap_um"] = args.gap
    if args.kappa is not None:
        spec["kappa"] = args.kappa
    if args.alpha is not None:
        spec["alpha_cm"] = args.alpha
    if args.n_g is not None:
        spec["n_g"] = args.n_g
    return spec


def main(argv=None):
    here = Path(__file__).resolve().parent.parent  # lda/
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))

    ap = argparse.ArgumentParser(description="LDA 链路设计→验证闭环（双 ground 上提）")
    ap.add_argument("--type", default="wdm", help="链路类型（当前仅 wdm）")
    ap.add_argument("--channels", default="1.53,1.55,1.57,1.59",
                    help="逗号分隔信道波长(um)")
    ap.add_argument("--R", type=float, default=10.0, help="默认环半径(um)")
    ap.add_argument("--Rs", default=None, help="逗号分隔逐环半径(um)，覆盖 --R")
    ap.add_argument("--gap", type=float, default=0.3, help="环-总线间隙(um)")
    ap.add_argument("--kappa", type=float, default=0.05, help="耦合系数（derived from gap 若省略）")
    ap.add_argument("--alpha", type=float, default=2.5, help="直波导损耗(dB/cm)")
    ap.add_argument("--n_g", type=float, default=4.2, help="群折射率")
    ap.add_argument("--out", default=None, help="输出目录（默认系统临时目录）")
    args = ap.parse_args(argv)

    from lda_agent.orchestrator import Orchestrator

    out_dir = args.out or tempfile.mkdtemp(prefix="lda_chip_")
    os.makedirs(out_dir, exist_ok=True)
    spec = _build_spec(args)

    print(f"[link] 规划链路 type={spec.get('type')} "
          f"channels={spec.get('channels_um')} ...")
    ctx = Orchestrator().run(spec, out_dir=out_dir)

    v = ctx.verification or {}
    b19 = v.get("b19_harness", {})
    ec = v.get("energy_conservation", {})
    accepted = (v.get("status") == "ok") and not ctx.error

    print("=" * 64)
    print("链路设计→验证闭环结果（双 ground 上提）")
    print("=" * 64)
    print(f"  接受状态          : {accepted}  (verification={v.get('status')}"
          f"{(' ERROR: '+ctx.error) if ctx.error else ''})")
    print(f"  B19 无源无增益     : {'PASS' if b19.get('passed') else 'FAIL'}"
          f"   max|T|={b19.get('candidate')}  ≤ golden={b19.get('golden')}"
          f"  tol={b19.get('tol')}  cmp={b19.get('cmp')}")
    print(f"  能量守恒(无损诊断): 逐源最大泄漏 = {ec.get('per_source_leak')}"
          f"  lossless_ok={ec.get('lossless_ok')}")
    print(f"  无缺模型          : {v.get('no_missing_models')}"
          f"  missing={v.get('missing_models')}")
    print(f"  布线完整          : {v.get('routing_complete')}"
          f"  blocked={v.get('blocked_nets')}")
    print(f"  物理锚            : {v.get('anchor')}  empirical_anchor={v.get('empirical_anchor')}")
    print(f"  诚实声明          : {v.get('honest_note')}")
    print("-" * 64)
    print(f"  GDS               : {os.path.join(out_dir, 'chip.gds')}")
    print(f"  报告              : {os.path.join(out_dir, 'chip_report.json')}")
    print("=" * 64)

    # 退出码：接受则 0，否则 1（供 CI / 自动化消费）
    return 0 if accepted else 1


if __name__ == "__main__":
    sys.exit(main())
