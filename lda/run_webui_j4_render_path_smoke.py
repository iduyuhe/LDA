#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""J4 案例卡渲染路径常驻门禁（前端取值路径 + 跨源逐值对拍 + 判据数自洽 + 红线）。

═══ 判什么（分节）═══
A 🔴 **前端接线**：`index.html` 有 `sec-j4` 段 · `runJ4` 按钮 · `renderJ4` 函数 ·
   `apiGet('/api/j4_qs_system')` 调用 · `CASE_MAP` 深链 `#sec-j4` · 首屏 `#sec-j4` 链接。
B 🔴 **取值路径存在性**：`renderJ4` 里每个 `d.<block>.<key>` 引用都能在真实 `case_card()`
   JSON 上逐段解析（防「卡里有值但前端问错了地方」）。
C 🔴 **反向完备**：`case_card()` 的每个顶层键必须被前端引用（防「后端算了前端不问」）。
D 🔴 **跨源逐值对拍**：`j4_case` 的闭式现算 ≡ **真源模块**现算
   （τ̂ ≡ `qs_j4_multiparam.decouple_cramer` · Q ≡ `qs_j4_packaging.cryo_wiring_heat_load`
    ≡ **账本锚 B518 golden** · 劣化倍率 ≡ `qs_j4_integration` · 微型化 ≡ `qs_j4_microcell`）。
E 🔴 **判据数自洽**：实跑 `run_j4_multiparam_smoke` 的 PASS 数 == 卡内 `gate_checks`。
F 🔴 **红线**：`verdict` 恒 `DESIGN_BUDGET`（不伪装实测）· 不进 `HEAVY_POST_PATHS` ·
   `j4_case` 不 import numpy/scipy（ast 断言 · 零重计算）。
G 🔴 **突变探针**（in-process，不碰源文件）：改坏各节关键量 ⇒ 对应对拍判据必红。

🔴 **零重计算**：本门禁只读 `index.html` 文本 + 调 `j4_case.case_card()`（微秒级）。
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
    from lda_webui import j4_case as J4  # noqa: E402
except ImportError:  # pragma: no cover
    from .lda_webui import j4_case as J4  # type: ignore

from lda_l2 import qs_j4_integration as IG  # noqa: E402
from lda_l2 import qs_j4_microcell as MC  # noqa: E402
from lda_l2 import qs_j4_multiparam as MP  # noqa: E402
from lda_l2 import qs_j4_packaging as PK  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

_HTML = os.path.join(_HERE, "lda_webui", "static", "index.html")
_J4_SRC = os.path.join(_HERE, "lda_webui", "j4_case.py")
_SMOKE = "run_j4_multiparam_smoke.py"


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


