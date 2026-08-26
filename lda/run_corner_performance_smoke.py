"""Merge-1b 性能漂移角扫 smoke（v0.8.13 · ⑥审计落地）。

覆盖（防自证门禁）：
  ① 光子角：RingResonator(FSR) SS/TT/FF 漂移带 + 单调物理方向（SS R 小→FSR 大）
  ② 量子角：Transmon(f01) Q-SS/Q-TT/Q-FF 漂移带（域定义，无 SS/TT/FF 惯例混用）
  ③ 死标量判决：漂移 > tol → FAIL 被抓（防自证）
  ④ 无映射 bid → 显式报错不静默（防漏登记）
  ⑤ 诚实边界 note

红线：性能值=golden 正算（确定性），判决=漂移带 vs tol 死标量，LLM 不进。
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from lda_harness.benchmarks import BENCHMARK_DEFS  # noqa: E402
from lda_pdk.corner_performance import (  # noqa: E402
    corner_scan_case,
    corner_scan_report,
)

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    tag = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"[{tag}] {name}" + (f" —— {detail}" if detail else ""))


def main() -> int:
    # ① 光子角：RingResonator FSR（B4 参数 R=10/n_g=4.18）
    r = corner_scan_case("RingResonator", "B4",
                         dict(BENCHMARK_DEFS["B4"]["default_params"]),
                         tol_pct=15.0, domain="photon")
    check("光子角 Ring FSR 三角落扫描完成", r["passed"] and len(r["corners"]) == 3,
          r["note"])
    fsr_ss, fsr_tt, fsr_ff = (r["corners"]["SS"]["value"],
                              r["corners"]["TT"]["value"],
                              r["corners"]["FF"]["value"])
    # 物理方向：R 缩放 SS=0.95 → R 小 → FSR=λ²/(2πRn_g) 大；FF=1.05 → FSR 小
    check("光子角物理方向（SS R 小→FSR 大 > TT > FF）",
          fsr_ss > fsr_tt > fsr_ff,
          f"SS={fsr_ss} TT={fsr_tt} FF={fsr_ff}")

    # ② 量子角：Transmon f01（B9 参数 EJ=20/EC=0.3）
    q = corner_scan_case("Transmon", "B9",
                         dict(BENCHMARK_DEFS["B9"]["default_params"]),
                         tol_pct=5.0, domain="quantum")
    check("量子角 Transmon f01 三角落（Q-SS/TT/FF）",
          q["passed"] and len(q["corners"]) == 3, q["note"])
    check("量子角域定义（键名 Q-* 非 SS/TT/FF 混用）",
          set(q["corners"].keys()) == {"Q-SS", "Q-TT", "Q-FF"},
          f"keys={list(q['corners'].keys())}")

    # ③ 死标量判决：收紧 tol 到 0.01% → 漂移必超 → FAIL 被抓
    strict = corner_scan_case("RingResonator", "B4",
                              dict(BENCHMARK_DEFS["B4"]["default_params"]),
                              tol_pct=0.01, domain="photon")
    check("收紧 tol → 角漂移被抓 FAIL（死标量判决）",
          (not strict["passed"]) and strict["max_drift_pct"] > 0.01,
          f"max_drift={strict['max_drift_pct']}% vs tol=0.01%")

    # ④ 未登记 bid → 显式报错不静默
    unknown = corner_scan_case("XX", "B99", {"x": 1.0}, tol_pct=10.0)
    check("未登记 bid 显式报错（不静默）",
          (not unknown["passed"]) and "error" in unknown,
          unknown.get("error", "?")[:50])

    # ⑤ 批量报告 + 诚实边界
    rep = corner_scan_report([
        {"device": "RingResonator", "bid": "B4",
         "params": dict(BENCHMARK_DEFS["B4"]["default_params"]),
         "tol_pct": 15.0, "domain": "photon"},
        {"device": "Transmon", "bid": "B9",
         "params": dict(BENCHMARK_DEFS["B9"]["default_params"]),
         "tol_pct": 5.0, "domain": "quantum"},
        {"device": "MziInterferometer", "bid": "B20",
         "params": dict(BENCHMARK_DEFS["B20"]["default_params"]),
         "tol_pct": 15.0, "domain": "photon"},
    ])
    check("批量角扫 3/3 PASS", rep["all_pass"] and rep["n_pass"] == 3,
          f"{rep['n_pass']}/{rep['n_cases']}")
    check("诚实边界 note", "非真实 PDK" in rep["honest_note"],
          rep["honest_note"][:30])

    print(f"\n汇总：{PASS} PASS / {FAIL} FAIL")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
