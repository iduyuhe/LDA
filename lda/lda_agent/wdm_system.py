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


def _transfer(R_um: float, gap_um: float, wls_um: List[float]):
    """单环 add-drop 传递（复用 D-37 模型）。返回 (drop[], thru[])。"""
    from lda_agent.ring_adddrop import (adddrop_spectrum, bending_loss_db_per_cm,
                                        gap_to_kappa)
    kappa = gap_to_kappa(gap_um)
    alpha_bend = bending_loss_db_per_cm(R_um)
    sp = adddrop_spectrum(wls_um, R_um, 4.2, kappa, alpha_bend, 1.55)
    return sp["drop"], sp["thru"]


def system_metrics(channels_nm: List[float], Rs: List[float], gap: float,
                   n_g: float = 4.2) -> Dict[str, Any]:
    """在精确信道波长处求级联 drop/thru → 每信道 IL、邻信道串扰、thru。"""
    wls = [lam * 1e-3 for lam in channels_nm]
    drop_ij: List[List[float]] = []
    thru_ij: List[List[float]] = []
    for i, R in enumerate(Rs):
        d, t = _transfer(R, gap, wls)
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
                     step_nm: float = 0.1) -> Dict[str, Any]:
    """级联 drop 谱（显示用，粗网格）。"""
    lo, hi = min(channels_nm) - 2.0, max(channels_nm) + 2.0
    grid = [round((lo + i * step_nm) * 1e-3, 6)
            for i in range(int((hi - lo) / step_nm) + 1)]
    out = {"wavelengths_nm": [round(g * 1000, 2) for g in grid],
           "drop": [], "thru": []}
    for i, R in enumerate(Rs):
        d, t = _transfer(R, gap, grid)
        cascade = d[:]
        for k in range(i):
            _, tk = _transfer(Rs[k], gap, grid)
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
               m: int = 170) -> Dict[str, Any]:
    """WDM 多环级联系统设计闭环：IR 网表 → 逆设计 → 级联响应 → 系统验收。"""
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
    metrics = system_metrics(channels_nm, Rs, gap, n_g)
    spec = cascade_spectrum(channels_nm, Rs, gap)

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


if __name__ == "__main__":
    sys.exit(main())
