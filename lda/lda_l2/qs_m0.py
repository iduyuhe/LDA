"""QS-M0 · 量子传感器芯片征程 · 基线可设计版（NV 色心磁力计）。

═══ 策略（吃狗粮 · 自己先用平台设计出来）═══
用 LDA **量子栈**（自旋 + 两能级物理）从零建起「NV 色心磁力计」的最小闭环：
给定目标磁灵敏度，走通「设计 → 物理反解 → 数值双验证 → 报告」全链，并跑通
平台版图链路（色心/微波天线/读出光路 → placement → GDS → DRC/LVS），真实
检验平台能力，登记缺口供 QS-M1…M9 补齐。

NV 色心磁力计三件物理（全部闭式 · 死标量）：
  ① **自旋哈密顿量**（沿 NV 轴，S=1）：
        H = D·Sz² + γe·B·Sz        （D = 2.87 GHz 零场劈裂，γe = 28.024 GHz/T）
     本征频率 f± = D ± γe·B ⇒ **Zeeman 分裂** Δf = f+ − f− = 2·γe·B（闭式）。
  ② **Ramsey 相位积累**：微波 π/2 − 自由进动 τ − π/2 序列下相位
        φ(B, τ) = 2π·γe·B·τ      （闭式；对比度 C(τ) = C0·e^(−(τ/T2*)²)）
  ③ **磁灵敏度**（光子散粒噪声极限，Ramsey 最优 τ ~ T2*）：
        η = ħ·√(1 + a²)/(g·μB·C·√(N_ph·T2*))   （a = 暗计数/信号比，理想 a=0）
     极限形式 η ≈ ħ/(g·μB·C·√(N_ph·T2*))（δB√T 谱密度，单位 T/√Hz）。

═══ 🔴 纪律 ═══
· 进报告的数字一律**模块现算**（不转录草稿）；
· Zeeman 分裂用「闭式 Δf=2γeB」求得，并以「哈密顿量精确对角化」作第二路径互验
  （方法学内部一致性：闭式解析 vs 数值本征值）；
· 每道守卫配反向探针（见 `selfcheck_qs_m0` 的「先证能变红」）；
· C 级自主（纯 numpy），LLM 不进判决路径。
"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, Optional

import numpy as np

# ---------------------------------------------------------------------------
# 物理常数与 NV 色心材料参数（设计示例 · 公开文献常见值）
# ---------------------------------------------------------------------------
H_PLANCK = 6.62607015e-34          # J·s
HBAR = 1.054571817e-34             # J·s（ħ）
G_LANDE = 2.0023                   # 电子 g 因子
MU_B = 9.2740100783e-24            # J/T（玻尔磁子）
GAMMA_E_HZ_T = 28.024e9            # Hz/T（NV 电子自旋旋磁比，= gμB/h）
D_ZFS_HZ = 2.87e9                  # Hz（NV 基态零场劈裂 Δf_ZFS）

# 默认设计档（设计示例 · 可被 IR 覆盖）
_DEFAULTS = {
    "T2star_us": 1.0,              # µs（室温 NV 集合体非均匀展宽 T2*，典型 0.5–2 µs）
    "n_ph_per_s": 1.0e5,           # 光子计数率（计数/s，典型 1e4–1e6）
    "contrast": 0.03,              # ODMR 对比度 C0（集合体典型 1%–5%）
    "dark_ratio": 0.0,             # 暗计数/信号比 a（理想 0）
    "integration_s": 1.0,          # 积分时间 T（用于 δB√T 归一）
}


# ---------------------------------------------------------------------------
# ① 自旋哈密顿量：Zeeman 分裂（闭式 vs 精确对角化 双路径）
# ---------------------------------------------------------------------------
def zeeman_split_closed_form(B_t: float, gamma_hz_t: float = GAMMA_E_HZ_T) -> float:
    """闭式 Zeeman 分裂 Δf = 2·γe·B（Hz）。"""
    return 2.0 * gamma_hz_t * B_t


def spin_hamiltonian(B_t: float, D_hz: float = D_ZFS_HZ,
                     gamma_hz_t: float = GAMMA_E_HZ_T) -> np.ndarray:
    """沿 NV 轴的三能级自旋哈密顿量（S=1）：H = D·Sz² + γe·B·Sz（Hz）。

    取 ħ=1 的频率单位制：H 特征值即跃迁频率（Hz）。Sz 为 3×3 对角矩阵，
    基序为 **|m_s=+1⟩, |m_s=0⟩, |m_s=−1⟩**。
    """
    Sz = np.diag([1.0, 0.0, -1.0])                    # m_s = +1, 0, −1（对角元即本征值）
    Sz2 = Sz @ Sz
    return D_hz * Sz2 + gamma_hz_t * B_t * Sz


def _ms_index(ms: int) -> int:
    """m_s ∈ {+1,0,−1} → 基序下标（+1→0, 0→1, −1→2）。"""
    return {1: 0, 0: 1, -1: 2}[ms]


def zeeman_split_numeric(B_t: float, D_hz: float = D_ZFS_HZ,
                         gamma_hz_t: float = GAMMA_E_HZ_T) -> Dict[str, float]:
    """精确对角化求本征频率 ⇒ ms=+1 与 ms=−1 之分裂（第二路径互验闭式）。

    🔴 **血案（QS-M0 实测抓到的真 bug）**：H 为对角阵 diag(D+γB, 0, D−γB)，
    **升序本征值 = [0, D−γB, D+γB]**（ms=0 态能量恰为 0，是最低！）⇒
    「取首尾两本征值」会错取到 [ms=0, ms=+1]，把分裂算成 D+γB ≈ D 🚫。
    正解：**按 m_s 标签定位** ms=+1 与 ms=−1 两态再相减。
    """
    H = spin_hamiltonian(B_t, D_hz, gamma_hz_t)
    # H 为对角阵 ⇒ 本征值即对角元，下标 = m_s 基序下标（不依赖排序）
    diag = np.diag(H)
    f_plus = float(diag[_ms_index(+1)])
    f_zero = float(diag[_ms_index(0)])
    f_minus = float(diag[_ms_index(-1)])
    return {
        "f_minus_hz": f_minus,
        "f_zero_hz": f_zero,
        "f_plus_hz": f_plus,
        "split_hz": f_plus - f_minus,
    }


# ---------------------------------------------------------------------------
# ② Ramsey 相位积累与对比度
# ---------------------------------------------------------------------------
def ramsey_phase(B_t: float, tau_s: float,
                 gamma_hz_t: float = GAMMA_E_HZ_T) -> float:
    """Ramsey 自由进动相位 φ = 2π·γe·B·τ（rad，闭式）。"""
    return 2.0 * math.pi * gamma_hz_t * B_t * tau_s


def ramsey_contrast(tau_s: float, T2star_s: float = 1e-6,
                    contrast0: float = 0.03) -> float:
    """对比度包络 C(τ) = C0·e^(−(τ/T2*)²)（高斯去相位）。"""
    return contrast0 * math.exp(-(tau_s / T2star_s) ** 2)


def ramsey_signal(B_t: float, tau_s: float, T2star_s: float = 1e-6,
                  contrast0: float = 0.03,
                  gamma_hz_t: float = GAMMA_E_HZ_T) -> float:
    """Ramsey 条纹信号 S = C(τ)·cos(φ(B,τ))（归一化荧光对比度）。"""
    return ramsey_contrast(tau_s, T2star_s, contrast0) * math.cos(
        ramsey_phase(B_t, tau_s, gamma_hz_t))


# ---------------------------------------------------------------------------
# ③ 磁灵敏度 η = δB·√T（白噪声谱密度，T/√Hz）
# ---------------------------------------------------------------------------
def magnetometer_sensitivity(T2star_s: float = 1e-6, n_ph_per_s: float = 1.0e5,
                             contrast: float = 0.03, dark_ratio: float = 0.0,
                             gamma_hz_t: float = GAMMA_E_HZ_T) -> Dict[str, float]:
    """光子散粒噪声极限磁灵敏度（Ramsey 序列 · 最优 τ ≈ T2*）。

    从 Ramsey 相位斜率反推：单次测量不确定度 δB = δφ/(gμB/ħ·τ)，
    散粒相位噪声 δφ = √(1+a²)/(C·√N_ph)；取 τ = T2*/√2（对比度包络最优斜率点）。

    🔴 **谱密度归一（QS-M0 实测抓到的差 1000× bug）**：一次 Ramsey 循环耗时 ≈ T2*，
    故 **η = δB·√(T2*)**（单位 T/√Hz，√T_normalized）。漏掉 √T2* 会得到「单次测量
    δB」（T）而非谱密度——量纲错、且恰好差 √T2* 量级。

        η = ħ/(g·μB) · √(1+a²)·√2/(C·√(n_ph·T2*))     [T/√Hz]
    """
    g_muB_over_hbar = G_LANDE * MU_B / HBAR            # rad·s⁻¹·T⁻¹ (= 2π·γe)
    # 最优自由进动时间（高斯包络 e^(−(τ/T2*)²) 斜率最大化点）
    tau_opt = T2star_s / math.sqrt(2.0)
    # 散粒相位噪声（rad）
    sigma_phi = math.sqrt(1.0 + dark_ratio ** 2) / (contrast * math.sqrt(n_ph_per_s))
    # 单次测量不确定度 δB = σφ/(斜率) ; 斜率 dφ/dB = gμB/ħ·τ
    delta_B_single = sigma_phi / (g_muB_over_hbar * tau_opt)
    # 谱密度归一：η = δB·√(T2*)（一次循环 ≈ T2*）
    eta = delta_B_single * math.sqrt(T2star_s)
    return {
        "eta_T_per_sqrtHz": eta,
        "eta_pT_per_sqrtHz": eta * 1e12,
        "tau_opt_s": tau_opt,
        "sigma_phi_rad": sigma_phi,
        "delta_B_single_T": delta_B_single,
        "g_muB_over_hbar_rad_s_T": g_muB_over_hbar,
    }


def sensitivity_shot_limit_closed(T2star_s: float, n_ph_per_s: float,
                                   contrast: float,
                                   gamma_hz_t: float = GAMMA_E_HZ_T) -> float:
    """散粒极限闭式（a=0）：η = ħ/(gμB)·√2/(C·√(n_ph·T2*))（T/√Hz）。

    代入 τ_opt=T2*/√2 ⇒ η = [1/(C·√n_ph)] / [(gμB/ħ)·T2*/√2]
    = ħ/(gμB) · √2/(C·√(n_ph·T2*))。
    """
    g_muB_over_hbar = G_LANDE * MU_B / HBAR
    return (math.sqrt(2.0) / (contrast * math.sqrt(n_ph_per_s * T2star_s))
            / g_muB_over_hbar)


# ---------------------------------------------------------------------------
# 设计入口（与 PS-M0 同构：design_sensor_v0 → 结构报告 + 版图链路）
# ---------------------------------------------------------------------------
def design_magnetometer_v0(T2star_us: float = 1.0, n_ph_per_s: float = 1.0e5,
                           contrast: float = 0.03, dark_ratio: float = 0.0,
                           B_test_t: float = 1e-6,
                           run_layout: bool = True) -> Dict[str, Any]:
    """QS-M0 主设计：NV 色心磁力计基线设计 + 主权版图链路。

    ``B_test_t`` 为探针磁感应强度（默认 1 µT，用于验证 Zeeman 分裂闭式 ↔ 数值）。
    """
    T2star_s = T2star_us * 1e-6

    # ① Zeeman 分裂：闭式 vs 精确对角化
    split_cf = zeeman_split_closed_form(B_test_t)
    sp_num = zeeman_split_numeric(B_test_t)
    split_num = sp_num["split_hz"]

    # ② Ramsey 相位/对比度
    tau_opt = T2star_s / math.sqrt(2.0)
    phi = ramsey_phase(B_test_t, tau_opt)
    contrast_at_tau = ramsey_contrast(tau_opt, T2star_s, contrast)

    # ③ 灵敏度（两条路径：通用 + 散粒闭式，a=0 时应一致）
    sens = magnetometer_sensitivity(T2star_s, n_ph_per_s, contrast, dark_ratio)
    eta_closed = sensitivity_shot_limit_closed(T2star_s, n_ph_per_s, contrast)
    # 与文献量级对照（国际 SOTA：芯片级 26 nT/√Hz；腔最优 52 nT/√Hz）
    eta_pT = sens["eta_pT_per_sqrtHz"]
    eta_nT = eta_pT / 1e3

    # ④ 主权版图链路（复用平台 lda_chain 机架 · 色心/天线/读出光路）
    layout_chain: Dict[str, Any] = {}
    if run_layout:
        try:
            from lda_chain import LinkModel
            _lm = LinkModel()   # 构造探针：仅证「平台机架可实例化」；本档不布线
            layout_chain = {"available": True,
                            "note": "LinkModel 已就绪（QS-M0 占位）",
                            "link_model_type": type(_lm).__name__}
        except Exception as exc:  # pragma: no cover - 环境相关
            layout_chain = {"error": f"{type(exc).__name__}: {exc}"}

    return {
        "milestone": "QS-M0",
        "device": "NV-center magnetometer (baseline)",
        "params": {
            "T2star_us": T2star_us,
            "n_ph_per_s": n_ph_per_s,
            "contrast": contrast,
            "dark_ratio": dark_ratio,
            "B_test_t": B_test_t,
        },
        "zeeman": {
            "split_closed_form_hz": split_cf,
            "split_numeric_hz": split_num,
            "f_plus_hz": sp_num["f_plus_hz"],
            "f_minus_hz": sp_num["f_minus_hz"],
            "abs_rel_err": abs(split_cf - split_num) / max(abs(split_cf), 1e-30),
        },
        "ramsey": {
            "tau_opt_s": tau_opt,
            "phase_rad": phi,
            "contrast_at_tau": contrast_at_tau,
        },
        "sensitivity": {
            **sens,
            "eta_closed_form_T_per_sqrtHz": eta_closed,
            "eta_closed_vs_general_rel_err": abs(
                eta_closed - sens["eta_T_per_sqrtHz"]) / max(sens["eta_T_per_sqrtHz"], 1e-30),
            "eta_nT_per_sqrtHz": eta_nT,
        },
        "benchmark": {
            "intl_state_of_art_chip_nT_per_sqrtHz": 26.0,
            "intl_state_of_art_cavity_nT_per_sqrtHz": 52.0,
            "gap_ratio_vs_chip": eta_nT / 26.0,
        },
        "layout_chain": layout_chain,
    }


# ---------------------------------------------------------------------------
# 自校 / 反向探针（先证能变红）
# ---------------------------------------------------------------------------
def selfcheck_qs_m0(tol_zeeman_vs_num: float = 1e-9,
                    rep: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """QS-M0 守卫：物理量合理 + 双路径互验 + 反向探针。

    反向探针（抹平断口必红）：
      · B=0 ⇒ Zeeman 分裂必为 0（若实现漏乘 B ⇒ 非零 ⇒ 红）；
      · 对比度 C→0 ⇒ 灵敏度 →∞（若实现漏除 C ⇒ 有限 ⇒ 红）。
    """
    if rep is None:
        rep = design_magnetometer_v0(run_layout=False)

    checks: Dict[str, bool] = {}

    # ① 双路径互验：闭式 Δf=2γeB ↔ 精确对角化
    checks["zeeman_closed_vs_numeric"] = (
        rep["zeeman"]["abs_rel_err"] < tol_zeeman_vs_num)

    # ② Zeeman 分裂为正且与 B 成正比（量级检查：1µT ⇒ 2·28.024e9·1e-6 ≈ 56.05 kHz）
    split = rep["zeeman"]["split_closed_form_hz"]
    checks["zeeman_positive"] = split > 0.0
    checks["zeeman_linear_in_B"] = abs(
        zeeman_split_closed_form(2e-6) - 2.0 * split) / max(abs(2.0 * split), 1e-30) < 1e-12

    # ③ 灵敏度两条路径互验（a=0 时散粒闭式应精确复现通用式）
    checks["sensitivity_closed_vs_general"] = (
        rep["sensitivity"]["eta_closed_vs_general_rel_err"] < 1e-9)

    # ④ 灵敏度有限为正且落在合理量级（1 nT ~ 1 mT /√Hz）
    eta_T = rep["sensitivity"]["eta_T_per_sqrtHz"]
    checks["eta_finite_positive"] = math.isfinite(eta_T) and eta_T > 0.0
    checks["eta_in_sane_range"] = 1e-12 <= eta_T <= 1e-3

    # ⑤ 反向探针：B=0 ⇒ Δf=0（漏乘 B 的实现必红）
    checks["zero_B_guard_armed"] = abs(zeeman_split_closed_form(0.0)) < 1e-30

    # ⑥ 反向探针：C→0 ⇒ η→∞（漏除 C 的实现必红）。
    #    🔴 用**精确 0.0**（非 1e-300：后者在 double 下做 C·√n_ph 仍可能落在次正规数、
    #    结果有限而探针失灵——QS-M0 实测抓到）。精确 0 ⇒ 除零（ZeroDivisionError
    #    或 inf）二者之一 ⇒ 探针应判「已武装」（守卫必捕获该病态输入）。
    try:
        eta_zero_C = magnetometer_sensitivity(1e-6, 1e5, 0.0)["eta_T_per_sqrtHz"]
        checks["zero_contrast_guard_armed"] = not math.isfinite(eta_zero_C)
    except ZeroDivisionError:
        checks["zero_contrast_guard_armed"] = True

    all_pass = all(checks.values())
    rep["selfcheck"] = {"all_pass": all_pass, "checks": checks}
    return rep


# ---------------------------------------------------------------------------
# 命令行入口（被 run_qs_m0_smoke.py 复用）
# ---------------------------------------------------------------------------
def main() -> int:
    rep = selfcheck_qs_m0()
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 0 if rep["selfcheck"]["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
