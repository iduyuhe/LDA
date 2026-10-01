# -*- coding: utf-8 -*-
"""ecore · E13 · **2D MOS 输运桥**（I–V / 亚阈值摆幅：补上 G-K 登记的最后一块）。

============================================================================
为什么存在（E13 · 电子计算征程）
----------------------------------------------------------------------------
E12 的诚实边界 **G-K** 写死：「2D MOS 为准平衡静电求解 ⇒ **不产 I-V**」，
`device_2d.short_channel_capability_report()` 的 `still_not_available` 第一条即
「**I–V 特性 / 亚阈值摆幅（从电流）⇒ E13 候选**」。

E13 补上能力本身（`lda_solver/mos_2d_transport.py`：Si-only SG 连续性 + Gummel）。
本模块是 ecore 侧的**桥**，做三件事：
  ① **量纲桥**（复用 E11-c `device_pde`，不复制第二份）；
  ② **判据 golden**：SS 的**教科书闭式** `(kT/q)ln10·(1+Cd/Cox)` ⟷ 长沟道数值 SS；
     以及 **SS ≥ 60 mV/dec 热极限**（物理定律锚）；
  ③ **交叉验证**：恒定电流法 V_th ⟷ E12 表面势法 V_th（两法**互不充当 ORACLE**）。

🔴 方法学独立性（判据为什么算数）
  golden_A = **热极限** `(kT/q)ln10 = 59.53 mV/dec`（室温）—— **物理定律锚**：
             扩散机制下 SS **不可能**低于它；数值解若低于 ⇒ 必是数值假象。
  golden_B = **教科书 SS 闭式**（耗尽近似 · 含体效应 `Cd/Cox`）—— 科学原理层公共品。
  cand     = 2D 漂移扩散数值解（`is_oracle=False`）。
  ⇒ 判据 = **长沟道数值 SS 收敛到闭式 golden_B**（不是收敛到 60 —— 60 是**硬下限**）。
  V_th 双法（恒流法 ⟷ 表面势法）为**内部交叉**，两法均 `is_oracle=False`。

🔴 honest 边界
  · 漂移扩散框架 ⇒ 不含量子修正 / 速度饱和 / 隧穿 / 弹道输运；
    **深亚阈值 SS 不受影响**，但 **I_on 偏高、I_off 偏低**。
  · **迁移率为常数** ⇒ `I_on` 绝对值**不可当器件性能**，只作相对趋势与 SS 判据。
  · 无 LDD / halo / 应变 / 栅重叠；参数为公开典型量级占位（**非 PDK**）。
  · 2D 仿真 = **每单位宽度电流**（A/m）；`I_ref` / `V_dd` 为公开惯例口径。
  · 不报 TOPS / TOPS-W / fJ/op。**EAR 744.23**（成熟节点 / 非先进用途）。
  · 依赖 scipy ⇒ 本模块用**函数内惰性导入**（无 scipy 环境仍可 import 本模块）。
"""
from __future__ import annotations

from typing import Dict, List, Optional

try:                                                    # 包内导入
    from .device_pde import NM_TO_M
except ImportError:                                     # 脚本直跑自检
    from lda_l2.ecore.device_pde import NM_TO_M  # type: ignore

# ---- 默认量（公开惯例 · 与内核同源）----
LG_NM_DEFAULT = 100.0
VG_LO_DEFAULT = -0.6
VG_HI_DEFAULT = 1.0
VG_N_DEFAULT = 21
V_D_LINEAR = 0.05
V_D_SAT = 1.0
SS_THERMAL_LIMIT_MV_DEC = 60.0
#: 默认栅长扫描（长沟道 → 短沟道；用于 G2/G3）
SS_LS_NM = (1000.0, 250.0, 100.0, 65.0)


def _mt():
    """惰性导入 2D MOS 输运内核（依赖 scipy ⇒ 不可放模块级）。"""
    from lda_solver import mos_2d_transport as MT
    return MT


def _m2():
    from lda_solver import mos_2d as M2
    return M2


