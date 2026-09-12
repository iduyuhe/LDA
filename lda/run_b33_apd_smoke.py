"""B33-APD 探测器带宽锚 · APD 闭式倍增扩展护栏 smoke（T1-C W1 · v0.9.69）。

守护四件事：
  ① 正向：golden 闭式(Miller √M 折减) 与 candidate 数值积分 一致（残差 ≪ tol）
  ② 判据 D：n_time 加密 → candidate 拟合残差单调收敛（真数值离散化，非代数恒等）
  ③ 反向：V_bias 升高 ⇒ M↑ ⇒ 带宽↓（信号翻转必被抓）
  ④ 红线守卫：V_bias ≥ V_br 必 raise（雪崩击穿区不可宣称 ORACLE）；APD 带宽 < PIN 带宽

运行：python run_b33_apd_smoke.py（~3s）
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
    print("B33-APD 探测器 APD 带宽锚（Miller 增益 · 闭式倍增扩展）")
    print("=" * 72)

    from lda_harness.b33_detector_bandwidth_anchor import (
        b33_detector_bandwidth,
        b33_apd_bandwidth,
        b33_apd_bandwidth_candidate,
    )

    R, eps, A, d = 50.0, 1.036e-10, 9.653e-9, 1.0e-6
    V_bias, V_br, n = 22.0, 25.0, 3.0

    # ------------------------------------------------ ① 正向
    g = b33_apd_bandwidth(R, eps, A, d, V_bias, V_br, n)
    c = b33_apd_bandwidth_candidate(R, eps, A, d, V_bias, V_br, n, n_time=4000)
    rel = abs(c - g) / g
    check("① 正向：golden 闭式 ≒ candidate 数值", rel < 0.02,
          f"gold={g:.6e} cand={c:.6e} 残差={rel:.2%}")

    # ------------------------------------------------ ② 判据 D 单调收敛
    grids = (200, 400, 800, 1600, 3200)
    errs = []
    for nt in grids:
        cc = b33_apd_bandwidth_candidate(R, eps, A, d, V_bias, V_br, n, n_time=nt)
        errs.append(abs(cc - g) / g)
    mono = all(errs[i + 1] <= errs[i] for i in range(len(errs) - 1))
    check("② 判据D：残差随 n_time 单调非增（真独立）", mono,
          " ".join("%.1e" % e for e in errs))
    check("② 判据D：基线残差 > 1e-12（非代数恒等）", errs[-1] > 1e-12,
          "res=%.2e" % errs[-1])

    # ------------------------------------------------ ③ 反向必被抓
    g_lo = b33_apd_bandwidth(R, eps, A, d, V_bias * 0.95, V_br, n)
    g_hi = b33_apd_bandwidth(R, eps, A, d, V_bias * 1.05, V_br, n)
    check("③ 反向：V_bias↑ ⇒ M↑ ⇒ 带宽↓（信号翻转）", g_hi < g_lo,
          f"V×0.95={g_lo / 1e9:.4f}GHz → V×1.05={g_hi / 1e9:.4f}GHz")

    # ------------------------------------------------ ④ 红线守卫
    guard_ok = False
    try:
        b33_apd_bandwidth(R, eps, A, d, V_br, V_br, n)  # V==V_br ⇒ 击穿
    except Exception:
        guard_ok = True
    pin = b33_detector_bandwidth(R, eps, A, d)
    check("④ 红线：V≥V_br 击穿区必 raise（不宣称 ORACLE）", guard_ok,
          "" if guard_ok else "V==V_br 未抛异常")
    check("④ 红线：APD 带宽 < PIN 带宽（折减真实）", g < pin,
          f"APD={g / 1e9:.4f}GHz < PIN={pin / 1e9:.4f}GHz")

    print("=" * 72)
    if FAIL:
        print(f"B33-APD 冒烟：{PASS} PASS / {FAIL} FAIL —— 🔴 存在问题")
        return 1
    print(f"B33-APD 冒烟：{PASS} PASS / 0 FAIL —— 全绿")
    return 0


if __name__ == "__main__":
    sys.exit(main())
