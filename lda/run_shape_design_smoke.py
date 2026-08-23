"""D-81 形状逆设计 + 多目标联合 smoke：3 例（形状正例 + 多目标正例 + DRC 负例）。

运行：python run_shape_design_smoke.py（managed python，纯 numpy）
"""
import sys
sys.path.insert(0, ".")

from lda_agent.multi_objective_design import design_shape, design_multi_objective

cases = []


def run(name, fn, expect_ok):
    try:
        r = fn()
        ok = bool(r.get("ok")) and bool(r.get("acceptance", {}).get("passed"))
        status = "PASS" if ok == expect_ok else "FAIL"
        cases.append((name, status, ok,
                      r.get("verdict", r.get("error", ""))[:100]))
    except Exception as e:  # noqa: BLE001
        status = "PASS" if (not expect_ok) else "FAIL"
        cases.append((name, status, False, f"异常: {str(e)[:80]}"))


# 1) 正例：形状逆设计（8 控制点宽度曲线，FOM improvement + DRC）
run("正例-形状逆设计", lambda: design_shape(
    Nx=80, Ny=60, dl_factor=10, n_controls=8, iters=18,
    nsamples=5, delta=0.05), True)

# 2) 正例：多目标联合（2 波长加权 + Pareto 前端）
run("正例-多目标2波长", lambda: design_multi_objective(
    wavelengths="1.53,1.57", Nx=80, Ny=60, dl_factor=10,
    n_controls=8, iters=14, nsamples=5, delta=0.05), True)

# 3) 负例：DRC 不满足（宽度界冲突：w_min > w_max）→ 优雅 FAIL
run("负例-宽度界非法", lambda: design_shape(
    Nx=80, Ny=60, dl_factor=10, n_controls=8, iters=10,
    w_min=10.0, w_max=2.0), False)

all_pass = all(c[1] == "PASS" for c in cases)
for name, status, ok, verdict in cases:
    print(f"[{status}] {name}: ok={ok}")
    print(f"      {verdict}")
print(f"\nSMOKE {'ALL PASS' if all_pass else 'FAILED'} "
      f"({sum(1 for c in cases if c[1]=='PASS')}/{len(cases)})")
sys.exit(0 if all_pass else 1)
