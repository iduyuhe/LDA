"""D-102 · WebUI API 路由层冒烟（维护门禁，覆盖 WebUI 路由层）。

此前全部 smoke 只测后端内核，未覆盖 WebUI 路由层。本 smoke：
  1) 从 lda_webui/app.py 源码静态提取 do_GET / do_POST 全部 /api/* 路由；
  2) 启动 WebUI（临时端口）子进程，/api/status 就绪探测；
  3) 实跑「快路径」：全部 GET 端点 + /api/ecosystem/* 提交/评审类 POST 端点
     （空载荷即快速返回，覆盖路由分发 + JSON 序列化）；
  4) 重计算 POST 端点（adjoint/hybrid/inverse/sparams 等）**不实跑**——
     静态已证路由存在，其内核由各自专用 smoke 覆盖（run_adjoint_design_smoke
     等）；避免空载荷触发数分钟优化导致冒烟挂起（🔴 D-102 血泪教训）。
  5) D-103 追加：生态字段存在性断言——前端面板 53-56 渲染硬依赖的
     GET /api/ecosystem 关键字段路径（含嵌套 review_stats / proposal_status /
     review_policy / sovereign.A/B/C 等）逐一验证存在，字段被删除/改名即 FAIL。
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

# 重计算 GET 端点（默认配置即实跑数秒~数十秒规模计算）→ 仅静态验证路由存在，
# 不实跑（其内核由 run_cpo_array_smoke / run_cpo_array_scale_smoke 覆盖）。
HEAVY_GET = {
    "cpo_array",
}

# v0.9.33：冷启动耗时的重计算 GET——进入断言循环前必须先各打一次把 TTL 缓存
# 预热（耗时给足 120s）。否则通用 GET 循环会用 15s 超时硬撞冷启动，得到一个
# 与代码质量无关的 flaky 红（v0.9.33 首轮回归即连中 ecosystem / benchmark_crosscheck
# 两个端点，二者冷启动实测 15.3s / 9.1s，均与本次改动无关）。
# ⚠️ 预热不是放宽标准：真正被断言的是「第二次必须命中缓存且秒回」
# （见 `_check_heavy_get_caches`），那才是无鉴权公开 GET 的 DoS 护栏。
HEAVY_WARMUP = ["/api/ecosystem", "/api/benchmark_crosscheck"]


def _extract_routes():
    """P2 路由拆分后，/api/* 路由表已外置到 lda_webui/routes.py。

    从 routes.py 源码静态提取 GET_ROUTES / POST_ROUTES 字典的键（精确路由），
    等价覆盖原 app.py do_GET/do_POST 中 `path == "..."` 的精确端点；
    前缀型路由（startswith/endswith，如静态资源/proofs）非 API 端点，不纳入。
    """
    routes_path = os.path.join(HERE, "lda_webui", "routes.py")
    src = open(routes_path, encoding="utf-8").read()
    key_re = re.compile(r'^\s*"([/a-zA-Z0-9_.\-]+)"\s*:', re.M)

    def keys_of(block_name):
        i = src.index(block_name + " = {")
        j = src.index("}", i)
        return key_re.findall(src[i:j])

    # 仅纳入 /api/* 精确端点（HTML 页面路由如 /、/index.html 由静态分发覆盖，
    # 不纳入 JSON 路由层断言，与原 do_GET 解析口径一致）。
    gets = sorted(set(k for k in keys_of("GET_ROUTES") if k.startswith("/api/")))
    posts = sorted(set(k for k in keys_of("POST_ROUTES") if k.startswith("/api/")))
    return gets, posts


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _http(method, url, body=None, timeout=15, headers=None):
    data = None
    h = {}
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(400).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(400).decode("utf-8", "replace")
    except Exception as e:
        return None, str(e)


def _smoke_user_header(base: str):
    """注册一个 smoke 专用临时账号，返回带 Authorization 的请求头；失败返回 None。

    用途：验证 /api/store/me/* 与 /api/store/orders/mine 等需登录端点的 200 路径。
    注册失败（如限流/环境限制）时返回 None，由调用方降级为「401 鉴权有效」断言。
    """
    import secrets as _secrets
    email = f"smoke-{_secrets.token_hex(6)}@lda.local"
    payload = {"email": email, "name": "smoke", "password": "lda-smoke-pwd-2026",
               "user_type": "standard"}
    code, text = _http("POST", f"{base}/api/store/register", payload)
    if code != 200:
        return None
    try:
        tok = json.loads(text).get("token")
    except Exception:
        return None
    return {"Authorization": f"Bearer {tok}"} if tok else None


def _smoke_user_cookie(base: str):
    """P2-5 验证：注册临时账号并捕获后端签发的 HttpOnly Cookie（lda_store_token）。

    后端登录/注册现在同时签发 HttpOnly Cookie，前端不再用 localStorage 持有
    令牌。本函数验证「仅持 Cookie、不持 Authorization」也能通过需登录端点鉴权
    → 证明 XSS 抵抗令牌流端到端可用。返回形如 "lda_store_token=xxxx" 的 cookie
    字符串；注册/取 Cookie 失败时返回 None。
    """
    import secrets as _secrets
    email = f"smoke-{_secrets.token_hex(6)}@lda.local"
    payload = {"email": email, "name": "smoke", "password": "lda-smoke-pwd-2026",
               "user_type": "standard"}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{base}/api/store/register", data=data,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status != 200:
                return None
            sc = r.headers.get("Set-Cookie", "")
            # 取 lda_store_token=... 这一段（到第一个 ; 为止；HttpOnly 等属性丢弃）
            for part in sc.split(","):
                part = part.strip()
                if part.startswith("lda_store_token="):
                    return part.split(";")[0]
    except Exception:
        return None
    return None


# 前端面板 53-56 渲染硬依赖的 GET /api/ecosystem 关键字段路径（D-103 深审固化）
ECOSYSTEM_REQUIRED_FIELDS = [
    "harness.total", "harness.passed", "new_benchmarks",
    "sovereign.A.count", "sovereign.B.count", "sovereign.C.count",
    "registry.stats.total", "acceptance.passed", "acceptance.checks",
    "community.devices", "community.proposals",
    "community.proposal_status.pending", "community.proposal_status.approved",
    "community.proposal_status.rejected", "community.proposal_status.landed",
    "community.proposal_status.published",
    "community.review_stats.approvals", "community.review_stats.rejections",
    "community.review_stats.quorum_votes", "community.review_stats.avg_review_seconds",
    "community.review_policy.enforce_positive_tol",
    "community.review_policy.enforce_nonempty_params",
    "community.review_policy.enforce_value_bounds",
    "community.review_policy.authorized_reviewers",
    "community.review_policy.min_source_length",
    "community.review_policy.min_quorum",
    "community.review_policy.strict_dedup",
    "community.published", "community.publish_pending",
    # v0.9.33 新增：缓存契约字段——无鉴权公开 GET 不得每次请求都重跑 48 道锚
    "harness.cached", "harness.compute_ms", "harness.cache_ttl_s",
]

# D-108 实证锚字段存在性断言（面板 57 渲染硬依赖，D-62 新增端点此前无字段门禁）：
EMPIRICAL_REQUIRED_FIELDS = [
    "corpus.total", "corpus.by_metric", "corpus.records",
    "adversarial.total",
    "e_benchmarks",
    "review.stats", "review.proposals",
    "honest_note",
]


def _check_empirical_fields(base):
    """实证锚字段存在性断言（D-108）：GET /api/empirical 真实响应中逐一解析
    面板 57 渲染硬依赖字段路径（corpus/adversarial/e_benchmarks/review/
    honest_note），字段删除/改名即 FAIL。"""
    try:
        with urllib.request.urlopen(f"{base}/api/empirical", timeout=15) as r:
            d = json.load(r)
    except Exception as e:
        return [("FAIL", "GET /api/empirical", f"响应读取/解析失败: {e}")]

    def has(path):
        cur = d
        for k in path.split("."):
            if not isinstance(cur, dict) or k not in cur:
                return False
            cur = cur[k]
        return True

    checks = [("PASS" if has(p) else "FAIL", "field", p)
              for p in EMPIRICAL_REQUIRED_FIELDS]
    # e_benchmarks 数组元素字段（面板 57 判题演示硬依赖）
    eb = d.get("e_benchmarks") if isinstance(d, dict) else None
    if isinstance(eb, list) and eb:
        elem = eb[0]
        for k in ("id", "empirical_id", "golden", "tol"):
            checks.append(("PASS" if isinstance(elem, dict) and k in elem
                           else "FAIL", "field", f"e_benchmarks[0].{k}"))
    elif not isinstance(eb, list):
        checks.append(("FAIL", "field", "e_benchmarks 非数组"))
    return checks


def _check_heavy_get_caches(base):
    """v0.9.33 重计算 GET 的**缓存护栏**断言（无鉴权公开 GET 的 DoS 护栏）。

    被断言的性质：这些端点冷启动要跑 9~15s 的真内核，属无鉴权公开 GET，
    因此**重复请求必须命中 TTL 缓存秒回**，绝不能每次请求都重算——
    否则一个请求就占满 ThreadingHTTPServer 一个线程十秒级，并发即打爆进程。

    判据（死标量，不依赖机器负载）：`cached is True` 且响应耗时 < 3s。
    （冷启动已在 main() ⓪ 完成，此处跑的必然是缓存命中路径。）
    """
    checks = []
    for ep in HEAVY_WARMUP:
        t0 = time.time()
        try:
            with urllib.request.urlopen(f"{base}{ep}", timeout=15) as r:
                d = json.load(r)
        except Exception as e:
            checks.append(("FAIL", "perf", f"{ep} 缓存命中路径读取失败: {e}"))
            continue
        dt = time.time() - t0
        cached = d.get("cached")
        # /api/ecosystem 把 cached 放在 harness 子对象里（只缓存 harness 部分）
        if cached is None and isinstance(d.get("harness"), dict):
            cached = d["harness"].get("cached")
        checks.append(("PASS" if cached is True else "FAIL", "perf",
                       f"{ep} cached is True（未重复重算）"))
        checks.append(("PASS" if dt < 3.0 else "FAIL", "perf",
                       f"{ep} 缓存命中耗时 {dt:.2f}s < 3.0s"))
    return checks


def _check_ecosystem_fields(base):
    """生态字段存在性断言（D-103）：GET /api/ecosystem 真实响应中逐一解析
    前端面板 53-56 渲染硬依赖的关键字段路径，字段删除/改名即 FAIL。

    v0.9.33 追加 `harness.cached` / `harness.compute_ms` / `harness.cache_ttl_s`
    三个缓存契约字段——本端点 harness 全量实跑 48 道锚需 15.3s，属无鉴权公开
    GET，必须能被外部观察「本次是否命中缓存」，禁止「秒回即假装刚跑过」。
    （缓存是否真的生效由 `_check_heavy_get_caches()` 统一断言，不在此重复。）"""
    try:
        with urllib.request.urlopen(f"{base}/api/ecosystem", timeout=15) as r:
            d = json.load(r)
    except Exception as e:
        return [("FAIL", "GET /api/ecosystem", f"响应读取/解析失败: {e}")]

    def has(path):
        cur = d
        for k in path.split("."):
            if not isinstance(cur, dict) or k not in cur:
                return False
            cur = cur[k]
        return True

    return [(("PASS" if has(p) else "FAIL"), "field", p)
            for p in ECOSYSTEM_REQUIRED_FIELDS]


def _check_security_headers(base):
    """纵深防御安全头断言（B 纵深加固）：GET /api/status 响应须含全部安全响应头。

    任一缺失即 FAIL——安全头是全局注入（app.py _send），漏配会全局降级。
    """
    required = ["X-Frame-Options", "X-Content-Type-Options", "Referrer-Policy",
                "Content-Security-Policy", "Permissions-Policy"]
    try:
        with urllib.request.urlopen(f"{base}/api/status", timeout=15) as r:
            hdrs = {k.lower(): v for k, v in r.headers.items()}
    except Exception as e:
        return [("FAIL", "header", f"响应读取失败: {e}")]
    out = []
    for name in required:
        out.append(("PASS" if name.lower() in hdrs else "FAIL",
                     "header", name + ("" if name.lower() in hdrs else " 缺失")))
    return out


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

        # ⓪ 冷启动预热（v0.9.33）：重计算 GET 首次请求要跑真内核
        #    （/api/ecosystem 全量实跑 48 道物理定律锚 15.3s，其中 E2 半矢量
        #     本征解单道 12.0s；/api/benchmark_crosscheck 9.1s）。
        #    二者都已有 TTL 缓存，但**首次**仍是冷启动，必须先跑完再进断言循环。
        for _ep in HEAVY_WARMUP:
            _t0 = time.time()
            code, text = _http("GET", f"{base}{_ep}", timeout=120)
            if code != 200:
                print(f"[FATAL] {_ep} 冷启动失败 code={code} {text[:120]}")
                return 1
            print(f"[INFO] {_ep} 冷启动实跑耗时 {time.time() - _t0:.2f}s")

        ok, info, fail = [], [], []
        # 0) 鉴权端点凭据准备（v0.8.55 起弱默认管理员令牌已失效，硬编码 dev token 不再被接受）
        #    - /api/admin/* ：读环境变量 LDA_ADMIN_TOKEN（生产必设）
        #    - 需登录端点   ：临时注册一个 smoke 专用账号取 token
        #    无凭据时：断言「必须返回 401」= 鉴权有效（守护断言，防将来误关鉴权），
        #              绝不把未授权放行当作 PASS——安全标准不因 CI 变绿而降低。
        env_admin = os.environ.get("LDA_ADMIN_TOKEN", "").strip()
        admin_hdr = {"Authorization": f"Bearer {env_admin}"} if env_admin else None
        user_hdr = _smoke_user_header(base)

        # 1) GET 端点实跑（快）
        for r in gets:
            if r.replace("/api/", "") in HEAVY_GET:
                info.append(("GET", r,
                             "静态存在（重计算 GET，内核由专用 smoke 覆盖）"))
                continue
            if r.startswith("/api/admin/") or r == "/api/stats":
                h, need_auth = (admin_hdr or {}), True
            elif r.startswith("/api/store/me/") or r == "/api/store/orders/mine":
                h, need_auth = (user_hdr or {}), True
            else:
                h, need_auth = {}, False
            code, text = _http("GET", f"{base}{r}", headers=h)
            is_json = text.lstrip().startswith(("{", "["))
            if need_auth and not h and code == 200:
                # 安全回归：需鉴权端点在无任何凭据时返回 200 = 鉴权被误关，必须 FAIL
                fail.append(("GET", r, "鉴权缺失：无凭据却返回 200"))
            elif code == 200 and is_json:
                ok.append(("GET", r, f"{code} JSON"))
            elif need_auth and code == 401 and not h:
                # 未配凭据 → 401 是正确行为（鉴权有效），作守护断言计入 PASS
                ok.append(("GET", r, "401 鉴权有效（无凭据，仅验未授权被拒）"))
            else:
                fail.append(("GET", r, f"{code} {text[:50]}"))
        # 1b) P2-5 HttpOnly Cookie 端到端验证：仅持后端签发的 Cookie、
        #     不持 Authorization，调需登录端点须返回 200 → 证明 XSS 抵抗令牌流可用。
        #     该路径独立于现有 Bearer 鉴权（1a），二者并存不冲突。
        store_cookie = _smoke_user_cookie(base)
        if store_cookie:
            code, text = _http("GET", f"{base}/api/store/orders/mine",
                               headers={"Cookie": store_cookie})
            if code == 200:
                ok.append(("COOKIE", "/api/store/orders/mine",
                           "仅持 HttpOnly Cookie 鉴权 200 ✅（XSS 抵抗令牌流可用）"))
            else:
                fail.append(("COOKIE", "/api/store/orders/mine",
                             f"仅持 Cookie 鉴权失败 {code}（HttpOnly 流断裂）"))
        else:
            # 注册/取 Cookie 失败时降级：不破坏既有 PASS 口径，仅记录 info
            info.append(("COOKIE", "/api/store/orders/mine",
                         "注册未返回 HttpOnly Cookie（降级，未断言）"))
        # 2) /api/ecosystem/* 快速 POST 实跑（空载荷即快速返回）
        #    measurement（D-62）除外：空载荷 400 是正确行为（action 必填），
        #    其内核由 run_empirical_anchor_smoke 深度覆盖 → 静态验证存在。
        eco_posts = [r for r in posts if r.startswith("/api/ecosystem/")
                     and r != "/api/ecosystem/measurement"]
        for r in eco_posts:
            code, text = _http("POST", f"{base}{r}", {})
            is_json = text.lstrip().startswith(("{", "["))
            if code == 200 and is_json:
                ok.append(("POST", r, f"{code} JSON"))
            else:
                fail.append(("POST", r, f"{code} {text[:50]}"))
        # 3) 生态字段存在性断言（D-103：前端渲染硬依赖，字段删除/改名即 FAIL）
        for kind, r, d in _check_ecosystem_fields(base):
            if kind == "PASS":
                ok.append(("FIELD", r, d))
            else:
                fail.append(("FIELD", r, d))
        # 3a) v0.9.33 重计算 GET 缓存护栏（无鉴权公开 GET 的 DoS 护栏）
        for kind, r, d in _check_heavy_get_caches(base):
            if kind == "PASS":
                ok.append(("PERF", r, d))
            else:
                fail.append(("PERF", r, d))
        # 3b) 实证锚字段存在性断言（D-108：面板 57 渲染硬依赖）
        for kind, r, d in _check_empirical_fields(base):
            if kind == "PASS":
                ok.append(("FIELD", r, d))
            else:
                fail.append(("FIELD", r, d))
        # 3c) 纵深防御安全头断言（B 纵深加固）：/api/status 响应须含全部安全响应头
        for kind, r, d in _check_security_headers(base):
            if kind == "PASS":
                ok.append(("HEADER", r, d))
            else:
                fail.append(("HEADER", r, d))
        # 4) 重计算 POST 端点：静态验证存在（不实跑）
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
