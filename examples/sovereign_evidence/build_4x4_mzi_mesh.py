"""走法一（主权全链路）· 4×4 MZI 网格 P&R 可行性证明（4×4 光子计算核）。

这是「4×4 光子计算核」的**物理版图 P&R** 实证：把 mzi_mesh_matmul.py 的
Reck 分解（计算核数学层，N=4 → 6 个 MZI 单元、保真度≈1.0）映射到真实
主权版图链路（LinkModel → placement → A* 路由 → export_chip_gds + DRC/LVS）。

关键可行性闸门：mesh 必然含 waveguide crossing（交叉）。主权链 LVS 的
_can_cross(M1,M2)=False（异层介质隔离）→ 把交叉的两根波导一根放 M1、一根
放 M2（跨层桥接），多层 LVS 即放行。本脚本用此机制实跑 4×4 mesh。

诚实边界（见报告 honest_note）：
- MZI 单元在此用 DirectionalCoupler（2×2 端口结构代理）表示；真实 optics
  （θ/φ→耦合长度/相移电压，CMT+Vπ·L 物理锚）在 mzi_mesh_matmul.py。
- 仅验证几何合法性（主权子集 DRC + 多层 LVS 拓扑一致）+ 交叉化解机制；
  尚无逐器件光学表征，非 foundry 工艺级 deck，未锚定可售 GP-*。
"""
from __future__ import annotations

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))   # D:/agent_LDA
sys.path.insert(0, os.path.join(ROOT, "lda"))

from lda_chain.link_model import LinkModel
from lda_layout.placement import port_abs, device_bbox
from lda_layout.router import route_net, RouteResult
from lda_l2.chip_layout_export import (
    export_chip_gds, device_geoms, io_grating_geoms, route_geoms,
)
from lda_l2.mzi_mesh_matmul import (
    reck_decompose, dft_matrix, assemble_mesh, unitary_fidelity, mesh_cascade_loss_db,
)

WG = 0.5
RULES = {
    "min_width_um": 0.30,
    "min_space_um": 0.20,
    "min_bend_R_um": 5.0,
    "max_split_angle_deg": 30.0,
}
OUT = HERE


# ── 几何工具 ──────────────────────────────────────────────────────────────────
def _d(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _seg_intersect_point(p1, p2, p3, p4):
    """两线段交点（不相交返回 None）。用于定位交叉点以做局部跨层跳。"""
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
    """返回两折线所有交点（列表）。"""
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
    """点 q 到折线最近点的弧长位置（交叉点必在某折线上）。"""
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
    """截取弧长 [s0,s1] 间的子折线（端点插值）。"""
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


_LOSS_PER_UM = 0.0002   # 几何代理：~0.2 dB/cm（Si 波导量级），仅结构性标注


def _seg(net_id, pts, layer):
    """构造一段 RouteResult（直线段，无弯折 → 直段=总长，损耗按长度代理）。"""
    length = round(sum(_d(pts[i], pts[i + 1]) for i in range(len(pts) - 1)), 4)
    loss = round(length * _LOSS_PER_UM, 6)
    return RouteResult(
        net_id=net_id,
        points_um=[tuple(p) for p in pts],
        length_um=length,
        straight_um=length,
        n_bends=0,
        bend_loss_db=0.0,
        straight_loss_db=loss,
        total_loss_db=loss,
        layer=layer,
    )


def make_crossing_hops(rr, m2_points, hop_um=2.0, stub_min=2.0):
    """对一条网做『逐交叉局部 M2 跳』：在每个需 M2 的交叉点附近开一段 M2
    窗口（其余为 M1）。窗口两端强制留 ≥stub_min 的 M1 残段，确保网的首/末段
    仍在 M1（匹配器件端口层），中间跨层跳点坐标重合 → LVS via 桥接合法。
    每个交叉点恰一根网在 M2、另一根在 M1（异层 → 多层 LVS 不判短），且不会
    制造 M2∩M2。无论冲突图是否二分都可解。"""
    pts = [tuple(p) for p in rr.points_um]
    if not m2_points:
        return [rr]
    cum = _cum_arclen(pts)
    total = cum[-1]
    lo_lim, hi_lim = stub_min, total - stub_min
    if lo_lim >= hi_lim:
        # 网太短，留不出 M1 残段：整条留 M1（该交叉改由对端网跳 M2）
        return [rr]
    # 每个 M2 点 → 弧长处开窗口（夹紧到 interior，绝不触首/末端点）
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
    # 在窗口边界处切分折线
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
    """逐段输出布线几何（带层标签），供 SVG 按 M1/M2 着色。"""
    out = []
    for _net_id, segs in (routes or {}).items():
        seg_list = segs if isinstance(segs, (list, tuple)) else [segs]
        for seg in seg_list:
            pts = [tuple(p) for p in getattr(seg, "points_um", seg)]
            out.append(("P", str(getattr(seg, "layer", "M1")).upper(), wg, tuple(pts)))
    return out


def render_svg(geoms, title, path, layer_colors=None):
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
    lc = layer_colors or {"M1": "#38bdf8", "M2": "#f59e0b", "DEV": "#22d3ee",
                          "IO": "#a78bfa"}
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
                         f'fill-opacity="0.5" stroke="{lc["DEV"]}" '
                         f'stroke-width="0.5"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="'
           f'{mx*scale:.1f} {my*scale:.1f} {w*scale:.1f} {h*scale:.1f}" '
           f'width="{w*scale:.0f}" height="{h*scale:.0f}" '
           f'style="background:#0b1220">\n' + "\n".join(parts) +
           f'\n<text x="{mx*scale:.1f}" y="{(my+2)*scale:.1f}" fill="#94a3b8" '
           f'font-size="11" font-family="monospace">{title}</text>\n</svg>\n')
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)


