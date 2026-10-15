# -*- coding: utf-8 -*-
"""J5 量子网络与接口征程 · **M1 能力层：纠缠源 / 光子不可分辨性**（`qnet_source`）。

定位：M0（`qnet_channel` + `qnet_distribution`）解决**信道侧**「分发后纠缠还剩多少」；
      本层解决**源侧**「两个光子到底有多不可分辨」—— 光子频率/时间不匹配会**直接限制
      纠缠交换的干涉质量**，是纠缠源可用性的第一个判据（缺口 **G-QNET-2**）。

物理链（三环）：
  ① 波包重叠幅度   `M = ∫ψ₁*(t)ψ₂(t)dt`，`ψ_i(t) ∝ (2πσ_i²)^{−1/4}·exp(−(t−t_i)²/(4σ_i²))·exp(−iω_i t)`
  ② HOM 可见度     `V = |M|²`（闭式 σ₁=σ₂=σ：`V = exp(−δt²/(4σ²))·exp(−δω²σ²)`）
  ③ 不可分辨度     `1 − V`（V→1 完全不可分辨 ⇒ HOM dip 最深）

🔴 **与 `lda_qeda/loqc_states.py` 既有族的边界（防同源）**：既有 `hom_coincidence` /
  `hom_visibility(theta)` 的**自变量是分束器角度 θ**（假设两光子**完全不可区分**）；
  本层自变量是**波包参数（δt / δω）**——「光子有多不可分辨」这一维，既有族**完全没有**。
  ⇒ 不同物理量（承 B452↔B33 先例）。

🔴 **诚实边界**：σ / δt / δω 为**设计示例量级**（非实测光谱）；只建模两个理想高斯波包
  （未含真实 NV 发射线型、腔滤波、探测器时间抖动、多光子成分）⇒ 只支撑预算与量级，
  **不作性能宣称**。零商业依赖（纯 `math`）。
"""

from __future__ import annotations

import math
from typing import Dict

__all__ = [
    "QNET_SOURCE_CALIBER",
    "DEFAULT_PACKET_SIGMA_S",
    "DEFAULT_DELAY_S",
    "DEFAULT_DW_RAD_S",
    "overlap_magnitude_sq",
    "hom_visibility",
    "indistinguishability",
    "hom_dip_depth_db",
    "source_report",
    "selfcheck_qnet_source",
]

QNET_SOURCE_CALIBER = "photon_indistinguishability__hom_visibility__unitless"

#: 波包宽度 σ（s · 设计示例 1 ps）
DEFAULT_PACKET_SIGMA_S = 1.0e-12
#: 时间延迟 δt（s · 取 2σ）
DEFAULT_DELAY_S = 2.0e-12
#: 频率差 δω（rad/s · 取 1/σ）
DEFAULT_DW_RAD_S = 1.0e12


def overlap_magnitude_sq(delay_s: float = DEFAULT_DELAY_S,
                         dw_rad_s: float = DEFAULT_DW_RAD_S,
                         packet_sigma_s: float = DEFAULT_PACKET_SIGMA_S) -> float:
    """② 波包重叠幅度平方（闭式 · σ₁=σ₂=σ）：

        `V = |M|² = exp(−δt²/(4σ²)) · exp(−δω²σ²)`

    （通式 `[2σ₁σ₂/(σ₁²+σ₂²)]·exp(−δt²/(2(σ₁²+σ₂²)))·exp(−2δω²σ₁²σ₂²/(σ₁²+σ₂²))`。）
    """
    s = float(packet_sigma_s)
    if s <= 0.0:
        raise ValueError("波包宽度 σ 须 > 0")
    return float(math.exp(-float(delay_s) ** 2 / (4.0 * s * s))
                 * math.exp(-float(dw_rad_s) ** 2 * s * s))


def hom_visibility(delay_s: float = DEFAULT_DELAY_S,
                   dw_rad_s: float = DEFAULT_DW_RAD_S,
                   packet_sigma_s: float = DEFAULT_PACKET_SIGMA_S) -> float:
    """① ② **HOM 干涉可见度** `V = |M|²`（两光子不可分辨性越高 ⇒ V 越大）。"""
    return overlap_magnitude_sq(delay_s, dw_rad_s, packet_sigma_s)


def indistinguishability(delay_s: float = DEFAULT_DELAY_S,
                         dw_rad_s: float = DEFAULT_DW_RAD_S,
                         packet_sigma_s: float = DEFAULT_PACKET_SIGMA_S) -> float:
    """③ **不可分辨度** `1 − V`（V=1 ⇒ 0，完全可分辨 ⇒ 1）。"""
    return float(1.0 - hom_visibility(delay_s, dw_rad_s, packet_sigma_s))


