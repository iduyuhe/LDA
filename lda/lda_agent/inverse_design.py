"""LDA · D-38 agent 逆设计通用框架落地（声明式注册表 + 跨场景复用）。

D-24 的 SpectrumInverseDesignAgent 已是通用框架（engine/metric/oracle/
method_check 三函数即插即用）。D-38 把它从"两个薄包装"升级为**声明式注册表**，
并用**同一套 agent** 落地到 4 个真实器件，证明"跨场景复用、非单点 hack"：

  器件         域      参数     目标特征       模式        搜索
  ──────────────────────────────────────────────────────────────
  RingResonator  光子   R_um     FSR(nm)       match       黄金分割
  BraggMirror    光子   periods  R_min(阻带)   threshold   离散扫描
  Transmon       量子   E_J      f01(GHz)      match       黄金分割
  RingAddDrop    光子   gap      Q_L(加载 Q)   match       黄金分割

每个器件只需注册一个声明式 spec（kind + 目标 + bounds + engine/metric/oracle），
run_inverse_design(kind, target_metric) 统一派发到同一个 SpectrumInverseDesignAgent——
新器件接入 = 新增一条 spec，零框架改动。

铁律：LLM 不进判决路径；PASS 由框架内死标量比对（特征误差 + 方法一致性）决定。
"""
from __future__ import annotations

import math
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = os.path.dirname(_HERE)
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)

from lda_agent.spectrum_loop import (SpectrumInverseDesignAgent,  # noqa: E402
                                     SpectrumTarget, metric_error)


# ---------------------------------------------------------------------------
# 4 个真实器件的 engine / metric / oracle（注册表用）
# ---------------------------------------------------------------------------
def _ring_triple(n_g: float, wl0_um: float, Q: float, kappa: float,
                 n_points: int):
    """环形 FSR 逆设计三函数（D-11/D-24 既有实例）。"""
    from lda_agent.spectrum_loop import (ring_engine, ring_metric, ring_oracle)

    def engine(R: float) -> Tuple[List[float], List[float]]:
        return ring_engine(R, n_g, wl0_um, Q, kappa, n_points=n_points)

    def metric_fn(wls: List[float], spec: List[float]) -> float:
        return ring_metric(wls, spec)

    def oracle_fn(R: float) -> float:
        return ring_oracle(R, n_g, wl0_um)

    return engine, metric_fn, oracle_fn, None


def _bragg_tmm_spectrum(lam: float, n_si: float, n_sio: float,
                        wavelengths_um: List[float]):
    """TMM 全透射谱（独立频域物理锚；搜索阶段瞬时）。"""
    _solver_dir = os.path.join(_LDA_ROOT, "lda_solver")
    if _solver_dir not in sys.path:
        sys.path.insert(0, _solver_dir)
    import tmm  # lda_solver/tmm.py

    def calc(periods: float) -> List[float]:
        n = int(round(periods))
        qw_hi, qw_lo = lam / (4.0 * n_si), lam / (4.0 * n_sio)
        layers = [(float("inf"), 1.0)]
        for _ in range(n):
            layers.append((qw_hi, n_si))
            layers.append((qw_lo, n_sio))
        layers.append((float("inf"), 1.0))
        return tmm.solve_spectrum(
            {"layers": layers, "wavelengths_um": wavelengths_um})["transmission"]

    return calc


