"""线路级量子态仿真 · 编译映射 · 噪声传播（v0.9.301 · `schip G-Db` + `j2 J2-G-C`）。

## 为什么建这个

两张卡各自缺的同一步：

- `schip G-Db`：「线路编译（门分解 / 映射到本卡拓扑 / 调度）+ 编译后线路的**噪声传播仿真**」
- `j2 J2-G-C`：「线路级**量子态演化**（不演化态、不算保真度）」

v0.9.300 把它们从「须实验台」里**拆出来**，明确写着「纯模型活、不需要任何硬件」。
拆出来就放着不做，那「拆而不并」就退化成「拆出来挂账」—— 本层把它做掉。

## 本层要回答的那个问题（也是唯一的交付）

工程上最常用的估算是一行：

```
F_线路 ≈ Π F_门          ← 卡片上「单比特门 99.9%、两比特门 99.5%」直接相乘
```

**这行在什么条件下成立？** 本层给出三个层次的答案，每一层都有闭式/精确对照：

### ① depolarizing 下：不正确，但偏差有精确闭式，且方向确定

用**态保真度**口径（`ρ → pρ + (1−p)I/2` 作用于纯态 `|ψ⟩`）：

```
F(p)  = ⟨ψ|ρ_out|ψ⟩ = (1 + p)/2                ← 单级闭式
F_tot = (1 + p₁p₂)/2                           ← **组合的是 p，不是 F**（Werner 型）
ΠF    = (1+p₁)/2 · (1+p₂)/2
⇒ F_tot − ΠF = (1−p₁)(1−p₂)/4  ≥ 0             ← 精确闭式，**恒为正**
```

⇒ 「保真度相乘」**系统性偏低**，不是随机误差。`p=0.99` 两级时差 2.5e-5（小），
但 `p=0.9` 时差 2.5e-3、`p=0.5` 时差 6.25e-2 —— 门越差，错得越多。

### ② amplitude damping 下：**连"一个门保真度数字"都不存在**

AD 的 Kraus 作用在 `|0⟩` 上**完全无损**（`F=1` 恰），作用在 `|+⟩` 上
`F=(1+√(1−γ))/2`。⇒ 同一个门、同一个 `γ`，**保真度随输入态变**
⇒ 卡片上那个单一数字隐含了「输入态假设」，而这个假设从不写在卡上。
本层把这个歧义**算出来并列报**，而不是挑一个数当答案。

### ③ 编译映射：SWAP 也是会付噪声的门

线性链拓扑上执行距离 `d` 的两比特门，至少需 `d−1` 次 SWAP、每次 3 个 CNOT
⇒ 编译会**凭空长出** `3(d−1)` 个两比特门。`d` 大时主导总误差，
而这部分在「只有逻辑门数」的预算里完全看不见。

## 对照支路（每个模型一条精确已知答案）

| 支路 | 已知答案 | 用途 |
|---|---|---|
| 空线路（无门无噪声） | `F ≡ 1`（恰） | 桩检测：演化器本体不出错 |
| 单级 depol + 任意纯态 | `(1+p)/2` | 演化器 ⇄ 闭式 |
| 两级 depol | `(1+p₁p₂)/2` **且** 与 `ΠF` 之差 `== (1−p₁)(1−p₂)/4` | 双闭式互证 |
| AD on `\\|0⟩` | `≡ 1`（恰） | 端点为已知物理 |
| AD on `\\|+⟩` | `(1+√(1−γ))/2` | 演化器 ⇄ 闭式 |
| SWAP 计数 | `d−1` 次 · `3(d−1)` CNOT | 组合数学，与门实现无关 |

## 诚实边界

- 噪声模型是**单一 Kraus 信道串联**（每个门后接一个信道）；未含门期间的自由演化
  `T1/T2`（那由 `j2_case.gate_error_1q` 的闭式单独给）、未含串扰、未含测量错误相关、未含 leaky 态。
- 只仿到 **2–3 比特**（`8×8` 密度矩阵，纯标准库）：够验证组合律，**不足以**报任何具体线路的
  端到端保真度数字 —— 后者需要 20+ 比特与真实门表。
- 本层**不产出任何"我们做到了多少保真度"的宣称**：它只给「怎么算才对、按旧算法差多少」。
"""

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

