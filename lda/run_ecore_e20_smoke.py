# -*- coding: utf-8 -*-
"""E20 规模/误差口径归零门禁（D-195 · v0.9.316）。

═══════════════════════════════════════════════════════════════════════════
判什么（分节）
═══════════════════════════════════════════════════════════════════════════
A 模块自检（`scale_basis.scale_basis_self_check` **17 项**）
B 关键事实 name-first（14 条）：
  · 解析金标（闭式 ⟷ Thomas）· 5% 预算成对（仅IR 18 / 全链 12）·
  🔴 **对外载体逐点对拍**（卡 tiers × 4 / 卡 ceiling × 4 / 卡 full_chain × 4）——
    这三组此前**从未与底层模块对拍过**（只判过"登记齐全"与硬编码对硬编码）；
  · 卡片每档口径标注（basis / far 并报）· 卡 note 两端数字都在 ·
  · 列线电阻贡献 +29.8%~+40.7%（**推翻「二阶项」旧措辞**）· E7 卡片三点可复现 ·
  · G-I 边界文案已换代（不得静默回退成「二阶项」）· 模块披露同样换代 ·
  · 只读纪律（E7/E9/E15 默认值未变）· 诚实（无肯定性 TOPS 宣称）
C 反向可证伪：**6 条突变探针**（卡片数值错 / 抹 basis / ceiling 冒充全链 /
  清空成对声明 / 列线贡献置零 / G-I 回退旧措辞）⇒ 均必红 + **还原重跑**
K 自入 CI core（防静默漏接 · 血案 #28）

═══════════════════════════════════════════════════════════════════════════
🔴 本门禁的核心价值（不是"补一个模块"，是**把对外数字钉死在底层能力上**）
═══════════════════════════════════════════════════════════════════════════
1. **闭合三处真缺陷**（均实测确证，非推测）：
   ① 对外载体口径未标注（`SCALE_CEILING` 单值 ⇒ 读者分不清"仅IR"与"全链"）
   ② 对外载体不可复现的陈旧值（`SCALE_PRESSURE_TIERS` 的 N=64/256 两点，
      与当前默认参数下 **avg / far 两个口径都对不上**；参数自 E7/E9 起从未变更）
   ③ 门禁只判存在性不判数值（`compression_1024` 是硬编码对硬编码）
2. 🔴 **推翻一条已发布的披露措辞**：「1D 忽略列线电阻是**二阶项**」**不成立** ——
   实测该省略使最坏列压降低估 **+29.8%（N=32）~ +40.7%（N=8）**，是**主导修正**。
   本门禁同时守住文案**不得静默回退**（C6）。
3. **对外规模数字必须成对**：5% 预算 ⇒ 仅 IR **18 行** / 全链 **12 行**，
   单报其一即虚报能力（C3 探针守此）。
4. 🔴 **只读纪律**：`scale_basis` 只读消费 E7/E9/E15，**不改**任何既有默认值
   （B13 逐位核 `ELEC_PROCESS` / `DEFAULT_CELL_PARAMS`）。
"""
from __future__ import annotations

import os
import sys
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import array_scale as AS          # noqa: E402
from lda_l2.ecore import layout as LY              # noqa: E402
from lda_l2.ecore import parasitic as PA           # noqa: E402
from lda_l2.ecore import scale_basis as SB         # noqa: E402
from lda_webui import ecore_case as EC             # noqa: E402
from lda_harness.smoke_kit import make_result_collector  # noqa: E402

_results: list = []
check = make_result_collector(_results)

# ── 实测锚（本机默认几何 ‖ 默认器件档 vg=2.5 · 由 scale_basis 现算，非手填）──
AN_CEIL_5PCT_IR = 18          # 5% 预算 · 仅 IR-drop 的可及行数
AN_CEIL_5PCT_FULL = 12        # 5% 预算 · 全链的可及行数
AN_COL_LIFT_LO = 0.298        # 列线电阻贡献下界（N=32）
AN_COL_LIFT_HI = 0.407        # 列线电阻贡献上界（N=8）


