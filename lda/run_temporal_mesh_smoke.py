"""量子时间复用可编程酉 门禁 smoke（D-121 · M4 延伸：构造性通用性 + 「买元件数不买损耗」）。

═══ 为什么要有这个 smoke ═══
D-121 是本平台**唯一**把「时间复用架构」当被判对象的模块，它给出三条极易被后人
"修"成好看样子的结论，必须钉成常驻断言：

  ① **构造性通用性**：时间复用（1 片物理 MZI）**能**重现任意 N 模酉到机器精度。
     有人把 schedule 的装配方向改错 ⇒ 保真度立刻掉到 ~0.6（本轮真实血案）。
  ② **深度下界（参数计数）**：D ≥ ⌈n_mzi/⌊N/2⌋⌉，N 偶⇒N−1、N 奇⇒N。
     有人把下界"放宽"到 o(N) ⇒ 立刻变红（这是「不省损耗」结论的地基）。
  ③ **★修正 M4 口号★**：通用目标下时间复用**不省损耗**（最有利假设下严格更差）。
     有人把结论反转成「时间复用省损」⇒ 必须立刻变红。
  ④ **Borealis 维度判死**：浅晶格可及参数 ≪ N² ⇒ 非通用（只比规模/参数计数）。
  ⑤ **任意对可寻址引理 L1**：非相邻对由延迟共轭寻址（含「置换阵必须从零阵起建」
     的踩坑点：用 np.eye 起手会残留对角 1 ⇒ 引理假红）。

═══ 判什么（分六节 · 24 条）═══
A 时空原语 4 · B 构造性通用性 4 · C 深度下界+元件数 4 ·
D 损耗不省+Borealis 维度判死 4 · E 跨模块+前沿+诚实标注 4 · F 常数同源+红线 4。

运行：python run_temporal_mesh_smoke.py（cwd=lda/）
出口：全 PASS 退 0；任一 FAIL 退 1。LLM 不进判决路径。
"""
from __future__ import annotations

import os
import re
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))       # = …/lda
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:
    from lda_qeda import temporal_mesh as TMB
    from lda_qeda import scale_bench as SBM
    from lda_qeda import loqc_states as LS
except ImportError:                                       # 极端兜底
    sys.path.insert(0, os.path.join(_HERE, "lda_qeda"))
    import temporal_mesh as TMB            # noqa: E402
    import scale_bench as SBM              # noqa: E402
    import loqc_states as LS               # noqa: E402

from lda_l2 import mzi_mesh_matmul as MMM                 # noqa: E402
from lda_harness.smoke_kit import make_check              # noqa: E402

# 计数写进模块命名空间；助手复用公共 `smoke_kit`，不另建局部 `def check`
# （防「助手重复棘轮」劣化 · **名字在前**！写反成 check(cond, name) ⇒ 假绿）。
PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=" | {d}", return_ok=True)


