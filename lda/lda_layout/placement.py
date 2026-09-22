"""LDA L1/L2 · 器件放置（placement）+ 端口锚点 + 包围盒。


P1-M2 配合 router 使用：把 LinkModel 的器件实例映射到芯片坐标，
给出端口绝对坐标（供 router 布线）与器件包围盒（供 router 避障）。

端口锚点（WDM add-drop 约定，与 gds_export.geometry_desc 的 RingAddDrop
同源）：RingResonator 的 in/out 在 through bus（下，y=-off）、drop 在
drop bus（上，y=+off）；off = R + wg_width/2 + gap，half = R*1.5。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # 仅类型标注用，避免 lda_chain ↔ lda_layout 循环导入
    from lda_chain.link_model import LinkModel

# v0.8.39：port_abs 组件查找缓存（placement → comp_by_id 索引）。
#   每次调用线性扫 link.ir.components 是 O(n·m) 存量低效（scale_anchor 构建
#   与 LVS 锚点表均循环调用）；缓存 {id(placement), id(link)} → {inst: comp}
#   后查表 O(1)。缓存失效条件：新 placement/link 对象（构造器每次新建，
#   规模案例/不同用例天然新对象；原地增删器件走 _port_abs_cache_clear）。
_port_abs_comp_cache: Dict[Tuple[int, int], Dict[str, "object"]] = {}


def _port_abs_comp_index(placement: dict, link) -> Dict[str, "object"]:
    """按 (placement, link) 对象身份缓存 {inst: comp} 索引。"""
    key = (id(placement), id(link))
    idx = _port_abs_comp_cache.get(key)
    if idx is None:
        idx = {c.id: c for c in link.ir.components}
        _port_abs_comp_cache[key] = idx
    return idx


def _port_abs_cache_clear() -> None:
    """清空 port_abs 组件索引缓存（对象原地增删器件后调用）。"""
    _port_abs_comp_cache.clear()


def port_anchor(kind: str, port: str, params: dict) -> Tuple[float, float]:
    """器件局部坐标下端口锚点 (dx,dy) µm（器件原点 0,0）。"""
    R = float(params.get("R", 10.0))
    wg_w = float(params.get("wg_width", 0.5))
    gap = float(params.get("gap", 0.3))
    if kind in ("RingResonator", "RingAddDrop"):
        half = R * 1.5
        off = R + wg_w / 2.0 + gap
        return {
            "in": (-half, -off),
            "out": (half, -off),
            "drop": (0.0, off),
        }.get(port, (0.0, 0.0))
    if kind == "Waveguide":
        length = float(params.get("length", 10.0))
        return {"in": (0.0, 0.0), "out": (length, 0.0)}.get(port, (0.0, 0.0))
    if kind == "GratingCoupler":
        L = float(params.get("L", 10.0))
        return {"fib": (0.0, 0.0), "wg": (0.0, L)}.get(port, (0.0, 0.0))
    if kind == "DirectionalCoupler":
        # 与 gds_export.geometry_desc 的双波导表达逐点一致：
        # 两臂 y=±off，x∈[0, Lc]；off=(gap+core_w)/2。
        core_w = float(params.get("width", 0.5))
        gap = float(params.get("gap", 0.3))
        Lc = float(params.get("Lc", 10.0))
        off = (gap + core_w) / 2.0
        return {"in1": (0.0, off), "in2": (0.0, -off),
                "out1": (Lc, off), "out2": (Lc, -off)}.get(port, (0.0, 0.0))
    if kind == "MZI":
        # P0 网格 P&R · 单 MZI 单元局部端口锚（Clements 矩形网格相邻耦合约定）。
        # 局部原点 = 下轨 (rail j) 左端；上轨 (rail j+1) 在 local y=dy（=rail_pitch）。
        # 四端口：in1/out1 在下轨（y=0），in2/out2 在上轨（y=dy）。
        Lu = float(params.get("Lu", 20.0))
        dy = float(params.get("dy", 4.0))   # 下轨→上轨偏移（相邻轨间距）
        return {"in1": (0.0, 0.0), "out1": (Lu, 0.0),
                "in2": (0.0, dy), "out2": (Lu, dy)}.get(port, (0.0, 0.0))
    if kind == "PhaseShifter":
        # 输出相移器（P1-A 物理综合）：短波导段 + 片上加热/载流子相移。
        # 端口 in/out 在局部 (0,0) / (L,0)，与 Waveguide 同向，便于串入 rail 链。
        L = float(params.get("L", 4.0))
        return {"in": (0.0, 0.0), "out": (L, 0.0)}.get(port, (0.0, 0.0))
    if kind == "MMI":
        # 与 primitives.mmi_descs 逐点一致：input=(-L_tap,0)；
        # out1/out2=(L_mmi+L_tap+L_out, ±(w/2+out_gap/2))。
        # v0.9.95 · WDM 网格 P&R：支持 n_out>2 的 1×N 扇出（线性阵列，
        # 居中排布）。N=2 时与旧版逐字节一致（out1=+yo, out2=-yo）。
        w = float(params.get("width", 0.5))
        L = float(params.get("L_mmi", 20.0))
        Lt = float(params.get("L_tap", 4.0))
        gap = float(params.get("out_gap", 0.5))
        Lo = float(params.get("L_out", 3.0))
        yo = w / 2.0 + gap / 2.0
        n_out = int(params.get("n_out", 2))
        if n_out <= 2:
            return {"in": (-Lt, 0.0),
                    "out1": (L + Lt + Lo, yo),
                    "out2": (L + Lt + Lo, -yo)}.get(port, (0.0, 0.0))
        # N>2：out{j}（j=1..N）线性阵列，居中于 y=0
        step = yo * 2.0
        tbl = {"in": (-Lt, 0.0)}
        for j in range(1, n_out + 1):
            tbl[f"out{j}"] = (L + Lt + Lo, (j - (n_out + 1) / 2.0) * step)
        return tbl.get(port, (0.0, 0.0))
    if kind == "MMIC":
        # N×1 合波器（1×N 的镜像）：in1..inN 在左（线性阵列，居中），
        # out 在右（合波输出）。供 WDM 网格 P&R 平面输出端收口用。
        w = float(params.get("width", 0.5))
        L = float(params.get("L_mmi", 20.0))
        Lt = float(params.get("L_tap", 4.0))
        gap = float(params.get("out_gap", 0.5))
        Lo = float(params.get("L_out", 3.0))
        yo = w / 2.0 + gap / 2.0
        n_in = int(params.get("n_in", 2))
        step = yo * 2.0
        tbl = {"out": (Lt, 0.0)}
        for j in range(1, n_in + 1):
            tbl[f"in{j}"] = (-(L + Lt + Lo), (j - (n_in + 1) / 2.0) * step)
        return tbl.get(port, (0.0, 0.0))
    if kind == "SymmetricYBranch":
        # 与 gds_export.geometry_desc 逐点一致：input=(0,0)；
        # 两臂 (tap_len+arm·cos(half), ±arm·sin(half))，half=split_angle/2。
        angle = math.radians(float(params.get("split_angle", 10.0)))
        arm = float(params.get("arm_length", 5.0))
        half = angle / 2.0
        tap_len = min(arm * 0.25, 2.0)
        x0 = tap_len
        return {"in": (0.0, 0.0),
                "out1": (x0 + arm * math.cos(half), arm * math.sin(half)),
                "out2": (x0 + arm * math.cos(half), -arm * math.sin(half))
                }.get(port, (0.0, 0.0))
    if kind == "BraggMirror":
        # 与 primitives.bragg_grating_descs 逐点一致：input=(-L_in,0)；
        # output=(total_len_um - L_in, 0)。段长由 LDA 自有求解器导出，
        # 故惰性调用 bragg_grating_report 取精确末端（避免手写近似值漂移）。
        from lda_l2.primitives import bragg_grating_report as _bgr
        Li = float(params.get("L_in", 2.0))
        try:
            out_x = _bgr(params)["total_len_um"] - Li
        except Exception:
            out_x = 6.0
        return {"in": (-Li, 0.0), "out": (out_x, 0.0)}.get(port, (0.0, 0.0))
    return (0.0, 0.0)


def device_bbox(kind: str, params: dict) -> Tuple[float, float]:
    """器件包围盒半宽半高 (hw,hh) µm（器件原点 0,0）。"""
    R = float(params.get("R", 10.0))
    wg_w = float(params.get("wg_width", 0.5))
    gap = float(params.get("gap", 0.3))
    if kind in ("RingResonator", "RingAddDrop"):
        half = R * 1.5
        off = R + wg_w / 2.0 + gap
        return (half + R * 0.3, off + R * 0.3)
    if kind == "Waveguide":
        length = float(params.get("length", 10.0))
        return (length / 2.0, wg_w)
    if kind == "MZI":
        Lu = float(params.get("Lu", 20.0))
        dy = float(params.get("dy", 4.0))
        return (Lu / 2.0, dy / 2.0 + 2.0)
    if kind == "PhaseShifter":
        L = float(params.get("L", 4.0))
        wg_w = float(params.get("wg", 0.5))
        return (L / 2.0, wg_w / 2.0 + 1.0)
    if kind == "GratingCoupler":
        L = float(params.get("L", 10.0))
        return (max(L / 2.0, 5.0), 5.0)
    return (5.0, 5.0)


def place_row(link: LinkModel, pitch_x: Optional[float] = None,
              origin: Tuple[float, float] = (0.0, 0.0),
              y0: float = 0.0) -> Dict[str, Tuple[float, float, float]]:
    """沿 x 轴等距放置器件实例（按 link.ir.components 顺序）。

    pitch_x 省略时按最大器件半宽自动设定（≥ 2*hw + 余量）。
    返回 {inst: (x, y, rotation)}。
    """
    comps = link.ir.components
    if not comps:
        return {}
    if pitch_x is None:
        max_hw = max(device_bbox(c.kind, dict(c.params))[0] for c in comps)
        pitch_x = 2.0 * max_hw + 8.0
    return {c.id: (origin[0] + i * pitch_x, origin[1] + y0, 0.0)
            for i, c in enumerate(comps)}


def place_2d(link: LinkModel, cols: int = 3,
             origin: Tuple[float, float] = (0.0, 0.0),
             pitch_x: Optional[float] = None,
             pitch_y: Optional[float] = None) -> Dict[str, Tuple[float, float, float]]:
    """2D 网格放置（行优先，器件尺寸感知——第二梯队-2b，审计差距 #3）。

    在 place_row 单行基础上支持多行布局：按 cols 列宽分多行，
    行距/列距由器件包围盒自适应（≥2*hw/hh + 余量），旋转保持 0
    （端口默认左右方向，网格放置与波导布线天然对齐）。

    pitch_x/pitch_y 省略时按最大器件半宽/半高自动设定。
    """
    comps = link.ir.components
    if not comps:
        return {}
    bboxes = {c.id: device_bbox(c.kind, dict(c.params)) for c in comps}
    if pitch_x is None:
        pitch_x = 2.0 * max(hw for hw, _ in bboxes.values()) + 8.0
    if pitch_y is None:
        pitch_y = 2.0 * max(hh for _, hh in bboxes.values()) + 8.0
    cols = max(1, int(cols))
    out = {}
    for i, c in enumerate(comps):
        row, col = divmod(i, cols)
        out[c.id] = (origin[0] + col * pitch_x,
                     origin[1] + row * pitch_y, 0.0)
    return out


def port_abs(inst: str, port: str, placement: dict,
             link: LinkModel) -> Tuple[float, float]:
    """端口绝对坐标 (x,y)。v0.8.39：comp 查找走索引缓存（O(1) 查表）。"""
    ox, oy, _ = placement[inst]
    comp = _port_abs_comp_index(placement, link).get(inst)
    if comp is None:
        return (ox, oy)
    dx, dy = port_anchor(comp.kind, port, dict(comp.params))
    return (ox + dx, oy + dy)
