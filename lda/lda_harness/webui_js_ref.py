# -*- coding: utf-8 -*-
"""WebUI 前端**取值路径**静态解析公共助手（v0.9.191 · 源自 E17-e / 血案 #32 机器化）。

为什么单独成模块
----------------
`run_webui_ecore_render_path_smoke.py`（D-193）建立的「别名时间线 + 引用扫描 +
逐段解析」三件套，是「JSON 里有值 ≠ 前端问对了地方」这一层纪律的**通用**实现。
PM（光子存储）案例卡门禁需要同一套能力 ⇒ **不得逐字复制**（那正是
`run_helper_dup_ratchet_smoke` J4「逐字重复组文件数只降不升」要抓的事），
故抽到本模块，两个门禁共用一份。

设计原则
--------
- **静态**：不执行 JS。只做正则 + 花括号配对 + JSON 逐段解析。
- **零副作用**：纯标准库、不 import 数值内核、不读 index.html（由调用方传入源码）。
- **位置敏感**：别名会被重复绑定（`var` 提升 + 顺序执行）⇒ 引用取「其之前最近一次绑定」。
"""
from __future__ import annotations

import re

__all__ = [
    "JS_MEMBERS", "REF_SENTINELS", "render_body", "alias_timeline", "scan_refs",
    "resolve", "json_path_exists", "js_ref_ok", "bad_refs",
]

#: 卡内**合法但非展示**的哨兵字段（所有案例卡都以 `if(!d||d.error)` 做错误分支）。
#: 它们不出现在正常返回体里 ⇒ 路径存在性检查必须跳过，否则判据恒红（假红）。
REF_SENTINELS = frozenset({"error"})

# 🔴 JS 内建成员名（数组/字符串方法 + 通用属性）—— **不是 JSON 路径**。
#    实测：`DTS.map(function(x){…})` 若不当心会被当成 `device_timing.stages.map`
#    ⇒ 假阳性。凡路径段命中本表即整条丢弃。
JS_MEMBERS = frozenset((
    "map", "filter", "forEach", "length", "join", "slice", "splice", "concat",
    "indexOf", "lastIndexOf", "includes", "toFixed", "toExponential", "toString",
    "toUpperCase", "toLowerCase", "reduce", "sort", "some", "every", "find",
    "findIndex", "push", "pop", "shift", "unshift", "reverse", "keys", "values",
    "entries", "flat", "flatMap", "at", "charAt", "substring", "substr", "trim",
    "split", "replace", "replaceAll", "match", "test", "exec", "repeat",
    "padStart", "padEnd", "startsWith", "endsWith", "call", "apply", "bind",
))

#: 别名绑定三式（按位置排序后建立时间线）——**与 D-193 原实现逐字同式**，
#: 目的是让 `run_webui_ecore_render_path_smoke` 的迁移**行为等价**（不多不少）。
#:  · root —— `var X=(d.k…` / 同行多声明 `, X=(d.k…`（🔴 必须同时吃两者）
#:  · two  —— `X=(Y.k1||{}).k2||…`（先补默认空对象再取子键）
#:  · one  —— `X=Y.k…`（**不带**括号；带括号形式不在本式内 ⇒ 前端须写无括号式）
BIND_PATTERNS = (
    ("root", r"(?:var\s+|,\s*)(\w+)\s*=\s*\(\s*d\.(\w+)\s*\|\|"),
    ("two", r"(\w+)\s*=\s*\(\s*(\w+)\.(\w+)\s*\|\|\s*\{\}\s*\)\s*\.(\w+)\s*\|\|"),
    ("one", r"(\w+)\s*=\s*(\w+)\.(\w+)\s*\|\|"),
)

_REF_RE = re.compile(r"(?<![\w.$])([A-Za-z_]\w*)\.((?:\w+)(?:\.\w+)*)")


def render_body(src: str, fn_name: str) -> str:
    """抽出 `function <fn_name>(...){ ... }` 的函数体（花括号配对，含 async 前缀）。

    找不到 ⇒ 抛 ValueError（调用方据此判「函数未定义」）。
    """
    pat = re.compile(r"(?:async\s+)?function\s+%s\s*\([^)]*\)\s*\{" % re.escape(fn_name))
    m = pat.search(src)
    if not m:
        raise ValueError("未找到函数定义：%s" % fn_name)
    j = src.index("{", m.start())
    depth, k = 0, j
    while k < len(src):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return src[j + 1:k]
        k += 1
    raise ValueError("%s 花括号不配对" % fn_name)


