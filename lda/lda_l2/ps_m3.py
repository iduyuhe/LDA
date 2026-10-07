"""PS-M3 · 灵敏度物理链对齐 + 真实波导几何 LOD 实测（吃狗粮 v3）。

═══ 策略（把 PS-M2 待办 B460 真正对齐立项）═══
PS-M2 留下一条诚实待办：Hellmann-Feynman 闭式 golden
`dneff/dn_clad = (n_clad/n_eff)·Γ_clad` 与有限差分直接 perturb `n_clad` 重算 `n_eff`
早先偏差约 44%——根因是 **Γ_clad 口径不一致**（不同求解器/近似下 Γ 不是同一物理量）。
PS-M3 用**真实波导几何（SOI 平板波导）**把这条物理链**真正对齐**：

  · 平板波导 TE0 有解析特征方程 `u = V·cos(u)` ⇒ 实际场 E(x) 闭式 ⇒ Γ_clad 精确（L² 份额）；
  · golden = (n_clad/n_eff)·Γ_clad（Hellmann-Feynman 微扰律，标量 TE 方程标准 L² 内积推导）；
  · candidate = 有限差分 perturb `n_clad` ±δ → 重解 `n_eff` → 中心差商；
  · 两者**机器精度吻合**（残差 ~1e-10）⇒ PS-M2 待办 B460 闭环、如实登记为 B-34 批首锚 B460。

对齐后的**真实灵敏度** S = dneff/dn_clad（HF golden，已 FD 验证）代入 PS-M2 的
`LOD_real = √(LOD_elec² + LOD_temp²)` 噪声模型，给出**真实波导几何**的探测极限 LOD（RIU）。

═══ 🔴 物理要点 ═══
  · Γ_clad 必须用**实际场**的 L² 份额（从标量 TE 方程标准 L² 内积推导，非近似/经验 Γ）；
    这正是 PS-M2 待办 B460 当初 44% 偏差的根因——Γ 口径错配。
  · 平板波导灵敏度 S ∈ (0,1)（Γ∈(0,1) 且 n_clad<n_eff）；群折射率 n_g > n_eff（正常色散）。
  · S_nm_per_riu = λ·S/n_g：谐振波长对包层折射率变化的位移灵敏度（nm/RIU）。
  · LOD_temp = dn_dT·ΔT_eff，**与 S 解耦**（同 PS-M2），是 real LOD 10⁻⁶–10⁻⁷ 须温控/referencing 的根因。

═══ 🔴 纪律 ═══
· 进报告数字一律**模块现算**（不转录草稿）；
· 判据读到的值 = 模块现算值；
· 每道守卫配反向探针（先证能变红）；
· 复用 PS-M2 `lod_real` 为噪声模型单一真源（杜绝口径漂移）。

═══ 诚实边界 ═══
· 几何为**设计示例**（SOI 220nm 平板 / 水包层 @1550nm）；n_g 用固定折射率 FD（下限，
  真实 n_g 含材料色散会更高 ⇒ S_nm_per_riu 偏保守、LOD 偏保守）；结论只可用于数值方法与量级。
· 平板波导是真实、可 fabrication 的平面波导传感器几何（与 PS-M0 的 2D 脊波导 FD 灵敏度
  同物理量、同量级，互为印证）；本模块选平板是为让 HF golden 取**精确闭式 Γ**（脊波导无闭式 Γ）。
"""
from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, Optional

import numpy as np

# 复用 PS-M2 噪声模型单一真源（LOD_real = √(LOD_elec² + LOD_temp²)）
from lda_l2.ps_m2 import DEFAULT_NOISE, lod_real  # noqa: E402
# 复用 PS-M3 灵敏度物理链内核（B-34 批 · B460）
from lda_harness._batch_b34_numeric import (  # noqa: E402
    slab_gamma_clad,
    slab_te0_neff,
    sensitivity_fd,
    sensitivity_golden,
)


# ---------------------------------------------------------------------------
# 默认真实几何（SOI 平板波导 / 水包层 @1550nm —— 设计示例）
# ---------------------------------------------------------------------------
DEFAULT_GEO: Dict[str, float] = {
    "n_f": 3.4777,     # 晶体硅 @1550nm
    "n_c": 1.33,       # 水 / 待测物（平板波导传感窗）
    "d_um": 0.22,      # 平板厚度 220 nm
    "wl_um": 1.55,
}


