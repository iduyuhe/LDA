# -*- coding: utf-8 -*-
"""E36 · **IP 级 DRC / LVS**（`lda/lda_l2/ecore/ddrc_lvs.py` · D-222 / D-223）。

══════════════════════════════════════════════════════════════
定位：E35 只做了「线载提取 + 线感知 STA」，IP 级 **可制造性检查为零**。本模块第一次
对合并后的金属几何做两层签核：

- **D-222 DRC（设计规则检查）**：最小线宽 / 最小间距（同层重叠或间距 < S_MIN）
  / 通孔包围。抓「画错但未短路」的几何违规。
- **D-223 LVS（版图-原理图对照）**：按几何 flood-fill 连通性，校验**每根网的引脚
  是否经金属互连成一体**；并检测**异网同层重叠（短路）**。抓「连错了 / 没连上」。

══════════════════════════════════════════════════════════════
🔴🔴 绝对金标（DRC）
══════════════════════════════════════════════════════════════
- 每条金属 min(宽,高) ≥ W_MIN（线宽够）
- 同层金属两两不重叠，且边到边间距 ≥ S_MIN（间距够）—— 把每条金属膨胀 S_MIN/2 后
  仍与同层他者重叠 = 违例（含短路与近距）
- 每个通孔被其桥接的两层金属各自「包围」：孔 inset ENC 后仍落在该层金属内

🔴🔴 绝对金标（LVS）
══════════════════════════════════════════════════════════════
- 每根网的全部布线形状（M3/M4/弯角孔）必须落在**同一个连通分量**（经重叠/flood-fill）
- 每根网的每个终端点（单元中心 / 端口落点）必须被**该网某形状覆盖**（确实连上）
- 任意两层**不同网**同层重叠 = 短路，必报

══════════════════════════════════════════════════════════════
⚠️ 诚实边界（全部 `claimable=False`）
══════════════════════════════════════════════════════════════
- **规则值是假设**（W_MIN/S_MIN/ENC 取自公开工艺近似，非 Foundry PDK）
- **仅金属层 M1/M3/M4 + 通孔层**参与；未检注入/阱/天线/密度等完整 DRC 规则集
- **LVS 只验布线连通性，不验器件匹配**：单元内部是黑盒，不查晶体管级 LVS
- **单角、无寄生提取驱动的二次违例**：这是「签核能力的雏形」，不是 Calibre/ICV 级
"""
from __future__ import annotations

from collections import defaultdict

from . import ddetail as DD
from . import dplac as PL

# ---- 规则假设（MODEL_ESTIMATE · 一阶）----
W_MIN = 0.10             # µm · 最小金属线宽
S_MIN = 0.10             # µm · 最小同层间距
ENC = 0.02              # µm · 通孔包围（金属比孔大出的单边量）

# 通孔桥接的层对（via layer -> [layer_a, layer_b]）
VIA_BRIDGE = {
    DD.L_VIA1: [DD.L_M1, DD.L_M2],   # M1 <-> M2
    DD.L_VIA2: [DD.L_M3, DD.L_M4],   # M3 <-> M4
}
# 桥接层中本征程实际会有的金属（M2 在数字区未画 ⇒ 跳过其包围检查，见披露）
BRIDGE_PRESENT = {DD.L_M1, DD.L_M3, DD.L_M4}


