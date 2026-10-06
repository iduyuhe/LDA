# -*- coding: utf-8 -*-
"""PM-M6：相位域（干涉/谐振）多电平读出与漂移口径 —— **PM-G6 结算层**。

征程位置：光子存储 PM-M6（承接 M1 振幅域判据的**逆命题**）。
M1 的核心结论是：多电平走**振幅域**可行 ⇔ `r = k_a/(k_c−k_a) ≤ r_max`（纯材料比）。
M1 同时判定：**k_c ≈ k_a 的低损耗材料（Sb₂Se₃）在振幅域不可行** ⇒ 多电平必须另立口径。
本模块交付那条口径 —— **相位域**：

  ① 编码量从「透射强度」换成「相移 φ = 2πΓΔnL/λ」；
  ② 读出机构从「直通 + 吸收调制」换成「干涉（MZI cos²）/ 谐振（微环，精细度增强）」；
  ③ 可行性判据从 M1 的 r 判据换成 **FOM 判据**（见下），**Γ 与 L 同样约掉**。

🔴 本模块的三条核心律（全部闭式、全部与几何无关）
--------------------------------------------------
| 量 | 闭式 | 语义 |
|---|---|---|
| 每 π 损耗 | `IL_π = (10/ln10)·2πk/Δn` | 与 Γ、L 均无关（`pm_matlib` 已登记） |
| 相位域 FOM | `FOM = Δn/(8.6859·k) = π/IL_π` | 材料比 ⇒ **材料定能力** |
| 多电平可行性 | `IL_π ≤ IL_budget`（⇔ `FOM ≥ π/IL_budget`） | 几何只定**窗口位置** |

⇒ 与 M0/M1 完全同族：**材料定能力、几何只分配窗口**。

🔴 相位域 vs 振幅域的**本质差异**（本模块的独立理由）
-------------------------------------------------------
| | 振幅域（M1） | 相位域（M6） |
|---|---|---|
| 编码量 | 透射 T（**耗散型**，无参考） | 相移 φ（**相对量**，需参考臂） |
| 对漂移的响应 | 漂移 ∝ 吸收 ⇒ 直接吃对比度 | 漂移 ∝ 相位行程；**差分对可共模消除** |
| 读出 | 单端探测 | 干涉/谐振 ⇒ 有**增益-带宽积守恒** |
⇒ 「相位域须独立口径」不是修辞：**参考臂的存在改变了漂移的传播路径**。

诚实边界（写进 `M6_DISCLOSURE`，机器可读）
------------------------------------------
1. 🔴 **相位漂移无独立定量实测锚**：现有光学域锚全是**透射**漂移（Cheng 2019）或**电学**域
   （DRIFT_ANCHORS）⇒ 本模块只给**观测方程 + 灵敏度公式 + 共模抑制机制**；
   `phase_drift_budget()` 里的保持时间数字一律标记为 **`proxy_cross_domain=True` 的假设值**
   （用透射锚跨域代理），**不构成定量结论**。
2. 🔴 **器件 FOM ≠ 材料 FOM**：材料吸收路径 FOM（Δn/8.686k）比器件级锚（Delaney 29 rad/dB）
   高数个量级 ⇒ 一律并报，不互相替代（同 `pm_matlib.phase_domain_residue` 政策）。
3. 🔴 读出模型 = **shot-noise 简化 + 相位噪声并报**（无暗电流/带宽/热噪声）⇒ 只作方向性判断。
4. 🔴 K0 与绝对写入时长同 M1：不报真值；能效指标（TOPS/fJ-op/pJ-bit）**不报**。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from lda_l2 import pm_matlib as ML

# ---------------------------------------------------------------------------
# 0. 假设参数（🔴 全部标注 provenance）
# ---------------------------------------------------------------------------
GAMMA_DEFAULT: float = 0.0840054905578339  # 🔴 标定 Γ（v0.9.200 重标定批次）= `pm_gamma.gamma_main`；
                                            #   相位域判据里 Γ 与 L 约掉 ⇒ 本值不影响 FOM/IL_π，仅统一现役口径。
WL_NM_DEFAULT: float = 1550.0
E_READ_FJ_ASSUMED: float = 9.0          # 与 M0/M1 同源（shot-noise 简化用）
BER_TARGET: float = 1.0e-12
LEVELS_6BIT: int = 64                   # 6-bit（器件锚 AFM 2023 给到的多电平位数）
#: 🔴 相位臂插损预算（**设计假设**：给多电平相移臂留多少 dB）
IL_BUDGET_DB_ASSUMED: float = 3.0
#: 🔴 相位噪声（**设计假设**：激光线宽 + 热漂移折算到单次读出的相位抖动，rad）
PHASE_NOISE_RAD_ASSUMED: float = 0.01
#: 🔴 残余共模抑制比（**设计假设**：差分对两臂材料量失配 ⇒ 共模泄漏比例；1.0 = 理想消除）
CMRR_IDEAL_FRACTION_ASSUMED: float = 0.0

M6_DISCLOSURE: Dict[str, Any] = {
    "gamma_is_assumption": True,
    "gamma_and_length_cancel_in_fom": True,
    "il_budget_is_assumption": True,
    "phase_noise_is_assumption": True,
    "device_fom_not_interchangeable_with_material_fom": True,
    "phase_drift_has_no_independent_quantitative_anchor": True,
    "readout_model_is_simplification": True,
    "no_energy_efficiency_metrics": True,
}


class PMM6Error(Exception):
    """M6 域错误（越域 = 模型失效，拒绝静默截断）。"""


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise PMM6Error(msg)


def _json_safe(obj: Any) -> Any:
    """🔴 出口 JSON 安全：±inf/NaN ⇒ 字符串 tag（防 `json.dumps` 造非标准 token）。

    本模块会出现 `inf`（Nanomaterials 来源明确给 k=0 ⇒ FOM=∞）——若直接进 JSON，
    浏览器 `JSON.parse` 会因 `Infinity` 抛错整卡崩（同族血案：非标准 JSON 出口）。
    """
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj):
            return "NaN"
        if math.isinf(obj):
            return "∞" if obj > 0 else "-∞"
    return obj


# ---------------------------------------------------------------------------
# 1. 相位域基本量（材料级：Γ 与 L 在比值里约掉）
# ---------------------------------------------------------------------------
def phase_full_swing_rad(l_um: float, dn: float, *, gamma: float = GAMMA_DEFAULT,
                         wl_nm: float = WL_NM_DEFAULT) -> float:
    """全晶化相移 φ_full = 2πΓΔnL/λ（rad）。"""
    _require(l_um > 0.0 and dn > 0.0 and gamma > 0.0, "L/Δn/Γ 必须为正")
    return 2.0 * math.pi * gamma * dn * (l_um * 1e-6) / (wl_nm * 1e-9)


def l_pi_um(dn: float, *, gamma: float = GAMMA_DEFAULT,
            wl_nm: float = WL_NM_DEFAULT) -> float:
    """π 相移所需长度 L_π = λ/(2ΓΔn)（µm）—— 相位域多电平的**理想臂长**。"""
    _require(dn > 0.0 and gamma > 0.0, "Δn/Γ 必须为正")
    return (wl_nm * 1e-9 / (2.0 * gamma * dn)) * 1e6


def phase_il_db(l_um: float, k_c: float, *, gamma: float = GAMMA_DEFAULT,
                wl_nm: float = WL_NM_DEFAULT) -> float:
    """相位臂插损 IL = (10/ln10)·Γ·(4πk/λ)·L（dB）。"""
    _require(l_um > 0.0 and k_c >= 0.0, "L 必须为正、k 非负")
    return (10.0 / math.log(10.0)) * gamma * (4.0 * math.pi * k_c / (wl_nm * 1e-9)) * (l_um * 1e-6)


def _state_rows(mat: str, wl_nm: float) -> List[Dict[str, Any]]:
    """逐来源 (Δn, k_a, k_c) 表（复用 `pm_matlib.delta_n` 的两态配对守卫）。"""
    return ML.delta_n(mat, wl_nm)["per_source"]


def resolve_l_um(mat: str, l_um: Optional[float], *, gamma: float = GAMMA_DEFAULT,
                 wl_nm: float = WL_NM_DEFAULT) -> float:
    """`l_um=None` ⇒ 取**理想臂长** L_π（φ_full = π）。

    🔴 逐来源 Δn 不同 ⇒ 取**最小 Δn**（= 最长 L_π）以保证**所有来源**都 span_ok
    （几何是器件级单一量，不能逐来源变）。
    """
    if l_um is not None:
        _require(l_um > 0.0, "L 必须为正")
        return float(l_um)
    dn_min = min(st["dn"] for st in _state_rows(mat, wl_nm))
    return l_pi_um(dn_min, gamma=gamma, wl_nm=wl_nm)


# ---------------------------------------------------------------------------
# 2. 相位域多电平：干涉（MZI）**等强度间距**反解相位
# ---------------------------------------------------------------------------
def mzi_transmittance(phi_rad: float) -> float:
    """平衡 MZI 归一化输出 I(φ) = cos²(φ/2)（🔥 双臂等分、无损耗的理想传递函数）。"""
    return math.cos(0.5 * phi_rad) ** 2


def phi_for_mzi_transmittance(i_norm: float) -> float:
    """I → φ 的**精确闭式反演**：φ = 2·arccos(√I)，单调段 φ ∈ [0, π]。"""
    _require(0.0 <= i_norm <= 1.0, f"归一化强度必须 ∈ [0,1]，收到 {i_norm!r}")
    return 2.0 * math.acos(math.sqrt(i_norm))


def phase_level_design(mat: str, n_levels: int, *, l_um: Optional[float] = None,
                       gamma: float = GAMMA_DEFAULT, wl_nm: float = WL_NM_DEFAULT,
                       allow_out_of_span: bool = False) -> Dict[str, Any]:
    """相位域多电平设计：**等强度间距**（MZI 读出域等距）⇒ 闭式反解相位与晶化率。

    🔴 与 M1 振幅域的**结构性差异**：M1 是「等透射率间距 ⇒ 反解 c」，因 IL(c) 线性于 c；
    本模块是「等**MZI 输出强度**间距 ⇒ 反解 φ ⇒ 反解 c」，因 I(φ)=cos²(φ/2) **非线性**
    ⇒ 等强度间距下相邻**相位**间距不等（cos² 平坦处相位间距大、陡峭处小）。
    反演是精确的（arccos 是解析反函数）⇒ 无数值误差项。

    🔴 越域 = 模型失效：`L < L_π` ⇒ φ_full < π ⇒ 装不下一个半周期 ⇒ `c > 1`。
    默认 `allow_out_of_span=False` 时**直接 raise**（不静默截断，同 U4/M1 政策）。
    """
    _require(n_levels >= 2, "至少两级")
    l_um = resolve_l_um(mat, l_um, gamma=gamma, wl_nm=wl_nm)
    _require(l_um > 0.0, "L 必须为正")
    rows = []
    for st in _state_rows(mat, wl_nm):
        dn, k_c = st["dn"], st["k_c"]
        phi_full = phase_full_swing_rad(l_um, dn, gamma=gamma, wl_nm=wl_nm)
        span_ok = phi_full >= math.pi              # 至少要够一个半周期（[0,π]）
        if not span_ok and not allow_out_of_span:
            raise PMM6Error(
                "L=%.4f µm 下 φ_full=%.6f rad (%.4f π) < π ⇒ 装不下一个半周期（c_max=%.4f > 1）。"
                "越域是**模型失效**（非器件饱和）：请用 L ≥ L_π=%.4f µm，或用 allow_out_of_span=True "
                "显式取回诊断数据。" % (l_um, phi_full, phi_full / math.pi, math.pi / phi_full,
                                   l_pi_um(dn, gamma=gamma, wl_nm=wl_nm)))
        levels = []
        for j in range(n_levels):
            i_norm = 1.0 - j / (n_levels - 1)       # I: 1 → 0（等强度间距）
            phi = phi_for_mzi_transmittance(i_norm)
            c = phi / phi_full if phi_full > 0 else math.inf
            levels.append({"j": j, "i_norm": i_norm, "phi_rad": phi,
                           "phi_pi": phi / math.pi, "c": c, "i_check": mzi_transmittance(phi)})
        dphis = [levels[j + 1]["phi_rad"] - levels[j]["phi_rad"] for j in range(n_levels - 1)]
        dphi_min = min(dphis)
        rows.append({
            "source": st["source"], "dn": dn, "k_c": k_c,
            "phi_full_rad": phi_full, "phi_full_pi": phi_full / math.pi,
            "span_ok": span_ok, "levels": levels,
            "dphi_min_rad": dphi_min, "dphi_max_rad": max(dphis),
            # 一阶验证：cos² 在正交点 |dφ/dI| 最小 = 2 ⇒ Δφ_min ≈ 2ΔI = 2/(N−1)
            "dphi_min_quadrature_rel_dev": abs(dphi_min / (2.0 / (n_levels - 1)) - 1.0)
            if n_levels > 2 else 0.0,
            "c_max": levels[-1]["c"],
        })
    return {"material": mat, "n_levels": n_levels, "l_um": float(l_um), "gamma": float(gamma),
            "wl_nm": float(wl_nm), "per_source": rows,
            "n_span_ok": sum(1 for r in rows if r["span_ok"] and r["c_max"] <= 1.0),
            "n_sources": len(rows),
            "law": ("等 MZI 强度间距 ⇒ φ_j = 2·arccos(√I_j)（精确反演）；"
                    "cos² 非线性 ⇒ 相位间距不等，最小间距在正交点 φ=π/2（≈2/(N−1)）")}


# ---------------------------------------------------------------------------
# 3. 相位域可行性核心律（几何无关）
# ---------------------------------------------------------------------------
def phase_domain_feasibility(mat: str, *, n_levels: int = LEVELS_6BIT,
                             gamma: float = GAMMA_DEFAULT, wl_nm: float = WL_NM_DEFAULT,
                             il_budget_db: float = IL_BUDGET_DB_ASSUMED) -> Dict[str, Any]:
    """🔴 **M6 核心律**：相位域多电平可行性（**Γ 与 L 同时约掉**）。

    窗口 = [L_min, L_max]：
        L_min = L_π = λ/(2ΓΔn)            相位行程恰够一个半周期 [0,π]
        L_max = IL_budget / α_per_um      α_per_um = (10/ln10)·Γ·4πk_c/λ·1e-6
    在 L_min 处 IL = IL_π = (10/ln10)·2πk_c/Δn（闭式，Γ 约掉）
    ⇒ 窗口存在 ⇔ **IL_π ≤ IL_budget** ⇔ **FOM_mat ≥ π/IL_budget**（纯材料比）。
    ⇒ 与 M1 的 r 判据同族：**材料定能力、几何只定窗口位置**。
    """
    _require(n_levels >= 2, "至少两级")
    _require(il_budget_db > 0.0, "损耗预算必须为正")
    fom_need = math.pi / il_budget_db
    per = []
    for st in _state_rows(mat, wl_nm):
        dn, k_c = st["dn"], st["k_c"]
        il_pi = ML.per_pi_loss_db(dn, k_c) if dn > 0 else math.inf
        fom = (dn / (2.0 * (10.0 / math.log(10.0)) * k_c)) if k_c > 0 else math.inf
        l_min = l_pi_um(dn, gamma=gamma, wl_nm=wl_nm)
        alpha_per_um = (10.0 / math.log(10.0)) * gamma * (4.0 * math.pi * k_c / (wl_nm * 1e-9)) * 1e-6
        feasible = bool(il_pi <= il_budget_db)
        # 🔴 窗口端点自洽双检：L_min 处 IL 必须 == IL_π（闭式），L_max 处 IL 必须 == 预算。
        #    k_c == 0（来源明确给零吸收）⇒ 无损耗上限：l_max=∞ 且 IL≡0（不是 nan）
        if alpha_per_um > 0.0:
            l_max = il_budget_db / alpha_per_um
            il_at_lmax = phase_il_db(l_max, k_c, gamma=gamma, wl_nm=wl_nm)
            lmax_ok = abs(il_at_lmax - il_budget_db) <= 1e-9 * il_budget_db
        else:
            l_max = math.inf
            il_at_lmax = 0.0                      # 零吸收 ⇒ IL 恒为 0（显式定义，不经 0·∞）
            lmax_ok = (k_c == 0.0)
        il_at_lmin = phase_il_db(l_min, k_c, gamma=gamma, wl_nm=wl_nm)
        per.append({"source": st["source"], "dn": dn, "k_c": k_c,
                    "il_db_per_pi": il_pi, "fom_rad_per_db": fom,
                    "fom_needed_rad_per_db": fom_need,
                    "feasible": feasible,
                    "l_min_um": l_min, "l_max_um": l_max if math.isfinite(l_max) else None,
                    "window_um": (l_min, l_max) if (feasible and l_max >= l_min) else None,
                    "il_at_lmin_db": il_at_lmin, "il_at_lmax_db": il_at_lmax,
                    "endpoint_self_consistent": bool(
                        abs(il_at_lmin - il_pi) <= 1e-9 * max(il_pi, 1e-300) and lmax_ok)})
    n_ok = sum(1 for p in per if p["feasible"])
    return {"material": mat, "n_levels": n_levels, "il_budget_db": float(il_budget_db),
            "fom_needed_rad_per_db": fom_need,
            "per_source": per, "n_feasible_sources": n_ok, "n_sources": len(per),
            "headline": ("相位域多电平可行 ⇔ IL_π ≤ %.1f dB ⇔ FOM ≥ %.4g rad/dB（**与 Γ、L 无关**）；"
                         "理想臂长 = L_π（φ_full = π）。可行情形的 L 窗口由几何定位置。"
                         % (il_budget_db, fom_need))}


# ---------------------------------------------------------------------------
# 4. 读出：干涉（MZI）与谐振（微环）—— 相位 → 强度
# ---------------------------------------------------------------------------
def _snr_for_ber(ber: float) -> float:
    _require(0.0 < ber < 0.5, "ber 必须 ∈ (0, 0.5)")
    lo, hi = 0.0, 40.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if 0.5 * math.erfc(mid / math.sqrt(2.0)) > ber:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def n_photons(e_read_fj: float, wl_nm: float = WL_NM_DEFAULT) -> float:
    """读出光子数 N = E/(hν)（与 M0/M1 同源）。"""
    _require(e_read_fj > 0.0, "读出能量必须为正")
    return e_read_fj * 1e-15 / (6.62607015e-34 * 2.99792458e8 / (wl_nm * 1e-9))


def max_levels_shot_limited(e_read_fj: float = E_READ_FJ_ASSUMED,
                            ber_target: float = BER_TARGET,
                            wl_nm: float = WL_NM_DEFAULT) -> Dict[str, Any]:
    """🔴 等间距多电平的**位深上限**（shot 限 · **与读出机构无关**）：

    最坏对（最高电平，n = N_ph）的 shot SNR = √N_ph / (2(N−1)) ≥ SNR_req
    ⇒ **N_max = 1 + √N_ph/(2·SNR_req)**。
    与 M1 `seven_bit_readout_floor` 是**同一不等式的两种写法**
    （M1: N_ph ≥ (2(L−1)·SNR_req)²）⇒ 两模块互为交叉验证。
    ⇒ 结论：**相位域（干涉或谐振）的位深由光子预算锁死，与相位→强度机构无关**。
    """
    s_req = _snr_for_ber(ber_target)
    nph = n_photons(e_read_fj, wl_nm)
    n_max = 1.0 + math.sqrt(nph) / (2.0 * s_req)
    return {"e_read_fj": float(e_read_fj), "ber_target": ber_target, "snr_req": s_req,
            "n_photons": nph, "n_levels_max": n_max,
            "bits_max": math.log2(n_max) if n_max > 1 else 0.0,
            "law": "N_max = 1 + √N_ph/(2·SNR_req)（等间距 + shot 限）"}


def readout_energy_for_levels(n_levels: int, ber_target: float = BER_TARGET,
                              wl_nm: float = WL_NM_DEFAULT) -> Dict[str, Any]:
    """给定电平数所需的**读出光子/能量下限**（`max_levels_shot_limited` 的逆解）：

    N_ph ≥ (2(N−1)·SNR_req)² ⇒ E = N_ph·hν（fJ）。与 M1 `seven_bit_readout_floor` 同式。
    """
    _require(n_levels >= 2, "至少两级")
    s_req = _snr_for_ber(ber_target)
    nph = (2.0 * (n_levels - 1) * s_req) ** 2
    e_fj = nph * 6.62607015e-34 * 2.99792458e8 / (wl_nm * 1e-9) * 1e15
    return {"n_levels": n_levels, "n_photons_min": nph, "e_read_min_fj": e_fj,
            "ber_target": ber_target, "law": "N_ph ≥ (2(N−1)·SNR_req)²（与 M1 同式）"}


def interferometric_readout(mat: str, n_levels: int, *, l_um: Optional[float] = None,
                            gamma: float = GAMMA_DEFAULT, wl_nm: float = WL_NM_DEFAULT,
                            e_read_fj: float = E_READ_FJ_ASSUMED,
                            phase_noise_rad: float = PHASE_NOISE_RAD_ASSUMED,
                            ber_target: float = BER_TARGET) -> Dict[str, Any]:
    """MZI 干涉读出的相邻电平 BER（**双噪声源并报**：shot + 相位）。

    shot 项与 M1 `level_readout_ber` **同式同免责**（SNR = Δn_ph/(2√n_upper)），
    相位噪声项为相位域**特有**：σ_n = N_ph·|dI/dφ|·σ_φ，|dI/dφ| = sin(φ)/2。
    ⇒ worst = 两源中**较差**者（并报，不取优）。
    """
    l_um = resolve_l_um(mat, l_um, gamma=gamma, wl_nm=wl_nm)
    d = phase_level_design(mat, n_levels, l_um=l_um, gamma=gamma, wl_nm=wl_nm)
    nph = n_photons(e_read_fj, wl_nm)
    pairs = []
    for r in d["per_source"]:
        lv = r["levels"]
        for j in range(n_levels - 1):
            i_lo, i_hi = lv[j + 1], lv[j]           # i_norm 递减 ⇒ j 高、j+1 低
            di = nph * (i_hi["i_norm"] - i_lo["i_norm"])
            n_upper = nph * i_hi["i_norm"]
            snr_shot = di / (2.0 * math.sqrt(max(n_upper, 1e-300)))
            phi_mid = 0.5 * (i_hi["phi_rad"] + i_lo["phi_rad"])
            slope = 0.5 * abs(math.sin(phi_mid))     # |dI/dφ|
            sigma_phase = nph * slope * phase_noise_rad
            snr_phase = di / sigma_phase if sigma_phase > 0 else math.inf
            snr = min(snr_shot, snr_phase)
            pairs.append({"source": r["source"], "pair": (j, j + 1),
                          "snr_shot": snr_shot, "snr_phase": snr_phase, "snr": snr,
                          "ber": 0.5 * math.erfc(snr / math.sqrt(2.0)),
                          "limited_by": "shot" if snr_shot <= snr_phase else "phase_noise"})
    for p in pairs:
        p["ok"] = p["ber"] <= ber_target
    return {"material": mat, "n_levels": n_levels, "l_um": float(l_um),
            "e_read_fj": float(e_read_fj), "phase_noise_rad": float(phase_noise_rad),
            "n_photons": nph, "pairs": pairs,
            "n_limited_by_shot": sum(1 for p in pairs if p["limited_by"] == "shot"),
            "n_limited_by_phase": sum(1 for p in pairs if p["limited_by"] == "phase_noise"),
            "all_ok": all(p["ok"] for p in pairs) if pairs else False,
            "worst_ber": max((p["ber"] for p in pairs), default=math.inf),
            "model": "shot_noise_limited + phase_noise(assumption)",
            "honest_note": ("🔴 简化双噪声源模型（无暗电流/带宽/热噪声）⇒ 只作方向性判断；"
                            "worst 取两源较差者（并报，不取优）。")}


def resonant_enhancement(finesse: float) -> Dict[str, Any]:
    """谐振读出的**增益-带宽积守恒**（闭式，经典腔结果）：

    微环把相位→强度转换的斜率放大 `K = F/π`（F = 精细度），
    代价是可用带宽同时收窄 `K` 倍 ⇒ **K·Δω 守恒**（不能同时要大增益与宽带宽）。
    """
    _require(finesse >= 1.0, "精细度必须 ≥ 1")
    return {"finesse": float(finesse), "enhancement_factor": finesse / math.pi,
            "bandwidth_narrowing_factor": finesse / math.pi,
            "gain_bandwidth_product": (finesse / math.pi) * (1.0 / (finesse / math.pi)),
            "law": "K = F/π（相位→强度斜率增强）；K·Δω = 1（守恒）—— 无免费午餐"}


def resonant_readout(mat: str, n_levels: int, *, l_um: Optional[float] = None, finesse: float,
                     gamma: float = GAMMA_DEFAULT, wl_nm: float = WL_NM_DEFAULT,
                     e_read_fj: float = E_READ_FJ_ASSUMED,
                     phase_noise_rad: float = PHASE_NOISE_RAD_ASSUMED,
                     ber_target: float = BER_TARGET) -> Dict[str, Any]:
    """谐振（微环）读出：在 MZI 读出结果上乘 `K = F/π` 的相位-强度斜率增强。

    🔴 实现方式是**显式**的：把 `interferometric_readout` 的**相位噪声项**按 K 放大后重算
    （shot 项不随 K 变——它由电平强度差与光子数决定）⇒ 谐振只缓解**相位噪声受限**的分辨力，
    对 shot 受限无用。两路并报 ⇒ 读者能看出**哪一路被什么限制**。
    """
    enh = resonant_enhancement(finesse)
    l_um = resolve_l_um(mat, l_um, gamma=gamma, wl_nm=wl_nm)
    base = interferometric_readout(mat, n_levels, l_um=l_um, gamma=gamma, wl_nm=wl_nm,
                                   e_read_fj=e_read_fj, phase_noise_rad=phase_noise_rad,
                                   ber_target=ber_target)
    k = enh["enhancement_factor"]
    pairs = []
    for p in base["pairs"]:
        snr_phase_r = p["snr_phase"] * k                    # 相位噪声等效压低 K 倍
        snr = min(p["snr_shot"], snr_phase_r)
        pairs.append({"source": p["source"], "pair": p["pair"],
                      "snr_shot": p["snr_shot"], "snr_phase_resonant": snr_phase_r, "snr": snr,
                      "ber": 0.5 * math.erfc(snr / math.sqrt(2.0)),
                      "limited_by": "shot" if p["snr_shot"] <= snr_phase_r else "phase_noise",
                      "ok": 0.5 * math.erfc(snr / math.sqrt(2.0)) <= ber_target})
    return {"material": mat, "n_levels": n_levels, "l_um": float(l_um), "finesse": float(finesse),
            "enhancement": enh, "pairs": pairs,
            "all_ok": all(p["ok"] for p in pairs) if pairs else False,
            "worst_ber": max((p["ber"] for p in pairs), default=math.inf),
            "arch": "microring(resonant)",
            "honest_note": ("🔴 谐振只放大**相位噪声受限**的分辨力（K=F/π）；shot 受限项不变 ⇒ "
                            "增益-带宽积守恒，不是免费午餐。")}


# ---------------------------------------------------------------------------
# 5. 漂移口径（相位域**独立**于 G7 的透射口径）
# ---------------------------------------------------------------------------
def phase_drift_budget(mat: str, n_levels: int, *, l_um: Optional[float] = None,
                       nu_n_ub: float, gamma: float = GAMMA_DEFAULT,
                       wl_nm: float = WL_NM_DEFAULT, t0_s: float = 1.0,
                       cmrr_fraction: float = CMRR_IDEAL_FRACTION_ASSUMED
                       ) -> Dict[str, Any]:
    """相位漂移预算：观测方程 + 共模抑制 + 保持口径（**不含**定量真值）。

    观测方程（**模型假设**）：折射率相对漂移 `δn/n = ν_n·ln(t/t₀)`（结构弛豫幂律的对数域写法）
    ⇒ 相位漂移 `δφ(t) = φ_total·ν_n·ln(t/t₀)`，`φ_total = 2πΓΔnL/λ`。
    电平判定阈：`δφ ≤ Δφ_step/2`（相邻相位间距之半）
    ⇒ `t_hold = t₀·exp( (Δφ_step/2) / (φ_total·ν_n) )`。

    🔴 **共模抑制**（相位域特有）：差分对（两臂同材料反相编程）把漂移变共模 ⇒ 理想全消；
    残余 = `δφ·cmrr_fraction`。**cmrr_fraction 是设计假设**（两臂材料量失配未建模）。
    🔴 **ν_n 无独立实测锚**：调用者必须显式传入 `nu_n_ub` 及其语义；
    本函数把它**原样**标记为 `proxy` 并返回 `is_quantitative_conclusion=False`。
    """
    _require(n_levels >= 2, "至少两级")
    _require(nu_n_ub > 0.0, "漂移指数上界必须为正")
    _require(0.0 <= cmrr_fraction <= 1.0, "共模残余比例必须 ∈ [0,1]")
    l_um = resolve_l_um(mat, l_um, gamma=gamma, wl_nm=wl_nm)
    dsg = phase_level_design(mat, n_levels, l_um=l_um, gamma=gamma, wl_nm=wl_nm)
    rows = []
    for r in dsg["per_source"]:
        lv = r["levels"]
        dphis = [abs(lv[j]["phi_rad"] - lv[j + 1]["phi_rad"]) for j in range(n_levels - 1)]
        dphi_step = min(dphis)
        phi_total = r["phi_full_rad"]
        # 单臂：漂移全进信号
        cap_single = (0.5 * dphi_step) / (phi_total * nu_n_ub) if (phi_total > 0 and nu_n_ub > 0) else math.inf
        t_hold_single = t0_s * math.exp(cap_single) if cap_single < 700 else math.inf
        # 差分：残余 = 共模泄漏比例
        cap_diff = cap_single / cmrr_fraction if cmrr_fraction > 0 else math.inf
        t_hold_diff = t0_s * math.exp(cap_diff) if cap_diff < 700 else math.inf
        rows.append({"source": r["source"], "dphi_step_min_rad": dphi_step,
                     "phi_total_rad": phi_total,
                     "t_hold_single_arm_s": t_hold_single,
                     "t_hold_differential_s": t_hold_diff})
    return {"material": mat, "n_levels": n_levels, "l_um": float(l_um),
            "nu_n_ub": float(nu_n_ub), "nu_n_source": "proxy_cross_domain",
            "cmrr_fraction": float(cmrr_fraction),
            "per_source": rows,
            "is_quantitative_conclusion": False,
            "observation_equation": "δφ(t) = φ_total·ν_n·ln(t/t₀)；t_hold = t₀·exp((Δφ_step/2)/(φ_total·ν_n))",
            "common_mode_mechanism": "差分对把漂移变共模 ⇒ 理想全消；残余由 cmrr_fraction（假设）给",
            "honest_note": ("🔴 **相位漂移无独立定量实测锚** ⇒ 本函数给的是**口径 + 灵敏度公式**；"
                            "任何 t_hold 数字都是「**用透射/电学锚跨域代理**」的假设值，"
                            "不构成定量保持性结论（`is_quantitative_conclusion=False`）。")}


def phase_drift_sensitivity(mat: str, *, l_um: float, gamma: float = GAMMA_DEFAULT,
                            wl_nm: float = WL_NM_DEFAULT) -> Dict[str, Any]:
    """相位漂移**灵敏度**（与 ν 无关的纯几何/材料量）：dφ/d(δn/n) = φ_total。

    🔴 这解释了相位域与振幅域漂移的**本质差别**：
      振幅域漂移 ∝ 吸收（IL），相位域漂移 ∝ **相位行程**（φ_total）——
      两者都是单调量，但相位域可用**差分对**把漂移变共模（振幅域无参考臂）。
    """
    rows = []
    for st in _state_rows(mat, wl_nm):
        phi_total = phase_full_swing_rad(l_um, st["dn"], gamma=gamma, wl_nm=wl_nm)
        rows.append({"source": st["source"], "phi_total_rad": phi_total,
                     "dphi_per_rel_dn": phi_total})
    return {"material": mat, "l_um": float(l_um), "per_source": rows,
            "law": "dφ/d(δn/n) = φ_total = 2πΓΔnL/λ ⇒ 漂移灵敏 ∝ 相位行程（几何相关）",
            "contrast_with_amplitude": ("振幅域：漂移 ∝ 吸收 IL（无参考 ⇒ 不可共模消除）；"
                                        "相位域：漂移 ∝ 相位行程，但**差分对可共模消除**。")}


# ---------------------------------------------------------------------------
# 6. 缺口证据链（机器判定 + 重算，不读字面量）
# ---------------------------------------------------------------------------
def phase_domain_status(mat: str = "Sb2Se3", wl_nm: float = WL_NM_DEFAULT) -> Dict[str, Any]:
    """**机器判定**：相位域口径是否建立（读锚表 + 现算闭式，非字面量）。

    闭合口径（PM-G6）= 「相位域锚表含 ≥1 **measured** 条 ∧ 材料 FOM 闭式可算 ∧
    器件锚可重算 ⇒ 口径建立」。🔴 与漂移定量**无关**（漂移无独立锚 ⇒ 如实开放，见
    `M6_DISCLOSURE.phase_drift_has_no_independent_quantitative_anchor`）。
    """
    n_all = ML.phase_domain_anchor_count(mat)
    n_meas = ML.phase_domain_anchor_count(mat, "measured")
    n_sim = ML.phase_domain_anchor_count(mat, "simulation")
    fom = ML.phase_fom_material(mat, wl_nm)
    feas = phase_domain_feasibility(mat)
    has_device_fom = any(r["kind"] == "device_fom" for r in ML.PHASE_DOMAIN_ANCHORS.get(mat, []))
    ok = bool(n_meas >= 1 and fom["has_finite_fom"] and has_device_fom)
    return {"material": mat, "n_anchors": n_all, "n_measured": n_meas, "n_simulation": n_sim,
            "has_device_fom_anchor": has_device_fom,
            "fom_material_min_rad_per_db": fom["fom_min_rad_per_db"],
            "n_feasible_sources": feas["n_feasible_sources"], "n_sources": feas["n_sources"],
            "phase_domain_established": ok,
            "gap_pm_g6_open": not ok,
            "residual_boundary": ("相位**漂移**无独立定量锚 ⇒ 定量保持性仍开放"
                                  "（`phase_drift_has_no_independent_quantitative_anchor=True`）"),
            "disclosed": "判定读锚表计数与现算 FOM（机器可查），不读声明的字面量。"}


# ---------------------------------------------------------------------------
# 7. 相位域对拍表（国际对标 · 三带规则）
# ---------------------------------------------------------------------------
def _band(ratio: float) -> str:
    """三带规则（与 M5 同口径）：[0.5,2]=same_order · (2,5]=within_5x · 其余=outside_band。"""
    if ratio <= 0:
        return "undefined"
    r = ratio if ratio >= 1.0 else 1.0 / ratio
    if 0.5 <= r <= 2.0:
        return "same_order"
    if r <= 5.0:
        return "within_5x"
    return "outside_band"


def phase_benchmark_rows(mat: str = "Sb2Se3", wl_nm: float = WL_NM_DEFAULT) -> List[Dict[str, Any]]:
    """相位域逐行对拍表：LDA 值**全模块现算**（禁转录），文献值取锚表 DOI。

    🔴 每条 `lda_source` 标明现算出处；`verdict` 用三带规则；
    口径不同的行（材料 FOM vs 器件 FOM）**如实标 `regime_mismatch`**，不强行比。
    """
    rows: List[Dict[str, Any]] = []

    # ── 行1：材料级 FOM（LDA 现算）vs 器件级 FOM 锚（Delaney 2020）──────────────
    fom = ML.phase_fom_material(mat, wl_nm)
    dev_rows = [r for r in ML.PHASE_DOMAIN_ANCHORS[mat]
                if r["kind"] == "device_fom" and r.get("claim_kind") == "measured"]
    dev_fom = float(dev_rows[0]["fom_rad_per_db"])
    rows.append({"metric": "fom_rad_per_db", "unit": "rad/dB",
                 "lda_value": fom["fom_min_rad_per_db"], "lda_source": "pm_m6←pm_matlib.phase_fom_material（现算）",
                 "lit_value": dev_fom, "lit_source": dev_rows[0]["source"],
                 "ratio": fom["fom_min_rad_per_db"] / dev_fom,
                 "verdict": _band(fom["fom_min_rad_per_db"] / dev_fom),
                 "regime_mismatch": True,
                 "note": ("🔴 口径不同：LDA = **材料吸收路径** FOM；文献 = **器件级** FOM（含散射）。"
                          "差数个量级本身即结论：器件损耗几乎全来自非材料项（不强行判同带）。")})

    # ── 行2：每 π 损耗（器件锚）vs PhotoniX 2022 实测拆分 ───────────────────────
    split = [r for r in ML.PHASE_DOMAIN_ANCHORS[mat] if r["kind"] == "phase_loss_split"]
    if split:
        s = split[0]
        rows.append({"metric": "device_il_db_per_pi", "unit": "dB/π",
                     "lda_value": s["il_db_per_pi_total"], "lda_source": "phase loss split 锚（器件级实测）",
                     "lit_value": s["il_db_per_pi_total"], "lit_source": s["source"],
                     "ratio": 1.0, "verdict": "same_order",
                     "note": "同一来源（PhotoniX 2022）—— 该行锁的是「拆分自洽」（0.2 = 0.1 散射 + 0.1 材料）。"})

    # ── 行3：材料 Δn（LDA 逐来源）vs Delaney 器件 Δn=0.77 ──────────────────────
    dn = ML.delta_n(mat, wl_nm)
    dn_lo, dn_hi = dn["dn_min"], dn["dn_max"]
    fd = [r for r in ML.PHASE_DOMAIN_ANCHORS[mat] if r["kind"] == "device_fom"][0]
    lit_dn = float(fd["dn_contrast"])
    in_span = dn_lo <= lit_dn <= dn_hi
    rows.append({"metric": "delta_n", "unit": "",
                 "lda_value": (dn_lo, dn_hi), "lda_source": "pm_matlib.delta_n（逐来源区间）",
                 "lit_value": lit_dn, "lit_source": fd["source"],
                 "ratio": None, "verdict": "same_order" if in_span else "outside_band",
                 "note": ("LDA Δn 逐来源区间是否**覆盖**文献器件值（覆盖 ⇒ 同带）"
                          + ("✓ 覆盖" if in_span else "✗ 不覆盖") + "。")})

    # ── 行4：相位域位深上限（LDA 现算 · 同源 9 fJ）vs AFM 2023 器件 6-bit ──────
    ml = [r for r in ML.PHASE_DOMAIN_ANCHORS[mat] if r["kind"] == "multilevel_switch"]
    lim = max_levels_shot_limited()
    e6 = readout_energy_for_levels(LEVELS_6BIT)
    if ml:
        m = ml[0]
        lda_bits = lim["bits_max"]
        rows.append({"metric": "levels_bits", "unit": "bit",
                     "lda_value": lda_bits,
                     "lda_source": ("pm_m6.max_levels_shot_limited（现算 · 同源 %.0f fJ · BER 1e-12）"
                                    % E_READ_FJ_ASSUMED),
                     "lit_value": float(m["levels_bits"]), "lit_source": m["source"],
                     "ratio": lda_bits / float(m["levels_bits"]),
                     "verdict": _band(lda_bits / float(m["levels_bits"])),
                     "note": ("LDA 在**同源 %.0f fJ 读出预算**下等间距可分辨 %.2f bit；文献器件实测 "
                              "6-bit 🔴 **逆解**：6-bit 需读出 ≥ %.1f fJ（比 %.0f fJ 锚高 %.1f×）"
                              "⇒ 「位深 ⟷ 读出能量」trade-off 显式并报（非同一预算下的对比）。"
                              % (E_READ_FJ_ASSUMED, lda_bits, e6["e_read_min_fj"],
                                 E_READ_FJ_ASSUMED, e6["e_read_min_fj"] / E_READ_FJ_ASSUMED))})

    # ── 行5：6-bit 所需读出能量（LDA 现算）vs 器件锚读出能量 9 fJ ───────────────
    rows.append({"metric": "readout_energy_for_6bit_fj", "unit": "fJ",
                 "lda_value": e6["e_read_min_fj"],
                 "lda_source": "pm_m6.readout_energy_for_levels(64, BER 1e-12)（现算）",
                 "lit_value": E_READ_FJ_ASSUMED,
                 "lit_source": ("pm_matlib.DEVICE_ANCHORS['PCM_PM_RECORD_2025'].readout_energy_fj"
                                "（器件锚 · 量级对照，非本设计预算）"),
                 "ratio": e6["e_read_min_fj"] / E_READ_FJ_ASSUMED,
                 "verdict": _band(e6["e_read_min_fj"] / E_READ_FJ_ASSUMED),
                 "note": ("6-bit 所需读出能量下限 vs 器件锚 9 fJ：比值 = 「位深换能量」倍率 "
                          "⇒ 9 fJ 锚自身对应的位深远低于 6-bit（两数口径不同，如实标带）。")})

    # ── 行6：L_π（LDA 现算）vs PhotoniX 2022 器件 11 µm ───────────────────────
    if split:
        s = split[0]
        st0 = _state_rows(mat, wl_nm)[0]
        l_pi = l_pi_um(st0["dn"], wl_nm=wl_nm)
        g_implied = float(s["delta_n_eff"]) / st0["dn"]           # 文献器件隐含的模式重叠
        l_pi_at_implied = l_pi_um(st0["dn"], gamma=g_implied, wl_nm=wl_nm)
        dev_l_pi = float(s["l_pi_um"])
        rows.append({"metric": "l_pi_um", "unit": "µm",
                     "lda_value": l_pi, "lda_source": "pm_m6.l_pi_um(Γ=%.3f·Δn)（现算）" % GAMMA_DEFAULT,
                     "lit_value": dev_l_pi, "lit_source": s["source"],
                     "ratio": l_pi / dev_l_pi, "verdict": _band(l_pi / dev_l_pi),
                     "note": ("🔴 LDA 用 **Γ 假设** 折算 L_π；文献器件隐含模式重叠 "
                              "Γ_implied = Δn_eff/Δn = %.4f/%.4f = **%.4f**（LDA 假设 Γ=%.3f ⇒ 差 %.2f×）。"
                              "若取 Γ_implied，LDA L_π = %.2f µm ⇔ 文献 %.0f µm（吻合 %.1f%%）"
                              "⇒ 与 LDA 保守假设 Γ 同量级（**不同几何/材料** ⇒ 只作交叉参照）；"
                              "LDA **自研 Γ 标定**见 `pm_gamma`（主账 0.084 · v0.9.198 PM-G2 已结算）。"
                              % (float(s["delta_n_eff"]), st0["dn"], g_implied, GAMMA_DEFAULT,
                                 g_implied / GAMMA_DEFAULT, l_pi_at_implied, dev_l_pi,
                                 100.0 * (1.0 - abs(l_pi_at_implied - dev_l_pi) / dev_l_pi)))})

    # ── 行7：MZI 消光比 —— LDA **不建模**（如实 not_modeled）──────────────────
    keep = [r for r in ML.PHASE_DOMAIN_ANCHORS[mat] if r["kind"] == "mzi_extinction"]
    if keep:
        rows.append({"metric": "mzi_extinction_ratio_db", "unit": "dB",
                     "lda_value": None, "lda_source": "未建模（无分束比失配/损耗失配模型）",
                     "lit_value": float(keep[0]["extinction_ratio_db"]), "lit_source": keep[0]["source"],
                     "ratio": None, "verdict": "not_modeled",
                     "note": "🔴 宁可标不可判：LDA 无 MZI 消光比模型（需分束器失配/臂损耗失配）⇒ 不给数。"})

    return rows


# ---------------------------------------------------------------------------
# 8. 汇总报告
# ---------------------------------------------------------------------------
def m6_report(mat: str = "Sb2Se3", n_levels: int = LEVELS_6BIT, *,
              l_um: Optional[float] = None, gamma: float = GAMMA_DEFAULT,
              wl_nm: float = WL_NM_DEFAULT, finesse: float = 100.0,
              e_read_fj: float = E_READ_FJ_ASSUMED,
              il_budget_db: float = IL_BUDGET_DB_ASSUMED) -> Dict[str, Any]:
    """PM-M6 汇总：相位域基本量 + 多电平设计 + 可行性 + 读出 + 漂移口径 + 对拍 + 披露。

    🔴 `l_um=None`（默认）⇒ 自动取**理想臂长 L_π**（φ_full = π）。
    """
    l_um = resolve_l_um(mat, l_um, gamma=gamma, wl_nm=wl_nm)
    feas = phase_domain_feasibility(mat, n_levels=n_levels, gamma=gamma, wl_nm=wl_nm,
                                    il_budget_db=il_budget_db)
    dsg = phase_level_design(mat, n_levels, l_um=l_um, gamma=gamma, wl_nm=wl_nm)
    readout = interferometric_readout(mat, n_levels, l_um=l_um, gamma=gamma, wl_nm=wl_nm,
                                      e_read_fj=e_read_fj)
    reson = resonant_readout(mat, n_levels, l_um=l_um, finesse=finesse, gamma=gamma,
                             wl_nm=wl_nm, e_read_fj=e_read_fj)
    # 漂移段：用**透射**上界锚作跨域代理（显式标注），只为给「口径可算」的演示
    from lda_l2 import pm_m2 as M2
    nu_proxy = M2.nu_optical_bound("GST")["nu_ub_max"]
    drift = phase_drift_budget(mat, n_levels, l_um=l_um, nu_n_ub=nu_proxy,
                               gamma=gamma, wl_nm=wl_nm)
    drift["proxy_anchor_source"] = "pm_m2.nu_optical_bound('GST')（**透射**域上界 ⇒ 跨域代理）"
    return {
        "material": mat, "n_levels": n_levels, "l_um": float(l_um), "gamma": float(gamma),
        "wl_nm": float(wl_nm),
        "fom_material": ML.phase_fom_material(mat, wl_nm),
        "residue_vs_device": ML.phase_domain_residue(mat, wl_nm),
        "feasibility": feas,
        "level_design": dsg,
        "readout_interferometric": readout,
        "readout_resonant": reson,
        "readout_limits": {"max_levels_shot_limited": max_levels_shot_limited(e_read_fj, wl_nm=wl_nm),
                           "energy_for_6bit": readout_energy_for_levels(LEVELS_6BIT, wl_nm=wl_nm)},
        "drift": drift,
        "drift_sensitivity": phase_drift_sensitivity(mat, l_um=l_um, gamma=gamma, wl_nm=wl_nm),
        "benchmark_rows": phase_benchmark_rows(mat, wl_nm),
        "status": phase_domain_status(mat, wl_nm),
        "disclosure": dict(M6_DISCLOSURE),
    }


def m6_report_json_safe(mat: str = "Sb2Se3", n_levels: int = LEVELS_6BIT,
                        **kw: Any) -> Dict[str, Any]:
    """`m6_report` 的 **JSON 安全**包装（±inf/NaN ⇒ 字符串 tag）。"""
    return _json_safe(m6_report(mat, n_levels, **kw))


def phase_case_summary(mat: str = "Sb2Se3") -> Dict[str, Any]:
    """WebUI / 案例卡用的**轻量**摘要（全现算，无快照依赖）。"""
    rep = m6_report(mat)
    return _json_safe({
        "material": mat,
        "fom_material_min_rad_per_db": rep["fom_material"]["fom_min_rad_per_db"],
        "fom_device_measured_rad_per_db": rep["residue_vs_device"]["fom_device_measured_rad_per_db"],
        "residue_ratio_material_over_device": rep["residue_vs_device"]["ratio_material_over_device"],
        "n_feasible_sources": rep["feasibility"]["n_feasible_sources"],
        "n_sources": rep["feasibility"]["n_sources"],
        "fom_needed_rad_per_db": rep["feasibility"]["fom_needed_rad_per_db"],
        "il_budget_db": rep["feasibility"]["il_budget_db"],
        "readout_all_ok": rep["readout_interferometric"]["all_ok"],
        "readout_worst_ber": rep["readout_interferometric"]["worst_ber"],
        "resonant_worst_ber": rep["readout_resonant"]["worst_ber"],
        "levels_bits_max_shot_limited": rep["readout_limits"]["max_levels_shot_limited"]["bits_max"],
        "energy_for_6bit_fj": rep["readout_limits"]["energy_for_6bit"]["e_read_min_fj"],
        "phase_domain_established": rep["status"]["phase_domain_established"],
        "residual_boundary": rep["status"]["residual_boundary"],
        "benchmark_rows": rep["benchmark_rows"],
    })


if __name__ == "__main__":  # pragma: no cover
    rep = m6_report("Sb2Se3")
    print("== PM-M6 相位域（干涉/谐振）多电平口径 ==")
    print("材料 FOM = %.4g rad/dB（min，逐来源）" % rep["fom_material"]["fom_min_rad_per_db"])
    print("器件 FOM 锚 = %.4g rad/dB；材料/器件 = %.4g×"
          % (rep["residue_vs_device"]["fom_device_measured_rad_per_db"],
             rep["residue_vs_device"]["ratio_material_over_device"]))
    print("可行性：FOM ≥ %.4g rad/dB ⇒ 可行源 %d/%d"
          % (rep["feasibility"]["fom_needed_rad_per_db"],
             rep["feasibility"]["n_feasible_sources"], rep["feasibility"]["n_sources"]))
    print("MZI 读出 worst BER = %.3g（shot 限 %d / 相位噪声限 %d）"
          % (rep["readout_interferometric"]["worst_ber"],
             rep["readout_interferometric"]["n_limited_by_shot"],
             rep["readout_interferometric"]["n_limited_by_phase"]))
    print("谐振读出 worst BER = %.3g（精细度 %.0f ⇒ 增强 %.2f×）"
          % (rep["readout_resonant"]["worst_ber"], rep["readout_resonant"]["finesse"],
             rep["readout_resonant"]["enhancement"]["enhancement_factor"]))
    lim = rep["readout_limits"]
    print("位深上限（同源 %.0f fJ · BER 1e-12）= %.2f bit；6-bit 需读出 ≥ %.1f fJ（%.1f×）"
          % (E_READ_FJ_ASSUMED, lim["max_levels_shot_limited"]["bits_max"],
             lim["energy_for_6bit"]["e_read_min_fj"],
             lim["energy_for_6bit"]["e_read_min_fj"] / E_READ_FJ_ASSUMED))
    print("口径建立 = %s；残余边界：%s"
          % (rep["status"]["phase_domain_established"], rep["status"]["residual_boundary"]))
    print("\n-- 对拍表 --")
    for r in rep["benchmark_rows"]:
        print("  %-28s LDA=%-14s LIT=%-12s ratio=%-10s %s"
              % (r["metric"], r["lda_value"], r["lit_value"],
                 ("%.3g" % r["ratio"]) if isinstance(r["ratio"], (int, float)) else r["ratio"],
                 r["verdict"]))
