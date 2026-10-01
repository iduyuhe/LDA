# -*- coding: utf-8 -*-
"""ecore · E12 · **2D MOS 桥**（短沟道效应：从「算不了」到「算得了」）。

============================================================================
为什么存在（E12 · 电子计算征程）
----------------------------------------------------------------------------
E11-d（`device_limits.py`）把短沟道效应登记为**平台算不了**：
只引文献经验闭式（Yau 电荷共享 / DIBL 经验式），每项标 `computed_by_lda=False`。

E12 补上能力本身：平台新增 `lda_solver/mos_2d.py`（四端 2D MOSFET 自洽泊松）。
本模块是 ecore 侧的**桥**，做三件事：
  ① **量纲桥**（nm 级几何 / cm⁻³ ⟷ m⁻³；与 E11-c 同源，往返可逆）；
  ② **交叉验证**：2D 长沟道极限 ⟷ E11-c 的教科书 1D 闭式（**golden**）；
  ③ **短沟道报告**：roll-off / DIBL 由 2D 数值解给出，并与 E11-d 的文献式**对照**
     （对照 ≠ golden：文献式是经验拟合；本模块还给出**指数衰减律**这一独立物理判据）。

🔴 方法学独立性（判据为什么算数）
  golden  = 教科书 1D 长沟道耗尽式（`device_pde.physics_vth_closed`，E11-c 单一定义）
  cand    = 2D 数值泊松解（`lda_solver/mos_2d.py`，`is_oracle=False`）
  ⇒ 判据 = **长沟道极限 2D 收敛到 1D 闭式**；以及短沟道偏离量的**指数衰减律**（R²）。
  绝不反过来「用 2D 数值解当真值去标定文献式」——那会当场破红线。

🔴 honest 边界
  · 本段是**准平衡 / 耗尽静电求解**，**不含漂移扩散输运** ⇒ **不产 I-V**；
    V_th 用「界面最低表面势达 +φ_F」判据（非恒定电流法——那需要 I-V）。
  · 结构为教科书突变结 + 2 nm 平滑；无 LDD / halo / 应力 / 量子修正 / 栅重叠。
  · 参数（N_A / N_SD / t_ox / x_j / V_FB）为**公开典型量级占位**，**非 PDK**；无实测锚。
  · 不报 TOPS/TOPS-W/fJ/op；不宣称器件性能。
  · 🔴 **EAR 744.23**：声明仅用于成熟节点 / 非先进用途半导体器件设计仿真。
  · 依赖 scipy ⇒ 本模块用**函数内惰性导入**（无 scipy 环境仍可 import 本模块）。
"""
from __future__ import annotations

from typing import Dict, List, Optional

# 量纲桥（与 E11-c 同源，不复制第二份定义）
try:  # 包内导入
    from .device_pde import (  # noqa: F401
        NM_TO_M,
        cm3_to_m3,
        m3_to_cm3,
        m_to_nm,
        nm_to_m,
    )
except ImportError:  # 脚本直跑自检
    from lda_l2.ecore.device_pde import (  # type: ignore  # noqa: F401
        NM_TO_M, cm3_to_m3, m3_to_cm3, m_to_nm, nm_to_m)

# ---- 结构默认（公开典型量级占位 · 非 PDK；单位 nm）----
LG_NM_DEFAULT = 100.0
XJ_NM_DEFAULT = 30.0
T_OX_NM_DEFAULT = 4.0
NA_CM3_DEFAULT = 1.0e17
N_SD_CM3_DEFAULT = 1.0e20
T_SI_NM_DEFAULT = 150.0
L_SIDE_NM_DEFAULT = 100.0

#: roll-off 扫描默认栅长（nm）
ROLLOFF_LS_NM = (65.0, 100.0, 150.0, 250.0, 500.0)
#: 长沟道参考栅长（nm）—— 该长度下 2D 应已收敛到 1D 闭式
LONG_CHANNEL_NM = 1000.0


def _m2():
    """惰性导入 2D 求解器（mos_2d 依赖 scipy ⇒ 不可放在模块级）。"""
    from lda_solver import mos_2d as M2
    return M2


def _dx_for(lg_nm: float, dx_target_nm: Optional[float] = None) -> float:
    """按栅长选网格（长沟道物理平滑 ⇒ 可用粗网格，省算力）。"""
    if dx_target_nm is not None:
        return float(dx_target_nm) * NM_TO_M
    lg = float(lg_nm)
    return (10.0 if lg >= 400.0 else (5.0 if lg >= 200.0 else 2.5)) * NM_TO_M


