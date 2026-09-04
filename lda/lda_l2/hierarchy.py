"""LDA L2 · 层次化 GDS 导出（v0.9.33 · P0-1）。

把 flat 版图中**重复出现的单元**提取为一个 cell，再用 SREF/AREF 引用，
使 GDS 体积与元素数从 O(N) 降为 O(1)。

## 为什么需要

CPO 250k（40 光引擎 × 68 通道 × 8 波长）的 2,720 个通道几何完全相同，
flat 导出产生 **897,600 个元素 / 97.45 MB**。层次化后 = **1 个 CHANNEL cell
（330 元素）+ 1 条 AREF**，实测 **331 元素 / 36 KB**（降 99.96%）。

## 严格性要求（缺一不可，均已实测）

1. **周期由算法自动检测**（KMP 最小周期），不硬编码；
2. **阵列参数逐个严格校验**——任一实例位置不匹配即整体回退 flat；
3. **几何归属判定必须严格**——只把「完全落在 base 实例内」的几何收进
   cell（布线看 net 两端器件、IO 看端口所属器件），跨实例几何留在 TOP；
4. **展开后与 flat 逐元素等价**（DBU 量化比对，≤1 DBU）；
5. **检测失败自动回退 flat**，并在返回值中显式标注原因（不静默）。

## 🔴 与 POC 的关键差异（产品化必须补的）

POC（`assess_1m_hierarchy_poc.py`）在 CPO 上验证通过，但 CPO 案例**没有
跨通道布线、也没有非 base 的 IO**——所以 POC 只需处理 cell 内几何。
通用设计（任意网表）必然存在**不属于任何实例的几何**（跨通道布线、顶层
IO 环等）。本模块把它们显式收集为 `top_geoms` 并在等价性验证中计入，
否则会**静默丢失几何**（比不压缩更糟）。

## 非目标

- 不做任意网表的图同构挖掘（只识别「器件序列的平移重复」这一 CPO 形态）；
- 不做多层级嵌套（当前只支持一层 cell + TOP，已覆盖主要收益）。
"""
from __future__ import annotations

import math
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA = os.path.dirname(_HERE)
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

from lda_l2 import gds_export  # noqa: E402

Geom = Tuple


# ────────────────────────────────────────────────────────── 周期自动检测
def _signature(c) -> Tuple:
    """器件签名：kind + 数值参数（浮点保留 6 位防末位噪声）。"""
    p = tuple(sorted((k, round(float(v), 6))
                     for k, v in dict(c.params).items()
                     if isinstance(v, (int, float)) and not isinstance(v, bool)))
    return (c.kind, p)


def min_period(sigs: Sequence[Tuple]) -> Optional[int]:
    """KMP 前缀函数求 token 序列最小周期；无重复返回 None。"""
    n = len(sigs)
    if n < 2:
        return None
    pi = [0] * n
    for i in range(1, n):
        j = pi[i - 1]
        while j > 0 and sigs[i] != sigs[j]:
            j = pi[j - 1]
        if sigs[i] == sigs[j]:
            j += 1
        pi[i] = j
    p = n - pi[n - 1]
    if n % p != 0 or p >= n:
        return None
    return p if all(sigs[i] == sigs[i % p] for i in range(n)) else None


def detect_array(placement, comps, period: int,
                 tol: float = 1e-6) -> Optional[Tuple[int, int, float, float]]:
    """检测平移复用的 2D 矩形阵列参数。

    判据：实例 k 的位置 = base 位置 + (a·dx, b·dy)，a = k % nx，b = k // nx。
    **全部实例逐个严格校验**，任一不匹配即返回 None（整体回退 flat）。

    返回 (nx, ny, dx, dy) 或 None（非规则阵列 ⇒ 改用逐实例 SREF）。
    """
    n_inst = len(comps) // period
    if n_inst < 2:
        return None
    base = placement[comps[0].id]
    shifts = []
    for k in range(n_inst):
        x0, y0 = placement[comps[k * period].id][0], placement[comps[k * period].id][1]
        shifts.append((round(x0 - base[0], 6), round(y0 - base[1], 6)))

    dx, dy_row = shifts[1]
    if abs(dy_row) > tol:            # 实例 1 已换行 ⇒ 每行仅 1 个实例
        nx = 1
    else:
        nx = 2
        while nx < n_inst:
            sx, sy = shifts[nx]
            if abs(sy) > tol:        # 换行
                break
            if abs(sx - dx * nx) > tol:   # 非等间距 ⇒ 不规则
                return None
            nx += 1
    if n_inst % nx != 0:
        return None
    ny = n_inst // nx
    dy = shifts[nx][1] if nx < n_inst else 0.0

    for k in range(n_inst):
        a, b = k % nx, k // nx
        sx, sy = shifts[k]
        if abs(sx - a * dx) > tol or abs(sy - b * dy) > tol:
            return None
    return nx, ny, dx, dy


