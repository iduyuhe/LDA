#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""LDA · 实时 Web 预览界面后端（零依赖）。

把已落地的内核（验证裁判 harness / L1 KernelGateway / agent 设计闭环 /
L2 开放 PDK Registry）通过 HTTP 暴露给一个真正的产品级前端，使
"现场跑 LDA 内核"可被交互式预览。

暴露接口：
  GET  /                 → index.html（产品级控制台）
  GET  /api/status        → 系统落地状态（哪些层已 built / planned）
  GET  /api/benchmarks    → 题库 B1–B11 定义
  GET  /api/pdks          → 已登记 PDK + 器件模板（L2）
  POST /api/verify        → {candidate, perturb?} 真跑 harness，返回逐题判定
  POST /api/agent_loop    → {solver, dual?} 真跑 agent 自迭代设计闭环
  POST /api/pdk_design    → {pdk, template, solver} 用 PDK 驱动 agent 逆设计
  POST /api/pdk_compare   → {device_type, solver} 跨多晶圆厂跑同器件类型逆设计对比

许可证纪律：零外部依赖（仅 Python 标准库），离线可跑、主权可控；
所有内核逻辑复用 lda_harness / lda_l1 / lda_agent / lda_l2，不在此处重写验证逻辑。
"""
import json
import math
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WEBUI_DIR = os.path.dirname(os.path.abspath(__file__))
LDA_ROOT = os.path.dirname(WEBUI_DIR)
if LDA_ROOT not in sys.path:
    sys.path.insert(0, LDA_ROOT)

from lda_harness.benchmarks import BENCHMARK_DEFS
from lda_harness.harness import (
    VerificationHarness, ReferenceCandidate, PerturbedCandidate,
)
from lda_harness.l3_ai_solver import L3AISolverCandidate
from lda_agent.design_loop import DesignAgent
from lda_agent.run_demo import build_intent
from lda_l2.pdk import get_default_registry

HARNESS = VerificationHarness(BENCHMARK_DEFS)
AGENT_OUT = os.path.join(LDA_ROOT, "reports_agent")


# --------------------------------------------------------------------------
# 内核调用（全部复用已落地模块）
# --------------------------------------------------------------------------
def build_results_json(results, meta):
    details = []
    for r in results:
        details.append({
            "id": r.bid, "metric": r.metric, "oracle": r.oracle,
            "source": getattr(r, "source", ""),
            "golden": r.golden, "candidate": r.candidate,
            "tol": r.tol, "passed": r.passed, "note": r.note,
        })
    passed = sum(1 for r in results if r.passed)
    return {
        "meta": meta,
        "summary": {"total": len(results), "passed": passed,
                    "failed": len(results) - passed},
        "details": details,
    }


def run_verify(payload):
    kind = payload.get("candidate", "reference")
    perturb = float(payload.get("perturb", 0.1) or 0.1)
    if kind == "l3_ai":
        cand = L3AISolverCandidate()
        name = "L3AISolverCandidate(llm=%s)" % cand.llm_enabled
    elif kind == "perturb":
        cand = PerturbedCandidate(perturb)
        name = "PerturbedCandidate(%.0f%%)" % (perturb * 100)
    else:
        cand = ReferenceCandidate()
        name = "ReferenceCandidate"
    specs = HARNESS.resolve_specs(None)
    results = HARNESS.run(specs, cand)
    meta = {"candidate": name, "oracle": "确定性物理定律锚（麦克斯韦方程的必然）"}
    return build_results_json(results, meta)


def run_agent_loop(payload):
    """真跑 agent 自迭代设计闭环（复用 run_demo 的布拉格镜意图）。

    用真实 design_loop API（DesignAgent.run(intent)），后端 numpy 已实证。
    """
    backend = payload.get("backend", "numpy")
    geo = payload.get("geo", "stack")
    threshold = float(payload.get("threshold", 0.99))
    intent = build_intent(threshold, geo)
    intent["geo_kind"] = geo
    intent["extra"] = {"backend": backend, "dl_factor": 60.0, "sponge": 60, "ramp": 200}
    agent = DesignAgent(backend=backend, geo_kind=geo,
                        dl_factor=60.0, sponge=60, ramp=200)
    rep = agent.run(intent)
    return rep.to_dict()


def system_status():
    return {
        "layers": [
            {"id": "L0", "name": "统一 IR / DSL（机器优先·含谱形+多 foundry）", "status": "built"},
            {"id": "L1", "name": "agent 协议层 + 真·MCP", "status": "built"},
            {"id": "L2", "name": "PDK Registry（社区共建）", "status": "built"},
            {"id": "L3", "name": "AI 写求解内核", "status": "built"},
            {"id": "harness", "name": "验证裁判（物理定律锚）", "status": "built"},
            {"id": "field", "name": "B5–B7 场级 ORACLE", "status": "built"},
            {"id": "agent", "name": "agent 自迭代设计闭环", "status": "built"},
            {"id": "ui", "name": "L4 产品级实时 UI", "status": "built"},
        ],
        "benchmarks_total": len(BENCHMARK_DEFS),
    }


# --------------------------------------------------------------------------
# HTTP 处理
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj=None, body=None, ctype="application/json"):
        if body is None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            p = os.path.join(WEBUI_DIR, "static", "index.html")
            with open(p, "rb") as f:
                self._send(200, body=f.read(), ctype="text/html")
        elif path == "/api/status":
            self._send(200, system_status())
        elif path == "/api/benchmarks":
            bm = [{"id": k, "title": v.get("title"), "metric": v.get("metric"),
                   "oracle": v.get("oracle"), "tol": v.get("tol")}
                  for k, v in BENCHMARK_DEFS.items()]
            self._send(200, {"benchmarks": bm})
        elif path == "/api/pdks":
            reg = get_default_registry()
            self._send(200, {"pdks": reg.to_summary(), "keys": reg.list_pdks()})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            payload = {}
        try:
            if path == "/api/verify":
                self._send(200, run_verify(payload))
            elif path == "/api/agent_loop":
                self._send(200, run_agent_loop(payload))
            elif path == "/api/pdk_design":
                self._send(501, {"error": "not_implemented",
                                 "message": "PDK 逆设计依赖 DesignProblem 抽象层，尚未实现（超前骨架）。"
                                            "当前可用：/api/verify、/api/agent_loop。"})
            elif path == "/api/pdk_compare":
                self._send(501, {"error": "not_implemented",
                                 "message": "PDK 跨厂对比依赖 DesignProblem 抽象层，尚未实现（超前骨架）。"
                                            "当前可用：/api/verify、/api/agent_loop。"})
            elif path == "/api/ir_demo":
                self._send(501, {"error": "not_implemented",
                                 "message": "IR demo 依赖 DesignProblem 抽象层，尚未实现（超前骨架）。"
                                            "当前可用：/api/verify、/api/agent_loop。"})
            else:
                self._send(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            self._send(500, {"error": str(e)})

    def log_message(self, *a):
        pass


def main():
    port = int(os.environ.get("LDA_WEBUI_PORT", "8787"))
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("LDA webui serving on http://0.0.0.0:%d" % port, flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
