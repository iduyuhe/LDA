"""D-84 3D adjoint 形状逆设计 smoke：3 例（正例 + 形状梯度 + 非法域负例）。

运行：python run_adjoint3d_smoke.py（managed python，纯 numpy）
"""
import sys
sys.path.insert(0, ".")

from lda_agent.adjoint3d_design import design_shape3d  # noqa: E402

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


# 1) 正例：3D adjoint 形状逆设计（3D Yee 显式转置 + 宽度 taper）
run("正例-3D形状逆设计", lambda: design_shape3d(
    Nx=40, Ny=32, Nz=10, dl_factor=10, n_controls=8,
    iters=12, nsamples=6, delta=0.05), True)

# 2) 正例：不同网格（Nz 加厚核心层）仍过——3D 转置与网格无关
run("正例-不同网格", lambda: design_shape3d(
    Nx=40, Ny=32, Nz=12, dl_factor=12, n_controls=6,
    iters=10, nsamples=5, delta=0.05), True)

# 3) 负例：3D 域过小 → 优雅 FAIL
run("负例-域过小", lambda: design_shape3d(
    Nx=16, Ny=16, Nz=6, n_controls=4, iters=4), False)

all_pass = all(c[1] == "PASS" for c in cases)
for name, status, ok, verdict in cases:
    print(f"[{status}] {name}: ok={ok}")
    print(f"      {verdict}")
print(f"\nSMOKE {'ALL PASS' if all_pass else 'FAILED'} "
      f"({sum(1 for c in cases if c[1]=='PASS')}/{len(cases)})")
sys.exit(0 if all_pass else 1)
