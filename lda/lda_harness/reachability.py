# -*- coding: utf-8 -*-
"""D-223 · **公开函数动态可达性分析**（reachability）—— 能力层 · 净增 0 锚。

## 为什么需要它（血案）

v0.9.271 修的那个 bug 是 `sc_readout_mux.resonator_freq_ghz` **偏 1e6 倍**。
它能潜伏很久，原因不是"没人写门禁"，而是：

> **这个函数全仓零引用** ⇒ 344 道门禁一道都没碰过它 ⇒ 没有任何判据能发现它错。

同族的 `resonator_length_um` 有 3 处调用、方向正确、没 bug；反向函数写完就没人用。
这是 **「死函数 ⇒ 无门禁覆盖 ⇒ 自由腐烂」**，与已有的 `dead_assert_guard`
（只扫 `scripts/*_probe.py` 的突变锚点是否还在活代码里）**互补但不重叠**。

## 为什么不能只用正则（记忆里已有血案）

`run_*_selfchecks` / `*_gds` 多以**函数对象**传入回调表，如
`("G2", SC.run_tunable_selfchecks, 8)` —— 名字后面**没有括号**，
正则 `\\bname\\s*\\(` 会判成零调用 ⇒ 假阳性。

## 四层口径（本模块的核心）

| 层 | 内容 | 覆盖的引用形式 |
|---|---|---|
| **L1** | 跨模块符号引用 | `MOD.func(...)` · `from X import func` · `MOD.func` 作对象传递 |
| **L1b** | 本模块**函数体之外**的引用 | `ROUTES = {"/api/x": h_x}` · `if __name__` 块 · 类体 |
| **L2** | 字符串/对象入口 | `BENCHMARK_DEFS[k]["golden_fn"]`（**函数对象**，531/541 条）· `candidate` 函数名字符串 · `getattr(MOD, "name")` |
| **L3** | 同模块传递闭包 | f 被同模块 g 调用且 g 可达 ⇒ f 可达 |

判定：`公开函数集合 − 四层入口的传递闭包 == ∅` 才算活；否则为**死函数候选**。

## 三条实测血案（每一层都是被假阳性逼出来的）

1. **只算「函数体内引用」会漏掉路由表**：`routes.py` 的 `"/api/about": h_about`
   在**模块级 dict** 里 ⇒ 首版把 150 个路由 handler 全判死（占 297 的 50%）。⇒ 补 **L1b**。
2. **只扫字符串会漏掉 `golden_fn`**：`BENCHMARK_DEFS[k]["golden_fn"]` 是**函数对象**
   （531/541 条），不是函数名字符串 ⇒ 会把「锚的黄金实现」整批判死。⇒ 补 **L2 的对象入口**。
3. **只判跨模块会漏掉同文件包装**：`_batch_*_numeric.py` 里 `*_golden` 被同文件
   `_xxx_c` / `golden_bNNN` 包装调用 ⇒ 只看跨模块引用会把活实现判死。⇒ 补 **L3 传递闭包**。

修完这三层，死函数从 **533 → 297 → 96**（占 3389 个公开函数的 **2.83%**），
且**已修复的 `resonator_freq_ghz` 不在名单里** —— 说明判据不是恒真。

## 边界（不得读成"质量分数"）

- 这是**静态可达性**，不是运行时覆盖率：一个函数"可达"不代表"被测过"；
- 私有函数（`_` 前缀）**不在扫描面**（不被外部误当 API 调用，风险等级不同）；
- `_batch_*_numeric.py` 里的 `*_golden` 若只被**已死的私有包装**调用，仍算死
  （本轮实测 `magnetometer_eta_golden` 就是：链是 ← `_eta_golden_c`（死）← 无人，
  而账本真正用的是 `golden_b473`）—— **这类链才是真正该清理的**。
- **本模块不含任何锚号字面量**（避免被 K4 文本代理误判成覆盖），锚相关判断全在
  `reachability_registry.py`（非门禁模块）。

## 红线

纯 `ast` + `os` + `sys`，**不 import 被测业务模块**（唯一例外是
`lda_harness.benchmarks`，因为需要读 `golden_fn` 的函数对象）。零子进程、零落盘、
零网络。LLM 不进判决路径。
"""
from __future__ import annotations

import ast
import os
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

