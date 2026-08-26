"""LDA 性能漂移角扫（Merge-1b · v0.8.13）。

把 S3 从「可制造性角扫（DRC 复检）」升级为「性能漂移角扫」：
  工艺角缩放参数 → harness golden 正算性能 metric → 相对 TT 的漂移带报告。

设计原则：
  - 复用锚体系：性能值 = golden_value(bid, 缩放参数)（确定性死标量，LLM 不进判决）；
  - 按域定义角（⑥审计结论）：
      光子角  SS/TT/FF：w_scale/n_scale/gap_scale（尺寸/折射率容差）
      量子角  Q-SS/Q-TT/Q-FF：ej_scale/ec_scale（约瑟夫森能/充电能容差，
              transmon 领域无 SS/TT/FF 惯例——显式命名量子角避免概念混用）；
  - 诚实边界：角落数据为公开文献典型量级（非真实 PDK），发动期真实 PDK 替换。

输出：{device, bid, metric, corners: {角: (value, drift_pct)}, tol, passed}
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from lda_harness.golden import golden_value  # noqa: E402

# ---- 光子角（尺寸/折射率容差，公开文献典型） ----
PHOTON_CORNERS: Dict[str, Dict[str, float]] = {
    "SS": {"w_scale": 0.95, "n_scale": 0.99, "gap_scale": 1.05},
    "TT": {"w_scale": 1.00, "n_scale": 1.00, "gap_scale": 1.00},
    "FF": {"w_scale": 1.05, "n_scale": 1.01, "gap_scale": 0.95},
}

# ---- 量子角（EJ/EC 容差，transmon 域显式命名） ----
QUANTUM_CORNERS: Dict[str, Dict[str, float]] = {
    "Q-SS": {"ej_scale": 1.03, "ec_scale": 0.97},
    "Q-TT": {"ej_scale": 1.00, "ec_scale": 1.00},
    "Q-FF": {"ej_scale": 0.97, "ec_scale": 1.03},
}

# ---- 锚题参数 ↔ 角落缩放键映射 ----
# 光子角：w_scale 作用于几何尺寸，n_scale 作用于折射率
# 量子角：ej_scale/ec_scale 作用于能级参数
PHOTON_PARAM_MAP: Dict[str, Dict[str, str]] = {
    "B2": {"w_core": "w_scale", "h_core": "w_scale", "n_si": "n_scale"},
    "B4": {"R": "w_scale", "n_g": "n_scale"},
    "B20": {"deltaL_um": "w_scale", "n_core": "n_scale"},
    "B22": {"L_um": "w_scale", "n_eff": "n_scale"},
    "B21": {"R": "w_scale", "n_eff": "n_scale"},
}
QUANTUM_PARAM_MAP: Dict[str, Dict[str, str]] = {
    "B9": {"E_J": "ej_scale", "E_C": "ec_scale"},
    "B23": {"E_J": "ej_scale", "E_C": "ec_scale"},
    "B25": {"E_J": "ej_scale", "E_C": "ec_scale"},
}


def _scale_params(params: Dict[str, float],
                  corner: Dict[str, float],
                  param_map: Dict[str, str]) -> Dict[str, float]:
    """按角落缩放锚题参数（仅映射键参与；未映射键保持）。"""
    out = dict(params)
    for key, scale_key in param_map.items():
        if key in out and scale_key in corner:
            out[key] = out[key] * corner[scale_key]
    return out


def _drift_pct(value: float, base: float) -> float:
    return round((value - base) / abs(base) * 100.0, 4) if base else 0.0


def corner_scan_case(device: str, bid: str, params: Dict[str, float],
                     tol_pct: float, domain: Optional[str] = None
                     ) -> Dict[str, Any]:
    """单器件性能漂移角扫。

    domain: "photon" | "quantum"（缺省按 bid 自动判定：B9/B23/B25 为量子）。
    tol_pct: 相对 TT 漂移容差（%）——漂移超容差即 FAIL（死标量）。
    """
    if domain is None:
        domain = "quantum" if bid in QUANTUM_PARAM_MAP else "photon"
    corners = QUANTUM_CORNERS if domain == "quantum" else PHOTON_CORNERS
    param_map = (QUANTUM_PARAM_MAP if domain == "quantum"
                 else PHOTON_PARAM_MAP)
    pmap = param_map.get(bid)
    if pmap is None:
        return {"device": device, "bid": bid, "metric": "?",
                "error": f"bid {bid} 无角落映射（需在 PHOTON/QUANTUM_PARAM_MAP 登记）",
                "passed": False}

    metric = _metric_name(bid)
    results: Dict[str, Dict[str, float]] = {}
    base = None
    for cname, cscale in corners.items():
        scaled = _scale_params(params, cscale, pmap)
        val = golden_value(bid, scaled)
        if base is None:
            base = val
        results[cname] = {"value": round(val, 6),
                          "drift_pct": _drift_pct(val, base)}
    ttv = results["TT" if domain == "photon" else "Q-TT"]
    max_drift = max(abs(r["drift_pct"]) for r in results.values())
    return {
        "device": device, "bid": bid, "metric": metric,
        "domain": domain, "corners": results,
        "tt_value": ttv["value"], "max_drift_pct": max_drift,
        "tol_pct": tol_pct,
        "passed": max_drift <= tol_pct,
        "note": f"性能漂移带 [{min(r['value'] for r in results.values()):.4g}, "
                f"{max(r['value'] for r in results.values()):.4g}] "
                f"max_drift={max_drift}% vs tol={tol_pct}%",
    }


def corner_scan_report(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """批量角扫 → 汇总报告（含逐器件 PASS/FAIL）。"""
    rows = [corner_scan_case(**c) for c in cases]
    return {
        "rows": rows,
        "n_cases": len(rows),
        "n_pass": sum(1 for r in rows if r["passed"]),
        "all_pass": all(r["passed"] for r in rows),
        "honest_note": ("角落数据为公开文献典型量级（非真实 PDK）；"
                        "发动期真实 PDK 替换角落因子即升级。"),
    }


def _metric_name(bid: str) -> str:
    from lda_harness.benchmarks import BENCHMARK_DEFS
    d = BENCHMARK_DEFS.get(bid, {})
    return d.get("metric", bid)
