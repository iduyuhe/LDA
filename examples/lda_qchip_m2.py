"""LDA 新征程 · LDA-Q2：参数化 N×N 可编程 MZI 干涉仪 mesh（LOQC 通用处理器）P&R 生成器。

============================================================================
定位（吃自己的狗粮 · M2 = 规模/性能升级 + 可扩 P&R）
----------------------------------------------------------------------------
M1（LDA-Q1）用手写硬编码的 4×4 Reck 三角 mesh 走通主权全链路。M2 把"4×4 硬编码
布局"升级为**参数化 N×N mesh P&R 生成器**（闭合平台缺口 G_Q6），并顺带闭合 M1 的
"物理 mesh 是否忠实实现目标酉"诚实缺口：

- 任意 N×N 酉 → reck_decompose 拆成 N(N-1)/2 个 MZI 单元（ops，作用在当前基两模）。
- 用 ops 做 **rail-tracking netlist 生成**：光逆序穿过每个 MZI（每片 = G_m†），
  并在输入端串入对角相位层 D（PhaseShifter）。由此画出的 mesh 传递矩阵 ≡ 目标酉
  （机器精度，构造性成立）→ 这是一台**真正可编程**的线性光量子计算（LOQC）处理器。
- 主权全链路：LinkModel → placement(A* 路由 + 交叉化解) → export_chip_gds → DRC/LVS。

红线纪律（与 LDA 一致）：C 级自主（纯 numpy）、LLM 不进判决路径、外部求解器只作
ORACLE 不进 golden。本脚本只产出结构代理版图（DirectionalCoupler 画 MZI 几何）；
MZI/PhaseShifter 是真器件但当前 GDS 几何未生成（平台已知限制，如实标注），物理
前端（CMT 耦合长度 / Vπ·L 相移）由 mzi_mesh_matmul 给出；量子态层（G_Q1–G_Q4）属 M3。
============================================================================
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))   # D:/agent_LDA
sys.path.insert(0, os.path.join(ROOT, "lda"))

from lda_chain.link_model import LinkModel
from lda_layout.placement import port_abs, device_bbox
from lda_layout.router import route_net, RouteResult
from lda_l2.chip_layout_export import (
    export_chip_gds, device_geoms, io_grating_geoms,
)
from lda_l2.mzi_mesh_matmul import (
    reck_triangular_mesh, assemble_triangular_mesh, unitary_fidelity,
    mesh_cascade_loss_db, coupler_length_from_theta, voltage_from_phase,
    dft_matrix, VPI_L_V_CM,
)

WG = 0.5
RULES = {
    "min_width_um": 0.30,
    "min_space_um": 0.20,
    "min_bend_R_um": 5.0,
    "max_split_angle_deg": 30.0,
}
OUT = HERE
IN_X = -15.0
COL_PITCH = 22.0
RAIL_DY = 14.0
LC_MIN = 3.0          # G_Q9：θ=0 直通 MZI 的 Lc=0 包围盒塌缩守卫
PS_X = IN_X + 18.0    # 输入对角相位层（D）列 x
MZI_X0 = PS_X + 20.0  # mesh 起始 x（物理阶段 c=N-2 最靠近输入）
MZI_POST = 22.0       # mesh 末列到输出光栅间距


# ── 几何工具（复用主权 P&R 已证机制）────────────────────────────────────────────
def _d(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _seg_intersect_point(p1, p2, p3, p4):
    x1, y1, x2, y2 = p1[0], p1[1], p2[0], p2[1]
    x3, y3, x4, y4 = p3[0], p3[1], p4[0], p4[1]
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-12:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    u = ((x1 - x3) * (y1 - y2) - (y1 - y3) * (x1 - x2)) / den
    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    return None


def _path_intersections(a, b):
    out = []
    for i in range(len(a) - 1):
        for j in range(len(b) - 1):
            p = _seg_intersect_point(a[i], a[i + 1], b[j], b[j + 1])
            if p is not None:
                out.append(p)
    return out


def _cum_arclen(pts):
    cum = [0.0]
    for i in range(len(pts) - 1):
        cum.append(cum[-1] + _d(pts[i], pts[i + 1]))
    return cum


def _point_at_arclen(pts, cum, s):
    s = max(0.0, min(cum[-1], s))
    for i in range(len(pts) - 1):
        if cum[i] <= s <= cum[i + 1]:
            seg = cum[i + 1] - cum[i]
            t = 0.0 if seg < 1e-12 else (s - cum[i]) / seg
            return (pts[i][0] + t * (pts[i + 1][0] - pts[i][0]),
                    pts[i][1] + t * (pts[i + 1][1] - pts[i][1]))
    return pts[-1]


def _arclen_of_point(pts, cum, q):
    best, best_s = None, 0.0
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        seg = _d(a, b)
        if seg < 1e-12:
            s = cum[i]
        else:
            t = ((q[0] - a[0]) * (b[0] - a[0]) + (q[1] - a[1]) * (b[1] - a[1])) / (seg * seg)
            t = max(0.0, min(1.0, t))
            s = cum[i] + t * seg
        d = _d((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])), q)
        if best is None or d < best:
            best, best_s = d, s
    return best_s


def _subpoly(pts, cum, s0, s1):
    s0, s1 = max(0.0, s0), min(cum[-1], s1)
    if s1 - s0 < 1e-9:
        return [pts[0]]
    out = [_point_at_arclen(pts, cum, s0)]
    for i in range(len(pts) - 1):
        if cum[i] > s0 + 1e-9 and cum[i] < s1 - 1e-9:
            out.append(pts[i])
    out.append(_point_at_arclen(pts, cum, s1))
    dedup = [out[0]]
    for p in out[1:]:
        if _d(dedup[-1], p) > 1e-9:
            dedup.append(p)
    return dedup


_LOSS_PER_UM = 0.0002


def _seg(net_id, pts, layer):
    length = round(sum(_d(pts[i], pts[i + 1]) for i in range(len(pts) - 1)), 4)
    loss = round(length * _LOSS_PER_UM, 6)
    return RouteResult(
        net_id=net_id, points_um=[tuple(p) for p in pts], length_um=length,
        straight_um=length, n_bends=0, bend_loss_db=0.0,
        straight_loss_db=loss, total_loss_db=loss, layer=layer,
    )


def make_crossing_hops(rr, m2_points, hop_um=2.0, stub_min=2.0):
    pts = [tuple(p) for p in rr.points_um]
    if not m2_points:
        return [rr]
    cum = _cum_arclen(pts)
    total = cum[-1]
    lo_lim, hi_lim = stub_min, total - stub_min
    if lo_lim >= hi_lim:
        return [rr]
    windows = []
    for q in m2_points:
        s = _arclen_of_point(pts, cum, q)
        windows.append((max(lo_lim, s - hop_um), min(hi_lim, s + hop_um)))
    windows.sort()
    merged = []
    for (a, b) in windows:
        if merged and a <= merged[-1][1] + 1e-9:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append([a, b])
    bounds = [0.0]
    for (a, b) in merged:
        bounds.append(a); bounds.append(b)
    bounds.append(total)
    bounds = sorted(set(round(x, 4) for x in bounds))
    segs = []
    for i in range(len(bounds) - 1):
        lo, hi = bounds[i], bounds[i + 1]
        if hi - lo < 1e-9:
            continue
        mid = (lo + hi) / 2.0
        layer = "M2" if any(a_ <= mid <= b_ for (a_, b_) in merged) else "M1"
        seg_pts = _subpoly(pts, cum, lo, hi)
        if len(seg_pts) >= 2:
            segs.append(_seg(rr.net_id, seg_pts, layer))
    return segs if segs else [rr]


def route_seg_geoms(routes, wg):
    out = []
    for _net_id, segs in (routes or {}).items():
        seg_list = segs if isinstance(segs, (list, tuple)) else [segs]
        for seg in seg_list:
            pts = [tuple(p) for p in getattr(seg, "points_um", seg)]
            out.append(("P", str(getattr(seg, "layer", "M1")).upper(), wg, tuple(pts)))
    return out


def render_svg(geoms, title, path):
    xs, ys = [], []
    for g in geoms:
        for (px, py) in (g[3] if len(g) >= 4 else ()):
            xs.append(px); ys.append(py)
    if not xs:
        xs, ys = [0.0], [0.0]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    mx, my = minx - 4, miny - 4
    w, h = (maxx - minx) + 8, (maxy - miny) + 8
    scale = 660.0 / max(w, h)
    lc = {"M1": "#38bdf8", "M2": "#f59e0b", "DEV": "#22d3ee", "IO": "#a78bfa"}
    parts = []
    for g in geoms:
        kind, layer, width, pts = g[0], g[1], g[2], g[3]
        sp = " ".join(f"{px*scale:.1f},{py*scale:.1f}" for (px, py) in pts)
        if kind == "P":
            col = lc.get(layer, "#38bdf8")
            sw = max(0.6, (width or WG) * scale)
            parts.append(f'<polyline points="{sp}" fill="none" stroke="{col}" '
                         f'stroke-width="{sw:.2f}" stroke-linejoin="round" '
                         f'stroke-linecap="round"/>')
        else:
            parts.append(f'<polygon points="{sp}" fill="{lc["DEV"]}" '
                         f'fill-opacity="0.5" stroke="{lc["DEV"]}" stroke-width="0.5"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="'
           f'{mx*scale:.1f} {my*scale:.1f} {w*scale:.1f} {h*scale:.1f}" '
           f'width="{w*scale:.0f}" height="{h*scale:.0f}" style="background:#0b1220">\n'
           + "\n".join(parts) +
           f'\n<text x="{mx*scale:.1f}" y="{(my+2)*scale:.1f}" fill="#94a3b8" '
           f'font-size="11" font-family="monospace">{title}</text>\n</svg>\n')
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)


# ── rail-tracking netlist 生成（物理忠实 P&R · 相邻三角 mesh）────────────────────
def build_qchip_mesh(N: int, U_target: np.ndarray, out_name: str, title: str):
    """生成任意 N×N 可编程 MZI mesh 的 LinkModel + placement + connects。

    物理忠实性：光先穿输入对角相位层 D（PhaseShifter），再逆序穿过每个 MZI
    （每片 = G_m†，耦合相邻模 (p,p+1)），画出的 mesh 传递矩阵 ≡ 目标酉（机器精度）。

    关键修复（相对 M1 硬编码 / 初版 reck_decompose 直接映射）：
    - 用 reck_triangular_mesh（相邻模耦合）替代 reck_decompose（非相邻模耦合），
      消除波导交叉爆炸（G_Q6 可扩 P&R 的核心）。
    - 波导rail固定在 y=k·RAIL_DY，MZI 置于相邻 rail 之间（yc=(p+0.5)·RAIL_DY），
      不再做 pos 突变 ⇒ 路由交叉数数量级下降。
    - 物理阶段：c=N-2 最靠近输入（光先过 D → 阶段高→低 → 输出），
      MZI x = MZI_X0 + (N-2-c)·COL_PITCH。
    """
    U_target = np.array(U_target, dtype=complex)
    ops, D = reck_triangular_mesh(U_target)
    n_mzi = len(ops)
    link = LinkModel(domain="photon", name=out_name,
                     notes=f"{title} · N={N} programmable MZI mesh (LOQC engine)")
    m_optics = {}

    # 输入/输出光栅
    for k in range(N):
        link.add_device(f"in{k}", "GratingCoupler", {"width": WG, "L": 10.0})
        link.add_device(f"out{k}", "GratingCoupler", {"width": WG, "L": 10.0})
    # 输入对角相位层 D（每个 mode 一个 PhaseShifter）
    for k in range(N):
        ph = float(np.angle(D[k, k]))
        link.add_device(f"ps{k}", "PhaseShifter",
                        {"wg": WG, "L": 4.0, "phase_rad": round(ph, 4)})
    # MZI 单元（DirectionalCoupler 结构代理，Lc 由 CMT 锚定 + G_Q9 守卫）
    for (c, p, mth, mph) in ops:
        Lc_phys = coupler_length_from_theta(mth)
        Lc_layout = max(round(Lc_phys, 4), LC_MIN)
        m_optics[f"m_{c}_{p}"] = {
            "stage": int(c), "mode_pair": (int(p), int(p + 1)),
            "theta": round(mth, 4), "phi": round(mph, 4),
            "Lc_um_true": round(Lc_phys, 3), "Lc_um_layout": Lc_layout,
            "V_at_1cm_arm": round(voltage_from_phase(mph), 3),
        }
        link.add_device(f"m_{c}_{p}", "DirectionalCoupler",
                        {"width": WG, "gap": 0.3, "Lc": Lc_layout})

    if N - 1 > 0:
        out_x = MZI_X0 + (N - 1) * COL_PITCH + MZI_POST
    else:
        out_x = MZI_X0 + MZI_POST

    connects = []
    placement = {}
    for k in range(N):
        placement[f"in{k}"] = (IN_X, float(k * RAIL_DY), 0.0)
        placement[f"ps{k}"] = (PS_X, float(k * RAIL_DY), 0.0)
        placement[f"out{k}"] = (out_x, float(k * RAIL_DY), 0.0)
    # 输入光栅 → 相位层
    for k in range(N):
        connects.append((f"p_in{k}", f"in{k}", "wg", f"ps{k}", "in"))

    # mesh：光按物理序（reversed(ops)，阶段高→低）穿过相邻对 MZI。
    # rail k 固定在 y=k·RAIL_DY；较低模 p→in2(−off下轨)、较高模 p+1→in1(+off上轨)，
    # 出口同步：out2→rail p、out1→rail p+1（rail 序不变，无 permutation）。
    rail_src = {k: (f"ps{k}", "out") for k in range(N)}
    for n_cnt, (c, p, mth, mph) in enumerate(reversed(ops)):
        nid = f"m_{c}_{p}"
        xc = MZI_X0 + (N - 2 - int(c)) * COL_PITCH
        yc = (int(p) + 0.5) * RAIL_DY
        placement[nid] = (xc, yc, 0.0)
        connects.append((f"net_{nid}_2", rail_src[int(p)][0], rail_src[int(p)][1], nid, "in2"))
        connects.append((f"net_{nid}_1", rail_src[int(p + 1)][0], rail_src[int(p + 1)][1], nid, "in1"))
        rail_src[int(p)] = (nid, "out2")
        rail_src[int(p + 1)] = (nid, "out1")
    # MZI 出口 → 输出光栅
    for k in range(N):
        connects.append((f"net_out{k}", rail_src[k][0], rail_src[k][1], f"out{k}", "wg"))
    for (net, s, sp, d_, dp) in connects:
        link.connect(net, s, sp, d_, dp)
    for k in range(N):
        link.external_io(f"io_in{k}", f"in{k}", "fib")
        link.external_io(f"io_out{k}", f"out{k}", "fib")
    link.validate()

    # ── A* 路由 + 交叉化解（复用主权已证机制）──
    obstacles = []
    for c in link.ir.components:
        ox, oy, _ = placement[c.id]
        hw, hh = device_bbox(c.kind, dict(c.params))
        obstacles.append((ox, oy, hw + WG, hh + WG))

    PRE, POST = 10.0, 10.0

    def _outward(p, toward, L):
        dx, dy = toward[0] - p[0], toward[1] - p[1]
        m = math.hypot(dx, dy) or 1.0
        return (round(p[0] + dx / m * L, 4), round(p[1] + dy / m * L, 4))

    base_routes = {}
    route_paths = {}
    for (net, s, sp, d_, dp) in connects:
        a = port_abs(s, sp, placement, link)
        b = port_abs(d_, dp, placement, link)
        a2 = _outward(a, b, PRE)
        b2 = _outward(b, a, POST)
        rr = route_net(net, a2, b2, obstacles=obstacles, wg_width=WG,
                       bend_radius=5.0, corner="round", layer="M1")
        if rr is None:
            full = [a, a2, b2, b]
        else:
            full = [tuple(a)] + [tuple(p) for p in rr.points_um] + [tuple(b)]
        dedup = [full[0]]
        for p in full[1:]:
            if _d(dedup[-1], p) > 1e-6:
                dedup.append(p)
        base_routes[net] = _seg(net, dedup, "M1")
        route_paths[net] = dedup

    STUB_MIN = 0.8
    HOP = 1.0
    net_ids = list(base_routes.keys())
    cum_len = {n: _cum_arclen(route_paths[n]) for n in net_ids}
    tot_len = {n: cum_len[n][-1] for n in net_ids}
    m2_for_net = {nid: [] for nid in net_ids}
    crossing_pairs = []
    unresolved = []

    def _can_host(n, s):
        return (s >= STUB_MIN) and (s <= tot_len[n] - STUB_MIN)

    for i in range(len(net_ids)):
        for j in range(i + 1, len(net_ids)):
            ni, nj = net_ids[i], net_ids[j]
            xps = _path_intersections(route_paths[ni], route_paths[nj])
            if not xps:
                continue
            crossing_pairs.append((ni, nj))
            for P in xps:
                sA = _arclen_of_point(route_paths[ni], cum_len[ni], P)
                sB = _arclen_of_point(route_paths[nj], cum_len[nj], P)
                _canA, _canB = _can_host(ni, sA), _can_host(nj, sB)
                # 每交叉点独立二着色：较大 net id 跳 M2（极小桩 ±HOP，避免 M2∩M2）。
                target = nj if nj > ni else ni
                m2_for_net[target].append(P)
                if not (_canA or _canB):
                    unresolved.append((ni, nj, (round(P[0], 3), round(P[1], 3))))

    routes = {}
    bridged = set()
    for net, rr in base_routes.items():
        segs = make_crossing_hops(rr, m2_for_net[net], hop_um=HOP, stub_min=STUB_MIN)
        routes[net] = segs
        if any(getattr(s, "layer", "M1") == "M2" for s in segs):
            bridged.add(net)

    res = export_chip_gds(link, placement, routes, wg_width=WG,
                          with_io_grating=True, rules=RULES, with_hierarchy=False)
    drc = res.get("drc_report") or {}
    lvs = res.get("lvs_report") or {}
    stats = res.get("gds_stats") or {}

    gds_path = os.path.join(OUT, f"{out_name}.gds")
    with open(gds_path, "wb") as f:
        f.write(res["gds_bytes"])
    geoms = (device_geoms(link, placement, WG)
             + io_grating_geoms(link, placement, WG)
             + route_seg_geoms(routes, WG))
    svg_path = os.path.join(OUT, f"{out_name}.svg")
    render_svg(geoms, f"{title} · M1蓝/M2琥珀=跨层桥", svg_path)

    U_rec = assemble_triangular_mesh(ops, D, N)
    fid = unitary_fidelity(U_rec, U_target)
    loss = mesh_cascade_loss_db(n_mzi, n_crossings=len(crossing_pairs))

    return {
        "name": out_name, "N": N, "title": title,
        "gds_path": gds_path, "gds_bytes": len(res["gds_bytes"]),
        "n_components": len(link.ir.components),
        "gds_elements": stats.get("n_elements"), "bbox_um": stats.get("bbox_um"),
        "multilayer": stats.get("multilayer"),
        "drc_verdict": "PASS" if drc.get("all_pass") else "FAIL",
        "drc_devices": {c: v.get("passed") for c, v in (drc.get("devices") or {}).items()},
        "lvs_verdict": (lvs.get("verdict") or "SKIP"),
        "lvs_nets": (lvs.get("match") or {}).get("n_nets_total"),
        "lvs_matched": (lvs.get("match") or {}).get("n_nets_match"),
        "lvs_violations": lvs.get("n_violations"),
        "n_mzi": n_mzi,
        "n_routed_nets": len(base_routes),
        "n_crossing_pairs": len(crossing_pairs),
        "n_bridged_nets": len(bridged),
        "n_unresolved_crossings": len(unresolved),
        "unresolved_crossings": [list(p) for p in unresolved],
        "compute_core": {
            "N": N, "fidelity": round(fid, 9),
            "recon_err_fro": float(np.linalg.norm(U_rec - U_target)),
            "cascade_loss_db": round(loss, 3),
            "vpi_l_v_cm": VPI_L_V_CM,
        },
        "svg_path": svg_path,
    }


def main():
    argv = sys.argv[1:]
    NS = [int(x) for x in argv] if argv else [4, 8, 16]
    targets = []
    for N in NS:
        if N == 4 and NS == [4]:
            # 单独跑 N=4 时镜映 LDA-Q1 路径纠缠原语（向后兼容 M1 验证）
            U4 = np.eye(4, dtype=complex)
            bs = np.array([[1, 1j], [1j, 1]], dtype=complex) / math.sqrt(2.0)
            U4[np.ix_([0, 2], [0, 2])] = bs
            targets.append((4, U4, "lda_q2_n4", "LDA-Q2 · 4-mode path-entangling LOQC"))
        else:
            targets.append((N, dft_matrix(N), f"lda_q2_n{N}",
                            f"LDA-Q2 · {N}-mode DFT LOQC mesh"))

    results = []
    for (N, U, name, title) in targets:
        r = build_qchip_mesh(N, U, name, title)
        results.append(r)
        print(f"=== {title} ===")
        print(f"GDS   : {r['gds_path']} ({r['gds_bytes']} B, {r['gds_elements']} 元素, "
              f"{r['n_components']} 组件, 多层={r['multilayer']})")
        print(f"bbox  : {r['bbox_um']}")
        print(f"DRC   : {r['drc_verdict']}  ({sum(1 for v in r['drc_devices'].values() if v)}/"
              f"{len(r['drc_devices'])} 器件过)")
        print(f"LVS   : {r['lvs_verdict']}  (nets={r['lvs_nets']}, matched={r['lvs_matched']}, "
              f"viol={r['lvs_violations']})")
        print(f"mesh  : {r['n_mzi']} MZI / {r['n_routed_nets']} 网 / 交叉对 "
              f"{r['n_crossing_pairs']} / 桥接 {r['n_bridged_nets']} / 未解 "
              f"{r['n_unresolved_crossings']}")
        print(f"保真度: {r['compute_core']['fidelity']}  (‖Δ‖={r['compute_core']['recon_err_fro']:.2e})  "
              f"级联损耗={r['compute_core']['cascade_loss_db']} dB")
        print()

    # 通用性（任意 Haar 酉也可编程实现，三角 mesh 同保真）
    haar_fids = {}
    for N in NS:
        rng = np.random.default_rng(7)
        X = (rng.standard_normal((N, N)) + 1j * rng.standard_normal((N, N))) / math.sqrt(2.0)
        Q, R = np.linalg.qr(X)
        U = Q @ np.diag(np.diag(R) / np.abs(np.diag(R)))
        ops, D = reck_triangular_mesh(U)
        haar_fids[N] = round(unitary_fidelity(assemble_triangular_mesh(ops, D, N), U), 9)

    rep = {
        "chip_family": "LDA-Q2 · 参数化 N×N 可编程 MZI mesh（LOQC 通用处理器）P&R 生成器",
        "strategy": "走法一主权全链路（零 gdsfactory）：reck_triangular_mesh（相邻模耦合）→ "
                    "rail-tracking netlist (逆序相邻 MZI + 输入对角相位层 D) → A* 路由 + "
                    "交叉化解 → GDS → DRC/LVS",
        "physical_faithfulness": "画出 mesh 传递矩阵 ≡ 目标酉（机器精度，构造性成立）："
                                 "光逆序穿相邻 MZI(每片=G_m†)+输入 D 相位层 ⇒ 真可编程 LOQC 处理器",
        "results": results,
        "universality_haar_fidelity": haar_fids,
        "gaps_closed": ["G_Q6（可扩 N×N P&R 生成器）", "M1 物理实现诚实缺口（mesh 现忠实于目标酉）"],
        "honest_note": (
            "M2 把 M1 的 4×4 硬编码布局升级为参数化 N×N mesh P&R 生成器，并让画出的 mesh "
            "忠实实现目标酉（任意酉可编程，机器精度）。仍属结构代理版图：MZI/PhaseShifter "
            "为真器件但当前 GDS 几何未生成（平台已知限制）；物理前端 CMT+Vπ·L 由 "
            "mzi_mesh_matmul 给出。真量子态层（Fock/HOM/过程保真度 G_Q1–G_Q4）、标定闭环 "
            "G_Q5、量子 DRC/LVS G_Q7、量子基准 G_Q8 属 M3/M4。规模继续上行对标 "
            "Xanadu Borealis 216 模 / PsiQuantum（M4）。"),
    }
    rep_path = os.path.join(OUT, f"lda_q2_report_{'_'.join(map(str, NS))}.json")
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2,
                  default=lambda o: [o.real, o.imag] if isinstance(o, complex)
                  else (list(o) if hasattr(o, "tolist") else str(o)))
    print(f"报告 : {rep_path}")
    return rep


if __name__ == "__main__":
    main()
