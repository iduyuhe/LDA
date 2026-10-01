# -*- coding: utf-8 -*-
"""E17 时序 / 时钟预算链门禁（D-187 · v0.9.165）。

═══════════════════════════════════════════════════════════════════════════
判什么（分节）
═══════════════════════════════════════════════════════════════════════════
A 模块自检（`timing.timing_self_check` **12 项**）
B 关键事实 name-first（19 条）：五个闭式 golden（G-1 RC 建立 · G-2 ½LSB@k ·
  G-3 Elmore 规模律 · G-4 SAR 拍数 · G-5 CDAC⇒时钟）· 🔴 **时间合成律按拓扑**
  （serial=Σ / pipelined=max · **与 E15 的误差分类合成律不同**）· 流水线口径 ·
  **R_oc=0 退化** · 跨模块交叉核对（E14 `t_to_half_lsb_8bit_s` / `_cdac_c_unit` /
  `sar_convert.trace`）· 五阶段单调 · 主导项 + **位数交叉** · 🔴 **规模×时间趋势相反** ·
  解析交叉点 · 时钟预算反解+代回 · 保护性约束（E7/E14 + E15/E16）· 诚实披露
C 反向可证伪：**6 条突变探针**（合成律改 RSS / ½LSB 漏 +1 / SAR 漏采样拍 /
  行线丢驱动源阻抗 / CDAC 漏 dummy 电容 / 注入「已报 TOPS」）⇒ 均必红 + **还原重跑**
K 自入 CI core（防静默漏接 · 血案 #28）

═══════════════════════════════════════════════════════════════════════════
🔴 本门禁的核心价值
═══════════════════════════════════════════════════════════════════════════
1. **「误差要分类，时间要分拓扑」是本段的第一原理**（B4/B5）。
   E15 的 `budget.combine` 按**类型**做 RSS（系统性 Σ / 随机 RSS / 有界 √3）；
   E17 的时间阶段是**物理串行**的 ⇒ 必须**代数相加**，流水线稳态取 **max**。
   ⇒ B5 特意断言「**对时间取 RSS 会给出不同值**」—— 否则「两套合成律」只是口号。
2. **退化必须退化为特例**（B7）：`R_oc = 0` ⇒ 行线时间退化为**纯 Elmore**（逐位）；
   且 `R_oc > 0` ⇒ **严格更大** ⇒ 探针 C4（丢掉驱动源阻抗项）**打得出来**。
   若只断言"相等"，丢项判据不特异 ⇒ 假探针。
3. 🔴 **规模 × 时间趋势相反**（B12）是本段最可讲的结论：
   `N: 8 → 1024` 时阵列 `τ_row` 跨 **12556×**（∝N²），而**每样本耗时只跨 1.00469×**。
   ⇒ **规模墙是「精度墙」（E15：IR drop ∝N²）不是「速度墙」** —— 加行列不拖慢采样率，但会毁掉有效位数。
4. **保护性约束**（B15/B16）：本段**只读消费** E7/E14，**不改**任何既有默认值；
   **不给** `PERIPHERY_PROCESS` 加时间键（E14 行驱动保持原样）；
   E15/E16 已发布数字**逐位不变**。⇒ 同 `NmosParams` / `mna.vcvs` 一族纪律。
5. 🔴 **诚实**（B17/B18）：**只报「每样本耗时（ns）」与相对量**；**绝不报 TOPS / TOPS-W / fJ/op**
   —— 那是吞吐×能效的联合指标，本段既无功耗模型、也无实测硅。

🔴 判据纪律（E15/E16 通则）：
  · **B18 用「肯定性禁止短语」**（`已报 TOPS` / `已流片` …）而**不是** `"TOPS" not in blob` ——
    披露里写的是「**不报** TOPS/TOPS-W/fJ/op」⇒ 用否定词窗口会把**正确的自我否定**误判成违规（E12/E13 血案同族）。
  · **探针只对被测机制敏感**：C6 **追加**「已报 TOPS」而不替换原文 ⇒ B17 仍绿、**只有 B18 红**。
"""

from __future__ import annotations

