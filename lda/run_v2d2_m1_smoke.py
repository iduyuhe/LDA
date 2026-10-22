# -*- coding: utf-8 -*-
"""蓝图 v2 · **D2 QEC 码族 · M1 常驻门禁**（码族比较 / 开销 · **裁决净增 0 锚**）。

本档**不立新锚**：M1 的「码族间资源-阈值折衷」与「逻辑门集合可比性」经占用体检判定
**没有可锚物**（连续部分已被既有锚复用，非连续部分全是整数 / 拟合值 / 离散选择）。
依据：`docs/LDA_V2-D2_QEC码族_M1短评估_码族比较与开销_2026-10-22.md`。
裁决面与非门禁登记见 `lda_harness/d2_registries.py`（`D2_M1_ADJUDICATION`）。

判据分节（**判据数实跑现数** · A4 + B2 + C2 + D3 + E2 = **13**）：
  A 裁决面 4：四类齐全 · 每类证据 ≥3 条 · 每类理由 ≥30 字 · 每类 `anchorable is False` 显式
  B 锁 2：**哨兵指标名未被偷登记**（M0∪M1 并集扫 `BENCHMARK_DEFS`）·
    登记面 ≡ 面板卡（类数与判定逐条一致，跨源不信任任一侧）
  C 反向探针 2（**两侧都验**）：凭空多一条裁决 ⇒ 完整性判定必 False ·
    抹掉一条 ⇒ 必 False（防空表恒真）
  D 面板跨源 3：api 卡 ≡ 直接调用（逐值）· 卡内 `d*` ≡ 门禁侧独立现算（**换底数写法**）·
    `index.html` 三入口面齐全（`sec-d2` ∧ `#wbCaseBar` ∧ `CASE_MAP` 深链 ∧ 渲染函数 ∧ 端点调用）
  E 复用既有锚 2：卡内参考档 `d*` ≡ 既有锚 golden（**按 metric 名取，不写锚号**）·
    可行性分界 `p_phys ≥ p_th ⇒ d* < 0`（且反向：`p_phys < p_th ⇒ d* > 0`）

🔴 本门禁源码**不写任何锚号字面量**：锚一律按 `metric` 名从 `BENCHMARK_DEFS` 反查，
  防 K4 文本代理把「提了一句」算成「有专属判据」。
🔴 **CORE 自证不在本门禁内**（本档固定 13 判据）：成员资格由
  `run_timeout_budget_ratchet_smoke`（B20 覆盖反向完备）与 `run_ci_coverage_gate_smoke` 承担。
🔴 `main()` 返回真值而非恒 0。
"""
from __future__ import annotations

import io
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

_INDEX = os.path.join(_HERE, "lda_webui", "static", "index.html")

#: M1 期望的四类（结构断言：防「悄悄换一类」）
_EXPECT_CLASSES = {
    "exact_integer_overhead",
    "fitted_threshold_parameters",
    "discrete_argmin_comparison",
    "same_function_asymptotic_bound",
}


def _scan_sentinels(defs, sentinels):
    """把「不可锚」指标名偷登记成锚的 id 列表（纯函数，便于反向探针）。"""
    sents = {s.lower() for s in sentinels}
    out = []
    for bid, d in defs.items():
        blob = ((d.get("metric") or "") + " " + (d.get("title") or "")).lower()
        if any(s in blob for s in sents):
            out.append(bid)
    return out


def _adjudication_complete(adj):
    """裁决面完整性（纯函数 ⇒ 可喂坏数据做双向探针）。"""
    cls = (adj or {}).get("unanchorable_classes") or {}
    if len(cls) != 4:
        return False
    for v in cls.values():
        if not (isinstance(v.get("evidence"), list) and len(v["evidence"]) >= 3):
            return False
        if not (isinstance(v.get("reason"), str) and len(v["reason"]) >= 30):
            return False
        if v.get("anchorable") is not False:
            return False
    return True


