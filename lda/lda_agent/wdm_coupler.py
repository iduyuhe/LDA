"""D-57: 耦合器 × WDM 组合（FDTD 标定 κ(gap) PDK 文件 → WDM 环 bus 耦合段设计）。

物理洞察：add-drop 环的 bus↔ring 耦合本质是方向耦合器。D-42 的 WDM
用**解析** gap_to_kappa（D-37 指数模型，kappa_ref=0.35 为假设值）；
本模块用 D-55 的 **2D FDTD 双点标定**标定 κ_c(gap) [rad/µm]，存为
**PDK 标定文件**（一次性后台标定 ~20 分钟，设计时秒级加载）：

  PDK 标定（kappa_calibration.json：κ_c(gap) 5 点，dl=0.039µm 高分辨率）
  → k_ring = sin(κ_c · L_couple)，L_couple = 2·√(2·R·gap)（环形耦合近似）
  → gap 扫描设计：{0.25, 0.30, 0.35} 各查标定文件 + WDM 验收，取首个全过
  → 系统验收：WDM IL/XT/DRC（复用 D-42）+ 标定有效（非缠绕）+ 换算自洽
  → 诚实报告：FDTD 校准 k_ring vs 解析 gap_to_kappa 的偏差
    （D-57 实测：gap=0.25 时 k_ring=0.107 vs 解析 0.488，比值 0.22——
    解析假设显著偏乐观，系统以 FDTD 校准为准并报告偏差）

物理模型（LLM 不进判决路径，全部复用已验证实现）：
  · κ_c：2D FDTD 双点差分（D-55，dc_transmission_spectrum）
  · k_ring：sin(κ_c·L_couple)（环形耦合近似，诚实标注近似边界）
  · WDM：add-drop 级联传递（D-37/D-42）
"""

import argparse
import json
import math
import os
import sys
from typing import Any, Callable, Dict, List, Optional

from lda_agent.wdm_system import design_wdm  # type: ignore
from lda_agent.ring_adddrop import gap_to_kappa  # type: ignore

# 默认参数
_DEF_CHANNELS = [1550.0, 1553.0, 1556.0]
_DEF_GAP_SCAN = [0.25, 0.30, 0.35]
_CALIB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "data", "kappa_calibration.json")
_WL_CALIB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "data", "kappa_wavelength_calibration.json")
_GRID_CALIB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "data", "kappa_grid_calibration.json")


# ---------------------------------------------------------------------------
# PDK 标定文件
# ---------------------------------------------------------------------------
def kappa_c_grid_interp(grid: Dict[str, Any], gap_um: float,
                        wl_um: float) -> Optional[float]:
    """κ_c(gap,λ) 全网格双线性插值（越界 → None）。"""
    pts = {(p["gap_um"], p["wl_um"]): p["kappa_c_rad_um"]
           for p in grid["points"]}
    gaps = sorted(grid["gaps_um"])
    wls = sorted(grid["wls_um"])
    if gap_um < gaps[0] - 1e-9 or gap_um > gaps[-1] + 1e-9:
        return None
    if wl_um < wls[0] - 1e-9 or wl_um > wls[-1] + 1e-9:
        return None
    g0 = max(g for g in gaps if g <= gap_um + 1e-9)
    g1 = min(g for g in gaps if g >= gap_um - 1e-9)
    w0 = max(w for w in wls if w <= wl_um + 1e-9)
    w1 = min(w for w in wls if w >= wl_um - 1e-9)
    if g0 == g1 and w0 == w1:
        return pts[(g0, w0)]
    k00 = pts[(g0, w0)]
    k01 = pts[(g0, w1)] if w1 != w0 else k00
    k10 = pts[(g1, w0)] if g1 != g0 else k00
    k11 = pts[(g1, w1)] if (g1 != g0 and w1 != w0) else k00
    wg = (gap_um - g0) / (g1 - g0) if g1 != g0 else 0.0
    ww = (wl_um - w0) / (w1 - w0) if w1 != w0 else 0.0
    k_bot = k00 + (k10 - k00) * wg
    k_top = k01 + (k11 - k01) * wg
    return k_bot + (k_top - k_bot) * ww


