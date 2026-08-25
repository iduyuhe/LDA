"""LDA P1-M3 · Agent 元编排器（orchestrator）。

把四个 Agent（链路规划 / 器件综合 / 版图布线 / 验证）用 MCP/A2A 风格消息协作
串成端到端芯片级闭环：

  planner@plan  →  synthesis@synthesize  →  layout@layout  →  verify@verify
        ↓               ↓                      ↓                  ↓
     LinkModel      device_models         placement/routes/    sim +
                                                 gds           物理锚验收

确定性、无状态、无 GUI、无 LLM（验证判决走物理定律锚）。每个 Agent 通过
AgentMsg 协作，orchestrator 仅做调度与上下文黑板维护。

CLI：
  python -m lda_agent.orchestrator --type wdm \
      --channels 1.53,1.55,1.57,1.59 --R 10 --gap 0.3 --kappa 0.05 --out reports_chip
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = os.path.dirname(_HERE)
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)

from .agents import AgentMsg, DesignContext
from .agent_planner import LinkPlannerAgent
from .agent_synthesis import DeviceSynthesisAgent
from .agent_layout import LayoutRoutingAgent
from .agent_verify import VerificationAgent


class Orchestrator:
    """元编排器：调度四 Agent，维护共享 DesignContext 黑板。"""

    def __init__(self):
        self.agents = {
            "planner": LinkPlannerAgent(),
            "synthesis": DeviceSynthesisAgent(),
            "layout": LayoutRoutingAgent(),
            "verify": VerificationAgent(),
        }

    def run(self, spec: Dict[str, Any],
            layout_opts: Optional[Dict[str, Any]] = None,
            out_dir: Optional[str] = None) -> DesignContext:
        ctx = DesignContext(spec=spec)
        layout_opts = layout_opts or {}

        # 1) 链路规划
        self._dispatch(ctx, "planner", "plan_wdm" if spec.get("type") == "wdm"
                       else "plan_generic", {"spec": spec})
        # 2) 器件综合
        self._dispatch(ctx, "synthesis", "synthesize", {})
        # 3) 版图布线
        self._dispatch(ctx, "layout", "layout", layout_opts)
        # 4) 验证
        self._dispatch(ctx, "verify", "verify", {})

        # 落盘（GDS + 系统报告）
        if out_dir:
            self._persist(ctx, out_dir)
        return ctx

    def _dispatch(self, ctx: DesignContext, receiver: str, action: str,
                  payload: Dict[str, Any]) -> Dict[str, Any]:
        msg = AgentMsg(sender="orchestrator", receiver=receiver,
                       action=action, payload=payload, trace_id=ctx.trace_id)
        agent = self.agents[receiver]
        return agent.handle(msg, ctx)

    def _persist(self, ctx: DesignContext, out_dir: str) -> None:
        os.makedirs(out_dir, exist_ok=True)
        # GDS
        gds_path = os.path.join(out_dir, "chip.gds")
        with open(gds_path, "wb") as f:
            f.write(ctx.gds_bytes)
        # 系统报告
        report = ctx.to_dict()
        report["accepted"] = (ctx.verification.get("status") == "ok")
        report_path = os.path.join(out_dir, "chip_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        ctx.artifacts = {"gds": gds_path, "report": report_path}

    # ---- 对外工具声明（MCP 风格，与 L1 KernelGateway.tool_schemas 同构）----
    def tool_schemas(self) -> List[Dict[str, Any]]:
        out = [{
            "name": "lda.orchestrate_link",
            "description": "元编排四 Agent 端到端完成芯片级链路设计："
                           "规划→综合→布线→验证，返回结构化 DesignContext。",
            "input_schema": {
                "type": "object",
                "properties": {
                    "spec": {"type": "object",
                             "description": "链路设计意图（type=wdm 或通用 instances/nets）"},
                    "layout_opts": {"type": "object",
                                    "description": "版图选项：wg_width/bend_radius/corner"},
                    "out_dir": {"type": "string",
                                "description": "落盘目录（GDS + 报告）"},
                },
                "required": ["spec"],
            },
            "output_schema": {"type": "object"},
        }]
        for a in self.agents.values():
            out.extend(a.tool_schemas())
        return out


def main() -> int:
    ap = argparse.ArgumentParser(description="LDA P1-M3 芯片级链路设计元编排器")
    ap.add_argument("--type", default="wdm", choices=["wdm", "generic"])
    ap.add_argument("--channels", default="1.53,1.55,1.57,1.59",
                    help="WDM 信道波长(µm)，逗号分隔")
    ap.add_argument("--R", type=float, default=10.0, help="基础环半径(µm)")
    ap.add_argument("--gap", type=float, default=0.3, help="环-总线间隙(µm)")
    ap.add_argument("--kappa", type=float, default=0.05, help="耦合系数")
    ap.add_argument("--alpha_cm", type=float, default=2.5, help="波导损耗(dB/cm)")
    ap.add_argument("--wg_width", type=float, default=0.5)
    ap.add_argument("--bend_radius", type=float, default=5.0)
    ap.add_argument("--out", default=None, help="落盘目录")
    args = ap.parse_args()

    if args.type == "wdm":
        channels = [float(x) for x in args.channels.split(",")]
        spec = {
            "type": "wdm",
            "channels_um": channels,
            "R_um": args.R,
            "gap_um": args.gap,
            "kappa": args.kappa,
            "alpha_cm": args.alpha_cm,
        }
    else:
        spec = {"type": "generic", "instances": [], "nets": [], "sources": []}

    ctx = Orchestrator().run(
        spec,
        layout_opts={"wg_width": args.wg_width,
                     "bend_radius": args.bend_radius},
        out_dir=args.out,
    )
    print(json.dumps(ctx.to_dict(), ensure_ascii=False, indent=2))
    return 0 if ctx.verification.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