def _dev_kw(lg_nm: float = LG_NM_DEFAULT, dx_target_nm: Optional[float] = None,
            **over) -> Dict:
    m2 = _m2()
    kw = {
        "Lg": float(lg_nm) * NM_TO_M,
        "xj": float(over.pop("xj_nm", XJ_NM_DEFAULT)) * NM_TO_M,
        "t_ox": float(over.pop("t_ox_nm", T_OX_NM_DEFAULT)) * NM_TO_M,
        "N_A": cm3_to_m3(float(over.pop("n_a_cm3", NA_CM3_DEFAULT))),
        "N_SD": cm3_to_m3(float(over.pop("n_sd_cm3", N_SD_CM3_DEFAULT))),
        "T_si": float(over.pop("t_si_nm", T_SI_NM_DEFAULT)) * NM_TO_M,
        "L_side": float(over.pop("l_side_nm", L_SIDE_NM_DEFAULT)) * NM_TO_M,
        "dx_target": _dx_for(lg_nm, dx_target_nm),
    }
    kw.update(over)
    assert m2 is not None
    return kw


# ---------------------------------------------------------------------------
# ① 量纲桥
# ---------------------------------------------------------------------------
def dimension_roundtrip_report() -> Dict:
    """nm 级几何 / cm⁻³ 掺杂的**往返可逆**检验（G-1 同型：两侧单位制不互通）。"""
    checks = []
    for v in (1.0, 65.0, 1000.0):
        checks.append({"kind": "nm↔m", "v": v,
                       "round": m_to_nm(nm_to_m(v)),
                       "reversible": abs(m_to_nm(nm_to_m(v)) - v) < 1e-9})
    for v in (1.0e16, 1.0e17, 1.0e20):
        checks.append({"kind": "cm^-3↔m^-3", "v": v,
                       "round": m3_to_cm3(cm3_to_m3(v)),
                       "reversible": abs(m3_to_cm3(cm3_to_m3(v)) - v) / v < 1e-12})
    ok = all(c["reversible"] for c in checks)
    return {"checks": checks, "all_reversible": bool(ok),
            "note": "nm 级几何与 cm⁻³ 掺杂经同一桥往返无损"}


# ---------------------------------------------------------------------------
# ② 交叉验证：2D 长沟道 ⟷ 教科书 1D 闭式（golden）
# ---------------------------------------------------------------------------
def cross_check_vth_2d_longchannel(lg_nm: float = LONG_CHANNEL_NM,
                                   n_a_cm3: float = NA_CM3_DEFAULT,
                                   t_ox_nm: float = T_OX_NM_DEFAULT,
                                   dx_target_nm: Optional[float] = 10.0) -> Dict:
    """**本段最强判据**：栅长 → ∞ 时，2D 数值 V_th 必须收敛到教科书 1D 闭式。

    golden 直调 `device_pde.physics_vth_closed`（E11-c 单一定义，不复制公式）。
    """
    m2 = _m2()
    from lda_l2.ecore import device_pde as DP
    golden = DP.physics_vth_closed(n_a_cm3=n_a_cm3, t_ox_nm=t_ox_nm)
    dev = m2.mos2d_device(**_dev_kw(lg_nm, dx_target_nm, n_a_cm3=n_a_cm3,
                                    t_ox_nm=t_ox_nm))
    r2d = m2.extract_vth_2d(Vd=0.05, mode="majority", device=dev)
    rel = abs(r2d["V_th"] - golden["V_th"]) / golden["V_th"]
    return {"Lg_nm": float(lg_nm), "V_th_2d_v": float(r2d["V_th"]),
            "V_th_golden_1d_v": float(golden["V_th"]),
            "abs_diff_mv": float((r2d["V_th"] - golden["V_th"]) * 1e3),
            "rel_err": float(rel), "converged": bool(r2d["converged"]),
            "golden_source": "lda_l2.ecore.device_pde.physics_vth_closed",
            "is_oracle": False}


