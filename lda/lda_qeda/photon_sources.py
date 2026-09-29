"""D-114 · 单光子源物理（G_Q1 源部分）——SPDC 双模压缩 / 预示单光子 / HBT g²(0) / 弱相干态。

LDA-Q3b（M3 物理深度第二步 · 源侧）：给 LOQC 处理器补上**真实单光子源**这一环。

D-113（loqc_states）处理的是「理想 Fock 态输入 + 理想酉演化」；但真实光量子芯片里的单光子
不会凭空出现——它来自 **SPDC（自发参量下转换）双模压缩真空**，按概率成对产生，再用
「预告」(herald) 方式取出一路、以另一路的探测作为单光子「已产生」的宣告。预告源的
**纯度 / 多光子污染 / 二阶相干度**直接决定 LOQC 的输入态质量。本模块把这一层物理补上，
并给出与芯片无关的可复用闭式锚。

════════════════════════════════════════════════════════════════════════════
物理定律锚（闭式 · 公共品科学原理 · 可作 golden）
════════════════════════════════════════════════════════════════════════════
1. **HBT 二阶相干度**（Hanbury Brown–Twiss, 1956）：
       g²(0) = ⟨a†a†aa⟩ / ⟨a†a⟩² = ⟨n(n−1)⟩ / ⟨n⟩²。闭式：
     · Fock |n⟩        : g²(0) = (n−1)/n     （|1⟩ ⇒ 0 —— 单光子的「反聚束」判据）
     · 相干态 |α⟩      : g²(0) = 1           （泊松统计）
     · 热光(玻色-爱因) : g²(0) = 2           （玻色聚束）
2. **SPDC 双模压缩真空**（TMSS） |TMSV⟩ = √(1−λ²)·Σₙ λⁿ|n,n⟩（λ=tanh r，r 压缩参数）：
     · 联合光子数分布 P(n,n) = (1−λ²)·λ^{2n}
     · 单模约化态 = **热态**，平均光子 n̄ = λ²/(1−λ²) = sinh²r
     · 孪生光束光子数差 Δ(n₁−n₂) ≡ 0（理想相位匹配下完美关联）
3. **预告单光子**（heralded single photon）：
     · **PNR 预告**（可分辨光子数，取 n=1）⇒ 条件态 = **纯** |1⟩（纯度 1）；
     · **on/off 预告**（「有/无」探测器，含 n≥1 全部投影）⇒ 条件态 ρ ∝ Σ_{n≥1}λ^{2n}|n⟩⟨n|，闭式：
          纯度 Tr[ρ²] = (1−λ²)/(1+λ²)，  二阶相干度 g²(0) = 2λ² = 2·n̄/(1+n̄)
4. **弱相干态（WCS）** 作单光子源替代：P(n) = e^{−μ}μⁿ/n!；
     · 单光子概率 μe^{−μ}；多光子污染 P(≥2) = 1 − e^{−μ}(1+μ)

以上均为量子光学**闭式物理律**（教科书级、非拟合、非仿真值）⇒ 依 LDA「合法 golden 三类」
纪律（闭式物理律 / 分裂符号律 / A 级实测事实）可直接作 golden。

════════════════════════════════════════════════════════════════════════════
方法学独立（交叉验证 · 反自证桩）
════════════════════════════════════════════════════════════════════════════
TMSS 用两条**结构完全不同**的路径独立构造，须机器精度一致：
  (a) **闭式解析**：P(n,n) = (1−λ²)λ^{2n}，n̄ = λ²/(1−λ²)；
  (b) **数值算符构造**：压缩算符 S(ζ) = exp[r(a†b† − ab)] 作用于真空。生成元
      (a†b†−ab) 是**反 Hermitian**（M†=−M）⇒ exp(M) 走 eigh（i·M 为 Hermitian）。
      再做数值部分迹（约化）与投影（条件）得到热态/预告态。
解析（组合计数）vs 数值（矩阵指数 + 迹）结构迥异 ⇒ 一致即非复制粘贴。

════════════════════════════════════════════════════════════════════════════
红线纪律（与 LDA 一致）
════════════════════════════════════════════════════════════════════════════
· C 级自主：纯 numpy，零量子 SDK（无 qiskit/cirq/pennylane/strawberryfields/thewalrus）。
· LLM 不进判决路径：PASS/FAIL 由闭式死标量比对决定。
· 物理边界（诚实）：本层是**理想 SPDC**（无相位噪声/无传播损耗/无模式失配/无暗计数）；
  探测器物理（G_Q1 探测部分，见 detectors.py）与开放系统退相干（G_Q3，见 open_system.py）
  属同批增量的另两片。截断 Fock 空间（n_max）的残差**如实上报**，不掩盖。

运行自检：python -c "from lda.lda_qeda.photon_sources import run_selfchecks; run_selfchecks(verbose=True)"
"""
from __future__ import annotations

