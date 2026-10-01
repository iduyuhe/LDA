# -*- coding: utf-8 -*-
"""电子计算征程 E12 门禁 · **2D MOS 求解器（短沟道效应：算不了 → 算得了）**。

═══ 判什么（分节）═══
A 模块自检（`lda_solver.mos_2d.run_selfchecks` 12 项 + `ecore.device_2d.device_2d_self_check` 8 项）
B 关键事实 name-first：长沟道收敛到教科书 1D 闭式 · roll-off 单调 · DIBL 指数衰减律（R²）
  · 自然长度同式 · 网格收敛 · 两变体互验 · 能力闭合表 · 与 E11-d 文献式同量级（**对照**）
  · **与底层模块交叉核对**（门禁数字 ≡ 模块实测）
C 反向可证伪（**6 条突变探针**，每条先证「去掉该机制 ⇒ 对应判据必红」）
D 诚实护栏：不宣称 I-V/TOPS · `is_oracle=False`
K 自入 CI core（防静默漏接 · 血案 28）

🔴 本门禁守的核心是 **E12 的两条命门**：
  ① **golden 是教科书 1D 闭式**，2D 数值解只是 candidate（`is_oracle=False`）——
     只允许「长沟道极限 2D → 1D」这一方向，**绝不反向**用 2D 当标定真值；
  ② **偏压必须真进得去**（电子准费米势分裂）—— 若退回朴素写法，漏端被压回 ψ_n、
     DIBL 恒 ≈ 0 而探针 C5 必红（这是本段抓到的**假绿**血案）。
"""
import contextlib
import os
import sys
import unittest.mock as mock

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))       # = …/lda
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import device_2d as D2                 # noqa: E402
from lda_l2.ecore import device_pde as DP                # noqa: E402
from lda_solver import mos_2d as M2                      # noqa: E402
from lda_harness.smoke_kit import make_check             # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

#: 探针用的低成本网格（快速证伪，不需要生产精度）
CHEAP = {"dx_target_nm": 5.0}


def _fresh():
    """清设备缓存 —— 突变探针改的是装配路径，不清缓存就测不到。"""
    M2._DEV_CACHE.clear()


@contextlib.contextmanager
def _mutated(**patches):
    _fresh()
    try:
        with contextlib.ExitStack() as st:
            for obj, name, val in patches["items"]:
                st.enter_context(mock.patch.object(obj, name, val))
            yield
    finally:
        _fresh()


# ══════════════════════ 判据实现（可被探针复用）══════════════════════
def _longchannel_ok() -> bool:
    cc = D2.cross_check_vth_2d_longchannel(lg_nm=1000.0, dx_target_nm=15.0)
    return bool(cc["rel_err"] < 0.02 and cc["converged"])


def _rolloff_ok() -> bool:
    ro = D2.rolloff_2d_report(Ls_nm=(65.0, 100.0, 250.0), **CHEAP)
    p65 = ro["points"][0]
    # 🔴 三条一起判，缺一不可（本轮血案：只判「单调 + 显著下降」不特异 ——
    #    若把判据点取 max，V_th 会被结边（恒 > φ_F）拉成 ≈0 ⇒ 仍"单调"且"下降很大"，
    #    判据却全绿 ⇒ 必须**同时**要求短沟道 V_th 仍是**有意义的正值阈值**。
    return bool(ro["monotone_rolloff"]
                and p65["dvth_vs_golden_mv"] < -100.0
                and 0.05 < p65["V_th_v"] < ro["golden_1d_v"])


def _dibl_ok() -> bool:
    dib = D2.dibl_2d_report(Ls_nm=(65.0, 250.0), **CHEAP)
    return bool(dib["points"][0]["dibl_mv_per_v"] > 10.0
                and dib["exponential_law"]["r2"] > 0.99)


def _natural_length_ok() -> bool:
    return bool(D2.natural_length_2d()["same_formula"])


def _grid_convergence_ok() -> bool:
    a = D2.cross_check_vth_2d_longchannel(lg_nm=250.0, dx_target_nm=5.0)
    b = D2.cross_check_vth_2d_longchannel(lg_nm=250.0, dx_target_nm=2.5)
    return bool(abs(a["V_th_2d_v"] - b["V_th_2d_v"]) < 3e-3)


def _mode_gap_ok() -> bool:
    g = M2.mos2d_vth_mode_gap(100e-9, dx_target=5e-9)
    return bool(0.0 < g < 0.030)          # boltzmann 含反型层 ⇒ V_th 略高，差 <30 mV


