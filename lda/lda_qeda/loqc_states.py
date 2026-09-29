"""D-113 · LOQC 量子态层（离散变量 Fock 基）——线性光学对量子态的作用 + 符合计数 + HOM。

LDA-Q3（M3 物理深度第一步）：把 M2 产出的「可编程酉 U」从**经典光学层**提升到
**量子态层**——线性光学元件的模式变换矩阵 U 作用到 Fock（光子数）态上，给出真正的
量子干涉（而非经典功率 |U|²）。

════════════════════════════════════════════════════════════════════════════
物理定律锚（闭式 · 公共品科学原理 · 可作 golden；详见 §锚）
════════════════════════════════════════════════════════════════════════════
1. **HOM 干涉**（Hong–Ou–Mandel, 1987）：两个**不可区分**单光子分别从分束器两输入
   进入，在 50:50 分束器上发生**破坏性干涉** ⇒ 同时到达两输出的符合计数 = 0
   （两光子总是「聚束」到同一输出）。
2. **一般分束器闭式**：透射率 T=cos²θ（功率）时，|1,1⟩→|1,1⟩ 振幅 = per(U) = cos2θ，
   符合概率 = **cos²(2θ) = (T−R)²**（R=sin²θ）。
3. **玻色采样振幅**（Aaronson–Arkhipov 2011）：N 光子 M 模输入 S、输出 T 的振幅
   = per(U_{T,S}) / √(Πᵢ nᵢ! Πⱼ mⱼ!)，permanent 为素数 #P-hard 组合计数。

这些是量子光学的**闭式物理律**（非拟合、非仿真值），依 LDA「合法 golden 三类」纪律
（闭式物理律 / 分裂符号律 / A 级实测事实）可直接作 golden。

════════════════════════════════════════════════════════════════════════════
方法学独立（交叉验证 · 反自证桩）
════════════════════════════════════════════════════════════════════════════
同一输出分布用**两种结构不同的算法**独立计算，须机器精度一致：
  (a) **永久式法**：组合计数（permanent，定义级排列求和）；
  (b) **产生算符多项式展开法**：把 a†ᵢ → Σⱼ U_{jᵢ} a'†ⱼ（Heisenberg 模式变换）代入
      Fock 态的产生算符多项式，利用玻色子对易关系 [a†,a†]=0 收集同类项。
两者算法结构完全不同（#P-hard 计数 vs 多项式符号展开）⇒ 一致即非复制粘贴。

════════════════════════════════════════════════════════════════════════════
红线纪律（与 LDA 一致）
════════════════════════════════════════════════════════════════════════════
· C 级自主：纯 numpy，零量子 SDK（无 qiskit/cirq/pennylane）。
· LLM 不进判决路径：PASS/FAIL 由闭式死标量比对决定。
· 物理边界（诚实）：本层是**理想酉**线性光学（无损耗/无相位噪声/无探测器暗计数）；
  单光子源/SNSPD 探测物理（G_Q1）、开放系统退相干（Lindblad/G_Q3 完全过程层）
  属后续增量。本层不产出实测保真度，只产出量子态演化的精确代数结果。

运行自检：python -c "from lda.lda_qeda.loqc_states import run_selfchecks; run_selfchecks(verbose=True)"
"""
from __future__ import annotations

import itertools
import math

import numpy as np

__all__ = [
    "permanent",
    "linear_optics_amplitude",
    "output_distribution",
    "prob_of",
    "apply_linear_optics_polynomial",
    "bs_unitary",
    "mzi_embed",
    "hom_coincidence",
    "hom_coincidence_closed_form",
    "hom_coincidence_distinguishable",
    "hom_visibility",
    "coincidence_probability",
    "run_selfchecks",
    "RED_LINE_DISCLOSURE",
]

RED_LINE_DISCLOSURE = (
    "D-113 LOQC 量子态层：纯 numpy 自研（C 级自主），零量子 SDK；闭式物理律 (HOM/玻色采样) "
    "作 golden；两种结构不同算法（permanent × 产生算符多项式展开）交叉验证。LLM 不进判决路径。"
    "诚实边界：理想酉、无损耗/无噪声/无探测物理（G_Q1/G_Q3 属后续增量）。"
)

