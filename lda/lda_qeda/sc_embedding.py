"""J2 M4 · 表面码 **真嵌入**（编译/映射）—— 把「度 ≥ 4 就判 DIRECT」换成可判定的谓词。

═══════════════════════════════════════════════════════════════════════════
这条缺口的原文（`j2 J2-G-D`）
═══════════════════════════════════════════════════════════════════════════
「λ₂ 为图论谱不变量；2D 最近邻嵌入判定为设计规则。**仍缺**编译/映射实测与真实
硬件拓扑下的往返验证。」

拆开看是两件事：
  · **编译/映射** = 给定硬件耦合图，表面码的关联图到底能不能落上去 —— **纯建模活**；
  · **真实硬件拓扑下的往返验证** = 要真机 logical error rate —— 须实验台 ⇒ 边界声明。
本模块只做前者（`J2-G-Da`），后者在卡上标 `J2-G-Db` 边界。

═══════════════════════════════════════════════════════════════════════════
要修的三件事
═══════════════════════════════════════════════════════════════════════════
① 旧判据 `surface_code_2d_nn_verdict`：`max_degree ≥ 4 ⇒ DIRECT`。
   这条**是必要条件，却被当成充分条件用**。反例（本模块自检 ④ 造出来）：
   3-ary 树（内部节点度恰 4、24 个节点 ≥ 17）按旧规则判 DIRECT，实际**可证不可能**
   —— 表面码的关联图含 4-圈（相邻两个稳定子交叠 2 个数据比特），树一个 4-圈都没有。
② 旧判据对 heavy-hex 返回 `ADAPTED ⇒ ACCEPT`，读起来像「能跑」。
   真相更强：`max_degree = 3 < 4` ⇒ **原生嵌入可证不可能**（内部稳定子权重 4）。
   「适配」不是换版图，是**换码**（flag 比特把权重 4 的检验拆成多步）—— 那是另一个码，
   距离与开销本模块没算 ⇒ 只能标边界，不能算 ACCEPT。
③ j2 卡里 `"embedding": "DIRECT" if 4 >= 4 else "ADAPTED"` 是**恒真表达式**
   （`4 >= 4` 永远真），`max_degree: 4` 也是手填 ⇒ 判据自己证明自己。

═══════════════════════════════════════════════════════════════════════════
模型（只取**关联结构**，不取 CSS 结构）
═══════════════════════════════════════════════════════════════════════════
距离 d 的表面码关联图 `SC(d)`：
  · 数据比特 d² 个，记 `("D", a, b)`，a,b ∈ [0, d)
  · 内部稳定子 (d−1)² 个，记 `("A", a, b)`，支撑 = 所在方格的 4 个角 ⇒ **权重 4**
  · 边界稳定子 2(d−1) 个，记 `("T", x)` / `("B", x)`，支撑 = 相邻 2 个数据 ⇒ **权重 2**
  ⇒ 节点数 = d² + (d−1)² + 2(d−1) = **2d² − 1**（与 J1 资源口径同式）

嵌入 = **注入同态**：把 `SC(d)` 的每个节点映到硬件图上不同的节点，且**每条 required
边都必须是硬件图的边**（即 `SC(d)` 是硬件图的子图）。这是「耦合器够不够用」的判据。

🔴 为什么只取关联结构：硬件层面要回答的是「这几个比特之间有没有耦合器」，
   只与关联（incidence）有关，与哪个是 X 稳定子、哪个是 Z 稳定子无关。

═══════════════════════════════════════════════════════════════════════════
三值判决与「不得拿搜不到当不存在」
═══════════════════════════════════════════════════════════════════════════
  DIRECT     — 搜到显式映射，且映射由 `verify_map` **独立复核**（注入 + 逐边在位）
  IMPOSSIBLE — **有证明**。证明只能来自三处之一：
               (a) 节点数不足  (b) 度数界不足  (c) required 图有 4-圈而硬件图没有
               (d) 搜索树**穷尽**（不是预算用尽）后仍无解
  UNKNOWN    — 预算用尽仍未搜到。🔴 **不得**记为 IMPOSSIBLE、更不得记为 DIRECT。

这条纪律是本模块存在的理由：`max_degree ≥ 4` 这类设计规则**只能证伪、不能证实**，
把「证伪不了」写成「可行」是本仓反复出现的同一个错（v0.9.302 派生标签数原始维度 /
v0.9.307 分工机核只认未闭合）。所以判决类型里必须有 `UNKNOWN` 这一档，且它不许被压扁。

诚实边界：本层是**图论口径**的嵌入。它不验证映射是否保持 2D 局部性（允许「蛇形折叠」）
⇒ `DIRECT` 只说明「耦合器够、拓扑不挡」，**不等于**有一个可制造的版图。
d ≤ 5 的最小边标定是**穷尽搜索**结果，不是闭式定理。
"""
from __future__ import annotations

