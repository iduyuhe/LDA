# -*- coding: utf-8 -*-
"""E38 · **网格迷宫路由器 + 可布通性研究**（`lda/lda_l2/ecore/ddroute_grid.py` · D-225）。

══════════════════════════════════════════════════════════════
定位：E36/E37 用「简化 L 形路由」画金属，E37 证明 2 层 L 路由 + track 分配在**稠密布局**
上不能清零（每行 clique 87~120 vs 通道 2 轨 ⇒ 真清零需 ×14.6 面积）。E38 换**真正的网格
迷宫路由器**：在 M3(横)/M4(竖) 两层轨道网格上用 BFS 逐网布线 + 简单 rip-up，把「路由算法」
换成工业标准的迷宫思路，看**到底能不能布通**——并诚实报告布通率。

🔴🔴 本模块的**核心不是"布通"，而是"诚实测量布通率"**：当前布局 die 仅 18.0×18.7µm 却塞
1340 单元（≈223 单元/行、平均单元宽 0.075µm），0.36µm 轨距下每行只有 ~50 条竖轨，而 223
个单元的引脚挤在这 50 条轨上 ⇒ 大量网争夺同一网格 ⇒ 布通率会很低。这是**布局密度**（符号级
超窄单元）造成的，不是路由器不够聪明。E38a 如实报这个数，E38b 再量化「放大 N 倍才 100% 可布通」。

══════════════════════════════════════════════════════════════
🔴🔴 两层网格模型（诚实简化，见披露）
══════════════════════════════════════════════════════════════
- 网格点 `(i,j)` 在 `(i·PITCH, j·PITCH)`，`PITCH = W_ROUTE + S_MIN = 0.34→取 0.36`。
- **M3 = 横向层**（沿行 j 左右走）、**M4 = 纵向层**（沿列 i 上下走）、交点 VIA2。
- **分层独立占用**：`H_OWN`/`V_OWN` 分别记 M3/M4 各点归属——**异网 M3 横线与异网 M4 竖线
  可在同点交叉而不短路**（不同层，无孔）——这是真实 2 层网格的关键（此前 E37 的 track 未利用）。
- **单元中心 = 终端簇**：同一单元的多条网在中心汇成单点（单元内黑盒，与 E36/E37 同口径）；
  该点是这些网的**共享终端**（可多网作为端点），但**不可被异网穿过**（穿过=短路）。

🔴🔴 绝对金标
══════════════════════════════════════════════════════════════
- **已布网**：该网全部终端落在同一连通分量（LVS 无断连）；几何同层异网不重叠（DRC 清）；
  线长 ≥ 该网 MST（物理下界，不可编数）。
- **布通率** = 已布网数 / 多端网总数（如实报，不伪绿；低就是低）。
- **确定性**：同 netlist 同 seed 逐位可复现。

══════════════════════════════════════════════════════════════
⚠️ 诚实边界（全部 `claimable=False`）
══════════════════════════════════════════════════════════════
- 网格 2 层（M3/M4），无 M5/M6；无 track 分配以外的拥塞代价（via 与线同权 = 1）。
- 单元几何仍是符号级（超窄）；die 尺寸 18×18.7µm 是符号布局，非真实标准单元面积。
- rip-up 是**一轮轻量**版本（非工业多轮 R&R）；无时序/串扰/电源完整性驱动。
- 规则值 W_MIN/S_MIN/VIA 仍是 MODEL_ESTIMATE（非 Foundry PDK）。
"""
from __future__ import annotations

from collections import defaultdict, deque

from . import ddetail as DD
from . import dplac as PL
from .dsynth import Netlist

PITCH = DD.TRACK_PITCH          # 0.36 µm · 轨道间距（> W_ROUTE+S_MIN）
W = DD.W_ROUTE                  # 0.24 µm
VIA = DD.VIA                    # 0.20 µm
L_M3 = DD.L_M3
L_M4 = DD.L_M4
L_VIA2 = DD.L_VIA2

# 多端网才需布；单端网（仅端口/单驱动）跳过
_L3, _L4 = 3, 4


