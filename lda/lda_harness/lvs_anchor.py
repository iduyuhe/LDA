"""LDA S9 锚 · LVS 版图-原理图一致性判决锚（签核级 · v0.8.24）。

S9 是**系统锚**（与 S1-S6 预算锚、S7/S8 统计锚并列）：LVS 是流片签核
的必要检查，其判决必须是**确定性可复现**的——同一案例任何人重跑得到
同一 ACCEPT/REJECT。S9 把「LVS 判决正确性」固化为标准题：

  - case='consistent'  ：一致版图（布线端点与端口锚点一一对应）→ 1.0（ACCEPT）
  - case='open'        ：断路（删一条布线）→ 0.0（REJECT，open 检出）
  - case='misconnect'  ：错连（两网布线互换）→ 0.0（REJECT，misconnect 检出）
  - case='short'       ：短路（两网共享端口）→ 0.0（REJECT，short 检出）
  - case='dangling'    ：悬空（布线端点无端口归属）→ 0.0（REJECT，dangling 检出）

golden = s9_lvs_verdict(case)（确定性算法判决），harness 用
|candidate − golden| ≤ tol 判定；判决路径零 LLM（纯坐标几何 + 集合比对）。

案例链路：3 器件（WG → Ring → WG），2 条内部 net（net_a/net_b）——
覆盖多端口器件（Ring in/out/drop）、多 net 互连的最小充分案例。
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA = os.path.dirname(_HERE)
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

from lda_chain.link_model import LinkModel
from lda_layout.placement import device_bbox, place_row, port_abs
from lda_layout.router import route_net
from lda_l2.lvs import run_lvs

CASES = ("consistent", "open", "misconnect", "short", "dangling")


def build_lvs_case(case: str = "consistent",
                   ) -> Tuple[LinkModel, Dict[str, Any], Dict[str, Any]]:
    """构造 LVS 案例：3 器件链路 + 放置 + 布线（正例/反例）。"""
    if case not in CASES:
        raise ValueError(f"case 须为 {CASES}，实际 {case}")

    link = LinkModel(name=f"s9_lvs_{case}")
    link.add_device("wg0", "Waveguide", {"length": 20.0})
    link.add_device("ring0", "RingResonator", {"R": 10.0})
    link.add_device("wg1", "Waveguide", {"length": 20.0})
    link.connect("net_a", "wg0", "out", "ring0", "in")
    link.connect("net_b", "ring0", "drop", "wg1", "in")

    placement = place_row(link)

    # 无障碍布线（正例基线）：net_a = wg0.out → ring0.in；net_b = ring0.drop → wg1.in
    pa = (port_abs("wg0", "out", placement, link),
          port_abs("ring0", "in", placement, link))
    pb = (port_abs("ring0", "drop", placement, link),
          port_abs("wg1", "in", placement, link))
    r_a = route_net("net_a", pa[0], pa[1])
    r_b = route_net("net_b", pb[0], pb[1])

    if case == "consistent":
        routes = {"net_a": r_a, "net_b": r_b}
    elif case == "open":            # 断路：删 net_b 布线
        routes = {"net_a": r_a}
    elif case == "misconnect":      # 错连：两网布线互换
        routes = {"net_a": r_b, "net_b": r_a}
    elif case == "short":           # 短路：net_b 起点错接到 wg0.out（与 net_a 共享端口）
        r_short = route_net("net_b", port_abs("wg0", "out", placement, link),
                            port_abs("wg1", "in", placement, link))
        routes = {"net_a": r_a, "net_b": r_short}
    elif case == "dangling":        # 悬空：net_b 端点指向空白（无端口归属）
        r_dgl = route_net("net_b", (500.0, 500.0), (600.0, 500.0))
        routes = {"net_a": r_a, "net_b": r_dgl}
    return link, placement, routes


def s9_lvs_verdict(case: str = "consistent", tol: float = 1.0) -> float:
    """S9 golden：LVS 判决正确性（确定性算法，可复现）。

    返回 1.0（ACCEPT）/ 0.0（REJECT）。判决路径零 LLM：
    版图网表由布线几何独立恢复 → 集合比对 → 死标量 verdict。
    """
    link, placement, routes = build_lvs_case(case)
    r = run_lvs(link, placement, routes, tol=tol)
    return 1.0 if r["verdict"] == "ACCEPT" else 0.0


def s9_report() -> Dict[str, Any]:
    """S9 全案例判决报告（smoke/WebUI 消费）。"""
    rows = []
    for case in CASES:
        link, placement, routes = build_lvs_case(case)
        r = run_lvs(link, placement, routes)
        rows.append({
            "case": case,
            "verdict": r["verdict"],
            "n_violations": r["n_violations"],
            "violation_kinds": sorted(r["violations"].keys()),
        })
    return {
        "title": "S9 · LVS 版图-原理图一致性判决锚",
        "expected": {"consistent": "ACCEPT"},
        "cases": rows,
        "all_consistent_accepted": all(
            x["verdict"] == ("ACCEPT" if x["case"] == "consistent" else "REJECT")
            for x in rows),
    }


# ---------------------------------------------------------------------------
# S10 多层 LVS 锚（v0.8.25 · 版图差距 #6：金属/通孔层叠）
# ---------------------------------------------------------------------------
MULTI_CASES = ("consistent", "cross_short", "via_short", "port_short",
               "dangling")


def build_multilayer_case(case: str = "consistent"
                          ) -> Tuple[LinkModel, Dict[str, Any], Dict[str, Any]]:
    """构造多层 LVS 案例：3 器件（M1/M2 混合）+ 跨层 via 布线（正例/反例）。

    层栈：SOI（M1 硅波导 / VIA12 / M2 金属互连）。器件：wg0/wg1 在 M1、
    wg2 在 M2；net_a = wg0.out→wg2.in（M1→M2 跨层）、net_b = wg2.out→wg1.in。
    """
    if case not in MULTI_CASES:
        raise ValueError(f"case 须为 {MULTI_CASES}，实际 {case}")
    from lda_layout.placement import port_abs
    from lda_layout.router import route_net

    link = LinkModel(name=f"s10_lvs_{case}")
    link.add_device("wg0", "Waveguide", {"length": 20.0})
    link.add_device("wg2", "Waveguide", {"length": 20.0, "layer": "M2"})
    link.add_device("wg1", "Waveguide", {"length": 20.0})
    link.connect("net_a", "wg0", "out", "wg2", "in")
    link.connect("net_b", "wg2", "out", "wg1", "in")
    # 自定义放置：wg1 下移避免 M1 段共线（S9 放置陷阱教训：同层段不可意外共线）
    placement = {"wg0": (0.0, 0.0, 0.0), "wg2": (60.0, 0.0, 0.0),
                 "wg1": (100.0, -40.0, 0.0)}
    pa0 = port_abs("wg0", "out", placement, link)     # (20, 0)  M1
    pa1 = port_abs("wg2", "in", placement, link)      # (60, 0)  M2
    pb0 = port_abs("wg2", "out", placement, link)     # (80, 0)  M2
    pb1 = port_abs("wg1", "in", placement, link)      # (100,-40) M1

    # 正例基线：net_a = M1 段 (20,0)→(20,-40) via → M2 段 → wg2.in；
    #           net_b = M2 段 (80,0)→(80,-20) via → M1 段 → wg1.in
    r_a1 = route_net("net_a", pa0, (20.0, -40.0), layer="M1")
    r_a2 = route_net("net_a", (20.0, -40.0), pa1, layer="M2")
    r_b1 = route_net("net_b", pb0, (80.0, -20.0), layer="M2")
    r_b2 = route_net("net_b", (80.0, -20.0), pb1, layer="M1")

    if case == "consistent":
        routes = {"net_a": [r_a1, r_a2], "net_b": [r_b1, r_b2]}
    elif case == "cross_short":      # 同层中点交叉：net_b M1 段水平穿过 net_a M1 垂直段
        routes = {"net_a": [r_a1, r_a2],
                  "net_b": [r_b1,
                            route_net("net_b", (80.0, -20.0), (10.0, -20.0),
                                      layer="M1"),
                            route_net("net_b", (10.0, -20.0), pb1,
                                      layer="M1")]}
    elif case == "via_short":        # net_b 端点撞 net_a via 点 (20,-40)（跨层短路）
        routes = {"net_a": [r_a1, r_a2],
                  "net_b": [route_net("net_b", pb0, (20.0, -40.0), layer="M2"),
                            route_net("net_b", (20.0, -40.0), pb1,
                                      layer="M1")]}
    elif case == "port_short":       # 两网共享 wg2.in 端口（net_b 从 wg2.in 出发）
        routes = {"net_a": [r_a1, r_a2],
                  "net_b": [route_net("net_b", pa1, (80.0, -20.0), layer="M2"),
                            r_b2]}
    elif case == "dangling":         # net_b M2 段端点悬空（空白区域）
        routes = {"net_a": [r_a1, r_a2],
                  "net_b": [route_net("net_b", (500.0, 500.0), (600.0, 500.0),
                                      layer="M2"),
                            route_net("net_b", (600.0, 500.0), pb1,
                                      layer="M1")]}
    return link, placement, routes


def s10_lvs_multilayer_verdict(case: str = "consistent", tol: float = 1.0) -> float:
    """S10 golden：多层 LVS 判决正确性（确定性，可复现）。

    一致跨层版图 → 1.0（ACCEPT）；四类失配（同层交叉/通孔短路/端口共享/
    悬空）→ 0.0（REJECT）。判决零 LLM（层感知几何 + can_cross 谓词）。
    """
    from lda_l2.layers import get_stack
    from lda_l2.lvs import run_lvs_multilayer
    link, placement, routes = build_multilayer_case(case)
    r = run_lvs_multilayer(link, placement, routes,
                           stack=get_stack("soi"), tol=tol)
    return 1.0 if r["verdict"] == "ACCEPT" else 0.0


def s10_report() -> Dict[str, Any]:
    """S10 全案例判决报告（smoke/WebUI 消费）。"""
    from lda_l2.layers import get_stack
    from lda_l2.lvs import run_lvs_multilayer
    stack = get_stack("soi")
    rows = []
    for case in MULTI_CASES:
        link, placement, routes = build_multilayer_case(case)
        r = run_lvs_multilayer(link, placement, routes, stack=stack)
        rows.append({
            "case": case,
            "verdict": r["verdict"],
            "n_violations": r["n_violations"],
            "violation_kinds": sorted(r["violations"].keys()),
        })
    return {
        "title": "S10 · 多层 LVS 签核锚（M1/VIA12/M2 层叠）",
        "expected": {"consistent": "ACCEPT"},
        "cases": rows,
        "all_consistent_accepted": all(
            x["verdict"] == ("ACCEPT" if x["case"] == "consistent" else "REJECT")
            for x in rows),
        "stack": stack.to_summary(),
    }