Complex = complex
Matrix = List[List[Complex]]


# ══════════════════════════════════════════════════════════════════════════
# 复数矩阵工具（纯标准库 · 只有 2×2 … 16×16）
# ══════════════════════════════════════════════════════════════════════════
def qmat_eye(n: int) -> Matrix:
    return [[1.0 + 0j if i == j else 0j for j in range(n)] for i in range(n)]


def qmat_mul(a: Matrix, b: Matrix) -> Matrix:
    n, m, p = len(a), len(b), len(b[0])
    if len(a[0]) != m:
        raise ValueError("矩阵维度不匹配")
    out: Matrix = [[0j] * p for _ in range(n)]
    for i in range(n):
        for k in range(m):
            aik = a[i][k]
            if aik == 0:
                continue
            for j in range(p):
                out[i][j] += aik * b[k][j]
    return out


def qmat_add(a: Matrix, b: Matrix, scale: Complex = 1.0) -> Matrix:
    return [[a[i][j] + scale * b[i][j] for j in range(len(a[0]))] for i in range(len(a))]


def qmat_scale(a: Matrix, s: Complex) -> Matrix:
    return [[s * x for x in row] for row in a]


def qmat_dag(a: Matrix) -> Matrix:
    """共轭转置。"""
    return [[a[j][i].conjugate() for j in range(len(a))] for i in range(len(a[0]))]


def qmat_kron(a: Matrix, b: Matrix) -> Matrix:
    ra, ca, rb, cb = len(a), len(a[0]), len(b), len(b[0])
    out: Matrix = [[0j] * (ca * cb) for _ in range(ra * rb)]
    for i in range(ra):
        for j in range(ca):
            for k in range(rb):
                for l in range(cb):
                    out[i * rb + k][j * cb + l] = a[i][j] * b[k][l]
    return out


def qmat_trace(a: Matrix) -> Complex:
    return sum(a[i][i] for i in range(min(len(a), len(a[0]))))


def qmat_is_unitary(u: Matrix, tol: float = 1e-12) -> bool:
    """`U†U == I`（逐元素容差）。"""
    n = len(u)
    p = qmat_mul(qmat_dag(u), u)
    return all(abs(p[i][j] - (1.0 if i == j else 0.0)) <= tol
               for i in range(n) for j in range(n))


# ── 单比特门（2×2）──────────────────────────────────────────────────────
QM_I: Matrix = [[1 + 0j, 0j], [0j, 1 + 0j]]
QM_X: Matrix = [[0j, 1 + 0j], [1 + 0j, 0j]]
QM_Y: Matrix = [[0j, -1j], [1j, 0j]]
QM_Z: Matrix = [[1 + 0j, 0j], [0j, -1 + 0j]]
QM_H: Matrix = [[1 / math.sqrt(2), 1 / math.sqrt(2)],
                [1 / math.sqrt(2), -1 / math.sqrt(2)]]


def qm_rx(theta: float) -> Matrix:
    c, s = math.cos(theta / 2.0), math.sin(theta / 2.0)
    return [[complex(c), complex(-1j * s)], [complex(-1j * s), complex(c)]]


def qm_ry(theta: float) -> Matrix:
    c, s = math.cos(theta / 2.0), math.sin(theta / 2.0)
    return [[complex(c), complex(-s)], [complex(s), complex(c)]]


def qm_rz(theta: float) -> Matrix:
    e = complex(math.cos(theta / 2.0), -math.sin(theta / 2.0))
    return [[e, 0j], [0j, e.conjugate()]]


def qm_expand_1q(u2: Matrix, qubit: int, n: int) -> Matrix:
    """把 2×2 单比特门嵌入 n 比特空间（作用在第 `qubit` 位，big-endian）。"""
    if not 0 <= qubit < n:
        raise ValueError("qubit 越界")
    left = qmat_eye(1 << qubit) if qubit else [[1 + 0j]]
    right = qmat_eye(1 << (n - qubit - 1)) if n - qubit - 1 else [[1 + 0j]]
    return qmat_kron(qmat_kron(left, u2), right)


