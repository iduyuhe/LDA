#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""B1 并行布线 smoke（v0.8.44）：批量 API 语义一致 + 并行收益 + 诚实边界。

守护点：
1. route_batch(workers=1) 与逐条 route_net 逐位一致（判决不变性）
2. 链式场景 workers=1 vs 2 逐位一致（细粒度不破坏语义）
3. 障碍密集场景 workers=4 有真实收益（≥1.8×，证明并行框架不是摆设）
4. 诚实边界：congestion + workers>1 必须拒绝（不伪并行）
5. 可复现（固定种子）
"""
import random
import sys
import time

_HERE = __import__("os").path.dirname(__file__)
sys.path.insert(0, _HERE)

_PASS = _FAIL = 0


def check(name, ok, detail=""):
    global _PASS, _FAIL
    if ok:
        _PASS += 1
        print(f"  [PASS] {name}" + (f"  {detail}" if detail else ""))
    else:
        _FAIL += 1
        print(f"  [FAIL] {name}" + (f"  {detail}" if detail else ""))


def main():
    from lda_layout.router import route_net
    from lda_layout.parallel_routing import route_batch, route_batch_timing

    random.seed(9)
    obs = []
    for _ in range(300):
        obs.append((random.uniform(50, 950), random.uniform(50, 950),
                    random.uniform(15, 40), random.uniform(15, 40)))

    # ① 链式场景（12µs 粒度）：workers=1 vs 2 逐位一致
    nets_a = [(f"n{i}", (i * 10, 0.0), (i * 10, 200.0)) for i in range(50)]
    r1 = route_batch(nets_a, obstacles=[], workers=1)
    r2 = route_batch(nets_a, obstacles=[], workers=2)
    check("链式场景 workers=1 vs 2 逐位一致",
          len(r1) == len(r2) == 50 and all(r1[k] == r2[k] for k in r1))

    # ② 障碍密集场景：逐条 route_net vs batch(1) 逐位一致
    nets_b = [(f"m{i}", (random.uniform(0, 200), random.uniform(0, 200)),
               (random.uniform(800, 1000), random.uniform(800, 1000)))
              for i in range(20)]
    manual = {}
    for nid, s, d in nets_b:
        manual[nid] = route_net(nid, s, d, obstacles=obs, wg_width=0.5)
    rb = route_batch(nets_b, obstacles=obs, workers=1)
    check("障碍密集 逐条 vs batch(1) 逐位一致",
          all(manual[k] == rb[k] for k in manual))

    # ③ 并行收益：4 进程 ≥ 1.8×（真实加速，非摆设）
    rep = route_batch_timing(nets_b, obstacles=obs, workers_list=(1, 4))
    sp = rep["4"]["speedup_vs_1"]
    check(f"障碍密集 workers=4 收益 ≥1.8×（实测 {sp}×）", sp >= 1.8,
          f"1w={rep['1']['seconds']}s 4w={rep['4']['seconds']}s")

    # ④ 诚实边界：congestion + 并行必须拒绝
    from lda_layout.congestion import CongestionMap
    try:
        route_batch(nets_b, obstacles=obs, workers=2,
                    congestion=CongestionMap())
        check("congestion+并行 拒绝", False, "未拒绝（伪并行）")
    except ValueError:
        check("congestion+并行 拒绝", True)

    # ⑤ 顺序保持：返回 dict 键序 == 输入序
    keys = list(rb.keys())
    check("结果顺序与输入一致", keys == [n[0] for n in nets_b])

    print(f"\n并行布线 smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
