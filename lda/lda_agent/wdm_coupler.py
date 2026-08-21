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


# ---------------------------------------------------------------------------
# PDK 标定文件
# ---------------------------------------------------------------------------
def _wdm_detail(wdm: Dict[str, Any]) -> str:
    """WDM 验收摘要（避免多行 f-string 跨括号，Python<3.12 兼容）。"""
    chks = wdm["acceptance"]["checks"]
    n_ok = sum(1 for c in chks if c["ok"])
    n_tot = len(chks)
    il_max = max(wdm["metrics"]["il_drop_db"])
    xt_min = min(wdm["metrics"]["xt_min_db"])
    return f"{n_ok}/{n_tot} 项：IL≤{il_max:.2f}dB XT≥{xt_min:.1f}dB"


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
                            n_g: float = 4.2, m: int = 170) -> Dict[str, Any]:
    """耦合器×WDM 组合设计：FDTD 标定驱动 gap 选择 → WDM 系统验收。"""
    if channels_nm is None:
        channels_nm = list(_DEF_CHANNELS)
    if gap_scan is None:
        gap_scan = list(_DEF_GAP_SCAN)
    if calib is None:
        calib = load_calibration()
    n_ch = len(channels_nm)
    # WDM 环半径（m 阶环）：R = m·λ0/(2π·n_g)
    R_typ = m * channels_nm[0] * 1e-3 / (2.0 * math.pi * n_g)

    calibrations: List[Dict[str, Any]] = []
    attempts: List[Dict[str, Any]] = []
    chosen: Optional[Dict[str, Any]] = None
    for gap in gap_scan:
        cal = ring_kappa_from_calibration(calib, gap, R_typ)
        calibrations.append(cal)
        if cal["kappa_c_rad_um"] is None or not 0 < cal["k_ring"] < 1.0:
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
        verdict = (f"耦合器×WDM 组合 PASS：FDTD 标定驱动 gap="
                   f"{chosen['gap_um']}µm（κ_c="
                   f"{cal['kappa_c_rad_um']} rad/µm → k_ring="
                   f"{cal['k_ring']}），{n_ch} 信道 WDM 验收全过"
                   f"（IL≤{max(chosen['wdm']['metrics']['il_drop_db']):.2f}"
                   f"dB，XT≥{min(chosen['wdm']['metrics']['xt_min_db']):.1f}"
                   f"dB）")
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
        "wdm": chosen["wdm"] if chosen else None,
        "acceptance": {"checks": checks, "passed": accepted},
        "verdict": verdict,
        "note": "bus↔ring 耦合本质是方向耦合器：κ_c 由 2D FDTD（D-55 双点"
                "标定）实测并沉淀为 PDK 标定文件（一次性后台标定，设计时"
                "秒级加载），经环形耦合有效长度 L_couple=2√(2R·gap) 换算 "
                "k_ring=sin(κ_c·L_couple) 驱动 WDM（D-42 级联传递）。诚实"
                "标注：L_couple 为环形耦合近似；D-57 实测 gap=0.25 时 "
                "k_ring=0.107 vs 解析 0.488（比值 0.22，解析偏乐观）——"
                "系统以 FDTD 校准为准并报告偏差。LLM 不进判决路径。",
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
    args = ap.parse_args()
    ch = [float(x) for x in args.channels.split(",") if x.strip()]
    gs = [float(x) for x in args.gap_scan.split(",") if x.strip()]
    r = design_wdm_with_coupler(ch, gap_scan=gs)
    print(json.dumps({k: r[k] for k in
                      ("title", "channels_nm", "gap_scan", "R_typ_um",
                       "calibration_file", "calibrations", "attempts",
                       "chosen_gap_um", "chosen_k_ring", "acceptance",
                       "verdict")}, ensure_ascii=False, indent=2, default=str))
    return 0 if r["acceptance"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
