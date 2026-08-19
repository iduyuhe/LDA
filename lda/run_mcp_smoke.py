"""LDA L1 · MCP server 冒烟测试（模拟 MCP 客户端）。

自拉起 run_mcp_server.py 子进程，依次发 initialize / tools/list /
lda.list_benchmarks / lda.verify_design（reference）四条 JSON-RPC 消息，
逐条读回并断言，验证真·MCP server 端到端可达。这是对「外部 agent 真能
call lda.verify_design」的最小实证。

用法：python run_mcp_smoke.py
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
SERVER = os.path.join(HERE, "run_mcp_server.py")


def send(proc, obj):
    proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
    proc.stdin.flush()


def recv(proc):
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("server 无响应（EOF）")
    return json.loads(line)


def main():
    proc = subprocess.Popen(
        [PY, SERVER],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        text=True, encoding="utf-8", bufsize=1,
        cwd=HERE,
    )
    checks = []

    # 1) initialize
    send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05",
                           "capabilities": {}, "clientInfo": {"name": "smoke"}}})
    r = recv(proc)
    ok = (r.get("id") == 1 and r.get("result", {}).get("protocolVersion")
          == "2024-11-05")
    checks.append(("initialize", ok, r.get("result", {}).get("serverInfo")))

    # 2) notifications/initialized（通知，无回包）
    send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

    # 3) tools/list
    send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    r = recv(proc)
    tools = [t["name"] for t in r.get("result", {}).get("tools", [])]
    ok = (r.get("id") == 2 and "lda.verify_design" in tools
          and "lda.list_benchmarks" in tools)
    checks.append(("tools/list", ok, tools))

    # 4) tools/call → lda.list_benchmarks
    send(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "lda.list_benchmarks", "arguments": {}}})
    r = recv(proc)
    content = r.get("result", {}).get("content", [{}])
    txt = content[0].get("text", "{}") if content else "{}"
    bm = json.loads(txt)
    res = bm.get("result", {})  # AgentResponse.result.benchmarks
    ok = (r.get("id") == 3 and not r.get("result", {}).get("isError")
          and "benchmarks" in res)
    checks.append(("tools/call:list_benchmarks", ok,
                   f"{len(res.get('benchmarks', []))} 题"))

    # 5) tools/call → lda.verify_design (reference)
    send(proc, {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                "params": {"name": "lda.verify_design",
                           "arguments": {"candidate": {"type": "reference"}}}})
    r = recv(proc)
    content = r.get("result", {}).get("content", [{}])
    txt = content[0].get("text", "{}") if content else "{}"
    vr = json.loads(txt)
    sm = vr.get("result", {}).get("summary", {})
    ok = (r.get("id") == 4 and not r.get("result", {}).get("isError")
          and sm.get("passed") == sm.get("total") and sm.get("total") == 8)
    checks.append(("tools/call:verify_design", ok,
                   f"{sm.get('passed')}/{sm.get('total')} PASS"))

    # 6) tools/call → lda.verify_design (l3_ai, 应 FAIL 但流程成功)
    send(proc, {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                "params": {"name": "lda.verify_design",
                           "arguments": {"candidate": {"type": "l3_ai"}}}})
    r = recv(proc)
    content = r.get("result", {}).get("content", [{}])
    txt = content[0].get("text", "{}") if content else "{}"
    vr = json.loads(txt)
    sm = vr.get("result", {}).get("summary", {})
    # isError 应为 False（流程成功，只是有 FAIL 被试出）
    ok = (r.get("id") == 5 and not r.get("result", {}).get("isError")
          and sm.get("passed", 99) < sm.get("total", 0))
    checks.append(("tools/call:verify_design(l3_ai)", ok,
                   f"{sm.get('passed')}/{sm.get('total')} (法官抓 FAIL)"))

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    print("\n=== MCP server 冒烟测试结果 ===")
    all_ok = True
    for name, ok, detail in checks:
        flag = "✅" if ok else "❌"
        if not ok:
            all_ok = False
        print(f"  {flag} {name}  ·  {detail}")
    print("=== 结论:", "全通过" if all_ok else "有失败", "===")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
