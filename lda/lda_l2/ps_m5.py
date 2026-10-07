"""PS-M5 · 微流控 / Lab-on-chip 多物理场（吃狗粮 v5）。

═══ 策略（把 PS-M4 的生物/化学读出延伸到真实「芯片实验室」流体/热/界面物理）═══
PS-M4 把 analyte 结合 → 表面折射率变化 → 谐振位移的读出链判决化。但 lab-on-chip 里
analyte **不是**静态滴加：它被**压力驱动流 / 毛细驱动 / 表面张力**输运到传感窗，并在
**微通道热管理**（PCR 热循环、电泳焦耳热）下工作。PS-M5 抽取三道可判决的**多物理场支柱**，
每道都用「解析闭式 golden × 方法学独立的数值候选」双轨判决（与 PS-M2~M4 同纪律）：

  · B463 矩形微通道 Hagen-Poiseuille 体积流量 `Q`：压力驱动输运的吞吐基准；
  · B464 Lucas-Washburn 毛细填充长度 `L(t)`：无泵毛细自驱动输运的时间尺度；
  · B465 圆柱微通道壁面径向热阻 `R_th`：微通道热管理（焦耳热/PCR）的散热瓶颈。

═══ 🔴 物理要点 ═══
  · B463 矩形截面形状因子 `C_f(α)`（α=b/a）是精确级数，α→0 退化为平行板缝（C_f→1）、
    α=1 退化为方管（C_f=0.4217）；候选用**红黑（棋盘）SOR** 解 2D Poisson，必须红黑
    分色（真 Gauss-Seidel 序）才能收敛（整片同时更新是 JOR，2D Poisson 发散）。
  · B464 Lucas-Washburn ODE `dL/dt=k/L` 在 L=0 处斜率无限 ⇒ 所有显式法首步必爆；
    后向欧拉（隐式·无条件稳定）`L_{n+1}=(L_n+√(L_n²+4hk))/2` 从 L₀=0 平滑起步。
  · B465 径向导热用**守恒界面通量**格式（界面半径 r_{1/2}=r_i+dr/2），比「前向差分 × r_i」
    一阶格式高一级精度（O(dr²) 收敛）。

═══ 🔴 纪律 ═══
· 进报告数字一律**模块现算**（不转录草稿）；
· 判据读到的值 = 模块现算值；
· 每道守卫配反向探针（先证能变红）；
· 复用 PS-M5 内核（`_batch_b36_numeric`）为三道多物理场数学单一真源。
· 量纲 O(1) 化（判据 D 纪律）：Q 报 nL/s（×1e9）、L 报 mm（×1000）、R_th 报 K/W。

═══ 诚实边界 ═══
· 几何/流体/热参数为**设计示例**（水 µ=1e-3 Pa·s、γ=0.072 N/m、玻璃 k=1.4 W/m·K；
  通道 20×10 µm²、长 1 mm、毛细管 Ø10 µm）。结论只可用于数值方法与量级，不得作制造/性能宣称。
· B463 为充分发展层流（低 Re 假设），忽略入口效应/可压缩性；B464 为理想圆柱毛细
  （忽略重力/动态接触角滞后）；B465 为一维径向稳态导热（忽略轴向漏热）。均为 lab-on-chip
  标准一阶模型。
· 零商业依赖（纯 numpy + math）。
"""
from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, Optional

# 复用 PS-M5 数学核（B-36 批 · B463/B464/B465）：微流控/Lab-on-chip 多物理场
from lda_harness._batch_b36_numeric import (  # noqa: E402
    _cf_rect,
    poiseuille_flow_rate_fd_nl_s,
    poiseuille_flow_rate_golden_nl_s,
    thermal_resistance_fd_k_W,
    thermal_resistance_golden_k_W,
    washburn_length_be_mm,
    washburn_length_golden_mm,
)


# ---------------------------------------------------------------------------
# 默认设计示例几何/流体/热参数
# ---------------------------------------------------------------------------
#: B463 矩形微通道（20×10 µm²、长 1 mm，水 µ=1e-3 Pa·s，ΔP=1000 Pa）
DEFAULT_B463: Dict[str, float] = {
    "dp_pa": 1000.0, "mu_pas": 1e-3, "L_m": 1e-3, "w_m": 20e-6, "h_m": 10e-6,
}
#: B464 毛细管（Ø10 µm，水 γ=0.072 N/m、η=1e-3 Pa·s，t=1 s，完全润湿 cosθ=1）
DEFAULT_B464: Dict[str, float] = {
    "D_m": 10e-6, "gamma_Nm": 0.072, "cos_theta": 1.0, "eta_Pas": 1e-3, "t_s": 1.0,
}
#: B465 圆柱壁（r_i=10 µm、r_o=30 µm，玻璃 k=1.4 W/m·K，长 1 mm）
DEFAULT_B465: Dict[str, float] = {
    "r_i_m": 10e-6, "r_o_m": 30e-6, "k_WmK": 1.4, "L_m": 1e-3,
}

