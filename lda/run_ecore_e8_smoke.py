"""电子计算芯片非理想/失配/噪声 门禁 smoke（E8 · D-158）。

═══ 为什么要有这个 smoke ═══
E8 给 E1–E7 的**确定性标称器件**补上真实硅片的三类非理想：**器件失配**（Pelgrom）、
**温度**（Vth/迁移率漂移、片内热梯度）、**噪声**（热 4kTγg_m + 闪烁）。它们决定了
**要不要校准、校准到哪一层** —— 随机项按 1/√N 平均掉，系统项不会。这类统计/物理律
最易被悄悄抹平（把 σ 归零、把温度系数改成 0、把校准说成"万能"）⇒ 必须钉成常驻断言 + **突变探针**。

  ① **模块自检 10/10** + **E7 回归**（E8 不破坏寄生链）
  ② **Pelgrom 闭式** σ_ΔVth = A_VT/√(W·L)（面积 ×4 ⇒ σ 减半）· MC 实测 ≡ 闭式
  ③ **温度** Vth 线性（k_T·ΔT）· 迁移率 ∝ (T/T0)^m（升温降）
  ④ **噪声闭式** 热 i_n²=4kTγg_m（∝T · ∝g_m）· 输入折合 4kTγ/g_m · 闪烁 ∝1/f 与 1/(W·L)
  ⑤ **失配 Monte Carlo** 输出误差分布；**σ_rel ∝ 1/√N**（求和平均律）· 无偏 · MC 收敛
  ⑥ **校准层级** 残差单调降 L0 ≥ L1 ≥ L2；L1 消**列系统项**；L2 受**测量噪声**限制（∝σ_est）
  ⑦ **吃狗粮**：与 E1/E2 的 NmosParams 口径一致、几何与 E6 版图一致
  ⑧ **诚实边界 + 红线**（参数非 PDK · L2 为理想化模型 · 无空间相关 · 零商业 EDA · 无 TOPS 自夸）
  ⑨ **突变探针**（篡 Pelgrom / 关失配 / 温度系数归零 / 消掉列系统项）各必红 + 还原复绿

运行：python run_ecore_e8_smoke.py（cwd=lda/）
出口：全 PASS 退 0；任一 FAIL 退 1。**LLM 不进判决路径**。
"""
from __future__ import annotations

import os
import re
import sys
import unittest.mock as mock

_HERE = os.path.dirname(os.path.abspath(__file__))       # = …/lda
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import numpy as np                                        # noqa: E402

from lda_l2.ecore import layout as LY                     # noqa: E402
from lda_l2.ecore import mismatch as MM                   # noqa: E402
from lda_l2.ecore import parasitic as PA                  # noqa: E402
from lda_l2.ecore.mosfet import NmosParams                # noqa: E402
from lda_harness.smoke_kit import make_check              # noqa: E402

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=" | {d}", return_ok=True)

W_UM, L_UM = 1.20, 0.30          # E6 版图回提几何（W/L = 4.00）


# ═══════════════ 绿色判据复用小函数（突变探针复用同一份）═══════════════
def _pelgrom_ok() -> bool:
    s1 = MM.pelgrom_sigma_vth_mv(W_UM, L_UM)
    s4 = MM.pelgrom_sigma_vth_mv(2 * W_UM, 2 * L_UM)
    return abs(s4 - s1 / 2.0) < 1e-12


def _sqrt_law_ok() -> bool:
    law = MM.sigma_vs_n([4, 16, 64], trials=500, seed=3)
    vals = [p["sigma_rel"] for p in law["points"]]
    if any(v <= 0.0 for v in vals):
        return False
    return law["sqrt_law_ok"]


def _vth_temp_linear() -> bool:
    return abs((MM.vth_at(85.0) - MM.vth_at(25.0)) - (-0.060)) < 1e-9


