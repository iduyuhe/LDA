"""LDA J5 量子网络与接口征程 · **M4 量子-经典接口**（G-QNET-5）能力层。

═══ 本模块定位 ═══
M4 回答「**经典控制电子学的时间精度（时钟抖动）如何限制量子操作的保真度**」——
这是量子网络里「量子-经典边界」的直接体现：量子比特的每一次门操作都由经典
微波/激光脉冲驱动，脉冲的定时误差 ⇒ 相位误差 ⇒ 保真损失。

═══ 🔴 净增 0 如实登记（本档不立锚）═══════════════════════════════════════════
章程 §2 ⑤ / §5 R8 明示：「经典接口**易工程参数充数** ⇒ **无物理律者一律归 smoke**」。
经**实 grep 全仓 BENCHMARK_DEFS** + **三组数值实测**（见 `_AVOIDANCE` 与
`negative_evidence()`），本档**如实登记净增 0**，理由三条：

  ① **结构邻接 B475**（`spin_echo_phase_variance` = 自旋回波相位方差）——
     与「噪声 → 相位方差」共享**普遍结构**；且 `lda_l2/qs_m2.coherent_chi` 已实现
     「噪声谱 × CPMG 滤波函数 → 相干积分」的完整链路（同源结构）。
  ② **格式邻接 B522**（微波-光换能 η = 有限探测带内**洛伦兹型积分** ⇄ 复合 Simpson）——
     本档若改用「有限带宽洛伦兹积分」则与 B522 **同数值格式**。
  ③ **实测否决**（三证据）：
     · 洛伦兹抖动谱 ⇒ 被积函数 1/f² 尾部慢收敛 ⇒ 残差随网格 **停滞**
       （m=128/256/512 残差恒 2.124e-3、比值恒 1.00）—— 指纹「与离散参数无关」
       = **非离散误差**（技能血案：残差与离散参数无关 ⇒ 不是精度问题）。
     · 高斯抖动谱 ⇒ 被积函数光滑指数衰减 ⇒ 数值积分**精确到机器精度**
       （m≥64 残差**恰 0.0**）⇒「精确量不可锚」⇒ 判据 D「粗端浮出双精度地板」不成立。
     · CPMG 滤波为**振荡**函数 ⇒ 复合 **Simpson 粗端非单调**（B520 同型血案）。

⇒ 交付物降为**能力层 + 总装 + WebUI 面板**（不进判决路径、不进账本）。
**纪律**：不硬做、不虚报（同 J4 M1/M2 · J5 M2 的先例）。

═══ 物理链（能力层实现 · 解析闭式）════════════════════════════════════════════
  抖动自相关 `C_t(τ)` → 相位方差 `σ_φ²` → 保真度 `F = exp(−σ_φ²/2)`

  ① 白噪声抖动（无相关，`τ_c → 0`）：
       σ_φ² = Ω²·σ_t²·Σ_p a_p²            （a_p = CPMG 时序系数）
  ② 指数相关（洛伦兹谱，相关时间 τ_c）：
       σ_φ² = Ω²·σ_t²·Σ_{p,q} a_p a_q · e^{−|t_p−t_q|/τ_c}
  ③ 高斯相关（高斯谱）：
       σ_φ² = Ω²·σ_t²·Σ_{p,q} a_p a_q · e^{−((t_p−t_q)/τ_c)²}

  CPMG-N 时序（**与 `qs_m2.cpmg_filter` 同一时序定义**）：
      t_j = (2j−1)·t/(2n)，t_0 = 0，t_{n+1} = t
  把 `qs_m2.cpmg_filter` 的 `y = Σ_j (−1)^j(e^{iωt_{j+1}} − e^{iωt_j})` 展开为
  `Σ_p a_p e^{iωt_p}` ⇒ `a_0 = −1` · `a_k = 2(−1)^{k−1}(1≤k≤n)` · `a_{n+1} = (−1)^n`，
  且 `Σ_p a_p = 0`（⇔ CPMG 恒重聚 DC 噪声，自洽校验）。

  观测标量 = **保真损失** `1 − F`（无量纲）。

🔴 本模块**复用** `qs_m2.cpmg_filter`（章程 §4 M4 复用列）：`cpmg_filter_times()`
   与 `cpmg_filter()` 共用同一时序定义，并有逐点对拍自检。
🔴 零量子 SDK（不依赖 Qiskit/Cirq/PennyLane/QuTiP）；LLM 不进判决路径。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

from lda_l2.qs_m2 import cpmg_filter

TWO_PI = 2.0 * math.pi

#: 口径串（对外账本用）
QNET_CLASSICAL_CALIBER = "clock_jitter_pulse_infidelity__unitless"

# ── 设计示例默认档（🔴 与 WebUI case 卡同源 · J4 血案）──────────────────────
DEFAULT_OMEGA_RABI_RAD_S = TWO_PI * 1.0e6     # 拉比频率 1 MHz ⇒ 脉冲相位灵敏度 Ω
DEFAULT_SIGMA_T_S = 20.0e-9                    # RMS 时钟抖动 20 ns
DEFAULT_TAU_C_S = 1.0e-6                       # 抖动相关时间 1 μs
DEFAULT_SEQ_TIME_S = 4.0e-6                    # 脉冲序列总时长 4 μs
DEFAULT_N_PULSES = 8                           # CPMG-N 脉冲数

#: 🔴 净增 0 避让登记表（对外可查）
_AVOIDANCE: Dict[str, Dict[str, str]] = {
    "B475": {
        "title": "自旋回波（Hahn echo）相位方差",
        "kind": "结构邻接（同一普遍结构：噪声 → 相位方差）",
        "分歧": "噪声源（磁噪声单色 vs 经典时钟抖动谱）· 被测标量（相位方差 ⟨Φ²⟩ vs 保真损失 1−F）",
        "结论": "结构同源 ⇒ 不可计新锚",
    },
    "qs_m2.coherent_chi": {
        "title": "相干积分 χ(t)=(1/π)∫S(ω)·F_n(ω,t)/ω²dω（幂律噪声谱 × CPMG 滤波）",
        "kind": "结构邻接（非锚 · 能力层函数）",
        "分歧": "噪声谱形式（幂律 vs 洛伦兹/高斯）",
        "结论": "既有实现已覆盖「噪声谱 × CPMG 滤波 → 积分」链路 ⇒ 新锚无方法学增量",
    },
    "B522": {
        "title": "微波-光换能效率 η（有限探测带内洛伦兹型积分 ⇄ 复合 Simpson）",
        "kind": "格式邻接（同一数值格式：洛伦兹型积分 ⇄ 复合 Simpson）",
        "分歧": "被积函数（两洛伦兹乘积 vs 洛伦兹×振荡滤波）",
        "结论": "若改用「有限带宽洛伦兹积分」则与 B522 同格式 ⇒ 不可计新锚",
    },
}

#: 三组数值实测（负结果取证）
_NEGATIVE_EVIDENCE: Dict[str, str] = {
    "E1_lorentz_tail": (
        "洛伦兹抖动谱：残差随网格**停滞**（m=32→512: 4.349e-02 → 1.148e-02 → 2.123e-03 → "
        "2.124e-03 → 2.124e-03，比值 3.79/5.41/**1.00/1.00**）⇒ 指纹「与离散参数无关」= 非离散误差"),
    "E2_gauss_exact": (
        "高斯抖动谱：被积函数光滑指数衰减 ⇒ 数值积分精确（m≥64 残差**恰 0.0**）⇒ "
        "判据 D「粗端浮出双精度地板」不成立 ⇒ 属「精确量不可锚」"),
    "E3_simpson_osc": (
        "CPMG 滤波为振荡函数 ⇒ 复合 Simpson 粗端**非单调**（同 B520 血案）"),
}


# ══════════════════════════════════════════════════════════════════════
# ① CPMG 时序与系数（复用 qs_m2 时序定义 + 逐点对拍）
# ══════════════════════════════════════════════════════════════════════
def cpmg_filter_times(t: float, n: int) -> List[float]:
    """CPMG-N 脉冲时序 t_j = (2j−1)·t/(2n)，t_0=0，t_{n+1}=t（与 `qs_m2.cpmg_filter` 同定义）。

    🔴 对拍自检：`cpmg_filter_times` 应与 `qs_m2.cpmg_filter` 内部时序逐位一致
       （本模块的闭式展开即建立在该时序上）。
    """
    if n < 1:
        raise ValueError("CPMG 脉冲数 n 必须 ≥ 1")
    tau = t / n
    return [0.0] + [(2.0 * j - 1.0) * tau / 2.0 for j in range(1, n + 1)] + [float(t)]


def cpmg_coefficients(n: int) -> List[float]:
    """把 `qs_m2.cpmg_filter` 的 `y = Σ_j (−1)^j(e^{iωt_{j+1}} − e^{iωt_j})` 展开为 Σ a_p e^{iωt_p}。

    a_0 = −1 · a_k = 2(−1)^{k−1}(1 ≤ k ≤ n) · a_{n+1} = (−1)^n
    🔴 自洽校验：Σ_p a_p = 0（⇔ CPMG 恒重聚 DC 噪声；`cpmg_filter(ω→0)=0`）。
    """
    if n < 1:
        raise ValueError("CPMG 脉冲数 n 必须 ≥ 1")
    a = [-1.0]
    a.extend(2.0 * ((-1.0) ** (k - 1)) for k in range(1, n + 1))
    a.append(float((-1.0) ** n))
    return a


def _assert_dc_null(n: int) -> None:
    if abs(sum(cpmg_coefficients(n))) > 1e-12:
        raise AssertionError("Σa_p ≠ 0 ⇒ CPMG 系数展开有误（DC 未被重聚）")


# ══════════════════════════════════════════════════════════════════════
# ② 相位方差（三种抖动相关模型的解析闭式）
# ══════════════════════════════════════════════════════════════════════
def phase_variance(omega_rabi: float = DEFAULT_OMEGA_RABI_RAD_S,
                   sigma_t: float = DEFAULT_SIGMA_T_S,
                   tau_c: float = DEFAULT_TAU_C_S,
                   t: float = DEFAULT_SEQ_TIME_S,
                   n: int = DEFAULT_N_PULSES,
                   kernel: str = "lorentz") -> float:
    """时钟抖动诱导的**脉冲相位方差** `σ_φ²`（rad² · 解析闭式）。

    `σ_φ² = Ω²·σ_t²·Σ_{p,q} a_p a_q · C(Δt_{pq})`，`C` 由抖动相关模型给定：
      · `"lorentz"`（指数相关）：`C(τ)=e^{−|τ|/τ_c}`（洛伦兹谱，工程常用）
      · `"gauss"`（高斯相关）：`C(τ)=e^{−(τ/τ_c)²}`
      · `"white"`（无相关）：`C(τ)=δ_{pq}` ⇒ `σ_φ²=Ω²σ_t²Σ_p a_p²`

    🔴 **为何用解析闭式而非数值积分**：本档已实测「数值积分不可靠」（见
       `negative_evidence()`：洛伦兹谱尾部慢收敛 / 高斯谱积分精确 ⇒ 两侧均
       无法建立判据 D 窗口）。⇒ 本函数**只作能力层估计**，**不进判决路径**。
    """
    if n < 1:
        raise ValueError("CPMG 脉冲数 n 必须 ≥ 1")
    if sigma_t < 0.0 or tau_c <= 0.0 or t <= 0.0 or omega_rabi < 0.0:
        raise ValueError("物理参数须满足 σ_t ≥ 0 · τ_c > 0 · t > 0 · Ω ≥ 0")
    _assert_dc_null(n)

    a = cpmg_coefficients(n)
    ts = cpmg_filter_times(t, n)
    if kernel == "white":
        s = sum(ap * ap for ap in a)
    else:
        if kernel not in ("lorentz", "gauss"):
            raise ValueError("kernel 须为 'lorentz' / 'gauss' / 'white'")
        s = 0.0
        for p in range(len(ts)):
            for q in range(len(ts)):
                dt = abs(ts[p] - ts[q])
                if kernel == "lorentz":
                    s += a[p] * a[q] * math.exp(-dt / tau_c)
                else:
                    s += a[p] * a[q] * math.exp(-((dt / tau_c) ** 2))
    return (omega_rabi ** 2) * (sigma_t ** 2) * s


def pulse_fidelity(sigma_phi2: float) -> float:
    """高斯退相位近似下的脉冲保真度 `F = exp(−σ_φ²/2)`（无量纲）。"""
    if sigma_phi2 < 0.0:
        raise ValueError("相位方差须 ≥ 0")
    return float(math.exp(-0.5 * float(sigma_phi2)))


def jitter_limited_fidelity(omega_rabi: float = DEFAULT_OMEGA_RABI_RAD_S,
                            sigma_t: float = DEFAULT_SIGMA_T_S,
                            tau_c: float = DEFAULT_TAU_C_S,
                            t: float = DEFAULT_SEQ_TIME_S,
                            n: int = DEFAULT_N_PULSES,
                            kernel: str = "lorentz") -> float:
    """时钟抖动限制的 CPMG-N 脉冲序列保真度 `F`（无量纲）。"""
    return pulse_fidelity(phase_variance(omega_rabi, sigma_t, tau_c, t, n, kernel))


def jitter_infidelity(omega_rabi: float = DEFAULT_OMEGA_RABI_RAD_S,
                      sigma_t: float = DEFAULT_SIGMA_T_S,
                      tau_c: float = DEFAULT_TAU_C_S,
                      t: float = DEFAULT_SEQ_TIME_S,
                      n: int = DEFAULT_N_PULSES,
                      kernel: str = "lorentz") -> float:
    """**保真损失** `1 − F`（本档观测标量 · 无量纲）。"""
    return 1.0 - jitter_limited_fidelity(omega_rabi, sigma_t, tau_c, t, n, kernel)


def cpmg_suppression_ratio(t: float = DEFAULT_SEQ_TIME_S,
                           n: int = DEFAULT_N_PULSES,
                           tau_c: float = DEFAULT_TAU_C_S,
                           omega_rabi: float = DEFAULT_OMEGA_RABI_RAD_S,
                           sigma_t: float = DEFAULT_SIGMA_T_S) -> float:
    """CPMG-N 相对自由进动（FID · 无脉冲）的相位方差比 `<1 即序列更优`。

    🔴 **物理**：CPMG 只抑制**低频**噪声（`τ_c ≫ t` ⇒ 比 < 1）；
       对**白噪声**（`τ_c → 0`）多脉冲反而各段累积独立抖动
       ⇒ 比 = `Σa_p²/2 = (4n+2)/2`（n=8 ⇒ **17.0**）—— 与 `qs_m2.cpmg_filter` 在
       高 ω 不衰减（`F_n ~ O(n²)`）互为印证。
    🔴 FID 基线系数 = `[−1, +1]` ⇒ `Σa_p² = 2`（**不可漏因子 2**）。
    """
    v_fid = 2.0 * (omega_rabi ** 2) * (sigma_t ** 2)
    v_cpmg = phase_variance(omega_rabi, sigma_t, tau_c, t, n)
    if v_fid == 0.0:
        return 0.0
    return float(v_cpmg / v_fid)


# ══════════════════════════════════════════════════════════════════════
# ③ 报告 / 避让 / 负结果取证
# ══════════════════════════════════════════════════════════════════════
def negative_evidence() -> Dict[str, str]:
    """三组数值实测的负结果（本档「不立锚」的**实测依据**）。"""
    return dict(_NEGATIVE_EVIDENCE)


def avoidance_table() -> Dict[str, Dict[str, str]]:
    """净增 0 的避让登记表（逐条列既有锚/实现 + 邻接类型 + 分歧 + 结论）。"""
    return {k: dict(v) for k, v in _AVOIDANCE.items()}


def jitter_report(omega_rabi: float = DEFAULT_OMEGA_RABI_RAD_S,
                  sigma_t: float = DEFAULT_SIGMA_T_S,
                  tau_c: float = DEFAULT_TAU_C_S,
                  t: float = DEFAULT_SEQ_TIME_S,
                  n: int = DEFAULT_N_PULSES) -> Dict[str, Any]:
    """五段口径的经典接口报告（能力层 · 不进判决路径）。"""
    sig2 = phase_variance(omega_rabi, sigma_t, tau_c, t, n)
    f = pulse_fidelity(sig2)
    return {
        "caliber": QNET_CLASSICAL_CALIBER,
        "omega_rabi_rad_s": float(omega_rabi),
        "sigma_t_s": float(sigma_t),
        "tau_c_s": float(tau_c),
        "seq_time_s": float(t),
        "n_pulses": int(n),
        "phase_variance_rad2": float(sig2),
        "fidelity": float(f),
        "infidelity": float(1.0 - f),
        "cpmg_suppression_ratio": cpmg_suppression_ratio(t, n, tau_c, omega_rabi, sigma_t),
        "verdict": "ACCEPT" if sig2 < 1.0 else "REVIEW",
    }


def selfcheck_qnet_classical() -> Dict[str, bool]:
    """能力层自检（含与 `qs_m2` 的复用对拍 + 三模型极限自洽）。"""
    checks: Dict[str, bool] = {}

    # ① DC 重聚：Σa_p = 0（各 n）
    checks["dc_null_all_n"] = all(
        abs(sum(cpmg_coefficients(nn))) < 1e-12 for nn in (1, 2, 3, 8, 16))

    # ② 与 qs_m2.cpmg_filter 逐点对拍（复用验证：|Σa_p e^{iωt_p}|² ≡ cpmg_filter）
    def _manual(w, t, n):
        a = cpmg_coefficients(n)
        ts = cpmg_filter_times(t, n)
        re = sum(ap * math.cos(w * tp) for ap, tp in zip(a, ts))
        im = sum(ap * math.sin(w * tp) for ap, tp in zip(a, ts))
        return re * re + im * im

    checks["matches_qs_m2_cpmg_filter"] = all(
        abs(_manual(w, 4e-6, 8) - cpmg_filter(w, 4e-6, 8))
        <= 1e-12 * max(1.0, cpmg_filter(w, 4e-6, 8))
        for w in (1e3, 1e5, 1e6, 1e7, 4e7))

    # ③ 白噪声档 = Ω²σ_t²Σa_p²（恒等式）
    sig2_white = phase_variance(sigma_t=20e-9, n=8, kernel="white")
    a8 = cpmg_coefficients(8)
    checks["white_identity"] = bool(
        abs(sig2_white - (TWO_PI * 1e6) ** 2 * (20e-9) ** 2 * sum(x * x for x in a8)) < 1e-30)

    # ④ τ_c → 0 极限：洛伦兹档 → 白噪声档
    sig2_tiny_tau = phase_variance(sigma_t=20e-9, tau_c=1e-15, n=8, kernel="lorentz")
    checks["tau_c_to_zero_equals_white"] = bool(abs(sig2_tiny_tau - sig2_white) < 1e-6 * sig2_white)

    # ⑤ τ_c → ∞ 极限：洛伦兹档 → 0（全相关 ⇒ CPMG 完全重聚）
    sig2_big_tau = phase_variance(sigma_t=20e-9, tau_c=1e6, n=8, kernel="lorentz")
    checks["tau_c_to_inf_vanishes"] = bool(abs(sig2_big_tau) < 1e-12)

    # ⑥ 保真度单调递减于 σ_t
    checks["fidelity_monotone_in_jitter"] = bool(
        jitter_limited_fidelity(sigma_t=10e-9) > jitter_limited_fidelity(sigma_t=40e-9))

    # ⑦ F ∈ (0,1] 且 1−F 恒等
    f0 = jitter_limited_fidelity()
    checks["fidelity_range_and_identity"] = bool(0.0 < f0 <= 1.0
                                                 and abs((1.0 - f0) - jitter_infidelity()) < 1e-15)

    # ⑧ CPMG 的两侧物理：白噪声档累积更多（=Σa²/2=17）· 低频档抑制（<1）
    checks["cpmg_amplifies_white_noise"] = bool(
        abs(cpmg_suppression_ratio(tau_c=1e-12) - sum(x * x for x in cpmg_coefficients(8)) / 2.0)
        < 1e-6)
    checks["cpmg_suppresses_low_freq"] = bool(cpmg_suppression_ratio(tau_c=1e-2) < 1.0)

    # ⑨ 非法参数抛 ValueError（先校验再计算）
    def _raises(fn):
        try:
            fn(); return False
        except ValueError:
            return True

    checks["reverse_bad_n_raises"] = _raises(lambda: phase_variance(n=0))
    checks["reverse_bad_tau_raises"] = _raises(lambda: phase_variance(tau_c=0.0))
    checks["reverse_bad_kernel_raises"] = _raises(lambda: phase_variance(kernel="nope"))
    checks["reverse_bad_sigma2_raises"] = _raises(lambda: pulse_fidelity(-1.0))

    # ⑩ 避让表 + 负结果齐备（对外可查）
    checks["avoidance_table_complete"] = (
        set(avoidance_table()) == {"B475", "qs_m2.coherent_chi", "B522"}
        and len(negative_evidence()) == 3)

    return checks


def main() -> int:  # pragma: no cover
    print("J5 M4 量子-经典接口能力层（抖动 → 保真损失）· 净增 0 如实登记")
    sc = selfcheck_qnet_classical()
    bad = 0
    for k, v in sc.items():
        print("  [%s] %s" % ("PASS" if v else "FAIL", k))
        if not v:
            bad += 1
    r = jitter_report()
    print("\n  相位方差 σ_φ² = %.6e rad²" % r["phase_variance_rad2"])
    print("  保真度 F      = %.12f" % r["fidelity"])
    print("  保真损失 1−F  = %.6e" % r["infidelity"])
    print("  CPMG 抑制比    = %.6f" % r["cpmg_suppression_ratio"])
    print("  签核          = %s" % r["verdict"])
    print("\n避让登记：%s" % ", ".join(avoidance_table()))
    print("负结果取证：%d 条" % len(negative_evidence()))
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
