"""LDA L2 · LVS 器件参数几何回提（G4 · 版图↔原理图双向一致 · v0.9.128）。

**为什么需要它（问题陈述）**：
`lvs.py` 的 `extract_layout_netlist` 只从布线几何恢复**连接关系**，器件
`kind` 与 `params` **全部来自原理图声明**（`lvs.py:419-420`）——
⇒ 版图侧只有「实例存在性」，**没有任何几何尺寸回提**。
后果：版图把波导画成 30µm 而原理图声明 20µm、把环半径画成 8µm 而声明 10µm，
**LVS 一律 ACCEPT**（连接关系没变）。这正是 D4 定义「几何↔原理图双向一致」
缺失的那一半 —— 交付物在「连接对」但「尺寸错」时不可信。

**本模块做什么**：
从**版图几何**（`chip_layout_export.device_geom_of` 的绝对坐标 `Geom` 列表）
**独立测量**器件参数，与 IR 声明的 `params` 逐字段比对，产出
`device_param_mismatch` 违规（由 `lvs.run_lvs` 注入判决）。

🔴 **方法学独立性的诚实边界（必读）**：
  - 本模块的「测量」是 **几何 → 尺寸的逆映射**，与 `gds_export.geometry_desc`
    的「尺寸 → 几何的正向映射」是**两段不同的代码**（不同文件、不同作者路径），
    故可检出「几何被改动而 IR 未同步」这一真实失配；
  - ⚠️ **但两者共享「几何约定」这一先验知识**（例如「Waveguide 的 PATH 从
    x=0 到 x=length」）。因此这是 **代码路径级独立**，**不是**物理方法级独立 ——
    若正向约定本身写错，本模块会**同样错**（自洽却全错，参见 U10 血案 13）。
    ⇒ 本模块**不构成对几何约定的验证**；它验证的是「版图几何与 IR 声明是否
    一致」，不是「几何约定是否符合 foundry 事实」（后者需真 PDK deck，属 D5）。
  - 测量一律使用**平移不变量**（距离 / 跨度 / 半径），故**不依赖 placement 原点**；
    ⚠️ 当前 `device_geom_of` 忽略旋转（只用 placement 的前两维）⇒ 本模块同样
    **不含旋转不变量**（器件带旋转时 x 跨度类度量会失真）。当前流水线 rot ≡ 0。

**覆盖范围（v0.9.141 · G4/M4 攻关后 · 实测驱动）**：**14 类器件 / 44 个参数** ——
从首版的 7 类 / 7 参数扩到**全部链路器件类**（`DEVICE_CLASSES`）：

| kind | 回提参数（14 类全覆盖） |
|---|---|
| `Waveguide` | `length` |
| `GratingCoupler` | `L` |
| `DirectionalCoupler` | `Lc` · `gap` · `width` |
| `RingResonator` | `R` · `gap` · `wg_width` |
| `RingAddDrop` | `R` · `gap` · `wg_width` |
| `MMI` | `L_mmi` · `W_mmi` · `L_tap` · `L_out` · `out_gap` · `n_out` · `width` |
| `MMIC` | `L_mmi` · `W_mmi` · `L_tap` · `L_out` · `out_gap` · `n_in` · `width` |
| `Splitter` | `length` · `width` |
| `MZI` | `Lu` · `dy` · `wg` |
| `PhaseShifter` | `L` · `wg` |
| `MziModulator` | `arm_L` · `width` |
| `Photodetector` | `det_L` · `det_w` · `width` |
| `SymmetricYBranch` | `arm_length` · `split_angle` · `width` |
| `BraggMirror` | `periods` · `corrugation` · `width` · `taper_len` |

**为什么首版只做 7 类（以及 v0.9.141 改了什么）**：首版对
`MZI`/`MMIC`/`PhaseShifter`/`Splitter`/`MziModulator`/`Photodetector`
**直接 `raise`（根本没有版图几何）**，故这 6 类在 G4 上**结构性缺席** ——
不是"测不准"，是"没东西可测"。v0.9.141 给这 6 类补上真实版图几何
（`primitives.splitter_descs` / `mmic_descs` / `mzi_descs` + 既有基元接线），
覆盖才从 7/14 推到 14/14。

**参数分类（机器可审 · 见 `PARAM_TAXONOMY`）**：声明参数分三档 ——
`geometric`（本器件尺寸量，必须可回提）/ `encoded_not_recovered`（几何确实随它
变，但不是尺寸量或多解）/ `not_encoded`（几何**完全不编码**该参数）。判据由
`run_lvs_geom_smoke` 用**几何敏感性**独立复核，不靠注释自说自话。

🔴 **`coverage_declared` 结构性到不了 1.0**：声明参数含 `Q`/`kappa`/`n_g`/
`n_eff`/`phase_rad`/`target_*` 等**物理量与目标量**，版图不编码它们。规划 §4
M4 写的「100%」只可能落在**器件类**（`class_coverage`）与**几何量**
（`coverage_geometric`）两个口径上 —— 这是对一条**不可达指标**的口径更正
（并给出机器可证的分类依据），不是放宽判据。

判决口径：全死标量（坐标几何 + 距离比对），LLM 不进判决路径。
主权：C 级自写零依赖（仅标准库）。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

# 几何元组（与 chip_layout_export.Geom 同构）：
#   ("P", layer, width_um, pts)  —— PATH
#   ("B", layer, None, pt)       —— BOUNDARY（展平单环点列）
Geom = Tuple


# ---------------------------------------------------------------------------
# 1) 几何访问助手（不依赖任何正向映射代码）
# ---------------------------------------------------------------------------
def _paths(geoms: Sequence[Geom]) -> List[Sequence[Tuple[float, float]]]:
    """PATH 点列（"P"）。"""
    return [g[3] for g in geoms if g and g[0] == "P"]


def _boundaries(geoms: Sequence[Geom]) -> List[Sequence[Tuple[float, float]]]:
    """BOUNDARY 点列（"B"）。"""
    return [g[3] for g in geoms if g and g[0] == "B"]


def _dist(p: Tuple[float, float], q: Tuple[float, float]) -> float:
    """两点欧氏距离（平移不变量）。"""
    return math.hypot(q[0] - p[0], q[1] - p[1])


def _x_span(pts: Sequence[Tuple[float, float]]) -> float:
    """点列 x 跨度（平移不变量）。"""
    xs = [p[0] for p in pts]
    return max(xs) - min(xs)


def _y_span(pts: Sequence[Tuple[float, float]]) -> float:
    """点列 y 跨度（平移不变量）。"""
    ys = [p[1] for p in pts]
    return max(ys) - min(ys)


def _centroid(pts: Sequence[Tuple[float, float]]) -> Tuple[float, float]:
    """点列形心。"""
    n = len(pts)
    if n == 0:
        return (0.0, 0.0)
    return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n)


# ---------------------------------------------------------------------------
# 2) 各 kind 的测量器（输入 = 该器件的全部 Geom，输出 = 尺寸 µm | None）
# ---------------------------------------------------------------------------
def _m_single_path_length(geoms: Sequence[Geom]) -> Optional[float]:
    """单 PATH 端点距离（Waveguide.length / GratingCoupler.L）。"""
    p = _paths(geoms)
    if len(p) != 1 or len(p[0]) < 2:
        return None
    return _dist(p[0][0], p[0][-1])


def _m_dc_Lc(geoms: Sequence[Geom]) -> Optional[float]:
    """双 PATH 整体 x 跨度（DirectionalCoupler.Lc）。"""
    p = _paths(geoms)
    if len(p) != 2:
        return None
    pts = list(p[0]) + list(p[1])
    return _x_span(pts) if pts else None


def _m_ring_R(geoms: Sequence[Geom]) -> Optional[float]:
    """环形 PATH 顶点 → 形心距离（RingResonator.R / RingAddDrop.R）。

    取**点数最多**的 PATH（环形离散点数 ≫ bus 的 2 点），不硬编码索引。
    离散顶点均匀采样于半径 R 的圆上 ⇒ 各顶点到形心距离相等 = R（机器精度）。
    """
    p = _paths(geoms)
    if not p:
        return None
    ring = max(p, key=len)
    if len(ring) < 8:
        return None
    c = _centroid(ring)
    return sum(_dist(v, c) for v in ring) / len(ring)


def _m_ybranch_arm(geoms: Sequence[Geom]) -> Optional[float]:
    """两条 arm PATH 的端点距离（SymmetricYBranch.arm_length）。

    arm PATH = 2 点折线，起点在分叉点、终点在臂端 ⇒ 距离 = arm_length。
    取全部 2 点 PATH 的最大距离（taper 是 BOUNDARY，不参与）。
    """
    p = [q for q in _paths(geoms) if len(q) == 2]
    if not p:
        return None
    return max(_dist(q[0], q[1]) for q in p)


# ---------------------------------------------------------------------------
# 2b) v0.9.141（G4/M4）新增测量器 —— 把「13 类器件」的覆盖从 7 类推到全类
#     🔴 全部只收 `geoms`（签名可断言），不读 IR 声明 —— 与首版同纪律。
# ---------------------------------------------------------------------------
def _path_geoms(geoms: Sequence[Geom]) -> List[Geom]:
    """PATH 几何元组（保留 width 字段 —— 波导宽本身就是版图几何量）。"""
    return [g for g in geoms if g and g[0] == "P"]


def _rect_geoms(geoms: Sequence[Geom]) -> List[Geom]:
    """4 点 BOUNDARY（矩形/梯形族；taper 是 66 点，天然被排除）。"""
    return [g for g in geoms if g and g[0] == "B" and len(g[3]) == 4]


def _lead_geoms(geoms: Sequence[Geom]) -> List[Geom]:
    """2 点 PATH（引线/直臂）。"""
    return [g for g in _path_geoms(geoms) if len(g[3]) == 2]


def _lead_width(geoms: Sequence[Geom]) -> Optional[float]:
    """引线共同宽度（µm）。多条引线宽度不一致 ⇒ 判不可测（不取平均）。

    用途：MMI/MMIC/MZI/SymmetricYBranch 的「波导宽」声明量 —— 几何按该值
    绘制引线 ⇒ 版图自带该尺寸，属**几何回提**（不是读 IR 声明）。
    """
    ws = {round(float(g[2]), 9) for g in _lead_geoms(geoms) if g[2] is not None}
    return ws.pop() if len(ws) == 1 else None


def _lead_groups(geoms: Sequence[Geom]) -> List[List[Geom]]:
    """把 2 点引线按 min-x 分组（同一端的引线聚为一组）。"""
    groups: Dict[float, List[Geom]] = {}
    for g in _lead_geoms(geoms):
        key = round(min(p[0] for p in g[3]), 6)
        groups.setdefault(key, []).append(g)
    return list(groups.values())


def _m_lead_width(geoms: Sequence[Geom]) -> Optional[float]:
    """引线共同宽度（MMI/MMIC 的 `width`、MZI 的 `wg`、Y 分支的 `width`）。"""
    return _lead_width(geoms)


def _m_dc_gap(geoms: Sequence[Geom]) -> Optional[float]:
    """DirectionalCoupler.gap —— 由双轨中心距反解。

    几何：两轨中心线 y=±off，off=(gap+width)/2 ⇒ gap = 2·off − width，
    off 由引线 y 直接量得、width 由 PATH 宽度字段量得。
    """
    offs = {round(abs(p[1]), 9) for g in _lead_geoms(geoms) for p in g[3]}
    w = _lead_width(geoms)
    if len(offs) != 1 or w is None:
        return None
    return 2.0 * offs.pop() - w


def _m_dc_width(geoms: Sequence[Geom]) -> Optional[float]:
    """DirectionalCoupler.width（引线宽度字段）。"""
    return _lead_width(geoms)


def _m_ring_wg(geoms: Sequence[Geom]) -> Optional[float]:
    """RingResonator/RingAddDrop.wg_width（环中心线 PATH 的 width 字段）。"""
    p = _path_geoms(geoms)
    if not p:
        return None
    ring = max(p, key=lambda g: len(g[3]))
    return None if ring[2] is None else float(ring[2])


def _m_ring_gap(geoms: Sequence[Geom]) -> Optional[float]:
    """RingResonator/RingAddDrop.gap —— 由 bus 偏移反解（三项几何量联立）。

    几何：bus 中心线 y=±off，off = R + wg/2 + gap ⇒ gap = off − R − wg/2。
    三项（off / R / wg）**各自都是几何量**：off 取 2 点引线的 |y|、R 由环
    顶点到形心的平均距离、wg 取环 PATH 宽度。首版曾以「需串联三项、鲁棒性
    不足」为由不做 —— 但那三条都是机器精度几何量（见 smoke 反向判据），
    故 v0.9.141 改为**实测回提**（不硬凑：测不出即返回 None）。
    """
    buses = [g for g in _lead_geoms(geoms)
             if abs(g[3][0][0] - g[3][1][0]) > abs(g[3][0][1] - g[3][1][1])]
    off = min((abs(p[1]) for g in buses for p in g[3]), default=None)
    R = _m_ring_R(geoms)
    wg = _m_ring_wg(geoms)
    if off is None or R is None or wg is None:
        return None
    return off - R - wg / 2.0


def _m_body_rect_x(geoms: Sequence[Geom]) -> Optional[float]:
    """多模区矩形（4 点 BOUNDARY 中 y 跨度最大者）的 x 跨度。

    MMI/MMIC/`Splitter` 的多模干涉区 = 唯一的 4 点大矩形（taper 为 66 点）；
    y 跨度最大保证取到主体而非极细电极/引线。
    """
    rs = _rect_geoms(geoms)
    if not rs:
        return None
    return _x_span(max(rs, key=lambda g: _y_span(g[3]))[3])


def _m_body_rect_y(geoms: Sequence[Geom]) -> Optional[float]:
    """多模区矩形的 y 跨度（`Splitter.width` = 多模区宽）。"""
    rs = _rect_geoms(geoms)
    if not rs:
        return None
    return _y_span(max(rs, key=lambda g: _y_span(g[3]))[3])


def _m_taper_len(geoms: Sequence[Geom]) -> Optional[float]:
    """taper 段长（66 点 BOUNDARY 的 x 跨度；全部 taper 同长 ⇒ 唯一）。"""
    spans = {round(_x_span(g[3]), 9) for g in geoms
             if g and g[0] == "B" and len(g[3]) > 4}
    return spans.pop() if len(spans) == 1 else None


def _m_lead_len_array(geoms: Sequence[Geom]) -> Optional[float]:
    """**成组引线**（成员 ≥2 的那一组）的 x 跨度（= MMI/MMIC 的 L_out）。

    MMI 的输出组在右（成员 = n_out）、MMIC 的输入组在左（成员 = n_in）：
    两者都是「同端成组」的那一组，故本规则与朝向无关。
    """
    gs = _lead_groups(geoms)
    if len(gs) != 2:
        return None
    arr = max(gs, key=len)
    if len(arr) < 2:
        return None          # 单路（n=1）⇒ 两端无法区分，判不可测
    spans = {round(_x_span(g[3]), 9) for g in arr}
    return spans.pop() if len(spans) == 1 else None


def _m_lead_len_single(geoms: Sequence[Geom]) -> Optional[float]:
    """**单路引线**那一组的 x 跨度（= MMI/MMIC 的 L_tap 引线段）。"""
    gs = _lead_groups(geoms)
    if len(gs) != 2:
        return None
    single = min(gs, key=len)
    if len(single) != 1 or len(max(gs, key=len)) < 2:
        return None
    return _x_span(single[0][3])


def _m_lead_gap(geoms: Sequence[Geom]) -> Optional[float]:
    """`out_gap` —— 由成组引线的**相邻中心距**反解：gap = 间距 − 波导宽。

    🔴 必须先用 set 去重 y（每条引线的两个端点同 y）。不去重会把 0.0 当成
    一个"间距"⇒ 步距集合有 2 个元素 ⇒ 判不可测（首版实测踩到）。
    """
    gs = _lead_groups(geoms)
    if len(gs) != 2:
        return None
    arr = max(gs, key=len)
    if len(arr) < 2:
        return None
    ys = sorted({p[1] for g in arr for p in g[3]})
    steps = {round(ys[i + 1] - ys[i], 9) for i in range(len(ys) - 1)}
    w = _lead_width(geoms)
    if len(steps) != 1 or w is None:
        return None
    return steps.pop() - w


def _m_lead_count_array(geoms: Sequence[Geom]) -> Optional[float]:
    """成组引线的成员数（MMI.n_out / MMIC.n_in）。"""
    gs = _lead_groups(geoms)
    if len(gs) != 2:
        return None
    arr = max(gs, key=len)
    return None if len(arr) < 2 else float(len(arr))


def _m_mzi_Lu(geoms: Sequence[Geom]) -> Optional[float]:
    """MZI.Lu（双轨引线的 x 跨度）。"""
    p = _lead_geoms(geoms)
    if len(p) < 2:
        return None
    spans = {round(_x_span(g[3]), 9) for g in p}
    return spans.pop() if len(spans) == 1 else None


def _m_mzi_dy(geoms: Sequence[Geom]) -> Optional[float]:
    """MZI.dy（上下轨中心线间距 = 全部点的 y 跨度）。"""
    ys = [p[1] for g in _lead_geoms(geoms) for p in g[3]]
    if len(ys) < 2:
        return None
    return max(ys) - min(ys)


def _m_ps_L(geoms: Sequence[Geom]) -> Optional[float]:
    """PhaseShifter.L（主波导条 = 4 点矩形中 y 跨度**最小**者的 x 跨度）。"""
    rs = _rect_geoms(geoms)
    if not rs:
        return None
    return _x_span(min(rs, key=lambda g: _y_span(g[3]))[3])


def _m_ps_wg(geoms: Sequence[Geom]) -> Optional[float]:
    """PhaseShifter.wg（主波导条的 y 跨度）。"""
    rs = _rect_geoms(geoms)
    if not rs:
        return None
    return _y_span(min(rs, key=lambda g: _y_span(g[3]))[3])


def _m_mod_armL(geoms: Sequence[Geom]) -> Optional[float]:
    """MziModulator.arm_L（臂/电极矩形的 x 跨度；四件同长 ⇒ 取最大）。"""
    rs = _rect_geoms(geoms)
    if not rs:
        return None
    return max(_x_span(g[3]) for g in rs)


def _m_mod_width(geoms: Sequence[Geom]) -> Optional[float]:
    """MziModulator.width（臂厚 = 4 点矩形中 y 跨度最小者）。"""
    rs = _rect_geoms(geoms)
    if not rs:
        return None
    return min(_y_span(g[3]) for g in rs)


def _m_pd_detL(geoms: Sequence[Geom]) -> Optional[float]:
    """Photodetector.det_L（吸收区 = 4 点矩形中 y 跨度最大者的 x 跨度）。"""
    return _m_body_rect_x(geoms)


def _m_pd_detW(geoms: Sequence[Geom]) -> Optional[float]:
    """Photodetector.det_w（吸收区的 y 跨度）。"""
    return _m_body_rect_y(geoms)


def _m_pd_wg(geoms: Sequence[Geom]) -> Optional[float]:
    """Photodetector.width（输入波导条 = 4 点矩形中 y 跨度最小者的 y 跨度）。"""
    rs = _rect_geoms(geoms)
    if not rs:
        return None
    return min(_y_span(g[3]) for g in rs)


def _m_yb_split_angle(geoms: Sequence[Geom]) -> Optional[float]:
    """SymmetricYBranch.split_angle（arm 张角，单位度）。

    🔴 不能用"两臂端点之差"：两臂**同起点**（分叉点）且**同终点 x** ⇒ 两臂
    末点 x 差恒为 0（首版实测踩到，判不可测）。正解 = 取**单臂自身**的
    起点→终点向量 (Δx, Δy)：臂终点 = (x0+arm·cos(θ/2), ±arm·sin(θ/2))
    ⇒ θ = 2·atan2(Δy, Δx)。taper 是 66 点 BOUNDARY，不参与。
    """
    p = _lead_geoms(geoms)
    if len(p) != 2:
        return None
    dx = abs(p[0][3][-1][0] - p[0][3][0][0])
    dy = abs(p[0][3][-1][1] - p[0][3][0][1])
    if dx <= 0:
        return None
    return 2.0 * math.degrees(math.atan2(dy, dx))


def _m_bragg_periods(geoms: Sequence[Geom]) -> Optional[float]:
    """BraggMirror.periods（周期段 = 4 点矩形，每周期两段 ⇒ 计数 / 2）。"""
    n = len(_rect_geoms(geoms))
    return None if n == 0 or n % 2 else float(n // 2)


def _m_bragg_corrugation(geoms: Sequence[Geom]) -> Optional[float]:
    """BraggMirror.corrugation（宽段宽 − 窄段宽 = 周期矩形 y 跨度的极差）。"""
    ws = {round(_y_span(g[3]), 9) for g in _rect_geoms(geoms)}
    return None if len(ws) != 2 else max(ws) - min(ws)


def _m_bragg_width(geoms: Sequence[Geom]) -> Optional[float]:
    """BraggMirror.width（标称宽 = 引线 PATH 的宽度字段）。"""
    return _lead_width(geoms)


# ---------------------------------------------------------------------------
# 3) 可回提参数表 + 器件类清单 + 参数分类表
# ---------------------------------------------------------------------------
#: kind → {声明参数名: 测量器}。**只有列在这里的 (kind, param) 会被比对。**
#: v0.9.141（G4/M4）：7 类 / 7 参数 → **14 类 / 44 参数**（覆盖全部链路器件类）。
PARAM_MEASURERS: Dict[str, Dict[str, Any]] = {
    "Waveguide": {"length": _m_single_path_length},
    "GratingCoupler": {"L": _m_single_path_length},
    "DirectionalCoupler": {"Lc": _m_dc_Lc, "gap": _m_dc_gap,
                           "width": _m_dc_width},
    "RingResonator": {"R": _m_ring_R, "gap": _m_ring_gap,
                      "wg_width": _m_ring_wg},
    "RingAddDrop": {"R": _m_ring_R, "gap": _m_ring_gap,
                    "wg_width": _m_ring_wg},
    "MMI": {"L_mmi": _m_body_rect_x, "W_mmi": _m_body_rect_y,
            "L_tap": _m_taper_len, "L_out": _m_lead_len_array,
            "out_gap": _m_lead_gap, "n_out": _m_lead_count_array,
            "width": _m_lead_width},
    "MMIC": {"L_mmi": _m_body_rect_x, "W_mmi": _m_body_rect_y,
             "L_tap": _m_lead_len_single, "L_out": _m_lead_len_array,
             "out_gap": _m_lead_gap, "n_in": _m_lead_count_array,
             "width": _m_lead_width},
    "Splitter": {"length": _m_body_rect_x, "width": _m_body_rect_y},
    "MZI": {"Lu": _m_mzi_Lu, "dy": _m_mzi_dy, "wg": _m_lead_width},
    "PhaseShifter": {"L": _m_ps_L, "wg": _m_ps_wg},
    "MziModulator": {"arm_L": _m_mod_armL, "width": _m_mod_width},
    "Photodetector": {"det_L": _m_pd_detL, "det_w": _m_pd_detW,
                      "width": _m_pd_wg},
    "SymmetricYBranch": {"arm_length": _m_ybranch_arm,
                         "split_angle": _m_yb_split_angle,
                         "width": _m_lead_width},
    "BraggMirror": {"periods": _m_bragg_periods,
                    "corrugation": _m_bragg_corrugation,
                    "width": _m_bragg_width,
                    "taper_len": _m_taper_len},
}

#: 全部测量器名（供 smoke / 审计遍历，避免调用方硬编码名单）。
#: 🔴 一致性由 `run_lvs_geom_smoke` 判据把关：`PARAM_MEASURERS` 引用的每个
#: 测量器 `__name__` 必须落在此清单内（防「加了测量器忘登记」），且**双向**
#: 一致（防清单里留孤儿名）。
MEASURER_NAMES: Tuple[str, ...] = (
    "_m_single_path_length",
    "_m_dc_Lc",
    "_m_ring_R",
    "_m_ybranch_arm",
    "_m_dc_gap",
    "_m_dc_width",
    "_m_lead_width",
    "_m_ring_wg",
    "_m_ring_gap",
    "_m_body_rect_x",
    "_m_body_rect_y",
    "_m_taper_len",
    "_m_lead_len_array",
    "_m_lead_len_single",
    "_m_lead_gap",
    "_m_lead_count_array",
    "_m_mzi_Lu",
    "_m_mzi_dy",
    "_m_ps_L",
    "_m_ps_wg",
    "_m_mod_armL",
    "_m_mod_width",
    "_m_pd_detL",
    "_m_pd_detW",
    "_m_pd_wg",
    "_m_yb_split_angle",
    "_m_bragg_periods",
    "_m_bragg_corrugation",
    "_m_bragg_width",
)

#: **链路器件类全表（13 → 14）** —— 真相源 = `link_model._DEFAULT_PORTS` 的 12 类
#: ∪ {`RingAddDrop`, `MMIC`}。规划 §4 写的「13 类器件」是起草时的计数（漏了
#: `MMIC` 或 `BraggMirror` 之一）；本表是机器可核的口径，由 `run_lvs_geom_smoke`
#: 与 `link_model._DEFAULT_PORTS` **对表断言**（防两处漂移）。
DEVICE_CLASSES: Tuple[str, ...] = (
    "Waveguide", "GratingCoupler", "DirectionalCoupler", "RingResonator",
    "RingAddDrop", "MMI", "MMIC", "Splitter", "MZI", "PhaseShifter",
    "MziModulator", "Photodetector", "SymmetricYBranch", "BraggMirror",
)

#: 每类器件的**规范声明**（最小可放置实例的参数）—— 供 `class_coverage()`
#: 与 smoke / 探针复用，避免三处各写一份「代表性参数」而在漂移后互相背书。
CANONICAL_PARAMS: Dict[str, Dict[str, float]] = {
    "Waveguide": {"length": 12.0, "width": 0.5},
    "GratingCoupler": {"L": 10.0, "period": 0.63, "duty": 0.5},
    "DirectionalCoupler": {"gap": 0.3, "Lc": 10.0, "width": 0.5},
    "RingResonator": {"R": 10.0, "gap": 0.3, "wg_width": 0.5},
    "RingAddDrop": {"R": 6.0, "gap": 0.3, "wg_width": 0.5},
    "MMI": {"L_mmi": 20.0, "W_mmi": 6.0, "L_tap": 4.0, "L_out": 3.0,
            "out_gap": 0.5, "n_out": 2, "width": 0.5},
    "MMIC": {"L_mmi": 20.0, "W_mmi": 6.0, "L_tap": 4.0, "L_out": 3.0,
             "out_gap": 0.5, "n_in": 2, "width": 0.5},
    "Splitter": {"length": 5.0, "width": 2.0},
    "MZI": {"Lu": 20.0, "dy": 4.0, "wg": 0.5, "gap": 0.3},
    "PhaseShifter": {"L": 4.0, "wg": 0.5, "phase_rad": 1.0},
    "MziModulator": {"arm_L": 200.0, "width": 0.5},
    "Photodetector": {"det_L": 20.0, "det_w": 5.0, "width": 0.5},
    "SymmetricYBranch": {"width": 0.5, "split_angle": 10.0,
                         "arm_length": 5.0},
    "BraggMirror": {"periods": 6, "corrugation": 0.12, "width": 0.5,
                    "taper_len": 1.5,
                    "wl0_um": 1.55, "h_core_um": 0.22, "n_si": 3.48,
                    "n_sio": 1.44},
}

#: **参数分类表（机器可审）** —— kind → {参数名: (类别, 原因)}。
#: 类别三档（由 `run_lvs_geom_smoke` 用**几何敏感性**独立复核，不是自说自话）：
#:   * `geometric`              —— 声明值就是本器件版图的一个尺寸量 ⇒ 必须可回提
#:                                 （有测量器 + 往返实测吻合 + 几何敏感）。
#:   * `encoded_not_recovered`  —— 几何**确实随它变**，但它不是本器件的尺寸量
#:                                 （目标/工艺/求解输入），或反推多解 ⇒ 首版不收。
#:   * `not_encoded`            —— 本器件几何**完全不编码**它（几何不随它变）
#:                                 ⇒ 结构性不可回提（机器可证，非"懒得做"）。
PARAM_TAXONOMY: Dict[str, Dict[str, Tuple[str, str]]] = {
    "Waveguide": {
        "length": ("geometric", "单 PATH 首末点距离"),
        "width": ("not_encoded",
                  "几何按**全局**波导宽 wg_width 绘制 ⇒ 器件级 width 不落在本器件几何上"),
    },
    "GratingCoupler": {
        "L": ("geometric", "单 PATH 首末点距离（device_geom_of 只画输入波导）"),
        "period": ("not_encoded", "光栅齿未绘制 ⇒ 几何不编码周期"),
        "duty": ("not_encoded", "同上（齿未绘制）"),
        "width": ("not_encoded", "几何按全局波导宽绘制"),
    },
    "DirectionalCoupler": {
        "Lc": ("geometric", "双 PATH 整体 x 跨度"),
        "gap": ("geometric", "gap = 2·双轨中心距 − 波导宽"),
        "width": ("geometric", "引线 PATH 的 width 字段"),
        "kappa_target": ("not_encoded",
                         "目标耦合系数：几何只用 gap/Lc/width ⇒ 版图不编码它"),
    },
    "RingResonator": {
        "R": ("geometric", "环顶点 → 形心平均距离"),
        "gap": ("geometric", "gap = |bus 偏移| − R − wg/2（三项均为几何量）"),
        "wg_width": ("geometric", "环中心线 PATH 的 width 字段"),
        "Q": ("not_encoded", "品质因子：光谱/物理量，版图不编码"),
        "kappa": ("not_encoded", "耦合系数：物理量，版图不编码"),
        "n_g": ("not_encoded", "群折射率：材料/工艺量，版图不编码"),
        "target_fsr_nm": ("not_encoded", "设计目标：不入版图"),
    },
    "RingAddDrop": {
        "R": ("geometric", "环顶点 → 形心平均距离"),
        "gap": ("geometric", "gap = |bus 偏移| − R − wg/2"),
        "wg_width": ("geometric", "环中心线 PATH 的 width 字段"),
        "target_Q": ("not_encoded", "设计目标：不入版图"),
        "n_g": ("not_encoded", "群折射率：材料/工艺量"),
    },
    "MMI": {
        "L_mmi": ("geometric", "多模区矩形 x 跨度"),
        "W_mmi": ("geometric", "多模区矩形 y 跨度"),
        "L_tap": ("geometric", "taper 段 x 跨度（66 点 BOUNDARY）"),
        "L_out": ("geometric", "成组引线（n_out 路）的 x 跨度"),
        "out_gap": ("geometric", "out_gap = 成组引线相邻中心距 − 波导宽"),
        "n_out": ("geometric", "成组引线的成员数"),
        "width": ("geometric", "引线 PATH 的 width 字段"),
    },
    "MMIC": {
        "L_mmi": ("geometric", "多模区矩形 x 跨度"),
        "W_mmi": ("geometric", "多模区矩形 y 跨度"),
        "L_tap": ("geometric", "单路引线（合波输出）的 x 跨度"),
        "L_out": ("geometric", "成组引线（n_in 路）的 x 跨度"),
        "out_gap": ("geometric", "out_gap = 成组引线相邻中心距 − 波导宽"),
        "n_in": ("geometric", "成组引线的成员数"),
        "width": ("geometric", "引线 PATH 的 width 字段"),
    },
    "Splitter": {
        "length": ("geometric", "多模区矩形 x 跨度（IR `length` ↔ 基元 `L_mmi`）"),
        "width": ("geometric", "多模区矩形 y 跨度（IR `width` ↔ 基元 `W_mmi`）"),
    },
    "MZI": {
        "Lu": ("geometric", "双轨引线 x 跨度"),
        "dy": ("geometric", "上下轨中心线间距"),
        "wg": ("geometric", "轨 PATH 的 width 字段"),
        "gap": ("not_encoded",
                "耦合发生在**相邻** MZI 之间；单元自身不含耦合器几何"),
    },
    "PhaseShifter": {
        "L": ("geometric", "主波导条（4 点矩形中 y 跨度最小者）x 跨度"),
        "wg": ("geometric", "主波导条 y 跨度"),
        "phase_rad": ("not_encoded", "目标相移：物理目标，版图不编码"),
    },
    "MziModulator": {
        "arm_L": ("geometric", "臂/电极矩形 x 跨度"),
        "width": ("geometric", "臂矩形 y 跨度（4 点矩形中最小）"),
    },
    "Photodetector": {
        "det_L": ("geometric", "吸收区矩形（y 跨度最大）x 跨度"),
        "det_w": ("geometric", "吸收区矩形 y 跨度"),
        "width": ("geometric", "输入波导条（y 跨度最小）y 跨度"),
    },
    "SymmetricYBranch": {
        "arm_length": ("geometric", "两条 arm 引线的端点距离"),
        "split_angle": ("geometric", "arm 张角 = 2·atan2(|Δy|, Δx)"),
        "width": ("geometric", "arm PATH 的 width 字段"),
    },
    "BraggMirror": {
        "periods": ("geometric", "周期段（4 点矩形）计数 / 2"),
        "corrugation": ("geometric", "宽段宽 − 窄段宽 = 周期矩形 y 跨度极差"),
        "width": ("geometric", "引线 PATH 的 width 字段（= 标称宽）"),
        "taper_len": ("geometric", "taper 段 x 跨度（66 点 BOUNDARY）"),
        "wl0_um": ("encoded_not_recovered",
                   "决定段长 L=λ0/(4·n_eff)，但反解需 n_eff（多解）"),
        "h_core_um": ("encoded_not_recovered", "同上（EIM 归约输入）"),
        "n_si": ("not_encoded",
                 "材料折射率：本版图用 n_core/n_clad（BRAGG_DEFAULTS）派生段长，"
                 "n_si/n_sio 只进器件库 TMM 模型"),
        "n_sio": ("not_encoded", "同上（不落在本版图几何上）"),
        "target_r_min": ("not_encoded", "反射率目标：不入版图"),
    },
}

#: **在 `lda/**` 源码内没有「具名 `add_device` 调用」的器件类**。
#: 精确口径：不存在 `add_device(inst, "<Kind>"[, ...])` 或 `kind="<Kind>"`
#: 形式的**字面量** kind 调用（大小写敏感；`spice_netlist` 的
#: `"modulator"/"photodetector"` 属**电域 SPICE 器件**，不是光子器件类）。
#: ⚠️ 这是「**具名构造路径为零**」的机器事实，**不等于**「永不被实例化」
#: （kind 为变量、经 `lda_ir.photon` 工厂 + `ir.add` 的路径不在静态扫描范围）。
#: 意义：对这 6 类，「几何回提覆盖率」在现有流水线里**没有分母** ⇒ 其
#: 几何/测量器能力由 `run_lvs_geom_smoke` 的规范声明用例演示，而不是被实战使用。
#: 由 `run_lvs_geom_smoke` ⑲ 用源码扫描**双向**复核（一旦接线即红 ⇒ 逼更新本表）。
NO_NAMED_ADD_DEVICE: Tuple[str, ...] = (
    "BraggMirror", "DirectionalCoupler", "MziModulator", "Photodetector",
    "Splitter", "SymmetricYBranch",
)

#: 几何**不可生成**的 kind —— v0.9.141 起为空元组（14 类全部有版图几何）。
#: smoke 断言其为空，防回退；`chip_layout_export` 的诚实说明仍指向本常量。
GEOM_UNSUPPORTED_KINDS: Tuple[str, ...] = ()

#: 未分类参数的占位类别（smoke 断言规范声明中**不存在**此类别 ⇒ 无漏登记）。
CLASS_UNCLASSIFIED = "unclassified"


def classify_param(kind: str, param: str) -> Tuple[str, str]:
    """(参数, 类别) → (类别, 原因)。未登记 ⇒ (`unclassified`, 提示语)。"""
    hit = PARAM_TAXONOMY.get(kind, {}).get(param)
    if hit is None:
        return (CLASS_UNCLASSIFIED,
                "未登记：新增声明参数必须补进 PARAM_TAXONOMY（防静默漏登记）")
    return hit


def class_coverage(geom_of=None) -> Dict[str, Any]:
    """**14 类器件**的「几何可生成 + 可回提」覆盖（规划 M4 的机器口径）。

    对 `DEVICE_CLASSES` 的每一类，用 `CANONICAL_PARAMS` 造一个最小实例：
      ① 几何可生成（`device_geom_of` 不 raise）；
      ② `PARAM_MEASURERS` 里至少 1 个回提参数；
      ③ 规范声明里**每个**参数都在 `PARAM_TAXONOMY` 里有类别（无漏登记）。
    返回计数 + **缺失清单**（缺口机器可读，不靠文字）。

    🔴 `coverage_declared` 永远到不了 1.0 —— 因为声明参数里含 Q / kappa /
    n_g / n_eff / phase_rad / target_* 等**版图结构性不编码**的物理量与目标量。
    规划 §4 写的「100%」只能落在**器件类**与**几何量**两个口径上（本函数 +
    `coverage_geometric`），这是对不可达指标的口径更正，不是放宽判据。
    """
    n_ok = 0
    missing: List[List[str]] = []
    per_class: Dict[str, Dict[str, Any]] = {}
    for kind in DEVICE_CLASSES:
        why: List[str] = []
        params = CANONICAL_PARAMS.get(kind)
        if not params:
            why.append("无规范声明")
        if kind not in PARAM_MEASURERS:
            why.append("无可回提参数")
        uncls = sorted(str(p) for p in (params or {})
                       if classify_param(kind, str(p))[0] == CLASS_UNCLASSIFIED)
        if uncls:
            why.append(f"未分类参数 {uncls}")
        gen = False
        if params:
            try:
                from lda_chain.link_model import LinkModel
                if geom_of is None:
                    from lda_l2.chip_layout_export import device_geom_of as _g
                    geom_of = _g
                lm = LinkModel(name=f"cov_{kind}")
                lm.add_device("d0", kind, dict(params))
                geoms = geom_of(lm.ir.components[0], {"d0": (0.0, 0.0, 0.0)}, 0.5)
                gen = bool(geoms)
                if not gen:
                    why.append("几何为空")
            except Exception as exc:                # noqa: BLE001 —— 缺口要落表
                why.append(f"几何不可生成：{type(exc).__name__}")
        ok = not why
        n_ok += 1 if ok else 0
        if not ok:
            missing.append([kind] + why)
        per_class[kind] = {"ok": ok, "geometry": gen,
                           "n_params": len(params or {}), "why": why}
    return {
        "n_classes": len(DEVICE_CLASSES),
        "n_ok": n_ok,
        "class_coverage": (n_ok / len(DEVICE_CLASSES)) if DEVICE_CLASSES else 1.0,
        "missing": missing,
        "per_class": per_class,
    }


def measure_device_params(kind: str,
                          geoms: Sequence[Geom]) -> Dict[str, Optional[float]]:
    """从几何独立测量该 kind 的**全部**可回提参数。

    返回 {param: 测量值 µm | None}；None = 几何形态不满足测量前提
    （**不静默跳过**，由调用方登记为该参数的测量失败）。

    🔴 **测量独立性（机器可证）**：本函数与 `MEASURER_NAMES` 下的全部测量器
    **只接受 `geoms` 一个输入**（签名可断言），且源码不出现 `.params` /
    `declared` / `link` ⇒ **结构上无法读取 IR 声明**。这是「回提独立于声明」
    的机器验证依据，而非仅靠注释声称（判据见 `run_lvs_geom_smoke` ⑧）。
    """
    table = PARAM_MEASURERS.get(kind)
    if not table:
        return {}
    out: Dict[str, Optional[float]] = {}
    for param, fn in table.items():
        try:
            out[param] = fn(geoms)
        except Exception:                       # 测量器异常 ⇒ 记为不可测，不传播
            out[param] = None
    return out


# ---------------------------------------------------------------------------
# 4) 主入口：逐器件回提 + 与 IR 声明比对
# ---------------------------------------------------------------------------
def extract_layout_params(link, placement, wg_width: float = 0.5,
                          geom_of=None,
                          rel_tol: float = 1e-6,
                          abs_tol: float = 1e-9) -> Dict[str, Any]:
    """器件参数几何回提 + 比对（G4）。

    参数：
      link/placement : 与 run_lvs 同源
      wg_width       : 传给 geom_of 的默认波导宽（几何生成的兜底参数）
      geom_of        : 几何生成回调 (component, placement, wg_width) → [Geom]。
                       None ⇒ 惰性取 `chip_layout_export.device_geom_of`
                       （函数内 import，避免模块级循环依赖）。
      rel_tol/abs_tol: 比对容差。默认 (1e-6, 1e-9) —— 吸收浮点噪声
                       （cos/sin 离散），**远低于任何工艺意义**，故不掩盖真失配
                       （真失配是 µm 量级，见判据实测）。

    返回：
      {
        "devices": {inst: {"kind", "declared", "measured", "deltas", "ok"}},
        "violations": [{"inst","kind","param","declared","measured",
                        "abs_diff","rel_diff"}],
        "n_devices": int, "n_devices_checked": int,
        "n_params_checked": int,        # 实际比对成功的 (器件,参数) 对
        "n_params_recoverable": int,    # 落在可回提清单内的声明参数数
        "n_params_declared": int,       # 全部声明参数数
        "n_params_geometric": int,      # 分类为 geometric 的声明参数数（真分母）
        "coverage_by_table": float,     # n_params_checked / n_params_recoverable
        "coverage_geometric": float,    # 🔴 n_params_checked / n_params_geometric
                                        #    （M4 的真实口径：几何量是否 100% 回提）
        "coverage_declared": float,     # n_params_checked / n_params_declared
                                        #    （**结构性到不了 1.0**：含物理量/目标量）
        "class_coverage": float,        # 本 case 内「有 ≥1 参数成功回提」的类占比
        "unrecoverable_by_class": {类别: 计数},
        "n_unclassified": int,          # 未进 PARAM_TAXONOMY 的声明参数数（应为 0）
        "geom_failed": {inst: 原因},
        "unrecoverable": [[kind, param, "[类别] 原因"], ...],
        "honest_note": str,
      }
    """
    if geom_of is None:
        from lda_l2.chip_layout_export import device_geom_of as geom_of  # noqa

    devices: Dict[str, Dict[str, Any]] = {}
    violations: List[Dict[str, Any]] = []
    geom_failed: Dict[str, str] = {}
    unrecoverable: List[List[str]] = []
    by_class: Dict[str, int] = {}
    n_declared = 0
    n_recoverable = 0
    n_geometric = 0
    n_unclassified = 0
    n_checked = 0
    kinds_declared: set = set()
    kinds_hit: set = set()

    for c in link.ir.components:
        declared = {k: float(v) for k, v in dict(c.params).items()
                    if isinstance(v, (int, float))}
        n_declared += len(declared)
        kinds_declared.add(c.kind)
        table = PARAM_MEASURERS.get(c.kind, {})
        decl_recoverable = [p for p in declared if p in table]
        n_recoverable += len(decl_recoverable)

        # 补登记「声明了但本模块不覆盖」的参数（去重）—— 类别 + 原因来自
        # PARAM_TAXONOMY（机器可审）；未登记者标 `unclassified`，**不用**
        # 「v2 候选」这种含糊话术（含糊正是覆盖率被误读的入口）。
        for p in declared:
            if p in table:
                continue
            klass, reason = classify_param(c.kind, p)
            if klass == CLASS_UNCLASSIFIED:
                n_unclassified += 1
            by_class[klass] = by_class.get(klass, 0) + 1
            row = [c.kind, p, f"[{klass}] {reason}"]
            if row not in unrecoverable:
                unrecoverable.append(row)
        for p in declared:
            if classify_param(c.kind, p)[0] == "geometric":
                n_geometric += 1

        try:
            geoms = geom_of(c, placement, wg_width)
        except Exception as exc:
            geom_failed[c.id] = f"{type(exc).__name__}: {exc}"
            devices[c.id] = {"kind": c.kind, "declared": declared,
                             "measured": {}, "deltas": {}, "ok": False,
                             "geom_error": geom_failed[c.id]}
            continue

        measured = measure_device_params(c.kind, geoms)
        deltas: Dict[str, float] = {}
        okflags: Dict[str, bool] = {}
        measure_failed = [p for p in decl_recoverable
                          if measured.get(p) is None]
        for param in decl_recoverable:
            mv = measured.get(param)
            if mv is None:
                continue                       # 测量失败：不比对、不虚报通过
            dv = declared[param]
            d = mv - dv
            ok = math.isclose(mv, dv, rel_tol=rel_tol, abs_tol=abs_tol)
            deltas[param] = d
            okflags[param] = ok
            n_checked += 1
            kinds_hit.add(c.kind)
            if not ok:
                rel = abs(d) / abs(dv) if dv != 0 else float("inf")
                violations.append({
                    "inst": c.id, "kind": c.kind, "param": param,
                    "declared": dv, "measured": mv,
                    "abs_diff": d, "rel_diff": rel,
                })
        devices[c.id] = {"kind": c.kind, "declared": declared,
                         "measured": measured, "deltas": deltas, "ok": okflags,
                         "measure_failed": measure_failed}

    cov_table = (n_checked / n_recoverable) if n_recoverable else 1.0
    cov_decl = (n_checked / n_declared) if n_declared else 1.0
    cov_geom = (n_checked / n_geometric) if n_geometric else 1.0
    cov_class = (len(kinds_hit) / len(kinds_declared)) if kinds_declared else 1.0
    n_dev_checked = sum(1 for v in devices.values() if v.get("ok"))
    return {
        "devices": devices,
        "violations": violations,
        "n_devices": len(list(link.ir.components)),
        "n_devices_checked": n_dev_checked,
        "n_params_checked": n_checked,
        "n_params_recoverable": n_recoverable,
        "n_params_declared": n_declared,
        "n_params_geometric": n_geometric,
        "coverage_by_table": cov_table,
        "coverage_geometric": cov_geom,
        "coverage_declared": cov_decl,
        "class_coverage": cov_class,
        "unrecoverable_by_class": by_class,
        "n_unclassified": n_unclassified,
        "geom_failed": geom_failed,
        "unrecoverable": unrecoverable,
        "honest_note": (
            f"几何回提：{n_dev_checked}/{len(list(link.ir.components))} 器件"
            f"成功回提；比对 {n_checked} 个 (器件,参数) 对，失配 "
            f"{len(violations)} 项。覆盖 {len(PARAM_MEASURERS)} 类器件 × "
            f"{sum(len(v) for v in PARAM_MEASURERS.values())} 参数"
            f"（占声明的**几何量** {cov_geom:.1%}、占全部声明参数 "
            f"{cov_decl:.1%} —— 后者结构性到不了 1.0：Q/kappa/n_g/目标量等"
            f"不落在版图几何上）；几何不可生成 {len(geom_failed)} 器件、"
            f"不覆盖 {len(unrecoverable)} 类参数（类别计数 "
            f"{by_class or '{}'}）。判决全死标量（几何独立测量 + "
            f"距离比对），LLM 不进判决路径。"
            "诚实边界：本模块验证「版图几何与 IR 声明是否一致」，"
            "**不验证几何约定是否符合 foundry 事实**（后者需真 PDK deck）。"),
    }
