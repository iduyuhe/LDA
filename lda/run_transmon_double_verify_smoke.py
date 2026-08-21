"""LDA L2 · transmon 真实数值物理双验证 smoke（量子域实质推进：Koch ↔ 严格对角化）。

与光子栈 run_ring_double_verify_smoke.py 同构：量子侧用「Koch 解析近似 ↔
Josephson 电路严格数值对角化」两种独立路径交叉验证 f01，零 GPU、纯 numpy
（维度 ≤41）、LLM 不进判决路径。

退出码 0=全绿；非 0=有失败（便于 CI / 自动化）。
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lda_l2"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lda_solver"))

from device_library import DeviceLibrary  # noqa: E402


def main() -> int:
    lib = DeviceLibrary()
    print("=== Transmon 双验证 (Koch 解析 ↔ 严格对角化) ===")

    # contract：Koch 量级物理 + 目标反解可达
    c = lib.verify_transmon(mode="contract")
    print(f"contract: passed={c['passed']} | {c['verdict']}")

    # live：B9 Koch 命中 + 严格对角化自洽
    r = lib.verify_transmon(mode="live")
    ac = r["analytic_contract"]
    num = r["numerical"]
    print(f"live: passed={r['passed']}")
    print(f"  B9 解析契约: target={ac['target_f01_ghz']}GHz -> E_J={ac['ej_hit']} "
          f"(in_bounds={ac['ej_in_bounds']}, hit_err={ac['b9_hit_err']})")
    print(f"  真实对角化: f01_diag={num['f01_diag']}GHz <-> Koch={num['f01_koch']}GHz "
          f"rel={num['rel_err']:.4%} (tol {num['tol_rel']:.0%}, accepted={num['accepted']})")
    print(f"  anharmonicity: diag={num['alpha_diag']} vs -E_C={num['alpha_koch']} "
          f"(rel {num['alpha_rel_err']:.2%}, informational)")
    print(f"  levels_ghz={num['levels_ghz']}")
    print(f"verdict: {r['verdict']}")

    ok = bool(c["passed"] and r["passed"])
    print("\n=== Transmon 双验证 smoke: " + ("ALL GREEN" if ok else "FAIL") + " ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