# ══════════════════════════════════════════════════════════════════════════
# 复用的绿色判据（突变探针也调同一份 —— 保证「打的判据」就是「守的判据」）
# ══════════════════════════════════════════════════════════════════════════
def _card_tiers_ok() -> bool:
    """B3 · 卡片 `SCALE_PRESSURE_TIERS.ir_drop_rel` ≡ 现算 avg（逐点相对差 < 1e-4）。"""
    computed = {t["n"]: t for t in SB.card_pressure_tiers()}
    for row in EC.SCALE_PRESSURE_TIERS:
        c = computed.get(row["n"])
        if c is None:
            return False
        if abs(row["ir_drop_rel"] - c["ir_drop_rel"]) / c["ir_drop_rel"] > 1e-4:
            return False
        if abs(row["ir_far_drop_rel"] - c["ir_far_drop_rel"]) / c["ir_far_drop_rel"] > 1e-4:
            return False
    return True


def _card_basis_ok() -> bool:
    """B4 · 卡片每档都标 `basis == ir_avg_rel_err` 且并报 `ir_far_drop_rel` > 0。"""
    return all(r.get("basis") == "ir_avg_rel_err"
               and r.get("ir_far_drop_rel", 0.0) > 0.0
               for r in EC.SCALE_PRESSURE_TIERS)


def _ceil_ir_ok() -> bool:
    """B5 · 卡片 `SCALE_CEILING` ≡ 现算 max_rows_ir_only（逐档相等）。"""
    comp = {round(x["budget_rel"], 6): x["max_rows_ir_only"]
            for x in SB.scale_ceiling_paired()}
    return all(comp.get(round(r["budget_rel"], 6)) == r["max_rows"]
               and r.get("basis") == "max_rows_ir_only"
               for r in EC.SCALE_CEILING)


def _ceil_fc_ok() -> bool:
    """B6 · 卡片 `SCALE_CEILING_FULL_CHAIN` ≡ 现算 max_rows_full_chain（逐档相等）。"""
    comp = {round(x["budget_rel"], 6): x["max_rows_full_chain"]
            for x in SB.scale_ceiling_paired()}
    return all(comp.get(round(r["budget_rel"], 6)) == r["max_rows"]
               and r.get("basis") == "max_rows_full_chain"
               for r in EC.SCALE_CEILING_FULL_CHAIN)


def _note_has_both(note: str) -> bool:
    return ("18" in note) and ("12" in note) and ("成对" in note) and ("全链" in note)


def _col_lift_ok() -> bool:
    """B8 · 列线电阻贡献全部在 +29.8%~+40.7%，且无任何一档被判「二阶小量」。"""
    sweep = SB.col_contribution_sweep()
    return (all(AN_COL_LIFT_LO - 5e-3 < x["rel_lift"] < AN_COL_LIFT_HI + 5e-3 for x in sweep)
            and not any(x["is_second_order_small"] for x in sweep))


def _e7_card_ok() -> bool:
    """B9 · E7 卡片 IR drop 三点 ≡ 现算含列线 2D（容差 5e-3 = 卡片 2~3 位有效数字）。"""
    card = {4: 0.0042, 16: 0.0806, 32: 0.270}     # PARASITIC_FACTS["ir_drop_rel"]
    sweep = {x["n"]: x for x in SB.col_contribution_sweep()}
    return all(abs(sweep[n]["far_2d_with_col"] - v) / v < 5e-3 for n, v in card.items())


def _gi_text_renewed() -> bool:
    """B10 · G-I 边界文案已换代：含「+29.8%」与「非二阶小量」/「不是二阶小量」。"""
    for g in EC.GAPS:
        if g.get("id") == "G-I":
            blob = (g.get("title", "") + g.get("status", "") + g.get("detail", ""))
            return ("29.8" in blob) and ("二阶小量" in blob)
    return False


def _disclosure_renewed() -> bool:
    """B11 · `SCALE_DISCLOSURE.omission` 已换代（不得只剩「二阶项」）。"""
    om = AS.SCALE_DISCLOSURE.get("omission", "")
    return ("29.8" in om) and ("不是二阶小量" in om)


def _readonly_ok() -> bool:
    """B13 · 只读纪律：E7/E9 的默认工艺与几何逐位未变（含 r_leak 数值钉扎值）。"""
    return (PA.ELEC_PROCESS["r_leak_ohm"] == 1.0e9
            and PA.ELEC_PROCESS["rho_cu_ohm_um"] == 1.68e-2
            and PA.ELEC_PROCESS["t_m1_um"] == 0.20
            and PA.ELEC_PROCESS["eps_r_ild"] == 3.9
            and LY.DEFAULT_CELL_PARAMS["w_um"] == 1.20
            and LY.DEFAULT_CELL_PARAMS["l_um"] == 0.30
            and LY.DEFAULT_CELL_PARAMS["row_w_um"] == 0.40)