def run_drc(shapes: list, verbose: bool = False) -> dict:
    """对金属 + 通孔几何做 DRC。返回 violations 列表与统计。"""
    violations = []
    metals = [s for s in shapes if s.kind in ("metal", "pin")]
    vias = [s for s in shapes if s.kind == "via"]

    # ① 最小线宽：走线截面（窄边）≥ W_MIN。短 jumper（窄边=长度且长边≥3×W_MIN）
    #    视为着陆块，不判；真细线（长边≥3×W_MIN 且窄边<W_MIN）才判违例。
    for s in metals:
        w = s.x1 - s.x0
        h = s.y1 - s.y0
        if max(w, h) >= 3.0 * W_MIN and min(w, h) < W_MIN - 1e-9:
            violations.append(("min_width", s.layer, round(min(w, h), 4)))

    # ② 最小间距（同层膨胀 S_MIN/2 后重叠 = 违例）。🔴 同网金属可邻近/重叠（同一导体），
    #    只检**异网**同层（短路风险）。
    half = S_MIN / 2.0
    for i in range(len(metals)):
        for j in range(i + 1, len(metals)):
            a, b = metals[i], metals[j]
            if a.layer != b.layer or a.net == b.net:
                continue
            if DD.rects_overlap(a, b, inflate=half):
                violations.append(("min_spacing", a.layer,
                                   (round(a.x0, 3), round(a.y0, 3)),
                                   (round(b.x0, 3), round(b.y0, 3))))

    # ③ 通孔包围 / 悬空：仅当该桥接层确有金属与孔重叠时才要求包围（纯 H/纯 V 网的退化边
    #    只桥接一层，另一层无金属 ⇒ 跳过该层，避免误报）。若**两层都无金属与孔重叠** ⇒ 悬空孔。
    for v in vias:
        bridge = VIA_BRIDGE.get(v.layer)
        if bridge is None:
            continue
        ix0, iy0, ix1, iy1 = v.x0 + ENC, v.y0 + ENC, v.x1 - ENC, v.y1 - ENC
        if ix1 <= ix0 or iy1 <= iy0:
            violations.append(("via_not_enclosed_size", v.layer))
            continue
        touched_any = False
        for lay in bridge:
            if lay not in BRIDGE_PRESENT:
                continue  # 该桥接层未画金属（如 M2），跳过（披露）
            touching = [m for m in metals
                        if m.layer == lay and DD.rects_overlap(m, v, inflate=1e-6)]
            if not touching:
                continue  # 该层无金属与孔重叠 ⇒ 此孔不桥接该层，跳过
            touched_any = True
            ok = any((m.x0 <= ix0 and m.y0 <= iy0 and m.x1 >= ix1 and m.y1 >= iy1)
                     for m in touching)
            if not ok:
                violations.append(("via_enclosure", v.layer, lay))
        if not touched_any:
            violations.append(("via_floating", v.layer))

    if verbose:
        print("  drc: metals=%d vias=%d  violations=%d"
              % (len(metals), len(vias), len(violations)))
    return {
        "ok": len(violations) == 0, "violations": violations,
        "n_metals": len(metals), "n_vias": len(vias),
    }


def _union_find(shapes: list) -> list:
    """按**电气**连通性做并查集（非纯几何重叠）：

    - 同层金属重叠 ⇒ 连通（合并 / 短路）
    - 通孔与金属重叠 ⇒ 桥接（通孔把其两层金属连起来）
    - **异层金属即使矩形交叉也不连通**（无孔 = 无电气连接）——这是 LVS 的关键
    """
    n = len(shapes)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        si = shapes[i]
        for j in range(i + 1, n):
            sj = shapes[j]
            if si.kind == "via" and sj.kind == "metal":
                if DD.rects_overlap(si, sj, inflate=1e-6):
                    union(i, j)
            elif sj.kind == "via" and si.kind == "metal":
                if DD.rects_overlap(si, sj, inflate=1e-6):
                    union(i, j)
            elif si.kind == "metal" and sj.kind == "metal":
                if si.layer == sj.layer and DD.rects_overlap(si, sj, inflate=1e-6):
                    union(i, j)
            # 异层金属重叠：不连通（无孔），留给短路检测处理
    return [find(i) for i in range(n)]


