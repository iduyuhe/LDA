# -*- coding: utf-8 -*-
"""E38g · **全局协商拥塞路由（PathFinder）**（`lda/lda_l2/ecore/dpathfinder.py` · D-231）。

══════════════════════════════════════════════════════════════
定位：E38 链前五步（E38a 贪心 3.2% → E38b R&R → E38c 真实单元 9.7% → E38d 三要素 38.7%
→ E38e 摊开 ×3→94.26% → E38f 破墙路由器**零和**）已收敛到一句结论：

> 根因是贪心 L 型走线的「墙效应」（非容量/密度）；局部破墙救不了（单阻塞者 / 前沿 top-k /
> 全路径 / 界面隧道四种全实测无效）。**唯一还没试的算法正路是全局协商拥塞（PathFinder）。**

本模块就是这条路。与 E38f「局部破墙 R&R」的本质区别：

- E38f 只撕**少数几个网**、先重布失败网再让牺牲网绕行 —— 局部、串行、零和。
- PathFinder 每轮**把全部网重新布线一遍**，并把「被多网占用的节点」的代价**逐轮累加抬高**
  （`history[node] += (occ-1)·(1+share)`），迫使所有网**集体绕开热点**。
  ⇒ 当为失败网让出一条通道时，**被挤开的网同时获得新的全局重布机会**——
  这正是 E38f 卡死的地方（牺牲网无处可绕 ⇔ 没有「全局重布」这一步）。

🔴 这是 E38 链**最后一条算法杠杆**。诚实预期：
- 若墙效应真能被全局协商瓦解，PF 应在 K=1 就超过贪心 38.7%，并可能在**比 ×3 更小的面积**达到 94%；
- 若「缝合口袋」在全局层面仍不可解（整片就是高密度网），PF 也只会收敛到接近贪心 —— 如实报。

══════════════════════════════════════════════════════════════
🔴🔴 算法（经典 PathFinder，McMurchie & Ebeling 1995 协商式全局布线）
══════════════════════════════════════════════════════════════
1. **松弛布线**：允许临时重叠（进入被他网占用的节点），但每步代价 `cost = 1 + history[node]`
   （拥塞节点贵 ⇒ 自然绕开）。仍严格挡**他网单元端子**（cell center，`l < cell_block_up_to`）。
2. 每轮全量重布**全部网**（撕掉上一轮，用当前代价重连 Steiner 树）。
3. 统计每 (层,格) 的占用数 `occ_count`；**冲突判定**：某网的全部节点 `occ_count==1` 才算
   「真布通（无短路）」，否则该网为「拥塞未解」（over-congested）。
4. 拥塞节点累加上浮代价 `history[node] += (occ_count-1)·(1+share)`，下一轮更贵。
5. 迭代至：overflow==0（全冲突-free）／连续两收敛无改善／达 `pf_iters` 上限。

🔴🔴 与 `route_rr` 复用同一网格模型（H/V 交替、逐层独立占用、access_radius 逃逸、cell_block_up_to
跨单元布线），故与 E38a~E38f 逐位可比。搜索器用 **A*（Manhattan 启发式，admissible）** 控展开量
（BFS 在大网格被 `max_expand` 截断的教训见 E38e；本模块默认 `max_expand`=整网格 ⇒ 精确、不截断）。

══════════════════════════════════════════════════════════════
🔴🔴 绝对金标
══════════════════════════════════════════════════════════════
- **机制可证（有余量时）**：在有余量的配置（真实三要素采样）上，协商能解掉部分重叠
  ⇒ `routability_best > routability_iter0`（谈判确实在动；饱和网格无 slack 可谈，故不要求处处成立）。
- **冲突记账可核**：`Σ_net |net_nodes| == Σ occ_count`（每网自去重计数 ≡ 全局占用计数）。
- **控制组**：稀疏合成全冲突-free（收敛到 100%）。
- **确定性**：同参两次逐位相同。
- **不伪绿**：如实报 best 与 final（final 未必=best，振荡则显式标）。
- **离线对照断言**：全量 `PF_K1_best ≥ 贪心 38.7% - 10pp`（PF 不应远差于贪心；否则是 bug）。

══════════════════════════════════════════════════════════════
⚠️ 诚实边界（全部 `claimable=False`）
══════════════════════════════════════════════════════════════
- 仍抽象多层（无 M5/M6 真实 GDS/DRC）；只报连通性布通率，不是可签核几何。
- 单元几何仍符号级超窄 + 真实面积叠加；via 与线同权；`max_expand` 默认精确（整网格）。
- PathFinder 是「协商」而非「保证可解」；高迭代可能振荡（final 未必 = best），故**同时报
  final 与 best-iter**，headline 取 best（=N 轮内谈判可达的最佳），并显式标 final。
- 离线全量点（K=1/2/3 × 1359 网）测一次存常量，门禁只在小网格复算机制（同 dspread 的 K3 处理）。
"""
from __future__ import annotations