import math
from collections import OrderedDict

import numpy as np

__all__ = [
    "annihilation",
    "number_operator",
    "fock_dm",
    "coherent_dm",
    "thermal_dm",
    "second_order_g2",
    "g2_fock",
    "g2_coherent",
    "g2_thermal",
    "tmss_amplitudes",
    "tmss_joint_probs",
    "tmss_mean_photon",
    "tmss_numeric_state",
    "two_mode_operators",
    "squeezing_operator",
    "partial_trace_mode2",
    "twin_beam_number_difference",
    "heralded_pnr",
    "heralded_onoff",
    "heralded_purity_onoff",
    "heralded_g2_onoff",
    "wcs_probs",
    "wcs_single_photon_prob",
    "wcs_multiphoton_prob",
    "truncation_residual",
    "run_selfchecks",
    "RED_LINE_DISCLOSURE",
]

RED_LINE_DISCLOSURE = (
    "D-114 单光子源物理：纯 numpy 自研（C 级自主），零量子 SDK；闭式物理律（HBT g²、TMSS 分布、"
    "预告纯度）作 golden；两条结构不同路径（闭式解析 × 压缩算符矩阵指数）交叉验证。"
    "LLM 不进判决路径。诚实边界：理想 SPDC（无相位噪声/损耗/模式失配/暗计数），截断残差如实上报。"
)

# 截断 Fock 空间默认维度（n=0..TMSS_TRUNC）
TMSS_TRUNC = 30
# 热光截断须足够大：n̄=2 时二阶矩 ⟨n(n−1)⟩ 的截断残差 ~ (n̄/(1+n̄))^{n_max}·n² ，
# n_max=60 时 g²(0) 偏差达 1.5e-8（实测）；n_max=150 降到 ~1e-23（机器精度可忽略）。
_THERMAL_TRUNC = 150


# ════════════════════════════════════════════════════════════════════════════
# 1. 基础算符与态（截断 Fock 基）
# ════════════════════════════════════════════════════════════════════════════
def annihilation(n_max: int) -> np.ndarray:
    """单模湮灭算符 a（截断 n=0..n_max，dim=n_max+1）：a|n⟩=√n|n−1⟩。

    矩阵元 a[m,n] = √n·δ_{m,n−1} ⇒ 上对角（第 1 超对角）为 √n。
    """
    d = int(n_max) + 1
    a = np.zeros((d, d), dtype=complex)
    for n in range(1, d):
        a[n - 1, n] = math.sqrt(n)
    return a


def number_operator(n_max: int) -> np.ndarray:
    """光子数算符 n = a†a（对角，diag(0,1,…,n_max)）。"""
    a = annihilation(n_max)
    return a.conj().T @ a


def fock_dm(n: int, n_max: int) -> np.ndarray:
    """Fock 态 |n⟩⟨n| 的密度矩阵（截断）。"""
    d = int(n_max) + 1
    if not (0 <= n <= n_max):
        raise ValueError(f"Fock 态 |{n}⟩ 超出截断 n_max={n_max}")
    v = np.zeros(d, dtype=complex)
    v[n] = 1.0
    return np.outer(v, v.conj())


def coherent_dm(alpha: complex, n_max: int = _THERMAL_TRUNC) -> np.ndarray:
    """相干态 |α⟩⟨α| 密度矩阵（截断后重归一，消除截断残差的非物理迹亏）。"""
    d = int(n_max) + 1
    v = np.array([math.exp(-abs(alpha) ** 2 / 2.0) * alpha ** n / math.sqrt(math.factorial(n))
                  for n in range(d)], dtype=complex)
    nrm = float(np.linalg.norm(v))
    if nrm <= 0.0:
        raise ValueError("相干态截断向量范数为 0（|α|² 过大超出截断）")
    v = v / nrm
    return np.outer(v, v.conj())


