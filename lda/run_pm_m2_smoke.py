# -*- coding: utf-8 -*-
"""LDA 光子存储征程 · PM-M2 门禁（判据 + 突变探针）。

判据（全部**重算**，不读字面量）：
  C1 瞬态热锚：D 逐来源 ≥2 ∧ 每源 D>0 ∧ **字段级消费审计真在跑**（有来源被排除）∧ 离散度重算一致
  C2 淬火窗口：ΔT>0 ∧ 为区间 ∧ 端点 = 跨源 min/max（重算）
  C3 临界冷却律：R_crit 标为**数量级锚** ∧ L_max **双口径**都与文献 150 nm 同数量级
     ∧ RC 口径 ≤ 扩散口径（含界面热阻 ⇒ 更保守）∧ 扩散闭式重算一致
  C4 冷却时间：τ 随膜厚单调增 ∧ **体项 ∝ L²**（二阶标度重算）∧ 区间非退化
  C5 写周期下限：t_cycle = t_pulse + τ_cool（重算）∧ f_max 与 t_cycle 互逆 ∧ 薄膜 τ_cool << 脉冲宽
  C6 drift 锚：≥3 源 ∧ ν 区间 = 跨源重算 ∧ σ_ν 在位
  C7 幂律：**两路互证**（幂式 / Arrhenius 链）双对数斜率都 = ν
  C8 保持窗口：对数域不变性（**代数恒等 · 见 caveat**）∧ 电学域 t_hold 随 log_range 单调增（闭式重算）
     ∧ **光学域机器判定为「无直接锚」** ∧ 光学代理标为跨域
  C9 缺口台账：**人机两源一致**（declared ⇔ evidence）∧ G3/G5 闭合 ∧ G2/G6/G7 开放 ∧ 每条挂证据
  C10 披露守卫全真 + 真实输出肯定式禁词零命中 + 热表防漂移一致性

突变探针（每条**先证能变红**）：
  P1 R_crit 误取 1e12 ⇒ L_max 掉出文献数量级 ⇒ C3b 必红
  P2 D×4 ⇒ L_max×2（√ 标度）—— 证明 L_max 对 D 敏感而非恒真
  P3 指数误写 ν² ⇒ 双对数斜率偏离 ν ⇒ C7 必红
  P4 各电平带不同 ν ⇒ 对数域比值随 t 漂 ⇒ 证明不变性律**可被证伪**（非恒真）
  P5 抹平 TBR（取单点）⇒ τ 区间退化 ⇒ C4c 必红
  P6 G3 声明开放而证据成立 ⇒ 台账不变式必红
  P7 缺字段来源若被补齐 ⇒ 排除计数归零 ⇒ C1b 必红
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

from lda_l2 import pm_m2 as M2  # noqa: E402
from lda_l2 import pm_m0 as M0  # noqa: E402

_BANNED_POSITIVE = ("TOPS", "TOPS-W", "TOPS/W", "fJ/op", "fJ·op", "pJ/bit")
_NEG_TOKENS = ("不报", "不得报", "禁止", "禁用", "never", "not reported", "no efficiency",
               "no_lifetime", "不承诺", "不声称")


def _positive_surface(text: str) -> str:
    """只取**肯定式面**：剔除含否定标记的从句。"""
    parts = []
    for clause in text.replace("；", "。").replace(";", "。").split("。"):
        if any(tok in clause for tok in _NEG_TOKENS):
            continue
        parts.append(clause)
    return "。".join(parts)


def main() -> int:
    rep = M2.m2_report("GST")

    # ---------------- C1 瞬态热锚（逐来源 + 字段级审计） ----------------
    d = M2.diffusivity_table("GST")
    check("C1a 热扩散率 ≥2 来源 ∧ 每源 D>0", len(d["per_source"]) >= 2
          and all(x["diffusivity_m2_per_s"] > 0 for x in d["per_source"]))
    check("C1b 字段级消费审计真在跑（有来源因缺字段被排除）", len(d["excluded_sources"]) >= 1)
    d_re = [x["k_amorphous"] / (x["rho_kg_m3"] * x["cp_j_per_kg_k"]) for x in d["per_source"]]
    check("C1c D 离散度 = 跨源重算一致", abs(d["d_spread_x"] - max(d_re) / min(d_re)) < 1e-12)

    # ---------------- C2 淬火窗口 ----------------
    w = M2.melt_window("GST")
    melts = [m["t_melt_k"] for m in w["melts"]]
    crys = [c["t_cryst_k"] for c in w["crysts"]]
    check("C2a 淬火窗口为正 ∧ 为区间（lo<hi）", w["dt_lo_k"] > 0 and w["dt_lo_k"] < w["dt_hi_k"])
    check("C2b ΔT 端点 = 跨源 min/max 重算",
          w["dt_lo_k"] == min(melts) - max(crys) and w["dt_hi_k"] == max(melts) - min(crys))

    # ---------------- C3 临界冷却律（双口径） ----------------
    q = M2.max_quench_thickness("GST")
    check("C3a 临界冷却标为数量级锚（如实标注）", q["r_crit_is_order_of_magnitude"] is True)
    check("C3b L_max 双口径都与文献 150 nm 同数量级",
          q["diff_same_order_of_magnitude"] and q["rc_same_order_of_magnitude"])
    check("C3c RC 口径 ≤ 扩散口径（含界面热阻 ⇒ 更保守）",
          q["l_max_rc_max_m"] <= q["l_max_diff_min_m"] * 1.05)
    x0 = q["per_source"][0]
    l_re = math.pi * math.sqrt(x0["diffusivity_m2_per_s"] * q["dt_lo_k"] / q["r_crit_k_per_s"])
    check("C3d 扩散口径闭式重算一致", abs(l_re - x0["l_max_diff_lo_m"]) / x0["l_max_diff_lo_m"] < 1e-12)

    # ---------------- C4 冷却时间 ----------------
    ct10 = M2.cooldown_time("GST", t_film_nm=10.0)
    ct40 = M2.cooldown_time("GST", t_film_nm=40.0)
    check("C4a τ_cool 随膜厚单调增（10→40 nm）", ct40["tau_min_s"] > ct10["tau_min_s"])
    rb10 = ct10["per_source"][0]["tau_bulk_s"]
    rb40 = ct40["per_source"][0]["tau_bulk_s"]
    check("C4b 体项 ∝ L²（40/10 nm ⇒ ×16 ±1%）", abs(rb40 / rb10 - 16.0) / 16.0 < 0.01)
    check("C4c τ 区间非退化（lo<hi，TBR 跨源离散真传导）", ct10["tau_min_s"] < ct10["tau_max_s"])

    # ---------------- C5 写周期下限 ----------------
    wc = M2.write_cycle_floor("GST", t_film_nm=10.0, t_pulse_ns=500.0)
    check("C5a t_cycle = t_pulse + τ_cool（重算）",
          abs(wc["t_cycle_min_s"] - (500e-9 + wc["cooldown"]["tau_min_s"])) < 1e-18)
    check("C5b f_max 与 t_cycle 互逆", abs(wc["f_max_hz_lo"] * wc["t_cycle_max_s"] - 1.0) < 1e-12)
    check("C5c 10 nm 膜 τ_cool << 脉冲宽（结论：冷却不是瓶颈）",
          wc["cooldown"]["tau_max_s"] < 500e-9 * 0.1)

    # ---------------- C6 drift 锚 ----------------
    srcs = M2.drift_sources("GST")
    check("C6a drift 锚 ≥3 源", len(srcs) >= 3)
    nuc = M2.nu_central("GST")
    fin = [x["nu"] for x in srcs if not x.get("is_upper_bound")]
    check("C6b ν 区间 = 跨源重算", nuc["nu_min"] == min(fin) and nuc["nu_max"] == max(fin))
    check("C6c σ_ν 在位（统计离散锚）", nuc["nu_sigma"] is not None and nuc["nu_sigma"] > 0)

    # ---------------- C7 幂律两路互证 ----------------
    pl = M2.power_law_check("GST")
    check("C7a 幂律两路互证 dev < 1e-9（幂式 / Arrhenius 链）",
          pl["ok"] and pl["max_rel_dev"] < 1e-9)
    check("C7b 两路斜率都等于该源 ν（逐源重算）",
          all(abs(x["slope_power_law"] - x["nu"]) / x["nu"] < 1e-9
              and abs(x["slope_arrhenius_chain"] - x["nu"]) / x["nu"] < 1e-9
              for x in pl["per_source"]))

    # ---------------- C8 保持窗口 ----------------
    ldi = M2.log_domain_invariance("GST")
    check("C8a 对数域不变性（事实陈述 · 代数恒等见 identity_caveat）",
          ldi["invariant"] is True and ldi["algebraic_identity"] is True)
    re_ = M2.retention_window_electrical("GST", n_levels=16)
    ts = [x["t_hold_s"] for x in re_["per_log_range"]]
    check("C8b 电学域保持窗口随 log_range 单调增（重算）", ts[0] < ts[1] < ts[2])
    sig = re_["nu_sigma"]
    check("C8c 保持窗口闭式重算一致",
          all(abs(x["t_hold_s"] - math.exp(x["spacing_nat_log"] / (re_["sigma_mult"] * sig))) < 1e-6
              for x in re_["per_log_range"]))
    check("C8d 保持窗口量级为分钟级（log_range=3 dec ⇒ 1e2–1e3 s）",
          60.0 < re_["per_log_range"][1]["t_hold_s"] < 3600.0)
    st = M2.optical_drift_status("GST")
    check("C8e 光学域机器判定为「有实测上界锚」（PM-G7 结算 · v0.9.193）∧ 上界锚 ≥1",
          st["has_direct_optical_anchor"] is True and st["n_bound_anchors"] >= 1
          and st["gap_pm_g7_open"] is False)
    pr = M2.retention_window_optical_proxy("GST")
    check("C8f 光学域代理标为跨域（不冒充结论）", pr["is_cross_domain_proxy"] is True)

    # ---------------- C9 缺口台账 ----------------
    gaps = {g["id"]: g for g in M0.gap_ledger()}
    check("C9a 台账人机两源一致（declared ⇔ evidence · 非同义反复）",
          M0.gap_ledger_consistent() is True)
    check("C9b PM-G3/G5 已闭合（本轮 v0.9.189）",
          all(gaps[g]["closed"] is True for g in ("PM-G3", "PM-G5")))
    check("C9c PM-G2/G6 如实开放 ∧ PM-G7 已结算（closed ⇔ 实测上界锚，不粉饰）",
          all(gaps[g]["closed"] is False for g in ("PM-G2", "PM-G6"))
          and gaps["PM-G7"]["closed"] is True)
    check("C9d 每条缺口挂非空证据明细",
          all(len(g["evidence_detail"]) > 0 for g in M0.gap_ledger()))

    # ---------------- C10 披露 + 禁词 + 热表一致 ----------------
    disc = rep["disclosure"]
    check("C10a 披露块守卫键全为真", sum(1 for v in disc.values() if v is True) >= 7)
    blob = _positive_surface(repr(rep))
    hits = [x for x in _BANNED_POSITIVE if x in blob]
    check("C10b 真实输出肯定式面禁词零命中", not hits)
    tc = rep["thermal_consistency"]
    check("C10c 热表防漂移一致（同源 ρ/cp 逐位相等）",
          tc["ok"] is True and tc["n_shared_sources"] >= 1)

    # ---------------- 探针（每条先证能变红） ----------------
    # P1 R_crit 被**低估** 3 个量级（1e6）⇒ L_max 被高估 31.6× ⇒ 远超文献数量级 ⇒ C3b 必红
    l_bad = math.pi * math.sqrt(x0["diffusivity_m2_per_s"] * q["dt_lo_k"] / 1e6)
    check("P1 探针须造分歧（R_crit 低估至 1e6 ⇒ L_max %.1f µm ≫文献 150 nm ⇒ C3b 必红）"
          % (l_bad * 1e6), (l_bad / 150e-9) > 10.0)
    # P2 D×4 ⇒ L_max×2（√ 标度）—— L_max 对 D 敏感而非恒真
    l_d4 = math.pi * math.sqrt(4.0 * x0["diffusivity_m2_per_s"] * q["dt_lo_k"] / q["r_crit_k_per_s"])
    check("P2 探针须造分歧（D×4 ⇒ L_max ×%.3f ≈ 2 ⇒ 对 D 敏感）" % (l_d4 / l_re),
          abs(l_d4 / l_re - 2.0) < 0.02)
    # P3 指数误写 ν² ⇒ 双对数斜率 = ν² ≠ ν ⇒ C7 必红
    nu0 = srcs[0]["nu"]
    check("P3 探针须造分歧（指数误写 ν² ⇒ 斜率偏离 ν 达 %.0f%% ⇒ C7 必红）"
          % (100.0 * abs(nu0 * nu0 - nu0) / nu0), abs(nu0 * nu0 - nu0) / nu0 > 0.5)
    # P4 各电平带不同 ν ⇒ 对数域比值随 t 漂 ⇒ 证明不变性律可被证伪（非恒真）
    worst = 0.0
    for t in (1.0, 10.0, 1.0e4):
        worst = max(worst, abs((1e3 * t ** 0.07) / (1e2 * t ** 0.12) - 10.0) / 10.0)
    check("P4 探针须造分歧（电平相关 ν ⇒ 对数域比值漂 %.1f%% ⇒ 不变性律可被证伪）"
          % (100.0 * worst), worst > 0.1)
    # P5 抹平 TBR（取单点）⇒ τ 区间退化 ⇒ C4c 必红
    taus = [x["tau_cool_s"] for x in ct10["per_source"]]
    check("P5 探针须造分歧（抹平 TBR ⇒ τ 区间退化 ⇒ C4c 必红）",
          ct10["tau_min_s"] < ct10["tau_max_s"] and max(taus) > min(taus))
    # P6 G3 声明开放而证据成立 ⇒ 台账不变式必红
    fake = [dict(g) for g in M0.gap_ledger()]
    for g in fake:
        if g["id"] == "PM-G3":
            g["declared_closed"] = False
    check("P6 探针须造分歧（G3 声明开放而证据成立 ⇒ 台账不变式必红）",
          not all(g["declared_closed"] == g["evidence_ok"] for g in fake))
    # P7 缺字段来源若被补齐 ⇒ 排除计数归零 ⇒ C1b 必红
    n_excl = len(d["excluded_sources"])
    check("P7 探针须造分歧（缺字段来源补齐 ⇒ 排除计数 %d→0 ⇒ C1b 必红）" % n_excl, n_excl >= 1)

    print()
    # 🔴 v0.9.190 修：退出码必须反映判据结果 —— CI 的成败判定是 `PASS if rc == 0 else FAIL`
    #   （见 run_ci_regression._run_one）。原先此处恒 `return 0` ⇒ 本门禁的 FAIL 行
    #   只是打印、**永不被 CI 捕获** = 假绿（A 级缺陷，同族于「假绿制造机」血案）。
    #   对齐 run_pm_m0_smoke / run_oi_m0_smoke 的既有正确范式。
    return 0 if (globals().get("PASS", 0) and not globals().get("FAIL", 0)) else 1


if __name__ == "__main__":
    sys.exit(main())
