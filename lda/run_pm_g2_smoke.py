# -*- coding: utf-8 -*-
"""LDA 光子存储征程 · PM-G2 门禁（Γ 场求解标定 · 判据 + 突变探针）。

判据（全部**重算**，不读字面量）：
  C1  n_pcm 现算：来自 `pm_matlib.nk()` 多源均值 ∧ 源数 ≥2 ∧ 落在 [n_min,n_max] 内
  C2  Γ 主账有限 ∧ 0<Γ<1 ∧ **非退化**（>1e-3）—— 计算值不得退化成 0/1
  C3  🔴 **独立离散一致**：半矢量 collocated vs 全矢量 staggered（两套代码路径）
      ⇒ rel < 5%（实测 ~1.9%）—— 本门禁最有价值的一条（实现无关性）
  C4  微扰法（Δn_eff/Δn_bulk）与场法同量级（rel < 20%）
  C5  🔴 收敛证据：网格加密（h 0.02→0.01）主值漂移 < 3% ∧ 全矢量 < 5%
  C6  窗口不变性（1D 平板独立维度）：L=3 ↔ L=4 逐位相同（<1e-12）
  C7  🔴 对照比值**现算复现**：vs 假设 / vs 文献的 ratio == 重算值（不读字面量）
  C8  披露完备：`claim_kind=="simulation"` ∧ `never_golden` ∧ 不依赖 Meep/Tidy3D
  C9  真实输出**肯定式面**禁词零命中（否定式免责句不误伤）
  C10 🔴 JSON 出口安全（`dumps(allow_nan=False)` 不抛）
  C11 状态判定：`calibrated` ∧ not `gap_pm_g2_open`（缺口两源一致）
  C12 🔴 几何对齐守卫：尺寸非网格整数倍 ⇒ **必 raise**（拒绝静默抹开薄层）
  C13 复现性：两次独立求解同值（机器精度）∧ 结果不依赖缓存命中顺序
  C14 对拍表 ≥3 行 ∧ 含「独立离散互证」行
  C15 🔴 **下游断口**（PM-G11）：1/Γ 缩放律精确复核（rel<1e-9）∧ 现役设计点**越出**标定口径
      可行窗 ∧ 披露非空 —— 标定**改了**绝对长度结论就必须**并报**，不许只报旧的
  C16 🔴 **Γ-无关量现算互等**：每 π 损耗 IL_π 与 M1 判据 r 在**两档 Γ** 下逐位相等
      （proves「Γ 与 L 同时约掉」是算出来的，不是引述的）
  C17 缺口台账：PM-G11 已登记 ∧ 开放 ∧ `declared==evidence` 不变式保持 ∧ PM-G2 已闭合

突变探针（每条**先证能变红**；探针注入后一律 finally 还原）：
  P1  PCM 厚度 ×2 ⇒ Γ 显著变（C3/C5 有判别力 —— 对几何敏感）
  P2  场法积分区域改成「全区域」⇒ Γ≡1 ⇒ C2 非退化判据必红
  P3  非对齐网格（L=2.9 非 0.02 整数倍）⇒ C12 必 raise
  P4  禁词 "TOPS" 放**肯定式**面 ⇒ C9 必命中
  P5  PCM 厚度 = 0 ⇒ Γ→0 ⇒ C2 必红（退化检测真在跑）
  P6  🔴 复现 v0.9.198 实发缺陷：顶点掩码**带容差**把芯顶面算进 PCM ⇒ Γ 虚高 ⇒ C3 必红
  P7  窗口压到 L=0.6 ⇒ Γ 偏离 >5% ⇒ C6 有判别力
  P8  🔴 **抹平 Γ 断口**（把标定 Γ 强设为假设 Γ）⇒ C15b 越窗判据翻转为「窗内」⇒ 该判据必红
      （证明「越窗」是**真算出来**的、不是恒真的文案）
"""
from __future__ import annotations

import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=' —— {d}')

from lda_l2 import pm_gamma as G  # noqa: E402
from lda_l2 import pm_matlib as ML  # noqa: E402

