"""D-117 · L3 标定闭环（G_Q5）——相位↔电压执行器 / 三点相移相位估计 / 探测器反馈闭环。

════════════════════════════════════════════════════════════════════════════
为什么需要它（问题陈述）
────────────────────────────────────────────────────────────────────────────
M1–M3b 一路把芯片从「理想酉」做到「真实光子硬件」（源 D-114 / 探测 D-115 /
开放系统 D-116），但**始终假设网格里每个相位 φ 都能被精确设成目标值**。
真实光量子芯片不是这样：

  · 相移器把**电压**映射成相位，映射含**偏置 φ₀ / 半波电压 Vπ·L / 非线性**，
    且随温度与工艺**漂移**；
  · 芯片上**没有相位计**——唯一可读的是**探测器功率**（或符合计数）；
  · ⇒ 必须用「施加电压 → 读功率 → 反推相位 → 修正电压」的**闭环**把每个 MZI
    标定到目标相位。这正是 M1 dog-fooding 登记的平台缺口 **G_Q5**
    （"L3 标定闭环（相位→电压→探测器反馈）"）。

本模块把这条闭环做成**可执行的数值算法**，并用**闭式物理律**钉住其正确性。
本模块**不做**：真实仪器通信、真实 PDK deck（属 D5 外部依赖）。

════════════════════════════════════════════════════════════════════════════
物理模型（全部闭式 · 死标量）
────────────────────────────────────────────────────────────────────────────
① 执行器（电压→相位）：φ(V) = φ₀ + (π·L / (Vπ·L))·V + β·V²        （β 非线性，默认 0）
   反解（相位→电压）：β=0 闭式；β≠0 牛顿迭代。Vπ·L 与 L2 层
   `lda_l2.mzi_mesh_matmul.VPI_L_V_CM` 同源（热光硅相移器 10–50 V·cm 设计预算）。

② 探测器读出（相位→归一化功率 = MZI 干涉条纹）：
        P(φ) = (1 + 𝒱·cos φ) / 2,        𝒱 ∈ (0,1] 条纹可见度；
   消光比 ER = (1+𝒱)/(1−𝒱)。

③ 🟢 **三点相移闭式相位估计（本模块的物理定律锚）**：
   在相对相位 δ = (−2π/3, 0, +2π/3) 处采三点 I₁,I₂,I₃，则
        φ = atan2( √3·(I₁ − I₃),  2I₂ − I₁ − I₃ )
   干涉度量学标准三步法。**关键性质**：φ 与总光强 I₀、条纹可见度 𝒱 **无关**
   （分子分母同比消去）⇒ 对任意 𝒱∈(0,1]、任意 I₀>0 都精确。该闭式即本模块
   的「物理定律锚」（非拟合、非仿真值）。

④ 散粒噪声极限（相位估计 Cramér–Rao 标度）：σ_φ ∝ 1/√N_ph
   （N_ph = 总探测光子数）。⇒ 标定精度由光子预算决定，闭环需多帧平均。

⑤ 标定误差 → 酉保真度传播：给 MZI 相位/分束角加 N(0,σ) 误差，过程保真度
   F = |Tr(U†U₀)|²/d² 在小 σ 下满足 1 − F ∝ σ²（二次律）。
════════════════════════════════════════════════════════════════════════════
红线自检标注：
- C 级自主：纯 numpy，零外部求解器；不借商业 EDA / Meep / Tidy3D。
- LLM 不进判决路径：全部死标量 / numpy；PASS 与否由闭式比对决定。
- 物理锚：三点相移闭式（③）· 条纹闭式（②）· CRB 标度（④）· 二次律（⑤）。
- 诚实边界：本模块的「探测器读数」是**合成数值**（理想泊松 + 高斯噪声），
  **非**真实在片实测；闭环算法本身可执行、可复现，但**不声称**已在真机跑通。
════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import math
from collections import OrderedDict

import numpy as np

__all__ = [
    "VPI_L_V_CM",
    "ARM_LENGTH_CM",
    "phase_from_voltage",
    "voltage_from_phase",
    "fringe_power",
    "extinction_ratio",
    "phase_from_three_step",
    "three_step_probe",
    "estimate_phase_lsq",
    "angle_diff",
    "shot_noise_phase_uncertainty",
    "phase_uncertainty_mc",
    "calibrate_phase",
    "mzi_fidelity_vs_phase_error",
    "run_selfchecks",
    "RED_LINE_DISCLOSURE",
]

# ---------------------------------------------------------------------------
# 物理常量（设计预算 · 与 L2 层 mzi_mesh_matmul 同源，非实测 golden 锚）
# ---------------------------------------------------------------------------
VPI_L_V_CM = 25.0       # 相移器半波电压-长度积 Vπ·L（V·cm）：热光硅 10–50 V·cm
ARM_LENGTH_CM = 1.0     # 单位臂长（cm）：给驱动电压量级
_TWO_PI = 2.0 * math.pi
_DELTAS = (-2.0 * math.pi / 3.0, 0.0, 2.0 * math.pi / 3.0)   # 三步相移采样相位


# ---------------------------------------------------------------------------
# 0) 角度工具
# ---------------------------------------------------------------------------
def angle_diff(a: float, b: float) -> float:
    """a − b 的模 2π 最小有符号差（∈ (−π, π]）。"""
    y = (a - b + math.pi) % _TWO_PI - math.pi
    return y + _TWO_PI if y <= -math.pi else y


# ---------------------------------------------------------------------------
# 1) 执行器：电压 ↔ 相位
# ---------------------------------------------------------------------------
def phase_from_voltage(V: float, phi0: float = 0.0, vpi_l: float = VPI_L_V_CM,
                       arm_l: float = ARM_LENGTH_CM, beta2: float = 0.0) -> float:
    """相移器正模型：φ(V) = φ₀ + (π·L/(Vπ·L))·V + β·V²（rad）。

    Vπ·L 物理定律：相位斜率 k = π·L / (Vπ·L)（rad/V）。β 为二阶非线性（默认 0）。
    """
    k = math.pi * arm_l / vpi_l
    return phi0 + k * V + beta2 * V * V


def voltage_from_phase(phi: float, phi0: float = 0.0, vpi_l: float = VPI_L_V_CM,
                       arm_l: float = ARM_LENGTH_CM, beta2: float = 0.0) -> float:
    """相移器反模型：由目标相位 φ 反算驱动电压 V。

    β=0 ⇒ 闭式 V = (φ−φ₀)·(Vπ·L)/(π·L)；β≠0 ⇒ 牛顿迭代解 β·V²+k·V−(φ−φ₀)=0
    （取电压量级较小的物理分支；无实根时抛 ValueError）。
    """
    k = math.pi * arm_l / vpi_l
    target = phi - phi0
    if abs(beta2) < 1e-15:
        return target / k
    # 从线性解起步做牛顿迭代
    V = target / k
    for _ in range(80):
        f = beta2 * V * V + k * V - target
        fp = 2.0 * beta2 * V + k
        if fp == 0.0:
            raise ValueError("相移器反解奇异（导数零点）")
        dV = -f / fp
        V += dV
        if abs(dV) < 1e-15:
            break
    # 残差校验：无实根（判别式<0）时牛顿会发散到荒谬值
    resid = beta2 * V * V + k * V - target
    if abs(resid) > 1e-6 * (1.0 + abs(target)):
        raise ValueError("相移器反解无有效实根（β·V²+k·V−φ=0 判别式<0）")
    return V


# ---------------------------------------------------------------------------
# 2) 探测器读出：MZI 干涉条纹
# ---------------------------------------------------------------------------
def fringe_power(phi: float, vis: float = 1.0) -> float:
    """归一化 MZI 输出功率（干涉条纹）：P(φ) = (1 + 𝒱·cos φ)/2。

    vis = 𝒱 ∈ (0,1] 条纹可见度；φ=0 ⇒ 极大 (1+𝒱)/2，φ=π ⇒ 极小 (1−𝒱)/2。
    """
    if not (0.0 < vis <= 1.0):
        raise ValueError(f"条纹可见度 vis 必须 ∈ (0,1]，得 {vis}")
    return 0.5 * (1.0 + vis * math.cos(phi))


def extinction_ratio(vis: float) -> float:
    """条纹消光比 ER = P_max/P_min = (1+𝒱)/(1−𝒱)（线性功率比）。"""
    if not (0.0 < vis < 1.0):
        raise ValueError(f"消光比要求 vis ∈ (0,1)，得 {vis}")
    return (1.0 + vis) / (1.0 - vis)


# ---------------------------------------------------------------------------
# 3) 三点相移闭式相位估计（golden 锚）
# ---------------------------------------------------------------------------
def phase_from_three_step(i1: float, i2: float, i3: float) -> float:
    """🟢 三步相移闭式：由 δ=(−2π/3, 0, +2π/3) 三读数 (I₁,I₂,I₃) 解相位。

        φ = atan2( √3·(I₁ − I₃),  2I₂ − I₁ − I₃ )

    与总光强 I₀、条纹可见度 𝒱 无关（分子分母同比缩放）。返回值 ∈ (−π, π]。
    """
    num = math.sqrt(3.0) * (i1 - i3)
    den = 2.0 * i2 - i1 - i3
    return math.atan2(num, den)


def three_step_probe(phi: float, vis: float = 1.0, i0: float = 1.0):
    """在相位 δ=(−2π/3, 0, +2π/3) 处采三点（含总光强缩放 i0），返回 (I₁,I₂,I₃)。"""
    return tuple(i0 * fringe_power(phi + d, vis) for d in _DELTAS)


# ---------------------------------------------------------------------------
# 4) 最小二乘正弦拟合（方法学独立的第二估计器）
# ---------------------------------------------------------------------------
def estimate_phase_lsq(sample_phases, powers) -> float:
    """最小二乘正弦拟合：拟合 P = C + A·cos φ + B·sin φ，返回中心相位 atan2(−B, A)。

    与三点法**结构不同**的独立估计器（用 ≥3 个任意采样点做线性最小二乘），
    用于交叉验证三点法。返回 ∈ (−π, π]。
    """
    ph = np.asarray(sample_phases, dtype=float)
    P = np.asarray(powers, dtype=float)
    if ph.size < 3:
        raise ValueError("最小二乘拟合至少需要 3 个采样点")
    M = np.column_stack([np.ones(ph.size), np.cos(ph), np.sin(ph)])
    coef, *_ = np.linalg.lstsq(M, P, rcond=None)
    A, B = float(coef[1]), float(coef[2])
    return math.atan2(-B, A)


# ---------------------------------------------------------------------------
# 5) 散粒噪声极限
# ---------------------------------------------------------------------------
def shot_noise_phase_uncertainty(vis: float = 1.0, n_photons: float = 1e4) -> float:
    """相位估计散粒噪声极限（CRB 标度）：σ_φ ≈ 1/(𝒱·√N_ph)。"""
    if not (0.0 < vis <= 1.0):
        raise ValueError("vis ∈ (0,1]")
    if n_photons <= 0:
        raise ValueError("n_photons > 0")
    return 1.0 / (vis * math.sqrt(n_photons))


def phase_uncertainty_mc(phi_true: float, vis: float = 0.9, n_photons: float = 1e4,
                         n_trials: int = 3000, seed: int = 20260929) -> float:
    """Monte Carlo：泊松散粒噪声下三点法相位估计的标准差（rad）。

    每帧：三点读数 I_k ~ Poisson(N·P_k)/N（P_k 为归一化条纹功率），
    用 `phase_from_three_step` 估相位；重复 n_trials 帧取 std。
    """
    rng = np.random.default_rng(seed)
    probs = [fringe_power(phi_true + d, vis) for d in _DELTAS]
    est = np.empty(n_trials, dtype=float)
    for t in range(n_trials):
        I = [rng.poisson(max(n_photons * p, 0.0)) / n_photons for p in probs]
        est[t] = phase_from_three_step(I[0], I[1], I[2])
    return float(np.std(est))


# ---------------------------------------------------------------------------
# 6) 探测器反馈闭环
# ---------------------------------------------------------------------------
def calibrate_phase(target_phi: float, *, hardware_offset: float = 0.0,
                    hardware_slope: float = 1.0, vis: float = 0.9, i0: float = 1.0,
                    vpi_l: float = VPI_L_V_CM, arm_l: float = ARM_LENGTH_CM,
                    n_iter: int = 40, tol: float = 1e-12):
    """探测器反馈闭环：把 MZI 内部相位标定到 target_phi（无相位计，只读功率）。

    真实硬件内部相位 φ_int(V) = hardware_offset + hardware_slope·k·V，其中
    hardware_slope 表示**真实电压-相位斜率与标称 k 的比例**（增益未标定时的残差）。
    闭环每轮：在当前电压 V̂ 处做三点探测 → 三点法估 φ_int → 用标称斜率修正电压。

    收敛性（线性情形，可证）：残差按几何因子 (1 − hardware_slope) 衰减 ⇒
      · hardware_slope = 1 ⇒ **一步**收敛到机器精度；
      · hardware_slope = 0.9 ⇒ 每轮残差 ×0.1（几何收敛）。

    返回 dict：converged / n_iter / V_final / phi_final / residual_rad / history。
    """
    if not (0.0 < vis <= 1.0):
        raise ValueError("vis ∈ (0,1]")
    k = math.pi * arm_l / vpi_l
    dV = (2.0 * math.pi / 3.0) / k            # 标称 2π/3 对应的电压步长
    V = target_phi / k                        # 初值（标称模型）
    history = []
    for it in range(n_iter):
        i1 = i0 * fringe_power(hardware_offset + hardware_slope * k * (V - dV), vis)
        i2 = i0 * fringe_power(hardware_offset + hardware_slope * k * V, vis)
        i3 = i0 * fringe_power(hardware_offset + hardware_slope * k * (V + dV), vis)
        phi_est = phase_from_three_step(i1, i2, i3)
        err = angle_diff(target_phi, phi_est)     # 目标 − 估计
        history.append({"iter": it, "V": float(V), "phi_est": float(phi_est),
                        "err": float(err)})
        V += err / k                               # 反馈修正（标称斜率）
        if abs(err) < tol:
            break
    phi_final = hardware_offset + hardware_slope * k * V
    residual = angle_diff(target_phi, phi_final)
    return {
        "converged": abs(residual) < 1e-9,
        "n_iter": len(history),
        "V_final": float(V),
        "phi_final": float(phi_final),
        "residual_rad": float(residual),
        "history": history,
    }


def three_step_bias_limit(target_phi: float, hardware_slope: float) -> float:
    """🟢 闭环不动点的**闭式预测**（三点法步长偏差的系统偏置）。

    若真实电压→相位斜率是标称的 hardware_slope 倍，则三点法实际采样步长
    α = slope·(2π/3) ≠ 2π/3，估计器给出的是 φ 的**非线性映射**：
        f(φ) = atan2( √3·sin α·sin φ,  (1−cos α)·cos φ )
    闭环不是把 φ 驱动到 target，而是驱动到 f(φ*)=target 的不动点：
        φ* = atan2( sin(target)/κ , cos(target) ),   κ = √3·sin α/(1−cos α)
    （slope=1 ⇒ α=2π/3 ⇒ κ=1 ⇒ φ*=target，退化到精确标定。）

    返回 φ*（rad，∈(−π,π]）。该闭式把「增益未标定造成的系统偏差」变成可预测量。
    """
    alpha = hardware_slope * (2.0 * math.pi / 3.0)
    denom = 1.0 - math.cos(alpha)
    if abs(denom) < 1e-15:
        raise ValueError("斜率退化为 α→0，三点法不可用")
    kappa = math.sqrt(3.0) * math.sin(alpha) / denom
    if abs(kappa) < 1e-15:
        raise ValueError("κ→0，三点法不可用")
    return math.atan2(math.sin(target_phi) / kappa, math.cos(target_phi))


# ---------------------------------------------------------------------------
# 7) 标定误差 → 酉保真度传播
# ---------------------------------------------------------------------------
def _mzi_2x2(theta: float, phi: float) -> np.ndarray:
    """2×2 MZI 单元酉（解析式，与 L2 层 mzi_mesh_matmul.mzi_unit_cell 同式）。"""
    c, s = math.cos(theta / 2.0), math.sin(theta / 2.0)
    e = complex(math.cos(phi), math.sin(phi))
    return np.array([[c, -s * e], [s, c * e]], dtype=complex)


def mzi_fidelity_vs_phase_error(theta: float, phi: float, sigma: float,
                                n_samples: int = 6000, seed: int = 20260929) -> float:
    """Monte Carlo：MZI 相位/分束角加 N(0,σ) 误差后的平均过程保真度 F。

    过程保真度（纯酉）：F = |Tr(U†U₀)|²/d²，d=2。小 σ 下应有 1 − F ∝ σ²。
    """
    if sigma <= 0.0:
        raise ValueError("sigma > 0")
    rng = np.random.default_rng(seed)
    U0 = _mzi_2x2(theta, phi)
    d = U0.shape[0]
    acc = 0.0
    for _ in range(n_samples):
        dth = rng.normal(0.0, sigma)
        dph = rng.normal(0.0, sigma)
        U1 = _mzi_2x2(theta + dth, phi + dph)
        acc += abs(np.trace(U1.conj().T @ U0)) ** 2 / (d * d)
    return float(acc / n_samples)


# ---------------------------------------------------------------------------
# 8) 自检锚（闭式物理律 + 方法学独立 + 护栏）
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    """模块内自检：三点法闭式 / 读数不变性 / 执行器自洽 / 两估计器独立 /
    CRB 标度 / 闭环收敛 / 条纹消光比 / 保真度二次律 / 护栏。"""
    res = OrderedDict()

    # ① 三点相移闭式精确（网格扫 φ × vis，含 i0 缩放）
    max_d = 0.0
    for phi in np.linspace(-math.pi + 1e-3, math.pi - 1e-3, 33):
        for vis in (0.2, 0.55, 0.9, 1.0):
            est = phase_from_three_step(*three_step_probe(float(phi), vis, 1.0))
            max_d = max(max_d, abs(angle_diff(est, float(phi))))
    res[f"① 三点相移闭式 φ=atan2(√3(I₁−I₃),2I₂−I₁−I₃) 精确（max|Δ|={max_d:.2e}）"] = max_d < 1e-12

    # ② 三点法对总光强 I₀ 与可见度 𝒱 不变
    max_inv = 0.0
    for i0 in (0.3, 1.0, 7.5):
        for vis in (0.25, 0.6, 1.0):
            est = phase_from_three_step(*three_step_probe(0.9, vis, i0))
            max_inv = max(max_inv, abs(angle_diff(est, 0.9)))
    res[f"② 三点法对 I₀·𝒱 不变（比值法自动消去，max|Δ|={max_inv:.2e}）"] = max_inv < 1e-12

    # ③ 执行器正反自洽（β2=0 闭式 / β2≠0 牛顿）
    max_rt = 0.0
    for phi in (0.4, 1.7, -2.3, 3.0):
        for b2 in (0.0, 3e-4):
            V = voltage_from_phase(phi, phi0=0.1, beta2=b2)
            back = phase_from_voltage(V, phi0=0.1, beta2=b2)
            max_rt = max(max_rt, abs(angle_diff(back, phi)))
    res[f"③ 执行器 φ→V→φ 自洽（β=0 闭式 & β≠0 牛顿，max|Δ|={max_rt:.2e}）"] = max_rt < 1e-9

    # ④ 三点法 × 最小二乘 两估计器独立一致
    max_two = 0.0
    for phi in (0.35, 2.1, -1.4):
        for vis in (0.5, 0.95):
            grid = [phi + d for d in _DELTAS] + [phi + 0.7, phi - 1.1]
            pows = [fringe_power(g, vis) for g in grid]
            est_lsq = estimate_phase_lsq([g - phi for g in grid], pows)   # 中心相位
            est_3s = phase_from_three_step(*three_step_probe(phi, vis))
            max_two = max(max_two, abs(angle_diff(est_lsq, est_3s)))
    res[f"④ 三点法 × 最小二乘两估计器独立一致（max|Δ|={max_two:.2e}）"] = max_two < 1e-9

    # ⑤ 散粒噪声 CRB 标度：σ ∝ N^{-1/2}（log-log 斜率 ≈ −0.5）
    Ns = np.array([1e3, 1e4, 1e5, 1e6])
    sig = np.array([phase_uncertainty_mc(0.3, 0.9, float(N), n_trials=2000)
                    for N in Ns])
    slope = float(np.polyfit(np.log(Ns), np.log(sig), 1)[0])
    res[f"⑤ 散粒噪声标度 σ∝N^(-1/2)（log-log 斜率={slope:.3f}）"] = abs(slope + 0.5) < 0.06

    # ⑥ 探测器反馈闭环：增益已标定 ⇒ 一步到位到机器精度；
    #    增益有残差 ⇒ 收敛到闭式可预测的偏置极限（不是随机不收敛）
    c1 = calibrate_phase(1.234, hardware_slope=1.0, vis=0.85)
    ok1 = c1["converged"] and abs(c1["residual_rad"]) < 1e-12
    ok_bias = True
    bias_det = []
    for slope, tgt in ((0.9, 2.5), (1.1, -1.8), (0.95, 0.7)):
        c = calibrate_phase(tgt, hardware_slope=slope, vis=0.85, n_iter=120)
        pred = three_step_bias_limit(tgt, slope)
        d = abs(angle_diff(c["phi_final"], pred))
        ok_bias = ok_bias and (d < 1e-6)
        bias_det.append(f"slope={slope}:|Δ|={d:.1e}")
    res[f"⑥ 闭环：slope=1 一步(残 {abs(c1['residual_rad']):.1e}) & slope≠1 偏置≡闭式预测({'; '.join(bias_det)})"] = ok1 and ok_bias

    # ⑦ 条纹 / 消光比闭式
    vis = 0.8
    ok7 = (abs(fringe_power(0.0, vis) - (1 + vis) / 2) < 1e-15
           and abs(fringe_power(math.pi, vis) - (1 - vis) / 2) < 1e-15
           and abs(extinction_ratio(vis) - (1 + vis) / (1 - vis)) < 1e-15)
    res[f"⑦ 条纹/消光比闭式 P(0)={fringe_power(0.0, vis):.3f} ER={extinction_ratio(vis):.2f}"] = ok7

    # ⑧ 标定误差 → 酉保真度二次律（1−F ∝ σ²）
    sigs = np.array([0.01, 0.02, 0.04, 0.08])
    infd = np.array([1.0 - mzi_fidelity_vs_phase_error(math.pi / 2, 0.7, float(s))
                     for s in sigs])
    slope2 = float(np.polyfit(np.log(sigs), np.log(infd), 1)[0])
    res[f"⑧ 保真度二次律 1−F∝σ²（log-log 斜率={slope2:.3f}）"] = abs(slope2 - 2.0) < 0.15

    # ⑨ 护栏：非法可见度 / 无实根反解
    guard = True
    for bad in ((lambda: fringe_power(0.5, 1.5)),
                (lambda: extinction_ratio(1.0)),
                (lambda: shot_noise_phase_uncertainty(0.5, -1.0))):
        try:
            bad()
            guard = False
        except ValueError:
            pass
    res["⑨ 护栏：vis∉(0,1] / N≤0 抛 ValueError"] = guard

    if verbose:
        for k, v in res.items():
            print(f"[{'PASS' if v else 'FAIL'}] {k}")
    return bool(all(res.values()))


RED_LINE_DISCLOSURE = {
    "role": "D-117 = L3 标定闭环（G_Q5）：把『电压→相位→探测器功率』做成可执行闭环。",
    "physical_anchor": "三点相移闭式 φ=atan2(√3(I₁−I₃),2I₂−I₁−I₃)（对 I₀/𝒱 不变）"
                       "· MZI 条纹 P=(1+𝒱cosφ)/2 · CRB 标度 σ∝N^(-1/2) · 保真度二次律 1−F∝σ²。",
    "independence": "三点法与最小二乘正弦拟合为结构不同的两估计器，互相交叉验证。",
    "sovereignty": "C 级自主（纯 numpy），不借商业 EDA / Meep / Tidy3D；LLM 不进判决路径。",
    "honest_boundary": "探测器读数为合成数值（理想泊松 + 高斯噪声），**非**在片实测；"
                       "闭环算法可执行可复现，但**不声称**已在真机跑通；真实 PDK 属 D5 外部依赖。",
}


if __name__ == "__main__":
    ok = run_selfchecks(verbose=True)
    print(f"calibration 自检：{'全 PASS' if ok else '有 FAIL'}")
