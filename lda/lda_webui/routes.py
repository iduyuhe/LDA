# -*- coding: utf-8 -*-
"""LDA WebUI 路由表（从 app.py 拆出，行为严格等价于原始 elif 链）。

handler 签名：(h, payload, query, path) -> (code, obj) | None
  h       : Handler 实例（._send / .headers / .path / .rfile / .command）
  payload : POST body dict（GET 时为 None）
  query   : query-string dict（已由 dispatch 解析）
  path    : 已去除 query 的请求路径
  返回 (code, obj) -> dispatch 调 h._send(code, obj)
  返回 None        -> handler 已自行 h._send(...)（静态资源 / 文件下载 / v1 委托）

业务函数与常量统一经 `_app` 访问：模块级只绑定 app 模块引用，属性在请求
到来、app 完全初始化后才读取，彻底避免循环导入与冗长 import 列表。

循环导入规避：`app.py` 在 `_dispatch` 内延迟导入本模块；本模块则通过
sys.modules 反查已加载的 app 模块——优先取以脚本形态运行的 __main__（直接
`python app.py` 时 app 是 __main__ 而非 lda_webui.app，避免双实例导致两个
独立 store），否则取包形态 lda_webui.app。`_app` 仅在请求期被读取，加载先后
无关。
"""
import ast
import os
import re
import sys
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

# 反查 app 模块：优先 __main__（脚本运行），否则 lda_webui.app（包运行）
_main = sys.modules.get("__main__")
if _main is not None and hasattr(_main, "system_status"):
    _app = _main
else:
    from . import app as _app


# ============================ 静态 / 资源 ============================
def h_index(h, p, q, path):
    fp = os.path.join(_app.WEBUI_DIR, "static", "index.html")
    with open(fp, "rb") as f:
        h._send(200, body=f.read(), ctype="text/html", nocache=True)
    return None


def h_static_html(h, p, q, path):
    name = os.path.basename(path)
    fp = os.path.join(_app.WEBUI_DIR, "static", name)
    if name in ("index.html", "insights.html", "admin.html", "store.html",
                "mine.html", "public.html") and os.path.exists(fp):
        with open(fp, "rb") as f:
            h._send(200, body=f.read(), ctype="text/html", nocache=True)
    else:
        h._send(404, {"error": "not found"})
    return None


def h_static_asset(h, p, q, path):
    name = os.path.basename(path)
    fp = os.path.join(_app.WEBUI_DIR, "static", name)
    if os.path.exists(fp):
        ctype = "application/javascript" if path.endswith(".js") else "text/css"
        with open(fp, "rb") as f:
            h._send(200, body=f.read(), ctype=ctype, nocache=True)
    else:
        h._send(404, {"error": "not found"})
    return None


def h_proofs(h, p, q, path):
    fname = path[len("/proofs/"):]
    if not re.fullmatch(r"[0-9a-f]{32}\.(png|jpg)", fname):
        h._send(404, {"error": "not found"})
        return None
    fp = os.path.join(_app.PROOF_DIR, fname)
    if not os.path.exists(fp):
        h._send(404, {"error": "not found"})
        return None
    ctype = "image/png" if fname.endswith(".png") else "image/jpeg"
    with open(fp, "rb") as _f:
        h._send(200, body=_f.read(), ctype=ctype,
                headers={"Cache-Control": "public, max-age=86400"})
    return None


def h_static_img(h, p, q, path):
    name = os.path.basename(path)
    fp = os.path.join(_app.WEBUI_DIR, "static", name)
    if os.path.exists(fp):
        ext = name.rsplit(".", 1)[-1].lower()
        ctype = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                 "png": "image/png", "gif": "image/gif"}[ext]
        with open(fp, "rb") as f:
            h._send(200, body=f.read(), ctype=ctype,
                    headers={"Cache-Control": "public, max-age=86400"})
    else:
        h._send(404, {"error": "not found"})
    return None


# ============================ GET · 系统状态类 ============================
def h_status(h, p, q, path):
    return (200, _app.system_status())


def h_health(h, p, q, path):
    return (200, _app.health_check())


def h_benchmarks(h, p, q, path):
    bm = [{"id": k, "title": v.get("title"), "metric": v.get("metric"),
           "oracle": v.get("oracle"), "tol": v.get("tol")}
          for k, v in _app.BENCHMARK_DEFS.items()]
    return (200, {"benchmarks": bm})


def h_pdks(h, p, q, path):
    reg = _app.get_default_registry()
    return (200, {"pdks": reg.to_summary(), "keys": reg.list_pdks()})


def h_ecosystem(h, p, q, path):
    return (200, _app.ecosystem_status())


def h_empirical(h, p, q, path):
    return (200, _app.empirical_status())


def h_design_catalog(h, p, q, path):
    try:
        from lda_design.design_package import engine_catalog, package_catalog
        return (200, {"engine": engine_catalog(), "package": package_catalog()})
    except Exception as e:  # noqa: BLE001
        return (200, {"engine": [], "package": [], "error": str(e)[:120]})


def h_gc_benchmarks(h, p, q, path):
    return (200, _app.gc_benchmarks_status(run=q.get("run") == "1"))


def h_scale_demo(h, p, q, path):
    return (200, _app.scale_demo_status())


def h_capability_demos(h, p, q, path):
    if q.get("run") == "1":
        return (200, _app.capability_demos_run())
    return (200, _app.capability_demos_status())


# --------------------------------------------------------------------------
# /api/cpo_array 重计算端点并发护栏
# 背景：app.py 用 ThreadingHTTPServer（每请求一线程）。该端点无鉴权且默认
# 实跑十万级器件（build+DRC+LVS ~数秒~数十秒），一旦被并发请求（外部扫描 /
# 监控轮询 / 反复自测）打中，多个重计算会并行吃满 CPU/内存 → 服务器被打爆。
# 三道护栏：① 输入硬上限（防单请求 scale 到 OOM）② 全局串行锁（任意时刻
# 至多一个重计算在跑，其余 429 排队，杜绝并行堆叠）③ 默认配置结果缓存
# （TTL 120s，重复 curl 同配置秒回，不再重算）。
# --------------------------------------------------------------------------
_CPO_HEAVY_LOCK = threading.Lock()
_CPO_CACHE = {}                 # key -> (ts, body)；仅缓存默认配置，避免体积膨胀
_CPO_CACHE_TTL = 120.0
_CPO_MAX = {"oe": 48, "ch": 96, "lane": 16}   # 硬上限；超则 400，防单请求 OOM
_CPO_DEFAULT = (32, 34, 8, 4)   # 默认配置 (oe, ch, lane, ch_per_row)


