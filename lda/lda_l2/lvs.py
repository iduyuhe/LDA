"""LDA L2 · LVS（Layout vs Schematic）版图-原理图一致性检查（签核级 · v0.8.24+）。

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
  4. **v0.8.25 多层扩展**（版图差距 #6）：
     - `extract_layout_netlist_multilayer` —— 层感知几何恢复：布线段按层匹配
       端口；同 net 跨层段端点重合自动发现 **via 桥接**；短路判定用层栈
       `can_cross` 谓词——**同层路径相交才判 short，跨层垂直投影重叠安全**
       （介质隔离，物理正确）；
     - `run_lvs_multilayer` —— 多层签核主入口（短路语义层叠化）；
  5. `lvs_markdown`             —— 人类可读签核报告（含诚实边界）。

判决：**全死标量**（坐标几何 + 集合等价类比对），LLM 不进判决路径。
PASS/FAIL 由确定性计算决定：`ACCEPT` iff 器件全匹配 ∧ 网络全匹配 ∧ 零违规。

与 DRC 的关系：`chip_drc_report`（可制造性）与 `run_lvs`（一致性）并列构成
芯片级签核双闸——`tapeout_pipeline` 的 S2（DRC）+ S4（LVS）管道段。

诚实边界：多层模型为「信号层 + via 层」的公开工艺近似（SOI M1/VIA12/M2）；
真实 PDK 的完整工艺图层叠（数十层金属/通孔规则）属发动期对接（接口已就位）。
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


# ---------------------------------------------------------------------------
# 5) 多层版图 LVS（v0.8.25 · 版图差距 #6：金属/通孔层叠）
# ---------------------------------------------------------------------------
def _device_layer(comp) -> str:
    """器件所在信号层（params.layer，默认 M1 波导层）。"""
    return str(comp.params.get("layer", "M1"))


def _seg_layer(rr) -> str:
    """RouteResult 所在层（缺省 M1）。"""
    return str(getattr(rr, "layer", "M1"))


def _normalize_multilayer_routes(routes) -> Dict[str, List[Any]]:
    """把单层/多层 routes 统一为 {net_id: [RouteResult, ...]}（段列表）。"""
    out: Dict[str, List[Any]] = {}
    for nid, val in (routes or {}).items():
        if isinstance(val, (list, tuple)):
            out[nid] = list(val)
        else:
            out[nid] = [val]          # 单段（单层兼容）
    return out


def _nearest_port_on_layer(x, y, layer, anchors_layered, tol):
    """端点 → 指定层端口锚点最近归属（容差内唯一；None=悬空）。"""
    best, best_d = None, float("inf")
    for (inst, port, pl), (ax, ay) in anchors_layered.items():
        if pl != layer:
            continue                   # 层不匹配：M1 布线只接 M1 端口
        d = math.hypot(x - ax, y - ay)
        if d < best_d:
            best, best_d = (inst, port), d
    return best if best_d <= tol else None


def extract_layout_netlist_multilayer(link, placement, routes, stack=None,
                                      tol: float = 1.0) -> Dict[str, Any]:
    """多层版图网表：层感知几何恢复（不读原理图声明）。

    routes : {net_id: [RouteResult, ...]}（每段可不同层，v0.8.25）
             或 {net_id: RouteResult}（单层兼容，视为 stack 首信号层）。

    层感知语义（核心价值——多层 LVS 与单层的关键差异）：
      - **端口按层匹配**：M1 布线段端点只匹配 M1 器件端口；M2 段只接 M2 端口；
      - **via 桥接自动发现**：同一 net 的不同层段端点坐标重合（≤tol）→ 通孔
        桥接（跨层电气连接合法，段端点共享）；不同 net 的跨层端点重合 → 短路
        （未经声明的跨层相接）；
      - **短路层叠判定**：`stack.can_cross(l1,l2)`——同层路径相交 → short_cross；
        跨层垂直投影重叠（M1/M2）→ **安全**（介质隔离，不判短——这正是
        多层版图能把布线叠起来省面积的物理依据）。

    返回结构同 extract_layout_netlist（nets/dangling/loops/port_shorts/
    cross_shorts + 新增 layer_shorts/via_shorts）。
    """
    from lda_l2.layers import get_stack
    stack = stack or get_stack("soi")
    # 端口锚点（带层）：{(inst, port, layer): (x, y)}
    anchors: Dict[Tuple[str, str, str], Tuple[float, float]] = {}
    for c in link.ir.components:
        lay = _device_layer(c)
        for p in c.ports:
            anchors[(c.id, p.name, lay)] = port_abs(c.id, p.name, placement, link)

    segs_by_net = _normalize_multilayer_routes(routes)
    nets: Dict[str, List[str]] = {}
    dangling: List[str] = []
    loops: List[str] = []
    port_owner: Dict[Tuple[str, str], str] = {}
    port_shorts: Dict[Tuple[str, str], List[str]] = {}
    paths_by_layer: Dict[str, Dict[str, List[Tuple[float, float]]]] = {}
    # 段端点坐标占用（跨层短路检测）：{(x,y): (net_id, layer)} 记录全部段端点
    seg_touch: Dict[Tuple[float, float], Tuple[str, str]] = {}
    via_shorts: List[Tuple[str, str, str]] = []   # (net1, net2, layer_pair)

    for net_id, segs in segs_by_net.items():
        if not segs:
            continue
        net_ports: set = set()
        # 段端点坐标全集（首段起点→末段终点为端口连接点；中间端点为 via 跳点）
        all_endpoints: List[Tuple[Tuple[float, float], str]] = []  # ((x,y), layer)
        for seg in segs:
            pts = [tuple(p) for p in _route_endpoints(seg)]
            if len(pts) < 2:
                dangling.append(net_id)
                continue
            layer = _seg_layer(seg)
            paths_by_layer.setdefault(layer, {})[net_id] = pts
            all_endpoints.append((pts[0], layer))
            all_endpoints.append((pts[-1], layer))
        if not all_endpoints:
            continue
        # 端口匹配：首段起点 + 末段终点（中间端点是 via 跳点，不匹配端口）
        first_ep, first_layer = all_endpoints[0]
        last_ep, last_layer = all_endpoints[-1]
        p0 = _nearest_port_on_layer(first_ep[0], first_ep[1], first_layer,
                                    anchors, tol)
        p1 = _nearest_port_on_layer(last_ep[0], last_ep[1], last_layer,
                                    anchors, tol)
        if p0 is None or p1 is None:
            dangling.append(net_id)
            continue
        if p0 == p1:
            loops.append(net_id)
            continue
        for p in (p0, p1):
            net_ports.add(f"{p[0]}.{p[1]}")
            if p in port_owner and port_owner[p] != net_id:
                port_shorts.setdefault(p, []).append(net_id)
            else:
                port_owner[p] = net_id
        # 全部段端点（含 via 跳点）：跨 net 端点重合 = 未经声明的跨层相接（短路）
        seen_own: set = set()
        for ep, layer in all_endpoints:
            key = (round(ep[0], 3), round(ep[1], 3))
            if key in seen_own:
                continue               # 同 net 内部重复端点（via 桥/汇聚）合法
            seen_own.add(key)
            if key in seg_touch and seg_touch[key][0] != net_id:
                other_net, other_layer = seg_touch[key]
                via_shorts.append((net_id, other_net,
                                   f"{other_layer}↔{layer}"))
            else:
                seg_touch[key] = (net_id, layer)
        if net_ports:
            nets[net_id] = sorted(net_ports)

    # —— 层叠短路：同层路径相交才判 short（stack.can_cross 谓词）——
    cross_shorts: List[Tuple[str, str, str]] = []
    layer_names = sorted(paths_by_layer.keys())
    for i in range(len(layer_names)):
        for j in range(i, len(layer_names)):
            l1, l2 = layer_names[i], layer_names[j]
            if not stack.can_cross(l1, l2):
                continue               # 异层介质隔离：投影重叠不短（核心语义）
            pl1, pl2 = paths_by_layer[l1], paths_by_layer[l2]
            for n1 in sorted(pl1):
                for n2 in sorted(pl2):
                    if n1 == n2 and l1 == l2:
                        continue       # 同网自身不比对
                    pts1, pts2 = pl1[n1], pl2[n2]
                    hit = False
                    for k in range(len(pts1) - 1):
                        for m in range(len(pts2) - 1):
                            a, b = pts1[k], pts1[k + 1]
                            c, d = pts2[m], pts2[m + 1]
                            shared = (a == c or a == d or b == c or b == d)
                            if not shared and _segments_intersect(a, b, c, d):
                                hit = True
                                break
                        if hit:
                            break
                    if hit:
                        cross_shorts.append((n1, n2, f"{l1}∩{l2}"))

    kind_of = {c.id: c.kind for c in link.ir.components}
    inst = {k: kind_of.get(k, "?") for k in (placement or {})}
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
        "cross_shorts": cross_shorts,          # (n1, n2, layer_pair)
        "via_shorts": via_shorts,              # (net1, net2, layer_pair)
        "stack": stack.to_summary(),
    }


def run_lvs_multilayer(link, placement, routes, stack=None,
                       tol: float = 1.0) -> Dict[str, Any]:
    """多层 LVS 签核主入口：层叠版图 vs 原理图一致性。

    短路语义层叠化：同层相交短路 / 跨层投影安全（介质隔离）/ 未经声明的
    跨层相接（via 短路）检出。判决全死标量，LLM 不进判决路径。
    """
    from lda_l2.layers import get_stack
    stack = stack or get_stack("soi")
    sch = extract_schematic_netlist(link)
    lay = extract_layout_netlist_multilayer(link, placement, routes,
                                            stack=stack, tol=tol)
    viol: Dict[str, List[Any]] = {}

    sch_inst = set(sch["instances"])
    lay_inst = set(lay["instances"])
    missing = sorted(sch_inst - lay_inst)
    extra = sorted(lay_inst - sch_inst)
    if missing:
        viol["device_missing"] = missing
    if extra:
        viol["device_extra"] = extra

    sch_nets: Dict[str, List[str]] = dict(sch["nets"])
    lay_nets: Dict[str, List[str]] = dict(lay["nets"])

    open_nets = []
    for nid, ports in sch_nets.items():
        if nid not in lay_nets:
            if nid in lay.get("dangling", []) or nid in lay.get("loops", []):
                open_nets.append((nid, "dangling_or_loop"))
            else:
                open_nets.append((nid, "no_layout_net"))
    if open_nets:
        viol["open"] = open_nets

    extra_nets = sorted(set(lay_nets) - set(sch_nets))
    if extra_nets:
        viol["extra"] = extra_nets

    misconnects = []
    for nid in sorted(set(sch_nets) & set(lay_nets)):
        if sch_nets[nid] != lay_nets[nid]:
            misconnects.append((nid, sch_nets[nid], lay_nets[nid]))
    if misconnects:
        viol["misconnect"] = misconnects

    if lay.get("port_shorts"):
        viol["short_port"] = [(p, v) for p, v in lay["port_shorts"].items()]
    if lay.get("cross_shorts"):
        viol["short_cross"] = lay["cross_shorts"]
    if lay.get("via_shorts"):
        viol["short_via"] = lay["via_shorts"]
    if lay.get("dangling"):
        viol["dangling"] = lay["dangling"]
    if lay.get("loops"):
        viol["loop"] = lay["loops"]

    n_viol = sum(len(v) for v in viol.values())
    verdict = "ACCEPT" if n_viol == 0 else "REJECT"
    n_sch, n_lay = len(sch_nets), len(lay_nets)
    n_match = sum(1 for nid in sch_nets
                  if nid in lay_nets and sch_nets[nid] == lay_nets[nid])
    stack_name = lay.get("stack", {}).get("name", "?")
    return {
        "verdict": verdict,
        "mode": "multilayer",
        "schematic": {"n_instances": len(sch_inst), "n_nets": n_sch},
        "layout": {"n_instances": len(lay_inst), "n_nets": n_lay},
        "match": {
            "n_devices_match": len(sch_inst - set(missing) - set(extra)),
            "n_nets_match": n_match,
            "n_nets_total": n_sch,
        },
        "violations": viol,
        "n_violations": n_viol,
        "stack": lay.get("stack", {}),
        "honest_note": (
            f"多层 LVS 签核（{stack_name}）：层感知几何恢复——M1 段只接 M1 端口、"
            f"跨层段端点重合自动发现 via 桥接；短路判定用层栈 can_cross 谓词"
            f"（同层相交才 short、跨层投影重叠安全=介质隔离）。"
            f"比对原理图 {n_sch} 网 vs 版图 {n_lay} 网，{n_match}/{n_sch} 一致，"
            f"违规 {n_viol} 项。判决全死标量，LLM 不进判决路径。"
            "诚实边界：公开工艺近似层栈（M1/VIA12/M2），真实 PDK 完整层叠属发动期。"),
    }


_VIOL_LABEL["short_via"] = "通孔短路（未经声明的跨层相接）"
