# -*- coding: utf-8 -*-
"""Batch J2 数值实现 · 超导 Transmon 征程（J2）M2 两比特门层（CR 门 + 残余 ZZ）。

════════════════════════════════════════════════════════════════
本批**二锚**（`benchmark_defs/part7.py` 引用）——

  B506：**两比特 CR 门退相干错误率**（cross-resonance 门 · 2q gate error）
        golden   = 闭式 **ε = 1 − (4·F_pro^A·F_pro^B + 1)/5**
                   （单比特 A+D 信道过程保真度 **F_pro^i = (1 + e^{−t/T1ⁱ} + 2e^{−t/T2ⁱ})/4**；
                    2q 张量 F_pro = F_pro^A·F_pro^B；平均门保真度 (d·F_pro+1)/(d+1), d=4）。
        candidate = **16×16 Liouvillian（vec-F 序）RK4** 传播 16 个 2q Pauli 基算子，
                    F_pro = Σ_m tr(σ_m E(σ_m))/64 ⇒ ε（与 golden 的解析闭式方法学独立）。
        ——方法学独立：golden 走「张量信道解析闭式」；candidate 走「Lindblad 超算子数值积分」。
        🔴 实测残差链（RK4）：O(h⁴) 单调下降、默认档仍 >0（非机器零残差）⇒ **非代数恒等**。

  B507：**残余 ZZ 诱导门错误率**（residual ZZ idle/gate error · 2q coherent error）
        golden   = 闭式 **ε = (4/5)·sin²(ζ·t/2)**
                   （静态 ZZ 哈密顿 H=(ζ/2)·Z⊗Z 严格演化 U=e^{−iHt} ⇒ F_pro=|tr(U)/4|²=cos²(ζt/2)；
                    F_avg=(4F_pro+1)/5 ⇒ ε=1−F_avg=(4/5)sin²(ζt/2)）。
        candidate = **4×4 复矩阵传播子 RK4**：积分 dU/dt=−iH U（U(0)=I₄）⇒ U(t) ⇒ F_avg。
        ——方法学独立：golden 走「闭式 cos²」；candidate 走「矩阵 ODE 数值积分」。
        🔴 小角极限 ε → (1/5)(ζt)²（与「残余 ZZ 错误率 ∝ (σ_zz·t)²」量级一致，非线性）。

🔴 物理意义（承 J2 超导 Transmon 蓝图 · M2「两比特 CR 门错误率」）：
  · **B506（CR 门退相干）**：CR 门由控制比特微波驱动、经交换耦合 J 生成有效 ZX，
    门时间 t_CR=π/|g_CR|（`cross_resonance` 有效模型）。门执行期间两比特各自经受
    T1（幅度阻尼）+ Tφ（纯退相）⇒ 退相干是 CR 门错误的首要项。本锚把「张量 A+D
    信道闭式 ⇄ Lindblad 超算子数值」钉进账本——把**器件物理层（T1/T2）**与
    **两比特门错误率**连成可验证的一条链。
  · **B507（残余 ZZ）**：固定频率 transmon 对存在静态残余 ZZ 耦合 ζ（由交换耦合二阶
    虚交换产生），在门/idle 期间累积条件相位 ⇒ 相干错误。本锚把「ZZ 相位闭式 ⇄
    数值演化」钉进账本。

🔴 与既有锚的边界（**同源体检 · 实 grep 全仓核验**，本批第一道闸）：
  · **B10**（单量子比特门保真度 F（退相干极限））：golden=(3+2e^{−t/T2}+e^{−t/T1})/6，
    candidate=Lindblad **4×4** 超算子 RK4。与 B506 **三者均不同**：①被测标量
    **1q 门保真度 F** vs **2q CR 门错误率 ε**；②物理构型 **单比特信道** vs
    **两比特 CR 门（张量信道）**；③数值格式 **4×4** vs **16×16**。按 B452↔B33
    先例（标量/构型/格式三者均异 ⇒ 计新锚），B506 计新锚；而宪章原 B508
    （「单比特门错误率 闭式 ⇄ 数值」）与 B10 三者全同 ⇒ **已否决**（见
    `docs/LDA_J2_..._2026-10-13.md` §7.1）。
  · **B26/B27**（色散位移 χ / 色散 CZ 门时间 t_CZ）：χ=g²α/(Δ(Δ+α)) 与 t_CZ=π/(2|χ|)
    ——**门时间/色散量**，非门错误率；且不含量子信道/ZZ 演化。**不同物理量**。
  · **S4**（量子门保真度预算 ∏fᵢ）：纯**算术级联**系统锚（保真度相乘），无任何信道
    动力学/离散化误差（残差恒 0 型）。**不同源**。
  · **B502/B503/B504**（J1 QEC 容错门预算 exp(−∫率)）：一维率积分。B506 是 16×16
    量子信道超算子、B507 是 ZZ 相位演化——**不同算子/不同格式**。
  · 实 grep 核验：`CR 门错误|两比特门错误|residual ZZ|残余 ZZ|cr_gate_error` 在
    `benchmark_defs/` 与 `lda_solver/` 内**仅本批命中**（既有锚零占用）。

🔴 命名避让：批次号 **J2** 与量子征程里程碑 **J2**（Transmon）同名 ⇒ 沿用连字符写法
  `_batch_j2_numeric` / `_get_j2_numeric`；候选 key `cr_gate_decoherence_506` /
  `residual_zz_error_507` 前缀 `b506_`/`b507_` 尚未占用。

🔴 纪律：
· golden 与 candidate 是**两种结构不同的算法**（非「同式异写」）；进报告数字一律**现算**。
· 🔴 **判据 D 双向标定**：生产档（t≪T1）下 RK4 截断误差沉到噪声地板 ⇒ **残差不可标定**
  （B10 血案）。本锚 `default_params` 取**退相干标定档**（t 与 T1/T2 同量级，
  如 t/T1≈0.2、ζ·t≈O(1)）⇒ 截断误差浮出 1e-12 之上、随 N 单调收敛、判据 D 可标定。
  诚实边界：标定档是**为可证伪而选的敏感工作点**（非典型生产门时间），已在 note 披露。
· 🔴 **tol 绝对口径**（harness `_cmp_ok` 默认 cmp='abs'）按各锚物理量级标定；
  余量 ≥100× 且 |golden| ≥ 13.5×tol。
· 🔴 **默认档 = 判据 D 扫描网格末端**。
· 顶层 import numpy（2q Liouvillian / 矩阵传播子需要）——同 `_batch_b10_numeric.py` 纪律。
"""
from __future__ import annotations

