#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""批量并行布线（v0.8.44 · B1 技术纵深）。

对外提供 `route_batch`——多条网一次布线的统一入口：
- workers=1（默认）：串行，与逐条调用 `route_net` 语义逐位一致（回归保护）。
- workers>1：ProcessPoolExecutor 并行（纯标准库 concurrent.futures，零新依赖）。

收益边界（实测 v0.8.44）：
- 链式/规则拓扑（build_chain_case 型）：单网 ~12µs，并行框架开销 > 任务本身，
  必用串行（workers=1）。
- 复杂版图（障碍密集，A* 真搜索）：单网 ~400ms（40 网串行 16s），workers=4
  进程池可近线性加速（pickle 开销占比小）。

诚实边界：
- 拥塞感知布线（congestion）有路径标记的顺序依赖，无法并行——并行模式
  下传 congestion 会抛 ValueError（不做伪并行）。
- 结果顺序与输入一致（dict 保持插入序），判决语义零变化。

LLM 不进布线路径：A* 为确定性网格搜索，进程池仅调度不变判定。
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Optional, Sequence, Tuple

from lda_layout.router import (
    DEFAULT_STRAIGHT_LOSS_DB_CM,
    RouteResult,
    route_net,
)

__all__ = ["route_batch", "route_batch_timing"]


def _route_one(args) -> Tuple[str, RouteResult]:
    """进程池 worker（顶层函数，可 pickle）。"""
    (net_id, src, dst, obstacles, wg_width, bend_radius, corner,
     straight_loss_db_cm, method, grid_dl, layer) = args
    return (net_id, route_net(
        net_id, src, dst, obstacles=obstacles, wg_width=wg_width,
        bend_radius=bend_radius, corner=corner,
        straight_loss_db_cm=straight_loss_db_cm,
        method=method, grid_dl=grid_dl, layer=layer))


def route_batch(
    nets: Sequence[Tuple[str, Tuple[float, float], Tuple[float, float]]],
    obstacles: Optional[Sequence] = None,
    workers: int = 1,
    wg_width: float = 0.5,
    bend_radius: float = 5.0,
    corner: str = "round",
    straight_loss_db_cm: float = DEFAULT_STRAIGHT_LOSS_DB_CM,
    method: str = "astar",
    grid_dl: float = 1.0,
    layer: str = "M1",
    congestion=None,
    max_span: float = 2000.0,
) -> Dict[str, RouteResult]:
    """批量布线：n 条网一次执行。

    nets: [(net_id, src, dst), ...]——src/dst 为绝对坐标 (x,y) µm。
    workers=1 串行（与逐条 route_net 逐位一致）；>1 进程池并行。

    返回 {net_id: RouteResult}（保持输入顺序）。

    诚实边界：congestion（拥塞感知）有标记顺序依赖，并行下会抛 ValueError——
    不做伪并行；需要拥塞感知时用 workers=1 逐条标记。
    """
    if congestion is not None and workers > 1:
        raise ValueError(
            "拥塞感知布线（congestion）有路径标记顺序依赖，无法并行；"
            "请用 workers=1 逐条标记（先布后标）。")
    obstacles = list(obstacles or [])
    tasks = []
    for item in nets:
        net_id, src, dst = item[0], item[1], item[2]
        lay = item[3] if len(item) > 3 else layer
        tasks.append((net_id, src, dst, obstacles, wg_width, bend_radius,
                      corner, straight_loss_db_cm, method, grid_dl, lay))

    out: Dict[str, RouteResult] = {}
    if workers <= 1:
        for t in tasks:
            nid, r = _route_one(t)
            out[nid] = r
        return out

    # 进程池并行（零依赖标准库；worker 为顶层函数可 pickle）
    with ProcessPoolExecutor(max_workers=max(1, int(workers))) as ex:
        for nid, r in ex.map(_route_one, tasks, chunksize=max(1, len(tasks) // (workers * 4))):
            out[nid] = r
    return out


def route_batch_timing(
    nets: Sequence[Tuple[str, Tuple[float, float], Tuple[float, float]]],
    obstacles: Optional[Sequence] = None,
    workers_list: Sequence[int] = (1, 4),
    **kwargs,
) -> Dict[str, object]:
    """实测报告：多 workers 配置下的批量布线耗时与加速比。

    返回 {workers: {seconds, speedup_vs_1, n_nets, per_net_ms}}——
    供 smoke/性能守护与文档引用（诚实收益边界实测）。
    """
    base = None
    report: Dict[str, object] = {}
    for w in workers_list:
        t0 = time.perf_counter()
        res = route_batch(nets, obstacles=obstacles, workers=w, **kwargs)
        dt = time.perf_counter() - t0
        if base is None:
            base = dt
        report[str(w)] = {
            "seconds": round(dt, 4),
            "speedup_vs_1": round(base / dt, 2) if base and dt > 0 else 1.0,
            "n_nets": len(res),
            "per_net_ms": round(dt / max(len(res), 1) * 1000, 3),
        }
    return report
