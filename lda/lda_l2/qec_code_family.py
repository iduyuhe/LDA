# -*- coding: utf-8 -*-
"""蓝图 v2 · **D2 QEC 码族**能力层（`lda_l2/qec_code_family.py`）。

本模块只做**纯闭式 / 纯整数**的码族量，供 harness 锚与面板取用；不含求解器、不含 RNG、
不 import numpy/scipy（零商业依赖）。

## 为什么这一层大部分量**不入账本**

D2 的可锚性体检（`docs/LDA_V2-D2_QEC码族_..._2026-10-22.md` §3）结论：

- **精确组合量**（`steane_hamming_slack` / `toric_ground_degeneracy` / `stabilizer_group_order`
  / `logical_class_count`）：任何"独立"算法都给出同一个有理数或整数 ⇒ `resid ≡ 0`
  ⇒ 触 BL 的「零残差」红线 ⇒ **原理上不可锚**（不是"难锚"）。
- **渐近可达速率界**（`hashing_bound`）：闭式本身有真正的数值路径（把 `log` 换成
  `−log₂x = (1/ln2)∫ₓ¹ dt/t` 再求积）⇒ 残差是真截断 O(h⁴) ⇒ **可锚**（B525）。

因此本模块把两类量**并列**提供：可锚的那一个进账本，其余三个作为**能力 + 负结果证据**，
由 `lda_harness/d2_registries.py` 机器登记「不可锚」的理由与哨兵名。

## 语义

- `p`：退极化信道错误率（Pauli 错误总概率），取值 `[0, 3/4]`。
- `hashing_bound(p) = 1 − H₂(p) − p·log₂3`：hashing / coherent-information 界（bit 单位，
  即每信道使用可传输的逻辑量子比特数）。`p=0 ⇒ 1`（无噪）；
  🔴 `p=3/4 ⇒ **−1**`（完全退极化）—— **不是 0**：该项在 `p* ≈ 0.1893` 处穿零，
  再往上是负值（负值表示「不可靠传输」，界仍取 ≤0 判死）。
- `p* ≈ 0.1893`：该界的零点（`hashing_bound(p*)=0`），即**退极化信道的 hashing 阈值**。

确定性：纯函数，无时钟 / 无随机 / 无文件 IO。
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

__all__ = [
    "PAULI_ERROR_DIM",
    "binary_entropy",
    "hashing_bound",
    "hashing_threshold",
    "quantum_hamming_rhs",
    "steane_hamming_slack",
    "toric_ground_degeneracy",
    "stabilizer_group_order",
    "logical_class_count",
    "code_family_report",
    "selfcheck_qec_code_family",
]

#: 单比特 Pauli 错误类型的非恒等个数（X / Y / Z）—— 退极化信道里 `p·log₂3` 的 3
PAULI_ERROR_DIM = 3


def binary_entropy(p: float) -> float:
    """二元 Shannon 熵 `H₂(p) = −p·log₂p − (1−p)·log₂(1−p)`（bit）。端点按极限取 0。"""
    if p < 0.0 or p > 1.0:
        raise ValueError("binary_entropy: p 须在 [0,1]，得到 %r" % (p,))
    if p == 0.0 or p == 1.0:
        return 0.0
    return -p * math.log2(p) - (1.0 - p) * math.log2(1.0 - p)


def hashing_bound(p: float) -> float:
    """退极化信道的 hashing 界 `I_c(p) = 1 − H₂(p) − p·log₂3`（bit / 信道使用）。

    `p = 0` ⇒ 1（无噪，可无失真传输）；🔴 `p = 3/4` ⇒ **−1**（完全退极化；穿零点 `p*≈0.1893`，
    再往上是负值 ⇒ 「不可靠传输」）。
    """
    if p < 0.0 or p > 0.75:
        raise ValueError("hashing_bound: p 须在 [0, 0.75]，得到 %r" % (p,))
    return 1.0 - binary_entropy(p) - p * math.log2(float(PAULI_ERROR_DIM))


def hashing_threshold(lo: float = 0.0, hi: float = 0.75, iters: int = 200) -> float:
    """hashing 界的零点 `p*`（二分；`I_c` 在 `[0,0.75]` 上单调降）。仅作能力解析用。"""
    flo = hashing_bound(lo)
    fhi = hashing_bound(hi)
    if flo * fhi > 0.0:
        raise ValueError("hashing_threshold: 区间端点未夹住零点")
    for _ in range(int(iters)):
        mid = 0.5 * (lo + hi)
        fm = hashing_bound(mid)
        if fm == 0.0:
            return mid
        if flo * fm < 0.0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return 0.5 * (lo + hi)


# ── 以下三个是**精确组合量**（整数 / 有理数）⇒ 原理上不可锚，仅作能力与负结果证据 ──


def quantum_hamming_rhs(n: int, t: int) -> int:
    """量子 Hamming（球填充）界右端 `Σ_{j=0}^{t} C(n,j)·3^j`（精确整数）。"""
    if n <= 0 or t < 0:
        raise ValueError("quantum_hamming_rhs: n>0 且 t≥0，得到 n=%r t=%r" % (n, t))
    return sum(math.comb(int(n), j) * (PAULI_ERROR_DIM ** j) for j in range(0, int(t) + 1))


def steane_hamming_slack() -> float:
    """Steane `[[7,1,3]]` 的量子 Hamming 界松紧度 `2^(n−k) / Σ_{j≤t} C(n,j)3^j`。

    `n=7, k=1, d=3 ⇒ t=1`：`2^6 / (1 + 7·3) = 64/22 = 32/11`（精确有理数）。
    🔴 精确有理 ⇒ 任何精确算法都得到同一值 ⇒ `resid ≡ 0` ⇒ **不可锚**（见模块 docstring）。
    """
    n, k, t = 7, 1, 1
    return (2 ** (n - k)) / float(quantum_hamming_rhs(n, t))


def toric_ground_degeneracy(genus: int = 1) -> int:
    """Toric code 在亏格 `g` 曲面上的基态简并 `4^g`（`g=1` ⇒ 4）。精确整数 ⇒ 不可锚。"""
    if genus < 0:
        raise ValueError("toric_ground_degeneracy: genus ≥ 0")
    return 4 ** int(genus)


def stabilizer_group_order(n: int, k: int) -> int:
    """`[[n,k]]` 稳定子群阶 `2^(n−k)`（精确整数）。"""
    if k > n:
        raise ValueError("stabilizer_group_order: k ≤ n")
    return 2 ** (int(n) - int(k))


def logical_class_count(k: int) -> int:
    """逻辑 Pauli 类数 `2^(2k)`（精确整数）。"""
    if k < 0:
        raise ValueError("logical_class_count: k ≥ 0")
    return 2 ** (2 * int(k))


def code_family_report(p: float = 0.10) -> Dict[str, object]:
    """面板用汇总（闭式现算 · 零重算）。"""
    return {
        "p": float(p),
        "hashing_bound_bit": hashing_bound(p),
        "binary_entropy_bit": binary_entropy(p),
        "pauli_overhead_log2_3": math.log2(float(PAULI_ERROR_DIM)),
        "hashing_threshold": hashing_threshold(),
        "steane_hamming_slack": steane_hamming_slack(),
        "toric_degeneracy_g1": toric_ground_degeneracy(1),
        "steane_stabilizer_order": stabilizer_group_order(7, 1),
        "steane_logical_classes": logical_class_count(1),
        "verdict": "DESIGN_BUDGET",
    }


def selfcheck_qec_code_family() -> Dict[str, bool]:
    """能力层自检（≥12 项）。全 PASS 才允许门禁绿。"""
    c: Dict[str, bool] = {}

    # 熵与界的语义
    c["entropy_zero_at_0"] = abs(binary_entropy(0.0)) < 1e-15
    c["entropy_zero_at_1"] = abs(binary_entropy(1.0)) < 1e-15
    c["entropy_max_at_half"] = abs(binary_entropy(0.5) - 1.0) < 1e-12
    c["entropy_symmetric"] = abs(binary_entropy(0.3) - binary_entropy(0.7)) < 1e-12
    c["hashing_one_at_zero_noise"] = abs(hashing_bound(0.0) - 1.0) < 1e-15
    # 🔴 p=3/4 是**完全退极化**，但公式给出 **−1**（穿零点在 p*≈0.1893），不是 0
    c["hashing_minus_one_at_full_depol"] = abs(hashing_bound(0.75) + 1.0) < 1e-12
    c["hashing_monotone_decreasing"] = all(
        hashing_bound(a) > hashing_bound(b)
        for a, b in ((0.00, 0.10), (0.10, 0.20), (0.20, 0.30), (0.60, 0.74)))
    c["hashing_positive_below_threshold"] = hashing_bound(0.15) > 0.0
    c["hashing_negative_above_threshold"] = hashing_bound(0.20) < 0.0

    # 阈值自洽
    th = hashing_threshold()
    c["threshold_matches_literature"] = abs(th - 0.18929) < 2e-4
    c["threshold_roots_the_bound"] = abs(hashing_bound(th)) < 1e-12

    # 精确组合量（能力，不入账本）
    c["steane_slack_exact"] = abs(steane_hamming_slack() - 32.0 / 11.0) < 1e-15
    c["hamming_rhs_steane"] = quantum_hamming_rhs(7, 1) == 22
    c["toric_degeneracy_g1"] = toric_ground_degeneracy(1) == 4
    c["toric_degeneracy_g2"] = toric_ground_degeneracy(2) == 16
    c["stabilizer_order_steane"] = stabilizer_group_order(7, 1) == 64
    c["logical_classes_steane"] = logical_class_count(1) == 4

    # 非法输入必须抛（反向探针依赖这一点）
    def _raises(fn, *a):
        try:
            fn(*a)
        except ValueError:
            return True
        return False

    c["rejects_negative_p"] = _raises(hashing_bound, -0.1)
    c["rejects_p_above_three_quarters"] = _raises(hashing_bound, 0.8)
    c["report_verdict_is_design_budget"] = code_family_report(0.1)["verdict"] == "DESIGN_BUDGET"
    return c


if __name__ == "__main__":
    rep = code_family_report(0.10)
    for k in ("p", "hashing_bound_bit", "binary_entropy_bit", "hashing_threshold",
              "steane_hamming_slack", "toric_degeneracy_g1",
              "steane_stabilizer_order", "steane_logical_classes"):
        print("  %-24s %s" % (k, rep[k]))
    sc = selfcheck_qec_code_family()
    bad = [k for k, v in sc.items() if not v]
    print("\n自检 %d 项：%s" % (len(sc), "ALL PASS" if not bad else "FAIL=%s" % bad))
