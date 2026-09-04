"""LVS 短路检测等价护栏（P0-2 · v0.9.35）：生产实现 vs naive O(n²) 真值 字节级等价。

🔴 红线：本护栏测试的是 **生产代码** lda_l2.lvs._collect_cross_shorts（不是任何
本地副本）。任何提速（v0.8.44 线段网格 / v0.9.34 bbox 复用 / v0.9.35 按轴独立 cell）
都必须证明 verdict 集合与 NAIVE 纯双重循环（仅调用 _paths_cross 精确语义、不依赖
任何网格）**逐字节一致**——否则禁止合并。

覆盖：单集合 i<j、跨层 A×B（含同 id）、共享端点、自接触、长跨全图链、随机密度、
以及 v0.9.35 特护的**狭长阵列**（全宽长段 × 多行，旧标量 cell 退化路径）。
全部断言 naive == new（sorted 列表逐元素相等）即通过。退出码 0=PASS / 1=FAIL。
"""
import math
import os
import random
import sys

_LDA = os.path.join(os.path.dirname(os.path.abspath(__file__)))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

from lda_l2 import lvs as L  # 生产模块（被测 _collect_cross_shorts 在此）

# ---------------------------------------------------------------------------
# NAIVE：纯双重循环真值基准（ground truth，仅调用 _paths_cross 精确语义）。
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
                pts.append(rng.choice(anchors))   # 共享端点
            else:
                p = (round(rng.uniform(0, area), 3), round(rng.uniform(0, area), 3))
                pts.append(p)
                anchors.append(p)
        paths[f"net_{i}"] = pts
    return paths


def _long_spanning(rng, n_nets, area=2000.0):
    """长链横穿全图（旧实现的退化全对回退路径）。"""
    paths = {}
    for i in range(n_nets):
        y = round(rng.uniform(0, area), 3)
        paths[f"net_{i}"] = [(0.0, y), (area, y)]
    return paths


def _elongated_lattice(rng, n_rows, n_cols=32, pitch=28.0, area_w=None):
    """v0.9.35 特护：**狭长阵列**（32 列 × n_rows 行，全宽长段 × 多行）。

    复刻 build_chain_case 的几何形态：行内水平段（局部）+ 跨行全宽 M2 跳线。
    旧标量 cell = span/√N 在 span_y 巨大时 cell_y 被拉爆 → 跨行退化；本场景
    正是对该退化的回归守护。"""
    area_w = area_w or (n_cols * pitch)
    paths = {}
    for r in range(n_rows):
        y = round(r * pitch, 3)
        for c in range(n_cols - 1):                 # 行内水平段（局部）
            x0 = round(c * pitch, 3)
            x1 = round((c + 1) * pitch, 3)
            paths[f"h_{r}_{c}"] = [(x0, y), (x1, y)]
        # 跨行全宽 M2 跳线（横穿整行）
        paths[f"j_{r}"] = [(0.0, round(y - 5.0, 3)),
                            (round(area_w, 3), round(y - 5.0, 3))]
    return paths


def main():
    rng = random.Random(20260830)
    fails = 0
    total = 0

    # 1) 单集合随机密度
    for scale in (10, 50, 200, 400):
        for trial in range(5):
            paths = _rand_paths(rng, scale)
            old = _old_single(paths)
            new = L._collect_cross_shorts(paths)          # 生产实现
            total += 1
            if old != new:
                fails += 1
                print(f"[FAIL single] scale={scale} trial={trial} "
                      f"old_n={len(old)} new_n={len(new)}")
                so, sn = set(old), set(new)
                print("  only_old:", list(so - sn)[:3])
                print("  only_new:", list(sn - so)[:3])

    # 2) 跨层 A×B（含同 id 跨层）
    for scale in (10, 50, 200, 400):
        for trial in range(5):
            pl1 = _rand_paths(rng, scale)
            pl2 = _rand_paths(rng, max(1, scale // 4))
            for k in range(min(3, len(pl2))):
                pl2[f"net_{k}"] = pl1[f"net_{k}"]
            old = _old_cross(pl1, pl2)
            new = L._collect_cross_shorts(pl1, other=pl2)  # 生产实现
            total += 1
            if old != new:
                fails += 1
                print(f"[FAIL cross] scale={scale} trial={trial} "
                      f"old_n={len(old)} new_n={len(new)}")

    # 3) 长跨全图（旧退化路径）
    for scale in (10, 50, 200, 400, 800):
        paths = _long_spanning(rng, scale)
        old = _old_single(paths)
        new = L._collect_cross_shorts(paths)
        total += 1
        if old != new:
            fails += 1
            print(f"[FAIL long] scale={scale} old_n={len(old)} new_n={len(new)}")

    # 4) 共享端点/自接触边界
    paths = {
        "a": [(0.0, 0.0), (10.0, 10.0)],
        "b": [(0.0, 0.0), (10.0, 0.0)],
        "c": [(10.0, 10.0), (20.0, 0.0)],
        "d": [(5.0, 5.0), (5.0, 5.0)],
    }
    old = _old_single(paths)
    new = L._collect_cross_shorts(paths)
    total += 1
    if old != new:
        fails += 1
        print(f"[FAIL edge] old={old} new={new}")

    # 5) v0.9.36 特护：狭长阵列（退化守护，含反例——人为制造一处真短路）
    #    n_rows=800 时 naive O(n²) 真值超 2min 超时，故止步 200（退化域已覆盖）。
    for n_rows in (50, 200):
        paths = _elongated_lattice(rng, n_rows)
        # 反例：在 (area_w/2, 0) 处放一条垂直段，横穿第 0 行所有水平段
        aw = 32 * 28.0
        paths["fault"] = [(round(aw / 2, 3), -1.0), (round(aw / 2, 3), 1.0)]
        old = _old_single(paths)
        new = L._collect_cross_shorts(paths)
        total += 1
        if old != new:
            fails += 1
            print(f"[FAIL elongated] n_rows={n_rows} old_n={len(old)} new_n={len(new)}")
            so, sn = set(old), set(new)
            print("  only_old:", list(so - sn)[:3])
            print("  only_new:", list(sn - so)[:3])

    print(f"\n=== 等价性断言: {total} 组, FAIL={fails} ===")
    if fails == 0:
        print("PASS · 生产 _collect_cross_shorts 与 naive O(n²) 真值基准逐字节一致 ✓")
    else:
        print("FAIL · 存在语义差异，禁止合并")
    return fails


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