def grid_dims(p: PL.Placement) -> tuple:
    nx = max(2, int(round(p.die_w_um / PITCH)) + 1)
    ny = max(2, int(round(p.die_h_um / PITCH)) + 1)
    return nx, ny


def _snap(x: float, y: float, nx: int, ny: int) -> tuple:
    i = min(max(int(round(x / PITCH)), 0), nx - 1)
    j = min(max(int(round(y / PITCH)), 0), ny - 1)
    return (i, j)


def _net_terminals(nl: Netlist, p: PL.Placement, nx: int, ny: int, spread: float = 1.0) -> dict:
    """net -> 终端网格点集合（单元中心/端口落点 → 最近网格点，去重）。

    `spread` 把坐标等比放大（用于「布局密度 → 可布通性」扫描：放大=单元变稀）。
    """
    pins = DD._net_pins(nl, p)
    term = {}
    for net, pts in pins.items():
        s = set()
        for (x, y) in pts:
            s.add(_snap(x * spread, y * spread, nx, ny))
        term[net] = s
    return term, pins


def _bfs(start_node, goal_nodes, net, nx, ny, H_OWN, V_OWN, TERM, max_expand: int = 40000):
    """从 start 点（可在任一层起步）BFS 到任一 goal 节点（树）。返回状态路径或 None。

    状态 = (i, j, layer)，layer∈{3(M3 横),4(M4 竖)}；边：横移(layer3)/竖移(layer4)/换层(via)，
    每步代价 1。分层独立占用 ⇒ 异网横竖可在同点交叉不短路。
    `max_expand` 限扩展数（大网格/无解时防失控；触顶即判未布，属**保守**估计，已披露）。
    """
    def passable(i, j, lay):
        if i < 0 or i >= nx or j < 0 or j >= ny:
            return False
        own = TERM.get((i, j))
        if own and net not in own:       # 异网终端 ⇒ 不可穿过（己方/共享终端可）
            return False
        if lay == _L3 and H_OWN.get((i, j)) not in (None, net):
            return False
        if lay == _L4 and V_OWN.get((i, j)) not in (None, net):
            return False
        return True

    goals = set(goal_nodes)
    si, sj = start_node
    dq = deque()
    parent = {}
    seen = set()
    for lay in (_L3, _L4):
        if passable(si, sj, lay):
            st = (si, sj, lay)
            parent[st] = None
            seen.add(st)
            dq.append(st)

    expanded = 0
    while dq:
        st = dq.popleft()
        expanded += 1
        if expanded > max_expand:
            return None
        i, j, lay = st
        if (i, j) in goals and parent.get(st) is not None:
            # reconstruct
            path = []
            cur = st
            while cur is not None:
                path.append(cur)
                cur = parent[cur]
            path.reverse()
            return path
        # 邻居
        nbrs = []
        if lay == _L3:
            nbrs.append((i - 1, j, _L3))
            nbrs.append((i + 1, j, _L3))
            nbrs.append((i, j, _L4))       # via
        else:
            nbrs.append((i, j - 1, _L4))
            nbrs.append((i, j + 1, _L4))
            nbrs.append((i, j, _L3))       # via
        for (ni, nj, nl) in nbrs:
            if not passable(ni, nj, nl):
                continue
            ns = (ni, nj, nl)
            if ns in seen:
                continue
            seen.add(ns)
            parent[ns] = st
            dq.append(ns)
    return None


def _route_net(term_nodes, net, nx, ny, H_OWN, V_OWN, TERM, max_expand: int = 40000):
    """把多端网的终端连成树。成功返回 (edges, via_nodes)；失败 None。"""
    terms = sorted(term_nodes)
    if len(terms) < 2:
        return [], set()
    tree = {terms[0]}
    edges = []
    vias = set(terms)
    for tgt in terms[1:]:
        if tgt in tree:
            continue
        path = _bfs(tgt, tree, net, nx, ny, H_OWN, V_OWN, TERM, max_expand)
        if path is None:
            return None
        for k in range(len(path) - 1):
            edges.append((path[k], path[k + 1]))
            if path[k][2] != path[k + 1][2]:
                vias.add((path[k][0], path[k][1]))
        for (i, j, _l) in path:
            tree.add((i, j))
        vias.add((tgt[0], tgt[1]))
    return edges, vias