# 光子总数上限护栏（permanent 定义级排列求和 O(n!) 的可行域；超此须换 Ryser/近似）
_MAX_PHOTONS_EXACT = 10


# ════════════════════════════════════════════════════════════════════════════
# 1. permanent（组合计数 · 振幅的法定义）
# ════════════════════════════════════════════════════════════════════════════
def permanent(A: np.ndarray) -> complex:
    """方阵的 permanent（定义级：per(A)=Σ_σ Πᵢ a_{i,σ(i)}）。

    与 determinant 只差符号 ⇒ **不能复用行列式**（玻色子全对称）。此实现对 n≤10
    用精确排列求和（复系数无符号相消问题）；更大 n 须换 Ryser/近似（本层不涉）。
    """
    A = np.asarray(A, dtype=complex)
    if A.ndim != 2 or A.shape[0] != A.shape[1]:
        raise ValueError("permanent 仅定义在方阵上（玻色采样子矩阵必为方阵）")
    n = A.shape[0]
    if n == 0:
        return 1.0 + 0.0j
    if n > _MAX_PHOTONS_EXACT:
        raise ValueError(
            f"permanent 精确排列求和仅支持 n≤{_MAX_PHOTONS_EXACT}（当前 n={n}）；"
            "更大规模须换 Ryser 或近似算法"
        )
    total = 0.0 + 0.0j
    for perm in itertools.permutations(range(n)):
        prod = 1.0 + 0.0j
        for i, j in enumerate(perm):
            prod *= A[i, j]
        total += prod
    return total


# ════════════════════════════════════════════════════════════════════════════
# 2. 线性光学振幅 / 输出分布（永久式法）
# ════════════════════════════════════════════════════════════════════════════
def _factorial_product(occ) -> float:
    """Πᵢ occᵢ!（玻色子归一化分母的因子；不预先开方，避免双重 sqrt）。"""
    d = 1.0
    for c in occ:
        d *= math.factorial(int(c))
    return d


def linear_optics_amplitude(U: np.ndarray, in_occ, out_occ) -> complex:
    """⟨out_occ| Û |in_occ⟩ = per(U_{T,S}) / √(Π nᵢ! · Π mⱼ!)。

    约定：U 为**模式变换矩阵**，输出湮灭算符 a'ⱼ = Σᵢ U_{jᵢ} aᵢ（即 a' = U·a）。
    子矩阵 U_{T,S}：行 = 输出模按 out_occ 重数（mⱼ 次），列 = 输入模按 in_occ 重数
    （nᵢ 次）。光子数不守恒（Σin≠Σout）返回 0。
    """
    U = np.asarray(U, dtype=complex)
    in_occ = tuple(int(x) for x in in_occ)
    out_occ = tuple(int(x) for x in out_occ)
    if U.shape[0] != len(out_occ) or U.shape[1] != len(in_occ):
        raise ValueError(
            f"U 形状 {U.shape} 与组态不符（需 {len(out_occ)}×{len(in_occ)}）"
        )
    if sum(in_occ) != sum(out_occ):
        return 0.0 + 0.0j
    rows = [j for j, m in enumerate(out_occ) for _ in range(m)]
    cols = [i for i, n in enumerate(in_occ) for _ in range(n)]
    if not rows:                       # 真空 → 真空
        return 1.0 + 0.0j
    sub = U[np.ix_(rows, cols)]
    per = permanent(sub)
    return per / math.sqrt(_factorial_product(in_occ) * _factorial_product(out_occ))


def _compositions(n: int, M: int):
    """所有长度 M、和为 n 的非负整数组态。"""
    if M == 1:
        yield (n,)
        return
    for first in range(n + 1):
        for rest in _compositions(n - first, M - 1):
            yield (first,) + rest


