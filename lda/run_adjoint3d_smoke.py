"""D-84/85/87/89/92 3D adjoint 逆设计 smoke：7 例（shape + section + spectral + 不同网格 + numba 一致性 + 3D 拓扑 + 非法域负例）。

运行：python run_adjoint3d_smoke.py（managed python，纯 numpy；有 numba 时
forward/梯度自动走 JIT 核，无则回退 numpy——一致性用例跨环境稳定）
"""
import sys
sys.path.insert(0, ".")

from lda_agent.adjoint3d_design import (  # noqa: E402
    design_shape3d, design_section3d, design_spectral3d, design_topology3d,
)

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

# 2) 正例：3D 截面形状（宽度 × 厚度双软边界）
run("正例-3D截面形状", lambda: design_section3d(
    Nx=40, Ny=32, Nz=12, dl_factor=10, n_controls=8,
    iters=12, nsamples=6, delta=0.05), True)

# 3) 正例：谱形目标 × 3D 截面（多波长加权联合——物理网格固定只变 omega）
run("正例-谱形目标x3D截面", lambda: design_spectral3d(
    Nx=40, Ny=32, Nz=12, dl_factor=10, n_controls=8,
    iters=12, nsamples=5, delta=0.05,
    wavelengths_um=[1.5, 1.6]), True)

# 4) 正例：不同网格仍过——3D 转置与网格无关
run("正例-不同网格", lambda: design_shape3d(
    Nx=40, Ny=32, Nz=12, dl_factor=12, n_controls=6,
    iters=10, nsamples=5, delta=0.05), True)

# 5) 正例：numba 后端一致性（有 numba 验证 JIT 与 numpy FOM 一致；无 numba 验证优雅回退）
def case_numba():
    import numpy as np
    from lda_solver.adjoint_fdtd3d import (  # noqa: E402
        AdjointProblem3D, ShapeProblem3D, forward3d, _NUMBA,
    )
    p = AdjointProblem3D(Nx=40, Ny=32, Nz=12)
    sp = ShapeProblem3D(p, n_controls=8)
    eps3 = sp.eps(np.full(8, sp.init_halfwidth))
    f_np = forward3d(p, eps3, backend="numpy")
    f_nb = forward3d(p, eps3, backend="numba")   # 无 numba 时自动回退 numpy
    rel = abs(f_nb["FOM"] - f_np["FOM"]) / f_np["FOM"]
    ok = bool(rel <= 1e-10)
    return {"ok": ok, "acceptance": {"passed": ok},
            "verdict": f"numba={_NUMBA} FOM rel={rel:.1e}（≤1e-10）"}


run("正例-numba后端一致性", case_numba, True)

# 6) 正例：3D voxel 拓扑逆设计（3D 纵深最后一环——潜伏密度 + tanh 投影）
run("正例-3D拓扑逆设计", lambda: design_topology3d(
    Nx=40, Ny=32, Nz=12, dl_factor=10, iters=12, nsamples=5, delta=0.05), True)

# 7) 负例：3D 域过小 → 优雅 FAIL
run("负例-域过小", lambda: design_spectral3d(
    Nx=16, Ny=16, Nz=6, n_controls=4, iters=4), False)

all_pass = all(c[1] == "PASS" for c in cases)
for name, status, ok, verdict in cases:
    print(f"[{status}] {name}: ok={ok}")
    print(f"      {verdict}")
print(f"\nSMOKE {'ALL PASS' if all_pass else 'FAILED'} "
      f"({sum(1 for c in cases if c[1]=='PASS')}/{len(cases)})")
sys.exit(0 if all_pass else 1)