def default_vg_list(vg_lo: float = VG_LO_DEFAULT, vg_hi: float = VG_HI_DEFAULT,
                    n: int = VG_N_DEFAULT) -> List[float]:
    """默认 V_g 扫描（**含负 V_g** ⇒ 一定能扫到深亚阈值区）。

    🔴 血案：若只从 `V_g = 0` 起扫，深亚阈值区根本进不去 —— 实测 0.1 µm 器件
    在 `V_g = 0` 处已有 1.5e-3 A/m，SS 拟合窗口内一个点都不落（`SS = nan`）。
    亚阈值摆幅是**从深亚阈值区**定义的量，扫描必须覆盖 `V_g < V_th`。
    """
    k = max(int(n) - 1, 1)
    return [round(float(vg_lo) + (float(vg_hi) - float(vg_lo)) * i / k, 6)
            for i in range(k + 1)]


def _dx_for(lg_nm: float) -> float:
    """按栅长选网格（与 device_2d 同口径）。"""
    lg = float(lg_nm)
    return (10.0 if lg >= 400.0 else (5.0 if lg >= 200.0 else 2.5)) * NM_TO_M


# ---------------------------------------------------------------------------
# ① 转移特性 + 三个提取量（一次算好，多处引用）
# ---------------------------------------------------------------------------
def transfer_curve(lg_nm: float = LG_NM_DEFAULT, v_d: float = V_D_LINEAR,
                   vg_list: Optional[List[float]] = None,
                   dx_target_nm: Optional[float] = None,
                   device: Optional[dict] = None, **kw) -> Dict:
    """跑一条转移特性 I_d(V_g) 并提取 SS / V_th(恒流法) / I_on·I_off。"""
    mt = _mt()
    m2 = _m2()
    if device is None:
        dxn = dx_target_nm if dx_target_nm is not None else (_dx_for(lg_nm) / NM_TO_M)
        device = m2.mos2d_device(Lg=float(lg_nm) * NM_TO_M,
                                 dx_target=float(dxn) * NM_TO_M)
    vgs = vg_list if vg_list is not None else default_vg_list()
    sw = mt.sweep_id_vg(Vd=float(v_d), Vg_list=vgs, device=device, **kw)
    pts = sw["points"]
    ss = mt.subthreshold_swing(pts)
    vt = mt.vth_constant_current(pts, lg_m=float(lg_nm) * NM_TO_M)
    io = mt.i_on_off(pts)
    cmax = max((p["conservation_rel"] for p in pts), default=float("nan"))
    nconv = sum(1 for p in pts if p["converged"])
    return {"Lg_nm": float(lg_nm), "V_d": float(v_d), "points": pts,
            "SS_mv_dec": ss["SS_mv_dec"], "SS_n_points": ss["n_points"],
            "SS_window": ss["window_a_per_m"], "SS_method": ss["method"],
            "SS_below_thermal_limit": bool(ss.get("abnormal_below_thermal_limit")),
            "V_th_cc_v": vt["V_th_cc_v"], "i_ref_a_per_m": vt["i_ref_a_per_m"],
            "I_on_a_per_m": io["I_on"], "I_off_a_per_m": io["I_off"],
            "I_on_off_ratio": io["ratio"],
            "conservation_max_rel": float(cmax),
            "all_converged": bool(nconv == len(pts)), "n_converged": int(nconv),
            "n_points": len(pts), "is_oracle": False}


# ---------------------------------------------------------------------------
# ② 判据 G1：SS ≥ 60 mV/dec（物理定律锚）
# ---------------------------------------------------------------------------
def ss_thermal_limit_report(lg_nm: float = LG_NM_DEFAULT,
                            curve: Optional[Dict] = None, **kw) -> Dict:
    """**G1**：数值 SS 不得低于室温热极限 `(kT/q)·ln10`。

    这是**物理定律锚**（扩散机制的硬下限）⇒ 低于它必是数值假象（伪负电容 /
    拟合窗口跨到了强反型段）。比任何"和文献比"都强，因为它是**不等式**而非等式。
    """
    c = curve if curve is not None else transfer_curve(lg_nm=lg_nm, **kw)
    ideal = _mt().ss_closed_form()["SS_ideal_mv_dec"]
    ss = c["SS_mv_dec"]
    return {"SS_mv_dec": ss, "thermal_limit_mv_dec": float(ideal),
            "margin_mv_dec": float(ss - ideal) if ss == ss else float("nan"),
            "violates_thermal_limit": bool(ss == ss and ss < ideal),
            "n_points": c["SS_n_points"], "Lg_nm": c["Lg_nm"],
            "is_oracle": False}


