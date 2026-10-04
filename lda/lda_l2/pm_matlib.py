# -*- coding: utf-8 -*-
"""PM · 相变材料常数库（文献锚 · 光学 @1550nm + 热学）—— 光子存储征程 M0 缺口①清偿。

定位（吃狗粮第五程 · 光子存储 2026-10-04 启动）
--------------------------------------------------
`nonvolatile_weight_backend`（U8）只登记了**器件级**锚（dB/π、位深、耐久），
**没有任何 n,k 光学常数**（GST 的 dB/π 甚至是 `None`）⇒ 无法从材料出发算对比度/损耗。
本模块补上这一层：**按来源逐条登记的文献常数 + 区间口径 + 反外推守卫**。

🔴 三条守卫（机器守卫，不是文字承诺）
--------------------------------------
| 守卫 | 语义 |
|---|---|
| `PROVENANCE_KINDS = ("literature",)` | 本项目**没有** PCM 实测 ⇒ 「measurement」不是可选项；任何 `is_measured_by_this_project=True` 即 raise |
| 波长反外推 | `nk(mat, phase, wl)` **只在已登记波长上取值**（容差 0.01 nm）；未登记波长一律 raise，**绝不插值/外推**（文献曲线不是本项目数据） |
| 缺字段即 raise | 消费某字段而无锚 ⇒ raise（宁缺毋滥，禁止「补一个合理值」） |

🔴 本模块的头号实证发现（机器可算）
------------------------------------
**跨来源离散度 > 一个数量级。** 同为「c-GST @1550nm」，k 的公开值 0.1 / 0.83 / 1.02 / 1.55
（4 个独立来源）⇒ 由闭式律 `IL_per_π = 4.343·2πk/Δn` 算出的每 π 损耗相差 **≈15×**
（≈0.97 → ≈14.8 dB/π）。⇒ **任何单值设计结论都是伪精度**；本模块一律报**区间 + 逐来源表**，
并由门禁 `C2` 钉住「不许只留一个来源」。

第二条实证（把两条锚族接起来）：Sb₂Se₃ 在 C 波段 k ≤ 1e-6 ⇒ 材料吸收路径给出的每 π 损耗
**≈3.6e-5 dB**，而 U8 登记的**器件级**锚是 **0.1 dB/π** ⇒ 两者相差 3 个数量级
⇒ **器件级 0.1 dB/π 几乎全部来自非材料吸收项**（散射/模式失配/界面），
**材料常数路径不能替代器件锚、反之亦然**（`device_anchor_residue()` 并报两口径）。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# 0. 域常量与守卫
# ---------------------------------------------------------------------------
PROVENANCE_KINDS: Tuple[str, ...] = ("literature",)          # 🔴 无 "measurement"
PHASES: Tuple[str, ...] = ("amorphous", "crystalline")
WL_TOL_NM: float = 0.01                                      # 取值容差（反外推）
NEGLIGIBLE_K: float = 1.0e-6                                 # 「k 低于探测限」登记上界


class PMMatlibError(Exception):
    """材料库通用错误。"""


class PMMatlibRedlineError(PMMatlibError):
    """红线违规（假实测声明 / 反外推 / 缺锚）。"""


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise PMMatlibRedlineError(msg)


# ---------------------------------------------------------------------------
# 1. 光学常数锚（λ = 1550 nm，全部文献，全部非本项目实测）
# ---------------------------------------------------------------------------
#: 字段：n / k（该来源**自身**给的数）；k_upper_bound=True 表示来源只给上界（如「<1e-6」）。
OPTICAL_ANCHORS: Dict[str, List[Dict[str, Any]]] = {
    "GST": [
        {"source": "ACS Photonics 2025 / arXiv 2512.23559（椭偏 · Cody-Lorentz 拟合 · 30nm 膜）",
         "wl_nm": 1550.0, "amorphous": (4.33, 0.07), "crystalline": (6.93, 1.02)},
        {"source": "Opt. Express 20(9):10283 (2012)（椭偏实测 · Si 波导上 GST 膜）",
         "wl_nm": 1550.0, "amorphous": (4.39, 0.16), "crystalline": (7.25, 1.55)},
        {"source": "Photonics 9(6):366 (2022)（片上 MOMR 建模引用值）",
         "wl_nm": 1550.0, "amorphous": (3.94, 0.045), "crystalline": (6.11, 0.83)},
        {"source": "arXiv 2511.21138（超表面建模引用值 · 椭偏拟合）",
         "wl_nm": 1550.0, "amorphous": (2.4, 0.02), "crystalline": (5.2, 0.1)},
        {"source": "RSC Adv. 8 (2018)（光谱反演 · 退火相变序列）",
         "wl_nm": 1550.0, "amorphous": (3.25, 0.070), "crystalline": (5.68, 0.847)},
    ],
    "GSST": [
        {"source": "Photonics 9(6):366 (2022)（Ge2Sb2Se4Te 引用值）",
         "wl_nm": 1550.0, "amorphous": (3.32, 0.0), "crystalline": (5.08, 0.35)},
    ],
    "Sb2Se3": [
        {"source": "ACS Photonics 2025 / arXiv 2512.23559（椭偏 · Cody-Lorentz 拟合 · 80nm 膜）",
         "wl_nm": 1550.0, "amorphous": (3.34, 1.0e-6), "crystalline": (4.32, 1.0e-6),
         "k_upper_bound": True, "k_note": "来源报 k 可忽略（低于探测限）⇒ 此处为上界"},
        {"source": "Nanomaterials 14(15):1317 (2024)（逆设计引用值）",
         "wl_nm": 1550.0, "amorphous": (3.285, 0.0), "crystalline": (4.050, 0.0),
         "k_upper_bound": True, "k_note": "来源明确写 0.000i"},
        {"source": "Opt. Express 33(12):26713 (2025)（椭偏实测 · 220°C 退火 / 激光相变）",
         "wl_nm": 1550.0, "amorphous": (3.245, 1.0e-6), "crystalline": (4.012, 1.0e-6),
         "k_upper_bound": True, "k_note": "来源报 C 波段 k < 1e-6"},
    ],
}

# ---------------------------------------------------------------------------
# 2. 热学常数锚（相变写入预算用；🔴 潜热**无文献锚** ⇒ 见 LATENT_HEAT_J_PER_G）
# ---------------------------------------------------------------------------
THERMAL_ANCHORS: Dict[str, List[Dict[str, Any]]] = {
    "GST": [
        {"source": "Microsyst. Nanoeng. 8:101 (2022) Tab.1（综述汇总值）",
         "rho_kg_m3": 6350.0, "cp_j_per_kg_k": 250.0,
         "k_thermal_w_per_m_k": 1.48, "t_melt_k": 893.0},
        {"source": "Opt. Express 23(23):29353 (2015) Tab.1（光学/热参数表）",
         "rho_kg_m3": 6200.0, "cp_j_per_kg_k": 202.0,
         "k_thermal_a_w_per_m_k": 0.17, "k_thermal_c_w_per_m_k": 0.5},
    ],
}

#: 🔴 **本项目假设**（文献未给统一值 ⇒ 不发明、不引用）：熔化潜热。
#: 主账**不计潜热**（只算显热下限），潜热只作**上界并报**（`assumption` 来源，范围给全）。
LATENT_HEAT_J_PER_G_ASSUMED_RANGE: Tuple[float, float] = (100.0, 150.0)

# ---------------------------------------------------------------------------
# 3. 器件级文献锚（**只作对照**，永不作判据 —— 与 U8 同一政策）
# ---------------------------------------------------------------------------
DEVICE_ANCHORS: Dict[str, Dict[str, Any]] = {
    "PCM_PM_RECORD_2025": {
        "source": "Photonics 12(11):1130 (2025)（结构优化的光子 PCM 器件）",
        "levels_n": 209, "levels_bits": 7.6,
        "write_energy_pj": 0.96, "readout_energy_fj": 9.0,
        "endurance_cycles": 6000,
        "note": "记录值为该**特定几何**器件所测 ⇒ 只作量级对照，不参与任何判据阈值。",
    },
    "SB2SE3_DEVICE_ANCHOR": {
        "source": "内部总结 §市场对比（Sb₂Se₃ 器件：7-bit / retention >10yr / 耐久 >1e8 / ~0.1 dB/π）",
        "il_db_per_pi": 0.1, "levels_bits": 7.0,
        "endurance_cycles": 1.0e8,
        "note": "与 U8 `LITERATURE_ANCHORS['Sb2Se3']` 同源（器件级），非材料常数。",
    },
}


def _check_anchors() -> None:
    """守卫：锚表结构合法性（任何来源不得自称实测）。"""
    for mat, rows in OPTICAL_ANCHORS.items():
        for r in rows:
            _require("source" in r, f"{mat} 光学锚缺 source")
            _require(r.get("is_measured_by_this_project", False) is False,
                     f"{mat} 光学锚不得自称本项目实测")
            for ph in PHASES:
                _require(ph in r and len(r[ph]) == 2, f"{mat}/{ph} 锚缺 (n,k)")


# ---------------------------------------------------------------------------
# 4. 取值 API（反外推：只认已登记波长）
# ---------------------------------------------------------------------------
def registered_wavelengths(mat: str) -> List[float]:
    _require(mat in OPTICAL_ANCHORS, f"未登记材料：{mat}")
    return sorted({float(r["wl_nm"]) for r in OPTICAL_ANCHORS[mat]})


def nk_sources(mat: str, phase: str, wl_nm: float = 1550.0) -> List[Tuple[float, float, str]]:
    """返回该 (材料, 相态, 波长) 的**逐来源** (n, k, source)。未登记波长 ⇒ raise（不插值）。"""
    _require(mat in OPTICAL_ANCHORS, f"未登记材料：{mat}")
    _require(phase in PHASES, f"未登记相态：{phase}（允许 {PHASES}）")
    hits = [r for r in OPTICAL_ANCHORS[mat] if abs(float(r["wl_nm"]) - float(wl_nm)) <= WL_TOL_NM]
    _require(bool(hits),
             f"{mat}@{wl_nm}nm 无锚 ⇒ 拒绝取值（已登记波长 {registered_wavelengths(mat)}）。"
             f"🔴 文献曲线不是本项目数据，禁止插值/外推。")
    out = []
    for r in hits:
        n, k = r[phase]
        out.append((float(n), float(k), str(r["source"])))
    return out


def nk(mat: str, phase: str, wl_nm: float = 1550.0) -> Dict[str, Any]:
    """区间口径的 (n, k)：跨来源 min/max + 逐来源表。"""
    rows = nk_sources(mat, phase, wl_nm)
    ns = [r[0] for r in rows]
    ks = [r[1] for r in rows]
    return {
        "material": mat, "phase": phase, "wl_nm": float(wl_nm),
        "n_min": min(ns), "n_max": max(ns), "k_min": min(ks), "k_max": max(ks),
        "n_spread_x": (max(ns) / min(ns)) if min(ns) > 0 else None,
        "k_spread_x": (max(ks) / min(ks)) if min(ks) > 0 else None,
        "n_sources": len(rows),
        #: 🔴 单来源材料**不得**给离散度口径（无从谈离散）⇒ 必须显式标记供下游谨慎使用。
        "single_source": len(rows) == 1,
        "per_source": [{"n": n, "k": k, "source": s} for n, k, s in rows],
    }


def delta_n(mat: str, wl_nm: float = 1550.0) -> Dict[str, Any]:
    """n_c − n_a 的**逐来源**值与区间（两态须来自同一来源，禁止混搭）。"""
    aa = {s: (n, k) for n, k, s in nk_sources(mat, "amorphous", wl_nm)}
    cc = {s: (n, k) for n, k, s in nk_sources(mat, "crystalline", wl_nm)}
    per = []
    for s, (n_c, k_c) in cc.items():
        _require(s in aa, f"{mat}：来源「{s}」只有晶态、无非晶态 ⇒ 禁止跨来源混搭")
        n_a, k_a = aa[s]
        per.append({"source": s, "dn": n_c - n_a, "dk": k_c - k_a,
                    "n_a": n_a, "n_c": n_c, "k_a": k_a, "k_c": k_c})
    dns = [p["dn"] for p in per]
    return {"material": mat, "wl_nm": float(wl_nm),
            "dn_min": min(dns), "dn_max": max(dns), "per_source": per,
            "dn_spread_x": (max(dns) / min(dns)) if min(dns) > 0 else None}


# ---------------------------------------------------------------------------
# 5. 🔴 闭式物理律：每 π 损耗与重叠因子 Γ 无关
# ---------------------------------------------------------------------------
#: 传播常数：α = Γ·4πk/λ（每米）· 相移 φ = 2πΓΔnL/λ ⇒ 每 π 损耗
#:   IL_π = (10/ln10)·Γ·(4πk/λ)·L_π,  L_π = λ/(2ΓΔn)
#:        = (10/ln10)·2πk/Δn     ← **Γ 严格约掉**
PER_PI_LOSS_COEF: float = 10.0 / math.log(10.0) * 2.0 * math.pi


def per_pi_loss_db(dn: float, k_c: float) -> float:
    """闭式：IL_π = (10/ln10)·2πk/Δn（dB/π）。Γ 与器件长度**均不出现**。"""
    _require(dn > 0.0, "Δn 必须为正（否则无相位可用）")
    _require(k_c >= 0.0, "k 必须非负")
    return PER_PI_LOSS_COEF * (k_c / dn)


def per_pi_loss_table(mat: str, wl_nm: float = 1550.0) -> Dict[str, Any]:
    """逐来源的每 π 损耗（用**晶态** k = 相位遍历中的高损耗态）+ 区间。"""
    d = delta_n(mat, wl_nm)
    rows = []
    for p in d["per_source"]:
        rows.append({"source": p["source"], "dn": p["dn"], "k_c": p["k_c"],
                     "il_db_per_pi": per_pi_loss_db(p["dn"], p["k_c"])})
    vals = [r["il_db_per_pi"] for r in rows]
    return {"material": mat, "wl_nm": float(wl_nm), "per_source": rows,
            "il_min_db_per_pi": min(vals), "il_max_db_per_pi": max(vals),
            "spread_x": (max(vals) / min(vals)) if min(vals) > 0 else None}


def gamma_invariance(mat: str, wl_nm: float = 1550.0,
                     gammas: Tuple[float, ...] = (0.005, 0.02, 0.05, 0.1, 0.2),
                     t_gst_nm: float = 20.0) -> Dict[str, Any]:
    """数值实证「Γ 无关」：扫描 Γ，用**逐 Γ 重算**的 L_π 与 IL 求 IL_π（而非套用闭式）。"""
    d = delta_n(mat, wl_nm)
    dn = d["per_source"][0]["dn"]
    k_c = d["per_source"][0]["k_c"]
    lam_m = wl_nm * 1e-9
    out = []
    for g in gammas:
        l_pi_m = lam_m / (2.0 * g * dn)                      # 需要 π 相移的长度
        il_pi_db = (10.0 / math.log(10.0)) * (g * 4.0 * math.pi * k_c / lam_m) * l_pi_m
        out.append({"gamma": float(g), "l_pi_um": l_pi_m * 1e6, "il_pi_db": il_pi_db})
    vals = [o["il_pi_db"] for o in out]
    span = max(vals) - min(vals)
    return {"material": mat, "rows": out, "closed_form_db": per_pi_loss_db(dn, k_c),
            "max_rel_dev": (span / abs(vals[0])) if vals[0] else None,
            "l_pi_law": "L_π ∝ 1/(ΓΔn) ⇒ 与 Γ 反比、与 Δn 反比（长度可换、损耗不可换）"}


# ---------------------------------------------------------------------------
# 6. 与器件级锚的**残差并报**（两条锚族不许互相替代）
# ---------------------------------------------------------------------------
def device_anchor_residue(mat: str = "Sb2Se3") -> Dict[str, Any]:
    """材料吸收路径的每 π 损耗 vs 器件级 dB/π 锚 ⇒ 残差 = 非材料吸收项。"""
    _require(mat == "Sb2Se3", "仅 Sb2Se3 有器件级 dB/π 锚（U8 登记）")
    tbl = per_pi_loss_table(mat)
    dev = DEVICE_ANCHORS["SB2SE3_DEVICE_ANCHOR"]["il_db_per_pi"]
    return {
        "material": mat,
        "material_absorption_db_per_pi_max": tbl["il_max_db_per_pi"],
        "device_anchor_db_per_pi": dev,
        "residue_db_per_pi": dev - tbl["il_max_db_per_pi"],
        "residue_over_material_x": (dev / tbl["il_max_db_per_pi"]) if tbl["il_max_db_per_pi"] > 0 else None,
        "honest_note": ("材料吸收路径 ⇒ 每 π 损耗 ≈ 3.6e-5 dB 量级；器件级锚 0.1 dB/π 比它大 3 个数量级 "
                        "⇒ 器件损耗几乎全部来自非材料吸收项（散射/模式失配/界面/弯曲）。"
                        "🔴 两条锚族**不可互相替代**，必须并报。"),
    }


# ---------------------------------------------------------------------------
# 7. 写入热预算（显热主账 + 潜热上界并报）
# ---------------------------------------------------------------------------
def write_energy_budget(mat: str = "GST", *, l_um: float, w_um: float,
                        t_nm: float, t0_k: float = 300.0) -> Dict[str, Any]:
    """非晶化（熔化-淬火）写入能量**设计预算**：Q = ρV[c_p·(T_m − T0)]（显热下限）。

    🔴 潜热无文献锚 ⇒ 只作**上界并报**（假设区间），主账不含；不报 pJ/bit 能效。
    """
    _require(mat in THERMAL_ANCHORS, f"无热学锚：{mat}")
    anchors = THERMAL_ANCHORS[mat]
    vol_m3 = (l_um * 1e-6) * (w_um * 1e-6) * (t_nm * 1e-9)
    rows, excluded = [], []
    need = ("rho_kg_m3", "cp_j_per_kg_k", "t_melt_k")
    for a in anchors:
        missing = [f for f in need if a.get(f) is None]
        if missing:                       # 🔴 字段级消费审计：缺字段 ⇒ 该来源**不参与**估算
            excluded.append({"source": a["source"], "missing_fields": missing,
                             "rule": "缺字段即排除（宁缺毋滥，不借他源值合成）"})
            continue
        m = a["rho_kg_m3"] * vol_m3
        e_sens = m * a["cp_j_per_kg_k"] * (a["t_melt_k"] - t0_k)
        rows.append({"source": a["source"], "mass_kg": m, "sensible_j": e_sens,
                     "t_melt_k": a["t_melt_k"], "rho_kg_m3": a["rho_kg_m3"],
                     "cp_j_per_kg_k": a["cp_j_per_kg_k"]})
    _require(bool(rows), f"{mat}：无任何来源同时具备 {need} ⇒ 拒绝估算（不合成）")
    lo, hi = LATENT_HEAT_J_PER_G_ASSUMED_RANGE
    rho_min = min(r["rho_kg_m3"] for r in rows)
    rho_max = max(r["rho_kg_m3"] for r in rows)
    lat_lo = (lo * 1e3) * rho_min * vol_m3          # J/g → J/kg
    lat_hi = (hi * 1e3) * rho_max * vol_m3
    e_lo = min(r["sensible_j"] for r in rows)
    e_hi = max(r["sensible_j"] for r in rows)
    return {
        "material": mat, "volume_m3": vol_m3, "per_source": rows, "excluded_sources": excluded,
        "sensible_lower_j": e_lo, "sensible_upper_j": e_hi,
        "latent_upper_assumed_j": (lat_lo, lat_hi),
        "provenance": {"sensible": "literature", "latent": "assumption"},
        "device_anchor_pj": DEVICE_ANCHORS["PCM_PM_RECORD_2025"]["write_energy_pj"],
        "honest_note": ("本预算是**设计预算层**（θ 无 foundry 真值、潜热为假设）⇒ 只报量级，"
                        "不与文献记录值作等同比较；🔴 不报 pJ/bit、fJ/op 类能效指标。"),
    }


# ---------------------------------------------------------------------------
# 8. 汇总
# ---------------------------------------------------------------------------
def matlib_report(wl_nm: float = 1550.0) -> Dict[str, Any]:
    _check_anchors()
    mats = {}
    for mat in OPTICAL_ANCHORS:
        mats[mat] = {
            "nk_amorphous": nk(mat, "amorphous", wl_nm),
            "nk_crystalline": nk(mat, "crystalline", wl_nm),
            "delta_n": delta_n(mat, wl_nm),
            "per_pi_loss": per_pi_loss_table(mat, wl_nm),
        }
    return {
        "wl_nm": float(wl_nm),
        "materials": mats,
        "device_anchors": DEVICE_ANCHORS,
        "headline": {
            "cross_source_spread": {
                m: {"k_spread_x": mats[m]["nk_crystalline"]["k_spread_x"],
                    "dn_spread_x": mats[m]["delta_n"]["dn_spread_x"]}
                for m in mats},
            "headline_finding": ("跨来源离散度 > 一个数量级 ⇒ 单值设计结论是伪精度；"
                                 "一律报区间 + 逐来源表。"),
        },
        "guardrails": {
            "provenance_kinds": list(PROVENANCE_KINDS),
            "no_extrapolation": True,
            "device_anchors_are_reference_only": True,
        },
    }
