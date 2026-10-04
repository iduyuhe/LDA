"""PM-M2：瞬态热（PM-G3）+ 非晶 drift（PM-G5）—— 光子存储单元的热-可靠性层。

设计哲学（与 M0/M1 同族）：
- **材料比值定能力，几何只分配窗口**（M0：`IL_π` 与 Γ、L 同时约掉；M1：可行性判据 `r` 与 Γ、L 无关）；
- 一切数字**逐来源**报区间，不合成跨源单值；
- 缺锚 ⇒ raise 或**显式登记缺口**，绝不发明、绝不外推。

本层回答两个 M0/M1 刻意排除在外的物理：
1. **PM-G3 瞬态热**：reset 要把熔体淬火（速率 > ~10⁹ K/s）⇒
   ① 可非晶化**最大膜厚** `L_max`（超过则淬不成非晶）；② 冷却时间 `τ_cool` ⇒
   **写周期下限** = 脉冲宽 + `τ_cool`（Adv. Mater. 2024 对切换时间的定义）。
2. **PM-G5 非晶 drift**：结构弛豫 ⇒ power law `R = R₀·(t/t₀)^ν`（电学域锚充分）。
   本层给出**电学域可算判据**，并**机器判定光学域无直接锚** ⇒ 派生缺口 **PM-G7**。
"""

import math
from typing import Any, Dict, List, Optional, Tuple

from lda_l2 import pm_matlib as ML


class PMM2Error(Exception):
    """M2 热/可靠性层错误。"""


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise PMM2Error(msg)


T0_K_DEFAULT: float = 300.0            # 环境温度（drift/热预算参考点）
MARGIN_REQ_DEFAULT: float = 0.06       # M1 的「4 bit @ 6% 间距」口径（沿用，不另立）
LEVELS_4BIT: int = 16
SIGMA_MULT_DEFAULT: float = 3.0        # 分布展宽判据的 σ 倍数
#: 🔴 **假设**（非文献锚）：非晶/晶态电阻比的数量级。PCM 公开典型 ~10²–10⁴。
#: 只影响**电学域**保持窗口的绝对量级；对「对数域不变性」与「光学域无锚」两条结论**无影响**。
LOG_RANGE_DECADES_ASSUMED: float = 3.0
LOG_RANGE_SCAN: Tuple[float, ...] = (2.0, 3.0, 4.0)
ASSUMED_NOTE = ("🔴 电阻比数量级为**假设**（无逐条文献锚）⇒ 只报敏感性区间，"
                "不作绝对保持寿命承诺。")


# ---------------------------------------------------------------------------
# 1. 瞬态热：热扩散率 / 淬火窗口 / 界面热阻（逐来源）
# ---------------------------------------------------------------------------
def diffusivity_table(mat: str = "GST") -> Dict[str, Any]:
    """非晶相热扩散率 D = k_a/(ρ·cp) [m²/s]，逐来源 + **字段级消费审计**。

    消费语义要求 {ρ, cp, k_amorphous} 三字段齐全；缺任一 ⇒ 该来源**显式排除并记录**
    （不借他源字段合成、不用相态未标的 k 顶替）。
    """
    rows, excluded = [], []
    for a in ML.TRANSIENT_THERMAL_ANCHORS.get(mat, []):
        miss = [f for f in ("rho_kg_m3", "cp_j_per_kg_k", "k_amorphous") if not a.get(f)]
        if miss:
            excluded.append({"source": a["source"], "missing": miss})
            continue
        rows.append({"source": a["source"], "k_amorphous": a["k_amorphous"],
                     "rho_kg_m3": a["rho_kg_m3"], "cp_j_per_kg_k": a["cp_j_per_kg_k"],
                     "vol_heat_cap_j_per_m3k": a["rho_kg_m3"] * a["cp_j_per_kg_k"],
                     "diffusivity_m2_per_s": a["k_amorphous"] / (a["rho_kg_m3"] * a["cp_j_per_kg_k"])})
    _require(len(rows) >= 2, f"{mat}：非晶相热扩散率来源 <2 ⇒ 拒绝单源结论")
    ds = [r["diffusivity_m2_per_s"] for r in rows]
    return {"material": mat, "per_source": rows, "excluded_sources": excluded,
            "d_min": min(ds), "d_max": max(ds), "d_spread_x": max(ds) / min(ds)}