def output_distribution(U: np.ndarray, in_occ):
    """输出光子数分布 {out_occ: P}（永久式法）。酉 U 下须归一（Σ=1，可作自检）。"""
    U = np.asarray(U, dtype=complex)
    in_occ = tuple(int(x) for x in in_occ)
    N = sum(in_occ)
    M = U.shape[0]
    dist = {}
    for out_occ in _compositions(N, M):
        amp = linear_optics_amplitude(U, in_occ, out_occ)
        dist[out_occ] = float(abs(amp) ** 2)
    return dist


def prob_of(U: np.ndarray, in_occ, out_occ) -> float:
    """指定输出组态的概率 |振幅|²。"""
    return float(abs(linear_optics_amplitude(U, in_occ, out_occ)) ** 2)


# ════════════════════════════════════════════════════════════════════════════
# 3. 方法学独立算法：产生算符多项式展开
# ════════════════════════════════════════════════════════════════════════════
def _multinomial_powers(coeffs, n: int):
    """(Σₖ coeffs[k]·xₖ)^n 展开为 {指数元组: 系数}（多重组合系数）。"""
    M = len(coeffs)
    res = {}
    for combo in itertools.combinations_with_replacement(range(M), n):
        counts = [0] * M
        for idx in combo:
            counts[idx] += 1
        mcoef = math.factorial(n)
        for c in counts:
            mcoef //= math.factorial(c)
        e = tuple(counts)
        val = complex(mcoef)
        for k, cnt in enumerate(counts):
            if cnt:
                val *= coeffs[k] ** cnt
        res[e] = res.get(e, 0.0 + 0.0j) + val
    return res


def apply_linear_optics_polynomial(U: np.ndarray, in_occ):
    """独立算法：把 |in_occ⟩ 的产生算符多项式代换 a†ᵢ → Σⱼ U_{jᵢ} a'†ⱼ 后收集同类项。

    返回 {out_occ: 振幅}。与 permanent 法**结构不同**（符号多项式展开 vs 组合计数）；
    玻色子 [a†ⱼ,a†ₖ]=0 ⇒ 同类项直接相加，无需反对称符号。
    """
    U = np.asarray(U, dtype=complex)
    in_occ = tuple(int(x) for x in in_occ)
    M = U.shape[0]
    poly = {tuple([0] * M): 1.0 + 0.0j}          # 未归一化的 a'† 单项式 → 系数
    for i, n_i in enumerate(in_occ):
        if n_i == 0:
            continue
        factor = _multinomial_powers([U[j, i] for j in range(M)], n_i)
        merged = {}
        for e1, c1 in poly.items():
            for e2, c2 in factor.items():
                e = tuple(a + b for a, b in zip(e1, e2))
                merged[e] = merged.get(e, 0.0 + 0.0j) + c1 * c2
        poly = merged
    # 单项式 Σ c·Π(a'†)^m 归一化：|Π(a'†)^m⟩ = √(Π m!)·|occ⟩ ⇒ 振幅 = c·√(Πm!)/√(Πn!)
    in_norm = math.sqrt(_factorial_product(in_occ))
    out = {}
    for e, c in poly.items():
        out[e] = c * math.sqrt(_factorial_product(e)) / in_norm
    return out


# ════════════════════════════════════════════════════════════════════════════
# 4. 分束器 / MZI / HOM
# ════════════════════════════════════════════════════════════════════════════
def bs_unitary(theta: float, phi: float = 0.0) -> np.ndarray:
    """2×2 分束器酉（功率透射 T=cos²θ、反射 R=sin²θ；内部相位 φ）。

    U = [[cosθ, i·sinθ·e^{iφ}], [i·sinθ·e^{−iφ}, cosθ]]。
    该相位约定（离对角虚数）正是 HOM 破坏性干涉成立的条件（φ 不影响 HOM）。
    """
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[c, 1j * s * np.exp(1j * phi)],
                     [1j * s * np.exp(-1j * phi), c]], dtype=complex)


def mzi_embed(N: int, i: int, j: int, theta: float, phi: float = 0.0) -> np.ndarray:
    """把 2×2 分束器嵌入 N 模（模 i,j 上作用，余恒等）。"""
    U = np.eye(N, dtype=complex)
    U[np.ix_([i, j], [i, j])] = bs_unitary(theta, phi)
    return U


