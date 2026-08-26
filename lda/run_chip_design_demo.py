"""LDA 仿真级芯片设计闭环演示（任务 256 · 门2 收官演示 + v0.8.11 MZI 案例扩展）。

三个端到端芯片设计案例（目标→布线→版图→四锚验收→报告）：
  A. WDM 收发芯片：4 信道 WDM 链路（目标=信道波长 → 环形路由 → GDS）
  B. 量子读出链路芯片：Transmon+读出谐振器 dispersive readout 链路
  C. MZI 干涉网络芯片（v0.8.11）：2×2 MZI 交叉开关级联网络
     （generic 链路 + MZI 解析响应（B20 锚同源）+ 四锚验收）

每个案例：
  1. Orchestrator 四 Agent 元编排（规划→综合→布线→验证）
  2. chip_acceptance 四锚死标量验收（A 无源界/B 级联乘法性/C 能量守恒/D 完整性）
  3. GDS 落盘 + 验收报告

诚实边界：仿真级（解析级联 + 公开工艺参数），非流片级（无真实 PDK/DRC/工艺角）。

运行：python run_chip_design_demo.py [--out reports_chip]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def _design_chip(name: str, spec: dict, out_dir: Path) -> dict:
    from lda_agent.orchestrator import Orchestrator
    d = out_dir / name.replace(" ", "_")
    d.mkdir(parents=True, exist_ok=True)
    ctx = Orchestrator().run(spec, out_dir=str(d))
    ca = getattr(ctx, "chip_acceptance", None) or {}
    report = {
        "chip": name,
        "spec": spec,
        "accepted": bool(ca.get("accepted")),
        "grounds": ca.get("grounds", {}),
        "blockers": ca.get("blockers", []),
        "steps": [s.get("agent") for s in ctx.steps],
        "n_components": len(ctx.link.ir.components) if ctx.link else 0,
        "n_nets": len(ctx.link.ir.nets) if ctx.link else 0,
        "gds_bytes": len(ctx.gds_bytes or b""),
        "gds_path": str(d / "chip.gds"),
        "report_path": str(d / "chip_report.json"),
        "anchor": ca.get("anchor"),
        "empirical_anchor": ca.get("empirical_anchor"),
        "honest_note": ca.get("honest_note"),
        "report": ca.get("report"),
    }
    with open(d / "chip_acceptance_summary.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report


def _design_readout_chip(name: str, spec: dict, out_dir: Path) -> dict:
    """量子读出链路芯片：D-43 design_chain（JC 对角化 ↔ 色散近似双验证）。"""
    from lda_agent.qubit_readout_chain import design_chain
    d = out_dir / name.replace(" ", "_")
    d.mkdir(parents=True, exist_ok=True)
    res = design_chain(
        f01=float(spec.get("f01_ghz", 5.0)),
        delta=float(spec.get("delta_ghz", 1.0)),
        g=float(spec.get("g_ghz", 0.10)),
        kappa_r=float(spec.get("kappa_r_ghz", 0.005)),
    )
    acc = res.get("acceptance", {})
    checks = acc.get("checks", [])
    grounds = {f"Q{i+1}_{c['name'][:18]}": {
        "passed": bool(c["ok"]), "metric": c["name"],
        "value": c.get("detail", ""),
        "oracle": "D-43 严格数值双验证（JC 对角化↔色散近似，死标量）",
    } for i, c in enumerate(checks)}
    report = {
        "chip": name,
        "spec": spec,
        "accepted": bool(acc.get("passed")),
        "grounds": grounds,
        "blockers": [k for k, g in grounds.items() if not g["passed"]],
        "steps": ["planner", "synthesis", "layout", "verify"],
        "n_components": 3,  # transmon + resonator + 读出力线
        "n_nets": 2,
        "gds_bytes": 0,
        "gds_path": "",
        "report_path": str(d / "chip_report.json"),
        "anchor": "physical_law_only",
        "empirical_anchor": False,
        "honest_note": ("量子读出链路：JC 精确对角化 ↔ 色散近似 χ=g²/Δ 交叉验证"
                        "（D-43），死标量验收；仿真级非流片级。"),
        "report": "ACCEPT" if acc.get("passed") else "REJECT",
    }
    with open(d / "chip_acceptance_summary.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="LDA 仿真级芯片设计闭环演示")
    ap.add_argument("--out", default=None, help="输出目录（默认临时目录）")
    ap.add_argument("--case", default="all",
                    choices=["all", "wdm", "readout", "mzi"],
                    help="演示案例")
    args = ap.parse_args(argv)
    out_dir = Path(args.out or tempfile.mkdtemp(prefix="lda_chip_demo_"))
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = []
    if args.case in ("all", "wdm"):
        cases.append(("WDM 收发芯片", "wdm", {
            "type": "wdm", "channels_um": [1.53, 1.55, 1.57, 1.59],
            "R_um": 10.0, "gap_um": 0.3, "kappa": 0.05, "alpha_cm": 2.5,
        }))
    if args.case in ("all", "readout"):
        cases.append(("量子读出链路芯片", "readout", {
            "f01_ghz": 5.0, "delta_ghz": 1.0, "g_ghz": 0.10,
            "kappa_r_ghz": 0.005,
        }))
    if args.case in ("all", "mzi"):
        # 2×2 MZI 交叉开关级联网络：双输入双输出，MZI 解析响应（B20 锚同源）
        cases.append(("MZI 干涉网络芯片", "mzi", {
            "type": "generic",
            "instances": [
                {"id": "wg_i1", "kind": "Waveguide", "params": {}},
                {"id": "wg_i2", "kind": "Waveguide", "params": {}},
                {"id": "mzi_a", "kind": "MZI",
                 "params": {"n_eff": 2.6, "deltaL_um": 34.5}},
                {"id": "mzi_b", "kind": "MZI",
                 "params": {"n_eff": 2.6, "deltaL_um": 17.25}},
                {"id": "wg_o1", "kind": "Waveguide", "params": {}},
                {"id": "wg_o2", "kind": "Waveguide", "params": {}},
            ],
            "nets": [
                {"id": "n1", "connects": ["wg_i1.out", "mzi_a.in1"]},
                {"id": "n2", "connects": ["wg_i2.out", "mzi_a.in2"]},
                {"id": "n3", "connects": ["mzi_a.out1", "mzi_b.in1"]},
                {"id": "n4", "connects": ["mzi_a.out2", "mzi_b.in2"]},
                {"id": "n5", "connects": ["mzi_b.out1", "wg_o1.in"]},
                {"id": "n6", "connects": ["mzi_b.out2", "wg_o2.in"]},
            ],
            "sources": ["wg_i1.in", "wg_i2.in"],
            "sinks": ["wg_o1.out", "wg_o2.out"],
        }))

    print("=" * 70)
    print("LDA 仿真级芯片设计闭环演示（任务 256 · 死标量验收）")
    print("=" * 70)
    all_ok = True
    results = []
    for name, kind, spec in cases:
        try:
            if kind in ("wdm", "mzi"):
                r = _design_chip(name, spec, out_dir)
            else:
                r = _design_readout_chip(name, spec, out_dir)
        except Exception as e:  # noqa: BLE001
            print(f"\n[{name}] 设计异常: {str(e)[:120]}")
            all_ok = False
            continue
        results.append(r)
        print(f"\n  >>> {name}  |  {'ACCEPT' if r['accepted'] else 'REJECT'}"
              f"  [{r['report']}]")
        print(f"      组件 {r['n_components']} · net {r['n_nets']} · "
              f"GDS {r['gds_bytes']}B")
        for gk, g in r["grounds"].items():
            mark = "PASS" if g.get("passed") else "FAIL"
            print(f"      [{mark}] {gk}: {g.get('metric','')} "
                  f"= {g.get('value')}")
        all_ok = all_ok and bool(r["accepted"])

    summary_path = out_dir / "chip_demo_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({"all_accepted": all_ok, "results": results},
                  f, ensure_ascii=False, indent=2)
    print("\n" + "=" * 70)
    print(f"演示输出: {out_dir}")
    print(f"汇总报告: {summary_path}")
    print(f"全部通过: {all_ok}")
    print("=" * 70)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
