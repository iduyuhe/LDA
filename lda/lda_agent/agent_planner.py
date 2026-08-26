"""LDA P1-M3 · 链路规划 Agent（planner）。

把高层「链路设计意图」翻译为通用 LinkModel（L0 IR 的链路门面）：
  - WDM 多信道级联（委托 lda_chain.build_wdm_link）
  - 通用实例/互连描述（instances + nets + sources）

产出：ctx.link（LinkModel，已 IR.validate 通过），并标记输入源。
"""
from __future__ import annotations

from typing import Any, Dict, List

from .agents import AgentMsg, BaseAgent, DesignContext
from lda_chain import LinkModel
from lda_chain.photon_link import build_wdm_link


class LinkPlannerAgent(BaseAgent):
    NAME = "planner"
    ACTIONS = ["plan_wdm", "plan_generic"]

    def _run(self, msg: AgentMsg, ctx: DesignContext) -> Dict[str, Any]:
        spec = msg.payload.get("spec") or ctx.spec
        ctx.spec = spec
        stype = spec.get("type", "generic")

        if stype == "wdm":
            link = self._plan_wdm(spec)
            summary = (f"WDM 链路规划：{len(link.ir.components)} 实例 / "
                       f"{len(link.ir.nets)} 互连，输入源 {link.sources}")
        else:
            link = self._plan_generic(spec)
            summary = (f"通用链路规划：{len(link.ir.components)} 实例 / "
                       f"{len(link.ir.nets)} 互连，输入源 {link.sources}")

        link.validate()  # 复用现有 IR 硬校验
        ctx.link = link
        ctx.append_step(self.NAME, msg.action, summary,
                        {"n_inst": len(link.ir.components),
                         "n_nets": len(link.ir.nets),
                         "sources": list(link.sources)})
        return {"status": "ok", "n_inst": len(link.ir.components),
                "n_nets": len(link.ir.nets), "sources": list(link.sources)}

    @staticmethod
    def _plan_wdm(spec: Dict[str, Any]) -> LinkModel:
        channels_um = spec["channels_um"]
        channels_nm = [float(c) * 1000.0 for c in channels_um]
        gap = float(spec.get("gap_um", 0.3))
        n_g = float(spec.get("n_g", 4.2))
        Rs = spec.get("Rs_um")
        if Rs is None:
            # 缺省：闭式逆设计每环半径（与 M1 smoke 同源）
            from lda_agent.wdm_system import inverse_ring_for_channel
            Rs = [inverse_ring_for_channel(c * 1e-3, n_g) for c in channels_um]
        link = build_wdm_link(channels_nm, [float(r) for r in Rs],
                              gap=gap, n_g=n_g)
        # 链路级共享参数（波长采样网格 + 共享 gap）；kappa 由 gap 决定（registry 派生）
        link.link_params = {
            "wl0_um": float(spec.get("wl0_um", 1.55)),
            "span_um": float(spec.get("span_um", 0.06)),
            "n_samples": int(spec.get("n_samples", 61)),
            "gap": gap,
        }
        return link

    @staticmethod
    def _plan_generic(spec: Dict[str, Any]) -> LinkModel:
        link = LinkModel()
        for inst in spec.get("instances", []):
            link.add_device(
                inst["id"], inst["kind"],
                {k: float(v) for k, v in inst.get("params", {}).items()},
            )
        for net in spec.get("nets", []):
            # net: {"id":.., "connects":["i0.p0","i1.p1"]} → connect(net_id, src, src_port, dst, dst_port)
            src, dst = net["connects"]
            si, sp = src.split(".", 1)
            di, dp = dst.split(".", 1)
            link.connect(net["id"], si, sp, di, dp)
        for s in spec.get("sources", []):
            i, p = tuple(s.split(".", 1))
            link.mark_source(i, p)
        for s in spec.get("sinks", []):
            # 输出端口显式声明为外部 IO（单端口 net 悬挂端口）
            i, p = tuple(s.split(".", 1))
            link.external_io(f"sink_{i}_{p}", i, p)
        return link
