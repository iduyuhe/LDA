# -*- coding: utf-8 -*-
"""B3 · **数字链干线对外只读案例卡**（`/api/digital_demo`）。

═══════════════════════════════════════════════════════════════════════════════
为什么要有这张卡
───────────────────────────────────────────────────────────────────────────────
B3 干线（`db3_trunk`）此前**只被自己的门禁调用** —— 也就是「只有检查它的东西在用它」，
没有任何真实消费者。本模块给它第一个**非门禁**下游：把 c17 端到端的真实落点/布线/DRC/
DEF 写出结果做成对外可看的只读卡片。

🔴 **口径纪律（三条，都能被机核）**
  ① **不冒充签核**：`verdict` 恒为 `FLOW_RUN_NOT_SIGNOFF`（流程跑通 ≠ 签核 ≠ 流片实测）。
     `ddetail` 路由器在 c17 上实测 **87 处 min_spacing**（弯角孔包围 v0.9.370 已修至 0；
     余下为**容量不足**，见 `capacity` 段）⇒ 卡片**如实报违规数与分规则计数**，
     绝不写「clean」「pass」「signoff」。
  ② **不报未实现的段**：`synthesized=False`（入口就是门级网表）、`timing_included=False`
     （干线未串时序段）、`routed_exported=False`（DEF 只到 placed，`ROUTED` 未导出 ——
     `ddetail.DetailRoute.shapes` 没有按网归属，写了就是编造布线）。
  ③ **不报能效**：不报 TOPS / TOPS-W / fJ/op；不宣称与商业工具互通。

🔴 **成本与确定性**
  · 计算**一次性**（模块级缓存 + 串行锁）：首调要 import 数字链（~0.2s）+ 跑一次干线（~10ms），
    其后每次仅重组字典（微秒级）。**不做每请求重算**（避免 DoS 面）。
  · `digest` = 规范化 JSON（`sort_keys` + 浮点 round 6）的 sha256 ⇒ **同输入同结果**；
    `compute_ms`（实测耗时）**不进 digest**，否则每台机器都不一样。

🔴 **诚实边界（在本卡里逐条写明，不靠读者猜）**
  · 非 foundry PDK（INV/NAND2 为教科书尺度单元）；非流片实测；不做 P&R 宣称之外的事；
  · DEF 引脚名是 **LDA 约定**（`dcell` 只声明输入名，输出统一记 `z`），宏名是 netlist 单元名，
    **不是库真名** ⇒ 不可称与商业工具互通（真实互通须 LEF `PORT` 名覆盖）；
  · 无综合、无时序、无寄生；LLM 不进判决路径；C 级自主（纯标准库）。
"""
from __future__ import annotations

import hashlib
import json
import threading
from typing import Any, Dict, List

CASE_ID = "D-B3-DIGITAL-TRUNK"
ENDPOINT = "/api/digital_demo"
#: 🔴 恒为「流程跑通」——**不是** ACCEPT / PASS / SIGNOFF。改这个字面量 ⇒ 自检必红。
VERDICT = "FLOW_RUN_NOT_SIGNOFF"

#: 声明本卡覆盖/未覆盖的段（机核用，禁止与实际行为不一致）
SEGMENTS_COVERED = ("parse", "place", "route", "drc_lvs", "def_write")
SEGMENTS_MISSING = ("synthesis", "timing")

#: 诚实边界（逐条都在卡片里输出，且被 selfcheck 要求非空 + 含关键词）
HONEST_NOTES = (
    "设计期流程跑通，非签核、非流片实测。",
    "ddetail 路由器 claimable=False：c17 实测 87 处 min_spacing（via_enclosure 已修至 0），"
    "本卡如实报数，不伪造 clean；余下违规是**容量不足**（capacity 段），不是路由器写错。",
    "DEF 只到 placed（routed_exported=False）—— DetailRoute.shapes 无按网归属，"
    "写 ROUTED 等于编造布线。",
    "synthesized=False（入口即门级网表）、timing_included=False（干线未串时序段）。",
    "单元库为教科书尺度、非 foundry PDK；不改称任何制造/性能结论。",
    "不报 TOPS / TOPS-W / fJ/op；不宣称与 OpenROAD/OpenSTA 等外部工具一致。",
    "DEF 引脚名为 LDA 约定（输出记 z），宏名为 netlist 单元名，非库真名。",
    "B4 差异表的参考列是 unavailable（本机无 OpenROAD/OpenSTA）⇒ evidence_level "
    "只到 SELF_CONSISTENCY_ONLY，不构成与外部工具一致的证据。",
)

