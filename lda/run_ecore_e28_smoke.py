# -*- coding: utf-8 -*-
"""E28 行线电阻反解与版图可行性门禁（D-203 · v0.9.324）。

═══════════════════════════════════════════════════════════════════════════
本段把 E27 的「r↓N×」目标换成「**具体的版图动作 + 各自的代价**」
═══════════════════════════════════════════════════════════════════════════
① 🔴 **「5% 预算只有 12 行」不是物理极限，是 `M1 + 单端驱动` 这个版图选择的结果。**
   只换 RDL 厚金属（**C 完全不变 ⇒ 零电容代价**）⇒ **42 行**；再加双端驱动 ⇒ **87 行**。
② 🔴 **物理依据两条，都是精确恒等式**：
   · `C` 的闭式 `ε₀ε_r·W/d` 里**没有 `t`** ⇒ 加厚金属**纯收益**（R↓ C 不动）；
   · `R∝1/W` 且 `C∝W` ⇒ **`R·C` 与线宽无关** ⇒ 加宽只换**静态 IR**，代价是**动态功耗**。
③ **推荐方案（两项显式约束内）**：RDL + W0.8 + 双端驱动 ⇒ **N=125**（10.42×）、
   ADC 项 179.2 → **17.2 fJ/op**、vs Mythic **21.6× → 2.1×**；代价 C×2 / **总功耗 +0.96%**。

判什么
  A 模块自检（`row_metal.row_metal_self_check` **12 项**）
  B 关键事实（11 条）：R□ · `R·C` 不变性 · `C` 对 t 不变性 · 六方案 N ·
    推荐方案 · 基准对照 · 双端 1/4 · 代价单调 · 代价必须报出 · 输出档位
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

from lda_l2.ecore import row_metal as R     # noqa: E402
from lda_harness.smoke_kit import make_result_collector  # noqa: E402

_results: list = []
check = make_result_collector(_results)

# 现算锚值（v0.9.324）
AN_SHEET_M1 = 0.084                 # R□ = ρ/t（Ω/□）
AN_RC = 0.111382                    # R·C（与线宽无关）
AN_C = 0.220996                     # 每段 C（与金属厚度无关）
AN_N = [12, 29, 42, 87, 125, 200]    # 六方案 N 上界
AN_BEST_N = 125
AN_BEST_VS = 2.1
AN_BEST_COST_C = 2.00
AN_BEST_DPP = 0.96                  # 总功耗增量（百分点）
AN_BASE_N = 12
AN_BASE_VS = 21.6
# 行线功耗份额（% · **取 4 位有效数字，不取显示精度**）
#   🔴 曾按 %.2f 显示值硬写 [0.09,...] ⇒ 首个元素实际 0.0942，相对差 4.67% ⇒ 判据当场红
AN_SHARES = [0.0942, 0.2395, 0.3502, 0.7318, 1.0518, 1.6772]
AN_MYTHIC = 8.3


def _rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b) if b else float("inf")


# ---------------------------------------------------------------------------
# B 关键事实
# ---------------------------------------------------------------------------
def _sheet_ok() -> bool:
    return _rel(R.seg_rc("m1", 0.40)["sheet_r_ohm_sq"], AN_SHEET_M1) < 1e-9


def _rc_invariant_ok() -> bool:
    """B2 · 🔴 `R·C` 与线宽无关（精确恒等式 · 加宽只换静态 IR 的依据）。"""
    inv = R.rc_invariance()
    return inv["invariant"] and _rel(inv["rc_values"][0], AN_RC) < 1e-5


def _c_vs_t_ok() -> bool:
    """B3 · 🔴 `C` 与金属厚度无关（换层纯收益的依据）。"""
    ct = R.c_vs_thickness()
    return ct["invariant"] and _rel(ct["c_values"][0], AN_C) < 1e-5


def _plans_ok() -> bool:
    return [r["n_max"] for r in R.plan_table()] == AN_N


def _best_ok() -> bool:
    bp = R.best_plan()
    d_pp = (bp["plan"]["row_line_share"] - bp["baseline"]["row_line_share"]) * 100.0
    return (bp["plan"]["n_max"] == AN_BEST_N
            and _rel(bp["plan"]["vs_mythic"], AN_BEST_VS) < 0.03
            and _rel(bp["plan"]["cost_c"], AN_BEST_COST_C) < 0.01
            and abs(d_pp - AN_BEST_DPP) < 0.02)


def _base_ok() -> bool:
    base = R.plan_table()[0]
    return base["n_max"] == AN_BASE_N and _rel(base["vs_mythic"], AN_BASE_VS) < 0.02


def _dual_ok() -> bool:
    return abs([x for x in R.DRIVE_MODES if x["id"] == "dual"][0]["r_factor"] - 0.25) < 1e-15


def _cost_reported_ok() -> bool:
    """B9 · 🔴 代价必须报出，且随方案推进单调上升（守「不得只报收益」）。"""
    shares = [r["row_line_share"] * 100 for r in R.plan_table()]
    return (all(_rel(s, a) < 0.005 for s, a in zip(shares, AN_SHARES))
            and all(shares[i] <= shares[i + 1] + 1e-9 for i in range(len(shares) - 1)))


def _cost_model_ok() -> bool:
    """B10 · cost_model 必须同时报物理代价、工艺代价、未建模项。"""
    cm = R.cost_model("ac")
    return (cm["physical"]["c_ratio"] > 0
            and "extra_masks" in cm["process"]
            and len(cm["not_modeled"]) >= 3
            and "未做 DRC" in cm["verdict"])


def main() -> int:
    print("=" * 74)
    print("E28 行线电阻反解与版图可行性门禁（D-203）")
    print("=" * 74)

    print("\n[A] 模块自检（row_metal.row_metal_self_check）")
    ok_mod = R.row_metal_self_check(verbose=True)
    check("A1 模块自检 12/12 全绿", ok_mod)

    print("\n[B] 关键事实")
    check("B1 R□(M1) = ρ/t = %.4f Ω/□" % AN_SHEET_M1, _sheet_ok())
    check("B2 🔴 `R·C` 与线宽**无关**（值 %.6f · 4 档 W 偏差 <1e-12）⇒ 加宽只换静态 IR"
          % AN_RC, _rc_invariant_ok())
    check("B3 🔴 `C` 与金属厚度**无关**（值 %.6f · 5 层偏差 0）⇒ **换层是纯收益**"
          % AN_C, _c_vs_t_ok())
    check("B4 六方案 N 上界 = %s" % AN_N, _plans_ok())
    check("B5 🔴 推荐方案 N=%d · vs Mythic %.1f× · 代价 C%.2f× / +%.2fpp"
          % (AN_BEST_N, AN_BEST_VS, AN_BEST_COST_C, AN_BEST_DPP), _best_ok())
    check("B6 基准对照 N=%d · vs Mythic %.1f×（**天花板起点**）"
          % (AN_BASE_N, AN_BASE_VS), _base_ok())
    check("B7 双端驱动 `r_eff/r ≡ 0.25`（IR ∝ N²/8 vs N²/2）", _dual_ok())
    check("B8 行线功耗份额随方案推进单调上升：%s %%（**代价必须同屏**）" % AN_SHARES,
          _cost_reported_ok())
    check("B9 cost_model 同时报物理/工艺/未建模项，且**明写未做 DRC/LVS**", _cost_model_ok())
    check("B10 全部输出恒标 `MODEL_ESTIMATE`",
          R.plan_table()[0]["tier"] == "MODEL_ESTIMATE")

    # ------------------------------------------------------------------
    # C 突变探针
    # ------------------------------------------------------------------
    print("\n[C] 反向可证伪探针")

    # C1：让 C 依赖 t（伪装"厚金属电容更大"）⇒ B3 必红
    _real_seg = R.seg_rc

    def _c_dep_t(layer="m1", width_um=0.40, pitch_um=None, proc=None):
        r = _real_seg(layer, width_um, pitch_um, proc)
        return {**r, "c_seg_fF": r["c_seg_fF"] * (r["t_um"] / 0.20)}

    with mock.patch.object(R, "seg_rc", _c_dep_t):
        c1 = not _c_vs_t_ok()
    check("C1 探针：让 C 依赖金属厚度（伪装「厚金属电容更大」）⇒ B3 必红", c1)

    # C2：让 R 不依赖 W ⇒ B4/B5 的 W 档失效 ⇒ A1 的判据② 必红
    def _r_no_w(layer="m1", width_um=0.40, pitch_um=None, proc=None):
        r = _real_seg(layer, width_um, pitch_um, proc)
        return {**r, "r_seg_ohm": 0.504, "rc_product": 0.504 * r["c_seg_fF"]}

    with mock.patch.object(R, "seg_rc", _r_no_w):
        c2 = not _sheet_ok() or not R.row_metal_self_check()
    check("C2 探针：让 R 不依赖线宽（R≡常数）⇒ 模块自检必红", c2)

    # C3：双端写成 r/2（漏掉电流分摊）⇒ B7 必红
    with mock.patch.object(R, "DRIVE_MODES",
                           [{"id": "single", "name": "单端驱动", "r_factor": 1.0, "why": ""},
                            {"id": "dual", "name": "双端驱动", "r_factor": 0.5, "why": ""}]):
        c3 = not _dual_ok()
    check("C3 探针：双端驱动写成 `r/2`（漏掉两端电流分摊）⇒ B7 必红", c3)

    # C4：隐藏代价（所有方案 cost_c ≡ 1、份额不变）⇒ B8 必红
    _real_plans = R.plan_table()

    def _hidden_cost(budget_pct=5.0):
        return [{**p, "cost_c": 1.0, "row_line_share": 0.0009} for p in _real_plans]

    with mock.patch.object(R, "plan_table", _hidden_cost):
        c4 = not _cost_reported_ok()
    check("C4 探针：隐藏代价（cost_c≡1、份额不升）⇒ B8 必红", c4)

    # C5：把 N 上界写成与 r 无关 ⇒ 模块自检判据⑦ 必红
    with mock.patch.object(R, "n_ceiling_for",
                           lambda r_seg, budget_pct=5.0, scan_hi=512: {
                               "r_seg_ohm": float(r_seg), "n_max": 12,
                               "n_max_ir_only": 18, "saturated": False,
                               "scan_hi": 512, "budget_pct": float(budget_pct),
                               "tier": "MODEL_ESTIMATE"}):
        c5 = not R.row_metal_self_check()
    check("C5 探针：把 N 上界写成与 r 无关（N≡12）⇒ 模块自检判据⑦ 必红", c5)

    check("C6 全部探针还原后，模块自检与关键事实仍全绿",
          R.row_metal_self_check() and _plans_ok() and _best_ok())

    # ------------------------------------------------------------------
    print("\n[K] CI 登记")
    ci = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_ecore_e28_smoke.py" in ck)

    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    print()
    for name, ok, detail in _results:
        print(("[PASS] " if ok else "[FAIL] ") + name + (("  :: " + detail) if detail else ""))
    print()
    print("=" * 74)
    print("E28 门禁结果：%d PASS / %d FAIL（共 %d 判据 · 含 5 突变探针）"
          % (npass, nfail, len(_results)))
    print("=" * 74)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
