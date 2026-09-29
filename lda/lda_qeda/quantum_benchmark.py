"""D-119 · 量子基准（G_Q8）——玻色采样 / HOM 可见度 / 过程保真度 / 综合对标分。

════════════════════════════════════════════════════════════════════════════
为什么需要它（问题陈述）
────────────────────────────────────────────────────────────────────────────
M1–M3 把芯片做出来、把物理补齐（源/探测/开放系统/标定/签核），但**没有量化
「这颗芯片到底有多强」的基准**：能算多少模、保真度多少、离国际水平
（Xanadu Borealis 216 模 GBS / PsiQuantum 光子融合）还差多远？
这正是 M1 dog-fooding 登记的平台缺口 **G_Q8**（"量子基准（Clifford/RB/XEB 类）"，
现状「无量子基准挂入平台」）。

本模块给光量子芯片挂 **4 类基准**，全部用**闭式物理律作 golden**
（🔴 红线：绝不用仿真/自研计算值当 golden）：

  ① **玻色采样正确性**：输出分布必须满足
       · 概率守恒 Σ_out P(out) = 1（物理律，精确）
       · 闭式特例：DFT 矩阵 + 单光子 ⇒ 均匀 1/N；置换/恒等 ⇒ δ 分布；
         HOM（50/50 + |1,1⟩）⇒ 符合率 = 0。
     并做**采样统计校验**（χ² 拟合优度），证明分布确有概率意义（可采样）。
  ② **HOM 可见度基准**：V = 源光子不可区分度 μ（闭式）。
  ③ **过程保真度基准**：接 D-116 纠缠保真度闭式、D-118 酉保真度。
  ④ **综合对标分**：平台自定义的 QV-类合成量（**非国际公认指标**，仅内部追踪）：
         score = log2(Hilbert 维) × 综合保真度
         综合保真度 = mesh 酉保真度 × HOM 可见度 × (1−g²) × 探测效率

🔴 **诚实边界（必读）**：
  · 「综合对标分」是我们**自定义**的合成量，**不是** IBM Quantum Volume /
    XEB 等国际公认指标；不得用它对外宣称「达到国际水平」，只能作内部趋势追踪。
  · 本模块**不**与真实 Borealis/PsiQuantum 实测数据比对（那需 A 级可溯源实测，
    属外部依赖）；只给**本芯片自身**的可复现基准量。
════════════════════════════════════════════════════════════════════════════
红线自检标注：
- C 级自主：纯 numpy + 平台模块，零量子 SDK。
- LLM 不进判决路径：全部死标量；基准量由闭式/统计判据决定。
- 物理锚：概率守恒 · DFT 均匀 · HOM 零符合 · χ² 分布（均为闭式/统计律）。
════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import math
from collections import OrderedDict

import numpy as np

from lda_l2 import mzi_mesh_matmul as MMM
from lda_qeda import loqc_states as LS

__all__ = [
    "boson_sampling_benchmark",
    "sample_from_distribution",
    "chi_square_gof",
    "hom_visibility_benchmark",
    "process_fidelity_benchmark",
    "composite_quantum_score",
    "run_selfchecks",
    "RED_LINE_DISCLOSURE",
]


# ---------------------------------------------------------------------------
# 1) 玻色采样正确性基准
# ---------------------------------------------------------------------------
def boson_sampling_benchmark(U: np.ndarray, in_occ) -> dict:
    """玻色采样基准：输出分布的概率守恒 + 分布熵 + 峰值（死标量）。

    Σ_out P(out) = 1 是物理律（概率守恒），可作精确判据。
    返回 {"norm", "entropy_bits", "peak", "n_outcomes"}。
    """
    dist = LS.output_distribution(U, in_occ)
    probs = np.array(list(dist.values()), dtype=float)
    probs = np.clip(probs, 0.0, None)
    norm = float(np.sum(probs))
    safe = probs[probs > 0.0]
    entropy = float(-np.sum(safe * np.log2(safe))) if safe.size else 0.0
    return {
        "norm": norm,
        "entropy_bits": entropy,
        "peak": float(np.max(probs)) if probs.size else 0.0,
        "n_outcomes": int(probs.size),
    }


def sample_from_distribution(dist: dict, n_samples: int, seed: int = 20260929):
    """按分布做多项式采样，返回 (keys, counts)。"""
    if n_samples < 1:
        raise ValueError("n_samples ≥ 1")
    keys = list(dist.keys())
    p = np.array([dist[k] for k in keys], dtype=float)
    tot = float(np.sum(p))
    if tot <= 0.0:
        raise ValueError("分布总概率 ≤ 0，不可采样")
    p = p / tot
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(keys), size=n_samples, p=p)
    counts = np.bincount(idx, minlength=len(keys)).astype(float)
    return keys, counts


def chi_square_gof(counts, dist_probs, n_samples: int) -> dict:
    """χ² 拟合优度检验：counts 是否符合理论分布 dist_probs。

    返回 {"chi2", "dof", "p_value"(χ² 上尾近似), "reject_5pct"}。
    dof = k − 1（k 为输出态数）。p 值用 Wilson–Hilferty 近似（零 SciPy 依赖）。
    """
    c = np.asarray(counts, dtype=float)
    p = np.asarray(dist_probs, dtype=float)
    p = p / float(np.sum(p))
    exp = n_samples * p
    mask = exp > 0.0
    chi2 = float(np.sum((c[mask] - exp[mask]) ** 2 / exp[mask]))
    dof = int(np.sum(mask)) - 1
    if dof < 1:
        return {"chi2": chi2, "dof": dof, "p_value": 1.0, "reject_5pct": False}
    # Wilson–Hilferty：χ²_dof ≈ dof·(1 − 2/(9dof) + z·√(2/(9dof)))³
    z = ((chi2 / dof) ** (1.0 / 3.0) - (1.0 - 2.0 / (9.0 * dof))) / math.sqrt(2.0 / (9.0 * dof))
    # 标准正态上尾 P(Z>z) 用 erfc 闭式
    p_value = 0.5 * math.erfc(z / math.sqrt(2.0))
    return {"chi2": chi2, "dof": dof, "p_value": float(p_value),
            "reject_5pct": bool(p_value < 0.05)}


# ---------------------------------------------------------------------------
# 2) HOM 可见度基准
# ---------------------------------------------------------------------------
def hom_visibility_benchmark(indistinguishability: float = 1.0) -> float:
    """HOM 干涉可见度基准：理想不可区分光子 ⇒ V = μ（闭式，μ 为不可区分度）。"""
    if not (0.0 <= indistinguishability <= 1.0):
        raise ValueError("不可区分度 μ ∈ [0,1]")
    return float(indistinguishability)


# ---------------------------------------------------------------------------
# 3) 过程保真度基准（接 D-116 / D-118）
# ---------------------------------------------------------------------------
def process_fidelity_benchmark(entanglement_fidelity: float,
                               mesh_unitary_fidelity: float) -> dict:
    """过程保真度基准：汇聚开放系统纠缠保真度（D-116）与网格酉保真度（D-118）。"""
    for v in (entanglement_fidelity, mesh_unitary_fidelity):
        if not (0.0 <= v <= 1.0 + 1e-12):
            raise ValueError("保真度须 ∈ [0,1]")
    return {
        "entanglement_fidelity": float(entanglement_fidelity),
        "unitary_fidelity": float(mesh_unitary_fidelity),
        "product": float(entanglement_fidelity * mesh_unitary_fidelity),
    }


# ---------------------------------------------------------------------------
# 4) 综合对标分（平台自定义 · 非国际公认指标）
# ---------------------------------------------------------------------------
def composite_quantum_score(*, n_modes: int, n_photons: int, fidelity: float,
                            source_g2: float = 0.03, hom_visibility: float = 0.96,
                            detector_eta: float = 0.85) -> dict:
    """平台自定义综合量子基准分（QV-类，**非国际公认指标**，仅内部趋势追踪）。

        log2_dim       = n_photons · log2(n_modes)     （Hilbert 空间维数对数）
        combined_fid   = fidelity · hom_visibility · (1 − g²) · detector_eta
        score          = log2_dim · combined_fid

    说明：这是**我们自己的**合成量，不是 IBM Quantum Volume / XEB；
    不得据此对外宣称「达到国际水平」。
    """
    if n_modes < 2:
        raise ValueError("n_modes ≥ 2")
    if n_photons < 1:
        raise ValueError("n_photons ≥ 1")
    if not (0.0 <= fidelity <= 1.0 + 1e-12):
        raise ValueError("fidelity ∈ [0,1]")
    if not (0.0 <= source_g2):
        raise ValueError("source_g2 ≥ 0")
    log2_dim = float(n_photons) * math.log2(float(n_modes))
    combined = float(fidelity) * float(hom_visibility) * (1.0 - float(source_g2)) * float(detector_eta)
    return {
        "log2_hilbert_dim": log2_dim,
        "combined_fidelity": combined,
        "score": log2_dim * combined,
        "label": "platform-defined composite (NOT a recognized international metric)",
    }


# ---------------------------------------------------------------------------
# 5) 自检锚
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    """D-119 自检：概率守恒 / DFT 均匀 / δ 分布 / HOM 零符合 / 采样统计 /
    HOM 可见度 / 过程保真度 / 综合分单调 / 护栏。"""
    res = OrderedDict()
    N = 4

    # ① 概率守恒 ΣP=1（多 U × 多输入）
    max_norm = 0.0
    for U in (MMM.dft_matrix(N), np.eye(N, dtype=complex)):
        for occ in ((1, 0, 0, 0), (1, 1, 0, 0), (2, 0, 0, 0)):
            b = boson_sampling_benchmark(U, occ)
            max_norm = max(max_norm, abs(b["norm"] - 1.0))
    res[f"① 概率守恒 Σ_out P(out)=1（物理律，max|Δ|={max_norm:.2e}）"] = max_norm < 1e-12

    # ② DFT + 单光子 ⇒ 均匀 1/N（闭式 golden）
    d_dft = LS.output_distribution(MMM.dft_matrix(N), (1, 0, 0, 0))
    dev = max(abs(p - 1.0 / N) for p in d_dft.values())
    res[f"② DFT + |1⟩ ⇒ 输出均匀 1/N（闭式，max|Δ|={dev:.2e}）"] = dev < 1e-12

    # ③ 恒等/置换 ⇒ δ 分布（闭式 golden）
    ident = LS.output_distribution(np.eye(N, dtype=complex), (1, 0, 0, 0))
    perm = np.zeros((N, N), dtype=complex)
    for i in range(N):
        perm[i, (i + 1) % N] = 1.0        # U[i,j]=1 ⇒ 输入 j 的光子到输出 i
    d_perm = LS.output_distribution(perm, (0, 1, 0, 0))   # 输入 mode1 → 输出 mode0
    ok3 = (abs(ident[(1, 0, 0, 0)] - 1.0) < 1e-12
           and abs(d_perm[(1, 0, 0, 0)] - 1.0) < 1e-12)
    res["③ 恒等/置换 ⇒ δ 分布（闭式）"] = ok3

    # ④ HOM：50/50（T=cos²θ ⇒ θ=π/4）+ 不可区分 |1,1⟩ ⇒ 符合率 = 0（闭式 cos²2θ）
    bs = LS.bs_unitary(math.pi / 4.0)
    p_coin = LS.coincidence_probability(bs, (1, 1), (0, 1), (0, 1))
    p_cf = LS.hom_coincidence_closed_form(math.pi / 4.0)
    p_dist = LS.hom_coincidence_distinguishable(math.pi / 4.0)   # 可区分经典极限 = 1/2
    vis_ideal = LS.hom_visibility(math.pi / 4.0)                 # 理想可见度 = 1
    res[f"④ HOM 50/50：不可区分符合率={p_coin:.2e}(闭式 {p_cf:.2e})·可区分={p_dist:.4f}·V={vis_ideal:.4f}"] = (
        abs(p_coin) < 1e-12 and abs(p_dist - 0.5) < 1e-12 and abs(vis_ideal - 1.0) < 1e-12)

    # ⑤ 采样统计收敛：经验频率 → 理论
    dist = LS.output_distribution(MMM.dft_matrix(N), (1, 1, 0, 0))
    keys, counts = sample_from_distribution(dist, 200000, seed=5)
    th = np.array([dist[k] for k in keys])
    emp = counts / counts.sum()
    max_gap = float(np.max(np.abs(emp - th)))
    res[f"⑤ 采样统计收敛（2e5 样本 max|频率−理论|={max_gap:.4f}）"] = max_gap < 0.01

    # ⑥ χ² 拟合优度：采样样本不拒绝理论分布
    gof = chi_square_gof(counts, th, int(counts.sum()))
    res[f"⑥ χ² 拟合优度 p={gof['p_value']:.3f}（dof={gof['dof']}）不拒绝"] = not gof["reject_5pct"]

    # ⑦ HOM 可见度基准：V = μ（闭式）
    vs = [hom_visibility_benchmark(mu) for mu in (0.0, 0.5, 1.0)]
    res[f"⑦ HOM 可见度基准 V=μ（{vs}）"] = (vs[0] == 0.0 and vs[1] == 0.5 and vs[2] == 1.0)

    # ⑧ 综合分单调：保真度/效率↑ ⇒ 升；g²↑ ⇒ 降
    base = composite_quantum_score(n_modes=16, n_photons=4, fidelity=0.99)["score"]
    up_f = composite_quantum_score(n_modes=16, n_photons=4, fidelity=1.0)["score"]
    up_n = composite_quantum_score(n_modes=64, n_photons=4, fidelity=0.99)["score"]
    dn_g = composite_quantum_score(n_modes=16, n_photons=4, fidelity=0.99,
                                   source_g2=0.5)["score"]
    res[f"⑧ 综合分单调：F↑⇒↑({base:.2f}→{up_f:.2f}) N↑⇒↑({up_n:.2f}) g²↑⇒↓({dn_g:.2f})"] = (
        up_f > base and up_n > base and dn_g < base)

    # ⑨ 过程保真度 + 护栏
    pf = process_fidelity_benchmark(0.95, 0.999)
    guard = True
    for bad in ((lambda: composite_quantum_score(n_modes=1, n_photons=1, fidelity=0.9)),
                (lambda: hom_visibility_benchmark(1.5)),
                (lambda: process_fidelity_benchmark(1.2, 0.9))):
        try:
            bad()
            guard = False
        except ValueError:
            pass
    res[f"⑨ 过程保真度乘积={pf['product']:.6f} + 护栏（非法参数抛 ValueError）"] = (
        abs(pf["product"] - 0.95 * 0.999) < 1e-12 and guard)

    if verbose:
        for k, v in res.items():
            print(f"[{'PASS' if v else 'FAIL'}] {k}")
    return bool(all(res.values()))


RED_LINE_DISCLOSURE = {
    "role": "D-119 = 量子基准（G_Q8）：玻色采样正确性 / HOM 可见度 / 过程保真度 / 综合对标分。",
    "golden": "只用闭式物理律：概率守恒 ΣP=1 · DFT 单光子均匀 1/N · 恒等/置换 δ · "
              "HOM 零符合 · χ² 统计分布。**不**用仿真/自研计算值当 golden。",
    "sovereignty": "C 级自主（纯 numpy + 平台 lda_l2/lda_qeda），零量子 SDK；LLM 不进判决路径。",
    "honest_boundary": "综合对标分是**平台自定义**合成量（非 IBM QV/XEB 等国际公认指标），"
                       "仅作内部趋势追踪，**不得**据此对外宣称「达到国际水平」；"
                       "本模块不与真实 Borealis/PsiQuantum 实测数据比对（需 A 级可溯源实测，属外部依赖）。",
}


if __name__ == "__main__":
    ok = run_selfchecks(verbose=True)
    print(f"quantum_benchmark 自检：{'全 PASS' if ok else '有 FAIL'}")
