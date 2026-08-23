"""D-79 真实基元接入流水线 smoke：3 项（正例 / 非法 kind / 几何真实化断言）。"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    t0 = time.time()
    from lda_agent.pipeline_realize import design_pipeline_realize
    # 正例：全 9 kind 真实 GDS + DRC + round-trip
    rep = design_pipeline_realize(verbose=False)
    ok1 = bool(rep["acceptance"]["passed"])
    # 断言：Ring/AddDrop 已是 PATH（无实心环带 boundary）
    ring = rep["devices"]["RingResonator"]
    adddrop = rep["devices"]["RingAddDrop"]
    ok_geom = ("boundary" not in ring["desc_summary"] and
               "boundary" not in adddrop["desc_summary"] and
               "path" in ring["desc_summary"])
    ok_yb = rep["devices"]["SymmetricYBranch"]["desc_summary"].startswith(
        "boundary")  # taper 边界 + 双 path
    ok2 = ok_geom and ok_yb
    # 负例：非法 kind → 优雅 FAIL
    bad = design_pipeline_realize(devices=["NonexistentKind"])
    ok3 = not bad["acceptance"]["passed"]
    print(f"[{'PASS' if ok1 else 'FAIL'}] 全 9 kind 真实 GDS + DRC（{time.time()-t0:.0f}s）")
    print(f"[{'PASS' if ok2 else 'FAIL'}] 几何真实化断言（Ring/AddDrop→PATH，YB→taper+PATH）")
    print(f"[{'PASS' if ok3 else 'FAIL'}] 非法 kind 优雅 FAIL")
    passed = sum([ok1, ok2, ok3])
    print(f"\nD-79 smoke: {passed}/3 PASS")
    return 0 if passed == 3 else 1


if __name__ == "__main__":
    sys.exit(main())
