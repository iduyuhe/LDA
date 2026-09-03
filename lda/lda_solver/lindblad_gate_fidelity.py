"""单量子比特 Lindblad 主方程数值积分 → 平均门保真度（B10 独立候选，v0.9.24）。

自包含、纯 numpy、零外部依赖、零 GPU。**LLM 不进判决路径**。

================================================================================
物理模型
================================================================================
单比特 idle 门（H=0，目标门 U=I），T=0 热库下的主方程：

    dρ/dt = γ₁·D[σ₋]ρ + γ_φ·D[σ_z]ρ,   D[A]ρ = AρA† − ½{A†A, ρ}

    γ₁ = 1/T1                        （能量弛豫）
    γ_φ = (1/T2 − 1/(2·T1)) / 2      （纯退相位；相干衰减 1/T2 = γ₁/2 + 2γ_φ）

超算子形式（row-major vec 约定）：vec(AρB) = (A ⊗ Bᵀ)·vec(ρ)。
4×4 Liouvillian L，对 4 个 Pauli 基各积分一次 ⇒ 得到**完整 PTM 矩阵**
（Pauli Transfer Matrix，PTM[i,j] = ½·Tr[σ_i·Λ(σ_j)]）。

平均门保真度（Nielsen & Chuang，d=2）：
    F_avg = ½ + (PTM_xx + PTM_yy + PTM_zz) / 6
           = (3 + 2·e^(−t/T2) + e^(−t/T1)) / 6        ← 闭式（golden 侧）

================================================================================
🔴 三条必须钉死的坑（改本模块前必读）
================================================================================
1. **row-major vec 下 bipartite 分解不是裸 np.kron**。
   对 2-qubit ρ，row-major vec 的索引顺序是 (iA,iB,jA,jB)，而 kron(L, I₄) 要求
   (iA,jA,iB,jB) ⇒ 直接 kron 会让 ρ 根本不演化，F 恒等于 1.0（v1 探针实测）。
   本模块因此**完全避开 2-qubit 升维**：不构造 Choi 矩阵，改用「4 个 Pauli 基
   各积分一次 ⇒ 完整 PTM」，只用 4×4 Liouvillian。数学上等价且更省。

2. **生产档位残差落在机器精度，不可标定**。
   t_gate=0.02 µs、T1/T2 ~ 60-80 µs ⇒ 无量纲演化量 |L|·t ≈ 2.5e-4，RK4 从
   N=5 到 N=400 残差恒为 1.11e-16（实测），与 N 无关。
   ⇒ 不能靠「生产档位残差」证明积分器在工作（与自证桩的 |Δ|≡0 不可区分）。
   本模块的自校锚因此**全部建在可标定的量上**：
     · PTM 非对角元 PTM[Z,I] = −(1 − e^(−t/T1)) ≈ −2.5e-4（不是机器精度）
     · 敏感 regime（t=200 µs，|L|t ≈ 2.7）残差 8.8e-9，且 N 加倍降 16.4×（O(h⁴)）
     · 稳态极限 t→∞ ⇒ F → 0.5（完全退相干通道的平均保真度）
   生产档位的「残差恒为机器精度」是**物理事实**，不是缺陷，但必须如实标注。

3. **PTM 不是对角的**。振幅阻尼把激发态布居转到基态 ⇒
   PTM[Z,I] = −(1 − e^(−t/T1)) ≠ 0（下三角）。平均保真度只依赖 PTM 的**迹**
   （Bloch 球面积分时 ⟨r_i⟩=0 让非对角元不贡献），所以闭式仍然精确，
   但候选的数值路径会真实遇到这些非对角元 —— 这是「不假设对角结构」的凭据。

================================================================================
独立性声明
================================================================================
golden（golden.py::b10_gate_fidelity）= 闭式 (3+2e^(−t/T2)+e^(−t/T1))/6，
用 math.exp 独立实现，不 import 本模块。
candidate（本模块）= 16 元超算子数值积分，不套任何衰减率公式。

两者物理同源、方法独立（解析闭式 vs 数值 ODE）。判据窗口实测（v0.9.24）：
    baseline |Δ| = 1.11e-16  <  tol = 1e-8  <  min(10% 扰动信号) = 3.787e-6
余量：下界 9e7×，上界 379×。
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "N_STEPS",
    "liouvillian",
    "propagate",
    "ptm",
    "average_gate_fidelity",
    "closed_form",
    "selfcheck_ptm_structure",
    "selfcheck_rk4_convergence",
    "selfcheck_steady_state",
    "selfcheck_unphysical_input",
    "run_selfchecks",
]

# ---------------------------------------------------------------------------
# 生产档位
# ---------------------------------------------------------------------------
# N_STEPS：RK4 步数。生产档位下残差与 N 无关（恒 1.11e-16），取 50 只为
# 「在敏感 regime 下仍有 8.8e-9 的可标定残差」留一致性，不是精度需要。
# ⚠️ 不要为了「让残差更好看」去调它 —— 那等于把可标定证据调没了。
N_STEPS = 50

_I2 = np.eye(2, dtype=complex)
_SX = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex)
_SY = np.array([[0.0, -1j], [1j, 0.0]], dtype=complex)
_SZ = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=complex)
_SM = np.array([[0.0, 0.0], [1.0, 0.0]], dtype=complex)  # σ₋
_PAULI = (_I2, _SX, _SY, _SZ)
_PAULI_NAME = ("I", "X", "Y", "Z")

# 敏感 regime 用的门时长（µs）：|L|·t ≈ (1/T1)·t = 0.0125×200 = 2.5 ~ O(1)。
# 只有在 |L|t ~ O(1) 时 RK4 的截断误差才浮出机器精度、可被标定。
T_SENSITIVE = 200.0
# 残差可接受区间（双向）：下界排除「回落 golden / 自证桩」（|Δ|≡0），
# 上界排除「积分器实现错误」。实测 N=50 时 |Δ| = 8.755e-9，落在区间中部。
SENSITIVE_LO = 1e-12
SENSITIVE_HI = 1e-6
# O(h⁴) 收敛：N 加倍残差应降 ~16×，断言 ≥8×（留 2× 浮点/平台余量）。
CONVERGE_MIN_RATIO = 8.0


def _dissipator(A: np.ndarray) -> np.ndarray:
    """Lindblad 耗散超算子 D[A]，row-major vec 约定。

    vec(AρB) = (A ⊗ Bᵀ)·vec(ρ)
    D[A]ρ = AρA† − ½{A†A, ρ}
          ⇒ A ⊗ conj(A) − ½[ (A†A) ⊗ I + I ⊗ (A†A)ᵀ ]
    （B = A† ⇒ Bᵀ = (A†)ᵀ = conj(A)）
    """
    AdagA = A.conj().T @ A
    return (np.kron(A, A.conj())
            - 0.5 * (np.kron(AdagA, _I2) + np.kron(_I2, AdagA.T)))


def liouvillian(T1: float, T2: float) -> np.ndarray:
    """单比特 Liouvillian（H=0，idle 门；T=0 热库），4×4 复数矩阵。

    参数
    ----
    T1, T2 : 能量弛豫 / 相干时间（µs）。

    抛出
    ----
    ValueError
        T2 > 2·T1 ⇒ 纯退相位率 γ_φ < 0，违反 T2 ≤ 2T1 的物理约束。
        **不静默 clamp** —— 静默 clamp 会让非物理参数产生看似合法的保真度。
    """
    g1 = 1.0 / float(T1)
    gphi = (1.0 / float(T2) - 0.5 * g1) / 2.0
    if gphi < -1e-15:
        raise ValueError(
            f"非物理相干时间: T2={float(T2)} > 2·T1={2.0 * float(T1)} "
            f"⇒ 纯退相位率 γ_φ={gphi:.6e} < 0")
    return g1 * _dissipator(_SM) + max(gphi, 0.0) * _dissipator(_SZ)


def propagate(L: np.ndarray, rho0: np.ndarray, t: float, n_steps: int) -> np.ndarray:
    """RK4 积分 d(vec ρ)/dt = L·vec(ρ)，返回 2×2 密度矩阵。

    RK4 全局误差 O(h⁴)（敏感 regime 实测收敛比 16.2~16.5×，见 selfcheck）。
    """
    v = np.asarray(rho0, dtype=complex).reshape(-1).copy()
    h = float(t) / int(n_steps)
    for _ in range(int(n_steps)):
        k1 = L @ v
        k2 = L @ (v + 0.5 * h * k1)
        k3 = L @ (v + 0.5 * h * k2)
        k4 = L @ (v + h * k3)
        v = v + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return v.reshape(2, 2)


def ptm(T1: float, T2: float, t: float, n_steps: int = N_STEPS) -> np.ndarray:
    """完整 Pauli 转移矩阵 PTM[i,j] = ½·Tr[σ_i · Λ(σ_j)]（4×4 实数）。

    对 4 个 Pauli 基各积分一次 Lindblad ⇒ 不做任何解析化简：
    不假设对角、不假设衰减率形式、不套闭式。
    """
    L = liouvillian(T1, T2)
    cols = [propagate(L, P, t, n_steps) for P in _PAULI]
    M = np.zeros((4, 4), dtype=float)
    for i, Pi in enumerate(_PAULI):
        for j in range(4):
            M[i, j] = 0.5 * float(np.real(np.trace(Pi @ cols[j])))
    return M


def average_gate_fidelity(T1: float, T2: float, t_gate: float,
                          n_steps: int = N_STEPS) -> float:
    """B10 候选：数值 Lindblad 积分得到的平均门保真度 F_avg。

    F_avg = ½ + (PTM_xx + PTM_yy + PTM_zz)/6

    该式来自 Bloch 球面积分（⟨r_i⟩=0、⟨r_i r_j⟩=δ_ij/3），**不依赖** PTM 对角
    假设 ⇒ 即便通道有非对角 PTM 元（振幅阻尼的 PTM[Z,I]）也精确。
    """
    M = ptm(T1, T2, t_gate, n_steps)
    # 🔴 必须 float() 包裹：M 的元素是 np.float64，裸返回会让下游
    # `passed = abs(cand-golden) <= tol` 得到 **np.bool_**，进而在
    # `report.format_json` 里抛 `TypeError: Object of type bool is not
    # JSON serializable`（v0.9.24 全量回归实测抓到，与 v0.9.17 B24 同类）。
    return float(0.5 + (M[1, 1] + M[2, 2] + M[3, 3]) / 6.0)


def closed_form(T1: float, T2: float, t: float) -> float:
    """参考闭式 F=(3+2e^(−t/T2)+e^(−t/T1))/6。

    🔴 **仅供自校锚与 smoke 使用**。harness 判决路径的 golden 是
    golden.py::b10_gate_fidelity 的独立 math.exp 实现 —— 两条实现不共享代码，
    否则「闭式两侧同源」会让验证退化成同义反复。
    """
    return (3.0 + 2.0 * np.exp(-float(t) / float(T2))
            + np.exp(-float(t) / float(T1))) / 6.0


# ---------------------------------------------------------------------------
# 自校锚
# ---------------------------------------------------------------------------
def selfcheck_ptm_structure(T1: float = 80.0, T2: float = 60.0,
                            t: float = 0.02, tol: float = 1e-10):
    """自校锚 ①：完整 PTM 与解析 PTM **逐元素**比对（含非对角元）。

    解析 PTM（T=0 振幅阻尼 + 纯退相位，H=0）：
        PTM[I,I]=1
        PTM[X,X]=PTM[Y,Y]=e^(−t/T2)
        PTM[Z,Z]=e^(−t/T1)
        PTM[Z,I]=−(1−e^(−t/T1))          ← 布居转移特征，非对角
        其余 = 0

    🔴 这条自校锚的价值：PTM[Z,I] ≈ −2.5e-4 **不是机器精度**，因此可标定 ——
    它证明积分器真的在解完整的 4×4 超算子，而不只是在套三个指数衰减率。
    """
    M = ptm(T1, T2, t, N_STEPS)
    E = np.zeros((4, 4), dtype=float)
    E[0, 0] = 1.0
    E[1, 1] = E[2, 2] = np.exp(-t / T2)
    E[3, 3] = np.exp(-t / T1)
    E[3, 0] = -(1.0 - np.exp(-t / T1))
    diff = float(np.max(np.abs(M - E)))
    detail = {
        "PTM[Z,Z]": (float(M[3, 3]), float(E[3, 3])),
        "PTM[X,X]": (float(M[1, 1]), float(E[1, 1])),
        "PTM[Z,I]（非对角·布居转移）": (float(M[3, 0]), float(E[3, 0])),
        "max|Δ|": diff,
    }
    return diff <= tol, diff, detail


def selfcheck_rk4_convergence(T1: float = 80.0, T2: float = 80.0,
                              t: float = T_SENSITIVE, n: int = 50):
    """自校锚 ②：敏感 regime 下残差**可标定**且按 O(h⁴) 收敛。

    判据（双向 —— 这是「网格双向标定」铁律的落地）：
      · 下界 SENSITIVE_LO：残差必须 > 1e-12。若候选回落到 golden（|Δ|≡0），
        这一步立刻红 ⇒ 生产档位的「残差 1.11e-16」不会被误当成验证凭据。
      · 上界 SENSITIVE_HI：残差必须 < 1e-6 ⇒ 积分器实现正确。
      · 收敛比：N 加倍残差至少降 8×（理论 16×，留 2× 平台余量）。

    实测（T1=T2=80, t=200）：N=50 → 8.755e-9；N=100 → 5.330e-10（16.4×）。
    """
    ref = closed_form(T1, T2, t)
    d1 = abs(average_gate_fidelity(T1, T2, t, n) - ref)
    d2 = abs(average_gate_fidelity(T1, T2, t, 2 * n) - ref)
    ratio = (d1 / d2) if d2 > 0 else float("inf")
    ok = (SENSITIVE_LO < d1 < SENSITIVE_HI) and (ratio >= CONVERGE_MIN_RATIO)
    detail = {
        f"|Δ|(N={n})": d1,
        f"|Δ|(N={2 * n})": d2,
        "收敛比": ratio,
        f"可接受区间": (SENSITIVE_LO, SENSITIVE_HI),
        "收敛比下限": CONVERGE_MIN_RATIO,
    }
    return bool(ok), d1, detail


def selfcheck_steady_state(T1: float = 80.0, T2: float = 60.0,
                           t: float = 5000.0, tol: float = 1e-6):
    """自校锚 ③：t → ∞ 稳态极限 F → 0.5。

    T=0 完全退相干通道把任意输入映射到 |0⟩⟨0| ⇒
        F_e = ⟨φ|(|0⟩⟨0| ⊗ I)|φ⟩/... = ¼，F_avg = (2·¼+1)/3 = ½
    闭式 t→∞：(3+0+0)/6 = ½ ✓ 两条路径独立给出同一个数。
    """
    f = average_gate_fidelity(T1, T2, t, n_steps=2000)
    diff = abs(f - 0.5)
    detail = {"F(t=5000µs)": f, "期望": 0.5, "|Δ|": diff}
    return diff <= tol, diff, detail


def selfcheck_unphysical_input():
    """自校锚 ④：T2 > 2·T1（非物理）必须抛 ValueError，不得静默 clamp。"""
    try:
        liouvillian(80.0, 200.0)
    except ValueError as e:
        return True, 0.0, {"抛出": f"ValueError: {e}"}
    return False, 0.0, {"抛出": "（无 —— 护栏缺失）"}


def run_selfchecks(verbose: bool = True) -> bool:
    """跑全部自校锚；返回是否全 PASS。"""
    checks = (
        ("① PTM 结构（含非对角元 PTM[Z,I]）", selfcheck_ptm_structure),
        ("② 敏感 regime RK4 O(h⁴) 收敛", selfcheck_rk4_convergence),
        ("③ t→∞ 稳态 F→0.5", selfcheck_steady_state),
        ("④ T2>2T1 非物理输入护栏", selfcheck_unphysical_input),
    )
    all_ok = True
    if verbose:
        print("=" * 74)
        print("lindblad_gate_fidelity 自校锚")
        print("=" * 74)
    for name, fn in checks:
        ok, val, detail = fn()
        all_ok &= ok
        if verbose:
            print(f"  {'PASS' if ok else 'FAIL'}  {name}")
            for k, v in detail.items():
                if isinstance(v, tuple):
                    print(f"          {k}: 算={v[0]:.10g}  期望={v[1]:.10g}")
                elif isinstance(v, float):
                    print(f"          {k}: {v:.6g}")
                else:
                    print(f"          {k}: {v}")
    if verbose:
        print("-" * 74)
        print(f"合计: {'全部 PASS' if all_ok else '存在 FAIL'}")
    return bool(all_ok)


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_selfchecks() else 1)
