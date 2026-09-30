#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""光计算芯片案例卡门禁（WebUI 只读端点 /api/pchip_demo · M5 收尾）。

═══ 判什么（分六节）═══
A 模块自检（pchip_case.run_selfchecks 13 项）· B 关键事实 name-first 断言 ·
C 反向可证伪（突变探针：破坏诚实边界 ⇒ 必红）·
D 不进 HEAVY_POST_PATHS（公开只读 · 零重计算）·
E API 参考已登记（gen_api_reference 已跑 · 血案 23 防双红）·
K 自入 CI core（防静默漏接 · 血案 28）。

🔴 本门禁的核心价值：守 WebUI 对外案例卡的**诚实边界**——verdict 恒 DESIGN_SIGNOFF、
不报 fabricated 能效、规模按「设计容量」解读。任一被静默改坏 ⇒ C 组突变探针必红。
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
    """文本读文件（不 import 模块 ⇒ 不拉 numpy，避免 routes 顶层依赖拽不动）。"""
    fp = os.path.join(_ROOT, rel)
    if not os.path.exists(fp):
        return ""
    with open(fp, encoding="utf-8", errors="replace") as f:
        return f.read()


def main() -> int:
    from lda_webui import pchip_case as PC

    # ══════════════════════ A 模块自检 ══════════════════════
    ok_a = PC.run_selfchecks(verbose=False)
    check("A1 模块自检 13/13 PASS（闭式/规模盲/tiling/EO/组装/降级/诚实/定位/口径/"
          "零SDK/零能效/护栏）", ok_a)

    # ══════════════════════ B 关键事实（name-first）══════════════════════
    card = PC.case_card(repo_root="__nonexistent_root__")
    check("B1 endpoint == /api/pchip_demo", card["endpoint"] == "/api/pchip_demo")
    check("B2 verdict == DESIGN_SIGNOFF（非 ACCEPT/PASS）",
          card["verdict"] == "DESIGN_SIGNOFF")
    check("B3 五段征程（M1→M5）", len(card["milestones"]) == 5)
    check("B4 关键结论 5 条", len(card["findings"]) == 5)
    check("B5 诚实边界 7 条", card["gaps_total"] == 7)
    check("B6 规模盲 ratio 相对标准差 = 0.0766（随 N 不塌缩）",
          abs(card["flagship"]["scale_blind_ratio_rel_std"] - 0.0766) < 1e-9)
    check("B7 tiling 局部标定增益 = 2.8×",
          abs(card["flagship"]["tiling_gain"] - 2.8) < 1e-9)
    check("B8 EO Vπ+5% 未标定 83.3% → 标定 100%",
          abs(card["eo_chain"]["eo_vpi_mismatch_acc"] - 0.833) < 1e-9
          and abs(card["eo_chain"]["eo_vpi_cal_acc"] - 1.0) < 1e-9)
    check("B9 零外部光学 SDK 声明", card["identity"]["zero_optical_sdk"] is True)
    check("B10 8 条 A 级公开 landmark（Lightmatter/MIT/清华/AIP/Ayar）",
          len(card["public_landmarks"]) == 8)

    # ══════════════════════ C 反向可证伪（突变探针）═══════════════════════
    # C1 破坏 honest_note 关键字 ⇒ ⑧ 必红
    saved_note = PC.PCHIP_HONEST_NOTE
    PC.PCHIP_HONEST_NOTE = saved_note.replace("非流片后实测", "")
    ok_c1 = PC.run_selfchecks(verbose=False)
    PC.PCHIP_HONEST_NOTE = saved_note
    check("C1 反向：移除「非流片后实测」字样 ⇒ ⑧ 判定必红（run_selfchecks False）",
          ok_c1 is False)

    # C2 清空公开 landmark ⇒ ⑨ 必红
    saved_lm = PC.PUBLIC_LANDMARKS
    PC.PUBLIC_LANDMARKS = []
    ok_c2 = PC.run_selfchecks(verbose=False)
    PC.PUBLIC_LANDMARKS = saved_lm
    check("C2 反向：清空公开 landmark ⇒ ⑨ 判定必红（run_selfchecks False）",
          ok_c2 is False)

    # ══════════════════════ D 免登录 / 零重计算（文本解析 routes.py，不 import 以防 numpy 拉不动）═══════════════════════
    rt = _read("lda/lda_webui/routes.py")
    # D1 不进 HEAVY_POST_PATHS（公开只读 · 零重计算 · 无 DoS 面）
    heavy = rt.split("HEAVY_POST_PATHS = {")[1].split("}")[0] if "HEAVY_POST_PATHS = {" in rt else ""
    check("D1 端点不进 HEAVY_POST_PATHS（公开只读 · 零重计算 · 无 DoS 面）",
          "/api/pchip_demo" not in heavy)
    # D2 GET 端点（不是 POST）—— 与 qchip/schip 同属公开只读类
    get_block = rt.split("GET_ROUTES = {")[1].split("}")[0] if "GET_ROUTES = {" in rt else ""
    check("D2 GET 端点接线（\"/api/pchip_demo\": h_pchip_demo, 在 GET_ROUTES）",
          '"/api/pchip_demo": h_pchip_demo,' in get_block)
    # D3 零重计算：pchip_case 模块不 import 求解器/P&R/numpy
    src_pc = _read("lda/lda_webui/pchip_case.py")
    check("D3 🔴 零重计算：pchip_case 不 import 求解器/P&R/numpy（纯静态闭式 + 诚实边界）",
          all(k not in src_pc.split("def run_selfchecks")[0]
              for k in ("import lda_l2", "import lda_layout", "import lda_pdk",
                        "import numpy", "from lda_l2", "from lda_layout",
                        "from lda_pdk", "from numpy")))

    # ══════════════════════ E API 参考已登记（gen_api_reference 已跑）═══════════════════════
    jp = os.path.join(_ROOT, "docs", "api_reference.json")
    try:
        ref = json.load(open(jp, encoding="utf-8"))
        ep = next((e for e in ref["endpoints"] if e["path"] == "/api/pchip_demo"), None)
        ok_ep = bool(ep) and ep["auth"] == "public" and bool(ep["description"])
        check("E1 API 参考已含 /api/pchip_demo 且 auth=public（gen 已跑 · 防 ⑤⑦ 双红）",
              ok_ep, "found=%s auth=%s" % (ep is not None, ep["auth"] if ep else "?"))
    except Exception as e:  # pragma: no cover
        check("E1 API 参考已含 /api/pchip_demo", False, "读参考失败: %s" % e)

    # ══════════════════════ K 自入 CI core（防静默漏接 · 血案 28）═══════════════════════
    try:
        import run_ci_regression as R  # noqa: E402,F401
        in_core = "run_pchip_case_smoke.py" in R.CORE_SMOKES
        check("K1 本 smoke 已登记进 CI core（CORE_SMOKES）", in_core,
              "len=%d" % len(R.CORE_SMOKES))
    except Exception as e:  # pragma: no cover
        check("K1 本 smoke 已登记进 CI core（CORE_SMOKES）", False,
              "import 失败: %s" % e)

    # make_check 仅在「有失败」时才写 ns["FAIL"]；全 PASS 时该键不存在 ⇒ 用
    # globals().get 兜底（血案：全绿反而 NameError）。ns 即模块 globals 字典。
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
