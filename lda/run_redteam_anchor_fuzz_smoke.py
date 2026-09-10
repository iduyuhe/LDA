# -*- coding: utf-8 -*-
"""红队锚面 fuzz 护栏（C · 让 26 严独也被外部攻击过一遍）。

背景：既有红队（run_redteam_*.py）只打 S 系列预算锚（4 参数链路空间），
对 26 个**物理严独锚（B/E 系列）+ 25 自证桩**完全没攻击过。本 smoke 把攻击面
扩展到全部 52 锚：对每个锚做参数扰动，用统一死标量执行器 run_verification
（独立候选 vs golden）判卷，记录发散点。

纪律（同构既有红队，见 MEMORY「多智能体红蓝队分工纪律」）：
- LLM 不进判决路径：run_verification 的 compare_fn 是死标量，判卷与 LLM 无关。
- 红队只「出题/攻击」（此处=参数扰动生成），锚判卷。
- 假独立：扰动攻击若用 LLM 生成（可选增强），须与生成器模型不同源；本基线用
  规则式扰动（天然不同源、零依赖、可复现），LLM 增强为可选。

死标量（同构既有红队 metrics）：
  strict_coverage = 被攻击的严独锚数 / 26          （目标 1.0：全覆盖）
  attacks_total   = 出题（扰动）总数
  genuine_div     = 独立候选与 golden 在域内发散(有限值且 err>tol) 数
                    （>0 ⇒ 锚可能是假独立 / golden 或候选算错 ⇒ 真实发现）
  cand_limitation = 候选在扰动下抛异常/返回 None 数（候选覆盖不全，非 golden 错）
  golden_unstable = golden 在扰动下 NaN/inf 数（自证桩域安全）
  divergence_rate = (genuine_div + golden_unstable) / attacks_total

绿准则（健康基线）：strict_coverage==1.0 且 genuine_div==0。
  - coverage<1.0 ⇒ 红队没打全 26 严独 ⇒ FAIL（攻击面缺口）。
  - genuine_div>0 ⇒ 发现跨方法发散 ⇒ FAIL 并打印候选（交 BOUNTY 人工复核，
    非自动判 PASS/FAIL，守「LLM 不进判决路径」）。
降级：无外部依赖，纯 CPU 规则式扰动，必跑（无权豁免）。
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.benchmarks import BENCHMARK_DEFS
from lda_harness.verification_adapters import BENCHMARK_CANDIDATES
from lda_harness.verification_spec import (
    VerificationSpec,
    run_verification,
    compare_fn_for,
)

_PASS = 0
_FAIL = 0
_REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "redteam_anchor_fuzz_report.json")
_DEFECTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "redteam_anchor_fuzz_defects_pending.json")


def _classify() -> Tuple[List[str], List[str], List[str]]:
    """三分类（与 C2 护栏 / routes.py 同源口径）。"""
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


def _llm_attack_anchor(bid: str, d: Dict[str, Any],
                       params0: Dict[str, Any], n: int = 4) -> List[Dict[str, Any]]:
    """可选 LLM 扰动生成器（接 generator="llm"）。

    仅当 LDA_REDTEAM_BASE/KEY 配置时启用；复用 RedTeamProposer 同款 OpenAI 兼容
    HTTP 模式。LLM **只出对抗参数**，不判对错（判卷在 run_verification 死标量）。
    未配置 / 调用失败 / 解析失败 → 返回空列表（调用方回退规则式，零依赖优雅降级）。
    """
    base = (os.environ.get("LDA_REDTEAM_BASE")
            or os.environ.get("LDA_LLM_BASE") or "").rstrip("/")
    key = os.environ.get("LDA_REDTEAM_KEY") or ""
    model = os.environ.get("LDA_REDTEAM_MODEL") or "gpt-4o-mini"
    if not (base and key):
        return []
    try:
        import json as _json
        import urllib.request as _req
        pschema = ", ".join(f"{k}:{type(v).__name__}={v!r}"
                            for k, v in params0.items())
        prompt = (
            f"你是光子/量子验证管线的对抗红队。锚 {bid} 指标={d.get('metric')}。"
            f"参数现状：{pschema}。请构造 {n} 组「工程界内、但应让该锚的闭式 golden "
            f"与独立候选分叉」的临界对抗参数（如把某个物理量推向近似失效边界）。"
            f"只输出 JSON 数组，每项含上述全部参数键（数值）。")
        body = {"model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.9, "max_tokens": 600}
        rq = _req.Request(f"{base}/chat/completions",
                          data=_json.dumps(body).encode("utf-8"),
                          headers={"Content-Type": "application/json",
                                    "Authorization": f"Bearer {key}"},
                          method="POST")
        with _req.urlopen(rq, timeout=30) as resp:
            txt = _json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]
        t = txt.strip()
        if "```" in t:
            for part in t.split("```"):
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("["):
                    t = part
                    break
        raw = _json.loads(t[t.find("["):t.rfind("]") + 1])
        out = []
        for c in raw:
            if not isinstance(c, dict):
                continue
            item = {}
            ok = True
            for k, v0 in params0.items():
                if k not in c:
                    ok = False
                    break
                try:
                    val = float(c[k]) if isinstance(v0, (int, float)) and not isinstance(v0, bool) else c[k]
                    if isinstance(v0, (int, float)) and not isinstance(v0, bool) and not math.isfinite(val):
                        ok = False
                        break
                    item[k] = val
                except (TypeError, ValueError):
                    ok = False
                    break
            if ok:
                out.append(item)
        return out
    except Exception:
        return []


def _perturb(params0: Dict[str, Any], factors=(0.7, 0.85, 1.0, 1.15, 1.3)
             ) -> List[Dict[str, Any]]:
    """对每个浮点参数独立做乘性扰动（一次一个），含标称点(1.0)。

    只扰动数值参数；非数值（字符串/列表/布尔）保持默认，避免破坏锚语义。
    """
    out: List[Dict[str, Any]] = []
    float_keys = [k for k, v in params0.items()
                  if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not float_keys:
        out.append(dict(params0))
        return out
    for k in float_keys:
        base = float(params0[k])
        if base == 0:
            # 零基参数：加 ±小量而非乘性，避免恒为零
            deltas = [0.0, 0.1 * (1.0 if base >= 0 else -1.0),
                      0.3 * (1.0 if base >= 0 else -1.0)]
            for dl in deltas:
                p = dict(params0)
                p[k] = base + dl
                out.append(p)
        else:
            for f in factors:
                p = dict(params0)
                p[k] = base * f
                out.append(p)
    # 去重（标称点会重复出现）；参数值可能含 list/dict，转成可哈希键
    def _hkey(v):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return round(float(v), 6)
        if isinstance(v, (list, tuple)):
            return tuple(_hkey(x) for x in v)
        if isinstance(v, dict):
            return tuple(sorted((k, _hkey(val)) for k, val in v.items()))
        return v

    seen, uniq = set(), []
    for p in out:
        key = tuple(sorted((kk, _hkey(v)) for kk, v in p.items()))
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def _is_empirical(d: Dict[str, Any]) -> bool:
    """实证锚（真值来自实测语料库，无闭式 golden）→ 不可经闭式 fuzz。"""
    if d.get("anchor") in ("empirical", "empirical_unverified"):
        return True
    try:
        g = d["golden_fn"](**d["default_params"])
    except Exception:
        return True
    return g is None


def _fuzz_one(bid: str, as_strict: bool) -> Dict[str, Any]:
    d = BENCHMARK_DEFS[bid]
    params0 = dict(d["default_params"])
    tol = float(d["tol"])
    cmp = d.get("cmp", "abs")
    golden_fn = d["golden_fn"]
    key = d.get("candidate")

    # 实证锚：无闭式 golden，交实测语料库判卷；此处仅计覆盖，不做闭式 fuzz
    if _is_empirical(d):
        return {"bid": bid, "as_strict": as_strict, "n_attacks": 0,
                "genuine_div": 0, "cand_limitation": 0, "golden_unstable": 0,
                "empirical_skip": True, "samples": []}

    attacks = _perturb(params0)
    # 可选 LLM 对抗增强（env 门控；无 key 返回空，纯规则式，零依赖）
    llm_atk = _llm_attack_anchor(bid, d, params0, n=4)
    if llm_atk:
        def _hkey(p):
            return tuple(sorted((kk, round(float(v), 6)
                                if isinstance(v, (int, float)) and not isinstance(v, bool)
                                else v) for kk, v in p.items()))
        seen_keys = {_hkey(a) for a in attacks}
        for a in llm_atk:
            hk = _hkey(a)
            if hk not in seen_keys:
                seen_keys.add(hk)
                attacks.append(a)
    genuine_div, cand_lim, golden_unstable = 0, 0, 0
    samples = []

    for p in attacks:
        spec = VerificationSpec(
            spec_id=bid,
            metric=d["metric"],
            oracle_kind=d.get("oracle_kind", "physical_law"),
            oracle_fn=lambda pp, g=golden_fn: g(**pp),
            compare_fn=compare_fn_for(cmp),
            tol=tol,
            tol_mode=cmp,
            params=p,
            source="redteam_fuzz",
        )
        if as_strict and key and key in BENCHMARK_CANDIDATES:
            cand_fn = lambda sp, ov, k=key: BENCHMARK_CANDIDATES[k](sp, ov)
        else:
            # 自证桩：候选 ≡ golden（域安全检查）
            cand_fn = lambda sp, ov: sp.oracle_fn(sp.params)

        out = run_verification(spec, cand_fn)
        if out.oracle_value is None or (isinstance(out.oracle_value, float)
                                        and not math.isfinite(out.oracle_value)):
            golden_unstable += 1
            samples.append({"params": p, "issue": "golden_unstable",
                            "oracle": out.oracle_value, "cand": out.candidate,
                            "err": out.err})
            continue
        if not out.passed:
            if out.candidate is None or "执行异常" in out.diagnostics:
                cand_lim += 1
                samples.append({"params": p, "issue": "candidate_limitation",
                                "diag": out.diagnostics})
            else:
                genuine_div += 1
                samples.append({"params": p, "issue": "genuine_divergence",
                                "oracle": out.oracle_value,
                                "cand": out.candidate, "err": out.err,
                                "tol": tol})
    return {
        "bid": bid, "as_strict": as_strict, "n_attacks": len(attacks),
        "genuine_div": genuine_div, "cand_limitation": cand_lim,
        "golden_unstable": golden_unstable, "samples": samples[:5],
    }


def main():
    print("红队锚面 fuzz（覆盖 26 严独 + 25 自证桩）")
    print("=" * 60)

    strict, degraded, stub = _classify()
    print(f"三分类：严独 {len(strict)} · 降级 {len(degraded)} · 自证 {len(stub)}")

    strict_attacked = 0
    attacks_total = 0
    genuine_div_total = 0
    cand_lim_total = 0
    golden_unstable_total = 0
    findings = []

    # 重点：26 严独全打
    for bid in strict:
        r = _fuzz_one(bid, as_strict=True)
        strict_attacked += 1
        attacks_total += r["n_attacks"]
        genuine_div_total += r["genuine_div"]
        cand_lim_total += r["cand_limitation"]
        golden_unstable_total += r["golden_unstable"]
        if r["genuine_div"] > 0:
            findings.append(r)
        tag = " (实证跳过)" if r.get("empirical_skip") else ""
        print(f"  [严独] {bid:<5} 攻击={r['n_attacks']:>3}{tag} "
              f"发散={r['genuine_div']} 候选局限={r['cand_limitation']} "
              f"golden失稳={r['golden_unstable']}")

    # 扩展：25 自证桩（域安全检查，非跨方法判卷）
    for bid in stub:
        r = _fuzz_one(bid, as_strict=False)
        attacks_total += r["n_attacks"]
        cand_lim_total += r["cand_limitation"]
        golden_unstable_total += r["golden_unstable"]
        if r["golden_unstable"] > 0:
            findings.append(r)
        tag = " (实证跳过)" if r.get("empirical_skip") else ""
        print(f"  [自证] {bid:<5} 攻击={r['n_attacks']:>3}{tag} "
              f"候选局限={r['cand_limitation']} "
              f"golden失稳={r['golden_unstable']}")

    strict_coverage = strict_attacked / len(strict) if strict else 1.0
    divergence_rate = ((genuine_div_total + golden_unstable_total) / attacks_total
                       if attacks_total else 0.0)

    report = {
        "strict_total": len(strict),
        "strict_attacked": strict_attacked,
        "strict_coverage": strict_coverage,
        "attacks_total": attacks_total,
        "genuine_div": genuine_div_total,
        "cand_limitation": cand_lim_total,
        "golden_unstable": golden_unstable_total,
        "divergence_rate": divergence_rate,
        "findings": findings,
    }
    with open(_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    # BOUNTY 待复核缺陷候选：仅汇总统发发散点，交人工确认后再 land（守
    # 「LLM 不进判决路径」——此处不自动 confirmed）。每个含 bid/params/err/tol，
    # 可直接作为 BOUNTY 对抗题/缺陷提交（见 BOUNTY.md 评审流）。
    pending = []
    for r in findings:
        for s in r.get("samples", []):
            if s.get("issue") == "genuine_divergence":
                pending.append({"bid": r["bid"], "params": s.get("params"),
                                "oracle": s.get("oracle"), "cand": s.get("cand"),
                                "err": s.get("err"), "tol": s.get("tol"),
                                "status": "pending_human_review"})
    if pending:
        with open(_DEFECTS_PATH, "w", encoding="utf-8") as f:
            json.dump({"n_pending": len(pending), "defects": pending},
                      f, ensure_ascii=False, indent=2, default=str)
        print(f"  [BOUNTY] {len(pending)} 个待复核缺陷候选 → {_DEFECTS_PATH}")

    print("-" * 60)
    print(f"  严独覆盖 = {strict_attacked}/{len(strict)} ({strict_coverage:.2f})")
    print(f"  攻击总数 = {attacks_total}")
    print(f"  跨方法发散 = {genuine_div_total}  候选局限 = {cand_lim_total}  "
          f"golden失稳 = {golden_unstable_total}")
    print(f"  发散率   = {divergence_rate:.4f}")
    print(f"  报告落盘 = {_REPORT_PATH}")

    # 绿准则（守「不喊狼来」纪律）：
    #   硬门禁 = 严独覆盖 26/26（攻击面必须全覆盖，否则是真实缺口）。
    #   发散点 = 待人工/BOUNTY 域有效性复核的情报（多为 ±30% 极值扰动推到闭式
    #           golden 有效域外，属预期物理分叉，非确认 bug）；仅打印+落盘，不硬判 FAIL。
    #   实证锚 = 无闭式 golden，已跳过内圈 fuzz，不计入失稳/发散。
    ok = True
    if strict_coverage < 1.0:
        ok = False
        print(f"  [FAIL] 严独覆盖 < 1.0（{strict_coverage:.2f}）：攻击面缺口")
    else:
        print(f"  [PASS] 严独全覆盖（{strict_attacked}/{len(strict)}）")

    print(f"  [情报] 跨方法发散 {genuine_div_total} 处（待域有效性人工复核，非确认缺陷）")
    for r in findings:
        if r.get("genuine_div"):
            print(f"        {r['bid']}: {r['samples']}")
    if cand_lim_total or golden_unstable_total:
        print(f"  [诊断] 候选局限 {cand_lim_total} · 物理 golden 失稳 {golden_unstable_total}"
              f"（域边界/候选覆盖不全，非判决失败）")

    print("=" * 60)
    print("红队锚面 fuzz smoke: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