def thermal_dm(nbar: float, n_max: int = _THERMAL_TRUNC) -> np.ndarray:
    """热光态密度矩阵（玻色-爱因斯坦分布 P(n)=n̄ⁿ/(1+n̄)^{n+1}，截断后重归一）。"""
    if nbar < 0.0:
        raise ValueError("平均光子数 n̄ 必须 ≥ 0")
    d = int(n_max) + 1
    p = np.array([nbar ** n / (1.0 + nbar) ** (n + 1) for n in range(d)], dtype=float)
    p = p / p.sum()
    return np.diag(p.astype(complex))


# ════════════════════════════════════════════════════════════════════════════
# 2. HBT 二阶相干度 g²(0)
# ════════════════════════════════════════════════════════════════════════════
def second_order_g2(rho: np.ndarray, n_max: int = _THERMAL_TRUNC) -> float:
    """数值 g²(0) = ⟨a†a†aa⟩ / ⟨a†a⟩²（由密度矩阵直接算，不套闭式）。"""
    if n_max + 1 != rho.shape[0]:
        n_max = rho.shape[0] - 1
    a = annihilation(n_max)
    n_op = a.conj().T @ a
    mean = float(np.real(np.trace(rho @ n_op)))
    if mean <= 0.0:
        return float("nan")
    # ⟨a†a†aa⟩ = ⟨n(n−1)⟩
    n2 = float(np.real(np.trace(rho @ a.conj().T @ a.conj().T @ a @ a)))
    return n2 / mean ** 2


def g2_fock(n: int) -> float:
    """Fock 态 |n⟩ 的 g²(0) 闭式 = (n−1)/n（|1⟩⇒0 反聚束判据）。"""
    if n <= 0:
        raise ValueError("真空态 |0⟩ 的 g²(0) 无定义（⟨n⟩=0）")
    return (n - 1) / n


def g2_coherent() -> float:
    """相干态 g²(0) 闭式 = 1（泊松统计）。"""
    return 1.0


def g2_thermal() -> float:
    """热光 g²(0) 闭式 = 2（玻色聚束）。"""
    return 2.0


# ════════════════════════════════════════════════════════════════════════════
# 3. SPDC 双模压缩真空（TMSS）
# ════════════════════════════════════════════════════════════════════════════
def tmss_amplitudes(lam: float, n_max: int = TMSS_TRUNC):
    """TMSS 振幅 ⟨n,n|TMSV⟩ = √(1−λ²)·λⁿ（截断 n=0..n_max）。"""
    if not (0.0 <= lam < 1.0):
        raise ValueError(f"压缩参数 λ=tanh r 必须满足 0 ≤ λ < 1（当前 {lam}）")
    return np.array([math.sqrt(1.0 - lam ** 2) * lam ** n for n in range(int(n_max) + 1)],
                    dtype=float)


def tmss_joint_probs(lam: float, n_max: int = TMSS_TRUNC) -> dict:
    """TMSS 联合光子数分布 { (n,n): P } 闭式 = (1−λ²)·λ^{2n}。"""
    return {(n, n): (1.0 - lam ** 2) * lam ** (2 * n) for n in range(int(n_max) + 1)}


def tmss_mean_photon(lam: float) -> float:
    """TMSS 单模平均光子数闭式 n̄ = λ²/(1−λ²) = sinh²r。"""
    if not (0.0 <= lam < 1.0):
        raise ValueError(f"λ 必须满足 0 ≤ λ < 1（当前 {lam}）")
    return lam ** 2 / (1.0 - lam ** 2)


def two_mode_operators(n_max: int = TMSS_TRUNC):
    """双模（模 1 × 模 2）湮灭算符 (a, b)，行主序索引 = n₁·d + n₂。"""
    d = int(n_max) + 1
    a1 = annihilation(n_max)
    eye = np.eye(d, dtype=complex)
    a = np.kron(a1, eye)      # 作用于模 1
    b = np.kron(eye, a1)      # 作用于模 2
    return a, b


def _expm_antihermitian(M: np.ndarray) -> np.ndarray:
    """反 Hermitian 矩阵 M（M†=−M）的矩阵指数 exp(M)，走 Hermitian 对角化：exp(M)=V·diag(e^{−i w})·V†，w=eig(i·M)。

    纯 numpy（无 scipy.linalg.expm）：i·M 为 Hermitian ⇒ eigh 保证实特征值、正交本征矢。
    """
    A = 1j * M
    w, V = np.linalg.eigh(A)
    return (V * np.exp(-1j * w)) @ V.conj().T