def run_lvs(shapes: list, net_pins: dict, verbose: bool = False) -> dict:
    """版图-原理图对照：每网连通性 + 异网短路。"""
    routed = [s for s in shapes if s.net is not None and s.kind in ("metal", "via")]
    comp = _union_find(routed)

    # 每网形状 -> 分量集合
    net_comp = defaultdict(set)
    net_shapes = defaultdict(list)
    for idx, s in enumerate(routed):
        net_comp[s.net].add(comp[idx])
        net_shapes[s.net].append((idx, s))

    problems = []

    # ① 每网形状必须落在同一连通分量
    for net, comps in net_comp.items():
        if len(comps) > 1:
            problems.append(("net_disconnected", net, len(comps)))

    # ② 每网终端点必须被该网某形状覆盖
    for net, pts in net_pins.items():
        if net not in net_shapes:
            # 单端网（仅出现在端口或单驱动）—— 无布线形状，跳过连通检查
            if len(pts) >= 2:
                problems.append(("net_no_shapes", net))
            continue
        for (px, py) in pts:
            covered = any(DD.point_in_rect(px, py, s) for (_i, s) in net_shapes[net])
            if not covered:
                problems.append(("pin_not_reached", net, round(px, 3), round(py, 3)))

    # ③ 短路检测
    metals = [s for s in routed if s.kind == "metal"]
    vias = [s for s in routed if s.kind == "via"]
    # ③a 异网同层金属重叠 = 短路
    for i in range(len(metals)):
        for j in range(i + 1, len(metals)):
            a, b = metals[i], metals[j]
            if a.layer != b.layer or a.net == b.net:
                continue
            if DD.rects_overlap(a, b, inflate=1e-6):
                problems.append(("short", a.net, b.net, a.layer))
    # ③b 异网通孔压在异网金属上 = 跨网连接短路
    for v in vias:
        for m in metals:
            if m.net == v.net or v.net is None or m.net is None:
                continue
            if DD.rects_overlap(v, m, inflate=1e-6):
                problems.append(("short_via", v.net, m.net, m.layer))

    if verbose:
        print("  lvs: nets_checked=%d  problems=%d"
              % (len(net_shapes), len(problems)))
    return {
        "ok": len(problems) == 0, "problems": problems,
        "n_nets": len(net_shapes),
    }


# ---------------------------------------------------------------------------
# 快速版（空间哈希，避免大布局 O(n^2) 超时）：供 track_route / 自检 / 门禁使用
# ---------------------------------------------------------------------------
def _cell_span(s, cell):
    gx0 = int(s.x0 / cell); gx1 = int(s.x1 / cell)
    gy0 = int(s.y0 / cell); gy1 = int(s.y1 / cell)
    return gx0, gx1, gy0, gy1


def _index_bbox(shapes, cell):
    grid = {}
    for i, s in enumerate(shapes):
        gx0, gx1, gy0, gy1 = _cell_span(s, cell)
        gx0 = max(gx0, -100000); gx1 = min(gx1, 100000)
        gy0 = max(gy0, -100000); gy1 = min(gy1, 100000)
        for gx in range(gx0, gx1 + 1):
            for gy in range(gy0, gy1 + 1):
                grid.setdefault((gx, gy), []).append(i)
    return grid


