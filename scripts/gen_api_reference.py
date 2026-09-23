"""从 `lda_webui/routes.py` 路由表**自动生成** WebUI REST API 参考（P2-T2.3 · 指标 M8）。

为什么是生成而不是手写
----------------------
手写的端点清单必然漂移（血案：仓库根 `LDA_D-13_WebUI内网部署说明.md` 停在
B1-B11 / 七面板 / 无鉴权，而真实已是 469 锚 / 57 面板 / 有登录闸门）。
本脚本把**唯一真相源**钉在代码上：

* 端点集合 ← `routes.py` 的 `GET_ROUTES` / `POST_ROUTES` / `PATCH_ROUTES`
  / `GET_PREFIX` / `POST_PREFIX`（PATCH 虽只有精确表，但 `app.py:do_PATCH` 真分发）
* 用途描述 ← 优先级阶梯（**全部来自代码，零手写**）：
    ① handler 自己的 docstring
    ② handler 转调的业务 `_app.<fn>` 的 docstring（自动跳过 `_` 私有基建助手，
       并优先取出现在 `return` 表达式里的那个 ⇒ 避开 `_get_store` 这类陷阱）
    ③ handler 调 `_app._get_store().<method>` ⇒ 取 `store.py` 同名方法的 docstring
       （store / admin / 订单整簇端点走这条）
    ④ 都没有 ⇒ 如实标「（未描述）」**并计入缺口**，不编造
* 请求参数 ← `ast` 扫 handler 体的 `p.get("x")`；无则回退业务函数的首参 `.get`
* 鉴权要求 ← 是否属 `HEAVY_POST_PATHS`（登录闸门，见 `routes.py:_heavy_guard`）
* 二进制响应 ← handler 是否调用 `_send(..., body=...)`（全仓唯一二进制端点）

输出两份等价产物（同一函数生成，杜绝双口径）：
  * `docs/API_REFERENCE.md`  —— 人读
  * `docs/api_reference.json` —— 机器读（常驻门禁 `run_p2_usability_smoke.py` 用它
    做「重新生成 == 磁盘文件」的同源断言，漂移即红）

用法（仓库根）::

    python scripts/gen_api_reference.py            # 写入 docs/
    python scripts/gen_api_reference.py --check    # 只比对，不写（CI 用）

红线：本脚本只做静态提取与格式化，不做任何判决；LLM 不进路径。
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent            # 仓库根
_LDA = _ROOT / "lda"            # lda 包根（扁平 lda_* 命名空间）
if str(_LDA) not in sys.path:
    sys.path.insert(0, str(_LDA))

_ROUTES_PY = _LDA / "lda_webui" / "routes.py"
_APP_PY = _LDA / "lda_webui" / "app.py"
_STORE_PY = _LDA / "lda_webui" / "store.py"

# `_app.<fn>` 里有一部分是「再导出」的业务函数（真定义不在 app.py），例如
# `_app.submit_device` 实为 `lda_pdk/submit.py:196`。这些模块一并进索引，
# 描述仍取自代码 docstring（**不手写**）；索引名冲突由门禁断言兜底。
_EXTRA_BUSINESS_FILES = [
    _LDA / "lda_pdk" / "submit.py",
    _LDA / "lda_pdk" / "review.py",
    _LDA / "lda_pdk" / "publish.py",
    _LDA / "lda_pdk" / "empirical.py",
    _LDA / "lda_l2" / "pdk.py",
]

# 基建助手黑名单：这些 `_app.*` 是通用管道（取 store / 令牌 / 编码），
# 不是端点的业务语义来源。被误取会让「/api/admin/config → 惰性加载商业闭环模块」
# 这种离谱描述进参考（开发期实测踩到）。
_INFRA_APP_NAMES = {
    "_get_store", "_admin_token", "_check_admin", "_token_from_request",
    "_ok_code", "_json", "_send", "_now_iso", "_h",
}


# ---------------------------------------------------------------- ast 工具
def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _func_index(mod: ast.Module) -> dict:
    """顶层函数名 -> FunctionDef 节点。"""
    return {n.name: n for n in mod.body if isinstance(n, ast.FunctionDef)}


def _docstring(node: ast.FunctionDef) -> str:
    d = ast.get_docstring(node) or ""
    return d.strip()


def _first_line(text: str) -> str:
    for ln in text.splitlines():
        ln = ln.strip()
        if ln:
            return ln
    return ""


def _full_doc(text: str) -> str:
    """把 docstring 折成单行（供表格用），保留全部信息。"""
    parts = [p.strip() for p in text.splitlines()]
    return " ".join(p for p in parts if p)


def _app_calls(node: ast.FunctionDef) -> list:
    """按源码出现顺序收集 `_app.<name>` 调用；`return` 里的优先。

    返回 [(name, in_return_bool)]，已剔除私有 / 基建名。
    """
    ret_nodes = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Return) and sub.value is not None:
            for inner in ast.walk(sub.value):
                ret_nodes.add(id(inner))
    out, seen = [], set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        fn = sub.func
        if not (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name)
                and fn.value.id == "_app"):
            continue
        name = fn.attr
        if name.startswith("_") or name in _INFRA_APP_NAMES:
            continue
        if name in seen:
            continue
        seen.add(name)
        out.append((name, id(sub) in ret_nodes))
    # return 里的排前面
    out.sort(key=lambda t: (not t[1],))
    return out


def _store_calls(node: ast.FunctionDef) -> list:
    """收集经 `store = _app._get_store()` 后调用的 `<store>.<method>` 名。

    store / admin / 订单类 handler 不直接调业务函数，而是
    `store = _app._get_store()` 再 `store.login(p)` 这种「取模块再调方法」形态 ——
    业务语义在 store.py 的方法 docstring 里，必须单独解析，否则整簇端点无描述
    （实测：不解析时 45 条未描述里 24 条属此簇）。
    """
    locals_ = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assign) and isinstance(sub.value, ast.Call):
            f = sub.value.func
            if (isinstance(f, ast.Attribute) and f.attr == "_get_store"
                    and isinstance(f.value, ast.Name) and f.value.id == "_app"):
                for t in sub.targets:
                    if isinstance(t, ast.Name):
                        locals_.add(t.id)
    out = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        fn = sub.func
        if not isinstance(fn, ast.Attribute):
            continue
        recv = fn.value
        if (isinstance(recv, ast.Name) and recv.id in locals_
                and not fn.attr.startswith("_") and fn.attr not in out):
            out.append(fn.attr)
    return out


def _payload_keys(node: ast.FunctionDef, receiver: str | None) -> list:
    """扫 `<receiver>.get("key")` 字面量键（receiver=None 时扫任意 .get）。

    只取字符串字面量键；跳过嵌套函数体，避免把内部实现细节当契约。
    """
    keys, order = set(), []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        fn = sub.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "get"):
            continue
        if receiver is not None:
            v = fn.value
            if not (isinstance(v, ast.Name) and v.id == receiver):
                continue
        if len(sub.args) != 1 or not isinstance(sub.args[0], ast.Constant):
            continue
        k = sub.args[0].value
        if isinstance(k, str) and k and k not in keys:
            keys.add(k)
            order.append(k)
    return order


def _first_param_name(node: ast.FunctionDef) -> str | None:
    a = node.args
    pos = list(a.posonlyargs) + list(a.args)
    return pos[0].arg if pos else None


def _is_binary_send(node: ast.FunctionDef) -> bool:
    """handler 是否走 `_send(..., body=...)`（二进制响应）。"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            for kw in sub.keywords:
                if kw.arg == "body" and not (isinstance(kw.value, ast.Constant)
                                             and kw.value.value is None):
                    return True
    return False


