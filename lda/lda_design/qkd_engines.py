"""QKD 安全密钥率引擎（v0.9.40 · 方法学扩展 · 死标量锚 S-QKD-SKR）。

本模块是 LDA 研发生产系统里**第一类信息论类锚**（此前全是光子损耗 / 量子保真度
类死标量）。它把「量子密钥分发（QKD）安全密钥率」当作一个**可被公开公式 + 公开
参数独立复现**的死标量，对标公开 datasheet / 论文密钥率量级——属等效验证，非本
团队流片。

物理（Lo–Ma–Chen 2005 / Ma–Qi–Zhao–Qian 2005 decoy-state BB84 渐近下界）：
    R ≥ q · [ Q_1·(1 − H₂(e₁)) − Q_μ·f·H₂(E_μ) ]
  q     = 1/2   BB84 基矢筛选因子
  f     = 误纠错低效（典型 1.1）
  H₂    = 二进制熵
  Q_1   = 单光子增益（信号态 μ）
  e₁    = 单光子误码率（失配 + 背景诱导）
  Q_μ   = 信号态总增益
  E_μ   = 信号态总误码率（QBER）
信道：T(L) = 10^{−(Alice_IL + α·L + Bob_IL)/10}，单光子探测效率 η = T·η_det；
  Y₀ = 2·p_d（双探测器背景产额）；Y₁ = Y₀ + η（单光子产额）。

🟢 红线一致：LLM 不进判决路径；本模块纯解析物理 + 死标量比对；不调 tapeout。
🔴 Q-D67 护栏（方法论扩展版的能量守恒下界）：
  1) 密钥率不得突破单光子贡献上界 R ≤ q·Q₁（漏算误纠错惩罚项 −Q_μ·f·H₂(E_μ)
     或错用 Q_μ 替代 Q₁ 都会突破此界 → 必拦）；
  2) 等效探测效率 η ≤ 1（不得出现超物理透射 / 增益 → 符号或单位错误必拦）。
"""
from __future__ import annotations

import math
from typing import Any, Dict


def binary_entropy(p: float) -> float:
    """二进制熵 H₂(p) = −p·log2(p) − (1−p)·log2(1−p)（p∈[0,1]）。"""
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -p * math.log2(p) - (1.0 - p) * math.log2(1.0 - p)


