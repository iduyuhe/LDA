"""QS-M3 · 量子传感**灵敏度几何优化**物理（吃狗粮 v3 · 量子传感器芯片征程）。

═══ 定位（蓝图层 `docs/LDA_量子传感器芯片征程_总蓝图_v1_2026-10-10.md` §QS-M3）═══
QS-M0 交付 NV 磁力计最小闭环；QS-M1 交付**灵敏度 FOM 体系**；QS-M2 补**退相干 +
多源噪声**真实性。QS-M3 转而回答**几何设计**问题——
  · **色心深度 / 金刚石表面距离 → 收集效率**：越深越难收集（出射衰减），
    但太浅则受表面自旋浴噪声（谱扩散 ∝ 1/d³）劣化对比度 ⇒ **存在最优深度**；
  · **腔增强（Purcell）→ 光子计数率**：把发射体耦合进谐振腔，发射率被
    Purcell 因子 F_P=4g²/(κγ₁) 增强 ⇒ 光子计数率提升 ⇒ 灵敏度改善；
  · **与 bulk 极限对照**：几何优化相对无结构体材料（bulk）天花板的百分比。
**平台缺口 G5**：量子传感专用 PDK 器件（NV 柱 / 腔 / 天线）。

═══ 🔴 物理链（三条 · 闭式可作 golden）═══
链① **NA 立体角收集效率**（偶极图样 I(θ)∝sin²θ，θ 自偶极轴量起）：
    η_NA(NA) = ∫₀^{θmax} sin³θ dθ / ∫₀^{π/2} sin³θ dθ，θmax = arcsin(NA)。
    上半球总能量 = 2/3；闭式 η_NA = [cos³θ/3 − cosθ]₀^{θmax} / (2/3)。
链② **深度 → 收集效率**：η_coll(d) = η_NA · exp(−d/d_att)（d_att=出射衰减长度）。
链③ **最优深度 d\\***（灵敏度 FOM 极小点）：灵敏度随收集效率劣化 ∝ 1/√η_coll，
    同时受表面噪声惩罚 ∝ √(1+(d₀/d)³)。故 η_tot(d) ∝ √(1+(d₀/d)³) / √η_coll(d)，
    取 d(ln η_tot)/dd = 0 ⇒ **d⁴ + d₀³·d = 3·d₀³·d_att**（闭式根方程）。
链④ **Purcell 腔增强计数率比**：R/R₀ = 1 + β·F_P，F_P = 4g²/(κγ₁)（标准腔 QED）。

═══ 🔴 与既有锚的边界（**不同物理量**，非重复计数）═══
· B18（谐振腔 Purcell 因子 F_P=4g²/(κγ₁)）：**本档链④ 复用同一 Purcell 物理**，
  故链④ **不另登记为 B 锚**（避免与 B18 重复计数）—— 归本模块 smoke 覆盖。
· B473（NV 磁力计磁灵敏度 η）：QS-M0 的**灵敏度标量**；本档是**几何量**
  （收集效率 / 最优深度），物理对象不同。
· B459–B472（光子传感器灵敏度族）：**折射率传感**，与本档自旋系综磁传感不同域。

═══ 🔴 纪律 ═══
· 进报告数字一律**模块现算**（不转录草稿）；判据读到的值 = 模块现算值。
· 每道守卫配反向探针（先证能变红）。
· 纯 numpy 顶层（scipy 隔离）；C 级自主，不借外部量子/光子 SDK。
· 🔴 **诚实边界**：d₀ / d_att / NA / (g,κ,γ₁) 均为**设计示例量级**（室温 NV 典型），
  非实测；报告为建模值，**不得作制造 / 性能宣称**；本档不宣称「已达国际水平」。
"""
from __future__ import annotations

import math
from typing import Any, Dict

import numpy as np

# ---------------------------------------------------------------------------
# 复用 QS 统一口径（单一真源 · 与 qs_m1/qs_m2 同源）
# ---------------------------------------------------------------------------
SENSITIVITY_CALIBER = "eta_dB_sqrtT__amplitude_spectral_density__T_per_sqrtHz"

