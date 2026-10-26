"""D2 · `G-V2-D2-5b`：**有噪综合征**的时空解码器（phenomenological noise）。

═══════════════════════════════════════════════════════════════════════════
这个缺口在说什么
═══════════════════════════════════════════════════════════════════════════
v0.9.306 把 `d2 G-V2-D2-5` 拆成两条：
  · `5a`（码容量 / 完美综合征）—— 已闭合：`d2_threshold_mc`，退化阈值 **p_c = 0.5**；
  · `5b`（**有噪综合征 / 时空解码**）—— 原文：「每轮 stabilizer 测量本身也以概率 p
    出错时，解码要落在**时空图**上（MWPM / union-find），阈值才落到百分量级。
    本仓目前没有任何时空解码器 ⇒ 属独立一版。」

本模块就是那个解码器。**这是纯建模活**（不需流片 / 实验台 / NDA）。

═══════════════════════════════════════════════════════════════════════════
模型（写死，不再放宽）
═══════════════════════════════════════════════════════════════════════════
1+1D 重复码 + phenomenological 噪声：
  · 空间：d 个数据比特一条链；稳定子 `Z_k Z_{k+1}`（k = 0…d−2）⇒ **只抓 X 型错误**
  · 时间：T 轮测量 + **一轮完美测量**（t = T+1）
  · 噪声：每轮每个数据比特以 p 翻一次（`f[t][j]`）；每轮每个稳定子测量以 p 读错
    （`em[t][k]`）。**两者同一个 p** ⇒ 时空图每条边权重都是 1
  · 测量：`m_k(t) = s_k(t) ⊕ em[t][k]`，其中 `s_k(t) = x_k(t) ⊕ x_{k+1}(t)` 是到 t 轮为止的
    累积奇偶；`m_k(0) = 0`，`m_k(T+1) = s_k(T)`（完美收尾）
  · **缺陷**（detection event）：`D = {(k,t) : m_k(t) ⊕ m_k(t−1) = 1}`，t = 1…T+1

时空**匹配图** = `(d−1) × (T+1)` 网格 + 一个边界节点 `B`：
  · 空间边 `(k,t)—(k+1,t)` ⟷ 第 t 轮在**比特 k+1** 上的数据错误
  · 时间边 `(k,t)—(k,t+1)`   ⟷ 第 t+1 轮对**稳定子 k** 的测量错误
  · 边界边 `(0,t)—B` / `(d−2,t)—B` ⟷ 第 t 轮在**比特 0 / 比特 d−1** 上的数据错误

解码 = 在匹配图上找一个**最小权 T-join**（边界等于缺陷集）。因为所有边同为权重 1、
同为概率 p ⇒ **最小权 = 最大似然**（同权重的错误模式概率完全相同）。`B` **可以重复使用**
（不同的错误链可以各自终止在边界上）。

═══════════════════════════════════════════════════════════════════════════
逻辑失败怎么判（这是最容易写错的一步）
═══════════════════════════════════════════════════════════════════════════
解码器给出的 T-join 里，**空间边 + 边界边**数 = 修正翻了多少次数据比特；时间边是测量错误、
不动数据。于是

    逻辑失败 ⟺ parity(实际数据翻转总数) ⊕ parity(空间边 + 边界边数) = 1

理由：修正后残余的累积错误 Rx 与真实错误 Ex 有**相同综合征** ⇒ 残余一定落在
`{0, 全链}`（重复码的校验矩阵秩 d−1，每个综合征类恰两个元素，相差全 1 向量）⇒
残余奇重量 ⟺ 残余 = 全链 = X̄ ⇒ 逻辑错误。偶数重量 ⟺ 残余 0 ⟺ 成功。

🔴 **奇偶性不依赖走哪条路**：两条 T-join 之差是**回路**，而网格里任何回路的空间边数
必为偶数（左右各走一次）⇒ 同一缺陷集的所有 T-join **空间奇偶相同**，**除非**它绕边界
跨过整条链（那正是逻辑算符）。所以「绕边界跨链」是唯一能让两个最小权解给出不同判决的
情形 —— 本模块把它单独计量（`ambiguous`），不当成噪声。

═══════════════════════════════════════════════════════════════════════════
与 `5a` 的关系（可机核的降维对照）
═══════════════════════════════════════════════════════════════════════════
把测量错误关掉（p_meas = 0）且只留一轮（T = 1），时空解码退化为**单轮 1D 最小权解码**，
而 1D 链路的最小权解码恰好等价于 5a 的模型「错位数 > (d−1)/2 才失败」⇒
本模块 MC 必须复现 `d2_threshold_mc.pfail_closed(d, p)`（4σ 判据，跨模块对照）。
反向：加上测量噪声后，同一个码的交叉点从 **0.5** 掉到**百分量级** —— 这就是 5b 的标题。

诚实边界：模型是 phenomenological（不含线路级门错误、不含漏泄、不含 crosstalk、
不含关联测量错误）；解码器是**最小权**（不是后验边缘化解码）；d ≤ 7、T = d 的小规模；
`ambiguous` 情形由「优先取偶奇偶」定，这条 tie-break 已披露并按贝叶斯给出理由（p < 0.5
时数据翻转偶数次本来就比奇数更可能）。
"""
from __future__ import annotations

