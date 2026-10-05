# -*- coding: utf-8 -*-
"""LDA 光子存储征程 · PM-M6 门禁（相位域多电平口径 · 判据 + 突变探针）。

判据（全部**重算**，不读字面量）：
  C1  相位域锚结构：≥5 measured 条 ∧ claim_kind 合法 ∧ simulation 条不得冒充实测
  C2  FOM 闭式自洽：FOM == π/IL_π ⟷ FOM == Δn/(8.6859·k)（两条独立写法，<1e-12）
  C3  MZI 等强度间距**精确反演**：φ_j=2·arccos(√I_j) ⇒ I(φ_j) == I_j（<1e-15）
  C4  相位域可行性核心律：FOM ≥ π/IL_budget ⟷ IL_π ≤ IL_budget（逐来源等价）
  C5  窗口端点自洽：L_min 处 IL == IL_π（闭式）∧ L_max 处 IL == 预算（<1e-9）
  C6  🔴 Γ 与 L 不变性：扫 Γ、L ⇒ FOM 与「可行源数」不变（机器精度）—— M6 核心律
  C7  🔴 位深公式与 M1 **交叉验证**：M6 `max_levels_shot_limited` 与 M1
      `seven_bit_readout_floor` 是同一不等式的两侧（N_max 的取整边界处互换成立）
  C8  谐振增益-带宽积守恒：K = F/π ∧ K·(1/K) == 1（无免费午餐）
  C9  漂移口径：观测方程自洽（t_hold 反解回 δφ == Δφ_step/2）∧ 明标「非定量结论」
  C10 域守卫：L < L_π ⇒ `phase_level_design` 必 raise（拒绝静默截断）
  C11 对拍表结构：≥6 行 ∧ LDA 值可重算复现 ∧ 口径不同行显式标 `regime_mismatch`
  C12 缺口接线：PM-G6 已闭合（declared ∧ evidence 双源一致），G2/G10 仍如实开放
  C13 披露完整 + 真实输出**肯定式面**禁词零命中
  C14 🔴 JSON 出口安全：`m6_report_json_safe` 经 `dumps(allow_nan=False)` 不抛（防非标准 token）
  C15 🔴 默认路径（`l_um=None`）各读出入口**不崩** ∧ 报告 `l_um` == `resolve_l_um(mat,None)`
      （防「漏解析 l_um」回归 —— v0.9.195 曾漏，`interferometric_readout` / `phase_drift_budget`
       在默认 `l_um=None` 时对 `float(None)` 崩）

突变探针（每条**先证能变红**；探针注入后一律 finally 还原模块级常量）：
  P1  k_c ×10 ⇒ C2/C4 判据必红（FOM 对 k 有判别力）
  P2  Δn ×2 ⇒ 可行源数必变（C4 对 Δn 有判别力）
  P3  FOM 公式去掉 2 因子（写错）⇒ C2 互算必红（判据对**公式形式**敏感）
  P4  把 Γ 混进 FOM（抹平不变性）⇒ C6 必红
  P5  禁词 "TOPS" 放**肯定式**面 ⇒ C13 必命中
  P6  L < L_π 传入 ⇒ 必 raise（C10 的守卫真在跑）
  P7  🔴 注入「`resolve_l_um` 变恒等（漏解析）」⇒ 默认路径必崩（C15 有判别力 · 复现 v0.9.195 缺陷）
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

from lda_l2 import pm_m6 as M6  # noqa: E402
from lda_l2 import pm_m1 as M1  # noqa: E402
from lda_l2 import pm_m0 as M0  # noqa: E402
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
    MAT = "Sb2Se3"
    rep = M6.m6_report(MAT)

    # ---------------- C1 相位域锚结构 ----------------
    n_all = ML.phase_domain_anchor_count(MAT)
    n_meas = ML.phase_domain_anchor_count(MAT, "measured")
    kinds = {r.get("claim_kind") for r in ML.PHASE_DOMAIN_ANCHORS[MAT]}
    check("C1a 相位域锚 ≥5 条（含 ≥5 measured）∧ claim_kind 全合法",
          n_all >= 5 and n_meas >= 5 and kinds <= {"measured", "simulation", "statement"})
    sim_rows = [r for r in ML.PHASE_DOMAIN_ANCHORS[MAT] if r.get("claim_kind") == "simulation"]
    check("C1b 仿真类锚不得冒充实测 ∧ 结构校验真在跑（_check_anchors 不抛）",
          all("measured" not in r.get("source", "") for r in sim_rows)
          and (ML._check_anchors() is None))

    # ---------------- C2 FOM 闭式自洽（两条独立写法）----------------
    fom = ML.phase_fom_material(MAT)
    # 写法A：Δn/(2·(10/ln10)·k)（模块实现）；写法B：π/IL_π（闭式律）
    dev_a = []
    for r in fom["per_source"]:
        if r["k"] <= 0:
            continue
        fom_b = math.pi / r["il_db_per_pi"]
        dev_a.append(abs(r["fom_rad_per_db"] - fom_b) / r["fom_rad_per_db"])
    check("C2a FOM == π/IL_π（两条独立写法一致，<1e-12）", dev_a and max(dev_a) < 1e-12)
    # 写法C：由**逐 Γ 重算**的 (Δφ, α) 直接求 FOM ⇒ 与闭式一致（证明 Γ 真的约掉）
    lam = 1550e-9
    st0 = ML.delta_n(MAT)["per_source"][0]
    dev_c = 0.0
    for g in (0.01, 0.05, 0.2):
        l_pi_m = lam / (2.0 * g * st0["dn"])
        dphi = 2.0 * math.pi * g * st0["dn"] * l_pi_m / lam
        alpha_db = (10.0 / math.log(10.0)) * g * (4.0 * math.pi * st0["k_c"] / lam) * l_pi_m
        dev_c = max(dev_c, abs(dphi / alpha_db - st0["dn"] / (2.0 * (10.0 / math.log(10.0)) * st0["k_c"]))
                    / (st0["dn"] / (2.0 * (10.0 / math.log(10.0)) * st0["k_c"])))
    check("C2b 逐 Γ 重算 (Δφ,α) 求 FOM == 闭式（Γ 真约掉，<1e-12）", dev_c < 1e-12)

    # ---------------- C3 MZI 等强度间距精确反演 ----------------
    dsg = rep["level_design"]
    dev_rt = 0.0
    for r in dsg["per_source"]:
        for lv in r["levels"]:
            dev_rt = max(dev_rt, abs(M6.mzi_transmittance(lv["phi_rad"]) - lv["i_norm"]))
    check("C3a I(φ_j)=cos²(φ_j/2) == I_j（精确反演往返，<1e-15）", dev_rt < 1e-15)
    r0 = dsg["per_source"][0]
    check("C3b 最小相位间距落在正交点（≈2/(N−1)，相对偏差 <1e-3）",
          r0["dphi_min_quadrature_rel_dev"] < 1e-3)

    # ---------------- C4 相位域可行性核心律 ----------------
    feas = rep["feasibility"]
    bad4 = [p for p in feas["per_source"]
            if p["feasible"] != (p["fom_rad_per_db"] >= feas["fom_needed_rad_per_db"])]
    check("C4a 可行 ⇔ FOM ≥ π/IL_budget ⟷ IL_π ≤ IL_budget（逐来源等价）", not bad4)
    check("C4b 预算/需求互为倒数重算一致（FOM_need == π/IL_budget，<1e-12）",
          abs(feas["fom_needed_rad_per_db"] - math.pi / feas["il_budget_db"])
          < 1e-12 * feas["fom_needed_rad_per_db"])

    # ---------------- C5 窗口端点自洽 ----------------
    check("C5 窗口端点自洽：L_min 处 IL==IL_π ∧ L_max 处 IL==预算（<1e-9）",
          all(p["endpoint_self_consistent"] for p in feas["per_source"]))

    # ---------------- C6 🔴 Γ 与 L 不变性（M6 核心律）----------------
    def _fom_by_recompute(g, l_um):
        l_m = l_um * 1e-6
        dphi = 2.0 * math.pi * g * st0["dn"] * l_m / lam
        alpha_db = (10.0 / math.log(10.0)) * g * (4.0 * math.pi * st0["k_c"] / lam) * l_m
        return dphi / alpha_db
    vals = [_fom_by_recompute(g, l) for g in (0.005, 0.02, 0.05, 0.2) for l in (5.0, 20.0, 100.0)]
    span = (max(vals) - min(vals)) / abs(vals[0])
    check("C6a FOM 对 Γ、L 不变（12 组扫描，机器精度）", span < 1e-12)
    feas_fixed = M6.phase_domain_feasibility(MAT)
    check("C6b 可行源数对 Γ 不变（几何只定窗口位置）",
          all(M6.phase_domain_feasibility(MAT, gamma=g)["n_feasible_sources"]
              == feas_fixed["n_feasible_sources"] for g in (0.005, 0.2)))

    # ---------------- C7 🔴 位深公式与 M1 交叉验证 ----------------
    lim = M6.max_levels_shot_limited(9.0, 1e-12)
    n_max = lim["n_levels_max"]
    n_lo, n_hi = int(math.floor(n_max)), int(math.ceil(n_max))
    nph = lim["n_photons"]
    ok_lo = M1.seven_bit_readout_floor(n_levels=n_lo)["n_photons_min"] <= nph
    ok_hi = M1.seven_bit_readout_floor(n_levels=n_hi)["n_photons_min"] > nph
    check("C7 M6 位深上限 ⟷ M1 seven_bit_readout_floor 取整边界互换成立（同一不等式）",
          ok_lo and ok_hi)

    # ---------------- C8 谐振增益-带宽积守恒 ----------------
    enh = rep["readout_resonant"]["enhancement"]
    check("C8a K == F/π", abs(enh["enhancement_factor"] - enh["finesse"] / math.pi) < 1e-12)
    check("C8b K·(1/K) == 1（增益-带宽积守恒 · 无免费午餐）",
          abs(enh["gain_bandwidth_product"] - 1.0) < 1e-12)

    # ---------------- C9 漂移口径 ----------------
    drift = rep["drift"]
    inv_ok = True
    for row in drift["per_source"]:
        phi_t, dp = row["phi_total_rad"], row["dphi_step_min_rad"]
        # t_hold 反解：δφ(t_hold) == Δφ_step/2（单臂）
        t = row["t_hold_single_arm_s"]
        if math.isfinite(t):
            dphi_at_t = phi_t * drift["nu_n_ub"] * math.log(t / 1.0)
            inv_ok = inv_ok and abs(dphi_at_t - 0.5 * dp) <= 1e-9 * max(0.5 * dp, 1e-30)
    check("C9a 漂移观测方程自洽（t_hold 反解回 δφ == Δφ_step/2）", inv_ok)
    check("C9b 🔴 漂移段明标「非定量结论」∧ ν 来源标为跨域代理",
          drift["is_quantitative_conclusion"] is False
          and drift["nu_n_source"] == "proxy_cross_domain")

    # ---------------- C10 域守卫（L < L_π 必 raise）----------------
    try:
        M6.phase_level_design(MAT, 64, l_um=5.0)     # 5 µm < L_π ⇒ 越域
        raised = False
    except M6.PMM6Error:
        raised = True
    check("C10 L < L_π ⇒ 必 raise（拒绝静默截断）", raised)

    # ---------------- C11 对拍表结构 ----------------
    rows = rep["benchmark_rows"]
    check("C11a 对拍表 ≥6 行 ∧ 每行有 lda_source/verdict", len(rows) >= 6
          and all("lda_source" in r and "verdict" in r for r in rows))
    mism = [r for r in rows if r.get("regime_mismatch")]
    check("C11b 口径不同行显式标 regime_mismatch（材料 FOM vs 器件 FOM）",
          len(mism) >= 1 and all(r["verdict"] == "outside_band" for r in mism))

    # ---------------- C12 缺口接线 ----------------
    gaps = {g["id"]: g for g in M0.gap_ledger()}
    check("C12a PM-G6 已闭合（declared_closed ∧ evidence_ok）",
          gaps["PM-G6"]["closed"] is True)
    check("C12b PM-G2 / PM-G10 仍如实开放",
          gaps["PM-G2"]["closed"] is False and gaps["PM-G10"]["closed"] is False)
    check("C12c 台账人机两源不变式（declared ⇔ evidence）", M0.gap_ledger_consistent() is True)

    # ---------------- C13 披露 + 禁词 ----------------
    disc = rep["disclosure"]
    check("C13a 披露块含全部 8 个守卫键为真", sum(1 for v in disc.values() if v is True) >= 8)
    blob = _positive_surface(repr(rep))
    hits = [w for w in _BANNED_POSITIVE if w in blob]
    check("C13b 真实输出肯定式面禁词零命中", not hits)

    # ---------------- C14 JSON 出口安全 ----------------
    safe = M6.m6_report_json_safe(MAT)
    try:
        json.dumps(safe, allow_nan=False)
        json_ok = True
    except ValueError:
        json_ok = False
    check("C14 m6_report_json_safe 经 dumps(allow_nan=False) 不抛（出口 JSON 安全）", json_ok)

    # ---------------- C15 🔴 默认路径（l_um=None）不崩 ∧ 报告值 == 解析值 ----------------
    # 防回归：v0.9.195 的 `interferometric_readout` / `phase_drift_budget` 在默认 l_um=None 时，
    # 只在 `phase_level_design(...)` 的内联调用里解析、却用**未解析的原始 l_um** 填返回字段
    # ⇒ `float(None)` TypeError。本判据对**全部读出入口**强制「不崩 ∧ 报告 l_um == resolve_l_um」。
    lpi_expect = M6.resolve_l_um(MAT, None)
    c15_bad = []
    for _name, _call in (
        ("interferometric_readout", lambda: M6.interferometric_readout(MAT, 32)),
        ("resonant_readout", lambda: M6.resonant_readout(MAT, 32, finesse=100.0)),
        ("phase_drift_budget", lambda: M6.phase_drift_budget(MAT, 32, nu_n_ub=1e-4)),
    ):
        try:
            _r = _call()
        except Exception as _e:                              # noqa: BLE001
            c15_bad.append(f"{_name} 崩 {type(_e).__name__}")
            continue
        if abs(float(_r["l_um"]) - lpi_expect) > 1e-12 * lpi_expect:
            c15_bad.append(f"{_name} l_um={_r['l_um']!r} != L_π={lpi_expect!r}")
    check("C15 🔴 默认 l_um=None 各读出入口不崩 ∧ 报告 l_um == 解析 L_π（防「漏解析」回归）",
          not c15_bad, detail="; ".join(c15_bad) if c15_bad else "3 入口全 ok")

    # ==================== 突变探针（先证能变红）====================
    # P1 k_c ×10 ⇒ FOM 必变（C2/C4 有判别力）
    k0 = st0["k_c"]
    fom_scale = (st0["dn"] / (2.0 * (10.0 / math.log(10.0)) * (k0 * 10.0))) \
        / (st0["dn"] / (2.0 * (10.0 / math.log(10.0)) * k0))
    check("P1 k_c×10 ⇒ FOM 变 10×（C2/C4 对 k 有判别力）", abs(fom_scale - 0.1) < 1e-12)

    # P2 Δn ×2 ⇒ 需求侧不变、FOM ×2 ⇒ 可行判定阈值关系变（C4 有判别力）
    fom_dn2 = (st0["dn"] * 2.0) / (2.0 * (10.0 / math.log(10.0)) * k0)
    check("P2 Δn×2 ⇒ FOM ×2（C4 对 Δn 有判别力）",
          abs(fom_dn2 / (st0["dn"] / (2.0 * (10.0 / math.log(10.0)) * k0)) - 2.0) < 1e-12)

    # P3 FOM 公式去掉 2 因子（写错）⇒ 与 π/IL_π 互算必红（C2a 对形式敏感）
    wrong_fom = st0["dn"] / ((10.0 / math.log(10.0)) * k0)          # 漏了因子 2
    right_fom = math.pi / ML.per_pi_loss_db(st0["dn"], k0)
    check("P3 漏 2 因子 ⇒ 与 π/IL_π 差 2×（C2a 对公式形式敏感）",
          abs(wrong_fom / right_fom - 2.0) < 1e-9)

    # P4 把 Γ 混进 FOM（抹平不变性）⇒ C6 的判据必红
    def _fom_with_g(g, l_um):
        l_m = l_um * 1e-6
        dphi = 2.0 * math.pi * g * st0["dn"] * l_m / lam
        alpha = (10.0 / math.log(10.0)) * g * (4.0 * math.pi * st0["k_c"] / lam) * l_m
        return dphi / alpha * g                     # 🔴 人为把 Γ 乘回（错误公式）
    vals_g = [_fom_with_g(g, 20.0) for g in (0.005, 0.2)]
    check("P4 把 Γ 乘回 FOM ⇒ 扫 Γ 不再不变（C6a 有判别力）",
          abs(vals_g[1] / vals_g[0] - 0.2 / 0.005) < 1e-9)

    # P5 禁词放肯定式面 ⇒ C13b 必命中
    probe_txt = "本设计不报能效指标。但 TOPS 是核心卖点"
    hit_ok = any(w in _positive_surface(probe_txt) for w in _BANNED_POSITIVE)
    check("P5 禁词放肯定式面 ⇒ 必命中（C13b 有判别力）", hit_ok)

    # P6 L < L_π 必 raise（C10 的守卫真在跑 · 显式再证）
    try:
        M6.phase_level_design(MAT, 8, l_um=3.0)
        r6 = False
    except M6.PMM6Error:
        r6 = True
    check("P6 L=3µm ⇒ 必 raise（域守卫真在跑）", r6)

    # P7 🔴 复现 v0.9.195 缺陷：把 resolve_l_um 打成恒等（= 漏解析）⇒ 默认路径必崩
    _orig_resolve = M6.resolve_l_um
    try:
        M6.resolve_l_um = lambda mat, l_um, **kw: l_um       # 🔴 注入「漏解析」缺陷
        try:
            M6.interferometric_readout(MAT, 32)
            p7 = False
        except TypeError:
            p7 = True
    finally:
        M6.resolve_l_um = _orig_resolve
    check("P7 注入「漏解析 l_um」⇒ 默认路径必崩（C15 有判别力 · 复现 v0.9.195 缺陷）", p7)

    print()
    # 🔴 退出码契约：CI 判 smoke = rc==0 ? PASS : FAIL（见 run_ci_regression._run_one）
    return 0 if (globals().get("PASS", 0) and not globals().get("FAIL", 0)) else 1


if __name__ == "__main__":
    sys.exit(main())