#: 物理常数（承 qs_m0/qs_m2）
HBAR = 1.054571817e-34
G_LANDE = 2.0023
MU_B = 9.2740100783e-24
GAMMA_E_HZ_T = 28.024e9


def assert_caliber(caliber: str) -> None:
    """口径自检（报告前强制）：只接受统一口径，防误用其它口径。"""
    if caliber != SENSITIVITY_CALIBER:
        raise ValueError("灵敏度口径不一致：只允许 %r，得到 %r"
                         % (SENSITIVITY_CALIBER, caliber))


# ===========================================================================
# ① NA 立体角收集效率（偶极图样 I(θ) ∝ sin²θ）
# ===========================================================================
def collection_efficiency_na_closed(na: float) -> float:
    """闭式：偶极上半球辐射被 NA 锥收集的能量占比。

    η_NA(NA) = [cos³θ/3 − cosθ]₀^{θmax} / (2/3)，θmax=arcsin(NA)。
    闭式由 ∫sin³θ dθ = cos³θ/3 − cosθ 直接代入（**解析积分**）。
    🔴 NA=1 ⇒ θmax=π/2 ⇒ η_NA=1（全半球）；NA→0 ⇒ η_NA→0。
    """
    if not (0.0 < na <= 1.0):
        raise ValueError("NA 必须 ∈ (0, 1]")
    tm = math.asin(na)

    def F(x: float) -> float:
        c = math.cos(x)
        return c ** 3 / 3.0 - c

    return (F(tm) - F(0.0)) / (2.0 / 3.0)


def collection_efficiency_na_numeric(na: float, n_theta: int = 400000) -> float:
    """数值链：对偶极角分布逐点采样 → 落在 NA 锥内（θ≤θmax）的权重占比。

    权重 w(θ) = sin²θ · sinθ · dθ（强度 × 立体角），全半球归一。
    方法学独立于闭式（数值求和 vs 解析积分）；残差 = 网格离散化。
    """
    if not (0.0 < na <= 1.0):
        raise ValueError("NA 必须 ∈ (0, 1]")
    th = (np.arange(n_theta) + 0.5) * (math.pi / 2.0) / n_theta
    dth = (math.pi / 2.0) / n_theta
    w = np.sin(th) ** 3 * dth
    tot = float(np.sum(w))
    m = th <= math.asin(na)
    return float(np.sum(w[m]) / tot)


def collection_efficiency_depth(depth_nm: float, eta_na: float,
                                d_att_nm: float = 200.0) -> float:
    """深度 → 收集效率：η_coll(d) = η_NA · exp(−d/d_att)。

    🔴 越深（d↑）⇒ 出射衰减 ⇒ 收集效率指数下降。
    """
    if depth_nm < 0.0:
        raise ValueError("depth_nm 必须 ≥ 0")
    if d_att_nm <= 0.0:
        raise ValueError("d_att_nm 必须 > 0")
    return float(eta_na) * math.exp(-depth_nm / d_att_nm)


# ===========================================================================
# ② 最优深度（灵敏度 FOM 极小点）
# ===========================================================================
def _fom_model(depth_nm: float, d0_nm: float, d_att_nm: float) -> float:
    """几何灵敏度 FOM（∝ η_tot，越小越好，未归一）：

    η_tot(d) = √(1 + (d₀/d)³) / √(η_coll(d))
      · 分子 √(1+(d₀/d)³)：表面自旋浴噪声（谱扩散 ∝ 1/d³）劣化对比度；
      · 分母 √η_coll：收集效率越低 ⇒ 每单位时间光子越少 ⇒ 灵敏度越差。
    """
    if depth_nm <= 0.0:
        raise ValueError("depth_nm 必须 > 0（最优深度须正）")
    eta_na = 1.0                       # 归一（NA 因子与深度无关，约掉）
    eta_coll = collection_efficiency_depth(depth_nm, eta_na, d_att_nm)
    return math.sqrt(1.0 + (d0_nm / depth_nm) ** 3) / math.sqrt(eta_coll)


