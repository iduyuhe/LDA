# -*- coding: utf-8 -*-
"""E15 端到端误差预算链门禁（D-180 · v0.9.161）。

═══════════════════════════════════════════════════════════════════════════
判什么（分节）
═══════════════════════════════════════════════════════════════════════════
A 模块自检（`budget.run_selfchecks` **12 项**）
B 关键事实 name-first：口径桥闭式 · 退化闭式（3 类）· RSS · 8×8 报告实测值 ·
  精度 vs N 六点 · **主导项交叉点** · 全链上界 · 🔴 **与 E9 逐值一致（G7）** · 保护性约束
C 反向可证伪：**5 条突变探针**（口径桥系数错 / 随机项代数相加 / 有界项 RSS /
  丢 systematic / 主导项排序反转）⇒ 均必红 + **还原重跑**
K 自入 CI core（防静默漏接 · 血案 #28）

═══════════════════════════════════════════════════════════════════════════
🔴 本门禁的核心价值
═══════════════════════════════════════════════════════════════════════════
本段是「把 E1–E14 串成一个答案」的合成段，**最怕的是合成律本身错而无人知**：

  · **退化闭式**是最关键的可证伪点 —— 只留一类误差时，合成**必须**退化为该类闭式。
    合成律写错（如随机项用代数相加、有界项用 RSS）在"混合"情形下**看不出来**
    （只是数值略偏），**只有在退化情形才暴露** ⇒ 必须逐类测。
  · **G7（与 E9 逐值一致）**证明本段**不是另起一套模型**，而是 E9 的严格泛化
    （仅 IR drop ⇒ 委托 E9 ⇒ 逐值相等）。没有这条，"泛化"只是自说自话。
  · **保护性约束（G8）**：本段只读消费 E7/E8/E9/E14 ⇒ 必须证明**没改坏任何既有模块**。

🔴 两处口径纪律（本段最容易踩）：
  1. IR drop 项取 **`avg_rel_err`（全列平均）** 而非 `max_rel_err`（最坏列）——
     后者与 E9 的预算口径不一致（E9 通则 1：口径不同 ≠ 模型错）。
  2. `output_effective_bits` **不是 IEEE ENOB**（自定义量，口径 = log2(100/最坏相对误差[%])）。
"""

from __future__ import annotations

import math
import os
import sys
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import array_scale as AS       # noqa: E402
from lda_l2.ecore import budget as B             # noqa: E402
from lda_harness.smoke_kit import make_result_collector

_results: list = []


check = make_result_collector(_results)


# ── 复用的绿色判据（突变探针也调同一份 —— 保证"打的判据"就是"守的判据"）──────
def _bridge_ok() -> bool:
    """G1 口径桥自洽 + 逆向可逆。"""
    return (abs(B.lsb_to_rel_pct(8) - 0.390625) < 1e-12
            and all(abs(B.output_effective_bits(B.lsb_to_rel_pct(k)) - k) < 1e-12
                    for k in range(4, 13))
            and all(abs(B.rel_pct_to_lsb(B.lsb_to_rel_pct(k), k) - 1.0) < 1e-12
                    for k in range(4, 13)))


def _degenerate_ok() -> bool:
    """G2 退化闭式：只留一类误差 ⇒ 合成退化为该类闭式。

    🔴 随机项与有界项**必须各用 ≥2 个成员**！单成员时 `Σ` 与 `√(Σ²)` **恒等**
    （都等于该值）⇒ 合成律里「RSS vs 代数相加」「Σ|b| vs √(Σb²)」这两种错法
    **在单成员下不可区分** ⇒ 判据对该机制不敏感 ⇒ 突变探针会变成**假探针**
    （E8 通则「判据必须只对被测机制敏感」/ E14 C6 同族）。本段实测确认：初版用单成员，
    C3 探针**确实没红**。
    """
    s = B.combine([B.make_term("s", B.SYSTEMATIC, 3.0, "t")])
    r = B.combine([B.make_term("r1", B.RANDOM, 3.0, "t"),
                   B.make_term("r2", B.RANDOM, 4.0, "t")])    # RSS: √(9+16)=5 ≠ 代数 7
    b = B.combine([B.make_term("b1", B.BOUNDED, 1.0, "t"),
                   B.make_term("b2", B.BOUNDED, 2.0, "t")])    # Σ: 3 ≠ RSS √5≈2.236
    return (abs(s["worst_pct"] - 3.0) < 1e-12 and abs(s["typical_pct"] - 3.0) < 1e-12
            and abs(r["worst_pct"] - 15.0) < 1e-12 and abs(r["typical_pct"] - 5.0) < 1e-12
            and abs(b["worst_pct"] - 3.0) < 1e-12
            and abs(b["typical_pct"] - 3.0 / math.sqrt(3.0)) < 1e-12)


