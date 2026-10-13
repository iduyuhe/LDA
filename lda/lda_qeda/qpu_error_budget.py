"""J2 M4 · QPU 级误差预算集成 + 阈值余量（吃狗粮）。

承 J2 蓝图 M4「QPU 级误差预算集成」：把**逐分量错误率**集成为**每周期总错误率**，
并与表面码阈值 p_th 比出**余量**（ACCEPT / REJECT），供 J1↔J2 复利闭环回喂。

分量（全闭式 + 复用既有能力层，零量子 SDK）：
  · **1q 门**：退相干极限（`physical_error_model.gate_error_decoherence`，与 B10 同律）。
  · **2q CR 门**：张量 A+D 信道过程保真度组合 `ε=1−(4·F_pro^A·F_pro^B+1)/5`，
    `F_proⁱ=(1+e^{−t/T1ⁱ}+2e^{−t/T2ⁱ})/4` —— **与账本锚 B506 同一物理律**
    （本层是设计预算实现；`run_j2_qpu_smoke` 常驻断言二者逐值一致，防副本漂移）。
    门时间 t_2q 由 CR 有效模型 `g_CR=2J²Δ/(α²−Δ²)` ⇒ `t_CR=π/|g_CR|` 现算
    （复用 `cross_resonance`，纯算术、无求解器）。
  · **读出**：色散读出误判 `ε=½·erfc(SNR/√2)`（复用 `lda_agent.readout_fidelity`，
    与 B30 同律）。
  · **idle**：同一退相干律，时长 = 同步提取周期内的闲置时长。
  · **残余 ZZ**：`ε_zz=(4/5)·sin²(ζt/2)`（**与账本锚 B507 同一物理律**），
    ζ 取 S 分支 `crosstalk_budget` 的**最近邻**静态 ZZ；`ζ ≤ ζ_lim=1.0 MHz` 为 S 铁律②。

集成口径（**诚实并列两种**，不选择性披露）：
  · 一阶独立求和：`p_cyc = Σ_k n_k·ε_k`（小量极限）
  · 级联保真度：`F_cyc = Π_k (1−ε_k)^{n_k}` ⇒ `p_cyc^F = 1 − F_cyc`
  二者在小量下一致，本层同时给出并报最大差，不做「只报好看的那个」。

诚实边界：T1/T2/J/Δ/α/t/p_th/n_* 均为**设计示例量级**（非实测 PDK/非流片）；本层只做
**设计预算**（不含量子线路仿真、不含脉冲级控制、不含蒙特卡洛），结论只可用于设计与量级，
**不得作制造/性能宣称**。d 阶冗余（`2d²−1`）与拓扑对接见 `topology_qec_bridge`。
红线：纯 numpy/标准库 · 零量子 SDK · LLM 不进判决路径 · 阈值为设计规则。
"""
from __future__ import annotations

import math
from typing import Dict, Optional

from lda_agent.readout_fidelity import readout_fidelity
from lda_qeda import j2_to_j1_calibration as CAL
from lda_qeda import physical_error_model as PEM
from lda_qeda import sc_readout as S4
from lda_qeda.cross_resonance import cross_resonance

# ── 设计示例档（可覆盖 · 非实测 golden）────────────────────────────────────
DEFAULT_QPU_BUDGET = {
    # 退相干
    "T1_s": 80e-6, "T2_s": 60e-6,
    # 门 / idle 时长（同步提取周期内）
    "t_1q_s": 20e-9,          # 单比特门
    "t_idle_s": 300e-9,       # 每比特在周期内闲置时长
    "J_mhz": 20.0,            # CR 有效模型：交换耦合
    "delta_mhz": -200.0,      # Δ = ω_t − ω_c（须 |Δ|<|α|）
    "alpha_mhz": -250.0,      # α 非谐性（负）
    # 读出（与 B30 工作点同口径）
    "chi_ghz": 0.05, "kappa_r_ghz": 0.005, "nbar": 2.0,
    "eta": 0.5, "N_amp": 5.0, "t_ro_s": 4.236705e-9,
    # 每周期各操作次数（同步提取周期示意）
    "n_1q": 2, "n_2q": 4, "n_ro": 1, "n_idle": 2,
    # 阈值（公认量级 · rotated surface code 典型）
    "p_th": 0.01,
}

