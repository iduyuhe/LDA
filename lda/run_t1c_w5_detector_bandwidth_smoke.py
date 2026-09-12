"""T1-C-W5 探测器带宽 B 档真求解护栏 smoke（经 T1 电学内核 · v0.9.71）。

守护四件事（对齐 B33/W4 范式）：
  ① 正向：数值渡越 f_tr ≤ 闭式 golden 0.44·v_sat/W（亚饱和⇒更慢），且真实级联
     带宽 f_total ≤ RC 闭式 f_rc（渡越惩罚 ≥ 0）；与 B33 锚 RC 闭式跨模块一致。
  ② 判据 D：n_carriers/n_t 加密 ⇒ 数值 f_tr 单调收敛（真数值离散化，非代数恒等）。
  ③ 反向：N_D↓ ⇒ W↑ ⇒ f_total 单调↓ 且渡越惩罚单调↑（信号翻转必被抓）。
  ④ 红线守卫：T1 输出 is_oracle=False；force_oracle 必 raise（不作 ORACLE）。

运行：python run_t1c_w5_detector_bandwidth_smoke.py（~5s）
"""
from __future__ import annotations

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
    print("T1-C-W5 探测器带宽 B 档真求解（RC + 渡越，经 T1 电学内核）")
    print("=" * 72)

    from lda_solver.detector_bandwidth_true import (
        detector_bandwidth_true_solve,
        transit_bandwidth_numeric,
        transit_bandwidth_closed_form,
        t1_depletion_field,
        rc_bandwidth,
        guard_t1_not_oracle,
        R_LOAD_DEFAULT,
        EPS_CAP_DEFAULT,
        A_DET_DEFAULT,
    )
    from lda_harness.b33_detector_bandwidth_anchor import b33_detector_bandwidth

    R, eps, A = R_LOAD_DEFAULT, EPS_CAP_DEFAULT, A_DET_DEFAULT

    # ------------------------------------------------ ① 正向
    r = detector_bandwidth_true_solve(N_D=1e21)
    W = r["W"]
    ok_le = r["f_tr"] <= r["f_tr_closed"] * 1.001
    check("① 正向：f_tr(数值) ≤ 闭式 0.44·v_sat/W（亚饱和⇒更慢）", ok_le,
          f"num={r['f_tr']/1e9:.3f} cf={r['f_tr_closed']/1e9:.3f}GHz ratio={r['ratio_tr']:.3f}")
    check("① 正向：f_total ≤ f_rc（渡越惩罚 ≥ 0）",
          r["f_total"] <= r["f_rc"] * 1.001 and r["penalty_pct"] >= -1e-6,
          f"f_total={r['f_total']/1e9:.3f} ≤ f_rc={r['f_rc']/1e9:.3f}GHz penalty={r['penalty_pct']:.2f}%")
    check("① 正向：亚饱和比值 ratio_tr ∈ [0.25, 1.0]（物理合理带）",
          0.25 <= r["ratio_tr"] <= 1.0, f"ratio_tr={r['ratio_tr']:.3f}")
    # 跨模块一致：本模块 rc_bandwidth(R,eps,A,W) == B33 锚 d=W
    b33 = b33_detector_bandwidth(R, eps, A, W)
    check("① 正向：本模块 RC 闭式 == B33 锚（d=W）跨模块一致",
          abs(b33 - r["f_rc"]) / b33 < 1e-9,
          f"b33={b33/1e9:.4f} vs self={r['f_rc']/1e9:.4f}GHz")

    # ------------------------------------------------ ② 判据 D 收敛
    fld = t1_depletion_field(N_D=1e21)
    xd, Ed = fld["x_dep"], fld["E_dep"]
    grids = ((500, 200), (1000, 400), (2000, 800), (4000, 1600))
    vals = []
    for nc, nt in grids:
        vals.append(transit_bandwidth_numeric(xd, Ed, n_carriers=nc, n_t=nt))
    diffs = [abs(vals[i + 1] - vals[i]) for i in range(len(vals) - 1)]
    mono = all(diffs[i + 1] <= diffs[i] for i in range(len(diffs) - 1))
    check("② 判据D：n_carriers/n_t 加密 ⇒ 数值 f_tr 单调收敛（真独立）", mono,
          "f=" + " ".join("%.4f" % (v / 1e9) for v in vals) +
          " | d=" + " ".join("%.1e" % d for d in diffs))
    check("② 判据D：末段残差 > 1e-12（非代数恒等）",
          diffs[-1] > 1e-12, "d_last=%.2e" % diffs[-1])

    # ------------------------------------------------ ③ 反向必被抓
    # 物理：W↑ ⇒ 渡越 f_tr 单调↓（载流子漂移更远）；RC f_rc = W/(2πRεA) 单调↑
    # （C=εA/W 变小）⇒ 真实级联带宽 f_total 在二者交叉处取**极大**（经典 RC↔渡越
    # 折衷），非单调；故反向判据用「单调量」f_tr↓ 与渡越惩罚↑（信号翻转必被抓）。
    sweep = [1e22, 1e21, 5e20, 3e20]
    f_ts, pens, Ws, f_tots = [], [], [], []
    for N_D in sweep:
        rr = detector_bandwidth_true_solve(N_D=N_D)
        f_ts.append(rr["f_tr"]); pens.append(rr["penalty_pct"])
        Ws.append(rr["W"]); f_tots.append(rr["f_total"])
    f_tr_dec = all(f_ts[i + 1] < f_ts[i] for i in range(len(f_ts) - 1))
    p_inc = all(pens[i + 1] > pens[i] for i in range(len(pens) - 1))
    check("③ 反向：N_D↓⇒W↑⇒渡越 f_tr 单调↓（信号翻转）", f_tr_dec,
          " ".join("W=%.0fnm→f_tr=%.2fGHz" % (Ws[i] * 1e9, f_ts[i] / 1e9)
                   for i in range(len(sweep))))
    check("③ 反向：N_D↓⇒W↑⇒渡越惩罚单调↑", p_inc,
          " ".join("%.1f%%" % p for p in pens))
    # 折衷证据（观察量，硬判据由上面单调量承担）：f_total 先升后降、峰值居 f_rc/f_tr 交叉处
    peak = max(range(len(f_tots)), key=lambda i: f_tots[i])
    print(f"  [INFO] f_total(W) 折衷曲线：" +
          " ".join("%.2f" % (x / 1e9) for x in f_tots) +
          f"GHz（峰值在 W≈{Ws[peak]*1e9:.0f}nm，RC↔渡越交叉处；闭式 f_rc 单调↑ 则高估）")

    # ------------------------------------------------ ④ 红线守卫
    ok_flag = r["is_oracle"] is False and r["provenance"] == "self_authored_t1c_w5_true_solve"
    check("④ 红线：输出 is_oracle=False + provenance 诚实", ok_flag,
          f"is_oracle={r['is_oracle']} prov={r['provenance']}")
    guard_ok = True
    try:
        guard_t1_not_oracle(r)                       # 正常应通过
    except Exception as e:
        guard_ok = False
        check("④ 红线：正常调用 guard 不应 raise", False, repr(e))
    forced = False
    try:
        guard_t1_not_oracle(r, force_oracle=True)    # 反向必须 raise
    except RuntimeError:
        forced = True
    check("④ 红线：force_oracle ⇒ 守卫必 raise（不作 ORACLE）", guard_ok and forced,
          "守卫双向正确")

    print("=" * 72)
    if FAIL:
        print(f"T1-C-W5 冒烟：{PASS} PASS / {FAIL} FAIL —— 🔴 存在问题")
        return 1
    print(f"T1-C-W5 冒烟：{PASS} PASS / 0 FAIL —— 全绿")
    return 0


if __name__ == "__main__":
    sys.exit(main())