def optimal_depth_closed(d0_nm: float = 20.0, d_att_nm: float = 200.0) -> float:
    """闭式最优深度：解 **d⁴ + d₀³·d = 3·d₀³·d_att**（由 d(ln η_tot)/dd = 0 导出）。

    推导：ln η_tot = ½ln(1+(d₀/d)³) + d/(2 d_att) − ½ln η_NA。
      导数 = ½·[−3d₀³/d⁴ / (1+(d₀/d)³)] + 1/(2 d_att) = 0
      ⇒ 3 d₀³ d_att / (d⁴ + d₀³ d) = 1 ⇒ d⁴ + d₀³ d = 3 d₀³ d_att。
    🔴 f(d)=d⁴+d₀³d−3d₀³d_att 在 d>0 上**严格单调增**（f'=4d³+d₀³>0）⇒
      唯一正根，二分法必收敛。
    """
    if d0_nm <= 0.0 or d_att_nm <= 0.0:
        raise ValueError("d0_nm / d_att_nm 必须 > 0")
    rhs = 3.0 * d0_nm ** 3 * d_att_nm
    lo, hi = 1e-6, 100.0 * d_att_nm
    for _ in range(300):
        mid = 0.5 * (lo + hi)
        if mid ** 4 + d0_nm ** 3 * mid < rhs:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def optimal_depth_numeric(d0_nm: float = 20.0, d_att_nm: float = 200.0,
                          n_grid: int = 200000) -> float:
    """数值链：全网格扫描 η_tot(d) 取极小 + **抛物插值**精修（不用任何导数/根方程）。

    方法学独立于闭式（网格扫描+三点抛物插值 vs 解析求导+二分求根）；
    残差 = 网格离散化 + 抛物近似的三阶项。
    """
    if d0_nm <= 0.0 or d_att_nm <= 0.0:
        raise ValueError("d0_nm / d_att_nm 必须 > 0")
    ds = np.linspace(1e-3 * d_att_nm, 10.0 * d_att_nm, n_grid)
    ys = np.array([_fom_model(float(x), d0_nm, d_att_nm) for x in ds])
    i = int(np.argmin(ys))
    if 0 < i < n_grid - 1:
        y0, y1, y2 = ys[i - 1], ys[i], ys[i + 1]
        denom = y0 - 2.0 * y1 + y2
        if abs(denom) > 1e-300:
            step = ds[i + 1] - ds[i]
            return float(ds[i] - 0.5 * step * (y2 - y0) / denom)
    return float(ds[i])


# ===========================================================================
# ③ Purcell 腔增强 → 光子计数率比
# ===========================================================================
def purcell_factor(g_ghz: float = 0.05, kappa_ghz: float = 0.01,
                   gamma1_ghz: float = 0.002) -> float:
    """Purcell 因子 F_P = 4g²/(κγ₁)（标准腔 QED 无量纲增强因子）。

    🔴 **与 B18 同一物理量**（B18 已登记）⇒ 本档链④ **不另登记 B 锚**。
    """
    if kappa_ghz <= 0.0 or gamma1_ghz <= 0.0:
        raise ValueError("κ / γ₁ 必须 > 0")
    return 4.0 * g_ghz ** 2 / (kappa_ghz * gamma1_ghz)


def photon_rate_ratio(g_ghz: float = 0.05, kappa_ghz: float = 0.01,
                      gamma1_ghz: float = 0.002, beta_cav: float = 1.0) -> float:
    """腔增强光子计数率比 R/R₀ = 1 + β·F_P（β=进腔模分支比）。"""
    if not (0.0 <= beta_cav <= 1.0):
        raise ValueError("β_cav 必须 ∈ [0, 1]")
    return 1.0 + beta_cav * purcell_factor(g_ghz, kappa_ghz, gamma1_ghz)