def fast_drc(shapes, verbose: bool = False) -> dict:
    """`run_drc` 的空间哈希加速版（包围盒登记），结果应逐位一致。

    🔴 金属段可能很长（跨多个 µm），不能只按中心格索引——否则中心离过孔/端点很远、
    邻域永远看不到重叠。改为把每个 shape 登记进其包围盒覆盖的全部网格；查询取其包围盒
    覆盖格 + 1 环。
    """
    metals = [s for s in shapes if s.kind in ("metal", "pin")]
    vias = [s for s in shapes if s.kind == "via"]
    violations = []
    for s in metals:
        w = s.x1 - s.x0; h = s.y1 - s.y0
        if max(w, h) >= 3.0 * W_MIN and min(w, h) < W_MIN - 1e-9:
            violations.append(("min_width", s.layer, round(min(w, h), 4)))
    half = S_MIN / 2.0
    cell = max(DD.W_ROUTE, DD.VIA) + S_MIN + 0.05
    grid = _index_bbox(metals, cell)
    seen = set()
    for i, a in enumerate(metals):
        gx0, gx1, gy0, gy1 = _cell_span(a, cell)
        cand = set()
        for gx in range(gx0 - 1, gx1 + 2):
            for gy in range(gy0 - 1, gy1 + 2):
                cand.update(grid.get((gx, gy), ()))
        for j in cand:
            if j <= i or (i, j) in seen:
                continue
            seen.add((i, j))
            b = metals[j]
            if a.layer != b.layer or a.net == b.net:
                continue
            if DD.rects_overlap(a, b, inflate=half):
                violations.append(("min_spacing", a.layer,
                                   (round(a.x0, 3), round(a.y0, 3)),
                                   (round(b.x0, 3), round(b.y0, 3))))
    for v in vias:
        bridge = VIA_BRIDGE.get(v.layer)
        if bridge is None:
            continue
        ix0, iy0, ix1, iy1 = v.x0 + ENC, v.y0 + ENC, v.x1 - ENC, v.y1 - ENC
        if ix1 <= ix0 or iy1 <= iy0:
            violations.append(("via_not_enclosed_size", v.layer))
            continue
        touched_any = False
        for lay in bridge:
            if lay not in BRIDGE_PRESENT:
                continue
            touching = [m for m in metals
                        if m.layer == lay and DD.rects_overlap(m, v, inflate=1e-6)]
            if not touching:
                continue
            touched_any = True
            ok = any((m.x0 <= ix0 and m.y0 <= iy0 and m.x1 >= ix1 and m.y1 >= iy1)
                     for m in touching)
            if not ok:
                violations.append(("via_enclosure", v.layer, lay))
        if not touched_any:
            violations.append(("via_floating", v.layer))
    if verbose:
        print("  fast_drc: metals=%d vias=%d violations=%d"
              % (len(metals), len(vias), len(violations)))
    return {"ok": len(violations) == 0, "violations": violations,
            "n_metals": len(metals), "n_vias": len(vias)}


