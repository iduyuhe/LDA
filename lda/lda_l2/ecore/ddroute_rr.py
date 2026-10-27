# -*- coding: utf-8 -*-
"""E38b · **多轮 R&R + 完整密度曲线 + 多层对比**（`lda/lda_l2/ecore/ddroute_rr.py` · D-226）。

══════════════════════════════════════════════════════════════
定位：E38a 用两层（M3 横 / M4 竖）贪心迷宫路由，诚实测到真实符号布局布通率仅 **3.2%**
（44/1354），并证明「放大布局布通率回升 ⇒ 是布局密度而非算法」。E38b 补齐三件事：
1. **多轮 rip-up & reroute（R&R）**：原子替换（不丢网），看能否把布通率再抬。
2. **完整密度曲线**：布通率 vs 布局放大 ×K（面积 ×K²），找 ~100% 可布通的操作点。
3. **多层对比**：抽象层数 2 / 4 / 6（M3/M4 / +M5/M6 / +）⇒ 看「加层」能否替代「摊开密度」。

🔴🔴 本模块是**抽象容量研究**（routability / connectivity），**不产 GDS 金属**（无 M5/M6 真实层），
故只报「布通率」这一抽象连通性指标；真实几何 DRC/LVS 属 E38a 的两层范围。这是刻意的边界。

══════════════════════════════════════════════════════════════
🔴🔴 网格模型（抽象多层，H/V 交替）
══════════════════════════════════════════════════════════════
- 层 `l` 的 kind：偶层=H(沿行左右)、奇层=V(沿列上下)；相邻层可换层(via)。
- 节点 `(i,j,l)`；边：H 层横移 / V 层竖移 / 邻居换层，每步代价 1。
- 占用**逐层独立**：`occ[l][(i,j)]=net`；异网可在不同层的同点共存（不同层不短路）。
- 终端簇：单元中心=单点，多网共享（单元黑盒，与 E36/E37/E38a 同口径）。
- 每网用 `net_occ[net]={(l,i,j)...}` 精确记账 ⇒ **rip/restore 原子**（R&R 不丢网）。

🔴🔴 绝对金标
══════════════════════════════════════════════════════════════
- 控制组（稀疏合成）：100% 布通。
- **R&R 原子性**：`routed(R&R) ≥ routed(贪心)`（rip 后必还原，绝不丢网）——这是本版最关键的金标。
- **多层单调**：`routability(layers=4) ≥ routability(layers=2)`（同密度下加层不劣）。
- **密度单调**：`routability(×K)` 随 K 非减（放大不劣）。
- 布通率如实报（低就低，不伪绿）。

══════════════════════════════════════════════════════════════
⚠️ 诚实边界（全部 `claimable=False`）
══════════════════════════════════════════════════════════════
- 抽象层（无 M5/M6 真实 GDS/DRC）；只报连通性布通率，不是可签核几何。
- 单元几何仍符号级超窄；via 与线同权（每步 1）；`max_expand` 上限对大网格为**保守**估计。
- R&R 是「单阻塞者原子替换」的轻量版，非工业多轮多阻塞者；不保证最优。
"""
from __future__ import annotations

from collections import defaultdict

from . import ddetail as DD
from . import dplac as PL
from .dsynth import Netlist

PITCH = DD.TRACK_PITCH


def make_layers(n: int) -> list:
    """n 层抽象层：偶层 H、奇层 V；物理层号 27,29,31,33,35,37（M3,M4,M5,M6,…）。"""
    base = [27, 29, 31, 33, 35, 37, 39, 41]
    layers = []
    for i in range(n):
        kind = "H" if i % 2 == 0 else "V"
        layers.append((kind, base[i] if i < len(base) else base[-1] + 2 * (i - len(base) + 1)))
    return layers


def _snap(x, y, nx, ny):
    i = min(max(int(round(x / PITCH)), 0), nx - 1)
    j = min(max(int(round(y / PITCH)), 0), ny - 1)
    return (i, j)


def _dims(p, spread):
    return (max(2, int(round(p.die_w_um * spread / PITCH)) + 1),
            max(2, int(round(p.die_h_um * spread / PITCH)) + 1))


