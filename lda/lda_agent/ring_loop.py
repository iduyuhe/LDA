"""LDA · D-11 环形谱形逆设计闭环（验收锚扩展：布拉格镜 → 环形谐振器）。

D-03 把布拉格镜验收升级为宽带谱形；D-11 把同一"给定目标谱形 → 反推设计
参数"闭环扩展到环形谐振器（B11 谱形匹配）：agent 调半径 R 使 drop 端口
透射谱的 FSR 命中目标，形成"设计→仿真谱→物理锚验收"闭环。

双判据（与 D-03 的"阻带达标 + FDTD↔TMM 谱形一致"对称）：
  meets_target     ：解析 FSR_c(R) 对目标 target_fsr 的归一化误差 ≤ target_tol
                      （设计目标：谱形周期命中目标，等价 B11 golden）
  within_tolerance ：逐波长洛伦兹梳谱形**提取**的 FSR_measured 对解析 FSR_c
                      的相对误差 ≤ method_tol（方法一致性：谱形级计算 ↔
                      公式直算交叉对拍，替代布拉格镜的 FDTD↔TMM 角色）
  passed           = 两者皆满足

铁律不变：LLM 不进判决路径；PASS 由死标量比对决定。求解用解析环形传递
函数（物理定律锚，零依赖）——环形 FDTD 求解核为后续迭代项，不在本任务。
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# 环形 drop 端口透射谱（洛伦兹梳解析模型）
# ---------------------------------------------------------------------------
def ring_fsr_analytic_nm(R_um: float, n_g: float, wl0_um: float) -> float:
    """解析 FSR(nm)：FSR = λ²/(n_g·2πR)·1000。与 golden.b11 同式。"""
    return (wl0_um ** 2) / (n_g * 2.0 * math.pi * R_um) * 1000.0


def ring_transfer_spectrum(R_um: float, n_g: float, wl0_um: float, Q: float,
                           kappa: float, wavelengths_um: List[float]) -> List[float]:
    """环形谐振器 drop 端口透射谱（洛伦兹梳解析模型，逐波长）。

    峰位由 FSR(R) 展开（λ_res,k = λ0 + k·FSR），线宽 Γ=λ0/Q（Q 决定线宽），
    幅度由 kappa 调制（临界耦合以下随 kappa 增强）。峰位只依赖 R/n_g——
    这正是"谱形提取 FSR ↔ 解析 FSR 公式"交叉对拍的基础。
    """
    fsr_nm = ring_fsr_analytic_nm(R_um, n_g, wl0_um)
    lam0_nm = wl0_um * 1000.0
    half = (lam0_nm / max(Q, 1.0)) / 2.0
    # 覆盖扫描范围需要的峰数（上下各留 2 个）
    span_nm = (max(wavelengths_um) - min(wavelengths_um)) * 1000.0
    n_peaks = max(6, int(span_nm / max(fsr_nm, 1e-6)) + 6)
    drop = []
    for w_um in wavelengths_um:
        lam = w_um * 1000.0
        s = 0.0
        for k in range(-n_peaks // 2, n_peaks // 2 + 1):
            lam_res = lam0_nm + k * fsr_nm
            s += (half ** 2) / ((lam - lam_res) ** 2 + half ** 2)
        drop.append(s * min(kappa * 20.0, 1.0))
    return drop


def _extract_fsr_nm(wavelengths_um: List[float], drop: List[float]) -> float:
    """从逐波长谱形中提取 FSR(nm)：局部峰 + 抛物线插值精确定位 → 平均峰间距。"""
    wls_nm = [w * 1000.0 for w in wavelengths_um]
    peak_pos = []
    for i in range(1, len(drop) - 1):
        if drop[i] > drop[i - 1] and drop[i] >= drop[i + 1]:
            # 抛物线插值：峰顶位置在采样点间微调
            y0, y1, y2 = drop[i - 1], drop[i], drop[i + 1]
            denom = (y0 - 2.0 * y1 + y2)
            if abs(denom) < 1e-12:
                x_peak = wls_nm[i]
            else:
                delta = 0.5 * (y0 - y2) / denom
                x_peak = wls_nm[i] + delta * (wls_nm[i + 1] - wls_nm[i - 1]) / 2.0
            peak_pos.append(x_peak)
    if len(peak_pos) < 2:
        return 0.0
    # 去重：间距小于 0.3×中位间距视为同一峰（数值噪声），只保留高者
    peak_pos.sort()
    merged = [peak_pos[0]]
    for p in peak_pos[1:]:
        if p - merged[-1] < 0.15:
            merged[-1] = p
        else:
            merged.append(p)
    if len(merged) < 2:
        return 0.0
    spacings = [merged[i + 1] - merged[i] for i in range(len(merged) - 1)]
    return sum(spacings) / len(spacings)


# ---------------------------------------------------------------------------
# 环形谱形验收结果
# ---------------------------------------------------------------------------
@dataclass
class RingVerifyResult:
    metric: str = "spectrum_match"
    final_R_um: float = 0.0
    fsr_analytic_nm: float = 0.0     # 解析 FSR（公式直算）
    fsr_measured_nm: float = 0.0     # 谱形提取 FSR（逐波长谱峰间距）
    spectrum_err: float = 0.0        # |FSR_c − target|/target（设计目标）
    fsr_method_err: float = 0.0      # |FSR_measured − FSR_analytic|/FSR_analytic（方法一致性）
    meets_target: bool = False
    within_tolerance: bool = False
    passed: bool = False
    n_points: int = 0
    per_wavelength: List[Dict[str, float]] = field(default_factory=list)


def verify_ring(R_um: float, n_g: float, wl0_um: float, Q: float, kappa: float,
                target_fsr_nm: float, target_tol: float, method_tol: float,
                n_points: int = 81) -> RingVerifyResult:
    """环形谱形验收：设计目标命中 + 谱形提取与解析公式方法一致。

    死代码判定，LLM 不进判决路径。
    """
    fsr_analytic = ring_fsr_analytic_nm(R_um, n_g, wl0_um)
    spectrum_err = abs(fsr_analytic - target_fsr_nm) / target_fsr_nm

    # 逐波长谱形（覆盖目标 FSR ±2 倍，足够看到 ≥3 个峰）
    wl_span_um = 4.0 * target_fsr_nm / 1000.0
    wl0 = wl0_um
    wavelengths_um = [
        round(wl0 + (i / (n_points - 1) - 0.5) * wl_span_um, 5)
        for i in range(n_points)
    ]
    drop = ring_transfer_spectrum(R_um, n_g, wl0_um, Q, kappa, wavelengths_um)
    fsr_measured = _extract_fsr_nm(wavelengths_um, drop)
    fsr_method_err = (abs(fsr_measured - fsr_analytic) / fsr_analytic
                      if fsr_measured > 0 else float("inf"))

    meets = spectrum_err <= target_tol
    within = fsr_method_err <= method_tol
    per = [{"wl": w, "drop": d} for w, d in zip(wavelengths_um, drop)]
    return RingVerifyResult(
        final_R_um=R_um,
        fsr_analytic_nm=fsr_analytic,
        fsr_measured_nm=fsr_measured,
        spectrum_err=spectrum_err,
        fsr_method_err=fsr_method_err,
        meets_target=meets,
        within_tolerance=within,
        passed=meets and within,
        n_points=n_points,
        per_wavelength=per,
    )


# ---------------------------------------------------------------------------
# 环形谱形逆设计闭环
# ---------------------------------------------------------------------------
class RingBandAgent:
    """编排器：调 R 使 FSR 命中目标谱形（黄金分割单调收敛），最终谱形级验收。"""

    def __init__(self, n_points: int = 81):
        self.n_points = n_points

    def run(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        t0 = time.time()
        ex = intent.get("extra", {})
        R0 = float(ex.get("R_um", 10.0))
        R_lo, R_hi = [float(v) for v in ex.get("R_bounds", [8.0, 12.0])]
        n_g = float(ex.get("n_g", 4.2))
        wl0 = float(ex.get("wl0_um", 1.55))
        Q = float(ex.get("Q", 1.0e4))
        kappa = float(ex.get("kappa", 0.05))
        target_fsr = float(ex.get("target_fsr_nm", 9.15))
        target_tol = float(ex.get("target_tol", 0.03))
        method_tol = float(intent.get("tolerance_rel", 0.02))
        max_iter = int(intent.get("max_iterations", 40))
        if not (R_lo < R0 < R_hi):
            R0 = (R_lo + R_hi) / 2.0

        def f(R: float) -> float:
            # 设计目标：解析 FSR 对目标谱形的归一化误差（单调单谷 → 黄金分割稳）
            return (abs(ring_fsr_analytic_nm(R, n_g, wl0) - target_fsr)
                    / target_fsr)

        # 黄金分割搜索（R_bounds 内单调收敛）
        gr = (math.sqrt(5.0) - 1.0) / 2.0
        a, b = R_lo, R_hi
        c = b - gr * (b - a)
        d = a + gr * (b - a)
        fc, fd = f(c), f(d)
        trace: List[Dict[str, Any]] = []
        it = 0
        for it in range(1, max_iter + 1):
            trace.append({
                "iteration": it,
                "R": round((a + b) / 2.0, 6),
                "spectrum_err": round(f((a + b) / 2.0), 6),
            })
            if abs(b - a) < 1e-6 * max(abs(a), abs(b), 1.0):
                break
            if fc <= fd:
                b, d, fd = d, c, fc
                c = b - gr * (b - a)
                fc = f(c)
            else:
                a, c, fc = c, d, fd
                d = a + gr * (b - a)
                fd = f(d)
        R_final = (a + b) / 2.0

        # 最终谱形级验收（在收敛 R 下做逐波长谱提取 ↔ 解析对拍）
        verify = verify_ring(R_final, n_g, wl0, Q, kappa, target_fsr,
                             target_tol, method_tol, n_points=self.n_points)
        elapsed = time.time() - t0
        report = {
            "target": {
                "geometry_type": intent.get("geometry_type", "ring"),
                "target_wavelength_um": wl0,
                "target_metric": intent.get("target_metric", "spectrum_match"),
                "tolerance_rel": method_tol,
                "max_iterations": max_iter,
            },
            "accepted": verify.passed,
            "iterations": it,
            "final_R_um": R_final,
            "R_bounds": [R_lo, R_hi],
            "n_g": n_g,
            "Q": Q,
            "kappa": kappa,
            "target_fsr_nm": target_fsr,
            "final_fsr_analytic_nm": verify.fsr_analytic_nm,
            "final_fsr_measured_nm": verify.fsr_measured_nm,
            "final_spectrum_err": verify.spectrum_err,
            "final_fsr_method_err": verify.fsr_method_err,
            "target_tol": target_tol,
            "method_tol": method_tol,
            "final_band_curves": verify.per_wavelength,
            "loop_trace": trace,
            "verdict": self._verdict(verify, elapsed),
        }
        return report

    @staticmethod
    def _verdict(v: RingVerifyResult, elapsed: float) -> str:
        if v.passed:
            return (
                f"环形谱形设计达标：R={v.final_R_um:.4f}µm，"
                f"FSR(解析)={v.fsr_analytic_nm:.3f}nm vs 目标 "
                f"{v.fsr_measured_nm:.3f}nm(谱形提取)，谱形误差 "
                f"{v.spectrum_err:.2e} ≤ 容差，方法一致性 {v.fsr_method_err:.2e} "
                f"≤ 容差；闭环耗时 {elapsed:.1f}s。结果已可由「人」验收。"
            )
        return (
            f"环形谱形未达标：谱形误差={v.spectrum_err:.2e}，"
            f"方法一致性={v.fsr_method_err:.2e}；"
            f"请检查 R_bounds / target_fsr / Q 设置后重跑。耗时 {elapsed:.1f}s。"
        )


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------
def main_ring(intent: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if intent is None:
        # 默认：目标 FSR=9.15nm（与 seed/B11 对齐），R∈[8,12]µm
        intent = {
            "geometry_type": "ring",
            "target_wavelength_um": 1.55,
            "target_metric": "spectrum_match",
            "tolerance_rel": 0.02,
            "max_iterations": 40,
            "extra": {
                "R_um": 10.0,
                "R_bounds": [8.0, 12.0],
                "n_g": 4.2,
                "Q": 1.0e4,
                "kappa": 0.05,
                "target_fsr_nm": 9.15,
                "wl0_um": 1.55,
                "target_tol": 0.03,
                "backend": "numpy",
            },
        }
    agent = RingBandAgent()
    return agent.run(intent)


if __name__ == "__main__":
    rep = main_ring()
    print(json.dumps(rep, ensure_ascii=False, indent=2))
