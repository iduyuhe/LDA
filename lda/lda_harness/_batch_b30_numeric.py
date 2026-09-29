# -*- coding: utf-8 -*-
"""B-30 数值核（Batch B-30 · 量子征程「回填」· 3 锚 B453/B454/B455）

物理族 = **有限维 Fock 截断 × 解析闭式**（连续变量光量子器件：预报单光子源 + 损耗通道）。
来源：量子光学教科书物理定律（人类公共品）—— TMSS 压缩真空 / on-off 预报 / 振幅阻尼损耗通道。

| 锚 | 被测标量 | golden（解析闭式） | candidate（方法学独立） |
|---|---|---|---|
| B453 | 相干态经损耗通道的输入-输出保真度 | `exp(−\\|α\\|²(1−√η)²)`（\\|α⟩→\\|√η α⟩ 的态重叠） | 截断 Fock 空间建密度矩阵 + Kraus 算子求和 ⇒ `Tr(ρ_out ρ_in)` |
| B454 | TMSS on/off 预报条件态**纯度** | `(1−λ²)/(1+λ²)` | 矩阵指数建 TMSV → on/off 投影 → 部分迹 → `Tr(ρ²)` |
| B455 | TMSS on/off 预报条件态 **g²(0)** | `2λ²` | 同 B454 路线 ⇒ `⟨n(n−1)⟩/⟨n⟩²` |

三者共享的数值机制 = **有限维截断**（截断维数 N = Fock 截断）；残差 = 截断误差，
**非恒等、非地板**（实测见 §自检）。

判据 D：固定物理参数，只扫**候选自身离散参数** N（截断维数）。
        要求 ①粗端残差 > 1e-13 且 **< tol**（窗口铁律 `1e-15 < 粗端 < tol`）
        ②随 N 严格单调下降 ③默认档残差 > 1e-12（避开 `run_d_criterion_smoke` ③ 红灯）
        ④`|golden|/tol ≥ 13.5` ⑤余量 `tol/|Δ| ≥ 2`。
        **收敛阶/比值数字一律来自实测扫描，不按标称阶写死**（B-19 血案）。
        截断型收敛不是幂律 ⇒ 比值随 N 单调增（超几何型），如实登记，不假称「恰 2^k」。

🔴 同源体检（**实 grep 全仓**，排除 `.git/__pycache__/node_modules/lda_cuda_venv` 三方噪声）：
    · `heralded|TMSS|squeez|压缩|twin_beam|孪生` 在 `lda/` 内**仅命中 `lda_qeda/photon_sources.py`
      自身**（D-114 模块），**零锚占用** ⇒ B454/B455 族为**新方程/新构型**。
    · `coherent_loss|loss_fidelity|相干态` 在 `lda/` 内仅 `lda_qeda/open_system.py`（D-116 模块）
      与两处 smoke ⇒ B453 的闭式**非既有锚**。
    · **B453 vs B10**（唯一需登记的近邻）：B10 = 单量子比特门保真度（退相干极限），
      golden `F=(3+2e^{−t/T2}+e^{−t/T1})/6`、candidate = Lindblad 4×4 超算子 RK4 积分 → PTM。
      **三方分歧**：①**被测标量不同**（B10 平均门保真度（qubit，含 T1/T2 双通道）vs
      本题 `exp(−|α|²(1−√η)²)`（连续变量相干态、纯损耗、无相位退相干））；
      ②**物理构型不同**（B10 二能级 qubit + 4×4 PTM；本题相干态在**截断 Fock 空间** + 振幅阻尼通道）；
      ③**数值格式不同**（B10 时间步进 RK4 积分超算子；本题**静态 Kraus 算子求和**
      —— 无时间步进、离散参数是 Fock 截断维数而非步数）。
      ⇒ **非重复计数**（先例：B452 vs B33 同为 RC 一阶暂态而三处分歧 ⇒ 计新锚；
         B448/B449 同为 Ci 函数不同 X 亦各计一锚）。此判断如实登记，供人工复核；
      **不掩盖**「同属 Lindblad 损耗 + 保真度」这一共同上位结构。

🔴 血案预防：
    1. `coherent_dm` 内用 `math.factorial(n)` ⇒ **N ≥ 171 溢出**（`OverflowError`）。
       本批 N 上限 26/36/22，安全；但候选内**显式** `raise ValueError` 拦住 N > 160。
    2. 部分迹必须**先取模 2 对角再求和**（D-115 血案：同时求和 n₂ 与 n₂' 会保留模 2 相干 ⇒
       得到秩 1 钝态、纯度恒为 1）。本批**复用** `photon_sources.heralded_onoff`（已修正版），
       不自写部分迹。
    3. 相干态的截断密度矩阵**必须归一**后再入通道（未归一会引入额外偏差 ⇒ 残差量级失真）。
    4. 本批 golden 与 candidate **共用 `lda_qeda` 模块**但调用**不同函数族**
       （闭式代数式 vs 算子构造），不是同一函数的两种写法 ⇒ 判据 D 实测有响应（见 §自检）。

诚实边界：
    · 参数（λ、α、η）为**设计预算值**，本批**无实测锚**；结论只可用于预算与量级，不得作性能宣称。
    · 截断型收敛**不是幂律**：比值随 N 单调增（超几何型）；`tol` 按「余量 ≥ 2 且
      `|golden|/tol ≥ 13.5`」逐锚标定，不按标称阶设定。
    · B453 的 residual 主要在 N = 10~14 段（截断尾概率主导）；B454/B455 在 N ≥ 26/36 仍未到
      双精度地板 ⇒ 三者默认档残差均 ≫ 1e-12，符合 `run_d_criterion_smoke` ③。
    · 零商业依赖（纯 numpy + 本项目 `lda_qeda` 纯净模块）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_LDA_DIR = Path(__file__).resolve().parents[1]        # …/lda（给出 `lda_qeda` 包）
_PS = None
_OS = None


def _qeda():
    """双路兜底导入 `lda_qeda.photon_sources` / `open_system`（缓存）。

    🔴 这两模块是**本项目自研纯净模块**（纯 numpy、零第三方），非外部依赖；
    本批把它们接入账本判决路径（此前量子征程为「平台能力演示、账本零改动」）。
    """
    global _PS, _OS
    if _PS is not None and _OS is not None:
        return _PS, _OS
    try:
        from lda_qeda import open_system as _os_mod
        from lda_qeda import photon_sources as _ps_mod
    except ImportError:                                # 裸模块名回退
        if str(_LDA_DIR) not in sys.path:
            sys.path.insert(0, str(_LDA_DIR))
        import open_system as _os_mod                  # type: ignore
        import photon_sources as _ps_mod               # type: ignore
    _PS, _OS = _ps_mod, _os_mod
    return _PS, _OS


# ===========================================================================
# 公共工具
# ===========================================================================
_N_MAX_SAFE = 160          # math.factorial 溢出前上限（血案 1）


def _guard_n(n) -> int:
    nn = int(n)
    if nn < 2 or nn > _N_MAX_SAFE:
        raise ValueError("截断维数 N 须 ∈ [2, %d]（math.factorial 溢出护栏）" % _N_MAX_SAFE)
    return nn


def _heralded_onoff_state(lam: float, n: int) -> np.ndarray:
    """TMSS on/off 预报**条件态**（已归一）—— 复用 D-114 的「矩阵指数 + 投影 + 部分迹」。

    血案 2：部分迹走 `photon_sources.heralded_onoff`（先取模 2 对角再求和），**不自写**。
    """
    ps, _os = _qeda()
    nn = _guard_n(n)
    la = float(lam)
    if not (0.0 <= la < 1.0):
        raise ValueError("λ 须 ∈ [0,1)（tanh r 的值域）")
    psi = ps.tmss_numeric_state(float(np.arctanh(la)), nn)
    rho2 = np.outer(psi, psi.conj())
    return ps.heralded_onoff(rho2, nn)


# ===========================================================================
# B453 · 相干态经损耗通道的输入-输出保真度
# ===========================================================================
def golden_b453(alpha, eta):
    """F = exp(−|α|²(1−√η)²)（教科书：|α⟩ 经振幅阻尼 → |√η α⟩，态重叠模方）。"""
    _ps, os_mod = _qeda()
    return float(os_mod.coherent_loss_fidelity_closed_form(complex(float(alpha)), float(eta)))


def cand_b453(alpha, eta, N: int = 22):
    """候选：截断 Fock 空间 |α⟩⟨α| ⟶ Kraus 损耗通道 ⟶ F = Tr(ρ_out ρ_in)（纯态输入）。"""
    ps, os_mod = _qeda()
    nn = _guard_n(N)
    R = ps.coherent_dm(complex(float(alpha)), nn)
    tr = float(np.real(np.trace(R)))
    if tr <= 0.0:
        raise ValueError("相干态截断密度矩阵迹为 0（N 太小）")   # 血案 3：必须归一
    rho0 = R / tr
    rho_out = os_mod.kraus_channel(rho0, os_mod.loss_kraus(float(eta), nn))
    return float(np.real(np.trace(rho_out @ rho0)))


# ===========================================================================
# B454 · TMSS on/off 预报条件态纯度
# ===========================================================================
def golden_b454(lam):
    """纯度闭式 = (1−λ²)/(1+λ²)（λ = tanh r；λ→0 趋 1、λ→1 趋 0）。"""
    ps, _os = _qeda()
    return float(ps.heralded_purity_onoff(float(lam)))


def cand_b454(lam, N: int = 26):
    """候选：截断 Fock 空间建 TMSV ⟶ on/off 投影 ⟶ 部分迹 ⟶ Tr(ρ²)。"""
    cond = _heralded_onoff_state(float(lam), N)
    return float(np.real(np.trace(cond @ cond)))


# ===========================================================================
# B455 · TMSS on/off 预报条件态 g²(0)
# ===========================================================================
def golden_b455(lam):
    """g²(0) 闭式 = 2λ²（= 2·n̄/(1+n̄)，n̄ = λ²/(1−λ²)）。"""
    ps, _os = _qeda()
    return float(ps.heralded_g2_onoff(float(lam)))


def cand_b455(lam, N: int = 36):
    """候选：同 B454 路线的条件态 ⟶ g²(0) = ⟨n(n−1)⟩/⟨n⟩²。"""
    cond = _heralded_onoff_state(float(lam), N)
    dg = np.real(np.diag(cond))
    ns = np.arange(len(dg), dtype=float)
    n1 = float(np.sum(ns * dg))
    if n1 <= 0.0:
        raise ValueError("条件态平均光子数为 0（N 太小 / λ 太小）")
    n2 = float(np.sum(ns * (ns - 1.0) * dg))
    return float(n2 / (n1 * n1))


# ===========================================================================
# 逐锚默认档 / 判据 D 扫描网格 / tol
# ===========================================================================
#: 默认档 = 判据 D 扫描网格**末端**（B-16 血案：默认档必须等于扫描末端）
_N_BY_BID = {
    "B453": 22,
    "B454": 26,
    "B455": 36,
}
#: 判据 D 扫描网格（4 档，覆盖 `1e-15 < 粗端 < tol` 窗口；截断型 ⇒ 等比不适用，用等差）
_GRID_BY_BID = {
    "B453": [10, 14, 18, 22],
    "B454": [8, 14, 20, 26],
    "B455": [18, 24, 30, 36],
}
#: 逐锚 tol（按「余量 ≥ 2 且 |golden|/tol ≥ 13.5、粗端 < tol」标定；只收紧不放松）
_TOL_BY_BID = {
    "B453": 1e-2,
    "B454": 5e-3,
    "B455": 1e-2,
}

_CASES = [
    ("B453", golden_b453, cand_b453, {"alpha": 2.0, "eta": 0.6}),
    ("B454", golden_b454, cand_b454, {"lam": 0.8}),
    ("B455", golden_b455, cand_b455, {"lam": 0.8}),
]


if __name__ == "__main__":
    print("=== B-30 有限维 Fock 截断 × 解析闭式（量子征程回填）自检 ===")
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
        print("%-6s %-56s %-8s 比值 %.2f~%.2f  粗端>1e-13:%s  粗端<tol:%s  默认档>1e-12:%s"
              % (bid, "  ".join(row), "MONO" if mono else "NONMONO",
                 min(ratios), max(ratios), d_first > 1e-13, d_first < tol, d_last > 1e-12))
    print("\nBAD =", bad, "（应为 0）")