#: 读出时间优化后的**乐观设计档**（用于展示预算余量的响应方向，非宣称）
PRESET_OPTIMIZED = dict(DEFAULT_QPU_BUDGET, t_ro_s=2.0e-6, T1_s=120e-6, T2_s=90e-6)


def _p_get(p: Dict, k: str) -> float:
    return float(DEFAULT_QPU_BUDGET[k] if p.get(k) is None else p[k])


def cr_gate_time_us(J_mhz: float, delta_mhz: float, alpha_mhz: float) -> Dict:
    """CR 有效模型 ⇒ g_CR 与门时间 t_CR（复用 `cross_resonance`；纯算术）。

    g_CR = 2J²Δ/(α²−Δ²)（MHz）⇒ t_CR = π/|g_CR|（µs）。参数区无效（|Δ|≥|α|）⇒ 抛错。
    """
    cr = cross_resonance(float(J_mhz), float(delta_mhz), float(alpha_mhz))
    if not cr.get("ok") and cr.get("t_CR_us") is None:
        raise ValueError("CR 有效模型参数区无效：%s" % cr.get("error"))
    return {
        "g_CR_mhz": float(cr["g_CR_MHz"]),
        "abs_g_CR_mhz": float(cr["abs_g_CR_MHz"]),
        "t_CR_us": float(cr["t_CR_us"]),
        "sigma_zz_mhz": float(cr.get("sigma_zz_MHz", 0.0)),
        "valid_regime": bool(cr.get("valid_regime", False)),
    }


def cr_gate_error_2q(t_us: float, T1_a_s: float, T2_a_s: float,
                     T1_b_s: float, T2_b_s: float) -> float:
    """2q CR 门退相干错误率闭式（**与账本锚 B506 同一物理律**）。

    单比特 A+D 信道过程保真度 F_pro(T1,T2,t)=(1+e^{−t/T1}+2e^{−t/T2})/4；
    2q 张量信道 F_pro=F_pro^A·F_pro^B ⇒ ε=1−(4·F_pro+1)/5。
    """
    t = float(t_us) * 1e-6

    def _fpro(T1: float, T2: float) -> float:
        return (1.0 + math.exp(-t / float(T1)) + 2.0 * math.exp(-t / float(T2))) / 4.0

    fpro = _fpro(T1_a_s, T2_a_s) * _fpro(T1_b_s, T2_b_s)
    return 1.0 - (4.0 * fpro + 1.0) / 5.0


def residual_zz_error(t_us: float, zeta_mhz: float) -> float:
    """残余 ZZ 诱导错误率闭式 ε=(4/5)·sin²(ζt/2)（**与账本锚 B507 同一物理律**）。"""
    zeta_rad_per_us = 2.0 * math.pi * (float(zeta_mhz) * 1e-3)   # MHz ⇒ rad/µs
    phi = zeta_rad_per_us * float(t_us)
    return (4.0 / 5.0) * math.sin(phi / 2.0) ** 2


