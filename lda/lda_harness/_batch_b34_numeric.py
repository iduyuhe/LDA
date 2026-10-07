# -*- coding: utf-8 -*-
"""B-34 数值核（Batch B-34 · 光子传感器新征程 PS-M3 衍生锚 · 1 锚 B460）。

物理族 = **波导灵敏度物理链（Hellmann-Feynman 微扰律 vs 有限差分）**——
光子折射率传感器的**核心读出机制**：待测物折射率微扰包层 → 有效折射率变化，
其灵敏度 `S = dneff/dn_clad` 直接决定波长位移 `Δλ = (λ/n_g)·S·Δn`，进而决定 LOD。
本锚把「Hellmann-Feynman 闭式 golden `dneff/dn_clad = (n_clad/n_eff)·Γ_clad`
（Γ_clad=实际场 L² 份额）」与「有限差分直接 perturb `n_clad` 重算 `n_eff`」做成一道
**方法学独立**的物理定律锚，**真正对齐** PS-M2 留下的待办 B460（原口径不一致偏差 44%）。

| 锚 | 被测标量 | golden（解析闭式） | candidate（方法学独立） |
|---|---|---|---|
| **B460** | 平板波导**灵敏度** `dneff/dn_clad` | 闭式 HF 微扰 `S=(n_clad/n_eff)·Γ_clad`（Γ=实际场 L² 份额，平板解析场） | 有限差分：perturb `n_clad` ±δ → 重解 `n_eff` → 中心差商 |

残差来源 = **离散差分 + 数值积分**误差（中心差商 O(δ²)；Γ 解析闭式无离散误差）；
随 `δ` 缩小**单调收敛**，随积分网格加密残差进一步下降。

判据 D：固定几何（n_f,n_clad,d,λ），只扫**候选自身离散参数** `dp`（模块 docstring 明标）。
        窗口铁律 `1e-15 < 粗端残差 < tol`；随 dp 严格单调下降；默认档残差 > 1e-12；
        `|golden|/tol ≥ 13.5`；余量 `tol/|Δ| ≥ 2`。收敛阶数字**一律来自实测**，不按标称阶写死。

🔴 同源体检（实 grep 全仓，排除 `.git/__pycache__/node_modules/lda_cuda_venv/reports/dist` 噪声）：
    · `hellmann|feynman|dneff/dn|灵敏度.*波导|sensitivity.*waveguide|Γ_clad|gamma_clad`
      在 `BENCHMARK_DEFS` 的 title/metric/oracle/note/candidate_desc 内 **0 命中**
      ⇒ **HF 波导灵敏度族零锚占用**（本批为本族首锚）。
    · 与 PS-M0 `bulk_sensitivity`（整包层/顶部暴露 FD 灵敏度）**同源异形**：PS-M0 只算
      FD 灵敏度，未与 HF 闭式 golden 对齐；本锚是其「判决化 + 口径对齐」封装，golden 为
      HF 闭式（PS-M0 没有），candidate 同为 FD 但判据 D 扫描 + 常驻账本。
    · 与既有 `B2(n_eff)` **不同**：B2 测的是 `n_eff` 本身（闭式 vs 数值微分），本锚测的是
      `n_eff` 对包层折射率的**导数灵敏度**——被测标量、物理意义、数值机制三处均不同
      ⇒ **非重复计数**。

🔴 血案预防：
    1. Γ_clad 必须用**实际场**的 L² 份额（本锚从标量 TE 方程标准 L² 内积推导：
       `δ(β²)=k0²·2n_c·δn_c·∫_clad E²dx`，归一化 `∫E²dx=1` ⇒ `dneff/dn_clad=(n_c/n_eff)·Γ_L2`）；
       不得用近似/经验 Γ（PS-M2 待办 B460 当初 44% 偏差即源于 Γ 口径不一致）。
    2. 平板场为解析闭式 ⇒ Γ 精确；golden 与 FD 应机器精度吻合（非约等）。
    3. 候选返回 `np.float64` ⇒ 适配层再 `float()` 包裹一次（防 numpy 标量泄漏到 JSON）。
    4. 平板须为导模（V>0 恒有 TE0）；若 n_f≤n_c（无限制）⇒ 求解器返回 nan，守卫必红。

诚实边界：
    · 几何参数为**设计示例**（SOI 220nm 平板 / 水包层），结论只可用于数值方法与量级，
      不得作制造/性能宣称。
    · 候选是离散差分近似（非电磁全波）；本锚只证明「HF 微扰闭式 = 有限差分」这一物理事实，
      量级正确、物理站得住（波导传感器灵敏度是标准读出量）。
    · 零商业依赖（纯 numpy + math）。
"""
from __future__ import annotations

import math

import numpy as np


