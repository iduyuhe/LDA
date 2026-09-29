# -*- coding: utf-8 -*-
"""B-31 数值核（Batch B-31 · 量子征程「其余模块可锚量再评估」· 2 锚 B456/B457）

物理族 = **有限维 Fock 截断 × 解析闭式**（弱相干态 WCS 光源的光子数统计）——
延续 B-30 的族机制，但换到 **D-114 `photon_sources` 的 WCS/Poisson 分支**。
来源：量子光学教科书物理定律（人类公共品）—— 弱相干态 |α⟩ 的泊松光子数统计。

| 锚 | 被测标量 | golden（解析闭式） | candidate（方法学独立） |
|---|---|---|---|
| B456 | WCS 单光子概率（有限 Fock 空间） | `μ·e^{−μ}` | 截断 Fock 空间建 WCS 布居 `P(n)=e^{−μ}μⁿ/n!`（D-114 `wcs_probs`）→ **归一** → 读 ρ₁₁ |
| B457 | WCS 多光子污染 P(≥2)（有限 Fock 空间） | `1 − e^{−μ}(1+μ)` | 同 B456 的归一截断密态 → `Tr(ρ·Π_{≥2})` = Σ_{n≥2}ρ_nn |

两者共享的数值机制 = **有限维截断 + 重归一**（截断维数 N = Fock 截断）；残差 = 截断误差，
**非恒等、非地板**（实测见 §自检）。

判据 D：固定物理参数（μ=1.0），只扫**候选自身离散参数** N（截断维数）。
        要求 ①粗端残差 > 1e-13 且 **< tol**（窗口铁律 `1e-15 < 粗端 < tol`）
        ②随 N 严格单调下降 ③默认档残差 > 1e-12（避开 `run_d_criterion_smoke` ③ 红灯）
        ④`|golden|/tol ≥ 13.5` ⑤余量 `tol/|Δ| ≥ 2`。
        **收敛阶/比值数字一律来自实测扫描，不按标称阶写死**（B-19 血案）。
        截断型收敛不是幂律 ⇒ 比值随 N 单调增（超几何型），如实登记，不假称「恰 2^k」。

🔴 同源体检（**实 grep 全仓**，排除 `.git/__pycache__/node_modules/lda_cuda_venv/reports/dist` 噪声）：
    · `wcs|弱相干|weak.?coherent` / `单光子概率|single.?photon.?prob` / `多光子|multiphoton|multi.?photon`
      / `poisson|泊松`（**统计义**，排除静电 Poisson 方程）在 `BENCHMARK_DEFS` 的
      title/metric/oracle/note/candidate_desc 内**全为 0 命中** ⇒ WCS/Poisson 统计族**零锚占用**。
    · **B456/B457 vs B453**（唯一需登记的近邻，同属「有限维 Fock 截断」）——
      B453 = 相干态经**振幅阻尼损耗通道**的输入-输出**保真度**（golden `exp(−|α|²(1−√η)²)`，
      candidate = 建态 + **Kraus 算子求和** + `Tr(ρ_out ρ_in)`）。
      **三方分歧**：①**被测标量不同**（B453 态间保真度 vs 本题**光子数概率** P(1)/P(≥2)）；
      ②**物理构型不同**（B453 有**通道**（振幅阻尼，η<1）vs 本题**无通道**，纯 Fock 截断+重归一）；
      ③**数值格式不同**（B453 Kraus 算子代数 vs 本题**直接读归一布居的对角元 / 对 POVM Π_{≥2} 取迹**
      —— 无 Kraus、无通道）。⇒ **非重复计数**（先例：B452 vs B33 同为 RC 一阶暂态而三处分歧 ⇒ 计新锚；
         B448/B449 同为 Ci 函数不同 X 亦各计一锚）。此判断如实登记，供人工复核；
      **不掩盖**「同属有限维 Fock 截断这一数值机制」这一共同上位结构（B-30 已声明的族属性）。
    · **B456 vs B457**：同截断机制但**被测标量不同**（P(1) 归一单元素 vs P(≥2) POVM 迹）⇒
      按 B448/B449 先例各计一锚。

🔴 血案预防：
    1. `math.factorial(n)` 在 n ≥ 171 溢出 ⇒ 候选内显式 `raise ValueError` 拦住 N > 160；
       布居向量改用**迭代递推** `t_n = t_{n−1}·μ/n`（不直接算 factorial）。
    2. 截断密态**必须归一**后再读观测量（未归一 ⇒ 量级失真、残差被常数偏移主导）。
       归一化正是本族残差的物理来源（有限 Fock 空间必需）。
    3. golden 与 candidate **共用 `lda_qeda.photon_sources` 模块**但调用**不同函数族**
       （`wcs_single_photon_prob`/`wcs_multiphoton_prob` 闭式 vs `wcs_probs` 布居 + 归一 + 迹），
       不是同一函数的两种写法 ⇒ 判据 D 实测有响应（见 §自检）。

诚实边界：
    · 参数 μ=1.0 为**设计预算值**（WCS 单光子源参考点，`μe^{−μ}` 在此取极大 1/e），本批**无实测锚**；
      结论只可用于预算与量级，不得作性能宣称。
    · 截断型收敛**不是幂律**：比值随 N 单调增（超几何型）；`tol` 按「余量 ≥ 2 且
      `|golden|/tol ≥ 13.5`、粗端 < tol」逐锚标定，不按标称阶设定。
    · 残差主体在 N = 4~10 段（截断尾概率主导）；默认档 N=10 残差均 ≫ 1e-12，
      符合 `run_d_criterion_smoke` ③。
    · 零商业依赖（纯 numpy + 本项目 `lda_qeda` 纯净模块）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_LDA_DIR = Path(__file__).resolve().parents[1]        # …/lda（给出 `lda_qeda` 包）
_PS = None


def _qeda():
    """双路兜底导入 `lda_qeda.photon_sources`（缓存）。

    🔴 该模块是**本项目自研纯净模块**（纯 numpy、零第三方），非外部依赖；
    本批沿用 B-30 的做法，把它接入账本判决路径。
    """
    global _PS
    if _PS is not None:
        return _PS
    try:
        from lda_qeda import photon_sources as _ps_mod
    except ImportError:                                # 裸模块名回退
        if str(_LDA_DIR) not in sys.path:
            sys.path.insert(0, str(_LDA_DIR))
        import photon_sources as _ps_mod               # type: ignore
    _PS = _ps_mod
    return _PS


# ===========================================================================
# 公共工具
# ===========================================================================
_N_MAX_SAFE = 160          # math.factorial 溢出前上限（血案 1）


def _guard_n(n) -> int:
    nn = int(n)
    if nn < 2 or nn > _N_MAX_SAFE:
        raise ValueError("截断维数 N 须 ∈ [2, %d]（factorial 溢出护栏）" % _N_MAX_SAFE)
    return nn


def _mu_guard(mu) -> float:
    m = float(mu)
    if not (m >= 0.0):
        raise ValueError("平均光子数 μ 须 ≥ 0")
    return m


def _truncated_wcs_state(mu, N: int) -> np.ndarray:
    """截断 + **归一** 的 WCS 密态 ρ（对角）：有限 Fock 空间里模拟器持有的态（血案 2）。

    布居由 D-114 `wcs_probs`（泊松闭式）给出，再按迹归一 ⇒ ρ_nn = P(n)/Σ_{k≤N}P(k)。
    """
    ps = _qeda()
    nn = _guard_n(N)
    m = _mu_guard(mu)
    pops = ps.wcs_probs(m, nn)
    vec = np.array([float(pops[k]) for k in range(nn + 1)], dtype=float)
    z = float(vec.sum())
    if z <= 0.0:
        raise ValueError("截断布居总概率为 0（N/μ 非法）")
    return np.diag(vec / z)


# ===========================================================================
# B456 · WCS 单光子概率（有限 Fock 空间）
# ===========================================================================
def golden_b456(mu):
    """P(1) = μ·e^{−μ}（教科书：WCS 光子数泊松，单光子概率；μ=1 取极大 1/e）。"""
    ps = _qeda()
    return float(ps.wcs_single_photon_prob(_mu_guard(mu)))


def cand_b456(mu, N: int = 10):
    """候选：截断 Fock 空间建归一 WCS 密态 ⟶ 读 ρ₁₁（= 归一单光子布居）。"""
    rho = _truncated_wcs_state(mu, N)
    return float(np.real(rho[1, 1]))


# ===========================================================================
# B457 · WCS 多光子污染 P(≥2)（有限 Fock 空间）
# ===========================================================================
def golden_b457(mu):
    """P(≥2) = 1 − e^{−μ}(1+μ)（教科书：WCS 多光子污染，单光子源关键限值）。"""
    ps = _qeda()
    return float(ps.wcs_multiphoton_prob(_mu_guard(mu)))


def cand_b457(mu, N: int = 10):
    """候选：同 B456 的归一截断密态 ⟶ Tr(ρ·Π_{≥2}) = Σ_{n≥2} ρ_nn。"""
    rho = _truncated_wcs_state(mu, N)
    return float(np.real(np.diag(rho)[2:].sum()))


# ===========================================================================
# 逐锚默认档 / 判据 D 扫描网格 / tol
# ===========================================================================
#: 默认档 = 判据 D 扫描网格**末端**（B-16 血案：默认档必须等于扫描末端）
_N_BY_BID = {
    "B456": 10,
    "B457": 10,
}
#: 判据 D 扫描网格（4 档，覆盖 `1e-15 < 粗端 < tol` 窗口；截断型 ⇒ 等比不适用，用等差）
_GRID_BY_BID = {
    "B456": [4, 6, 8, 10],
    "B457": [4, 6, 8, 10],
}
#: 逐锚 tol（按「余量 ≥ 2 且 |golden|/tol ≥ 13.5、粗端 < tol」标定；只收紧不放松）
_TOL_BY_BID = {
    "B456": 1e-2,
    "B457": 1e-2,
}

_CASES = [
    ("B456", golden_b456, cand_b456, {"mu": 1.0}),
    ("B457", golden_b457, cand_b457, {"mu": 1.0}),
]


if __name__ == "__main__":
    print("=== B-31 WCS/Poisson 有限维 Fock 截断 × 解析闭式（量子征程再评估）自检 ===")
    print("\n%-6s %16s %18s %12s %10s %-9s %-9s %s"
          % ("锚", "golden", "cand(默认档)", "|Δ|", "margin", "基线>1e-12", "gold/tol", "判定"))
    bad = 0
    for bid, gf, cf, p in _CASES:
        g = gf(**p)
        c = cf(N=_N_BY_BID[bid], **p)
        dd = abs(g - c)
        tol = _TOL_BY_BID[bid]
        margin = (tol / dd) if dd > 0 else float("inf")
        base_ok = dd > 1e-12
        gr = abs(g) / tol
        ok = (margin >= 2.0) and base_ok and (gr >= 13.5)
        bad += 0 if ok else 1
        print("%-6s %16.10f %18.10f %12.3e %10.1f %-9s %-9.1f %s"
              % (bid, g, c, dd, margin, base_ok, gr, "OK" if ok else "BAD"))

    print("\n--- 判据 D 扫描（残差随截断维数 N 单调下降；比值来自实测，不按标称阶写死）---")
    for bid, gf, cf, p in _CASES:
        g = gf(**p)
        grid = _GRID_BY_BID[bid]
        row, prev, mono, ratios = [], None, True, []
        for nn in grid:
            dd = abs(g - cf(N=nn, **p))
            if prev is not None:
                ratio = (prev / dd) if dd > 0 else float("nan")
                ratios.append(ratio)
                if dd > prev:
                    mono = False
                row.append("%d:%.2e(x%.2f)" % (nn, dd, ratio))
            else:
                row.append("%d:%.2e" % (nn, dd))
            prev = dd
        d_last, d_first = abs(g - cf(N=grid[-1], **p)), abs(g - cf(N=grid[0], **p))
        tol = _TOL_BY_BID[bid]
        print("%-6s %-58s %-8s 比值 %.2f~%.2f  粗端>1e-13:%s  粗端<tol:%s  默认档>1e-12:%s"
              % (bid, "  ".join(row), "MONO" if mono else "NONMONO",
                 min(ratios), max(ratios), d_first > 1e-13, d_first < tol, d_last > 1e-12))
    print("\nBAD =", bad, "（应为 0）")
