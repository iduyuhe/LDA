# -*- coding: utf-8 -*-
"""J5 量子网络与接口征程 · **第 0 号动作：公里级信道层**（`qnet_channel`）。

定位：J1–J4 全部建模「芯片内 / 实验室距离」；本层**第一次引入公里级距离**这一维度，
      是 J5 全部上层锚的**前置基础设施**（章程 §3.1）。

物理链（三件 · 全部教科书闭式）：
  ① 光纤衰减      `T(L) = 10^{−α·L_km/10}`（α 单位 dB/km）
     · 衰减长度    `L_att = 10/(α·ln10)·1000` [m]
  ② 偏振去相干    `p(L) = exp(−L/L_depol)`（退极化信道保留的相干度 · 指数律）
  ③ Werner 保真度 `F(p) = (1 + 3p)/4`（Bell 对角态经退极化 · 教科书闭式）

🔴 **独立验证纪律**：本层物理律**不可直接被上层当 golden 用**；其「闭式 ⇄ 数值」互备
   在本模块自检内完成（`selfcheck_qnet_channel`：①分段乘积 ⇄ 整体闭式 ②指数律的
   RK4 步进 ⇄ 闭式）⇒ 先自证，再被引用。

🔴 **与既有锚的边界（同源体检实证 · 2026-10-15 实 grep `BENCHMARK_DEFS`）**：
  · `werner` = **0 命中**；`entangl|bell|EPR|concurrence|CHSH|teleport` 在锚定义内 **0 命中**
    （唯一近邻为 `part1.py:221` 的「EPR 哈密顿量对角化(pyEPR/Ansys)仅作外部 ORACLE」文本，**非锚**）。
  · 🔴 `kraus` 已被 **B453**（`coherent_loss_fidelity` · 相干态经损耗通道 · **静态 Fock 截断
    Kraus 算子求和**）占用 ⇒ 本行程候选**一律避开 Kraus 求和格式**，改用「**距离步进 Liouvillian**」
    （数值格式分歧，见 B519）。
  · `fiber` 命中为 **阶跃光纤 LP01 模式有效折射率**锚（part5 · `fiber_lp01_neff_fd`）⇒ 那是
    **模式本征值求解**，与「信道损耗 / 保真度」**物理量不同**。

🔴 **诚实边界**：α=0.2 dB/km / L_depol / L 均为**设计示例 / 公开典型值**，非任何实测链路；
   本层只支撑预算与量级，不作性能宣称。零商业依赖（纯 `math`）。
"""

from __future__ import annotations

import math
from typing import Dict

__all__ = [
    "QNET_CHANNEL_CALIBER",
    "DEFAULT_ALPHA_DB_PER_KM",
    "DEFAULT_L_DEPOL_M",
    "DEFAULT_LINK_LENGTH_M",
    "transmission",
    "attenuation_length_m",
    "polarization_coherence",
    "werner_fidelity",
    "series_coherence_length",
    "link_fidelity",
    "channel_report",
    "selfcheck_qnet_channel",
]

#: 口径串（本层所有量：衰减·相干度·保真度均为**无量纲**；长度为 m）
QNET_CHANNEL_CALIBER = "fiber_channel__attenuation_depolarization_fidelity__unitless_or_SI"

#: 公开典型单模光纤 1550 nm 衰减（dB/km · 设计示例）
DEFAULT_ALPHA_DB_PER_KM = 0.2
#: 偏振去相干长度（m · 设计示例，与 L_att 同量级）
DEFAULT_L_DEPOL_M = 2.2e4
#: 链路长度（m · 设计示例 100 km）
DEFAULT_LINK_LENGTH_M = 1.0e5

_LN10 = math.log(10.0)