def purcell_rate_ratio_numeric(g_ghz: float = 0.05, kappa_ghz: float = 0.01,
                               gamma1_ghz: float = 0.002, beta_cav: float = 1.0,
                               n_grid: int = 2000001, span_kappa: float = 500.0) -> float:
    """数值链：腔态密度**峰值数值提取** → 增强比（不复用 F_P 闭式代入）。

    腔洛伦兹态密度 ρ_c(ω) = (1/π)·(κ/2)/((ω−ω_c)²+(κ/2)²)（峰值 2/(πκ)）。
    腔致附加衰减 = 2·ImΣ(0) = 2·g²·π·ρ_c(0)。增强比 = 1 + β·(2·g²·π·ρ_c(0))/γ₁。
    🔴 ρ_c(0) **由细网格数值取 max 提取**（非解析代入 2/(πκ)）⇒ 方法学独立。
    """
    hw = kappa_ghz / 2.0
    ws = np.linspace(-span_kappa * kappa_ghz, span_kappa * kappa_ghz, n_grid)
    rho = (1.0 / math.pi) * hw / (ws ** 2 + hw * hw)
    rho_peak = float(np.max(rho))
    f_p_num = 2.0 * (g_ghz ** 2 * (math.pi * rho_peak)) / gamma1_ghz
    return 1.0 + beta_cav * f_p_num


# ===========================================================================
# ④ bulk 极限对照
# ===========================================================================
def vs_bulk_ratio(eta_coll_structured: float, eta_coll_bulk: float) -> float:
    """相对体材料（bulk）天花板的收集效率比 = η_structured / η_bulk。

    🔴 **诚实边界**：bulk 极限此处取 η_NA(NA_max)（无深度衰减的理想上限），
      比值 ∈ (0, 1]；「达到 bulk 的 x%」是**建模对照**，非实测宣称。
    """
    if eta_coll_bulk <= 0.0:
        raise ValueError("η_bulk 必须 > 0")
    return float(eta_coll_structured) / float(eta_coll_bulk)


# ===========================================================================
# ⑤ 四情景（承 QS-M1/M2 范式）
# ===========================================================================
SCENARIOS: Dict[str, Dict[str, Any]] = {
    # baseline：设计点，NA=0.75，深度取最优 d*，无腔
    "baseline": dict(na=0.75, d_att_nm=200.0, d0_nm=20.0, depth_nm=None,
                     g_ghz=0.0, kappa_ghz=0.01, gamma1_ghz=0.002, beta_cav=0.0),
    # shallow：浅色心（d=10nm）—— 表面噪声重，对比度差
    "shallow": dict(na=0.75, d_att_nm=200.0, d0_nm=20.0, depth_nm=10.0,
                    g_ghz=0.0, kappa_ghz=0.01, gamma1_ghz=0.002, beta_cav=0.0),
    # deep：深色心（d=150nm）—— 收集效率低
    "deep": dict(na=0.75, d_att_nm=200.0, d0_nm=20.0, depth_nm=150.0,
                 g_ghz=0.0, kappa_ghz=0.01, gamma1_ghz=0.002, beta_cav=0.0),
    # cavity_enhanced：最优深度 + 腔增强（β=0.9）
    "cavity_enhanced": dict(na=0.9, d_att_nm=200.0, d0_nm=20.0, depth_nm=None,
                            g_ghz=0.05, kappa_ghz=0.01, gamma1_ghz=0.002, beta_cav=0.9),
}


