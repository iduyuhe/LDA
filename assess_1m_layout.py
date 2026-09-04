"""百万级器件规模评估 · 版图层（A层签核链 + B层A*障碍路由）。

只读评估，不改任何产品代码。输出实测数据供战略判定。
"""
from __future__ import annotations

import gc
import os
import sys
import time
import tracemalloc

sys.path.insert(0, "D:/agent_LDA/lda")
sys.path.insert(0, "D:/agent_LDA/lda/lda_harness")

import psutil  # noqa: E402

PROC = psutil.Process()
PEAK_RSS = 0.0


def rss_gb() -> float:
    return PROC.memory_info().rss / 1e9


def tick() -> None:
    global PEAK_RSS
    PEAK_RSS = max(PEAK_RSS, rss_gb())


def hdr(t: str) -> None:
    print(f"\n{'='*72}\n{t}\n{'='*72}", flush=True)


# ---------------------------------------------------------------- A 层
def part_a():
    """A层：版图签核链（构建+放置+多层布线+LVS）规模外推。"""
    import scale_anchor as SA
    hdr("A层 · 版图签核链：构建+放置+布线+LVS（scale_anchor S11 全链路）")
    print(f"{'N':>9} {'build_s':>9} {'lvs_s':>9} {'total_s':>9} "
          f"{'x/prev':>7} {'RSS_GB':>8} {'verdict':>8}", flush=True)
    prev = None
    for n in (256_000, 512_000, 1_000_000):
        gc.collect()
        r0 = rss_gb()
        t0 = time.perf_counter()
        rep = SA.run_scale_pipeline(n, case="consistent")
        dt = time.perf_counter() - t0
        tick()
        x = "" if prev is None else f"{rep['time_total_s']/prev:6.2f}x"
        print(f"{n:>9} {rep['time_build_s']:>9.2f} {rep['time_lvs_s']:>9.2f} "
              f"{rep['time_total_s']:>9.2f} {x:>7} {rss_gb()-r0:>8.2f} "
              f"{rep['verdict']:>8}", flush=True)
        if rep["verdict"] != "ACCEPT":
            print(f"  !! N={n} verdict={rep['verdict']} — 语义回归！", flush=True)
        prev = rep["time_total_s"]
        del rep
        gc.collect()


# ---------------------------------------------------------------- B 层
def part_b():
    """B层：A* 避障路由的规模行为 —— 直接量化 O(N x 障碍)。

    固定源漏（同一段距离），只增障碍数，测单次 route_net 耗时。
    若耗时随障碍数线性增长 ⇒ 全局布 N 条网 = O(N^2)。
    """
    from lda_layout.router import route_net
    hdr("B层 · A* 避障路由：单次 route_net 耗时 vs 障碍数（固定源漏）")

    src = (0.0, 0.0)
    dst = (300.0, 300.0)

    def make_obstacles(n: int, span: float = 300.0):
        """在源漏附近散布 n 个小方块障碍（模拟已布器件/禁布区）。"""
        import math
        cols = int(math.isqrt(n)) + 1
        step = span / cols
        obs = []
        for i in range(n):
            r, c = divmod(i, cols)
            x = -50.0 + c * step
            y = -50.0 + r * step
            obs.append((x, y, x + step * 0.5, y + step * 0.5))
        return obs

    print(f"{'n_obs':>8} {'t_per_route_ms':>16} {'x/2x':>7}", flush=True)
    prev = None
    for n in (0, 250, 500, 1000, 2000, 4000, 8000):
        obs = make_obstacles(n)
        # 预热
        route_net("warm", src, dst, obstacles=obs[:1])
        reps = 3 if n <= 4000 else 2
        t0 = time.perf_counter()
        for k in range(reps):
            r = route_net(f"net_b{k}", src, dst, obstacles=obs)
        dt = (time.perf_counter() - t0) / reps
        x = "" if prev is None or prev == 0 else f"{dt/prev:6.2f}x"
        ok = "OK" if r else "FAIL(超网格上限)"
        print(f"{n:>8} {dt*1000:>16.2f} {x:>7}   {ok}", flush=True)
        prev = dt
        del obs
        gc.collect()


# ---------------------------------------------------------------- D 层
def part_d():
    """D层：1M 器件对象 + placement + routes 的内存实测。"""
    from lda_ir.core import Component
    hdr("D层 · 内存：1M 器件 IR + placement + routes")
    gc.collect()
    r0 = rss_gb()
    tracemalloc.start()
    comps = [Component(id=f"wg{i}", kind="Waveguide",
                       params={"length": 20.0}) for i in range(1_000_000)]
    tick()
    c1 = rss_gb()
    print(f"  1M Component 对象          : RSS +{c1-r0:6.2f} GB", flush=True)

    placement = {c.id: (float(i % 1000) * 30.0,
                        float(i // 1000) * 20.0, 0.0)
                 for i, c in enumerate(comps)}
    tick()
    c2 = rss_gb()
    print(f"  + 1M placement (dict+tuple): RSS +{c2-c1:6.2f} GB", flush=True)

    routes = {c.id: [[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]]
              for c in comps}
    tick()
    c3 = rss_gb()
    print(f"  + 1M routes (3点折线)      : RSS +{c3-c2:6.2f} GB", flush=True)
    print(f"  -------- 1M IR 常驻合计    : RSS +{c3-r0:6.2f} GB", flush=True)
    cur, peak = tracemalloc.get_traced_memory()
    print(f"  tracemalloc peak           : {peak/1e9:6.2f} GB", flush=True)
    tracemalloc.stop()
    del comps, placement, routes
    gc.collect()


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    print(f"机器: {psutil.cpu_count()} 核 / "
          f"{psutil.virtual_memory().total/1e9:.0f} GB RAM / "
          f"Python {sys.version.split()[0]}", flush=True)
    t0 = time.perf_counter()
    if which in ("all", "b"):
        part_b()
    if which in ("all", "d"):
        part_d()
    if which in ("all", "a"):
        part_a()
    print(f"\n全部完成 {time.perf_counter()-t0:.1f}s · 峰值RSS {PEAK_RSS:.2f} GB",
          flush=True)
