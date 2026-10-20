# -*- coding: utf-8 -*-
"""K 征程 · K0 结算审计 **常驻门禁**（量子赛道一期未结项台账 · 闭环缺口 G-K-1）。

判据分节（**判据数实跑现数**）：
  A 台账存在与 schema：文件存在 · 顶层字段齐备 · 条目数与 G-K-1…8 齐全 ·
    每条必需字段齐备 · owner_stage 覆盖 K0–K6
  B 快照 ≡ 现算：账本 total/strict/degraded/stub · 独立率 · CI core 条数 ·
    端点 · `CASE_PANELS_MIN` · 最高锚 · 面板清单（与 G-K-4 互证）
  C 受跟踪生成物三件套：**子进程重跑生成器 ≡ 磁盘台账（逐字节）** · 生成器幂等 · LF only
  D 反向探针（**先证能变红**）：篡改 `items_total` / 篡改某条 evidence /
    篡改快照字段 ⇒ 校验函数**必报红**（证明判据有鉴别力，非「恒绿空转」）
  E 证据现算对拍（G-K-2/3/4/5/7/8 的台账值 ≡ 现算）
  F 红线：零量子 SDK · 本门禁自身 ∈ `CORE_SMOKES`（自食其规则）

🔴 `main()` 返回「真值」而非恒 0（J4 血案：恒 `return 0` = 假绿）。
🔴 一律走 `smoke_kit.make_check`（助手单一来源棘轮 J3：禁自定义 `def check(`）。
🔴 本门禁**只读**产品代码 + 读台账；不改任何产品面（K0 为零代码审计档）。
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))          # lda/
_ROOT = os.path.dirname(_HERE)                              # 仓库根
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.benchmarks import BENCHMARK_DEFS, BENCHMARK_ORDER  # noqa: E402
from lda_harness.smoke_kit import make_check  # noqa: E402  # 助手单一来源（棘轮 J3）

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

_LEDGER = os.path.join(_ROOT, "lda", "reports", "k0_audit.json")
_GEN = os.path.join(_ROOT, "scripts", "k0_audit.py")
_EXPECT_IDS = ["G-K-%d" % i for i in range(1, 9)]
_REQUIRED_ITEM_KEYS = ("id", "title", "type", "owner_stage", "evidence",
                       "exit_criterion", "status")


def _load_gen():
    spec = importlib.util.spec_from_file_location("k0_audit", _GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GEN = _load_gen()


def _load_ledger():
    with open(_LEDGER, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 校验函数（供正向判据与反向探针共用 · 返回 名称 → bool）
# ---------------------------------------------------------------------------
def validate(led: dict, fresh: dict) -> dict:
    r = {}

    # ── A 台账存在与 schema ────────────────────────────────────────────
    r["A1 台账文件存在"] = os.path.exists(_LEDGER)
    r["A2 顶层字段齐备（schema/generated_by/roadmap/subject/frozen_snapshot/items）"] = all(
        k in led for k in ("schema", "generated_by", "roadmap", "subject",
                           "frozen_snapshot", "items", "items_total", "items_settled"))
    ids = [it.get("id") for it in led.get("items", [])]
    r["A3 条目数 8 且 items_total ≡ len(items)"] = (
        led.get("items_total") == 8 and len(led.get("items", [])) == 8)
    r["A4 缺口编号 G-K-1…8 齐全且无重复"] = sorted(ids) == sorted(_EXPECT_IDS)
    r["A5 每条必需字段齐备"] = all(
        all(k in it for k in _REQUIRED_ITEM_KEYS) for it in led.get("items", []))
    stages = {it.get("owner_stage") for it in led.get("items", [])}
    r["A6 owner_stage 覆盖 K0–K6（清偿→固化→对外→奠基）"] = stages == {
        "K0", "K1", "K2", "K3", "K4", "K5", "K6"}

    # ── B 快照 ≡ 现算 ─────────────────────────────────────────────────
    ls, fs = led.get("frozen_snapshot", {}), fresh.get("frozen_snapshot", {})
    r["B1 账本 total/strict/degraded/stub ≡ 现算"] = all(
        ls.get(k) == fs.get(k) for k in ("ledger_total", "ledger_strict",
                                         "ledger_degraded", "ledger_stub"))
    r["B2 独立率 ≡ 现算"] = ls.get("independence_rate") == fs.get("independence_rate")
    r["B3 CI core 条数 ≡ len(CORE_SMOKES)"] = ls.get("ci_core") == fs.get("ci_core")
    r["B4 端点 ≡ 现算"] = ls.get("endpoints") == fs.get("endpoints")
    r["B5 CASE_PANELS_MIN ≡ 现算"] = ls.get("case_panels_min") == fs.get("case_panels_min")
    r["B6 最高锚 ≡ 现算"] = ls.get("max_anchor") == fs.get("max_anchor")
    # 🔴 K2 补齐 J1 面板后语义翻转：旧判据曾断言面板清单「**不含** sec-j1」⇒ 已被打反。
    r["B7 面板清单 ≡ 现算（**含 sec-j1** · K2 已补齐 · 与 G-K-4 互证）"] = (
        ls.get("panels") == fs.get("panels") and "sec-j1" in ls.get("panels", []))

    # ── E 证据现算对拍 ────────────────────────────────────────────────
    by_id = {it.get("id"): it for it in led.get("items", [])}
    fe = {it.get("id"): it for it in fresh.get("items", [])}

    def ev(gid):
        return by_id.get(gid, {}).get("evidence", {})

    def fev(gid):
        return fe.get(gid, {}).get("evidence", {})

    e2, f2 = ev("G-K-2"), fev("G-K-2")
    r["E1 G-K-2 两口径值/函数行号 ≡ 现算"] = (
        e2.get("cooperativity_g_form") == f2.get("cooperativity_g_form")
        and e2.get("cooperativity_qv_form") == f2.get("cooperativity_qv_form")
        and e2.get("two_caliber_functions") == f2.get("two_caliber_functions"))
    # 🔴 K1 结算后语义翻转：旧判据曾断言「消费侧**未**并报（口径术语全 0）」——
    #   K1 兑现后该判据被**打反** ⇒ 必须改为「消费侧**已**并报（结构化字段）∧ 错误等式 0 命中」。
    r["E2 G-K-2 已结算：消费侧并报兑现 ∧ 错误等式 0 命中 ∧ items_settled 一致"] = (
        e2.get("consumer_side_fulfilled") is True
        and e2.get("wrong_identity_hits") == 0
        and f2.get("wrong_identity_hits") == 0
        and e2.get("settled_by_stage") == "K1"
        and e2.get("ratio_closed_form") == f2.get("ratio_closed_form")
        and e2.get("consumer_caliber_term_hits") == f2.get("consumer_caliber_term_hits")
        and led.get("items_settled") == 7)
    e3 = ev("G-K-3")
    r["E3 G-K-3 B516/B517 均不在账本 ∧ 终态=reserved_null ∧ 体检证据齐备"] = (
        e3.get("in_benchmark_defs") == {"B516": False, "B517": False}
        and e3.get("in_benchmark_order") == {"B516": False, "B517": False}
        and "B516" not in BENCHMARK_DEFS and "B517" not in BENCHMARK_DEFS
        and "B516" not in set(BENCHMARK_ORDER) and "B517" not in set(BENCHMARK_ORDER)
        and e3.get("b516_verdict") == "reserved_null"
        and e3.get("b517_verdict") == "reserved_null"
        and bool(e3.get("b516_reason")) and bool(e3.get("b517_reason"))
        # 同源体检命中面**现算**（证据不手写）：B197–B200 必须出现在 B516 命中表内
        and all(b in e3.get("b516_keyword_hits", {}) for b in ("B197", "B198", "B199", "B200"))
        and "B513" in e3.get("b517_keyword_hits", {}))
    e4, f4 = ev("G-K-4"), fev("G-K-4")
    # 🔴 K2 补齐后语义翻转：旧判据曾断言「sec-j1 **缺位** ∧ j1_case 不存在」⇒ 已被打反。
    # 🔴 K5 加了 sec-qtrack ⇒ 面板数 16→17；判据改为**下限棘轮语义**（≥16，只增不减）。
    r["E4 G-K-4 **已补齐**：sec-j1 齐备 ∧ J2–J5 齐备 ∧ j1_case 存在 ∧ CASE_PANELS_MIN ≥ 16"] = (
        e4.get("panel_hits") == f4.get("panel_hits")
        and e4.get("endpoint_hits") == f4.get("endpoint_hits")
        and all(e4.get("panel_hits", {}).get(k, 0) >= 1
                for k in ("sec-j1", "sec-j2", "sec-j3", "sec-j4", "sec-j5"))
        and e4.get("j1_case_py_exists") is True
        and e4.get("verdict") == "closed"
        and e4.get("settled_by_stage") == "K2"
        and (f4.get("case_panels_min") or 0) >= 16)
    e5, f5 = ev("G-K-5"), fev("G-K-5")
    # 🔴 K3 建表后语义翻转：旧判据曾断言「**常量表不存在**」⇒ 已被打反（第 3 例 Step-5）。
    r["E5 G-K-5 **已结算**：表存在 ∧ 站点 ≥2 ∧ 行号现算 ∧ 表内规模自洽"] = (
        e5.get("reuse_sites") == f5.get("reuse_sites")
        and len(e5.get("reuse_sites", [])) >= 2
        and all(s.get("line") for s in e5.get("reuse_sites", []))
        and e5.get("table_exists") is True
        and f5.get("table_exists") is True
        and (f5.get("table_summary") or {}).get("sites_total", 0) >= 2
        and (f5.get("table_summary") or {}).get("sites_cross_stage", 0) >= 2
        and e5.get("table_summary") == f5.get("table_summary"))
    e7 = ev("G-K-7")
    # 🔴 K5 交付后语义翻转：旧判据曾断言「白皮书/论文/总览入口**均缺**」⇒ 已被打反（第 5 例 Step-5）。
    r["E6 G-K-7 **已交付**：白皮书 ∧ 论文 ∧ 总览面板 ∧ 渲染门禁存在"] = (
        e7.get("whitepaper_exists") is True and e7.get("paper_exists") is True
        and e7.get("overview_section_hits") >= 1
        and e7.get("overview_panel") == "sec-qtrack"
        and e7.get("overview_endpoint") == "/api/qtrack"
        and e7.get("overview_gate_exists") is True)
    # 🔴 K4 关门后补建：G-K-6 此前**无对应判据**（台账有条目、门禁无判据 = 覆盖盲区本身）
    e6, f6 = ev("G-K-6"), fev("G-K-6")
    _m6 = f6.get("matrix_summary") or {}
    _r6 = f6.get("matrix_ratchet") or {}
    r["E8 G-K-6 **已结算**：矩阵存在 ∧ 三层覆盖自洽 ∧ ratchet ≥ 硬编码下限 ∧ 锚键集 ≡ 账本"] = (
        e6.get("matrix_summary") == f6.get("matrix_summary")
        and e6.get("matrix_ratchet") == f6.get("matrix_ratchet")
        and _m6.get("anchors_total") == len(BENCHMARK_DEFS)
        and _m6.get("l1_unified_covered") == _m6.get("anchors_total")
        and (_m6.get("l2_bespoke_covered") or 0)
            + (_m6.get("l2_blind") or 0) == _m6.get("anchors_total")
        and int(_r6.get("l2_min", 0)) >= 520
        and int(_r6.get("l3_min", 0)) >= 65)
    e8 = ev("G-K-8")
    # 🔴 K6 起草后语义翻转：旧判据曾断言「蓝图 v2 **不存在**」⇒ 已被草案打反（第 6 例 Step-5）。
    r["E7 G-K-8 **已起草**：v2 草案存在 ∧ 机器可读矩阵 ∧ status=draft_only"] = (
        e8.get("blueprint_v2_exists") is True
        and e8.get("blueprint_v2_status", "").startswith("draft_only")
        and e8.get("blueprint_v2_matrix") == "lda/reports/blueprint_v2_gap_matrix.json"
        and e8.get("blueprint_v2_generator") == "scripts/k6_blueprint_v2.py")
    return r


def main() -> int:
    fresh = GEN.collect()

    print("[A] 台账存在与 schema")
    led = _load_ledger()
    res = validate(led, fresh)

    # 逐条按声明顺序打印（避免依赖 dict 顺序）
    def emit(names, detail_fn=None):
        for n in names:
            ok = res.get(n, False)
            d = detail_fn(n) if detail_fn else None
            check(n, ok, d)

    emit(["A1 台账文件存在",
          "A2 顶层字段齐备（schema/generated_by/roadmap/subject/frozen_snapshot/items）",
          "A3 条目数 8 且 items_total ≡ len(items)",
          "A4 缺口编号 G-K-1…8 齐全且无重复",
          "A5 每条必需字段齐备",
          "A6 owner_stage 覆盖 K0–K6（清偿→固化→对外→奠基）"])

    print("\n[B] 冻结快照 ≡ 现算")
    fs = fresh["frozen_snapshot"]
    emit(["B1 账本 total/strict/degraded/stub ≡ 现算",
          "B2 独立率 ≡ 现算",
          "B3 CI core 条数 ≡ len(CORE_SMOKES)",
          "B4 端点 ≡ 现算",
          "B5 CASE_PANELS_MIN ≡ 现算",
          "B6 最高锚 ≡ 现算",
          "B7 面板清单 ≡ 现算（**含 sec-j1** · K2 已补齐 · 与 G-K-4 互证）"],
         detail_fn=lambda n: ("ledger %d/%d/%d/%d · rate=%s · ci_core=%d · eps=%d · cpm=%d · max=%s"
                              % (fs["ledger_total"], fs["ledger_strict"], fs["ledger_degraded"],
                                 fs["ledger_stub"], fs["independence_rate"], fs["ci_core"],
                                 fs["endpoints"], fs["case_panels_min"], fs["max_anchor"])))

    print("\n[C] 受跟踪生成物三件套")
    r1 = subprocess.run([sys.executable, _GEN], capture_output=True, text=True,
                        cwd=_ROOT, timeout=300)
    r2 = subprocess.run([sys.executable, _GEN], capture_output=True, text=True,
                        cwd=_ROOT, timeout=300)
    with open(_LEDGER, encoding="utf-8", newline="") as f:
        disk = f.read()
    check("C1 子进程重跑生成器 ≡ 磁盘台账（逐字节）", r1.returncode == 0 and r1.stdout == disk,
          "rc=%d · len(gen)=%d vs len(ledger)=%d" % (r1.returncode, len(r1.stdout), len(disk)))
    check("C2 生成器幂等（两次重跑一致）", r1.stdout == r2.stdout,
          "len=%d vs %d" % (len(r1.stdout), len(r2.stdout)))
    check("C3 台账 LF only（无 CRLF 污染）", "\r\n" not in disk and "\r" not in disk,
          "crlf=%d" % disk.count("\r\n"))

    print("\n[D] 反向探针（先证能变红）")
    t1 = json.loads(json.dumps(led))
    t1["items_total"] = 7
    check("D1 篡改 items_total ⇒ 校验必红（判据 A3 有鉴别力）",
          not validate(t1, fresh)["A3 条目数 8 且 items_total ≡ len(items)"],
          "篡改后 A3=%s" % validate(t1, fresh)["A3 条目数 8 且 items_total ≡ len(items)"])
    t2 = json.loads(json.dumps(led))
    for it in t2["items"]:
        if it["id"] == "G-K-2":
            it["evidence"]["cooperativity_qv_form"] = 1.0
    check("D2 篡改 G-K-2 evidence ⇒ 校验必红（判据 E1 有鉴别力）",
          not validate(t2, fresh)["E1 G-K-2 两口径值/函数行号 ≡ 现算"],
          "篡改后 E1=%s" % validate(t2, fresh)["E1 G-K-2 两口径值/函数行号 ≡ 现算"])
    t3 = json.loads(json.dumps(led))
    t3["frozen_snapshot"]["ledger_total"] = 999
    check("D3 篡改快照字段 ⇒ 校验必红（判据 B1 有鉴别力）",
          not validate(t3, fresh)["B1 账本 total/strict/degraded/stub ≡ 现算"],
          "篡改后 B1=%s" % validate(t3, fresh)["B1 账本 total/strict/degraded/stub ≡ 现算"])

    print("\n[E] 证据现算对拍（G-K-2/3/4/5/7/8）")
    emit(["E1 G-K-2 两口径值/函数行号 ≡ 现算",
          "E2 G-K-2 已结算：消费侧并报兑现 ∧ 错误等式 0 命中 ∧ items_settled 一致",
          "E3 G-K-3 B516/B517 均不在账本 ∧ 终态=reserved_null ∧ 体检证据齐备",
          "E4 G-K-4 **已补齐**：sec-j1 齐备 ∧ J2–J5 齐备 ∧ j1_case 存在 ∧ CASE_PANELS_MIN ≥ 16",
          "E5 G-K-5 **已结算**：表存在 ∧ 站点 ≥2 ∧ 行号现算 ∧ 表内规模自洽",
          "E6 G-K-7 **已交付**：白皮书 ∧ 论文 ∧ 总览面板 ∧ 渲染门禁存在",
          "E7 G-K-8 **已起草**：v2 草案存在 ∧ 机器可读矩阵 ∧ status=draft_only",
          "E8 G-K-6 **已结算**：矩阵存在 ∧ 三层覆盖自洽 ∧ ratchet ≥ 硬编码下限 ∧ 锚键集 ≡ 账本"])

    print("\n[F] 红线")
    src = ""
    for fn in ("scripts/k0_audit.py", "lda/run_k0_audit_smoke.py"):
        p = os.path.join(_ROOT, fn)
        if os.path.exists(p):
            src += open(p, encoding="utf-8").read()
    sdk = [s for s in ("qiskit", "cirq", "pennylane", "qutip") if ("import " + s) in src]
    check("F1 主权边界：零量子 SDK（不依赖 Qiskit/Cirq/PennyLane/QuTiP）",
          not sdk, "命中=%s" % (sdk or "无"))
    try:
        import run_ci_regression as R
        in_core = os.path.basename(__file__) in R.CORE_SMOKES
    except Exception as ex:  # pragma: no cover
        in_core = False
        print("    （无法读取 CORE_SMOKES：%s）" % ex)
    check("F2 本门禁自身 ∈ CORE_SMOKES（自食其规则）", in_core,
          "in_core=%s" % in_core)

    bad = globals().get("FAIL", 0)
    print("\n" + "=" * 78)
    print("K0 审计门禁：%s（FAIL=%d）" % ("ALL PASS" if bad == 0 else "有红色", bad))
    print("=" * 78)
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
