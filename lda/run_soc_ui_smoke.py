# -*- coding: utf-8 -*-
"""光子计算 SoC 案例卡（/api/soc_demo · #sec-soc）跨源一致性 + 前端取值路径门禁。

═══════════════════════════════════════════════════════════════
为什么需要这道门禁（A 档接入的「定稿数字必须真模块现算」纪律）
═══════════════════════════════════════════════════════════════
`lda/lda_webui/soc_case.py` 是**只读案例卡数据源**，顶层只 `import json/math/os/typing`
（保持端点零重计算、无 DoS 面）。但它的定稿数字（WDM λ0 / 栅格 / tol、TDM 帧数 / tol、
MZI 计数闭式）必须与**真源模块**（`lda/lda_l2/soc_wdm.py`、`soc_tdm.py`）逐位同源 ——
否则会出现「卡内数字漂离真源、却无人发现」的静默债（同血案 #32「后端有值 ≠ 前端问对地方」
的跨层变体：这里是「卡内常量 ≠ 求解器真源」）。

本门禁分三节：
B 跨源一致性：卡内 LEVERS 常量 ≡ lda_l2 真源模块常量（含反向探针：改真源必红）。
C 端点 + 前端取值路径：/api/soc_demo 已接线、#sec-soc 三入口面齐备（首屏条/hash 深链/
   运行按钮→renderSoc），且 verdict 恒 DESIGN_SIGNOFF（非 ACCEPT/PASS）。
D 红线（外部对拍，防 soc_case 自检被绕过）：零外部光学 SDK / 零能效键 / 诚实边界齐全。
K 自入 CI core（防静默漏接 · 血案 #28）。

设计：**纯文本解析 + 轻量 import**，零浏览器、零网络；跨源对拍只取模块级常量（不跑仿真）。
"""
from __future__ import annotations

import io
import os
import re
import sys
from lda_harness.smoke_kit import make_result_collector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "lda", "lda_webui", "static")
ROUTES = os.path.join(ROOT, "lda", "lda_webui", "routes.py")
SOC_CASE = os.path.join(ROOT, "lda", "lda_webui", "soc_case.py")
CI_REG = os.path.join(ROOT, "lda", "run_ci_regression.py")

# ── 真源模块（跨源对拍目标）────────────────────────────────────────────
try:
    from lda.lda_webui import soc_case as sc  # type: ignore
except Exception:  # pragma: no cover
    from lda_webui import soc_case as sc  # type: ignore

try:
    from lda.lda_l2 import soc_wdm as _wdm  # type: ignore
except Exception:  # pragma: no cover
    _wdm = None
try:
    from lda.lda_l2 import soc_tdm as _tdm  # type: ignore
except Exception:  # pragma: no cover
    _tdm = None

_results: list[tuple[str, bool, str]] = []
check = make_result_collector(_results)


def read_text(path: str) -> str:
    return io.open(path, encoding="utf-8").read()


# ───────────────────────── B 跨源一致性（卡内 ≡ 真源）─────────────────────────
def _wdm_ok() -> bool:
    """卡内 WDM 杠杆常量 ≡ soc_wdm 真源（AND）。"""
    if _wdm is None:
        return False
    lv = sc.LEVERS["wdm"]
    return (abs(lv["lambda0_um"] - _wdm.LAMBDA0_UM) < 1e-12
            and abs(lv["channel_spacing_um"] - _wdm.WDM_CHANNEL_SPACING_UM) < 1e-15
            and abs(lv["mvm_tol"] - _wdm.WDM_TOL_MVM_REL) < 1e-12)


def _tdm_ok() -> bool:
    """卡内 TDM 杠杆常量 ≡ soc_tdm 真源（AND）。"""
    if _tdm is None:
        return False
    lv = sc.LEVERS["tdm"]
    return (lv["default_frames"] == _tdm.TDM_DEFAULT_FRAMES
            and abs(lv["mvm_tol"] - _tdm.TDM_TOL_MVM_REL) < 1e-12)


