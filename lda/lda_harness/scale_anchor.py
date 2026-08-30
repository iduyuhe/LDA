"""LDA S11 锚 · 规模扩展锚（v0.8.26 · 版图差距 #7 收官；v0.8.45 默认 128k）。

S11 是**规模锚**：验证 LDA 全链路（构建→放置→布线→LVS 签核）在**128k 器件级
（10万+）**设计下的正确性与可扩展性——确定性、可复现、死标量判决（LLM 不进路径）。

v0.8.45 关键治理：LVS 短路检测在 v0.8.39 网格剪枝后仍为 O(n²)（按路径 bbox 分桶，
长链跳线退化全对）。改为**按线段分桶**（`_collect_cross_shorts`）后，短路候选对枚举
降为 O(n)，128k cProfile 热点榜前 12 名已无 lvs.py 函数（单函数 <10.7ms）。判决语义
零变化（由 verify_lvs_cross_equiv.py 字节级等价铁证：46 组 0 FAIL）。
全链 scaling：4k→256k 翻倍斜率 2.26–2.85×（近线性），256k 全链实测 14.5s。

规模案例设计（链式 + ⑥多层协同——收官项与多层项联动）：
  - **n 器件链式链路**：wg_i.out → wg_{i+1}.in（n-1 条内部 net）；
  - **2D 网格放置**（place_2d，尺寸自适应）；
  - **跨行跳线走 M2 层**：行内 net 用 M1 直连；行尾→下一行首的跳线用
    M1 短段 + **M2 水平段**（via 桥接，每行 via_y 递增错开）——避免 M1 层
    横穿同行段（S10 教训：同层段不可意外共线），同时验证「多层版图可叠
    布线」在规模场景的价值（跨层投影重叠安全 = 跳线可横穿芯片）。

S11 golden（s11_large_scale_verdict）：
  - case='consistent'  ：4k 全链路 ACCEPT → 1.0；
  - case='disconnect'  ：破坏一条 net（删布线）→ REJECT → 0.0；
  - case='misroute'    ：互换两条 net 布线 → REJECT → 0.0。

性能预算（smoke 断言，不进 golden——正确性由 golden 判、性能由预算断）：
  128k 全链路（构建+放置+布线+LVS）≤ 30s（LVS O(n²) 治理后实测 ~5s，256k ~14.5s）。
"""
from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA = os.path.dirname(_HERE)
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

from lda_chain.link_model import LinkModel
from lda_layout.placement import port_abs
from lda_layout.router import route_net
from lda_l2.lvs import run_lvs_multilayer

SCALE_CASES = ("consistent", "disconnect", "misroute")

# v0.8.45：规模锚默认 4k→128k（10万+ 纵深，LVS O(n²) 治理后规模能力实至名归；
# 128k 全链实测 ~5s，预算 30s 余量 ~6×；256k 纵深守护 ~14.5s）
DEFAULT_N_DEVICES = 128000
DEFAULT_COLS = 32
VIA_SHORT_UM = 5.0          # 跳线 M1 段1 短垂距（行尾端口→via，不穿下行）
BUDGET_SEC = 30.0           # 128k 器件全链路性能预算（构建+放置+布线+LVS）


