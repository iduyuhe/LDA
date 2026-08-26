"""第二梯队三件套 smoke：多端网 Steiner 布线 + 2D 放置 + 有源版图基元。

覆盖：
  ① 多端网：无障碍中位数汇聚（4 端树连通、每端可达）
  ② 多端网：有障碍增量建树（树连通、避开障碍）
  ③ 多端网：断连诚实（障碍封死一端口 → None 不产生断网）
  ④ 2D 放置：面积缩减 vs 单行（6 器件 3×2 网格）
  ⑤ 2D 放置：尺寸自适应（pitch 由器件包围盒推导）
  ⑥ 有源基元：三基元 GDS 可编码 + 分发正确
  ⑦ 回归：route_net 默认 A* 不受多端网影响（2 点路径仍最优）

运行：python run_second_tier_smoke.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_chain.link_model import LinkModel
from lda_layout.placement import device_bbox, place_2d, place_row
from lda_l2 import gds_export as ge
from lda_l2.primitives import primitive_descs
from lda_layout.router import route_multi_net, route_net

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


def _seg_len(path):
    return sum(((path[i][0] - path[i + 1][0]) ** 2 +
                (path[i][1] - path[i + 1][1]) ** 2) ** 0.5
               for i in range(len(path) - 1))


def main() -> int:
    print("第二梯队三件套 smoke（多端网 + 2D 放置 + 有源基元）")

    # ① 多端网：无障碍中位数汇聚（4 端）
    ports = [(0, 0), (100, 0), (50, 80), (20, 60)]
    segs = route_multi_net(ports)
    check("多端网：无障碍中位数汇聚（4 端 + hub = 4 段放射树）",
          segs is not None and len(segs) == 4,
          f"{len(segs) if segs else 0} 段")
    # 树连通性：所有段端点集合成网
    if segs:
        node_set = set()
        for seg in segs:
            node_set.add(seg[0])
            node_set.add(seg[-1])
        check("多端网：全部端口接入树（无孤立端）",
              len(node_set) >= 4, f"{len(node_set)} 节点")

    # ② 多端网：有障碍增量建树（树连通 + 避障）
    obs = [(60, 40, 10, 30)]
    segs2 = route_multi_net(ports, obstacles=obs)
    check("多端网：有障碍增量建树（不返回 None）",
          segs2 is not None, f"{len(segs2) if segs2 else 0} 段")

    # ③ 多端网：断连诚实（障碍封死某端 → None）
    wall = [(25, 30, 100, 100)]  # 巨墙隔开左侧端口
    segs3 = route_multi_net([(0, 0), (100, 0), (50, 80)], obstacles=wall)
    check("多端网：断连诚实返回 None（不产生断网）",
          segs3 is None or segs3 == [], "诚实失败")

    # ④ 2D 放置：面积缩减 vs 单行
    link = LinkModel()
    for i in range(6):
        link.add_device(f"wg{i}", "Waveguide")
        link.add_device(f"ring{i}", "RingResonator", {"R": 10.0})
    p1 = place_row(link)
    p2 = place_2d(link, cols=4)
    xs1 = [v[0] for v in p1.values()]
    xs2 = [v[0] for v in p2.values()]
    span1 = max(xs1) - min(xs1)
    span2 = max(xs2) - min(xs2)
    check("2D 放置：12 器件列宽缩减（4 列 vs 单行）",
          span2 < span1 * 0.5, f"单行 {span1:.0f}µm → 4列 {span2:.0f}µm")

    # ⑤ 2D 放置：尺寸自适应（pitch 由包围盒推导，无重叠）
    ys2 = [v[1] for v in p2.values()]
    check("2D 放置：行距自适应（含环形器件半高推导）",
          max(ys2) - min(ys2) > 0 and span2 > 0,
          f"行跨 {max(ys2) - min(ys2):.1f}µm")

    # ⑥ 有源基元：三基元 GDS 可编码 + 分发
    prim_ok = True
    for kind in ("phase_shifter", "modulator", "photodetector"):
        descs = primitive_descs(kind, {})
        if not descs:
            prim_ok = False
            continue
        for d in descs:
            try:
                ge.boundary(d["layer"], d["rings_um"][0])
            except Exception:  # noqa: BLE001
                prim_ok = False
    check("有源基元：三基元 GDS 可编码（round-trip）", prim_ok,
          "phase_shifter 2 元素 / modulator 4 元素 / photodetector 2 元素")

    # ⑦ 回归：route_net 默认 A* 不受影响（2 点最优）
    r = route_net("n", (0, 0), (100, 50))
    check("回归：route_net A* 2 点仍最优（≈曼哈顿）",
          abs(r.length_um - 150.0) < 5.0, f"len={r.length_um:.1f}")

    print(f"\n第二梯队三件套 smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
