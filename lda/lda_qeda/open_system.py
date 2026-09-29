"""D-116 · 多模 Lindblad 开放系统（G_Q3）——光子损耗通道 / 过程保真度 / 三法独立。

LDA-Q3b（M3 物理深度第三步 · 退相干侧）：把「理想酉演化」升级为**开放系统**。

D-113 与 M2/M3 处理的都是**理想酉**（无损耗）；真实光量子芯片里，每个模式都在丢光子。
本模块把**多模玻色开放系统**补上：M 个模（各截断到 d 能级）、逐模光子损耗 Liouvillian、
以及**过程级**（不只态级）的通道等价性验证。这是「真可编程 LOQC 处理器」与「真实硬件」
之间的最后一道物理桥。

════════════════════════════════════════════════════════════════════════════
物理定律锚（闭式 · 公共品科学原理 · 可作 golden）
════════════════════════════════════════════════════════════════════════════
1. **光子损耗通道**（振幅阻尼，T=0 热库）主方程：dρ/dt = Σⱼ κⱼ D[aⱼ]ρ，
   D[A]ρ = AρA† − ½{A†A, ρ}。等效透射率 **η = e^{−κt}**。
2. **Kraus 表示**（k = **丢失**的光子数）：
      A_k = Σ_{n≥k} √(C(n,k))·(1−η)^{k/2}·η^{(n−k)/2}·|n−k⟩⟨n|
   ⇒ 布居闭式 **P(m 幸存 | n 输入) = C(n,m)·η^m·(1−η)^{n−m}**（二项分布）。
   🔴 陷阱：写成 |k⟩⟨n|（把「丢失数」当「幸存数」）会得到**去相位通道**，
      η=1 时退化为完全去相位（纠缠保真度错成 1/d），不是恒等通道。
3. **相干态**：|α⟩ 经损耗 ⇒ |√η·α⟩ ⇒ 保真度闭式 **F = |⟨α|√η α⟩|² = exp(−|α|²(1−√η)²)**。
4. **纠缠保真度**（entanglement fidelity，通道的过程级标量）：
      F_e(Φ) = ⟨Φ₊|(I⊗Φ)(|Φ₊⟩⟨Φ₊|)|Φ₊⟩ = (1/d²)·Σ_k |Tr[A_k]|²
   ⇒ 损耗通道闭式 F_e = (1/d²)·(Σ_{n=0}^{d−1} η^{n/2})²。

════════════════════════════════════════════════════════════════════════════
方法学独立（交叉验证 · 反自证桩）
════════════════════════════════════════════════════════════════════════════
同一通道用三条结构不同的路径独立构造，须机器精度一致：
  (a) **全空间数值**：在 d^M 维张量积空间构造 Liouvillian，RK4 积分主方程；
  (b) **逐模分解**：无模间耦合 ⇒ 总传播子 = ⊗ⱼ Λⱼ（每模 d² 维小问题）；
  (c) **Kraus 解析**：Σ_k A_k ρ A_k†（组合计数构造的解析通道）。
(a) vs (b) 是「一个大问题 vs 多个小问题的张量积」，(a)/(b) vs (c) 是「ODE 积分 vs 解析 Kraus」。
过程矩阵（vec(ρ_out)=M·vec(ρ_in) 的 M）逐元素比对 ⇒ **过程级**（非单态级）等价性。

════════════════════════════════════════════════════════════════════════════
红线纪律（与 LDA 一致）
════════════════════════════════════════════════════════════════════════════
· C 级自主：纯 numpy，零量子 SDK（无 qiskit/cirq/pennylane/qutip）。
· LLM 不进判决路径（闭式死标量比对）。
· 物理边界（诚实）：T=0 热库（未含 n_th 热激发）；纯损耗（未含相位噪声/增益/模间串扰）；
  截断 d 与模数 M 的有限性 ⇒ 残差如实上报。

运行自检：python -c "from lda.lda_qeda.open_system import run_selfchecks; run_selfchecks(verbose=True)"
"""
from __future__ import annotations

import math
from collections import OrderedDict

import numpy as np

# ── 统一命名空间导入（防「同一文件双实例」陷阱，同 detectors.py）────────────
import os as _os
import sys as _sys

_LDA_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))   # = …/lda
if _LDA_DIR not in _sys.path:
    _sys.path.insert(0, _LDA_DIR)