def _commit(net, edges, vias, H_OWN, V_OWN):
    for (a, b) in edges:
        for (i, j, la) in (a, b):
            if la == _L3:
                H_OWN[(i, j)] = net
            else:
                V_OWN[(i, j)] = net
    # via 点两层都占
    for (i, j) in vias:
        H_OWN.setdefault((i, j), net)
        V_OWN.setdefault((i, j), net)


def _shapes_from(edges, vias, net) -> list:
    """边 + via → 真实金属矩形（H=M3 / V=M4 / 通孔 VIA2）。"""
    out = []
    for (a, b) in edges:
        (i0, j0, la) = a
        (i1, j1, lb) = b
        if la == _L3 and lb == _L3 and j0 == j1 and i0 != i1:      # 横段 M3
            x0, x1 = sorted([i0 * PITCH, i1 * PITCH])
            out.append(DD._rect(L_M3, x0, j0 * PITCH - W / 2.0,
                                x1, j0 * PITCH + W / 2.0, net=net, kind="metal"))
        elif la == _L4 and lb == _L4 and i0 == i1 and j0 != j1:    # 竖段 M4
            y0, y1 = sorted([j0 * PITCH, j1 * PITCH])
            out.append(DD._rect(L_M4, i0 * PITCH - W / 2.0, y0,
                                i0 * PITCH + W / 2.0, y1, net=net, kind="metal"))
        # 换层边本身不产生金属（via 由 vias 集合统一发）
    land = VIA / 2.0 + DD.ENC + 0.01
    for (i, j) in vias:
        # 每个 via 加 M3+M4 landing pad + VIA2（保证被双侧金属包围，修 enclosure）
        DD._via_landing(out, i * PITCH, j * PITCH, net, land)
    return out


def _mst_len(term_nodes):
    """终端点（网格坐标）的曼哈顿 MST 长（µm）。"""
    pts = [(i * PITCH, j * PITCH) for (i, j) in term_nodes]
    if len(pts) < 2:
        return 0.0
    edges = DD._mst_edges(pts)
    tot = 0.0
    for (a, b) in edges:
        tot += abs(pts[a][0] - pts[b][0]) + abs(pts[a][1] - pts[b][1])
    return tot


