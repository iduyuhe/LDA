"""J3 量子测控与读出征程 · M0/M1 测控闭环总装（闭环可用性 · 能力层）。

🔴 主权纪律：本模块是**能力验证**模块（门禁 `run_j3_ctrl_smoke` 覆盖），**不是账本锚**；
纯标准库 + numpy（复用本征程 `pulse_library` / `qubit_dynamics`），全确定性（零 RNG）。

**闭环四环（J3 蓝图「闭环可用性」的机器实现）**：

  Ring A **Rabi 幅度定标闭环**：DAC/任意波形发生器的实际增益 g 未知（A_delivered = g·A_req）。
    控制器只观测物理量 **P₁**（TDSE 数值演化得到），用固定增益 γ 的乘性更新
        A_req ← A_req · (π / θ_measured)^γ,   θ_measured = 2·asin(√P₁)
    迭代至 |P₁ − 1| < tol（几何收敛 ⇒ 迭代次数可机器核验）。
    ⇒ 这是「幅度 ⇄ 布居」这一**唯一可观测通道**的闭环，是实验上 Rabi 定标的标准范式。

    🔴 **捕获范围（本轮实测发现，如实登记）**：`θ_measured = 2·asin(√P₁) ∈ [0, π]` 是
    **折叠**的（asin 主值）⇒ 该乘性更新只在 **θ ∈ (0, π)** 内是收缩映射（误差每步 ×½）；
    一旦初始 θ₀ = g·A₀·t **超过 π**，测得的 θ 反而变小 ⇒ A_req 单调放大 ⇒ **发散**
    （实测 g=2.5 ⇒ θ₀=4.0 > π ⇒ A_req 数值溢出）。
    ⇒ 实现**显式捕获范围守卫**（越界即 `diverged=True` 并 `break`，**不静默溢出**）；
    真实实验里靠「从小到大扫功率先定位第一个 π 脉冲」解决（本模块只做诚实披露，不假装通用）。

  Ring B **DRAG 泄漏抑制闭环**：在标定好的 π 脉冲上扫描 DRAG 系数 β，取泄漏极小 β*，
    报**抑制比** L = P_leak(β=0)/P_leak(β*)，并**回写** β* 进脉冲规格。

  Ring C **读出判别环**：给定读出信噪比 SNR ⇒ 误判概率 ε = ½·erfc(SNR/√2)
    （🔴 口径**复用** D-47 / B30 的「色散读出 SNR → erfc 误判链」，同一物理律，
    本模块不重造公式语义，只在门禁里做**跨模块数值一致**复核）。

  Ring D **签核**：把三环结果汇总为控制层签核（定标收敛 ∧ 泄漏抑制达标 ∧ 读出误判达标
    ⇒ ACCEPT / REJECT），并**并列披露**各环实测值与限值。

  Ring E **门保真环（M2）**：RB 一阶 p 与二阶 unitarity u 联立 ⇒ 相干/非相干误差分解
    （复用 `rb_benchmark`，去极化关系 u=p² 精确）。

  Ring F **读出链环（M3）**：IQ 解调 + 判别阈值 + 分配矩阵（列和=1）+ Purcell 滤波抑制比
    （复用 `readout_demod`，与账本锚 B513 同律）。

  Ring G **低温电子学环（M4）**：Caves 量子极限（n_add ≥ 1/2）+ Friis 级联 + cryo-CMOS
    权衡（复用 `cryo_electronics`，与账本锚 B514 同律）。

  **`full_control_loop_report` = 测控闭环总装（M4）**：脉冲（A/B）→ 门保真（E）→
    读出（F）→ 反馈（把标定值**回写**成控制参数规格 spec）→ 低温电子学（G），
    四子报告全 ACCEPT 才 ACCEPT（J3 章程 §3 M4 的 G-CTRL* 闭合）。

🔴 与 J2 的口径边界（防混淆，必读）：
  · J2 `qpu_error_budget` 是**物理比特层**误差预算（退相干 / 门 / 读出 / idle / ZZ）；
    本模块是**控制层**闭环签核（脉冲定标收敛 + 相干泄漏抑制 + 读出误判）——
    两者在不同抽象层，**不重复计数**、也不互相替代。
  · 本模块**不建模 T1/T2 退相干**（属 J2 `physical_error_model`）。

🔴 诚实边界：
  · σ/α/β/g/SNR/γ 均为**设计示例量级**（非实测 PDK / 非任意波形发生器标定数据）；
  · 未知增益 g 是**确定性常数**（非随机漂移）；本模块不建模 1/f 漂移、温漂、线缆延迟；
  · 泄漏是**相干泄漏**（三能级、无退相干）；DRAG 抑制比是两次数值解之商 ⇒ **不作 golden**；
  · 只证「闭环迭代收敛 + 抑制趋势 + 读出误判链自洽」，**不作制造/性能宣称**，
    不报能效/TOPS/fJ-op。
红线：纯 numpy + 标准库 · 零量子 SDK · LLM 不进判决路径 · 限值为设计规则。
"""
from __future__ import annotations

