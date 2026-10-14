"""J3 量子测控与读出征程 · M0 脉冲库（驱动脉冲包络 + 面积/幅度定标 · 能力层）。

🔴 主权纪律：本模块是**能力验证**模块（门禁 `run_j3_ctrl_smoke` 覆盖），**不是账本锚**；
纯标准库（`math`），零第三方依赖，全确定性。与账本锚（B1+）零重叠、各司其职。

提供（驱动脉冲层）：
  · `gaussian(t, sigma)` / `gaussian_derivative(t, sigma)`：高斯包络与其时间导数。
  · `drag_quadrature(t, sigma, alpha, beta)`：**DRAG 正交分量**
        Ω_y(t) = −(β/α)·dΩ_x/dt
    （DRAG = derivative removal by adiabatic gate：用包络导数抵消三能级泄漏，
      β 为可调系数，β=1 为标准值；transmon α<0 ⇒ Ω_y 与 dΩ_x/dt 同号）。
  · `pulse_window(sigma, n_sigma)`：脉冲时间窗（±n_sigma·σ 截断）。
  · `sample_drive(...)`：采样 (t_k, Ω_x(t_k), Ω_y(t_k)) 三序列。
  · `pulse_area(times, amps)`：脉冲面积 ∫Ω dt（复合梯形）。
  · `calibrate_amplitude(..., target_area)`：**幅度定标**——给定包络形状，反解使
    ∫Ω dt = target_area（π 脉冲 ⇒ target_area = π）的幅度系数。
  · `frequency_band_ok(f01_ghz)`：S 铁律① **频率限带守护**（f01 ∈ [5.0, 6.2] GHz，复用口径）。

🔴 诚实边界：
  · 本模块只做**脉冲形状与面积的闭式/数值定标**（纯数学 + 信号处理），**不含**
    量子态演化（演化在 `lda_qeda/qubit_dynamics.py`）；
  · σ / α / β / 幅度均为**设计示例量级**（非实测 PDK / 非任意波形发生器标定数据）；
  · DRAG 的泄漏抑制效果**只在三能级数值演化中体现**（`qubit_dynamics.leakage_suppression_ratio`），
    本模块不宣称抑制比；
  · 只证「包络/面积/定标链条自洽」，**不作制造/性能宣称**，不报能效/TOPS/fJ-op。
红线：纯标准库 · 零量子 SDK · LLM 不进判决路径 · 阈值为设计规则。
"""
from __future__ import annotations

import math

__all__ = [
    "BAND_LO_GHZ",
    "BAND_HI_GHZ",
    "DEFAULT_PULSE",
    "gaussian",
    "gaussian_derivative",
    "drag_quadrature",
    "pulse_window",
    "sample_drive",
    "pulse_area",
    "calibrate_amplitude",
    "frequency_band_ok",
    "run_selfchecks",
]

#: S 铁律① 频率限带（与 J2 `physical_error_model` 同口径，设计规则 · 可覆盖）
BAND_LO_GHZ = 5.0
BAND_HI_GHZ = 6.2

#: 默认脉冲设计参数（设计示例量级 · 非实测 PDK）
DEFAULT_PULSE = {
    "sigma_ns": 5.0,      # 高斯包络标准差（ns）
    "n_sigma": 4.0,       # 时间窗截断（±n_sigma·σ）
    "beta": 1.0,          # DRAG 系数（1.0 为标准值）
    "alpha_ghz": -0.3,    # transmon 非谐性 α（rad/ns，负）
    "n_samples": 4001,    # 采样点数
}


def gaussian(t: float, sigma: float) -> float:
    """高斯包络 G(t) = exp(−t²/(2σ²))（峰值 1，峰在 t=0）。"""
    if sigma <= 0.0:
        raise ValueError("σ 须 > 0")
    return math.exp(-(float(t) ** 2) / (2.0 * float(sigma) ** 2))


