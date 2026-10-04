# -*- coding: utf-8 -*-
"""LDA 光子存储征程 · PM-M0 门禁（判据 + 突变探针 + 双方法互证）。

判据（全部**重算**，不读字面量）：
  C1 锚库守卫：表结构合法 ∧ 未登记波长取值必 raise ∧「假实测」声明必 raise（双向）
  C2 跨来源离散度如实报：多来源材料的 k/每 π 损耗离散度 ≥10× ∧ per_source 条数 == 登记来源数
  C3 Γ 无关律：IL_π 对 Γ 扫描不变（机器精度）—— M0 的核心闭式律
  C4 双方法互证：闭式 ⟷ 分片累乘（两种 n_seg 都一致到 1e-12）
  C5 对比度随长度单调增（每点重算，不用缩放假设）
  C6 写能量预算：量级正确 ∧ 与文献记录值同量级 ∧ 字段级消费审计真在跑（有来源被排除）
  C7 缺口台账：`closed ⇔ evidence_ok` ∧ PM-G1 已闭合 ∧ PM-G2..G5 如实开放
  C8 披露完整 + 真实输出肯定式禁词扫描零命中
  C9 报告自洽：headline 离散度与逐来源重算一致（防 headline 写死）

突变探针（每条**先证能变红**）：
  P1 把律写成 k² ⇒ Γ 无关性必破（C3 有判别力）
  P2 只留 1 个来源 ⇒ 离散度口径失效（C2 有判别力）
  P3 锚标「本项目实测」⇒ C1 守卫必 raise
  P4 台账造假（G2 closed=True 而证据不变）⇒ C7 必红
  P5 单元长度压到 0.01µm ⇒ 读出能量下限爆炸（读出判据有判别力）
  P6 全部热锚缺 T_melt ⇒ 写预算必 raise（不合成、不发明）
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=' —— {d}')

from lda_l2 import pm_matlib as ML  # noqa: E402
from lda_l2 import pm_m0 as M  # noqa: E402

_BANNED_POSITIVE = ("TOPS", "TOPS-W", "TOPS/W", "fJ/op", "fJ·op", "pJ/bit")
_NEG_TOKENS = ("不报", "不得报", "禁止", "禁用", "never", "not reported", "no efficiency")


def _positive_surface(text: str) -> str:
    """只取**肯定式面**：剔除含否定标记的从句（免责句不应让判据恒红，也不该豁免真违规）。"""
    parts = []
    for clause in text.replace("；", "。").replace(";", "。").split("。"):
        if any(tok in clause for tok in _NEG_TOKENS):
            continue
        parts.append(clause)
    return "。".join(parts)


def main() -> int:
    rep = M.cell_report("GST")

    # ---------------- C1 锚库守卫 ----------------
    ok_struct = True
    try:
        ML._check_anchors()
    except Exception:
        ok_struct = False
    guard_raise = False
    try:
        ML.nk("GST", "amorphous", 1310.0)
    except ML.PMMatlibRedlineError:
        guard_raise = True
    check("C1a 锚表结构合法", ok_struct)
    check("C1b 未登记波长取值必 raise（反外推）", guard_raise)

    # ---------------- C2 跨来源离散度如实报 ----------------
    mats = rep["matlib"]["materials"]
    gst_c = mats["GST"]["nk_crystalline"]
    gst_l = mats["GST"]["per_pi_loss"]
    n_reg = len(ML.OPTICAL_ANCHORS["GST"])
    check("C2a GST k 跨来源离散 ≥10×（实测 %.1f×）" % gst_c["k_spread_x"],
          gst_c["k_spread_x"] is not None and gst_c["k_spread_x"] >= 10.0)
    check("C2b GST 每 π 损耗跨来源离散 ≥10×（实测 %.2f×）" % gst_l["spread_x"],
          gst_l["spread_x"] is not None and gst_l["spread_x"] >= 10.0)
    check("C2c per_source 条数 == 登记来源数（%d）" % n_reg,
          len(gst_l["per_source"]) == n_reg == len(gst_c["per_source"]))
    check("C2d 单来源材料被显式标记（GSST）", mats["GSST"]["nk_crystalline"]["single_source"] is True)
    # 独立重算：离散度必须等于 max/min（咬语义，防 headline 写死）
    vals = [r["il_db_per_pi"] for r in gst_l["per_source"]]
    check("C2e 离散度由逐来源重算一致",
          abs(gst_l["spread_x"] - max(vals) / min(vals)) < 1e-12)

    # ---------------- C3 Γ 无关律（核心闭式律）----------------
    inv = rep["cell"]["per_pi_law"]
    check("C3a IL_π 对 Γ 扫描不变（实测 rel_dev=%.2e）" % inv["max_rel_dev"],
          inv["max_rel_dev"] is not None and inv["max_rel_dev"] < 1e-12)
    # 独立第二路径：自己按「固定 3π 相移」逐 Γ 反解长度再算 IL，比值应与闭式一致
    dn = ML.delta_n("GST")["per_source"][0]["dn"]
    k_c = ML.delta_n("GST")["per_source"][0]["k_c"]
    cf = ML.per_pi_loss_db(dn, k_c)
    devs = []
    for g in (0.03, 0.07, 0.13):
        l_for_pi = 1550e-9 / (2.0 * g * dn)
        il_at_pi = (10.0 / math.log(10.0)) * g * (4.0 * math.pi * k_c / 1550e-9) * l_for_pi
        devs.append(abs(il_at_pi - cf) / cf)
    check("C3b 第二独立路径（反解长度）同值（max_dev=%.2e）" % max(devs), max(devs) < 1e-12)

    # ---------------- C4 双方法互证 ----------------
    v1 = M.verify_closed_form_vs_segments("GST", l_um=2000.0, n_seg=64)
    v2 = M.verify_closed_form_vs_segments("GST", l_um=2000.0, n_seg=997)
    check("C4a 闭式 ⟷ 分片（64 段）一致", v1["phi_rel_dev"] < 1e-12 and v1["il_rel_dev"] < 1e-12)
    check("C4b 闭式 ⟷ 分片（997 段）一致（非巧合）",
          v2["phi_rel_dev"] < 1e-12 and v2["il_rel_dev"] < 1e-12)

    # ---------------- C5 对比度随长度单调增 ----------------
    cvl = rep["cell"]["contrast_vs_length"]
    cmin = [c["contrast_min_db"] for c in cvl]
    cmax = [c["contrast_max_db"] for c in cvl]
    check("C5a 对比度两端来源均随 L 严格递增",
          all(b > a for a, b in zip(cmin, cmin[1:])) and all(b > a for a, b in zip(cmax, cmax[1:])))
    check("C5b 全部长度对比度 > 0", min(cmin) > 0.0)

    # ---------------- C6 写能量预算 ----------------
    w = rep["cell"]["write"]
    check("C6a 显热主账落在设计预算量级 [1e-13,1e-10] J (%.3e)" % w["sensible_lower_j"],
          1e-13 <= w["sensible_lower_j"] <= 1e-10)
    check("C6b 与文献记录值同量级（比值 %.2f ∈[0.1,100]）" % w["ratio_sensible_to_anchor"],
          0.1 <= w["ratio_sensible_to_anchor"] <= 100.0)
    check("C6c 字段级消费审计真在跑（有来源因缺字段被排除）", len(w["excluded_sources"]) >= 1)
    check("C6d 潜热为假设来源、主账不计",
          w["provenance"]["latent"] == "assumption" and w["sensible_lower_j"] < sum(w["latent_upper_assumed_j"]) * 100)

    # ---------------- C7 缺口台账 ----------------
    gaps = {g["id"]: g for g in rep["gaps"]}
    check("C7a 台账不变式 closed ⇔ evidence_ok", M.gap_ledger_consistent() is True)
    check("C7b PM-G1（材料常数库）已闭合", gaps["PM-G1"]["closed"] is True)
    check("C7c PM-G3/G4/G5 已闭合（锚 + 律自检 · v0.9.189 证据升级）",
          all(gaps[g]["closed"] is True for g in ("PM-G3", "PM-G4", "PM-G5")))
    check("C7c2 PM-G2/G6 如实开放 ∧ PM-G7 已结算（v0.9.193 · 不粉饰）",
          all(gaps[g]["closed"] is False for g in ("PM-G2", "PM-G6"))
          and gaps["PM-G7"]["closed"] is True)
    check("C7c3 台账人机两源一致性（declared ⇔ evidence · 非同义反复）",
          all(g["declared_closed"] == g["evidence_ok"] for g in rep["gaps"]))
    check("C7d 每条缺口都挂证据明细（非空）",
          all(len(g["evidence_detail"]) > 0 for g in rep["gaps"]))

    # ---------------- C8 披露 + 禁词 ----------------
    disc = rep["disclosure"]
    check("C8a 披露块：三布尔守卫为真 ∧ layer/known_drift 为字符串",
          all(disc[k] is True for k in ("no_foundry_truth", "no_project_measurement",
                                        "no_efficiency_metric_reported"))
          and isinstance(disc["layer"], str) and isinstance(disc["known_drift"], str))
    surf = _positive_surface(repr(rep))
    hits = [b for b in _BANNED_POSITIVE if b in surf]
    check("C8b 真实输出**肯定式面**禁词零命中（否定式免责句不误伤）", not hits)
    # 反向：真把禁词写进肯定式面 ⇒ 扫描器必抓（证明扫描器非恒真）
    check("C8c 探针：肯定式面注入 pJ/bit ⇒ 必被抓",
          bool([b for b in _BANNED_POSITIVE if b in _positive_surface("本设计能效 pJ/bit 为 3")]))

    # ---------------- C9 报告自洽 ----------------
    hl = rep["matlib"]["headline"]["cross_source_spread"]["GST"]
    check("C9 headline 离散度 == 逐来源重算",
          abs(hl["k_spread_x"] - gst_c["k_spread_x"]) < 1e-12)

    # ---------------- 探针（每条先证能变红）----------------
    # P1 损耗写成 ∝Γ² ⇒ Γ 不再约掉 ⇒ 律必破（若模块真这么写，C3 必红）
    def _il_pi_variant(g: float, gamma_power: int) -> float:
        l_pi = 1550e-9 / (2.0 * g * dn)
        return (10.0 / math.log(10.0)) * (g ** gamma_power) * (4.0 * math.pi * k_c / 1550e-9) * l_pi
    vs = [_il_pi_variant(g, 2) for g in (0.01, 0.05, 0.2)]
    mut_dev = (max(vs) - min(vs)) / min(vs)
    check("P1 探针须造分歧（损耗 ∝Γ² ⇒ Γ 相关性 %.2f ≫ 1e-12）" % mut_dev, mut_dev > 0.5)

    # P2 只留 1 个来源 ⇒ 离散度口径失效
    orig_opt = ML.OPTICAL_ANCHORS
    try:
        ML.OPTICAL_ANCHORS = {"GST": [orig_opt["GST"][0]]}
        single = ML.nk("GST", "crystalline")
        deg_fail = (single["k_spread_x"] is None) or (single["k_spread_x"] < 10.0)
    finally:
        ML.OPTICAL_ANCHORS = orig_opt
    check("P2 探针须造分歧（单来源 ⇒ C2 判据必红）", deg_fail)

    # P3 锚标「本项目实测」⇒ C1 守卫必 raise
    try:
        ML.OPTICAL_ANCHORS = {"GST": [dict(orig_opt["GST"][0], is_measured_by_this_project=True)]}
        raised = False
        try:
            ML._check_anchors()
        except ML.PMMatlibRedlineError:
            raised = True
    finally:
        ML.OPTICAL_ANCHORS = orig_opt
    check("P3 探针须造分歧（假实测声明 ⇒ C1 必红）", raised)

    # P4 台账造假（人工声明与机器验算打架）⇒ C7 不变式必红
    fake = [dict(g) for g in rep["gaps"]]
    for g in fake:
        if g["id"] == "PM-G2":
            g["declared_closed"] = True          # 声明闭合，但 evidence_ok=False
            g["closed"] = True
    check("P4 探针须造分歧（G2 声明闭合而证据不成立 ⇒ 台账不变式必红）",
          not all(g["declared_closed"] == g["evidence_ok"] for g in fake))

    # P5 长度压到 0.01µm ⇒ 读出能量下限爆炸
    ro_small = M.readout_margin("GST", l_um=0.01)
    ro_norm = rep["cell"]["readout"]
    check("P5 探针须造分歧（极短单元 ⇒ 读出判据必红）",
          (not ro_small["all_ok"]) and ro_norm["all_ok"])

    # P6 全部热锚缺 T_melt ⇒ 写预算必 raise（不合成）
    orig_th = ML.THERMAL_ANCHORS
    try:
        ML.THERMAL_ANCHORS = {"GST": [{"source": "synthetic", "rho_kg_m3": 6350.0, "cp_j_per_kg_k": 250.0}]}
        raised6 = False
        try:
            ML.write_energy_budget("GST", l_um=0.5, w_um=0.5, t_nm=20.0)
        except ML.PMMatlibRedlineError:
            raised6 = True
    finally:
        ML.THERMAL_ANCHORS = orig_th
    check("P6 探针须造分歧（全缺 T_melt ⇒ 写预算必 raise）", raised6)

    return 0 if (globals().get("PASS", 0) and not globals().get("FAIL", 0)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