def fast_lvs(shapes, net_pins: dict, verbose: bool = False) -> dict:
    """`run_lvs` 的空间哈希加速版（包围盒登记）。"""
    routed = [s for s in shapes if s.net is not None and s.kind in ("metal", "via")]
    cell = max(DD.W_ROUTE, DD.VIA) + S_MIN + 0.05
    grid = _index_bbox(routed, cell)
    n = len(routed)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    seen = set()
    for i, s in enumerate(routed):
        gx0, gx1, gy0, gy1 = _cell_span(s, cell)
        cand = set()
        for gx in range(gx0 - 1, gx1 + 2):
            for gy in range(gy0 - 1, gy1 + 2):
                cand.update(grid.get((gx, gy), ()))
        for j in cand:
            if j <= i or (i, j) in seen:
                continue
            seen.add((i, j))
            t = routed[j]
            if s.kind == "via" and t.kind == "metal":
                if DD.rects_overlap(s, t, inflate=1e-6):
                    union(i, j)
            elif t.kind == "via" and s.kind == "metal":
                if DD.rects_overlap(s, t, inflate=1e-6):
                    union(i, j)
            elif s.kind == "metal" and t.kind == "metal":
                if s.layer == t.layer and DD.rects_overlap(s, t, inflate=1e-6):
                    union(i, j)
    comp = [find(i) for i in range(n)]
    net_comp = defaultdict(set)
    net_shapes = defaultdict(list)
    for idx, s in enumerate(routed):
        net_comp[s.net].add(comp[idx])
        net_shapes[s.net].append((idx, s))
    problems = []
    for net, comps in net_comp.items():
        if len(comps) > 1:
            problems.append(("net_disconnected", net, len(comps)))
    for net, pts in net_pins.items():
        if net not in net_shapes:
            if len(pts) >= 2:
                problems.append(("net_no_shapes", net))
            continue
        for (px, py) in pts:
            covered = any(DD.point_in_rect(px, py, s) for (_i, s) in net_shapes[net])
            if not covered:
                problems.append(("pin_not_reached", net, round(px, 3), round(py, 3)))
    metals = [s for s in routed if s.kind == "metal"]
    # 🔴 独立 metals 网格：i/j 必须同为 metals 下标（此前误用 routed 网格 ⇒ 下标空间错配
    #    致 j<=i 失效、金属-金属短路被重复计数）
    mgrid = _index_bbox(metals, cell)
    seen2 = set()
    for i, a in enumerate(metals):
        gx0, gx1, gy0, gy1 = _cell_span(a, cell)
        cand = set()
        for gx in range(gx0 - 1, gx1 + 2):
            for gy in range(gy0 - 1, gy1 + 2):
                cand.update(mgrid.get((gx, gy), ()))
        for j in cand:
            if j <= i or (i, j) in seen2:
                continue
            seen2.add((i, j))
            b = metals[j]
            if a.layer != b.layer or a.net == b.net:
                continue
            if DD.rects_overlap(a, b, inflate=1e-6):
                problems.append(("short", a.net, b.net, a.layer))
    # ③b 异网通孔压在异网金属上 = 跨网连接短路（与 run_lvs 同口径；此前 fast 版漏检）
    for vi, v in enumerate(routed):
        if v.kind != "via":
            continue
        gx0, gx1, gy0, gy1 = _cell_span(v, cell)
        cand = set()
        for gx in range(gx0 - 1, gx1 + 2):
            for gy in range(gy0 - 1, gy1 + 2):
                cand.update(grid.get((gx, gy), ()))
        for j in cand:
            m = routed[j]
            if m.kind != "metal":
                continue
            if m.net == v.net or v.net is None or m.net is None:
                continue
            if DD.rects_overlap(v, m, inflate=1e-6):
                problems.append(("short_via", v.net, m.net, m.layer))
    if verbose:
        print("  fast_lvs: nets_checked=%d problems=%d"
              % (len(net_shapes), len(problems)))
    return {"ok": len(problems) == 0, "problems": problems,
            "n_nets": len(net_shapes)}


# ---------------------------------------------------------------------------
# 自检（含「必须失败」的对照组）
# ---------------------------------------------------------------------------
def drc_self_check(verbose: bool = False) -> dict:
    """校验 DRC checker 有判别力（突变探针必打红）；如实报告当前简化路由器的违例数。

    ⚠️ 基线（trivial L 路由）存在大量同层间距违例是**已知诚实事实**（无 track 分配），
    不因此判红；判红只针对「checker 抓不住注入故障」。
    """
    from . import dctrl as C
    problems = []
    b = C.build()
    nl = b["netlist"]
    p = PL.place(nl)
    dr = DD.detail_route(nl, p)
    res = run_drc(dr.shapes, verbose=verbose)

    # 🔴 对照组 1：注入一条过窄金属（0.05 < W_MIN 0.10）⇒ DRC 必须抓红
    h = next((s for s in dr.shapes if s.layer == DD.L_M3 and
              (s.x1 - s.x0) >= 3.0 * W_MIN), None)
    if h is not None:
        bad = list(dr.shapes)
        bad.append(DD._rect(DD.L_M3, h.x0, h.y0, h.x1, h.y0 + 0.05,
                            net="__bad__", kind="metal"))
        r2 = run_drc(bad)
        if not any(v[0] == "min_width" for v in r2["violations"]):
            problems.append(("control_narrow_not_red",))
    else:
        problems.append(("control_no_h_segment",))

    # 🔴 对照组 2：注入一条与现有 H 段重叠的金属（间距违例）⇒ DRC 必须抓红
    if h is not None:
        bad2 = list(dr.shapes)
        bad2.append(DD._rect(DD.L_M3, h.x0, h.y0 - 0.02, h.x1, h.y0 + W_MIN - 0.02,
                             net="__bad2__", kind="metal"))
        r3 = run_drc(bad2)
        if not any(v[0] == "min_spacing" for v in r3["violations"]):
            problems.append(("control_spacing_not_red",))

    # 🔴 对照组 3：注入一个不被任何金属包围的悬空通孔 ⇒ DRC 必须抓红
    bad3 = list(dr.shapes)
    bad3.append(DD._rect(DD.L_VIA2, 999.0, 999.0, 999.0 + DD.VIA, 999.0 + DD.VIA,
                         net="__badvia__", kind="via"))
    r4 = run_drc(bad3)
    if not any(v[0] == "via_floating" for v in r4["violations"]):
        problems.append(("control_floating_via_not_red",))

    return {"ok": not problems, "problems": problems,
            "baseline_ok": res["ok"], "baseline_violations": len(res["violations"])}


