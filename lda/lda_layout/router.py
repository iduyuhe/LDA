"""LDA L2 · C 级自写最小布线器（routing）。

P1-M2 核心。把「端口 A→端口 B」自动转为波导走线：
  - 曼哈顿路径（L 形 / Z 形绕行），多候选择优；
  - 圆角（圆弧，bend_radius）或直角（sharp，忽略散射损耗）；
  - 避障：路径不与器件包围盒（含波导半宽余量）相交；
  - 损耗计入：直波导 α_cm + 每个弯曲的弯曲损耗 dB
    （弯曲损耗复用 lda_agent.ring_adddrop.bending_loss_db_per_cm，
     与环模型同源；直波导损耗 α_cm 参数化，默认 SOI 220nm 典型 ~2.5 dB/cm）。

主权策略：C 级自写零依赖（标准库 + 复用 bending_loss_db_per_cm）。
不引入 gdsfactory / gdspy / KLayout。
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from lda_agent.ring_adddrop import bending_loss_db_per_cm

# 直波导传播损耗（dB/cm），SOI 220nm 硅波导 C 波段典型量级（文献近似，非标定）
DEFAULT_STRAIGHT_LOSS_DB_CM = 2.5


@dataclass
class RouteResult:
    net_id: str
    points_um: List[Tuple[float, float]]   # 圆角后折线（µm）
    length_um: float                        # 总弧长（直+弯）
    straight_um: float                      # 直段长
    n_bends: int                            # 弯曲（拐角）数
    bend_loss_db: float
    straight_loss_db: float
    total_loss_db: float
    blocked: bool = False                   # 候选均碰撞时直连（诚实标注）
    note: str = ""
    layer: str = "M1"                       # v0.8.25 多层版图：布线所在信号层


def _norm(vx, vy):
    m = math.hypot(vx, vy)
    return (vx / m, vy / m) if m > 1e-12 else (0.0, 0.0)


def _seg_len(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _perp(vx, vy):
    return (-vy, vx)


def _arc_points(a, b, corner, r, n=8):
    """从 a 到 b 的圆角弧（拐角顶点 corner，半径 r）。"""
    d1 = _norm(corner[0] - a[0], corner[1] - a[1])   # a→corner
    d2 = _norm(b[0] - corner[0], b[1] - corner[1])   # corner→b
    n1 = _perp(d1[0], d1[1])
    c = (corner[0] + n1[0] * r, corner[1] + n1[1] * r)
    if abs(math.hypot(c[0] - a[0], c[1] - a[1]) - r) > 1e-6:
        c = (corner[0] - n1[0] * r, corner[1] - n1[1] * r)
    a0 = math.atan2(a[1] - c[1], a[0] - c[0])
    a1 = math.atan2(b[1] - c[1], b[0] - c[0])
    if a1 - a0 > math.pi:
        a1 -= 2 * math.pi
    elif a0 - a1 > math.pi:
        a1 += 2 * math.pi
    pts = []
    for k in range(1, n):
        ang = a0 + (a1 - a0) * k / n
        pts.append((c[0] + r * math.cos(ang), c[1] + r * math.sin(ang)))
    return pts


def _round_corners(pts, r):
    """折线 → 圆角折线（拐角替换为圆弧）。"""
    if len(pts) < 3:
        return [tuple(p) for p in pts]
    out = [list(pts[0])]
    for i in range(1, len(pts) - 1):
        p_prev, p_cur, p_nxt = pts[i - 1], pts[i], pts[i + 1]
        d1 = _seg_len(p_prev, p_cur)
        d2 = _seg_len(p_cur, p_nxt)
        rr = min(r, d1 / 2.0, d2 / 2.0)
        if rr < 1e-6:
            out.append(list(p_cur))
            continue
        a = (p_cur[0] + (p_prev[0] - p_cur[0]) * rr / d1,
             p_cur[1] + (p_prev[1] - p_cur[1]) * rr / d1)
        b = (p_cur[0] + (p_nxt[0] - p_cur[0]) * rr / d2,
             p_cur[1] + (p_nxt[1] - p_cur[1]) * rr / d2)
        out.append(list(a))
        out.extend(_arc_points(a, b, p_cur, rr))
        out.append(list(b))
    out.append(list(pts[-1]))
    return [(round(x, 4), round(y, 4)) for x, y in out]


def _in_rect(x, y, cx, cy, hw, hh, margin):
    return (abs(x - cx) <= hw + margin) and (abs(y - cy) <= hh + margin)


def _path_hits(points, obstacles, wg_half):
    """离散折线，检测是否落入任一障碍矩形（含波导半宽余量）。"""
    if not obstacles:
        return False
    margin = wg_half
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        seg = max(1, int(math.ceil(_seg_len(a, b) / max(wg_half, 0.5))))
        for s in range(seg + 1):
            t = s / seg
            x = a[0] + (b[0] - a[0]) * t
            y = a[1] + (b[1] - a[1]) * t
            for (cx, cy, hw, hh) in obstacles:
                if _in_rect(x, y, cx, cy, hw, hh, margin):
                    return True
    return False


def _path_variants(src, dst):
    """候选曼哈顿路径（L 形 + Z 形绕行）。"""
    x1, y1 = src
    x2, y2 = dst
    variants = [
        [src, (x2, y1), dst],   # L1：先横后纵
        [src, (x1, y2), dst],   # L2：先纵后横
    ]
    if abs(x2 - x1) > 1e-6 and abs(y2 - y1) > 1e-6:
        off = max(abs(x2 - x1), abs(y2 - y1)) * 0.3 + 4.0
        variants.append([src, (x2, y1), (x2, y1 - off), dst])  # 下绕
        variants.append([src, (x2, y1), (x2, y1 + off), dst])  # 上绕
        variants.append([src, (x1 + off, y1), (x2, y1), dst])  # 右延
        variants.append([src, (x1 - off, y1), (x2, y1), dst])  # 左延
    return variants


def _count_bends(points, tol_deg=15.0):
    """统计折点（方向变化 > tol）的数量（对未圆角折线）。"""
    if len(points) < 3:
        return 0
    n = 0
    for i in range(1, len(points) - 1):
        ax = points[i - 1][0] - points[i][0]
        ay = points[i - 1][1] - points[i][1]
        bx = points[i + 1][0] - points[i][0]
        by = points[i + 1][1] - points[i][1]
        la, lb = math.hypot(ax, ay), math.hypot(bx, by)
        if la < 1e-9 or lb < 1e-9:
            continue
        cosang = max(-1.0, min(1.0, (ax * bx + ay * by) / (la * lb)))
        if math.degrees(math.acos(cosang)) > tol_deg:
            n += 1
    return n


def astar_route(src: Tuple[float, float], dst: Tuple[float, float],
               obstacles: Sequence[Tuple[float, float, float, float]],
               wg_half: float, dl: float = 1.0,
               max_span: float = 2000.0,
               congestion=None) -> Optional[List[Tuple[float, float]]]:
    """A* 最短路径（网格离散 + 曼哈顿启发式 + 障碍膨胀）。

    第二梯队-1（版图审计差距 #1/#2 落地）：从贪心「2-6 个 L/Z 形候选首个
    可行即取」升级为全局网格搜索——最短曼哈顿路径（可采纳启发式保证最优）。

    v0.8.42（S2-② 拥塞感知）：congestion 可选 CongestionMap——启发式 h 叠加
    拥塞惩罚（h = 曼哈顿 + penalty × 途经格占用）。语义：
      - congestion=None：与改造前逐位一致（可采纳 h → 严格最短路径）；
      - 传入：引导绕开拥挤走廊（非严格最短，但均衡全局通道利用）。
      拥塞**不阻塞格点、不改变可解性**（有解必有解）；纯启发式影响路径选择。

    参数：
      src/dst    绝对坐标 (x,y) µm
      obstacles  器件包围盒 [(cx,cy,hw,hh)]（中心+半宽半高）
      wg_half    波导半宽 µm（障碍膨胀用）
      dl         网格分辨率 µm（默认 1.0）
      max_span   搜索域上限 µm（防超大规模爆炸）
      congestion 可选 CongestionMap（拥塞感知启发式；None=关闭）
    返回：
      路径折点列表（已压缩共线点，仅保留拐弯）或 None（无解——不再盲目退化）。
    """
    if not obstacles:
        # 无障碍直接 L 形（等价于原贪心最优解）
        x1, y1 = src
        x2, y2 = dst
        return [src, (x2, y1), dst] if abs(x2 - x1) > 1e-9 else [src, dst]

    # —— 网格离散（搜索域 = 源/目标/障碍边界 + margin——非固定大 padding）——
    pad = wg_half + dl * 0.75
    x1, y1 = src
    x2, y2 = dst
    xs = [x1, x2]
    ys = [y1, y2]
    for cx, cy, hw, hh in obstacles:
        xs.extend([cx - hw, cx + hw])
        ys.extend([cy - hh, cy + hh])
    margin = min(max_span, max(20.0, dl * 50.0))
    xmin = min(xs) - margin
    xmax = max(xs) + margin
    ymin = min(ys) - margin
    ymax = max(ys) + margin

    def to_grid(p):
        return (round((p[0] - xmin) / dl), round((p[1] - ymin) / dl))

    def to_xy(g):
        return (xmin + g[0] * dl, ymin + g[1] * dl)

    gs = to_grid(src)
    gd = to_grid(dst)
    span = (round((xmax - xmin) / dl), round((ymax - ymin) / dl))
    if span[0] * span[1] > 4_000_000:   # 网格过大防爆
        return None

    # —— 障碍栅格（膨胀 wg_half + 网格余量，碰撞即禁格）——
    blocked = set()
    n_obs = 0
    for cx, cy, hw, hh in obstacles:
        bx0 = round((cx - hw - pad - xmin) / dl)
        bx1 = round((cx + hw + pad - xmin) / dl)
        by0 = round((cy - hh - pad - ymin) / dl)
        by1 = round((cy + hh + pad - ymin) / dl)
        for gx in range(max(0, bx0), min(span[0], bx1) + 1):
            for gy in range(max(0, by0), min(span[1], by1) + 1):
                if (gx, gy) != gs and (gx, gy) != gd:
                    blocked.add((gx, gy))
        n_obs += 1

    # —— A*（4 邻域，g=步长，h=曼哈顿+可选拥塞惩罚）——
    # v0.8.42：congestion 非空时 h 叠加 penalty × 途经格占用（引导绕行，
    # 不阻塞；h 不再严格可采纳 → 路径可能略长但通道更均衡）
    start = gs
    goal = gd
    if start == goal:
        return [src, dst]
    if goal in blocked:
        return None
    open_h = []
    g_cost = {start: 0.0}
    came: dict = {}
    heapq.heappush(open_h, (0.0, start))
    closed = set()
    while open_h:
        _, cur = heapq.heappop(open_h)
        if cur == goal:
            # 回溯路径
            path = [goal]
            while path[-1] in came:
                path.append(came[path[-1]])
            path.reverse()
            pts = [to_xy(g) for g in path]
            # 压缩共线点（仅保留拐弯）
            comp = [pts[0]]
            for i in range(1, len(pts) - 1):
                a = pts[i - 1]
                b = pts[i]
                c = pts[i + 1]
                if (b[0] - a[0]) * (c[1] - b[1]) != (b[1] - a[1]) * (c[0] - b[0]):
                    comp.append(b)
            comp.append(pts[-1])
            return comp
        if cur in closed:
            continue
        closed.add(cur)
        gx, gy = cur
        for nx, ny in ((gx + 1, gy), (gx - 1, gy), (gx, gy + 1), (gx, gy - 1)):
            nb = (nx, ny)
            if nb in blocked or nb in closed:
                continue
            if not (0 <= nx <= span[0] and 0 <= ny <= span[1]):
                continue
            ng = g_cost[cur] + dl
            if ng < g_cost.get(nb, float("inf")):
                g_cost[nb] = ng
                came[nb] = cur
                h = abs(nx - goal[0]) + abs(ny - goal[1])  # 曼哈顿（可采纳）
                if congestion is not None:
                    # 拥塞惩罚：途经格占用 × penalty（引导绕行；可采纳性
                    # 允许放宽——代价换通道均衡，路径仍保证连通）
                    gx2, gy2 = nx, ny
                    h += congestion.penalty_at(to_xy((gx2, gy2))[0],
                                               to_xy((gx2, gy2))[1])
                heapq.heappush(open_h, (ng + h * dl, nb))
    return None  # 无解（不盲目退化直连——诚实返回）


def route_multi_net(ports: Sequence[Tuple[float, float]],
                   obstacles: Sequence[Tuple[float, float, float, float]] = (),
                   wg_width: float = 0.5, dl: float = 1.0,
                   max_span: float = 2000.0) -> Optional[List[List[Tuple[float, float]]]]:
    """多端网 Steiner 布线（N 端汇聚——第二梯队-2a，审计差距 #4）。

    算法：增量建树——从首端口出发，每步用【多目标 A*】把下一个端口连到
    当前已建树（目标=树上任意点，h=到目标集的最小曼哈顿），累计路径段。
    这是网格 Steiner 树的标准近似（中位数点意义下的最短互连）。

    返回：路径段列表（每段为折点序列，段间共享端点构成树）；任一端无法
    连通返回 None（诚实，不产生断网）。
    """
    if len(ports) < 2:
        return None
    # 无障碍：中位数汇聚点放射连接（曼哈顿 Steiner 近似，确定性）
    if not obstacles:
        xs = [p[0] for p in ports]
        ys = [p[1] for p in ports]
        cx = sorted(xs)[len(xs) // 2]
        cy = sorted(ys)[len(ys) // 2]
        hub = (float(cx), float(cy))
        segs = []
        for p in ports:
            if p == hub:
                continue
            path = [p, (hub[0], p[1]), hub] if abs(hub[0] - p[0]) > 1e-9 else [p, hub]
            segs.append(path)
        return segs

    # 有障碍：多目标 A* 增量建树
    # —— 网格预处理（复用 astar_route 的域与膨胀逻辑）——
    pad = wg_width / 2.0 + dl * 0.75
    allx = [p[0] for p in ports]
    ally = [p[1] for p in ports]
    for cx, cy, hw, hh in obstacles:
        allx.extend([cx - hw, cx + hw])
        ally.extend([cy - hh, cy + hh])
    margin = min(max_span, max(20.0, dl * 50.0))
    xmin, xmax = min(allx) - margin, max(allx) + margin
    ymin, ymax = min(ally) - margin, max(ally) + margin

    def to_grid(p):
        return (round((p[0] - xmin) / dl), round((p[1] - ymin) / dl))

    def to_xy(g):
        return (xmin + g[0] * dl, ymin + g[1] * dl)

    span = (round((xmax - xmin) / dl), round((ymax - ymin) / dl))
    if span[0] * span[1] > 4_000_000:
        return None
    blocked = set()
    for cx, cy, hw, hh in obstacles:
        for gx in range(max(0, round((cx - hw - pad - xmin) / dl)),
                        min(span[0], round((cx + hw + pad - xmin) / dl)) + 1):
            for gy in range(max(0, round((cy - hh - pad - ymin) / dl)),
                            min(span[1], round((cy + hh + pad - ymin) / dl)) + 1):
                blocked.add((gx, gy))
    gports = [to_grid(p) for p in ports]
    for gp in gports:
        blocked.discard(gp)

    def astar_to_set(src_g, goals, blocked_set):
        """多目标 A*：src 到 goal 集任一点的最短网格路径（折点压缩后）。"""
        if src_g in goals:
            return [to_xy(src_g)]
        open_h = []
        g_cost = {src_g: 0.0}
        came: dict = {}
        heapq.heappush(open_h, (0.0, src_g))
        closed = set()
        while open_h:
            _, cur = heapq.heappop(open_h)
            if cur in goals:
                path = [cur]
                while path[-1] in came:
                    path.append(came[path[-1]])
                path.reverse()
                return [to_xy(g) for g in path]
            if cur in closed:
                continue
            closed.add(cur)
            gx, gy = cur
            for nx, ny in ((gx + 1, gy), (gx - 1, gy), (gx, gy + 1), (gx, gy - 1)):
                nb = (nx, ny)
                if nb in blocked_set or nb in closed:
                    continue
                if not (0 <= nx <= span[0] and 0 <= ny <= span[1]):
                    continue
                ng = g_cost[cur] + dl
                if ng < g_cost.get(nb, float("inf")):
                    g_cost[nb] = ng
                    came[nb] = cur
                    h = min(abs(nx - gx2) + abs(ny - gy2) for gx2, gy2 in goals)
                    heapq.heappush(open_h, (ng + h * dl, nb))
        return None

    # —— 增量建树：已连树 = 已接入端口集合；逐端口 A* 连到树 ——
    tree_goals = {gports[0]}
    tree_points = set()
    segs = []
    for i in range(1, len(gports)):
        path_g = astar_to_set(gports[i], tree_goals, blocked)
        if path_g is None:
            return None  # 任一端不可达 → 整体诚实失败
        segs.append(path_g)
        # 把新路径的全部网格点并入树（作为后续端口的目标）
        for pt in path_g:
            g = to_grid(pt)
            tree_goals.add(g)
            tree_points.add(pt)
    return segs


def route_net(net_id, src, dst, obstacles=None, wg_width=0.5,
              bend_radius=5.0, corner="round",
              straight_loss_db_cm=DEFAULT_STRAIGHT_LOSS_DB_CM,
              method: str = "astar", grid_dl: float = 1.0,
              layer: str = "M1", congestion=None) -> RouteResult:
    """端口 A→B 自动布线（曼哈顿 + 圆角/直角 + 避障 + 损耗计入）。

    参数：
      src/dst             ：绝对坐标 (x,y) µm
      obstacles           ：器件包围盒 [(cx,cy,hw,hh)]（中心+半宽半高）
      wg_width            ：波导宽度 µm
      bend_radius         ：圆角半径 µm
      corner              ：'round'（圆弧，计弯曲损耗）| 'sharp'（直角，忽略散射）
      straight_loss_db_cm ：直波导损耗 dB/cm
      layer               ：v0.8.25 多层版图——布线所在信号层（默认 M1，
                            单层行为不变；多层 LVS 按层比对短路）
      congestion          ：v0.8.42 可选 CongestionMap（拥塞感知 A* 启发式；
                            默认 None = 与改造前逐位一致）

    返回 RouteResult（points_um / 长度 / 弯曲数 / 损耗 / layer）。
    """
    obstacles = obstacles or []
    wg_half = wg_width / 2.0
    best, raw, blocked = None, None, False
    if method == "astar":
        # 第二梯队-1：A* 全局最优（网格搜索），无解返回 None 走退化直连
        path = astar_route(src, dst, obstacles, wg_half, dl=grid_dl,
                           congestion=congestion)
        if path is not None:
            pts = _round_corners(path, bend_radius) if corner == "round" else list(path)
            if not _path_hits(pts, obstacles, wg_half):
                best, raw = pts, path
    if best is None and method != "astar":
        for cand in _path_variants(src, dst):
            pts = _round_corners(cand, bend_radius) if corner == "round" else list(cand)
            if not _path_hits(pts, obstacles, wg_half):
                best, raw = pts, cand
                break
    if best is None:  # 退化直连（诚实标注——A* 无解或全部候选碰撞）
        cand = [src, dst]
        best = _round_corners(cand, bend_radius) if corner == "round" else list(cand)
        raw, blocked = cand, True

    n_bends = _count_bends(raw)
    length = sum(_seg_len(best[i], best[i + 1]) for i in range(len(best) - 1))
    arc_len = n_bends * (math.pi / 2.0) * bend_radius if corner == "round" else 0.0
    straight = length - arc_len

    bend_loss = 0.0
    if corner == "round" and n_bends > 0:
        arc_cm = (math.pi / 2.0) * bend_radius / 1e4
        bend_loss = bending_loss_db_per_cm(bend_radius) * arc_cm * n_bends
    straight_loss = straight_loss_db_cm * (straight / 1e4)
    total = bend_loss + straight_loss

    note = "警告：所有候选路径均与障碍碰撞，退化为直连（未避障）" if blocked else ""
    return RouteResult(
        net_id=net_id, points_um=best, length_um=round(length, 4),
        straight_um=round(straight, 4), n_bends=n_bends,
        bend_loss_db=round(bend_loss, 6),
        straight_loss_db=round(straight_loss, 6),
        total_loss_db=round(total, 6), blocked=blocked, note=note,
        layer=layer)