def wildcard_patterns(mode: str, pat) -> list:
    """把一条前缀/后缀路由规则展开成**对外的模式串**列表 —— 全库唯一定义处。

    门禁 `lda/run_p2_usability_smoke.py` 直接 import 本函数做「参考 ≡ 路由表」的
    双向比对，杜绝两处各写一遍口径（本仓铁律：判据与生产共用同一份定义）。

    * `startswith "/api/v1/"`       ⇒ `["/api/v1/**"]`
    * `endswith ".html"`            ⇒ `["*.html"]`
    * `endswith (".js", ".css")`    ⇒ `["*.js", "*.css"]`（**逐后缀各一行**）

    🔴 为何逐后缀展开：初版把元组 `join` 成一行 `".js / .css/*"` —— 那是个**不存在的
    路径**，人照抄必错，机器也没法跟路由表对齐（门禁实测报「漏 4 条通配」即此）。
    """
    pats = (pat,) if isinstance(pat, str) else tuple(pat)
    if mode == "startswith":
        return [p.rstrip("/") + "/**" for p in pats]
    return ["*" + p for p in pats]


# ---------------------------------------------------------------- 组装
def build_reference() -> dict:
    rmod = _parse(_ROUTES_PY)
    amod = _parse(_APP_PY)
    smod = _parse(_STORE_PY)
    hf = _func_index(rmod)
    af = _func_index(amod)
    sf = _func_index(smod)
    a_doc = {n: _docstring(d) for n, d in af.items()}
    a_keys = {n: _payload_keys(d, _first_param_name(d)) for n, d in af.items()}
    s_doc = {n: _docstring(d) for n, d in sf.items()}
    s_keys = {n: _payload_keys(d, _first_param_name(d)) for n, d in sf.items()}
    # 再导出业务模块：只补 a_doc / a_keys 里**缺失**的名字，app.py 自身定义优先
    for p in _EXTRA_BUSINESS_FILES:
        if not p.exists():
            continue
        for n, d in _func_index(_parse(p)).items():
            if n not in a_doc or not a_doc[n]:
                a_doc[n] = _docstring(d)
            if n not in a_keys or not a_keys[n]:
                a_keys[n] = _payload_keys(d, _first_param_name(d))

    # 运行时导入只为拿「哪个路径属重计算闸门」——避免重复实现该判定
    from lda_webui import routes as R      # noqa: E402
    heavy = set(R.HEAVY_POST_PATHS)

    ctx = {"a_doc": a_doc, "a_keys": a_keys, "s_doc": s_doc, "s_keys": s_keys}

    entries = []
    # 精确路由：GET / POST / PATCH。PATCH 只有 `PATCH_ROUTES`（无前缀表），
    # 但 `app.py:do_PATCH` 真会分发，故必须进参考（初版漏了 ⇒ 读参考的人会以为
    # 「改自己资料」这个端点不存在）。
    for method, table in (("GET", R.GET_ROUTES), ("POST", R.POST_ROUTES),
                          ("PATCH", R.PATCH_ROUTES)):
        for path, h in table.items():
            entries.append(_entry(method, path, h.__name__, hf.get(h.__name__),
                                  ctx, heavy, wildcard=False))
    for method, prefix in (("GET", R.GET_PREFIX), ("POST", R.POST_PREFIX)):
        for mode, pat, h in prefix:
            note = "（%s匹配）" % ("前缀" if mode == "startswith" else "后缀")
            for shown in wildcard_patterns(mode, pat):
                entries.append(_entry(method, shown, h.__name__,
                                      hf.get(h.__name__), ctx, heavy,
                                      wildcard=True, note=note))
    entries.sort(key=lambda e: (e["method"], e["path"]))

    described = [e for e in entries if e["description"] and e["source"] != "none"]
    return {
        "schema": "lda.api_reference/1",
        "source": "lda/lda_webui/routes.py",
        "generated_by": "scripts/gen_api_reference.py",
        "counts": {
            "total": len(entries),
            "precise": sum(1 for e in entries if not e["wildcard"]),
            "wildcard": sum(1 for e in entries if e["wildcard"]),
            "described": len(described),
            "undescribed": len(entries) - len(described),
            "needs_login": sum(1 for e in entries if e["auth"] == "login"),
        },
        "endpoints": entries,
    }


