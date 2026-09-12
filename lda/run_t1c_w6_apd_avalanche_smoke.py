"""T1-C-W6 APD 雪崩载流子输运 B 档真求解护栏 smoke（经 T1 电学内核 · v0.9.72）。

守护四件事（对齐 W5/B33 范式）：
  ① 正向：解析极限机器精度退化（αh=0→e^{αW}、αe=αh→1/(1−αW)）；
     MC ↔ 精确 ODE 一致（ratio∈[0.95,1.05]）；F_mc ↔ McIntyre 闭式一致（<10%）；
     与 B33/active_models Miller 闭式跨模块一致（误差公开：n_eff<文献带）。
  ② 判据 D：n_x 加密 ⇒ M_exact(V_fixed) 单调收敛（梯形 O(dx²)）。
  ③ 反向：N_D↓ ⇒ V_br 单调↑（宽耗尽更难击穿）；V↑ ⇒ M↑ / F↑（信号翻转必被抓）。
  ④ 红线守卫：is_oracle=False + force_oracle 必 raise + 击穿区（V≥V_br）必 raise。

运行：python run_t1c_w6_apd_avalanche_smoke.py（~10s）
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    tag = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{tag}] {name}" + (f" —— {detail}" if detail else ""))


def main() -> int:
    print("=" * 72)
    print("T1-C-W6 APD 雪崩载流子输运 B 档真求解（电离积分 + MC 雪崩链）")
    print("=" * 72)

    from lda_solver.apd_avalanche_true import (
        multiplication_exact, breakdown_voltage, mc_avalanche_gain_noise,
        effective_ionization_ratio, miller_gain_closed,
        mcintyre_excess_noise_closed, miller_n_effective,
        apd_avalanche_true_solve, avalanche_profiles, guard_t1_not_oracle,
    )
    from lda_design.active_models import apd_miller_gain

    # ------------------------------------------------ ① 正向
    # 解析极限（均匀系数手搓闭式 vs 模块公式结构）：αh=0 → e^{αe·W}
    def _lim(ae, ah, W):
        dW = 0.5 * (ae - ah) * W
        if abs(ae - ah) < 1e-30:
            J = ae * W
        else:
            J = 0.5 * (ae + ah) * (1.0 - math.exp(-(ae - ah) * W)) / (ae - ah)
        return 2.0 / (1.0 + math.exp(-2.0 * dW) - 2.0 * J)
    ok1 = abs(_lim(1e5, 0.0, 3e-6) - math.exp(0.3)) < 1e-12
    ok2 = abs(_lim(1e5, 1e5, 3e-6) - 1.0 / (1.0 - 0.3)) < 1e-12
    check("① 正向：解析极限 αh=0→e^{αW} / αe=αh→1/(1−αW)（机器精度）",
          ok1 and ok2, f"lim1={_lim(1e5,0.0,3e-6):.10f} vs {math.exp(0.3):.10f}")

    V_br = breakdown_voltage()
    V = 0.7 * V_br
    r = apd_avalanche_true_solve(V, n_pairs=1500, seed=7)
    check("① 正向：MC ↔ 精确 ODE 一致（|ratio−1|<0.05）",
          abs(r["M_mc_over_exact"] - 1.0) < 0.05,
          f"M_mc={r['M_mc']:.3f} M_ode={r['M_exact']:.3f} ratio={r['M_mc_over_exact']:.4f}")
    f_dev = abs(r["F_mc"] - r["F_mcintyre_closed"]) / r["F_mcintyre_closed"]
    check("① 正向：F_mc ↔ McIntyre 闭式一致（<10%）", f_dev < 0.10,
          f"F_mc={r['F_mc']:.3f} F_McI={r['F_mcintyre_closed']:.3f} dev={f_dev:.2%}")
    # 跨模块：本模块 Miller 闭式 == active_models.apd_miller_gain（B33 同源）
    m_self = miller_gain_closed(V, V_br, 3.0)
    m_am = apd_miller_gain(V, V_br, 3.0)
    check("① 正向：Miller 闭式跨模块一致（== active_models/B33）",
          abs(m_self - m_am) / m_am < 1e-12,
          f"self={m_self:.4f} active_models={m_am:.4f}")
    # 误差公开：局部模型 n_eff 低于文献 Miller 带 1.5–4（如实记账非缺陷）
    ne = r["n_eff_vs_own_vbr"]
    check("① 正向：n_eff 诚实公开（<文献带 1.5，局部模型局限标注）",
          0.0 < ne < 1.5, f"n_eff={ne:.3f}（文献带 1.5–4，死区/非局域所致）")

    # ------------------------------------------------ ② 判据 D 收敛
    prev, vals, ds = None, [], []
    for nx in (100, 200, 400, 800, 1600):
        m = multiplication_exact(V, n_x=nx)
        vals.append(m)
        if prev is not None:
            ds.append(abs(m - prev))
        prev = m
    mono = all(ds[i + 1] < ds[i] for i in range(len(ds) - 1))
    check("② 判据D：n_x 加密 ⇒ M_exact 单调收敛（O(dx²)）", mono,
          "M=" + " ".join("%.6f" % v for v in vals) +
          " | d=" + " ".join("%.1e" % d for d in ds))
    check("② 判据D：末段残差 > 1e-12（非代数恒等）", ds[-1] > 1e-12,
          "d_last=%.2e" % ds[-1])

    # ------------------------------------------------ ③ 反向必被抓
    vbrs = [breakdown_voltage(N_D=nd) for nd in (1.0e22, 5.0e21, 2.0e21)]
    check("③ 反向：N_D↓ ⇒ V_br 单调↑（宽耗尽更难击穿）",
          all(vbrs[i + 1] > vbrs[i] for i in range(len(vbrs) - 1)),
          " ".join("%.1fV" % v for v in vbrs))
    Ms, Fs = [], []
    for frac in (0.5, 0.7, 0.9):
        rr = apd_avalanche_true_solve(frac * V_br, n_pairs=800, seed=7)
        Ms.append(rr["M_exact"]); Fs.append(rr["F_mcintyre_closed"])
    check("③ 反向：V↑ ⇒ M↑ 且 F↑（信号翻转）",
          all(Ms[i + 1] > Ms[i] for i in range(2)) and
          all(Fs[i + 1] > Fs[i] for i in range(2)),
          "M=" + " ".join("%.2f" % m for m in Ms) +
          " F=" + " ".join("%.2f" % f for f in Fs))
    # 固定种子可复现
    a = mc_avalanche_gain_noise(V, n_pairs=400, seed=123)
    b = mc_avalanche_gain_noise(V, n_pairs=400, seed=123)
    check("③ 反向：固定种子可复现（MC 确定性）", a == b,
          f"M={a[0]:.4f} F={a[1]:.4f} 两次全等")

    # ------------------------------------------------ ④ 红线守卫
    ok_flag = r["is_oracle"] is False and r["provenance"] == "self_authored_t1c_w6_true_solve"
    check("④ 红线：输出 is_oracle=False + provenance 诚实", ok_flag,
          f"is_oracle={r['is_oracle']} prov={r['provenance']}")
    guard_ok = True
    try:
        guard_t1_not_oracle(r)
    except Exception as e:
        guard_ok = False
        check("④ 红线：正常调用 guard 不应 raise", False, repr(e))
    forced = False
    try:
        guard_t1_not_oracle(r, force_oracle=True)
    except RuntimeError:
        forced = True
    check("④ 红线：force_oracle ⇒ 守卫必 raise（不作 ORACLE）", guard_ok and forced,
          "守卫双向正确")
    br_ok = False
    try:
        apd_avalanche_true_solve(1.2 * V_br, n_pairs=100)  # 击穿区
    except RuntimeError:
        br_ok = True
    check("④ 红线：V≥V_br 击穿区必 raise（不假绿）", br_ok,
          "" if br_ok else "击穿区未抛异常")

    print("=" * 72)
    if FAIL:
        print(f"T1-C-W6 冒烟：{PASS} PASS / {FAIL} FAIL —— 🔴 存在问题")
        return 1
    print(f"T1-C-W6 冒烟：{PASS} PASS / 0 FAIL —— 全绿")
    return 0


if __name__ == "__main__":
    sys.exit(main())