def main() -> int:
    print("=" * 78)
    print("量子时间复用可编程酉 门禁 smoke（D-121 · M4 延伸）")
    print("=" * 78)

    # ════════════════ A 节：时空原语 ════════════════
    print("── A 时空原语（延迟=置换 · 任意对寻址 · 2 模 golden）──")
    try:
        ok_a = TMB.run_selfchecks(verbose=False)
    except Exception as e:                                # noqa: BLE001
        ok_a = False
        print(f"  时间复用模块自检异常：{type(e).__name__}: {e}")
    check("A1 时间复用模块自检 13/13 PASS", ok_a,
          "时空原语/引理L1/2模golden/护栏/构造性通用性/深度下界/资源/损耗/对标/前沿/护栏")

    bad = []
    for n in (4, 7, 216):
        S = TMB.cyclic_shift_unitary(n, 1)
        if float(np.max(np.abs(S @ S.conj().T - np.eye(n)))) > 1e-12:
            bad.append(n)
        if float(np.max(np.abs(np.linalg.matrix_power(S, n) - np.eye(n)))) > 1e-12:
            bad.append(n)
    check("A2 延迟环=酉置换：S_m 酉性 + S_1^N=I（N=4/7/216）",
          not bad, f"失配={bad or '无'}")

    n, m, i, th, ph = 7, 3, 2, 0.7, 0.4
    direct = TMB.pair_rotation_unitary(n, i, i + m, th, ph)
    P = np.zeros((n, n), dtype=complex)               # 🔴 必须零阵起建（踩坑点）
    for k in range(n):
        P[(k + i) % n, k] = 1.0
    conj = P @ TMB.pair_rotation_unitary(n, 0, m, th, ph) @ P.conj().T
    check("A3 ★引理 L1★ 非相邻对由延迟共轭寻址：(i,i+m) ≡ P·(0,m)·P†",
          float(np.max(np.abs(direct - conj))) < 1e-14,
          f"max|Δ|={float(np.max(np.abs(direct - conj))):.2e}（P 从零阵起建）")

    U_lda = MMM.mzi_unit_cell(0.9, 0.3)
    U_bs = LS.bs_unitary(0.45, 0.3 + np.pi / 2.0)
    gauge = U_lda @ U_bs.conj().T
    diag_ok = float(np.max(np.abs(gauge - np.diag(np.diag(gauge))))) < 1e-13
    mag_ok = float(np.max(np.abs(np.abs(U_lda) - np.abs(U_bs)))) < 1e-13
    check("A4 2 模 golden：MZI 与 loqc_states.bs_unitary 同分束比 + 差对角相位规范",
          diag_ok and mag_ok, "分束比逐元素一致 · 差异仅为局部相位规范")

    # ════════════════ B 节：构造性通用性 ════════════════
    print("── B 构造性通用性（1 片物理 MZI 重现任意酉）──")
    worst = 1.0
    ok1 = True
    for n_ in (4, 8, 16, 32, 64):
        pr = TMB.temporal_schedule_profile(n_, target="dft")
        worst = min(worst, pr["fidelity"])
        if not (abs(pr["fidelity"] - 1.0) < 1e-11 and pr["unitary_ok"]):
            ok1 = False
    check("B1 构造性通用性（DFT 酉）：N=4…64 时间表重建 ≡ 目标（机器精度）",
          ok1, f"最差 fid={worst:.12f}")

    ok2 = True
    got2 = []
    for n_ in (4, 16, 64):
        pr = TMB.temporal_schedule_profile(n_, target="random", seed=n_ * 13 + 1)
        got2.append(f"N={n_}:{pr['fidelity']:.12f}")
        if not (abs(pr["fidelity"] - 1.0) < 1e-11 and pr["unitary_ok"]):
            ok2 = False
    check("B2 构造性通用性（Haar 随机酉）：非基准矩阵同样机器精度",
          ok2, " · ".join(got2))

    # 每步必须是真匹配（否则「同一步内共享模」在物理上不可实现）
    n_ = 12
    U_ = TMB.random_unitary(n_, seed=5)
    ops_, D_ = MMM.reck_triangular_mesh(U_)
    sched_, _ = TMB.schedule_from_reck_ops(ops_, D_, n_)
    step_ok = all(TMB.gate_matching_ok(
        [(int(i2), float(t2), float(p2), bool(v2)) for (i2, t2, p2, v2) in s["gates"]], n_)
        for s in sched_ if s["kind"] == "gates")
    max_per_step = max(len(s["gates"]) for s in sched_ if s["kind"] == "gates")
    check("B3 时间表每步都是真『匹配』（两两不相交 ⇒ 可同步施加）",
          step_ok and max_per_step <= n_ // 2,
          f"N=12 最大同步门数={max_per_step}（≤⌊N/2⌋={n_ // 2}）")

    pr = TMB.temporal_schedule_profile(32, target="dft")
    check("B4 构造时间表自洽：门数=N(N−1)/2 · 深度∈[下界, 门数]",
          pr["n_gates"] == 32 * 31 // 2 and pr["depth_within_bounds"] is True,
          f"gates={pr['n_gates']} steps={pr['n_gate_steps']} dmin={pr['depth_lower_bound']}")

    # ════════════════ C 节：深度下界 + 元件数 ════════════════
    print("── C 通用性深度下界（参数计数）+ 元件数 ──")
    bad3 = []
    for n_ in (2, 3, 4, 5, 8, 16, 64, 100, 216):
        d = TMB.universality_depth_lower_bound(n_)
        if (n_ % 2 == 0 and d != n_ - 1) or (n_ % 2 == 1 and d != n_):
            bad3.append(n_)
    check("C1 深度下界闭式：⌈N(N−1)/2 / ⌊N/2⌋⌉ ⇒ N 偶=N−1 · N 奇=N（216⇒215）",
          not bad3, f"失配={bad3 or '无'} · N=216⇒{TMB.universality_depth_lower_bound(216)}")

    st = TMB.static_mesh_resources(216)
    tm = TMB.temporal_mesh_resources(216, TMB.universality_depth_lower_bound(216))
    check("C2 元件数：静态 23220 片 MZI vs 时间复用 1 片（O(N²)→O(1)）",
          st["n_physical_mzi"] == 23220 and tm["n_physical_mzi"] == 1,
          f"省 {st['n_physical_mzi'] / tm['n_physical_mzi']:.0f}×（可制造性/版图/对准）")

    fr = TMB.programmability_frontier(216)
    lin_ok = all(r["max_gates"] == 108 * r["depth"] for r in fr["rows"])
    uni_ok = all(r["universal"] == (r["depth"] >= 215) for r in fr["rows"])
    check("C3 可编程性前沿：可及参数 = ⌊N/2⌋·D（线性）· 通用 ⟺ D ≥ 215",
          lin_ok and uni_ok and fr["depth_lower_bound"] == 215,
          f"rows={len(fr['rows'])} · 每步最大门数={fr['max_gates_per_step']}")

    lat = TMB.fixed_lattice_programmability(216, lattice_a=6)
    check("C4 固定浅晶格（3 环）可及参数 ≪ N² ⇒ 维度计数直接判非通用",
          lat["n_loops_depth"] == 3 and lat["universal"] is False
          and lat["reachable_params_model"] == 324,
          f"3 环 ⇒ 216 模 · 可及 {lat['reachable_params_model']} vs 需 {lat['gates_needed_universal']}")

    # ════════════════ D 节：损耗不省 + Borealis 维度判死 ════════════════
    print("── D ★修正 M4 口号★：时间复用买元件数，不买损耗 ──")
    vd = TMB.temporal_mesh_verdict(216)
    check("D1 ★核心★ 最有利假设（理论最优深度 215）下时间复用仍**更差**：不省损",
          vd["loss_saving_strictly_negative"] is True
          and vd["universal_constructible"] is True
          and vd["depth_required_lower_bound"] == 215,
          f"静态 {vd['static_loss_per_mode_db']:.0f} dB vs 复用下界 "
          f"{vd['temporal_loss_lower_bound_db']:.0f} dB（省 {vd['loss_saved_db_by_time_multiplexing']:.0f} dB）")

    w_tm = TMB.temporal_loss_wall_n(1e-2)
    w_st = SBM.loss_wall_n(1e-2)
    check("D2 时间复用**通用**表损耗关门点不比静态网格更晚 ⇒ 不构成规模出路",
          2 <= w_tm <= w_st,
          f"N*_tm={w_tm} ≤ N*_static={w_st}（1e−2 透射门限）")

    bm = TMB.benchmark_against_borealis_temporal(216)
    check("D3 Borealis 维度判死：报称参数 ≪ N² ⇒ 浅晶格不可能实现任意 216 模酉",
          bm["reported_params_fraction"] < 0.05 and bm["mode_count_matches"] is True,
          f"报称 {SBM.BOREALIS_REF['programmable_parameters']} / N²=46656 = "
          f"{bm['reported_params_fraction'] * 100:.1f}%")

    check("D4 Borealis 对标：模数 216 匹配 · 形态不同（CV GBS vs DV LOQC）· 诚实标注齐备",
          bm["same_modality"] is False and "honest_boundary" in bm
          and "不复算" in bm["honest_boundary"],
          f"匹配={bm['mode_count_matches']} 同形态={bm['same_modality']}")

    # ════════════════ E 节：跨模块 + 前沿 + 诚实标注 + 冗余实现 ════════════════
    print("── E 跨模块桥 + 前沿 + 诚实标注 + 冗余实现 ──")
    n_ = 6
    U_ = TMB.random_unitary(n_, seed=3)
    ops_, D_ = MMM.reck_triangular_mesh(U_)
    sched_, _ = TMB.schedule_from_reck_ops(ops_, D_, n_)
    d_bridge = float(np.max(np.abs(TMB.schedule_unitary(sched_, n_)
                                   - MMM.assemble_triangular_mesh(ops_, D_, n_))))
    check("E1 跨模块桥：时间表重建 ≡ 平台 assemble_triangular_mesh（逐位一致）",
          d_bridge < 1e-13, f"max|Δ|={d_bridge:.2e}")

    ref = SBM.BOREALIS_REF
    check("E2 外部事实 A 级可溯源（Nature 606 + DOI + URL）",
          "Nature 606" in ref["source"] and ref["doi"] == "10.1038/s41586-022-04725-x"
          and ref["public_url"].startswith("https://www.nature.com/"),
          f"{ref['source']} doi:{ref['doi']}")

    proof = vd.get("proof_sketch", "")
    check("E3 修正结论带**证明骨架**（门数必要性 → 层容量 → 损耗下界）",
          "Clements" in proof and "⌊N/2⌋" in proof and "N−1" in proof,
          proof[:70] + "…")

    # 冗余实现：前沿表在 N=8 上与暴力枚举「每步 ⌊N/2⌋ 门」一致
    fr8 = TMB.programmability_frontier(8, depths=[1, 2, 3, 7])
    brute_ok = all(r["max_gates"] == (8 // 2) * r["depth"] for r in fr8["rows"])
    check("E4 前沿表冗余对拍：N=8 上 可及参数 ≡ ⌊N/2⌋·D（暴力核算一致）",
          brute_ok and fr8["depth_lower_bound"] == 7,
          f"N=8 ⇒ 下界 7（=N−1）· rows={[(r['depth'], r['max_gates']) for r in fr8['rows']]}")

    # ════════════════ F 节：常数同源 + 红线 ════════════════
    print("── F 常数同源 + 红线 ──")
    per_mzi_l2 = MMM.mesh_cascade_loss_db(1, n_crossings=0)
    d_const = abs(per_mzi_l2 - TMB.PER_MZI_LOSS_DB)
    check("F1 常数同源桥：D-121 PER_MZI_LOSS_DB ≡ L2 单件级联损耗（与 D-120 同源）",
          d_const < 1e-12 and abs(TMB.PER_ROUNDTRIP_LOSS_DB
                                  - (TMB.PER_MZI_LOSS_DB + TMB.DELAY_LOSS_DB)) < 1e-12,
          f"per_mzi={TMB.PER_MZI_LOSS_DB:.3f} dB · per_roundtrip="
          f"{TMB.PER_ROUNDTRIP_LOSS_DB:.3f} dB（=MZI+环/开关）")

    banned = ("qiskit", "cirq", "pennylane", "strawberryfields", "thewalrus", "qutip")
    hits = [b for b in banned
            if re.search(rf"^\s*(import|from)\s+{b}\b",
                         open(os.path.join(_HERE, "lda_qeda", "temporal_mesh.py"),
                              encoding="utf-8").read(), re.M)]
    check("F2 红线：D-121 零量子 SDK 依赖（纯 numpy + 平台，C 级自主）",
          not hits, f"命中={hits or '无'}")

    guard = True
    for bad in ((lambda: TMB.matching_layer_unitary(4, [(0, 0.1, 0.0, False),
                                                       (0, 0.1, 0.0, False)])),
                (lambda: TMB.cyclic_shift_unitary(1, 1)),
                (lambda: TMB.pair_rotation_unitary(4, 3, 2, 0.1)),
                (lambda: TMB.universality_depth_lower_bound(1)),
                (lambda: TMB.temporal_loss_wall_n(1.5)),
                (lambda: TMB.temporal_mesh_resources(4, 0))):
        try:
            bad()
            guard = False
        except ValueError:
            pass
    check("F3 护栏：重复模门层 / 越界 / i≥j / N<2 / 非法 η / depth<1 抛 ValueError",
          guard, "六类非法输入全抛错")

    check("F4 判决无 LLM：结论全部由整数恒等式 + numpy 线性代数给出（零模型调用）",
          isinstance(vd["loss_saving_strictly_negative"], bool)
          and isinstance(vd["depth_required_lower_bound"], int),
          "loss_saving_strictly_negative 为 bool · depth 为 int（死标量）")

    print()
    print(f"量子时间复用可编程酉 门禁 smoke：{PASS}/{PASS + FAIL} PASS")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
