# -*- coding: utf-8 -*-
"""适配器分片布局契约护栏（v0.9.117 · 审计 F-08 巨石拆分的专用门禁）。

背景
----
`lda_harness/verification_adapters.py`（原 6789 行）与 `lda_harness/benchmarks.py`
（原 6633 行）是仓库两个巨石模块（2026-09-19 代码审计 F-08）。拆分（T2.2）的
**最大风险不是"拆不开"，而是拆的过程悄悄改变注册表**：

  * `@_register_candidate` 按 **decorator 执行顺序**写入 `BENCHMARK_CANDIDATES`，
    其**插入序即全仓遍历序** ⇒ facade 少加载任一片、或调换片序，都会**静默**
    少项 / 改序，而账本三分类随之变化（"拆完看着全绿，账本已换"）。
  * 若某个片在片内**新建同名注册表或装饰器**，注册表被割裂成两份，
    两侧各看一半 ⇒ 同样是静默失真。

`scripts/registry_snapshot.py --check` 能抓「拆前/拆后」的一次性漂移，但它：
  ① 需要一份外部快照文件（不是常驻门禁）；
  ② `benchmark_candidates` 只记 `[key, func.__name__]`、`benchmark_defs_keys` 只记
     **键** ⇒ 对「片被漏加载后**恰好**项数不变」之类结构性缺陷无能为力。
故本 smoke 把**布局契约**本身机器化，作为**常驻**门禁（入 CORE_SMOKES）。

判据（死标量 · LLM 不进判决路径）
--------------------------------
  L0  facade + 分片**可导入**（少加载片 ⇒ `_ASSEMBLY_CONTRACT` 引用未定义名 ⇒
      NameError；降级为明确判红而非 traceback）
  L1  注册表**单一实例**：`_adapter_core.BENCHMARK_CANDIDATES is facade.BENCHMARK_CANDIDATES`
  L2  `_adapter_p1..p6` **全部**已加载（在场于 `sys.modules`）
  L3  各片的 `_register_candidate` **就是** core 的那个（无片内自称装饰器）
  L4  **逐片**：运行时贡献数 == 该片顶层 `@_register_candidate` 的 AST 计数
      （静态定义 vs 运行时生效，两侧独立取证 ⇒ 抓「漏加载 / 未执行 / 重复注册」）
  L5  合计 == `len(BENCHMARK_CANDIDATES)` **且** 键唯一（无静默覆盖）
  L6  装配顺序契约：facade 源文本中 `from . import (…)` 的次序
      == `_ASSEMBLY_CONTRACT` 元组次序 == p1..p6
  L7  DEFS 引用完整性：`BENCHMARK_DEFS` 声明过的 `candidate` 全部已注册
  L8  re-export 契约：`_REEXPORT_CONTRACT` 每个名字都能从 facade 取到
  L9  磁盘上的 `_adapter_p*.py` **实际文件数** == 装配契约片数（防「加了片忘接线」）
  L10 🔴 **反向测试**：子进程**只**加载 core + p1 ⇒ 注册数必等于 p1 静态数且
      **小于**全量 ⇒ 证明 L4/L5 的「漏片」方向**真会变红**（非恒真）
  L11 🔴 **反证对照**：全量合规输入下 L4 判定**必须为真**（证明 L4 非恒假、
      非"全等"式自证 —— 缺它则反向判据可被空判据假绿）
  L12 自食其规则：本 smoke 自身在 `CORE_SMOKES` 内

运行：python run_adapter_shard_layout_smoke.py
"""
from __future__ import annotations

import ast
import collections
import glob
import os
import subprocess
import sys

from lda_harness.smoke_kit import make_check

_HERE = os.path.dirname(os.path.abspath(__file__))          # …/lda
_HARNESS = os.path.join(_HERE, "lda_harness")
_SELF = "run_adapter_shard_layout_smoke.py"
_FACADE = os.path.join(_HARNESS, "verification_adapters.py")
_CORE = "_adapter_core.py"
_NPARTS = 6
_PART_FILES = ["_adapter_p%d.py" % i for i in range(1, _NPARTS + 1)]
_PART_MODS = ["lda_harness._adapter_p%d" % i for i in range(1, _NPARTS + 1)]

_NP = 0
_NF = 0
check = make_check(globals(), ok_key="_NP", bad_key="_NF", indent="  ",
                   detail_fmt="  —— {d}", detail_on="fail", return_ok=True)


