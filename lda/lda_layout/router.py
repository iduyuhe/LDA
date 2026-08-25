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


def route_net(net_id, src, dst, obstacles=None, wg_width=0.5,
              bend_radius=5.0, corner="round",
              straight_loss_db_cm=DEFAULT_STRAIGHT_LOSS_DB_CM) -> RouteResult:
    """端口 A→B 自动布线（曼哈顿 + 圆角/直角 + 避障 + 损耗计入）。

    参数：
      src/dst             ：绝对坐标 (x,y) µm
      obstacles           ：器件包围盒 [(cx,cy,hw,hh)]（中心+半宽半高）
      wg_width            ：波导宽度 µm
      bend_radius         ：圆角半径 µm
      corner              ：'round'（圆弧，计弯曲损耗）| 'sharp'（直角，忽略散射）
      straight_loss_db_cm ：直波导损耗 dB/cm

    返回 RouteResult（points_um / 长度 / 弯曲数 / 损耗）。
    """
    obstacles = obstacles or []
    wg_half = wg_width / 2.0
    best, raw, blocked = None, None, False
    for cand in _path_variants(src, dst):
        pts = _round_corners(cand, bend_radius) if corner == "round" else list(cand)
        if not _path_hits(pts, obstacles, wg_half):
            best, raw = pts, cand
            break
    if best is None:  # 退化直连（诚实标注）
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
        total_loss_db=round(total, 6), blocked=blocked, note=note)
