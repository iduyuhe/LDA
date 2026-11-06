#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CI 影响面闭包计算器（**只报告，不改变任何 CI 行为**）

为什么需要它
--------------------------------
「子集全绿 ≠ 全量绿」在本仓有**四次实证**，根因都是**人工维护的子集清单会漏**。
所以受影响集合必须**自动算**：用 AST 建 import 图，算反向闭包。

分级
----------------
- 轻门禁（< 30 s，350 道）：**每次都跑**
- 重门禁（>= 30 s，55 道）：**只跑受影响的**
- 闭包过大或命中 T1~T4：升级 D2 全量

用法
----
    python scripts/ci_closure.py --files lda/lda_l2/ecore/ddrc_lvs.py
    python scripts/ci_closure.py --git-diff HEAD~1
    python scripts/ci_closure.py --files ... --json
    python scripts/ci_closure.py --self-test

⚠️ 本脚本只产出报告，**不改变现有 CI 行为**。
   接入 `core_fast_smokes()` 前必须先人工核对输出是否合理。
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG_ROOT = os.path.join(ROOT, "lda")          # 门禁脚本以 lda/ 为 sys.path 根
BASELINE = os.path.join(ROOT, "lda", "timeout_budget_baseline.json")

#: 闭包模块数阈值 —— **未校准**。
#: 校准方法：取历史 5~10 次真实改动，算闭包大小与受影响门禁数，取「能覆盖全部真事故」的最小值。
#: 在校准前，**边界情形一律升级 D2**（fail-safe）。
CLOSURE_THRESHOLD = 50
CLOSURE_THRESHOLD_CALIBRATED = False

#: 轻/重分界（与 run_ci_regression.FAST_EXCLUDE_SECONDS 一致）
HEAVY_SECONDS = 30.0


# ---------------------------------------------------------------------------
# 一、模块索引
# ---------------------------------------------------------------------------
def build_index() -> dict:
    """扫描 lda/ 下所有 .py，得到 `模块名 -> 相对路径`。

    模块名以 `lda/` 为根（因为门禁脚本用 `from lda_l2.ecore import ...`）。
    `__init__.py` 映射到其包名。
    """
    idx = {}
    for dirpath, _dirnames, filenames in os.walk(PKG_ROOT):
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, PKG_ROOT).replace(os.sep, "/")
            parts = rel[:-3].split("/")
            if parts[-1] == "__init__":
                parts = parts[:-1]
                if not parts:
                    continue
            idx[".".join(parts)] = rel
    return idx


def path_to_module(path: str) -> str | None:
    """`lda/lda_l2/ecore/dpnr.py` -> `lda_l2.ecore.dpnr`"""
    p = os.path.abspath(path)
    try:
        rel = os.path.relpath(p, PKG_ROOT).replace(os.sep, "/")
    except ValueError:
        return None
    if not rel.endswith(".py") or rel.startswith(".."):
        return None
    parts = rel[:-3].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
        if not parts:
            return None
    return ".".join(parts)


# ---------------------------------------------------------------------------
# 二、AST 解析 import
# ---------------------------------------------------------------------------
def _pkg_of(mod: str) -> list:
    return mod.split(".")[:-1]


