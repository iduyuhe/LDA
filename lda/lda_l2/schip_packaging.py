# -*- coding: utf-8 -*-
"""📦 S5 封装 / 低温布线：**TSV · 倒装焊 · 低温衰减链**（`schip_packaging`）。

定位：`schip` 的 `G-E` 一直写着「封装只做到『腔模规避 + 参与比预算』；**倒装焊、TSV、
低温衰减链未实现**」。本层把这三项都建起来，且**每一项都配一条精确对照支路**
（不是「模型写完了」，而是「模型能被已知答案判红」）。

⚠️ 本卡红线（见 `run_schip_case_smoke` 的 Z2）要求 `schip_case` **零重计算、不 import 求解器**
⇒ 本层是独立能力层，**不挂进卡片**，只由门禁对拍。

═══ ① TSV 同轴闭式 ═══
  内导体半径 `r_i`、外导体（硅通孔侧壁/套筒）半径 `r_o`、高 `h`、介质 `ε_r`：
    `L = (μ₀h/2π)·ln(r_o/r_i)`          `C = 2π·ε₀ε_r·h/ln(r_o/r_i)`
    `Z₀ = √(L/C) = (1/2π)·√(μ₀/(ε₀ε_r))·ln(r_o/r_i)`
    `v_p = 1/√(L·C)`  🔴 **必须等于 `c/√ε_r`** —— 这条判据能抓住 L 或 C 里任何因子 2 / 单位错。
  另配恒等式 `L·C ≡ μ₀ε₀ε_r·h²`（两条独立推导同一结果）。

═══ ② 倒装焊凸点 ═══
  两根**平行线段**（长 `h`、间距 `d`）的互感 —— Neumann 积分有**精确闭式**：
    `M(d) = (μ₀/2π)·[h·asinh(h/d) − √(h²+d²) + d]`
  对照支路：**直接对 `1/√((z−z′)²+d²)` 做二维复合 Simpson**（不求原函数）⇒ 相对 ≤1e-8。
  另一条：`d ≪ h` 渐近必须回到细线对数式 `(μ₀h/2π)[ln(2h/d) − 1]`。
  凸点直流电阻 `R = ρ·h/(πa²)`（`a` = 半径）。

═══ ③ 低温衰减链（驱动线噪声到达器件） ═══
  分段衰减器（损耗因子 `A_i ≥ 1`、物理温度 `T_i`）串联，源在 `T_src`：
    `n_out = n_th(T_src)·Π(1/A_i) + Σ_i n_th(T_i)·(1 − 1/A_i)·Π_{j>i}(1/A_j)`
  🔴 **闭式已知答案（望远镜恒等式）**：`Σ_i (1−1/A_i)Π_{j>i}(1/A_j) ≡ 1 − Π(1/A_i)`
     ⇒ **整条链同温且等于源温时，`n_out ≡ n_th(T)`（链是透明的）**。
     这条判据极硬：任何一处把「下游衰减」写成「上游衰减」，等式立刻破。
  🔴 **由此得到的设计结论（可复算）**：每一级的贡献被**下游**（更靠近器件侧）的损耗压低、
     而**最靠器件那一级不被压低** ⇒ **大衰减要放在最冷、最后一级**（混频级），
     而不是最前（室温端）。本层用「冷端在前 ↔ 冷端在后」两条链**逐条对比**给出倍数。

🔴 **诚实边界**：`r_i/r_o/h/a/d/ρ` 与各级 `A_i/T_i` 全为**设计示例量级**（非任何实测封装/低温链）；
  只建模**单根同轴 TSV**（未含 TSV 阵列间的衬底耦合与应力）、**两根平行凸点**（未含整阵列集体效应）、
  **频率无关的分段衰减器**（未含衰减器频响、连接器反射、同轴段驻波）。
  零商业依赖（纯 `math`）；**零 RNG**；**LLM 不进判决路径**。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from lda_l2.qnet_thermal_noise import thermal_occupancy

__all__ = [
    "SCHIP_PKG_CALIBER",
    "MU0",
    "EPS0",
    "C_LIGHT",
    "RHO_CU_4K",
    "tsv_coax",
    "mutual_inductance_parallel",
    "mutual_neumann_simpson",
    "bump_report",
    "drive_line_noise",
    "attenuation_chain_compare",
    "packaging_report",
    "selfcheck_schip_packaging",
]

SCHIP_PKG_CALIBER = "packaging__si_units"

#: 🔴 **CODATA-2018 书写值**（SI 2019 起 μ₀ 不再是「精确 4π×10⁻⁷」）
MU0 = 1.25663706212e-6          # H/m
EPS0 = 8.8541878128e-12         # F/m
C_LIGHT = 299792458.0           # m/s（SI 定义值 · 精确）

#: 铜在 4 K 的电阻率（RRR≈100 量级 · 设计示例）
RHO_CU_4K = 1.7e-10             # Ω·m

_TWO_PI = 2.0 * math.pi


def _pos(name: str, value: float) -> float:
    v = float(value)
    if not v > 0.0:
        raise ValueError("%s 须 > 0" % name)
    return v


# ══════════════════════════════════════════════════════════════════════
# ① TSV 同轴闭式
# ══════════════════════════════════════════════════════════════════════
def tsv_coax(r_inner_um: float = 5.0, r_outer_um: float = 20.0,
             height_um: float = 100.0, eps_r: float = 11.9,
             rho_ohm_m: float = RHO_CU_4K) -> Dict[str, float]:
    """同轴 TSV 闭式：`L / C / Z₀ / v_p / R_dc`。

    `v_p` 必须等于 `c/√ε_r`（判据机核）—— 这条能抓住 `L` 或 `C` 里任何因子 2 与单位错。
    """
    ri = _pos("r_i", r_inner_um) * 1e-6
    ro = _pos("r_o", r_outer_um) * 1e-6
    h = _pos("h", height_um) * 1e-6
    er = _pos("ε_r", eps_r)
    if not ro > ri:
        raise ValueError("r_o 须 > r_i")
    ln = math.log(ro / ri)
    L = MU0 * h / _TWO_PI * ln                      # H
    cap = _TWO_PI * EPS0 * er * h / ln              # F
    Z0 = math.sqrt(L / cap)
    # 🔴 `v_p` 必须用**单位长度** `L′=L/h`、`C′=C/h`：
    #    用**总量** `L_tot·C_tot = μ₀ε h²` 会得到 `1/(h√(μ₀ε))` —— 差一个 `1/h`（本层实测差 **1e4×**）。
    #    这个错正是「`v_p == c/√ε_r`」这条判据当场抓出来的。
    lp, cp = L / h, cap / h
    vp = 1.0 / math.sqrt(lp * cp)
    r_dc = float(rho_ohm_m) * h / (math.pi * (ro * ro - ri * ri))
    return {
        "r_inner_um": float(r_inner_um), "r_outer_um": float(r_outer_um),
        "height_um": float(height_um), "eps_r": float(eps_r),
        "L_H": float(L), "C_F": float(cap),
        "Z0_ohm": float(Z0),
        "Z0_closed_form_ohm": float(math.sqrt(MU0 / (EPS0 * er)) / _TWO_PI * ln),
        "L_per_m_H": float(lp), "C_per_m_F": float(cp),
        "v_p_m_per_s": float(vp),
        "v_p_expected_m_per_s": float(C_LIGHT / math.sqrt(er)),
        "LC_identity": float(L * cap),
        "LC_expected": float(MU0 * EPS0 * er * h * h),
        "R_dc_ohm": float(r_dc),
        "delay_ps": float(h / vp * 1e12),
    }


# ══════════════════════════════════════════════════════════════════════
# ② 倒装焊凸点：平行线段互感（精确闭式 ⇄ 二维 Simpson）
# ══════════════════════════════════════════════════════════════════════
def mutual_inductance_parallel(height_um: float = 20.0,
                               spacing_um: float = 50.0) -> float:
    """两根平行线段（等长 `h`、间距 `d`）的互感 `M`（H）—— Neumann 积分的**精确闭式**。

    `M = (μ₀/2π)·[h·asinh(h/d) − √(h²+d²) + d]`（`d ≪ h` 时回到细线对数式）。
    """
    h = _pos("h", height_um) * 1e-6
    d = _pos("d", spacing_um) * 1e-6
    return float(MU0 / _TWO_PI * (h * math.asinh(h / d)
                                  - math.sqrt(h * h + d * d) + d))


def mutual_neumann_simpson(height_um: float = 20.0,
                           spacing_um: float = 50.0,
                           n: int = 200) -> float:
    """**独立路径**：直接对 `1/√((z−z′)²+d²)` 做二维复合 Simpson（不借任何原函数）。"""
    h = _pos("h", height_um) * 1e-6
    d = _pos("d", spacing_um) * 1e-6
    if int(n) < 4 or int(n) % 2:
        raise ValueError("Simpson 要求 n 为 ≥4 的偶数")
    m = int(n)
    step = h / m
    # Simpson 权重
    w = [1.0] + [4.0 if (i % 2) else 2.0 for i in range(1, m)] + [1.0]
    tot = 0.0
    for i in range(m + 1):
        zi = i * step
        row = 0.0
        for j in range(m + 1):
            zj = j * step
            row += w[j] / math.sqrt((zi - zj) ** 2 + d * d)
        tot += w[i] * row
    return float(MU0 / (4.0 * math.pi) * (step / 3.0) ** 2 * tot)


def bump_report(radius_um: float = 10.0, height_um: float = 20.0,
                spacing_um: float = 50.0, rho_ohm_m: float = RHO_CU_4K
                ) -> Dict[str, float]:
    """凸点报告：`R_dc` · 自感上界 · 互感 · 耦合系数 `k`。"""
    a = _pos("a", radius_um) * 1e-6
    h = _pos("height_um", height_um) * 1e-6
    d = _pos("spacing_um", spacing_um) * 1e-6
    r_dc = float(rho_ohm_m) * h / (math.pi * a * a)
    # 自感取「同尺寸孤立细线」的对数式（d → a 的极限），作**上界量级**
    l_self = float(MU0 * h / _TWO_PI * (math.log(2.0 * h / a) - 1.0))
    m_mut = mutual_inductance_parallel(height_um, spacing_um)
    return {
        "radius_um": float(radius_um), "height_um": float(height_um),
        "spacing_um": float(spacing_um),
        "R_dc_ohm": float(r_dc),
        "L_self_H": float(l_self),
        "M_mutual_H": float(m_mut),
        "M_over_L": float(m_mut / l_self),
        "k_coupling": float(m_mut / l_self),
        "spacing_over_height": float(d / h),
    }


# ══════════════════════════════════════════════════════════════════════
# ③ 低温衰减链：驱动线噪声到达器件
# ══════════════════════════════════════════════════════════════════════
def drive_line_noise(stages: Sequence[Tuple[float, float]],
                     source_temp_k: float = 300.0,
                     freq_hz: float = 5.0e9) -> Dict[str, Any]:
    """分段衰减链到达器件的噪声光子数。

    `stages` 按**源 → 器件**顺序给 `(损耗因子 A, 物理温度 T)`。`A ≥ 1`（`A = 1` 为无损耗）。

    🔴 **每级贡献被「下游」（更靠器件侧）损耗压低，最靠器件那一级不被压低** —— 这就是
      「大衰减放最冷、最后一级」的定量来源。
    """
    if not stages:
        raise ValueError("至少一级")
    src = _pos("源温度", source_temp_k)
    f = _pos("频率", freq_hz)
    n_src = thermal_occupancy(src, f)
    trans_all = 1.0
    contrib: List[Dict[str, float]] = []
    for a, t in stages:
        ai = float(a)
        if not ai >= 1.0:
            raise ValueError("损耗因子 A 须 ≥ 1")
        _pos("级温度", t)
        trans_all /= ai
    for i, (a, t) in enumerate(stages):
        ai = float(a)
        down = 1.0
        for b, _tb in stages[i + 1:]:
            down /= float(b)
        c = thermal_occupancy(float(t), f) * (1.0 - 1.0 / ai) * down
        contrib.append({"stage": int(i), "A": ai, "T_K": float(t),
                        "downstream_transmission": float(down),
                        "contribution": float(c)})
    n_out = n_src * trans_all + sum(c["contribution"] for c in contrib)
    return {
        "source_temp_k": float(source_temp_k), "freq_hz": float(f),
        "total_transmission": float(trans_all),
        "source_term": float(n_src * trans_all),
        "stages": contrib,
        "n_out": float(n_out),
        "n_source": float(n_src),
        "telescope_sum": float(sum((1.0 - 1.0 / float(a)) *
                                   math.prod([1.0 / float(b) for b, _ in stages[i + 1:]])
                                   for i, (a, _t) in enumerate(stages))),
        "telescope_expected": float(1.0 - trans_all),
    }


def attenuation_chain_compare(cold_temp_k: float = 0.020, warm_temp_k: float = 4.0,
                              loss_db: float = 10.0, n_stages: int = 3,
                              freq_hz: float = 5.0e9) -> Dict[str, Any]:
    """**设计结论机核**：同样各级损耗，「冷端在前」vs「冷端在后」逐条对比。"""
    a = 10.0 ** (float(loss_db) / 10.0)
    n = int(n_stages)
    cold_first = [(a, cold_temp_k)] + [(a, warm_temp_k)] * (n - 1)
    cold_last = [(a, warm_temp_k)] * (n - 1) + [(a, cold_temp_k)]
    r1 = drive_line_noise(cold_first, freq_hz=freq_hz)
    r2 = drive_line_noise(cold_last, freq_hz=freq_hz)
    return {
        "loss_factor_per_stage": float(a),
        "loss_db": float(loss_db),
        "n_stages": n,
        "n_out_cold_first": r1["n_out"],
        "n_out_cold_last": r2["n_out"],
        "n_out_homogeneous": drive_line_noise(
            [(a, cold_temp_k)] * n, source_temp_k=cold_temp_k, freq_hz=freq_hz)["n_out"],
        "ratio_cold_first_over_last": float(r1["n_out"] / r2["n_out"]) if r2["n_out"] > 0 else float("inf"),
        "cold_last_is_better": bool(r2["n_out"] < r1["n_out"]),
        "n_th_cold": float(thermal_occupancy(float(cold_temp_k), freq_hz)),
    }


def packaging_report() -> Dict[str, Any]:
    """封装能力层报告（三块一次给全 · 零重计算）。"""
    tsv = tsv_coax()
    bump = bump_report()
    chain = attenuation_chain_compare()
    stages = [(10.0, 300.0), (10.0, 4.0), (10.0, 0.020)]
    dl = drive_line_noise(stages)
    return {"tsv": tsv, "bump": bump, "chain": chain,
            "reference_chain": {"stages": stages, "n_out": dl["n_out"],
                                "total_transmission": dl["total_transmission"]},
            "caliber": SCHIP_PKG_CALIBER}


def selfcheck_schip_packaging() -> Dict[str, bool]:
    """封装层自检（**三条闭式已知答案 + 望远镜恒等式 + 绝对量级 + 反向探针**）。"""
    c: Dict[str, bool] = {}
    t = tsv_coax()
    b = bump_report()
    ch = attenuation_chain_compare()

    # ① 电磁常数：CODATA 书写值自洽（μ₀ε₀c² = 1 · 相 4.3e-14）+ c 是 SI 定义值
    c["em_constants_consistent"] = bool(abs(MU0 * EPS0 * C_LIGHT ** 2 - 1.0) <= 1e-12)
    c["c_is_si_definition_value"] = bool(C_LIGHT == 299792458.0)

    # ② 🔴 TSV 闭式已知答案：v_p 必须 == c/√ε_r（抓 L/C 的因子 2 与单位错）
    rel_vp = abs(t["v_p_m_per_s"] - t["v_p_expected_m_per_s"]) / t["v_p_expected_m_per_s"]
    c["tsv_velocity_equals_c_over_sqrt_eps"] = bool(rel_vp <= 1e-12)
    # ③ 恒等式 L·C ≡ μ₀ε₀ε_r h²
    c["tsv_LC_identity"] = bool(
        abs(t["LC_identity"] - t["LC_expected"]) <= 1e-15 * t["LC_expected"])
    # ④ Z₀ 两条独立推导一致
    c["tsv_Z0_two_paths"] = bool(
        abs(t["Z0_ohm"] - t["Z0_closed_form_ohm"]) <= 1e-14 * t["Z0_ohm"])
    # ⑤ L、C 均 ∝ h（精确比例）
    t2 = tsv_coax(height_um=200.0)
    c["tsv_L_C_linear_in_h"] = bool(
        abs(t2["L_H"] / t["L_H"] - 2.0) <= 1e-15
        and abs(t2["C_F"] / t["C_F"] - 2.0) <= 1e-15
        and abs(t2["R_dc_ohm"] / t["R_dc_ohm"] - 2.0) <= 1e-15)

    # ⑥ 🔴 互感：闭式 ≡ 二维 Simpson（独立路径 · 相对 ≤1e-8）
    m_closed = mutual_inductance_parallel(20.0, 50.0)
    m_simp = mutual_neumann_simpson(20.0, 50.0, n=200)
    rel_m = abs(m_closed - m_simp) / m_closed
    c["mutual_closed_equals_simpson"] = bool(rel_m <= 1e-8)
    # ⑦ 细线渐近：d ≪ h 时闭式必须回到 (μ₀h/2π)[ln(2h/d) − 1]
    h, d = 20e-6, 0.02 * 20e-6
    asym = MU0 * h / _TWO_PI * (math.log(2.0 * h / d) - 1.0)
    c["mutual_asymptote_thin_wire"] = bool(
        abs(mutual_inductance_parallel(20.0, 0.02 * 20.0) - asym) / abs(asym) <= 2e-2)
    # ⑧ 互感的符号与单调性（间距↑ ⇒ M↓，且恒为正）
    ms = [mutual_inductance_parallel(20.0, x) for x in (5.0, 20.0, 50.0, 100.0)]
    c["mutual_positive_and_monotone"] = bool(
        all(x > 0.0 for x in ms) and all(ms[i] > ms[i + 1] for i in range(len(ms) - 1)))

    # ⑨ 🔴 望远镜恒等式：Σ(1−1/A)Π_down(1/A) ≡ 1 − Π(1/A)（相对 1e-14）
    dl = drive_line_noise([(10.0, 300.0), (10.0, 4.0), (10.0, 0.020)])
    c["telescoping_identity"] = bool(
        abs(dl["telescope_sum"] - dl["telescope_expected"])
        <= 1e-14 * abs(dl["telescope_expected"]))
    # ⑩ 🔴 最强对照支路：整链同温且等于源温 ⇒ 链**透明**（n_out ≡ n_th(T)）
    for temp_k in (0.020, 4.0, 300.0):
        homo = drive_line_noise([(10.0, temp_k)] * 4, source_temp_k=temp_k)
        ok = abs(homo["n_out"] - homo["n_source"]) <= 1e-14 * max(homo["n_source"], 1e-300)
        c["transparent_when_all_stages_same_temp_%g" % temp_k] = bool(ok)
        if not ok:
            break

    # ⑪ 🔴 设计结论机核：冷端放在**最后**（靠器件）优于放最前
    c["cold_last_beats_cold_first"] = bool(ch["cold_last_is_better"])
    # 实测约 6.1×（3 级 ×10 dB · 20 mK vs 4 K）；门槛取 >5× 留余量
    c["cold_last_ratio_gt_5x"] = bool(ch["ratio_cold_first_over_last"] > 5.0)
    # ⑫ 同温链 = 单级等效（把 n 级同温同损合并成一级，总损耗 A^n ⇒ n_out 必须相同）
    a, t0, n = 10.0, 4.0, 3
    merged = drive_line_noise([(a ** n, t0)], source_temp_k=t0)
    split = drive_line_noise([(a, t0)] * n, source_temp_k=t0)
    c["same_temp_chain_equals_single_stage"] = bool(
        abs(merged["n_out"] - split["n_out"]) <= 1e-14 * max(merged["n_out"], 1e-300))

    # ⑬ 绝对量级锚点（防单位/量级错）
    #   Z₀ = 24.1 Ω（= 60/√ε_r·ln(r_o/r_i) 同口径）· v_p = 8.69e7 m/s · L_self = 1.55 pH ·
    #   R_dc = 1.4e-5 Ω（4 K 铜 · 100 µm² 截面 ⇒ 确实很小，这是低损耗而非算错）
    c["reference_magnitude"] = bool(
        10.0 <= t["Z0_ohm"] <= 60.0
        and 8.0e7 <= t["v_p_m_per_s"] <= 9.5e7
        and 1e-13 <= b["L_self_H"] <= 1e-10
        and 1e-7 <= t["R_dc_ohm"] <= 1e-2
        and 1e-3 <= ch["n_out_cold_last"] <= 10.0)

    # ⑭ 无源不放大：输出噪声不超过源噪声
    c["passive_no_amplification"] = bool(
        dl["n_out"] <= dl["n_source"] + 1e-15)

    # 反向探针：非法入参必抛
    def _raises(fn):
        try:
            fn()
        except ValueError:
            return True
        return False

    c["reverse_bad_geometry_raise"] = bool(
        _raises(lambda: tsv_coax(r_inner_um=20.0, r_outer_um=5.0))
        and _raises(lambda: tsv_coax(height_um=0.0)))
    c["reverse_bad_stage_raise"] = bool(
        _raises(lambda: drive_line_noise([(0.5, 4.0)]))
        and _raises(lambda: drive_line_noise([])))
    return c


def main() -> int:  # pragma: no cover
    checks = selfcheck_schip_packaging()
    bad = [k for k, v in checks.items() if not v]
    for k, v in checks.items():
        print("  [%s] %s" % ("PASS" if v else "FAIL", k))
    r = packaging_report()
    t, b, ch = r["tsv"], r["bump"], r["chain"]
    print("\n① TSV 同轴（r_i=5 / r_o=20 / h=100 µm / ε_r=11.9）：")
    print("   L = %.6e H · C = %.6e F · Z₀ = %.3f Ω · v_p = %.6e m/s（c/√ε_r = %.6e）· R_dc = %.4f Ω"
          % (t["L_H"], t["C_F"], t["Z0_ohm"], t["v_p_m_per_s"],
             t["v_p_expected_m_per_s"], t["R_dc_ohm"]))
    print("② 凸点（a=10 / h=20 / d=50 µm）：R_dc = %.4f Ω · L_self = %.4e H · M = %.4e H · k = %.3f"
          % (b["R_dc_ohm"], b["L_self_H"], b["M_mutual_H"], b["k_coupling"]))
    print("③ 衰减链（3×10 dB · 源 300 K → 4 K → 20 mK）：到达器件 n_out = %.6f（源 %.4g）"
          % (r["reference_chain"]["n_out"], drive_line_noise([(10.0, 300.0), (10.0, 4.0), (10.0, 0.020)])["n_source"]))
    print("   冷端在前 %.4f  vs  冷端在后 %.4f  ⇒ 冷端在后优 **%.1f×**"
          % (ch["n_out_cold_first"], ch["n_out_cold_last"], ch["ratio_cold_first_over_last"]))
    print("自检：%s（FAIL=%s）" % ("ALL PASS" if not bad else "FAIL", bad or "无"))
    return 0 if not bad else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
