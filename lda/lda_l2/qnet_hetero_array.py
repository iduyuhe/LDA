# -*- coding: utf-8 -*-
"""蓝图 v2 · D1 光-量异质集成 · **M0 能力层：多模换能阵列**（`qnet_hetero_array`）。

定位：J5 M3（`qnet_transducer` / B522）解决**单节点**微波-光换能效率；本层把它推进到
      **多模阵列**——N 个换能单元沿一条输出总线排布，输出端是**有限孔径**（多模光纤/波导）。
      阵列的几何代价是：偏离中心的单元，其高斯模场尾部被孔径**截断**。

物理量（M0 · 一条）：
  `γ_i = 0.5·[erf((a−x_i)/(√2w)) + erf((a+x_i)/(√2w))]`（单元 i 的模场功率落入孔径的占比）
  `γ̄  = (1/N)·Σ γ_i`（阵列**平均孔径截断效率**）
  `x_i = (i − (N−1)/2)·d`（中心对齐排布）

闭式（golden）⇄ 限窗复合 Simpson 求积（candidate · 真截断 · O(h⁴)）——见 `_batch_v2d1_numeric`。

🔴 **与 B522 的避让**：B522 = 单节点换能的**频域**效率（协同度 × 有限探测带侧带重叠）；
  本层 = 阵列的**几何孔径**因子（无 C、无洛伦兹带、无频域积分）⇒ 物理量不同，非重复计数。
🔴 **零 RNG**（纯 `math`）；**零商业依赖**；**LLM 不进判决路径**。
🔴 **诚实边界**：N / d / w / a 均为**设计示例量级**（非任何实测光纤阵列/波导）；只建模
  「高斯模场 × 有限孔径」这一最小骨架（未含模式耦合、相位、偏振、背反射、温漂）
  ⇒ 只支撑几何预算与量级，**不作制造/性能宣称**。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

__all__ = [
    "QNET_HETERO_ARRAY_CALIBER",
    "DEFAULT_N_MODES",
    "DEFAULT_SPACING_M",
    "DEFAULT_WAIST_M",
    "DEFAULT_APERTURE_HALF_M",
    "mode_offsets",
    "aperture_clip_efficiency",
    "array_average_clip",
    "array_clip_spread",
    "hetero_array_report",
    "selfcheck_qnet_hetero_array",
]

QNET_HETERO_ARRAY_CALIBER = "multimode_transducer_array_aperture_clip_efficiency__unitless"

#: 阵列单元数
DEFAULT_N_MODES = 8
#: 单元间距 d（m · 2 µm）
DEFAULT_SPACING_M = 2.0e-6
#: 单模场高斯腰 w（m · 1.5 µm）
DEFAULT_WAIST_M = 1.5e-6
#: 输出孔径半宽 a（m · 6 µm）
DEFAULT_APERTURE_HALF_M = 6.0e-6

_SQRT2 = math.sqrt(2.0)


def mode_offsets(n_modes: int = DEFAULT_N_MODES,
                 spacing_m: float = DEFAULT_SPACING_M) -> List[float]:
    """中心对齐排布：`x_i = (i − (N−1)/2)·d`（i=0…N−1）。"""
    n = int(n_modes)
    d = float(spacing_m)
    if n < 1:
        raise ValueError("n_modes 须 ≥ 1")
    if not d > 0.0:
        raise ValueError("spacing_m 须 > 0")
    return [(i - (n - 1) / 2.0) * d for i in range(n)]


def aperture_clip_efficiency(offset_m: float = 0.0,
                             waist_m: float = DEFAULT_WAIST_M,
                             aperture_half_m: float = DEFAULT_APERTURE_HALF_M) -> float:
    """单元模场功率落入有限孔径的占比 `γ ∈ [0,1]`（闭式 erf）。

    高斯模场 `E(x)=exp(−(x−offset)²/(2w²))`；孔径 `[−a, a]`。
    `γ = 0.5·[erf((a−offset)/(√2w)) + erf((a+offset)/(√2w))]`。
    """
    x = float(offset_m)
    w = float(waist_m)
    a = float(aperture_half_m)
    if not w > 0.0:
        raise ValueError("waist_m 须 > 0")
    if not a > 0.0:
        raise ValueError("aperture_half_m 须 > 0")
    s2 = _SQRT2 * w
    g = 0.5 * (math.erf((a - x) / s2) + math.erf((a + x) / s2))
    # 数值夹紧（erf 饱和档的理论值本就在 [0,1]）
    return float(min(1.0, max(0.0, g)))


def array_average_clip(n_modes: int = DEFAULT_N_MODES,
                       spacing_m: float = DEFAULT_SPACING_M,
                       waist_m: float = DEFAULT_WAIST_M,
                       aperture_half_m: float = DEFAULT_APERTURE_HALF_M) -> float:
    """阵列**平均**孔径截断效率 `γ̄ = (1/N)·Σ γ_i`。"""
    xs = mode_offsets(n_modes, spacing_m)
    vals = [aperture_clip_efficiency(x, waist_m, aperture_half_m) for x in xs]
    return float(sum(vals) / len(vals))


def array_clip_spread(n_modes: int = DEFAULT_N_MODES,
                      spacing_m: float = DEFAULT_SPACING_M,
                      waist_m: float = DEFAULT_WAIST_M,
                      aperture_half_m: float = DEFAULT_APERTURE_HALF_M) -> Dict[str, float]:
    """阵列截断效率的分布（min/max/中心/边缘 · 只读报告）。"""
    xs = mode_offsets(n_modes, spacing_m)
    vals = [aperture_clip_efficiency(x, waist_m, aperture_half_m) for x in xs]
    return {
        "min": float(min(vals)),
        "max": float(max(vals)),
        "center": float(aperture_clip_efficiency(0.0, waist_m, aperture_half_m)),
        "edge": float(aperture_clip_efficiency(xs[0], waist_m, aperture_half_m)),
        "ratio_aperture_over_waist": float(aperture_half_m / waist_m),
        "ratio_span_over_aperture": float(((n_modes - 1) * spacing_m)
                                          / (2.0 * aperture_half_m)),
    }


def hetero_array_report() -> Dict[str, Any]:
    """M0 报告（一条主标量 + 分布 · 零重计算）。"""
    r = array_clip_spread()
    return {
        "average_clip_efficiency": array_average_clip(),
        "clip_min": r["min"],
        "clip_max": r["max"],
        "clip_center": r["center"],
        "clip_edge": r["edge"],
        "ratio_aperture_over_waist": r["ratio_aperture_over_waist"],
        "ratio_span_over_aperture": r["ratio_span_over_aperture"],
        "n_modes": float(DEFAULT_N_MODES),
        "caliber": QNET_HETERO_ARRAY_CALIBER,
    }


def selfcheck_qnet_hetero_array() -> Dict[str, bool]:
    """M0 能力层自检（物理性质 + 与 golden 逐位对拍 + 反向探针）。"""
    checks: Dict[str, bool] = {}
    r = hetero_array_report()

    # ① 值域
    checks["average_clip_in_unit_interval"] = bool(0.0 < r["average_clip_efficiency"] <= 1.0)

    # ② 极限：宽孔径 ⇒ 1；零孔径 ⇒ 0
    checks["clip_to_one_at_wide_aperture"] = bool(
        abs(aperture_clip_efficiency(0.0, DEFAULT_WAIST_M,
                                     DEFAULT_WAIST_M * 100.0) - 1.0) < 1e-12)
    checks["clip_to_zero_at_tiny_aperture"] = bool(
        aperture_clip_efficiency(0.0, DEFAULT_WAIST_M, DEFAULT_WAIST_M * 1e-6) < 1e-6)

    # ③ 单调：随孔径增、随偏移减；对称
    checks["clip_monotone_in_aperture"] = bool(
        aperture_clip_efficiency(0.0, DEFAULT_WAIST_M, DEFAULT_APERTURE_HALF_M * 0.6)
        < aperture_clip_efficiency(0.0, DEFAULT_WAIST_M, DEFAULT_APERTURE_HALF_M * 1.4))
    checks["clip_monotone_decreasing_in_offset"] = bool(
        aperture_clip_efficiency(0.0) > aperture_clip_efficiency(DEFAULT_SPACING_M * 3.0))
    checks["clip_symmetric_in_offset"] = bool(
        abs(aperture_clip_efficiency(DEFAULT_SPACING_M * 2.0)
            - aperture_clip_efficiency(-DEFAULT_SPACING_M * 2.0)) < 1e-15)

    # ④ 阵列平均落在 [min, max] 且边缘 < 中心
    checks["average_between_min_max"] = bool(
        r["clip_min"] <= r["average_clip_efficiency"] <= r["clip_max"])
    checks["edge_below_center"] = bool(r["clip_edge"] < r["clip_center"])

    # ⑤ 与数值核 golden 逐位对拍
    try:
        from lda_harness import _batch_v2d1_numeric as V
        g = V.golden_b523()
        rel = abs(array_average_clip() - g) / max(abs(g), 1e-300)
        checks["matches_b523_golden_rel_lt_1e-12"] = bool(rel < 1e-12)
        checks["matches_b523_default_params"] = bool(
            abs(V.B523_DEFAULT_PARAMS["n_modes"] - DEFAULT_N_MODES) < 1e-12
            and abs(V.B523_DEFAULT_PARAMS["spacing_m"] - DEFAULT_SPACING_M) < 1e-12
            and abs(V.B523_DEFAULT_PARAMS["waist_m"] - DEFAULT_WAIST_M) < 1e-12
            and abs(V.B523_DEFAULT_PARAMS["aperture_half_m"] - DEFAULT_APERTURE_HALF_M) < 1e-12)
    except Exception:
        checks["matches_b523_golden_rel_lt_1e-12"] = False
        checks["matches_b523_default_params"] = False

    # ⑥ 反向探针：非法入参必抛
    def _raises(fn):
        try:
            fn()
        except ValueError:
            return True
        return False

    checks["reverse_bad_waist_raise"] = bool(
        _raises(lambda: aperture_clip_efficiency(0.0, 0.0, DEFAULT_APERTURE_HALF_M)))
    checks["reverse_bad_aperture_raise"] = bool(
        _raises(lambda: aperture_clip_efficiency(0.0, DEFAULT_WAIST_M, 0.0)))
    checks["reverse_bad_modes_raise"] = bool(_raises(lambda: mode_offsets(0)))
    return checks


def main() -> int:  # pragma: no cover
    checks = selfcheck_qnet_hetero_array()
    bad = [k for k, v in checks.items() if not v]
    for k, v in checks.items():
        print("  [%s] %s" % ("PASS" if v else "FAIL", k))
    r = hetero_array_report()
    print("\nγ̄ = %.12e  (min %.6e / max %.6e / center %.6e / edge %.6e)"
          % (r["average_clip_efficiency"], r["clip_min"], r["clip_max"],
             r["clip_center"], r["clip_edge"]))
    print("a/w = %.2f  ·  span/(2a) = %.2f" % (r["ratio_aperture_over_waist"],
                                               r["ratio_span_over_aperture"]))
    print("自检：%s（FAIL=%s）" % ("ALL PASS" if not bad else "FAIL", bad or "无"))
    return 0 if not bad else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
