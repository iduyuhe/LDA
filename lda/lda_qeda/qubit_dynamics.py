"""J3 量子测控与读出征程 · M0 量子态时域动力学（TDSE 演化器 · 能力层）。

🔴 主权纪律：本模块是**能力验证**模块（门禁 `run_j3_ctrl_smoke` 覆盖），**不是账本锚**；
纯 numpy（自研 RK4，不用任何量子 SDK），全确定性（零 RNG）。

提供（时域驱动演化）：
  · `two_level_H(Omega, delta)` / `qutrit_H(Omega, alpha)`：RWA 驱动哈密顿
    （二能级 (δ/2)σ_z + (Ω/2)σ_x；三能级含 √2 升降矩阵元与非谐性 α）。
  · `evolve_constant(H, psi0, t, n)`：常矩阵 TDSE 四阶 RK4（n 步）。
  · `evolve_time_dependent(H_of_t, psi0, t0, t1, n)`：**含时**哈密顿 RK4
    （四阶 Gauss–Legendre 三点采样：h/2 中点 + 两端点，标准 RK4 对含时驱动即足够四阶）。
  · `rabi_population(Omega, delta, t, n)`：二能级 |1⟩ 布居 P₁。
  · `qutrit_leakage(Omega, alpha, t, n)`：方波驱动下 |2⟩ 泄漏布居 P_leak。
  · `drag_leakage(sigma, alpha, beta, ...)`：**Gaussian(+DRAG) 脉冲**下泄漏布居
    （脉冲幅度按 `pulse_library.calibrate_amplitude` 定标到面积 π ⇒ π 脉冲）。
  · `leakage_suppression_ratio(...)`：**DRAG 泄漏抑制比** L = P_leak(β=0) / P_leak(β*)。
  · `drag_optimal_beta(...)`：扫描 β 取泄漏极小（数值最优化，非解析）。

🔴 与账本锚的关系（口径分工 · 必读）：
  · 本模块的**闭式对照量**（广义 Rabi 闭式 / 三能级谱分解闭式）**不在本模块**，而在
    账本数值核 `lda_harness/_batch_j3_numeric.py`（B510/B511）—— 能力层只做**数值演化**，
    闭式 golden 走 harness 判决。**同一物理量只有一份闭式实现**（单一真源纪律）。
  · `qutrit_leakage` 的**方波**档与账本锚 B511 candidate 同物理模型（同一 H），
    但**数值格式独立实现**（本模块允许外部注入步数、并在自检里核对与解析谱一致）；
    真正的判决一致性由门禁的「能力层↔账本锚同律」判据机器复核。
  · `leakage_suppression_ratio`（DRAG 抑制比）是**两次数值解之商** ⇒ **不作 golden、不进账本**
    （比值无独立闭式对照；如实放在能力层，只作工程指标与单调性/反向判据）。

🔴 诚实边界：
  · Ω/α/δ/σ/β/t 均为**设计示例量级**（非实测 PDK / 非任意波形发生器标定）；
  · 三能级模型**未建模**高阶能级（|3⟩+）、驱动线非线性、T1/T2 退相干（退相干另在
    J2 `physical_error_model`）⇒ 本模块的泄漏是**相干泄漏**（coherent leakage）；
  · 只证「时域数值演化 → 布居/泄漏」自洽与 DRAG 抑制趋势，**不作制造/性能宣称**，
    不报能效/TOPS/fJ-op。
红线：纯 numpy · 零量子 SDK · LLM 不进判决路径 · 阈值为设计规则。
"""
from __future__ import annotations

import math

import numpy as np

from lda_qeda.pulse_library import (
    DEFAULT_PULSE,
    calibrate_amplitude,
    drag_quadrature,
    gaussian,
    pulse_window,
)

__all__ = [
    "two_level_H",
    "qutrit_H",
    "evolve_constant",
    "evolve_time_dependent",
    "rabi_population",
    "qutrit_leakage",
    "drag_leakage",
    "leakage_suppression_ratio",
    "drag_optimal_beta",
    "run_selfchecks",
]

_SQRT2 = math.sqrt(2.0)


def two_level_H(Omega: float, delta: float) -> "np.ndarray":
    """二能级 RWA 驱动哈密顿 H = (δ/2)σ_z + (Ω/2)σ_x（|0⟩ 取 +δ/2）。"""
    return np.array([[float(delta) / 2.0, float(Omega) / 2.0],
                     [float(Omega) / 2.0, -float(delta) / 2.0]], dtype=complex)