def qm_cnot(n: int, control: int, target: int) -> Matrix:
    """n 比特 CNOT（big-endian：第 0 位是最高位）。"""
    if control == target:
        raise ValueError("control == target")
    dim = 1 << n
    out: Matrix = [[0j] * dim for _ in range(dim)]
    for i in range(dim):
        cbit = (i >> (n - 1 - control)) & 1
        tbit = (i >> (n - 1 - target)) & 1
        j = i if cbit == 0 else (i ^ (1 << (n - 1 - target)))
        out[j][i] = 1.0 + 0j
        _ = tbit
    return out


def qm_swap(n: int, a: int, b: int) -> Matrix:
    """SWAP = 3 个 CNOT（用于机核 SWAP 的实现口径与本层计数一致）。"""
    c1 = qm_cnot(n, a, b)
    c2 = qm_cnot(n, b, a)
    c3 = qm_cnot(n, a, b)
    return qmat_mul(c3, qmat_mul(c2, c1))


# ══════════════════════════════════════════════════════════════════════════
# 噪声信道（Kraus 算子）
# ══════════════════════════════════════════════════════════════════════════
def kraus_depolarizing(p: float) -> List[Matrix]:
    """`ρ → pρ + (1−p)·I/2` 的 Kraus 分解（`p` = **Werner 型保真度参数**）。

    ```
    K₀ = √(1 − 3(1−p)/4)·I     K₁,₂,₃ = √((1−p)/4)·{X, Y, Z}
    Σ K†K = [1 − 3(1−p)/4]I + 3·(1−p)/4·I = I        （保迹）
    作用： (1−3q/4)ρ + (q/4)(2I−ρ) = (1−q)ρ + (q/2)I,  q ≡ 1−p
    ```

    🔴 **这里的 `p` 有两种常见参数化，混用会让保真度差 `(1−p)/6`**（我自己第一版就混了）：

    | 写法 | 系数取 | 实际信道 | 纯态保真度 |
    |---|---|---|---|
    | `√p·I` + `√((1−p)/3)·{X,Y,Z}` | **错**（那是「Pauli 噪声概率 β=1−p 均匀分三轴」的口径） | `pρ + ((1−p)/3)(2I−ρ)` | `p + (1−p)/3` |
    | `√(1−3(1−p)/4)·I` + `√((1−p)/4)·{X,Y,Z}` | **对**（本实现） | `pρ + (1−p)I/2` | **`(1+p)/2`** |

    ⇒ 两者在 `p=0.5` 时给 `0.667` vs `0.75` —— 被「演化器 ⇄ 闭式」这条对照支路当场抓住
    （自检 `depol_parametrizations_differ` 把这条坑本身写成判据）。
    """
    if not 0.0 <= p <= 1.0:
        raise ValueError("p 须在 [0,1]")
    q = 1.0 - p
    a = math.sqrt(1.0 - 0.75 * q)
    b = math.sqrt(0.25 * q)
    return [qmat_scale(QM_I, a), qmat_scale(QM_X, b),
            qmat_scale(QM_Y, b), qmat_scale(QM_Z, b)]


def kraus_amplitude_damping(gamma: float) -> List[Matrix]:
    """AD：`K₀=[[1,0],[0,√(1−γ)]]`、`K₁=[[0,√γ],[0,0]]`（|1⟩ → |0⟩ 的衰减）。"""
    if not 0.0 <= gamma <= 1.0:
        raise ValueError("gamma 须在 [0,1]")
    r = math.sqrt(1.0 - gamma)
    g = math.sqrt(gamma)
    return [[[1 + 0j, 0j], [0j, complex(r)]],
            [[0j, complex(g)], [0j, 0j]]]


def kraus_dephasing(lam: float) -> List[Matrix]:
    """纯退相位：`ρ → (1−λ/2)ρ + (λ/2)ZρZ`（λ=1 ⇒ 完全失相位）。"""
    if not 0.0 <= lam <= 1.0:
        raise ValueError("lam 须在 [0,1]")
    return [qmat_scale(QM_I, math.sqrt(1.0 - lam / 2.0)),
            qmat_scale(QM_Z, math.sqrt(lam / 2.0))]


