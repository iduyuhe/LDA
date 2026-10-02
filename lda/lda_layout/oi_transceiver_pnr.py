# -*- coding: utf-8 -*-
"""LDA 光联接模块征程 · M2 · **G-OI2 收发器专用真 GDS builder**。

============================================================================
为什么需要它（G-OI2 缺口）
----------------------------------------------------------------------------
`lda_layout/wdm_mesh_pnr.py` 是 **WDM 网格计算核**（K 波长 × N×N Clements 酉网格，
每波长面真算该酉）—— 它**不是收发器**：没有调制器、没有探测器、没有电接口。
`lda_l2/oi_module.py`（M0）能**装配**收发器 IR 并算链路预算，但**不出真版图**
（无 placement / routes / GDS / DRC / LVS）。

⇒ M2 吃狗粮暴露的短板 G-OI2：**该收发器拓扑没有专用真 GDS builder**
⇒ 收发器只能停在「能算不能签」。本模块补上这一环。

============================================================================
拓扑（8×200G PAM4 · LPO/可插拔形态共用同一版图骨架）
----------------------------------------------------------------------------
  Tx ：N 个 `MziModulator` 阵列（外部激光注入，臂间电极驱动）
        → `MMIC` N×1 合波器 → `GratingCoupler`（wg→fib）出片
  光纤 span：**片外互连，不落芯片版图**（Tx/Rx 各自 GC 的 fib 端口为外部 IO）
  Rx ：`GratingCoupler`（fib→wg）入片
        → N 个 `RingAddDrop` 级联（add-drop bus，每环谐振一个信道）
        → N 个 `Photodetector`

全部并入**单一 LinkModel + 单一 placement/routes + 单次主权 DRC/LVS 签核**
⇒ 产出可下载的真 GDS 字节（经 D4 交付域 `oi_transceiver` 对外）。

============================================================================
布局纪律（防 LVS 假红 / 假绿 · 逐条可复核）
----------------------------------------------------------------------------
1. **两域 y 分离**：Tx 全部 y≥0（实测 Tx y∈[−3.75, 208.75]），Rx 全部 y<0
   （Rx y∈[−399.3, −245.6]）⇒ 两域走线 y 区间不相交 ⇒ **结构性无 cross_short**。
2. **反序 + L 型走线 ⇒ 可证无交叉**（本 builder 的第一条硬规律）：
   设源 `(a_i, s_i)`、目标 `(B, b_i)`（目标 x 全同 = B），走线取
   「先竖直（在 x=a_i）后水平（在 y=b_i）」。则竖直段 i 与水平段 j 相交的
   充要条件为 `a_i∈[a_j,B] ∧ b_j∈[min(s_i,b_i),max(s_i,b_i)]`。
   🔴 **只有当「源 x 次序」与「目标 y 次序」相反时，两个条件互为否定**
   ⇒ 仅 `i=j` 相交（同 net，不判）⇒ 零交叉。
   若两者**同向**，两条件等价 ⇒ **所有 i>j 对全部交叉**。
   （v0.9.178 首版 Tx（正序映射 i↔in{i+1}）与 Rx（det y 递减）双双踩中，
   LVS 各报 28 处 `short_cross`（C(8,2)）—— 这是首次运行即被门禁抓住的真 bug，
   也是本模块 docstring 保留这条规律的原因。）
   · Tx —— 源 `mod{i}.out` 的 x **阶梯递增**（a_i = i·dx_step + arm_L/2）；
           目标取 `MMIC.in{n−i}` ⇒ 其 x **全同**（B）、y **随 i 递减** ⇒ 反序 ✓。
   · Rx —— 源 `ring{i}.drop` 的 y **全同**（Y_ring+off）、x 随 i 递增；
           目标 `det{i}.in` 的 x **全同**（B_det）、y 随 i **递增** ⇒ 反序 ✓。
3. **bus 走线与环心 x 错开**：级联 bus 段只覆盖**环间间隙** [x_i+half, x_{i+1}−half]，
   而环心 x_i 落在间隙之外 ⇒ `depth{i}` 的竖直段穿过 bus 所在 y 线时
   **不与任何 bus 线段相交**（这是「穿过一条线」与「与线段相交」的区别，
   专门验证过——否则 N=8 时会出现 8 条假 cross_short）。
4. 全部端点由 `placement.port_anchor` 计算（**单一真源**，与 DRC/LVS 同源）。

============================================================================
诚实边界（逐条登记，不粉饰）
----------------------------------------------------------------------------
- 层规 = **公开工艺近似的设计规则**（非 Foundry PDK 标定值）；DRC 为**参数级**近似。
- **设计期签核**：`verdict` 属设计期 DRC/LVS，**非流片、非实测签核**。
- 🔴 **MMIC 几何为版图占位**：宽多模区 `W_mmi = (N−1)·lane_step + 10`
  （由**端口跨度**派生，保证端口落在多模区内），**未建模自成像长度**
  `L_π ∝ W²/λ` —— 真实 SOI 上 8 路合波所需的宽多模区可行性**未验**。
  这是 M2 吃狗粮暴露的**器件几何参数化短板**（登记为 G-OI-REG）。
- **fiber span 不落版图**（片外互连）⇒ Tx/Rx 为同一芯片的两个子电路，
  其光学连接由片外光纤完成；芯片版图只保证各自 GC 的光纤耦合面。
- **不报** TOPS / TOPS-W / fJ/op / pJ/bit（红线）。
- 判决全死标量，**LLM 不进判决路径**；零商业 EDA 依赖（纯 numpy 平台栈）。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from lda_chain.link_model import LinkModel
from lda_l2 import drc as drc_mod
from lda_l2 import gds_export as gx
from lda_l2 import lvs as lvs_mod
from lda_layout.placement import device_bbox, port_abs, _port_abs_cache_clear
from lda_layout.wdm_mesh_pnr import wdm_ring_anchor

__all__ = [
    "OI_TX_LANE_STEP_UM", "OI_TRANSCEIVER_DISCLOSURE",
    "build_oi_transceiver_pnr", "oi_transceiver_reverse_guard",
    "oi_transceiver_self_check", "demo_oi_transceiver",
]

# ─────────────────────────────────────────────────────────────────────────────
# 版图设计常量（µm；**尺寸设计值**，非 PDK 标定值）
# ─────────────────────────────────────────────────────────────────────────────
WG_UM = 0.5                    # 单模波导宽（≥ DRC min_width 0.35）
OI_TX_LANE_STEP_UM = 12.5      # 通道 y 间距（== MMIC 输入端口间距；8 路 ∴ 跨度 87.5）

# Tx 侧
TX_ARM_L_UM = 60.0             # 调制器臂长（版图紧凑取值；电光 V_π·L 未在此建模）
TX_ARM_GAP_UM = 4.0
TX_ELEC_W_UM = 1.0
TX_ELEC_GAP_UM = 0.5
TX_DX_STEP_UM = 70.0           # 调制器 x 阶梯（≥ arm_L + 10 ⇒ 防竖直段共线）
MMIC_L_UM = 60.0
MMIC_LT_UM = 6.0
MMIC_LO_UM = 6.0
MMIC_W_SPAN_UM = 10.0          # 多模区宽度余量（相对端口跨度）
_MMIC_B_X_MARGIN_UM = 60.0     # MMIC 输入 x 到「最右调制器输出」的余量
_MMIC_Y_MARGIN_UM = 40.0       # MMIC 原点到「最上调制器输出」的最小 y 余量

# Rx 侧
RX_RING_Y_UM = -260.0
RX_RING_M = 268                # 环区数 m = `lda_l2.oi_m2.plan_m2_rings()` 的搜索解（M2 O-band 栅）
# 🔴 原为 129（**M1 的 C-band 解**，误标为「M1/M2 规划给出的 m」）⇒ 版图环与 M2 链路预算
#    **不同参**（R 6.41 vs 13.31 µm）。v0.9.179 对齐为 M2 规划解 268，并由
#    `run_oi_m2_smoke` C15c 跨模块互锁（builder 的 m ⟷ 规划器 best m）。
RX_N_G = 4.2                   # 群折射率（M1 信道规划同源口径）
RX_RING_GAP_UM = 0.55
RX_RING_DX_UM = 30.0
RX_DET_PITCH_UM = 12.0         # 🔴 **必须递增**：目标 y 与源 x 同向才不交叉
_RX_B_X_MARGIN_UM = 60.0       # 探测器 in 公共 x（B_det）到「最右环心」的余量
_RX_Y_SAME_SIDE_MARGIN_UM = 40.0   # 探测器阵列最上件仍须低于源 y 线的余量
GC_L_UM = 14.0                 # GC 端口锚定长度（port_anchor 口径）
GC_LAMBDA_UM = 0.68            # 光栅周期（DRC 齿宽 = Λ·duty）
GC_DUTY = 0.55                 # 占空比（≥0.51 才能让齿宽 ≥ 0.35 通过 min_width）

# 交付/签核口径
OI_TRANSCEIVER_DISCLOSURE: Dict[str, str] = {
    "kind": "transceiver_pic_layout",
    "domain": "oi_transceiver",
    "topology": "N×200G PAM4 收发器（Tx 调制器阵列 + MMIC 合波 + GC；Rx GC + 环解波 + 探测器阵列）",
    "fiber_off_chip": "fiber span 为片外互连，**不落芯片版图**；Tx/Rx 由片外光纤连接。",
    "mmic_placeholder": ("MMIC 多模区宽度由端口跨度派生（(N−1)·lane_step+10），"
                         "**未建模自成像长度 L_π∝W²/λ** ⇒ 宽多模区在真实 SOI 的可行性未验"
                         "（M2 暴露的器件几何参数化短板 G-OI-REG）。"),
    "drc_level": "参数级 DRC（逐器件可制造性几何量）；非多边形布尔运算。",
    "rules_source": "层规 = 公开工艺近似设计规则（非 Foundry PDK 标定值）。",
    "signoff": "设计期签核（DRC/LVS）；非流片、非实测签核。",
    "no_energy": "零能效数字：不报 TOPS / TOPS-W / fJ/op / pJ/bit。",
    "llm": "判决全死标量，LLM 不进判决路径。",
}


def _mmic_out_gap_um(lane_step_um: float = OI_TX_LANE_STEP_UM) -> float:
    """MMIC 的 `out_gap` 使**输入端口间距 == 通道间距**。

    `port_anchor("MMIC")` 的步距 = `width + out_gap` ⇒ 反解 `out_gap = step − width`。
    单一真源：通道间距由本函数与 `_mod_origin` / `_mmic_in_y` 共用，不各写一份。
    """
    return float(lane_step_um) - WG_UM


def _mmic_w_mmi_um(n_lanes: int, lane_step_um: float = OI_TX_LANE_STEP_UM) -> float:
    """多模区宽度 = **端口跨度** + 余量（保证 N 个输入端口全落在多模区内）。"""
    return (n_lanes - 1) * float(lane_step_um) + MMIC_W_SPAN_UM


def _tx_last_mod_out_x_um(n_lanes: int) -> float:
    """最右调制器（`mod{n-1}`）输出端口的 x（源 x 序列的最大值）。"""
    return (n_lanes - 1) * TX_DX_STEP_UM + TX_ARM_L_UM / 2.0


def _mmic_x_um(n_lanes: int) -> float:
    """MMIC 原点 x —— **由通道数派生**，保证「目标 x 全同 = B」且 `B > max(源 x)`。

    🔴 这是布局纪律 2 的**前提**，不是排版偏好：首版把 x 写成常量 640 ⇒ n>8 时
    最右调制器输出 x 超过 MMIC 输入 x（B），水平段反向 ⇒ L 型走线交叉
    （n=12 实例 LVS 报 5 处 `short_cross`，被逐规模判据 T9 抓住）。
    """
    return (_tx_last_mod_out_x_um(n_lanes) + _MMIC_B_X_MARGIN_UM
            + MMIC_L_UM + MMIC_LT_UM + MMIC_LO_UM)


def _rx_det_x_um(n_lanes: int) -> float:
    """探测器 `in` 端口的**公共 x**（B_det）—— 由通道数派生。

    🔴 与 `_mmic_x_um` 同族的**前提**：布局纪律 2 要求「目标 x 全同 = B」且
    `B > max(源 x)`。Rx 的源是环的 drop，其 x = i·ring_dx（随 i 递增）⇒
    首版把 B_det 写成常量 270 ⇒ n>8 时最右环心 x 超过 B_det ⇒ 水平段反向 ⇒
    L 型走线交叉（n=12 实例 LVS 报 3 处 `short_cross`，被逐规模判据 T9 抓住）。
    """
    return (n_lanes - 1) * RX_RING_DX_UM + _RX_B_X_MARGIN_UM


def _rx_det_y0_um(n_lanes: int, ring_y_um: float, off_um: float) -> float:
    """探测器阵列**首件** y —— 由通道数派生，使**全部** det 低于源 y 线（Y0）。

    🔴 第三条隐含前提：L 型走线的无交叉证明要求「目标 y 与源 y **同侧**」
    （否则竖直段的 y 区间跨越源线，与另一条的竖直/水平段必然相交）。
    首版把首件 y 写成常量 −330 ⇒ n≥7 时 y 序列**穿过** Y0（Y0 ≈ −252.8）⇒
    rx_drop7..11 两两交叉（n=12 实例 LVS 报 10 处 `short_cross`）。
    """
    y0 = ring_y_um + off_um
    return y0 - (n_lanes - 1) * RX_DET_PITCH_UM - _RX_Y_SAME_SIDE_MARGIN_UM


def _mmic_y_um(n_lanes: int, lane_step_um: float = OI_TX_LANE_STEP_UM) -> float:
    """MMIC 原点 y —— **由通道数派生**，保证 `b_i > s_i`（目标 y 恒在源 y 之上）。

    最苛刻的一对是 (i=n−1)：`b_{n-1} − s_{n-1} = mmic_y + lane_step·(1.5−1.5n) + ag/2`
    ⇒ 取 `mmic_y = lane_step·(1.5n−1.5) + ag/2 + 余量` 即恒有 `b_i − s_i ≥ 余量 > 0`。
    """
    return (float(lane_step_um) * (1.5 * n_lanes - 1.5)
            + TX_ARM_GAP_UM / 2.0 + _MMIC_Y_MARGIN_UM)


def _ring_geometry(n_lanes: int) -> Dict[str, float]:
    """环几何锚（R / half / off）——取**首个信道**的环半径（M1 规划的 m·λ/(2π·n_g)）。

    λ 取信道规划的首信道波长（O-band 1311 nm 家族），与 `wdm_ring_anchor` 同源。
    """
    wl0 = 1311.0
    a = wdm_ring_anchor(wl0, n_g=RX_N_G, m=RX_RING_M, gap=RX_RING_GAP_UM)
    R = float(a["R_um"])
    return {"R_um": R, "half_um": 1.5 * R,
            "off_um": R + WG_UM / 2.0 + RX_RING_GAP_UM,
            "wl0_nm": wl0, "FSR_nm": float(a["FSR_nm"])}


# ─────────────────────────────────────────────────────────────────────────────
# GDS：把「器件几何」平移到版图坐标（复用 gds_export.geometry_desc 单一真源）
# ─────────────────────────────────────────────────────────────────────────────
def _device_elements(kind: str, params: Dict[str, Any],
                     x0: float, y0: float) -> List[bytes]:
    """器件几何 → 平移后的 GDSII 元素（**不重写几何**：只平移 descs 的点）。"""
    out: List[bytes] = []
    for d in gx.geometry_desc(kind, dict(params)):
        if d["kind"] == "path":
            pts = [(px + x0, py + y0) for (px, py) in d["points_um"]]
            out.append(gx.path(int(d["layer"]), float(d["width_um"]), pts))
        else:
            rings = [[(px + x0, py + y0) for (px, py) in ring]
                     for ring in (d.get("rings_um") or [])]
            out.append(gx.boundary(int(d["layer"]), gx._flatten_rings(rings)))
    return out


def layout_discipline_ok(link, placement: Dict[str, Any], n_lanes: int,
                         lane_step_um: float = OI_TX_LANE_STEP_UM
                         ) -> Dict[str, Any]:
    """**「反序 ⇒ 无交叉」三条前提**的机器判据（全部从实际 `link`/`placement` 派生）。

    这是本 builder 唯一「不是靠声明、而是靠几何事实」的护栏，也是 M2 吃狗粮
    逐规模实测暴露三条隐含前提后的**机器化收口**（首版把三个坐标写成常量 ⇒
    n>8 时分别报 5 / 3 / 10 处 `short_cross`）：

      ① `x_ok`             —— 目标 x **全同**且严格大于对应源 x 上界
                              （否则水平段反向 ⇒ 与竖直段的相交条件不再互否）；
      ② `reverse_order_ok` —— 目标 y 次序与源 x 次序**相反**
                              （Tx 必须用 `in{n−i}` 映射；Rx det y 必须递增）；
      ③ `same_side_ok`     —— 目标 y 与源 y 线**同侧**
                              （否则竖直段的 y 区间跨越源线 ⇒ 必与邻段相交）。

    三条**任一**不成立 ⇒ LVS 必报 `short_cross`（V1/V2 已分别实证 ② 与性质）。
    🔴 全部读 `port_anchor` 真实锚点，**不**写成常量 True（那是自证桩假判据）。
    """
    from lda_layout.placement import port_anchor

    kind_of = {c.id: c.kind for c in link.ir.components}
    params_of = {c.id: dict(c.params) for c in link.ir.components}

    def _pin(inst: str, port: str) -> Tuple[float, float]:
        ox, oy, _rot = placement[inst]
        dx, dy = port_anchor(kind_of[inst], port, params_of[inst])
        return (ox + dx, oy + dy)

    def _net(nid: str):
        return next((x for x in link.ir.nets if x.id == nid), None)

    tx_tgt = [_pin("mmic_tx", f"in{n_lanes - i}") for i in range(n_lanes)]
    tx_src = [_pin(f"mod{i}", "out") for i in range(n_lanes)]
    rx_tgt = [_pin(f"det{i}", "in") for i in range(n_lanes)]
    rx_src = [_pin(f"ring{i}", "drop") for i in range(n_lanes)]

    def _same_x(pts) -> bool:
        xs = [p[0] for p in pts]
        return max(xs) - min(xs) < 1e-9

    x_ok = (_same_x(tx_tgt) and _same_x(rx_tgt)
            and max(p[0] for p in tx_tgt) > max(p[0] for p in tx_src)
            and max(p[0] for p in rx_tgt) > max(p[0] for p in rx_src))

    tx_rev = all(f"mmic_tx.in{n_lanes - i}" in ((_net(f"tx_lane{i}") or
                                                type("_N", (), {"connects": []})()).connects)
                 for i in range(n_lanes))
    rx_inc = all(rx_tgt[i][1] < rx_tgt[i + 1][1] for i in range(n_lanes - 1))

    rx_y = rx_src[0][1]
    rx_side = all((p[1] - rx_y) * (rx_tgt[0][1] - rx_y) > 0 for p in rx_tgt)
    tx_side = all(t[1] > s[1] for t, s in zip(tx_tgt, tx_src))

    return {
        "x_ok": bool(x_ok),
        "reverse_order_ok": bool(tx_rev and rx_inc),
        "same_side_ok": bool(rx_side and tx_side),
        "ok": bool(x_ok and tx_rev and rx_inc and rx_side and tx_side),
        "detail": {
            "tx_target_x": max(p[0] for p in tx_tgt),
            "tx_source_x_max": max(p[0] for p in tx_src),
            "rx_target_x": max(p[0] for p in rx_tgt),
            "rx_source_x_max": max(p[0] for p in rx_src),
            "rx_source_y": rx_y,
            "rx_target_y_band": [min(p[1] for p in rx_tgt),
                                 max(p[1] for p in rx_tgt)],
            "tx_target_y_minus_source_y": min(t[1] - s[1]
                                              for t, s in zip(tx_tgt, tx_src)),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 主构造
# ─────────────────────────────────────────────────────────────────────────────
def build_oi_transceiver_pnr(n_lanes: int = 8,
                             tol: float = 1.0,
                             lib_name: str = "LDA_OI_TRANSCEIVER",
                             ) -> Dict[str, Any]:
    """构建 N×200G 收发器 PIC 的**真版图** + 网表 + GDS + DRC/LVS 报告。

    参数：
      n_lanes : 通道数（M2 = 8×200G = 1.6T）。
      tol     : LVS 端点→端口归属容差（µm）。
    返回结构化报告 dict（含 GDS 字节、双闸判决、版图 bbox、端口/网表计数、disclosure）。
    """
    n = int(n_lanes)
    if n < 1:
        raise ValueError("n_lanes 须 ≥ 1")
    lane_step = OI_TX_LANE_STEP_UM
    mmic_gap = _mmic_out_gap_um(lane_step)
    mmic_w_mmi = _mmic_w_mmi_um(n, lane_step)
    mmic_x = _mmic_x_um(n)
    mmic_y = _mmic_y_um(n, lane_step)
    det_x = _rx_det_x_um(n)
    ring = _ring_geometry(n)
    off = ring["off_um"]
    y_src_rx = RX_RING_Y_UM + off              # Rx 源（环 drop）的 y 线
    det_y0 = _rx_det_y0_um(n, RX_RING_Y_UM, off)

    link = LinkModel(domain="photon", name=f"OI_Transceiver_{n}x200G",
                     notes=("光联接模块 M2 · 收发器 PIC 版图（Tx 调制器阵列 + MMIC "
                            "合波 + GC；Rx GC + 环解波 + 探测器阵列）· G-OI2"))
    placement: Dict[str, Tuple[float, float, float]] = {}
    routes: Dict[str, dict] = {}
    elements: List[bytes] = []
    params_of: Dict[str, Dict[str, Any]] = {}
    kind_of: Dict[str, str] = {}

    def _add(inst: str, kind: str, params: Dict[str, Any],
             xy: Tuple[float, float], ports: Optional[List[str]] = None) -> None:
        link.add_device(inst, kind, params=params, ports=ports)
        _port_abs_cache_clear()       # 同 link 增量 add_device ⇒ 索引缓存必须失效
        placement[inst] = (float(xy[0]), float(xy[1]), 0.0)
        params_of[inst] = dict(params)
        kind_of[inst] = kind
        elements.extend(_device_elements(kind, params, xy[0], xy[1]))

    def _route(net_id: str, inst_a: str, port_a: str,
               inst_b: str, port_b: str, mid: Optional[List[Tuple[float, float]]] = None
               ) -> None:
        pa = port_abs(inst_a, port_a, placement, link)
        pb = port_abs(inst_b, port_b, placement, link)
        pts = [pa] + list(mid or []) + [pb]
        routes[net_id] = {"points_um": pts}
        link.connect(net_id, inst_a, port_a, inst_b, port_b)
        elements.append(gx.path(gx.LIB_LAYER_SI, WG_UM, pts))

    # ── Tx：调制器阵列（x 阶梯 + y 阶梯，由布局纪律 2 保证零交叉）────────────
    tx_mod_params = {"width": WG_UM, "arm_L": TX_ARM_L_UM,
                     "arm_gap": TX_ARM_GAP_UM, "elec_w": TX_ELEC_W_UM,
                     "elec_gap": TX_ELEC_GAP_UM}
    for i in range(n):
        inst = f"mod{i}"
        _add(inst, "MziModulator", tx_mod_params,
             (i * TX_DX_STEP_UM, i * lane_step))
        link.mark_source(inst, "in")     # 外部激光注入（单端口 net，不参与 LVS 比对）

    # ── Tx：MMIC N×1 合波器 ────────────────────────────────────────────────
    _add("mmic_tx", "MMIC",
         {"width": WG_UM, "W_mmi": mmic_w_mmi, "L_mmi": MMIC_L_UM,
          "L_tap": MMIC_LT_UM, "L_out": MMIC_LO_UM, "out_gap": mmic_gap,
          "n_in": n},
         (mmic_x, mmic_y),
         ports=["out"] + [f"in{j}" for j in range(1, n + 1)])

    # ── Tx：出片 GC（wg→fib）──────────────────────────────────────────────
    gc_params = {"L": GC_L_UM, "width": WG_UM,
                 "Lambda": GC_LAMBDA_UM, "duty": GC_DUTY, "n_tooth": 20, "L_in": 3.0}
    _add("gc_tx", "GratingCoupler", gc_params,
         (mmic_x + MMIC_LT_UM + 60.0, mmic_y - GC_L_UM))

    # ── 走线：mod{i}.out → mmic_tx.in{n−i}（先竖直后水平；**反序**证无交叉）
    #    🔴 必须是 `in{n−i}`（不是 `in{i+1}`）：目标 y 次序要与源 x 次序**相反**，
    #    否则 8 条 lane 走线两两相交（LVS 报 C(8,2)=28 处 short_cross）。
    for i in range(n):
        pa = port_abs(f"mod{i}", "out", placement, link)
        pb = port_abs("mmic_tx", f"in{n - i}", placement, link)
        _route(f"tx_lane{i}", f"mod{i}", "out", "mmic_tx", f"in{n - i}",
               mid=[(pa[0], pb[1])])
    pa = port_abs("mmic_tx", "out", placement, link)
    pb = port_abs("gc_tx", "wg", placement, link)
    _route("tx_out", "mmic_tx", "out", "gc_tx", "wg")

    # ── Rx：入片 GC（fib→wg）──────────────────────────────────────────────
    x_r0 = 0.0
    _add("gc_rx", "GratingCoupler", gc_params,
         (x_r0 - ring["half_um"] - 80.0, RX_RING_Y_UM - off - GC_L_UM))

    # ── Rx：环阵列（add-drop bus 级联）─────────────────────────────────────
    ring_params = {"R": ring["R_um"], "wg_width": WG_UM, "gap": RX_RING_GAP_UM}
    for i in range(n):
        _add(f"ring{i}", "RingAddDrop", ring_params,
             (x_r0 + i * RX_RING_DX_UM, RX_RING_Y_UM),
             ports=["in", "out", "drop"])

    # ── Rx：探测器阵列（in 端口公共 x = `_rx_det_x_um(n)`；y 随 i **递增**）──
    det_params = {"width": WG_UM, "det_L": 20.0, "det_w": 5.0}
    for i in range(n):
        _add(f"det{i}", "Photodetector", det_params,
             (det_x + 8.0, det_y0 + i * RX_DET_PITCH_UM))
        link.external_io(f"det{i}_out", f"det{i}", "out")

    # ── Rx 走线 ───────────────────────────────────────────────────────────
    _route("rx_in", "gc_rx", "wg", "ring0", "in")
    for i in range(n - 1):
        _route(f"rx_bus{i}", f"ring{i}", "out", f"ring{i + 1}", "in")
    for i in range(n):
        pa = port_abs(f"ring{i}", "drop", placement, link)
        pb = port_abs(f"det{i}", "in", placement, link)
        _route(f"rx_drop{i}", f"ring{i}", "drop", f"det{i}", "in",
               mid=[(pa[0], pb[1])])

    # ── GDS ───────────────────────────────────────────────────────────────
    gds_bytes = gx.gds_library(lib_name, {f"OI_TRX_{n}x200G": elements})

    # ── DRC（逐器件参数级）─────────────────────────────────────────────────
    drc_rules = drc_mod.rules_from_pdk(None)
    drc_results: Dict[str, Any] = {}
    for inst, kind in kind_of.items():
        drc_results[inst] = drc_mod.drc_check_device(kind, params_of[inst],
                                                     rules=drc_rules)
    drc_all_pass = all(r.passed for r in drc_results.values())

    # ── LVS（单一主权签核：连接 + 网格几何）────────────────────────────────
    lvs_report = lvs_mod.run_lvs(link, placement, routes, tol=tol)

    # ── 版图 bbox / 面积（器件 bbox ∪ 走线点）──────────────────────────────
    xs: List[float] = []
    ys: List[float] = []
    tx_ys: List[float] = []
    rx_ys: List[float] = []
    for inst, (x, y, _rot) in placement.items():
        hw, hh = device_bbox(kind_of[inst], params_of[inst])
        xs += [x - hw, x + hw]
        ys += [y - hh, y + hh]
        band = (tx_ys if inst.startswith(("mod", "mmic_tx", "gc_tx"))
                else rx_ys)
        band += [y - hh, y + hh]      # 🔴 用 **bbox 带**（非原点）判两域分离
    for rr in routes.values():
        for (px, py) in rr["points_um"]:
            xs.append(px)
            ys.append(py)
    bbox = {"x_min": min(xs), "x_max": max(xs), "y_min": min(ys), "y_max": max(ys)}
    footprint = (bbox["x_max"] - bbox["x_min"]) * (bbox["y_max"] - bbox["y_min"])

    honest_note = (
        f"G-OI2 收发器真 GDS：{n}×200G PAM4 收发器 PIC（光联接类芯片 · **非计算核**，"
        f"故不报能效/TOPS）：Tx {n} 个 MziModulator 阶梯阵列 + MMIC "
        f"{n}×1 合波 + GC 出片；Rx GC 入片 + {n} 个 RingAddDrop 级联 + {n} 个 Photodetector），"
        f"环半径 R = m·λ/(2π·n_g) = {ring['R_um']:.4f} µm（m={RX_RING_M}·n_g={RX_N_G}·"
        f"λ={ring['wl0_nm']:.0f}nm，FSR={ring['FSR_nm']:.3f}nm，与 D-42/D-57 同源物理锚）。"
        f"版图 {len(kind_of)} 器件 / {len(routes)} 网 / {len(elements)} GDS 元素，"
        f"bbox={bbox['x_max'] - bbox['x_min']:.0f}×{bbox['y_max'] - bbox['y_min']:.0f} µm²"
        f"（{footprint:.0f} µm²）。布局纪律：Tx(y∈[{min(tx_ys):.1f},{max(tx_ys):.1f}]) 与 "
        f"Rx(y∈[{min(rx_ys):.1f},{max(rx_ys):.1f}]) **y 区间不相交**；Tx/Rx 均用"
        f"「源 x 次序 ⟂ 目标 y 次序（**反序**）+ 目标 x 全同」L 型走线 ⇒ 竖直段 i 与"
        f"水平段 j 的相交充要条件互为否定、退化为 i=j ⇒ **结构性零 cross_short**。"
        f"DRC {'全绿' if drc_all_pass else '有违规'}；"
        f"LVS={lvs_report['verdict']}（{lvs_report['n_violations']} 违规）。"
        f"诚实边界：① **fiber span 为片外互连、不落版图**；② MMIC 多模区宽 "
        f"{mmic_w_mmi:.1f} µm 由端口跨度派生，**未建模自成像长度 L_π∝W²/λ** ⇒ 宽多模区"
        f"在真实 SOI 的可行性未验（M2 暴露的器件几何参数化短板）；③ 层规为公开工艺近似"
        f"（非 Foundry PDK 标定值）、DRC 为参数级近似；④ 本版图为**设计期签核**"
        f"（非流片、非实测签核）；⑤ 零能效数字（不报 TOPS/TOPS-W/fJ/op/pJ/bit）；"
        f"⑥ 判决全死标量，LLM 不进路径。"
    )

    return {
        "n_lanes": n,
        "net_per_lane_gbps": 200.0,
        "aggregate_gbps": n * 200.0,
        "n_tx_mods": n, "n_rx_rings": n, "n_rx_dets": n,
        "n_devices": len(kind_of), "n_nets": len(routes),
        "gds_bytes": gds_bytes,
        "gds_elements": len(elements),
        "gds_structures": 1,
        "drc_pass": drc_all_pass,
        "drc_results": {k: r.to_dict() for k, r in drc_results.items()},
        "lvs_verdict": lvs_report["verdict"],
        "lvs_n_violations": lvs_report["n_violations"],
        "lvs_match": lvs_report["match"],
        "lvs_full": lvs_report,
        "layout_bbox": bbox,
        "footprint_um2": footprint,
        "ring_anchor": ring,
        "mmic_w_mmi_um": mmic_w_mmi,
        "mmic_port_span_um": (n - 1) * lane_step,
        "mmic_origin_um": [mmic_x, mmic_y],
        "mmic_in_x_um": mmic_x - (MMIC_L_UM + MMIC_LT_UM + MMIC_LO_UM),
        "tx_source_x_max_um": _tx_last_mod_out_x_um(n),
        "rx_det_in_x_um": det_x,
        "rx_source_x_max_um": (n - 1) * RX_RING_DX_UM,
        "rx_source_y_um": y_src_rx,
        "rx_det_y_band_um": [det_y0, det_y0 + (n - 1) * RX_DET_PITCH_UM],
        # 布局纪律三条前提的**机器可读自证位**（供模块自检与门禁 T5b/T5c 消费）。
        # 🔴 全部**从实际走线/placement 派生**（不得写成常量 True —— 那是自证桩，
        #    "candidate ≡ golden" 的假判据；一旦映射被改回同序它必须跟着变 False）。
        "tx_lane_map_reversed": all(
            f"mmic_tx.in{n - i}" in next(
                x for x in link.ir.nets if x.id == f"tx_lane{i}").connects
            for i in range(n)),
        "rx_det_y_increasing": all(
            placement[f"det{i}"][1] < placement[f"det{i + 1}"][1]
            for i in range(n - 1)),
        "tx_all_b_above_s": all(
            _mmic_y_um(n, lane_step) + (n - i - (n + 1) / 2.0) * lane_step
            > i * lane_step + TX_ARM_GAP_UM / 2.0 for i in range(n)),
        "fiber_off_chip": True,
        "tx_y_band": [min(tx_ys), max(tx_ys)],
        "rx_y_band": [min(rx_ys), max(rx_ys)],
        "link": link, "placement": placement, "routes": routes,
        "disclosure": dict(OI_TRANSCEIVER_DISCLOSURE),
        "honest_note": honest_note,
    }


# ─────────────────────────────────────────────────────────────────────────────
# demo + 反向护栏
# ─────────────────────────────────────────────────────────────────────────────
def demo_oi_transceiver(n_lanes: int = 8) -> Dict[str, Any]:
    """收发器版图全流程 demo。"""
    rep = build_oi_transceiver_pnr(n_lanes=n_lanes)
    rep["target"] = f"{n_lanes}×200G PAM4 收发器 PIC（G-OI2 真 GDS）"
    return rep


def oi_transceiver_reverse_guard(rep: Optional[Dict[str, Any]] = None,
                                 n_lanes: Optional[int] = None) -> Dict[str, Any]:
    """反向护栏：注入缺陷**必须**让 LVS 亮红（证明签核不是假绿）。

    D1（断路 open）：删一条 `rx_drop{i}` 路由 ⇒ 原理图有 net 而版图无
      ⇒ 判 open ⇒ LVS 必 REJECT 且违规数 >0。
    D2（悬空 dangling）：把 `det{n-1}` 挪出 30 µm（远超 tol=1.0）⇒ 该 net 端点
      归属失败 ⇒ dangling ⇒ REJECT。
    D3（交叉短路 cross_short）：新增一条横穿 Tx 走线带的伪网（从最左竖直段左侧
      水平穿过到右侧）⇒ 与多条 tx_lane 竖直段相交 ⇒ 必报 cross_short ⇒ REJECT。
    """
    n = int(n_lanes if n_lanes is not None else (rep or {}).get("n_lanes", 8))
    out: Dict[str, Any] = {}

    # —— D1：删路由 → open ——
    bad = build_oi_transceiver_pnr(n_lanes=n)
    key = f"rx_drop{n - 1}"
    if key in bad["routes"]:
        del bad["routes"][key]
    r1 = lvs_mod.run_lvs(bad["link"], bad["placement"], bad["routes"], tol=1.0)
    out["D1_open_detected"] = bool(r1["verdict"] == "REJECT"
                                   and r1["n_violations"] > 0)
    out["D1_n_violations"] = r1["n_violations"]

    # —— D2：挪器件 → dangling ——
    bad2 = build_oi_transceiver_pnr(n_lanes=n)
    inst = f"det{n - 1}"
    x, y, rot = bad2["placement"][inst]
    bad2["placement"][inst] = (x + 30.0, y, rot)      # 远超 tol=1.0
    r2 = lvs_mod.run_lvs(bad2["link"], bad2["placement"], bad2["routes"], tol=1.0)
    out["D2_dangling_detected"] = bool(r2["verdict"] == "REJECT"
                                       and r2["n_violations"] > 0)
    out["D2_n_violations"] = r2["n_violations"]

    # —— D3：伪网横穿 Tx 走线带 → cross_short ——
    bad3 = build_oi_transceiver_pnr(n_lanes=n)
    pa = port_abs("mod0", "out", bad3["placement"], bad3["link"])
    ya = pa[1] - 20.0          # 落在 Tx 竖直段覆盖的 y 带内、但避开任何端点
    yb = pa[1] + 120.0
    xa = pa[0] - 20.0          # 在最左竖直段 (x=arm_L/2) 左侧
    xb = pa[0] + 400.0         # 横穿后续所有竖直段
    bad3["routes"]["_sneak"] = {"points_um": [(xa, ya), (xa, yb), (xb, yb)]}
    r3 = lvs_mod.run_lvs(bad3["link"], bad3["placement"], bad3["routes"], tol=1.0)
    out["D3_cross_detected"] = bool(r3["verdict"] == "REJECT"
                                    and r3["n_violations"] > 0)
    out["D3_n_violations"] = r3["n_violations"]
    out["all_detected"] = bool(out["D1_open_detected"] and out["D2_dangling_detected"]
                               and out["D3_cross_detected"])
    return out


def oi_transceiver_self_check(verbose: bool = True) -> Dict[str, Any]:
    """模块自检（**不含**突变探针；突变探针在 `run_oi_transceiver_pnr_smoke.py`）。"""
    n = 8
    rep = build_oi_transceiver_pnr(n_lanes=n)
    checks: List[Tuple[str, bool]] = []

    checks.append((f"GDS 非空（{rep['gds_elements']} 元素）", rep["gds_elements"] > 0
                   and len(rep["gds_bytes"]) > 0))
    checks.append(("GDS HEADER 魔数正确（确定性编码）",
                   bytes(rep["gds_bytes"][:4]) == b"\x00\x06\x00\x02"))
    checks.append((f"DRC 全绿（{len(rep['drc_results'])} 器件）", rep["drc_pass"]))
    checks.append((f"LVS ACCEPT（{rep['lvs_n_violations']} 违规）",
                   rep["lvs_verdict"] == "ACCEPT" and rep["lvs_n_violations"] == 0))
    checks.append((f"器件数 = 3N+3 = {rep['n_devices']}",
                   rep["n_devices"] == 3 * n + 3))
    checks.append((f"网数 = 3N+1 = {rep['n_nets']}（不含片外 fiber）",
                   rep["n_nets"] == 3 * n + 1))
    checks.append(("Tx/Rx **y 区间不相交**（结构性防交叉）",
                   rep["tx_y_band"][0] > rep["rx_y_band"][1]))
    checks.append((f"聚合 = {rep['aggregate_gbps']:.0f} Gb/s = 8×200G",
                   abs(rep["aggregate_gbps"] - 1600.0) < 1e-9))
    checks.append((f"MMIC 多模区宽 {rep['mmic_w_mmi_um']:.1f} ≥ 端口跨度 "
                   f"{rep['mmic_port_span_um']:.1f}",
                   rep["mmic_w_mmi_um"] >= rep["mmic_port_span_um"]))
    # 🔴 布局纪律「反序 ⇒ 无交叉」的**三条前提**必须由几何本身保证（M2 吃狗粮
    #    逐规模实测暴露：首版把 MMIC x / detector x / detector y0 写成常量，
    #    n>8 时三条前提各自被破坏 ⇒ LVS 分别报 5 / 3 / 10 处 short_cross）。
    _b_x, _src_max = rep["mmic_in_x_um"], rep["tx_source_x_max_um"]
    _rb, _rsm = rep["rx_det_in_x_um"], rep["rx_source_x_max_um"]
    _y0, _y1, _ysrc = (*rep["rx_det_y_band_um"], rep["rx_source_y_um"])
    checks.append((f"前提①：目标 x 全同且 > 源 x 上界（Tx {_b_x:.0f}>{_src_max:.0f} · "
                   f"Rx {_rb:.0f}>{_rsm:.0f}）", _b_x > _src_max and _rb > _rsm))
    checks.append(("前提②：目标 y 与源 y 次序**相反**"
                   "（Tx 映射 in{n−i} · Rx det y 递增）",
                   rep["tx_lane_map_reversed"] and rep["rx_det_y_increasing"]))
    checks.append((f"前提③：目标 y 与源 y 线**同侧**"
                   f"（Tx 全部 b_i>s_i · Rx det 带 [{_y0:.0f},{_y1:.0f}] vs 源线 {_ysrc:.0f}）",
                   rep["tx_all_b_above_s"] and (_y1 < _ysrc or _y0 > _ysrc)))
    # 🔴 **第二独立通道**：同一组「三条前提」再经 `layout_discipline_ok` 从
    #    `link`/`placement` 经 `port_anchor` **重新推一遍**。它不是上面 rep 派生位
    #    的同义重写（上面读 builder 算出的标量，这里读端口锚点真实几何）⇒
    #    两路都绿才算过（避免「同源相等」的假判据）。
    _lay = layout_discipline_ok(rep["link"], rep["placement"], n)
    checks.append((f"布局纪律三前提（第二通道·读 port_anchor 反推）"
                   f"x={_lay['x_ok']} · 反序={_lay['reverse_order_ok']} · "
                   f"同侧={_lay['same_side_ok']}", bool(_lay["ok"])))
    checks.append((f"环半径 {rep['ring_anchor']['R_um']:.3f} ≥ DRC min_bend_R 5.0",
                   rep["ring_anchor"]["R_um"] >= drc_mod.DEFAULT_RULES["min_bend_R_um"]))
    # 确定性
    rep2 = build_oi_transceiver_pnr(n_lanes=n)
    checks.append(("确定性：同参数 sha256 一致",
                   __import__("hashlib").sha256(rep["gds_bytes"]).hexdigest()
                   == __import__("hashlib").sha256(rep2["gds_bytes"]).hexdigest()))
    # 参数敏感性（防「常数化假确定性」）
    rep3 = build_oi_transceiver_pnr(n_lanes=n - 1)
    checks.append((f"参数敏感：n={n - 1} 时 sha256 必须不同",
                   __import__("hashlib").sha256(rep["gds_bytes"]).hexdigest()
                   != __import__("hashlib").sha256(rep3["gds_bytes"]).hexdigest()))

    ok = all(v for _, v in checks)
    if verbose:
        print("=== OI Transceiver PNR 自检 ===")
        for name, v in checks:
            print(f"  [{'PASS' if v else 'FAIL'}] {name}")
        print(f"  {rep['honest_note']}")
    return {"ok": ok, "checks": checks, "report": rep}


if __name__ == "__main__":
    r = oi_transceiver_self_check()
    raise SystemExit(0 if r["ok"] else 1)
