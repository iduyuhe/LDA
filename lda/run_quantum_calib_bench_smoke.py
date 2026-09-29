"""量子标定/DRC-LVS/基准门禁 smoke（D-117/118/119 · 凭据守护）。

═══ 为什么要有这个 smoke ═══
D-117（L3 标定闭环 G_Q5）/ D-118（量子器件 DRC/LVS G_Q7）/ D-119（量子基准 G_Q8）
补上 LDA-Q3c 的最后三块物理深度能力。三块都**必须**有常驻护栏：

  ① **闭式物理律锚**：三点相移公式、MZI 干涉条纹、DFT 单光子均匀、HOM 零符合、
     概率守恒、CRB 标度、保真度二次律。若有人把相位约定/归一化/量化约定改错，
     这些闭式立刻失真 ⇒ 必须钉成断言。
  ② **方法学独立**：
     · 标定：三点法 × 最小二乘正弦拟合（两估计器）；闭环偏置 × 闭式不动点预测；
     · LVS：嵌入矩阵装配 × 平台 lda_l2 行组合装配；
     · 基准：数值分布 × 闭式（permanent/DFT/δ）。
  ③ **反自证桩**：
     · 单模输入分布对网格相位 φ **免疫**（φ 只贡献整体相位）⇒ 单光子计数标不了相位，
       跨模双光子才敏感 —— 这对判据保证 LVS 的量子层交叉不是假绿。

═══ 判什么（分四节 · 26 条）═══
A 标定闭环（D-117）8 条 · B 量子 DRC/LVS（D-118）7 条 · C 量子基准（D-119）6 条 ·
D 跨模块 + 红线 5 条。

运行：python run_quantum_calib_bench_smoke.py（cwd=lda/）
出口：全 PASS 退 0；任一 FAIL 退 1。LLM 不进判决路径。
"""
from __future__ import annotations

import math
import os
import re
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))       # = …/lda
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:
    from lda_qeda import calibration as CAL
    from lda_qeda import quantum_drc_lvs as QDR
    from lda_qeda import quantum_benchmark as QBM
    from lda_qeda import loqc_states as LS
except ImportError:                                       # 极端兜底
    sys.path.insert(0, os.path.join(_HERE, "lda_qeda"))
    import calibration as CAL          # noqa: E402
    import quantum_drc_lvs as QDR      # noqa: E402
    import quantum_benchmark as QBM    # noqa: E402
    import loqc_states as LS           # noqa: E402

from lda_l2 import mzi_mesh_matmul as MMM                 # noqa: E402
from lda_harness.smoke_kit import make_check              # noqa: E402

# 计数写进模块命名空间；助手复用公共 `smoke_kit`，不另建局部 `def check`
# （防「助手重复棘轮」J3/J4 劣化 · 名字在前！写反成 check(cond, name) ⇒ 假绿）。
PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=" | {d}", return_ok=True)