try:
    from lda_qeda import photon_sources as PS      # 统一形式（lda/ 已在 path）
except ImportError:                                # 极端兜底（直跑且包根不可达）
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    import photon_sources as PS                    # noqa: E402

__all__ = [
    "N_STEPS",
    "mode_operators",
    "dissipator",
    "loss_liouvillian",
    "rk4_linear",
    "full_ode_evolve",
    "single_mode_propagator",
    "factorized_evolve",
    "kraus_multimode_evolve",
    "loss_kraus",
    "kraus_channel",
    "process_matrix_kraus",
    "process_matrix_ode_single",
    "entanglement_fidelity_kraus",
    "entanglement_fidelity_closed_form",
    "loss_population_closed_form",
    "coherent_loss_fidelity_closed_form",
    "transmissivity_from_kappa",
    "run_selfchecks",
    "RED_LINE_DISCLOSURE",
]

RED_LINE_DISCLOSURE = (
    "D-116 多模 Lindblad 开放系统：纯 numpy 自研（C 级自主），零量子 SDK；闭式物理律（二项布居、"
    "相干态保真、纠缠保真度）作 golden；三条结构不同路径（全空间 ODE × 逐模分解张量积 × Kraus 解析）"
    "在**过程矩阵**层交叉验证。LLM 不进判决路径。诚实边界：T=0 纯损耗（无热激发/相位噪声/串扰）。"
)

N_STEPS = 300         # RK4 步数：过程矩阵/模态演化共用。40 步时 d=4、κt~0.8 残差达 5.3e-8
#                       （实测）⇒ 提到 300 步（h⁴ ⇒ 残差降 ~3e-4×）到 ~1.7e-11。


# ════════════════════════════════════════════════════════════════════════════
# 1. 多模张量积空间与 Liouvillian
# ════════════════════════════════════════════════════════════════════════════
def mode_operators(M: int, d: int):
    """M 个模、各截断到 d 能级的湮灭算符列表 [a₀,…,a_{M−1}]（维 d^M）。

    索引约定：|n₀…n_{M−1}⟩ 的行主序索引 = n₀·d^{M−1}+…+n_{M−1}；
    aⱼ = I_{d^j} ⊗ a ⊗ I_{d^{M−1−j}}（a 作用在第 j 个（从 0 起）模）。
    """
    a1 = PS.annihilation(d - 1)                        # d×d
    ops = []
    for j in range(M):
        left = np.eye(d ** j, dtype=complex)
        right = np.eye(d ** (M - 1 - j), dtype=complex)
        ops.append(np.kron(np.kron(left, a1), right))
    return ops


def dissipator(A: np.ndarray) -> np.ndarray:
    """Lindblad 耗散超算子 D[A]（row-major vec：vec(AρB)=(A⊗Bᵀ)vec(ρ)）。

    D[A] = A⊗conj(A) − ½[(A†A)⊗I + I⊗(A†A)ᵀ]。
    """
    d = A.shape[0]
    I = np.eye(d, dtype=complex)
    AdagA = A.conj().T @ A
    return (np.kron(A, A.conj())
            - 0.5 * (np.kron(AdagA, I) + np.kron(I, AdagA.T)))


def loss_liouvillian(kappas, M: int, d: int) -> np.ndarray:
    """多模光子损耗 Liouvillian L = Σⱼ κⱼ·D[aⱼ]（(d^M)² × (d^M)²）。

    kappas: 长度 M 的损耗率列表（单位 1/时间）。κⱼ=0 ⇒ 该模无损耗。
    """
    if len(kappas) != M:
        raise ValueError(f"kappas 长度 {len(kappas)} 与模数 M={M} 不符")
    for k in kappas:
        if k < 0.0:
            raise ValueError("损耗率 κ 必须 ≥ 0（κ<0 是非物理增益）")
    ops = mode_operators(M, d)
    L = np.zeros((d ** (2 * M), d ** (2 * M)), dtype=complex)
    for j, kap in enumerate(kappas):
        if kap != 0.0:
            L += kap * dissipator(ops[j])
    return L


