"""D-78 · 超市前端登录门禁护栏 smoke（v0.9.43 · 防「改造留半截」回潮）。

防什么
------
**已登录用户被反复要求二次登录，且登录后不进入原目标画面。**

血案（2026-09-06，杜先生实测报障）：登录进系统后点「🛠 提交定制需求」，
**又弹一次登录框要求输邮箱密码**；输完之后**什么也没发生**，不进定制画面。

根因（不是逻辑错，是改造留半截）：
  P2-5 把会话令牌由 JS 可读字符串改为 **HttpOnly Cookie**（XSS 不可读，正确方向）。
  改造时把 `var store_token = ""` 废用（注释都写了"前端不再持有令牌字符串"），
  但**忘了同步改 4 处 `if(!store_token){ showLogin(); return; }` 门禁**
  （openCustom / openBuy / openConsult / loadOrders）。
  ⇒ `store_token` 恒为空串 ⇒ 门禁**恒真** ⇒ 已登录用户一律被判成未登录。
  后端契约本身完全正确（`/api/store/me` 凭 Cookie 探活返回 user）。

第二个症状同源：`submitAuth()` 登录成功后只 `closeAuth() + refreshAuth()`，
**没有重放被门禁中断的动作** ⇒ 用户"输完密码什么都没发生"。

这是本项目**第三次**栽在「标签 ≠ 行为」（前两次：v0.9.15 独立候选标签、
v0.9.41 文档写"进 CI"而实际零引用）。共同特征：**某个符号/文档还挂着旧语义，
但它的真值来源已被改造搬走**。故本护栏锁的是**结构**而非数值。

判据（死标量，LLM 不进判决路径）
--------------------------------
  ① store.html 不得再出现 `if(!store_token)` 旧门禁（回潮即 FAIL）
  ② `requireAuth()` 已定义，且内部**自带探活**（页面加载时 refreshAuth 是异步的，
     用户在探活返回前点按钮会误判未登录 ⇒ 门禁不能只看缓存变量）
  ③ 四处受保护动作（openCustom / openBuy / openConsult / loadOrders）均走 requireAuth
  ④ 登出必须清 `STORE_USER`（不再清已废用的 store_token）
  ⑤ 登录成功后必须**重放** PENDING_ACTION（修"输完密码没进画面"）
  ⑥ 会话类 fetch（/api/store/me、/api/store/orders/mine）必须带 credentials
  ⑦ 🔴 反向测试 A：注入旧门禁写法 ⇒ ① 必须报
  ⑧ 🔴 反向测试 B：抽掉某动作的 requireAuth ⇒ ③ 必须报
  ⑨ 🔴 反向测试 C：删掉重放逻辑 ⇒ ⑤ 必须报

判据 ⑦~⑨ 用于证明**本护栏自己会响** —— 没被验证过的护栏不算护栏。

🔴 为什么是静态检查而不跑浏览器：CI 里**零 node 依赖**（已核实），引入 node
会破坏外部可复现性。故只守「会随改造漂移的结构不变量」，不在 CI 里做端到端。
端到端行为已另做 node 沙箱实测 12/12（含反向），见 CHANGELOG v0.9.43。

运行：python lda/run_store_auth_gate_smoke.py
"""
from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict, List

_LDA = os.path.dirname(os.path.abspath(__file__))
_HTML = os.path.join(_LDA, "lda_webui", "static", "store.html")

# 受登录门禁保护的动作（四处，缺一即漏）
_PROTECTED = ["openCustom", "openBuy", "openConsult", "loadOrders"]