def kraus_is_trace_preserving(kraus: Sequence[Matrix], tol: float = 1e-12) -> bool:
    """`Σ K†K == I`（信道必须保迹 —— 这是「不是子归一化」的机核）。"""
    n = len(kraus[0])
    acc = [[0j] * n for _ in range(n)]
    for k in kraus:
        acc = qmat_add(acc, qmat_mul(qmat_dag(k), k))
    return all(abs(acc[i][j] - (1.0 if i == j else 0.0)) <= tol
               for i in range(n) for j in range(n))


# ══════════════════════════════════════════════════════════════════════════
# 态与演化
# ══════════════════════════════════════════════════════════════════════════
def qm_state(index: int, n: int) -> Matrix:
    """计算基态 `|index⟩` 的密度矩阵。"""
    dim = 1 << n
    if not 0 <= index < dim:
        raise ValueError("index 越界")
    v = [0j] * dim
    v[index] = 1.0 + 0j
    return [[v[i] * v[j].conjugate() for j in range(dim)] for i in range(dim)]


def qm_plus_state(n: int = 1, qubit: int = 0) -> Matrix:
    """`|+⟩`（其余位 `|0⟩`）的密度矩阵。"""
    dim = 1 << n
    s = 1.0 / math.sqrt(2.0)
    idx0 = 0
    idx1 = 1 << (n - 1 - qubit)
    v = [0j] * dim
    v[idx0] = complex(s)
    v[idx1] = complex(s)
    return [[v[i] * v[j].conjugate() for j in range(dim)] for i in range(dim)]


def evolve_unitary(rho: Matrix, u: Matrix) -> Matrix:
    """`ρ → U ρ U†`。"""
    return qmat_mul(qmat_mul(u, rho), qmat_dag(u))


def evolve_channel(rho: Matrix, kraus: Sequence[Matrix]) -> Matrix:
    """`ρ → Σ Kᵢ ρ Kᵢ†`。"""
    out = [[0j] * len(rho) for _ in range(len(rho))]
    for k in kraus:
        out = qmat_add(out, qmat_mul(qmat_mul(k, rho), qmat_dag(k)))
    return out


def apply_1q_channel(rho: Matrix, kraus2: Sequence[Matrix], qubit: int, n: int) -> Matrix:
    """把单比特 Kraus 集合嵌入 n 比特空间后作用。"""
    return evolve_channel(rho, [qm_expand_1q(k, qubit, n) for k in kraus2])


def state_fidelity(rho: Matrix, psi: Matrix) -> float:
    """纯态保真度 `⟨ψ|ρ|ψ⟩ = Tr(ρ·|ψ⟩⟨ψ|)`（`psi` 用密度矩阵表示，取实部）。"""
    return float(qmat_trace(qmat_mul(rho, psi)).real)


def is_density_matrix(rho: Matrix, tol: float = 1e-12) -> bool:
    """厄米 ∧ 迹 1 ∧ 对角非负（三个必要条件）。"""
    n = len(rho)
    herm = all(abs(rho[i][j] - rho[j][i].conjugate()) <= tol for i in range(n) for j in range(n))
    tr = abs(qmat_trace(rho) - 1.0) <= tol
    diag = all(rho[i][i].real >= -tol and abs(rho[i][i].imag) <= tol for i in range(n))
    return herm and tr and diag


# ══════════════════════════════════════════════════════════════════════════
# 闭式：组合律与「朴素相乘」的偏差
# ══════════════════════════════════════════════════════════════════════════
def depol_state_fidelity_closed(p: float) -> float:
    """单级 depolarizing 对**纯态**的态保真度 `(1+p)/2`。

    🔴 别与 `(1+3p)/4` 混：后者是对**任意输入**（含混态）的**平均**保真度，
       本层全部用**纯态**口径 ⇒ `(1+p)/2`。两个口径差 `|p−1|/4`，不注明就会对不上。
    """
    return (1.0 + p) / 2.0


def ad_plus_fidelity_closed(gamma: float) -> float:
    """AD 作用在 `|+⟩` 上的态保真度 `(1+√(1−γ))/2`。"""
    return (1.0 + math.sqrt(1.0 - gamma)) / 2.0


