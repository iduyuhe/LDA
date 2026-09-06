"""P1 布线器 smoke（v0.9.52）：正确性 + 性能反向护栏。

覆盖（双层验证，呼应铁律「测生产代码非内嵌副本 / 规模结论必须实测」）：

【A 正确性 —— 与旧 router 逐位一致 + 行为正确】
  ① route_net_p1 == route_net（多场景逐位一致：无障/避障/封死/多障/斜障）
  ② astar_route_p1 == astar_route（路径逐位一致）
  ③ Router.route_all 首 net（无已布路径）：合法最优路由（长度==旧 router /
     无碰撞 / 未假封死）+ 与直接 route_net_p1（相同紧窗口）逐位一致（Router
     是无分歧封装；紧窗口是性能杠杆，路径几何可能因网格原点与旧全 extent 窗口
     略有差异，但等长最优且无碰撞——正确性零回归）
  ④ 无碰撞：障碍场景下 route_net_p1 路径不与障碍相交（或诚实标注 blocked）
  ⑤ 无解诚实退化：封死障碍 → blocked=True（不盲目钻洞）
  ⑥ 拥塞语义：congestion=None 与不传逐位一致；拥塞只影响启发式、不改变可解性
  ⑦ 网-网避让：先布 net1，后续 net2 不得与 net1 路径相交（增量占位生效）

【B 性能反向护栏 —— 证明提速来自索引，且未静默退回全局】
  ⑧ P1(Router) N=40 耗时 < 旧 route_net N=40 × 0.5（P1 完胜基线）
  ⑨ 增长阶护栏：Router N=320 / N=160 耗时增长 < 4（证明非 O(N^2) 静默退回全局）
  ⑩ 反向（索引是提速来源）：共享索引 Router 明显快于「逐网 route_net_p1（无共享索引）」

运行：python run_router_p1_smoke.py
"""
from __future__ import annotations

import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_layout.router import RouteResult, astar_route, route_net
from lda_layout.router_p1 import Router, astar_route_p1, route_net_p1
from lda_layout.spatial_index import ObstacleIndex
from lda_layout.congestion import CongestionMap

_PASS = 0
_FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    mark = "PASS" if cond else "FAIL"
    if cond:
        _PASS += 1
    else:
        _FAIL += 1
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))


def _rr_eq(a: RouteResult, b: RouteResult) -> bool:
    return (a.points_um == b.points_um and a.length_um == b.length_um
            and a.n_bends == b.n_bends and a.blocked == b.blocked
            and a.total_loss_db == b.total_loss_db and a.layer == b.layer
            and a.note == b.note)


def _seg_intersect(p1, p2, p3, p4, eps=1e-6):
    """线段 p1p2 与 p3p4 是否相交（含端点接触）。"""
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    d1 = cross(p3, p4, p1)
    d2 = cross(p3, p4, p2)
    d3 = cross(p1, p2, p3)
    d4 = cross(p1, p2, p4)
    if ((d1 > eps and d2 < -eps) or (d1 < -eps and d2 > eps)) and \
       ((d3 > eps and d4 < -eps) or (d3 < -eps and d4 > eps)):
        return True
    return False


def _path_hits_any(pts, obstacles, wg_half):
    """离散折线是否落入任一障碍（复制 router._path_hits 语义，验证 P1 产物）。"""
    margin = wg_half
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        seg = max(1, int(math.ceil(math.hypot(b[0] - a[0], b[1] - a[1]) / max(wg_half, 0.5))))
        for s in range(seg + 1):
            t = s / seg
            x = a[0] + (b[0] - a[0]) * t
            y = a[1] + (b[1] - a[1]) * t
            for (cx, cy, hw, hh) in obstacles:
                if abs(x - cx) <= hw + margin and abs(y - cy) <= hh + margin:
                    return True
    return False


def _make_local_nets(n, seed=20260906):
    """生成 n 条局部短跳 net（端点间距 ≤ 150µm）+ 静态障碍。"""
    rng = random.Random(seed)
    CHIP, R = 2000.0, 150.0
    static = [(rng.uniform(100, CHIP - 100), rng.uniform(100, CHIP - 100),
               rng.uniform(15, 40), rng.uniform(15, 40)) for _ in range(10)]
    nets = []
    for i in range(n):
        a = (rng.uniform(0, CHIP), rng.uniform(0, CHIP))
        ang = rng.uniform(0, 2 * math.pi)
        rad = rng.uniform(0, R)
        b = (min(CHIP, max(0, a[0] + rad * math.cos(ang))),
             min(CHIP, max(0, a[1] + rad * math.sin(ang))))
        nets.append((f"net_{i}", a, b))
    return static, nets