# ══════════════════════ 突变探针（每条先证「真能变红」）══════════════════════
def probe_flat_electrodes_no_rolloff() -> bool:
    """把所有电极钉到体内电位 ⇒ 无横向结 ⇒ roll-off 消失 ⇒ B2 必红。"""
    real = M2.mos2d_dirichlet

    def flat(dev, *a, **kw):
        t = dict(real(dev, *a, **kw))
        t["val"] = np.full(np.asarray(t["val"], dtype=float).shape, t["psi_bulk"])
        return t

    with _mutated(items=[(M2, "mos2d_dirichlet", flat)]):
        return not _rolloff_ok()


def probe_zero_drain_bias_no_dibl() -> bool:
    """强制 V_d ≡ 0 ⇒ 漏端与源端同电位 ⇒ DIBL 消失 ⇒ B3 必红。"""
    real = M2.mos2d_dirichlet

    def novd(dev, Vg, Vd, *a, **kw):
        return real(dev, Vg, 0.0, *a, **kw)

    with _mutated(items=[(M2, "mos2d_dirichlet", novd)]):
        return not _dibl_ok()


def probe_no_qfl_split_kills_bias() -> bool:
    """🔴 本轮血案回归：去掉**电子准费米势分裂**（phi_n_shift ≡ 0）。

    后果：n⁺ 漏区电子密度 `N_D·e^{V_d/V_T}` 非物理 ⇒ Poisson 把漏端压回 ψ_n
    ⇒ **偏压进不去** ⇒ DIBL ≈ 0。若此探针不能变红，说明 B3 是假绿。
    """
    real = M2._rho_and_drho

    def no_shift(psi, mode, NA, ND, in_ox, v_t, n_i, phi_n_shift):
        return real(psi, mode, NA, ND, in_ox, v_t, n_i,
                    np.zeros_like(np.asarray(phi_n_shift, dtype=float)))

    with _mutated(items=[(M2, "_rho_and_drho", no_shift)]):
        return not _dibl_ok()


def probe_no_oxide_shifts_vth() -> bool:
    """把氧化层介电常数抹成 ε_si（等于去掉栅氧）⇒ 长沟道 V_th 剧烈偏移 ⇒ B1 必红。"""
    def all_si(y, t_ox):
        y = np.asarray(y, dtype=float)
        return np.full(y.size, M2.EPS_SI), np.full(y.size - 1, M2.EPS_SI)

    with _mutated(items=[(M2, "_face_eps", all_si)]):
        return not _longchannel_ok()


def probe_interface_eps_regression() -> bool:
    """界面节点误赋 ε_si（**本轮血案**：氧化层末段被调和平均成 5.85ε₀ ⇒ C_ox 偏高 9%）

    ⇒ 长沟道 V_th 系统性偏低 ~17 mV ⇒ B1 必红。守的是「面中点判介质」这条修正。
    """
    def bad_face_eps(y, t_ox):
        y = np.asarray(y, dtype=float)
        eps_node = np.where(y < float(t_ox), M2.EPS_OX, M2.EPS_SI)
        # 错法：法向面用「相邻节点调和平均」，界面节点为 ε_si ⇒ 末段氧化层被稀释
        ev = np.array([M2._harmonic(eps_node[j], eps_node[j + 1])
                       for j in range(eps_node.size - 1)], dtype=float)
        return eps_node, ev

    with _mutated(items=[(M2, "_face_eps", bad_face_eps)]):
        return not _longchannel_ok()


def probe_max_surface_potential_reverses() -> bool:
    """界面判据点取 **max** 而非 min ⇒ 短沟道趋势反向 ⇒ B2 必红。"""
    real = M2.surface_potential

    def use_max(sol):
        r = dict(real(sol))
        ps = np.asarray(sol["psi"][:, sol["j_if"]], dtype=float)
        i_lo, i_hi = sol["i_gate"]
        i_mx = int(i_lo + np.argmax(ps[i_lo:i_hi + 1]))
        r["psi_s_min"] = float(ps[i_mx])
        r["i_min"] = i_mx
        return r

    with _mutated(items=[(M2, "surface_potential", use_max)]):
        return not _rolloff_ok()


def probe_claim_iv_or_tops() -> bool:
    """注入「LDA 已算 I-V / TOPS」式口径 ⇒ 诚实护栏必红。"""
    return not _no_iv_or_tops_claim("本模块已给出完整 I-V 曲线与 TOPS/W 能效")


# ══════════════════════ 诚实护栏 ══════════════════════
_FORBIDDEN = ("I-V 曲线", "I-V曲线", "TOPS", "TOPS/W", "fJ/op")