import math

from lda_qeda.pulse_library import calibrate_amplitude
from lda_qeda.qubit_dynamics import (
    drag_leakage,
    drag_optimal_beta,
    leakage_suppression_ratio,
    rabi_population,
)
from lda_qeda import rb_benchmark as _RB
from lda_qeda import readout_demod as _RD
from lda_qeda import cryo_electronics as _CE

__all__ = [
    "DEFAULT_LOOP",
    "READOUT_SNR_MIN",
    "LEAKAGE_LIMIT",
    "readout_error_probability",
    "rabi_amplitude_calibrate",
    "control_loop_report",
    "full_control_loop_report",
    "run_selfchecks",
]

#: 默认闭环设计参数（设计示例量级 · 非实测 PDK）
DEFAULT_LOOP = {
    "t_pulse_ns": 40.0,     # π 脉冲时长（ns）
    "omega0": 0.04,         # 初始幅度猜测（rad/ns）
    "true_gain": 1.37,      # 硬件实际增益 g（未知，闭环要标定掉的量）
    "loop_gain": 0.5,       # 控制器迭代增益 γ ∈ (0, 1]
    "loop_tol": 1e-9,       # 收敛判据 |P₁ − 1| < tol
    "max_iter": 200,
    "n_steps": 3000,        # 「一次测量」的 TDSE 步数（实测 RK4 残差 ~3e-17 ≪ 1e-9 判据）
}

#: 读出信噪比下限（设计规则 · 可覆盖）；误判率上限
READOUT_SNR_MIN = 5.0
LEAKAGE_LIMIT = 1e-2        # 相干泄漏布居上限（设计规则 · 可覆盖）


def readout_error_probability(snr: float) -> float:
    """二分态高斯的误判概率 ε = ½·erfc(SNR/√2)（口径复用 D-47 / B30）。"""
    return 0.5 * math.erfc(float(snr) / math.sqrt(2.0))


def rabi_amplitude_calibrate(t_pulse: float = None, true_gain: float = None,
                             omega0: float = None, loop_gain: float = None,
                             tol: float = None, max_iter: int = None,
                             n_steps: int = None):
    """Ring A —— Rabi 幅度定标闭环（乘性固定增益迭代，几何收敛）。

    返回 dict：`trace`（每次迭代的 (k, A_req, P₁, |P₁−1|)）· `omega`（收敛 A_req）
    · `iterations` · `converged` · `diverged`（越出捕获范围）· `final_p1` · `true_gain`。
    """
    p = DEFAULT_LOOP
    t_pulse = p["t_pulse_ns"] if t_pulse is None else float(t_pulse)
    true_gain = p["true_gain"] if true_gain is None else float(true_gain)
    omega0 = p["omega0"] if omega0 is None else float(omega0)
    loop_gain = p["loop_gain"] if loop_gain is None else float(loop_gain)
    tol = p["loop_tol"] if tol is None else float(tol)
    max_iter = p["max_iter"] if max_iter is None else int(max_iter)
    n_steps = p["n_steps"] if n_steps is None else int(n_steps)
    if not 0.0 < loop_gain <= 1.0:
        raise ValueError("迭代增益 γ 须 ∈ (0, 1]")

    omega_req = omega0
    trace = []
    converged = False
    diverged = False
    p1 = 0.0
    bound = 1e3 * max(abs(omega0), 1e-12)
    for k in range(max_iter):
        # 硬件施加 A_delivered = g·A_req（g 未知）；控制器只看到 P₁
        p1 = rabi_population(true_gain * omega_req, 0.0, t_pulse, n=n_steps)
        trace.append((k, omega_req, p1, abs(p1 - 1.0)))
        if not math.isfinite(p1):
            diverged = True
            break
        if abs(p1 - 1.0) < tol:
            converged = True
            break
        theta = 2.0 * math.asin(min(1.0, math.sqrt(max(p1, 0.0))))
        if theta <= 0.0:
            diverged = True
            break
        omega_req = omega_req * (math.pi / theta) ** loop_gain
        if omega_req > bound or omega_req < 1e-3 * bound:
            # 🔴 捕获范围守卫：θ₀ > π ⇒ 折叠测量使 A_req 单调放大 ⇒ 越界即显式失败
            diverged = True
            break
    return {
        "trace": trace,
        "omega": omega_req,
        "iterations": len(trace),
        "converged": converged,
        "diverged": diverged,
        "final_p1": p1,
        "true_gain": true_gain,
        "t_pulse_ns": t_pulse,
    }