#: 逐锚判据 D tol（与内核 _TOL_BY_BID 同口径，模块级引用，防漂移）
_TOL_B463 = 5e-5    # nL/s
_TOL_B464 = 1e-1    # mm
_TOL_B465 = 1e-2    # K/W


# ---------------------------------------------------------------------------
# 真实多物理场物理量（设计示例 · 量级 + 反向探针）
# ---------------------------------------------------------------------------
def real_poiseuille_Q(p: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """矩形微通道体积流量（golden 精确级数 + FD 候选 + 关键无量纲）。"""
    pp = dict(DEFAULT_B463) if p is None else dict(p)
    g = poiseuille_flow_rate_golden_nl_s(
        pp["dp_pa"], pp["mu_pas"], pp["L_m"], pp["w_m"], pp["h_m"])
    c = poiseuille_flow_rate_fd_nl_s(
        pp["dp_pa"], pp["mu_pas"], pp["L_m"], pp["w_m"], pp["h_m"], N_grid=200)
    a = max(pp["w_m"], pp["h_m"])
    b = min(pp["w_m"], pp["h_m"])
    return {
        "dp_pa": pp["dp_pa"], "mu_pas": pp["mu_pas"], "L_m": pp["L_m"],
        "w_m": pp["w_m"], "h_m": pp["h_m"],
        "golden_Q_nl_s": g, "fd_Q_nl_s": c,
        "abs_res": abs(g - c), "alpha": (b / a) if a > 0 else float("nan"),
        "C_f": _cf_rect(b / a) if a > 0 else float("nan"),
        "aspect_ratio": (pp["w_m"] / pp["h_m"]) if pp["h_m"] > 0 else float("nan"),
    }


def real_washburn_L(p: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """Lucas-Washburn 毛细填充长度（golden 闭式 + 后向欧拉候选）。"""
    pp = dict(DEFAULT_B464) if p is None else dict(p)
    g = washburn_length_golden_mm(
        pp["D_m"], pp["gamma_Nm"], pp["cos_theta"], pp["eta_Pas"], pp["t_s"])
    c = washburn_length_be_mm(
        pp["D_m"], pp["gamma_Nm"], pp["cos_theta"], pp["eta_Pas"],
        pp["t_s"], n_steps=2000)
    return {
        "D_m": pp["D_m"], "gamma_Nm": pp["gamma_Nm"], "cos_theta": pp["cos_theta"],
        "eta_Pas": pp["eta_Pas"], "t_s": pp["t_s"],
        "golden_L_mm": g, "be_L_mm": c, "abs_res": abs(g - c),
    }


def real_thermal_R(p: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """圆柱微通道壁面径向热阻（golden Fourier 闭式 + 1D FD 守恒格式候选）。"""
    pp = dict(DEFAULT_B465) if p is None else dict(p)
    g = thermal_resistance_golden_k_W(
        pp["r_i_m"], pp["r_o_m"], pp["k_WmK"], pp["L_m"])
    c = thermal_resistance_fd_k_W(
        pp["r_i_m"], pp["r_o_m"], pp["k_WmK"], pp["L_m"], N=600)
    return {
        "r_i_m": pp["r_i_m"], "r_o_m": pp["r_o_m"], "k_WmK": pp["k_WmK"],
        "L_m": pp["L_m"],
        "golden_R_K_W": g, "fd_R_K_W": c, "abs_res": abs(g - c),
    }


# ---------------------------------------------------------------------------
# 场景（复用量级 + 反向探针）
# ---------------------------------------------------------------------------
SCENARIOS: Dict[str, Dict[str, Any]] = {
    # PDMS 软光刻微通道（水，低压差驱动输运）
    "pdms_channel": dict(kind="B463",
                         dp_pa=500.0, mu_pas=1e-3, L_m=5e-3, w_m=50e-6, h_m=25e-6),
    # 玻璃毛细（水，完全润湿，t=1 s 自驱动填充长度）
    "glass_capillary": dict(kind="B464",
                            D_m=10e-6, gamma_Nm=0.072, cos_theta=1.0,
                            eta_Pas=1e-3, t_s=1.0),
    # 硅微通道壁（k=150 W/m·K，散热瓶颈对照玻璃）
    "si_wall": dict(kind="B465",
                    r_i_m=10e-6, r_o_m=30e-6, k_WmK=150.0, L_m=1e-3),
}


def _scenario_report(v: Dict[str, Any]) -> Dict[str, Any]:
    if v["kind"] == "B463":
        return real_poiseuille_Q({k: v[k] for k in
                                  ("dp_pa", "mu_pas", "L_m", "w_m", "h_m")})
    if v["kind"] == "B464":
        return real_washburn_L({k: v[k] for k in
                               ("D_m", "gamma_Nm", "cos_theta", "eta_Pas", "t_s")})
    if v["kind"] == "B465":
        return real_thermal_R({k: v[k] for k in
                              ("r_i_m", "r_o_m", "k_WmK", "L_m")})
    return {}


# ---------------------------------------------------------------------------
# 自校 / 反向探针（先证能变红）
# ---------------------------------------------------------------------------
def selfcheck_ps_m5(tol_b463: float = _TOL_B463,
                    tol_b464: float = _TOL_B464,
                    tol_b465: float = _TOL_B465) -> Dict[str, Any]:
    """PS-M5 守卫：三道多物理场核心对齐 + 物理量纲合理 + 缩放律 + 反向红标。"""
    q = real_poiseuille_Q()
    l = real_washburn_L()
    r = real_thermal_R()
    checks: Dict[str, Any] = {}

    # ① B463 核心对齐：golden 精确级数 vs 红黑 SOR FD（|Δ|<tol=5e-5）
    checks["b463_aligned_golden_vs_fd"] = (q["abs_res"] < tol_b463)

    # ② B463 物理量纲：Q 有限且为正
    checks["b463_Q_positive"] = (math.isfinite(q["golden_Q_nl_s"])
                                 and q["golden_Q_nl_s"] > 0.0)

    # ③ B463 缩放律：Q ∝ ΔP（golden 精确线性，doubling ΔP ⇒ 2×Q）
    q2 = poiseuille_flow_rate_golden_nl_s(
        DEFAULT_B463["dp_pa"] * 2.0, DEFAULT_B463["mu_pas"],
        DEFAULT_B463["L_m"], DEFAULT_B463["w_m"], DEFAULT_B463["h_m"])
    rel = (abs(q2 - 2.0 * q["golden_Q_nl_s"]) / (2.0 * q["golden_Q_nl_s"])
           if q["golden_Q_nl_s"] > 0 else float("nan"))
    checks["b463_Q_scales_linear_dP"] = (rel < 1e-9)

    # ④ B463 缩放律：Q ∝ 1/μ（doubling μ ⇒ 0.5×Q）
    q3 = poiseuille_flow_rate_golden_nl_s(
        DEFAULT_B463["dp_pa"], DEFAULT_B463["mu_pas"] * 2.0,
        DEFAULT_B463["L_m"], DEFAULT_B463["w_m"], DEFAULT_B463["h_m"])
    rel3 = (abs(q3 - 0.5 * q["golden_Q_nl_s"]) / (0.5 * q["golden_Q_nl_s"])
            if q["golden_Q_nl_s"] > 0 else float("nan"))
    checks["b463_Q_scales_inverse_mu"] = (rel3 < 1e-9)

    # ⑤ B463 连续一致：方管 w=h ⇒ 应等于方管级数值（C_f=0.4217 闭式自洽，1e-9）
    a_sq = 10e-6
    q_sq = poiseuille_flow_rate_golden_nl_s(
        DEFAULT_B463["dp_pa"], DEFAULT_B463["mu_pas"],
        DEFAULT_B463["L_m"], a_sq, a_sq)
    q_sq_exact = ((DEFAULT_B463["dp_pa"] / (DEFAULT_B463["mu_pas"]
                   * DEFAULT_B463["L_m"])) * (a_sq ** 4 / 12.0)
                  * _cf_rect(1.0) * 1e9)
    rel_sq = (abs(q_sq - q_sq_exact) / q_sq_exact
              if q_sq_exact > 0 else float("nan"))
    checks["b463_square_tube_continuity"] = (rel_sq < 1e-9)

    # ⑥ B463 反向红标：μ≤0 ⇒ 必为 nan
    checks["b463_zero_viscosity_red_flag"] = (
        not math.isfinite(poiseuille_flow_rate_golden_nl_s(
            DEFAULT_B463["dp_pa"], 0.0, DEFAULT_B463["L_m"],
            DEFAULT_B463["w_m"], DEFAULT_B463["h_m"])))

    # ⑦ B464 核心对齐：golden 闭式 vs 后向欧拉（|Δ|<tol=0.1 mm）
    checks["b464_aligned_golden_vs_be"] = (l["abs_res"] < tol_b464)

    # ⑧ B464 物理量纲：L 有限且为正
    checks["b464_L_positive"] = (math.isfinite(l["golden_L_mm"])
                                 and l["golden_L_mm"] > 0.0)

    # ⑨ B464 缩放律：L ∝ √t（golden 精确，L(4s) ≈ 2·L(1s)）
    l4 = washburn_length_golden_mm(
        DEFAULT_B464["D_m"], DEFAULT_B464["gamma_Nm"], DEFAULT_B464["cos_theta"],
        DEFAULT_B464["eta_Pas"], 4.0)
    rel4 = (abs(l4 - 2.0 * l["golden_L_mm"]) / (2.0 * l["golden_L_mm"])
            if l["golden_L_mm"] > 0 else float("nan"))
    checks["b464_L_scales_sqrt_t"] = (rel4 < 1e-9)

    # ⑩ B464 缩放律：L ∝ √γ（doubling γ ⇒ √2·L）
    l2 = washburn_length_golden_mm(
        DEFAULT_B464["D_m"], DEFAULT_B464["gamma_Nm"] * 2.0,
        DEFAULT_B464["cos_theta"], DEFAULT_B464["eta_Pas"], DEFAULT_B464["t_s"])
    rel2 = (abs(l2 - math.sqrt(2.0) * l["golden_L_mm"])
            / (math.sqrt(2.0) * l["golden_L_mm"])
            if l["golden_L_mm"] > 0 else float("nan"))
    checks["b464_L_scales_sqrt_gamma"] = (rel2 < 1e-9)

    # ⑪ B464 反向红标：cosθ<0（非润湿，γ·cosθ<0）⇒ 必为 nan
    checks["b464_nonwetting_red_flag"] = (
        not math.isfinite(washburn_length_golden_mm(
            DEFAULT_B464["D_m"], DEFAULT_B464["gamma_Nm"], -1.0,
            DEFAULT_B464["eta_Pas"], DEFAULT_B464["t_s"])))

    # ⑫ B464 反向红标：η≤0 ⇒ 必为 nan
    checks["b464_zero_viscosity_red_flag"] = (
        not math.isfinite(washburn_length_golden_mm(
            DEFAULT_B464["D_m"], DEFAULT_B464["gamma_Nm"],
            DEFAULT_B464["cos_theta"], 0.0, DEFAULT_B464["t_s"])))

    # ⑬ B465 核心对齐：golden Fourier 闭式 vs 1D FD 守恒格式（|Δ|<tol=1e-2）
    checks["b465_aligned_golden_vs_fd"] = (r["abs_res"] < tol_b465)

    # ⑭ B465 物理量纲：R 有限且为正
    checks["b465_R_positive"] = (math.isfinite(r["golden_R_K_W"])
                                 and r["golden_R_K_W"] > 0.0)

    # ⑮ B465 缩放律：R 随 r_o 增大而增大（壁更厚 ⇒ 更多材料 ⇒ 更大热阻）
    r_wide = thermal_resistance_golden_k_W(
        DEFAULT_B465["r_i_m"], 50e-6, DEFAULT_B465["k_WmK"], DEFAULT_B465["L_m"])
    checks["b465_R_increases_with_ro"] = (
        math.isfinite(r_wide) and r_wide > r["golden_R_K_W"])

    # ⑯ B465 薄壁极限：r_o→r_i ⇒ R→0（有限小正值，非 nan）
    r_thin = thermal_resistance_golden_k_W(10e-6, 10.2e-6, 1.4, 1e-3)
    checks["b465_thin_wall_limit_to_zero"] = (
        math.isfinite(r_thin) and r_thin > 0.0)

    # ⑰ B465 反向红标：k≤0 ⇒ 必为 nan
    checks["b465_zero_conductivity_red_flag"] = (
        not math.isfinite(thermal_resistance_golden_k_W(
            DEFAULT_B465["r_i_m"], DEFAULT_B465["r_o_m"], 0.0, DEFAULT_B465["L_m"])))

    # ⑱ B465 反向红标：r_o≤r_i ⇒ 必为 nan
    checks["b465_invalid_radii_red_flag"] = (
        not math.isfinite(thermal_resistance_golden_k_W(
            30e-6, 10e-6, DEFAULT_B465["k_WmK"], DEFAULT_B465["L_m"])))

    all_pass = all(v for k, v in checks.items() if not k.startswith(("note",)))
    scen_reports = {}
    for k, v in SCENARIOS.items():
        scen_reports[k] = _scenario_report(v)
    return {
        "selfcheck": {"all_pass": all_pass, "checks": checks},
        "baseline_poiseuille": q,
        "baseline_washburn": l,
        "baseline_thermal": r,
        "scenarios": scen_reports,
    }


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------
def main(out_dir: Optional[str] = None) -> int:
    rep = selfcheck_ps_m5()
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "ps_m5_report.json"), "w",
                  encoding="utf-8") as f:
            json.dump(rep, f, indent=2, ensure_ascii=False)
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 0 if rep["selfcheck"]["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(out_dir=os.path.join("outputs", "ps_m5")))
