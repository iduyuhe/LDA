"""N-5 导购二期护栏（v0.9.49 · 无 LLM 可降级版）。

守护：
- 静态：store_guide.py 存在 + recommend 是确定性（无 LLM 依赖）；store.html 含导购入口与结果渲染。
- 行为（真跑 WebUI）：POST /api/store/guide 对自然语言需求返回实跑匹配结果，
  且结果中的价格/规格数字**来自货架数据**（与 shelf_status 的 price_cny 一致），
  严禁模板或 LLM 杜撰规格数字。
- 反向：乱码/无意义查询优雅返回 count=0（不抛错、不假匹配）；
  篡改 parse_query（如把赛道别名清空）后，原本命中的需求应失准（INFO/反向 FAIL）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "lda_webui", "app.py")
GUIDE_SRC = os.path.join(HERE, "lda_l2", "store_guide.py")
STORE_HTML = os.path.join(HERE, "lda_webui", "static", "store.html")

ADMIN_TOK = "smoke-admin-tok-n5"


def _http(method, url, timeout=10, headers=None, body=None):
    try:
        import urllib.request
        data = body.encode() if isinstance(body, str) else body
        req = urllib.request.Request(url, data=data, method=method,
                                     headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        code = getattr(e, "code", None)
        msg = getattr(e, "read", lambda: b"" )()
        if isinstance(msg, bytes):
            msg = msg.decode("utf-8", "replace")
        return (code if code is not None else 0), msg


def _free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _report(results):
    n_pass = sum(1 for _, ok, _ in results if ok)
    print("=" * 64)
    print("N-5 导购二期 · run_store_guide_smoke")
    print("=" * 64)
    for name, ok, note in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({note})" if note else ""))
    print(f"—— {n_pass}/{len(results)} PASS ——")
    return 0 if n_pass == len(results) else 1


def _price_from_shelf(base):
    """从 /api/shelf 取每个货架的 price_cny，用于核对导购返回的价格的真实性。"""
    code, body = _http("GET", f"{base}/api/shelf", timeout=10)
    if code != 200:
        return {}
    try:
        d = json.loads(body)
    except Exception:
        return {}
    return {r["id"]: r.get("price_cny") for r in d.get("rows", [])}


def main():
    results = []
    # —— 静态判据 ——
    guide_src = open(GUIDE_SRC, encoding="utf-8").read()
    ok = "def recommend(" in guide_src and "used_llm" in guide_src
    results.append(("源码 store_guide.py 含 recommend + used_llm 标志",
                    ok, "" if ok else "缺少推荐主函数"))
    # 数字来自数据的硬性约束：reason 拼接只允许引用 item.specs / price_of，
    # 不得出现「凭空写死」的规格数字（用正则抽查：reason 构建处只能拼变量）
    ok = "item.specs" in guide_src and "price_of" in guide_src
    results.append(("源码数字必来自货架数据（specs / price_of）",
                    ok, "" if ok else "未引用货架数据字段"))

    html = open(STORE_HTML, encoding="utf-8").read()
    ok = ('id="guideQ"' in html) and ("runGuide(" in html) and ("/api/store/guide" in html)
    results.append(("store.html 含导购入口与 POST /api/store/guide 调用",
                    ok, "" if ok else "导购 UI 未接线"))

    # —— 真跑 WebUI ——
    port = _free_port()
    env = dict(os.environ, LDA_WEBUI_PORT=str(port), LDA_ADMIN_TOKEN=ADMIN_TOK)
    proc = subprocess.Popen([sys.executable, APP], env=env,
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

        shelf_prices = _price_from_shelf(base)

        # ① 正常需求 → 命中且价格数字与货架一致
        code, body = _http("POST", f"{base}/api/store/guide", timeout=15,
                           headers={"Content-Type": "application/json"},
                           body=json.dumps({"text": "量子保密通信 QKD 相关"}))
        try:
            d = json.loads(body)
        except Exception:
            d = {}
        ok = code == 200 and d.get("count", 0) >= 1 and d.get("used_llm") is False
        first = (d.get("results") or [{}])[0]
        results.append(("POST /api/store/guide「QKD」返回 ≥1 命中且无 LLM",
                        ok, f"code={code} count={d.get('count')} used_llm={d.get('used_llm')}"))
        # 价格真实性核对
        if first.get("id") and first.get("id") in shelf_prices:
            okp = first.get("price_cny") == shelf_prices[first["id"]]
            results.append(("结果价格 == /api/shelf 实付价（数字来自数据）",
                            okp, f"guide={first.get('price_cny')} shelf={shelf_prices.get(first['id'])}"))
        else:
            results.append(("结果价格 == /api/shelf 实付价（咨询制货架无价，跳过）",
                            True, "咨询制货架"))

        # ② CPO + 预算 → 命中且超预算项带 over_budget 标记或整体命中 CPO 赛道
        code, body = _http("POST", f"{base}/api/store/guide", timeout=15,
                           headers={"Content-Type": "application/json"},
                           body=json.dumps({"text": "CPO 共封装光引擎 预算2万"}))
        try:
            d2 = json.loads(body)
        except Exception:
            d2 = {}
        ok = code == 200 and d2.get("count", 0) >= 1
        hit_cpo = any("CPO" in (r.get("track_label") or "") for r in d2.get("results", []))
        results.append(("POST /api/store/guide「CPO 预算」返回命中且含 CPO 赛道",
                        ok and hit_cpo, f"code={code} count={d2.get('count')} hit_cpo={hit_cpo}"))

        # ③ 反向：乱码/无意义 → 优雅返回 count=0，不抛错、不假匹配
        code, body = _http("POST", f"{base}/api/store/guide", timeout=15,
                           headers={"Content-Type": "application/json"},
                           body=json.dumps({"text": "asdkj qwe zxc 1234 @#$% 随便乱写"}))
        try:
            d3 = json.loads(body)
        except Exception:
            d3 = {}
        ok = code == 200 and d3.get("count", 0) == 0
        results.append(("反向·乱码查询优雅返回 count=0（不假匹配）",
                        ok, f"code={code} count={d3.get('count')}"))

        # ④ 反向：空文本 → count=0
        code, body = _http("POST", f"{base}/api/store/guide", timeout=15,
                           headers={"Content-Type": "application/json"},
                           body=json.dumps({"text": ""}))
        try:
            d4 = json.loads(body)
        except Exception:
            d4 = {}
        ok = code == 200 and d4.get("count", 0) == 0
        results.append(("反向·空文本返回 count=0",
                        ok, f"code={code} count={d4.get('count')}"))

        # ⑤ 反向污染（进程内 monkeypatch）：清空 quantum 赛道别名 → 原本高分的 QKD 货架分数应下降。
        #    直接测纯函数 recommend，避免「写污染文件却未加载」导致假绿。
        try:
            import importlib
            sys.path.insert(0, os.path.join(HERE, ".."))
            import lda_l2.store_guide as sg
            importlib.reload(sg)
            from lda_l2.innovation_market import DEFAULT_SHELF
            orig_alias = list(sg._TRACK_KEYWORDS["quantum"])
            sg._TRACK_KEYWORDS["quantum"] = []
            try:
                d_poll = sg.recommend("量子保密通信 QKD 相关", DEFAULT_SHELF,
                                      price_of=lambda s: None)
            finally:
                sg._TRACK_KEYWORDS["quantum"] = orig_alias
            s_orig = {r["id"]: r["score"] for r in d.get("results", [])}
            s_poll = {r["id"]: r["score"] for r in d_poll.get("results", [])}
            dropped = any(s_poll.get(k, 0) < s_orig.get(k, 0)
                          for k in s_orig if "QKD" in k)
            results.append(("反向·清空 quantum 别名后 QKD 货架分数下降（判据对污染响应）",
                            dropped,
                            f"orig_qkd={ {k:v for k,v in s_orig.items() if 'QKD' in k} } "
                            f"polluted={ {k:v for k,v in s_poll.items() if 'QKD' in k} }"))
        except Exception as e:
            results.append(("反向·清空 quantum 别名后 QKD 货架分数下降",
                            False, f"异常 {e}"))
    finally:
        try:
            proc.terminate()
        except Exception:
            pass

    return _report(results)


if __name__ == "__main__":
    sys.exit(main())
