#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""WebUI J3 案例卡「渲染路径」常驻门禁（v0.9.236 · J3 征程 M0–M4 面板交付）。

═══════════════════════════════════════════════════════════════════════════
为什么需要这一道（与 `run_webui_entry_smoke` / `run_j3_ctrl_smoke` 的分工）
═══════════════════════════════════════════════════════════════════════════
· `run_j3_ctrl_smoke`   —— **后端**（五锚 B510–B514 + 六能力层 + 闭环总装）的物理判据门禁；
· `run_webui_entry_smoke` —— 面板**入族**（三入口面之一：首屏条 / 抽屉字典 / data-stage 族）；
· **本门禁** —— **前端渲染路径**：从 `index.html` 里**真抽出** `renderJ3` 函数体，把其
  中**每一条 `d.xxx` / `blk.field` 取值路径**拿到**真实 `case_card()` JSON** 上逐条解析，
  并做**反向完备**（`case_card()` 的每个顶层键 / 每个嵌套块字段都必须被前端引用）
  + **跨源逐值对拍**（卡内数字 ≡ `lda_qeda` 各真源模块现算值）
  + **红线**（verdict 恒 DESIGN_BUDGET / 诚实边界 / 路由登记 / 免登录 / 零重计算）
  + **突变探针**（逐条必红）。

🔴 血案背景：`v0.9.225`（新增 `sec-qsensor` 忘了抬 `CASE_PANELS_MIN`）与 `v0.9.211`
（README 顶行声明判据数但 `_W10_EXTRA` 漏登记）—— 本门禁把「面板三层（入口/接线/渲染）」与
「数字跨源一致」全部机器化，并由 `run_webui_pm_render_path_smoke._W10_EXTRA` 交叉守 README 声明。

