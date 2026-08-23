"""D-74 量子门/纠错拓扑 smoke：3 例（正例 + 超阈值 FAIL + CR 失效 FAIL）。"""
import sys
sys.path.insert(0, ".")

from lda_agent.qeda_topology import design_qeda_topology

cases = []


def run(name, fn, expect_ok):
    try:
        r = fn()
        ok = bool(r.get("ok")) and bool(r.get("acceptance", {}).get("passed"))
        status = "PASS" if ok == expect_ok else "FAIL"
        cases.append((name, status, ok,
                      r.get("verdict", r.get("error", ""))[:90]))
    except Exception as e:  # noqa: BLE001
        status = "PASS" if (not expect_ok) else "FAIL"
        cases.append((name, status, False, f"异常: {str(e)[:80]}"))


# 1) 正例：d=3，p=5e-3（<p_th=0.01），CR 默认参数（J=5,Δ=100,α=−250）
run("正例-d3/p5e-3/CR默认", lambda: design_qeda_topology(
    d=3, p_phys=5e-3, J=5.0, delta=100.0, alpha=-250.0), True)

# 2) 负例：超阈值 p=5e-2（>p_th）→ 阈值击穿 FAIL
run("负例-超阈值(p=0.05)", lambda: design_qeda_topology(
    d=3, p_phys=5e-2, J=5.0, delta=100.0, alpha=-250.0), False)

# 3) 负例：CR 耦合失效 J=0 → g_CR=0 → 门时间无穷 FAIL
run("负例-CR失效(J=0)", lambda: design_qeda_topology(
    d=3, p_phys=5e-3, J=0.0, delta=100.0, alpha=-250.0), False)

all_pass = all(c[1] == "PASS" for c in cases)
for name, status, ok, verdict in cases:
    print(f"[{status}] {name}: ok={ok}")
    print(f"      {verdict}")
print(f"\nSMOKE {'ALL PASS' if all_pass else 'FAILED'} "
      f"({sum(1 for c in cases if c[1]=='PASS')}/{len(cases)})")
sys.exit(0 if all_pass else 1)
