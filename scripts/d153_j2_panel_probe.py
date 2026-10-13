#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""J2 超导 transmon QPU 案例卡（WebUI `sec-j2` 面板）· 门禁的**真实文件级**突变探针
（13 条突变各必红 + 还原复绿 · v0.9.234）。

═══════════════════════════════════════════════════════════════════════════
为什么还要这一层（门禁里已有 19 条 in-gate 探针）
═══════════════════════════════════════════════════════════════════════════
`run_webui_j2_render_path_smoke` 的 G1–G19 探针是在**函数参数**上做变异（喂变异卡 /
变异源码字符串）—— 它证明的是**判定函数**能变红。但若「判定函数吃的输入」与
「真实文件」不同构（例如门禁读的是另一个路径、或 `from lda_webui import j2_case`
没真拿到被改的那个模块），in-gate 探针仍会全绿而**真实缺陷照样漏**。

本脚本因此对**真实文件内容 / 真实模块对象**做突变，再跑**整道门禁**，并断言
**预期判据名**出现在 `[FAIL]` 行里（不是只看 `FAIL>0`）：

  M1  index.html 删 onclick 接线                    ⇒ A1 必红
  M2  index.html 删 `<div id="j2Body">`            ⇒ A2 必红
  M3  index.html 删首屏直达 `href="#sec-j2"`        ⇒ A3 必红
  M4  index.html 改一处取值路径（idf.physics→…X）   ⇒ B1 必红
  M5  index.html 删 `m.bands` 引用（项目块字面量）  ⇒ C3 必红
  M6  index.html 抹掉一个嵌套块别名（bg=d.budget）  ⇒ C2 必红
  M7  j2_case.py 顶层注入 `import numpy`（源码级）  ⇒ F5 必红
  M8  卡内 `errors.eps_1q` ×2（闭式复刻漂移）       ⇒ D1 必红
  M9  卡内 `budget.signoff` 篡改（ACCEPT→REJECT）   ⇒ D6 必红
  M10 卡内 `loop.p_phys_used` ÷2（退回 ε 口径）     ⇒ D10 必红
  M11 卡内 verdict 冒充 ACCEPT                      ⇒ F1 必红
  M12 卡内 honest_note 删边界关键词                  ⇒ F2 必红
  M13 routes.py 把 `/api/j2_qpu` 塞进 HEAVY_POST_PATHS ⇒ F4 必红
  （末条）还原后复跑 ⇒ 全绿（还原完整性）

