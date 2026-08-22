# -*- coding: utf-8 -*-
"""D-69 伴随法拓扑逆设计 smoke：验证锚（adjoint vs FD）+ 拓扑优化 + 负例。

正例：默认聚焦器几何 → verify 对拍 max_rel_err≤0.15 且拓扑提升≥1.5。
负例：空设计区（应 FAIL）；iters=0（无优化，improvement=1.0 应 FAIL）。
LLM 不进判决路径。
"""
import sys
sys.path.insert(0, ".")

from lda_agent.adjoint_design import design_adjoint  # noqa: E402
from lda_solver.adjoint_fdtd import AdjointProblem  # noqa: E402

PASS = []


def run(name, expect, **kw):
    try:
        r = design_adjoint(**kw)
        ok = bool(r.get("acceptance", {}).get("passed")) == expect
    except Exception as e:  # noqa: BLE001
        ok, r = False, {"error": str(e)}
    PASS.append(ok)
    tag = "PASS" if ok else "FAIL"
    print(f"{tag} | {name}"
          f"{'' if ok else ' | ' + str(r.get('verdict', r.get('error')))[:90]}")


# 正例：默认几何 + 精简迭代（smoke 提速）
run("默认聚焦器：验证锚 + 拓扑逆设计", True,
    iters=30, step0=0.5, nsamples=6)

# 负例 1：空设计区（di0==di1 → 无优化自由度，应 FAIL）
run("空设计区（应 FAIL）", False,
    problem=AdjointProblem(di0=40, di1=40, dj0=30, dj1=60),
    iters=20, nsamples=4)

# 负例 2：0 次迭代（无优化，improvement=1.0 应 FAIL）
run("0 次迭代（应 FAIL）", False, iters=0, nsamples=4)

print(f"\n{'=' * 40}\nD-69 smoke: {sum(PASS)}/{len(PASS)} PASS")
sys.exit(0 if all(PASS) else 1)
