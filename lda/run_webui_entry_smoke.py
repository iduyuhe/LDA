# -*- coding: utf-8 -*-
"""WebUI 入口可达性门禁（v0.9.160 立 · 根因来自用户「反复查也找不到电子计算芯片案例」）。

═══════════════════════════════════════════════════════════════════════════
为什么需要这道门禁：一条真实的、持续很久的、无人发现的对外缺陷链
═══════════════════════════════════════════════════════════════════════════
用户报障：「我按你说的路径反复查了，**没有找到**『电子计算芯片案例（模拟计算核 / MVM
交叉阵列）』，之前的我也找过，也没找到。」—— 能力本身早已上线且门禁全绿，
但**用户到达不了**。

实测定位（agent-browser 在生产页 DOM 上取的硬证据）：

  ① **入口命名灾难**：唯一的能力清单入口是顶部一个文本为「**目录**」的按钮
     （`static/nav.js` 注入 `#wbMenuBtn`）。零信息量 ⇒ 无人能联想到里面有「芯片案例」。
  ② **层级被自家浮层碾压**：抽屉 `.wb-drawer` 的 `z-index:999`，而本页注入的
     3 个浮层（cs_widget 客服 / guide_widget 引导 / onboard_widget 上手）用的是
     `z-index ≈ 21.47 亿`（最高 2147483003）⇒ 点开抽屉后左下角被「✅ 入门进度 0/4」
     「🎯 3分钟引导」压住，**看起来像"打不开 / 没反应"**。
  ③ **深层卡片无首屏锚点**：4 张案例卡位于页面 ~48 屏处
     （实测 `#sec-ecore` at **26872px** / 整页 **27423px**），
     而全页没有任何指向它们的首屏入口 ⇒ 手动滚动几乎不可能碰到。

⇒ 通则（本项目第 4 次同类教训）：**「已上线 + 门禁全绿」≠「用户能用」**。
  CI 只验证了能力本身，没有任何门禁验证**入口的可发现性 / 层级 / 命名 / 契约**。
  **本门禁就是补这一格。**

═══════════════════════════════════════════════════════════════════════════
判什么（分节）
═══════════════════════════════════════════════════════════════════════════
A 文件完整性
B **层级门禁**：抽屉/遮罩 z-index 必须高于所有静态脚本注入的浮层 z-index（守根因②）
C **id 契约门禁**：index.html 内 JS 引用的 id 必须有人定义（HTML 或注入脚本）
                 —— 防「getElementById 拿到 null ⇒ 整段脚本静默崩 ⇒ 入口消失」
D **入口命名门禁**：入口按钮文本必须可解读（黑名单 + 必须含"能力/案例"）（守根因①）
E **案例卡可达门禁**：4 张案例卡（光量子/超导/光计算/电子计算）必须有首屏直达 +
  自动运行接线 + 锚点高亮（守根因③）
F **目录数据源完备**：每个 `button[id^="run"]` 都必须位于带 `data-stage` 的 `.sec` 内
                 （否则抽屉 `collect()` 会给它兜底 stage，能力会被归错阶段而难找）
G 反向可证伪：**5 条突变探针**，每条都必须能把对应判据打红
K 自入 CI core（防静默漏接 · 血案 #28）

设计：**纯文本解析，零浏览器、零网络、零重计算** ⇒ 秒级，可进 CI core。
"""

from __future__ import annotations

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "lda", "lda_webui", "static")

# 由 index.html 引用的注入脚本（它们可以「定义」id）——白名单必须显式，
# 新增注入脚本时要一并加进来，否则 C 判据会把合法注入误判为缺失。
INJECTOR_SCRIPTS = ("nav.js", "cs_widget.js", "guide_widget.js", "onboard_widget.js")

CASE_CARDS = (
    ("sec-qchip", "光量子计算芯片"),
    ("sec-schip", "超导量子计算芯片"),
    ("sec-pchip", "光计算芯片"),
    ("sec-ecore", "电子计算芯片（E1–E14）"),
)