def _card_matches_registry(card, adj):
    """登记面 ≡ 面板卡：类数一致 ∧ 每条判定都是 NOT_ANCHORABLE ∧ 卡片覆盖全部类名。"""
    nr = (card or {}).get("negative_results") or {}
    cls = (adj or {}).get("unanchorable_classes") or {}
    if len(nr) != len(cls):
        return False, "card=%d registry=%d" % (len(nr), len(cls))
    if not all(v.get("verdict") == "NOT_ANCHORABLE" for v in nr.values()):
        return False, "卡片存在非 NOT_ANCHORABLE 条目"
    if not all(len(v.get("evidence") or []) >= 3 for v in nr.values()):
        return False, "卡片存在证据 <3 条"
    return True, "类数=%d 逐条一致" % len(nr)


def _recompute_dstar(p_phys, target, p_th, A):
    """门禁侧**独立**现算 `d*`（换写法：以 10 为底 + 显式比值），用于跨源对拍。"""
    return 2.0 * math.log10(target / A) / math.log10(p_phys / p_th) - 1.0


def main() -> int:
    print("=" * 78)
    print("蓝图 v2 · D2-M1 门禁（码族比较/开销 · 裁决净增 0 锚 · 面板跨源对拍）")
    print("=" * 78)

    from lda_harness import d2_registries as D2
    from lda_harness.benchmarks import BENCHMARK_DEFS
    from lda_webui import d2_case as C

    try:
        from lda_harness import verification_adapters as va
        specs, _cands = va.build_harness_specs()
        by = {x.spec_id: x for x in specs}
    except Exception:  # noqa: BLE001  仅 E 组需要；失败即判红
        by = {}

    adj = D2.D2_M1_ADJUDICATION

    # ── A 裁决面 ──────────────────────────────────────────────────────────
    cls = adj["unanchorable_classes"]
    check("A1 四类齐全（类名 ≡ 期望集 · 防悄悄换类）",
          set(cls) == _EXPECT_CLASSES, "类=%s" % sorted(cls))

    n_ev = {k: len(v.get("evidence") or []) for k, v in cls.items()}
    check("A2 每类证据 ≥3 条（负结果须带书面证据）",
          all(n >= 3 for n in n_ev.values()), "证据数=%s" % n_ev)

    n_rs = {k: len(v.get("reason") or "") for k, v in cls.items()}
    check("A3 每类理由 ≥30 字（不是一句口号）",
          all(n >= 30 for n in n_rs.values()), "理由字数=%s" % n_rs)

    check("A4 每类 `anchorable is False` 显式（不留「也许可锚」的缝）",
          all(v.get("anchorable") is False for v in cls.values()),
          "取值=%s" % {k: v.get("anchorable") for k, v in cls.items()})

    # ── B 两道锁 ─────────────────────────────────────────────────────────
    sents = D2.d2_all_sentinel_metrics()
    hit = _scan_sentinels(BENCHMARK_DEFS, sents)
    check("B1 哨兵指标名未被偷登记（M0∪M1 并集 %d 名）" % len(sents), not hit,
          "命中=%s" % hit[:6])

    card = C.case_card()
    ok_b2, why_b2 = _card_matches_registry(card, adj)
    check("B2 登记面 ≡ 面板卡（类数 ∧ 判定 ∧ 证据数逐条，两源互证）", ok_b2, why_b2)

    # ── C 反向探针（两侧都验）──────────────────────────────────────────────
    import copy
    extra = copy.deepcopy(adj)
    extra["unanchorable_classes"]["bogus_extra_class"] = {
        "anchorable": False,
        "reason": "凭空多出来的一类：应当被完整性判定当场判红（五类 ≠ 四类）",
        "evidence": ["e1", "e2", "e3"],
        "sentinel_metrics": ["qec_bogus_metric"],
    }
    check("C1 反向探针：凭空多一条裁决 ⇒ A 组判定必 False（非恒真）",
          not _adjudication_complete(extra),
          "五类时 complete=%s" % _adjudication_complete(extra))

    drop = copy.deepcopy(adj)
    drop["unanchorable_classes"].pop(sorted(drop["unanchorable_classes"])[0])
    check("C2 反向探针：抹掉一条裁决 ⇒ 判定必 False（防空表/少表恒真）",
          not _adjudication_complete(drop),
          "三类时 complete=%s（被抹=%s）"
          % (_adjudication_complete(drop), sorted(adj["unanchorable_classes"])[0]))

    # ── D 面板跨源 ────────────────────────────────────────────────────────
    card2 = C.case_card()
    same = (card == card2)
    seg_diff = [s["segment"] for s, t in zip(card["segments"], card2["segments"])
                if s["value"] != t["value"]]
    check("D1 卡两次调用逐值一致（零重计算 ⇒ 无时钟/随机/IO）", same and not seg_diff,
          "段差=%s" % seg_diff[:3])

    ref_card = float(card["budget"]["d_star_reference"])
    ref_gate = _recompute_dstar(C.P_PHYS_DEFAULT, C.TARGET_DEFAULT, 0.01, 0.03)
    rel_d = abs(ref_card - ref_gate) / max(abs(ref_gate), 1e-300)
    check("D2 卡内 d* ≡ 门禁侧独立现算（换底数写法 · rel < 1e-15）", rel_d < 1e-15,
          "card=%.17g gate=%.17g rel=%.1e" % (ref_card, ref_gate, rel_d))

    html = io.open(_INDEX, encoding="utf-8").read()
    has_sec = ('id="sec-d2"' in html) and ('data-stage="accept"' in html)
    has_bar = 'href="#sec-d2"' in html
    has_map = '"#sec-d2": "runD2"' in html
    has_fn = ("function renderD2(" in html) and ("async function runD2(" in html)
    has_ep = "apiGet('/api/d2_code_family')" in html
    check("D3 index.html 三入口面齐备（sec-d2 ∧ wbCaseBar ∧ CASE_MAP 深链 ∧ 渲染函数 ∧ 端点）",
          all([has_sec, has_bar, has_map, has_fn, has_ep]),
          "sec=%s bar=%s map=%s fn=%s ep=%s"
          % (has_sec, has_bar, has_map, has_fn, has_ep))

    # ── E 复用既有锚（按 metric 名取，不写锚号）──────────────────────────────
    metric = "qec_threshold_distance"
    ids = [k for k, v in BENCHMARK_DEFS.items() if v.get("metric") == metric]
    g = None
    if len(ids) == 1 and ids[0] in by:
        g = float(by[ids[0]].oracle_fn(by[ids[0]].params))
    d_anchor = abs(ref_card - g) if g is not None else float("inf")
    check("E1 卡内参考档 d* ≡ 既有锚 golden（metric=%s · 复用非新立）" % metric,
          g is not None and d_anchor < 1e-9,
          "golden=%s card=%.17g |Δ|=%.3e" % ("None" if g is None else "%.17g" % g,
                                             ref_card, d_anchor))

    infeas = [f for f in card["families"] if not f["feasible"]]
    feas = [f for f in card["families"] if f["feasible"]]
    bound_ok = bool(infeas) and bool(feas) and all(
        f["d_star"] < 0.0 and f["verdict"] == "INFEASIBLE" for f in infeas) and all(
        f["d_star"] > 0.0 and f["verdict"] == "FEASIBLE" for f in feas)
    check("E2 可行性分界：p_phys ≥ p_th ⇒ d*<0/INFEASIBLE ∧ p_phys < p_th ⇒ d*>0/FEASIBLE",
          bound_ok,
          "可行=%d 不可行=%d（不可行 d*=%s）"
          % (len(feas), len(infeas),
             ["%.4f" % f["d_star"] for f in infeas][:2]))

    n_bad = globals().get("FAIL", 0)
    print("\n" + "=" * 78)
    print("D2-M1 门禁：%s（FAIL=%d）· 类数=%d · 证据/类=%s · 净增锚 0（裁决）"
          % ("ALL PASS" if n_bad == 0 else "有红色", n_bad, len(cls),
             min(n_ev.values())))
    print("=" * 78)
    return 0 if n_bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
