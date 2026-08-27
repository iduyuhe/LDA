"""v0.8.27 千器件芯片级演示（版图差距 #7 收官后 · 千器件版图接入演示）。

把千器件规模能力接入**芯片级演示闭环**：1000 器件链式链路 → 2D 放置 →
多层布线（跨行跳线走 M2）→ **可测芯片版图导出**（GDS + IO 光栅 + 统计 +
DRC + LVS 签核双闸）→ markdown 报告落盘。

与既有演示的区别：
  - run_chip_design_demo（WDM/量子/MZI 案例）：Orchestrator 四 Agent + 四锚验收，
    小规模（<20 器件）；
  - run_chip_scale_demo（本脚本）：**千器件级**——构建→放置→布线→GDS→DRC→
    LVS 全链路，死标量验收（LVS ACCEPT + DRC 全过 + GDS 可解析 + 性能预算）。

IO 接入：链式链路 wg0.in（源）+ wg999.out（汇）标记外部 IO → 光栅耦合器
接入（芯片可光纤耦合测试，与 v0.8.11d IO 光栅同机制）。

诚实边界：仿真级（公开工艺近似 + 规则链式布线），非流片级；DRC 为器件级
可制造性自查（非真实 PDK 全规则）。

运行：python run_chip_scale_demo.py [--n 1000] [--cols 32] [--out reports_chip_scale]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

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
    return cond


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="千器件芯片级演示（v0.8.27）")
    ap.add_argument("--n", type=int, default=1000, help="器件数（默认 1000）")
    ap.add_argument("--cols", type=int, default=32, help="放置列数")
    ap.add_argument("--out", default="reports_chip_scale",
                    help="报告输出目录（相对 lda/）")
    args = ap.parse_args(argv)
    n, cols = args.n, args.cols
    out_dir = Path(_HERE) / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    t_start = time.perf_counter()
    print(f"千器件芯片级演示（n={n} · cols={cols} · 构建→放置→多层布线→GDS→DRC→LVS）")
    print("=" * 64)

    from lda_harness.scale_anchor import build_chain_case
    from lda_l2.chip_layout_export import export_chip_gds

    # ① 构建 + IO 标记（源/汇 → IO 光栅接入）
    link, placement, routes = build_chain_case(n_devices=n, cols=cols)
    link.mark_source("wg0", "in", net_id="src_in")
    link.external_io("out_wg999", "wg999", "out")
    t_build = time.perf_counter()
    print(f"[1/4] 千器件链路构建 + IO 标记: {t_build - t_start:.2f}s")
    check("链路构建：n 器件 / (n-1) 内部 net",
          len(link.ir.components) == n and len(link.ir.nets) >= n - 1,
          f"dev={len(link.ir.components)} net={len(link.ir.nets)}")

    # ② 芯片版图导出（GDS + 统计 + DRC + LVS 双闸）
    r = export_chip_gds(link, placement, routes)
    t_gds = time.perf_counter()
    print(f"[2/4] 芯片版图导出（GDS/DRC/LVS）: {t_gds - t_build:.2f}s")
    st = r["gds_stats"]
    check("版图统计：千器件 + 千 net + 多层标记",
          st["n_devices"] == n and st["n_nets"] >= n - 1
          and st.get("multilayer") is True,
          f"dev={st['n_devices']} net={st['n_nets']} multi={st.get('multilayer')}")
    check("IO 接入：源/汇 2 个光栅耦合器端口",
          st["n_io"] == 2 and len(r["io_ports"]) == 2,
          f"io={st['n_io']} ports={r['io_ports']}")
    check("GDS round-trip 可解析（1999+ 元素）",
          isinstance(r["gds_parse"], dict)
          and r["gds_parse"].get("n_structures", 0) >= 1
          and st["n_elements"] >= 2 * n - 1,
          f"elements={st['n_elements']} gds={st['gds_bytes']}B")

    # ③ DRC 可制造性（千器件全过）
    drc = r["drc_report"]
    print(f"[3/4] DRC 可制造性自查: {drc['n_pass']}/{drc['n_checked']}")
    check("DRC：千器件可制造性全过（死标量）",
          drc["all_pass"] and drc["n_pass"] == n,
          f"{drc['n_pass']}/{drc['n_checked']}")

    # ④ LVS 签核（多层：层叠短路语义）
    lvs = r["lvs_report"]
    print(f"[4/4] LVS 签核（多层 M1/VIA12/M2）: {lvs['verdict']}")
    check("LVS：千器件版图-原理图一致 ACCEPT（0 违规）",
          lvs["verdict"] == "ACCEPT" and lvs["n_violations"] == 0,
          f"viol={lvs['n_violations']} match={lvs['match']}")
    check("LVS：网络全匹配（999/999）",
          lvs["match"]["n_nets_match"] == lvs["match"]["n_nets_total"] == n - 1,
          f"{lvs['match']['n_nets_match']}/{lvs['match']['n_nets_total']}")

    # ⑤ 性能预算 + 报告落盘
    t_total = time.perf_counter() - t_start
    check(f"性能预算：千器件全链路 ≤ 10s", t_total <= 10.0, f"{t_total:.2f}s")

    report = {
        "title": f"千器件芯片级演示（n={n} · 版图 7 差距收官）",
        "n_devices": n,
        "n_nets": n - 1,
        "gds_bytes": st["gds_bytes"],
        "chip_bbox_um": st["bbox_um"],
        "chip_area_um2": st["area_um2"],
        "io_ports": r["io_ports"],
        "drc": {"n_pass": drc["n_pass"], "n_checked": drc["n_checked"],
                "all_pass": drc["all_pass"]},
        "lvs": {"verdict": lvs["verdict"], "n_violations": lvs["n_violations"],
                "match": lvs["match"], "stack": lvs.get("stack", {})},
        "time_total_s": round(t_total, 2),
        "accepted": bool(drc["all_pass"] and lvs["verdict"] == "ACCEPT"),
    }
    with open(out_dir / "chip_scale_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    L = []
    L.append("# 千器件芯片级演示报告（v0.8.27 · 版图 7 差距收官）")
    L.append("")
    L.append(f"- 芯片：**{n} 器件链式链路**（{n - 1} 条内部 net）· 2D 放置（{cols} 列）· "
             "多层布线（跨行跳线走 M2）")
    L.append(f"- IO 端口（光栅耦合器接入）：`{'` `'.join(r['io_ports'])}`")
    L.append(f"- 芯片 bbox：{st['bbox_um']} µm · 面积 {st['area_um2']} µm²")
    L.append(f"- GDS：{st['gds_bytes']} B · {st['n_elements']} 元素 · "
             f"{st['n_structures']} 结构（round-trip 可解析）")
    L.append(f"- DRC：**{drc['n_pass']}/{drc['n_checked']} 器件通过**"
             f"（{'✅ 可制造性自查通过' if drc['all_pass'] else '❌ 有违规'}）")
    L.append(f"- LVS：**{lvs['verdict']}**（{lvs['match']['n_nets_match']}/"
             f"{lvs['match']['n_nets_total']} 网一致 · 违规 {lvs['n_violations']} 项 · "
             f"层栈 {lvs.get('stack', {}).get('name', '?')}）")
    L.append(f"- 全链路耗时：**{t_total:.2f}s**（构建+放置+布线+GDS+DRC+LVS）")
    L.append(f"- 验收：**{'✅ ACCEPT' if report['accepted'] else '❌ REJECT'}**"
             "（DRC 全过 ∧ LVS ACCEPT，死标量）")
    L.append("")
    L.append("*诚实边界：仿真级（公开工艺近似 + 规则链式布线），非流片级；"
             "DRC 为器件级可制造性自查，真实 PDK 全规则属发动期。*")
    md_path = out_dir / "chip_scale_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))

    print("=" * 64)
    print(f"千器件芯片演示：{_PASS} PASS / {_FAIL} FAIL · 全链路 {t_total:.2f}s")
    print(f"报告：{md_path}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