# ---------------------------------------------------------------------------
# ③ 短沟道报告（roll-off / DIBL）
# ---------------------------------------------------------------------------
def rolloff_2d_report(Ls_nm=ROLLOFF_LS_NM, v_d_v: float = 0.05,
                      n_a_cm3: float = NA_CM3_DEFAULT,
                      t_ox_nm: float = T_OX_NM_DEFAULT,
                      dx_target_nm: Optional[float] = None) -> Dict:
    """2D 数值 roll-off（ΔV_th vs L）+ 与 E11-d 文献式（Yau）**对照**。

    🔴 `yau_dvth_mv` 是**文献经验式**、`computed_by_lda=False`，只作对照坐标；
    判据永远用 2D 数值列（`dvth_vs_golden_mv`）。
    """
    m2 = _m2()
    from lda_l2.ecore import device_limits as DL
    from lda_l2.ecore import device_pde as DP
    golden = DP.physics_vth_closed(n_a_cm3=n_a_cm3, t_ox_nm=t_ox_nm)["V_th"]
    pts: List[Dict] = []
    for lg in Ls_nm:
        kw = _dev_kw(lg, dx_target_nm, n_a_cm3=n_a_cm3, t_ox_nm=t_ox_nm)
        dev = m2.mos2d_device(**kw)
        r = m2.extract_vth_2d(Vd=v_d_v, mode="majority", device=dev)
        yau = DL.yau_rolloff_dvth(float(lg) * 1e-3, n_a_cm3=n_a_cm3,
                                  t_ox_nm=t_ox_nm)
        pts.append({
            "Lg_nm": float(lg), "V_th_v": float(r["V_th"]),
            "dvth_vs_golden_mv": float((r["V_th"] - golden) * 1e3),
            "yau_dvth_mv": float(yau["dV_th_v"] * 1e3),
            "yau_computed_by_lda": False, "converged": bool(r["converged"]),
        })
    ref = max(pts, key=lambda p: p["Lg_nm"])["V_th_v"]
    for p in pts:
        p["rolloff_vs_longest_mv"] = float((p["V_th_v"] - ref) * 1e3)
    return {"V_d_v": float(v_d_v), "golden_1d_v": float(golden),
            "points": pts,
            "monotone_rolloff": bool(all(
                pts[i]["V_th_v"] >= pts[i - 1]["V_th_v"] - 1e-9
                for i in range(1, len(pts)))),        # 列表按 L 递增 ⇒ V_th 应递增
            "is_oracle": False}


def dibl_2d_report(Ls_nm=(65.0, 100.0, 150.0, 250.0), v_d_lo: float = 0.05,
                   v_d_hi: float = 1.0, n_a_cm3: float = NA_CM3_DEFAULT,
                   t_ox_nm: float = T_OX_NM_DEFAULT,
                   dx_target_nm: Optional[float] = None) -> Dict:
    """2D 数值 DIBL + **指数衰减律**检验 + 与 E11-d 文献式**对照**。"""
    m2 = _m2()
    from lda_l2.ecore import device_limits as DL
    pts = []
    for lg in Ls_nm:
        kw = _dev_kw(lg, dx_target_nm, n_a_cm3=n_a_cm3, t_ox_nm=t_ox_nm)
        dev = m2.mos2d_device(**kw)
        a = m2.extract_vth_2d(Vd=v_d_lo, mode="majority", device=dev)
        b = m2.extract_vth_2d(Vd=v_d_hi, mode="majority", device=dev)
        dibl = (a["V_th"] - b["V_th"]) / (v_d_hi - v_d_lo) * 1e3      # mV/V
        lit = DL.dibl_dvth(float(lg) * 1e-3, v_ds_v=v_d_hi,
                           t_ox_nm=t_ox_nm)
        pts.append({"Lg_nm": float(lg), "vth_lo_v": a["V_th"], "vth_hi_v": b["V_th"],
                    "dibl_mv_per_v": float(dibl),
                    "literature_dibl_mv_per_v": float(-lit["dV_th_v"] / v_d_hi * 1e3),
                    "literature_computed_by_lda": False})
    law = m2.dibl_exponential_law(Ls=(65e-9, 150e-9, 250e-9))
    return {"points": pts, "v_d_lo": float(v_d_lo), "v_d_hi": float(v_d_hi),
            "exponential_law": {"r2": float(law["r2"]),
                                "decay_length_nm": float(law["decay_length_nm"])},
            "is_oracle": False}


