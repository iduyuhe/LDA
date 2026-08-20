"""LDA · 通用谱形逆设计闭环（D-24）。

收敛 D-03 BandDesignAgent（布拉格镜）与 D-11 RingBandAgent（环形）两套
近重复的「搜索参数命中目标谱形」闭环为统一框架：

  SpectrumInverseDesignAgent
    ├─ engine   : param → (wavelengths_um, spectrum)       物理引擎（FDTD / 解析）
    ├─ metric   : (wavelengths, spectrum) → float          谱形标量特征（FSR / R_min / …）
    ├─ oracle   : param → float                             独立物理锚特征（真值）
    ├─ target   : 目标特征 + 模式（match 等值命中 / threshold 阈值达标）
    ├─ bounds   : 参数范围 + discrete（整数扫描 / 连续黄金分割）
    └─ 验收     : 特征误差 ≤ tol_rel  且  方法一致性 ≤ method_tol

D-03 / D-11 成为框架的两个实例（ring_loop / multiband_loop 薄包装为框架）；
新谱形目标器件只须提供 engine / metric / oracle 三函数即插即用。

铁律不变：LLM 不进判决路径；PASS 由死标量比对（框架内确定性判据）决定。
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 目标描述
# ---------------------------------------------------------------------------
@dataclass
class SpectrumTarget:
    """通用谱形逆设计目标。"""

    name: str                       # 目标名（如 "ring-fsr" / "bragg-band"）
    param_name: str                 # 可调参数名（如 "R_um" / "periods"）
    bounds: Tuple[float, float]     # 搜索范围 [lo, hi]
    target_metric: float            # 目标特征值
    mode: str = "match"             # 'match'（|metric−target|/target）| 'threshold'（未达阈值部分）
    discrete: bool = False          # True：离散扫描（step 递增）；False：黄金分割
    step: float = 1.0               # 离散步长
    start: Optional[float] = None   # 离散起始（缺省 bounds[0]）
    max_iter: int = 40
    tol_rel: float = 0.05           # 特征误差容差（相对目标）
    method_tol: float = 0.05        # 方法一致性容差（engine 特征 vs oracle 特征）
    desc: str = ""

    def __post_init__(self):
        if self.start is None:
            self.start = self.bounds[0]
        if self.mode not in ("match", "threshold"):
            raise ValueError(f"mode 必须为 match/threshold，got {self.mode}")


# ---------------------------------------------------------------------------
# 特征误差（两种目标语义）
# ---------------------------------------------------------------------------
def metric_error(metric: float, target: SpectrumTarget) -> float:
    """特征相对误差。match：|m−t|/t；threshold：max(0,(t−m)/t)（未达部分）。"""
    t = max(float(target.target_metric), 1e-30)
    if target.mode == "threshold":
        return max(0.0, (t - float(metric)) / t)
    return abs(float(metric) - t) / t


# ---------------------------------------------------------------------------
# 搜索器
# ---------------------------------------------------------------------------
def _golden_search(obj: Callable[[float], float], lo: float, hi: float,
                   max_iter: int, on_iter: Callable[[int, float], None]
                   ) -> Tuple[float, int]:
    """黄金分割搜索（要求 obj 在 [lo,hi] 单谷）。返回 (最优参数, 迭代数)。"""
    gr = (math.sqrt(5.0) - 1.0) / 2.0
    a, b = lo, hi
    c = b - gr * (b - a)
    d = a + gr * (b - a)
    fc, fd = obj(c), obj(d)
    it = 0
    for it in range(1, max_iter + 1):
        on_iter(it, (a + b) / 2.0)
        if abs(b - a) < 1e-6 * max(abs(a), abs(b), 1.0):
            break
        if fc <= fd:
            b, d, fd = d, c, fc
            c = b - gr * (b - a)
            fc = obj(c)
        else:
            a, c, fc = c, d, fd
            d = a + gr * (b - a)
            fd = obj(d)
    return (a + b) / 2.0, it


def _scan_search(obj: Callable[[float], float], target: SpectrumTarget,
                 on_iter: Callable[[int, float], None]
                 ) -> Tuple[float, int]:
    """离散扫描：从 start 以 step 递增，误差达标即停（obj 单调递减假设）。"""
    v = float(target.start)
    it = 0
    last = v
    for it in range(1, target.max_iter + 1):
        last = v
        err = obj(v)
        on_iter(it, v)
        if err <= target.tol_rel:
            return v, it
        nxt = v + target.step
        if nxt > target.bounds[1]:
            break
        v = nxt
    return last, it


# ---------------------------------------------------------------------------
# 通用谱形逆设计编排器
# ---------------------------------------------------------------------------
class SpectrumInverseDesignAgent:
    """统一谱形逆设计闭环（D-24）。

    三函数即插即用：
      engine(param, **engine_kw) -> (wavelengths_um, spectrum)
      metric(wavelengths_um, spectrum) -> float
      oracle(param) -> float
    """

    def __init__(self):
        pass

    def run(self, target: SpectrumTarget,
            engine: Callable[..., Tuple[List[float], List[float]]],
            metric_fn: Callable[[List[float], List[float]], float],
            oracle_fn: Callable[[float], float],
            engine_kw: Optional[Dict[str, Any]] = None,
            method_check_fn: Optional[Callable[[float], float]] = None
            ) -> Dict[str, Any]:
        """统一谱形逆设计闭环。

        三函数即插即用：
          engine(param, **engine_kw) -> (wavelengths_um, spectrum)
          metric(wavelengths_um, spectrum) -> float
          oracle(param) -> float
        可选 method_check_fn(param, wls, spec) -> float：方法一致性误差（逐点/
        谱形级）。缺省用特征级 |metric−oracle|/oracle。wls/spec 为最终已算谱。
        """
        t0 = time.time()
        kw = dict(engine_kw or {})

        def obj(param: float) -> float:
            """搜索目标 = 特征相对误差（match 单谷 / threshold 单调）。"""
            wls, spec = engine(param, **kw)
            m = metric_fn(wls, spec)
            return metric_error(m, target)

        trace: List[Dict[str, Any]] = []
        on_iter = lambda it, p: trace.append({   # noqa: E731
            "iteration": it, target.param_name: round(p, 6),
            "metric_err": round(obj(p), 6)})

        if target.discrete:
            param_final, iterations = _scan_search(obj, target, on_iter)
        else:
            param_final, iterations = _golden_search(
                obj, target.bounds[0], target.bounds[1], target.max_iter, on_iter)

        # 最终谱形 + 验收（死代码判定）
        wls, spec = engine(param_final, **kw)
        m = metric_fn(wls, spec)
        o = oracle_fn(param_final)
        err = metric_error(m, target)
        if method_check_fn is not None:
            method_err = method_check_fn(param_final, wls, spec)
        else:
            method_err = abs(m - o) / (abs(o) + 1e-30)
        passed = err <= target.tol_rel and method_err <= target.method_tol
        elapsed = time.time() - t0

        report = {
            "target": {
                "name": target.name, "param_name": target.param_name,
                "bounds": list(target.bounds), "target_metric": target.target_metric,
                "mode": target.mode, "discrete": target.discrete,
                "tol_rel": target.tol_rel, "method_tol": target.method_tol,
            },
            "accepted": passed,
            "iterations": iterations,
            "final_params": {target.param_name: round(param_final, 6)},
            "final_metric": round(m, 6),
            "final_oracle": round(o, 6),
            "metric_err": round(err, 6),
            "method_err": round(method_err, 6),
            "final_band_curves": [{"wl": w, "value": s}
                                  for w, s in zip(wls, spec)],
            "loop_trace": trace,
            "elapsed_s": round(elapsed, 1),
            "verdict": self._verdict(target, m, o, err, method_err, passed,
                                     param_final, elapsed),
        }
        return report

    @staticmethod
    def _verdict(target: SpectrumTarget, metric: float, oracle: float,
                 err: float, method_err: float, passed: bool,
                 param_final: float, elapsed: float) -> str:
        if passed:
            return (
                f"{target.name} 谱形设计达标：{target.param_name}={param_final:.4f}，"
                f"特征={metric:.6f} vs 目标 {target.target_metric:.6f}"
                f"（误差 {err:.2e} ≤ {target.tol_rel}），方法一致性 {method_err:.2e}"
                f" ≤ {target.method_tol}；闭环耗时 {elapsed:.1f}s。"
                f"结果已可由「人」验收。")
        return (
            f"{target.name} 谱形未达标：特征={metric:.6f} vs 目标 "
            f"{target.target_metric:.6f}（误差 {err:.2e} > {target.tol_rel}），"
            f"方法一致性 {method_err:.2e}；请检查 bounds/目标/容差后重跑。"
            f"耗时 {elapsed:.1f}s。")


# ---------------------------------------------------------------------------
# 实例：环形谐振器（D-11，match 模式 + 黄金分割）
# ---------------------------------------------------------------------------
def ring_engine(R_um: float, n_g: float, wl0_um: float, Q: float, kappa: float,
                n_points: int = 81, span_um: float = None) -> Tuple[List[float], List[float]]:
    """环形 drop 端口透射谱（洛伦兹梳解析模型，复用 ring_loop）。"""
    from lda_agent.ring_loop import ring_fsr_analytic_nm, ring_transfer_spectrum
    fsr = ring_fsr_analytic_nm(R_um, n_g, wl0_um)
    span = span_um if span_um else 4.0 * fsr / 1000.0
    wls = [wl0_um + (i / (n_points - 1) - 0.5) * span for i in range(n_points)]
    drop = ring_transfer_spectrum(R_um, n_g, wl0_um, Q, kappa, wls)
    return wls, drop


def ring_metric(wls: List[float], drop: List[float]) -> float:
    """谱形标量特征：峰提取 FSR（nm）。"""
    from lda_agent.ring_loop import _extract_fsr_nm
    return _extract_fsr_nm(wls, drop)


def ring_oracle(R_um: float, n_g: float, wl0_um: float) -> float:
    """独立物理锚：解析 FSR 公式。"""
    from lda_agent.ring_loop import ring_fsr_analytic_nm
    return ring_fsr_analytic_nm(R_um, n_g, wl0_um)


def run_ring_spectrum(intent: Dict[str, Any]) -> Dict[str, Any]:
    """D-11 环形谱形逆设计（RingBandAgent 等价薄包装）。"""
    ex = intent.get("extra", {})
    R_lo, R_hi = [float(v) for v in ex.get("R_bounds", [8.0, 12.0])]
    n_g = float(ex.get("n_g", 4.2))
    wl0 = float(ex.get("wl0_um", 1.55))
    target_fsr = float(ex.get("target_fsr_nm", 9.15))
    target_tol = float(ex.get("target_tol", 0.03))
    method_tol = float(intent.get("tolerance_rel", 0.02))
    max_iter = int(intent.get("max_iterations", 40))
    n_points = int(ex.get("n_points", 81))
    target = SpectrumTarget(
        name="ring-fsr", param_name="R_um",
        bounds=(R_lo, R_hi), target_metric=target_fsr, mode="match",
        max_iter=max_iter, tol_rel=target_tol, method_tol=method_tol,
        desc="环形 drop 谱 FSR 命中目标（D-11）")
    rep = SpectrumInverseDesignAgent().run(
        target,
        engine=lambda R: ring_engine(R, n_g, wl0,
                                     float(ex.get("Q", 1.0e4)),
                                     float(ex.get("kappa", 0.05)),
                                     n_points=n_points),
        metric_fn=ring_metric,
        oracle_fn=lambda R: ring_oracle(R, n_g, wl0))
    # 对齐 RingBandAgent 报告字段（webui/外部依赖兼容）
    rep["geometry_type"] = intent.get("geometry_type", "ring")
    rep["final_R_um"] = rep["final_params"]["R_um"]
    rep["R_bounds"] = [R_lo, R_hi]
    rep["n_g"] = n_g
    rep["target_fsr_nm"] = target_fsr
    rep["final_fsr_analytic_nm"] = round(rep["final_oracle"], 6)
    rep["final_fsr_measured_nm"] = round(rep["final_metric"], 6)
    rep["final_spectrum_err"] = rep["metric_err"]
    rep["final_fsr_method_err"] = rep["method_err"]
    return rep


# ---------------------------------------------------------------------------
# 实例：布拉格镜（D-03，threshold 模式 + 离散扫描）
# ---------------------------------------------------------------------------
def _bragg_engine_factory(target, wavelengths_um, backend, dl_factor,
                          sponge, ramp, geo_kind="stack"):
    """构造布拉格镜物理引擎（DesignerAgent/SolverAgent，FDTD 每步昂贵）。"""
    from lda_agent.l1_protocol import DesignerAgent, SolverAgent

    def engine(periods: float, **kw):
        n = int(round(periods))
        doc = DesignerAgent.propose(
            target, periods=n, doc_id=f"bragg-band-N{n}",
            wavelengths_um=wavelengths_um, geo_kind=geo_kind)
        res = SolverAgent.solve(doc)
        return wavelengths_um, res.spectrum["transmission"]
    return engine


def _bragg_tmm_spectrum(target, wavelengths_um):
    """TMM 全透射谱（独立频域物理锚，逐点谱形用）。"""
    import os as _os
    import sys as _sys
    _dir = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "lda_solver")
    if _dir not in _sys.path:
        _sys.path.insert(0, _dir)
    import tmm

    def calc(periods: float) -> List[float]:
        n = int(round(periods))
        lam = target.target_wavelength_um
        qw_hi = lam / (4.0 * target.materials["sih"])
        qw_lo = lam / (4.0 * target.materials["silo"])
        layers = [(float("inf"), 1.0)]
        for _ in range(n):
            layers.append((qw_hi, target.materials["sih"]))
            layers.append((qw_lo, target.materials["silo"]))
        layers.append((float("inf"), 1.0))
        return tmm.solve_spectrum(
            {"layers": layers, "wavelengths_um": wavelengths_um})["transmission"]
    return calc


def _bragg_oracle_factory(target, wavelengths_um):
    """构造 TMM 物理锚（特征真值 = 阻带底线 R_min）。"""
    tmm_spec = _bragg_tmm_spectrum(target, wavelengths_um)

    def oracle(periods: float) -> float:
        return min(1.0 - t for t in tmm_spec(periods))
    return oracle


def _bragg_metric(wls: List[float], transmission: List[float]) -> float:
    """谱形标量特征：阻带底线 R_min = min(1−T)。"""
    return min(1.0 - t for t in transmission)


def run_bragg_spectrum(intent: Dict[str, Any]) -> Dict[str, Any]:
    """D-03 布拉格镜宽带谱形逆设计（BandDesignAgent 等价薄包装）。"""
    from lda_agent.l1_protocol import InterpreterAgent
    # 补 D-03 默认（与 main_band 一致；空 intent 也可跑）
    d = dict(intent)
    d.setdefault("geometry_type", "bragg_mirror")
    d.setdefault("target_wavelength_um", 1.55)
    d.setdefault("target_metric", "R")
    d.setdefault("threshold", 0.99)
    d.setdefault("tolerance_rel", 0.02)
    d.setdefault("max_iterations", 12)
    d.setdefault("initial_periods", 6)
    d.setdefault("materials", {"air": 1.0, "sih": 3.48, "silo": 1.44})
    ex = dict(d.get("extra") or {})
    ex.setdefault("band_span_um", 0.12)
    ex.setdefault("band_points", 11)
    ex.setdefault("backend", "numba_cpu")
    d["extra"] = ex
    intent = d
    target = InterpreterAgent.parse(intent)
    band_span = float(target.extra.get("band_span_um", 0.12))
    band_points = int(target.extra.get("band_points", 11))
    lam = target.target_wavelength_um
    if band_points < 2:
        band_points = 2
    wavelengths_um = [
        round(lam + (i / (band_points - 1) - 0.5) * 2.0 * band_span, 4)
        for i in range(band_points)]
    backend = target.extra.get("backend", "numba_cpu")
    dl_factor = float(target.extra.get("dl_factor", 60.0))
    sponge = int(target.extra.get("sponge", 60))
    ramp = int(target.extra.get("ramp", 200))
    initial = int(target.initial_periods)
    hi = int(initial + max(target.max_iterations - 1, 1))

    tgt = SpectrumTarget(
        name="bragg-band", param_name="periods",
        bounds=(initial, hi), target_metric=float(target.threshold),
        mode="threshold", discrete=True, step=1.0, start=initial,
        max_iter=target.max_iterations,
        tol_rel=float(target.threshold),          # 未达阈值部分相对容差
        method_tol=float(target.tolerance_rel),   # FDTD↔TMM 谱形一致性
        desc="布拉格镜全波段阻带底线 R≥threshold（D-03）")

    engine = _bragg_engine_factory(target, wavelengths_um, backend,
                                   dl_factor, sponge, ramp)
    oracle_fn = _bragg_oracle_factory(target, wavelengths_um)
    tmm_spec = _bragg_tmm_spectrum(target, wavelengths_um)

    def _method_check(periods: float, wls, spec_fdtd) -> float:
        """逐点方法一致性：全波段 max|ΔR| = max|(1−T_fdtd)−(1−T_tmm)|（同 D-03 verify_band）。"""
        tmm_T = tmm_spec(periods)
        return max(abs((1.0 - a) - (1.0 - b))
                   for a, b in zip(spec_fdtd, tmm_T))

    rep = SpectrumInverseDesignAgent().run(
        tgt, engine=engine, metric_fn=_bragg_metric, oracle_fn=oracle_fn,
        method_check_fn=_method_check)
    # 对齐 BandDesignAgent 报告字段（webui/CI 兼容）
    rep["scan_wavelengths_um"] = wavelengths_um
    rep["final_periods"] = int(rep["final_params"]["periods"])
    rep["final_band_min_R_fdtd"] = round(rep["final_metric"], 6)
    rep["final_band_min_R_oracle"] = round(rep["final_oracle"], 6)
    rep["final_max_abs_err"] = round(rep["method_err"], 6)
    return rep


if __name__ == "__main__":
    import json
    r1 = run_ring_spectrum({})
    r2 = run_bragg_spectrum({})
    print("ring accepted:", r1["accepted"], "R=%.4f" % r1["final_R_um"])
    print("bragg accepted:", r2["accepted"], "N=%d R_min=%.4f"
          % (r2["final_periods"], r2["final_band_min_R_fdtd"]))
    print(json.dumps(r1, ensure_ascii=False, indent=2)[:800])