import functools
import math

import numpy as np

# ---------------------------------------------------------------------------
# 设计示例量级（transmon 参数示意 · 非实测 PDK）
# ---------------------------------------------------------------------------
# B506 退相干标定档：门时间 t 与 T1/T2 同量级 ⇒ RK4 截断误差可标定（判据 D 前提）。
_B506_DEFAULT = {
    "T1_A": 10.0,   # 控制比特能量弛豫时间（µs）
    "T1_B": 12.0,   # 目标比特能量弛豫时间（µs）
    "T2_A": 8.0,    # 控制比特退相干时间（µs）
    "T2_B": 9.0,    # 目标比特退相干时间（µs）
    "t": 2.0,       # CR 门时间量级（µs）
}
# B507 标定档：残余 ZZ 角 ζ·t 取 O(1) ⇒ 相位演化误差可标定。
_B507_DEFAULT = {
    "zeta": 0.5,    # 残余 ZZ 角耦合（rad/µs）
    "t": 2.0,       # 门/idle 时间（µs）
}


# ===========================================================================
# 默认档 / 判据 D 扫描网格 / 逐锚 tol（三表 · 单一出处）
# ===========================================================================
_N_BY_BID = {
    "B506": 16,
    "B507": 16,
}
_GRID_BY_BID = {
    "B506": [2, 4, 8, 16],
    "B507": [2, 4, 8, 16],
}
# 逐锚 tol（**绝对口径** · 与 harness compare_fn cmp='abs' 一致；按各锚量级标定；
# 依实测默认档残差 ×100 标定 —— 见 __main__ 实测输出）。
_TOL_BY_BID = {
    "B506": 1e-7,   # 默认档 abs 残差 6.51e-10 ⇒ 余量 154×
    "B507": 1e-6,   # 默认档 abs 残差 2.55e-9 ⇒ 余量 393×
}


