"""D-86 3D 逆设计 × 3D 端口 S 参数联合验收 smoke：3 例（正例 + 能量守恒 + 非法参数负例）。

运行：python run_port_acceptance_smoke.py（envs/default python，含 numba）
"""
import sys
sys.path.insert(0, ".")

from lda_agent.port_acceptance import design_port_acceptance  # noqa: E402

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


# 1) 正例：3D 逆设计 → 端口 S 参数联合验收（FOM 与 S21 同向双过）
run("正例-端口联合验收", lambda: design_port_acceptance(
    Nx=44, Ny=36, Nz=12, dl_factor=10, n_controls=8,
    iters=16, nsamples=6, delta=0.05, w_min=4.0, init_w=6.0), True)

# 2) 正例：不同波长（wl=1.5）仍过——端口验收通道对工作频率鲁棒
run("正例-不同波长", lambda: design_port_acceptance(
    Nx=44, Ny=36, Nz=12, dl_factor=10, n_controls=8,
    iters=14, nsamples=5, delta=0.05, w_min=4.0, init_w=6.0,
    wl_um=1.5), True)

# 3) 负例：非法宽度（w_min ≥ init_w）→ 优雅 FAIL
run("负例-宽度界非法", lambda: design_port_acceptance(
    Nx=40, Ny=32, Nz=10, n_controls=6, iters=6,
    w_min=6.0, init_w=5.0), False)

all_pass = all(c[1] == "PASS" for c in cases)
for name, status, ok, verdict in cases:
    print(f"[{status}] {name}: ok={ok}")
    print(f"      {verdict}")
print(f"\nSMOKE {'ALL PASS' if all_pass else 'FAILED'} "
      f"({sum(1 for c in cases if c[1]=='PASS')}/{len(cases)})")
sys.exit(0 if all_pass else 1)
