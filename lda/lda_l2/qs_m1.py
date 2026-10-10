"""QS-M1 · 量子传感**灵敏度 FOM 体系**（吃狗粮 v2 · 量子传感器芯片征程）。

═══ 定位（蓝图层 `docs/LDA_量子传感器芯片征程_总蓝图_v1_2026-10-10.md` §4）═══
QS-M0 已交付 **NV 色心磁力计最小闭环**（自旋哈密顿量 → Ramsey 响应 → 散粒极限 η）。
QS-M1 把「灵敏度」从**单个标量**升级为**可比较的 FOM 体系**：统一口径、四情景、
逐项溯源。**平台缺口 G3**：量子传感指标求解与报告（**避免 PS 征程的「指标从零建」血案**）。

═══ 🔴 统一口径（红线 · 全征程唯一）═══
  · **η = δB·√T**，单位 T·Hz^(-1/2)（白噪声**幅度谱密度**）。
  · 严禁与「线宽受限 LOD」（单位 T，单点分辨力）混比——PS 征程血案：两口径混比
    ⇒ 余量判断反向。本模块以 `SENSITIVITY_CALIBER` 常量为**单一真源**，
    `assert_caliber()` 在报告前强制自检。
  · 逐项标注条件（室温/低温、AC/DC、单点/阵列）——本档全为**室温 · DC · 单点**。

═══ 🔴 FOM 体系（三条独立可测量 → 散粒噪声极限）═══
量子磁力计的灵敏度由三条**可直接测量**的 FOM 决定：
  ① 对比度 C        —— Ramsey 条纹幅度（无量纲，0<C≤1）
  ② 线宽 δf         —— 频域高斯宽度 σ_f = √2/(2πT₂*)（Hz）
  ③ 光子计数率 n_ph —— 荧光光子率（光子数/秒）
散粒极限 η = ħ/(gμB)·√(1+a²)·√2/(C·√(n_ph·T₂*))，其中 T₂* = √2/(2π·σ_f)（由②反解）。
本档**同时**给出「T₂* 路径」与「线宽路径」两条独立算法，互为方法学验证（见 B474）。

═══ 🔴 四情景（baseline / cited / degraded / bench）═══
  · baseline：QS-M0 设计点（T₂*=1µs / C=0.03 / n_ph=1e5），本征散粒极限；
  · cited   ：取**公开发表的 NV 集合体典型量级**（作对标准星，非 LDA 实测）；
  · degraded：含未建模降级因子（微波功率展宽 / 磁场不均匀）→ 真实灵敏度劣化；
  · bench   ：单调性/反向探针场景（零对比度 ⇒ η→∞；零光子率 ⇒ η→∞）。

═══ 🔴 纪律 ═══
· 进报告数字一律**模块现算**（不转录草稿）；判据读到的值 = 模块现算值。
· 每道守卫配反向探针（先证能变红）。
· 纯 numpy 顶层（scipy 隔离）；C 级自主，不借外部量子 SDK。
· 🔴 **诚实边界**：本档为**闭式散粒极限建模值**，非实测、非制造宣称；
  真实灵敏度受微波功率展宽、磁场不均匀、表象噪声等**未建模**因素降级。
"""
from __future__ import annotations

import math
from typing import Any, Dict

# ---------------------------------------------------------------------------
# 物理常数（与 qs_m0 / _batch_b39_numeric 同源）
# ---------------------------------------------------------------------------
HBAR = 1.054571817e-34
G_LANDE = 2.0023
MU_B = 9.2740100783e-24
GAMMA_E_HZ_T = 28.024e9

_G_MUB_OVER_HBAR = G_LANDE * MU_B / HBAR       # rad·s⁻¹·T⁻¹ (= 2π·γe)

#: 🔴 统一灵敏度口径（全征程唯一真源）——白噪声幅度谱密度 T·Hz^(-1/2)
SENSITIVITY_CALIBER = "eta_dB_sqrtT__amplitude_spectral_density__T_per_sqrtHz"

#: 本档测量条件（逐项标注，禁不标注）
MEASUREMENT_CONDITIONS = {
    "temperature": "room_temperature_300K",
    "field_mode": "DC",
    "channel": "single_channel",
    "normalization": "per_sqrtHz",
}


def assert_caliber(caliber: str) -> None:
    """口径自检（报告前强制）：只接受统一口径常量，防「线宽受限 LOD」混比。"""
    if caliber != SENSITIVITY_CALIBER:
        raise ValueError(
            "灵敏度口径不一致：只允许 %r，得到 %r（禁与线宽受限 LOD 混比）"
            % (SENSITIVITY_CALIBER, caliber)
        )


