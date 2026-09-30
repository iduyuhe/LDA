#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
死断言常驻扫描门禁（D-145 防回潮 · 2026-09-30 入 CI core）。

血案 D-145 场景：重构后，某突变探针 patch 的入口已不被消费
⇒ 探针「仍绿」被静默放过（护栏失效 = 死断言）。本 smoke 把这一防御
做成常驻 CI core 门禁，**纯静态（AST + 文本子串）、不改任何源码、
不起子进程**，故可安全常驻。

对 scripts/ 下每一个 *_probe.py，核验：
  ① 探针声明的「突变锚点」（mutate/patch/replace_in 的第一实参串）
     仍真实存在于其当前目标源码中（即探针仍在改 LIVE 代码，而非
     已失效的死文本）；只要声明了字符串锚点而该串已从活代码消失，
     即判为 dead_probe → FAIL。
  ② 探针声明的目标源文件（SRC/TARGET 赋值串）真实存在；
     目标文件被删 ⇒ 探针指向死对象 → FAIL。
  ③ 探针文件本身可被 AST 解析（语法损坏 ⇒ FAIL）。
  ④ 探针声明了 0 个字符串锚点（monkeypatch / 动态 mutate(d,kw,med) 类）
     → 计为 live（其「仍绿」由运行时 patch 目标是否存在兜底），
     仅打 soft note，不判失败。

任一项硬失败 → 门禁 FAIL，并把 dead 探针逐一列出，强制人类把探针
重定向到更根本的入口（血案 25 通则）。

红线：本 smoke 只读 scripts/*_probe.py 与其目标源码，绝不修改、绝不 import
被测业务模块（避免副作用）。判据由本文件机器执行，LLM 不进判决。
"""
import ast
import glob
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))      # .../lda
REPO = os.path.dirname(_HERE)                            # .../D:/agent_LDA
SCRIPTS_DIR = os.path.join(REPO, "scripts")

# 探针里用来「按串改源码」的函数名（第一实参即突变锚点串）。
_ANCHOR_FUNCS = ("mutate", "patch", "replace_in", "replace")
# 探针里声明目标源文件的赋值名。
_TARGET_NAMES = ("SRC", "TARGET", "SRC_PATH", "TARGET_PATH", "SRC_FILE")


def _iter_string_consts(node):
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            yield n.value


def parse_probe(path):
    """返回 (targets, anchors, src_text)。"""
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    targets, anchors = [], []
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id in _TARGET_NAMES:
                    if isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
                        targets.append(n.value.value)
        if isinstance(n, ast.Call):
            fn = n.func
            fname = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
            if fname in _ANCHOR_FUNCS and n.args:
                a0 = n.args[0]
                if isinstance(a0, ast.Constant) and isinstance(a0.value, str) and a0.value:
                    anchors.append(a0.value)
    return targets, anchors, src


def resolve_target(path):
    if os.path.isabs(path) and os.path.exists(path):
        return path
    for base in (REPO, _HERE):
        cand = os.path.join(base, path)
        if os.path.exists(cand):
            return cand
    # 容错：探针里可能写成 "lda/xxx.py" 或 "scripts/xxx.py"
    cand = os.path.join(REPO, os.path.basename(path))
    return cand if os.path.exists(cand) else None


def main():
    probes = sorted(glob.glob(os.path.join(SCRIPTS_DIR, "*_probe.py")))
    if not probes:
        print("[FAIL] scripts/ 下未发现任何 *_probe.py（突变探针体系缺失）")
        sys.exit(1)

    dead, live, dynamic = [], 0, 0
    for p in probes:
        name = os.path.basename(p)
        try:
            targets, anchors, src = parse_probe(p)
        except SyntaxError as e:
            dead.append((name, "探针语法损坏，AST 解析失败: %s" % e))
            continue

        problems = []

        # ② 目标文件存在性
        resolved = []
        for t in targets:
            r = resolve_target(t)
            if r is None:
                problems.append("声明的目标源文件不存在: %s" % t)
            else:
                resolved.append(r)

        # ① 字符串锚点活性（D-145 核心判据）
        if anchors and resolved:
            missing = []
            for r in resolved:
                tsrc = open(r, encoding="utf-8").read()
                for a in anchors:
                    if a not in tsrc:
                        missing.append((os.path.basename(r), a[:48]))
            if missing:
                problems.append("死锚点（声明的突变串已不在活代码中）=%r" % (missing[:5],))
        elif anchors and not resolved:
            # 目标文件全缺失时，锚点活性无法核验，但目标缺失已记问题
            pass

        if problems:
            dead.append((name, "; ".join(problems)))
        else:
            if anchors:
                live += 1
            else:
                dynamic += 1
                live += 1

    total = len(probes)
    print("=" * 72)
    print("死断言常驻扫描：扫描 %d 个突变探针 · live=%d（其中动态/monkeypatch=%d）· dead=%d"
          % (total, live, dynamic, len(dead)))
    print("-" * 72)
    for name, why in dead:
        print("  [DEAD] %-30s %s" % (name, why))
    print("-" * 72)
    if dead:
        print("[FAIL] %d 个探针是死断言（D-145 复发风险）：重构后其突变锚点已脱离活代码"
              % len(dead))
        sys.exit(1)
    # 软提示：动态探针靠运行时兜底，提示维护者别误以为静态已覆盖
    if dynamic:
        print("  (note) %d 个探针用 monkeypatch/动态 mutate，无静态锚点，"
              "其「仍绿」由运行时 patch 目标存在性兜底" % dynamic)
    print("[PASS] 全部 %d 个突变探针仍 patch LIVE 代码，无死断言" % live)
    sys.exit(0)


if __name__ == "__main__":
    main()
