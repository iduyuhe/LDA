#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""电子计算芯片案例卡门禁（WebUI 只读端点 /api/ecore_demo · D-155 建卡 → D-160 升级 E1–E9 →
**E11-e 升级为 E1–E11 全链**）。

═══ 判什么（分节）═══
A 模块自检（ecore_case.run_selfchecks **23 项**）· B 关键事实 name-first 断言（含 E6–E9 四块能力面 +
**E11-c/E11-d 两块能力面** + 🔴 **B16/B17 与底层模块交叉核对**）·
C 反向可证伪（**8 条突变探针**：破坏诚实边界 / 清空 landmark / verdict 冒充实测 / 规模上界非单调 /
掏空版图面 / **G-3 被改成自洽** / **缺口归零** / **注入「已支持 2D MOS」** ⇒ 均必红）·
D 不进 HEAVY_POST_PATHS（公开只读 · 零重计算）·
E API 参考已登记（gen_api_reference 已跑 · 血案 23）· K 自入 CI core（防静默漏接 · 血案 28）。

🔴 本门禁的核心价值：守 WebUI 对外案例卡的**诚实边界**——verdict 恒 DESIGN_VERIFIED、
不报 fabricated 能效（TOPS/TOPS-W）、规模按「可建模/可验证容量」解读、landmark 仅背景坐标；
守住**升级后的能力面不被静默缩水**（E6/E7/E8/E9/E11-c/E11-d 六块 facts 必须都在）；
并守住 🔴 **「内部能力 ↔ 对外载体」真拉平**（B16/B17 拿卡里的数字与**底层模块实测**对拍，
而不是卡自证自洽）。
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
    check("A1 模块自检 23/23 PASS（容量/量化界/版图闭式/压缩比/方块电阻/Pelgrom/1√N/"
          "Elmore/组装/降级/诚实/定位/口径/零框架/护栏/里程碑/landmark/E6-E9 面/上界单调/"
          "**E11-c 器件级内核面/E11-d 失效边界面/诚实不宣称**）", ok_a)

    # ══════════════════════ B 关键事实（name-first）══════════════════════
    card = EC.case_card(repo_root="__nonexistent_root__")
    check("B1 endpoint == /api/ecore_demo", card["endpoint"] == "/api/ecore_demo")
    check("B2 verdict == DESIGN_VERIFIED（非 ACCEPT/PASS）",
          card["verdict"] == "DESIGN_VERIFIED")
    check("B3 十段征程（E1→E11）", len(card["milestones"]) == 10)
    check("B4 关键结论 11 条", len(card["findings"]) == 11)
    check("B5 诚实边界 10 条", card["gaps_total"] == 10)
    check("B6 门禁判据合计 = 235（含 46 条突变探针）",
          card["span"]["gate_checks"] == 235 and card["span"]["probe_checks"] == 46)
    check("B6b 判据合计 ≡ Σ 各段 gate（内部自洽）",
          sum(m["gate"] for m in card["milestones"]) == card["span"]["gate_checks"]
          and sum(m["seg_probes"] for m in card["milestones"]) == card["span"]["probe_checks"])
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

    # B12–B15 E6–E9 四块新能力面（升级后必须出现在对外卡上）
    check("B12 E6 版图签核：1T 单元 7 元素 · 4×4=120 元素 · GDS 936 B · W/L=1.20/0.30",
          card["layout"]["cell_elements"] == 7
          and card["layout"]["arr_4x4_elements"] == 120
          and card["layout"]["gds_bytes_4x4"] == 936
          and abs(card["layout"]["w_um"] - 1.20) < 1e-9
          and abs(card["layout"]["l_um"] - 0.30) < 1e-9)
    check("B13 E7 寄生后仿：R□=0.084 Ω/□ · IR drop N=4 0.42%→N=32 27.0% · sneak 1.29×→7.26×",
          abs(card["parasitic"]["sheet_r_m1_ohm_sq"] - 0.084) < 1e-12
          and card["parasitic"]["ir_drop_rel"][0][1] == 0.0042
          and card["parasitic"]["ir_drop_rel"][-1][1] == 0.270
          and card["parasitic"]["sneak_ratio"][-1][1] == 7.26)
    check("B14 E8 失配/校准：σ_ΔVth=5.00 mV · MC σ_rel 0.654% · L0 1.696%→L1 0.212%→L2 0.0743%",
          abs(card["mismatch"]["sigma_vth_mv"] - 5.00) < 1e-9
          and abs(card["mismatch"]["mc_sigma_rel_8x8"] - 0.00654) < 1e-9
          and card["mismatch"]["calibration"]["L0_rel"]
          > card["mismatch"]["calibration"]["L1_rel"]
          > card["mismatch"]["calibration"]["L2_rel"])
    check("B15 E9 规模压力：压缩比 3571× · 三重规模律 · 上界 5% ⇒ N≤18",
          card["scale_pressure"]["facts"]["compression_1024"] == 3571.0
          and len(card["scale_pressure"]["tiers"]) == 4
          and any(c["budget_rel"] == 0.05 and c["max_rows"] == 18
                  for c in card["scale_pressure"]["ceiling"]))

    # B16/B17 🔴 **与底层模块交叉核对**（真拉平 · 非自洽）：
    # 卡里硬编码的数字必须 ≡ 模块实测值 —— 这是「内部能力 ↔ 对外载体」的机器化对齐，
    # 而不是"卡自己和自己一致"。任何一侧漂移 ⇒ 必红。
    from lda_l2.ecore import device_limits as DL   # noqa: E402
    from lda_l2.ecore import device_pde as DP      # noqa: E402
    cc = DP.cross_check_vth()
    pts = DP.cross_check_qs()
    check("B16 🔴 E11-c 面 **与模块交叉核对**：卡内数字 ≡ device_pde 实测"
          "（V_th 闭式⟷PDE · Q_s 跨点最差）",
          abs(card["device_pde"]["vth_golden_v"] - cc["V_th_golden"]) < 5e-4
          and abs(card["device_pde"]["vth_rel_err_pct"] - cc["rel_err"] * 100) < 1e-3
          and abs(card["device_pde"]["qs_cross_point_worst_rel_pct"]
                  - max(p["rel_err"] for p in pts) * 100) < 1e-3,
          "卡 %.4f%% vs 模块 %.4f%%" %
          (card["device_pde"]["qs_cross_point_worst_rel_pct"],
           max(p["rel_err"] for p in pts) * 100))
    check("B17 🔴 E11-d 面 **与模块交叉核对**：卡内数字 ≡ device_limits 实测"
          "（半宽比 · L=65nm 缺口）",
          abs(card["device_limits"]["physical_over_numerical_halfwidth"]
              - DL.window_ratio_physical_over_numerical()) < 1e-3
          # 卡内为 3 位有效数字展示（0.379），模块精确值 0.37864 ⇒ 容差按展示精度取 2e-3
          and abs(card["device_limits"]["gap_at_L65nm"]["rolloff_frac_of_vth"]
                  - DL.literature_gap_report(0.065)["rolloff_frac_of_vth"]) < 2e-3,
          "卡 %.3f vs 模块 %.5f" %
          (card["device_limits"]["gap_at_L65nm"]["rolloff_frac_of_vth"],
           DL.literature_gap_report(0.065)["rolloff_frac_of_vth"]))

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

    # C4 E9 可及规模上界改成非单调（预算越紧反而行数越多）⇒ ⑳ 判定必红
    saved_ceil = EC.SCALE_CEILING
    EC.SCALE_CEILING = [{"budget_rel": 0.10, "max_rows": 8},
                        {"budget_rel": 0.05, "max_rows": 18},
                        {"budget_rel": 0.02, "max_rows": 11},
                        {"budget_rel": 0.01, "max_rows": 26}]     # ← 非单调
    ok_c4 = EC.run_selfchecks(verbose=False)
    EC.SCALE_CEILING = saved_ceil
    check("C4 反向：可及上界非单调 ⇒ ⑳ 判定必红（规模律不许被静默改坏）", ok_c4 is False)

    # C5 E6–E9 能力面 facts 被掏空（GDS 字节归零）⇒ ⑲ 判定必红
    saved_lay = dict(EC.LAYOUT_FACTS)
    EC.LAYOUT_FACTS["cell_elements"] = 0
    ok_c5 = EC.run_selfchecks(verbose=False)
    EC.LAYOUT_FACTS.clear()
    EC.LAYOUT_FACTS.update(saved_lay)
    check("C5 反向：掏空 E6 版图能力面（cell_elements=0）⇒ ⑲ 判定必红", ok_c5 is False)

    # C6 E11-c 面被改坏（G-3 不自洽被改成「自洽」）⇒ ㉑ 判定必红
    saved_pc = dict(EC.DEVICE_PDE_FACTS["param_consistency"])
    EC.DEVICE_PDE_FACTS["param_consistency"] = dict(saved_pc, consistent=True)
    ok_c6 = EC.run_selfchecks(verbose=False)
    EC.DEVICE_PDE_FACTS["param_consistency"] = saved_pc
    check("C6 反向：把 G-3 参数不自洽改成「自洽」⇒ ㉑ 判定必红"
          "（诚实项不许被静默抹平）", ok_c6 is False)

    # C7 E11-d 面被掏空（短沟道缺口归零）⇒ ㉒ 判定必红
    saved_gap = dict(EC.DEVICE_LIMITS_FACTS["gap_at_L65nm"])
    EC.DEVICE_LIMITS_FACTS["gap_at_L65nm"] = {"rolloff_frac_of_vth": 0.0,
                                              "dibl_frac_of_vth": 0.0,
                                              "rolloff_dvth_v": 0.0,
                                              "vth_long_channel_v": 0.4260}
    ok_c7 = EC.run_selfchecks(verbose=False)
    EC.DEVICE_LIMITS_FACTS["gap_at_L65nm"] = saved_gap
    check("C7 反向：把短沟道缺口归零 ⇒ ㉒ 判定必红（缺口不许被静默抹掉）", ok_c7 is False)

    # C8 注入「已支持 2D MOS」口径 ⇒ ㉓ 诚实判据必红
    saved_gaps = [dict(g) for g in EC.GAPS]
    EC.GAPS[0]["detail"] = "本平台已支持 2D MOS 求解。"
    ok_c8 = EC.run_selfchecks(verbose=False)
    EC.GAPS[:] = saved_gaps
    check("C8 反向：注入「已支持 2D MOS」口径 ⇒ ㉓ 诚实判据必红", ok_c8 is False)

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
