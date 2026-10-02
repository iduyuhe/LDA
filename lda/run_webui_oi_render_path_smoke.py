# -*- coding: utf-8 -*-
"""WebUI 光联接模块 M0 案例卡前端**取值路径 + onclick**门禁（新征程 · 2026-10-02）。

═══════════════════════════════════════════════════════════════════════════
为什么存在（血案 #18 / #19 机器化）
═══════════════════════════════════════════════════════════════════════════
E17-e 生产实测：`renderECore` 取 `synthesis_law.serial_ns`，而该值实际在
`synthesis_law.demo.serial_ns` ⇒ **三格显示 0.0**。后端侧一切门禁
（案例卡 B1–B24 / API 验收）**都看不到这一层**：它们只保证 JSON 里有值，
**不保证前端问对了地方**。

本门禁把 `renderOi`（`sec-oi` 面板）的每条取值路径，逐条拿到真实
`oi_case.case_card()` JSON 上解析，并验证 `onclick` 接线反向完备——把
「JSON 里有值 ≠ 前端问对了地方」这层钉死。

───────────────────────────────────────────────────────────────────────────
判什么
───────────────────────────────────────────────────────────────────────────
1. **onclick 接线**：$('runOi').onclick = runOi 在场（防「能力上线却点不动」）。
2. **函数定义**：runOi / renderOi 在 index.html 内定义。
3. **路径存在性**：renderOi 引用的每条 d./rq./c./m./g. 取值路径，在真实 JSON 上
   逐段解析；**任一段不存在 ⇒ 红**（这正是血案 #18/#19 要抓的）。
4. **反向完备**：case_card() 下每个 channel 字段、requested 子字段、milestones/gaps
   元素字段都必须被前端引用（防「后端加了、前端不显示」的静默盲区）。
5. **突变探针**（先证能变红）：① 抹掉 case_card 某 channel 字段 ⇒ 路径判据必红；
   ② 删掉 onclick 接线行 ⇒ 接线判据必红；还原后复绿。
6. 自入 CI core（防静默漏接 · 血案 #28 同族）。

🔴 诚实边界：本门禁是**静态路径检查**，不执行 JS、不看渲染是否「好看」；
值存在但**语义不对**（口径漂移）仍由 oi_case.run_selfchecks + run_oi_m0_smoke
那类「卡内数字 ≡ 模块现算」判据守。二者互补：**那些守「值对不对」，本门禁守「问对没」**。
"""
from __future__ import annotations

import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

INDEX = os.path.join(_HERE, "lda_webui", "static", "index.html")

# (JS 字面引用, JSON 路径) —— JSON 路径支持 `arr[].key` 取首元素。
ROOT_PATHS = [
    ("d.case_id", "case_id"),
    ("d.verdict", "verdict"),
    ("d.verdict_label", "verdict_label"),
    ("d.b19_passivity", "b19_passivity"),
    ("d.honest_note", "honest_note"),
    ("d.design_notes", "design_notes"),
    ("d.milestones", "milestones"),
    ("d.gaps", "gaps"),
    ("d.channels", "channels"),
]
REQUESTED_PATHS = [  # renderOi 用 `var rq=d.requested||{}` 别名
    ("d.requested", "requested"),
    ("rq.n_lanes", "requested.n_lanes"),
    ("rq.channels_nm", "requested.channels_nm"),
    ("rq.v_pi_v", "requested.v_pi_v"),
    ("rq.gc_coupling", "requested.gc_coupling"),
    ("rq.fiber_span_db", "requested.fiber_span_db"),
]
CHANNEL_PATHS = [  # `var ch=d.channels||[]` 后 `c` 为元素
    ("ch", "channels"),
    ("c.lane", "channels[].lane"),
    ("c.channel_nm", "channels[].channel_nm"),
    ("c.R_um", "channels[].R_um"),
    ("c.il_closedform_db", "channels[].il_closedform_db"),
    ("c.il_cascade_db", "channels[].il_cascade_db"),
    ("c.il_ab_diff_db", "channels[].il_ab_diff_db"),
    ("c.isolation_db", "channels[].isolation_db"),
]
MILESTONE_PATHS = [  # `m` 为 milestones 元素
    ("m.id", "milestones[].id"),
    ("m.label", "milestones[].label"),
]
GAP_PATHS = [  # `g` 为 gaps 元素
    ("g.closed", "gaps[].closed"),
    ("g.id", "gaps[].id"),
    ("g.title", "gaps[].title"),
]


def json_path_exists(card: dict, path: str) -> bool:
    """逐段解析 JSON 路径；`arr[].k` 取首元素。任一段缺失 ⇒ False。"""
    cur = card
    for part in path.split("."):
        if part.endswith("[]"):
            key = part[:-2]
            if not isinstance(cur, dict) or key not in cur:
                return False
            arr = cur[key]
            if not isinstance(arr, list) or not arr:
                return False
            cur = arr[0]
        else:
            if not isinstance(cur, dict) or part not in cur:
                return False
            cur = cur[part]
    return True


def renderOi_src(html: str) -> str:
    m = re.search(r"function\s+renderOi\s*\([^\n]*\)\s*\{(.*?)\n\}", html, re.S)
    return m.group(1) if m else ""


def runOi_src(html: str) -> str:
    m = re.search(r"function\s+runOi\s*\([^\n]*\)\s*\{(.*?)\n\}", html, re.S)
    return m.group(1) if m else ""


