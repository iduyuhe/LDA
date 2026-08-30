"""LVS 短路检测：线段网格(_collect_cross_shorts) vs naive O(n²) 真值 字节级等价铁证。

红线：任何提速必须证明 verdict 集合逐字节一致。本脚本用 NAIVE 纯双重循环
（仅调用 _paths_cross 精确语义，不依赖任何网格）作为 ground truth，与 NEW
_collect_cross_shorts（线段网格，O(n) 规模）逐字节比对。naive 基准不绑死任一
实现，守护可长期运行。

覆盖：单集合 i<j、跨层 A×B（含同 id）、共享端点、自接触、长跨全图链、随机密度。
全部断言 naive == new（sorted 列表逐元素相等）即通过。
"""
import math
import os
import random
import sys

_LDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lda")
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

from lda_l2 import lvs as L  # 当前模块

# ---------------------------------------------------------------------------
# NEW：线段网格候选收敛（随后原样搬入 lvs.py）
# ---------------------------------------------------------------------------
def _collect_cross_shorts(paths_by_id, other=None):
    ids_a = sorted(paths_by_id.keys())
    if not ids_a:
        return []
    if other is None:
        ids_b = ids_a
    else:
        ids_b = sorted(other.keys())
        if not ids_b:
            return []

    segs = []  # (net_id, src, (ax,ay),(bx,by))
    for nid in ids_a:
        pts = paths_by_id[nid]
        for k in range(len(pts) - 1):
            segs.append((nid, 0, tuple(pts[k]), tuple(pts[k + 1])))
    if other is not None:
        for nid in ids_b:
            pts = other[nid]
            for k in range(len(pts) - 1):
                segs.append((nid, 1, tuple(pts[k]), tuple(pts[k + 1])))
    if not segs:
        return []

    xmin = ymin = float("inf")
    xmax = ymax = float("-inf")
    for (_, _, a, b) in segs:
        for (px, py) in (a, b):
            if px < xmin:
                xmin = px
            if py < ymin:
                ymin = py
            if px > xmax:
                xmax = px
            if py > ymax:
                ymax = py
    span = max(xmax - xmin, ymax - ymin, 1e-9)
    nseg = len(segs)
    cell = max(span / max(math.sqrt(nseg), 1.0), 1e-6)

    grid = {}
    for idx, (nid, src, a, b) in enumerate(segs):
        ax0, ay0, ax1, ay1 = (min(a[0], b[0]), min(a[1], b[1]),
                              max(a[0], b[0]), max(a[1], b[1]))
        gx0, gy0 = int(ax0 // cell), int(ay0 // cell)
        gx1, gy1 = int(ax1 // cell), int(ay1 // cell)
        for gx in range(gx0, gx1 + 1):
            for gy in range(gy0, gy1 + 1):
                grid.setdefault((gx, gy), []).append(idx)

    tested = set()
    result = set()
    p_a = paths_by_id
    p_b = paths_by_id if other is None else other
    for occ in grid.values():
        Ln = len(occ)
        for ii in range(Ln):
            ia = occ[ii]
            na, sa, _, _ = segs[ia]
            for jj in range(ii + 1, Ln):
                ib = occ[jj]
                nb, sb, _, _ = segs[ib]
                if other is None:
                    if na == nb:
                        continue
                    key = (na, nb) if na < nb else (nb, na)
                    if key in tested:
                        continue
                    tested.add(key)
                    if L._paths_cross(p_a[na], p_a[nb]):
                        result.add(key)
                else:
                    if sa == sb:
                        continue
                    a_net, b_net = (na, nb) if sa == 0 else (nb, na)
                    key = (a_net, b_net)
                    if key in tested:
                        continue
                    tested.add(key)
                    if L._paths_cross(p_a[a_net], p_b[b_net]):
                        result.add(key)
    return sorted(result)


# ---------------------------------------------------------------------------
# NAIVE：纯双重循环真值基准（不依赖任何网格——是短路集合的 ground truth，
# 仅调用 _paths_cross 精确语义）。新线段网格 _collect_cross_shorts 是超集过滤，
# 两者输出应逐字节相等（等价铁证可持续运行，不绑死任一实现）。
# ---------------------------------------------------------------------------
def _old_single(paths):
    ids = sorted(paths.keys())
    out = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            n1, n2 = ids[i], ids[j]
            if L._paths_cross(paths[n1], paths[n2]):
                out.append((n1, n2))
    return sorted(out)


def _old_cross(pl1, pl2):
    ids_a = sorted(pl1.keys())
    ids_b = sorted(pl2.keys())
    out = []
    for n1 in ids_a:
        for n2 in ids_b:
            if L._paths_cross(pl1[n1], pl2[n2]):
                out.append((n1, n2))
    return sorted(out)


# ---------------------------------------------------------------------------
# 随机场景生成
# ---------------------------------------------------------------------------
def _rand_paths(rng, n_nets, area=1000.0, max_pts=6, p_share=0.15):
    paths = {}
    anchors = []
    for i in range(n_nets):
        npts = rng.randint(2, max_pts)
        pts = []
        for _ in range(npts):
            if anchors and rng.random() < p_share:
                pts.append(rng.choice(anchors))   # 共享端点（练 shared-endpoint 跳过）
            else:
                p = (round(rng.uniform(0, area), 3), round(rng.uniform(0, area), 3))
                pts.append(p)
                anchors.append(p)
        paths[f"net_{i}"] = pts
    return paths


def _long_spanning(rng, n_nets, area=2000.0):
    """长链横穿全图（练旧实现的退化全对回退路径）。"""
    paths = {}
    for i in range(n_nets):
        y = round(rng.uniform(0, area), 3)
        paths[f"net_{i}"] = [(0.0, y), (area, y)]
    return paths


def main():
    rng = random.Random(20260830)
    fails = 0
    total = 0

    # 1) 单集合随机密度（等价性是超集结构性证明，小样本即可）
    for scale in (10, 50, 200, 400):
        for trial in range(5):
            paths = _rand_paths(rng, scale)
            old = _old_single(paths)
            new = _collect_cross_shorts(paths)
            total += 1
            if old != new:
                fails += 1
                print(f"[FAIL single] scale={scale} trial={trial} "
                      f"old_n={len(old)} new_n={len(new)}")
                so, sn = set(old), set(new)
                print("  only_old:", list(so - sn)[:3])
                print("  only_new:", list(sn - so)[:3])

    # 2) 跨层 A×B（M1 全 / M2 子集），含同 id 跨层
    for scale in (10, 50, 200, 400):
        for trial in range(5):
            pl1 = _rand_paths(rng, scale)
            pl2 = _rand_paths(rng, max(1, scale // 4))
            for k in range(min(3, len(pl2))):
                pl2[f"net_{k}"] = pl1[f"net_{k}"]
            old = _old_cross(pl1, pl2)
            new = _collect_cross_shorts(pl1, other=pl2)
            total += 1
            if old != new:
                fails += 1
                print(f"[FAIL cross] scale={scale} trial={trial} "
                      f"old_n={len(old)} new_n={len(new)}")
                so, sn = set(old), set(new)
                print("  only_old:", list(so - sn)[:3])
                print("  only_new:", list(sn - so)[:3])

    # 3) 长跨全图（旧实现的退化全对回退路径）
    for scale in (10, 50, 200, 400, 800):
        paths = _long_spanning(rng, scale)
        old = _old_single(paths)
        new = _collect_cross_shorts(paths)
        total += 1
        if old != new:
            fails += 1
            print(f"[FAIL long] scale={scale} old_n={len(old)} new_n={len(new)}")

    # 4) 共享端点/自接触边界
    paths = {
        "a": [(0.0, 0.0), (10.0, 10.0)],
        "b": [(0.0, 0.0), (10.0, 0.0)],          # 共享 (0,0)
        "c": [(10.0, 10.0), (20.0, 0.0)],        # 共享 (10,10) with a
        "d": [(5.0, 5.0), (5.0, 5.0)],           # 退化单点
    }
    old = _old_single(paths)
    new = _collect_cross_shorts(paths)
    total += 1
    if old != new:
        fails += 1
        print(f"[FAIL edge] old={old} new={new}")

    print(f"\n=== 等价性断言: {total} 组, FAIL={fails} ===")
    if fails == 0:
        print("PASS · 新线段网格(_collect_cross_shorts) 与 naive O(n²) 真值基准输出逐字节一致 ✓")
    else:
        print("FAIL · 存在语义差异，禁止合并")
    return fails


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)