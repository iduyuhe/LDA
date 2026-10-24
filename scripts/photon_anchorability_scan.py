# -*- coding: utf-8 -*-
"""光子域可锚性结构扫描（v0.9.281 · D-229 · M7 第一步 · **只读**）

回答一个问题：**光子侧（`lda_l2` 100 + `lda_agent` 53 模块）到底该不该照搬量子侧的
`ANCHORABLE` + `why_not_anchored()` 声明纪律？**

扫描先于改造。本脚本**不改任何文件**，只输出四张清单：

  A 有「数值闭式形态」但无 `ANCHORABLE` 声明
  B 无闭式形态（纯工程 / IO / 编排）
  C 有闭式形态但账本**零引用**
  D **成对实现**（同模块内闭式 + 独立数值两条实现）= 天然锚候选

🔴 **判据的诚实边界**（这是本脚本最重要的一段）：

  · A 的「闭式」是**形态判据**（顶层公开函数 ∧ 返回数值表达式 ∧ 无 IO 调用），
    **不等于**「可作 golden」。`lda_l2` 里绝大多数是**设计函数**（反解几何、扫描
    参数域），它们本来就不该出锚。把 A 当"待补声明名单"会制造 57 条合规装饰。
  · C ≡ A 是**结构必然**，不是巧合：账本 514 个 `golden_fn` **全部**在
    `lda_harness`，153 个能力模块**一个**都不被账本直接引用。所以"有闭式但零引用"
    与"有闭式"是同一个集合。
  · **D 才是可行动的**：同模块内同时存在闭式与独立数值实现，说明作者已经写好了
    golden 与 candidate 两半 —— 那是**真的锚候选**。D 的处置不是"补声明"，而是
    「必须有门禁真拿到该模块」（`run_reachability_smoke` 的 G11 已把它立成契约）。

用法（确定性输出，无时间戳、无随机、无 cwd 相对路径）：

    python scripts/photon_anchorability_scan.py            # 摘要 + 各清单前 20 条
    python scripts/photon_anchorability_scan.py --full     # 全部条目
    python scripts/photon_anchorability_scan.py --json     # 机器可读（stdout）
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "lda"))

PKGS = ("lda_l2", "lda_agent")

#: 视为"IO / 副作用"的调用名（出现即不算纯闭式）
_IO_CALLS = frozenset({
    "open", "read_text", "read_bytes", "write_text", "write_bytes",
    "system", "run", "Popen", "check_output", "urlopen", "connect",
    "mkdir", "makedirs", "dump", "load", "savefig", "glob", "listdir",
})
#: 视为"返回数值"的调用名（无 BinOp 时用它兜底）
_NUM_CALLS = frozenset({
    "sqrt", "exp", "log", "log10", "log2", "sin", "cos", "tan", "arcsin",
    "arccos", "arctan", "arctan2", "sinh", "cosh", "tanh", "abs", "pow",
    "real", "imag", "conj", "angle", "sum", "max", "min", "mean", "prod",
    "dot", "cross", "float", "complex", "array", "erf", "gamma", "ceil",
    "floor", "round", "hypot", "degrees", "radians", "log1p", "expm1",
})


def _call_name(node: ast.AST) -> str:
    """调用/属性的裸名（`a.b.c` → `c`）。"""
    f = getattr(node, "func", node)
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return ""


def _has_io(node: ast.AST) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and _call_name(n) in _IO_CALLS:
            return True
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            root = ((getattr(n, "module", "") or "").split(".")[0])
            if root in ("subprocess", "socket", "urllib", "requests", "shutil"):
                return True
    return False


def _returns_numeric(node: ast.AST) -> bool:
    for n in ast.walk(node):
        if not (isinstance(n, ast.Return) and n.value is not None):
            continue
        v = n.value
        if isinstance(v, (ast.BinOp, ast.UnaryOp)):
            return True
        if isinstance(v, (ast.Tuple, ast.List)):
            if any(isinstance(e, (ast.BinOp, ast.UnaryOp)) for e in v.elts):
                return True
        if isinstance(v, ast.Call) and _call_name(v) in _NUM_CALLS:
            return True
    return False


def _scan_module(path: str) -> dict:
    """单模块结构画像（解析失败如实标注，不跳过、不猜）。"""
    with open(path, encoding="utf-8", errors="replace") as fh:
        src = fh.read()
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return {"ok": False, "error": str(exc), "fns": [], "anchorable": None,
                "lines": len(src.split("\n"))}
    anchorable = None
    for n in tree.body:
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id == "ANCHORABLE":
                    anchorable = bool(getattr(n.value, "value", n.value))
    fns = []
    for n in tree.body:
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if n.name.startswith("_") or _has_io(n) or not _returns_numeric(n):
            continue
        fns.append(n.name)
    has_why = any(isinstance(n, ast.FunctionDef) and n.name == "why_not_anchored"
                  for n in tree.body)
    return {"ok": True, "fns": fns, "anchorable": anchorable,
            "why_not_anchored": has_why, "lines": len(src.split("\n"))}


def scan() -> dict:
    """现算四张清单（确定性：全部 sorted）。"""
    from lda_harness.benchmarks import BENCHMARK_DEFS as D
    from lda_harness import reachability_registry as REG

    # ① 锚层归属：账本 golden_fn 落在哪些模块
    golden_home = collections.defaultdict(set)
    for bid, v in D.items():
        fn = v.get("golden_fn")
        if fn is None:
            continue
        golden_home[getattr(fn, "__module__", "?")].add(bid)

    # ② 能力层画像
    rows = []
    for pkg in PKGS:
        d = os.path.join(_ROOT, "lda", pkg)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".py") or fn == "__init__.py" or fn.startswith("_"):
                continue
            rel = "lda/%s/%s" % (pkg, fn)
            modname = "%s.%s" % (pkg, fn[:-3])
            info = _scan_module(os.path.join(d, fn))
            info.update(mod=rel, modname=modname,
                        anchors=sorted(golden_home.get(modname, set())))
            rows.append(info)

    paired = REG.paired_implementation_modules()
    # 🔴 传 CI 清单：不传时契约只判"门禁存在且 import 了模块"，**不判这个门禁会不会真跑**。
    #    与门禁 G11 用同一口径，避免"工具报绿、门禁报红"的双口径。
    try:
        from run_ci_regression import CORE_SMOKES as _core
    except Exception:  # noqa: BLE001 —— 拿不到就如实标注，不假装已核
        _core = None
    contract = REG.paired_gate_contract(_core)

    list_a = sorted(r["mod"] for r in rows if r.get("ok") and r["fns"])
    list_b = sorted(r["mod"] for r in rows if r.get("ok") and not r["fns"])
    list_c = sorted(r["mod"] for r in rows if r.get("ok") and r["fns"]
                    and not r["anchors"])
    list_d = sorted(paired)

    declared = sorted(r["mod"] for r in rows if r.get("anchorable") is not None)
    referenced = sorted(r["mod"] for r in rows if r["anchors"])

    return {
        "schema": "lda-photon-anchorability-scan/1",
        "generated_by": "scripts/photon_anchorability_scan.py",
        "subject": ("光子域 `lda_l2` + `lda_agent` 的可锚性结构画像："
                    "能力模块是否被账本引用、是否声明 ANCHORABLE、是否有成对实现"),
        "excluded": ["时间戳", "git HEAD", "任何判决数值（本脚本不跑仿真）"],
        "summary": {
            "modules_scanned": len(rows),
            "modules_by_pkg": dict(collections.Counter(m.split("/")[1]
                                                       for m in (r["mod"] for r in rows))),
            "anchors_total": len(D),
            "golden_home_modules": len(golden_home),
            "golden_home_harness_modules": sum(1 for m in golden_home
                                               if "lda_harness" in m),
            "golden_home_elsewhere_modules": sorted(m for m in golden_home
                                                    if "lda_harness" not in m),
            "anchors_with_golden_fn": sum(len(v) for v in golden_home.values()),
            "anchors_without_golden_fn": len(D) - sum(len(v) for v in golden_home.values()),
            "capability_modules_referenced_by_ledger": len(referenced),
            "modules_with_anchorable_decl": len(declared),
            "A_closed_form_shaped": len(list_a),
            "B_engineering_only": len(list_b),
            "C_closed_but_zero_reference": len(list_c),
            "D_paired_implementation": len(list_d),
            "D_pairs_total": contract["n_pairs"],
            "D_gated": contract["n_gated"],
            "D_ungated": len(contract["ungated"]),
            "D_not_in_core": len(contract["not_in_core"]),
            "D_core_checked": contract["core_checked"],
            "D_override": contract["n_override"],
            "C_equals_A": list_c == list_a,
        },
        "golden_home": {m: sorted(v) for m, v in sorted(golden_home.items())},
        "lists": {"A": list_a, "B": list_b, "C": list_c, "D": list_d},
        "paired_detail": {m: {"pairs": [list(p) for p in v]}
                          for m, v in sorted(paired.items())},
        "paired_gate": contract["details"],
        "honest_note": (
            "A/C 是**形态判据**（顶层公开函数 ∧ 返回数值 ∧ 无 IO），**不等于可作 golden**："
            "`lda_l2` 多数是设计函数（反解几何、扫参数域），本就不该出锚；"
            "C ≡ A 是结构必然 —— 账本 514 个 golden_fn 全在 lda_harness，"
            "153 个能力模块无一被账本直接引用。"
            "**D 才是可行动清单**：成对实现 = golden 与 candidate 已写好，"
            "处置是『必须有门禁真拿到该模块』（G11 契约），不是『补 ANCHORABLE 声明』。"
        ),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="光子域可锚性结构扫描（只读）")
    ap.add_argument("--full", action="store_true", help="打印全部条目（默认各前 20）")
    ap.add_argument("--json", action="store_true", help="输出 JSON 到 stdout")
    args = ap.parse_args(argv)

    rep = scan()
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1, sort_keys=True))
        return 0

    s = rep["summary"]
    print("光子域可锚性结构扫描（v0.9.281 · D-229 · M7）")
    print("=" * 74)
    print("模块 %d（lda_l2 %d + lda_agent %d） · 账本锚 %d"
          % (s["modules_scanned"], s["modules_by_pkg"].get("lda_l2", 0),
             s["modules_by_pkg"].get("lda_agent", 0), s["anchors_total"]))
    print()
    print("锚层归属：%d 个模块承载 golden_fn（lda_harness %d 个 / 其他 %s）"
          % (s["golden_home_modules"], s["golden_home_harness_modules"],
             s["golden_home_elsewhere_modules"] or "无"))
    print("          %d / %d 道锚带 golden_fn（其余 %d 道无 golden_fn 对象）"
          % (s["anchors_with_golden_fn"], s["anchors_total"],
             s["anchors_without_golden_fn"]))
    print("能力层：账本直接引用的能力模块 **%d** 个 · 声明 ANCHORABLE 的 **%d** 个"
          % (s["capability_modules_referenced_by_ledger"],
             s["modules_with_anchorable_decl"]))
    print()
    print("A 有闭式形态但无声明            : %d" % s["A_closed_form_shaped"])
    print("B 无闭式形态（工程/IO/编排）    : %d" % s["B_engineering_only"])
    print("C 有闭式但账本零引用            : %d（C ≡ A ? %s）"
          % (s["C_closed_but_zero_reference"], s["C_equals_A"]))
    print("D **成对实现**（闭式+独立数值） : %d 模块 / %d 对 · 已配门禁 %d · 未配 %d"
          % (s["D_paired_implementation"], s["D_pairs_total"],
             s["D_gated"], s["D_ungated"]))
    print("          门禁在 CI core 里跑：%d/%d（不在 CI 的 %d 个 · 已核=%s）"
          % (s["D_paired_implementation"] - s["D_not_in_core"],
             s["D_paired_implementation"], s["D_not_in_core"], s["D_core_checked"]))
    print()
    print("[D] 成对实现明细（**唯一可行动清单**）")
    for m in rep["lists"]["D"]:
        pd = rep["paired_detail"][m]
        gt = rep["paired_gate"][m]
        print("  %-38s %d 对  gate=%-32s imports=%-5s in_core=%s"
              % (m, len(pd["pairs"]), gt["gate"], gt["gate_imports"],
                 gt.get("gate_in_core")))
    lim = None if args.full else 20
    for key, title in (("A", "A 有闭式形态（**不是**待补声明名单）"),
                       ("B", "B 无闭式形态"), ("C", "C 有闭式但零引用")):
        items = rep["lists"][key]
        print()
        print("[%s] %s —— %d 条%s"
              % (key, title, len(items), "" if lim is None or len(items) <= lim
                 else "（下列前 %d）" % lim))
        for m in (items if lim is None else items[:lim]):
            print("  " + m)
    print()
    print("判据边界：" + rep["honest_note"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
