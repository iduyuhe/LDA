"""D-80 谱形目标逆设计 smoke：3 例（正例 split_ratio + 正例 spectrum + 负例非法类型）。

运行：python run_spectral_design_smoke.py（managed python，纯 numpy）
"""
import sys
sys.path.insert(0, ".")

from lda_agent.spectral_inverse_design import design_spectral

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


# 1) 正例：分束比 50:50 拓扑逆设计（双监视器，对数加权 FOM）
run("正例-分束比50:50", lambda: design_spectral(
    target_type="split_ratio", target_ratio=0.5,
    Nx=70, Ny=60, dl_factor=10, iters=18, nsamples=5, delta=0.02,
    beta_max=10.0), True)

# 2) 正例：谱形目标 3 波长窄带联合优化（[1.53,1.55,1.57]）
run("正例-谱形3波长", lambda: design_spectral(
    target_type="spectrum", wavelengths="1.53,1.55,1.57",
    Nx=70, Ny=60, dl_factor=10, iters=12, nsamples=5, delta=0.02), True)

# 3) 负例：非法 target_type → 优雅 FAIL
run("负例-非法target_type", lambda: design_spectral(
    target_type="not_a_target"), False)

all_pass = all(c[1] == "PASS" for c in cases)
for name, status, ok, verdict in cases:
    print(f"[{status}] {name}: ok={ok}")
    print(f"      {verdict}")
print(f"\nSMOKE {'ALL PASS' if all_pass else 'FAILED'} "
      f"({sum(1 for c in cases if c[1]=='PASS')}/{len(cases)})")
sys.exit(0 if all_pass else 1)