def squeezing_operator(r: float, n_max: int = TMSS_TRUNC) -> np.ndarray:
    """双模压缩算符 S = exp[r(a†b† − ab)]（作用于双模截断空间，维 d²）。

    生成元 M = r(a†b†−ab) 满足 M† = r(ab − a†b†) = −M ⇒ 反 Hermitian ⇒ S 酉。
    """
    a, b = two_mode_operators(n_max)
    M = r * (a.conj().T @ b.conj().T - a @ b)
    return _expm_antihermitian(M)


def tmss_numeric_state(r: float, n_max: int = TMSS_TRUNC) -> np.ndarray:
    """数值 TMSS 态矢量 |TMSV⟩ = S(r)|0,0⟩（走矩阵指数，独立于闭式）。"""
    S = squeezing_operator(r, n_max)
    d2 = S.shape[0]
    vac = np.zeros(d2, dtype=complex)
    vac[0] = 1.0
    return S @ vac


def partial_trace_mode2(rho2: np.ndarray, n_max: int = TMSS_TRUNC) -> np.ndarray:
    """对双模密度矩阵（索引 n₁·d+n₂）迹掉模 2，得模 1 约化密度矩阵（d×d）。"""
    d = int(n_max) + 1
    r = rho2.reshape(d, d, d, d)         # (n1, n2, n1', n2')
    return np.einsum("ikjk->ij", r)


def twin_beam_number_difference(lam: float, n_max: int = TMSS_TRUNC) -> float:
    """孪生光束光子数差方差 Var(n₁−n₂)：理想 TMSS 下 ≡ 0（完美关联）。"""
    probs = tmss_joint_probs(lam, n_max)
    mean_diff2 = sum(((n1 - n2) ** 2) * p for (n1, n2), p in probs.items())
    mean_diff = sum((n1 - n2) * p for (n1, n2), p in probs.items())
    return float(mean_diff2 - mean_diff ** 2)


# ════════════════════════════════════════════════════════════════════════════
# 4. 预告单光子（heralded single photon）
# ════════════════════════════════════════════════════════════════════════════
def heralded_pnr(rho2: np.ndarray, n_max: int = TMSS_TRUNC,
                 herald_n: int = 1) -> np.ndarray:
    """PNR 预告：对模 2 做「恰 n=herald_n 光子」投影，返回模 1 条件态（已归一）。

    正确部分迹：ρ_s[s,s'] = Tr₂[(I⊗|k⟩⟨k|)ρ][s,s'] = ρ[s,k,s',k]（投影后再对模 2 迹）。
    TMSS 下模 1 条件态 = 纯 |k⟩⟨k|。
    """
    d = int(n_max) + 1
    r = rho2.reshape(d, d, d, d)                     # (s, i, s', i')
    cond = r[:, herald_n, :, herald_n]               # 投影 n2=n2'=herald_n
    tr = float(np.real(np.trace(cond)))
    if tr <= 0.0:
        raise ValueError("预告投影概率为 0（herald_n 超出有效占据）")
    return cond / tr


def heralded_onoff(rho2: np.ndarray, n_max: int = TMSS_TRUNC) -> np.ndarray:
    """on/off 预告：模 2 投影到「有光子」(n≥1) 子空间，返回模 1 条件态（已归一）。

    🔴 正确的部分迹（曾写错，v 修正）：ρ_s[s,s'] = Tr₂[(I⊗Π₁)ρ][s,s'] = Σ_{i≥1} ρ[s,i,s',i]
       —— 只对**对角** i=i' 求和（i.e. 先取模 2 的对角、再对 n₂≥1 求和）。
       错写为 Σ_{i≥1,i'≥1} ρ[s,i,s',i']（同时求和 n₂ 与 n₂'）会保留模 2 的相干、得到
       **秩 1 纯态**（纯度 1，物理错误）。
    TMSS 下条件态 = 对角混合态 Σ_{n≥1}λ^{2n}|n⟩⟨n|（未归一），纯度 =(1−λ²)/(1+λ²) < 1。
    """
    d = int(n_max) + 1
    r = rho2.reshape(d, d, d, d)                     # (s, i, s', i')
    cond = np.zeros((d, d), dtype=complex)
    for i in range(1, d):                            # 只累加模 2 的**对角**元 i=i'≥1
        cond += r[:, i, :, i]
    tr = float(np.real(np.trace(cond)))
    if tr <= 0.0:
        raise ValueError("on/off 预告投影概率为 0")
    return cond / tr


def heralded_purity_onoff(lam: float) -> float:
    """on/off 预告条件态纯度闭式 = (1−λ²)/(1+λ²)（λ→0 趋 1，λ→1 趋 0）。"""
    if not (0.0 <= lam < 1.0):
        raise ValueError(f"λ 必须满足 0 ≤ λ < 1（当前 {lam}）")
    return (1.0 - lam ** 2) / (1.0 + lam ** 2)


