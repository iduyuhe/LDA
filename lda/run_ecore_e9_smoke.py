"""电子计算芯片千级阵列规模压力与诚实对标 门禁 smoke（E9 · D-159）。

═══ 为什么要有这个 smoke ═══
E6 的 `crossbar_array` **物化** N²·7+2N 个几何对象、E7 的稠密 MNA 未知量 ~2NM —— 两者都只到 N≈32。
E9 换成 **O(N) 算法**（层次化 AREF 出图 + 一维三对角 IR-drop 求解）把规模推到**千级**，
并给出三重规模律与**可及规模上界**。这类「换算法后规模数变了」的结论最易被悄悄改回稠密、
或把规模律说成"线性" ⇒ 必须钉成常驻断言 + **突变探针**。

  ① **模块自检 11/11** + **E8 回归**
  ② **规模闭式**：flat = N²·7+2N · hier = 7+1+2N（O(N)）· 压缩比 ∝ N² · 足迹与 E6 同源
  ③ **层次化版图**：16² 真展开 ≡ flat · 256² **不展开**结构性核算 ≡ flat · 1024² 可出图（压缩比 ≫1）
  ④ **1D 三对角 ≡ E7 的 2D 稠密 MNA**（最坏列口径 · 列线 R=0）；r=0 无压降；电压单调降；far ≥ avg
  ⑤ **规模律**：IR drop 超线性（近 N²）· 面积 ∝N² · 失配 σ ∝1/√N · Elmore τ ∝N²
  ⑥ **可及规模上界**：预算越紧 ⇒ 最大 N 越小；与 1D 解交叉核对（结果真满足/超出预算）
  ⑦ **诚实对标**：landmark 带 source 且 `verified=False` · `LDA_CAPABILITIES` 无 TOPS 自夸 ·
     `NON_CLAIMED` 明写不做数值超越比较
  ⑧ **吃狗粮**：几何与 E6 同源 · Pelgrom 与 E8 同源 · 线阻与 E7 同源
  ⑨ **突变探针**（篡上界 / 注入 fabricated 指标 / 篡元素数闭式 / 拆掉压降）各必红 + 还原复绿

运行：python run_ecore_e9_smoke.py（cwd=lda/）
出口：全 PASS 退 0；任一 FAIL 退 1。**LLM 不进判决路径**。
"""
from __future__ import annotations

import os
import sys
import unittest.mock as mock

_HERE = os.path.dirname(os.path.abspath(__file__))       # = …/lda
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import numpy as np                                        # noqa: E402

from lda_l2.ecore import array_scale as AS                # noqa: E402
from lda_l2.ecore import layout as LY                     # noqa: E402
from lda_l2.ecore import mismatch as MM                   # noqa: E402
from lda_l2.ecore import parasitic as PA                  # noqa: E402
from lda_l2.ecore.mosfet import NmosParams                # noqa: E402
from lda_harness.smoke_kit import make_check              # noqa: E402

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=" | {d}", return_ok=True)

VG = 2.5
W_UM, L_UM = 1.20, 0.30


def _g() -> float:
    nn = NmosParams(w_over_l=W_UM / L_UM)
    return nn.kp * nn.w_over_l * (VG - nn.vth0)


def _r_seg() -> float:
    return PA.array_parasitics(8, 8)["r_row_seg_ohm"]


# ═══════════════ 绿色判据复用小函数（突变探针复用同一份）═══════════════
def _elements_closed_form_ok() -> bool:
    return (AS.elements_flat(8, 8) == 8 * 8 * 7 + 16
            and AS.elements_hierarchical(8, 8) == 7 + 1 + 16
            and AS.elements_hierarchical(1024, 1024) == 7 + 1 + 2048)


def _hier_matches_flat_at_scale() -> bool:
    h = AS.hierarchical_gds(256, 256)
    ex = AS.expanded_element_count(h["gds_bytes"], max_expand=64)
    return ex["structural_count"] == AS.elements_flat(256, 256)


def _1d_matches_2d() -> bool:
    worst = 0.0
    for n in (4, 8, 16, 32):
        ap = PA.array_parasitics(n, n)
        r1 = AS.row_line_profile(n, ap["r_row_seg_ohm"], _g())["far_drop_rel"]
        r2 = PA.ir_drop_report(n, n, np.full((n, n), _g()), [1.0] * n,
                               ap["r_row_seg_ohm"], 0.0)["max_rel_err"]
        worst = max(worst, abs(r1 - r2) / max(r2, 1e-30))
    return worst < 1e-9