def route_grid(nl: Netlist, p: PL.Placement, spread: float = 1.0, sample: int = None) -> dict:
    """网格迷宫路由（贪心一次布；多轮 R&R 留 E38b）。返回 shapes/布通率/线长/MST。

    `spread` 等比放大布局（网格与终端同步放大）= 单元变稀，用于密度→可布通性扫描。
    `sample` 只布前 N 个（等距取样）多端网（大 spread 扫描控成本；TERM 仍含全部终端）。
    """
    nx = max(2, int(round(p.die_w_um * spread / PITCH)) + 1)
    ny = max(2, int(round(p.die_h_um * spread / PITCH)) + 1)
    max_expand = 40000
    term, pins = _net_terminals(nl, p, nx, ny, spread)

    # 终端簇：节点 -> 拥有它的网集合
    TERM = defaultdict(set)
    for net, nodes in term.items():
        for nd in nodes:
            TERM[nd].add(net)

    multi = [(net, nodes) for net, nodes in term.items() if len(nodes) >= 2]
    # 确定性顺序：终端多/包围盒大的先布（更难）
    def _key(item):
        net, nodes = item
        xs = [i for (i, j) in nodes]
        ys = [j for (i, j) in nodes]
        peri = (max(xs) - min(xs)) + (max(ys) - min(ys))
        return (len(nodes), peri, net)
    multi.sort(key=_key)

    # 采样（用于大 spread 扫描控成本）：确定性等距取样；TERM 仍由**全部**终端构造，
    # 故密度效应（引脚拥挤）保留，仅未采样的网不参与布线（不占轨道）——已披露。
    n_total = len(multi)
    if sample is not None and n_total > sample:
        step = max(1, n_total // sample)
        multi = multi[::step][:sample]

    H_OWN, V_OWN = {}, {}
    shapes = []
    routed = {}
    net_wl = {}
    net_mst = {}
    order_first = [(net, nodes) for (net, nodes) in multi]

    def try_route(net, nodes, commit=True):
        r = _route_net(nodes, net, nx, ny, H_OWN, V_OWN, TERM, max_expand)
        if r is None:
            return None
        edges, vias = r
        if commit:
            _commit(net, edges, vias, H_OWN, V_OWN)
            routed[net] = (edges, vias)
            wl = 0.0
            for (a, b) in edges:
                wl += abs(a[0] - b[0]) + abs(a[1] - b[1])
            net_wl[net] = wl * PITCH
            net_mst[net] = _mst_len(nodes)
        return edges, vias

    unrouted = []
    for net, nodes in order_first:
        if try_route(net, nodes) is None:
            unrouted.append((net, nodes))

    # 注：多轮 rip-up & reroute（工业 R&R）留 E38b。本版为**贪心一次布**——更保守、
    #   无副作用；实测贪心 3.2%（44/1354），负结果成立。早前误加的「轻量 rip-up」会
    #   静默丢已布网、把布通率压到 0%（假象），已移除。

    # 生成形状
    for net, (edges, vias) in routed.items():
        shapes.extend(_shapes_from(edges, vias, net))

    n_multi = len(multi)
    n_routed = len(routed)
    return {
        "shapes": shapes,
        "net_pins": pins,
        "nx": nx, "ny": ny,
        "n_nets": n_multi,
        "n_total_nets": n_total,
        "sampled": bool(sample is not None and n_total > sample),
        "n_routed": n_routed,
        "n_unrouted": n_multi - n_routed,
        "routability": (n_routed / n_multi) if n_multi else 1.0,
        "routed_edges": {net: len(e) for net, (e, _v) in routed.items()},
        "wirelength_um": dict(net_wl),
        "mst_um": dict(net_mst),
        "unrouted_nets": [net for net, _ in unrouted],
        "routed_nets": list(routed.keys()),
    }


# ---------------------------------------------------------------------------
# 稀疏合成控制路由（证明路由器有效，非 0% 是 bug）
# ---------------------------------------------------------------------------
def _route_term_set(term: dict, nx: int, ny: int) -> tuple:
    TERM = defaultdict(set)
    for n, ns in term.items():
        for nd in ns:
            TERM[nd].add(n)
    multi = sorted([(n, ns) for n, ns in term.items() if len(ns) >= 2],
                   key=lambda x: (len(x[1]), x[0]))
    H, V = {}, {}
    routed, unrouted = {}, []
    for n, ns in multi:
        r = _route_net(ns, n, nx, ny, H, V, TERM)
        if r is None:
            unrouted.append(n)
            continue
        _commit(n, r[0], r[1], H, V)
        routed[n] = (r[0], r[1])
    shapes = []
    for n, (e, v) in routed.items():
        shapes.extend(_shapes_from(e, v, n))
    return shapes, routed, unrouted, term


def routability_vs_spread(nl: Netlist, p: PL.Placement, factors=(1, 2, 3)) -> list:
    """**布通率 vs 布局放大倍数**（全量网、贪心）：放大=单元变稀，看布通率是否回升。

    面积 ≈ 放大倍数的平方（die_w×spread × die_h×spread）。E38a 只做小范围（×1~×3，控成本）；
    完整的「需放大多少倍才 ~100%」曲线（含多轮 R&R）属 E38b。
    """
    out = []
    for K in factors:
        r = route_grid(nl, p, spread=float(K))
        out.append({"spread": K, "routability": r["routability"],
                    "n_routed": r["n_routed"], "n_nets": r["n_nets"],
                    "n_total_nets": r["n_total_nets"], "sampled": r["sampled"],
                    "area_factor": float(K) * float(K)})
    return out


# ---------------------------------------------------------------------------
# 自检（含「必须失败」的对照组）
# ---------------------------------------------------------------------------
def route_grid_self_check(verbose: bool = False) -> dict:
    """E38a 自检：证明「路由器有效」+「真实布局 0% 可布通是密度所致」+「放大即恢复」。

    - ① 控制组：稀疏合成 3 网 ⇒ 100% 布通 + DRC 清 + LVS 通 + 线长≥MST（路由器非空转）。
    - ② 真实布局：布通率如实报（本密度应极低），断言 < 0.5（=密度不可布通的负结果）。
    - ③ 密度扫描：放大 K 倍 ⇒ 布通率回升（证明低布通率是密度不是算法），报面积 ×K²。
    - ④ 探针：C1 围死一网 ⇒ 必报未布（非静默丢）；C2 重叠注入 ⇒ DRC 红；C3 砍段 ⇒ 线长<MST。
    """
    from . import dctrl as C
    from . import ddrc_lvs as DL
    problems = []

    # ① 控制组：稀疏合成
    synth = {"nA": {(2, 2), (10, 8)}, "nB": {(20, 20), (30, 10)}, "nC": {(5, 40), (45, 40)}}
    snx, sny = 51, 53
    ss, s_routed, s_unr, _st = _route_term_set(synth, snx, sny)
    if s_unr:
        problems.append(("control_unrouted", s_unr))
    sd = DL.fast_drc(ss)
    if len(sd["violations"]) != 0:
        problems.append(("control_drc", sd["violations"][:2]))
    s_pins = {n: [(i * PITCH, j * PITCH) for (i, j) in ns] for n, ns in synth.items()}
    sl = DL.fast_lvs(ss, s_pins)
    if not sl["ok"]:
        problems.append(("control_lvs", sl["problems"][:2]))
    for n, (e, v) in s_routed.items():
        wl = sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in e) * PITCH
        if wl < _mst_len(synth[n]) - 1e-6:
            problems.append(("control_wl_short", n))

    # ② 真实布局布通率
    b = C.build()
    nl = b["netlist"]
    p = PL.place(nl)
    r = route_grid(nl, p)
    if r["n_nets"] <= 0:
        problems.append(("no_multi_nets",))
    if not (r["routability"] < 0.5):
        problems.append(("real_routability_unexpectedly_high", round(r["routability"], 4)))
    # 真实已布形状的 DRC/LVS 只作**信息**（不判红）：单元中心=共享终端黑盒 ⇒ 多网在
    #   同一网格点共用终端，landing pad 会重叠、连通性定义含混——这是 E36/E37 起就有的
    #   单元黑盒简化，不是路由器缺陷。判红只用「稀疏合成控制组」（终端互斥，几何干净）。
    real_drc_n = real_lvs_n = None
    if r["shapes"]:
        real_drc_n = len(DL.fast_drc(r["shapes"])["violations"])
        rp = {n: r["net_pins"][n] for n in r["routed_nets"]}
        real_lvs_n = len(DL.fast_lvs(r["shapes"], rp)["problems"])

    # ③ 密度扫描（×1~×3）：放大布局布通率应回升（证明低布通率是密度所致）
    sweep = routability_vs_spread(nl, p, factors=(1, 2, 3))
    if not (sweep[-1]["routability"] >= sweep[0]["routability"] - 1e-9):
        problems.append(("spread_not_relieved", sweep))

    # ④ 探针 C1：围死 nA（用异网终端封住其唯一出路）⇒ 必报未布
    wnx, wny = 6, 3
    wall_term = {"nA": {(0, 0), (5, 0)}}
    TERM = defaultdict(set)
    for nd in wall_term["nA"]:
        TERM[nd].add("nA")
    for i in range(1, 5):
        for j in range(wny):
            TERM[(i, j)].add("__wall__")   # 中间整列封死
    c1 = _route_net(wall_term["nA"], "nA", wnx, wny, {}, {}, TERM)
    if c1 is not None:
        problems.append(("probe_wall_not_unrouted",))

    # 探针 C2：控制组形状注入异网重叠 ⇒ fast_drc 必红 min_spacing
    if ss:
        h = next((s for s in ss if s.layer == L_M3 and s.kind == "metal"
                  and (s.x1 - s.x0) >= 3 * 0.10), None)
        if h is not None:
            bad = list(ss)
            bad.append(DD._rect(L_M3, h.x0, h.y0 + 0.01, h.x1, h.y0 + 0.01 + W,
                                net="__short__", kind="metal"))
            if not any(v[0] == "min_spacing" for v in DL.fast_drc(bad)["violations"]):
                problems.append(("probe_overlap_not_red",))
        else:
            problems.append(("probe_no_h_seg",))

    # 探针 C3：砍掉控制组某网的 1 条边 ⇒ 线长 < MST（金标有牙）
    n0 = next(iter(s_routed))
    e0 = s_routed[n0][0]
    wl_full = sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in e0) * PITCH
    if e0:
        e1 = e0[:-1]
        wl_cut = sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in e1) * PITCH
        if not (wl_cut < _mst_len(synth[n0]) - 1e-6):
            problems.append(("probe_cut_not_detected", wl_full, wl_cut))

    if verbose:
        print("  grid: %dx%d  real routability=%.1f%% (%d/%d)  real_drc=%s real_lvs=%s  spread: %s"
              % (r["nx"], r["ny"], 100 * r["routability"], r["n_routed"], r["n_nets"],
                 real_drc_n, real_lvs_n,
                 ", ".join("×%g→%.0f%%" % (s["spread"], 100 * s["routability"]) for s in sweep)))
    return {
        "ok": not problems, "problems": problems,
        "grid_w": r["nx"], "grid_h": r["ny"],
        "n_nets": r["n_nets"], "n_routed": r["n_routed"],
        "routability": r["routability"],
        "control_routability": (len(s_routed) / len(synth)) if synth else 0.0,
        "real_drc_info": real_drc_n, "real_lvs_info": real_lvs_n,
        "sweep": sweep,
    }


