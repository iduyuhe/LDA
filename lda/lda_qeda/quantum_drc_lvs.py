"""D-118 · 量子器件 DRC/LVS（G_Q7）——量子设计规则检查 + 酉层版图-原理图一致性签核。

════════════════════════════════════════════════════════════════════════════
为什么需要它（问题陈述）
────────────────────────────────────────────────────────────────────────────
平台已有的 DRC/LVS（`lda_l2/drc.py` · `lda_l2/lvs.py` · `lda_l2/lvs_geom.py`）
只覆盖**经典光子基元**（波导/耦合器/环形腔的最小宽度、间距、几何回提）。
做真量子芯片，签核必须再覆盖两层：

  · **量子 DRC**：量子专用设计规则 —— 分束比可实现域、数字相移器相位分辨率、
    网格交叉/损耗预算、单光子源纯度 g²(0)、源不可区分性（HOM 可见度）、
    SNSPD 效率、以及 **L3 标定残差**（D-117 闭环的输出）。这些**都不在**经典
    DRC 里（M1 dog-fooding 登记的平台缺口 **G_Q7**）。
  · **量子 LVS**：经典 LVS 断言「版图连接 == 原理图连接」；量子 LVS 必须断言
    「**版图实际实现的酉矩阵 == 目标酉矩阵**」—— 这是量子签核的正确判据。

本模块**不做**：真实 GDS 的量子器件几何（属 M2/M3a 版图层）、真实 PDK deck（D5）。

════════════════════════════════════════════════════════════════════════════
方法（全部死标量 · LLM 不进判决路径）
────────────────────────────────────────────────────────────────────────────
① **量子 DRC**：9 条规则，逐条返回 violation（规则 id + 实测值 + 限值）。
   器件的「量子参数」（g²、HOM 可见度、η、标定残差）由 D-114/115/117 提供，
   本模块只做**限值比对**（接口解耦）。

② **量子 LVS 的两侧**：
   · **原理图侧** U_target —— 目标酉矩阵（设计意图，由 Reck 分解输入）。
   · **版图侧** U_actual —— 由网格 op 参数（θ, φ）经**非理想效应**重建：
        · 相位量化：φ → round(φ/Δφ)·Δφ（Δφ = 2π/2^bits，数字相移器）
        · 标定残差：φ → φ + N(0, σ_cal)（D-117 闭环残余）
        · 耦合器误差：θ → θ + N(0, σ_θ)（制造偏差）
     两侧比对得**酉保真度** F，F ≥ 阈值 ⇒ ACCEPT，否则 REJECT。

③ 🟢 **方法学独立（LVS 装配两路）**：版图侧装配用**嵌入矩阵乘法**（把每片 MZI 的
   2×2 逆序嵌入 N×N 后整体左乘 `E @ U`）；而平台 `lda_l2.mzi_mesh_matmul.
   assemble_triangular_mesh` 用**行向量线性组合**。两者数值路径结构不同 ⇒
   互为交叉验证（自检断言两路机器精度一致）。

④ 量子层交叉：当 U_actual ≠ U_target 时，单光子输出分布（`lda_qeda.loqc_states`
   的玻色振幅）也应改变 ⇒ 给出「酉层失配 ⇒ 量子层分布失配」的端到端证据。
════════════════════════════════════════════════════════════════════════════
红线自检标注：
- C 级自主：纯 numpy，零外部 EDA / 量子 SDK。
- LLM 不进判决路径：ACCEPT/REJECT 全由死标量（保真度 vs 阈值）决定。
- 物理锚：酉保真度（数学量）· 量化步长 Δφ=2π/2^bits（物理量）。
- 诚实边界：本模块的「版图侧」是**参数化重建**（op 参数 + 合成非理想效应），
  **非**从真实 GDS 提版图；属**代码路径级独立**（与 lvs_geom 同性质的诚实标注），
  **不构成**对「版图几何约定是否符合 foundry 事实」的验证（需真 PDK，属 D5）。
════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import math
from collections import OrderedDict

import numpy as np

from lda_l2 import mzi_mesh_matmul as MMM

__all__ = [
    "DEFAULT_DRC_LIMITS",
    "QDR_RULES",
    "phase_resolution_rad",
    "quantize_phase",
    "run_quantum_drc",
    "reconstruct_actual_unitary",
    "quantum_lvs_signoff",
    "run_selfchecks",
    "RED_LINE_DISCLOSURE",
]

# ---------------------------------------------------------------------------
# 量子 DRC 限值（设计规则 · 非实测 golden；可被调用方覆盖）
# ---------------------------------------------------------------------------
DEFAULT_DRC_LIMITS = {
    "coupling_split_min": 0.02,          # 定向耦合器分束比下限（可实现域）
    "coupling_split_max": 0.98,          # 上限
    "phase_resolution_rad": 2.0 * math.pi / (2 ** 12),   # 12-bit 相移器量化步长
    "max_crossings": 40,                 # 网格波导交叉数上限
    "max_loss_db": 25.0,                 # 级联插损预算上限（dB）
    "max_source_g2": 0.10,               # 单光子源 g²(0) 上限（纯度）
    "min_hom_visibility": 0.90,          # HOM 可见度下限（不可区分性）
    "min_detector_eta": 0.70,            # SNSPD 效率下限
    "max_calib_residual_rad": 1e-2,      # L3 标定残差上限（D-117 闭环输出）
}

QDR_RULES = (
    "QDR-PHASE-DOMAIN", "QDR-COUPLING-RANGE", "QDR-PHASE-RESOLUTION",
    "QDR-CROSSING-BUDGET", "QDR-LOSS-BUDGET", "QDR-SOURCE-PURITY",
    "QDR-INDISTINGUISHABILITY", "QDR-DETECTOR-EFFICIENCY", "QDR-CALIB-RESIDUAL",
)


# ---------------------------------------------------------------------------
# 1) 相位量化（数字相移器）
# ---------------------------------------------------------------------------
def phase_resolution_rad(bits: int) -> float:
    """数字相移器相位量化步长 Δφ = 2π/2^bits（rad）。"""
    if bits < 1:
        raise ValueError("相位比特数 bits ≥ 1")
    return 2.0 * math.pi / float(2 ** bits)


def quantize_phase(phi: float, bits: int) -> float:
    """把相位 φ 量化到最近的 Δφ 网格：round(φ/Δφ)·Δφ（Δφ=2π/2^bits）。"""
    dphi = phase_resolution_rad(bits)
    return round(phi / dphi) * dphi


# ---------------------------------------------------------------------------
# 2) 量子 DRC
# ---------------------------------------------------------------------------
def run_quantum_drc(design: dict, limits: dict | None = None) -> dict:
    """量子设计规则检查：逐条比对，返回 violations 与 ACCEPT/REJECT 判决。

    design 字段（缺省视为「未提供 ⇒ 该规则跳过」）：
      ops                 : 网格 op 列表 [(c, p, theta, phi), …]
      N                   : 模数
      n_crossings         : 网格波导交叉数
      source_g2           : 单光子源 g²(0)（D-114）
      hom_visibility      : 源不可区分性 HOM 可见度
      detector_eta        : SNSPD 探测效率（D-115）
      calib_residual_rad  : L3 标定残差（D-117 闭环输出）
      phase_bits          : 数字相移器比特数

    返回 {"verdict": "ACCEPT"/"REJECT", "violations": [...], "n_rules": k}。
    判决：任一 violation ⇒ REJECT。全死标量，LLM 不进判决路径。
    """
    lim = dict(DEFAULT_DRC_LIMITS)
    if limits:
        lim.update(limits)
    viol = []
    checked = 0

    # ① 相位/分束角物理域
    ops = design.get("ops")
    if ops is not None:
        checked += 1
        bad = [f"(c={c},p={p}) θ={th:.4f}" for (c, p, th, ph) in ops
               if not (0.0 <= th <= math.pi) or not math.isfinite(ph)]
        if bad:
            viol.append({"rule": "QDR-PHASE-DOMAIN", "detail": "θ∉[0,π] 或 φ 非有限: "
                                 + "; ".join(bad[:4])})

    # ② 定向耦合器分束比可实现域
    if ops is not None:
        checked += 1
        lo, hi = lim["coupling_split_min"], lim["coupling_split_max"]
        bad = []
        for (c, p, th, ph) in ops:
            split = math.sin(th / 2.0) ** 2
            if not (lo <= split <= hi):
                bad.append(f"(c={c},p={p}) split={split:.4f}")
        if bad:
            viol.append({"rule": "QDR-COUPLING-RANGE",
                         "detail": f"split∉[{lo},{hi}]: " + "; ".join(bad[:4])})

    # ③ 相位分辨率
    if design.get("phase_bits") is not None:
        checked += 1
        dphi = phase_resolution_rad(int(design["phase_bits"]))
        if dphi > lim["phase_resolution_rad"]:
            viol.append({"rule": "QDR-PHASE-RESOLUTION",
                         "detail": f"Δφ={dphi:.3e} > 限值 {lim['phase_resolution_rad']:.3e}"})

    # ④ 交叉数预算
    if design.get("n_crossings") is not None:
        checked += 1
        if int(design["n_crossings"]) > lim["max_crossings"]:
            viol.append({"rule": "QDR-CROSSING-BUDGET",
                         "detail": f"n_crossings={design['n_crossings']} > {lim['max_crossings']}"})

    # ⑤ 级联插损预算
    if ops is not None and design.get("n_crossings") is not None:
        checked += 1
        loss = MMM.mesh_cascade_loss_db(len(ops), n_crossings=int(design["n_crossings"]))
        if loss > lim["max_loss_db"]:
            viol.append({"rule": "QDR-LOSS-BUDGET",
                         "detail": f"级联插损 {loss:.3f} dB > {lim['max_loss_db']} dB"})

    # ⑥ 单光子源纯度 g²(0)
    if design.get("source_g2") is not None:
        checked += 1
        g2 = float(design["source_g2"])
        if g2 > lim["max_source_g2"]:
            viol.append({"rule": "QDR-SOURCE-PURITY",
                         "detail": f"g²(0)={g2:.4f} > {lim['max_source_g2']}"})

    # ⑦ 源不可区分性（HOM 可见度）
    if design.get("hom_visibility") is not None:
        checked += 1
        vis = float(design["hom_visibility"])
        if vis < lim["min_hom_visibility"]:
            viol.append({"rule": "QDR-INDISTINGUISHABILITY",
                         "detail": f"HOM 可见度 {vis:.4f} < {lim['min_hom_visibility']}"})

    # ⑧ SNSPD 效率
    if design.get("detector_eta") is not None:
        checked += 1
        eta = float(design["detector_eta"])
        if eta < lim["min_detector_eta"]:
            viol.append({"rule": "QDR-DETECTOR-EFFICIENCY",
                         "detail": f"η={eta:.4f} < {lim['min_detector_eta']}"})

    # ⑨ L3 标定残差
    if design.get("calib_residual_rad") is not None:
        checked += 1
        r = abs(float(design["calib_residual_rad"]))
        if r > lim["max_calib_residual_rad"]:
            viol.append({"rule": "QDR-CALIB-RESIDUAL",
                         "detail": f"标定残差 {r:.3e} rad > {lim['max_calib_residual_rad']:.3e}"})

    return {
        "verdict": "REJECT" if viol else "ACCEPT",
        "violations": viol,
        "n_rules": checked,
    }


# ---------------------------------------------------------------------------
# 3) 量子 LVS：版图侧酉重建 + 签核
# ---------------------------------------------------------------------------
def _assemble_by_embedding(ops, D, N: int) -> np.ndarray:
    """独立装配（**嵌入矩阵乘法**路径）：每片 MZI 的 2×2 逆序嵌入 N×N 后左乘。

    与 `lda_l2.mzi_mesh_matmul.assemble_triangular_mesh` 的「行向量线性组合」
    写法结构不同 ⇒ 两条数值路径互为交叉验证（见 run_selfchecks ①）。
    """
    U = np.array(D, dtype=complex, copy=True)
    for (c, p, theta, phi) in reversed(ops):
        G2 = MMM.mzi_unit_cell(theta, phi).conj().T
        E = np.eye(N, dtype=complex)
        E[p, p] = G2[0, 0]
        E[p, p + 1] = G2[0, 1]
        E[p + 1, p] = G2[1, 0]
        E[p + 1, p + 1] = G2[1, 1]
        U = E @ U
    return U


def reconstruct_actual_unitary(ops, D, N: int, *, phase_bits: int | None = None,
                               calib_sigma: float = 0.0, theta_sigma: float = 0.0,
                               seed: int = 20260929) -> np.ndarray:
    """版图侧酉重建：对 op 参数施加**非理想效应**后装配实际酉 U_actual。

      ① 相位量化（phase_bits 非 None）：φ → round(φ/Δφ)·Δφ
      ② 标定残差（calib_sigma>0）：φ → φ + N(0, σ_cal)（D-117 闭环残余）
      ③ 耦合器误差（theta_sigma>0）：θ → θ + N(0, σ_θ)
    """
    if calib_sigma < 0.0 or theta_sigma < 0.0:
        raise ValueError("sigma ≥ 0")
    rng = np.random.default_rng(seed)
    ops2 = []
    for (c, p, theta, phi) in ops:
        th, ph = float(theta), float(phi)
        if theta_sigma > 0.0:
            th += rng.normal(0.0, theta_sigma)
        if phase_bits is not None:
            ph = quantize_phase(ph, int(phase_bits))
        if calib_sigma > 0.0:
            ph += rng.normal(0.0, calib_sigma)
        ops2.append((c, p, th, ph))
    return _assemble_by_embedding(ops2, D, N)


def quantum_lvs_signoff(U_target: np.ndarray, ops, D, N: int, *,
                        phase_bits: int | None = 12, calib_sigma: float = 0.0,
                        theta_sigma: float = 0.0, seed: int = 20260929,
                        fid_threshold: float = 0.999) -> dict:
    """量子 LVS 签核：版图侧 U_actual vs 原理图侧 U_target，按酉保真度判 ACCEPT/REJECT。

    F = unitary_fidelity(U_actual, U_target)（1 − ‖ΔU‖_F/(N√2)）；
    F ≥ fid_threshold ⇒ ACCEPT。全死标量。
    """
    U_actual = reconstruct_actual_unitary(ops, D, N, phase_bits=phase_bits,
                                          calib_sigma=calib_sigma,
                                          theta_sigma=theta_sigma, seed=seed)
    fid = MMM.unitary_fidelity(U_actual, U_target)
    err_fro = float(np.linalg.norm(U_actual - np.asarray(U_target, dtype=complex)))
    return {
        "verdict": "ACCEPT" if fid >= fid_threshold else "REJECT",
        "fidelity": float(fid),
        "fro_err": err_fro,
        "fid_threshold": float(fid_threshold),
        "imperfections": {"phase_bits": phase_bits, "calib_sigma": calib_sigma,
                          "theta_sigma": theta_sigma},
    }


# ---------------------------------------------------------------------------
# 4) 自检锚
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    """D-118 自检：双路装配一致 / 零扰动签核 / 量化与噪声效应 / DRC 九规则 /
    阈值边界 / 量子层交叉 / 护栏 / 红线。"""
    res = OrderedDict()
    N = 4
    U_target = MMM.dft_matrix(N)
    ops, D = MMM.reck_triangular_mesh(U_target)

    # ① 方法学独立：嵌入矩阵装配 × lda_l2 行组合装配
    Ua = _assemble_by_embedding(ops, D, N)
    Ub = MMM.assemble_triangular_mesh(ops, D, N)
    d_asm = float(np.max(np.abs(Ua - Ub)))
    res[f"① LVS 双路装配一致（嵌入矩阵乘法 × lda_l2 行组合，max|Δ|={d_asm:.2e}）"] = d_asm < 1e-12

    # ② 零扰动签核 ⇒ fid=1，ACCEPT
    s0 = quantum_lvs_signoff(U_target, ops, D, N, phase_bits=None)
    res[f"② 零扰动 LVS：fid={s0['fidelity']:.12f} ⇒ {s0['verdict']}"] = (
        abs(s0["fidelity"] - 1.0) < 1e-12 and s0["verdict"] == "ACCEPT")

    # ③ 相位量化：12-bit 通过，低位显著退化
    s12 = quantum_lvs_signoff(U_target, ops, D, N, phase_bits=12)
    low3 = quantum_lvs_signoff(U_target, ops, D, N, phase_bits=3)
    res[f"③ 相位量化：12bit fid={s12['fidelity']:.6f}({s12['verdict']}) "
        f"3bit fid={low3['fidelity']:.6f}({low3['verdict']})"] = (
        s12["fidelity"] > 0.999 and low3["fidelity"] < s12["fidelity"] - 1e-3)

    # ④ 标定残差 σ_cal ↑ ⇒ 保真度单调降
    fids = [quantum_lvs_signoff(U_target, ops, D, N, phase_bits=None,
                                calib_sigma=s, seed=7)["fidelity"]
            for s in (0.001, 0.01, 0.05, 0.2)]
    mono = all(fids[i] > fids[i + 1] for i in range(len(fids) - 1))
    res[f"④ 标定残差↑⇒fid 单调降（{['%.4f' % f for f in fids]}）"] = mono

    # ⑤ 全合法设计 ⇒ DRC ACCEPT
    legal = {"ops": ops, "N": N, "n_crossings": 0, "source_g2": 0.03,
             "hom_visibility": 0.96, "detector_eta": 0.85,
             "calib_residual_rad": 1e-3, "phase_bits": 12}
    d_ok = run_quantum_drc(legal)
    res[f"⑤ DRC 全合法（{d_ok['n_rules']} 规则）⇒ {d_ok['verdict']}"] = d_ok["verdict"] == "ACCEPT"

    # ⑥ 逐条规则注入违规 ⇒ 对应规则被报出（9/9 覆盖）
    injections = [
        ("QDR-PHASE-DOMAIN", {"ops": [(0, 0, 3.5, 0.0)] + list(ops)}),
        ("QDR-COUPLING-RANGE", {"ops": [(0, 0, 0.05, 0.0)] + list(ops)}),
        ("QDR-PHASE-RESOLUTION", {"phase_bits": 2}),
        ("QDR-CROSSING-BUDGET", {"n_crossings": 1000}),
        ("QDR-LOSS-BUDGET", {"n_crossings": 0, "ops": ops * 40}),
        ("QDR-SOURCE-PURITY", {"source_g2": 0.5}),
        ("QDR-INDISTINGUISHABILITY", {"hom_visibility": 0.5}),
        ("QDR-DETECTOR-EFFICIENCY", {"detector_eta": 0.3}),
        ("QDR-CALIB-RESIDUAL", {"calib_residual_rad": 0.1}),
    ]
    hit = []
    for rule, patch in injections:
        d = dict(legal)
        d.update(patch)
        got = {v["rule"] for v in run_quantum_drc(d)["violations"]}
        hit.append(rule in got)
    res[f"⑥ DRC 九规则逐条可触发（{sum(hit)}/9）"] = all(hit)

    # ⑦ 保真度阈值边界行为
    lo = quantum_lvs_signoff(U_target, ops, D, N, phase_bits=None,
                             calib_sigma=0.3, seed=11, fid_threshold=0.5)["verdict"]
    hi = quantum_lvs_signoff(U_target, ops, D, N, phase_bits=None,
                             calib_sigma=0.3, seed=11, fid_threshold=1.0)["verdict"]
    res[f"⑦ 阈值边界：同扰动 低阈值⇒{lo} 高阈值⇒{hi}"] = (lo == "ACCEPT" and hi == "REJECT")

    # ⑧ 量子层反自证桩：单模输入（单光子/同模双光子，只取 U 第一列）对 φ 免疫
    #    （φ 只贡献整体相位 ⇒ 模不变）；跨模双光子 |1,1⟩ 的干涉才感知 φ。
    #    ⇒ 「单光子计数标不了相位，标定必须靠干涉」的物理根因（呼应 D-117）。
    from lda_qeda import loqc_states as _LS
    Ua0 = reconstruct_actual_unitary(ops, D, N, phase_bits=None)
    UaN = reconstruct_actual_unitary(ops, D, N, phase_bits=None, calib_sigma=0.5, seed=3)
    d1 = _LS.output_distribution(Ua0, (1, 0, 0, 0))
    d1n = _LS.output_distribution(UaN, (1, 0, 0, 0))
    gap1 = max(abs(d1[k] - d1n.get(k, 0.0)) for k in d1)
    d2 = _LS.output_distribution(Ua0, (1, 1, 0, 0))
    d2n = _LS.output_distribution(UaN, (1, 1, 0, 0))
    gap2 = max(abs(d2[k] - d2n.get(k, 0.0)) for k in d2)
    res[f"⑧ 量子层反自证桩：单光子分布对 φ 免疫(Δ={gap1:.1e})·跨模双光子敏感(Δ={gap2:.3e})"] = (
        gap1 < 1e-12 and gap2 > 1e-2)

    # ⑨ 护栏
    guard = True
    for bad in ((lambda: phase_resolution_rad(0)),
                (lambda: reconstruct_actual_unitary(ops, D, N, calib_sigma=-1.0))):
        try:
            bad()
            guard = False
        except ValueError:
            pass
    res["⑨ 护栏：bits<1 / σ<0 抛 ValueError"] = guard

    if verbose:
        for k, v in res.items():
            print(f"[{'PASS' if v else 'FAIL'}] {k}")
    return bool(all(res.values()))


RED_LINE_DISCLOSURE = {
    "role": "D-118 = 量子器件 DRC/LVS（G_Q7）：量子设计规则 + 酉层版图-原理图签核。",
    "drc": "9 条量子规则（相位域/分束比域/量化分辨率/交叉预算/损耗预算/源纯度/"
           "不可区分性/探测效率/标定残差），全死标量限值比对。",
    "lvs": "版图侧 U_actual（量化+标定残差+耦合器误差）vs 原理图侧 U_target，"
           "按酉保真度判 ACCEPT/REJECT。",
    "independence": "版图侧装配用嵌入矩阵乘法，平台用行组合——两路数值独立互验。",
    "sovereignty": "C 级自主（纯 numpy + 平台 lda_l2），零量子 SDK；LLM 不进判决路径。",
    "honest_boundary": "版图侧是**参数化重建**（非真实 GDS 提版图），属代码路径级独立，"
                       "不构成对几何约定是否符合 foundry 事实的验证（需真 PDK，属 D5）。",
}


if __name__ == "__main__":
    ok = run_selfchecks(verbose=True)
    print(f"quantum_drc_lvs 自检：{'全 PASS' if ok else '有 FAIL'}")