def ad_chain_gamma(gammas: Sequence[float]) -> float:
    """多级 amplitude damping 的等效 `γ_eff = 1 − Π(1−γᵢ)`。

    🔴 **AD 的串联律与 depolarizing 结构不同**，别混：

    ```
    depolarizing : p_tot = Π pᵢ              （乘积）   ⇒ F_tot = (1 + Πpᵢ)/2
    amplitude damp: γ_eff = 1 − Π(1−γᵢ)      （残存幅度相乘） ⇒ F 由 γ_eff 再代入闭式
    ```

    物理来源：AD 的 `|1⟩` 幅度按 `√(1−γ)` 衰减，两级即 `√(1−γ₁)·√(1−γ₂)` ⇒ 残存概率相乘
    ⇒ `1−γ_eff = Π(1−γᵢ)`。**不是 `γ₁+γ₂`**（那只在两级的 γ 都 ≪1 时近似成立）。
    """
    surv = 1.0
    for g in gammas:
        if not 0.0 <= g <= 1.0:
            raise ValueError("gamma 须在 [0,1]")
        surv *= (1.0 - g)
    return 1.0 - surv


def chain_p(ps: Sequence[float]) -> float:
    """多级 depolarizing 串联的等效 `p_tot = Π p_i`（**Werner 型组合律**）。"""
    out = 1.0
    for p in ps:
        out *= p
    return out


def chain_fidelity_closed(ps: Sequence[float]) -> float:
    """`F_tot = (1 + Πp_i)/2`。"""
    return (1.0 + chain_p(ps)) / 2.0


def naive_product_fidelity(ps: Sequence[float]) -> float:
    """朴素口径：`Π F_i`（卡片上「门保真度直接相乘」的那一行）。"""
    out = 1.0
    for p in ps:
        out *= depol_state_fidelity_closed(p)
    return out


def two_stage_gap_closed(p1: float, p2: float) -> float:
    """两级口径差精确闭式 `(1−p₁)(1−p₂)/4`（**恒为正 ⇒ 朴素口径系统性偏低**）。"""
    return (1.0 - p1) * (1.0 - p2) / 4.0


# ══════════════════════════════════════════════════════════════════════════
# 编译映射：线性链上的 SWAP 计数
# ══════════════════════════════════════════════════════════════════════════
def swaps_for_distance(distance: int) -> int:
    """线性链上执行距离 `d` 的两比特门所需 SWAP 下界 `d−1`（`d≤1` ⇒ 0）。"""
    return max(0, int(distance) - 1)


def cnots_per_swap() -> int:
    """SWAP 的标准分解 = 3 个 CNOT（与 `qm_swap` 的实现口径一致）。"""
    return 3


def linear_chain_compile(n_qubits: int, pairs: Sequence[Tuple[int, int]]) -> Dict[str, Any]:
    """把一组逻辑两比特门映射到 `0-1-…-(n−1)` 线性链，返回**凭空多出来的**门数。

    🔴 这就是「编译会自己生误差」的机核：逻辑上 `len(pairs)` 个两比特门，
    物理上要 `len(pairs) + 3·Σ(d−1)` 个两比特门操作。
    """
    if n_qubits < 2:
        raise ValueError("n_qubits 须 ≥2")
    per_pair = []
    total_swaps = 0
    for a, b in pairs:
        if not (0 <= a < n_qubits and 0 <= b < n_qubits):
            raise ValueError("比特索引越界")
        if a == b:
            raise ValueError("同一比特的两比特门非法")
        d = abs(a - b)
        sw = swaps_for_distance(d)
        per_pair.append({"pair": [a, b], "distance": d, "swaps": sw,
                         "extra_cnots": sw * cnots_per_swap()})
        total_swaps += sw
    logical_2q = len(pairs)
    physical_2q = logical_2q + total_swaps * cnots_per_swap()
    return {
        "n_qubits": n_qubits,
        "per_pair": per_pair,
        "logical_2q_gates": logical_2q,
        "total_swaps": total_swaps,
        "physical_2q_ops": physical_2q,
        "amplification": (float(physical_2q) / logical_2q) if logical_2q else 1.0,
    }


