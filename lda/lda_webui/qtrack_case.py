# -*- coding: utf-8 -*-
"""量子赛道六层总览案例卡（K5 · `sec-qtrack` · **零重计算**）。

设计约束（🔴 硬）：
1. **零重计算**：本模块只做**元数据聚合**，不重算任何物理量；
2. **只用 stdlib + 读受跟踪 JSON**：**禁止 import `lda_harness.benchmarks`**
   —— 生产环境无 `scipy`，而 `benchmarks.__init__` 链会拉 `golden` →
   `_batch_b2_numeric` → `scipy.linalg` ⇒ 会 500。
3. **层划分按章程确定的编号区间**（J1–J5 为连续区间；Layer 0 = B473–B496），
   不靠 title 关键词猜（关键词会把非区间锚误卷进来）。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

CALIBER = "LDA 量子赛道蓝图 v1 · Layer 0–5 六层总览（设计期签核）"
CASE_ID = "LDA-QTRACK · 量子赛道六层复利总览（Layer 0 → J5）"
RENDER_PATH_SMOKE = "run_webui_qtrack_render_path_smoke.py"
HEAVY_POST = False

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPORTS = os.path.join(_HERE, "..", "reports")
_COV = os.path.join(_REPORTS, "anchor_gate_coverage.json")
_VERIF = os.path.join(_REPORTS, "verification_report.json")

# 六层：编号区间（章程确定）+ 门禁名 + 判据数（实跑现数，见白皮书 §3.1）
LAYERS: List[Dict[str, Any]] = [
    {"id": "L0", "name": "器件与相位（QS-M*）", "lo": 473, "hi": 496,
     "gate": "qs_m*_smoke.py（多档）", "judges": None,
     "role": "几何 / 相位 / 协同度基座"},
    {"id": "L1", "name": "量子纠错（J1）", "lo": 497, "hi": 505,
     "gate": "run_j1_qec_smoke.py", "judges": 19,
     "role": "阈值标度 · 解码器 · 综合征 · 容错门"},
    {"id": "L2", "name": "超导处理器（J2）", "lo": 506, "hi": 509,
     "gate": "run_j2_qpu_smoke.py", "judges": 37,
     "role": "CR 门 · ZZ · 多音串扰 · 耦合图"},
    {"id": "L3", "name": "测控与读出（J3）", "lo": 510, "hi": 514,
     "gate": "run_j3_ctrl_smoke.py", "judges": 44,
     "role": "Rabi · DRAG · 纯度 · Purcell · 噪声链"},
    {"id": "L4", "name": "传感系统（J4）", "lo": 515, "hi": 518,
     "gate": "run_j4_multiparam_smoke.py", "judges": 25,
     "role": "多参数解耦 · 旁瓣 · 串扰 · 热负载"},
    {"id": "L5", "name": "量子网络（J5）", "lo": 519, "hi": 522,
     "gate": "run_j5_qnet_smoke.py", "judges": 66,
     "role": "分发保真 · HOM · 中继 · 换能"},
]

FORBIDDEN_IMPORTS = ("lda_harness.benchmarks", "lda_harness.golden",
                     "scipy", "numpy")


def _load(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _anchor_num(aid: str):
    return int(aid[1:]) if aid.startswith("B") and aid[1:].isdigit() else None


def layer_table() -> List[Dict[str, Any]]:
    """六层聚合（纯元数据）。"""
    cov = _load(_COV)
    ver = _load(_VERIF)
    cls = {r["id"]: r.get("candidate_class", "") for r in ver["results"]}
    known = set(cov["anchors"])
    out = []
    for L in LAYERS:
        ids = sorted((a for a in known
                      if (_anchor_num(a) is not None
                          and L["lo"] <= _anchor_num(a) <= L["hi"])),
                     key=_anchor_num)
        l2 = sum(1 for a in ids
                 if (cov["anchors"][a].get("l2_count") or 0) > 0)
        l3 = sum(1 for a in ids if cov["anchors"][a].get("l3") is True)
        strict = sum(1 for a in ids if cls.get(a) == "strict_independent")
        out.append({
            "id": L["id"], "name": L["name"], "role": L["role"],
            "band": "B%d–B%d" % (L["lo"], L["hi"]),
            "anchors_n": len(ids), "anchor_ids": ids,
            "strict_n": strict,
            "l2_n": l2, "l3_n": l3,
            "gate": L["gate"], "judges": L["judges"],
            "full_covered": len(ids) > 0 and l2 == len(ids) and l3 == len(ids),
        })
    return out


def case_card() -> Dict[str, Any]:
    layers = layer_table()
    cov = _load(_COV)
    ver = _load(_VERIF)
    total_anchors = sum(l["anchors_n"] for l in layers)
    total_strict = sum(l["strict_n"] for l in layers)
    total_l2 = sum(l["l2_n"] for l in layers)
    total_l3 = sum(l["l3_n"] for l in layers)
    judges = sum(l["judges"] or 0 for l in layers)
    led = ver["summary"]
    return {
        "case_id": CASE_ID,
        "caliber": CALIBER,
        "verdict": "ACCEPT",
        "layers": layers,
        "totals": {
            "layers_n": len(layers),
            "anchors_n": total_anchors,
            "strict_n": total_strict,
            "l2_n": total_l2,
            "l3_n": total_l3,
            "judges_n": judges,
            "full_covered_layers": sum(1 for l in layers if l["full_covered"]),
        },
        "ledger": {
            "anchors": led["total"],
            "strict_independent": led["candidate_class_totals"]["strict_independent"],
            "degraded_ordinal": led["candidate_class_totals"]["degraded_ordinal"],
            "self_consistent_stub": led["candidate_class_totals"]["self_consistent_stub"],
            "verified": led["verified"],
        },
        "coverage": {
            "anchors_total": cov["summary"]["anchors_total"],
            "l1": cov["summary"]["l1_unified_covered"],
            "l2": cov["summary"]["l2_bespoke_covered"],
            "l3": cov["summary"]["l3_multi_covered"],
            "blind": cov["summary"]["l2_blind"],
            "core_smokes": cov["summary"]["core_smokes"],
            "ratchet": cov["ratchet"],
        },
        "honesty": [
            "设计期签核（design-time signoff），非流片实测",
            "参数为设计示例量级，非具体 PDK 认证值",
            "规模数字为版图容量，非已制造规模",
            "不报 TOPS / fJ-op / 能效比",
            "全账本仍有 415 锚仅有统一判决（K4 已机器登记，不粉饰）",
        ],
        "render_path_smoke": RENDER_PATH_SMOKE,
        "heavy_post": HEAVY_POST,
    }


def run_selfchecks() -> Dict[str, bool]:
    ok: Dict[str, bool] = {}
    # ① 零重计算：顶层不得 import 物理/数值库
    import ast
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    tree = ast.parse(src)
    mods = set()
    for n in tree.body:
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    ok["zero_recompute_imports"] = not any(
        bad.split(".")[0] in mods for bad in FORBIDDEN_IMPORTS)
    ok["top_imports_whitelist"] = mods <= {"json", "os", "typing",
                                           "ast", "__future__"}

    card = case_card()
    t = card["totals"]
    ok["layers_six"] = t["layers_n"] == 6
    ok["anchors_at_least_48"] = t["anchors_n"] >= 48
    ok["strict_eq_anchors"] = t["strict_n"] == t["anchors_n"]
    ok["l2_eq_anchors"] = t["l2_n"] == t["anchors_n"]
    ok["l3_eq_anchors"] = t["l3_n"] == t["anchors_n"]
    ok["all_layers_full_covered"] = t["full_covered_layers"] == 6
    ok["judges_at_least_191"] = t["judges_n"] >= 191

    # 逐层自洽
    for l in card["layers"]:
        ok["layer_%s_covered" % l["id"]] = (
            l["anchors_n"] > 0 and l["l2_n"] == l["anchors_n"]
            and l["l3_n"] == l["anchors_n"] and l["full_covered"])
        ok["layer_%s_nonempty" % l["id"]] = l["anchors_n"] > 0

    # 层间不重叠 + 合计守恒
    allids = [a for l in card["layers"] for a in l["anchor_ids"]]
    ok["layers_disjoint"] = len(allids) == len(set(allids))
    ok["band_labels"] = all("-" in l["band"] or "–" in l["band"]
                            for l in card["layers"])

    # 与 K4 矩阵口径一致
    c = card["coverage"]
    ok["coverage_l1_all"] = c["l1"] == c["anchors_total"] >= 538
    ok["coverage_l2_plus_blind"] = c["l2"] + c["blind"] == c["anchors_total"]
    # 🔴 下限棘轮语义必须是 `>=`（「只增不减」），不能写 `==`：
    #   v0.9.251 首轮全量 CI 当场抓出 —— BL 门禁**点名** `B391`（缺陷登记表）令 K4 的
    #   文本代理 L2 由 123 涨到 124，`l2_min`（下限 123）未变 ⇒ `==` 把**涨**判成**红**。
    #   同族血案第二次：v0.9.249 K0 的 `CASE_PANELS_MIN == 16` 被 17 打反。
    ok["ratchet_present"] = c["l2"] >= c["ratchet"]["l2_min"] and \
        c["l3"] >= c["ratchet"]["l3_min"]
    ok["core_smokes_at_least_333"] = c["core_smokes"] >= 333

    # 与 verification_report 口径一致
    lg = card["ledger"]
    ok["ledger_at_least_538"] = lg["anchors"] >= 538
    ok["ledger_classes_sum"] = (lg["strict_independent"] + lg["degraded_ordinal"]
                                + lg["self_consistent_stub"]) == lg["anchors"]
    ok["ledger_verified_eq_strict"] = lg["verified"] == lg["strict_independent"]

    # 诚实边界齐备 + 渲染门禁名
    ok["honesty_present"] = len(card["honesty"]) >= 5
    ok["render_smoke_declared"] = card["render_path_smoke"] == RENDER_PATH_SMOKE
    ok["not_heavy_post"] = card["heavy_post"] is False
    return ok


def main() -> int:  # pragma: no cover
    sc = run_selfchecks()
    bad = [k for k, v in sc.items() if not v]
    print("=" * 72)
    print("量子赛道六层总览案例卡自检：%d 项" % len(sc))
    for k in sc:
        print("  [%s] %s" % ("PASS" if sc[k] else "FAIL", k))
    print("=" * 72)
    print("FAIL=%d" % len(bad))
    card = case_card()
    print("\n层数 %d · 锚 %d · 严格独立 %d · L2 %d · L3 %d · 判据 %d"
          % (card["totals"]["layers_n"], card["totals"]["anchors_n"],
             card["totals"]["strict_n"], card["totals"]["l2_n"],
             card["totals"]["l3_n"], card["totals"]["judges_n"]))
    return 0 if not bad else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