def alias_timeline(body: str):
    """按位置顺序建立别名绑定时间线 ⇒ (line, table)。

    line  = [(pos, alias, base_tuple), ...]（按 pos 升序）
    table = {alias: base_tuple}（**终态**，仅供「别名全集」用；取值必须查 line）
    """
    events = []
    for kind, pat in BIND_PATTERNS:
        for m in re.finditer(pat, body):
            events.append((m.start(), kind, m))
    events.sort(key=lambda e: e[0])
    table = {"d": ()}
    # 🔴 根绑定 `d`（= 整个 case_card）必须进时间线，否则 `d.x.y` 引用因「该位置无绑定」
    #    被整条跳过 ⇒ 顶层路径**完全没有守护**（实测：PM 卡 12 个顶层键静默落进盲区）。
    line = [(-1, "d", ())]
    for pos, kind, m in events:
        alias = m.group(1)
        if kind == "root":
            base = (m.group(2),)
        elif kind == "one":
            p = table.get(m.group(2))
            if p is None:
                continue
            base = p + (m.group(3),)
        else:                                   # two
            p = table.get(m.group(2))
            if p is None:
                continue
            base = p + (m.group(3), m.group(4))
        table[alias] = base
        line.append((pos, alias, base))
    return line, table


def scan_refs(body: str, alias_names, timeline):
    """收集所有 `X.a.b.c` 引用并绑上「该位置生效的 base」⇒ [(alias, path, base)]。"""
    out = []
    for m in _REF_RE.finditer(body):
        a, path = m.group(1), m.group(2)
        if a not in alias_names:
            continue
        if any(seg in JS_MEMBERS for seg in path.split(".")):
            continue                            # JS 内建成员访问，不是 JSON 路径
        base = None
        for pos, al, b in timeline:
            if pos <= m.start() and al == a:
                base = b
            elif pos > m.start():
                break
        if base is None:
            continue                            # 该位置尚无绑定（作用域外）⇒ 不判
        out.append((a, path, base))
    return out


def resolve(obj, base, path):
    """在 `obj` 上按 `base + path` 逐段解析 ⇒ (ok, where)。"""
    cur, walked = obj, list(base)
    for seg in base:
        if isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        else:
            return False, ".".join(walked)
    for seg in path.split("."):
        walked.append(seg)
        if isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        elif isinstance(cur, list):
            return False, ".".join(walked) + "（父为数组）"
        else:
            return False, ".".join(walked)
    return True, cur


def json_path_exists(card: dict, path: str) -> bool:
    """逐段解析 JSON 路径；`arr[].k` 取首元素。任一段缺失 ⇒ False。"""
    cur = card
    for part in path.split("."):
        if part.endswith("[]"):
            key = part[:-2]
            if not isinstance(cur, dict) or key not in cur:
                return False
            arr = cur[key]
            if not isinstance(arr, list) or not arr:
                return False
            cur = arr[0]
        else:
            if not isinstance(cur, dict) or part not in cur:
                return False
            cur = cur[part]
    return True


_DELIM_AFTER = re.compile(r"[^\w$]")


def bad_refs(card, refs):
    """逐条解析 `refs`（`scan_refs` 的输出）⇒ 返回**坏路径描述**列表。

    跳过 `REF_SENTINELS`（错误分支哨兵字段，正常返回体里本就没有）。
    返回空列表 = 「前端问的每个地方，后端都真有值」。
    """
    out = []
    for a, path, base in refs:
        if not base and path.split(".")[0] in REF_SENTINELS:
            continue
        ok, _where = resolve(card, base, path)
        if not ok:
            out.append("%s.%s → %s.%s（卡内缺）" % (a, path, ".".join(base), path))
    return out


def js_ref_ok(rsrc: str, js_lit: str, all_lits) -> bool:
    """JS 字面引用判定：短路径若被其它字面量「前缀包含」，必须**边界收尾**才算引用。

    反例（实测）：`m3ly.gds_sha256` 被 `m3ly.gds_sha256_short` **前缀包含**
    ⇒ 纯子串判定会假绿 ⇒ 必须要求引用后一个字符是分隔符。
    """
    idx = 0
    while True:
        k = rsrc.find(js_lit, idx)
        if k < 0:
            return False
        nxt = rsrc[k + len(js_lit):k + len(js_lit) + 1]
        ambiguous = any(o != js_lit and o.startswith(js_lit) for o in all_lits)
        if (not ambiguous) or (nxt == "" or _DELIM_AFTER.fullmatch(nxt)):
            return True
        idx = k + 1