def _l1_removes_systematic() -> bool:
    """**特异性判据**：有列系统项时 L0 显著抬升，而 **L1 对系统项不变**。

    🔴 不要用「L1 < 0.8·L0」——实测证明该式在**纯随机**下也成立（列标量校准会顺带
    消掉列共模），因此**不特异**：它不能证明 L1 消的是系统项。正解 = 对比
    「有/无系统项」两次实验，看 **L0 抬升、L1 不变**。
    """
    a = MM.calibration_report(8, 8, vg=1.0, trials=500, seed=5,
                              thermal_grad_c_per_col=2.0)
    b = MM.calibration_report(8, 8, vg=1.0, trials=500, seed=5,
                              thermal_grad_c_per_col=0.0)
    l0_inflated = a["sigma_rel_L0"] > 1.5 * b["sigma_rel_L0"]
    l1_invariant = abs(a["sigma_rel_L1"] - b["sigma_rel_L1"]) < 0.35 * b["sigma_rel_L1"]
    return bool(l0_inflated and l1_invariant)


# ═══════════════ 突变探针（每个都先证「真能变红」）═══════════════
def probe_pelgrom_corrupt() -> bool:
    """把 Pelgrom 闭式改成常数 ⇒ 1/√(WL) 判据必红。"""
    with mock.patch.object(MM, "pelgrom_sigma_vth_mv", lambda w, l, p=None: 3.0):
        return not _pelgrom_ok()


def probe_mismatch_off() -> bool:
    """关掉失配（σ ≡ 0）⇒ 1/√N 统计律判据必红（σ 不再严格降且不为正）。"""
    def zeros(n, m, w, l, trials=1, seed=0, process=None):
        return {"dvth_v": np.zeros((trials, n, m)), "dbeta_rel": np.zeros((trials, n, m)),
                "sigma_vth_v": 0.0, "sigma_beta_rel": 0.0}
    with mock.patch.object(MM, "sample_mismatch", zeros):
        return not _sqrt_law_ok()


def probe_temp_coeff_zero() -> bool:
    """把 Vth 温度系数归零 ⇒ 温度线性判据必红。"""
    pr = dict(MM.MISMATCH_PROCESS)
    pr["vth_tc_mv_per_k"] = 0.0
    with mock.patch.object(MM, "MISMATCH_PROCESS", pr):
        return not _vth_temp_linear()


def probe_col_systematic_removed() -> bool:
    """消掉列系统项（温度与列无关）⇒ 「L0 被系统项抬升」判据必红。"""
    with mock.patch.object(MM, "conductance_at_temperature",
                           lambda vg, w, l, t, params=None, process=None: 1.0):
        return not _l1_removes_systematic()