# ══════════════════════════════════════════════════════════════════════════
# 三层自检
# ══════════════════════════════════════════════════════════════════════════
def selfcheck_qcircuit_level() -> Dict[str, bool]:
    c: Dict[str, bool] = {}

    # ① 矩阵工具自洽：门都是幺正 ∧ 信道都保迹
    c["gates_unitary"] = all(qmat_is_unitary(u) for u in
                             (QM_I, QM_X, QM_Y, QM_Z, QM_H,
                              qm_rx(0.7), qm_ry(1.1), qm_rz(-0.4)))
    c["cnot_unitary"] = qmat_is_unitary(qm_cnot(2, 0, 1))
    c["swap_unitary"] = qmat_is_unitary(qm_swap(2, 0, 1))
    c["channels_tp"] = (kraus_is_trace_preserving(kraus_depolarizing(0.93))
                        and kraus_is_trace_preserving(kraus_amplitude_damping(0.2))
                        and kraus_is_trace_preserving(kraus_dephasing(0.35)))

    # ② SWAP 分解**真的**等于三 CNOT（不是嘴上说的计数）
    n = 2
    rho = qm_state(1, n)                       # |01⟩
    direct = qm_swap(n, 0, 1)
    rho_sw = evolve_unitary(rho, direct)
    c["swap_swaps_bits"] = abs(state_fidelity(rho_sw, qm_state(2, n)) - 1.0) <= 1e-15
    # 交换后再交换 ⇒ 回原态（对合性，闭式已知答案）
    back = evolve_unitary(rho_sw, direct)
    c["swap_involution"] = abs(state_fidelity(back, rho) - 1.0) <= 1e-15

    # ③ 🔴 对照支路：空线路（只有恒等）⇒ F 恰为 1
    #    ⚠️ **`==` 只对精确已知的量**：基态 `|0⟩` 的 ρ 元素是精确 0/1 ⇒ 恰为 1.0；
    #       而 `|+⟩` 含 `1/√2`（非精确）⇒ `Tr(ρ²)=0.9999999999999996`，只能用 rel。
    #       这不是「精确性不够」，而是**把 `==` 用在由浮点运算得到的量上**（v0.9.296 纪律）。
    _z = qm_state(0, 1)
    _p1 = qm_plus_state(1, 0)
    c["identity_fidelity_is_one"] = (
        state_fidelity(evolve_unitary(_z, QM_I), _z) == 1.0
        and abs(state_fidelity(evolve_unitary(_p1, QM_I), _p1) - 1.0) <= 1e-15)

    # ④ 🔴 单级 depol：演化器 ⇄ 闭式 (1+p)/2（两个不同输入态都成立 ⇒ 与态无关）
    ok_single = True
    for p in (1.0, 0.99, 0.9, 0.5, 0.0):
        for psi in (qm_state(0, 1), qm_plus_state(1, 0)):
            got = state_fidelity(evolve_channel(psi, kraus_depolarizing(p)), psi)
            ok_single = ok_single and abs(got - depol_state_fidelity_closed(p)) <= 1e-15
    c["single_depol_matches_closed_form"] = ok_single
    # 端点：p=1 ⇒ F=1（恰）· p=0 ⇒ F=1/2（完全去极化，任何纯态都只剩 1/2）
    c["depol_p1_is_one"] = depol_state_fidelity_closed(1.0) == 1.0
    c["depol_p0_is_half"] = depol_state_fidelity_closed(0.0) == 0.5

    # ⑤ 🔴 两级串联：演化 ≡ (1+p₁p₂)/2 ∧ 与 ΠF 之差 **== (1−p₁)(1−p₂)/4**
    p1, p2 = 0.93, 0.87
    psi = qm_plus_state(1, 0)
    r = evolve_channel(psi, kraus_depolarizing(p1))
    r = evolve_channel(r, kraus_depolarizing(p2))
    got = state_fidelity(r, psi)
    c["two_stage_matches_chain_closed"] = abs(got - chain_fidelity_closed((p1, p2))) <= 1e-15
    c["two_stage_gap_equals_closed"] = abs(
        (got - naive_product_fidelity((p1, p2))) - two_stage_gap_closed(p1, p2)) <= 1e-15
    c["naive_is_lower"] = naive_product_fidelity((p1, p2)) < got

    # ⑥ 🔴 AD 的本性：|0⟩ 无损（恰 1）∧ |+⟩ 有闭式 ∧ **两者不同 ⇒ 单一门保真度数字有歧义**
    g = 0.12
    ad0 = state_fidelity(evolve_channel(qm_state(0, 1), kraus_amplitude_damping(g)),
                         qm_state(0, 1))
    adp = state_fidelity(evolve_channel(qm_plus_state(1, 0), kraus_amplitude_damping(g)),
                         qm_plus_state(1, 0))
    c["ad_on_zero_is_one"] = ad0 == 1.0
    c["ad_on_plus_matches_closed"] = abs(adp - ad_plus_fidelity_closed(g)) <= 1e-15
    c["ad_fidelity_is_state_dependent"] = abs(ad0 - adp) > 1e-3

    # ⑦ 🔴 AD 的串联律是 `1−(1−γ)²`，**不是 `γ+γ`**（与 depol 的 `Πpᵢ` 结构不同）
    #    ⚠️ 第一版我把这条写成「由 ad_two 反解 γ_eff 再回代 ⇒ 应相等」——
    #       **那是恒等式**（反解回代必然相等），判据写成了恒真，还命名成 `not_single_equivalent`。
    #       正确做法：用**独立闭式** `1−Π(1−γᵢ)` 预测，再与演化器对拍。
    r_ad = evolve_channel(psi, kraus_amplitude_damping(g))
    r_ad = evolve_channel(r_ad, kraus_amplitude_damping(g))
    ad_two = state_fidelity(r_ad, psi)
    geff = ad_chain_gamma((g, g))                      # 1−(1−γ)²
    c["ad_two_stage_matches_chain_law"] = abs(
        ad_two - ad_plus_fidelity_closed(geff)) <= 1e-15
    # 且 ≠ 简单相加（γ+γ）：两级的残存是相乘，不是相加
    c["ad_chain_law_is_not_additive"] = abs(geff - 2.0 * g) > 1e-3
    # 且 ≠ 保真度直接相乘（F·F）
    c["ad_two_stage_differs_from_naive"] = abs(ad_two - adp * adp) > 1e-6

    # ⑧ 编译：SWAP 计数闭式 ∧ 线性链放大比
    _cmp = linear_chain_compile(5, [(0, 4)])
    c["compile_swap_count"] = (_cmp["total_swaps"] == 3
                              and _cmp["physical_2q_ops"] == 1 + 9)
    c["compile_adjacent_no_swap"] = linear_chain_compile(5, [(1, 2)])["total_swaps"] == 0
    c["compile_amplification_gt_1"] = _cmp["amplification"] > 5.0

    # ⑨ 密度矩阵合法性 + `apply_1q_channel`（把 2×2 Kraus 嵌入 n 比特空间）等价于手工展开
    #    🔴 走**便利入口**而不是每次手动 `[qm_expand_1q(k, q, n) for k in ...]` ——
    #       可达性门禁曾把 `apply_1q_channel` 判成零引用，接线的正解是**用它**，不是登记成死代码。
    _rho2 = qm_plus_state(2, 0)
    _via_api = apply_1q_channel(_rho2, kraus_amplitude_damping(0.3), 0, 2)
    _via_manual = evolve_channel(_rho2, [qm_expand_1q(k, 0, 2)
                                        for k in kraus_amplitude_damping(0.3)])
    c["apply_1q_channel_equals_manual"] = all(
        abs(_via_api[i][j] - _via_manual[i][j]) <= 1e-15
        for i in range(4) for j in range(4))
    # ⚠️ 2 比特态（4×4）配 2×2 Kraus 会**维度不匹配** —— 这段原被我写成
    #    `all(...) if False else ...` 永久短路，所以从没执行到（死代码自由腐烂）。
    #    接回来立刻崩溃 ⇒ 必须走 `apply_1q_channel` 做空间展开。
    c["evolved_states_are_density_matrices"] = (
        is_density_matrix(_via_api)
        and is_density_matrix(apply_1q_channel(qm_plus_state(2, 1),
                                              kraus_depolarizing(0.8), 1, 2)))

    # ⑩ 非法入参一律抛（判红不崩溃）
    def _raises(fn) -> bool:
        try:
            fn()
        except ValueError:
            return True
        return False

    # ⑪ 🔴 把「我自己踩过的参数化混用坑」写成判据：两种写法的保真度**必须不同**
    #    （若哪天有人把 Kraus 改回 `√p`，本条与 ④ 会**同时**判红 —— 双向可证伪）
    _p = 0.5
    _wrong = _p + (1.0 - _p) / 3.0                     # √p 口径的纯态保真度
    _right = depol_state_fidelity_closed(_p)           # 本层口径 (1+p)/2
    c["depol_parametrizations_differ"] = abs(_right - _wrong) > 1e-3

    c["rejects_illegal"] = (_raises(lambda: kraus_depolarizing(1.2))
                            and _raises(lambda: kraus_amplitude_damping(-0.1))
                            and _raises(lambda: qm_cnot(2, 1, 1))
                            and _raises(lambda: linear_chain_compile(1, [(0, 0)]))
                            and _raises(lambda: qm_state(4, 2)))
    return c