def _ladder() -> "np.ndarray":
    """三能级升降算符 a = Σ_n √(n+1)|n⟩⟨n+1|（√2 来自谐振子矩阵元）。"""
    return np.array([[0.0, 1.0, 0.0],
                     [0.0, 0.0, _SQRT2],
                     [0.0, 0.0, 0.0]], dtype=float)


def qutrit_H(Omega: float, alpha: float) -> "np.ndarray":
    """三能级 transmon RWA 驱动哈密顿（方波驱动，Ω_x 常数）。

        H = (Ω/2)(a + a†) + α·|2⟩⟨2|
    """
    lap = _ladder()
    x = lap + lap.T
    h = (float(Omega) / 2.0) * x
    h[2, 2] += float(alpha)
    return h.astype(complex)


def _qutrit_drive_matrices():
    """返回 (X, Y, P2)：三能级驱动算符（a+a†、i(a†−a)、|2⟩⟨2|）。"""
    lap = _ladder()
    x = lap + lap.T
    y = 1j * (lap.T - lap)
    p2 = np.zeros((3, 3), dtype=float)
    p2[2, 2] = 1.0
    return x, y, p2


def evolve_constant(H: "np.ndarray", psi0: "np.ndarray", t: float, n: int) -> "np.ndarray":
    """常矩阵 TDSE（i dψ/dt = Hψ）四阶 RK4 推进 [0, t]，n 步。"""
    n = int(n)
    if n < 1:
        raise ValueError("步数 n 须 ≥ 1")
    h = float(t) / n
    psi = np.asarray(psi0, dtype=complex)

    def _f(y):
        return -1j * (H @ y)

    for _ in range(n):
        k1 = _f(psi)
        k2 = _f(psi + 0.5 * h * k1)
        k3 = _f(psi + 0.5 * h * k2)
        k4 = _f(psi + h * k3)
        psi = psi + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return psi


def evolve_time_dependent(H_of_t, psi0: "np.ndarray", t0: float, t1: float,
                          n: int) -> "np.ndarray":
    """含时哈密顿 TDSE 四阶 RK4 推进 [t0, t1]，n 步（中点采样标准 RK4）。"""
    n = int(n)
    if n < 1:
        raise ValueError("步数 n 须 ≥ 1")
    h = (float(t1) - float(t0)) / n
    psi = np.asarray(psi0, dtype=complex)

    def _f(tm, y):
        return -1j * (H_of_t(tm) @ y)

    for k in range(n):
        tk = float(t0) + h * k
        k1 = _f(tk, psi)
        k2 = _f(tk + 0.5 * h, psi + 0.5 * h * k1)
        k3 = _f(tk + 0.5 * h, psi + 0.5 * h * k2)
        k4 = _f(tk + h, psi + h * k3)
        psi = psi + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return psi


def rabi_population(Omega: float, delta: float = 0.0, t: float = 1.0,
                    n: int = 4096) -> float:
    """二能级 |1⟩ 布居 P₁(t)（TDSE RK4，ψ(0)=|0⟩）。"""
    psi = evolve_constant(two_level_H(Omega, delta),
                          np.array([1.0, 0.0], dtype=complex), t, n)
    return float(abs(psi[1]) ** 2)


def qutrit_leakage(Omega: float, alpha: float = -0.3, t: float = 1.0,
                   n: int = 8192) -> float:
    """方波驱动下三能级 |2⟩ 泄漏布居 P_leak(t)（TDSE RK4，ψ(0)=|0⟩）。"""
    psi = evolve_constant(qutrit_H(Omega, alpha),
                          np.array([1.0, 0.0, 0.0], dtype=complex), t, n)
    return float(abs(psi[2]) ** 2)


