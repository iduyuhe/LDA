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
     `ddetail` 路由器在 c17 上实测 **DRC 87 处 min_spacing**（弯角孔包围 v0.9.370 已修至 0）
     ＋ **LVS 183 条短路条目**（78 `short` + 105 `short_via`，去重 **43 对网**）⇒ 卡片**如实报两类违规的分规则计数**，
     绝不写「clean」「pass」「signoff」。
  ② **不报未实现的段**：`synthesized=False`（入口就是门级网表）、`timing_included=True`
     （v0.9.377 接入，但 `hold_checked=False`、无时钟域 ⇒ `fmax=None`）
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
import copy
import threading
from typing import Any, Dict, List

CASE_ID = "D-B3-DIGITAL-TRUNK"
ENDPOINT = "/api/digital_demo"
#: 🔴 恒为「流程跑通」——**不是** ACCEPT / PASS / SIGNOFF。改这个字面量 ⇒ 自检必红。
VERDICT = "FLOW_RUN_NOT_SIGNOFF"

#: 声明本卡覆盖/未覆盖的段（机核用，禁止与实际行为不一致）
SEGMENTS_COVERED = ("parse", "place", "route", "drc_lvs", "timing", "em", "ec_b3", "thermal", "def_write")
SEGMENTS_MISSING = ("synthesis",)