# ════════════════════════════════════════════════════════════════════════════
# 2. 数值积分（RK4）
# ════════════════════════════════════════════════════════════════════════════
def rk4_linear(L: np.ndarray, v0: np.ndarray, t: float, n_steps: int) -> np.ndarray:
    """RK4 积分 dv/dt = L·v（v 可为向量或矩阵——矩阵按列分别积分）。"""
    if t < 0.0:
        raise ValueError("演化时间 t 必须 ≥ 0")
    v = np.asarray(v0, dtype=complex).copy()
    h = float(t) / int(n_steps)
    for _ in range(int(n_steps)):
        k1 = L @ v
        k2 = L @ (v + 0.5 * h * k1)
        k3 = L @ (v + 0.5 * h * k2)
        k4 = L @ (v + h * k3)
        v = v + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return v


def full_ode_evolve(kappas, M: int, d: int, rho0: np.ndarray,
                    t: float, n_steps: int = N_STEPS) -> np.ndarray:
    """路径(a)：全空间 Liouvillian + RK4 演化任意初态 ρ0（d^M × d^M）。"""
    L = loss_liouvillian(kappas, M, d)
    D = d ** M
    if rho0.shape != (D, D):
        raise ValueError(f"ρ0 形状 {rho0.shape} 与空间维 {D} 不符")
    v = rk4_linear(L, rho0.reshape(-1), t, n_steps)
    return v.reshape(D, D)


# ════════════════════════════════════════════════════════════════════════════
# 3. 逐模分解（张量积传播子）
# ════════════════════════════════════════════════════════════════════════════
def single_mode_propagator(kappa: float, t: float, d: int,
                           n_steps: int = N_STEPS) -> np.ndarray:
    """单模损耗通道的过程矩阵 Mⱼ（d²×d²）：由 RK4 积分 d² 个矩阵基元得到。

    M 满足 vec(ρ_out) = M·vec(ρ_in)（row-major）。
    """
    L = kappa * dissipator(PS.annihilation(d - 1))
    eye = np.eye(d * d, dtype=complex)
    return rk4_linear(L, eye, t, n_steps)               # 对单位阵积分 ⇒ 传播子


def _apply_single_mode_channel(rt: np.ndarray, Mj: np.ndarray,
                               j: int, M: int, d: int) -> np.ndarray:
    """把单模过程矩阵 Mj（d²×d²）作用在张量 rt 的第 j 个模上（行/列索引同时）。

    rt 形状 (d,)*(2M)：轴 0..M−1 = 行指标 (n₀…n_{M−1})，轴 M..2M−1 = 列指标。
    🔴 row-major vec 下逐模通道**不是** np.kron(M₀,M₁,…)：vec 索引序是
       (r₀,r₁,…,r_{M−1},c₀,…,c_{M−1})，模式 j 的两条索引是轴 j 与轴 M+j，须用张量收缩
       作用，不能简单 kron（正是平台 Lindblad 模块 docstring 警告的同款陷阱）。
    """
    Mj4 = Mj.reshape(d, d, d, d)                       # (r_out, c_out, r_in, c_in)
    rt2 = np.moveaxis(rt, [j, M + j], [-2, -1])        # 被作用两轴移到末尾
    out = np.einsum("...ab,ABab->...AB", rt2, Mj4)     # 收缩 (r_in,c_in)，输出 (r_out,c_out)
    return np.moveaxis(out, [-2, -1], [j, M + j])


def factorized_evolve(kappas, M: int, d: int, rho: np.ndarray, t: float,
                      n_steps: int = N_STEPS) -> np.ndarray:
    """路径(b)：无模间耦合 ⇒ 逐模施加单模通道（**张量收缩**，非 kron）。

    对**任意**初态 ρ（含模间纠缠）按模式 j=0..M−1 依次作用单模过程矩阵 Mⱼ。
    """
    if len(kappas) != M:
        raise ValueError(f"kappas 长度 {len(kappas)} 与模数 M={M} 不符")
    rt = rho.reshape((d,) * (2 * M))
    for j, kap in enumerate(kappas):
        Mj = single_mode_propagator(kap, t, d, n_steps)
        rt = _apply_single_mode_channel(rt, Mj, j, M, d)
    return rt.reshape(d ** M, d ** M)