def gaussian_derivative(t: float, sigma: float) -> float:
    """高斯包络时间导数 dG/dt = −(t/σ²)·G(t)。"""
    return -(float(t) / (float(sigma) ** 2)) * gaussian(t, sigma)


def drag_quadrature(t: float, sigma: float, alpha: float,
                    beta: float = 1.0) -> float:
    """DRAG 正交分量 Ω_y(t) = −(β/α)·dΩ_x/dt（Ω_x 取单位幅度高斯）。

    α 为 transmon 非谐性（负）⇒ −β/α > 0 ⇒ Ω_y 与 dΩ_x/dt 同号（标准 DRAG 约定）。
    """
    if alpha == 0.0:
        raise ValueError("α=0 无泄漏通道 ⇒ DRAG 无定义")
    return -(float(beta) / float(alpha)) * gaussian_derivative(t, float(sigma))


def pulse_window(sigma: float, n_sigma: float = 4.0):
    """脉冲时间窗 (−T/2, +T/2)，T = 2·n_sigma·σ（峰在 0）。"""
    if n_sigma <= 0.0:
        raise ValueError("n_sigma 须 > 0")
    half = float(n_sigma) * float(sigma)
    return -half, half


def sample_drive(sigma: float = None, alpha: float = None, beta: float = None,
                 n_sigma: float = None, n_samples: int = None):
    """采样驱动脉冲：返回 (times, omega_x, omega_y) 三列表（单位幅度）。

    时间网格等距覆盖脉冲窗 [−T/2, T/2]，T = 2·n_sigma·σ。
    """
    p = DEFAULT_PULSE
    sigma = p["sigma_ns"] if sigma is None else float(sigma)
    alpha = p["alpha_ghz"] if alpha is None else float(alpha)
    beta = p["beta"] if beta is None else float(beta)
    n_sigma = p["n_sigma"] if n_sigma is None else float(n_sigma)
    n_samples = p["n_samples"] if n_samples is None else int(n_samples)
    if n_samples < 3:
        raise ValueError("采样点数须 ≥ 3")
    lo, hi = pulse_window(sigma, n_sigma)
    step = (hi - lo) / float(n_samples - 1)
    ts = [lo + step * k for k in range(n_samples)]
    gx = [gaussian(t, sigma) for t in ts]
    gy = [drag_quadrature(t, sigma, alpha, beta) for t in ts]
    return ts, gx, gy


def pulse_area(times, amps) -> float:
    """脉冲面积 ∫Ω dt（复合梯形，等距网格）。"""
    n = len(times)
    if n < 2 or len(amps) != n:
        raise ValueError("times/amps 长度须一致且 ≥ 2")
    h = (times[-1] - times[0]) / float(n - 1)
    acc = 0.5 * (amps[0] + amps[-1])
    for k in range(1, n - 1):
        acc += amps[k]
    return acc * h


def calibrate_amplitude(sigma: float = None, alpha: float = None, beta: float = None,
                        n_sigma: float = None, n_samples: int = None,
                        target_area: float = math.pi) -> float:
    """幅度定标：使 ∫ A·G(t) dt = target_area 的幅度 A（π 脉冲 ⇒ target_area = π）。

    面积 ∝ 幅度（线性）⇒ A* = target_area / ∫G dt（解析一步，无迭代）。
    """
    ts, gx, _gy = sample_drive(sigma, alpha, beta, n_sigma, n_samples)
    unit_area = pulse_area(ts, gx)
    if unit_area <= 0.0:
        raise ValueError("单位幅度面积须 > 0")
    return float(target_area) / unit_area


def frequency_band_ok(f01_ghz: float, lo: float = BAND_LO_GHZ,
                      hi: float = BAND_HI_GHZ) -> bool:
    """S 铁律① 频率限带守护：f01 落在 [lo, hi] GHz 内。"""
    return bool(lo <= float(f01_ghz) <= hi)