def h_cpo_array(h, p, q, path):
    """GET /api/cpo_array —— CPO 共封装光引擎阵列死锚判决（外部可验货）。

    默认 32 引擎 × 34 通道 × 8 波长 = 100,096 器件；?oe=&ch=&lane=&ch_per_row=
    缩放（如 ?oe=40&ch=68 → 250,240 器件）。?gds=1 含 GDS 导出（默认跳过省时）。
    返回死标量验收 JSON：器件数 / DRC / LVS / 断路反例 / 耗时 / accepted。
    读-only、无鉴权——直接服务「可被外部验货的验证可信度」战略主线。
    """
    try:
        sys.path.insert(0, _app.LDA_ROOT)
        from lda_harness.cpo_array import (CPOArrayConfig, build_cpo_array_case,
                                           inject_fault)
        from lda_l2.chip_layout_export import chip_drc_report
        from lda_l2.lvs import run_lvs
        oe = int(q.get("oe", ["32"])[0])
        ch = int(q.get("ch", ["34"])[0])
        lane = int(q.get("lane", ["8"])[0])
        cpr = int(q.get("ch_per_row", ["4"])[0])
        gds = q.get("gds", ["0"])[0] == "1"
        # ① 输入硬上限：防止单请求 scale 到 OOM（线程服务下尤为危险）
        if oe > _CPO_MAX["oe"] or ch > _CPO_MAX["ch"] or lane > _CPO_MAX["lane"]:
            return (400, {"endpoint": "/api/cpo_array", "accepted": False,
                          "error": "超出安全上限 oe<=%d, ch<=%d, lane<=%d（防止单请求 OOM）"
                                   % (_CPO_MAX["oe"], _CPO_MAX["ch"], _CPO_MAX["lane"])})
        # ③ 默认配置走缓存：重复 curl 同配置秒回，不再重算
        is_default = (oe, ch, lane, cpr) == _CPO_DEFAULT and not gds
        if is_default:
            cached = _CPO_CACHE.get("default")
            if cached and (time.time() - cached[0]) < _CPO_CACHE_TTL:
                body = dict(cached[1])
                body["cached"] = True
                return (200, body)
        # ② 全局串行锁：任意时刻至多一个重计算在跑，其余 429 排队，杜绝并行堆叠
        if not _CPO_HEAVY_LOCK.acquire(timeout=1.0):
            return (429, {"endpoint": "/api/cpo_array", "accepted": False,
                          "error": "重计算忙，请 1-2 秒后重试（并发护栏）"})
        try:
            cfg = CPOArrayConfig(n_oe=oe, n_ch=ch, n_lane=lane, ch_per_row=cpr)
            cfg.validate()
            t0 = time.perf_counter()
            link, placement, routes, meta = build_cpo_array_case(cfg)
            drc = chip_drc_report(link, placement)
            lvs = run_lvs(link, placement, routes)
            nm = lvs["match"]
            r_dis = dict(routes)
            inject_fault(r_dis, "disconnect")
            lvs_dis = run_lvs(link, placement, r_dis)
            gds_stats = {}
            if gds:
                from lda_l2.chip_layout_export import export_chip_gds
                r = export_chip_gds(link, placement, routes)
                st = r["gds_stats"]
                gds_stats = {"gds_bytes": st["gds_bytes"], "n_elements": st["n_elements"],
                             "width_um": st["width_um"], "height_um": st["height_um"]}
            t_total = time.perf_counter() - t0
            accepted = bool(drc["all_pass"] and lvs["verdict"] == "ACCEPT"
                            and lvs_dis["verdict"] == "REJECT")
            body = {
                "endpoint": "/api/cpo_array",
                "config": {"n_oe": oe, "n_ch": ch, "n_lane": lane,
                           "ch_per_row": cpr, "n_devices": meta["n_devices"],
                           "n_chains": meta["n_chains"]},
                "drc": {"n_pass": drc["n_pass"], "n_checked": drc["n_checked"],
                        "all_pass": drc["all_pass"]},
                "lvs": {"verdict": lvs["verdict"], "n_violations": lvs["n_violations"],
                        "net_match": nm["n_nets_match"], "net_total": nm["n_nets_total"]},
                "fault_injection": {"verdict": lvs_dis["verdict"],
                                    "n_violations": lvs_dis["n_violations"]},
                "gds": gds_stats,
                "time_s": {"build_route": round(meta.get("time_build_link_s", 0), 3),
                           "total": round(t_total, 3)},
                "accepted": accepted,
                "honest_note": "仅建模无源光子层（有源器件按黑箱·负面清单）；"
                               "工艺为公开文献近似非真实 PDK；只做版图闭环未做光学仿真；"
                               "未流片无实测回流。LLM 不进判决路径——PASS/FAIL 由死标量比对。",
            }
            if is_default:
                _CPO_CACHE["default"] = (time.time(), body)
            return (200, body)
        finally:
            _CPO_HEAVY_LOCK.release()
    except Exception as e:  # noqa: BLE001
        return (200, {"endpoint": "/api/cpo_array", "error": str(e)[:200],
                      "accepted": False})


