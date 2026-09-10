# -*- coding: utf-8 -*-
"""红队 fuzz 发散点裁决（C2 · BOUNTY 常态化 · 信任墙活体化）

读取 run_redteam_anchor_fuzz_smoke.py 落盘的 pending 发散点，用死标量重跑锚判定，
按扰动幅度分类：

  - expected_extreme_perturbation（±30% 极值扰动，落在闭式 golden 有效域外）
        ⇒ 预期物理分叉，非缺陷；不喊狼来。
  - in_domain_divergence（域内发散，扰动 < 30% 仍 err>tol）
        ⇒ 真疑点，升级 BOUNTY 人工/锚复核（不自动判 bug）。

纪律（同构 redteam_cron / 多智能体红蓝队分工）：
- LLM 不进判决路径：run_verification 的 compare_fn 是死标量，判卷与 LLM 无关。
- 本脚本只做「出题结果的分类与汇总」，不判 PASS/FAIL、不自动 confirmed。
- 假独立：扰动攻击由规则式 fuzz 生成（天然不同源、零依赖）。

输出：
  - redteam_adjudication_report.json（机器可读，供 cron 看门狗消费）
  - redteam_adjudication_report.md（人类可读，可作 BOUNTY 信任墙活体记录）

绿准则：脚本本身不因发散点 FAIL——发散点是情报，不是测试失败（同 fuzz smoke）。
       仅当输入文件缺失/损坏时非零退出（属管道断裂，须告警）。
"""
from __future__ import annotations

import json
import math
import os
import sys
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.benchmarks import BENCHMARK_DEFS
from lda_harness.verification_adapters import BENCHMARK_CANDIDATES
from lda_harness.verification_spec import (
    VerificationSpec,
    run_verification,
    compare_fn_for,
)

_EXTREME = 0.30  # 闭式 golden 有效域外阈值（与 fuzz 扰动幅度对齐）

_PENDING = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "redteam_anchor_fuzz_defects_pending.json")
_REPORT_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "redteam_adjudication_report.json")
_REPORT_MD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "redteam_adjudication_report.md")


def _classify() -> Tuple[List[str], List[str], List[str]]:
    strict, degraded, stub = [], [], []
    for bid in sorted(BENCHMARK_DEFS):
        d = BENCHMARK_DEFS[bid]
        key = d.get("candidate")
        if d.get("candidate_status") == "degraded_ordinal":
            degraded.append(bid)
        elif key and key in BENCHMARK_CANDIDATES:
            strict.append(bid)
        else:
            stub.append(bid)
    return strict, degraded, stub


def _max_perturbation(bid: str, params: Dict[str, Any]) -> float:
    """返回该点相对默认参数在浮点维度上的最大相对扰动幅度。

    零基准参数（default=0）改用绝对 delta（fuzz 用 ±0.1/±0.3），
    故 delta>=0.3 视为极端。非浮点参数忽略（无法定义相对扰动）。
    """
    d = BENCHMARK_DEFS.get(bid, {})
    default = d.get("default_params", {}) or {}
    worst = 0.0
    for k, v in params.items():
        if k not in default:
            continue
        dv = default[k]
        if isinstance(dv, (int, float)) and not isinstance(dv, bool):
            if dv == 0:
                # 零基准：用绝对量纲的 delta 衡量
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    worst = max(worst, abs(float(v)) / 0.3)  # delta/0.3 → >=1 即极端
            else:
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    worst = max(worst, abs(float(v) - float(dv)) / abs(float(dv)))
    return worst


def _rejudge(bid: str, params: Dict[str, Any], as_strict: bool) -> Dict[str, Any]:
    d = BENCHMARK_DEFS[bid]
    tol = float(d["tol"])
    cmp = d.get("cmp", "abs")
    golden_fn = d["golden_fn"]
    key = d.get("candidate")
    spec = VerificationSpec(
        spec_id=bid, metric=d["metric"],
        oracle_kind=d.get("oracle_kind", "physical_law"),
        oracle_fn=lambda pp, g=golden_fn: g(**pp),
        compare_fn=compare_fn_for(cmp), tol=tol, tol_mode=cmp,
        params=params, source="redteam_adjudication",
    )
    if as_strict and key and key in BENCHMARK_CANDIDATES:
        cand_fn = lambda sp, ov, k=key: BENCHMARK_CANDIDATES[k](sp, ov)
    else:
        cand_fn = lambda sp, ov: sp.oracle_fn(sp.params)
    out = run_verification(spec, cand_fn)
    return {
        "oracle": out.oracle_value,
        "cand": out.candidate,
        "err": out.err,
        "passed": out.passed,
    }


