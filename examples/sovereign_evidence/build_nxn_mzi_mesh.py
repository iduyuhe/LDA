"""走法一（主权全链路）· 通用 N×N MZI 网格 P&R 可行性生成器（4×4→8×8 可扩展）。

这是「4×4 光子计算核 P&R」的泛化：把手工写死的 4×4 抽成对任意 N 可复用的
主权版图 P&R 生成器，证明 mesh 的『物理 P&R + 交叉化解（M1/M2 跨层桥）』机制
对 N×N 规模通用、可扩展，而非调参调出来的特例。

拓扑：Clements（2016）矩形折叠网格——N-1 个 stage，每 stage N/2 个 MZI（N 偶），
相邻 stage 间 rail 顺序反转（folded），保证矩形版图 + 连通 + 必然产生 waveguide
crossing。crossing 用主权链 can_cross(M1,M2)=False 的异层桥接化解（每交点恰一
根网跳 M2，另一根留 M1）。

诚实边界（与 4×4 一致，更明确）：
- 本脚本验证『N×N MZI 网格主权 P&R 可行性 + 交叉化解机制』对任意 N 通用；
  通用网格用统一 50/50 定向耦合器（Lc 由 CMT 锚定 θ=π/2 → 7.75µm），不绑定
  特定酉矩阵的 mode 装配映射（那是完整 MZI 网格编译器的工作，超出 P&R 可行性范围）。
- 计算核数学层用 reck_decompose(dft_matrix(N)) 独立验证『N×N 酉可由 MZI 网格
  以机器精度实现』（保真度≈1.0），这是可行性（可实现性）的定理级证据。
- 仍为结构代理版图：无相移器几何段 / foundry deck / 逐器件光学表征，未锚定 GP-*。
"""
from __future__ import annotations


import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))   # D:/agent_LDA
sys.path.insert(0, os.path.join(ROOT, "lda"))

from lda_chain.link_model import LinkModel
from lda_layout.placement import port_abs, device_bbox
from lda_layout.router import route_net, RouteResult
from lda_l2.chip_layout_export import (
    export_chip_gds, device_geoms, io_grating_geoms, 
)
from lda_l2.mzi_mesh_matmul import (
    reck_decompose, dft_matrix, assemble_mesh, unitary_fidelity, mesh_cascade_loss_db,
    coupler_length_from_theta,  
)

WG = 0.5
RULES = {
    "min_width_um": 0.30,
    "min_space_um": 0.20,
    "min_bend_R_um": 5.0,
    "max_split_angle_deg": 30.0,
}


# ── 几何工具（与 4×4 同源）───────────────────────────────────────────────────────
def _d(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _seg_intersect_point(p1, p2, p3, p4):
    x1, y1, x2, y2 = p1[0], p1[1], p2[0], p2[1]
    x3, y3, x4, y4 = p3[0], p3[1], p4[0], p4[1]
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-12:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    u = ((x1 - x3) * (y1 - y2) - (y1 - y3) * (x1 - x2)) / den
    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    return None


def _path_intersections(a, b):
    out = []
    for i in range(len(a) - 1):
        for j in range(len(b) - 1):
            p = _seg_intersect_point(a[i], a[i + 1], b[j], b[j + 1])
            if p is not None:
                out.append(p)
    return out


def _cum_arclen(pts):
    cum = [0.0]
    for i in range(len(pts) - 1):
        cum.append(cum[-1] + _d(pts[i], pts[i + 1]))
    return cum


def _point_at_arclen(pts, cum, s):
    s = max(0.0, min(cum[-1], s))
    for i in range(len(pts) - 1):
        if cum[i] <= s <= cum[i + 1]:
            seg = cum[i + 1] - cum[i]
            t = 0.0 if seg < 1e-12 else (s - cum[i]) / seg
            return (pts[i][0] + t * (pts[i + 1][0] - pts[i][0]),
                    pts[i][1] + t * (pts[i + 1][1] - pts[i][1]))
    return pts[-1]


def _arclen_of_point(pts, cum, q):
    best, best_s = None, 0.0
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        seg = _d(a, b)
        if seg < 1e-12:
            s = cum[i]
        else:
            t = ((q[0] - a[0]) * (b[0] - a[0]) + (q[1] - a[1]) * (b[1] - a[1])) / (seg * seg)
            t = max(0.0, min(1.0, t))
            s = cum[i] + t * seg
        d = _d((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])), q)
        if best is None or d < best:
            best, best_s = d, s
    return best_s


def _subpoly(pts, cum, s0, s1):
    s0, s1 = max(0.0, s0), min(cum[-1], s1)
    if s1 - s0 < 1e-9:
        return [pts[0]]
    out = [_point_at_arclen(pts, cum, s0)]
    for i in range(len(pts) - 1):
        if cum[i] > s0 + 1e-9 and cum[i] < s1 - 1e-9:
            out.append(pts[i])
    out.append(_point_at_arclen(pts, cum, s1))
    dedup = [out[0]]
    for p in out[1:]:
        if _d(dedup[-1], p) > 1e-9:
            dedup.append(p)
    return dedup


_LOSS_PER_UM = 0.0002   # 几何代理：~0.2 dB/cm（Si 波导量级），仅结构性标注


def _seg(net_id, pts, layer):
    length = round(sum(_d(pts[i], pts[i + 1]) for i in range(len(pts) - 1)), 4)
    loss = round(length * _LOSS_PER_UM, 6)
    return RouteResult(
        net_id=net_id,
        points_um=[tuple(p) for p in pts],
        length_um=length,
        straight_um=length,
        n_bends=0,
        bend_loss_db=0.0,
        straight_loss_db=loss,
        total_loss_db=loss,
        layer=layer,
    )


