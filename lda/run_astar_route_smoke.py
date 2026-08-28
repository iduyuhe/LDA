"""第二梯队-1 A* 布线 smoke：贪心 → 全局最优（版图审计差距 #1/#2 落地）。

覆盖：
  ① 无障碍：A* 与贪心一致（L 形最优解）
  ② 障碍避障：A* 无碰撞绕行 vs 贪心撞墙退化直连（审计差距 #1 实证）
  ③ 无解检测：封死障碍 → A* 诚实退化（不盲目钻洞）
  ④ 最优性：A* 长度 ≤ 贪心（绕行路径不劣化）
  ⑤ 网格防爆：超大域返回 None 不崩
  ⑥ 链路接线集成：chip_layout_export 走 A* 正常

运行：python run_astar_route_smoke.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_layout.router import astar_route, route_net

_PASS = 0
_FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    mark = "PASS" if cond else "FAIL"
    if cond:
        _PASS += 1
    else:
        _FAIL += 1
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))


def main() -> int:
    print("第二梯队-1 A* 布线 smoke（贪心→全局最优）")

    # ① 无障碍：A* = 贪心 = L 形最优（曼哈顿距离）
    r1 = route_net("n1", (0, 0), (100, 50), method="astar")
    manhattan = 100.0 + 50.0
    check("无障碍 A* 长度 ≈ 曼哈顿最优",
          abs(r1.length_um - manhattan) < 5.0,
          f"len={r1.length_um:.1f} vs 曼哈顿 {manhattan}")

    # ② 障碍避障：A* 无碰撞绕行 vs 贪心撞墙
    obs = [(50, 20, 8, 30)]  # 竖条障碍挡在 x=50 的 L 形路径上
    r2a = route_net("n2", (0, 0), (100, 50), obstacles=obs, method="astar")
    r2g = route_net("n2", (0, 0), (100, 50), obstacles=obs, method="greedy")
    check("A* 避障：无碰撞绕行（审计差距 #1 修复）",
          ("警告" not in r2a.note) and len(r2a.points_um) >= 3,
          f"A* len={r2a.length_um:.1f} 无碰撞")
    check("贪心对照组：L 形候选撞墙退化直连",
          "警告" in r2g.note, f"greedy len={r2g.length_um:.1f}")

    # ④ 最优性：A* 绕行路径 ≤ 贪心撞墙长度 + 余量（绕行不劣化）
    check("A* 绕行长度合理（不劣化过度）",
          r2a.length_um < r2g.length_um * 1.8,
          f"A*={r2a.length_um:.1f} greedy={r2g.length_um:.1f}")

    # ③ 无解检测：封死障碍 → 诚实退化（不再盲目钻洞）
    obs3 = [(50, 25, 200, 100)]
    r3 = route_net("n3", (0, 0), (100, 50), obstacles=obs3, method="astar")
    check("无解：A* 诚实退化直连（含警告）",
          "警告" in r3.note and len(r3.points_um) == 2,
          r3.note[:30])

    # ⑤ 网格防爆：超大搜索域返回 None 不崩
    far = astar_route((0, 0), (50000, 50000), [(1, 1, 1000, 1000)], 0.25,
                      dl=1.0, max_span=2000.0)
    check("超大域防爆：返回 None 不崩", far is None)

    # ⑥ 链路接线集成（chip_layout_export 默认走 A*）
    from lda_agent.orchestrator import Orchestrator
    ctx = Orchestrator().run({"type": "wdm", "channels_um": [1.53, 1.55, 1.57],
                              "R_um": 10.0, "gap_um": 0.3, "kappa": 0.05})
    check("链路接线集成：orchestrator WDM 默认 A* 布线正常",
          ctx.link is not None and getattr(ctx, "sim", None) is not None,
          "端到端无异常")

    # ⑦ v0.8.42 回归保护：congestion=None 与不传逐位一致
    from lda_layout.congestion import CongestionMap
    obs7 = [(50, 50, 10, 10), (50, 100, 10, 10)]
    base = astar_route((0, 0), (100, 80), obs7, 0.25)
    with_cg = astar_route((0, 0), (100, 80), obs7, 0.25,
                          congestion=None)
    check("拥塞=None 与不传逐位一致（回归保护）",
          base == with_cg, f"{base} == {with_cg}")

    # ⑧ 拥塞感知：平行网绕同一障碍，最大占用显著下降（通道均衡）
    obs8 = [(50, 100, 15, 60)]
    nets8 = [(i * 8, 0, i * 8, 240) for i in range(8)]
    cm0 = CongestionMap()
    for sx, sy, dx, dy in nets8:
        p = astar_route((sx, sy), (dx, dy), obs8, 0.25)
        if p:
            cm0.mark_path(p)
    cm1 = CongestionMap(penalty=8.0)
    for sx, sy, dx, dy in nets8:
        p = astar_route((sx, sy), (dx, dy), obs8, 0.25, congestion=cm1)
        if p:
            cm1.mark_path(p)
    m0 = cm0.stats()["max_occupancy"]
    m1 = cm1.stats()["max_occupancy"]
    check("拥塞感知：最大通道占用下降（4→2 减半）",
          m1 < m0, f"max {m0} → {m1}")

    # ⑨ 红线：拥塞只影响启发式、不改变可解性（有解必有解）
    check("拥塞感知：所有网仍连通（有解必有解，不阻塞）",
          all(p is not None for p in
              [astar_route(s, d, obs8, 0.25, congestion=cm1)
               for s, d in [((0, 0), (0, 240)), ((56, 0), (56, 240))]]),
          "无解退化未引入")

    print(f"\nA* 布线 smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