def kraus_multimode_evolve(kappas, M: int, d: int, rho: np.ndarray,
                           t: float) -> np.ndarray:
    """路径(c)：全空间**嵌入 Kraus** 逐模施加（Σ_k A_k^emb ρ A_k^emb†，A 嵌到第 j 模）。

    与路径(b)算法结构不同（大空间 Kraus 求和 vs 小空间张量收缩）⇒ 交叉验证。
    """
    if len(kappas) != M:
        raise ValueError(f"kappas 长度 {len(kappas)} 与模数 M={M} 不符")
    D = d ** M
    out = np.asarray(rho, dtype=complex).copy()
    for j, kap in enumerate(kappas):
        eta = transmissivity_from_kappa(kap, t)
        ks = loss_kraus(eta, d - 1)
        acc = np.zeros((D, D), dtype=complex)
        for A in ks:
            Aj = np.kron(np.kron(np.eye(d ** j, dtype=complex), A),
                         np.eye(d ** (M - 1 - j), dtype=complex))
            acc += Aj @ out @ Aj.conj().T
        out = acc
    return out


# ════════════════════════════════════════════════════════════════════════════
# 4. Kraus 解析（路径 c）
# ════════════════════════════════════════════════════════════════════════════
def loss_kraus(eta: float, n_max: int):
    """光子损耗通道的 Kraus 算符列表 [A₀,…,A_{n_max}]（k = **丢失**光子数）。

    A_k = Σ_{n≥k} √(C(n,k))·(1−η)^{k/2}·η^{(n−k)/2}·|n−k⟩⟨n|。
    Σ_k A_k†A_k = I（保迹；由二项式定理保证）。
    """
    if not (0.0 <= eta <= 1.0):
        raise ValueError(f"透射率 η 必须在 [0,1]（当前 {eta}）")
    d = int(n_max) + 1
    ks = []
    for k in range(d):
        A = np.zeros((d, d), dtype=complex)
        for n in range(k, d):
            A[n - k, n] = (math.sqrt(math.comb(n, k))
                           * (1.0 - eta) ** (k / 2.0) * eta ** ((n - k) / 2.0))
        ks.append(A)
    return ks


def kraus_channel(rho: np.ndarray, kraus) -> np.ndarray:
    """Σ_k A_k ρ A_k†（在给定 Hilbert 空间上作用）。"""
    out = np.zeros_like(rho, dtype=complex)
    for A in kraus:
        out += A @ rho @ A.conj().T
    return out


def process_matrix_kraus(kraus, d: int) -> np.ndarray:
    """Kraus 通道的过程矩阵 M = Σ_k A_k ⊗ conj(A_k)（d²×d²）。"""
    M = np.zeros((d * d, d * d), dtype=complex)
    for A in kraus:
        M += np.kron(A, A.conj())
    return M


def process_matrix_ode_single(kappa: float, t: float, d: int,
                              n_steps: int = N_STEPS) -> np.ndarray:
    """路径(a)（单模）：ODE 过程矩阵 = single_mode_propagator（同一物理）。"""
    return single_mode_propagator(kappa, t, d, n_steps)


# ════════════════════════════════════════════════════════════════════════════
# 5. 闭式锚
# ════════════════════════════════════════════════════════════════════════════
def transmissivity_from_kappa(kappa: float, t: float) -> float:
    """η = e^{−κt}。"""
    return math.exp(-kappa * t)


def loss_population_closed_form(n: int, m: int, eta: float) -> float:
    """P(m 幸存 | n 输入) = C(n,m)·η^m·(1−η)^{n−m}（m>n ⇒ 0）。"""
    if m < 0 or m > n:
        return 0.0
    return math.comb(n, m) * eta ** m * (1.0 - eta) ** (n - m)


def coherent_loss_fidelity_closed_form(alpha: complex, eta: float) -> float:
    """相干态经损耗后的保真度闭式 F = exp(−|α|²(1−√η)²)（|α⟩→|√η α⟩）。"""
    return math.exp(-abs(alpha) ** 2 * (1.0 - math.sqrt(eta)) ** 2)


def entanglement_fidelity_kraus(kraus, d: int) -> float:
    """纠缠保真度 F_e = ⟨Φ₊|(I⊗Φ)(|Φ₊⟩⟨Φ₊|)|Φ₊⟩（直接由最大纠缠态数值算）。"""
    phi = np.zeros(d * d, dtype=complex)
    for i in range(d):
        phi[i * d + i] = 1.0 / math.sqrt(d)
    rho_out = np.zeros((d * d, d * d), dtype=complex)
    for A in kraus:
        IAk = np.kron(np.eye(d, dtype=complex), A)
        rho_out += IAk @ np.outer(phi, phi.conj()) @ IAk.conj().T
    return float(np.real(np.vdot(phi, rho_out @ phi)))