def qpu_cycle_error_budget(params: Optional[Dict] = None) -> Dict:
    """QPU 级误差预算集成：逐分量 ⇒ 每周期总错误率 ⇒ 阈值余量 + 签核。"""
    p = dict(DEFAULT_QPU_BUDGET)
    if params:
        p.update(params)
    T1 = _p_get(p, "T1_s")
    T2 = _p_get(p, "T2_s")

    # ① 1q 门（同一退相干律）
    eps_1q = PEM.gate_error_decoherence(_p_get(p, "t_1q_s"), T1, T2)
    # ② 2q CR 门（现算门时间；两比特取同参数 ≠ 掩盖：诚实并列 A/B）
    cr = cr_gate_time_us(_p_get(p, "J_mhz"), _p_get(p, "delta_mhz"),
                         _p_get(p, "alpha_mhz"))
    eps_2q = cr_gate_error_2q(cr["t_CR_us"], T1, T2, T1, T2)
    # ③ 读出误判（复用 readout_fidelity；与 B30 同律）
    ro = readout_fidelity(_p_get(p, "chi_ghz"), _p_get(p, "kappa_r_ghz"),
                          _p_get(p, "nbar"), _p_get(p, "eta"),
                          _p_get(p, "N_amp"), _p_get(p, "t_ro_s"), T1)
    eps_ro = float(ro["eps"])
    # ④ idle（同一退相干律）
    eps_idle = PEM.gate_error_decoherence(_p_get(p, "t_idle_s"), T1, T2)
    # ⑤ 残余 ZZ（最近邻静态 ZZ 预算；S 铁律② 上限）
    xt = S4.crosstalk_budget(p) if params is None else S4.crosstalk_budget()
    zeta = float(xt["max_nearest_zz_mhz"])
    eps_zz = residual_zz_error(cr["t_CR_us"], zeta)

    counts = {"1q": int(_p_get(p, "n_1q")), "2q": int(_p_get(p, "n_2q")),
              "ro": int(_p_get(p, "n_ro")), "idle": int(_p_get(p, "n_idle")),
              "zz": int(_p_get(p, "n_2q"))}
    comps = {"1q": eps_1q, "2q": eps_2q, "ro": eps_ro,
             "idle": eps_idle, "zz": eps_zz}

    # 集成口径 A：一阶独立求和（小量极限）
    p_sum = sum(comps[k] * counts[k] for k in comps)
    # 集成口径 B：级联保真度（大错误量下更保守）
    f_cyc = 1.0
    for k, e in comps.items():
        f_cyc *= (1.0 - e) ** counts[k]
    p_cascade = 1.0 - f_cyc

    n_ops = sum(counts.values())
    p_op_avg = p_sum / float(n_ops)          # 每操作平均错误率（阈值比较的标准口径）
    p_op_max = max(comps.values())           # 最差分量（透明披露，不作签核主判据）

    p_th = _p_get(p, "p_th")
    # 🔴 阈值口径：p_th≈1% 是 **circuit-level 每操作** 错误率（非每周期总量）
    #   ⇒ 签核比 p_op_avg；同时并列给出每周期总量与最差分量（不选择性披露）。
    margin = p_th - p_op_avg
    verdict = "ACCEPT" if (margin > 0.0) else "REJECT"
    over = [k for k, v in comps.items() if v > p_th]
    return {
        "components": {k: float(v) for k, v in comps.items()},
        "counts": counts, "n_ops": n_ops,
        "t_CR_us": cr["t_CR_us"], "g_CR_mhz": cr["g_CR_mhz"],
        "zeta_zz_mhz": zeta, "zeta_limit_mhz": float(S4.ZZ_STRAY_LIMIT_MHZ),
        "zz_within_limit": bool(zeta <= S4.ZZ_STRAY_LIMIT_MHZ),
        "p_cycle_sum": float(p_sum), "p_cycle_cascade": float(p_cascade),
        "p_op_avg": float(p_op_avg), "p_op_max": float(p_op_max),
        "components_over_threshold": over,
        "p_th": float(p_th), "threshold_margin": float(margin),
        "cycle_margin": float(p_th - p_sum),
        "orders_below_threshold": float(CAL.orders_below_threshold(p_op_avg, p_th)),
        "verdict": verdict,
        "note": ("QPU 每周期总错误率 = 逐分量（1q/2q/读出/idle/ZZ）× 周期内次数集成；"
                 "签核比**每操作平均错误率** p_op=p_cyc/n_ops 与阈值 p_th≈1%"
                 "（circuit-level 每操作口径）。并列披露每周期总量与最差分量。"
                 "2q 退相干与 B506 同律、ZZ 与 B507 同律、读出与 B30 同律 ⇒ "
                 "预算链与账本锚逐值可对拍（run_j2_qpu_smoke 常驻）。"
                 "设计预算，不含量子线路仿真/脉冲级控制。"),
    }


