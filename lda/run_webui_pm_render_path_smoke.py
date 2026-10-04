# -*- coding: utf-8 -*-
"""WebUI 光子存储阵列（PM-M3）案例卡前端**取值路径 + 反向完备 + onclick** 门禁（2026-10-04）。

═══════════════════════════════════════════════════════════════════════════
为什么存在（血案 #32 同族 / 血案 #18·#19 机器化）
═══════════════════════════════════════════════════════════════════════════
后端侧门禁（`run_pm_m3_smoke` / 案例卡自检 / API 验收）**只保证 JSON 里有值**，
**不保证前端问对了地方**。本门禁把 `renderPm`（`sec-pm` 面板）的每条取值路径
逐条拿到真实 `pm_case.case_card()` JSON 上解析，并做**反向完备**——
把「后端加了字段、前端从不显示」的静默盲区钉死。

───────────────────────────────────────────────────────────────────────────
判什么
───────────────────────────────────────────────────────────────────────────
  W1 onclick 接线（`$('runPm').onclick = runPm`）+ 面板 DOM 契约
     （`sec-pm` / `runPm` / `pmSummary` / `pmBody` / `pmConclusion` 齐备）
  W2 函数定义（runPm / renderPm 真在场，且 runPm 真调 apiGet('/api/pm_demo')）
  W3 🔴 **取值路径存在性**：renderPm 里每条 `X.a.b` 引用（别名**按位置**解出 base）
     在真实 JSON 上逐段解析 ⇒ 全部存在
  W4 🔴 **反向完备**：顶层键 + 12 个嵌套块 + 5 个 `[]` 项目块，**每个字段都被前端引用**
  W5 路由接线（`/api/pm_demo` 登记 `GET_ROUTES` ∧ **不在** `HEAVY_POST_PATHS`）
  W6 🔴 突变探针（先证能变红）：改真实路径 / 抹掉别名绑定 / 往后端注入新字段 /
     改项目块字面量 ⇒ 对应判据必红；还原后复绿
  W7 自入 CI core

🔴 **诚实边界**：本门禁是**静态**路径检查，不执行 JS、不看渲染好不好看；
值存在但口径漂移仍需 `run_pm_m3_smoke`（重算判据）守。二者互补：
**重算判据守「值对不对」，本门禁守「问对没问对」。**
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from lda_harness.smoke_kit import make_check  # noqa: E402
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

from lda_harness.webui_js_ref import (  # noqa: E402
    render_body, alias_timeline, scan_refs, bad_refs, json_path_exists, js_ref_ok,
)

INDEX = os.path.join(_HERE, "lda_webui", "static", "index.html")
ROUTES = os.path.join(_HERE, "lda_webui", "routes.py")

#: 顶层块反向完备：`(JSON 前缀元组, 说明)`
_BLOCKS = (
    (("identity",), "器件/物理识别"),
    (("identity", "layers"), "版图层号"),
    (("span",), "征程跨度"),
    (("pitch",), "单元 pitch"),
    (("upstream",), "上游汇总"),
    (("upstream", "cell_length"), "M1 单元长"),
    (("upstream", "levels"), "M1 电平数"),
    (("upstream", "thermal"), "M2 热隔离"),
    (("budget",), "设计预算"),
    (("budget", "single_cell_il_db"), "单元插损区间"),
    (("budget", "array_il_db"), "阵列总损区间"),
    (("array",), "阵列汇总"),
    (("array", "main"), "主阵列"),
    (("array", "main", "stats"), "主阵列版图统计"),
    (("array", "main", "drc"), "主阵列 DRC"),
    (("array", "main", "lvs"), "主阵列 LVS"),
    (("array", "independent_scan"), "独立解码复核"),
    (("array", "expected_layers"), "期望层计数"),
    (("array", "wide"), "宽阵列"),
    (("array", "wide", "stats"), "宽阵列版图统计"),
    (("device",), "实现器件"),
    (("ui",), "面板导航"),
    (("signoff_checks",), "签核断言"),
    (("artifacts",), "产出物元信息"),
)

#: `[]` 项目块：`(JSON 前缀带 [] 路径, {js字面量: 相对字段})`
_ITEM_BLOCKS = (
    ("scale_tiers[]", "规模档", {
        "t.bus_x_cells": "bus_x_cells", "t.n_cells_total": "n_cells_total",
        "t.n_devices": "n_devices", "t.n_nets": "n_nets",
        "t.n_elements": "n_elements", "t.gds_bytes": "gds_bytes",
        "t.area_um2": "area_um2", "t.lvs": "lvs",
        "t.lvs_violations": "lvs_violations", "t.independent_ok": "independent_ok",
    }),
    ("milestones[]", "里程碑", {
        "m.id": "id", "m.code": "code", "m.title": "title",
        "m.gate": "gate", "m.result": "result",
    }),
    ("findings[]", "设计洞察", {"f.title": "title", "f.detail": "detail"}),
    ("gaps[]", "缺口", {"g.id": "id", "g.title": "title", "g.detail": "detail"}),
    ("artifacts.items[]", "产出物清单", {"it.name": "name", "it.bytes": "bytes"}),
)


#: 🔴 **显式豁免**（最后手段）：子键为**同源副本**，前端只渲染「真身」那一份。
#: 每条豁免都必须能通过「活性探针」（W4d）：该路径在本体里确实存在（不是死条款）。
_DUP_SUBTREES = {
    ("pitch", "thermal"): "与 upstream.thermal 同源副本（pitch 由 thermal 派生，前端只渲染上游那份）",
}


def _block_keys(card, prefix):
    """取 JSON 路径 `prefix` 处的键集（列表取首元素）。"""
    cur = card
    for seg in prefix:
        if isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        else:
            return set()
    if isinstance(cur, dict):
        return set(cur.keys())
    if isinstance(cur, list) and cur and isinstance(cur[0], dict):
        return set(cur[0].keys())
    return set()


def _ref_segs(refs, prefix):
    """由 refs 派生「在 `prefix` 这一层的被引用键名」。"""
    out = set()
    for _a, path, base in refs:
        full = tuple(base) + tuple(path.split("."))
        if len(full) > len(prefix) and full[:len(prefix)] == prefix:
            out.add(full[len(prefix)])
    return out


def _fulls(refs):
    return [tuple(base) + tuple(p.split(".")) for _a, p, base in refs]


def main() -> int:
    print("=" * 74)
    print("WebUI 光子存储阵列（PM-M3）案例卡 前端取值路径 + 反向完备 + onclick 门禁")
    print("=" * 74)

    html = open(INDEX, encoding="utf-8").read()
    from lda_webui import pm_case as PC
    card = PC.case_card()

    rsrc = render_body(html, "renderPm")
    usrc = render_body(html, "runPm")

    # ── W1 onclick 接线 + 面板 DOM 契约 ─────────────────────────────────
    check("W1a onclick 接线：$('runPm').onclick = runPm 在场（防「能力上线却点不动」）",
          "$('runPm').onclick = runPm" in html)
    dom = all(('id="%s"' % i) in html for i in
              ("sec-pm", "runPm", "pmSummary", "pmBody", "pmConclusion"))
    check("W1b 面板 DOM 契约：sec-pm / runPm / pmSummary / pmBody / pmConclusion 齐备", dom)
    check("W1c 导航快捷链接 #sec-pm 在场（入口可达性）", 'href="#sec-pm"' in html)

    # ── W2 函数定义 ─────────────────────────────────────────────────────
    check("W2a runPm / renderPm 在 index.html 内定义（非空壳）",
          "function runPm(" in html and "function renderPm(" in html)
    check("W2b runPm 调 apiGet('/api/pm_demo') 并转交 renderPm",
          "/api/pm_demo" in usrc and "renderPm(" in usrc)
    heads = ("① 上游设计点", "② 单元间距", "③ 主阵列", "④ 独立解码复核", "⑤ 规模档",
             "⑥ 设计预算", "⑦ 征程里程碑", "⑧ 设计洞察", "⑨ 诚实缺口", "⑩ 产出物")
    miss = [h for h in heads if h not in rsrc]
    check("W2c renderPm 真渲染 ①–⑩ 十段（防「后端加了段、前端还是空壳」）", not miss,
          "缺段：%s" % miss)
    check("W2d 抽屉目录自动运行映射含 '#sec-pm': 'runPm'",
          '"#sec-pm": "runPm"' in html)

    # ── W3 取值路径存在性 ───────────────────────────────────────────────
    timeline, table = alias_timeline(rsrc)
    names = set(table.keys())
    refs = scan_refs(rsrc, names, timeline)
    bad = bad_refs(card, refs)
    check("W3 🔴 **取值路径存在性**：%d 条引用路径（%d 个别名）逐条在真实 `case_card()` JSON 上"
          "解析 ⇒ 全部存在（血案 #32 那一层）" % (len(refs), len(names) - 1),
          not bad, "坏路径 %d 条：%s" % (len(bad), bad[:4]))

    # ── W4 反向完备 ─────────────────────────────────────────────────────
    top_backend = set(card.keys())
    top_ref = {f[0] for f in _fulls(refs) if f}
    miss_top = sorted(top_backend - top_ref)
    check("W4a 反向完备（顶层）：`case_card()` 全部 %d 个顶层键都被前端引用" % len(top_backend),
          not miss_top, "未被引用：%s" % miss_top)

    miss_blocks = []
    for prefix, label in _BLOCKS:
        bk = {k for k in _block_keys(card, prefix)
              if (prefix + (k,)) not in _DUP_SUBTREES}          # 显式豁免（同源副本）
        rk = _ref_segs(refs, prefix)
        d = sorted(bk - rk)
        if d:
            miss_blocks.append("%s(%s)缺%s" % (".".join(prefix), label, d))
    check("W4b 反向完备（%d 个嵌套块）：每块每个字段都被前端引用" % len(_BLOCKS),
          not miss_blocks, "盲区：%s" % miss_blocks[:4])

    # W4d 豁免活性探针：豁免的路径必须在**本体**里真存在（防「写死豁免吞掉新成员」）
    dead = [".".join(p) for p in _DUP_SUBTREES
            if p[-1] not in _block_keys(card, p[:-1])]
    check("W4d 🔴 豁免活性：%d 条显式豁免的路径在 `case_card()` 里**确实存在**（非死条款）"
          % len(_DUP_SUBTREES), not dead, "失效豁免：%s" % dead)

    all_lits = []
    for _p, _l, m in _ITEM_BLOCKS:
        all_lits += list(m.keys())
    miss_items, bad_items = [], []
    for prefix, label, mapping in _ITEM_BLOCKS:
        bk = _block_keys(card, prefix)
        rk = set(mapping.values())
        d = sorted(bk - rk)
        if d:
            miss_items.append("%s(%s)缺%s" % (prefix, label, d))
        for lit, _rel in mapping.items():
            if not js_ref_ok(rsrc, lit, all_lits):
                bad_items.append(lit)
    check("W4c 反向完备（%d 个 `[]` 项目块）：字段全覆盖 ∧ 每条 JS 字面量真在场"
          % len(_ITEM_BLOCKS), not miss_items and not bad_items,
          "缺字段=%s 缺字面量=%s" % (miss_items[:3], bad_items[:3]))

    # ── W5 路由接线 ─────────────────────────────────────────────────────
    rt = open(ROUTES, encoding="utf-8").read()
    get_block = rt.split("GET_ROUTES = {")[1].split("\n}")[0] if "GET_ROUTES = {" in rt else ""
    heavy = rt.split("HEAVY_POST_PATHS = {")[1].split("}")[0] if "HEAVY_POST_PATHS = {" in rt else ""
    check("W5a `/api/pm_demo` 登记进 GET_ROUTES 且 handler = h_pm_demo",
          '"/api/pm_demo": h_pm_demo,' in get_block)
    check("W5b 🔴 `/api/pm_demo` **不在** HEAVY_POST_PATHS（零重计算 ⇒ 免登录、无 DoS 面）",
          "/api/pm_demo" not in heavy and "def h_pm_demo(" in rt)

    # ── W6 突变探针（先证能变红）────────────────────────────────────────
    def _bad_paths(body):
        tl, tb = alias_timeline(body)
        return [x.split(" → ")[0] for x in bad_refs(card, scan_refs(body, set(tb.keys()), tl))]

    assert _bad_paths(rsrc) == [], "前置：原体应无坏路径"

    p1 = _bad_paths(rsrc.replace("PI.pitch_um", "PI.pitch_um_typo", 1))
    check("W6-P1 把一条真实路径改成 `PI.pitch_um_typo` ⇒ W3 必红（模拟血案 #32）",
          len(p1) >= 1, "命中 %d 条：%s" % (len(p1), p1[:2]))

    # 抹掉别名绑定 ⇒ 该块「不再被引用」⇒ W4 必红
    assert ", UI=d.ui||{}" in rsrc, "前置：别名块含 UI=d.ui||{}（探针锚点）"
    body2 = rsrc.replace(", UI=d.ui||{}", "", 1)
    _tl2, _tb2 = alias_timeline(body2)
    _refs2 = scan_refs(body2, set(_tb2.keys()), _tl2)
    top2 = {f[0] for f in _fulls(_refs2) if f}
    check("W6-P2 抹掉 `UI=d.ui||{}` 绑定 ⇒ W4a 顶层反向完备必红（假盲区回归）",
          "ui" not in top2)

    # 后端注入新字段 ⇒ W4b 该块必红
    import copy as _copy
    card2 = _copy.deepcopy(card)
    card2["pitch"]["brand_new_field"] = 1
    bk2 = {k for k in _block_keys(card2, ("pitch",))
           if ("pitch", k) not in _DUP_SUBTREES}
    d = sorted(bk2 - _ref_segs(refs, ("pitch",)))
    check("W6-P3 后端往 `pitch` 注入新字段 ⇒ W4b 必红（防「后端加了、前端不显示」）",
          d == ["brand_new_field"], "命中：%s" % d)

    # 项目块字面量被改 ⇒ W4c 必红
    p4 = "t.independent_okX" if not js_ref_ok(rsrc, "t.independent_okX", all_lits) else None
    check("W6-P4 项目块 JS 字面量被改（`t.independent_ok` → `…okX`）⇒ W4c 必红",
          p4 is not None and "t.independent_ok" in rsrc)

    check("W6-P5 还原完整性：探针退出后复跑仍无坏路径 ∧ UI 绑定仍在",
          _bad_paths(rsrc) == [] and "UI=d.ui||{}" in rsrc and '"#sec-pm": "runPm"' in html)

    # ── W7 自入 CI core ─────────────────────────────────────────────────
    ci = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("W7 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_webui_pm_render_path_smoke.py" in ck)

    print("")
    print("门禁 smoke：%d PASS / %d FAIL" % (globals().get("PASS", 0), globals().get("FAIL", 0)))
    return 0 if globals().get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
