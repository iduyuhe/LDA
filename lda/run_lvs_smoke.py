"""v0.8.24+ LVS 签核 smoke：版图-原理图一致性检查（签核级 · 版图差距 #5/#6）。

验证 `lda_l2.lvs`（单层 + 多层 v0.8.25）：
  1. 正例：一致版图 → ACCEPT（器件/网络全匹配、零违规）
  2. 反例-断路：删布线 → REJECT（open 检出）
  3. 反例-错连：布线互换 → REJECT（misconnect 检出）
  4. 反例-短路：共享端口 → REJECT（short_port 检出）
  5. 反例-悬空：端点无归属 → REJECT（dangling + open 检出）
  6. 几何恢复独立性：版图网表从布线几何恢复（不读原理图声明）
  7. 集成：chip_layout_export 返回 lvs_report；tapeout S4 一致 ACCEPT /
     错连 REJECT（SKIP 不阻断旧接口）
  8. S9 锚：golden_value 正例 1.0 / 反例 0.0；BENCHMARK_ORDER 46 题
  8b. 多层 LVS（v0.8.25 S10 锚）：层栈 can_cross 谓词 / 跨层 via 正例
      ACCEPT / 同层交叉·通孔短路·端口共享·悬空四反例 REJECT / 题库 44
  9. 红线：判决函数源码零 LLM（import 断言）

全部死标量（坐标几何 + 集合比对），LLM 不进判决路径。
运行：python run_lvs_smoke.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.benchmarks import BENCHMARK_ORDER
from lda_harness.golden import golden_value
from lda_harness.lvs_anchor import build_lvs_case, s9_report
from lda_l2.lvs import extract_layout_netlist, run_lvs

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
    print("LVS 签核 smoke（版图-原理图一致性 · 签核级）")

    # ① 正例：一致版图 ACCEPT
    link, placement, routes = build_lvs_case("consistent")
    r = run_lvs(link, placement, routes)
    check("正例：一致版图 ACCEPT（零违规）",
          r["verdict"] == "ACCEPT" and r["n_violations"] == 0,
          f"{r['verdict']} viol={r['n_violations']}")
    m = r["match"]
    check("正例：器件 3/3 匹配 · 网络 2/2 一致",
          m["n_devices_match"] == 3 and m["n_nets_match"] == 2
          and m["n_nets_total"] == 2,
          f"dev={m['n_devices_match']} net={m['n_nets_match']}/{m['n_nets_total']}")

    # ② 反例-断路
    link2, p2, routes2 = build_lvs_case("open")
    r2 = run_lvs(link2, p2, routes2)
    check("反例-断路：REJECT 且 open 检出",
          r2["verdict"] == "REJECT" and "open" in r2["violations"],
          f"open={r2['violations'].get('open')}")

    # ③ 反例-错连
    link3, p3, routes3 = build_lvs_case("misconnect")
    r3 = run_lvs(link3, p3, routes3)
    check("反例-错连：REJECT 且 misconnect 检出（两网均失配）",
          r3["verdict"] == "REJECT"
          and len(r3["violations"].get("misconnect", [])) == 2,
          f"misconnect={r3['violations'].get('misconnect')}")

    # ④ 反例-短路
    link4, p4, routes4 = build_lvs_case("short")
    r4 = run_lvs(link4, p4, routes4)
    check("反例-短路：REJECT 且 short_port 检出（端口被多网共享）",
          r4["verdict"] == "REJECT"
          and "short_port" in r4["violations"],
          f"short_port={r4['violations'].get('short_port')}")

    # ⑤ 反例-悬空
    link5, p5, routes5 = build_lvs_case("dangling")
    r5 = run_lvs(link5, p5, routes5)
    check("反例-悬空：REJECT 且 dangling 检出",
          r5["verdict"] == "REJECT"
          and "dangling" in r5["violations"],
          f"dangling={r5['violations'].get('dangling')}")

    # ⑥ 几何恢复独立性：版图网表从几何恢复（net_a 两端 = wg0.out / ring0.in）
    lay = extract_layout_netlist(link, placement, routes)
    net_a = lay["nets"].get("net_a", [])
    check("几何恢复：net_a 从布线端点恢复为 [ring0.in, wg0.out]",
          net_a == ["ring0.in", "wg0.out"], f"net_a={net_a}")
    check("几何恢复：net_b 恢复为 [ring0.drop, wg1.in]",
          lay["nets"].get("net_b") == ["ring0.drop", "wg1.in"],
          f"net_b={lay['nets'].get('net_b')}")

    # ⑦ 集成：chip_layout_export 返回 lvs_report
    from lda_l2.chip_layout_export import export_chip_gds
    cx = export_chip_gds(link, placement, routes)
    check("集成：export_chip_gds 返回 lvs_report ACCEPT",
          cx.get("lvs_report", {}).get("verdict") == "ACCEPT",
          f"verdict={cx.get('lvs_report', {}).get('verdict')}")

    # ⑦b 集成：tapeout S4（一致 ACCEPT / 错连 REJECT / SKIP 不阻断旧接口）
    from lda_pdk.tapeout_pipeline import run_tapeout_pipeline
    t1 = run_tapeout_pipeline({"RingAddDrop": {"R": 10.0, "gap": 0.3}},
                              link=link, placement=placement, routes=routes)
    check("集成：tapeout S4 一致版图 → LVS ACCEPT 且 accepted",
          t1.lvs_result.get("verdict") == "ACCEPT" and t1.accepted)
    t2 = run_tapeout_pipeline({"RingAddDrop": {"R": 10.0, "gap": 0.3}},
                              link=link3, placement=p3, routes=routes3)
    check("集成：tapeout S4 错连版图 → LVS REJECT 且不 accepted",
          t2.lvs_result.get("verdict") == "REJECT" and not t2.accepted)
    t0 = run_tapeout_pipeline({"RingAddDrop": {"R": 10.0, "gap": 0.3}})
    check("集成：tapeout 无版图输入 → LVS SKIP 不阻断（诚实标注）",
          t0.lvs_result.get("verdict") == "SKIP" and t0.accepted,
          f"verdict={t0.lvs_result.get('verdict')}")

    # ⑧ S9 锚：正例 1.0 / 反例 0.0 / 题库 43
    check("S9 锚：consistent=1.0（ACCEPT）",
          golden_value("S9", {"case": "consistent"}) == 1.0)
    check("S9 锚：open/misconnect/short/dangling 均 =0.0（REJECT）",
          all(golden_value("S9", {"case": c}) == 0.0
              for c in ("open", "misconnect", "short", "dangling")))
    check("S9 锚：题库 45 → 46 题（B27+E7+S9+S10+S11+S12）",
          "S9" in BENCHMARK_ORDER and len(BENCHMARK_ORDER) == 46,
          f"n={len(BENCHMARK_ORDER)}")
    s9r = s9_report()
    check("S9 锚：全案例判决自洽（仅 consistent 判 ACCEPT）",
          s9r["all_consistent_accepted"])

    # ⑧b 多层 LVS（v0.8.25 · S10 锚 · 版图差距 #6）
    from lda_harness.lvs_anchor import (build_multilayer_case, s10_report,
                                        s10_lvs_multilayer_verdict)
    from lda_l2.layers import get_stack
    from lda_l2.lvs import run_lvs_multilayer
    mstack = get_stack("soi")
    check("多层：can_cross 谓词（同层可短 M1∩M1 / 跨层介质隔离 M1×M2）",
          mstack.can_cross("M1", "M1") and not mstack.can_cross("M1", "M2")
          and not mstack.can_cross("M2", "M1"))
    mlink, mpl, mroutes = build_multilayer_case("consistent")
    mr = run_lvs_multilayer(mlink, mpl, mroutes, stack=mstack)
    check("多层正例：跨层 via 布线 ACCEPT（M1 段+via+M2 段，零违规）",
          mr["verdict"] == "ACCEPT" and mr["n_violations"] == 0,
          f"{mr['verdict']} viol={mr['n_violations']}")
    check("多层正例：mode=multilayer 且层栈 SOI",
          mr.get("mode") == "multilayer"
          and "M2" in mr.get("stack", {}).get("signal_layers", []),
          f"stack={mr.get('stack', {}).get('name')}")
    # 多层四类反例
    multi_cases = {"cross_short": "short_cross", "via_short": "short_via",
                   "port_short": "short_port", "dangling": "dangling"}
    for mc, expect_viol in multi_cases.items():
        l2, p2, rt2 = build_multilayer_case(mc)
        rr2 = run_lvs_multilayer(l2, p2, rt2, stack=mstack)
        check(f"多层反例-{mc}：REJECT 且 {expect_viol} 检出",
              rr2["verdict"] == "REJECT" and expect_viol in rr2["violations"],
              f"kinds={sorted(rr2['violations'].keys())}")
    # S10 锚：golden_value 经 harness
    check("S10 锚：consistent=1.0 / 四反例 0.0（经 golden_value）",
          golden_value("S10", {"case": "consistent"}) == 1.0
          and all(golden_value("S10", {"case": c}) == 0.0
                  for c in ("cross_short", "via_short", "port_short",
                            "dangling")))
    check("S10 锚：题库 45 → 46 题（B27+E7+S9+S10+S11+S12）",
          "S10" in BENCHMARK_ORDER and len(BENCHMARK_ORDER) == 46,
          f"n={len(BENCHMARK_ORDER)}")
    s10r = s10_report()
    check("S10 锚：全案例判决自洽 + 层栈信息",
          s10r["all_consistent_accepted"]
          and s10r.get("stack", {}).get("name", "").startswith("SOI"),
          f"stack={s10r.get('stack', {}).get('name')}")

    # ⑨ 红线：判决路径零 LLM（run_lvs / extract_layout_netlist 源码零 LLM import）
    import inspect
    from lda_l2 import lvs as lvs_mod
    src = inspect.getsource(lvs_mod)
    llm_hits = [k for k in ("openai", "anthropic", "ollama", "transformers",
                            "requests.post") if k in src]
    check("红线：lvs.py 源码零 LLM 引用（判决全死标量）",
          not llm_hits, f"hits={llm_hits}")

    print(f"\nLVS 签核 smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