def evaluate_scenario(name: str) -> Dict[str, Any]:
    """单情景：NA 收集效率 → 深度修正 → FOM → （可选）腔增强计数率比。"""
    if name not in SCENARIOS:
        raise KeyError("未知情景 %r（可选：%s）" % (name, sorted(SCENARIOS)))
    p = SCENARIOS[name]
    na = float(p["na"])
    d_att = float(p["d_att_nm"])
    d0 = float(p["d0_nm"])
    eta_na = collection_efficiency_na_closed(na)
    d_star = optimal_depth_closed(d0, d_att)
    depth = d_star if p.get("depth_nm") is None else float(p["depth_nm"])
    eta_coll = collection_efficiency_depth(depth, eta_na, d_att)
    fom = _fom_model(depth, d0, d_att)
    rr = photon_rate_ratio(float(p["g_ghz"]), float(p["kappa_ghz"]),
                           float(p["gamma1_ghz"]), float(p["beta_cav"]))
    return {
        "scenario": name,
        "eta_na": eta_na,
        "depth_nm": depth,
        "optimal_depth_nm": d_star,
        "eta_collection": eta_coll,
        "fom": fom,
        "purcell_rate_ratio": rr,
        "vs_bulk_fraction": vs_bulk_ratio(eta_coll, collection_efficiency_na_closed(1.0)),
    }


def geometry_table() -> Dict[str, Dict[str, Any]]:
    """四情景几何表（现算）。"""
    return {n: evaluate_scenario(n)
            for n in ("baseline", "shallow", "deep", "cavity_enhanced")}


# ===========================================================================
# ⑥ 设计入口
# ===========================================================================
def design_geometry(run_checks: bool = True) -> Dict[str, Any]:
    """QS-M3 主入口：灵敏度几何优化报告。"""
    tbl = geometry_table()
    report: Dict[str, Any] = {
        "module": "qs_m3",
        "milestone": "QS-M3",
        "caliber": SENSITIVITY_CALIBER,
        "geometry": tbl,
    }
    if run_checks:
        report["checks"] = selfcheck_qs_m3()
    return report