import math
import os
import sys
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import budget as B              # noqa: E402
from lda_l2.ecore import converter as CV          # noqa: E402
from lda_l2.ecore import parasitic as PA          # noqa: E402
from lda_l2.ecore import periphery as PR          # noqa: E402
from lda_l2.ecore import timing as T              # noqa: E402
from lda_l2.ecore import weight_prog as WP        # noqa: E402

_results: list = []
LN2 = math.log(2.0)

# ── 实测锚（本机默认几何 ‖ 默认工艺 · 8×8 / 8 bit）─────────────────────
AN_TAU_ROW_8 = 3.1186932940799992e-15     # E7 纯 Elmore
AN_TAU_COL_8 = 2.07912886272e-15
AN_SERIAL_NS = 129.565246                 # 每样本（串行）
AN_SAR_NS = 92.13526
AN_SH_NS = 6.238325
AN_DAC_NS = 31.19162
AN_RATE_MSA = 7.7181
AN_FIXED_NS = 37.43                       # 除 SAR 外的固定开销
AN_N_FOR_1NS = 4238                       # 阵列 τ 达 1 ns 的 N（二分）


def check(name: str, cond: bool, detail: str = "") -> bool:
    _results.append((name, bool(cond), detail))
    return bool(cond)


# ── 复用的绿色判据（突变探针也调同一份 —— 保证「打的判据」就是「守的判据」）──
def _rc_ok() -> bool:
    """B1 · G-1 一阶 RC 建立闭式 + 反解。"""
    tau, e = 3.7e-9, 1.0e-6
    t = T.rc_settle_time(tau, e)
    return (abs(t - tau * math.log(1.0 / e)) < 1e-24
            and abs(math.exp(-t / tau) - e) < 1e-18)


def _half_lsb_ok() -> bool:
    """B2 · G-2 = τ(k+1)ln2 且 == G-1 令 ε=2^{−(k+1)}（机精度）。

    🔴 容差 `1e-21`（**相对 ~1e-13**）：两条路径是**不同算法**
    （`(k+1)·ln2` ⟷ `ln(1/2^{−(k+1)})`）⇒ k 大时它们的 float64 舍入**不同**，
    用 `1e-24`（相对 ~1e-16）会逼近机器 eps 而**假红**。
    """
    for k in (0, 1, 4, 6, 8, 10, 12, 16):
        a = T.settle_half_lsb(1.0e-9, k)
        if abs(a - 1.0e-9 * (k + 1) * LN2) > 1e-21:
            return False
        if abs(a - T.rc_settle_time(1.0e-9, 2.0 ** (-(k + 1)))) > 1e-21:
            return False
    return True


def _e14_cross_ok() -> bool:
    """B3 · G-2 ⟷ E14 实测（跨模块 · E14 走 MNA 瞬态 ⇒ 方法学独立）。"""
    sh = CV.sample_hold_transient()
    mine = T.settle_half_lsb(sh["tau_s"], 8)
    ref = sh["t_to_half_lsb_8bit_s"]
    return abs(mine - ref) / ref < 1e-12


def _time_synth_ok() -> bool:
    """B4 · 🔴 时间合成律：serial == Σ · pipelined == max（**非恒等样本**）。"""
    st = [{"name": "a", "t_s": 3.0e-9}, {"name": "b", "t_s": 7.0e-9},
          {"name": "c", "t_s": 11.0e-9}]
    ss, pp = T.serial_sum(st), T.pipelined_period(st)
    return (len(st) >= 2 and abs(ss["t_s"] - 21.0e-9) < 1e-24
            and abs(pp["t_s"] - 11.0e-9) < 1e-24 and ss["t_s"] != pp["t_s"])


def _pipeline_ok() -> bool:
    """B5 · 🔴 流水线口径 + **「对时间取 RSS 会给出不同值」**（否则两套合成律只是口号）。

    朴素串行模型（无限带宽）下 5 阶段仍**串行**（同一次转换内先后发生）⇒
    流水线的收益来自**多行/多批次重叠**，但每批次内部不可再分。
    """
    st = [{"name": "a", "t_s": 3.0e-9}, {"name": "b", "t_s": 7.0e-9},
          {"name": "c", "t_s": 11.0e-9}]
    pp = T.pipelined_period(st)
    rss = math.sqrt(sum(s["t_s"] ** 2 for s in st))
    return (abs(pp["pipelined_latency_s"] - 21.0e-9) < 1e-24
            and abs(pp["pipeline_gain_frac"] - (21.0 - 11.0) / 21.0) < 1e-12
            and abs(rss - pp["pipelined_latency_s"]) > 1e-9)


