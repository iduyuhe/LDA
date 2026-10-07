# -*- coding: utf-8 -*-
"""B-33 数值核（Batch B-33 · 光子传感器新征程 PS-M2 衍生锚 · 1 锚 B459）。

物理族 = **洛伦兹谐振线型斜率极值**——光子传感器（谐振环 / FP 腔折射率传感）读出的
**关键灵敏度指标**：谐振峰越陡（斜率越大），单位折射率变化对应的透射变化越大 ⇒
折射率分辨率越高。本锚把「洛伦兹线型 |dT/dλ|_max」做成一道**方法学独立**的物理定律锚。

| 锚 | 被测标量 | golden（解析闭式） | candidate（方法学独立） |
|---|---|---|---|
| **B459** | 洛伦兹谐振线型**最大绝对斜率** | 闭式 `slope_closed = depth·(3√3/4)/FWHM` | 等距采样洛伦兹线型 + 中心差分 `np.gradient` 取 `|dT/dλ|` 最大值 |

残差来源 = **离散采样 + 中心差分**的数值微分误差（采样点越密，最大斜率越接近解析极值）；
随采样点数 `n` 增大**单调收敛**（实测 O(h²)，中心差分标称阶）。

判据 D：固定物理参数（depth, FWHM），只扫**候选自身离散参数** `n`（模块 docstring 明标）。
        窗口铁律 `1e-15 < 粗端残差 < tol`；随 n 严格单调下降；默认档残差 > 1e-12；
        `|golden|/tol ≥ 13.5`；余量 `tol/|Δ| ≥ 2`。收敛阶数字**一律来自实测**，不按标称阶写死。

🔴 同源体检（实 grep 全仓，排除 `.git/__pycache__/node_modules/lda_cuda_venv/reports/dist` 噪声）：
    · `洛伦兹|lorentz|谐振.*斜率|dT/dλ|slope.*resonance|线型.*斜率|resonance_slope`
      在 `BENCHMARK_DEFS` 的 title/metric/oracle/note/candidate_desc 内 **0 命中**
      ⇒ **洛伦兹线型斜率族零锚占用**（本批为本族首锚）。
    · 与既有「谐振/环」锚 B4（FSR）/B11（环谱匹配）/B12（谐振频率）**不同**：那些测的是
      频率/FSR/谱形匹配度，无任一计算「洛伦兹线型 |dT/dλ|_max 闭式 vs 数值微分」，
      被测标量、数值机制、golden 三处均不同 ⇒ **非重复计数**。
    · 与同征程 PS-M2 模块 `lda_l2.ps_m2.resonance_slope_max`（已存在工具函数）**同源异形**：
      本锚是其「判决化封装」——独立自测 + 判据 D 扫描 + 常驻账本，golden 闭式同一推导，
      但候选离散参数与标定为账本口径，不与之共用可变状态。

🔴 血案预防：
    1. slope 与 T_bg、λ0 **无关**（只依赖 depth、FWHM）——golden 闭式已剔除这两项；
       candidate 内部固定 T_bg、λ0 仅为构造线型，验证其不影响结果（见 §自检跨源一致）。
    2. FWHM 须 > 0，否则闭式发散（return inf）；candidate 同步守卫。
    3. 候选返回 `np.float64` ⇒ 适配层再 `float()` 包裹一次（防 numpy 标量泄漏到 JSON）。
    4. 采样区间取 ±3·FWHM（覆盖线型主体），过窄会漏掉 argmax 附近的斜率极值点。

诚实边界：
    · depth/FWHM 为**设计示例参数**（非实测谐振峰），结论只可用于数值方法与量级，
      不得作制造/性能宣称。
    · 候选是离散采样 + 中心差分的数值微分近似（非电磁全波）；本锚只证明「数值微分收敛到
      解析斜率极值」这一数学事实，量级正确、物理站得住（谐振斜率传感是标准读出量）。
    · 零商业依赖（纯 numpy + math）。
"""
from __future__ import annotations

import math

import numpy as np


# ===========================================================================
# B459 · 洛伦兹谐振线型最大绝对斜率
# ===========================================================================
def slope_closed(depth: float, FWHM: float) -> float:
    """golden：洛伦兹线型最大绝对斜率（解析闭式，单位 1/λ）。

    线型：T(λ) = T_bg − depth·(FWHM/2)² / ((λ−λ0)² + (FWHM/2)²)
    对 λ 求导取极值 ⇒ |dT/dλ|_max = depth·(3√3/4) / FWHM（与 T_bg、λ0 无关）。
    """
    if FWHM <= 0.0:
        return float("inf")
    return float(depth) * (3.0 * math.sqrt(3.0) / 4.0) / float(FWHM)


#: golden 入口别名（与 `golden_<bid>` 命名契约一致；`slope_closed` 为物理语义名）
golden_b459 = slope_closed


