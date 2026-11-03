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
  S6 **对外入口**：`/api/digital_demo` 消费干线（此前干线**只有自己的门禁在调它**）——
     卡片数字必须 == 门禁**独立重跑**的真值；未实现的段（综合/时序/ROUTED）显式 False；
     诚实性自检正向空、反向两向必报；两次调用 digest 一致且 JSON 硬。

诚实边界
────────
· ddetail.detail_route 的 claimable=False（c17 实测 101 DRC 违规）是**已知边界**，干线如实披露；
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

    # ── S3 布线段守恒（route 覆盖每条网）──────────────────────────────
    rt = _stage(rep, "route")
    check("S3 布线段守恒：route 覆盖全部 11 条网（routed_nets == nets）",
          rt is not None and rt["routed_nets"] == 11 and rt["routed_nets"] == p["nets"],
          "routed_nets=%s nets=%s" % (rt["routed_nets"] if rt else None, p["nets"]))

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
    _p2 = PL.place(nl)
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
        "lvs_problems": len(_rep2["drc_lvs_detail"]["lvs"]["problems"]),
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
    check("S6c 分规则 DRC 计数自洽（Σ 分规则 == 总数）∧ 违规/问题如实报 >0（不伪造 clean）",
          sum(card["drc_lvs"]["drc_by_rule"].values()) == card["drc_lvs"]["drc_violations"]
          and card["drc_lvs"]["drc_violations"] > 0
          and card["drc_lvs"]["lvs_problems"] > 0
          and card["drc_lvs"]["drc_ok"] is False,
          "by_rule=%r" % (card["drc_lvs"]["drc_by_rule"],))

    # ── S6d 诚实三态：未实现的段必须显式 False（不是「没说」）───────────
    check("S6d 未实现的段显式登记：synthesized=False ∧ timing_included=False ∧ "
          "routed_exported=False（`ROUTED` 未导出 —— shapes 无网归属）",
          card["synthesized"] is False and card["timing_included"] is False
          and card["def_export"]["routed_exported"] is False,
          "synthesized=%r timing=%r routed=%r" % (card["synthesized"],
                                                  card["timing_included"],
                                                  card["def_export"]["routed_exported"]))

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