def _seg_collinear_overlap(p1, p2, q1, q2, tol=0.12):
    """若线段 p1p2 与 q1q2 共线（平行、同轴线、垂直间距 < tol）且沿轴投影重叠，
    返回 (lo, hi, axis) 描述在 p1p2 上的重叠坐标区间；否则 None。
    与『段中点距』法不同：本函数对『一长段 vs 短段同轨』也能正确判定重叠。"""
    # 水平段（y 恒定）
    if abs(p1[1] - p2[1]) < 1e-9 and abs(q1[1] - q2[1]) < 1e-9:
        if abs(p1[1] - q1[1]) >= tol:
            return None
        lo = max(min(p1[0], p2[0]), min(q1[0], q2[0]))
        hi = min(max(p1[0], p2[0]), max(q1[0], q2[0]))
        if hi - lo <= 1e-9:
            return None
        return (lo, hi, "x")
    # 垂直段（x 恒定）
    if abs(p1[0] - p2[0]) < 1e-9 and abs(q1[0] - q2[0]) < 1e-9:
        if abs(p1[0] - q1[0]) >= tol:
            return None
        lo = max(min(p1[1], p2[1]), min(q1[1], q2[1]))
        hi = min(max(p1[1], p2[1]), max(q1[1], q2[1]))
        if hi - lo <= 1e-9:
            return None
        return (lo, hi, "y")
    return None


def _overlap_spans(a, b, tol=0.12):
    """返回折线 a 上需跳 M2 的弧长区间列表：a 与 b 真正共线重叠的段（间距 < tol）。
    用于化解『两网在 M1 层投影重叠』（不仅是交叉点），这是 N×N 规模化后 A* 把
    相邻 rail 的 net 路由到同一走廊时必然出现的冲突。"""
    ca = _cum_arclen(a)
    out = []
    for i in range(len(a) - 1):
        p1, p2 = a[i], a[i + 1]
        L = ca[i + 1] - ca[i]
        if L < 1e-12:
            continue
        run_lo = min(p1[0], p2[0]) if abs(p1[1] - p2[1]) < 1e-9 else min(p1[1], p2[1])
        span = abs(p2[0] - p1[0]) if abs(p1[1] - p2[1]) < 1e-9 else abs(p2[1] - p1[1])
        for j in range(len(b) - 1):
            r = _seg_collinear_overlap(p1, p2, b[j], b[j + 1], tol)
            if r is None:
                continue
            lo, hi, axis = r
            if axis == "x":
                t0 = (lo - run_lo) / (span + 1e-12)
                t1 = (hi - run_lo) / (span + 1e-12)
            else:
                t0 = (lo - run_lo) / (span + 1e-12)
                t1 = (hi - run_lo) / (span + 1e-12)
            out.append((ca[i] + t0 * L, ca[i] + t1 * L))
    return out


