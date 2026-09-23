"""LDA 命令行入口（v0.8.29 · 开发者钩子）。

让开源用户 / 工程师用一条命令感知 LDA 的设计—验证闭环，而不必读懂
整套引擎与锚体系。CLI 是**薄壳**：只做参数解析 + 装配 + 复用已有能力，
不引入新求解器 / 新判决逻辑（LLM 不进路径，死标量判决不变）。

子命令：
  lda design <kind> --target <float> [--top-k N]
      跑一个器件设计闭环，输出最优已验证候选（参数 / 指标 / 目标误差）。
  lda build <goal.json> --out <dir> [--wg W] [--top-k N]
      端到端单命令（P1-T1.2 · 指标 M1）：**一句话目标** → 设计包（DesignEngine
      真实闭环解参数）→ 版图 → GDS → DRC/LVS 双闸签核报告，全部落盘。
      与 `lda check` 的区别：check 收的是**参数已写死**的链路；build 收的是**目标**
      （参数由引擎解出），因此才是「端到端一条命令」。
  lda check  <spec.json>
      把一条链路（器件 + 互连 JSON）装配成版图，输出 DRC/LVS 双闸报告，
      并把 GDS 落盘。主权零依赖（纯标准库 + lda 内部模块）。
  lda report [--out DIR] [--quick]
      生成「基准对照验证闭环报告」（跨源死标量对照 + 实证语料覆盖矩阵）。
  lda gf <gdsfactory_component.py|json> [--out DIR]
      把 gdsfactory 组件描述转成 LDA 链路 spec（IR 兼容），再走 LDA
      设计—验证闭环 + DRC/LVS 双闸（对接最大开源光子生态，可选依赖）。
  lda check --gds <file.gds> [--out DIR]
      导入任意 GDSII（含 gdsfactory 导出），跑 LDA 主权几何 DRC 快查（子集）
      + 版图摘要（诚实边界：非 foundry 全量 DRC）。

红线：所有输出都是既有引擎 / harness / layout 的真实计算结果；CLI 不做
任何判决，只对结果做格式化呈现。
"""
from __future__ import annotations

