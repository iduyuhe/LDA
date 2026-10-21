#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""D1 案例卡渲染路径常驻门禁（前端取值路径 + 跨源逐值对拍 + 判据数自洽 + 红线 + 突变探针）。

═══ 判什么（分节 · **判据数实跑现数**）═══
A 前端接线 3：`index.html` 有 `sec-d1` 段 · `runD1` 按钮 · `renderD1` 函数 ·
  `apiGet('/api/d1_hetero')` 调用 · `CASE_MAP` 深链 `#sec-d1` · 首屏直达链接。
B 取值路径 1：`renderD1` 里每个 `d.<block>` 引用都能在真实 `case_card()` JSON 上解析
  （防「卡里有值但前端问错了地方」）。
C 反向完备 1：`case_card()` 的每个顶层键都被前端引用（防「后端算了前端不问」）。
D 跨源逐值对拍 5：本卡闭式现算 ≡ **真源模块**现算
  （阵列孔径 ≡ `lda_l2.qnet_hetero_array` · DMM 透射 / Debye 热容 / h_K / R_K ≡
   `lda_l2.hetero_thermal`）—— **不信任卡自证**。
E 判据数自洽 1：实跑 `run_v2d1_smoke` 的 PASS 数 == 卡内 `gate_checks`。
F 红线 5：`verdict` 恒 `DESIGN_BUDGET` · 卡不 import numpy/scipy/求解器（ast）·
  不进 `HEAVY_POST_PATHS` · **两条负结果如实呈现**（M1/M2 均 NOT_ANCHORABLE 且各带 ≥3 证据）·
  端点已注册进 `routes.ROUTES`。
G 突变探针 4：改坏闭式 / verdict ⇒ 对应对拍必红；还原复绿。

🔴 **零重计算**：本门禁只读 `index.html` 文本 + 调 `d1_case.case_card()`（微秒级）
+ 跑一次 `run_v2d1_smoke`（约 0.9 s）。
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
    from lda_webui import d1_case as D1  # noqa: E402
except ImportError:  # pragma: no cover
    from .lda_webui import d1_case as D1  # type: ignore

from lda_l2 import hetero_thermal as TH  # noqa: E402
from lda_l2 import qnet_hetero_array as AR  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

_HTML = os.path.join(_HERE, "lda_webui", "static", "index.html")
_ROUTES = os.path.join(_HERE, "lda_webui", "routes.py")
_D1_SRC = os.path.join(_HERE, "lda_webui", "d1_case.py")
_SMOKE = "run_v2d1_smoke.py"

#: case_card 顶层键白名单（身份 / 口径 / span / 自洽数 / 路径 — 非前端渲染块）
_IDENTITY = ("case_id", "verdict", "honest_note", "span", "gate_checks",
             "module_selfchecks", "negative_net_new_anchors", "source_paths", "error")

_REL_TOL = 1e-12


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


def _rel(a, b):
    return abs(float(a) - float(b)) / max(abs(float(b)), 1e-300)