# ---------------------------------------------------------------------------
# ③ 判据 G2：长沟道 SS ⟷ 教科书闭式（golden）
# ---------------------------------------------------------------------------
def cross_check_ss_closed_form(lg_nm: float = 1000.0,
                               curve: Optional[Dict] = None,
                               tol_rel: float = 0.10, **kw) -> Dict:
    """**G2**：长沟道数值 SS 收敛到**教科书闭式**（含体效应 `Cd/Cox`）。

    🔴 收敛目标是**闭式**，**不是 60**：`60 mV/dec` 只在 `Cd → 0`（FD-SOI / 双栅）
    时达到；体硅器件因体效应收敛到 `60·(1+Cd/Cox)` 的平台（本例 **≈ 66.4**）。
    把 60 当渐近目标会得出"永远不达标"的错误结论 —— 这是本段最重要的一条物理澄清。
    """
    mt = _mt()
    c = curve if curve is not None else transfer_curve(lg_nm=lg_nm, **kw)
    g = mt.ss_closed_form()
    ss = c["SS_mv_dec"]
    rel = abs(ss - g["SS_mv_dec"]) / g["SS_mv_dec"] if ss == ss else float("inf")
    return {"Lg_nm": c["Lg_nm"], "SS_2d_mv_dec": ss,
            "SS_closed_mv_dec": g["SS_mv_dec"],
            "SS_ideal_mv_dec": g["SS_ideal_mv_dec"],
            "Cd_over_Cox": g["Cd_over_Cox"],
            "rel_err": float(rel), "tol_rel": float(tol_rel),
            "passes": bool(rel < tol_rel),
            "golden_source": "lda_solver.mos_2d_transport.ss_closed_form",
            "is_oracle": False}


# ---------------------------------------------------------------------------
# ④ 判据 G3：栅长趋势（长沟道 SS ↓ 趋近平台；短沟道退化）
# ---------------------------------------------------------------------------
def ss_vs_length_report(Ls_nm=SS_LS_NM, curves: Optional[Dict] = None,
                        **kw) -> Dict:
    """**G3**：`L ↓ ⇒ SS ↑`（短沟道静电控制退化）且 `L ↑ ⇒ SS ↓` 单调趋近闭式平台。

    与 E12 的 roll-off / DIBL **同物理、同方向** ⇒ 两条**独立**路径互相印证。
    """
    mt = _mt()
    dev_fn = _m2().mos2d_device
    pts = []
    for L in Ls_nm:
        c = (curves or {}).get(float(L))
        if c is None:
            dev = dev_fn(Lg=float(L) * NM_TO_M, dx_target=_dx_for(L))
            c = transfer_curve(lg_nm=float(L), device=dev, **kw)
        pts.append({"Lg_nm": float(L), "SS_mv_dec": c["SS_mv_dec"],
                    "V_th_cc_v": c["V_th_cc_v"], "I_off_a_per_m": c["I_off_a_per_m"],
                    "n_SS_points": c["SS_n_points"]})
    # 按 L **升序**检查：短沟道 SS 更大 ⇒ SS 随 L 单调**非增**
    #   🔴 语义别写反：判据是「L↓ ⇒ SS↑」，等价于「按 L 升序读，SS 单调**递减**」。
    asc = sorted(pts, key=lambda p: p["Lg_nm"])
    mono = all((asc[i]["SS_mv_dec"] <= asc[i - 1]["SS_mv_dec"] + 1e-9)
               for i in range(1, len(asc)) if asc[i]["SS_mv_dec"] == asc[i]["SS_mv_dec"])
    return {"points": pts, "monotone_long_to_short": bool(mono),
            "SS_closed_platform_mv_dec": float(mt.ss_closed_form()["SS_mv_dec"]),
            "is_oracle": False}


