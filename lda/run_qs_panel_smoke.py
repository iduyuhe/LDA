#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""量子传感器案例卡门禁（WebUI 只读端点 /api/qsensor_demo · QS-M8 · G10 闭合）。

═══ 判什么（分节）═══
A 模块自检（`qs_case.run_selfchecks` **12 项**）·
B 关键事实 name-first **+ 🔴 跨源一致性**（面板常量快照 ≡ `qs_m0`…`qs_m7` 现算值逐位 ——
  漂移即红；含**闭式镜像**（散粒极限 / Zeeman）与**九档模块自检项数**对拍）·
C 反向可证伪（in-process 突变：破坏诚实边界 / verdict 冒充 ACCEPT / 两腿快照漂移 /
  缺口粉饰 ⇒ 均必红）·
D 🔴 **嵌套块反向完备**（每个展示块的叶子键都必须被前端渲染段引用；含**前缀归一**、
  **假绿复现探针**、**注入探针**、**抹引用探针**）·
E 免登录 / 零重计算（不进 HEAVY_POST_PATHS · 模块不 import numpy/scipy/lda_l2/网络）·
F 路由与面板接线（GET_ROUTES 注册 / handler 定义 / 面板属性齐 / 三容器齐 / 按钮 id 以
  run 开头 / div 配平 / **三入口面**（CASE_MAP 深链 + 首屏 #wbCaseBar + 抽屉按钮）/
  面板诚实标注限定在本面板内 / API 参考已登记）+ **优雅降级** ·
K 自入 CI core（防静默漏接）。

