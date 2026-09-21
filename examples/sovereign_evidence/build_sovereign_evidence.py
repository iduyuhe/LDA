"""走法一（主权全链路）真实版图 · 证据集生成器（扩展版，7 例）。

不依赖 gdsfactory（B 级）；纯用 LDA 自有 L0/L1/L2：
  LinkModel → placement → routes → chip_layout_export.export_chip_gds
  （器件几何 + IO 光栅 + 主权 DRC/LVS）。

本脚本产出 7 个典型拓扑，全部经 DRC/LVS 双闸签核，构成「降标走法」的流程
跑通证据（平台熟练度 + 主权链可重复性证明）：
  C1  2×2 方向耦合器（分束器，in2 留空）
  C2  环形 add-drop（drop 端口接线，验证 drop bus）
  C3  2×2 方向耦合器 + 环形谐振器（组合电路）
  C4  MMI 1×2 多模干涉分束器
  C5  对称 Y 分支（SymmetricYBranch）分束器
  C6  Mach-Zehnder 干涉仪（2×DC + 2 臂波导）
  C7  Bragg 反射镜（侧壁调制）透射线

运行（需受管 3.14.3 解释器，自带 numpy）：
  python examples/sovereign_evidence/build_sovereign_evidence.py

产物直接落在脚本同目录（自包含货架）：
  lda_c{1..7}_*.gds / *.svg  +  sovereign_evidence_index.json

LVS 硬契约（与 lda_l2.lvs 逐字节对齐）：
  - routes 的 dict key 必须 == link.connect() 的 net_id；
  - 每条 route 首末端点必须落在对应 net 两端口锚点 ±1.0µm 内（用 port_abs 取）；
  - 不同 net 布线不得相交（否则 short_cross）；
  - 同一端口不得被多于一个 net 占用（否则 short_port）。
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))   # D:/agent_LDA
sys.path.insert(0, os.path.join(ROOT, "lda"))

from lda_chain.link_model import LinkModel
from lda_layout.placement import port_abs
from lda_l2.chip_layout_export import (
    export_chip_gds, device_geoms, io_grating_geoms, route_geoms,
)

WG = 0.5  # 波导宽 µm
RULES = {
    "min_width_um": 0.30,
    "min_space_um": 0.20,
    "min_bend_R_um": 5.0,
    "max_split_angle_deg": 30.0,
}
OUT = HERE  # 产物直接落在货架目录，自包含可复跑


def render_svg(geoms, title, path):
    xs, ys = [], []
    for g in geoms:
        pts = g[3] if len(g) >= 4 else ()
        for (px, py) in pts:
            xs.append(px); ys.append(py)
    if not xs:
        xs, ys = [0.0], [0.0]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    mx, my = minx - 3, miny - 3
    w, h = (maxx - minx) + 6, (maxy - miny) + 6
    scale = 640.0 / max(w, h)
    vb = f"{mx*scale:.1f} {my*scale:.1f} {w*scale:.1f} {h*scale:.1f}"
    polys = []
    for g in geoms:
        kind, layer, width, pts = g[0], g[1], g[2], g[3]
        sp = " ".join(f"{px*scale:.1f},{py*scale:.1f}" for (px, py) in pts)
        if kind == "P":
            sw = max(0.6, (width or WG) * scale)
            polys.append(f'<polyline points="{sp}" fill="none" '
                         f'stroke="#38bdf8" stroke-width="{sw:.2f}" '
                         f'stroke-linejoin="round" stroke-linecap="round"/>')
        else:
            polys.append(f'<polygon points="{sp}" fill="#0e7490" '
                         f'fill-opacity="0.55" stroke="#22d3ee" stroke-width="0.5"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" '
           f'width="{w*scale:.0f}" height="{h*scale:.0f}" '
           f'style="background:#0b1220">\n'
           + "\n".join(polys) +
           f'\n<text x="{mx*scale:.1f}" y="{(my+2)*scale:.1f}" '
           f'fill="#94a3b8" font-size="11" font-family="monospace">{title}</text>'
           f'\n</svg>\n')
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)


def _wp(wp, placement, link):
    """把路由路点规格解析为绝对坐标。wp 形如 ('P', inst, port) 或 ('XY', x, y)。"""
    if wp[0] == "XY":
        return (float(wp[1]), float(wp[2]))
    return port_abs(wp[1], wp[2], placement, link)


def build(name, title, devices, connects, io_ports, placement, route_specs):
    """通用构建器：route_specs = {net_id: [wp, wp, ...]}；返回单电路报告 dict。"""
    link = LinkModel(domain="photon", name=name, notes=title)
    for (d, k, p) in devices:
        link.add_device(d, k, p)
    for (net, s, sp, d_, dp) in connects:
        link.connect(net, s, sp, d_, dp)
    for (io, inst, port) in io_ports:
        link.external_io(io, inst, port)
    link.validate()

    # link 建好后再解析端口锚点（port_abs 需 link 查器件类型）
    routes = {net: {"points_um": [_wp(wp, placement, link) for wp in specs]}
              for net, specs in route_specs.items()}

    res = export_chip_gds(link, placement, routes, wg_width=WG,
                          with_io_grating=True, rules=RULES,
                          with_hierarchy=False)
    drc = res.get("drc_report") or {}
    lvs = res.get("lvs_report") or {}
    stats = res.get("gds_stats") or {}

    gds_path = os.path.join(OUT, f"{name}.gds")
    with open(gds_path, "wb") as f:
        f.write(res["gds_bytes"])
    geoms = (device_geoms(link, placement, WG)
             + io_grating_geoms(link, placement, WG)
             + route_geoms(routes, WG))
    svg_path = os.path.join(OUT, f"{name}.svg")
    render_svg(geoms, title, svg_path)

    return {
        "name": name, "title": title,
        "gds_path": gds_path,
        "gds_bytes": len(res["gds_bytes"]),
        "n_components": len(link.ir.components),
        "gds_elements": stats.get("n_elements"),
        "drc_verdict": "PASS" if drc.get("all_pass") else "FAIL",
        "drc_devices": {c: v.get("passed") for c, v in
                        (drc.get("devices") or {}).items()},
        "lvs_verdict": (lvs.get("verdict") or "SKIP"),
        "lvs_nets": lvs.get("n_nets"),
        "lvs_matched": lvs.get("n_matched"),
        "lvs_violations": lvs.get("violations"),
        "io_ports": res.get("io_ports"),
        "svg_path": svg_path,
    }


# ── C1：2×2 方向耦合器（分束器，in2 留空）────────────────────────────────────
c1 = build(
    "lda_c1_dc_splitter",
    "C1 · 2x2 方向耦合器分束器 (no gdsfactory)",
    devices=[
        ("gc_in",   "GratingCoupler", {"width": WG, "L": 10.0}),
        ("gc_thru", "GratingCoupler", {"width": WG, "L": 10.0}),
        ("gc_drop", "GratingCoupler", {"width": WG, "L": 10.0}),
        ("dc1", "DirectionalCoupler", {"width": WG, "gap": 0.3, "Lc": 10.0}),
    ],
    connects=[
        ("n1", "gc_in",   "wg", "dc1", "in1"),
        ("n2", "dc1",     "out1", "gc_thru", "wg"),
        ("n3", "dc1",     "out2", "gc_drop", "wg"),
    ],
    io_ports=[
        ("io_in",   "gc_in",   "fib"),
        ("io_thru", "gc_thru", "fib"),
        ("io_drop", "gc_drop", "fib"),
    ],
    placement={
        "gc_in":   (0.0,   0.0, 0.0),
        "dc1":     (30.0,  0.0, 0.0),
        "gc_thru": (70.0,  0.0, 0.0),
        "gc_drop": (70.0, -12.0, 0.0),
    },
    route_specs={
        "n1": [("P", "gc_in", "wg"), ("XY", 30.0, 10.0), ("P", "dc1", "in1")],
        "n2": [("P", "dc1", "out1"), ("XY", 70.0, 10.0), ("P", "gc_thru", "wg")],
        "n3": [("P", "dc1", "out2"), ("XY", 40.0, -12.0),
               ("XY", 70.0, -12.0), ("P", "gc_drop", "wg")],
    },
)

# ── C2：环形 add-drop（drop 端口接线）───────────────────────────────────────
c2 = build(
    "lda_c2_ring_add_drop",
    "C2 · 环形谐振器 add-drop (no gdsfactory)",
    devices=[
        ("gc_in",   "GratingCoupler", {"width": WG, "L": 10.0}),
        ("gc_thru", "GratingCoupler", {"width": WG, "L": 10.0}),
        ("gc_drop", "GratingCoupler", {"width": WG, "L": 10.0}),
        ("ring1", "RingResonator", {"R": 8.0, "wg_width": WG, "gap": 0.3}),
    ],
    connects=[
        ("n1", "gc_in",   "wg", "ring1", "in"),
        ("n2", "ring1",   "out", "gc_thru", "wg"),
        ("n3", "ring1",   "drop", "gc_drop", "wg"),
    ],
    io_ports=[
        ("io_in",   "gc_in",   "fib"),
        ("io_thru", "gc_thru", "fib"),
        ("io_drop", "gc_drop", "fib"),
    ],
    placement={
        "gc_in":   (0.0,  0.0, 0.0),
        "ring1":   (40.0, 0.0, 0.0),
        "gc_thru": (90.0, 0.0, 0.0),
        "gc_drop": (40.0, -20.0, 0.0),
    },
    route_specs={
        "n1": [("P", "gc_in", "wg"), ("XY", 28.0, 10.0), ("P", "ring1", "in")],
        "n2": [("P", "ring1", "out"), ("XY", 90.0, -8.55), ("P", "gc_thru", "wg")],
        "n3": [("P", "ring1", "drop"), ("P", "gc_drop", "wg")],
    },
)

# ── C3：2×2 方向耦合器 + 环形谐振器（组合，已验证）───────────────────────────
c3 = build(
    "lda_c3_dc_ring",
    "C3 · 2x2 方向耦合器 + 环形谐振器 (no gdsfactory)",
    devices=[
        ("gc_in",   "GratingCoupler", {"width": WG, "L": 10.0}),
        ("gc_add",  "GratingCoupler", {"width": WG, "L": 10.0}),
        ("gc_thru", "GratingCoupler", {"width": WG, "L": 10.0}),
        ("gc_drop", "GratingCoupler", {"width": WG, "L": 10.0}),
        ("dc1", "DirectionalCoupler", {"width": WG, "gap": 0.3, "Lc": 10.0}),
        ("ring1", "RingResonator", {"R": 8.0, "wg_width": WG, "gap": 0.3}),
    ],
    connects=[
        ("n1", "gc_in",   "wg", "dc1", "in1"),
        ("n2", "gc_add",  "wg", "dc1", "in2"),
        ("n3", "dc1",     "out1", "ring1", "in"),
        ("n4", "ring1",   "out", "gc_thru", "wg"),
        ("n5", "dc1",     "out2", "gc_drop", "wg"),
    ],
    io_ports=[
        ("io_in", "gc_in", "fib"), ("io_add", "gc_add", "fib"),
        ("io_thru", "gc_thru", "fib"), ("io_drop", "gc_drop", "fib"),
    ],
    placement={
        "gc_in":   (0.0,   0.0, 0.0),
        "gc_add":  (0.0, -12.0, 0.0),
        "dc1":     (20.0,  0.0, 0.0),
        "ring1":   (60.0,  0.0, 0.0),
        "gc_thru": (110.0, 0.0, 0.0),
        "gc_drop": (100.0, -12.0, 0.0),
    },
    route_specs={
        "n1": [("P", "gc_in", "wg"), ("XY", 20.0, 10.0), ("P", "dc1", "in1")],
        "n2": [("P", "gc_add", "wg"), ("XY", 20.0, -2.0), ("P", "dc1", "in2")],
        "n3": [("P", "dc1", "out1"), ("XY", 30.0, 12.0), ("XY", 39.0, 12.0),
               ("XY", 39.0, -8.55), ("P", "ring1", "in")],
        "n4": [("P", "ring1", "out"), ("XY", 110.0, -8.55), ("P", "gc_thru", "wg")],
        "n5": [("P", "dc1", "out2"), ("XY", 30.0, -12.0), ("XY", 60.0, -12.0),
               ("XY", 60.0, -2.0), ("P", "gc_drop", "wg")],
    },
)

# ── C4：MMI 1×2 多模干涉分束器 ───────────────────────────────────────────────
c4 = build(
    "lda_c4_mmi_splitter",
    "C4 · MMI 1x2 多模干涉分束器 (no gdsfactory)",
    devices=[
        ("gc_in", "GratingCoupler", {"width": WG, "L": 10.0}),
        ("gc_a",  "GratingCoupler", {"width": WG, "L": 10.0}),
        ("gc_b",  "GratingCoupler", {"width": WG, "L": 10.0}),
        ("mmi1", "MMI", {"width": WG, "W_mmi": 6.0, "L_mmi": 20.0,
                         "L_tap": 4.0, "out_gap": 0.5, "L_out": 3.0}),
    ],
    connects=[
        ("n1", "gc_in", "wg", "mmi1", "in"),
        ("n2", "mmi1",  "out1", "gc_a", "wg"),
        ("n3", "mmi1",  "out2", "gc_b", "wg"),
    ],
    io_ports=[
        ("io_in", "gc_in", "fib"),
        ("io_a",  "gc_a",  "fib"),
        ("io_b",  "gc_b",  "fib"),
    ],
    placement={
        "gc_in": (0.0,  0.0, 0.0),
        "mmi1":  (40.0, 0.0, 0.0),
        "gc_a":  (90.0, 12.0, 0.0),
        "gc_b":  (90.0, -12.0, 0.0),
    },
    route_specs={
        "n1": [("P", "gc_in", "wg"), ("XY", 36.0, 10.0), ("P", "mmi1", "in")],
        "n2": [("P", "mmi1", "out1"), ("XY", 90.0, 0.5), ("P", "gc_a", "wg")],
        "n3": [("P", "mmi1", "out2"), ("XY", 90.0, -0.5), ("P", "gc_b", "wg")],
    },
)

# ── C5：对称 Y 分支（SymmetricYBranch）分束器 ─────────────────────────────────
c5 = build(
    "lda_c5_ybranch_splitter",
    "C5 · 对称Y分支 1x2 分束器 (no gdsfactory)",
    devices=[
        ("gc_in", "GratingCoupler", {"width": WG, "L": 10.0}),
        ("gc_a",  "GratingCoupler", {"width": WG, "L": 10.0}),
        ("gc_b",  "GratingCoupler", {"width": WG, "L": 10.0}),
        ("yb1", "SymmetricYBranch", {"width": WG, "split_angle": 20.0,
                                     "arm_length": 8.0}),
    ],
    connects=[
        ("n1", "gc_in", "wg", "yb1", "in"),
        ("n2", "yb1",   "out1", "gc_a", "wg"),
        ("n3", "yb1",   "out2", "gc_b", "wg"),
    ],
    io_ports=[
        ("io_in", "gc_in", "fib"),
        ("io_a",  "gc_a",  "fib"),
        ("io_b",  "gc_b",  "fib"),
    ],
    placement={
        "gc_in": (0.0,  0.0, 0.0),
        "yb1":   (40.0, 0.0, 0.0),
        "gc_a":  (90.0, 12.0, 0.0),
        "gc_b":  (90.0, -12.0, 0.0),
    },
    route_specs={
        "n1": [("P", "gc_in", "wg"), ("XY", 40.0, 10.0), ("P", "yb1", "in")],
        "n2": [("P", "yb1", "out1"), ("XY", 90.0, 1.389), ("P", "gc_a", "wg")],
        "n3": [("P", "yb1", "out2"), ("XY", 90.0, -1.389), ("P", "gc_b", "wg")],
    },
)

# ── C6：Mach-Zehnder 干涉仪（2×DC + 2 臂波导）─────────────────────────────────
c6 = build(
    "lda_c6_mzi_interferometer",
    "C6 · Mach-Zehnder 干涉仪 2x2 (no gdsfactory)",
    devices=[
        ("gc_in",   "GratingCoupler", {"width": WG, "L": 10.0}),
        ("gc_thru", "GratingCoupler", {"width": WG, "L": 10.0}),
        ("gc_drop", "GratingCoupler", {"width": WG, "L": 10.0}),
        ("dc1", "DirectionalCoupler", {"width": WG, "gap": 0.3, "Lc": 10.0}),
        ("dc2", "DirectionalCoupler", {"width": WG, "gap": 0.3, "Lc": 10.0}),
        ("wg1", "Waveguide", {"width": WG, "length": 10.0}),
        ("wg2", "Waveguide", {"width": WG, "length": 10.0}),
    ],
    connects=[
        ("n1", "gc_in", "wg", "dc1", "in1"),
        ("n2", "dc1", "out1", "wg1", "in"),
        ("n3", "wg1", "out", "dc2", "in1"),
        ("n4", "dc1", "out2", "wg2", "in"),
        ("n5", "wg2", "out", "dc2", "in2"),
        ("n6", "dc2", "out1", "gc_thru", "wg"),
        ("n7", "dc2", "out2", "gc_drop", "wg"),
    ],
    io_ports=[
        ("io_in", "gc_in", "fib"),
        ("io_thru", "gc_thru", "fib"),
        ("io_drop", "gc_drop", "fib"),
    ],
    placement={
        "gc_in":   (0.0,   0.0, 0.0),
        "dc1":     (20.0,  0.0, 0.0),
        "wg1":     (45.0,  8.0, 0.0),
        "wg2":     (45.0, -8.0, 0.0),
        "dc2":     (70.0,  0.0, 0.0),
        "gc_thru": (110.0, 0.0, 0.0),
        "gc_drop": (110.0, -12.0, 0.0),
    },
    route_specs={
        "n1": [("P", "gc_in", "wg"), ("XY", 20.0, 10.0), ("P", "dc1", "in1")],
        "n2": [("P", "dc1", "out1"), ("XY", 45.0, 0.4), ("P", "wg1", "in")],
        "n3": [("P", "wg1", "out"), ("XY", 70.0, 8.0), ("P", "dc2", "in1")],
        "n4": [("P", "dc1", "out2"), ("XY", 45.0, -0.4), ("P", "wg2", "in")],
        "n5": [("P", "wg2", "out"), ("XY", 70.0, -8.0), ("P", "dc2", "in2")],
        "n6": [("P", "dc2", "out1"), ("XY", 110.0, 0.4), ("P", "gc_thru", "wg")],
        "n7": [("P", "dc2", "out2"), ("XY", 110.0, -0.4), ("P", "gc_drop", "wg")],
    },
)

# ── C7：Bragg 反射镜（侧壁调制）透射线 ────────────────────────────────────────
c7 = build(
    "lda_c7_bragg_mirror",
    "C7 · Bragg 反射镜透射线 (no gdsfactory)",
    devices=[
        ("gc_in",  "GratingCoupler", {"width": WG, "L": 10.0}),
        ("gc_out", "GratingCoupler", {"width": WG, "L": 10.0}),
        ("bm1", "BraggMirror", {"width": WG, "corrugation": 0.12,
                                "periods": 6, "wl0_um": 1.55,
                                "h_core_um": 0.22, "n_core": 3.48,
                                "n_clad": 1.44}),
    ],
    connects=[
        ("n1", "gc_in", "wg", "bm1", "in"),
        ("n2", "bm1", "out", "gc_out", "wg"),
    ],
    io_ports=[
        ("io_in", "gc_in", "fib"),
        ("io_out", "gc_out", "fib"),
    ],
    placement={
        "gc_in":  (0.0, 0.0, 0.0),
        "bm1":    (40.0, 0.0, 0.0),
        "gc_out": (90.0, 0.0, 0.0),
    },
    route_specs={
        "n1": [("P", "gc_in", "wg"), ("XY", 38.0, 10.0), ("P", "bm1", "in")],
        "n2": [("P", "bm1", "out"), ("XY", 90.0, 0.0), ("P", "gc_out", "wg")],
    },
)

# ── MESH4：4×4 MZI 网格 P&R（4×4 光子计算核可行性，走法一）──────────────────
# 用户拍板「进证据集索引 + CI 护栏」。复用 build_4x4_mzi_mesh.build_mesh() 的真实
# 主权链产出（6 MZI 单元 + 4 入 4 出 + M1/M2 跨层桥接化解交叉），作为第 8 例。
# 该例独立于 c1-c7 的基元/组合范式，属「计算核可行性」证明。
import build_4x4_mzi_mesh as _m4  # noqa: E402
mesh4 = _m4.build_mesh()

# ── 汇总报告 ────────────────────────────────────────────────────────────────
circuits = [c1, c2, c3, c4, c5, c6, c7, mesh4]
index = {
    "strategy": "降标走法 · 主权全链路（走法一，零 gdsfactory 依赖）流程跑通证据",
    "interpreter": "managed 3.14.3/python.exe (自带 numpy)",
    "shelf": "examples/sovereign_evidence/",
    "n_circuits": len(circuits),
    "topology_classes": {
        "splitter": ["C1", "C4", "C5"],
        "ring": ["C2", "C3"],
        "interferometer": ["C6"],
        "filter_reflector": ["C7"],
        "compute_core": ["MESH4"],
    },
    "all_drc_pass": all(c["drc_verdict"] == "PASS" for c in circuits),
    "all_lvs_accept": all(c["lvs_verdict"] == "ACCEPT" for c in circuits),
    "honest_note": ("主权子集 DRC + LVS 几何合法性已验证；C4 MMI 另已有 2D-TEz 模型级"
                    "光学表征（见 c4_mmi_characterization.json：过量损耗 4.08dB、"
                    "不平衡 0.019dB，B16 根因显示 L=20µm 仅达理想成像长度 146µm 的 14%）。"
                    "该表征为 2D 数值结果，非物理定律锚；依 E5 报告 MMI 过量损耗在 2D 层级"
                    "不可判到 0.1dB tol，真锚需 3D 矢量求解器或流片。未注册为可售 GP-* 基元，"
                    "不进创新超市当货架商品。"),
    "circuits": circuits,
}
idx_path = os.path.join(OUT, "sovereign_evidence_index.json")
with open(idx_path, "w", encoding="utf-8") as f:
    json.dump(index, f, ensure_ascii=False, indent=2)

print("=== 走法一 主权版图证据集（扩展版，8 例：7 基元/组合 + 4×4 计算核）===")
for c in circuits:
    print(f"\n[{c['name']}] {c['title']}")
    print(f"  GDS    : {c['gds_path']}  ({c['gds_bytes']} B, {c['gds_elements']} 元素, {c['n_components']} 组件)")
    print(f"  DRC    : {c['drc_verdict']}  {c['drc_devices']}")
    print(f"  LVS    : {c['lvs_verdict']}  (nets={c['lvs_nets']}, matched={c['lvs_matched']}, viol={c['lvs_violations']})")
    print(f"  IO端口 : {c['io_ports']}")
    print(f"  SVG    : {c['svg_path']}")
print(f"\n汇总: 全部DRC PASS = {index['all_drc_pass']} | 全部LVS ACCEPT = {index['all_lvs_accept']}")
print(f"索引: {idx_path}")