def transmission(length_m: float, alpha_db_per_km: float = DEFAULT_ALPHA_DB_PER_KM) -> float:
    """① 光纤**透射率**（无量纲 · 闭式）：`T(L) = 10^{−α·L_km/10}`。

    α 单位 dB/km ⇒ 链路损耗 dB = α·(L/1000) ⇒ 功率透射 = 10^{−dB/10}。
    """
    if length_m < 0.0:
        raise ValueError("长度须 ≥ 0")
    if alpha_db_per_km < 0.0:
        raise ValueError("衰减系数须 ≥ 0")
    return float(10.0 ** (-alpha_db_per_km * (length_m / 1000.0) / 10.0))


def attenuation_length_m(alpha_db_per_km: float = DEFAULT_ALPHA_DB_PER_KM) -> float:
    """① 衰减长度 `L_att`（m）：使 `T = e^{−1}` 的距离 ⇒ `L_att = 10/(α·ln10)·1000`。"""
    if alpha_db_per_km <= 0.0:
        raise ValueError("衰减系数须 > 0（L_att 无穷大无意义）")
    return float(10.0 / (alpha_db_per_km * _LN10) * 1000.0)


def polarization_coherence(length_m: float, l_depol_m: float = DEFAULT_L_DEPOL_M) -> float:
    """② 偏振**保留相干度**（无量纲 · 闭式）：`p(L) = exp(−L/L_depol)`。"""
    if l_depol_m <= 0.0:
        raise ValueError("去相干长度须 > 0")
    if length_m < 0.0:
        raise ValueError("长度须 ≥ 0")
    return float(math.exp(-length_m / l_depol_m))


def werner_fidelity(p: float) -> float:
    """③ **Werner 族保真度**（无量纲 · 闭式）：`F(p) = (1 + 3p)/4`。

    Bell 对角态 `ρ = p|Φ+⟩⟨Φ+| + (1−p)·I/4` 对理想 `|Φ+⟩` 的保真度。
    p=1 ⇒ F=1（理想）；p=0 ⇒ F=1/4（完全混态）。
    """
    if not (0.0 <= p <= 1.0):
        raise ValueError("p 须落在 [0, 1]")
    return float((1.0 + 3.0 * p) / 4.0)


def series_coherence_length(l_att_m: float, l_depol_m: float) -> float:
    """**串联有效相干长度**（m）：`1/L_eff = 1/L_att + 1/L_depol`（率相加）。"""
    if l_att_m <= 0.0 or l_depol_m <= 0.0:
        raise ValueError("两长度均须 > 0")
    return float(1.0 / (1.0 / l_att_m + 1.0 / l_depol_m))


def link_fidelity(length_m: float = DEFAULT_LINK_LENGTH_M,
                  l_depol_m: float = DEFAULT_L_DEPOL_M) -> float:
    """端到端**分发后保真度**（无量纲）：`F(L) = (1 + 3·exp(−L/L_depol))/4`。"""
    return werner_fidelity(polarization_coherence(length_m, l_depol_m))


def channel_report(length_m: float = DEFAULT_LINK_LENGTH_M,
                   alpha_db_per_km: float = DEFAULT_ALPHA_DB_PER_KM,
                   l_depol_m: float = DEFAULT_L_DEPOL_M) -> Dict[str, float]:
    """信道层汇总（只读 · 闭式现算）。"""
    l_att = attenuation_length_m(alpha_db_per_km)
    p = polarization_coherence(length_m, l_depol_m)
    return {
        "length_m": float(length_m),
        "length_km": float(length_m / 1000.0),
        "alpha_db_per_km": float(alpha_db_per_km),
        "attenuation_length_m": l_att,
        "transmission": transmission(length_m, alpha_db_per_km),
        "link_loss_db": float(alpha_db_per_km * (length_m / 1000.0)),
        "l_depol_m": float(l_depol_m),
        "coherence_p": p,
        "fidelity": werner_fidelity(p),
        "series_coherence_length_m": series_coherence_length(l_att, l_depol_m),
    }


