#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""电子计算征程 · E11-d · **器件级模型失效边界门禁**（D-164）。

═══════════════════════════════════════════════════════════════════════════
本门禁守什么
═══════════════════════════════════════════════════════════════════════════
E11-d 的产出是**边界说明书**，不是新能力。它最容易出的问题是**两类边界被混为一谈**：

    A **数值窗口**（LDA 实测：PDE 与闭式在多大 ψ_s 内一致 · 由网格分辨率定）
    B **物理模型边界**（文献判据：玻尔兹曼/1D 假设何时失效 · LDA **算不出**）

若把 B 说成"LDA 的成果"，就是**把文献当自家能力**（比"假绿"更隐蔽的越界）。
故本门禁守三件事：

① **数值窗口可实测复现**（不是查表常数）：真扫 PDE，确认 ψ_s ∈ φ_F·[1±1.54]；
② 🔴 **A/B 严格分离**：文献项必须逐项标 `computed_by_lda=False` + 有 source；
   且**物理窗口必须比数值窗口更严**（否则说明我们连"瓶颈在哪"都说错了）；
③ **缺口量化不得被当成能力**：`literature_gap_report` 报告的是 **LDA 的缺口**，
   不是 LDA 的计算结果（`computed_by_lda=False`），且长沟道极限下缺口必须单调减。

判什么（分节）
--------------
A 模块自检（device_limits 7/7）
B 关键事实 name-first（数值窗口 · **实测复现** · 窗口外必降级 · 物理<数值 ·
  缺口量化 + 长沟道极限 · 文献登记完整 · 能力边界汇总）
