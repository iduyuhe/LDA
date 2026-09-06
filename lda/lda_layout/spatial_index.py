"""LDA L2 · 布线空间索引（P1 重写核心杠杆 · v0.9.52）。

根除旧 ``router.py`` 的根因：每次布线都把**全部**障碍重栅格化进 ``blocked``、
``_path_hits`` 每次遍历**全部**障碍——端到端 O(N^3.57)，~50 网即失工程可用性。

本模块用均匀网格哈希（uniform grid hash）把障碍包围盒
``[(cx, cy, hw, hh)]`` 离散进网格，``query_rect`` 只回**局部**障碍
（O(局部) 而非 O(全部)），作为路由加速的第一杠杆。

红线（与全局一致）：
  - 纯算术（dict 网格），零新依赖，LLM 不进判决路径；
  - 索引只影响「查询哪些障碍」，不改 A* 的可解性 / 最优性 / 路径判定。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

# 障碍包围盒：(center_x, center_y, half_width, half_height)
Obstacle = Tuple[float, float, float, float]


class ObstacleIndex:
    """均匀网格哈希空间索引：插入障碍、查询矩形窗口内的局部障碍。

    用法（单 net 加速）：
        idx = ObstacleIndex(obstacles)        # O(N) 建索引一次
        local = idx.query_rect(x0, y0, x1, y1)  # O(局部格 + 命中障碍数)

    用法（增量布线，多 net 共享）：
        router = Router(static_obstacles)     # 内部持有一个 ObstacleIndex
        router.route_all(nets)                # 每条 net 只查附近障碍 + 已布路径回填

    正确性护栏：``query_rect`` 返回「包围盒与查询矩形相交」的全部障碍；
    A* 栅格化只取局部障碍，但 A* 搜索域由全局 extent 决定（见 router_p1），
    二者配合保证：局部障碍集对「最优路径所在走廊」是充分的 → 路径与旧 router 一致。
    """

    def __init__(self, obstacles: Sequence[Obstacle], cell: float = 50.0) -> None:
        self.cell = float(cell)
        self._obstacles: List[Obstacle] = []
        self._grid: Dict[Tuple[int, int], List[int]] = {}
        # (gmin_x, gmax_x, gmin_y, gmax_y) —— 所有障碍的整体外接范围
        self.global_extent = (float("inf"), float("-inf"),
                              float("inf"), float("-inf"))

        for o in obstacles:
            self.insert(o[0], o[1], o[2], o[3])

    # -- 写入 --------------------------------------------------------------
    def insert(self, cx: float, cy: float, hw: float, hh: float) -> int:
        """插入一个障碍包围盒，返回其索引。线程不安全（单机串行布线）。"""
        idx = len(self._obstacles)
        self._obstacles.append((cx, cy, hw, hh))

        # 更新整体 extent（供 A* 搜索域边界使用）
        gx0, gx1, gy0, gy1 = self.global_extent
        gx0 = min(gx0, cx - hw)
        gx1 = max(gx1, cx + hw)
        gy0 = min(gy0, cy - hh)
        gy1 = max(gy1, cy + hh)
        self.global_extent = (gx0, gx1, gy0, gy1)

        # 离散进覆盖的网格单元
        c0x = int(math.floor((cx - hw) / self.cell))
        c1x = int(math.floor((cx + hw) / self.cell))
        c0y = int(math.floor((cy - hh) / self.cell))
        c1y = int(math.floor((cy + hh) / self.cell))
        for gx in range(c0x, c1x + 1):
            for gy in range(c0y, c1y + 1):
                self._grid.setdefault((gx, gy), []).append(idx)
        return idx

    def insert_path(self, pts: Sequence[Tuple[float, float]], wg_half: float) -> None:
        """把一条已布线（折点序列）逐段转成薄包围盒并插入，供后续 net 避让。

        语义：已布网成为后续网的障碍 → 网-网避障（net-net avoidance）。
        逐段建薄 bbox（比整条路径单 bbox 更精确，避免过度阻挡相邻走廊）。
        """
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            cx = (a[0] + b[0]) / 2.0
            cy = (a[1] + b[1]) / 2.0
            hw = abs(b[0] - a[0]) / 2.0 + wg_half
            hh = abs(b[1] - a[1]) / 2.0 + wg_half
            self.insert(cx, cy, hw, hh)

    # -- 查询 --------------------------------------------------------------
    def query_rect(self, x0: float, y0: float, x1: float, y1: float) -> List[Obstacle]:
        """返回包围盒与矩形 [x0,x1]×[y0,y1] 相交的全部障碍。

        复杂度：O(覆盖格数 + 命中障碍数)，与障碍总数 N 无关 → 大规模下为 O(局部)。
        """
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        cx0 = int(math.floor(x0 / self.cell))
        cx1 = int(math.floor(x1 / self.cell))
        cy0 = int(math.floor(y0 / self.cell))
        cy1 = int(math.floor(y1 / self.cell))

        seen: set = set()
        out: List[Obstacle] = []
        for gx in range(cx0, cx1 + 1):
            for gy in range(cy0, cy1 + 1):
                for idx in self._grid.get((gx, gy), ()):
                    if idx in seen:
                        continue
                    seen.add(idx)
                    ocx, ocy, ohw, ohh = self._obstacles[idx]
                    # 轴对齐包围盒相交测试（充分必要）
                    if (ocx - ohw <= x1 and ocx + ohw >= x0
                            and ocy - ohh <= y1 and ocy + ohh >= y0):
                        out.append(self._obstacles[idx])
        return out

    @property
    def n_obstacles(self) -> int:
        return len(self._obstacles)

    def query_window(self, xmin: float, xmax: float, ymin: float, ymax: float
                     ) -> List[Obstacle]:
        """query_rect 的窗口元组友好版：参数顺序与 grid_window 一致
        ``(xmin, xmax, ymin, ymax)``，避免 ``*window`` 解包错位（曾导致
        坐标顺序错乱、返回空集 → 漏避障）。"""
        return self.query_rect(xmin, ymin, xmax, ymax)
