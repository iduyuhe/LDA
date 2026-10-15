# -*- coding: utf-8 -*-
"""Batch J5 量子网络与接口征程 · **M0** 数值核：**B519 分发后两体纠缠保真度**。

── 物理与锚形 ──────────────────────────────────────────────────────────────
J1–J4 全部建模「芯片内 / 实验室距离」；本条**第一次引入公里级距离**维度（章程 §3.1）。

  · 初始态：Bell 态 `|Φ+⟩=(|00⟩+|11⟩)/√2`（Werner 参数 p=1）。
  · 信道：光纤传输 + **偏振去相干**（退极化信道）⇒ 态进入 **Werner 族**
    `ρ(L) = p(L)·|Φ+⟩⟨Φ+| + (1−p(L))·I/4`，`p(L)=exp(−L/L_depol)`。
  · 读数：分发后**两体纠缠保真度** `F = Tr(ρ(L)·|Φ+⟩⟨Φ+|) = (1+3p(L))/4`。

**golden（闭式物理律 · 严格解析）**：`F(L)=(1+3·exp(−L/L_depol))/4`（Werner 族教科书闭式）。
**candidate（方法学独立）**：`dρ/dL = −(ρ − I/4)/L_depol` 的 **4×4 密度矩阵 RK4 距离步进**
（16 实分量全演化，末端读 `Tr(ρ·ρ_ideal)`）—— **静态算子代数 → 距离步进时间推进**。

── 同源体检（2026-10-15 实 grep `lda_harness/benchmark_defs/` · 如实登记）────────────
  · `werner` = **0 命中**；`entangl|bell|EPR|concurrence|CHSH|teleport` 在锚定义内 **0 命中**
    （唯一近邻 `part1.py:221`「EPR 哈密顿量对角化(pyEPR/Ansys)仅作外部 ORACLE」为**文本非锚**）。
  · 🔴 **`kraus` 已被 B453 占用**（`coherent_loss_fidelity` · 相干态经损耗通道 ·
    **静态 Fock 截断 Kraus 算子求和**）⇒ 本条候选**刻意避开 Kraus 求和**，改「距离步进 Liouvillian」。
  · `fiber` 命中为 **阶跃光纤 LP01 模式折射率**锚（part5 `fiber_lp01_neff_fd`）⇒ **模式求解**，
    与「信道损耗/保真度」**物理量不同**。

── 三方分歧（与既有保真度族）────────────────────────────────────────────────
  | 对 | ① 被测标量 | ② 物理构型 | ③ 数值格式 |
  |---|---|---|---|
  | **B453**（相干态损耗保真度） | **两体纠缠态**保真度（Werner · 含纠缠语义） | **含公里级信道传输**（距离 L 为自变量） | **距离步进 RK4 超算子**（vs 静态 Fock 截断 Kraus 求和） |
  | **B10**（单比特门保真度·退相干极限） | 两体纠缠态保真度 | 信道传输（vs 二能级 T1/T2 双通道） | RK4 距离步进（vs 4×4 PTM 时间步进） |
  | **B502/B503**（QEC 门/合并保真度） | 连续变量/纠缠态保真度 | 光纤信道（vs 表面码操作） | RK4 距离步进（vs 组合/数值链） |
  ⇒ **非重复计数**（先例：B452↔B33、B448/B449）。

── 判据 D（真离散误差）────────────────────────────────────────────────────
实测残差链 n=16→2.4914e-06 · 32→1.3823e-07 · 64→8.1415e-09 · 128→4.9399e-10 · 256→3.0420e-11
（比值 18.02/16.98/16.48/16.24 ⇒ **趋向 16 = O(h⁴)**；动态范围 1.32e6×）。
⇒ 粗端浮出双精度地板、严格单调、与 RK4 标称阶一致 ⇒ **真独立，非代数恒等**。

🔴 **诚实边界**：`L=100 km` / `L_depol=22 km` / `α=0.2 dB/km` 均为**公开典型值 / 设计示例**，
非任何实测链路；本锚只支撑预算与量级，**不作性能宣称**。残差 = RK4 截断误差。零商业依赖
（纯 `math` + `numpy`；零 RNG）。
"""

from __future__ import annotations

import math

import numpy as np

# ── 常量（设计示例 · 见诚实边界）──────────────────────────────────────────
#: 链路长度（m · 100 km）
_LINK_LENGTH_M = 1.0e5
#: 偏振去相干长度（m · 设计示例，与光纤 L_att 同量级）
_DEFAULT_L_DEPOL_M = 2.2e4