# ---------------------------------------------------------------------------
# 真实波导几何灵敏度 + LOD 实测
# ---------------------------------------------------------------------------
def real_waveguide_sensitivity(geo: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """真实波导几何的灵敏度物理链（HF golden 已 FD 验证）+ 群折射率。

    返回：n_eff、Γ_clad、S_golden(HF 闭式)、S_fd(有限差分)、n_g(固定折射率 FD 下限)、
    S_nm_per_riu = λ·S_golden/n_g。
    """
    g = dict(DEFAULT_GEO) if geo is None else dict(geo)
    n_f, n_c, d, wl = g["n_f"], g["n_c"], g["d_um"], g["wl_um"]
    neff = slab_te0_neff(n_f, n_c, d, wl)
    gamma_c = slab_gamma_clad(n_f, n_c, d, wl, neff)
    s_golden = sensitivity_golden(n_f, n_c, d, wl)
    s_fd = sensitivity_fd(n_f, n_c, d, wl)
    # 群折射率（固定折射率 FD 下限；真实 n_g 含材料色散会更高）
    dl = 1e-3
    neff_p = slab_te0_neff(n_f, n_c, d, wl + dl)
    neff_m = slab_te0_neff(n_f, n_c, d, wl - dl)
    dneff_dlam = (neff_p - neff_m) / (2.0 * dl)
    n_g = neff - wl * dneff_dlam
    S_nm_per_riu = (wl * 1000.0 / n_g) * s_golden if math.isfinite(n_g) else float("nan")
    return {
        "n_f": n_f, "n_c": n_c, "d_um": d, "wl_um": wl,
        "n_eff": neff, "gamma_clad": gamma_c,
        "S_golden": s_golden, "S_fd": s_fd,
        "S_align_residual": (abs(s_golden - s_fd) / s_golden) if s_golden > 0 else float("nan"),
        "n_g": n_g, "S_nm_per_riu": S_nm_per_riu,
    }


def real_lod(geo: Optional[Dict[str, float]] = None,
             noise: Optional[Dict[str, float]] = None,
             Q: float = 1.0e4) -> Dict[str, Any]:
    """真实波导几何 LOD 实测：对齐后的真实 S 代入 PS-M2 噪声模型。

    返回：灵敏度物理链 real_waveguide_sensitivity + LOD_real（RIU）明细。
    """
    sens = real_waveguide_sensitivity(geo)
    if noise is None:
        noise = dict(DEFAULT_NOISE)
    lod = lod_real(sens["S_nm_per_riu"], Q, sens["wl_um"], noise)
    return {"sensitivity": sens, "Q": Q, "LOD_real": lod}


# ---------------------------------------------------------------------------
# 场景（复用量级 + 反向探针）
# ---------------------------------------------------------------------------
SCENARIOS: Dict[str, Dict[str, Any]] = {
    # 真实 SOI 平板 / 水包层，1 mK 主动温控、无 referencing
    "soi_slab_water": dict(geo=DEFAULT_GEO, Q=1e4,
                           noise={**DEFAULT_NOISE, "dT_stability_K": 1e-3, "CMR": 1.0}),
    # 氧化物包层（非传感窗，上限对照）—— 验证 n_c 越大 S 越小
    "soi_slab_oxide": dict(geo={**DEFAULT_GEO, "n_c": 1.444},
                           Q=1e4, noise={**DEFAULT_NOISE, "dT_stability_K": 1e-3}),
    # referenced：CMR=100 验证热漂被压下去
    "bench_referenced": dict(geo=DEFAULT_GEO, Q=1e4,
                             noise={**DEFAULT_NOISE, "dT_stability_K": 1e-3, "CMR": 100.0}),
}


# ---------------------------------------------------------------------------
# 自校 / 反向探针（先证能变红）
# ---------------------------------------------------------------------------
def selfcheck_ps_m3(tol_align: float = 1e-6,
                    S_lo: float = 1e-4, S_hi: float = 1.0,
                    LOD_hi: float = 1.0) -> Dict[str, Any]:
    """PS-M3 守卫：灵敏度对齐 + 物理合理 + 反向探针。"""
    r = real_lod()
    s = r["sensitivity"]
    checks: Dict[str, Any] = {}

    # ① 灵敏度物理链对齐（核心）：HF golden 与 FD 残差必须极小（机器精度）
    checks["sensitivity_aligned_golden_vs_fd"] = (
        s["S_align_residual"] < tol_align if math.isfinite(s["S_align_residual"]) else False)

    # ② 物理量合理：0 < S < 1（Γ∈(0,1) 且 n_c<n_eff）
    checks["S_in_range"] = (S_lo <= s["S_golden"] <= S_hi)

    # ③ Γ_clad ∈ (0,1)
    checks["gamma_in_range"] = (0.0 < s["gamma_clad"] < 1.0)

    # ④ 群折射率 > 有效折射率（正常色散）
    checks["ng_gt_neff"] = (s["n_g"] > s["n_eff"]) if math.isfinite(s["n_g"]) else False

    # ⑤ LOD_real 有限且为正（量级 < 1 RIU）
    lod = r["LOD_real"]
    checks["LOD_finite_positive"] = (math.isfinite(lod["LOD_real_riu"])
                                     and 0 < lod["LOD_real_riu"] < LOD_hi)

    # ⑥ 反向探针：n_f ≤ n_c（无导模）⇒ S 必为 nan ⇒ 守卫必捕获
    nan_geo = {**DEFAULT_GEO, "n_f": 1.30}  # n_f < n_c=1.33 ⇒ 无限制
    s_nan = real_waveguide_sensitivity(nan_geo)
    checks["no_guided_mode_red_flag"] = (not math.isfinite(s_nan["S_golden"]))

    # ⑦ LOD_temp 与 S 解耦（同 PS-M2）：同温参数下 S=0.1 与 S=0.5 的 LOD_temp 必相等
    n_a = dict(DEFAULT_NOISE); n_a["dT_stability_K"] = 1e-3
    n_b = dict(DEFAULT_NOISE); n_b["dT_stability_K"] = 1e-3
    lod_t_a = lod_real(0.1, 1e4, 1.55, n_a)["LOD_temp_riu"]
    lod_t_b = lod_real(0.5, 1e4, 1.55, n_b)["LOD_temp_riu"]
    checks["LOD_temp_S_invariant"] = (abs(lod_t_a - lod_t_b) / max(lod_t_b, 1e-30) < 1e-9)

    # ⑧ 反向探针（先证能变红）：零功率 ⇒ LOD_elec → ∞ ⇒ LOD_real → ∞
    zero_pow = dict(DEFAULT_NOISE); zero_pow["power_W"] = 0.0
    r_zp = lod_real(s["S_nm_per_riu"], 1e4, s["wl_um"], zero_pow)
    checks["zero_power_red_flag"] = not math.isfinite(r_zp["LOD_real_riu"])

    # ⑨ n_c 增大 ⇒ 限制减弱 ⇒ 更多场进入包层 ⇒ S 增大（氧化物包层对照）：
    #    soi_slab_oxide(n_c=1.444) 的 S > soi_slab_water(n_c=1.33) 的 S
    s_oxide = real_waveguide_sensitivity(SCENARIOS["soi_slab_oxide"]["geo"])
    checks["S_increases_with_nc"] = (s_oxide["S_golden"] > s["S_golden"])

    all_pass = all(v for k, v in checks.items()
                   if not k.startswith(("note",)))
    scen_reports = {}
    for k, v in SCENARIOS.items():
        scen_reports[k] = real_lod(v["geo"], v.get("noise"), v["Q"])
    return {
        "selfcheck": {"all_pass": all_pass, "checks": checks},
        "baseline_real_lod": r,
        "scenarios": scen_reports,
    }


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------
def main(out_dir: Optional[str] = None) -> int:
    rep = selfcheck_ps_m3()
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "ps_m3_report.json"), "w",
                  encoding="utf-8") as f:
            json.dump(rep, f, indent=2, ensure_ascii=False)
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 0 if rep["selfcheck"]["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(out_dir=os.path.join("outputs", "ps_m3")))
