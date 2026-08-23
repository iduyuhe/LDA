"""LDA L2 · transmon-resonator 色散读出严格求解器（QEDA 求解器级补强 D-88）。

与光子栈「闭式解析 ↔ 严格数值」双验证完全同构：量子侧用
「**三能级色散修正解析式**（Blais 2011, PRA 83 065802: χ = g²α/(Δ(Δ+α))）
↔ **三能级 transmon + Fock 谐振器联合严格对角化**」两条独立路径交叉验证
色散频移 χ，落于确定性物理定律锚（零外部依赖、零 GPU、LLM 不进判决路径）。

物理（D-88 补强点）：
  现有 readout 验证（D-43 `jc_dispersive_verify`）用**二能级 JC 模型**
  （qubit=|g⟩,|e⟩，χ_an=g²/Δ）——忽略 transmon 非谐性 α 对色散的实质修正。
  真实 transmon 有 |f⟩ 态（f12=f01+α，α<0），虚跃迁经 |f⟩ 使色散频移变为
    χ = g²·α/(Δ(Δ+α))          （|Δ|=|f_q−f_r|，色散失谐）
  ——α→0 时自动退化回二能级 g²/Δ。三能级模型下 χ 为**负**（α<0），符号即
  非谐性的标志性物理（二能级近似给出正的 g²/Δ，物理上错误）。

模型（标准 readout 物理）：
    H = Σ_{s∈{g,e,f}} E_s|s⟩⟨s| + f_r·a†a
        + g·(n̂₀₁(|e⟩⟨g|+|g⟩⟨e|) + n̂₁₂(|f⟩⟨e|+|e⟩⟨f|))·(a+a†)
    E_g=0, E_e=f_q, E_f=2f_q+α；n̂₀₁ 归一化吸收进 g，n̂₁₂=√2（标准跃迁矩阵元比）。
    维度 3×(M+1)（M 光子截断）。

求解器输出（设计闭环所需 readout 物理量）：
  χ 色散频移（数值严格 + 三能级解析 + 二能级对比三值对拍）
  n_crit = Δ²/(4g²)          色散近似有效光子数上限（readout 设计关键约束）
  γ_Purcell = κ·g²/Δ²        qubit 经谐振器的 Purcell 衰减率（T1 限制）
  AC Stark：qubit 频移 = 2n·χ（谐振器 n 光子）
  真空拉比分裂 2g（共振自洽验证）

验收（死标量，LLM 不进判决路径）：
  (a) 色散区有效 Δ/g ≥ 5；
  (b) χ_num ↔ χ_an（三能级修正）rel ≤ 10%（弱耦合极限）；
  (c) 共振拉比分裂 g_self ↔ g rel ≤ 2%（自洽）；
  (d) 二能级近似 rel 显著更大（证明 α 修正必要，≥ 3×）。

参考：`transmon_solver.py`（单 qubit 严格对角化）、`coupler_solver.py`（双
qubit 耦合）、`qubit_readout_chain.py`（D-43 二能级 JC 验证——本求解器的
三能级升级）。
"""
from __future__ import annotations

import math
from typing import Any, Dict

import numpy as np

__all__ = ["tls_spectrum", "chi_analytic_3level", "chi_analytic_2level",
           "solve_qubit_resonator"]


def tls_spectrum(f_q: float, alpha: float, f_r: float, g: float,
                 M: int = 25) -> np.ndarray:
    """三能级 transmon + Fock 谐振器联合哈密顿量严格对角化（GHz）。

    低能级顺序（f_r 介于 f_q 与 2f_q+α 之间时）：|g,0⟩ < |e,0⟩ < |g,1⟩ <
    |f,0⟩ < |e,1⟩ < |f,1⟩…——态标记见 `solve_qubit_resonator` 的最近匹配。
    """
    dim = 3 * (M + 1)
    H = np.zeros((dim, dim), dtype=float)
    Es = {0: 0.0, 1: f_q, 2: 2.0 * f_q + alpha}
    n12 = math.sqrt(2.0)  # <f|n̂|e>/<e|n̂|g> 标准比值

    def idx(s: int, n: int) -> int:
        return s * (M + 1) + n

    for s in range(3):
        for n in range(M + 1):
            H[idx(s, n), idx(s, n)] = Es[s] + n * f_r
    for n in range(M):
        fac = math.sqrt(n + 1.0)
        # a†: |s,n⟩ → |s′,n+1⟩（<e|T̂|g>=1，<f|T̂|e>=√2）
        H[idx(1, n + 1), idx(0, n)] += g * fac
        H[idx(0, n), idx(1, n + 1)] += g * fac
        H[idx(2, n + 1), idx(1, n)] += g * fac * n12
        H[idx(1, n), idx(2, n + 1)] += g * fac * n12
        # a: |s,n+1⟩ → |s′,n⟩
        H[idx(1, n), idx(0, n + 1)] += g * fac
        H[idx(0, n + 1), idx(1, n)] += g * fac
        H[idx(2, n), idx(1, n + 1)] += g * fac * n12
        H[idx(1, n + 1), idx(2, n)] += g * fac * n12
    return np.sort(np.linalg.eigh(H)[0])


def _nearest(evals: np.ndarray, target: float) -> float:
    """弱耦合区最近能量匹配（态混合小，唯一近邻）。"""
    return float(evals[np.argmin(np.abs(evals - target))])