def heralded_g2_onoff(lam: float) -> float:
    """on/off 预告条件态 g²(0) 闭式 = 2λ² = 2·n̄/(1+n̄)。"""
    if not (0.0 <= lam < 1.0):
        raise ValueError(f"λ 必须满足 0 ≤ λ < 1（当前 {lam}）")
    return 2.0 * lam ** 2


# ════════════════════════════════════════════════════════════════════════════
# 5. 弱相干态（WCS）
# ════════════════════════════════════════════════════════════════════════════
def wcs_probs(mu: float, n_max: int = 30) -> dict:
    """WCS 光子数分布 {n: P} 闭式 = e^{−μ}μⁿ/n!（泊松）。"""
    if mu < 0.0:
        raise ValueError("平均光子数 μ 必须 ≥ 0")
    return {n: math.exp(-mu) * mu ** n / math.factorial(n) for n in range(int(n_max) + 1)}


def wcs_single_photon_prob(mu: float) -> float:
    """WCS 单光子概率闭式 = μe^{−μ}（μ=1 时取极大 1/e）。"""
    return mu * math.exp(-mu)


def wcs_multiphoton_prob(mu: float) -> float:
    """WCS 多光子污染闭式 = 1 − e^{−μ}(1+μ)（P(≥2)）。"""
    return 1.0 - math.exp(-mu) * (1.0 + mu)


# ════════════════════════════════════════════════════════════════════════════
# 6. 截断残差（诚实上报，不掩盖）
# ════════════════════════════════════════════════════════════════════════════
def truncation_residual(lam: float, n_max: int = TMSS_TRUNC) -> float:
    """TMSS 在截断 n≤n_max 下损失的总概率 = λ^{2(n_max+1)}（未归一前）。"""
    return float(lam ** (2 * (int(n_max) + 1)))