def _bragg_triple(lam: float, n_si: float, n_sio: float,
                  wavelengths_um: List[float], dl_factor: float):
    """布拉格镜 R_min 逆设计三函数。

    搜索用 TMM（瞬时）；方法一致性 = 最终参数下一次真实 3D FDTD vs TMM
    （fdtd3d.solve_spectrum，~20s）——"搜索便宜、真值终验"，与 D-36 同构。
    """
    from lda_agent.spectrum_loop import _bragg_metric

    def _ensure():
        try:
            from lda_l2.device_library import _ensure_solver_on_path
            _ensure_solver_on_path()
        except Exception:
            pass

    tmm_spec = _bragg_tmm_spectrum(lam, n_si, n_sio, wavelengths_um)
    _ensure()

    def engine(periods: float) -> Tuple[List[float], List[float]]:
        return wavelengths_um, tmm_spec(periods)

    def metric_fn(wls: List[float], spec: List[float]) -> float:
        return _bragg_metric(wls, spec)

    def oracle_fn(periods: float) -> float:
        return min(1.0 - t for t in tmm_spec(periods))

    def method_check_fn(periods: float, wls, spec_tmm) -> float:
        import fdtd3d  # 真实 3D FDTD（终验一次）
        spec = {"layers": [], "wavelengths_um": wls}
        n = int(round(periods))
        qw_hi, qw_lo = lam / (4.0 * n_si), lam / (4.0 * n_sio)
        spec["layers"] = [(float("inf"), 1.0)]
        for _ in range(n):
            spec["layers"].append((qw_hi, n_si))
            spec["layers"].append((qw_lo, n_sio))
        spec["layers"].append((float("inf"), 1.0))
        r_fdtd = fdtd3d.solve_spectrum(spec, dl_factor=dl_factor,
                                       sponge=60, ramp=200)["transmission"]
        return max(abs((1.0 - a) - (1.0 - b))
                   for a, b in zip(r_fdtd, spec_tmm))

    return engine, metric_fn, oracle_fn, method_check_fn


def _transmon_triple(E_C: float, N: int, n_g: float):
    """Transmon f01 逆设计三函数（量子域，D-35 求解器）。

    "谱形" = 能级谱（levels_ghz）；metric = f01 = E1−E0；oracle = Koch 解析。
    """
    from lda_solver.transmon_solver import solve_transmon, koch_f01

    def engine(E_J: float) -> Tuple[List[float], List[float]]:
        sol = solve_transmon(E_J, E_C, n_g=n_g, N=N)
        return list(range(len(sol["levels_ghz"]))), sol["levels_ghz"]

    def metric_fn(wls: List[float], spec: List[float]) -> float:
        return float(spec[1] - spec[0])          # f01

    def oracle_fn(E_J: float) -> float:
        return koch_f01(E_J, E_C)

    return engine, metric_fn, oracle_fn, None


def _adddrop_triple(R_um: float, wg_width: float, n_g: float, wl0_um: float,
                    n_points: int):
    """环形 add-drop 加载 Q 逆设计三函数（D-37 器件）。

    "谱形" = drop 传递谱；metric = Q_L（谱线宽反解）；oracle = Q 分解解析。
    网格**自适应**：按 oracle 预估 FWHM 动态取 8×FWHM 跨度 × n_points 采样，
    保证任意 gap（Q_L~700~5e5，FWHM~2nm~0.003nm）都能解析线宽。
    """
    from lda_agent.ring_adddrop import (adddrop_spectrum, bending_loss_db_per_cm,
                                         gap_to_kappa, q_decomposition)

    def _grid_for(gap: float, kappa: float, alpha_bend: float):
        qd = q_decomposition(R_um, n_g, kappa, alpha_bend, wl0_um)
        fwhm_est = max(wl0_um * 1000.0 / qd["Q_L"], 1e-3)
        span = max(fwhm_est * 8.0, 0.01)
        # 网格中心对准最近谐振波长（谐振梳间距 FSR≈15nm >> 窗口，否则窗口内无峰）
        path_um = n_g * 2.0 * math.pi * R_um          # 光学周长（µm）
        m = int(round(path_um / wl0_um))
        center = path_um / max(m, 1)                   # λ_res（µm）
        return [round(center + (i / (n_points - 1) - 0.5) * span * 1e-3, 6)
                for i in range(n_points)]

    def engine(gap: float) -> Tuple[List[float], List[float]]:
        kappa = gap_to_kappa(gap)
        alpha_bend = bending_loss_db_per_cm(R_um)
        wl_grid = _grid_for(gap, kappa, alpha_bend)
        spec = adddrop_spectrum(wl_grid, R_um, n_g, kappa, alpha_bend, wl0_um)
        return spec["wavelengths_um"], spec["drop"]

    def _fwhm(wls: List[float], spec: List[float]) -> float:
        i0 = int(max(range(len(spec)), key=lambda i: spec[i]))
        half = spec[i0] / 2.0
        lo = i0
        while lo - 1 >= 0 and spec[lo - 1] >= half:
            lo -= 1
        hi = i0
        while hi + 1 < len(spec) and spec[hi + 1] >= half:
            hi += 1
        if hi <= lo:
            return float("nan")
        return (wls[hi] - wls[lo]) * 1000.0

    def metric_fn(wls: List[float], spec: List[float]) -> float:
        fwhm = _fwhm(wls, spec)
        return float(wl0_um * 1000.0 / fwhm) if fwhm == fwhm else 0.0

    def oracle_fn(gap: float) -> float:
        kappa = gap_to_kappa(gap)
        alpha_bend = bending_loss_db_per_cm(R_um)
        qd = q_decomposition(R_um, n_g, kappa, alpha_bend, wl0_um)
        return qd["Q_L"]

    return engine, metric_fn, oracle_fn, None


