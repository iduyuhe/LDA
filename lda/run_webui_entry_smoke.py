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
  ③ **深层卡片无首屏锚点**：案例卡位于页面 ~48 屏处
     （实测 `#sec-ecore` at **26872px** / 整页 **27423px**），
     而全页没有任何指向它们的首屏入口 ⇒ 手动滚动几乎不可能碰到。

🔴 **2026-10-08 复现第二次（同族、更隐蔽）**：用户报「导航条里**没有**光传感器，但在
  面板里能找到」。实查：`sec-sensor`（光子传感器 PS-M7）登记了 hash 深链与抽屉按钮，
  **却漏了首屏 `#wbCaseBar` 的直达条目**；而本门禁的 E 节本应抓住它，却**全绿** —— 因为
  `CASE_CARDS` 是一张**手工维护的 4 项列表**（v0.9.160 时代冻结），此后首屏条长到 8 条
  （+accel/d4/oi/pm）、再 +sensor，**守卫的数据源原地不动** ⇒ E1/E2/E3/F2 一直只守着那
  4 张旧卡。**门禁守的"清单"与页面实际的"案例卡族"是两个口径 ⇒ 漂移静默。**
  ⇒ 修法：案例卡族**现算**自 `index.html` 的 `.sec[data-stage="accept"]`（单一真源），
  并加**非空下限**（防"去掉 data-stage 即脱族"把族缩小、令空集 `all()` 恒真 = 假绿）。

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
E **案例卡可达门禁**：全部 `data-stage="accept"` 案例卡（现算 · 单一真源）必须有首屏直达
  + 自动运行接线 + 锚点高亮 + 规模下限（守根因③）
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
from lda_harness.smoke_kit import make_result_collector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "lda", "lda_webui", "static")

# 由 index.html 引用的注入脚本（它们可以「定义」id）——白名单必须显式，
# 新增注入脚本时要一并加进来，否则 C 判据会把合法注入误判为缺失。
INJECTOR_SCRIPTS = ("nav.js", "cs_widget.js", "guide_widget.js", "onboard_widget.js")

#: 🔴 v0.9.208 修根因（见 docstring）：本表原为**手工维护的 4 项**（光量子/超导/光计算/
#:   电子计算，v0.9.160 时代冻结）。首屏条此后长到 8 条（+accel/d4/oi/pm）、2026-10-08
#:   再新增 `sec-sensor`（光子传感器 PS-M7）——守卫数据源不动 ⇒ 新面板漏首屏入口也全绿。
#:   现在改为**现算**：案例卡族 = `index.html` 中 `.sec[data-stage="accept"]` 的 id。
#:   `CASE_PANELS_MIN` = **非空下限**（棘轮，随族增长只增不减）：防"把 data-stage 摘掉
#:   即脱族"把族缩小到空，令 `all(空集)` 恒真 = 假绿（血案 #32 第二层）。
CASE_PANELS_MIN = 10
_ACCEPT_PATTERNS = (
    re.compile(r'data-stage="accept"[^>]*id="(sec-[A-Za-z0-9_]+)"'),
    re.compile(r'id="(sec-[A-Za-z0-9_]+)"[^>]*data-stage="accept"'),
)

# 入口命名的黑名单：这些词无信息量，配合「唯一入口」= 用户必然找不到
LABEL_BLACKLIST = ("目录", "菜单", "menu", "more", "更多", "≡", "☰目录", "全部")

_results: list[tuple[str, bool, str]] = []


check = make_result_collector(_results)


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
    # 窗口 4000 → 12000：首屏条只增不减（现 8→9 条 ≈1.7KB）；窗口过窄会截断 href
    # 令 E1 **假红**（此处取宽，宁可宽也不截）。
    m = re.search(r'id="wbCaseBar".{0,12000}?</div>', html, re.S)
    return re.findall(r'href="(#[^"]+)"', m.group(0)) if m else []


