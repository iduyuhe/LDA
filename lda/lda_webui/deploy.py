#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""LDA WebUI 内网部署脚本（D-13）。

用法（在仓库任意位置，用 LDA 的 venv python 运行）：
  python lda/lda_webui/deploy.py start            # 启动（默认端口 8787）
  python lda/lda_webui/deploy.py start --port 9000
  python lda/lda_webui/deploy.py status           # 状态 + 健康检查
  python lda/lda_webui/deploy.py stop             # 停止
  python lda/lda_webui/deploy.py restart          # 重启

跨平台（Windows / Linux / macOS）：
  - 后台子进程运行 app.py（0.0.0.0:port，内网可达）
  - pid 文件 + 日志文件便于运维
  - status 做 HTTP 健康检查（GET /api/status）

零外部依赖（仅标准库）；token/密钥不涉及；日志见 webui.log。
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time

WEBUI_DIR = os.path.dirname(os.path.abspath(__file__))
PIDFILE = os.path.join(WEBUI_DIR, "webui.pid")
LOGFILE = os.path.join(WEBUI_DIR, "webui.log")
DEFAULT_PORT = 8787


# ---------------------------------------------------------------------------
# 进程管理
# ---------------------------------------------------------------------------
def _pid_alive(pid: int) -> bool:
    if sys.platform.startswith("win"):
        # tasklist 输出为本地编码（如 GBK），用 bytes 解码并忽略错误
        r = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid],
                           capture_output=True)
        out = r.stdout.decode("utf-8", "ignore") + r.stderr.decode("utf-8", "ignore")
        return str(pid) in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_pid():
    if not os.path.exists(PIDFILE):
        return None
    try:
        pid = int(open(PIDFILE, encoding="utf-8").read().strip())
    except (ValueError, OSError):
        return None
    return pid if _pid_alive(pid) else None


def start(port: int) -> int:
    pid = _read_pid()
    if pid is not None:
        print(f"LDA WebUI 已在运行 pid={pid}（如需重启：deploy.py restart）")
        return 1
    python = sys.executable
    cmd = [python, os.path.join(WEBUI_DIR, "app.py")]
    env = dict(os.environ)
    env["LDA_WEBUI_PORT"] = str(port)
    with open(LOGFILE, "a", encoding="utf-8") as f:
        proc = subprocess.Popen(
            cmd, cwd=WEBUI_DIR, env=env,
            stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    with open(PIDFILE, "w", encoding="utf-8") as f:
        f.write(str(proc.pid))
    print(f"LDA WebUI 已启动 pid={proc.pid} 端口={port}")
    print(f"  日志：{LOGFILE}")
    time.sleep(1.5)
    status(port)
    return 0


def stop() -> int:
    pid = _read_pid()
    if pid is None:
        print("LDA WebUI 未运行（pid 文件缺失或进程已退出）")
        return 1
    if sys.platform.startswith("win"):
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True)
    else:
        os.kill(pid, signal.SIGTERM)
    if os.path.exists(PIDFILE):
        os.unlink(PIDFILE)
    print(f"LDA WebUI 已停止 pid={pid}")
    return 0


def status(port: int = DEFAULT_PORT) -> int:
    pid = _read_pid()
    if pid is None:
        print("LDA WebUI: 未运行")
        return 1
    import json
    import urllib.request
    try:
        req = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/status", timeout=5)
        d = json.loads(req.read().decode("utf-8"))
        print(f"LDA WebUI: 运行中 pid={pid} 端口={port} "
              f"layers={len(d.get('layers', []))} pdks={d.get('pdks_registered')}")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"LDA WebUI: 运行中 pid={pid}（但健康检查失败: {e}）")
        return 1


def restart(port: int) -> int:
    stop()
    time.sleep(0.5)
    return start(port)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="LDA WebUI 内网部署脚本（D-13）")
    ap.add_argument("action", choices=["start", "stop", "status", "restart"])
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help=f"端口（默认 {DEFAULT_PORT}）")
    args = ap.parse_args()

    if args.action == "start":
        return start(args.port)
    if args.action == "stop":
        return stop()
    if args.action == "status":
        return status(args.port)
    if args.action == "restart":
        return restart(args.port)
    return 1


if __name__ == "__main__":
    sys.exit(main())