def main() -> int:
    print("=" * 78)
    print("量子标定 / DRC-LVS / 基准 门禁 smoke（D-117 标定 · D-118 签核 · D-119 基准）")
    print("=" * 78)

    # ════════════════ A 节：L3 标定闭环（D-117）════════════════
    print("── A L3 标定闭环（D-117）──")
    try:
        ok_a = CAL.run_selfchecks(verbose=False)
    except Exception as e:                                # noqa: BLE001
        ok_a = False
        print(f"  标定自检异常：{type(e).__name__}: {e}")
    check("A1 标定模块自检 9/9 PASS", ok_a, "三点法/不变性/执行器/双估计器/CRB/闭环/条纹/二次律/护栏")

    mx = 0.0
    for phi in np.linspace(-3.0, 3.0, 25):
        for vis in (0.3, 0.7, 1.0):
            est = CAL.phase_from_three_step(*CAL.three_step_probe(float(phi), vis))
            mx = max(mx, abs(CAL.angle_diff(est, float(phi))))
    check("A2 三点相移闭式 φ=atan2(√3(I₁−I₃),2I₂−I₁−I₃) 精确", mx < 1e-12, f"max|Δ|={mx:.2e}")

    inv = 0.0
    for i0 in (0.5, 3.0):
        for vis in (0.4, 1.0):
            inv = max(inv, abs(CAL.angle_diff(
                CAL.phase_from_three_step(*CAL.three_step_probe(1.1, vis, i0)), 1.1)))
    check("A3 三点法对总光强 I₀ · 可见度 𝒱 不变（比值消去）", inv < 1e-12, f"max|Δ|={inv:.2e}")

    rt = 0.0
    for phi in (0.5, 2.0, -2.5):
        for b2 in (0.0, 2e-4):
            V = CAL.voltage_from_phase(phi, phi0=0.05, beta2=b2)
            rt = max(rt, abs(CAL.angle_diff(CAL.phase_from_voltage(V, phi0=0.05, beta2=b2), phi)))
    check("A4 执行器 φ→V→φ 自洽（β=0 闭式 & β≠0 牛顿）", rt < 1e-9, f"max|Δ|={rt:.2e}")

    two = 0.0
    for phi in (0.4, 1.9):
        for vis in (0.5, 0.9):
            grid = [phi + d for d in CAL._DELTAS] + [phi + 0.6]
            pows = [CAL.fringe_power(g, vis) for g in grid]
            two = max(two, abs(CAL.angle_diff(
                CAL.estimate_phase_lsq([g - phi for g in grid], pows),
                CAL.phase_from_three_step(*CAL.three_step_probe(phi, vis)))))
    check("A5 三点法 × 最小二乘正弦拟合 两估计器独立一致", two < 1e-9, f"max|Δ|={two:.2e}")

    c1 = CAL.calibrate_phase(1.1, hardware_slope=1.0, vis=0.9)
    check("A6 探测器反馈闭环：增益已标定 ⇒ 一步到机器精度",
          c1["converged"] and abs(c1["residual_rad"]) < 1e-12,
          f"n_iter={c1['n_iter']} 残差={abs(c1['residual_rad']):.1e}")

    bd = 0.0
    for slope, tgt in ((0.9, 2.2), (1.1, -1.5)):
        c = CAL.calibrate_phase(tgt, hardware_slope=slope, vis=0.9, n_iter=120)
        bd = max(bd, abs(CAL.angle_diff(c["phi_final"], CAL.three_step_bias_limit(tgt, slope))))
    check("A7 增益有残差时闭环偏置 ≡ 闭式不动点预测", bd < 1e-6, f"max|Δ|={bd:.2e}")

    Ns = np.array([1e3, 1e4, 1e5, 1e6])
    sig = np.array([CAL.phase_uncertainty_mc(0.3, 0.9, float(N), n_trials=1500) for N in Ns])
    sl = float(np.polyfit(np.log(Ns), np.log(sig), 1)[0])
    check("A8 相位估计散粒噪声标度 σ∝N^(-1/2)（CRB）", abs(sl + 0.5) < 0.06, f"斜率={sl:.3f}")

    # ════════════════ B 节：量子 DRC/LVS（D-118）════════════════
    print("── B 量子器件 DRC/LVS（D-118）──")
    try:
        ok_b = QDR.run_selfchecks(verbose=False)
    except Exception as e:                                # noqa: BLE001
        ok_b = False
        print(f"  DRC/LVS 自检异常：{type(e).__name__}: {e}")
    check("B1 DRC/LVS 模块自检 11/11 PASS", ok_b,
          "双路装配/零扰动/量化/噪声/DRC 九规则/阈值/反自证桩/护栏/★重判更严(D-124)/限值可覆盖")

    N4 = 4
    Ut = MMM.dft_matrix(N4)
    ops, D = MMM.reck_triangular_mesh(Ut)
    Ua = QDR._assemble_by_embedding(ops, D, N4)
    Ub = MMM.assemble_triangular_mesh(ops, D, N4)
    check("B2 LVS 双路装配一致（嵌入矩阵 × lda_l2 行组合）",
          float(np.max(np.abs(Ua - Ub))) < 1e-12, f"max|Δ|={float(np.max(np.abs(Ua - Ub))):.2e}")

    s0 = QDR.quantum_lvs_signoff(Ut, ops, D, N4, phase_bits=None)
    s12 = QDR.quantum_lvs_signoff(Ut, ops, D, N4, phase_bits=12)
    s3 = QDR.quantum_lvs_signoff(Ut, ops, D, N4, phase_bits=3)
    check("B3 零扰动签核 fid=1 ⇒ ACCEPT；量化 12bit 仍 ACCEPT",
          abs(s0["fidelity"] - 1.0) < 1e-12 and s0["verdict"] == "ACCEPT"
          and s12["fidelity"] > 0.999 and s12["verdict"] == "ACCEPT",
          f"fid0={s0['fidelity']:.12f} fid12={s12['fidelity']:.6f}")

    check("B4 低比特相位量化（3bit）显著退化 ⇒ REJECT",
          s3["verdict"] == "REJECT" and s3["fidelity"] < s12["fidelity"] - 1e-3,
          f"fid3={s3['fidelity']:.6f} < fid12={s12['fidelity']:.6f}")

    legal = {"ops": ops, "N": N4, "n_crossings": 0, "source_g2": 0.03,
             "hom_visibility": 0.96, "detector_eta": 0.85,
             "calib_residual_rad": 1e-3, "phase_bits": 12}
    d_ok = QDR.run_quantum_drc(legal)
    check("B5 量子 DRC：全合法设计 ⇒ ACCEPT（9 规则全查）",
          d_ok["verdict"] == "ACCEPT" and d_ok["n_rules"] == 9,
          f"n_rules={d_ok['n_rules']}")

    inj = {"QDR-PHASE-DOMAIN": {"ops": [(0, 0, 3.5, 0.0)] + list(ops)},
           "QDR-COUPLING-RANGE": {"ops": [(0, 0, 0.05, 0.0)] + list(ops)},
           "QDR-PHASE-RESOLUTION": {"phase_bits": 2},
           "QDR-CROSSING-BUDGET": {"n_crossings": 1000},
           "QDR-LOSS-BUDGET": {"n_crossings": 0, "ops": list(ops) * 40},
           "QDR-SOURCE-PURITY": {"source_g2": 0.5},
           "QDR-INDISTINGUISHABILITY": {"hom_visibility": 0.5},
           "QDR-DETECTOR-EFFICIENCY": {"detector_eta": 0.3},
           "QDR-CALIB-RESIDUAL": {"calib_residual_rad": 0.1}}
    hits = []
    for rule, patch in inj.items():
        dd = dict(legal)
        dd.update(patch)
        hits.append(rule in {v["rule"] for v in QDR.run_quantum_drc(dd)["violations"]})
    check("B6 量子 DRC 九规则逐条可触发（注入必被报出）",
          all(hits), f"{sum(hits)}/9")

    Ua0 = QDR.reconstruct_actual_unitary(ops, D, N4, phase_bits=None)
    UaN = QDR.reconstruct_actual_unitary(ops, D, N4, phase_bits=None, calib_sigma=0.5, seed=3)
    g1 = max(abs(LS.output_distribution(Ua0, (1, 0, 0, 0))[k]
                 - LS.output_distribution(UaN, (1, 0, 0, 0)).get(k, 0.0))
             for k in LS.output_distribution(Ua0, (1, 0, 0, 0)))
    g2 = max(abs(LS.output_distribution(Ua0, (1, 1, 0, 0))[k]
                 - LS.output_distribution(UaN, (1, 1, 0, 0)).get(k, 0.0))
             for k in LS.output_distribution(Ua0, (1, 1, 0, 0)))
    check("B7 量子层反自证桩：单光子分布对 φ 免疫 · 跨模双光子敏感",
          g1 < 1e-12 and g2 > 1e-2, f"单光子Δ={g1:.1e} 双光子Δ={g2:.3e}")

    # ════════════════ C 节：量子基准（D-119）════════════════
    print("── C 量子基准（D-119）──")
    try:
        ok_c = QBM.run_selfchecks(verbose=False)
    except Exception as e:                                # noqa: BLE001
        ok_c = False
        print(f"  基准自检异常：{type(e).__name__}: {e}")
    check("C1 基准模块自检 9/9 PASS", ok_c, "概率守恒/DFT均匀/δ/HOM/采样/χ²/可见度/综合分/护栏")

    mx_norm = 0.0
    for U in (MMM.dft_matrix(4), np.eye(4, dtype=complex)):
        for occ in ((1, 0, 0, 0), (1, 1, 0, 0)):
            mx_norm = max(mx_norm, abs(QBM.boson_sampling_benchmark(U, occ)["norm"] - 1.0))
    check("C2 玻色采样概率守恒 Σ_out P=1（物理律）", mx_norm < 1e-12, f"max|Δ|={mx_norm:.2e}")

    d_dft = LS.output_distribution(MMM.dft_matrix(4), (1, 0, 0, 0))
    dev = max(abs(p - 0.25) for p in d_dft.values())
    check("C3 DFT + |1⟩ ⇒ 输出均匀 1/N（闭式 golden）", dev < 1e-12, f"max|Δ|={dev:.2e}")

    bs50 = LS.bs_unitary(math.pi / 4.0)
    p_coin = LS.coincidence_probability(bs50, (1, 1), (0, 1), (0, 1))
    vis_hom = LS.hom_visibility(math.pi / 4.0)
    check("C4 HOM 50/50 不可区分 ⇒ 符合率 0 · 可见度 V=1（闭式）",
          abs(p_coin) < 1e-12 and abs(vis_hom - 1.0) < 1e-12,
          f"P_coin={p_coin:.2e} V={vis_hom:.6f}")

    dist = LS.output_distribution(MMM.dft_matrix(4), (1, 1, 0, 0))
    keys, counts = QBM.sample_from_distribution(dist, 200000, seed=11)
    th = np.array([dist[k] for k in keys])
    gof = QBM.chi_square_gof(counts, th, int(counts.sum()))
    check("C5 采样统计：2e5 样本 χ² 拟合优度不拒绝理论分布",
          not gof["reject_5pct"], f"p={gof['p_value']:.3f} dof={gof['dof']}")

    b0 = QBM.composite_quantum_score(n_modes=16, n_photons=4, fidelity=0.99)["score"]
    bN = QBM.composite_quantum_score(n_modes=64, n_photons=4, fidelity=0.99)["score"]
    bg = QBM.composite_quantum_score(n_modes=16, n_photons=4, fidelity=0.99, source_g2=0.5)["score"]
    check("C6 综合对标分单调（N↑ 升 · g²↑ 降）", bN > b0 and bg < b0,
          f"N16={b0:.2f} N64={bN:.2f} g²0.5={bg:.2f}")

    # ════════════════ D 节：跨模块 + 红线 ════════════════
    print("── D 跨模块一致性 + 红线 ──")
    d_bridge = 0.0
    for phi in (0.3, 1.7, 3.0):
        d_bridge = max(d_bridge, abs(CAL.voltage_from_phase(phi) - MMM.voltage_from_phase(phi)))
    check("D1 跨层桥：D-117 执行器 ≡ 平台 L2 mzi_mesh_matmul.voltage_from_phase",
          d_bridge < 1e-12, f"max|Δ|={d_bridge:.2e}")

    # D2 跨模块链：D-117 标定残差 → D-118 DRC 判据 → D-119 保真度基准
    c_res = CAL.calibrate_phase(0.8, hardware_slope=1.0, vis=0.9)["residual_rad"]
    design_chain = dict(legal)
    design_chain["calib_residual_rad"] = abs(c_res)
    vd = QDR.run_quantum_drc(design_chain)["verdict"]
    pf = QBM.process_fidelity_benchmark(
        LS.hom_visibility(math.pi / 4.0),
        QDR.quantum_lvs_signoff(Ut, ops, D, N4, phase_bits=12)["fidelity"])
    check("D2 跨模块链：D-117 标定残差 → D-118 DRC → D-119 保真度基准（判定连通）",
          vd == "ACCEPT" and pf["product"] > 0.99,
          f"DRC={vd} 过程保真乘积={pf['product']:.6f}")

    # D3 三段能力汇聚：源 g²(D-114) + 探测 η(D-115) + 标定(D-117) → D-118 DRC 数据契约
    full_design = {"ops": ops, "N": N4, "n_crossings": 0,
                   "source_g2": 0.06, "hom_visibility": 0.94, "detector_eta": 0.88,
                   "calib_residual_rad": 2e-3, "phase_bits": 12}
    check("D3 源/探测/标定参数经 DRC 数据契约汇聚 ⇒ ACCEPT（接口解耦连通）",
          QDR.run_quantum_drc(full_design)["verdict"] == "ACCEPT")

    banned = ("qiskit", "cirq", "pennylane", "strawberryfields", "thewalrus", "qutip")
    hits = []
    for mod in ("calibration", "quantum_drc_lvs", "quantum_benchmark"):
        src = open(os.path.join(_HERE, "lda_qeda", mod + ".py"), encoding="utf-8").read()
        hits += [f"{mod}:{b}" for b in banned if re.search(rf"^\s*(import|from)\s+{b}\b", src, re.M)]
    check("D4 红线：三模块零量子 SDK 依赖（纯 numpy + 平台，C 级自主）",
          not hits, f"命中={hits or '无'}")

    # D5 诚实边界：综合对标分必须自标为「非国际公认指标」
    score = QBM.composite_quantum_score(n_modes=16, n_photons=4, fidelity=0.99)
    check("D5 诚实边界：综合分自带『非国际公认指标』标注（防对外误称）",
          "NOT a recognized" in score["label"], score["label"][:48])

    print()
    print(f"量子标定/DRC-LVS/基准 门禁 smoke：{PASS}/{PASS + FAIL} PASS")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
