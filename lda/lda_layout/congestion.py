"""LDA L1/L2 · 布线拥塞图（congestion map · v0.8.42 · S2-② 布线层纵深）。

价值（真实 EDA 布线流程的 congestion-aware routing）：
  逐网串行布线时，纯 A* 只避障碍、不考虑「已布线通道的拥挤度」——
  先布的网占据的走廊不会阻止后续网穿过，导致多网密集场景（并行总线、
  阵列布线、真实 PIC 版图）下所有网挤进同一条通道：局部过密（散热/
  串扰风险）、间距违规风险高。
  拥塞图记录「每网格已布线路径占用次数」，A* 启发式叠加拥塞惩罚项
  → 引导后续网绕开拥挤走廊，均衡全局通道利用率。

红线下护栏（与全局一致）：
  - 拥塞图**只影响启发式**（h 加非负惩罚），不阻塞任何格点、不改变可解性
    （有解必有解）；唯一影响是路径选择（绕行 vs 挤同走廊）。
  - LLM 不进判决路径——拥塞查询是纯算术（计数）。
  - 零新依赖（纯 dict 网格），可选 numba 加速（v0.8.42 ④ 有 numba 用之）。

与判决的关系：route_net/astar_route 的 congestion 参数**默认 None**——
不传则行为与改造前逐位一致（回归保护）；传入才启用拥塞感知绕行。
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

# 默认网格分辨率（与 astar_route dl 一致）
DEFAULT_DL = 1.0
# 默认拥塞惩罚系数（h 中每单位容量的额外代价，单位 µm——A* 用长度代价，
# 惩罚等效于「绕行 N µm」的权衡；>0 即引导绕行，0 = 关闭）
DEFAULT_PENALTY = 4.0


class CongestionMap:
    """均匀网格拥塞图：格点占用计数 + 路径标记 + 惩罚查询。

    确定性、可复现（dict 计数），LLM 不进判决（纯算术）。
    """

    def __init__(self, dl: float = DEFAULT_DL,
                 penalty: float = DEFAULT_PENALTY) -> None:
        self.dl = float(dl)
        self.penalty = float(penalty)
        self.origin = (0.0, 0.0)          # 世界坐标原点（可 set_origin 对齐网格）
        self.counts: Dict[Tuple[int, int], int] = {}

    # -- 网格换算 ----------------------------------------------------------
    def set_origin(self, ox: float, oy: float) -> None:
        """设定网格原点（对齐搜索域，避免负格号/精度漂移）。"""
        self.origin = (float(ox), float(oy))

    def _cell(self, x: float, y: float) -> Tuple[int, int]:
        ox, oy = self.origin
        return (round((x - ox) / self.dl), round((y - oy) / self.dl))

    # -- 标记 --------------------------------------------------------------
    def mark_path(self, pts: Sequence[Tuple[float, float]]) -> None:
        """登记一条已布线路径（逐段按网格采样计数，含端点）。

        语义：路径经过的每个格点占用 +1。后续网的惩罚查询据此引导绕行。
        """
        if len(pts) < 2:
            return
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            self._mark_segment(a, b)

    def _mark_segment(self, a: Tuple[float, float],
                      b: Tuple[float, float]) -> None:
        """线段 a→b 经过的格点全部 +1（DDA 风格，确定性）。"""
        x0, y0 = a
        x1, y1 = b
        dx = x1 - x0
        dy = y1 - y0
        steps = max(int(abs(dx) / self.dl), int(abs(dy) / self.dl), 1)
        for k in range(steps + 1):
            t = k / steps
            cx = self._cell(x0 + dx * t, y0 + dy * t)
            self.counts[cx] = self.counts.get(cx, 0) + 1

    # -- 查询 --------------------------------------------------------------
    def occupancy(self, x: float, y: float) -> int:
        """格点占用次数（未标记 = 0）。"""
        return self.counts.get(self._cell(x, y), 0)

    def penalty_at(self, x: float, y: float) -> float:
        """拥塞惩罚代价（µm 单位，叠加到 A* g 或 h）。"""
        return self.penalty * self.counts.get(self._cell(x, y), 0)

    # -- 统计（供 smoke/报告）-----------------------------------------------
    def stats(self) -> Dict[str, float]:
        """拥塞分布统计：最大占用 / 平均占用 / 拥挤格点数。"""
        if not self.counts:
            return {"max_occupancy": 0, "avg_occupancy": 0.0, "n_crowded": 0}
        vals = list(self.counts.values())
        n = len(vals)
        mx = max(vals)
        avg = sum(vals) / n
        crowded = sum(1 for v in vals if v >= 2)
        return {"max_occupancy": mx, "avg_occupancy": round(avg, 3),
                "n_crowded": crowded, "n_cells": n}

    def to_summary(self) -> str:
        s = self.stats()
        return (f"拥塞图: {s['n_cells']} 格 · 最大占用 {s['max_occupancy']} · "
                f"平均 {s['avg_occupancy']} · 拥挤格 {s['n_crowded']}")