def chi_analytic_3level(f_q: float, alpha: float, f_r: float,
                        g: float) -> float:
    """三能级色散修正（Blais 2011）：χ = g²·α/(Δ(Δ+α))，Δ=f_q−f_r（GHz）。"""
    delta = f_q - f_r
    return float(g * g * alpha / (delta * (delta + alpha)))


def chi_analytic_2level(f_q: float, f_r: float, g: float) -> float:
    """二能级色散近似（D-43 使用，无 α 修正）：χ = g²/Δ。"""
    delta = f_q - f_r
    return float(g * g / delta)


def solve_qubit_resonator(f_q: float = 5.0, alpha: float = -0.3,
                          f_r: float = 6.0, g: float = 0.1,
                          kappa: float = 0.005, M: int = 25,
                          tol_chi: float = 0.10,
                          tol_rabi: float = 0.02) -> Dict[str, Any]:
    """transmon-resonator 色散读出严格求解器（D-88）。

    返回完整 readout 设计物理量 + 死标量验收。参数单位 GHz。
    """
    delta = f_q - f_r
    abs_delta = abs(delta)
    chi_an = chi_analytic_3level(f_q, alpha, f_r, g)
    chi_2lvl = chi_analytic_2level(f_q, f_r, g)

    # 严格数值：最近能量匹配提取 |g,0⟩|g,1⟩|e,0⟩|e,1⟩ → qubit 态依赖谐振器频移
    E = tls_spectrum(f_q, alpha, f_r, g, M=M)
    E_g0 = _nearest(E, 0.0)
    E_e0 = _nearest(E, f_q)
    E_g1 = _nearest(E, f_r)
    E_e1 = _nearest(E, f_q + f_r)
    w_r_g = E_g1 - E_g0
    w_r_e = E_e1 - E_e0
    chi_num = (w_r_e - w_r_g) / 2.0

    # 真空拉比分裂自洽（共振：f_r=f_q 时 |e,0⟩/|g,1⟩ 分裂=2g）
    E_res = tls_spectrum(f_q, alpha, f_q, g, M=M)
    rabi_split = E_res[2] - E_res[1]   # 共振低能谱：|g,0⟩<|e,0⟩≈|g,1⟩（混合对）
    g_self = rabi_split / 2.0

    chi_rel = abs(chi_num - chi_an) / (abs(chi_an) + 1e-12)
    g_rel = abs(g_self - g) / (g + 1e-12)
    n_crit = abs_delta ** 2 / (4.0 * g * g)
    gamma_purcell = kappa * g * g / (abs_delta * abs_delta)   # GHz
    t1_purcell_us = (1.0 / (gamma_purcell * 2.0 * math.pi)) * 1e3  # 2π→rad/s→µs
    ac_stark_1ph = 2.0 * chi_num   # 单光子态依赖 qubit 频移（负）
    dispersive_ok = abs_delta / g >= 5.0
    chi_ok = bool(chi_rel <= tol_chi)
    rabi_ok = bool(g_rel <= tol_rabi)
    # α 修正必要性：三能级解析应显著优于二能级近似（≥3×）
    rel_2lvl = abs(chi_num - chi_2lvl) / (abs(chi_2lvl) + 1e-12)
    correction_ok = bool(rel_2lvl >= 3.0 * chi_rel)
    passed = bool(dispersive_ok and chi_ok and rabi_ok and correction_ok)

    return {
        "chi_num_ghz": float(chi_num),
        "chi_3level_ghz": float(chi_an),
        "chi_2level_ghz": float(chi_2lvl),
        "chi_rel_err_3level": float(chi_rel),
        "chi_rel_err_2level": float(rel_2lvl),
        "n_crit": float(n_crit),
        "gamma_purcell_ghz": float(gamma_purcell),
        "t1_purcell_us": float(t1_purcell_us),
        "ac_stark_1ph_ghz": float(ac_stark_1ph),
        "rabi_split_ghz": float(rabi_split),
        "g_from_split_ghz": float(g_self),
        "g_rel_err": float(g_rel),
        "detune_ghz": float(delta),
        "delta_over_g": float(abs_delta / g),
        "f_q": float(f_q), "alpha": float(alpha), "f_r": float(f_r),
        "g": float(g), "kappa": float(kappa), "M": M,
        "levels_ghz": [float(e) for e in E[:6]],
        "acceptance": {
            "passed": passed,
            "checks": {
                "dispersive_region_delta_g_ge_5": bool(dispersive_ok),
                "chi_3level_rel_le_0.10": chi_ok,
                "rabi_split_self_consistency_le_0.02": rabi_ok,
                "alpha_correction_necessary_ge_3x": correction_ok,
            },
        },
        "verdict": ("三能级色散严格对角化 ↔ Blais 修正解析式一致 + 拉比自洽 + "
                    "α 修正必要性确认" if passed else "未达标"),
    }


if __name__ == "__main__":
    import json
    r = solve_qubit_resonator()
    print(json.dumps({k: r[k] for k in (
        "chi_num_ghz", "chi_3level_ghz", "chi_2level_ghz",
        "chi_rel_err_3level", "chi_rel_err_2level", "n_crit",
        "gamma_purcell_ghz", "t1_purcell_us", "ac_stark_1ph_ghz",
        "delta_over_g", "acceptance", "verdict")},
        ensure_ascii=False, indent=2))
