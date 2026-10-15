# -*- coding: utf-8 -*-
"""J5 量子网络与接口征程 · **M0 能力层：纠缠分发**（`qnet_distribution`）。

定位：把 `qnet_channel`（第 0 号动作 · 公里级信道层）的**信道输出**接到**纠缠质量**上 ——
      即「多节点量子网络」的第一个可用性判据（章程 §4 · 缺口 G-QNET-1）。

物理链（四环）：
  ① 信道传输        `qnet_channel.channel_report()` ⇒ 透射率 T / 保留相干度 p
  ② Werner 参数     `p(L) = exp(−L/L_depol)`（退极化信道）
  ③ 分发保真度      `F(L) = (1 + 3p)/4`（B519 锚 · `_batch_j5_numeric` 同律）
  ④ 纠缠可用性判据  `F > (1+3/√2)/4 ≈ 0.78033`（Bell 不等式违反阈值；Werner 族 CHSH `S = 2√2·p = 2√2·(4F−1)/3`，`S > 2` ⟺ `p > 1/√2` ⟺ `F > (1+3/√2)/4`）

🔴 **诚实边界（与 B519 note 一致）**：L / L_depol / α 均为**公开典型值 / 设计示例**（非实测链路）；
   只建模**单一退极化通道**（未含双折射随机游走、光纤非线性、探测器暗计数、存储-检索损耗）
   ⇒ 只支撑预算与量级，**不作性能宣称**。零商业依赖（纯 `math`；复用 `qnet_channel`）。

🔴 **同源边界**：`werner` / `entangl|bell|EPR|concurrence|CHSH|teleport` 在锚定义内 **0 命中**；
   🔴 `kraus` 已被 **B453** 占用 ⇒ 本层候选一律走**距离步进 Liouvillian**（见 `_batch_j5_numeric`）。
"""

from __future__ import annotations

import math
from typing import Dict

from lda_l2 import qnet_channel as CH

__all__ = [
    "QNET_DISTRIBUTION_CALIBER",
    "BELL_VIOLATION_THRESHOLD_F",
    "werner_parameter",
    "distribution_fidelity",
    "chsh_parameter",
    "violates_bell",
    "distribution_report",
    "selfcheck_qnet_distribution",
]

QNET_DISTRIBUTION_CALIBER = "entanglement_distribution__werner_fidelity__unitless"

#: Bell 不等式违反阈值（以**保真度 F** 表述）：Werner 族 `p > 1/√2` ⟺ `F > (1+3/√2)/4 ≈ 0.78033`
#: 🔴 注意：`p`（Werner 参数）与 `F`（保真度）**不是同一个量** —— `F = (1+3p)/4`；
#: 因此阈值写成 F 时是 **0.78033**，而非教科书中常见的「p 阈值 1/√2」（误混即真 bug）。
BELL_VIOLATION_THRESHOLD_F = (1.0 + 3.0 / math.sqrt(2.0)) / 4.0


def werner_parameter(length_m: float, l_depol_m: float = CH.DEFAULT_L_DEPOL_M) -> float:
    """Werner 参数 = 信道保留相干度 `p(L) = exp(−L/L_depol)`。"""
    return CH.polarization_coherence(length_m, l_depol_m)


def distribution_fidelity(length_m: float,
                          l_depol_m: float = CH.DEFAULT_L_DEPOL_M) -> float:
    """② ③ 分发后两体纠缠保真度 `F(L) = (1 + 3p(L))/4`（与 B519 锚同律）。"""
    return CH.werner_fidelity(werner_parameter(length_m, l_depol_m))


def chsh_parameter(fidelity: float) -> float:
    """Werner 族的 CHSH 参数 `S = 2√2·p`，`p = (4F − 1)/3`（理想 F=1 ⇒ p=1 ⇒ S=2√2≈2.828）。

    🔴 **勿混 p 与 F**：`p` 是 Werner 参数（`ρ = p|Φ+⟩⟨Φ+| + (1−p)I/4`），`F = (1+3p)/4` 是保真度。
    教科书结论「Werner 态在 `p > 1/√2` 时违反 CHSH」是**以 p 表述**的。
    """
    if not (0.0 <= fidelity <= 1.0):
        raise ValueError("保真度须落在 [0, 1]")
    p = (4.0 * fidelity - 1.0) / 3.0
    return float(2.0 * math.sqrt(2.0) * p)


def violates_bell(fidelity: float) -> bool:
    """是否违反 Bell 不等式（可用作纠缠见证）：`S > 2` ⟺ `p > 1/√2` ⟺ `F > (1+3/√2)/4`。"""
    return bool(fidelity > BELL_VIOLATION_THRESHOLD_F)