# ===========================================================================
# 对称平板波导 TE0 解析求解（bisection 解 u = V·cos(u)）
# ===========================================================================
def slab_te0_neff(n_f: float, n_c: float, d_um: float, wl_um: float) -> float:
    """对称平板波导 TE0 有效折射率（解析特征方程 + bisection）。

    半厚度 a=d/2；u=κa, w=γa, u²+w²=V², V=a·k0·√(n_f²−n_c²)；
    TE0 特征方程 u = V·cos(u)（u∈(0,π/2) 恒有根）。
    返回 n_eff = √(n_f² − (κ/k0)²)；无导模（n_f≤n_c）⇒ nan。
    """
    if n_f <= n_c:
        return float("nan")
    k0 = 2.0 * math.pi / wl_um
    a = 0.5 * d_um
    K2 = (n_f ** 2 - n_c ** 2) * (k0 ** 2)      # = K²
    V = a * math.sqrt(K2)                        # = a·K
    # g(u) = u − V·cos(u);  g(0)=−V<0, g(π/2)=π/2>0 ⇒ 根在 (0,π/2)
    lo, hi = 0.0, math.pi / 2.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if mid - V * math.cos(mid) < 0.0:
            lo = mid
        else:
            hi = mid
    u = 0.5 * (lo + hi)
    kappa = u / a
    neff2 = n_f ** 2 - (kappa / k0) ** 2
    if neff2 <= 0.0:
        return float("nan")
    return math.sqrt(neff2)


def slab_gamma_clad(n_f: float, n_c: float, d_um: float, wl_um: float,
                    neff: float) -> float:
    """实际场 L² 份额 Γ_clad（解析闭式，支持数值积分互验）。

    场：芯 |x|≤a: E=E0·cos(κx)；包层 |x|≥a: E=E0·cos(κa)·exp(−γ(|x|−a))。
    P_core(L²)=a + sin(2u)/(2κ)；P_clad(L²)=cos²(u)/γ；Γ=P_clad/(P_core+P_clad)。
    """
    if not math.isfinite(neff) or n_f <= n_c:
        return float("nan")
    k0 = 2.0 * math.pi / wl_um
    a = 0.5 * d_um
    K2 = (n_f ** 2 - n_c ** 2) * (k0 ** 2)
    V = a * math.sqrt(K2)
    u = None
    lo, hi = 0.0, math.pi / 2.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if mid - V * math.cos(mid) < 0.0:
            lo = mid
        else:
            hi = mid
    u = 0.5 * (lo + hi)
    kappa = u / a
    gamma = math.sqrt(V * V - u * u) / a          # = γ
    P_core = a + math.sin(2.0 * u) / (2.0 * kappa)
    P_clad = (math.cos(u) ** 2) / gamma
    return P_clad / (P_core + P_clad)


def slab_gamma_clad_numeric(n_f: float, n_c: float, d_um: float, wl_um: float,
                            neff: float, n_pts: int = 400009) -> float:
    """Γ_clad 数值积分互验（覆盖 ±12a 区间，指数尾充分收敛，避免解析符号错）。"""
    if not math.isfinite(neff) or n_f <= n_c:
        return float("nan")
    k0 = 2.0 * math.pi / wl_um
    a = 0.5 * d_um
    K2 = (n_f ** 2 - n_c ** 2) * (k0 ** 2)
    V = a * math.sqrt(K2)
    lo, hi = 0.0, math.pi / 2.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if mid - V * math.cos(mid) < 0.0:
            lo = mid
        else:
            hi = mid
    u = 0.5 * (lo + hi)
    kappa = u / a
    gamma = math.sqrt(V * V - u * u) / a
    x = np.linspace(-12.0 * a, 12.0 * a, n_pts)
    E = np.where(np.abs(x) <= a,
                 np.cos(kappa * x),
                 np.cos(kappa * a) * np.exp(-gamma * (np.abs(x) - a)))
    E2 = E ** 2
    # 在全格点上零化「非包层」区域再积分（避免在 x=±a 处因掩码切分产生
    # 半步缺口误算；Γ_clad = 包层积分 / 总量 严格成立）。
    E2_clad = np.where(np.abs(x) > a, E2, 0.0)
    clad_int = float(np.trapezoid(E2_clad, x))
    total_int = float(np.trapezoid(E2, x))
    if total_int <= 0.0:
        return float("nan")
    return float(clad_int / total_int)


# ===========================================================================
# B460 · HF 闭式 golden + FD candidate
# ===========================================================================
def sensitivity_golden(n_f: float, n_c: float, d_um: float, wl_um: float) -> float:
    """golden：Hellmann-Feynman 微扰闭式 `S=(n_clad/n_eff)·Γ_clad`（Γ=实际场 L² 份额）。

    推导（标量 TE 方程，标准 L² 内积归一化 ∫E²dx=1）：
      δ(β²) = k0²·2n_c·δn_c·∫_clad E²dx ⇒ dneff/dn_c = (n_c/n_eff)·Γ_L2。
    """
    neff = slab_te0_neff(n_f, n_c, d_um, wl_um)
    if not math.isfinite(neff):
        return float("nan")
    gamma_c = slab_gamma_clad(n_f, n_c, d_um, wl_um, neff)
    return (n_c / neff) * gamma_c