def melt_window(mat: str = "GST", *, t0_k: float = T0_K_DEFAULT) -> Dict[str, Any]:
    """淬火温度窗口 ΔT = T_melt − T_cryst（逐来源区间；字段级消费，两表合并取 t_melt）。"""
    melts = [(a["t_melt_k"], a["source"])
             for tbl in (ML.THERMAL_ANCHORS, ML.TRANSIENT_THERMAL_ANCHORS)
             for a in tbl.get(mat, []) if a.get("t_melt_k")]
    crysts = [(a["t_cryst_k"], a["source"]) for a in ML.T_CRYST_ANCHORS.get(mat, [])]
    _require(len(melts) >= 2, f"{mat}：熔点来源 <2")
    _require(len(crysts) >= 2, f"{mat}：晶化温度来源 <2")
    dt_lo = min(m for m, _ in melts) - max(c for c, _ in crysts)
    dt_hi = max(m for m, _ in melts) - min(c for c, _ in crysts)
    _require(dt_lo > 0.0, "淬火窗口必须为正（熔点须高于晶化温度）")
    return {"material": mat,
            "melts": [{"t_melt_k": m, "source": s} for m, s in melts],
            "crysts": [{"t_cryst_k": c, "source": s} for c, s in crysts],
            "dt_lo_k": dt_lo, "dt_hi_k": dt_hi,
            "note": "下游一律用 ΔT 区间（下界=保守淬火窗口），不取单点。"}


def critical_cooling(mat: str = "GST") -> Dict[str, Any]:
    """临界冷却速率锚（**数量级锚**，调用方须原样转述 `is_order_of_magnitude`）。"""
    a = ML.CRITICAL_COOLING_ANCHORS.get(mat)
    _require(a is not None, f"无临界冷却速率锚：{mat}")
    return dict(a)


