"""D-75 大规模系统基准 smoke：3 例（正例 8×8 + WDM 超容量 FAIL + qubit 过密 FAIL）。"""
import sys
sys.path.insert(0, ".")

from lda_agent.large_scale_bench import run_large_scale_bench

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


# 1) 正例：默认 8 WDM 信道 × 8 qubit 大规模联合压测（+边界扫描）
run("正例-WDM8×Q8联合压测", lambda: run_large_scale_bench(
    n_wdm=8, n_qubit=8), True)

# 2) 负例：WDM 超容量 N=10（span 10.8nm > FSR 9.1nm → 单 FSR 混叠 FAIL）
run("负例-WDM超容量(N=10跨FSR)", lambda: run_large_scale_bench(
    n_wdm=10, n_qubit=8), False)

# 3) 负例：qubit 读出间隔过密（0.02GHz < 3κ_r=0.0225GHz → 错开/dip 融合 FAIL）
run("负例-qubit过密(0.02<3κ_r)", lambda: run_large_scale_bench(
    n_wdm=8, n_qubit=8, qubit_spacing_ghz=0.02), False)

all_pass = all(c[1] == "PASS" for c in cases)
for name, status, ok, verdict in cases:
    print(f"[{status}] {name}: ok={ok}")
    print(f"      {verdict}")
print(f"\nSMOKE {'ALL PASS' if all_pass else 'FAILED'} "
      f"({sum(1 for c in cases if c[1]=='PASS')}/{len(cases)})")
sys.exit(0 if all_pass else 1)