def _rss_ok() -> bool:
    """G2b 随机项必须是 RSS（不是代数相加）。"""
    t = B.combine([B.make_term("r1", B.RANDOM, 3.0, "t"),
                   B.make_term("r2", B.RANDOM, 4.0, "t")])
    return abs(t["random_sigma_pct"] - 5.0) < 1e-12


def _report_8x8_ok() -> bool:
    """G3+G4：8×8 报告的实测锚值（下界性 / 有序性由 combine 内部保证）。"""
    rep = B.error_budget_report(8, 8)
    names = sorted(t["name"] for t in rep["terms"])
    return (names == ["adc_quantization", "adc_sar", "dac_inl",
                      "device_mismatch", "ir_drop", "row_driver_load"]
            and abs(rep["worst_pct"] - 4.06012) < 0.01
            and abs(rep["worst_bits"] - 4.622) < 0.02
            and rep["worst_pct"] >= rep["typical_pct"] > 0.0)


def _curve_ok() -> bool:
    """G5：精度 vs N 六点实测锚 + **主导项交叉点存在**。"""
    c = B.budget_vs_n([8, 16, 32, 64, 128, 256], budget_pct=5.0)
    pts = {p["n"]: p for p in c["points"]}
    xs = [p["n"] for p in c["points"]]
    mono = all(pts[xs[i]]["worst_pct"] <= pts[xs[i + 1]]["worst_pct"] + 1e-9
               for i in range(len(xs) - 1))
    cross = (pts[8]["dominant"] == "device_mismatch"
             and pts[32]["dominant"] == "ir_drop")
    return (len(c["points"]) == 6 and mono and cross
            and abs(pts[8]["worst_bits"] - 4.622) < 0.02
            and abs(pts[256]["worst_pct"] - 84.1844) < 0.5)


def _e9_consistent_ok() -> bool:
    """G7 🔴 仅 IR drop ⇒ 与 E9 `max_scale_for_budget` 逐值相等（泛化必须退化为特例）。"""
    r_seg = B.row_segment_resistance(8, 8)
    g = B.cell_conductance(2.5)
    mine = B.max_scale_full_chain(5.0, ir_drop_only=True)
    e9 = int(AS.max_scale_for_budget(0.05, r_seg, g))
    return (mine["method"] == "delegated_to_E9" and mine["n_max"] == e9)


def _protection_ok() -> bool:
    """G8 🔴 保护性约束：E7/E8/E9/E14 既有默认值与闭式逐位不变。"""
    return (AS.elements_flat(8, 8) == 8 * 8 * 7 + 16
            and AS.elements_hierarchical(8, 8) == 7 + 1 + 16
            and abs(B.lsb_to_rel_pct(8) - 100.0 / 256.0) < 1e-15
            and abs(B.cell_conductance(2.5) - (120e-6 * 4.0 * (2.5 - 0.4))) < 1e-15)