def _budget_ordering_ok() -> bool:
    r = _r_seg(); g = _g()
    return AS.max_scale_for_budget(0.01, r, g) < AS.max_scale_for_budget(0.05, r, g) \
        < AS.max_scale_for_budget(0.10, r, g)


def _honest_boundary_ok() -> bool:
    return AS.honest_boundary_ok()


# ═══════════════ 突变探针（每个都先证「真能变红」）═══════════════
def probe_budget_corrupt() -> bool:
    """把「可及规模上界」改成常数 ⇒ 预算单调判据必红。"""
    with mock.patch.object(AS, "max_scale_for_budget", lambda *a, **k: 42):
        return not _budget_ordering_ok()


def probe_inject_fabricated() -> bool:
    """向能力面注入 fabricated 指标（TOPS/W）⇒ 诚实护栏必红。"""
    bad = list(AS.LDA_CAPABILITIES) + ["LDA 模拟阵列达到 76 TOPS/W（造假示例）"]
    with mock.patch.object(AS, "LDA_CAPABILITIES", bad):
        return not _honest_boundary_ok()


def probe_elements_corrupt() -> bool:
    """把层次化元素数改成 flat（= 不再是 O(N)）⇒ 元素数/规模核算判据必红。"""
    with mock.patch.object(AS, "elements_hierarchical",
                           lambda n, m: AS.elements_flat(n, m)):
        return not (_elements_closed_form_ok() and _hier_matches_flat_at_scale())


def probe_drop_removed() -> bool:
    """把 1D 求解改成恒返回 v_in（无压降）⇒ 1D≡2D 判据必红。"""
    def flat_profile(n, r_seg, g, v_in=1.0):
        return {"voltages": np.full(n, v_in), "far_end_v": v_in, "far_drop_v": 0.0,
                "far_drop_rel": 0.0, "avg_rel_err": 0.0, "gr": g * r_seg, "alpha": 0.0}
    with mock.patch.object(AS, "row_line_profile", flat_profile):
        return not _1d_matches_2d()


