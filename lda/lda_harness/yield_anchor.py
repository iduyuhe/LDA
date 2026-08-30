"""LDA 系统级设计良率锚 S13（DFY · Design for Yield · v0.9.1）。

背景（锚缺口分析 2026-08-29 · 钉子 A）：
  商业 EDA 的核心卖点之一是 yield / DFM 分析——回答「这个设计在工艺容差下
  有多大比例能命中规格」。LDA 原有 S7/S8 统计锚只给出「分布均值 / 最坏下界」，
  缺产品级的「良率」标量。S13 把分布统计升级为**容差内概率**。

物理载体：环形谐振器 FSR 良率（复用 B4 已验证定律，零新物理）
  FSR = λ² / (n_g · L)                        （B4 环形 FSR 解析定律）
  L ~ N(L0, σ_rel·L0)                          （光刻 CD 工艺容差，高斯）
  规格窗口：FSR ∈ [FSR_nom·(1−δ), FSR_nom·(1+δ)]（双侧规格限 LSL/USL）

红线（严格保持 · LLM 不进判决路径）：
  判决 = 死标量比对，且是**同一物理定律的两种独立算法互证**：
    ① 解析解：FSR = c/L 单调 → 规格窗口可逆变换为 L 区间 →
       良率 = Φ((L_hi−L0)/σ_L) − Φ((L_lo−L0)/σ_L)，**精确闭式，非一阶近似**；
    ② 蒙特卡洛：固定种子采样 L → 逐样本算 FSR → 命中窗口计数 / N。
  两者若一致（|Δ| ≤ tol），说明数值采样与解析积分在同一物理定律上收敛——
  这是「非 AI ground」：高斯容差积分的解析解是确定性数学，不含任何模型假设。

为什么解析解用精确闭式而非一阶近似：
  一阶近似（FSR 相对偏差 ≈ −L 相对偏差）会给出 Y ≈ 2Φ(δ/σ_rel)−1，
  而精确解因 1/L 非线性略有差异（本例 0.9536 vs 0.9545）。用精确闭式
  才能让互证真正有效——否则是「两个近似互相印证」，不构成硬 ground。

实现约束：纯标准库（math/random/statistics），零第三方依赖——
与项目「核心零依赖优雅降级」铁律一致（FDTD 内核同纪律）。
"""
from __future__ import annotations

import math
import random
import statistics
from typing import Dict, List, Tuple

# ---- 默认工艺 / 规格参数（公开文献典型量级，发动期 PDK 校准替换） ----
LAMBDA_NM = 1550.0        # 工作波长（C 波段）
N_G = 4.2                 # SOI 波导群折射率（典型公开值）
FSR_NOM_NM = 17.5         # 目标 FSR（B4 锚常见场景量级）
SPEC_DELTA = 0.02         # 规格窗口半宽（±2%）
SIGMA_REL = 0.01          # 环周长工艺容差（1σ 相对值，±1%）
N_SAMPLES = 20000         # 蒙特卡洛采样数（标准误 ≈0.15pp）
SEED = 1313               # 固定种子（S13 序号，可复现）


def _phi(x: float) -> float:
    """标准正态累积分布函数 Φ(x) = ½·(1 + erf(x/√2))（纯标准库）。"""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def nominal_ring_length(fsr_nom_nm: float = FSR_NOM_NM,
                        n_g: float = N_G,
                        lam_nm: float = LAMBDA_NM) -> float:
    """由目标 FSR 反解名义环周长：L0 = λ² / (n_g · FSR)（B4 定律逆用）。"""
    return (lam_nm ** 2) / (n_g * fsr_nom_nm)


