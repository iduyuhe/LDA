"""LDA L1 · 真·MCP server（零依赖 stdio JSON-RPC 2.0）。

把 L1 协议层从「内部 KernelGateway 参考实现」升级为「对外可集成的 MCP 协议服务器」。
任意兼容 MCP 的客户端（Claude Desktop / Cursor / Cline / 自写 agent）均可：
  - tools/list  → 发现 lda.verify_design / lda.list_benchmarks
  - tools/call  → 真正驱动 L0 IR → L3 candidate → harness → 结构化验证结果

设计纪律：
  - 零外部依赖（不装 mcp/fastmcp 包），手写最小 JSON-RPC 2.0 over stdio，
    契合 LDA「离线可跑、主权可控」原则；协议版本 2024-11-05。
  - 复用 KernelGateway，不重复实现验证逻辑；物理定律锚 + 双判据全部继承。
  - 确定性：同请求 → 同结果；无状态、无交互。

启动：python run_mcp_server.py   （由 MCP 客户端以 stdio 方式拉起）
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lda_l1.protocol import AgentRequest, KernelGateway


class LdaMcpServer:
    PROTOCOL_VERSION = "2024-11-05"
    SERVER_NAME = "lda-kernel"
    SERVER_VERSION = "0.1.0"

    def __init__(self, out_dir="reports_mcp"):
        self.gw = KernelGateway(out_dir=out_dir)
        self.initialized = False

    # ---- 工具清单（MCP 格式：inputSchema 大写 S）---------------------
    def _tools(self):
        out = []
        for t in self.gw.tool_schemas():
            out.append({
                "name": t["name"],
                "description": t["description"],
                "inputSchema": t["input_schema"],
            })
        return out

    # ---- 把 KernelGateway 的 AgentResponse 包成 MCP tools/call 结果 ---
    @staticmethod
    def _wrap(resp):
        d = resp.to_dict()
        is_error = (d.get("status") == "error")
        return {
            "content": [
                {"type": "text",
                 "text": json.dumps(d, ensure_ascii=False, indent=2)}
            ],
            "isError": is_error,
        }

    # ---- 方法分发 ----------------------------------------------------
    def _dispatch(self, method, params):
        params = params or {}

        if method == "initialize":
            self.initialized = True
            return {
                "protocolVersion": self.PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": self.SERVER_NAME,
                    "version": self.SERVER_VERSION,
                },
            }

        if method == "ping":
            return {}

        if method == "tools/list":
            return {"tools": self._tools()}

        if method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments", {}) or {}
            # 通用分派：lda.<action> → AgentRequest(action, args)
            # 覆盖 verify_design / list_benchmarks / link_simulate / route /
            # place / export_chip_gds 等全部 L1 原语，无需逐工具分支。
            if name.startswith("lda."):
                action = name[len("lda."):]
                # verify_design 兼容旧字段名（l0_ir/candidate/benchmarks）
                if action in ("verify_design", "run_candidate"):
                    payload = {}
                    if "l0_ir" in args:
                        payload["l0_ir"] = args["l0_ir"]
                    if "candidate" in args:
                        payload["candidate"] = args["candidate"]
                    if "benchmarks" in args:
                        payload["benchmarks"] = args["benchmarks"]
                    if "rel_err" in args:
                        payload.setdefault("candidate", {})["rel_err"] = args["rel_err"]
                else:
                    payload = args
                req = AgentRequest(action, payload)
                return self._wrap(self.gw.handle(req))
            return {"error": {"code": -32602,
                              "message": f"未知工具: {name}"}}

        # 其他（含 notifications/*）→ 不回包
        return None

    # ---- stdio 事件循环 ----------------------------------------------
    def run(self, instream=None, outstream=None):
        instream = instream or sys.stdin
        outstream = outstream or sys.stdout
        for line in instream:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            method = msg.get("method")
            mid = msg.get("id")
            # 通知（无 id，如 notifications/initialized）→ 不回包
            if mid is None:
                continue
            if "method" not in msg:
                continue

            result = self._dispatch(method, msg.get("params", {}) or {})
            if result is None:
                continue
            if "error" in result and "content" not in result:
                out = {"jsonrpc": "2.0", "id": mid, "error": result["error"]}
            else:
                out = {"jsonrpc": "2.0", "id": mid, "result": result}
            outstream.write(json.dumps(out, ensure_ascii=False) + "\n")
            outstream.flush()


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(os.path.dirname(here), "reports_mcp")
    LdaMcpServer(out_dir=out_dir).run()


if __name__ == "__main__":
    main()
