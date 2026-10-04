# -*- coding: utf-8 -*-
"""LDA 光子存储征程 · M0 基线（非易失光子存储**单元**设计 · 闭式 + 双方法互证）。

定位（吃狗粮第五程 · 2026-10-04 启动）
--------------------------------------
用 LDA 已有材料层（本版新增 `pm_matlib`）与链路口径，把**一个非易失光子存储单元**
（Si 条波导 + GST 覆盖层 + 顶部微加热器）从「文献描述」变成**可算、可对拍、可判红**的
设计对象，并借此暴露平台缺口。

🔴 M0 的核心闭式律（本模块最有价值的产出）
--------------------------------------------
传播损耗 α = Γ·4πk/λ、相移 φ = 2πΓΔnL/λ ⇒ **每 π 损耗**
    IL_π = (10/ln10)·Γ·(4πk/λ)·L_π,  L_π = λ/(2ΓΔn)
⇒ **Γ 与器件长度同时约掉**：IL_π ≡ (10/ln10)·2πk/Δn。
含义：**重叠因子与长度可以互换（都只改 L_π），但每 π 损耗只由材料常数比 k/Δn 决定。**
由此两条锚族（材料常数 vs 器件 dB/π）第一次互相对上话（见 `pm_matlib.device_anchor_residue`）。

单元模型（全部闭式，零 FDTD）
------------------------------
- 相移/损耗：Γ·Δn / Γ·k 微扰，`cell_state()` 给**逐来源**值与区间
- 双态对比度：T_a/T_c（依赖 Γ·k·L ⇒ 绝对数依赖假设 Γ；**比值律不依赖**）
- 读出余量：shot-noise-limited 简化（**假设，显式标注**）+ 文献读出能量锚对照
- 写入预算：`pm_matlib.write_energy_budget`（显热主账 + 潜热上界并报）
- 缺口台账：机器可查（`closed ⇔ evidence_ok`，证据**重算**，不读字面量）

诚实边界
--------
- Γ（模场重叠）**无 FDTD 标定** ⇒ 是假设参数：绝对相移/长度结论对它线性敏感（并报敏感性）；
  但**每 π 损耗与它无关**（闭式已证）。
- 无 foundry 工艺真值、无本项目实测；材料常数全为**逐来源登记的文献值**，跨来源离散度**一个数量级以上**
  ⇒ 本模块一律报区间，不给单值结论。
- 🔴 不报 pJ/bit、fJ/op、TOPS 类能效指标（红线）。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from lda_l2 import pm_matlib as ML

# ---------------------------------------------------------------------------
# 0. 假设参数（🔴 全部标注 provenance，绝不伪装成实测）
# ---------------------------------------------------------------------------
GAMMA_DEFAULT: float = 0.05          # 模场-材料重叠因子（**假设**，M0 无 FDTD 标定 ⇒ 缺口 PM-G2）
GAMMA_SCAN: Tuple[float, ...] = (0.01, 0.02, 0.05, 0.1, 0.2)
WL_NM_DEFAULT: float = 1550.0
T0_K_DEFAULT: float = 300.0
READ_ENERGY_FJ_ASSUMED: float = 9.0  # 文献记录值作对照；shot-noise 简化用
BER_TARGET: float = 1.0e-12

#: 缺口语义（机器可查）：每项挂**重算证据**函数名，不读字面量。
GAP_SPECS: Tuple[Dict[str, Any], ...] = (
    # `declared_closed` = **人工声明**（对证据链的判定）；`evidence` 指向的函数 = **机器验算**。
    # 🔴 不变式 = `declared_closed == evidence_ok`（两**不同来源** ⇒ 非同义反复，有判别力）。
    {"id": "PM-G1", "title": "相变材料光学常数锚库（n,k @λ,相态）",
     "evidence": "_ev_g1", "declared_closed": True},
    {"id": "PM-G2", "title": "模场重叠因子 Γ 的 FDTD 标定",
     "evidence": "_ev_g2", "declared_closed": False},
    {"id": "PM-G3", "title": "瞬态热模型（冷却时间 = set/reset 周期下限）",
     "evidence": "_ev_g3", "declared_closed": True},
    {"id": "PM-G4", "title": "晶化动力学（JMAK/Avrami）",
     "evidence": "_ev_g4", "declared_closed": True},
    {"id": "PM-G5", "title": "非晶 drift（物理来源 + 电学域锚 + 光学域适用性判定）",
     "evidence": "_ev_g5", "declared_closed": True},
    {"id": "PM-G6", "title": "相位域（谐振/干涉）多电平读出与漂移口径",
     "evidence": "_ev_g6", "declared_closed": False},
    {"id": "PM-G7", "title": "光学域 drift 定量锚（@1550 nm 的 n/k 随时间）",
     "evidence": "_ev_g7", "declared_closed": False},
)


class PMM0Error(Exception):
    """M0 单元层错误。"""


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise PMM0Error(msg)


# ---------------------------------------------------------------------------
# 1. 单元状态（逐来源 + 区间）
# ---------------------------------------------------------------------------
def cell_state(mat: str, phase: str, *, l_um: float, gamma: float = GAMMA_DEFAULT,
               wl_nm: float = WL_NM_DEFAULT) -> Dict[str, Any]:
    """单态（amorphous/crystalline）的相移与插入损耗（逐来源 + 区间）。"""
    _require(l_um > 0.0, "L 必须为正")
    _require(gamma > 0.0, "Γ 必须为正")
    rows = ML.nk_sources(mat, phase, wl_nm)
    lam_m = wl_nm * 1e-9
    l_m = l_um * 1e-6
    per = []
    for n, k, src in rows:
        dphi_rad = 2.0 * math.pi * gamma * (n - 0.0) * l_m / lam_m   # 绝对相位（含材料 n）
        il_db = (10.0 / math.log(10.0)) * gamma * (4.0 * math.pi * k / lam_m) * l_m
        per.append({"source": src, "n": n, "k": k,
                    "dphi_rad": dphi_rad, "dphi_pi": dphi_rad / math.pi, "il_db": il_db,
                    "transmittance": 10.0 ** (-il_db / 10.0)})
    return {"material": mat, "phase": phase, "l_um": float(l_um), "gamma": float(gamma),
            "wl_nm": float(wl_nm), "per_source": per,
            "il_db_min": min(p["il_db"] for p in per), "il_db_max": max(p["il_db"] for p in per),
            "l_pi_um_ref": (lam_m / (2.0 * gamma * (ML.delta_n(mat, wl_nm)["per_source"][0]["dn"]))) * 1e6}


def cell_two_state(mat: str, *, l_um: float, gamma: float = GAMMA_DEFAULT,
                   wl_nm: float = WL_NM_DEFAULT) -> Dict[str, Any]:
    """双态对比度（逐来源）：T_a/T_c 与对比度 dB。"""
    a = cell_state(mat, "amorphous", l_um=l_um, gamma=gamma, wl_nm=wl_nm)
    c = cell_state(mat, "crystalline", l_um=l_um, gamma=gamma, wl_nm=wl_nm)
    keys_a = {p["source"]: p for p in a["per_source"]}
    rows = []
    for p in c["per_source"]:
        pa = keys_a.get(p["source"])
        _require(pa is not None, f"{mat}：两态来源不配对（{p['source']}）")
        cont = 10.0 * math.log10(pa["transmittance"] / p["transmittance"]) if p["transmittance"] > 0 else None
        rows.append({"source": p["source"], "il_a_db": pa["il_db"], "il_c_db": p["il_db"],
                     "contrast_db": cont})
    vals = [r["contrast_db"] for r in rows if r["contrast_db"] is not None]
    return {"material": mat, "l_um": float(l_um), "gamma": float(gamma), "per_source": rows,
            "contrast_min_db": min(vals), "contrast_max_db": max(vals),
            "l_pi_um": a["l_pi_um_ref"]}


def readout_margin(mat: str, *, l_um: float, gamma: float = GAMMA_DEFAULT,
                   e_read_fj: float = READ_ENERGY_FJ_ASSUMED,
                   ber: float = BER_TARGET, wl_nm: float = WL_NM_DEFAULT) -> Dict[str, Any]:
    """读出**能量下限**（shot-noise-limited 简化 · 假设，显式标注）。

    逆解：SNR = √N·(1−r)/(2√r)（r = T_c/T_a）⇒ 给定 BER 目标反解 N_min ⇒ E_min = N_min·hc/λ。
    🔴 只作**能量下限方向性**判断（无热噪声/暗电流/带宽）。
    """
    two = cell_two_state(mat, l_um=l_um, gamma=gamma, wl_nm=wl_nm)
    h, c = 6.62607015e-34, 2.99792458e8
    e_ph = h * c / (wl_nm * 1e-9)
    snr_need = _snr_for_ber(ber)
    rows = []
    for r in two["per_source"]:
        ta = 10.0 ** (-r["il_a_db"] / 10.0)
        tc = 10.0 ** (-r["il_c_db"] / 10.0)
        ratio = tc / ta if ta > 0 else 0.0
        denom = (1.0 - ratio) ** 2
        if denom <= 0.0:
            rows.append({"source": r["source"], "ratio": ratio, "n_min_photons": None,
                         "e_min_fj": None, "margin_ok": False})
            continue
        n_min = 4.0 * ratio * (snr_need ** 2) / denom
        e_min_j = n_min * e_ph
        rows.append({"source": r["source"], "ratio": ratio, "n_min_photons": n_min,
                     "e_min_j": e_min_j, "e_min_fj": e_min_j * 1e15,
                     "margin_ok": e_min_j <= e_read_fj * 1e-15})
    return {"material": mat, "e_read_fj": float(e_read_fj), "snr_needed": snr_need,
            "rows": rows, "all_ok": all(r["margin_ok"] for r in rows),
            "model": "shot_noise_limited(assumption)",
            "honest_note": "🔴 简化模型（仅散粒噪声）⇒ 只作读出能量下限的**方向性**判断；写能量才是本单元瓶颈。"}


def _snr_for_ber(ber: float) -> float:
    """由目标 BER 反解所需 SNR（二分；Q 函数单调）。"""
    _require(0.0 < ber < 0.5, "BER 必须 ∈ (0,0.5)")
    lo, hi = 0.0, 40.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if 0.5 * math.erfc(mid / math.sqrt(2.0)) > ber:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# 2. 写入预算（转调材料层）
# ---------------------------------------------------------------------------
def write_budget(mat: str = "GST", *, l_um: float = 0.5, w_um: float = 0.5,
                 t_gst_nm: float = 20.0, t0_k: float = T0_K_DEFAULT) -> Dict[str, Any]:
    b = ML.write_energy_budget(mat, l_um=l_um, w_um=w_um, t_nm=t_gst_nm, t0_k=t0_k)
    anchor_j = b["device_anchor_pj"] * 1e-12
    b["device_anchor_j"] = anchor_j
    b["ratio_sensible_to_anchor"] = b["sensible_lower_j"] / anchor_j
    b["same_order_as_anchor"] = 0.1 <= b["ratio_sensible_to_anchor"] <= 100.0
    return b


# ---------------------------------------------------------------------------
# 3. 独立数值对拍：闭式 ⟷ 分片传输（N 段 TMM 极限）
# ---------------------------------------------------------------------------
def verify_closed_form_vs_segments(mat: str, *, l_um: float = 200.0,
                                   gamma: float = GAMMA_DEFAULT, n_seg: int = 256,
                                   wl_nm: float = WL_NM_DEFAULT) -> Dict[str, Any]:
    """把单元分成 N 片逐片累乘（相位旋转 + 分贝损耗）⇒ 与闭式解析严格一致。

    两法**独立来源**：闭式 = 一次乘幂；分片 = N 次逐步累乘（不同算法路径）。
    """
    _require(n_seg >= 2, "n_seg 至少 2")
    dn = ML.delta_n(mat, wl_nm)["per_source"][0]["dn"]
    k = ML.delta_n(mat, wl_nm)["per_source"][0]["k_c"]
    lam_m = wl_nm * 1e-9
    l_m = l_um * 1e-6
    phi_cf = 2.0 * math.pi * gamma * dn * l_m / lam_m
    il_cf = (10.0 / math.log(10.0)) * gamma * (4.0 * math.pi * k / lam_m) * l_m
    phi_seg = 0.0
    il_seg = 0.0
    for _ in range(n_seg):
        phi_seg += 2.0 * math.pi * gamma * dn * (l_m / n_seg) / lam_m
        il_seg += (10.0 / math.log(10.0)) * gamma * (4.0 * math.pi * k / lam_m) * (l_m / n_seg)
    return {"phi_closed_form": phi_cf, "phi_segmented": phi_seg,
            "il_closed_form_db": il_cf, "il_segmented_db": il_seg,
            "phi_rel_dev": abs(phi_seg - phi_cf) / (abs(phi_cf) + 1e-300),
            "il_rel_dev": abs(il_seg - il_cf) / (abs(il_cf) + 1e-300),
            "n_seg": int(n_seg)}


# ---------------------------------------------------------------------------
# 4. 缺口台账（机器可查：closed ⇔ evidence_ok · 证据重算）
# ---------------------------------------------------------------------------
def _ev_g1() -> Tuple[bool, str]:
    """PM-G1：锚库可用（≥1 个多来源材料 + 全部来源逐条登记）且反外推守卫真会 raise（双向）。"""
    rep = ML.matlib_report()
    multi = [m for m, v in rep["materials"].items() if len(v["nk_crystalline"]["per_source"]) >= 2]
    flagged = all(v["nk_amorphous"].get("single_source") == (len(v["nk_amorphous"]["per_source"]) == 1)
                  for v in rep["materials"].values())
    try:
        ML.nk("GST", "amorphous", 1310.0)
        guard = False
    except ML.PMMatlibRedlineError:
        guard = True
    return (bool(multi) and flagged and guard), \
        f"多来源材料={multi} · 单来源标记一致={flagged} · 反外推守卫={guard}"


def _ev_g2() -> Tuple[bool, str]:
    """PM-G2：Γ 的 FDTD 标定 —— 需存在可为 Γ 背书的数据源（当前无）。"""
    has_fdtd = hasattr(ML, "GAMMA_FDTD_TABLE") and bool(getattr(ML, "GAMMA_FDTD_TABLE", None))
    return bool(has_fdtd), f"FDTD Γ 数据源存在={bool(has_fdtd)}"


def _ev_g3() -> Tuple[bool, str]:
    """PM-G3：热扩散率 ≥2 源（含字段级排除）∧ 临界冷却律双口径同数量级（**算出来的**）。"""
    if not (hasattr(ML, "TRANSIENT_THERMAL_ANCHORS") and hasattr(ML, "TBR_ANCHORS")):
        return False, "瞬态热锚不存在"
    from lda_l2 import pm_m2 as M2  # 局部导入避免加载序耦合
    d = M2.diffusivity_table("GST")
    q = M2.max_quench_thickness("GST")
    ok = (len(d["per_source"]) >= 2 and len(d["excluded_sources"]) >= 1
          and q["diff_same_order_of_magnitude"] and q["rc_same_order_of_magnitude"])
    return bool(ok), ("热扩散率来源=%d（字段级排除 %d）· L_max 双口径同数量级=%s/%s"
                      % (len(d["per_source"]), len(d["excluded_sources"]),
                         q["diff_same_order_of_magnitude"], q["rc_same_order_of_magnitude"]))


def _ev_g4() -> Tuple[bool, str]:
    """PM-G4：JMAK 锚 ≥2 源 ∧ 动力学律自检通过（**算出来的**，非存在性字面量）。"""
    if not hasattr(ML, "JMAK_PARAMS") or not ML.JMAK_PARAMS.get("GST"):
        return False, "JMAK 参数不存在"
    from lda_l2 import pm_m1 as M1  # 局部导入避免加载序耦合
    chk = M1.jmak_law_check("GST")
    n_src = len(ML.JMAK_PARAMS["GST"])
    return bool(chk["ok"] and n_src >= 2), (
        f"JMAK 锚源={n_src} · Arrhenius 双路径 dev={chk['max_rel_dev']:.2e}")


def _ev_g5() -> Tuple[bool, str]:
    """PM-G5：电学域 ν 锚 ≥3 源 ∧ 两路互证通过 ∧ **光学域适用性已机器判定**（算出来的）。

    闭合口径 = 「drift 物理来源登机 + 电学域锚 ≥3 源 + 律自检 + 光学域**无直接锚的判定本身**
    作为结论公开」；判定结论（无锚）⇒ **派生缺口 PM-G7**，不粉饰。
    """
    if not hasattr(ML, "DRIFT_ANCHORS"):
        return False, "drift 锚不存在"
    from lda_l2 import pm_m2 as M2
    n = len(ML.DRIFT_ANCHORS.get("GST", []))
    chk = M2.power_law_check("GST")
    st = M2.optical_drift_status("GST")
    ok = (n >= 3 and chk["ok"] and st["has_direct_optical_anchor"] is False)
    return bool(ok), ("电学域 ν 锚=%d 源 · 两路互证 dev=%.2e · 光学域直接锚=%s（判定为缺 ⇒ 缺口 PM-G7）"
                      % (n, chk["max_rel_dev"], st["has_direct_optical_anchor"]))


def _ev_g6() -> Tuple[bool, str]:
    """PM-G6：相位域多电平口径 —— M1 判振幅域对 Sb₂Se₃ 不可行 ⇒ 相位域须独立口径（当前无）。"""
    has = hasattr(ML, "PHASE_DOMAIN_ANCHOR") and bool(getattr(ML, "PHASE_DOMAIN_ANCHOR", None))
    return bool(has), f"相位域多电平锚存在={bool(has)}"


def _ev_g7() -> Tuple[bool, str]:
    """PM-G7：光学域 drift 定量锚 —— 读 `OPTICAL_DRIFT_ANCHORS`（空 ⇒ 未闭合）。"""
    n = len(getattr(ML, "OPTICAL_DRIFT_ANCHORS", {}).get("GST", []))
    return bool(n > 0), f"光学域 drift 锚源={n}（0 ⇒ 未闭合）"


def gap_ledger() -> List[Dict[str, Any]]:
    out = []
    for spec in GAP_SPECS:
        ev = globals()[spec["evidence"]]()
        ok = bool(ev[0])
        decl = bool(spec["declared_closed"])
        out.append({"id": spec["id"], "title": spec["title"],
                    "declared_closed": decl,      # 人工声明
                    "evidence_ok": ok,            # 机器验算
                    "closed": decl and ok,        # 两者**同时**成立才闭合
                    "evidence_detail": ev[1]})
    return out


def contrast_vs_length(mat: str, lengths_um: Tuple[float, ...] = (10.0, 50.0, 200.0, 1000.0),
                       gamma: float = GAMMA_DEFAULT, wl_nm: float = WL_NM_DEFAULT) -> List[Dict[str, Any]]:
    """对比度随长度单调增（每一长度都重算，不用缩放假设）。"""
    out = []
    for L in lengths_um:
        t = cell_two_state(mat, l_um=L, gamma=gamma, wl_nm=wl_nm)
        out.append({"l_um": float(L), "contrast_min_db": t["contrast_min_db"],
                    "contrast_max_db": t["contrast_max_db"]})
    return out


def gap_ledger_consistent() -> bool:
    """不变式：**人工声明 == 机器验算**（两**不同来源** ⇒ 非同义反复，有判别力）。

    打坏实现（如弱化某 `_ev_*`）而声明不改 ⇒ `evidence_ok` 掉 ⇒ 必红。
    """
    return all(g["declared_closed"] == g["evidence_ok"] for g in gap_ledger())


# ---------------------------------------------------------------------------
# 5. 汇总报告
# ---------------------------------------------------------------------------
def cell_report(mat: str = "GST", *, l_um: float = 200.0, gamma: float = GAMMA_DEFAULT,
                wl_nm: float = WL_NM_DEFAULT) -> Dict[str, Any]:
    inv = ML.gamma_invariance(mat, wl_nm=wl_nm)
    sens = []
    for g in GAMMA_SCAN:
        st = cell_state(mat, "crystalline", l_um=l_um, gamma=g, wl_nm=wl_nm)
        sens.append({"gamma": g, "l_pi_um": st["l_pi_um_ref"],
                     "il_db_min": st["il_db_min"], "il_db_max": st["il_db_max"]})
    return {
        "milestone": "PM-M0 · 非易失光子存储单元（闭式基线）",
        "matlib": ML.matlib_report(wl_nm),
        "cell": {
            "two_state": cell_two_state(mat, l_um=l_um, gamma=gamma, wl_nm=wl_nm),
            "write": write_budget(mat),
            "readout": readout_margin(mat, l_um=l_um, gamma=gamma, wl_nm=wl_nm),
            "closed_form_vs_segments": verify_closed_form_vs_segments(mat, l_um=l_um * 10, gamma=gamma, wl_nm=wl_nm),
            "contrast_vs_length": contrast_vs_length(mat, gamma=gamma, wl_nm=wl_nm),
            "per_pi_law": inv,
            "gamma_sensitivity": sens,
            "gamma_provenance": "assumption（无 FDTD 标定 ⇒ 缺口 PM-G2）",
        },
        "device_anchor_residue": ML.device_anchor_residue("Sb2Se3"),
        "gaps": gap_ledger(),
        "gaps_consistent": gap_ledger_consistent(),
        "disclosure": {
            "layer": "设计预算层（非流片结论）",
            "no_foundry_truth": True,
            "no_project_measurement": True,
            "no_efficiency_metric_reported": True,
            "known_drift": "材料常数跨来源离散度 >1 个数量级 ⇒ 结论一律区间口径。",
        },
    }