def _wdm_detail(wdm: Dict[str, Any]) -> str:
    """WDM 验收摘要（避免多行 f-string 跨括号，Python<3.12 兼容）。"""
    chks = wdm["acceptance"]["checks"]
    n_ok = sum(1 for c in chks if c["ok"])
    n_tot = len(chks)
    il_max = max(wdm["metrics"]["il_drop_db"])
    xt_min = min(wdm["metrics"]["xt_min_db"])
    return f"{n_ok}/{n_tot} 项：IL≤{il_max:.2f}dB XT≥{xt_min:.1f}dB"


def kappa_c_from_wavelength(calib: Dict[str, Any],
                            wl_um: float) -> Optional[float]:
    """从波长标定点线性插值 κ_c(λ) [rad/µm]（越界 → None）。"""
    pts = sorted(calib["points"], key=lambda p: p["wl_um"])
    wls = [p["wl_um"] for p in pts]
    if wl_um < wls[0] - 1e-9 or wl_um > wls[-1] + 1e-9:
        return None
    if wl_um <= wls[0]:
        return pts[0]["kappa_c_rad_um"]
    if wl_um >= wls[-1]:
        return pts[-1]["kappa_c_rad_um"]
    for i in range(len(pts) - 1):
        if wls[i] <= wl_um <= wls[i + 1]:
            w0, w1 = wls[i], wls[i + 1]
            k0 = pts[i]["kappa_c_rad_um"]
            k1 = pts[i + 1]["kappa_c_rad_um"]
            return k0 + (k1 - k0) * (wl_um - w0) / (w1 - w0)
    return None


