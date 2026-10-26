# -*- coding: utf-8 -*-
"""E29 版图可行性门禁（D-204 · v0.9.325）。

═══════════════════════════════════════════════════════════════════════════
本段把 E28 的「算得通」用 E6 的真实版图能力验成「做不通」
═══════════════════════════════════════════════════════════════════════════
① 🔴 **「换 RDL 厚金属」在平台里不存在** —— E6 电子层栈只有 **7 层**
   （DIFF/POLY/CONT/M1/VIA1/M2/PAD），**无 M3+/AP/RDL/VIA2+**。
   E28 的 M6 级需 **+8 层**、RDL 级需 **+10 层** ⇒ 那两条路径**无法表达**。
② 🔴 **「加宽到 W0.80」被 DRC 否决** —— 实测临界线宽 **0.52 µm**
   （0.55 起 `M1 间距 0.225 < 0.230`，行线 vs **列线 M1 落垫**）⇒ 实际最大加宽 **×1.30**（非 ×2）。
   `pitch_y` 加大**不能解决**（冲突在同一单元内）。违规数 ≡ N² ⇒ **系统性布局冲突**。
③ 🔴 **平台 DRC 复杂度约 O(N⁴)** —— N=12→0.2s / 26→3.8s / 42→26.4s ⇒ N=125 估 **~7 小时**
   ⇒ **可签核规模受工具限制，不是物理限制**（真实 DRC 是 O(N log N)）。

⇒ **E28 的三条路径在现有版图能力下没有一条可直接落地。当前唯一 DRC/LVS 全 ACCEPT 的
配置仍然是原样（M1 · W0.40 · 单端 · N≤42）。**

判什么
  A 模块自检（`layout_feasibility.layout_feasibility_self_check` **12 项**）
  B 关键事实（11 条）：层栈 7 层 · 缺口 8/10 · 临界 0.52 · 首条 REJECT 具体文本 ·
    违规数 N² · DRC/LVS/GDS 矩阵 · 几何回提 ≡ 声明 · 三路径 realizable=0 ·
    DRC O(N⁴) · 双端不编数 · 输出档位
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

from lda_l2.ecore import layout as LY            # noqa: E402
from lda_l2.ecore import layout_feasibility as F  # noqa: E402
from lda_harness.smoke_kit import make_result_collector  # noqa: E402

_results: list = []
check = make_result_collector(_results)

# 现算锚值（v0.9.325）
AN_N_LAYERS = 7
AN_GAP_M6 = 8
AN_GAP_RDL = 10
AN_W_MAX = 0.52
AN_MAX_WIDEN = 1.30
AN_FIRST_REJECT = "M1 间距 0.225 < 0.230 µm（col0 / row0）"
AN_NS = [8, 12, 26]
AN_DRC_42_S = 26.4


def _rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b) if b else float("inf")


# ---------------------------------------------------------------------------
# B 关键事实
# ---------------------------------------------------------------------------
def _layers_ok() -> bool:
    cl = F.current_layers()
    return len(cl) == AN_N_LAYERS and {x["name"] for x in cl} == {
        "DIFF", "POLY", "CONT", "M1", "VIA1", "M2", "PAD"}


def _gap_ok() -> bool:
    lg = F.layer_gap()
    return (lg["rows"][0]["actually_missing"] == AN_GAP_M6
            and lg["rows"][1]["actually_missing"] == AN_GAP_RDL)


def _wmax_ok() -> bool:
    mw = F.max_drc_width()
    return (abs(mw["w_max_um"] - AN_W_MAX) < 1e-9
            and abs(mw["max_widen"] - AN_MAX_WIDEN) < 0.02)


def _first_reject_ok() -> bool:
    fr = F.max_drc_width()["first_reject"]
    return fr is not None and fr["first"] == AN_FIRST_REJECT


def _viol_n2_ok() -> bool:
    """B5 · 违规数 ≡ N²（系统性冲突）。"""
    d = LY.run_edrc(LY.crossbar_array(8, 8, {"row_w_um": 0.55})["descs"])
    return len(d["violations"]) == 8 * 8


def _matrix_ok() -> bool:
    mx = F.drc_matrix()
    return ([r["n"] for r in mx] == AN_NS
            and all(r["drc"] == "ACCEPT" and r["lvs"] == "ACCEPT"
                    and r["roundtrip_match"] is True for r in mx))


def _extract_ok() -> bool:
    """B7 · 几何回提宽度 ≡ 声明值（证明 DRC 不是因为参数没进几何）。"""
    mx = F.drc_matrix()
    return all(abs(r["row_width_extracted"] - 0.40) < 1e-12
               and r["row_paths"] == r["n"] for r in mx)


def _no_path_ok() -> bool:
    """B8 · 🔴 三条路径 realizable 全为 False（守"不得把算得通说成做得通"）。"""
    fp = F.feasible_paths()
    return fp["n_realizable"] == 0 and all(r["realizable"] is False for r in fp["rows"])


def _scaling_ok() -> bool:
    ds = F.drc_scaling()
    return (abs(ds["observed_42"]["elapsed_s"] - AN_DRC_42_S) < 1e-9
            and ds["observed_42"]["verdict"] == "ACCEPT"
            and ds["extrapolated"][-1]["pred_s"] > 1000.0)


def _dual_no_number_ok() -> bool:
    dd = F.dual_drive_cost()
    return dd["area_overhead_pct"] is None and dd["need_both_sides"] is True


def main() -> int:
    print("=" * 74)
    print("E29 版图可行性门禁（D-204）")
    print("=" * 74)

    print("\n[A] 模块自检（layout_feasibility.layout_feasibility_self_check）")
    ok_mod = F.layout_feasibility_self_check(verbose=True)
    check("A1 模块自检 12/12 全绿", ok_mod)

    print("\n[B] 关键事实")
    check("B1 平台层栈 = %d 层（DIFF/POLY/CONT/M1/VIA1/M2/PAD）· **无 M3+/RDL**"
          % AN_N_LAYERS, _layers_ok())
    check("B2 E28 换层缺口：M6 级 +%d 层 · RDL 级 +%d 层" % (AN_GAP_M6, AN_GAP_RDL),
          _gap_ok())
    check("B3 🔴 DRC 放行最大行线宽 = %.2f µm（基准 0.40 ⇒ 最大加宽 ×%.2f，非 ×2）"
          % (AN_W_MAX, AN_MAX_WIDEN), _wmax_ok())
    check("B4 首条 REJECT = `%s`" % AN_FIRST_REJECT, _first_reject_ok())
    check("B5 违规数 ≡ N²（N=8 时 64 ⇒ **系统性布局冲突**）", _viol_n2_ok())
    check("B6 N ∈ %s 全部 DRC/LVS ACCEPT + GDS roundtrip match" % AN_NS, _matrix_ok())
    check("B7 几何回提 `row_w` ≡ 声明 0.40（**DRC 是几何真那样画了**）", _extract_ok())
    check("B8 🔴 E28 三条路径 **realizable 全 False**（算得通 ≠ 做得通）", _no_path_ok())
    check("B9 🔴 DRC ~O(N⁴)：42 实测 %.1f s · N=125 外推 >1000 s" % AN_DRC_42_S,
          _scaling_ok())
    check("B10 双端驱动面积开销 **不编数**（未建版图 ⇒ None）", _dual_no_number_ok())
    check("B11 全部输出恒标 `MODEL_ESTIMATE`",
          F.drc_matrix()[0]["tier"] == "MODEL_ESTIMATE")

    # ------------------------------------------------------------------
    print("\n[C] 反向可证伪探针")

    # C1：把层栈说成含 RDL ⇒ B1 必红
    _real_cl = F.current_layers   # 🔴 必须先存原函数，否则 lambda 调用自己 ⇒ 无限递归

    with mock.patch.object(F, "current_layers",
                           lambda: _real_cl() + [{"gds_layer": 27, "name": "RDL",
                                                  "kind": "signal"}]):
        c1 = not _layers_ok()
    check("C1 探针：把层栈说成含 RDL（第 8 层）⇒ B1 必红", c1)

    # C2：把 W0.80 说成 ACCEPT ⇒ B3 必红
    _real_scan = F.drc_width_scan

    def _all_accept(n=8):
        return [{**r, "verdict": "ACCEPT", "n_viol": 0, "rules": [], "first": ""}
                for r in _real_scan(n)]

    with mock.patch.object(F, "drc_width_scan", _all_accept):
        c2 = not _wmax_ok()
    check("C2 探针：把 W0.80 说成 DRC ACCEPT（临界推到 0.60）⇒ B3 必红", c2)

    # C3：几何回提宽度与声明不符 ⇒ B7 必红
    _real_mx = F.drc_matrix()

    def _bad_extract():
        return [{**r, "row_width_extracted": 0.80} for r in _real_mx]

    with mock.patch.object(F, "drc_matrix", _bad_extract):
        c3 = not _extract_ok()
    check("C3 探针：几何回提写成 0.80（与声明 0.40 不符）⇒ B7 必红", c3)

    # C4：宣称路径可落地 ⇒ B8 必红
    with mock.patch.object(F, "feasible_paths", lambda: {
            "rows": [{"path": "x", "realizable": True}], "n_realizable": 1,
            "verdict": "可落地", "tier": "MODEL_ESTIMATE"}):
        c4 = not _no_path_ok()
    check("C4 探针：宣称「E28 路径可直接落地」⇒ B8 必红", c4)

    # C5：隐藏 DRC 复杂度（把 42 说成 2 s）⇒ B9 必红
    #   🔴 同样必须先存原函数：探针内不得调用被 patch 的同一名字（本文件 C1/C5 各踩一次）
    _real_ds = F.drc_scaling

    def _fast_scaling():
        ds = _real_ds()
        return {**ds, "observed_42": {**ds["observed_42"], "elapsed_s": 2.0}}

    with mock.patch.object(F, "drc_scaling", _fast_scaling):
        c5 = not _scaling_ok()
    check("C5 探针：把 N=42 的 DRC 耗时说成 2 s（隐藏 O(N⁴)）⇒ B9 必红", c5)

    check("C6 全部探针还原后，模块自检与关键事实仍全绿",
          F.layout_feasibility_self_check() and _matrix_ok() and _no_path_ok())

    # ------------------------------------------------------------------
    print("\n[K] CI 登记")
    ci = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_ecore_e29_smoke.py" in ck)

    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    print()
    for name, ok, detail in _results:
        print(("[PASS] " if ok else "[FAIL] ") + name + (("  :: " + detail) if detail else ""))
    print()
    print("=" * 74)
    print("E29 门禁结果：%d PASS / %d FAIL（共 %d 判据 · 含 5 突变探针）"
          % (npass, nfail, len(_results)))
    print("=" * 74)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