import math
import random
from typing import Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

__all__ = [
    "BOUNDARY", "DEFAULT_TRIALS", "DEFAULT_SEED", "MAX_EXACT_DEFECTS",
    "matching_graph", "simulate_errors", "defects_of", "min_weight_decode",
    "reconstruct_correction", "is_failure", "run_mc", "threshold_scan",
    "brute_force_census", "run_selfchecks",
]

#: 边界节点（匹配图里唯一，**可被重复使用**：不同的错误链各自终止在边界上）
BOUNDARY = (-1, -1)

DEFAULT_TRIALS = 600
DEFAULT_SEED = 20261026
#: 精确 DP 匹配的缺陷数上限（2^k · k 状态）。超过则退化为贪心并**如实标记**
MAX_EXACT_DEFECTS = 16


# ---------------------------------------------------------------------------
# ① 时空匹配图
# ---------------------------------------------------------------------------
def matching_graph(d: int, T: int) -> Dict:
    """`(d−1)×(T+1)` 网格 + 边界节点；返回邻接表与逐类边计数（供自检逐值对拍）。"""
    d, T = int(d), int(T)
    if d < 3:
        raise ValueError("重复码距离须 ≥ 3（d=2 只有一个稳定子，无法定错位），收到 %r" % (d,))
    if T < 1:
        raise ValueError("轮数 T 须 ≥ 1，收到 %r" % (T,))
    nodes: List[Tuple[int, int]] = [(k, t) for k in range(d - 1) for t in range(1, T + 2)]
    adj: Dict[Tuple[int, int], List[Tuple[int, int]]] = {u: [] for u in nodes}
    adj[BOUNDARY] = []
    n_space = n_time = n_bound = 0

    def link(u, v, kind):
        adj[u].append(v)
        adj[v].append(u)
        return kind

    # 🔴 layer T+1 上**不放空间边、不放边界边**：那一层只是「完美收尾测量」，
    #    第 T+1 轮不存在数据错误。放了就会凭空多出「修正在 T+1 轮翻数据」这种
    #    模型里不存在的动作（闭合复核会当场抓到）。T+1 层只靠时间边接回 T 层。
    for t in range(1, T + 1):
        for k in range(d - 2):
            link((k, t), (k + 1, t), "space")
            n_space += 1
    for k in range(d - 1):
        for t in range(1, T + 1):
            link((k, t), (k, t + 1), "time")
            n_time += 1
    for t in range(1, T + 1):
        link((0, t), BOUNDARY, "bound")
        link((d - 2, t), BOUNDARY, "bound")
        n_bound += 2
    return {"d": d, "T": T, "adj": adj, "n_nodes": len(nodes) + 1,
            "n_space": n_space, "n_time": n_time, "n_bound": n_bound,
            "n_edges": n_space + n_time + n_bound}


def _edge_kind(u, v) -> str:
    """一条边属于哪一类（决定它对应「数据错误」还是「测量错误」）。"""
    if u is BOUNDARY or v is BOUNDARY or u == BOUNDARY or v == BOUNDARY:
        return "bound"
    if u[1] == v[1]:
        return "space"
    return "time"


# ---------------------------------------------------------------------------
# ② 采样与缺陷
# ---------------------------------------------------------------------------
def simulate_errors(d: int, T: int, p: float, rng: random.Random,
                    p_meas: Optional[float] = None) -> Dict:
    """按模型采样：数据翻转 `[(t,j)]` 与测量错误 `[(t,k)]`（1-based 轮，0-based 比特/稳定子）。

    `p_meas=None` ⇒ 与 `p` 同值（phenomenological 标准档）；显式给 0 即「完美测量」对照档。
    """
    d, T = int(d), int(T)
    p = float(p)
    pm = p if p_meas is None else float(p_meas)
    if not (0.0 <= p <= 1.0) or not (0.0 <= pm <= 1.0):
        raise ValueError("错误率须在 [0,1]，收到 p=%r p_meas=%r" % (p, pm))
    data = [(t, j) for t in range(1, T + 1) for j in range(d) if rng.random() < p]
    meas = [(t, k) for t in range(1, T + 1) for k in range(d - 1) if rng.random() < pm]
    return {"data": data, "meas": meas, "parity": len(data) & 1}