def max_quench_thickness(mat: str = "GST", *, iface: str = "GST/SiO2") -> Dict[str, Any]:
    """可非晶化**最大膜厚** —— **双口径并报**（不选择、不只报一个）。

    ① **扩散口径**：热扩散特征时间 τ=L²/(π²D)，要求 ΔT/τ ≥ R_crit ⇒ `L_max^diff = π·√(D·ΔT/R_crit)`。
    ② **集总 RC 口径**：τ=(TBR+L/k_a)·(ρ·cp·L)，要求 ΔT/τ ≥ R_crit
       ⇒ 解 `(ρcp/k_a)·L² + TBR·ρcp·L − ΔT/R_crit = 0`。
    ② 含界面热阻 ⇒ **更保守**（更贴近文献经验上限 ~150 nm）；① 作乐观上界。
    器件膜厚必须 ≤ L_max，否则 reset 淬不成非晶。
    """
    d_tbl = diffusivity_table(mat)
    win = melt_window(mat)
    r = critical_cooling(mat)["rate_k_per_s"]
    tbrs = [a["tbr_m2k_per_w"] for a in ML.TBR_ANCHORS.get(mat, []) if a["iface"] == iface]
    _require(len(tbrs) >= 2, f"{mat}/{iface}：界面热阻来源 <2 ⇒ 拒绝单源结论")
    tbr_lo, tbr_hi = min(tbrs), max(tbrs)
    rows = []
    for d in d_tbl["per_source"]:
        a = d["vol_heat_cap_j_per_m3k"] / d["k_amorphous"]
        l_rc = lambda tbr, dt: (-(tbr * d["vol_heat_cap_j_per_m3k"])                   # noqa: E731
                                + math.sqrt((tbr * d["vol_heat_cap_j_per_m3k"]) ** 2 + 4.0 * a * (dt / r))) / (2.0 * a)
        rows.append({"source": d["source"], "diffusivity_m2_per_s": d["diffusivity_m2_per_s"],
                     "l_max_diff_lo_m": math.pi * math.sqrt(d["diffusivity_m2_per_s"] * win["dt_lo_k"] / r),
                     "l_max_diff_hi_m": math.pi * math.sqrt(d["diffusivity_m2_per_s"] * win["dt_hi_k"] / r),
                     "l_max_rc_lo_m": l_rc(tbr_lo, win["dt_lo_k"]),
                     "l_max_rc_hi_m": l_rc(tbr_hi, win["dt_hi_k"])})
    l_diff_lo = min(x["l_max_diff_lo_m"] for x in rows)
    l_diff_hi = max(x["l_max_diff_hi_m"] for x in rows)
    l_rc_lo = min(x["l_max_rc_lo_m"] for x in rows)
    l_rc_hi = max(x["l_max_rc_hi_m"] for x in rows)
    ref = 150e-9   # Adv. Mater. 2024 经验上限
    return {"material": mat, "model": "dual(diffusion + lumped_RC)",
            "r_crit_k_per_s": r, "r_crit_is_order_of_magnitude": critical_cooling(mat)["is_order_of_magnitude"],
            "tbr_lo": tbr_lo, "tbr_hi": tbr_hi, "dt_lo_k": win["dt_lo_k"], "dt_hi_k": win["dt_hi_k"],
            "per_source": rows,
            "l_max_diff_min_m": l_diff_lo, "l_max_diff_max_m": l_diff_hi,
            "l_max_rc_min_m": l_rc_lo, "l_max_rc_max_m": l_rc_hi,
            "literature_l_ref_m": ref,
            # 🔴 **双边**数量级判据（只查「不过大」会让 L_max 塌缩而不报警 ⇒ 单边是假判据）
            "diff_same_order_of_magnitude": (0.1 < l_diff_lo / ref) and (l_diff_hi / ref < 10.0),
            "rc_same_order_of_magnitude": (0.1 < l_rc_lo / ref) and (l_rc_hi / ref < 10.0),
            "note": ("两个口径都与文献经验上限（~150 nm）**同数量级**；RC 口径更保守（更接近）。"
                     "模型忽略相变前沿动力学与温度依赖 k ⇒ 只作**可行性上界**，不作精确厚度选择依据。")}


def cooldown_time(mat: str = "GST", *, t_film_nm: float, iface: str = "GST/SiO2") -> Dict[str, Any]:
    """冷却时间 τ_cool [s]（**串联 界面 TBR + 体** 的集总 RC 模型）。

    τ = (r_th_tbr + r_th_bulk)·c_th = (TBR + L/k_a)·(ρ·cp·L)   （单位面积口径）
    —— 故 τ 对 L **二阶**（薄膜）：界面项 ∝L、体项 ∝L²。逐来源 + TBR 区间。
    """
    _require(t_film_nm > 0.0, "膜厚必须为正")
    L = t_film_nm * 1e-9
    tbrs = [a for a in ML.TBR_ANCHORS.get(mat, []) if a["iface"] == iface]
    _require(len(tbrs) >= 2, f"{mat}/{iface}：界面热阻来源 <2 ⇒ 拒绝单源结论")
    tbr_lo = min(a["tbr_m2k_per_w"] for a in tbrs)
    tbr_hi = max(a["tbr_m2k_per_w"] for a in tbrs)
    rows = []
    for d in diffusivity_table(mat)["per_source"]:
        k_a = d["k_amorphous"]
        c_th = d["vol_heat_cap_j_per_m3k"] * L                      # 面积比热 [J/(m²·K)]
        r_bulk = L / k_a                                            # 体热阻 [m²K/W]
        for tag, tbr in (("lo", tbr_lo), ("hi", tbr_hi)):
            rows.append({"source": d["source"], "tbr_tag": tag, "tbr_m2k_per_w": tbr,
                         "tau_bulk_s": r_bulk * c_th, "tau_iface_s": tbr * c_th,
                         "tau_cool_s": (r_bulk + tbr) * c_th})
    return {"material": mat, "t_film_nm": float(t_film_nm), "iface": iface,
            "model": "lumped_RC(series: TBR + L/k_a)",
            "tbr_lo": tbr_lo, "tbr_hi": tbr_hi, "per_source": rows,
            "tau_min_s": min(r["tau_cool_s"] for r in rows),
            "tau_max_s": max(r["tau_cool_s"] for r in rows),
            "note": "集总 RC 忽略面内扩散与温度依赖 k ⇒ 报**区间**，不作单点。"}


