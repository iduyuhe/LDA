#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BL 征程 · **BL-M0** 盲区锚判据有效性体检（**生成器** · 确定性 · 受跟踪台账）。

================================================================================
为什么要有这个台账
================================================================================
K4 的 L2 覆盖率是**文本代理**（门禁源码里出现锚号即算覆盖）⇒ 刷它等于指标游戏。
BL 征程的真命题是**判据的判别力**：这条锚的判据能不能区分「对」与「错」。

本生成器对**全部 strict 盲区锚**逐条**现算**：
  `golden = oracle_fn(params)` · `candidate = cand_map[bid](spec, golden)` ·
  `err = compare_fn(candidate, golden)`（本仓返回**误差值**，判 PASS 须 `err ≤ tol`）
并记录四类缺陷标志：

  ① `zero_resid`        —— `resid == 0.0`（与自证桩 `|Δ|≡0` 不可区分 ⇒ 判据 D 判假独立）
  ② `loose`             —— `|golden|/tol < 10`（B-14 血案门限：锚太松 ⇒ 判别力不足）
  ③ `tight`             —— `resid/tol > 0.5`（余量不足 2×）
  ④ `cancellation_suspect` —— `|golden| ∈ (0.9,1.1)` ∧ `resid/tol < 1e-9`（相消嫌疑）
  ⑤ `zero_injection_passes` —— **把 candidate 强注为 0 仍判 PASS**（判据**结构性失效**）
       🔴 仅对 `cmp_abs` 锚计算；`cmp_le/cmp_ge`（不等式锚，本仓仅 `B19`）**不适用**，
       因为「0」对单侧约束本就是合法值。

🔴 **不读 `verification_report.json`**：该报告把 float 舍入到 6 位，实测 86 条「零残差」中
   只有 19 条是真的（67 条是舍入假零）。**残差审计必须现算。**

确定性
------
零时间戳 / 零随机 / 零进程依赖（不读系统时钟，也不用伪随机与临时目录）；行按锚号稳定排序；
**线程数强制钉死 10**（见下方模块级 `os.environ` 赋值：否则多线程/单线程环境下部分锚的
`resid` 在第 7–9 位有效数字上不同 ⇒ 逐字节对拍永远红）；写盘走 `det.write_text`
（UTF-8 + LF，**不做 canon 截断**，保全 float 全精度）。
浮点**一律量化到 10 位有效数字**（`_q()`，保指数）后再落盘 —— 因 `E10` 的半矢量本征模求解
走 ARPACK 随机初始向量，末位有 ~1e-13 漂移；量化后快照可逐字节复现，而**判决仍用原值**。

用法
----
    python scripts/bl_audit.py --write     # 生成/更新受跟踪台账
    python scripts/bl_audit.py             # 只打印（stdout 与磁盘应逐字节一致）
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# ===========================================================================
# 🔴 线程数**钉死**（可复现性前置条件 · 必须先于 numpy / lda_harness 导入）
# ===========================================================================
# 实测（v0.9.251 首轮全量 CI 当场抓出）：同一台账在 **10 线程** 与 **默认（多线程）**
# 环境下，`B15/B40/B106–B110/B154–B156/B237/B238/B454` 等锚的 `resid` 在第 **7–9 位**
# 有效数字上不同（BLAS 归约顺序差异 ⇒ 迭代求解器末位漂移 ~1e-9 相对），而 `_q()` 只
# 量化到 **10 位** ⇒ 两者**量化后仍然不同** ⇒ 门禁 A1「子进程重跑 ≡ 磁盘（逐字节）」必红。
# 这不是量化位数不够，而是**输入环境未钉死**。
# ⇒ 此处**强制赋值**（不用 `setdefault`：`setdefault` 只在未设置时生效 ⇒ 命令行的单线程
#    或 4 线程环境会穿透过，钉不住），令台账与调用方环境**无关**。钉死后实测两次运行
#    byte-identical（10 线程 × 173 s × 2 次）。
# 🔴 门禁 `run_bl_anchor_guard_smoke.py` 的 **E5** 判据锁死本段（删掉即红）。
for _k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
           "OPENBLAS_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ[_k] = "10"