def main() -> int:
    print("=" * 74)
    print("WebUI 光联接模块 M0 案例卡 前端取值路径 + onclick 门禁（新征程 · 血案 #18/#19 机器化）")
    print("=" * 74)

    html = open(INDEX, encoding="utf-8").read()
    from lda_webui import oi_case as oi
    card = oi.case_card(use_cache=False)
    rsrc = renderOi_src(html)
    usrc = runOi_src(html)

    # ── 1. onclick 接线 ─────────────────────────────────────────────────
    check("① onclick 接线：$('runOi').onclick = runOi 在场（防「点不动」）",
          "$('runOi').onclick = runOi" in html)

    # ── 2. 函数定义 ─────────────────────────────────────────────────────
    check("② runOi 在 index.html 内定义", "function runOi(" in html)
    check("② renderOi 在 index.html 内定义", "function renderOi(" in html)
    # runOi 必须真的调 apiGet + renderOi（不是空壳）
    check("② runOi 调用 apiGet('/api/oi_demo') 并转交 renderOi",
          "/api/oi_demo" in usrc and "renderOi(" in usrc)

    # ── 3. 路径存在性（前端引用 ∧ 后端 JSON 真有值）─────────────────────
    all_paths = ROOT_PATHS + REQUESTED_PATHS + CHANNEL_PATHS + MILESTONE_PATHS + GAP_PATHS
    for js_lit, json_path in all_paths:
        js_ok = js_lit in rsrc
        json_ok = json_path_exists(card, json_path)
        check("③ 路径 %s ⇒ JSON %s（前端引用 ∧ 后端存在）"
              % (js_lit, json_path),
              js_ok and json_ok,
              "js_ref=%s json_ok=%s" % (js_ok, json_ok))

    # ── 4. 反向完备（后端每个「展示」字段都必须被前端引用）────────────
    # 🔴 `detail` 是紧凑行之外的辅助长文，前端 compact 行有意不渲染 ⇒ 允许不引用。
    OPTIONAL_UNREF = {"detail"}
    ch_keys = (set(card["channels"][0].keys()) if card.get("channels") else set()) - OPTIONAL_UNREF
    req_keys = (set(card["requested"].keys()) if isinstance(card.get("requested"), dict) else set()) - OPTIONAL_UNREF
    ms_keys = (set(card["milestones"][0].keys()) if card.get("milestones") else set()) - OPTIONAL_UNREF
    gp_keys = (set(card["gaps"][0].keys()) if card.get("gaps") else set()) - OPTIONAL_UNREF

    ref_ch = {p[1].split("[].", 1)[1] for p in CHANNEL_PATHS if p[1].startswith("channels[].")}
    ref_req = {p[1].split(".", 1)[1] for p in REQUESTED_PATHS if p[1].startswith("requested.")}
    ref_ms = {p[1].split("[].", 1)[1] for p in MILESTONE_PATHS if p[1].startswith("milestones[].")}
    ref_gp = {p[1].split("[].", 1)[1] for p in GAP_PATHS if p[1].startswith("gaps[].")}

    check("④a 反向完备：channels 每个展示字段都被前端引用（无静默盲区）",
          ch_keys <= ref_ch, "后端=%s 前端引用=%s" % (sorted(ch_keys), sorted(ref_ch)))
    check("④b 反向完备：requested 每个子字段都被前端引用",
          req_keys <= ref_req, "后端=%s 前端引用=%s" % (sorted(req_keys), sorted(ref_req)))
    check("④c 反向完备：milestones 每个展示字段都被前端引用（detail 为辅助长文，有意不渲染）",
          ms_keys <= ref_ms, "后端=%s 前端引用=%s" % (sorted(ms_keys), sorted(ref_ms)))
    check("④d 反向完备：gaps 每个展示字段都被前端引用（detail 同）",
          gp_keys <= ref_gp, "后端=%s 前端引用=%s" % (sorted(gp_keys), sorted(ref_gp)))

    # ── 5. 突变探针（先证能变红）───────────────────────────────────────
    # 探针①：抹掉 case_card 的某 channel 字段 ⇒ ③ 的路径判据必红
    import copy
    card_mut = copy.deepcopy(card)
    del card_mut["channels"][0]["il_cascade_db"]
    probe1 = json_path_exists(card_mut, "channels[].il_cascade_db")
    check("🔴 探针①: 抹掉 channels[].il_cascade_db ⇒ ③ 路径判据必红",
          probe1 is False)

    # 探针②：删掉 onclick 接线行 ⇒ ① 接线判据必红
    html_mut = html.replace("$('runOi').onclick = runOi", "$('runOi').onclick = null")
    probe2 = "$('runOi').onclick = runOi" in html_mut
    check("🔴 探针②: 删掉 onclick 接线 ⇒ ① 接线判据必红", probe2 is False)

    # ── 6. 自入 CI core ────────────────────────────────────────────────
    ci = os.path.join(_ROOT, "lda", "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28 同族）",
          "run_webui_oi_render_path_smoke.py" in ck)

    # ── 汇总（make_check 已逐行打印；此处只出计数）────────────────────
    npass = globals().get("PASS", 0)
    nfail = globals().get("FAIL", 0)
    print()
    print("RESULT: %d PASS / %d FAIL" % (npass, nfail))
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