CHECKS: List[Dict[str, Any]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    CHECKS.append({"name": name, "ok": bool(ok), "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return bool(ok)


# --- 判据实现（纯函数，接收源码字符串，便于反向测试注入） ---------------

def _strip_line_comment(line: str) -> str:
    """去掉 JS 行注释，但**不切** `http://` / `https://` 里的双斜杠。

    🔴 为什么需要：本文件为缺陷根因写了说明注释，注释里天然含 `if(!store_token)`
    字面量。若不剥离注释，判据 ① 会把自己的说明文字当成回潮报出来（自伤）。
    """
    return re.sub(r"(?<!:)//.*$", "", line)


def _old_gate_hits(src: str) -> List[str]:
    """① 返回源码中残留的旧门禁写法（`if(!store_token)` 及其变体）。

    只扫**代码**，跳过整行注释与行尾注释（注释里引用旧写法属正常说明）。
    """
    hits: List[str] = []
    for line in src.splitlines():
        s = line.strip()
        if s.startswith("//") or s.startswith("*") or s.startswith("/*"):
            continue                      # 整行注释
        hits += re.findall(r"if\s*\(\s*!\s*store_token\s*\)", _strip_line_comment(line))
    return hits


def _require_auth_defined(src: str) -> bool:
    """② requireAuth 已定义。"""
    return bool(re.search(r"function\s+requireAuth\s*\(", src))


def _require_auth_probes(src: str) -> bool:
    """② requireAuth 内部自带探活（不能只看缓存变量，否则有时序竞态）。"""
    m = re.search(r"function\s+requireAuth\s*\([^)]*\)\s*\{(.*?)\n\}", src, re.S)
    if not m:
        return False
    body = m.group(1)
    return ("store/me" in body) and ("fetch(" in body)


def _unprotected(src: str) -> List[str]:
    """③ 返回未走 requireAuth 的受保护动作名。"""
    # 按顶层 `function ` 切段，避免括号配平的复杂性
    segs = re.split(r"\nfunction\s+", src)
    out: List[str] = []
    for name in _PROTECTED:
        seg = next((s for s in segs if re.match(r"%s\s*\(" % re.escape(name), s)), None)
        if seg is None or "requireAuth(" not in seg:
            out.append(name)
    return out


def _logout_clears_truth(src: str) -> bool:
    """④ 登出清的是 STORE_USER（登录态真值），不是已废用的 store_token。"""
    m = re.search(r"function\s+logout\s*\(\s*\)\s*\{(.*?)\n\}", src, re.S)
    if not m:
        return False
    body = m.group(1)
    return ("STORE_USER" in body) and ("store_token=" not in body.replace("store_token =", "store_token="))


def _replay_present(src: str) -> bool:
    """⑤ 登录成功后重放 PENDING_ACTION。"""
    return bool(re.search(r"PENDING_ACTION\s*\}\s*\{\s*var\s+act\s*=\s*PENDING_ACTION", src)) or bool(
        re.search(r"if\s*\(\s*PENDING_ACTION\s*\)[\s\S]{0,200}?act\s*\(\s*\)", src)
    )


def _session_fetch_without_credentials(src: str) -> List[str]:
    """⑥ 返回未带 credentials 的会话类 fetch 调用（Cookie 会话必须显式携带）。

    🔴 实现要点：不能用 `fetch\\(...[^)]*\\)` 取参数——选项对象里有 `authHeaders()`
    这样的嵌套调用，第一个 `)` 就把参数截断了，导致明明写了 credentials 也被判缺。
    改为**按语句取窗口**：截到行尾 / 函数末 / 下一个 fetch 之前，三者取最先者。
    """
    pat = re.compile(r"fetch\(\s*['\"]/api/store/(me|orders/mine)['\"]")
    out: List[str] = []
    for m in pat.finditer(src):
        seg = src[m.start(): m.start() + 300]
        for stop in ("\n", "\nfunction ", "\n}"):
            i = seg.find(stop)
            if i > 0:
                seg = seg[:i]
        i = seg.find("fetch(", 1)          # 不跨到下一个 fetch
        if i > 0:
            seg = seg[:i]
        if "credentials" not in seg:
            out.append("/api/store/" + m.group(1))
    return out


def main() -> int:
    rc = 0
    if not os.path.exists(_HTML):
        print(f"FAIL — 找不到 {_HTML}")
        return 1
    src = open(_HTML, encoding="utf-8").read()

    print("=" * 74)
    print("D-78 · 超市前端登录门禁护栏（防「已登录却被要求二次登录」回潮）")
    print("=" * 74)

    # ① 旧门禁不得回潮
    old = _old_gate_hits(src)
    rc |= not check("① store.html 无 `if(!store_token)` 旧门禁残留",
                    not old, f"残留 {len(old)} 处")

    # ② requireAuth 定义 + 自带探活
    rc |= not check("② requireAuth() 已定义", _require_auth_defined(src))
    rc |= not check("②b requireAuth() 自带探活（防页面加载时序竞态误判未登录）",
                    _require_auth_probes(src))

    # ③ 四处动作都受保护
    missing = _unprotected(src)
    rc |= not check("③ 四处动作均走 requireAuth（%s）" % "/".join(_PROTECTED),
                    not missing, f"未保护：{missing}" if missing else "4/4")

    # ④ 登出清真值
    rc |= not check("④ 登出清 STORE_USER（不再清已废用的 store_token）",
                    _logout_clears_truth(src))

    # ⑤ 登录后重放
    rc |= not check("⑤ 登录成功后重放 PENDING_ACTION（修「输完密码没进画面」）",
                    _replay_present(src))

    # ⑥ credentials
    nocred = _session_fetch_without_credentials(src)
    rc |= not check("⑥ 会话类 fetch 均带 credentials（Cookie 会话）",
                    not nocred, f"缺：{nocred}" if nocred else "全部携带")

    # ---- 反向测试（证明护栏会响） ----
    # ⑦ 注入旧门禁写法 ⇒ ① 必须报
    injected = src.replace("function openCustom(){",
                           "function openCustom(){\n  if(!store_token){ showLogin(); return; }", 1)
    rc |= not check("⑦ 反向测试 A：注入旧门禁写法 ⇒ ① 必须报",
                    len(_old_gate_hits(injected)) > 0,
                    f"报出 {len(_old_gate_hits(injected))} 处")

    # ⑧ 抽掉 openBuy 的 requireAuth ⇒ ③ 必须报
    stripped = src.replace("function openBuy(shelfId){\n  requireAuth(function(){",
                           "function openBuy(shelfId){\n", 1)
    miss2 = _unprotected(stripped)
    rc |= not check("⑧ 反向测试 B：抽掉 openBuy 的 requireAuth ⇒ ③ 必须报",
                    "openBuy" in miss2, f"报出 {miss2}")

    # ⑨ 删掉重放逻辑 ⇒ ⑤ 必须报
    noreplay = re.sub(r"if\s*\(\s*PENDING_ACTION\s*\)\s*\{\s*var\s+act\s*=\s*PENDING_ACTION[^}]*\}",
                      "", src, count=1)
    rc |= not check("⑨ 反向测试 C：删掉重放逻辑 ⇒ ⑤ 必须报",
                    not _replay_present(noreplay))

    n_pass = sum(1 for c in CHECKS if c["ok"])
    print("-" * 74)
    print(f"汇总：{n_pass} PASS / {len(CHECKS) - n_pass} FAIL / 共 {len(CHECKS)} 项")
    if rc == 0:
        print("ALL PASS — 登录门禁走真实登录态，无旧门禁回潮，护栏会响")
    else:
        print("FAIL — 登录门禁存在回潮或护栏失效，请按上方 FAIL 项修复")
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