def natural_length_2d(x_j_nm: float = XJ_NM_DEFAULT,
                      t_ox_nm: float = T_OX_NM_DEFAULT) -> Dict:
    """2D 求解器与 E11-d 文献式的**自然长度同一性**检验（应逐位同式）。"""
    m2 = _m2()
    from lda_l2.ecore import device_limits as DL
    mine = m2.natural_length(float(x_j_nm) * NM_TO_M, float(t_ox_nm) * NM_TO_M)
    lit = DL.dibl_characteristic_length(float(t_ox_nm), float(x_j_nm) * 1e-3)
    return {"lda_2d_nm": float(mine * 1e9), "literature_nm": float(lit * 1e9),
            "same_formula": abs(mine - lit) / lit < 1e-12,
            "note": "λ = √(ε_si·t_ox·x_j/ε_ox)：2D 求解器与文献式**同式**（互为独立实现）"}


def short_channel_capability_report() -> Dict:
    """E11-d「算不了」→ E12「算得了」的**能力闭合表**（对外可直接引用）。"""
    return {
        "closed_by_e12": [
            {"item": "V_th roll-off（ΔV_th vs L）",
             "e11d_status": "文献式代入（Yau 电荷共享）· computed_by_lda=False",
             "e12_status": "2D 数值泊松解**自然涌现** · 与文献式同量级对照"},
            {"item": "DIBL（ΔV_th/ΔV_ds）",
             "e11d_status": "文献式代入（经验式 −0.4·V_ds·e^{−L/ℓ}）· computed_by_lda=False",
             "e12_status": "2D 数值解给出 · 且满足**指数衰减律**（ln DIBL–L 线性 R²>0.99）"},
            {"item": "自然长度校验",
             "e11d_status": "仅文献式标称值",
             "e12_status": "2D 求解器与文献式**同式**（独立实现）· 且指数律拟合的 ℓ_eff 可比"},
        ],
        "still_not_available": [
            {"item": "I–V 特性 / 亚阈值摆幅（从电流）",
             "why": "本段为**准平衡静电求解**，不含漂移扩散输运 ⇒ 无 I-V",
             "candidate": "E13（Gummel 2D 输运 + 准费米势分裂）"},
            {"item": "工艺角 / PDK 标定 / 硅验证",
             "why": "**T2 永久锁**（需 NDA + 流片）——属商业路径，非求解器精度问题",
             "candidate": "不在平台红线内"},
            {"item": "LDD / halo / 应力 / 量子修正",
             "why": "结构为教科书突变结模型",
             "candidate": "可选扩展"},
        ],
        "is_oracle": False,
    }


def device_2d_compute_rolloff_dibl_for_case() -> Dict:
    """案例卡用的一次性汇总（**只读 · 数字硬编码在卡侧，由门禁与模块交叉核对**）。

    ⚠️ 本函数只负责给出「与模块同源」的实测值；**不做 WebUI 计算**。
    """
    long_ = cross_check_vth_2d_longchannel()
    ro = rolloff_2d_report(Ls_nm=(65.0, 100.0, 250.0))
    dib = dibl_2d_report(Ls_nm=(65.0,), v_d_lo=0.05, v_d_hi=1.0)
    nat = natural_length_2d()
    return {"long_channel": long_, "rolloff": ro, "dibl": dib,
            "natural_length": nat}