os.environ["LDA_FDTD_THREADS"] = "10"

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_LDA = os.path.join(_ROOT, "lda")
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

from lda_harness import verification_adapters as _va  # noqa: E402,F401  —— 必须先 import 触发全分片注册
from lda_harness.benchmarks import BENCHMARK_DEFS  # noqa: E402
from lda_harness import deterministic as det  # noqa: E402

SCHEMA = "lda_bl_anchor_audit_v1"
COV_REL = "lda/reports/anchor_gate_coverage.json"
OUT_REL = "lda/reports/bl_anchor_audit.json"

# —— 阈值（与 BL 章程 §1.2 一致，改动须同步章程与门禁）——
LOOSE_MIN_RATIO = 10.0      # |golden|/tol 应 ≥ 10
TIGHT_MAX_RATIO = 0.5       # resid/tol 应 ≤ 0.5
CANCEL_BAND = (0.9, 1.1)    # |golden| 落在 1 附近的相消高危带
CANCEL_MAX_RATIO = 1e-9     # 且 resid/tol 极小


def _q(v):
    """台账收录用的**定点量化**（10 位有效数字 · 保指数）。

    🔴 为什么需要：`E10` 的候选走半矢量本征模求解（**ARPACK 随机初始向量**）⇒ 同一输入两次运行
    的末位不同（实测 `8.912818475376941` / `8.912818475377131`，相对漂移 ~1e-13）。
    这属求解器固有，不是本行程能改的产品面；若原样落盘，台账**永远无法逐字节复现**。
    **量化位数由实测反推：10 位有效数字**。12 位不够 —— 实测 `B355/B356`（Bernstein 数值核）
    与 `E10` 的漂移达 ~1.5e-12 相对（第 12 位就会变），10 位才稳定。
    10 位远高于任何 tol（最小 tol=1e-9）⇒ 不损害判别力；**判决仍用未量化的原值**
    （`compare_fn` 在量化之前算），量化只作用于「快照收录」。
    """
    if v is None:
        return None
    return float("%.10g" % float(v))


def _p(rel: str) -> str:
    return os.path.join(_ROOT, rel)


def _sort_key(bid: str):
    """稳定排序：B 系列按数值，其余按字典序（E/S 等）。"""
    if bid.startswith("B") and bid[1:].isdigit():
        return (0, int(bid[1:]), "")
    return (1, 0, bid)


