#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ecore 能力审计 —— 把评估报告里引用的每个数字变成**可复现的一条命令**。

用法::

    PYTHONPATH=lda python scripts/ecore_capability_audit.py              # 全部
    PYTHONPATH=lda python scripts/ecore_capability_audit.py --only E07   # 单项
    PYTHONPATH=lda python scripts/ecore_capability_audit.py --list       # 列证据项

设计约束：
  · 本脚本**只做度量与观测**，不含判据、不含阈值、不给结论 ⇒ 可以长期留在仓库里。
  · 每个证据项的输出都必须**确定性**（同一 commit 跑两次 JSON 相同，`elapsed` 类字段不输出）。
  · 不改任何产品模块的运行时状态（唯一例外：E05/E06 会真跑流程，属只读计算）。
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ECORE = os.path.join(ROOT, "lda", "lda_l2", "ecore")
sys.path.insert(0, os.path.join(ROOT, "lda"))

ENTRIES = ("db3_trunk", "soc_flow", "dmacro")
REGISTRY: dict = {}


def evidence(eid: str, title: str):
    def deco(fn):
        REGISTRY[eid] = (title, fn)
        return fn
    return deco


# ── E01 规模 ────────────────────────────────────────────────────────────────
@evidence("E01", "模块/行/公开函数/smoke 计数")
def e01():
    mods = sorted(f[:-3] for f in os.listdir(ECORE)
                  if f.endswith(".py") and f != "__init__.py")
    lines = api = 0
    for m in mods:
        src = open(os.path.join(ECORE, m + ".py"), encoding="utf-8").read()
        lines += src.count("\n") + 1
        tree = ast.parse(src)
        api += sum(1 for n in tree.body
                   if isinstance(n, ast.FunctionDef) and not n.name.startswith("_"))
    smokes = [f for f in os.listdir(os.path.join(ROOT, "lda"))
              if re.match(r"run_.*_smoke\.py$", f)]
    return {"modules": len(mods), "lines": lines, "public_funcs": api,
            "smoke_scripts": len(smokes)}


# ── E02 依赖图 + 入口可达性 ─────────────────────────────────────────────────
def _deps_of(name: str, mods: set) -> set:
    tree = ast.parse(open(os.path.join(ECORE, name + ".py"), encoding="utf-8").read())
    out = set()
    for n in ast.walk(tree):
        if not isinstance(n, ast.ImportFrom):
            continue
        if n.module and n.module.split(".")[-1] == "ecore":
            for a in n.names:
                if a.name in mods:
                    out.add(a.name)
        if n.module and n.module.split(".")[-1] in mods:
            out.add(n.module.split(".")[-1])
        if n.level >= 1:
            for a in n.names:
                if a.name in mods:
                    out.add(a.name)
    out.discard(name)
    return out


