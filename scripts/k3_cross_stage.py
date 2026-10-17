# -*- coding: utf-8 -*-
"""K3 · 量子赛道跨档复用常量表（机器生成 · **禁手写**）。

扫描 `lda_l2` + `lda_qeda` 的量子赛道模块集合（J1–J5 / QS-M* / SC / LOQC / 预算层），
用 AST 静态提取全部跨模块 import 站点，并对每个站点快照其**接口指纹**：

  · const    → 现算取值（`getattr`），上游改常量即漂移
  · function → `inspect.signature` 签名快照（含默认值 ⇒ 上游改接口即漂移）
  · class    → 构造签名快照
  · module   → 整包复用（只记关系）

确定性：零时间戳 / 零随机 / 零 git HEAD；键序固定；写盘走 `det.write_text`（UTF-8 + LF）。

用法：
    python scripts/k3_cross_stage.py            # 打印台账正文（供门禁逐字节对拍）
    python scripts/k3_cross_stage.py --write    # 写回 lda/reports/cross_stage_constants.json
"""
from __future__ import annotations

import argparse
import ast
import inspect
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LDA = os.path.join(_REPO, "lda")
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

from lda_harness import deterministic as det  # noqa: E402  （⑧b：确定性唯一口径）

SCHEMA = "lda_cross_stage_constants_v1"
OUT_REL = "lda/reports/cross_stage_constants.json"

# ── 量子赛道模块集合（本表扫描域） ────────────────────────────────────
L2_MODULES = (
    "qs_m0", "qs_m1", "qs_m2", "qs_m3", "qs_m3b", "qs_m3c", "qs_m4",
    "qs_m5", "qs_m6", "qs_m7", "qs_m9",
    "qs_j4_integration", "qs_j4_microcell", "qs_j4_multiparam",
    "qs_j4_packaging", "qs_j4_system",
    "qnet_channel", "qnet_distribution", "qnet_source", "qnet_repeater",
    "qnet_transducer", "qnet_classical", "qnet_system",
)
QEDA_MODULES = (
    "qec_noise", "fault_tolerant_gates", "logical_error_rate", "decoder",
    "qubit_dynamics", "cross_resonance", "control_closed_loop",
    "cryo_electronics", "j2_readout_mux", "j2_to_j1_calibration",
    "physical_error_model", "qpu_error_budget", "rb_benchmark",
    "readout_demod", "sc_array", "sc_control", "sc_coupler",
    "loqc_states", "photon_sources", "detectors", "gates", "pulse_library",
)

# ── 档位映射（模块 → 蓝图档位） ───────────────────────────────────────
STAGE = {
    "qs_m0": "QS-M0", "qs_m1": "QS-M1", "qs_m2": "QS-M2", "qs_m3": "QS-M3",
    "qs_m3b": "QS-M3b", "qs_m3c": "QS-M3c", "qs_m4": "QS-M4",
    "qs_m5": "QS-M5", "qs_m6": "QS-M6", "qs_m7": "QS-M7", "qs_m9": "QS-M9",
    "qs_j4_integration": "J4", "qs_j4_microcell": "J4",
    "qs_j4_multiparam": "J4", "qs_j4_packaging": "J4", "qs_j4_system": "J4",
    "qnet_channel": "J5", "qnet_distribution": "J5", "qnet_source": "J5",
    "qnet_repeater": "J5", "qnet_transducer": "J5", "qnet_classical": "J5",
    "qnet_system": "J5",
    "qec_noise": "J1", "fault_tolerant_gates": "J1",
    "logical_error_rate": "J1", "decoder": "J1",
    "qubit_dynamics": "J2", "cross_resonance": "J2",
    "pulse_library": "J2", "gates": "J2",
    "cryo_electronics": "J3", "control_closed_loop": "J3",
    "rb_benchmark": "J3", "readout_demod": "J3", "j2_readout_mux": "J3",
    "j2_to_j1_calibration": "J2→J1",
    "sc_array": "SC", "sc_control": "SC", "sc_coupler": "SC",
    "loqc_states": "LOQC", "photon_sources": "LOQC", "detectors": "LOQC",
    "physical_error_model": "BUDGET", "qpu_error_budget": "BUDGET",
}

PKG_DIR = {"lda_l2": os.path.join(_LDA, "lda_l2"),
           "lda_qeda": os.path.join(_LDA, "lda_qeda")}
ALL_MODULES = {"lda_l2": L2_MODULES, "lda_qeda": QEDA_MODULES}


def _rel(path: str) -> str:
    """仓库相对 POSIX 路径。"""
    return os.path.relpath(path, _REPO).replace(os.sep, "/")


def _trees():
    """(pkg, module) -> (tree, relpath)。"""
    out = {}
    for pkg, names in ALL_MODULES.items():
        for m in names:
            path = os.path.join(PKG_DIR[pkg], m + ".py")
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as f:
                src = f.read()
            out[(pkg, m)] = (ast.parse(src), _rel(path))
    return out


