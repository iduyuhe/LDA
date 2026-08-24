"""D-91 QEDA 纵深三件套 smoke：4 例（标准点 + 不同参数 + 驱动强场负例 + 串扰简并负例）。

运行：python run_qeda_depth_smoke.py（managed python，纯 numpy）
"""
import sys
sys.path.insert(0, ".")

from lda_agent.qeda_depth_design import design_qeda_depth  # noqa: E402

cases = []


def run(name, fn, expect_ok):
    try:
        r = fn()
        ok = bool(r.get("ok")) and bool(r.get("passed"))
        status = "PASS" if ok == expect_ok else "FAIL"
        cases.append((name, status, ok,
                      r.get("verdict", r.get("error", ""))[:110]))
    except Exception as e:  # noqa: BLE001
        status = "PASS" if (not expect_ok) else "FAIL"
        cases.append((name, status, False, f"异常: {str(e)[:80]}"))


# 1) 正例：标准工作点（f_q=5.0, α=-0.3, f_r=6.0, g=0.1 + 驱动 + 串扰）
run("正例-标准工作点", lambda: design_qeda_depth(
    f_q=5.0, alpha=-0.3, f_r=6.0, g=0.1,
    Omega=0.05, delta_d=0.4, f_q2=5.2, g2=0.08), True)

# 2) 正例：不同参数（f_r 更近 Δ=0.8、驱动更强 Ω=0.08、串扰 g2=0.1）仍过
run("正例-不同参数", lambda: design_qeda_depth(
    f_q=5.2, alpha=-0.25, f_r=6.0, g=0.08,
    Omega=0.08, delta_d=0.5, f_q2=5.0, g2=0.1), True)

# 3) 负例：驱动强场（Ω/δ_d 太大 → AC Stark 弱驱动近似失效）→ 优雅 FAIL
run("负例-驱动强场", lambda: design_qeda_depth(
    f_q=5.0, alpha=-0.3, f_r=6.0, g=0.1,
    Omega=0.25, delta_d=0.2, f_q2=5.2, g2=0.08), False)

# 4) 负例：串扰简并（f_q1=f_q2 → 简并态干扰 ZZ 提取？）→ 物理上应 FAIL 或稳健 PASS
#    简并下最近匹配可能错态 → 负例验证优雅失败（诚实边界）
run("负例-串扰简并", lambda: design_qeda_depth(
    f_q=5.0, alpha=-0.3, f_r=6.0, g=0.1,
    Omega=0.05, delta_d=0.4, f_q2=5.0, g2=0.08), False)

all_pass = all(c[1] == "PASS" for c in cases)
for name, status, ok, verdict in cases:
    print(f"[{status}] {name}: ok={ok}")
    print(f"      {verdict}")
print(f"\nSMOKE {'ALL PASS' if all_pass else 'FAILED'} "
      f"({sum(1 for c in cases if c[1]=='PASS')}/{len(cases)})")
sys.exit(0 if all_pass else 1)
