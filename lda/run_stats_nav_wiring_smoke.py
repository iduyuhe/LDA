#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_stats_nav_wiring_smoke.py —— stats.html 数据看板接线护栏（v0.9.47）。

背景：v0.9.46 发现 stats.html 是孤儿页（路由 404 + 导航不链）。本轮杜先生拍板
「接线挂回导航」。接线两处：
  (1) routes.py h_static_html 白名单加入 "stats.html"（否则 GET /stats.html → 404）；
  (2) nav.js 凭 /api/admin/me HttpOnly Cookie 探活显示「数据看板」链接，
      取代原 localStorage lda_admin_logged_in 影子标志（P2-5 改造留半截同类缺陷）。

本护栏以「真跑 WebUI + 反向测试」守护，防回潮：
  - 真跑：起 WebUI，GET /stats.html=200 且含「数据看板」；/nope.html=404（证明白名单在生效，
    而非 handler 恒 200）；/api/admin/me 无凭据=401（鉴权有效）；带 admin Cookie=200 admin:true。
  - 静态：routes.py 白名单含 stats.html；nav.js 不依赖 localStorage、含 /api/admin/me 探活、
    stats 链接默认隐藏；stats.html 引入 nav.js。
  - 反向：对每份源码做污染副本，重跑对应静态检查，必须 FAIL（证明判据会响）。
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
ROUTES = os.path.join(HERE, "lda_webui", "routes.py")
NAV = os.path.join(HERE, "lda_webui", "static", "nav.js")
STATS = os.path.join(HERE, "lda_webui", "static", "stats.html")
APP = os.path.join(HERE, "lda_webui", "app.py")

ADMIN_TOK = "smoke-admin-token-v0947"


# --------------------------------------------------------------------------
# 静态判据（纯源码字符串，便于反向污染重跑）
# --------------------------------------------------------------------------
def _has_whitelist_stats(src):
    return '"stats.html"' in src and "index.html" in src and "public.html" in src


def _nav_no_localstorage(src):
    # 严禁再用 localStorage 影子标志决定数据看板可见性（允许注释里作说明，
    # 但绝不允许出现真实的读取调用 localStorage.getItem("lda_admin_logged_in")）。
    return 'localStorage.getItem("lda_admin_logged_in")' not in src


def _nav_probes_admin_me(src):
    return "/api/admin/me" in src and "revealStatsIfAdmin" in src


def _nav_stats_link_hidden(src):
    # 默认隐藏，探活后才显示；不应再以条件拼接显隐（旧写法会回潮）
    return 'id="lda-nav-stats"' in src and "display:none" in src


def _stats_uses_nav(src):
    return "/nav.js" in src


STATIC_CHECKS = [
    ("routes.py 白名单含 stats.html", lambda s: _has_whitelist_stats(s["routes"])),
    ("nav.js 不再依赖 localStorage 影子标志", lambda s: _nav_no_localstorage(s["nav"])),
    ("nav.js 凭 /api/admin/me 探活", lambda s: _nav_probes_admin_me(s["nav"])),
    ("nav.js 数据看板链接默认隐藏", lambda s: _nav_stats_link_hidden(s["nav"])),
    ("stats.html 引入 nav.js", lambda s: _stats_uses_nav(s["stats"])),
]


def _load_sources():
    return {
        "routes": open(ROUTES, encoding="utf-8").read(),
        "nav": open(NAV, encoding="utf-8").read(),
        "stats": open(STATS, encoding="utf-8").read(),
    }


# --------------------------------------------------------------------------
# HTTP helpers
# --------------------------------------------------------------------------
def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _http(method, url, timeout=15, headers=None):
    h = {}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(2000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(2000).decode("utf-8", "replace")
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

    # —— 反向：污染每份源码后重跑对应判据，必须 FAIL ——
    corruption = {
        "routes": src["routes"].replace('"stats.html"', '""'),
        "nav": src["nav"].replace("/api/admin/me", "/api/admin/X"),
        "stats": src["stats"].replace("/nav.js", "/nav-no.js"),
    }
    # nav 的双重污染：探测调用被改 + 显隐改为 localStorage 回潮
    nav_relapse = src["nav"].replace(
        "revealStatsIfAdmin", "_revealViaLocalStorage"
    ).replace(
        'fetch("/api/admin/me"',
        'localStorage.getItem("lda_admin_logged_in") ? null : null; fetch("/api/admin/me"'
    )
    reverse_cases = [
        ("反向·白名单移除 stats.html 应 FAIL",
         lambda s: _has_whitelist_stats(s), corruption["routes"]),
        ("反向·nav 改走 /api/admin/X 应 FAIL",
         lambda s: _nav_probes_admin_me(s), corruption["nav"]),
        ("反向·stats 不引 nav.js 应 FAIL",
         lambda s: _stats_uses_nav(s), corruption["stats"]),
        ("反向·nav 回潮 localStorage 应 FAIL",
         lambda s: _nav_no_localstorage(s), nav_relapse),
    ]
    for name, fn, polluted in reverse_cases:
        ok = fn(polluted)  # 期望 False
        results.append((name, not ok, "" if not ok else "判据未对污染响应（假绿）"))

    # —— 真跑 WebUI ——
    port = _free_port()
    env = dict(os.environ, LDA_WEBUI_PORT=str(port), LDA_ADMIN_TOKEN=ADMIN_TOK)
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

        # ① /stats.html → 200 + 含「数据看板」
        code, body = _http("GET", f"{base}/stats.html", timeout=10)
        ok = code == 200 and "数据看板" in body
        results.append(("GET /stats.html = 200 且含「数据看板」",
                        ok, f"code={code} hasTitle={'数据看板' in body}"))

        # ② /nope.html → 404（反向证明白名单生效，非 handler 恒 200）
        code, _ = _http("GET", f"{base}/nope.html", timeout=10)
        results.append(("GET /nope.html = 404（白名单隔离）",
                        code == 404, f"code={code}"))

        # ③ /api/admin/me 无凭据 → 401（鉴权有效）
        code, _ = _http("GET", f"{base}/api/admin/me", timeout=10)
        results.append(("GET /api/admin/me 无凭据 = 401",
                        code == 401, f"code={code}"))

        # ④ /api/admin/me 带 admin Cookie → 200 admin:true
        code, body = _http("GET", f"{base}/api/admin/me", timeout=10,
                           headers={"Cookie": f"lda_admin_token={ADMIN_TOK}"})
        try:
            d = json.loads(body)
        except Exception:
            d = {}
        ok = code == 200 and d.get("ok") is True and d.get("admin") is True
        results.append(("GET /api/admin/me 带 admin Cookie = 200 admin:true",
                        ok, f"code={code} body={body[:80]}"))
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
    print(" stats.html 接线护栏 (run_stats_nav_wiring_smoke)")
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
