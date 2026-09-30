#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""电子计算征程 · E11-c · **器件级内核桥门禁**（D-163）。

═══════════════════════════════════════════════════════════════════════════
本门禁守什么
═══════════════════════════════════════════════════════════════════════════
E11-b 勘查结论：ecore 此前与平台器件级 T1 内核**零复用**——因为
`lda_solver/drift_diffusion_1d/2d` 是**两端 p-n 结**，而 ecore 的器件模型是
**三端 MOSFET**，两者不是同一种器件（`docs/LDA_电子计算征程_E11b_接缝勘查_2026-10-01.md` §3）。

E11-c 补上 MOS 结构 1D 自洽泊松内核（`lda_solver/mos_1d.py`）并在 ecore 侧建桥
（`lda_l2/ecore/device_pde.py`），使本包首次拥有「**教科书闭式 ⟷ 器件级 PDE**」
这条独立交叉验证路径。本门禁守住三件事：

① **交叉验证真的成立**（不是自说自话）：V_th 与 Q_s 跨点两路必须一致到既定容差；
② 🔴 **红线不破**：candidate（PDE 数值解）永标 `is_oracle=False`，golden 是教科书闭式，
   `guard_t1_not_oracle` 必须真正接线（反向 `force_oracle=True` 必 raise）；
③ 🔴 **账本保护**：`NmosParams` 默认值**逐位不变**——物理 V_th 只作并行第二器件模型，
   **绝不替换**电路级默认参数（否则 E1–E10 全部已上线数字失效）。

判什么（分节）
--------------
A 模块自检（mos_1d 8/8 + device_pde 8/8）
B 关键事实 name-first（V_th 一致 · 跨点 Q_s 一致 · 量纲桥 · G-3 显式不自洽 ·
  保护性约束 · **诚实窗口**：超出 2.5φ_F 必然劣化）
C 反向可证伪（5 条突变探针：闭式改常数 / PDE 电荷翻倍 / 候选标 ORACLE /
  量纲常数改错 / 默认参数被改 ⇒ 对应判据必红）
D 红线口径（is_oracle 语义 · guard 接线 · 披露含「红线」必含「分层」）
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

from lda_l2.ecore import device_pde as DP  # noqa: E402
from lda_l2.ecore.mosfet import NmosParams  # noqa: E402
from lda_solver import mos_1d as M1  # noqa: E402
from lda_solver.redline import guard_t1_not_oracle  # noqa: E402

TOL_VTH_REL = 0.02          # V_th 闭式⟷PDE 容差（实测 ~2e-4 % ⇒ 余量 ~1e4×）
TOL_QS_REL = 1.0e-3         # 跨点 Q_s 最差容差（实测 ~1.1e-4）
TOL_DIM_REL = 0.01          # C_ox 换算 vs 教科书 4 nm SiO₂ 容差（实测 0.38%）


# ══════════════════════ 判据实现（供主流程与探针共用）══════════════════════
def _vth_ok() -> bool:
    cc = DP.cross_check_vth()
    return bool(cc["converged"] and cc["rel_err"] < TOL_VTH_REL)


def _qs_ok() -> bool:
    pts = DP.cross_check_qs()
    return bool(all(p["converged"] for p in pts)
                and max(p["rel_err"] for p in pts) < TOL_QS_REL)


def _dim_ok() -> bool:
    cox_std = 3.9 * 8.854187817e-12 / DP.nm_to_m(4.0)
    cox_mm = DP.cox_f_per_um2_to_f_per_m2(8.6e-15)
    return bool(abs(cox_mm - cox_std) / cox_std < TOL_DIM_REL)


def _guard_ok() -> bool:
    """candidate 必须被判为候选；标成 ORACLE 时守卫必响。"""
    raised = False
    try:
        guard_t1_not_oracle(DP.physics_vth_pde(), force_oracle=True)
    except RuntimeError:
        raised = True
    return bool(raised and DP.physics_vth_pde()["is_oracle"] is False)


