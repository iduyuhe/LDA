"""B33 探测器带宽锚（A 档闭式/行为层有源 · v0.9.67）。

物理：pin / APD 光电探测器 3dB 带宽受负载 R 与反偏结电容 C 限制（RC 低通）。

golden（design_rule_anchor，确定性物理定律闭式）：
    C    = ε·A/d            （反偏 PN 结耗尽电容，ε = ε_r·ε0）
    f_3dB = 1 / (2π·R·C)

candidate（independent_cross_check）：RC 一阶暂态 V(t)=V0(1−e^{−t/τ}) 时域
    数值积分（梯形法）+ 最小二乘拟合 τ ⇒ f_3dB = 1/(2π·τ)。与闭式方法学独立
    （数值 ODE 拟合 vs 解析公式），判据 D 真数值离散化（n_time 加密→残差收敛）。

红线自检：纯电路闭式 + 数值积分，**无光子有源物理、无载流子动力学、无 TCAD、
无 A 级工具** ⇒ 不破「三不做 / 主权 / 验证纪律」任何一条红线。

诚实边界：本锚基础部分仅覆盖 PIN 的 RC 限制带宽，**不含**渡越时间 / 暗电流
（那些属 B 档禁区）。**APD 行为层扩展（b33_apd_*）**：纯闭式 Miller 增益
M=1/(1−V/V_br)^n + 增益带宽折减 √M，属 textbook 行为层，**不含**雪崩输运 /
过剩噪声 / 渡越时间分布（雪崩动力学整体留 B 档禁区）。标 "RC-limited / APD behavioral only"。
LLM 不进判决路径。
"""
import math


def _junction_capacitance(eps: float, A: float, d: float) -> float:
    """反偏 PN 结耗尽电容闭式 C = ε·A/d（F）。"""
    return eps * A / d


def b33_detector_bandwidth(R: float = 50.0, eps: float = 1.036e-10,
                            A: float = 9.653e-9, d: float = 1.0e-6) -> float:
    """探测器 3dB 带宽 f_3dB（Hz，确定性物理定律闭式）。

    f_3dB = 1/(2π·R·C)，C = ε·A/d（反偏结电容）。
    默认参数 → C≈1pF, R=50Ω ⇒ f_3dB≈3.18 GHz（RC-limited，典型 pin 量级）。
    """
    C = _junction_capacitance(eps, A, d)
    return 1.0 / (2.0 * math.pi * R * C)


def b33_rc_bandwidth_candidate(R: float = 50.0, eps: float = 1.036e-10,
                                A: float = 9.653e-9, d: float = 1.0e-6,
                                n_time: int = 2000) -> float:
    """B33 独立候选：RC 暂态时域数值积分 + 最小二乘拟合 τ。

    golden = f_3dB = 1/(2π·R·C)（解析闭式）；
    cand   = 模拟 V(t)=V0(1−e^{−t/τ})（τ=R·C，梯形法数值积分），
            对 ln(V0−V) 做线性拟合得斜率 −1/τ ⇒ f_3dB=1/(2π·τ)。
    判据 D 真数值离散化：n_time 2→512，拟合误差随步长收敛（梯形法 O(dt²)）。
    默认值 n_time=2000 ⇒ 基线残差 ~1e-5（≫1e-12 噪声地板，双向可标定）。

    ⚠️ 失败即抛异常上浮，绝不静默回退（IndependentCandidateRouter 既定原则）。
    """
    tau = R * _junction_capacitance(eps, A, d)  # 物理时间常数（秒）
    if tau <= 0.0 or n_time < 2:
        raise ValueError("B33 candidate: tau<=0 或 n_time<2")
    V0 = 1.0
    T_max = 5.0 * tau                      # 覆盖到 ~99.3% 上升
    dt = T_max / n_time
    # 梯形法积分 dV/dt = (V0−V)/τ（A-稳定，2 阶）
    V = 0.0
    ts, vs = [], []
    for _ in range(1, n_time + 1):
        t = _ * dt
        V = ((V * (1.0 - dt / (2.0 * tau)) + (dt / tau) * V0)
             / (1.0 + dt / (2.0 * tau)))
        ts.append(t)
        vs.append(V)
    # 线性拟合 ln(V0−V) = ln(V0) − t/τ ⇒ slope = −1/τ
    sx = sy = sxx = sxy = 0.0
    n = 0
    for t, v in zip(ts, vs):
        if v <= 0.0 or v >= V0:
            continue
        y = math.log(V0 - v)
        sx += t
        sy += y
        sxx += t * t
        sxy += t * y
        n += 1
    if n < 2:
        raise RuntimeError("B33 candidate: 拟合数据不足（梯形积分退化）")
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-300:
        raise RuntimeError("B33 candidate: 拟合退化")
    slope = (n * sxy - sx * sy) / denom      # = −1/τ_est
    tau_est = -1.0 / slope
    if tau_est <= 0.0:
        raise RuntimeError("B33 candidate: τ_est 非正（拟合异常）")
    return float(1.0 / (2.0 * math.pi * tau_est))