def write_cycle_floor(mat: str = "GST", *, t_film_nm: float, t_pulse_ns: float,
                      iface: str = "GST/SiO2") -> Dict[str, Any]:
    """**写周期下限** = 脉冲宽 + 冷却时间（Adv. Mater. 2024 对切换时间的定义）⇒ 最大写频率。"""
    _require(t_pulse_ns > 0.0, "脉冲宽必须为正")
    ct = cooldown_time(mat, t_film_nm=t_film_nm, iface=iface)
    t_pul = t_pulse_ns * 1e-9
    t_lo = t_pul + ct["tau_min_s"]
    t_hi = t_pul + ct["tau_max_s"]
    return {"material": mat, "t_film_nm": float(t_film_nm), "t_pulse_ns": float(t_pulse_ns),
            "cooldown": ct,
            "t_cycle_min_s": t_lo, "t_cycle_max_s": t_hi,
            "f_max_hz_lo": 1.0 / t_hi, "f_max_hz_hi": 1.0 / t_lo,
            "note": "周期下限由 **脉冲宽 + 冷却时间** 共同决定（不是只看冷却）。"}


# ---------------------------------------------------------------------------
# 2. 非晶 drift：power law / 对数域不变性 / 保持窗口
# ---------------------------------------------------------------------------
def drift_sources(mat: str = "GST") -> List[Dict[str, Any]]:
    """电学域 drift ν 锚（逐来源）。"""
    rows = ML.DRIFT_ANCHORS.get(mat, [])
    _require(len(rows) >= 3, f"{mat}：drift 锚来源 <3 ⇒ 拒绝单源结论")
    return rows


def nu_central(mat: str = "GST") -> Dict[str, Any]:
    """ν 的代表区间（取非上界项；上界项单列）。"""
    srcs = drift_sources(mat)
    finite = [s["nu"] for s in srcs if not s.get("is_upper_bound")]
    ub = [s["nu"] for s in srcs if s.get("is_upper_bound")]
    sigmas = [s["nu_sigma"] for s in srcs if s.get("nu_sigma")]
    return {"nu_min": min(finite), "nu_max": max(finite),
            "nu_upper_bound": min(ub) if ub else None,
            "nu_sigma": min(sigmas) if sigmas else None}