def main() -> int:
    print("红队 fuzz 发散点裁决（死标量重判 · 不喊狼来）")
    print("=" * 60)

    if not os.path.exists(_PENDING):
        print(f"  [OK] 无 pending 发散点文件（{_PENDING}）— 红队 fuzz 未产出分歧，干净。")
        rep = {"total": 0, "expected_extreme": 0, "in_domain_suspect": 0,
               "records": [], "clean": True}
        with open(_REPORT_JSON, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
        return 0

    with open(_PENDING, "r", encoding="utf-8") as f:
        pending = json.load(f)
    defects = pending.get("defects", []) or []
    print(f"  读入 pending 发散点：{len(defects)} 个")

    strict, degraded, stub = _classify()
    strict_set = set(strict)
    in_strict = {b for b in strict_set}

    expected, suspect = [], []
    records = []
    for df in defects:
        bid = df.get("bid")
        params = df.get("params", {}) or {}
        as_strict = bid in in_strict
        rj = _rejudge(bid, params, as_strict)
        worst = _max_perturbation(bid, params)
        if worst >= _EXTREME:
            cls = "expected_extreme_perturbation"
            bucket = expected
        else:
            cls = "in_domain_divergence"
            bucket = suspect
        rec = {
            "bid": bid, "as_strict": as_strict,
            "params": params,
            "oracle": rj["oracle"], "cand": rj["cand"], "err": rj["err"],
            "tol": df.get("tol"), "passed": rj["passed"],
            "max_perturbation": round(worst, 4),
            "classification": cls,
        }
        bucket.append(rec)
        records.append(rec)
        print(f"  [{cls[:6]:>6}] {bid:<5} 扰动={worst:5.2f} "
              f"err={rj['err']:.3e} tol={df.get('tol')} as_strict={as_strict}")

    rep = {
        "total": len(records),
        "expected_extreme": len(expected),
        "in_domain_suspect": len(suspect),
        "suspects": suspect,   # 升级 BOUNTY 人工/锚复核
        "records": records,
        "clean": len(suspect) == 0,
    }
    with open(_REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2, default=str)

    # 人类可读信任墙记录
    lines = ["# 红队对抗裁决 · 活体记录（自动生成）", "",
             f"- 裁决时间：{(__import__('datetime').datetime.now()).strftime('%Y-%m-%d %H:%M:%S')}",
             f"- 总发散点：**{len(records)}**",
             f"- 预期极值分叉（有效域外，非缺陷）：**{len(expected)}**",
             f"- 域内疑点（升级 BOUNTY 复核）：**{len(suspect)}**", "",
             "## 域内疑点（须人工/锚复核，不自动判 bug）", ""]
    if suspect:
        for r in suspect:
            lines.append(f"- **{r['bid']}** 扰动={r['max_perturbation']:.2f} "
                         f"err={r['err']:.3e} tol={r['tol']} params={r['params']}")
    else:
        lines.append("（无）— 全部发散点均在闭式 golden 有效域外，属预期物理分叉。")
    lines += ["", "## 预期极值分叉（闭式 golden 有效域外，非缺陷）", ""]
    for r in expected[:30]:
        lines.append(f"- {r['bid']} 扰动={r['max_perturbation']:.2f} err={r['err']:.3e}")
    if len(expected) > 30:
        lines.append(f"- …（其余 {len(expected)-30} 条略）")
    with open(_REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("-" * 60)
    print(f"  预期极值分叉 = {len(expected)}（非缺陷）")
    print(f"  域内疑点     = {len(suspect)}（升级 BOUNTY 复核）")
    print(f"  报告落盘 = {_REPORT_JSON}")
    print(f"  信任墙记录 = {_REPORT_MD}")
    if suspect:
        print(f"  [情报] {len(suspect)} 个域内疑点须人工/锚复核（不自动 confirmed）")
    else:
        print("  [OK] 无域内疑点 — 全部分歧为预期物理分叉")
    print("=" * 60)
    print("红队裁决：完成（脚本不因发散点 FAIL；发散点是情报非测试失败）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