_LOCK = threading.Lock()
_CACHE: Dict[str, Any] = {}


def _by_rule(violations: List[Any]) -> Dict[str, int]:
    """DRC 违规按规则名计数（violation = (rule, layer, p1, p2) 形态）。"""
    out: Dict[str, int] = {}
    for v in violations or []:
        rule = v[0] if isinstance(v, (list, tuple)) and v else str(v)
        out[str(rule)] = out.get(str(rule), 0) + 1
    return dict(sorted(out.items()))


def _canonical(obj: Any) -> str:
    """规范化 JSON 串（digest 的唯一口径：排序键 + 紧凑分隔 + 浮点 round 6）。"""
    def _norm(x):
        if isinstance(x, float):
            return round(x, 6)
        if isinstance(x, dict):
            return {k: _norm(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [_norm(v) for v in x]
        return x
    return json.dumps(_norm(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(card: Dict[str, Any]) -> str:
    """卡片内容的 sha256（**排除** compute_ms / digest 自身 ⇒ 跨机器同输入同 digest）。"""
    body = {k: v for k, v in card.items() if k not in ("compute_ms", "digest")}
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def _xcheck_facts(X, table: Dict[str, Any]) -> Dict[str, Any]:
    """把 B4 差异表压成卡片可承载的形状（**逐行保留三态与归因，不压扁、不改写**）。"""
    rows = []
    for r in table.get("rows") or []:
        rows.append({
            "metric": r.get("metric"),
            "unit": r.get("unit"),
            "lda_value": (r.get("lda") or {}).get("value"),
            "lda_source": (r.get("lda") or {}).get("source"),
            "reference_status": (r.get("reference") or {}).get("status"),
            "reference_tool": (r.get("reference") or {}).get("tool"),
            "baseline_used": r.get("baseline_used"),
            "delta": r.get("delta"),
            "exceeds": r.get("exceeds"),          # 🔴 true / false / null 三态，原样保留
            "evidence_level": r.get("evidence_level"),
            "attribution_code": (r.get("attribution") or {}).get("code"),
        })
    codes = {r["attribution_code"] for r in rows}
    known = set(getattr(X, "ATTRIBUTION_CODES", ()) or ())
    meta = table.get("meta") or {}
    return {
        "schema": table.get("schema"),
        "digest_sha256": X.digest(table),
        "claimable": bool(meta.get("claimable", False)),
        "claimable_reason": meta.get("claimable_reason"),
        "reference_available": bool(meta.get("reference_available", False)),
        "n_rows": len(rows),
        "rows": rows,
        # 机核用：归因码是否都落在闭式词表内 / dxcheck 自己的表校验是否零问题
        "attribution_codes_ok": bool(codes) and codes <= known,
        "table_problems": list(X.validate_table(table) or []),
    }


def _compute() -> Dict[str, Any]:
    """跑一次干线 + 一次 B4 对拍，抽成纯数据事实（**只搬运真值，不做二次推断**）。"""
    import time

    from lda_l2.ecore import db3_trunk as T
    from lda_l2.ecore import ddetail as DD
    from lda_l2.ecore import dplac as PL
    from lda_l2.ecore import dverilog as V
    from lda_l2.ecore import dxcheck as X

    t0 = time.perf_counter()
    nl = V.parse(V.SAMPLE_VERILOG)          # 🔴 只解析一次，干线与对拍共用同一 netlist
    report = T.run_trunk(nl)
    table = X.xcheck(nl, subject="c17")
    cap = DD.drc_capacity_bound(nl, PL.place(nl))   # 🔴 容量下界（独立 layout，不改干线）
    # 🔴 what-if：按「可布线所需」放大后 DRC 能否归零（4ms；**不是**可签核版图）
    cap = dict(cap, zero_experiment=DD.drc_zero_experiment(nl))
    ms = (time.perf_counter() - t0) * 1000.0

    st = {name: payload for name, payload in report["stages"]}
    drc = report["drc_lvs_detail"]["drc"]
    lvs = report["drc_lvs_detail"]["lvs"]
    routed = st.get("route", {})
    placed = st.get("place", {})
    wrote = st.get("def_write", {})
    parsed = st.get("parse", {})

    return {
        "compute_ms": round(ms, 3),
        "subject": {
            "benchmark": "ISCAS'85 c17",
            "source": "lda_l2.ecore.dverilog.SAMPLE_VERILOG（公开基准网表）",
            "gates": parsed.get("gates"),
            "nets": parsed.get("nets"),
            "inputs": parsed.get("inputs"),
            "outputs": parsed.get("outputs"),
        },
        "placement": {
            "cells": placed.get("cells"),
            "die_w_um": placed.get("die_w_um"),
            "die_h_um": placed.get("die_h_um"),
            "hpwl_um": placed.get("hpwl_um"),
            "cell_area_sum_um2": placed.get("cell_area_sum_um2"),
        },
        "routing": {
            "shapes": routed.get("shapes"),
            "routed_nets": routed.get("routed_nets"),
            "routed_segments": routed.get("routed_segments"),
            "claimable": False,
        },
        "drc_lvs": {
            "drc_ok": bool(drc.get("ok")),
            "drc_violations": len(drc.get("violations") or []),
            "drc_by_rule": _by_rule(drc.get("violations")),
            "lvs_ok": bool(lvs.get("ok")),
            "lvs_problems": len(lvs.get("problems") or []),
            "claimable": False,
        },
        "def_export": {
            "bytes": wrote.get("bytes"),
            "components": wrote.get("components"),
            "nets": wrote.get("nets"),
            "terms": wrote.get("terms"),
            "units_dbu_per_um": wrote.get("units"),
            "roundtrip_ok": bool(wrote.get("roundtrip_ok")),
            "routed_exported": bool(wrote.get("routed_exported")),
        },
        "conservation_ok": bool(report.get("conservation_ok")),
        "problems": list(report.get("problems") or []),
        "xcheck": _xcheck_facts(X, table),
        "capacity": cap,
        "segments_covered": list(SEGMENTS_COVERED),
        "segments_missing": list(SEGMENTS_MISSING),
        "synthesized": False,
        "timing_included": False,
    }


def facts() -> Dict[str, Any]:
    """一次性计算 + 模块级缓存（串行锁防并发重复计算）。"""
    with _LOCK:
        if "facts" not in _CACHE:
            _CACHE["facts"] = _compute()
        return _CACHE["facts"]


def clear_cache() -> None:
    """测试/门禁用：清缓存后重算（生产路径不调用）。"""
    with _LOCK:
        _CACHE.clear()


def case_card() -> Dict[str, Any]:
    """组装只读卡片（微秒级：仅重组字典 + 算 digest）。"""
    f = facts()
    card: Dict[str, Any] = {
        "endpoint": ENDPOINT,
        "case_id": CASE_ID,
        "claim": "用 LDA 跑通一条数字链干线：结构级 Verilog → 门级网表 → 布局 → 布线 → "
                 "DRC/LVS → DEF 写出，**每段断言吃的是上一段的输出**（守恒失败即 fail-closed）。",
        "verdict": VERDICT,
        "verdict_label": "设计期流程跑通（非签核 · 非流片实测）",
        "subject": f["subject"],
        "placement": f["placement"],
        "routing": f["routing"],
        "drc_lvs": f["drc_lvs"],
        "def_export": f["def_export"],
        "conservation_ok": f["conservation_ok"],
        "problems": f["problems"],
        "xcheck": f["xcheck"],
        "capacity": f["capacity"],
        "segments_covered": f["segments_covered"],
        "segments_missing": f["segments_missing"],
        "synthesized": f["synthesized"],
        "timing_included": f["timing_included"],
        "honest_note": list(HONEST_NOTES),
        "disclosure": {
            "pdk": "非 foundry PDK（教科书尺度 INV/NAND2）",
            "signoff": "否 —— DRC/LVS 未 converged，路由器 claimable=False",
            "external_agreement": "未验证（本机无 OpenROAD/OpenSTA；不宣称一致）",
            "pin_names": "LDA 约定：输入取 dcell 引脚名，输出统一 z（非库真名）",
            "units": "DEF 1 DBU = 1 nm（UNITS DISTANCE MICRONS 1000）",
            "energy_metrics": "不报 TOPS / TOPS-W / fJ/op",
            "sovereignty": "C 级自主（纯标准库）；LLM 不进判决路径",
        },
        "compute_ms": f["compute_ms"],
    }
    card["digest_sha256"] = digest(card)
    return card


def selfcheck(card: Dict[str, Any]) -> List[str]:
    """卡片自身的诚实性自检（返回问题列表；**空 = 通过**）。门禁直接喂变异体验证可判红。"""
    bad: List[str] = []
    if card.get("verdict") != VERDICT:
        bad.append("verdict 必须是 %s（当前 %r）—— 不得冒充签核" % (VERDICT, card.get("verdict")))
    if card.get("endpoint") != ENDPOINT:
        bad.append("endpoint 不符：%r" % (card.get("endpoint"),))
    notes = card.get("honest_note") or []
    if not notes:
        bad.append("honest_note 为空 —— 诚实边界不得静默")
    blob = " ".join(notes)
    for kw in ("非流片实测", "claimable=False", "非 foundry PDK", "TOPS", "synthesized=False"):
        if kw not in blob:
            bad.append("honest_note 缺关键词：%s" % kw)
    if card.get("synthesized") is not False:
        bad.append("synthesized 必须为 False（入口即门级网表，未做综合）")
    if card.get("timing_included") is not False:
        bad.append("timing_included 必须为 False（干线未串时序段）")
    de = card.get("def_export") or {}
    if de.get("routed_exported") is not False:
        bad.append("routed_exported 必须为 False（shapes 无网归属，不得写 ROUTED）")
    if de.get("roundtrip_ok") is not True:
        bad.append("DEF 往返双射未通过：roundtrip_ok=%r" % (de.get("roundtrip_ok"),))
    drc = card.get("drc_lvs") or {}
    if drc.get("drc_ok") is True or drc.get("lvs_ok") is True:
        bad.append("drc_ok/lvs_ok 报 True —— 与 claimable=False 矛盾（不得伪造 clean）")
    if len(drc.get("drc_by_rule") or {}) == 0 and (drc.get("drc_violations") or 0) > 0:
        bad.append("有违规但分规则计数为空 —— 记账不完整")
    if card.get("conservation_ok") is not True:
        bad.append("干线守恒断言未通过 —— 不能对外声称「跑通」")

    # ── B4 差异表（对拍对外可见）：三态、归因、证据等级三条都不能软 ──────────
    xc = card.get("xcheck") or {}
    rows = xc.get("rows") or []
    if not rows:
        bad.append("xcheck 行为空 —— 对拍结果不得静默缺失")
    if not xc.get("attribution_codes_ok"):
        bad.append("归因码不在闭式词表内（P5：归因必须可枚举、非空）")
    if xc.get("table_problems"):
        bad.append("dxcheck 表校验有问题：%r" % (xc.get("table_problems"),))
    # 三态纪律：exceeds 只许 true/false/null；值为 None 时**不许**报「未超界」
    for r in rows:
        _m, _ex = r.get("metric"), r.get("exceeds")
        if _ex not in (True, False, None):
            bad.append("%s: exceeds 非法取值 %r（只允许三态）" % (_m, _ex))
        if r.get("lda_value") is None and _ex is False:
            bad.append("%s: 值为 None 却报「未超界」—— 把「测不了」压扁成「没问题」" % _m)
    # 🔴 以**卡片级** `reference_available` 反推逐行状态：参考工具缺席时，任何一行都不许
    #    自称 measured / EXTERNAL_CROSSCHECK —— 否则就是「本机没跑过，却对外说跑过」。
    #    （反过来 reference_available=True（装了 OpenROAD 的机器）不在此处判红：那是
    #      真实更强的证据，不该被本规则误伤。）
    _avail = xc.get("reference_available")
    if _avail is False:
        for r in rows:
            m = r.get("metric")
            if r.get("reference_status") != "unavailable":
                bad.append("%s: 参考工具缺席却报 reference_status=%r（虚报外部对拍）"
                           % (m, r.get("reference_status")))
            if r.get("evidence_level") != "SELF_CONSISTENCY_ONLY":
                bad.append("%s: 参考未实测却把证据等级报成 %r" % (m, r.get("evidence_level")))

    # ── 容量下界与实测必须自洽（「清不了零」要说得出差在哪，且不能两头都圆）──
    cap = card.get("capacity") or {}
    _c_ok = (cap.get("capacity_per_row", 0) >= cap.get("clique_max", 0))
    _w_ok = (cap.get("pin_slot_need_um", 0) <= cap.get("cell_w_median_um", 0) + 1e-9)
    _x_ok = (cap.get("cols_need_um", 0) <= cap.get("cols_have_um", 0) + 1e-9)
    if cap.get("channel_ok") is not _c_ok or cap.get("width_ok") is not _w_ok \
            or cap.get("cols_ok") is not _x_ok:
        bad.append("capacity 的 *_ok 与数值不自洽（判定被手改）")
    _feasible = _c_ok and _w_ok and _x_ok
    if cap.get("verdict") != ("RESOURCE_SUFFICIENT" if _feasible else
                              "ROUTING_RESOURCE_INFEASIBLE"):
        bad.append("capacity.verdict 与三向判据不一致")
    if _feasible and (card.get("drc_lvs") or {}).get("drc_violations"):
        bad.append("容量判定为可行却仍有 DRC 违规 —— 检测器与几何脱节")
    if (not _feasible) and not (card.get("drc_lvs") or {}).get("drc_violations"):
        bad.append("容量判定为不可行却报 0 违规 —— 有一方在说谎")
    # 弯角孔包围修复的回归守卫（v0.9.370）：回退就必红
    if "via_enclosure" in ((card.get("drc_lvs") or {}).get("drc_by_rule") or {}):
        bad.append("via_enclosure 重新出现 —— 弯角延伸（_LAND_CORNER）被回退")

    # ── what-if 实验（放大面积换清零）：结论与数字必须互相咬住 ────────────
    ze = cap.get("zero_experiment") or {}
    if ze.get("verdict") == "DRC_ZERO_ACHIEVED" and ze.get("achieved_violations") != 0:
        bad.append("what-if 声称清零却仍有违规")
    if ze.get("verdict") == "STILL_VIOLATING" and ze.get("achieved_violations") == 0:
        bad.append("what-if 声称仍有违规却报 0")
    if ze.get("row_area_ratio", 0) <= ze.get("predicted_channel_ratio", 0):
        bad.append("清零实测面积比（%.2f×）≤ 通道下界（%.2f×）—— 不可能，数字被改过"
                   % (ze.get("row_area_ratio", 0), ze.get("predicted_channel_ratio", 0)))

    # 文字层面禁止签核/流片类宣称（防「披露写了一堆，结论仍吹」）
    claim = str(card.get("claim") or "")
    for bad_word in ("签核通过", "流片验证", "silicon proven", "signoff clean"):
        if bad_word in claim:
            bad.append("claim 含越界宣称：%s" % bad_word)
    return bad
