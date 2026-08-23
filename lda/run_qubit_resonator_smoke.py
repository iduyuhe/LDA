"""D-88 QEDA 求解器级补强 smoke：3 例（标准工作点 + 不同参数 + 色散区失效负例）。

运行：python run_qubit_resonator_smoke.py（managed python，纯 numpy）
"""
import sys
sys.path.insert(0, ".")

from lda_agent.qubit_resonator_design import design_qubit_resonator  # noqa: E402

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


# 1) 正例：标准 transmon 工作点（f_q=5.0, α=-0.3, f_r=f_q+1.0, g=0.1, κ=0.005）
run("正例-标准工作点", lambda: design_qubit_resonator(
    f_q=5.0, alpha=-0.3, f_r=6.0, g=0.1, kappa=0.005), True)

# 2) 正例：不同参数（Δ=0.8 失谐更近、耦合更弱 g=0.08）仍过
run("正例-不同参数", lambda: design_qubit_resonator(
    f_q=5.2, alpha=-0.25, f_r=6.0, g=0.08, kappa=0.01), True)

# 3) 负例：色散区失效（Δ/g=2 < 5，强耦合区三能级解析近似不适用）→ 优雅 FAIL
run("负例-色散区失效", lambda: design_qubit_resonator(
    f_q=5.0, alpha=-0.3, f_r=5.2, g=0.1, kappa=0.005), False)

all_pass = all(c[1] == "PASS" for c in cases)
for name, status, ok, verdict in cases:
    print(f"[{status}] {name}: ok={ok}")
    print(f"      {verdict}")
print(f"\nSMOKE {'ALL PASS' if all_pass else 'FAILED'} "
      f"({sum(1 for c in cases if c[1]=='PASS')}/{len(cases)})")
sys.exit(0 if all_pass else 1)