def power_law_check(mat: str = "GST", *, t0_s: float = 1.0,
                    ea_ref_ev: float = 0.30, ea0_ev: float = 0.50) -> Dict[str, Any]:
    """`R(t)=R₀(t/t₀)^ν` 的**两路互证**（两个数学形式，非同行换写）：

    路径 A（幂式直接）：双对数斜率 ≡ ν。
    路径 B（物理链 · Boniardi & Ielmini, APL 98:243506 (2011)）：结构弛豫让传导激活能随
      `ln t` 线性增长 `E_A(t)=E_A0+k_B·T_ref·ν·ln(t/t₀)` ⇒ 由 Arrhenius `R=R*·exp(E_A/k_BT_ref)`
      **导出**幂律。两路斜率都须 = ν ⇒ 证明「ν ≡ 激活能对数增长速率」的物理语义。
    🔴 本判据锁定**语义**（指数是否为 ν）；其判别力由门禁反向探针（改指数为 ν² 等）证明。
    """
    srcs = drift_sources(mat)
    rows, worst = [], 0.0
    for s in srcs:
        nu = s["nu"]

        def fB(t: float, nu: float = nu) -> float:      # Arrhenius 桥接（物理链）
            ea = ea0_ev + ea_ref_ev * nu * math.log(t / t0_s)
            return math.exp(ea / ea_ref_ev)

        t1, t2 = t0_s * 10.0, t0_s * 100.0
        sl_a = (math.log((t2 / t0_s) ** nu) - math.log((t1 / t0_s) ** nu)) / (math.log(t2) - math.log(t1))
        sl_b = (math.log(fB(t2)) - math.log(fB(t1))) / (math.log(t2) - math.log(t1))
        rows.append({"source": s["source"], "nu": nu,
                     "slope_power_law": sl_a, "slope_arrhenius_chain": sl_b})
        worst = max(worst, abs(sl_a - nu) / nu, abs(sl_b - nu) / nu)
    return {"material": mat, "max_rel_dev": worst, "ok": worst < 1e-9,
            "n_sources": len(srcs), "per_source": rows,
            "note": "两路（幂式 / Arrhenius 链）双对数斜率都 = ν ⇒ 语义锁定。"}


def log_domain_invariance(mat: str = "GST") -> Dict[str, Any]:
    """**电学域多电平的正面结论**：drift 是**统一因子** ⇒ 对数域电平间距严格不变。

    R_j(t)/R_k(t) = [R_j(0)(t/t₀)^ν] / [R_k(0)(t/t₀)^ν] = R_j(0)/R_k(0)，与 t 无关。
    ⇒ 只要读出在**对数域**，drift 不侵蚀间距；侵蚀只来自 **ν 的单元间分散**（见保持窗口）。
    """
    srcs = drift_sources(mat)
    worst = 0.0
    for s in srcs:
        nu = s["nu"]
        rj, rk = 1.0e3, 1.0e2
        for t in (1.0, 10.0, 1e4):
            ratio = (rj * (t) ** nu) / (rk * (t) ** nu)
            worst = max(worst, abs(ratio - rj / rk) / (rj / rk))
    return {"material": mat, "ratio_drift_max_rel_dev": worst, "invariant": worst < 1e-12,
            "note": "对数域间距对 drift **严格不变**（统一因子消去）；线性域读出才被侵蚀。",
            "algebraic_identity": True,
            "identity_caveat": ("🔴 本式是**代数恒等**（统一因子 t^ν 消去）⇒ 门禁只作**事实陈述**，"
                                "其判别力由反向探针（令各电平带不同 ν ⇒ 比值必随 t 变）证明。")}


def optical_drift_status(mat: str = "GST") -> Dict[str, Any]:
    """**机器判定**：光学域是否有定量 drift 锚（读 `OPTICAL_DRIFT_ANCHORS`，非字面量）。

    🔴 PM-G7 结算（v0.9.193）后的语义：锚表非空 ⇒ `has_direct_optical_anchor=True`；
    但**主账锚是「上界」语义**（实测事实 + 检测下限假设），不是点值 ⇒ 判定仍须显式披露。
    """
    srcs = ML.OPTICAL_DRIFT_ANCHORS.get(mat, [])
    n = len(srcs)
    n_bound = sum(1 for s in srcs if s.get("kind") == "transmission_drift_upper_bound")
    has = n > 0 and n_bound > 0
    return {"material": mat, "n_optical_anchors": n, "n_bound_anchors": n_bound,
            "has_direct_optical_anchor": has,
            "electrical_anchors": len(ML.DRIFT_ANCHORS.get(mat, [])),
            "verdict": ("光学域**无直接定量锚** ⇒ M1 的光学振幅域设计的保持性"
                        "**不可由现有文献证据判定** ⇒ 派生缺口 PM-G7（须实测或换机制）。"
                        if not has else
                        "光学域有**实测锚**（Cheng 2019 器件级 10⁴ s 无可测透射漂移 + "
                        "Kalb 2003 弛豫动力学 + Ríos 2015 保持声明）⇒ 主账用**上界**口径"
                        "（ν_T ≤ 检测下限/ln(t_meas/t₀)），保持时间结论为**下界**语义。"),
            "gap_pm_g7_open": not has,
            "disclosed": "判定读的是锚表长度（机器可查），不是声明的字面量。"}