import sys
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = [
    "SC_NATIVE_MAX_DEGREE", "STATUS_DIRECT", "STATUS_IMPOSSIBLE", "STATUS_UNKNOWN",
    "sc_tanner_graph", "four_cycle", "necessary_violations", "embed", "verify_map",
    "native_verdict", "min_square_side", "min_square_side_closed", "kary_tree",
    "run_selfchecks",
]

#: 表面码内部稳定子的权重 ⇒ 硬件图**必须**存在度数 ≥ 4 的节点（必要条件）
SC_NATIVE_MAX_DEGREE = 4

STATUS_DIRECT = "DIRECT"
STATUS_IMPOSSIBLE = "IMPOSSIBLE"
STATUS_UNKNOWN = "UNKNOWN"

#: 搜索的默认展开预算（DFS 节点展开次数）。预算用尽 ⇒ UNKNOWN，**不是** IMPOSSIBLE。
DEFAULT_BUDGET = 200000


# ---------------------------------------------------------------------------
# ① 表面码关联图
# ---------------------------------------------------------------------------
def sc_tanner_graph(d: int) -> Dict:
    """距离 d 的表面码关联图（数据比特 + 内部权重 4 + 边界权重 2）。

    返回 `required`（每个节点的邻接表，**只含 ancilla → data 方向与 data → ancilla
    方向都写全**，便于直接当无向图用）与 `stats`（各项计数，供自检逐值对拍）。
    """
    d = int(d)
    if d < 2:
        raise ValueError("表面码距离须 ≥ 2（d=1 无稳定子），收到 %r" % (d,))
    required: Dict[Tuple, List[Tuple]] = {}
    for a in range(d):
        for b in range(d):
            required[("D", a, b)] = []
    for a in range(d - 1):
        for b in range(d - 1):
            node = ("A", a, b)
            sup = [("D", a, b), ("D", a + 1, b), ("D", a, b + 1), ("D", a + 1, b + 1)]
            required[node] = sup
    for x in range(d - 1):
        required[("T", x)] = [("D", x, 0), ("D", x + 1, 0)]
        required[("B", x)] = [("D", x, d - 1), ("D", x + 1, d - 1)]
    # 补反向边（无向化，逐节点去重）
    for u in list(required):
        for v in required[u]:
            if u not in required[v]:
                required[v].append(u)
    stats = {
        "d": d,
        "n_data": sum(1 for n in required if n[0] == "D"),
        "n_ancilla": sum(1 for n in required if n[0] != "D"),
        "n_internal_w4": sum(1 for n in required if n[0] == "A"),
        "n_boundary_w2": sum(1 for n in required if n[0] in ("T", "B")),
        "n_nodes": len(required),
        "max_degree": max(len(v) for v in required.values()),
        "n_edges": sum(len(v) for v in required.values()) // 2,
        "weight4": (d - 1) ** 2,
        "weight2": 2 * (d - 1),
        "expected_nodes": 2 * d * d - 1,
    }
    return {"d": d, "required": required, "stats": stats}