def b33_detector_bandwidth_report(R: float = 50.0, eps: float = 1.036e-10,
                                   A: float = 9.653e-9, d: float = 1.0e-6) -> dict:
    g = b33_detector_bandwidth(R, eps, A, d)
    C = _junction_capacitance(eps, A, d)
    return {
        "metric": "f3dB_Hz",
        "value": g,
        "note": (f"RC 限制探测器 3dB 带宽 f_3dB=1/(2π·R·C)，C=ε·A/d。R={R}Ω, "
                 f"C≈{C * 1e12:.3f}pF ⇒ f_3dB≈{g / 1e9:.3f}GHz（仅 RC 限制，"
                 f"不含渡越时间/暗电流/APD 倍增——B 档禁区）。golden=确定性"
                 f"物理定律闭式；候选=RC 暂态梯形法数值积分+拟合，判据 D 真收敛。"),
    }


# ============================================================
# APD 扩展（T1-C W1 · 闭式倍增扩展，雪崩动力学留 B 档）
# ============================================================

def _apd_miller_gain(V_bias: float, V_br: float, n_miller: float = 3.0) -> float:
    """APD 雪崩倍增因子 M（Miller 闭式）。V_bias 须 < V_br，否则击穿。"""
    if V_bias >= V_br or n_miller <= 0.0:
        raise ValueError("APD 雪崩击穿区：须 V_bias<V_br 且 n_miller>0")
    x = 1.0 - V_bias / V_br
    if x <= 0.0:
        raise ValueError("APD 雪崩击穿区：1 − V/V_br ≤ 0")
    return 1.0 / (x ** n_miller)


def b33_apd_bandwidth(R: float = 50.0, eps: float = 1.036e-10, A: float = 9.653e-9,
                      d: float = 1.0e-6, V_bias: float = 22.0, V_br: float = 25.0,
                      n_miller: float = 3.0) -> float:
    """APD 3dB 带宽 f_3dB（Hz，确定性物理定律闭式 · A 档行为层）。

    f_3dB = 1/(2π·R·C·√M)，C=ε·A/d，M=1/(1−V/V_br)^n（Miller）。
    APD 增益带宽积经验律 f·M^0.5≈const ⇒ 带宽按 √M 折减（Si textbook）。
    纯电路/经验闭式，**无光子有源物理、无载流子动力学、无 TCAD、无 A 级工具**
    ⇒ 不破「三不做 / 主权 / 验证纪律」任何一条红线。
    诚实边界：本扩展为 APD 行为层闭式（Miller 增益 + 增益带宽折减），
    **不含**雪崩输运 / 过剩噪声 / 渡越时间分布（那些属 B 档禁区）。标 "APD behavioral only"。
    """
    C = _junction_capacitance(eps, A, d)
    M = _apd_miller_gain(V_bias, V_br, n_miller)
    return 1.0 / (2.0 * math.pi * R * C * math.sqrt(M))


