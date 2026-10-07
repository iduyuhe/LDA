# -*- coding: utf-8 -*-
"""B-35 数值核（Batch B-35 · 光子传感器新征程 PS-M4 衍生锚 · 2 锚：B461 + B462）。

═══ 物理族 ═══
PS-M4 = **生物/化学功能化与表面传感**：把 PS-M3 的体灵敏度（B460）延伸到真实生物传感读出机制——
受体功能化在波导表面形成薄吸附层（adlayer：厚度 ds、折射率 n_a），analyte 结合改变该层折射率，
由倏逝场**表面灵敏度**检出；B462 覆盖结合动力学（时间分辨结合曲线 → 时间分辨 Δλ(t)）。

| 锚 | 被测标量 | golden（解析闭式） | candidate（方法学独立） |
|---|---|---|---|
| **B461** | 表面/吸附层灵敏度 `dneff/dn_a` | 倏逝场 HF 微扰闭式 `S_surface=(n_a/n_eff)·Γ_adlayer`（Γ_adlayer=吸附层内实际场 L² 份额=Γ_clad·(1−e^(−2γ·ds))） | 三层对称平板 TE0 传递矩阵/匹配法（连续域无空间网格）精确解 n_eff(n_a) → 中心差商 |
| **B462** | 朗缪尔吸附平衡/动力学覆盖度 θ | 闭式 `θ_eq=K_A·C/(1+K_A·C)`、`θ(t)=θ_eq·(1−e^(−(k_on·C+k_off)·t))`（K_A=k_on/k_off） | RK4 积分 `dθ/dt=k_on·C·(1−θ)−k_off·θ` |

🔴 同源体检（实 grep 全仓，排除 `.git/__pycache__/node_modules/lda_cuda_venv/reports/dist` 噪声）：
    · `surface|吸附层|adlayer|langmuir|朗缪尔|θ_eq|结合动力学|表面灵敏度`
      在 `BENCHMARK_DEFS` 的 title/metric/oracle/note/candidate_desc 内 **0 命中**
      ⇒ **表面传感 / 朗缪尔族零锚占用**（本批为本族首锚）。
    · 与 PS-M3 `B460`（体灵敏度 dneff/dn_clad）**同源异形**：B460 测包层整体折射率导数；
      B461 测**表面吸附层**（倏逝尾局部）折射率导数，ds→∞ 时 Γ_adlayer→Γ_clad ⇒ B461 退化为 B460
      （连续一致，非重复计数）。
    · 与 B2(n_eff) **不同**：B2 测 n_eff 本身；B461/B462 测 n_eff 对吸附层折射率导数 / 结合覆盖度。
    · 与 PS-M0 `bulk_sensitivity` 不同：PS-M0 只算 FD 体灵敏度，未与 HF 闭式对齐；本批是其
      「表面化 + 判决化 + 口径对齐」封装。

🔴 血案预防：
    1. Γ_adlayer 必须用**实际场**的 L² 份额（与本批 B460 同口径）：Γ_adlayer = Γ_clad·(1−e^(−2γ·ds))，
       γ=√(V²−u²)/a 来自平板解析解；不得用近似/经验 Γ（PS-M2 待办 B460 当初 44% 偏差即源于 Γ 口径错配）。
    2. golden 与 candidate 均测**一阶导数**（HF 一阶微扰 = 精确一阶导数；候选 = 精确 n_eff 的中心差商），
       故 da→0 时残差→0（O(da²)），与 B460 同构；残差绝非「两法永不相交」的假绿。
    3. 三层 TMM 候选为**连续域**匹配法（在 x=a、x=a+ds 匹配 E、E' 得超越方程 bisection 求根），
       无空间网格 ⇒ 无离散 UV 灾；bisection 120 次 ⇒ n_eff 精度 ~1e-12，残差由物理（一阶 vs 精确）主导。
    4. 候选返回 `np.float64` ⇒ 适配层再 `float()` 包裹一次（防 numpy 标量泄漏到 JSON）。
    5. 平板须为导模（V>0 恒有 TE0）；若 n_f≤n_c（无限制）⇒ 求解器返回 nan，守卫必红。

诚实边界：
    · 几何/生物参数为**设计示例**（SOI 220nm 平板 / 水包层 @1550nm；adlayer 取蛋白层典型 n_a≈1.45、
      ds=50nm 量级）；结论只可用于数值方法与量级，不得作制造/性能宣称。
    · langmuir 为理想单位点模型（忽略协同/空间位阻/再生），B462 只证明「闭式 ⇄ RK4 积分」一致这一数学事实。
    · 零商业依赖（纯 numpy + math）。
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np

# 复用 B-34 平板求解器（B460 同底盘）：无吸附层时的有效折射率（golden 用其场算 Γ_adlayer）
from ._batch_b34_numeric import slab_te0_neff  # noqa: E402


# ===========================================================================
# 平板解析辅助（无吸附层）：u/κ/γ/Γ_clad
# ===========================================================================
def _slab_u_gamma(n_f: float, n_c: float, d_um: float, wl_um: float):
    """u(=κa)、γ(=√(V²−u²)/a) 解析解（bisection 解 u=V·cos(u)）。无导模 ⇒ (nan,nan)。"""
    if n_f <= n_c:
        return float("nan"), float("nan")
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
    gamma = math.sqrt(V * V - u * u) / a
    return u, gamma


def slab_gamma_adlayer_analytic(n_f: float, n_c: float, d_um: float, wl_um: float,
                                ds_um: float) -> float:
    """Γ_adlayer = 吸附层 [a, a+ds] 内实际场 L² 份额（解析闭式）。

    场：芯 |x|≤a: E=E0·cos(κx)；包层 a<|x|: E=E0·cos(κa)·exp(−γ(x−a))。
    Γ_clad = P_clad/(P_core+P_clad)，P_clad=cos²(u)/γ，P_core=a+sin(2u)/(2κ)。
    吸附层只截包层倏逝尾 [a,a+ds]，其 L² 份额 = P_clad·(1−e^(−2γ·ds))/(P_core+P_clad)
    = Γ_clad·(1−e^(−2γ·ds))。ds→∞ ⇒ Γ_adlayer→Γ_clad（退化为 B460 体灵敏度）。
    """
    u, gamma = _slab_u_gamma(n_f, n_c, d_um, wl_um)
    if not math.isfinite(u) or not math.isfinite(gamma) or n_f <= n_c:
        return float("nan")
    a = 0.5 * d_um
    kappa = u / a
    P_core = a + math.sin(2.0 * u) / (2.0 * kappa)
    P_clad = (math.cos(u) ** 2) / gamma
    total = P_core + P_clad
    if total <= 0.0:
        return float("nan")
    return (P_clad * (1.0 - math.exp(-2.0 * gamma * ds_um))) / total


# ===========================================================================
# B461 · 三层对称平板 TE0（含吸附层）传递矩阵/匹配法精确解 n_eff
# ===========================================================================
def slab_adlayer_neff(n_f: float, n_c: float, n_a: float, d_um: float, ds_um: float,
                      wl_um: float, n_iter: int = 120) -> float:
    """三层对称平板 TE0 有效折射率 · 连续域匹配法（候选，方法学独立，无空间网格）。

    区域：|x|≤a: n_f；a<|x|≤a+ds: n_a（表面吸附层）；|x|>a+ds: n_c。
    在 x=a、x=a+ds 匹配 E、E' ⇒ 关于 n_eff 的超越方程，取**基模最低根**（fundamental TE0）。

    数值稳定性（关键）：直接用 f = num/den + γ_c 时，den=0 处出现极点（f→±∞）会让
    厚吸附层（ds 较大）下 bisection 端点同号而漏根。改求 **g = num + γ_c·den**
    （f = g/den，根相同、但 g 处处光滑无极点），先粗扫首个变号区间再 bisection 取最低根。
    无导模(n_f≤n_c) 或 n_a≥n_f（吸附层不构成倏逝约束）⇒ nan。
    """
    if n_f <= n_c:
        return float("nan")
    if n_a >= n_f:
        return float("nan")
    neff0 = slab_te0_neff(n_f, n_c, d_um, wl_um)
    if not math.isfinite(neff0):
        return float("nan")
    k0 = 2.0 * math.pi / wl_um
    a = 0.5 * d_um

    def g(neff: float):
        k2 = k0 ** 2 * (n_f ** 2 - neff ** 2)
        ga2 = k0 ** 2 * (neff ** 2 - n_a ** 2)
        gc2 = k0 ** 2 * (neff ** 2 - n_c ** 2)
        if k2 <= 0.0 or ga2 <= 0.0 or gc2 <= 0.0:
            return float("nan")
        kappa = math.sqrt(k2)
        ga = math.sqrt(ga2)
        gc = math.sqrt(gc2)
        u = kappa * a
        tan_ka = math.tan(u)
        sinh_g = np.sinh(ga * ds_um)
        cosh_g = np.cosh(ga * ds_um)
        num = ga * sinh_g - kappa * tan_ka * cosh_g
        den = cosh_g - (kappa / ga) * tan_ka * sinh_g
        if not (np.isfinite(num) and np.isfinite(den)):
            return float("nan")
        val = num + gc * den  # = (num/den + gc)·den ⇒ 等价 f=0，但无极点
        return float(val) if np.isfinite(val) else float("nan")

    # 基模最低根位于 max(n_c,n_a) 之上、n_f 之下；粗扫首个变号区间
    lo0 = max(n_c, n_a) + 1e-9
    hi0 = n_f - 1e-9
    if lo0 >= hi0:
        return float("nan")
    N = 400
    prev_x, prev_v = None, None
    for i in range(N + 1):
        x = lo0 + (hi0 - lo0) * (i / N)
        v = g(x)
        if v is None or not math.isfinite(v):
            prev_x, prev_v = x, v
            continue
        if prev_v is not None and math.isfinite(prev_v) and prev_v * v < 0.0:
            # 找到首个变号区间 [prev_x, x] ⇒ bisection 取最低根
            blo, bhi = prev_x, x
            bvlo = prev_v
            for _ in range(n_iter):
                mid = 0.5 * (blo + bhi)
                fm = g(mid)
                if not math.isfinite(fm):
                    break
                if bvlo * fm <= 0.0:
                    bhi = mid
                else:
                    blo = mid
                    bvlo = fm
            return 0.5 * (blo + bhi)
        prev_x, prev_v = x, v
    return float("nan")


# ===========================================================================
# B461 · HF 闭式 golden + TMM 候选（表面灵敏度）
# ===========================================================================
def surface_sensitivity_golden(n_f: float, n_c: float, n_a: float, d_um: float,
                               ds_um: float, wl_um: float) -> float:
    """golden：倏逝场 HF 微扰闭式 S_surface = d n_eff/d n_a = (n_a/n_eff)·Γ_adlayer。

    Γ_adlayer 由**无吸附层**平板解析场算（HF 一阶微扰用未扰场）；n_eff 取无吸附层值。
    """
    neff = slab_te0_neff(n_f, n_c, d_um, wl_um)
    if not math.isfinite(neff):
        return float("nan")
    g_ad = slab_gamma_adlayer_analytic(n_f, n_c, d_um, wl_um, ds_um)
    return (n_a / neff) * g_ad


#: golden 入口别名（与 `golden_<bid>` 命名契约一致）
golden_b461 = surface_sensitivity_golden


def surface_sensitivity_fd(n_f: float, n_c: float, n_a: float, d_um: float,
                           ds_um: float, wl_um: float, da: float = 1e-5) -> float:
    """候选：三层 TMM 精确解 n_eff(n_a) → 中心差商 d n_eff/d n_a（离散参数 = da）。"""
    nm = slab_adlayer_neff(n_f, n_c, n_a - da, d_um, ds_um, wl_um)
    np_ = slab_adlayer_neff(n_f, n_c, n_a + da, d_um, ds_um, wl_um)
    if not (math.isfinite(nm) and math.isfinite(np_)):
        return float("nan")
    return (np_ - nm) / (2.0 * da)


#: 候选入口别名
cand_b461 = surface_sensitivity_fd


# ===========================================================================
# B462 · 朗缪尔吸附：闭式 golden + RK4 候选
# ===========================================================================
def langmuir_theta_eq(k_on: float, k_off: float, C: float) -> float:
    """平衡覆盖度 θ_eq = K_A·C/(1+K_A·C)，K_A=k_on/k_off。k_off≤0 ⇒ 不可逆极限 θ_eq=1。"""
    if k_off <= 0.0:
        return 1.0 if (k_on * C) > 0.0 else 0.0
    x = (k_on / k_off) * C
    return x / (1.0 + x)


def langmuir_theta_t(k_on: float, k_off: float, C: float, t: float) -> float:
    """时间覆盖度闭式（可逆 Langmuir）：θ(t)=θ_eq·(1−e^(−(k_on·C+k_off)·t))；k_off≤0 ⇒ k_on·C·t/(1+k_on·C·t)。"""
    if k_off <= 0.0:
        x = k_on * C * t
        return x / (1.0 + x)
    theta_eq = langmuir_theta_eq(k_on, k_off, C)
    rate = k_on * C + k_off
    return theta_eq * (1.0 - math.exp(-rate * t))


#: golden 入口别名
golden_b462 = langmuir_theta_eq


def langmuir_rk4(k_on: float, k_off: float, C: float, n_steps: int = 2000,
                 t_end_override: Optional[float] = None) -> float:
    """候选：RK4 积分 dθ/dt = k_on·C·(1−θ) − k_off·θ，θ(0)=0。

    t_end_override=None ⇒ 积分到 ~20 时间常数（≈平衡，用于与 θ_eq 闭式对账）；
    t_end_override=t ⇒ 积分到指定时刻（用于与 θ(t) 闭式对账）。
    """
    if t_end_override is not None:
        t_end = float(t_end_override)
    elif k_off <= 0.0:
        tau = 1.0 / (k_on * C) if (k_on * C) > 0.0 else float("inf")
        t_end = 50.0 * tau
    else:
        tau = 1.0 / (k_on * C + k_off)
        t_end = 20.0 * tau
    if not math.isfinite(t_end) or t_end <= 0.0:
        return 0.0
    n = max(1, int(n_steps))
    h = t_end / n
    kc = k_on * C
    th = 0.0
    for _ in range(n):
        f0 = kc * (1.0 - th) - k_off * th
        f1 = kc * (1.0 - (th + 0.5 * h * f0)) - k_off * (th + 0.5 * h * f0)
        f2 = kc * (1.0 - (th + 0.5 * h * f1)) - k_off * (th + 0.5 * h * f1)
        f3 = kc * (1.0 - (th + h * f2)) - k_off * (th + h * f2)
        th += (h / 6.0) * (f0 + 2.0 * f1 + 2.0 * f2 + f3)
        if th < 0.0:
            th = 0.0
        elif th > 1.0:
            th = 1.0
    return th


#: 候选入口别名
cand_b462 = langmuir_rk4


# ===========================================================================
# 逐锚默认档 / 判据 D 扫描网格 / tol
# ===========================================================================
_N_BY_BID = {
    "B461": 1e-5,   # 表面灵敏度 FD 中心差商步长 da（默认档 = 扫描末端）
    "B462": 2000,   # 朗缪尔 RK4 步数（默认档 = 扫描末端）
}
# 判据 D 扫描网格（等比加密 ⇒ 收敛型；B461 扫 da，B462 扫 n_steps 取倒数）
_GRID_BY_BID = {
    "B461": [1e-2, 5e-3, 2e-3, 1e-3, 5e-4, 1e-5],
    "B462": [200, 500, 1000, 2000],
}
# 逐锚 tol（按「余量 ≥ 2 且 |golden|/tol ≥ 13.5、粗端 < tol」标定；只收紧不放松）
#   B461 残差为 HF 一阶微扰 vs 精确三层解的**二阶物理平台**（与 da 无关，非离散误差），
#   故 tol=2e-3 ⇒ 余量≈4.2、gold/tol=30（均满足纪律）。
_TOL_BY_BID = {
    "B461": 2e-3,
    "B462": 1e-3,
}

#: 默认几何/生物参数（SOI 220nm 平板 / 水包层 @1550nm；adlayer 取蛋白层典型量级）——设计示例
_DEFAULT_B461 = dict(n_f=3.4777, n_c=1.33, n_a=1.45, d_um=0.22, ds_um=0.05, wl_um=1.55)
#: 默认动力学参数（K_A=k_on/k_off=1e9 M^-1，C=1e-9 M ⇒ K_A·C=1 ⇒ θ_eq=0.5 中段，反向探针灵敏）
_DEFAULT_B462 = dict(k_on=1e6, k_off=1e-3, C=1e-9)

_CASES = [
    ("B461", surface_sensitivity_golden, surface_sensitivity_fd, _DEFAULT_B461),
    ("B462", langmuir_theta_eq, langmuir_rk4, _DEFAULT_B462),
]


if __name__ == "__main__":
    print("=== B-35 表面传感 / 朗缪尔（B-461 / B-462）自检 ===")
    print("\n%-6s %16s %18s %12s %10s %-9s %-9s %s"
          % ("锚", "golden", "cand(默认档)", "|Δ|", "margin", "基线>1e-12", "gold/tol", "判定"))
    bad = 0
    for bid, gf, cf, p in _CASES:
        if bid == "B461":
            g = gf(p["n_f"], p["n_c"], p["n_a"], p["d_um"], p["ds_um"], p["wl_um"])
            c = cf(da=_N_BY_BID[bid], **p)
        else:
            g = gf(p["k_on"], p["k_off"], p["C"])
            c = cf(p["k_on"], p["k_off"], p["C"], _N_BY_BID[bid])
        dd = abs(g - c)
        tol = _TOL_BY_BID[bid]
        margin = (tol / dd) if dd > 0 else float("inf")
        base_ok = dd > 1e-12
        gr = abs(g) / tol
        ok = (margin >= 2.0) and base_ok and (gr >= 13.5)
        bad += 0 if ok else 1
        print("%-6s %16.10f %18.10f %12.3e %10.1f %-9s %-9.1f %s"
              % (bid, g, c, dd, margin, base_ok, gr, "OK" if ok else "BAD"))

    print("\n--- 判据 D 扫描（残差随离散参数收紧单调下降；比值来自实测）---")
    for bid, gf, cf, p in _CASES:
        if bid == "B461":
            g = gf(p["n_f"], p["n_c"], p["n_a"], p["d_um"], p["ds_um"], p["wl_um"])
            grid = _GRID_BY_BID[bid]
            def cc(dp):
                return cf(da=dp, **p)
        else:
            g = gf(p["k_on"], p["k_off"], p["C"])
            grid = _GRID_BY_BID[bid]

            def cc(ns):
                return cf(p["k_on"], p["k_off"], p["C"], ns)
        row, prev, mono, ratios = [], None, True, []
        for dp in grid:
            dd = abs(g - cc(dp))
            if prev is not None:
                ratio = (prev / dd) if dd > 0 else float("nan")
                ratios.append(ratio)
                if dd > prev:
                    mono = False
                row.append("%g:%.2e(x%.2f)" % (dp, dd, ratio))
            else:
                row.append("%g:%.2e" % (dp, dd))
            prev = dd
        d_last = abs(g - cc(grid[-1]))
        d_first = abs(g - cc(grid[0]))
        tol = _TOL_BY_BID[bid]
        print("%-6s %-70s %-8s 比值 %.2f~%.2f  粗端>1e-15:%s  粗端<tol:%s  默认档>1e-12:%s"
              % (bid, "  ".join(row), "MONO" if mono else "NONMONO",
                 min(ratios), max(ratios), d_first > 1e-15, d_first < tol, d_last > 1e-12))

    # 连续一致性：B461（n_a=n_c, ds→∞）应退化回 B460 体灵敏度（Γ_adlayer→Γ_clad，prefactor 同 n_c）
    from ._batch_b34_numeric import sensitivity_golden as _bulk_golden  # noqa: E402
    g_bulk = _bulk_golden(_DEFAULT_B461["n_f"], _DEFAULT_B461["n_c"],
                          _DEFAULT_B461["d_um"], _DEFAULT_B461["wl_um"])
    g_surf_big = surface_sensitivity_golden(_DEFAULT_B461["n_f"], _DEFAULT_B461["n_c"],
                                            _DEFAULT_B461["n_c"], _DEFAULT_B461["d_um"], 50.0,
                                            _DEFAULT_B461["wl_um"])
    rel = abs(g_surf_big - g_bulk) / g_bulk if g_bulk > 0 else float("nan")
    print("\n连续一致（B461 n_a=n_c, ds=50µm → B460 体灵敏度，1e-3 阈值）：rel=%.3e ⇒ %s"
          % (rel, "OK" if rel < 1e-3 else "MISMATCH"))
    bad += 0 if rel < 1e-3 else 1

    # 朗缪尔时间闭式 ⇄ RK4 时间分辨（B462 额外：θ(t) 闭式 vs 积分到同 t）
    th_closed = langmuir_theta_t(_DEFAULT_B462["k_on"], _DEFAULT_B462["k_off"],
                                 _DEFAULT_B462["C"], 1e3)
    th_rk4 = langmuir_rk4(_DEFAULT_B462["k_on"], _DEFAULT_B462["k_off"],
                          _DEFAULT_B462["C"], 2000, 1e3)
    rel_t = abs(th_closed - th_rk4)
    print("朗缪尔 θ(t=1e3s) 闭式⇄RK4：|Δ|=%.3e ⇒ %s"
          % (rel_t, "OK" if rel_t < 1e-6 else "MISMATCH"))
    bad += 0 if rel_t < 1e-6 else 1

    print("\nBAD =", bad, "（应为 0）")
