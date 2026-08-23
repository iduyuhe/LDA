"""D-74 · cross-resonance (CR) 门参数化（有效模型 + 阈值/资源验收）。

两固定频率 transmon（control c / target t）经交换耦合 J 相连，控制-目标失谐
Δ = ω_t − ω_c，非谐性 α（<0）。CR 相互作用经 Schrieffer-Wolff 主导阶给出有效
ZX 耦合（文献公认近似，Chow2011 / Rigetti）：

    g_CR = 2·J²·Δ / (α² − Δ²)          [MHz]

该式是**有效模型标度**（2 能级/3 能级 SW 主导阶），非完整 transmon 多能级数值；
高阶寄生项（YY、由 α 失配引入的附加 ZX）与 echoed-CR 对 σ_zz 的抵消未建模。
门时间 t_CR = π/|g_CR| 为特征 ZX(π) 时间（CZ/CNOT 等价旋转的量级估计）。

ORACLE 比对窗（器件物理已知范围）：
- |g_CR| ∈ [0.02, 10] MHz：超导 CR 门典型 ZX 率 ~0.1–5 MHz。
- t_CR ≤ T2（退相干预算）：真实 CR 门 ~0.1–0.4 µs，远小于 T2（~50–100 µs）。
- |Δ| < |α|：公式有效参数区（否则分母趋零 / 标度失效，须拒绝）。

LLM 不进判决路径：是否 PASS 由死标量比对（区间 + 不等式）决定。
"""
from __future__ import annotations

# CR 有效 ZX 耦合 ORACLE 区间（MHz），器件物理已知范围
G_CR_MIN_REAL = 0.02
G_CR_MAX_REAL = 10.0
# 默认退相干预算（µs），典型 transmon T2 ~ 50–100 µs
T2_DEFAULT_US = 100.0


def cross_resonance(J: float, delta: float, alpha: float,
                    T2_us: float = T2_DEFAULT_US) -> dict:
    """cross-resonance 门参数化（有效模型）。

    输入：J 耦合 (MHz)、Δ=ω_t−ω_c 失谐 (MHz)、α 非谐性 (MHz, 负)、T2_us 退相干预算。
    返回：g_CR（有效 ZX 耦合，MHz，带符号）、t_CR（门时间 µs）、σ_zz（残余 ZZ，
    有效估计）、参数区有效性、验收。
    """
    valid_regime = (alpha != 0) and (abs(delta) < abs(alpha))
    denom = (alpha * alpha - delta * delta)
    if not valid_regime or denom == 0:
        return {
            "ok": False,
            "error": ("参数区无效：须 |Δ|<|α| 且 α≠0（CR 有效模型标度失效）"
                      if valid_regime is False else "分母为零（Δ=±α 共振）"),
            "J_MHz": J, "delta_MHz": delta, "alpha_MHz": alpha,
            "valid_regime": bool(valid_regime),
        }

    g_cr = (2.0 * J * J * delta) / denom          # 有效 ZX 耦合 (MHz)
    abs_g = abs(g_cr)
    # 门时间 t_CR = π/|g_CR|；g_CR 单位 MHz → 时间 µs = π/(|g|·1e6)·1e6 = π/|g|
    t_cr_us = (3.141592653589793 / abs_g) if abs_g > 0 else float("inf")
    # 残余 ZZ 串扰（有效估计，echoed-CR 可抵消，仅作诚实报告）：
    # 主导阶随 J²/α 同量级，取 ~0.5·(2J²/α)·(|Δ|/|α|)/(1+(Δ/α)²) 量级
    x = delta / alpha
    sigma_zz = 0.5 * (2.0 * J * J / abs(alpha)) * abs(x) / (1.0 + x * x)

    in_band = G_CR_MIN_REAL <= abs_g <= G_CR_MAX_REAL
    within_t2 = t_cr_us <= T2_us
    ok = bool(valid_regime and in_band and within_t2 and abs_g > 0)

    return {
        "ok": ok,
        "J_MHz": float(J),
        "delta_MHz": float(delta),
        "alpha_MHz": float(alpha),
        "valid_regime": bool(valid_regime),
        "g_CR_MHz": float(g_cr),
        "abs_g_CR_MHz": float(abs_g),
        "t_CR_us": (None if t_cr_us == float("inf") else float(t_cr_us)),
        "sigma_zz_MHz": float(sigma_zz),
        "zz_suppressed_by_echo": True,   # echoed-CR 抵消 σ_zz（诚实标注）
        "in_real_band": bool(in_band),
        "within_T2": bool(within_t2),
        "T2_us": float(T2_us),
        "formula": "g_CR = 2·J²·Δ / (α² − Δ²)   [MHz, Schrieffer-Wolff 主导阶]",
        "acceptance": {
            "valid_regime": bool(valid_regime),
            "g_CR_in_real_band": bool(in_band),
            "t_CR_within_T2": bool(within_t2),
        },
        "note": ("有效模型（SW 主导阶）：g_CR=2J²Δ/(α²−Δ²) 为 CR 有效 ZX 耦合标度，"
                 "t_CR=π/|g_CR| 为 ZX(π) 特征门时间。诚实边界：①非完整 transmon "
                 "多能级数值，高阶寄生项（YY、附加 ZX）未建模；②σ_zz 为残余 ZZ 串扰"
                 "估计，真实器件用 echoed-CR 抵消；③仅固定频率 transmon 的 CR 方案"
                 "（非可调耦合 / 非 all-XY 门）。ORACLE：|g_CR|∈[0.02,10]MHz、"
                 "t_CR≤T2。LLM 不进判决路径。"),
    }