def _protected_ok(cls=NmosParams) -> bool:
    """账本保护判据：默认参数类逐位不变（`cls` 可注入，供突变探针消费）。"""
    p = cls()
    return bool(p.vth0 == 0.4 and p.kp == 120e-6 and p.lam == 0.02
                and p.w_over_l == 10.0)


# ══════════════════════ 突变探针（先证"真能变红"）══════════════════════
def _probe_closed_form_broken() -> bool:
    """把 golden 闭式替换成明显不同的常数 ⇒ V_th 一致性判据必红。"""
    def bad(*_a, **_kw):
        return {"V_th": 0.9, "phi_f": 0.4, "two_phi_f": 0.8, "W_dmax_nm": 100.0,
                "Q_dep": 1e-3, "C_ox_f_per_m2": 8.6e-3, "C_ox_f_per_um2": 8.6e-15,
                "n_a_cm3": 1e17, "t_ox_nm": 4.0, "vfb_v": -0.6,
                "provenance": "patched", "is_oracle": True}

    with mock.patch.object(DP, "physics_vth_closed", bad):
        return not _vth_ok()


def _probe_pde_charge_scaled() -> bool:
    """把 PDE 面电荷翻倍 ⇒ 跨点 Q_s 一致性判据必红。"""
    real = M1.solve_moscap_1d

    def bad(*a, **kw):
        r = dict(real(*a, **kw))
        r["Q_s"] = r["Q_s"] * 2.0
        return r

    with mock.patch.object(M1, "solve_moscap_1d", bad):
        return not _qs_ok()


def _probe_candidate_marked_oracle() -> bool:
    """把 PDE 解标成 is_oracle=True ⇒ 守卫必须抛错（红线哨响）。"""
    real = M1.moscap_vth_pde

    def bad(*a, **kw):
        r = dict(real(*a, **kw))
        r["is_oracle"] = True
        return r

    with mock.patch.object(M1, "moscap_vth_pde", bad):
        raised = False
        try:
            DP.cross_check_vth()
        except RuntimeError:
            raised = True
        return raised


def _probe_dimension_constant_wrong() -> bool:
    """把 µm²→m² 换算常数改错 1e6 倍 ⇒ 量纲判据必红。"""
    with mock.patch.object(DP, "F_PER_UM2_TO_F_PER_M2", 1.0e6):
        return not _dim_ok()


def _probe_default_params_changed() -> bool:
    """把 NmosParams 默认值改掉 ⇒ 账本保护判据必红。

    🔴 注：`mock.patch.object(NmosParams, "vth0", 0.5)` 对 dataclass **无效**
    （字段默认值固化在 `__init__` 签名里）⇒ 必须**注入替换类**，让被判据消费的
    那份引用本身换掉（否则"patch 成功但判据不红"= 假探针）。
    """
    class _Fake:
        vth0 = 0.5
        kp = 120e-6
        lam = 0.02
        w_over_l = 10.0

    return not _protected_ok(_Fake)