def nu_optical_bound(mat: str = "GST") -> Dict[str, Any]:
    """光学域透射漂移指数**上界**（从锚内实测字段**重算**，不读 `nu_ub` 字面量）。

    推导（纯算术）：Cheng 2019 实测「10⁴ s 无可测漂移」+ 编程电平 SD 0.35% 作检测下限
    ⇒ 漂移模型 ΔT/T ≈ ν_T·ln(t/t₀) 下 `ν_T ≤ floor/ln(t_meas/t₀)`。
    🔴 防漂移：若锚表里 `nu_ub` 与重算值不一致（有人改了 floor 却没改 nu_ub）⇒ raise。
    """
    srcs = ML.OPTICAL_DRIFT_ANCHORS.get(mat, [])
    bounds = [s for s in srcs if s.get("kind") == "transmission_drift_upper_bound"]
    _require(bounds, f"{mat}：光学域无透射漂移上界锚（kind=transmission_drift_upper_bound）")
    per, nus = [], []
    for b in bounds:
        floor = float(b["detection_floor_rel"])
        t_m = float(b["t_meas_s"])
        t0 = float(b["t0_s"])
        _require(t_m > t0 > 0.0 and floor > 0.0, "上界锚字段非法（须 t_meas>t₀>0 且 floor>0）")
        re_derived = floor / math.log(t_m / t0)
        stated = float(b["nu_ub"])
        _require(abs(re_derived - stated) <= 1e-12 * re_derived,
                 f"{mat}：上界锚 nu_ub={stated} 与重算 {re_derived} 不一致 ⇒ 锚表损坏")
        per.append({"source": b["source"], "nu_ub": re_derived,
                    "detection_floor_rel": floor, "t_meas_s": t_m})
        nus.append(re_derived)
    return {"material": mat, "nu_ub_max": max(nus), "n_bound_anchors": len(bounds),
            "per_anchor": per,
            "is_upper_bound_semantics": True,
            "derivation": "ν_T ≤ 检测下限 / ln(t_meas/t₀)（纯算术，检测下限假设显式披露）",
            "note": ("主账取**最大**上界（保守侧：ν_T 越小保持越长）；"
                     "t_max 结论因此是**下界**语义（真保持 ≥ 报告值）。")}


def retention_window_electrical(mat: str = "GST", *, n_levels: int = LEVELS_4BIT,
                                sigma_mult: float = SIGMA_MULT_DEFAULT,
                                log_range_decades: float = LOG_RANGE_DECADES_ASSUMED) -> Dict[str, Any]:
    """**电学域**保持窗口（有锚可算）：单元间 ν 分散 ⇒ 分布展宽 ≤ 间距/σ_mult。

    展宽 = σ_ν·ln(t/t₀)；对数域间距 = log_range·ln10/(n−1)；要求 σ_ν·ln(t/t₀) ≤ 间距/σ_mult
    ⇒ **t_hold = t₀·exp( ln10·log_range / ((n−1)·σ_mult·σ_ν) )**。
    """
    _require(n_levels >= 2, "至少两级")
    nu = nu_central(mat)
    sig = nu["nu_sigma"]
    _require(sig is not None, "缺 σ_ν ⇒ 无法做分布展宽判据（不臆造）")
    rows = []
    for lr in LOG_RANGE_SCAN:
        spacing_log = math.log(10.0) * lr / (n_levels - 1)
        t_hold = math.exp(spacing_log / (sigma_mult * sig))
        rows.append({"log_range_decades": lr, "spacing_nat_log": spacing_log,
                     "t_hold_s": t_hold, "t_hold_days": t_hold / 86400.0})
    return {"material": mat, "n_levels": n_levels, "sigma_mult": sigma_mult,
            "nu_sigma": sig, "per_log_range": rows,
            "log_range_used_decades": log_range_decades,
            "log_range_is_assumption": True,
            "note": ("🔴 电学域保持窗口**可算**（ν 统计锚在库）；但电阻比数量级为假设 ⇒ "
                     "报**敏感性区间**，不报单点寿命。光学域无锚 ⇒ 见 optical_drift_status。")}