@evidence("E02", "模块级依赖图与端到端入口可达性")
def e02():
    mods = {f[:-3] for f in os.listdir(ECORE)
            if f.endswith(".py") and f != "__init__.py"}
    graph = {m: sorted(_deps_of(m, mods)) for m in mods}
    indeg = {m: 0 for m in mods}
    for ds in graph.values():
        for d in ds:
            indeg[d] = indeg.get(d, 0) + 1
    seen, stack = set(), list(ENTRIES)
    while stack:
        cur = stack.pop()
        for nxt in graph.get(cur, ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    unreach = sorted(mods - seen - set(ENTRIES))
    return {"entries": list(ENTRIES), "n_modules": len(mods),
            "reachable": sorted(seen), "n_reachable": len(seen),
            "n_unreachable": len(unreach),
            "unreachable": unreach,
            "zero_indegree_unreachable": sorted(m for m in unreach if indeg[m] == 0),
            "graph": graph, "indegree": indeg}


# ── E03 链外模块的 smoke 覆盖 ───────────────────────────────────────────────
@evidence("E03", "链外模块是否被 smoke 覆盖（区分研究资产与死代码）")
def e03():
    d = e02()
    blob = ""
    for f in os.listdir(os.path.join(ROOT, "lda")):
        if re.match(r"run_.*_smoke\.py$", f):
            blob += open(os.path.join(ROOT, "lda", f),
                         encoding="utf-8", errors="replace").read()
    covered, uncovered = [], []
    for m in d["unreachable"]:
        (covered if re.search(r"\b%s\b" % re.escape(m), blob) else uncovered).append(m)
    return {"n_unreachable": len(d["unreachable"]),
            "n_covered": len(covered), "covered": covered,
            "uncovered": uncovered}


# ── E04 数字线端到端 ────────────────────────────────────────────────────────
@evidence("E04", "数字线端到端实测（run_trunk_from_verilog）")
def e04():
    from lda_l2.ecore import db3_trunk as B3
    from lda_l2.ecore import dverilog as V
    r = B3.run_trunk_from_verilog(V.SAMPLE_VERILOG)
    stages = [s[0] if isinstance(s, tuple) else s for s in r["stages"]]
    cl = r["claimability"]
    defw = next((s[1] for s in r["stages"]
                 if isinstance(s, tuple) and s[0] == "def_write"), {})
    return {"stages": stages, "n_stages": len(stages),
            "conservation_ok": r["conservation_ok"],
            "def_bytes": defw.get("bytes"),
            "claimable": cl["claimable"],
            "conditions": cl["conditions"],
            "blocking": cl["blocking"],
            "area_delta": r["area_delta"]}


# ── E05 模拟线端到端 ────────────────────────────────────────────────────────
@evidence("E05", "模拟/存算线端到端实测（run_flow 8 步）")
def e05():
    from lda_l2.ecore import soc_flow as SF
    r = SF.run_flow()
    out = {"self_check": SF.soc_flow_self_check(), "stages": []}
    for s in r["stages"]:
        body = s[1] if isinstance(s, tuple) else s
        m = body.get("metrics", {})
        out["stages"].append({
            "stage": body.get("stage"), "ok": body.get("ok"),
            "n_bytes": m.get("n_bytes"), "n_elements": m.get("n_elements"),
            "n_violations": m.get("n_violations"), "n_issues": m.get("n_issues"),
            "verdict": m.get("verdict"), "n": m.get("n")})
    return out


# ── E06 合流点 IP GDS ───────────────────────────────────────────────────────
@evidence("E06", "合流点 dmacro.build_ip（阵列 + 数字壳）")
def e06():
    from lda_l2.ecore import dmacro as DM
    from lda_l2.ecore import dverilog as V
    m = DM.build_ip(V.parse(V.SAMPLE_VERILOG))
    return {"gds_bytes": len(m.gds_bytes), "n_emitted": m.n_emitted,
            "n_parsed": m.n_parsed, "conservation_ok": m.n_emitted == m.n_parsed,
            "array_only_bytes": getattr(m, "array_only_bytes", None),
            "n_digital_cells": getattr(m, "n_digital_cells", None),
            "n_route_shapes": getattr(m, "n_route_shapes", None),
            "n_cell_shapes": getattr(m, "n_cell_shapes", None),
            "drc_violations": getattr(m, "drc_violations", None),
            "lvs_problems": getattr(m, "lvs_problems", None)}


# ── E07 面积三套口径 ────────────────────────────────────────────────────────
@evidence("E07", "面积三套口径与倍差")
def e07():
    from lda_l2.ecore import dcell as DC
    from lda_l2.ecore import dcells as CL
    sym = {"INV": 2 * DC.DEFAULT_TECH.area_per_tr_um2,
           "NAND2": 4 * DC.DEFAULT_TECH.area_per_tr_um2}
    geo = {"INV": CL.build_inv().area_um2, "NAND2": CL.build_nand2().area_um2}
    ref = {"INV": 2 * 0.266, "NAND2": 4 * 0.266}
    return {"symbolic": sym, "geometric": geo, "nangate_ref": ref,
            "ratio_geo_over_sym": {k: geo[k] / sym[k] for k in geo},
            "ratio_geo_over_ref": {k: geo[k] / ref[k] for k in geo},
            #: v0.9.409：`cell_area_um2` 已按「有版图走几何」分流，`basis` 让消费者无法误用
            "tech_cell_area_um2": {k: DC.cell_area_um2(k) for k in geo},
            "basis": {k: DC.area_basis(k) for k in sorted(DC.CELLS)},
            "n_layout_basis": sum(1 for k in DC.CELLS if DC.area_basis(k) == DC.AREA_BASIS_LAYOUT),
            "n_symbolic_basis": sum(1 for k in DC.CELLS if DC.area_basis(k) == DC.AREA_BASIS_SYMBOLIC)}


# ── E08 ileak 消费 ──────────────────────────────────────────────────────────
@evidence("E08", "ileak_na_per_tr 的消费路径")
def e08():
    hits = []
    for base in (os.path.join(ROOT, "lda"), os.path.join(ROOT, "scripts")):
        for dirpath, _dirs, files in os.walk(base):
            if "__pycache__" in dirpath:
                continue
            for f in files:
                if not f.endswith(".py"):
                    continue
                p = os.path.join(dirpath, f)
                try:
                    src = open(p, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                if "ileak_na_per_tr" in src:
                    hits.append(os.path.relpath(p, ROOT).replace("\\", "/"))
    # 按**位置性质**分类，不硬编码具体文件名（否则「靠名字判结构」的老毛病会重演）
    def kind(rel):
        if rel.startswith("scripts/"):
            return "audit"
        if os.path.basename(rel).startswith("run_") and rel.endswith("_smoke.py"):
            return "guard"
        if "/ecore/" in rel:
            return "definition_or_consumer"
        return "other"
    by_kind = {}
    for h in hits:
        by_kind.setdefault(kind(h), []).append(h)
    return {"files_mentioning": sorted(hits), "n": len(hits),
            "by_kind": {k: sorted(v) for k, v in by_kind.items()},
            #: 「产品链消费者」= 除定义处/判据/审计之外，还提到该参数的文件数。
            #: 该数为 0 即「参数有定义、无消费」⇒ 静默能力缺口。
            "n_non_definition_consumers": len(by_kind.get("definition_or_consumer", [])) - 1
            if "definition_or_consumer" in by_kind else 0}


# ── E09 单元库物理面 ────────────────────────────────────────────────────────
@evidence("E09", "单元库：逻辑 18 / 版图 3 / 物理链原语")
def e09():
    from lda_l2.ecore import dcell as DC
    from lda_l2.ecore import dcells as CL
    from lda_l2.ecore import dverilog as DV
    return {"n_logical_cells": len(DC.CELLS),
            "n_layout_cells": len([c for c in DC.CELLS.values() if c.layout]),
            "layout_names": sorted(c.layout for c in DC.CELLS.values() if c.layout),
            "dcells_keys": sorted(CL.CELLS),
            "physically_modeled": sorted(DV.PHYSICALLY_MODELED),
            "wl_by_src": DC.wl_provenance_summary()["by_src"]}


# ── E10 控制壳规模 ──────────────────────────────────────────────────────────
@evidence("E10", "控制壳网表规模（真实目标）")
def e10():
    from collections import Counter
    from lda_l2.ecore import dctrl as CT
    nl = CT.build()["netlist"]
    c = Counter(g.cell for g in nl.gates)
    return {"n_gates": len(nl.gates), "by_cell": dict(sorted(c.items())),
            "vs_c17": round(len(nl.gates) / 17.0, 1)}


# ── E11 数字链第三方依赖 ────────────────────────────────────────────────────
@evidence("E11", "数字链是否零第三方依赖（自主可控）")
def e11():
    core = ("drtl dsynth dplac dpnr dsta ddrc_lvs ddetail dextract ddef dlef "
            "dmacro dcell dcells dsignoff dpathfinder dinrow dctrl dverilog").split()
    bad, third = [], set()
    for m in core:
        p = os.path.join(ECORE, m + ".py")
        if not os.path.exists(p):
            continue
        tree = ast.parse(open(p, encoding="utf-8").read())
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    top = a.name.split(".")[0]
                    if top not in sys.stdlib_module_names and top != "lda_l2":
                        bad.append("%s:import %s" % (m, top))
                        third.add(top)
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                top = n.module.split(".")[0]
                if top not in sys.stdlib_module_names and top != "lda_l2":
                    bad.append("%s:from %s" % (m, top))
                    third.add(top)
    return {"modules_checked": len(core), "third_party": sorted(third),
            "violations": bad, "clean": not bad}


# ── E12 主链敏感量（改版必查）────────────────────────────────────────────
@evidence("E12", "布局预算：行高/单元宽/节距/pitch_x")
def e12():
    from lda_l2.ecore import dcells as CL
    from lda_l2.ecore import dpnr as PN
    return {"row_height_um": PN.row_height_um(),
            "cell_w_um": PN.CELL_W_UM,
            "cell_gap_um": PN.CELL_GAP_UM,
            "pitch": PN.PITCH,
            "per_cell_w": {k: f().w for k, f in CL.CELLS.items()},
            "per_cell_h": {k: f().h for k, f in CL.CELLS.items()}}


# ── E13 判据规模 ────────────────────────────────────────────────────────────
@evidence("E13", "s13 判据数（AST 数 check() 调用）")
def e13():
    p = os.path.join(ROOT, "lda", "run_ecore_s13_smoke.py")
    tree = ast.parse(open(p, encoding="utf-8").read())
    n = sum(1 for x in ast.walk(tree)
            if isinstance(x, ast.Call) and isinstance(x.func, ast.Name)
            and x.func.id == "check")
    return {"s13_check_calls": n}


# ── E14 c432 规模真值（F1 · 三口径分解 × 双口径布通率）────────────────────
@evidence("E14", "c432 规模真值：三口径门数 + 双口径布通率与三段归因")
def e14():
    """只度量两种**不同定义**的布通率，不做阶段决策。

    · `main` = 交付链口径：`build_ports + route_block(ports=)`，
      分母 `coverage.total`（全部网，含 primary I/O），DEMO45 单元库；
    · `e53_style` = E53 实验口径：`HD` 库 + `in_row_m3`、无 pad 建模，
      分母 `len(routed)+len(unrouted)`（仅内部网），`cols=8`。
    🔴 两者分母/库/配置都不同，**禁止互引或混称「布通率」**。
    """
    from lda_l2.ecore import dbench as B
    from lda_l2.ecore import ddrc_lvs as DL
    from lda_l2.ecore import dhdlib as HD
    from lda_l2.ecore import dpnr as PN
    from lda_l2.ecore import dproc as PR

    spec = B.parse_bench(B.load_corpus("c432"))
    out = {"corpus": "c432", "sha256": B.BENCH_SOURCE["c432"]["sha256"],
           "n_inputs": len(spec["inputs"]), "n_outputs": len(spec["outputs"]),
           "n_source_gates": len(spec["gates"]),
           "fanin_hist": B.decompose_report(spec, "A")["fanin_hist"],
           "definitions": {
               "main": "build_ports + route_block(ports=) · coverage.total · DEMO45",
               "e53_style": "PR.use(DEMO28,lib=HD) + in_row_m3 · routed+unrouted · cols=8",
               "note": "两口径分母/库/配置不同，不可互引；阶段决策不在本脚本判定"},
           "modes": {}}
    for mode in B.DECOMP_MODES:
        gates = B.decompose(spec, mode)
        nl = B.to_netlist(spec, gates, name="c432_%s" % mode)
        n = len(nl.gates)
        pl = PN.place_real(nl, max_cells=n)
        ports = PN.build_ports(nl, pl)
        rt = PN.route_block(nl, ports["pl"], ports=ports)
        cov = rt["coverage"]
        drc_main = len(DL.run_drc(PN.all_routing(rt))["violations"])
        with PR.use("DEMO28", lib=HD):
            pl2 = PN.place_real(nl, max_cells=n, cols=8)
            rt2 = PN.route_block(nl, pl2, in_row_m3=True)
            drc_e53 = len(DL.run_drc(PN.all_routing(rt2))["violations"])
        n_int = len(rt2["routed"]) + len(rt2["unrouted"])
        out["modes"][mode] = {
            "n_decomposed_gates": n,
            "cell_hist": B.decompose_report(spec, mode)["cell_hist"],
            "main": {"routed": cov["routed"], "total": cov["total"],
                     "failed": cov["failed"], "complete": cov["complete"],
                     "coverage_matches_independent": cov == PN.net_coverage(rt),
                     "n_col_fail_no_column": rt["n_col_fail_no_column"],
                     "n_col_fail_too_far": rt["n_col_fail_too_far"],
                     "n_in_row_m3_fail": len(rt["in_row_m3_fail"]),
                     "n_skipped_true_port": cov["skipped_true_port"],
                     "drc_violations": drc_main,
                     "rows": pl["rows"], "cols": pl["cols"]},
            "e53_style": {"routed": len(rt2["routed"]), "n_int": n_int,
                          "n_in_row_m3": rt2["n_in_row_m3"],
                          "n_col_fail_no_column": rt2["n_col_fail_no_column"],
                          "drc_violations": drc_e53,
                          "rows": pl2["rows"], "cols": pl2["cols"]},
        }
    return out


# ── E15 时序引脚进图（F2 第二批 · 只度量，不做阶段决策）──────────────────
@evidence("E15", "时序引脚进图：默认口径零漂移 + 完整映射下 D/CLK/Q/QN 的归宿")
def e15():
    """只度量两件事，不含阈值、不放行任何阶段结论。

    · `default_drift`：默认库口径下 `net_pins` 是否与 v0.9.411 逐位相同；
    · `full_map`：显式完整映射下时序引脚是否全部有归宿（端点 or 显式 NC）。
    🔴 诚实边界：QN 在网表无对应网 ⇒ 显式 NC；CLK 是 56 端点单网，
    其布通能力属 F3 CTS，本项**不做判定**，也不宣称「DFF 已能布通」。
    """
    import collections as _c
    from lda_l2.ecore import dctrl as CT
    from lda_l2.ecore import dhdlib as HD
    from lda_l2.ecore import dpnr as PN
    from lda_l2.ecore import dproc as PR

    def old_net_pins(pl, ports=None, with_nc=False):
        pins = _c.defaultdict(list)
        for inst in pl["insts"]:
            g = inst["gate"]
            names = ["A", "B"] if "B" in inst["geom"].pins else ["A"]
            idx = {n: k for k, n in enumerate(names)}
            for p in PN.pin_access_points(inst):
                if p["pin"] == "Y":
                    pins[g.out].append((inst["name"], "Y", p["x"], p["y"]))
                elif p["pin"] in idx:
                    k = idx[p["pin"]]
                    if k < len(g.ins):
                        pins[g.ins[k]].append((inst["name"], p["pin"], p["x"], p["y"]))
        if ports:
            for net, meta in (ports.get("pads") or {}).items():
                pins[net].append((meta["name"], "P", meta["x"], meta["y"]))
        if with_nc:
            return dict(pins), []
        return dict(pins)

    def sig(d):
        return {k: sorted(v) for k, v in d.items()}

    nl = CT.build()["netlist"]
    drift = {}
    for n in (64, 256):
        with PR.use("DEMO28", lib=HD):
            pl = PN.place_real(nl, max_cells=n, cols=8, truncate_ok=True)
        new = PN.net_pins(pl)
        drift["default_%d" % n] = {
            "n_insts": pl["n_picked"],
            "n_endpoints": sum(len(v) for v in new.values()),
            "identical_to_v0411": sig(old_net_pins(pl)) == sig(new),
        }
    with PR.use("DEMO28", lib=HD, cell_map=HD.CELL_MAP_FULL):
        pl2 = PN.place_real(nl, max_cells=2000)
    pins, nc = PN.net_pins(pl2, with_nc=True)
    dff = [i for i in pl2["insts"] if i["cell"] == "DFF"]
    have = {(e[0], e[1]) for v in pins.values() for e in v}
    all_pins = {(i["name"], p["pin"]) for i in pl2["insts"]
                for p in PN.pin_access_points(i)}
    return {
        "pin_role": {k: list(v) for k, v in sorted(PN.PIN_ROLE.items())},
        "default_drift": drift,
        "full_map": {
            "n_picked": pl2["n_picked"], "n_dff": len(dff),
            "n_endpoints": sum(len(v) for v in pins.values()),
            "n_nc": len(nc), "nc_pin_names": sorted({p for _n, p in nc}),
            "d_clk_q_endpoints": {p: sum(1 for i in dff if (i["name"], p) in have)
                                  for p in ("D", "CLK", "Q")},
            "n_signal_pins": len(all_pins),
            "all_pins_accounted": (have | set(nc)) == all_pins,
            "clk_net_endpoints": len(pins.get("CLK", [])),
        },
        "boundary": "QN 无网 ⇒ 显式 NC；CLK 56 端点高扇出网布通归 F3；本项不判定阶段",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="只跑某一项，如 E07")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dump", default=None, help="把 JSON 写到文件")
    a = ap.parse_args()
    if a.list:
        for k in sorted(REGISTRY):
            print("%s  %s" % (k, REGISTRY[k][0]))
        return 0
    ids = [a.only] if a.only else sorted(REGISTRY)
    out = {}
    for eid in ids:
        if eid not in REGISTRY:
            print("未知证据项 %s（用 --list 查看）" % eid, file=sys.stderr)
            return 2
        title, fn = REGISTRY[eid]
        try:
            out[eid] = {"title": title, "ok": True, "value": fn()}
        except Exception as exc:                              # noqa: BLE001
            out[eid] = {"title": title, "ok": False,
                        "error": "%s: %s" % (type(exc).__name__, str(exc)[:200])}
        print("[%s] %s %s" % ("OK  " if out[eid]["ok"] else "FAIL", eid, title))
    if a.dump:
        with open(a.dump, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2, sort_keys=True)
        print("\n写出 %s（%d 项）" % (a.dump, len(out)))
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if all(v["ok"] for v in out.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