# 案例卡 -> 其「运行」按钮 id（抽屉 collect() 与 wb-casejump-js 都按此接线）
CASE_RUN_BUTTONS = {
    "sec-qchip": "runQChip", "sec-schip": "runSChip",
    "sec-pchip": "runPChip", "sec-ecore": "runECore",
}

# 入口命名的黑名单：这些词无信息量，配合「唯一入口」= 用户必然找不到
LABEL_BLACKLIST = ("目录", "菜单", "menu", "more", "更多", "≡", "☰目录", "全部")

_results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> bool:
    _results.append((name, bool(cond), detail))
    return bool(cond)


# ───────────────────────── 纯函数：接受文本，返回事实 ─────────────────────────
def read_text(path: str) -> str:
    return io.open(path, encoding="utf-8").read()


def load_sources(static_dir: str = STATIC):
    """读入 index.html 与全部注入脚本；返回 (html, {fname: text})。"""
    html = read_text(os.path.join(static_dir, "index.html"))
    js = {}
    for f in INJECTOR_SCRIPTS:
        p = os.path.join(static_dir, f)
        js[f] = read_text(p) if os.path.exists(p) else ""
    return html, js


def drawer_z(html: str):
    m = re.search(r"\.wb-drawer\{[^}]*?z-index\s*:\s*(\d+)", html)
    return int(m.group(1)) if m else None


def scrim_z(html: str):
    m = re.search(r"\.wb-scrim\{[^}]*?z-index\s*:\s*(\d+)", html)
    return int(m.group(1)) if m else None


def max_widget_z(js: dict) -> int:
    zs = []
    for t in js.values():
        zs += [int(x) for x in re.findall(r"z-index\s*:\s*(\d{6,})", t)]
    return max(zs) if zs else 0


def referenced_ids(html: str) -> set:
    s = set(re.findall(r"""getElementById\(\s*['"]([\w\-]+)['"]""", html))
    s |= set(re.findall(r"""querySelector\(\s*['"]#([\w\-]+)['"]""", html))
    return s


def defined_ids(html: str, js: dict) -> set:
    s = set(re.findall(r"""\bid=["']([\w\-]+)["']""", html))
    for t in js.values():
        s |= set(re.findall(r"""\bid=\\?["']([\w\-]+)\\?["']""", t))
        s |= set(re.findall(r"""\bid:\s*["']([\w\-]+)["']""", t))
    return s


def menu_btn_label(js: dict) -> str:
    """从 nav.js 里取出 #wbMenuBtn 的**可见文本**。

    nav.js 用多段字符串拼接生成按钮（`'<button id="wbMenuBtn" ...' + '>...' +`
    `'☰ 能力目录</button>'`），故不能在单引号内直接取；这里用
    「`</button>` 前最后一个不含标签字符的引号片段」定位可见文本。
    """
    t = js.get("nav.js", "")
    m = re.search(r'id="wbMenuBtn"', t)
    if not m:
        return ""
    tail = t[m.end(): m.end() + 800]
    frag = re.search(r"'([^'<>]*?)</button>'", tail)
    if frag:
        return frag.group(1).strip()
    # 兜底：属性块之后的第一段纯文本
    frag2 = re.search(r">'\s*\+\s*'([^'<>]+)</button>", tail, re.S)
    return frag2.group(1).strip() if frag2 else ""


def case_bar_hrefs(html: str) -> list:
    m = re.search(r'id="wbCaseBar".{0,4000}?</div>', html, re.S)
    return re.findall(r'href="(#[^"]+)"', m.group(0)) if m else []


def casejump_map(html: str) -> dict:
    m = re.search(r'id="wb-casejump-js">(.*?)</script>', html, re.S)
    if not m:
        return {}
    body = m.group(1)
    return dict(re.findall(r'"(#sec-[\w\-]+)"\s*:\s*"(run\w+)"', body))


