"""LDA · D-38 agent 逆设计通用框架落地 smoke。

验证 SpectrumInverseDesignAgent（D-24）经声明式注册表落地到 4 个真实器件，
全部 accepted —— 证明"跨场景复用、非单点 hack"：
  RingResonator（光子/match/黄金分割）· BraggMirror（光子/threshold/离散+TMM 搜索
  FDTD 终验）· Transmon（量子/match）· RingAddDrop（D-37 器件/match/Q_L）。
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from lda_agent.inverse_design import run_inverse_design  # noqa: E402

EXPECT = {
    "RingResonator": ("R_um", "match"),
    "BraggMirror": ("periods", "threshold"),
    "Transmon": ("E_J", "match"),
    "RingAddDrop": ("gap", "match"),
}


def main() -> int:
    ok = True
    results = {}
    print("=" * 70)
    print("D-38 agent 逆设计通用框架落地（同一 SpectrumInverseDesignAgent 派发）")
    print("=" * 70)
    for kind, (param, mode) in EXPECT.items():
        r = run_inverse_design(kind)
        acc = r.get("accepted")
        fp = r.get("final_params", {})
        me, mth = r.get("metric_err"), r.get("method_err")
        print(f"[{'OK  ' if acc else 'FAIL'}] {kind:<14} param={fp} "
              f"({param},{mode}) metric_err={me} method_err={mth} "
              f"accepted={acc} {r.get('elapsed_s')}s")
        ok &= bool(acc)
        ok &= bool(fp.get(param) is not None)
        results[kind] = {"accepted": acc, "final_params": fp}
        # 未达标即打印判决帮助定位
        if not acc:
            print("    verdict:", r.get("verdict"))
    print("=" * 70)
    print("全部 4 器件经同一框架 accepted:", ok)
    with open(os.path.join(_HERE, "reports", "inverse_design_d38.json"), "w",
              encoding="utf-8") as f:
        json.dump({"framework": "SpectrumInverseDesignAgent (D-24/D-38)",
                   "all_passed": ok, "devices": results},
                  f, ensure_ascii=False, indent=2)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