def main() -> int:  # noqa: C901
    html = _read(_HTML)
    card = D1.case_card()
    segs = {s["segment"]: s for s in card["segments"]}

    # ----------------------------------------------------------------- A
    check("A1 前端接线齐备：sec-d1 段 + runD1 按钮 + renderD1 函数 + apiGet 调用",
          'id="sec-d1"' in html and 'id="runD1"' in html
          and "function renderD1(" in html and "apiGet('/api/d1_hetero')" in html,
          "sec=%s btn=%s fn=%s api=%s"
          % ('id="sec-d1"' in html, 'id="runD1"' in html,
             "function renderD1(" in html, "apiGet('/api/d1_hetero')" in html))
    check("A2 hash 深链 CASE_MAP 含 #sec-d1 → runD1",
          re.search(r'"#sec-d1"\s*:\s*"runD1"', html) is not None,
          "正则命中=%s" % (re.search(r'"#sec-d1"\s*:\s*"runD1"', html) is not None))
    check("A3 首屏导航含 #sec-d1 直达链接",
          'href="#sec-d1"' in html, "命中=%s" % ('href="#sec-d1"' in html))

    # ----------------------------------------------------------------- B
    _start = html.find("function renderD1(")
    _end = html.find("if($('runJ5')) $('runJ5').onclick", _start + 10)
    _blk = html[_start:_end if _end > _start else _start + 20000]
    refs = sorted(set(re.findall(r"\bd\.([a-z_][A-Za-z_0-9]*)", _blk)))
    missing = [r for r in refs if r != "error" and not _json_has(card, r)]
    check("B1 取值路径存在性：renderD1 引用的顶层块 %s 全部在真实 JSON 上可解析" % refs,
          not missing, "缺=%s" % (missing or "无"))

    # ----------------------------------------------------------------- C
    top_keys = list(card.keys())
    unreferenced = [k for k in top_keys if k not in refs and k not in _IDENTITY]
    check("C1 反向完备：case_card 顶层键（除身份/口径/span 外）均被前端引用",
          not unreferenced, "顶层键=%s 未引用=%s" % (top_keys, unreferenced or "无"))

    # ----------------------------------------------------------------- D
    g_src = float(AR.array_average_clip(n_modes=D1.N_MODES, spacing_m=D1.SPACING_M,
                                        waist_m=D1.WAIST_M,
                                        aperture_half_m=D1.APERTURE_HALF_M))
    check("D1 跨源对拍：阵列孔径 γ̄ ≡ qnet_hetero_array（rel < 1e-12）",
          _rel(segs["阵列孔径"]["value"], g_src) < _REL_TOL,
          "case=%.15e src=%.15e" % (segs["阵列孔径"]["value"], g_src))

    a_src = float(TH.dmm_transmission(D1.AL["v_sound_m_s"], D1.SI["v_sound_m_s"]))
    check("D2 跨源对拍：DMM 透射 α₁→₂ ≡ hetero_thermal.dmm_transmission",
          _rel(segs["声子透射"]["value"], a_src) < _REL_TOL,
          "case=%.15e src=%.15e" % (segs["声子透射"]["value"], a_src))

    c_src = float(TH.debye_heat_capacity_lowT(D1.T_K, D1.AL["theta_D_K"], D1.AL["n_atom_m3"]))
    check("D3 跨源对拍：Debye 热容 C₁ ≡ hetero_thermal.debye_heat_capacity_lowT",
          _rel(segs["声子热容"]["value"], c_src) < _REL_TOL,
          "case=%.15e src=%.15e" % (segs["声子热容"]["value"], c_src))

    h_src = float(TH.kapitza_conductance(D1.T_K))
    check("D4 跨源对拍：界面热导 h_K ≡ hetero_thermal.kapitza_conductance",
          _rel(segs["界面热导"]["value"], h_src) < _REL_TOL,
          "case=%.15e src=%.15e" % (segs["界面热导"]["value"], h_src))

    r_src = float(TH.kapitza_resistance(D1.T_K))
    check("D5 跨源对拍：界面热阻 R_K ≡ hetero_thermal.kapitza_resistance",
          _rel(segs["界面热阻"]["value"], r_src) < _REL_TOL,
          "case=%.15e src=%.15e" % (segs["界面热阻"]["value"], r_src))

    # ----------------------------------------------------------------- E
    r = subprocess.run([sys.executable, os.path.join(_HERE, _SMOKE)], cwd=_HERE,
                       capture_output=True, text=True, timeout=300, encoding="utf-8")
    n_pass = sum(1 for ln in (r.stdout or "").splitlines()
                 if ln.lstrip().startswith("[PASS"))
    check("E1 判据数自洽：实跑 %s 的 PASS 数（%d）== 卡内 gate_checks（%d）"
          % (_SMOKE, n_pass, int(card["gate_checks"])),
          n_pass == int(card["gate_checks"]), "实跑=%d 卡内=%d" % (n_pass, card["gate_checks"]))

    # ----------------------------------------------------------------- F
    check("F1 红线：verdict 恒 DESIGN_BUDGET（不伪装 ACCEPT/实测）",
          card["verdict"] == "DESIGN_BUDGET", "verdict=%s" % card["verdict"])

    tree = ast.parse(_read(_D1_SRC))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
    banned = sorted(imports & {"numpy", "scipy", "lda_solver", "lda_harness", "lda_l2"})
    check("F2 零重计算：d1_case 顶层 import 仅标准库（禁 numpy/scipy/求解器/能力层）",
          not banned, "imports=%s 违禁=%s" % (sorted(imports), banned or "无"))

    check("F3 端点不进 HEAVY_POST_PATHS（只读 GET · 无 DoS 面）",
          card["span"]["heavy_post"] is False, "heavy_post=%s" % card["span"]["heavy_post"])

    nr = card["negative_results"]
    check("F4 两条负结果如实呈现（M1/M2 均 NOT_ANCHORABLE ∧ 各带 ≥3 条证据）",
          len(nr) == 2
          and all(v["verdict"] == "NOT_ANCHORABLE" for v in nr.values())
          and all(len(v["evidence"]) >= 3 for v in nr.values()),
          "条数=%d 证据数=%s" % (len(nr), [len(v["evidence"]) for v in nr.values()]))

    check("F5 端点已注册进 routes.ROUTES（防「前端有按钮、后端无路由」）",
          '"/api/d1_hetero": h_d1_hetero' in _read(_ROUTES),
          "routes 命中=%s" % ('"/api/d1_hetero": h_d1_hetero' in _read(_ROUTES)))

    # ----------------------------------------------------------------- G
    _t = D1.array_average_clip
    D1.array_average_clip = lambda *a, **k: 0.5
    bad_g = _rel(D1.case_card()["segments"][0]["value"], g_src) < _REL_TOL
    D1.array_average_clip = _t
    check("G1 突变探针：array_average_clip 被改坏 ⇒ D1 型对拍必红（非假绿）",
          not bad_g, "假绿=%s" % bad_g)

    _h = D1.kapitza_h
    D1.kapitza_h = lambda *a, **k: 1.0
    bad_h = _rel(D1.case_card()["segments"][3]["value"], h_src) < _REL_TOL
    D1.kapitza_h = _h
    check("G2 突变探针：kapitza_h 被改坏 ⇒ D4 型对拍必红", not bad_h, "假绿=%s" % bad_h)

    _cc = D1.case_card
    D1.case_card = lambda: dict(_cc(), verdict="ACCEPT")
    bad_v = D1.case_card()["verdict"] == "DESIGN_BUDGET"
    D1.case_card = _cc
    check("G3 突变探针：verdict 被改成 ACCEPT ⇒ F1 必红（不伪装实测）",
          not bad_v, "假绿=%s" % bad_v)

    check("G4 还原复绿：三次突变后 case_card 仍与真源一致",
          _rel(D1.case_card()["segments"][0]["value"], g_src) < _REL_TOL
          and _rel(D1.case_card()["segments"][3]["value"], h_src) < _REL_TOL
          and D1.case_card()["verdict"] == "DESIGN_BUDGET",
          "g=%.12e h=%.12e" % (D1.case_card()["segments"][0]["value"],
                               D1.case_card()["segments"][3]["value"]))

    bad_n = globals().get("FAIL", 0)
    good_n = globals().get("PASS", 0)
    print("")
    print("D1 案例卡渲染路径门禁：%d PASS / %d FAIL" % (good_n, bad_n))
    return 0 if bad_n == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