def run_buttons_stage_ok(html: str) -> dict:
    """每个 run 按钮 -> 它最近的祖先 .sec 是否带 data-stage。"""
    secs = [(m.start(), "data-stage=" in m.group(1))
            for m in re.finditer(r'<div class="sec"([^>]*)>', html)]
    out = {}
    for m in re.finditer(r'<button[^>]*\bid="(run[\w]+)"', html):
        pos = m.start()
        prev = [s for s in secs if s[0] < pos]
        out[m.group(1)] = (prev[-1][1] if prev else False)
    return out


# ───────────────────────── 一次性审计（主流程与探针共用）─────────────────────────
def audit(html: str, js: dict) -> dict:
    """对给定源码做全部事实判定；**探针与主流程走同一份逻辑**（打在被消费的引用上）。"""
    dz, sz, mz = drawer_z(html), scrim_z(html), max_widget_z(js)
    ref, dfn = referenced_ids(html), defined_ids(html, js)
    label = menu_btn_label(js)
    hrefs = case_bar_hrefs(html)
    cmap = casejump_map(html)
    stage = run_buttons_stage_ok(html)
    return {
        "drawer_z": dz, "scrim_z": sz, "max_widget_z": mz,
        "b1": (dz is not None) and (dz > mz),
        "b2": (sz is not None) and (sz > mz) and (dz is not None) and (sz < dz),
        "missing_ids": sorted(ref - dfn),
        "c1": len(ref - dfn) == 0,
        "label": label,
        # 含糊命名 = **整体就叫**「目录/菜单」这类词。故用精确匹配（含匹配会误伤「☰ 能力目录」）。
        "d1": bool(label) and (len(label) >= 4)
              and (label.strip().lower() not in [b.lower() for b in LABEL_BLACKLIST])
              and (("能力" in label) or ("案例" in label)),
        "d2": ("wb-btn-primary" in html) and ("wb-btn-primary" in js.get("nav.js", "")),
        "case_hrefs": hrefs,
        "e1": len(hrefs) > 0 and all(("#" + c) in hrefs for c, _ in CASE_CARDS),
        "e2": all(('id="%s"' % c) in html for c, _ in CASE_CARDS),
        "casejump": cmap,
        "e3": all(cmap.get("#" + c) for c, _ in CASE_CARDS),
        "e4": (".sec:target" in html) and ("scroll-margin-top" in html),
        "bad_stage": sorted([k for k, v in stage.items() if not v]),
        "f1": len(stage) > 0 and all(stage.values()),
        "f2": all((CASE_RUN_BUTTONS[c] in stage) and stage[CASE_RUN_BUTTONS[c]]
                  for c, _ in CASE_CARDS)
              and all(cmap.get("#" + c) == CASE_RUN_BUTTONS[c] for c, _ in CASE_CARDS),
    }


