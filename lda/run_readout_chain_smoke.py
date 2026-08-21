"""LDA · D-43 光子-量子混合链路（芯片级 dispersive readout）smoke。

验证「qubit ↔ readout 谐振器 ↔ 读出力线」系统闭环：
  1. 默认 5GHz qubit / Δ=1GHz / g=0.1 → 三器件双验证 + JC 精确对角化自洽 PASS
  2. 变体（不同 f01/Δ/g/κ_r）均 PASS
  3. 混合 IR 网表（domain=hybrid）校验通过
  4. 负例：色散区失效（Δ/g<5）或读出不可分辨（χ<κ_r）→ 系统正确拒绝
LLM 不进判决路径。
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from lda_agent.qubit_readout_chain import design_chain  # noqa: E402

CASES = [
    (dict(f01=5.0, delta=1.0, g=0.10, kappa_r=0.005), True),
    (dict(f01=4.5, delta=1.5, g=0.12, kappa_r=0.004), True),
    (dict(f01=6.0, delta=1.0, g=0.08, kappa_r=0.003), True),
    (dict(f01=5.0, delta=0.2, g=0.10, kappa_r=0.005), False),  # Δ/g=2 <5 色散失效
    (dict(f01=5.0, delta=1.0, g=0.02, kappa_r=0.005),
     False),   # χ=g²/Δ=0.4MHz < κ_r=5MHz 读出不可分辨
]


def main() -> int:
    ok = True
    print("=" * 70)
    print("D-43 光子-量子混合链路（芯片级 dispersive readout）")
    print("=" * 70)
    for kw, expect in CASES:
        r = design_chain(**kw)
        got = bool(r["acceptance"]["passed"])
        good = (got == expect)
        ok &= good
        p = r["params"]
        v = r["verification"]
        print(f"[{'OK  ' if good else 'FAIL'}] f01={kw['f01']} Δ={kw['delta']} "
              f"g={kw['g']} κ_r={kw['kappa_r']} (期望 {'PASS' if expect else 'FAIL'}): "
              f"E_J={p['E_J']} l={p['l_m']*1e3:.2f}mm Cc={p['Cc']} Q_ext={p['Q_ext']} | "
              f"JC χ rel={v['jc']['chi_rel_err']:.1%} | "
              f"实际 {'PASS' if got else 'FAIL'}")
        for c in r["acceptance"]["checks"]:
            if not c["ok"]:
                print("    ✗", c["name"], "：", c["detail"])
    print("=" * 70)
    print("D-43 smoke 全绿:", ok)
    r0 = design_chain(**CASES[0][0])
    with open(os.path.join(_HERE, "reports", "readout_chain.json"), "w",
              encoding="utf-8") as f:
        json.dump({k: r0[k] for k in ("title", "f01_ghz", "f_r_ghz", "params",
                                      "verification", "ir", "acceptance",
                                      "verdict")},
                  f, ensure_ascii=False, indent=2)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