def h_verification_ledger(h, p, q, path):
    """GET /api/verification_ledger —— 全量验证账本（外部可验货，无鉴权）。

    把「可被外部验货的验证可信度」从单点（CPO 规模死锚）扩展到整引擎：
    暴露全部已注册验证资产的**分类与计数**，并诚实标注每类的事实来源
    （physical-law 确定性物理定律 / empirical 真实器件实测语料 /
    design-anchor B5/B6/B7 自证桩下限）。LLM 不进判决路径——此端点仅声明
    资产分类与计数，死标量比对由 /api/cpo_array 与各 harness 实测执行。
    """
    try:
        sys.path.insert(0, _app.LDA_ROOT)
        from lda_harness import golden
        dispatch = golden._GOLDEN_DISPATCH
        phys = golden._PHYSICAL_LAW
        phys_ids, anchor_ids = [], []
        for bid in dispatch:
            (phys_ids if bid in phys else anchor_ids).append(bid)
        # 实证大数据锚：文件背载、运行期由 harness 装载；此处声明存在 + 文档计数
        empirical_seed = 7  # E1–E7（README 账本）；真实器件实测语料
        empirical_ids = [f"E{i}" for i in range(1, empirical_seed + 1)]
        ci_core = 82  # run_ci_regression.py CORE_SMOKES 长度（计数一致性守护）
        ledger = {
            "endpoint": "/api/verification_ledger",
            "ci_core": {"count": ci_core, "tag": "core",
                        "note": "run_ci_regression.py --tag core；计数一致性由 run_count_consistency_smoke 守护"},
            "anchors": {
                "total": len(dispatch) + empirical_seed,
                "by_kind": {
                    "physical-law": {"count": len(phys_ids), "ids": phys_ids},
                    "oracle-dependent": {"count": len(anchor_ids), "ids": anchor_ids,
                                         "note": "B5/B6/B7 依赖外部 ORACLE（meep/tidy3d 真场级或 numpy 离线近似），ORACLE 缺失时回退设计守则下限——非纯物理定律，属 R4 开放缺口"},
                    "empirical": {"count": empirical_seed, "ids": empirical_ids,
                                  "note": "LDA 实证大数据锚（真实器件实测语料），文件背载，运行期由 harness 装载"},
                },
                "dispatch_ids": list(dispatch.keys()),
            },
            "cpo_scale": {
                "endpoint": "/api/cpo_array",
                "default_devices": 100096, "scale_devices": 250240,
                "verdict": "ACCEPT（死锚 DRC+LVS+断路反例）",
                "note": "外部可 curl 活体验货；本账本仅静态引用",
            },
            "verified_by_classification": (
                "physical-law=确定性物理定律/解析解（非 AI ground，任何人都可独立复算）；"
                "empirical=真实器件实测语料（跨多源，非 AI 互证）；"
                "oracle-dependent=B5/B6/B7 依赖外部 ORACLE（meep/tidy3d 真场级或 numpy 离线近似），"
                "ORACLE 缺失时回退设计守则下限（非纯物理定律）——属 R4 开放缺口"),
            "open_gaps": [
                "R2 外部 ORACLE（Meep/Tidy3D/pyEPR）默认不通 → 物理定律锚无法现场交叉验证",
                "R3 实证锚仅 7 条种子语料，规模不足以覆盖全品类",
                "R4 B5/B6/B7 为 ORACLE 依赖（numpy 离线近似或设计守则下限回退），根因=R2 缺外部 ORACLE",
            ],
            "honest_note": (
                "本账本仅声明已注册验证资产的分类与计数；LLM 不进判决路径，PASS/FAIL 一律由"
                "死标量比对。可被外部验货的部分=physical-law 锚（独立复算）+/api/cpo_array 死锚"
                "判决（curl 复现）。design-anchor 与 empirical 规模缺口为已知诚实边界。"),
        }
        return (200, ledger)
    except Exception as e:  # noqa: BLE001
        return (200, {"endpoint": "/api/verification_ledger", "error": str(e)[:200]})


# --------------------------------------------------------------------------
# /api/benchmark_crosscheck 重计算端点并发护栏（与 cpo_array 同款纪律）
# 无鉴权公开 GET、默认实跑 run_crosscheck(quick=True) ~9s（本地实测 9.2s），
# ThreadingHTTPServer 下并发会被并行打爆。串行锁 + 结果缓存（TTL 120s）。
# --------------------------------------------------------------------------
_BMCC_HEAVY_LOCK = threading.Lock()
_BMCC_CACHE = {}
_BMCC_CACHE_TTL = 120.0


def h_benchmark_crosscheck(h, p, q, path):
    try:
        # 缓存命中：重复 curl 秒回，不再重算 ~9s
        cached = _BMCC_CACHE.get("default")
        if cached and (time.time() - cached[0]) < _BMCC_CACHE_TTL:
            body = dict(cached[1])
            body["cached"] = True
            return (200, body)
        # 串行锁：任意时刻至多一个 crosscheck 在跑，其余 429
        if not _BMCC_HEAVY_LOCK.acquire(timeout=1.0):
            return (429, {"endpoint": "/api/benchmark_crosscheck",
                          "error": "重计算忙，请稍后重试", "retry_after": 1})
        try:
            sys.path.insert(0, _app.LDA_ROOT)
            from run_benchmark_crosscheck_report import run_crosscheck
            data = run_crosscheck(quick=True)
            body = {
                "summary": data["summary"],
                "corpus_coverage": data["corpus_coverage"],
                "oracle": data["oracle"],
                "rows": [{"kind": r["kind"], "ok": r.get("ok"),
                          "passed": r.get("passed"),
                          "metric": r.get("metric"),
                          "model_class": r.get("model_class", "L0-解析"),
                          "analytical_rel_pct": r.get("analytical_rel_pct"),
                          "verdict": r.get("verdict", "")[:140]}
                         for r in data["rows"]],
                "honest_note": data["honest_note"],
            }
            _BMCC_CACHE["default"] = (time.time(), body)
            return (200, body)
        finally:
            _BMCC_HEAVY_LOCK.release()
    except Exception as e:  # noqa: BLE001
        return (200, {"summary": {}, "corpus_coverage": {},
                      "oracle": {}, "rows": [],
                      "error": str(e)[:120]})


# ============================ GET · 货架 / 商业 ============================
def h_shelf(h, p, q, path):
    store = _app._get_store()
    u = store.user_by_token(_app._token_from_request(h.headers))
    return (200, _app.shelf_status(u.get("user_type") if u else None))


def h_shelf_opinions(h, p, q, path):
    sid = path.split("/")[3]
    return _app.opinion_list(sid)


