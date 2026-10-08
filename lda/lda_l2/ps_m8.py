"""PS-M8 · 几何灵敏度半 + Q 增强 LOD 缩放（吃狗粮 v8 · 光子传感器新征程 G2 几何半 + G4 传感窗口收口）。

═══ 策略（把「单点灵敏几何 + 谐振 Q 增强」两条被忽视的物理杠杆推到可执行、可判决）═══
PS-M0~M7 解决了灵敏度物理链（M3）、功能化（M4）、流体（M5）、规模集成（M6）、WebUI 自助
（M7）。但有两个**未建成**的物理杠杆：

  · G2 几何半（B460 已建 strip 物理对齐，但 slot / suspended / thin-wire 高灵敏几何 **未建 PDK 器件、
    未入账本**）—— 不同波导几何对 analyte 的折射率灵敏度差异是**设计级**杠杆；
  · G4 传感窗口层 / DRC 例外（待 Task #50 收口）—— 让传感器独有的「开窗 + 暴露波导」几何能过 DRC。

PS-M8 抽取三道**严格独立**锚（延续 PS-M2~M7 的「解析闭式 golden × 方法学独立数值候选」双轨纪律），
外加一道**自证桩**闭式（B472 · 如实标注，不越级谎报）：

  · B469 薄线（thin-wire）波导折射率灵敏度 `S=dn_eff/dn_a`；
  · B470 狭缝（slot）波导折射率灵敏度；
  · B471 悬浮（suspended）波导折射率灵敏度（去衬底 2.4× 增强杠杆）；
  · B472 Q 增强 LOD 缩放闭式 `LOD_real(Q)=√((LOD_elec_ref·Q0/Q)²+LOD_temp_ref²)`
    —— 🔴 **自证桩**：原设 candidate 与 golden **代数恒等**（实测 |Δ|=0.0），经反自证桩护栏
    实测判为自证桩 ⇒ **如实撤下候选登记、降为 Tier-1**（保留物理律 golden + 升级路径）。

═══ 🔴 纪律 ═══
· 进报告数字一律**模块现算**（不转录草稿）；tol 与 anchor 判据**读自 `BENCHMARK_DEFS`**（不硬编码）；
· 每道守卫配反向探针（先证能变红）；复用 B-38 内核（`_batch_b38_numeric`）为四锚数学单一真源；
· B469~B471 golden=**一阶本征值微扰（Rayleigh 商 + 左本征矢）**（非对称算子，右本征矢系统性错 0.815 vs 0.495）；
  candidate=FV-FD 有限差分（perturb n_a ±δ → 重解 n_eff → 中心差商），方法学独立；
· B472 golden=Q-scaling 闭式（**自证桩**；原候选 PS-M2 `lod_real` 逐分量合成与 golden 代数恒等
  ⇒ 经护栏实测判自证桩 ⇒ 如实降级、撤下 candidate 登记；仍在 ps_m8 内作 Q 缩放物理规律交付）；
· 🔴 **诚实梯度（实测）**：SOI 220nm 下 substrate 受限的薄条/狭缝灵敏度 ≈ strip 基线或略低，
  唯一戏剧杠杆是**去衬底** suspended→2.4×；判据梯度断言 = 「suspended ≫ strip ≈ thinwire ≈ slot」，**不要求 slot>thinwire>strip**；
· 🔴 **B472 测试区间纪律**：默认噪声（无 referencing）下 LOD 被热漂主导、与 Q 无关（缩放退化），故锚默认走
  **电学受限区间**（CMR=1e4 压低热漂），使 Q 缩放可见且单调；物理要点 = Q 增强 LOD **仅当**热漂被 referencing 抑制。

═══ 诚实边界 ═══
· 几何/材料为**设计示例**（SOI 220nm @1550nm；water n_a=1.33 / SiO2 substrate 1.444 / Si core 3.4777）。
  slot 狭缝水介质、suspended 去衬底均为真实可制造传感几何。结论只可用于数值方法与量级，
  **不得作制造/性能宣称**。
· 零商业依赖（numpy + scipy 标准数值库；scipy 仅在求解器/候选体内惰性 import）。
"""
from __future__ import annotations

import functools
import json
import math
import os
from typing import Any, Dict, Optional

from lda_harness._batch_b38_numeric import (  # noqa: E402
    cand_b469,
    cand_b470,
    cand_b471,
    golden_b472,
    geometry_sensitivity_golden,
    q_scaling_lod_cand,
)