def _elmore_scaling_ok() -> bool:
    """B6 · G-3 Elmore 规模律 τ ∝ N²（τ/N² 收敛 + 相邻比单调 → 4）。"""
    ns = (16, 32, 64, 128, 256)
    taus = [float(PA.array_parasitics(n, n)["tau_row_s"]) for n in ns]
    per_n2 = [t / float(n) ** 2 for t, n in zip(taus, ns)]
    ratios = [taus[i + 1] / taus[i] for i in range(len(taus) - 1)]
    return (all(ratios[i] > ratios[i + 1] - 1e-12 for i in range(len(ratios) - 1))
            and abs(ratios[-1] - 4.0) < 0.02
            and (max(per_n2) - min(per_n2)) / max(per_n2) < 0.15)


def _row_driver_ok() -> bool:
    """B7 · 🔴 **退化**：R_oc=0 ⇒ 纯 Elmore（逐位）· R_oc>0 ⇒ **严格更大**（丢项能被打出来）。"""
    p = PA.array_parasitics(8, 8)
    r0 = T.row_stage_time(8, 8, 8, r_oc=0.0)
    rd = T.row_stage_time(8, 8, 8)                     # 默认 R_oc
    return (r0["tau_drv_s"] == 0.0
            and r0["tau_s"] == p["tau_row_s"]
            and r0["t_s"] == T.settle_half_lsb(p["tau_row_s"], 8)
            and rd["tau_drv_s"] > 0.0
            and rd["tau_s"] > r0["tau_s"]
            and rd["t_s"] > r0["t_s"])


def _sar_ok() -> bool:
    """B8 · G-4 SAR = (n_bits+1)·t_clk 线性 + 与 E14 `len(trace)==n_bits` 一致。"""
    for nb in (4, 6, 8, 10, 12):
        if abs(T.sar_period(nb, 1.0e-9) - (nb + 1) * 1.0e-9) > 1e-24:
            return False
        if len(CV.sar_convert(0.37, n_bits=nb)["trace"]) != nb:
            return False
    st = T.sar_stage_time(8)
    return abs(st["t_s"] - T.sar_period(8, st["t_clk_s"])) < 1e-24 and st["n_clk"] == 9


def _g5_ok() -> bool:
    """B9 · G-5 C_tot = C_u·2^n ⟷ E14 `_cdac_c_unit` 之和 + τ_cdac = R_on·C_tot + t_clk 闭式。"""
    for nb in (4, 6, 8, 10, 12):
        if abs(T.cdac_total_cap(nb, 1.0e-12) - sum(CV._cdac_c_unit(nb, 1.0e-12))) > 1e-24:
            return False
    d = T.cdac_settle_tau(8)
    g5 = T.cdac_clock_from_settle(8)
    return (abs(d["c_total_f"] - 1.0e-12 * 256.0) < 1e-24
            and abs(d["tau_s"] - d["r_on_ohm"] * d["c_total_f"]) < 1e-24
            and abs(g5["t_clk_s"] - T.settle_half_lsb(d["tau_s"], 8)) < 1e-24
            and abs(d["r_on_ohm"] - CV.nmos_switch_ron_ohm(
                w_over_l=CV.CONV_PROCESS["dac_sw_wl"],
                v_gate=CV.CONV_PROCESS["sw_vgate_v"])) < 1e-15)


def _monotone_ok() -> bool:
    """B10 · 五阶段单调：bits ↑ ⇒ **每一阶段**时间 ↑（更严的 ½LSB）。"""
    lo = {s["name"]: s["t_s"] for s in T.stage_times(8, 8, 4)}
    hi = {s["name"]: s["t_s"] for s in T.stage_times(8, 8, 12)}
    return len(lo) == 5 and all(hi[k] > lo[k] for k in lo)


