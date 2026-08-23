"""D-78 光栅耦合器端口验收 smoke：3 项（正例 / 无调制 FAIL / 非法参数 FAIL）。"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = 0
FAIL = 1


def run(name: str, expect: bool, **kw) -> bool:
    t0 = time.time()
    try:
        from lda_agent.gc_design import design_gc
        rep = design_gc(**kw)
        got = bool(rep["acceptance"]["passed"])
        ok = got == expect
        tag = "PASS" if ok else "FAIL"
        print(f"[{tag}] {name} (expect={expect}, got={got}, {time.time()-t0:.0f}s)")
        if not ok:
            print("      verdict:", rep.get("verdict", "")[:160])
        return ok
    except Exception as e:  # noqa: BLE001
        ok = (not expect) and ("非法" in name or "无调制" in name)
        tag = "PASS" if ok else "FAIL"
        print(f"[{tag}] {name} (异常: {str(e)[:100]})")
        return ok


def main() -> int:
    results = []
    # 正例：GC 验收全过（谷检出 + 光栅方程位置对拍 + Λ 趋势锚）
    results.append(run("GC 端口验收 + 光栅方程 ORACLE", True,
                       gc={"width": 0.5, "Lambda": 0.68, "duty": 0.55,
                           "n_tooth": 12, "n_wl": 9}))
    # 负例：duty=1.0（无凹槽=直波导，无周期调制 → 无谷 → 应 FAIL）
    results.append(run("duty=1.0 无周期调制（应 FAIL）", False,
                       gc={"width": 0.5, "Lambda": 0.68, "duty": 1.0,
                           "n_tooth": 12, "n_wl": 7}))
    # 负例：非法参数（Lambda=0 → 除零/异常 → 应优雅 FAIL）
    results.append(run("Lambda=0 非法参数（应 FAIL）", False,
                       gc={"width": 0.5, "Lambda": 0.0, "n_wl": 3}))
    passed = sum(results)
    print(f"\nD-78 smoke: {passed}/{len(results)} PASS")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
