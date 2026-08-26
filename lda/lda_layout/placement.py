"""LDA L1/L2 · 器件放置（placement）+ 端口锚点 + 包围盒。

P1-M2 配合 router 使用：把 LinkModel 的器件实例映射到芯片坐标，
给出端口绝对坐标（供 router 布线）与器件包围盒（供 router 避障）。

端口锚点（WDM add-drop 约定，与 gds_export.geometry_desc 的 RingAddDrop
同源）：RingResonator 的 in/out 在 through bus（下，y=-off）、drop 在
drop bus（上，y=+off）；off = R + wg_width/2 + gap，half = R*1.5。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # 仅类型标注用，避免 lda_chain ↔ lda_layout 循环导入
    from lda_chain.link_model import LinkModel


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
    """端口绝对坐标 (x,y)。"""
    ox, oy, _ = placement[inst]
    comp = next((c for c in link.ir.components if c.id == inst), None)
    if comp is None:
        return (ox, oy)
    dx, dy = port_anchor(comp.kind, port, dict(comp.params))
    return (ox + dx, oy + dy)