def _terminals(nl, p, nx, ny, spread):
    pins = DD._net_pins(nl, p)
    term = {}
    for net, pts in pins.items():
        s = set()
        for (x, y) in pts:
            s.add(_snap(x * spread, y * spread, nx, ny))
        term[net] = s
    return term, pins


def _access_set(node, r, nx, ny):
    """引脚接入逃逸集：细层(M1/M2)可把引脚接到半径 r 内的粗网格点（曼哈顿半径）。

    r<=0 ⇒ 仅引脚本身（无逃逸，=E38b/c 原行为）。这是「真实设计靠细 M1/M2 把密排单元引脚接出」
    的抽象：逃逸自身不计占用（细层独立），是**乐观上界**（见披露）。
    """
    if r <= 0:
        return {(node[0], node[1])}
    i0, j0 = node
    s = set()
    for di in range(-r, r + 1):
        for dj in range(-r, r + 1):
            if abs(di) + abs(dj) <= r:
                i, j = i0 + di, j0 + dj
                if 0 <= i < nx and 0 <= j < ny:
                    s.add((i, j))
    return s


def _bfs(sources, goals, net, nx, ny, kinds, occ, TERM, max_expand, cell_block_up_to=None,
         stats=None, centers=None, astar=False):
    """多源搜索：从 sources（节点集合，可在任一层起步）到任一 goal 节点（树）。返回状态路径或 None。

    🔴🔴 两种模式，**默认 BFS 保历史口径**（E38b/c/d 的数是 BFS 冻结的）：
    - `astar=False`（默认）：普通 BFS（FIFO）。小网格足用，且与既有档逐位可比。
    - `astar=True`：A 星（FIFO 换成按 `g+h` 的优先队列），`h`=到**本网任一终端**的 Manhattan
      距离。注意这是**启发式**、非严格 admissible（最近终端可能还没连上）⇒ 不保证最短路径，
      但保证连通；金标「线长 ≥ MST」对任何路径成立，不受影响。

    🔴🔴 E38e 实证教训（为什么必须能换 A 星）：BFS 找距离 d 的点要展开 ~O(d²·L) 状态，
    网格放大 K 倍后展开量 ~K² 倍 ⇒ **同一 `max_expand` 预算下大网格必然截断**。实测 K=2
    （388×391×4）用 `max_expand=120000` 时失败 **997 网全部是截断**（与 stats 计数一致），
    布通率 26.6% < K=1 的 38.7% **纯属测量假象**，跟密度无关。

    `stats`（可选 dict）：累加 `truncated`（命中 `max_expand`）与 `expanded`（总扩展数）。
    **必须区分「真无路」与「被预算截断」**，否则大网格上的失败数会被误读成「不可布通」。
    """
    import heapq

    L = len(kinds)
    if cell_block_up_to is None:
        cell_block_up_to = L          # 默认：所有层都被单元中心阻断（E38b 原行为）
    cen = list(centers) if centers else None

    def h(i, j):
        if not cen:
            return 0
        return min(abs(i - a) + abs(j - b) for (a, b) in cen)

    def passable(i, j, l):
        if i < 0 or i >= nx or j < 0 or j >= ny:
            return False
        t = TERM.get((i, j))
        # 单元中心只在 l < cell_block_up_to 的层阻断（低层=引脚接入层）；高层可**跨单元布线**
        if t and net not in t and l < cell_block_up_to:
            return False
        o = occ[l].get((i, j))
        if o is not None and o != net:
            return False
        return True

    def nbrs_of(st):
        i, j, l = st
        out = []
        if kinds[l][0] == "H":
            out.append((i - 1, j, l))
            out.append((i + 1, j, l))
        else:
            out.append((i, j - 1, l))
            out.append((i, j + 1, l))
        if l - 1 >= 0:
            out.append((i, j, l - 1))
        if l + 1 < L:
            out.append((i, j, l + 1))
        return out

    def unwind(parent, st):
        path = []
        cur = st
        while cur is not None:
            path.append(cur)
            cur = parent[cur]
        path.reverse()
        return path

    def done(expanded):
        if stats is not None:
            stats["expanded"] = stats.get("expanded", 0) + expanded

    def trunc(expanded):
        done(expanded)
        if stats is not None:
            stats["truncated"] = stats.get("truncated", 0) + 1
        return None

    goals = set(goals)
    parent = {}

    if astar:
        heap = []
        tie = 0
        best_g = {}
        for (si, sj) in sources:
            for l in range(L):
                if passable(si, sj, l):
                    st = (si, sj, l)
                    if st in best_g:
                        continue
                    best_g[st] = 0
                    parent[st] = None
                    heap.append((h(si, sj), tie, st))
                    tie += 1
        heapq.heapify(heap)
        expanded = 0
        while heap:
            _f, _t, st = heapq.heappop(heap)
            g = best_g[st]
            expanded += 1
            if expanded > max_expand:
                return trunc(expanded)
            if st[0:2] in goals and parent.get(st) is not None:
                done(expanded)
                return unwind(parent, st)
            ng = g + 1
            for ns in nbrs_of(st):
                if not passable(ns[0], ns[1], ns[2]):
                    continue
                old = best_g.get(ns)
                if old is not None and old <= ng:
                    continue
                best_g[ns] = ng
                parent[ns] = st
                heapq.heappush(heap, (ng + h(ns[0], ns[1]), tie, ns))
                tie += 1
        done(expanded)
        return None

    from collections import deque as _dq
    dq = _dq()
    seen = set()
    for (si, sj) in sources:
        for l in range(L):
            if passable(si, sj, l):
                st = (si, sj, l)
                if st in seen:
                    continue
                parent[st] = None
                seen.add(st)
                dq.append(st)
    expanded = 0
    while dq:
        st = dq.popleft()
        expanded += 1
        if expanded > max_expand:
            return trunc(expanded)
        if st[0:2] in goals and parent.get(st) is not None:
            done(expanded)
            return unwind(parent, st)
        for ns in nbrs_of(st):
            if not passable(ns[0], ns[1], ns[2]):
                continue
            if ns in seen:
                continue
            seen.add(ns)
            parent[ns] = st
            dq.append(ns)
    done(expanded)
    return None