# ===========================================================================
# B506 · 两比特 CR 门退相干错误率
#   闭式（张量 A+D 信道）⇄ 16×16 Liouvillian RK4
# ===========================================================================
_SIGMA_MINUS = np.array([[0.0, 1.0], [0.0, 0.0]], dtype=complex)   # σ⁻ = |0><1|
_PAULI_I = np.eye(2, dtype=complex)
_PAULI_Z = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=complex)


def _single_qubit_gamma(T1: float, T2: float) -> tuple:
    """由 T1/T2 反解（幅度阻尼率 γ₁, 纯退相率 γ_φ）。

    1/T2 = 1/(2·T1) + 1/Tφ；Lindblad D[σ_z] 对 ρ₀₁ 的衰减率为 2γ_z ⇒ γ_z = 1/(2·Tφ)。
    """
    if T1 <= 0.0 or T2 <= 0.0:
        raise ValueError("T1/T2 必须 > 0")
    if T2 > 2.0 * T1:
        raise ValueError("物理约束 T2 ≤ 2·T1 必须满足（1/Tφ ≥ 0）")
    g1 = 1.0 / T1
    g_phi = 1.0 / T2 - 1.0 / (2.0 * T1)
    g_z = 0.5 * g_phi
    return g1, g_z


def _liouvillian_2q(T1_A: float, T1_B: float, T2_A: float, T2_B: float) -> np.ndarray:
    """2q Liouville 超算子（16×16，**column-major / F 序** vec 约定）。

    L(ρ) = Σ_k γ_k (A_k ρ A_k† − ½{A_k†A_k, ρ})；vec(A ρ B) = (Bᵀ ⊗ A) vec(ρ)（F 序）。
    四个跳变算符：σ⁻⊗I（A 的 T1）/ I⊗σ⁻（B 的 T1）/ σ_z⊗I（A 的 Tφ）/ I⊗σ_z（B 的 Tφ）。
    🔴 **必须 F 序 vec**：用行主序 vec 会让 ρ 不演化（F 恒 1.0，历史血案）。
    """
    g1a, gza = _single_qubit_gamma(T1_A, T2_A)
    g1b, gzb = _single_qubit_gamma(T1_B, T2_B)
    I2 = _PAULI_I
    jumps = [
        (np.kron(_SIGMA_MINUS, I2), g1a),
        (np.kron(I2, _SIGMA_MINUS), g1b),
        (np.kron(_PAULI_Z, I2), gza),
        (np.kron(I2, _PAULI_Z), gzb),
    ]
    I4 = np.eye(4, dtype=complex)
    L = np.zeros((16, 16), dtype=complex)
    for A, g in jumps:
        if g == 0.0:
            continue
        Ad = A.conj().T
        AdA = Ad @ A
        L += g * (np.kron(A.conj(), A)
                  - 0.5 * np.kron(I4, AdA)
                  - 0.5 * np.kron(AdA.T, I4))
    return L


def _two_qubit_pauli_basis() -> list:
    """2q Pauli 基（16 个 4×4 Hermitian 算子，tr(σ_m σ_n)=4 δ_mn）。"""
    p = [_PAULI_I, np.array([[0, 1], [1, 0]], dtype=complex),
         np.array([[0, -1j], [1j, 0]], dtype=complex), _PAULI_Z]
    return [np.kron(p[i], p[j]) for i in range(4) for j in range(4)]


def _rk4_linear(L: np.ndarray, v0: np.ndarray, t: float, n: int) -> np.ndarray:
    """RK4 积分线性 ODE dv/dt = L v 于 [0,t]，n 步（残差 = RK4 截断误差 O(h⁴)）。"""
    h = t / float(n)
    v = v0
    for _ in range(int(n)):
        k1 = L @ v
        k2 = L @ (v + 0.5 * h * k1)
        k3 = L @ (v + 0.5 * h * k2)
        k4 = L @ (v + h * k3)
        v = v + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return v