def yield_analytic(fsr_nom_nm: float = FSR_NOM_NM,
                   delta: float = SPEC_DELTA,
                   sigma_rel: float = SIGMA_REL,
                   n_g: float = N_G,
                   lam_nm: float = LAMBDA_NM) -> float:
    """解析良率（精确闭式，交叉验证的硬 ground）。

    推导：FSR = c/L（c = λ²/n_g），在区间上严格单调递减 →
      FSR ∈ [FSR_nom(1−δ), FSR_nom(1+δ)]
        ⟺ L ∈ [c/(FSR_nom(1+δ)), c/(FSR_nom(1−δ))]
    故 Y = P(L ∈ [L_lo, L_hi]) = Φ((L_hi−L0)/σ_L) − Φ((L_lo−L0)/σ_L)。

    这是**精确解**：除「L 服从高斯」这一工艺模型输入外不含任何近似
    （不是 δ/σ 的一阶线性化）。1/L 的非线性已被完整保留。
    """
    c = (lam_nm ** 2) / n_g
    l0 = c / fsr_nom_nm
    sigma_l = sigma_rel * l0
    fsr_lo = fsr_nom_nm * (1.0 - delta)
    fsr_hi = fsr_nom_nm * (1.0 + delta)
    l_lo = c / fsr_hi      # FSR 上限对应的 L 下限（单调递减）
    l_hi = c / fsr_lo      # FSR 下限对应的 L 上限
    y = _phi((l_hi - l0) / sigma_l) - _phi((l_lo - l0) / sigma_l)
    return y


def monte_carlo_yield(fsr_nom_nm: float = FSR_NOM_NM,
                      delta: float = SPEC_DELTA,
                      sigma_rel: float = SIGMA_REL,
                      n_g: float = N_G,
                      lam_nm: float = LAMBDA_NM,
                      n_samples: int = N_SAMPLES,
                      seed: int = SEED) -> Tuple[float, Dict[str, float]]:
    """蒙特卡洛良率估计（固定种子 → 可复现的确定性判决量）。

    返回 (良率估计, 诊断字典)；诊断含样本 FSR 均值/标准差与命中计数，
    供 smoke 做方向性断言（工艺容差越大良率越低）。
    """
    c = (lam_nm ** 2) / n_g
    l0 = c / fsr_nom_nm
    sigma_l = sigma_rel * l0
    fsr_lo = fsr_nom_nm * (1.0 - delta)
    fsr_hi = fsr_nom_nm * (1.0 + delta)
    rng = random.Random(seed)
    hits = 0
    fsrs: List[float] = []
    for _ in range(int(n_samples)):
        L = l0 + rng.gauss(0.0, sigma_l)
        if L <= 0.0:                      # 物理不可能样本（σ≪L0 时概率可忽略）
            continue
        fsr = c / L
        fsrs.append(fsr)
        if fsr_lo <= fsr <= fsr_hi:
            hits += 1
    n = len(fsrs)
    y_mc = hits / n if n else 0.0
    diag = {"n_effective": n, "hits": hits,
            "fsr_mean_nm": round(statistics.fmean(fsrs), 6) if n else 0.0,
            "fsr_stdev_nm": round(statistics.pstdev(fsrs), 6) if n > 1 else 0.0,
            "fsr_lo_nm": round(fsr_lo, 6), "fsr_hi_nm": round(fsr_hi, 6)}
    return y_mc, diag


def s13_design_yield_anchor(fsr_nom_nm: float = FSR_NOM_NM,
                            delta: float = SPEC_DELTA,
                            sigma_rel: float = SIGMA_REL,
                            n_g: float = N_G,
                            lam_nm: float = LAMBDA_NM,
                            n_samples: int = N_SAMPLES,
                            seed: int = SEED) -> float:
    """S13 golden：固定种子下蒙特卡洛仿真良率（确定性判决量，可复现）。

    语义：给定工艺容差与规格窗口，良率是唯一确定值——任何人重跑同种子
    得到同一数字（可复现性 = 统计锚的判决前提）。
    物理正确性由 `yield_report()` 中的解析交叉验证守护（非本函数职责）。
    """
    y_mc, _ = monte_carlo_yield(fsr_nom_nm=fsr_nom_nm, delta=delta,
                                sigma_rel=sigma_rel, n_g=n_g, lam_nm=lam_nm,
                                n_samples=n_samples, seed=seed)
    return round(y_mc, 6)