ROLE = ("D-223 · 公开函数动态可达性分析 —— 找出「零引用 ⇒ 无门禁覆盖 ⇒ 自由腐烂」的"
        "公开函数，供门禁与登记表裁决。能力层，不新增锚。")
ANCHORABLE = False

#: 默认扫描面：这些目录下的**顶层公开函数**是分析对象
DEFAULT_TARGET_DIRS = ("lda/lda_qeda", "lda/lda_l2", "lda/lda_harness", "lda/lda_webui")
#: 默认语料面：这些目录下的一切 Python 文件都算「可能的引用方」
DEFAULT_CORPUS_DIRS = ("lda", "scripts", "examples")
#: 语料里要跳过的目录名
SKIP_DIRS = ("__pycache__", ".git", "reports", "node_modules")


def _repo_root(start: Optional[str] = None) -> str:
    """从本文件位置向上两级得到仓库根（`<repo>/lda/lda_harness/reachability.py`）。"""
    if start:
        return start
    here = os.path.dirname(os.path.abspath(__file__))       # .../lda/lda_harness
    return os.path.dirname(os.path.dirname(here))           # .../  (repo root)


def _walk_py(root: str, dirs: Tuple[str, ...]) -> List[str]:
    """列出 `dirs` 下所有 .py 的绝对路径（跳过 SKIP_DIRS），按路径排序保证确定性。"""
    out: List[str] = []
    for d in dirs:
        base = os.path.join(root, d)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, files in os.walk(base):
            dirnames[:] = sorted(x for x in dirnames if x not in SKIP_DIRS)
            for f in sorted(files):
                if f.endswith(".py"):
                    out.append(os.path.join(dirpath, f))
    return sorted(out)


def _parse_file(path: str) -> Optional[ast.Module]:
    """解析单个文件；语法错误返回 None（不抛，由调用方计数）。"""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return ast.parse(fh.read())
    except SyntaxError:
        return None


def ids_in(node: ast.AST) -> Set[str]:
    """子树里出现的全部名字 token：`Attribute.attr` 与 `Name.id`。

    🔴 用 `Attribute.attr` 而不是只看 `Call.func`：回调表里 `SC.func,` **不带括号**，
    只看调用会漏（记忆里的血案）。
    """
    out: Set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Attribute):
            out.add(n.attr)
        elif isinstance(n, ast.Name):
            out.add(n.id)
    return out