# ---------------------------------------------------------------------------
# ② 必要条件（每条都自带「证明名」，判 IMPOSSIBLE 时点名）
# ---------------------------------------------------------------------------
def four_cycle(adj: Dict) -> Optional[Tuple]:
    """找一个 4-圈 `(u, v, w, x)`（u~v~w~x~u，四节点互不相同）；没有则 None。

    表面码的关联图**必然**含 4-圈：相邻两个稳定子交叠 2 个数据比特
    ⇒ `anc1 - datA - anc2 - datB - anc1`。这条是本层最锋利的**结构性**必要条件。
    """
    nbr = {u: set(v) for u, v in adj.items()}
    for u in adj:
        nu = nbr[u]
        for v in nu:
            for w in nbr[v]:
                if w == u or w in nu:
                    continue
                for x in nbr[w]:
                    if x != v and x != u and x in nu:
                        return (u, v, w, x)
    return None


def necessary_violations(req_adj: Dict, hw_adj: Dict) -> List[Dict]:
    """必要条件逐条核；返回违反项（空表 = 必要条件全过，**不等于可嵌入**）。"""
    out: List[Dict] = []
    if len(hw_adj) < len(req_adj):
        out.append({"proof": "node_count",
                    "detail": "硬件图 %d 个节点 < 关联图 %d 个节点"
                              % (len(hw_adj), len(req_adj))})
    req_deg = max(len(v) for v in req_adj.values())
    hw_deg = max((len(v) for v in hw_adj.values()), default=0)
    if hw_deg < req_deg:
        top = [n for n, v in req_adj.items() if len(v) == req_deg]
        # 证人优先取**内部稳定子**（物理上就是「权重 4 的检验」），其次数据比特
        witness = next((n for n in top if n[0] == "A"), top[0])
        n_anc4 = sum(1 for n in top if n[0] == "A")
        n_dat4 = sum(1 for n in top if n[0] == "D")
        out.append({"proof": "degree_bound",
                    "detail": "关联图有 %d 个度 %d 的节点（内部权重-4 稳定子 %d 个 / 数据比特 %d 个），"
                              "取证 %r；硬件图最大度只有 %d ⇒ 注入同态保持邻域数，必不可能"
                              % (len(top), req_deg, n_anc4, n_dat4, witness, hw_deg)})
    c_req = four_cycle(req_adj)
    if c_req is not None and four_cycle(hw_adj) is None:
        out.append({"proof": "four_cycle",
                    "detail": "关联图含 4-圈 %r（相邻稳定子交叠 2 个数据比特），"
                              "硬件图一个 4-圈都没有（树/围长 > 4）⇒ 必不可能"
                              % (c_req,)})
    return out


# ---------------------------------------------------------------------------
# ③ 搜索（穷尽 ⇔ 无解即为证明）与独立复核
# ---------------------------------------------------------------------------
def _order_nodes(req_adj: Dict) -> List:
    """确定性节点次序：先高度数，之后每步取「已定位邻居最多」者（约束最紧优先）。"""
    rest = sorted(req_adj, key=lambda n: (-len(req_adj[n]), str(n)))
    seq: List = []
    placed = set()
    while rest:
        best, best_key = None, None
        for n in rest:
            key = (-sum(1 for m in req_adj[n] if m in placed), -len(req_adj[n]), str(n))
            if best_key is None or key < best_key:
                best, best_key = n, key
        seq.append(best)
        placed.add(best)
        rest.remove(best)
    return seq


def embed(req_adj: Dict, hw_adj: Dict, budget: int = DEFAULT_BUDGET) -> Dict:
    """回溯子图同构（状态枚举 + **只用必要条件剪枝**）。

    🔴 剪枝只用**必要**条件（度数够大 / 已定邻居在硬件上相邻）⇒ 剪掉的候选一定不可行
    ⇒ 搜索**穷尽**时返回 `NONE` 是**无解的证明**；返回 `BUDGET` 只说明没搜完 ⇒ 上层记
    `UNKNOWN`。这条区分是本模块最重要的接口契约。
    """
    budget = int(budget)
    if budget <= 0:
        raise ValueError("budget 须为正整数")
    hw_deg = {n: len(v) for n, v in hw_adj.items()}
    need_deg = {n: len(v) for n, v in req_adj.items()}
    seq = _order_nodes(req_adj)
    cands = sorted(hw_adj, key=lambda n: (-hw_deg[n], n))
    assign: Dict = {}
    used = set()
    steps = [0]

    def feasible(node, cand) -> bool:
        if hw_deg[cand] < need_deg[node]:
            return False
        for m in req_adj[node]:
            if m in assign and assign[m] not in hw_adj[cand]:
                return False
        return True

    def dfs(i: int) -> bool:
        steps[0] += 1
        if steps[0] > budget:
            raise _Budget()
        if i == len(seq):
            return True
        node = seq[i]
        for cand in cands:
            if cand in used or not feasible(node, cand):
                continue
            assign[node] = cand
            used.add(cand)
            if dfs(i + 1):
                return True
            used.discard(cand)
            del assign[node]
        return False

    try:
        found = dfs(0)
    except _Budget:
        return {"status": "BUDGET", "steps": steps[0], "map": None}
    return {"status": "DIRECT" if found else "NONE", "steps": steps[0],
            "map": dict(assign) if found else None}


