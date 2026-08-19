"""LDA · D-03 多波长/宽带闭环（验收锚扩展）。

把 1.2 单中心波长布拉格镜验收升级为「宽带谱形验收」：DesignAgent 增减周期数，
使整个 λ 扫描范围内阻带都满足 R ≥ threshold，且与 TMM 物理定律锚谱形一致
（全波段 max|ΔR| ≤ tol）。这把闭环从「单点达标」推进到「给定目标谱形达标」，
更接近真实光子设计任务（给定反射/透射谱形 → 反推堆叠）。

铁律不变：LLM 不进判决路径；是否 PASS 由死标量比对（FDTD vs TMM ORACLE）
决定。本闭环复用 1.2 的 DesignerAgent/SolverAgent（主权 FDTD 核），只新增
band 模式验收判据。
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from lda_agent.l1_protocol import InterpreterAgent, DesignerAgent, SolverAgent


# ---------------------------------------------------------------------------
# 路径（复用 l1_protocol 的 ORACLE 加载纪律）
# ---------------------------------------------------------------------------
_SOLVER_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lda_solver")


def _ensure_solver_on_path() -> None:
    if _SOLVER_DIR not in sys.path:
        sys.path.insert(0, _SOLVER_DIR)


# ---------------------------------------------------------------------------
# 宽带验收结果
# ---------------------------------------------------------------------------
@dataclass
class BandVerifyResult:
    """全波段谱形验收结果（与 VerifyResult 同源但判据为 band 模式）。"""
    metric: str = "R_band"
    band_min_R_fdtd: float = 0.0       # 扫描范围内 FDTD 反射率最小值（阻带底线）
    band_min_R_oracle: float = 0.0     # 同范围 TMM 反射率最小值
    max_abs_err: float = 0.0           # 全波段 max|R_fdtd - R_oracle|
    meets_target: bool = False         # 全波段 R_fdtd >= threshold
    within_tolerance: bool = False     # 全波段 |ΔR| <= tol_abs
    passed: bool = False
    n_points: int = 0
    per_wavelength: List[Dict[str, float]] = field(default_factory=list)


def verify_band(doc, result, threshold: float, tol_abs: float) -> BandVerifyResult:
    """宽带谱形验收：整个 λ 扫描范围内阻带达标 + 与 TMM ORACLE 谱形一致。

    判据（死代码，非 AI）：
      meets_target = 所有采样波长 R_fdtd >= threshold
      within_tol   = 所有采样波长 |R_fdtd - R_oracle| <= tol_abs
      passed       = 两者皆满足
    """
    _ensure_solver_on_path()
    import tmm
    oracle = tmm.solve_spectrum(doc.to_solver_spec())
    wls = result.spectrum["wavelengths_um"]
    fdtd_T = result.spectrum["transmission"]
    tmm_T = oracle["transmission"]

    per: List[Dict[str, float]] = []
    band_min_R_fdtd = 1.0
    band_min_R_oracle = 1.0
    max_err = 0.0
    all_meet = True
    all_within = True
    for w, t_f, t_o in zip(wls, fdtd_T, tmm_T):
        R_f = 1.0 - t_f
        R_o = 1.0 - t_o
        err = abs(R_f - R_o)
        max_err = max(max_err, err)
        band_min_R_fdtd = min(band_min_R_fdtd, R_f)
        band_min_R_oracle = min(band_min_R_oracle, R_o)
        if R_f < threshold:
            all_meet = False
        if err > tol_abs:
            all_within = False
        per.append({"wl": w, "R_fdtd": R_f, "R_oracle": R_o, "abs_err": err})

    passed = all_meet and all_within
    return BandVerifyResult(
        band_min_R_fdtd=band_min_R_fdtd,
        band_min_R_oracle=band_min_R_oracle,
        max_abs_err=max_err,
        meets_target=all_meet,
        within_tolerance=all_within,
        passed=passed,
        n_points=len(wls),
        per_wavelength=per,
    )


# ---------------------------------------------------------------------------
# 宽带设计闭环
# ---------------------------------------------------------------------------
class BandDesignAgent:
    """编排器：把 1.2 的 DesignAgent 升级为 band 模式闭环。"""

    def __init__(self, backend: str = "numba_cpu", dl_factor: float = 60.0,
                 sponge: int = 60, ramp: int = 200):
        self.backend = backend
        self.dl_factor = dl_factor
        self.sponge = sponge
        self.ramp = ramp

    def run(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        t0 = time.time()
        target = InterpreterAgent.parse(intent)
        band_span = float(target.extra.get("band_span_um", 0.12))
        band_points = int(target.extra.get("band_points", 11))
        lam = target.target_wavelength_um
        # 扫描波长：中心 λ0 ± band_span，band_points 点（含端点）
        if band_points < 2:
            band_points = 2
        wavelengths_um = [
            round(lam + (i / (band_points - 1) - 0.5) * 2.0 * band_span, 4)
            for i in range(band_points)
        ]
        target.extra.setdefault("backend", self.backend)
        target.extra.setdefault("dl_factor", self.dl_factor)
        target.extra.setdefault("sponge", self.sponge)
        target.extra.setdefault("ramp", self.ramp)

        trace: List[Dict[str, Any]] = []
        periods = target.initial_periods
        final_doc = None
        final_verify: Optional[BandVerifyResult] = None
        accepted = False

        for it in range(1, target.max_iterations + 1):
            doc = DesignerAgent.propose(
                target, periods=periods,
                doc_id=f"bragg-band-N{periods}-it{it}",
                wavelengths_um=wavelengths_um, geo_kind="stack")
            final_doc = doc
            res = SolverAgent.solve(doc)
            verify = verify_band(doc, res, target.threshold, target.tolerance_rel)
            final_verify = verify
            trace.append({
                "iteration": it,
                "periods": periods,
                "band_min_R_fdtd": round(verify.band_min_R_fdtd, 5),
                "band_min_R_oracle": round(verify.band_min_R_oracle, 5),
                "max_abs_err": round(verify.max_abs_err, 5),
                "meets_target": verify.meets_target,
                "within_tolerance": verify.within_tolerance,
                "passed": verify.passed,
                "backend": res.backend,
            })
            if verify.passed:
                accepted = True
                break
            periods += 1

        elapsed = time.time() - t0
        report = {
            "target": target.__dict__,
            "accepted": accepted,
            "iterations": len(trace),
            "final_doc_id": final_doc.doc_id if final_doc else "",
            "final_periods": periods,
            "final_band_min_R_fdtd": (
                final_verify.band_min_R_fdtd if final_verify else 0.0),
            "final_band_min_R_oracle": (
                final_verify.band_min_R_oracle if final_verify else 0.0),
            "final_max_abs_err": (
                final_verify.max_abs_err if final_verify else float("inf")),
            "scan_wavelengths_um": wavelengths_um,
            "loop_trace": trace,
            "verdict": self._verdict(accepted, final_verify, elapsed),
        }
        return report

    @staticmethod
    def _verdict(accepted: bool, verify: Optional[BandVerifyResult],
                 elapsed: float) -> str:
        if accepted and verify is not None:
            return (
                f"宽带设计达标：扫描范围内 FDTD 反射率底线 R_min="
                f"{verify.band_min_R_fdtd:.4f} ≥ 阈值，"
                f"且对 TMM 物理定律锚全波段 max|ΔR|={verify.max_abs_err:.4f} "
                f"在容差内；闭环耗时 {elapsed:.1f}s。结果已可由「人」验收。"
            )
        return (
            f"未在迭代上限内宽带达标：阻带底线 R_min="
            f"{verify.band_min_R_fdtd if verify else 'NA'}；"
            f"请增周期数 / 放宽阈值 / 提高分辨率后重跑。"
            f"闭环耗时 {elapsed:.1f}s。"
        )


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------
def main_band(intent: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if intent is None:
        intent = {
            "geometry_type": "bragg_mirror",
            "materials": {"air": 1.0, "sih": 3.48, "silo": 1.44},
            "target_wavelength_um": 1.55,
            "target_metric": "R",
            "threshold": 0.99,
            "tolerance_rel": 0.02,
            "max_iterations": 12,
            "initial_periods": 6,
            "extra": {
                "band_span_um": 0.12,
                "band_points": 11,
                "backend": "numba_cpu",
            },
        }
    agent = BandDesignAgent()
    return agent.run(intent)


if __name__ == "__main__":
    rep = main_band()
    print(json.dumps(rep, ensure_ascii=False, indent=2))
