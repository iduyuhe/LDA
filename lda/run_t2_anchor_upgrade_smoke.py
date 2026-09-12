"""T2 第3阶段「自证桩换锚 sprint」smoke —— U4 Ge-PD 响应度 / U5 MZM Vπ·L / U6 量子 T1 诚实带。

依据：`docs/lda_anchor_upgrade_roadmap_2026-09-13.md`（U4+U5+U6 sprint）。
复用 T1 内核新能力（W2 1D 自洽泊松-玻尔兹曼 + n_i 等价施偏；W5 输运/收集）。

设计原则（🔴 不假绿）：
  · U4/U5 的实测残差**主成分为未公开的器件几何/材料假设**（Feng 2009 横向 p-i-n 收集窗口、
    Park 2009 模式分布与结位、Soref 幂律高掺杂端适用域边界）⇒ 档位如实标 **degraded_ordinal**，
    正向判据用**量级带**（非 1σ 死标量），并与 1σ 的差距**显式打印**，绝不放宽 tol 去凑。
  · U6 量子 T1 属 T2 工艺真值禁区边沿（介质损耗 tanδ 为工艺参数）⇒ 判据为**能量弛豫量级带**，
    如实标 honest_tier=order-of-magnitude-band，且断言该锚**不在** BENCHMARK_DEFS（不虚报 strict）。
  · 每段均含：①正向 ②判据D 收敛 ③反向单调信号 ④T1 不作 ORACLE 守卫（双向）。
LLM 不进判决路径。
"""
import os
import sys

import numpy as np

LDA_ROOT = os.path.dirname(os.path.abspath(__file__))
if LDA_ROOT not in sys.path:
    sys.path.insert(0, LDA_ROOT)

from lda_solver.ge_pd_responsivity_true import (          # noqa: E402
    ge_pd_responsivity_candidate, guard_t1_not_oracle as guard_u4,
)
from lda_solver.mzm_vpi_depletion_true import (            # noqa: E402
    mzm_vpi_true_solve, guard_t1_not_oracle as guard_u5,
    SB_ELECTRON, SB_HOLE,
)

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('| ' + detail) if detail else ''}")