def build() -> dict:
    """现算全部 strict 盲区锚，返回台账 payload（纯函数 · 无副作用）。"""
    with open(_p(COV_REL), encoding="utf-8") as f:
        cov = json.load(f)
    blind = sorted(set(cov["blind_anchors"]), key=_sort_key)

    specs, cand_map = _va.build_harness_specs()
    by_id = {s.spec_id: s for s in specs}

    strict = [a for a in blind if BENCHMARK_DEFS.get(a, {}).get("candidate")]
    non_anchorable = [a for a in blind if a not in set(strict)]

    rows = []
    for a in strict:
        s = by_id[a]
        g = float(s.oracle_fn(s.params))
        c = float(cand_map[a](s, g))
        tol = float(s.tol)
        kind = getattr(s.compare_fn, "__name__", "?")
        err = float(s.compare_fn(c, g))
        resid = abs(c - g)
        # 🔴 不等式锚（cmp_le/cmp_ge）的「余量/松紧」比值**无意义**（单侧约束，0 是合法值）
        #   ⇒ 只对 cmp_abs 计算 rt/gl，其余置 None，避免把 B19 误记为「余量不足」。
        _abs_kind = (kind == "cmp_abs")
        rt = (resid / tol) if (tol > 0 and _abs_kind) else None
        gl = (abs(g) / tol) if (tol > 0 and _abs_kind) else None

        z_err = None
        z_pass = None
        if _abs_kind:
            z_err = float(s.compare_fn(0.0, g))
            z_pass = bool(z_err <= tol)

        rows.append({
            "id": a,
            "title": str(BENCHMARK_DEFS[a].get("title", ""))[:90],
            "metric": str(BENCHMARK_DEFS[a].get("metric", "")),
            "compare": kind,
            "tol": tol,
            "golden": _q(g),
            "candidate": _q(c),
            "resid": _q(resid),
            "resid_over_tol": _q(rt),
            "golden_over_tol": _q(gl),
            "zero_injection_err": _q(z_err),
            "zero_injection_passes": z_pass,
            "passes": bool(err <= tol),
            "flags": {
                "zero_resid": resid == 0.0,
                "loose": (gl is not None and gl < LOOSE_MIN_RATIO),
                "tight": (rt is not None and rt > TIGHT_MAX_RATIO),
                "cancellation_suspect": (
                    gl is not None and rt is not None
                    and CANCEL_BAND[0] < abs(g) < CANCEL_BAND[1]
                    and rt < CANCEL_MAX_RATIO),
                "zero_injection_passes": bool(z_pass),
            },
        })

    def _ids(flag: str):
        return [r["id"] for r in rows if r["flags"][flag]]

    n_total_anchors = len(BENCHMARK_DEFS)
    summary = {
        "blind_total": len(blind),
        "blind_strict": len(strict),
        "blind_non_anchorable": len(non_anchorable),
        "non_anchorable_ids": non_anchorable,
        "l2_ceiling": n_total_anchors - len(non_anchorable),
        "ledger_total": n_total_anchors,
        "n_zero_resid": len(_ids("zero_resid")),
        "n_loose": len(_ids("loose")),
        "n_tight": len(_ids("tight")),
        "n_cancellation_suspect": len(_ids("cancellation_suspect")),
        "n_zero_injection_passes": len(_ids("zero_injection_passes")),
        "zero_resid_ids": _ids("zero_resid"),
        "loose_ids": _ids("loose"),
        "tight_ids": _ids("tight"),
        "cancellation_suspect_ids": _ids("cancellation_suspect"),
        "zero_injection_passes_ids": _ids("zero_injection_passes"),
        "n_fail_verdict": sum(1 for r in rows if not r["passes"]),
    }

    return {
        "schema": SCHEMA,
        "generated_by": "scripts/bl_audit.py",
        "roadmap": "BL（盲区判据有效性补强）",
        "subject": "K4 盲区锚的判据判别力（现算 · 不读 verification_report）",
        "method": ("逐锚现算 golden/candidate/err；判 PASS 走 compare_fn 的误差值 ≤ tol；"
                   "注入探针把 candidate 强注为 0，仅对 cmp_abs 适用"),
        "thresholds": {
            "loose_min_ratio": LOOSE_MIN_RATIO,
            "tight_max_ratio": TIGHT_MAX_RATIO,
            "cancellation_band": list(CANCEL_BAND),
            "cancellation_max_ratio": CANCEL_MAX_RATIO,
        },
        "summary": summary,
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="写入受跟踪台账")
    args = ap.parse_args()

    payload = build()
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1)
    if args.write:
        det.write_text(_p(OUT_REL), text)
        s = payload["summary"]
        print("[written] %s（盲区 %d = strict %d + 不可接 %d · 零残差 %d · 偏松 %d · "
              "余量不足 %d · 相消 %d · 放行注入0 %d）"
              % (OUT_REL, s["blind_total"], s["blind_strict"], s["blind_non_anchorable"],
                 s["n_zero_resid"], s["n_loose"], s["n_tight"],
                 s["n_cancellation_suspect"], s["n_zero_injection_passes"]))
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