def parse_imports(path: str, modname: str, idx: dict) -> set:
    """解析一个文件的 import，返回**项目内**模块名集合。

    覆盖四种形态：
      ① `import lda_l2.ecore.dpnr`
      ② `from lda_l2.ecore import dpnr as P`
      ③ `from lda_l2.ecore.dpnr import foo`
      ④ `from . import x` / `from .b import y` / `from ..core import z`（相对导入）
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read(), filename=path)
    except SyntaxError:
        return set()

    out = set()

    def _consider(name: str) -> None:
        """同时尝试 `a.b.c` 与 `a.b`，取索引里存在的那个（无法静态区分模块与属性）。"""
        if not name:
            return
        if name in idx:
            out.add(name)
            return
        head = name.rsplit(".", 1)[0]
        if head and head in idx:
            out.add(head)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                _consider(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                base = _pkg_of(modname)
                cut = len(base) - (node.level - 1)
                base = base[:cut] if cut > 0 else []
                prefix = ".".join(base)
                if node.module:
                    full = (prefix + "." + node.module) if prefix else node.module
                    _consider(full)
                    for a in node.names:
                        _consider(full + "." + a.name)
                else:
                    for a in node.names:
                        _consider((prefix + "." + a.name) if prefix else a.name)
            else:
                if node.module:
                    _consider(node.module)
                    for a in node.names:
                        _consider(node.module + "." + a.name)
    return out


# ---------------------------------------------------------------------------
# 三、图与闭包
# ---------------------------------------------------------------------------
def build_graph(idx: dict) -> tuple:
    """返回 (forward, reverse)：forward[mod] = 它依赖的模块集；reverse[mod] = 谁依赖它。"""
    forward, reverse = {}, {}
    for mod, rel in idx.items():
        full = os.path.join(PKG_ROOT, rel)
        deps = parse_imports(full, mod, idx)
        deps.discard(mod)
        forward[mod] = deps
    for mod, deps in forward.items():
        reverse.setdefault(mod, set())
        for d in deps:
            reverse.setdefault(d, set()).add(mod)
    return forward, reverse


def reverse_closure(seeds: set, reverse: dict) -> set:
    """谁（传递地）依赖 seeds。含 seeds 自身。"""
    seen = set(seeds)
    q = deque(seeds)
    while q:
        cur = q.popleft()
        for up in reverse.get(cur, ()):
            if up not in seen:
                seen.add(up)
                q.append(up)
    return seen


def forward_closure(seed: str, forward: dict) -> set:
    """seed（传递地）依赖谁。含自身。"""
    seen = {seed}
    q = deque([seed])
    while q:
        cur = q.popleft()
        for d in forward.get(cur, ()):
            if d not in seen:
                seen.add(d)
                q.append(d)
    return seen


# ---------------------------------------------------------------------------
# 四、耗时台账
# ---------------------------------------------------------------------------
def load_elapsed() -> dict:
    """门禁脚本名 -> 实测上界秒数（来自 timeout_budget_baseline.json）。"""
    try:
        with open(BASELINE, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return {}
    return {r["script"]: float(r.get("elapsed_max_s") or 0.0)
            for r in d.get("rows", [])}


def load_gates(idx: dict) -> dict:
    """门禁清单 = **台账的行**（405 道，即 `CORE_SMOKES` 的实测记录）。

    🔴 **不能用 `glob lda/run_*.py`**（自查抓到的 bug）：
        glob 会找到 **443 道**，多出 `run_agent` / `run_ci_regression` /
        `run_cpo_array_demo` 等**非 CORE 成员**的演示/元脚本；且 39 道**无耗时记录**
       （若把无记录者默认当 0 s，会被误归入"轻门禁"而漏跑）⇒ 必须用台账做权威清单。

    返回 {门禁脚本名(不含 .py): (模块名, 秒数)}。
    """
    out = {}
    for script, sec in load_elapsed().items():
        if script.startswith("lda_harness/"):
            mod = script[:-3].replace("/", ".")
        else:
            mod = script[:-3]
        if mod in idx:
            out[mod] = (mod, sec)
        else:
            out[mod] = (mod, sec)   # 保留：可能是子目录脚本，闭包匹配时自然为空
    return out


# ---------------------------------------------------------------------------
# 五、主分析
# ---------------------------------------------------------------------------
def analyse(changed_files: list, verbose: bool = True) -> dict:
    idx = build_index()
    forward, reverse = build_graph(idx)
    gates = load_gates(idx)          # 权威清单 = 台账 405 道

    seeds, unknown = set(), []
    for f in changed_files:
        m = path_to_module(os.path.join(ROOT, f) if not os.path.isabs(f) else f)
        if m and m in idx:
            seeds.add(m)
        else:
            unknown.append(f)

    if not seeds:
        return {"error": "没有可识别的项目内模块", "unknown": unknown}

    rclos = reverse_closure(seeds, reverse)

    hit_light, hit_heavy = [], []
    for g in sorted(gates):
        _mod, t = gates[g]
        deps = forward_closure(g, forward)
        if deps & rclos:
            (hit_heavy if t >= HEAVY_SECONDS else hit_light).append((g, t))

    # D1 = 全部轻门禁 + 受影响重门禁
    all_light = [(g, t) for g, (_m, t) in gates.items() if t < HEAVY_SECONDS]
    d1_cost = sum(t for _, t in all_light) + sum(t for _, t in hit_heavy)

    escalate = []
    if len(rclos) >= CLOSURE_THRESHOLD:
        escalate.append("闭包 %d 个模块 >= 阈值 %d（**阈值未校准**）"
                        % (len(rclos), CLOSURE_THRESHOLD))
    for f in changed_files:
        base = os.path.basename(f)
        if base in ("pyproject.toml", "README.md", "CONTRIBUTING.md"):
            escalate.append("%s 变化（疑似翻版 ⇒ T1）" % base)
        if base == "run_ci_regression.py":
            escalate.append("%s 变化（CORE 册可能变 ⇒ T2）" % base)

    res = {
        "changed_files": changed_files,
        "unknown_files": unknown,
        "n_seed_modules": len(seeds),
        "n_reverse_closure": len(rclos),
        "closure_threshold": CLOSURE_THRESHOLD,
        "threshold_calibrated": CLOSURE_THRESHOLD_CALIBRATED,
        "hit_light_gates": [g for g, _ in hit_light],
        "hit_heavy_gates": [{"gate": g, "elapsed_s": round(t, 1)} for g, t in hit_heavy],
        "all_light_count": len(all_light),
        "d1_estimated_seconds": round(d1_cost, 1),
        "d1_estimated_minutes": round(d1_cost / 60.0, 1),
        "escalate_to_d2": escalate,
        "recommend": "D2" if escalate else "D1",
    }
    if verbose:
        _print(res)
    return res


def _print(r: dict) -> None:
    print("=" * 74)
    print("CI 影响面闭包（只报告，不改 CI 行为）")
    print("=" * 74)
    print("改动文件：%d 个" % len(r["changed_files"]))
    for f in r["changed_files"]:
        print("   ", f)
    if r["unknown_files"]:
        print("  ⚠️ 无法识别（不计入种子）：")
        for f in r["unknown_files"]:
            print("   ", f)
    print()
    print("种子模块 %d 个 → 反向闭包 **%d 个模块**（阈值 %d%s）"
          % (r["n_seed_modules"], r["n_reverse_closure"], r["closure_threshold"],
             "，未校准" if not r["threshold_calibrated"] else ""))
    print()
    print("受影响重门禁（>= %.0fs）：" % HEAVY_SECONDS)
    if r["hit_heavy_gates"]:
        for h in r["hit_heavy_gates"]:
            print("   + %-44s %7.1fs" % (h["gate"], h["elapsed_s"]))
    else:
        print("   （无）")
    print("受影响轻门禁：%d 道（无论如何都全跑）" % len(r["hit_light_gates"]))
    print()
    print("D1 预估：%d 道轻门禁 + %d 道重门禁 ≈ **%.1f 分钟**"
          % (r["all_light_count"], len(r["hit_heavy_gates"]), r["d1_estimated_minutes"]))
    print()
    if r["escalate_to_d2"]:
        print("🔴 **建议升级 D2 全量**，理由：")
        for e in r["escalate_to_d2"]:
            print("   -", e)
    else:
        print("✅ 建议 D1（无需全量）")
    print()
    print("⚠️ 时长为台账 elapsed 相加推算，**不含进程启动开销**，")
    print("   真实值可能高 30~50%%；首次实跑后必须回填。")


# ---------------------------------------------------------------------------
# 六、自检（V2 反向探针：故意破坏 ⇒ 必红）
# ---------------------------------------------------------------------------
def self_test() -> int:
    fails = []

    def chk(name, cond, detail=""):
        print(("  ✅ " if cond else "  ❌ ") + name + (("  " + detail) if detail else ""))
        if not cond:
            fails.append(name)

    print("== 自检 ==")
    idx = build_index()
    chk("模块索引非空", len(idx) > 300, "n=%d" % len(idx))
    chk("ecore.dpnr 在索引内", "lda_l2.ecore.dpnr" in idx)
    chk("路径反解一致", path_to_module(os.path.join(PKG_ROOT, "lda_l2/ecore/dpnr.py"))
        == "lda_l2.ecore.dpnr")

    # 相对导入解析（用真实文件验证）
    p = os.path.join(PKG_ROOT, "lda_l2/ecore/ddrc_lvs.py")
    if os.path.exists(p):
        deps = parse_imports(p, "lda_l2.ecore.ddrc_lvs", idx)
        chk("ddrc_lvs 解析到项目内依赖", len(deps) >= 1, str(sorted(deps)[:3]))

    forward, reverse = build_graph(idx)
    # 方向性：改 ecore 的底层，必须能闭包到门禁脚本
    r = reverse_closure({"lda_l2.ecore.ddrc_lvs"}, reverse)
    chk("反向闭包含门禁脚本", any(m.startswith("run_") for m in r),
        "n=%d" % len(r))

    # 反向探针 1：方向搞反就必红 —— 门禁脚本自身不应出现在「它依赖的」集合之外
    fc = forward_closure("run_ecore_e37_smoke", forward)
    chk("正向闭包含 ddrc_lvs（e37 直接用它）", "lda_l2.ecore.ddrc_lvs" in fc,
        "n=%d" % len(fc))
    chk("反向闭包不含无关模块（抽取性）",
        "lda_qeda.gates" not in reverse_closure({"lda_l2.ecore.ddrc_lvs"}, reverse))

    # 反向探针 2：不存在的模块 ⇒ 空闭包（不许瞎报）
    chk("未知模块闭包为空", reverse_closure({"no.such.mod"}, reverse) == {"no.such.mod"})

    print()
    if fails:
        print("❌ 自检失败 %d 项：%s" % (len(fails), fails))
        return 1
    print("✅ 自检全部通过")
    return 0


# ---------------------------------------------------------------------------
def git_changed(ref: str) -> list:
    out = subprocess.run(
        ["git", "diff", "--name-only", ref],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    files = [l.strip() for l in (out.stdout or "").splitlines() if l.strip()]
    return [f for f in files if f.endswith(".py")]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="CI 影响面闭包计算器（只报告）")
    ap.add_argument("--files", nargs="*", default=None, help="改动文件（相对仓库根）")
    ap.add_argument("--git-diff", default=None, metavar="REF",
                    help="用 `git diff --name-only REF` 取改动文件（如 HEAD~1）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--self-test", action="store_true", help="自检")
    a = ap.parse_args(argv)

    if a.self_test:
        return self_test()

    files = list(a.files or [])
    if a.git_diff:
        files += git_changed(a.git_diff)
    if not files:
        ap.error("需要 --files 或 --git-diff（或 --self-test）")

    r = analyse(sorted(set(files)), verbose=not a.json)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if "error" not in r else 2


if __name__ == "__main__":
    sys.exit(main())