# ------------------------------------------------------------------ 静态取证
def static_reg_count(path):
    """该文件**顶层**函数定义上 `@_register_candidate(...)` 的条数（AST 计数）。"""
    with open(path, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    n = 0
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for d in node.decorator_list:
            if (isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
                    and d.func.id == "_register_candidate"):
                n += 1
    return n


def _tuple_names(node):
    """把 `X = (a, b, c)` 的元组取值还原成名字列表。"""
    for t in ast.walk(node):
        if isinstance(t, ast.Tuple):
            out = []
            for e in t.elts:
                if isinstance(e, ast.Name):
                    out.append(e.id)
                elif isinstance(e, ast.Attribute):
                    out.append(e.attr)
                else:
                    out.append("<?>")
            return out
    return []


def facade_contracts():
    """从 facade 源文本取出 (装配元组, 导入次序, re-export 元组, 导入块原始名)。"""
    with open(_FACADE, "r", encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src)
    asm, rex, imp_order = [], [], []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if not isinstance(tgt, ast.Name):
                    continue
                if tgt.id == "_ASSEMBLY_CONTRACT":
                    asm = _tuple_names(node.value)
                elif tgt.id == "_REEXPORT_CONTRACT":
                    rex = _tuple_names(node.value)
        elif isinstance(node, ast.ImportFrom) and node.level == 1 and node.module is None:
            imp_order = [a.name for a in node.names]
    return {"asm": asm, "rex": rex, "imp": imp_order, "src": src}


# ------------------------------------------------------------------ 反向取证
_REV_SNIPPET = (
    "import lda_harness._adapter_p1\n"
    "import lda_harness._adapter_core as C\n"
    "print(len(C.BENCHMARK_CANDIDATES))\n"
)


def _run_sub(env, code):
    return subprocess.run([sys.executable, "-c", code], cwd=_HERE, env=env,
                          capture_output=True, text=True, timeout=180)


def main() -> int:
    print("=" * 76)
    print("适配器分片布局契约护栏 — F-08 拆分后注册表不得静默少项/改序/割裂")
    print("=" * 76)

    rc = 0
    # ---- L0 可导入性（fail-closed 且可读）----
    # 🔴 少加载任何一个分片都会让 facade 的 `_ASSEMBLY_CONTRACT` 引用到**未定义名**
    #    ⇒ facade 直接 NameError 不可导入 ⇒ 全仓凡 import 它的模块（含本 smoke）
    #    连锁崩。此处把它降级为一条**明确判红**，避免以 traceback 面目出现。
    try:
        import lda_harness.verification_adapters as V
        import lda_harness._adapter_core as C
        from lda_harness import benchmarks as B
    except Exception as ex:                                   # noqa: BLE001
        check("L0 facade + 分片可导入（少加载片 ⇒ _ASSEMBLY_CONTRACT 名未定义）",
              False, "%s: %s" % (type(ex).__name__, ex))
        print("-" * 76)
        print("汇总：%d PASS / %d FAIL / 共 %d 项" % (_NP, _NF, _NP + _NF))
        print("FAIL — 拆分布局已破损到无法导入（优先检查 facade 的 import 块）")
        return 1

    cand = V.BENCHMARK_CANDIDATES
    check("L0 facade + 分片可导入（少加载片 ⇒ _ASSEMBLY_CONTRACT 名未定义）",
          True, "%d 项候选已注册" % len(cand))

    # ---- L1 单一注册表实例 ----
    same_obj = C.BENCHMARK_CANDIDATES is cand
    rc |= not check("L1 注册表单一实例（core 与 facade 同一 dict）", same_obj,
                    "同一对象" if same_obj else "!! 两份注册表（片内新建了容器）")

    # ---- L2 六片全加载 ----
    absent = [m for m in _PART_MODS if m not in sys.modules]
    rc |= not check("L2 %d 个分片全部已加载" % _NPARTS, not absent,
                    ("缺 %s" % absent) if absent else "p1..p%d 全在场" % _NPARTS)

    # ---- L3 装饰器唯一 ----
    foreign = []
    for i in range(1, _NPARTS + 1):
        m = sys.modules.get("lda_harness._adapter_p%d" % i)
        if m is None:
            continue
        f = getattr(m, "_register_candidate", None)
        if getattr(f, "__module__", None) != "lda_harness._adapter_core":
            foreign.append("p%d" % i)
    rc |= not check("L3 各片 _register_candidate 即 core 的实现", not foreign,
                    ("片内自称装饰器：%s" % foreign) if foreign else "6/6 指向 core")

    # ---- L4/L5 逐片静态 vs 运行时 ----
    contrib = collections.Counter(getattr(f, "__module__", None) for f in cand.values())
    rows, bad_rows = [], []
    tot_static = 0
    for i, fn in enumerate(_PART_FILES, 1):
        st = static_reg_count(os.path.join(_HARNESS, fn))
        rt = contrib.get("lda_harness._adapter_p%d" % i, 0)
        tot_static += st
        rows.append((i, st, rt))
        if st != rt:
            bad_rows.append("p%d 静态%d≠运行%d" % (i, st, rt))
    print("    分片  顶层@装饰(AST)  运行时注册")
    for i, st, rt in rows:
        print("      p%-3d %-14d %d" % (i, st, rt))
    rc |= not check("L4 逐片 静态 AST 计数 == 运行时贡献数", not bad_rows,
                    ("; ".join(bad_rows)) if bad_rows
                    else "6/6 逐片相等（合计 %d）" % tot_static)

    rc |= not check("L5 合计 == 注册表长度 且 键唯一",
                    tot_static == len(cand) == len(set(cand)),
                    "静态 %d · 注册 %d · 去重 %d" % (tot_static, len(cand), len(set(cand))))

    # ---- L6 装配顺序契约 ----
    fc = facade_contracts()
    want = [m.split(".")[-1] for m in _PART_MODS]        # p1..p6
    ok_order = (fc["imp"] == want == fc["asm"])
    rc |= not check("L6 装配顺序契约：import 块 == _ASSEMBLY_CONTRACT == p1..p6",
                    ok_order, "import=%s · 契约=%s" % (fc["imp"], fc["asm"]))

    # ---- L7 DEFS 引用完整性 ----
    declared = {d.get("candidate") for d in B.BENCHMARK_DEFS.values() if d.get("candidate")}
    dangling = sorted(declared - set(cand))
    rc |= not check("L7 BENCHMARK_DEFS 声明的 candidate 全部已注册",
                    not dangling,
                    ("悬空 %s" % dangling[:6]) if dangling
                    else "%d 个声明全部命中" % len(declared))

    # ---- L8 re-export 契约 ----
    missing = [n for n in fc["rex"] if not hasattr(V, n)]
    rc |= not check("L8 facade re-export 契约（%d 个名字）全部可取" % len(fc["rex"]),
                    fc["rex"] and not missing,
                    ("缺 %s" % missing) if missing else "全部可取")

    # ---- L9 磁盘片文件数 == 装配契约片数 ----
    found = sorted(os.path.basename(p)
                   for p in glob.glob(os.path.join(_HARNESS, "_adapter_p*.py")))
    rc |= not check("L9 磁盘 _adapter_p*.py 数 == 装配契约片数",
                    len(found) == len(fc["asm"]) == _NPARTS,
                    "磁盘 %d 个 %s · 契约 %d" % (len(found), found, len(fc["asm"])))

    # ---- L10 反向测试：只加载 core + p1 ⇒ 必少于全量 ----
    env = dict(os.environ)
    env["PYTHONPATH"] = _HERE + os.pathsep + env.get("PYTHONPATH", "")
    p1_static = rows[0][1]
    try:
        r = _run_sub(env, _REV_SNIPPET)
        got = int((r.stdout or "").strip().splitlines()[-1]) if r.returncode == 0 else -1
        why = "" if r.returncode == 0 else (r.stderr or "")[-200:]
    except Exception as ex:                                   # noqa: BLE001
        got, why = -1, str(ex)
    rc |= not check("L10 反向：仅加载 core+p1 ⇒ 注册数 == p1 静态数 且 < 全量",
                    got == p1_static and got < len(cand),
                    "得 %d（p1 静态 %d · 全量 %d）%s" % (got, p1_static, len(cand), why))

    # ---- L11 反证对照：合规全量下 L4 必须为真（非恒假/非空判据） ----
    rc |= not check("L11 反证对照：全量合规 ⇒ L4 判定为真（判据有区分度）",
                    not bad_rows and len(cand) > 0,
                    "L4 无违例且注册表非空 ⇒ 判据既能变红也能为真")

    # ---- L12 自食其规则 ----
    try:
        import run_ci_regression as R
        in_core = _SELF in R.CORE_SMOKES
    except Exception as ex:                                   # noqa: BLE001
        in_core = False
        print("    （无法读取 CORE_SMOKES：%s）" % ex)
    rc |= not check("L12 本 smoke 自身在 CORE_SMOKES 内（自食其规则）",
                    in_core, "" if in_core else "门禁自己被漏接！")

    print("-" * 76)
    print("汇总：%d PASS / %d FAIL / 共 %d 项" % (_NP, _NF, _NP + _NF))
    if rc == 0:
        print("ALL PASS — 拆分布局与注册表契约一致（无少项 / 无改序 / 无割裂）")
    else:
        print("FAIL — 分片布局契约被破坏：请检查 facade 的 import 次序、"
              "各片装饰器、以及是否漏加载了分片")
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
