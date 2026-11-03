# -*- coding: utf-8 -*-
"""B3 · **数字链干线**（综合→布局→布线→DRC 用现状模块串起来）。

═══════════════════════════════════════════════════════════════════════════════
定位：把 S3 新落地的「结构级 Verilog 子集」直接喂进**现状的数字链**——
`dverilog.parse → dsynth.Netlist → dplac.place → ddetail.detail_route → ddrc_lvs`
—— 跑通一份 ISCAS/EPFL 门级网表，并**每段显式断言「吃的是上一段的输出」**：

  · parse 输出（Netlist）有门 → 断言非空；
  · place 输入 = parse 的 Netlist，输出 Placement 覆盖**每一颗门**（cell_xywh 数 == 门数）；
  · route 输入 = (Netlist, Placement)，输出 DetailRoute 的 net_pins 覆盖**每一条网**；
  · drc/lvs 输入 = route 的 shapes + net_pins，如实报告违规数（不伪造干净 tapeout）。

🔴 **守恒断言是机核，不是装饰**：任何一段没真消费上一段的输出（门数/网数丢了），
   干线直接 fail-closed 报错，绝不放行「看起来跑通了」。

═══════════════════════════════════════════════════════════════════════════════
诚实边界（全部 `claimable=False`，如实披露）
───────────────────────────────────────────────────────────────────────────────
· **ddetail.detail_route 的 `claimable=False`**：当前主链路由器在 c17 上实测产 101 处 DRC
  违规（87 间距 + 14 通孔包围——所有线堆到一条 track），是**已知诚实边界**，非干线缺陷。
  干线**如实报告** DRC/LVS 违规数，绝不伪造「clean tapeout」。
· **几何/时序是模型假设**（见 dplac.DPLAC_DISCLOSURE / ddetail 披露）：行式布局、贪心+有限
  爬山、无电源条/阱/detail route；die 面积、IO ring 均为一阶假设。
· **C 级自主**：纯标准库 + 复用既有模块，零第三方依赖，LLM 不进判决路径。
· **非 foundry PDK**：单元库（INV/NAND2）为教科书尺度，非真实工艺；不报流片实测。
"""
from __future__ import annotations

import os
import sys

# 让本模块既可作为包成员（lda_l2.ecore.db3_trunk）导入，也可作为独立脚本运行。
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _distinct_nets(nl) -> set:
    """从 dsynth.Netlist 收全集所有网名（输出 + 输入）。"""
    s = set()
    for g in nl.gates:
        s.add(g.out)
        s.update(g.ins)
    return s