# ---------------------------------------------------------------------------
# ① FOM 定义：三条独立可测量量的数据结构
# ---------------------------------------------------------------------------
def fom_from_linewidth(linewidth_hz: float) -> Dict[str, float]:
    """② 线宽 FOM → 等效 T₂*（高斯包络反解）。

    高斯对比度包络 C(τ)=C₀·e^(−(τ/T₂*)²) 的**频域**高斯宽度 σ_f = √2/(2π·T₂*)。
    反解：T₂* = √2/(2π·σ_f)。
    """
    if linewidth_hz <= 0.0:
        raise ValueError("线宽必须 > 0（σ_f ≤ 0 无物理意义）")
    T2star_s = math.sqrt(2.0) / (2.0 * math.pi * linewidth_hz)
    return {"linewidth_hz": linewidth_hz, "T2star_s": T2star_s}


def fom_from_T2star(T2star_s: float) -> Dict[str, float]:
    """② 线宽 FOM ← T₂*（正解，与本模块 golden 同源）。"""
    if T2star_s <= 0.0:
        raise ValueError("T₂* 必须 > 0")
    return {"T2star_s": T2star_s,
            "linewidth_hz": math.sqrt(2.0) / (2.0 * math.pi * T2star_s)}


# ---------------------------------------------------------------------------
# ③ 灵敏度（统一口径 η = δB·√T）——T₂* 路径（金标闭式）
# ---------------------------------------------------------------------------
def sensitivity_via_T2star(T2star_s: float, n_ph_per_s: float, contrast: float,
                           dark_ratio: float = 0.0) -> Dict[str, float]:
    """T₂* 路径散粒极限：η = ħ/(gμB)·√(1+a²)·√2/(C·√(n_ph·T₂*))（T/√Hz）。

    （与 qs_m0.sensitivity_shot_limit_closed 同式；本模块独立重列以便 FOM 体系自洽。）
    """
    assert_caliber(SENSITIVITY_CALIBER)
    eta = (math.sqrt(1.0 + dark_ratio ** 2) * math.sqrt(2.0)
           / (contrast * math.sqrt(n_ph_per_s * T2star_s))
           / _G_MUB_OVER_HBAR)
    return {
        "eta_T_per_sqrtHz": eta,
        "eta_pT_per_sqrtHz": eta * 1e12,
        "caliber": SENSITIVITY_CALIBER,
        "T2star_s": T2star_s,
    }


# ---------------------------------------------------------------------------
# ③' 灵敏度——线宽路径（方法学独立：从②的 σ_f 反解 T₂* 再合成）
# ---------------------------------------------------------------------------
def sensitivity_via_linewidth(linewidth_hz: float, n_ph_per_s: float,
                              contrast: float, dark_ratio: float = 0.0) -> Dict[str, float]:
    """线宽路径散粒极限（**物理量不同**：以频域线宽 σ_f 为输入 FOM）。

    η = ħ/(gμB)·√(1+a²)·√2/(C·√(n_ph·T₂*))，其中 T₂* = √2/(2π·σ_f)。
    代入得等价闭式：η = √(1+a²)·√2·√(2π·σ_f/(√2·n_ph))/(C·gμB)。
    """
    assert_caliber(SENSITIVITY_CALIBER)
    lw = fom_from_linewidth(linewidth_hz)
    T2star_s = lw["T2star_s"]
    eta = (math.sqrt(1.0 + dark_ratio ** 2) * math.sqrt(2.0)
           * math.sqrt(2.0 * math.pi * linewidth_hz / (math.sqrt(2.0) * n_ph_per_s))
           / (contrast * _G_MUB_OVER_HBAR))
    return {
        "eta_T_per_sqrtHz": eta,
        "eta_pT_per_sqrtHz": eta * 1e12,
        "caliber": SENSITIVITY_CALIBER,
        "linewidth_hz": linewidth_hz,
        "T2star_s": T2star_s,
    }


