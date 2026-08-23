"""D-83 混合参数化 × 多波长加权联合 smoke：3 例（正例 + Pareto + 单波长负例）。

运行：python run_hybrid_multi_smoke.py（managed python，纯 numpy）
"""
import sys
sys.path.insert(0, ".")

from lda_agent.hybrid_design import design_hybrid_multi  # noqa: E402

cases = []


def run(name, fn, expect_ok):
    try:
        r = fn()
        ok = bool(r.get("ok")) and bool(r.get("acceptance", {}).get("passed"))
        status = "PASS" if ok == expect_ok else "FAIL"
        cases.append((name, status, ok,
                      r.get("verdict", r.get("error", ""))[:110]))
    except Exception as e:  # noqa: BLE001
        status = "PASS" if (not expect_ok) else "FAIL"
        cases.append((name, status, False, f"异常: {str(e)[:80]}"))


# 1) 正例：混合×多波长加权联合（1.53/1.57，含纯形状多波长基线对比）
run("正例-混合×多波长", lambda: design_hybrid_multi(
    wavelengths="1.53,1.57", Nx=80, Ny=60, dl_factor=10,
    n_controls=8, iters=16, nsamples=6, delta=0.02, topo_wgt=0.6), True)

# 2) 正例：Pareto 前端存在（权重网格 ≥2 点）
run("正例-Pareto前端", lambda: design_hybrid_multi(
    wavelengths="1.53,1.57", Nx=80, Ny=60, dl_factor=10,
    n_controls=8, iters=12, nsamples=4, delta=0.02,
    topo_wgt=0.6, pareto=True), True)

# 3) 负例：单波长（<2 个）→ 优雅 FAIL
run("负例-单波长", lambda: design_hybrid_multi(
    wavelengths="1.55", Nx=80, Ny=60, dl_factor=10,
    n_controls=8, iters=10), False)

all_pass = all(c[1] == "PASS" for c in cases)
for name, status, ok, verdict in cases:
    print(f"[{status}] {name}: ok={ok}")
    print(f"      {verdict}")
print(f"\nSMOKE {'ALL PASS' if all_pass else 'FAILED'} "
      f"({sum(1 for c in cases if c[1]=='PASS')}/{len(cases)})")
sys.exit(0 if all_pass else 1)