def accept_case_panels(html: str) -> list:
    """案例卡族（现算 · 单一真源）：index.html 中 `data-stage="accept"` 的 .sec id。

    🔴 取代原先手工维护的 4 项 `CASE_CARDS` —— 手工列表与页面实际族会漂移，
    且漂移**静默**（新面板漏首屏入口，E1 仍全绿）。
    """
    return sorted({m.group(1) for p in _ACCEPT_PATTERNS for m in p.finditer(html)})


def case_jump_ok(panels: list, cmap: dict, stage: dict) -> bool:
    """F2：每张案例卡的「运行」按钮（来自 CASE_MAP）确实存在于带 data-stage 的 .sec 内。

    空集合返回 False（非 True）—— 防「族为空 ⇒ all() 恒真 ⇒ 假绿」。
    """
    if not panels:
        return False
    for c in panels:
        btn = cmap.get("#" + c)
        if not btn or (btn not in stage) or (not stage[btn]):
            return False
    return True


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


def case_jump_target(js: dict) -> str:
    """`nav.js` 注入的「★ 芯片案例」直达按钮（`#wbCaseJump`）的目标锚点。

    🔴 第 **4** 种入口面：它同样**硬编码** `#sec-ecore`，且原 tooltip 枚举的也是旧的
    4 项清单 ⇒ 属同一"手工清单漂移"族（2026-10-08 一并清）。本函数取其实锚点，
    由 E5 判其**仍命中案例卡族**（防指向已删 / 改名面板 ⇒ 点了没反应）。
    """
    m = re.search(r'<a[^>]*id="wbCaseJump"[^>]*>', js.get("nav.js", "") or "")
    if not m:
        return ""
    h = re.search(r'href="(#[^"]+)"', m.group(0))
    return h.group(1) if h else ""