def load_calibration(path: str = _CALIB_PATH) -> Dict[str, Any]:
    """加载 κ_c(gap) PDK 标定文件。"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def kappa_c_from_calibration(calib: Dict[str, Any],
                             gap_um: float) -> Optional[float]:
    """从标定点线性插值 κ_c(gap) [rad/µm]（越界 → None）。"""
    pts = sorted(calib["points"], key=lambda p: p["gap_um"])
    gaps = [p["gap_um"] for p in pts]
    if gap_um < gaps[0] - 1e-9 or gap_um > gaps[-1] + 1e-9:
        return None
    if gap_um <= gaps[0]:
        return pts[0]["kappa_c_rad_um"]
    if gap_um >= gaps[-1]:
        return pts[-1]["kappa_c_rad_um"]
    for i in range(len(pts) - 1):
        if gaps[i] <= gap_um <= gaps[i + 1]:
            g0, g1 = gaps[i], gaps[i + 1]
            k0 = pts[i]["kappa_c_rad_um"]
            k1 = pts[i + 1]["kappa_c_rad_um"]
            return k0 + (k1 - k0) * (gap_um - g0) / (g1 - g0)
    return None


def ring_kappa_from_calibration(calib: Dict[str, Any], gap_um: float,
                                R_um: float) -> Dict[str, Any]:
    """标定文件 → 每圈场耦合比 k_ring（环形耦合有效长度近似）。"""
    kc = kappa_c_from_calibration(calib, gap_um)
    L_couple = 2.0 * math.sqrt(2.0 * R_um * gap_um)
    k_ring = math.sin(max(kc, 0.0) * L_couple) if kc and kc > 0 else 0.0
    return {"gap_um": gap_um, "kappa_c_rad_um": round(kc, 6) if kc else None,
            "R_um": round(R_um, 3), "L_couple_um": round(L_couple, 3),
            "k_ring": round(k_ring, 5),
            "k_analytic": round(gap_to_kappa(gap_um), 5),
            "ratio_fdtd_over_analytic": round(
                k_ring / gap_to_kappa(gap_um), 3)
            if gap_to_kappa(gap_um) > 0 else None}


# ---------------------------------------------------------------------------
# 主闭环：gap 扫描设计
# ---------------------------------------------------------------------------
def design_wdm_with_coupler(channels_nm: Optional[List[float]] = None,
                            gap_scan: Optional[List[float]] = None,
                            calib: Optional[Dict[str, Any]] = None,
                            n_g: float = 4.2, m: int = 170,
                            wavelength_calibrated: bool = False,
                            wl_calib: Optional[Dict[str, Any]] = None,
                            grid_calibrated: bool = False,
                            grid_calib: Optional[Dict[str, Any]] = None,
                            ) -> Dict[str, Any]:
    """耦合器×WDM 组合设计：FDTD 标定驱动 gap 选择 → WDM 系统验收。

    wavelength_calibrated=True：加载 κ_c(λ) 波长标定文件（gap 基线），
    每信道按 λ 插值 κ_c → 每环独立 k_ring；WDM 验收用最弱耦合
    k_ring_min（保守——最弱信道过则全部过），并报告每信道 k_ring 表
    与 κ_c(λ) 趋势（D-59：λ 1.50→1.60 增幅 ~27%）。

    grid_calibrated=True：加载 κ_c(gap,λ) 全网格标定文件（D-60），
    **双线性插值**直接查表（替代 D-59 分离变量近似）——每 gap × 每信道
    独立 κ_c → 最弱耦合保守验收。grid 优先级高于 wavelength。
    """
    if channels_nm is None:
        channels_nm = list(_DEF_CHANNELS)
    if gap_scan is None:
        gap_scan = list(_DEF_GAP_SCAN)
    if calib is None:
        calib = load_calibration()
    if wl_calib is None:
        wl_calib = (load_calibration(_WL_CALIB_PATH)
                    if os.path.exists(_WL_CALIB_PATH) else None)
    if grid_calib is None:
        grid_calib = (load_calibration(_GRID_CALIB_PATH)
                      if os.path.exists(_GRID_CALIB_PATH) else None)
    n_ch = len(channels_nm)
    # WDM 环半径（m 阶环）：R = m·λ0/(2π·n_g)
    R_typ = m * channels_nm[0] * 1e-3 / (2.0 * math.pi * n_g)

    def _grid_valid(gd: Dict[str, Any]) -> bool:
        """全网格标定文件覆盖全部 (gap_scan, 信道 λ)。"""
        return bool(gd and all(
            kappa_c_grid_interp(gd, g, c * 1e-3) is not None
            for g in gap_scan for c in channels_nm))
    grid_valid = _grid_valid(grid_calib) if grid_calib else False

    def _wl_valid(cb: Dict[str, Any]) -> bool:
        """波长标定文件覆盖全部信道。"""
        return bool(cb and all(
            kappa_c_from_wavelength(cb, c * 1e-3) is not None
            for c in channels_nm))
    wl_valid = _wl_valid(wl_calib) if wl_calib else False
    # 波长相关标定基线（gap=0.3）：κ_c_wl 基准 = κ_c_wl(1.55)（分离变量归一）
    wl_base = None
    if wavelength_calibrated and wl_calib:
        wl_base = kappa_c_from_wavelength(wl_calib, 1.55)

    calibrations: List[Dict[str, Any]] = []
    attempts: List[Dict[str, Any]] = []
    chosen: Optional[Dict[str, Any]] = None
    chosen_per_channel: List[Dict[str, Any]] = []
    for gap in gap_scan:
        if grid_calibrated and grid_valid:
            # 全网格：双线性插值 κ_c(gap,λ)（D-60，替代分离变量近似）
            Lc = 2.0 * math.sqrt(2.0 * R_typ * gap)
            per_channel = []
            for ch in channels_nm:
                kc = kappa_c_grid_interp(grid_calib, gap, ch * 1e-3)
                if kc is None:
                    attempts.append({"gap_um": gap, "ok": False,
                                     "reason": "网格插值越界"})
                    continue
                kr = math.sin(kc * Lc)
                per_channel.append({"channel_nm": ch,
                                    "kappa_c_rad_um": round(kc, 6),
                                    "k_ring": round(kr, 5)})
            if len(per_channel) != n_ch:
                continue
            k_rings = [p["k_ring"] for p in per_channel if p["k_ring"]]
            k_ring_min = min(k_rings) if k_rings else 0.0
            cal = {"gap_um": gap,
                   "kappa_c_rad_um": per_channel[0]["kappa_c_rad_um"],
                   "R_um": round(R_typ, 3),
                   "L_couple_um": round(Lc, 3),
                   "k_ring": round(k_ring_min, 5),
                   "k_analytic": round(gap_to_kappa(gap), 5),
                   "ratio_fdtd_over_analytic": round(
                       k_ring_min / gap_to_kappa(gap), 3)
                   if gap_to_kappa(gap) > 0 else None}
            calibrations.append(cal)
            if not 0 < cal["k_ring"] < 1.0:
                attempts.append({"gap_um": gap, "ok": False,
                                 "reason": "k_ring 超出 (0,1)"})
                continue
            k_ring = cal["k_ring"]
            kappa_fn: Callable[[float], float] = lambda g, kr=k_ring: kr
        elif wavelength_calibrated and wl_valid and wl_base:
            # 波长相关：κ_c(gap,λ) ≈ κ_c_gap(gap)·[κ_c_wl(λ)/κ_c_wl(1.55)]
            # （分离变量近似，诚实标注）；每信道独立 k_ring，取最弱保守验收
            kc_gap = kappa_c_from_calibration(calib, gap)
            if kc_gap is None or kc_gap <= 0 or wl_base is None:
                attempts.append({"gap_um": gap, "ok": False,
                                 "reason": "gap 标定越界或波长基线缺失"})
                continue
            Lc = 2.0 * math.sqrt(2.0 * R_typ * gap)
            per_channel = []
            for ch in channels_nm:
                kc_wl = kappa_c_from_wavelength(wl_calib, ch * 1e-3)
                if kc_wl is None:
                    kc_wl = 1.0
                kc = kc_gap * (kc_wl / wl_base)
                kr = math.sin(kc * Lc)
                per_channel.append({"channel_nm": ch,
                                    "kappa_c_rad_um": round(kc, 6),
                                    "k_ring": round(kr, 5)})
            k_rings = [p["k_ring"] for p in per_channel if p["k_ring"]]
            k_ring_min = min(k_rings) if k_rings else 0.0
            cal = {"gap_um": gap,
                   "kappa_c_rad_um": round(kc_gap, 6),
                   "R_um": round(R_typ, 3),
                   "L_couple_um": round(Lc, 3),
                   "k_ring": round(k_ring_min, 5),
                   "k_analytic": round(gap_to_kappa(gap), 5),
                   "ratio_fdtd_over_analytic": round(
                       k_ring_min / gap_to_kappa(gap), 3)
                   if gap_to_kappa(gap) > 0 else None}
            calibrations.append(cal)
            if not 0 < cal["k_ring"] < 1.0:
                attempts.append({"gap_um": gap, "ok": False,
                                 "reason": "k_ring 超出 (0,1)"})
                continue
            k_ring = cal["k_ring"]
            kappa_fn: Callable[[float], float] = lambda g, kr=k_ring: kr
        else:
            cal = ring_kappa_from_calibration(calib, gap, R_typ)
            calibrations.append(cal)
            if (cal["kappa_c_rad_um"] is None
                    or not 0 < cal["k_ring"] < 1.0):
                attempts.append({"gap_um": gap, "ok": False,
                                 "reason": "标定越界或 k_ring 超出 (0,1)",
                                 "k_ring": cal["k_ring"]})
                continue
            k_ring = cal["k_ring"]
            kappa_fn: Callable[[float], float] = lambda g, kr=k_ring: kr
        rep = design_wdm(channels_nm, gap=gap, n_g=n_g, m=m,
                         kappa_fn=kappa_fn)
        if rep.get("ok") and rep["acceptance"]["passed"]:
            chosen = {"gap_um": gap, "k_ring": k_ring, "wdm": rep,
                      "calibration": cal}
            chosen_per_channel = per_channel if (
                (grid_calibrated and grid_valid)
                or (wavelength_calibrated and wl_valid)) else []
            attempts.append({"gap_um": gap, "ok": True,
                             "reason": "WDM 验收全过",
                             "il_drop_max": max(rep["metrics"]["il_drop_db"]),
                             "xt_min": min(rep["metrics"]["xt_min_db"])})
            break
        else:
            attempts.append({"gap_um": gap, "ok": False,
                             "reason": "WDM 验收未全过",
                             "il_drop_max": max(rep["metrics"]["il_drop_db"]),
                             "xt_min": min(rep["metrics"]["xt_min_db"])})

    # 系统验收（死标量比对）
    checks: List[Dict[str, Any]] = []
    if chosen is None:
        checks = [
            {"name": "FDTD 标定有效（标定文件覆盖 gap 扫描）",
             "ok": bool(any(c["kappa_c_rad_um"] is not None
                            for c in calibrations)),
             "detail": "；".join(
                 f"gap={c['gap_um']} κ_c="
                 f"{c['kappa_c_rad_um'] if c['kappa_c_rad_um'] is not None else '越界'}"
                 for c in calibrations)},
            {"name": "存在满足 WDM 规格的 gap（IL≤3dB/XT≥15dB）",
             "ok": False,
             "detail": "；".join(f"gap={a['gap_um']}: {a['reason']}"
                                 for a in attempts)},
        ]
        verdict = ("耦合器×WDM 组合未全过：gap 扫描 "
                   f"{[g for g in gap_scan]} 均未满足规格（FDTD 校准 k_ring "
                   "与解析假设偏差过大，需更小 gap 或更大环 R）")
    else:
        cal = chosen["calibration"]
        checks = [
            {"name": "FDTD 标定有效（κ_c>0，k_ring 自洽）",
             "ok": bool(cal["kappa_c_rad_um"] is not None
                        and cal["kappa_c_rad_um"] > 0
                        and 0 < cal["k_ring"] < 1.0),
             "detail": f"gap={cal['gap_um']}µm → κ_c="
                       f"{cal['kappa_c_rad_um']} rad/µm（L_couple="
                       f"{cal['L_couple_um']}µm）→ k_ring={cal['k_ring']}"},
            {"name": "WDM 系统验收（IL≤3dB/XT≥15dB/DRC）",
             "ok": bool(chosen["wdm"]["acceptance"]["passed"]),
             "detail": _wdm_detail(chosen["wdm"])},
            {"name": "FDTD 校准 vs 解析假设偏差（诚实报告）",
             "ok": bool(cal["ratio_fdtd_over_analytic"] is not None),
             "detail": f"k_ring={cal['k_ring']} vs 解析 gap_to_kappa="
                       f"{cal['k_analytic']}（比值 "
                       f"{cal['ratio_fdtd_over_analytic']}——"
                       + ("校准与解析一致"
                          if 0.8 <= cal["ratio_fdtd_over_analytic"] <= 1.25
                          else "偏差显著，解析假设需校准") + "）"},
        ]
        if grid_calibrated:
            kcs = [p["kappa_c_rad_um"] for p in chosen_per_channel
                   if p["kappa_c_rad_um"]]
            mono = bool(len(kcs) >= 2 and all(
                b >= a for a, b in zip(kcs, kcs[1:])))
            checks.append({
                "name": "全网格标定有效（κ_c(gap,λ) 双线性插值）",
                "ok": bool(grid_valid and mono),
                "detail": "；".join(
                    f"λ{p['channel_nm']}nm κ_c={p['kappa_c_rad_um']} "
                    f"k_ring={p['k_ring']}" for p in chosen_per_channel) +
                    ("" if mono else "（非单调）")})
        elif wavelength_calibrated:
            kcs = [p["kappa_c_rad_um"] for p in chosen_per_channel
                   if p["kappa_c_rad_um"]]
            mono = bool(len(kcs) >= 2 and all(
                b >= a for a, b in zip(kcs, kcs[1:])))
            checks.append({
                "name": "波长相关标定有效（κ_c(λ) 单调）",
                "ok": bool(wl_valid and mono),
                "detail": "；".join(
                    f"λ{p['channel_nm']}nm κ_c={p['kappa_c_rad_um']} "
                    f"k_ring={p['k_ring']}" for p in chosen_per_channel) +
                    ("" if mono else "（非单调）")})
        verdict = (f"耦合器×WDM 组合 PASS：FDTD 标定驱动 gap="
                   f"{chosen['gap_um']}µm（κ_c="
                   f"{cal['kappa_c_rad_um']} rad/µm → k_ring="
                   f"{cal['k_ring']}），{n_ch} 信道 WDM 验收全过"
                   f"（IL≤{max(chosen['wdm']['metrics']['il_drop_db']):.2f}"
                   f"dB，XT≥{min(chosen['wdm']['metrics']['xt_min_db']):.1f}"
                   f"dB）"
                   + (f"；波长相关：每信道 k_ring="
                      f"{[p['k_ring'] for p in chosen_per_channel]}"
                      if wavelength_calibrated else ""))
    accepted = all(c["ok"] for c in checks)

    return {
        "ok": True,
        "title": f"{n_ch}-信道 WDM × 方向耦合器组合（FDTD 标定驱动 gap）",
        "channels_nm": channels_nm, "gap_scan": gap_scan,
        "R_typ_um": round(R_typ, 3),
        "calibration_file": os.path.basename(_CALIB_PATH),
        "calibrations": calibrations,
        "attempts": attempts,
        "chosen_gap_um": chosen["gap_um"] if chosen else None,
        "chosen_k_ring": chosen["k_ring"] if chosen else None,
        "per_channel_kappa": (chosen_per_channel
                              if (grid_calibrated or wavelength_calibrated)
                              else None),
        "wavelength_calibrated": wavelength_calibrated,
        "grid_calibrated": grid_calibrated,
        "wdm": chosen["wdm"] if chosen else None,
        "acceptance": {"checks": checks, "passed": accepted},
        "verdict": verdict,
        "note": "bus↔ring 耦合本质是方向耦合器：κ_c 由 2D FDTD（D-55 双点"
                "标定）实测并沉淀为 PDK 标定文件（一次性后台标定，设计时"
                "秒级加载），经环形耦合有效长度 L_couple=2√(2R·gap) 换算 "
                "k_ring=sin(κ_c·L_couple) 驱动 WDM（D-42 级联传递）。诚实"
                "标注：L_couple 为环形耦合近似；D-57 实测 gap=0.25 时 "
                "k_ring=0.107 vs 解析 0.488（比值 0.22，解析偏乐观）；D-59 "
                "波长相关标定：κ_c(λ) 单调（1.50→1.60 增幅 ~27%），每信道"
                "按 λ 独立 k_ring（最弱耦合保守验收）——系统以 FDTD 校准"
                "为准并报告偏差。LLM 不进判决路径。",
    }


# ---------------------------------------------------------------------------
# D-44 统一设计包（注册 wdm_coupler kind）
# ---------------------------------------------------------------------------
def package_from_wdm_coupler(
        channels_nm: Optional[List[float]] = None, **kw: Any) -> Dict[str, Any]:
    """把耦合器×WDM 组合设计包装为 D-44 统一 DesignPackage。"""
    from lda_design.design_package import SCHEMA_VERSION, _now_iso

    r = design_wdm_with_coupler(channels_nm=channels_nm, **kw)
    acc = r["acceptance"]
    wdm = r["wdm"] or {}
    return {
        "package_id": f"wdm-coupler{len(r['channels_nm'])}ch",
        "schema_version": SCHEMA_VERSION,
        "kind": "wdm_coupler", "domain": "photon",
        "title": r["title"],
        "created_at": _now_iso(),
        "ir": {"schema_version": wdm.get("ir", {}).get("schema_version", "0.3"),
               "domain": "photon",
               "n_components": wdm.get("ir", {}).get("n_components", 0),
               "n_nets": wdm.get("ir", {}).get("n_nets", 0),
               "validate_errors": wdm.get("ir", {}).get("validate_errors", [])},
        "design": {"targets": {"channels_nm": r["channels_nm"],
                               "gap_scan": r["gap_scan"]},
                   "params": {"chosen_gap_um": r["chosen_gap_um"],
                              "chosen_k_ring": r["chosen_k_ring"],
                              "calibrations": r["calibrations"]},
                   "inverse_design": {"formula": "FDTD 标定 κ_c(gap)（D-55）"
                                                 "+ k_ring=sin(κ_c·2√(2R·gap))"
                                                 "（环形耦合近似）"}},
        "verification": {"checks": acc["checks"], "passed": bool(acc["passed"]),
                         "verdict": r["verdict"]},
        "artifacts": {"attempts": r["attempts"],
                      "wdm_metrics": (wdm.get("metrics") if wdm else None)},
        "honest_notes": r.get("note", ""),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="LDA 耦合器×WDM 组合设计")
    ap.add_argument("--channels", default="1550,1553,1556",
                    help="WDM 信道波长(nm)，逗号分隔")
    ap.add_argument("--gap_scan", default="0.25,0.30,0.35",
                    help="gap 扫描(µm)，逗号分隔")
    ap.add_argument("--wavelength", action="store_true",
                    help="波长相关标定模式（每信道按 λ 独立 k_ring）")
    ap.add_argument("--grid", action="store_true",
                    help="全网格标定模式（κ_c(gap,λ) 双线性插值，D-60）")
    args = ap.parse_args()
    ch = [float(x) for x in args.channels.split(",") if x.strip()]
    gs = [float(x) for x in args.gap_scan.split(",") if x.strip()]
    r = design_wdm_with_coupler(ch, gap_scan=gs,
                                wavelength_calibrated=args.wavelength,
                                grid_calibrated=args.grid)
    print(json.dumps({k: r[k] for k in
                      ("title", "channels_nm", "gap_scan", "R_typ_um",
                       "calibration_file", "calibrations", "attempts",
                       "chosen_gap_um", "chosen_k_ring",
                       "per_channel_kappa", "wavelength_calibrated",
                       "grid_calibrated", "acceptance", "verdict")},
                     ensure_ascii=False, indent=2, default=str))
    return 0 if r["acceptance"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
