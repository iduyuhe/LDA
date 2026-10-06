"""PM-M1：多电平设计层 —— JMAK 晶化动力学（闭合 PM-G4）+ 脉冲阶梯 + 电平容量。

征程位置：光子存储 PM-M1（蓝图 `docs/LDA_光子存储芯片征程_总蓝图_v1_2026-10-04.md`）。
本模块在 PM-M0（单元双态闭式层）之上回答三问：
  1. 编程脉冲怎么给？—— JMAK 等温晶化动力学：X = 1 − exp(−k(T)·t^n)，
     闭式解 t = (θ/k(T))^(1/n)，θ = −ln(1−c)。全部设计结论（阶梯比、温度标度）**对 K0 不变**。
  2. 电平阶梯怎么设？—— **等透射率间距**（读出域等距）：T_j 闭式反演 c_j（精确，
     因线性混合下 IL(c) 严格线性于 c）。
  3. 能装几个 bit？—— 🔴 **M1 核心律（几何无关可行性判据）**：
       16 级 · 间距 ≥6% · BER ≤ 目标 ⇒ 可行 ⇔ r = k_a/(k_c−k_a) ≤ r_max，
       其中 r_max = −log10(T_a_min)，T_a_min = (2(L−1)·SNR_req)²/n_ph。
     推导：间距与读出 BER 都随 L 单调，且 contrast(L)、IL_a(L) 同 ∝L ⇒
     L 增大先满足间距、后饿死光子预算 ⇒ 可行 ⇔ 在 L_swing（恰好 10 dB 对比度）处
     T_a = 10^(−r) 仍 ≥ T_a_min。**Γ 与 L 同时约掉** —— 与 M0 的 IL_π=(10/ln10)·2πk/Δn 同族。

主账纪律（与 pm_m0 同）：
- 判据只读**算出来的**值；K0 前因子无文献锚 ⇒ **不登记**，设计结论对 K0 不变（比值消去）。
- 跨来源离散（Ea 1.93–4.66 eV、n 1–4 / 薄膜 <1、k_c 0.1–1.55）一律**区间并报**。
- 能效只报设计预算量级；🔴 不报 TOPS/TOPS-W/fJ-op/pJ-bit 类指标。
- 假设显式标注（GAMMA、shot-noise 读出模型、n 扫描下界）。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from lda_l2 import pm_matlib as ML

KB_EV: float = 8.617333262e-5          # 玻尔兹曼常数 eV/K（CODATA）
GAMMA_DEFAULT: float = 0.05            # 沿用 M0 **假设**值（Γ 已有自研标定 pm_gamma≈0.084 · PM-G2 v0.9.198
                                       #   结算）；🔴 L ∝ 1/Γ ⇒ 本值偏小 ⇒ 设计点偏长且**会越出**
                                       #   标定口径可行窗（缺口 PM-G11 · 两口径并报）
WL_NM_DEFAULT: float = 1550.0
READ_ENERGY_FJ_ASSUMED: float = 9.0    # 与 M0 同源（shot-noise 简化用）
BER_TARGET: float = 1.0e-12
MARGIN_REQ_DEFAULT: float = 0.06       # 文献锚「4 bit @ 6% 间距」的间距口径
LEVELS_4BIT: int = 16
LEVELS_7BIT: int = 128
#: 🔴 n 扫描下界 0.5 是**设计假设**（Wei 只给 n<1，未给下界）—— 显式标注。
N_SCAN_ASSUMED: Tuple[float, ...] = (0.5, 1.0, 2.0, 4.0)
ASSUMED_NOTE = ("K0 前因子无文献锚 ⇒ 绝对脉冲时长不可报真值；"
                "全部设计结论（阶梯比、温度标度、电平容量）对 K0 不变。")


class PMM1Error(Exception):
    """PM-M1 域错误（越域 = 模型失效，拒绝静默截断）。"""


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise PMM1Error(msg)


# ---------------------------------------------------------------------------
# 1. JMAK 晶化动力学（PM-G4 闭线）
# ---------------------------------------------------------------------------
def kinetic_sources(mat: str = "GST") -> List[Dict[str, Any]]:
    """JMAK 文献锚逐源表（字段级消费审计：缺字段的来源显式排除并记录）。"""
    _require(mat in ML.JMAK_PARAMS, f"无 JMAK 锚：{mat}")
    out = []
    for a in ML.JMAK_PARAMS[mat]:
        ea = a.get("ea_ev")
        n_max = a.get("n_max") if a.get("n_max") is not None else a.get("n_max_thin")
        rec: Dict[str, Any] = {"source": a["source"], "note": a.get("note", ""),
                               "film_context_nm": a.get("film_context_nm")}
        if ea is not None:
            rec["ea_ev"] = float(ea)
            rec["ea_lo_ev"] = float(ea - a["ea_ev_err"]) if a.get("ea_ev_err") is not None else float(ea)
            rec["ea_hi_ev"] = float(a.get("ea_ev_thin_ev", ea))
        else:
            rec["ea_ev"] = None           # 字段级审计：缺字段 ⇒ 显式 None，不借他源合成
        rec["n_max"] = float(n_max) if n_max is not None else None
        rec["n_min"] = float(a["n_min"]) if a.get("n_min") is not None else None
        out.append(rec)
    return out


def ea_scan_bounds(mat: str = "GST") -> Tuple[float, float]:
    """Ea 扫描区间（跨源算出来的 min/max，含误差棒下探与减厚上探）。"""
    srcs = kinetic_sources(mat)
    los = [s["ea_lo_ev"] for s in srcs if s["ea_lo_ev"] is not None]
    his = [s["ea_hi_ev"] for s in srcs if s["ea_hi_ev"] is not None]
    _require(los and his, "JMAK 锚缺 Ea 字段 ⇒ 无法定扫描区间（宁缺毋滥）")
    return min(los), max(his)


def rate_at(T_k: float, ea_ev: float, k0: float) -> float:
    """Arrhenius 速率 k(T) = K0·exp(−Ea/(kB·T))。"""
    _require(T_k > 0.0 and ea_ev > 0.0 and k0 > 0.0, "T/Ea/K0 必须为正")
    return k0 * math.exp(-ea_ev / (KB_EV * T_k))


def cryst_frac(t_s: float, T_k: float, ea_ev: float, n: float, k0: float) -> float:
    """JMAK 等温晶化率 X(t,T) = 1 − exp(−k(T)·t^n)。"""
    _require(n > 0.0 and t_s >= 0.0, "n 必须为正、t 非负")
    theta = rate_at(T_k, ea_ev, k0) * (t_s ** n)
    return 1.0 - math.exp(-theta)


def pulse_time_for_x(x: float, T_k: float, ea_ev: float, n: float, k0: float) -> float:
    """目标晶化率的闭式脉冲时长：t = (θ/k)^(1/n)，θ = −ln(1−x)。"""
    _require(0.0 < x < 1.0, f"目标晶化率必须 ∈ (0,1)，收到 {x!r}")
    theta = -math.log(1.0 - x)
    return (theta / rate_at(T_k, ea_ev, k0)) ** (1.0 / n)


def temperature_scaling(T1_k: float, T2_k: float, ea_ev: float) -> Dict[str, float]:
    """温度标度律（闭式）：t2/t1 = exp(Ea/kB·(1/T2 − 1/T1)) —— **K0 无关**。

    恒等式：(t2/t1)^n = k1/k2（脉冲时长 ∝ k^(−1/n)）。
    """
    _require(T1_k > 0.0 and T2_k > 0.0, "温度必须为正")
    r_time = math.exp(ea_ev / KB_EV * (1.0 / T2_k - 1.0 / T1_k))   # t2/t1
    r_rate = math.exp(ea_ev / KB_EV * (1.0 / T1_k - 1.0 / T2_k))   # k2/k1 = 1/r_time
    return {"time_ratio_t2_over_t1": r_time, "rate_ratio_k2_over_k1": r_rate}


def pulse_ladder(c_levels: Tuple[float, ...], T_k: float, ea_ev: float, n: float,
                 k0: float = 1.0) -> List[Dict[str, float]]:
    """编程脉冲阶梯：每级目标晶化率的脉冲时长。t_j = (θ_j/k)^(1/n)。

    k0 默认 1.0 ⇒ 返回值是**归一化时长**（对 K0 不变的设计量）；
    传真 K0 才得绝对时长（本库不提供 K0 ⇒ 调用者自担假设并标注）。
    """
    _require(len(c_levels) >= 2, "至少两级")
    _require(all(0.0 < c < 1.0 for c in c_levels), "晶化率必须 ∈ (0,1)")
    _require(n > 0.0, f"Avrami 指数必须为正，收到 {n!r}（越域是模型失效，拒绝静默）")
    rows = []
    for c in c_levels:
        theta = -math.log(1.0 - c)
        t = (theta / rate_at(T_k, ea_ev, k0)) ** (1.0 / n)
        rows.append({"c": c, "theta": theta, "t_rel": t})
    t1 = rows[0]["t_rel"]
    for r in rows:
        r["t_ratio_to_first"] = r["t_rel"] / t1
    return rows


def jmak_law_check(mat: str = "GST", *, T_ref_k: float = 800.0,
                   k0: float = 1.0) -> Dict[str, Any]:
    """PM-G4 闭线证据（**算出来的**）：Arrhenius 标度律两条独立路径一致性。

    恒等式 (t2/t1)^n = k1/k2：路径 A 经 pulse_time_for_x 反演、路径 B 经
    temperature_scaling 直算 —— 计算路径不同 ⇒ 内部一致性真检验；
    「改上游常量会红吗」由 run_pm_m1_smoke 探针 P1 负责（改 Ea ⇒ 比值必变）。
    """
    worst = 0.0
    n = 2.0
    for ea in {kinetic_sources(mat)[0]["ea_ev"], ea_scan_bounds(mat)[1]}:
        t1 = pulse_time_for_x(0.9, T_ref_k, ea, n, k0)
        t2 = pulse_time_for_x(0.9, T_ref_k * 1.25, ea, n, k0)
        a = (t2 / t1) ** n                                    # = k1/k2
        b = 1.0 / temperature_scaling(T_ref_k, T_ref_k * 1.25, ea)["rate_ratio_k2_over_k1"]
        worst = max(worst, abs(a - b) / b)
    return {"ok": worst < 1e-12, "max_rel_dev": worst, "assumed_note": ASSUMED_NOTE}


# ---------------------------------------------------------------------------
# 2. 多电平：等透射率间距 + 闭式反演
# ---------------------------------------------------------------------------
def _state_ka_kc(mat: str, wl_nm: float) -> List[Dict[str, Any]]:
    """逐来源 (k_a, k_c) 配对表（两态来源不配对 ⇒ raise，与 M0 同政策）。"""
    a = {(n, k, s) for n, k, s in ML.nk_sources(mat, "amorphous", wl_nm)}
    rows = []
    for n_c, k_c, s in ML.nk_sources(mat, "crystalline", wl_nm):
        pair = [x for x in a if x[2] == s]
        _require(len(pair) == 1, f"{mat}：来源 {s!r} 两态不配对")
        n_a, k_a, _ = pair[0]
        rows.append({"k_a": k_a, "k_c": k_c, "n_a": n_a, "n_c": n_c, "source": s})
    return rows


def il_of_c(c: float, k_a: float, k_c: float, *, l_um: float,
            gamma: float = GAMMA_DEFAULT, wl_nm: float = WL_NM_DEFAULT) -> float:
    """IL(c) = (10/ln10)·Γ·(4π/λ)·k_eff(c)·L —— 线性混合下 **严格线性于 c**。"""
    _require(0.0 <= c <= 1.0, f"晶化率越域 [0,1]：{c!r}（越域是模型失效，拒绝截断）")
    lam_m = wl_nm * 1e-9
    k_eff = k_a + c * (k_c - k_a)
    return (10.0 / math.log(10.0)) * gamma * (4.0 * math.pi * k_eff / lam_m) * (l_um * 1e-6)


def level_design(mat: str, n_levels: int, *, l_um: float,
                 gamma: float = GAMMA_DEFAULT, wl_nm: float = WL_NM_DEFAULT) -> Dict[str, Any]:
    """等透射率间距电平设计（逐来源 + 区间）。

    T_j = T_c + j·ΔT，ΔT = (T_a − T_c)/(L−1)；闭式反演 c_j = (IL_j − IL_a)/(IL_c − IL_a)
    （IL 线性于 c ⇒ 反演**精确**，无数值误差项）。
    """
    _require(n_levels >= 2, "至少两级")
    _require(l_um > 0.0, "L 必须为正")
    rows = []
    for st in _state_ka_kc(mat, wl_nm):
        il_a = il_of_c(0.0, st["k_a"], st["k_c"], l_um=l_um, gamma=gamma, wl_nm=wl_nm)
        il_c = il_of_c(1.0, st["k_a"], st["k_c"], l_um=l_um, gamma=gamma, wl_nm=wl_nm)
        t_a = 10.0 ** (-il_a / 10.0)
        t_c = 10.0 ** (-il_c / 10.0)
        dt = (t_a - t_c) / (n_levels - 1)
        levels = []
        for j in range(n_levels):
            t_j = t_c + j * dt
            il_j = -10.0 * math.log10(t_j)
            c_j = (il_j - il_a) / (il_c - il_a)
            levels.append({"j": j, "T": t_j, "c": c_j})
        rows.append({"source": st["source"], "il_a_db": il_a, "il_c_db": il_c,
                     "t_a": t_a, "t_c": t_c,
                     "spacing_frac": dt / t_a if t_a > 0 else 0.0,
                     "levels": levels,
                     "contrast_db": (10.0 * math.log10(t_a / t_c)) if t_c > 0 else math.inf})
    fin = [r for r in rows if math.isfinite(r["contrast_db"])]
    return {"material": mat, "n_levels": n_levels, "l_um": float(l_um), "gamma": gamma,
            "wl_nm": float(wl_nm), "per_source": rows,
            "spacing_frac_min": min(r["spacing_frac"] for r in rows),
            "spacing_frac_max": max(r["spacing_frac"] for r in rows),
            "contrast_min_db": min(r["contrast_db"] for r in fin),
            "contrast_max_db": max(r["contrast_db"] for r in fin)}


# ---------------------------------------------------------------------------
# 3. 读出（shot-noise 简化）与几何无关可行性判据
# ---------------------------------------------------------------------------
def snr_req(ber: float) -> float:
    """反解 SNR 需求：0.5·erfc(s/√2) = ber（二分，纯 math 无 scipy 依赖）。"""
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
    """读出光子数 N = E/(hν)。"""
    _require(e_read_fj > 0.0, "读出能量必须为正")
    return e_read_fj * 1e-15 / (6.62607015e-34 * 2.99792458e8 / (wl_nm * 1e-9))


def amplitude_feasibility(mat: str, n_levels: int = LEVELS_4BIT, *,
                          margin_req: float = MARGIN_REQ_DEFAULT,
                          ber_target: float = BER_TARGET,
                          e_read_fj: float = READ_ENERGY_FJ_ASSUMED,
                          wl_nm: float = WL_NM_DEFAULT,
                          gamma: float = GAMMA_DEFAULT) -> Dict[str, Any]:
    """🔴 **M1 核心律**：振幅域多电平可行性判据（**Γ 与 L 同时约掉**）。

    推导：contrast(L) 与 IL_a(L) 同 ∝L。间距要求 contrast ≥ −10log10(1−margin·(L−1))，
    读出要求 T_a ≥ T_a_min = (2(L−1)·SNR_req)²/N_ph。两约束在 L 上反向单调 ⇒
    可行 ⇔ 在 L_swing（间距恰达标的最短 L）处 T_a = 10^(−r) ≥ T_a_min，
    r = k_a/(k_c−k_a)。**r 是纯材料比 ⇒ 可行性与 Γ、L 无关**（几何只定窗口位置）。
    """
    _require(n_levels >= 2, "至少两级")
    _require(margin_req * (n_levels - 1) < 1.0, "margin·(L−1) 必须 <1（否则间距口径无解）")
    s_req = snr_req(ber_target)
    nph = n_photons(e_read_fj, wl_nm)
    contrast_need_db = -10.0 * math.log10(1.0 - margin_req * (n_levels - 1))
    t_a_min = (2.0 * (n_levels - 1) * s_req) ** 2 / nph
    per = []
    for st in _state_ka_kc(mat, wl_nm):
        dk = st["k_c"] - st["k_a"]
        if dk <= 0.0 or st["k_c"] <= 0.0:
            per.append({"source": st["source"], "r": None, "feasible": False,
                        "reason": ("两态吸收比不构成振幅域对比（k_c≤k_a 或 k_c≈0）⇒ "
                                   "该材料的多电平须走**相位域**（口径见 `pm_m6` · PM-G6 已结算）"),
                        "t_a_min": t_a_min})
            continue
        r = st["k_a"] / dk
        t_a_at_swing = 10.0 ** (-r)                       # L_swing 处的非晶态透射率
        feasible = t_a_at_swing >= t_a_min
        # L 窗口：L_swing（间距恰达标）到 L_starve（T_a 跌破 T_a_min）
        lam_m = wl_nm * 1e-9
        db_per_um = (10.0 / math.log(10.0)) * gamma * (4.0 * math.pi * dk / lam_m) * 1e-6
        l_swing = contrast_need_db / db_per_um
        il_a_starve_db = -10.0 * math.log10(t_a_min)
        l_starve = il_a_starve_db / ((10.0 / math.log(10.0)) * gamma
                                     * (4.0 * math.pi * st["k_a"] / lam_m) * 1e-6) \
            if st["k_a"] > 0 else math.inf
        per.append({"source": st["source"], "r": r, "feasible": feasible,
                    "t_a_at_swing": t_a_at_swing, "t_a_min": t_a_min,
                    "l_swing_um": l_swing,
                    "l_starve_um": l_starve if math.isfinite(l_starve) else None,
                    "window_um": (l_swing, l_starve) if (feasible and l_starve > l_swing) else None})
    n_ok = sum(1 for p in per if p["feasible"])
    return {"material": mat, "n_levels": n_levels, "margin_req": margin_req,
            "ber_target": ber_target, "e_read_fj": e_read_fj,
            "contrast_need_db": contrast_need_db, "t_a_min": t_a_min,
            "snr_req": s_req, "n_photons": nph,
            "per_source": per, "n_feasible_sources": n_ok, "n_sources": len(per),
            "headline": ("可行性判据 r=k_a/(k_c−k_a) ≤ −log10(T_a_min) 与 Γ、L 无关"
                         "（几何只定窗口位置）；r_max=%.3f（16级·6%%·BER%.0e·%.0ffJ）。"
                         % (-math.log10(t_a_min), ber_target, e_read_fj))}


def level_readout_ber(mat: str, n_levels: int, *, l_um: float,
                      gamma: float = GAMMA_DEFAULT, wl_nm: float = WL_NM_DEFAULT,
                      e_read_fj: float = READ_ENERGY_FJ_ASSUMED,
                      ber_target: float = BER_TARGET) -> Dict[str, Any]:
    """相邻电平检出 BER（shot-noise 简化，与 M0 同模型同免责）。"""
    d = level_design(mat, n_levels, l_um=l_um, gamma=gamma, wl_nm=wl_nm)
    nph = n_photons(e_read_fj, wl_nm)
    pairs = []
    for r in d["per_source"]:
        ts = [lv["T"] for lv in r["levels"]]
        for j in range(n_levels - 1):
            dn = nph * (ts[j + 1] - ts[j])
            snr = dn / (2.0 * math.sqrt(max(nph * ts[j + 1], 1e-300)))
            ber = 0.5 * math.erfc(snr / math.sqrt(2.0))
            pairs.append({"source": r["source"], "pair": (j, j + 1), "snr": snr,
                          "ber": ber, "ok": ber <= ber_target})
    return {"material": mat, "n_levels": n_levels, "l_um": float(l_um),
            "e_read_fj": float(e_read_fj), "n_photons": nph, "pairs": pairs,
            "all_ok": all(w["ok"] for w in pairs),
            "worst_ber": max(w["ber"] for w in pairs),
            "model": "shot_noise_limited(assumption)",
            "honest_note": "🔴 简化模型（仅散粒噪声）⇒ 只作余量方向性判断，不作签核口径。"}


def seven_bit_readout_floor(*, n_levels: int = LEVELS_7BIT,
                            margin_req: float = MARGIN_REQ_DEFAULT,
                            ber_target: float = BER_TARGET,
                            wl_nm: float = WL_NM_DEFAULT) -> Dict[str, Any]:
    """7-bit 的读出光子数下限（**算出来**，不声称可实现）：

    T_a ≤ 1 ⇒ SNR_top = √(N_ph·T_a)·(1−T_c/T_a)/((L−1)·2) ≤ √N_ph/((L−1)·2)
    ⇒ N_ph ≥ (2(L−1)·SNR_req)²，E_read ≥ N_ph·hν。
    """
    s_req = snr_req(ber_target)
    nph_min = (2.0 * (n_levels - 1) * s_req) ** 2
    e_read_min_fj = nph_min * 6.62607015e-34 * 2.99792458e8 / (wl_nm * 1e-9) * 1e15
    return {"n_levels": n_levels, "margin_req": margin_req, "snr_req": s_req,
            "n_photons_min": nph_min, "e_read_min_fj": e_read_min_fj,
            "honest_note": ("shot-noise 简化下限：T_a→1 的理想透明非晶态 + 等透射率间距；"
                            "真实器件（插损/串扰/drift）只会更贵。209 级 / N-GST >7 bit "
                            "走电阻域动态范围，口径不同，不可直接对比。")}


# ---------------------------------------------------------------------------
# 4. 汇总报告
# ---------------------------------------------------------------------------
def m1_report(mat: str = "GST", n_levels: int = LEVELS_4BIT, *,
              gamma: float = GAMMA_DEFAULT, wl_nm: float = WL_NM_DEFAULT,
              margin_req: float = MARGIN_REQ_DEFAULT,
              e_read_fj: float = READ_ENERGY_FJ_ASSUMED) -> Dict[str, Any]:
    """PM-M1 汇总：JMAK 锚 + 脉冲阶梯 + 可行性 + 读出 + 披露。"""
    srcs = kinetic_sources(mat)
    ea_lo, ea_hi = ea_scan_bounds(mat)
    lad = pulse_ladder(tuple(0.1 + 0.8 * j / (n_levels - 1) for j in range(n_levels)),
                       800.0, srcs[0]["ea_ev"], 2.0)
    feas = amplitude_feasibility(mat, n_levels, margin_req=margin_req,
                                 e_read_fj=e_read_fj, wl_nm=wl_nm, gamma=gamma)
    law = jmak_law_check(mat)
    # 在首个可行源窗口中点验证整链（间距 + BER）——逐源对齐，不跨源取 min
    demo = None
    for p in feas["per_source"]:
        if p["feasible"] and p["window_um"]:
            l_mid = 0.5 * (p["window_um"][0] + min(p["window_um"][1], p["window_um"][0] * 3.0))
            dsg = level_design(mat, n_levels, l_um=l_mid, gamma=gamma, wl_nm=wl_nm)
            row = [x for x in dsg["per_source"] if x["source"] == p["source"]][0]
            ber = level_readout_ber(mat, n_levels, l_um=l_mid, gamma=gamma,
                                    wl_nm=wl_nm, e_read_fj=e_read_fj)
            pairs = [w for w in ber["pairs"] if w["source"] == p["source"]]
            demo = {"source": p["source"], "l_mid_um": l_mid,
                    "spacing_frac": row["spacing_frac"],
                    "spacing_ok": row["spacing_frac"] >= margin_req,
                    "readout_all_ok": all(w["ok"] for w in pairs),
                    "worst_ber": max(w["ber"] for w in pairs)}
            break
    return {
        "material": mat, "n_levels": n_levels,
        "jmak": {"sources": srcs, "ea_scan_bounds_ev": (ea_lo, ea_hi),
                 "n_scan_assumed": N_SCAN_ASSUMED, "law_check": law,
                 "ladder_first_last_ratio": lad[-1]["t_ratio_to_first"],
                 "k0_registered": False},
        "feasibility": feas,
        "demo_design_point": demo,
        "seven_bit_floor": seven_bit_readout_floor(),
        "disclosure": {
            "k0_is_assumption": True,
            "gamma_is_assumption": True,
            "readout_model_is_simplification": True,
            "n_lower_bound_is_assumption": True,
            "no_energy_efficiency_metrics": True,
        },
    }
