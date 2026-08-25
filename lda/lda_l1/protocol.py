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

# P1-M3：链路级原语（消费 lda_chain / lda_layout，与 verify_design 同构）
from lda_chain import LinkModel, simulate as _chain_simulate
from lda_chain.photon_link import build_wdm_link
from lda_chain.route_sim import layout_only
from lda_layout.router import route_net
from lda_layout.placement import place_row


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
        # D-62 实证锚注入：L1 agent 验证链路默认携带第二道非 AI ground
        # （seed_empirical.json + 社区落库增量 empirical_contributions.json）。
        # 语料缺失/损坏时 anchor=None → E 题诚实降级（empirical-missing 不判 PASS）。
        anchor = None
        try:
            from lda_harness.verification_adapters import _load_empirical_anchor
            anchor = _load_empirical_anchor()
        except Exception:
            anchor = None
        self.harness = VerificationHarness(self.defs, anchor=anchor)
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
            # P1-M3 链路级原语
            if req.action == "link_simulate":
                return self._link_simulate(req)
            if req.action == "route":
                return self._route(req)
            if req.action == "place":
                return self._place(req)
            if req.action == "export_chip_gds":
                return self._export_chip_gds(req)
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

    # ---- P1-M3 链路级原语 --------------------------------------------
    @staticmethod
    def _build_link_from_spec(spec: dict) -> LinkModel:
        """把链路设计意图（spec）翻译为通用 LinkModel（与 orchestrator 同源）。"""
        stype = (spec or {}).get("type", "generic")
        if stype == "wdm":
            channels_um = spec["channels_um"]
            channels_nm = [float(c) * 1000.0 for c in channels_um]
            gap = float(spec.get("gap_um", 0.3))
            n_g = float(spec.get("n_g", 4.2))
            Rs = spec.get("Rs_um")
            if Rs is None:
                from lda_agent.wdm_system import inverse_ring_for_channel
                Rs = [inverse_ring_for_channel(c * 1e-3, n_g) for c in channels_um]
            link = build_wdm_link(channels_nm, [float(r) for r in Rs],
                                  gap=gap, n_g=n_g)
            link.link_params = {
                "wl0_um": float(spec.get("wl0_um", 1.55)),
                "span_um": float(spec.get("span_um", 0.06)),
                "n_samples": int(spec.get("n_samples", 61)),
                "gap": gap,
            }
            return link
        # 通用实例/互连
        link = LinkModel()
        for inst in spec.get("instances", []):
            link.add_device(inst["id"], inst["kind"],
                            {k: float(v) for k, v in inst.get("params", {}).items()})
        for net in spec.get("nets", []):
            link.connect(*[tuple(c.split(".", 1)) for c in net["connects"]])
        for s in spec.get("sources", []):
            i, p = tuple(s.split(".", 1))
            link.mark_source(i, p)
        return link

    def _link_simulate(self, req: AgentRequest) -> AgentResponse:
        """链路级联仿真原语：spec → LinkModel → lda_chain.simulate。"""
        spec = req.payload.get("spec") or {}
        link = self._build_link_from_spec(spec)
        link.validate()
        wls = req.payload.get("wavelengths_um")
        if not wls:
            # 与 orchestrator/agents 同构：从 link_params 构造完整波长网格
            lp = link.link_params or {}
            wl0 = float(lp.get("wl0_um", 1.55))
            span = float(lp.get("span_um", 0.06))
            n = int(lp.get("n_samples", 61))
            wls = [wl0 - span / 2.0 + span * i / (n - 1) for i in range(n)]
        sim = _chain_simulate(link, list(wls),
                              net_loss_db=req.payload.get("net_loss_db"))
        return AgentResponse(
            req.request_id, "ok",
            result={"n_inst": len(link.ir.components),
                    "transfers": {k: [round(v, 6) for v in vec]
                                  for k, vec in sim["transfers"].items()},
                    "missing_models": sim["missing_models"],
                    "note": sim["note"]},
        )

    def _route(self, req: AgentRequest) -> AgentResponse:
        """单 net 自动布线原语：src/dst/obstacles → route_net。"""
        p = req.payload
        src = tuple(p["src"])
        dst = tuple(p["dst"])
        obstacles = [tuple(o) for o in p.get("obstacles", [])]
        rr = route_net(p.get("net_id", "net"),
                       src, dst, obstacles=obstacles,
                       wg_width=float(p.get("wg_width", 0.5)),
                       bend_radius=float(p.get("bend_radius", 5.0)),
                       corner=p.get("corner", "round"),
                       straight_loss_db_cm=float(p.get("straight_loss_db_cm", 2.5)))
        return AgentResponse(
            req.request_id, "ok" if not rr.blocked else "fail",
            result={"n_points": len(rr.points_um),
                    "n_bends": rr.n_bends,
                    "total_loss_db": round(rr.total_loss_db, 6),
                    "straight_um": round(rr.straight_um, 3),
                    "bend_loss_db": round(rr.bend_loss_db, 6),
                    "straight_loss_db": round(rr.straight_loss_db, 6),
                    "blocked": rr.blocked},
        )

    def _place(self, req: AgentRequest) -> AgentResponse:
        """器件放置原语：spec → LinkModel → place_row。"""
        spec = req.payload.get("spec") or {}
        link = self._build_link_from_spec(spec)
        placement = place_row(link, pitch_x=req.payload.get("pitch_x"))
        return AgentResponse(
            req.request_id, "ok",
            result={"placement": {k: [round(v, 3) for v in c]
                                  for k, c in placement.items()},
                    "n_inst": len(placement)},
        )

    def _export_chip_gds(self, req: AgentRequest) -> AgentResponse:
        """整芯片 GDS 导出原语：spec → layout_only（放置+布线+GDS）。"""
        spec = req.payload.get("spec") or {}
        link = self._build_link_from_spec(spec)
        lo = layout_only(link,
                         wg_width=float(req.payload.get("wg_width", 0.5)),
                         bend_radius=float(req.payload.get("bend_radius", 5.0)),
                         corner=req.payload.get("corner", "round"),
                         pitch_x=req.payload.get("pitch_x"),
                         straight_loss_db_cm=float(
                             req.payload.get("straight_loss_db_cm", 2.5)))
        parse = lo["gds_parse"]
        return AgentResponse(
            req.request_id, "ok" if not lo["blocked_nets"] else "partial",
            result={"n_structs": parse.get("n_structures") if isinstance(parse, dict) else None,
                    "n_routed": len(lo["routes"]),
                    "total_loss_db": round(sum(lo["net_loss_db"].values()), 6),
                    "blocked_nets": lo["blocked_nets"],
                    "gds_bytes_len": len(lo["gds_bytes"])},
            artifacts={"gds_bytes": lo["gds_bytes"]},
        )

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
            # ---- P1-M3 链路级原语 ----
            {
                "name": "lda.link_simulate",
                "description": "链路级联仿真：spec（type=wdm 或通用实例/互连）→ LinkModel "
                               "→ lda_chain.simulate，返回各端口传递谱与缺模型清单。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "spec": {"type": "object",
                                 "description": "链路设计意图（channels_um/R_um/gap_um/... 或 instances/nets/sources）"},
                        "wavelengths_um": {"type": "array", "items": {"type": "number"},
                                           "description": "波长列表(µm)，缺省用 link_params"},
                        "net_loss_db": {"type": "object",
                                        "description": "可选 net→损耗(dB) 覆盖"}
                    },
                    "required": ["spec"]
                },
                "output_schema": {"type": "object"}
            },
            {
                "name": "lda.route",
                "description": "单 net 自动布线（C级自写）：src/dst/obstacles → 曼哈顿+圆角走线，"
                               "返回点数/弯曲数/损耗/避障状态。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "src": {"type": "array", "items": {"type": "number"}},
                        "dst": {"type": "array", "items": {"type": "number"}},
                        "obstacles": {"type": "array", "items": {"type": "array"}},
                        "wg_width": {"type": "number"}, "bend_radius": {"type": "number"},
                        "corner": {"type": "string"}, "straight_loss_db_cm": {"type": "number"}
                    },
                    "required": ["src", "dst"]
                },
                "output_schema": {"type": "object"}
            },
            {
                "name": "lda.place",
                "description": "器件放置：spec → LinkModel → place_row，返回各实例坐标。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "spec": {"type": "object"},
                        "pitch_x": {"type": "number"}
                    },
                    "required": ["spec"]
                },
                "output_schema": {"type": "object"}
            },
            {
                "name": "lda.export_chip_gds",
                "description": "整芯片 GDS 导出：spec → 放置+自动布线+GDSII（round-trip 可解析），"
                               "返回结构数/布线数/总损耗/blocked。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "spec": {"type": "object"},
                        "wg_width": {"type": "number"}, "bend_radius": {"type": "number"},
                        "corner": {"type": "string"}, "straight_loss_db_cm": {"type": "number"}
                    },
                    "required": ["spec"]
                },
                "output_schema": {"type": "object"}
            },
        ]