# ---------------------------------------------------------------------------
# 🔴 进程内记忆化（必配 · 否则 smoke 实测 243s / 超时余量仅 1.23×）
# ---------------------------------------------------------------------------
# PS-M8 的 FV 全矢量本征求解单次 ~6-11s，而 `selfcheck_ps_m8` 多处**复用同一** golden/cand
# （锚对齐 ×3 + 几何梯度 ×2（selfcheck + integration_summary）+ 反向探针 ×3 + 报告 ×3）
# ⇒ 不缓存会重复求解 4~6 遍（实测 243s）。按「一次现算去重」纪律（同 ps_m0 的 `rep=` 复用）
# 加 `lru_cache`：结果逐位不变（纯函数、零参/按 kind），仅消除重复计算（实测 → ~57s）。
@functools.lru_cache(maxsize=None)
def _geo_golden(kind: str) -> float:
    """四种几何的折射率灵敏度 golden（左本征矢 RQ 微扰闭式），按 kind 记忆化。"""
    return float(geometry_sensitivity_golden(kind))


def _memo0(fn):
    """零参函数记忆化（cand_* 均为零参 lambda）。"""
    return functools.lru_cache(maxsize=None)(fn)


#: 三锚（B469/B470/B471）：golden / candidate 均**零参**（内核 `_DEFAULTS` 已固化默认几何），
#: 两侧均记忆化。golden 经 `_geo_golden(kind)` 统一入口 ⇒ 与几何梯度支柱**共享**缓存（thinwire
#: / slot / suspended 不重复求解）。
#: 🔴 B472 为**自证桩**（无独立候选，见 part6.py note），不列入此表。
_GEO_KIND = {"B469": "thinwire", "B470": "slot", "B471": "suspended"}
_GOLDEN = {bid: (lambda k=k: _geo_golden(k)) for bid, k in _GEO_KIND.items()}
_CAND = {"B469": _memo0(cand_b469), "B470": _memo0(cand_b470),
         "B471": _memo0(cand_b471)}


# ---------------------------------------------------------------------------
# 判据工具：tol 读自 BENCHMARK_DEFS（不硬编码）
# ---------------------------------------------------------------------------
def _tol_from_defs(bid: str) -> float:
    """从 `BENCHMARK_DEFS` 现读该锚 tol（防与账本漂移）。"""
    from lda_harness.benchmarks import BENCHMARK_DEFS
    return float(BENCHMARK_DEFS[bid]["tol"])


def anchor_verdict(bid: str) -> Dict[str, float]:
    """现算某锚的 golden / candidate / |Δ| / tol / 是否 PASS（走与 harness 同口径的零参调用）。"""
    from lda_harness.benchmarks import BENCHMARK_DEFS
    tol = float(BENCHMARK_DEFS[bid]["tol"])
    g = float(_GOLDEN[bid]())
    c = float(_CAND[bid]())
    return {"golden": g, "candidate": c, "abs_res": abs(g - c), "tol": tol,
            "passed": abs(g - c) < tol}


def _verdict_with_perturbed_candidate(bid: str, cand_value: float) -> bool:
    """反向探针（与 `run_benchmark_falsifiability_smoke` 同语义）：**冻结** golden（零参现算），
    只把**候选侧**数值替换为 `cand_value`，判定是否仍 PASS（期望 False=被抓）。

    🔴 血案：若把 golden 也用扰动值重算，则 golden 与候选**同步漂移**⇒ |Δ| 不变 ⇒ 探针
    恒绿（假绿）。必须冻结 golden，只扰候选侧。本锚无标量输入参数（默认几何固化于内核），
    故直接对候选**数值**做 ×factor 扰动以证伪。
    """
    from lda_harness.benchmarks import BENCHMARK_DEFS
    tol = float(BENCHMARK_DEFS[bid]["tol"])
    g = float(_GOLDEN[bid]())
    c = float(cand_value)
    return math.isfinite(g) and math.isfinite(c) and abs(g - c) < tol