def control_loop_report(t_pulse: float = None, true_gain: float = None,
                        snr: float = None, n_steps: int = None) -> dict:
    """把闭环三环汇总为控制层签核（ACCEPT / REJECT），并列披露各环实测值。"""
    p = DEFAULT_LOOP
    t_pulse = p["t_pulse_ns"] if t_pulse is None else float(t_pulse)
    true_gain = p["true_gain"] if true_gain is None else float(true_gain)
    n_steps = p["n_steps"] if n_steps is None else int(n_steps)
    snr = READOUT_SNR_MIN if snr is None else float(snr)

    ring_a = rabi_amplitude_calibrate(t_pulse=t_pulse, true_gain=true_gain,
                                      n_steps=n_steps)
    amp = calibrate_amplitude()
    beta_star = drag_optimal_beta(n=n_steps)
    p_leak_on = drag_leakage(beta=beta_star, n=n_steps, amplitude=amp)
    p_leak_off = drag_leakage(beta=0.0, n=n_steps, amplitude=amp)
    ratio = leakage_suppression_ratio(n=n_steps)
    eps = readout_error_probability(snr)

    a_ok = bool(ring_a["converged"])
    b_ok = bool(p_leak_on < LEAKAGE_LIMIT)
    c_ok = bool(snr >= READOUT_SNR_MIN)
    verdict = "ACCEPT" if (a_ok and b_ok and c_ok) else "REJECT"
    return {
        "verdict": verdict,
        "ring_a": {
            "converged": a_ok,
            "iterations": ring_a["iterations"],
            "final_p1": ring_a["final_p1"],
            "omega_req": ring_a["omega"],
            "true_gain": true_gain,
        },
        "ring_b": {
            "beta_star": beta_star,
            "p_leak_no_drag": p_leak_off,
            "p_leak_with_drag": p_leak_on,
            "suppression_ratio": ratio,
            "leakage_limit": LEAKAGE_LIMIT,
            "within_limit": b_ok,
        },
        "ring_c": {
            "snr": snr,
            "readout_error": eps,
            "snr_min": READOUT_SNR_MIN,
            "within_limit": c_ok,
        },
        "note": ("控制层闭环签核（三层）：Ring A Rabi 幅度定标收敛（测得 P₁→1，未知硬件增益 g "
                 "被标定掉）· Ring B DRAG 泄漏抑制（β* 取泄漏极小，P_leak 需 < %.0e）· "
                 "Ring C 读出判别（SNR ≥ %.1f，误判 ε=½erfc(SNR/√2)）。"
                 "🔴 与 J2 `qpu_error_budget`（物理比特层退相干/门/读出预算）不同抽象层、不重复计数；"
                 "本模块不建模 T1/T2。设计示例量级（非实测 PDK）。"
                 % (LEAKAGE_LIMIT, READOUT_SNR_MIN)),
    }