def qpu_budget_verdict(params: Optional[Dict] = None) -> str:
    """签核便捷入口：ACCEPT（余量 > 0 且 ZZ 在限内）/ REJECT。"""
    b = qpu_cycle_error_budget(params)
    if not b["zz_within_limit"]:
        return "REJECT"
    return b["verdict"]


def run_selfchecks(verbose: bool = False) -> bool:
    """常驻自检：分量律一致 / 集成口径自洽 / 余量方向 / 签核二值 / 反向敏感。"""
    bad = []

    def chk(name: str, cond: bool) -> None:
        if verbose:
            print("  [%s] %s" % ("PASS" if cond else "FAIL", name))
        if not cond:
            bad.append(name)

    # ① 2q 律与 B506 同构：t→0 ⇒ ε→0；且与独立手算一致（张量信道）
    e_small = cr_gate_error_2q(1e-9, 80e-6, 60e-6, 80e-6, 60e-6)
    chk("2q: t→0 ⇒ ε→0", 0.0 <= e_small < 1e-8)
    t_us, T1, T2 = 0.4418, 80e-6, 60e-6
    fp = (1 + math.exp(-t_us * 1e-6 / T1) + 2 * math.exp(-t_us * 1e-6 / T2)) / 4.0
    chk("2q: 与张量信道手算逐位", abs(cr_gate_error_2q(t_us, T1, T2, T1, T2)
                                      - (1 - (4 * fp * fp + 1) / 5)) < 1e-15)
    # ② ZZ 律：ζ→0 ⇒ 0；φ=π/2 ⇒ 2/5；φ=π ⇒ 4/5（现算 ζ·t 反推时刻）
    chk("ZZ: ζ→0 ⇒ 0", residual_zz_error(1.0, 0.0) < 1e-15)
    _t_pi2 = 0.25 / 1e-3          # ζ=1 MHz ⇒ rad/µs=2π·1e-3 ⇒ φ=π/2 时 t=0.25/1e-3
    chk("ZZ: φ=π/2 ⇒ (4/5)sin²(π/4)=2/5",
        abs(residual_zz_error(_t_pi2, 1.0) - 0.4) < 1e-12)
    chk("ZZ: φ=π ⇒ (4/5)sin²(π/2)=4/5",
        abs(residual_zz_error(2.0 * _t_pi2, 1.0) - 0.8) < 1e-12)
    # ③ 集成口径自洽：小量下两口径接近；级联 ≤ 朴素和
    b = qpu_cycle_error_budget()
    chk("集成口径 A/B 同量级（差 ≤ 30%）",
        abs(b["p_cycle_sum"] - b["p_cycle_cascade"]) <= 0.3 * b["p_cycle_sum"])
    chk("级联口径 ≤ 朴素和（保守方向）",
        b["p_cycle_cascade"] <= b["p_cycle_sum"] + 1e-15)
    # ④ 分量有限非负 + 次数为正
    chk("分量有限非负", all(math.isfinite(v) and v >= 0.0
                            for v in b["components"].values()))
    chk("次数为正", all(c > 0 for c in b["counts"].values()))
    # ⑤ 预算数字可读且与分量一致（现算复核）
    n2 = b["counts"]["2q"]
    recomputed = sum(b["components"][k] * b["counts"][k]
                     for k in b["components"])
    chk("p_cycle_sum 与分量现算一致", abs(recomputed - b["p_cycle_sum"]) < 1e-15)
    chk("2q 与 ZZ 同用 n_2q 次数", b["counts"]["zz"] == n2)
    # ⑥ ZZ 上限检查（S 铁律②）
    chk("ζ_zz 上限可读", b["zeta_limit_mhz"] == S4.ZZ_STRAY_LIMIT_MHZ)
    chk("ζ_zz 有限非负", math.isfinite(b["zeta_zz_mhz"]) and b["zeta_zz_mhz"] >= 0.0)
    # ⑦ 签核良定义：二值 + 与**每操作**余量一致 + 并列量可读
    chk("签核二值", b["verdict"] in ("ACCEPT", "REJECT"))
    chk("签核 == 每操作余量符号",
        b["verdict"] == ("ACCEPT" if b["threshold_margin"] > 0 else "REJECT"))
    chk("每操作均值 == 每周期总量 / 次数",
        abs(b["p_op_avg"] - b["p_cycle_sum"] / b["n_ops"]) < 1e-15)
    chk("最差分量可读（透明披露）", b["p_op_max"] == max(b["components"].values()))
    # ⑦′ 双向：默认档 ACCEPT；T1/T2 同步缩短 10× ⇒ 抬过阈值 ⇒ REJECT
    chk("默认档签核 ACCEPT", b["verdict"] == "ACCEPT")
    b_bad0 = qpu_cycle_error_budget({"T1_s": 8e-6, "T2_s": 6e-6})
    chk("反向：T1/T2 ÷10 ⇒ 每操作错误率抬过阈值 ⇒ REJECT",
        b_bad0["verdict"] == "REJECT" and b_bad0["threshold_margin"] < 0.0)
    # ⑧ 方向敏感性：T1/T2 同步缩短 10× ⇒ 总错误率必须上升（否则预算对物理不响应）
    b_bad = b_bad0
    chk("反向：T1/T2 缩短 10× ⇒ 总错误率上升", b_bad["p_cycle_sum"] > b["p_cycle_sum"])
    # ⑧′ 物理守卫：T2 > 2T1 非物理 ⇒ 抛错（不静默）
    try:
        qpu_cycle_error_budget({"T1_s": 8e-6})
        chk("非物理 T2>2T1 ⇒ 抛错", False)
    except ValueError:
        chk("非物理 T2>2T1 ⇒ 抛错", True)
    # ⑨ 读出时间加长 ⇒ 读出误判下降（优化方向正确）
    b_opt = qpu_cycle_error_budget(PRESET_OPTIMIZED)
    chk("优化档：读出误判 ≤ 默认档", b_opt["components"]["ro"]
        <= b["components"]["ro"])
    # ⑩ CR 参数区无效 ⇒ 抛错（不静默）
    try:
        cr_gate_time_us(20.0, -250.0, -250.0)
        chk("CR 越过参数区 ⇒ 抛错", False)
    except ValueError:
        chk("CR 越过参数区 ⇒ 抛错", True)

    if verbose:
        print("自检：%d FAIL" % len(bad))
    return not bad


if __name__ == "__main__":  # pragma: no cover
    print("J2 M4 QPU 级误差预算集成自检")
    ok = run_selfchecks(verbose=True)
    b = qpu_cycle_error_budget()
    print("  分量(默认档)：", {k: "%.3e" % v for k, v in b["components"].items()})
    print("  t_CR=%.4f µs  ζ_zz=%.4f MHz(限 %.1f)  p_cyc=%.4e  p_th=%.3g  "
          "余量=%.4e  %s" % (b["t_CR_us"], b["zeta_zz_mhz"], b["zeta_limit_mhz"],
                            b["p_cycle_sum"], b["p_th"], b["threshold_margin"],
                            b["verdict"]))
    bo = qpu_cycle_error_budget(PRESET_OPTIMIZED)
    print("  优化档：p_cyc=%.4e  余量=%.4e  %s" % (bo["p_cycle_sum"],
                                                bo["threshold_margin"], bo["verdict"]))
    print("ALL PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)
