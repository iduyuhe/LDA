# -*- coding: utf-8 -*-
"""D-71 真实版图基元库 smoke：GDS 编码 + round-trip + DRC + 负例。

正例：4 基元（Taper/EulerBend/MMI/GratingCoupler）GDS 可编码（round-trip
回读一致）+ DRC 全绿 → accepted=True。
负例 1：非法 kind → primitive_descs 抛 ValueError（优雅错误，不崩）。
负例 2：Taper w1=0.1µm < min_width 0.35 → DRC FAIL → accepted=False。
LLM 不进判决路径。
"""
import sys
sys.path.insert(0, ".")

from lda_agent.primitives_design import design_primitives  # noqa: E402
from lda_l2.primitives import primitive_descs  # noqa: E402

PASS = []


def run(name, expect, **kw):
    try:
        r = design_primitives(**kw)
        ok = bool(r.get("acceptance", {}).get("passed")) == expect
    except Exception as e:  # noqa: BLE001
        ok, r = False, {"error": str(e)}
    PASS.append(ok)
    tag = "PASS" if ok else "FAIL"
    print(f"{tag} | {name}"
          f"{'' if ok else ' | ' + str(r.get('verdict', r.get('error')))[:90]}")


# 正例：4 基元默认参数 → GDS + DRC 全过
run("4 基元 GDS 可编码 + DRC 全绿", True, _svg=False)

# 负例 1：非法 kind 优雅抛错
try:
    primitive_descs("no_such_kind", {})
    ok = False
except ValueError:
    ok = True
PASS.append(ok)
print(f"{'PASS' if ok else 'FAIL'} | 非法 kind 优雅抛错（不崩）")

# 负例 2：Taper w1=0.1µm 违反 min_width → 验收 FAIL
run("Taper w1=0.1µm 违反 min_width（应 FAIL）", False,
    _svg=False, Taper={"w1": 0.1})

print(f"\n{'=' * 40}\nD-71 smoke: {sum(PASS)}/{len(PASS)} PASS")
sys.exit(0 if all(PASS) else 1)