def main() -> int:
    print("=" * 74)
    print("光子计算 SoC 案例卡 跨源一致性 + 前端取值路径门禁（v0.9.214 · 含交互式 tiling 预览）")
    print("=" * 74)

    # ── B 跨源一致性 ───────────────────────────────────────────────
    if _wdm is None or _tdm is None:
        check("B0 真源模块可 import（soc_wdm / soc_tdm）", False,
              "soc_wdm=%r soc_tdm=%r" % (_wdm is not None, _tdm is not None))
        return _report()
    check("B0 真源模块可 import（soc_wdm / soc_tdm）", True)

    check("B1 WDM λ0 = soc_wdm.LAMBDA0_UM（1.55µm · C 波段）",
          abs(sc.LEVERS["wdm"]["lambda0_um"] - _wdm.LAMBDA0_UM) < 1e-12,
          "card=%r src=%r" % (sc.LEVERS["wdm"]["lambda0_um"], _wdm.LAMBDA0_UM))
    check("B2 WDM 栅格 = soc_wdm.WDM_CHANNEL_SPACING_UM（0.0008µm · 100GHz ITU）",
          abs(sc.LEVERS["wdm"]["channel_spacing_um"] - _wdm.WDM_CHANNEL_SPACING_UM) < 1e-15,
          "card=%r src=%r" % (sc.LEVERS["wdm"]["channel_spacing_um"],
                              _wdm.WDM_CHANNEL_SPACING_UM))
    check("B3 WDM MVM tol = soc_wdm.WDM_TOL_MVM_REL（0.05）",
          abs(sc.LEVERS["wdm"]["mvm_tol"] - _wdm.WDM_TOL_MVM_REL) < 1e-12,
          "card=%r src=%r" % (sc.LEVERS["wdm"]["mvm_tol"], _wdm.WDM_TOL_MVM_REL))
    check("B4 TDM 默认帧 = soc_tdm.TDM_DEFAULT_FRAMES（4）",
          sc.LEVERS["tdm"]["default_frames"] == _tdm.TDM_DEFAULT_FRAMES,
          "card=%r src=%r" % (sc.LEVERS["tdm"]["default_frames"], _tdm.TDM_DEFAULT_FRAMES))
    check("B5 TDM MVM tol = soc_tdm.TDM_TOL_MVM_REL（0.05）",
          abs(sc.LEVERS["tdm"]["mvm_tol"] - _tdm.TDM_TOL_MVM_REL) < 1e-12,
          "card=%r src=%r" % (sc.LEVERS["tdm"]["mvm_tol"], _tdm.TDM_TOL_MVM_REL))

    # B6 闭式：MZI 计数 N(N−1)/2 与 VERIFIED_SIZES 权威档逐位同源
    ok6 = all(sc.reck_mzi_count(k) == k * (k - 1) // 2 for k in range(2, 129))
    ok6 = ok6 and (sc.VERIFIED_SIZES[0]["mzi"] == sc.reck_mzi_count(16)
                   and sc.VERIFIED_SIZES[1]["mzi"] == sc.reck_mzi_count(64)
                   and sc.VERIFIED_SIZES[2]["mzi"] == sc.reck_mzi_count(128))
    check("B6 MZI 计数闭式 N(N−1)/2 ≡ 实测档（120/2016/8128）", ok6,
          "16=%d 64=%d 128=%d" % (sc.reck_mzi_count(16), sc.reck_mzi_count(64),
                                  sc.reck_mzi_count(128)))

    # 🔴 B8 前端闭式同源：index.html 的 socTilingMzi(n) ≡ 后端 reck_mzi_count(N(N−1)/2)
    #    （防前端预览把 MZI 数硬编码/漂离真源 —— 跨层变体：卡内常量≠真源）
    _html_b8 = read_text(os.path.join(STATIC, "index.html"))
    _mzi_fn = re.search(r'function\s+socTilingMzi\(n\)\s*\{\s*return\s*([^;]+);', _html_b8)
    ok8 = False
    _d8 = "未匹配 socTilingMzi"
    if _mzi_fn:
        _expr = _mzi_fn.group(1).strip()
        _closed = "n*(n-1)/2" in _expr.replace(" ", "")
        try:
            ok8 = _closed and all(
                abs(eval(_expr, {"__builtins__": {}}, {"n": k}) - k * (k - 1) // 2) < 1e-9
                for k in (2, 8, 16, 64, 128))
            _d8 = "expr=%r 同源=%s" % (_expr, ok8)
        except Exception as e:  # pragma: no cover
            _d8 = "eval error: %s" % e
    check("B8 前端 socTilingMzi(n) 闭式 ≡ 后端 reck_mzi_count(N(N−1)/2)（同源对拍）",
          ok8, _d8)

    # 🔴 B7 反向完备：改真源常量 ⇒ 跨源判据必红（证守卫读真源、非硬编码镜像）
    _orig_lam = _wdm.LAMBDA0_UM
    _orig_tol = _tdm.TDM_TOL_MVM_REL
    normal = _wdm_ok() and _tdm_ok()
    _wdm.LAMBDA0_UM = 9.99
    _tdm.TDM_TOL_MVM_REL = 0.77
    patched = _wdm_ok() and _tdm_ok()
    _wdm.LAMBDA0_UM = _orig_lam
    _tdm.TDM_TOL_MVM_REL = _orig_tol
    check("B7 反向：真源常量被篡改 ⇒ 跨源判据必红（守卫读真源非镜像）",
          normal and (not patched),
          "normal=%s patched=%s" % (normal, patched))

    # ── C 端点 + 前端取值路径 ─────────────────────────────────────
    routes_src = read_text(ROUTES)
    c1 = '/api/soc_demo' in routes_src and 'h_soc_demo' in routes_src
    check("C1 端点 /api/soc_demo 已接线 GET_ROUTES + handler h_soc_demo", c1)

    html = read_text(os.path.join(STATIC, "index.html"))
    # C2：首屏 #wbCaseBar 含 #sec-soc 直达（第一种入口面）
    bar = re.search(r'id="wbCaseBar".{0,12000}?</div>', html, re.S)
    bar_hrefs = re.findall(r'href="(#[^"]+)"', bar.group(0)) if bar else []
    c2 = "#sec-soc" in bar_hrefs
    check("C2 首屏 #wbCaseBar 含 #sec-soc 直达条目（入口面①）", c2,
          "bar 条目=%s" % (bar_hrefs or "无"))

    # C3：hash 深链 CASE_MAP 含 "#sec-soc": "runSoc"（入口面②）
    cmap = re.search(r'var\s+CASE_MAP\s*=\s*\{(.*?)\}\s*;', html, re.S)
    cmap_pairs = dict(re.findall(r'"(#sec-[A-Za-z0-9_]+)"\s*:\s*"(run\w+)"',
                                 cmap.group(1) if cmap else ""))
    c3 = cmap_pairs.get("#sec-soc") == "runSoc"
    check("C3 hash 深链 CASE_MAP 含 #sec-soc → runSoc（入口面②）", c3,
          "got=%r" % cmap_pairs.get("#sec-soc"))

    # C4：运行按钮 + renderSoc 函数存在（入口面③ 点击→渲染路径）
    c4 = ('id="runSoc"' in html) and ('function runSoc(' in html) and ('function renderSoc(' in html)
    check("C4 面板运行按钮 id=runSoc + runSoc/renderSoc 函数存在（点击→渲染路径）", c4)

    # C5：面板 data-stage=accept（抽屉收集归阶段正确）
    c5 = 'id="sec-soc"' in html and 'data-stage="accept"' in html
    check("C5 #sec-soc 面板带 data-stage=accept（抽屉归阶段正确）", c5)

    # C6：verdict 恒 DESIGN_SIGNOFF（非 ACCEPT/PASS —— 明标设计&验证能力证明）
    card = sc.case_card()
    c6 = card["verdict"] == "DESIGN_SIGNOFF"
    check("C6 verdict 恒 DESIGN_SIGNOFF（非 ACCEPT/PASS）", c6, "verdict=%r" % card["verdict"])

    # 🔴 C7 反向：摘掉 CASE_MAP 的 #sec-soc 映射 ⇒ C3 必红（深链断线回归）
    if cmap is not None:
        m7 = re.sub(r'"#sec-soc"\s*:\s*"runSoc"', "", html, count=1)
        cm7 = re.search(r'var\s+CASE_MAP\s*=\s*\{(.*?)\}\s*;', m7, re.S)
        cm7_pairs = dict(re.findall(r'"(#sec-[A-Za-z0-9_]+)"\s*:\s*"(run\w+)"',
                                    cm7.group(1) if cm7 else ""))
        c7 = cm7_pairs.get("#sec-soc") != "runSoc"
    else:
        c7 = False
    check("C7 反向：摘掉 CASE_MAP 的 #sec-soc 映射 ⇒ C3 必红（深链断线回归）", c7)

    # ── D 红线（外部对拍，防 soc_case 自检被绕过）────────────────────
    sc_src = read_text(SOC_CASE).lower()
    banned = ("numpy", "scipy", "meep", "tidy3d", "lumerical", "torch",
              "tensorflow", "jax", "lda_l2")
    hit = [b for b in banned if ("import " + b) in sc_src or ("from " + b) in sc_src]
    check("D1 零外部光学 SDK / 零 numpy / 零 lda_l2：soc_case 无任何求解器 import", not hit,
          "命中=%s" % (hit or "无"))

    energy_keys = ("tops_w", "power_w", "pj_per_mac", "pj_per_bit",
                   "flops_per_watt", "top_s_w", "w_per_mac")
    flat = __import__("json").dumps(card).lower()
    hit_e = [k for k in energy_keys if k in flat]
    check("D2 零能效数字：案例卡返回体不含任何能效键", not hit_e, "命中=%s" % (hit_e or "无"))

    note = sc.SOC_HONEST_NOTE
    d3 = ("非流片后实测" in note and "不报任何 fabricated 能效" in note
          and "设计容量" in note and "NDA 真值本机不持有" in note)
    check("D3 诚实边界齐全：含「非流片后实测」/「不报任何 fabricated 能效」/"
          "「设计容量」/「NDA 真值本机不持有」", d3)

    # ── K 自入 CI core ───────────────────────────────────────────
    ck = read_text(CI_REG)
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_soc_ui_smoke.py" in ck)

    return _report()


def _report() -> int:
    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    print()
    for name, ok, detail in _results:
        print("  [%s] %s%s" % ("PASS" if ok else "FAIL", name,
                               ("   (%s)" % detail) if (detail and not ok) else ""))
    print()
    print("RESULT: %d PASS / %d FAIL" % (npass, nfail))
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
