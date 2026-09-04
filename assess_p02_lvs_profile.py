"""P0-2 探路：量化 LVS 在各规模下的耗时分布与增长阶。

目的：判断「层次化 LVS」是否值得做、收益上限在哪。只用实测，不猜。
"""
import cProfile
import io
import pstats
import sys
import time

sys.path.insert(0, r"D:\agent_LDA\lda")

from lda_agent.orchestrator import Orchestrator  # noqa: E402


def main():
    from lda_harness.scale_anchor import build_chain_case
    from lda_l2.layers import get_stack
    from lda_l2.lvs import run_lvs_multilayer
    stack = get_stack("soi")
    scales = [32000, 64000, 128000]
    print(f"{'器件数':>10} {'构建s':>8} {'LVS s':>8} {'LVS µs/器件':>12}")
    rows = []
    for n in scales:
        t0 = time.time()
        link, placement, routes = build_chain_case(n)
        t_build = time.time() - t0
        t1 = time.time()
        rep = run_lvs_multilayer(link, placement, routes, stack=stack)
        t_lvs = time.time() - t1
        us = t_lvs / max(n, 1) * 1e6
        rows.append((n, t_build, t_lvs))
        print(f"{n:>10} {t_build:>8.2f} {t_lvs:>8.2f} {us:>12.2f}  verdict={rep.get('verdict')}")

    if len(rows) >= 2:
        import math
        (n1, _, l1), (n2, _, l2) = rows[0], rows[-1]
        if l1 > 0 and l2 > 0:
            order = math.log(l2 / l1) / math.log(n2 / n1)
            print(f"\nLVS 增长阶 O(n^{order:.2f})（{n1}→{n2}）")
            print(f"外推 1M 器件 LVS ≈ {l2 * (1_000_000 / n2) ** order:.1f}s")

    # 顶层函数耗时剖析（用最大规模）
    n = scales[-1]
    link, placement, routes = build_chain_case(n)
    pr = cProfile.Profile()
    pr.enable()
    run_lvs_multilayer(link, placement, routes, stack=stack)
    pr.disable()
    s = io.StringIO()
    pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(14)
    print("\n=== LVS 热点（cumulative top 14）===")
    print(s.getvalue()[:2600])


if __name__ == "__main__":
    main()
