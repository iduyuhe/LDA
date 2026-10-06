# -*- coding: utf-8 -*-
"""LDA 光子存储征程 · PM-G7 结算门禁（光学域 drift 实测锚 → 主账口径翻转）。

判据（全部**重算**，不读字面量）：
  A1 锚表结构：`OPTICAL_DRIFT_ANCHORS["GST"]` ≥3 条 · 三种 kind 齐 · 每条含 DOI 源 ·
     无「本项目实测」自称（红线）
  A2 机器判定翻转：`pm_m2.optical_drift_status` ⇒ has_direct_optical_anchor=True ∧
     gap_pm_g7_open=False（判定读锚表长度，非字面量）
  B1 上界重算守卫：`nu_optical_bound` 的 ν_ub ≡ floor/ln(t_meas/t₀)（纯算术重算 ∧ 防漂移）
  B2 上界量级 sanity：0 < ν_T_ub < 0.004 ∧ 远小于电学域 ν_max（锚语义 = 上界）
  C1 主账恒等式：系统预算 ε_drift ≡ ν_T_ub·ln(t_hold/t₀)（重算）
  C2 🔴 口径翻转：主账 ε_drift < 旧电学代理 ε_drift（比值 > 100，实测 ≈315.8×）∧
     主账/旧口径的 `is_main_account` 标注各就各位
  C3 🔴 翻转后果（1 年保持）：主账 all_ok=True ∧ bottleneck==write；旧口径
     bottleneck==drift ∧ BER>0.4（两口径并存 ⇒ 并报不选择性披露）
  C4 下界语义：max_t_hold > 1e70 s（天文量级）∧ `retention_semantics` 显式声明下界
  C5 并报完整性：`drift_proxy.per_proxy` 非空 ∧ note 含「并报」∧ 含旧结论数字
  D1 缺口台账：机器账本仍有 PM-G7 且 closed ∧ 对外台账行含「已结算」+ Cheng 2019
     DOI ∧ **未闭合 spec 缺口全披露** —— 不用「条目数 == 常数」这类字面量判据
     （v0.9.194：写死 5 ⇒ M5 合法新增 PM-G10 后必红；「条目数不变」本身语义就错）
  D1b 🔴 对外台账 id 集合 == 开放 spec 缺口 ∪ 已登记例外 `{PM-G2, PM-G6, PM-G7, PM-G8, PM-G9, PM-G11}`
     （**精确指纹** · 防「新条目只进看得见的集合、无独立证据链」静默进盲区）
     · v0.9.195：PM-G6 由「开放」转「已结算但仍对外披露」⇒ 移入例外集合（同 G7 处置）
  D2 🔴 快照 schema == 仓库报告 JSON（system_budget 含 drift_anchor，逐块同构）
  D3 matlib `material_table()` 透传光学域锚（消费语义不脱钩）
  E1 披露守卫：`drift_segment_is_cross_domain_proxy=False` ∧ 主账=实测上界锚 ∧
     检测下限假设披露 ∧ 肯定式面禁词零命中
  S1 本门禁已登记进 CI core

突变探针（每条**先证能变红**，还原后复绿）：
  P1 锚 floor 0.35%→35%（同步改 nu_ub 保持一致）⇒ ν_T_ub ×100 ⇒ 主账 ε_drift ×100 ∧
     1 年瓶颈翻回 drift（证明预算真的读锚，非硬编码）
  P2 清空锚表 ⇒ 机器判定翻回「无锚/缺口开放」∧ `nu_optical_bound` raise（复现
     pre-fix 行为 ⇒ 「锚空=PM-G7 开放」的判定仍有效）
  P3 只改 nu_ub 不改 floor ⇒ 防漂移守卫 raise（锚表损坏当场暴露）
  P4 台账判据自身变异探针（先证能变红）：原样必绿；抹「已结算」/抹 DOI/删 G7 行/
     藏 G10 行/机器账本删行/机器账本改判未闭合 六种改法**各自**必红
  P5 D1b 指纹反向探针：原样绿 ∧ 偷加条目/偷删条目/换名 三改必红
"""
from __future__ import annotations