def _entry(method, path, handler, node, ctx, heavy, wildcard, note="") -> dict:
    """一条端点记录。描述按**代码来源阶梯**取值，取不到就如实标未描述。"""
    a_doc, a_keys = ctx["a_doc"], ctx["a_keys"]
    s_doc, s_keys = ctx["s_doc"], ctx["s_keys"]

    own = _docstring(node) if node else ""
    desc, source, ref = "", "none", None
    if own:
        desc, source = _full_doc(own), "handler_docstring"
    elif node is not None:
        # ② 转调的业务 `_app.<fn>`（跳过私有 / 基建；return 里的优先）
        for cand, _in_ret in _app_calls(node):
            if a_doc.get(cand):
                desc, source, ref = _full_doc(a_doc[cand]), "app_docstring", cand
                break
        # ③ `_app._get_store().<method>` ⇒ store.py 方法 docstring
        if not desc:
            for m in _store_calls(node):
                if s_doc.get(m):
                    desc, source = _full_doc(s_doc[m]), "store_docstring"
                    ref = "store.%s" % m
                    break
    params = _payload_keys(node, "p") if node else []
    if not params and source == "app_docstring" and ref:
        params = a_keys.get(ref, [])
    if not params and source == "store_docstring" and ref:
        params = s_keys.get(ref.split(".", 1)[1], [])
    return {
        "method": method,
        "path": path,
        "handler": handler,
        "app_function": ref,
        "description": desc,
        "source": source,
        "params": params,
        "auth": "login" if path in heavy else "public",
        "heavy": path in heavy,
        "binary": bool(node is not None and _is_binary_send(node)),
        "wildcard": wildcard,
        "note": note,
    }