def main() -> int:
    print("=" * 78)
    print("电子计算芯片非理想/失配/噪声 门禁 smoke（E8 · D-158）")
    print("=" * 78)

    # ════════════════ A 节：模块自检 + E7 回归 ════════════════
    print("── A 模块自检 ──")
    check("A1 mismatch 自检 10/10（Pelgrom/温度/噪声/√N 律/校准层级）",
          MM.run_selfchecks(verbose=False), "σ√N 常值 · L0≥L1≥L2")
    check("A2 E7 寄生链回归（E8 未破坏 parasitic 自检 10/10）",
          PA.run_selfchecks(verbose=False), "E7 10 判据仍绿")

    # ════════════════ B 节：Pelgrom 失配 ════════════════
    print("── B Pelgrom 失配 ──")
    s1 = MM.pelgrom_sigma_vth_mv(W_UM, L_UM)
    check("B1 Pelgrom σ_ΔVth = A_VT/√(W·L)（面积 ×4 ⇒ σ 减半）", _pelgrom_ok(),
          f"σ={s1:.4f} mV（W·L={W_UM*L_UM:.2f} µm²）")
    smp = MM.sample_mismatch(4000, 1, W_UM, L_UM, trials=1, seed=1)
    emp = float(np.std(smp["dvth_v"])) * 1000.0
    check("B2 MC 实测 σ_ΔVth ≡ Pelgrom 闭式（±8%）",
          abs(emp - s1) / s1 < 0.08, f"实测 {emp:.4f} vs 闭式 {s1:.4f} mV")
    sb = MM.pelgrom_sigma_beta_rel(W_UM, L_UM)
    sb2 = MM.pelgrom_sigma_beta_rel(4 * W_UM, L_UM)
    check("B3 Pelgrom β 匹配 σ_Δβ/β = A_β/√(W·L)（W ×4 ⇒ σ 减半）",
          abs(sb2 - sb / 2.0) < 1e-12, f"σ_β={sb:.5f}")
    check("B4 失配几何与 E6 版图口径一致（W/L = 4.00）",
          abs((W_UM / L_UM) - (LY.extract_wl(LY.crossbar_array(4, 4)["descs"])["W_um"]
                               / LY.extract_wl(LY.crossbar_array(4, 4)["descs"])["L_um"])) < 1e-9,
          "1.20/0.30")

    # ════════════════ C 节：温度 ════════════════
    print("── C 温度模型 ──")
    check("C1 Vth(T) 一阶线性（k_T·ΔT = −60 mV @ 25→85 °C）", _vth_temp_linear(),
          f"{MM.vth_at(25.0):.4f} → {MM.vth_at(85.0):.4f} V")
    check("C2 迁移率 µ(T) ∝ (T/T0)^m：升温降（µ_r(85°C) < 1）",
          MM.mobility_ratio(85.0) < 1.0 and abs(MM.mobility_ratio(25.0) - 1.0) < 1e-12,
          f"µ_r(85)={MM.mobility_ratio(85.0):.4f}")
    g25 = MM.conductance_at_temperature(1.0, W_UM, L_UM, 25.0)
    g85 = MM.conductance_at_temperature(1.0, W_UM, L_UM, 85.0)
    check("C3 温度下电导漂移（Vth 降 vs 迁移率降的净效应）", g85 != g25 and g85 > 0,
          f"g(25)={g25:.5e} → g(85)={g85:.5e} S")

    # ════════════════ D 节：噪声闭式 ════════════════
    print("── D 噪声闭式 ──")
    gm = 1.0e-3
    i25, i85 = MM.thermal_noise_psd(gm, 25.0), MM.thermal_noise_psd(gm, 85.0)
    check("D1 热噪声 i_n² = 4kTγg_m（∝T 线性 · ∝g_m 线性）",
          abs(i85 / i25 - (85 + 273.15) / (25 + 273.15)) < 1e-9
          and abs(MM.thermal_noise_psd(2 * gm, 25.0) / i25 - 2.0) < 1e-9,
          f"i_n²={i25:.4e} A²/Hz")
    check("D2 输入折合 v_n² = i_n²/g_m² = 4kTγ/g_m",
          abs(MM.input_referred_noise_psd(i25, gm)
              - 4 * MM.KB * (25 + 273.15) * (2 / 3) / gm) < 1e-30,
          f"v_n²={MM.input_referred_noise_psd(i25, gm):.4e} V²/Hz")
    sf = MM.flicker_input_noise_psd(W_UM, L_UM, 1e3)
    check("D3 闪烁噪声 ∝ 1/f 且 ∝ 1/(W·L)",
          abs(MM.flicker_input_noise_psd(W_UM, L_UM, 2e3) - sf / 2.0) < 1e-40
          and abs(MM.flicker_input_noise_psd(2 * W_UM, 2 * L_UM, 1e3) - sf / 4.0) < 1e-40,
          f"S_vg(1kHz)={sf:.4e} V²/Hz")
    check("D4 闪烁输出谱密度 ∝ g_m²",
          abs(MM.flicker_output_noise_psd(2 * gm, W_UM, L_UM, 1e3)
              / MM.flicker_output_noise_psd(gm, W_UM, L_UM, 1e3) - 4.0) < 1e-9, "g_m²")

    # ════════════════ E 节：失配 Monte Carlo + 统计律 ════════════════
    print("── E 失配 Monte Carlo ──")
    r8 = MM.mc_output_error(8, 8, 1.0, trials=800, seed=5)
    check("E1 输出误差分布可用（σ>0 · P95 > σ）",
          r8["sigma_rel"] > 0 and r8["p95_rel"] > r8["sigma_rel"],
          f"σ={r8['sigma_rel']:.5f} · P95={r8['p95_rel']:.5f}")
    check("E2 失配**无偏**（|均值| ≪ σ）",
          abs(r8["mean_rel"]) < 0.1 * r8["sigma_rel"], f"mean={r8['mean_rel']:.2e}")
    law = MM.sigma_vs_n([4, 16, 64], trials=500, seed=3)
    check("E3 随机失配输出相对误差 **∝ 1/√N**（求和平均律）",
          _sqrt_law_ok(), f"σ·√N={[round(v, 6) for v in law['sigma_x_sqrtN']] if 'sigma_x_sqrtN' in law else [round(p['sigma_rel']*p['n']**0.5, 6) for p in law['points']]}")
    check("E4 绝对值 |σ_out| 随 N **增大**（∝√N：相对降、绝对升）",
          MM.mc_output_error(4, 4, 1.0, trials=800, seed=5)["abs_sigma"]
          < MM.mc_output_error(16, 16, 1.0, trials=800, seed=5)["abs_sigma"],
          "相对 σ 降、绝对 σ 升")

    # ════════════════ F 节：校准层级 ════════════════
    print("── F 校准层级 ──")
    cr = MM.calibration_report(8, 8, vg=1.0, trials=800, seed=5)
    cr_ns = MM.calibration_report(8, 8, vg=1.0, trials=800, seed=5,
                                  thermal_grad_c_per_col=0.0)
    check("F1 校准残差单调降 L0 ≥ L1 ≥ L2",
          cr["sigma_rel_L0"] >= cr["sigma_rel_L1"] >= cr["sigma_rel_L2"],
          f"{cr['sigma_rel_L0']:.5f} ≥ {cr['sigma_rel_L1']:.5f} ≥ {cr['sigma_rel_L2']:.5f}")
    check("F2 L1（列增益校准）**特异性**消列系统项：L0 被系统项抬升、L1 对其**不变**",
          _l1_removes_systematic(),
          f"列增益散布 {cr['col_gain_spread']:.4f} · L0 {cr_ns['sigma_rel_L0']:.5f}→{cr['sigma_rel_L0']:.5f}"
          f" · L1 {cr_ns['sigma_rel_L1']:.5f}→{cr['sigma_rel_L1']:.5f}")
    cr_lo = MM.calibration_report(8, 8, vg=1.0, trials=800, seed=5, sigma_est_rel=0.001)
    cr_hi = MM.calibration_report(8, 8, vg=1.0, trials=800, seed=5, sigma_est_rel=0.004)
    ratio = cr_hi["sigma_rel_L2"] / cr_lo["sigma_rel_L2"]
    check("F3 L2 残差 ∝ 测量噪声 σ_est（线性）", 3.0 < ratio < 5.0, f"σ_est ×4 ⇒ 残差 ×{ratio:.2f}")
    check("F4 L2 残差 ≈ σ_est/√N（逐单元校准受测量精度限制）",
          0.5 < cr["sigma_rel_L2"] / (cr["sigma_est_rel"] / 8 ** 0.5) < 2.0,
          f"L2={cr['sigma_rel_L2']:.5f} vs σ_est/√N={cr['sigma_est_rel']/8**0.5:.5f}")

    # ════════════════ G 节：吃狗粮跨模块 ════════════════
    print("── G 吃狗粮跨模块（E1/E2 模型 · E6 版图）──")
    p = NmosParams(w_over_l=W_UM / L_UM)
    g_nom = MM.nominal_conductances(1.0, W_UM, L_UM, p)
    check("G1 标称电导与 E1/E2 同口径 g = kp·(W/L)·(Vg − Vth0)",
          abs(float(g_nom) - p.kp * p.w_over_l * (1.0 - p.vth0)) < 1e-18,
          f"g={float(g_nom):.5e} S")
    check("G2 失配不改变标称值（E[g]=g_nom，零均值扰动）",
          abs(float(np.mean(MM.mismatched_conductances(
              np.full((1, 400, 1), 1.0), MM.sample_mismatch(400, 1, W_UM, L_UM, 1, 7)["dvth_v"],
              MM.sample_mismatch(400, 1, W_UM, L_UM, 1, 7)["dbeta_rel"], p))) - float(g_nom))
          / float(g_nom) < 0.02, "E[g] ≈ g_nom")

    # ════════════════ H 节：诚实边界 + 红线 ════════════════
    print("── H 诚实边界 + 红线 ──")
    disc = MM.MISMATCH_DISCLOSURE
    check("H1 披露齐备：role/process/calibration/noise/correlation/red_line 六键",
          all(k in disc for k in ("role", "process", "calibration", "noise",
                                  "correlation", "red_line")), f"键={sorted(disc)}")
    check("H2 失配参数为公开典型量级 · 非 PDK（明确 D5 外部依赖）",
          "非 Foundry PDK" in disc["process"] and "公开典型量级" in disc["process"], "口径")
    check("H3 L2「逐单元校准」明确标注为**理想化模型**（非真实写-验流程）",
          "理想化模型" in disc["calibration"], "校准口径")
    check("H4 明确标注**不建模空间相关性**（独立同分布假定）",
          "空间相关" in disc["correlation"], "相关性口径")
    banned = ("ngspice", "pyspice", "ahkab", "ltspice", "xyce", "cadence",
              "synopsys", "gdstk", "gdspy", "gdsfactory", "qiskit", "cirq")
    src = open(os.path.join(_HERE, "lda_l2", "ecore", "mismatch.py"), encoding="utf-8").read()
    hits = [b for b in banned if re.search(rf"^\s*(import|from)\s+{b}\b", src, re.M)]
    check("H5 红线：零商业 EDA / 零量子 SDK 依赖（纯 numpy）", not hits, f"命中={hits or '无'}")
    check("H6 判决无 LLM：结果为 float 死标量（零模型调用）",
          all(isinstance(r8[k], float) for k in ("sigma_rel", "mean_rel", "p95_rel")),
          "纯数值")
    blob = str(disc).upper()
    check("H7 诚实边界：无 TOPS / TOPS-W / fJ-op 类器件性能自夸",
          "TOPS" not in blob and "FJ/OP" not in blob, "设计&验证工具链口径")

    # ════════════════ I 节：突变探针 ════════════════
    print("── I 突变探针（每个都必须真能变红）──")
    check("I1 探针：篡改 Pelgrom 闭式 ⇒ 1/√(WL) 判据必红",
          probe_pelgrom_corrupt() is True, "证读闭式")
    check("I2 探针：关掉失配（σ≡0）⇒ 1/√N 统计律判据必红",
          probe_mismatch_off() is True, "证 σ 真的来自抽样")
    check("I3 探针：Vth 温度系数归零 ⇒ 温度线性判据必红",
          probe_temp_coeff_zero() is True, "证温度真的读系数")
    check("I4 探针：消掉列系统项 ⇒ 「L0 被系统项抬升」判据必红",
          probe_col_systematic_removed() is True, "证 L1 真的在消系统项")

    # ════════════════ J 节：还原完整性 ════════════════
    print("── J 还原完整性 ──")
    check("J1 还原后：Pelgrom/√N/温度/校准四项复绿",
          _pelgrom_ok() and _sqrt_law_ok() and _vth_temp_linear() and _l1_removes_systematic(),
          "无 patch 残留")
    check("J2 还原后：模块自检 10/10 复绿", MM.run_selfchecks(verbose=False), "无残留")

    print()
    print(f"电子计算芯片非理想/失配/噪声 门禁 smoke（E8）：{PASS}/{PASS + FAIL} PASS")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
