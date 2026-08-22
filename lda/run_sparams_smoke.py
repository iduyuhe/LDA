# -*- coding: utf-8 -*-
"""D-72 端口 S 参数验收 smoke：MMI 2D FDTD + ORACLE 对拍 + PDK 注入 + 负例。

正例：MMI 小网格 → S 参数谱满足平衡度（≤0.15）+ 透射（≥0.05）+ PDK DRC 全绿。
负例 1：非法 kind（s_parameter_spectrum 应抛 ValueError，优雅不崩）。
负例 2：无输出（out_gap 极大导致输出口离线 → power_sum≈0 应 FAIL）。
LLM 不进判决路径。
"""
import sys
sys.path.insert(0, ".")

from lda_agent.sparams_design import design_sparams  # noqa: E402
from lda_solver.port_sparams import s_parameter_spectrum  # noqa: E402

PASS = []


def run(name, expect, **kw):
    try:
        r = design_sparams(**kw)
        ok = bool(r.get("acceptance", {}).get("passed")) == expect
    except Exception as e:  # noqa: BLE001
        ok, r = False, {"error": str(e)}
    PASS.append(ok)
    tag = "PASS" if ok else "FAIL"
    print(f"{tag} | {name}"
          f"{'' if ok else ' | ' + str(r.get('verdict', r.get('error')))[:90]}")


# 正例：生产几何（自成像段，5 波长全过的配置）中心附近 3 波长
run("MMI S 参数 + ORACLE 对拍 + PDK DRC", True,
    mmi={"width": 0.5, "W_mmi": 4.0, "L_mmi": 12.0, "L_tap": 3.0,
         "out_gap": 0.5, "L_out": 2.0, "wl0_um": 1.55, "n_wl": 3,
         "span_um": 0.02},
    transient_cycles=1200)

# 负例 1：非法 kind 优雅抛错
try:
    s_parameter_spectrum("no_such_kind", {}, [1.55])
    ok = False
except ValueError:
    ok = True
PASS.append(ok)
print(f"{'PASS' if ok else 'FAIL'} | 非法 kind 优雅抛错（不崩）")

# 负例 2：输出口离线（out_gap 巨大 → 输出波导在仿真域外 → power_sum≈0）
run("out_gap 超大 → 仿真无效（应 FAIL）", False,
    mmi={"width": 0.5, "W_mmi": 3.0, "L_mmi": 8.0, "L_tap": 3.0,
         "out_gap": 20.0, "L_out": 2.0, "wl0_um": 1.55, "n_wl": 2,
         "span_um": 0.02},
    transient_cycles=400)

print(f"\n{'=' * 40}\nD-72 smoke: {sum(PASS)}/{len(PASS)} PASS")
sys.exit(0 if all(PASS) else 1)