def yield_report(fsr_nom_nm: float = FSR_NOM_NM,
                 delta: float = SPEC_DELTA,
                 sigma_rel: float = SIGMA_REL,
                 n_samples: int = N_SAMPLES,
                 seed: int = SEED,
                 cross_tol: float = 0.01) -> Dict[str, object]:
    """良率完整报告：解析解 ↔ 蒙特卡洛交叉验证 + 判别力扫描。

    cross_check_ok 是 S13 的核心判决：两种独立算法（解析积分 / 数值采样）
    在同一物理定律上的偏差 ≤ cross_tol（1 个百分点）。
    """
    y_an = yield_analytic(fsr_nom_nm, delta, sigma_rel)
    y_mc, diag = monte_carlo_yield(fsr_nom_nm, delta, sigma_rel,
                                   n_samples=n_samples, seed=seed)
    delta_abs = abs(round(y_mc, 6) - y_an)
    # 判别力：工艺容差放大 → 良率必须单调下降（DFY 物理正确性）
    scan = yield_vs_tolerance_scan(fsr_nom_nm=fsr_nom_nm, delta=delta,
                                   sigmas=(0.005, 0.01, 0.02, 0.04),
                                   n_samples=n_samples, seed=seed)
    return {
        "spec": {"fsr_nom_nm": fsr_nom_nm, "delta": delta,
                 "window_nm": [round(fsr_nom_nm * (1 - delta), 4),
                               round(fsr_nom_nm * (1 + delta), 4)],
                 "sigma_rel": sigma_rel, "n_samples": n_samples, "seed": seed},
        "yield_analytic": round(y_an, 6),
        "yield_monte_carlo": round(y_mc, 6),
        "cross_delta": round(delta_abs, 6),
        "cross_tol": cross_tol,
        "cross_check_ok": delta_abs <= cross_tol,
        "monotone_in_sigma": scan["monotone_decreasing"],
        "sigma_scan": scan["rows"],
        "diagnostics": diag,
        "note": ("S13 设计良率锚：解析闭式（高斯容差精确积分，保留 1/L 非线性）"
                 "↔ 蒙特卡洛采样（固定种子）双算法互证，死标量比对；"
                 "LLM 不进判决路径。载体为 B4 环形 FSR 定律，零新物理。"),
    }


def yield_vs_tolerance_scan(fsr_nom_nm: float = FSR_NOM_NM,
                            delta: float = SPEC_DELTA,
                            sigmas: Tuple[float, ...] = (0.005, 0.01, 0.02, 0.04),
                            n_samples: int = N_SAMPLES,
                            seed: int = SEED) -> Dict[str, object]:
    """工艺容差 → 良率扫描（DFY 设计空间，商业演示素材）。

    回答「把光刻容差收紧到 ±0.5% 良率能到多少」这类客户真正关心的问题。
    同时给出单调性断言：σ 增大 → 良率单调下降（否则锚的判别力存疑）。
    """
    rows = []
    for s in sigmas:
        y_an = yield_analytic(fsr_nom_nm, delta, s)
        y_mc, _ = monte_carlo_yield(fsr_nom_nm, delta, s,
                                    n_samples=n_samples, seed=seed)
        rows.append({"sigma_rel": s,
                     "yield_analytic": round(y_an, 6),
                     "yield_monte_carlo": round(y_mc, 6),
                     "cross_delta": round(abs(y_mc - y_an), 6)})
    an_series = [r["yield_analytic"] for r in rows]
    monotone = all(an_series[i] > an_series[i + 1]
                   for i in range(len(an_series) - 1))
    return {"rows": rows, "monotone_decreasing": monotone}