def main() -> int:
    print("P1 布线器 smoke（正确性 + 性能反向护栏）")

    # ---------------- A. 正确性 ----------------
    print("\n[A] 正确性（与旧 router 逐位一致 + 行为正确）")
    scenarios = [
        ("无障", (0, 0), (100, 50), []),
        ("避障", (0, 0), (100, 50), [(50, 20, 8, 30)]),
        ("封死", (0, 0), (100, 50), [(50, 25, 200, 100)]),
        ("多障", (0, 0), (100, 80), [(50, 50, 10, 10), (50, 100, 10, 10)]),
        ("斜障", (10, 20), (180, 160), [(90, 90, 15, 15), (60, 40, 8, 40)]),
    ]
    for name, s, d, obs in scenarios:
        r_old = route_net("n", s, d, obstacles=obs, method="astar")
        r_new = route_net_p1("n", s, d, obstacles=obs, method="astar")
        check(f"route_net_p1==route_net（{name}）", _rr_eq(r_old, r_new),
              f"len {r_old.length_um:.1f}/{r_new.length_um:.1f}")

    for name, s, d, obs in scenarios:
        p_old = astar_route(s, d, obs, 0.25)
        p_new = astar_route_p1(s, d, obs, 0.25)
        check(f"astar_route_p1==astar_route（{name}）", p_old == p_new)

    # ③ Router 首 net（无已布路径）：合法最优路由 + 无分歧封装
    #   紧窗口是性能杠杆，A* 搜索域=源/目标 bbox ± detour_margin（非旧全 extent
    #   窗口），故与旧 route_net 等长最优但网格原点略异 → 不做字节级逐位比较，
    #   改为校验「合法最优 + 无碰撞 + 未假封死」并对照直接 route_net_p1（相同紧
    #   窗口）确保 Router 不是会引入分歧的封装。
    static, nets = _make_local_nets(5)
    nid, s, d = nets[0]
    x1, y1 = s
    x2, y2 = d
    qm = 200.0
    gw = (min(x1, x2) - qm, max(x1, x2) + qm,
          min(y1, y2) - qm, max(y1, y2) + qm)
    # 直接 route_net_p1（相同紧窗口，独立索引——须在 route_all 之前建，避免
    # 复用被 insert_path 污染的生产索引）
    fresh_idx = ObstacleIndex(static)
    r_p1 = route_net_p1(nid, s, d, obstacles=[], wg_width=0.5, method="astar",
                        grid_dl=1.0, index=fresh_idx,
                        grid_window=gw, query_window=gw)
    router = Router(static, wg_width=0.5)
    res = router.route_all(nets[:1])
    r_old = route_net(nid, s, d, obstacles=static, method="astar")
    only = res[nid]

    # 3a：合法最优（与旧 router 等长 / 无碰撞 / 未假封死）
    valid = (not only.blocked) \
        and (not _path_hits_any(only.points_um, static, 0.25)) \
        and abs(only.length_um - r_old.length_um) < 1e-3
    check("Router 首 net 合法最优（等长/无碰撞/未假封死）", valid,
          f"len {only.length_um:.4f}/{r_old.length_um:.4f} blocked={only.blocked}")

    # 3b：与直接 route_net_p1（相同紧窗口）逐位一致（Router 是无分歧封装）
    check("Router 首 net == route_net_p1（相同紧窗口逐位一致）", _rr_eq(r_p1, only),
          f"len {r_p1.length_um:.4f}/{only.length_um:.4f}")

    # ④ 无碰撞：障碍场景 route_net_p1 路径不与障碍相交（或诚实 blocked）
    obs4 = [(50, 20, 8, 30), (50, 80, 10, 40)]
    r4 = route_net_p1("n", (0, 0), (100, 50), obstacles=obs4, method="astar")
    if r4.blocked:
        check("无碰撞：封死场景诚实 blocked", True, "blocked=True")
    else:
        hit = _path_hits_any(r4.points_um, obs4, 0.25)
        check("无碰撞：route_net_p1 路径不穿障碍", not hit,
              "穿障" if hit else "清洁")

    # ⑤ 无解诚实退化
    obs5 = [(50, 25, 200, 100)]
    r5 = route_net_p1("n", (0, 0), (100, 50), obstacles=obs5, method="astar")
    check("无解诚实退化：blocked=True", r5.blocked and "警告" in r5.note)

    # ⑥ 拥塞语义
    obs6 = [(50, 50, 10, 10), (50, 100, 10, 10)]
    b6 = astar_route_p1((0, 0), (100, 80), obs6, 0.25)
    c6 = astar_route_p1((0, 0), (100, 80), obs6, 0.25, congestion=None)
    check("拥塞=None 与不传逐位一致", b6 == c6)
    cm = CongestionMap(penalty=8.0)
    p_nocg = astar_route_p1((0, 0), (0, 240), obs6, 0.25)
    p_cg = astar_route_p1((0, 0), (0, 240), obs6, 0.25, congestion=cm)
    check("拥塞不改变可解性（有解必有解）", p_nocg is not None and p_cg is not None)

    # ⑦ 网-网避让：先布水平 net1，net2 垂直穿越不得与之相交
    idx = ObstacleIndex([])
    r1 = route_net_p1("net1", (0, 0), (100, 0), obstacles=[], method="astar")
    # 把 net1 路径回填索引，再布垂直 net2
    idx.insert_path(r1.points_um, 0.25)
    r2 = route_net_p1("net2", (50, -50), (50, 50), obstacles=[], method="astar",
                      index=idx,
                      grid_window=(-200, 200, -200, 200),
                      query_window=(-200, 200, -200, 200))
    # 检查 r2 折线是否穿过 net1 线段 [(0,0),(100,0)]
    cross = False
    for i in range(len(r2.points_um) - 1):
        if _seg_intersect(r2.points_um[i], r2.points_um[i + 1],
                          (0.0, 0.0), (100.0, 0.0)):
            cross = True
            break
    check("网-网避让：net2 不穿越 net1 路径", (not cross) or r2.blocked,
          "相交" if cross else "避让成功")

    # ---------------- B. 性能反向护栏 ----------------
    print("\n[B] 性能反向护栏（提速来自索引，且未静默退回全局）")
    N = 40
    static, nets = _make_local_nets(N)
    # 旧 baseline（逐网 route_net，障碍集随已布路径增长 —— 复刻 doc 场景）
    t0 = time.perf_counter()
    placed = list(static)
    for nid, s, d in nets:
        rr = route_net(nid, s, d, obstacles=placed, wg_width=0.5)
        if not rr.blocked:
            xs = [p[0] for p in rr.points_um]; ys = [p[1] for p in rr.points_um]
            placed.append(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2,
                           (max(xs) - min(xs)) / 2 + 0.25, (max(ys) - min(ys)) / 2 + 0.25))
    old_t = time.perf_counter() - t0

    t0 = time.perf_counter()
    Router(static, wg_width=0.5, detour_margin=150.0).route_all(nets)
    new_t = time.perf_counter() - t0
    check(f"⑧ P1(Router) N={N} < 旧×0.5", new_t < old_t * 0.5,
          f"new={new_t:.3f}s old={old_t:.3f}s ({old_t/max(new_t,1e-9):.0f}x)")

    # ⑨ 增长阶护栏：N=160 vs N=320
    _, nets160 = _make_local_nets(160)
    _, nets320 = _make_local_nets(320)
    t0 = time.perf_counter(); Router(static, wg_width=0.5, detour_margin=150.0).route_all(nets160); t160 = time.perf_counter() - t0
    t0 = time.perf_counter(); Router(static, wg_width=0.5, detour_margin=150.0).route_all(nets320); t320 = time.perf_counter() - t0
    growth = t320 / t160 if t160 > 0 else float("inf")
    check(f"⑨ 增长护栏：N=320/N=160={growth:.2f}× < 4（非 O(N^2) 退回全局）", growth < 4,
          f"t160={t160:.3f}s t320={t320:.3f}s")

    # ⑩ 反向：共享索引明显快于「逐网 route_net_p1（无共享索引）」
    t0 = time.perf_counter()
    placed = list(static)
    for nid, s, d in nets:
        route_net_p1(nid, s, d, obstacles=placed, method="astar", wg_width=0.5)
        rr = route_net_p1(nid, s, d, obstacles=placed, method="astar", wg_width=0.5)
        if not rr.blocked:
            xs = [p[0] for p in rr.points_um]; ys = [p[1] for p in rr.points_um]
            placed.append(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2,
                           (max(xs) - min(xs)) / 2 + 0.25, (max(ys) - min(ys)) / 2 + 0.25))
    naive_t = time.perf_counter() - t0
    check(f"⑩ 反向：共享索引 Router < 逐网无索引 {naive_t/max(new_t,1e-9):.0f}×",
          new_t < naive_t * 0.8, f"indexed={new_t:.3f}s naive={naive_t:.3f}s")

    print(f"\nP1 布线 smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