def main() -> int:
    # ─────────────── A 模块自检 ───────────────
    check("A1 器件级内核自检 mos_1d.run_selfchecks() 8/8",
          M1.run_selfchecks(verbose=False) is True)
    check("A2 桥接层自检 device_pde_self_check() 8/8",
          DP.device_pde_self_check(verbose=False) is True)

    # ─────────────── B 关键事实（name-first）───────────────
    cc = DP.cross_check_vth()
    check("B1 V_th golden（教科书耗尽式）= 0.4260 V（与电路级占位 vth0=0.4 同阶）",
          abs(cc["V_th_golden"] - 0.4260) < 5e-4,
          "golden=%.4f V" % cc["V_th_golden"])
    check("B2 V_th：教科书闭式 ⟷ PDE 一致（rel < 2% · 实测 ~2e-4 %）",
          _vth_ok(), "rel=%.6f%% · cand=%.6f V · n_grid=%d" %
          (cc["rel_err"] * 100, cc["V_th_cand"], cc["n_grid"]))

    pts = DP.cross_check_qs()
    worst = max(pts, key=lambda p: p["rel_err"])
    check("B3 Q_s 跨点一致（0.5→2.5 φ_F 六点 · 最差 rel < 0.1%）",
          _qs_ok(), "最差 %.5f%% @ ψ_s=%.2fφ_F" %
          (worst["rel_err"] * 100, worst["psi_f_over_phi_f"]))

    check("B4 量纲桥：8.6 fF/µm² ≡ 8.6e-3 F/m²（与 4 nm SiO₂ 教科书值差 <1%）",
          _dim_ok(),
          "%.4e F/m²" % DP.cox_f_per_um2_to_f_per_m2(8.6e-15))

    pr = DP.parameter_consistency_report()
    check("B5 G-3 参数不自洽**显式可见**（µ 反推 ≈140 vs 典型 500 cm²/V·s ⇒ 比值 ~3.6×）",
          2.0 < pr["ratio_typical_over_implied"] < 6.0 and pr["consistent"] is False,
          "µ=%.0f cm²/V·s · 比=%.2f× · consistent=%s" %
          (pr["mu_implied_cm2_vs"], pr["ratio_typical_over_implied"], pr["consistent"]))

    check("B6 🔴 保护性约束：NmosParams 默认值逐位不变（vth0=0.4 · kp=120e-6）",
          _protected_ok())

    pf = M1.phi_f()
    beyond = DP.moscap_qs_pde(2.75 * pf)
    rel_beyond = abs(beyond["Q_s"] - M1.sze_qs_closed_form(2.75 * pf)) \
        / abs(M1.sze_qs_closed_form(2.75 * pf))
    check("B7 **诚实窗口**登记：ψ_s=2.75φ_F（超出工作区）必然劣化（rel > 1%）",
          rel_beyond > 0.01,
          "rel=%.3f%% ⇒ 工作区上限 2.5φ_F（反型层薄于界面网格）" % (rel_beyond * 100))

    check("B8 默认界面网格 ≡ 0.02 nm（强反型点 2.5φ_F 仍需 rel<0.1%）",
          abs(DP.DX_IF_NM_DEFAULT - 0.02) < 1e-12,
          "dx_if=%.3f nm" % DP.DX_IF_NM_DEFAULT)

    # ─────────────── C 反向可证伪（探针先证能变红）───────────────
    check("C1 探针：golden 闭式改成常数 0.9 ⇒ B2 判据必红",
          _probe_closed_form_broken() is True)
    check("C2 探针：PDE 面电荷翻倍 ⇒ B3 判据必红",
          _probe_pde_charge_scaled() is True)
    check("C3 探针：候选被标 is_oracle=True ⇒ 守卫必抛错（红线哨响）",
          _probe_candidate_marked_oracle() is True)
    check("C4 探针：量纲换算常数改错 1e6 倍 ⇒ B4 判据必红",
          _probe_dimension_constant_wrong() is True)
    check("C5 探针：NmosParams.vth0 被改成 0.5 ⇒ B6 账本保护判据必红",
          _probe_default_params_changed() is True)

    # ─────────────── D 红线口径 ───────────────
    check("D1 candidate（PDE）恒 is_oracle=False；golden（教科书闭式）is_oracle=True",
          DP.physics_vth_pde()["is_oracle"] is False
          and DP.physics_vth_closed()["is_oracle"] is True)
    check("D2 guard_t1_not_oracle 真正接线（正常通过 + force_oracle 必 raise）",
          _guard_ok())
    check("D3 桥接披露：含「红线」字样处必须同时含「分层」口径",
          all(("分层" in v) for k, v in DP.DEVICE_PDE_DISCLOSURE.items()
              if isinstance(v, str) and "红线" in v))

    # ─────────────── E 还原完整性 ───────────────
    check("E 还原完整性：探针运行后 A1/A2/B2/B3 复绿（无 patch 残留）",
          M1.run_selfchecks(verbose=False) is True
          and DP.device_pde_self_check(verbose=False) is True
          and _vth_ok() and _qs_ok())

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