# ---------------------------------------------------------------------------
# 声明式注册表（新器件 = 新增一条 spec，零框架改动）
# ---------------------------------------------------------------------------
_INVERSE_DESIGNS: Dict[str, Dict[str, Any]] = {
    "RingResonator": {
        "title": "环形谐振器 · 目标 FSR(nm)",
        "param_name": "R_um",
        "bounds": (8.0, 12.0),
        "default_target": 9.15,
        "mode": "match", "discrete": False,
        "tol_rel": 0.03, "method_tol": 0.02,
        "desc": "drop 谱 FSR 命中目标（D-11/D-24 实例）",
        "build": _ring_triple,
        "build_kw": lambda ex: dict(n_g=float(ex.get("n_g", 4.2)),
                                    wl0_um=float(ex.get("wl0_um", 1.55)),
                                    Q=float(ex.get("Q", 1.0e4)),
                                    kappa=float(ex.get("kappa", 0.05)),
                                    n_points=int(ex.get("n_points", 81))),
        "domain": "photon",
    },
    "BraggMirror": {
        "title": "布拉格镜 · 目标阻带 R_min（最少周期）",
        "param_name": "periods",
        "bounds": (4, 12),
        "default_target": 0.99,
        "mode": "threshold", "discrete": True, "step": 1.0, "start": 4,
        "tol_rel": 0.99, "method_tol": 0.05,
        "desc": "TMM 搜索最少周期达标 + 终验真实 3D FDTD vs TMM（D-03 实例）",
        "build": _bragg_triple,
        "build_kw": lambda ex: dict(
            lam=float(ex.get("wl0_um", 1.55)),
            n_si=float(ex.get("n_si", 3.48)),
            n_sio=float(ex.get("n_sio", 1.44)),
            wavelengths_um=[round(1.55 + (i / 10 - 0.5) * 0.24, 4)
                            for i in range(11)],
            dl_factor=float(ex.get("dl_factor", 60.0))),
        "domain": "photon",
    },
    "Transmon": {
        "title": "Transmon · 目标 f01(GHz)（量子域）",
        "param_name": "E_J",
        "bounds": (5.0, 40.0),
        "default_target": 5.0,
        "mode": "match", "discrete": False,
        "tol_rel": 0.03, "method_tol": 0.03,
        "desc": "严格对角化 f01 命中目标（Koch 解析 ORACLE，D-35 求解器）",
        "build": _transmon_triple,
        "build_kw": lambda ex: dict(E_C=float(ex.get("E_C", 0.30)),
                                    N=int(ex.get("N", 20)),
                                    n_g=float(ex.get("n_g", 0.0))),
        "domain": "quantum",
    },
    "RingAddDrop": {
        "title": "环形 add-drop · 目标加载 Q（D-37 器件）",
        "param_name": "gap",
        "bounds": (0.15, 0.80),
        "default_target": 2500.0,
        "mode": "match", "discrete": False,
        "tol_rel": 0.10, "method_tol": 0.10,
        "desc": "drop 谱线宽反解 Q_L 命中目标（Q 分解解析 ORACLE，D-37 模型）",
        "build": _adddrop_triple,
        "build_kw": lambda ex: dict(R_um=float(ex.get("R_um", 6.0)),
                                    wg_width=float(ex.get("wg_width", 0.5)),
                                    n_g=float(ex.get("n_g", 4.2)),
                                    wl0_um=float(ex.get("wl0_um", 1.55)),
                                    n_points=int(ex.get("n_points", 401))),
        "domain": "photon",
    },
}


