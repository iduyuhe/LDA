#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_cs_agent_chat_smoke.py —— 智能体客服「选择后能真正回复」护栏（v0.9.47）。

背景：杜先生报障「服务智能体选择后还不能真正回复」。根因定位为
lda_webui/static/cs_widget.js 的 addMsg() 漏写 `return m;`——它把消息节点
m 加进对话区却没返回，导致 `var wait = addMsg("bot", "…")` 拿到 undefined，
随后 `body.removeChild(wait)` 抛 `parameter 1 is not of type 'Node'`，回复占位符
「…」永远删不掉、真实 reply 永远加不进去。点击建议 / 输入发送均走同一死路 →
客服完全不可用。这是「改造留半截」类缺陷（同类于 D-78 的门禁半截）。

本护栏以「真跑 WebUI + 静态守卫 + 反向污染」三重守护，防回潮：
  - 真跑：POST /api/agent/chat（已知 FAQ 关键词）→ 断言 reply 非空；
          留资文本 → lead_captured=true；guide_cmd=start → 返回 guide。
  - 静态：cs_widget.js 的 addMsg 必须 `return m;`（关键守卫，防本次漏写复发）；
          两处 removeChild(wait) 不得裸调用（须 `if (wait && wait.parentNode)` 守卫）。
  - 反向：把 addMsg 的 `return m;` 删掉 / 把 removeChild 守卫去掉后重跑对应判据，
          必须 FAIL（证明判据会响，而非假绿）。
"""
import os
import re
import sys
import json
import time
import socket
import subprocess
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "lda_webui", "static")
CS = os.path.join(STATIC, "cs_widget.js")
APP = os.path.join(HERE, "lda_webui", "app.py")


# --------------------------------------------------------------------------
# 静态判据
# --------------------------------------------------------------------------
def _extract_addmsg(src):
    m = re.search(r"function addMsg\([\s\S]*?\n    \}", src)
    return m.group(0) if m else ""


def _addmsg_returns_node(src):
    """关键守卫：addMsg 必须返回其创建的节点 m。漏写 return 即本次根因。"""
    fn = _extract_addmsg(src)
    if not fn:
        return False
    return bool(re.search(r"return\s+m\s*;", fn))


def _no_unguarded_removechild(src):
    """两处 removeChild(wait) 不得裸调用，必须带 `if (wait && wait.parentNode)` 守卫。"""
    # 裸调用特征：body.removeChild(wait) 前面不是 `if (wait && wait.parentNode)`
    for m in re.finditer(r"body\.removeChild\(wait\)\s*;", src):
        start = max(0, m.start() - 60)
        pre = src[start:m.start()]
        if "wait && wait.parentNode" not in pre:
            return False
    return True


STATIC_CHECKS = [
    ("cs_widget.js addMsg 必须 return m（防漏写复发）",
     lambda s: _addmsg_returns_node(s["cs"])),
    ("cs_widget.js removeChild(wait) 不得裸调用（须守卫）",
     lambda s: _no_unguarded_removechild(s["cs"])),
]


def _load_sources():
    return {"cs": open(CS, encoding="utf-8").read()}


# --------------------------------------------------------------------------
# HTTP helpers
# --------------------------------------------------------------------------
def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _http(method, url, timeout=15, headers=None, data=None):
    h = {}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(8000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(8000).decode("utf-8", "replace")
    except Exception as e:  # noqa
        return None, str(e)


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
def main():
    results = []  # (name, ok, detail)

    # —— 静态判据 ——
    src = _load_sources()
    for name, fn in STATIC_CHECKS:
        ok = fn(src)
        results.append((name, ok, "" if ok else "源码判据未满足"))

    # —— 反向：污染副本后重跑，必须 FAIL ——
    cs = src["cs"]
    # 删掉 addMsg 的 return m;（复现漏写根因）
    addmsg_broken = re.sub(r"return\s+m\s*;", "", cs, count=1)
    # 去掉 removeChild 守卫（把 `if (wait && wait.parentNode) body.removeChild(wait);` 改成裸调用）
    removechild_broken = re.sub(
        r"if \(wait && wait\.parentNode\) body\.removeChild\(wait\);",
        "body.removeChild(wait);", cs)
    reverse = [
        ("反向·addMsg 漏 return 应 FAIL",
         lambda s: _addmsg_returns_node(s), addmsg_broken),
        ("反向·removeChild 去守卫应 FAIL",
         lambda s: _no_unguarded_removechild(s), removechild_broken),
    ]
    for name, fn, polluted in reverse:
        ok = fn(polluted)  # 期望 False
        results.append((name, not ok, "" if not ok else "判据未对污染响应（假绿）"))

    # —— 真跑 WebUI ——
    port = _free_port()
    env = dict(os.environ, LDA_WEBUI_PORT=str(port))
    proc = subprocess.Popen(
        [sys.executable, APP], env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        base = f"http://127.0.0.1:{port}"
        ready = False
        for _ in range(40):
            code, _ = _http("GET", f"{base}/api/status", timeout=5)
            if code == 200:
                ready = True
                break
            time.sleep(0.5)
        if not ready:
            results.append(("WebUI 服务就绪", False, "app.py 未起"))
            return _report(results)

        hdr = {"Content-Type": "application/json"}

        # ① 已知 FAQ 关键词 → 必须拿到非空真实 reply
        code, body = _http("POST", f"{base}/api/agent/chat",
                           headers=hdr,
                           data=json.dumps({"message": "你们是做什么的", "history": []}).encode())
        try:
            d = json.loads(body)
        except Exception:
            d = {}
        ok = code == 200 and isinstance(d.get("reply"), str) and len(d["reply"].strip()) > 0
        results.append(("POST /api/agent/chat 发问→真实 reply",
                        ok, f"code={code} replyLen={len(d.get('reply') or '')}"))

        # ② 留资文本 → lead_captured=true
        code, body = _http("POST", f"{base}/api/agent/chat",
                           headers=hdr,
                           data=json.dumps({"message": "留个联系方式 张三 z@x.com", "history": []}).encode())
        try:
            d = json.loads(body)
        except Exception:
            d = {}
        ok = code == 200 and d.get("lead_captured") is True
        results.append(("POST /api/agent/chat 留资→lead_captured=true",
                        ok, f"code={code} lead={d.get('lead_captured')}"))

        # ③ 引导模式 → 返回 guide 结构
        code, body = _http("POST", f"{base}/api/agent/chat",
                           headers=hdr,
                           data=json.dumps({"guide_cmd": "start", "history": []}).encode())
        try:
            d = json.loads(body)
        except Exception:
            d = {}
        g = d.get("guide") or {}
        ok = code == 200 and g.get("total") == 7 and isinstance(g.get("intro"), str)
        results.append(("POST /api/agent/chat 引导→guide 结构完整",
                        ok, f"code={code} total={g.get('total')}"))
    finally:
        try:
            proc.terminate()
        except Exception:
            pass

    return _report(results)


def _report(results):
    n_pass = sum(1 for _, ok, _ in results if ok)
    n_fail = len(results) - n_pass
    print("=" * 64)
    print(" 智能体客服回复护栏 (run_cs_agent_chat_smoke)")
    print("=" * 64)
    for name, ok, detail in results:
        tag = "PASS" if ok else "FAIL"
        line = f"  [{tag}] {name}"
        if detail and not ok:
            line += f"  ({detail})"
        print(line)
    print("-" * 64)
    print(f"  合计: {n_pass} PASS / {n_fail} FAIL")
    print("=" * 64)
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