def _dominant_ok() -> bool:
    """B11 · 🔴 主导项 + share 合计 100% + **主导项随位数交叉**（低位数 DAC / 高位数 SAR）。"""
    rep = T.per_sample_report(8, 8, 8)
    tot = sum(s["share_pct"] for s in rep["stages"])
    if abs(tot - 100.0) > 1e-9:
        return False
    if rep["dominant"]["t_s"] != max(s["t_s"] for s in rep["stages"]):
        return False
    if not (rep["dominant_name"] == "sar_convert"):
        return False
    return (T.per_sample_report(8, 8, 4)["dominant_name"] == "dac_settle"
            and T.per_sample_report(8, 8, 6)["dominant_name"] == "dac_settle"
            and T.per_sample_report(8, 8, 10)["dominant_name"] == "sar_convert"
            and T.per_sample_report(8, 8, 12)["dominant_name"] == "sar_convert")


def _n_trend_ok() -> bool:
    """B12 · 🔴 **规模 × 时间趋势相反**：τ_row 跨 ≫10000×，而每样本耗时跨 <1.01×。"""
    tv = T.time_vs_n([8, 1024], 8)
    a, b = tv["points"][0], tv["points"][1]
    return (tv["tau_row_span_x"] > 10000.0
            and tv["serial_span_x"] < 1.01
            and b["serial_ns"] > a["serial_ns"]                # 仍单调升（只是极缓）
            and b["dominant"] == "sar_convert" == a["dominant"])


def _crossover_ok() -> bool:
    """B13 · 🔴 解析交叉点：阵列 τ 达 1 ns 的 N（解析 ⟷ 二分 · rel < 1%）。"""
    c = T.crossover_n_ps(1.0e-9)
    return (c["rel_diff_pct"] < 1.0
            and abs(c["n_bisect"] - AN_N_FOR_1NS) / float(AN_N_FOR_1NS) < 0.01
            and c["tau_at_n_s"] >= 1.0e-9)


def _clock_budget_ok() -> bool:
    """B14 · 🔴 时钟预算反解 + **代回验证** + 不可行时显式 False。"""
    cb = T.clock_budget(160.0e-9, 8, 8)
    ok = (cb["feasible"] and abs(cb["residual_s"]) < 1e-18
          and abs(cb["fixed_s"] + T.sar_period(8, cb["t_clk_max_s"])
                  - cb["target_period_s"]) < 1e-24)
    bad = T.clock_budget(1.0e-12, 8, 8)                        # 目标小于固定开销 ⇒ 不可行
    ok &= (not bad["feasible"]) and math.isnan(bad["t_clk_max_s"])
    return bool(ok)


def _protect_e7e14_ok() -> bool:
    """B15 · 🔴 保护性约束：E7 τ 逐位不变 · `PERIPHERY_PROCESS` 键集不变 · `CONV_PROCESS` 未改。"""
    p = PA.array_parasitics(8, 8)
    return (abs(float(p["tau_row_s"]) - AN_TAU_ROW_8) < 1e-27
            and abs(float(p["tau_col_s"]) - AN_TAU_COL_8) < 1e-27
            and set(PR.PERIPHERY_PROCESS.keys()) == {"a_gain", "r_out_open_ohm", "vfs_v", "vdd_v"}
            and CV.CONV_PROCESS["rs_ohm"] == 1.0e3
            and CV.CONV_PROCESS["cs_f"] == 1.0e-12
            and CV.CONV_PROCESS["t_step_s"] == 1.0e-9
            and CV.CONV_PROCESS["c_unit_f"] == 1.0e-12
            and CV.CONV_PROCESS["r_unit_ohm"] == 10.0e3)


def _protect_e15e16_ok() -> bool:
    """B16 · 🔴 保护性约束：E15 已发布数字（4.06012% / 4.6223）与 E16 地板（0.70014%）逐位不变。"""
    r = B.error_budget_report(8, 8)
    sig = WP.noise_floor_sigma(WP.WEIGHT_PROG_PROCESS["sigma_pulse_rel"],
                               WP.WEIGHT_PROG_PROCESS["alpha_pulse"])
    return (abs(r["worst_pct"] - 4.06012) < 1e-4
            and abs(r["worst_bits"] - 4.6223) < 1e-3
            and abs(sig * 100.0 - 0.70014) < 1e-4
            and B.max_scale_full_chain(5.0)["n_max"] == 12)