def cand_b459(depth: float = 0.9, FWHM: float = 0.1, n: int = 4001,
              T_bg: float = 1.0, lam0: float = 1.55) -> float:
    """候选：等距采样洛伦兹线型 + 中心差分取 |dT/dλ| 最大值。

    离散参数 = 采样点数 `n`（覆盖 ±3·FWHM 区间）。返回 np.float ⇒ 适配层再 float() 包裹。
    T_bg、λ0 仅用于构造线型，解析上不影响斜率极值（见 docstring 血案预防 1）。
    """
    if FWHM <= 0.0:
        return float("inf")
    span = 3.0 * float(FWHM)
    lam = np.linspace(lam0 - span, lam0 + span, int(n))
    gamma2 = (float(FWHM) / 2.0) ** 2
    T = T_bg - float(depth) * gamma2 / ((lam - lam0) ** 2 + gamma2)
    dT = np.gradient(T, lam)              # 中心差分，O(h²)
    return float(np.max(np.abs(dT)))


# ===========================================================================
# 逐锚默认档 / 判据 D 扫描网格 / tol
# ===========================================================================
#: 默认档 = 判据 D 扫描网格**末端**（血案：默认档必须等于扫描末端）
_N_BY_BID = {
    "B459": 4001,
}
#: 判据 D 扫描网格（5 档 · 等比加密 ⇒ 收敛型；覆盖 `1e-15 < 粗端 < tol` 窗口）
_GRID_BY_BID = {
    "B459": [301, 601, 1201, 2001, 4001],
}
#: 逐锚 tol（按「余量 ≥ 2 且 |golden|/tol ≥ 13.5、粗端 < tol」标定；只收紧不放松）
_TOL_BY_BID = {
    "B459": 5e-2,
}

_CASES = [
    ("B459", slope_closed, cand_b459, {"depth": 0.9, "FWHM": 0.1}),
]


if __name__ == "__main__":
    print("=== B-33 洛伦兹谐振线型斜率极值（B-459）自检 ===")
    print("\n%-6s %16s %18s %12s %10s %-9s %-9s %s"
          % ("锚", "golden", "cand(默认档)", "|Δ|", "margin", "基线>1e-12", "gold/tol", "判定"))
    bad = 0
    for bid, gf, cf, p in _CASES:
        g = gf(**p)
        c = cf(n=_N_BY_BID[bid], **p)
        dd = abs(g - c)
        tol = _TOL_BY_BID[bid]
        margin = (tol / dd) if dd > 0 else float("inf")
        base_ok = dd > 1e-12
        gr = abs(g) / tol
        ok = (margin >= 2.0) and base_ok and (gr >= 13.5)
        bad += 0 if ok else 1
        print("%-6s %16.10f %18.10f %12.3e %10.1f %-9s %-9.1f %s"
              % (bid, g, c, dd, margin, base_ok, gr, "OK" if ok else "BAD"))

    print("\n--- 判据 D 扫描（残差随 n 单调下降；比值来自实测，不按标称阶写死）---")
    for bid, gf, cf, p in _CASES:
        g = gf(**p)
        grid = _GRID_BY_BID[bid]
        row, prev, mono, ratios = [], None, True, []
        for nn in grid:
            dd = abs(g - cf(n=nn, **p))
            if prev is not None:
                ratio = (prev / dd) if dd > 0 else float("nan")
                ratios.append(ratio)
                if dd > prev:
                    mono = False
                row.append("%d:%.2e(x%.2f)" % (nn, dd, ratio))
            else:
                row.append("%d:%.2e" % (nn, dd))
            prev = dd
        d_last, d_first = abs(g - cf(n=grid[-1], **p)), abs(g - cf(n=grid[0], **p))
        tol = _TOL_BY_BID[bid]
        print("%-6s %-58s %-8s 比值 %.2f~%.2f  粗端>1e-15:%s  粗端<tol:%s  默认档>1e-12:%s"
              % (bid, "  ".join(row), "MONO" if mono else "NONMONO",
                 min(ratios), max(ratios), d_first > 1e-15, d_first < tol, d_last > 1e-12))

    # 跨源一致：改变 T_bg、λ0 不影响候选斜率极值（验证 docstring 血案预防 1）
    c_nominal = cand_b459(0.9, 0.1, 4001)
    c_shifted = cand_b459(0.9, 0.1, 4001, T_bg=2.0, lam0=1.31)
    print("\n跨源一致（T_bg/λ0 改变不影响斜率极值，1e-9 阈值，余量 >> 残差）：|Δ|=%.3e ⇒ %s"
          % (abs(c_nominal - c_shifted),
             "OK" if abs(c_nominal - c_shifted) < 1e-9 else "MISMATCH"))
    bad += 0 if abs(c_nominal - c_shifted) < 1e-9 else 1

    print("\nBAD =", bad, "（应为 0）")
