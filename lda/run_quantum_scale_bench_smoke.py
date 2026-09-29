"""量子规模对标门禁 smoke（D-120 · M4 规模律与瓶颈守卫）。

═══ 为什么要有这个 smoke ═══
D-120（M4 规模对标）是本平台**唯一**把「规模」本身当被判对象的模块。它的结论
极易被后人改坏成「看起来对」的样子，必须钉成常驻断言：

  ① **闭式规模律**：n_mzi=N(N−1)/2 · n_stages=N−1 · loss=件数×per_mzi ·
     hilbert_dim=C(N+k−1,k)。有人把任一常数/公式改错 ⇒ 立刻失真。
  ② **核心反直觉结论（最易被"修"掉）**：网格酉保真度对规模**尺度盲** ——
     N 从 4 到 216，F 几乎不变（1−F≈(σ/2)√((N−1)/N)）。若有人把这条断言
     "修正"成「保真度随 N 下降」，必须立刻变红。
  ③ **规模墙排序**：第一面墙是**损耗**（指数），不是保真度。
  ④ **架构结论**：静态网格元件 O(N²)/损耗 O(N) dB vs 时间复用 O(log N)。
  ⑤ **对标诚实性**：Borealis 模数 216 对得上，但物理形态不同（CV GBS vs
     DV 被动 LOQC）⇒ 必须**只比规模律不比数值**，且引用可溯源。

═══ 判什么（分六节 · 26 条）═══
A 闭式规模律 5 · B N=216/100 实测 4 · C 标定尺度盲+损耗墙 6 ·
D 复杂度墙+输出墙 4 · E 架构对标+Borealis 4 · F 规模签核+跨模块+红线 4。

运行：python run_quantum_scale_bench_smoke.py（cwd=lda/）
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
    from lda_qeda import scale_bench as SBM
    from lda_qeda import quantum_drc_lvs as QDR
    from lda_qeda import loqc_states as LS
except ImportError:                                       # 极端兜底
    sys.path.insert(0, os.path.join(_HERE, "lda_qeda"))
    import scale_bench as SBM              # noqa: E402
    import quantum_drc_lvs as QDR          # noqa: E402
    import loqc_states as LS               # noqa: E402

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
    print("量子规模对标 门禁 smoke（D-120 · N=100+/Borealis 216 模 规模律与瓶颈）")
    print("=" * 78)

    # ════════════════ A 节：闭式规模律 ════════════════
    print("── A 闭式规模律（golden）──")
    try:
        ok_a = SBM.run_selfchecks(verbose=False)
    except Exception as e:                                # noqa: BLE001
        ok_a = False
        print(f"  规模模块自检异常：{type(e).__name__}: {e}")
    check("A1 规模模块自检 13/13 PASS", ok_a,
          "规模律/216实测/尺度盲/标定律/损耗墙/复杂度/输出墙/架构/对标/瓶颈/护栏/★每模口径(D-125)")

    bad = [n for n in (2, 3, 4, 8, 16, 32, 64, 100, 128, 216)
           if SBM.mesh_scaling_laws(n)["n_mzi"] != n * (n - 1) // 2]
    check("A2 元件数闭式 n_mzi=N(N−1)/2 精确（N=2…216 全对）",
          not bad, f"失配={bad or '无'} N=216⇒{SBM.mesh_scaling_laws(216)['n_mzi']}")

    bad = [n for n in (2, 4, 16, 64, 216)
           if not (SBM.mesh_scaling_laws(n)["n_stages"] == n - 1
                   and SBM.mesh_scaling_laws(n)["mzi_per_path"] == n - 1)]
    check("A3 深度闭式 n_stages=mzi_per_path=N−1 精确", not bad, f"失配={bad or '无'}")

    pm = SBM.PER_MZI_LOSS_DB
    ok4 = True
    for n in (4, 16, 64, 216):
        L = SBM.mesh_scaling_laws(n)
        if abs(L["loss_total_db"] - L["n_mzi"] * pm) > 1e-9:
            ok4 = False
        if abs(L["loss_per_path_db"] - (n - 1) * pm) > 1e-9:
            ok4 = False
    check("A4 插损闭式 total=件数·per_mzi · per_path=(N−1)·per_mzi",
          ok4, f"per_mzi={pm:.3f} dB（=2×DC+2×PS+波导段，与 L2 同源）")

    bad = [n for n in (4, 16, 100, 216)
           if SBM.mesh_scaling_laws(n)["calib_phases"] != n * (n - 1) // 2 + n]
    check("A5 标定相位数闭式 = N(N−1)/2 + N（网格 + 输入对角层）",
          not bad, f"N=216⇒{SBM.mesh_scaling_laws(216)['calib_phases']} 相位")

    # ════════════════ B 节：N=216 / N=100 实测 ════════════════
    print("── B 大规模实测剖析（N=216 / N=100）──")
    p216 = SBM.mesh_scale_profile(216)
    check("B1 N=216 实测元件数 ≡ 闭式 23220（真实建 mesh）",
          p216["n_mzi_measured"] == 23220 and p216["laws_match"] is True,
          f"n_mzi={p216['n_mzi_measured']} gen={p216['gen_s']:.3f}s asm={p216['asm_s']:.3f}s")

    check("B2 N=216 mesh 酉保真度=机器精度 + 装配酉性成立（构造性定理）",
          abs(p216["fidelity"] - 1.0) < 1e-12 and p216["unitary_ok"] is True,
          f"fid={p216['fidelity']:.15f} ‖UU†−I‖<1e-9")

    p100 = SBM.mesh_scale_profile(100)
    check("B3 N=100（M4 目标下限）实测 ≡ 闭式 4950 且保真度=机器精度",
          p100["n_mzi_measured"] == 4950 and abs(p100["fidelity"] - 1.0) < 1e-12,
          f"n_mzi={p100['n_mzi_measured']} fid={p100['fidelity']:.15f}")

    mism = []
    for n in (4, 8, 16, 32, 64):
        ops_n, D_n = MMM.reck_triangular_mesh(MMM.dft_matrix(n))
        if len(ops_n) != SBM.mesh_scaling_laws(n)["n_mzi"]:
            mism.append(n)
    check("B4 逐 N 对账：实测 op 数 ≡ 闭式规模律（N=4…64）",
          not mism, f"失配={mism or '无'}")

    # ════════════════ C 节：标定尺度盲 + 损耗墙 ════════════════
    print("── C 标定尺度盲（核心发现）+ 损耗墙 ──")
    F216 = SBM.calibration_fidelity_law(0.01, 216)
    pred = 1.0 - (0.01 / 2.0) * math.sqrt(215 / 216)
    check("C1 标定保真度闭式 F=1−(σ/2)√((N−1)/N) 自洽（N=216, σ=0.01）",
          abs(F216 - pred) < 1e-15, f"F={F216:.6f}")

    ratios = [(1.0 - SBM.calibration_fidelity_law(s, 16)) / s for s in (0.005, 0.01, 0.02, 0.04)]
    check("C2 标定律线性于 σ：(1−F)/σ 常量（四次取样）",
          max(ratios) - min(ratios) < 1e-12, f"(1−F)/σ={ratios[0]:.4f}（全同）")

    # 核心结论：保真度判决对 N 尺度盲（实测 N=4 vs N=32 同 σ 下几乎一致）
    f4 = SBM.measure_calibration_fidelity(4, 0.02, seeds=5)
    f32 = SBM.measure_calibration_fidelity(32, 0.02, seeds=5)
    check("C3 ★核心★ 酉保真度尺度盲：实测 F(N=4) 与 F(N=32) 同 σ 下几乎一致",
          abs(f4 - f32) < 0.01, f"F(4)={f4:.5f} F(32)={f32:.5f} |Δ|={abs(f4-f32):.4f}")

    e216 = SBM.per_path_transmissivity(216)
    e100 = SBM.per_path_transmissivity(100)
    check("C4 损耗墙：单路径透射率指数衰减 η(216)<η(100)<1e−20",
          e216 < e100 < 1e-20, f"η(100)={e100:.2e} η(216)={e216:.2e}")

    w = SBM.loss_wall_n(1e-2)
    check("C5 损耗关门点闭式自洽：η(N*−1)≥1e−2 且 η(N*)<1e−2",
          SBM.per_path_transmissivity(w - 1) >= 1e-2 > SBM.per_path_transmissivity(w),
          f"N*({w-1})={SBM.per_path_transmissivity(w-1):.4f} N*({w})={SBM.per_path_transmissivity(w):.4f}")

    s4 = math.sqrt(0.002 / SBM.mesh_scaling_laws(4)["n_mzi"])
    s216 = math.sqrt(0.002 / SBM.mesh_scaling_laws(216)["n_mzi"])
    check("C6 标定容差随 N 收紧 O(1/N)：σ*(216)/σ*(4) < 0.05",
          s216 / s4 < 0.05, f"σ*(4)={s4:.5f} σ*(216)={s216:.6f} 比={s216/s4:.4f}")

    # ════════════════ D 节：复杂度墙 + 输出空间墙 ════════════════
    print("── D LVS 复杂度墙 + 输出空间墙 ──")
    cost = SBM.lvs_assembly_cost(216)
    check("D1 LVS 复杂度墙：独立装配 O(N^5) vs 平台 O(N^3)（代价比≈2·n_mzi=O(N²)）",
          cost["independent_ops_complexity"] == "O(N^5)"
          and cost["platform_ops_complexity"] == "O(N^3)"
          and cost["independent_scalable"] is False,
          f"比值≈{cost['independent_over_platform']:.0f}×（N=216）")

    # 精确计数：独立路径 flops 阶 = n_mzi·2N³ = N⁴(N−1)（O(N⁵) 的精确身位）
    c16, c32 = SBM.lvs_assembly_cost(16), SBM.lvs_assembly_cost(32)
    ok2 = (c16["independent_flops_order"] == 120 * 2 * 16 ** 3
           and c32["independent_flops_order"] == 496 * 2 * 32 ** 3)
    check("D2 独立路径 flops 精确计数 = n_mzi·2N³ = N⁴(N−1)（O(N⁵) 身位）",
          ok2, f"N=16⇒{c16['independent_flops_order']:.3e} N=32⇒{c32['independent_flops_order']:.3e}")

    ok7 = True
    for (n, occ) in ((4, (1, 1, 0, 0)), (4, (2, 0, 0, 0)), (3, (2, 2, 0))):
        if SBM.hilbert_dim(n, sum(occ)) != len(LS.output_distribution(np.eye(n, dtype=complex), occ)):
            ok7 = False
    check("D3 输出空间恒等式：hilbert_dim(N,k)=C(N+k−1,k) ≡ 枚举输出态数",
          ok7, "小规模对拍 3 组")

    bits = SBM.output_space_bits(216, 125)
    check("D4 输出空间墙：C(216+124,125) log2>300 bits（规模上不可枚举/校验）",
          bits > 300.0, f"log2={bits:.1f} bits")

    # ════════════════ E 节：架构对标 + Borealis ════════════════
    print("── E 架构权衡（静态网格 × 时间复用）+ Borealis 对标 ──")
    tm = SBM.time_multiplexed_architecture(216)
    check("E1 时间复用架构：3 环 ⇒ a³=6³=216 模（精确整数幂，无浮点 ceil 陷阱）",
          tm["n_loops"] == 3 and tm["n_modes_realized"] == 216,
          f"loops={tm['n_loops']} a={tm['lattice_a']} realized={tm['n_modes_realized']}")

    tr = SBM.architecture_tradeoff(216)
    check("E2 架构权衡：时间复用比静态网格省损 >400 dB",
          tr["loss_saving_db_tmux"] > 400.0,
          f"静态 {tr['static']['loss_per_path_db']:.0f} dB vs 复用 {tr['time_multiplexed']['loss_per_mode_db']:.0f} dB")

    bm = SBM.benchmark_against_borealis(216)
    check("E3 Borealis 对标：模数 216 匹配 · 形态不同(CV GBS vs DV LOQC) · 诚实标注齐备",
          bm["mode_count_matches"] is True and bm["same_modality"] is False
          and "honest_boundary" in bm,
          f"匹配={bm['mode_count_matches']} 同形态={bm['same_modality']}")

    ref = SBM.BOREALIS_REF
    check("E4 外部事实 A 级可溯源（Nature 606 + DOI + URL）",
          "Nature 606" in ref["source"] and ref["doi"] == "10.1038/s41586-022-04725-x"
          and ref["public_url"].startswith("https://www.nature.com/"),
          f"{ref['source']} doi:{ref['doi']}")

    # ════════════════ F 节：规模签核 + 跨模块 + 红线 ════════════════
    print("── F 规模签核行为 + 跨模块 + 红线 ──")
    # 真实调用 D-118：N=216 网格在损耗预算上必然 REJECT（规模签核的诚实结论）
    ops216, D216 = MMM.reck_triangular_mesh(MMM.dft_matrix(216))
    d216 = QDR.run_quantum_drc({"ops": ops216, "N": 216, "n_crossings": 0,
                                "source_g2": 0.03, "hom_visibility": 0.96,
                                "detector_eta": 0.85, "calib_residual_rad": 1e-3,
                                "phase_bits": 12})
    rules216 = {v["rule"] for v in d216["violations"]}
    check("F1 规模签核：N=216 网格 DRC 因 QDR-LOSS-BUDGET 必然 REJECT（损耗墙落到判据上）",
          d216["verdict"] == "REJECT" and "QDR-LOSS-BUDGET" in rules216,
          f"违例={sorted(rules216)}")

    # 跨模块桥：D-120 的 per_path 闭式 ≡ (N−1)× L2 单件损耗（由 L2 函数反解）
    per_mzi_l2 = MMM.mesh_cascade_loss_db(1, n_crossings=0)
    d_bridge = abs((216 - 1) * per_mzi_l2 - SBM.mesh_scaling_laws(216)["loss_per_path_db"])
    check("F2 跨模块桥：D-120 per_path ≡ (N−1)× L2 单件级联损耗（同源常数）",
          d_bridge < 1e-9, f"max|Δ|={d_bridge:.2e} L2 单件={per_mzi_l2:.3f} dB")

    banned = ("qiskit", "cirq", "pennylane", "strawberryfields", "thewalrus", "qutip")
    hits = [b for b in banned
            if re.search(rf"^\s*(import|from)\s+{b}\b",
                         open(os.path.join(_HERE, "lda_qeda", "scale_bench.py"),
                              encoding="utf-8").read(), re.M)]
    check("F3 红线：D-120 零量子 SDK 依赖（纯 numpy + 平台，C 级自主）",
          not hits, f"命中={hits or '无'}")

    br = SBM.scale_bottleneck_report((4, 16, 64, 216), sigma_cal=0.001)
    check("F4 瓶颈诊断：第一墙=损耗 · 保真度判决 N-不变（尺度盲机器判据）",
          br["first_wall_closed"] == "loss" and br["fidelity_verdict_n_invariant"] is True,
          f"第一墙={br['first_wall_closed']} 保真度N不变={br['fidelity_verdict_n_invariant']}")

    print()
    print(f"量子规模对标 门禁 smoke：{PASS}/{PASS + FAIL} PASS")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
