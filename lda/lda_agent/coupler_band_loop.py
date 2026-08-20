"""LDA · 耦合器件多波长验收闭环（D-23）。

把 D-01 的单波长耦合器件验收锚扩展为**多波长扫描**（与 D-03 多波长/宽带
谱形验收主题一致）：
  - 方向耦合器（DC）：λ∈[λ_min,λ_max] 逐点 FDFD 超模法 κ_oracle(λ) ↔
    FDTD 超模投影 κ_fdtd(λ) 交叉对拍（方法独立，LLM 不进判决路径）
  - 对称 Y 分支分束器（YB）：λ∈[λ_min,λ_max] 逐点对称性定理（50/50）↔
    FDTD 两臂能流平衡度(λ)

验收判据（全波段谱形验收）：
  DC：① ORACLE κ(λ) 严格单调递增（真值谱形，Lc∝λ）；② FDTD 与 ORACLE 的
      全波段**平均**相对偏差 ≤ tol_kappa_mean；③ 最差点相对偏差 ≤ tol_kappa_max
      （防崩溃/完全错误）。诚实边界：κ=(βs−βa)/2 是"大数小差"量，标量近似 +
      网格色散下 FDTD 提取精度固有 ~10–45%（波长依赖），故用平均偏差而非
      逐点严格容差，max 容差仅排除完全错误。
  YB：max_λ |fracA−0.5| ≤ tol_balance，且全波段两臂总功率为正
      （对称性定理任意波长成立，精度高）。

工程纪律（D-23 实测暴露并修复）：
  - 多波长扫描必须**固定网格 dl**（不随 λ 变）：否则 FDFD 离散不连续 →
    超模选模漂移 → κ 非物理振荡（首次实测定格在 fdfd_coupler_supermodes
    加基模带锚定 + CouplerTarget.dl_um 固定网格）。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Dict, List, Optional

import numpy as np

from lda_agent.coupler_loop import CouplerAgent, CouplerTarget


def _monotonic_increasing(vals: List[float]) -> bool:
    """严格单调递增（物理趋势：DC 耦合长度 Lc∝λ → κ 随 λ 增）。"""
    return bool(vals and len(vals) >= 2
                and all(b > a for a, b in zip(vals, vals[1:])))


@dataclass
class CouplerBandTarget:
    """多波长耦合器件验收目标。"""

    kind: str                       # 'dc' 方向耦合器 | 'ybranch' 对称分束器
    wl_min_um: float = 1.50
    wl_max_um: float = 1.60
    n_points: int = 7
    label: str = ""
    # dc 专属（转发 CouplerTarget）
    gap_um: float = 0.3
    # yb 专属
    sep_um: float = 1.6
    # 判据
    tol_kappa: float = 0.25         # 单点判据（保留 D-01 语义）
    tol_kappa_mean: float = 0.25    # DC 全波段平均相对偏差容差
    tol_kappa_max: float = 0.75     # DC 全波段最差点相对偏差上限（防崩溃/完全错误）
    tol_balance: float = 0.10
    backend: str = "auto"
    dl_um: Optional[float] = None   # 固定网格步长（None → 取波段中心 wl/24。
                                    # 多波长扫描必须固定网格：dl 随 λ 变会引入
                                    # FDFD 离散不连续 → 超模选模漂移（D-23 实测））

    def wavelengths(self) -> List[float]:
        """等距波长采样（n_points 点）。"""
        if self.n_points < 2:
            return [self.wl_min_um]
        return [self.wl_min_um + (self.wl_max_um - self.wl_min_um) * i / (self.n_points - 1)
                for i in range(self.n_points)]


@dataclass
class CouplerBandOutcome:
    label: str
    kind: str
    passed: bool
    n_points: int
    wl_list: List[float]
    per_wl: List[dict]
    band_mean_kappa_rel: Optional[float]
    band_max_kappa_rel: Optional[float]
    band_max_balance: Optional[float]
    band_all_positive: Optional[bool]
    oracle_monotonic: Optional[bool]
    verdict: str
    elapsed: float

    def to_dict(self) -> dict:
        return {
            "label": self.label, "kind": self.kind, "passed": self.passed,
            "n_points": self.n_points, "wavelengths_um": self.wl_list,
            "per_wavelength": self.per_wl,
            "band_mean_kappa_rel": self.band_mean_kappa_rel,
            "band_max_kappa_rel": self.band_max_kappa_rel,
            "band_max_balance": self.band_max_balance,
            "band_all_power_positive": self.band_all_positive,
            "oracle_monotonic": self.oracle_monotonic,
            "verdict": self.verdict,
            "elapsed_s": round(self.elapsed, 1),
        }


class CouplerBandAgent:
    """多波长耦合器件验收编排器（D-23）。"""

    def run(self, t: CouplerBandTarget) -> CouplerBandOutcome:
        t0 = time.time()
        wls = t.wavelengths()
        dl_um = t.dl_um
        if dl_um is None:
            dl_um = (t.wl_min_um + t.wl_max_um) / 2.0 / 24.0
        base = CouplerTarget(
            kind=t.kind, wl_um=wls[0], gap_um=t.gap_um, sep_um=t.sep_um,
            tol_kappa=t.tol_kappa, tol_balance=t.tol_balance, backend=t.backend,
            dl_um=dl_um)
        agent = CouplerAgent()

        per_wl: List[dict] = []
        any_missing = False
        anchor = None               # 波长连续追踪：上一波长的超模 neff 对
        for wl in wls:
            tt = replace(base, wl_um=wl, oracle_anchor=anchor)
            out = agent.run(tt)
            m = out.metrics
            if t.kind == "dc":
                entry = {
                    "wl_um": round(float(wl), 4),
                    "passed": bool(m.get("kappa_rel_dev") is not None),  # 提取成功
                    "neff_s": m.get("neff_s"), "neff_a": m.get("neff_a"),
                    "kappa_oracle": m.get("kappa_oracle"),
                    "kappa_fdtd": m.get("kappa_fdtd"),
                    "kappa_method": m.get("kappa_method"),
                    "kappa_rel_dev": m.get("kappa_rel_dev"),
                    "error": m.get("error"),
                }
                if entry["kappa_rel_dev"] is None:
                    any_missing = True
                if out.passed and m.get("neff_s") is not None:
                    anchor = (m["neff_s"], m["neff_a"])
            else:  # ybranch
                entry = {
                    "wl_um": round(float(wl), 4), "passed": bool(out.passed),
                    "fracA": m.get("fracA"), "fracB": m.get("fracB"),
                    "balance_abs": m.get("balance_abs"),
                    "total_power_positive": m.get("total_power_positive"),
                    "error": m.get("error"),
                }
                if entry["balance_abs"] is None:
                    any_missing = True
            per_wl.append(entry)

        # ---- 全波段汇总 ----
        if t.kind == "dc":
            rels = [e["kappa_rel_dev"] for e in per_wl
                    if e.get("kappa_rel_dev") is not None]
            band_mean_kappa_rel = float(np.mean(rels)) if rels else None
            band_max_kappa_rel = max(rels) if rels else None
            band_max_balance = None
            band_all_positive = None
            ko_vals = [e["kappa_oracle"] for e in per_wl
                       if e.get("kappa_oracle") is not None]
            oracle_mono = _monotonic_increasing(ko_vals)
            all_extracted = not any_missing
            band_ok = (band_mean_kappa_rel is not None
                       and band_mean_kappa_rel <= t.tol_kappa_mean
                       and band_max_kappa_rel is not None
                       and band_max_kappa_rel <= t.tol_kappa_max
                       and oracle_mono and all_extracted)
            if band_ok:
                verdict = (f"全波段验收 PASS：ORACLE κ(λ) 单调递增（真值谱形），"
                           f"FDTD 平均偏差 {band_mean_kappa_rel:.4f} ≤ {t.tol_kappa_mean}，"
                           f"最差 {band_max_kappa_rel:.4f} ≤ {t.tol_kappa_max}，"
                           f"{len(wls)} 点全提取成功")
            elif not oracle_mono:
                verdict = "全波段验收 FAIL：ORACLE κ(λ) 非单调递增（超模选模不稳）"
            elif any_missing:
                verdict = "全波段验收 FAIL：存在波长点 κ 提取失败（见 per_wavelength）"
            else:
                verdict = (f"全波段验收 FAIL：FDTD 平均偏差 {band_mean_kappa_rel:.4f}"
                           f" > {t.tol_kappa_mean} 或最差 {band_max_kappa_rel:.4f}"
                           f" > {t.tol_kappa_max}")
        else:  # ybranch
            band_mean_kappa_rel = None
            band_max_kappa_rel = None
            bal = [e["balance_abs"] for e in per_wl
                   if e.get("balance_abs") is not None]
            pos = [e.get("total_power_positive") for e in per_wl]
            band_max_balance = max(bal) if bal else None
            band_all_positive = bool(pos) and all(p is True for p in pos)
            oracle_mono = True
            all_point_pass = all(e["passed"] for e in per_wl)
            band_ok = (band_max_balance is not None
                       and band_max_balance <= t.tol_balance
                       and band_all_positive and all_point_pass)
            if band_ok:
                verdict = (f"全波段验收 PASS：max_λ 平衡度 {band_max_balance:.4f}"
                           f" ≤ 容差 {t.tol_balance}，全波段功率为正，"
                           f"{len(wls)} 波长点全 PASS")
            elif any_missing:
                verdict = "全波段验收 FAIL：存在波长点功率测量失败（见 per_wavelength）"
            else:
                verdict = (f"全波段验收 FAIL：max_λ 平衡度 {band_max_balance:.4f}"
                           f" > 容差 {t.tol_balance} 或功率不正")

        label = t.label or (f"DC gap={t.gap_um} λ∈[{t.wl_min_um},{t.wl_max_um}]"
                            if t.kind == "dc"
                            else f"YB sep={t.sep_um} λ∈[{t.wl_min_um},{t.wl_max_um}]")
        return CouplerBandOutcome(
            label=label, kind=t.kind, passed=band_ok, n_points=len(wls),
            wl_list=[round(w, 4) for w in wls], per_wl=per_wl,
            band_mean_kappa_rel=band_mean_kappa_rel,
            band_max_kappa_rel=band_max_kappa_rel,
            band_max_balance=band_max_balance,
            band_all_positive=band_all_positive,
            oracle_monotonic=oracle_mono,
            verdict=verdict, elapsed=time.time() - t0)


# ---------------------------------------------------------------------------
# 默认案例（本地/CI 演示入口）
# ---------------------------------------------------------------------------
def main_band(cases: Optional[List[CouplerBandTarget]] = None) -> List[CouplerBandOutcome]:
    """跑默认多波长验收案例（DC gap=0.3 + YB），打印逐波长与全波段结果。"""
    if cases is None:
        cases = [
            CouplerBandTarget(kind="dc", gap_um=0.3, n_points=7,
                              label="DC gap=0.3µm 多波长验收"),
            CouplerBandTarget(kind="ybranch", sep_um=1.6, n_points=7,
                              label="YB 对称分束器多波长验收"),
        ]
    outcomes = []
    n_pass = 0
    for c in cases:
        out = CouplerBandAgent().run(c)
        outcomes.append(out)
        if out.passed:
            n_pass += 1
        flag = "PASS" if out.passed else "FAIL"
        print(f"[{flag}] {out.label}")
        for e in out.per_wl:
            if out.kind == "dc":
                print(f"    λ={e['wl_um']}µm  κ_oracle={e['kappa_oracle']} "
                      f"κ_fdtd={e['kappa_fdtd']} ({e['kappa_method']}) "
                      f"rel={e['kappa_rel_dev']}")
            else:
                print(f"    λ={e['wl_um']}µm  fracA={e['fracA']} "
                      f"fracB={e['fracB']} balance={e['balance_abs']}")
        print(f"    → {out.verdict}")
    print(f"\n多波长耦合器件验收闭环：{n_pass}/{len(outcomes)} PASS")
    return outcomes


if __name__ == "__main__":
    main_band()