def _disclosure_ok() -> bool:
    """B17 · 🔴 诚实（肯定）：披露含「只报每样本耗时」「不报 TOPS」「宏模型」「非 PDK」。"""
    d = T.TIMING_DISCLOSURE
    blob = " ".join(str(v) for v in d.values())
    return ("只报「每样本耗时（ns）」" in blob
            and "不报 TOPS" in blob
            and "宏模型" in blob
            and "非 PDK" in blob)


_FALSE_CLAIMS = ("已报 TOPS", "已报能效", "已流片", "已含真实版图寄生",
                 "已含功耗", "已签核", "实测硅数据")


def _no_false_claim_ok() -> bool:
    """B18 · 🔴 诚实（否定）：**未声称** TOPS / 能效 / 已流片 / 已含真实版图寄生 / 已含功耗。

    🔴 用「**肯定性禁止短语**」而**不是** `"TOPS" not in blob` ——
    披露里写的是「**不报** TOPS/TOPS-W/fJ/op」（**正确的自我否定**），
    用否定词窗口会把它误判成违规（E12/E13 血案同族）。
    """
    blob = " ".join(str(v) for v in T.TIMING_DISCLOSURE.values())
    return all(k not in blob for k in _FALSE_CLAIMS)


def _report_shape_ok() -> bool:
    """B19 · 报告结构完整（5 阶段 + serial/pipelined/latency/dominant/rate 齐备）。"""
    rep = T.per_sample_report(8, 8, 8)
    need = ("stages", "serial_s", "serial_ns", "pipelined_period_s",
            "pipelined_latency_s", "pipeline_gain_frac", "max_sample_rate_hz",
            "dominant", "dominant_name", "dominant_share_pct")
    return (len(rep["stages"]) == 5
            and all(k in rep for k in need)
            and abs(rep["serial_s"] - rep["pipelined_latency_s"]) < 1e-24
            and rep["pipelined_period_s"] < rep["serial_s"]
            and abs(rep["max_sample_rate_hz"] - 1.0 / rep["serial_s"]) < 1.0)