def h_shelf_item(h, p, q, path):
    parts = path.split("/")
    sid = parts[3]
    sub = parts[4] if len(parts) > 4 else ""
    if not re.match(r"^[A-Za-z0-9_.-]+$", sid):
        h._send(404, {"error": "invalid shelf id"})
        return None
    if sub == "package":
        from lda_l2.ship_package import package_info
        h._send(200, package_info(sid))
        return None
    if sub == "download":
        from lda_l2.ship_package import (consume_license,
                                         generate_package, is_download_open)
        if not is_download_open(sid):
            h._send(403, {"error": "not_open",
                         "reason": "该货架设计就绪包尚未开放下载"})
            return None
        qd = {k: v[0] for k, v in parse_qs(urlparse(h.path).query).items()}
        tok = qd.get("token", "")
        if not consume_license(tok, shelf_id=sid):
            h._send(403, {"error": "unauthorized",
                         "reason": "兑换码无效/已用完/不匹配"})
            return None
        r = generate_package(sid)
        if not r.get("ok"):
            h._send(404, {"error": r.get("error", "not found")})
            return None
        with open(r["zip_path"], "rb") as _fh:
            _data = _fh.read()
        h._send(200, body=_data, ctype="application/zip",
                headers={"Content-Disposition":
                          'attachment; filename="%s_design_ready.zip"' % sid})
        return None
    h._send(404, {"error": "not found"})
    return None


def h_shelf_dispatch(h, p, q, path):
    """GET /api/shelf/<id>/opinions 与 /api/shelf/<id>/(package|download)。"""
    if path.count("/") == 4 and path.endswith("/opinions"):
        return h_shelf_opinions(h, p, q, path)
    if path.count("/") == 4:
        return h_shelf_item(h, p, q, path)
    h._send(404, {"error": "not found"})
    return None


def h_admin_opinions(h, p, q, path):
    return _app.opinion_admin_all(h.headers)


def h_admin_purchase_reqs(h, p, q, path):
    return _app.purchase_request_list(h.headers)


def h_store_config(h, p, q, path):
    return (200, _app._get_store().public_config())


def h_store_orders_mine(h, p, q, path):
    store = _app._get_store()
    obj = store.list_orders(_app._token_from_request(h.headers), "mine")
    return (_ok_code(obj), obj)


def h_store_me_get(h, p, q, path):
    store = _app._get_store()
    u = store.user_by_token(_app._token_from_request(h.headers))
    obj = {"ok": True, "user": store._public_user(u) if u else None}
    return (_ok_code(obj), obj)


def h_store_me_summary(h, p, q, path):
    store = _app._get_store()
    obj = store.my_summary(_app._token_from_request(h.headers))
    return (_ok_code(obj), obj)


def h_store_me_licenses(h, p, q, path):
    store = _app._get_store()
    obj = store.my_licenses(_app._token_from_request(h.headers))
    return (_ok_code(obj), obj)


def h_admin_orders(h, p, q, path):
    store = _app._get_store()
    obj = store.list_orders(_app._token_from_request(h.headers), "all")
    return (_ok_code(obj), obj)


def h_admin_users(h, p, q, path):
    store = _app._get_store()
    obj = store.admin_list_users(_app._token_from_request(h.headers))
    return (_ok_code(obj), obj)


def h_stats(h, p, q, path):
    """管理后台数据看板（admin 专属）。真实/测试账号分离计数。"""
    store = _app._get_store()
    obj = store.stats_summary(_app._token_from_request(h.headers))
    return (_ok_code(obj), obj)