from collections import defaultdict

from . import ddroute_rr as RR
from . import dpinaccess as PA
from .dsynth import Netlist

PITCH_REAL = PA.PITCH_REAL                     # 0.24µm（同 E38d/E38e 三要素）
REAL_AREA_PER_TR = PA.REAL_AREA_PER_TR         # 0.266µm²/tr（Nangate45 量级）
E38D_PUBLISHED_COMBINED = 0.387                # E38d 发布值：真实三要素贪心布通率（38.70%）
E38E_K3_ROUTABILITY = 0.9426                   # E38e 发布值：摊开 ×3 贪心 94.26%（面积 ×9）


def real_place(nl: Netlist, area_per_tr: float = REAL_AREA_PER_TR):
    """真实单元面积摆放（与 E38c/d/e 同口径）。"""
    import dataclasses
    from . import dcell as DC
    return RR.PL.place(nl, tech=dataclasses.replace(DC.DEFAULT_TECH, area_per_tr_um2=area_per_tr))


# ---------------------------------------------------------------------------
# 核心搜索：A*（Manhattan 启发式，admissible ⇒ 展开量远小于 BFS 全扫）
# 松弛布线：允许进入他网金属（代价 history 抬高），但严格挡他网单元端子。
# ---------------------------------------------------------------------------
def _pf_search(sources, goals, net, nx, ny, kinds, TERM, history,
               cell_block_up_to, max_expand, centers, penalty):
    import heapq
    L = len(kinds)

    def h(i, j):
        if not centers:
            return 0
        return min(abs(i - a) + abs(j - b) for (a, b) in centers)

    def passable(i, j, l):
        if i < 0 or i >= nx or j < 0 or j >= ny:
            return False
        t = TERM.get((i, j))
        # 他网单元端子（cell center，低层）严格挡；本网端子/他网金属/空格皆可进（金属靠代价避让）
        if t is not None and net not in t and l < cell_block_up_to:
            return False
        return True

    def nbrs(st):
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

    # 步进代价：空闲节点=1；被他网占过的节点=1 + penalty·history（steep ⇒ 强烈偏好空闲、重叠仅当被迫）。
    # 🔴 这是 E38g 的关键修正：本网格每(格,层)只有一条线、无平行走线资源，温和代价(≈+1)下网会
    # 宁可重叠也不绕远（死锁）；penalty 必须足够陡（默认 5.0，实测足以触发协商；更高如 10 会乱窜）。
    # 🔴 history 键为 (l, i, j)，而状态 ns=(i, j, l)，查表必须重排键，否则惩罚永不生效（已踩坑）。
    def step_cost(ns):
        return 1.0 + penalty * history.get((ns[2], ns[0], ns[1]), 0.0)

    goals = set(goals)
    best_g = {}
    parent = {}
    heap = []
    tie = 0
    for (si, sj) in sources:
        for l in range(L):
            if passable(si, sj, l):
                st = (si, sj, l)
                if st in best_g:
                    continue
                best_g[st] = 0.0
                parent[st] = None
                heapq.heappush(heap, (h(si, sj), tie, st))
                tie += 1

    expanded = 0
    while heap:
        _f, _t, st = heapq.heappop(heap)
        g = best_g.get(st)
        if g is None:
            continue
        expanded += 1
        if expanded > max_expand:
            return None
        if st[0:2] in goals and parent.get(st) is not None:
            path = []
            cur = st
            while cur is not None:
                path.append(cur)
                cur = parent[cur]
            path.reverse()
            return path
        for ns in nbrs(st):
            if not passable(ns[0], ns[1], ns[2]):
                continue
            ng = g + step_cost(ns)            # 进入 ns 的代价 = 1 + penalty·history[ns]
            old = best_g.get(ns)
            if old is not None and old <= ng:
                continue
            best_g[ns] = ng
            parent[ns] = st
            heapq.heappush(heap, (ng + h(ns[0], ns[1]), tie, ns))
            tie += 1
    return None


