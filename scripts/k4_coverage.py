# -*- coding: utf-8 -*-
"""K4 · 六层门禁「判据 × 锚」覆盖矩阵（机器生成 · **禁手写**）。

三层覆盖（**分层如实，不虚报**）：
  L1 统一判决 —— `lda/reports/verification_report.json` 的 `results` 行集
                （harness 统一跑全部锚；L1 = 账本全集才是健康态）
  L2 专属门禁 —— CORE 门禁源码（去注释后）**显式出现该锚号** ≥1 处
  L3 多重专属 —— 同一锚被 ≥2 个 CORE 门禁显式提及

同时产出**覆盖下限棘轮**（`l2_min` / `l3_min`，只升不降）与**盲区台账**
（L2 未覆盖的锚，按号段分组），供补盲排期。

确定性：零时间戳 / 零随机 / 零 git HEAD；键序固定；写盘走 `det.write_text`（UTF-8 + LF）。

用法：
    python scripts/k4_coverage.py            # 打印台账正文（供门禁逐字节对拍）
    python scripts/k4_coverage.py --write    # 写回 lda/reports/anchor_gate_coverage.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LDA = os.path.join(_REPO, "lda")
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

from lda_harness import deterministic as det  # noqa: E402  （⑧b：确定性唯一口径）

SCHEMA = "lda_anchor_gate_coverage_v1"
OUT_REL = "lda/reports/anchor_gate_coverage.json"
VERIF_REL = "lda/reports/verification_report.json"

# 🔵 覆盖下限棘轮（**只升不降**）：L2 = 有专属门禁提及 · L3 = ≥2 门禁
L2_MIN = 123
L3_MIN = 65

ANCHOR_RE = re.compile(r"\bB(\d{3})\b")

# 🔴 排除门禁（**双向锁死**：门禁侧独立登记同一集合，见 G1 判据）——
#   本门禁判决「覆盖矩阵」本身；其 `_band()` 的 "B100–B199" 等**号段标签字符串**
#   会被锚号正则误扫成假覆盖 ⇒ 必须排除，且**只允许排除这一项**。
EXCLUDE_GATES = {
    "run_k4_coverage_smoke.py":
        "判决覆盖矩阵本身；_band() 的号段标签不是锚判据",
}


def _core_smokes():
    path = os.path.join(_LDA, "run_ci_regression.py")
    spec = importlib.util.spec_from_file_location("_ci_k4", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return [s for s in getattr(m, "CORE_SMOKES", [])]


def _ledger_ids():
    from lda_harness.benchmarks import BENCHMARK_DEFS, BENCHMARK_ORDER
    return sorted(set(BENCHMARK_DEFS) | set(BENCHMARK_ORDER))


def _lang_ids():
    """L1：harness 统一判决覆盖的锚（verification_report.results 的 id 集）。"""
    p = os.path.join(_REPO, VERIF_REL)
    if not os.path.exists(p):
        return set()
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    return {r["id"] for r in d.get("results", [])}


def _strip_comments(src: str) -> str:
    """去掉整行注释（注释里提锚号不算判据覆盖）。"""
    return "\n".join(ln for ln in src.split("\n")
                     if not ln.strip().startswith("#"))


def _band(aid: str) -> str:
    if aid.startswith("E"):
        return "E（实证）"
    if aid.startswith("S"):
        return "S（系统层）"
    n = int(aid[1:])
    lo = (n // 100) * 100
    hi = lo + 99
    return "B%d–B%d" % (lo, hi) if n >= 100 else "B1–B99"


def build():
    ids = _ledger_ids()
    idset = set(ids)
    core_all = _core_smokes()
    core = [c for c in core_all if c not in EXCLUDE_GATES]
    l1 = _lang_ids() & idset

    gate_anchors = {}
    for name in core:
        path = os.path.join(_LDA, name)
        if not os.path.exists(path):
            gate_anchors[name] = []
            continue
        with open(path, encoding="utf-8") as f:
            body = _strip_comments(f.read())
        found = {"B" + n for n in ANCHOR_RE.findall(body)}
        gate_anchors[name] = sorted(found & idset)

    anchor_gates = {}
    for name, anchors in gate_anchors.items():
        for a in anchors:
            anchor_gates.setdefault(a, []).append(name)
    for a in anchor_gates:
        anchor_gates[a].sort()

    l2 = set(anchor_gates)
    l3 = {a for a, gs in anchor_gates.items() if len(gs) >= 2}
    blind = sorted(idset - l2)

    dist = {}
    for gs in anchor_gates.values():
        dist[str(len(gs))] = dist.get(str(len(gs)), 0) + 1

    blind_by_band = {}
    for a in blind:
        b = _band(a)
        blind_by_band[b] = blind_by_band.get(b, 0) + 1

    anchors_out = {}
    for a in ids:
        gs = anchor_gates.get(a, [])
        anchors_out[a] = {
            "l1": a in l1,
            "l2_gates": gs,
            "l2_count": len(gs),
            "l3": len(gs) >= 2,
        }

    payload = {
        "schema": SCHEMA,
        "generated_by": "scripts/k4_coverage.py",
        "roadmap": "K（量子赛道一期结算与固化）",
        "subject": "hex-layer gate × anchor coverage matrix",
        "method": ("三层：L1 = verification_report.results 的 id 集；"
                   "L2/L3 = CORE 门禁源码去注释后显式锚号；锚全集 = "
                   "BENCHMARK_DEFS ∪ BENCHMARK_ORDER"),
        "excluded_fields": ["时间戳（非确定量）", "git HEAD（每次提交都变）"],
        "summary": {
            "anchors_total": len(idset),
            "core_smokes": len(core_all),
            "gates_scanned": len(core),
            "gates_excluded": len(EXCLUDE_GATES),
            "l1_unified_covered": len(l1),
            "l2_bespoke_covered": len(l2),
            "l3_multi_covered": len(l3),
            "l2_blind": len(blind),
            "gates_with_anchors": sum(1 for v in gate_anchors.values() if v),
            "gates_zero_anchor": sum(1 for v in gate_anchors.values() if not v),
            "by_gate_count": {k: dist[k] for k in sorted(dist, key=int)},
            "blind_by_band": {k: blind_by_band[k] for k in sorted(blind_by_band)},
        },
        "excluded_gates": {k: EXCLUDE_GATES[k] for k in sorted(EXCLUDE_GATES)},
        "ratchet": {"l2_min": L2_MIN, "l3_min": L3_MIN,
                    "policy": "只升不降：新增锚必须补专属判据或显式登记为 L1-only"},
        "anchors": anchors_out,
        "gates": {k: gate_anchors[k] for k in sorted(gate_anchors)},
        "blind_anchors": blind,
    }
    return payload


def render(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="K4 门禁×锚 覆盖矩阵生成器")
    ap.add_argument("--write", action="store_true", help="写回受跟踪台账")
    args = ap.parse_args(argv)

    payload = build()
    text = render(payload)
    if args.write:
        det.write_text(os.path.join(_REPO, OUT_REL), text)
        s = payload["summary"]
        print("[written] %s（锚 %d · L1 %d / L2 %d / L3 %d · 盲区 %d）"
              % (OUT_REL, s["anchors_total"], s["l1_unified_covered"],
                 s["l2_bespoke_covered"], s["l3_multi_covered"], s["l2_blind"]))
    else:
        # ⚠️ Windows 下 print 到管道是 CRLF，写盘是纯 LF；门禁走 text=True 归一
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
