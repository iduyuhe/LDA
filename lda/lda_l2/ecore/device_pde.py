# -*- coding: utf-8 -*-
"""ecore · E11-c · **器件级 T1 内核桥**（MOSCAP PDE ⟷ 教科书闭式交叉验证）。

============================================================================
为什么存在（E11-b 勘查结论）
----------------------------------------------------------------------------
E11-b 勘查查明：ecore 此前与平台的**器件级 T1 内核零复用**——因为
`lda_solver/drift_diffusion_1d/2d` 解的是**两端 p-n 结**，而本包的器件模型是
**三端 MOSFET**（栅氧 + 反型层），**两者不是同一种器件**，无法直接对接
（见 `docs/LDA_电子计算征程_E11b_接缝勘查_2026-10-01.md` §3）。

E11-c 补齐这一环：平台新增 **MOS 结构 1D 自洽泊松内核**（`lda_solver/mos_1d.py`），
本模块把它与 ecore 接通——用**器件级 PDE 真解**校验**教科书闭式**，
让本包的器件侧首次拥有「**闭式 ⟷ PDE**」这条独立交叉验证路径。

口径（必须与平台一致）
----------------------
平台红线为**分层口径**（2026-09-11 §八§九 · 2026-09-23 逐步解锁）：
**器件级 T1 数值内核已解锁**；**T2 工艺真值 / 工艺角 / 流片永久锁**。
ecore 其余模块**主动限定在电路级**（设计取舍，非红线要求）；本模块是该取舍的
**受控例外**——只做「器件级真解 ⟷ 教科书闭式」交叉验证，**不替换**任何电路级
默认参数（见 §保护性约束）。

🔴 方法学定位（本段最易做歪处）
------------------------------
- **golden = 教科书闭式**（Sze 完整 Q_s 式 · 耗尽近似 V_th 式）＝ 科学原理层公共品；
- **candidate = PDE 数值解**（T1 内核）＝ `is_oracle=False`，**永不作真值**；
- 判据方向 = 「**PDE 收敛到闭式**」，**绝不**「用 PDE 当真值去标定闭式」。
  守卫 `guard_t1_not_oracle` 单一定义在 `lda_solver/redline.py`（**不复制**）。

🔴 保护性约束（E11-c 定稿铁律）
------------------------------
**绝不用 PDE 的 V_th 去替换 `NmosParams.vth0`（=0.4）**：`NmosParams` 被 23 处
构造、`vth0` 被 30 处引用，E1–E10 全部已上线数字（账本 / `/api/ecore_demo` 案例卡
188 判据 / DOCX / PPTX）都建立其上。物理 V_th 只作**并行第二器件模型 + 可核参数
建议**（`physics_vth_*` 的返回值），默认路径不变。

🔴 诚实边界
-----------
- 工作区：ψ_s ≤ 2.5φ_F（积累 → 强反型）内 PDE 与完整闭式一致到 **≤0.02%**；
  ψ_s ≥ 2.75φ_F 时反型层厚度（~0.03 nm）薄于界面网格 ⇒ 系统性低估，**不进判据**。
- 1D MOS 电容**无源/漏、无沟道长度** ⇒ **天然不含短沟道效应**（roll-off / DIBL）。
- `N_A` / `t_ox` / `V_FB` 为**公开典型量级占位（非 PDK）**；无实测锚。
- 不报 TOPS/TOPS-W/fJ/op。
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# 量纲桥（🔴 G-1：lda_solver 全 SI，ecore 全 µm 制 —— 必须显式换算，不得靠记忆）
# ---------------------------------------------------------------------------
UM_TO_M = 1.0e-6        # µm → m
NM_TO_M = 1.0e-9        # nm → m
CM3_TO_M3 = 1.0e6       # cm⁻³ → m⁻³
F_PER_UM2_TO_F_PER_M2 = 1.0e12   # F/µm² → F/m²


def um_to_m(v: float) -> float:
    """µm → m。"""
    return float(v) * UM_TO_M


def m_to_um(v: float) -> float:
    """m → µm。"""
    return float(v) / UM_TO_M


def nm_to_m(v: float) -> float:
    """nm → m。"""
    return float(v) * NM_TO_M


def m_to_nm(v: float) -> float:
    """m → nm。"""
    return float(v) / NM_TO_M


def cm3_to_m3(v: float) -> float:
    """cm⁻³ → m⁻³。"""
    return float(v) * CM3_TO_M3


def m3_to_cm3(v: float) -> float:
    """m⁻³ → cm⁻³。"""
    return float(v) / CM3_TO_M3


def cox_f_per_um2_to_f_per_m2(v: float) -> float:
    """面电容 F/µm² → F/m²（与 `mismatch.MISMATCH_PROCESS['cox_f_per_um2']` 同源）。"""
    return float(v) * F_PER_UM2_TO_F_PER_M2


# ecore 侧工程默认（与 E11-b 勘查所用一致）
NA_CM3_DEFAULT = 1.0e17        # 衬底掺杂 (cm⁻³, = 1e23 m⁻³，与 drift_diffusion_1d 同源)
T_OX_NM_DEFAULT = 4.0          # 栅氧厚度 (nm)
VFB_V_DEFAULT = -0.60          # 平带电压 (V)
DX_IF_NM_DEFAULT = 0.02        # 界面首点目标间距 (nm) · 强反型（2.5φ_F）处仍需 rel<0.1%
MU_N_TYPICAL_CM2_VS = 500.0    # 公开典型量级（体硅 NMOS 迁移率，tox≈4 nm）· 仅作对照


def _mos():
    """惰性导入器件级内核（避免 ecore 包在无 numpy 环境被导入时连带失败）。"""
    from lda_solver import mos_1d as M
    return M


# ---------------------------------------------------------------------------
# golden（教科书闭式）
# ---------------------------------------------------------------------------
def physics_vth_closed(n_a_cm3: float = NA_CM3_DEFAULT,
                       t_ox_nm: float = T_OX_NM_DEFAULT,
                       vfb_v: float = VFB_V_DEFAULT) -> dict:
    """**golden-B**：教科书耗尽近似阈值电压（工程单位入参）。

    V_th = V_FB + 2φ_F + √(2·q·ε_si·N_A·2φ_F)/C_ox（Sze §6.3 / 本科教材标准式）。
    入参用工程单位（cm⁻³ · nm · V），内部经量纲桥转 SI。
    """
    m = _mos()
    r = m.moscap_vth_closed_form(N_A=cm3_to_m3(n_a_cm3),
                                 t_ox=nm_to_m(t_ox_nm), VFB=float(vfb_v))
    return {
        "V_th": r["V_th"], "phi_f": r["phi_f"], "two_phi_f": r["two_phi_f"],
        "W_dmax_nm": m_to_nm(r["W_dmax"]), "Q_dep": r["Q_dep"],
        "C_ox_f_per_m2": r["C_ox"],
        "C_ox_f_per_um2": r["C_ox"] / F_PER_UM2_TO_F_PER_M2,
        "n_a_cm3": float(n_a_cm3), "t_ox_nm": float(t_ox_nm), "vfb_v": float(vfb_v),
        "provenance": r["provenance"], "is_oracle": True,   # 教科书闭式 = 科学原理层 ⇒ 可作真值
    }


def physics_qs_closed(psi_s_v: float, n_a_cm3: float = NA_CM3_DEFAULT) -> dict:
    """**golden-A**：Sze 完整半导体面电荷 Q_s(ψ_s) 闭式（含反型层与玻尔兹曼尾）。

    符号口径 = 物理电荷（耗尽区电离受主带负电 ⇒ ψ_s>0 时 Q_s<0）。
    """
    m = _mos()
    q = m.sze_qs_closed_form(float(psi_s_v), N_A=cm3_to_m3(n_a_cm3))
    return {"psi_s_v": float(psi_s_v), "Q_s": q, "n_a_cm3": float(n_a_cm3),
            "provenance": "design_rule_anchor_sze_complete", "is_oracle": True}


# ---------------------------------------------------------------------------
# candidate（器件级 T1 内核）
# ---------------------------------------------------------------------------
def physics_vth_pde(n_a_cm3: float = NA_CM3_DEFAULT,
                    t_ox_nm: float = T_OX_NM_DEFAULT,
                    vfb_v: float = VFB_V_DEFAULT,
                    dx_if_nm: float = DX_IF_NM_DEFAULT) -> dict:
    """**candidate**：由 MOSCAP 1D 自洽泊松解求出的物理阈值电压（`is_oracle=False`）。

    ψ_s = 2φ_F 处的栅压即 V_th（强反型判据）。🔴 只作候选，真值判据是教科书闭式。
    """
    m = _mos()
    s = m.moscap_vth_pde(N_A=cm3_to_m3(n_a_cm3), t_ox=nm_to_m(t_ox_nm),
                         VFB=float(vfb_v), dx_if=nm_to_m(dx_if_nm))
    return {
        "V_th": s["V_th"], "psi_s_vth": s["psi_s_vth"],
        "Q_s": s["Q_s"], "E_s": s["E_s"], "V_g": s["V_g"],
        "converged": s["converged"], "n_grid": s["n_grid"], "n_iter": s["n_iter"],
        "provenance": s["provenance"], "is_oracle": s["is_oracle"],
    }


def moscap_qs_pde(psi_s_v: float, n_a_cm3: float = NA_CM3_DEFAULT,
                  dx_if_nm: float = DX_IF_NM_DEFAULT) -> dict:
    """**candidate**：给定表面势的 PDE 面电荷（含独立路径 Q_s_body，供自洽核对）。"""
    m = _mos()
    s = m.solve_moscap_1d(float(psi_s_v), N_A=cm3_to_m3(n_a_cm3),
                          dx_if=nm_to_m(dx_if_nm))
    return {"psi_s_v": s["psi_s"], "Q_s": s["Q_s"], "Q_s_body": s["Q_s_body"],
            "E_s": s["E_s"], "V_g": s["V_g"], "converged": s["converged"],
            "n_grid": s["n_grid"], "provenance": s["provenance"],
            "is_oracle": s["is_oracle"]}


# ---------------------------------------------------------------------------
# 交叉验证
# ---------------------------------------------------------------------------
def cross_check_vth(n_a_cm3: float = NA_CM3_DEFAULT,
                    t_ox_nm: float = T_OX_NM_DEFAULT,
                    vfb_v: float = VFB_V_DEFAULT,
                    dx_if_nm: float = DX_IF_NM_DEFAULT,
                    guard: bool = True) -> dict:
    """V_th 交叉验证：**教科书闭式（golden） ⟷ PDE 数值解（candidate）**。

    返回 {golden, cand, rel_err, abs_err, converged, is_oracle}。
    `guard=True` 时接线 `guard_t1_not_oracle`（candidate 必须是候选，不得标 ORACLE）。
    """
    g = physics_vth_closed(n_a_cm3, t_ox_nm, vfb_v)
    c = physics_vth_pde(n_a_cm3, t_ox_nm, vfb_v, dx_if_nm)
    rel = abs(c["V_th"] - g["V_th"]) / abs(g["V_th"])
    if guard:
        from lda_solver.redline import guard_t1_not_oracle
        guard_t1_not_oracle(c)
    return {
        "V_th_golden": g["V_th"], "V_th_cand": c["V_th"],
        "abs_err": abs(c["V_th"] - g["V_th"]), "rel_err": rel,
        "converged": c["converged"], "n_grid": c["n_grid"],
        "golden_source": g["provenance"], "cand_source": c["provenance"],
        "is_oracle": c["is_oracle"],
        "params": {"n_a_cm3": float(n_a_cm3), "t_ox_nm": float(t_ox_nm),
                   "vfb_v": float(vfb_v)},
    }


def cross_check_qs(psi_factors=(0.5, 1.0, 1.5, 2.0, 2.25, 2.5),
                   n_a_cm3: float = NA_CM3_DEFAULT,
                   dx_if_nm: float = DX_IF_NM_DEFAULT,
                   guard: bool = True) -> list:
    """Q_s 跨点交叉验证：在若干 ψ_s = f·φ_F 处比对 PDE 与完整闭式。

    跨点是**必需的**——在 ψ_s = 2φ_F 处两者恰好数学重合（charge-sheet 恒等），
    单点比对不构成独立验证。返回点表（含 rel_err）。
    """
    m = _mos()
    pf = m.phi_f(cm3_to_m3(n_a_cm3))
    out = []
    for f in psi_factors:
        ps = float(f) * pf
        g = physics_qs_closed(ps, n_a_cm3)
        c = moscap_qs_pde(ps, n_a_cm3, dx_if_nm)
        rel = abs(c["Q_s"] - g["Q_s"]) / abs(g["Q_s"])
        if guard:
            from lda_solver.redline import guard_t1_not_oracle
            guard_t1_not_oracle(c)
        out.append({"psi_f_over_phi_f": float(f), "psi_s_v": ps,
                    "Q_s_golden": g["Q_s"], "Q_s_cand": c["Q_s"],
                    "rel_err": rel, "converged": c["converged"],
                    "n_surface_m3": None, "is_oracle": c["is_oracle"]})
    return out


def pde_vs_closed_sweep(n_a_cm3: float = NA_CM3_DEFAULT,
                        t_ox_nm_list=(2.0, 4.0, 8.0),
                        vfb_v: float = VFB_V_DEFAULT,
                        dx_if_nm: float = DX_IF_NM_DEFAULT) -> list:
    """氧化物厚度扫描下的 V_th 闭式 ⟷ PDE 一致性表。"""
    return [cross_check_vth(n_a_cm3, t, vfb_v, dx_if_nm)
            for t in t_ox_nm_list]


# ---------------------------------------------------------------------------
# G-3：参数自洽性显式化（**只报告，不改值**）
# ---------------------------------------------------------------------------
def parameter_consistency_report(n_a_cm3: float = NA_CM3_DEFAULT,
                                 mu_typical_cm2_vs: float = MU_N_TYPICAL_CM2_VS) -> dict:
    """把「跨模块参数不自洽」**显式可见**（E11-b 缺口 G-3）。

    `ecore/mosfet.py` 的 `kp = µ·C_ox = 120 µA/V²` 与 `ecore/mismatch.py` 的
    `C_ox = 8.6 fF/µm²` 反推出的 µ 与体硅典型值差约 4×。本函数只**报告**该偏差
    （比值、各自来源），**不修改任何模块的参数**——统一数值会改动 E1–E10 全部已
    上线数字（见模块 docstring 的保护性约束）。
    """
    from lda_l2.ecore.mismatch import MISMATCH_PROCESS
    from lda_l2.ecore.mosfet import NmosParams
    kp = float(NmosParams().kp)                                   # A/V²
    cox_um2 = float(MISMATCH_PROCESS["cox_f_per_um2"])            # F/µm²
    cox_si = cox_f_per_um2_to_f_per_m2(cox_um2)                   # F/m²
    mu_implied_si = kp / cox_si                                   # m²/(V·s)
    mu_implied_cm2 = mu_implied_si * 1.0e4
    ratio = mu_typical_cm2_vs / mu_implied_cm2 if mu_implied_cm2 > 0 else float("inf")
    return {
        "kp_a_per_v2": kp,
        "cox_f_per_um2": cox_um2,
        "cox_f_per_m2": cox_si,
        "t_ox_nm_implied": m_to_nm(3.9 * 8.854187817e-12 / cox_si),
        "mu_implied_cm2_vs": mu_implied_cm2,
        "mu_typical_cm2_vs": float(mu_typical_cm2_vs),
        "ratio_typical_over_implied": ratio,
        "consistent": bool(0.5 <= ratio <= 2.0),
        "note": "两模块各自写占位值 ⇒ 不自洽；本报告只**显式暴露**，不修改任何默认值"
                "（改值会波及 E1–E10 全部已上线数字）。",
    }


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def device_pde_self_check(verbose: bool = True) -> bool:
    """桥接层自检：量纲桥可逆 · 闭式/候选对拍 · 跨点一致 · G-3 可见 · 守卫接线。"""
    msgs = []

    def chk(name, cond, _d=""):
        msgs.append((name, bool(cond)))
        return bool(cond)

    ok = True

    # ① 量纲桥往返可逆（µm↔m · cm⁻³↔m⁻³ · nm↔m · F/µm²↔F/m²）
    rt = (abs(m_to_um(um_to_m(3.7)) - 3.7) < 1e-12
          and abs(m3_to_cm3(cm3_to_m3(1e17)) - 1e17) < 1e2
          and abs(m_to_nm(nm_to_m(4.0)) - 4.0) < 1e-12
          and abs(cox_f_per_um2_to_f_per_m2(8.6e-15) - 8.6e-3) < 1e-15)
    ok &= chk("① 量纲桥往返可逆（µm/cm⁻³/nm/F·µm⁻²）", rt)

    # ② Cox 换算与教科书 4 nm SiO₂ 一致（<1%）
    cox_std = 3.9 * 8.854187817e-12 / nm_to_m(4.0)
    cox_mm = cox_f_per_um2_to_f_per_m2(8.6e-15)
    rel = abs(cox_mm - cox_std) / cox_std
    ok &= chk("② mismatch 的 C_ox 换算 ≡ 4 nm SiO₂ 教科书值（<1%）", rel < 0.01,
              "rel=%.3f%%" % (rel * 100))

    # ③ V_th 闭式 ⟷ PDE 交叉验证
    cc = cross_check_vth()
    ok &= chk("③ V_th：教科书闭式 ⟷ PDE 一致性（rel < 2%）",
              cc["rel_err"] < 0.02 and cc["converged"],
              "gold=%.4f V · cand=%.4f V · rel=%.4f%%" %
              (cc["V_th_golden"], cc["V_th_cand"], cc["rel_err"] * 100))

    # ④ 跨点 Q_s 一致（工作区 ψ_s ≤ 2.5φ_F 内 rel < 0.1%）
    pts = cross_check_qs()
    worst = max(p["rel_err"] for p in pts)
    ok &= chk("④ Q_s 跨点一致（ψ_s ≤ 2.5φ_F · 最差 rel < 0.1%）", worst < 1e-3,
              "最差 %.4f%% @ψ_s=%.2fφ_F" %
              (worst * 100, pts[int(max(range(len(pts)), key=lambda i: pts[i]['rel_err']))]
               ["psi_f_over_phi_f"]))

    # ⑤ 🔴 候选永不标 ORACLE
    cand_flags = [cc["is_oracle"]] + [p["is_oracle"] for p in pts]
    ok &= chk("⑤ 全部候选 is_oracle=False；golden 标 True（教科书闭式）",
              (not any(cand_flags)) and physics_vth_closed()["is_oracle"] is True)

    # ⑥ guard_t1_not_oracle 接线：force_oracle 必 raise
    from lda_solver.redline import guard_t1_not_oracle
    raised = False
    try:
        guard_t1_not_oracle(physics_vth_pde(), force_oracle=True)
    except RuntimeError:
        raised = True
    ok &= chk("⑥ guard_t1_not_oracle 已接线（force_oracle 必 raise）", raised)

    # ⑦ G-3 参数自洽性显式可见（报告存在且给出比值）
    pr = parameter_consistency_report()
    ok &= chk("⑦ G-3 参数自洽性报告可见（μ 反推 vs 典型）",
              pr["mu_implied_cm2_vs"] > 0 and pr["ratio_typical_over_implied"] > 0,
              "μ(PDE 反推)=%.0f vs 典型 %.0f cm²/V·s · 比=%.2f×" %
              (pr["mu_implied_cm2_vs"], pr["mu_typical_cm2_vs"],
               pr["ratio_typical_over_implied"]))

    # ⑧ 保护性约束：NmosParams 默认值逐位不变
    from lda_l2.ecore.mosfet import NmosParams
    p = NmosParams()
    ok &= chk("⑧ 保护性约束：NmosParams 默认值逐位不变（vth0=0.4）",
              p.vth0 == 0.4 and p.kp == 120e-6 and p.lam == 0.02 and p.w_over_l == 10.0,
              "kp=%.1e vth0=%.2f lam=%.2f W/L=%.1f" %
              (p.kp, p.vth0, p.lam, p.w_over_l))

    if verbose:
        for name, good in msgs:
            print("  [%s] %s" % ("PASS" if good else "FAIL", name))
        print("  selfcheck %d/%d" % (sum(1 for _, g_ in msgs if g_), len(msgs)))
    return bool(ok)


DEVICE_PDE_DISCLOSURE: dict = {
    "scope": "ecore 对**器件级 T1 内核**（`lda_solver/mos_1d.py` MOSCAP 自洽泊松）的桥接与"
             "交叉验证。ecore 其余模块**主动限定在电路级**（设计取舍，非红线要求）；本模块是该"
             "取舍的**受控例外**。平台红线为**分层口径**（器件级 T1 已解锁 · T2 工艺真值/工艺角/"
             "流片永久锁）。",
    "method": "golden = 教科书闭式（Sze 完整 Q_s 式 / 耗尽近似 V_th 式，科学原理层公共品）；"
              "candidate = PDE 数值解（T1 内核，`is_oracle=False`）。判据方向 = PDE 收敛到闭式，"
              "**绝不**用 PDE 当真值标定闭式。",
    "no_replace": "🔴 **不替换任何电路级默认参数**：物理 V_th 只作并行第二器件模型与可核参数"
                  "建议；`NmosParams` 默认值逐位不变（改值会波及 E1–E10 全部已上线数字）。",
    "validity_window": "PDE 与完整闭式在 ψ_s ≤ 2.5φ_F（积累→强反型）内一致到 ≤0.02%；"
                       "ψ_s ≥ 2.75φ_F 时反型层（~0.03 nm）薄于界面网格 ⇒ 系统性低估，不进判据。",
    "no_short_channel": "1D MOS 电容**无源/漏、无沟道长度** ⇒ **天然不含短沟道效应**"
                        "（V_th roll-off / DIBL 均不出现）；平台无 2D MOS 能力。",
    "params_are_typical": "N_A / t_ox / V_FB 为**公开典型量级占位（非 PDK）**；无实测锚；"
                          "不报 TOPS/TOPS-W/fJ/op。",
}


if __name__ == "__main__":
    print("=== 量纲桥 ===")
    print("  1 µm = %.1e m · 1 cm⁻³ = %.1e m⁻³ · 8.6 fF/µm² = %.4e F/m²" %
          (UM_TO_M, CM3_TO_M3, cox_f_per_um2_to_f_per_m2(8.6e-15)))
    print("=== V_th 交叉验证（闭式 ⟷ PDE）===")
    cc = cross_check_vth()
    print("  golden=%.4f V · cand=%.4f V · rel=%.4f%% · converged=%s" %
          (cc["V_th_golden"], cc["V_th_cand"], cc["rel_err"] * 100, cc["converged"]))
    print("=== 自检 ===")
    device_pde_self_check(verbose=True)