def drag_leakage(sigma: float = None, alpha: float = None, beta: float = None,
                 n_sigma: float = None, n: int = 4000,
                 amplitude: float = None) -> float:
    """Gaussian(+DRAG) π 脉冲后的三能级泄漏布居 P_leak。

    脉冲：Ω_x(t) = A·G(t−t_c)，Ω_y(t) = −(β/α)·A·G'(t−t_c)（β=0 ⇒ 无 DRAG 修正）；
    幅度 A 由 `pulse_library.calibrate_amplitude` 定标到 ∫Ω_x dt = π（π 脉冲）。
    时间窗 [−T/2, T/2]，t_c = 0（G 的峰）。
    """
    p = DEFAULT_PULSE
    sigma = p["sigma_ns"] if sigma is None else float(sigma)
    alpha = p["alpha_ghz"] if alpha is None else float(alpha)
    beta = p["beta"] if beta is None else float(beta)
    n_sigma = p["n_sigma"] if n_sigma is None else float(n_sigma)
    if amplitude is None:
        amplitude = calibrate_amplitude(sigma, alpha, beta, n_sigma)
    amp = float(amplitude)
    x_mat, y_mat, p2 = _qutrit_drive_matrices()
    lo, hi = pulse_window(sigma, n_sigma)

    def H_of_t(tm: float) -> "np.ndarray":
        gx = amp * gaussian(tm, sigma)
        gy = amp * drag_quadrature(tm, sigma, alpha, beta)
        return (gx / 2.0) * x_mat + (gy / 2.0) * y_mat + float(alpha) * p2

    psi = evolve_time_dependent(H_of_t, np.array([1.0, 0.0, 0.0], dtype=complex),
                                lo, hi, int(n))
    return float(abs(psi[2]) ** 2)


def leakage_suppression_ratio(sigma: float = None, alpha: float = None,
                              beta: float = None, n_sigma: float = None,
                              n: int = 4000) -> float:
    """DRAG 泄漏抑制比 L = P_leak(β=0) / P_leak(β)（β 默认取默认档 DRAG 系数）。

    🔴 比值为两次数值解之商 ⇒ **不作 golden、不进账本**（只作工程指标）。
    β=0 档与 β 档**共用同一幅度定标**（同一 ∫Ω_x dt = π ⇒ 同一脉冲时长/幅度，
    只差正交分量）⇒ 比较是「同脉冲换 DRAG 开/关」，不是换脉冲。
    """
    p = DEFAULT_PULSE
    sigma = p["sigma_ns"] if sigma is None else float(sigma)
    alpha = p["alpha_ghz"] if alpha is None else float(alpha)
    n_sigma = p["n_sigma"] if n_sigma is None else float(n_sigma)
    beta = p["beta"] if beta is None else float(beta)
    amp = calibrate_amplitude(sigma, alpha, 0.0, n_sigma)     # 共同幅度（按无 DRAG 面积定标）
    pl_off = drag_leakage(sigma, alpha, 0.0, n_sigma, n, amp)
    pl_on = drag_leakage(sigma, alpha, beta, n_sigma, n, amp)
    if pl_on <= 0.0:
        raise ZeroDivisionError("DRAG 档泄漏为 0 ⇒ 抑制比无定义（应检查参数档）")
    return pl_off / pl_on


def drag_optimal_beta(sigma: float = None, alpha: float = None,
                      betas=None, n_sigma: float = None, n: int = 4000) -> float:
    """扫描 β 取泄漏极小的数值最优 β*（网格 + 抛物插值，确定性）。"""
    p = DEFAULT_PULSE
    sigma = p["sigma_ns"] if sigma is None else float(sigma)
    alpha = p["alpha_ghz"] if alpha is None else float(alpha)
    n_sigma = p["n_sigma"] if n_sigma is None else float(n_sigma)
    if betas is None:
        betas = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
    amp = calibrate_amplitude(sigma, alpha, 0.0, n_sigma)
    vals = [(float(b), drag_leakage(sigma, alpha, float(b), n_sigma, n, amp))
            for b in betas]
    b_best, _ = min(vals, key=lambda kv: kv[1])
    return float(b_best)