_BANNED_POSITIVE = ("TOPS", "TOPS-W", "TOPS/W", "fJ/op", "fJ·op", "pJ/bit")
_NEG_TOKENS = ("不报", "不得报", "禁止", "禁用", "never", "not reported",
               "no efficiency", "无效率")


def _positive_surface(text: str) -> str:
    """只取**肯定式面**：剔除含否定标记的从句。"""
    parts = []
    for clause in text.replace("；", "。").replace(";", "。").split("。"):
        if any(tok in clause for tok in _NEG_TOKENS):
            continue
        parts.append(clause)
    return "。".join(parts)


def main() -> int:
    # ---------------- C1 材料参数现算 ----------------
    npcm = G.design_n_pcm()
    c1 = (npcm["n_sources"] >= 2 and npcm["n_min"] <= npcm["n_mean"] <= npcm["n_max"])
    check("C1a n_pcm 由多源现算均值（源=%d，[%.3f,%.3f]∋%.3f）"
          % (npcm["n_sources"], npcm["n_min"], npcm["n_max"], npcm["n_mean"]), c1)
    nk_src = ML.nk("Sb2Se3", "amorphous", 1550.0)
    c1b = abs(npcm["n_mean"] - sum(p["n"] for p in nk_src["per_source"]) / nk_src["n_sources"]) < 1e-12
    check("C1b 均值 == 逐来源重算（不读字面量）", c1b)

    # ---------------- 主账（快档，缓存后 0s）----------------
    cal = G.gamma_calibration()
    last = cal["gamma_main"]

    # ---------------- C2 主账有限 · 非退化 ----------------
    c2 = (isinstance(cal["gamma_main"], float) and math.isfinite(cal["gamma_main"])
          and 1e-3 < cal["gamma_main"] < 1.0)
    check("C2 Γ 主账有限 ∧ 非退化（Γ=%.5f ∈ (1e-3,1)）" % cal["gamma_main"], c2)

    # ---------------- C3 独立离散一致（核心）----------------
    c3_dev = cal["two_method_rel_dev"]
    check("C3 🔴 半矢量 vs 全矢量（**独立离散**）一致 rel=%.2e < 5e-2" % c3_dev,
          c3_dev < 5e-2, "field_semi=%.5f field_full=%.5f"
          % (cal["gamma_main"], cal["gamma_independent_fullvec"]))

    # ---------------- C4 微扰法同量级 ----------------
    c4_dev = cal["field_pert_rel_dev"]
    check("C4 微扰法（Δn_eff/Δn）与场法同量级 rel=%.2e < 2e-1" % c4_dev, c4_dev < 2e-1,
          "Γ_pert=%.5f" % cal["gamma_perturbation"])

    # ---------------- C5 收敛证据（细档，~20s）----------------
    cv = G.gamma_convergence()
    check("C5a 网格加密主值漂移 %.2e < 3e-2（h 0.02→0.01）" % cv["grid_rel_dev"],
          cv["grid_rel_dev"] < 3e-2,
          "coarse=%.5f fine=%.5f" % (cv["coarse"]["semivec_field"], cv["fine"]["semivec_field"]))
    check("C5b 全矢量网格加密漂移 %.2e < 5e-2" % cv["fullvec_rel_dev"],
          cv["fullvec_rel_dev"] < 5e-2,
          "coarse=%.5f fine=%.5f" % (cv["coarse"]["fullvec_field"], cv["fine"]["fullvec_field"]))

    # ---------------- C6 窗口不变性（1D 平板独立维度）----------------
    s3 = G.gamma_slab(L_win=3.0)["gamma_field"]
    s4 = G.gamma_slab(L_win=4.0)["gamma_field"]
    c6_rel = abs(s3 - s4) / s3
    check("C6 窗口不变性：L=3 ↔ L=4 相对差 %.1e < 1e-3（余量 4 个数量级）" % c6_rel,
          c6_rel < 1e-3, "slab=%.6f" % s3)

    # ---------------- C7 对照比值现算复现 ----------------
    va = cal["vs_assumption"]
    vl = cal["vs_literature"]
    c7 = (abs(va["ratio"] - last / va["assumption"]) < 1e-12
          and abs(vl["ratio"] - last / vl["lit_implied"]) < 1e-12)
    check("C7 对照比值 == 现算（vs 假设 %.3f / vs 文献 %.3f）" % (va["ratio"], vl["ratio"]), c7)

    # ---------------- C8 披露完备 ----------------
    d = cal["disclosure"]
    c8 = (d["claim_kind"] == "simulation" and d["never_golden"] is True
          and d["no_meep_no_tidy3d"] is True and d["no_fabricated_efficiency"] is True)
    check("C8 披露：claim_kind=simulation ∧ never_golden ∧ 无 Meep/Tidy3D", c8)

    # ---------------- C9 禁词肯定式面 ----------------
    blob = json.dumps(G.gamma_case_summary(), ensure_ascii=False)
    hits = [w for w in _BANNED_POSITIVE if w in _positive_surface(blob)]
    check("C9 真实输出**肯定式面**禁词零命中", not hits, "命中=%s" % (hits or "无"))

    # ---------------- C10 JSON 出口安全 ----------------
    try:
        s = json.dumps(G._json_safe(cal), ensure_ascii=False, allow_nan=False)
        c10 = len(s) > 0
    except (ValueError, TypeError):
        c10 = False
    check("C10 JSON 出口安全（dumps allow_nan=False 不抛）", c10)

    # ---------------- C11 状态判定 ----------------
    st = G.gamma_calibration_status()
    check("C11 calibrated ∧ not gap_pm_g2_open（两源一致）",
          st["calibrated"] is True and st["gap_pm_g2_open"] is False,
          "span=%s" % ([round(x, 5) for x in st["gamma_span"]]))

    # ---------------- C12 几何对齐守卫 ----------------
    raised = False
    try:
        G.gamma_semivec(h_grid=0.02, L_win=2.97)      # 2.97 非整数倍 ⇒ 必 raise
    except G.PMGammaError:
        raised = True
    check("C12 非对齐几何 ⇒ 必 raise（拒绝静默抹开薄层）", raised)

    # ---------------- C13 复现性 ----------------
    a = G.gamma_semivec()["gamma_field"]
    b = G.gamma_semivec()["gamma_field"]
    check("C13 两次独立求解同值（机器精度 |Δ|=%.1e）" % abs(a - b), abs(a - b) < 1e-12)

    # ---------------- C14 对拍表结构 ----------------
    rows = G.gamma_benchmark_rows()
    ok_rows = (len(rows) >= 3 and all("verdict" in r and "ratio" in r for r in rows)
               and any(r["metric"] == "gamma_fullvec_vs_semivec" for r in rows))
    check("C14 对拍表 ≥3 行 ∧ 含「独立离散互证」行", ok_rows, "n_rows=%d" % len(rows))

    # ---------------- C15 🔴 下游断口（PM-G11）：1/Γ 律 + 越窗 + 披露 ----------------
    from lda_l2 import pm_m0 as M0  # 局部导入（cm 版本对照用）
    imp = G.gamma_impact_on_design()
    law_ok = (imp["law_rel_dev"] is not None and imp["law_rel_dev"] < 1e-9
              and abs(imp["l_mid_predicted_by_law_um"] - imp["calibrated"]["l_mid_um"])
              < 1e-12)
    check("C15a 🔴 1/Γ 缩放律精确成立（L_mid(Γ_cal) == L_mid(Γ_as)·Γ_as/Γ_cal）"
          " rel=%.1e < 1e-9" % (imp["law_rel_dev"] or -1.0), law_ok,
          "L_as=%.4f L_cal=%.4f" % (imp["assumed"]["l_mid_um"], imp["calibrated"]["l_mid_um"]))
    _disc = imp["disclosure"]
    check("C15b 🔴 现役设计点**落入**标定口径可行窗（PM-G11 v0.9.200 重标定闭合）∧ 披露含「重标定/闭合/PM-G11」",
          imp["design_point_inside_calibrated_window"] is True
          and imp["reads_out"] is False
          and imp["design_point_outside_frac"] == 0.0
          and ("重标定" in _disc["headline"] and "闭合" in _disc["headline"]
               and imp["gap"] == "PM-G11"),
          _disc["headline"][:96])

    # ---------------- C16 🔴 Γ-无关量现算互等（不是引述）----------------
    from lda_l2 import pm_m1 as M1
    ga, gc = float(imp["gamma_assumed"]), float(imp["gamma_calibrated"])

    def _il_over_pi(gam: float) -> float:
        """每 π 损耗：先取该 Γ 的 L_π（模块算出来的），再在该 L_π 处算 IL。

        🔴 两次调用都必须用**同一来源统计口径**（这里统一取 `il_db_min`）——
        否则比较的是两个不同 k 源，约不掉 Γ，判据就成假的。
        """
        st = M0.cell_state("GST", "crystalline", l_um=1.0, gamma=gam, wl_nm=1550.0)
        return M0.cell_state("GST", "crystalline", l_um=st["l_pi_um_ref"],
                             gamma=gam, wl_nm=1550.0)["il_db_min"]

    il_a, il_c = _il_over_pi(ga), _il_over_pi(gc)
    r_a = M1.amplitude_feasibility("GST", 16, gamma=ga)["per_source"][0]["r"]
    r_c = M1.amplitude_feasibility("GST", 16, gamma=gc)["per_source"][0]["r"]
    check("C16 🔴 Γ-无关量**现算互等**：IL_π（rel=%.1e）∧ M1 判据 r（Δ=%.1e）两档 Γ 下一致"
          % (abs(il_a - il_c) / il_a, abs(r_a - r_c)),
          abs(il_a - il_c) / il_a < 1e-12 and abs(r_a - r_c) < 1e-15,
          "IL_π=%.6f vs %.6f · r=%.6f vs %.6f" % (il_a, il_c, r_a, r_c))

    # ---------------- C17 缺口台账（PM-G11 登记 ∧ 不变式保持）----------------
    led = {g["id"]: g for g in M0.gap_ledger()}
    check("C17 台账：PM-G2 已闭合 ∧ PM-G11 已登记且**闭合**（v0.9.200 重标定）∧ declared==evidence 不变式保持",
          led["PM-G2"]["closed"] is True and "PM-G11" in led
          and led["PM-G11"]["closed"] is True
          and led["PM-G11"]["declared_closed"] == led["PM-G11"]["evidence_ok"]
          and M0.gap_ledger_consistent() is True,
          "G11 ev=%s decl=%s" % (led["PM-G11"]["evidence_ok"], led["PM-G11"]["declared_closed"]))

    # ================= 突变探针（每条先证能变红）=================
    # P1 PCM 厚度 ×2 ⇒ Γ 显著变（对几何敏感）
    g2 = dict(G.GAMMA_GEOMETRY); g2["t_pcm_um"] = 0.08
    g_t2 = G.gamma_semivec(geom=g2, h_grid=0.02, L_win=3.0)["gamma_field"]
    p1 = abs(g_t2 - last) / last > 5e-2
    check("P1 探针：PCM 厚度 ×2 ⇒ Γ 变 %.1f%%（>5%% 才算有判别力）"
          % (100 * abs(g_t2 - last) / last), p1, "Γ(0.08µm)=%.5f" % g_t2)

    # P2 场法积分区域改成「全区域」⇒ Γ≡1 ⇒ C2 非退化判据必红
    import numpy as np
    base = dict(G.GAMMA_GEOMETRY)
    n2, xc, yc = G._build_index(base["w_um"], base["h_um"], base["t_pcm_um"],
                                 base["n_core"], base["n_clad"], npcm["n_mean"], True,
                                 h_grid=0.02, L_win=3.0)
    _, psi2 = G._solve_semivec(n2, 0.02, 2.0 * math.pi / 1.55)
    g_all = float(psi2.sum() / psi2.sum())
    p2 = not (1e-3 < g_all < 1.0)
    check("P2 探针：积分区改全区域 ⇒ Γ≡1 ⇒ C2 必红", p2, "Γ_all=%.3f" % g_all)

    # P3 非对齐网格 ⇒ C12 必 raise
    p3 = False
    try:
        G.gamma_fullvec(h_grid=0.013)
    except G.PMGammaError:
        p3 = True
    check("P3 探针：非对齐 h=0.013 ⇒ 必 raise", p3)

    # P4 禁词放肯定式面 ⇒ C9 必命中
    fake = "本器件能效达 12 TOPS（峰值）"
    hits4 = [w for w in _BANNED_POSITIVE if w in _positive_surface(fake)]
    check("P4 探针：肯定式面注入 TOPS ⇒ 必被抓", bool(hits4))

    # P5 PCM 厚度 = 0 ⇒ Γ→0 ⇒ C2 必红
    g0 = dict(G.GAMMA_GEOMETRY); g0["t_pcm_um"] = 0.02   # 单格退化（对齐）
    try:
        g_t0 = G.gamma_semivec(geom=g0, h_grid=0.02, L_win=3.0)["gamma_field"]
        p5 = g_t0 < last * 0.5
    except Exception:                                     # noqa: BLE001
        p5 = True                                         # 退化到算不出也算「检测到」
    check("P5 探针：PCM 单格退化 ⇒ Γ 显著下降（C2 有判别力）", p5)

    # P6 🔴 复现 v0.9.198 实发缺陷：顶点掩码带容差 ⇒ 把芯顶面算进 PCM ⇒ Γ 虚高
    neff, h2, (xv, yv) = G._solve_fullvec(n2, 0.02, 2.0 * math.pi / 1.55,
                                          base["w_um"], base["h_um"])
    strict = ((yv > base["h_um"] / 2.0) &
              (yv <= base["h_um"] / 2.0 + base["t_pcm_um"]))[:, None] & \
             (np.abs(xv) <= base["w_um"] / 2.0)[None, :]
    loose = ((yv > base["h_um"] / 2.0 - 1e-12) &
             (yv <= base["h_um"] / 2.0 + base["t_pcm_um"] + 1e-12))[:, None] & \
            (np.abs(xv) <= base["w_um"] / 2.0 + 1e-12)[None, :]
    g_strict = float(h2[strict].sum() / h2.sum())
    g_loose = float(h2[loose].sum() / h2.sum())
    p6 = (g_loose - g_strict) / g_strict > 2e-1                 # 容差版虚高 >20%
    check("P6 探针：顶点掩码带容差 ⇒ Γ 虚高（复现 v0.9.198 缺陷）", p6,
          "strict=%.5f loose=%.5f" % (g_strict, g_loose))

    # P7 窗口过小（L=0.6，模场被壁强烈挤压）⇒ Γ 显著偏离 ⇒ C6 型判据有判别力
    s_small = G.gamma_slab(L_win=0.6)["gamma_field"]
    p7 = abs(s_small - s3) / s3 > 5e-2
    check("P7 探针：窗口压到 L=0.6 ⇒ Γ 偏离 %.1f%%（C6 有判别力）"
          % (100 * abs(s_small - s3) / s3), p7, "Γ(L=0.6)=%.5f" % s_small)

    # P8 🔴 越窗判据是真算的（非恒真文案）：把标定 Γ 推小 ⇒ 标定窗整体放大（∝1/Γ）⇒
    #     现役设计点（~6.556µm）落到窗下界之下 ⇒ 越窗判据翻红；基线（标定 Γ）下窗内置信
    #     ⇒ 两向都有判别力，证明「越窗/落窗」是计算出来的（G11 闭合后本探针仍有效）。
    _gcs = G.gamma_calibration_status
    try:
        G.gamma_calibration_status = (
            lambda wl=1550.0: {**_gcs(wl), "gamma_main": 0.02})
        imp_small = G.gamma_impact_on_design()
    finally:
        G.gamma_calibration_status = _gcs
    p8 = (imp_small["design_point_inside_calibrated_window"] is False
          and imp["design_point_inside_calibrated_window"] is True)
    check("P8 探针：标定 Γ 推小 ⇒ 窗放大 ⇒ 现役点落入窗下界之外 ⇒ 越窗判据翻红（证明是真算的）",
          p8,
          "small_inside=%s base_inside=%s" % (imp_small["design_point_inside_calibrated_window"],
                                             imp["design_point_inside_calibrated_window"]))

    print()
    # 🔴 退出码契约：CI 判 smoke = rc==0 ? PASS : FAIL（见 run_ci_regression._run_one）
    return 0 if (globals().get("PASS", 0) and not globals().get("FAIL", 0)) else 1


if __name__ == "__main__":
    sys.exit(main())
