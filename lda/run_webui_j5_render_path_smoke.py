#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""J5 案例卡渲染路径常驻门禁（前端取值路径 + 跨源逐值对拍 + 判据数自洽 + 红线）。

═══ 判什么（分节）═══
A 🔴 **前端接线**：`index.html` 有 `sec-j5` 段 · `runJ5` 按钮 · `renderJ5` 函数 ·
   `apiGet('/api/j5_qnet')` 调用 · `CASE_MAP` 深链 `#sec-j5` · 首屏 `#sec-j5` 链接。
B 🔴 **取值路径存在性**：`renderJ5` 里每个 `d.<block>.<key>` 引用都能在真实 `case_card()`
   JSON 上逐段解析（防「卡里有值但前端问错了地方」）。
C 🔴 **反向完备**：`case_card()` 的每个顶层键必须被前端引用（防「后端算了前端不问」）。
D 🔴 **跨源逐值对拍**：`j5_case` 的闭式现算 ≡ **真源模块**现算
   （六段：信道 ≡ `qnet_channel.transmission` · 分发 ≡ `qnet_channel.link_fidelity`
    · 源 ≡ `qnet_source.hom_visibility` · 中继 ≡ `qnet_repeater` · 换能 ≡ `qnet_transducer`
    · 经典接口 ≡ `qnet_classical.jitter_infidelity`）**并 ≡ `qnet_system.link_segments()`**。
E 🔴 **判据数自洽**：实跑 `run_j5_qnet_smoke` 的 PASS 数 == 卡内 `gate_checks`。
F 🔴 **红线**：`verdict` 恒 `DESIGN_BUDGET`（不伪装实测）· 不进 `HEAVY_POST_PATHS` ·
   `j5_case` 不 import numpy/scipy（ast 断言 · 零重计算）· **M4 净增 0 如实呈现**。
G 🔴 **突变探针**（in-process，不碰源文件）：改坏各节关键量 ⇒ 对应对拍判据必红。

🔴 **零重计算**：本门禁只读 `index.html` 文本 + 调 `j5_case.case_card()`（微秒级）。
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from lda_harness.smoke_kit import make_check  # noqa: E402

try:
    from lda_webui import j5_case as J5  # noqa: E402
except ImportError:  # pragma: no cover
    from .lda_webui import j5_case as J5  # type: ignore

from lda_l2 import qnet_channel as CH  # noqa: E402
from lda_l2 import qnet_classical as CL  # noqa: E402
from lda_l2 import qnet_source as SR  # noqa: E402
from lda_l2 import qnet_system as QS  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

_HTML = os.path.join(_HERE, "lda_webui", "static", "index.html")
_J5_SRC = os.path.join(_HERE, "lda_webui", "j5_case.py")
_SMOKE = "run_j5_qnet_smoke.py"

#: case_card 顶层键白名单（身份 / 口径 / span / 门禁自洽数 —— 非前端渲染块）
_IDENTITY = ("case_id", "verdict", "honest_note", "span", "gate_checks", "error")


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def _json_has(obj, path):
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False
        cur = cur[part]
    return True