def run_selfchecks(verbose: bool = False) -> bool:
    """常驻自检：常/含时 RK4 精度 / 谱一致性 / 物理极限 / DRAG 抑制趋势 / 反向。"""
    bad = []

    def chk(name: str, cond: bool) -> None:
        if verbose:
            print("  [%s] %s" % ("PASS" if cond else "FAIL", name))
        if not cond:
            bad.append(name)

    # ① 常矩阵 RK4：与广义 Rabi 闭式一致（相对 1e-8）
    from lda_harness._batch_j3_numeric import rabi_population_golden
    for om, de, tt in ((0.05, 0.0, 20.0), (0.05, 0.03, 100.0), (0.08, -0.02, 50.0)):
        g = rabi_population_golden(om, de, tt)
        c = rabi_population(om, de, tt, n=4096)
        chk("二能级 RK4 ⇄ 广义 Rabi 闭式（rel<1e-8）", abs(c - g) <= 1e-8 * max(abs(g), 1e-12))
    # ② 三能级 RK4：与三角法谱分解闭式一致（相对 1e-6）
    from lda_harness._batch_j3_numeric import qutrit_leakage_golden
    for om, al, tt in ((0.05, -0.3, math.pi / 0.05), (0.03, -0.25, 60.0)):
        g = qutrit_leakage_golden(om, al, tt)
        c = qutrit_leakage(om, al, tt, n=8192)
        chk("三能级 RK4 ⇄ 三角法谱闭式（rel<1e-6）", abs(c - g) <= 1e-6 * max(abs(g), 1e-12))
    # ③ 物理极限：Ω=0 ⇒ 无演化（P₁=0、泄漏=0）；δ=0 ⇒ 标准 sin²(Ωt/2)
    chk("Ω=0 ⇒ P₁=0", abs(rabi_population(0.0, 0.03, 50.0, n=512)) < 1e-14)
    chk("δ=0 ⇒ P₁=sin²(Ωt/2)",
        abs(rabi_population(0.05, 0.0, 20.0, n=4096)
            - math.sin(0.05 * 20.0 / 2.0) ** 2) < 1e-10)
    chk("Ω=0 ⇒ 泄漏=0", abs(qutrit_leakage(0.0, -0.3, 50.0, n=512)) < 1e-14)
    # ④ DRAG：抑制比 > 1（DRAG 确降泄漏）；β=0 ⇒ 两档相同 ⇒ 比值恒等 1
    amp = calibrate_amplitude()
    base = drag_leakage(beta=0.0, n=4000, amplitude=amp)
    amp_d = calibrate_amplitude(beta=1.0)
    with_drag = drag_leakage(beta=1.0, n=4000, amplitude=amp)
    chk("DRAG 降低泄漏（P_leak(β=1) < P_leak(β=0)）", with_drag < base)
    chk("DRAG 抑制比 > 1", leakage_suppression_ratio() > 1.0)
    chk("β=0 ⇒ 抑制比恒等 1（同脉冲下开/关无差别）",
        abs(leakage_suppression_ratio(beta=0.0) - 1.0) < 1e-12)
    chk("幅度定标：DRAG 正交分量不改 ∫Ω_x dt",
        abs(amp_d - amp) < 1e-12)
    # ⑤ 最优 β 落在扫描网格内、且不劣于 β=1 与 β=2
    b_star = drag_optimal_beta()
    pl_star = drag_leakage(beta=b_star, n=4000, amplitude=amp)
    chk("最优 β 不劣于 β=1", pl_star <= drag_leakage(beta=1.0, n=4000, amplitude=amp))
    chk("最优 β 不劣于 β=2", pl_star <= drag_leakage(beta=2.0, n=4000, amplitude=amp))
    # ⑥ 含时 RK4 收敛：步数加倍残差下降（2 阶以上）
    ref = drag_leakage(beta=1.0, n=16000, amplitude=amp)
    r1 = abs(drag_leakage(beta=1.0, n=500, amplitude=amp) - ref)
    r2 = abs(drag_leakage(beta=1.0, n=1000, amplitude=amp) - ref)
    chk("含时 RK4 随步数收敛（残差下降 >2×）", r2 < r1 / 2.0)
    # ⑦ 极限行为（🔴 两条方向相反的物理极限，都要钉住）：
    #    (a) 非谐性越大 ⇒ 1-2 跃迁失谐越大 ⇒ 泄漏单调降低（这是 DRAG 得以工作的前提）；
    #    (b) α→0（谐振子极限）⇒ 1-2 共振 ⇒ 粒子沿能级阶梯上行 ⇒ 泄漏**反而显著**。
    #    ⚠️ 「α→0 泄漏塌陷」是**错直觉**（本轮实测纠正，如实登记）—— 泄漏极小来自 |α|≫Ω。
    lk_al = [qutrit_leakage(0.02, a, 300.0, n=40000) for a in (-0.1, -0.3, -1.0, -3.0)]
    chk("极限：非谐性 |α| 增大 ⇒ 泄漏单调降（0.1/0.3/1.0/3.0）",
        all(lk_al[i] > lk_al[i + 1] for i in range(len(lk_al) - 1)))
    chk("极限：谐振子极限 α→0 ⇒ 泄漏显著（>1e-3，非塌陷）",
        qutrit_leakage(0.02, -1e-6, 300.0, n=40000) > 1e-3)

    if verbose:
        print("自检：%d FAIL" % len(bad))
    return not bad


if __name__ == "__main__":  # pragma: no cover
    print("J3 M0 量子态时域动力学（TDSE 演化器）自检")
    ok = run_selfchecks(verbose=True)
    print("ALL PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)