def hom_coincidence(theta: float, phi: float = 0.0) -> float:
    """HOM 符合概率（数值 · 永久式法）：|1,1⟩→|1,1⟩ 概率。"""
    U = bs_unitary(theta, phi)
    return prob_of(U, (1, 1), (1, 1))


def hom_coincidence_closed_form(theta: float) -> float:
    """HOM 符合概率**闭式**：cos²(2θ) = (T−R)²（物理定律锚）。"""
    return math.cos(2.0 * theta) ** 2


def hom_coincidence_distinguishable(theta: float) -> float:
    """**可区分**光子的符合概率（无干涉 · 经典极限）：R²+T² = sin⁴θ+cos⁴θ。

    θ=π/4 时为 1/2，是 HOM dip 的上平台（P_max）；不可区分时降至 0（P_min）。
    """
    R = math.sin(theta) ** 2
    T = math.cos(theta) ** 2
    return R * R + T * T


def hom_visibility(theta: float) -> float:
    """HOM 干涉可见度 V=(P_dist−P_indist)/(P_dist+P_indist)。50:50 理论值 = 1。"""
    p_d = hom_coincidence_distinguishable(theta)
    p_i = hom_coincidence(theta)
    return (p_d - p_i) / (p_d + p_i)


def coincidence_probability(U: np.ndarray, in_occ, in_modes, out_modes) -> float:
    """指定输出模集合 out_modes 各恰有 1 光子（其余为 0）的概率。"""
    out_occ = tuple(1 if j in set(out_modes) else 0 for j in range(U.shape[0]))
    return prob_of(U, in_occ, out_occ)


