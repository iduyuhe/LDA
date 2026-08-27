"""LDA 命令行入口（v0.8.29 · 开发者钩子）。

让开源用户 / 工程师用一条命令感知 LDA 的设计—验证闭环，而不必读懂
整套引擎与锚体系。CLI 是**薄壳**：只做参数解析 + 装配 + 复用已有能力，
不引入新求解器 / 新判决逻辑（LLM 不进路径，死标量判决不变）。

子命令：
  lda design <kind> --target <float> [--top-k N]
      跑一个器件设计闭环，输出最优已验证候选（参数 / 指标 / 目标误差）。
  lda check  <spec.json>
      把一条链路（器件 + 互连 JSON）装配成版图，输出 DRC/LVS 双闸报告，
      并把 GDS 落盘。主权零依赖（纯标准库 + lda 内部模块）。
  lda report [--out DIR] [--quick]
      生成「基准对照验证闭环报告」（跨源死标量对照 + 实证语料覆盖矩阵）。

红线：所有输出都是既有引擎 / harness / layout 的真实计算结果；CLI 不做
任何判决，只对结果做格式化呈现。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent  # lda/ 包根
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lda_design.design_engine import DesignEngine  # noqa: E402
from lda_chain.link_model import LinkModel  # noqa: E402
from lda_chain.route_sim import layout_only  # noqa: E402
from lda_l2.chip_layout_export import (  # noqa: E402
    export_chip_gds,
    layout_markdown,
)
from run_benchmark_crosscheck_report import run_crosscheck  # noqa: E402


# --------------------------------------------------------------------------
# lda design
# --------------------------------------------------------------------------
def cmd_design(args: argparse.Namespace) -> int:
    eng = DesignEngine()
    if args.kind not in eng.specs:
        avail = ", ".join(sorted(eng.specs))
        print(f"[错误] 未知器件类型 {args.kind}；可选：{avail}", file=sys.stderr)
        return 2
    try:
        target = float(args.target)
    except (TypeError, ValueError):
        print(f"[错误] --target 须为数值，收到：{args.target!r}", file=sys.stderr)
        return 2

    res = eng.design(args.kind, target, top_k=args.top_k, verify_top_k=args.top_k)
    best = res.get("best")
    print(f"# LDA 设计闭环 · {res['title']}")
    print(f"- 目标：{target} {res.get('target_unit', '')} "
          f"（指标：{res['metric_name']}）")
    print(f"- 搜索 {res['searched']} 候选 · 验证 {res['verified']} · "
          f"通过 {res['passed']}")
    if not best:
        print("- 结果：**无通过候选**（可在更宽 sweep 域内重试）")
        return 1
    print(f"- **最优候选**（err={best['err']:.5f}）：")
    print(f"    params: {json.dumps(best['params'], ensure_ascii=False)}")
    print(f"    metric: {best.get('metric')}")
    print(f"    verdict: {best.get('verdict', '')[:160]}")
    if args.json:
        print("\n--- JSON ---")
        print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
    return 0


# --------------------------------------------------------------------------
# lda check —— 从 JSON 造 LinkModel，复用 layout_only 做布局+自动布线
# --------------------------------------------------------------------------
def _build_link(spec: Dict[str, Any]) -> LinkModel:
    """从用户 JSON 装配 link（布局/布线由 layout_only 生成，复用官方路径）。

    JSON schema：
      {
        "domain": "photon" | "quantum",
        "name": "...",
        "devices": [{"id":"d1","kind":"Waveguide","params":{...}}, ...],
        "nets":    [{"net":"n1","from":["d1","out"],"to":["d2","in"]}, ...],
        "io":      [{"net":"e1","device":"d1","port":"in"}, ...],
        "sources": [{"device":"d1","port":"in"}, ...]
      }
    """
    domain = spec.get("domain", "photon")
    link = LinkModel(domain=domain, name=spec.get("name", "cli-link"))
    for d in spec.get("devices", []):
        link.add_device(d["id"], d["kind"], params=d.get("params"))
    for nt in spec.get("nets", []):
        f, t = nt["from"], nt["to"]
        link.connect(nt["net"], f[0], f[1], t[0], t[1])
    for io in spec.get("io", []):
        link.external_io(io["net"], io["device"], io["port"])
    for s in spec.get("sources", []):
        link.mark_source(s["device"], s["port"])
    return link


def cmd_check(args: argparse.Namespace) -> int:
    try:
        with open(args.spec, "r", encoding="utf-8") as f:
            spec = json.load(f)
    except FileNotFoundError:
        print(f"[错误] 找不到 spec 文件：{args.spec}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"[错误] spec 不是合法 JSON：{e}", file=sys.stderr)
        return 2

    link = _build_link(spec)
    # 复用官方 layout_only 生成 placement + routes（含自动布线 + 损耗）
    try:
        lay = layout_only(link, wg_width=args.wg)
        placement, routes = lay["placement"], lay["routes"]
    except Exception as e:  # noqa: BLE001
        print(f"[错误] 布局/布线失败：{str(e)[:160]}", file=sys.stderr)
        return 1
    try:
        md = layout_markdown(link, placement, routes, wg_width=args.wg)
    except Exception as e:  # noqa: BLE001
        print(f"[错误] 版图导出失败：{str(e)[:160]}", file=sys.stderr)
        return 1

    print(md)

    # GDS 落盘
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    rep = export_chip_gds(link, placement, routes, wg_width=args.wg)
    gds_path = out_dir / f"{link.ir.name or 'chip'}.gds"
    gds_path.write_bytes(rep["gds_bytes"])
    print(f"\nGDS 已导出：{gds_path}（{rep['gds_stats']['gds_bytes']} B）")

    # 双闸判决结论
    drc = rep["drc_report"]
    lvs = rep["lvs_report"]
    ok = bool(drc.get("all_pass")) and lvs.get("verdict") == "ACCEPT"
    print(f"签核结论：{'✅ ACCEPT（DRC+LVS 双闸通过）' if ok else '❌ REJECT（见上方明细）'}")
    return 0 if ok else 1


# --------------------------------------------------------------------------
# lda report
# --------------------------------------------------------------------------
def cmd_report(args: argparse.Namespace) -> int:
    data = run_crosscheck(quick=args.quick)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "benchmark_crosscheck_report.md"
    js_path = out_dir / "benchmark_crosscheck_report.json"
    from run_benchmark_crosscheck_report import _fmt_report  # noqa: E402
    md_path.write_text(_fmt_report(data), encoding="utf-8")
    js_path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    s = data["summary"]
    print(f"# LDA 基准对照验证闭环报告")
    print(f"- 引擎 {s['engines_passed']}/{s['engines_total']} PASS · "
          f"rel max={s['rel_max_pct']}% median={s['rel_median_pct']}%")
    print(f"- 含解析契约锚 rel + 实证语料实测值 + loss 类引擎对照 + ORACLE 状态")
    print(f"- 诚实边界：{data['honest_note'][:120]}...")
    print(f"报告: {md_path}")
    print(f"数据: {js_path}")
    return 0 if s["engines_passed"] == s["engines_total"] else 1


# --------------------------------------------------------------------------
# main / argparse
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="lda",
        description="LDA — Agent-native 开源光芯片(PDA)+量子芯片(QEDA)设计软件 CLI",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_d = sub.add_parser("design", help="跑一个器件设计闭环，输出最优已验证候选")
    p_d.add_argument("kind", help="器件类型，如 Waveguide / RingResonator / Transmon")
    p_d.add_argument("--target", required=True, help="设计目标值（数值）")
    p_d.add_argument("--top-k", type=int, default=5, help="返回前 K 个候选（默认 5）")
    p_d.add_argument("--json", action="store_true", help="额外输出完整 JSON")
    p_d.set_defaults(func=cmd_design)

    p_c = sub.add_parser("check", help="把链路 JSON 装配成版图，输出 DRC/LVS 双闸报告 + GDS")
    p_c.add_argument("spec", help="链路描述 JSON 文件路径")
    p_c.add_argument("--out", default="reports", help="GDS/报告输出目录（默认 reports）")
    p_c.add_argument("--wg", type=float, default=0.5, help="波导宽度 µm（默认 0.5）")
    p_c.set_defaults(func=cmd_check)

    p_r = sub.add_parser("report", help="生成基准对照验证闭环报告")
    p_r.add_argument("--out", default="reports", help="输出目录（默认 reports）")
    p_r.add_argument("--quick", action="store_true", help="仅解析快引擎子集（CI）")
    p_r.set_defaults(func=cmd_report)

    return ap


def main(argv: List[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