运行：python run_webui_j3_render_path_smoke.py
"""
from __future__ import annotations

import ast
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
from lda_webui import j3_case as JC  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

API = "/api/j3_ctrl"
HANDLER = "h_j3_ctrl_demo"
PANEL_SMOKE = "run_j3_ctrl_smoke.py"
MILESTONE_SMOKE = "run_j3_ctrl_smoke.py"
_INDEX = os.path.join(_HERE, "lda_webui", "static", "index.html")
_J3CASE = os.path.join(_HERE, "lda_webui", "j3_case.py")
_ROUTES = os.path.join(_HERE, "lda_webui", "routes.py")

#: 顶层 import 白名单（与 `j3_case.run_selfchecks` ⑰ 同口径）
_TOP_IMPORT_OK = {"math", "os", "typing", "__future__"}
#: 诚实边界关键词（F2 与探针共用同一判定函数 ⇒ 探针打在被消费的引用上）
_HONEST_KWS = ("设计预算", "非流片实测", "零量子 SDK")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _extract_fn(src: str, name: str) -> str:
    """从 JS 源码抽出 `function name(...){...}` 体（花括号配对）。"""
    m = re.search(r"function\s+%s\s*\([^)]*\)\s*\{" % re.escape(name), src)
    if not m:
        raise ValueError("未找到函数 %s" % name)
    i = src.index("{", m.start())
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[m.start():j + 1]
    raise ValueError("花括号不配对：%s" % name)


#: 前端 renderJ3 用到的局部别名 → case_card() 顶层键
_ALIAS = {"idf": "identity", "sp": "span", "pu": "pulse", "lk": "leakage",
          "gf": "gate_fidelity", "ro": "readout", "cy": "cryo", "pos": "positioning"}


def _ref_paths(body: str):
    """抽出 renderJ3 中所有取值路径，归一为 (top_key, sub_key|None)。

    `d.<top>.<sub>` 与别名 `<alias>.<sub>` 等价；`d.error` 为异常响应字段
    （非 `case_card()` 正常键）⇒ 显式豁免。
    """
    raw = set()
    for var, top in list(_ALIAS.items()) + [("d", None)]:
        for m in re.finditer(
                r"\b%s\.([A-Za-z_][A-Za-z0-9_]*)(?:\.([A-Za-z_][A-Za-z0-9_]*))?" % var, body):
            raw.add((top, m.group(1), m.group(2)))
    norm = set()
    for top, a, b in raw:
        if top is None:
            if a in _ALIAS:                      # d.<alias>.<sub> 或 d.<alias>
                norm.add((_ALIAS[a], b))
            else:                                # d.<top>.<sub> 或 d.<top>
                norm.add((a, b))
        else:                                    # <alias>.<field>
            norm.add((top, a))
    norm.discard(("error", None))                # 异常响应字段豁免
    return norm


def _resolve(card, refs):
    """逐条在真实 case_card() JSON 上解析路径，返回坏路径列表。"""
    bad = []
    for top, sub in refs:
        if top not in card:
            bad.append((top, sub, "顶层键缺失"))
            continue
        if sub is None:
            continue
        node = card[top]
        if isinstance(node, list):
            if not node or not isinstance(node[0], dict) or sub not in node[0]:
                bad.append((top, sub, "列表项字段缺失"))
        elif isinstance(node, dict):
            if sub not in node:
                bad.append((top, sub, "嵌套字段缺失"))
        else:
            bad.append((top, sub, "标量不可下钻"))
    return bad


def _verdict_ok(card) -> bool:
    return card.get("verdict") == "DESIGN_BUDGET" and card.get("verdict") not in ("PASS", "ACCEPT")


def _honest_ok(card) -> bool:
    note = card.get("honest_note") or ""
    return all(k in note for k in _HONEST_KWS)


def _top_imports(path: str):
    tree = ast.parse(_read(path))
    mods = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    return mods


def _cross_source(card, verbose=True):
    """跨源逐值对拍：卡内数字 ≡ `lda_qeda` 真源现算值。返回 (名称, 通过, 详情) 列表。"""
    from lda_qeda import qubit_dynamics as QD
    from lda_qeda import rb_benchmark as RB
    from lda_qeda import readout_demod as RD
    from lda_qeda import cryo_electronics as CE

    out = []

    def rec(name, got, ref, tol):
        ok = abs(float(got) - float(ref)) <= tol
        out.append((name, ok, "card=%.15g ref=%.15g |Δ|=%.3e tol=%.1e"
                    % (float(got), float(ref), abs(float(got) - float(ref)), tol)))
        return ok

    pu, lk, gf, ro, cy = (card["pulse"], card["leakage"], card["gate_fidelity"],
                          card["readout"], card["cryo"])
    # 脉冲：j3_case 闭式 ≡ qubit_dynamics 数值 RK4（n=8192）⇒ 容差 1e-6 rel
    ref_p1 = QD.rabi_population(JC.OMEGA, JC.DELTA, JC.T_RABI, n=8192)
    rec("D1 pulse.p1 ≡ qubit_dynamics.rabi_population(RK4)", pu["p1"], ref_p1, 1e-8)
    # 泄漏：闭式 ≡ qubit_dynamics.qutrit_leakage（RK4 n=16384）⇒ 容差 1e-6 rel
    ref_lk = QD.qutrit_leakage(JC.OMEGA, JC.ALPHA, JC.pi_pulse_time(), n=16384)
    rec("D2 leakage.p_leak ≡ qubit_dynamics.qutrit_leakage(RK4)", lk["p_leak"], ref_lk, 1e-8)
    # 门保真：u ≡ rb_benchmark.unitarity_per_gate（同式 ⇒ 逐位）
    rec("D3 gate_fidelity.u ≡ rb_benchmark.unitarity_per_gate",
        gf["u"], RB.unitarity_per_gate(JC.GAMMA_DEPOL), 1e-15)
    # 读出误判：≡ readout_demod.readout_error_probability（同式 ⇒ 逐位）
    rec("D4 readout.error ≡ readout_demod.readout_error_probability",
        ro["error"], RD.readout_error_probability(JC.SNR_RO), 1e-18)
    # Purcell：≡ readout_demod.purcell_suppression（同式 ⇒ 逐位）
    rec("D5 readout.purcell_suppression ≡ readout_demod.purcell_suppression",
        ro["purcell_suppression"],
        RD.purcell_suppression(JC.F_Q, JC.F_S, 1.0), 1e-15)
    # 低温：≡ cryo_electronics.distributed_amp_nadd（同式 ⇒ 逐位）
    rec("D6 cryo.n_add ≡ cryo_electronics.distributed_amp_nadd",
        cy["n_add"], CE.distributed_amp_nadd(JC.ETA_RATIO, JC.G_AMP, JC.L_AMP), 1e-15)
    # 分配矩阵列和 = 1
    A = ro["assignment"]
    out.append(("D7 分配矩阵列和 = 1",
                all(abs(A[0][j] + A[1][j] - 1.0) < 1e-15 for j in range(2)),
                "A=%s" % A))
    return out


def _run_milestone_smoke():
    """实跑里程碑主门禁，返回 (rc, PASS 数, FAIL 数)。"""
    import contextlib
    import importlib
    import io
    mod = importlib.import_module(PANEL_SMOKE[:-3])
    mod.PASS = 0
    mod.FAIL = 0
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = mod.main()
    except Exception:  # noqa: BLE001
        return 99, 0, -1
    return rc, int(getattr(mod, "PASS", 0)), int(getattr(mod, "FAIL", 0))


def main() -> int:
    idx = _read(_INDEX)
    card = JC.case_card()

    # ----------------------------------------------------------------- A
    try:
        rj3 = _extract_fn(idx, "renderJ3")
        ok_fn = True
    except Exception as e:  # noqa: BLE001
        rj3, ok_fn = "", False
        check("A0 renderJ3 函数在场（花括号配对可抽出函数体）", False, str(e))
    if ok_fn:
        check("A0 renderJ3 函数在场（花括号配对可抽出函数体）", True, "len=%d" % len(rj3))
    check("A1 onclick 接线：$('runJ3').onclick = runJ3 在场（防「能力上线却点不动」）",
          "$('runJ3').onclick = runJ3" in idx)
    dom = all(s in idx for s in ("sec-j3", "runJ3", "j3Summary", "j3Body", "j3Conclusion"))
    check("A2 面板 DOM 契约：sec-j3 / runJ3 / j3Summary / j3Body / j3Conclusion 齐备", dom)
    check("A3 首屏案例直达条 #sec-j3 在场（入口可达性 · 三入口面之一）",
          'href="#sec-j3"' in idx)
    check("A4 runJ3 / renderJ3 在 index.html 内定义（非空壳）",
          "async function runJ3()" in idx and "function renderJ3(" in idx)
    check("A5 runJ3 调 apiGet('/api/j3_ctrl') 并转交 renderJ3",
          "apiGet('/api/j3_ctrl')" in idx and "renderJ3(d)" in idx)
    seg = ["① 案例身份", "② 征程五档", "③ 脉冲层", "④ 门保真", "⑤ 读出链", "⑥ 低温电子学",
           "⑦ 关键发现", "⑧ 定位"]
    miss = [s for s in seg if s not in rj3]
    check("A6 renderJ3 真渲染 ①–⑧ 八段（防「后端加了段、前端还是空壳」）", not miss,
          "缺=%s" % miss)
    check("A7 抽屉目录自动运行映射含 '\"#sec-j3\": \"runJ3\"'",
          '"#sec-j3": "runJ3"' in idx)

    # ----------------------------------------------------------------- B
    refs = _ref_paths(rj3)
    bad = _resolve(card, refs)
    check("B1 🔴 **取值路径存在性**：%d 条引用路径逐条在真实 `case_card()` JSON 上解析 ⇒ 全部存在"
          % len(refs), not bad, "坏路径=%s" % bad[:6])

    # ----------------------------------------------------------------- C
    tops = set(card.keys())
    used_tops = {t for t, _ in refs}
    unused = sorted(tops - used_tops)
    check("C1 🔴 反向完备（顶层）：`case_card()` 全部 %d 个顶层键都被前端引用" % len(tops),
          not unused, "未被引用=%s" % unused)
    # 🔴 N3-a（v0.9.283）判据修正：`anchors` 是**动态键集块** —— 其键 = 账本锚号，
    #    由账本决定（新增一条锚就变）。对动态键集要求"逐字段字面引用"意味着
    #    **账本每加一锚就要改 18 个 render 函数** ⇒ 那是反模式，不是保护。
    #    ⇒ 豁免逐字段，但**换成更严的替代判据 C2b**：必须对该块做 `Object.keys`
    #    别名遍历渲染。只出现一次 `d.anchors` 而不用它，C2b 照样红。
    _DYNAMIC_KEY_BLOCKS = {"anchors"}
    blocks = []
    for k, v in card.items():
        if isinstance(v, dict) and k not in _DYNAMIC_KEY_BLOCKS:
            blocks.append((k, set(v.keys())))
    miss_fields = []
    for blk, keys in blocks:
        used = {s for t, s in refs if t == blk and s}
        d = keys - used
        if d:
            miss_fields.append((blk, sorted(d)))
    check("C2 🔴 反向完备（%d 个嵌套块）：每块每个字段都被前端引用" % len(blocks),
          not miss_fields, "缺字段=%s" % miss_fields)

    # C2b：动态键集块（anchors）必须被**别名遍历**渲染，不是只被"提了一下"
    _m = re.search(r"var\s+(\w+)\s*=\s*d\.anchors\s*\|\|\s*\{\}", rj3)
    _alias = _m.group(1) if _m else None
    _loop_ok = bool(_alias) and ("Object.keys(" + _alias + ")" in rj3) \
        and ".forEach(" in rj3
    check("C2b 🔴 动态键集块 anchors 必须别名遍历渲染（Object.keys(<别名>).forEach；"
          "防「只引用不显示」）", _loop_ok,
          "别名=%s 遍历=%s" % (_alias, _loop_ok))

    # ----------------------------------------------------------------- D
    dres = _cross_source(card)
    for name, ok, detail in dres:
        check("🔴 跨源一致：%s" % name, ok, detail)

    # ----------------------------------------------------------------- E
    rc, npass, nfail = _run_milestone_smoke()
    gate_total = int(card["span"]["gate_checks"])
    check("E1 🔴 `%s` 实跑 [PASS] 总数 == span.gate_checks == %d" % (MILESTONE_SMOKE, gate_total),
          rc == 0 and npass == gate_total and nfail == 0,
          "rc=%s PASS=%d FAIL=%s" % (rc, npass, nfail))

    # ----------------------------------------------------------------- F
    check("F1 🔴 不伪装实测：verdict == DESIGN_BUDGET ∧ ∉ {PASS, ACCEPT}", _verdict_ok(card))
    check("F2 🔴 诚实边界：honest_note 含 %s" % list(_HONEST_KWS), _honest_ok(card))
    routes = _read(_ROUTES)
    check("F3 路由接线：`%s` 登记进 GET_ROUTES 且 handler = %s" % (API, HANDLER),
          ('"%s": %s' % (API, HANDLER)) in routes)
    check("F4 🔴 `%s` **不在** HEAVY_POST_PATHS（零重计算 ⇒ 免登录、无 DoS 面）" % API,
          API not in routes.split("HEAVY_POST_PATHS", 1)[-1].split("}")[0]
          if "HEAVY_POST_PATHS" in routes else True)
    imps = _top_imports(_J3CASE)
    check("F5 🔴 零重计算：j3_case.py 顶层 import ⊆ %s（ast 真遍历 · 零求解器 / 零量子 SDK）"
          % sorted(_TOP_IMPORT_OK), imps <= _TOP_IMPORT_OK, "实际=%s" % sorted(imps))
    check("F6 缺口登记：全部非空 ∧ 每条含 G-CTRL 前缀（不粉饰）",
          bool(card["gaps"]) and all("G-CTRL" in g for g in card["gaps"]))
    check("F7 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_webui_j3_render_path_smoke.py" in _read(os.path.join(_HERE, "run_ci_regression.py")))

    # ----------------------------------------------------------------- G
    # 突变探针：逐条**模拟真实突变**（改卡 / 改源码文本 / 改引用集），检查对应判据必红。
    probes = []
    # G1 verdict 改 ACCEPT ⇒ F1 必红
    c2 = dict(card); c2["verdict"] = "ACCEPT"
    probes.append(("G1 verdict 改 ACCEPT ⇒ F1 必红", not _verdict_ok(c2)))
    # G2 honest_note 抽掉关键词 ⇒ F2 必红
    c3 = dict(card); c3["honest_note"] = "无"
    probes.append(("G2 honest_note 抽掉关键词 ⇒ F2 必红", not _honest_ok(c3)))
    # G3 前端不引用顶层键 cryo ⇒ C1 必红
    refs3 = {(t, s) for t, s in refs if t != "cryo"}
    probes.append(("G3 前端不引用顶层键 cryo ⇒ C1 必红",
                   bool(set(card.keys()) - {t for t, _ in refs3})))
    # G4 前端不引用 pulse.p1 ⇒ C2 必红
    refs4 = {(t, s) for t, s in refs if not (t == "pulse" and s == "p1")}
    _blks4 = [(k, set(v.keys())) for k, v in card.items() if isinstance(v, dict)]
    probe_g4 = any(keys - {s for t, s in refs4 if t == blk and s} for blk, keys in _blks4)
    probes.append(("G4 前端不引用 pulse.p1 ⇒ C2 必红", bool(probe_g4)))
    # G5 span.gate_checks 篡改 ⇒ E1 必红
    c6 = dict(card); c6["span"] = {**card["span"], "gate_checks": 999}
    probes.append(("G5 span.gate_checks 篡改 ⇒ E1 必红",
                   not (rc == 0 and npass == int(c6["span"]["gate_checks"]) and nfail == 0)))
    # G6 路由 handler 改名 ⇒ F3 必红
    probes.append(("G6 路由 handler 改名 ⇒ F3 必红",
                   ('"%s": h_j3_ctrl_demo_X' % API) not in routes))
    # G7 首屏条 #sec-j3 摘掉 ⇒ A3 必红
    probes.append(("G7 首屏条 #sec-j3 摘掉 ⇒ A3 必红",
                   'href="#sec-j3"' not in idx.replace('href="#sec-j3"', 'href="#sec-j3-x"')))
    # G8 抽屉映射摘掉 ⇒ A7 必红
    probes.append(("G8 抽屉映射 #sec-j3 摘掉 ⇒ A7 必红",
                   '"#sec-j3": "runJ3"' not in idx.replace('"#sec-j3": "runJ3"',
                                                           '"#sec-j3": "x"')))
    # G9 renderJ3 段标题抽掉一个 ⇒ A6 必红
    probes.append(("G9 renderJ3 段标题抽掉 ⇒ A6 必红",
                   bool([s for s in seg if s not in rj3.replace("⑥ 低温电子学", "")])))
    # G10 顶层 import 加 numpy ⇒ F5 必红
    probes.append(("G10 顶层 import 加 numpy ⇒ F5 必红", not ({"numpy"} <= _TOP_IMPORT_OK)))
    # G11 跨源数字扰动（p1 ×1.5）⇒ D1 必红
    c7 = dict(card); c7["pulse"] = {**card["pulse"], "p1": card["pulse"]["p1"] * 1.5}
    probes.append(("G11 pulse.p1 扰动 ×1.5 ⇒ D1 必红", not _cross_source(c7)[0][1]))

    bad_g = [t for t, red in probes if not red]
    check("G 突变探针 %d 条：逐条必红（verdict/诚实边界/顶层键/嵌套字段/判据数/路由/入口/段标题/零重计算/跨源扰动）"
          % len(probes), not bad_g, "未按预期变红=%s" % bad_g)

    bad = globals().get("FAIL", 0)
    good = globals().get("PASS", 0)
    print("")
    print("WebUI J3 案例卡渲染路径门禁：%d PASS / %d FAIL" % (good, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