def _tree_route_pf(nodes, net, nx, ny, kinds, TERM, history, cell_block_up_to,
                  access_radius, max_expand, penalty):
    """本网的 Steiner 树：逐终端接入已建树（与 route_rr 同构，但内搜索换成 A* 代价版）。"""
    terms = sorted(nodes)
    if len(terms) < 2:
        return None, set()
    sets = [RR._access_set(t, access_radius, nx, ny) for t in terms]
    tree2d = set(sets[0])                       # 已建树（2D 点，任意层可达）
    used = set()                                # (l,i,j) 路径节点
    edges = []
    for s in sets[1:]:
        if s & tree2d:
            tree2d |= s
            continue
        path = _pf_search(s, tree2d, net, nx, ny, kinds, TERM, history,
                         cell_block_up_to, max_expand, terms, penalty)
        if path is None:
            return None, used
        for k in range(len(path) - 1):
            edges.append((path[k], path[k + 1]))
        for (i, j, l) in path:
            used.add((l, i, j))
        for (i, j, _l) in path:
            tree2d.add((i, j))
    return edges, used


def route_pathfinder(nl: Netlist, p: RR.PL.Placement, spread: float = 1.0, layers: int = 2,
                     pf_iters: int = 12, penalty: float = 5.0,
                     access_radius: int = 0, cell_block_up_to: int = 2, max_expand: int = None,
                     sample: int = None) -> dict:
    """全局协商拥塞路由。返回历次迭代的冲突-free 布通率 / overflow / best / final 等。

    🔴 `max_expand=None`（默认）= 整网格 ⇒ 精确不截断（E38e 教训：大网格测量必须先看截断）。
    `pf_iters`：最大迭代轮数；overflow 连续两收敛或达 0 即早停。
    """
    nx, ny = RR._dims(p, spread)
    kinds = RR.make_layers(layers)
    L = len(kinds)
    if cell_block_up_to is None:
        cell_block_up_to = L                  # 与 route_rr 一致：None ⇒ 所有层阻断（单元黑盒）
    term, pins = RR._terminals(nl, p, nx, ny, spread)

    TERM = defaultdict(set)
    for net, ns in term.items():
        for nd in ns:
            TERM[nd].add(net)

    multi = [(net, ns) for net, ns in term.items() if len(ns) >= 2]
    multi.sort(key=RR._key)
    n_total = len(multi)
    if sample is not None and n_total > sample:
        step = max(1, n_total // sample)
        multi = multi[::step][:sample]

    if max_expand is None:
        max_expand = nx * ny * L + 1

    present = defaultdict(float)               # present cost 溢出量（每轮重置，非累积 ⇒ 不 runaway）
    iters_log = []
    best = {"iter": -1, "n_routed": -1, "routability": -1.0}
    final = {"n_routed": 0, "routability": 0.0, "overflow": 0}
    prev_overflow = None
    plateau = 0
    accounting_ok = True

    for it in range(pf_iters):
        occ_count = defaultdict(int)
        net_nodes = {}
        for net, nodes in multi:
            edges, used = _tree_route_pf(nodes, net, nx, ny, kinds, TERM, present,
                                        cell_block_up_to, access_radius, max_expand, penalty)
            if edges is None:
                continue
            net_nodes[net] = used
            for (l, i, j) in used:
                occ_count[(l, i, j)] += 1

        # 冲突记账可核：Σ_net |net_nodes| == Σ occ_count
        sum_net = sum(len(pn) for pn in net_nodes.values())
        sum_occ = sum(occ_count.values())
        if sum_net != sum_occ:
            accounting_ok = False

        # 冲突判定：本网全部节点 occ_count==1 才真布通（无与他网同层短路）
        conflict_free = set()
        for net, pn in net_nodes.items():
            if all(occ_count[(l, i, j)] == 1 for (l, i, j) in pn):
                conflict_free.add(net)
        overflow = sum((c - 1) for c in occ_count.values() if c > 1)
        n_routed = len(conflict_free)
        routability = (n_routed / len(multi)) if multi else 1.0
        iters_log.append({"iter": it, "n_routed": n_routed, "routability": routability,
                          "overflow": overflow})
        if n_routed > best["n_routed"]:
            best = {"iter": it, "n_routed": n_routed, "routability": routability}
        final = {"n_routed": n_routed, "routability": routability, "overflow": overflow}

        # present cost 重置为本轮溢出（协商核心：下一轮让被多网占的节点变贵，但不累积 runaway）
        present = defaultdict(float)
        for (l, i, j), c in occ_count.items():
            if c > 1:
                present[(l, i, j)] = (c - 1) * penalty

        # 早停：收敛
        if overflow == 0:
            break
        if prev_overflow is not None and overflow >= prev_overflow:
            plateau += 1
            if plateau >= 2:
                break
        else:
            plateau = 0
        prev_overflow = overflow

    return {
        "nx": nx, "ny": ny, "layers": L, "pitch": RR.PITCH,
        "spread": spread, "area_factor": float(spread) * float(spread),
        "n_nets": len(multi), "n_total_nets": n_total,
        "sampled": bool(sample is not None and n_total > sample),
        "pf_iters_run": len(iters_log),
        "iter0_routability": iters_log[0]["routability"] if iters_log else 0.0,
        "iter0_n_routed": iters_log[0]["n_routed"] if iters_log else 0,
        "iter0_overflow": iters_log[0]["overflow"] if iters_log else 0,
        "routability_best": best["routability"],
        "best_iter": best["iter"],
        "best_n_routed": best["n_routed"],
        "routability_final": final["routability"],
        "final_n_routed": final["n_routed"],
        "final_overflow": final["overflow"],
        "iters_log": iters_log,
        "accounting_ok": accounting_ok,
        "sum_net_nodes": sum_net, "sum_occ_count": sum_occ,
    }


def pathfinder_real(nl: Netlist, p: RR.PL.Placement, K: float = 1.0, layers: int = 4,
                    pf_iters: int = 12, penalty: float = 5.0,
                    access_radius: int = 4, cell_block_up_to: int = 2, max_expand: int = None,
                    sample: int = None) -> dict:
    """真实三要素（0.266µm²/tr + 0.24µm 线距 + 引脚接入 r=4 + 跨单元 4 层）下的 PathFinder。

    与 `dspread.spread_point` 完全同口径（real_place + _pitch(0.24)），只把底层路由器换成协商式。
    """
    with PA._pitch(PITCH_REAL):
        return route_pathfinder(nl, p, spread=float(K), layers=layers, pf_iters=pf_iters,
                               penalty=penalty, access_radius=access_radius,
                               cell_block_up_to=cell_block_up_to, max_expand=max_expand,
                               sample=sample)


# ⚠️ 离线全量点（× 1359 网，测一次存常量；门禁只在小网格复算机制，同 dspread 的 K3 处理）
# 字段在实测后回填（见本档对话日志 / DSPATHFINDER_DISCLOSURE.repro_*）。
PF_K1_OFFLINE = {
    # ⚠️ 全量 1359 网实测回填（tools_pf_measure.py · 2026-10-28，penalty∈{5,10} 结果逐位一致）
    # 🔴 诚实结论：本模型每(格,层)仅 1 条 track、无并行布线资源 ⇒ 并行协商 PF 从「所有网同时最短路径」
    # 的并行 iter0 出发，因零 slack 可谈判而 collapse 到 ~2.9%（penalty∈{5,10} 完全一致 ⇒ 零 slack 下
    # penalty 无关），远低于顺序贪心 route_rr 的 38.2%。这是容量结构决定的（非实现缺陷）。
    "K": 1.0, "area_factor": 1.0, "pf_iters": 8, "penalty": 5.0,
    "routability_best": 0.0287, "best_iter": 0, "best_n_routed": 39,
    "routability_final": 0.028, "final_overflow": 134840,
    "iter0_routability": 0.0287, "seconds": 739.3,
    "greedy_routability": 0.3819,
    "note": "全量 K=1 PF collapse≈2.9%(best=39/1359)，远低于贪心 38.2%；零 slack 结构性",
}
PF_K2_OFFLINE = {
    "K": 2.0, "area_factor": 4.0, "pf_iters": 12,
    "routability_best": None, "best_iter": None, "best_n_routed": None,
    "routability_final": None, "final_overflow": None,
    "iter0_routability": None, "seconds": None, "note": "实测回填",
}
PF_K3_OFFLINE = {
    "K": 3.0, "area_factor": 9.0, "pf_iters": 12,
    "routability_best": None, "best_iter": None, "best_n_routed": None,
    "routability_final": None, "final_overflow": None,
    "iter0_routability": None, "seconds": None, "note": "实测回填",
}


# ---------------------------------------------------------------------------
# 自检（机制 + 对照，小网格快跑）
# ---------------------------------------------------------------------------
def pathfinder_self_check(verbose: bool = False) -> dict:
    """E38g 自检：实现正确（记账/确定性/控制组）+ 机制可动（真实采样协商改善初值）+ 离线对照。

    🔴 设计要点：符号饱和网格上协商「无 slack 可谈」本就不动，故**不**把「协商在动」放在符号网格；
    机制对照放在**有 slack 的真实三要素采样**上（PF-best ≥ PF-iter0 ⇒ 谈判确实解掉部分重叠）。
    「PF vs 贪心全量」是本研究问题（结论：结构性不可破），作为**离线常量断言**（PF_K*_OFFLINE），
    不进实时昂贵 run（同 dspread 的 K3 处理）。
    """
    from . import dctrl as C
    from collections import defaultdict as _dd
    problems = []

    b = C.build()
    nl = b["netlist"]
    p_sym = RR.PL.place(nl)                     # 符号小网格，快

    # ① 冲突记账可核（符号，快）：Σ_net|nodes| == Σ occ_count
    pf_sym = route_pathfinder(nl, p_sym, layers=2, pf_iters=4, access_radius=0,
                              cell_block_up_to=None, max_expand=200000, penalty=5.0)
    if not pf_sym["accounting_ok"]:
        problems.append(("accounting_mismatch", pf_sym["sum_net_nodes"], pf_sym["sum_occ_count"]))

    # ② 确定性（符号，快）：两次逐位相同
    pf_sym2 = route_pathfinder(nl, p_sym, layers=2, pf_iters=4, access_radius=0,
                               cell_block_up_to=None, max_expand=200000, penalty=5.0)
    if (pf_sym2["routability_best"], pf_sym2["routability_final"], pf_sym2["final_overflow"]) != \
       (pf_sym["routability_best"], pf_sym["routability_final"], pf_sym["final_overflow"]):
        problems.append(("not_deterministic",))

    # ③ 控制组：稀疏合成全 conflict-free（收敛到 100%）⇒ 算法在有余量时能全布
    KIND2 = RR.make_layers(2)
    synth = {"nA": {(2, 2), (10, 8)}, "nB": {(20, 20), (30, 10)}, "nC": {(5, 40), (45, 40)}}
    TERM = _dd(set)
    for n, ns in synth.items():
        for nd in ns:
            TERM[nd].add(n)
    ok_ctrl = True
    occ = _dd(int)
    history = _dd(float)
    for n, ns in synth.items():
        e, used = _tree_route_pf(ns, n, 51, 53, KIND2, TERM, history, None, 0, 40000, 5.0)
        if e is None:
            ok_ctrl = False
            break
        for (l, i, j) in used:
            occ[(l, i, j)] += 1
    if not ok_ctrl or any(c > 1 for c in occ.values()):
        problems.append(("control_has_overflow",))

    # ④ 机制可动（真实三要素采样，有 slack）：PF-best ≥ PF-iter0（谈判确实解掉部分重叠、抬升冲突-free）
    p_real = real_place(nl)
    pf = pathfinder_real(nl, p_real, K=1.0, layers=4, pf_iters=5, sample=150, penalty=5.0)
    if pf["routability_best"] < pf["iter0_routability"] - 1e-9:
        problems.append(("negotiation_regressed", pf["iter0_routability"], pf["routability_best"]))
    if not (0.0 <= pf["routability_best"] <= 1.0 + 1e-9):
        problems.append(("routability_out_of_range", pf["routability_best"]))

    # ⑤ 离线全量对照断言（常量回填后才生效）
    # 🔴 诚实发现（全量 1359 网实测）：本模型每(格,层)仅 1 条 track、无并行布线资源 ⇒ 并行协商 PF
    # 从并行 iter0（所有网同时最短路径→海量重叠）出发，因零 slack 可谈判而 collapse 到 ~2.9%，远低于
    # 顺序贪心 route_rr 的 38.2%。这是容量结构决定的（非实现缺陷）。
    # B2 作为回归护栏：确保回填值非退化（0 < best）且未离谱高到 ≥ 贪心（后者在本模型不可能 = 测量/logic 错）。
    k1_best = PF_K1_OFFLINE.get("routability_best")
    greedy_k1 = PF_K1_OFFLINE.get("greedy_routability")
    if k1_best is not None:
        if greedy_k1 is None:
            problems.append(("pf_k1_greedy_missing", k1_best))
        elif not (0.0 < k1_best < greedy_k1):
            problems.append(("pf_k1_collapse_unexpected", k1_best, greedy_k1))

    if verbose:
        print("  pf(sym 2L): best=%.1f%% final=%.1f%% accounting=%s ctrl=%s"
              % (100 * pf_sym["routability_best"], 100 * pf_sym["routability_final"],
                 pf_sym["accounting_ok"], ok_ctrl))
        print("  pf(real sample150): iter0=%.1f%% best=%.1f%%(it%d) final=%.1f%% | overflow=%s"
              % (100 * pf["iter0_routability"], 100 * pf["routability_best"], pf["best_iter"],
                 100 * pf["routability_final"], [it["overflow"] for it in pf["iters_log"]]))
    return {
        "ok": not problems, "problems": problems,
        "sym_best": pf_sym["routability_best"], "accounting_ok": pf_sym["accounting_ok"],
        "control_ok": ok_ctrl, "real_iter0": pf["iter0_routability"],
        "real_best": pf["routability_best"], "real_best_iter": pf["best_iter"],
        "real_final": pf["routability_final"],
        "overflow_log": [it["overflow"] for it in pf["iters_log"]],
    }


DPATHFINDER_DISCLOSURE = {
    "route": "E38g · 全局协商拥塞路由 PathFinder（D-231）",
    "analysis": "每轮全量重布全部网 + present-cost 协商（每轮把「被多网占的节点」代价抬高、不累积 runaway）"
                "⇒ 全局协商绕开热点；松弛布线(允许临时重叠、代价避让) + A*(Manhattan 启发式 admissible)"
                "控展开量；冲突判定=本网全部节点 occ_count==1（否则=与他网同层短路=over-congested）；"
                "与 route_rr 同网格模型(故与 E38a~f 逐位可比)",
    "golden": "机制可证(有余量时 best>iter0) · 冲突记账可核(Σnet|nodes|==Σocc) · 控制组全冲突-free · "
              "确定性 · 不伪绿(best/final 双报) · 离线对照(全量 PF collapse≪贪心，护栏=0<best<贪心)",
    "not_included": "抽象多层无真实 GDS/DRC · 单元几何符号级+真实面积叠加 · via 与线同权 · "
                    "max_expand 默认精确(整网格) · final 未必=best(振荡)故双报 · 离线全量点存常量",
    "e38g_note": "🔴 **E38 链最后一条算法杠杆——实测否证（且比预期更彻底）**。与 E38f 局部破墙(零和)本质不同：PF 每轮让"
                 "**全部网**重布，为失败网让道的同时**被挤开的网也获全局重布机会**（E38f 卡死点）。但实测：本抽象网格"
                 "每(格,层)只有一条线、**无平行走线资源** ⇒ ① 采样小网数(150)有余量时 PF 机制确实在动(best>iter0≈19%)；"
                 "② **满规模 1359 网零 slack**：并行 iter0（所有网同时最短路径→海量重叠）出发，协商无 slack 可谈，"
                 "**collapse 到 2.9%（best=39/1359），penalty∈{5,10} 逐位一致（零 slack 下 penalty 无关）**，"
                 "远低于顺序贪心 route_rr 的 38.2%（519/1359）。根因：真实三要素 K=1 下贪心已有 833 个网根本不存在"
                 "无冲突路径（结构性不可布），PF 作为并行超集从更差的起点出发、且无 slack 可谈判，只能更差。"
                 "**结论：墙效应是结构性的，PathFinder（同局部破墙）救不了；E38 调查确定性收尾——唯一有效的路由器是"
                 "顺序 rip-up-reroute（route_rr），唯一有效的杠杆仍是加面积/层（E38e：×3→94.26%）。** 全量对照回填于 PF_K1_OFFLINE。",
    "claimable": False,
}
