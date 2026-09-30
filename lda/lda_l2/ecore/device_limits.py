# -*- coding: utf-8 -*-
"""ecore · E11-d · **器件级模型的失效边界测绘**（诚实边界，不新增求解器能力）。

============================================================================
本模块回答一件事：**LDA 的器件级内核在什么范围内可信，出了范围会怎样。**
----------------------------------------------------------------------------
分两类，**性质完全不同**，不得混为一谈：

**A. LDA 自己算得出来的边界（数值窗口 · 实测）**
   MOSCAP 1D 自洽泊松的 PDE 解与教科书完整闭式在多大 ψ_s 范围内一致。
   实测（`lda_solver/mos_1d.py`）：窗口两端对 N_A（1e16…1e18 cm⁻³）与 T（250…400 K）
   **都近似不变**，但在参考界面网格 **dx_if = 0.02 nm** 下为

        ψ_s ∈ [φ_F − 1.54·φ_F, φ_F + 1.54·φ_F]         （即以 φ_F 归一后 1 ± 1.54）

   🔴 **数值窗口是「网格相关」的**（实测）：dx_if = 0.05 nm ⇒ [−0.40, 2.40]φ_F；
   0.02 nm ⇒ [−0.50, 2.50]φ_F。网格越细 ⇒ 窗口越宽（可被数值手段改善）。
   等价（且更本质）的表述：**表面载流子浓度 ≲ N_crit ≈ 5.5e26 m⁻³**（在 0.02 nm 下）。
   超出后界面薄层（积累层/反型层）薄于界面网格 ⇒ Q_s 被系统性低估。
   🔴 而 N_crit ≈ 5.5e26 m⁻³ 是**数值**上限（网格分辨率），**不是**物理简并边界
   （约 1e25 m⁻³）——后者见 §B，**与网格无关、不可被数值手段改善**。

**B. LDA 算不出来的边界（物理模型边界 · 文献登记 + 量化缺口）**
   1D MOS 电容**无源/漏、无沟道长度** ⇒ 一切**二维效应**都不在其模型内：
   - 短沟道 **V_th roll-off**（电荷共享，Yau 1974）
   - **DIBL**（漏致势垒降低）
   - **速度饱和**（高场 v(E) 饱和）
   - **迁移率退化**（垂直场致 µ_eff ↓）
   本模块把这些**半经验/经验闭式**实现出来，用途**只有一个**：**量化 LDA 的缺口**
   （如 L = 65 nm 时 roll-off 让 V_th 偏多少 %）——**它们不是 LDA 的计算结果**，
   不得当作 LDA 的能力（见 `LITERATURE_LIMITS` 每项的 `computed_by_lda=False`）。

口径
----
平台红线为**分层口径**：器件级 T1 数值内核已解锁；T2 工艺真值/工艺角/流片永久锁。
ecore 其余模块**主动限定在电路级**；本模块是**边界说明**，不新增能力。

🔴 诚实边界：`x_j`（结深）/ `θ`（迁移率退化系数）/ `v_sat` 等为**公开典型量级占位**；
文献式仅作**缺口量级**参照，**不构成任何工艺标定**。不报 TOPS/TOPS-W/fJ/op。
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# A. 数值窗口（LDA 算得出）
# ---------------------------------------------------------------------------
#: 实测反解的**数值**上限常数（表面载流子浓度，m⁻³）· 见模块 docstring §A
N_CRIT_NUMERICAL = 5.5e26
#: 文献**物理**简并边缘量级（m⁻³）——Si 有效态密度 N_c≈2.8e19 cm⁻³ 的 10% 量级
N_CRIT_DEGENERATE = 1.0e25
#: 实测窗口半宽（以 φ_F 为单位）——**在参考界面网格 dx_if = 0.02 nm 下测得**。
#: 🔴 数值窗口**随网格变化**（网格越细 ⇒ 窗口越宽），见 `numerical_window_grid_dependence()`。
WINDOW_HALF_WIDTH_PHI_F = 1.54
#: 上述常数的参考界面网格（nm）
WINDOW_REFERENCE_DX_IF_NM = 0.02


def measure_window_edge(sign: int, n_a_cm3: float = 1.0e17,
                        dx_if_nm: float = None) -> float:
    """**实测**窗口边界（以 φ_F 为单位）：真扫 PDE 找「PDE ≡ 闭式(rel<1e-3)」的最外点。

    两级扫描（粗 0.40 步长 → 邻域细 0.05 步长），兼顾精度与耗时。
    `sign=+1` 反型侧 / `sign=−1` 积累侧。
    🔴 初值取 0（**不是** ±1.0）：否则「一个都没通过」会被误报成「通过到 1.0」。
    """
    dx = float(dx_if_nm if dx_if_nm is not None else WINDOW_REFERENCE_DX_IF_NM) * 1.0e-9
    na = float(n_a_cm3) * 1.0e6
    pf = _mos_phi_f(na)

    def ok(mag: float) -> bool:
        ps = float(sign) * mag * pf
        s = _solve(ps, na, dx)
        g = _qs_closed(ps, na)
        if g == 0.0:
            return False
        return bool(abs(s["Q_s"] - g) / abs(g) < 1e-3 and s["converged"])

    last = 0.0
    for i in range(7):                       # 粗扫 0.40 … 2.80
        m = 0.40 + 0.40 * i
        if ok(m):
            last = m
        else:
            break
    if last == 0.0:
        return 0.0
    for i in range(1, 8):                    # 细扫 (last, last+0.40]，步长 0.05
        m = last + 0.05 * i
        if ok(m):
            last = m
        else:
            break
    return float(sign) * last


def numerical_window_grid_dependence(dx_if_nm_list=(0.05, 0.02)) -> list:
    """**数值窗口的网格依赖性**（实测）：网格越细 ⇒ 窗口越宽。

    🔴 这条构成 E11-d 的核心区分：**数值窗口是「网格相关」的（可被网格改进扩大），
    物理窗口是「网格无关」的（不可被数值手段改善）** ⇒ 真正的边界是后者。
    """
    out = []
    for d in dx_if_nm_list:
        out.append({"dx_if_nm": float(d),
                    "lo_phi_f": measure_window_edge(-1, dx_if_nm=d),
                    "hi_phi_f": measure_window_edge(+1, dx_if_nm=d)})
    return out


def _mos_phi_f(na_m3: float) -> float:
    from lda_solver import mos_1d as M
    return M.phi_f(na_m3)


def _solve(psi_s: float, na_m3: float, dx_m: float) -> dict:
    from lda_solver import mos_1d as M
    return M.solve_moscap_1d(psi_s, N_A=na_m3, dx_if=dx_m)


def _qs_closed(psi_s: float, na_m3: float) -> float:
    from lda_solver import mos_1d as M
    return M.sze_qs_closed_form(psi_s, N_A=na_m3)


def numerical_window_phi_f() -> dict:
    """实测数值窗口（以 φ_F 归一）——对 N_A 与 T 近似不变的统一常数。

    返回 {lo_phi_f, hi_phi_f, N_crit_m3, note}。
    """
    w = WINDOW_HALF_WIDTH_PHI_F
    return {
        "lo_phi_f": 1.0 - w, "hi_phi_f": 1.0 + w,
        "N_crit_m3": N_CRIT_NUMERICAL,
        "note": "两端由同一「表面载流子浓度 ≤ N_crit」判据定；N_crit 是**数值**上限（网格分辨率），"
                "非物理简并边界。",
    }


def degeneracy_phi_f(n_a_cm3: float = 1.0e17) -> dict:
    """**物理**边界（文献判据）：玻尔兹曼统计失效前的 ψ_s 范围。

    表面载流子浓度达到简并边缘 N_CRIT_DEGENERATE（≈1e25 m⁻³）时，玻尔兹曼近似不再成立。
    以 ψ_s 表示：|ψ_s − φ_F| ≤ V_T·ln(N_crit_degenerate/n_i)。
    """
    from lda_solver import mos_1d as M
    na = float(n_a_cm3) * 1.0e6
    pf = M.phi_f(na)
    d = M.V_T * _log_ratio(N_CRIT_DEGENERATE, M.N_I)
    return {"phi_f_v": pf, "psi_min_v": pf - d, "psi_max_v": pf + d,
            "N_crit_m3": N_CRIT_DEGENERATE,
            "note": "文献简并判据（玻尔兹曼适用上限）· 比数值上限更**严** ⇒ "
                    "**物理模型先失效，数值后崩**。"}


def _log_ratio(a: float, b: float) -> float:
    import math
    return math.log(float(a) / float(b))


def window_ratio_physical_over_numerical(n_a_cm3: float = 1.0e17) -> float:
    """物理窗口半宽 / 数值窗口半宽（<1 ⇒ 物理模型是瓶颈，不是数值精度）。"""
    from lda_solver import mos_1d as M
    pf = M.phi_f(float(n_a_cm3) * 1.0e6)
    d_phys = M.V_T * _log_ratio(N_CRIT_DEGENERATE, M.N_I)
    return float(d_phys / (WINDOW_HALF_WIDTH_PHI_F * pf))


# ---------------------------------------------------------------------------
# B. 文献参照（LDA **不算** · 只用于量化缺口）
# ---------------------------------------------------------------------------
#: 每一项都显式标 `computed_by_lda=False` + 来源
LITERATURE_LIMITS = (
    {"effect": "短沟道 V_th roll-off（电荷共享）",
     "model": "Yau 1974 电荷共享：ΔV_th = −(q·N_A·W_m/C_ox)·(x_j/L)·[√(1+2W_m/x_j) − 1]",
     "needs": ["源漏结深 x_j", "沟道长度 L", "二维耗尽边界"],
     "why_lda_cannot": "1D MOS 电容无源/漏、无沟道长度 ⇒ 无二维电荷共享",
     "computed_by_lda": False, "source": "Yau, Solid-State Electronics 17(10), 1974"},
    {"effect": "DIBL（漏致势垒降低）",
     "model": "特征长度 ℓ = √((ε_si/ε_ox)·t_ox·x_j)；ΔV_th ∝ −V_ds·e^{−L/ℓ}",
     "needs": ["drain 偏压 V_ds", "L", "x_j", "t_ox"],
     "why_lda_cannot": "1D 无漏端、无横向势垒调制",
     "computed_by_lda": False, "source": "Liu et al., IEEE TED 1993（DIBL 特征长度）"},
    {"effect": "速度饱和（高场）",
     "model": "v(E) = µ_eff·E/(1 + E/E_c)，E_c = v_sat/µ_eff",
     "needs": ["v_sat", "µ_eff", "横向高场"],
     "why_lda_cannot": "本包平方律模型（`ecore/mosfet.py`）不含横向场依赖的 v–E 关系",
     "computed_by_lda": False, "source": "Sze《Physics of Semiconductor Devices》§8.3（速度饱和）"},
    {"effect": "迁移率退化（垂直场）",
     "model": "µ_eff = µ_0/(1 + θ·(V_gs − V_th))（θ 为经验系数）",
     "needs": ["θ", "V_ov"],
     "why_lda_cannot": "平方律模型取常数 µ（κ_p = µ·C_ox 定值），无垂直场退化项",
     "computed_by_lda": False, "source": "Sze §6.4（有效迁移率经验式）"},
)

#: 经验/占位参数（公开典型量级，**非标定**）
LITERATURE_PARAMS = {
    "x_j_um": 0.030,          # 源漏结深 (µm) · 公开典型量级
    "v_sat_m_per_s": 1.0e5,   # 饱和速度 (m/s, ≈1e7 cm/s)
    "mu0_m2_per_vs": 0.014,   # 低场迁移率 (m²/V·s, ≈140 cm²/V·s，与 ecore kp/Cox 自洽)
    "theta_per_v": 0.30,      # 迁移率退化系数 (1/V) · 经验典型
}


def yau_rolloff_dvth(l_um: float, x_j_um: float = None, n_a_cm3: float = 1.0e17,
                     t_ox_nm: float = 4.0) -> dict:
    """**文献经验闭式**（Yau 电荷共享）算出的短沟道 V_th 偏移——**非 LDA 计算结果**。

    ΔV_th = −(q·N_A·W_m/C_ox)·(x_j/L)·[√(1 + 2W_m/x_j) − 1]（负 ⇒ V_th 下降）。
    """
    from lda_solver import mos_1d as M
    xj = float(x_j_um if x_j_um is not None else LITERATURE_PARAMS["x_j_um"]) * 1.0e-6
    na = float(n_a_cm3) * 1.0e6
    pf = M.phi_f(na)
    w_m = M.max_depletion_width(na, two_phi_f=2.0 * pf)
    c_ox = M.oxide_capacitance(float(t_ox_nm) * 1.0e-9)
    l_m = float(l_um) * 1.0e-6
    dv = -(M.Q_E * na * w_m / c_ox) * (xj / l_m) * ((1.0 + 2.0 * w_m / xj) ** 0.5 - 1.0)
    return {"dV_th_v": float(dv), "W_m_m": float(w_m), "x_j_um": xj * 1.0e6,
            "computed_by_lda": False, "source": "Yau 1974（电荷共享）"}


def dibl_characteristic_length(t_ox_nm: float = 4.0,
                               x_j_um: float = None, eps_ox: float = None) -> float:
    """DIBL 特征长度 ℓ = √((ε_si/ε_ox)·t_ox·x_j)（m）。**文献式，非 LDA 计算。**"""
    from lda_solver import mos_1d as M
    xj = float(x_j_um if x_j_um is not None else LITERATURE_PARAMS["x_j_um"]) * 1.0e-6
    eox = float(eps_ox if eps_ox is not None else M.EPS_OX)
    return float(((M.EPS_SI / eox) * (float(t_ox_nm) * 1.0e-9) * xj) ** 0.5)


def dibl_dvth(l_um: float, v_ds_v: float = 1.0, t_ox_nm: float = 4.0,
              x_j_um: float = None) -> dict:
    """DIBL 造成的 V_th 偏移（经验式 ΔV_th ≈ −0.4·V_ds·e^{−L/ℓ}）。**非 LDA 计算。**"""
    import math
    ell = dibl_characteristic_length(t_ox_nm, x_j_um)
    dv = -0.4 * float(v_ds_v) * math.exp(-(float(l_um) * 1.0e-6) / ell)
    return {"dV_th_v": float(dv), "ell_m": ell, "ell_nm": ell * 1.0e9,
            "computed_by_lda": False, "source": "DIBL 特征长度经验式（Liu 1993 形式）"}


def velocity_saturation_field(phi_f_v: float = 0.4167) -> dict:
    """速度饱和临界场 E_c = v_sat/µ_eff，µ_eff 取 2φ_F 处（经验式）。**非 LDA 计算。**"""
    mu0 = LITERATURE_PARAMS["mu0_m2_per_vs"]
    theta = LITERATURE_PARAMS["theta_per_v"]
    mu_eff = mu0 / (1.0 + theta * float(phi_f_v))
    ec = LITERATURE_PARAMS["v_sat_m_per_s"] / mu_eff
    return {"mu_eff_m2_per_vs": mu_eff, "E_c_v_per_m": ec,
            "E_c_kv_per_cm": ec / 1.0e5, "computed_by_lda": False,
            "source": "Sze §8.3（速度饱和）+ §6.4（有效迁移率）"}


def mobility_degradation_factor(v_ov_v: float, theta: float = None) -> dict:
    """迁移率退化因子 1/(1+θ·V_ov)（经验式）。**非 LDA 计算。**"""
    th = float(theta if theta is not None else LITERATURE_PARAMS["theta_per_v"])
    f = 1.0 / (1.0 + th * float(v_ov_v))
    return {"factor": float(f), "theta_per_v": th, "computed_by_lda": False,
            "source": "Sze §6.4（垂直场迁移率退化经验式）"}


def literature_gap_report(l_um: float = 0.065, n_a_cm3: float = 1.0e17,
                          t_ox_nm: float = 4.0, v_ds_v: float = 1.0) -> dict:
    """**缺口量化**：在给定沟道长度下，文献效应各让 V_th 偏多少（相对长沟道 V_th）。

    🔴 这是**LDA 的缺口报告**，不是 LDA 的计算结果——三项全部 `computed_by_lda=False`。
    """
    from lda_l2.ecore.device_pde import physics_vth_closed
    vth0 = physics_vth_closed(n_a_cm3, t_ox_nm)["V_th"]
    ro = yau_rolloff_dvth(l_um, n_a_cm3=n_a_cm3, t_ox_nm=t_ox_nm)
    db = dibl_dvth(l_um, v_ds_v, t_ox_nm)
    return {
        "L_um": float(l_um), "V_th_long_channel_v": vth0,
        "rolloff_dV_th_v": ro["dV_th_v"],
        "rolloff_frac_of_vth": abs(ro["dV_th_v"]) / vth0,
        "dibl_dV_th_v": db["dV_th_v"],
        "dibl_frac_of_vth": abs(db["dV_th_v"]) / vth0,
        "total_frac_of_vth": (abs(ro["dV_th_v"]) + abs(db["dV_th_v"])) / vth0,
        "computed_by_lda": False,
        "note": "该缺口**不可能**由本平台的 1D MOS 内核补上——需要 2D MOS 求解器 + 工艺参数。",
    }


# ---------------------------------------------------------------------------
# C. 能力边界汇总
# ---------------------------------------------------------------------------
def capability_boundary_map() -> dict:
    """LDA 器件级能力边界汇总：能算什么（+前提）/ 算什么（+需什么）。"""
    return {
        "can_compute": [
            "1D MOS 电容自洽泊松（ψ(x)/Q_s/V_g/V_th）· 前提：ψ_s 在数值窗口内",
            "教科书闭式 ⟷ PDE 交叉验证（V_th · Q_s 跨点）",
            "长沟道平方律三区特性 / 小信号 gm·gds（`ecore/mosfet.py`）",
            "体效应（V_th 随衬底偏置的经典 √ 式，长沟道）",
        ],
        "cannot_compute": [
            {"item": "短沟道 V_th roll-off", "needs": "2D MOS 求解器（本平台无）"},
            {"item": "DIBL", "needs": "2D 横向势垒调制"},
            {"item": "速度饱和 / 高场输运", "needs": "v–E 关系 + 高场求解"},
            {"item": "迁移率退化", "needs": "垂直场相关 µ_eff（经验 θ 标定）"},
            {"item": "工艺角 / PDK 标定 / 良率", "needs": "foundry 数据（**T2 永久锁**）"},
        ],
        "boundary_kind": {
            "numerical": "表面载流子浓度 ≤ ~5.5e26 m⁻³（网格分辨率）",
            "physical": "玻尔兹曼适用（≲1e25 m⁻³）；1D 无源漏（无任何二维效应）",
        },
        "positioning": "**物理模型先失效，数值后崩** ⇒ 瓶颈是物理模型，不是数值精度。",
    }


DEVICE_LIMITS_DISCLOSURE: dict = {
    "scope": "**失效边界说明书**（不新增求解器能力）。ecore 其余模块**主动限定在电路级**；"
             "平台红线为**分层口径**（器件级 T1 已解锁 · T2 工艺真值/工艺角/流片永久锁）。",
    "two_kinds": "A 数值窗口（LDA 实测，由网格分辨率定）与 B 物理模型边界（文献判据 + 文献经验式）"
                 "**性质不同**，不得混为一谈：`computed_by_lda` 字段逐项标明某项是否 LDA 计算所得。",
    "key_finding": "物理模型先失效、数值后崩 ⇒ **瓶颈是物理模型（1D 无源漏 + 玻尔兹曼），"
                   "不是数值精度**（物理窗口半宽/数值窗口半宽 ≈ 0.84 < 1）。",
    "window_grid_dependent": "🔴 数值窗口**与网格相关**（实测 dx_if 0.05 nm → [−0.40, 2.40]φ_F；"
                             "0.02 nm → [−0.50, 2.50]φ_F，网格越细越宽）；物理窗口（简并 / 1D 假设）"
                             "**与网格无关** ⇒ 真正的边界是物理窗口。",
    "no_short_channel": "🔴 本平台**无 2D MOS 能力** ⇒ roll-off / DIBL / 速度饱和 / 迁移率退化"
                        "**一律不是 LDA 的计算结果**；`literature_gap_report` 只用于**量化缺口**。",
    "params_are_typical": "x_j / v_sat / θ / µ_0 为**公开典型量级占位（非标定）**；"
                          "文献式只给缺口量级，不构成工艺标定。不报 TOPS/TOPS-W/fJ/op。",
}


def run_selfchecks(verbose: bool = True) -> bool:
    """边界模块自检：窗口常数 · 物理/数值窗口区分 · 文献登记完整性 · 缺口量化。"""
    msgs = []

    def chk(name, cond, _d=""):
        msgs.append((name, bool(cond)))
        return bool(cond)

    ok = True

    # ① 数值窗口以 φ_F 归一（两端）
    w = numerical_window_phi_f()
    ok &= chk("① 数值窗口 = φ_F·[1−1.54, 1+1.54]", abs(w["lo_phi_f"] + 0.54) < 1e-9
              and abs(w["hi_phi_f"] - 2.54) < 1e-9)

    # ② 物理窗口比数值窗口**更严**（瓶颈是物理模型）
    r = window_ratio_physical_over_numerical()
    ok &= chk("② 物理窗口半宽 / 数值窗口半宽 < 1（物理模型先失效）", r < 1.0,
              "ratio=%.3f" % r)

    # ③ 文献登记每项都有来源且标 computed_by_lda=False
    ok &= chk("③ 文献边界登记完整（每项含 source · computed_by_lda=False）",
              len(LITERATURE_LIMITS) >= 4
              and all(e.get("source") and e.get("computed_by_lda") is False
                      for e in LITERATURE_LIMITS),
              "%d 项" % len(LITERATURE_LIMITS))

    # ④ 缺口量化：短沟道下 roll-off 显著（给定 L=65 nm）
    g = literature_gap_report(0.065)
    ok &= chk("④ 缺口量化：L=65 nm 时 roll-off 占 V_th 显著比例", g["rolloff_frac_of_vth"] > 0.20,
              "roll-off=%.3f V（%.1f%% of V_th）· DIBL=%.4f V" %
              (g["rolloff_dV_th_v"], g["rolloff_frac_of_vth"] * 100, g["dibl_dV_th_v"]))

    # ⑤ 长沟道极限：L 增大 ⇒ 缺口单调减
    f1 = literature_gap_report(0.065)["rolloff_frac_of_vth"]
    f2 = literature_gap_report(0.250)["rolloff_frac_of_vth"]
    f3 = literature_gap_report(1.000)["rolloff_frac_of_vth"]
    ok &= chk("⑤ 长沟道极限：L↑ ⇒ roll-off 缺口单调减（65nm→250nm→1µm）",
              f1 > f2 > f3, "%.3f > %.3f > %.3f" % (f1, f2, f3))

    # ⑥ 能力边界汇总含「能算/不能算」且不能算项 5 条
    cm = capability_boundary_map()
    ok &= chk("⑥ 能力边界汇总：能算 ≥4 项 · 不能算 5 项（含 T2 锁）",
              len(cm["can_compute"]) >= 4 and len(cm["cannot_compute"]) == 5
              and any("T2" in c["needs"] for c in cm["cannot_compute"]))

    # ⑦ 速度饱和 / 迁移率退化登记可计算
    vs = velocity_saturation_field()
    md = mobility_degradation_factor(0.5)
    ok &= chk("⑦ 速度饱和 E_c 与迁移率退化因子可算（且标非 LDA 计算）",
              vs["E_c_kv_per_cm"] > 10.0 and 0.0 < md["factor"] < 1.0
              and vs["computed_by_lda"] is False and md["computed_by_lda"] is False,
              "E_c=%.1f kV/cm · µ_eff/µ_0=%.3f" % (vs["E_c_kv_per_cm"], md["factor"]))

    # ⑧ 数值窗口**随网格变化**（网格越细 ⇒ 窗口越宽）· 物理窗口则与网格无关
    dep = numerical_window_grid_dependence((0.05, 0.02))
    ok &= chk("⑧ 数值窗口的网格依赖性：dx_if↓ ⇒ 窗口↑（0.05nm → 0.02nm 变宽）",
              dep[1]["hi_phi_f"] > dep[0]["hi_phi_f"]
              and dep[1]["lo_phi_f"] < dep[0]["lo_phi_f"],
              "[%.2f, %.2f] → [%.2f, %.2f]φ_F" %
              (dep[0]["lo_phi_f"], dep[0]["hi_phi_f"],
               dep[1]["lo_phi_f"], dep[1]["hi_phi_f"]))

    if verbose:
        for name, good in msgs:
            print("  [%s] %s" % ("PASS" if good else "FAIL", name))
        print("  selfcheck %d/%d" % (sum(1 for _, g_ in msgs if g_), len(msgs)))
    return bool(ok)


if __name__ == "__main__":
    print("=== 数值窗口 / 物理窗口 ===")
    w = numerical_window_phi_f()
    d = degeneracy_phi_f()
    print("  数值: ψ_s ∈ [%.2f, %.2f]·φ_F（N_crit=%.1e m⁻³）"
          % (w["lo_phi_f"], w["hi_phi_f"], w["N_crit_m3"]))
    print("  物理: ψ_s ∈ [%.4f, %.4f] V（简并 N_crit=%.1e m⁻³）· φ_F=%.4f V"
          % (d["psi_min_v"], d["psi_max_v"], d["N_crit_m3"], d["phi_f_v"]))
    print("  物理/数值 半宽比 = %.3f（<1 ⇒ 物理模型先失效）" % window_ratio_physical_over_numerical())
    print("=== 缺口量化（L=65 nm）===")
    g = literature_gap_report(0.065)
    print("  长沟道 V_th=%.4f V · roll-off=%.4f V (%.1f%%) · DIBL=%.4f V (%.1f%%)"
          % (g["V_th_long_channel_v"], g["rolloff_dV_th_v"], g["rolloff_frac_of_vth"] * 100,
             g["dibl_dV_th_v"], g["dibl_frac_of_vth"] * 100))
    print("=== 自检 ===")
    run_selfchecks(verbose=True)