def _no_false_claim_ok() -> bool:
    """B14 · 诚实：模块/门禁披露不得出现**肯定性** TOPS 宣称（否定式不算违规）。"""
    blob = SB.SCALE_BASIS_DISCLOSURE["honest"] + SB.SCALE_BASIS_DISCLOSURE["red_line"]
    forbid = ["已报 TOPS", "已含能效", "达到 TOPS/W", "fJ/op 已实测"]
    return not any(s in blob for s in forbid)


# ══════════════════════════════════════════════════════════════════════════
def main() -> int:
    print("=" * 74)
    print("E20 规模/误差口径归零门禁（D-195）")
    print("=" * 74)

    # ── A 模块自检 ────────────────────────────────────────────────────
    print("\n── A 模块自检 ──")
    ok_a = SB.scale_basis_self_check(verbose=True)
    check("A1 scale_basis 自检 17/17（解析金标/双口径序/成对约束/反向完备/列线贡献）", ok_a)

    # ── B 关键事实 name-first ─────────────────────────────────────────
    print("\n── B 关键事实 ──")
    d64 = SB.dual_ir_basis(64)
    check("B1 解析闭式 ⟷ Thomas 数值解一致（N=64 · far 绝对差 < 1e-9）",
          abs(d64["ir_far_drop_rel"] - d64["closed_form"]["far_drop_rel"]) < 1e-9,
          "far=%.9f vs 闭式 %.9f" % (d64["ir_far_drop_rel"],
                                     d64["closed_form"]["far_drop_rel"]))

    paired = SB.scale_ceiling_paired()
    p5 = [x for x in paired if abs(x["budget_rel"] - 0.05) < 1e-12][0]
    check("B2 🔴 5% 预算成对：仅IR=18 行 / 全链=12 行（**两个数都现算可复现**）",
          p5["max_rows_ir_only"] == AN_CEIL_5PCT_IR
          and p5["max_rows_full_chain"] == AN_CEIL_5PCT_FULL,
          "ir=%d full=%d tighter=%s" % (p5["max_rows_ir_only"],
                                        p5["max_rows_full_chain"], p5["tighter"]))

    check("B3 🔴 对外载体对拍①：卡片 tiers ×4 ≡ 现算 avg/far（相对差 < 1e-4）"
          "（**此前从未对拍过**）", _card_tiers_ok())
    check("B4 对外载体对拍②：卡片每档标 basis + 并报 ir_far_drop_rel（口径不可省）",
          _card_basis_ok())
    check("B5 🔴 对外载体对拍③：卡片 SCALE_CEILING ×4 ≡ 现算 max_rows_ir_only",
          _ceil_ir_ok())
    check("B6 🔴 对外载体对拍④：卡片 SCALE_CEILING_FULL_CHAIN ×4 ≡ 现算 max_rows_full_chain",
          _ceil_fc_ok())

    note = EC.case_card()["scale_pressure"]["note"]
    check("B7 卡 note 两端数字都在（18 与 12）且明说「成对」与「全链」",
          _note_has_both(note), note[:60] + "…")

    sweep = SB.col_contribution_sweep()
    check("B8 🔴 列线电阻贡献 +29.8%~+40.7% ⇒ **推翻「二阶项」**（全档非二阶小量）",
          _col_lift_ok(),
          " / ".join("N=%d:%+.1f%%" % (x["n"], x["rel_lift"] * 100) for x in sweep))

    check("B9 E7 卡片 IR drop 三点（0.42%/8.06%/27.0%）≡ 现算含列线 2D（<5e-3）",
          _e7_card_ok())
    check("B10 🔴 G-I 边界文案已换代（含 29.8% + 非二阶小量 · **不得静默回退**）",
          _gi_text_renewed())
    check("B11 `SCALE_DISCLOSURE.omission` 已换代（含 29.8% + 「不是二阶小量」）",
          _disclosure_renewed())

    cov = SB.basis_coverage_report()
    check("B12 反向完备：%d 条口径全部解析到真实可调用对象" % len(SB.SCALE_BASIS),
          len(cov["ok"]) == len(SB.SCALE_BASIS) and not cov["missing"],
          str(cov["declared"]))

    check("B13 只读纪律：ELEC_PROCESS / DEFAULT_CELL_PARAMS 逐位未变", _readonly_ok())
    check("B14 诚实：披露无**肯定性** TOPS/能效宣称（否定式不算违规）", _no_false_claim_ok())

    # ── C 反向可证伪（突变探针）───────────────────────────────────────
    print("\n── C 反向可证伪 ──")

    bad_tiers = [dict(r) for r in EC.SCALE_PRESSURE_TIERS]
    bad_tiers[1]["ir_drop_rel"] = 0.152           # 回填历史陈旧值
    with mock.patch.object(EC, "SCALE_PRESSURE_TIERS", bad_tiers):
        c1 = not _card_tiers_ok()
    check("C1 探针：把卡 tiers 回填成历史陈旧值 0.152 ⇒ B3 必红", c1)

    no_basis = [dict(r) for r in EC.SCALE_PRESSURE_TIERS]
    no_basis[2].pop("basis", None)
    with mock.patch.object(EC, "SCALE_PRESSURE_TIERS", no_basis):
        c2 = not _card_basis_ok()
    check("C2 探针：抹掉某档 basis（口径丢失）⇒ B4 必红", c2)

    fake_ceil = [dict(r) for r in EC.SCALE_CEILING]
    fake_ceil[1]["max_rows"] = AN_CEIL_5PCT_FULL      # 18 → 12（少报）
    with mock.patch.object(EC, "SCALE_CEILING", fake_ceil):
        c3a = not _ceil_ir_ok()
    fake_ceil2 = [dict(r) for r in EC.SCALE_CEILING]
    fake_ceil2[1]["max_rows"] = 26                    # 18 → 26（**虚报能力**）
    with mock.patch.object(EC, "SCALE_CEILING", fake_ceil2):
        c3b = not _ceil_ir_ok()
    check("C3 探针：ceiling 改小或**改大冒充更大能力** ⇒ B5 必红（双向）", c3a and c3b,
          "改小变红=%s · 虚报变红=%s" % (c3a, c3b))

    saved = SB.SCALE_BASIS[0]["must_pair_with"]
    SB.SCALE_BASIS[0]["must_pair_with"] = []
    try:
        c4 = not SB.pairing_report()["consistent"]
    finally:
        SB.SCALE_BASIS[0]["must_pair_with"] = saved
    check("C4 探针：清空成对声明（只剩单口径）⇒ pairing 判据必红", c4)

    with mock.patch.object(PA, "ir_drop_report",
                           lambda *a, **k: {"max_rel_err": 0.0}):
        c5 = not _col_lift_ok()
    check("C5 探针：把含列线 2D 结果置零（杀掉列线贡献）⇒ B8 必红", c5)

    saved_gaps = EC.GAPS
    patched = [dict(g) for g in EC.GAPS]
    for g in patched:
        if g.get("id") == "G-I":
            g["detail"] = "千级阵列的 IR-drop 用一维三对角线模型，**忽略列线电阻**（二阶项）。"
    with mock.patch.object(EC, "GAPS", patched):
        c6 = not _gi_text_renewed()
    EC.GAPS = saved_gaps
    check("C6 探针：G-I 文案回退成旧「二阶项」⇒ B10 必红（**防静默回退**）", c6)

    # 还原重跑
    check("C7 还原完整性：探针退出后自检 + B3/B5/B6/B8/B10/B11 复跑仍全绿",
          SB.scale_basis_self_check(verbose=False) and _card_tiers_ok()
          and _ceil_ir_ok() and _ceil_fc_ok() and _col_lift_ok()
          and _gi_text_renewed() and _disclosure_renewed())

    # ── K 自入 CI core ────────────────────────────────────────────────
    ci = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_ecore_e20_smoke.py" in ck)

    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    print()
    for name, ok, detail in _results:
        if not ok:
            print("FAIL | " + name + (("  :: " + detail) if detail else ""))
        elif detail:
            print("PASS | " + name + "  :: " + detail)
    print()
    print("=" * 74)
    print("E20 门禁结果：%d PASS / %d FAIL（共 %d 判据 · 含 6 突变探针）"
          % (npass, nfail, len(_results)))
    print("=" * 74)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
