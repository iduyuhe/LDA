"""P1 布线器规模基准（v0.9.52）：旧 router 增量布线 vs 新 P1 Router。

忠实复刻规模评估 doc 的「端到端增量布线」场景（docs/lda_million_scale_assessment_*.md
第 5 节）：每布一条 net，把其已布路径回填为障碍，供后续 net 避让 → 障碍集随网数
线性增长。旧 router 每次对**全部**障碍重栅格化 + 碰撞检测 → 端到端 O(N^3.57)；
新 P1 用空间索引只取附近障碍 → 目标 O(N log N)。

运行：python bench_router_scale.py
输出：N=10..320 旧/新耗时表 + 实测 log-log 增长阶 + 加速比。

红线：所有结论来自**实测**，不臆测增长阶；规模结论必须实测（铁律）。
"""
from __future__ import annotations

import math
import random
import time
from typing import Dict, List, Tuple

from lda_layout.router import route_net
from lda_layout.router_p1 import Router

WG_WIDTH = 0.5
WG_HALF = WG_WIDTH / 2.0
CHIP = 2000.0          # µm 边长（大芯片，网分布稀疏 → 索引优势显著）
R_LOCAL = 150.0        # 每条 net 端点最大间距（局部短跳，贴合真实 PIC 布线）
N_STATIC = 10          # 静态器件障碍数
SEED = 20260906


def _path_bbox(pts: List[Tuple[float, float]], wg_half: float) -> Tuple[float, float, float, float]:
    """把一条已布路径转成单个包围盒障碍（与旧 router 障碍表示一致）。"""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    hw = (max(xs) - min(xs)) / 2.0 + wg_half
    hh = (max(ys) - min(ys)) / 2.0 + wg_half
    return (cx, cy, hw, hh)


def make_scenario(n_nets: int, seed: int = SEED):
    """生成 n_nets 条**局部** net（端点间距 ≤ R_LOCAL）+ N_STATIC 个静态障碍。

    局部短跳贴合真实 PIC 布线（网-网多数局部互连），使空间索引的「只查附近障碍」
    优势最大化，且多数 net 可成功布线（连通率高 → 测得的是真实布线耗时，非退化直连）。
    """
    rng = random.Random(seed)
    static = []
    for _ in range(N_STATIC):
        cx = rng.uniform(100, CHIP - 100)
        cy = rng.uniform(100, CHIP - 100)
        hw = rng.uniform(15, 40)
        hh = rng.uniform(15, 40)
        static.append((cx, cy, hw, hh))
    nets = []
    for i in range(n_nets):
        a = (rng.uniform(0, CHIP), rng.uniform(0, CHIP))
        # dst 落在以 a 为圆心、R_LOCAL 为半径的盘内（夹紧到 chip 内）
        ang = rng.uniform(0, 2 * math.pi)
        rad = rng.uniform(0, R_LOCAL)
        b = (min(CHIP, max(0, a[0] + rad * math.cos(ang))),
             min(CHIP, max(0, a[1] + rad * math.sin(ang))))
        nets.append((f"net_{i}", a, b))
    return static, nets


def old_incremental(static, nets):
    """复刻 doc 场景：逐网 route_net，已布路径回填为障碍（障碍集线性增长）。"""
    placed = list(static)
    results: Dict[str, object] = {}
    for nid, s, d in nets:
        rr = route_net(nid, s, d, obstacles=placed, wg_width=WG_WIDTH)
        results[nid] = rr
        if not rr.blocked:
            placed.append(_path_bbox(rr.points_um, WG_HALF))
    return results


def new_incremental(static, nets):
    """P1：空间索引 + 增量占位，全部 net 共享一个索引。"""
    router = Router(static, wg_width=WG_WIDTH, detour_margin=150.0)
    return router.route_all(nets)


def _fit_growth(ns, times):
    """log-log 最小二乘拟合增长阶 slope（time ∝ N^slope）。"""
    pts = [(math.log(n), math.log(t)) for n, t in zip(ns, times) if t > 0]
    if len(pts) < 2:
        return float("nan")
    n = len(pts)
    sx = sum(p[0] for p in pts)
    sy = sum(p[1] for p in pts)
    sxx = sum(p[0] * p[0] for p in pts)
    sxy = sum(p[0] * p[1] for p in pts)
    denom = n * sxx - sx * sx
    if denom == 0:
        return float("nan")
    return (n * sxy - sx * sy) / denom