def module_level_ids(tree: ast.Module) -> Set[str]:
    """**函数体之外**的名字引用（模块级 dict/list、`if __name__` 块、类体）。

    🔴 血案：`routes.py` 的 `"/api/about": h_about` 在模块级 dict 里，不是任何函数体
    内的调用 ⇒ 只算函数体引用会把整批路由 handler 判死。
    """
    out: Set[str] = set()

    def scan(node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return                                         # 函数体内另算
        for n in ast.walk(node):
            if isinstance(n, ast.Attribute):
                out.add(n.attr)
            elif isinstance(n, ast.Name):
                out.add(n.id)

    for stmt in tree.body:
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            continue
        scan(stmt)
    return out


def public_funcs(tree: ast.Module) -> Dict[str, ast.FunctionDef]:
    """模块顶层的公开函数（不以下划线开头）。"""
    return {n.name: n for n in tree.body
            if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")}


def anchor_entry_names(benchmarks: Any) -> Tuple[Set[str], Set[str]]:
    """从 `BENCHMARK_DEFS` 抽两类入口名。

    返回 `(all_names, golden_fn_names)`：
      - `all_names`：字符串字段里的标识符 ∪ `golden_fn` 的函数名；
      - `golden_fn_names`：仅 `golden_fn` 这一路的（供统计/探针用）。

    🔴 血案：`golden_fn` 是 **callable（函数对象）**，不是字符串 ——
    只扫字符串会把整批「锚的黄金实现」判死。
    """
    all_names: Set[str] = set()
    golden_names: Set[str] = set()
    for v in getattr(benchmarks, "values", lambda: [])():
        fn = v.get("golden_fn") if isinstance(v, dict) else None
        if callable(fn):
            nm = getattr(fn, "__name__", "")
            if nm and nm != "<lambda>":
                all_names.add(nm)
                golden_names.add(nm)
        if isinstance(v, dict):
            for field in ("candidate", "oracle", "metric", "candidate_desc", "title"):
                blob = str(v.get(field, ""))
                for tok in (blob.replace("(", " ").replace(")", " ")
                            .replace(",", " ").split()):
                    tok = tok.strip("\"'`[]{}:")
                    if tok.isidentifier():
                        all_names.add(tok)
    return all_names, golden_names


def _build_reference_index(root: str,
                          corpus_dirs: Tuple[str, ...] = DEFAULT_CORPUS_DIRS
                          ) -> Tuple[Dict[str, Set[str]], int]:
    """建倒排索引 `name -> {引用它的相对路径}`（一次遍历，O(节点数)）。

    索引来源：`Attribute.attr` · `Name.id` · `ImportFrom.names` · 短字符串字面量。
    """
    ref: Dict[str, Set[str]] = {}
    n_files = 0
    for p in _walk_py(root, corpus_dirs):
        tree = _parse_file(p)
        if tree is None:
            continue
        n_files += 1
        rel = os.path.relpath(p, root).replace("\\", "/")
        for name in ids_in(tree):
            ref.setdefault(name, set()).add(rel)
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom):
                for a in n.names:
                    ref.setdefault(a.name, set()).add(rel)
            elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                s = n.value.strip()
                if s and len(s) < 80:
                    ref.setdefault(s, set()).add(rel)
    return ref, n_files


def analyze(root: Optional[str] = None,
            target_dirs: Tuple[str, ...] = DEFAULT_TARGET_DIRS,
            corpus_dirs: Tuple[str, ...] = DEFAULT_CORPUS_DIRS,
            benchmarks: Any = None) -> Dict[str, Any]:
    """核心分析：返回 `{dead, stats, by_module, reachable_total}`。

    `dead` 是**排序后的** `[{"module": rel, "name": fn}]`，保证确定性（同输入同输出）。
    `benchmarks` 不传时自动 import（唯一被 import 的业务模块，只为读 `golden_fn`）。
    """
    root = _repo_root(root)
    ref, n_corpus = _build_reference_index(root, corpus_dirs)

    if benchmarks is None:
        if os.path.join(root, "lda") not in sys.path:
            sys.path.insert(0, os.path.join(root, "lda"))
        from lda_harness import benchmarks as _bm       # noqa: PLC0415
        # 🔴 传 `BENCHMARK_DEFS`（dict）而不是模块对象 —— 模块没有 `values()`，
        #    首版传模块导致 `anchor_entry_names = 0`（golden_fn 入口全丢，多判 5 个死）。
        benchmarks = _bm.BENCHMARK_DEFS
    entry_names, golden_names = anchor_entry_names(benchmarks)

    dead: List[Dict[str, str]] = []
    by_module: Dict[str, List[str]] = {}
    pub_total = 0
    reach_total = 0
    n_target = 0

    for p in _walk_py(root, target_dirs):
        tree = _parse_file(p)
        if tree is None:
            continue
        n_target += 1
        rel = os.path.relpath(p, root).replace("\\", "/")
        funcs = public_funcs(tree)
        if not funcs:
            continue
        pub_total += len(funcs)
        mod_ids = module_level_ids(tree)

        roots: Set[str] = set()
        for name in funcs:
            outside = ref.get(name, set()) - {rel}          # L1：跨模块
            if outside or name in entry_names or name in mod_ids:
                roots.add(name)                             # L1b / L2

        edges = {g: {t for t in ids_in(node) if t in funcs and t != g}
                 for g, node in funcs.items()}               # L3 边的原料

        reach: Set[str] = set(roots)
        stack = list(roots)
        while stack:
            cur = stack.pop()
            for nxt in edges.get(cur, ()):                   # L3 传递闭包
                if nxt not in reach:
                    reach.add(nxt)
                    stack.append(nxt)

        reach_total += len(reach)
        for name in sorted(set(funcs) - reach):
            dead.append({"module": rel, "name": name})
            by_module.setdefault(rel, []).append(name)

    dead.sort(key=lambda d: (d["module"], d["name"]))
    return {
        "dead": dead,
        "by_module": by_module,
        "stats": {
            "root": root,
            "target_files": n_target,
            "corpus_files": n_corpus,
            "public_total": pub_total,
            "reachable_total": reach_total,
            "dead_total": len(dead),
            "dead_pct": (100.0 * len(dead) / pub_total) if pub_total else 0.0,
            "anchor_entry_names": len(entry_names),
            "golden_fn_entries": len(golden_names),
        },
    }


def dead_key(entry: Dict[str, str]) -> str:
    """死函数的稳定键：`<module>::<name>`（登记表与门禁共用同一字符串格式）。"""
    return "%s::%s" % (entry["module"], entry["name"])


def dead_set(result: Dict[str, Any]) -> Set[str]:
    """分析结果的键集合。"""
    return {dead_key(d) for d in result["dead"]}


# ---------------------------------------------------------------------------
# 自检（分析器本身的可判别性 —— 不依赖真实仓库，用内存 AST 构造玩具样本）
# ---------------------------------------------------------------------------
def _toy_tree(src: str) -> ast.Module:
    return ast.parse(src)


def run_selfchecks(verbose: bool = True) -> bool:
    """四条自检，全部针对**分析器的判别力**（不是针对磁盘上的代码）。"""
    res: List[Tuple[str, bool, str]] = []

    def chk(name: str, cond: bool, detail: str = "") -> None:
        res.append((name, bool(cond), detail))

    # ① Attribute.attr 能抓到「不带括号的函数对象传递」（回调表）
    t1 = _toy_tree("def f(): pass\n"
                   "TABLE = [('G2', MOD.f, 8)]\n")
    chk("① 回调表里的 `MOD.f`（不带括号）能被 Attribute.attr 抓到",
        "f" in ids_in(t1))

    # ② module_level_ids 能抓到模块级 dict 的路由注册，且不把函数体内的算进去
    t2 = _toy_tree("def h_a(): pass\n"
                   "def h_b(): pass\n"
                   "ROUTES = {'/a': h_a}\n"
                   "def g():\n"
                   "    return h_b()\n")
    mod_ids = module_level_ids(t2)
    chk("② 模块级路由表 `{'/a': h_a}` 被算作入口，而函数体内的 h_b 不算",
        "h_a" in mod_ids and "h_b" not in mod_ids,
        "mod_ids=%s" % sorted(mod_ids))

    # ③ 传递闭包：f 被死的 g 调用 ⇒ f 仍死；f 被活的 h 调用 ⇒ f 活
    src = ("def f(): pass\n"
           "def g():\n"
           "    return f()\n"          # g 死 ⇒ f 仍死
           "def h():\n"
           "    return f()\n"
           "LIVE = {'h': h}\n")       # h 活 ⇒ f 应活
    tree = _toy_tree(src)
    funcs = public_funcs(tree)
    mod_ids = module_level_ids(tree)
    edges = {g: {t for t in ids_in(n) if t in funcs and t != g} for g, n in funcs.items()}
    roots = {n for n in funcs if n in mod_ids}
    reach, stack = set(roots), list(roots)
    while stack:
        cur = stack.pop()
        for nxt in edges.get(cur, ()):
            if nxt not in reach:
                reach.add(nxt); stack.append(nxt)
    chk("③ 传递闭包：f 被活的 h 调用 ⇒ f 可达；g 无人调用 ⇒ g 死",
        "f" in reach and "h" in reach and "g" not in reach,
        "reach=%s dead=%s" % (sorted(reach), sorted(set(funcs) - reach)))

    # ④ anchor_entry_names 能读到 golden_fn 的**函数对象**名
    class _FakeBench:
        @staticmethod
        def values():
            def golden_b0():
                return 0.0

            def cand_x():
                return 1.0
            return [{"golden_fn": golden_b0, "candidate": "cand_x",
                     "oracle": "analytical(x)", "metric": "m", "title": "t",
                     "candidate_desc": ""}]
    names, gold = anchor_entry_names(_FakeBench)
    chk("④ `golden_fn` 是函数对象（非字符串）也能被收作入口",
        "golden_b0" in names and "cand_x" in names and gold == {"golden_b0"},
        "golden_only=%s" % sorted(gold))

    ok = all(v for _, v, _ in res)
    if verbose:
        for n, v, dt in res:
            print(("  [PASS] " if v else "  [FAIL] ") + n + (("  |  " + dt) if dt else ""))
        print("\n可达性分析器自检：%d/%d %s"
              % (sum(1 for _, v, _ in res if v), len(res), "ALL PASS" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if run_selfchecks() else 1)