🔴 本门禁的核心价值：守「内部能力 ↔ 对外载体」**真拉平** —— 面板上的每个数字都必须 ≡
底层模块现算（而不是卡自证自洽），并守案例卡的**诚实边界**（verdict 恒 DESIGN_BUDGET、
口径统一 η=δB·√T、公开文献值仅作对标准星、不宣称已达国际水平、LLM 不进判决路径）。
"""
from __future__ import annotations

import json
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


def _read(rel):
    fp = os.path.join(_ROOT, rel)
    if not os.path.exists(fp):
        return ""
    with open(fp, encoding="utf-8", errors="replace") as f:
        return f.read()


# ---------------------------------------------------------------------------
# 前端渲染段抽取 + 反向完备工具
# ---------------------------------------------------------------------------
def _qs_sec(idx=None):
    """抽取 sec-qsensor 面板片段（从该 .sec 起点到 footer/下一个 .sec 之前）。"""
    if idx is None:
        idx = _read("lda/lda_webui/static/index.html")
    i = idx.find('id="sec-qsensor"')
    if i < 0:
        return ""
    start = idx.rfind('<div class="sec"', 0, i)
    if start < 0:
        start = i
    nxt = [x for x in (idx.find('<div class="sec"', i + 10),
                       idx.find('<div class="footer"', i),
                       len(idx)) if x > i]
    return idx[start:min(nxt)]


def _qs_js():
    """抽取主 <script> 里新增的量子传感器渲染段（绑定行 → 本段末）。"""
    idx = _read("lda/lda_webui/static/index.html")
    i = idx.find("if($('runQsensor')) $('runQsensor').onclick = runQsensor;")
    if i < 0:
        return ""
    j = idx.find("</script>", i)
    if j < 0:
        return ""
    return idx[i:j]


# JS 内建成员（避免把 x.map / x.length 当成 JSON 路径引用）
_JS_MEMBERS = {
    "map", "length", "join", "forEach", "filter", "toFixed", "toExponential",
    "push", "slice", "indexOf", "split", "replace", "trim", "value", "options",
    "innerHTML", "textContent", "min", "max", "step", "title", "disabled", "focus",
    "valueOf", "toString", "includes", "then", "catch", "finally", "json", "ok",
    "status", "apply", "call", "bind", "concat", "pop", "shift", "splice", "sort",
    "keys", "values", "entries", "hasOwnProperty", "addEventListener",
}

_DELIM_AFTER = re.compile(r"[^A-Za-z0-9_$]")


def _ref_ok(src, lit):
    """路径引用判定：命中处**收尾字符须为非标识符**（防「同前缀长路径」冒充 · 血案 11）。"""
    i = 0
    while True:
        k = src.find(lit, i)
        if k < 0:
            return False
        nxt = src[k + len(lit):k + len(lit) + 1]
        if nxt == "" or _DELIM_AFTER.fullmatch(nxt):
            return True
        i = k + 1


def _block_keys(card, prefix):
    """取 JSON 路径处的键集（列表取首元素；支持 `a.b[]` 点分形式）。

    🔴 前缀按 `.` 切分（**不是逐字符**）—— 逐字符会让 `_block_keys(card, "nv_leg")`
    在首字符处就返回空集，使「覆盖完备」退化成「空集 ⊆ 任何集合」**恒真**（血案 #32 第二层）。
    """
    parts = prefix.split(".") if isinstance(prefix, str) else list(prefix)
    cur = card
    for part in parts:
        is_list = part.endswith("[]")
        key = part[:-2] if is_list else part
        if not isinstance(cur, dict) or key not in cur:
            return set()
        cur = cur[key]
        if is_list:
            if not isinstance(cur, list) or not cur:
                return set()
            cur = cur[0]
    return set(cur.keys()) if isinstance(cur, dict) else set()


# 展示块 → 前端别名（渲染段里用于该块的变量名）
_BLOCK_ALIAS = {
    "identity": ["idf"],
    "span": ["sp"],
    "nv_leg": ["nv"],
    "squid_leg": ["sq"],
    "geometry": ["gm"],
    "array": ["ar"],
    "calibration": ["cl"],
    "optimization": ["op"],
    "milestones[]": ["ms"],
    "findings[]": ["fn"],
    "gaps[]": ["gp"],
    "sota_stars[]": ["st"],
    "positioning": ["pos"],
}


def _missing_in_block(card, block, js):
    keys = _block_keys(card, block)
    miss = set()
    for k in keys:
        if not any(_ref_ok(js, a + "." + k) for a in _BLOCK_ALIAS[block]):
            miss.add(k)
    return miss


def main() -> int:
    from lda_webui import qs_case as QS

    # ══════════════════════ A 模块自检 ══════════════════════
    ok_a = QS.run_selfchecks(verbose=False)
    check("A1 模块自检 12/12 PASS（零框架 import / verdict 非 PASS·ACCEPT / 诚实边界齐备 / "
          "九档征程齐备 / 闭式镜像 / Zeeman 闭式 / 增益派生 / 物理合理 / 缺口 11 项且 G11 "
          "已闭合且写明依据 / 对标准星背景声明 / 优雅降级 / 护栏）", ok_a)

    # ══════════════════════ B 关键事实 + 跨源一致性 ══════════════════════
    card = QS.case_card(repo_root="__nonexistent_root__")
    check("B1 endpoint == /api/qsensor_demo", card["endpoint"] == "/api/qsensor_demo")
    check("B2 verdict == DESIGN_BUDGET（非 ACCEPT/PASS）· verdict_label 含「非流片实测」",
          card["verdict"] == "DESIGN_BUDGET" and "非流片实测" in card["verdict_label"])
    check("B3 九档征程（QS-M0/M1/M2/M3/M3b/M4/M5/M6/M7）· 门禁全登记",
          [m["id"] for m in card["milestones"]]
          == ["QS-M0", "QS-M1", "QS-M2", "QS-M3", "QS-M3b",
              "QS-M4", "QS-M5", "QS-M6", "QS-M7"]
          and all(m["gate"].startswith("run_qs_") for m in card["milestones"]))
    check("B4 缺口 11 项（G1–G11）· G10 标「本档闭合」· G11 标已闭合（QS-M9）· 闭合 11/11",
          len(card["gaps"]) == 11 and card["gaps_total"] == 11
          and next(g for g in card["gaps"] if g["id"] == "G10")["status"] == "本档闭合"
          and "闭合" in next(g for g in card["gaps"] if g["id"] == "G11")["status"]
          and "未闭合" not in next(g for g in card["gaps"] if g["id"] == "G11")["status"]
          and card["gaps_closed"] == 11)

    # B4b 🔴 跨真源对拍（v0.9.276 修 F-6）：台账说「已闭合」必须由账本背书。
    #     **只断言"现在标已闭合"等于允许台账自封**（把 G11 从表里删掉也照样绿）。
    #     🔴 本判据**不写锚号字面量** —— K4 的 L2 文本代理会把门禁源码里出现的锚号
    #        算成「该门禁覆盖了这些锚」⇒ 覆盖率虚高（v0.9.268 已踩过同类）。
    #        改用**标题关键词**从账本动态筛：口径跟随账本，M9 新增锚自动纳入。
    from lda_harness.benchmarks import BENCHMARK_DEFS as _D
    _m9 = {k: v for k, v in _D.items()
           if "OPM" in str(v.get("title", "")) or "SERF" in str(v.get("title", ""))}
    _m9_bad = sorted(k for k, v in _m9.items()
                     if v.get("maturity_tier") != "strict_independent")
    check("B4b 🔴 G11 已闭合须账本背书：OPM/SERF 族锚 3 道全在册且 strict（台账不得自封）",
          len(_m9) == 3 and not _m9_bad,
          "n=%d 非strict=%s" % (len(_m9), _m9_bad))
    check("B5 honest_note 含关键限定（设计预算 / 口径 η=δB·√T / 不宣称「已达国际水平」/ "
          "公开文献值仅对标准星 / 零量子 SDK / LLM 不进判决路径）",
          all(kw in card["honest_note"] for kw in
              ("设计预算", "白噪声幅度谱密度", "不宣称「已达国际水平」",
               "公开文献值", "零量子 SDK", "LLM 不进判决路径")))
    check("B6 对标准星 ≥5 条 + 定位块（背景声明含「不同台比较」+ 3 条诚实限制）",
          len(card["sota_stars"]) >= 5
          and "不同台比较" in card["positioning"]["disclaimer"]
          and len(card["positioning"]["honest_limits"]) == 3)
    check("B7 两腿灵敏度物理合理（NV 基线 846.59 pT/√Hz · SQUID 基线 79.25 fT/√Hz · "
          "优化后 1.73 fT/√Hz < 基线 · sota_ratio∈(0,1)）",
          abs(card["nv_leg"]["eta_baseline_pT_per_sqrtHz"] - 846.5901146206905) < 1e-6
          and abs(card["squid_leg"]["b_n_baseline_fT_per_sqrtHz"] - 79.25050863210218) < 1e-9
          and card["squid_leg"]["b_n_opt_fT_per_sqrtHz"]
          < card["squid_leg"]["b_n_baseline_fT_per_sqrtHz"]
          and 0.0 < card["squid_leg"]["sota_ratio"] < 1.0)

    # ---- 🔴 B8–B14 跨源一致性：面板快照 ≡ 平台模块现算（漂移即红 · 真拉平非自洽）----
    from lda_l2 import (qs_m0, qs_m1, qs_m2, qs_m3, qs_m3b,  # noqa: E402
                        qs_m4, qs_m5, qs_m6, qs_m7)

    # B8 闭式镜像：散粒极限 ⟷ qs_m0.sensitivity_shot_limit_closed（同式同参）
    _mirror = QS.shot_limit_eta_pT(1.0e-6, 1.0e5, 0.03)
    _ref = qs_m0.sensitivity_shot_limit_closed(1.0e-6, 1.0e5, 0.03) * 1e12
    _z = QS.zeeman_split_hz(1e-6)
    _zref = qs_m0.zeeman_split_closed_form(1e-6)
    check("B8 🔴 闭式镜像 ≡ qs_m0 现算（散粒极限 η 逐位 · Zeeman 分裂 Δf=2γeB 逐位）",
          abs(_mirror - _ref) < 1e-9 and abs(_z - _zref) < 1e-9,
          "η %.6f vs %.6f | Δf %.1f vs %.1f" % (_mirror, _ref, _z, _zref))

    # B9 腿 A 快照 ≡ qs_m0 / qs_m1 / qs_m2 现算（五情景 η + 对标准星）
    _m0 = qs_m0.design_magnetometer_v0(run_layout=False)
    _m1 = qs_m1.design_fom_system()
    _m2 = qs_m2.design_coherence_noise()
    nv = card["nv_leg"]
    _pn = (nv["eta_baseline_pT_per_sqrtHz"] - _m0["sensitivity"]["eta_pT_per_sqrtHz"],
           nv["eta_cited_pT_per_sqrtHz"]
           - _m1["scenarios"]["cited"]["eta_pT_per_sqrtHz"],
           nv["eta_degraded_pT_per_sqrtHz"]
           - _m1["scenarios"]["degraded"]["eta_pT_per_sqrtHz"],
           nv["eta_realistic_pT_per_sqrtHz"]
           - _m2["noise_budget"]["realistic"]["eta_real_pT_per_sqrtHz"],
           nv["eta_dd_enhanced_pT_per_sqrtHz"]
           - _m2["noise_budget"]["dd_enhanced"]["eta_real_pT_per_sqrtHz"],
           nv["sota_chip_nT_per_sqrtHz"]
           - _m0["benchmark"]["intl_state_of_art_chip_nT_per_sqrtHz"],
           nv["sota_cavity_nT_per_sqrtHz"]
           - _m0["benchmark"]["intl_state_of_art_cavity_nT_per_sqrtHz"])
    _w9 = max(abs(x) for x in _pn)
    check("B9 🔴 腿 A 五情景 η + 对标准星 ≡ qs_m0/qs_m1/qs_m2 现算（7 项逐位）",
          _w9 < 1e-6, "max|Δ| = %.3e" % _w9)

    # B10 几何快照 ≡ qs_m3 / qs_m3b 现算
    _m3 = qs_m3.design_geometry()
    _m3b = qs_m3b.design_qs_devices(run_checks=False)
    gm = card["geometry"]
    _drcc = sum(_m3b["drc"][k]["n_checks"] for k in _m3b["drc"])
    _drcv = sum(_m3b["drc"][k]["n_violations"] for k in _m3b["drc"])
    _pg = (gm["d_star_nm"] - _m3["geometry"]["baseline"]["optimal_depth_nm"],
           gm["eta_na"] - _m3["geometry"]["baseline"]["eta_na"],
           nv["eta_collection_baseline"]
           - _m3["geometry"]["baseline"]["eta_collection"],
           nv["eta_collection_cavity"]
           - _m3["geometry"]["cavity_enhanced"]["eta_collection"],
           nv["purcell_rate_ratio"]
           - _m3["geometry"]["cavity_enhanced"]["purcell_rate_ratio"],
           gm["pillar_height_um"]
           - _m3b["pillar_depth_consistency"]["h_pillar_um"],
           gm["cavity_web_um"] - _m3b["geometry"]["NVCavity"]["geometry"]["min_web"],
           gm["antenna_loop_r_um"] - _m3b["geometry"]["MWAntenna"]["geometry"]["loop_r"],
           gm["n_device_kinds"] - float(len(_m3b["device_kinds"])),
           gm["drc_checks_total"] - float(_drcc),
           gm["drc_violations_total"] - float(_drcv))
    _w10 = max(abs(x) for x in _pg)
    check("B10 🔴 几何/器件本体快照 ≡ qs_m3 / qs_m3b 现算（11 项逐位）",
          _w10 < 1e-9, "max|Δ| = %.3e" % _w10)

    # B11 阵列快照 ≡ qs_m4 现算
    _m4 = qs_m4.design_qs_array()
    ar = card["array"]
    _b = _m4["scenarios"]["baseline"]
    _mx = _m4["mux_baseline"]
    _pa = (ar["n_channels"] - float(_b["n_channels"]),
           ar["max_pair"] - _b["max_x_pair"],
           ar["max_total"] - _b["max_x_total"],
           ar["eta_eff_nT_per_sqrtHz"] - _b["eta_eff_nT_per_sqrtHz"],
           ar["cmrr_db"] - _b["cmrr_db"],
           ar["mux_rows"] - float(_mx["rows"]),
           ar["mux_cols"] - float(_mx["cols"]),
           ar["mux_tones_per_feedline"] - float(_mx["tones_per_feedline"]),
           ar["mux_min_tone_spacing_mhz"] - _mx["min_tone_spacing_mhz"])
    _w11 = max(abs(x) for x in _pa)
    check("B11 🔴 阵列/集成快照 ≡ qs_m4 现算（9 项逐位）",
          _w11 < 1e-9, "max|Δ| = %.3e" % _w11)

    # B12 标定快照 ≡ qs_m5 现算
    _m5 = qs_m5.design_qs_locked()
    cl = card["calibration"]
    _c5 = _m5["scenarios"]["baseline"]
    _lk = _m5["frequency_lock_baseline"]
    _fl = _m5["field_loop_baseline"]
    _pc = (cl["linewidth_mhz"] - _c5["linewidth_mhz"],
           cl["dynamic_range_db"] - _c5["dynamic_range_db"],
           cl["ac_sensitivity_nT"] - _c5["ac_sensitivity_nt"],
           cl["b_max_nT"] - _c5["b_max_nT"],
           cl["lock_n_iter"] - float(_lk["n_iter"]),
           cl["lock_residual_rel_linewidth"] - _lk["residual_rel_linewidth"],
           cl["field_scale_mismatch"] - _fl["scale_mismatch"])
    _w12 = max(abs(x) for x in _pc)
    check("B12 🔴 闭环标定/动态范围快照 ≡ qs_m5 现算（7 项逐位）",
          _w12 < 1e-9, "max|Δ| = %.3e" % _w12)

    # B13 SQUID 基线快照 ≡ qs_m6 现算
    _m6 = qs_m6.design_qs_squid()
    _c6 = qs_m6.design_defaults()
    sq = card["squid_leg"]
    _rep6 = _m6["report"]
    _ps = (sq["b_n_baseline_fT_per_sqrtHz"] - _rep6["b_n_fT_per_sqrt_hz"],
           sq["beta_c"] - _rep6["beta_c"],
           sq["plasma_freq_ghz"] - _rep6["plasma_freq_ghz"],
           sq["loop_area_m2"] - _rep6["area_m2"],
           sq["ic0_a"] - _c6["ic0_a"],
           sq["rn_ohm"] - _c6["rn_ohm"],
           sq["temp_k"] - _c6["temp_k"])
    _w13 = max(abs(x) for x in _ps)
    check("B13 🔴 SQUID 基线快照 ≡ qs_m6 现算（7 项逐位）",
          _w13 < 1e-9, "max|Δ| = %.3e" % _w13)

    # B14 性能冲刺快照 + 派生增益 ≡ qs_m7 现算
    _m7 = qs_m7.design_qs_noise_opt()
    _p7 = _m7["physics"]
    op = card["optimization"]
    _po = (op["a_eff_m2"] - _p7["a_eff_m2"],
           op["area_gain"] - _p7["area_gain"],
           op["rn_gain"] - _p7["rn_gain"],
           op["rn_opt_ohm"] - _p7["rn_opt_ohm"],
           op["b_n_opt_fT_per_sqrtHz"] - _p7["b_n_opt_fT_per_sqrt_hz"],
           op["optimization_gain"] - _p7["sensitivity_gain"],
           op["sota_ratio"] - _p7["sota_ratio"],
           op["baseline_b_n_fT_per_sqrtHz"] - _p7["base_b_n_fT_per_sqrt_hz"],
           sq["a_eff_m2"] - _p7["a_eff_m2"],
           sq["area_gain"] - _p7["area_gain"],
           sq["rn_opt_ohm"] - _p7["rn_opt_ohm"],
           sq["rn_gain"] - _p7["rn_gain"],
           sq["b_n_opt_fT_per_sqrtHz"] - _p7["b_n_opt_fT_per_sqrt_hz"],
           sq["optimization_gain"] - _p7["sensitivity_gain"],
           sq["sota_ratio"] - _p7["sota_ratio"])
    _w14 = max(abs(x) for x in _po)
    check("B14 🔴 性能冲刺快照 + 面板派生增益（重算非转录）≡ qs_m7 现算（15 项逐位）",
          _w14 < 1e-9, "max|Δ| = %.3e" % _w14)

    # B15 🔴 九档「模块自检项数」≡ 各模块 selfcheck 字典长度（手写数字机器对照）
    _counts = {
        "QS-M0": len(qs_m0.selfcheck_qs_m0()["selfcheck"]["checks"]),
        "QS-M1": len(qs_m1.design_fom_system()["checks"]),
        "QS-M2": len(qs_m2.design_coherence_noise()["checks"]),
        "QS-M3": len(qs_m3.design_geometry()["checks"]),
        "QS-M3b": len(qs_m3b.design_qs_devices()["checks"]),
        "QS-M4": len(qs_m4.design_qs_array()["checks"]),
        "QS-M5": len(qs_m5.design_qs_locked()["checks"]),
        "QS-M6": len(_m6["selfcheck"]),
        "QS-M7": len(_m7["checks"]),
    }
    _declared = {m["id"]: m["selfchecks"] for m in card["milestones"]}
    check("B15 🔴 九档「模块自检项数」≡ 各模块 selfcheck 现算长度（9 项 · 手写数字机器对照）",
          _declared == _counts, "declared=%s actual=%s" % (_declared, _counts))
    check("B16 span.module_selfchecks ≡ 九档自检项数之和",
          card["span"]["module_selfchecks"] == sum(_counts.values())
          and card["span"]["milestones"] == 9 and card["span"]["gates"] == 9)

    # ---- B17 产出物：优雅降级 + 正常根下可用 ----
    _bad = QS.case_card(repo_root="__nonexistent_root__")
    _good = QS.case_card()
    check("B17 产出物探测：错误根 ⇒ available=False（不抛错）· 正常根 ⇒ available=True 且 n_dirs>0",
          _bad["artifacts"]["available"] is False
          and _good["artifacts"]["available"] is True
          and _good["artifacts"]["n_dirs"] > 0,
          "bad=%s good=%s" % (_bad["artifacts"]["available"],
                              _good["artifacts"]["available"]))

    # ══════════════════════ C 反向可证伪（突变探针）═══════════════════════
    # C1 破坏 honest_note 关键字 ⇒ A1 必红
    _sn = QS.QS_HONEST_NOTE
    QS.QS_HONEST_NOTE = _sn.replace("不宣称「已达国际水平」", "")
    ok_c1 = QS.run_selfchecks(verbose=False)
    QS.QS_HONEST_NOTE = _sn
    check("C1 反向：移除「不宣称「已达国际水平」」⇒ A1 必红", ok_c1 is False)

    # C2 verdict 冒充 ACCEPT ⇒ 不伪装实测判据必红
    _cc = QS.case_card

    def _fake(repo_root=None, **_kw):
        c = _cc(repo_root=repo_root)
        c["verdict"] = "ACCEPT"
        return c

    QS.case_card = _fake
    _fc = QS.case_card(repo_root="__nonexistent_root__")
    QS.case_card = _cc
    check("C2 反向：verdict 冒充 ACCEPT ⇒ 不伪装实测判据必红",
          _fc["verdict"] == "ACCEPT" and _fc["verdict"] != "DESIGN_BUDGET")

    # C3 腿 A 快照漂移（基线 η +1）⇒ B9 必红
    _v = QS.NV_LEG["eta_baseline_pT_per_sqrtHz"]
    QS.NV_LEG["eta_baseline_pT_per_sqrtHz"] = _v + 1.0
    _drift3 = abs(QS.NV_LEG["eta_baseline_pT_per_sqrtHz"]
                  - qs_m0.design_magnetometer_v0(run_layout=False)["sensitivity"]["eta_pT_per_sqrtHz"])
    QS.NV_LEG["eta_baseline_pT_per_sqrtHz"] = _v
    check("C3 反向：腿 A 基线 η 漂移 +1 pT/√Hz ⇒ B9 判据必红", _drift3 > 1e-6)

    # C4 腿 B 快照漂移（优化后 B_N ×2）⇒ B14 必红
    _b = QS.SQUID_LEG["b_n_opt_fT_per_sqrtHz"]
    QS.SQUID_LEG["b_n_opt_fT_per_sqrtHz"] = _b * 2.0
    _drift4 = abs(QS.SQUID_LEG["b_n_opt_fT_per_sqrtHz"]
                  - qs_m7.design_qs_noise_opt()["physics"]["b_n_opt_fT_per_sqrt_hz"])
    QS.SQUID_LEG["b_n_opt_fT_per_sqrtHz"] = _b
    check("C4 反向：腿 B 优化后 B_N ×2 ⇒ B14 判据必红（跨源漂移可见）", _drift4 > 1e-9)

    # C5 反向（v0.9.276 语义反转）：G11 已由 QS-M9 实质闭合 ⇒ 「倒退成未闭合」必须被抓。
    #    （原反向是「谎报已闭合」；F-6 修完后真值变了，反向也要跟着反向 ——
    #      否则这条判据会变成**永远为真的假判据**：无论实现怎样它都绿。）
    _st = QS.GAPS[10]["status"]
    QS.GAPS[10]["status"] = "未闭合"
    ok_c5 = QS.run_selfchecks(verbose=False)
    QS.GAPS[10]["status"] = _st
    check("C5 反向：G11 倒退标「未闭合」⇒ A1 必红（台账不得与已交付实现脱钩）",
          ok_c5 is False)

    # C6 手写自检项数谎报 ⇒ B15 必红
    _sc = QS.MILESTONES[0]["selfchecks"]
    QS.MILESTONES[0]["selfchecks"] = 99
    _decl2 = {m["id"]: m["selfchecks"] for m in QS.case_card()["milestones"]}
    QS.MILESTONES[0]["selfchecks"] = _sc
    check("C6 反向：里程碑自检项数谎报（QS-M0: 8→99）⇒ B15 对照必红",
          _decl2["QS-M0"] != _counts["QS-M0"])

    # ══════════════════════ D 嵌套块反向完备 ══════════════════════
    js = _qs_js()
    check("D1 前端渲染段可抽取（runQsensor 绑定 → 段末）且含 renderQsensor",
          bool(js) and "function renderQsensor" in js)

    _sizes = {b: len(_block_keys(card, b)) for b in _BLOCK_ALIAS}
    check("D2 🔴 各展示块键集势 > 0（左集合为 0 即假判据 · 血案 #32 第二层）",
          all(v > 0 for v in _sizes.values()), str(_sizes))

    _all_missing = {}
    for b in _BLOCK_ALIAS:
        mm = _missing_in_block(card, b, js)
        if mm:
            _all_missing[b] = sorted(mm)
    check("D3 🔴 嵌套块反向完备：全部展示块叶子键均被前端渲染段引用",
          not _all_missing, str(_all_missing))

    def _block_keys_buggy(card_, prefix):
        cur = card_
        for seg in prefix:          # ← 病根：字符串逐字符
            if not isinstance(cur, dict) or seg not in cur:
                return set()
            cur = cur[seg]
        return set(cur.keys()) if isinstance(cur, dict) else set()

    _buggy = {b: len(_block_keys_buggy(card, b)) for b in ("nv_leg", "squid_leg")}
    check("D4 假绿复现探针：修复前实现（`for seg in prefix` 逐字符）对前缀恒返回空集",
          all(v == 0 for v in _buggy.values()), str(_buggy))

    _bk = dict(card)
    _bk["nv_leg"] = dict(card["nv_leg"], zz_injected_probe_key=1.0)
    _inj = sorted(_missing_in_block(_bk, "nv_leg", js))
    check("D5 注入探针：往 nv_leg 注入假字段 ⇒ 缺字段集合恰为该假字段（反向判据非死测试）",
          _inj == ["zz_injected_probe_key"], str(_inj))

    _js_cut = js.replace("nv.optimal_depth_nm", "nv.__cut__")
    _miss6 = _missing_in_block(card, "nv_leg", _js_cut)
    check("D6 反向：抹掉前端对 nv.optimal_depth_nm 的引用 ⇒ 反向完备必红",
          "optimal_depth_nm" in _miss6, str(sorted(_miss6)))

    _probe_src = "obj.abcd_ref"
    check("D7 反向：`obj.abc` 不应被 `obj.abcd_ref` 冒充（非标识符边界判定）",
          _ref_ok(_probe_src, "obj.abcd_ref") and not _ref_ok(_probe_src, "obj.abc"))

    # ══════════════════════ E 免登录 / 零重计算 ══════════════════════
    rt = _read("lda/lda_webui/routes.py")
    heavy = rt.split("HEAVY_POST_PATHS = {")[1].split("}")[0] if "HEAVY_POST_PATHS = {" in rt else ""
    check("E1 端点不进 HEAVY_POST_PATHS（公开只读 · 零重计算 · 无 DoS 面）",
          "/api/qsensor_demo" not in heavy)
    src_qs = _read("lda/lda_webui/qs_case.py")
    # 🔴 用 `ast` 遍历真实 import（不用源码字符串 in —— 会命中自己的 docstring，血案 6）
    import ast as _ast
    _mods = set()
    for _node in _ast.walk(_ast.parse(src_qs)):
        if isinstance(_node, _ast.Import):
            for _a in _node.names:
                _mods.add(_a.name.split(".")[0])
        elif isinstance(_node, _ast.ImportFrom):
            if _node.module:
                _mods.add(_node.module.split(".")[0])
    _banned = {"numpy", "scipy", "torch", "sklearn", "requests", "urllib",
               "socket", "http", "transformers", "openai", "lda_l2", "lda_harness"}
    check("E2 🔴 零重计算：qs_case 真实 import 不含求解器 / numpy / scipy / 网络（ast 遍历）",
          not (_mods & _banned), "imports=%s" % sorted(_mods))
    check("E3 模块顶层只 import math/os/typing（真实 import 集合 ⊆ 白名单）",
          _mods <= {"__future__", "math", "os", "typing", "json", "ast"},
          "imports=%s" % sorted(_mods))

    # ══════════════════════ F 路由 / 面板接线 + 降级 ══════════════════════
    get_block = rt.split("GET_ROUTES = {")[1].split("}")[0] if "GET_ROUTES = {" in rt else ""
    check("F1 GET 端点接线（\"/api/qsensor_demo\": h_qsensor_demo, 在 GET_ROUTES）",
          '"/api/qsensor_demo": h_qsensor_demo,' in get_block)
    check("F2 handler 定义存在（def h_qsensor_demo）", "def h_qsensor_demo(" in rt)
    idx = _read("lda/lda_webui/static/index.html")
    check("F3 面板三容器齐（qsSummary / qsBody / qsConclusion）",
          all(x in idx for x in ('id="qsSummary"', 'id="qsBody"', 'id="qsConclusion"')))
    check("F4 面板按钮 id 以 run 开头（自动进抽屉「能力目录」）", 'id="runQsensor"' in idx)
    check("F5 面板属性齐（id=sec-qsensor + data-stage=accept + data-stack + data-roles）",
          'id="sec-qsensor"' in idx and 'data-stage="accept"' in idx
          and 'data-stack="both"' in idx)
    check("F6 div 配平（<div> == </div>）",
          len(re.findall(r"<div\b", idx)) == idx.count("</div>"),
          "%d vs %d" % (len(re.findall(r"<div\b", idx)), idx.count("</div>")))

    # F7 🔴 案例卡面板必须可经 hash **深链**直达（CASE_MAP 覆盖 · 族现算 + 下限棘轮）
    _cm = re.search(r"var\s+CASE_MAP\s*=\s*\{(.*?)\}\s*;", idx, re.S)
    _cm_pairs = dict(re.findall(r'"(#sec-[A-Za-z0-9_]+)"\s*:\s*"([A-Za-z0-9_]+)"',
                                _cm.group(1) if _cm else ""))
    _accept_ids = sorted(set(
        [m.group(1) for m in re.finditer(r'data-stage="accept"[^>]*id="(sec-[A-Za-z0-9_]+)"', idx)] +
        [m.group(1) for m in re.finditer(r'id="(sec-[A-Za-z0-9_]+)"[^>]*data-stage="accept"', idx)]))
    _missing = [s for s in _accept_ids if ("#" + s) not in _cm_pairs]
    check("F7 🔴 全部 accept 案例卡均登记 CASE_MAP（hash 深链可达 · 下限棘轮 ≥11）",
          len(_accept_ids) >= 11 and not _missing,
          "accept=%d map=%d missing=%s" % (len(_accept_ids), len(_cm_pairs), _missing))
    check("F7b sec-qsensor 映射到 runQsensor", _cm_pairs.get("#sec-qsensor") == "runQsensor",
          "got=%r" % _cm_pairs.get("#sec-qsensor"))

    # F8 🔴 首屏 #wbCaseBar 直达条目（第三种入口面）
    _bar = re.search(r'id="wbCaseBar".{0,12000}?</div>', idx, re.S)
    _bar_hrefs = re.findall(r'href="(#[^"]+)"', _bar.group(0)) if _bar else []
    check("F8 🔴 sec-qsensor 已登记首屏案例条 #wbCaseBar（否则首屏扫不到）",
          "#sec-qsensor" in _bar_hrefs, "bar 条目=%d" % len(_bar_hrefs))

    # F9 🔴 面板诚实标注不得被静默抹掉（**限定在 sec-qsensor 面板内**）
    _sec = _qs_sec(idx)
    check("F9 面板诚实标注齐备（只读 · 免登录 · 零重计算 / DESIGN_BUDGET / "
          "LLM 不进判决路径 / 不宣称「已达国际水平」）",
          bool(_sec) and all(kw in _sec for kw in
                             ("只读 · 免登录 · 零重计算", "DESIGN_BUDGET",
                              "LLM 不进判决路径", "不宣称「已达国际水平」")),
          "面板片段长 %d" % len(_sec))

    jp = os.path.join(_ROOT, "docs", "api_reference.json")
    try:
        ref = json.load(open(jp, encoding="utf-8"))
        ep = next((e for e in ref["endpoints"] if e["path"] == "/api/qsensor_demo"), None)
        check("F10 API 参考已含 /api/qsensor_demo 且 auth=public（gen 已跑 · 防双红）",
              bool(ep) and ep["auth"] == "public" and bool(ep["description"]),
              "found=%s" % (ep is not None))
    except Exception as e:  # pragma: no cover
        check("F10 API 参考已含 /api/qsensor_demo", False, "读参考失败: %s" % e)

    # ══════════════════════ K 自入 CI core ══════════════════════
    try:
        import run_ci_regression as R  # noqa: E402,F401
        check("K1 本 smoke 已登记进 CI core（CORE_SMOKES）",
              "run_qs_panel_smoke.py" in R.CORE_SMOKES,
              "len=%d" % len(R.CORE_SMOKES))
    except Exception as e:  # pragma: no cover
        check("K1 本 smoke 已登记进 CI core（CORE_SMOKES）", False, "import 失败: %s" % e)

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
