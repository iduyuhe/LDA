# -*- coding: utf-8 -*-
"""K0 结算审计生成器 —— 量子赛道一期未结项台账（机器可读 · 单一来源）。

用途（K 征程 · K0 硬前置 · 闭环缺口 G-K-1）
------------------------------------------------
把「量子赛道蓝图 v1（J1–J5）留下但未结清的三类项」——**债务（断口/账面空洞）·
平台（漂移风险/覆盖盲区）· 对外（交付欠账）**——落成**机器可读台账**，作为 K1–K6
各档的输入契约。

用法
----
    python scripts/k0_audit.py            # 打印 JSON 到 stdout（确定性 · 无时间戳）
    python scripts/k0_audit.py --write    # 写 lda/reports/k0_audit.json（LF 换行）

设计约束（对齐 LDA「受跟踪生成物」铁律）
----------------------------------------
* **零时间戳 / 零随机 / 零 git HEAD**：台账必须**逐字节可复现**，否则常驻门禁
  （`lda/run_k0_audit_smoke.py`）的「台账 ≡ 现算」对拍会在每次提交后假红。
  ⇒ 版本号 `version` **保留**（bump 时必须同步重生成，这是纪律不是噪声）；
    `head` **排除**（每次提交都变，属非确定量）。
* **证据全部现算**：grep 命中数、行号、函数值一律现场读取，**禁手写**。
* **写盘固定 `newline="\\n"`**（Windows 下防 CRLF 污染受跟踪产物）。

🔴 本模块**不改任何产品代码**（K0 为零代码审计档）；只读 + 生成台账。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))          # scripts/
_ROOT = os.path.dirname(_HERE)                              # 仓库根
_LDA = os.path.join(_ROOT, "lda")

if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

#: 🔴 落盘走仓内 **确定性唯一口径**（`det.write_text`：UTF-8 + LF + 末尾恰一换行）。
#:   注意**不用** `det.write_json` —— 后者经 `canon()` 会把 float 截到
#:   `SIGNIFICANT_DIGITS = 9` 位有效数字，而本台账需保留 `ratio_closed_form` 等
#:   全精度值（`run_k1_..._smoke` 的 B2 判据按 `1e-12` 比残差）⇒ 会被截断误红。
from lda_harness import deterministic as det  # noqa: E402

SCHEMA = "lda_k0_audit_v1"
OUT_REL = "lda/reports/k0_audit.json"


# ---------------------------------------------------------------------------
# 只读工具（全部现算 · 无副作用）
# ---------------------------------------------------------------------------
def _p(rel: str) -> str:
    return os.path.join(_ROOT, rel.replace("/", os.sep))


def _read(rel: str) -> str:
    try:
        with open(_p(rel), encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def _count(rel: str, needle: str) -> int:
    """子串命中数（文件缺失 ⇒ -1，与「命中 0」区分）。"""
    if not os.path.exists(_p(rel)):
        return -1
    return _read(rel).count(needle)


def _count_re(rel: str, pattern: str) -> int:
    if not os.path.exists(_p(rel)):
        return -1
    return len(re.findall(pattern, _read(rel)))


def _first_line(rel: str, needle: str):
    """首次出现的 1-based 行号；未命中 ⇒ None。"""
    for i, line in enumerate(_read(rel).splitlines(), 1):
        if needle in line:
            return i
    return None


def _exists(rel: str) -> bool:
    return os.path.exists(_p(rel))


def _anchor_keyword_hits(keys) -> dict:
    """**同源体检现算**：在 `BENCHMARK_DEFS` 的锚定义文本里逐锚搜关键词。

    返回 `{bid: [命中词...]}`（按 B 号数值升序）。用于 G-K-3 的「靶被谁占用」机器判定 ——
    🔴 证据**现算**，不手写命中清单（手写必过期）。
    """
    from lda_harness.benchmarks import BENCHMARK_DEFS, BENCHMARK_ORDER

    out = {}
    for bid in BENCHMARK_ORDER:
        e = BENCHMARK_DEFS.get(bid) or {}
        parts = []
        for k in ("title", "metric", "unit", "note", "candidate_desc",
                  "definition", "physical_law"):
            v = e.get(k)
            if isinstance(v, str):
                parts.append(v)
        blob = "\n".join(parts).lower()
        got = sorted({str(k) for k in keys if str(k).lower() in blob})
        if got:
            out[bid] = got
    return dict(sorted(out.items(),
                       key=lambda kv: int(re.sub(r"\D", "", kv[0]) or 0)))


# ---------------------------------------------------------------------------
# 冻结快照（审计相关稳定事实 · 排除 head）
# ---------------------------------------------------------------------------
def collect_snapshot() -> dict:
    from lda_harness.benchmarks import BENCHMARK_DEFS
    from lda_harness.benchmarks import _vmm_classify  # noqa: PLC2701 （权威分类单一来源）

    tiers = {"strict_independent": 0, "degraded": 0, "self_certified": 0}
    for _bid, defn in BENCHMARK_DEFS.items():
        t = defn.get("maturity_tier") or _vmm_classify(defn)
        tiers[t] = tiers.get(t, 0) + 1

    total = len(BENCHMARK_DEFS)
    strict = tiers["strict_independent"]

    # 端点：docs/api_reference.json（与 gen_api_reference.py 同一产物）
    try:
        with open(_p("docs/api_reference.json"), encoding="utf-8") as f:
            api = json.load(f)
        endpoints = len(api.get("endpoints", {}))
    except (OSError, ValueError):
        endpoints = -1

    # CI core 条数：run_ci_regression.CORE_SMOKES（权威定义）
    try:
        import run_ci_regression as R  # noqa: E402
        ci_core = len(R.CORE_SMOKES)
    except Exception:  # pragma: no cover （导入失败时如实标 -1，不掩盖）
        ci_core = -1

    # CASE_PANELS_MIN（run_webui_entry_smoke.py 现读）
    m = re.search(r"CASE_PANELS_MIN\s*=\s*(\d+)",
                  _read("lda/run_webui_entry_smoke.py"))
    case_panels_min = int(m.group(1)) if m else -1

    # 版本（pyproject 真源）
    vm = re.search(r'^version\s*=\s*"([^"]+)"',
                   _read("pyproject.toml"), re.M)
    version = vm.group(1) if vm else ""

    # 锚号上界（B 族 · 数值最大）
    bnums = []
    for bid in BENCHMARK_DEFS:
        mm = re.fullmatch(r"B(\d+)", bid)
        if mm:
            bnums.append(int(mm.group(1)))
    max_anchor = "B%d" % max(bnums) if bnums else ""

    panels = sorted(set(re.findall(r'id="(sec-[a-z0-9]+)"',
                                   _read("lda/lda_webui/static/index.html"))))

    return {
        "version": version,
        "ledger_total": total,
        "ledger_strict": strict,
        "ledger_degraded": tiers["degraded"],
        "ledger_stub": tiers["self_certified"],
        "independence_rate": round(strict / total, 6) if total else 0.0,
        "ci_core": ci_core,
        "endpoints": endpoints,
        "case_panels_min": case_panels_min,
        "max_anchor": max_anchor,
        "panels": panels,
    }


# ---------------------------------------------------------------------------
# 未结项条目（G-K-1…G-K-8 · 证据全部现算）
# ---------------------------------------------------------------------------
def collect_items() -> list:
    from lda_l2 import qs_m3c as M

    # ── G-K-2 证据：QS-M3c 两口径（现算 · K1 结算面） ──────────────────
    phys = M.design_qs_m3c()["physics"]
    cg = float(phys["cooperativity_g_form"])
    cqv = float(phys["cooperativity_qv_form"])
    ratio = (cg / cqv) if cqv else float("inf")
    _cal_set = M.cooperativity_calibers()
    # 消费侧（J5 M3 换能层）是否并报另一口径 —— 🔴 **结构化判据**（不靠散文）
    _consumer = "lda/lda_l2/qnet_transducer.py"
    _caliber_terms = ["口径", "约定", "convention", "2n", "8982", "8983"]
    consumer_caliber_hits = {t: _count(_consumer, t) for t in _caliber_terms}
    consumer_import_line = _first_line(_consumer, "from lda_l2.qs_m3c import")
    try:
        from lda_l2 import qnet_transducer as _TR
        _rep = _TR.transducer_report()
        consumer_disclosed = all(k in _rep for k in (
            "qs_m3c_cooperativity_g_form", "qs_m3c_cooperativity_qv_form",
            "qs_m3c_cooperativity_ratio", "qs_m3c_cooperativity_ratio_closed_form"))
    except Exception:  # pragma: no cover
        consumer_disclosed = False
    # 被订正的错误等式（断言两口径相等）· 纠正后必须 0 命中
    _wrong = ("4g²/(κγ_rad)=(3λ³Q/4π²V)(γ_rad/γ₁)",
              "4g²/(κγ_rad) = (3λ³Q/4π²V)(γ_rad/γ₁)")
    _wrong_files = ("lda/lda_l2/qs_m3c.py", "lda/run_qs_m3c_smoke.py",
                    "lda/lda_harness/_batch_qs_m3c_numeric.py",
                    "lda/lda_harness/benchmark_defs/part7.py")
    wrong_identity_hits = sum(_count(f, w) for f in _wrong_files for w in _wrong)

    # ── G-K-3 证据：B516/B517 是否入账 ───────────────────────────────────
    from lda_harness.benchmarks import BENCHMARK_DEFS, BENCHMARK_ORDER
    _order = set(BENCHMARK_ORDER)

    # ── G-K-4 证据：J1 面板/端点 ─────────────────────────────────────────
    _sech = "lda/lda_webui/static/index.html"
    _rout = "lda/lda_webui/routes.py"
    panel_hits = {
        "sec-j1": _count(_sech, 'id="sec-j1"'),
        "sec-j2": _count(_sech, 'id="sec-j2"'),
        "sec-j3": _count(_sech, 'id="sec-j3"'),
        "sec-j4": _count(_sech, 'id="sec-j4"'),
        "sec-j5": _count(_sech, 'id="sec-j5"'),
    }
    endpoint_hits = {
        "/api/j1_qec": _count(_rout, "/api/j1_qec"),
        "/api/j2_qpu": _count(_rout, "/api/j2_qpu"),
        "/api/j3_ctrl": _count(_rout, "/api/j3_ctrl"),
        "/api/j4_qs_system": _count(_rout, "/api/j4_qs_system"),
        "/api/j5_qnet": _count(_rout, "/api/j5_qnet"),
    }
    j1_case_exists = _exists("lda/lda_webui/j1_case.py")

    # ── G-K-5 证据：跨档复用站点（现算） ─────────────────────────────────
    reuse_sites = [
        {"from_module": "qs_m3c.cooperativity_from_g",
         "to_module": "qnet_transducer",
         "file": _consumer,
         "line": consumer_import_line,
         "style": "函数内 import"},
        {"from_module": "qs_m2.cpmg_filter",
         "to_module": "qnet_classical",
         "file": "lda/lda_l2/qnet_classical.py",
         "line": _first_line("lda/lda_l2/qnet_classical.py", "from lda_l2.qs_m2 import"),
         "style": "顶层 import"},
    ]
    reuse_table_exists = _exists("lda/reports/cross_stage_constants.json")

    # ── G-K-3 证据：B516/B517 终态（K2 同源体检裁决） ────────────────────
    _b516_keys = ("voigt", "缓冲气体", "碰撞展宽", "压致展宽", "doppler", "多普勒",
                  "气室", "谱线展宽", "fwhm", "hwhm", "卷积")
    _b517_keys = ("隔离度", "isolation", "隔离比", "寄生耦合", "parasitic", "s21",
                  "s21(f", "散射参数", "定向耦合", "微波-光")
    b516_hits = _anchor_keyword_hits(_b516_keys)
    b517_hits = _anchor_keyword_hits(_b517_keys)

    # ── G-K-6 证据：覆盖矩阵 ─────────────────────────────────────────────
    partial_matrix = "lda/run_anchor_coverage_matrix.py"
    partial_matrix_in_core = _count("lda/run_ci_regression.py",
                                    "run_anchor_coverage_matrix") > 0

    # ── G-K-7 证据：对外交付 ─────────────────────────────────────────────
    whitepaper_exists = _exists("docs/LDA_量子赛道蓝图v1_收官白皮书_2026-10-16.md")
    paper_exists = _exists("docs/LDA_量子赛道_J1-J5六层复利_论文.md")
    overview_hits = _count(_sech, 'id="sec-qtrack"')

    return [
        {
            "id": "G-K-1",
            "title": "一期未结项无机器可读台账（散落于技能记录与文档）",
            "type": "平台·可追溯",
            "owner_stage": "K0",
            "evidence": {
                "ledger_self": OUT_REL,
                "prior_human_docs": sorted(
                    ["docs/LDA_J5_量子网络与接口_征程总结_2026-10-16.md",
                     "docs/LDA_K_量子赛道一期结算与固化_可行性评估_架构定义_蓝图补丁_2026-10-16.md"]),
                "machine_readable_before": False,
            },
            "exit_criterion": ("台账文件存在 ∧ 台账 ≡ 现算（子进程重跑逐字节对拍）"
                               "∧ 反向探针（篡改台账侧必红）"),
            "status": "open",
        },
        {
            "id": "G-K-2",
            "title": "QS-M3c cooperativity 两口径断口**已结算**（K1）· 消费侧已并报",
            "type": "债务·断口",
            "owner_stage": "K1",
            "evidence": {
                "source": "lda_l2/qs_m3c.py · design_qs_m3c()['physics']（现算）",
                "cooperativity_g_form": cg,
                "cooperativity_qv_form": cqv,
                "ratio_g_over_qv": round(ratio, 3),
                "ratio_closed_form": _cal_set["ratio_closed_form"],
                "ratio_closed_form_expr": _cal_set["ratio_closed_form_expr"],
                "two_caliber_functions": {
                    "cooperativity_from_g": _first_line("lda/lda_l2/qs_m3c.py",
                                                        "def cooperativity_from_g"),
                    "cooperativity_from_qv": _first_line("lda/lda_l2/qs_m3c.py",
                                                         "def cooperativity_from_qv"),
                },
                "consumer_file": _consumer,
                "consumer_import_line": consumer_import_line,
                "consumer_caliber_term_hits": consumer_caliber_hits,
                "consumer_side_fulfilled": bool(consumer_disclosed),
                "wrong_identity_hits": int(wrong_identity_hits),
                "settled_by_stage": "K1",
                "settlement_surface": "lda_l2.qs_m3c.cooperativity_calibers()",
                "settlement_gate": "lda/run_k1_cooperativity_settlement_smoke.py",
                "registered_in_charter": "docs/LDA_J5_...md R3b（必须并报两口径）",
            },
            "exit_criterion": ("定主账口径 ∧ 并报另一口径（机读字段强制·缺字段即红）"
                               "∧「抹平断口必红」探针 ∧ 消费侧复核（防口径翻转打反既有判据）"),
            "status": "settled",
        },
        {
            "id": "G-K-3",
            "title": "B516/B517 预留编号**已裁决 reserved_null**（K2 同源体检）",
            "type": "债务·账面空洞",
            "owner_stage": "K2",
            "evidence": {
                "in_benchmark_defs": {b: (b in BENCHMARK_DEFS) for b in ("B516", "B517")},
                "in_benchmark_order": {b: (b in _order) for b in ("B516", "B517")},
                "reserve_registry": {
                    "file": "lda/run_count_consistency_smoke.py",
                    "line": _first_line("lda/run_count_consistency_smoke.py", "B516/B517"),
                },
                "j4_targets": {
                    "B516": "缓冲气体压致展宽线宽（Voigt 半宽）",
                    "B517": "片上微波-光寄生耦合隔离度",
                    "source": "docs/LDA_J4_...md",
                },
                "why_net_zero": "J4 M2 三重避让（1/|S21|² 与 B513 同格式 · 耦合模与 B14 同源 · √(1+X²) 与 B479 同量）",
                # 🔴 K2 同源体检（现算 · 证据不手写）：靶被哪些既有锚占用
                "adjudication": "K2（2026-10-17）· 真 grep 同源体检 ⇒ 两条均判 reserved_null",
                "b516_keyword_hits": b516_hits,
                "b516_verdict": "reserved_null",
                "b516_reason": ("Voigt 轮廓族已被 B197–B200 四锚占满（线心/远翼/洛伦兹主导/"
                                "深远翼 · 候选=卷积定义式数值积分）；B516 的靶（Voigt 半宽）"
                                "golden 与 candidate **两端都绕不开同一 Voigt 卷积** ⇒ "
                                "被测标量虽异（轮廓值 vs 半宽求根）但**方法学面不可区分**"),
                "b517_keyword_hits": b517_hits,
                "b517_verdict": "reserved_null",
                "b517_reason": ("靶 `I=1/|S21|²` 与 **B513**（`S=1/|S21(f_q)|²`）**同为该标量形式**、"
                                "候选同族（**ODE 数值积分**）；「耦合模」面另被 **B14** 占用 ⇒ "
                                "同源重复 ⇒ 不可区分"),
                "retarget_considered": ("曾评估改靶（B516→Dicke 窄化 / 压力展宽系数温度定标；"
                                        "B517→非互易隔离）⇒ 前者为**查表常量**或非闭式物理律，"
                                        "后者需磁光效应闭式（本档无）⇒ 如实不改靶"),
                "note": "🔴 reserved-null 是**终态裁决**（非法：把已被占用的靶再立一遍）；"
                        "`run_count_consistency_smoke` 的预留清单与此处一致（机器互证）",
            },
            "exit_criterion": ("同源体检（真 grep）后：可区分 ⇒ 按 lda-anchor-wiring 立靶；"
                               "不可区分 ⇒ 明示 reserved-null 并机器登记"),
            "status": "settled",
        },
        {
            "id": "G-K-4",
            "title": "J1（QEC）WebUI 面板/端点**已补齐**（K2 · 六层面板首次齐备）",
            "type": "平台·覆盖缺口",
            "owner_stage": "K2",
            "evidence": {
                "panel_hits": panel_hits,
                "endpoint_hits": endpoint_hits,
                "j1_case_py_exists": j1_case_exists,
                "case_panels_min": None,      # 由 snapshot 填（避免双来源）
                "note": ("🔴 K2（2026-10-17）**已补齐**：新增 `j1_case.py` + `GET /api/j1_qec` + "
                         "`index.html` `sec-j1` 三入口面 + `CASE_PANELS_MIN 15→16` ⇒ 六层面板首次齐备"
                         "（此前 A 档三入口面纪律只对新增强制 ⇒ J1 老档漏网）"),
                "settled_by_stage": "K2",
                "settlement_artifacts": [
                    "lda/lda_webui/j1_case.py",
                    "lda/run_webui_j1_render_path_smoke.py",
                    "lda/lda_webui/routes.py::h_j1_qec_demo",
                    "lda/lda_webui/static/index.html::sec-j1",
                ],
                "verdict": "closed",
            },
            "exit_criterion": ("j1_case.py + GET /api/j1_qec + index.html sec-j1 三入口面齐备"
                               "∧ CASE_PANELS_MIN 15→16 ∧ 渲染门禁（照抄 J5 骨架）"),
            "status": "settled",
        },
        {
            "id": "G-K-5",
            "title": "跨档复用常量无机器表 ⇒ 上游改档下游静默漂移",
            "type": "平台·漂移风险",
            "owner_stage": "K3",
            "evidence": {
                "reuse_sites": reuse_sites,
                "known_sites": len(reuse_sites),
                "table_exists": reuse_table_exists,
                "expected_table": "lda/reports/cross_stage_constants.json",
            },
            "exit_criterion": ("机器生成的跨档复用常量表 ∧ 常驻一致性判据（表 ≡ 现算）"
                               "∧ 反向探针（篡改上游原子必红）"),
            "status": "open",
        },
        {
            "id": "G-K-6",
            "title": "六层门禁覆盖矩阵未机器化（判据 × 锚 无下限棘轮）",
            "type": "平台·覆盖盲区",
            "owner_stage": "K4",
            "evidence": {
                "existing_partial": partial_matrix,
                "existing_partial_scope": "52 锚 × 33 类（T-9 · 2026-09-06 快照）",
                "existing_partial_in_core": partial_matrix_in_core,
                "current_ledger_total": None,   # 由 snapshot 填
                "note": "既有矩阵只覆盖 52 锚旧集且未入 CORE ⇒ 538 锚 × 判据 的覆盖矩阵仍缺",
            },
            "exit_criterion": ("538 锚「判据 × 锚」覆盖矩阵（机器生成）∧ 覆盖下限棘轮（只升不降）"
                               "∧ 盲区补判据"),
            "status": "open",
        },
        {
            "id": "G-K-7",
            "title": "一期对外交付欠账（白皮书 / 六层总览页 / 论文）",
            "type": "对外·交付欠账",
            "owner_stage": "K5",
            "evidence": {
                "whitepaper_exists": whitepaper_exists,
                "paper_exists": paper_exists,
                "overview_section_hits": overview_hits,
                "note": "对外口径只写「设计期签核 · 非流片实测」，不报能效/TOPS/fJ-op",
            },
            "exit_criterion": ("收官白皮书（docx/pdf）∧ WebUI 六层总览入口 ∧ 论文"
                               "（署名杜玉河 + 致谢 LDA 工程团队）"),
            "status": "open",
        },
        {
            "id": "G-K-8",
            "title": "蓝图 v2 缺口矩阵未起草（观察项 · 只起草不动实现）",
            "type": "观察项·奠基",
            "owner_stage": "K6",
            "evidence": {
                "blueprint_v1": "docs/LDA_量子赛道总蓝图_v1_2026-10-12.md（Layer 0–5 全收官）",
                "blueprint_v2_exists": _exists("docs/LDA_量子赛道总蓝图_v2_2026-10-16.md"),
                "new_domain_candidates": ["光-量异质集成（换能器 B522 已建）",
                                          "QEC 码族扩展（J1 只做表面码）",
                                          "容错编译（QEC ↔ QPU 联合）"],
            },
            "exit_criterion": "缺口矩阵 v2（人读 MD + 机器可读清单）· 新域落地须另出章程",
            "status": "open",
        },
    ]


# ---------------------------------------------------------------------------
# 组装
# ---------------------------------------------------------------------------
def collect() -> dict:
    snap = collect_snapshot()
    items = collect_items()
    # 单来源填值（避免双来源漂移）
    for it in items:
        if it["id"] == "G-K-4":
            it["evidence"]["case_panels_min"] = snap["case_panels_min"]
        if it["id"] == "G-K-6":
            it["evidence"]["current_ledger_total"] = snap["ledger_total"]
    return {
        "schema": SCHEMA,
        "generated_by": "scripts/k0_audit.py",
        "roadmap": "K（量子赛道一期结算与固化）",
        "subject": "量子赛道蓝图 v1（J1–J5）一期未结项",
        "excluded_fields": ["head（每次提交都变 ⇒ 非确定量，故意不入台账）"],
        "frozen_snapshot": snap,
        "items_total": len(items),
        "items_settled": sum(1 for it in items if it.get("status") == "settled"),
        "items": items,
    }


def dumps(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="K0 结算审计台账生成器")
    ap.add_argument("--write", action="store_true",
                    help="写 %s（LF）" % OUT_REL)
    args = ap.parse_args(argv)

    payload = collect()
    text = dumps(payload)
    if args.write:
        dest = _p(OUT_REL)
        det.write_text(dest, text)   # 确定性唯一口径：UTF-8 + LF + 末尾恰一换行
        print("[written] %s（%d 条未结项）" % (OUT_REL, payload["items_total"]))
    else:
        print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