def _conflict_pairs_grid(route_paths, net_ids, cell=2.0):
    """空间网格宽相位：返回真正可能冲突（bbox 重叠）的网对集合。

    原冲突消解对每对网都跑 `_path_intersections`(≈O(段²))，整体 O(nets²)→O(N⁴)，
    在 N≥64 不可行。这里用网格只筛出 bbox 重叠的候选对（宽相位），精确消解仍由调用方
    对候选对跑原逻辑——结果与原逻辑逐对一致，复杂度降到 O(段数·邻接度)。
    """
    segs = []
    for nid in net_ids:
        pts = route_paths[nid]
        for k in range(len(pts) - 1):
            a, b = pts[k], pts[k + 1]
            segs.append((nid, min(a[0], b[0]), min(a[1], b[1]),
                         max(a[0], b[0]), max(a[1], b[1])))
    grid = {}
    for idx, (nid, ax0, ay0, ax1, ay1) in enumerate(segs):
        gx0, gx1 = int(ax0 // cell), int(ax1 // cell)
        gy0, gy1 = int(ay0 // cell), int(ay1 // cell)
        for gx in range(gx0, gx1 + 1):
            for gy in range(gy0, gy1 + 1):
                grid.setdefault((gx, gy), []).append(idx)
    pairs = set()
    for occ in grid.values():
        L = len(occ)
        for ii in range(L):
            ia = occ[ii]
            na = segs[ia][0]
            ax0, ay0, ax1, ay1 = segs[ia][1], segs[ia][2], segs[ia][3], segs[ia][4]
            for jj in range(ii + 1, L):
                ib = occ[jj]
                nb = segs[ib][0]
                if na == nb:
                    continue
                bax0, bay0, bax1, bay1 = segs[ib][1], segs[ib][2], segs[ib][3], segs[ib][4]
                if (max(ax0, bax0) <= min(ax1, bax1)
                        and max(ay0, bay0) <= min(ay1, bay1)):
                    pairs.add((na, nb) if na < nb else (nb, na))
    return pairs


def _m2_len(spans):
    return sum(max(0.0, b - a) for (a, b) in spans)


def _assign_layers_consistent(route_paths, net_ids, cum_len, tot_len,
                              can_host, stub_min, hop, overlap_tol, max_iter=96):
    """逐网对一致 M2 跳层分配（根治 HOP 窗口溢出 + 规模债振荡）。

    阶段1：对每个冲突网对 (ni,nj) 一次性选定『跳网 winner』并全程一致——给 winner 在该
    对所有交叉点/重叠段打紧 M2 气泡，loser 全程留 M1。这避免逐点翻转导致的振荡，且 winner
    在多点交叉时保持一致（如 n66 在 (n66,n67) 全交叉点恒 M2 / 恒 M1），不引入 M2∩M2。
    阶段2：有界调和——对残留同层交叉（仅 3 网共点等 2 层物理不可解情形）再迭代修；未收敛
    即真实 2 层布线天花板，如实上报 LVS REJECT，绝不隐瞒。
    """
    m2_spans = {nid: [] for nid in net_ids}
    crossing_pairs = []
    unresolved = []
    for (ni, nj) in sorted(_conflict_pairs_grid(route_paths, net_ids)):
        xps = _path_intersections(route_paths[ni], route_paths[nj])
        ov_i = _overlap_spans(route_paths[ni], route_paths[nj], tol=overlap_tol)
        ov_j = _overlap_spans(route_paths[nj], route_paths[ni], tol=overlap_tol)
        if not xps and not ov_i and not ov_j:
            continue
        crossing_pairs.append((ni, nj))
        # 选跳网 winner（一次定，全程一致）
        winner = None
        if xps:
            sB = _arclen_of_point(route_paths[nj], cum_len[nj], xps[0])
            sA = _arclen_of_point(route_paths[ni], cum_len[ni], xps[0])
            if can_host(nj, sB):
                winner = nj
            elif can_host(ni, sA):
                winner = ni
        if winner is None and ov_j and all(stub_min <= a2 and b2 <= tot_len[nj] - stub_min
                                           for (a2, b2) in ov_j):
            winner = nj
        if winner is None and ov_i and all(stub_min <= a2 and b2 <= tot_len[ni] - stub_min
                                           for (a2, b2) in ov_i):
            winner = ni
        if winner is None:
            for P in xps:
                unresolved.append((ni, nj, (round(P[0], 3), round(P[1], 3))))
            continue
        # 给 winner 在所有交叉点 + 重叠段打紧气泡
        for P in xps:
            s = _arclen_of_point(route_paths[winner], cum_len[winner], P)
            m2_spans[winner].append((s - hop / 2.0, s + hop / 2.0))
        if winner == nj and ov_j:
            for (a2, b2) in ov_j:
                if stub_min <= a2 and b2 <= tot_len[nj] - stub_min:
                    m2_spans[nj].append((float(a2), float(b2)))
        elif winner == ni and ov_i:
            for (a2, b2) in ov_i:
                if stub_min <= a2 and b2 <= tot_len[ni] - stub_min:
                    m2_spans[ni].append((float(a2), float(b2)))
    # 阶段2：有界调和（仅 3 网共点等真实不可解情形会残留）
    it = 0
    for it in range(1, max_iter + 1):
        m1, m2 = _subpaths_by_layer(route_paths, m2_spans)
        bad = False
        for (n1, n2, P) in _same_layer_crossings(m2):
            if _m2_len(m2_spans.get(n1, [])) >= _m2_len(m2_spans.get(n2, [])):
                _demote_at(m2_spans, n1, route_paths, P, 0.6)
            else:
                _demote_at(m2_spans, n2, route_paths, P, 0.6)
            bad = True
        for (n1, n2, P) in _same_layer_crossings(m1):
            if _m2_len(m2_spans.get(n1, [])) <= _m2_len(m2_spans.get(n2, [])):
                _promote_at(m2_spans, n1, route_paths, P, 0.6, stub_min)
            else:
                _promote_at(m2_spans, n2, route_paths, P, 0.6, stub_min)
            bad = True
        if not bad:
            break
    return m2_spans, it, crossing_pairs, unresolved


def make_jumps(rr, layer_spans, stub_min=1.0):
    """对一条网做跨层跳：在 layer_spans（{层: 弧长区间列表}）内设对应层，其余 M1。

    layer_spans 支持两种形态：
      - dict {layer: [(a,b)...]}（S4 多色着色产出，含 M1/M2/M3）：按层优先级
        M3>M2>M1 选层，同址重叠时高层覆盖低层；
      - list [(a,b)...]（旧 M2 单层兼容）：等同 {"M2": layer_spans}。

    区间两端强制留 ≥stub_min 的 M1 残段接器件端口（LVS 端口按层匹配），
    中间跨层段坐标重合 → 多层 LVS via 桥接合法（can_cross(异层)=False 不判短）。
    """
    pts = [tuple(p) for p in rr.points_um]
    # 旧 list 形态兼容
    if isinstance(layer_spans, (list, tuple)):
        layer_spans = {"M2": list(layer_spans)}
    active = {L: [s for s in sp if s[1] - s[0] >= 1e-9]
              for L, sp in layer_spans.items() if sp}
    if not active:
        return [rr]
    cum = _cum_arclen(pts)
    total = cum[-1]
    lo_lim, hi_lim = stub_min, total - stub_min
    if lo_lim >= hi_lim:
        return [rr]
    priority = {"M3": 2, "M2": 1, "M1": 0}
    merged = {}
    for L, sp in active.items():
        merged[L] = _merge_spans([(max(lo_lim, min(hi_lim, a)),
                                   max(lo_lim, min(hi_lim, b))) for (a, b) in sp])
    bounds = set([0.0, total])
    for L, sp in merged.items():
        for (a, b) in sp:
            bounds.add(a); bounds.add(b)
    bounds = sorted(bounds)
    segs = []
    for i in range(len(bounds) - 1):
        lo, hi = bounds[i], bounds[i + 1]
        if hi - lo < 1e-9:
            continue
        mid = (lo + hi) / 2.0
        chosen = "M1"
        for L in sorted(merged, key=lambda x: priority.get(x, 0), reverse=True):
            if any(a_ <= mid <= b_ for (a_, b_) in merged[L]):
                chosen = L
                break
        seg_pts = _subpoly(pts, cum, lo, hi)
        if len(seg_pts) >= 2:
            segs.append(_seg(rr.net_id, seg_pts, chosen))
    return segs if segs else [rr]


# ── 多层 LVS 反馈修复（照妖镜防规模债）────────────────────────────────────────────
# 根因：HOP=3.0 的 M2 跳层窗口在稠密网格下会「溢出」盖住相邻交叉点，导致两条不同网
# 在某一交叉点同时处于 M2（M2∩M2 短接），违反「每交叉恰一网上 M2」铁律。小规模交叉
# 稀疏不触发，N≥32 触发。修复：以 LVS 为 oracle，迭代检测同层交叉点并把其中一条网
# 在该点退为 M1（M2∩M2）或抬为 M2（M1∩M1），局部开窗、重复至零违例。
def _merge_spans(spans):
    out = []
    for (a, b) in sorted(spans):
        if b - a < 1e-9:
            continue
        if out and a <= out[-1][1] + 1e-9:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append([a, b])
    return [(float(a), float(b)) for (a, b) in out]


def _subpaths_by_layer(route_paths, m2_spans):
    """把每条网拆成 M1 / M2 子折线段（供同层交叉检测）。"""
    m1, m2 = {}, {}
    for n, full in route_paths.items():
        cum = _cum_arclen(full)
        total = cum[-1]
        spans = _merge_spans(m2_spans.get(n, []))
        m2subs = []
        for (a, b) in spans:
            if b - a < 1e-9:
                continue
            m2subs.append(_subpoly(full, cum, a, b))
        if m2subs:
            m2[n] = m2subs
        m1subs, cur = [], 0.0
        for (a, b) in spans:
            if a - cur > 1e-9:
                m1subs.append(_subpoly(full, cum, cur, a))
            cur = max(cur, b)
        if total - cur > 1e-9:
            m1subs.append(_subpoly(full, cum, cur, total))
        if m1subs:
            m1[n] = m1subs
    return m1, m2


def _first_cross_point(subs_a, subs_b):
    for sa in subs_a:
        for sb in subs_b:
            pts = _path_intersections(sa, sb)
            if pts:
                return pts[0]
    return None


def _same_layer_crossings(grp, cell=2.0):
    """grp: {net: [subpoly, ...]}；返回 [(n1, n2, P), ...] 同层（同集合内）交叉点。

    网格宽相位：仅对 bbox 重叠的候选段对做精确 `_path_intersections`，避免 O(nets²)
    逐对检测（N≥64 不可行）。返回交点供修复环定位弧长。
    """
    segs = []
    for nid, subs in grp.items():
        for sub in subs:
            for k in range(len(sub) - 1):
                a, b = sub[k], sub[k + 1]
                segs.append((nid, min(a[0], b[0]), min(a[1], b[1]),
                             max(a[0], b[0]), max(a[1], b[1])))
    grid = {}
    for idx, (nid, ax0, ay0, ax1, ay1) in enumerate(segs):
        gx0, gx1 = int(ax0 // cell), int(ax1 // cell)
        gy0, gy1 = int(ay0 // cell), int(ay1 // cell)
        for gx in range(gx0, gx1 + 1):
            for gy in range(gy0, gy1 + 1):
                grid.setdefault((gx, gy), []).append(idx)
    res = []
    seen = set()
    for occ in grid.values():
        L = len(occ)
        for ii in range(L):
            ia = occ[ii]
            na = segs[ia][0]
            ax0, ay0, ax1, ay1 = segs[ia][1], segs[ia][2], segs[ia][3], segs[ia][4]
            for jj in range(ii + 1, L):
                ib = occ[jj]
                nb = segs[ib][0]
                if na == nb:
                    continue
                bax0, bay0, bax1, bay1 = segs[ib][1], segs[ib][2], segs[ib][3], segs[ib][4]
                if (max(ax0, bax0) <= min(ax1, bax1)
                        and max(ay0, bay0) <= min(ay1, bay1)):
                    key = (na, nb) if na < nb else (nb, na)
                    if key in seen:
                        continue
                    seen.add(key)
                    for sa in grp[na]:
                        for sb in grp[nb]:
                            for P in _path_intersections(sa, sb):
                                res.append((na, nb, P))
    return res


def _demote_at(m2_spans, n, route_paths, P, delta):
    """把网 n 在交叉点 P 处退为 M1（挖掉其 M2 窗口里覆盖 P 的小段）。"""
    full = route_paths[n]
    cum = _cum_arclen(full)
    s = _arclen_of_point(full, cum, (P[0], P[1]))
    new_spans, changed = [], 0
    for (a, b) in m2_spans.get(n, []):
        if b < s - delta or a > s + delta:
            new_spans.append((a, b))
        else:
            changed += 1
            if a < s - delta:
                new_spans.append((a, s - delta))
            if b > s + delta:
                new_spans.append((s + delta, b))
    m2_spans[n] = _merge_spans(new_spans)
    return changed


def _promote_at(m2_spans, n, route_paths, P, delta, stub_min):
    """把网 n 在交叉点 P 处抬为 M2（补一个覆盖 P 的小窗）。"""
    full = route_paths[n]
    cum = _cum_arclen(full)
    total = cum[-1]
    s = _arclen_of_point(full, cum, (P[0], P[1]))
    lo, hi = stub_min, total - stub_min
    a2 = max(lo, s - delta)
    b2 = min(hi, s + delta)
    if b2 - a2 < 1e-9:
        return 0
    m2_spans[n] = _merge_spans(list(m2_spans.get(n, [])) + [(a2, b2)])
    return 1


def repair_layer_assignment(route_paths, m2_spans, max_iter=64, delta=0.6,
                          stub_min=0.3):
    """迭代消除同层交叉（M2∩M2 / M1∩M1），保证每交叉恰一网上 M2。

    返回实际迭代次数；m2_spans 原地修复。收敛即停。delta 取小窗以最小化窗口溢出。
    """
    it = 0
    for it in range(1, max_iter + 1):
        m1, m2 = _subpaths_by_layer(route_paths, m2_spans)
        bad = False
        for (n1, n2, P) in _same_layer_crossings(m2):
            _demote_at(m2_spans, n1, route_paths, P, delta)
            bad = True
        for (n1, n2, P) in _same_layer_crossings(m1):
            _promote_at(m2_spans, n1, route_paths, P, delta, stub_min)
            bad = True
        if not bad:
            break
    return it


def _assign_layers_multicolor(route_paths, net_ids, cum_len, hop, stub_min,
                              overlap_tol=0.12, allow_m3=True):
    """交叉图多色层分配（S4 规模债根治：N≥64 奇圈 2 层不可解 → 第 3 层 M3）。

    机制：把每条网的交叉事件（点交叉 + 共线重叠段）按 HOP 聚类为节点；同网相邻
    交叉合并为同一节点（该网在此节点同色）。建冲突图（每条交叉 = 一条边，连接两
    网节点）；先 2-着色——若含奇圈（2 层物理不可解，如 3 网同址互交）则升级 3-着色，
    把奇圈组件内若干网抬到 M3（异层恒隔离，can_cross(M3,M1/M2)=False，物理正确）。
    返回 (layer_spans, n_m3_nets, color_fail, crossing_pairs, unresolved)：
      layer_spans: {net: {"M1":[], "M2":[], "M3":[]}}，span 已 clamp 到
                   [stub_min, total-stub_min]；点交叉 ±hop/2，重叠段用真实区间。
      color_fail:  3-着色仍失败（极罕见，如实上报，不隐瞒）。
    """
    # 1) 交叉事件（点交叉 + 共线重叠段）
    from collections import defaultdict
    events = defaultdict(list)
    crossing_pairs = []
    pairs = _conflict_pairs_grid(route_paths, net_ids)
    for (ni, nj) in pairs:
        xps = _path_intersections(route_paths[ni], route_paths[nj])
        ov_i = _overlap_spans(route_paths[ni], route_paths[nj], tol=overlap_tol)
        ov_j = _overlap_spans(route_paths[nj], route_paths[ni], tol=overlap_tol)
        if xps or ov_i or ov_j:
            crossing_pairs.append((ni, nj))
        for P in xps:
            si = _arclen_of_point(route_paths[ni], cum_len[ni], P)
            sj = _arclen_of_point(route_paths[nj], cum_len[nj], P)
            events[ni].append((nj, P, si, "point", None))
            events[nj].append((ni, P, sj, "point", None))
        for (a, b) in ov_i:
            mid = (a + b) / 2.0
            events[ni].append((nj, None, mid, "overlap", (a, b)))
        for (a, b) in ov_j:
            mid = (a + b) / 2.0
            events[nj].append((ni, None, mid, "overlap", (a, b)))
    for n in events:
        events[n].sort(key=lambda t: t[2])

    # 2) 按 HOP 聚类（同网相邻交叉/重叠合并为节点）
    cluster_of_event = {}
    clusters = {}
    ci_counter = defaultdict(int)
    for n in net_ids:
        evs = events.get(n, [])
        if not evs:
            continue
        ci = 0
        start = 0
        for k in range(1, len(evs) + 1):
            if k == len(evs) or evs[k][2] - evs[k - 1][2] >= hop:
                key = (n, ci)
                clusters[key] = {
                    "net": n,
                    "events": [(evs[j][1], evs[j][0], evs[j][2], evs[j][3], evs[j][4])
                              for j in range(start, k)],
                }
                for j in range(start, k):
                    cluster_of_event[(n, j)] = key
                ci += 1
                start = k

    # 3) 冲突边（每条交叉 = 连接两网节点的一跳）
    edges = []
    for n in net_ids:
        evs = events.get(n, [])
        for k, (_partner, P, s, _kind, _iv) in enumerate(evs):
            own = cluster_of_event[(n, k)]
            pevs = events.get(_partner, [])
            kp = None
            for kk in range(len(pevs)):
                if pevs[kk][0] == n and (
                        (P is None and pevs[kk][1] is None)
                        or (P is not None and pevs[kk][1] is not None
                            and abs(pevs[kk][1][0] - P[0]) < 1e-6
                            and abs(pevs[kk][1][1] - P[1]) < 1e-6)):
                    kp = kk
                    break
            if kp is None:
                continue
            other = cluster_of_event[(_partner, kp)]
            if own != other:
                a, b = own, other
                if a > b:
                    a, b = b, a
                edges.append((a, b))
    seen = set()
    E = []
    for e in edges:
        if e in seen:
            continue
        seen.add(e)
        E.append(e)

    # 4) 着色：先 2-着色，含奇圈则 3-着色（M3 破奇圈）
    adj = defaultdict(set)
    for (a, b) in E:
        adj[a].add(b)
        adj[b].add(a)

    def _try_color(K):
        col = {}
        for v in adj:
            used = set(col.get(w) for w in adj[v] if w in col)
            c = 0
            while c in used and c < K:
                c += 1
            if c >= K:
                return None
            col[v] = c
        for key in clusters:
            col.setdefault(key, 0)
        return col

    color = _try_color(2)
    color_fail = False
    if color is None:
        if allow_m3:
            color = _try_color(3)
            if color is None:
                color_fail = True
                color = {}
        else:
            color_fail = True
            color = {}

    LAYERS = {0: "M1", 1: "M2", 2: "M3"}

    # 5) 生成 per-net per-layer spans（clamp 到 stub_min 内）
    layer_spans = {n: {"M1": [], "M2": [], "M3": []} for n in net_ids}
    for key, cl in clusters.items():
        c = color.get(key, 0)
        lay = LAYERS.get(c, "M1")
        tot = cum_len[cl["net"]][-1]
        for (_P, partner, s, kind, iv) in cl["events"]:
            if kind == "overlap" and iv is not None:
                a, b = iv
            else:
                a, b = s - hop / 2.0, s + hop / 2.0
            a = max(stub_min, min(tot - stub_min, a))
            b = max(stub_min, min(tot - stub_min, b))
            if b - a >= 1e-9:
                layer_spans[cl["net"]][lay].append((a, b))

    n_m3_nets = sum(1 for n in net_ids if layer_spans[n]["M3"])
    unresolved = []
    if color_fail:
        for key in clusters:
            if key not in color:
                unresolved.append(key)
    return layer_spans, n_m3_nets, color_fail, crossing_pairs, unresolved


def route_seg_geoms(routes, wg):
    out = []
    for _net_id, segs in (routes or {}).items():
        seg_list = segs if isinstance(segs, (list, tuple)) else [segs]
        for seg in seg_list:
            pts = [tuple(p) for p in getattr(seg, "points_um", seg)]
            out.append(("P", str(getattr(seg, "layer", "M1")).upper(), wg, tuple(pts)))
    return out


def render_svg(geoms, title, path, layer_colors=None):
    xs, ys = [], []
    for g in geoms:
        for (px, py) in (g[3] if len(g) >= 4 else ()):
            xs.append(px); ys.append(py)
    if not xs:
        xs, ys = [0.0], [0.0]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    mx, my = minx - 4, miny - 4
    w, h = (maxx - minx) + 8, (maxy - miny) + 8
    scale = 660.0 / max(w, h)
    lc = layer_colors or {"M1": "#38bdf8", "M2": "#f59e0b", "DEV": "#22d3ee",
                          "IO": "#a78bfa"}
    parts = []
    for g in geoms:
        kind, layer, width, pts = g[0], g[1], g[2], g[3]
        sp = " ".join(f"{px*scale:.1f},{py*scale:.1f}" for (px, py) in pts)
        if kind == "P":
            col = lc.get(layer, "#38bdf8")
            sw = max(0.6, (width or WG) * scale)
            parts.append(f'<polyline points="{sp}" fill="none" stroke="{col}" '
                         f'stroke-width="{sw:.2f}" stroke-linejoin="round" '
                         f'stroke-linecap="round"/>')
        else:
            parts.append(f'<polygon points="{sp}" fill="{lc["DEV"]}" '
                         f'fill-opacity="0.5" stroke="{lc["DEV"]}" '
                         f'stroke-width="0.5"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="'
           f'{mx*scale:.1f} {my*scale:.1f} {w*scale:.1f} {h*scale:.1f}" '
           f'width="{w*scale:.0f}" height="{h*scale:.0f}" '
           f'style="background:#0b1220">\n' + "\n".join(parts) +
           f'\n<text x="{mx*scale:.1f}" y="{(my+2)*scale:.1f}" fill="#94a3b8" '
           f'font-size="11" font-family="monospace">{title}</text>\n</svg>\n')
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)


# ── Clements 矩形折叠网格连接计划 ────────────────────────────────────────────────
def _clements_plan(N):
    """生成 Clements 矩形折叠网格的连接计划。

    返回 (mzis, connects, order_final)：
      mzis:      list of (mid, s, pa, pb)  # 物理 stage s，物理 rail pa/pb
      connects:  list of (net, s_dev, s_port, d_dev, d_port)
    算法：维护 order（当前 rail 逻辑↔物理映射）；每 stage s 的 active pairs 为
      s 偶 → (0,1),(2,3),... ；s 奇 → (1,2),(3,4),...（N 偶）。每个 pair (a,b) 取
      物理 rail pa=order[a], pb=order[b]，建 MZI 串入两条 rail；stage 末 order 反转。
    """
    if N % 2 != 0:
        raise ValueError("本生成器当前仅支持偶数 N（Clements 矩形折叠）")
    order = list(range(N))
    rail_cur = {j: (f"in{j}", "wg") for j in range(N)}
    mzis = []
    connects = []
    net = [0]

    def nn():
        net[0] += 1
        return f"n{net[0]}"

    for s in range(N - 1):
        if s % 2 == 0:
            idx_pairs = [(2 * k, 2 * k + 1) for k in range(N // 2)]
        else:
            idx_pairs = [(2 * k + 1, 2 * k + 2) for k in range(N // 2 - 1)]
            idx_pairs.append((0, N - 1))   # 折叠边界对（蛇形回转，Clements 奇数层必有）
        for (ia, ib) in idx_pairs:
            pa, pb = order[ia], order[ib]
            mid = f"m{len(mzis)}"
            mzis.append((mid, s, pa, pb))
            sa, sap = rail_cur[pa]
            sb, sbp = rail_cur[pb]
            connects.append((nn(), sa, sap, mid, "in1"))
            connects.append((nn(), sb, sbp, mid, "in2"))
            rail_cur[pa] = (mid, "out1")
            rail_cur[pb] = (mid, "out2")
        order = order[::-1]
    for j in range(N):
        dj, dp = rail_cur[j]
        connects.append((nn(), dj, dp, f"out{j}", "wg"))
    return mzis, connects, order


def build_nxn_mesh(N, out_dir=HERE, return_geoms: bool = False):
    """构建 N×N MZI 网格主权 P&R（Clements 折叠），返回报告 dict。

    return_geoms=True 时额外返回几何原语元组列表 geoms
    （(kind, layer, width, pts)），供 SoC 设计包把它并入同一份主权 GDS
    （C8：光子层 + 电子层 + 光 IO 层协同）。默认 False，不改变既有行为。
    """
    if N % 2 != 0:
        raise ValueError("N 必须为偶数")
    # 计算核数学层（Reck 分解独立验证 N×N 可重构）
    U_target = dft_matrix(N)
    ops, D = reck_decompose(U_target)
    if len(ops) != N * (N - 1) // 2:
        raise RuntimeError(f"Reck 应得 {N*(N-1)//2} 单元，得 {len(ops)}")

    mzis, connects, _ = _clements_plan(N)
    assert len(mzis) == N * (N - 1) // 2

    link = LinkModel(domain="photon", name=f"lda_{N}x{N}_mzi_mesh",
                     notes=f"{N}x{N} MZI mesh (Clements folded) P&R feasibility")
    # 50/50 定向耦合器：Lc 由 CMT 锚定 θ=π/2
    Lc_50_50 = coupler_length_from_theta(math.pi / 2.0)
    for j in range(N):
        link.add_device(f"in{j}", "GratingCoupler", {"width": WG, "L": 10.0})
        link.add_device(f"out{j}", "GratingCoupler", {"width": WG, "L": 10.0})
    for (mid, _s, _pa, _pb) in mzis:
        link.add_device(mid, "DirectionalCoupler",
                        {"width": WG, "gap": 0.3, "Lc": round(Lc_50_50, 4)})
    for (net, s, sp, d_, dp) in connects:
        link.connect(net, s, sp, d_, dp)
    for j in range(N):
        link.external_io(f"io_in{j}", f"in{j}", "fib")
        link.external_io(f"io_out{j}", f"out{j}", "fib")
    link.validate()

    # 布局
    rail_pitch = 14.0
    x_in, x0, x_out = -15.0, 20.0, 20.0 + (N - 1) * 35.0 + 40.0
    placement = {}
    for j in range(N):
        placement[f"in{j}"] = (x_in, j * rail_pitch, 0.0)
        placement[f"out{j}"] = (x_out, j * rail_pitch, 0.0)
    # MZI 放其连接的两 rail 之间（min rail + 0.5 格），stage 内不重叠；
    # 边界对(0,N-1) 用 y=0.5 格（不与内部对冲突，因内部对 min 为奇数格）。
    for (mid, s, pa, pb) in mzis:
        x = x0 + s * 35.0
        y = (min(pa, pb) + 0.5) * rail_pitch
        placement[mid] = (x, y, 0.0)

    obstacles = []
    for c in link.ir.components:
        ox, oy, _ = placement[c.id]
        hw, hh = device_bbox(c.kind, dict(c.params))
        obstacles.append((ox, oy, hw + WG, hh + WG))

    PRE, POST = 10.0, 10.0

    def _outward(p, toward, L):
        dx, dy = toward[0] - p[0], toward[1] - p[1]
        m = math.hypot(dx, dy) or 1.0
        return (round(p[0] + dx / m * L, 4), round(p[1] + dy / m * L, 4))

    base_routes = {}
    route_paths = {}
    for (net, s, sp, d_, dp) in connects:
        a = port_abs(s, sp, placement, link)
        b = port_abs(d_, dp, placement, link)
        a2 = _outward(a, b, PRE)
        b2 = _outward(b, a, POST)
        rr = route_net(net, a2, b2, obstacles=obstacles, wg_width=WG,
                       bend_radius=5.0, corner="round", layer="M1")
        if rr is None:
            full = [a, a2, b2, b]
        else:
            full = [tuple(a)] + [tuple(p) for p in rr.points_um] + [tuple(b)]
        dedup = [full[0]]
        for p in full[1:]:
            if _d(dedup[-1], p) > 1e-6:
                dedup.append(p)
        base_routes[net] = _seg(net, dedup, "M1")
        route_paths[net] = dedup

    # DEBUG（S4 规模债离线求解）：落盘原始 routes + 弧长 + 布线端点/障碍，供迭代冲突化解算法
    if os.environ.get("LDA_S4_PICKLE"):
        import pickle as _pkl
        _connects_info = []
        for (net, s, sp, d_, dp) in connects:
            a = port_abs(s, sp, placement, link)
            b = port_abs(d_, dp, placement, link)
            a2 = _outward(a, b, PRE)
            b2 = _outward(b, a, POST)
            _connects_info.append((net, a, a2, b, b2))
        _dbg = {
            "N": N,
            "net_ids": sorted(route_paths.keys()),
            "route_paths": {n: [tuple(p) for p in route_paths[n]] for n in route_paths},
            "cum_len": {n: _cum_arclen(route_paths[n]) for n in route_paths},
            "connects_info": _connects_info,
            "obstacles": [tuple(o) for o in obstacles],
            "wg": WG,
            "bend": 5.0,
        }
        with open(os.environ["LDA_S4_PICKLE"], "wb") as _f:
            _pkl.dump(_dbg, _f)
        print("PICKLED_ROUTES", os.environ["LDA_S4_PICKLE"], flush=True)
    if os.environ.get("LDA_S4_ROUTES_ONLY"):
        return {"N": N, "_routes_only": True,
                "route_paths": {n: [tuple(p) for p in route_paths[n]] for n in route_paths},
                "n_routed_nets": len(route_paths)}

    # 冲突检测 + 逐冲突分配 M2 跳（点交叉 + 近距重叠段，统一化解为 M2 区间跳）
    # 机制：任意两网在 M1 层投影冲突（交叉点 或 共线重叠段）→ 让字典序大者(nj)跳 M2
    # 覆盖该冲突区间，另一网(ni)留 M1；异层投影重叠 can_cross(M1,M2)=False 不判短 →
    # 多层 LVS ACCEPT。绝不同时跳两网（否则 M2∩M2 仍短）。
    STUB_MIN = 0.3   # 器件端口按 xy(tol=1.0µm)归属，不按层；M1 残段只需盖住端口即可
    # HOP：单交叉 M2 气泡半宽。须 ≥ 交叉几何延展(~0.5µm)以覆盖交叉点，但须 ≪ 同网相邻
    # 交叉间距，否则一处 M2 气泡会「溢出」盖住该网在相邻交叉处的 M1 判定 → M2∩M2 短接
    # （规模债根因）。N≥64 密集交叉下 HOP=3.0 溢出触发；收窄到 1.0 兼顾覆盖与隔离。
    HOP = 1.0
    OVERLAP_TOL = 0.12   # 仅捕获『真正重叠(间距≈0)』，避开合法最小间距(0.2µm)的相邻走线
    net_ids = sorted(base_routes.keys())
    cum_len = {n: _cum_arclen(route_paths[n]) for n in net_ids}
    tot_len = {n: cum_len[n][-1] for n in net_ids}

    def _can_host(n, s):
        return (s >= STUB_MIN) and (s <= tot_len[n] - STUB_MIN)

    # 交叉图多色层分配（S4 规模债根治）：
    #   2-着色覆盖全部点交叉 + 共线重叠段；N≥64 出现的奇圈（3 网同址互交等 2 层
    #   不可解结构）自动升级 3-着色，把奇圈组件内若干网抬到 M3（异层恒隔离，物理
    #   正确）→ 零同层短路，LVS ACCEPT。layer_spans: {net:{M1/M2/M3:[区间]}}。
    layer_spans, n_m3_nets, color_fail, crossing_pairs, unresolved = \
        _assign_layers_multicolor(route_paths, net_ids, cum_len, HOP, STUB_MIN, OVERLAP_TOL)

    routes = {}
    bridged = set()
    for net, rr in base_routes.items():
        segs = make_jumps(rr, layer_spans[net], stub_min=STUB_MIN)
        routes[net] = segs
        if any(getattr(s, "layer", "M1") in ("M2", "M3") for s in segs):
            bridged.add(net)

    res = export_chip_gds(link, placement, routes, wg_width=WG,
                          with_io_grating=True, rules=RULES, with_hierarchy=False)
    drc = res.get("drc_report") or {}
    lvs = res.get("lvs_report") or {}
    stats = res.get("gds_stats") or {}

    gds_path = os.path.join(out_dir, f"lda_{N}x{N}_mzi_mesh.gds")
    with open(gds_path, "wb") as f:
        f.write(res["gds_bytes"])
    geoms = (device_geoms(link, placement, WG)
             + io_grating_geoms(link, placement, WG)
             + route_seg_geoms(routes, WG))
    svg_path = os.path.join(out_dir, f"lda_{N}x{N}_mzi_mesh.svg")
    render_svg(geoms, f"{N}x{N} MZI mesh · M1蓝/M2琥珀/M3粉=跨层桥", svg_path,
               layer_colors={"M1": "#38bdf8", "M2": "#f59e0b", "M3": "#f472b6",
                             "DEV": "#22d3ee", "IO": "#a78bfa"})

    U_rec = assemble_mesh(ops, D, N)
    fid = unitary_fidelity(U_rec, U_target)
    loss = mesh_cascade_loss_db(len(ops), n_crossings=len(crossing_pairs))

    return {
        "name": f"lda_{N}x{N}_mzi_mesh",
        "title": f"MESH{N} · {N}×{N} MZI 网格 P&R（主权全链路，零 gdsfactory）",
        "io_ports": [f"in{j}.fib" for j in range(N)] + [f"out{j}.fib" for j in range(N)],
        "gds_path": gds_path, "gds_bytes": len(res["gds_bytes"]),
        "gds_bytes_raw": res["gds_bytes"],
        "n_components": len(link.ir.components),
        "gds_elements": stats.get("n_elements"),
        "bbox_um": stats.get("bbox_um"),
        "multilayer": stats.get("multilayer"),
        "drc_verdict": "PASS" if drc.get("all_pass") else "FAIL",
        "lvs_verdict": (lvs.get("verdict") or "SKIP"),
        "lvs_violations": lvs.get("violations"),
        "n_routed_nets": len(base_routes),
        "n_mzi": len(mzis),
        "n_crossing_pairs": len(crossing_pairs),
        "n_bridged_nets": len(bridged), "bridged_nets": sorted(bridged),
        "n_m3_nets": n_m3_nets,
        "n_layer_repairs": n_m3_nets,
        "color_fail": color_fail,
        "n_unresolved_crossings": len(unresolved),
        "unresolved_crossings": [list(p) for p in unresolved],
        "compute_core": {
            "N": N, "n_mzi": len(ops), "fidelity": round(fid, 6),
            "cascade_loss_db": round(loss, 3),
            "scheme": "Clements folded (uniform 50/50 couplers, Lc CMT-anchored)",
        },
        "svg_path": svg_path,
        "geoms": geoms if return_geoms else None,
    }


if __name__ == "__main__":
    import sys as _sys
    for N in (4, 8):
        try:
            r = build_nxn_mesh(N)
            print(f"=== {N}×{N} MZI 网格 P&R ===")
            print(f"GDS   : {r['gds_path']}  ({r['gds_bytes']} B, {r['gds_elements']} 元素, "
                  f"{r['n_components']} 组件, 多层={r['multilayer']})")
            print(f"DRC   : {r['drc_verdict']}")
            print(f"LVS   : {r['lvs_verdict']}  (viol={r['lvs_violations']})")
            print(f"布线   : {r['n_routed_nets']} 网 / MZI {r['n_mzi']} / 交叉对 {r['n_crossing_pairs']} "
                  f"/ 桥接网 {r['n_bridged_nets']}")
            print(f"计算核 : N={r['compute_core']['N']} MZI={r['compute_core']['n_mzi']} "
                  f"保真度={r['compute_core']['fidelity']} 级联损耗={r['compute_core']['cascade_loss_db']} dB")
        except Exception as e:
            print(f"=== {N}×{N} FAILED: {e} ===")
            _sys.exit(1)
