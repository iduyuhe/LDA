# -*- coding: utf-8 -*-
"""J3 M2 · 门保真标定能力层：随机 Clifford RB + unitarity（二阶纯度衰减）。

════════════════════════════════════════════════════════════════
物理（章程 §3 M2 · 缺口 G-CTRL-2）——

  · **RB（randomized benchmarking）**：用**随机 Clifford 序列**把任意噪声信道
    **twirl 成去极化信道**，测平均门保真度衰减参数 **p**（**一阶量**）。
  · **unitarity u** 是**二阶量**：测**纯度（purity）衰减率** —— 它对**相干（酉）误差
    不敏感**（酉演化保纯度 ⇒ u = 1），对**非相干（去极化）误差敏感**（u = p²）。
  ⇒ 二者联立把「**相干误差 vs 非相干误差**」分离（Wallman et al. 2015 的物理内容）。

🔴 与账本锚 **B512** 同物理律（`run_j3_ctrl_smoke` D 节核验）：
   去极化纯度律 **P(m) = 1/2 + (1/2)·u^m**，u = e^{−2Γ}（每门去极化率 Γ）。
   B512 golden = 连续时间闭式 P(t)；本模块 = **逐门序列版**（m 门，m·n 步 RK4）。

主权：纯 numpy/math + 复用本包 `gates.py` 的 24 元 Clifford 群；**零量子 SDK**。
"""
from __future__ import annotations

import math

import numpy as np

from lda_qeda.gates import _clifford_1q_set

#: 默认去极化率（每门 Γ）与默认序列长度
DEFAULT_RB = {"Gamma": 0.02, "m_max": 20}

_SX = np.array([[0, 1], [1, 0]], dtype=complex)
_SY = np.array([[0, -1j], [1j, 0]], dtype=complex)
_SZ = np.array([[1, 0], [0, -1]], dtype=complex)


def clifford_1q() -> list:
    """单比特 Clifford 群（恰 24 元，复用 `gates.py` 的精确群论闭包）。"""
    return _clifford_1q_set()


# ── 解析闭式（去极化信道）────────────────────────────────────────────────
def rb_decay_param(Gamma: float = 0.02) -> float:
    """一阶 RB 保真度衰减参数 **p = e^{−Γ}**（每门）。"""
    return math.exp(-float(Gamma))


def unitarity_per_gate(Gamma: float = 0.02) -> float:
    """二阶 unitarity **u = e^{−2Γ} = p²**（去极化信道的精确关系）。"""
    return math.exp(-2.0 * float(Gamma))


def purity_decay_analytic(m: int, Gamma: float = 0.02) -> float:
    """解析纯度衰减 **P(m) = 1/2 + (1/2)·u^m**（初态 |0⟩ 纯态 ⇒ P(0)=1）。"""
    u = unitarity_per_gate(Gamma)
    return 0.5 * (1.0 + u ** int(m))


def fidelity_decay_analytic(m: int, Gamma: float = 0.02) -> float:
    """解析保真度衰减 **F(m) = 1/2 + (1/2)·p^m**（一阶对照量）。"""
    p = rb_decay_param(Gamma)
    return 0.5 * (1.0 + p ** int(m))


# ── 数值（密度矩阵 Liouvillian RK4 · 与 B512 candidate 同法）────────────────
def _depol_rhs(rho: np.ndarray, Gamma: float) -> np.ndarray:
    return (Gamma / 4.0) * (_SX @ rho @ _SX + _SY @ rho @ _SY + _SZ @ rho @ _SZ
                            - 3.0 * rho)


def purity_decay_numeric(m: int, Gamma: float = 0.02, n: int = 64) -> float:
    """数值：m 门 × 每门 n 步的四阶 RK4（初态 |0⟩⟨0|，返回 Tr(ρ²)）。

    总演化时间 = m（每门单位时长），总步数 = m·n。离散参数 = n（步/门）。
    """
    m, n = int(m), int(n)
    if m < 0 or n < 1:
        raise ValueError("m ≥ 0 且 n ≥ 1")
    rho = np.array([[1.0, 0.0], [0.0, 0.0]], dtype=complex)
    h = 1.0 / n
    for _ in range(m * n):
        k1 = _depol_rhs(rho, Gamma)
        k2 = _depol_rhs(rho + 0.5 * h * k1, Gamma)
        k3 = _depol_rhs(rho + 0.5 * h * k2, Gamma)
        k4 = _depol_rhs(rho + h * k3, Gamma)
        rho = rho + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return float(np.real(np.trace(rho @ rho)))


def unitarity_from_purity_sequence(m1: int = 1, m2: int = 3, Gamma: float = 0.02,
                                   n: int = 64) -> float:
    """从两个序列长度的**数值纯度**反解 unitarity：
        u = (P(m1) − 1/2) / (P(m2) − 1/2) 的 1/(m1−m2) 次幂。
    （与解析 u=e^{−2Γ} 比对 —— 体现「数值 RB 从纯度衰减提取二阶量」。）
    """
    d1 = purity_decay_numeric(m1, Gamma, n) - 0.5
    d2 = purity_decay_numeric(m2, Gamma, n) - 0.5
    if d1 <= 0.0 or d2 <= 0.0:
        raise ValueError("纯度偏离 1/2 过小 ⇒ 无法反解 unitarity")
    return (d1 / d2) ** (1.0 / (int(m1) - int(m2)))


# ── 相干 vs 非相干误差分解 ────────────────────────────────────────────────
def coherence_measure(p: float, u: float) -> float:
    """相干性度量 **u − p²**（≥0；=0 ⇔ 纯非相干/去极化；>0 ⇔ 含相干分量）。"""
    return float(u) - float(p) ** 2