# ---------------------------------------------------------------------------
# ④ 四情景
# ---------------------------------------------------------------------------
SCENARIOS: Dict[str, Dict[str, Any]] = {
    # baseline：QS-M0 设计点（室温 NV 集合体典型量级，本征散粒极限）
    "baseline": dict(T2star_us=1.0, n_ph_per_s=1.0e5, contrast=0.03, dark_ratio=0.0),
    # cited：公开发表的 NV 集合体**典型量级**（作对标准星；非 LDA 实测）
    #   T₂*~1–10 µs、C~1–10%、n_ph~1e5–1e6/s（室温集合体 Ramsey 文献量级）
    "cited": dict(T2star_us=10.0, n_ph_per_s=1.0e6, contrast=0.10, dark_ratio=0.0),
    # degraded：含未建模降级（微波功率展宽 + 磁场不均匀 → 有效 T₂*、C 双降）
    "degraded": dict(T2star_us=0.1, n_ph_per_s=1.0e4, contrast=0.01, dark_ratio=0.05),
    # bench：反向探针专用（单调性/极限行为），非真实设计点
    "bench": dict(T2star_us=1.0, n_ph_per_s=1.0e5, contrast=0.03, dark_ratio=0.0),
}


def _scenario_params(scn: Dict[str, Any]) -> Dict[str, float]:
    return {
        "T2star_s": float(scn["T2star_us"]) * 1e-6,
        "n_ph_per_s": float(scn["n_ph_per_s"]),
        "contrast": float(scn["contrast"]),
        "dark_ratio": float(scn.get("dark_ratio", 0.0)),
    }


def evaluate_scenario(name: str) -> Dict[str, Any]:
    """对单个情景：T₂* 路径 + 线宽路径**双算**，返回一致性 + 结果。"""
    if name not in SCENARIOS:
        raise KeyError("未知情景 %r（可选：%s）" % (name, sorted(SCENARIOS)))
    p = _scenario_params(SCENARIOS[name])
    r_t2 = sensitivity_via_T2star(**p)
    lw = fom_from_T2star(p["T2star_s"])["linewidth_hz"]
    r_lw = sensitivity_via_linewidth(lw, p["n_ph_per_s"], p["contrast"], p["dark_ratio"])
    eta_a = r_t2["eta_T_per_sqrtHz"]
    eta_b = r_lw["eta_T_per_sqrtHz"]
    rel = abs(eta_a - eta_b) / eta_a if eta_a > 0 else float("inf")
    return {
        "scenario": name,
        "params": p,
        "linewidth_hz": lw,
        "eta_T_per_sqrtHz__T2star_path": eta_a,
        "eta_T_per_sqrtHz__linewidth_path": eta_b,
        "eta_pT_per_sqrtHz": eta_a * 1e12,
        "rel_two_paths": rel,
        "caliber": SENSITIVITY_CALIBER,
        "conditions": dict(MEASUREMENT_CONDITIONS),
    }


def fom_table() -> Dict[str, Dict[str, Any]]:
    """四情景 FOM 汇总表（现算）。"""
    return {n: evaluate_scenario(n) for n in ("baseline", "cited", "degraded", "bench")}


# ---------------------------------------------------------------------------
# ⑤ 设计入口（与 PS-M2 / QS-M0 同构）
# ---------------------------------------------------------------------------
def design_fom_system(run_checks: bool = True) -> Dict[str, Any]:
    """QS-M1 主入口：灵敏度 FOM 体系报告（四情景 + 单调性 + 反向探针）。"""
    table = fom_table()
    report: Dict[str, Any] = {
        "module": "qs_m1",
        "milestone": "QS-M1",
        "caliber": SENSITIVITY_CALIBER,
        "conditions": dict(MEASUREMENT_CONDITIONS),
        "scenarios": table,
    }
    if run_checks:
        report["checks"] = selfcheck_qs_m1()
    return report