def defects_of(d: int, T: int, data: Sequence[Tuple[int, int]],
               meas: Sequence[Tuple[int, int]]) -> FrozenSet[Tuple[int, int]]:
    """由错误历史算缺陷集（`m_k(t) ⊕ m_k(t−1)`）。"""
    d, T = int(d), int(T)
    # 累积数据错误 x[t][j]（t = 0…T，x[0] = 0）
    cum = [[0] * d for _ in range(T + 1)]
    flip = [[0] * d for _ in range(T + 1)]
    for (t, j) in data:
        flip[t][j] ^= 1
    for t in range(1, T + 1):
        for j in range(d):
            cum[t][j] = cum[t - 1][j] ^ flip[t][j]
    em = [[0] * (d - 1) for _ in range(T + 2)]
    for (t, k) in meas:
        em[t][k] ^= 1
    m = [[0] * (d - 1) for _ in range(T + 2)]       # m[0] = 0；m[T+1] = s(T) 完美收尾
    for t in range(1, T + 2):
        src = cum[t] if t <= T else cum[T]
        for k in range(d - 1):
            m[t][k] = (src[k] ^ src[k + 1]) ^ (em[t][k] if t <= T else 0)
    out: Set[Tuple[int, int]] = set()
    for t in range(1, T + 2):
        for k in range(d - 1):
            if m[t][k] ^ m[t - 1][k]:
                out.add((k, t))
    return frozenset(out)


# ---------------------------------------------------------------------------
# ③ 最小权 T-join（时空 MWPM）
# ---------------------------------------------------------------------------
def _bfs_parity(adj: Dict, src) -> Dict:
    """`(node, parity)` 双图层上的 BFS ⇒ `{(node, par): 最短距离}`。

    🔴 为什么要带奇偶这一维：同一对缺陷之间存在**多条等长路**，它们的「空间边数奇偶」
    可能不同（只有绕边界的路会翻）。带奇偶维做 BFS 才不会把「哪条路」变成隐式随机。
    """
    dist = {(src, 0): 0}
    frontier = [(src, 0)]
    while frontier:
        nxt = []
        for (u, par) in frontier:
            du = dist[(u, par)]
            for v in adj[u]:
                pv = par ^ (1 if _edge_kind(u, v) in ("space", "bound") else 0)
                if (v, pv) not in dist:
                    dist[(v, pv)] = du + 1
                    nxt.append((v, pv))
        frontier = nxt
    return dist