#: golden 入口别名（与 `golden_<bid>` 命名契约一致）
golden_b460 = sensitivity_golden


def sensitivity_fd(n_f: float, n_c: float, d_um: float, wl_um: float,
                  dp: float = 1e-4) -> float:
    """候选：有限差分 perturb `n_clad` ± dp → 重解 n_eff → 中心差商。"""
    nm = slab_te0_neff(n_f, n_c - dp, d_um, wl_um)
    np_ = slab_te0_neff(n_f, n_c + dp, d_um, wl_um)
    if not (math.isfinite(nm) and math.isfinite(np_)):
        return float("nan")
    return (np_ - nm) / (2.0 * dp)


#: 候选入口别名（与 `cand_<bid>` 命名契约一致）
cand_b460 = sensitivity_fd


# ===========================================================================
# 逐锚默认档 / 判据 D 扫描网格 / tol
# ===========================================================================
#: 默认档 = 判据 D 扫描网格**末端**（血案：默认档必须等于扫描末端）
_N_BY_BID = {
    "B460": 1e-6,
}
#: 判据 D 扫描网格（6 档 · 等比加密 ⇒ 收敛型；覆盖 `1e-15 < 粗端 < tol` 窗口）
#   名义 O(δ²) 收敛，实测比值来自运行，不写死标称阶。
_GRID_BY_BID = {
    "B460": [1e-2, 5e-3, 2e-3, 1e-3, 5e-4, 1e-6],
}
#: 逐锚 tol（按「余量 ≥ 2 且 |golden|/tol ≥ 13.5、粗端 < tol」标定；只收紧不放松）
_TOL_BY_BID = {
    "B460": 1e-3,
}

# 默认几何（SOI 220nm 平板 / 水包层 @1550nm）——设计示例参数
_DEFAULT_GEO = dict(n_f=3.4777, n_c=1.33, d_um=0.22, wl_um=1.55)

_CASES = [
    ("B460", sensitivity_golden, sensitivity_fd, _DEFAULT_GEO),
]


if __name__ == "__main__":
    print("=== B-34 波导灵敏度 HF 闭式 vs FD（B-460）自检 ===")
    print("\n%-6s %16s %18s %12s %10s %-9s %-9s %s"
          % ("锚", "golden", "cand(默认档)", "|Δ|", "margin", "基线>1e-12", "gold/tol", "判定"))
    bad = 0
    for bid, gf, cf, p in _CASES:
        g = gf(**p)
        c = cf(dp=_N_BY_BID[bid], **p)
        dd = abs(g - c)
        tol = _TOL_BY_BID[bid]
        margin = (tol / dd) if dd > 0 else float("inf")
        base_ok = dd > 1e-12
        gr = abs(g) / tol
        ok = (margin >= 2.0) and base_ok and (gr >= 13.5)
        bad += 0 if ok else 1
        print("%-6s %16.10f %18.10f %12.3e %10.1f %-9s %-9.1f %s"
              % (bid, g, c, dd, margin, base_ok, gr, "OK" if ok else "BAD"))

    print("\n--- 判据 D 扫描（残差随 dp 缩小单调下降；比值来自实测）---")
    for bid, gf, cf, p in _CASES:
        g = gf(**p)
        grid = _GRID_BY_BID[bid]
        row, prev, mono, ratios = [], None, True, []
        for dp in grid:
            dd = abs(g - cf(dp=dp, **p))
            if prev is not None:
                ratio = (prev / dd) if dd > 0 else float("nan")
                ratios.append(ratio)
                if dd > prev:
                    mono = False
                row.append("%g:%.2e(x%.2f)" % (dp, dd, ratio))
            else:
                row.append("%g:%.2e" % (dp, dd))
            prev = dd
        d_last, d_first = abs(g - cf(dp=grid[-1], **p)), abs(g - cf(dp=grid[0], **p))
        tol = _TOL_BY_BID[bid]
        print("%-6s %-68s %-8s 比值 %.2f~%.2f  粗端>1e-15:%s  粗端<tol:%s  默认档>1e-12:%s"
              % (bid, "  ".join(row), "MONO" if mono else "NONMONO",
                 min(ratios), max(ratios), d_first > 1e-15, d_first < tol, d_last > 1e-12))

    # 跨源一致：Γ 解析 vs 数值积分（验证 docstring 血案预防 1 的口径正确）
    neff0 = slab_te0_neff(**_DEFAULT_GEO)
    g_an = slab_gamma_clad(**_DEFAULT_GEO, neff=neff0)
    g_num = slab_gamma_clad_numeric(**_DEFAULT_GEO, neff=neff0)
    print("\n跨源一致（Γ 解析 vs 数值积分，1e-6 阈值）：|Δ|=%.3e ⇒ %s"
          % (abs(g_an - g_num), "OK" if abs(g_an - g_num) < 1e-6 else "MISMATCH"))
    bad += 0 if abs(g_an - g_num) < 1e-6 else 1

    print("\nBAD =", bad, "（应为 0）")
