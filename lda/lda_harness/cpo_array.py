"""LDA · CPO（Co-Packaged Optics）共封装光引擎阵列生成器（v0.8.47 · 阶段2）。

阶段2 目标：把 v0.8.45（LVS O(n²) 治理）与 v0.8.46（GDS 导出 O(n²) 治理）
打通的**十万器件级全链能力**落到**真实器件样例**上——不再是抽象的
「N 个 Waveguide 串成一条链」，而是**共封装光学光子引擎阵列**：层次化
（阵列 → 光引擎 → 波长通道 → 波长 lane）、器件类型多样（微环调制器 /
WDM 解复用环 / 功率监测抽头 / 光栅耦合器 / 互连波导段）、参数由物理
谐振条件反解（非拍脑袋常数）。

──────────────────────────────────────────────────────────────────────
一、架构层次（真实 CPO 光引擎拓扑）
──────────────────────────────────────────────────────────────────────
  Array   ：n_oe   个光引擎（Optical Engine, OE）—— 交换 ASIC 周边环绕
  Engine  ：n_ch   个波长通道（Channel）—— 每个通道 = 1 路双向光纤端口
  Channel ：n_lane 条波长 lane（WDM 波长数，默认 LAN-WDM 8 波）
  Lane    ：一条完整光路（Tx 发射链 / Rx 接收链上的一段）

  每条 Tx 链 = 1 条独立光路（外部激光源 ELS 馈入 → 级联微环调制 →
  输出光栅耦合器 → 光纤）；
  每条 Rx 链 = 1 条独立光路（输入光栅耦合器 → 级联 add-drop 解复用 →
  探测器馈线）。

  默认 32 引擎 × 34 通道 × 8 波长 → **100,096 器件 / 2,176 条独立光路**。

──────────────────────────────────────────────────────────────────────
二、物理参数（由谐振条件反解，非拟合常数）
──────────────────────────────────────────────────────────────────────
  波长栅格  ：LAN-WDM 8 波（O 波段 1273.54–1304.42 nm，~4.5 nm 间隔）
  有效折射率：n_eff = 2.45（SOI 220 nm × 450 nm 条形波导，公开文献近似）
  谐振级数  ：m = 91（**整数**——微环谐振的物理约束，非自由参数）
  环半径    ：R_k = m · λ_k / (2π · n_eff)  →  7.530 – 7.713 µm

  半径差仅 ~0.18 µm（真实 WDM 微环的量级——波长选择靠热调谐 trimming
  微调到 ITU 栅格，版图差异本就极小；这里由公式直接给死，不注入虚假精度）。

  gap = 0.22 µm（≥ DRC min_space 0.20）；wg_width = 0.5 µm（≥ min_width 0.35）；
  监测环 R = 5.2 µm（≥ DRC min_bend_R 5.0）。全部满足 DEFAULT_RULES。

──────────────────────────────────────────────────────────────────────
三、几何策略：端口线对齐 + 零跳线（可证明无同层短路）
──────────────────────────────────────────────────────────────────────
  1. **端口线对齐**：每个器件的 in/out 端口在局部坐标下 y 相同（Waveguide
     恒 0；Ring 恒 −off）。放置时按「in 端口（链首用 out 端口）」做 y 补偿
     → 同一行全部器件的连接端口落在**同一条水平线** y = row·pitch_y 上。
  2. **零跳线**：pitch_x 取 ≥ max(out_dx) − min(in_dx) + 余量 → 所有行内
     连接都是**正向水平段**（不回折）；通道宽度 92 器件整除行宽 → 通道
     不跨行 → **不需要任何跨行跳线**。
  3. 于是全部布线为同层 M1 水平段，同行 x 区间互不重叠（段恰好连接相邻
     器件的 body 边缘）、异行 y 不同 → **同层短路数为 0**（几何保证，非
     靠 LVS 兜底）。

  诚实标注：这是**规则阵列（regular fabric）布线**——真实 CPO/PIC 的阵列
  化版图确实用预留布线通道 + 规则拓扑，但它不是拥塞感知的全局布线器。
  多层能力（跨引擎 shuffle）由 S11 规模锚（128k 多层）独立验证，本样例
  不为了"用上多层"而引入几何风险。

──────────────────────────────────────────────────────────────────────
四、诚实边界（不可省略）
──────────────────────────────────────────────────────────────────────
  - **只建模无源光子层**。有源器件（激光器 / 探测器 / 驱动 IC / TIA）按
    黑箱处理（LDA 负面清单：有源器件不做物理级建模）——探测器馈线以
    Waveguide 表达并 external_io 标记，不代表真实探测器几何。
  - 工艺为**公开文献近似**（SOI 220 nm 典型规则），非真实 foundry PDK。
  - 本模块只做**版图闭环**（构建→放置→布线→GDS→DRC→LVS），**不做光学
    仿真验证**（插损/串扰/FSR 属另一条链路，不在阶段2 范围）。
  - 未流片，无实测回流。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA = os.path.dirname(_HERE)
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

from lda_chain.link_model import LinkModel
from lda_layout.placement import device_bbox, port_abs, port_anchor
from lda_layout.router import route_net

# ── 物理常量（公开文献近似，见模块 docstring）──────────────────────────
LAN_WDM_CHANNELS_NM: Tuple[float, ...] = (
    1273.54, 1277.89, 1282.26, 1286.66,
    1291.10, 1295.50, 1299.92, 1304.42,
)
N_EFF_SOI = 2.45          # SOI 220nm×450nm 条形波导 @ O 波段（公开近似）
RING_ORDER_M = 91         # 谐振级数（整数，物理约束）
WG_WIDTH_UM = 0.5         # 波导芯宽（≥ DRC min_width 0.35）
GAP_UM = 0.22             # 耦合间隙（≥ DRC min_space 0.20）
MON_R_UM = 5.2            # 监测/锁定环半径（≥ DRC min_bend_R 5.0）
GC_L_UM = 12.0            # 光栅耦合器长度（沿传播方向）
PITCH_MARGIN_UM = 8.0     # 器件间最小留白（µm）

# 光栅耦合器齿形：由布拉格条件反解，且满足 DRC 线宽/间距**双**约束
#   λ_c = Λ · (n_eff,gr − sin θ)：浅刻蚀光栅 n_eff,gr ≈ 2.4，
#   光纤耦合角 θ = 15°（真实典型窗口 8–25° 内）
#   → Λ = 1.310 / (2.4 − sin15°) = 0.612 µm（正对 O 波段中心）
#   duty = 0.60 → 齿宽 0.367 µm（≥ min_width 0.35）· 齿隙 0.245 µm
#                 （≥ min_space 0.20）—— 双双合规，非拍脑袋取值
GC_LAMBDA_UM = 0.612
GC_DUTY = 0.60
GC_N_EFF_GRATING = 2.40
GC_COUPLING_ANGLE_DEG = 15.0

# 器件角色 → (kind, 参数构造所需的角色标记)
ROLE_KIND = {
    "wg_trunk": "Waveguide", "wg_feed": "Waveguide", "wg_pre": "Waveguide",
    "wg_post": "Waveguide", "wg_bus": "Waveguide", "wg_drop": "Waveguide",
    "wg_pd": "Waveguide",
    "mrm": "RingAddDrop", "demux": "RingAddDrop",
    "tap_in": "RingResonator", "mon": "RingResonator",
    "tap_rx": "RingResonator",
    "gc_tx": "GratingCoupler", "gc_rx": "GratingCoupler",
}

# 波导段长度（µm）——真实互连量级，同时受 pitch_x 约束（见 _pitch）
WG_LEN_UM = {
    "wg_trunk": 18.0, "wg_feed": 12.0, "wg_pre": 8.0, "wg_post": 8.0,
    "wg_bus": 18.0, "wg_drop": 10.0, "wg_pd": 8.0,
}

_PORTS = {
    "Waveguide": ["in", "out"],
    "RingResonator": ["in", "out"],
    "RingAddDrop": ["in", "out", "drop"],
    "GratingCoupler": ["fib", "wg"],
}

# 单波长 lane 的器件角色序列（顺序即光路顺序，也是版图顺序）
_TX_LANE_ROLES = ("wg_feed", "tap_in", "wg_pre", "mrm", "wg_post", "mon",
                  "wg_bus")
_RX_LANE_ROLES = ("demux", "wg_drop", "tap_rx", "wg_pd")


def ring_radius_um(lam_nm: float, m: int = RING_ORDER_M,
                   n_eff: float = N_EFF_SOI) -> float:
    """微环半径（µm）：由谐振条件 m·λ = 2π·n_eff·R 反解。

    m 必须为整数（物理约束）；本函数不四舍五入 m——m 由调用方给定整数，
    半径随 λ 连续变化（真实 WDM 微环阵列的设计方式）。
    """
    return m * (lam_nm / 1000.0) / (2.0 * math.pi * n_eff)


def lane_wavelengths(n_lane: int = 8) -> Tuple[float, ...]:
    """取前 n_lane 个 LAN-WDM 波长（nm）。n_lane ≤ 8。"""
    if not 1 <= n_lane <= len(LAN_WDM_CHANNELS_NM):
        raise ValueError(f"n_lane 须在 1..{len(LAN_WDM_CHANNELS_NM)}，实际 {n_lane}")
    return LAN_WDM_CHANNELS_NM[:n_lane]


@dataclass
class CPOArrayConfig:
    """CPO 光引擎阵列配置。"""

    n_oe: int = 32            # 光引擎数
    n_ch: int = 34            # 每引擎波长通道数
    n_lane: int = 8           # 每通道波长数（≤8，LAN-WDM）
    ch_per_row: int = 4       # 每行容纳的通道数（须整除 n_ch×n_oe）
    pitch_margin_um: float = PITCH_MARGIN_UM
    name: str = "cpo_array"

    def validate(self) -> None:
        if self.n_oe < 1 or self.n_ch < 1:
            raise ValueError("n_oe / n_ch 须 ≥ 1")
        if not 1 <= self.n_lane <= len(LAN_WDM_CHANNELS_NM):
            raise ValueError(f"n_lane 须在 1..{len(LAN_WDM_CHANNELS_NM)}")
        if self.ch_per_row < 1:
            raise ValueError("ch_per_row 须 ≥ 1")
        if (self.n_oe * self.n_ch) % self.ch_per_row != 0:
            raise ValueError(
                f"ch_per_row={self.ch_per_row} 须整除 n_oe×n_ch="
                f"{self.n_oe * self.n_ch}（否则通道跨行，需跨行跳线）")

    @property
    def n_channels(self) -> int:
        return self.n_oe * self.n_ch

    def channel_width(self) -> int:
        """单通道器件数（= Tx 链 + Rx 链长度）。"""
        return (1 + self.n_lane * len(_TX_LANE_ROLES) + 1) + \
               (1 + 1 + self.n_lane * len(_RX_LANE_ROLES))

    @property
    def n_devices(self) -> int:
        return self.channel_width() * self.n_channels

    @property
    def cols(self) -> int:
        return self.channel_width() * self.ch_per_row


# ── 器件清单生成 ──────────────────────────────────────────────────────
@dataclass
class DevSpec:
    """一个器件实例的描述（构建期中间表示）。"""

    id: str
    kind: str
    params: Dict[str, float]
    role: str
    chain_id: int          # 所属光路（-1 = 无）
    engine: int
    channel: int
    lane: int              # -1 = 通道级公共器件
    lam_nm: float = 0.0


def _role_params(role: str, lam_nm: float) -> Dict[str, float]:
    """角色 → 器件参数（物理反解，非拍脑袋）。"""
    kind = ROLE_KIND[role]
    if kind == "Waveguide":
        return {"length": WG_LEN_UM[role], "wg_width": WG_WIDTH_UM}
    if kind == "RingAddDrop":
        # MRM 与 DEMUX 同用谐振条件反解半径（同波长同半径——
        # 发射端调制该波长、接收端 drop 该波长，物理上对称）
        return {"R": round(ring_radius_um(lam_nm), 4),
                "wg_width": WG_WIDTH_UM, "gap": GAP_UM}
    if kind == "RingResonator":
        # 监测/波长锁定环：不参与波长选择 → 固定小半径（省面积）
        return {"R": MON_R_UM, "wg_width": WG_WIDTH_UM, "gap": GAP_UM}
    return {"L": GC_L_UM, "wg_width": WG_WIDTH_UM,
            "Lambda": GC_LAMBDA_UM, "duty": GC_DUTY}


def _out_port(kind: str) -> str:
    """光路「出端口」名（GratingCoupler 的波导侧是 wg，fib 是光纤侧/外部）。"""
    return "wg" if kind == "GratingCoupler" else "out"


def _in_port(kind: str) -> str:
    """光路「入端口」名。"""
    return "wg" if kind == "GratingCoupler" else "in"


def _io_port(kind: str, at_head: bool) -> str:
    """外部 IO 端口名（GC 走 fib；普通器件走 in/out）。"""
    if kind == "GratingCoupler":
        return "fib"
    return "in" if at_head else "out"


def _channel_specs(cfg: CPOArrayConfig, oe: int, ch: int,
                   chain_base: int, dev_base: int
                   ) -> Tuple[List[DevSpec], List[List[str]]]:
    """生成一个通道的全部器件 + 光路（链）划分。

    返回 (specs, chains)；chains 为每条光路的器件 id 序列（Tx 链在前）。
    """
    lams = lane_wavelengths(cfg.n_lane)
    specs: List[DevSpec] = []
    k = dev_base
    p = f"oe{oe}_ch{ch}"

    # ── Tx 链（发射）：ELS 馈入 → [波长 lane × n_lane] → 输出光栅 ──
    tx: List[str] = []
    d = DevSpec(f"{p}_tx_trunk", "Waveguide",
                _role_params("wg_trunk", lams[0]), "wg_trunk",
                chain_base, oe, ch, -1)
    specs.append(d)
    tx.append(d.id)
    k += 1
    for li, lam in enumerate(lams):
        for role in _TX_LANE_ROLES:
            d = DevSpec(f"{p}_tx_l{li}_{role}", ROLE_KIND[role],
                        _role_params(role, lam), role,
                        chain_base, oe, ch, li, lam)
            specs.append(d)
            tx.append(d.id)
            k += 1
    d = DevSpec(f"{p}_gc_tx", "GratingCoupler", _role_params("gc_tx", lams[0]),
                "gc_tx", chain_base, oe, ch, -1)
    specs.append(d)
    tx.append(d.id)
    k += 1

    # ── Rx 链（接收）：输入光栅 → 主干 → [波长 lane × n_lane] ──
    rx: List[str] = []
    d = DevSpec(f"{p}_gc_rx", "GratingCoupler", _role_params("gc_rx", lams[0]),
                "gc_rx", chain_base + 1, oe, ch, -1)
    specs.append(d)
    rx.append(d.id)
    k += 1
    d = DevSpec(f"{p}_rx_trunk", "Waveguide", _role_params("wg_trunk", lams[0]),
                "wg_trunk", chain_base + 1, oe, ch, -1)
    specs.append(d)
    rx.append(d.id)
    k += 1
    for li, lam in enumerate(lams):
        for role in _RX_LANE_ROLES:
            d = DevSpec(f"{p}_rx_l{li}_{role}", ROLE_KIND[role],
                        _role_params(role, lam), role,
                        chain_base + 1, oe, ch, li, lam)
            specs.append(d)
            rx.append(d.id)
            k += 1
    return specs, [tx, rx]


def build_cpo_array_specs(cfg: Optional[CPOArrayConfig] = None
                          ) -> Tuple[List[DevSpec], List[List[str]]]:
    """生成整个阵列的器件清单与光路划分（不建 LinkModel，便于统计/校验）。"""
    cfg = cfg or CPOArrayConfig()
    cfg.validate()
    all_specs: List[DevSpec] = []
    chains: List[List[str]] = []
    dev_base = 0
    for oe in range(cfg.n_oe):
        for ch in range(cfg.n_ch):
            specs, ch_chains = _channel_specs(cfg, oe, ch, len(chains),
                                              dev_base)
            all_specs.extend(specs)
            chains.extend(ch_chains)
            dev_base += len(specs)
    return all_specs, chains


# ── 放置 ──────────────────────────────────────────────────────────────
def _pitch(specs: Sequence[DevSpec], margin: float) -> Tuple[float, float]:
    """由器件几何反解网格 pitch（保证行内连接不回折 + 器件不重叠）。

    pitch_x 取两个下界的最大值：
      (a) 2·max_hw + margin            → 相邻器件 body 不重叠；
      (b) max(out_dx) − min(in_dx) + 6 → 任意「前一级 out → 后一级 in」
          的连线长度为正（不向左回折 —— 回折会穿越前级 body 并与
          相邻段共线，是同层短路的温床）。
    """
    max_hw = max(device_bbox(s.kind, dict(s.params))[0] for s in specs)
    max_hh = max(device_bbox(s.kind, dict(s.params))[1] for s in specs)
    max_out_dx = max(port_anchor(s.kind, _out_port(s.kind),
                                 dict(s.params))[0] for s in specs)
    min_in_dx = min(port_anchor(s.kind, _in_port(s.kind),
                                dict(s.params))[0] for s in specs)
    pitch_x = max(2.0 * max_hw + margin, max_out_dx - min_in_dx + 6.0)
    pitch_y = 2.0 * max_hh + margin
    return pitch_x, pitch_y


def _in_dy(s: DevSpec) -> float:
    return port_anchor(s.kind, _in_port(s.kind), dict(s.params))[1]


def _out_dy(s: DevSpec) -> float:
    return port_anchor(s.kind, _out_port(s.kind), dict(s.params))[1]


def place_cpo_array(specs: Sequence[DevSpec], chains: Sequence[Sequence[str]],
                    cfg: CPOArrayConfig) -> Tuple[Dict[str, Tuple[float, float, float]],
                                                  Tuple[float, float]]:
    """端口线对齐的网格放置（零跳线几何的基石）。

    链首器件按 **out 端口** 补偿 y，非链首按 **in 端口** 补偿 →
    同一行所有「行内连接端口」落在同一条水平线上（y = row · pitch_y）。
    于是行内连接退化为纯水平段（无垂直段 → 无跨行垂落 → 零短路风险）。
    """
    pitch_x, pitch_y = _pitch(specs, cfg.pitch_margin_um)
    by_id = {s.id: s for s in specs}
    chain_head = {c[0]: i for i, c in enumerate(chains) if c}
    placement: Dict[str, Tuple[float, float, float]] = {}
    for idx, s in enumerate(specs):
        row, col = divmod(idx, cfg.cols)
        # 链首用 out 端口对齐（其后连接从 out 出发），其余用 in 端口对齐
        dy = _out_dy(s) if s.id in chain_head else _in_dy(s)
        placement[s.id] = (col * pitch_x, row * pitch_y - dy, 0.0)
    return placement, (pitch_x, pitch_y)


# ── 构建 + 布线 ───────────────────────────────────────────────────────
def build_cpo_array_case(cfg: Optional[CPOArrayConfig] = None
                         ) -> Tuple[LinkModel, Dict[str, Any], Dict[str, Any],
                                    Dict[str, Any]]:
    """构建 CPO 光引擎阵列（器件 + 放置 + 布线 + 元信息）。

    返回 (link, placement, routes, meta)。routes 为单层 M1 直连
    （{net_id: RouteResult}）——见模块 docstring「几何策略」。
    """
    cfg = cfg or CPOArrayConfig()
    cfg.validate()
    specs, chains = build_cpo_array_specs(cfg)

    link = LinkModel(name=f"{cfg.name}_{cfg.n_devices}")
    for s in specs:
        link.add_device(s.id, s.kind, dict(s.params),
                        ports=list(_PORTS[s.kind]))

    # 链内串行连接（每条链 = 一条独立光路）
    kind = {s.id: s.kind for s in specs}          # O(1) 查表（禁 O(n) 线性查找）
    t0 = _now()
    for ci, chain in enumerate(chains):
        for a, b in zip(chain, chain[1:]):
            link.connect(f"net_{ci}_{a}__{b}", a, _out_port(kind[a]),
                         b, _in_port(kind[b]))
    # 外部 IO：
    #   Tx 链首（波导主干）← 外部激光源 ELS 馈入；Tx 链尾 GC 的 fib → 光纤输出
    #   Rx 链首 GC 的 fib ← 光纤输入；Rx 链尾（探测器馈线）→ 探测器（黑箱）
    for ci, chain in enumerate(chains):
        head, tail = chain[0], chain[-1]
        link.mark_source(head, _io_port(kind[head], True),
                         net_id=f"io_src_{ci}")
        link.external_io(f"io_sink_{ci}", tail, _io_port(kind[tail], False))
    t_link = _now() - t0

    placement, (pitch_x, pitch_y) = place_cpo_array(specs, chains, cfg)

    # 布线：全部行内同链 → 纯水平 M1 直连（route_net 无障碍快路径）
    t0 = _now()
    routes: Dict[str, Any] = {}
    for ci, chain in enumerate(chains):
        for a, b in zip(chain, chain[1:]):
            net_id = f"net_{ci}_{a}__{b}"
            pa = port_abs(a, _out_port(kind[a]), placement, link)
            pb = port_abs(b, _in_port(kind[b]), placement, link)
            routes[net_id] = route_net(net_id, pa, pb, layer="M1")
    t_route = _now() - t0

    meta = {
        "config": {
            "n_oe": cfg.n_oe, "n_ch": cfg.n_ch, "n_lane": cfg.n_lane,
            "ch_per_row": cfg.ch_per_row, "cols": cfg.cols,
        },
        "n_devices": len(specs),
        "n_chains": len(chains),
        "n_nets": len(link.ir.nets),
        "pitch_um": [round(pitch_x, 3), round(pitch_y, 3)],
        "wavelengths_nm": list(lane_wavelengths(cfg.n_lane)),
        "ring_radii_um": [round(ring_radius_um(l), 4)
                          for l in lane_wavelengths(cfg.n_lane)],
        "n_eff": N_EFF_SOI,
        "ring_order_m": RING_ORDER_M,
        "device_mix": _mix(specs, lambda s: s.kind),
        "role_mix": _mix(specs, lambda s: s.role),
        "time_build_link_s": round(t_link, 3),
        "time_route_s": round(t_route, 3),
    }
    return link, placement, routes, meta


def _mix(specs: Sequence[DevSpec], key) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for s in specs:
        k = key(s)
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def _now() -> float:
    import time
    return time.perf_counter()


# ── 反例（供锚/CI 验证"抓得住"）──────────────────────────────────────
def inject_fault(routes: Dict[str, Any], kind: str = "disconnect") -> str:
    """注入一个故障（返回被破坏的 net_id），用于验证判决抓得住。

    kind:
      'disconnect' —— 删掉中间一条布线（断路 → LVS 应 REJECT）；
      'misroute'   —— 互换相邻两条布线（错连 → LVS 应 REJECT）。
    """
    ids = sorted(routes)
    if len(ids) < 2:
        return ""
    mid = len(ids) // 2
    if kind == "disconnect":
        net = ids[mid]
        del routes[net]
        return net
    if kind == "misroute":
        a, b = ids[mid], ids[mid + 1]
        routes[a], routes[b] = routes[b], routes[a]
        return f"{a}<->{b}"
    raise ValueError(f"未知故障类型 {kind}")


__all__ = [
    "CPOArrayConfig", "DevSpec", "build_cpo_array_case",
    "build_cpo_array_specs", "place_cpo_array", "ring_radius_um",
    "lane_wavelengths", "LAN_WDM_CHANNELS_NM", "ROLE_KIND",
]