def hom_dip_depth_db(delay_s: float = DEFAULT_DELAY_S,
                     dw_rad_s: float = DEFAULT_DW_RAD_S,
                     packet_sigma_s: float = DEFAULT_PACKET_SIGMA_S) -> float:
    """HOM dip 深度（dB）：`−10·log₁₀(1 − V)`（V→1 ⇒ 深度 → ∞）。"""
    v = hom_visibility(delay_s, dw_rad_s, packet_sigma_s)
    if v >= 1.0:
        raise ValueError("V ≥ 1 ⇒ dip 深度无界（不可分辨度过高）")
    return float(-10.0 * math.log10(1.0 - v))


def source_report(delay_s: float = DEFAULT_DELAY_S,
                  dw_rad_s: float = DEFAULT_DW_RAD_S,
                  packet_sigma_s: float = DEFAULT_PACKET_SIGMA_S) -> Dict[str, float]:
    """纠缠源汇总（只读 · 闭式现算 · 零重计算）。"""
    s = float(packet_sigma_s)
    v = hom_visibility(delay_s, dw_rad_s, s)
    # 使 V 跌破 1/2 的临界延迟（δω=0 时）：exp(−δt²/(4σ²))=1/2 ⇒ δt = 2σ√(ln2)
    dt_half = 2.0 * s * math.sqrt(math.log(2.0))
    return {
        "packet_sigma_s": s,
        "delay_s": float(delay_s),
        "delay_in_sigma": float(delay_s) / s,
        "dw_rad_s": float(dw_rad_s),
        "dw_times_sigma": float(dw_rad_s) * s,
        "hom_visibility": v,
        "indistinguishability": float(1.0 - v),
        "dip_depth_db": hom_dip_depth_db(delay_s, dw_rad_s, s),
        "half_visibility_delay_s": float(dt_half),
        "half_visibility_delay_in_sigma": float(dt_half / s),
    }


def selfcheck_qnet_source() -> Dict[str, bool]:
    """纠缠源能力层自检。"""
    checks: Dict[str, bool] = {}

    # 零延迟 + 零频差 ⇒ 完全不可分辨（V=1）
    checks["perfect_overlap_is_unity"] = bool(abs(hom_visibility(0.0, 0.0) - 1.0) < 1e-15)
    # 单调性
    checks["visibility_monotone_decreasing_in_delay"] = bool(
        hom_visibility(0.0) > hom_visibility(1.0e-12) > hom_visibility(3.0e-12))
    checks["visibility_monotone_decreasing_in_dw"] = bool(
        hom_visibility(2.0e-12, 0.0) > hom_visibility(2.0e-12, 5.0e11)
        > hom_visibility(2.0e-12, 2.0e12))
    # 半可见度延迟闭式
    r = source_report()
    dt_half = r["half_visibility_delay_s"]
    checks["half_visibility_closed_form"] = bool(
        abs(hom_visibility(dt_half, 0.0) - 0.5) < 1e-12)
    # 与数值核同律（闭式逐位）
    try:
        from lda_harness import _batch_j5_numeric as J5
        checks["matches_b520_golden"] = bool(
            abs(J5.hom_visibility_golden() - hom_visibility()) < 1e-15)
    except Exception:
        checks["matches_b520_golden"] = False
    # 不可分辨度互补
    checks["indistinguishability_complements"] = bool(
        abs(indistinguishability() + hom_visibility() - 1.0) < 1e-15)

    def _raises(fn):
        try:
            fn()
            return False
        except ValueError:
            return True

    checks["reverse_bad_sigma_raises"] = _raises(lambda: hom_visibility(1e-12, 0.0, 0.0))
    checks["reverse_dip_depth_unbounded_raises"] = _raises(
        lambda: hom_dip_depth_db(0.0, 0.0))

    return checks


def main() -> int:
    sc = selfcheck_qnet_source()
    for k, v in sc.items():
        print("  [%s] %s" % ("PASS" if v else "FAIL", k))
    bad = sum(1 for v in sc.values() if not v)
    print("qnet_source 自检：%d PASS / %d FAIL" % (len(sc) - bad, bad))
    r = source_report()
    print("  σ=%.1f ps · δt=%.1fσ · δω·σ=%.2f ⇒ V=%.12g · 1−V=%.6g · 半可见延迟=%.4fσ"
          % (r["packet_sigma_s"] * 1e12, r["delay_in_sigma"], r["dw_times_sigma"],
             r["hom_visibility"], r["indistinguishability"],
             r["half_visibility_delay_in_sigma"]))
    return 1 if bad else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