def main() -> int:
    html = _read(_HTML)
    card = J4.case_card()

    # ----------------------------------------------------------------- A
    check("A1 前端接线齐备：sec-j4 段 + runJ4 按钮 + renderJ4 函数 + apiGet 调用",
          'id="sec-j4"' in html and 'id="runJ4"' in html
          and "function renderJ4(" in html and "apiGet('/api/j4_qs_system')" in html,
          "sec=%s btn=%s fn=%s api=%s" % ('id="sec-j4"' in html, 'id="runJ4"' in html,
                                          "function renderJ4(" in html,
                                          "apiGet('/api/j4_qs_system')" in html))
    check("A2 hash 深链 CASE_MAP 含 #sec-j4 → runJ4",
          re.search(r'"#sec-j4"\s*:\s*"runJ4"', html) is not None,
          "正则命中=%s" % (re.search(r'"#sec-j4"\s*:\s*"runJ4"', html) is not None))
    check("A3 首屏 #wbCaseBar 含 #sec-j4 直达链接",
          'href="#sec-j4"' in html, "命中=%s" % ('href="#sec-j4"' in html))

    # ----------------------------------------------------------------- B
    refs = sorted(set(re.findall(r"\bd\.([a-z_]+)", html[html.find("function renderJ4("):
                                                            html.find("async function runJ3(")])))
    missing = [r for r in refs if r != "error" and not _json_has(card, r)]
    check("B1 取值路径存在性：renderJ4 引用的顶层块 %s 全部在真实 JSON 上可解析" % refs,
          not missing, "缺=%s" % (missing or "无"))

    # ----------------------------------------------------------------- C
    top_keys = [k for k in card.keys()]
    unreferenced = [k for k in top_keys if k not in refs
                    and k not in ("case_id", "verdict", "honest_note", "findings",
                                  "span", "gate_checks", "error")]
    check("C1 反向完备：case_card 顶层键（除身份/口径/span 外）均被前端引用",
          not unreferenced, "顶层键=%s 未引用=%s" % (top_keys, unreferenced or "无"))

    # ----------------------------------------------------------------- D
    tau_mp = float(MP.decouple_cramer(1.0)[1])
    check("D1 跨源逐值对拍：j4_case τ̂ ≡ qs_j4_multiparam.decouple_cramer（≤1 ULP）",
          abs(card["multiparam"]["tau_hat"] - tau_mp) < 1e-15,
          "case=%.15e mp=%.15e" % (card["multiparam"]["tau_hat"], tau_mp))

    q_pk = float(PK.cryo_wiring_heat_load())
    from lda_harness import _batch_j4_numeric as B
    q_anchor = float(B.golden_b518())
    check("D2 跨源逐值对拍：j4_case Q ≡ qs_j4_packaging ≡ **账本锚 B518 golden**（逐位）",
          abs(card["packaging"]["single_wire_load_w"] - q_pk) == 0.0
          and abs(q_pk - q_anchor) == 0.0,
          "case=%.15e pkg=%.15e anchor=%.15e" % (card["packaging"]["single_wire_load_w"],
                                                 q_pk, q_anchor))

    pen_ig = float(IG.net_sensitivity_penalty())
    check("D3 跨源逐值对拍：j4_case 净劣化 ≡ qs_j4_integration.net_sensitivity_penalty",
          abs(card["integration"]["net_penalty"] - pen_ig) < 1e-15,
          "case=%.15e ig=%.15e" % (card["integration"]["net_penalty"], pen_ig))

    mc_mod = MC.microcell_report()
    check("D4 跨源逐值对拍：j4_case 微型化劣化 ≡ qs_j4_microcell（rel<1e-12）",
          abs(card["microcell"]["penalty"] - mc_mod["miniaturization_penalty"]) < 1e-12,
          "case=%.9f mc=%.9f" % (card["microcell"]["penalty"], mc_mod["miniaturization_penalty"]))

    # ----------------------------------------------------------------- E
    r = subprocess.run([sys.executable, os.path.join(_HERE, _SMOKE)], cwd=_HERE,
                       capture_output=True, text=True, timeout=300)
    n_pass = sum(1 for ln in (r.stdout or "").splitlines()
                 if ln.lstrip().startswith("[PASS"))
    check("E1 判据数自洽：实跑 %s 的 PASS 数（%d）== 卡内 gate_checks（%d）"
          % (_SMOKE, n_pass, int(card["gate_checks"])),
          n_pass == int(card["gate_checks"]), "实跑=%d 卡内=%d" % (n_pass, card["gate_checks"]))

    # ----------------------------------------------------------------- F
    check("F1 红线：verdict 恒 DESIGN_BUDGET（不伪装 ACCEPT/PASS/实测）",
          card["verdict"] == "DESIGN_BUDGET", "verdict=%s" % card["verdict"])

    src = _read(_J4_SRC)
    tree = ast.parse(src)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
    banned = sorted(imports & {"numpy", "scipy", "lda_solver", "lda_harness", "lda_l2"})
    check("F2 零重计算：j4_case 顶层 import 仅标准库（禁 numpy/scipy/求解器）",
          not banned, "imports=%s 违禁=%s" % (sorted(imports), banned or "无"))

    check("F3 端点不进 HEAVY_POST_PATHS（只读 GET · 无 DoS 面）",
          card["span"]["heavy_post"] is False, "heavy_post=%s" % card["span"]["heavy_post"])

    # ----------------------------------------------------------------- G
    _tau = J4.cramer_temperature
    J4.cramer_temperature = lambda *a, **k: 0.0
    bad = abs(J4.case_card()["multiparam"]["tau_hat"] - tau_mp) < 1e-15
    J4.cramer_temperature = _tau
    check("G1 突变探针：τ̂ 被改坏 ⇒ D1 型对拍必红（非假绿）", not bad, "假绿=%s" % bad)

    _q = J4.wiring_heat_load
    J4.wiring_heat_load = lambda *a, **k: 1.0
    badq = abs(J4.case_card()["packaging"]["single_wire_load_w"] - q_anchor) == 0.0
    J4.wiring_heat_load = _q
    check("G2 突变探针：Q 被改坏 ⇒ D2 型对拍必红（非假绿）", not badq, "假绿=%s" % badq)

    _cc = J4.case_card
    J4.case_card = lambda: dict(_cc(), verdict="ACCEPT")
    badv = J4.case_card()["verdict"] == "DESIGN_BUDGET"
    J4.case_card = _cc
    check("G3 突变探针：verdict 被改成 ACCEPT ⇒ F1 必红（不伪装实测）", not badv, "假绿=%s" % badv)

    check("G4 还原复绿：三次突变后 case_card 仍与真源一致",
          abs(J4.case_card()["multiparam"]["tau_hat"] - tau_mp) < 1e-15
          and J4.case_card()["verdict"] == "DESIGN_BUDGET",
          "tau=%.12e" % J4.case_card()["multiparam"]["tau_hat"])

    bad_n = globals().get("FAIL", 0)
    good_n = globals().get("PASS", 0)
    print("")
    print("J4 案例卡渲染路径门禁：%d PASS / %d FAIL" % (good_n, bad_n))
    return 0 if bad_n == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