class _Budget(Exception):
    """内部：搜索预算用尽（**不是**无解）。"""


def verify_map(req_adj: Dict, hw_adj: Dict, mapping: Dict) -> Dict:
    """**独立**复核一个映射：注入 + 每条 required 边在硬件上存在 + 节点都在硬件图里。"""
    ok_domain = all(n in mapping for n in req_adj)
    targets = [mapping.get(n) for n in req_adj]
    injective = ok_domain and len(set(targets)) == len(targets)
    in_hw = ok_domain and all(t in hw_adj for t in targets)
    missing: List = []
    if ok_domain and in_hw and injective:
        for u, vs in req_adj.items():
            for v in vs:
                if mapping[v] not in hw_adj[mapping[u]]:
                    missing.append((u, v))
    ok = bool(ok_domain and injective and in_hw and not missing)
    return {"ok": ok, "injective": bool(injective), "in_hardware": bool(in_hw),
            "n_missing_edges": len(missing), "first_missing": missing[:3]}


# ---------------------------------------------------------------------------
# ④ 三值判决
# ---------------------------------------------------------------------------
def native_verdict(hw_adj: Dict, d: int, budget: int = DEFAULT_BUDGET) -> Dict:
    """`SC(d)` 能否原生嵌入硬件图：DIRECT / IMPOSSIBLE（附证明）/ UNKNOWN。"""
    sc = sc_tanner_graph(d)
    req = sc["required"]
    viol = necessary_violations(req, hw_adj)
    if viol:
        return {"status": STATUS_IMPOSSIBLE, "d": int(d), "proof": viol[0]["proof"],
                "detail": viol[0]["detail"], "violations": viol,
                "n_nodes_required": sc["stats"]["n_nodes"],
                "n_nodes_hw": len(hw_adj)}
    res = embed(req, hw_adj, budget=budget)
    if res["status"] == "DIRECT":
        ver = verify_map(req, hw_adj, res["map"])
        if not ver["ok"]:      # 理论上不会发生；发生了必须报出来而不是当成功
            return {"status": STATUS_UNKNOWN, "d": int(d), "proof": None,
                    "detail": "搜索给了映射但独立复核不过：%r" % (ver,),
                    "violations": [], "n_nodes_required": sc["stats"]["n_nodes"],
                    "n_nodes_hw": len(hw_adj)}
        return {"status": STATUS_DIRECT, "d": int(d), "proof": "explicit_map",
                "detail": "显式映射 %d 个节点，逐边在位（独立复核通过）" % len(res["map"]),
                "violations": [], "map_size": len(res["map"]), "steps": res["steps"],
                "n_nodes_required": sc["stats"]["n_nodes"],
                "n_nodes_hw": len(hw_adj)}
    if res["status"] == "NONE":
        return {"status": STATUS_IMPOSSIBLE, "d": int(d), "proof": "exhaustive_search",
                "detail": "必要条件全过，但搜索树**穷尽**（%d 步）后无解" % res["steps"],
                "violations": [], "n_nodes_required": sc["stats"]["n_nodes"],
                "n_nodes_hw": len(hw_adj)}
    return {"status": STATUS_UNKNOWN, "d": int(d), "proof": None,
            "detail": "预算 %d 步用尽仍未搜到 ⇒ 只说明没搜完，**不是**无解" % budget,
            "violations": [], "n_nodes_required": sc["stats"]["n_nodes"],
            "n_nodes_hw": len(hw_adj)}