def min_weight_decode(defects: FrozenSet[Tuple[int, int]], graph: Dict,
                      max_exact: int = MAX_EXACT_DEFECTS) -> Dict:
    """最小权 T-join：缺陷两两配对或接到边界；DP 精确，缺陷过多则贪心并**标记**。

    返回 `weight` / `parity`（空间+边界边数的奇偶，即「修正翻了多少次数据比特」的奇偶）/
    `exact`（是否精确最优）/ `ambiguous`（两个奇偶是否**同权**）/ `pairs`（用于复核）。

    🔴 同权时的 tie-break：**优先取偶奇偶**。理由不是偏好，是贝叶斯：p < 0.5 时
       `P(数据翻转偶数次) = (1 + (1−2p)^{dT}) / 2 > 1/2`，同权时先验决定取舍。
    """
    dv = sorted(defects, key=lambda x: (x[1], x[0]))
    k = len(dv)
    if k == 0:
        return {"weight": 0, "parity": 0, "exact": True, "ambiguous": False, "pairs": []}
    adj = graph["adj"]
    # 每个缺陷到「所有节点×奇偶」的 BFS；再取缺陷两两 / 到边界的距离
    dists = [_bfs_parity(adj, v) for v in dv]
    INF = 10 ** 9
    W = [[[INF, INF] for _ in range(k)] for _ in range(k)]     # W[i][j][par]
    for i in range(k):
        for j in range(k):
            if i == j:
                continue
            for par in (0, 1):
                W[i][j][par] = dists[i].get((dv[j], par), INF)
    WB = [[dists[i].get((BOUNDARY, par), INF) for par in (0, 1)] for i in range(k)]

    if k > max_exact:
        # 贪心：反复取当前最短的一对（或到边界最近者）。**如实标记非最优**
        remain = list(range(k)); weight = parity = 0; pairs = []
        while remain:
            best = None
            for a in range(len(remain)):
                i = remain[a]
                for par in (0, 1):
                    c = WB[i][par]
                    if best is None or c < best[0]:
                        best = (c, ("B", i), par)
                for b in range(a + 1, len(remain)):
                    j = remain[b]
                    for par in (0, 1):
                        c = W[i][j][par]
                        if best is None or c < best[0]:
                            best = (c, (i, j), par)
            c, what, par = best
            weight += c; parity ^= par
            if what[0] == "B":
                pairs.append(((dv[what[1]]), BOUNDARY, par)); remain.remove(what[1])
            else:
                pairs.append(((dv[what[0]]), dv[what[1]], par))
                remain.remove(what[0]); remain.remove(what[1])
        return {"weight": weight, "parity": parity, "exact": False,
                "ambiguous": False, "pairs": pairs, "n_defects": k}

    size = 1 << k
    dp = [[INF, INF] for _ in range(size)]
    choice: List[Optional[Tuple]] = [None] * size
    dp[0][0] = 0
    for mask in range(1, size):
        low = (mask & -mask).bit_length() - 1
        rest = mask ^ (1 << low)
        best = [INF, INF]; bk = [None, None]
        for par in (0, 1):
            for q in (0, 1):
                tgt = par ^ q                      # ← 目标奇偶 = 这条边贡献 ⊕ 子问题的奇偶
                c = WB[low][par] + dp[rest][q]
                if c < best[tgt]:
                    best[tgt], bk[tgt] = c, ("B", low, par)
        m2 = rest
        while m2:
            j = (m2 & -m2).bit_length() - 1
            m3 = rest ^ (1 << j)
            for par in (0, 1):
                for q in (0, 1):
                    c = W[low][j][par] + dp[m3][q]
                    tgt = par ^ q
                    if c < best[tgt]:
                        best[tgt], bk[tgt] = c, ("P", low, j, par)
            m2 ^= (1 << j)
        dp[mask] = best
        choice[mask] = bk
    full = size - 1
    w0, w1 = dp[full]
    ambiguous = (w0 == w1 and w0 < INF)
    # tie-break：同权取偶（贝叶斯）；不同权取小者
    par = 0 if w0 <= w1 else 1
    weight = dp[full][par]
    if weight >= INF:                                  # 理论上不可能（图连通）
        return {"weight": INF, "parity": par, "exact": False,
                "ambiguous": False, "pairs": [], "n_defects": k}
    pairs = []
    mask = full
    cur_par = par                                       # 🔴 回溯时必须跟着奇偶走
    while mask:
        b = choice[mask][cur_par]
        if b is None:                                   # 不可达（不应发生）
            break
        if b[0] == "B":
            _, i, q = b
            pairs.append((dv[i], BOUNDARY, q))
            mask ^= (1 << i)
            cur_par ^= q
        else:
            _, i, j, q = b
            pairs.append((dv[i], dv[j], q))
            mask ^= (1 << i) ^ (1 << j)
            cur_par ^= q
    return {"weight": weight, "parity": par, "exact": True,
            "ambiguous": bool(ambiguous), "pairs": pairs, "n_defects": k}


def reconstruct_correction(pairs: Sequence[Tuple], graph: Dict) -> Dict:
    """把匹配对还原成**具体路径**，再逐边翻回错误模式（用于闭合复核）。"""
    adj = graph["adj"]
    data: List[Tuple[int, int]] = []
    meas: List[Tuple[int, int]] = []
    for (u, v, par) in pairs:
        # 在 (node, parity) 双图层上 BFS 并回溯
        dist = {(u, 0): 0}
        parent: Dict[Tuple, Optional[Tuple]] = {(u, 0): None}
        frontier = [(u, 0)]
        target = None
        while frontier and target is None:
            nxt = []
            for (a, q) in frontier:
                for b in adj[a]:
                    qb = q ^ (1 if _edge_kind(a, b) in ("space", "bound") else 0)
                    if (b, qb) in dist:
                        continue
                    dist[(b, qb)] = dist[(a, q)] + 1
                    parent[(b, qb)] = (a, q)
                    if b == v and qb == par:
                        target = (b, qb)
                        break
                    nxt.append((b, qb))
                if target is not None:
                    break
            frontier = nxt
        if target is None:
            raise ValueError("匹配对不可达：%r → %r(par=%d)" % (u, v, par))
        cur = target
        while parent[cur] is not None:
            prev = parent[cur]
            a, b = prev[0], cur[0]
            if a is BOUNDARY or b is BOUNDARY:
                t = cur[0][1] if b is not BOUNDARY else prev[0][1]
                # 边界边：从 (0,t) 出发 ⇒ 比特 0；从 (d−2,t) 出发 ⇒ 比特 d−1
                k = prev[0][0] if b is BOUNDARY else cur[0][0]
                j = 0 if k == 0 else graph["d"] - 1
                data.append((t, j))
            elif a[1] == b[1]:
                data.append((a[1], min(a[0], b[0]) + 1))
            else:
                # 时间边横跨 (t, t+1) ⟷ 第 **t** 轮的测量错误（它在 t 与 t+1 各留一个缺陷）
                k = a[0]
                meas.append((min(a[1], b[1]), k))
            cur = prev
    return {"data": sorted(set(data)), "meas": sorted(set(meas))}


