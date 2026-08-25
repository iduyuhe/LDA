"""LDA P1-M3 · 版图布线 Agent（layout）。

把 LinkModel 落地为几何版图：放置（place_row）→ 自动布线（route_net，
含弯曲/直波导损耗）→ 整芯片 GDSII（round-trip 可解析）。

复用 P1-M2 资产（lda_chain.route_sim.layout_only），不重复造轮子。
产出：ctx.placement / routes / net_loss_db / gds_bytes / gds_parse / blocked_nets。
"""
from __future__ import annotations

from typing import Any, Dict

from .agents import AgentMsg, BaseAgent, DesignContext
from lda_chain.route_sim import layout_only


class LayoutRoutingAgent(BaseAgent):
    NAME = "layout"
    ACTIONS = ["layout"]

    def _run(self, msg: AgentMsg, ctx: DesignContext) -> Dict[str, Any]:
        if ctx.link is None:
            raise RuntimeError("链路规划未执行：ctx.link 为空")
        p = msg.payload
        lo = layout_only(
            ctx.link,
            wg_width=float(p.get("wg_width", 0.5)),
            bend_radius=float(p.get("bend_radius", 5.0)),
            corner=p.get("corner", "round"),
            pitch_x=p.get("pitch_x"),
            straight_loss_db_cm=float(p.get("straight_loss_db_cm", 2.5)),
        )
        ctx.placement = lo["placement"]
        ctx.routes = {k: _route_summary(v) for k, v in lo["routes"].items()}
        ctx.net_loss_db = lo["net_loss_db"]
        ctx.gds_bytes = lo["gds_bytes"]
        ctx.gds_parse = lo["gds_parse"]
        ctx.blocked_nets = lo["blocked_nets"]

        total_routed = len(lo["routes"])
        total_loss = sum(lo["net_loss_db"].values())
        summary = (f"版图布线：{total_routed} 条 net 布线，总损耗 {total_loss:.4f} dB"
                   + (f"；⚠ 未避障 {len(lo['blocked_nets'])} 条"
                      if lo["blocked_nets"] else "；全部成功避障"))
        ctx.append_step(self.NAME, msg.action, summary,
                        {"n_routed": total_routed,
                         "total_loss_db": round(total_loss, 6),
                        "blocked": lo["blocked_nets"],
                        "gds_structs": (lo["gds_parse"].get("n_structures")
                                         if isinstance(lo["gds_parse"], dict)
                                         else None)})
        return {"status": "ok" if not lo["blocked_nets"] else "partial",
                "n_routed": total_routed,
                "total_loss_db": round(total_loss, 6),
                "blocked": lo["blocked_nets"]}


def _route_summary(rr) -> Dict[str, Any]:
    return {
        "n_points": len(getattr(rr, "points_um", [])),
        "n_bends": getattr(rr, "n_bends", 0),
        "total_loss_db": round(getattr(rr, "total_loss_db", 0.0), 6),
        "straight_len_um": round(getattr(rr, "straight_len_um", 0.0), 3),
        "bend_len_um": round(getattr(rr, "bend_len_um", 0.0), 3),
        "blocked": getattr(rr, "blocked", False),
    }