import argparse
import json
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
    # —— 模式 B：直接导入任意 GDSII（含 gdsfactory 导出）→ 主权几何 DRC 快查 ——
    if getattr(args, "gds", None):
        from lda_l2.gds_export import parse_gds_polygons
        from lda_l2.gds_drc import check_geometry, geometry_drc_markdown
        try:
            with open(args.gds, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            print(f"[错误] 找不到 GDS 文件：{args.gds}", file=sys.stderr)
            return 2
        parsed = parse_gds_polygons(data)
        rep = check_geometry(parsed["structures"])
        print(f"# LDA 导入 GDSII 主权校验（{args.gds}）")
        print(f"- 库名：{parsed['libname']} · 结构数：{len(parsed['structures'])} "
              f"· 元素数：{rep['n_elements']}")
        print(geometry_drc_markdown(rep))
        return 0 if rep["all_pass"] else 1

    # —— 模式 A：链路 JSON → 官方布局布线 → DRC/LVS 双闸 + GDS ——
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
# lda build —— 一句话目标 → 设计包 → 版图 → GDS + 签核（P1-T1.2 · M1）
# --------------------------------------------------------------------------
def _goal_example_path() -> Path:
    """随包发布的「一句话目标」示例（干净 clone 下可直接跑）。"""
    return _ROOT / "examples" / "cli_build_goal.json"


def build_usage_hint() -> str:
    """无参数 / 用法错误时打印的可用指引（**不是 traceback**）。"""
    from lda_design import goal_build as gb
    ex = _goal_example_path()
    L = ["LDA 端到端单命令：一句话目标 → 设计包 → 版图 → GDS + 签核报告", "",
         "用法：",
         "  lda build <goal.json> --out <dir> [--wg 0.5] [--top-k 3]", "",
         "最省事的第一步（示例 goal 随包发布）：",
         f"  lda build {ex} --out reports", "",
         "goal.json 最小结构（devices 里 design.target ⇒ 引擎闭环解参数；",
         "params ⇒ 参数已知直接给定；两者都没有 ⇒ 用器件默认参数）：",
         '  {"domain": "photon", "name": "demo",',
         '   "devices": [{"id": "ring", "kind": "RingResonator",',
         '                "design": {"target": 17.5}}],',
         '   "nets": [], "io": [], "sources": []}', "",
         f"当前可由目标设计出参数的器件（引擎 kind 已桥接）：{gb.bridgeable_engine_kinds()}",
         f"其中版图 kind：{sorted(gb.LAYOUT_TO_ENGINE)}",
         "准入标准是「设计输出**确实进入版图几何**」，不是名字对得上；其余引擎 kind "
         "无 2D 版图表达、或与版图器件同名不同物、或设计输出在芯片级没有自由度"
         "（如 engine_waveguide 的 width）⇒ 本命令拒绝登记并报错（不静默丢弃）。",
         "参数已知的器件请直接用 params 给定（不受桥接表限制）。", "",
         "同族命令：`lda check <spec.json>`（参数已写死的链路）· "
         "`lda design <kind> --target <float>`（只出器件候选）"]
    return "\n".join(L)


def cmd_build(args: argparse.Namespace) -> int:
    from lda_design import goal_build as gb

    if not getattr(args, "goal", None):
        # 用法错误一律走 stderr（stdout 只留真实产物），且**给指引不抛 traceback**
        print(build_usage_hint(), file=sys.stderr)
        return 2

    try:
        with open(args.goal, "r", encoding="utf-8") as f:
            goal = json.load(f)
    except FileNotFoundError:
        print(f"[错误] 找不到 goal 文件：{args.goal}", file=sys.stderr)
        print(build_usage_hint(), file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"[错误] goal 不是合法 JSON：{e}", file=sys.stderr)
        return 2

    try:
        res = gb.build_goal(goal, args.out, wg_width=args.wg, top_k=args.top_k)
    except Exception as e:  # noqa: BLE001
        print(f"[错误] 构建失败：{str(e)[:200]}", file=sys.stderr)
        return 1

    if res.get("stage") == "assemble":
        print("[错误] goal 无法装配成链路：", file=sys.stderr)
        for e in res.get("errors", []):
            print(f"  - {e}", file=sys.stderr)
        print("", file=sys.stderr)
        print(build_usage_hint(), file=sys.stderr)
        return 2

    print(res["markdown"])
    s = res["summary"]
    print(f"产物：{res['report_paths']}")
    print(f"签核结论：{'✅ ACCEPT（DRC+LVS 双闸通过）' if s['verdict'] == 'ACCEPT' else '❌ REJECT（见上方明细）'}")
    return 0 if res.get("ok") else 1


# --------------------------------------------------------------------------
# lda gf —— gdsfactory 组件 → LDA 链路 spec（生态互通桥）
# --------------------------------------------------------------------------
def cmd_gf(args: argparse.Namespace) -> int:
    from lda_l1.gdsfactory_bridge import (
        gdsfactory_available, gf_component_to_spec, export_gf_component,
    )
    if not gdsfactory_available():
        print("[提示] gdsfactory 未安装（B 级可选依赖，不阻塞 LDA 自有路径）。")
        print("  对接 gdsfactory：pip install gdsfactory 后本命令可用；")
        print("  或直接用 `lda check --gds <file.gds>` 导入 gdsfactory 导出的 GDS 做主权校验。")
        return 0
    # 输入：.py（含 gf.Component 工厂）或 .json（已序列化的组件名列表）
    src = args.source
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        if src.endswith(".py"):
            import importlib.util
            spec = importlib.util.spec_from_file_location("lda_gf_user", src)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            comp = getattr(mod, "component", None) or getattr(mod, "C", None)
            if comp is None:
                print("[错误] gdsfactory 脚本须导出 `component`（gf.Component）", file=sys.stderr)
                return 2
        else:
            print(f"[错误] 暂仅支持 .py（gdsfactory 组件工厂），收到：{src}", file=sys.stderr)
            return 2
        lda_spec = gf_component_to_spec(comp, name=getattr(comp, "name", "gf_import"))
        spec_path = out_dir / f"{getattr(comp, 'name', 'gf_import')}.lda_spec.json"
        spec_path.write_text(json.dumps(lda_spec, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        print("# LDA ⇄ gdsfactory 兼容桥")
        print(f"- 已把 gdsfactory 组件 `{getattr(comp, 'name', '?')}` 转成 LDA 链路 spec：{spec_path}")
        print(f"- 设备 {len(lda_spec['devices'])} · IO {len(lda_spec['io'])}（互连由用户显式补或 LDA 自动布线）")
        print(f"- 下一步：lda check {spec_path}  → 走 LDA 设计—验证闭环 + DRC/LVS 双闸")
        print("- 或导出 GDS 校验：lda check --gds <gds>（export_gf_component 可用）")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"[错误] gdsfactory 桥处理失败：{str(e)[:160]}", file=sys.stderr)
        return 1


# --------------------------------------------------------------------------
# lda report
# --------------------------------------------------------------------------
def cmd_report(args: argparse.Namespace) -> int:
    from lda_harness.crosscheck_report import build_report, print_summary  # noqa: E402
    r = build_report(quick=args.quick, out_dir=args.out, archive=True)
    print_summary(r)
    s = r["score"]
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

    p_c = sub.add_parser("check", help="把链路 JSON 装配成版图，输出 DRC/LVS 双闸报告 + GDS；或导入 GDSII 做主权几何 DRC")
    p_c.add_argument("spec", nargs="?", help="链路描述 JSON 文件路径（与 --gds 二选一）")
    p_c.add_argument("--gds", default=None, help="导入任意 GDSII 文件（含 gdsfactory 导出）做主权几何 DRC 快查")
    p_c.add_argument("--out", default="reports", help="GDS/报告输出目录（默认 reports）")
    p_c.add_argument("--wg", type=float, default=0.5, help="波导宽度 µm（默认 0.5）")
    p_c.set_defaults(func=cmd_check)

    p_b = sub.add_parser(
        "build",
        help="一句话目标 → 设计包 → 版图 → GDS + DRC/LVS 签核（端到端单命令 · M1）")
    p_b.add_argument("goal", nargs="?",
                     help="一句话目标 JSON；不传则打印用法指引（不抛 traceback）")
    p_b.add_argument("--out", default="reports", help="产物输出目录（默认 reports）")
    p_b.add_argument("--wg", type=float, default=0.5, help="波导宽度 µm（默认 0.5）")
    p_b.add_argument("--top-k", type=int, default=3,
                     help="引擎闭环返回前 K 候选（默认 3）")
    p_b.set_defaults(func=cmd_build)

    p_g = sub.add_parser("gf", help="gdsfactory 组件 → LDA 链路 spec（生态互通桥，可选依赖）")
    p_g.add_argument("source", help="gdsfactory 组件工厂脚本（.py，导出 `component`）")
    p_g.add_argument("--out", default="reports", help="输出目录（默认 reports）")
    p_g.set_defaults(func=cmd_gf)

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