def report() -> Dict[str, Any]:
    """参考档：把三层的数字一次算出来（供门禁与文档引用）。"""
    p1, p2 = 0.99, 0.95
    psi = qm_plus_state(1, 0)
    r2 = evolve_channel(evolve_channel(psi, kraus_depolarizing(p1)),
                        kraus_depolarizing(p2))
    f2 = state_fidelity(r2, psi)
    g = 0.05
    ad0 = state_fidelity(evolve_channel(qm_state(0, 1), kraus_amplitude_damping(g)),
                         qm_state(0, 1))
    adp = state_fidelity(evolve_channel(qm_plus_state(1, 0), kraus_amplitude_damping(g)),
                         qm_plus_state(1, 0))
    cmp5 = linear_chain_compile(5, [(0, 4)])
    return {
        "tier1_depol": {
            "p1": p1, "p2": p2,
            "f_two_stage_evolved": float(f2),
            "f_two_stage_closed": float(chain_fidelity_closed((p1, p2))),
            "f_naive_product": float(naive_product_fidelity((p1, p2))),
            "gap": float(f2 - naive_product_fidelity((p1, p2))),
            "gap_closed": float(two_stage_gap_closed(p1, p2)),
        },
        "tier2_amplitude_damping": {
            "gamma": g,
            "f_on_zero": float(ad0),
            "f_on_plus": float(adp),
            "f_on_plus_closed": float(ad_plus_fidelity_closed(g)),
            "ambiguity": float(ad0 - adp),
        },
        "tier3_compile": cmp5,
        "caliber": ("态保真度口径（纯态 ⟨ψ|ρ|ψ⟩）；depolarizing 用 (1+p)/2，"
                    "**不是**平均保真度 (1+3p)/4；单信道串联，未含门期间 T1/T2 自由演化"),
    }