def _kinds(tree):
    """模块顶层符号类型表：name -> const|function|class。"""
    k = {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            k[n.name] = "function"
        elif isinstance(n, ast.ClassDef):
            k[n.name] = "class"
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    k[t.id] = "const"
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            k[n.target.id] = "const"
    return k


def _holder(tree, lineno):
    funcs = {n.name: (n.lineno, n.end_lineno) for n in ast.walk(tree)
             if isinstance(n, ast.FunctionDef)}
    for fn, (a, b) in funcs.items():
        if a <= lineno <= b:
            return fn
    return "<module>"


def _scan():
    trees = _trees()
    kinds = {kk: _kinds(t) for kk, (t, _p) in trees.items()}
    sites = []
    for (pkg, me), (tree, rel) in sorted(trees.items()):
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            base = node.module.split(".")
            if base[0] not in ("lda_l2", "lda_qeda"):
                continue
            sp = base[0]
            if len(base) == 1:
                # from lda_l2 import qs_m2  → 整包
                for a in node.names:
                    if a.name not in STAGE or (sp == pkg and a.name == me):
                        continue
                    sites.append(dict(
                        consumer_pkg=pkg, consumer_module=me,
                        consumer_symbol="<module>", consumer_file=rel,
                        consumer_line=node.lineno,
                        holder=_holder(tree, node.lineno),
                        source_pkg=sp, source_module=a.name,
                        symbol="<module>", kind="module"))
                continue
            sm = base[1]
            if sm not in STAGE or (sp == pkg and sm == me):
                continue
            for a in node.names:
                k = kinds.get((sp, sm), {}).get(a.name, "unknown")
                sites.append(dict(
                    consumer_pkg=pkg, consumer_module=me,
                    consumer_symbol=a.asname or a.name, consumer_file=rel,
                    consumer_line=node.lineno,
                    holder=_holder(tree, node.lineno),
                    source_pkg=sp, source_module=sm,
                    symbol=a.name, kind=k))
    # 稳定排序（不受 ast.walk 顺序影响）
    sites.sort(key=lambda s: (s["consumer_pkg"], s["consumer_module"],
                              s["consumer_line"], s["symbol"]))
    return sites, len(trees)


def _fingerprint(pkg, module, symbol, kind):
    """接口指纹：const 取值 · function/class 签名。取不到则记 error（不静默）。"""
    if kind == "module":
        return {}
    try:
        mod = __import__("%s.%s" % (pkg, module), fromlist=[symbol])
        obj = getattr(mod, symbol)
    except Exception as e:  # noqa: BLE001
        return {"fingerprint_error": "%s: %s" % (type(e).__name__, str(e)[:120])}
    if kind == "const":
        if isinstance(obj, bool):
            return {"value": obj, "value_type": "bool"}
        if isinstance(obj, (int, float)):
            return {"value": obj, "value_type": type(obj).__name__}
        if isinstance(obj, str):
            return {"value": obj, "value_type": "str"}
        return {"value_repr": repr(obj)[:200], "value_type": type(obj).__name__}
    try:
        sig = str(inspect.signature(obj))
    except Exception as e:  # noqa: BLE001
        return {"fingerprint_error": "%s: %s" % (type(e).__name__, str(e)[:120])}
    return {"signature": sig}


def build():
    sites, n_mod = _scan()
    for s in sites:
        s["stage_from"] = STAGE[s["source_module"]]
        s["stage_to"] = STAGE[s["consumer_module"]]
        s["cross_stage"] = s["stage_from"] != s["stage_to"]
        s.update(_fingerprint(s["source_pkg"], s["source_module"],
                              s["symbol"], s["kind"]))
    by_kind = {}
    for s in sites:
        by_kind[s["kind"]] = by_kind.get(s["kind"], 0) + 1
    cross = sum(1 for s in sites if s["cross_stage"])
    payload = {
        "schema": SCHEMA,
        "generated_by": "scripts/k3_cross_stage.py",
        "roadmap": "K（量子赛道一期结算与固化）",
        "subject": "量子赛道 J1–J5 / QS-M* 跨模块复用常量与接口签名",
        "method": ("AST 静态扫描 lda_l2 + lda_qeda 量子赛道模块集合"
                   "（%d 模块）→ 每站点快照 const 值 / function 签名" % n_mod),
        "excluded_fields": ["时间戳（非确定量）", "git HEAD（每次提交都变）"],
        "stage_map": {m: STAGE[m] for m in sorted(STAGE)},
        "summary": {
            "modules_scanned": n_mod,
            "sites_total": len(sites),
            "sites_cross_stage": cross,
            "sites_same_stage": len(sites) - cross,
            "by_kind": {k: by_kind[k] for k in sorted(by_kind)},
        },
        "sites": sites,
    }
    return payload


def render(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="K3 跨档复用常量表生成器")
    ap.add_argument("--write", action="store_true", help="写回受跟踪台账")
    args = ap.parse_args(argv)

    payload = build()
    text = render(payload)
    if args.write:
        det.write_text(os.path.join(_REPO, OUT_REL), text)
        print("[written] %s（%d 站点 · 跨档 %d）"
              % (OUT_REL, payload["summary"]["sites_total"],
                 payload["summary"]["sites_cross_stage"]))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