def _no_iv_or_tops_claim(text: str) -> bool:
    """披露/文案里不得出现「已算 I-V」「TOPS」等未做或不该做的宣称。

    允许出现「不报 TOPS」「不含输运 ⇒ 无 I-V」这类**否定式**表述
    （窗口取 40 字符 —— "不报 TOPS/TOPS-W/fJ/op" 整串有 16 字符，
     12 字符窗口会漏判 ⇒ 判据误报，本轮血案）。
    """
    t = str(text)
    negatives = ("不报", "不含", "无 I-V", "无I-V", "不算", "非 LDA", "不宣称", "未做")
    for kw in _FORBIDDEN:
        pos = t.find(kw)
        while pos >= 0:
            head = t[max(0, pos - 40):pos + len(kw)]
            if not any(neg in head for neg in negatives):
                return False
            pos = t.find(kw, pos + 1)
    return True


def main() -> int:
    _fresh()

    # ══════════════════════ A 模块自检 ══════════════════════
    ok_a1 = M2.run_selfchecks(verbose=False)
    check("A1 mos_2d 自检 12/12（网格/掺杂/FV 面材质/收敛/长沟道 golden/roll-off/"
          "DIBL 指数律/t_ox/网格收敛/λ/红线拒绝/两变体互验）", ok_a1)
    ok_a2 = D2.device_2d_self_check(verbose=False)
    check("A2 device_2d 桥自检 8/8（量纲桥/长沟道 golden/roll-off/文献对照/DIBL 律/"
          "λ 同式/能力闭合表/诚实护栏）", ok_a2)

    # ══════════════════════ B 关键事实（name-first）══════════════════════
    cc = D2.cross_check_vth_2d_longchannel(lg_nm=1000.0, dx_target_nm=15.0)
    check("B1 长沟道 2D V_th ⟷ 教科书 1D 闭式（golden · rel < 2%）",
          cc["rel_err"] < 0.02 and cc["converged"],
          f"2D={cc['V_th_2d_v']:.4f} V · 1D={cc['V_th_golden_1d_v']:.4f} V · "
          f"Δ={cc['abs_diff_mv']:+.2f} mV · rel={cc['rel_err']:.3%}")

    ro = D2.rolloff_2d_report(Ls_nm=(65.0, 100.0, 250.0), **CHEAP)
    p65 = ro["points"][0]
    check("B2 roll-off **单调** 且 L=65 nm 显著下降（< −100 mV vs golden）",
          ro["monotone_rolloff"] and p65["dvth_vs_golden_mv"] < -100.0,
          f"ΔV_th(65nm)={p65['dvth_vs_golden_mv']:+.1f} mV · "
          f"V_th(65/100/250)=" +
          "/".join(f"{p['V_th_v']:.4f}" for p in ro["points"]))

    dib = D2.dibl_2d_report(Ls_nm=(65.0, 100.0, 150.0, 250.0), **CHEAP)
    law = dib["exponential_law"]
    check("B3 DIBL > 0 且 **ln(DIBL)–L 线性**（R² > 0.99 · 指数衰减律）",
          dib["points"][0]["dibl_mv_per_v"] > 10.0 and law["r2"] > 0.99,
          f"DIBL(65nm)={dib['points'][0]['dibl_mv_per_v']:.1f} mV/V · "
          f"ℓ_eff={law['decay_length_nm']:.1f} nm · R²={law['r2']:.5f}")

    nat = D2.natural_length_2d()
    check("B4 自然长度 λ：2D 求解器 与 E11-d 文献式 **同式**（独立实现）",
          nat["same_formula"], f"λ={nat['lda_2d_nm']:.2f} nm ≡ {nat['literature_nm']:.2f} nm")

    check("B5 网格收敛：dx 5→2.5 nm @Lg=250nm ⇒ ΔV_th < 3 mV", _grid_convergence_ok())
    check("B6 两变体互验：0 < V_th(boltzmann) − V_th(majority) < 30 mV @Lg=100nm",
          _mode_gap_ok(), f"Δ={M2.mos2d_vth_mode_gap(100e-9, dx_target=5e-9)*1e3:.1f} mV")

    cap = D2.short_channel_capability_report()
    check("B7 能力闭合表：闭合 3 项（roll-off / DIBL / λ）· 仍不可用 3 项（含 T2 锁）",
          len(cap["closed_by_e12"]) == 3 and len(cap["still_not_available"]) == 3
          and any("T2" in c["why"] for c in cap["still_not_available"]))

    ratio = abs(p65["dvth_vs_golden_mv"] / p65["yau_dvth_mv"])
    check("B8 与 E11-d **文献式对照**：2D roll-off 同量级（0.5 < 比值 < 2）· 对照非 golden",
          0.5 < ratio < 2.0,
          f"2D={p65['dvth_vs_golden_mv']:+.1f} mV vs Yau={p65['yau_dvth_mv']:+.1f} mV · "
          f"|比值|={ratio:.3f} · yau_computed_by_lda={p65['yau_computed_by_lda']}")

    check("B9 golden 单一定义：2D 桥的长沟道 golden **直调** "
          "device_pde.physics_vth_closed（不复制公式）",
          cc["golden_source"] == "lda_l2.ecore.device_pde.physics_vth_closed"
          and abs(DP.physics_vth_closed()["V_th"] - cc["V_th_golden_1d_v"]) < 1e-12)

    check("B10 🔴 **与底层模块交叉核对**：门禁数字 ≡ device_2d / mos_2d 实测（非卡自证）",
          abs(nat["lda_2d_nm"] - M2.natural_length() * 1e9) < 1e-9
          and abs(law["r2"] - M2.dibl_exponential_law(
              Ls=(65e-9, 150e-9, 250e-9))["r2"]) < 1e-6,
          f"λ {nat['lda_2d_nm']:.4f} ≡ {M2.natural_length()*1e9:.4f} nm")

    # ══════════════════════ C 突变探针 ══════════════════════
    check("C1 探针：电极全钉体内电位 ⇒ 无横向结 ⇒ roll-off 消失 ⇒ B2 必红",
          probe_flat_electrodes_no_rolloff() is True)
    check("C2 探针：强制 V_d ≡ 0 ⇒ DIBL 消失 ⇒ B3 必红",
          probe_zero_drain_bias_no_dibl() is True)
    check("C3 🔴 探针：去掉**电子准费米势分裂** ⇒ 偏压进不去 ⇒ DIBL≈0 ⇒ B3 必红（血案回归）",
          probe_no_qfl_split_kills_bias() is True)
    check("C4 探针：氧化层 ε 抹成 ε_si ⇒ 长沟道 V_th 偏移 ⇒ B1 必红",
          probe_no_oxide_shifts_vth() is True)
    check("C5 探针：界面节点误赋 ε_si（末段 C_ox 偏高 9%）⇒ 长沟道 V_th 偏 ⇒ B1 必红（血案回归）",
          probe_interface_eps_regression() is True)
    check("C6 探针：界面判据点取 **max** ⇒ 短沟道趋势反向 ⇒ B2 必红",
          probe_max_surface_potential_reverses() is True)
    check("C7 探针：注入「已算 I-V / TOPS」⇒ 诚实护栏必红",
          probe_claim_iv_or_tops() is True)

    # ══════════════════════ D 诚实护栏 ══════════════════════
    disc = D2.DEVICE_2D_DISCLOSURE
    check("D1 披露显式声明「准平衡静电求解 · 不含输运 ⇒ 无 I-V」",
          "不含输运" in disc["honest_boundary"] and "无 I-V" in disc["honest_boundary"])
    check("D2 披露不宣称未做的能力（I-V / TOPS / 器件性能）",
          _no_iv_or_tops_claim(json_dump(disc)))
    check("D3 T1 红线：candidate 恒 `is_oracle=False`，golden 由教科书闭式定",
          cc["is_oracle"] is False and ro["is_oracle"] is False and dib["is_oracle"] is False)

    # ══════════════════════ E 还原完整性 ══════════════════════
    _fresh()
    check("E1 探针后还原：长沟道 / roll-off / DIBL 三项复绿（无 patch 残留）",
          _longchannel_ok() and _rolloff_ok() and _dibl_ok())

    # ══════════════════════ K 自入 CI core（防静默漏接 · 血案 28）══════════════════════
    try:
        import run_ci_regression as _R
        in_core = "run_ecore_e12_smoke.py" in _R.CORE_SMOKES
        in_to = "run_ecore_e12_smoke.py" in _R._BUILTIN_TIMEOUT_OVERRIDE
    except Exception:
        in_core = in_to = False
    check("K1 本门禁已进 CORE_SMOKES 且已登记超时覆盖（防静默漏接）",
          bool(in_core and in_to), f"in_core={in_core} in_timeout_override={in_to}")

    bad = globals().get("FAIL", 0)
    good = globals().get("PASS", 0)
    print("")
    print("门禁 smoke：%d PASS / %d FAIL" % (good, bad))
    return 0 if bad == 0 else 1


def json_dump(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