# ---------------------------------------------------------------------------
# ⑥ 自检（常驻门禁 · 反向探针）
# ---------------------------------------------------------------------------
def selfcheck_qs_m1() -> Dict[str, bool]:
    """QS-M1 自检：口径自检 + 双路径一致 + 四情景单调性 + 反向探针（先证能变红）。"""
    checks: Dict[str, bool] = {}

    # ① 口径自检：统一口径通过
    try:
        assert_caliber(SENSITIVITY_CALIBER)
        checks["caliber_ok"] = True
    except ValueError:
        checks["caliber_ok"] = False
    # ①' 口径反向探针：混入「线宽受限 LOD」口径必须被拒
    try:
        assert_caliber("linewidth_limited_LOD__T")
        checks["caliber_rejects_wrong"] = False       # 未抛异常 = 守卫失效
    except ValueError:
        checks["caliber_rejects_wrong"] = True

    # ② 双路径一致：四情景 T₂* 路径 ↔ 线宽路径 rel < 1e-9
    table = fom_table()
    checks["two_paths_consistent"] = all(
        table[n]["rel_two_paths"] < 1e-9 for n in table
    )

    # ③ 单调性：T₂* ↑ ⇒ η ↓；C ↑ ⇒ η ↓；n_ph ↑ ⇒ η ↓
    e_t2_1 = sensitivity_via_T2star(1e-6, 1e5, 0.03)["eta_T_per_sqrtHz"]
    e_t2_2 = sensitivity_via_T2star(1e-5, 1e5, 0.03)["eta_T_per_sqrtHz"]
    checks["monotone_T2star"] = e_t2_2 < e_t2_1
    e_c1 = sensitivity_via_T2star(1e-6, 1e5, 0.01)["eta_T_per_sqrtHz"]
    e_c2 = sensitivity_via_T2star(1e-6, 1e5, 0.10)["eta_T_per_sqrtHz"]
    checks["monotone_contrast"] = e_c2 < e_c1
    e_n1 = sensitivity_via_T2star(1e-6, 1e4, 0.03)["eta_T_per_sqrtHz"]
    e_n2 = sensitivity_via_T2star(1e-6, 1e6, 0.03)["eta_T_per_sqrtHz"]
    checks["monotone_photonrate"] = e_n2 < e_n1

    # ④ 情景序：degraded 应**劣于** baseline（η 更大）
    checks["degraded_worse_than_baseline"] = (
        table["degraded"]["eta_T_per_sqrtHz__T2star_path"]
        > table["baseline"]["eta_T_per_sqrtHz__T2star_path"]
    )
    # ④' cited 应优于 baseline（更好的 T₂*/C/n_ph ⇒ η 更小）
    checks["cited_better_than_baseline"] = (
        table["cited"]["eta_T_per_sqrtHz__T2star_path"]
        < table["baseline"]["eta_T_per_sqrtHz__T2star_path"]
    )

    # ⑤ 反向探针（先证能变红）：
    #   零对比度 ⇒ η → ∞（散粒噪声发散）
    checks["reverse_zero_contrast_diverges"] = _diverges(
        lambda: sensitivity_via_T2star(1e-6, 1e5, 0.0)["eta_T_per_sqrtHz"]
    )
    #   零光子率 ⇒ η → ∞
    checks["reverse_zero_photonrate_diverges"] = _diverges(
        lambda: sensitivity_via_T2star(1e-6, 0.0, 0.03)["eta_T_per_sqrtHz"]
    )
    #   零线宽 ⇒ ValueError（无物理意义）
    try:
        fom_from_linewidth(0.0)
        checks["reverse_zero_linewidth_raises"] = False
    except ValueError:
        checks["reverse_zero_linewidth_raises"] = True

    # ⑥ 暗计数只会**劣化**（a>0 ⇒ η 更大）
    e_a0 = sensitivity_via_T2star(1e-6, 1e5, 0.03, 0.0)["eta_T_per_sqrtHz"]
    e_a1 = sensitivity_via_T2star(1e-6, 1e5, 0.03, 0.5)["eta_T_per_sqrtHz"]
    checks["dark_ratio_degrades"] = e_a1 > e_a0

    return checks


def _diverges(fn) -> bool:
    """调用 fn 并判断结果是否发散（inf/nan/极大）。"""
    try:
        v = fn()
    except (ZeroDivisionError, ValueError):
        return True
    return not math.isfinite(v) or v > 1e30


def main() -> int:
    """打印 QS-M1 FOM 体系报告。"""
    rep = design_fom_system(run_checks=True)
    print("=== QS-M1 灵敏度 FOM 体系 ===")
    print("口径:", rep["caliber"])
    print("条件:", rep["conditions"])
    for n, s in rep["scenarios"].items():
        print("  [%s] eta = %.4f pT/sqrtHz  (T2*=%.3g s, C=%.3g, n_ph=%.3g/s, rel_2paths=%.2e)"
              % (n, s["eta_pT_per_sqrtHz"], s["params"]["T2star_s"],
                 s["params"]["contrast"], s["params"]["n_ph_per_s"], s["rel_two_paths"]))
    npass = sum(1 for v in rep["checks"].values() if v)
    ntot = len(rep["checks"])
    print("checks: %d/%d PASS" % (npass, ntot))
    for k, v in rep["checks"].items():
        if not v:
            print("  FAIL:", k)
    return 0 if npass == ntot else 1


if __name__ == "__main__":
    raise SystemExit(main())
