#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""WebUI 案例卡前端**取值路径**门禁（D-193 · v0.9.169）。

═══════════════════════════════════════════════════════════════════════════
为什么存在（血案 #32 机器化）
═══════════════════════════════════════════════════════════════════════════
E17-e 生产实测发现：前端面板取 `synthesis_law.serial_ns`，而该值实际在
`synthesis_law.demo.serial_ns` ⇒ **三格显示 0.0**。此后靠**人肉在生产页上翻**才发现。
根因不是「渲染错」，而是 **JS 里写的取值路径与后端 JSON 的键路径不一致** ——
而后端侧的一切门禁（案例卡 B1–B24、API 验收）**都看不到这一层**：
它们只保证 JSON 里有这个值，**不保证前端问对了地方**。

⇒ 本门禁把这层钉住：**把 `renderECore` 里的每条取值路径，逐条拿到真实案例卡 JSON 上解析**。

═══════════════════════════════════════════════════════════════════════════
🔴 关键难点：**别名会被重复绑定**（本轮实测踩到）
═══════════════════════════════════════════════════════════════════════════
`renderECore` 里 `DB` **被声明两次**：
  · 第 4866–4867 行：`var D2=…, LC=…, RO=…, DB=(D2.dibl||{}), …`（DB = device_2d.dibl）
  · 第 4958 行：    `var DB=(d.device_budget||{}), …`（DB = device_budget，**覆盖前者**）
`var` 提升 + 顺序执行 ⇒ **同一个别名在不同位置指向不同的 JSON 子树**。
⇒ 别名图**必须按位置建立时间线**，每条引用取「其**之前**最近一次绑定」。
（用「一个别名一个全局绑定」的朴素映射 ⇒ 63 条**假阳性** —— 本轮实测。）

═══════════════════════════════════════════════════════════════════════════
判什么
═══════════════════════════════════════════════════════════════════════════
1. **别名时间线**：`var X=(d.<k>||…)` / `X=(Y.<k>||{})` / `X=(Y.<k1>||{}).<k2>||…` 三类绑定
   按出现位置排序；任一绑定解析不出根键 ⇒ 红。
2. 🔴 **路径存在性**：每条引用 `X.a.b.c` 取自**该位置**的有效绑定，在真实 `case_card()` JSON
   上逐段解析；**任一段不存在 ⇒ 红**（这正是 E17 血案）。
3. **反向完备**：`case_card()` 下**每个 `device_*` facts 块**都必须被引用到
   （防「后端加了块、前端从不显示」的静默盲区 —— 与能力清单「反向完备」同族）。
4. **覆盖性**：E18 面板的别名必须在时间线内且被逐一检查（防「新面板绕过门禁」）。
5. 🔴 **突变探针**（先证能变红）：注入假路径 / 抹掉 facts 块引用 ⇒ 必红；还原后复绿。
6. 自入 CI core。