#: 诚实边界（逐条都在卡片里输出，且被 selfcheck 要求非空 + 含关键词）
HONEST_NOTES = (
    "设计期流程跑通，非签核、非流片实测。",
    # 🔴 v0.9.376 主链切换：这条必须放最前，否则「DRC 0」会被读成全芯片清零。
    "主链 dpnr 只布 **4/11** 条网（7 条接 primary I/O 的网因端口未建模布不了）⇒ "
    "这 4 条网的 **DRC 0 / LVS 0** 是**子集结论**（scope=ROUTED_SUBSET_ONLY），"
    "不是全芯片清零；未检验的网逐条列在 drc_lvs.nets_uncovered。",
    "双报一版：旧链 detail_route 的数字并排在 baseline 段（布满 11 条网，但 DRC 87 处 "
    "min_spacing ＋ LVS 183 条短路条目 / 43 对网）—— 两条链都 claimable=False。",
    "主链切换的面积代价：die 3.401 → 33.696 µm²（×9.909），是 CELL_GAP 换引脚可达性的代价，"
    "**不是工艺升级**。",
    "旧链 ddetail 路由器 claimable=False：c17 实测 DRC 87 处 min_spacing（via_enclosure 已修至 0）"
    "＋ **LVS 183 条短路条目**（78 同层 short + 105 通孔 short_via，去重后 **43 对网**），"
    "本卡如实报数，不伪造 clean；余下违规是**容量不足**（capacity 段），不是路由器写错。",
    "DEF 只到 placed（routed_exported=False）—— ROUTED 子集写出器未实现，"
    "写 ROUTED 等于编造布线。",
    "synthesized=False（入口即门级网表）；timing_included=True 但 hold_checked=False"
    "（未做保持时间检查），且 c17 无时钟域 ⇒ t_clk_min/fmax 为 None（不是 0）；"
    "未布的 7 条网按 **0 线载**算 ⇒ 走这些网的路径**偏乐观**。",
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


def _unique_pairs(problems) -> int:
    """LVS 问题的**去重网对数**（`(rule, net_a, net_b, layer)` ⇒ 无序网对）。"""
    pairs = set()
    for it in problems or []:
        if isinstance(it, (list, tuple)) and len(it) >= 3:
            pairs.add(frozenset((str(it[1]), str(it[2]))))
    return len(pairs)


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


def _baseline_facts(b) -> Dict[str, Any]:
    """旧链 `detail_route` 的并排事实（**双报一版，一个数字都不许省**）。

    🔴 为什么必须留在卡片上：主链 c17 是「DRC 0 但只布 4/11 条网」，旧链是
    「布满 11 条网但 87 处间距 + 183 条短路条目」。只报任一边都能被读成
    「已经解决了」或「什么都没做」—— 两张一起才叫报表。
    """
    if not b:
        return {}
    dl = b.get("drc_lvs") or {}
    return {
        "chain": b.get("chain"),
        "placement": dict(b.get("place") or {}),
        "routing": dict(b.get("route") or {}),
        "drc_lvs": {
            "chain": dl.get("chain"),
            "drc_ok": dl.get("drc_ok"),
            "drc_violations": dl.get("drc_violations"),
            "drc_by_rule": dict(dl.get("drc_by_rule") or {}),
            "lvs_ok": dl.get("lvs_ok"),
            "lvs_problems": dl.get("lvs_problems"),
            "lvs_by_rule": dict(dl.get("lvs_by_rule") or {}),
            "lvs_unique_pairs": dl.get("lvs_unique_pairs"),
        },
        "def_bytes": b.get("def_bytes"),
        "claimable": bool(b.get("claimable")),
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
    # 🔴 B 系列主链的**网覆盖记账**（2026-11-04 审计：此前 7 条端口网被静默跳过、
    #    unrouted 返回空 ⇒ 「4 网 DRC 0」被误读成「11 网已清零」）。0.4ms。
    from lda_l2.ecore import dpnr as PN
    _rt = PN.route_block(nl, PN.place_real(nl))
    cap = dict(cap, dpnr_coverage=_rt["coverage"],
               dpnr_skipped_port_nets=_rt["skipped_port_nets"])
    # 🔴 B 系列主链的 LVS（v0.9.375 起可跑 —— 此前 pins 是 4 元组，run_lvs 直接 ValueError）。
    #    `ok` 只对本模块**实际布了线的网**成立（c17：4/11），故 scope 必须与结论同行。
    _lv = PN.lvs_scoped(_rt)
    cap = dict(cap, dpnr_lvs={k: v for k, v in _lv.items() if k != "problems"})
    # 🔴 what-if：按「可布线所需」放大后 DRC 能否归零（4ms；**不是**可签核版图）
    cap = dict(cap, zero_experiment=DD.drc_zero_experiment(nl))
    ms = (time.perf_counter() - t0) * 1000.0

    st = {name: payload for name, payload in report["stages"]}
    dl = report["drc_lvs_detail"]
    drc = dl["drc"]
    lvs = dl["lvs"]
    # 🔴 主链的 problems **列表**在 `drc_lvs_detail["problems"]`（列表不进 stages，省体积）；
    #    `drc_lvs_detail["lvs"]` 里带的是 `n_problems` / `by_rule` / `unique_pairs`。
    #    两者都要读：只读一处会在「非零」时静默报 0（本仓踩过同类：有违规却分规则为空）。
    _prob = dl.get("problems")
    _n_lvs = lvs.get("n_problems")
    if _n_lvs is None:
        _n_lvs = len(_prob or lvs.get("problems") or [])
    routed = st.get("route", {})
    placed = st.get("place", {})
    wrote = st.get("def_write", {})
    parsed = st.get("parse", {})
    tmg = st.get("timing", {})
    emd = st.get("em", {})
    b3d = st.get("ec_b3", {})
    thd = st.get("thermal", {})

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
        # 🔴 v0.9.376 主链切换：placement / routing / drc_lvs 现在描述 **dpnr**（B 系列 P&R），
        #    旧链 detail_route 的数字整体下沉到 `baseline` 块（双报一版，不得只留一边）。
        "chain": report.get("chain"),
        "placement": {
            "chain": placed.get("chain"),
            "cells": placed.get("cells"),
            "rows": placed.get("rows"),
            "cols": placed.get("cols"),
            "die_w_um": placed.get("die_w_um"),
            "die_h_um": placed.get("die_h_um"),
            "die_area_um2": placed.get("die_area_um2"),
            "cell_gap_um": placed.get("cell_gap_um"),
            "hpwl_um": placed.get("hpwl_um"),          # 主链不算 HPWL ⇒ None（旧链值见 baseline）
            # 🔴 v0.9.383 补透（`.382` 在 report 里就有值、卡片忘了带出来 ⇒ 线上是 null）：
            #    **无 pad 时的 die 尺寸/面积**是「pad 带 + I/O 落点」这笔面积代价的唯一基线，
            #    没有它，读者只能看到 60.84 µm² 而无法判断「为端口可布付了多少」。
            "die_w_um_noport": placed.get("die_w_um_noport"),
            "die_area_um2_noport": placed.get("die_area_um2_noport"),
            "ports": dict(placed.get("ports") or {}),
        },
        "routing": {
            "chain": routed.get("chain"),
            "shapes": routed.get("shapes"),
            "nets_with_segments": routed.get("nets_with_segments"),
            "nets_touched": routed.get("nets_touched"),
            "nets_skipped_port": routed.get("nets_skipped_port"),
            # 🔴 旧义 + 两个有区分力的拆分（v0.9.379）：真端口 vs 悬空网。
            "nets_skipped_true_port": routed.get("nets_skipped_true_port"),
            "nets_dangling": routed.get("nets_dangling"),
            "nets_failed": routed.get("nets_failed"),
            "all_routed": bool(routed.get("all_routed")),
            # 🔴 派生值（v0.9.378），不是常量 False
            "claimable": bool((report.get("claimability") or {}).get("claimable")),
        },
        "drc_lvs": {
            "chain": dl.get("chain"),
            "drc_ok": bool(drc.get("ok")),
            "drc_violations": len(drc.get("violations") or []),
            "drc_by_rule": _by_rule(drc.get("violations")),
            "lvs_ok": bool(lvs.get("ok")),
            "lvs_problems": _n_lvs,
            # 🔴 必须分类：旧链 183 全是**短路**（78 同层 short + 105 通孔 short_via），
            #    只报总数会让读者以为「只是间距紧」—— 那是连通性错误，不是余量不足。
            "lvs_by_rule": dict(lvs.get("by_rule") or _by_rule(_prob)),
            # 🔴 183 是**条目数**（同一条网对会被多段金属/多个通孔各报一次，且双向各报一次）
            #    ⇒ 去重后只有 **43 对网**。只报 183 会把"短路规模"夸大 4 倍。
            "lvs_unique_pairs": (lvs.get("unique_pairs")
                                 if lvs.get("unique_pairs") is not None
                                 else _unique_pairs(_prob)),
            # 🔴 **作用域必须与结论同行**：0 违规只对 nets_checked 成立。
            #    c17 主链只布 4/11 条网 ⇒ 这几行是「0 违规」能不能读的唯一依据。
            "scope": dl.get("scope") or lvs.get("scope"),
            "nets_checked": dl.get("nets_checked", lvs.get("nets_checked")),
            "nets_total": dl.get("nets_total", lvs.get("nets_total")),
            "nets_uncovered": list(dl.get("nets_uncovered") or lvs.get("nets_uncovered") or []),
            "claimable": bool((report.get("claimability") or {}).get("claimable")),
        },
        # 🔴 签核资格：条件 + 阻塞项 + 清单自检，全部来自实测推导
        "claimable": bool((report.get("claimability") or {}).get("claimable")),
        "claimability": dict(report.get("claimability") or {}),
        # 🔴 **M1 阶段出口判据**（v0.9.381 改口径）：已布网 DRC/LVS 干净 +
        #    **未布网逐条枚举归因** + 布通率显式披露。旧判据「全芯片干净」在本拓扑下
        #    不可达，要求它等于逼人把子集结论写成全芯片结论。
        #    ⚠️ 与 `claimable` 是**两件事**：本项达成 ≠ 可签核。
        "m1_exit": dict(st.get("m1_exit") or {}),
        "baseline": _baseline_facts(report.get("baseline")),
        "area_delta": dict(report.get("area_delta") or {}),
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
        # 🔴 时序段（v0.9.377）：线载来自**主链布线的带网形状**，拓扑序先排过。
        #   无时钟域 ⇒ t_clk_min / fmax 是 **None**（三态，不压扁成 0）。
        "timing": {
            "chain": tmg.get("chain"),
            "topo_sorted": bool(tmg.get("topo_sorted")),
            "nets_with_wire": tmg.get("nets_with_wire"),
            # 未布的网按 0 线载算 ⇒ 走这些网的路径**偏乐观**（必须显式列出）
            "nets_without_wire": tmg.get("nets_without_wire"),
            "total_wire_um": tmg.get("total_wire_um"),
            "total_wire_c_fF": tmg.get("total_wire_c_fF"),
            "comb_delay_ideal_ps": tmg.get("comb_delay_ideal_ps"),
            "comb_delay_wired_ps": tmg.get("comb_delay_wired_ps"),
            "t_clk_min_ps": tmg.get("t_clk_min_ps"),
            "fmax_mhz": tmg.get("fmax_mhz"),
            "n_dff": tmg.get("n_dff"),
            "clock_domains": tmg.get("clock_domains"),
            "hold_checked": bool(tmg.get("hold_checked")),
            "critical_path": list(tmg.get("critical_path") or []),
        },
        # 🔴 EM 逐网裕量（v0.9.387 · B2b）：**诊断段，不进 blocking**。
        #    之前 EM 只是 `dsignoff` 里的纯函数、主链从未给它电流 ⇒ 对外等于不存在。
        #    🔴 读数纪律：`n_fail=0` **只对 `n_nets_judged` 成立**（`scope` 同行给出）；
        #    无布线的网是**不可判**（`undecidable_nets`），不是「通过」。
        "em": dict(emd),
        "ec_b3": dict(b3d),
        "thermal": dict(thd),
        "segments_covered": list(SEGMENTS_COVERED),
        "segments_missing": list(SEGMENTS_MISSING),
        "synthesized": False,
        "timing_included": True,
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
    """组装只读卡片（微秒级：仅重组字典 + 算 digest）。

    🔴 **返回深拷贝**（v0.9.378）：`facts()` 是模块级缓存，早期实现里卡片的嵌套
    dict/list 与缓存**共享同一对象** ⇒ 调用方（测试、门禁、任何消费方）就地改一张卡
    会把缓存改坏，之后所有请求都读到被污染的数据。
    这是实测踩到的：门禁探针「删掉一条条件」后，下一次 `case_card()` 也少了那条。
    """
    f = copy.deepcopy(facts())
    card: Dict[str, Any] = {
        "endpoint": ENDPOINT,
        "case_id": CASE_ID,
        "claim": "用 LDA 跑通一条数字链干线：结构级 Verilog → 门级网表 → 布局 → 布线 → "
                 "DRC/LVS → DEF 写出，**每段断言吃的是上一段的输出**（守恒失败即 fail-closed）。",
        "verdict": VERDICT,
        "verdict_label": "设计期流程跑通（非签核 · 非流片实测）",
        "chain": f["chain"],
        "subject": f["subject"],
        "placement": f["placement"],
        "routing": f["routing"],
        "drc_lvs": f["drc_lvs"],
        # 🔴 双报一版（v0.9.376 主链切换）：旧链数字与面积代价必须同卡呈现
        "baseline": f["baseline"],
        "area_delta": f["area_delta"],
        "claimable": f["claimable"],
        "claimability": f["claimability"],
        "m1_exit": f["m1_exit"],
        "def_export": f["def_export"],
        "conservation_ok": f["conservation_ok"],
        "problems": f["problems"],
        "xcheck": f["xcheck"],
        "capacity": f["capacity"],
        "segments_covered": f["segments_covered"],
        "segments_missing": f["segments_missing"],
        "synthesized": f["synthesized"],
        "timing_included": f["timing_included"],
        "timing": f["timing"],
        "em": f["em"],
        "ec_b3": f["ec_b3"],
        "thermal": f["thermal"],
        "honest_note": list(HONEST_NOTES),
        "disclosure": {
            "thermal": ("本卡片**含热诊断段**（chain=dpnr，逐门功率与一维稳态热链温升谱见 `thermal`），但**不回灌 `t_c`**：EM 仍用 `T_REF_C=125°C` 假设，本段与 EM 未接线。`r_th` / `t_amb` / `alpha` / `f` 均为**假设或归一化占位**（非工艺认证）⇒ 只报带量纲的谱与不变式，**不报绝对温度结论、不判违规、不进签核 blocking**，`in_blocking=False`、`scope=DIAGNOSTIC_ONLY`。不含瞬态 `C_th`、封装/散热边界真值、3D 热耦合、热点极限判据；规则集自建教科书尺度、非 foundry PDK ⇒ 不作可制造性 / 可靠性 / 性能宣称。"),
            "ec_b3": ("本卡片**含几何/量纲诊断段**，且**含天线比几何代理**（`ratio_by_g` = 每网金属同层并集面积 / 栅面积代理量 g，逐口径语义见 `ec_b3` 的 `ratio_semantics`；**不含电荷积分、Fowler-Nordheim 隧穿与栅氧退化**），但 **DRC 规则集仍不含密度/天线规则**：本段不进 DRC、不进签核 blocking，`in_blocking=False`、`scope=DIAGNOSTIC_ONLY`，只报带量纲的谱与不变式，**不判违规、不构成可制造性或电气签核**。窗口 `n∈{1,2,4,8,16,32}` 是离散化尺度（die 仅 7.8 µm，远小于真实工艺窗口），四个分母口径均为代理量与假设、非工艺认证；不含 PDN、时钟树、via 许用电流、栅氧厚度、峰值 di/dt。"),
            "pdk": "非 foundry PDK（教科书尺度 INV/NAND2）",
            "signoff": "否 —— claimable 由六条实测条件推导（all_nets_routed / drc_zero / "
                       "lvs_zero / lvs_scope_full_chip / timing_included / hold_checked），"
                       "当前未满足，逐条见 claimability.blocking",
            "external_agreement": "未验证（本机无 OpenROAD/OpenSTA；不宣称一致）",
            "pin_names": "LDA 约定：输入取 dcell 引脚名，输出统一 z（非库真名）",
            "units": "DEF 1 DBU = 1 nm（UNITS DISTANCE MICRONS 1000）",
            "energy_metrics": "不报 TOPS / TOPS-W / fJ/op",
            "sovereignty": "C 级自主（纯标准库）；LLM 不进判决路径",
            # 🔴 v0.9.386：EM 此前**对外完全不可见** —— `dsignoff.B3_DISCLOSURE` 没有任何端点透出，
            #    于是「把隐藏假设变成明账」只发生在代码与 CHANGELOG 里，读者在 API 上读不到。
            #    🔴 v0.9.387（B2b）**主链接线了**：`db3_trunk` 现在 import `dsignoff` 并输出
            #       `em` 段 ⇒ 本句从「不含 EM 判决」必须改成「含 EM 诊断段」。
            #       这正是 S19c 存在的意义 —— 它当场会红，逼文案跟着事实走（不是靠人记得改）。
            #    这条文案的四处事实都必须可机核（s13 的 S19a–d / S20a–h）：
            #      ① 含 T_ref / Ea / n 三个参数名（否则读者不知道「假设」指什么）
            #      ② 倍数与 `j_max_at(85)/j_max_at(125)` 实测一致（不许手填一个数）
            #      ③ 「含/不含 EM」两个互斥措辞**恰好出现一个**，且与主链 AST 事实一致
            #      ④ 必须声明「不进 blocking」与「不可判≠通过」（A 方案的核心承诺）
            "em": ("本卡片**含 EM 诊断段**（chain=dpnr，逐网裕量见 `em`），但 **EM 不进签核 "
                   "blocking**：`claimable` 与 `m1_exit` 都不参考它。读数纪律："
                   "`em.n_fail=0` 只对 `em.n_nets_judged` 成立（scope=JUDGED_SUBSET_ONLY），"
                   "无布线的网是**不可判**、不是通过。假设集：J_max(T) 用 Black 温度标度，"
                   "T_ref=125°C / Ea=0.9 eV / n=1.1 均为假设（非工艺认证；基准若为 85°C，"
                   "允许值缩约 14×）；频率由组合延时反推（取半周期）、翻转率 α=0.1、"
                   "VDD 取 tech 默认值，同为假设。覆盖边界：只判有金属的信号网，"
                   "**不含电源/地网（PDN 未建模）、时钟树、via 许用电流、峰值 di/dt**；"
                   "c17 动态电流仅 µA 级 ⇒ 本判据在该设计上**不具备判别力**"
                   "（裕量量级见 `em.min_margin_x`，不要读成「EM 合格」）。"),
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
    # 🔴 v0.9.378：关键词从 `claimable=False` 改为 `claimable` —— 该常量已不存在
    #   （签核资格改为六条件派生）。仍要求提到它，只是不再钉死某个取值，
    #   否则条件成立的那天会与「必须写 False」自相矛盾。
    for kw in ("非流片实测", "claimable", "非 foundry PDK", "TOPS", "synthesized=False"):
        if kw not in blob:
            bad.append("honest_note 缺关键词：%s" % kw)
    if card.get("synthesized") is not False:
        bad.append("synthesized 必须为 False（入口即门级网表，未做综合）")
    # 🔴 v0.9.377 重锚：旧规则「timing_included 必须为 False」是「干线未串时序段」时代的写法。
    #   现在时序已接入，若仍禁止 True 就只能逼人把时序段删掉。新规则：允许 True，
    #   但**四条边界缺一必红**（它们正是这份时序「能说明什么、不能说明什么」的边界）。
    tmg = card.get("timing") or {}
    if card.get("timing_included") is not True:
        bad.append("timing_included 必须为 True（时序段已接入干线）")

    # 🔴 v0.9.381 新增：**M1 出口判据**的自检（改口径不许变成「少布就算过」）
    #   ① `ok=True` 时**不许**还有未归因网（否则「不可达就跳过」会悄悄成立）；
    #   ② 布通率必须与 `routing` 段**同源**（两处各写一份必然漂移）；
    #   ③ 归因原因必须落在枚举里（自由文本不是归因）；
    #   ④ **本判据达成 ≠ 可签核** ⇒ `m1_exit.ok=True` 而 `claimable` 也 True 时，
    #      必须能由六条条件解释（即六条真的全满足），否则就是两个布尔被混用。
    _m1 = card.get("m1_exit") or {}
    if not _m1:
        bad.append("m1_exit 段缺失 —— M1 出口判据不得静默消失")
    else:
        if _m1.get("ok") and _m1.get("unattributed"):
            bad.append("m1_exit.ok=True 但仍有未归因网 %r —— 归因不完备不得判过"
                       % (_m1.get("unattributed"),))
        if _m1.get("bad_reason"):
            bad.append("m1_exit 出现枚举外的归因原因：%r" % (_m1.get("bad_reason"),))
        _rout = card.get("routing") or {}
        if _m1.get("routed") != _rout.get("nets_with_segments"):
            bad.append("m1_exit.routed(%r) 与 routing.nets_with_segments(%r) 不同源"
                       % (_m1.get("routed"), _rout.get("nets_with_segments")))
        _tot = _m1.get("total")
        if _tot and _m1.get("routed") is not None and _tot > _m1["routed"] \
                and _m1.get("is_full_chip_routing"):
            bad.append("m1_exit.is_full_chip_routing 与 routed/total(%s/%d) 矛盾"
                       % (_m1.get("routed"), _tot))
        if _m1.get("ok") and card.get("claimable") is True:
            _cl = card.get("claimability") or {}
            if not _cl.get("claimable"):
                bad.append("m1_exit.ok=True ∧ claimable=True 但 claimability 六条未全满足 "
                           "—— 两个布尔被混用（阶段出口 ≠ 签核资格）")
    if not tmg:
        bad.append("timing 段缺席 —— 接入时序后不得省略")
    else:
        if tmg.get("hold_checked") is not False:
            bad.append("hold_checked 必须显式 False（未做保持时间检查）")
        if tmg.get("n_dff") == 0 and (tmg.get("fmax_mhz") is not None
                                      or tmg.get("t_clk_min_ps") is not None):
            bad.append("无时钟域（n_dff=0）却给出 Fmax/t_clk_min —— 不得凭空造时钟")
        if (tmg.get("comb_delay_wired_ps") is not None
                and tmg.get("comb_delay_ideal_ps") is not None
                and tmg["comb_delay_wired_ps"] < tmg["comb_delay_ideal_ps"] - 1e-9):
            bad.append("带线载延时 %.3f < 理想 %.3f —— 加负载不可能变快"
                       % (tmg["comb_delay_wired_ps"], tmg["comb_delay_ideal_ps"]))
        if tmg.get("nets_without_wire") is None:
            bad.append("nets_without_wire 未给出 —— 未布网按 0 线载，必须显式")
    de = card.get("def_export") or {}
    if de.get("routed_exported") is not False:
        bad.append("routed_exported 必须为 False（shapes 无网归属，不得写 ROUTED）")
    if de.get("roundtrip_ok") is not True:
        bad.append("DEF 往返双射未通过：roundtrip_ok=%r" % (de.get("roundtrip_ok"),))
    drc = card.get("drc_lvs") or {}
    # 🔴 v0.9.376 重锚：旧规则「drc_ok/lvs_ok 报 True 一律红」是旧主链时代的写法
    #   （旧链 detail_route 必然有 87/183 违规）。主链切到 dpnr 后，c17 的 4 条已布网
    #   **确实 0 违规** —— 禁止 True 会逼人报假数。
    #   新规则不是「允许 True」，而是「**不许出现无作用域的 True**」：
    #   · scope 必须显式（全芯片 or 子集）；
    #   · 不是全芯片时，nets_uncovered 必须非空 —— 否则「4/11 网 0 违规」会被读成
    #     「11 网已清零」，这正是审计当日抓到的失真。
    if drc.get("drc_ok") is True or drc.get("lvs_ok") is True:
        _scope = drc.get("scope")
        if _scope not in ("FULL_CHIP", "ROUTED_SUBSET_ONLY"):
            bad.append("drc_ok/lvs_ok 报 True 但 scope=%r 未显式 —— 0 违规必须带作用域"
                       % (_scope,))
        elif _scope != "FULL_CHIP" and not (drc.get("nets_uncovered") or []):
            bad.append("子集 0 违规（scope=%s）却未列 nets_uncovered —— "
                       "会被读成全芯片清零" % (_scope,))
        if drc.get("nets_checked") is None or drc.get("nets_total") is None:
            bad.append("0 违规却未给 nets_checked/nets_total —— 作用域不完整")
    if len(drc.get("drc_by_rule") or {}) == 0 and (drc.get("drc_violations") or 0) > 0:
        bad.append("有违规但分规则计数为空 —— 记账不完整")
    # LVS 分类纪律：183 是短路，不是「余量不足」；分类必须求和自洽
    _lv = drc.get("lvs_by_rule") or {}
    if sum(_lv.values()) != (drc.get("lvs_problems") or 0):
        bad.append("lvs_by_rule 求和 %d ≠ lvs_problems %d —— LVS 分类与总数不自洽"
                   % (sum(_lv.values()), drc.get("lvs_problems") or 0))
    # 🔴 v0.9.382 精修：**只有短路类问题**才要求 short/short_via 分类与网对去重。
    #    原规则假设「LVS 问题 = 短路」，而本版出现了另一类问题 ——
    #    `net_no_shapes` / `pin_not_reached`（**未布网**的形态），它们没有「网对」可言。
    #    拿原规则判 ⇒ 会把「3 条未布网问题」误判成「分类缺失」。
    #    ⇒ 判据按**问题类型**分流，两类各自成立，谁也不能顶替谁。
    _short_like = (_lv.get("short") or 0) + (_lv.get("short_via") or 0)
    _n_lv = drc.get("lvs_problems") or 0
    _has_short_type = _short_like > 0
    if _has_short_type and _short_like != _n_lv and not (
            _lv.get("net_no_shapes") or _lv.get("pin_not_reached")
            or _lv.get("net_disconnected")):
        bad.append("有 %d 处短路类 LVS 问题却未分类出 short/short_via —— 不得只说「有问题」"
                   % _n_lv)
    _u = drc.get("lvs_unique_pairs")
    if _has_short_type and not (_u or 0):
        bad.append("有短路类 LVS 问题却报 0 对网 —— 去重计数缺失")
    if _u is not None and _u > (drc.get("lvs_problems") or 0):
        bad.append("去重网对 %d > 条目数 %d —— 计数逻辑错" % (_u, drc.get("lvs_problems") or 0))
    # ── 旧链（baseline）的同类纪律：独立一套，不能只查主链 ────────────────
    #   🔴 v0.9.376 由 S7k 反向探针逼出来：此前自检只查 `card["drc_lvs"]`（现为主链，0 问题），
    #      于是「把旧链的 lvs_by_rule 改成 {'short': 1}」这种篡改**完全测不出来** ——
    #      旧链 183 条短路的分类质量就此失去守卫。两条链各查一遍才算守住。
    _b2 = card.get("baseline") or {}
    if not _b2:
        bad.append("baseline 缺席 —— 双报一版期间旧链数字不得静默消失")
    else:
        _bd = _b2.get("drc_lvs") or {}
        _bv = _bd.get("lvs_by_rule") or {}
        if sum(_bv.values()) != (_bd.get("lvs_problems") or 0):
            bad.append("旧链 lvs_by_rule 求和 %d ≠ lvs_problems %d"
                       % (sum(_bv.values()), _bd.get("lvs_problems") or 0))
        if (_bd.get("lvs_problems") or 0) > 0 and not (_bv.get("short") or _bv.get("short_via")):
            bad.append("旧链有 %d 处 LVS 问题却未分类出 short/short_via"
                       % (_bd.get("lvs_problems") or 0,))
        _bu = _bd.get("lvs_unique_pairs")
        if _bu is not None and _bu > (_bd.get("lvs_problems") or 0):
            bad.append("旧链去重网对 %d > 条目数 %d" % (_bu, _bd.get("lvs_problems") or 0))
        if len(_bd.get("drc_by_rule") or {}) == 0 and (_bd.get("drc_violations") or 0) > 0:
            bad.append("旧链有 DRC 违规但分规则为空")
        if _b2.get("chain") != "detail_route":
            bad.append("baseline.chain 必须是 detail_route（当前 %r）" % (_b2.get("chain"),))
        if _b2.get("claimable") is not False:
            bad.append("baseline.claimable 必须为 False（旧链有 87/183 违规 ⇒ 六条件必不成立）")
    # 双报一致性：主链标识 + 面积代价字段必须齐（面积差不许只给一边）
    if card.get("chain") != "dpnr":
        bad.append("card.chain 必须是 dpnr（当前 %r）" % (card.get("chain"),))
    _ad = card.get("area_delta") or {}
    if not _ad:
        bad.append("area_delta 缺席 —— 主链切换的面积代价不得省略")
    elif not (_ad.get("main_die_area_um2") and _ad.get("baseline_die_area_um2")):
        bad.append("area_delta 两侧面积必须都给：%r" % (_ad,))

    # ── 签核资格（v0.9.378）：claimable 必须由条件推导，缺一必 False ──────────
    _cl = card.get("claimability") or {}
    _conds = _cl.get("conditions") or {}
    _block = _cl.get("blocking")
    if not _cl:
        bad.append("claimability 缺席 —— claimable 不得再是常量")
    else:
        if _cl.get("condition_list_ok") is not True:
            bad.append("条件清单被改动（condition_list_ok=False）—— 六条缺一不可")
        # 🔴 数**实有条目**，不信自报的 `n_conditions` ——
        #   首版这里读 self-reported 计数，删掉一条条件时它仍是旧值 6 ⇒ 探针空转（已实测）。
        if len(_conds) != 6:
            bad.append("实有 %d 条条件 ≠ 6 —— 有条件被删/漏算" % len(_conds))
        if _cl.get("n_conditions") != len(_conds):
            bad.append("n_conditions=%r 与实有 %d 条不一致 —— 计数被手改"
                       % (_cl.get("n_conditions"), len(_conds)))
        _derived = all(_conds.get(k) is True for k in _conds) and len(_conds) == 6
        if card.get("claimable") is not _derived:
            bad.append("claimable=%r 与条件推导值 %r 不一致 —— 有人手改了结论"
                       % (card.get("claimable"), _derived))
        if card.get("claimable") is False and not _block:
            bad.append("claimable=False 却未给 blocking —— 不可签核必须说清卡在哪")
        # 🔴 blocking 必须**恰好**等于条件里为 False 的那些（多列/漏列都是手改痕迹）
        _expect_block = sorted(k for k, v in _conds.items() if v is not True)
        if sorted(_block or []) != _expect_block:
            bad.append("blocking=%r ≠ 实际未满足项 %r —— 阻塞清单与条件不一致"
                       % (sorted(_block or []), _expect_block))
        if card.get("claimable") is True and _block:
            bad.append("claimable=True 却仍有阻塞项 %r" % (_block,))
        # 与 drc_lvs / routing 分区必须同值（一个结论，不许出现两个）
        if (card.get("drc_lvs") or {}).get("claimable") is not card.get("claimable"):
            bad.append("drc_lvs.claimable 与顶层 claimable 不一致")
        if (card.get("routing") or {}).get("claimable") is not card.get("claimable"):
            bad.append("routing.claimable 与顶层 claimable 不一致")

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
    # 🔴 v0.9.376 重锚：`capacity` 是用 `dplac` 落点 + `ddetail` 路由器算出来的
    #   ⇒ 它描述的是 **baseline（旧链）** 的容量，**不是**主链 dpnr 的。
    #   旧写法拿它去比 `drc_lvs`（现已是主链）⇒ 跨链比较，两边都会被误判。
    #   现在显式取 baseline 的 DRC 违规数来对拍；baseline 缺席则不判（不静默通过，
    #   由「baseline 必须存在」的另一条规则兜）。
    _bl = card.get("baseline") or {}
    _bl_drc = (_bl.get("drc_lvs") or {}).get("drc_violations")
    if _bl_drc is not None:
        if _feasible and _bl_drc:
            bad.append("容量判定为可行却仍有 DRC 违规（旧链 %d）—— 检测器与几何脱节"
                       % _bl_drc)
        if (not _feasible) and not _bl_drc:
            bad.append("容量判定为不可行却报 0 违规（旧链）—— 有一方在说谎")
    # 弯角孔包围修复的回归守卫（v0.9.370）：回退就必红
    _bl_rule = ((_bl.get("drc_lvs") or {}).get("drc_by_rule") or {})
    if "via_enclosure" in _bl_rule:
        bad.append("via_enclosure 在旧链重新出现 —— 弯角延伸（_LAND_CORNER）被回退")

    # ── 网覆盖记账（B 系列主链）：没布的必须被看见，且两个布尔不许混用 ──────
    _cov = cap.get("dpnr_coverage") or {}
    if _cov:
        if _cov.get("routed", 0) + _cov.get("skipped_port", 0) + _cov.get("failed", 0) \
                != _cov.get("total", -1):
            bad.append("网覆盖四分类不闭合：%r" % (_cov,))
        if _cov.get("missing") or _cov.get("unknown"):
            bad.append("网覆盖有漏记/多记：missing=%r unknown=%r"
                       % (_cov.get("missing"), _cov.get("unknown")))
        if _cov.get("overlap"):
            bad.append("网覆盖有重复归类（四分类必须互斥）：%r" % (_cov.get("overlap"),))
        if _cov.get("all_routed") and _cov.get("skipped_port"):
            bad.append("all_routed=True 却有 %d 条端口未布 —— 谎报全布"
                       % _cov.get("skipped_port"))
        # complete（有归类）与 all_routed（真的全布）是两件事，卡片必须都能看到
        if "complete" not in _cov or "all_routed" not in _cov:
            bad.append("网覆盖缺 complete/all_routed 两字段 —— 两者不可合并")

    # ── 主链 LVS 的作用域纪律（v0.9.375）──────────────────────────────
    _lv = cap.get("dpnr_lvs") or {}
    if _lv:
        if _lv.get("nets_checked", 0) + len(_lv.get("nets_uncovered") or []) \
                != _lv.get("nets_total", -1):
            bad.append("LVS 覆盖数不闭合：checked %s + uncovered %s ≠ total %s"
                       % (_lv.get("nets_checked"), len(_lv.get("nets_uncovered") or []),
                          _lv.get("nets_total")))
        if _lv.get("ok") and not _lv.get("ok_is_full_chip"):
            # ok=True 是**子集**结论；只要 scope 不是 FULL_CHIP，就不许把它读成全芯片通过
            if _lv.get("scope") != "ROUTED_SUBSET_ONLY":
                bad.append("ok=True 且非全芯片，但 scope=%r —— 作用域必须显式"
                           % (_lv.get("scope"),))
        if _lv.get("ok_is_full_chip") and _lv.get("nets_uncovered"):
            bad.append("ok_is_full_chip=True 却有 %d 条网未覆盖 —— 谎报全芯片 LVS"
                       % len(_lv.get("nets_uncovered") or []))
        if sum((_lv.get("by_rule") or {}).values()) != _lv.get("n_problems", -1):
            bad.append("LVS by_rule 求和 ≠ n_problems")

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