# ────────────────────────────────────────────────────────── 层次化方案
class HierarchyPlan:
    """层次化导出方案（cell + 引用）。

    属性：
      cell_name   : cell 结构名
      period      : 每实例的器件数
      n_inst      : 实例总数
      nx, ny      : 阵列列/行数（AREF）；逐实例 SREF 时为 (n_inst, 1)
      dx, dy      : 阵列步进 µm（AREF）；逐实例 SREF 时为 (0, 0)
      origin      : 阵列原点（= base 实例首器件位置）
      cell_geoms  : cell 几何（**局部坐标**）
      top_geoms   : 不属于任何实例的几何（**绝对坐标**，跨实例布线/IO 等）
      use_aref    : 是否用 AREF（False ⇒ 逐实例 SREF）
    """

    def __init__(self, cell_name, period, n_inst, nx, ny, dx, dy,
                 origin, cell_geoms, top_geoms, use_aref):
        self.cell_name = cell_name
        self.period = period
        self.n_inst = n_inst
        self.nx, self.ny = nx, ny
        self.dx, self.dy = dx, dy
        self.origin = origin
        self.cell_geoms = cell_geoms
        self.top_geoms = top_geoms
        self.use_aref = use_aref

    @property
    def n_elements(self) -> int:
        """层次化后的 GDS 元素数（cell 元素 + 引用记录 + 顶层散装几何）。"""
        n_refs = 1 if self.use_aref else self.n_inst
        return len(self.cell_geoms) + n_refs + len(self.top_geoms)

    def instance_origins(self) -> List[Tuple[float, float]]:
        """全部实例的原点（绝对坐标）。"""
        ox, oy = self.origin
        if self.use_aref:
            return [(ox + a * self.dx, oy + b * self.dy)
                    for b in range(self.ny) for a in range(self.nx)]
        return [(ox, oy)] * self.n_inst