🔴 **诚实边界**：本门禁是**静态路径检查**，不执行 JS、不看渲染是否「好看」；
值存在但**语义不对**（口径漂移）仍需 B16–B24 那类「卡内数字 ≡ 模块实测」判据守。
二者互补：**B16–B24 守「值对不对」，本门禁守「问对没问对」。**
"""
from __future__ import annotations

import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

INDEX = os.path.join(_HERE, "lda_webui", "static", "index.html")

_BIND_PATTERNS = (
    # (kind, regex)  kind: root | one | two
    # 🔴 root 必须同时吃 `var X=(d.k||…` 与**同行多声明** `, X=(d.k||…`
    #    —— 本轮实测 `var DPD=(d.device_pde||{}), DLM=(d.device_limits||{});`
    #    的第二个别名曾整条漏掉 ⇒ 造出「device_limits 未被引用」的假缺口。
    ("root", r"(?:var\s+|,\s*)(\w+)\s*=\s*\(\s*d\.(\w+)\s*\|\|"),
    ("two", r"(\w+)\s*=\s*\(\s*(\w+)\.(\w+)\s*\|\|\s*\{\}\s*\)\s*\.(\w+)\s*\|\|"),
    ("one", r"(\w+)\s*=\s*(\w+)\.(\w+)\s*\|\|"),
)

# 🔴 JS 内建成员名（数组/字符串方法 + 通用属性）—— **不是 JSON 路径**。
#    本轮实测：`DTS.map(function(x){…})` 被当成 `device_timing.stages.map` ⇒ 假阳性。
_JS_MEMBERS = frozenset((
    "map", "filter", "forEach", "length", "join", "slice", "splice", "concat",
    "indexOf", "lastIndexOf", "includes", "toFixed", "toExponential", "toString",
    "toUpperCase", "toLowerCase", "reduce", "sort", "some", "every", "find",
    "findIndex", "push", "pop", "shift", "unshift", "reverse", "keys", "values",
    "entries", "flat", "flatMap", "at", "charAt", "substring", "substr", "trim",
    "split", "replace", "replaceAll", "match", "test", "exec", "repeat",
    "padStart", "padEnd", "startsWith", "endsWith", "call", "apply", "bind",
))


def _read(p):
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


def render_body(src: str) -> str:
    """抽 `function renderECore(d){ ... }` 的函数体（花括号配对）。"""
    i = src.index("function renderECore(d){")
    j = src.index("{", i)
    depth, k = 0, j
    while k < len(src):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return src[j + 1:k]
        k += 1
    raise ValueError("renderECore 花括号不配对")


def alias_timeline(body: str):
    """按位置顺序建立别名绑定时间线 ⇒ [(pos, alias, base_tuple)]（JS 顺序执行语义）。"""
    events = []
    for kind, pat in _BIND_PATTERNS:
        for m in re.finditer(pat, body):
            events.append((m.start(), kind, m))
    events.sort(key=lambda e: e[0])
    table = {"d": ()}
    line = []
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
    """收集所有 `X.a.b.c` 引用，并绑上「该位置生效的 base」；返回 [(alias, path, base, err)]。"""
    out = []
    for m in re.finditer(r"(?<![\w.$])([A-Za-z_]\w*)\.((?:\w+)(?:\.\w+)*)", body):
        a, path = m.group(1), m.group(2)
        if a not in alias_names:
            continue
        if any(seg in _JS_MEMBERS for seg in path.split(".")):
            continue                            # 🔴 JS 内建成员访问，不是 JSON 路径
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


def main() -> int:
    from lda_webui import ecore_case as EC

    src = _read(INDEX)
    body = render_body(src)
    card = EC.case_card(repo_root="__nonexistent_root__")

    timeline, table = alias_timeline(body)
    names = set(table.keys())
    refs = scan_refs(body, names, timeline)
    dup = {}
    for _, a, _ in timeline:
        dup[a] = dup.get(a, 0) + 1
    rebind = sorted(a for a, c in dup.items() if c > 1)

    check("A1 别名时间线：%d 条绑定 / %d 个别名（其中**重绑定** %d 个：%s）"
          % (len(timeline), len(names) - 1, len(rebind), ",".join(rebind) or "无"),
          len(timeline) >= 10 and "DB" in names,
          "🔴 重绑定必须按位置处理 —— 朴素全局映射会造 63 条假阳性（本轮实测）")

    check("A2 别名解析完整：每条绑定的父别名都已被更早绑定解析（无悬空父）",
          all(b for _, _, b in timeline) and len(set(names)) >= 10,
          "根→子链全部可解析")

    bad = []
    for a, path, base in refs:
        ok, where = resolve(card, base, path)
        if not ok:
            bad.append("%s.%s → %s.%s（卡内缺）" % (a, path, ".".join(base), path))
    check("B1 🔴 **取值路径存在性**：%d 条引用路径（%d 个别名）逐条在真实 `case_card()` JSON 上"
          "解析 ⇒ 全部存在（**这正是 E17 血案那一层**）" % (len(refs), len(set(r[0] for r in refs))),
          not bad, "坏路径 %d 条：%s" % (len(bad), bad[:4]))

    facts_keys = [k for k in card if k.startswith("device_")]
    referenced = set()
    for a, path, base in refs:
        if base:
            referenced.add(base[0])
    missing = [k for k in facts_keys if k not in referenced]
    check("C1 🔴 **反向完备**：`case_card()` 里 %d 个 `device_*` facts 块**每一个**都被前端引用"
          "（防「后端加了块、前端从不显示」的静默盲区）" % len(facts_keys),
          not missing, "未被引用的块：%s" % missing)

    e18 = [r for r in refs if r[0] in ("DCS", "DCSM", "DCSF", "DCSS", "DCSK",
                                       "DCST", "DCSA", "DCSRC", "DCSRV", "DCSP")
           or (r[2] and r[2][0] == "device_col_share")]
    check("D1 🔴 覆盖性：E18 面板别名（DCS/DCSM/DCSF/DCSS/DCSK/DCST/DCSA/DCSRC/DCSRV/DCSP）"
          "**在时间线内**且被逐一检查（%d 条引用）" % len(e18),
          len(e18) >= 8 and all(n in names for n in
                                ("DCSM", "DCSF", "DCSS", "DCSK", "DCST", "DCSA", "DCSRC", "DCSRV")),
          "E18 覆盖到位")

    # ── 突变探针（先证能变红）──
    def _scan(b):
        tl, _tb = alias_timeline(b)
        _nm = set(t[1] for t in tl) | {"d"}
        out = []
        for a, path, base in scan_refs(b, _nm, tl):
            ok, _ = resolve(card, base, path)
            if not ok:
                out.append(a + "." + path)
        return out

    assert _scan(body) == [], "前置：原体应无坏路径（实得 %s）" % _scan(body)[:3]
    probe1 = body.replace("DCSM.unit_cap_area_um2", "DCSM.unit_cap_area_um2_typo", 1)
    p1 = _scan(probe1)
    check("E1 反向：把一条真实路径改成 `DCSM.unit_cap_area_um2_typo` ⇒ B1 必红"
          "（模拟 E17 血案：路径写错而 JSON 侧一切正常）", len(p1) >= 1, "命中 %d 条：%s" % (len(p1), p1[:2]))

    probe2 = body.replace("DCSF.spread", "DCSF.spread_wrong", 1)
    p2 = _scan(probe2)
    check("E2 反向：把 `DCSF.spread` 改成 `DCSF.spread_wrong` ⇒ B1 必红（同一探针换别名）",
          len(p2) >= 1, "命中 %d 条" % len(p2))

    probe3 = body.replace("d.device_col_share", "d.device_col_share_x", 1)
    _tl3, _tb3 = alias_timeline(probe3)
    _nm3 = set(t[1] for t in _tl3) | {"d"}
    _ref3 = set()
    for a, path, base in scan_refs(probe3, _nm3, _tl3):
        if base:
            _ref3.add(base[0])
    check("E3 反向：抹掉 `d.device_col_share` 的绑定 ⇒ C1 必红（假盲区回归）",
          "device_col_share" not in _ref3)

    check("E4 还原完整性：探针退出后复跑仍为空（无 patch 残留）",
          _scan(body) == [] and "device_col_share" in body)

    ci = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_webui_ecore_render_path_smoke.py" in ck)

    bad_n = globals().get("FAIL", 0)
    good_n = globals().get("PASS", 0)
    print("")
    print("门禁 smoke：%d PASS / %d FAIL" % (good_n, bad_n))
    return 0 if bad_n == 0 else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