# ════════════════════════════════════════════════════════════════════════════
# 7. 自检锚（闭式物理律 + 方法学独立 + 护栏）
# ════════════════════════════════════════════════════════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """模块内自检：g² 三态闭式 / TMSS 双路 / 约化热态 / 预告纯度与 g² / 孪生关联 / WCS / 护栏。"""
    res = OrderedDict()

    def rec(name, ok, detail=""):
        res[name] = bool(ok)
        if verbose:
            print(f"[{'PASS' if ok else 'FAIL'}] {name}{(' | ' + detail) if detail else ''}")

    # ① HBT g²(0) 三态：数值（密度矩阵）vs 闭式
    g2_f1 = second_order_g2(fock_dm(1, _THERMAL_TRUNC), _THERMAL_TRUNC)
    g2_f2 = second_order_g2(fock_dm(2, _THERMAL_TRUNC), _THERMAL_TRUNC)
    g2_coh = second_order_g2(coherent_dm(2.0, _THERMAL_TRUNC), _THERMAL_TRUNC)
    g2_th = second_order_g2(thermal_dm(2.0, _THERMAL_TRUNC), _THERMAL_TRUNC)
    d_g2 = max(abs(g2_f1 - g2_fock(1)), abs(g2_f2 - g2_fock(2)),
               abs(g2_coh - g2_coherent()), abs(g2_th - g2_thermal()))
    rec("HBT g²(0) 三态闭式：|1⟩=0 |2⟩=0.5 相干=1 热光=2",
        d_g2 < 1e-9,
        f"max|Δ|={d_g2:.3e}（|1⟩反聚束是单光子判据）")

    # ② TMSS 双路独立：闭式 P(n,n)=(1−λ²)λ^{2n} vs 数值压缩算符矩阵指数
    lam = 0.4
    r = math.atanh(lam)
    psi = tmss_numeric_state(r, TMSS_TRUNC)
    d = TMSS_TRUNC + 1
    cl = tmss_joint_probs(lam, TMSS_TRUNC)
    max_d_joint = 0.0
    for n in range(d):
        p_num = float(abs(psi[n * d + n]) ** 2)
        # 数值态未重归一：除以总概率（=1−λ^{2(n_max+1)}）对齐闭式
        p_num_norm = p_num / float(np.vdot(psi, psi).real)
        max_d_joint = max(max_d_joint, abs(p_num_norm - cl[(n, n)]))
    rec("TMSS 双路独立：闭式 (1−λ²)λ²ⁿ × 压缩算符矩阵指数（P(n,n) 全 n）",
        max_d_joint < 1e-10,
        f"max|Δ|={max_d_joint:.3e}·截断残差={truncation_residual(lam):.2e}")

    # ③ TMSS 单模约化 = 热态（n̄ = sinh²r 闭式）：数值部分迹 vs 闭式热分布
    rho2 = np.outer(psi, psi.conj())
    rho1 = partial_trace_mode2(rho2, TMSS_TRUNC)
    nbar_closed = tmss_mean_photon(lam)
    nbar_num = float(np.real(np.trace(rho1 @ number_operator(TMSS_TRUNC))))
    # 分布逐项比对（用闭式热分布，未截断归一）
    p_therm = np.array([(1 - lam ** 2) * lam ** (2 * n) for n in range(d)])
    max_d_red = float(np.max(np.abs(np.real(np.diag(rho1)) / float(np.trace(rho1).real) - p_therm)))
    rec("TMSS 单模约化 = 热态（数值部分迹 × 闭式 n̄=λ²/(1−λ²)）",
        abs(nbar_num / float(np.trace(rho1).real) - nbar_closed) < 1e-10 and max_d_red < 1e-10,
        f"n̄ 数值={nbar_num / float(np.trace(rho1).real):.12f} 闭式={nbar_closed:.12f}")

    # ④ 预告纯度：PNR⇒纯态(1)；on/off⇒(1−λ²)/(1+λ²) 闭式
    cond_pnr = heralded_pnr(rho2, n_max=TMSS_TRUNC, herald_n=1)
    pure_pnr = float(np.real(np.trace(cond_pnr @ cond_pnr)))
    cond_oo = heralded_onoff(rho2, TMSS_TRUNC)
    pure_oo = float(np.real(np.trace(cond_oo @ cond_oo)))
    rec("预告纯度：PNR⇒1（纯 |1⟩）· on/off⇒(1−λ²)/(1+λ²) 闭式",
        abs(pure_pnr - 1.0) < 1e-10 and abs(pure_oo - heralded_purity_onoff(lam)) < 1e-10,
        f"PNR 纯度={pure_pnr:.12f} on/off 纯度={pure_oo:.12f} 闭式={heralded_purity_onoff(lam):.12f}")

    # ⑤ 预告 g²(0)：on/off 条件态数值 vs 闭式 2λ²
    g2_oo_num = second_order_g2(cond_oo, TMSS_TRUNC)
    rec("预告 on/off 条件态 g²(0)=2λ² 闭式",
        abs(g2_oo_num - heralded_g2_onoff(lam)) < 1e-9,
        f"数值={g2_oo_num:.12f} 闭式={heralded_g2_onoff(lam):.12f}")

    # ⑥ 孪生光束光子数差 ≡ 0（完美关联）
    var_diff = twin_beam_number_difference(lam, TMSS_TRUNC)
    rec("孪生光束光子数差 Var(n₁−n₂)=0（理想 TMSS 完美关联）",
        abs(var_diff) < 1e-15, f"Var={var_diff:.3e}")

    # ⑦ WCS 多光子污染闭式
    mu = 0.5
    p1 = wcs_single_photon_prob(mu)
    pmp = wcs_multiphoton_prob(mu)
    probs = wcs_probs(mu, 40)
    s = sum(probs.values())
    p_ge2_num = 1.0 - probs[0] - probs[1]
    rec("WCS：单光子概率 μe^{−μ} 与多光子污染 1−e^{−μ}(1+μ) 闭式",
        abs(p_ge2_num - pmp) < 1e-12 and abs(s - 1.0) < 1e-12,
        f"P(1)={p1:.6f} P(≥2)={pmp:.6e} ΣP={s:.12f}")

    # ⑧ 护栏：λ≥1 抛错（tanh r 的物理域）+ 截断残差如实上报
    guard_ok = True
    try:
        tmss_amplitudes(1.0)
        guard_ok = False
    except ValueError:
        pass
    resid_ok = truncation_residual(0.4) < 1e-12
    rec("护栏：λ≥1 抛 ValueError（不静默）· 截断残差如实上报",
        guard_ok and resid_ok,
        f"λ=0.4 截断残差={truncation_residual(0.4):.2e} < 1e-12")

    ok = all(res.values())
    if verbose:
        n_fail = sum(1 for v in res.values() if not v)
        print(f"\nphoton_sources 自检：{len(res) - n_fail}/{len(res)} PASS")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_selfchecks(verbose=True) else 1)
