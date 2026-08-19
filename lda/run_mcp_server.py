"""LDA L1 · MCP server 启动入口。

由任意 MCP 客户端以 stdio 方式拉起，例如 Claude Desktop / Cursor 的
mcpServers 配置：
  {
    "mcpServers": {
      "lda-kernel": {
        "command": "python",
        "args": ["D:/agent_LDA/lda/run_mcp_server.py"]
      }
    }
  }

server 通过 stdin/stdout 的 newline-delimited JSON-RPC 2.0 与客户端通信，
无需网络端口、无需第三方包。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_l1.mcp_server import LdaMcpServer

if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "reports_mcp")
    LdaMcpServer(out_dir=out_dir).run()