运行：python scripts/d153_j2_panel_probe.py
"""
from __future__ import annotations

import contextlib
import io
import os
import re
import sys
import tempfile
import types

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LDA = os.path.join(_ROOT, "lda")
for _p in (_LDA, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import run_webui_j2_render_path_smoke as SMOKE          # noqa: E402
from lda_webui import j2_case as JC                     # noqa: E402
import lda_webui                                        # noqa: E402

_REAL_INDEX = SMOKE.INDEX
_REAL_ROUTES = SMOKE.ROUTES
_REAL_CASE = SMOKE.CASE_PY

_TMP = tempfile.mkdtemp(prefix="j2_panel_probe_")
_results = []


def _run():
    """跑整道门禁（在已打补丁的路径/模块上），返回 (rc, {FAIL 判据名})。"""
    SMOKE.PASS = 0
    SMOKE.FAIL = 0
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = SMOKE.main()
    except Exception:                                    # noqa: BLE001
        rc = 2
    out = buf.getvalue()
    fails = set(re.findall(r"\[FAIL\]\s+([A-Z][A-Za-z0-9]*)", out))
    return rc, fails, out


def _write(tmp_name, text):
    p = os.path.join(_TMP, tmp_name)
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return p


@contextlib.contextmanager
def _patched(index=None, routes=None, case_src=None, card_mut=None):
    """打补丁：源码级走临时文件路径；卡值级走替换 `lda_webui.j2_case` 模块对象。"""
    old_index, old_routes, old_case = SMOKE.INDEX, SMOKE.ROUTES, SMOKE.CASE_PY
    old_mod = getattr(lda_webui, "j2_case", None)
    try:
        if index is not None:
            SMOKE.INDEX = _write("index.html", index)
        if routes is not None:
            SMOKE.ROUTES = _write("routes.py", routes)
        if case_src is not None:
            SMOKE.CASE_PY = _write("j2_case.py", case_src)
        if card_mut is not None:
            card = JC.case_card()
            card_mut(card)
            variant = types.ModuleType("lda_webui.j2_case")
            variant.__dict__.update(JC.__dict__)
            variant.case_card = lambda: card           # type: ignore[assignment]
            setattr(lda_webui, "j2_case", variant)
        yield
    finally:
        SMOKE.INDEX, SMOKE.ROUTES, SMOKE.CASE_PY = old_index, old_routes, old_case
        if old_mod is not None:
            setattr(lda_webui, "j2_case", old_mod)


def _probe(name, expect, **kw):
    with _patched(**kw):
        rc, fails, _out = _run()
    ok = expect in fails
    _results.append((name, ok, "期望 %s 红 · 实红=%s" % (expect, sorted(fails)[:6])))
    print("  [%s] %s  |  期望 %s 红 · 实红=%s"
          % ("PASS" if ok else "FAIL", name, expect, sorted(fails)[:6]))
    return ok


def main() -> int:
    print("=" * 74)
    print("J2 面板门禁 · 真实文件级突变探针（13 条 + 还原复绿）")
    print("=" * 74)

    index = io.open(_REAL_INDEX, encoding="utf-8").read()
    routes = io.open(_REAL_ROUTES, encoding="utf-8").read()
    case_src = io.open(_REAL_CASE, encoding="utf-8").read()

    # 前置：原样全绿
    with _patched():
        rc0, fails0, out0 = _run()
    _results.append(("M0 前置：原样跑 ⇒ 0 FAIL", rc0 == 0 and not fails0,
                     "rc=%s fails=%s" % (rc0, sorted(fails0)[:6])))
    print("  [%s] M0 前置：原样跑 ⇒ 0 FAIL  |  rc=%s fails=%s"
          % ("PASS" if rc0 == 0 and not fails0 else "FAIL", rc0, sorted(fails0)[:6]))

    # M1 onclick 接线删除
    _probe("M1 index.html 删 onclick 接线", "A1",
           index=index.replace("$('runJ2').onclick = runJ2", "", 1))
    # M2 面板 DOM 契约破缺
    _probe("M2 index.html 删 `<div id=\"j2Body\">`", "A2",
           index=index.replace('<div id="j2Body"></div>', "", 1))
    # M3 首屏直达删除
    _probe("M3 index.html 删首屏直达 href=\"#sec-j2\"", "A3",
           index=re.sub(r'\s*<a href="#sec-j2"[^>]*>[^<]*</a>', "", index, count=1))
    # M4 取值路径篡改
    # 🔴 作用域纪律：`idf.physics` 全文件首现于 renderQsensor（QS 面板 · 由 QS 门禁守），
    #    若在全文件上做首个 replace，变异落在 J2 门禁消费范围之外 ⇒ B1 本就不该红 ⇒ 探针假阳。
    #    门禁 B1 基于 render_body(html,"renderJ2") ⇒ 变异必须落进 renderJ2 函数体（首个匹配在 10438 行）。
    _j2_off = index.index("function renderJ2(d){")
    _m4_idx = (index[:_j2_off]
               + index[_j2_off:].replace("idf.physics", "idf.physicsX", 1))
    _probe("M4 index.html 改取值路径（renderJ2 内 idf.physics→…X）", "B1",
           index=_m4_idx)
    # M5 项目块字面量删除
    _probe("M5 index.html 删 `m.bands` 引用", "C3",
           index=index.replace("+m.bands", "", 1).replace("(m.bands||[])", "", 1))
    # M6 嵌套块别名抹掉 ⇒ 该块不再被引用
    _probe("M6 index.html 抹掉 `bg=d.budget||{},` 绑定", "C2",
           index=index.replace("bg=d.budget||{},", "", 1))
    # M7 顶层注入 numpy（源码级）
    _probe("M7 j2_case.py 顶层注入 `import numpy`", "F5",
           case_src=case_src.replace("import math\n", "import math\nimport numpy  # noqa\n", 1))
    # M8 闭式复刻漂移
    _probe("M8 卡内 errors.eps_1q ×2（复刻漂移）", "D1",
           card_mut=lambda c: c["errors"].__setitem__("eps_1q", c["errors"]["eps_1q"] * 2.0))
    # M9 预算签核篡改
    _probe("M9 卡内 budget.signoff 篡改（ACCEPT→REJECT）", "D6",
           card_mut=lambda c: c["budget"].__setitem__("signoff", "REJECT"))
    # M10 去极化口径错（÷2 退回 ε）
    _probe("M10 卡内 loop.p_phys_used ÷2（退回 ε 口径）", "D10",
           card_mut=lambda c: c["loop"].__setitem__("p_phys_used", c["loop"]["p_phys_used"] / 2.0))
    # M11 verdict 冒充实测
    _probe("M11 卡内 verdict 冒充 ACCEPT", "F1",
           card_mut=lambda c: c.__setitem__("verdict", "ACCEPT"))
    # M12 诚实边界删关键词
    _probe("M12 卡内 honest_note 删「零量子 SDK」", "F2",
           card_mut=lambda c: c.__setitem__("honest_note", c["honest_note"].replace("零量子 SDK", "")))
    # M13 端点误入登录闸门
    _probe("M13 routes.py 把 /api/j2_qpu 塞进 HEAVY_POST_PATHS", "F4",
           routes=routes.replace("HEAVY_POST_PATHS = {",
                                 'HEAVY_POST_PATHS = {\n    "/api/j2_qpu",', 1))

    # 还原复绿
    with _patched():
        rc1, fails1, _o = _run()
    _results.append(("M14 还原完整性：还原后复跑 ⇒ 0 FAIL", rc1 == 0 and not fails1,
                     "rc=%s fails=%s" % (rc1, sorted(fails1)[:6])))
    print("  [%s] M14 还原完整性：还原后复跑 ⇒ 0 FAIL  |  rc=%s fails=%s"
          % ("PASS" if rc1 == 0 and not fails1 else "FAIL", rc1, sorted(fails1)[:6]))

    n_ok = sum(1 for _n, ok, _d in _results if ok)
    print("")
    print("探针：%d PASS / %d FAIL（共 %d 条）"
          % (n_ok, len(_results) - n_ok, len(_results)))
    return 0 if n_ok == len(_results) else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