def build_chain_case(n_devices: int = DEFAULT_N_DEVICES,
                     cols: int = DEFAULT_COLS,
                     case: str = "consistent",
                     via_short: float = VIA_SHORT_UM
                     ) -> Tuple[LinkModel, Dict[str, Any], Dict[str, Any]]:
    """构造千器件链式链路 + 2D 放置 + 多层布线（正例/反例）。

    行内 net（i%cols != cols-1）：M1 直连；
    跨行 net（i%cols == cols-1）跳线（行尾→下行首，走 M2 层）：
      - M1 段1：wg_i.out → (x_end, y_row − via_short)（短垂，不穿下方行尾）
      - M2 段 ：(x_end, y_row − via_short) → (x_left, y_row − via_short)
                （水平横穿；y 每行不同 → M2 段互不相交；与 M1 跨层安全）
      - M1 段2 ：(x_left, y_row − via_short) → wg_{i+1}.in（x_left 每行
                (row%8)*2 偏移 → 垂直段不同列；水平段 y 行内 [0,x_left<20]
                不与行内 M1 段 [20,x_end] 重叠）

    教训（S10/S11 两轮踩坑）：跨行跳线 M1 段若在行尾列垂落或 x=0 列垂落，
    必然与下方/相邻行同层段共线（真实短路）——跳线几何必须把「垂落段」错
    列、把「横穿段」错层错行。
    """
    if case not in SCALE_CASES:
        raise ValueError(f"case 须为 {SCALE_CASES}，实际 {case}")
    if n_devices < 2:
        raise ValueError("n_devices ≥ 2")

    link = LinkModel(name=f"s11_chain_{n_devices}")
    for i in range(n_devices):
        link.add_device(f"wg{i}", "Waveguide", {"length": 20.0})
    for i in range(n_devices - 1):
        link.connect(f"net_{i}", f"wg{i}", "out", f"wg{i + 1}", "in")
    # 2D 放置：尺寸自适应 pitch + **奇偶行 x 偏移交错**（行首错列——
    # 否则所有行首器件在 x=0，跳线 M1 段2 垂落列相同 → 相邻行 x=0 段共线）
    from lda_layout.placement import device_bbox
    bboxes = {c.id: device_bbox(c.kind, dict(c.params))
              for c in link.ir.components}
    pitch_x = 2.0 * max(hw for hw, _ in bboxes.values()) + 8.0
    pitch_y = 2.0 * max(hh for _, hh in bboxes.values()) + 8.0
    placement: Dict[str, Tuple[float, float, float]] = {}
    for i, c in enumerate(link.ir.components):
        row, col = divmod(i, cols)
        xoff = (row % 2) * 10.0              # 奇数行右移 10µm（跳线垂落列交替）
        placement[c.id] = (xoff + col * pitch_x, row * pitch_y, 0.0)

    routes: Dict[str, Any] = {}
    for i in range(n_devices - 1):
        pa = port_abs(f"wg{i}", "out", placement, link)
        pb = port_abs(f"wg{i + 1}", "in", placement, link)
        row = i // cols
        if i % cols != cols - 1:
            # 行内：M1 直连
            routes[f"net_{i}"] = [route_net(f"net_{i}", pa, pb, layer="M1")]
        else:
            # 跨行跳线：M1 短垂 → M2 横穿到目标列 → M1 纯垂直短接
            # （M1 段2 无水平段——L 形水平横穿会与相邻跳线垂落段相交；
            #  垂落列 = 目标行首 x（奇偶交替 0/10），相邻同列段 y 区间
            #  [via_y, y_next] 长 ~14 < 行距 18 → 不重叠）
            via_y = pa[1] - via_short
            r1 = route_net(f"net_{i}", pa, (pa[0], via_y), layer="M1")
            r2 = route_net(f"net_{i}", (pa[0], via_y), (pb[0], via_y),
                           layer="M2")
            r3 = route_net(f"net_{i}", (pb[0], via_y), pb, layer="M1")
            routes[f"net_{i}"] = [r1, r2, r3]

    # 反例：局部破坏
    if case == "disconnect":
        del routes["net_500"]                       # 断路：删一条布线
    elif case == "misroute":
        r_500 = routes.pop("net_500")               # 错连：互换两条布线
        r_501 = routes.pop("net_501")
        routes["net_500"], routes["net_501"] = r_501, r_500
    return link, placement, routes


def run_scale_pipeline(n_devices: int = DEFAULT_N_DEVICES,
                       cols: int = DEFAULT_COLS,
                       case: str = "consistent") -> Dict[str, Any]:
    """千器件全链路（构建+放置+布线+LVS）→ 判决 + 性能。"""
    from lda_l2.layers import get_stack
    t0 = time.perf_counter()
    link, placement, routes = build_chain_case(n_devices, cols=cols, case=case)
    t1 = time.perf_counter()
    report = run_lvs_multilayer(link, placement, routes,
                                stack=get_stack("soi"))
    t2 = time.perf_counter()
    report["n_devices"] = n_devices
    report["n_nets"] = len(link.ir.nets)
    report["time_build_s"] = round(t1 - t0, 3)
    report["time_lvs_s"] = round(t2 - t1, 3)
    report["time_total_s"] = round(t2 - t0, 3)
    report["within_budget"] = (t2 - t0) <= BUDGET_SEC
    return report


def s11_large_scale_verdict(case: str = "consistent",
                            n_devices: int = DEFAULT_N_DEVICES) -> float:
    """S11 golden：千器件规模锚判决（确定性，可复现）。

    全链路（构建+放置+多层布线+LVS 签核）成功且 LVS ACCEPT → 1.0；
    局部破坏（断路/错连）→ 0.0。判决零 LLM（层感知几何 + can_cross）。
    """
    report = run_scale_pipeline(n_devices=n_devices, case=case)
    return 1.0 if report["verdict"] == "ACCEPT" else 0.0


def s11_report(n_devices: int = DEFAULT_N_DEVICES) -> Dict[str, Any]:
    """S11 全案例判决 + 性能报告（smoke/WebUI 消费）。"""
    rows = []
    for case in SCALE_CASES:
        r = run_scale_pipeline(n_devices=n_devices, case=case)
        rows.append({
            "case": case,
            "verdict": r["verdict"],
            "n_violations": r["n_violations"],
            "violation_kinds": sorted(r["violations"].keys()),
            "time_total_s": r["time_total_s"],
        })
    return {
        "title": f"S11 · 千器件规模扩展锚（n={n_devices} · 链式 + 多层跨行跳线）",
        "expected": {"consistent": "ACCEPT"},
        "cases": rows,
        "all_consistent_accepted": all(
            x["verdict"] == ("ACCEPT" if x["case"] == "consistent" else "REJECT")
            for x in rows),
        "budget_sec": BUDGET_SEC,
        "within_budget": all(x["time_total_s"] <= BUDGET_SEC for x in rows),
    }