# ---------------------------------------------------------------- 渲染
_MD_HEAD = """# LDA WebUI · REST API 参考

> **本文件由 `scripts/gen_api_reference.py` 自动生成，请勿手工编辑**（手改必被
> `lda/run_p2_usability_smoke.py` 的「重新生成 == 磁盘文件」断言判红）。
> 改接口请改 `lda/lda_webui/routes.py`（唯一真相源），再重跑生成脚本。

- 真相源：`lda/lda_webui/routes.py`（路由表 + `HEAVY_POST_PATHS`）
- 描述来源优先级：① handler 自身 docstring → ② 转调业务 `_app.<fn>` 的 docstring
  → ③ `_app._get_store().<method>` 对应的 `store.py` 方法 docstring
  → ④ 无 ⇒ 如实标「（未描述）」（**不编造**）
- 鉴权：`login` = 命中 `HEAVY_POST_PATHS` 重计算闸门，须 store 会话令牌或
  `Authorization: Bearer <管理员令牌>`（见 `routes.py:_heavy_guard`）；未登录返回
  **401 且不消耗并发/缓存**。`public` = 匿名可访问（对外验货可达性）。
- 请求参数：由 `ast` 扫代码得出（`p.get("…")`），**不是** OpenAPI schema；
  只列键名，不含类型/必填性 —— 诚实边界。
- 前缀/后缀路由：`/xxx/**` = **前缀匹配**（`/xxx/` 之下任意路径，含动态段）；
  `*.js` = **后缀匹配**（任意路径以该后缀结尾）。同一条规则含多个后缀时逐后缀各一行
  （渲染规则见 `scripts/gen_api_reference.py:wildcard_patterns`，唯一真相源）。

## 总览

| 项 | 值 |
|---|---|
"""