def retention_window_optical_proxy(mat: str = "GST", *, margin_req: float = MARGIN_REQ_DEFAULT,
                                  nu_proxy: Optional[float] = None) -> Dict[str, Any]:
    """🔴 **跨域代理**（显式假设，非锚）：光学相对漂移率**若**与电学同阶 ⇒ 间距侵蚀时间。

    间距被侵蚀到 `margin` 需 ν·ln(t/t₀) = margin ⇒ t = t₀·exp(margin/ν)。
    结果**只作「证据不足下的上界敏感性」**，不作设计判据（光学域无锚 ⇒ 见 PM-G7）。
    """
    nu = nu_central(mat)
    proxies = [nu_proxy] if nu_proxy is not None else sorted({nu["nu_min"], nu["nu_max"]})
    rows = []
    for p in proxies:
        rows.append({"nu_proxy": p, "t_erode_s": math.exp(margin_req / p),
                     "t_erode_human": _humanize_s(math.exp(margin_req / p))})
    return {"material": mat, "margin_req": margin_req, "per_proxy": rows,
            "is_cross_domain_proxy": True,
            "note": ("🔴 **跨域代理（无据假设）**：光学域 drift 无直接锚 ⇒ 本表只说明"
                     "「若同阶则保持窗口为秒~分钟级」，**不得**当作光学域寿命结论。")}


def _humanize_s(t_s: float) -> str:
    if t_s < 60.0:
        return "%.1f 秒" % t_s
    if t_s < 3600.0:
        return "%.1f 分钟" % (t_s / 60.0)
    if t_s < 86400.0:
        return "%.1f 小时" % (t_s / 3600.0)
    if t_s < 86400.0 * 365:
        return "%.1f 天" % (t_s / 86400.0)
    return "%.2f 年" % (t_s / (86400.0 * 365.0))


# ---------------------------------------------------------------------------
# 3. 汇总报告
# ---------------------------------------------------------------------------
def m2_report(mat: str = "GST", *, t_film_nm: float = 10.0, t_pulse_ns: float = 500.0,
              n_levels: int = LEVELS_4BIT) -> Dict[str, Any]:
    """PM-M2 汇总：瞬态热 + drift + 机器判定 + 披露。"""
    return {
        "material": mat,
        "thermal": {
            "diffusivity": diffusivity_table(mat),
            "melt_window": melt_window(mat),
            "critical_cooling": critical_cooling(mat),
            "max_quench_thickness": max_quench_thickness(mat),
            "write_cycle_floor": write_cycle_floor(mat, t_film_nm=t_film_nm, t_pulse_ns=t_pulse_ns),
        },
        "drift": {
            "sources": drift_sources(mat),
            "nu_central": nu_central(mat),
            "power_law_check": power_law_check(mat),
            "log_domain_invariance": log_domain_invariance(mat),
            "optical_status": optical_drift_status(mat),
            "retention_electrical": retention_window_electrical(mat, n_levels=n_levels),
            "retention_optical_proxy": retention_window_optical_proxy(mat),
        },
        "thermal_consistency": ML.thermal_table_consistency(),
        "disclosure": {
            "tbr_is_literature": True,
            "r_crit_is_order_of_magnitude": True,
            "lumped_rc_is_simplification": True,
            "resistance_ratio_is_assumption": True,
            "optical_drift_has_no_anchor": True,
            "no_lifetime_guarantee": True,
            "no_energy_efficiency_metrics": True,
        },
    }
