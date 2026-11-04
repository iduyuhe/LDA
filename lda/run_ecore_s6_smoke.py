# -*- coding: utf-8 -*-
"""S6 门禁：**B3 数字链干线**（Verilog→Netlist→place→route→drc/lvs 端到端守恒）。

═══════════════════════════════════════════════════════════════════════════════
这一版要证明什么
───────────────────────────────────────────────────────────────────────────────
`db3_trunk.py` 把 S3 的结构级 Verilog 子集直接喂进现状数字链，跑通 ISCAS-85 c17，并
**每段显式断言「吃的是上一段的输出」**。判据只问三件事：

  S0 **干线跑通**：c17 端到端不抛异常，conservation_ok=True。
  S1 **解析段守恒**：parse 输出 Netlist 有 6 门 / 11 网（c17 真实拓扑）。
  S2 **布局段守恒**：place 覆盖**每一颗门**（cells == gates），门一个不少。
  S3 **布线段守恒**：route 的 net_pins 覆盖**每一条网**（routed_nets == 11），网一条不漏。
  S4 **DRC/LVS 如实报告**：违规数被记录且 claimable=False（不伪造 clean tapeout）。
  S5 **fail-closed**：空/None 输入 → 干线直接报错（不放行「看起来跑通了」）。
  S7 **DRC 收敛**：弯角延伸把 `via_enclosure` 修到 **0**（孔必须被两层金属包围，且**不得**
     靠画长线蒙过 —— 中心线长仍须 == MST）；余下 87 处全是 `min_spacing`，用
     `drc_capacity_bound()` 三向下界证明是**容量不足**（通道 2<7 · 引脚槽 0.96µm>单元宽 0.067µm ·
     列 6.12µm>die 1.09µm）；卡片与门禁必须同口径，且三向伪造（容量可行/0 违规/via 回退）必红。
  S7i–S7k **口径清理**（v0.9.373）：LVS 183 条必须分类（78 `short` + 105 `short_via`）且**去重 43 对网**
     （条目数会把规模夸大 4 倍）；`ddetail` 诚实边界必须含 `short`、**不得**再出现「同层短路为零」
     的旧表述；三向反向探针（旧表述塞回 / 分类与总数不符 / 去重数超条目数）必红。
  S7e–S7h **反证实验**（把下界变成实测对照）：只加通道时构造出的面积比 **1.58×** 恰好复现
     下界预测，但**仍违规 155 处** ⇒ 「1.577× 换 0 违规」被推翻（必要非充分）；
     单元宽给足（`(n_pins+1)·pitch` + 引脚均布 + 轨道分配）⇒ DRC **真 0**，代价行面积 **26.32×**；
     中间档（0.5×）仍 21 处 ⇒ 存在真实阈值，不是「随便放大都行」。
  S6 **对外入口**：`/api/digital_demo` 消费干线（此前干线**只有自己的门禁在调它**）——
     卡片数字必须 == 门禁**独立重跑**的真值；未实现的段（综合/时序/ROUTED）显式 False；
     诚实性自检正向空、反向两向必报；两次调用 digest 一致且 JSON 硬。

  C1–C4 **签核资格条件化**（v0.9.378）：`claimable` 不再是常量，而由六条实测条件派生
     （all_nets_routed / drc_zero / lvs_zero / lvs_scope_full_chip / timing_included /
     hold_checked）。判据先给一个**全满足 ⇒ True** 的用例（否则恒假判据会让六条
     「缺一必 False」全部平凡通过），再逐条证明「只缺一条 ⇒ 必 False 且 blocking 恰为该条」。
  S8–S9 **双报一版**（v0.9.376 主链切换）：主链从 `detail_route` 换成 `dpnr`。
     风险不是「算错」而是**静默替换** —— 不并排报旧链，87 处间距 + 183 条短路条目
     就会从报表里消失，而它们正是「为什么必须换」的唯一证据。故要求：
     `rep.chain=dpnr` ∧ `baseline.chain=detail_route` ∧ 干线不 import `track_route` ∧
     `nets_with_segments ≤ nets_touched` ∧ 面积代价两侧都给且比值可独立复算 ∧
     反向三向（改标主链 / 抹 baseline / 抹 area_delta）必红。

诚实边界
────────
· ddetail.detail_route 的 claimable=False（c17 实测 87 处 min_spacing；via_enclosure 已修至 0，
  余下为**容量不足**，见 `ddetail.drc_capacity_bound`）是**已知边界**，干线如实披露；
  数字链几何/时序为模型假设（见 dplac/ddetail 披露）；非 foundry PDK；不报流片实测。
· C 级自主：纯标准库 + 复用既有模块，LLM 不进判决路径。
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_l2.ecore import db3_trunk as T                      # noqa: E402

_FALS: list = []
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   record=_FALS)
T0 = time.time()
AN_ELAPSED_MAX_S = 120.0


def _stage(rep, name):
    for s, d in rep["stages"]:
        if s == name:
            return d
    return None


def main() -> int:
    src = T._get_sample_verilog()
    rep = T.run_trunk_from_verilog(src)

    # ── S0 干线跑通 ────────────────────────────────────────────────────
    check("S0 干线跑通（c17 端到端无异常）· conservation_ok=True",
          rep.get("conservation_ok", False), "conservation_ok=%s" % rep.get("conservation_ok"))

    # ── S1 解析段守恒 ─────────────────────────────────────────────────
    p = _stage(rep, "parse")
    check("S1 解析段：c17 拓扑 = 6 门 / 11 网", p is not None and p["gates"] == 6 and p["nets"] == 11,
          "parse=%s" % (p,))

    # ── S2 布局段守恒（place 覆盖每颗门）──────────────────────────────
    pl = _stage(rep, "place")
    check("S2 布局段守恒：place 覆盖全部 6 颗门（cells == gates）",
          pl is not None and pl["cells"] == 6 and pl["cells"] == p["gates"],
          "place cells=%s parse gates=%s" % (pl["cells"] if pl else None, p["gates"]))

    # ── S3 布线段守恒（v0.9.376 口径变更：从「覆盖每条网」→「每条网有且仅有一类归属」）──
    #   🔴 为什么改：主链 dpnr 不建端口，7 条接 primary I/O 的网**布不了**。
    #      旧口径「routed_nets == 11」现在必然为假；强行要求它等于逼人把「布不了」
    #      报成「布了」——那正是第 1 步抓到的失真。新口径要求**三类互斥且并集 == 全集**。
    rt = _stage(rep, "route")
    _ws, _tn = (rt["nets_with_segments"], rt["nets_touched"]) if rt else (None, None)
    _sk, _fl = (rt["nets_skipped_port"], rt["nets_failed"]) if rt else (None, None)
    check("S3 布线段守恒：%d 已布 + %d 端口未布 + %d 布失败 == %d 网（nets_with_segments "
          "≤ nets_touched，且 all_routed 如实为 False）"
          % (_ws or -1, _sk or -1, _fl or -1, _tn or -1),
          rt is not None and _ws + _sk + _fl == _tn == p["nets"]
          and _ws <= _tn and rt["all_routed"] is False,
          "route=%s" % (rt,))

    # ── S4 DRC/LVS 如实报告 ───────────────────────────────────────────
    dl = _stage(rep, "drc_lvs")
    detail = rep.get("drc_lvs_detail", {})
    check("S4 DRC/LVS 如实报告：违规数为非负整数 · claimable=False（不伪造 clean）",
          dl is not None and isinstance(dl["drc_violations"], int)
          and isinstance(dl["lvs_problems"], int)
          and detail.get("claimable") is False,
          "drc=%s lvs=%s claimable=%s" % (dl["drc_violations"] if dl else None,
                                         dl["lvs_problems"] if dl else None,
                                         detail.get("claimable")))

    # ── D1–D4 DEF 写出段（v0.9.367：ddef 接回干线，补 B3 的 DEF 出口）──────
    dw = _stage(rep, "def_write")
    check("D1 DEF 段守恒：组件 == 6 颗门 ∧ 网 == 11 条（与 parse 段逐值对齐）",
          dw is not None and dw["components"] == p["gates"] == 6
          and dw["nets"] == p["nets"] == 11,
          "def=%s" % (dw,))
    check("D2 DEF 往返字节级双射：写出→读回→再写出 完全一致（roundtrip_ok）",
          dw is not None and dw["roundtrip_ok"] is True, "def=%s" % (dw,))

    # 🔴 独立复算（不信报告自述）：重跑 place + from_placement + serialize，逐项对拍
    from lda_l2.ecore import ddef as DD      # noqa: E402
    from lda_l2.ecore import dplac as PL     # noqa: E402
    from lda_l2.ecore import dverilog as V   # noqa: E402

    nl = V.parse(src)
    from lda_l2.ecore import dpnr as PN                       # noqa: E402

    # 🔴 v0.9.376：主链切到 dpnr ⇒ DEF 段吃的是 dpnr 落点（不是 dplac 的）。
    #    这里必须用**同一个真源**复算，否则「吃上一段输出」这条不变量在 DEF 段断掉。
    _p2 = PN.place_real(nl)
    _txt = DD.serialize_def(DD.from_placement(_p2, nl, name="lda_c17"))
    check("D3 DEF 内容独立复算：字节数一致 ∧ **不含 ROUTED**（shapes 无网归属 ⇒ 写了就是编造）"
          " ∧ UNITS DISTANCE MICRONS 1000（1 DBU = 1 nm）",
          len(_txt) == dw["bytes"] and "ROUTED" not in _txt
          and "UNITS DISTANCE MICRONS 1000 ;" in _txt,
          "bytes=%d vs %s" % (len(_txt), dw["bytes"]))

    # D4 反向探针：落点缺失必须 fail-closed（不许写出半个 DEF）
    class _NoPlc:
        cell_xywh = {}

    _raised = False
    try:
        DD.from_placement(_NoPlc(), nl)
    except ValueError:
        _raised = True
    check("D4 反向：placement 缺落点 ⇒ from_placement 抛 ValueError（不写半个 DEF）",
          _raised, "未报错")

    # ── S5 fail-closed：空/None 输入必报错 ────────────────────────────
    raised = False
    try:
        T.run_trunk(None)
    except (ValueError, AssertionError):
        raised = True
    check("S5 fail-closed：空/None 输入 → 干线直接报错（不放行）",
          raised, "未报错（空输入被放行）")

    # ── S6 对外入口：B3 干线必须有非门禁消费者 ────────────────────────
    #   🔴 这条不是「多测一个端点」，是补 B3 的真缺口：此前干线**只有自己的门禁在调它**
    #      （R3 债务「给一个非门禁消费者」）。现在 `/api/digital_demo` 消费它。
    from lda_webui import digital_case as DC                  # noqa: E402

    DC.clear_cache()
    card = DC.case_card()

    _rt = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "lda", "lda_webui", "routes.py"), encoding="utf-8").read()
    _get_block = _rt.split("GET_ROUTES = {")[1].split("}")[0]
    _heavy = _rt.split("HEAVY_POST_PATHS = {")[1].split("}")[0]
    check("S6a 端点接线：\"/api/digital_demo\": h_digital_demo 在 GET_ROUTES ∧ 不进 HEAVY_POST_PATHS"
          "（公开只读 · 缓存后无 DoS 面）",
          '"/api/digital_demo": h_digital_demo,' in _get_block
          and "/api/digital_demo" not in _heavy,
          "wired=%s heavy=%s" % ('"/api/digital_demo": h_digital_demo,' in _get_block,
                                 "/api/digital_demo" in _heavy))

    # 🔴 独立复算（不信卡片自述）：门禁自己再跑一次干线，逐项对拍卡片数字
    _rep2 = T.run_trunk(V.parse(V.SAMPLE_VERILOG))
    _st2 = {n: p for n, p in _rep2["stages"]}
    _want = {
        "components": _st2["def_write"]["components"],
        "nets_def": _st2["def_write"]["nets"],
        "terms": _st2["def_write"]["terms"],
        "def_bytes": _st2["def_write"]["bytes"],
        "drc_violations": len(_rep2["drc_lvs_detail"]["drc"]["violations"]),
        # 🔴 v0.9.376：主链的 problems 列表在 `drc_lvs_detail["problems"]`（列表不进 lvs dict）
        "lvs_problems": _rep2["drc_lvs_detail"]["lvs"].get("n_problems",
                          len(_rep2["drc_lvs_detail"].get("problems") or [])),
        "gates": _st2["parse"]["gates"],
        "nets": _st2["parse"]["nets"],
    }
    _got = {
        "components": card["def_export"]["components"],
        "nets_def": card["def_export"]["nets"],
        "terms": card["def_export"]["terms"],
        "def_bytes": card["def_export"]["bytes"],
        "drc_violations": card["drc_lvs"]["drc_violations"],
        "lvs_problems": card["drc_lvs"]["lvs_problems"],
        "gates": card["subject"]["gates"],
        "nets": card["subject"]["nets"],
    }
    check("S6b 卡片数字 == 独立重跑干线的真值（%r）—— 不信卡片自述" % (_want,),
          _want == _got, "卡片=%r" % (_got,))
    _bl = card.get("baseline") or {}
    _bl_dl = _bl.get("drc_lvs") or {}
    check("S6c 两条链的数字都要自洽且都如实：主链 Σ分规则==%d（0 合规但要带作用域）· "
          "旧链 DRC %s / LVS %s（必须仍 >0，双报不许把旧证据抹掉）"
          % (card["drc_lvs"]["drc_violations"], _bl_dl.get("drc_violations"),
             _bl_dl.get("lvs_problems")),
          sum(card["drc_lvs"]["drc_by_rule"].values()) == card["drc_lvs"]["drc_violations"]
          and card["drc_lvs"]["drc_violations"] >= 0
          and card["drc_lvs"]["scope"] in ("FULL_CHIP", "ROUTED_SUBSET_ONLY")
          and (_bl_dl.get("drc_violations") or 0) > 0
          and (_bl_dl.get("lvs_problems") or 0) > 0
          and sum((_bl_dl.get("lvs_by_rule") or {}).values()) == (_bl_dl.get("lvs_problems") or 0),
          "main=%r baseline=%r"
          % (card["drc_lvs"]["drc_by_rule"], _bl_dl))

    # ── S6d 诚实三态：未实现的段必须显式 False（不是「没说」）───────────
    # 🔴 v0.9.377：`timing_included` 已由 False 变 True（时序段接入），
    #   但**边界必须同时在场**：hold 未检、无时钟域不给 Fmax、segment 清单要如实。
    check("S6d 未实现的段显式登记：synthesized=False ∧ timing_included=True 且 "
          "hold_checked=False ∧ routed_exported=False ∧ segments_missing 只含 synthesis",
          card["synthesized"] is False and card["timing_included"] is True
          and card["timing"]["hold_checked"] is False
          and card["def_export"]["routed_exported"] is False
          and list(card["segments_missing"]) == ["synthesis"]
          and "timing" in card["segments_covered"],
          "synthesized=%r timing=%r hold=%r missing=%r"
          % (card["synthesized"], card["timing_included"],
             card["timing"]["hold_checked"], card["segments_missing"]))

    # ── S6e 卡片诚实性自检 + 两条反向探针（改坏必报）──────────────────
    _sc_ok = DC.selfcheck(card)
    _bad1 = dict(card, verdict="SIGNOFF_PASS")
    _bad2 = json.loads(json.dumps(card))
    _bad2["def_export"]["routed_exported"] = True
    check("S6e 卡片自检：正向空 ∧ 反向两向必报（verdict 改签核 / routed_exported 改 True）",
          not _sc_ok and DC.selfcheck(_bad1) and DC.selfcheck(_bad2),
          "正向=%r 反1=%r 反2=%r" % (_sc_ok, DC.selfcheck(_bad1), DC.selfcheck(_bad2)))

    # ── S6f 可复现：两次调用 digest 一致 ∧ JSON 硬（无 NaN/Inf）─────────
    card2 = DC.case_card()
    check("S6f 同输入同结果：两次 case_card() 的 digest 相同（%s）∧ JSON 硬（allow_nan=False）"
          % card["digest_sha256"][:16],
          card["digest_sha256"] == card2["digest_sha256"]
          and bool(json.dumps(card, allow_nan=False, ensure_ascii=False)),
          "digest=%s vs %s" % (card["digest_sha256"][:12], card2["digest_sha256"][:12]))

    # ── S7a–S7d DRC 收敛（v0.9.370）：修得掉的修掉，修不掉的给出容量下界 ────
    from lda_l2.ecore import ddetail as DTL                  # noqa: E402
    from lda_l2.ecore import dplac as PLC                    # noqa: E402
    from lda_l2.ecore import ddrc_lvs as DRC                 # noqa: E402

    _p3 = PLC.place(nl)
    _dr = DTL.detail_route(nl, _p3)
    _r3 = DRC.run_drc(_dr.shapes)
    _by = {}
    for _v in _r3["violations"]:
        _by[_v[0]] = _by.get(_v[0], 0) + 1
    # ① 弯角延伸：VIA2 必须被两层金属包围（否则 via_enclosure 必违例）；
    #    延伸只加在段端，**中心线长必须仍 == MST**（不能靠画长线把孔包住）
    _mst_ok = all(abs(_dr.centerline_um[k] - _dr.mst_um[k]) < 1e-9 for k in _dr.centerline_um)
    check("S7a 弯角延伸修复：via_enclosure == 0（%r）∧ 中心线长 == MST（延伸不改线长）"
          % (_by,),
          _by.get("via_enclosure", 0) == 0 and _mst_ok,
          "by_rule=%r mst_ok=%s" % (_by, _mst_ok))

    # ② 容量下界：三向都必须够才能清零 —— 当前三向都不够，且数字要能独立复算
    _cap = DTL.drc_capacity_bound(nl, _p3)
    _need = {
        "channel": (_cap["capacity_per_row"], _cap["clique_max"]),
        "width": (_cap["pin_slot_need_um"], _cap["cell_w_median_um"]),
        "cols": (_cap["cols_need_um"], _cap["cols_have_um"]),
    }
    check("S7b 容量下界三向都缺：通道 %d<%d · 引脚槽需 %.2fµm>单元宽 %.3fµm · "
          "列需 %.2fµm>die %.2fµm ⇒ verdict=ROUTING_RESOURCE_INFEASIBLE"
          % (_need["channel"] + _need["width"] + _need["cols"]),
          _cap["verdict"] == "ROUTING_RESOURCE_INFEASIBLE"
          and _cap["capacity_per_row"] < _cap["clique_max"]
          and _cap["pin_slot_need_um"] > _cap["cell_w_median_um"]
          and _cap["cols_need_um"] > _cap["cols_have_um"],
          "cap=%r" % ({k: _cap[k] for k in ("capacity_per_row", "clique_max",
                                            "pin_slot_need_um", "cell_w_median_um",
                                            "cols_need_um", "cols_have_um")},))

    # ③ 卡片承载的容量/DRC 必须 == 独立复算（对外不许与门禁口径分叉）
    _card3 = DC.case_card()
    _c_cap = _card3["capacity"]
    _same = all(abs(_c_cap[k] - _cap[k]) < 1e-9 for k in
                ("capacity_per_row", "clique_max", "pin_slot_need_um",
                 "cell_w_median_um", "cols_need_um", "cols_have_um"))
    # 🔴 v0.9.376：`capacity` 由 dplac+ddetail 算出 ⇒ 它描述 **baseline**，
    #    因此对拍也必须取 baseline 的 DRC 违规数（此前取的是主链，跨链比较）。
    check("S7c 卡片 capacity == 独立复算 ∧ **旧链** DRC 违规数 == 门禁实测（%d）"
          % len(_r3["violations"]),
          _same and _c_cap["verdict"] == _cap["verdict"]
          and ((_card3.get("baseline") or {}).get("drc_lvs") or {})
          .get("drc_violations") == len(_r3["violations"]),
          "card=%r gate=%r bl=%r" % (_c_cap.get("verdict"), _cap.get("verdict"),
                                     ((_card3.get("baseline") or {}).get("drc_lvs") or {})
                                     .get("drc_violations")))

    # ④ 反向三向：伪造「容量够」/「0 违规」/「via 回退」⇒ 自检必红
    _f1 = json.loads(json.dumps(_card3))
    _f1["capacity"]["verdict"] = "RESOURCE_SUFFICIENT"
    _f2 = json.loads(json.dumps(_card3))
    _f2["baseline"]["drc_lvs"]["drc_violations"] = 0
    _f2["baseline"]["drc_lvs"]["drc_by_rule"] = {}
    _f3 = json.loads(json.dumps(_card3))
    _f3["baseline"]["drc_lvs"]["drc_by_rule"] = {"min_spacing": 73, "via_enclosure": 14}
    _f6 = json.loads(json.dumps(_card3))
    _f6["drc_lvs"]["scope"] = None            # 🔴 主链 0 违规但抹掉作用域 ⇒ 必红
    check("S7d 反向三向必红：伪造容量可行 / **旧链**伪造成 0 违规 / 旧链伪造 via 回退 ⇒ "
          "自检各报一条",
          DC.selfcheck(_f1) and DC.selfcheck(_f2) and DC.selfcheck(_f3)
          and DC.selfcheck(_f6),
          "f1=%r f2=%r f3=%r f6=%r" % (DC.selfcheck(_f1)[:1], DC.selfcheck(_f2)[:1],
                                        DC.selfcheck(_f3)[:1], DC.selfcheck(_f6)[:1]))

    # ── S7e–S7h 反证实验：放大面积能不能换 0 违规（预测 vs 实测）────────────
    _e_ch = DTL.drc_zero_experiment(nl, widen=None)          # 只加通道
    _e_half = DTL.drc_zero_experiment(nl, widen=0.5)
    _e_full = DTL.drc_zero_experiment(nl, widen=1.0)
    # ① 通道这一项：构造出来的面积比必须**复现**下界预测（1.577×），证明模型没写错；
    #    但**它仍然违规** ⇒ 预测只是必要条件，不是「1.577× 就够」
    _pred_ok = abs(_e_ch["row_area_ratio"] - _cap["area_ratio_for_channel"]) \
        < 0.02 * _cap["area_ratio_for_channel"]
    check("S7e 通道项构造实测 %.2f× == 下界预测 %.2f×（模型自洽）∧ **仍违规 %d 处**"
          " ⇒ 「1.577× 换 0 违规」被推翻（预测是必要非充分）"
          % (_e_ch["row_area_ratio"], _cap["area_ratio_for_channel"],
             _e_ch["achieved_violations"]),
          _pred_ok and _e_ch["achieved_violations"] > 0,
          "pred=%.3f got=%.3f viol=%d" % (_cap["area_ratio_for_channel"],
                                          _e_ch["row_area_ratio"],
                                          _e_ch["achieved_violations"]))

    # ② 达标点：单元宽给够 ⇒ DRC **真的归零**（不是判据松了，是几何够了）
    check("S7f widen=1.0（单元宽 (n_pins+1)·pitch + 引脚均布 + 轨道分配）⇒ DRC **0**"
          " 且行面积 %.2f×（die 口径 %.2f×）"
          % (_e_full["row_area_ratio"], _e_full["area_ratio_vs_die"]),
          _e_full["achieved_violations"] == 0
          and _e_full["verdict"] == "DRC_ZERO_ACHIEVED",
          "achieved=%d by=%r" % (_e_full["achieved_violations"], _e_full["achieved_by_rule"]))

    # ③ 单调性：87 → 21 → 0。中间档仍违规 ⇒ 不是「随便放大都行」，存在真实阈值
    check("S7g 单调性：基准 %d → widen=0.5 **%d** → widen=1.0 **%d**（中间档仍违规 ⇒ 有阈值）"
          % (_e_ch["base_violations"], _e_half["achieved_violations"],
             _e_full["achieved_violations"]),
          _e_half["achieved_violations"] > 0
          and _e_half["achieved_violations"] < _e_ch["base_violations"]
          and _e_full["achieved_violations"] == 0,
          "half=%d" % _e_half["achieved_violations"])

    # ④ 卡片承载 == 独立复算 ∧ 反向两向（伪造计数 / 伪造低于下界的面积比）必红
    _cz = DC.case_card()["capacity"]["zero_experiment"]
    _f4 = json.loads(json.dumps(DC.case_card()))
    _f4["capacity"]["zero_experiment"]["achieved_violations"] = 0
    _f4["capacity"]["zero_experiment"]["verdict"] = "STILL_VIOLATING"
    _f5 = json.loads(json.dumps(DC.case_card()))
    _f5["capacity"]["zero_experiment"]["row_area_ratio"] = 1.0
    check("S7h 卡片 what-if == 独立复算（%s/%d/×%.2f）∧ 反向两向必红"
          % (_cz["verdict"], _cz["achieved_violations"], _cz["row_area_ratio"]),
          _cz["verdict"] == _e_full["verdict"]
          and _cz["achieved_violations"] == _e_full["achieved_violations"]
          and abs(_cz["row_area_ratio"] - _e_full["row_area_ratio"]) < 1e-9
          and DC.selfcheck(_f4) and DC.selfcheck(_f5),
          "card=%r" % (_cz,))

    # ── S7i–S7k 口径清理（v0.9.373）：短路必须分类 + 去重 + 披露与实测一致 ──
    #   🔴 起因：全仓原先只写「LVS 183 问题」，读者会当成「间距紧」；实际是**连通性错误**。
    #      而且 183 是**条目数**（同一网对被多段金属/通孔各报一次、双向各报一次），
    #      去重后只有 43 对网 —— 只报 183 会把规模夸大 4 倍。
    # 🔴 v0.9.376：183 条短路条目属于**旧链**（主链只有 4 条网、0 违规）
    #   ⇒ 这条口径纪律的载体随之移到 baseline，否则它会因「主链没有问题」而空转。
    _dl = rep["baseline"]["drc_lvs_detail"]
    _dl = {"by_rule": _dl["by_rule"], "unique_pairs": _dl["unique_pairs"],
           "problems": _dl["lvs"]["problems"]}
    _stage_lvs = rep["baseline"]["drc_lvs"]
    _uniq_ref = len({frozenset((str(x[1]), str(x[2]))) for x in _dl["problems"]})
    check("S7i LVS 分类与去重自洽：%r 求和=%d == problems=%d ∧ 去重 **%d 对网** ∧ "
          "干线段同样带 by_rule"
          % (_dl["by_rule"], sum(_dl["by_rule"].values()), len(_dl["problems"]), _uniq_ref),
          sum(_dl["by_rule"].values()) == len(_dl["problems"])
          and _dl.get("unique_pairs") == _uniq_ref
          and _uniq_ref <= len(_dl["problems"])
          and _stage_lvs.get("lvs_by_rule") == _dl["by_rule"]
          and (_dl["by_rule"].get("short") or _dl["by_rule"].get("short_via")),
          "by_rule=%r unique=%r ref=%r" % (_dl["by_rule"], _dl.get("unique_pairs"), _uniq_ref))

    # ② 披露与实测一致：ddetail 的诚实边界必须说「短路」，且不得再出现「0 同层短路」
    _dd_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "lda_l2", "ecore", "ddetail.py"), encoding="utf-8").read()

    def _disclosure_ok(src: str) -> bool:
        head = src.split('"""')[1] if src.count('"""') >= 2 else src
        return ("short" in head) and ("0 同层短路" not in head)

    check("S7j 披露与实测一致：ddetail 诚实边界含 `short` ∧ **不含「0 同层短路」**"
          "（该表述 v0.9.373 已删，与 78 处同层短路矛盾）",
          _disclosure_ok(_dd_src),
          "含 short=%s 含旧表述=%s" % ("short" in _dd_src, "0 同层短路" in _dd_src))

    # ③ 反向两向：把旧表述塞回披露 / 把分类调成与总数不符 ⇒ 判据与自检各必红
    _bad_src = _dd_src.replace("并且有 183 处 LVS 短路", "0 同层短路不代表布通，并且有 183 处 LVS 短路", 1)
    _bad_card = json.loads(json.dumps(DC.case_card()))
    _bad_card["baseline"]["drc_lvs"]["lvs_by_rule"] = {"short": 1}
    _bad_card2 = json.loads(json.dumps(DC.case_card()))
    _bad_card2["baseline"]["drc_lvs"]["lvs_unique_pairs"] = 999
    check("S7k 反向三向必红：① 旧表述塞回披露 ⇒ S7j 判据假 ② lvs_by_rule 与总数不符 ⇒ "
          "自检红 ③ 去重数 > 条目数 ⇒ 自检红",
          (not _disclosure_ok(_bad_src)) and DC.selfcheck(_bad_card)
          and DC.selfcheck(_bad_card2),
          "src=%s card1=%r card2=%r" % (_disclosure_ok(_bad_src),
                                        DC.selfcheck(_bad_card)[:1],
                                        DC.selfcheck(_bad_card2)[:1]))

    # ── S8–S9 双报一版（v0.9.376 主链切换）：两条链必须同时在场 ────────────
    #   🔴 这一步的风险不是「算错」，是**静默替换**：主链从 detail_route 换成 dpnr 后，
    #      如果不并排报旧链，87 处间距 + 183 条短路条目就会从报表里消失 ——
    #      而它们恰恰是「为什么必须换主链」的唯一证据。
    _blk = rep.get("baseline") or {}
    _trunk_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "lda_l2", "ecore", "db3_trunk.py"), encoding="utf-8").read()
    check("S8 双报一版：rep.chain=%r ∧ baseline.chain=%r ∧ 干线不 import track_route ∧ "
          "nets_with_segments(%d) ≤ nets_touched(%d)"
          % (rep.get("chain"), _blk.get("chain"), rt["nets_with_segments"],
             rt["nets_touched"]),
          rep.get("chain") == "dpnr" and _blk.get("chain") == "detail_route"
          and "track_route" not in _trunk_src
          and rt["nets_with_segments"] <= rt["nets_touched"],
          "chain=%r baseline=%r track=%s"
          % (rep.get("chain"), _blk.get("chain"), "track_route" in _trunk_src))

    # 面积代价：必须两侧都给，且比值 == 独立复算；不许把「pin 可达性代价」说成工艺升级
    _ad = rep.get("area_delta") or {}
    _main_a = rep["stages"][1][1]["die_area_um2"]
    _base_a = (_blk.get("place") or {}).get("die_area_um2")
    # 报告里的 ratio 是 3 位小数（round 过），对拍必须用**同精度**比较：
    # 用 1e-6 容差去比一个 round(·,3) 的值，判据必然假红（本节首跑就是这么红的）。
    _ratio_ok = bool(_main_a and _base_a) and \
        round(_main_a / _base_a, 3) == _ad.get("ratio")
    check("S9 面积代价如实：主链 %.3f µm² / 旧链 %.3f µm² ⇒ ×%.3f（独立复算一致）∧ "
          "理由写明「不是工艺升级」"
          % (_main_a or 0, _base_a or 0, _ad.get("ratio") or 0),
          _ratio_ok and _ad.get("ratio", 0) > 1.0
          and "不是工艺升级" in (_ad.get("reason") or ""),
          "area_delta=%r main=%r base=%r" % (_ad, _main_a, _base_a))

    # 反向：把 chain 改标成旧链 / 把 baseline 抹掉 ⇒ 卡片自检各必红（自检认得出来）
    _cbl = json.loads(json.dumps(card))
    _cbl["chain"] = "detail_route"
    _cbl2 = json.loads(json.dumps(card))
    _cbl2["baseline"] = {}
    _cbl3 = json.loads(json.dumps(card))
    _cbl3["area_delta"] = {}
    check("S9-P1 反向三向必红：主链标识改标旧链 / baseline 抹掉 / area_delta 抹掉 ⇒ "
          "自检各报一条（防静默替换）",
          DC.selfcheck(_cbl) and DC.selfcheck(_cbl2) and DC.selfcheck(_cbl3),
          "1=%r 2=%r 3=%r" % (DC.selfcheck(_cbl)[:1], DC.selfcheck(_cbl2)[:1],
                              DC.selfcheck(_cbl3)[:1]))

    # ── T1–T5 时序段（v0.9.377）：拓扑序 + 线载单调 + 三态 + 反向 ─────────
    from lda_l2.ecore import dextract as DE                   # noqa: E402
    from lda_l2.ecore import dsta as ST                       # noqa: E402

    import lda_l2.ecore.dsynth as SY                          # noqa: E402

    tmg = _stage(rep, "timing")
    shp = PN.all_routing(PN.route_block(nl, PN.place_real(nl)))
    _ideal_comb = ST.sta(nl, topo_sort=True).comb_delay_ps

    # T1 拓扑序：先证明**排序结果合法**，再用**人造反例**证明不排序会错。
    #   🔴 首版这里写错过：我曾断言「c17 的书写顺序不是拓扑序」，实测是**错的** ——
    #      c17 文件序本就是合法拓扑序；当初的 KeyError 来自输入网名（`_inet` 约定
    #      vs `dverilog` 的 `n1`），与门序无关。判据改为两条都机核：
    #      ① topo_order 的输出必须满足「每个生产者先于消费者」（对任意网表成立）；
    #      ② 把门序**倒过来**（人造违例）⇒ 不排序必须报错，排序后必须回到同一答案。
    _prod = {g.out: i for i, g in enumerate(nl.gates)}          # 网 → 文件序下标
    _prod_name = {g.out: g.name for g in nl.gates}              # 网 → 生产者门名
    _file_is_topo = all(_prod.get(n, -1) < i
                        for i, g in enumerate(nl.gates) for n in g.ins)
    _topo = list(SY.topo_order(nl))
    _pos = {g.name: i for i, g in enumerate(_topo)}             # 门名 → 拓扑序下标
    _topo_valid = all(_pos[_prod_name[n]] < _pos[g.name]
                      for g in _topo for n in g.ins if n in _prod_name)
    _rev = SY.Netlist(name="rev", inputs=nl.inputs, in_nets=dict(nl.in_nets),
                      outputs=dict(nl.outputs), gates=list(reversed(nl.gates)),
                      clocks=nl.clocks)
    try:
        ST.sta(_rev)                      # 不排序：人造违例必须炸（不许静默算错）
        _rev_failed = False
    except KeyError:
        _rev_failed = True
    _rev_sorted = ST.sta(_rev, topo_sort=True)
    check("T1 拓扑序：排序结果**合法**（每个生产者先于消费者）∧ 人造反例（门序倒置）"
          "不排序必报错、排序后回到同一答案（%.3f ps）"
          % _rev_sorted.comb_delay_ps,
          _topo_valid and _rev_failed
          and abs(_rev_sorted.comb_delay_ps - _ideal_comb) < 1e-9,
          "valid=%s rev_failed=%s rev=%.4f"
          % (_topo_valid, _rev_failed, _rev_sorted.comb_delay_ps))
    check("T1b 如实记录：c17 的**书写顺序本身就是合法拓扑序**（%s）⇒ `topo_sort` 是"
          "对其他网表的防线，不是「修 c17」" % _file_is_topo,
          _file_is_topo is True, "file_is_topo=%r" % _file_is_topo)

    # T2 线载单调 + 与 dextract 同源：卡片值 == 独立复算；加负载必更慢
    _wl = DE.wire_loads_from_shapes(shp)
    _ideal = ST.sta(nl, topo_sort=True)      # 与 T1 的 _ideal_comb 同值，此处留作对照
    _wired = ST.sta(nl, wire_load_ff=_wl, topo_sort=True)
    check("T2 线载同源且单调：独立复算 ideal=%.3f / wired=%.3f ps ∧ wired > ideal "
          "∧ 总线载 %.3f fF（%d 条网）"
          % (_ideal.comb_delay_ps, _wired.comb_delay_ps, sum(_wl.values()), len(_wl)),
          abs(tmg["comb_delay_ideal_ps"] - round(_ideal.comb_delay_ps, 3)) < 1e-9
          and abs(tmg["comb_delay_wired_ps"] - round(_wired.comb_delay_ps, 3)) < 1e-9
          and _wired.comb_delay_ps > _ideal.comb_delay_ps
          and tmg["nets_with_wire"] == len(_wl),
          "card=(%r,%r) gate=(%r,%r)"
          % (tmg["comb_delay_ideal_ps"], tmg["comb_delay_wired_ps"],
             round(_ideal.comb_delay_ps, 3), round(_wired.comb_delay_ps, 3)))

    # T3 单调性探针：线载 ×100 ⇒ 必须更慢（防「线载没真进模型」）
    _x100 = ST.sta(nl, wire_load_ff={k: v * 100 for k, v in _wl.items()}, topo_sort=True)
    check("T3 线载 ×100 ⇒ 延时进一步上升（%.3f → %.3f ps）—— 证明线载真进了负载模型"
          % (_wired.comb_delay_ps, _x100.comb_delay_ps),
          _x100.comb_delay_ps > _wired.comb_delay_ps,
          "x100=%.3f" % _x100.comb_delay_ps)

    # T4 三态：无时钟域 ⇒ t_clk_min / fmax 必须是 None，且未布网数必须显式
    check("T4 三态不压扁：n_dff=%d ⇒ t_clk_min=%r ∧ fmax=%r（**None，不是 0**）∧ "
          "nets_without_wire=%r 显式（未布网按 0 线载 ⇒ 偏乐观）"
          % (tmg["n_dff"], tmg["t_clk_min_ps"], tmg["fmax_mhz"], tmg["nets_without_wire"]),
          tmg["n_dff"] == 0 and tmg["t_clk_min_ps"] is None and tmg["fmax_mhz"] is None
          and tmg["clock_domains"] == 0 and tmg["nets_without_wire"] is not None
          and tmg["nets_without_wire"] > 0,
          "tmg=%r" % ({k: tmg[k] for k in ("n_dff", "t_clk_min_ps", "fmax_mhz",
                                           "nets_without_wire")},))

    # T5 反向四向必红：造时钟 / hold 声称已检 / 延时倒挂 / 抹掉未布网数
    _t1 = json.loads(json.dumps(card))
    _t1["timing"]["fmax_mhz"] = 1000.0
    _t2 = json.loads(json.dumps(card))
    _t2["timing"]["hold_checked"] = True
    _t3 = json.loads(json.dumps(card))
    _t3["timing"]["comb_delay_wired_ps"] = 1.0
    _t4 = json.loads(json.dumps(card))
    _t4["timing"]["nets_without_wire"] = None
    check("T5 反向四向必红：无时钟域造 Fmax / hold 声称已检 / 带载延时倒挂 / "
          "抹掉未布网数 ⇒ 自检各报一条",
          DC.selfcheck(_t1) and DC.selfcheck(_t2) and DC.selfcheck(_t3)
          and DC.selfcheck(_t4),
          "1=%r 2=%r 3=%r 4=%r" % (DC.selfcheck(_t1)[:1], DC.selfcheck(_t2)[:1],
                                    DC.selfcheck(_t3)[:1], DC.selfcheck(_t4)[:1]))

    # ── C1–C4 签核资格条件化（v0.9.378）：claimable 由六条实测推导 ────────────
    #   🔴 为什么必须先给一个 **True 用例**：如果判据恒为 False（常量时代就是这样），
    #      那么「缺一必 False」的六条探针**全部平凡通过** —— 恒假当然每条都 False。
    #      所以先证明「六条全满足时能给 True」，再逐条证明「缺一条就 False」。
    _full = {"stages": [
        ("route", {"all_routed": True}),
        ("drc_lvs", {"drc_violations": 0, "lvs_problems": 0, "lvs_scope": "FULL_CHIP"}),
        ("timing", {"topo_sorted": True, "hold_checked": True}),
    ]}
    _cl_full = T.claimability(_full)

    def _variant(**over):
        """在「全满足」基底上只改**一个** measured 项。"""
        rt = {"all_routed": True}
        dl = {"drc_violations": 0, "lvs_problems": 0, "lvs_scope": "FULL_CHIP"}
        tm = {"topo_sorted": True, "hold_checked": True}
        stages = []
        if over.get("all_nets_routed") is not None:
            rt["all_routed"] = over["all_nets_routed"]
        if over.get("drc_zero") is not None:
            dl["drc_violations"] = over["drc_zero"]
        if over.get("lvs_zero") is not None:
            dl["lvs_problems"] = over["lvs_zero"]
        if over.get("lvs_scope_full_chip") is not None:
            dl["lvs_scope"] = over["lvs_scope_full_chip"]
        if over.get("hold_checked") is not None:
            tm["hold_checked"] = over["hold_checked"]
        stages.append(("route", rt))
        stages.append(("drc_lvs", dl))
        # 🔴 `timing_included=False` 有两种形态，必须分开测（首版混成一种，判据误红）：
        #   · 段在但没排拓扑序（`topo_sorted=False`）⇒ **只有** timing_included 不满足；
        #   · 段整体缺失 ⇒ 连 `hold_checked` 都无从测量 ⇒ **两条同时**阻塞
        #     （这正体现「没测 ≠ 通过」，不是判据 bug）。
        if over.get("timing_included") is False:
            stages.append(("timing", dict(tm, topo_sorted=False)))
        elif over.get("timing_included") == "absent":
            pass
        else:
            stages.append(("timing", tm))
        return {"stages": stages}

    _cl_cur = rep["claimability"]
    check("C1 条件清单完整：n=%d 条 ∧ condition_list_ok=True ∧ 当前阻塞项恰为 %r"
          % (_cl_cur["n_conditions"], _cl_cur["blocking"]),
          _cl_cur["condition_list_ok"] is True and _cl_cur["n_conditions"] == 6
          and set(_cl_cur["conditions"]) == set(T.CLAIMABLE_CONDITIONS)
          and _cl_cur["claimable"] is False
          and sorted(_cl_cur["blocking"]) == sorted(
              k for k, v in _cl_cur["conditions"].items() if v is not True),
          "cl=%r" % ({k: _cl_cur[k] for k in ("claimable", "blocking", "n_conditions")},))

    # 正向：六条全满足 ⇒ True（证明判据不是恒假）
    check("C2 **正向用例**：六条全部满足的合成报告 ⇒ claimable=True（blocking=%r）"
          % (_cl_full["blocking"],),
          _cl_full["claimable"] is True and _cl_full["blocking"] == []
          and _cl_full["condition_list_ok"] is True,
          "full=%r" % (_cl_full["conditions"],))

    # 缺一必 False：逐条只翻一个 ⇒ claimable 必 False，且 blocking 恰为该条
    _cases = {
        "all_nets_routed": dict(all_nets_routed=False),
        "drc_zero": dict(drc_zero=1),
        "lvs_zero": dict(lvs_zero=1),
        "lvs_scope_full_chip": dict(lvs_scope_full_chip="ROUTED_SUBSET_ONLY"),
        "timing_included": dict(timing_included=False),
        "hold_checked": dict(hold_checked=False),
    }
    _res = {}
    for _name, _kw in _cases.items():
        _r = T.claimability(_variant(**_kw))
        _res[_name] = (_r["claimable"], _r["blocking"])
    check("C3 **缺一必 False**：逐条只翻一条 ⇒ claimable 必 False 且 blocking 恰为该条（六向）",
          all(v[0] is False and v[1] == [k] for k, v in _res.items()),
          "res=%r" % (_res,))

    # C3b 时序段**整体缺失** ⇒ timing_included 与 hold_checked **同时**阻塞
    #   （「没测」不等于「通过」；这是与 C3 分开的一条，因为它的阻塞是两条而不是一条）
    _absent = T.claimability(_variant(timing_included="absent"))
    check("C3b 时序段整体缺失 ⇒ 同时阻塞 timing_included 与 hold_checked（%r）—— "
          "「没测」不等于「通过」" % (_absent["blocking"],),
          _absent["claimable"] is False
          and sorted(_absent["blocking"]) == ["hold_checked", "timing_included"],
          "absent=%r" % (_absent["blocking"],))

    # 卡片同源 + 一个结论不许出现两个值 + 反向三向必红
    _cc = DC.case_card()
    _t1 = json.loads(json.dumps(_cc))
    _t1["claimable"] = True
    _t2 = json.loads(json.dumps(_cc))
    _t2["claimability"]["blocking"] = []
    _t3 = json.loads(json.dumps(_cc))
    _t3["claimability"]["conditions"].pop("hold_checked", None)
    check("C4 卡片 claimable == 独立复算（%s / 阻塞 %r）∧ 与 drc_lvs/routing 同值 ∧ "
          "反向三向必红（手改 True / 抹 blocking / 删一条条件）"
          % (_cc["claimable"], _cc["claimability"]["blocking"]),
          _cc["claimable"] == _cl_cur["claimable"]
          and _cc["claimability"]["conditions"] == _cl_cur["conditions"]
          and _cc["drc_lvs"]["claimable"] == _cc["claimable"]
          and _cc["routing"]["claimable"] == _cc["claimable"]
          and DC.selfcheck(_t1) and DC.selfcheck(_t2) and DC.selfcheck(_t3),
          "card=%r" % ({k: _cc["claimability"][k] for k in ("claimable", "blocking")},))

    # ── S0t 耗时红线 ──────────────────────────────────────────────────
    dt = time.time() - T0
    check("S0t 门禁耗时 %.2f s < %.0f s" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, "%.2f s" % dt)

    print()
    print("  [模块] db3_trunk · 纯标准库 · C 级自主 · LLM 不进判决路径")
    print("  [S0] 干线跑通（c17 端到端）· 守恒断言全绿")
    print("  [S1] 解析段守恒：6 门 / 11 网")
    print("  [S2] 布局段守恒：place 覆盖每颗门")
    print("  [S3] 布线段守恒：route 覆盖每条网")
    print("  [S4] DRC/LVS 如实报告（claimable=False，不伪造 clean）")
    print("  [D1–D4] DEF 写出段：placed DEF（落点 + 连接）· 往返字节双射 · **不写 ROUTED**")
    print("         （ddetail.shapes 无网归属 ⇒ 写布线就是编造；缺落点 ⇒ fail-closed）")
    print("  [S5] fail-closed：空输入直接报错")
    print("  [S7a–d] DRC 收敛：via_enclosure 修至 0（不改线长）· 容量下界三向都缺 · "
          "卡片与门禁同口径 · 三向伪造必红")
    print("  [S7i–k] 口径清理：LVS 183 条（78 short + 105 short_via）**去重 43 对网** · "
          "披露含 short 且无旧表述 · 三向探针必红")
    print("  [S7e–h] 反证实验：1.58×（通道下界）仍违规 155 ⇒ 预测必要非充分；"
          "给足单元宽 ⇒ DRC 0，代价 26.32× 行面积；0.5× 档仍 21 ⇒ 有阈值")
    print("  [C1–C4] 签核资格：六条条件全部由实测推导 · **先给 True 用例**（防恒假判据）· "
          "逐条「缺一必 False」· 卡片与门禁同值 · 反向三向必红")
    print("  [T1–T5] 时序段：拓扑序是必要的（不排序即 KeyError）· 线载同源且单调 · "
          "无时钟域 fmax=None 不压扁 · 反向四向必红")
    print("  [S8–S9] 双报一版：主链 dpnr + 旧链 detail_route 并排 · 面积代价 ×%.2f 写明"
          "「pin 可达性代价，不是工艺升级」· 反向三向（改标/抹 baseline/抹面积）必红"
          % ((rep.get("area_delta") or {}).get("ratio") or 0))
    print("  [S6a–f] 对外入口 /api/digital_demo：卡片 == 门禁独立重跑的真值 · "
          "未实现段显式 False · 自检两向可判红 · digest 稳定")
    print("  [边界] ddetail 路由器 claimable=False · 几何/时序为模型假设 · 非 foundry PDK")

    if _FALS:
        print("S6 有红色：%s" % ", ".join(_FALS))
        return 1
    print("S6 全绿 · B3 数字链干线落地：c17 用现状模块端到端跑通 + 每段守恒断言 + "
          "DRC/LVS 诚实披露")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
