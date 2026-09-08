# -*- coding: utf-8 -*-
"""P2.5 · 重计算 POST 登录闸门完备性护栏（v0.9.6x · 权限审计 2026-09-09）。

🔴 防什么（审计新发现，2026-09-09）
-------------------------------
v0.9.7 定下纪律：「重计算须登录」——凡 handler 直调 `_app.run_*`（仿真/求解/
优化内核）的 POST 端点，必须 ∈ routes.HEAVY_POST_PATHS（经 _heavy_guard 的
登录闸门 + 并发护栏），匿名不可触发。

但审计 grep 全部 run_*smoke*.py：**无任何判据守护这张集合**——本次补录的
7 个漏网端点（agent_loop/band_loop/ring_loop/geometry_drc/tapeout/
proposal_design/verify）若未来回退、或再新增重计算端点时漏录，CI 不会响
（「重计算须登录」纪律只靠人工维护）。verify 正是被本 smoke 的设计启发扫出
的第 7 个漏网点（跑全 48 锚判决回路，candidate=perturb/l3_ai 触发真求解器）。

判据（死标量，LLM 不进判决路径）
-------------------------------
C1 接线：HEAVY_POST_PATHS 每个成员都必须真实注册在 POST_ROUTES（防死路径
    躺在集合里假绿——集合里有、路由表没，等于没保护）。
C2 完备：POST_ROUTES 中凡 handler 函数体直调 `_app.run_*`（ast 扫描）的端点
    必须 ∈ HEAVY_POST_PATHS。轻量豁免须显式进 EXEMPT_PUBLIC_RUN 并附实测
    理由（当前为空集；将来若有 run_cs_chat 类 FAQ 毫秒级端点，允许加白但
    必须注释「读码+实测 <xx ms」——宁红不假绿）。
C3 互斥：PUBLIC_RATE_PATHS（公开写端点，IP 限流）与 HEAVY_POST_PATHS
    （登录闸门）无交集——一个端点不可能既「故意公开」又「须登录」。
C4 反向（防假绿）：把 agent_loop / verify 从 HEAVY_POST_PATHS 源码剔除后
    重跑同一扫描器 ⇒ C2 必须 FAIL（证明护栏会响，非重言式）。

运行：python run_heavy_post_gate_smoke.py   （纯静态，<1s）
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUTES = os.path.join(HERE, "lda_webui", "routes.py")

# 轻量豁免（handler 调 run_* 但实测毫秒级、故意公开）——加入必须附实测理由
EXEMPT_PUBLIC_RUN: set = set()


def _parse(src: str):
    """从 routes.py 源码静态解析，返回各集合（纯函数，供正向/反向共用）。

    Returns:
        heavy: HEAVY_POST_PATHS 端点集合
        rate:  PUBLIC_RATE_PATHS 端点集合
        registered: POST_ROUTES 端点 → handler 函数名
        run_eps:    调用了 `_app.run_*` 的 POST 端点集合（减 EXEMPT）
    """

    def block(name: str) -> str:
        i = src.index(name + " = {")
        j = src.index("}", i)
        return src[i:j]

    key_re = re.compile(r'"(/[a-zA-Z0-9_.\-/]+)"')
    heavy = set(key_re.findall(block("HEAVY_POST_PATHS")))
    rate = set(key_re.findall(block("PUBLIC_RATE_PATHS")))
    pr_block = block("POST_ROUTES")
    ent_re = re.compile(r'^\s*"(/[a-zA-Z0-9_.\-/]+)"\s*:\s*(\w+)\s*,', re.M)
    registered = dict(ent_re.findall(pr_block))
    # ast：收集每个 h_* handler 直调 `_app.run_xxx` 的属性名
    tree = ast.parse(src)
    fn_runs = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("h_"):
            attrs = set()
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Attribute)
                        and isinstance(sub.func.value, ast.Name)
                        and sub.func.value.id in ("_app", "app")
                        and sub.func.attr.startswith("run_")):
                    attrs.add(sub.func.attr)
            if attrs:
                fn_runs[node.name] = attrs
    run_eps = {ep for ep, fn in registered.items()
               if fn in fn_runs and ep not in EXEMPT_PUBLIC_RUN}
    return heavy, rate, registered, run_eps


def main() -> int:
    src = open(ROUTES, encoding="utf-8").read()
    heavy, rate, registered, run_eps = _parse(src)
    passed = failed = 0

    def check(name, cond, extra=""):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            failed += 1
            print(f"  [FAIL] {name} {extra}")

    print("=== P2.5 重计算 POST 登录闸门完备性 ===")
    # C1 接线：HEAVY 成员必须真实注册
    dead = sorted(heavy - set(registered))
    check("C1 HEAVY_POST_PATHS(%d) ⊆ POST_ROUTES 注册" % len(heavy),
          not dead, f"死路径: {dead}")
    # C2 完备：run_* 端点必须入闸门
    missing = sorted(run_eps - heavy)
    check("C2 run_* 内核端点(%d) 全部 ∈ HEAVY_POST_PATHS" % len(run_eps),
          not missing, f"漏网: {missing}")
    # C3 互斥：公开限流 ∩ 登录闸门 = ∅
    overlap = sorted(rate & heavy)
    check("C3 PUBLIC_RATE_PATHS ∩ HEAVY_POST_PATHS = ∅", not overlap,
          f"重叠: {overlap}")
    # C4 反向：剔除任一闸门成员，C2 必须 FAIL（护栏会响）
    for victim in ("/api/agent_loop", "/api/verify"):
        # 从 HEAVY_POST_PATHS 块内剔除 victim 字符串（兼容同行多端点：
        # agent_loop 与 band_loop/ring_loop 同行，整行剔除会误伤；残留
        # 空白对语法无害）。POST_ROUTES 注册行不动。
        i = src.index("HEAVY_POST_PATHS = {")
        j = src.index("}", i)
        stripped = src[i:j].replace('"%s",' % victim, "")
        src2 = src[:i] + stripped + src[j:]
        heavy2, _, _, run_eps2 = _parse(src2)
        missing2 = sorted(run_eps2 - heavy2)
        check("C4 反向·剔除 %s ⇒ C2 必须 FAIL" % victim,
              victim in missing2,
              f"剔除后竟仍全在闸门内（假绿！missing={missing2}）")

    print("-" * 50)
    print(f"P2.5 结果：PASS={passed} FAIL={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