def lvs_self_check(verbose: bool = False) -> dict:
    """校验 LVS checker 有判别力（突变探针必打红）；如实报告当前简化路由器的短路/断连数。

    ⚠️ 基线（trivial L 路由）存在大量异网同层重叠（短路）是**已知诚实事实**，
    不因此判红；判红只针对「checker 抓不住注入故障」。
    """
    from . import dctrl as C
    problems = []
    b = C.build()
    nl = b["netlist"]
    p = PL.place(nl)
    dr = DD.detail_route(nl, p)
    res = run_lvs(dr.shapes, dr.net_pins, verbose=verbose)

    # 🔴 对照组 1：断开某 2 端网的 M3 布线 ⇒ 靠 M3 到达的引脚失连 ⇒ LVS 必须抓红
    #   （删段比删孔更可靠：多通孔网删单孔未必断网；删整层段必使该层引脚失连）
    target = None
    for net, pts in dr.net_pins.items():
        if len(pts) == 2:
            target = net
            break
    if target is not None:
        has_m3 = any(s.net == target and s.layer == DD.L_M3 for s in dr.shapes)
        if has_m3:
            bad = [s for s in dr.shapes
                   if not (s.net == target and s.layer == DD.L_M3)]
            r2 = run_lvs(bad, dr.net_pins)
            caught = any(pr[0] in ("net_disconnected", "pin_not_reached")
                         and len(pr) > 1 and pr[1] == target
                         for pr in r2["problems"])
            if not caught:
                problems.append(("control_via_break_not_red",))
        else:
            problems.append(("control_no_m3",))
    else:
        problems.append(("control_no_two_pin_net",))

    # 🔴 对照组 2：注入异网同层重叠（短路）⇒ LVS 必须抓红
    h = next((s for s in dr.shapes if s.layer == DD.L_M3 and
              (s.x1 - s.x0) >= 3.0 * W_MIN), None)
    if h is not None:
        bad3 = list(dr.shapes)
        bad3.append(DD._rect(DD.L_M3, h.x0, h.y0 + 0.01, h.x1, h.y0 + 0.01 + DD.W_ROUTE,
                             net="__short__", kind="metal"))
        r3 = run_lvs(bad3, dr.net_pins)
        if not any(pr[0] == "short" for pr in r3["problems"]):
            problems.append(("control_short_not_red",))
    else:
        problems.append(("control_no_metal",))

    return {"ok": not problems, "problems": problems,
            "baseline_ok": res["ok"], "baseline_problems": len(res["problems"])}


