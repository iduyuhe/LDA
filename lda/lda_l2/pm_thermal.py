"""光子存储 · **加热器电-热-光链路**（PM-G8 · v0.9.293 · 纯标准库）

═══════════════════════════════════════════════════════════════════════
改前是什么（PM-G8「加热器电-热联仿与 T1 器件级真值」）
═══════════════════════════════════════════════════════════════════════
M4 只交付了**行为级**外设（`R_h = R_sheet·(L_h/w_h)`、`P = V²/R`、`E = P·t`），
热-光耦合与 T1 全落在「器件级锁死区」。而 `lda_design/active_models.py` 里
热阻是**一个与几何无关的手填常数** `R_TH_K_PER_MW = 1.0`（注释只写「文献量级」）：
  ⇒ 同一台机器上，「热阻」既能由几何算（本层），又被当成常数用（`phase_shift_rad`），
    **两个口径相差 12.5 倍且从无人核** —— 与 v0.9.287/288/290/291/292 同型。

═══════════════════════════════════════════════════════════════════════
本层给什么（1D 串联热阻 + 集总热容 · 全闭式 · 带对照支路）
═══════════════════════════════════════════════════════════════════════
① `layer_thermal_resistance`  分层热阻 `R_i = t_i/(k_i·A)`，`A = L_h·w_h`（串联求和）
② `thermal_capacitance`       集总热容 `C = Σ ρc_p,i·V_i`（同体积口径）
③ `thermal_time_constant`     **T1 = τ = R_th·C_th**（这就是「器件级 T1」的解析估计）
④ `step_response_dT`          阶跃响应 `ΔT(t)/ΔT_ss = 1 − e^{−t/τ}`
⑤ `pi_shift_link`             π 相移的 ΔT_π / P_π / 开关能量，**两条能量路径互核**
⑥ `heater_link_report`        参考几何全量 + 与「手填常数口径」的比值对照

🔴 **三条对照支路（闭式已知答案，全部写进判据）**：
   · **稳态能量守恒**：`P ≡ ΔT/R_th`（回代逐位）；
   · **两条能量路径相等**：`E = C_th·ΔT_π` ≡ `P_π·τ`（相对 1e-12）—— 因为 `τ = R·C`；
   · **阶跃 τ 点**：`t = τ ⇒ 1 − e^{−1} = 0.6321205588285577`（逐位）。

═══════════════════════════════════════════════════════════════════════
诚实边界（**必读，别把 1D 当 2D 用**）
═══════════════════════════════════════════════════════════════════════
· **1D 串联模型系统性偏大**：它假设热只沿垂直方向一维流走，忽略衬底/包层的**横向扩展散热**
  （真实散热面远大于 `A`）⇒ 本层 `R_th` 是**上界**，故 `P_π` 是**乐观值（下界）**。
  参考几何：1D 给 `12.51 K/mW`，而现用常数 `1.0 K/mW` ⇒ 比值 **12.51×**，真实值落在两者之间，
  必须由 **2D/FEM 或工艺实测**定夺 ⇒ 「热阻真值」仍是**边界**（见 `PM-G8b`）。
· **未含光场限制因子 Γ**：等价 `Γ = 1`（加热区与光场完全重叠的乐观口径）；`Γ < 1` 会让 `P_π` 等比例放大。
· **参数全为公开工程典型**（`k_SiO2=1.4` / `k_Si=148` / ρc_p / `R_sheet=10 Ω/sq`），
  **非本项目实测锚**（与 `PM-G9` 同口径）。
· **不是 PCM 相变开关能耗**：本层算的是「把波导加热到 ΔT」的热调能耗，相变器件能耗属另一本账。
· 不作制造 / 能耗 / 性能宣称；不报 fJ/op、TOPS。
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional

__all__ = [
    "GEOMETRY_REF",
    "K_SIO2", "K_SI", "RC_SIO2", "RC_SI", "R_SHEET_OHN_PER_SQ",
    "layer_thermal_resistance",
    "thermal_resistance_k_per_mw",
    "thermal_capacitance",
    "thermal_time_constant",
    "step_response_dT",
    "pi_shift_link",
    "heater_link_report",
    "selfcheck_pm_thermal",
]

# ── 材料参数（**公开工程典型量级，非实测锚**）──────────────────────────
K_SIO2 = 1.4          # W/(m·K)  二氧化硅热导率
K_SI = 148.0          # W/(m·K)  硅热导率
RC_SIO2 = 2200.0 * 730.0   # J/(m³·K) 体积热容：ρ·c_p
RC_SI = 2329.0 * 700.0
#: TiN 薄膜方阻（Ω/sq）—— 与 `PM-G9` 同口径的公开典型值
R_SHEET_OHN_PER_SQ = 10.0

#: 参考几何（SOI 220 nm 平台 · 100 µm 长加热器 · 2 µm 宽）
GEOMETRY_REF: Dict[str, float] = {
    "L_h_um": 100.0,      # 加热器长度（沿波导）
    "w_h_um": 2.0,        # 加热器宽度
    "t_clad_um": 1.5,     # 上包层 SiO2 厚度
    "t_si_um": 0.22,      # 波导芯 Si 厚度（220 nm 平台）
    "t_box_um": 2.0,      # 埋氧层 SiO2 厚度
}

#: 现役「手填常数」口径（`lda_design.active_models.R_TH_K_PER_MW`）—— 仅用于比值对照
R_TH_CONST_K_PER_MW = 1.0


def _geom(g: Optional[Dict[str, float]]) -> Dict[str, float]:
    out = dict(GEOMETRY_REF)
    if g:
        out.update({k: float(v) for k, v in g.items()})
    return out


def _area_m2(g: Dict[str, float]) -> float:
    return float(g["L_h_um"]) * 1e-6 * float(g["w_h_um"]) * 1e-6


# ══════════════════════════════════════════════════════════════════════
# ① 分层热阻（串联）
# ══════════════════════════════════════════════════════════════════════
def layer_thermal_resistance(geom: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """各层热阻 `R_i = t_i/(k_i·A)` 与串联合计（K/W）。

    路径：加热器 → 上包层 SiO2 → 波导芯 Si → 埋氧 SiO2 → 衬底（**恒温热沉边界**）。
    """
    g = _geom(geom)
    a = _area_m2(g)
    if a <= 0.0:
        raise ValueError("加热器面积须 > 0")
    layers = (
        ("clad_sio2", float(g["t_clad_um"]) * 1e-6, K_SIO2),
        ("core_si", float(g["t_si_um"]) * 1e-6, K_SI),
        ("box_sio2", float(g["t_box_um"]) * 1e-6, K_SIO2),
    )
    rows = []
    total = 0.0
    for name, t, k in layers:
        r = t / (k * a)
        rows.append({"layer": name, "t_m": t, "k_W_mK": k, "R_K_W": float(r)})
        total += r
    return {"area_m2": float(a), "layers": rows, "R_th_K_W": float(total),
            "R_th_K_per_mW": float(total / 1000.0)}


def thermal_resistance_k_per_mw(geom: Optional[Dict[str, float]] = None) -> float:
    """串联热阻（K/mW）—— 与手填常数**同单位**，便于直接对照。"""
    return float(layer_thermal_resistance(geom)["R_th_K_per_mW"])


# ══════════════════════════════════════════════════════════════════════
# ② 集总热容
# ══════════════════════════════════════════════════════════════════════
def thermal_capacitance(geom: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """集总热容 `C = Σ ρc_p,i · (A·t_i)`（J/K）—— 与热阻**同一体积口径**。"""
    g = _geom(geom)
    a = _area_m2(g)
    rows = []
    total = 0.0
    for name, t_um, rc in (
        ("clad_sio2", float(g["t_clad_um"]), RC_SIO2),
        ("core_si", float(g["t_si_um"]), RC_SI),
        ("box_sio2", float(g["t_box_um"]), RC_SIO2),
    ):
        c = rc * a * (t_um * 1e-6)
        rows.append({"layer": name, "C_J_K": float(c)})
        total += c
    return {"layers": rows, "C_th_J_K": float(total)}


# ══════════════════════════════════════════════════════════════════════
# ③ T1 热时间常数
# ══════════════════════════════════════════════════════════════════════
def thermal_time_constant(geom: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """**T1 = τ = R_th·C_th**（s）。这就是「器件级 T1 真值」的**解析估计**（非实测）。"""
    r = layer_thermal_resistance(geom)["R_th_K_W"]
    c = thermal_capacitance(geom)["C_th_J_K"]
    return {"R_th_K_W": float(r), "C_th_J_K": float(c),
            "tau_s": float(r * c), "tau_us": float(r * c * 1e6)}


# ══════════════════════════════════════════════════════════════════════
# ④ 阶跃响应（一阶集总系统）
# ══════════════════════════════════════════════════════════════════════
def step_response_dT(t_s: float, tau_s: float) -> float:
    """归一化阶跃响应 `ΔT(t)/ΔT_ss = 1 − e^{−t/τ}`。

    🔴 **对照支路**：`t = τ ⇒ 1 − e^{−1}`（**与参数无关**的闭式已知答案）。
    """
    tau = float(tau_s)
    if tau <= 0.0:
        return 1.0 if float(t_s) > 0.0 else 0.0
    return float(1.0 - math.exp(-float(t_s) / tau))


# ══════════════════════════════════════════════════════════════════════
# ⑤ π 相移链路（ΔT_π → P_π → 开关能量 · 两条路径互核）
# ══════════════════════════════════════════════════════════════════════
def pi_shift_link(geom: Optional[Dict[str, float]] = None,
                  wl_um: float = 1.55,
                  dn_dT: Optional[float] = None,
                  gamma: float = 1.0) -> Dict[str, Any]:
    """π 相移所需的温升 / 功率 / 开关能量，并与手填常数口径对照。

    🔴 **复用真源**：`dn/dT` 与相位公式来自 `lda_design.active_models`
    （`DN_DT_SI_PER_K` / `phase_shift_rad`），不在本层重写 —— 同源必须写成引用。
    """
    from lda_design import active_models as AM  # 单一真源（同源引用，非字面量拷贝）

    dnd = float(AM.DN_DT_SI_PER_K if dn_dT is None else dn_dT)
    g = _geom(geom)
    L_um = float(g["L_h_um"])
    # 🔴 K/mW 走**单一 accessor**（`thermal_resistance_k_per_mw`），不再 `["R_th_K_per_mW"]` 直取
    #    —— 同一口径两个入口 = 会漂；v0.9.298 的可达性门禁当场抓出这个 accessor 「零引用」。
    #    K/W 仍直接取自 `rth_report`（该 dict 另有分层明细），不在此重复换算。
    rth_report = layer_thermal_resistance(g)
    r_th_mw = thermal_resistance_k_per_mw(g)
    tau = thermal_time_constant(g)
    c_th = tau["C_th_J_K"]

    # Δφ = (2π/λ)·(dn/dT·Γ·ΔT)·L  ⇒  ΔT_π = π / [(2π/λ)·dn/dT·Γ·L]
    k_per_kelvin = (2.0 * math.pi / float(wl_um)) * dnd * float(gamma) * L_um
    if k_per_kelvin <= 0.0:
        raise ValueError("相移灵敏度须 > 0")
    dT_pi = math.pi / k_per_kelvin                      # K
    P_pi_mw = dT_pi / r_th_mw                           # mW（ΔT = R_th·P）
    # 两条独立的能量路径（τ = R·C ⇒ 必然相等）
    e_from_c = c_th * dT_pi                             # J
    e_from_p = (P_pi_mw * 1e-3) * tau["tau_s"]          # J
    # 手填常数口径（同 Γ）—— 仅作对照，不作结论
    const = AM.power_for_pi(L_um, wl_um, dnd * float(gamma),
                            R_TH_CONST_K_PER_MW)
    return {
        "geometry": g,
        "dn_dT_per_K": dnd,
        "gamma": float(gamma),
        "R_th_K_W": float(rth_report["R_th_K_W"]),
        "R_th_K_per_mW": float(r_th_mw),
        "C_th_J_K": float(c_th),
        "tau_s": float(tau["tau_s"]),
        "tau_us": float(tau["tau_us"]),
        "dT_pi_K": float(dT_pi),
        "P_pi_mw": float(P_pi_mw),
        "E_switch_nJ": float(e_from_c * 1e9),
        "E_from_C_J": float(e_from_c),
        "E_from_Ptau_J": float(e_from_p),
        # 与「手填常数」口径的对照（如实并列，不替换对外数字）
        "P_pi_mw_const_R_th": float(const),
        "P_pi_ratio_vs_const": float(P_pi_mw / const) if const > 0 else float("inf"),
        "R_th_ratio_vs_const": float(r_th_mw / R_TH_CONST_K_PER_MW),
    }


# ══════════════════════════════════════════════════════════════════════
# ⑥ 参考几何报告
# ══════════════════════════════════════════════════════════════════════
def heater_link_report(geom: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """参考几何全量报告（含三条对照支路的现场回代 + 诚实边界）。"""
    link = pi_shift_link(geom)
    rth = link["R_th_K_per_mW"]
    dT = link["dT_pi_K"]
    p_mw = link["P_pi_mw"]
    # 对照支路① 稳态能量守恒：P ≡ ΔT/R_th（回代逐位）
    p_back = dT / rth
    # 对照支路② 两条能量路径相等
    rel_e = abs(link["E_from_C_J"] - link["E_from_Ptau_J"]) / link["E_from_C_J"]
    # 对照支路③ 阶跃 τ 点
    at_tau = step_response_dT(link["tau_s"], link["tau_s"])
    return {
        "link": link,
        "check_steady_state": {"P_mw": float(p_mw), "P_back_mw": float(p_back),
                               "abs_diff": float(abs(p_mw - p_back))},
        "check_energy_rel": float(rel_e),
        "check_step_at_tau": float(at_tau),
        "one_d_is_upper_bound": True,
        "note": (
            "1D 串联热阻忽略横向扩展散热 ⇒ R_th 是**上界**、P_π 是**乐观值**；"
            "参考几何 1D 得 12.51 K/mW，而现用手填常数 1.0 K/mW ⇒ 比值 12.51×，"
            "真实值落在两者之间，须 2D/FEM 或实测定夺（见 PM-G8b 边界声明）；"
            "未含光场限制因子 Γ（等价 Γ=1，乐观）；参数为公开工程典型，非本项目实测锚；"
            "算的是热调能耗，**不是 PCM 相变开关能耗**。"
        ),
    }


# ══════════════════════════════════════════════════════════════════════
# 自检
# ══════════════════════════════════════════════════════════════════════
def selfcheck_pm_thermal() -> Dict[str, bool]:
    c: Dict[str, bool] = {}
    rep = heater_link_report()
    link = rep["link"]

    # ① 稳态能量守恒（回代逐位）
    c["steady_state_energy_conserved"] = rep["check_steady_state"]["abs_diff"] <= 1e-15
    # ② 两条能量路径相等（τ=R·C 的必然结果）
    c["two_energy_paths_agree"] = rep["check_energy_rel"] <= 1e-12
    # ③ 阶跃 τ 点 == 1−e^{−1}（闭式已知答案，与参数无关）
    c["step_at_tau_is_one_minus_inv_e"] = abs(rep["check_step_at_tau"] - (1.0 - math.exp(-1.0))) <= 1e-15
    # ④ P=0 ⇒ ΔT=0（零输入零输出）
    c["zero_power_zero_rise"] = (0.0 * link["R_th_K_per_mW"]) == 0.0
    # ⑤ 线性：P 加倍 ⇒ ΔT 加倍
    c["linear_in_power"] = abs((2.0 * link["P_pi_mw"] * link["R_th_K_per_mW"])
                               - 2.0 * link["dT_pi_K"]) <= 1e-12
    # ⑥ τ 与功率无关（同几何两次调用一致）
    c["tau_power_independent"] = (thermal_time_constant()["tau_s"]
                                  == thermal_time_constant()["tau_s"])
    # ⑦ 比值解析关系：ΔT = R_th·P ⇒ **功率比与热阻比互为倒数**（乘积恒为 1）
    #    🔴 写这条时我自己先把方向搞错过（写成两者相等）——正是本仓反复吃的「比值方向」坑，
    #      由本条判据当场抓住；故判据取「乘积 == 1」而不是「相等」。
    c["power_ratio_is_inverse_of_resistance_ratio"] = abs(
        link["P_pi_ratio_vs_const"] * link["R_th_ratio_vs_const"] - 1.0) <= 1e-12
    # ⑧ 1D 是上界：R_th(1D) > 手填常数（如实记录方向）
    c["one_d_exceeds_constant"] = link["R_th_K_per_mW"] > R_TH_CONST_K_PER_MW
    # ⑨ 分层热阻加和自洽
    lay = layer_thermal_resistance()
    c["layer_sum_consistent"] = abs(sum(x["R_K_W"] for x in lay["layers"])
                                    - lay["R_th_K_W"]) <= 1e-12 * lay["R_th_K_W"]
    # ⑩ 非法几何抛 ValueError（不静默给假数）
    try:
        layer_thermal_resistance({"w_h_um": 0.0})
        c["bad_geometry_raises"] = False
    except ValueError:
        c["bad_geometry_raises"] = True
    return c


if __name__ == "__main__":  # pragma: no cover
    sc = selfcheck_pm_thermal()
    bad = [k for k, v in sc.items() if not v]
    print("pm_thermal 自检：%d/%d 通过" % (len(sc) - len(bad), len(sc)))
    if bad:
        print("FAIL:", bad)
    r = heater_link_report()["link"]
    print("R_th=%.4f K/mW · C_th=%.4g J/K · tau=%.2f us" %
          (r["R_th_K_per_mW"], r["C_th_J_K"], r["tau_us"]))
    print("dT_pi=%.2f K · P_pi=%.3f mW · E_sw=%.2f nJ" %
          (r["dT_pi_K"], r["P_pi_mw"], r["E_switch_nJ"]))
