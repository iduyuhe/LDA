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
