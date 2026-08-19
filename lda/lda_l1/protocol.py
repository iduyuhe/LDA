"""LDA L1 · agent 协议层（参考实现）。

机器优先（machine-first）协议：agent 之间、agent 与 L3 内核之间用确定性消息交互，
不依赖 GUI、不依赖人逐步确认。KernelGateway 把一条 AgentRequest 翻译为
「L0 IR → L3 candidate → harness → AgentResponse」的确定性调用链。

设计原则（《白皮书》§11/§12、设计前置文献梳理 P0）：
  - 确定性：同请求 → 同结果，无随机、无状态、无交互。
  - 可验证：harness 的黄金参考来自非 AI 的物理定律锚。
  - 无交互：不弹窗、不等人、不给人看 GUI；只回结构化 AgentResponse。
  - 可编排：对外的 tool_schemas() 暴露 MCP 风格工具，供任意外部 agent/LLM 调用。
"""
from __future__ import annotations

import json
import os
import time
import uuid

from lda_harness.harness import (
    VerificationHarness, ReferenceCandidate, PerturbedCandidate,
)
from lda_harness.benchmarks import BENCHMARK_DEFS
from lda_harness.l3_ai_solver import L3AISolverCandidate
from lda_harness import report as rep


# --------------------------------------------------------------------------
# 消息信封（machine-first）
# --------------------------------------------------------------------------
class AgentRequest:
    """agent 发给 L1 协议层的请求。

    action:
      - verify_design  / run_candidate : 驱动 L3 candidate + harness 验证
      - list_benchmarks                  : 列出标准题库定义
    payload.candidate.type: reference | perturbed | l3_ai
    """

    def __init__(self, action, payload=None, meta=None, request_id=None):
        self.request_id = request_id or ("req-" + uuid.uuid4().hex[:12])
        self.action = action
        self.payload = payload or {}
        self.meta = meta or {}

    def to_dict(self):
        return {
            "request_id": self.request_id,
            "action": self.action,
            "payload": self.payload,
            "meta": self.meta,
        }


class AgentResponse:
    """L1 协议层回给 agent 的结构化结果。

    status: ok（全 PASS）/ fail（有 FAIL，但流程成功）/ error（异常）
    """

    def __init__(self, request_id, status, result=None, artifacts=None, error=None):
        self.request_id = request_id
        self.status = status
        self.result = result or {}
        self.artifacts = artifacts or {}
        self.error = error

    def to_dict(self):
        return {
            "request_id": self.request_id,
            "status": self.status,
            "result": self.result,
            "artifacts": self.artifacts,
            "error": self.error,
        }

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------
# 请求处理器（核心：人操作壳 → agent 操作接口 的翻译）
# --------------------------------------------------------------------------
class KernelGateway:
    """L1 协议层核心。

    对外暴露确定性原语；对内把请求路由到 L0 IR 解析、L3 candidate 构建、
    harness 运行、报告生成。整个链路无交互、可复现。
    """

    def __init__(self, defs=None, out_dir="reports_l1"):
        self.defs = defs or BENCHMARK_DEFS
        self.harness = VerificationHarness(self.defs)
        self.out_dir = out_dir

    # ---- candidate 构造（L3 接口适配）---------------------------------
    @staticmethod
    def _build_candidate(spec):
        t = (spec or {}).get("type", "reference")
        if t == "reference":
            return ReferenceCandidate()
        if t == "perturbed":
            return PerturbedCandidate((spec or {}).get("rel_err", 0.0))
        if t == "l3_ai":
            return L3AISolverCandidate()
        raise ValueError(f"未知 candidate 类型: {t}")

    # ---- 入口 ----------------------------------------------------------
    def handle(self, req: AgentRequest) -> AgentResponse:
        try:
            if req.action == "list_benchmarks":
                return self._list_benchmarks(req)
            if req.action in ("verify_design", "run_candidate"):
                return self._verify(req)
            return AgentResponse(req.request_id, "error",
                                 error=f"未知 action: {req.action}")
        except Exception as e:  # 结构化错误，不抛给人
            return AgentResponse(req.request_id, "error", error=str(e))

    # ---- verify_design / run_candidate --------------------------------
    def _verify(self, req: AgentRequest) -> AgentResponse:
        payload = req.payload
        l0_ir = payload.get("l0_ir")
        candidate = self._build_candidate(payload.get("candidate", {}))

        specs = self.harness.resolve_specs(l0_ir)
        wanted = payload.get("benchmarks")
        if wanted:
            specs = [s for s in specs if s["id"] in wanted]

        results = self.harness.run(specs, candidate)
        passed = sum(1 for r in results if r.passed)

        meta = {
            "L0_IR": (l0_ir.get("lda_version", "(内置默认)") if l0_ir
                      else "(内置默认)"),
            "candidate": type(candidate).__name__,
            "oracle": "确定性物理定律锚（analytical/EIM/Airy/Rayleigh）",
            "via": "L1 KernelGateway",
        }
        os.makedirs(self.out_dir, exist_ok=True)
        md_path = os.path.join(self.out_dir, "verification_report.md")
        json_path = os.path.join(self.out_dir, "verification_report.json")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(rep.format_markdown(results, meta))
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(rep.format_json(results, meta))

        details = [
            {"id": r.bid, "metric": r.metric, "golden": r.golden,
             "candidate": r.candidate, "tol": r.tol, "passed": r.passed,
             "oracle": r.oracle}
            for r in results
        ]
        status = "ok" if passed == len(results) else "fail"
        return AgentResponse(
            req.request_id, status,
            result={"summary": {"total": len(results), "passed": passed},
                    "details": details},
            artifacts={"report_md": md_path, "report_json": json_path},
        )

    # ---- list_benchmarks ----------------------------------------------
    def _list_benchmarks(self, req: AgentRequest) -> AgentResponse:
        items = [
            {"id": k, "metric": d["metric"], "oracle": d["oracle"], "tol": d["tol"]}
            for k, d in sorted(self.defs.items())
        ]
        return AgentResponse(req.request_id, "ok",
                             result={"benchmarks": items})

    # ---- 对外工具声明（MCP 风格，供外部 agent/LLM 调用）---------------
    def tool_schemas(self):
        return [
            {
                "name": "lda.verify_design",
                "description": "用确定性物理定律锚验证 L0 IR 设计：驱动 L3 candidate + harness，"
                               "返回结构化 AgentResponse（summary/details/artifacts）。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "l0_ir": {"type": "object",
                                  "description": "L0 IR 对象（可选，缺省用内置默认题库）"},
                        "candidate": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string",
                                         "enum": ["reference", "perturbed", "l3_ai"]},
                                "rel_err": {"type": "number",
                                            "description": "perturbed 模式的相对扰动"}
                            },
                            "required": ["type"]
                        },
                        "benchmarks": {"type": "array", "items": {"type": "string"},
                                       "description": "仅验证指定题号，如 ['B1','B2']"}
                    },
                    "required": ["candidate"]
                },
                "output_schema": {"type": "object"}
            },
            {
                "name": "lda.list_benchmarks",
                "description": "列出全部标准题 B1–Bn 的定义（指标/ORACLE/容差）。",
                "input_schema": {"type": "object", "properties": {}},
                "output_schema": {"type": "object"}
            },
        ]