def _rk4_exponential(length_m: float, l_depol_m: float, n: int) -> float:
    """数值验证：`dp/dL = −p/L_depol` 的 **RK4** 步进（与闭式指数律方法学独立）。"""
    h = length_m / n
    p = 1.0

    def f(v):
        return -v / l_depol_m

    for _ in range(n):
        k1 = f(p)
        k2 = f(p + 0.5 * h * k1)
        k3 = f(p + 0.5 * h * k2)
        k4 = f(p + h * k3)
        p = p + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return float(p)


def selfcheck_qnet_channel() -> Dict[str, bool]:
    """信道层自检（先自证，后被引用）。"""
    checks: Dict[str, bool] = {}

    l_att = attenuation_length_m(0.2)
    checks["l_att_matches_public_typical"] = bool(abs(l_att - 21714.7240952) < 1e-3)

    # ① 分段乘积 ⇄ 整体闭式（方法学独立）
    n = 1000
    seg = 1.0
    for _ in range(n):
        seg *= transmission(1.0e5 / n, 0.2)
    checks["transmission_segments_eq_closed"] = bool(
        abs(seg - transmission(1.0e5, 0.2)) < 1e-15)

    # ② 指数律：RK4 步进 ⇄ 闭式（真离散残差，粗端浮出地板）
    closed = polarization_coherence(1.0e5, 2.2e4)
    coarse = _rk4_exponential(1.0e5, 2.2e4, 8)
    fine = _rk4_exponential(1.0e5, 2.2e4, 512)
    checks["rk4_coarse_has_real_residual"] = bool(abs(coarse - closed) > 1e-12)
    checks["rk4_fine_converges_to_closed"] = bool(abs(fine - closed) < 1e-9)
    checks["rk4_residual_monotone"] = bool(
        abs(coarse - closed) > abs(_rk4_exponential(1.0e5, 2.2e4, 64) - closed)
        > abs(fine - closed))

    # ③ Werner 边界
    checks["werner_p1_is_one"] = bool(abs(werner_fidelity(1.0) - 1.0) < 1e-15)
    checks["werner_p0_is_quarter"] = bool(abs(werner_fidelity(0.0) - 0.25) < 1e-15)

    # ④ 端到端保真度落在 (1/4, 1)
    f = link_fidelity()
    checks["link_fidelity_in_open_interval"] = bool(0.25 < f < 1.0)

    # ⑤ 串联有效长度 < 两个分量的较小者
    l_eff = series_coherence_length(l_att, 2.2e4)
    checks["series_length_less_than_min"] = bool(l_eff < min(l_att, 2.2e4))

    # ⑥ 单调性：L 越大保真度越低
    checks["fidelity_monotone_decreasing"] = bool(
        link_fidelity(1.0e4) > link_fidelity(1.0e5) > link_fidelity(5.0e5))

    # ⑦ 反向：非法输入必抛
    def _raises(fn):
        try:
            fn()
            return False
        except (ValueError, ZeroDivisionError):
            return True

    checks["reverse_bad_alpha_raises"] = _raises(lambda: attenuation_length_m(0.0))
    checks["reverse_bad_p_raises"] = _raises(lambda: werner_fidelity(1.5))
    checks["reverse_negative_length_raises"] = _raises(lambda: transmission(-1.0))
    checks["reverse_bad_depol_raises"] = _raises(lambda: polarization_coherence(1.0, 0.0))

    return checks


def main() -> int:
    sc = selfcheck_qnet_channel()
    for k, v in sc.items():
        print("  [%s] %s" % ("PASS" if v else "FAIL", k))
    bad = sum(1 for v in sc.values() if not v)
    print("qnet_channel 自检：%d PASS / %d FAIL" % (len(sc) - bad, bad))
    r = channel_report()
    print("  L=%.1f km ⇒ loss=%.2f dB · T=%.6g · p=%.6g · F=%.12g"
          % (r["length_km"], r["link_loss_db"], r["transmission"],
             r["coherence_p"], r["fidelity"]))
    return 1 if bad else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
