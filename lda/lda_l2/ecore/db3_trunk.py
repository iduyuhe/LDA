# -*- coding: utf-8 -*-
"""B3 · **数字链干线**（Verilog → Netlist → 布局 → 布线 → DRC/LVS → DEF）。

═══════════════════════════════════════════════════════════════════════════════
定位：把 S3 的结构级 Verilog 子集直接喂进数字链，跑通 ISCAS-85 c17，并
**每段显式断言「吃的是上一段的输出」**。

  · parse 输出（Netlist）有门 → 断言非空；
  · place 输入 = parse 的 Netlist，输出必须覆盖**每一颗门**；
  · route 输入 = (Netlist, Placement)，输出必须让**每一条网有且仅有一类归属**
    （已布 / 端口未布 / 布失败 —— 三类互斥且并集 == 全集）；
  · drc/lvs 输入 = route 的 shapes + pins，如实报告；**结论必须带作用域**；
  · def_write 输入 = 段1 的落点 + 段0 的 Netlist，往返必须字节级双射。

🔴 **守恒断言是机核，不是装饰**：任何一段没真消费上一段的输出，干线直接 fail-closed，
   绝不放行「看起来跑通了」。

═══════════════════════════════════════════════════════════════════════════════
v0.9.376：**主链切换到 `dpnr`（B 系列 P&R），旧链 `ddetail.detail_route` 降为 baseline**
───────────────────────────────────────────────────────────────────────────────
为什么切（审计 2026-11-04 实测，同一份 c17）：

  | 链 | 布通网数 | DRC | LVS |
  |---|---|---|---|
  | `dpnr`（新主链） | **4 / 11**（7 条端口网未建模） | **0**（仅这 4 条网） | **0**（仅这 4 条网） |
  | `detail_route`（baseline） | 11 / 11 | **87** | **183 条短路条目 / 43 对网** |

🔴 **这不是「变好了」，是「口径不同」**，两件事必须同时说：
  · 新主链 DRC=0 只覆盖 **4/11** 条网 —— 7 条接 primary I/O 的网**布不了**（端口未建模）；
  · 旧链「覆盖 11 条网」但代价是 87 处间距违规 + 183 条短路条目（连通性错误）。
⇒ 所以本版**双报一版**：`report["stages"]`（主链）与 `report["baseline"]`（旧链）并排，
  让「口径变化」可见，而不是静默替换掉旧证据。旧数字在下版之前**不得删除**。

🔴 **面积不是免费的**：主链 die **33.696 µm²** vs 旧链 **3.401 µm²** ⇒ **×9.909**。
   代价来自 `CELL_GAP`（为引脚可达性预留间距），**是 pin 可达性的面积代价，不是工艺升级**。
   `report["area_delta"]` 显式给出两者与该比值，卡片同源。

═══════════════════════════════════════════════════════════════════════════════
诚实边界（全部 `claimable=False`，如实披露）
───────────────────────────────────────────────────────────────────────────────
· **主链 `claimable=False`**：`dpnr` 只布 4/11 条网（端口未建模），且单元内部仍黑盒、
  单摆多行、无绕障/拥塞求解、无寄生/时序 ⇒ **不产可签核结果**。
· **baseline `claimable=False`**：`detail_route` 在 c17 实测 DRC 87 处 `min_spacing`
  ＋ LVS 183 条短路条目（78 `short` + 105 `short_via`，去重 43 对网）—— 是**连通性错误**，
  不是「余量不足」。根因是容量不足（通道 2<7 · 引脚槽 0.96µm>单元宽 0.067µm · 列 6.12µm>die 1.09µm），
  见 `ddetail.drc_capacity_bound`。
· **几何/时序是模型假设**（见 dplac/dpnr/ddetail 披露）：行式布局、贪心+有限爬山、
  无电源条/阱、detail route 为一阶模型；die 面积、IO ring 均为一阶假设。
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

#: 主链标识（v0.9.376 起）。**写进报告**，供门禁与卡片核对「这一版到底跑的是哪条链」。
TRUNK_CHAIN = "dpnr"
#: 对照链标识（双报一版过渡期保留；数字不得删除）。
BASELINE_CHAIN = "detail_route"


def _distinct_nets(nl) -> set:
    """从 dsynth.Netlist 收全集所有网名（输出 + 输入）。"""
    s = set()
    for g in nl.gates:
        s.add(g.out)
        s.update(g.ins)
    return s


def _count_by_rule(items) -> dict:
    """按规则名计数（DRC violation / LVS problem 的首元素都是规则名）。

    🔴 为什么必须分类：LVS 在 c17 上报 **183 处**，若只给总数，读者会当成「间距紧、余量大一点就好」；
    实际是 **78 处同层 `short` + 105 处 `short_via`** —— **电气连通性错误**。
    这两件事的处置方式完全不同，混成一个数就是口径失真。
    """
    out: dict = {}
    for it in items or []:
        rule = it[0] if isinstance(it, (list, tuple)) and it else str(it)
        out[str(rule)] = out.get(str(rule), 0) + 1
    return dict(sorted(out.items()))


def _unique_net_pairs(problems) -> int:
    """LVS 去重网对数（同一条网对会被多段金属/多个通孔各报一次、双向各报一次）。"""
    return len({frozenset((str(p[1]), str(p[2]))) for p in problems or []})


def _baseline_report(nl, nets_all) -> dict:
    """旧链（`detail_route`）的并排报告 —— 双报一版过渡用，**数字不得删除**。"""
    from lda_l2.ecore import ddef as DD
    from lda_l2.ecore import ddetail, dplac, ddrc_lvs

    p0 = dplac.place(nl)
    r0 = ddetail.detail_route(nl, p0)
    drc0 = ddrc_lvs.run_drc(r0.shapes)
    lvs0 = ddrc_lvs.run_lvs(r0.shapes, r0.net_pins)
    text0 = DD.serialize_def(DD.from_placement(p0, nl, name="lda_c17"))

    return {
        "chain": BASELINE_CHAIN,
        "place": {
            "chain": BASELINE_CHAIN, "cells": len(p0.cell_xywh),
            "die_w_um": round(p0.die_w_um, 3), "die_h_um": round(p0.die_h_um, 3),
            "die_area_um2": round(p0.die_w_um * p0.die_h_um, 3),
            "hpwl_um": round(p0.hpwl_um, 3),
            "cell_area_sum_um2": round(p0.cell_area_sum_um2, 4),
        },
        "route": {
            "chain": BASELINE_CHAIN, "shapes": len(r0.shapes),
            "nets_with_segments": len(r0.net_pins),
            "nets_touched": len(nets_all),
            "routed_segments": r0.n_routed_segments,
        },
        "drc_lvs": {
            "chain": BASELINE_CHAIN,
            "drc_ok": drc0["ok"], "drc_violations": len(drc0["violations"]),
            "drc_by_rule": _count_by_rule(drc0["violations"]),
            "lvs_ok": lvs0["ok"], "lvs_problems": len(lvs0["problems"]),
            "lvs_by_rule": _count_by_rule(lvs0["problems"]),
            "lvs_unique_pairs": _unique_net_pairs(lvs0["problems"]),
        },
        "drc_lvs_detail": {
            "drc": drc0, "lvs": lvs0,
            "by_rule": _count_by_rule(lvs0["problems"]),
            "unique_pairs": _unique_net_pairs(lvs0["problems"]),
            "claimable": False,
        },
        "def_bytes": len(text0),
        "claimable": False,
        "note": "detail_route（旧链）：DRC 87 处 min_spacing ＋ LVS 183 条短路条目"
                "（78 short + 105 short_via，去重 43 对网）—— 连通性错误，不是余量不足；"
                "根因是容量不足，见 ddetail.drc_capacity_bound。",
    }


def run_trunk(nl, *, baseline: bool = True):
    """跑通「parse 输出 → place → route → drc/lvs → DEF」全链，返回带守恒断言的报告。

    每段都断言「吃的是上一段输出」；任一守恒失败 → 抛 AssertionError（fail-closed）。
    `baseline=True` 时并排给出旧链 `detail_route` 的数字（双报一版，防口径静默替换）。
    """
    from lda_l2.ecore import ddef as DD                       # 延迟导入，避免顶层重依赖
    from lda_l2.ecore import ddrc_lvs, dpnr

    report = {"chain": TRUNK_CHAIN, "baseline_chain": BASELINE_CHAIN,
              "stages": [], "conservation_ok": True, "problems": []}

    # ── 段 0：解析输出（Netlist）──────────────────────────────────────
    if nl is None or len(getattr(nl, "gates", ())) == 0:
        raise ValueError("段0：parse 输出为空（无门实例）—— 干线无米下锅")
    nets_all = _distinct_nets(nl)
    report["stages"].append(("parse", {
        "gates": len(nl.gates), "nets": len(nets_all),
        "inputs": len(getattr(nl, "inputs", ())),
        "outputs": len(getattr(nl, "outputs", {})),
    }))

    # ── 段 1：布局（主链 dpnr.place_real，输入 = parse 的 Netlist）───────
    pl = dpnr.place_real(nl)
    picked = len(pl["insts"])
    if picked != len(nl.gates) or (pl.get("skipped_cells") or {}):
        raise AssertionError(
            "段1 守恒失败：place 覆盖 %d 颗门（skipped=%r），但 Netlist 有 %d 颗"
            % (picked, pl.get("skipped_cells"), len(nl.gates)))
    die_w = float(pl["die_w_um"])
    die_h = float(pl["die_h_um"])
    report["stages"].append(("place", {
        "chain": TRUNK_CHAIN, "cells": picked,
        "rows": pl.get("rows"), "cols": pl.get("cols"),
        "die_w_um": round(die_w, 3), "die_h_um": round(die_h, 3),
        "die_area_um2": round(die_w * die_h, 3),
        "cell_gap_um": pl.get("cell_gap_um"),
    }))

    # ── 段 2：布线（主链 dpnr.route_block，输入 = (Netlist, Placement)）───
    rt = dpnr.route_block(nl, pl)
    cov = rt["coverage"]
    ref = dpnr.net_coverage(rt)                    # 🔴 独立复算，不信 route 自述
    if cov != ref:
        raise AssertionError("段2 守恒失败：覆盖记账与独立复算不一致\n  rt=%r\n  ref=%r"
                             % (cov, ref))
    if not cov["complete"] or cov["missing"] or cov["unknown"] or cov["overlap"]:
        raise AssertionError("段2 守恒失败：网覆盖记账不闭合（complete=%s missing=%r "
                             "unknown=%r overlap=%r）"
                             % (cov["complete"], cov["missing"], cov["unknown"],
                                cov["overlap"]))
    if cov["total"] != len(nets_all):
        raise AssertionError("段2 守恒失败：记账总数 %d != 网表网数 %d"
                             % (cov["total"], len(nets_all)))
    shapes = dpnr.all_routing(rt)
    report["stages"].append(("route", {
        "chain": TRUNK_CHAIN, "shapes": len(shapes),
        # 🔴 字段名（v0.9.376）：`nets_with_segments` = 真画了金属的网；
        #    `nets_touched` = 路由过程碰过的网（含端口未布 / 布失败）。
        #    两者不可互换 —— 旧名 `nets` / `routed_nets` 曾并列出现（10 vs 11），读者必误判。
        "nets_with_segments": cov["routed"], "nets_touched": cov["total"],
        "nets_skipped_port": cov["skipped_port"], "nets_failed": cov["failed"],
        "all_routed": cov["all_routed"],
    }))

    # ── 段 3：DRC / LVS（主链，输入 = route 的 shapes + pins）──────────────
    drc = ddrc_lvs.run_drc(shapes)
    lvs = dpnr.lvs_scoped(rt)
    report["stages"].append(("drc_lvs", {
        "chain": TRUNK_CHAIN,
        "drc_ok": drc["ok"], "drc_violations": len(drc["violations"]),
        "drc_by_rule": _count_by_rule(drc["violations"]),
        "lvs_ok": lvs["ok"], "lvs_problems": lvs["n_problems"],
        "lvs_by_rule": lvs["by_rule"],
        # 🔴 作用域必须与结论同行：0 违规只对 nets_checked 成立
        "lvs_scope": lvs["scope"],
        "nets_checked": lvs["nets_checked"], "nets_total": lvs["nets_total"],
    }))

    # ── 段 4：DEF 写出（主链落点 + 段0 的 Netlist）─────────────────────
    #    🔴 只写 placed DEF（落点 + 连接），**不写 ROUTED**：shapes 的网归属虽然已按网打标签
    #       （`dpnr` 每根 wire 都带 net），但 DEF 的 ROUTED 需要完整几何/层/宽度语义，
    #       当前导出面未覆盖 ⇒ 写了就是编造。布线导出须先补 ROUTED 子集写出器（后续里程碑）。
    design = DD.from_placement(pl, nl, name="lda_c17")
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
        "chain": TRUNK_CHAIN,
        "bytes": len(text), "components": len(back.components),
        "nets": len(back.nets), "terms": sum(len(n.terms) for n in back.nets),
        "units": back.units, "roundtrip_ok": True,
        "routed_exported": False,
        "diearea_dbu": list(getattr(back, "diearea", ()) or ()),
    }))

    report["drc_lvs_detail"] = {
        "chain": TRUNK_CHAIN,
        "drc": drc,
        "lvs": {k: v for k, v in lvs.items() if k != "problems"},
        "problems": lvs["problems"],
        "scope": lvs["scope"],
        "nets_checked": lvs["nets_checked"],
        "nets_total": lvs["nets_total"],
        "nets_uncovered": lvs["nets_uncovered"],
        "claimable": False,
        "note": "主链 dpnr：DRC %d / LVS %d，但只覆盖 %d/%d 条网"
                "（%d 条端口网布不了）—— 0 违规**不是**全芯片结论；"
                "旧链 detail_route 的数字见 report['baseline']。"
                % (len(drc["violations"]), lvs["n_problems"],
                   lvs["nets_checked"], lvs["nets_total"],
                   len(lvs["nets_uncovered"])),
    }

    # ── 段 5：baseline（旧链并排双报，防「换了主链，旧证据消失」）──────────
    if baseline:
        b = _baseline_report(nl, nets_all)
        report["baseline"] = b
        base_area = b["place"]["die_area_um2"]
        report["area_delta"] = {
            "main_die_area_um2": round(die_w * die_h, 3),
            "baseline_die_area_um2": base_area,
            "ratio": round((die_w * die_h) / base_area, 3) if base_area else 0.0,
            "reason": "CELL_GAP 换引脚可达性 —— **pin 可达性的面积代价，不是工艺升级**",
        }
    return report


def run_trunk_from_verilog(src: str, **kw) -> dict:
    """从 Verilog 源文本跑干线（先 dverilog.parse 再 run_trunk）。"""
    from lda_l2.ecore.dverilog import parse as parse_verilog
    nl = parse_verilog(src)
    return run_trunk(nl, **kw)


# ═══════════════════════════════════════════════════════════════════════════
# 代表性 ISCAS-85 c17（S3 dverilog.SAMPLE_VERILOG 同款；在此模块内按需导入）
# ═══════════════════════════════════════════════════════════════════════════
def _get_sample_verilog() -> str:
    from lda_l2.ecore.dverilog import SAMPLE_VERILOG
    return SAMPLE_VERILOG


def _fmt_report(rep: dict) -> str:
    lines = ["B3 数字链干线报告（双报一版）", "=" * 48,
             "主链 chain = %s" % rep.get("chain"),
             "对照 chain = %s" % rep.get("baseline_chain")]
    labels = {"parse": "段0 解析(Verilog→Netlist)",
              "place": "段1 布局(place)", "route": "段2 布线(route)",
              "drc_lvs": "段3 DRC/LVS", "def_write": "段4 DEF 写出"}
    for stage, data in rep["stages"]:
        lines.append("%s" % labels.get(stage, stage))
        for k, v in data.items():
            lines.append("    %-20s %s" % (k, v))
    b = rep.get("baseline")
    if b:
        lines.append("")
        lines.append("── baseline（%s，双报一版）──" % b["chain"])
        for sec in ("place", "route", "drc_lvs"):
            for k, v in b[sec].items():
                lines.append("    %-20s %s" % ("%s.%s" % (sec, k), v))
        lines.append("    %-20s %s" % ("def_bytes", b["def_bytes"]))
    a = rep.get("area_delta")
    if a:
        lines.append("")
        lines.append("面积：主链 %.3f µm² / 旧链 %.3f µm² ⇒ ×%.3f" %
                     (a["main_die_area_um2"], a["baseline_die_area_um2"], a["ratio"]))
        lines.append("      " + a["reason"])
    d = rep["drc_lvs_detail"]
    lines.append("")
    lines.append("诚实边界（claimable=False）：")
    lines.append("    " + d["note"])
    return "\n".join(lines)


if __name__ == "__main__":
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