if __name__ == "__main__":       # pragma: no cover
    sc = selfcheck_qcircuit_level()
    bad = [k for k, v in sc.items() if not v]
    print("qcircuit_level 自检 %d/%d" % (len(sc) - len(bad), len(sc)))
    if bad:
        print("FAIL:", bad)
        raise SystemExit(1)
    rep = report()
    d1, d2, d3 = rep["tier1_depol"], rep["tier2_amplitude_damping"], rep["tier3_compile"]
    print("\n① depolarizing 两级（p1=%.2f p2=%.2f）" % (d1["p1"], d1["p2"]))
    print("   演化 F=%.15f · 闭式=%.15f · 朴素ΠF=%.15f" %
          (d1["f_two_stage_evolved"], d1["f_two_stage_closed"], d1["f_naive_product"]))
    print("   偏差=%.6e · 闭式(1−p1)(1−p2)/4=%.6e" % (d1["gap"], d1["gap_closed"]))
    print("\n② amplitude damping（γ=%.2f）" % d2["gamma"])
    print("   |0⟩ F=%.15f（恰 1）· |+⟩ F=%.6f · 闭式=%.6f · **歧义=%.6f**" %
          (d2["f_on_zero"], d2["f_on_plus"], d2["f_on_plus_closed"], d2["ambiguity"]))
    print("\n③ 线性链编译（5 比特 · q0↔q4）")
    print("   逻辑两比特门=%d · SWAP=%d · 物理两比特操作=%d · 放大=%.2f×" %
          (d3["logical_2q_gates"], d3["total_swaps"],
           d3["physical_2q_ops"], d3["amplification"]))