def main() -> int:
    print("=" * 74)
    print("WebUI 入口可达性门禁（v0.9.160 · 用户「找不到电子计算芯片案例」根因护栏）")
    print("=" * 74)

    idx = os.path.join(STATIC, "index.html")
    if not os.path.exists(idx):
        check("A1 static/index.html 存在且规模合理（>300KB）", False, "文件不存在")
        return _report()
    html, js = load_sources()
    a1 = len(html) > 300_000
    check("A1 static/index.html 存在且规模合理（>300KB）", a1,
          "len=%d" % len(html))

    r = audit(html, js)

    # ── B 层级门禁（根因②）──────────────────────────────────────────────
    check("B1 抽屉 z-index 高于所有注入浮层（否则点开被『入门进度/3分钟引导』压住）",
          r["b1"], "drawer=%s vs max_widget=%s" % (r["drawer_z"], r["max_widget_z"]))
    check("B2 遮罩 z-index 位于 (max_widget, drawer) 之间",
          r["b2"], "scrim=%s" % r["scrim_z"])

    # ── C id 契约（防静默崩溃）──────────────────────────────────────────
    check("C1 index.html 内 JS 引用的 id 全部有定义（HTML 或注入脚本）",
          r["c1"], "缺失=%s" % (r["missing_ids"] or "无"))

    # ── D 入口命名（根因①）──────────────────────────────────────────────
    check("D1 入口按钮文本可解读（非黑名单 · 含『能力』或『案例』）",
          r["d1"], "label=%r" % r["label"])
    check("D2 入口按钮使用强调色高亮类 .wb-btn-primary（能从白底按钮里跳出来）",
          r["d2"])

    # ── E 案例卡可达（根因③）────────────────────────────────────────────
    check("E1 首屏 #wbCaseBar 含全部 4 张案例卡锚点直达",
          r["e1"], "hrefs=%s" % r["case_hrefs"])
    check("E2 4 张案例卡 id 均存在于 index.html", r["e2"])
    check("E3 直达后自动运行接线（wb-casejump-js 的 CASE_MAP 覆盖 4 卡）",
          r["e3"], "map=%s" % r["casejump"])
    check("E4 锚点落地高亮（.sec:target）+ 不被 sticky 导航遮挡（scroll-margin-top）",
          r["e4"])

    # ── F 目录数据源完备 ────────────────────────────────────────────────
    check("F1 每个 run 按钮都位于带 data-stage 的 .sec 内（否则被抽屉归错阶段）",
          r["f1"], "违例=%s" % (r["bad_stage"] or "无"))
    check("F2 4 张案例卡的『运行』按钮可被抽屉收集 · 且与 CASE_MAP 映射一致", r["f2"])

    # ── G 反向可证伪（突变探针）──────────────────────────────────────────
    print("-" * 74)
    print("G 反向可证伪（突变探针）：每条都必须能把对应判据打红")
    print("-" * 74)

    # G1 层级回归：把抽屉 z 改回 999
    m1 = re.sub(r"(\.wb-drawer\{[^}]*?z-index\s*:\s*)\d+", r"\g<1>999", html, count=1)
    g1 = audit(m1, js)["b1"] is False
    check("G1 反向：抽屉 z-index 改回 999 ⇒ B1 必红（层级碾压回归）", g1)

    # G2 命名回归：把入口文本改回「目录」
    js2 = dict(js)
    js2["nav.js"] = js2["nav.js"].replace("☰ 能力目录", "目录")
    g2 = audit(html, js2)["d1"] is False
    check("G2 反向：入口文本改回「目录」⇒ D1 必红（命名灾难回归）", g2)

    # G3 直达缺失：删掉电子计算芯片案例的直达锚点
    m3 = html.replace('<a href="#sec-ecore" style="color:#1a1205', '<a href="#nowhere" style="color:#1a1205')
    g3 = audit(m3, js)["e1"] is False
    check("G3 反向：删掉 #sec-ecore 直达 ⇒ E1 必红（深层卡片再度失联）", g3)

    # G4 自动运行断线：掏空 CASE_MAP
    m4 = re.sub(r'(id="wb-casejump-js">.*?)"#sec-ecore"\s*:\s*"runECore"', r"\g<1>", html, count=1, flags=re.S)
    g4 = audit(m4, js)["e3"] is False
    check("G4 反向：掏空 wb-casejump-js 的 #sec-ecore 映射 ⇒ E3 必红", g4)

    # G5 阶段缺失：把案例卡所在 .sec 的 data-stage 去掉
    m5 = html.replace('<div class="sec" data-stage="accept" data-stack="both" data-roles="engineer,expert" id="sec-ecore">',
                      '<div class="sec" data-stack="both" data-roles="engineer,expert" id="sec-ecore">')
    g5 = audit(m5, js)["f1"] is False
    check("G5 反向：案例卡所在 .sec 去掉 data-stage ⇒ F1 必红（能力被归错阶段）", g5)

    # ── K 自入 CI core ─────────────────────────────────────────────────
    ci = os.path.join(ROOT, "lda", "run_ci_regression.py")
    ck = read_text(ci) if os.path.exists(ci) else ""
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_webui_entry_smoke.py" in ck)

    return _report()


def _report() -> int:
    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    print()
    for name, ok, detail in _results:
        print("  [%s] %s%s" % ("PASS" if ok else "FAIL", name,
                               ("   (%s)" % detail) if (detail and not ok) else ""))
    print()
    print("RESULT: %d PASS / %d FAIL" % (npass, nfail))
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