def error_budget(p: float, u: float, d: int = 2) -> dict:
    """误差预算：总错误率 / 非相干下界 / 相干余量（Wallman 关系）。

    · 总错误率 r_total = (d−1)/d · (1 − p)（一阶 RB）
    · unitarity 给出「纯非相干份 ⇒ p²」⇒ 相干余量 = u − p²（≥0）
    · 纯去极化 ⇒ u = p²（coherence 0）；纯酉 ⇒ u = 1 且 p<1（coherence 最大）。
    """
    p, u, d = float(p), float(u), int(d)
    r_total = (d - 1) / d * (1.0 - p)
    return {
        "p": p, "u": u, "d": d,
        "r_total": r_total,
        "u_minus_p2": coherence_measure(p, u),
        "fully_coherent": abs(u - 1.0) < 1e-12,
        "depolarizing": abs(u - p * p) < 1e-12,
    }


def rb_report(Gamma: float = None, m_max: int = None, n: int = 64) -> dict:
    """RB + unitarity 标定报告（签核：纯度二阶量自洽 ∧ 去极化关系成立）。"""
    p0 = DEFAULT_RB
    Gamma = p0["Gamma"] if Gamma is None else float(Gamma)
    m_max = p0["m_max"] if m_max is None else int(m_max)
    p = rb_decay_param(Gamma)
    u = unitarity_per_gate(Gamma)
    seq = [(m, purity_decay_analytic(m, Gamma)) for m in range(0, m_max + 1)]
    # 数值 vs 解析一致性（默认档 m_max）
    num = purity_decay_numeric(m_max, Gamma, n)
    ana = purity_decay_analytic(m_max, Gamma)
    rel = abs(num - ana) / abs(ana)
    u_num = unitarity_from_purity_sequence(1, 3, Gamma, n)
    ok = (
        abs(u - p * p) < 1e-15            # u = p²（去极化关系）
        and rel < 1e-8                     # 数值 ≡ 解析
        and abs(u_num - u) / abs(u) < 1e-8  # 纯度序列反解 ≡ 解析
        and seq[0][1] == 1.0               # P(0) = 1（纯态）
    )
    return {
        "verdict": "ACCEPT" if ok else "REJECT",
        "Gamma": Gamma, "p": p, "u": u,
        "u_from_purity_sequence": u_num,
        "purity_sequence": seq,
        "numeric_vs_analytic_rel": rel,
        "budget": error_budget(p, u),
        "n_clifford": len(clifford_1q()),
        "note": ("RB 一阶 p 与二阶 unitarity u 联立 ⇒ 相干/非相干误差分解；"
                 "去极化关系 u=p² 精确成立。设计预算，不含量子线路噪声仿真。"),
    }


def run_selfchecks(verbose: bool = False) -> bool:
    """常驻自检：Clifford 24 元 / 去极化关系 / 纯度单调 / 数值≡解析 / 分解良定义。"""
    bad = []

    def chk(name: str, cond: bool) -> None:
        if verbose:
            print("  [%s] %s" % ("PASS" if cond else "FAIL", name))
        if not cond:
            bad.append(name)

    # ① 群论：24 元
    cs = clifford_1q()
    chk("Clifford 单比特群恰 24 元", len(cs) == 24)
    # ② 去极化关系 u = p²（多种 Γ）
    for G in (0.005, 0.02, 0.05, 0.1):
        chk("u = p² (Γ=%.3f)" % G,
            abs(unitarity_per_gate(G) - rb_decay_param(G) ** 2) < 1e-15)
    # ③ 纯度衰减：P(0)=1、单调降、P(∞)→1/2
    chk("P(0) = 1", abs(purity_decay_analytic(0, 0.02) - 1.0) < 1e-15)
    chk("P 单调降", all(purity_decay_analytic(m, 0.02) > purity_decay_analytic(m + 1, 0.02)
                        for m in range(0, 10)))
    chk("P(m≫) → 1/2", abs(purity_decay_analytic(10 ** 6, 0.05) - 0.5) < 1e-12)
    # ④ 数值 ≡ 解析（同一物理律）
    for G in (0.02, 0.05):
        num = purity_decay_numeric(5, G, n=128)
        ana = purity_decay_analytic(5, G)
        chk("数值≡解析 (Γ=%.3f, rel=%.2e)" % (G, abs(num - ana) / abs(ana)),
            abs(num - ana) / abs(ana) < 1e-8)
    # ⑤ 纯度序列反解 unitarity ≡ 解析
    G = 0.02
    u_num = unitarity_from_purity_sequence(1, 3, G, n=128)
    chk("纯度序列反解 u ≡ 解析", abs(u_num - unitarity_per_gate(G)) / unitarity_per_gate(G) < 1e-8)
    # ⑥ 分解：纯去极化 ⇒ coherence=0；纯酉（u=1）⇒ coherence>0
    p_dep = 0.9
    chk("纯去极化 ⇒ u−p²=0", abs(coherence_measure(p_dep, p_dep ** 2)) < 1e-15)
    chk("纯酉 ⇒ u−p²>0", coherence_measure(0.9, 1.0) > 0.0)
    chk("分解良定义：fully_coherent/depolarizing 二值",
        error_budget(0.9, 1.0)["fully_coherent"] and error_budget(0.9, 0.81)["depolarizing"])
    # ⑦ 报告签核二值
    rep = rb_report()
    chk("RB 报告签核二值", rep["verdict"] in ("ACCEPT", "REJECT"))
    chk("RB 报告默认 ACCEPT", rep["verdict"] == "ACCEPT")

    if verbose:
        print("自检：%d FAIL" % len(bad))
    return not bad


if __name__ == "__main__":  # pragma: no cover
    print("J3 M2 门保真标定自检（RB + unitarity）")
    ok = run_selfchecks(verbose=True)
    print("ALL PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)
