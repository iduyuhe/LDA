# -*- coding: utf-8 -*-
"""D-72 深化 smoke：3D 端口 S 参数验收（SOI 220nm）+ 负例。

正例：MMI 小几何 → 3D S 参数谱满足仿真有效 + 平衡度（≤0.15）+ 透射（≥0.05）。
负例 1：非法 kind（verify_s_params_3d 仅支持 MMI，非法应优雅报错）。
负例 2：out_gap 超大 → 输出口离线 → power_sum≈0 应 FAIL。
LLM 不进判决路径。
"""
import sys
sys.path.insert(0, ".")

from lda_agent.sparams_3d_design import design_sparams_3d  # noqa: E402
from lda_solver.port_sparams_3d import s_parameter_spectrum_3d  # noqa: E402

PASS = []


def run(name, expect, **kw):
    try:
        r = design_sparams_3d(**kw)
        ok = bool(r.get("acceptance", {}).get("passed")) == expect
    except Exception as e:  # noqa: BLE001
        ok, r = False, {"error": str(e)}
    PASS.append(ok)
    tag = "PASS" if ok else "FAIL"
    print(f"{tag} | {name}"
          f"{'' if ok else ' | ' + str(r.get('verdict', r.get('error')))[:90]}")


# 正例：小 MMI + 中心波长范围 + 短瞬态（smoke 提速；判据仍生效）
run("3D MMI S 参数验收（SOI 220nm）", True,
    mmi={"width": 0.5, "W_mmi": 3.0, "L_mmi": 6.0, "L_tap": 3.0,
         "out_gap": 0.5, "L_out": 2.0, "wl0_um": 1.55, "n_wl": 3,
         "span_um": 0.02},
    transient_cycles=800, dl_factor=12.0)

# 负例 1：非法 kind 优雅报错（s_parameter_spectrum_3d 不支持非 MMI）
try:
    s_parameter_spectrum_3d({}, [1.55])
    ok = False
except (ValueError, KeyError):
    ok = True
PASS.append(ok)
print(f"{'PASS' if ok else 'FAIL'} | 非法参数优雅报错（不崩）")

# 负例 2：out_gap 超大 → 输出口离线 → power_sum≈0 应 FAIL
run("3D out_gap 超大 → 仿真无效（应 FAIL）", False,
    mmi={"width": 0.5, "W_mmi": 3.0, "L_mmi": 6.0, "L_tap": 3.0,
         "out_gap": 20.0, "L_out": 2.0, "wl0_um": 1.55, "n_wl": 2,
         "span_um": 0.02},
    transient_cycles=400, dl_factor=12.0)

print(f"\n{'=' * 40}\nD-72 3D smoke: {sum(PASS)}/{len(PASS)} PASS")
sys.exit(0 if all(PASS) else 1)