def _skr_per_pulse(geom: Dict[str, Any]) -> Dict[str, float]:
    """计算 decoy-state BB84 密钥率全部中间量（含 Q-D67 护栏，递归无关）。

    返回 dict：per_pulse / transmittance / eta_det_eff / Y1 / e1 / Q1 / Qmu / Emu。
    护栏触发抛 AssertionError（与 golden_product_benchmarks 的 D-67 同式纪律）。
    注意：本函数**不**计算 max_secure_distance_km，避免与 secure_distance_km 互递归。
    """
    L = float(geom["distance_km"])
    alpha = float(geom.get("fiber_loss_db_km", 0.2))      # 标准 SMF @1550nm 0.2 dB/km
    alice_il = float(geom.get("alice_il_db", 15.0))       # npj QI 2017 Alice 芯片 15 dB
    bob_il = float(geom.get("bob_il_db", 8.0))            # npj QI 2017 Bob 芯片 8 dB
    eta_det = float(geom.get("detector_eff", 0.1))        # InGaAs SPAD ~0.1
    p_d = float(geom.get("dark_count_prob", 1e-6))        # 每脉冲每探测器暗计数
    e_mis = float(geom.get("misalignment", 0.015))        # 系统失配误码
    mu = float(geom.get("mu", 0.5))                        # 信号态强度
    f = float(geom.get("f_ec", 1.1))                       # 误纠错低效
    q = 0.5                                               # BB84 基矢筛选

    # —— 信道 + 探测端总衰减（dB）→ 单光子等效探测效率 η ——
    loss_db = alice_il + alpha * L + bob_il
    T = 10.0 ** (-loss_db / 10.0)        # 源→探测器端（探测器前）透射率
    eta = T * eta_det                    # 单光子探测效率（含探测器）

    Y0 = 2.0 * p_d                       # 背景产额（双探测器）
    Y1 = Y0 + eta                        # 单光子产额
    e1 = e_mis + Y0 / (2.0 * Y1)         # 单光子误码率（失配 + 背景诱导）
    Q1 = mu * math.exp(-mu) * Y1         # 单光子增益
    Qmu = Y0 + eta * mu                  # 信号态总增益
    Emu = (0.5 * Y0 + e1 * mu * math.exp(-mu) * Y1) / Qmu   # 总 QBER

    H1 = binary_entropy(e1)
    Hmu = binary_entropy(Emu)
    # Lo–Ma–Chen 渐近下界（每脉冲）
    skr_per_pulse = q * (Q1 * (1.0 - H1) - Qmu * f * Hmu)

    # 🔴 Q-D67 护栏①：密钥率 ≤ 单光子贡献上界（漏算惩罚项 / 错用 Q_μ 必突破）
    q1_upper = q * Q1
    if skr_per_pulse > q1_upper + 1e-15:
        raise AssertionError(
            f"[QKD] 密钥率 {skr_per_pulse:.3e}/脉冲 超过单光子贡献上界 {q1_upper:.3e} "
            f"（疑似漏算误纠错惩罚项 −Q_μ·f·H₂(E_μ) 或错用 Q_μ 替代 Q₁，见 Q-D67 回归）")
    # 🔴 Q-D67 护栏②：等效探测效率不得超物理（η ≤ 1）
    if eta > 1.0 + 1e-12:
        raise AssertionError(
            f"[QKD] 等效探测效率 η={eta:.3e} > 1（超物理，疑似符号/单位错误，见 Q-D67 回归）")

    return {
        "per_pulse": skr_per_pulse,
        "transmittance": T,
        "eta_det_eff": eta,
        "single_photon_yield": Y1,
        "single_photon_qber": e1,
        "qber": Emu,
        "model": "decoy-BB84-LoMaChen",
    }


def secure_distance_km(geom: Dict[str, Any], hi0: float = 1e4) -> float:
    """求安全密钥率 R(L)=0 的距离上界 L_max（R 随 L 单调递减 → 二分）。

    返回最大安全传输距离（km）。R<0 即该距离不可安全成钥。
    """
    def f_l(L: float) -> float:
        g = dict(geom)
        g["distance_km"] = L
        return _skr_per_pulse(g)["per_pulse"]

    if f_l(0.0) <= 0.0:
        return 0.0
    hi = hi0
    while f_l(hi) > 0.0:
        hi *= 2.0
        if hi > 1e9:
            break
    lo = 0.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if f_l(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    return lo


def decoy_bb84_skr(geom: Dict[str, Any]) -> Dict[str, Any]:
    """QKD 安全密钥率引擎主入口（供 golden 基准 / 设计管线调用）。

    输入几何/工艺参数（dict），输出死标量 dict：
      metric / value            → 主量（secure_key_rate_bps，与 MetricSpec 兼容）
      secure_key_rate_bps       → 安全密钥率（bps）
      max_secure_distance_km    → 最大安全传输距离（km）
      transmittance / eta_det_eff / single_photon_yield / single_photon_qber / qber
    全部为可被公开公式独立复现的死标量；判决纯算术，LLM 不进路径。
    """
    rep_rate = float(geom.get("rep_rate_hz", 1e9))
    core = _skr_per_pulse(geom)
    skr_bps = core["per_pulse"] * rep_rate
    out = dict(core)
    out["secure_key_rate_bps"] = skr_bps
    out["max_secure_distance_km"] = secure_distance_km(geom)
    out["metric"] = "secure_key_rate_bps"
    out["value"] = skr_bps
    return out


if __name__ == "__main__":
    for name, g in {
        "IDQ-Clavis-InGaAs@50km": {"distance_km": 50.0},
        "SNSPD@100km": {"distance_km": 100.0, "detector_eff": 0.85,
                        "dark_count_prob": 1e-8},
    }.items():
        r = decoy_bb84_skr(g)
        print(name, {k: round(v, 4) for k, v in r.items()
                     if k in ("secure_key_rate_bps", "max_secure_distance_km",
                              "transmittance", "eta_det_eff", "qber")})