def render_md(ref: dict) -> str:
    c = ref["counts"]
    pct = (100.0 * c["described"] / c["total"]) if c["total"] else 0.0
    out = [_MD_HEAD]
    out.append("| 端点总数 | %d（精确 %d + 前缀/后缀 %d） |"
               % (c["total"], c["precise"], c["wildcard"]))
    out.append("| 方法分布 | %s |"
               % " · ".join("%s %d" % (meth, sum(1 for e in ref["endpoints"]
                                                 if e["method"] == meth))
                            for meth in sorted({e["method"] for e in ref["endpoints"]})))
    out.append("| 有描述 | %d（**%.1f%%**） |" % (c["described"], pct))
    out.append("| 需登录（重计算闸门） | %d |" % c["needs_login"])
    out.append("")
    for method in ("GET", "POST", "PATCH"):
        rows = [e for e in ref["endpoints"] if e["method"] == method]
        if not rows:
            continue
        out.append("## %s（%d）" % (method, len(rows)))
        out.append("")
        out.append("| 路径 | 用途 | 参数 | 鉴权 |")
        out.append("|---|---|---|---|")
        for e in rows:
            d = e["description"] or "（未描述）"
            d = d.replace("|", "\\|")
            ps = ", ".join("`%s`" % k for k in e["params"]) or "—"
            auth = "login" if e["auth"] == "login" else "public"
            if e["binary"]:
                auth += " · **二进制**"
            out.append("| `%s`%s | %s | %s | %s |"
                       % (e["path"], e["note"], d, ps, auth))
        out.append("")
    out.append("## 诚实边界")
    out.append("")
    out.append("1. 描述取自代码 docstring，是**代码作者的原始表述**，非外部接口规范；")
    out.append("   标「（未描述）」的端点即代码里本来就没有描述。")
    out.append("2. 参数表由静态扫描 `p.get(\"…\")` 得出，**不含类型/必填/取值范围**，"
               "且可能漏掉深层嵌套键 —— 契约以 `routes.py` handler 源代码为准。")
    out.append("3. `public` 仅表示**不经过登录闸门**，不代表无其它语义校验"
               "（如 store 端点仍需会话 / 订单归属校验）。")
    out.append("4. 本参考不含鉴权凭据获取流程，见 `docs/ENVIRONMENT.md` 与 "
               "`LDA_D-13_WebUI内网部署说明.md`。")
    out.append("")
    return "\n".join(out)


def _write(ref: dict, check: bool) -> int:
    md_path = _ROOT / "docs" / "API_REFERENCE.md"
    js_path = _ROOT / "docs" / "api_reference.json"
    md = render_md(ref)
    js = json.dumps(ref, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if check:
        bad = []
        for p, new in ((md_path, md), (js_path, js)):
            old = p.read_text(encoding="utf-8") if p.exists() else ""
            if old != new:
                bad.append(p.name)
        if bad:
            print("DRIFT: %s 与代码不一致，请重跑 scripts/gen_api_reference.py"
                  % ", ".join(bad))
            return 1
        c = ref["counts"]
        print("OK: 参考与代码一致（%d 端点 / 有描述 %d / %.1f%%）"
              % (c["total"], c["described"],
                 100.0 * c["described"] / c["total"]))
        return 0
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md, encoding="utf-8", newline="\n")
    js_path.write_text(js, encoding="utf-8", newline="\n")
    c = ref["counts"]
    print("已生成 %s / %s" % (md_path.relative_to(_ROOT), js_path.relative_to(_ROOT)))
    print("  端点 %d（精确 %d + 通配 %d）· 有描述 %d（%.1f%%）· 需登录 %d · 未描述 %d"
          % (c["total"], c["precise"], c["wildcard"], c["described"],
             100.0 * c["described"] / c["total"], c["needs_login"],
             c["undescribed"]))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="生成 WebUI REST API 参考（P2-T2.3）")
    ap.add_argument("--check", action="store_true",
                    help="只比对磁盘产物与代码是否同源（不改文件；CI 用）")
    args = ap.parse_args(argv)
    return _write(build_reference(), args.check)


if __name__ == "__main__":
    raise SystemExit(main())