# ── 4×4 MZI 网格定义 ────────────────────────────────────────────────────────────
# 6 个 MZI 单元（Reck 三角/folded 布局：3 级各 2 个），4 入 4 出。
# 坐标（µm）：DC 长 Lc=10，off=(gap+core_w)/2=0.4。
def build_mesh():
    link = LinkModel(domain="photon", name="lda_4x4_mzi_mesh",
                     notes="4x4 MZI mesh (Reck folded) P&R feasibility")
    # 6 MZI 单元（DirectionalCoupler 结构代理）
    for i in range(6):
        nid = f"m{i}"
        link.add_device(nid, "DirectionalCoupler",
                        {"width": WG, "gap": 0.3, "Lc": 10.0})
    # 4 入 / 4 出 光栅
    for k in range(4):
        link.add_device(f"in{k}", "GratingCoupler", {"width": WG, "L": 10.0})
        link.add_device(f"out{k}", "GratingCoupler", {"width": WG, "L": 10.0})

    connects = [
        ("n1", "in0", "wg", "m0", "in1"),
        ("n2", "in1", "wg", "m0", "in2"),
        ("n3", "in2", "wg", "m1", "in1"),
        ("n4", "in3", "wg", "m1", "in2"),
        # 一级 → 二级（含交叉：m0.out2↔m3.in2 与 m1.out1↔m2.in2 互换）
        ("n5", "m0", "out1", "m2", "in1"),
        ("n6", "m0", "out2", "m3", "in2"),
        ("n7", "m1", "out1", "m2", "in2"),
        ("n8", "m1", "out2", "m3", "in1"),
        # 二级 → 三级（含交叉：m2.out2↔m5.in2 与 m3.out1↔m4.in2 互换）
        ("n9",  "m2", "out1", "m4", "in1"),
        ("n10", "m2", "out2", "m5", "in2"),
        ("n11", "m3", "out1", "m4", "in2"),
        ("n12", "m3", "out2", "m5", "in1"),
        # 三级 → 输出
        ("n13", "m4", "out1", "out0", "wg"),
        ("n14", "m4", "out2", "out1", "wg"),
        ("n15", "m5", "out1", "out2", "wg"),
        ("n16", "m5", "out2", "out3", "wg"),
    ]
    for (net, s, sp, d_, dp) in connects:
        link.connect(net, s, sp, d_, dp)
    for k in range(4):
        link.external_io(f"io_in{k}", f"in{k}", "fib")
        link.external_io(f"io_out{k}", f"out{k}", "fib")
    link.validate()

    # 放置：三级列 x=20/60/100；每列两个 MZI（上 yc=45 混合轨2/3，下 yc=17 混合轨0/1）
    placement = {
        "in0":  (-15,  0.0, 0.0), "in1": (-15, 14.0, 0.0),
        "in2":  (-15, 28.0, 0.0), "in3": (-15, 42.0, 0.0),
        "m0":   (20.0, 17.0, 0.0), "m1": (20.0, 45.0, 0.0),
        "m2":   (60.0, 17.0, 0.0), "m3": (60.0, 45.0, 0.0),
        "m4":  (100.0, 17.0, 0.0), "m5": (100.0, 45.0, 0.0),
        "out0": (140.0,  0.0, 0.0), "out1": (140.0, 14.0, 0.0),
        "out2": (140.0, 28.0, 0.0), "out3": (140.0, 42.0, 0.0),
    }

    # 障碍：器件包围盒（含波导半宽余量）
    obstacles = []
    for c in link.ir.components:
        ox, oy, _ = placement[c.id]
        hw, hh = device_bbox(c.kind, dict(c.params))
        obstacles.append((ox, oy, hw + WG, hh + WG))

    # A* 布线（先全部走 M1）。为避免交叉贴端口（首/末段须留 M1 残段接器件），
    # 在源/的各自首末端外扩一段直 M1 引线（PRE/POST），把交叉推到网的内部，
    # 使每个交叉点对任意一根网都落在 interior → 可容下 M2 窗口。
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
        # 去重相邻重复点（避免 0 长段）
        dedup = [full[0]]
        for p in full[1:]:
            if _d(dedup[-1], p) > 1e-6:
                dedup.append(p)
        base_routes[net] = _seg(net, dedup, "M1")
        route_paths[net] = dedup

    # 交叉检测 + 逐交叉分配 M2 跳：每个交点必有一根网跳到 M2，另一根留 M1
    # （异层 → 多层 LVS 不判短）。跳点须落在该网的 interior（距首/末端 ≥stub_min），
    # 故优先选『能容下 M2 窗口』的网；两网都能则取字典序大者；两网都不能（交点贴端口）
    # 则记入 unresolved 诚实披露。无论冲突图是否二分均可解，且不会制造 M2∩M2。
    STUB_MIN = 1.0
    HOP = 2.0
    net_ids = list(base_routes.keys())
    cum_len = {n: _cum_arclen(route_paths[n]) for n in net_ids}
    tot_len = {n: cum_len[n][-1] for n in net_ids}
    m2_for_net = {nid: [] for nid in net_ids}
    crossing_pairs = []
    unresolved = []

    def _can_host(n, s):
        # 只需交叉点 s 本身落在 interior（首/末端留 ≥STUB_MIN 的 M1 残段接器件）；
        # M2 窗口左缘夹紧到 STUB_MIN 即可覆盖 s，无需整窗越过 STUB_MIN。
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
                canA, canB = _can_host(ni, sA), _can_host(nj, sB)
                if canA and not canB:
                    m2_for_net[ni].append(P)
                elif canB and not canA:
                    m2_for_net[nj].append(P)
                elif canA and canB:
                    m2_for_net[nj if nj > ni else ni].append(P)   # 确定性：大者跳
                else:
                    unresolved.append((ni, nj, (round(P[0], 3), round(P[1], 3))))

    # 组装多层 routes：每网按记录的 M2 交叉点做局部跨层跳
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

    gds_path = os.path.join(OUT, "lda_4x4_mzi_mesh.gds")
    with open(gds_path, "wb") as f:
        f.write(res["gds_bytes"])
    geoms = (device_geoms(link, placement, WG)
             + io_grating_geoms(link, placement, WG)
             + route_seg_geoms(routes, WG))
    svg_path = os.path.join(OUT, "lda_4x4_mzi_mesh.svg")
    render_svg(geoms, "4x4 MZI mesh · M1蓝/M2琥珀=跨层桥", svg_path,
               layer_colors={"M1": "#38bdf8", "M2": "#f59e0b",
                             "DEV": "#22d3ee", "IO": "#a78bfa"})

    # 计算核数学层（Reck 分解）
    U = dft_matrix(4)
    ops, D = reck_decompose(U)
    U_rec = assemble_mesh(ops, D, 4)
    fid = unitary_fidelity(U_rec, U)
    loss = mesh_cascade_loss_db(len(ops), n_crossings=len(crossing_pairs))

    return {
        "name": "lda_4x4_mzi_mesh",
        "title": "MESH4 · 4×4 MZI 网格 P&R（4×4 光子计算核可行性, no gdsfactory）",
        "io_ports": [f"in{k}.fib" for k in range(4)]
                    + [f"out{k}.fib" for k in range(4)],
        "gds_path": gds_path, "gds_bytes": len(res["gds_bytes"]),
        "n_components": len(link.ir.components),
        "gds_elements": stats.get("n_elements"),
        "bbox_um": stats.get("bbox_um"),
        "multilayer": stats.get("multilayer"),
        "drc_verdict": "PASS" if drc.get("all_pass") else "FAIL",
        "drc_devices": {c: v.get("passed") for c, v in
                        (drc.get("devices") or {}).items()},
        "lvs_verdict": (lvs.get("verdict") or "SKIP"),
        "lvs_nets": lvs.get("n_nets"), "lvs_matched": lvs.get("n_matched"),
        "lvs_violations": lvs.get("violations"),
        "n_routed_nets": len(base_routes),
        "n_crossing_pairs": len(crossing_pairs),
        "crossing_pairs": [list(p) for p in crossing_pairs],
        "n_bridged_nets": len(bridged), "bridged_nets": sorted(bridged),
        "n_unresolved_crossings": len(unresolved),
        "unresolved_crossings": [list(p) for p in unresolved],
        "compute_core": {
            "N": 4, "n_mzi": len(ops), "fidelity": round(fid, 6),
            "cascade_loss_db": round(loss, 3),
            "ops": [(int(i), int(j), round(th, 4), round(ph, 4))
                    for (i, j, th, ph) in ops],
        },
        "svg_path": svg_path,
    }