# ───────────────────────── 一次性审计（主流程与探针共用）─────────────────────────
def audit(html: str, js: dict) -> dict:
    """对给定源码做全部事实判定；**探针与主流程走同一份逻辑**（打在被消费的引用上）。"""
    dz, sz, mz = drawer_z(html), scrim_z(html), max_widget_z(js)
    ref, dfn = referenced_ids(html), defined_ids(html, js)
    label = menu_btn_label(js)
    hrefs = case_bar_hrefs(html)
    cmap = casejump_map(html)
    stage = run_buttons_stage_ok(html)
    panels = accept_case_panels(html)
    cjt = case_jump_target(js)
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
        "case_panels": panels,
        "case_hrefs": hrefs,
        # E1：首屏条 ⊇ 案例卡族（族现算 ⇒ 新增面板自动纳入，不再漏）
        "e1": len(panels) > 0 and all(("#" + c) in hrefs for c in panels),
        # E1b：族规模下限（防"摘 data-stage 即脱族"的减面假绿）
        "e1b": len(panels) >= CASE_PANELS_MIN,
        # E2：首屏条目的 href 必须指向真实存在的 id（无悬空锚 · 防手误改名）
        "e2": len(hrefs) > 0 and all(('id="%s"' % h[1:]) in html for h in hrefs),
        "casejump": cmap,
        "e3": len(panels) > 0 and all(cmap.get("#" + c) for c in panels),
        "e4": (".sec:target" in html) and ("scroll-margin-top" in html),
        # E5：nav.js「★ 芯片案例」直达按钮的目标仍命中案例卡族
        "case_jump_target": cjt,
        "e5": bool(cjt) and (cjt[1:] in panels),
        "bad_stage": sorted([k for k, v in stage.items() if not v]),
        "f1": len(stage) > 0 and all(stage.values()),
        "f2": case_jump_ok(panels, cmap, stage),
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
    check("E1 首屏 #wbCaseBar 含**全部**案例卡锚点直达（族现算 · 非手工 4 项）",
          r["e1"], "panels=%d(%s) hrefs=%s" % (len(r["case_panels"]), ",".join(r["case_panels"]),
                                               len(r["case_hrefs"])))
    check("E1b 案例卡族规模 ≥ 下限（防「摘 data-stage 即脱族」的减面假绿）",
          r["e1b"], "族=%d 下限=%d" % (len(r["case_panels"]), CASE_PANELS_MIN))
    check("E2 首屏条目的 href 均指向真实存在的面板 id（无悬空锚）", r["e2"])
    check("E3 直达后自动运行接线（wb-casejump-js 的 CASE_MAP 覆盖全部案例卡）",
          r["e3"], "map=%d panels=%d" % (len(r["casejump"]), len(r["case_panels"])))
    check("E4 锚点落地高亮（.sec:target）+ 不被 sticky 导航遮挡（scroll-margin-top）",
          r["e4"])
    check("E5 nav.js「★ 芯片案例」直达按钮的目标仍命中案例卡族（防指向已删/改名面板）",
          r["e5"], "target=%r" % r["case_jump_target"])

    # ── F 目录数据源完备 ────────────────────────────────────────────────
    check("F1 每个 run 按钮都位于带 data-stage 的 .sec 内（否则被抽屉归错阶段）",
          r["f1"], "违例=%s" % (r["bad_stage"] or "无"))
    check("F2 全部案例卡的『运行』按钮可被抽屉收集 · 且与 CASE_MAP 映射一致", r["f2"])

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

    # G6 🔴 本版血案的**正主**：删掉新增案例卡（sec-sensor）的首屏直达条目
    #    —— 2026-10-08 用户实测「导航条里没有光传感器」，而当时 E1 全绿（守着手工 4 项）。
    m6 = re.sub(r'\s*<a href="#sec-sensor"[^>]*>[^<]*</a>', "", html, count=1)
    g6 = audit(m6, js)["e1"] is False
    check("G6 反向：删掉 #sec-sensor 首屏直达 ⇒ E1 必红（新增面板漏首屏入口 · 本版血案）", g6)

    # G7 减面攻击：把某案例卡（sec-sensor）的 data-stage 摘掉 ⇒ 族 10→9 ⇒ E1b 必红
    #    （若不设下限，族缩到空时 all(空集) 恒真 ⇒ E1/E3/F2 全部假绿）
    m7 = re.sub(r'(<div class="sec" )data-stage="accept"([^>]*id="sec-sensor">)',
                r"\g<1>\g<2>", html, count=1)
    a7 = audit(m7, js)
    g7 = (a7["e1b"] is False) and (len(a7["case_panels"]) == len(r["case_panels"]) - 1)
    check("G7 反向：摘掉某案例卡 data-stage（族 10→9）⇒ E1b 必红（减面假绿防线）", g7,
          "族=%d" % len(a7["case_panels"]))

    # G8 🔴 **假绿复现**（verbatim 旧实现）：在"删掉 sec-sensor 直达"的缺陷页上，
    #    旧实现（all over 手工 4 项 CASE_CARDS）**仍判绿**，而新实现必红。
    #    这证明旧守卫在真实缺陷面前**结构性地看不见**，不是阈值松动（血案 #32 第二层）。
    _OLD_FOUR = ("sec-qchip", "sec-schip", "sec-pchip", "sec-ecore")
    old_hrefs = case_bar_hrefs(m6)
    old_logic_green = all(("#" + c) in old_hrefs for c in _OLD_FOUR)
    new_logic_red = audit(m6, js)["e1"] is False
    g8 = (old_logic_green is True) and (new_logic_red is True)
    check("G8 假绿复现：缺陷页上旧实现（手工 4 项）判绿 ∧ 新实现判红 ⇒ 旧守卫结构性失明", g8,
          "old_green=%s new_red=%s" % (old_logic_green, new_logic_red))

    # G9 第 4 入口面断链：nav.js「★ 芯片案例」指向不存在的面板 ⇒ E5 必红
    js9 = dict(js)
    js9["nav.js"] = js9["nav.js"].replace('id="wbCaseJump" class="wb-btn wb-btn-primary" href="#sec-ecore"',
                                          'id="wbCaseJump" class="wb-btn wb-btn-primary" href="#sec-gone"')
    g9 = (audit(html, js9)["e5"] is False) and (js9["nav.js"] != js["nav.js"])
    check("G9 反向：nav.js「★ 芯片案例」指向已删面板 ⇒ E5 必红（点了没反应）", g9)

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