# ---------------------------------------------------------------------------
# ⑤ 方阵最小边长（穷尽搜索标定 + 闭式表示，两处互拍）
# ---------------------------------------------------------------------------
def min_square_side(d: int, budget: int = DEFAULT_BUDGET) -> Dict:
    """方阵硬件图上 `SC(d)` 能落下的**最小边长**（逐 n 搜索，失败档也留痕）。"""
    from lda_qeda import sc_topology_core as TOPO
    sc = sc_tanner_graph(d)
    need = sc["stats"]["n_nodes"]
    n = 1
    while n * n < need:
        n += 1
    start_side = n        # 小于它的一律因**节点数**不足而无解（不是搜索结论）
    trace: List[Dict] = []
    while n <= 3 * int(d) + 2:
        hw = TOPO.grid_topology(n, n)["adjacency"]
        v = native_verdict(hw, d, budget=budget)
        trace.append({"n": n, "sites": n * n, "status": v["status"], "proof": v["proof"]})
        if v["status"] == STATUS_DIRECT:
            return {"d": int(d), "side": n, "sites": n * n, "status": STATUS_DIRECT,
                    "trace": trace, "required": need, "start_side": start_side}
        if v["status"] == STATUS_UNKNOWN:
            return {"d": int(d), "side": None, "status": STATUS_UNKNOWN,
                    "trace": trace, "required": need, "start_side": start_side}
        n += 1
    return {"d": int(d), "side": None, "status": STATUS_UNKNOWN, "trace": trace,
            "required": need, "start_side": start_side}


def min_square_side_closed(d: int) -> int:
    """**闭式表示**：方阵最小边长 = `2d − 1`。

    🔴 这不是推出来的定理，是 d = 2…5 **穷尽搜索**标定出来的模式（门禁 K6 逐值对拍
    `min_square_side(d)`）。所以它只能用于「量级/占位估算」，不得当定理引用。
    推论（同样是标定推论）：方阵占位 `(2d−1)²` 比码本体 `2d²−1` 多 **`2(d−1)²`** 个比特。
    """
    d = int(d)
    if d < 2:
        raise ValueError("表面码距离须 ≥ 2，收到 %r" % (d,))
    return 2 * d - 1