def main() -> int:
    import sys
    print("P1 布线器规模基准：旧增量布线 vs 新 P1 Router（实测）", flush=True)
    print(f"  CHIP={CHIP}µm · 静态障碍={N_STATIC} · wg={WG_WIDTH}µm · seed={SEED}", flush=True)
    # 新 router 跑全序列；旧 router 为 O(N^3) 类，单 N 超预算即停止（与 doc
    # 自证「40 网≈12s」一致——更高 N 已超出可行 CI 时间，故封顶采样）。
    NEW_NS = [10, 20, 40, 80, 160, 320]
    OLD_NS = [10, 20, 40, 80]
    OLD_BUDGET_S = 90.0  # 单 N 旧 router 计时上限（秒）；超时则停止旧采样

    new_times, old_times = {}, {}
    print(f"\n{'N':>5} | {'old(s)':>10} | {'new(s)':>10} | {'speedup':>8} | {'old连':>6} | {'new连':>6}", flush=True)
    print("-" * 64, flush=True)
    for n in NEW_NS:
        static, nets = make_scenario(n, SEED)
        if n in OLD_NS:
            t0 = time.perf_counter()
            ro = old_incremental(static, nets)
            to = time.perf_counter() - t0
            old_times[n] = to
            old_conn = sum(1 for r in ro.values() if not r.blocked)
            if to > OLD_BUDGET_S:
                print(f"  (旧 router N={n} 用时 {to:.1f}s 已超预算 {OLD_BUDGET_S:.0f}s，"
                      f"停止旧采样——与 doc 自证 O(N^3) 一致)", flush=True)
                OLD_NS = [m for m in OLD_NS if m <= n]
        else:
            to = float("nan")
            old_conn = 0
        t0 = time.perf_counter()
        rn = new_incremental(static, nets)
        tn = time.perf_counter() - t0
        new_times[n] = tn
        new_conn = sum(1 for r in rn.values() if not r.blocked)
        spd = (to / tn) if (tn > 0 and to == to) else float("inf")
        print(f"{n:>5} | {to:>10.3f} | {tn:>10.3f} | {spd:>7.1f}x | {old_conn:>6} | {new_conn:>6}", flush=True)

    # 增长阶拟合（仅对有效时间）
    old_valid = [(n, old_times[n]) for n in OLD_NS if n in old_times]
    new_valid = [(n, new_times[n]) for n in NEW_NS if n in new_times]
    old_slope = _fit_growth(*zip(*old_valid)) if len(old_valid) >= 2 else float("nan")
    new_slope = _fit_growth(*zip(*new_valid)) if len(new_valid) >= 2 else float("nan")

    print("\n实测增长阶（time ∝ N^slope，log-log 最小二乘）：", flush=True)
    print(f"  旧 router 增量布线：slope ≈ {old_slope:.2f}  (采样 N={[n for n,_ in old_valid]})", flush=True)
    print(f"  新 P1 Router      ：slope ≈ {new_slope:.2f}  (采样 N={[n for n,_ in new_valid]})", flush=True)

    # 关键护栏：新 320/160 增长必须 < 4（证明未静默退回全局 O(N^2)）
    growth = (new_times[320] / new_times[160]) if (new_times.get(160, 0) > 0 and 320 in new_times) else float("nan")
    guard = growth < 4
    print(f"  新 320/160 增长 = {growth:.2f}×  (护栏: < 4 证明未静默退回全局)", flush=True)

    last_old = old_times[max(old_valid)[0]] if old_valid else float("nan")
    print(f"\n结论：旧 ~O(N^{old_slope:.2f}) → 新 ~O(N^{new_slope:.2f})；"
          f"新在 N=320 相对旧 N=80 加速 ≈ {last_old/new_times[320]:.0f}x", flush=True)
    print("护栏(N=320/160增长<4):", "PASS" if guard else "FAIL", flush=True)
    return 0 if guard else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())