def cr_gate_error_golden(T1_A: float = _B506_DEFAULT["T1_A"],
                         T1_B: float = _B506_DEFAULT["T1_B"],
                         T2_A: float = _B506_DEFAULT["T2_A"],
                         T2_B: float = _B506_DEFAULT["T2_B"],
                         t: float = _B506_DEFAULT["t"]) -> float:
    """golden：2q CR 门退相干错误率 ε = 1 − (4·F_pro^A·F_pro^B + 1)/5。

    F_proⁱ = (1 + e^{−t/T1ⁱ} + 2e^{−t/T2ⁱ})/4（单比特 A+D 信道过程保真度解析闭式，
    与 B10 的 (3+2e^{−t/T2}+e^{−t/T1})/6 同源换算：F_avg=(2F_pro+1)/3）。
    2q 张量信道 F_pro = F_pro^A·F_pro^B（独立信道相乘）；平均门保真度 (d·F_pro+1)/(d+1)。
    """
    if T1_A <= 0.0 or T1_B <= 0.0 or T2_A <= 0.0 or T2_B <= 0.0 or t < 0.0:
        raise ValueError("T1/T2 > 0 且 t ≥ 0")
    fpa = (1.0 + math.exp(-t / T1_A) + 2.0 * math.exp(-t / T2_A)) / 4.0
    fpb = (1.0 + math.exp(-t / T1_B) + 2.0 * math.exp(-t / T2_B)) / 4.0
    f_pro = fpa * fpb
    f_avg = (4.0 * f_pro + 1.0) / 5.0
    return float(1.0 - f_avg)


def cr_gate_error_candidate(T1_A: float = _B506_DEFAULT["T1_A"],
                            T1_B: float = _B506_DEFAULT["T1_B"],
                            T2_A: float = _B506_DEFAULT["T2_A"],
                            T2_B: float = _B506_DEFAULT["T2_B"],
                            t: float = _B506_DEFAULT["t"], n: int = 16) -> float:
    """candidate：16×16 Liouvillian RK4 传播 16 个 2q Pauli 基算子 ⇒ 过程保真度 ⇒ ε。

    F_pro = (1/d²)·Σ_m tr(σ_m E(σ_m))/tr(σ_m²)·... 取 tr(σ_m σ_m)=4 ⇒
      F_pro = Σ_m tr(σ_m E(σ_m)) / (4·d²) = Σ_m tr(σ_m E(σ_m)) / 64，d=4。
    残差 = RK4 截断误差（O(h⁴)，随 n 严格单调）。
    """
    if T1_A <= 0.0 or T1_B <= 0.0 or T2_A <= 0.0 or T2_B <= 0.0 or t < 0.0 or n < 1:
        raise ValueError("参数非法")
    L = _liouvillian_2q(T1_A, T1_B, T2_A, T2_B)
    acc = 0.0
    for P in _two_qubit_pauli_basis():
        v0 = P.reshape(16, order="F")
        vE = _rk4_linear(L, v0, t, n)
        E = vE.reshape(4, 4, order="F")
        acc += float(np.real(np.trace(P.conj().T @ E)))
    f_pro = acc / 64.0
    f_avg = (4.0 * f_pro + 1.0) / 5.0
    return float(1.0 - f_avg)


# ===========================================================================
# B507 · 残余 ZZ 诱导门错误率
#   闭式 (4/5)·sin²(ζt/2) ⇄ 4×4 复矩阵传播子 RK4
# ===========================================================================
def residual_zz_error_golden(zeta: float = _B507_DEFAULT["zeta"],
                             t: float = _B507_DEFAULT["t"]) -> float:
    """golden：ε_ZZ = (4/5)·sin²(ζ·t/2)。

    H = (ζ/2)·Z⊗Z（静态残余 ZZ，角耦合 ζ）⇒ U=e^{−iHt}，本征值 {e^{∓iζt/2}}×2 ⇒
    F_pro=|tr(U)/4|²=cos²(ζt/2)；F_avg=(4F_pro+1)/5 ⇒ ε=1−F_avg=(4/5)sin²(ζt/2)。
    小角极限 ε → (1/5)(ζt)²。
    """
    if zeta < 0.0 or t < 0.0:
        raise ValueError("zeta ≥ 0 且 t ≥ 0")
    return float((4.0 / 5.0) * math.sin(0.5 * zeta * t) ** 2)