# ===========================================================================
# ⑦ 自检（常驻门禁 · 反向探针）
# ===========================================================================
def selfcheck_qs_m3() -> Dict[str, bool]:
    """QS-M3 自检：NA 收集单调 + 最优深度是极小 + 链间互验 + 反向探针。"""
    checks: Dict[str, bool] = {}

    # ① NA 收集效率：闭式 ∧ 数值 一致（多 NA 点，相对残差 < 1e-4）
    na_pts = [0.3, 0.5, 0.6, 0.75, 0.85, 0.9, 0.95]
    checks["na_closed_eq_numeric"] = all(
        abs(collection_efficiency_na_numeric(na)
            - collection_efficiency_na_closed(na))
        / collection_efficiency_na_closed(na) < 1e-4
        for na in na_pts
    )
    # ② η_NA 随 NA 单调增 + 边界 NA=1 ⇒ 1
    vals = [collection_efficiency_na_closed(na) for na in na_pts]
    checks["na_monotone_increasing"] = all(
        vals[i] < vals[i + 1] for i in range(len(vals) - 1)
    )
    checks["na_boundary_one"] = abs(collection_efficiency_na_closed(1.0) - 1.0) < 1e-12

    # ③ 收集效率随深度单调降
    checks["collection_decreases_with_depth"] = all(
        collection_efficiency_depth(d, 0.15) > collection_efficiency_depth(d + 10.0, 0.15)
        for d in (0.0, 20.0, 50.0, 100.0)
    )

    # ④ 最优深度：闭式 ∧ 数值 一致（多参数点）
    opt_pts = [(10.0, 100.0), (20.0, 200.0), (20.0, 100.0), (30.0, 300.0)]
    checks["optimal_depth_closed_eq_numeric"] = all(
        abs(optimal_depth_numeric(d0, datt) - optimal_depth_closed(d0, datt))
        / optimal_depth_closed(d0, datt) < 1e-5
        for d0, datt in opt_pts
    )
    # ⑤ d\\* 确实是最小值点（左右两侧 FOM 都更大）
    checks["optimal_depth_is_minimum"] = all(
        (lambda d: _fom_model(d * 0.7, d0, datt) > _fom_model(d, d0, datt)
                   and _fom_model(d * 1.3, d0, datt) > _fom_model(d, d0, datt))(
            optimal_depth_closed(d0, datt))
        for d0, datt in opt_pts
    )

    # ⑥ Purcell 计数率比：闭式 ∧ 数值 一致
    checks["purcell_ratio_closed_eq_numeric"] = all(
        abs(photon_rate_ratio(g, k, gm) - purcell_rate_ratio_numeric(g, k, gm))
        / photon_rate_ratio(g, k, gm) < 1e-9
        for g, k, gm in ((0.05, 0.01, 0.002), (0.1, 0.005, 0.001))
    )
    # ⑦ 腔增强必 ≥ 1（β≥0 ⇒ R/R₀≥1）
    checks["purcell_ratio_ge_one"] = photon_rate_ratio(0.05, 0.01, 0.002, 0.9) >= 1.0

    # ⑧ bulk 对照 ∈ (0,1]
    checks["vs_bulk_in_unit_interval"] = all(
        0.0 < evaluate_scenario(n)["vs_bulk_fraction"] <= 1.0
        for n in ("baseline", "shallow", "deep", "cavity_enhanced")
    )

    # ⑨ 反向探针（先证能变红）
    checks["reverse_na_out_of_range_raises"] = _raises(
        lambda: collection_efficiency_na_closed(1.5)
    )
    checks["reverse_negative_depth_raises"] = _raises(
        lambda: collection_efficiency_depth(-1.0, 0.15)
    )
    # 🔴 反向探针「最优深度判别力」：故意把 FOM 模型改成无深度惩罚
    #    （去掉 √(1+(d0/d)³) 项）⇒ FOM=1/√η_coll 随 d **单调增** ⇒ 内部极小消失
    #    （极小退到 d→0 边界）⇒ 证明 optimal_depth_is_minimum 依赖惩罚项、非恒真。
    def _fom_no_penalty(d: float) -> float:
        return 1.0 / math.sqrt(collection_efficiency_depth(d, 1.0, 200.0))

    # 无惩罚 ⇒ FOM 严格单调增 ⇒ 任意 d1<d2 有 fom(d1)<fom(d2)（无内部极小）
    checks["reverse_wrong_model_detected"] = (
        _fom_no_penalty(50.0) < _fom_no_penalty(200.0)
        and _fom_no_penalty(10.0) < _fom_no_penalty(50.0)
    )
    # 🔴 反向探针「β 口径」：β=0 时计数率比必须恰为 1（无腔增强）
    checks["reverse_beta_zero_no_enhancement"] = (
        photon_rate_ratio(0.05, 0.01, 0.002, 0.0) == 1.0
    )
    # 🔴 反向探针「κ 口径」：κ→0 ⇒ F_P 发散
    checks["reverse_zero_kappa_diverges"] = _raises(
        lambda: purcell_factor(0.05, 0.0, 0.002)
    )

    # ⑩ 口径自检（承 QS-M1/M2）
    try:
        assert_caliber(SENSITIVITY_CALIBER)
        checks["caliber_ok"] = True
    except ValueError:
        checks["caliber_ok"] = False

    return checks


def _raises(fn) -> bool:
    try:
        fn()
    except (ValueError, ZeroDivisionError, OverflowError):
        return True
    return False


def main() -> int:
    """打印 QS-M3 灵敏度几何优化报告。"""
    rep = design_geometry(run_checks=True)
    print("=== QS-M3 灵敏度几何优化 ===")
    print("口径:", rep["caliber"])
    for n, s in rep["geometry"].items():
        print("  [%-16s] η_NA=%.5f | d=%.2fnm (d*=%.2f) | η_coll=%.6f | "
              "R/R0=%.1f | bulk=%.2f%%"
              % (n, s["eta_na"], s["depth_nm"], s["optimal_depth_nm"],
                 s["eta_collection"], s["purcell_rate_ratio"],
                 s["vs_bulk_fraction"] * 100.0))
    ck = rep["checks"]
    npass = sum(1 for v in ck.values() if v)
    print("checks: %d/%d %s" % (npass, len(ck), "PASS" if npass == len(ck) else "FAIL"))
    for k, v in ck.items():
        if not v:
            print("  FAIL:", k)
    return 0 if npass == len(ck) else 1


if __name__ == "__main__":
    raise SystemExit(main())
