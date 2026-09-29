"""超导耦合 transmon 对 门禁 smoke（D-134 · S2 · 几何 DRC/LVS + 物理签核）。

═══ 为什么要有这个 smoke ═══
D-134 把平台「能设计超导芯片」从单比特（S1·D-133）推进到**多比特耦合对**。
这类「新增多比特版图原语 + 多网连通 LVS + 物理签核」半年后最易被悄悄降级
（例如把耦合器桥接检查删掉、把 J 双验证容差改松、把 CR 验收窗放宽），必须
钉成常驻断言：

  ① **合法耦合对 DRC/LVS 双 ACCEPT**（默认参数）
  ② **DRC 各规则可触发 REJECT**（耦合器太薄 / 地短接 / 地间隙过小 / JJ 太薄）
  ③ **LVS 多网连通可触发 REJECT**（缺耦合器分列 / JJ 不桥接 / 地短接 / 无 net）
  ④ **诚实标注 + 红线**（限值为设计规则 · 零量子 SDK · 判决死标量）
  ⑤ **GDS round-trip**（真出 GDS → parse_gds 读回含 SC 层 10/11/12）
  ⑥ **跨模块物理双验证**（coupler_solver 严格 J ↔ 解析 J；cross_resonance 有效
     ZX/ZZ 落 ORACLE 验收窗）

运行：python run_schip_s2_smoke.py（cwd=lda/）
出口：全 PASS 退 0；任一 FAIL 退 1。LLM 不进判决路径。
"""
from __future__ import annotations

import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))       # = …/lda
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_qeda import sc_coupler as S2                              # noqa: E402
from lda_qeda import sc_layout as SCD                              # noqa: E402
from lda_harness.smoke_kit import make_check                       # noqa: E402

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=" | {d}", return_ok=True)