# ══════════════════════════════════════════════════════════════════════════
def main() -> int:
    print("=" * 74)
    print("E15 端到端误差预算链门禁（D-180 · 合成律 + 口径桥 + 泛化上界）")
    print("=" * 74)

    # ── A 模块自检 ──────────────────────────────────────────────────────
    ok_a = B.run_selfchecks(verbose=False)
    check("A1 模块自检 12/12 PASS（口径桥自洽/可逆 · 退化三类 · RSS · 下界性 · 有序性 · "
          "位数单调 · 主导项识别 · 端到端报告 · 保护性约束）", ok_a)

    # ── B 关键事实 ─────────────────────────────────────────────────────
    check("B1 🔴 口径桥闭式：lsb_to_rel_pct(8) == 0.390625（1 LSB @ 8bit 的 %FS）",
          abs(B.lsb_to_rel_pct(8) - 0.390625) < 1e-12)
    check("B2 🔴 口径桥自洽 + 可逆（k=4..12）：bits_eff(lsb_to_rel_pct(k)) == k",
          _bridge_ok())
    check("B3 🔴 退化闭式（3 类各一）：仅系统 ⇒ worst=typ=该项 · 仅随机 ⇒ kσ/σ · "
          "仅有界 ⇒ b 与 b/√3", _degenerate_ok())
    check("B4 🔴 随机项 RSS：√(3²+4²) == 5.0（**非**代数相加 7.0）", _rss_ok())

    rep = B.error_budget_report(8, 8)
    check("B5 8×8 报告 = 6 项误差 · worst 4.0601% · bits_eff 4.622（实测锚）",
          _report_8x8_ok())
    dm = rep["dominant"]
    check("B6 8×8 主导项 = device_mismatch（44.0%）· 排序含全部 6 项",
          dm["name"] == "device_mismatch" and abs(dm["share_pct"] - 44.0) < 1.0
          and len(dm["ranking"]) == 6)

    c = B.budget_vs_n([8, 16, 32, 64, 128, 256], budget_pct=5.0)
    check("B7 精度 vs N 六点：worst 随 N 单调非降（4.06 → 84.18%）· bits 4.622 → 0.248",
          _curve_ok())

    pts = {p["n"]: p for p in c["points"]}
    check("B8 🔴 **主导项交叉点存在**：N=8 由「器件失配」主导 · N=32 由「IR drop」主导"
          "（← 本段最有价值的结论：小 N 失配主导 / 大 N IR drop 主导）",
          pts[8]["dominant"] == "device_mismatch" and pts[32]["dominant"] == "ir_drop")

    full = B.max_scale_full_chain(5.0)
    only = B.max_scale_full_chain(5.0, ir_drop_only=True)
    check("B9 全链可及上界（5% 预算）= N≤12（扫描法 · 因 worst(N) 未必单调 ⇒ 不用二分）",
          full["method"] == "scan" and full["n_max"] == 12 and not full["saturated"])

    check("B10 🔴 **与 E9 逐值一致（G7）**：仅 IR drop ⇒ 委托 E9 ⇒ n_max == 18（逐值相等）",
          _e9_consistent_ok() and only["n_max"] == 18)

    check("B11 🔴 全链预算**严格于**仅 IR drop 口径（12 < 18 ⇒ E9 的「5%⇒N≤18」是"
          "**乐观的**：漏计失配/行驱动/转换器后只能到 12）",
          full["n_max"] < only["n_max"])

    check("B12 🔴 保护性约束（G8）：E7/E8/E9/E14 既有默认值与闭式**逐位不变**",
          _protection_ok())

    # ── C 反向可证伪（突变探针）────────────────────────────────────────
    print("-" * 74)
    print("C 反向可证伪（突变探针）：每条都必须能把对应判据打红")
    print("-" * 74)

    # C1 口径桥系数写错：100/2^k → 100/k
    with mock.patch.object(B, "lsb_to_rel_pct", lambda bits: 100.0 / float(int(bits))):
        c1 = not _bridge_ok()
    check("C1 反向：口径桥系数写错（100/2^k → 100/k）⇒ B1/B2 必红", c1)

    # C2 随机项用代数相加（不 RSS）
    def _bad_combine_algebraic(terms, k_sigma=B.DEFAULT_K_SIGMA):
        s = sum(float(t["rel_pct"]) for t in terms if t["category"] == B.SYSTEMATIC)
        r = sum(float(t["rel_pct"]) for t in terms if t["category"] == B.RANDOM)
        b = sum(float(t["rel_pct"]) for t in terms if t["category"] == B.BOUNDED)
        w, ty = s + float(k_sigma) * r + b, s + r + b / math.sqrt(3.0)
        return {"systematic_pct": s, "random_sigma_pct": r, "bounded_pct": b,
                "worst_pct": w, "typical_pct": ty,
                "worst_bits": B.output_effective_bits(w),
                "typical_bits": B.output_effective_bits(ty), "n_terms": len(terms)}

    with mock.patch.object(B, "combine", _bad_combine_algebraic):
        c2 = not (_degenerate_ok() and _rss_ok())
    check("C2 反向：随机项用**代数相加**（不做 RSS）⇒ B3/B4 必红"
          "（混合情形看不出来，只有退化情形暴露 —— 这正是退化判据的价值）", c2)

    # C3 有界项用 RSS（而非代数相加）
    def _bad_combine_bnd_rss(terms, k_sigma=B.DEFAULT_K_SIGMA):
        s = sum(float(t["rel_pct"]) for t in terms if t["category"] == B.SYSTEMATIC)
        sig = math.sqrt(sum(float(t["rel_pct"]) ** 2 for t in terms if t["category"] == B.RANDOM))
        b = math.sqrt(sum(float(t["rel_pct"]) ** 2 for t in terms if t["category"] == B.BOUNDED))
        w, ty = s + float(k_sigma) * sig + b, s + sig + b / math.sqrt(3.0)
        return {"systematic_pct": s, "random_sigma_pct": sig, "bounded_pct": b,
                "worst_pct": w, "typical_pct": ty,
                "worst_bits": B.output_effective_bits(w),
                "typical_bits": B.output_effective_bits(ty), "n_terms": len(terms)}

    with mock.patch.object(B, "combine", _bad_combine_bnd_rss):
        c3 = not _degenerate_ok()
    check("C3 反向：有界项用 **RSS**（Σ|b| → √(Σb²)）⇒ B3 退化判据必红", c3)

    # C4 合成丢掉 systematic 项
    def _bad_combine_drop_sys(terms, k_sigma=B.DEFAULT_K_SIGMA):
        sig = math.sqrt(sum(float(t["rel_pct"]) ** 2 for t in terms if t["category"] == B.RANDOM))
        b = sum(float(t["rel_pct"]) for t in terms if t["category"] == B.BOUNDED)
        w, ty = float(k_sigma) * sig + b, sig + b / math.sqrt(3.0)
        return {"systematic_pct": 0.0, "random_sigma_pct": sig, "bounded_pct": b,
                "worst_pct": w, "typical_pct": ty,
                "worst_bits": B.output_effective_bits(w),
                "typical_bits": B.output_effective_bits(ty), "n_terms": len(terms)}

    with mock.patch.object(B, "combine", _bad_combine_drop_sys):
        c4 = not (_degenerate_ok() and _report_8x8_ok())
    check("C4 反向：合成**丢掉 systematic 项** ⇒ B3/B5 必红（下界性被破坏）", c4)

    # C5 主导项排序反转
    def _bad_dominant(terms, k_sigma=B.DEFAULT_K_SIGMA):
        terms = list(terms)
        if not terms:
            return None
        sc = sorted(((B._worst_contribution(t, k_sigma), t) for t in terms),
                    key=lambda p: p[0])            # 升序 = 反转（错）
        return {"name": sc[0][1]["name"], "category": sc[0][1]["category"],
                "contribution_pct": sc[0][0], "share_pct": 0.0,
                "ranking": [{"name": t["name"], "category": t["category"],
                             "contribution_pct": s} for s, t in sc]}

    with mock.patch.object(B, "dominant_term", _bad_dominant):
        c5 = not (_report_8x8_ok() and _curve_ok())
    check("C5 反向：主导项排序**反转** ⇒ B6/B8 必红（交叉点结论被破坏）", c5)

    # 还原重跑（无残留漂移）
    check("C6 还原完整性：全部探针退出后，A1 自检 + B5/B8/B10 复跑仍全绿",
          B.run_selfchecks(verbose=False) and _report_8x8_ok()
          and _curve_ok() and _e9_consistent_ok())

    # ── K 自入 CI core ────────────────────────────────────────────────
    ci = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_ecore_e15_smoke.py" in ck)

    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    print()
    for name, ok, detail in _results:
        print("  [%s] %s%s" % ("PASS" if ok else "FAIL", name,
                               ("   (%s)" % detail) if (detail and not ok) else ""))
    print()
    print("RESULT: %d PASS / %d FAIL" % (npass, nfail))
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
