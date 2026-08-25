"""LDA P1-M1 · 光子链路 MVP 骨架（photon link builder）。

把 wdm_system 的 WDM 多环级联「专用脚本逻辑」收敛为通用 LinkModel 构造器，
作为光子链路范例（plan：保留 wdm_system 作旧范例，新通用框架以 lda_chain 为
准）。后续 M2 自动布线、M3 Agent 编排都将消费 LinkModel。

  验证锚点：build_wdm_link 构造的链路经 lda_chain.engine.simulate 级联，结果
  须与 wdm_system.system_metrics 完全一致（同一 adddrop_spectrum 模型、同一
  级联公式的通用化表达）。
"""
from __future__ import annotations

from typing import List, Optional

from lda_ir import ObjectiveSpec

from .link_model import LinkModel


def build_wdm_link(channels_nm: List[float], Rs: List[float],
                   gap: float = 0.3, n_g: float = 4.2) -> LinkModel:
    """N 环 WDM 级联链路（通用 LinkModel 表达）。

    拓扑：一条 bus 链 ring_i.out → ring_{i+1}.in；每个 ring 的 drop 为外部
    输出端口；ring0.in 为唯一输入源。
    """
    link = LinkModel(domain="photon", name="wdm-N-ring",
                     notes=f"WDM {len(channels_nm)} 信道级联（通用链路框架）")
    for i, (lam, R) in enumerate(zip(channels_nm, Rs)):
        link.add_device(f"ring{i}", "RingResonator",
                        params={"R": float(R), "n_g": n_g, "gap": gap},
                        ports=["in", "out", "drop"])
    # bus 链内部互连
    for i in range(len(Rs) - 1):
        link.connect(f"bus{i}", f"ring{i}", "out", f"ring{i + 1}", "in")
    # 设计意图：每环 FSR 目标（与 wdm_system.build_wdm_ir 同构，过 IR.validate）
    from lda_agent.wdm_system import fsr_nm
    for i, (lam, R) in enumerate(zip(channels_nm, Rs)):
        link.ir.objectives.append(
            ObjectiveSpec(bid="B4", target=round(fsr_nm(lam, R, n_g), 3),
                          tol=1e-3, role="objective"))
    # 外部 IO：输入源 + 每环 drop 输出 + 末环 thru 输出
    link.mark_source("ring0", "in")
    for i in range(len(Rs)):
        link.external_io(f"drop{i}", f"ring{i}", "drop")
    link.external_io(f"thru{len(Rs) - 1}", f"ring{len(Rs) - 1}", "out")
    return link


def build_wdm_link_from_channels(channels_nm: List[float], gap: float = 0.3,
                                 n_g: float = 4.2, m: int = 170
                                 ) -> LinkModel:
    """从信道波长直接构造 WDM 链路（闭式逆设计每环半径 R=m·λ/(2π·n_g)）。"""
    from lda_agent.wdm_system import inverse_ring_for_channel
    channels_nm = sorted(float(c) for c in channels_nm)
    Rs = [inverse_ring_for_channel(c * 1e-3, n_g, m) for c in channels_nm]
    return build_wdm_link(channels_nm, Rs, gap=gap, n_g=n_g)