def run_trunk(nl):
    """跑通「parse 输出 → place → route → drc/lvs」全链，返回带守恒断言的报告 dict。

    每段都断言「吃的是上一段的输出」；任一守恒失败 → 抛 AssertionError（fail-closed）。
    """
    from lda_l2.ecore import dplac, ddetail, ddrc_lvs          # 延迟导入，避免顶层重依赖

    report = {"stages": [], "conservation_ok": True, "problems": []}

    # ── 段 0：解析输出（Netlist）──────────────────────────────────────
    if nl is None or len(getattr(nl, "gates", ())) == 0:
        raise ValueError("段0：parse 输出为空（无门实例）—— 干线无米下锅")
    nets_all = _distinct_nets(nl)
    report["stages"].append(("parse", {
        "gates": len(nl.gates), "nets": len(nets_all),
        "inputs": len(getattr(nl, "inputs", ())),
        "outputs": len(getattr(nl, "outputs", {})),
    }))

    # ── 段 1：布局（输入 = parse 的 Netlist）────────────────────────────
    p = dplac.place(nl)                 # 默认 tech = DC.DEFAULT_TECH
    placed_cells = len(p.cell_xywh)
    if placed_cells != len(nl.gates):   # 🔴 守恒断言：place 必须覆盖每一颗门
        raise AssertionError(
            "段1 守恒失败：place 覆盖 %d 颗门，但 Netlist 有 %d 颗（丢了门）"
            % (placed_cells, len(nl.gates)))
    report["stages"].append(("place", {
        "cells": placed_cells, "die_w_um": round(p.die_w_um, 3),
        "die_h_um": round(p.die_h_um, 3), "hpwl_um": round(p.hpwl_um, 3),
        "cell_area_sum_um2": round(p.cell_area_sum_um2, 4),
    }))

    # ── 段 2：布线（输入 = (Netlist, Placement)）───────────────────────
    r = ddetail.detail_route(nl, p)
    routed_nets = set(r.net_pins.keys())
    missing = nets_all - routed_nets   # 🔴 守恒断言：route 必须覆盖每一条网
    if missing:
        raise AssertionError(
            "段2 守恒失败：route 未覆盖网 %s（Netlist 有 %d 条网，route 覆盖 %d 条）"
            % (sorted(missing), len(nets_all), len(routed_nets)))
    report["stages"].append(("route", {
        "shapes": len(r.shapes), "nets": r.n_nets,
        "routed_nets": len(r.net_pins),
        "routed_segments": r.n_routed_segments,
    }))

    # ── 段 3：DRC / LVS（输入 = route 的 shapes + net_pins）──────────────
    drc = ddrc_lvs.run_drc(r.shapes)
    lvs = ddrc_lvs.run_lvs(r.shapes, r.net_pins)
    report["stages"].append(("drc_lvs", {
        "drc_ok": drc["ok"], "drc_violations": len(drc["violations"]),
        "lvs_ok": lvs["ok"], "lvs_problems": len(lvs["problems"]),
    }))

    # ── 段 4：DEF 写出（输入 = 段1 的落点 + 段0 的 Netlist）──────────────
    #    🔴 只写 placed DEF（落点 + 连接），**不写 ROUTED**：ddetail.shapes 没有网归属，
    #       强行写就是编造。布线导出须先给 shape 打网标签（后续里程碑）。
    from lda_l2.ecore import ddef as DD
    design = DD.from_placement(p, nl, name="lda_c17")
    text = DD.serialize_def(design)
    back = DD.parse_def(text)
    if DD.serialize_def(back) != text:                 # 写出→读回→再写出 必须字节一致
        raise AssertionError("段4 守恒失败：DEF 往返不是字节级双射")
    if len(back.components) != len(nl.gates):
        raise AssertionError("段4 守恒失败：DEF 组件 %d != 门数 %d"
                             % (len(back.components), len(nl.gates)))
    if len(back.nets) != len(nets_all):
        raise AssertionError("段4 守恒失败：DEF 网 %d != Netlist 网 %d"
                             % (len(back.nets), len(nets_all)))
    _got = {c.name: (c.macro, c.x, c.y) for c in back.components}
    for c in design.components:
        if _got.get(c.name) != (c.macro, c.x, c.y):
            raise AssertionError("段4 守恒失败：组件 %s 的宏名/落点在往返后变了" % c.name)
    report["stages"].append(("def_write", {
        "bytes": len(text), "components": len(back.components),
        "nets": len(back.nets), "terms": sum(len(n.terms) for n in back.nets),
        "units": back.units, "roundtrip_ok": True,
        "routed_exported": False,
    }))

    report["drc_lvs_detail"] = {
        "drc": drc, "lvs": lvs,
        "claimable": False,
        "note": "ddetail.detail_route 当前 claimable=False：c17 实测 101 处 DRC 违规"
                "（87 间距 + 14 通孔包围——线堆单 track），为已知诚实边界，非干线缺陷。",
    }
    return report


def run_trunk_from_verilog(src: str) -> dict:
    """从 Verilog 源文本跑干线（先 dverilog.parse 再 run_trunk）。"""
    from lda_l2.ecore.dverilog import parse as parse_verilog
    nl = parse_verilog(src)
    return run_trunk(nl)


# ═══════════════════════════════════════════════════════════════════════════
# 代表性 ISCAS-85 c17（S3 dverilog.SAMPLE_VERILOG 同款；在此模块内按需导入）
# ═══════════════════════════════════════════════════════════════════════════
def _get_sample_verilog() -> str:
    from lda_l2.ecore.dverilog import SAMPLE_VERILOG
    return SAMPLE_VERILOG


def _fmt_report(rep: dict) -> str:
    lines = ["B3 数字链干线报告", "=" * 48]
    labels = {"parse": "段0 解析(Verilog→Netlist)",
              "place": "段1 布局(place)", "route": "段2 布线(route)",
              "drc_lvs": "段3 DRC/LVS"}
    for stage, data in rep["stages"]:
        lines.append("%s" % labels.get(stage, stage))
        for k, v in data.items():
            lines.append("    %-18s %s" % (k, v))
    d = rep["drc_lvs_detail"]
    lines.append("")
    lines.append("诚实边界（claimable=False）：")
    lines.append("    " + d["note"])
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as fh:
            src = fh.read()
        label = sys.argv[1]
    else:
        src = _get_sample_verilog()
        label = "SAMPLE_VERILOG (ISCAS-85 c17)"
    rep = run_trunk_from_verilog(src)
    print(_fmt_report(rep))
    print("\n来源: %s" % label)
    raise SystemExit(0)