def full_control_loop_report(t_pulse: float = None, true_gain: float = None,
                             snr: float = None, n_steps: int = None) -> dict:
    """**测控闭环总装**（J3 章程 §3 M4 · 缺口 G-CTRL*）：

       脉冲（Ring A/B）→ 门保真（M2 RB+unitarity）→ 读出（M3 解调+Purcell）
       → 反馈（把各环标定值回写成**控制参数规格**）→ 低温电子学（M4 Caves+级联）

    返回五段结果 + **回写规格** `spec`，签核 = 四子报告**全部** ACCEPT。
    🔴 与 J2 `qpu_error_budget`（物理比特层）不同抽象层、不重复计数；不建模 T1/T2。
    """
    base = control_loop_report(t_pulse=t_pulse, true_gain=true_gain, snr=snr, n_steps=n_steps)
    rb = _RB.rb_report()
    rd = _RD.readout_chain_report(snr=snr)
    cy = _CE.cryo_noise_report()
    spec = {
        "pulse_amplitude": base["ring_a"]["omega_req"],      # Ring A 回写：π 脉冲幅度
        "drag_beta": base["ring_b"]["beta_star"],            # Ring B 回写：DRAG 系数
        "gate_fidelity_param_p": rb["p"],                    # M2 回写：一阶 RB 参数
        "unitarity": rb["u"],                                # M2 回写：二阶 unitarity
        "readout_threshold": rd["threshold"],                # M3 回写：判别阈值
        "readout_error": rd["readout_error"],                # M3 回写：误判率
        "purcell_suppression": rd["purcell_suppression"],    # M3 回写：滤波抑制比
        "amp_added_noise": cy["distributed_nadd"],           # M4 回写：放大链附加噪声
    }
    all_ok = (base["verdict"] == "ACCEPT" and rb["verdict"] == "ACCEPT"
              and rd["verdict"] == "ACCEPT" and cy["verdict"] == "ACCEPT")
    return {
        "verdict": "ACCEPT" if all_ok else "REJECT",
        "pulse": base,
        "gate_fidelity": rb,
        "readout": rd,
        "cryo": cy,
        "spec": spec,
        "note": ("测控闭环总装（脉冲→门→读出→反馈→低温电子学）：四子报告全 ACCEPT 才 ACCEPT。"
                 "spec 为回写的控制参数规格（设计示例量级）。零量子 SDK。"),
    }