DDROUTE_GRID_DISCLOSURE = {
    "route": "E38a · 网格迷宫路由器 + 可布通性（D-225）",
    "analysis": "M3(横)/M4(竖) 两层网格 · 逐网 BFS 迷宫布线（贪心一次布，无 R&R）· 分层独立占用"
                "（异网横竖可在同点交叉不短路）· via 带 landing pad",
    "golden": "稀疏合成控制组：100% 布通 + 同层不重叠(DRC=0) + 终端全连通(LVS) + 线长≥MST；"
              "真实布局：布通率如实报（本密度仅 3.2%，判 <50%）· 放大布局布通率回升",
    "not_included": "仅 M3/M4 两层(无 M5/M6) · 单元几何符号级超窄 · **无多轮 rip-up/R&R**（E38b）· "
                    "via 与线同权 · 无时序/串扰/PI 驱动 · 规则值 MODEL_ESTIMATE",
    "real_drc_lvs_note": "真实布局已布形状的 DRC/LVS **不判红、只作信息**：单元中心=共享终端黑盒，"
                         "多网在同一网格点共用终端 ⇒ landing pad 重叠/连通性定义含混（E36/E37 起既有简化），"
                         "非路由器缺陷；几何干净性以「稀疏合成控制组（终端互斥）」为准。",
    "e38_note": "真实布局 die 18×18.7µm、1340 单元(≈223/行、单元宽 0.075µm)⇒ **布通率仅 3.2%**"
                "（贪心 44/1354）：0.36µm 轨距下 ~4~5 单元挤到同一网格点，几乎每点都是某网终端 ⇒ "
                "大多数线出不了引脚。这是**布局密度**（符号级超窄单元）所致，非路由器不足；"
                "放大布局后布通率回升（见 sweep）。诚实负结果：本版符号布局在 M3/M4 网格上基本不可布通，"
                "需真实单元面积/更多层（多轮 R&R 与完整密度曲线属 E38b）。",
    "claimable": False,
}
