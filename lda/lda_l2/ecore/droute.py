# -*- coding: utf-8 -*-
"""E35 · **全局布线（global routing）**（`lda/lda_l2/ecore/droute.py` · D-217）。

══════════════════════════════════════════════════════════════
定位：在 `dplac` 的布局上，给**每一根网**算出真实走线长度 —— 这是把
E34「走线电容=0」变成「走线电容=线长×c/µm」的**物理来源**。
══════════════════════════════════════════════════════════════
E34 的 STA 只能说「走线电容诚实取 0」；本模块第一次给出**每根网的线长**，
下一步 `dextract` 把它变成 C_wire，STA 才有资格说「带线载的真实 Fmax」。

══════════════════════════════════════════════════════════════
🔴🔴 绝对金标：2 端网线长 ≥ 两端曼哈顿距离（精确下界）
══════════════════════════════════════════════════════════════
任何合法布线都不可能短于连接其两端点的直线（曼哈顿距离），对 2 端网**取等即直连**。
⚠️ HPWL（半周长线长总和）其实是 RSMT 的**上界**而非下界，多端网 MST 可低于其 HPWL
⇒ 本模块**不**用「总线长 ≥ HPWL」作判据（方向会反）。

══════════════════════════════════════════════════════════════
⚠️ 诚实边界（全部 `claimable=False`）
══════════════════════════════════════════════════════════════
- **最短曼哈顿 MST**，非真正 Steiner 最小树（MST ≥ RSMT，保守）
- **L 形走线**，无绕障 / 无通道拥塞模型 / 无 via 代价
- **无 detail route / 无实际通孔**（via 电阻电容未计 ⇒ 略低估长网延时）
- 网格分辨率仅用于「可复现」，不影响长度（曼哈顿距离与网格无关）
"""
from __future__ import annotations

from dataclasses import dataclass

from .dsynth import Netlist
from . import dplac as PL


@dataclass
class Route:
    length_um: dict            # net -> 线长（µm）
    total_um: float
    hpwl_um: float             # 半周长线长下界
    n_nets: int


def _net_pins(nl: Netlist, p: PL.Placement) -> dict:
    """每个 net 的引脚坐标列表（µm，die 局部）。"""
    pins: dict = {}
    for g in nl.gates:
        cx, cy = 0.0, 0.0
        if g.name in p.cell_xywh:
            x0, y0, w, h = p.cell_xywh[g.name]
            cx, cy = x0 + w / 2.0, y0 + h / 2.0
        pins.setdefault(g.out, []).append((cx, cy))
        for n in g.ins:
            pins.setdefault(n, []).append((cx, cy))
    # 端口引脚落点
    for net, (x, y) in p.port_pins.items():
        pins.setdefault(net, []).append((x, y))
    return pins


def _mst_length(points: list) -> float:
    """曼哈顿度量下的最小生成树总长（Prim，O(n²)）。

    每个 MST 边用 L 形（曼哈顿最短）布 ⇒ 边权 = 两点曼哈顿距离。
    返回总长。单点/空点返回 0。
    """
    n = len(points)
    if n < 2:
        return 0.0
    INF = float("inf")
    dist = [INF] * n
    used = [False] * n
    dist[0] = 0.0
    total = 0.0
    for _ in range(n):
        # 取最近未用点
        u = -1
        best = INF
        for i in range(n):
            if not used[i] and dist[i] < best:
                best = dist[i]
                u = i
        if u < 0:
            break
        used[u] = True
        total += best
        xu, yu = points[u]
        for v in range(n):
            if used[v]:
                continue
            xv, yv = points[v]
            d = abs(xu - xv) + abs(yu - yv)
            if d < dist[v]:
                dist[v] = d
    return total


def route(nl: Netlist, p: PL.Placement) -> Route:
    pins = _net_pins(nl, p)
    length = {}
    total = 0.0
    hpwl = 0.0
    n_nets = 0
    for net, pts in pins.items():
        if len(pts) < 2:
            length[net] = 0.0
            continue
        n_nets += 1
        L = _mst_length(pts)
        length[net] = L
        total += L
        xs = [x for x, _y in pts]
        ys = [y for _x, y in pts]
        hpwl += (max(xs) - min(xs)) + (max(ys) - min(ys))
    return Route(length_um=length, total_um=total, hpwl_um=hpwl, n_nets=n_nets)