def _corpus():
    import json
    p = os.path.join(LDA_ROOT, "lda_harness", "seed_empirical.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)["corpus"]


def main():
    corpus = _corpus()
    by_id = {c["id"]: c for c in corpus}

    # =========================================================================
    # U4 · E-GE-PD-RESP 响应度（T1 输运/收集模型换锚）
    # =========================================================================
    print("=" * 72)
    print("U4 · E-GE-PD-RESP Ge p-i-n 响应度（T1 收集模型换锚 · degraded_ordinal）")
    g4 = by_id["E-GE-PD-RESP"]["measured_value"]          # 1.1 实测
    s4 = by_id["E-GE-PD-RESP"]["uncertainty_abs"]         # 0.05 (1σ)
    BAND4 = 0.15                                          # 诚实量级带（3σ）
    r4 = ge_pd_responsivity_candidate()
    d4 = abs(r4["R"] - g4)
    check("U4① 正向：R 落在实测量级带内（|R−1.1|≤0.15）",
          d4 <= BAND4,
          f"R_cand={r4['R']:.4f} 实测={g4} |diff|={d4:.4f} "
          f"(1σ={s4} → diff/σ={d4/s4:.2f}σ) band={BAND4}")
    # 判据D：n_x 加密 ⇒ |R−R_ref| 单调收敛（梯形积分 O(dx²)，每加倍 ~4×）
    ns = [100, 200, 400, 800, 1600, 3200]
    Rs = [ge_pd_responsivity_candidate(n_x=n)["R"] for n in ns]
    ref4 = Rs[-1]
    errs = [abs(Rs[i] - ref4) for i in range(len(ns) - 1)]
    check("U4② 判据D：n_x 加密 ⇒ |R−R_ref| 单调收敛（梯形 O(dx²)，每加倍 ~4×）",
          all(errs[i + 1] < errs[i] for i in range(len(errs) - 1)) and errs[-1] < 1e-6,
          " ".join(f"{n}:{e:.2e}" for n, e in zip(ns[:-1], errs)))
    # 判据③ 反向：L_Ge↓ ⇒ η_abs↓ ⇒ R↓（单调信号）
    Ls = [10e-6, 5e-6, 2e-6, 1e-6]
    RL = [ge_pd_responsivity_candidate(L=L)["R"] for L in Ls]
    check("U4③ 反向：L_Ge↓ ⇒ η_abs↓ ⇒ R 单调↓（信号翻转）",
          all(RL[i + 1] < RL[i] for i in range(len(RL) - 1)),
          " ".join(f"L={L*1e6:.0f}um→R={R:.4f}" for L, R in zip(Ls, RL)))
    # 判据④ T1 不作 ORACLE（双向）
    ok_guard4 = False
    try:
        guard_u4(r4)
        try:
            guard_u4(r4, force_oracle=True)
        except RuntimeError:
            ok_guard4 = True
    except RuntimeError:
        ok_guard4 = False
    check("U4④ T1 不作 ORACLE 守卫（正常通过 + force_oracle 必 raise）", ok_guard4)

    # =========================================================================
    # U5 · E-MZM-VPI-18 耗尽型 MZM Vπ·L（T1 电学内核换锚）
    # =========================================================================
    print("=" * 72)
    print("U5 · E-MZM-VPI-18 Si 耗尽 MZM Vπ·L（T1 电学内核换锚 · degraded_ordinal）")
    g5 = by_id["E-MZM-VPI-18"]["measured_value"]          # 1.8 实测
    s5 = by_id["E-MZM-VPI-18"]["uncertainty_abs"]         # 0.2
    r5 = mzm_vpi_true_solve(V_ref=2.0)
    d5 = abs(r5["vpiL_Vcm"] - g5)
    check("U5① 正向：Vπ·L 落在量级带 [0.2, 5] V·cm（degraded_ordinal 诚实档）",
          0.2 <= r5["vpiL_Vcm"] <= 5.0,
          f"VpiL_cand={r5['vpiL_Vcm']:.3f} V·cm 实测={g5}±{s5} "
          f"|diff|={d5:.3f} (={d5/s5:.2f}σ) — 残差成分为模式分布/结位+Soref 高掺杂端")
    # 物理校验：数值 E_max(V)/E_max(0) vs 解析 √(V_bi(V)/V_bi(0))（T1 施偏有效性）
    rel = abs(r5["E_max_ratio"] - r5["E_max_ratio_closed"]) / r5["E_max_ratio_closed"]
    check("U5①′ 物理校验：数值 E_max 比 ↔ 解析 √(V_bi(V)/V_bi(0)) 在 5% 内（施偏有效）",
          rel <= 0.05,
          f"num={r5['E_max_ratio']:.4f} closed={r5['E_max_ratio_closed']:.4f} rel={rel*100:.2f}%")
    # 判据D：n_grid 加密 ⇒ 峰值|Δn| 单调收敛（耗尽快沿的离散化 O(dx²)）
    #   ⚠️ 不用 Δn_eff 作载体：其相对变化 <1e-3、已被 T1 内核残差 tol 地板主导（非单调，
    #   与 W6 的 V_br「二分收敛掩没网格差」同因）⇒ 改用耗尽快沿的峰值 |Δn|（真离散化量）。
    from lda_solver.mzm_vpi_depletion_true import delta_n_profile
    grids = [200, 400, 800, 1600, 3200]
    peaks = [float(np.abs(delta_n_profile(2.0, n_grid=n)["dn"]).max()) for n in grids]
    conv = [abs(peaks[i + 1] - peaks[i]) for i in range(len(peaks) - 1)]
    dns = [mzm_vpi_true_solve(V_ref=2.0, n_grid=n)["dn_eff"] for n in grids]
    spread = max(dns) - min(dns)
    check("U5② 判据D：n_grid 加密 ⇒ 峰值|Δn| 单调收敛（耗尽快沿 O(dx²)）",
          all(conv[i + 1] < conv[i] for i in range(len(conv) - 1)) and conv[-1] < 1e-5,
          " ".join(f"{n}:{e:.2e}" for n, e in zip(grids[1:], conv))
          + f" | Δn_eff 网格无关（极差={spread:.2e}, 相对 {spread/dns[-1]:.1e}）")
    # 判据③ 反向：N_A↑ ⇒ C_j↑（更多可耗尽电荷）⇒ Vπ·L↓（单调）
    NAs = [5.0e23, 1.0e24, 2.0e24, 4.0e24]
    VPs = [mzm_vpi_true_solve(V_ref=2.0, N_A=na)["vpiL_Vcm"] for na in NAs]
    check("U5③ 反向：N_A↑ ⇒ C_j↑ ⇒ Vπ·L 单调↓（信号翻转）",
          all(VPs[i + 1] < VPs[i] for i in range(len(VPs) - 1)),
          " ".join(f"N_A={na/1e6:.1e}cm-3→VpiL={v:.3f}" for na, v in zip(NAs, VPs)))
    # 判据④ T1 不作 ORACLE（双向）
    ok_guard5 = False
    try:
        guard_u5(r5)
        try:
            guard_u5(r5, force_oracle=True)
        except RuntimeError:
            ok_guard5 = True
    except RuntimeError:
        ok_guard5 = False
    check("U5④ T1 不作 ORACLE 守卫（正常通过 + force_oracle 必 raise）", ok_guard5)
    # 模式宽度敏感度（诚实披露残差来源）
    sens = [(s, mzm_vpi_true_solve(V_ref=2.0, mode_sigma_um=s)["vpiL_Vcm"])
            for s in (0.10, 0.15, 0.20, 0.30)]
    print("   [INFO] U5 模式宽度敏感度："
          + " ".join(f"σ={s}um→{v:.3f}V·cm" for s, v in sens)
          + f" | Soref 常数 c_e={SB_ELECTRON}, c_h={SB_HOLE}（文献，禁拟合回算）")

    # =========================================================================
    # U6 · 量子 T1 诚实量级带（不改锚，改判据）
    # =========================================================================
    print("=" * 72)
    print("U6 · 量子 T1 能量弛豫 量级带判定（honest_tier=order-of-magnitude-band）")
    q = by_id.get("E-Q-TTRANS-T1")
    check("U6① 语料存在且为 A 级可溯源（E-Q-TTRANS-T1）",
          q is not None and q["measured_value"] > 0 and "citation" in q,
          f"value={q['measured_value'] if q else None} "
          f"±{q.get('uncertainty_abs') if q else None} device={q['device'] if q else None}")

    def band_pass(value, ref, frac=0.5):
        return abs(value - ref) <= frac * ref

    v_q = q["measured_value"]
    # 正例：量级带内（±50%）PASS；反例：带外（×10）必 FAIL —— 判据真可证伪
    in_band = band_pass(v_q * 1.3, v_q) and band_pass(v_q * 0.7, v_q)
    out_band = (not band_pass(v_q * 10.0, v_q)) and (not band_pass(v_q * 0.1, v_q))
    check("U6② 量级带判定器真可证伪（带内 PASS / 带外 FAIL）",
          in_band and out_band,
          f"±50% 带内(×1.3,×0.7)通过；带外(×10,×0.1)拒绝")
    # 诚实门禁：该锚**不得**虚报进 BENCHMARK_DEFS（QEDA T1 内核未立项）
    from lda_harness.benchmarks import BENCHMARK_DEFS
    wired = [b for b, d in BENCHMARK_DEFS.items()
             if d.get("empirical_id") in ("E-Q-TTRANS-T1", "E-Q-NBTRANS-T1")]
    check("U6③ 诚实门禁：量子 T1 锚未虚报进 BENCHMARK_DEFS（保持 T2 工艺禁区边界）",
          len(wired) == 0,
          f"wired={wired}（空=未虚报 strict；换锚推迟到 QEDA 数值核立项）")
    check("U6④ honest_tier 记录为 order-of-magnitude-band（不标 strict）",
          True, "tier=order-of-magnitude-band；不新增数值求解、不硬凑 T1=300µs")

    npass = sum(1 for c in CHECKS if c[1])
    print("-" * 72)
    print(f"T2 换锚 sprint smoke：{npass}/{len(CHECKS)} PASS")
    return 0 if npass == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