def _route_net(nodes, net, nx, ny, kinds, occ, TERM, max_expand, cell_block_up_to=None,
               access_radius=0, stats=None, astar=False):
    terms = sorted(nodes)
    if len(terms) < 2:
        return []
    sets = [_access_set(t, access_radius, nx, ny) for t in terms]
    tree = set(sets[0])
    edges = []
    for s in sets[1:]:
        if s & tree:
            tree |= s
            continue
        path = _bfs(s, tree, net, nx, ny, kinds, occ, TERM, max_expand, cell_block_up_to,
                    stats, terms, astar)
        if path is None:
            return None
        for k in range(len(path) - 1):
            edges.append((path[k], path[k + 1]))
        for (i, j, _l) in path:
            tree.add((i, j))
        tree |= s
    return edges


def _edge_len(edges):
    return sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in edges)


def _key(item):
    net, nodes = item
    xs = [i for (i, j) in nodes]
    ys = [j for (i, j) in nodes]
    return (len(nodes), (max(xs) - min(xs)) + (max(ys) - min(ys)), net)


def route_rr(nl: Netlist, p: PL.Placement, spread: float = 1.0, layers: int = 2,
             rr_rounds: int = 3, sample: int = None, max_expand: int = 40000,
             cell_block_up_to: int = None, access_radius: int = 0,
             astar: bool = False) -> dict:
    """抽象多层网格 + 贪心布线 + 多轮原子 R&R。返回布通率等（不产 GDS）。

    `cell_block_up_to`：单元中心只在**前 N 层**阻断（低层=引脚接入），N 以上可跨单元布线
    （=真实「高层金属跨过标准单元」；默认 None ⇒ 所有层阻断 = E38b 原行为）。
    `access_radius`：引脚接入逃逸半径（细层 M1/M2 把引脚接到半径 r 内粗网格点；默认 0=无逃逸）。
    `astar`：搜索器（默认 False=BFS，与 E38b/c/d 冻结口径一致；True=A 星，仅大网格摊开研究用）。
    返回额外含 `n_truncated`（被 `max_expand` 截断的网数，>0 时布通率只是**下界**）与
    `expanded`（总搜索扩展数，用于成本模型）。
    """
    nx, ny = _dims(p, spread)
    kinds = make_layers(layers)
    L = len(kinds)
    term, pins = _terminals(nl, p, nx, ny, spread)

    TERM = defaultdict(set)
    for net, ns in term.items():
        for nd in ns:
            TERM[nd].add(net)

    multi = [(net, ns) for net, ns in term.items() if len(ns) >= 2]
    multi.sort(key=_key)
    n_total = len(multi)
    if sample is not None and n_total > sample:
        step = max(1, n_total // sample)
        multi = multi[::step][:sample]

    occ = [{} for _ in range(L)]
    net_occ = defaultdict(set)
    routed = {}
    unrouted = []
    stats = {"truncated": 0, "expanded": 0}

    def commit(net, edges):
        for (a, b) in edges:
            for (i, j, l) in (a, b):
                occ[l][(i, j)] = net
                net_occ[net].add((l, i, j))

    def rip(net):
        saved = set(net_occ[net])
        for (l, i, j) in saved:
            if occ[l].get((i, j)) == net:
                del occ[l][(i, j)]
        net_occ[net].clear()
        return saved

    def restore(net, saved):
        for (l, i, j) in saved:
            occ[l][(i, j)] = net
            net_occ[net].add((l, i, j))

    def try_route(net, nodes):
        return _route_net(nodes, net, nx, ny, kinds, occ, TERM, max_expand,
                          cell_block_up_to, access_radius, stats, astar)

    for net, nodes in multi:
        e0 = stats["expanded"]
        e = try_route(net, nodes)
        if e is None:
            # 失败模式二分（E38e 诊断用）：扩展数=0 ⇒ 引脚接入点全被占（压死）；
            # 否则是"搜完了确实没路" ⇒ 已布金属形成闭合墙把网格切断（墙效应）。
            if stats["expanded"] == e0:
                stats["fail_src_blocked"] = stats.get("fail_src_blocked", 0) + 1
            else:
                stats["fail_walled"] = stats.get("fail_walled", 0) + 1
            unrouted.append((net, nodes))
        else:
            commit(net, e)
            routed[net] = e

    # 多轮原子 R&R（单阻塞者替换；rip 后必还原 ⇒ 绝不丢网）
    for _r in range(max(0, rr_rounds)):
        progress = False
        still = []
        for net, nodes in unrouted:
            xs = [i for (i, j) in nodes]
            ys = [j for (i, j) in nodes]
            i0, i1, j0, j1 = min(xs), max(xs), min(ys), max(ys)
            cnt = defaultdict(int)
            for l in range(L):
                for (i, j), o in occ[l].items():
                    if o != net and i0 <= i <= i1 and j0 <= j <= j1:
                        cnt[o] += 1
            victim = max(cnt, key=lambda k: (cnt[k], k)) if cnt else None
            if victim is None or victim not in routed:
                still.append((net, nodes))
                continue
            saved = rip(victim)
            ve = routed.pop(victim)
            ne = try_route(net, nodes)
            if ne is not None:
                commit(net, ne)
                ve2 = try_route(victim, term[victim])
                if ve2 is not None:
                    commit(victim, ve2)
                    routed[victim] = ve2
                    routed[net] = ne
                    progress = True
                    continue            # net 已布通，不入 still
                # 回滚 net
                for (l, i, j) in list(net_occ[net]):
                    if occ[l].get((i, j)) == net:
                        del occ[l][(i, j)]
                net_occ[net].clear()
                routed.pop(net, None)
            restore(victim, saved)
            routed[victim] = ve
            still.append((net, nodes))
        unrouted = still
        if not progress:
            break

    n_routed = len(routed)
    wl = 0.0
    mst = 0.0
    for net, e in routed.items():
        wl += _edge_len(e) * PITCH
        mst += _mst_len(term[net])
    return {
        "nx": nx, "ny": ny, "layers": L,
        "n_nets": len(multi), "n_total_nets": n_total,
        "sampled": bool(sample is not None and n_total > sample),
        "n_routed": n_routed,
        "n_truncated": stats["truncated"],
        "expanded": stats["expanded"],
        "capacity_nodes": nx * ny * L,
        "fail_source_blocked": stats.get("fail_src_blocked", 0),
        "fail_walled": stats.get("fail_walled", 0),
        "routability": (n_routed / len(multi)) if multi else 1.0,
        "routed_nets": list(routed.keys()),
        "unrouted_nets": [net for net, _ in unrouted],
        "wirelength_um": wl, "mst_um": mst,
    }


def _mst_len(nodes):
    pts = [(i * PITCH, j * PITCH) for (i, j) in nodes]
    if len(pts) < 2:
        return 0.0
    tot = 0.0
    for (a, b) in DD._mst_edges(pts):
        tot += abs(pts[a][0] - pts[b][0]) + abs(pts[a][1] - pts[b][1])
    return tot


def density_curve(nl: Netlist, p: PL.Placement, factors=(1, 2, 3, 4), layers: int = 2,
                  rr_rounds: int = 0, sample: int = None) -> list:
    """布通率 vs 布局放大 ×K（面积 ×K²）。找「需要摊开多少倍才 ~100% 可布通」。

    ⚠️ `max_expand=40000` 在 K≥3（网格×层数 > 4e4 状态）会截断长路径 ⇒ 大 K 布通率为
    **保守下界**（真实值 ≥ 报出值），已在披露注明；K=1,2 不受限（网格状态 < 4e4）。
    """
    out = []
    for K in factors:
        r = route_rr(nl, p, spread=float(K), layers=layers, rr_rounds=rr_rounds, sample=sample)
        out.append({"spread": K, "routability": r["routability"],
                    "n_routed": r["n_routed"], "n_nets": r["n_nets"],
                    "n_total_nets": r["n_total_nets"], "area_factor": float(K) * float(K)})
    return out


def layer_compare(nl: Netlist, p: PL.Placement, spread: float = 1.0,
                  layer_counts=(2, 4, 6), rr_rounds: int = 0, sample: int = None) -> list:
    """同密度下，抽象层数 2/4/6 的布通率对比（加层能否替代摊开密度）。"""
    out = []
    for Lc in layer_counts:
        r = route_rr(nl, p, spread=spread, layers=Lc, rr_rounds=rr_rounds, sample=sample)
        out.append({"layers": Lc, "routability": r["routability"],
                    "n_routed": r["n_routed"], "n_nets": r["n_nets"]})
    return out


# ---------------------------------------------------------------------------
# 自检（含「必须失败」的对照组）
# ---------------------------------------------------------------------------
def route_rr_self_check(verbose: bool = False) -> dict:
    """E38b 自检：R&R 原子不丢网 + 多层单调 + 密度单调 + 控制组有效。

    - ① 控制组：稀疏合成 2 层 100% 布通。
    - ② R&R 原子：真实布局 `routed(R&R) ≥ routed(贪心)`（绝不丢网）。
    - ③ 多层单调：layers=4 布通率 ≥ layers=2（同密度加层不劣）。
    - ④ 密度单调：×1→×2→×3 布通率端点非减。
    - 探针：C1 强制不可布（围死）必报未布；C2 R&R 关闭时 routed ≤ R&R 开启。
    """
    from collections import defaultdict as _dd
    from . import dctrl as C
    problems = []

    # ① 控制组（稀疏合成，2 层）
    synth = {"nA": {(2, 2), (10, 8)}, "nB": {(20, 20), (30, 10)}, "nC": {(5, 40), (45, 40)}}
    KIND2 = make_layers(2)
    TERM = _dd(set)
    for n, ns in synth.items():
        for nd in ns:
            TERM[nd].add(n)
    occ = [{} for _ in KIND2]
    # 手工贪心布控制组（不走 route_rr，因其需 netlist）
    ok_ctrl = True
    for n, ns in synth.items():
        e = _route_net(ns, n, 51, 53, KIND2, occ, TERM, 40000)
        if e is None:
            ok_ctrl = False
            break
        for (a, b) in e:
            for (i, j, l) in (a, b):
                occ[l][(i, j)] = n
    if not ok_ctrl:
        problems.append(("control_unrouted",))

    # ②③④ 真实布局
    b = C.build()
    nl = b["netlist"]
    p = PL.place(nl)

    greedy = route_rr(nl, p, layers=2, rr_rounds=0)
    rrd = route_rr(nl, p, layers=2, rr_rounds=3)
    if rrd["n_routed"] < greedy["n_routed"]:
        problems.append(("rr_lost_nets", greedy["n_routed"], rrd["n_routed"]))

    lay = layer_compare(nl, p, spread=1.0, layer_counts=(2, 4), rr_rounds=0)
    if lay[1]["routability"] < lay[0]["routability"] - 1e-9:
        problems.append(("layers_not_monotone", lay))

    dens = density_curve(nl, p, factors=(1, 2, 3, 4), layers=2, rr_rounds=0)
    if dens[-1]["routability"] < dens[0]["routability"] - 1e-9:
        problems.append(("density_not_monotone", dens))

    # 探针 C1：围死某网 ⇒ 必报未布
    wterm = _dd(set)
    wterm[(0, 0)].add("w")
    wterm[(5, 0)].add("w")
    for i in range(1, 5):
        for j in range(3):
            wterm[(i, j)].add("__wall__")
    occ2 = [{} for _ in KIND2]
    c1 = _route_net({(0, 0), (5, 0)}, "w", 6, 3, KIND2, occ2, wterm, 40000)
    if c1 is not None:
        problems.append(("probe_wall_not_unrouted",))

    if verbose:
        cells = len(p.cell_xywh)
        cpn = cells / float(greedy["nx"] * greedy["ny"]) if greedy["nx"] * greedy["ny"] else 0.0
        print("  rr: greedy=%.1f%% R&R=%.1f%% | layers 2/4=%.1f%%/%.1f%% | cells/node@K1=%.2f | dens %s"
              % (100 * greedy["routability"], 100 * rrd["routability"],
                 100 * lay[0]["routability"], 100 * lay[1]["routability"], cpn,
                 " ".join("×%g→%.0f%%" % (d["spread"], 100 * d["routability"]) for d in dens)))
    return {
        "ok": not problems, "problems": problems,
        "control_routability": 1.0 if ok_ctrl else 0.0,
        "greedy_routability": greedy["routability"],
        "rr_routability": rrd["routability"],
        "rr_n_routed": rrd["n_routed"], "greedy_n_routed": greedy["n_routed"],
        "layers": lay,
        "density": dens,
    }


DDROUTE_RR_DISCLOSURE = {
    "route": "E38b · 多轮 R&R + 完整密度曲线 + 多层对比（D-226）",
    "analysis": "抽象多层网格(H/V 交替) · 逐网 BFS · 单阻塞者原子 R&R（rip 后必还原）· "
                "net_occ 精确记账 ⇒ 绝不丢网 · 密度曲线 ×K · 层数对比 2/4/6",
    "golden": "控制组 100% · R&R 原子性 routed(R&R)≥routed(贪心) · 多层单调 layers4≥layers2 · "
              "密度单调 ×K 非减 · 布通率如实报",
    "not_included": "抽象层无 M5/M6 真实 GDS/DRC（只报连通性）· 单元几何符号级超窄 · "
                    "单阻塞者轻量 R&R（非工业多阻塞者）· via 与线同权 · max_expand 为保守上限",
    "e38b_note": "本模块是**容量研究**不是可签核几何：只回答「加 R&R / 加层 / 摊开密度各能把布通率"
                 "抬到多少」。实测（K=1）：R&R 几乎无益（3.8%→3.8%，终端拥挤所致，非占用拥塞）；"
                 "层数 2→4 约翻倍（3.8%→7.2%）但远不够；摊开 ×2/×3/×4 缓慢升（5.6/6.8/7.7%）。"
                 "⚠️ `max_expand=40000` 在 K≥3 截断长路径 ⇒ 大 K 为**保守下界**（真实值 ≥ 报出值）。"
                 "🔴 结论：**路由技巧（R&R/加层/温和摊开）都救不了**，根因是符号级超窄单元密度（cells/node@K1≈0.5）；"
                 "正路是换真实单元面积。另注：本抽象变体比 E38a（含 landing-pad 占用）略宽松 ⇒ 3.8% vs 3.2%，皆 ~不可布通。",
    "claimable": False,
}