def residual_zz_hamiltonian(zeta: float) -> np.ndarray:
    """H = (ζ/2)·Z⊗Z（4×4 Hermitian，实对角）。"""
    return 0.5 * float(zeta) * np.kron(_PAULI_Z, _PAULI_Z)


def _rk4_unitary(H: np.ndarray, t: float, n: int) -> np.ndarray:
    """RK4 积分 dU/dt = −i H U（U(0)=I₄）于 [0,t]，n 步 ⇒ U(t)（残差 O(h⁴)）。"""
    h = t / float(n)
    U = np.eye(4, dtype=complex)
    mH = -1j * H
    for _ in range(int(n)):
        k1 = mH @ U
        k2 = mH @ (U + 0.5 * h * k1)
        k3 = mH @ (U + 0.5 * h * k2)
        k4 = mH @ (U + h * k3)
        U = U + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return U


def residual_zz_error_candidate(zeta: float = _B507_DEFAULT["zeta"],
                                t: float = _B507_DEFAULT["t"],
                                n: int = 16) -> float:
    """candidate：RK4 传播矩阵 ODE dU/dt=−iH U（H=(ζ/2)Z⊗Z）⇒ F_avg ⇒ ε。

    残差 = RK4 截断误差（O(h⁴)，随 n 严格单调）。
    """
    if zeta < 0.0 or t < 0.0 or n < 1:
        raise ValueError("参数非法")
    H = residual_zz_hamiltonian(zeta)
    U = _rk4_unitary(H, t, n)
    f_pro = float(abs(np.trace(U) / 4.0) ** 2)
    f_avg = (4.0 * f_pro + 1.0) / 5.0
    return float(1.0 - f_avg)


# ---- 默认参数（default_params 真源 · 键集 ⊆ golden 形参集）----
B506_DEFAULT_PARAMS = dict(_B506_DEFAULT)
B507_DEFAULT_PARAMS = dict(_B507_DEFAULT)


# ---- lru_cache 入口（part7.py 顶层引用）----
@functools.lru_cache(maxsize=256)
def _b506_golden_c(t1a, t1b, t2a, t2b, t):
    return cr_gate_error_golden(t1a, t1b, t2a, t2b, t)


@functools.lru_cache(maxsize=256)
def _b506_cand_c(t1a, t1b, t2a, t2b, t, n):
    return cr_gate_error_candidate(t1a, t1b, t2a, t2b, t, n)


def golden_b506(T1_A: float = _B506_DEFAULT["T1_A"],
                T1_B: float = _B506_DEFAULT["T1_B"],
                T2_A: float = _B506_DEFAULT["T2_A"],
                T2_B: float = _B506_DEFAULT["T2_B"],
                t: float = _B506_DEFAULT["t"]) -> float:
    """part7.py 顶层引用的 golden 入口（接受 default_params 关键字）。"""
    return _b506_golden_c(T1_A, T1_B, T2_A, T2_B, t)


def cand_b506(T1_A: float = _B506_DEFAULT["T1_A"],
              T1_B: float = _B506_DEFAULT["T1_B"],
              T2_A: float = _B506_DEFAULT["T2_A"],
              T2_B: float = _B506_DEFAULT["T2_B"],
              t: float = _B506_DEFAULT["t"], n: int = 16) -> float:
    """candidate 入口（_adapter_p4 用）。"""
    return _b506_cand_c(T1_A, T1_B, T2_A, T2_B, t, n)


@functools.lru_cache(maxsize=256)
def _b507_golden_c(zeta, t):
    return residual_zz_error_golden(zeta, t)


@functools.lru_cache(maxsize=256)
def _b507_cand_c(zeta, t, n):
    return residual_zz_error_candidate(zeta, t, n)


