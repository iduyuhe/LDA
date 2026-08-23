"""D-82 形状+拓扑混合逆设计 smoke：3 例（混合正例 + 纯形状基线对比 + 拓扑带非法）。

运行：python run_hybrid_design_smoke.py（managed python，纯 numpy）
"""
import sys
sys.path.insert(0, ".")

from lda_agent.hybrid_design import design_hybrid

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


# 1) 正例：混合逆设计（形状主干 + 拓扑带，含纯形状基线对比）
run("正例-混合逆设计", lambda: design_hybrid(
    Nx=80, Ny=60, dl_factor=10, n_controls=8, iters=16,
    nsamples=6, delta=0.02, topo_wgt=0.6), True)

# 2) 正例：混合 ≥ 纯形状（基线对比通过——同一设计入口已验证）
run("正例-混合≥纯形状", lambda: design_hybrid(
    Nx=80, Ny=60, dl_factor=10, n_controls=8, iters=14,
    nsamples=6, delta=0.02, topo_band="1.5,6.5"), True)

# 3) 负例：拓扑带非法（lo ≥ hi）→ 优雅 FAIL
run("负例-拓扑带非法", lambda: design_hybrid(
    Nx=80, Ny=60, dl_factor=10, n_controls=8, iters=10,
    topo_band="7.0,2.0"), False)

all_pass = all(c[1] == "PASS" for c in cases)
for name, status, ok, verdict in cases:
    print(f"[{status}] {name}: ok={ok}")
    print(f"      {verdict}")
print(f"\nSMOKE {'ALL PASS' if all_pass else 'FAILED'} "
      f"({sum(1 for c in cases if c[1]=='PASS')}/{len(cases)})")
sys.exit(0 if all_pass else 1)