# ---------------------------------------------------------------------------
# ⑤ 判据 G4：电流守恒（源 ≡ 漏）
# ---------------------------------------------------------------------------
def current_conservation_report(curve: Dict,
                               i_floor_a_per_m: float = 1.0e-3,
                               tol_rel: float = 1.0e-3) -> Dict:
    """**G4**：源端电流 ≡ 漏端电流（`∇·J=0` 的直接推论）。

    🔴 **必须带绝对下限**：深亚阈值电流可到 1e-10 A/m，此时相对差被数值噪声主导
    （实测 rel 可达 1.35 > 1，但绝对差仅 1e-9 A/m）⇒ 只在 `|I_d| ≥ i_floor`
    的点检查相对守恒。**相对判据在分母趋零时失效** —— 这是本轮的一条通则。
    """
    checked = []
    worst = 0.0
    worst_vg = float("nan")
    for p in curve["points"]:
        if abs(p["I_d"]) >= i_floor_a_per_m:
            checked.append(p)
            if p["conservation_rel"] > worst:
                worst = float(p["conservation_rel"])
                worst_vg = float(p["Vg"])
    return {"n_checked": len(checked), "n_total": curve["n_points"],
            "i_floor_a_per_m": float(i_floor_a_per_m),
            "worst_rel": float(worst), "worst_Vg": float(worst_vg),
            "tol_rel": float(tol_rel),
            "passes": bool(len(checked) > 0 and worst < tol_rel),
            "is_oracle": False}


# ---------------------------------------------------------------------------
# ⑥ 判据 G5：输出特性单调（低 V_d 线性 → 高 V_d 增）
# ---------------------------------------------------------------------------
def id_vd_report(lg_nm: float = 300.0, v_ds=(0.05, 0.2, 0.5, 1.0),
                 v_g: float = 1.0, **kw) -> Dict:
    """**G5**：固定 `V_g`，`I_d` 随 `V_d` 单调增（MOS 输出特性）。"""
    mt = _mt()
    m2 = _m2()
    dev = m2.mos2d_device(Lg=float(lg_nm) * NM_TO_M, dx_target=_dx_for(lg_nm))
    pts = []
    warm = None
    for vd in v_ds:
        s = mt.solve_mos2d_iv_point(float(v_g), Vd=float(vd), device=dev,
                                    warm=warm, return_fields=True, **kw)
        warm = s["psi"].flatten()
        pts.append({"V_d": float(vd), "I_d_a_per_m": abs(s["I_d"]),
                    "converged": bool(s["converged"])})
    mono = all(pts[i]["I_d_a_per_m"] > pts[i - 1]["I_d_a_per_m"] - 1e-12
               for i in range(1, len(pts)))
    return {"points": pts, "monotone": bool(mono), "V_g": float(v_g),
            "Lg_nm": float(lg_nm), "is_oracle": False}


# ---------------------------------------------------------------------------
# ⑦ 判据 G6：V_th 双法交叉（恒流法 ⟷ E12 表面势法）
# ---------------------------------------------------------------------------
def vth_cc_vs_surface_potential(lg_nm: float = LG_NM_DEFAULT,
                                curve: Optional[Dict] = None,
                                tol_rel: float = 0.40, **kw) -> Dict:
    """**G6**：恒定电流法 V_th（E13 · 从 I–V）⟷ 表面势法 V_th（E12 · 从 ψ_s）。

    两法**互相独立**（一个用电流判据、一个用静电表面势判据）⇒ 是交叉验证而非自证。
    🔴 两法**均 `is_oracle=False`** —— 互不充当 ORACLE；判据只要求**同量级**
    （口径不同 ⇒ 存在系统性差异，实测约 80 mV / 24 %，已在披露中说明）。
    """
    c = curve if curve is not None else transfer_curve(lg_nm=lg_nm, **kw)
    from lda_solver import mos_2d as M2
    r = M2.extract_vth_2d(Lg=float(lg_nm) * NM_TO_M, Vd=V_D_LINEAR,
                          mode="majority", dx_target=_dx_for(lg_nm))
    v_cc = c["V_th_cc_v"]
    v_sp = float(r["V_th"])
    rel = abs(v_cc - v_sp) / abs(v_sp) if v_sp else float("inf")
    return {"Lg_nm": float(lg_nm), "V_th_cc_v": v_cc, "V_th_surface_potential_v": v_sp,
            "abs_diff_mv": float((v_cc - v_sp) * 1e3), "rel_err": float(rel),
            "tol_rel": float(tol_rel), "passes": bool(rel < tol_rel),
            "note": "两法口径不同（恒流法在弱反型 I_ref；表面势法在 ψ_s=φ_F 强反型起始）"
                    "⇒ 存在系统性差异；判据只要求同量级",
            "is_oracle": False}