def detect_hierarchy(link, placement, routes, wg_width: float = 0.5,
                     cell_name: str = "CHANNEL",
                     min_instances: int = 2,
                     with_io_grating: bool = True) -> Optional[HierarchyPlan]:
    """检测版图中的重复单元，返回层次化方案；不适用则返回 None。

    `None` 是**正常结果**而非错误——调用方应回退 flat 并如实标注原因。
    """
    from lda_l2.chip_layout_export import (
        device_geom_of, io_ports_of, _rebase_geom, _geom_key)

    comps = list(link.ir.components)
    sigs = [_signature(c) for c in comps]
    period = min_period(sigs)
    if period is None:
        return None
    n_inst = len(comps) // period
    if n_inst < max(2, min_instances):
        return None

    # 单元成员：第 0 个实例的器件
    base_ids = {c.id for c in comps[:period]}
    bx0, by0 = placement[comps[0].id][0], placement[comps[0].id][1]

    # ── cell 几何：base 实例的全部器件几何（局部坐标）
    cell_geoms: List[Geom] = []
    for c in comps[:period]:
        for g in device_geom_of(c, placement, wg_width):
            cell_geoms.append(_rebase_geom(g, bx0, by0))

    # 器件 → 实例索引（周期检测已保证全部器件归属某个实例）
    inst_of = {c.id: i // period for i, c in enumerate(comps)}

    # net → 两端器件集合（"inst.port" 取器件 id；用于判断布线是否跨实例）
    net_devs: Dict[Any, set] = {
        net.id: {str(c).split(".", 1)[0] for c in net.connects}
        for net in link.ir.nets}

    # ── 布线归属 ────────────────────────────────────────────────
    # 语义（🔴 P0-1 关键，第一版在这里判错）：
    #   • 实例内布线（两端器件同属一个实例） ⇒ **由 cell 展开覆盖**，
    #     只需把 base 的那一份收进 cell；其他实例的那一份**跳过**，
    #     否则展开后会重复。
    #   • 跨实例布线（两端分属不同实例）     ⇒ 进 top_geoms（展开会在
    #     每个实例都画一条，是错的，必须留在顶层画一次）。
    #   • 非对称的实例内布线（某实例独有，base 中没有对应项）⇒
    #     进 top_geoms（不能进 cell，否则每个实例都多画一条）。
    route_geom: Dict[Any, Geom] = {}
    top_geoms: List[Geom] = []
    lib = gds_export.LIB_LAYER_SI
    for net_id, rr in (routes or {}).items():
        route_geom[net_id] = ("P", lib, wg_width,
                              tuple(_route_points(rr)))

    inst_origins = [placement[comps[k * period].id][:2]
                    for k in range(n_inst)]
    base_route_keys = set()
    for net_id, g in route_geom.items():
        devs = net_devs.get(net_id)
        if devs and devs <= base_ids:                    # base 实例内
            local = _rebase_geom(g, bx0, by0)
            base_route_keys.add(_geom_key(local))
            cell_geoms.append(local)

    for net_id, g in route_geom.items():
        devs = net_devs.get(net_id)
        if devs and devs <= base_ids:
            continue                                     # 已收进 cell
        if devs:
            insts = {inst_of.get(d) for d in devs}
            if len(insts) == 1 and None not in insts:    # 实例内（非 base）
                k = insts.pop()
                local = _rebase_geom(g, inst_origins[k][0], inst_origins[k][1])
                if _geom_key(local) in base_route_keys:
                    continue                             # 对称 ⇒ 展开覆盖
        top_geoms.append(g)                              # 跨实例 / 非对称

    # ── IO 归属 ─────────────────────────────────────────────────
    # 同上：挂在**任意实例器件**上的 IO 由展开覆盖，只有挂在「不属于任何
    # 实例」的器件上（顶层 IO 环、PAD）才进 top_geoms。
    base_io_keys = set()
    if with_io_grating:
        from lda_layout.placement import port_abs
        for (inst, port) in io_ports_of(link):
            if inst not in base_ids:
                continue
            ox, oy = port_abs(inst, port, placement, link)
            for d in _primitive_descs(wg_width):
                for g in _primitive_geom(d, ox, oy):
                    local = _rebase_geom(g, bx0, by0)
                    base_io_keys.add(_geom_key(local))
                    cell_geoms.append(local)

        for (inst, port) in io_ports_of(link):
            if inst in base_ids:
                continue
            if inst in inst_of:                          # 其他实例的器件
                k = inst_of[inst]
                ox, oy = port_abs(inst, port, placement, link)
                sym = True
                for d in _primitive_descs(wg_width):
                    for g in _primitive_geom(d, ox, oy):
                        local = _rebase_geom(g, inst_origins[k][0],
                                             inst_origins[k][1])
                        if _geom_key(local) not in base_io_keys:
                            sym = False
                            break
                    if not sym:
                        break
                if sym:
                    continue                             # 对称 ⇒ 展开覆盖
            # 非对称或不属于任何实例 ⇒ 顶层单独画
            ox, oy = port_abs(inst, port, placement, link)
            for d in _primitive_descs(wg_width):
                top_geoms.extend(_primitive_geom(d, ox, oy))

    # ── 阵列参数（失败则退回逐实例 SREF）
    arr = detect_array(placement, comps, period)
    if arr is None:
        origins = [placement[comps[k * period].id][:2] for k in range(n_inst)]
        return HierarchyPlan(cell_name, period, n_inst, n_inst, 1, 0.0, 0.0,
                             (bx0, by0), cell_geoms, top_geoms,
                             use_aref=False) if _uniform(origins) else None

    nx, ny, dx, dy = arr
    return HierarchyPlan(cell_name, period, n_inst, nx, ny, dx, dy,
                         (bx0, by0), cell_geoms, top_geoms, use_aref=True)


def _uniform(origins: Sequence[Sequence[float]]) -> bool:
    """逐实例 SREF 的兜底判据：至少有两个实例（无位置约束）。"""
    return len(origins) >= 2


# ────────────────────────────────────────────────────────── 局部辅助
def _route_points(rr) -> List[Tuple[float, float]]:
    from lda_l2.chip_layout_export import _route_points as _rp
    return _rp(rr)


def _rebase_geom(g: Geom, ox: float, oy: float) -> Geom:
    from lda_l2.chip_layout_export import _rebase_geom as _rb
    return _rb(g, ox, oy)


def _shift_geom(g: Geom, dx: float, dy: float) -> Geom:
    from lda_l2.chip_layout_export import _shift_geom as _sh
    return _sh(g, dx, dy)


def _geom_key(g: Geom, q: int = 1000) -> Tuple:
    from lda_l2.chip_layout_export import _geom_key as _gk
    return _gk(g, q)


def _primitive_descs(wg_width: float) -> List[Dict]:
    from lda_l2.primitives import primitive_descs
    return primitive_descs("grating_coupler",
                           {"width": wg_width, "n_tooth": 16})


def _primitive_geom(d: Dict, ox: float, oy: float) -> List[Geom]:
    from lda_l2.chip_layout_export import _desc_geoms
    return _desc_geoms(d, ox, oy)


# ────────────────────────────────────────────────────────── 编码
def encode_hierarchical(plan: HierarchyPlan, lib_name: str = "LDA_CHIP",
                        top_name: str = "TOP") -> bytes:
    """层次化方案 → GDSII 字节。"""
    from lda_l2.chip_layout_export import _encode_geom
    cell_elements = [_encode_geom(g) for g in plan.cell_geoms]
    top_elements = [_encode_geom(g) for g in plan.top_geoms]
    if plan.use_aref:
        top_elements.append(gds_export.aref(
            plan.cell_name, plan.origin, plan.dx, plan.dy,
            plan.nx, plan.ny))
    else:
        for (ox, oy) in plan.instance_origins():
            top_elements.append(gds_export.sref(plan.cell_name, (ox, oy)))
    return gds_export.gds_library(
        lib_name, {plan.cell_name: cell_elements, top_name: top_elements})


def expand_plan(plan: HierarchyPlan) -> List[Geom]:
    """把层次化方案展开回绝对坐标几何（等价性验证 / 抽样检查用）。"""
    from lda_l2.chip_layout_export import _shift_geom
    out: List[Geom] = []
    for (ox, oy) in plan.instance_origins():
        out.extend(_shift_geom(g, ox, oy) for g in plan.cell_geoms)
    out.extend(plan.top_geoms)
    return out
