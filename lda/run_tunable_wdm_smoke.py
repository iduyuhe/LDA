"""D-73 热光可调 WDM smoke：3 例（正例 + FSR 混叠负例 + 非法信道负例）。"""
import sys
sys.path.insert(0, ".")

from lda_agent.tunable_wdm import design_tunable_wdm

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


# 1) 正例：默认 3 信道，全局热调谐演示
run("正例-默认3信道热调谐", lambda: design_tunable_wdm(
    [1550.0, 1553.0, 1556.0]), True)

# 2) 负例：目标超出 FSR/2（跨入相邻 FSR，应判 no_fsr_alias 失败）
run("负例-FSR混叠(目标+10nm)", lambda: design_tunable_wdm(
    [1550.0, 1553.0, 1556.0], target_channels_nm=[1560.0, 1563.0, 1566.0]), False)

# 3) 负例：非法（单信道，应优雅失败）
run("负例-单信道", lambda: design_tunable_wdm([1550.0]), False)

all_pass = all(c[1] == "PASS" for c in cases)
for name, status, ok, verdict in cases:
    print(f"[{status}] {name}: ok={ok}")
    print(f"      {verdict}")
print(f"\nSMOKE {'ALL PASS' if all_pass else 'FAILED'} ({sum(1 for c in cases if c[1]=='PASS')}/{len(cases)})")
sys.exit(0 if all_pass else 1)