# ---------------------------------------------------------------------------
# 支柱 ① 几何灵敏度半（四种几何 S=dn_eff/dn_a + 诚实梯度）
# ---------------------------------------------------------------------------
def geometry_sensitivity_profile(p: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """四种几何的折射率灵敏度（golden=左本征矢 RQ 微扰闭式现算）+ 诚实梯度判定。

    诚实梯度（实测）：suspended ≫ strip ≈ thinwire ≈ slot；不要求 slot>thinwire>strip。
    """
    kinds = ["strip", "thinwire", "slot", "suspended"]
    S = {k: _geo_golden(k) for k in kinds}
    honest_grad = (
        S["suspended"] > S["strip"] * 1.5
        and abs(S["thinwire"] - S["strip"]) < 0.15
        and abs(S["slot"] - S["strip"]) < 0.15
    )
    return {
        "S_by_geometry": S,
        "honest_gradient": honest_grad,
        "suspended_gain_vs_strip": (S["suspended"] / S["strip"]
                                    if S["strip"] > 0.0 else float("nan")),
        "thinwire_vs_strip": S["thinwire"] - S["strip"],
        "slot_vs_strip": S["slot"] - S["strip"],
    }


# ---------------------------------------------------------------------------
# 支柱 ② Q 增强 LOD 缩放（电学受限区间）
# ---------------------------------------------------------------------------
def q_scaling_profile(S_nm_per_riu: float = 300.0,
                      Q0: float = 1e4) -> Dict[str, Any]:
    """Q 增强 LOD 缩放剖面：扫 Q、演示单调性（Q↑⇒LOD↓）+ 热漂解耦（LOD_temp 与 Q 无关）。

    默认走电学受限区间 B472_NOISE（CMR=1e4，≈80 dB referencing 压低热漂），使 Q 缩放可见且单调。
    """
    from lda_harness._batch_b38_numeric import B472_NOISE
    Qs = [1e4, 5e4, 1e5, 2e5]
    lod_seq = [float(q_scaling_lod_cand(Q, Q0, S_nm_per_riu, noise=B472_NOISE)) for Q in Qs]
    from lda_l2.ps_m2 import lod_real  # 惰性（纯 numpy）
    lt_seq = [float(lod_real(S_nm_per_riu, Q, 1.55, B472_NOISE)["LOD_temp_riu"]) for Q in Qs]
    mono = all(lod_seq[i + 1] < lod_seq[i] for i in range(len(lod_seq) - 1))
    thermal_decoupled = all(abs(lt_seq[i + 1] - lt_seq[i]) < 1e-15
                            for i in range(len(lt_seq) - 1))
    return {
        "Q_grid": Qs,
        "LOD_real_riu_by_Q": dict(zip((str(int(q)) for q in Qs), lod_seq)),
        "LOD_temp_riu_by_Q": dict(zip((str(int(q)) for q in Qs), lt_seq)),
        "q_enhancement_monotonic": mono,
        "thermal_decoupled_from_Q": thermal_decoupled,
        "lod_at_default_Q": float(q_scaling_lod_cand(1e5, Q0, S_nm_per_riu, noise=B472_NOISE)),
    }


# ---------------------------------------------------------------------------
# 集成汇总（几何半 + Q 缩放 → 设计指引）
# ---------------------------------------------------------------------------
def integration_summary(S_nm_per_riu: float = 300.0,
                        Q0: float = 1e4) -> Dict[str, Any]:
    """把几何灵敏度半与 Q 缩放合成为设计指引：选 suspended 几何（最大灵敏度杠杆）+
    选高 Q 并配 referencing（Q 增强 LOD 仅当热漂被抑制） + 诚实边界标注。"""
    geo = geometry_sensitivity_profile()
    qsc = q_scaling_profile(S_nm_per_riu, Q0)
    # 设计指引：最大灵敏度几何 = suspended；最高 LOD 缩放区间 = 电学受限 + 高 Q
    best_geo = max(geo["S_by_geometry"], key=geo["S_by_geometry"].get)
    return {
        "best_sensitivity_geometry": best_geo,
        "best_sensitivity_S": geo["S_by_geometry"][best_geo],
        "suspended_gain_vs_strip": geo["suspended_gain_vs_strip"],
        "q_enhancement_monotonic": qsc["q_enhancement_monotonic"],
        "thermal_decoupled_from_Q": qsc["thermal_decoupled_from_Q"],
        "geometry": geo,
        "q_scaling": {k: v for k, v in qsc.items()
                      if k not in ("geometry",)},
        "honest_caveat": ("Q 增强 LOD 仅当热漂被 referencing 抑制才成立；substrate 受限几何灵敏度"
                          " ≈ strip 基线，唯一大幅增强杠杆是去衬底 suspended。"),
    }


# ---------------------------------------------------------------------------
# 自校 / 反向探针（先证能变红）
# ---------------------------------------------------------------------------
def selfcheck_ps_m8() -> Dict[str, Any]:
    """PS-M8 守卫：四锚对齐（tol 读自 BENCHMARK_DEFS）+ 几何诚实梯度 + Q 缩放单调/热漂解耦
    + 反向探针（候选 ×1.1 必红）+ 非法参数红标。"""
    checks: Dict[str, Any] = {}

    # ---- ① 三锚对齐（B469/B470/B471 · 走 harness 同口径；B472 为自证桩，见 ①b）----
    for bid in ("B469", "B470", "B471"):
        v = anchor_verdict(bid)
        checks["%s_anchor_within_tol" % bid.lower()] = bool(v["passed"])
        checks["%s_tol_read_from_defs" % bid.lower()] = (
            abs(v["tol"] - _tol_from_defs(bid)) < 1e-18)

    # ---- ①b B472 自证桩契约（诚实降级 · 防静默回退为「严格独立」）----
    # 🔴 B472 原候选与 golden **代数恒等**（slope=depth·(3√3/4)/FWHM、FWHM=λ/Q ⇒ slope∝Q
    #    ⇒ LOD_elec∝1/Q ⇒ 缩放闭式精确重现 lod_real，实测 |Δ|=0.0），经反自证桩护栏
    #    `run_benchmark_falsifiability_smoke` 实测判为**自证桩**（B28 同型「同式异写」）。
    #    故其 DEFS 内**不得**再出现 `candidate` 键（否则会被 `_vmm_classify` 越级判严格独立）。
    #    本判据 + `b472_tol_read_from_defs` 共同守「B472 仍是带 tol 的物理律 golden ∧ 无候选登记」。
    from lda_harness.benchmarks import BENCHMARK_DEFS as _DEFS
    checks["b472_selfcertified_no_candidate"] = ("candidate" not in _DEFS["B472"])
    checks["b472_tol_read_from_defs"] = (
        abs(float(_DEFS["B472"]["tol"]) - _tol_from_defs("B472")) < 1e-18)

    # ---- ② 几何灵敏度半：诚实梯度 ----
    geo = geometry_sensitivity_profile()
    checks["geo_sensitivities_all_finite"] = all(
        math.isfinite(s) for s in geo["S_by_geometry"].values())
    checks["geo_honest_gradient"] = bool(geo["honest_gradient"])
    checks["geo_suspended_gain_ge_2x"] = (geo["suspended_gain_vs_strip"] > 2.0)

    # ---- ③ Q 缩放：单调 + 热漂解耦 ----
    qsc = q_scaling_profile()
    checks["q_scaling_monotonic"] = bool(qsc["q_enhancement_monotonic"])
    checks["q_scaling_thermal_decoupled"] = bool(qsc["thermal_decoupled_from_Q"])

    # ---- ④ 反向探针（先证能变红）：候选 ×1.1 必 FAIL（冻结 golden，只扰候选侧）----
    checks["reverse_b469_perturb_cand_flips_red"] = (
        not _verdict_with_perturbed_candidate("B469", _CAND["B469"]() * 1.1))
    checks["reverse_b470_perturb_cand_flips_red"] = (
        not _verdict_with_perturbed_candidate("B470", _CAND["B470"]() * 1.1))
    checks["reverse_b471_perturb_cand_flips_red"] = (
        not _verdict_with_perturbed_candidate("B471", _CAND["B471"]() * 1.1))
    # B472（自证桩）：Q 缩放律反向探针 —— 候选换成 Q=2e5（默认 Q=1e5）⇒ 远超 tol(1e-9) ⇒ 必红
    # （冻结 golden（默认 Q 处闭式），只改 Q；证 Q 依赖是真算出来的，非恒真文案。）
    _g472 = float(golden_b472())
    _c472 = float(q_scaling_lod_cand(2e5, 1e4, 300.0))
    checks["reverse_b472_wrong_Q_flips_red"] = (
        math.isfinite(_g472) and math.isfinite(_c472)
        and not (abs(_g472 - _c472) < _tol_from_defs("B472")))

    # ---- ⑤ 非法参数红标：substrate=True 且无导模 / 退化几何 ⇒ nan ----
    bad = geometry_sensitivity_golden("thinwire", {"w_um": 0.05, "h_um": 0.22,
                                                  "gap_um": 0.0, "w_rail_um": 0.0,
                                                  "substrate": True, "Lhalf_um": 1.5})
    checks["red_flag_cutoff_geometry_nan"] = (not math.isfinite(bad))

    all_pass = all(bool(v) for v in checks.values())
    return {
        "selfcheck": {"all_pass": all_pass, "checks": checks,
                      "n_checks": len(checks)},
        "geometry": geo,
        "q_scaling": qsc,
        "integration": integration_summary(),
        "anchors": {bid: anchor_verdict(bid) for bid in ("B469", "B470", "B471")},
        "b472_selfcertified": {
            "golden": float(golden_b472()),
            "registered_candidate": False,
            "status": ("self_certified（VMM Tier-1）—— 原候选与 golden 代数恒等"
                       "（实测 |Δ|=0.0）⇒ 如实降级，不越级谎报为严格独立"),
        },
    }


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------
def main(out_dir: Optional[str] = None) -> int:
    rep = selfcheck_ps_m8()
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "ps_m8_report.json"), "w",
                  encoding="utf-8", newline="\n") as f:
            json.dump(rep, f, indent=2, ensure_ascii=False)
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 0 if rep["selfcheck"]["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(out_dir=os.path.join("outputs", "ps_m8")))