def entanglement_fidelity_closed_form(eta: float, d: int) -> float:
    """损耗通道纠缠保真度闭式 (1/d²)·(Σ_{n=0}^{d−1} η^{n/2})²。"""
    s = sum(eta ** (n / 2.0) for n in range(d))
    return (1.0 / d ** 2) * s ** 2


# ════════════════════════════════════════════════════════════════════════════
# 6. 自检锚
# ════════════════════════════════════════════════════════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """自检：单模过程矩阵 ODE×Kraus · 二项布居 · 相干态保真 · 纠缠保真 · 多模三法 · 护栏。"""
    res = OrderedDict()

    def rec(name, ok, detail=""):
        res[name] = bool(ok)
        if verbose:
            print(f"[{'PASS' if ok else 'FAIL'}] {name}{(' | ' + detail) if detail else ''}")

    d = 4
    kappa, t = 0.7, 0.55
    eta = transmissivity_from_kappa(kappa, t)

    # ① 单模过程矩阵：ODE(RK4) × Kraus 逐元素一致（跨 η 网格）
    max_d_M = 0.0
    for (kk, tt) in ((0.7, 0.55), (1.3, 0.2), (0.05, 3.0), (2.0, 0.4)):
        e = transmissivity_from_kappa(kk, tt)
        M_ode = process_matrix_ode_single(kk, tt, d)
        M_kr = process_matrix_kraus(loss_kraus(e, d - 1), d)
        max_d_M = max(max_d_M, float(np.max(np.abs(M_ode - M_kr))))
    rec("单模过程矩阵：ODE(RK4) × Kraus 逐元素一致（跨 η 网格）",
        max_d_M < 1e-10, f"max|Δ|={max_d_M:.3e}（d={d}）")

    # ② 布居二项闭式：Kraus 通道对角 × C(n,m)η^m(1−η)^{n−m}
    max_d_pop = 0.0
    for n in range(d):
        rho = np.zeros((d, d), dtype=complex)
        rho[n, n] = 1.0
        out = kraus_channel(rho, loss_kraus(eta, d - 1))
        for m in range(d):
            max_d_pop = max(max_d_pop,
                            abs(float(np.real(out[m, m])) - loss_population_closed_form(n, m, eta)))
    rec("光子损耗布居闭式 P(m|n)=C(n,m)ηᵐ(1−η)^{n−m}（Kraus 对角）",
        max_d_pop < 1e-12, f"max|Δ|={max_d_pop:.3e}（η={eta:.6f}）")

    # ③ 相干态损耗：|α⟩→|√η α⟩ ⇒ 态保真 ⟨α|Φ(|α⟩⟨α|)|α⟩ × 闭式 exp(−|α|²(1−√η)²)；⟨n⟩→η|α|²
    alpha = 1.3
    rho_coh = PS.coherent_dm(alpha, 40)
    kraus_full = loss_kraus(eta, 40)
    out_coh = kraus_channel(rho_coh, kraus_full)
    v_alpha = _coh_vec(alpha, 40)                      # 原输入 |α⟩（归一）
    fid_num = float(abs(np.vdot(v_alpha, out_coh @ v_alpha)))   # ⟨α|ρ_out|α⟩
    fid_cl = coherent_loss_fidelity_closed_form(alpha, eta)
    nbar_out = float(np.real(np.trace(out_coh @ PS.number_operator(40))))
    rec("相干态损耗：态保真 ⟨α|Φ(|α⟩⟨α|)|α⟩ × 闭式 exp(−|α|²(1−√η)²) 且 ⟨n⟩→η|α|²",
        abs(fid_num - fid_cl) < 1e-10 and abs(nbar_out - eta * alpha ** 2) < 1e-9,
        f"F 数值={fid_num:.12f} 闭式={fid_cl:.12f} ⟨n⟩={nbar_out:.9f} η|α|²={eta * alpha ** 2:.9f}")

    # ④ 纠缠保真度：数值（最大纠缠态）× 闭式 (1/d²)(Ση^{n/2})²
    fe_num = entanglement_fidelity_kraus(loss_kraus(eta, d - 1), d)
    fe_cl = entanglement_fidelity_closed_form(eta, d)
    # η=1 时 F_e 必须 = 1（恒等通道；防「去相位通道」误实现）
    fe_one = entanglement_fidelity_kraus(loss_kraus(1.0, d - 1), d)
    rec("纠缠保真度：数值 × 闭式 (1/d²)(Ση^{n/2})² · η=1⇒F_e=1（非去相位）",
        abs(fe_num - fe_cl) < 1e-12 and abs(fe_one - 1.0) < 1e-12,
        f"F_e 数值={fe_num:.12f} 闭式={fe_cl:.12f} η=1⇒{fe_one:.12f}")

    # ⑤ 多模三法一致（任意含纠缠初态）：全空间 ODE × 逐模张量收缩 × 全空间嵌入 Kraus
    max_tri = 0.0
    for (M, dd, kaps, tt) in ((2, 4, (0.7, 0.3), 0.55),
                              (3, 2, (0.5, 0.9, 0.2), 0.6),
                              (2, 3, (1.1, 0.0), 1.0)):
        # 随机（一般、含模间纠缠）初态 × 三法演化
        rr = np.random.default_rng(20260929 + M * 10 + dd)
        X = rr.standard_normal((dd ** M, dd ** M)) + 1j * rr.standard_normal((dd ** M, dd ** M))
        rho0 = X @ X.conj().T
        rho0 = rho0 / np.trace(rho0)
        ra = full_ode_evolve(kaps, M, dd, rho0, tt)                 # (a) 全空间 ODE
        rb = factorized_evolve(kaps, M, dd, rho0, tt)               # (b) 逐模张量收缩
        rc = kraus_multimode_evolve(kaps, M, dd, rho0, tt)          # (c) 全空间嵌入 Kraus
        max_tri = max(max_tri, float(np.max(np.abs(ra - rb))), float(np.max(np.abs(ra - rc))))
    rec("多模三法一致（任意含纠缠初态）：全空间 ODE × 逐模张量收缩 × 全空间 Kraus（M=2/3）",
        max_tri < 1e-9, f"max|Δ|={max_tri:.3e}")

    # ⑥ 物理性：通道保迹 + Choi 半正定（CP）
    kraus = loss_kraus(eta, d - 1)
    tp_err = float(np.max(np.abs(sum(A.conj().T @ A for A in kraus) - np.eye(d))))
    # Choi 矩阵 J = Σ_ij |i⟩⟨j| ⊗ Φ(|i⟩⟨j|)，PSD ⟺ CP
    J = np.zeros((d * d, d * d), dtype=complex)
    for i in range(d):
        for j in range(d):
            Eij = np.zeros((d, d), dtype=complex)
            Eij[i, j] = 1.0
            J += np.kron(np.outer(_e(i, d), _e(j, d).conj()), kraus_channel(Eij, kraus))
    ev = np.linalg.eigvalsh(J)
    rec("物理性：通道保迹 ΣA†A=I · Choi 半正定（CP）",
        tp_err < 1e-15 and ev.min() > -1e-12,
        f"max|ΣA†A−I|={tp_err:.2e} Choi 最小本征={ev.min():.3e}")

    # ⑦ 护栏：κ<0 / t<0 / η∉[0,1] 抛错；模数/长度错配抛错
    guard_ok = True
    for bad in ((lambda: loss_liouvillian([-0.1], 1, 2)),
                (lambda: rk4_linear(np.eye(2, dtype=complex), np.eye(2, dtype=complex), -1.0, 4)),
                (lambda: loss_kraus(1.5, 3)),
                (lambda: loss_liouvillian([0.1, 0.2], 1, 2))):
        try:
            bad()
            guard_ok = False
        except ValueError:
            pass
    rec("护栏：κ<0 / t<0 / η∉[0,1] / 模数与长度错配 均抛 ValueError",
        guard_ok, "非物理输入不静默")

    ok = all(res.values())
    if verbose:
        n_fail = sum(1 for v in res.values() if not v)
        print(f"\nopen_system 自检：{len(res) - n_fail}/{len(res)} PASS")
    return ok


def _e(i: int, d: int) -> np.ndarray:
    """第 i 个标准基矢（d 维）。"""
    v = np.zeros(d, dtype=complex)
    v[i] = 1.0
    return v


def _coh_vec(alpha: complex, n_max: int) -> np.ndarray:
    """相干态矢量（截断重归一）。"""
    d = n_max + 1
    v = np.array([math.exp(-abs(alpha) ** 2 / 2.0) * alpha ** n / math.sqrt(math.factorial(n))
                  for n in range(d)], dtype=complex)
    return v / float(np.linalg.norm(v))


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_selfchecks(verbose=True) else 1)
