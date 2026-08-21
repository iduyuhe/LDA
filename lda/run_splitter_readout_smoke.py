"""D-63 方向耦合器 × 量子读出 smoke：正例 + 负例。"""
import json
import sys

sys.path.insert(0, ".")
from lda_agent.splitter_readout import design_splitter_readout  # noqa: E402

results = []


def run(name, expect_pass, **kw):
    try:
        r = design_splitter_readout(**kw)
        passed = bool(r.get("acceptance", {}).get("passed"))
    except Exception as e:  # noqa: BLE001
        passed, r = False, {"error": str(e)[:100]}
    ok = (passed == expect_pass)
    results.append(ok)
    detail = (f"passed={passed} (期望 {expect_pass})" +
              (f" | {r.get('verdict', '')[:80]}" if passed else
               f" | {r.get('error', '')[:80]}"))
    print(f"  {'PASS' if ok else 'FAIL'} | {name} | {detail}")
    return ok


print("=== D-63 方向耦合器×量子读出 smoke ===")
ok1 = run("3 qubit 均匀分束", True, f01s=[4.8, 5.0, 5.2])
ok2 = run("4 qubit 均匀分束（3 级 DC）", True, f01s=[4.8, 5.0, 5.2, 5.4])
ok3 = run("极端权重（最弱路 SNR 不足应 FAIL）", False,
          f01s=[4.8, 5.0, 5.2], weights=[0.9, 0.05, 0.05], nbar0=3.0)
ok4 = run("nbar0 过低（均匀分配后 SNR 不足应 FAIL）", False,
          f01s=[4.8, 5.0, 5.2], nbar0=0.3)
ok5 = run("weights 与 f01s 长度不匹配（应 FAIL）", False,
          f01s=[4.8, 5.0, 5.2], weights=[0.3, 0.7])

all_ok = all([ok1, ok2, ok3, ok4, ok5])
print(f"=== {'ALL PASS' if all_ok else 'HAS FAILURE'}（{sum(results)}/{len(results)}）===")
sys.exit(0 if all_ok else 1)
