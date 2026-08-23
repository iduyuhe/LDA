"""D-75 · 大规模系统基准（Track D 系统级 · M7 第三件）。

把 D-42/D-45（WDM 级联）、D-51（多 qubit 读出保真度）、D-52（混合巨型
系统）推进到 **N≥8 大规模**，并做**性能与精度边界压测**：

  ① WDM 大规模：N=8 信道（间隔 1.2nm 密集 DWDM grid、gap 由 FDTD 标定
     库区间选 0.4µm 弱耦合高 XT）级联设计 → 死标量验收 + 插损预算；
  ② qubit 大规模：N=8 qubit 沿公共力线频率复用读出（间隔 50MHz ≫ 3κ_r
     =22.5MHz）→ 逐 qubit 保真度 + dip 可分辨；
  ③ 联合压测：8 WDM 信道 ↔ 8 qubit 1:1 映射混合巨型系统（D-52）；
  ④ 精度/容量边界（D-75 核心新增）：
     - WDM 容量自洽：理论 n_max=floor(FSR/spacing)+1（单 FSR 工作区）
       vs 实际规模扫描最大可行 N —— 死标量一致；
     - IL 级联模型：N 环级联 thru 残差累积 vs 3dB 预算 → 预算占比 +
       3dB 内最大可级联环数（级联损耗模型在规模下的余量）；
     - qubit 间隔临界：扫描读出间隔 → 最小可分辨间隔（dip 融合/3κ_r
       失效点）→ 默认间隔余量倍率；
     - 标定网格分辨率：κ_c(gap,λ) 4×5 网格（λ 间距 25nm）在信道级
       （1.2nm）密集波长下的插值误差上界 → 网格分辨率余量；
  ⑤ 性能基准：各压测耗时（解析物理模型秒级完成，诚实记录）。

验收（LLM 不进判决路径，全部死标量）：
- WDM N=8 全过（IL≤3dB / XT≥15dB / 单 FSR / DRC / IR）
- qubit N=8 全过（错开≥3κ_r / dip 可分辨 / 逐 qubit F≥0.95）
- 联合 8×8 全过 + 映射完整
- 容量自洽：实际最大可行 N == 理论 n_max
- qubit 间隔余量 ≥1.5×（默认 vs 临界）
- 标定网格分辨率余量：信道级 κ_c 相对变化 ≤1%
- IL 预算余量：max_total_il ≤3dB 且预算占用 ≤50%

诚实边界：级联/传递为解析物理模型（D-37 add-drop + D-42 级联）；FSR 用
2D 有效折射率（容差 30% 已知）；κ_c 网格分辨率诊断用网格内插值相对变化
（FDTD 标定自身已由 D-68 验证）；性能为解析模型耗时，非商业级 FDTD。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = os.path.dirname(_HERE)
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)

from lda_agent.wdm_system import (design_wdm, channel_capacity,  # noqa: E402
                                  insertion_loss_budget, fsr_nm,
                                  inverse_ring_for_channel)
from lda_agent.multiqubit_fidelity import design_multiqubit_fidelity  # noqa: E402
from lda_agent.mixed_system import design_mixed_system  # noqa: E402

# ---------------------------------------------------------------------------
# 默认大规模配置（物理可行动，探针实测：8 信道全过 / 8 qubit 全过 / 8×8 联合全过）
# ---------------------------------------------------------------------------
_WDM_SPACING_NM = 1.2          # 密集 DWDM grid（真实模块 1.6/0.8nm 量级）
_WDM_GAP_UM = 0.4              # 标定库区间 [0.25,0.4] 取弱耦合端 → 高 XT
_WDM_M = 170                   # 环阶数 → R≈10µm → FSR≈9.1nm
_XT_TARGET_DB = 15.0
_IL_BUDGET_DB = 3.0
_KAPPA_GRID = os.path.join(_LDA_ROOT, "lda_agent", "data",
                           "kappa_grid_calibration.json")
_GRID_LAMBDA_STEP_UM = 0.025   # 标定网格 λ 间距 25nm（4×5 网格）
_KAPPA_REL_CHANNEL_TOL = 0.01  # 信道级 κ_c 相对变化 ≤1%（网格分辨率余量判据）
_QU_SPACING_GHZ = 0.05         # qubit 读出间隔（≫ 3κ_r=0.0225GHz）
_QU_BASE_GHZ = 4.8
_DELTA_GHZ = 1.0
_G_GHZ = 0.10
_KAPPA_EXT_GHZ = 0.005
_T1_US = 20.0
_NBAR = 10.0
_QU_SPACING_MARGIN_MIN = 1.5   # 默认间隔 vs 临界间隔 余量倍率下限
_IL_BUDGET_USAGE_MAX = 0.50    # IL 预算占用 ≤50%


def _wdm_channels(n_wdm: int, spacing_nm: float) -> List[float]:
    return [round(1550.0 + i * spacing_nm, 3) for i in range(n_wdm)]


def _qubit_f01s(n_qubit: int, spacing_ghz: float) -> List[float]:
    return [round(_QU_BASE_GHZ + i * spacing_ghz, 4) for i in range(n_qubit)]


def wdm_scale_scan(spacing_nm: float = _WDM_SPACING_NM,
                   gap_um: float = _WDM_GAP_UM,
                   m: int = _WDM_M,
                   n_min: int = 2, n_max: int = 12) -> Dict[str, Any]:
    """WDM 规模扫描：N 从 n_min 到 n_max，记录每 N 的验收结果与原因。

    返回 {rows: [{n, span_nm, fsr_min_nm, passed, fail_reason}],
          max_feasible_n, theory_capacity_n}。
    theory_capacity_n = floor(min FSR / spacing) + 1（单 FSR 工作区）。
    """
    rows: List[Dict[str, Any]] = []
    max_feasible = 0
    fsr_ref = None
    for n in range(n_min, n_max + 1):
        ch = _wdm_channels(n, spacing_nm)
        r = design_wdm(ch, gap=gap_um, m=m)
        span = ch[-1] - ch[0]
        if fsr_ref is None:
            fsr_ref = min(fsr_nm(c, R, 4.2) for c, R in zip(ch, r["ring_radii_um"]))
        fails = [c["name"] for c in r["acceptance"]["checks"] if not c["ok"]]
        ok = bool(r["acceptance"]["passed"])
        if ok:
            max_feasible = n
        rows.append({"n": n, "span_nm": round(span, 2),
                     "fsr_min_nm": round(fsr_ref, 2) if fsr_ref else None,
                     "passed": ok,
                     "fail_reason": ";".join(fails) if fails else ""})
    theory = int(math.floor((fsr_ref or 9.1) / spacing_nm)) + 1
    return {"rows": rows, "max_feasible_n": max_feasible,
            "theory_capacity_n": theory,
            "capacity_consistent": bool(max_feasible == theory),
            "note": f"理论容量 = floor(min FSR({fsr_ref:.2f}nm)/间隔"
                    f"{spacing_nm}nm)+1 = {theory}；实际最大可行 N = "
                    f"{max_feasible}。"}


def il_cascade_scan(spacing_nm: float = _WDM_SPACING_NM,
                    gap_um: float = _WDM_GAP_UM,
                    m: int = _WDM_M,
                    n_min: int = 2, n_max: int = 16,
                    budget_db: float = _IL_BUDGET_DB) -> Dict[str, Any]:
    """级联插损模型压测：N 环级联总插损 vs 3dB 预算。

    每 N：max_total_il = 末信道 drop IL + 前序环 thru 残差累积
    （insertion_loss_budget 复用 D-45）。返回增长行 + 预算内最大级联 N。
    """
    rows: List[Dict[str, Any]] = []
    max_under = 0
    for n in range(n_min, n_max + 1):
        ch = _wdm_channels(n, spacing_nm)
        Rs = [inverse_ring_for_channel(c * 1e-3, 4.2, m) for c in ch]
        ilb = insertion_loss_budget(ch, Rs, gap_um)
        mx = ilb["max_total_il_db"]
        ok = mx <= budget_db
        if ok:
            max_under = n
        rows.append({"n": n, "max_total_il_db": round(mx, 4),
                     "within_budget": ok,
                     "budget_usage_pct": round(100.0 * mx / budget_db, 2)})
    return {"rows": rows, "budget_db": budget_db,
            "max_cascadable_under_budget": max_under,
            "note": f"级联总插损 = drop IL + 前序环 thru 残差累积（D-45 "
                    f"模型）；预算 {budget_db}dB 内最大可级联 {max_under} 环。"}


def qubit_spacing_scan(n_qubit: int = 8, delta: float = _DELTA_GHZ,
                       g: float = _G_GHZ,
                       kappa_ext: float = _KAPPA_EXT_GHZ,
                       spacings: Optional[List[float]] = None) -> Dict[str, Any]:
    """qubit 读出间隔扫描：找 dip 融合 / 3κ_r 失效的临界间隔。

    返回 {rows: [{spacing_ghz, spacing_vs_3kappa, dip_all_resolvable,
                  spacing_ok, passed}], critical_spacing_ghz,
          default_margin_x}。
    """
    if spacings is None:
        spacings = [0.08, 0.06, 0.05, 0.04, 0.03, 0.025, 0.0225, 0.02]
    kappa_r = kappa_ext + kappa_ext / 2.0
    three_k = 3.0 * kappa_r
    rows: List[Dict[str, Any]] = []
    critical = spacings[-1]
    for sp in spacings:
        f01s = _qubit_f01s(n_qubit, sp)
        r = design_multiqubit_fidelity(f01s, delta=delta, g=g)
        acc = r["acceptance"]["passed"]
        spacing_ok = sp >= three_k
        resolv = r.get("dip_resolvability") or []
        all_res = bool(resolv) and all(x.get("resolvable") for x in resolv)
        rows.append({"spacing_ghz": sp,
                     "spacing_vs_3kappa": round(sp / three_k, 2),
                     "dip_all_resolvable": all_res,
                     "spacing_ok": bool(spacing_ok),
                     "passed": bool(acc)})
        if not acc:
            critical = sp
    # 默认配置（50MHz）vs 临界
    default = _QU_SPACING_GHZ
    margin = default / critical if critical > 0 else float("inf")
    return {"rows": rows, "critical_spacing_ghz": critical,
            "default_spacing_ghz": default,
            "default_margin_x": round(margin, 2),
            "kappa_r_ghz": round(kappa_r, 5),
            "note": f"临界读出间隔 = {critical}GHz（3κ_r={three_k}GHz 附近"
                    f" dip 融合/错开失效）；默认 {default}GHz 余量 "
                    f"{margin:.1f}×。"}


def kappa_grid_resolution_diag(
        kappa_grid_path: str = _KAPPA_GRID,
        channel_spacing_um: float = 1.2e-3) -> Dict[str, Any]:
    """标定网格分辨率诊断：κ_c(gap,λ) 网格 λ 间距 vs WDM 信道间隔。

    网格 λ 间距 25nm（4×5 标定库）；WDM 信道间隔 1.2nm（=0.0012µm）。
    计算每个 gap 列相邻网格点 κ_c 相对变化 → 每 nm 变化率 →
    单信道间隔内最大相对变化 → 判据 ≤1%（网格分辨率在信道级有余量）。
    """
    if not os.path.exists(kappa_grid_path):
        return {"ok": False, "error": f"标定文件缺失 {kappa_grid_path}"}
    with open(kappa_grid_path, encoding="utf-8") as f:
        d = json.load(f)
    gaps: List[float] = d["gaps_um"]
    wls: List[float] = d["wls_um"]
    step_um = wls[1] - wls[0] if len(wls) > 1 else _GRID_LAMBDA_STEP_UM
    pts = d["points"]
    max_rel_per_step = 0.0
    worst = None
    for gi, gap in enumerate(gaps):
        col = [p for p in pts if abs(p["gap_um"] - gap) < 1e-9]
        col = sorted(col, key=lambda p: p["wl_um"])
        for k in range(len(col) - 1):
            a, b = col[k], col[k + 1]
            if a["kappa_c_rad_um"] > 0:
                rel = abs(b["kappa_c_rad_um"] - a["kappa_c_rad_um"]) / \
                    a["kappa_c_rad_um"]
                if rel > max_rel_per_step:
                    max_rel_per_step = rel
                    worst = (gap, a["wl_um"], b["wl_um"], rel)
    # 每 nm 变化率 × 信道间隔 → 信道级最大相对变化
    per_nm = max_rel_per_step / (step_um * 1000.0)
    per_channel = per_nm * (channel_spacing_um * 1000.0)
    ok = per_channel <= _KAPPA_REL_CHANNEL_TOL
    return {
        "ok": bool(ok),
        "grid_lambda_step_nm": round(step_um * 1000.0, 2),
        "channel_spacing_nm": round(channel_spacing_um * 1000.0, 2),
        "max_rel_change_per_grid_step": round(max_rel_per_step, 6),
        "rel_change_per_nm": round(per_nm, 8),
        "rel_change_per_channel": round(per_channel, 8),
        "tolerance": _KAPPA_REL_CHANNEL_TOL,
        "worst_grid_segment": (f"gap={worst[0]}µm λ="
                               f"{worst[1]}→{worst[2]}µm rel="
                               f"{worst[3]:.4f}") if worst else None,
        "note": (f"标定网格 λ 间距 {step_um * 1000.0:.0f}nm ≫ 信道间隔 "
                 f"{channel_spacing_um * 1000.0:.1f}nm；相邻网格点 κ_c 最大"
                 f"相对变化 {max_rel_per_step:.4f} → 每信道内 ≤"
                 f"{per_channel:.4f}（判据 ≤{_KAPPA_REL_CHANNEL_TOL}）"
                 + (" → 网格分辨率在信道级余量充足" if ok
                    else " → 网格分辨率不足")),
    }


def run_large_scale_bench(n_wdm: int = 8, n_qubit: int = 8,
                          wdm_spacing_nm: float = _WDM_SPACING_NM,
                          wdm_gap_um: float = _WDM_GAP_UM,
                          wdm_m: int = _WDM_M,
                          qubit_spacing_ghz: float = _QU_SPACING_GHZ,
                          delta_ghz: float = _DELTA_GHZ,
                          g_ghz: float = _G_GHZ,
                          T1_us: float = _T1_US,
                          nbar: float = _NBAR,
                          scan: bool = True) -> Dict[str, Any]:
    """D-75 大规模系统基准主入口。

    n_wdm ≥ 8 / n_qubit ≥ 8 联合压测 + 边界扫描（scan=True 时）。
    返回 {wdm, qubit, joint, boundary, performance, acceptance, verdict}。
    """
    if n_wdm < 8 or n_qubit < 8:
        return {"ok": False,
                "error": f"大规模基准要求 N≥8：收到 WDM={n_wdm}, qubit={n_qubit}"}

    t0 = time.perf_counter()
    # ① WDM 大规模
    ch = _wdm_channels(n_wdm, wdm_spacing_nm)
    t1 = time.perf_counter()
    wdm = design_wdm(ch, gap=wdm_gap_um, m=wdm_m)
    t2 = time.perf_counter()
    Rs = wdm["ring_radii_um"]
    ilb = insertion_loss_budget(ch, Rs, wdm_gap_um)
    wdm["insertion_loss_budget"] = ilb
    wdm_s = t2 - t1

    # ② qubit 大规模
    f01s = _qubit_f01s(n_qubit, qubit_spacing_ghz)
    t3 = time.perf_counter()
    qu = design_multiqubit_fidelity(
        f01s, delta=delta_ghz, g=g_ghz, T1_us_list=[T1_us] * n_qubit,
        nbar_list=[nbar] * n_qubit)
    t4 = time.perf_counter()
    qu_s = t4 - t3

    # ③ 联合压测 8×8
    t5 = time.perf_counter()
    joint = design_mixed_system(ch, f01s, wdm_gap_um=wdm_gap_um,
                                delta_ghz=delta_ghz, g_ghz=g_ghz,
                                T1_us_list=[T1_us] * n_qubit,
                                nbar_list=[nbar] * n_qubit)
    t6 = time.perf_counter()
    joint_s = t6 - t5

    # ④ 边界压测
    t7 = time.perf_counter()
    boundary: Dict[str, Any] = {}
    if scan:
        boundary["wdm_scale"] = wdm_scale_scan(
            wdm_spacing_nm, wdm_gap_um, wdm_m)
        boundary["il_cascade"] = il_cascade_scan(
            wdm_spacing_nm, wdm_gap_um, wdm_m)
        boundary["qubit_spacing"] = qubit_spacing_scan(
            n_qubit, delta_ghz, g_ghz)
        boundary["kappa_grid_resolution"] = kappa_grid_resolution_diag()
    boundary_s = time.perf_counter() - t7
    total_s = time.perf_counter() - t0

    # ⑤ 死标量验收
    checks: List[Dict[str, Any]] = []
    # 5a WDM 大规模
    wdm_acc = wdm["acceptance"]
    checks.append({
        "name": f"WDM {n_wdm} 信道大规模设计",
        "ok": bool(wdm_acc["passed"]),
        "detail": (f"{sum(1 for c in wdm_acc['checks'] if c['ok'])}/"
                   f"{len(wdm_acc['checks'])} 项：IL≤{max(wdm['metrics']['il_drop_db']):.2f}"
                   f"dB XT≥{min(wdm['metrics']['xt_min_db']):.1f}dB 跨度"
                   f" {ch[-1] - ch[0]:.1f}nm")})
    # 5b qubit 大规模
    qu_acc = qu["acceptance"]
    f_list = [q["budget"]["F"] for q in qu["per_qubit"]]
    checks.append({
        "name": f"{n_qubit}-qubit 大规模复用读出",
        "ok": bool(qu_acc["passed"]),
        "detail": (f"{sum(1 for c in qu_acc['checks'] if c['ok'])}/"
                   f"{len(qu_acc['checks'])} 项：逐 qubit F∈"
                   f"[{min(f_list):.4f},{max(f_list):.4f}]")})
    # 5c 联合 8×8
    j_acc = joint["acceptance"]
    checks.append({
        "name": f"联合 {n_wdm}×{n_qubit} 混合巨型系统",
        "ok": bool(j_acc["passed"]),
        "detail": (f"{sum(1 for c in j_acc['checks'] if c['ok'])}/"
                   f"{len(j_acc['checks'])} 项（光子+量子+映射）")})
    # 5d 容量自洽（仅 scan 时有）
    if scan:
        ws = boundary["wdm_scale"]
        checks.append({
            "name": "WDM 容量自洽（实际最大可行 N == 理论 n_max）",
            "ok": bool(ws["capacity_consistent"]),
            "detail": (f"实际 {ws['max_feasible_n']} == 理论 "
                       f"{ws['theory_capacity_n']}（单 FSR 工作区）")})
        # 5e qubit 间隔余量
        qs = boundary["qubit_spacing"]
        checks.append({
            "name": "qubit 读出间隔余量（默认/临界 ≥1.5×）",
            "ok": bool(qs["default_margin_x"] >= _QU_SPACING_MARGIN_MIN),
            "detail": (f"默认 {qs['default_spacing_ghz']}GHz / 临界 "
                       f"{qs['critical_spacing_ghz']}GHz = "
                       f"{qs['default_margin_x']}×（3κ_r="
                       f"{qs['kappa_r_ghz'] * 3}GHz）")})
        # 5f 标定网格分辨率余量
        kg = boundary["kappa_grid_resolution"]
        checks.append({
            "name": "标定网格分辨率余量（信道级 κ_c 变化 ≤1%）",
            "ok": bool(kg.get("ok")),
            "detail": (kg.get("note", "标定文件缺失") if not kg.get("ok")
                       else f"每信道 κ_c 相对变化 "
                            f"{kg['rel_change_per_channel']}（≤"
                            f"{kg['tolerance']}）")})
        # 5g IL 预算余量
        ic = boundary["il_cascade"]
        usage = 100.0 * ic["rows"][-1]["max_total_il_db"] / ic["budget_db"]
        checks.append({
            "name": "级联 IL 预算余量（≤3dB 且占用 ≤50%）",
            "ok": bool(ic["rows"][-1]["max_total_il_db"] <= ic["budget_db"]
                       and usage <= 100.0 * _IL_BUDGET_USAGE_MAX),
            "detail": (f"N={ic['rows'][-1]['n']} 时 max_total_il="
                       f"{ic['rows'][-1]['max_total_il_db']}dB（预算 "
                       f"{ic['budget_db']}dB 的 {usage:.1f}%）；3dB 内最大"
                       f"可级联 {ic['max_cascadable_under_budget']} 环")})
    # 5h 性能（非判据，诚实报告）
    perf = {"wdm_s": round(wdm_s, 3), "qubit_s": round(qu_s, 3),
            "joint_s": round(joint_s, 3), "boundary_s": round(boundary_s, 3),
            "total_s": round(total_s, 3)}

    accepted = all(c["ok"] for c in checks)
    verdict = (
        f"大规模系统基准 PASS：WDM {n_wdm} 信道（间隔 {wdm_spacing_nm}nm）"
        f"+ {n_qubit}-qubit 复用读出（间隔 {qubit_spacing_ghz}GHz）+ "
        f"联合 {n_wdm}×{n_qubit} 混合系统全部死标量验收通过；容量自洽"
        f"（实际={boundary.get('wdm_scale', {}).get('max_feasible_n')} vs "
        f"理论={boundary.get('wdm_scale', {}).get('theory_capacity_n')}）、"
        f"IL 预算占用 {100.0 * ilb['max_total_il_db'] / _IL_BUDGET_DB:.1f}%、"
        f"qubit 间隔余量 "
        f"{boundary.get('qubit_spacing', {}).get('default_margin_x')}×、"
        f"标定网格信道级 κ_c 变化 "
        f"{boundary.get('kappa_grid_resolution', {}).get('rel_change_per_channel')}"
        f"≤1%。总压测耗时 {total_s:.1f}s（解析物理模型）。"
        if accepted else
        "大规模系统基准未全过：" +
        "; ".join(c["name"] for c in checks if not c["ok"]))

    return {
        "ok": True,
        "title": f"大规模系统基准（WDM {n_wdm} 信道 × {n_qubit} qubit 联合压测）",
        "n_wdm": n_wdm, "n_qubit": n_qubit,
        "wdm": wdm, "qubit": qu, "joint": joint,
        "boundary": boundary,
        "performance": perf,
        "acceptance": {"checks": checks, "passed": accepted},
        "verdict": verdict,
        "note": ("D-75 把 WDM 级联（D-42/45）+ 多 qubit 读出（D-51）+ 混合"
                 "巨型系统（D-52）推进到 N≥8 大规模，并压测性能与精度边界："
                 "单 FSR 容量自洽、级联 IL 模型余量、qubit 间隔临界、标定"
                 "网格分辨率余量。所有判据均为死标量（物理定律锚/计数/不等式），"
                 "LLM 不进判决路径。诚实边界：级联为解析物理模型（FSR 2D 有效"
                 "折射率容差 30% 已知）；性能为解析模型耗时，非商业级 FDTD；"
                 "网格分辨率诊断基于标定库内插值相对变化（标定自身已由 D-68 "
                 "dl40 验证）。"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="D-75 大规模系统基准")
    ap.add_argument("--n_wdm", type=int, default=8)
    ap.add_argument("--n_qubit", type=int, default=8)
    ap.add_argument("--wdm_spacing", type=float, default=_WDM_SPACING_NM)
    ap.add_argument("--wdm_gap", type=float, default=_WDM_GAP_UM)
    ap.add_argument("--qubit_spacing", type=float, default=_QU_SPACING_GHZ)
    ap.add_argument("--no-scan", action="store_true", help="跳过边界扫描")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    r = run_large_scale_bench(
        n_wdm=a.n_wdm, n_qubit=a.n_qubit,
        wdm_spacing_nm=a.wdm_spacing, wdm_gap_um=a.wdm_gap,
        qubit_spacing_ghz=a.qubit_spacing,
        scan=not a.no_scan)
    print(json.dumps({k: r[k] for k in
                      ("title", "n_wdm", "n_qubit", "performance",
                       "acceptance", "verdict")},
                     ensure_ascii=False, indent=2))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        print(f"\n[written] {a.out}")
    return 0 if (r.get("ok") and r["acceptance"]["passed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