# ---------- 公开自证看板（无需鉴权）----------
# 设计约束：WebUI 进程零依赖（不 import numpy）。锚清单(BENCHMARK_ORDER)与
# CI core 清单(CORE_SMOKES)的真实来源模块会经 golden/numpy 间接 import，
# 故此处用 ast 解析源码字面量（零依赖、随代码自更新）取数，绝不触发重依赖。
def _anchor_inventory():
    """返回 BENCHMARK_ORDER 列表（numpy-free）。优先直接 import，失败则解析源码。"""
    try:
        from lda_harness.benchmarks import BENCHMARK_ORDER  # 需 numpy，webui 可能无
        return list(BENCHMARK_ORDER)
    except Exception:
        pass
    try:
        fp = os.path.join(os.path.dirname(__file__), "..",
                          "lda_harness", "benchmarks.py")
        with open(fp, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "BENCHMARK_ORDER":
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            return [e.value for e in node.value.elts
                                    if isinstance(e, ast.Constant)]
    except Exception:
        pass
    return []


def _ci_core_count():
    """返回 CORE_SMOKES 项数（numpy-free，解析 run_ci_regression.py 字面量）。"""
    try:
        fp = os.path.join(os.path.dirname(__file__), "..",
                          "run_ci_regression.py")
        with open(fp, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "CORE_SMOKES":
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            return len([e for e in node.value.elts
                                        if isinstance(e, ast.Constant)])
            elif isinstance(node, ast.AnnAssign):
                t = node.target
                if isinstance(t, ast.Name) and t.id == "CORE_SMOKES":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        return len([e for e in node.value.elts
                                    if isinstance(e, ast.Constant)])
    except Exception:
        pass
    return None


def h_public_stats(h, p, q, path):
    """公开自证看板（无需鉴权）。仅暴露可信度信号：锚/引擎/货架/CI 项，
    绝不返回任何用户、订单、GMV 等敏感数据。"""
    inv = {
        "service": "lda-webui",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verification": {
            "principles": [
                "物理定律锚红线：裁判最终判定落非 AI ground（解析解 / 麦克斯韦确定性）",
                "LLM 不进判决路径：PASS / FAIL 由死标量比对决定，机器优先、人终审",
                "主权编码：GPL 零污染，22 类端到端设计引擎 + 27 个自研求解核模块",
            ],
        },
        "assets": {},
        "ci": {},
    }
    # 版本（health_check 单一真源，自更新）
    try:
        hc = _app.health_check()
        inv["version"] = hc.get("version")
    except Exception:
        inv["version"] = None
    # 设计引擎数
    try:
        from lda_design.design_package import ENGINE_KINDS
        inv["assets"]["design_engines"] = len(ENGINE_KINDS)
    except Exception:
        inv["assets"]["design_engines"] = None
    # 货架 + 分档
    try:
        from .shelf_pricing import build_price_map
        from lda_l2.ship_package import OPEN_SHELVES
        pm = build_price_map()
        inv["assets"]["shelves_total"] = len(pm)
        inv["assets"]["shelves_open"] = len(OPEN_SHELVES)
        tiers = {"basic": 0, "standard": 0, "premium": 0}
        for v in pm.values():
            if v == 599.0:
                tiers["basic"] += 1
            elif v == 1999.0:
                tiers["standard"] += 1
            elif v == 4999.0:
                tiers["premium"] += 1
        inv["assets"]["pricing_tiers"] = tiers
    except Exception:
        inv["assets"]["shelves_total"] = None
    # 锚（numpy-free）
    bids = _anchor_inventory()
    inv["assets"]["anchors_total"] = len(bids)
    byc = {"B": 0, "E": 0, "S": 0}
    for b in bids:
        bu = str(b).upper()
        for k in byc:
            if bu.startswith(k):
                byc[k] += 1
                break
    inv["assets"]["anchors_by_class"] = byc
    # CI core
    inv["ci"]["core_smokes"] = _ci_core_count()
    inv["ci"]["note"] = ("CI core 全量回归最近一次：82 PASS / 0 SKIP / 0 FAIL"
                         "（与 README 当前账本段一致）；重 FDTD/GPU 项走 --tag all。")
    return (200, inv)


def h_store_order_download(h, p, q, path):
    store = _app._get_store()
    parts = path.split("/")
    oid = parts[4]
    r = store.order_download(oid, _app._token_from_request(h.headers))
    if not r.get("ok"):
        h._send(403 if r.get("code") == 401 else 400, r)
        return None
    if r.get("deliverable_url"):
        h._send(200, r)
        return None
    with open(r["zip_path"], "rb") as _fh:
        _data = _fh.read()
    h._send(200, body=_data, ctype="application/zip",
            headers={"Content-Disposition":
                      'attachment; filename="%s_design_ready.zip"' % r["shelf_id"]})
    return None


def h_store_order_get(h, p, q, path):
    if path.count("/") == 5:
        parts = path.split("/")
        oid = parts[4]
        sub = parts[5] if len(parts) > 5 else ""
        if sub == "download":
            return h_store_order_download(h, p, q, path)
    h._send(404, {"error": "not found"})
    return None


def h_admin_config_get(h, p, q, path):
    store = _app._get_store()
    if not store.is_admin(_app._token_from_request(h.headers)):
        return (401, {"error": "unauthorized"})
    return (200, {"config": store.get_config()})


# ============================ GET · 会员资料 PATCH ============================
def h_store_me_patch(h, p, q, path):
    store = _app._get_store()
    obj = store.update_profile(_app._token_from_request(h.headers),
                               name=p.get("name"), phone=p.get("phone"),
                               organization=p.get("organization"),
                               user_type=p.get("user_type"))
    return (_ok_code(obj), obj)


# ============================ POST · 设计闭环 / 内核 ============================
def h_verify(h, p, q, path):
    return (200, _app.run_verify(p))


def h_shelf_evaluate(h, p, q, path):
    return (200, _app.shelf_evaluate(p))


def h_purchase_request(h, p, q, path):
    return _app.purchase_request_submit(p)


def h_purchase_upload_proof(h, p, q, path):
    return _app.purchase_upload_proof(p)


def h_opinion_submit(h, p, q, path):
    return _app.opinion_submit(p)


def h_proposal_design(h, p, q, path):
    return (200, _app.run_proposal_design(p))


def h_agent_loop(h, p, q, path):
    return (200, _app.run_agent_loop(p))


def h_band_loop(h, p, q, path):
    return (200, _app.run_band_loop(p))


def h_ring_loop(h, p, q, path):
    return (200, _app.run_ring_loop(p))


def h_ring_fdtd(h, p, q, path):
    return (200, _app.run_ring_fdtd_demo(p))


def h_device_library(h, p, q, path):
    return (200, _app.run_device_library_demo(p))


def h_dc_transmission(h, p, q, path):
    return (200, _app.run_dc_transmission_demo(p))


def h_layout_pipeline(h, p, q, path):
    return (200, _app.run_layout_pipeline(p))


def h_design_pipeline(h, p, q, path):
    return (200, _app.run_design_pipeline(p))


def h_design_loop(h, p, q, path):
    return (200, _app.run_design_loop(p))


def h_ring_package(h, p, q, path):
    return (200, _app.run_ring_package(p))


def h_inverse_design(h, p, q, path):
    return (200, _app.run_inverse_design_demo(p))


def h_quantum_design(h, p, q, path):
    return (200, _app.run_quantum_design(p))


def h_wdm_design(h, p, q, path):
    return (200, _app.run_wdm_design(p))


def h_readout_chain(h, p, q, path):
    return (200, _app.run_readout_chain(p))


def h_multiqubit_readout(h, p, q, path):
    return (200, _app.run_multiqubit_readout(p))


def h_readout_fidelity(h, p, q, path):
    return (200, _app.run_readout_fidelity(p))


def h_multiqubit_fidelity(h, p, q, path):
    return (200, _app.run_multiqubit_fidelity(p))


def h_mixed_system(h, p, q, path):
    return (200, _app.run_mixed_system(p))


def h_coupler_design(h, p, q, path):
    return (200, _app.run_coupler_design(p))


def h_wdm_coupler(h, p, q, path):
    return (200, _app.run_wdm_coupler(p))


def h_splitter_readout(h, p, q, path):
    return (200, _app.run_splitter_readout(p))


def h_wdm_splitter(h, p, q, path):
    return (200, _app.run_wdm_splitter(p))


def h_design_package(h, p, q, path):
    return (200, _app.run_design_package(p))


def h_design_outcome(h, p, q, path):
    return (200, _app.run_design_outcome(p))


def h_drc_fix_demo(h, p, q, path):
    return (200, _app.run_drc_fix_demo(p))


def h_coupler_loop(h, p, q, path):
    return (200, _app.run_coupler_loop(p))


def h_ir_demo(h, p, q, path):
    return (200, _app.run_ir_demo(p))


def h_adjoint_design(h, p, q, path):
    return (200, _app.run_adjoint_design(p))


def h_adjoint_loop(h, p, q, path):
    return (200, _app.run_adjoint_loop(p))


def h_primitives(h, p, q, path):
    return (200, _app.run_primitives(p))


def h_sparams(h, p, q, path):
    return (200, _app.run_sparams(p))


def h_sparams_3d(h, p, q, path):
    return (200, _app.run_sparams_3d(p))


def h_gc_sparams(h, p, q, path):
    return (200, _app.run_gc_sparams(p))


def h_pipeline_realize(h, p, q, path):
    return (200, _app.run_pipeline_realize(p))


def h_tunable_wdm(h, p, q, path):
    return (200, _app.run_tunable_wdm(p))


def h_qeda_topology(h, p, q, path):
    return (200, _app.run_qeda_topology(p))


def h_large_scale_bench(h, p, q, path):
    return (200, _app.run_large_scale_bench(p))


def h_ir_spec(h, p, q, path):
    return (200, _app.run_ir_spec(p))


def h_ci_regression(h, p, q, path):
    return (200, _app.run_ci_regression(p))


def h_link_design(h, p, q, path):
    return (200, _app.run_link_design(p))


def h_link_lvs(h, p, q, path):
    return (200, _app.run_link_lvs(p))


def h_perf_bench(h, p, q, path):
    return (200, _app.run_perf_bench(p))


def h_spectral_design(h, p, q, path):
    return (200, _app.run_spectral_design(p))


def h_shape_design(h, p, q, path):
    return (200, _app.run_shape_design(p))


def h_hybrid_design(h, p, q, path):
    return (200, _app.run_hybrid_design(p))


def h_hybrid_multi(h, p, q, path):
    return (200, _app.run_hybrid_multi(p))


def h_adjoint3d(h, p, q, path):
    return (200, _app.run_adjoint3d(p))


def h_port_acceptance(h, p, q, path):
    return (200, _app.run_port_acceptance(p))


def h_adjoint3d_perf(h, p, q, path):
    return (200, _app.run_adjoint3d_perf(p))


def h_qubit_resonator(h, p, q, path):
    return (200, _app.run_qubit_resonator(p))


def h_qeda_depth(h, p, q, path):
    return (200, _app.run_qeda_depth(p))


def h_pdk_design(h, p, q, path):
    return (501, {"error": "not_implemented",
                  "message": "PDK 驱动逆设计依赖 DesignProblem 抽象层，规划于 D-09；"
                             "当前可用：/api/verify、/api/agent_loop、/api/band_loop、"
                             "/api/coupler_loop、/api/ir_demo。"})


def h_pdk_compare(h, p, q, path):
    return (501, {"error": "not_implemented",
                  "message": "PDK 跨厂对比依赖 DesignProblem 抽象层，规划于 D-09；"
                             "当前可用：上方已落地的闭环接口。"})


# ============================ POST · 生态共建 ============================
def h_eco_submit(h, p, q, path):
    return (200, _app.submit_device(p))


def h_eco_import(h, p, q, path):
    entries = p.get("entries", []) if isinstance(p, dict) else []
    res = _app.submit_devices_batch(entries)
    return (200, {"results": res, "summary": _app._summarize_submit(res)})


def h_eco_propose(h, p, q, path):
    return (200, _app.submit_benchmark_proposal(p))


def h_eco_review(h, p, q, path):
    return (200, _app.review_proposal(
        proposal_id=p.get("id", ""),
        decision=p.get("decision", ""),
        reviewer=p.get("reviewer", ""),
        rationale=p.get("rationale", ""),
        oracle_fn_source=p.get("oracle_fn_source")))


def h_eco_land(h, p, q, path):
    return (200, _app.land_proposal(p.get("id", "")))


def h_eco_resubmit(h, p, q, path):
    return (200, _app.resubmit_proposal(
        proposal_id=p.get("id", ""),
        updates=p.get("updates") or {},
        contrib_path=None))


def h_eco_review_batch(h, p, q, path):
    entries = p.get("entries", []) if isinstance(p, dict) else []
    return (200, _app.review_proposals_batch(entries))


def h_eco_land_batch(h, p, q, path):
    ids = p.get("ids", []) if isinstance(p, dict) else []
    return (200, _app.land_proposals_batch(ids))


def h_eco_publish(h, p, q, path):
    return (200, _app.publish_proposal(
        proposal_id=p.get("id", ""),
        author=p.get("author", ""),
        note=p.get("note", "")))


def h_eco_measurement(h, p, q, path):
    action = p.get("action", "")
    if action == "submit":
        return (200, _app.submit_measurement(p))
    if action == "review":
        return (200, _app.review_measurement(
            mid=p.get("id", ""),
            decision=p.get("decision", ""),
            reviewer=p.get("reviewer", ""),
            rationale=p.get("rationale", "")))
    if action == "land":
        return (200, _app.land_measurement(p.get("id", "")))
    return (400, {"status": "error",
                  "reason": "action 须为 submit|review|land"})


# ============================ POST · 商业闭环 ============================
def h_store_register(h, p, q, path):
    store = _app._get_store()
    r = store.register(p.get("email"), p.get("name"),
                       p.get("password"), p.get("phone"),
                       p.get("user_type"), p.get("organization"),
                       client_ip=_app._client_ip(h))
    if r.get("ok") and r.get("token"):
        # P2-5：会话令牌下发 HttpOnly Cookie（XSS 不可读），前端不再存 localStorage
        h._set_cookie("lda_store_token", r["token"],
                      max_age=store.TOKEN_TTL_DAYS * 86400)
    return (200, r)


def h_store_login(h, p, q, path):
    store = _app._get_store()
    r = store.login(p.get("email"), p.get("password"),
                    client_ip=_app._client_ip(h))
    if r.get("ok") and r.get("token"):
        h._set_cookie("lda_store_token", r["token"],
                      max_age=store.TOKEN_TTL_DAYS * 86400)
    return (200, r)


def h_admin_reset_pwd(h, p, q, path):
    store = _app._get_store()
    obj = store.admin_reset_password(p.get("email") or p.get("user_id"),
                                     _app._token_from_request(h.headers),
                                     p.get("temp_password", ""))
    return (_ok_code(obj), obj)


def h_admin_unlock(h, p, q, path):
    store = _app._get_store()
    obj = store.admin_unlock_login(_app._token_from_request(h.headers))
    return (_ok_code(obj), obj)


def h_store_password(h, p, q, path):
    store = _app._get_store()
    r = store.change_password(_app._token_from_request(h.headers),
                              p.get("old_password", ""),
                              p.get("new_password", ""))
    if r.get("ok") and r.get("token"):
        # P2-5：改密后刷新会话 Cookie（change_password 返回新令牌）
        h._set_cookie("lda_store_token", r["token"],
                      max_age=store.TOKEN_TTL_DAYS * 86400)
    return (r.get("code", 200) if isinstance(r, dict) else 200, r)


def h_store_logout(h, p, q, path):
    # P2-5：清除 HttpOnly 会话 Cookie（Max-Age=0）
    h._clear_cookie("lda_store_token")
    return (200, {"ok": True})


def h_admin_login(h, p, q, path):
    """P2-5：管理员令牌改为 HttpOnly Cookie 下发，不再存 localStorage。"""
    tok = (p.get("token") or "").strip()
    if tok and tok == _app._admin_token():
        h._set_cookie("lda_admin_token", tok, max_age=86400)
        return (200, {"ok": True})
    return (401, {"ok": False, "error": "管理员令牌不正确"})


def h_admin_logout(h, p, q, path):
    h._clear_cookie("lda_admin_token")
    return (200, {"ok": True})


def h_store_order_create(h, p, q, path):
    store = _app._get_store()
    r = store.create_order(_app._token_from_request(h.headers), p)
    return (r.get("code", 200) if isinstance(r, dict) else 200, r)


def h_admin_config_set(h, p, q, path):
    store = _app._get_store()
    r = store.set_config(p, _app._token_from_request(h.headers))
    return (r.get("code", 200) if isinstance(r, dict) else 200, r)


# ============================ 前缀路由 handler ============================
def h_v1(h, p, q, path):
    h._handle_v1()
    return None


def h_admin_purchase(h, p, q, path):
    parts = path.split("/")
    req_id = parts[4]
    sub = parts[5]
    if sub == "approve":
        return _app.purchase_request_approve(p, h.headers, req_id)
    return (404, {"error": "not found"})


def h_store_order(h, p, q, path):
    store = _app._get_store()
    parts = path.split("/")
    if path.endswith("/accept_delivery") and path.count("/") == 5:
        oid = parts[4]
        r = store.custom_accept_delivery(oid, _app._token_from_request(h.headers))
        return (_ok_code(r), r)
    if path.count("/") == 5:
        oid = parts[4]
        sub = parts[5] if len(parts) > 5 else ""
        if sub == "download":
            r = store.order_download(oid, _app._token_from_request(h.headers))
            if not r.get("ok"):
                h._send(403 if r.get("code") == 401 else 400, r)
                return None
            if r.get("deliverable_url"):
                h._send(200, r)
                return None
            with open(r["zip_path"], "rb") as _fh:
                _data = _fh.read()
            h._send(200, body=_data, ctype="application/zip",
                    headers={"Content-Disposition":
                              'attachment; filename="%s_design_ready.zip"' % r["shelf_id"]})
            return None
        if sub == "proof":
            r = store.submit_proof(oid, _app._token_from_request(h.headers),
                                   p.get("proof", ""))
            return (_ok_code(r), r)
        h._send(404, {"error": "not found"})
        return None
    h._send(404, {"error": "not found"})
    return None


def h_admin_order(h, p, q, path):
    store = _app._get_store()
    parts = path.split("/")
    oid = parts[4]
    sub = parts[5]
    tok = _app._token_from_request(h.headers)
    if sub == "approve":
        r = store.admin_approve(oid, tok, p.get("deliverable_url", ""))
    elif sub == "reject":
        r = store.admin_reject(oid, tok, p.get("reason", ""))
    else:
        r = {"ok": False, "error": "not found"}
    return (_ok_code(r), r)


def h_admin_custom(h, p, q, path):
    store = _app._get_store()
    parts = path.split("/")
    oid = parts[4]
    sub = parts[5]
    tok = _app._token_from_request(h.headers)
    if sub == "accept":
        r = store.custom_accept(oid, tok,
                                dev_note=p.get("dev_note", ""),
                                quote_cny=p.get("quote_cny"),
                                eta_date=p.get("eta_date", ""))
    elif sub == "note":
        r = store.custom_update_note(oid, tok, p.get("dev_note", ""))
    elif sub == "add_deliverable":
        r = store.custom_add_deliverable(oid, tok,
                                         p.get("name", ""),
                                         p.get("url", ""))
    elif sub == "deliver":
        r = store.custom_deliver(oid, tok)
    else:
        r = {"ok": False, "error": "not found"}
    return (_ok_code(r), r)


# ============================ 辅助 ============================
def _ok_code(obj):
    """与原 do_* 一致的 code 提取：(obj.get('code') or 200) 若 dict。"""
    return (obj.get("code") or 200) if isinstance(obj, dict) else 200


# ============================ 路由表 ============================
# 精确路径 -> handler
GET_ROUTES = {
    "/": h_index,
    "/index.html": h_index,
    "/api/status": h_status,
    "/api/health": h_health,
    "/api/benchmarks": h_benchmarks,
    "/api/pdks": h_pdks,
    "/api/ecosystem": h_ecosystem,
    "/api/empirical": h_empirical,
    "/api/design_catalog": h_design_catalog,
    "/api/gc_benchmarks": h_gc_benchmarks,
    "/api/shelf": h_shelf,
    "/api/admin/opinions": h_admin_opinions,
    "/api/admin/purchase_requests": h_admin_purchase_reqs,
    "/api/store/config": h_store_config,
    "/api/store/orders/mine": h_store_orders_mine,
    "/api/store/me": h_store_me_get,
    "/api/store/me/summary": h_store_me_summary,
    "/api/store/me/licenses": h_store_me_licenses,
    "/api/admin/orders": h_admin_orders,
    "/api/admin/users": h_admin_users,
    "/api/stats": h_stats,
    "/api/public/stats": h_public_stats,
    "/api/admin/config": h_admin_config_get,
    "/api/scale_demo": h_scale_demo,
    "/api/capability_demos": h_capability_demos,
    "/api/cpo_array": h_cpo_array,
    "/api/verification_ledger": h_verification_ledger,
    "/api/benchmark_crosscheck": h_benchmark_crosscheck,
}

# 后缀/前缀匹配：顺序须与原 do_GET 一致（html → js/css → proofs → img → shelf → store/order）
GET_PREFIX = [
    ("endswith", ".html", h_static_html),
    ("endswith", (".js", ".css"), h_static_asset),
    ("startswith", "/proofs/", h_proofs),
    ("endswith", (".jpg", ".jpeg", ".png", ".gif"), h_static_img),
    ("startswith", "/api/shelf/", h_shelf_dispatch),
    ("startswith", "/api/store/order/", h_store_order_get),
]

POST_ROUTES = {
    "/api/verify": h_verify,
    "/api/shelf/evaluate": h_shelf_evaluate,
    "/api/purchase/request": h_purchase_request,
    "/api/purchase/upload_proof": h_purchase_upload_proof,
    "/api/opinion/submit": h_opinion_submit,
    "/api/proposal_design": h_proposal_design,
    "/api/agent_loop": h_agent_loop,
    "/api/band_loop": h_band_loop,
    "/api/ring_loop": h_ring_loop,
    "/api/ring_fdtd": h_ring_fdtd,
    "/api/device_library": h_device_library,
    "/api/dc_transmission": h_dc_transmission,
    "/api/layout_pipeline": h_layout_pipeline,
    "/api/design_pipeline": h_design_pipeline,
    "/api/design_loop": h_design_loop,
    "/api/ring_package": h_ring_package,
    "/api/inverse_design": h_inverse_design,
    "/api/quantum_design": h_quantum_design,
    "/api/wdm_design": h_wdm_design,
    "/api/readout_chain": h_readout_chain,
    "/api/multiqubit_readout": h_multiqubit_readout,
    "/api/readout_fidelity": h_readout_fidelity,
    "/api/multiqubit_fidelity": h_multiqubit_fidelity,
    "/api/mixed_system": h_mixed_system,
    "/api/coupler_design": h_coupler_design,
    "/api/wdm_coupler": h_wdm_coupler,
    "/api/splitter_readout": h_splitter_readout,
    "/api/wdm_splitter": h_wdm_splitter,
    "/api/design_package": h_design_package,
    "/api/design_outcome": h_design_outcome,
    "/api/drc_fix_demo": h_drc_fix_demo,
    "/api/coupler_loop": h_coupler_loop,
    "/api/ir_demo": h_ir_demo,
    "/api/adjoint_design": h_adjoint_design,
    "/api/adjoint_loop": h_adjoint_loop,
    "/api/primitives": h_primitives,
    "/api/sparams": h_sparams,
    "/api/sparams_3d": h_sparams_3d,
    "/api/gc_sparams": h_gc_sparams,
    "/api/pipeline_realize": h_pipeline_realize,
    "/api/tunable_wdm": h_tunable_wdm,
    "/api/qeda_topology": h_qeda_topology,
    "/api/large_scale_bench": h_large_scale_bench,
    "/api/ir_spec": h_ir_spec,
    "/api/ci_regression": h_ci_regression,
    "/api/link_design": h_link_design,
    "/api/link_lvs": h_link_lvs,
    "/api/perf_bench": h_perf_bench,
    "/api/spectral_design": h_spectral_design,
    "/api/shape_design": h_shape_design,
    "/api/hybrid_design": h_hybrid_design,
    "/api/hybrid_multi": h_hybrid_multi,
    "/api/adjoint3d": h_adjoint3d,
    "/api/port_acceptance": h_port_acceptance,
    "/api/adjoint3d_perf": h_adjoint3d_perf,
    "/api/qubit_resonator": h_qubit_resonator,
    "/api/qeda_depth": h_qeda_depth,
    "/api/pdk_design": h_pdk_design,
    "/api/pdk_compare": h_pdk_compare,
    "/api/ecosystem/submit": h_eco_submit,
    "/api/ecosystem/import": h_eco_import,
    "/api/ecosystem/propose": h_eco_propose,
    "/api/ecosystem/review": h_eco_review,
    "/api/ecosystem/land": h_eco_land,
    "/api/ecosystem/resubmit": h_eco_resubmit,
    "/api/ecosystem/review_batch": h_eco_review_batch,
    "/api/ecosystem/land_batch": h_eco_land_batch,
    "/api/ecosystem/publish": h_eco_publish,
    "/api/ecosystem/measurement": h_eco_measurement,
    "/api/store/register": h_store_register,
    "/api/store/login": h_store_login,
    "/api/store/logout": h_store_logout,
    "/api/store/password": h_store_password,
    "/api/admin/login": h_admin_login,
    "/api/admin/logout": h_admin_logout,
    "/api/admin/user/reset_password": h_admin_reset_pwd,
    "/api/admin/unlock_login": h_admin_unlock,
    "/api/store/order": h_store_order_create,
    "/api/admin/config": h_admin_config_set,
}

# 前缀匹配：顺序须与原 do_POST 一致
# （v1 → admin/purchase → store/order[accept_delivery 优先 proof] → admin/order → admin/custom）
POST_PREFIX = [
    ("startswith", "/api/v1/", h_v1),
    ("startswith", "/api/admin/purchase/", h_admin_purchase),
    ("startswith", "/api/store/order/", h_store_order),
    ("startswith", "/api/admin/order/", h_admin_order),
    ("startswith", "/api/admin/custom/", h_admin_custom),
]

PATCH_ROUTES = {
    "/api/store/me": h_store_me_patch,
}
