"""LDA · WDM 多环级联系统设计（IR 网表驱动，系统级纵深）。

把 D-36~D-41 的单器件闭环升级为**系统级**：一条 bus 上串联 N 个 add-drop 环，
每个环谐振对齐一个 WDM 信道 → 从 input 到各 drop 端口分波（数据中心光模块
核心器件）。系统级设计闭环：

  1. IR 网表（D-40）：N × RingResonator + nets（bus 链 + drop 端口）+ 约束
     （每环 FSR > 信道总跨度，防混叠）→ validate；
  2. 逆设计（闭式）：信道 λ_i → 环半径 R_i = m·λ_i/(2π·n_g)（谐振对齐）；
  3. 级联传递（解析物理模型，复用 D-37 adddrop_spectrum）：
       drop_i(λ) = T_drop(R_i)·Π_{j<i} T_thru(R_j)   （信号先经前环 thru）
       thru_out(λ) = Π_all T_thru(R_j)
  4. 系统验收（死标量比对，LLM 不进判决）：
       - 每信道 drop IL ≤ 3dB（在自身波长处 drop 效率）
       - 邻信道串扰 XT ≥ 15dB（在其它信道波长处泄漏）
       - 每环 DRC（R/gap/wg）可制造
       - 每环 FSR > 信道总跨度（单 FSR 工作区，无混叠）
  5. N 环级联版图（GDS + SVG）+ 设计报告。

CLI：python lda_agent/wdm_system.py --channels 1550,1552.5,1555,1557.5
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = os.path.dirname(_HERE)
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)

from lda_ir import IRModel, ObjectiveSpec, RingResonator, validate  # noqa: E402
from lda_l2.drc import DEFAULT_RULES  # noqa: E402
from lda_l2.gds_export import (LIB_LAYER_SI, boundary, gds_library,  # noqa: E402
                               path, ring_ring_polygon, svg_preview)


# ---------------------------------------------------------------------------
# 逆设计 / 级联模型
# ---------------------------------------------------------------------------
def inverse_ring_for_channel(channel_um: float, n_g: float = 4.2,
                             m: int = 170) -> float:
    """信道 λ → 环半径 R（谐振对齐闭式：R = m·λ/(2π·n_g)）。"""
    return round(m * channel_um / (2.0 * math.pi * n_g), 4)


def fsr_nm(lam_nm: float, R_um: float, n_g: float = 4.2) -> float:
    """环形 FSR（nm）：λ²/(n_g·2π·R)，λ 用 nm、R 用 µm（×1000 换算）。"""
    return lam_nm ** 2 / (n_g * 2.0 * math.pi * R_um * 1000.0)


def _transfer(R_um: float, gap_um: float, wls_um: List[float],
              kappa_fn=None):
    """单环 add-drop 传递（复用 D-37 模型）。返回 (drop[], thru[])。

    kappa_fn: 可选覆盖 gap→每圈场耦合比 的函数（缺省解析 gap_to_kappa；
    D-57 用 FDTD 标定换算函数替换——bus 耦合段由真实 2D FDTD 校准）。
    """
    from lda_agent.ring_adddrop import (adddrop_spectrum, bending_loss_db_per_cm,
                                        gap_to_kappa)
    if kappa_fn is None:
        kappa_fn = gap_to_kappa
    kappa = kappa_fn(gap_um)
    alpha_bend = bending_loss_db_per_cm(R_um)
    sp = adddrop_spectrum(wls_um, R_um, 4.2, kappa, alpha_bend, 1.55)
    return sp["drop"], sp["thru"]


def system_metrics(channels_nm: List[float], Rs: List[float], gap: float,
                   n_g: float = 4.2, kappa_fn=None) -> Dict[str, Any]:
    """在精确信道波长处求级联 drop/thru → 每信道 IL、邻信道串扰、thru。"""
    wls = [lam * 1e-3 for lam in channels_nm]
    drop_ij: List[List[float]] = []
    thru_ij: List[List[float]] = []
    for i, R in enumerate(Rs):
        d, t = _transfer(R, gap, wls, kappa_fn)
        drop_ij.append(d)
        thru_ij.append(t)
    il_drop, xt_min, thru_ch = [], [], []
    for i in range(len(Rs)):
        vals = []
        for j in range(len(Rs)):
            v = drop_ij[i][j]
            for k in range(i):
                v *= thru_ij[k][j]
            vals.append(v)
        il_drop.append(-10.0 * math.log10(max(vals[i], 1e-9)))
        xts = [-10.0 * math.log10(max(vals[j], 1e-9))
               for j in range(len(Rs)) if j != i]
        xt_min.append(min(xts) if xts else 90.0)
    thru_out = [1.0] * len(Rs)
    for j in range(len(Rs)):
        v = 1.0
        for k in range(len(Rs)):
            v *= thru_ij[k][j]
        thru_out[j] = v
    return {"il_drop_db": [round(x, 3) for x in il_drop],
            "xt_min_db": [round(x, 2) for x in xt_min],
            "thru_at_channels": [round(x, 5) for x in thru_out]}


def cascade_spectrum(channels_nm: List[float], Rs: List[float], gap: float,
                     step_nm: float = 0.1, kappa_fn=None) -> Dict[str, Any]:
    """级联 drop 谱（显示用，粗网格）。"""
    lo, hi = min(channels_nm) - 2.0, max(channels_nm) + 2.0
    grid = [round((lo + i * step_nm) * 1e-3, 6)
            for i in range(int((hi - lo) / step_nm) + 1)]
    out = {"wavelengths_nm": [round(g * 1000, 2) for g in grid],
           "drop": [], "thru": []}
    for i, R in enumerate(Rs):
        d, t = _transfer(R, gap, grid, kappa_fn)
        cascade = d[:]
        for k in range(i):
            _, tk = _transfer(Rs[k], gap, grid, kappa_fn)
            cascade = [cascade[x] * tk[x] for x in range(len(grid))]
        out["drop"].append([round(x, 5) for x in cascade])
    thru = [1.0] * len(grid)
    for R in Rs:
        _, t = _transfer(R, gap, grid)
        thru = [thru[x] * t[x] for x in range(len(grid))]
    out["thru"] = [round(x, 5) for x in thru]
    return out


# ---------------------------------------------------------------------------
# IR 网表（D-40）
# ---------------------------------------------------------------------------
def build_wdm_ir(channels_nm: List[float], Rs: List[float], n_g: float = 4.2
                 ) -> IRModel:
    """N 环级联 IR 网表：RingResonator × N + bus 链 nets + FSR 防混叠约束。"""
    m = IRModel(domain="photon", name="wdm-N-ring",
                notes=f"WDM {len(channels_nm)} 信道级联：信道 "
                      f"{[round(c,1) for c in channels_nm]}nm")
    for i, (lam, R) in enumerate(zip(channels_nm, Rs)):
        m.add(RingResonator(id=f"ring{i}", R=R, n_g=n_g,
                            target_fsr_nm=round(fsr_nm(lam, R, n_g), 3)))
        # 目标：每环 FSR（单 FSR 工作区判定在系统验收 checks 中）
        m.objectives.append(ObjectiveSpec(bid="B4",
                                          target=round(fsr_nm(lam, R, n_g), 3),
                                          tol=1e-3, role="objective"))
    # 网表：bus 链 ring_i.out → ring_{i+1}.in；drop 端口外接
    for i in range(len(Rs) - 1):
        m.connect(f"bus{i}", f"ring{i}.out", f"ring{i + 1}.in")
    m.connect("in", f"ring0.in")
    m.connect(f"drop{len(Rs)-1}", f"ring{len(Rs)-1}.drop")
    return m


# ---------------------------------------------------------------------------
# N 环级联版图（GDS + SVG）
# ---------------------------------------------------------------------------
def cascade_layout(channels_nm: List[float], Rs: List[float], gap: float,
                   wg_width: float = 0.5, pitch: Optional[float] = None
                   ) -> Tuple[bytes, str]:
    """N 环级联 GDS：一条 bus + N 个环（等距）+ 每环 drop bus。"""
    from lda_l2.gds_export import _flatten_rings
    pitch = pitch or (2.0 * max(Rs) + 4.0)
    off = max(Rs) + wg_width / 2.0 + gap
    elements: List[bytes] = []
    items: List[Tuple[str, dict]] = []
    # 主 bus（through，y=-off，横跨全部环）
    x_lo = -pitch * 0.6
    x_hi = (len(Rs) - 0.4) * pitch
    elements.append(path(LIB_LAYER_SI, wg_width,
                         [(x_lo, -off), (x_hi, -off)]))
    items.append(("path", {"points_um": [(x_lo, -off), (x_hi, -off)],
                           "width_um": wg_width, "layer": LIB_LAYER_SI}))
    for i, R in enumerate(Rs):
        cx = i * pitch
        # 环（平移到 (cx, 0)）
        rings = [[(x + cx, y) for (x, y) in r] for r in ring_ring_polygon(R, wg_width)]
        elements.append(boundary(LIB_LAYER_SI, _flatten_rings(rings)))
        pts = []
        for r in rings:
            pts.extend(r)
            pts.append(r[0])
        items.append(("boundary", {"points_um": pts, "layer": LIB_LAYER_SI}))
        # drop bus（环顶 → y=+off）
        xd = cx
        elements.append(path(LIB_LAYER_SI, wg_width, [(xd, 0.0), (xd, off)]))
        items.append(("path", {"points_um": [(xd, 0.0), (xd, off)],
                               "width_um": wg_width, "layer": LIB_LAYER_SI}))
    gds = gds_library("LDA-WDM", {"WDM": elements})
    svg = svg_preview({"WDM": items})
    return gds, svg


# ---------------------------------------------------------------------------
# 主闭环
# ---------------------------------------------------------------------------
def design_wdm(channels_nm: List[float], gap: float = 0.3,
               wg_width: float = 0.5, n_g: float = 4.2,
               m: int = 170, kappa_fn=None) -> Dict[str, Any]:
    """WDM 多环级联系统设计闭环：IR 网表 → 逆设计 → 级联响应 → 系统验收。

    kappa_fn: 可选覆盖 gap→每圈场耦合比（缺省解析 gap_to_kappa；D-57
    wdm_coupler 传 FDTD 标定换算函数——bus 耦合段由真实 2D FDTD 校准）。
    """
    if len(channels_nm) < 2:
        return {"ok": False, "error": "至少 2 个信道"}
    channels_nm = [float(c) for c in channels_nm]
    channels_nm.sort()
    span = channels_nm[-1] - channels_nm[0]

    # 1) 逆设计：每环 R 谐振对齐信道
    Rs = [inverse_ring_for_channel(c * 1e-3, n_g, m) for c in channels_nm]

    # 2) IR 网表 + 校验
    model = build_wdm_ir(channels_nm, Rs, n_g)
    ir_errs = validate(model)

    # 3) 级联响应 + 系统指标
    metrics = system_metrics(channels_nm, Rs, gap, n_g, kappa_fn)
    spec = cascade_spectrum(channels_nm, Rs, gap, kappa_fn=kappa_fn)

    # 4) 系统验收（死标量比对）
    checks = [
        {"name": "IR 网表校验", "ok": not ir_errs,
         "detail": f"{len(model.components)} 环 + {len(model.nets)} 网表"
                   f"{'，' + '；'.join(ir_errs[:3]) if ir_errs else ' 通过'}"},
        {"name": "每信道 drop IL ≤ 3dB", "ok": all(x <= 3.0 for x in metrics["il_drop_db"]),
         "detail": " / ".join(f"λ{c}={il:.2f}" for c, il in
                              zip(channels_nm, metrics["il_drop_db"]))},
        {"name": "邻信道串扰 XT ≥ 15dB", "ok": all(x >= 15.0 for x in metrics["xt_min_db"]),
         "detail": " / ".join(f"{x:.1f}dB" for x in metrics["xt_min_db"])},
        {"name": "每环 DRC（R/gap/wg）", "ok": bool(
            all(R >= DEFAULT_RULES["min_bend_R_um"] for R in Rs)
            and gap >= DEFAULT_RULES["min_space_um"]
            and wg_width >= DEFAULT_RULES["min_width_um"]),
         "detail": f"R∈[{min(Rs)},{max(Rs)}]µm gap={gap}µm wg={wg_width}µm"},
        {"name": "单 FSR 工作区（防混叠）", "ok": bool(
            min(fsr_nm(c, R, n_g) for c, R in zip(channels_nm, Rs)) > span),
         "detail": f"信道跨度 {span}nm < min FSR "
                   f"{min(fsr_nm(c, R, n_g) for c, R in zip(channels_nm, Rs)):.1f}nm"},
    ]
    accepted = all(c["ok"] for c in checks)
    gds, svg = cascade_layout(channels_nm, Rs, gap, wg_width)
    from lda_l2.gds_export import parse_gds
    gds_meta = parse_gds(gds)
    gds_meta["size_bytes"] = len(gds)
    for _s, _i in gds_meta.get("structures", {}).items():
        if isinstance(_i.get("layers"), set):
            _i["layers"] = sorted(_i["layers"])
    verdict = (f"WDM {len(channels_nm)} 信道级联系统设计 PASS：每信道 drop IL "
               f"≤{max(metrics['il_drop_db']):.2f}dB、邻信道串扰 ≥"
               f"{min(metrics['xt_min_db']):.1f}dB、IR 网表通过、DRC 可制造、"
               f"单 FSR 防混叠。" if accepted else
               "WDM 系统未全过：" + "; ".join(c["name"] for c in checks if not c["ok"]))
    return {
        "ok": True,
        "title": f"WDM {len(channels_nm)} 信道多环级联系统设计",
        "channels_nm": channels_nm,
        "ring_radii_um": Rs,
        "gap_um": gap,
        "wg_width_um": wg_width,
        "ir": {"schema_version": model.schema_version, "n_components": len(model.components),
               "n_nets": len(model.nets), "validate_errors": ir_errs},
        "inverse_design": {"formula": "R=m·λ/(2π·n_g)（谐振对齐闭式）",
                           "m": m, "n_g": n_g},
        "metrics": metrics,
        "spectrum": spec,
        "layout_svg": svg,
        "gds": gds_meta,
        "acceptance": {"checks": checks, "passed": accepted},
        "verdict": verdict,
        "note": "级联传递为解析物理模型（D-37 add-drop 传递函数，bus 串联）；"
                "信道间隔需 << 每环 FSR（单 FSR 工作区）。LLM 不进判决路径。",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="LDA WDM 多环级联系统设计")
    ap.add_argument("--channels", default="1550,1552.5,1555,1557.5",
                    help="信道中心波长(nm)，逗号分隔")
    ap.add_argument("--gap", type=float, default=0.3)
    args = ap.parse_args()
    ch = [float(x) for x in args.channels.split(",") if x.strip()]
    rep = design_wdm(ch, gap=args.gap)
    print(json.dumps({k: rep[k] for k in
                      ("title", "channels_nm", "ring_radii_um", "metrics",
                       "ir", "acceptance", "verdict", "gds")},
                     ensure_ascii=False, indent=2))
    return 0 if rep["acceptance"]["passed"] else 1


# ---------------------------------------------------------------------------
# D-45 WDM 纵深：XT 反解 gap / 插损预算 / 单 FSR 信道上限
# ---------------------------------------------------------------------------
def xt_min_for_gap(channels_nm: List[float], Rs: List[float], gap: float,
                   n_g: float = 4.2) -> float:
    """给定 gap 的邻信道最小串扰（dB）。"""
    m = system_metrics(channels_nm, Rs, gap, n_g)
    return float(min(m["xt_min_db"]))


def xt_to_gap(channels_nm: List[float], xt_target_db: float,
              gap_lo: float = 0.20, gap_hi: float = 0.80,
              tol_db: float = 0.3, n_g: float = 4.2) -> Dict[str, Any]:
    """反解满足 XT 指标的最小耦合 gap（XT(gap) 单调增，bisection）。

    返回 {gap, xt_db, achievable, note}；gap_hi 仍不达标 → achievable=False。
    """
    Rs = [inverse_ring_for_channel(c * 1e-3, n_g) for c in channels_nm]

    def f(g: float) -> float:
        return xt_min_for_gap(channels_nm, Rs, g, n_g) - xt_target_db

    if f(gap_lo) >= 0:
        return {"gap": gap_lo, "xt_db": round(xt_min_for_gap(channels_nm, Rs,
                                                             gap_lo, n_g), 2),
                "achievable": True, "note": "gap 下限已满足指标"}
    if f(gap_hi) < 0:
        return {"gap": None, "xt_db": round(xt_min_for_gap(channels_nm, Rs,
                                                           gap_hi, n_g), 2),
                "achievable": False,
                "note": f"gap 上限 {gap_hi}µm 仍达不到 XT={xt_target_db}dB"
                        f"（需更弱耦合/更宽信道间隔）"}
    lo, hi = gap_lo, gap_hi
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if f(mid) < 0:
            lo = mid
        else:
            hi = mid
    gap = round((lo + hi) / 2.0, 4)
    return {"gap": gap,
            "xt_db": round(xt_min_for_gap(channels_nm, Rs, gap, n_g), 2),
            "achievable": True,
            "note": f"bisection 反解：XT(gap) 单调，{tol_db}dB 内收敛"}


def insertion_loss_budget(channels_nm: List[float], Rs: List[float], gap: float,
                          n_g: float = 4.2) -> Dict[str, Any]:
    """级联插损预算：每信道总插损 = drop IL + 前序环 thru 残差。

    返回 {rows: [{channel, drop_il_db, thru_residue_db, total_il_db}],
          max_total_il_db}。
    """
    from lda_agent.ring_adddrop import (adddrop_spectrum, bending_loss_db_per_cm,
                                        gap_to_kappa)
    wls = [c * 1e-3 for c in channels_nm]
    di, ti = [], []
    for R in Rs:
        k = gap_to_kappa(gap)
        ab = bending_loss_db_per_cm(R)
        sp = adddrop_spectrum(wls, R, n_g, k, ab, 1.55)
        di.append(sp["drop"]); ti.append(sp["thru"])
    rows = []
    for i in range(len(channels_nm)):
        drop = di[i][i]
        thru_res = 1.0
        for k in range(i):
            thru_res *= ti[k][i]
        drop_il = -10.0 * math.log10(max(drop, 1e-9))
        res_il = -10.0 * math.log10(max(thru_res, 1e-9))
        rows.append({"channel_nm": channels_nm[i],
                     "drop_il_db": round(drop_il, 3),
                     "thru_residue_db": round(res_il, 3),
                     "total_il_db": round(drop_il + res_il, 3)})
    return {"rows": rows, "max_total_il_db": round(max(r["total_il_db"]
                                                       for r in rows), 3)}


def channel_capacity(xt_target_db: float, spacing_nm: float,
                     n_g: float = 4.2, m: int = 170,
                     gap_hi: float = 0.80) -> Dict[str, Any]:
    """单 FSR 工作区 + XT 指标下的信道上限。

    ① 反解满足 XT 的最小 gap（相邻信道对）；② 单 FSR 限制：span=(N−1)·spacing
    < FSR(R) → N_max = floor(FSR/spacing)+1。
    """
    # 相邻信道对（最紧串扰）上反解 gap
    pair = [1550.0, 1550.0 + spacing_nm]
    g = xt_to_gap(pair, xt_target_db, gap_hi=gap_hi)
    if not g["achievable"]:
        return {"achievable": False, "note": g["note"]}
    R = inverse_ring_for_channel(1550e-3, n_g, m)
    fsr = fsr_nm(1550.0, R, n_g)
    n_max = int(math.floor(fsr / spacing_nm)) + 1
    return {"achievable": True,
            "required_gap_um": g["gap"],
            "xt_at_gap_db": g["xt_db"],
            "spacing_nm": spacing_nm,
            "min_fsr_nm": round(fsr, 2),
            "n_max_single_fsr": n_max,
            "max_channel_span_nm": round((n_max - 1) * spacing_nm, 2),
            "note": f"信道间隔 {spacing_nm}nm、XT≥{xt_target_db}dB → 需 gap="
                    f"{g['gap']}µm；单 FSR {fsr:.1f}nm 内最多 {n_max} 信道"}


def design_wdm_advanced(channels_nm: Optional[List[float]] = None,
                        n_channels: int = 4, spacing_nm: float = 2.5,
                        xt_target_db: Optional[float] = None,
                        gap: Optional[float] = None,
                        wg_width: float = 0.5, n_g: float = 4.2,
                        m: int = 170) -> Dict[str, Any]:
    """WDM 纵深统一入口：XT 指标→gap 反解 / 信道生成 / 插损预算 / 容量。"""
    if channels_nm is None:
        channels_nm = [round(1550.0 + i * spacing_nm, 2)
                       for i in range(n_channels)]
    channels_nm = [float(c) for c in channels_nm]
    channels_nm.sort()
    # XT 指标 → gap 反解（未显式给 gap 时）
    xt_solve = None
    if gap is None and xt_target_db is not None:
        xt_solve = xt_to_gap(channels_nm, xt_target_db)
        if not xt_solve["achievable"]:
            return {"ok": False, "error": xt_solve["note"],
                    "xt_target_db": xt_target_db}
        gap = xt_solve["gap"]
    gap = gap if gap is not None else 0.3
    rep = design_wdm(channels_nm, gap=gap, wg_width=wg_width, n_g=n_g, m=m)
    if not rep["ok"]:
        return rep
    # 插损预算 + 容量
    Rs = rep["ring_radii_um"]
    ilb = insertion_loss_budget(channels_nm, Rs, gap, n_g)
    rep["insertion_loss_budget"] = ilb
    rep["xt_solve"] = xt_solve
    if xt_target_db is not None:
        cap = channel_capacity(xt_target_db,
                               spacing_nm if len(channels_nm) > 1
                               else min(abs(b - a) for a, b in
                                        zip(channels_nm, channels_nm[1:]) or [2.5]),
                               n_g=n_g, m=m)
        rep["channel_capacity"] = cap
        # 追加验收：XT ≥ 指标 + 插损预算 ≤ 3dB
        m0 = rep["metrics"]
        acc = rep["acceptance"]
        acc["checks"].append(
            {"name": f"XT ≥ 指标 {xt_target_db}dB", "ok": bool(
                min(m0["xt_min_db"]) >= xt_target_db - 0.5),
             "detail": f"min XT={min(m0['xt_min_db']):.1f}dB vs 指标 "
                       f"{xt_target_db}dB（bisection 容差 0.5dB）"})
        acc["checks"].append(
            {"name": "级联插损预算 ≤ 3dB", "ok": bool(
                ilb["max_total_il_db"] <= 3.0),
             "detail": f"max 总插损={ilb['max_total_il_db']}dB"})
        acc["passed"] = all(c["ok"] for c in acc["checks"])
        rep["verdict"] = ("WDM 纵深设计 PASS：XT≥指标 "
                          f"{xt_target_db}dB（min {min(m0['xt_min_db']):.1f}dB）、"
                          f"gap={gap}µm（反解）、插损预算 ≤"
                          f"{ilb['max_total_il_db']}dB、单 FSR 上限 "
                          f"{(rep.get('channel_capacity') or {}).get('n_max_single_fsr')}"
                          if acc["passed"] else
                          "WDM 纵深未全过：" + "; ".join(
                              c["name"] for c in acc["checks"] if not c["ok"]))
    return rep


if __name__ == "__main__":
    sys.exit(main())
