"""D-102 · WebUI API 路由层冒烟（维护门禁，覆盖 WebUI 路由层）。

此前全部 smoke 只测后端内核，未覆盖 WebUI 路由层。本 smoke：
  1) 从 lda_webui/app.py 源码静态提取 do_GET / do_POST 全部 /api/* 路由；
  2) 启动 WebUI（临时端口）子进程，/api/status 就绪探测；
  3) 实跑「快路径」：全部 GET 端点 + /api/ecosystem/* 提交/评审类 POST 端点
     （空载荷即快速返回，覆盖路由分发 + JSON 序列化）；
  4) 重计算 POST 端点（adjoint/hybrid/inverse/sparams 等）**不实跑**——
     静态已证路由存在，其内核由各自专用 smoke 覆盖（run_adjoint_design_smoke
     等）；避免空载荷触发数分钟优化导致冒烟挂起（🔴 D-102 血泪教训）。
"""
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "lda_webui", "app.py")

ROUTE_RE = re.compile(r'path == "(/api/[a-z_0-9/]+)"')
# 重计算端点（空载荷会触发数分钟优化）→ 仅静态验证存在，不实跑
HEAVY_POST = {
    "adjoint_design", "adjoint_loop", "agent_loop", "band_loop",
    "coupler_design", "coupler_loop", "dc_transmission", "design_loop",
    "design_package", "design_pipeline", "device_library", "gc_sparams",
    "hybrid_design", "hybrid_multi", "inverse_design", "ir_demo", "ir_spec",
    "large_scale_bench", "layout_pipeline", "mixed_system",
    "multiqubit_fidelity", "multiqubit_readout", "pdk_design", "pdks",
    "perf_bench", "pipeline_realize", "port_acceptance", "primitives",
    "qeda_depth", "qeda_topology", "quantum_design", "qubit_resonator",
    "readout_chain", "readout_fidelity", "ring_fdtd", "ring_loop",
    "ring_package", "shape_design", "sparams", "spectral_design",
    "splitter_readout", "tunable_wdm", "verify", "wdm_coupler", "wdm_design",
    "wdm_splitter", "pdk_compare",
}


def _extract_routes():
    src = open(APP, encoding="utf-8").read()
    get_blk = src.split("def do_GET", 1)[1].split("def do_POST", 1)[0]
    post_blk = src.split("def do_POST", 1)[1].split("def log_message", 1)[0]
    gets = sorted(set(ROUTE_RE.findall(get_blk)))
    posts = sorted(set(ROUTE_RE.findall(post_blk)))
    return gets, posts


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _http(method, url, body=None, timeout=15):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(400).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(400).decode("utf-8", "replace")
    except Exception as e:
        return None, str(e)


def main():
    gets, posts = _extract_routes()
    port = _free_port()
    env = dict(os.environ, LDA_WEBUI_PORT=str(port))
    proc = subprocess.Popen(
        [sys.executable, os.path.join(HERE, "lda_webui", "app.py")],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        base = f"http://127.0.0.1:{port}"
        ready = False
        for _ in range(30):
            code, _ = _http("GET", f"{base}/api/status")
            if code == 200:
                ready = True
                break
            time.sleep(0.5)
        if not ready:
            print("[FATAL] WebUI 服务未就绪")
            return 1

        ok, info, fail = [], [], []
        # 1) GET 端点实跑（快）
        for r in gets:
            code, text = _http("GET", f"{base}{r}")
            is_json = text.lstrip().startswith(("{", "["))
            if code == 200 and is_json:
                ok.append(("GET", r, f"{code} JSON"))
            else:
                fail.append(("GET", r, f"{code} {text[:50]}"))
        # 2) /api/ecosystem/* 快速 POST 实跑（空载荷即快速返回）
        eco_posts = [r for r in posts if r.startswith("/api/ecosystem/")]
        for r in eco_posts:
            code, text = _http("POST", f"{base}{r}", {})
            is_json = text.lstrip().startswith(("{", "["))
            if code == 200 and is_json:
                ok.append(("POST", r, f"{code} JSON"))
            else:
                fail.append(("POST", r, f"{code} {text[:50]}"))
        # 3) 重计算 POST 端点：静态验证存在（不实跑）
        heavy = [r for r in posts
                 if any(f"/{h}" in r for h in HEAVY_POST)]
        static_only = [r for r in posts if r not in eco_posts
                       and r not in heavy and r != "/api/status"]
        for r in heavy:
            info.append(("POST", r, "静态存在（重计算，内核由专用 smoke 覆盖）"))
        for r in static_only:
            info.append(("POST", r, "静态存在（未分类/重计算，不实跑）"))

        print("=" * 66)
        print(f"WebUI API 路由层冒烟 · GET {len(gets)} / POST {len(posts)}")
        print("=" * 66)
        for m, r, d in ok:
            print(f"[PASS] {m:<5} {r:<40} {d}")
        for m, r, d in info:
            print(f"[INFO] {m:<5} {r:<40} {d}")
        for m, r, d in fail:
            print(f"[FAIL] {m:<5} {r:<40} {d}")
        print("-" * 66)
        print(f"实跑 PASS={len(ok)} · 静态 INFO={len(info)} · FAIL={len(fail)}")
        if fail:
            print("存在路由层失败 ❌")
            return 1
        print("路由层全绿 ✅（重计算端点静态验证存在，其内核由各专用 smoke 覆盖）")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