def run_selfchecks(verbose: bool = False) -> bool:
    """常驻自检：闭环几何收敛 / 标定正确性 / DRAG 抑制 / 读出误判链 / 签核二值 + 反向。"""
    bad = []

    def chk(name: str, cond: bool) -> None:
        if verbose:
            print("  [%s] %s" % ("PASS" if cond else "FAIL", name))
        if not cond:
            bad.append(name)

    # ① 闭环收敛：收敛标志为真、迭代次数有限、终态 P₁ 距 1 < tol
    ra = rabi_amplitude_calibrate()
    chk("Ring A 收敛", ra["converged"] is True)
    chk("Ring A 终态 |P₁−1| < tol", abs(ra["final_p1"] - 1.0) < DEFAULT_LOOP["loop_tol"])
    chk("Ring A 迭代次数 > 1（真迭代，非一步解析回代）", ra["iterations"] > 1)
    # ② 标定正确性：收敛幅度 × 真增益 × 脉冲时长 → π（π 脉冲条件）。
    #    🔴 精度由收敛判据决定：|P₁−1| = cos²(θ/2) ≈ (π−θ)²/4 ⇒ |π−θ| ≤ 2√tol
    #    （本轮实测 |Δ|=3.2e-5，与 2√(1e-9)=6.3e-5 同量级 ⇒ 口径自洽）。
    ang = ra["omega"] * ra["true_gain"] * ra["t_pulse_ns"]
    tol_a = 2.0 * math.sqrt(DEFAULT_LOOP["loop_tol"]) * 1.1
    chk("Ring A 标定正确：A*·g·t → π（|Δ| ≤ 2√tol）", abs(ang - math.pi) < tol_a)
    # ③ 几何收敛：误差序列在收敛前严格下降
    errs = [e for _, _, _, e in ra["trace"]]
    chk("Ring A 误差单调下降（收敛前）",
        all(errs[i] > errs[i + 1] for i in range(len(errs) - 2)))
    # ④ 标定不变量：不同（未知）硬件增益 g **在捕获范围内** ⇒ 收敛到**同一物理角**
    #    A*·g·t = π —— 这正是「闭环把未知增益标定掉」的机器证据（控制器 A_req 随 g 反向
    #    缩放，物理角不变）。🔴 捕获范围 θ₀ = g·A₀·t < π ⇒ g < π/(A₀·t) = 1.963。
    angs = []
    for g in (0.8, 1.0, 1.37, 1.8):
        ra_g = rabi_amplitude_calibrate(true_gain=g)
        if not ra_g["converged"]:
            angs.append(float("inf"))
        angs.append(abs(ra_g["omega"] * g * ra_g["t_pulse_ns"] - math.pi))
    chk("Ring A 标定不变量：g∈{0.8,1.0,1.37,1.8} 均收敛且 A*·g·t=π", max(angs) < tol_a)
    # ⑤ 🔴 捕获范围如实披露（非静默溢出）：θ₀ = g·A₀·t = 4.0 > π 的档必须**显式** diverged
    ra_out = rabi_amplitude_calibrate(true_gain=2.5)
    chk("Ring A 捕获范围：g=2.5（θ₀=4.0>π）⇒ diverged 且 converged=False",
        ra_out["diverged"] is True and ra_out["converged"] is False
        and math.isfinite(ra_out["omega"]))
    # ⑥ DRAG 抑制：比值 > 1 且 DRAG 档泄漏 < 无 DRAG 档
    amp = calibrate_amplitude()
    chk("Ring B DRAG 抑制比 > 1", leakage_suppression_ratio() > 1.0)
    chk("Ring B DRAG 档泄漏 < 无 DRAG 档",
        drag_leakage(beta=1.0, amplitude=amp) < drag_leakage(beta=0.0, amplitude=amp))
    # ⑥ 读出误判链：SNR ↑ ⇒ ε ↓；大 SNR → 0；erfc 口径与公式一致
    chk("Ring C ε 随 SNR 单调降",
        readout_error_probability(3.0) > readout_error_probability(5.0)
        > readout_error_probability(8.0))
    chk("Ring C ε(SNR→大)→0", readout_error_probability(12.0) < 1e-30)
    chk("Ring C ε 与公式同源", abs(readout_error_probability(3.0)
                                   - 0.5 * math.erfc(3.0 / math.sqrt(2.0))) < 1e-18)
    # ⑦ 签核二值 + 三条件合取一致
    rep = control_loop_report()
    chk("签核二值", rep["verdict"] in ("ACCEPT", "REJECT"))
    chk("签核 = 三环合取",
        (rep["verdict"] == "ACCEPT") == (rep["ring_a"]["converged"]
                                        and rep["ring_b"]["within_limit"]
                                        and rep["ring_c"]["within_limit"]))
    chk("默认档 ACCEPT", rep["verdict"] == "ACCEPT")
    # ⑧ 反向：读出 SNR 取到荒谬小 ⇒ 读出环 FAIL ⇒ 整链 REJECT（可证伪）
    rep_bad = control_loop_report(snr=0.5)
    chk("反向：SNR=0.5 ⇒ 读出环 FAIL", rep_bad["ring_c"]["within_limit"] is False)
    chk("反向：SNR=0.5 ⇒ 整链 REJECT", rep_bad["verdict"] == "REJECT")
    # ⑨ M2 门保真环：RB + unitarity（去极化关系 u=p² 精确）
    rb = _RB.rb_report()
    chk("M2 RB 签核 ACCEPT", rb["verdict"] == "ACCEPT")
    chk("M2 去极化关系 u=p²", abs(rb["u"] - rb["p"] ** 2) < 1e-15)
    # ⑩ M3 读出链环：解调 + 分配矩阵列和 + Purcell 抑制
    rd = _RD.readout_chain_report()
    chk("M3 读出链签核 ACCEPT", rd["verdict"] == "ACCEPT")
    chk("M3 分配矩阵列和=1",
        all(abs(sum(rd["assignment"][i][j] for i in range(2)) - 1.0) < 1e-15
            for j in range(2)))
    chk("M3 Purcell 抑制 ≥ 1", rd["purcell_suppression"] >= 1.0)
    # ⑪ M4 低温电子学环：Caves 极限 + 级联噪声
    cy = _CE.cryo_noise_report()
    chk("M4 低温电子学签核 ACCEPT", cy["verdict"] == "ACCEPT")
    chk("M4 Caves 极限 = 1/2", abs(cy["caves_limit"] - 0.5) < 1e-15)
    # ⑫ 总装：五段闭环全 ACCEPT + 回写规格完整 + 反向
    full = full_control_loop_report()
    chk("总装闭环签核 ACCEPT", full["verdict"] == "ACCEPT")
    chk("总装回写规格八键齐备", len(full["spec"]) == 8
        and all(k in full["spec"] for k in
                ("pulse_amplitude", "drag_beta", "unitarity", "purcell_suppression")))
    chk("总装签核二值", full["verdict"] in ("ACCEPT", "REJECT"))
    full_bad = full_control_loop_report(snr=0.5)
    chk("反向：总装 SNR=0.5 ⇒ REJECT", full_bad["verdict"] == "REJECT")

    if verbose:
        print("自检：%d FAIL" % len(bad))
    return not bad


if __name__ == "__main__":  # pragma: no cover
    print("J3 测控闭环总装（Rabi 定标 / DRAG 抑制 / 读出判别 / 签核）自检")
    ok = run_selfchecks(verbose=True)
    print("ALL PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)