import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=" —— {d}")

from lda_l2 import pm_m0 as M0          # noqa: E402
from lda_l2 import pm_m2 as M2          # noqa: E402
from lda_l2 import pm_m4 as M4          # noqa: E402
from lda_l2 import pm_matlib as ML      # noqa: E402
from lda_webui import pm_case as PC     # noqa: E402

_BANNED_POSITIVE = ("TOPS", "TOPS-W", "TOPS/W", "fJ/op", "fJ·op", "pJ/bit")
_NEG_TOKENS = ("不报", "不得报", "禁止", "禁用", "never", "not reported",
               "no efficiency", "不承诺", "不声称", "非", "无")


def _positive_surface(text: str) -> str:
    """只取**肯定式面**：剔除含否定标记的从句。"""
    parts = []
    for clause in text.replace("；", "。").replace(";", "。").split("。"):
        if any(tok in clause for tok in _NEG_TOKENS):
            continue
        parts.append(clause)
    return "。".join(parts)


def _g7_ledger_ok(case_gaps, ledger, spec):
    """PM-G7 台账判据（**参数化**：探针可喂变异体 ⇒ 先证能变红）。

    四个合取项各有独立语义：
      ① 机器账本 `gap_ledger()` 里仍有 PM-G7 且 `closed=True` —— 结算 ≠ 删行；
      ② 对外台账里仍有 PM-G7 且标题含「已结算」—— 结算动作确实对外披露；
      ③ 该行 detail 含 Cheng 2019 DOI —— 挂的是**实测锚**而非自述；
      ④ 所有**未闭合**的 spec 缺口都在对外台账里 —— 开放缺口不许被藏。
    🔴 v0.9.194 血案：原判据写死 `len(PC.GAPS) == 5`（字面量）⇒ M5 合法新增
    PM-G10 后必红。**「条目数不变」本身就是错的语义**（缺口只该增、不该被静默
    吞），正确的是「开放缺口必须披露 + 结算不删行」。字面量计数 = 假判据高发区。
    """
    lrow = next((r for r in ledger if r.get("id") == "PM-G7"), None)
    crow = next((x for x in case_gaps if x.get("id") == "PM-G7"), None)
    if lrow is None or crow is None or not lrow.get("closed"):
        return False
    open_ids = {s["id"] for s in spec if not s.get("declared_closed")}
    case_ids = {x.get("id") for x in case_gaps}
    return ("已结算" in crow.get("title", "")
            and "doi:10.1126/sciadv.aau5759" in crow.get("detail", "")
            and open_ids <= case_ids)


#: 对外台账里**不属「开放 spec 缺口」**的两类合法行：
#:   ① 已结算但仍对外披露（结算 ≠ 从台账消失）；
#:   ② M4 登记、**暂无独立证据链**的外设/器件级条目（`GAP_SPECS` 无对应 `_ev_*`）
#:      —— 用**精确指纹**把它显式登记下来，任何一侧悄悄增删都会当场变红
#:      （否则新条目只进「看得见的集合」⇒ 静默进盲区，本仓已吃过这一课）。
#:   · v0.9.198：PM-G2（Γ 场求解标定）由「开放」转「已结算但仍对外披露」⇒ 移入例外集合。
#:   · v0.9.200：PM-G11（L_mid 按标定 Γ=0.084 重标定，现役设计点 6.556µm 落入标定窗
#:     [3.559,9.553]µm，余量 +31.4%）由「开放」转「已结算但仍对外披露」⇒ 移入例外集合。
#:     （注：P5 的「偷加」样本 id 已改用未使用的 `PM-G0`，故登记 G11 不会让探针静默失效。）
_LEDGER_EXTRA = {"PM-G2", "PM-G6", "PM-G7", "PM-G8", "PM-G9", "PM-G11"}


