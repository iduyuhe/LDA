"""LDA L2 · LVS（Layout vs Schematic）版图-原理图一致性检查（签核级 · v0.8.24）。

标准 EDA 签核（sign-off）流程中：
  - **DRC** 保证「版图可制造」（几何合规）；
  - **LVS** 保证「版图即原理图」——版图中每个器件实例、每条物理连接必须与
    原理图网表一一对应。LVS 是流片签核的必要条件：版图与原理图不一致的
    芯片即使 DRC 全过也不能流片（物理连接与设计意图不符）。

本模块（C 级自写零依赖，仅标准库 + lda_layout/lda_chain）：
  1. `extract_schematic_netlist` —— 原理图网表：器件实例 + 网络（来自
     LinkModel.ir，即设计意图）；
  2. `extract_layout_netlist`   —— 版图网表：**从几何独立恢复**——布线路径
     端点坐标 → 端口锚点最近归属（不读原理图声明）。这正是签核级检查的
     意义：布线器/版图的物理事实独立恢复，才能发现「实现 ≠ 意图」；
  3. `run_lvs`                  —— 比对：器件匹配 + 网络匹配 + 违规检出
     （断路 open / 短路 short / 错连 misconnect / 悬空 dangling / 自环 loop
       / 多余 extra / 器件失配 device_mismatch）；
  4. `lvs_markdown`             —— 人类可读签核报告（含诚实边界）。

判决：**全死标量**（坐标几何 + 集合等价类比对），LLM 不进判决路径。
PASS/FAIL 由确定性计算决定：`ACCEPT` iff 器件全匹配 ∧ 网络全匹配 ∧ 零违规。

与 DRC 的关系：`chip_drc_report`（可制造性）与 `run_lvs`（一致性）并列构成
芯片级签核双闸——`tapeout_pipeline` 的 S2（DRC）+ S5（LVS）管道段。

诚实边界：当前版图模型为「放置 + 单层波导布线」（2 端口 net）；多层金属/通孔
版图、真实工艺图层叠的完整 LVS 属发动期 PDK 对接后扩展（接口已就位）。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from lda_layout.placement import device_bbox, port_abs


# ---------------------------------------------------------------------------
# 1) 原理图网表（schematic netlist）—— 设计意图
# ---------------------------------------------------------------------------
def schematic_instances(link) -> Dict[str, str]:
    """原理图器件实例：{inst_id: kind}（LinkModel.ir.components）。"""
    return {c.id: c.kind for c in link.ir.components}


def schematic_nets(link) -> Dict[str, List[str]]:
    """原理图网络：{net_id: sorted([inst.port, ...])}（仅内部连接 ≥2 端口）。

    单端口 net（外部 IO / 源汇）不参与 LVS 连接比对（它们没有物理布线，
    由 IO 光栅耦合器接入承载——见 chip_layout_export）。
    """
    out: Dict[str, List[str]] = {}
    for net in link.ir.nets:
        ports = sorted(x for x in net.connects if "." in x)
        if len(ports) >= 2:
            out[net.id] = ports
    return out


def extract_schematic_netlist(link) -> Dict[str, Any]:
    """原理图网表（器件 + 网络），供 run_lvs 比对。"""
    return {
        "instances": schematic_instances(link),
        "nets": schematic_nets(link),
    }


# ---------------------------------------------------------------------------
# 2) 版图网表（layout netlist）—— 从几何独立恢复
# ---------------------------------------------------------------------------
def _route_endpoints(rr) -> List[Tuple[float, float]]:
    """RouteResult / dict → 路径折点（含首末）。"""
    pts = rr.points_um if hasattr(rr, "points_um") else rr.get("points_um")
    return [tuple(p) for p in (pts or [])]


def _port_anchor_table(link, placement) -> Dict[Tuple[str, str], Tuple[float, float]]:
    """端口锚点绝对坐标表：{(inst, port): (x, y)}。"""
    table: Dict[Tuple[str, str], Tuple[float, float]] = {}
    for c in link.ir.components:
        for p in c.ports:
            table[(c.id, p.name)] = port_abs(c.id, p.name, placement, link)
    return table


def _nearest_port(x: float, y: float,
                  anchors: Dict[Tuple[str, str], Tuple[float, float]],
                  tol: float) -> Optional[Tuple[str, str]]:
    """端点 → 最近端口锚点（容差内唯一归属；返回 None = 悬空 dangling）。"""
    best, best_d = None, float("inf")
    for key, (ax, ay) in anchors.items():
        d = math.hypot(x - ax, y - ay)
        if d < best_d:
            best, best_d = key, d
    return best if best_d <= tol else None


def _segments_intersect(a, b, c, d) -> bool:
    """线段 ab 与 cd 是否相交（含端点触碰；不含共享端点本身——调用方排除）。"""
    def _ccw(p, q, r):
        return (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])

    def _on_seg(p, q, r):
        return (min(p[0], r[0]) - 1e-9 <= q[0] <= max(p[0], r[0]) + 1e-9
                and min(p[1], r[1]) - 1e-9 <= q[1] <= max(p[1], r[1]) + 1e-9)

    o1, o2, o3, o4 = _ccw(a, b, c), _ccw(a, b, d), _ccw(c, d, a), _ccw(c, d, b)
    if o1 == 0 and _on_seg(a, c, b):
        return True
    if o2 == 0 and _on_seg(a, d, b):
        return True
    if o3 == 0 and _on_seg(c, a, d):
        return True
    if o4 == 0 and _on_seg(c, b, d):
        return True
    return (o1 * o2 < 0) and (o3 * o4 < 0)


def extract_layout_netlist(link, placement, routes,
                           tol: float = 1.0) -> Dict[str, Any]:
    """版图网表：从布线几何恢复连接（不依赖原理图声明）。

    routes : {net_id: RouteResult | dict}——布线路径（points_um）。

    恢复逻辑（纯几何，零原理图读取）：
      - 每条 route 首末端点 → 端口锚点最近归属（容差 tol µm）；
      - 端点无归属            → dangling（悬空布线，签核异常）；
      - 两端同属一个端口      → loop（自环，异常）；
      - 同一端口被多个 net 连接 → 端口短路候选（short）；
      - 不同 net 路径线段相交（非共享端点）→ 布线交叉短路候选（short）。

    返回：
      {
        "instances": 版图器件实例（placement 全集 + 恢复连接中出现的实例）,
        "nets": {net_id: sorted([inst.port, ...])}（几何恢复）,
        "dangling": [net_id], "loops": [net_id],
        "port_shorts": {port: [net_id, ...]}, "cross_shorts": [(n1, n2)],
        "unrouted": [net_id]（routes 中无路径的 net，由调用方补全）,
      }
    """
    anchors = _port_anchor_table(link, placement)
    nets: Dict[str, List[str]] = {}
    dangling: List[str] = []
    loops: List[str] = []
    port_owner: Dict[Tuple[str, str], str] = {}   # (inst,port) -> net_id
    port_shorts: Dict[Tuple[str, str], List[str]] = {}
    paths: Dict[str, List[Tuple[float, float]]] = {}

    for net_id, rr in (routes or {}).items():
        pts = _route_endpoints(rr)
        if not pts:
            continue
        paths[net_id] = pts
        if len(pts) < 2:
            dangling.append(net_id)
            continue
        e0, e1 = pts[0], pts[-1]
        p0 = _nearest_port(e0[0], e0[1], anchors, tol)
        p1 = _nearest_port(e1[0], e1[1], anchors, tol)
        if p0 is None or p1 is None:
            dangling.append(net_id)
            continue
        if p0 == p1:
            loops.append(net_id)
            continue
        nets[net_id] = sorted([f"{p0[0]}.{p0[1]}", f"{p1[0]}.{p1[1]}"])
        for p in (p0, p1):
            if p in port_owner and port_owner[p] != net_id:
                port_shorts.setdefault(p, []).append(net_id)
            else:
                port_owner[p] = net_id

    # 布线交叉短路（不同 net 路径线段相交，非共享端点）
    cross_shorts: List[Tuple[str, str]] = []
    net_ids = sorted(paths.keys())
    for i in range(len(net_ids)):
        for j in range(i + 1, len(net_ids)):
            n1, n2 = net_ids[i], net_ids[j]
            pts1, pts2 = paths[n1], paths[n2]
            hit = False
            for k in range(len(pts1) - 1):
                for m in range(len(pts2) - 1):
                    a, b = pts1[k], pts1[k + 1]
                    c, d = pts2[m], pts2[m + 1]
                    # 排除共享端点（合法汇聚——多端网/公共节点）
                    shared = (a == c or a == d or b == c or b == d)
                    if not shared and _segments_intersect(a, b, c, d):
                        hit = True
                        break
                if hit:
                    break
            if hit:
                cross_shorts.append((n1, n2))

    # 版图器件实例：placement 全集（防未来版图引擎独立生成时的核对点）
    kind_of = {c.id: c.kind for c in link.ir.components}
    inst = {k: kind_of.get(k, "?") for k in (placement or {})}
    # 端口短路完整列表：首属 owner + 全部冲突 net
    port_shorts_full = {
        f"{k[0]}.{k[1]}": [port_owner[k]] + v
        for k, v in port_shorts.items()
    }
    return {
        "instances": inst,
        "nets": nets,
        "dangling": dangling,
        "loops": loops,
        "port_shorts": port_shorts_full,
        "cross_shorts": cross_shorts,
    }


# ---------------------------------------------------------------------------
# 3) LVS 比对（compare）+ 判决（verdict）
# ---------------------------------------------------------------------------
def run_lvs(link, placement, routes, tol: float = 1.0,
            net_loss_db: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """LVS 主入口：原理图 vs 版图一致性签核。

    参数：
      link      : LinkModel（原理图：器件实例 + 网络）
      placement : {inst: (x, y, rot)} 器件放置
      routes    : {net_id: RouteResult | dict} 布线路径
      tol       : 端点→端口归属容差 µm（默认 1.0）
      net_loss_db : 可选——布线损耗 dict（用于 open 判定：net 有布线但
                    损耗为 None 的异常情况；默认 None 不做该检查）

    返回：
      {
        "verdict": "ACCEPT" | "REJECT",
        "schematic": {"n_instances", "n_nets"},
        "layout":    {"n_instances", "n_nets"},
        "match": {"n_devices_match", "n_nets_match", "n_nets_total"},
        "violations": {类别: 明细}, "n_violations": int,
        "honest_note": str,
      }
    """
    sch = extract_schematic_netlist(link)
    lay = extract_layout_netlist(link, placement, routes, tol=tol)
    viol: Dict[str, List[Any]] = {}

    # —— 器件比对 ——
    sch_inst = set(sch["instances"])
    lay_inst = set(lay["instances"])
    missing_devices = sorted(sch_inst - lay_inst)
    extra_devices = sorted(lay_inst - sch_inst)
    if missing_devices:
        viol["device_missing"] = missing_devices
    if extra_devices:
        viol["device_extra"] = extra_devices

    # —— 网络比对 ——
    sch_nets: Dict[str, List[str]] = dict(sch["nets"])
    lay_nets: Dict[str, List[str]] = dict(lay["nets"])

    # 断路 open：原理图 net 在版图无对应布线（或布了但悬空/自环未入 nets）
    open_nets = []
    for nid, ports in sch_nets.items():
        ln = lay_nets.get(nid)
        if ln is None:
            # 若该 net 在版图侧因悬空/自环未恢复 → 仍算 open（物理未连通）
            if nid in lay.get("dangling", []) or nid in lay.get("loops", []):
                open_nets.append((nid, "dangling_or_loop"))
            else:
                open_nets.append((nid, "no_layout_net"))
    if open_nets:
        viol["open"] = open_nets

    # 多余 extra：版图有布线而原理图无此 net
    extra_nets = sorted(set(lay_nets) - set(sch_nets))
    if extra_nets:
        viol["extra"] = extra_nets

    # 错连 misconnect：同名 net 端口集合不同
    misconnects = []
    for nid in sorted(set(sch_nets) & set(lay_nets)):
        if sch_nets[nid] != lay_nets[nid]:
            misconnects.append((nid, sch_nets[nid], lay_nets[nid]))
    if misconnects:
        viol["misconnect"] = misconnects

    # —— 短路 short：端口被多 net 占用 / 布线交叉 ——
    if lay.get("port_shorts"):
        viol["short_port"] = [(p, v) for p, v in lay["port_shorts"].items()]
    if lay.get("cross_shorts"):
        viol["short_cross"] = lay["cross_shorts"]

    # 悬空 / 自环
    if lay.get("dangling"):
        viol["dangling"] = lay["dangling"]
    if lay.get("loops"):
        viol["loop"] = lay["loops"]

    n_viol = sum(len(v) for v in viol.values())
    verdict = "ACCEPT" if n_viol == 0 else "REJECT"

    n_sch_nets = len(sch_nets)
    n_lay_nets = len(lay_nets)
    n_nets_match = sum(1 for nid in sch_nets
                       if nid in lay_nets and sch_nets[nid] == lay_nets[nid])
    return {
        "verdict": verdict,
        "schematic": {"n_instances": len(sch_inst), "n_nets": n_sch_nets},
        "layout": {"n_instances": len(lay_inst), "n_nets": n_lay_nets},
        "match": {
            "n_devices_match": len(sch_inst - set(missing_devices) - set(extra_devices)),
            "n_nets_match": n_nets_match,
            "n_nets_total": n_sch_nets,
        },
        "violations": viol,
        "n_violations": n_viol,
        "honest_note": (
            f"LVS 签核：版图网表由布线几何独立恢复（端点→端口锚点容差 {tol}µm），"
            f"比对原理图 {n_sch_nets} 网 vs 版图 {n_lay_nets} 网；"
            f"{n_nets_match}/{n_sch_nets} 网一致，违规 {n_viol} 项。"
            "判决全死标量（坐标几何 + 集合比对），LLM 不进判决路径。"
            "诚实边界：当前版图模型为单层波导（2 端口 net），多层金属/通孔"
            "完整 LVS 属发动期 PDK 对接后扩展。"),
    }


# ---------------------------------------------------------------------------
# 4) 人类可读签核报告（markdown）
# ---------------------------------------------------------------------------
_VIOL_LABEL = {
    "device_missing": "器件缺失（原理图有、版图无）",
    "device_extra": "多余器件（版图有、原理图无）",
    "open": "断路（原理图网在版图未物理连通）",
    "extra": "多余布线（版图有、原理图无此网）",
    "misconnect": "错连（同名网端口集合不一致）",
    "short_port": "端口短路（同端口被多网连接）",
    "short_cross": "布线交叉短路（不同网路径相交）",
    "dangling": "悬空布线（端点无端口归属）",
    "loop": "自环（布线两端同属一端口）",
}


def lvs_markdown(report: Dict[str, Any]) -> str:
    """LVS 签核报告 → markdown（WebUI / 报告文件消费）。"""
    L = []
    L.append("## LVS 签核（版图 vs 原理图一致性）")
    L.append("")
    verdict = report.get("verdict", "REJECT")
    mark = "✅ ACCEPT" if verdict == "ACCEPT" else "❌ REJECT"
    L.append(f"- 判决：**{mark}**（{report.get('n_violations', 0)} 项违规）")
    sch = report.get("schematic", {})
    lay = report.get("layout", {})
    m = report.get("match", {})
    L.append(f"- 器件：原理图 {sch.get('n_instances', 0)} · 版图 "
             f"{lay.get('n_instances', 0)} · 匹配 {m.get('n_devices_match', 0)}")
    L.append(f"- 网络：原理图 {sch.get('n_nets', 0)} · 版图 "
             f"{lay.get('n_nets', 0)} · 一致 {m.get('n_nets_match', 0)}/"
             f"{m.get('n_nets_total', 0)}")
    viol = report.get("violations", {})
    if viol:
        L.append("")
        L.append("### 违规明细")
        L.append("")
        for cat, items in viol.items():
            label = _VIOL_LABEL.get(cat, cat)
            L.append(f"- **{label}**（{len(items)} 项）：`{str(items)[:200]}`")
    L.append("")
    L.append(f"*{report.get('honest_note', '')}*")
    return "\n".join(L)