C 反向可证伪（5 条突变探针）
D 诚实护栏（披露不得声称 LDA 能算短沟道；含「红线」必含「分层」）
E 还原完整性
"""
from __future__ import annotations

import os
import sys
import unittest.mock as mock

_HERE = os.path.dirname(os.path.abspath(__file__))          # = …/lda
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

from lda_l2.ecore import device_limits as DL  # noqa: E402
from lda_solver import mos_1d as M1  # noqa: E402

TOL_WINDOW_PHI_F = 0.15     # 实测窗口边界与常数 1.54 的容差（φ_F）
TOL_OUTSIDE_REL = 0.05      # 窗口外（ψ_s=3φ_F）相对差下限（实测 ~0.49）
DX_IF_M = DL.WINDOW_REFERENCE_DX_IF_NM * 1.0e-9


# ══════════════════════ 判据实现 ══════════════════════
def _window_constant_ok() -> bool:
    w = DL.numerical_window_phi_f()
    return bool(abs(w["lo_phi_f"] + 0.54) < 1e-9 and abs(w["hi_phi_f"] - 2.54) < 1e-9)


def _window_measured_ok() -> bool:
    """实测边界应与常数 ψ_s∈[1−1.54, 1+1.54]·φ_F（即 [−0.54, 2.54]）一致。

    🔴 比的是**边界值**（−0.54 / 2.54），不是半宽（1.54）——把两者搞混会让判据
    在「实测 −0.50 与该到 −0.54」时误报（本轮实际踩到）。
    扫描实现复用模块的 `measure_window_edge`（两级扫描，兼顾精度与耗时）。
    """
    hi = DL.measure_window_edge(+1)
    lo = DL.measure_window_edge(-1)
    return bool(abs(hi - (1.0 + DL.WINDOW_HALF_WIDTH_PHI_F)) < TOL_WINDOW_PHI_F
                and abs(lo - (1.0 - DL.WINDOW_HALF_WIDTH_PHI_F)) < TOL_WINDOW_PHI_F)


def _grid_dependence_ok() -> bool:
    """数值窗口**随网格变宽**（网格越细 ⇒ 窗口越大）⇒ 数值窗口是网格相关的。"""
    dep = DL.numerical_window_grid_dependence((0.05, 0.02))
    return bool(dep[1]["hi_phi_f"] > dep[0]["hi_phi_f"]
                and dep[1]["lo_phi_f"] < dep[0]["lo_phi_f"])


def _outside_degrades_ok() -> bool:
    """窗口外（ψ_s = 3φ_F）必然降级（诚实：边界是真的边界）。"""
    pf = M1.phi_f()
    ps = 3.0 * pf
    s = M1.solve_moscap_1d(ps, dx_if=DX_IF_M)
    g = M1.sze_qs_closed_form(ps)
    return bool(abs(s["Q_s"] - g) / abs(g) > TOL_OUTSIDE_REL)


def _physical_stricter_ok() -> bool:
    """物理窗口必须比数值窗口**更严**（瓶颈是物理模型）。"""
    return bool(DL.window_ratio_physical_over_numerical() < 1.0)


def _gap_monotone_ok() -> bool:
    """缺口量化判据：roll-off 必须**为负**（V_th 下降）且 L↑ 时单调减。

    🔴 符号是判据的一部分：`literature_gap_report` 里的 `*_frac_of_vth` 取的是**绝对值**，
    只看比值会让「符号翻转」这类错误逃脱（本轮突变探针 C4 抓到过）⇒ 必须显式断言符号。
    """
    gs = [DL.literature_gap_report(L) for L in (0.065, 0.250, 1.000)]
    f = [g["rolloff_frac_of_vth"] for g in gs]
    return bool(all(g["rolloff_dV_th_v"] < 0.0 for g in gs)
                and f[0] > f[1] > f[2] and f[0] > 0.20)


def _literature_registry_ok(reg=None) -> bool:
    reg = DL.LITERATURE_LIMITS if reg is None else reg
    return bool(len(reg) >= 4
                and all(e.get("source") and e.get("computed_by_lda") is False
                        for e in reg))


def _no_short_channel_claim(text: str = None) -> bool:
    """诚实护栏：披露/报告不得声称「LDA 已算出短沟道效应」。"""
    if text is None:
        parts = [str(v) for v in DL.DEVICE_LIMITS_DISCLOSURE.values()]
        parts += [str(cm) for cm in DL.capability_boundary_map().values()]
        parts.append(str(DL.literature_gap_report(0.065)))
        text = "\n".join(parts)
    bad = ("LDA 已算" in text and "短沟道" in text) or ("本平台已支持 2D MOS" in text)
    return not bad


# ══════════════════════ 突变探针 ══════════════════════
def _probe_window_constant_wrong() -> bool:
    """把窗口半宽常数从 1.54 改成 0.5 ⇒ B1 判据必红。"""
    with mock.patch.object(DL, "WINDOW_HALF_WIDTH_PHI_F", 0.5):
        return not _window_constant_ok()


def _probe_degeneracy_loosened() -> bool:
    """把物理简并上限抬到 > 数值上限 ⇒ 「物理更严」判据必红。"""
    with mock.patch.object(DL, "N_CRIT_DEGENERATE", 1.0e30):
        return not _physical_stricter_ok()


def _probe_literature_claimed_as_lda() -> bool:
    """把文献项标成 LDA 自算 ⇒ 登记完整性判据必红（诚实护栏）。"""
    fake = tuple(dict(e, computed_by_lda=True) for e in DL.LITERATURE_LIMITS)
    return not _literature_registry_ok(fake)


def _probe_yau_sign_flipped() -> bool:
    """把 Yau roll-off 的符号翻转（变成 V_th 升高）⇒ 长沟道单调性判据必红。"""
    real = DL.yau_rolloff_dvth

    def bad(*a, **kw):
        r = dict(real(*a, **kw))
        r["dV_th_v"] = -r["dV_th_v"]
        return r

    with mock.patch.object(DL, "yau_rolloff_dvth", bad):
        return not _gap_monotone_ok()


def _probe_claim_short_channel_computed() -> bool:
    """注入「LDA 已算短沟道…」式口径 ⇒ 诚实护栏必红。"""
    return not _no_short_channel_claim("本平台 LDA 已算出短沟道 roll-off，误差 3%")


def _probe_grid_dependence_reversed() -> bool:
    """把网格依赖**反转**（粗网格窗口反而更宽）⇒ B8 判据必红。"""
    def bad(*_a, **_kw):
        return [{"dx_if_nm": 0.05, "lo_phi_f": -1.50, "hi_phi_f": 3.00},
                {"dx_if_nm": 0.02, "lo_phi_f": -0.50, "hi_phi_f": 2.50}]

    with mock.patch.object(DL, "numerical_window_grid_dependence", bad):
        return not _grid_dependence_ok()


def main() -> int:
    # ─────────────── A 模块自检 ───────────────
    check("A1 边界模块自检 device_limits.run_selfchecks() 8/8",
          DL.run_selfchecks(verbose=False) is True)

    # ─────────────── B 关键事实 ───────────────
    w = DL.numerical_window_phi_f()
    check("B1 数值窗口常数 = φ_F·[1−1.54, 1+1.54] · N_crit=5.5e26 m⁻³",
          _window_constant_ok(), "lo=%.2f hi=%.2f φ_F" % (w["lo_phi_f"], w["hi_phi_f"]))

    hi = DL.measure_window_edge(+1)
    lo = DL.measure_window_edge(-1)
    check("B2 **实测复现**：真扫 PDE 得窗口边界 ≡ 常数（±0.15 φ_F）",
          _window_measured_ok(), "实测 [%.2f, %.2f] φ_F · 常数 [−0.54, 2.54]" % (lo, hi))

    pf = M1.phi_f()
    s3 = M1.solve_moscap_1d(3.0 * pf, dx_if=DX_IF_M)
    g3 = M1.sze_qs_closed_form(3.0 * pf)
    check("B3 窗口外（ψ_s=3φ_F）**必然降级**（rel > 5% · 边界是真的边界）",
          _outside_degrades_ok(),
          "rel=%.1f%%" % (abs(s3["Q_s"] - g3) / abs(g3) * 100))

    check("B4 物理窗口 **比** 数值窗口更严（ratio<1 ⇒ 瓶颈是物理模型不是数值精度）",
          _physical_stricter_ok(),
          "ratio=%.3f" % DL.window_ratio_physical_over_numerical())

    gr = DL.literature_gap_report(0.065)
    check("B5 缺口量化：L=65 nm ⇒ roll-off 占 V_th > 20%；L↑ 单调减（长沟道极限）",
          _gap_monotone_ok(),
          "roll-off=%.3f V（%.1f%% of V_th）" % (gr["rolloff_dV_th_v"],
                                                 gr["rolloff_frac_of_vth"] * 100))

    check("B6 文献边界登记完整：≥4 项 · 每项含 source 且 `computed_by_lda=False`",
          _literature_registry_ok(), "%d 项" % len(DL.LITERATURE_LIMITS))

    cm = DL.capability_boundary_map()
    check("B7 能力边界汇总：能算 ≥4 · 不能算 5 项（含 T2 永久锁）",
          len(cm["can_compute"]) >= 4 and len(cm["cannot_compute"]) == 5
          and any("T2" in c["needs"] for c in cm["cannot_compute"]),
          "能算 %d / 不能算 %d" % (len(cm["can_compute"]), len(cm["cannot_compute"])))

    dep = DL.numerical_window_grid_dependence((0.05, 0.02))
    check("B8 数值窗口**网格相关**（dx_if 0.05→0.02 nm 窗口变宽）而物理窗口与网格无关",
          _grid_dependence_ok(),
          "[%.2f, %.2f] → [%.2f, %.2f] φ_F" %
          (dep[0]["lo_phi_f"], dep[0]["hi_phi_f"], dep[1]["lo_phi_f"], dep[1]["hi_phi_f"]))

    # ─────────────── C 反向可证伪 ───────────────
    check("C1 探针：窗口半宽常数改 0.5 ⇒ B1 必红",
          _probe_window_constant_wrong() is True)
    check("C2 探针：物理简并上限抬到 1e30 ⇒ B4「物理更严」必红",
          _probe_degeneracy_loosened() is True)
    check("C3 探针：文献项被标成 LDA 自算 ⇒ B6 诚实判据必红",
          _probe_literature_claimed_as_lda() is True)
    check("C4 探针：Yau 符号翻转 ⇒ B5 长沟道单调性必红",
          _probe_yau_sign_flipped() is True)
    check("C5 探针：注入「LDA 已算短沟道」⇒ 诚实护栏必红",
          _probe_claim_short_channel_computed() is True)
    check("C6 探针：网格依赖被反转 ⇒ B8 判据必红",
          _probe_grid_dependence_reversed() is True)

    # ─────────────── D 诚实护栏 / 口径 ───────────────
    check("D1 披露与报告不含「LDA 已算短沟道 / 已支持 2D MOS」类口径",
          _no_short_channel_claim() is True)
    check("D2 边界披露：含「红线」字样处必须同时含「分层」口径",
          all(("分层" in v) for v in DL.DEVICE_LIMITS_DISCLOSURE.values()
              if isinstance(v, str) and "红线" in v))
    check("D3 两类边界显式分离（披露含 `computed_by_lda` 语义说明）",
          "computed_by_lda" in DL.DEVICE_LIMITS_DISCLOSURE.get("two_kinds", ""))

    # ─────────────── E 还原完整性 ───────────────
    check("E 还原完整性：探针后 A1/B1/B4/B5/B6 复绿（无 patch 残留）",
          DL.run_selfchecks(verbose=False) is True and _window_constant_ok()
          and _physical_stricter_ok() and _gap_monotone_ok()
          and _literature_registry_ok())

    bad = globals().get("FAIL", 0)
    good = globals().get("PASS", 0)
    print("")
    print("门禁 smoke：%d PASS / %d FAIL" % (good, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