def main() -> int:
    print("=" * 78)
    print("超导耦合 transmon 对 门禁 smoke（D-134 · S2 · 几何 DRC/LVS + 物理签核）")
    print("=" * 78)

    # ════════════════ A 节：模块自检 ════════════════
    print("── A 模块自检 ──")
    try:
        ok_a = S2.run_selfchecks(verbose=False)
    except Exception as e:                                       # noqa: BLE001
        ok_a = False
        print(f"  run_selfchecks 异常：{type(e).__name__}: {e}")
    check("A1 D-134 模块自检 7/7 PASS（合法 ACCEPT×2 · 四类违规各 REJECT · 物理 ACCEPT）",
          ok_a, "合法双 ACCEPT + 缺耦合器/耦合器薄/地短接/物理各 REJECT")

    # ════════════════ B 节：DRC 规则可触发 ════════════════
    print("── B 超导耦合对 DRC 规则 ──")
    base = S2.coupled_pair_cell({})
    check("B1 合法耦合对 DRC ACCEPT（4 规则全过）",
          S2.run_sc_pair_drc(base)["verdict"] == "ACCEPT",
          f"verdict={S2.run_sc_pair_drc(base)['verdict']}")
    thin = S2.coupled_pair_cell({"coupler_cw": 0.05})
    vt = S2.run_sc_pair_drc(thin)
    check("B2 耦合器太薄(高0.1<0.2) ⇒ DRC REJECT（SCD-MIN-WIDTH）",
          vt["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-MIN-WIDTH" for v in vt["violations"]),
          f"violations={[v['rule'] for v in vt['violations']]}")
    short = S2.coupled_pair_cell({"ground_gap": -0.5})
    vs = S2.run_sc_pair_drc(short)
    check("B3 地与 qubit 短接(ground_gap<0) ⇒ DRC REJECT（SCD-QUBIT-GROUND-SHORT）",
          vs["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-QUBIT-GROUND-SHORT" for v in vs["violations"]),
          f"violations={[v['rule'] for v in vs['violations']]}")
    smallgap = S2.coupled_pair_cell({"ground_gap": 0.1})
    vg = S2.run_sc_pair_drc(smallgap)
    check("B4 地间隙 0.1<0.5 ⇒ DRC REJECT（SCD-MIN-GROUND-GAP）",
          vg["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-MIN-GROUND-GAP" for v in vg["violations"]),
          f"violations={[v['rule'] for v in vg['violations']]}")
    badjj = SCD.transmon_cell({"jj_len": 0.1})
    vj = SCD.run_sc_drc(badjj)
    check("B5 单 qubit JJ 太薄(0.1<0.15) ⇒ DRC REJECT（SCD-MIN-JJ）",
          vj["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-MIN-JJ" for v in vj["violations"]),
          f"violations={[v['rule'] for v in vj['violations']]}")
    check("B6 规则名 / n_rules 稳定（SCD_RULES=4 条 · n_rules=4）",
          len(S2.PAIR_DRC_RULES) == 4 and S2.run_sc_pair_drc(base)["n_rules"] == 4,
          f"SCD_RULES={len(S2.PAIR_DRC_RULES)}")

    # ════════════════ C 节：LVS 多网连通可触发 ════════════════
    print("── C 超导耦合对 LVS 多网连通 ──")
    check("C1 合法耦合对 LVS ACCEPT（qubit+耦合器单连通分量 · JJ 桥接）",
          S2.sc_pair_lvs_signoff(base)["verdict"] == "ACCEPT",
          f"netlist={S2.sc_pair_lvs_signoff(base)['netlist']}")
    no_coup = [d for d in base if d.get("net") != "coupler"]
    vnc = S2.sc_pair_lvs_signoff(no_coup)
    check("C2 缺耦合器 ⇒ LVS REJECT（COUPLER-NOT-BRIDGING / FLOATING 分量）",
          vnc["verdict"] == "REJECT"
          and any(("COUPLER" in i) or ("FLOATING" in i) for i in vnc["issues"]),
          f"issues={vnc['issues']}")
    bad_jj = SCD.transmon_cell({"jj_len": 0.1})
    vbj = SCD.sc_lvs_signoff(bad_jj)
    check("C3 单 qubit JJ 不桥接 ⇒ LVS REJECT（SCD-LVS-JJ-NOT-BRIDGING）",
          vbj["verdict"] == "REJECT"
          and any("JJ-NOT-BRIDGING" in i for i in vbj["issues"]),
          f"issues={vbj['issues']}")
    vsh = S2.sc_pair_lvs_signoff(short)
    check("C4 地短接 ⇒ LVS REJECT（SCD-LVS-QUBIT-GROUND-SHORT）",
          vsh["verdict"] == "REJECT"
          and any("GROUND-SHORT" in i for i in vsh["issues"]),
          f"issues={vsh['issues']}")
    nonet = base + [{"kind": "boundary", "layer": S2.FILM,
                     "rings_um": [[(40, 40), (42, 40), (42, 42), (40, 42)]]}]
    vnn = S2.sc_pair_lvs_signoff(nonet)
    check("C5 无 net 标签导体 ⇒ LVS REJECT（SCD-LVS-NO-NET）",
          vnn["verdict"] == "REJECT"
          and any("NO-NET" in i for i in vnn["issues"]),
          f"issues={vnn['issues']}")
    check("C6 LVS n_checks=6（连通性/JJ桥接/耦合器桥接/地/端口/无net 六判据）",
          S2.sc_pair_lvs_signoff(base)["n_checks"] == 6,
          f"n_checks={S2.sc_pair_lvs_signoff(base)['n_checks']}")

    # ════════════════ D 节：诚实标注 + 红线 ════════════════
    print("── D 诚实标注 + 红线 ──")
    disc = S2.RED_LINE_DISCLOSURE
    check("D1 披露齐备：role/layers/limits/lvs/physics/red_line 五键",
          all(k in disc for k in ("role", "layers", "limits", "lvs",
                                   "physics", "red_line")),
          f"键={sorted(disc)}")
    check("D2 限值为设计规则 · 非实测 golden（明确标注 D5 外部依赖）",
          "设计规则" in disc["limits"] and "非实测 golden" in disc["limits"]
          and "D5" in disc["limits"], "默认限值为设计规则口径")
    src = open(os.path.join(_HERE, "lda_qeda", "sc_coupler.py"), encoding="utf-8").read()
    banned = ("qiskit", "cirq", "pennylane", "strawberryfields", "thewalrus", "qutip")
    hits = [b for b in banned if re.search(rf"^\s*(import|from)\s+{b}\b", src, re.M)]
    check("D3 红线：D-134 零量子 SDK 依赖（纯几何 + 平台，C 级自主）",
          not hits, f"命中={hits or '无'}")
    drc_v = S2.run_sc_pair_drc(base)
    check("D4 判决无 LLM：verdict 为 str 死标量、violation 为 dict（零模型调用）",
          drc_v["verdict"] in ("ACCEPT", "REJECT")
          and all(isinstance(v, dict) and set(v) == {"rule", "detail"}
                  for v in drc_v["violations"]),
          "rule/detail 二元组 · 纯限值比对")

    # ════════════════ E 节：GDS round-trip ════════════════
    print("── E GDS 真出 + 解析 round-trip ──")
    data = S2.coupled_pair_gds({}, os.path.join(_HERE, "_sc_s2_tmp.gds"))
    parsed = S2.G.parse_gds(data)
    layers = set()
    total_elems = 0
    for st in parsed.get("structures", {}).values():
        layers |= set(st.get("layers", []))
        total_elems += st.get("elements", 0)
    check("E1 真出 GDSII（含 SC 层 10/11/12）",
          bool(data) and {10, 11, 12}.issubset(layers),
          f"layers={sorted(layers)} · bytes={len(data)}")
    check("E2 parse_gds 读回：结构数≥1 · 元素数>0 · 含 SC 层 10/11/12",
          parsed.get("n_structures", 0) >= 1 and total_elems > 0
          and {10, 11, 12}.issubset(layers),
          f"structs={parsed.get('n_structures')} · elems={total_elems} · layers={sorted(layers)}")

    # ════════════════ F 节：跨模块物理（双验证 + CR 有效模型 + ZZ）═══════════════
    print("── F 跨模块物理（coupler_solver 严格 J ↔ 解析 J · cross_resonance 有效 ZX/ZZ）──")
    phys = S2.coupled_pair_physics({})
    check("F1 J 严格对角化 ↔ 解析闭式 双验证 rel≤5%（确定性物理定律锚）",
          phys["J_rel_err"] <= 0.05,
          f"J_num={phys['J_num_ghz']:.5f} · J_an={phys['J_analytic_ghz']:.5f} · rel={phys['J_rel_err']:.2%}")
    check("F2 CR 有效模型落窗：|g_CR|∈[0.02,10]MHz · t_CR≤T2 · 参数区 |Δ|<|α|",
          bool(phys["cr_ok"]),
          f"g_CR={phys['g_CR_mhz']:.3f}MHz · t_CR={phys['t_CR_us']:.3f}µs · "
          f"Δ={phys['detune_ghz']*1000:.1f}MHz · |α|={abs(phys['alpha_B_ghz'])*1000:.0f}MHz")
    check("F3 残余 ZZ 诚实报告（σ_zz 返回 + echoed-CR 抵消标注）",
          phys["sigma_zz_mhz"] is not None,
          f"σ_zz={phys['sigma_zz_mhz']:.3f}MHz（echoed-CR 可抵消）")
    check("F4 物理产出合理：f01_A/B∈[4,7]GHz · α<0 · 0<Δ<|α|",
          4.0 <= phys["f01_A_ghz"] <= 7.0 and 4.0 <= phys["f01_B_ghz"] <= 7.0
          and phys["alpha_B_ghz"] < 0
          and 0.0 < phys["detune_ghz"] < abs(phys["alpha_B_ghz"]),
          f"f01_A={phys['f01_A_ghz']:.3f} · f01_B={phys['f01_B_ghz']:.3f} · "
          f"α={phys['alpha_B_ghz']:.3f} · Δ={phys['detune_ghz']:.4f}")
    check("F5 耦合对物理签核 verdict=ACCEPT（J 双验证 + CR 落窗 同真）",
          phys["verdict"] == "ACCEPT",
          f"verdict={phys['verdict']} · J_double={phys['J_double_validated']} · cr_ok={phys['cr_ok']}")

    print()
    print(f"超导耦合 transmon 对 门禁 smoke（D-134）：{PASS}/{PASS + FAIL} PASS")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
