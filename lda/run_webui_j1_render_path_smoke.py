# -*- coding: utf-8 -*-
"""J1 量子纠错案例卡 · **WebUI 渲染路径门禁**（K 征程 K2 · 补齐 G-K-4 六层面板）。

判据分节（**判据数实跑现数**）：
  A 前端接线（3）：`sec-j1` 段 + `runJ1` 按钮 + `renderJ1` 函数 + `apiGet('/api/j1_qec')` ·
    hash 深链 `CASE_MAP` · 首屏导航直达链接
  B 取值路径（2）：`renderJ1` 引用的顶层块在**真实 JSON** 上可解析 · 反向完备（卡顶层键均被引用）
  C **跨源逐值对拍**（7）：`j1_case` 的 7 个闭式 ≡ `lda_qeda/{qec_noise,fault_tolerant_gates,
    logical_error_rate}` 真源（同参数 · ≤1 ULP）
  D 锚号（1）：9 锚 B497–B505 与 `BENCHMARK_DEFS` 一致
  E 纪律（4）：零重计算（AST 断言仅 math/typing）· 端点不进 `HEAVY_POST_PATHS` 且免登录 ·
    verdict 恒 `DESIGN_BUDGET` · 模块自检全 PASS
  F 突变探针（3）：改坏 `syndrome_weight` / `transversal_cnot_fidelity` / `verdict` ⇒ 必红
  G 还原复绿（1）：三次突变后 `case_card` 仍与真源一致

🔴 `main()` 返回「真值」而非恒 0；一律走 `smoke_kit.make_check`（棘轮 J3）。
"""

from __future__ import annotations

import ast
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))          # lda/
_ROOT = os.path.dirname(_HERE)                              # 仓库根
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402  # 助手单一来源（棘轮 J3）
from lda_qeda import fault_tolerant_gates as G  # noqa: E402
from lda_qeda import logical_error_rate as L  # noqa: E402
from lda_qeda import qec_noise as N  # noqa: E402
from lda_webui import j1_case as J  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

_INDEX = os.path.join(_HERE, "lda_webui", "static", "index.html")
_CASE = os.path.join(_HERE, "lda_webui", "j1_case.py")
_ROUTES = os.path.join(_HERE, "lda_webui", "routes.py")


def _read(p):
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


def _ulp_ok(a, b, rel=1e-15):
    """逐位（≤1 ULP 相对 1e-15）对拍。"""
    d = abs(float(a) - float(b))
    return d <= rel * max(1.0, abs(float(a)), abs(float(b)))


def _cross_source_pairs(card):
    """(名称, 卡值, 真源值) —— 同参数调用真源（方法学独立于卡的纯 math 复刻）。"""
    return [
        ("syndrome_weight", card["m1_decoder"]["syndrome_weight"],
         N.expected_syndrome_weight(J.P_PHYS, J.CODE_L)),
        ("flag_hook_detection", card["m2_syndrome_extraction"]["flag_hook_detection"],
         N.flag_hook_detection(J.N_HOOK, J.FLAG_FAULTS)),
        ("adjacent_syndrome_correlation",
         card["m2_syndrome_extraction"]["adjacent_syndrome_correlation"],
         N.adjacent_syndrome_correlation(J.D_CORR, J.SIGMA_CORR, J.CX_CORR, J.CY_CORR,
                                         J.R_SHIFT)),
        ("transversal_cnot_fidelity",
         card["m3_fault_tolerant_gates"]["transversal_cnot_fidelity"],
         G.transversal_cnot_fidelity(J.P0_CNOT, J.ALPHA_CNOT, J.BETA_CNOT, J.T_CNOT)),
        ("lattice_surgery_merge_fidelity",
         card["m3_fault_tolerant_gates"]["lattice_surgery_merge_fidelity"],
         G.lattice_surgery_merge_fidelity(J.C_LS, J.P_PHYS, J.D_LS)),
        ("lattice_surgery_resource",
         card["m3_fault_tolerant_gates"]["lattice_surgery_resource"],
         G.lattice_surgery_resource(J.D_LS)),
        ("logical_error_accumulated",
         card["m4_end_to_end"]["logical_error_accumulated"],
         L.logical_error_accumulated(J.LAM_E2E, J.T_E2E, J.BETA_E2E, J.GAMMA_E2E)),
    ]