# ════════════════════════════════════════════════════════════════════════════
# 5. 自检锚（闭式物理律 + 方法学独立 + 护栏）
# ════════════════════════════════════════════════════════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """模块内自检：闭式 HOM / 跨 θ 对齐 / 归一 / 双算法一致 / 经典极限 / 护栏。

    返回全 PASS 的 bool（供门禁调用）。仅用死标量比对，无拟合。
    """
    from collections import OrderedDict

    res = OrderedDict()

    def rec(name, ok, detail=""):
        res[name] = bool(ok)
        if verbose:
            print(f"[{'PASS' if ok else 'FAIL'}] {name} {('| ' + detail) if detail else ''}")

    # ① HOM 50:50 破坏性干涉：符合概率 = 0（闭式 golden）
    p_ind = hom_coincidence(math.pi / 4.0)
    p_ref = hom_coincidence_closed_form(math.pi / 4.0)
    rec("HOM 50:50 符合概率=0（破坏性干涉，闭式 cos²2θ=0）",
        p_ind < 1e-12 and abs(p_ref) < 1e-15,
        f"数值={p_ind:.3e} 闭式={p_ref:.3e}")

    # ② 跨 θ 网格：数值（永久式）× 闭式 × 独立（多项式）三方一致
    max_d_cf = 0.0
    max_d_poly = 0.0
    for th in np.linspace(0.0, math.pi / 2.0, 37):
        U = bs_unitary(float(th))
        a_perm = linear_optics_amplitude(U, (1, 1), (1, 1))
        a_poly = apply_linear_optics_polynomial(U, (1, 1))[(1, 1)]
        cf = math.sqrt(max(hom_coincidence_closed_form(float(th)), 0.0))
        max_d_cf = max(max_d_cf, abs(abs(a_perm) - cf))
        max_d_poly = max(max_d_poly, abs(a_perm - a_poly))
    rec("HOM 跨 θ 网格：永久式振幅 × 闭式 cos2θ 一致",
        max_d_cf < 1e-12, f"max|Δ|={max_d_cf:.3e}")
    rec("方法学独立：永久式 × 产生算符多项式展开一致（HOM 族）",
        max_d_poly < 1e-12, f"max|Δ|={max_d_poly:.3e}")

    # ③ 酉下输出分布归一（多模 / 多光子）
    rng = np.random.default_rng(20260929)
    max_norm_err = 0.0
    for (M, nphot) in ((2, 2), (3, 2), (4, 3), (4, 4), (6, 2)):
        X = (rng.standard_normal((M, M)) + 1j * rng.standard_normal((M, M))) / math.sqrt(2.0)
        Q, R = np.linalg.qr(X)
        U = Q @ np.diag(np.diag(R) / np.abs(np.diag(R)))
        # 均匀铺光子到前 nphot 模（nphot≤M）
        in_occ = tuple(1 if k < nphot else 0 for k in range(M))
        dist = output_distribution(U, in_occ)
        max_norm_err = max(max_norm_err, abs(sum(dist.values()) - 1.0))
    rec("输出分布归一 Σ P = 1（随机酉 × 多模多光子）",
        max_norm_err < 1e-12, f"max|ΣP−1|={max_norm_err:.3e}")

    # ④ 方法学独立（通用）：随机酉 × 随机 Fock 输入，逐组态振幅比对
    max_d_gen = 0.0
    for (M, nphot, seed) in ((3, 2, 1), (4, 3, 2), (5, 3, 3)):
        r = np.random.default_rng(seed)
        X = (r.standard_normal((M, M)) + 1j * r.standard_normal((M, M))) / math.sqrt(2.0)
        Q, R = np.linalg.qr(X)
        U = Q @ np.diag(np.diag(R) / np.abs(np.diag(R)))
        occ_list = [0] * M
        for k in range(nphot):
            occ_list[k % M] += 1
        in_occ = tuple(occ_list)
        poly = apply_linear_optics_polynomial(U, in_occ)
        for out_occ in _compositions(nphot, M):
            a_perm = linear_optics_amplitude(U, in_occ, out_occ)
            a_poly = poly.get(out_occ, 0.0 + 0.0j)
            max_d_gen = max(max_d_gen, abs(a_perm - a_poly))
    rec("方法学独立（通用）：永久式 × 多项式展开逐组态一致",
        max_d_gen < 1e-10, f"max|Δ|={max_d_gen:.3e}")

    # ⑤ 经典极限：单光子分布 = |U_{j,i}|²（量子结果退化到经典强度）
    r = np.random.default_rng(4)
    X = (r.standard_normal((5, 5)) + 1j * r.standard_normal((5, 5))) / math.sqrt(2.0)
    Q, R = np.linalg.qr(X)
    U = Q @ np.diag(np.diag(R) / np.abs(np.diag(R)))
    in_occ = (1, 0, 0, 0, 0)
    max_cl_err = 0.0
    for j in range(5):
        out_occ = tuple(1 if k == j else 0 for k in range(5))
        max_cl_err = max(max_cl_err, abs(prob_of(U, in_occ, out_occ) - abs(U[j, 0]) ** 2))
    rec("单光子经典极限：P(j) = |U_{ji}|²",
        max_cl_err < 1e-12, f"max|Δ|={max_cl_err:.3e}")

    # ⑥ 反自证桩：可区分 ≠ 不可区分（干涉真实存在，非恒 0）
    p_dist = hom_coincidence_distinguishable(math.pi / 4.0)
    rec("反自证桩：可区分光子符合概率=1/2 ≠ 不可区分=0（干涉真实）",
        abs(p_dist - 0.5) < 1e-12 and p_ind < 1e-12,
        f"可区分={p_dist:.6f} 不可区分={p_ind:.3e}")

    # ⑦ 护栏：非方阵 permanent / 光子数不守恒 / 非酉不静默
    guard_ok = True
    try:
        permanent(np.ones((2, 3), dtype=complex))
        guard_ok = False
    except ValueError:
        pass
    amp_mismatch = linear_optics_amplitude(np.eye(2, dtype=complex), (2, 0), (1, 1))
    guard_ok = guard_ok and abs(amp_mismatch) < 1e-15
    rec("护栏：非方阵 permanent 抛错 + 光子数不守恒振幅恒 0",
        guard_ok, "非方阵 ValueError；Σin≠Σout ⇒ amp=0")

    ok = all(res.values())
    if verbose:
        n_fail = sum(1 for v in res.values() if not v)
        print(f"\nloqc_states 自检：{len(res) - n_fail}/{len(res)} PASS")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_selfchecks(verbose=True) else 1)