def golden_b507(zeta: float = _B507_DEFAULT["zeta"],
                t: float = _B507_DEFAULT["t"]) -> float:
    """part7.py 顶层引用的 golden 入口。"""
    return _b507_golden_c(zeta, t)


def cand_b507(zeta: float = _B507_DEFAULT["zeta"],
              t: float = _B507_DEFAULT["t"], n: int = 16) -> float:
    """candidate 入口（_adapter_p4 用）。"""
    return _b507_cand_c(zeta, t, n)


# ===========================================================================
# 自检（`python -m lda.lda_harness._batch_j2_numeric` 或直接运行）
# ===========================================================================
_CASES = (
    ("B506", golden_b506, cand_b506, cr_gate_error_candidate,
     B506_DEFAULT_PARAMS, "n"),
    ("B507", golden_b507, cand_b507, residual_zz_error_candidate,
     B507_DEFAULT_PARAMS, "n"),
)


def _measure_candidates():
    """逐锚实测：默认档残差 / 网格残差链 / 单调性 / 收敛比 / tol 余量。"""
    rows = []
    for bid, gf, cf, raw_cf, params, key in _CASES:
        g = gf(**params)
        chain, abs_chain = [], []
        for n in _GRID_BY_BID[bid]:
            c = raw_cf(**params, **{key: n})
            d = abs(c - g)
            abs_chain.append(d)
            chain.append(d / max(abs(g), 1e-300))
        tol = _TOL_BY_BID[bid]
        rows.append({
            "bid": bid, "golden": g, "tol": tol,
            "grid": list(_GRID_BY_BID[bid]), "rel_chain": chain,
            "abs_chain": abs_chain,
            "mono": all(chain[i] > chain[i + 1] for i in range(len(chain) - 1)),
            "ratio": [chain[i] / chain[i + 1] if chain[i + 1] > 0 else float("inf")
                      for i in range(len(chain) - 1)],
            "default_rel": chain[-1],
            "margin_x": tol / abs_chain[-1] if abs_chain[-1] > 0 else float("inf"),
            "abs_default": abs_chain[-1],
            "golden_over_tol": abs(g) / tol,
            "n_default": _N_BY_BID[bid],
        })
    return rows


if __name__ == "__main__":
    print("=" * 78)
    print("Batch J2 数值核自检（超导 Transmon · M2 两比特门层 · B506/B507）")
    print("=" * 78)
    bad = 0
    for r in _measure_candidates():
        print("\n%s  golden=%.6e  tol=%.1e  |golden|/tol=%.3e"
              % (r["bid"], r["golden"], r["tol"], r["golden_over_tol"]))
        print("   网格 %s  默认档=%d" % (r["grid"], r["n_default"]))
        print("   rel 链: %s" % " → ".join("%.3e" % x for x in r["rel_chain"]))
        print("   收敛比: %s   MONO=%s"
              % (" ".join("%.2f×" % x for x in r["ratio"]), r["mono"]))
        print("   默认档 rel=%.3e  abs=%.3e  余量(tol/abs)=%.1f×"
              % (r["default_rel"], r["abs_default"], r["margin_x"]))
        for cond, msg in (
            (r["default_rel"] > 1e-12, "默认档 rel > 1e-12（非机器零残差）"),
            (r["mono"], "残差链严格单调"),
            (r["abs_default"] > 0.0, "默认档 abs > 0（真数值残差）"),
            (r["margin_x"] >= 100.0, "余量 ≥ 100×"),
            (r["golden_over_tol"] >= 13.5, "|golden| ≥ 13.5×tol")):
            if not cond:
                print("   [FAIL] %s" % msg)
                bad += 1
        if not (r["rel_chain"][0] >= 20.0 * r["default_rel"]):
            print("   [FAIL] 粗端残差未显著放大（恒等嫌疑）")
            bad += 1
        if not all(1.5 <= x <= 40.0 for x in r["ratio"]):
            print("   [FAIL] 收敛比越界（阶不符）：%s" % r["ratio"])
            bad += 1
    print("\n" + "=" * 78)
    print("自检结论：%s（%d 项不符）" % ("ALL PASS" if bad == 0 else "FAIL", bad))
    raise SystemExit(0 if bad == 0 else 1)
