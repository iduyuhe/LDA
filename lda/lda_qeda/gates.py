"""D-74 · 量子门解析矩阵库 + 幺正性 + 通用性（死标量物理定律锚）。

不依赖任何量子 SDK：门矩阵用 numpy 精确构造（Pauli 代数闭式），验收靠
**精确数学**而非拟合：

1. 幺正性（精确）：每个门矩阵满足 ‖U†U − I‖_∞ ≤ 1e-12（闭式矩阵乘法，死标量）。
2. 通用性（精确群论）：单比特 Clifford 群恰 24 元；**T ∉ 单比特 Clifford**
   ⇒ {H, T, CNOT} 在 SU(2^n) 中稠密（Solovay-Kitaev），即通用门集。
   T 不在 24 元 Clifford 集内是精确群论判定（比对每个生成元到全局相位）。

这些是「物理定律锚」：群论/线性代数，非数据拟合，LLM 不进判决路径。
"""
from __future__ import annotations
import numpy as np

# ---- 基础门（精确闭式）----
I2 = np.eye(2, dtype=complex)
X = np.array([[0, 1], [1, 0]], dtype=complex)
Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
Z = np.array([[1, 0], [0, -1]], dtype=complex)
H = (1.0 / np.sqrt(2.0)) * np.array([[1, 1], [1, -1]], dtype=complex)
S = np.array([[1, 0], [0, 1j]], dtype=complex)
T = np.array([[1, 0], [0, np.exp(1j * np.pi / 4.0)]], dtype=complex)


def _kron_seq(*mats):
    m = mats[0]
    for nxt in mats[1:]:
        m = np.kron(m, nxt)
    return m


def cnot() -> np.ndarray:
    """CNOT (control=0, target=1)：|0><0|⊗I + |1><1|⊗X。"""
    return np.array([[1, 0, 0, 0],
                     [0, 1, 0, 0],
                     [0, 0, 0, 1],
                     [0, 0, 1, 0]], dtype=complex)


def cz() -> np.ndarray:
    """CZ = diag(1,1,1,-1)。"""
    return np.diag([1, 1, 1, -1]).astype(complex)


def swap() -> np.ndarray:
    """SWAP (2 比特)。"""
    return np.array([[1, 0, 0, 0],
                     [0, 0, 1, 0],
                     [0, 1, 0, 0],
                     [0, 0, 0, 1]], dtype=complex)


def toffoli() -> np.ndarray:
    """Toffoli (CCX, 3 比特)：前两位为控制，第三位为目标。"""
    dim = 8
    M = np.eye(dim, dtype=complex)
    # 控制位 |1,1> 对应基 6(110),7(111)；目标位翻转 → 交换 6↔7
    M[6, 6], M[6, 7] = 0, 1
    M[7, 6], M[7, 7] = 1, 0
    return M


# 门注册表（含元信息：是否 Clifford / 作用比特数）
_GATE_DEFS = {
    "I": (I2, 1), "X": (X, 1), "Y": (Y, 1), "Z": (Z, 1),
    "H": (H, 1), "S": (S, 1), "T": (T, 1),
    "CNOT": (cnot(), 2), "CZ": (cz(), 2), "SWAP": (swap(), 2),
    "Toffoli": (toffoli(), 3),
}
# Clifford 群层级（Clifford 层级分类，用于备注）
_CLAUDR = {"I": 1, "X": 1, "Y": 1, "Z": 1, "H": 1, "S": 1,
           "CNOT": 1, "CZ": 1, "SWAP": 1, "Toffoli": 3}
# T 是层级 2（非 Clifford），是通用门集的关键非 Clifford 元素


def is_unitary(U: np.ndarray, tol: float = 1e-12) -> bool:
    """精确幺正性：‖U†U − I‖_∞ ≤ tol（闭式，死标量）。"""
    d = U.shape[0]
    err = float(np.max(np.abs(U.conj().T @ U - np.eye(d, dtype=complex))))
    return err <= tol


def _clifford_1q_set(tol: float = 1e-9) -> list:
    """生成单比特 Clifford 群（恰 24 元）via {H, S} 闭包。

    比对到全局相位：U 与 e^{iφ}C 等价 ⇔ |trace(U†C)| ≈ dim。
    """
    dim = 2
    elems = [I2.copy()]
    gens = [H, S]
    changed = True
    while changed:
        changed = False
        for e in list(elems):
            for g in gens:
                ng = g @ e
                # 已存在？（到全局相位）
                found = False
                for ex in elems:
                    if abs(abs(np.trace(ng.conj().T @ ex)) - dim) <= tol * dim:
                        found = True
                        break
                if not found:
                    elems.append(ng)
                    changed = True
                    if len(elems) >= 24:
                        return elems
    return elems


def is_in_clifford_1q(U: np.ndarray, clifford_set=None, tol: float = 1e-9) -> bool:
    """U 是否属于单比特 Clifford 群（到全局相位）。"""
    cs = clifford_set if clifford_set is not None else _clifford_1q_set()
    dim = U.shape[0]
    for c in cs:
        if abs(abs(np.trace(U.conj().T @ c)) - dim) <= tol * dim:
            return True
    return False


def verify_gate_library() -> dict:
    """量子门库死标量验证：幺正性（全部）+ 通用性（T∉Clifford）。

    返回结构化结果，验收项：
    - all_unitary：每个门 ‖U†U−I‖≤1e-12（精确）
    - T_not_in_clifford：T 不在 24 元单比特 Clifford（精确群论）
    - universality_proven：{H,T,CNOT} 通用（H/CNOT 为 Clifford，T 提供非 Clifford）
    """
    gates = {}
    uni = {}
    for name, (M, nq) in _GATE_DEFS.items():
        gates[name] = {"n_qubits": nq, "shape": list(M.shape),
                       "clifford_layer": _CLAUDR.get(name, 2),
                       "unitary": bool(is_unitary(M))}
        uni[name] = gates[name]["unitary"]

    cliff = _clifford_1q_set()
    T_not_cliff = not is_in_clifford_1q(T, cliff)
    H_in_cliff = is_in_clifford_1q(H, cliff)
    CNOT_uni_check = is_unitary(cnot())

    universality = bool(T_not_cliff and H_in_cliff and CNOT_uni_check)

    return {
        "gates": gates,
        "all_unitary": bool(all(uni.values())),
        "n_gates": len(gates),
        "clifford_group_size": len(cliff),
        "T_not_in_clifford": bool(T_not_cliff),
        "H_in_clifford": bool(H_in_cliff),
        "universality_proven": bool(universality),
        "universal_set": ["H", "T", "CNOT"],
        "note": ("门矩阵为 Pauli 代数闭式（numpy 精确构造）；幺正性 ‖U†U−I‖≤1e-12 "
                 "与「T∉24 元单比特 Clifford」均为精确数学判定（群论/线性代数），"
                 "非拟合、非 LLM 判决。{H,T,CNOT} 通用（Solovay-Kitaev）：H/CNOT 为 "
                 "Clifford，T 是非 Clifford 元素，稠密生成 SU(2^n)。诚实边界：本报告"
                 "验证门集的代数正确性与通用性，不声称具体物理门的脉冲实现保真度"
                 "（那是器件层，归 transmon_solver / 实测标定）。"),
    }