def distribution_report(length_m: float = CH.DEFAULT_LINK_LENGTH_M,
                        l_depol_m: float = CH.DEFAULT_L_DEPOL_M,
                        alpha_db_per_km: float = CH.DEFAULT_ALPHA_DB_PER_KM) -> Dict[str, float]:
    """分发链汇总（只读 · 闭式现算 · 零重计算）。"""
    ch = CH.channel_report(length_m, alpha_db_per_km, l_depol_m)
    f = distribution_fidelity(length_m, l_depol_m)
    # 使 S 跌破 2 的临界长度：Werner 参数阈值 p* = 1/√2 ⇒ L* = −L_depol·ln p*
    p_star = 1.0 / math.sqrt(2.0)
    l_star = -l_depol_m * math.log(p_star)
    return {
        "length_m": ch["length_m"],
        "length_km": ch["length_km"],
        "alpha_db_per_km": ch["alpha_db_per_km"],
        "link_loss_db": ch["link_loss_db"],
        "transmission": ch["transmission"],
        "attenuation_length_m": ch["attenuation_length_m"],
        "l_depol_m": ch["l_depol_m"],
        "werner_p": werner_parameter(length_m, l_depol_m),
        "fidelity": f,
        "chsh_s": chsh_parameter(f),
        "violates_bell": 1.0 if violates_bell(f) else 0.0,
        "bell_threshold_f": BELL_VIOLATION_THRESHOLD_F,
        "bell_critical_length_m": float(l_star),
    }


def selfcheck_qnet_distribution() -> Dict[str, bool]:
    """分发能力层自检。"""
    checks: Dict[str, bool] = {}
    f0 = distribution_fidelity(0.0)
    checks["zero_length_is_ideal"] = bool(abs(f0 - 1.0) < 1e-15)

    f_inf = distribution_fidelity(1.0e12)
    checks["long_length_approaches_quarter"] = bool(abs(f_inf - 0.25) < 1e-9)

    checks["bell_threshold_consistent"] = bool(
        abs(chsh_parameter(BELL_VIOLATION_THRESHOLD_F) - 2.0) < 1e-12)

    # 100 km 链路：F = 0.25796 < 1/√2 ⇒ 不违反 Bell（即：直传 100 km 无法保持纠缠见证）
    checks["100km_does_not_violate_bell"] = bool(not violates_bell(distribution_fidelity(1.0e5)))

    # 短链路（1 km）应违反 Bell
    checks["1km_violates_bell"] = bool(violates_bell(distribution_fidelity(1.0e3)))

    checks["monotone_decreasing"] = bool(
        distribution_fidelity(1.0e3) > distribution_fidelity(1.0e4)
        > distribution_fidelity(1.0e5) > distribution_fidelity(1.0e6))

    # 临界长度自洽：在 L* 附近应是阈值穿越（跨过即翻转）
    rep = distribution_report()
    l_star = rep["bell_critical_length_m"]
    checks["critical_length_is_crossing"] = bool(
        violates_bell(distribution_fidelity(l_star * 0.99))
        and not violates_bell(distribution_fidelity(l_star * 1.01)))

    # 与 B519 数值核同律（闭式逐位）
    try:
        from lda_harness import _batch_j5_numeric as J5
        checks["matches_b519_golden"] = bool(
            abs(J5.distribution_fidelity_golden(2.2e4)
                - distribution_fidelity(1.0e5, 2.2e4)) < 1e-15)
    except Exception:
        checks["matches_b519_golden"] = False

    def _raises(fn):
        try:
            fn()
            return False
        except ValueError:
            return True

    checks["reverse_bad_fidelity_raises"] = _raises(lambda: chsh_parameter(1.5))
    checks["reverse_bad_length_raises"] = _raises(lambda: werner_parameter(-1.0))

    return checks


def main() -> int:
    sc = selfcheck_qnet_distribution()
    for k, v in sc.items():
        print("  [%s] %s" % ("PASS" if v else "FAIL", k))
    bad = sum(1 for v in sc.values() if not v)
    print("qnet_distribution 自检：%d PASS / %d FAIL" % (len(sc) - bad, bad))
    r = distribution_report()
    print("  L=%.1f km ⇒ F=%.12g · CHSH=%.6g · violates_bell=%s · L*=%.1f km"
          % (r["length_km"], r["fidelity"], r["chsh_s"], bool(r["violates_bell"]),
             r["bell_critical_length_m"] / 1000.0))
    return 1 if bad else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
