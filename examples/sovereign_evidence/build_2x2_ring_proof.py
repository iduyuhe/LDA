"""走法一（主权全链路）真实版图生成：2×2 方向耦合器 + 环形谐振器（最小证明件）。

这是主权全链路（不依赖 gdsfactory）跑通的第一块真实版图，拓扑与证据集 C3 一致，
作为新人"第一读"的最简示例。完整 7 例见同目录 build_sovereign_evidence.py。

运行（受管 3.14.3 解释器，自带 numpy）：
  python examples/sovereign_evidence/build_2x2_ring_proof.py

产物（直接落在脚本同目录）：
  lda_2x2_ring.gds   真实 GDSII 版图（器件 + 布线 + 光栅）
  lda_2x2_ring.svg   渲染图（深色主题）
  lda_2x2_ring_report.json  导出统计 + DRC/LVS 判决

关键契约（与 lda_l2.lvs 逐字节对齐）：
  - routes 的 dict key 必须与 link.connect() 的 net_id 完全一致；
  - 每条 route 首末端点必须落在对应 net 的两个端口锚点 ±1.0µm 内；
  - 不同 net 的布线不得相交（否则 short_cross）；
  - 同一端口不得被多于一个 net 占用（否则 short_port）。
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
from lda_layout.placement import port_abs
from lda_l2.chip_layout_export import (
    export_chip_gds, device_geoms, io_grating_geoms, route_geoms,
)
from lda_l2 import gds_export

WG = 0.5  # 波导宽 µm

# ── 1) 链路构建（器件实例 + 端口 + 内部互连 + 外部 IO）──────────────────────
link = LinkModel(domain="photon", name="lda_2x2_ring",
                 notes="走法一 sovereignty demo: 2x2 方向耦合器 + 环形谐振器")
link.add_device("gc_in",   "GratingCoupler", {"width": WG, "L": 10.0})
link.add_device("gc_add",  "GratingCoupler", {"width": WG, "L": 10.0})
link.add_device("gc_thru", "GratingCoupler", {"width": WG, "L": 10.0})
link.add_device("gc_drop", "GratingCoupler", {"width": WG, "L": 10.0})
# 2×2：方向耦合器（两输入 in1/in2，两输出 out1/out2）
link.add_device("dc1", "DirectionalCoupler",
                {"width": WG, "gap": 0.3, "Lc": 10.0})
# 环形：谐振环（in/out 下 bus，drop 上 bus）
link.add_device("ring1", "RingResonator",
                {"R": 8.0, "wg_width": WG, "gap": 0.3})

# 五个内部互连网络（net_id == routes 的 key，LVS 据此逐网比对）
link.connect("n1", "gc_in",   "wg",   "dc1",    "in1")
link.connect("n2", "gc_add",  "wg",   "dc1",    "in2")
link.connect("n3", "dc1",     "out1", "ring1",  "in")
link.connect("n4", "ring1",   "out",  "gc_thru","wg")
link.connect("n5", "dc1",     "out2", "gc_drop", "wg")

# 外部 IO：每个光栅耦合器的光纤侧（fib）作为芯片对外接口 → 渲染真实光栅齿区
for g in ("gc_in", "gc_add", "gc_thru", "gc_drop"):
    link.external_io(f"io_{g}", g, "fib")
link.validate()

# ── 2) 放置（绝对坐标 µm）────────────────────────────────────────────────
# dc1 端口（相对原点）：in1=(0,+0.4) in2=(0,-0.4) out1=(Lc,+0.4) out2=(Lc,-0.4)
# ring1 端口：in=(±R*1.5, -off) drop=(0,+off)，off=R+wg/2+gap=8.55
placement = {
    "gc_in":   (  0.0,   0.0, 0.0),
    "gc_add":  (  0.0, -12.0, 0.0),
    "dc1":     ( 20.0,   0.0, 0.0),
    "ring1":   ( 60.0,   0.0, 0.0),
    "gc_thru": (110.0,   0.0, 0.0),
    "gc_drop": (100.0, -12.0, 0.0),
}

# ── 3) 布线（每条 key 与 connect net_id 一致；端点精确落在端口锚点）─────────
# 手工规划的水平/垂直"通道"互不相交，确保 LVS 无 short_cross。
routes = {
    "n1": {"points_um": [
        port_abs("gc_in",   "wg",   placement, link),   # (0, 10)
        (20.0, 10.0),
        port_abs("dc1",     "in1",  placement, link),   # (20, 0.4)
    ]},
    "n2": {"points_um": [
        port_abs("gc_add",  "wg",   placement, link),   # (0, -2)
        (20.0, -2.0),
        port_abs("dc1",     "in2",  placement, link),   # (20, -0.4)
    ]},
    "n3": {"points_um": [
        port_abs("dc1",     "out1", placement, link),   # (30, 0.4)
        (30.0, 12.0),    # 先向上避开 dc1 输出端的 0.8µm 紧邻端口
        (39.0, 12.0),
        (39.0, -8.55),
        port_abs("ring1",   "in",   placement, link),   # (48, -8.55)
    ]},
    "n4": {"points_um": [
        port_abs("ring1",   "out",  placement, link),   # (72, -8.55)
        (110.0, -8.55),
        port_abs("gc_thru", "wg",   placement, link),   # (110, 10)
    ]},
    "n5": {"points_um": [
        port_abs("dc1",     "out2", placement, link),   # (30, -0.4)
        (30.0, -12.0),   # 先向下，与 n3 的向上通道分离
        (60.0, -12.0),   # 在 n4 水平段 (x>=72) 左侧折返
        (60.0, -2.0),    # 升至 y=-2（高于 n4 的 y=-8.55 水平段）
        port_abs("gc_drop", "wg",   placement, link),   # (100, -2)
    ]},
}

# ── 4) 导出真实 GDS + 主权 DRC/LVS ──────────────────────────────────────
# 工艺规则：min_width 取 0.3µm（光栅齿宽 0.34µm 落在规则内）；其余沿用默认。
RULES = {
    "min_width_um": 0.30,
    "min_space_um": 0.20,
    "min_bend_R_um": 5.0,
    "max_split_angle_deg": 30.0,
}
res = export_chip_gds(link, placement, routes, wg_width=WG,
                      with_io_grating=True, rules=RULES,
                      with_hierarchy=False)
gds_bytes = res["gds_bytes"]
stats = res["gds_stats"]
drc = res.get("drc_report") or {}
lvs = res.get("lvs_report") or {}

out_dir = HERE   # 产物直接落在货架目录
gds_path = os.path.join(out_dir, "lda_2x2_ring.gds")
with open(gds_path, "wb") as f:
    f.write(gds_bytes)

# ── 5) 渲染：用与导出同源的几何元组，画深色 SVG/PNG ─────────────────────
geoms = (device_geoms(link, placement, WG)
         + io_grating_geoms(link, placement, WG)
         + route_geoms(routes, WG))

xs, ys = [], []
for g in geoms:
    pts = g[3] if len(g) >= 4 else ()
    for (px, py) in pts:
        xs.append(px); ys.append(py)
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
       f'fill="#94a3b8" font-size="11" font-family="monospace">'
       f'LDA 2×2 方向耦合器 + 环形谐振器 · 主权版图 (no gdsfactory)</text>'
       f'\n</svg>\n')
svg_path = os.path.join(out_dir, "lda_2x2_ring.svg")
with open(svg_path, "w", encoding="utf-8") as f:
    f.write(svg)

# PNG（若 matplotlib 可用）
png_path = os.path.join(out_dir, "lda_2x2_ring.png")
png_ok = False
png_note = ""
try:
    import matplotlib  # noqa: F401
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as _np
    fig, ax = plt.subplots(figsize=(9, 6), dpi=110)
    ax.set_facecolor("#0b1220")
    for g in geoms:
        kind, layer, width, pts = g[0], g[1], g[2], g[3]
        if kind == "P":
            xs_ = [p[0] for p in pts]; ys_ = [p[1] for p in pts]
            ax.plot(xs_, ys_, color="#38bdf8", lw=max(0.4, (width or WG) * 3))
        else:
            arr = _np.array(pts)
            ax.fill(arr[:, 0], arr[:, 1], color="#0e7490", alpha=0.55,
                    edgecolor="#22d3ee", lw=0.4)
    ax.invert_yaxis()
    ax.set_aspect("equal"); ax.axis("off")
    fig.tight_layout()
    fig.savefig(png_path, facecolor="#0b1220")
    plt.close(fig)
    png_ok = True
except Exception as e:  # noqa: BLE001
    png_note = str(e)

# ── 6) 报告 ─────────────────────────────────────────────────────────────
def _verdict(d):
    if not d:
        return "SKIP"
    v = d.get("verdict")
    return str(v) if v is not None else "SKIP"

report = {
    "gds_path": gds_path,
    "gds_bytes": len(gds_bytes),
    "n_components": len(link.ir.components),
    "gds_stats": {k: stats.get(k) for k in
                  ("n_elements", "gds_bytes", "multilayer")},
    "drc_verdict": "PASS" if drc.get("all_pass") else "FAIL",
    "drc_detail": {k: drc.get(k) for k in drc if k != "verdict"},
    "lvs_verdict": _verdict(lvs),
    "lvs_detail": {k: lvs.get(k) for k in lvs if k != "verdict"},
    "io_ports": res.get("io_ports"),
    "png_rendered": png_ok,
    "png_note": png_note,
}
rep_path = os.path.join(out_dir, "lda_2x2_ring_report.json")
with open(rep_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print("=== 走法一 真实版图产物（最小证明件）===")
print(f"GDS   : {gds_path}  ({len(gds_bytes)} bytes)")
print(f"组件数: {len(link.ir.components)}  ·  GDS 元素: {stats.get('n_elements')}")
print(f"DRC   : {'PASS' if drc.get('all_pass') else 'FAIL'}")
if not drc.get("all_pass"):
    for cid, v in drc.get("devices", {}).items():
        if not v.get("passed"):
            print(f"   - {cid}: {v.get('brief')}")
print(f"LVS   : {report['lvs_verdict']}")
if lvs.get("violations"):
    print(f"   违规: {json.dumps(lvs.get('violations'), ensure_ascii=False)}")
print(f"IO端口: {res.get('io_ports')}")
print(f"SVG   : {svg_path}")
print(f"PNG   : {png_path if png_ok else 'matplotlib 不可用：' + png_note}")
print(f"报告  : {rep_path}")