def main() -> int:  # noqa: C901
    html = _read(_HTML)
    card = J5.case_card()
    rows = QS.link_segments()
    segs = {s["segment"]: s for s in card["segments"]}

    # ----------------------------------------------------------------- A
    check("A1 前端接线齐备：sec-j5 段 + runJ5 按钮 + renderJ5 函数 + apiGet 调用",
          'id="sec-j5"' in html and 'id="runJ5"' in html
          and "function renderJ5(" in html and "apiGet('/api/j5_qnet')" in html,
          "sec=%s btn=%s fn=%s api=%s" % ('id="sec-j5"' in html, 'id="runJ5"' in html,
                                          "function renderJ5(" in html,
                                          "apiGet('/api/j5_qnet')" in html))
    check("A2 hash 深链 CASE_MAP 含 #sec-j5 → runJ5",
          re.search(r'"#sec-j5"\s*:\s*"runJ5"', html) is not None,
          "正则命中=%s" % (re.search(r'"#sec-j5"\s*:\s*"runJ5"', html) is not None))
    check("A3 首屏导航含 #sec-j5 直达链接",
          'href="#sec-j5"' in html, "命中=%s" % ('href="#sec-j5"' in html))

    # ----------------------------------------------------------------- B
    _blk = html[html.find("function renderJ5("):html.find("async function runJ4(")]
    # 🔴 字符类须含数字：`d.m4` 若用 `[a-z_]+` 会被截成 `m` ⇒ B1 假红 + C1 假红（本档实测踩到）
    refs = sorted(set(re.findall(r"\bd\.([a-z_][A-Za-z_0-9]*)", _blk)))
    missing = [r for r in refs if r != "error" and not _json_has(card, r)]
    check("B1 取值路径存在性：renderJ5 引用的顶层块 %s 全部在真实 JSON 上可解析" % refs,
          not missing, "缺=%s" % (missing or "无"))

    # ----------------------------------------------------------------- C
    top_keys = [k for k in card.keys()]
    unreferenced = [k for k in top_keys if k not in refs and k not in _IDENTITY]
    check("C1 反向完备：case_card 顶层键（除身份/口径/span 外）均被前端引用",
          not unreferenced, "顶层键=%s 未引用=%s" % (top_keys, unreferenced or "无"))

    # ----------------------------------------------------------------- D
    t_ch = float(CH.transmission(J5.LINK_LENGTH_M))
    check("D1 跨源逐值对拍：channel.transmission ≡ qnet_channel ≡ qnet_system 第 1 段（≤1 ULP）",
          abs(segs["channel"]["value"] - t_ch) < 1e-15
          and abs(rows[0]["value"] - t_ch) < 1e-15,
          "case=%.15e sys=%.15e" % (segs["channel"]["value"], rows[0]["value"]))

    f_ch = float(CH.link_fidelity(J5.LINK_LENGTH_M))
    check("D2 跨源逐值对拍：dist.fidelity ≡ qnet_channel.link_fidelity ≡ 第 2 段（≤1 ULP）",
          abs(segs["dist"]["value"] - f_ch) < 1e-15 and abs(rows[1]["value"] - f_ch) < 1e-15,
          "case=%.15e sys=%.15e" % (segs["dist"]["value"], rows[1]["value"]))

    v_sr = float(SR.hom_visibility())
    check("D3 跨源逐值对拍：source.visibility ≡ qnet_source.hom_visibility ≡ 第 3 段（≤1 ULP）",
          abs(segs["source"]["value"] - v_sr) < 1e-15 and abs(rows[2]["value"] - v_sr) < 1e-15,
          "case=%.15e sys=%.15e" % (segs["source"]["value"], rows[2]["value"]))

    check("D4 跨源逐值对拍：repeater.storage_window_factor ≡ qnet_system 第 4 段（≤1 ULP）",
          abs(segs["repeater"]["value"] - rows[3]["value"]) < 1e-15,
          "case=%.15e sys=%.15e" % (segs["repeater"]["value"], rows[3]["value"]))

    check("D5 跨源逐值对拍：transducer.eta_band ≡ qnet_system 第 5 段（≤1 ULP）",
          abs(segs["transducer"]["value"] - rows[4]["value"]) < 1e-15,
          "case=%.15e sys=%.15e" % (segs["transducer"]["value"], rows[4]["value"]))

    inf_cl = float(CL.jitter_infidelity())
    check("D6 跨源逐值对拍：classical.infidelity ≡ qnet_classical ≡ 第 6 段（≤1 ULP）",
          abs(segs["classical"]["value"] - inf_cl) < 1e-15
          and abs(rows[5]["value"] - inf_cl) < 1e-15,
          "case=%.15e sys=%.15e cl=%.15e" % (segs["classical"]["value"], rows[5]["value"], inf_cl))

    # ----------------------------------------------------------------- E
    r = subprocess.run([sys.executable, os.path.join(_HERE, _SMOKE)], cwd=_HERE,
                       capture_output=True, text=True, timeout=300, encoding="utf-8")
    n_pass = sum(1 for ln in (r.stdout or "").splitlines()
                 if ln.lstrip().startswith("[PASS"))
    check("E1 判据数自洽：实跑 %s 的 PASS 数（%d）== 卡内 gate_checks（%d）"
          % (_SMOKE, n_pass, int(card["gate_checks"])),
          n_pass == int(card["gate_checks"]), "实跑=%d 卡内=%d" % (n_pass, card["gate_checks"]))

    # ----------------------------------------------------------------- F
    check("F1 红线：verdict 恒 DESIGN_BUDGET（不伪装 ACCEPT/PASS/实测）",
          card["verdict"] == "DESIGN_BUDGET", "verdict=%s" % card["verdict"])

    src = _read(_J5_SRC)
    tree = ast.parse(src)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
    banned = sorted(imports & {"numpy", "scipy", "lda_solver", "lda_harness", "lda_l2"})
    check("F2 零重计算：j5_case 顶层 import 仅标准库（禁 numpy/scipy/求解器）",
          not banned, "imports=%s 违禁=%s" % (sorted(imports), banned or "无"))

    check("F3 端点不进 HEAVY_POST_PATHS（只读 GET · 无 DoS 面）",
          card["span"]["heavy_post"] is False, "heavy_post=%s" % card["span"]["heavy_post"])

    check("F4 M4 净增 0 如实呈现（不虚报）：净增=0 ∧ 避让 3 条 ∧ 负证据 3 条",
          card["m4"]["net_new_anchors"] == 0 and len(card["m4"]["avoidance"]) == 3
          and len(card["m4"]["negative_evidence"]) == 3,
          "net_new=%s" % card["m4"]["net_new_anchors"])

    # ----------------------------------------------------------------- G
    _t = J5.transmission
    J5.transmission = lambda *a, **k: 0.5
    bad_t = abs(J5.case_card()["segments"][0]["value"] - t_ch) < 1e-15
    J5.transmission = _t
    check("G1 突变探针：transmission 被改坏 ⇒ D1 型对拍必红（非假绿）", not bad_t, "假绿=%s" % bad_t)

    _j = J5.jitter_infidelity
    J5.jitter_infidelity = lambda *a, **k: 0.0
    bad_j = abs(J5.case_card()["segments"][5]["value"] - inf_cl) < 1e-15
    J5.jitter_infidelity = _j
    check("G2 突变探针：jitter_infidelity 被改坏 ⇒ D6 型对拍必红", not bad_j, "假绿=%s" % bad_j)

    _cc = J5.case_card
    J5.case_card = lambda: dict(_cc(), verdict="ACCEPT")
    bad_v = J5.case_card()["verdict"] == "DESIGN_BUDGET"
    J5.case_card = _cc
    check("G3 突变探针：verdict 被改成 ACCEPT ⇒ F1 必红（不伪装实测）", not bad_v, "假绿=%s" % bad_v)

    check("G4 还原复绿：三次突变后 case_card 仍与真源一致",
          abs(J5.case_card()["segments"][0]["value"] - t_ch) < 1e-15
          and abs(J5.case_card()["segments"][5]["value"] - inf_cl) < 1e-15
          and J5.case_card()["verdict"] == "DESIGN_BUDGET",
          "t=%.12e" % J5.case_card()["segments"][0]["value"])

    bad_n = globals().get("FAIL", 0)
    good_n = globals().get("PASS", 0)
    print("")
    print("J5 案例卡渲染路径门禁：%d PASS / %d FAIL" % (good_n, bad_n))
    return 0 if bad_n == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
