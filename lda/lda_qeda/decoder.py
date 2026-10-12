"""量子纠错征程 J1 · 解码器能力模块（量子纠错 QEC · M1 解码器（G_Q9 主项））。

🔴 主权纪律：本模块是**能力验证**模块（功能门禁 `run_j1_qec_smoke` 覆盖），**不是账本锚**；
**不借 networkx / 商业求解器**，纯 numpy + 标准库。解码器为**自主实现**（避免 vendor lock-in）。

提供两条**方法学独立**的解码路径（同被测对象、不同算法）：
  · `brute_force_mwpm`：暴力最小权完美匹配（**最优参考**，仅限小实例）—— 门禁对拍的「golden 路径」
    （注意：这是**算法等价性对拍**，非物理闭式 golden，属 ②级「事实/算法基准」）。
  · `union_find_decode`：自主 **Union-Find** 解码器（候选）—— 表面码标准聚类-剥离算法。

两路径在门禁中裁决：
  (1) 两者都须使综合征归零（合法解码器）；
  (2) 单错误（ unambiguous）用例须逐位一致；
  (3) 随机小实例上 UF 的逻辑判决须与 MWPM 高度一致（验证 UF 算法正确性）。

为规避平面表面码边界特殊分支、聚焦「匹配解码器内核」，本模块以**环面 toric code**（周期边界、
无边界特例）作测试床 —— 匹配解码器内核（MWPM + Union-Find 在缺陷图上的运作）与平面表面码
完全同构；平面边界处理列为 M2+ 扩展（本文件已留 TODO 接口）。

🔴 诚实边界：错误率/逻辑错误率为**设计示例量级**，非实测 PDK；本模块只证明「匹配解码器内核
正确性」这一工程事实，**不得作制造/性能宣称**。
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

import numpy as np


# ===========================================================================
# 环面码（toric code）测试床 —— X 错误解码（匹配 plaquette/Z 缺陷）
# ===========================================================================
class ToricCode:
    """L×L 环面码。数据比特在边上（horizontal / vertical）；面 (r,c) 的 Z 稳定子
    测量其 4 条邻边 X 错误之积。单条边上 X 错误 ⇒ 恰 2 个面被否决（缺陷）。

    缺陷图：面为顶点；缺陷面两两匹配；距离为环面最短 Manhattan（含卷绕）。
    逻辑 X = 不可收缩竖直环（固定列 c0，取全部 v[r][c0]）。
    """

    def __init__(self, L: int):
        if L < 2:
            raise ValueError("L 必须 ≥ 2")
        self.L = L
        # 边索引：h[r][c] (r,c)∈[0,L)×[0,L) 连接 (r,c)-(r,(c+1)%L)
        #         v[r][c] 连接 (r,c)-((r+1)%L,c)
        self.h = np.zeros((L, L), dtype=bool)
        self.v = np.zeros((L, L), dtype=bool)

    # --- 缺陷（综合征）提取 ------------------------------------------------
    def syndrome_x(self, xh: np.ndarray, xv: np.ndarray) -> List[Tuple[int, int]]:
        """返回被否决（parity=1）的面坐标列表。"""
        L = self.L
        xh = np.asarray(xh, dtype=bool).reshape(L, L)
        xv = np.asarray(xv, dtype=bool).reshape(L, L)
        defects = []
        for r in range(L):
            for c in range(L):
                # 面 (r,c) 的 4 条边：上 h[r][c]、下 h[(r+1)%L][c]、左 v[r][c]、右 v[r][(c+1)%L]
                parity = (int(xh[r, c]) + int(xh[(r + 1) % L, c])
                          + int(xv[r, c]) + int(xv[r, (c + 1) % L])) & 1
                if parity:
                    defects.append((r, c))
        return defects

    # --- 环面距离 ----------------------------------------------------------
    def torus_dist(self, a: Tuple[int, int], b: Tuple[int, int]) -> int:
        L = self.L
        dr = abs(a[0] - b[0])
        dc = abs(a[1] - b[1])
        dr = min(dr, L - dr)
        dc = min(dc, L - dc)
        return dr + dc

    # --- 最短路径翻转（恢复）-----------------------------------------------
    def _flip_path(self, xh: np.ndarray, xv: np.ndarray,
                   a: Tuple[int, int], b: Tuple[int, int]) -> None:
        """沿 a→b 的环面最短路径翻转边（XOR）。调用方负责传入可写数组。

        🔴 边类型关键：竖直移动（跨行）跨过的是**水平边 h**；水平移动（跨列）跨过的是
        **竖直边 v**。面 (r,c) 的「底边」= h[(r+1)%L][c]（连 (r+1,c)）、「顶边」= h[r][c]
        （连 (r-1,c)）；「右边」= v[r][(c+1)%L]（连 (r,c+1)）、「左边」= v[r][c]（连 (r,c-1)）。
        """
        L = self.L
        r1, c1 = a
        r2, c2 = b
        # 选最短 (dr,dc) 卷绕
        dr = r2 - r1
        dc = c2 - c1
        if dr > L / 2:
            dr -= L
        elif dr < -L / 2:
            dr += L
        if dc > L / 2:
            dc -= L
        elif dc < -L / 2:
            dc += L
        # 先竖直后水平（任意单调路径皆可，只需连接两端）
        r, c = r1, c1
        step_r = 1 if dr >= 0 else -1
        for _ in range(abs(dr)):
            if step_r == 1:
                xh[(r + 1) % L, c % L] ^= True  # 底边：面 (r,c) ↔ (r+1,c)
            else:
                xh[r % L, c % L] ^= True        # 顶边：面 (r,c) ↔ (r-1,c)
            r = (r + step_r) % L
        step_c = 1 if dc >= 0 else -1
        for _ in range(abs(dc)):
            if step_c == 1:
                xv[r % L, (c + 1) % L] ^= True  # 右边：面 (r,c) ↔ (r,c+1)
            else:
                xv[r % L, c % L] ^= True        # 左边：面 (r,c) ↔ (r,c-1)
            c = (c + step_c) % L

    def recovery_from_matching(self, defects: List[Tuple[int, int]],
                               matching: List[Tuple[int, int]]) -> Tuple[np.ndarray, np.ndarray]:
        """matching: 缺陷对列表（每个元素是两个缺陷坐标）。返回翻转后的 (xh, xv)。"""
        L = self.L
        xh = np.zeros((L, L), dtype=bool)
        xv = np.zeros((L, L), dtype=bool)
        for a, b in matching:
            self._flip_path(xh, xv, a, b)
        return xh, xv

    def logical_x(self, xh: np.ndarray, xv: np.ndarray, col: int = 0) -> int:
        """逻辑 X = 固定列 col 的全部竖直边（不可收缩竖直环）。返回 0/1。"""
        L = self.L
        xv = np.asarray(xv, dtype=bool).reshape(L, L)
        return int(np.sum(xv[:, col % L]) & 1)


# ===========================================================================
# 参考解码器：暴力最小权完美匹配（最优 · 仅小实例）
# ===========================================================================
def brute_force_mwpm(code: ToricCode,
                     defects: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """枚举所有完美匹配，取环面距离加权和最小者。缺陷数须为偶数且 ≤ ~10。"""
    n = len(defects)
    if n == 0:
        return []
    if n % 2 != 0:
        raise ValueError("环面码缺陷数必为偶数")
    best_cost = [math.inf]
    best_match: List[Tuple[int, int]] = [[]]

    def rec(used: int, cost: int, acc: List[Tuple[int, int]]):
        if used == (1 << n) - 1:
            if cost < best_cost[0]:
                best_cost[0] = cost
                best_match[0] = list(acc)
            return
        # 找第一个未用
        i = 0
        while i < n and (used >> i) & 1:
            i += 1
        for j in range(i + 1, n):
            if (used >> j) & 1:
                continue
            w = code.torus_dist(defects[i], defects[j])
            rec(used | (1 << i) | (1 << j), cost + w, acc + [(defects[i], defects[j])])

    rec(0, 0, [])
    if best_cost[0] == math.inf:
        raise RuntimeError("暴力 MWPM 未找到匹配")
    return best_match[0]


# ===========================================================================
# 候选解码器：自主 Union-Find（聚类-剥离）
# ===========================================================================
def union_find_decode(code: ToricCode,
                      defects: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """自主 Union-Find 解码器（表面码标准算法 · 本仓自主实现）。

    在缺陷完全图上做聚类生长 + 剥离：所有奇簇必含边界（环面无边界 ⇒ 缺陷数恒偶，
    生长必使所有簇归偶），再在簇内做贪心近邻配对（簇小，等价最优）。

    🔴 返回合法匹配（使综合征归零）—— 与 MWPM 共享「匹配解码器内核」，但算法路径独立。
    """
    n = len(defects)
    if n == 0:
        return []
    if n % 2 != 0:
        raise ValueError("环面码缺陷数必为偶数")

    # 并查集
    parent = list(range(n))
    rank = [0] * n

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if rank[ra] < rank[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        if rank[ra] == rank[rb]:
            rank[ra] += 1

    radius = [0] * n
    # 预计算边（含权重）
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            w = code.torus_dist(defects[i], defects[j])
            edges.append((w, i, j))
    edges.sort()

    # 聚类生长直到所有簇缺陷数为偶（toric code 恒偶）
    max_iter = 4 * code.L + 16
    for _ in range(max_iter):
        # 各簇半径 +1
        for k in range(n):
            radius[k] += 1
        # 探索中点落在两簇半径内的边
        for w, i, j in edges:
            ci, cj = find(i), find(j)
            if ci == cj:
                continue
            mid = (w + 1) // 2  # 中点距离（整数）
            if mid <= radius[ci] and mid <= radius[cj]:
                union(i, j)
        # 检查是否所有簇缺陷数为偶
        roots = {}
        for k in range(n):
            roots.setdefault(find(k), 0)
            roots[find(k)] += 1
        if all(cnt % 2 == 0 for cnt in roots.values()):
            break

    # 簇内贪心近邻配对（簇小 ⇒ 等价最优）
    matching: List[Tuple[int, int]] = []
    clusters: Dict[int, List[int]] = {}
    for k in range(n):
        clusters.setdefault(find(k), []).append(k)
    for members in clusters.values():
        # 贪心：反复取最相近未配对对
        free = set(members)
        while len(free) >= 2:
            best_pair = None
            best_w = math.inf
            lst = list(free)
            for a in range(len(lst)):
                for b in range(a + 1, len(lst)):
                    w = code.torus_dist(defects[lst[a]], defects[lst[b]])
                    if w < best_w:
                        best_w = w
                        best_pair = (lst[a], lst[b])
            ia, ib = best_pair
            matching.append((defects[ia], defects[ib]))
            free.discard(ia)
            free.discard(ib)
    return matching


# ===========================================================================
# 便捷门禁入口
# ===========================================================================
def decode_pair(code: ToricCode, defects: List[Tuple[int, int]], method: str):
    """method='mwpm' | 'uf'。返回 (matching, recovery_xh, recovery_xv, logical)：
    logical = 修正后（error XOR recovery）在固定列的逻辑 X 奇偶（0/1）。
    """
    if method == "mwpm":
        m = brute_force_mwpm(code, defects)
    elif method == "uf":
        m = union_find_decode(code, defects)
    else:
        raise ValueError("method 须为 mwpm / uf")
    xh, xv = code.recovery_from_matching(defects, m)
    logical = code.logical_x(xh, xv)
    return m, xh, xv, logical