# ---------------------------------------------------------------------------
# ⑧ 能力闭合表（E12 的 still_not_available → E13 闭合）
# ---------------------------------------------------------------------------
def transport_capability_closure() -> Dict:
    """E12「算不了」→ E13「算得了」的**能力闭合表**（对外可直接引用）。"""
    return {
        "closed_by_e13": [
            {"item": "I–V 特性（I_d(V_g, V_d)）",
             "e12_status": "不含输运 ⇒ 不产 I-V（G-K 登记为 still_not_available）",
             "e13_status": "稳态漂移扩散（SG 离散 + Gummel）⇒ 转移/输出特性**可从数值解提取**"},
            {"item": "亚阈值摆幅 SS",
             "e12_status": "无（需从电流提取）",
             "e13_status": "从 I–V 提取 · 满足 **SS ≥ 60 mV/dec 热极限**，"
                           "长沟道收敛到**教科书闭式** `(kT/q)ln10·(1+Cd/Cox)`"},
            {"item": "恒定电流法 V_th",
             "e12_status": "只有表面势法（ψ_s = φ_F）",
             "e13_status": "恒流法可用 ⇒ 与表面势法**交叉验证**（两法互不充当 ORACLE）"},
            {"item": "I_on / I_off",
             "e12_status": "无",
             "e13_status": "可提取（**口径为每单位宽度电流**，非器件性能）"},
        ],
        "still_not_available": [
            {"item": "量子修正（反型层电荷重心 / 体量子化）· 速度饱和 · 带间/栅隧穿 · 弹道输运",
             "why": "本内核仍是**漂移扩散（DD）框架** ⇒ 不含上述机制；"
                    "深亚阈值 SS 不受影响，但 **I_on 偏高、I_off 偏低**",
             "candidate": "超出 T1 范围（需 NEGF / 量子修正 DD）"},
            {"item": "真实迁移率（场依赖退化 / 表面散射 / 库仑散射）",
             "why": "本内核迁移率为**常数**（文献典型值）⇒ `I_on` 绝对值不可当器件性能",
             "candidate": "需经 CallibrationWindow（公开量级不可外推为 PDK）"},
            {"item": "工艺角 / PDK 标定 / 硅验证",
             "why": "**T2 永久锁**（需 NDA + 流片）——属商业路径，非求解器精度问题",
             "candidate": "不在平台红线内"},
            {"item": "LDD / halo / 应变 / 栅重叠 / 温度扫描 / AC·瞬态",
             "why": "结构为教科书突变结 + 2 nm 平滑；本段固定 300 K、只做 DC",
             "candidate": "可选扩展"},
        ],
        "is_oracle": False,
    }