def b33_apd_bandwidth_candidate(R: float = 50.0, eps: float = 1.036e-10,
                                A: float = 9.653e-9, d: float = 1.0e-6,
                                V_bias: float = 22.0, V_br: float = 25.0,
                                n_miller: float = 3.0, n_time: int = 2000) -> float:
    """B33-APD 独立候选：APD 等效一阶暂态 V(t)=M(1−e^{−t/τ_apd}) 时域数值积分
    + 最小二乘拟合 τ_apd ⇒ f_3dB=1/(2π·τ_apd)。

    golden = f_3dB = 1/(2π·R·C·√M)（Miller 闭式）；
    cand   = 模拟 APD 阶跃响应（DC 增益 M，时间常数 τ_apd=R·C·√M），
            对 ln(M−V) 线性拟合得 τ_apd ⇒ f=1/(2π·τ_apd)。
    与闭式方法学独立（数值积分拟合 vs 解析公式），判据 D 真数值离散化
    （n_time 加密→拟合残差单调收敛）。
    ⚠️ 失败即抛异常上浮，绝不静默回退。
    """
    C = _junction_capacitance(eps, A, d)
    M = _apd_miller_gain(V_bias, V_br, n_miller)
    tau = R * C * math.sqrt(M)          # APD 等效时间常数（秒）
    if tau <= 0.0 or n_time < 2:
        raise ValueError("B33-APD candidate: tau<=0 或 n_time<2")
    T_max = 5.0 * tau
    dt = T_max / n_time
    V = 0.0
    ts, vs = [], []
    for _ in range(1, n_time + 1):
        t = _ * dt
        # 一阶 RC 型更新（A-稳定）
        V = ((V * (1.0 - dt / (2.0 * tau)) + (dt / tau) * M)
             / (1.0 + dt / (2.0 * tau)))
        ts.append(t)
        vs.append(V)
    sx = sy = sxx = sxy = 0.0
    n = 0
    for t, v in zip(ts, vs):
        if v <= 0.0 or v >= M:
            continue
        y = math.log(M - v)
        sx += t
        sy += y
        sxx += t * t
        sxy += t * y
        n += 1
    if n < 2:
        raise RuntimeError("B33-APD candidate: 拟合数据不足")
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-300:
        raise RuntimeError("B33-APD candidate: 拟合退化")
    slope = (n * sxy - sx * sy) / denom     # = −1/τ_est
    tau_est = -1.0 / slope
    if tau_est <= 0.0:
        raise RuntimeError("B33-APD candidate: τ_est 非正")
    return float(1.0 / (2.0 * math.pi * tau_est))


def b33_apd_report(R: float = 50.0, eps: float = 1.036e-10, A: float = 9.653e-9,
                   d: float = 1.0e-6, V_bias: float = 22.0, V_br: float = 25.0,
                   n_miller: float = 3.0) -> dict:
    g = b33_apd_bandwidth(R, eps, A, d, V_bias, V_br, n_miller)
    C = _junction_capacitance(eps, A, d)
    M = _apd_miller_gain(V_bias, V_br, n_miller)
    return {
        "metric": "f3dB_Hz_APD",
        "value": g,
        "note": (f"APD 3dB 带宽 f_3dB=1/(2π·R·C·√M)，C=ε·A/d，"
                 f"M=1/(1−V/V_br)^{n_miller}。R={R}Ω, C≈{C*1e12:.3f}pF, "
                 f"M≈{M:.3f} ⇒ f_3dB≈{g/1e9:.3f}GHz"
                 f"（Miller 增益带宽折减 √M；APD 行为层闭式，雪崩动力学留 B 档）。"),
    }
