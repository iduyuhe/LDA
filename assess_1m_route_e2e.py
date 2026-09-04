"""百万级器件规模评估 · B2 端到端增量布线（真实顺序布线流程）。

模拟真实流程：器件已放置，逐条布线，每布一条把它加入障碍集
（后续网必须避让已布线）→ 直接测量端到端布线总时间的增长阶。
  O(N)   ⇒ 斜率 ~2x
  O(N^2) ⇒ 斜率 ~4x  ← 灾难区
"""
from __future__ import annotations

import math
import sys
import time

sys.path.insert(0, "D:/agent_LDA/lda")
from lda_layout.router import route_net  # noqa: E402


def run_incremental(n_nets: int, pitch: float = 60.0):
    """n_nets 条网，器件排成一行，相邻互连；每条布线避让此前所有已布线。"""
    cols = max(2, int(math.isqrt(n_nets)) + 1)
    pts = []
    for i in range(n_nets + 1):
        r, c = divmod(i, cols)
        pts.append((c * pitch, r * pitch))

    obstacles: list = []
    t0 = time.perf_counter()
    ok = 0
    for i in range(n_nets):
        a, b = pts[i], pts[i + 1]
        r = route_net(f"net_{i}", a, b, obstacles=obstacles)
        if r and getattr(r, "points_um", None):
            ok += 1
            pl = r.points_um
            for k in range(len(pl) - 1):
                (x0, y0), (x1, y1) = pl[k], pl[k + 1]
                obstacles.append((min(x0, x1) - 1.0, min(y0, y1) - 1.0,
                                  max(x0, x1) + 1.0, max(y0, y1) + 1.0))
    dt = time.perf_counter() - t0
    return dt, ok, n_nets


if __name__ == "__main__":
    print("=" * 72)
    print("B2 · 端到端增量布线：总耗时 vs 网数（障碍=已布线，真实顺序流程）")
    print("=" * 72)
    print(f"{'n_nets':>8} {'total_s':>10} {'x/2x':>8} {'ms/net':>10} "
          f"{'外推1M_net(h)':>16}", flush=True)
    prev = None
    for n in (5, 10, 20, 40):
        dt, ok, n_nets = run_incremental(n)
        per = dt / n_nets * 1000
        x = "" if prev is None else f"{dt/prev:7.2f}x"
        # 由实测斜率外推到 1M 网（保守：用实测最后一段斜率）
        if prev is None:
            ext = ""
        else:
            slope = dt / prev
            hours = dt * (slope ** math.log2(1_000_000 / n_nets)) / 3600.0
            ext = f"{hours:,.1f}"
        print(f"{n:>8} {dt:>10.3f} {x:>8} {per:>10.2f} {ext:>16}", flush=True)
        prev = dt
    print("\nDONE", flush=True)