def list_designs() -> List[Dict[str, Any]]:
    return [{"kind": k, "title": v["title"], "param_name": v["param_name"],
             "bounds": list(v["bounds"]), "default_target": v["default_target"],
             "mode": v["mode"], "discrete": v["discrete"],
             "domain": v["domain"], "desc": v["desc"]}
            for k, v in _INVERSE_DESIGNS.items()]


def run_inverse_design(kind: str, target_metric: Optional[float] = None,
                       extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """统一派发：kind + 目标 → 同一个 SpectrumInverseDesignAgent 闭环。"""
    if kind not in _INVERSE_DESIGNS:
        return {"ok": False, "error": f"未知器件 {kind}；可选：{list(_INVERSE_DESIGNS)}",
                "kinds": list(_INVERSE_DESIGNS)}
    spec = _INVERSE_DESIGNS[kind]
    ex = dict(extra or {})
    target = float(target_metric if target_metric is not None
                   else spec["default_target"])
    engine, metric_fn, oracle_fn, method_check = spec["build"](
        **spec["build_kw"](ex))
    tgt = SpectrumTarget(
        name=kind.lower(), param_name=spec["param_name"],
        bounds=spec["bounds"], target_metric=target, mode=spec["mode"],
        discrete=spec["discrete"], step=spec.get("step", 1.0),
        start=spec.get("start"), max_iter=int(ex.get("max_iter", 40)),
        tol_rel=spec["tol_rel"], method_tol=spec["method_tol"],
        desc=spec["desc"])
    rep = SpectrumInverseDesignAgent().run(
        tgt, engine=engine, metric_fn=metric_fn, oracle_fn=oracle_fn,
        method_check_fn=method_check)
    rep["ok"] = True
    rep["kind"] = kind
    rep["title"] = spec["title"]
    rep["domain"] = spec["domain"]
    rep["param_name"] = spec["param_name"]
    return rep


def run_all_designs(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """4 器件全部经同一框架逆设计（跨场景复用演示）。"""
    out: Dict[str, Any] = {"framework": "SpectrumInverseDesignAgent (D-24/D-38)",
                           "devices": {}}
    for kind in _INVERSE_DESIGNS:
        out["devices"][kind] = run_inverse_design(kind, extra=extra)
    out["all_passed"] = all(
        v.get("accepted") for v in out["devices"].values())
    return out


if __name__ == "__main__":
    import json
    res = run_all_designs()
    print(json.dumps(
        {"framework": res["framework"], "all_passed": res["all_passed"],
         "devices": {k: {"accepted": v.get("accepted"),
                         "final": v.get("final_params"),
                         "metric_err": v.get("metric_err"),
                         "method_err": v.get("method_err"),
                         "elapsed_s": v.get("elapsed_s")}
                     for k, v in res["devices"].items()}},
        ensure_ascii=False, indent=2))