def checker_equiv_self_check(verbose: bool = False) -> dict:
    """E37 · 校验器硬化：`fast_drc`/`fast_lvs` 与原生 O(n²) `run_drc`/`run_lvs` **逐位一致**。

    两道等价金标（baseline 真实几何上）：
      - DRC：总数 + 按类 breakdown 完全相同；
      - LVS：总数 + 按类 breakdown 完全相同（含 short_via 与金属-金属短路去重）。
    两个判别式（防 fast 版静默变瞎子）：注入窄金属 / 悬空过孔 ⇒ fast_drc 必红。
    """
    from collections import Counter
    from . import dctrl as C
    problems = []
    b = C.build()
    nl = b["netlist"]
    p = PL.place(nl)
    base = DD.detail_route(nl, p)

    rd = run_drc(base.shapes)
    fd = fast_drc(base.shapes)
    if len(rd["violations"]) != len(fd["violations"]):
        problems.append(("drc_count_mismatch", len(rd["violations"]), len(fd["violations"])))
    if Counter(v[0] for v in rd["violations"]) != Counter(v[0] for v in fd["violations"]):
        problems.append(("drc_breakdown_mismatch",))

    rl = run_lvs(base.shapes, base.net_pins)
    fl = fast_lvs(base.shapes, base.net_pins)
    if len(rl["problems"]) != len(fl["problems"]):
        problems.append(("lvs_count_mismatch", len(rl["problems"]), len(fl["problems"])))
    if Counter(pr[0] for pr in rl["problems"]) != Counter(pr[0] for pr in fl["problems"]):
        problems.append(("lvs_breakdown_mismatch",))

    # 判别式 1：注入窄金属 ⇒ fast_drc 必红 min_width
    h = next((s for s in base.shapes if s.layer == DD.L_M3 and
              (s.x1 - s.x0) >= 3.0 * W_MIN), None)
    if h is not None:
        bad = list(base.shapes)
        bad.append(DD._rect(DD.L_M3, h.x0, h.y0, h.x1, h.y0 + 0.05,
                            net="__bad__", kind="metal"))
        if not any(v[0] == "min_width" for v in fast_drc(bad)["violations"]):
            problems.append(("probe_narrow_not_red",))
    else:
        problems.append(("probe_no_h_segment",))

    # 判别式 2：注入悬空过孔 ⇒ fast_drc 必红 via_floating
    bad2 = list(base.shapes)
    bad2.append(DD._rect(DD.L_VIA2, 9999.0, 9999.0, 9999.0 + DD.VIA, 9999.0 + DD.VIA,
                         net="__badvia__", kind="via"))
    if not any(v[0] == "via_floating" for v in fast_drc(bad2)["violations"]):
        problems.append(("probe_floating_via_not_red",))

    if verbose:
        print("  checker_equiv: drc run=%d fast=%d  lvs run=%d fast=%d"
              % (len(rd["violations"]), len(fd["violations"]),
                 len(rl["problems"]), len(fl["problems"])))
    return {"ok": not problems, "problems": problems,
            "baseline_drc": len(rd["violations"]),
            "baseline_lvs": len(rl["problems"]),
            "drc_breakdown": dict(Counter(v[0] for v in rd["violations"])),
            "lvs_breakdown": dict(Counter(pr[0] for pr in rl["problems"]))}


DDRC_LVS_DISCLOSURE = {
    "route": "E36 · P&R 深化 第 2 刀 · D-222 DRC + D-223 LVS",
    "analysis": "合并金属几何 → 最小线宽/最小间距/通孔包围(DRC) + 几何 flood-fill 连通性"
                "(LVS：每网引脚互连成体 + 异网同层短路)",
    "golden": "DRC：线宽≥W_MIN · 同层间距≥S_MIN · 通孔被桥接层包围；"
              "LVS：每网布线单分量 · 终端点被该网覆盖 · 无异网同层重叠",
    "not_included": "规则值假设(非 PDK) · 仅 M1/M3/M4+通孔 · 未检注入/阱/天线/密度 · "
                    "LVS 只验布线不验器件匹配 · 单角",
    "claimable": False,
    "claimable_reason": "DRC/LVS 是几何机核；可 signoff 的是「几何无违规/连通正确」，"
                       "其**规则阈值**仍 MODEL_ESTIMATE",
}