# ---------------------------------------------------------------------------
# ⑥ 自检
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    """常驻自检（13 项）：计数逐值 / 必要条件 / 反例 / 正例 / 预算语义 / 反向探针。"""
    from lda_qeda import sc_topology_core as TOPO
    bad: List[str] = []

    def chk(name: str, cond: bool, detail: str = "") -> None:
        if verbose:
            print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                                   ("  |  " + detail) if detail else ""))
        if not cond:
            bad.append(name)

    # ① 计数逐值（`==`，精确已知的组合量）
    ok_counts = True
    detail = []
    for d in (2, 3, 4, 5, 6):
        s = sc_tanner_graph(d)["stats"]
        ok_counts = ok_counts and (
            s["n_data"] == d * d and s["n_ancilla"] == d * d - 1
            and s["n_internal_w4"] == (d - 1) ** 2 and s["n_boundary_w2"] == 2 * (d - 1)
            and s["n_nodes"] == 2 * d * d - 1 and s["max_degree"] == 4)
        detail.append("d=%d:%d节点/度%d" % (d, s["n_nodes"], s["max_degree"]))
    chk("① 关联图计数逐值 ==（d² 数据 + (d−1)² 权重4 + 2(d−1) 权重2 = 2d²−1；最大度 4）",
        ok_counts, " ".join(detail))

    g3 = TOPO.grid_topology(5, 5)["adjacency"]
    g4 = TOPO.grid_topology(6, 6)["adjacency"]
    h3 = TOPO.heavy_hex_topology(3, 3)["adjacency"]
    tree = kary_tree(3, 24)

    # ② 必要条件：heavy-hex 度 3 ⇒ IMPOSSIBLE，且证明点名 degree_bound
    v_hex = native_verdict(h3, 3)
    chk("② heavy-hex（最大度 3）⇒ IMPOSSIBLE，证明 = degree_bound（内部权重 4 稳定子放不下）",
        v_hex["status"] == STATUS_IMPOSSIBLE and v_hex["proof"] == "degree_bound",
        v_hex["detail"])

    # ③ 反例（本模块存在的理由）：3-ary 树 最大度恰 4、24 节点 ≥ 17
    #    ⇒ 旧设计规则（max_degree ≥ 4 ⇒ DIRECT）会判 DIRECT，实际**可证不可能**
    tree_deg = max(len(v) for v in tree.values())
    sc3 = sc_tanner_graph(3)
    old_rule = tree_deg >= SC_NATIVE_MAX_DEGREE and len(tree) >= sc3["stats"]["n_nodes"]
    v_tree = native_verdict(tree, 3)
    chk("③ 反例：树（最大度 4、%d 节点）旧规则判 DIRECT=%s，实际 IMPOSSIBLE（证明=%s）"
        " ⇒ 度数规则只是必要条件" % (len(tree), old_rule, v_tree["proof"]),
        old_rule and v_tree["status"] == STATUS_IMPOSSIBLE
        and v_tree["proof"] == "four_cycle",
        v_tree["detail"])

    # ④ 正例：方阵 5×5（25 个比特）真能落下 d=3；映射由 verify_map **独立**复核
    v_g3 = native_verdict(g3, 3)
    r = embed(sc3["required"], g3)
    ver = verify_map(sc3["required"], g3, r["map"] or {})
    chk("④ 正例：方阵 5×5 可嵌 d=3（DIRECT）且 17 个节点逐边在位（独立复核 ok=%s）"
        % ver["ok"],
        v_g3["status"] == STATUS_DIRECT and ver["ok"], v_g3["detail"])

    # ⑤ 负例**不是节点数不够**：方阵 6×6 = 36 ≥ 31，但 d=4 仍无解（穷尽）
    v_g4 = native_verdict(g4, 4)
    chk("⑤ 方阵 6×6（36 站点 ≥ 31 节点）仍 IMPOSSIBLE，证明 = exhaustive_search"
        "（⇒ 下界不只是计数界）",
        v_g4["status"] == STATUS_IMPOSSIBLE and v_g4["proof"] == "exhaustive_search",
        v_g4["detail"])

    # ⑥ 预算用尽 ⇒ UNKNOWN，**不许**变成 IMPOSSIBLE（本模块最关键的语义）
    v_budget = native_verdict(g3, 3, budget=1)
    chk("⑥ 预算=1 步 ⇒ UNKNOWN（非 IMPOSSIBLE、非 DIRECT）—— 「搜不到」≠「不存在」",
        v_budget["status"] == STATUS_UNKNOWN and v_budget["proof"] is None,
        v_budget["detail"])

    # ⑦ 反向探针：把好映射改坏三种方式 ⇒ verify_map 必判红（复核器不是恒真）
    good = dict(r["map"])
    keys = sorted(good, key=str)
    broken_swap = dict(good)
    broken_swap[keys[0]], broken_swap[keys[1]] = good[keys[1]], good[keys[0]]
    broken_dup = dict(good)
    broken_dup[keys[1]] = good[keys[0]]
    broken_missing = {k: v for k, v in good.items() if k != keys[-1]}
    rej = [verify_map(sc3["required"], g3, m)["ok"]
           for m in (broken_swap, broken_dup, broken_missing)]
    chk("⑦ 反向探针：交换两项 / 复制目标 / 缺一项 ⇒ verify_map 三例全判红",
        rej == [False, False, False], "错误映射被判通过数 = %d/3" % sum(rej))

    # ⑧ 4-圈判据自身可证伪：方阵有 4-圈、树没有
    chk("⑧ 4-圈检测非恒真：方阵 5×5 有 4-圈 ∧ 3-ary 树没有",
        four_cycle(g3) is not None and four_cycle(tree) is None)

    # ⑨ 最小边长标定 ⇄ 闭式表示（两处表示必须对拍，d=2..5）
    sides = {d: min_square_side(d)["side"] for d in (2, 3, 4, 5)}
    chk("⑨ 方阵最小边长（穷尽搜索）≡ 闭式 2d−1（d=2..5 逐值）",
        all(sides[d] == min_square_side_closed(d) for d in sides),
        " ".join("d=%d:%s" % (k, v) for k, v in sides.items()))

    # ⑩ 占位开销闭式 (2d−1)² − (2d²−1) ≡ 2(d−1)²（精确已知的组合恒等式）
    worst = max(abs((2 * d - 1) ** 2 - (2 * d * d - 1) - 2 * (d - 1) ** 2)
                for d in range(2, 12))
    chk("⑩ 方阵占位开销 (2d−1)²−(2d²−1) ≡ 2(d−1)²（d=2..11 逐值，|Δ|=%d）" % worst,
        worst == 0)

    # ⑪ 必要条件**不等于**充分条件（把这句话做成判据，防以后有人又拿它当充分用）
    viol_tree = necessary_violations(sc3["required"], tree)
    chk("⑪ 必要条件与充分条件分离：树在 ③ 里已判 IMPOSSIBLE，但「必要条件违反表」"
        "非空只因 4-圈（度数与节点数都过）",
        all(v["proof"] != "degree_bound" for v in viol_tree)
        and any(v["proof"] == "four_cycle" for v in viol_tree))

    # ⑫ 非物理输入拦截
    n_bad = 0
    for fn, kw in ((sc_tanner_graph, {"d": 1}), (sc_tanner_graph, {"d": 0}),
                   (min_square_side_closed, {"d": 1}), (embed, {"budget": 0})):
        try:
            if fn is embed:
                fn(sc3["required"], g3, kw["budget"])
            else:
                fn(**kw)
        except ValueError:
            n_bad += 1
    chk("⑫ 非物理输入（d<2 / budget≤0）必须抛 ValueError", n_bad == 4,
        "拦截 %d/4" % n_bad)

    # ⑬ 映射是注入（不能两个码节点挤一个硬件比特）—— 顺带钉死「挤」是什么样
    squeezed = dict(good)
    squeezed[keys[1]] = good[keys[0]]
    chk("⑬ 注入性：好映射 targets 互异；挤占（两项同目标）被 verify_map 判注入失败",
        len(set(good.values())) == len(good)
        and verify_map(sc3["required"], g3, squeezed)["injective"] is False)

    if verbose:
        print("sc_embedding 自检：%d/%d PASS" % (len(bad) and 0 or 13 - len(bad), 13))
        print("FAIL: %s" % bad if bad else "ALL PASS")
    return not bad