def main() -> int:
    print("=" * 78)
    print("电子计算芯片千级阵列规模压力与诚实对标 门禁 smoke（E9 · D-159）")
    print("=" * 78)

    # ════════════════ A 节：模块自检 + E8 回归 ════════════════
    print("── A 模块自检 ──")
    check("A1 array_scale 自检 11/11（闭式/1D≡2D/AREF/规模律/上界/护栏）",
          AS.run_selfchecks(verbose=False), "1D≡2D · 千级出图 · 护栏在位")
    check("A2 E8 失配链回归（E9 未破坏 mismatch 自检 10/10）",
          MM.run_selfchecks(verbose=False), "E8 10 判据仍绿")

    # ════════════════ B 节：规模闭式 ════════════════
    print("── B 规模闭式 ──")
    check("B1 元素数：flat = N²·7+2N · hier = 7+1+2N（O(N)）",
          _elements_closed_form_ok(),
          f"flat(64²)={AS.elements_flat(64, 64)} · hier(64²)={AS.elements_hierarchical(64, 64)}")
    c16, c64, c256 = (AS.compression_ratio(s, s) for s in (16, 64, 256))
    check("B2 层次化压缩比 **∝ N**（flat ∝N²、hier ∝N ⇒ 比值 ∝N：N ×4 ⇒ 比 ×4）",
          3.5 < c64 / c16 < 5.0 and 3.5 < c256 / c64 < 5.0,
          f"{c16:.0f}× → {c64:.0f}× → {c256:.0f}×")
    check("B3 足迹闭式与 E6 同源（同一 array_footprint）",
          abs(AS.array_scale_sweep([16])[0]["footprint_um"][0]
              - LY.array_footprint(16, 16)[0]) < 1e-9,
          f"{AS.array_scale_sweep([16])[0]['footprint_um']}")

    # ════════════════ C 节：层次化版图 ════════════════
    print("── C 层次化版图（O(N) · 不物化 N²）──")
    h16 = AS.hierarchical_gds(16, 16)
    ex16 = AS.expanded_element_count(h16["gds_bytes"], max_expand=64)
    check("C1 16×16 真展开元素数 ≡ flat 闭式",
          ex16["expanded"] and ex16["match"]
          and ex16["expanded_count"] == AS.elements_flat(16, 16),
          f"{ex16.get('expanded_count')} ≡ {AS.elements_flat(16, 16)}")
    ex256 = AS.expanded_element_count(AS.hierarchical_gds(256, 256)["gds_bytes"],
                                      max_expand=64)
    check("C2 256×256 **不展开**结构性核算 ≡ flat 闭式（O(N) 出图）",
          _hier_matches_flat_at_scale(),
          f"结构 {ex256['structural_count']} ≡ flat {AS.elements_flat(256, 256)}"
          f"（colrow={ex256['colrow']} · expanded={ex256['expanded']}）")
    h1k = AS.hierarchical_gds(1024, 1024)
    check("C3 1024×1024 层次化 GDS 真生成（压缩比 ≫1000×）",
          h1k["n_bytes"] > 0 and h1k["compression"] > 1000,
          f"{h1k['n_bytes']} B · top {h1k['n_top_records']} 条 · 压缩比 {h1k['compression']:.0f}×")
    check("C4 千级版图含电子层 20..25（DIFF…M2）",
          {20, 21, 22, 23, 24, 25}.issubset(set(h1k["layers"])),
          f"layers={h1k['layers']}")

    # ════════════════ D 节：1D 求解 ≡ E7 的 2D ════════════════
    print("── D 1D 三对角 ≡ E7 的 2D 稠密 MNA ──")
    check("D1 最坏列口径 1D ≡ 2D（rel < 1e-9 · N=4/8/16/32）", _1d_matches_2d(),
          "列线 R=0 · 4 个规模")
    z = AS.row_line_profile(16, 0.0, _g())
    check("D2 r_seg = 0 ⇒ 无压降（理想互连退化正确）",
          z["far_drop_rel"] == 0.0 and z["avg_rel_err"] == 0.0, "far=avg=0")
    vs = AS.row_line_profile(16, _r_seg(), _g())["voltages"]
    check("D3 行线电压沿线单调不增（IR drop 剖面物理）",
          all(vs[k] >= vs[k + 1] - 1e-15 for k in range(len(vs) - 1)) and vs[-1] < vs[0],
          f"{vs[0]:.5f} → {vs[-1]:.5f} V")
    pf = AS.row_line_profile(32, _r_seg(), _g())
    check("D4 口径区分：far_drop_rel ≥ avg_rel_err（末端 vs 全列平均）",
          pf["far_drop_rel"] > pf["avg_rel_err"] > 0.0,
          f"{pf['far_drop_rel']:.5f} ≥ {pf['avg_rel_err']:.5f}")

    # ════════════════ E 节：规模律 ════════════════
    print("── E 三重规模律 ──")
    sw = AS.array_scale_sweep([16, 64, 256, 1024])
    irs = [r["ir_avg_rel_err"] for r in sw]
    check("E1 IR drop 随 N **超线性**（近 N²：N ×4 ⇒ 误差 ≥×6）",
          all(irs[k] < irs[k + 1] for k in range(len(irs) - 1))
          and irs[1] / irs[0] >= 6.0,
          f"{' → '.join(f'{v*100:.2f}%' for v in irs)}")
    areas = [r["footprint_mm2"] for r in sw]
    check("E2 版图面积 ∝ N²（N ×4 ⇒ 面积 ×16 ±10%）",
          abs(areas[1] / areas[0] - 16.0) < 1.6, f"{areas[0]:.4f} → {areas[1]:.4f} mm²")
    sms = [r["mismatch_sigma_rel"] for r in sw]
    check("E3 失配输出 σ ∝ 1/√N（N ×4 ⇒ σ 减半）",
          all(abs(sms[k] / sms[k + 1] - 2.0) < 0.05 for k in range(len(sms) - 1)),
          f"{' → '.join(f'{v*100:.4f}%' for v in sms)}")
    taus = [r["tau_row_s"] for r in sw]
    check("E4 Elmore 互连时间常数 ∝ N²（N ×4 ⇒ τ ×16 ±20%）",
          abs(taus[1] / taus[0] - 16.0) < 3.2, f"{taus[0]:.3e} → {taus[1]:.3e} s")

    # ════════════════ F 节：可及规模上界 ════════════════
    print("── F 可及规模上界 ──")
    r_seg, g = _r_seg(), _g()
    n10 = AS.max_scale_for_budget(0.10, r_seg, g)
    n5 = AS.max_scale_for_budget(0.05, r_seg, g)
    n1 = AS.max_scale_for_budget(0.01, r_seg, g)
    check("F1 预算越紧 ⇒ 可及最大 N 越小（单调）", _budget_ordering_ok(),
          f"10%→N≤{n10} · 5%→N≤{n5} · 1%→N≤{n1}")
    ok_lo = AS.row_line_profile(n5, r_seg, g)["avg_rel_err"] <= 0.05
    ok_hi = AS.row_line_profile(n5 + 2, r_seg, g)["avg_rel_err"] > 0.05
    check("F2 上界自洽：N_5% 满足预算、N_5%+2 超出预算（二分真收敛）",
          ok_lo and ok_hi,
          f"err({n5})={AS.row_line_profile(n5, r_seg, g)['avg_rel_err']:.5f} ≤0.05"
          f" < err({n5+2})={AS.row_line_profile(n5+2, r_seg, g)['avg_rel_err']:.5f}")
    check("F3 上界远小于千级 ⇒ 被动单端行线驱动的 IR-drop 是**硬天花板**",
          n10 < 100, f"10% 预算下 N≤{n10}（千级阵列在被动驱动下不可达）")

    # ════════════════ G 节：诚实对标 ════════════════
    print("── G 诚实对标 ──")
    check("G1 landmark 均带 source 且 `verified=False`（照录·未在 LDA 上验证）",
          all(lm.get("source") and lm.get("verified") is False for lm in AS.LANDMARKS),
          f"{len(AS.LANDMARKS)} 条 landmark")
    check("G2 诚实护栏：`LDA_CAPABILITIES` 无 TOPS / TOPS-W / fJ-op 自夸",
          _honest_boundary_ok(), "设计&验证工具链口径")
    check("G3 `NON_CLAIMED` 明写**不做数值超越比较**（不同层级）",
          len(AS.NON_CLAIMED) >= 3 and any("数值" in s for s in AS.NON_CLAIMED),
          f"{len(AS.NON_CLAIMED)} 条不宣称项")
    hc = AS.honest_comparison()
    check("G4 对标结果含「可比维度」与「不可比维度」两组",
          hc["comparable_dimensions"] and hc["not_comparable"]
          and len(hc["not_comparable"]) == len(AS.NON_CLAIMED), "双向声明")
    check("G5 披露齐备：SCALE_DISCLOSURE 七键（含 **omission** 省略项显式声明）",
          all(k in AS.SCALE_DISCLOSURE for k in
              ("role", "algorithms", "omission", "process", "landmarks", "honest", "red_line")),
          f"键={sorted(AS.SCALE_DISCLOSURE)}")

    # ════════════════ H 节：吃狗粮跨模块 ════════════════
    print("── H 吃狗粮跨模块 ──")
    check("H1 布线几何与 E6 **同源**（共用 `layout.array_lines`，无第二份副本）",
          len(LY.array_lines(4, 4)) == 8
          and AS.hierarchical_gds(4, 4)["n_lines"] == 8,
          "4 行线 + 4 列线")
    check("H2 Pelgrom 与 E8 **同源**（σ_δ 由 E8 闭式给出）",
          abs(AS.sigma_cell_rel(W_UM, L_UM, VG)
              - float(np.hypot(MM.pelgrom_sigma_beta_rel(W_UM, L_UM),
                               MM.pelgrom_sigma_vth_mv(W_UM, L_UM) / 1000.0
                               / (VG - NmosParams().vth0)))) < 1e-15, "单一真源")
    check("H3 线阻与 E7 **同源**（`array_parasitics.r_row_seg`）",
          abs(AS.array_scale_sweep([8])[0]["r_row_seg_ohm"]
              - PA.array_parasitics(8, 8)["r_row_seg_ohm"]) < 1e-12,
          f"{_r_seg():.4f} Ω")

    # ════════════════ I 节：突变探针 ════════════════
    print("── I 突变探针（每个都必须真能变红）──")
    check("I1 探针：把「可及上界」改成常数 ⇒ 预算单调判据必红",
          probe_budget_corrupt() is True, "证上界真由 1D 解反解")
    check("I2 探针：注入 fabricated 指标（TOPS/W）⇒ 诚实护栏必红",
          probe_inject_fabricated() is True, "证护栏真的会拦")
    check("I3 探针：把层次化元素数改成 flat ⇒ 元素数/规模核算判据必红",
          probe_elements_corrupt() is True, "证 O(N) 断言非假绿")
    check("I4 探针：拆掉压降（恒返回 v_in）⇒ 1D≡2D 判据必红",
          probe_drop_removed() is True, "证压降真来自求解")

    # ════════════════ J 节：还原完整性 ════════════════
    print("── J 还原完整性 ──")
    check("J1 还原后：闭式/规模核算/1D≡2D/上界/护栏 五项复绿",
          _elements_closed_form_ok() and _hier_matches_flat_at_scale()
          and _1d_matches_2d() and _budget_ordering_ok() and _honest_boundary_ok(),
          "无 patch 残留")
    check("J2 还原后：模块自检 11/11 复绿", AS.run_selfchecks(verbose=False), "无残留")

    print()
    print(f"电子计算芯片千级阵列规模压力与诚实对标 门禁 smoke（E9）：{PASS}/{PASS + FAIL} PASS")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