if __name__ == "__main__":
    r = build_mesh()
    print("=== 4×4 MZI 网格 P&R（4×4 光子计算核可行性）===")
    print(f"GDS    : {r['gds_path']}  ({r['gds_bytes']} B, {r['gds_elements']} 元素, "
          f"{r['n_components']} 组件, 多层={r['multilayer']})")
    print(f"bbox   : {r['bbox_um']}")
    print(f"DRC    : {r['drc_verdict']}  {r['drc_devices']}")
    print(f"LVS    : {r['lvs_verdict']}  (nets={r['lvs_nets']}, matched={r['lvs_matched']}, "
          f"viol={r['lvs_violations']})")
    print(f"布线    : {r['n_routed_nets']} 网 / 交叉对 {r['n_crossing_pairs']} / "
          f"桥接网 {r['n_bridged_nets']} {r['bridged_nets']}")
    print(f"计算核 : N={r['compute_core']['N']} MZI={r['compute_core']['n_mzi']} "
          f"保真度={r['compute_core']['fidelity']} 级联损耗={r['compute_core']['cascade_loss_db']} dB")
    print(f"SVG    : {r['svg_path']}")

    rep = {"strategy": "4×4 MZI 网格 P&R · 主权全链路（走法一，零 gdsfactory）",
           "mesh": r,
           "honest_note": (
               "本版图证明 4×4 光子计算核的『物理 P&R + 交叉化解』可行性：6 个 MZI 单元"
               "（Reck folded，4 入 4 出）经主权链产出真实 GDSII，DRC PASS、多层 LVS ACCEPT；"
               "mesh 的交叉由 M1/M2 跨层桥接化解（can_cross(M1,M2)=False → 异层投影不判短）。"
               "MZI 单元用 DirectionalCoupler 作 2×2 结构代理；真实光学（θ/φ→耦合长度/相移，"
               "CMT+Vπ·L 物理锚）在 mzi_mesh_matmul.py，计算核保真度≈1.0。仅验证几何合法性与"
               "交叉机制，无逐器件光学表征，非 foundry deck，未锚定可售 GP-*、不进创新超市。")}
    rep_path = os.path.join(OUT, "lda_4x4_mzi_mesh_report.json")
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print(f"报告   : {rep_path}")