def kary_tree(k: int, n_nodes: int) -> Dict[int, List[int]]:
    """k 叉树（根度 k、内部节点度 k+1）—— 用来造「最大度 4 但无 4-圈」的反例。"""
    k = int(k)
    n_nodes = int(n_nodes)
    if k < 1 or n_nodes < 2:
        raise ValueError("k ≥ 1 且节点数 ≥ 2")
    adj: Dict[int, List[int]] = {i: [] for i in range(n_nodes)}
    for i in range(1, n_nodes):
        p = (i - 1) // k
        adj[i].append(p)
        adj[p].append(i)
    return adj


if __name__ == "__main__":   # pragma: no cover
    print("J2 M4 表面码真嵌入（编译/映射）自检")
    ok = run_selfchecks(verbose=True)
    from lda_qeda import sc_topology_core as _T
    for d in (2, 3, 4, 5):
        ms = min_square_side(d)
        print("  d=%d 最小方阵边长=%s（%s 站点 / 码本体 %d）开销 %s"
              % (d, ms["side"], ms["sites"], ms["required"],
                 (ms["sites"] - ms["required"]) if ms["side"] else "—"))
    for name, adj in (("方阵 5×5", _T.grid_topology(5, 5)["adjacency"]),
                      ("heavy-hex 3×3", _T.heavy_hex_topology(3, 3)["adjacency"]),
                      ("3-ary 树(24)", kary_tree(3, 24))):
        v = native_verdict(adj, 3)
        print("  %-14s |V|=%3d 最大度=%d ⇒ %-10s 证明=%s"
              % (name, len(adj), max(len(x) for x in adj.values()),
                 v["status"], v["proof"]))
    sys.exit(0 if ok else 1)
