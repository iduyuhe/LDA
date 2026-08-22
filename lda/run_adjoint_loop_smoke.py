# -*- coding: utf-8 -*-
"""D-70 逆设计目标泛化接入 D-36 引擎 smoke：method=adjoint 闭环 + 负例 + 兼容性。

正例：method="adjoint" → 均匀平板初值 → FD 对拍锚 → 梯度拓扑优化 → accepted=True。
负例：空设计区（应 FAIL）；iters=0（improvement=1.0 应 FAIL）。
兼容性：method 默认 "scan" 的布拉格扫描路径不受影响（跑通 + 结构正确）。
LLM 不进判决路径。
"""
import sys
sys.path.insert(0, ".")

from lda_agent.design_loop import DesignAgent  # noqa: E402

PASS = []


def run(name, expect, intent):
    try:
        rep = DesignAgent().run(intent)
        ok = bool(rep.accepted) == expect
    except Exception as e:  # noqa: BLE001
        ok, rep = False, None
    PASS.append(ok)
    tag = "PASS" if ok else "FAIL"
    detail = "" if ok else (
        " | " + (rep.verdict[:90] if rep is not None else str(None)))
    print(f"{tag} | {name}{detail}")


# 正例：adjoint 逆设计闭环（小网格提速）
run("method=adjoint：梯度拓扑逆设计闭环", True, {
    "method": "adjoint",
    "geometry_type": "adjoint_focuser",
    "extra": {"Nx": 90, "Ny": 70, "dl_factor": 14.0, "sponge": 10,
              "iters": 20, "nsamples": 6},
})

# 负例 1：空设计区（di0==di1 → 无优化自由度，应 FAIL）
run("method=adjoint 空设计区（应 FAIL）", False, {
    "method": "adjoint",
    "extra": {"di0": 40, "di1": 40, "dj0": 30, "dj1": 60,
              "iters": 20, "nsamples": 4},
})

# 负例 2：0 次迭代（improvement=1.0 应 FAIL）
run("method=adjoint 0 次迭代（应 FAIL）", False, {
    "method": "adjoint",
    "extra": {"iters": 0, "nsamples": 4},
})

# 兼容性：method 默认 "scan"（布拉格）路径不回归——跑通且结构正确
try:
    rep = DesignAgent().run({})
    ok = rep.iterations >= 1 and isinstance(rep.verdict, str) \
        and isinstance(rep.loop_trace, list)
except Exception as e:  # noqa: BLE001
    ok, rep = False, None
PASS.append(ok)
print(f"{'PASS' if ok else 'FAIL'} | method 默认 scan（布拉格）路径兼容"
      f"{'' if ok else ' | ' + (rep.verdict[:90] if rep is not None else '')}")

print(f"\n{'=' * 40}\nD-70 smoke: {sum(PASS)}/{len(PASS)} PASS")
sys.exit(0 if all(PASS) else 1)