def main() -> int:
    # ══════════════════════ A 模块自检 ══════════════════════
    ok_a = T.timing_self_check(verbose=False)
    check("A1 模块自检 12/12 PASS（G-1~G-5 闭式 / 跨模块 E14 交叉 / 时间合成律 / 流水线口径 / "
          "五阶段单调 / 主导项 / 保护性约束）", ok_a,
          "每样本(8×8/8bit)=%.4f ns ⇒ %.4f MSa/s"
          % (T.per_sample_report(8, 8, 8)["serial_ns"],
             T.per_sample_report(8, 8, 8)["max_sample_rate_hz"] / 1e6))

    # ══════════════════════ B 关键事实（name-first）══════════════════════
    check("B1 🔴 G-1 一阶 RC 建立闭式 t = τ·ln(1/ε)（闭式 ⟷ 反解 e^{−t/τ} == ε）",
          _rc_ok(), "τ=3.7 ns · ε=1e-6 ⇒ t=%.6e s" % T.rc_settle_time(3.7e-9, 1e-6))

    check("B2 🔴 G-2 建立到 k-bit ½LSB = τ·(k+1)·ln2（== G-1 令 ε=2^{−(k+1)} · 机精度）",
          _half_lsb_ok(), "k=8 ⇒ %.6e s" % T.settle_half_lsb(1e-9, 8))

    sh = CV.sample_hold_transient()
    check("B3 🔴 G-2 ⟷ **E14 实测** `t_to_half_lsb_8bit_s`（跨模块 · E14 走 MNA 瞬态 ⇒ 方法学独立）",
          _e14_cross_ok(), "闭式=%.6e ⟷ E14=%.6e" % (T.settle_half_lsb(sh["tau_s"], 8),
                                                     sh["t_to_half_lsb_8bit_s"]))

    ss_demo = T.serial_sum([{"name": "a", "t_s": 3e-9}, {"name": "b", "t_s": 7e-9},
                            {"name": "c", "t_s": 11e-9}])
    pp_demo = T.pipelined_period([{"name": "a", "t_s": 3e-9}, {"name": "b", "t_s": 7e-9},
                                  {"name": "c", "t_s": 11e-9}])
    check("B4 🔴🔴 **时间合成律按拓扑**：serial == Σ t_i · pipelined == max t_i"
          "（**与 E15 的误差分类合成律不同** · 非恒等样本）",
          _time_synth_ok(), "Σ=%.3e · max=%.3e s" % (ss_demo["t_s"], pp_demo["t_s"]))

    check("B5 🔴 流水线口径：首样本延迟 == Σ · 收益 = (Σ−max)/Σ · "
          "**「对时间取 RSS」会给出不同值**（否则两套合成律只是口号）",
          _pipeline_ok(), "收益=%.4f · RSS=%.3e ⟷ Σ=%.3e"
          % (pp_demo["pipeline_gain_frac"],
             math.sqrt(9e-18 + 49e-18 + 121e-18), ss_demo["t_s"]))

    check("B6 🔴 G-3 Elmore 规模律 τ ∝ N²（τ/N² 收敛 · 相邻比单调 → 4）",
          _elmore_scaling_ok(), "τ_row(8)=%.6e s" % AN_TAU_ROW_8)

    r0 = T.row_stage_time(8, 8, 8, r_oc=0.0)
    rd = T.row_stage_time(8, 8, 8)
    check("B7 🔴🔴 **退化**：R_oc=0 ⇒ 行线时间退化为**纯 Elmore**（逐位）；"
          "R_oc>0 ⇒ **严格更大**（⇒ 探针 C4「丢驱动项」打得出来）",
          _row_driver_ok(), "τ(0Ω)=%.6e ⟷ τ(默认 %.3fΩ)=%.6e s"
          % (r0["tau_s"], rd["r_oc_ohm"], rd["tau_s"]))

    check("B8 🔴 G-4 SAR 周期 = (n_bits+1)·t_clk（线性）· 与 E14 `len(sar_convert.trace)==n_bits` 一致",
          _sar_ok(), "8bit ⇒ %.6f ns（9 拍）" % (T.sar_stage_time(8)["t_s"] * 1e9))

    g5 = T.cdac_clock_from_settle(8)
    check("B9 🔴 G-5 C_tot = C_u·2^n（⟷ E14 `_cdac_c_unit` 之和 · 等价不复制）· "
          "τ_cdac = R_on·C_tot · t_clk = settle_half_lsb(τ_cdac, k)",
          _g5_ok(), "C_tot=%.4e F · τ_cdac=%.4e s · t_clk=%.6f ns"
          % (g5["c_total_f"], g5["tau_cdac_s"], g5["t_clk_s"] * 1e9))

    check("B10 五阶段单调：bits 4 → 12 ⇒ **每一阶段**时间都上升（更严的 ½LSB）",
          _monotone_ok(), "SAR 4bit=%.3e → 12bit=%.3e s"
          % (T.stage_times(8, 8, 4)[3]["t_s"], T.stage_times(8, 8, 12)[3]["t_s"]))

    check("B11 🔴 主导项识别 + share 合计 100% + **主导项随位数交叉**"
          "（4/6 bit ⇒ DAC 建立 · 8/10/12 bit ⇒ SAR 转换）",
          _dominant_ok(), "8bit：主导=%s(%.2f%%)"
          % (T.per_sample_report(8, 8, 8)["dominant_name"],
             T.per_sample_report(8, 8, 8)["dominant_share_pct"]))

    tv = T.time_vs_n([8, 1024], 8)
    check("B12 🔴🔴 **规模 × 时间趋势相反**：N 8→1024 ⇒ 阵列 τ_row 跨 ≫10000×（∝N²），"
          "而每样本耗时只跨 <1.01× ⇒ **规模墙是精度墙不是速度墙**",
          _n_trend_ok(), "τ_row 跨 %.1f× ⟷ 每样本跨 %.5f×"
          % (tv["tau_row_span_x"], tv["serial_span_x"]))

    cx = T.crossover_n_ps(1.0e-9)
    check("B13 🔴 解析交叉点：阵列 τ 达 1 ns 的 N（解析 ⟷ 二分 · rel < 1%）· "
          "**该 N 远超 E15 的可及规模（N≤12）** ⇒ 可达规模内阵列 RC 永不是时间瓶颈",
          _crossover_ok(), "N_analytic=%.1f ⟷ N_bisect=%d（rel %.3f%%）· E15 5%% 上界 N≤12"
          % (cx["n_analytic"], cx["n_bisect"], cx["rel_diff_pct"]))

    cb = T.clock_budget(160.0e-9, 8, 8)
    check("B14 🔴 时钟预算反解 + **代回验证**（`fixed + (bits+1)·t_clk_max == target`）· "
          "目标小于固定开销时显式 `feasible=False`",
          _clock_budget_ok(), "固定=%.3f ns · t_clk_max(160ns)=%.4f ns · 代回残差=%.2e"
          % (cb["fixed_s"] * 1e9, cb["t_clk_max_s"] * 1e9, cb["residual_s"]))

    check("B15 🔴 **保护性约束**：E7 τ 逐位不变 · `PERIPHERY_PROCESS` **键集不变**"
          "（E17 不向其加时间键）· E14 `CONV_PROCESS` 值未改",
          _protect_e7e14_ok(), "τ_row(8×8)=%.6e" % AN_TAU_ROW_8)

    b16 = B.error_budget_report(8, 8)
    check("B16 🔴 **保护性约束**：E15 已发布数字（8×8 worst 4.06012% / 4.6223 位 / 5% 上界 N≤12）"
          "与 E16 写入噪声地板（0.70014%）**逐位不变**",
          _protect_e15e16_ok(), "worst=%.5f%% · bits=%.4f · 上界=%d"
          % (b16["worst_pct"], b16["worst_bits"], B.max_scale_full_chain(5.0)["n_max"]))

    check("B17 🔴 诚实（肯定）：披露含「只报每样本耗时（ns）」+「不报 TOPS」+"
          "「宏模型」+「非 PDK」",
          _disclosure_ok(), "披露 %d 键全含要求项" % len(T.TIMING_DISCLOSURE))

    check("B18 🔴 诚实（否定）：**未声称** TOPS / 能效 / 已流片 / 已含真实版图寄生 / 已含功耗 "
          "（🔴 用**肯定性禁止短语**，不用 `\"TOPS\" not in blob` —— 否则会误伤"
          "「**不报** TOPS」这句正确的自我否定）",
          _no_false_claim_ok(), "禁止短语 %d 条无一命中" % len(_FALSE_CLAIMS))

    check("B19 报告结构完整（5 阶段 + serial/pipelined/latency/dominant/rate 齐备 · "
          "pipelined_period < serial · rate == 1/serial）",
          _report_shape_ok())

    # ══════════════════════ C 反向可证伪（6 条突变探针）══════════════════════
    # C1 时间合成律改成 RSS（照搬 E15 的误差律）⇒ B4 必红
    def _rss_combine(stages, topology="serial"):
        ss = T.normalize_stages(stages)
        rss = math.sqrt(sum(s["t_s"] ** 2 for s in ss))
        return {"topology": topology, "t_s": rss, "serial_s": rss,
                "pipelined_period_s": rss, "pipelined_latency_s": rss,
                "pipeline_gain_frac": 0.0, "n_stages": len(ss),
                "slowest_stage": None, "stages": ss, "is_oracle": False}

    with mock.patch.object(T, "combine_time", _rss_combine):
        c1 = not _time_synth_ok()
    check("C1 反向：时间合成律改成 **RSS**（√Σt²，照搬 E15 的误差律）⇒ B4 必红"
          "（串行阶段的时间必然叠加，不满足「独立随机量」前提）", c1,
          "合成律判据实测变红 = %s" % c1)

    # C2 ½LSB 闭式漏 +1 ⇒ B1/B2/B3 必红
    with mock.patch.object(T, "settle_half_lsb",
                           lambda tau, bits: float(tau) * float(int(bits)) * LN2):
        c2 = not (_half_lsb_ok() and _e14_cross_ok())
    check("C2 反向：½LSB 闭式写成 τ·k·ln2（**漏 +1**，即把「k 位精度」当成「k−1 个 ln2」）"
          "⇒ B2/B3 必红", c2, "½LSB 判据实测变红 = %s" % c2)

    # C3 SAR 漏采样那一拍 ⇒ B8 必红
    with mock.patch.object(T, "sar_period",
                           lambda n_bits, t_clk_s: float(int(n_bits)) * float(t_clk_s)):
        c3 = not _sar_ok()
    check("C3 反向：SAR 周期写成 n_bits·t_clk（**漏掉采样那一拍**）⇒ B8 必红", c3,
          "SAR 判据实测变红 = %s" % c3)

    # C4 行线丢驱动源阻抗项（只留 Elmore）⇒ B7 必红
    def _no_drv(n, m=None, bits=None, r_oc=None, cell_params=None, proc=None):
        p = PA.array_parasitics(int(n), int(n) if m is None else int(m), cell_params, proc)
        b = int(T.TIMING_PROCESS["bits"] if bits is None else bits)
        return {"name": "row_line", "t_s": T.settle_half_lsb(p["tau_row_s"], b),
                "tau_s": p["tau_row_s"], "tau_dist_s": p["tau_row_s"], "tau_drv_s": 0.0,
                "r_oc_ohm": 0.0, "bits": b, "n": int(n), "m": int(n),
                "source": "MUTATED", "is_oracle": False}

    with mock.patch.object(T, "row_stage_time", _no_drv):
        c4 = not _row_driver_ok()
    check("C4 反向：行线时间**丢掉驱动源阻抗项** `R_oc·C_row_tot`（只留 Elmore）⇒ B7 必红"
          "（🔴 退化判据要求 R_oc>0 时**必须严格更大**，否则丢项判不出来）", c4,
          "行线退化判据实测变红 = %s" % c4)

    # C5 CDAC 漏 dummy 电容（C_tot = C_u·(2^n − 1)）⇒ B9 必红
    with mock.patch.object(T, "cdac_total_cap",
                           lambda bits, c_unit=None: float(
                               CV.CONV_PROCESS["c_unit_f"] if c_unit is None else c_unit)
                           * float((1 << int(bits)) - 1)):
        c5 = not _g5_ok()
    check("C5 反向：CDAC 总电容写成 `C_u·(2^n − 1)`（**漏掉 dummy C_u**）⇒ B9 必红"
          "（与 E14 `_cdac_c_unit` 之和不符 ⇒ 等价性被破坏）", c5,
          "G-5 判据实测变红 = %s" % c5)

    # C6 披露**追加**「已报 TOPS」（而非替换）⇒ **只有 B18 红**，B17 仍绿（探针特异性）
    _bad_disc = dict(T.TIMING_DISCLOSURE)
    _bad_disc["metric"] = _bad_disc["metric"] + " 已报 TOPS：7.7 TOPS"
    with mock.patch.object(T, "TIMING_DISCLOSURE", _bad_disc):
        c6_false = not _no_false_claim_ok()
        c6_still_true = _disclosure_ok()               # B17 应**仍为真**（追加而非替换）
    check("C6 反向：披露**追加**「已报 TOPS」（而非替换原文）⇒ B18 必红 · "
          "**且 B17 仍绿**（🔴 探针只对被测机制敏感 · 否定词窗口会误伤正确的自我否定）",
          c6_false and c6_still_true,
          "B18 变红 = %s · B17 仍绿 = %s" % (c6_false, c6_still_true))

    # 还原重跑（无残留漂移）
    check("C7 还原完整性：全部探针退出后，A1 自检 + B4/B7/B9/B12/B18 复跑仍全绿",
          T.timing_self_check(verbose=False) and _time_synth_ok() and _row_driver_ok()
          and _g5_ok() and _n_trend_ok() and _no_false_claim_ok())

    # ── K 自入 CI core ────────────────────────────────────────────────
    ci = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_ecore_e17_smoke.py" in ck)

    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    print()
    for name, ok, detail in _results:
        if not ok:
            print("FAIL | " + name + (("  :: " + detail) if detail else ""))
        elif detail:
            print("PASS | " + name + "  :: " + detail)
    print()
    print("=" * 74)
    print("E17 门禁结果：%d PASS / %d FAIL（共 %d 判据 · 含 6 突变探针）"
          % (npass, nfail, len(_results)))
    print("=" * 74)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
