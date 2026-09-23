# -*- coding: utf-8 -*-
"""U3 · 微环 κ_c 的 FDTD 标定层 + 网格可信度机器化。

背景（内部总结 §4.2 U3）
------------------------
`wdm_ring_anchor`（`lda_layout/wdm_mesh_pnr.py`）的 κ_c 一直取**解析经验模型**
`gap_to_kappa`（`κ_ref=0.35` / `L_ev=0.15µm` / 与 λ 无关，D-37）作**占位** ——
模块 docstring 自己写明「解析上界作占位，honest note 标注」，即**它是一处已知缺口**。
与此同时 D-55/D-60/D-68 已把 2D FDTD 标定 κ_c(gap,λ) 用于 `wdm_coupler`。

本模块做两件事：
  1. 把「微环锚」这条链也接到 FDTD 标定（`calibrated_ring_anchor`），并给出
     解析占位 vs 第一性原理的**量化偏差**；
  2. 🔴 把**标定自身的可信度**机器化 —— 网格收敛、粗网格假结果、跨网格离散度、
     设计预算达标与否，全部变成死标量判据（`run_ring_kappa_calib_smoke.py`）。

复用（不重写任何已证数学）
--------------------------
| 复用对象 | 来源 | 用途 |
|---|---|---|
| `kappa_fdtd(gap, wl, dl_factor)` | `lda_agent.calibrate_kappa_grid`（D-60） | FDTD κ_c 双点差分提取（D-55 方法） |
| `dc_transmission_spectrum` / `build_dc_field` | `lda_solver.fdtd2d_coupler`（D-29） | 2D FDTD 全场稳态透射 + L_eff |
| `gap_to_kappa(gap, ...)` | `lda_agent.ring_adddrop`（D-37） | 解析经验模型（golden 位，**非真值**） |
| `kappa_c_grid_interp(grid, gap, wl)` | `lda_agent.wdm_coupler`（D-60/D-68） | 标定表双线性插值 |
| `wdm_ring_anchor(wl, n_g, m, gap)` | `lda_layout.wdm_mesh_pnr` | 环几何（R / L_couple / FSR） |

🔴 三条诚实边界（实测确立，写在前面的最后）
------------------------------------------
① **判据 D（残差严格单调）在本实现下不成立** —— 实测 gap=0.30 可信残差序列
   `[0.002210, 0.013622, 0.001282]`、gap=0.25 为 `[0.001680, 0.005019]`，**均非单调**。
   ⇒ 本模块**不**声称「κ_c 已收敛」；只报**跨网格离散度**作为真实不确定度。
   根因 = **阶梯离散的有效 gap 随 dl 非单调变化**，而 κ_c 对 gap 指数敏感
   （L_ev≈0.1µm ⇒ 0.02µm 的有效 gap 误差 ⇒ ~20% 的 κ_c 变化）。
② **解析模型是占位上界，不是真值** —— FDTD/解析偏差实测 **13–38×**（1200–3700%），
   远超 §4.2 的 10% 设计预算；解析值只可用于「量级不敏感」的占位。
③ **10% 设计预算未达标（诚实暴露）** —— 解析侧 1200–3700%、FDTD 跨网格 30–55%，
   两侧都超预算 ⇒ 「精确回填」**不成立**，只能交付「带不确定度的取数接口」。

耗时（实测 · 单点含 2 次 2D FDTD）：dl16 ≈ 2.7s · dl20 ≈ 6–9s · dl25 ≈ 18–21s ·
dl30 ≈ 95s（**dl30 不进 smoke**）。FDTD **不可在 P&R / 设计时跑** ⇒ 运行时走标定表。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# 常量 / 阈值
# ---------------------------------------------------------------------------
#: 交叉功率比饱和阈值：cf1 超过此值 ⇒ 双点差分不可用（asin 折叠 / winding）。
#: 与 `calibrate_kappa_grid.kappa_fdtd` 内部的 `c1 > 0.6` winding 判据同口径。
CF_SATURATION = 0.6

#: §4.2 U3 的设计预算（相对偏差）。用于**判定是否达标**（不用于放宽）。
UNCERTAINTY_BUDGET_REL = 0.10

#: smoke / 交互默认网格档（dl30 太慢，实测 95s，刻意排除）。
DEFAULT_DL_FACTORS: Tuple[int, ...] = (16, 20, 25)

#: 默认器件参数（与 D-37 / D-57 / D-60 同源）。
W_UM = 0.5
N_CORE = 3.48
N_CLAD = 1.44
WL_UM_DEFAULT = 1.55

#: 可信度定级
TRUST_OK = "ok"
TRUST_WINDING = "winding"          # 双点差分缠绕（c2<c1 或 c1>CF_SATURATION）
TRUST_CF_SATURATED = "cf_saturated"  # cf1 饱和，κ 被压成假小/假大
TRUST_NONFINITE = "nonfinite"

#: 诚实边界声明（smoke 断言其键存在，防被悄悄删掉）
RING_KAPPA_DISCLOSURE: Dict[str, Any] = {
    "scope": (
        "只做「2D FDTD 提取 κ_c(gap,λ) + 与解析经验模型比对 + 网格可信度量化」。"
        "不做 3D 仿真、不做环谱/器件级签核、不改任何 golden 或 tol。"
    ),
    "mesh_convergence_not_established": (
        "🔴 判据 D（响应残差严格单调下降）在本实现下**不成立**："
        "实测 gap=0.30 可信残差 [0.002210, 0.013622, 0.001282]、"
        "gap=0.25 为 [0.001680, 0.005019]，均非单调。"
        "⇒ 不声称「κ_c 已收敛」，只报跨网格离散度作为真实不确定度。"
    ),
    "root_cause_staircase_gap": (
        "非单调的根因 = 阶梯（pixel 化）离散的**有效 gap** 随 dl 非单调变化；"
        "而 κ_c 对 gap 呈指数敏感（L_ev≈0.1µm）⇒ 0.02µm 的有效 gap 误差即带来"
        "约 20% 的 κ_c 变化。这不是随机噪声，是**结构化离散误差**。"
    ),
    "analytic_is_placeholder": (
        "解析经验模型 gap_to_kappa（κ_ref=0.35 / L_ev=0.15µm / 与 λ 无关，D-37）"
        "与第一性原理 2D FDTD 标定相差 **13–38×**（即 1200–3700%），"
        "远超 10% 设计预算 ⇒ 它只是**占位上界**，不可用于量级敏感判决。"
    ),
    "budget_not_met": (
        "🔴 §4.2 U3 的「κ_c 相对解析值偏差 ≤10%」**未达标**：解析侧 1200–3700%、"
        "FDTD 跨网格离散度 30–55%（实测）。两侧都超预算 ⇒ 「精确回填」不成立；"
        "本模块交付的是**带不确定度的取数接口 + 不达标的事实**，不粉饰。"
    ),
    "no_3d_and_no_vertical_confinement": (
        "2D FDTD 无垂直（y 方向）限制，有效折射率口径与真实 SOI 220nm 器件不同 ⇒ "
        "绝对值系统性偏离 3D；本模块只用于**相对比较与趋势**，不当 3D 真值。"
    ),
    "fdtd_too_slow_for_runtime": (
        "FDTD 单点实测 2.7s(dl16) / 6–9s(dl20) / 18–21s(dl25) / 95s(dl30) "
        "⇒ **不可在 P&R / 设计时跑**；运行时只走标定表查询（kappa_grid_calibration.json）。"
    ),
}


class RingKappaCalibError(Exception):
    """参数越界 / 前置条件不满足（不是数值不达标）。"""


# ---------------------------------------------------------------------------
# 1. FDTD 网格序列（复用 D-60 提取，不重写数学）
# ---------------------------------------------------------------------------
def kappa_c_series(gap_um: float, wl_um: float = WL_UM_DEFAULT,
                   dl_factors: Sequence[int] = DEFAULT_DL_FACTORS,
                   w_um: float = W_UM, n_core: float = N_CORE,
                   n_clad: float = N_CLAD) -> Dict[str, Any]:
    """跑一列网格档的 FDTD κ_c（逐档复用 `calibrate_kappa_grid.kappa_fdtd`）。

    返回每档 `kappa_c_rad_um` / `cf1` / `cf2` / `winding` / `trusted` / `reason`
    与总体元数据。**不做收敛判定**（那是 `convergence_report` 的职责）。
    """
    if not (0.0 < gap_um <= 2.0):
        raise RingKappaCalibError("gap_um 越界（需 0<gap≤2µm）：%r" % (gap_um,))
    if not (1.0 <= wl_um <= 2.0):
        raise RingKappaCalibError("wl_um 越界（需 1≤λ≤2µm）：%r" % (wl_um,))
    if not dl_factors:
        raise RingKappaCalibError("dl_factors 为空")
    for d in dl_factors:
        if d < 2 or d > 80:
            raise RingKappaCalibError("dl_factor 越界（2..80）：%r" % (d,))

    from lda_agent.calibrate_kappa_grid import kappa_fdtd  # 局部导入（慢依赖）

    points: List[Dict[str, Any]] = []
    for dlf in dl_factors:
        k, c1, c2, winding = kappa_fdtd(gap_um, wl_um, dl_factor=int(dlf))
        trusted, reason = classify_trust(k, c1, c2, bool(winding))
        points.append({
            "dl_factor": int(dlf),
            "dl_um": round(1.55 / float(dlf), 5),
            "kappa_c_rad_um": float(k),
            "cf1": float(c1),
            "cf2": float(c2),
            "winding": bool(winding),
            "trusted": bool(trusted),
            "reason": reason,
        })
    return {
        "gap_um": float(gap_um),
        "wl_um": float(wl_um),
        "w_um": float(w_um),
        "n_core": float(n_core),
        "n_clad": float(n_clad),
        "dl_factors": [int(d) for d in dl_factors],
        "points": points,
        "n_points": len(points),
        "n_trusted": sum(1 for p in points if p["trusted"]),
    }


def classify_trust(kappa: float, cf1: float, cf2: float,
                   winding: bool) -> Tuple[bool, str]:
    """单点可信度判定（不依赖调用方解释 `winding` 标志）。"""
    if not (math.isfinite(kappa) and math.isfinite(cf1) and math.isfinite(cf2)):
        return False, TRUST_NONFINITE
    if not (0.0 < cf1 < 1.0) or not (0.0 < cf2 < 1.0):
        return False, TRUST_NONFINITE
    if winding:
        return False, TRUST_WINDING
    # 独立复核饱和：即便上游 winding=False，cf1 超阈也判不可信
    if cf1 > CF_SATURATION or cf2 > 0.995:
        return False, TRUST_CF_SATURATED
    if kappa <= 0.0:
        return False, TRUST_NONFINITE
    return True, TRUST_OK


# ---------------------------------------------------------------------------
# 2. 收敛 / 不确定度分析（核心：诚实报「不收敛」）
# ---------------------------------------------------------------------------
def convergence_report(series: Dict[str, Any]) -> Dict[str, Any]:
    """可信档序列的残差 + 离散度 + 收敛判定（判据 D 的**如实**报告）。

    - `residuals[i] = |κ_i − κ_{i+1}|`（仅可信档，按 dl 递增）
    - `monotone_decreasing_residual`：残差是否**严格单调下降**（判据 D）
    - `spread_rel`：跨可信档 `(max−min)/mean`，即**跨网格离散度**（真实不确定度）
    - `converged`：`monotone_decreasing_residual and spread_rel ≤ UNCERTAINTY_BUDGET_REL`
    - `finest_trusted_kappa`：最细可信档的 κ（**仍带离散度，非真值**）
    """
    trusted = [p for p in series["points"] if p["trusted"]]
    kappas = [p["kappa_c_rad_um"] for p in trusted]
    residuals = [abs(a - b) for a, b in zip(kappas, kappas[1:])]
    mono = all(x > y for x, y in zip(residuals, residuals[1:])) if len(residuals) >= 2 else None
    if kappas:
        mean = sum(kappas) / len(kappas)
        spread_abs = max(kappas) - min(kappas)
        spread_rel = spread_abs / mean if mean > 0 else float("inf")
    else:
        mean = spread_abs = 0.0
        spread_rel = float("inf")
    converged = bool(mono) and spread_rel <= UNCERTAINTY_BUDGET_REL
    reasons: List[str] = []
    if len(trusted) < 2:
        reasons.append("可信档不足 2（无法判收敛）")
    if mono is False:
        reasons.append("残差非严格单调下降（判据 D 不成立 ⇒ 不声称收敛）")
    if spread_rel > UNCERTAINTY_BUDGET_REL:
        reasons.append("跨网格离散度 %.1f%% > 预算 %.0f%%"
                       % (spread_rel * 100.0, UNCERTAINTY_BUDGET_REL * 100.0))
    return {
        "n_trusted": len(trusted),
        "trusted_dl_factors": [p["dl_factor"] for p in trusted],
        "trusted_kappas": kappas,
        "residuals": residuals,
        "monotone_decreasing_residual": mono,
        "mean_kappa": mean,
        "spread_abs": spread_abs,
        "spread_rel": spread_rel,
        "budget_rel": UNCERTAINTY_BUDGET_REL,
        "budget_met": bool(spread_rel <= UNCERTAINTY_BUDGET_REL),
        "converged": converged,
        "finest_trusted_kappa": kappas[-1] if kappas else None,
        "finest_trusted_dl_factor": trusted[-1]["dl_factor"] if trusted else None,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# 3. 解析模型对比（golden 位 = 占位，不是真值）
# ---------------------------------------------------------------------------
def analytic_kappa(gap_um: float) -> float:
    """解析经验模型 κ_c(gap)（**复用** D-37 `gap_to_kappa`，不重写公式）。"""
    from lda_agent.ring_adddrop import gap_to_kappa  # 局部导入
    return float(gap_to_kappa(gap_um))


def analytic_vs_fdtd(gap_um: float, kappa_fdtd: float) -> Dict[str, Any]:
    """解析占位 vs FDTD 的量化偏差（倍数 + 相对偏差）。"""
    ka = analytic_kappa(gap_um)
    if not (math.isfinite(kappa_fdtd) and kappa_fdtd > 0.0):
        raise RingKappaCalibError("kappa_fdtd 非正/非有限：%r" % (kappa_fdtd,))
    ratio = ka / kappa_fdtd
    return {
        "gap_um": float(gap_um),
        "analytic_kappa_rad_um": ka,
        "fdtd_kappa_rad_um": float(kappa_fdtd),
        "ratio_analytic_over_fdtd": ratio,
        "rel_dev_analytic_vs_fdtd": abs(ka - kappa_fdtd) / kappa_fdtd,
        "analytic_over_budget": bool(abs(ka - kappa_fdtd) / kappa_fdtd > UNCERTAINTY_BUDGET_REL),
        "note": ("解析模型是占位上界（13–38×，见 RING_KAPPA_DISCLOSURE）；"
                 "本字段只报偏差，不据此修改任何 golden/tol。"),
    }


# ---------------------------------------------------------------------------
# 4. 标定表查询（运行时路径：不跑 FDTD）
# ---------------------------------------------------------------------------
def kappa_c_from_table(gap_um: float, wl_um: float = WL_UM_DEFAULT,
                       grid_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """查已签发标定表 `kappa_grid_calibration.json`（复用 wdm_coupler 的双线性插值）。

    越界 ⇒ None（**不**回退去跑 FDTD —— 那会在设计路径里引入 ~10s 级延迟）。
    """
    import json
    import os
    from lda_agent.wdm_coupler import kappa_c_grid_interp  # 局部导入

    if grid_path is None:
        grid_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "lda_agent", "data",
                                 "kappa_grid_calibration.json")
        grid_path = os.path.normpath(grid_path)
    if not os.path.exists(grid_path):
        return None
    with open(grid_path, encoding="utf-8") as f:
        grid = json.load(f)
    k = kappa_c_grid_interp(grid, gap_um, wl_um)
    if k is None:
        return None
    return {
        "kappa_c_rad_um": float(k),
        "backend": "fdtd-table",
        "table_path": grid_path,
        "table_dl_factor": grid.get("dl_factor"),
        "table_gaps_um": grid.get("gaps_um"),
        "table_wls_um": grid.get("wls_um"),
        "uncertainty_rel": None,   # 表本身不带跨网格离散度 ⇒ 显式标 None
        "note": ("来自已签发标定表；该表为**单档网格**（无跨网格离散度字段），"
                 "真实不确定度须由 convergence_report 现算（30–55%，实测）。"),
    }


def kappa_c_lookup(gap_um: float, wl_um: float = WL_UM_DEFAULT,
                   backend: str = "analytic",
                   grid_path: Optional[str] = None) -> Dict[str, Any]:
    """统一取数入口。

    - `backend="analytic"`（**默认**，向后兼容）：解析经验模型（占位，快）
    - `backend="fdtd-table"`：查标定表（快，越界 ⇒ raise，不静默回退）
    """
    if backend == "analytic":
        ka = analytic_kappa(gap_um)
        return {"kappa_c_rad_um": ka, "backend": "analytic-placeholder",
                "uncertainty_rel": None,
                "note": "解析占位（与 FDTD 差 13–38×），仅用于非量级敏感路径。"}
    if backend == "fdtd-table":
        hit = kappa_c_from_table(gap_um, wl_um, grid_path)
        if hit is None:
            raise RingKappaCalibError(
                "gap=%.3f λ=%.3f 落在标定表外（不静默回退解析模型）；"
                "请先扩表或改用 backend='analytic'。" % (gap_um, wl_um))
        return hit
    raise RingKappaCalibError("未知 backend：%r（可选 analytic / fdtd-table）" % (backend,))


# ---------------------------------------------------------------------------
# 5. 微环锚回填（复用 wdm_ring_anchor 拿几何，替换 κ_c / k_ring）
# ---------------------------------------------------------------------------
def calibrated_ring_anchor(wl_nm: float, n_g: float = 2.45, m: int = 30,
                           gap: float = 0.3,
                           dl_factors: Sequence[int] = DEFAULT_DL_FACTORS
                           ) -> Dict[str, Any]:
    """微环物理锚的 **FDTD 标定版**：几何复用 `wdm_ring_anchor`，κ_c 换真值。

    🔴 会**真的跑 FDTD**（默认三档 ≈ 30s）⇒ 只用于标定 / 验证，
    **不得**放进 P&R 或 WebUI 请求路径。
    """
    from lda_layout.wdm_mesh_pnr import wdm_ring_anchor  # 局部导入（避免耦合）

    base = wdm_ring_anchor(wl_nm, n_g=n_g, m=m, gap=gap)
    wl_um = float(wl_nm) * 1e-3
    series = kappa_c_series(gap, wl_um, dl_factors=dl_factors)
    conv = convergence_report(series)
    kc_fdtd = conv["finest_trusted_kappa"]
    out: Dict[str, Any] = dict(base)
    out["kappa_backend"] = "fdtd-2d-calibrated"
    out["kappa_c_rad_um"] = round(float(kc_fdtd), 6) if kc_fdtd else None
    out["kappa_uncertainty_rel"] = round(conv["spread_rel"], 4)
    out["kappa_converged"] = conv["converged"]
    L_couple = base["L_couple_um"]
    out["k_ring"] = (round(math.sin(float(kc_fdtd) * L_couple), 6)
                     if kc_fdtd else 0.0)
    out["kappa_series"] = series["points"]
    out["kappa_convergence"] = {
        "residuals": conv["residuals"],
        "monotone_decreasing_residual": conv["monotone_decreasing_residual"],
        "spread_rel": conv["spread_rel"],
        "budget_met": conv["budget_met"],
        "reasons": conv["reasons"],
    }
    dev_txt = "n/a（无可信档）"
    if kc_fdtd:
        av = analytic_vs_fdtd(gap, float(kc_fdtd))
        out["analytic_vs_fdtd"] = av
        dev_txt = "%.1f×" % av["ratio_analytic_over_fdtd"]
    out["honest_note"] = (
        "几何（R/L_couple/FSR）与 wdm_ring_anchor 逐位同源；κ_c 取 2D FDTD 最细可信档，"
        "跨网格离散度 %.1f%%（§4.2 预算 %.0f%% ⇒ %s）；解析占位偏差 %s。"
        % (conv["spread_rel"] * 100.0, UNCERTAINTY_BUDGET_REL * 100.0,
           "达标" if conv["budget_met"] else "**未达标**", dev_txt)
    )
    return out


if __name__ == "__main__":       # pragma: no cover - 人工自测入口
    import json
    import time

    G, W = 0.30, 1.55
    t0 = time.time()
    ser = kappa_c_series(G, W)
    conv = convergence_report(ser)
    print("== U3 κ_c 网格序列（gap=%.2f µm · λ=%.2f µm）==" % (G, W))
    for p in ser["points"]:
        print("  dl_factor=%-3d dl=%.5f κ_c=%.6f cf1=%.3f cf2=%.3f winding=%-5s "
              "trusted=%-5s %s"
              % (p["dl_factor"], p["dl_um"], p["kappa_c_rad_um"], p["cf1"],
                 p["cf2"], p["winding"], p["trusted"], p["reason"]))
    print("  残差:", conv["residuals"],
          "严格单调下降:", conv["monotone_decreasing_residual"])
    print("  跨网格离散度: %.1f%%  budget(%.0f%%)_met=%s  converged=%s"
          % (conv["spread_rel"] * 100, UNCERTAINTY_BUDGET_REL * 100,
             conv["budget_met"], conv["converged"]))
    print("  不收敛理由:", conv["reasons"])
    print("  解析 vs FDTD:", json.dumps(analytic_vs_fdtd(G, conv["finest_trusted_kappa"]),
                                        ensure_ascii=False)[:220])
    print("  取数 analytic:", kappa_c_lookup(G)["kappa_c_rad_um"])
    print("  取数 table   :", (kappa_c_from_table(G, W) or {}).get("kappa_c_rad_um"))
    print("  耗时 %.1fs" % (time.time() - t0))
    print("诚实边界键:", sorted(RING_KAPPA_DISCLOSURE))
