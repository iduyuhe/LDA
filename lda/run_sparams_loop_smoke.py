# -*- coding: utf-8 -*-
"""D-72 深化 smoke：3D 端口验收接入设计闭环（DesignAgent method=sparams3d）。

正例：method=sparams3d + kind=mmi / dc → DesignOutcomeReport accepted=True。
负例 1：非法 kind → 优雅 FAIL（不崩）。
兼容性：method 默认 "scan"（布拉格）路径不受影响。
需 numba（python envs/default venv）。LLM 不进判决路径。
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


# 正例 1：method=sparams3d + MMI（小网格 + 短瞬态）
run("method=sparams3d MMI 闭环", True, {
    "method": "sparams3d",
    "geometry_type": "3d_sparams",
    "extra": {"kind": "mmi", "width": 0.5, "W_mmi": 3.0, "L_mmi": 6.0,
              "L_tap": 3.0, "out_gap": 0.5, "L_out": 2.0,
              "wl0_um": 1.55, "n_wl": 3, "span_um": 0.02,
              "transient_cycles": 800, "dl_factor": 12.0},
})

# 正例 2：method=sparams3d + DC
run("method=sparams3d DC 闭环", True, {
    "method": "sparams3d",
    "extra": {"kind": "dc", "width": 0.5, "gap": 0.3, "Lc": 10.0,
              "wl0_um": 1.55, "n_wl": 5, "span_um": 0.04,
              "transient_cycles": 800, "dl_factor": 12.0},
})

# 负例 1：非法 kind → 优雅 FAIL
run("method=sparams3d 非法 kind（应 FAIL）", False, {
    "method": "sparams3d",
    "extra": {"kind": "no_such", "width": 0.5,
              "wl0_um": 1.55, "n_wl": 2, "span_um": 0.02,
              "transient_cycles": 200, "dl_factor": 12.0},
})

# 兼容性：method 默认 "scan"（布拉格）路径不回归
try:
    rep = DesignAgent().run({})
    ok = rep.iterations >= 1 and isinstance(rep.verdict, str) \
        and isinstance(rep.loop_trace, list)
except Exception as e:  # noqa: BLE001
    ok, rep = False, None
PASS.append(ok)
print(f"{'PASS' if ok else 'FAIL'} | method 默认 scan（布拉格）路径兼容"
      f"{'' if ok else ' | ' + (rep.verdict[:90] if rep is not None else '')}")

print(f"\n{'=' * 40}\nD-72 闭环 smoke: {sum(PASS)}/{len(PASS)} PASS")
sys.exit(0 if all(PASS) else 1)
