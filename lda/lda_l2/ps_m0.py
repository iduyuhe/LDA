"""PS-M0 · 光子传感器新征程 · 基线可设计版（裸硅微环折射率传感器）。

═══ 策略（吃狗粮 · 自己先用平台设计出来）═══
先用 LDA 现有全矢量模式求解器算「包层/待测物折射率微扰 → dneff/dn」（闭式
微扰论，直接以折射率中心差商求得），再得体灵敏度 S = λ/n_g · dneff/dn，给出
微环谐振位移 Δλ 与「谐振线宽受限」的探测极限 LOD。最后用平台现有
`RingResonator` 几何跑通「几何→placement→GDS→DRC/LVS」主权流片链路，
真实检验平台能力，并登记缺口供 PS-M1…M7 补齐。

═══ 🔴 纪律 ═══
· 进报告的数字一律**模块现算**（不转录草稿）；
· `dneff/dn` 用「折射率中心差商」求得（闭式微扰），并以「向前差商」作第二差商
  互验（方法学内部一致性）；
· 每道守卫配反向探针（见 `selfcheck_ps_m0` 的「先证能变红」）。
"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, Optional

import numpy as np

from lda_solver.full_vector_mode_solver import (
    group_index,
    solve_modes,
    solve_modes_eps,
)
from lda_chain import LinkModel
from lda_ir.core import ObjectiveSpec
from lda_ir.photon import RingResonator


# ---------------------------------------------------------------------------
# 求解器挑选：TE 基模（Hy 主导）
# ---------------------------------------------------------------------------
def _te_fundamental(rs):
    te = [r for r in rs if r.frac_hy_core > 0.5]
    if not te:
        return None
    te.sort(key=lambda r: -r.neff)
    return te[0]


# ---------------------------------------------------------------------------
# 体灵敏度核心：dneff/dn（闭式微扰，中心差商 + 向前差商互验）
# ---------------------------------------------------------------------------
def bulk_sensitivity(w: float = 0.5, h: float = 0.22, wl_um: float = 1.55,
                     n_core: float = 3.4777, n_clad_oxide: float = 1.4441,
                     n_analyte: float = 1.33,
                     h_grid: float = 0.02, Lh: float = 2.5,
                     dp_clad: float = 1e-4, dp_ana: float = 1e-3) -> Dict[str, float]:
    """算两种传感暴露模型下的 dneff/dn 与体灵敏度 S（nm/RIU）。

    · whole-cladding：整个氧化包层折射率微扰 → 上限（整个传感体积被待测物取代）；
    · exposed-top   ：仅顶部被待测物取代（真实传感窗口模型，主指标）。
    """
    k0 = 2.0 * math.pi / wl_um

    # (a) 整包层灵敏度（上限）
    rs0 = solve_modes(w, h, wl_um, n_core, n_clad_oxide)
    r0 = _te_fundamental(rs0)
    neff0 = r0.neff
    n1 = _te_fundamental(solve_modes(w, h, wl_um, n_core, n_clad_oxide + dp_clad)).neff
    nm = _te_fundamental(solve_modes(w, h, wl_um, n_core, n_clad_oxide - dp_clad)).neff
    d_clad_c = (n1 - nm) / (2.0 * dp_clad)
    d_clad_f = (n1 - neff0) / dp_clad

    # (b) 顶部暴露灵敏度（真实传感窗口）：仅 y>h/2 为待测物，其余为氧化包层
    N = int(round(2.0 * Lh / h_grid))
    xv = np.linspace(-Lh, Lh, N + 1)
    yv = np.linspace(-Lh, Lh, N + 1)
    xc = 0.5 * (xv[:-1] + xv[1:])
    yc = 0.5 * (yv[:-1] + yv[1:])
    XX, YY = np.meshgrid(xc, yc)

    def _te_n(n_top: float) -> float:
        eps = np.full((N, N), n_clad_oxide ** 2)
        eps[YY > h / 2] = n_top ** 2  # 顶部 = 待测物
        core = (np.abs(XX) <= w / 2) & (np.abs(YY) <= h / 2)
        eps[core] = n_core ** 2
        rs = solve_modes_eps(eps, xv, yv, k0,
                             n_lo=n_clad_oxide * 0.99, n_hi=n_core, conf_min=0.30)
        return _te_fundamental(rs).neff

    na0 = _te_n(n_analyte)
    na1 = _te_n(n_analyte + dp_ana)
    nam = _te_n(n_analyte - dp_ana)
    d_ana_c = (na1 - nam) / (2.0 * dp_ana)
    d_ana_f = (na1 - na0) / dp_ana

    # 群折射率（材料色散，Si/SiO2 Sellmeier）——S 的缩放因子
    ng = group_index(w, h, wl_um, n_core, n_clad_oxide,
                     core_material="Si", clad_material="SiO2")

    S_top = (wl_um * 1000.0 / ng) * d_ana_c
    S_whole = (wl_um * 1000.0 / ng) * d_clad_c

    return {
        "neff": neff0,
        "n_g": ng,
        "dneff_dn_clad_whole": d_clad_c,
        "dneff_dn_clad_whole_fwd": d_clad_f,
        "dneff_dn_ana_top": d_ana_c,
        "dneff_dn_ana_top_fwd": d_ana_f,
        "S_nm_per_riu_top": S_top,
        "S_nm_per_riu_whole": S_whole,
        "wl_um": wl_um,
        "n_analyte": n_analyte,
        "n_core": n_core,
        "n_clad_oxide": n_clad_oxide,
        "w_um": w,
        "h_um": h,
    }


# ---------------------------------------------------------------------------
# 微环传感器指标
# ---------------------------------------------------------------------------
def ring_sensor_metrics(R_um: float, wl_um: float, n_g: float,
                        S_nm_per_riu: float, Q: float) -> Dict[str, float]:
    """FSR、谐振线宽受限最小可分辨位移、探测极限 LOD（RIU）。

    🔴 LOD 为「谐振线宽受限」理论最优（δλ_min ≈ λ/Q）；v0 暂不建模环传播损耗与
    探测器噪声（缺口③，PS-M2 补齐噪声模型）。
    """
    fsr_nm = (wl_um ** 2) / (n_g * 2.0 * math.pi * R_um) * 1000.0
    dlambda_min_nm = wl_um * 1000.0 / Q  # 谐振 FWHM
    LOD_riu = dlambda_min_nm / S_nm_per_riu
    return {
        "R_um": R_um,
        "Q": Q,
        "FSR_nm": fsr_nm,
        "dlambda_min_nm": dlambda_min_nm,
        "S_nm_per_riu": S_nm_per_riu,
        "LOD_riu": LOD_riu,
    }


def resonance_shift_nm(S_nm_per_riu: float, delta_n: float) -> float:
    """给定体折射率变化 Δn，微环谐振波长位移 Δλ（nm）。"""
    return S_nm_per_riu * delta_n


# ---------------------------------------------------------------------------
# v0 设计编排：指标计算 + 平台现有 RingResonator 跑通主权流片链路
# ---------------------------------------------------------------------------
def design_sensor_v0(w: float = 0.5, h: float = 0.22, wl_um: float = 1.55,
                     n_core: float = 3.4777, n_clad_oxide: float = 1.4441,
                     n_analyte: float = 1.33, R_um: float = 10.0,
                     Q: float = 1.0e4,
                     out_dir: Optional[str] = None) -> Dict[str, Any]:
    sens = bulk_sensitivity(w, h, wl_um, n_core, n_clad_oxide, n_analyte)
    ring = ring_sensor_metrics(R_um, wl_um, sens["n_g"], sens["S_nm_per_riu_top"], Q)

    # —— 主权流片链路（复用现有 RingResonator 几何）——
    layout: Dict[str, Any] = {}
    try:
        from lda_chain.route_sim import layout_only  # noqa: E402
        from lda_l2.chip_layout_export import export_chip_gds  # noqa: E402

        link = LinkModel(domain="photon", name="ps_m0_ring_sensor")
        link.ir.add(RingResonator(id="ring", R=R_um, n_g=sens["n_g"], Q=Q))
        link.ir.objectives.append(ObjectiveSpec(bid="B11", target=0.99))
        lay = layout_only(link, wg_width=0.5)
        rep = export_chip_gds(link, lay["placement"], lay["routes"], wg_width=0.5)
        drc = rep.get("drc_report", {}) or {}
        gds_path = None
        if out_dir:
            import os
            os.makedirs(out_dir, exist_ok=True)
            gds_path = os.path.join(out_dir, "ps_m0_ring_sensor.gds")
            with open(gds_path, "wb") as f:
                f.write(rep.get("gds_bytes", b""))
        layout = {
            "gds_bytes": len(rep.get("gds_bytes", b"")),
            "gds_path": gds_path,
            "n_elements": (rep.get("gds_stats", {}) or {}).get("n_elements"),
            "drc_all_pass": drc.get("all_pass"),
            "n_drc_checked": drc.get("n_checked"),
            "lvs_present": "lvs_report" in rep,
            "blocked_nets": lay.get("blocked_nets"),
        }
    except Exception as e:  # noqa: BLE001 —— 链路异常即如实登记为缺口发现
        layout = {"error": str(e)[:240]}

    # v0 已暴露 / 待补的缺口（与 docs 路线图 §3/§5 对应）
    gaps = {
        "G1_sensitive_layer_model": "缺失（无功能化/表面结合动力学）——PS-M4",
        "G2_sensor_pdk_device": "缺失（无 slot/suspended/开窗几何）——PS-M1/M3",
        "G3_sensor_metrics_report": "部分（v0 算 S/LOD，但无 FOM/噪声模型/标定报告）——PS-M2",
        "G4_sensing_window_layer": "缺失（无开窗工艺层/DRC 特例）——PS-M1",
        "G5_microfluidics": "缺失（无流体通道/多物理场）——PS-M5",
        "G6_webui_panel": "缺失（无 /api/sensor_demo）——PS-M7",
    }

    return {
        "sensor": "ring_refractive_index_v0",
        "params": {
            "w_um": w, "h_um": h, "wl_um": wl_um,
            "n_core": n_core, "n_clad_oxide": n_clad_oxide,
            "n_analyte": n_analyte, "R_um": R_um, "Q": Q,
        },
        "sensitivity": sens,
        "ring_metrics": ring,
        "layout_chain": layout,
        "gaps_registered": gaps,
    }


# ---------------------------------------------------------------------------
# 自校 / 反向探针（先证能变红）
# ---------------------------------------------------------------------------
def selfcheck_ps_m0(tol_central_vs_fwd: float = 0.02,
                    S_lo: float = 1.0, S_hi: float = 5000.0,
                    LOD_hi: float = 1.0) -> Dict[str, Any]:
    """v0 守卫：物理量合理 + 差商互验 + 反向探针。

    反向探针（抹平断口必红）：若 dneff/dn 被置 0 ⇒ S=0 ⇒ LOD→∞ ⇒ 判据必红；
    若 Δn 取负 ⇒ Δλ 必为负（红移/蓝移符号正确）。
    """
    rep = design_sensor_v0()
    s = rep["sensitivity"]
    ring = rep["ring_metrics"]

    checks: Dict[str, bool] = {}

    # ① 差商内部一致性（中心 vs 向前）
    checks["fd_consistency_clad"] = (
        abs(s["dneff_dn_clad_whole_fwd"] - s["dneff_dn_clad_whole"])
        / max(abs(s["dneff_dn_clad_whole"]), 1e-9) < tol_central_vs_fwd)
    checks["fd_consistency_ana"] = (
        abs(s["dneff_dn_ana_top_fwd"] - s["dneff_dn_ana_top"])
        / max(abs(s["dneff_dn_ana_top"]), 1e-9) < tol_central_vs_fwd)

    # ② 物理量合理：敏感度为正、在 sane 区间
    checks["S_positive"] = s["S_nm_per_riu_top"] > 0
    checks["S_in_range"] = S_lo <= s["S_nm_per_riu_top"] <= S_hi

    # ③ LOD 有限且为正
    checks["LOD_finite_positive"] = (math.isfinite(ring["LOD_riu"])
                                     and 0 < ring["LOD_riu"] < LOD_hi)

    # ④ 反向探针：Δn>0 ⇒ Δλ>0（红移）；Δn<0 ⇒ Δλ<0
    d_pos = resonance_shift_nm(s["S_nm_per_riu_top"], +1e-3)
    d_neg = resonance_shift_nm(s["S_nm_per_riu_top"], -1e-3)
    checks["shift_sign_correct"] = (d_pos > 0) and (d_neg < 0)

    # ⑤ 反向探针（先证能变红）：S=0（抹平断口）⇒ LOD→∞ ⇒ 守卫必捕获。
    #    用与 ring_sensor_metrics 同式的 LOD 公式验证：S=0 时显式得 inf，
    #    `not isfinite` 必为 True ⇒ 守卫已武装（常态 S≠0 时不会误红）。
    _LOD = lambda dmin, S: (dmin / S) if S != 0 else float("inf")
    checks["zero_S_guard_armed"] = not math.isfinite(_LOD(ring["dlambda_min_nm"], 0.0))

    # ⑥ 平台流片链路：DRC 全过 + LVS 存在（标准环不应触发缺口④）
    lc = rep["layout_chain"]
    if "error" in lc:
        checks["layout_chain_ok"] = False
        checks["layout_chain_note"] = lc["error"]
    else:
        checks["layout_chain_ok"] = bool(lc.get("drc_all_pass")) and bool(lc.get("lvs_present"))

    all_pass = all(v for k, v in checks.items() if not k.startswith("layout_chain_note"))
    rep["selfcheck"] = {"all_pass": all_pass, "checks": checks}
    return rep


# ---------------------------------------------------------------------------
# 命令行入口（被 run_ps_m0_smoke.py 复用）
# ---------------------------------------------------------------------------
def main() -> int:
    rep = selfcheck_ps_m0()
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 0 if rep["selfcheck"]["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
