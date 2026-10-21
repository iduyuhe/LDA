# -*- coding: utf-8 -*-
"""量子赛道六层总览 · **WebUI 渲染路径门禁**（K 征程 K5 · 闭环 G-K-7）。

判据分节（**判据数实跑现数**）：
  A 前端接线（4）：`sec-qtrack` 段 + `runQTrack` 按钮 + `renderQTrack` 函数 +
    `apiGet('/api/qtrack')` · hash 深链 `CASE_MAP` · 首屏导航直达 · 三个渲染容器
  B 取值路径（2）：`renderQTrack` 引用的顶层键在**真实 card** 上可解析 · 反向完备
  C 事实性（6）：六层齐备 · 锚合计 48 · 每层 L2 == 锚数 · 每层 L3 == 锚数 ·
    判据合计 191 · **与 K4 矩阵独立对拍**（读 JSON 现算）
  D 纪律（4）：零重计算（AST 断言仅 stdlib · **禁 `lda_harness.benchmarks`（会拉 scipy）**）·
    端点免登录且不进 `HEAVY_POST_PATHS` · verdict 恒 `ACCEPT` + 诚实边界 ≥5 条 · 模块自检全 PASS
  E 突变探针（3）：改坏某层锚数 / 改坏 `coverage.l2` / 改坏 `verdict` ⇒ 必红
  F 还原复绿（1）：三次突变后 `case_card` 仍自洽

🔴 `main()` 返回「真值」而非恒 0；一律走 `smoke_kit.make_check`（棘轮 J3）。
🔴 本门禁**不 import `lda_harness.benchmarks`**（也不需要）—— 全部走受跟踪 JSON 口径。
"""

from __future__ import annotations

import ast
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_webui import qtrack_case as Q  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

_INDEX = os.path.join(_HERE, "lda_webui", "static", "index.html")
_CASE = os.path.join(_HERE, "lda_webui", "qtrack_case.py")
_ROUTES = os.path.join(_HERE, "lda_webui", "routes.py")
_COV = os.path.join(_HERE, "reports", "anchor_gate_coverage.json")

_EXPECT_LAYERS = 6
_EXPECT_ANCHORS = 48       # 🔵 下限棘轮（只增不减）
_EXPECT_JUDGES = 191       # 🔵 下限棘轮（只增不减）


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def _validate(card):
    """纯函数：把结构/事实性校验收成一个可注入对象的映射（供突变探针复用）。"""
    r = {}
    layers = card.get("layers") or []
    t = card.get("totals") or {}
    c = card.get("coverage") or {}
    lg = card.get("ledger") or {}
    r["C1 六层齐备"] = len(layers) == _EXPECT_LAYERS and \
        [l["id"] for l in layers] == ["L0", "L1", "L2", "L3", "L4", "L5"]
    r["C2 锚合计 ≥ 48"] = (t.get("anchors_n") or 0) >= _EXPECT_ANCHORS and \
        t.get("anchors_n") == sum(l.get("anchors_n", 0) for l in layers)
    r["C3 每层 L2 == 锚数（100%）"] = all(
        l.get("anchors_n", 0) > 0 and l.get("l2_n") == l.get("anchors_n")
        for l in layers)
    r["C4 每层 L3 == 锚数（100%）"] = all(
        l.get("l3_n") == l.get("anchors_n") for l in layers)
    r["C5 五层判据合计 ≥ 191"] = (t.get("judges_n") or 0) >= _EXPECT_JUDGES
    # 与 K4 矩阵独立对拍：读 JSON 现算 48 锚的 l2_count 全 > 0
    cov = json.loads(_read(_COV))
    ids = [a for l in layers for a in l.get("anchor_ids", [])]
    r["C6 与 K4 矩阵独立对拍（48 锚 l2_count 全 >0）"] = (
        len(ids) >= _EXPECT_ANCHORS and len(set(ids)) == len(ids)
        and all((cov["anchors"].get(a, {}).get("l2_count") or 0) > 0 for a in ids)
        and c.get("anchors_total") == cov["summary"]["anchors_total"]
        and c.get("l2") == cov["summary"]["l2_bespoke_covered"]
        and c.get("blind") == cov["summary"]["l2_blind"])
    r["D3 verdict 恒 ACCEPT 且诚实边界 ≥5"] = (
        card.get("verdict") == "ACCEPT" and len(card.get("honesty") or []) >= 5)
    r["D4 账本口径自洽（540 = 518+3+19）"] = (
        lg.get("anchors") == 540
        and lg.get("strict_independent") == 518
        and lg.get("degraded_ordinal") == 3
        and lg.get("self_consistent_stub") == 19)
    return r