#: 完全混态 I/4 与理想 Bell 态 |Φ+⟩⟨Φ+|（4×4）
_I4 = np.eye(4, dtype=float) / 4.0
_PHI = np.zeros((4, 4), dtype=float)
_PHI[0, 0] = _PHI[3, 3] = 0.5
_PHI[0, 3] = _PHI[3, 0] = 0.5

# ── 三表（判据 D 扫描格 / 默认档 = 格末端 / tol 绝对口径按量级标定）───────────
_M_BY_BID = {"B519": 256}
_GRID_BY_BID = {"B519": [16, 32, 64, 128, 256]}
_TOL_BY_BID = {"B519": 1e-8}

#: 默认物理参数（只放 golden 接受的键；离散参数 n 由候选签名默认值承载）
_B519_DEFAULT = {"l_depol_m": 2.2e4}


def _werner_rho(p: float) -> np.ndarray:
    """Werner 族密度矩阵 `ρ = p|Φ+⟩⟨Φ+| + (1−p)I/4`。"""
    return p * _PHI + (1.0 - p) * _I4


def _rhs(rho: np.ndarray, l_depol_m: float) -> np.ndarray:
    """退极化信道 Liouvillian（距离域）：`dρ/dL = −(ρ − I/4)/L_depol`。"""
    return -(rho - _I4) / l_depol_m


def distribution_fidelity_golden(l_depol_m: float = _DEFAULT_L_DEPOL_M) -> float:
    """B519 golden：Werner 族**分发后保真度**（**严格解析闭式**）。

        F(L) = (1 + 3·p(L)) / 4 ,   p(L) = exp(−L/L_depol)

    推导：退极化信道把 `ρ₀=|Φ+⟩⟨Φ+|` 映为 `ρ(L)=p|Φ+⟩⟨Φ+|+(1−p)I/4`；对理想态取重叠
    `Tr(ρ·ρ₀) = p + (1−p)/4 = (1+3p)/4`。**非迭代、非截断**。
    """
    l_depol_m = float(l_depol_m)
    if l_depol_m <= 0.0:
        raise ValueError("去相干长度 L_depol 须 > 0")
    p = math.exp(-_LINK_LENGTH_M / l_depol_m)
    return (1.0 + 3.0 * p) / 4.0


def distribution_fidelity_candidate(l_depol_m: float = _DEFAULT_L_DEPOL_M,
                                   n: int = _M_BY_BID["B519"]) -> float:
    """B519 candidate：**4×4 密度矩阵沿距离的 RK4 步进**（与 golden 方法学独立）。

    把信道写成距离域初值问题 `dρ/dL = −(ρ−I/4)/L_depol`，`ρ(0)=|Φ+⟩⟨Φ+|`，
    自 L=0 推进到 L=100 km（n 步四阶 RK4，**16 个实分量全演化**），末端读
    `F = Tr(ρ(L)·|Φ+⟩⟨Φ+|)`。残差 = RK4 截断误差（O(h⁴)，实测比值趋向 16）。

    🔴 与 B453 的数值格式分歧点：本条是**距离步进时间推进**（离散参数 = 步数 n），
    B453 是**静态算子代数**（离散参数 = Fock 截断维数）。
    """
    n = int(n)
    if n < 1:
        raise ValueError("步数 n 须 ≥ 1")
    l_depol_m = float(l_depol_m)
    if l_depol_m <= 0.0:
        raise ValueError("去相干长度 L_depol 须 > 0")
    h = _LINK_LENGTH_M / n
    rho = _werner_rho(1.0)
    for _ in range(n):
        k1 = _rhs(rho, l_depol_m)
        k2 = _rhs(rho + 0.5 * h * k1, l_depol_m)
        k3 = _rhs(rho + 0.5 * h * k2, l_depol_m)
        k4 = _rhs(rho + h * k3, l_depol_m)
        rho = rho + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return float(np.trace(rho @ _PHI).real)


# ── 统一入口（harness / golden.py 按名调用）────────────────────────────────
def golden_b519(l_depol_m: float = _DEFAULT_L_DEPOL_M) -> float:
    return distribution_fidelity_golden(l_depol_m)