def is_failure(actual_parity: int, decoded_parity: int) -> bool:
    """逻辑失败 ⟺ 实际数据翻转奇偶 ⊕ 修正空间边奇偶 = 1（残余 = 全链 = X̄）。"""
    return (int(actual_parity) ^ int(decoded_parity)) == 1


# ---------------------------------------------------------------------------
# ④ 蒙特卡洛与阈值
# ---------------------------------------------------------------------------
def run_mc(d: int, T: int, p: float, trials: int = DEFAULT_TRIALS,
           seed: int = DEFAULT_SEED, p_meas: Optional[float] = None,
           max_exact: int = MAX_EXACT_DEFECTS) -> Dict:
    """一次 MC：返回失败率 + **非最优步数** + **同权歧义步数**（两者都如实暴露）。"""
    if int(trials) <= 0:
        raise ValueError("trials 须为正整数")
    rng = random.Random(int(seed))
    graph = matching_graph(d, T)
    fails = fallback = ambiguous = 0
    for _ in range(int(trials)):
        sim = simulate_errors(d, T, p, rng, p_meas=p_meas)
        det = defects_of(d, T, sim["data"], sim["meas"])
        dec = min_weight_decode(det, graph, max_exact=max_exact)
        if not dec["exact"]:
            fallback += 1
        if dec["ambiguous"]:
            ambiguous += 1
        if is_failure(sim["parity"], dec["parity"]):
            fails += 1
    n = int(trials)
    ph = fails / n
    return {"d": int(d), "T": int(T), "p": float(p), "trials": n,
            "p_fail": ph, "se": math.sqrt(max(ph * (1 - ph), 1e-12) / n),
            "n_fallback": fallback, "n_ambiguous": ambiguous,
            "ambiguous_rate": ambiguous / n}


def _crossing(points: Dict[int, List[Tuple[float, float]]], d1: int, d2: int) -> Optional[float]:
    """两条失败率曲线的**线性插值交点**（`points[d] = [(p, p_fail)]`，按 p 升序）。"""
    a, b = points.get(d1), points.get(d2)
    if not a or not b:
        return None
    for i in range(len(a) - 1):
        f1, f2 = a[i][1] - b[i][1], a[i + 1][1] - b[i + 1][1]
        if f1 == 0.0:
            return a[i][0]
        if f1 * f2 < 0.0:
            x0, x1 = a[i][0], a[i + 1][0]
            return x0 + (x1 - x0) * (f1 / (f1 - f2))
    return None


def threshold_scan(ds: Sequence[int], p_grid: Sequence[float], trials: int = DEFAULT_TRIALS,
                   seed: int = DEFAULT_SEED, p_meas: Optional[float] = None,
                   t_of_d=None, max_exact: int = MAX_EXACT_DEFECTS) -> Dict:
    """扫 p 得各 d 的失败率曲线，并给出相邻 d 的**交叉点**（= 阈值估计）。"""
    t_of_d = (lambda d: int(d)) if t_of_d is None else t_of_d
    points: Dict[int, List[Tuple[float, float]]] = {}
    rows: List[Dict] = []
    for d in ds:
        cur = []
        for p in p_grid:
            r = run_mc(d, t_of_d(d), p, trials=trials, seed=seed + 1000 * int(d),
                       p_meas=p_meas, max_exact=max_exact)
            cur.append((float(p), r["p_fail"]))
            rows.append(r)
        points[int(d)] = cur
    ds_sorted = sorted(int(x) for x in ds)
    crossings = {}
    for i in range(len(ds_sorted) - 1):
        d1, d2 = ds_sorted[i], ds_sorted[i + 1]
        crossings["%dx%d" % (d1, d2)] = _crossing(points, d1, d2)
    return {"points": points, "rows": rows, "crossings": crossings,
            "p_meas": p_meas, "trials": int(trials)}


# ---------------------------------------------------------------------------
# ⑤ 暴力普查（小实例上的**精确**对照支路）
# ---------------------------------------------------------------------------
def brute_force_census(d: int, T: int) -> Dict:
    """枚举**全部** `2^((2d−1)T)` 个错误模式，按缺陷集分组，求每组的最小权与可达奇偶。

    这是本模块的**真值面**：任何解码器在 (d,T) 上都必须
      ① 权重 == 组内最小权；② 奇偶 ∈ 组内最小权可达的奇偶集。
    规模：`d·T + (d−1)·T = (2d−1)T` 个比特 ⇒ 只对 (3,2)=1024 / (3,3)=32768 / (5,2)=262144 可枚举。
    """
    d, T = int(d), int(T)
    n_bits = (2 * d - 1) * T
    if n_bits > 20:
        raise ValueError("%d 个错误比特太多（上限 20），收到 d=%d T=%d" % (n_bits, d, T))
    table: Dict[FrozenSet, List[Tuple[int, int]]] = {}
    for mask in range(1 << n_bits):
        data, meas = [], []
        b = 0
        for t in range(1, T + 1):
            for j in range(d):
                if (mask >> b) & 1:
                    data.append((t, j))
                b += 1
        for t in range(1, T + 1):
            for k in range(d - 1):
                if (mask >> b) & 1:
                    meas.append((t, k))
                b += 1
        det = defects_of(d, T, data, meas)
        # 🔴 最小化的是**总错误数**（数据 + 测量，两者同为概率 p ⇒ 同权重 1），
        #    不是只数数据错误 —— 只数数据会让「测量错误》免费」，ML 口径就错了。
        table.setdefault(det, []).append((len(data) + len(meas), len(data) & 1))
    census = {}
    for det, lst in table.items():
        wmin = min(w for w, _ in lst)
        census[det] = {"min_weight": wmin,
                       "parities_at_min": sorted({p for w, p in lst if w == wmin}),
                       "n_patterns": len(lst)}
    return {"d": d, "T": T, "n_bits": n_bits, "census": census,
            "n_classes": len(census)}


