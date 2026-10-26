# -*- coding: utf-8 -*-
"""E30 层栈扩展门禁（D-205 · v0.9.326）。

═══════════════════════════════════════════════════════════════════════════
本段把 E29 的「平台表达不了」变成「能表达、且精确知道还缺什么」
═══════════════════════════════════════════════════════════════════════════
① 层栈 **6 → 16 层**（+M3/M4/M5/M6/AP + VIA2-VIA5/VIA_AP），层号 27-36。
   🔴 **纯加法**：旧栈 `ecmos` 逐位不动 —— `gds_bytes` 936/1272/1608 · `flat` 120/464/1032
   三档**逐位一致**；`get_estack()` 缺省仍返回旧栈。
② 🔴 **换层实测暴露三个障碍**：
   · **CONT 结构性悬空**（行线是 CONT 的上层金属，移走即悬空 ⇒ 需 M1 落垫 + via stack）；
   · **AP 强制加宽**（`min_width=1.60` ⇒ W=0.40 时 DRC 必红）；
   · **AP 行距约束**（`pitch_y ≥ W + 1.60`）。
③ 🔴 **但找到了第一条 DRC 全过的换层路径**：AP 行线 W=1.60 · pitch_y=3.20 ⇒
   **DRC ACCEPT · r ×40 · 面积 ×1.32**（E28 假设 RDL 只有 ×10）⇒ 只差 CONT 悬空这一步。

判什么
  A 模块自检（`layer_stack_ext.layer_stack_ext_self_check` **10 项**）
  B 关键事实（10 条）：层数/加法性/层号段/M1 基准/CONT 悬空/强制加宽/AP 路径/
    r ≡ 闭式/缺口闭合但不可签核/输出档位
  C 反向可证伪：**5 条突变探针** ⇒ 均必红 + 还原重跑
  K 自入 CI core
"""
from __future__ import annotations

import os
import sys
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import layer_stack_ext as X   # noqa: E402
from lda_l2.ecore import parasitic as PA        # noqa: E402
from lda_harness.smoke_kit import make_result_collector  # noqa: E402

_results: list = []
check = make_result_collector(_results)

# 现算锚值（v0.9.326）
AN_OLD_LAYERS = 6
AN_NEW_LAYERS = 16
AN_ADDED = 10
AN_GDS = {4: 936, 8: 1272, 12: 1608}
AN_FLAT = {4: 120, 8: 464, 12: 1032}
AN_LAYER_MIN = 27
AN_LAYER_MAX = 36
AN_DANGLING = 64
AN_AP_W = 1.60
AN_AP_PY = 3.20
AN_AP_R = 0.012600
AN_AP_R_GAIN = 40.0
AN_AP_AREA = 1.32
AN_AP_W040_VIOL = 8


def _rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b) if b else float("inf")


# ---------------------------------------------------------------------------
# B 关键事实
# ---------------------------------------------------------------------------
def _layers_ok() -> bool:
    sc = X.stack_comparison()
    return (sc["old"]["n_layers"] == AN_OLD_LAYERS
            and sc["new"]["n_layers"] == AN_NEW_LAYERS
            and sc["n_added"] == AN_ADDED
            and sc["old_z_preserved"] and sc["default_unchanged"])


def _pure_add_ok() -> bool:
    """B2 · 🔴 纯加法：旧栈 GDS 指纹逐位一致（单看 DRC verdict 不够）。"""
    bu = X.baseline_unchanged()
    return bu["all_ok"] and all(
        r["gds"] == AN_GDS[r["n"]] and r["flat"] == AN_FLAT[r["n"]] for r in bu["rows"])


def _layer_no_ok() -> bool:
    sc = X.stack_comparison()
    new_only = [v for k, v in sc["new"]["gds"].items() if k not in sc["old"]["gds"]]
    return all(AN_LAYER_MIN <= v <= AN_LAYER_MAX for v in new_only) and len(new_only) == 10