def cand_b519(l_depol_m: float = _DEFAULT_L_DEPOL_M,
              n: int = _M_BY_BID["B519"]) -> float:
    return distribution_fidelity_candidate(l_depol_m, n)


#: 暴露给锚定义（键集必须 ⊆ golden 形参集）
B519_DEFAULT_PARAMS = dict(_B519_DEFAULT)

_GOLDEN_BY_BID = {"B519": golden_b519}
_CAND_BY_BID = {"B519": cand_b519}

#: 自检用例：bid, 物理参数（golden 键）
_CASES = (("B519", _B519_DEFAULT),)


# ── 自检 ───────────────────────────────────────────────────────────────────
def _selfcheck() -> int:
    bad = 0
    print("=" * 78)
    print("Batch J5 数值核自检（B519 分发后两体纠缠保真度）")
    print("=" * 78)
    for bid, params in _CASES:
        gold = _GOLDEN_BY_BID[bid](**params)
        tol = float(_TOL_BY_BID[bid])
        n_end = int(_M_BY_BID[bid])
        grid = list(_GRID_BY_BID[bid])

        chain = []
        for n in grid:
            chain.append((n, abs(_CAND_BY_BID[bid](n=n, **params) - gold)))
        d_res = abs(_CAND_BY_BID[bid](n=n_end, **params) - gold)

        ratios = []
        for i in range(1, len(chain)):
            ratios.append(chain[i - 1][1] / chain[i][1] if chain[i][1] > 0 else float("inf"))

        dyn = chain[0][1] / chain[-1][1] if chain[-1][1] > 0 else float("inf")
        mono = all(chain[i][1] > chain[i + 1][1] for i in range(len(chain) - 1))
        margin = tol / d_res if d_res > 0 else float("inf")

        print("\n[%s] golden=%.15e  tol=%.1e  默认 n=%d" % (bid, gold, tol, n_end))
        print("  残差链: " + " → ".join("n=%d:%.4e" % (n, d) for n, d in chain))
        print("  比值:   " + " / ".join("%.2f" % r for r in ratios))
        print("  动态范围=%.4g×  余量=%.1f×  |golden|/tol=%.4g×  单调=%s"
              % (dyn, margin, abs(gold) / tol, mono))

        checks = {
            "残差 > 0（非代数恒等）": d_res > 0.0,
            "残差 < tol（判决通过）": d_res < tol,
            "基线残差 > 1e-12（不沉双精度地板）": d_res > 1e-12,
            "粗端残差 > 1e-13（离散误差主导）": chain[0][1] > 1e-13,
            "残差链严格单调递减": mono,
            "动态范围 ≥ 1e4×": dyn >= 1.0e4,
            "余量 ≥ 100×": margin >= 100.0,
            "|golden| / tol ≥ 13.5×": abs(gold) / tol >= 13.5,
            # RK4 ⇒ 比值趋向 16（粗端未入渐近区略高，如实登记不假称「恰 16」）
            "比值形态与 RK4 标称阶一致（趋向 16）":
                4.0 <= ratios[-1] <= 22.0 and ratios[-1] <= ratios[0],
            "默认档 = 扫描格末端": n_end == grid[-1],
        }
        for k, v in checks.items():
            print("  [%s] %s" % ("PASS" if v else "FAIL", k))
            if not v:
                bad += 1

        # 反向探针：物理参数扰动 ±10% 必须显著改变候选（C3/C5）
        d_pert = abs(_CAND_BY_BID[bid](n=n_end, **{**params, "l_depol_m": params["l_depol_m"] * 1.1})
                     - _CAND_BY_BID[bid](n=n_end, **params))
        sig = d_pert / tol
        ok_sig = sig >= 1.4
        print("  [%s] 扰动 L_depol ×1.1 ⇒ 信号 %.4e（%.1f× tol ≥ 1.4×）"
              % ("PASS" if ok_sig else "FAIL", d_pert, sig))
        if not ok_sig:
            bad += 1

        # 反向探针：非法离散参数必抛
        raised = False
        try:
            _CAND_BY_BID[bid](n=0, **params)
        except ValueError:
            raised = True
        print("  [%s] 反向：n=0 必抛 ValueError" % ("PASS" if raised else "FAIL"))
        if not raised:
            bad += 1

    print("\n" + "=" * 78)
    print("自检结果：%s（bad=%d）" % ("ALL PASS" if bad == 0 else "FAIL", bad))
    print("=" * 78)
    return bad


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_selfcheck())