DEVICE_2D_DISCLOSURE: dict = {
    "route": "电子计算征程 E12 · 2D MOS 求解器（短沟道效应：算不了 → 算得了）",
    "capability": "四端（栅/源/漏/衬底）2D MOSFET 自洽泊松：变系数 FV 离散（按面中点判介质）"
                  "+ 分段边界条件 + 电子准费米势分裂 + 阻尼牛顿/continuation",
    "golden": "教科书 1D 长沟道耗尽式（`device_pde.physics_vth_closed` · E11-c 单一定义）",
    "candidate": "2D 数值泊松解（`lda_solver/mos_2d.py`）· is_oracle=False",
    "two_variants": "mode='majority'（耗尽近似，任意 V_d）/ mode='boltzmann'（含反型层，仅 V_d=0）",
    "honest_boundary": "准平衡静电求解，**不含输运 ⇒ 无 I-V**；V_th = 界面最低表面势达 +φ_F；"
                       "结构为教科书突变结 + 2 nm 平滑，无 LDD/halo/应力/量子修正；"
                       "参数为公开典型量级占位（非 PDK）；不报 TOPS/TOPS-W/fJ/op",
    "redline": "红线 = 分层口径（器件级 T1 已解锁 · T2 工艺真值/工艺角/流片永久锁）；"
               "T1 输出永不作 ORACLE；LLM 不进判决路径；EAR 744.23 成熟节点用途",
}


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def device_2d_self_check(verbose: bool = True) -> bool:
    msgs = []

    def chk(name, cond, det=""):
        msgs.append((name, bool(cond), det))
        return bool(cond)

    ok = True

    # ① 量纲桥往返可逆
    dr = dimension_roundtrip_report()
    ok &= chk("① 量纲桥（nm 级几何 / cm⁻³ 掺杂）往返可逆", dr["all_reversible"],
              f"{len(dr['checks'])} 项")

    # ② 长沟道 ⟷ 教科书 1D 闭式（golden）
    cc = cross_check_vth_2d_longchannel()
    ok &= chk("② 长沟道 2D V_th ⟷ 教科书 1D 闭式（rel < 2%）",
              cc["rel_err"] < 0.02,
              f"2D={cc['V_th_2d_v']:.4f} · 1D={cc['V_th_golden_1d_v']:.4f} V · "
              f"rel={cc['rel_err']:.3%}")

    # ③ roll-off：单调 + 短沟道显著低于长沟道
    ro = rolloff_2d_report(Ls_nm=(65.0, 100.0, 250.0))
    p65 = ro["points"][0]
    ok &= chk("③ roll-off 单调 且 L=65nm 显著下降（< −100 mV vs golden）",
              ro["monotone_rolloff"] and p65["dvth_vs_golden_mv"] < -100.0,
              f"ΔV_th(65nm)={p65['dvth_vs_golden_mv']:+.1f} mV · "
              f"文献式={p65['yau_dvth_mv']:+.1f} mV")

    # ④ 2D 与文献式**同量级**（对照，非 golden）
    ratio = abs(p65["dvth_vs_golden_mv"] / p65["yau_dvth_mv"])
    ok &= chk("④ 2D 数值 roll-off 与 Yau 文献式**同量级**（0.5 < |比值| < 2）",
              0.5 < ratio < 2.0, f"|2D/文献| = {ratio:.3f}")

    # ⑤ DIBL 存在且随 L 指数衰减
    dib = dibl_2d_report(Ls_nm=(65.0,))
    law = dib["exponential_law"]
    ok &= chk("⑤ DIBL > 0 且 ln(DIBL)–L 线性（R² > 0.99 · 指数衰减律）",
              dib["points"][0]["dibl_mv_per_v"] > 10.0 and law["r2"] > 0.99,
              f"DIBL(65nm)={dib['points'][0]['dibl_mv_per_v']:.1f} mV/V · "
              f"ℓ_eff={law['decay_length_nm']:.1f} nm · R²={law['r2']:.5f}")

    # ⑥ 自然长度：2D 求解器与文献式同式
    nat = natural_length_2d()
    ok &= chk("⑥ 自然长度 λ：2D 求解器与 E11-d 文献式**同式**",
              nat["same_formula"],
              f"λ={nat['lda_2d_nm']:.2f} nm ≡ {nat['literature_nm']:.2f} nm")

    # ⑦ 能力闭合表：闭合 3 项 + 仍不可用 3 项（含 T2）
    cap = short_channel_capability_report()
    ok &= chk("⑦ 能力闭合表：闭合 3 项 · 仍不可用 3 项（含 T2 永久锁）",
              len(cap["closed_by_e12"]) == 3 and len(cap["still_not_available"]) == 3
              and any("T2" in c["why"] for c in cap["still_not_available"]))

    # ⑧ 诚实护栏：不宣称 I-V / TOPS
    ok &= chk("⑧ 披露显式声明「不含输运 ⇒ 无 I-V」且不报 TOPS",
              "不含输运" in DEVICE_2D_DISCLOSURE["honest_boundary"]
              and "TOPS" in DEVICE_2D_DISCLOSURE["honest_boundary"])

    if verbose:
        for nm, c, det in msgs:
            print(("  [PASS] " if c else "  [FAIL] ") + nm + (f" :: {det}" if det else ""))
        print(f"  —— device_2d 自检 {sum(1 for _, c, _ in msgs if c)}/{len(msgs)} ——")
    return ok


if __name__ == "__main__":
    import json
    print("=== device_2d 自检 ===")
    device_2d_self_check(verbose=True)
    print("=== 汇总（供案例卡/门禁核对的同源实测）===")
    print(json.dumps(device_2d_compute_rolloff_dibl_for_case(),
                     ensure_ascii=False, indent=1)[:1400])
