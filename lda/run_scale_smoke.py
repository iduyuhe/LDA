"""v0.8.26 千器件规模扩展 smoke（版图差距 #7 收官 · S11 规模锚）。

验证 `lda_harness/scale_anchor`（千器件链式 + 多层跨行跳线）：
  1. 千器件全链路（构建 1000 器件/999 net + 2D 放置 + 多层布线 + LVS 签核）
     → ACCEPT（0 违规，器件/网络全匹配）
  2. 反例-断路：删 net_500 布线 → REJECT（open 检出）
  3. 反例-错连：互换 net_500/501 布线 → REJECT（misconnect 检出）
  4. 性能预算：全链路 ≤ 5s（bbox 预检后实测 ~0.9s，死标量）
  5. 多层协同：跨行跳线走 M2 层（M2 段数 > 0，与 S10 协同验证）
  6. S11 锚：golden_value 正例 1.0 / 反例 0.0；BENCHMARK_ORDER 45 题
  7. 红线：判决源码零 LLM（scale_anchor/lvs import 断言）

全部死标量（坐标几何 + 集合比对 + 性能预算），LLM 不进判决路径。
运行：python run_scale_smoke.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.benchmarks import BENCHMARK_ORDER
from lda_harness.golden import golden_value
from lda_harness.scale_anchor import (BUDGET_SEC, DEFAULT_N_DEVICES,
                                      SCALE_CASES, run_scale_pipeline,
                                      s11_large_scale_verdict, s11_report)

_PASS = 0
_FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    mark = "PASS" if cond else "FAIL"
    if cond:
        _PASS += 1
    else:
        _FAIL += 1
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))


def main() -> int:
    print(f"千器件规模扩展 smoke（S11 · n={DEFAULT_N_DEVICES}）")

    # ① 千器件正例：全链路 ACCEPT
    r = run_scale_pipeline(n_devices=DEFAULT_N_DEVICES, case="consistent")
    check("千器件正例：全链路 ACCEPT（零违规）",
          r["verdict"] == "ACCEPT" and r["n_violations"] == 0,
          f"{r['verdict']} viol={r['n_violations']}")
    m = r["match"]
    check("千器件正例：器件 1000/1000 · 网络 999/999 全匹配",
          m["n_devices_match"] == DEFAULT_N_DEVICES
          and m["n_nets_match"] == m["n_nets_total"] == 999,
          f"dev={m['n_devices_match']} net={m['n_nets_match']}/{m['n_nets_total']}")
    check("千器件正例：n_devices/n_nets 报告正确",
          r["n_devices"] == DEFAULT_N_DEVICES and r["n_nets"] == 999,
          f"dev={r['n_devices']} net={r['n_nets']}")

    # ② 反例-断路
    r2 = run_scale_pipeline(case="disconnect")
    check("反例-断路：REJECT 且 open 检出（局部断连被千网表 LVS 抓住）",
          r2["verdict"] == "REJECT" and "open" in r2["violations"],
          f"kinds={sorted(r2['violations'].keys())}")

    # ③ 反例-错连
    r3 = run_scale_pipeline(case="misroute")
    check("反例-错连：REJECT 且 misconnect 检出",
          r3["verdict"] == "REJECT" and "misconnect" in r3["violations"],
          f"kinds={sorted(r3['violations'].keys())}")

    # ④ 性能预算（死标量：千器件全链路 ≤ 5s）
    check(f"性能预算：千器件全链路 ≤ {BUDGET_SEC}s",
          r["within_budget"] and r["time_total_s"] <= BUDGET_SEC,
          f"{r['time_total_s']}s（构建 {r['time_build_s']}s + LVS {r['time_lvs_s']}s）")
    check("性能预算：LVS 千器件 ≤ 3s（bbox 预检优化）",
          r["time_lvs_s"] <= 3.0, f"{r['time_lvs_s']}s")

    # ④b v0.8.39 规模纵深：4k 全链近线性（LVS O(n²)→网格后斜率 <3×/翻倍）
    #    证明 LVS 不再卡规模；4k 在预算内（旧实现 14.65s 超预算，新 0.07s）
    r4k = run_scale_pipeline(n_devices=4000, case="consistent")
    check("4k 规模纵深：全链 ACCEPT 且在 5s 预算内",
          r4k["verdict"] == "ACCEPT" and r4k["time_total_s"] <= BUDGET_SEC,
          f"{r4k['verdict']} {r4k['time_total_s']}s")
    check("4k 规模纵深：LVS 近线性（4k ≤ 1s，旧实现 14.4s）",
          r4k["time_lvs_s"] <= 1.0, f"LVS {r4k['time_lvs_s']}s")
    check("4k 规模纵深：缩放斜率近线性（4k/1k ≤ 8×，理想 4×）",
          r4k["time_total_s"] <= 8.0 * r["time_total_s"],
          f"{r4k['time_total_s']:.2f}s vs 1k {r['time_total_s']:.2f}s")

    # ⑤ 多层协同：跨行跳线走 M2 层
    from lda_harness.scale_anchor import build_chain_case
    link, placement, routes = build_chain_case(n_devices=200, cols=32)
    n_m2 = sum(1 for segs in routes.values()
               for seg in segs if getattr(seg, "layer", "M1") == "M2")
    # 跨行跳线数 = i%32==31 的 net 数（i=31,63,...,≤n-2）
    n_jump = (1 + (200 - 2 - 31) // 32) if 200 >= 33 else 0
    check("多层协同：跨行跳线走 M2 层（M2 段 = 跳线数）",
          n_m2 == n_jump, f"M2 段 {n_m2} == 跳线 {n_jump}")

    # ⑥ S11 锚：golden_value + 题库 45
    check("S11 锚：consistent=1.0（千器件 ACCEPT）",
          golden_value("S11", {"case": "consistent"}) == 1.0)
    check("S11 锚：disconnect/misroute =0.0（REJECT）",
          all(golden_value("S11", {"case": c}) == 0.0
              for c in ("disconnect", "misroute")))
    check("S11 锚：题库 44 → 45 题（B27+E7+S11）",
          "S11" in BENCHMARK_ORDER and len(BENCHMARK_ORDER) == 45,
          f"n={len(BENCHMARK_ORDER)}")
    rep = s11_report()
    check("S11 锚：全案例判决自洽 + 性能预算达标",
          rep["all_consistent_accepted"] and rep["within_budget"],
          f"budget={rep['within_budget']}")

    # ⑦ 红线：判决源码零 LLM
    import inspect
    from lda_harness import scale_anchor as sa_mod
    src = inspect.getsource(sa_mod)
    llm_hits = [k for k in ("openai", "anthropic", "ollama", "transformers",
                            "requests.post") if k in src]
    check("红线：scale_anchor.py 源码零 LLM 引用",
          not llm_hits, f"hits={llm_hits}")

    print(f"\n千器件规模扩展 smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