def main() -> int:
    print("=" * 74)
    print("LDA 光子存储征程 · PM-G7 结算门禁（光学域 drift 实测锚 → 主账口径翻转）")
    print("=" * 74)

    # ── A1 锚表结构 ──────────────────────────────────────────────────────
    rows = ML.OPTICAL_DRIFT_ANCHORS.get("GST", [])
    kinds = {r.get("kind") for r in rows}
    check("A1 锚表结构：≥3 条 ∧ 三种 kind 齐 ∧ 每条含 DOI 源 ∧ 无「本项目实测」自称",
          len(rows) >= 3
          and {"transmission_drift_upper_bound", "relaxation_kinetics",
               "device_retention_claim"} <= kinds
          and all("doi:" in r.get("source", "") for r in rows)
          and not any(r.get("is_measured_by_this_project") for r in rows),
          "kinds=%s" % sorted(k for k in kinds if k))

    # ── A2 机器判定翻转 ──────────────────────────────────────────────────
    st = M2.optical_drift_status("GST")
    check("A2 机器判定：has_direct_optical_anchor=True ∧ gap_pm_g7_open=False（读锚表非字面量）",
          st["has_direct_optical_anchor"] is True and st["gap_pm_g7_open"] is False
          and st["n_bound_anchors"] >= 1,
          "n=%d n_bound=%d" % (st["n_optical_anchors"], st["n_bound_anchors"]))

    # ── B1 上界重算守卫 ──────────────────────────────────────────────────
    nuo = M2.nu_optical_bound("GST")
    _re = 0.0035 / math.log(1.0e4 / 1.0)
    check("B1 上界重算：ν_ub ≡ floor/ln(t_meas/t₀)（纯算术重算 ∧ 防漂移守卫内建）",
          abs(nuo["nu_ub_max"] - _re) <= 1e-12 * _re and nuo["n_bound_anchors"] >= 1,
          "ν_T_ub=%.6g" % nuo["nu_ub_max"])

    # ── B2 量级 sanity ──────────────────────────────────────────────────
    nu_el = M2.nu_central("GST")
    check("B2 上界量级：0 < ν_T_ub < 0.004 ∧ ≪ 电学域 ν_max（上界语义 = 保守侧）",
          0.0 < nuo["nu_ub_max"] < 0.004 and nuo["nu_ub_max"] < 0.1 * float(nu_el["nu_max"]),
          "optical=%.4g electrical=%.4g ratio=%.1f×"
          % (nuo["nu_ub_max"], float(nu_el["nu_max"]),
             float(nu_el["nu_max"]) / nuo["nu_ub_max"]))

    # ── C1 主账恒等式 ───────────────────────────────────────────────────
    b = M4.system_link_budget("GST")
    b1y = M4.system_link_budget("GST", t_hold_s=M4.T_HOLD_S_DEFAULT)
    _exp = nuo["nu_ub_max"] * math.log(b["t_hold_s"] / M4.T_HOLD_T0_S)
    check("C1 主账恒等式：ε_drift ≡ ν_T_ub·ln(t_hold/t₀)（重算）",
          abs(b["eps"]["drift"] - _exp) <= 1e-12 * _exp,
          "ε_drift=%.6g" % b["eps"]["drift"])

    # ── C2 口径翻转 ─────────────────────────────────────────────────────
    leg = b["drift_proxy"]
    _ratio = leg["eps_drift_at_t_hold"] / b["eps"]["drift"]
    check("C2 口径翻转：主账 ε_drift < 旧电学代理（比值 >100）∧ is_main_account 各就各位",
          _ratio > 100.0
          and b["drift_anchor"]["is_main_account"] is True
          and leg["is_main_account"] is False
          and leg["is_cross_domain_proxy"] is True,
          "ratio=%.1f× 主账=%.4g 旧=%.4g" % (_ratio, b["eps"]["drift"],
                                            leg["eps_drift_at_t_hold"]))

    # ── C3 翻转后果（1 年保持）──────────────────────────────────────────
    check("C3 翻转后果：主账 all_ok=True ∧ bottleneck==write；旧口径 bottleneck==drift ∧ BER>0.4",
          b1y["all_ok"] is True and b1y["bottleneck"] == "write"
          and b1y["drift_proxy"]["bottleneck"] == "drift"
          and b1y["drift_proxy"]["ber_total"] > 0.4
          and b1y["ber_total"] < b1y["ber_target"],
          "主账 BER=%.3g 旧口径 BER=%.4g" % (b1y["ber_total"],
                                            b1y["drift_proxy"]["ber_total"]))

    # ── C4 下界语义 ─────────────────────────────────────────────────────
    check("C4 下界语义：max_t_hold > 1e70 s ∧ retention_semantics 显式声明下界",
          b1y["max_t_hold_s_for_target"] > 1.0e70
          and "下界" in b1y["drift_anchor"]["retention_semantics"],
          "t_max=%.3g s" % b1y["max_t_hold_s_for_target"])

    # ── C5 并报完整性 ───────────────────────────────────────────────────
    check("C5 并报完整性：per_proxy 非空 ∧ note 含「并报」∧ note 含旧结论（1.7 秒）",
          len(leg["per_proxy"]) >= 2 and "并报" in leg["note"]
          and "1.7" in leg["note"],
          "n_proxy=%d" % len(leg["per_proxy"]))

    # ── D1 缺口台账 ─────────────────────────────────────────────────────
    _g7 = next(g for g in PC.GAPS if g["id"] == "PM-G7")
    _ledger = M0.gap_ledger()
    _spec = list(M0.GAP_SPECS)
    _open_ids = {s["id"] for s in _spec if not s.get("declared_closed")}
    check("D1 缺口台账：机器账本仍有 PM-G7 且 closed ∧ 对外行含「已结算」+ Cheng 2019 DOI "
          "∧ 未闭合缺口（%d 条）全披露" % len(_open_ids),
          _g7_ledger_ok(PC.GAPS, _ledger, _spec),
          "title=%s · case=%d ledger=%d" % (_g7["title"][:34], len(PC.GAPS),
                                            len(_ledger)))

    # ── D1b 🔴 对外台账 == 开放 spec 缺口 ∪ 已登记例外（**精确指纹**）──────
    # 反向完备：两侧任何一侧悄悄增删条目都必红 ⇒ 新缺口不会只活在某一份清单里。
    _case_ids = {g["id"] for g in PC.GAPS}
    _want = _open_ids | _LEDGER_EXTRA
    check("D1b 🔴 对外台账 id 集合 == 开放 spec 缺口 ∪ 已登记例外"
          "（精确指纹 · 防「新条目进了看得见的集合却无证据链」静默进盲区）",
          _case_ids == _want,
          "多=%s 缺=%s" % (sorted(_case_ids - _want), sorted(_want - _case_ids)))

    # ── D2 快照 schema == 仓库报告 JSON ─────────────────────────────────
    rep_fp = os.path.join(_ROOT, "examples", "photo_memory", "lda_pm_m4_report.json")
    repj = json.load(open(rep_fp, encoding="utf-8"))
    snap_sb = PC.STATIC_SNAPSHOT["m4"]["system_budget"]
    rep_sb = repj["system_budget"]

    def _dig(o, keys):
        for k in keys:
            o = o[k]
        return o

    schema_bad = []
    for keys in (("drift_anchor",), ("drift_proxy",), ("eps",), ("share",)):
        ka, kb = set(_dig(snap_sb, keys).keys()), set(_dig(rep_sb, keys).keys())
        if ka != kb:
            schema_bad.append("%s: 快照缺%s 报告多%s"
                              % (".".join(keys), sorted(ka - kb), sorted(kb - ka)))
    check("D2 🔴 快照 schema == 仓库报告 JSON（system_budget 含 drift_anchor，逐块同构）",
          not schema_bad, "失配：%s" % schema_bad)

    # ── D3 matlib 透传 ──────────────────────────────────────────────────
    tbl = ML.matlib_report()
    _mt = tbl.get("optical_drift_anchors", {}).get("GST", [])
    check("D3 matlib material_table() 透传光学域锚（消费语义不脱钩）",
          len(_mt) == len(rows) and _mt[0].get("kind") == "transmission_drift_upper_bound",
          "n=%d" % len(_mt))

    # ── E1 披露守卫 ─────────────────────────────────────────────────────
    disc = M4.m4_report("GST")["disclosure"]
    surf = _positive_surface(json.dumps(b["drift_anchor"], ensure_ascii=False))
    hits = [t for t in _BANNED_POSITIVE if t in surf]
    check("E1 披露守卫：跨域代理=False ∧ 主账=实测上界锚 ∧ 检测下限假设披露 ∧ 禁词零命中",
          disc["drift_segment_is_cross_domain_proxy"] is False
          and disc["drift_segment_main_account_is_measured_optical_upper_bound"] is True
          and disc["retention_claims_depend_on_detection_floor_assumption"] is True
          and not hits, "禁词命中=%s" % hits)

    # ═══════════════ 突变探针（先证能红 · 还原后复绿）═══════════════
    _anchor0 = ML.OPTICAL_DRIFT_ANCHORS["GST"][0]
    _keep = dict(_anchor0)
    try:
        # P1 floor 0.35%→35%（同步 nu_ub 保持一致）⇒ ν_T_ub ×100 ⇒ 瓶颈翻回 drift
        _anchor0["detection_floor_rel"] = 0.35
        _anchor0["nu_ub"] = 0.35 / math.log(1.0e4)
        _p1 = M4.system_link_budget("GST", t_hold_s=M4.T_HOLD_S_DEFAULT)
        check("P1 探针：floor ×100 ⇒ ν_T_ub ×100 ⇒ 主账 ε_drift ×100 ∧ 1 年瓶颈翻回 drift"
              "（证明预算真读锚，非硬编码）",
              abs(_p1["eps"]["drift"] - b1y["eps"]["drift"] * 100.0) <= 1e-9 * b1y["eps"]["drift"]
              and _p1["bottleneck"] == "drift",
              "ε_drift=%.4g bn=%s" % (_p1["eps"]["drift"], _p1["bottleneck"]))
    finally:
        ML.OPTICAL_DRIFT_ANCHORS["GST"][0] = _keep

    try:
        # P2 清空锚表 ⇒ 机器判定翻回「缺口开放」∧ nu_optical_bound raise（pre-fix 行为复现）
        _rows_keep = list(ML.OPTICAL_DRIFT_ANCHORS["GST"])
        ML.OPTICAL_DRIFT_ANCHORS["GST"] = []
        _st2 = M2.optical_drift_status("GST")
        _raised = False
        try:
            M2.nu_optical_bound("GST")
        except Exception:
            _raised = True
        check("P2 探针：清空锚表 ⇒ has_direct_optical_anchor=False ∧ gap_pm_g7_open=True ∧ "
              "nu_optical_bound raise（pre-fix 行为复现，钉死「锚空=缺口开放」）",
              _st2["has_direct_optical_anchor"] is False
              and _st2["gap_pm_g7_open"] is True and _raised)
    finally:
        ML.OPTICAL_DRIFT_ANCHORS["GST"] = _rows_keep

    try:
        # P3 只改 nu_ub 不改 floor ⇒ 防漂移守卫 raise（锚表损坏当场暴露）
        ML.OPTICAL_DRIFT_ANCHORS["GST"][0]["nu_ub"] = _keep["nu_ub"] * 2.0
        _raised3 = False
        try:
            M2.nu_optical_bound("GST")
        except Exception:
            _raised3 = True
        check("P3 探针：nu_ub 与 floor 重算不一致 ⇒ 防漂移守卫 raise（锚表损坏必暴露）",
              _raised3)
    finally:
        ML.OPTICAL_DRIFT_ANCHORS["GST"][0] = _keep

    # ── P4 台账判据的变异探针（各改法**各自**必红 + 原样必绿）──────────────
    _m_title = [{**x} for x in PC.GAPS]
    for _x in _m_title:
        if _x["id"] == "PM-G7":
            _x["title"] = _x["title"].replace("已结算", "（开放）")
    _m_doi = [{**x} for x in PC.GAPS]
    for _x in _m_doi:
        if _x["id"] == "PM-G7":
            _x["detail"] = _x["detail"].replace("doi:10.1126/sciadv.aau5759",
                                                "（无 DOI）")
    _m_del_g7 = [x for x in PC.GAPS if x["id"] != "PM-G7"]
    _m_del_g10 = [x for x in PC.GAPS if x["id"] != "PM-G10"]
    _m_led_del = [r for r in _ledger if r["id"] != "PM-G7"]
    _m_led_open = [{**r, "closed": False} if r["id"] == "PM-G7" else r
                   for r in _ledger]
    _mut = [
        _g7_ledger_ok(PC.GAPS, _ledger, _spec) is True,            # 原样必绿（非恒假）
        _g7_ledger_ok(_m_title, _ledger, _spec) is False,          # 抹「已结算」必红
        _g7_ledger_ok(_m_doi, _ledger, _spec) is False,            # 抹 DOI 必红
        _g7_ledger_ok(_m_del_g7, _ledger, _spec) is False,         # 对外删 G7 行必红
        _g7_ledger_ok(_m_del_g10, _ledger, _spec) is False,        # 藏开放缺口必红
        _g7_ledger_ok(PC.GAPS, _m_led_del, _spec) is False,        # 机器账本删行必红
        _g7_ledger_ok(PC.GAPS, _m_led_open, _spec) is False,       # 账本判「未闭合」必红
        _g7_ledger_ok(PC.GAPS, _ledger,
                      [_s for _s in _spec if _s["id"] != "PM-G10"]) is True,
    ]
    check("P4 台账判据变异探针：原样绿 ∧ 抹已结算/抹 DOI/删 G7/藏 G10/账本删行/"
          "账本改判 六改必红",
          all(_mut), "mut=%s" % _mut)

    # ── P5 D1b 精确指纹的反向探针（增/删/换名 各自必红）──────────────────
    # 🔴 v0.9.198：探针的「偷加」样本 id 必须是**未使用**的（原用 `PM-G11`，
    #    加入 PM-G11 后它成了合法 id ⇒ 该样本恒等于原样 ⇒ 探针静默失效）。
    _case_ids = {g["id"] for g in PC.GAPS}
    _fp = [
        _case_ids == (_open_ids | _LEDGER_EXTRA),                     # 原样绿
        (_case_ids | {"PM-G0"}) == (_open_ids | _LEDGER_EXTRA),       # 偷加条目必红
        (_case_ids - {"PM-G10"}) == (_open_ids | _LEDGER_EXTRA),      # 偷删条目必红
        (_case_ids - {"PM-G9"} | {"PM-G99"}) == (_open_ids | _LEDGER_EXTRA),  # 换名必红
    ]
    check("P5 D1b 指纹反向探针：原样绿 ∧ 偷加(PM-G0)/偷删/换名 三改必红",
          _fp[0] and not any(_fp[1:]), "fp=%s" % _fp)

    # ── S1 自入 CI core ─────────────────────────────────────────────────
    cut = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(cut, encoding="utf-8").read() if os.path.exists(cut) else ""
    check("S1 本门禁已登记进 CORE_SMOKES（防静默漏接）", "run_pm_g7_settlement_smoke.py" in ck)

    print("")
    print("门禁 smoke：%d PASS / %d FAIL" % (globals().get("PASS", 0), globals().get("FAIL", 0)))
    return 0 if globals().get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