def _matrix_ok() -> bool:
    """B4 · M1 全过 · 非 M1 的 LVS 全 REJECT。

    🔴 **反向完备**：`all(r["lvs"] != "ACCEPT" for r in others)` 在 `others` 为空时恒为 True
    ⇒ 必须显式断言「非 M1 的行数 == 3」，否则探针把所有行改成 M1 后判据**反而变绿**
    （v0.9.326 开发时当场抓到的假绿）。
    """
    mx = X.row_layer_matrix()
    m1 = [r for r in mx if r["row_layer"] == "M1"]
    others = [r for r in mx if r["row_layer"] != "M1"]
    return (len(m1) == 1 and len(others) == 3
            and m1[0]["drc"] == "ACCEPT" and m1[0]["lvs"] == "ACCEPT"
            and all(r["lvs"] != "ACCEPT" for r in others))


def _dangling_ok() -> bool:
    da = X.dangling_analysis()
    return da["n_dangling"] == AN_DANGLING and "DANGLING" in da["sample"]


def _forced_widen_ok() -> bool:
    fw = X.ap_forced_widen()
    return (fw["rows"][0]["n_viol"] == AN_AP_W040_VIOL
            and "EDR-MIN-WIDTH" in fw["rows"][0]["rules"])


def _ap_ok() -> bool:
    summ, rows = X.ap_pathway()
    r = rows[0]
    return (summ["drc_all_pass"] and summ["lvs_all_reject"]
            and _rel(r["w_um"], AN_AP_W) < 1e-12
            and _rel(r["pitch_y_um"], AN_AP_PY) < 1e-12
            and _rel(r["r_gain"], AN_AP_R_GAIN) < 0.02
            and _rel(r["area_ratio"], AN_AP_AREA) < 0.03)


def _r_formula_ok() -> bool:
    """B8 · AP 的 r 必须 ≡ E7 闭式（不另设口径）。"""
    _, rows = X.ap_pathway()
    ref = PA.wire_resistance(2.40, AN_AP_W, 1.68e-2, 2.00)
    return abs(rows[0]["r_seg_ohm"] - ref) / ref < 1e-15 and _rel(ref, AN_AP_R) < 1e-5


def _gap_ok() -> bool:
    """B9 · 缺口「能表达」但不「可签核」（两者必须分开报）。"""
    gc = X.gap_closure()
    da = X.dangling_analysis()
    return (gc["m6_expressible"] and gc["ap_expressible"] and da["n_dangling"] > 0)