def route_self_check(verbose: bool = False) -> dict:
    from . import dctrl as C
    b = C.build()
    nl = b["netlist"]
    p = PL.place(nl)
    r = route(nl, p)
    problems = _validate(nl, p, r)

    # 🔴 对照组：构造一个**物理不可能**的布线——把某根 2 端网线长压到两端距离的一半
    bad = _break_one_two_pin(nl, p, r)
    bad_problems = _validate(nl, p, bad)
    if not bad_problems:
        problems.append(("control_two_pin_too_short_not_red",))

    if verbose:
        print("  route: nets=%d  total=%.1f um  hpwl=%.1f um  ratio=%.3f"
              % (r.n_nets, r.total_um, r.hpwl_um,
                 (r.total_um / r.hpwl_um) if r.hpwl_um > 0 else 0.0))
    return {
        "ok": not problems, "problems": problems,
        "n_nets": r.n_nets, "total_um": r.total_um, "hpwl_um": r.hpwl_um,
        "ratio": (r.total_um / r.hpwl_um) if r.hpwl_um > 0 else 0.0,
    }


def _validate(nl: Netlist, p: PL.Placement, r: Route) -> list:
    """布线合法性的机核判据（真实路由 + 对照组共用）。"""
    problems = []
    pins = _net_pins(nl, p)
    EPS = 1e-6
    for net, pts in pins.items():
        L = r.length_um.get(net, 0.0)
        if len(pts) <= 1:
            if L > EPS:
                problems.append(("single_pin_net_nonzero", net, L))
            continue
        # 多端网必须被布线
        if L <= 1e-12:
            problems.append(("unrouted_multinet", net))
        # 🔴 2 端网：线长 ≥ 两端曼哈顿距离（精确下界，取等即直连）
        if len(pts) == 2:
            d = abs(pts[0][0] - pts[1][0]) + abs(pts[0][1] - pts[1][1])
            if L < d - EPS:
                problems.append(("two_pin_shorter_than_L1", net, L, d))
    # 总线长 > 0
    if r.total_um <= 0.0:
        problems.append(("zero_total_wire", r.total_um))
    # 上界 sanity：MST 不应远超 HPWL 总和（抓「翻倍编数」类错误）
    if r.hpwl_um > 0 and r.total_um > 1.5 * r.hpwl_um:
        problems.append(("total_over_hpwl_1p5", r.total_um, r.hpwl_um))
    return problems


def _break_one_two_pin(nl: Netlist, p: PL.Placement, r: Route) -> Route:
    """对照组：把一根 2 端网线长压到其两端距离的 0.4×（物理不可能）。"""
    pins = _net_pins(nl, p)
    target = None
    for net, pts in pins.items():
        if len(pts) == 2:
            target = net
            break
    bad_len = dict(r.length_um)
    if target is not None:
        d = abs(pts[0][0] - pts[1][0]) + abs(pts[0][1] - pts[1][1])
        bad_len[target] = d * 0.4
    return Route(length_um=bad_len, total_um=sum(bad_len.values()),
                 hpwl_um=r.hpwl_um, n_nets=r.n_nets)


def _is_single(nl: Netlist, p: PL.Placement, net: str) -> bool:
    cnt = 0
    for g in nl.gates:
        if g.out == net:
            cnt += 1
        cnt += sum(1 for n in g.ins if n == net)
    if net in p.port_pins:
        cnt += 1
    return cnt <= 1


DROUTE_DISCLOSURE = {
    "route": "E35 · CIM 加速器 IP 的 P&R · 第 1 层（全局布线）",
    "analysis": "曼哈顿度量 MST（Prim）把多端网拆成 2 端 L 形布线 · 累加每网线长",
    "golden": "2 端网线长 ≥ 两端曼哈顿距离（精确下界，取等=直连）；多端网必布；"
              "总线长 ≤ 1.5×HPWL（抓翻倍编数）",
    "not_included": "MST ≥ RSMT（略高估）· 无绕障/拥塞/via 代价 · 无 detail route · "
                    "网格仅用于可复现、不影响长度",
    "claimable": False,
    "claimable_reason": "线长是拓扑量（布局决定），但**布局本身是模型假设** ⇒ "
                       "线长随之是 MODEL_ESTIMATE；可 signoff 的只有结构性事实（总≥HPWL）",
}