def run_selfchecks(verbose: bool = False) -> bool:
    """常驻自检：包络/导数闭式 / DRAG 反号 / 面积线性 / 定标反解 / 限带二值。"""
    bad = []

    def chk(name: str, cond: bool) -> None:
        if verbose:
            print("  [%s] %s" % ("PASS" if cond else "FAIL", name))
        if not cond:
            bad.append(name)

    sig = 5.0
    # ① 高斯包络：峰值 1、对称、单调衰减、σ 处恰 e^{−1/2}
    chk("G(0)=1", abs(gaussian(0.0, sig) - 1.0) < 1e-15)
    chk("G 对称", abs(gaussian(3.0, sig) - gaussian(-3.0, sig)) < 1e-15)
    chk("G(σ)=e^{−1/2}", abs(gaussian(sig, sig) - math.exp(-0.5)) < 1e-15)
    chk("G 单调衰减", gaussian(0.0, sig) > gaussian(sig, sig) > gaussian(3 * sig, sig))
    # ② 导数：dG/dt(0)=0、奇对称、极小点在 t=σ
    chk("dG/dt(0)=0", abs(gaussian_derivative(0.0, sig)) < 1e-15)
    chk("dG/dt 奇对称",
        abs(gaussian_derivative(2.0, sig) + gaussian_derivative(-2.0, sig)) < 1e-15)
    chk("|dG/dt| 极小点在 σ",
        abs(gaussian_derivative(sig, sig)) > abs(gaussian_derivative(0.5 * sig, sig))
        and abs(gaussian_derivative(sig, sig)) > abs(gaussian_derivative(2 * sig, sig)))
    # ③ DRAG：α<0 ⇒ Ω_y 与 dG/dt 同号（−β/α>0）；β→0 ⇒ Ω_y→0
    chk("DRAG 与 dG/dt 同号（α<0）",
        drag_quadrature(3.0, sig, -0.3) * gaussian_derivative(3.0, sig) > 0.0)
    chk("DRAG(β=0)=0", abs(drag_quadrature(3.0, sig, -0.3, 0.0)) < 1e-15)
    chk("DRAG ∝ β", abs(drag_quadrature(3.0, sig, -0.3, 2.0)
                        - 2.0 * drag_quadrature(3.0, sig, -0.3, 1.0)) < 1e-15)
    # ④ 面积：线性于幅度；窗截断面积 → √(2π)σ（n_sigma→∞ 极限）
    ts, gx, gy = sample_drive()
    area1 = pulse_area(ts, gx)
    area2 = pulse_area(ts, [2.0 * v for v in gx])
    chk("面积线性于幅度", abs(area2 - 2.0 * area1) < 1e-12)
    analytic_full = math.sqrt(2.0 * math.pi) * sig
    ts_w, gx_w, _ = sample_drive(n_sigma=12.0, n_samples=20001)
    chk("窗截断面积 → √(2π)σ（rel<1e-12）",
        abs(pulse_area(ts_w, gx_w) - analytic_full) / analytic_full < 1e-12)
    # ⑤ 定标反解：A*·∫G dt 恰 == target_area
    amp = calibrate_amplitude(target_area=math.pi)
    chk("定标反解自洽（A*·∫G = π）",
        abs(amp * area1 - math.pi) < 1e-12)
    chk("幅度正有限", math.isfinite(amp) and amp > 0.0)
    # ⑥ 限带守护二值
    chk("限带：带内 True", frequency_band_ok(5.5) is True)
    chk("限带：越界 False",
        frequency_band_ok(4.5) is False and frequency_band_ok(6.5) is False)

    if verbose:
        print("自检：%d FAIL" % len(bad))
    return not bad


if __name__ == "__main__":  # pragma: no cover
    print("J3 M0 脉冲库（驱动包络 + 面积/幅度定标）自检")
    ok = run_selfchecks(verbose=True)
    print("ALL PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)