def main() -> int:
    print("=" * 74)
    print("E30 层栈扩展门禁（D-205）")
    print("=" * 74)

    print("\n[A] 模块自检（layer_stack_ext.layer_stack_ext_self_check）")
    ok_mod = X.layer_stack_ext_self_check(verbose=True)
    check("A1 模块自检 10/10 全绿", ok_mod)

    print("\n[B] 关键事实")
    check("B1 层栈 %d → %d 层（+%d）· 旧 z 逐位继承 · 缺省仍旧栈"
          % (AN_OLD_LAYERS, AN_NEW_LAYERS, AN_ADDED), _layers_ok())
    check("B2 🔴 **纯加法**：旧栈三档 `gds_bytes` %s + `flat` %s 逐位一致"
          % (list(AN_GDS.values()), list(AN_FLAT.values())), _pure_add_ok())
    check("B3 新增层号落在 %d~%d（不与他域冲突）" % (AN_LAYER_MIN, AN_LAYER_MAX),
          _layer_no_ok())
    check("B4 M1 基准 DRC/LVS 全 ACCEPT；非 M1 全部 LVS **REJECT**", _matrix_ok())
    check("B5 🔴 换层障碍 = **CONT 悬空**（%d 条 DANGLING-BRIDGE）" % AN_DANGLING,
          _dangling_ok())
    check("B6 🔴 AP `min_width=1.60` ⇒ W=0.40 必红（%d 处）⇒ **换层强制加宽**"
          % AN_AP_W040_VIOL, _forced_widen_ok())
    check("B7 🔴 AP 路径 DRC 全过：W=%.2f · pitch_y=%.2f ⇒ **r ×%.0f** · 面积 ×%.2f"
          % (AN_AP_W, AN_AP_PY, AN_AP_R_GAIN, AN_AP_AREA), _ap_ok())
    check("B8 AP 的 `r_seg` ≡ E7 闭式 `ρL/(Wt)` = %.6f Ω" % AN_AP_R, _r_formula_ok())
    check("B9 E29 缺口「**能表达**」但**不可签核**（CONT 悬空未解）", _gap_ok())
    check("B10 全部输出恒标 `MODEL_ESTIMATE`",
          X.stack_comparison()["tier"] == "MODEL_ESTIMATE")

    # ------------------------------------------------------------------
    print("\n[C] 反向可证伪探针")

    # C1：把新栈退回 6 层（假装没加层）⇒ B1 必红
    _real_sc = X.stack_comparison

    def _no_ext():
        sc = _real_sc()
        sc["new"] = dict(sc["old"])
        sc["n_added"] = 0
        return sc

    with mock.patch.object(X, "stack_comparison", _no_ext):
        c1 = not _layers_ok()
    check("C1 探针：把新栈退回 6 层（假装没加层）⇒ B1 必红", c1)

    # C2：把换层强制成 M1（换层失效）⇒ B4 必红
    _real_mx = X.row_layer_matrix

    def _all_m1(n=8):
        return [{**r, "row_layer": "M1", "lvs": "ACCEPT"} for r in _real_mx(n)]

    with mock.patch.object(X, "row_layer_matrix", _all_m1):
        c2 = not _matrix_ok()
    check("C2 探针：把换层强制成 M1（LVS 全 ACCEPT）⇒ B4 必红", c2)

    # C3：把 AP 的 min_width 说成 0.40（"换层不需加宽"）⇒ B6 必红
    _real_fw = X.ap_forced_widen

    def _no_widen():
        fw = _real_fw()
        fw["rows"][0].update({"drc": "ACCEPT", "n_viol": 0, "rules": []})
        fw["rows"][1].update({"drc": "ACCEPT", "n_viol": 0, "rules": []})
        return fw

    with mock.patch.object(X, "ap_forced_widen", _no_widen):
        c3 = not _forced_widen_ok()
    check("C3 探针：把 AP min_width 说成 0.40（宣称「换层不需加宽」）⇒ B6 必红", c3)

    # C4：宣称 AP 路径可签核（LVS ACCEPT）⇒ B7 必红
    _real_ap = X.ap_pathway

    def _fake_signoff():
        summ, rows = _real_ap()
        return ({**summ, "lvs_all_reject": False},
                [{**r, "lvs": "ACCEPT"} for r in rows])

    with mock.patch.object(X, "ap_pathway", _fake_signoff):
        c4 = not _ap_ok()
    check("C4 探针：宣称 AP 路径 LVS 也过（可签核）⇒ B7 必红", c4)

    # C5：宣称缺口已完全闭合（把悬空说成 0 条）⇒ B9 必红
    with mock.patch.object(X, "dangling_analysis", lambda n=8: {
            "n": n, "row_layer": "M6", "lvs": "ACCEPT", "n_issues": 0,
            "n_dangling": 0, "sample": "", "root_cause": "", "fix": "",
            "verdict": "已闭合", "tier": "MODEL_ESTIMATE"}):
        c5 = not _gap_ok()
    check("C5 探针：把 CONT 悬空说成 0 条（宣称缺口全闭合）⇒ B9 必红", c5)

    check("C6 全部探针还原后，模块自检与关键事实仍全绿",
          X.layer_stack_ext_self_check() and _pure_add_ok() and _ap_ok())

    # ------------------------------------------------------------------
    print("\n[K] CI 登记")
    ci = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_ecore_e30_smoke.py" in ck)

    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    print()
    for name, ok, detail in _results:
        print(("[PASS] " if ok else "[FAIL] ") + name + (("  :: " + detail) if detail else ""))
    print()
    print("=" * 74)
    print("E30 门禁结果：%d PASS / %d FAIL（共 %d 判据 · 含 5 突变探针）"
          % (npass, nfail, len(_results)))
    print("=" * 74)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