DEVICE_TRANSPORT_DISCLOSURE: dict = {
    "route": "电子计算征程 E13 · 2D MOS 漂移扩散输运（I–V / 亚阈值摆幅）",
    "capability": "稳态漂移扩散（Gummel：非线性泊松 ⟷ SG 连续性）+ Si-only 掩码连续性"
                  "+ 接触准费米势 BC + 终端电流（SG 守恒截面）",
    "golden_A": "**SS 热极限** `(kT/q)·ln10 = 59.53 mV/dec`（室温）—— 物理定律锚（不等式）",
    "golden_B": "**教科书 SS 闭式** `(kT/q)ln10·(1+Cd/Cox)`（耗尽近似 · 含体效应）",
    "candidate": "2D 漂移扩散数值解（`lda_solver/mos_2d_transport.py`）· is_oracle=False",
    "cross_check": "恒定电流法 V_th ⟷ E12 表面势法 V_th（两法均 is_oracle=False，互不充当 ORACLE）",
    "honest_boundary": "漂移扩散框架 ⇒ 不含量子修正/速度饱和/隧穿/弹道；迁移率为常数 "
                       "⇒ I_on 绝对值不可当器件性能；**深亚阈值 SS 不受影响**，但 I_on 偏高、"
                       "I_off 偏低；无 LDD/halo/应变/栅重叠；参数为公开典型量级占位（非 PDK）；"
                       "2D 仿真 = 每单位宽度电流（A/m）；不报 TOPS/TOPS-W/fJ/op",
    "redline": "红线 = 分层口径（器件级 T1 已解锁 · T2 工艺真值/工艺角/流片永久锁）；"
               "T1 输出永不作 ORACLE；LLM 不进判决路径；EAR 744.23 成熟节点用途",
}


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def device_transport_self_check(verbose: bool = True) -> bool:
    msgs = []

    def chk(name, cond, det=""):
        msgs.append((name, bool(cond), det))
        return bool(cond)

    ok = True

    # ① 内核自检 6/6（掩码/接触/平衡/守恒/闭式/单调）
    ok &= chk("① 内核自检 mos_2d_transport.run_selfchecks() 6/6",
              _mt().run_selfchecks(verbose=False) is True)

    # ② 判据 G1：SS ≥ 热极限
    g1 = ss_thermal_limit_report()
    ok &= chk("② G1 SS ≥ 60 mV/dec 热极限（物理定律锚）",
              (not g1["violates_thermal_limit"]) and g1["SS_mv_dec"] == g1["SS_mv_dec"],
              "SS=%.2f · 极限=%.2f mV/dec" % (g1["SS_mv_dec"], g1["thermal_limit_mv_dec"]))

    # ③ 判据 G2：长沟道 ⟷ 教科书闭式
    g2 = cross_check_ss_closed_form()
    ok &= chk("③ G2 长沟道 SS ⟷ 教科书闭式（含体效应 · rel < 10%）",
              g2["passes"], "2D=%.2f ⟷ 闭式=%.2f（rel=%.2f%% · Cd/Cox=%.4f）"
              % (g2["SS_2d_mv_dec"], g2["SS_closed_mv_dec"], g2["rel_err"] * 100,
                 g2["Cd_over_Cox"]))

    # ④ 判据 G4：电流守恒（带绝对下限）
    c = transfer_curve()
    g4 = current_conservation_report(c)
    ok &= chk("④ G4 电流守恒（源≡漏 · 大电流点 rel < 1e-3）",
              g4["passes"], "检查 %d/%d 点 · worst=%.2e @Vg=%.2f"
              % (g4["n_checked"], g4["n_total"], g4["worst_rel"], g4["worst_Vg"]))

    # ⑤ 判据 G5：输出特性单调
    g5 = id_vd_report()
    ok &= chk("⑤ G5 输出特性 I_d 随 V_d 单调增", g5["monotone"],
              " · ".join("Vd=%.2f→%.3e" % (p["V_d"], p["I_d_a_per_m"])
                         for p in g5["points"]))

    # ⑥ 判据 G6：V_th 双法同量级
    g6 = vth_cc_vs_surface_potential(curve=c)
    ok &= chk("⑥ G6 V_th 双法同量级（恒流法 ⟷ E12 表面势法 · rel < 40%）",
              g6["passes"], "CC=%.4f · ψ_s=%.4f V（差 %.1f mV · %.1f%%）"
              % (g6["V_th_cc_v"], g6["V_th_surface_potential_v"], g6["abs_diff_mv"],
                 g6["rel_err"] * 100))

    # ⑦ 能力闭合表：闭合 4 项 · 仍不可用 4 项（含 T2）
    cap = transport_capability_closure()
    ok &= chk("⑦ 能力闭合表：闭合 4 项 · 仍不可用 4 项（含 T2 永久锁 + DD 框架边界）",
              len(cap["closed_by_e13"]) == 4 and len(cap["still_not_available"]) == 4
              and any("T2" in c["why"] for c in cap["still_not_available"]))

    # ⑧ 诚实护栏：披露必须显式声明 DD 边界与不报 TOPS
    ok &= chk("⑧ 披露显式声明「漂移扩散框架 ⇒ 不含量子修正/隧穿」且不报 TOPS",
              "漂移扩散" in DEVICE_TRANSPORT_DISCLOSURE["honest_boundary"]
              and "TOPS" in DEVICE_TRANSPORT_DISCLOSURE["honest_boundary"])

    if verbose:
        for nm, cc, det in msgs:
            print(("  [PASS] " if cc else "  [FAIL] ") + nm + ((" :: " + det) if det else ""))
        print("  —— device_transport 自检 %d/%d ——"
              % (sum(1 for _, cc, _ in msgs if cc), len(msgs)))
    return ok


if __name__ == "__main__":
    import json
    print("=== device_transport 自检 ===")
    device_transport_self_check(verbose=True)
    print("=== 能力闭合表 ===")
    print(json.dumps(transport_capability_closure(), ensure_ascii=False, indent=1)[:1200])