def main():
    print("=" * 78)
    print("量子赛道六层总览渲染路径门禁（K5 · 闭环 G-K-7）")
    print("=" * 78)

    html = _read(_INDEX)
    routes = _read(_ROUTES)
    card = Q.case_card()

    # ── A 前端接线 ────────────────────────────────────────────────
    check("A1 前端接线齐备：sec-qtrack 段 + runQTrack 按钮 + renderQTrack 函数 + apiGet 调用",
          all(k in html for k in ('id="sec-qtrack"', 'id="runQTrack"',
                                  "function renderQTrack",
                                  "apiGet('/api/qtrack')")),
          "缺=%s" % [k for k in ('id="sec-qtrack"', 'id="runQTrack"',
                                 "function renderQTrack",
                                 "apiGet('/api/qtrack')") if k not in html])
    check("A2 hash 深链 CASE_MAP 含 #sec-qtrack → runQTrack",
          '"#sec-qtrack": "runQTrack"' in html, "")
    check("A3 首屏导航含 #sec-qtrack 直达链接",
          'href="#sec-qtrack"' in html, "")
    check("A4 三个渲染容器齐备（qtSummary / qtBody / qtConclusion）",
          all(k in html for k in ('id="qtSummary"', 'id="qtBody"',
                                  'id="qtConclusion"')), "")

    # ── B 取值路径 ────────────────────────────────────────────────
    # 只取 renderQTrack 体内引用的顶层键
    body = html.split("function renderQTrack")[1].split("async function")[0] \
        if "function renderQTrack" in html else ""
    refs = [k for k in ("layers", "totals", "ledger", "coverage", "honesty",
                        "verdict", "case_id", "heavy_post", "render_path_smoke")
            if "d." + k in body]
    check("B1 取值路径存在性：renderQTrack 引用的顶层块全部在真实 card 上可解析",
          all(k in card for k in refs),
          "refs=%s 缺=%s" % (refs, [k for k in refs if k not in card]))
    identity = {"case_id", "caliber", "render_path_smoke"}
    check("B2 反向完备：card 顶层键（除身份类）均被前端引用",
          all((k in body) or ("d." + k in body) for k in card if k not in identity),
          "未引用=%s" % [k for k in card if k not in identity and
                        ("d." + k) not in body])

    # ── C 事实性 ──────────────────────────────────────────────────
    r = _validate(card)
    for k in ("C1 六层齐备", "C2 锚合计 ≥ 48", "C3 每层 L2 == 锚数（100%）",
              "C4 每层 L3 == 锚数（100%）", "C5 五层判据合计 ≥ 191",
              "C6 与 K4 矩阵独立对拍（48 锚 l2_count 全 >0）"):
        check(k, r[k], "")

    # ── D 纪律 ────────────────────────────────────────────────────
    tree = ast.parse(_read(_CASE))
    mods = set()
    for n in tree.body:
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    bad_mods = mods & {"numpy", "scipy", "lda_harness", "lda_qeda", "lda_l2",
                       "lda_chain", "lda_design"}
    check("D1 零重计算：qtrack_case 顶层 import 仅 stdlib（禁 numpy/scipy/lda_harness）",
          not bad_mods, "违规=%s · 实际=%s" % (sorted(bad_mods), sorted(mods)))
    in_heavy = "/api/qtrack" in routes.split("HEAVY_POST_PATHS")[1][:4000] \
        if "HEAVY_POST_PATHS" in routes else False
    check("D2 端点免登录且不进 HEAVY_POST_PATHS",
          '"/api/qtrack": h_qtrack_demo' in routes and not in_heavy,
          "registered=%s in_heavy=%s"
          % ('"/api/qtrack": h_qtrack_demo' in routes, in_heavy))
    for k in ("D3 verdict 恒 ACCEPT 且诚实边界 ≥5", "D4 账本口径自洽（540 = 518+3+19）"):
        check(k, r[k], "")
    sc = Q.run_selfchecks()
    check("D5 模块自检全 PASS", all(sc.values()),
          "FAIL=%s" % [k for k, v in sc.items() if not v])

    # ── E 突变探针 ────────────────────────────────────────────────
    def mutated(fn):
        clone = json.loads(json.dumps(card))
        fn(clone)
        rr = _validate(clone)
        return [k for k, v in rr.items() if not v]

    def m_anchor(x):
        x["layers"][0]["anchors_n"] = 1
        x["totals"]["anchors_n"] = 1

    def m_cov(x):
        x["coverage"]["l2"] = -1

    def m_verdict(x):
        x["verdict"] = "MEASURED"

    red1 = mutated(m_anchor)
    check("E1 反向探针：改坏某层锚数 ⇒ C 组必红",
          "C2 锚合计 ≥ 48" in red1 or "C3 每层 L2 == 锚数（100%）" in red1,
          "红项=%s" % red1[:3])
    red2 = mutated(m_cov)
    check("E2 反向探针：改坏 coverage.l2 ⇒ C6 必红",
          "C6 与 K4 矩阵独立对拍（48 锚 l2_count 全 >0）" in red2,
          "红项=%s" % red2[:3])
    red3 = mutated(m_verdict)
    check("E3 反向探针：改坏 verdict ⇒ D3 必红",
          "D3 verdict 恒 ACCEPT 且诚实边界 ≥5" in red3, "红项=%s" % red3[:3])

    # ── F 还原复绿 ────────────────────────────────────────────────
    fresh = Q.case_card()
    rf = _validate(fresh)
    check("F1 还原复绿：突变后 case_card 仍自洽（C2/C3/C6 全 PASS）",
          rf["C2 锚合计 ≥ 48"] and rf["C3 每层 L2 == 锚数（100%）"]
          and rf["C6 与 K4 矩阵独立对拍（48 锚 l2_count 全 >0）"], "")

    bad = globals().get("FAIL", 0)
    print("\n" + "=" * 78)
    print("量子赛道总览渲染门禁：%s（FAIL=%d）"
          % ("ALL PASS" if bad == 0 else "有红色", bad))
    print("=" * 78)
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