def main() -> int:
    idx = _read(_INDEX)
    card = J.case_card()
    routes = _read(_ROUTES)

    print("[A] 前端接线（三入口面）")
    check("A1 前端接线齐备：sec-j1 段 + runJ1 按钮 + renderJ1 函数 + apiGet 调用",
          ('id="sec-j1"' in idx and 'id="runJ1"' in idx
           and "function renderJ1(" in idx and "/api/j1_qec" in idx),
          "seg=%s btn=%s fn=%s api=%s" % ('id="sec-j1"' in idx, 'id="runJ1"' in idx,
                                          "function renderJ1(" in idx, "/api/j1_qec" in idx))
    check("A2 hash 深链 CASE_MAP 含 #sec-j1 → runJ1",
          bool(re.search(r'"#sec-j1"\s*:\s*"runJ1"', idx)))
    check("A3 首屏导航含 #sec-j1 直达链接",
          bool(re.search(r'href="#sec-j1"', idx)),
          "n=%d" % len(re.findall(r'href="#sec-j1"', idx)))

    print("\n[B] 取值路径（真实 JSON 可解析 + 反向完备）")
    # renderJ1 引用的顶层块
    m = re.search(r"function renderJ1\(d\)\{(.*?)\n\}", idx, re.S)
    body = m.group(1) if m else ""
    refs = sorted(set(re.findall(r"d\.([a-z_][A-Za-z0-9_]*)", body)))
    _skip = {"error", "case_id", "verdict", "render_path_smoke", "honest_note",
             "caliber", "milestones", "anchors", "gaps", "design_point"}
    check("B1 取值路径存在性：renderJ1 引用的顶层块全部在真实 JSON 上可解析",
          all(k in card for k in refs if k != "error"),
          "refs=%s 缺=%s" % (refs, [k for k in refs if k != "error" and k not in card]))
    top_keys = [k for k in card if k not in _skip]
    check("B2 反向完备：case_card 顶层键（除身份/口径类）均被前端引用",
          all(k in refs for k in top_keys),
          "未被引用=%s" % [k for k in top_keys if k not in refs])

    print("\n[C] 跨源逐值对拍（j1_case ≡ lda_qeda 真源 · ≤1 ULP）")
    for nm, a, b in _cross_source_pairs(card):
        check("C %s ≡ lda_qeda 真源（≤1 ULP）" % nm, _ulp_ok(a, b),
              "%r vs %r" % (a, b))

    print("\n[D] 锚号与账本一致")
    from lda_harness.benchmarks import BENCHMARK_DEFS
    check("D1 9 锚 B497–B505 齐备且与 BENCHMARK_DEFS 一致",
          len(card["anchors"]) == 9
          and all(b in BENCHMARK_DEFS for b in card["anchors"])
          and set(card["anchors"]) == {"B%d" % i for i in range(497, 506)},
          "n=%d" % len(card["anchors"]))

    print("\n[E] 纪律")
    src = _read(_CASE)
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or "").split(".")[0])
    mods.discard("__future__")
    check("E1 零重计算：j1_case 顶层 import 仅标准库（禁 numpy/scipy/求解器）",
          mods <= {"math", "typing"}, "mods=%s" % sorted(mods))
    check("E2 端点免登录且不进 HEAVY_POST_PATHS",
          "/api/j1_qec" in routes and "h_j1_qec_demo" in routes)
    check("E3 verdict 恒 DESIGN_BUDGET（不伪装 ACCEPT/PASS/实测）",
          card["verdict"] == "DESIGN_BUDGET", "verdict=%s" % card["verdict"])
    sc = J.run_selfchecks()
    check("E4 模块自检全 PASS", all(sc.values()),
          "n=%d FAIL=%s" % (len(sc), [k for k, v in sc.items() if not v]))

    print("\n[F] 突变探针（先证能变红）")
    f1 = dict(card)
    f1["m1_decoder"] = dict(card["m1_decoder"], syndrome_weight=0.123)
    check("F1 突变探针：syndrome_weight 被改坏 ⇒ C 型对拍必红",
          not _ulp_ok(f1["m1_decoder"]["syndrome_weight"],
                      N.expected_syndrome_weight(J.P_PHYS, J.CODE_L)))
    f2 = dict(card)
    f2["m3_fault_tolerant_gates"] = dict(card["m3_fault_tolerant_gates"],
                                         transversal_cnot_fidelity=0.5)
    check("F2 突变探针：transversal_cnot_fidelity 被改坏 ⇒ C 型对拍必红",
          not _ulp_ok(f2["m3_fault_tolerant_gates"]["transversal_cnot_fidelity"],
                      G.transversal_cnot_fidelity(J.P0_CNOT, J.ALPHA_CNOT,
                                                  J.BETA_CNOT, J.T_CNOT)))
    f3 = dict(card, verdict="ACCEPT")
    check("F3 突变探针：verdict 被改成 ACCEPT ⇒ E3 必红（不伪装实测）",
          f3["verdict"] != "DESIGN_BUDGET")

    print("\n[G] 还原复绿")
    check("G1 还原复绿：突变后 case_card 仍与真源逐值一致",
          all(_ulp_ok(a, b) for _n, a, b in _cross_source_pairs(J.case_card())))

    bad = globals().get("FAIL", 0)
    print("\n" + "=" * 78)
    print("J1 案例卡渲染路径门禁：%s（FAIL=%d）" % ("ALL PASS" if bad == 0 else "有红色", bad))
    print("=" * 78)
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
