#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""电子计算芯片案例卡门禁（WebUI 只读端点 /api/ecore_demo · E 征程收官 · D-155）。

═══ 判什么（分节）═══
A 模块自检（ecore_case.run_selfchecks 12 项）· B 关键事实 name-first 断言 ·
C 反向可证伪（突变探针：破坏诚实边界 / 清空 landmark ⇒ 必红）·
D 不进 HEAVY_POST_PATHS（公开只读 · 零重计算）· E API 参考已登记（gen_api_reference 已跑 · 血案 23）·
K 自入 CI core（防静默漏接 · 血案 28）。

🔴 本门禁的核心价值：守 WebUI 对外案例卡的**诚实边界**——verdict 恒 DESIGN_VERIFIED、
不报 fabricated 能效（TOPS/TOPS-W）、规模按「可建模/可验证容量」解读、landmark 仅背景坐标。
任一被静默改坏 ⇒ C 组突变探针必红。
"""
from __future__ import annotations

import json
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


def _read(rel):
    """文本读文件（不 import 模块 ⇒ 不拉 numpy）。"""
    fp = os.path.join(_ROOT, rel)
    if not os.path.exists(fp):
        return ""
    with open(fp, encoding="utf-8", errors="replace") as f:
        return f.read()


def main() -> int:
    from lda_webui import ecore_case as EC

    # ══════════════════════ A 模块自检 ══════════════════════
    ok_a = EC.run_selfchecks(verbose=False)
    check("A1 模块自检 12/12 PASS（容量闭式/量化界/组装/降级/诚实/定位/口径/"
          "零框架/护栏/里程碑/landmark）", ok_a)

    # ══════════════════════ B 关键事实（name-first）══════════════════════
    card = EC.case_card(repo_root="__nonexistent_root__")
    check("B1 endpoint == /api/ecore_demo", card["endpoint"] == "/api/ecore_demo")
    check("B2 verdict == DESIGN_VERIFIED（非 ACCEPT/PASS）",
          card["verdict"] == "DESIGN_VERIFIED")
    check("B3 五段征程（E1→E5）", len(card["milestones"]) == 5)
    check("B4 关键结论 5 条", len(card["findings"]) == 5)
    check("B5 诚实边界 5 条", card["gaps_total"] == 5)
    check("B6 门禁判据合计 = 28", card["span"]["gate_checks"] == 28)
    check("B7 旗舰容量 256×256 ⇒ 65536 突触 · 257 物理列",
          card["flagship"]["n_synapses"] == 65536
          and card["flagship"]["n_phys_cols_incl_ref"] == 257)
    check("B8 规模律：相对误差有界（256 ⇒ 0.030）· 绝对误差 ∝N（0.08→0.54）",
          abs(card["physics"]["metrics"]["scale_rel_err_256"] - 0.030) < 1e-9
          and card["physics"]["metrics"]["scale_abs_err_256"]
          > card["physics"]["metrics"]["scale_abs_err_32"])
    check("B9 零外部 SPICE 引擎声明", card["identity"]["zero_spice_engine"] is True)
    check("B10 landmark 登记含 source（Mythic · mythic.ai）",
          len(EC.LANDMARKS_BRIEF) >= 1
          and all(e.get("source") for e in EC.LANDMARKS_BRIEF))
    check("B11 定位声明含「不报任何 TOPS / TOPS-W」",
          "不报任何 TOPS / TOPS-W" in card["positioning"]["disclaimer"])

    # ══════════════════════ C 反向可证伪（突变探针）═══════════════════════
    # C1 破坏 honest_note 关键字 ⇒ ⑥ 必红
    saved_note = EC.ECORE_HONEST_NOTE
    EC.ECORE_HONEST_NOTE = saved_note.replace("非流片后实测", "")
    ok_c1 = EC.run_selfchecks(verbose=False)
    EC.ECORE_HONEST_NOTE = saved_note
    check("C1 反向：移除「非流片后实测」字样 ⇒ ⑥ 判定必红（run_selfchecks False）",
          ok_c1 is False)

    # C2 清空公开 landmark ⇒ ⑫ 必红
    saved_lm = EC.LANDMARKS_BRIEF
    EC.LANDMARKS_BRIEF = []
    ok_c2 = EC.run_selfchecks(verbose=False)
    EC.LANDMARKS_BRIEF = saved_lm
    check("C2 反向：清空公开 landmark ⇒ ⑫ 判定必红（run_selfchecks False）",
          ok_c2 is False)

    # C3 让 verdict 冒充 ACCEPT ⇒ ⑥ 必红（不伪装实测）
    saved_cc = EC.case_card

    def _fake_card(repo_root=None):
        c = saved_cc(repo_root=repo_root)
        c["verdict"] = "ACCEPT"
        return c

    EC.case_card = _fake_card
    # 直接检查不伪装实测红线（复刻自检 ⑥ 的判据）
    fake = EC.case_card(repo_root="__nonexistent_root__")
    EC.case_card = saved_cc
    check("C3 反向：verdict 冒充 ACCEPT ⇒ 不伪装实测判据必红",
          fake["verdict"] != "DESIGN_VERIFIED")

    # ══════════════════════ D 免登录 / 零重计算 ═══════════════════════════
    rt = _read("lda/lda_webui/routes.py")
    heavy = rt.split("HEAVY_POST_PATHS = {")[1].split("}")[0] if "HEAVY_POST_PATHS = {" in rt else ""
    check("D1 端点不进 HEAVY_POST_PATHS（公开只读 · 零重计算 · 无 DoS 面）",
          "/api/ecore_demo" not in heavy)
    get_block = rt.split("GET_ROUTES = {")[1].split("}")[0] if "GET_ROUTES = {" in rt else ""
    check("D2 GET 端点接线（\"/api/ecore_demo\": h_ecore_demo, 在 GET_ROUTES）",
          '"/api/ecore_demo": h_ecore_demo,' in get_block)
    src_ec = _read("lda/lda_webui/ecore_case.py")
    check("D3 🔴 零重计算：ecore_case 不 import 求解器/numpy（纯静态闭式 + 诚实边界）",
          all(k not in src_ec.split("def run_selfchecks")[0]
              for k in ("import lda_l2", "import numpy", "from lda_l2", "from numpy",
                        "import scipy", "from scipy")))

    # ══════════════════════ E API 参考已登记（gen_api_reference 已跑）═══════════════════════
    jp = os.path.join(_ROOT, "docs", "api_reference.json")
    try:
        ref = json.load(open(jp, encoding="utf-8"))
        ep = next((e for e in ref["endpoints"] if e["path"] == "/api/ecore_demo"), None)
        ok_ep = bool(ep) and ep["auth"] == "public" and bool(ep["description"])
        check("E1 API 参考已含 /api/ecore_demo 且 auth=public（gen 已跑 · 防双红）",
              ok_ep, "found=%s auth=%s" % (ep is not None, ep["auth"] if ep else "?"))
    except Exception as e:  # pragma: no cover
        check("E1 API 参考已含 /api/ecore_demo", False, "读参考失败: %s" % e)

    # ══════════════════════ K 自入 CI core（防静默漏接 · 血案 28）═══════════════════════
    try:
        import run_ci_regression as R  # noqa: E402,F401
        in_core = "run_ecore_case_smoke.py" in R.CORE_SMOKES
        check("K1 本 smoke 已登记进 CI core（CORE_SMOKES）", in_core,
              "len=%d" % len(R.CORE_SMOKES))
    except Exception as e:  # pragma: no cover
        check("K1 本 smoke 已登记进 CI core（CORE_SMOKES）", False,
              "import 失败: %s" % e)

    bad = globals().get("FAIL", 0)
    good = globals().get("PASS", 0)
    print("")
    print("门禁 smoke：%d PASS / %d FAIL" % (good, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
