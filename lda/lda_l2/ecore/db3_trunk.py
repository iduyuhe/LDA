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
  · timing 输入 = 段0 的 Netlist + 段2 的**带网形状**（线长 → 负载 → 延时），
    并断言「加线载不可能变快」；
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


#: 签核资格的**条件清单**（顺序即报告顺序）。
#: 🔴 判据必须写成「**缺一必 False**」，不能写成「全满足才 True」——
#:   后者用默认值就能糊过去（本仓先例：`drc_ok` 曾经的默认 True 写法）。
#: 🔴 这份清单本身也是被检对象：`claimability()` 会报 `condition_list_ok`，
#:   有人删条件 / 漏算时它变 False，门禁据此判红 —— 不靠人眼数条数。
CLAIMABLE_CONDITIONS = (
    "all_nets_routed",        # 每条网都真布了（不是「有归类」）
    "drc_zero",               # DRC 违规 == 0
    "lvs_zero",               # LVS 问题 == 0
    "lvs_scope_full_chip",    # 且这个 0 是**全芯片**口径（子集 0 不算）
    "timing_included",        # 时序段接进来了且排过拓扑序
    "hold_checked",           # 保持时间**真检过**（当前为 False）
)


def claimability(report) -> dict:
    """从**实测数据**推导签核资格（不接收调用方传进来的布尔）。

    🔴 三条纪律：
    ① 六条必须**全部**成立；任一条**缺数据**（`None` / 缺段）都按不成立处理 ——
       「没测」不等于「通过」；
    ② `lvs_zero` 与 `lvs_scope_full_chip` 是**两条独立条件**，虽然逻辑上相关：
       前者防「有问题」，后者防「0 违规只是子集口径」（本仓审计抓到的头号失真）；
    ③ `condition_list_ok` 必须为 True —— 条件被删/漏算时它立即可见。
    """
    st = {name: payload for name, payload in (report.get("stages") or [])}
    rt = st.get("route") or {}
    dl = st.get("drc_lvs") or {}
    tm = st.get("timing") or {}

    measured = {
        "all_nets_routed": rt.get("all_routed"),
        "drc_zero": dl.get("drc_violations"),
        "lvs_zero": dl.get("lvs_problems"),
        "lvs_scope_full_chip": dl.get("lvs_scope"),
        "timing_included": (True if tm.get("topo_sorted") is True
                            else (None if not tm else False)),
        "hold_checked": tm.get("hold_checked"),
    }
    conds = {
        "all_nets_routed": measured["all_nets_routed"] is True,
        "drc_zero": measured["drc_zero"] == 0,
        "lvs_zero": measured["lvs_zero"] == 0,
        "lvs_scope_full_chip": measured["lvs_scope_full_chip"] == "FULL_CHIP",
        "timing_included": measured["timing_included"] is True,
        "hold_checked": measured["hold_checked"] is True,
    }
    blocking = [k for k in CLAIMABLE_CONDITIONS if not conds[k]]
    return {
        "claimable": all(conds[k] for k in CLAIMABLE_CONDITIONS),
        "conditions": conds,
        "blocking": blocking,
        "measured": {k: measured[k] for k in CLAIMABLE_CONDITIONS},
        "n_conditions": len(conds),
        "condition_list_ok": set(conds) == set(CLAIMABLE_CONDITIONS),
        "rule": "六条全成立才 True；任一条缺数据（None）按不成立处理",
    }


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
        # 与主链**同一个函数**派生（不写第二套判据）：
        # 旧链没有时序段、且 DRC 非零 ⇒ 必然不可 claim
        "claimability": claimability({"stages": [
            ("route", {"all_routed": len(r0.net_pins) == len(nets_all)}),
            ("drc_lvs", {"drc_violations": len(drc0["violations"]),
                         "lvs_problems": len(lvs0["problems"]),
                         "lvs_scope": "FULL_CHIP"}),
        ]}),
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
    # 🔴 **pad 落点默认启用**（v0.9.382 · A 改拓扑第一段）：端口网从「无端点」变成可布，
    #    且 pad 引出改走 **M2 竖直**（不占 M4 列）后，c17 布通 **4 → 7**、DRC 0。
    #    `pl_p` 是单元整体右移后的布局（带两侧 pad 带）；面积代价在此如实计入。
    ports = dpnr.build_ports(nl, pl)
    pl_p = ports["pl"]
    die_w = float(pl_p["die_w_um"])
    die_h = float(pl_p["die_h_um"])
    report["stages"].append(("place", {
        "chain": TRUNK_CHAIN, "cells": picked,
        "rows": pl.get("rows"), "cols": pl.get("cols"),
        "die_w_um": round(die_w, 3), "die_h_um": round(die_h, 3),
        "die_area_um2": round(die_w * die_h, 3),
        "cell_gap_um": pl.get("cell_gap_um"),
        # 🔴 面积代价必须**两侧都给**：无 pad 时 die 多大 vs 现在多大。
        "die_w_um_noport": round(float(pl["die_w_um"]), 3),
        "die_area_um2_noport": round(float(pl["die_w_um"]) * float(pl["die_h_um"]), 3),
        "ports": {"n_pads": ports["n_pads"], "n_in": ports["n_in"],
                  "n_out": ports["n_out"], "band_um": round(ports["band_um"], 3),
                  # 🔴 v0.9.383：左右带分别报 + 网格对齐余量 —— 三者与无 pad 的 die 宽
                  #    必须能**逐位复算**出 die_w（S11d 机核），否则「面积为什么这样」无法核。
                  "band_left_um": round(ports["band_left_um"], 3),
                  "band_right_um": round(ports["band_right_um"], 3),
                  "grid_align_um": round(ports["grid_align_um"], 3),
                  "extra_cols": ports["extra_cols"],
                  "model": "示意级 I/O 落点（240nm pad · 无 ESD/电源/ring 层次）"},
    }))

    # ── 段 2：布线（主链 dpnr.route_block，输入 = (Netlist, Placement)）───
    rt = dpnr.route_block(nl, pl_p, ports=ports)
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
        # 🔴 单端点网必须**再分两类**（v0.9.379）：`nets_skipped_port` 是**旧义**= 单端点全集，
        #    其中只有 `nets_skipped_true_port` 条接 primary I/O（补端口模型可望布通），
        #    `nets_dangling` 条是**悬空网**（c17 的 `n10`：网表里 `g22` 第二输入写成 `n16`），
        #    它补端口也布不通、只能改网表。混成一类会让读者把工作量估小。
        "nets_skipped_port": cov["skipped_port"],
        "nets_skipped_true_port": cov["skipped_true_port"],
        "nets_dangling": cov["skipped_dangling"],
        "nets_failed": cov["failed"],
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

    # ── 段 4：时序（输入 = 段0 Netlist + 段2 布线的**带网形状**）──────────
    #   🔴 两个「不做就错」的前置：
    #   ① `dsta.sta` 原先按 `nl.gates` **书写顺序**传播 —— 源文件顺序不保证拓扑序
    #      （c17 就不是），必须 `topo_sort=True`，否则用旧到达时间静默算错；
    #   ② 网名以 `nl.in_nets` 为准（`dverilog` 的网名是 `n1`，不是 `in_n1_0`）。
    from lda_l2.ecore import dextract as DE, dsta as ST

    lengths = DE.net_length_um(shapes)
    wl = DE.wire_loads_from_shapes(shapes)      # 与 `dextract` 同一公式，不另写一份
    tm_ideal = ST.sta(nl, topo_sort=True)
    tm = ST.sta(nl, wire_load_ff=wl, topo_sort=True)
    if tm.comb_delay_ps < tm_ideal.comb_delay_ps - 1e-9:
        raise AssertionError("段4 守恒失败：带线载延时 %.4f < 理想 %.4f —— "
                             "加负载不可能变快（模型或注入路径写反了）"
                             % (tm.comb_delay_ps, tm_ideal.comb_delay_ps))
    report["stages"].append(("timing", {
        "chain": TRUNK_CHAIN, "topo_sorted": True,
        "nets_with_wire": len(wl),
        # 🔴 未布的网按 **0 线载** 处理 ⇒ 走这些网的路径**偏乐观**（必须显式说）
        "nets_without_wire": len(nets_all) - len(wl),
        "total_wire_um": round(sum(lengths.values()), 3),
        "total_wire_c_fF": round(sum(wl.values()), 3),
        "comb_delay_ideal_ps": round(tm_ideal.comb_delay_ps, 3),
        "comb_delay_wired_ps": round(tm.comb_delay_ps, 3),
        # 三态而非压扁：无时钟域 ⇒ None（不是 0，也不是「无违规」）
        "t_clk_min_ps": (None if tm.t_clk_min_ps is None else round(tm.t_clk_min_ps, 3)),
        "fmax_mhz": (None if tm.fmax_mhz is None else round(tm.fmax_mhz, 3)),
        "n_dff": tm.n_dff,
        "clock_domains": (0 if tm.t_clk_min_ps is None else 1),
        "hold_checked": bool(tm.hold_checked),
        "critical_path": list(tm.critical_path),
    }))

    # ── 段 4b：EM 逐网裕量（**诊断段** · v0.9.387 · B2b）────────────────
    #   🔴 三个「不做就错」的前置：
    #   ① c17 是**纯组合**电路 ⇒ `dsta` 给不出 `fmax`（无时钟域）⇒ EM 必须有频率输入，
    #      只能由组合关键路径延时反推，且**「f 是假设」必须进输出**（默认半周期，保守）；
    #   ② 电流里的 C 必须是**该网总负载**（线载 + 扇出栅电容），只算线载会低估 1.5~2.7×
    #      （c17 实测 C_wire 1.2 fF vs C_tot 3.2 fF）；
    #   ③ 无金属的网**不可判**（不是通过）⇒ `scope` 与 `undecidable_nets` 必须与结论同行。
    #   🔴 本段 `in_blocking=False`：只给带量纲的裕量，**不改变 `claimable`/`m1_exit`**。
    from lda_l2.ecore import dcell as DCell, dsignoff as DSG

    em_rep = DSG.em_net_signoff(
        lengths, wl, ST.loads_of(nl, wire_load_ff=wl), nets_all,
        f_hz=DSG.f_from_comb_delay(tm.comb_delay_ps, half_period=True),
        vdd=float(DCell.DEFAULT_TECH.vdd), width_um=float(dpnr.W))
    report["stages"].append(("em", dict(em_rep, chain=TRUNK_CHAIN)))

    # ── 段 4c：几何 / 量纲诊断（EC-B3.1 · 诊断段，不进 blocking）──────────
    #   🔴 四个分母口径全部由**网表 / 几何复算**（不手填独立常量）：
    #      g_area = nl.area_um2()；g_per_gate / g_per_transistor 按门/管均分；
    #      g_cell = 单元外框 w*h。全片统一、写进段内 assumptions。
    #   🔴 只报谱与不变式，**不判违规、不进 blocking** ⇒
    #      claimable / m1_exit / 对外主链数字一律不变。
    _g_b3 = {
        "g_area": float(nl.area_um2()),
        "g_per_gate": float(nl.area_um2()) / float(nl.n_gates()),
        "g_per_transistor": float(nl.area_um2()) / float(nl.n_transistors()),
        "g_cell": float(pl_p["insts"][0]["w"]) * float(pl_p["insts"][0]["h"]),
    }
    b3_rep = DSG.ec_b3_signoff(
        shapes, die_w_um=die_w, die_h_um=die_h,
        width_um=float(dpnr.W), g_values=_g_b3)
    report["stages"].append(("ec_b3", dict(b3_rep, chain=TRUNK_CHAIN)))

    # ── 段 4d：稳态热链诊断（EC-B4.1 · 诊断段，**不回灌 t_c**）────────────
    #   🔴 与段 4b EM **同源**：f 由 tm.comb_delay_ps 反推半周期；alpha 用 DSG.ALPHA_DYN；
    #      vdd 用 tech 默认。功率口径与 `dsta.switching_power_nw` 同源（门输出负载，不含线载）
    #      ⇒ 逐门之和逐位守恒（EC-B4.0 构造规格）。
    #   🔴 节点顺序 = pl_p["insts"]（确定性）；单元面积 = w*h。
    #   🔴 **不传 t_c 给 em_net_signoff**：EM 仍用 T_REF_C=125°C 假设；
    #      本段只是诊断谱，不进 blocking、不改任何既有对外数字。
    _f_b4 = DSG.f_from_comb_delay(tm.comb_delay_ps, half_period=True)
    _v_b4 = float(DCell.DEFAULT_TECH.vdd)
    _pw_b4 = DSG.b4_cell_power_w(nl, ST.loads_of(nl), _f_b4, DSG.ALPHA_DYN, _v_b4)
    _cells_b4 = [
        {"name": i["name"], "p_w": _pw_b4.get(i["name"], 0.0),
         "area_um2": float(i["w"]) * float(i["h"])}
        for i in pl_p["insts"]
    ]
    th_rep = DSG.b4_thermal_signoff(
        _cells_b4, assumptions={
            "alpha": DSG.ALPHA_DYN, "f_hz": _f_b4, "vdd": _v_b4,
            "t_comb_ps": float(tm.comb_delay_ps),
            "f_basis": "half-period inverse of comb delay (c17 pure combinational)",
            "wire_load_in_power": False,
        })
    report["stages"].append(("thermal", dict(th_rep, chain=TRUNK_CHAIN)))

    # ── 段 5：DEF 写出（主链落点 + 段0 的 Netlist）─────────────────────
    #    🔴 只写 placed DEF（落点 + 连接），**不写 ROUTED**：shapes 的网归属虽然已按网打标签
    #       （`dpnr` 每根 wire 都带 net），但 DEF 的 ROUTED 需要完整几何/层/宽度语义，
    #       当前导出面未覆盖 ⇒ 写了就是编造。布线导出须先补 ROUTED 子集写出器（后续里程碑）。
    design = DD.from_placement(pl_p, nl, name="lda_c17")
    text = DD.serialize_def(design)
    back = DD.parse_def(text)
    if DD.serialize_def(back) != text:                 # 写出→读回→再写出 必须字节一致
        raise AssertionError("段5 守恒失败：DEF 往返不是字节级双射")
    if len(back.components) != len(nl.gates):
        raise AssertionError("段5 守恒失败：DEF 组件 %d != 门数 %d"
                             % (len(back.components), len(nl.gates)))
    if len(back.nets) != len(nets_all):
        raise AssertionError("段5 守恒失败：DEF 网 %d != Netlist 网 %d"
                             % (len(back.nets), len(nets_all)))
    _got = {c.name: (c.macro, c.x, c.y) for c in back.components}
    for c in design.components:
        if _got.get(c.name) != (c.macro, c.x, c.y):
            raise AssertionError("段5 守恒失败：组件 %s 的宏名/落点在往返后变了" % c.name)
    report["stages"].append(("def_write", {
        "chain": TRUNK_CHAIN,
        "bytes": len(text), "components": len(back.components),
        "nets": len(back.nets), "terms": sum(len(n.terms) for n in back.nets),
        "units": back.units, "roundtrip_ok": True,
        "routed_exported": False,
        "diearea_dbu": list(getattr(back, "diearea", ()) or ()),
    }))

    # ── M1 阶段出口判据（v0.9.381 改口径）──────────────────────────────────
    #   🔴 **这不是放松要求**：旧判据「c17 全芯片 DRC/LVS 干净」在现有拓扑下**不可达**
    #      （6 条端口网无 pad 模型 + 1 条悬空网），要求它等于**逼人把子集结论写成
    #      全芯片结论** —— 那才是本项目头号失真。新判据把「不可达」换成
    #      「**每条未布网必须逐条枚举归因**」：归因不出来就判红。
    #   🔴 与 `claimability` 是两件事：本判据达成 = 阶段数字可信，**不等于可签核**。
    report["stages"].append(("m1_exit", dpnr.m1_exit_assessment(rt, drc, lvs)))

    report["drc_lvs_detail"] = {
        "chain": TRUNK_CHAIN,
        "drc": drc,
        "lvs": {k: v for k, v in lvs.items() if k != "problems"},
        "problems": lvs["problems"],
        "scope": lvs["scope"],
        "nets_checked": lvs["nets_checked"],
        "nets_total": lvs["nets_total"],
        "nets_uncovered": lvs["nets_uncovered"],
        # 🔴 由 `claimability()` 派生（v0.9.378），不再是常量 False
        "claimable": None,
        "note": "主链 dpnr：DRC %d / LVS %d，但只覆盖 %d/%d 条网"
                "（%d 条端口网布不了）—— 0 违规**不是**全芯片结论；"
                "旧链 detail_route 的数字见 report['baseline']。"
                % (len(drc["violations"]), lvs["n_problems"],
                   lvs["nets_checked"], lvs["nets_total"],
                   len(lvs["nets_uncovered"])),
    }

    # ── 签核资格：由**实测数据**派生（六条条件，缺一必 False）──────────────
    #   🔴 放在这里而不是每处写 `claimable=False`：常量 False 会让
    #      「缺一必 False」的探针**全部平凡通过**（恒假当然每条都 False）。
    report["claimability"] = claimability(report)
    report["drc_lvs_detail"]["claimable"] = report["claimability"]["claimable"]

    # ── 段 5：baseline（旧链并排双报，防「换了主链，旧证据消失」）──────────
    if baseline:
        b = _baseline_report(nl, nets_all)
        b["claimable"] = b["claimability"]["claimable"]
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
              "drc_lvs": "段3 DRC/LVS", "timing": "段4 时序(dsta + dextract 线载)",
              "def_write": "段5 DEF 写出"}
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
    _cl = rep.get("claimability") or {}
    lines.append("签核资格：claimable=%s（阻塞项 %s）"
                 % (_cl.get("claimable"), ", ".join(_cl.get("blocking") or []) or "无"))
    lines.append("诚实边界（claimable=False 的原因见上）：")
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