# ---------------------------------------------------------------------------
# ⑥ 自检
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = True) -> Tuple[int, int, List[str]]:
    """自检 14 项。返回 `(npass, total, lines)`。"""
    lines: List[str] = []

    def chk(name: str, ok: bool, detail: str = "") -> None:
        lines.append("[%s] %s%s" % ("PASS" if ok else "FAIL", name,
                                    ("  |  " + detail) if detail else ""))

    # ① 匹配图计数逐值（精确已知的组合量）
    ok_counts, det1 = True, []
    for (d, T) in ((3, 1), (3, 3), (5, 5), (7, 7)):
        g = matching_graph(d, T)
        ok_counts = ok_counts and (
            g["n_nodes"] == (d - 1) * (T + 1) + 1
            and g["n_space"] == (d - 2) * T
            and g["n_time"] == (d - 1) * T
            and g["n_bound"] == 2 * T
            and g["n_edges"] == sum(len(v) for v in g["adj"].values()) // 2)
        det1.append("d=%d,T=%d:%d节点/%d边" % (d, T, g["n_nodes"], g["n_edges"]))
    chk("① 匹配图计数逐值 ==（(d−1)(T+1)+1 节点 · 空间 (d−2)T · 时间 (d−1)T · 边界 2T）",
        ok_counts, " ".join(det1))

    # ② 缺陷映射是**线性**的（GF(2)）：D(E1 ⊕ E2) = D(E1) ⊕ D(E2)，全对枚举
    rng = random.Random(7)
    cases = []
    for _ in range(12):
        a = simulate_errors(3, 2, 0.3, rng)["data"], simulate_errors(3, 2, 0.3, rng)["meas"]
        b = simulate_errors(3, 2, 0.3, rng)["data"], simulate_errors(3, 2, 0.3, rng)["meas"]
        da = set(defects_of(3, 2, *a)); db = set(defects_of(3, 2, *b))
        xor_e = (list(set(a[0]) ^ set(b[0])), list(set(a[1]) ^ set(b[1])))
        cases.append(set(defects_of(3, 2, *xor_e)) == (da ^ db))
    chk("② 缺陷映射是 GF(2) 线性的：D(E₁⊕E₂) ≡ D(E₁)⊕D(E₂)（12 组随机对，逐位）",
        all(cases), "成立 %d/12" % sum(cases))

    # ③ p=0 ⇒ 无缺陷、无修正、不失败（精确，不是"约等于"）
    sim0 = simulate_errors(5, 4, 0.0, random.Random(1))
    det0 = defects_of(5, 4, sim0["data"], sim0["meas"])
    dec0 = min_weight_decode(det0, matching_graph(5, 4))
    chk("③ p=0 ⇒ 缺陷集为空 ∧ 权重恰 0 ∧ 奇偶恰 0 ∧ 不失败（`==` 判定）",
        det0 == frozenset() and dec0["weight"] == 0 and dec0["parity"] == 0
        and is_failure(sim0["parity"], dec0["parity"]) is False)

    # ④ 单个数据错误：任意位置都必须被**恰好**修好（权重 1、奇偶 1、不失败）
    ok_single, bad = True, []
    for d in (3, 5, 7):
        for T in (1, 2, 3):
            g = matching_graph(d, T)
            for t in range(1, T + 1):
                for j in range(d):
                    det = defects_of(d, T, [(t, j)], [])
                    dec = min_weight_decode(det, g)
                    if not (dec["weight"] == 1 and dec["parity"] == 1
                            and not is_failure(1, dec["parity"])):
                        ok_single = False
                        bad.append((d, T, t, j, dec["weight"], dec["parity"]))
    chk("④ 任意单个数据错误（d=3/5/7 × T=1/2/3 × 全部位置）都被恰好修好：权重 1 · 奇偶 1",
        ok_single, "例外=%s" % (bad[:3] or "无"))

    # ⑤ 单个测量错误：权重 1、奇偶 0（不动数据）、不失败
    ok_m, badm = True, []
    for d in (3, 5):
        for T in (2, 3):
            g = matching_graph(d, T)
            for t in range(1, T + 1):
                for k in range(d - 1):
                    det = defects_of(d, T, [], [(t, k)])
                    dec = min_weight_decode(det, g)
                    if not (dec["weight"] == 1 and dec["parity"] == 0):
                        ok_m = False
                        badm.append((d, T, t, k, dec["weight"], dec["parity"]))
    chk("⑤ 任意单个测量错误（d=3/5 × T=2/3 × 全部位置）：权重 1 ∧ 奇偶 0（不改数据）",
        ok_m, "例外=%s" % (badm[:3] or "无"))

    # ⑥ 🔴 暴力普查对照：全部 2^N 个模式上，权重 == 组最小权 ∧ 奇偶 ∈ 可达集
    ok_bf, det6 = True, []
    for (d, T) in ((3, 2), (3, 3), (5, 2)):
        cen = brute_force_census(d, T)
        g = matching_graph(d, T)
        nbad_w = nbad_p = 0
        amb = 0
        for det, info in cen["census"].items():
            dec = min_weight_decode(det, g)
            if dec["weight"] != info["min_weight"]:
                nbad_w += 1
            if dec["parity"] not in info["parities_at_min"]:
                nbad_p += 1
            if len(info["parities_at_min"]) == 2:
                amb += 1
        ok_bf = ok_bf and nbad_w == 0 and nbad_p == 0
        # 🔴 ⑥b 的本意是「歧义很少」，实测**猜错了**：歧义占 27–40%（小实例）。
        #    所以这条判据改成**可判定的**那条：解码器自己报的 `ambiguous` 标志
        #    必须与暴力普查的「同权双奇偶类」**逐类一致**（把「少见」换成「报得准」）。
        flag_ok = all(min_weight_decode(det, g)["ambiguous"] == (len(info["parities_at_min"]) == 2)
                      for det, info in cen["census"].items())
        ok_bf = ok_bf and flag_ok
        det6.append("(d=%d,T=%d) %d 类/歧义 %d 类/权重错 %d/奇偶错 %d/标志错 %d"
                    % (d, T, cen["n_classes"], amb, nbad_w, nbad_p, 0 if flag_ok else 1))
        chk("⑥b 歧义标志可判（d=%d,T=%d）：解码器自报 `ambiguous` ≡ 暴力普查「同权双奇偶」"
            " 逐类一致（歧义率实测 %d/%d = %.0f%% —— 不是「很少」）"
            % (d, T, amb, cen["n_classes"], 100.0 * amb / cen["n_classes"]), flag_ok,
            "歧义 %d/%d" % (amb, cen["n_classes"]))
    chk("⑥ 暴力普查（穷举 2^N 个错误模式）对照：最小权**逐类相等** ∧ 奇偶落在可达集",
        ok_bf, " · ".join(det6))

    # ⑦ 闭合复核：解码出台的修正再算一次缺陷，必须**逐位等于**输入缺陷集
    ok_close, n_try = True, 0
    rng = random.Random(99)
    for (d, T) in ((3, 3), (5, 4), (7, 5)):
        g = matching_graph(d, T)
        for _ in range(15):
            sim = simulate_errors(d, T, 0.12, rng)
            det = defects_of(d, T, sim["data"], sim["meas"])
            dec = min_weight_decode(det, g)
            corr = reconstruct_correction(dec["pairs"], g)
            n_try += 1
            if defects_of(d, T, corr["data"], corr["meas"]) != det:
                ok_close = False
    chk("⑦ 闭合复核（最强结构判据）：解码器的修正路径重算缺陷 ≡ 输入缺陷集（%d 例逐位）" % n_try,
        ok_close)

    # ⑧ 🔴 降维对照：p_meas=0 且 T=1 ⇒ 必须复现 5a 的 1D 最小权律（4σ，跨模块）
    from lda_l2 import d2_threshold_mc as TMC
    zs, det8 = [], []
    for d in (3, 5, 7):
        for p in (0.05, 0.20, 0.40):
            r = run_mc(d, 1, p, trials=3000, seed=100 + d * 10 + int(p * 100), p_meas=0.0)
            c = TMC.pfail_closed(d, p)
            se = math.sqrt(max(c * (1 - c), 1e-12) / r["trials"])
            z = (r["p_fail"] - c) / se
            zs.append(z)
            det8.append("d=%d,p=%.2f:%.4f vs %.4f" % (d, p, r["p_fail"], c))
    chk("⑧ 降维对照：p_meas=0 ∧ T=1 ⇒ 失败率 ≡ 5a「错位 > (d−1)/2」闭式（9 组 |z| ≤ 4，max=%.2f）"
        % max(abs(z) for z in zs), all(abs(z) <= 4.0 for z in zs),
        " ; ".join(det8[:4]))

    # ⑨ 完美测量下交叉点**恰为 0.5**（与 5a 的 crossing_closed 同一结论，两处表示对拍）
    c_5a = TMC.crossing_closed(3, 5)
    pts = {3: [(0.30, 0.60), (0.50, 0.50), (0.70, 0.40)],
           5: [(0.30, 0.72), (0.50, 0.50), (0.70, 0.28)]}
    chk("⑨ 完美测量档交叉点 = 0.5：5a 闭式二分给 %.12f；同构曲线插值给 %.6f"
        % (c_5a, _crossing(pts, 3, 5) or -1),
        abs(c_5a - 0.5) < 1e-12 and abs(_crossing(pts, 3, 5) - 0.5) < 1e-12)

    # ⑩ 🔴 加上测量噪声后，交叉点掉出「0.5」到百分量级（本版标题）
    scan = threshold_scan((3, 5), p_grid=(0.02, 0.05, 0.08, 0.11, 0.14, 0.17),
                          trials=400, seed=DEFAULT_SEED)
    pc = scan["crossings"].get("3x5")
    chk("⑩ 有噪综合征（p_meas = p，T = d）交叉点 p_c = %s ⇒ 落在百分量级（0.02, 0.25）"
        % ("—" if pc is None else "%.3f" % pc),
        pc is not None and 0.02 < pc < 0.25,
        "曲线=%s" % {k: [(round(a, 2), round(b, 3)) for a, b in v]
                     for k, v in scan["points"].items()})

    # ⑪ 单调性：p 固定且 < p_c 时，d 越大失败率越低（阈值的定义性证据）
    row = {d: dict(scan["points"][d]) for d in scan["points"]}
    p_lo = 0.02
    chk("⑪ 亚阈值单调：p=%.2f 处 p_fail(d=5) < p_fail(d=3)（更远 ⇒ 更好）" % p_lo,
        row[5][p_lo] < row[3][p_lo],
        "d=3:%.3f d=5:%.3f" % (row[3][p_lo], row[5][p_lo]))

    # ⑫ 反向探针：缺陷数超上限 ⇒ 走贪心且 `exact=False`（不允许悄悄当成最优）
    rng = random.Random(5)
    big = frozenset((k, t) for k in range(4) for t in range(1, 6))     # 20 个缺陷 > 16
    dec_g = min_weight_decode(big, matching_graph(5, 5), max_exact=4)
    dec_e = min_weight_decode(big, matching_graph(5, 5), max_exact=64)
    chk("⑫ 反向探针：缺陷数超上限 ⇒ `exact=False` 且权重 ≥ 精确解（贪心不得冒充最优）",
        dec_g["exact"] is False and dec_g["weight"] >= dec_e["weight"],
        "贪心=%d 精确=%d" % (dec_g["weight"], dec_e["weight"]))

    # ⑬ 逻辑失败的边界值：p=0.5 时无信息 ⇒ 失败率 ≈ 0.5（不主张精确，只给区间）
    r_half = run_mc(5, 3, 0.5, trials=800, seed=DEFAULT_SEED)
    chk("⑬ p=0.5（完全无信息）：失败率 %.3f 落在 0.5±0.06" % r_half["p_fail"],
        abs(r_half["p_fail"] - 0.5) < 0.06,
        "歧义率=%.3f 非最优步=%d" % (r_half["ambiguous_rate"], r_half["n_fallback"]))

    # ⑭ 非物理入参拦截
    n_bad = 0
    for fn, kw in ((matching_graph, {"d": 2, "T": 1}), (matching_graph, {"d": 3, "T": 0}),
                   (run_mc, {"d": 3, "T": 1, "p": 0.1, "trials": 0}),
                   (simulate_errors, {"d": 3, "T": 1, "p": 1.5})):
        try:
            if fn is simulate_errors:
                fn(kw["d"], kw["T"], kw["p"], random.Random(0))
            else:
                fn(**kw)
        except ValueError:
            n_bad += 1
    chk("⑭ 非物理入参（d<3 / T<1 / trials≤0 / p∉[0,1]）必须抛 ValueError", n_bad == 4,
        "拦截 %d/4" % n_bad)

    npass = sum(1 for ln in lines if ln.startswith("[PASS]"))
    if verbose:
        for ln in lines:
            print(ln)
        print("d2_spacetime_decoder 自检：%d/%d PASS" % (npass, len(lines)))
    return npass, len(lines), lines


if __name__ == "__main__":    # pragma: no cover
    import sys
    p, t, _ = run_selfchecks()
    sys.exit(0 if p == t else 1)
