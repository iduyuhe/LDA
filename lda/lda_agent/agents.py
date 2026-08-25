"""LDA P1-M3 · Agent 协议与共享上下文（机器优先、MCP/A2A 风格）。

四个 Agent（链路规划 / 器件综合 / 版图布线 / 验证）通过结构化 AgentMsg 协作，
由 Orchestrator（元编排器）统一调度。所有交互确定性、无状态、无 GUI、无 LLM。

设计纪律（继承 L1 协议层）：
  - 确定性：同请求 → 同结果
  - 可验证：验证 Agent 的锚来自物理定律（无源网络无增益），LLM 不进判决路径
  - 可编排：每个 Agent 暴露 tool_schemas()，可由外部编排器/MCP 调用
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_TRACE: List[Dict[str, Any]] = []


@dataclass
class AgentMsg:
    """Agent 之间的确定性消息信封（A2A 风格）。

    sender/receiver：agent 名（planner/synthesis/layout/verify/orchestrator）
    action         ：该 agent 要执行的子任务
    payload        ：结构化输入
    trace_id       ：端到端追踪号
    """

    sender: str
    receiver: str
    action: str
    payload: Dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""
    msg_id: str = field(default_factory=lambda: "msg-" + uuid.uuid4().hex[:8])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "msg_id": self.msg_id,
            "trace_id": self.trace_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "action": self.action,
            "payload": self.payload,
        }


@dataclass
class DesignContext:
    """贯穿全链路的共享黑板（blackboard）。

    各 Agent 在其阶段写入/读取对应字段；orchestrator 最终序列化输出。
    """

    spec: Dict[str, Any] = field(default_factory=dict)
    trace_id: str = field(default_factory=lambda: "trace-" + uuid.uuid4().hex[:12])

    # 链路规划产
    link: Any = None            # LinkModel
    # 器件综合产
    device_models: Dict[str, Any] = field(default_factory=dict)   # inst_id -> model
    # 版图布线产
    placement: Dict[str, Any] = field(default_factory=dict)
    routes: Dict[str, Any] = field(default_factory=dict)
    net_loss_db: Dict[str, float] = field(default_factory=dict)
    gds_bytes: bytes = b""
    gds_parse: Any = None
    blocked_nets: List[str] = field(default_factory=list)
    # 验证产
    sim: Dict[str, Any] = field(default_factory=dict)
    verification: Dict[str, Any] = field(default_factory=dict)
    # 流程追踪
    steps: List[Dict[str, Any]] = field(default_factory=list)
    trace: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None

    def append_step(self, agent: str, action: str, summary: str,
                    detail: Optional[Dict[str, Any]] = None) -> None:
        self.steps.append({
            "agent": agent,
            "action": action,
            "summary": summary,
            "detail": detail or {},
            "ts": time.time(),
        })

    def record_msg(self, msg: AgentMsg, result: Dict[str, Any]) -> None:
        self.trace.append({"msg": msg.to_dict(), "result": result})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "spec": self.spec,
            "steps": self.steps,
            "device_models": {k: (v if isinstance(v, dict) else str(v))
                              for k, v in self.device_models.items()},
            "placement": self.placement,
            "net_loss_db": self.net_loss_db,
            "blocked_nets": self.blocked_nets,
            "sim": {k: (list(v) if isinstance(v, list) else v)
                    for k, v in self.sim.items()
                    if k not in ("transfers",)},
            "sim_transfers_summary": {
                k: {"len": len(v),
                    "max": float(max(v)) if v else 0.0,
                    "min": float(min(v)) if v else 0.0}
                for k, v in self.sim.get("transfers", {}).items()
            },
            "verification": self.verification,
            "trace": self.trace,
            "artifacts": self.artifacts,
            "error": self.error,
        }


class BaseAgent:
    """Agent 基类：统一 handle(msg, ctx) -> (result_dict, ctx_updates)。

    子类实现 _run；handle 负责封装追踪。"""
    NAME = "base"
    ACTIONS: List[str] = []

    def handle(self, msg: AgentMsg, ctx: DesignContext) -> Dict[str, Any]:
        try:
            result = self._run(msg, ctx)
            ctx.record_msg(msg, result)
            return result
        except Exception as e:  # 结构化错误，不抛给人
            err = {"status": "error", "agent": self.NAME,
                   "action": msg.action, "error": str(e)}
            ctx.record_msg(msg, err)
            return err

    def _run(self, msg: AgentMsg, ctx: DesignContext) -> Dict[str, Any]:
        raise NotImplementedError

    def tool_schemas(self) -> List[Dict[str, Any]]:
        return [{
            "name": f"lda.{self.NAME}",
            "description": f"{self.NAME} agent",
            "input_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object"},
        }]
