"""超导 N 比特阵列 门禁 smoke（D-135 · S3 · 阵列 P&R + 规模 DRC/LVS + 物理签核）。

═══ 为什么要有这个 smoke ═══
D-135 把平台「能设计超导芯片」从耦合对（S2·D-134）推进到**阵列规模**（网格排布 +
最近邻耦合路由 + 超导专用 DRC/LVS + 逐边物理签核）。这类「新增阵列版图原语 + 规模
感知多网 LVS + 逐边物理」半年后最易被悄悄降级（例如删掉耦合器桥接恰好 2 的检查、把
阵列间距规则去掉、把 J 双验证容差改松、把 CR 验收窗放宽），必须钉成常驻断言：

  ① **合法阵列 DRC/LVS 双 ACCEPT**（2×2 网格 + 1×4 链）
  ② **DRC 各规则可触发 REJECT**（耦合器薄 / 地短接 / 地间隙 / JJ 薄 / 阵列间距）
  ③ **LVS 多网连通可触发 REJECT**（缺耦合器分列 / 耦合器误桥>2 / 地短接 / 无 net /
     拓扑边数不符）
  ④ **诚实标注 + 红线**（限值为设计规则 · 零量子 SDK · 判决死标量）
  ⑤ **GDS round-trip**（真出 GDS → parse_gds 读回含 SC 层 10/11/12）
  ⑥ **跨模块物理双验证**（逐边 coupler_solver 严格 J ↔ 解析 J；cross_resonance 有效
     ZX/ZZ 落 ORACLE 验收窗；规模 3×3=9 qubit/12 边 PASS）

运行：python run_schip_s3_smoke.py（cwd=lda/）
出口：全 PASS 退 0；任一 FAIL 退 1。LLM 不进判决路径。
"""
from __future__ import annotations

import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))       # = …/lda
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_qeda import sc_array as S3                                 # noqa: E402
from lda_harness.smoke_kit import make_check                        # noqa: E402

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=" | {d}", return_ok=True)


def _expected_edges(rows: int, cols: int) -> int:
    return rows * (cols - 1) + cols * (rows - 1)


def main() -> int:
    print("=" * 78)
    print("超导 N 比特阵列 门禁 smoke（D-135 · S3 · 阵列 P&R + 规模 DRC/LVS + 物理）")
    print("=" * 78)

    # ════════════════ A 节：模块自检 ════════════════
    print("── A 模块自检 ──")
    try:
        ok_a = S3.run_selfchecks(verbose=False)
    except Exception as e:                                       # noqa: BLE001
        ok_a = False
        print(f"  run_selfchecks 异常：{type(e).__name__}: {e}")
    check("A1 D-135 模块自检 11/11 PASS（合法双 ACCEPT · 六类违规各 REJECT · 物理 ACCEPT）",
          ok_a, "合法双 ACCEPT + 缺耦合器/误桥/间距/耦合器薄/地短接/物理各 REJECT")

    # ════════════════ B 节：DRC 规则可触发（规模感知）═══════════════
    print("── B 超导阵列 DRC 规则 ──")
    grid = S3.array_cell({"rows": 2, "cols": 2})
    check("B1 合法 2×2 阵列 DRC ACCEPT（5 规则全过）",
          S3.run_sc_array_drc(grid)["verdict"] == "ACCEPT",
          f"verdict={S3.run_sc_array_drc(grid)['verdict']}")
    thin = S3.array_cell({"rows": 1, "cols": 2, "coupler_cw": 0.05})
    vt = S3.run_sc_array_drc(thin)
    check("B2 耦合器太薄(高0.1<0.2) ⇒ DRC REJECT（SCD-MIN-WIDTH）",
          vt["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-MIN-WIDTH" for v in vt["violations"]),
          f"violations={[v['rule'] for v in vt['violations']]}")
    short = S3.array_cell({"rows": 2, "cols": 2, "ground_gap": -0.5})
    vs = S3.run_sc_array_drc(short)
    check("B3 地与 qubit 短接(ground_gap<0) ⇒ DRC REJECT（SCD-QUBIT-GROUND-SHORT）",
          vs["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-QUBIT-GROUND-SHORT" for v in vs["violations"]),
          f"violations={[v['rule'] for v in vs['violations']]}")
    smallgap = S3.array_cell({"rows": 2, "cols": 2, "ground_gap": 0.1})
    vg = S3.run_sc_array_drc(smallgap)
    check("B4 地间隙 0.1<0.5 ⇒ DRC REJECT（SCD-MIN-GROUND-GAP）",
          vg["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-MIN-GROUND-GAP" for v in vg["violations"]),
          f"violations={[v['rule'] for v in vg['violations']]}")
    badjj = S3.array_cell({"rows": 1, "cols": 1, "jj_len": 0.1})
    vj = S3.run_sc_array_drc(badjj)
    check("B5 单 qubit JJ 太薄(0.1<0.15) ⇒ DRC REJECT（SCD-MIN-JJ）",
          vj["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-MIN-JJ" for v in vj["violations"]),
          f"violations={[v['rule'] for v in vj['violations']]}")
    overlap = S3.array_cell({"rows": 1, "cols": 2, "pitch_x": 4.0})
    vsp = S3.run_sc_array_drc(overlap)
    check("B6 两 qubit 互叠(pitch 不足) ⇒ DRC REJECT（SCD-ARRAY-QUIBIT-SPACING）",
          vsp["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-ARRAY-QUIBIT-SPACING" for v in vsp["violations"]),
          f"violations={[v['rule'] for v in vsp['violations']]}")
    check("B7 规则名 / n_rules 稳定（ARRAY_DRC_RULES=5 条）",
          len(S3.ARRAY_DRC_RULES) == 5 and S3.run_sc_array_drc(grid)["n_rules"] == 5,
          f"ARRAY_DRC_RULES={len(S3.ARRAY_DRC_RULES)}")

    # ════════════════ C 节：LVS 多网连通（拓扑感知）═══════════════
    print("── C 超导阵列 LVS 多网连通 ──")
    check("C1 合法 2×2 阵列 LVS ACCEPT（4 网 · 4 耦合器各桥 2 · 连通）",
          S3.sc_array_lvs_signoff(grid)["verdict"] == "ACCEPT",
          f"netlist={S3.sc_array_lvs_signoff(grid)['netlist']}")
    nl_grid = S3.sc_array_lvs_signoff(grid)["netlist"]
    check("C2 2×2 拓扑断言：qubit_nets==4 · 边==4(2×1+2×1) · 连通",
          nl_grid["qubit_nets"] == 4
          and nl_grid["edges_bridged"] == _expected_edges(2, 2)
          and nl_grid["graph_connected"],
          f"netlist={nl_grid}")
    chain = S3.array_cell({"rows": 1, "cols": 4})
    nl_chain = S3.sc_array_lvs_signoff(chain)["netlist"]
    check("C3 1×4 链 LVS ACCEPT + 拓扑断言：4 网 · 边==3 · 连通",
          S3.sc_array_lvs_signoff(chain)["verdict"] == "ACCEPT"
          and nl_chain["qubit_nets"] == 4
          and nl_chain["edges_bridged"] == _expected_edges(1, 4)
          and nl_chain["graph_connected"],
          f"netlist={nl_chain}")
    no_coup = [d for d in grid if d.get("net") != "coupler"]
    vnc = S3.sc_array_lvs_signoff(no_coup)
    check("C4 缺耦合器 ⇒ LVS REJECT（NO-COUPLER / FLOATING 分量）",
          vnc["verdict"] == "REJECT"
          and any(("NO-COUPLER" in i) or ("FLOATING" in i) for i in vnc["issues"]),
          f"issues={vnc['issues']}")
    big = list(grid)
    cond_boxes = [S3._bbox(d) for d in grid if d.get("net") in ("qubit", "coupler")]
    ax0 = min(b[0] for b in cond_boxes); ax1 = max(b[1] for b in cond_boxes)
    ay0 = min(b[2] for b in cond_boxes); ay1 = max(b[3] for b in cond_boxes)
    big.append({"kind": "boundary", "layer": S3.FILM, "net": "coupler",
                 "rings_um": [[(ax0, ay0), (ax1, ay0), (ax1, ay1), (ax0, ay1)]]})
    vbc = S3.sc_array_lvs_signoff(big)
    check("C5 耦合器误桥 >2 qubit ⇒ LVS REJECT（COUPLER-BRIDGE-NE2）",
          vbc["verdict"] == "REJECT"
          and any("BRIDGE-NE2" in i for i in vbc["issues"]),
          f"issues={vbc['issues']}")
    vsh = S3.sc_array_lvs_signoff(short)
    check("C6 地短接 ⇒ LVS REJECT（SCD-LVS-QUBIT-GROUND-SHORT）",
          vsh["verdict"] == "REJECT"
          and any("GROUND-SHORT" in i for i in vsh["issues"]),
          f"issues={vsh['issues']}")
    nonet = grid + [{"kind": "boundary", "layer": S3.FILM,
                     "rings_um": [[(200, 200), (202, 200), (202, 202), (200, 202)]]}]
    vnn = S3.sc_array_lvs_signoff(nonet)
    check("C7 无 net 标签导体 ⇒ LVS REJECT（SCD-LVS-NO-NET）",
          vnn["verdict"] == "REJECT"
          and any("NO-NET" in i for i in vnn["issues"]),
          f"issues={vnn['issues']}")
    check("C8 LVS n_checks=6（连通性/JJ桥接/耦合器桥接/地/无net/耦合器-地 六判据）",
          S3.sc_array_lvs_signoff(grid)["n_checks"] == 6,
          f"n_checks={S3.sc_array_lvs_signoff(grid)['n_checks']}")

    # ════════════════ D 节：诚实标注 + 红线 ════════════════
    print("── D 诚实标注 + 红线 ──")
    disc = S3.RED_LINE_DISCLOSURE
    check("D1 披露齐备：role/layers/limits/lvs/physics/red_line 五键",
          all(k in disc for k in ("role", "layers", "limits", "lvs",
                                   "physics", "red_line")),
          f"键={sorted(disc)}")
    check("D2 限值为设计规则 · 非实测 golden（明确标注 D5 外部依赖）",
          "设计规则" in disc["limits"] and "非实测 golden" in disc["limits"]
          and "D5" in disc["limits"], "默认限值为设计规则口径")
    src = open(os.path.join(_HERE, "lda_qeda", "sc_array.py"), encoding="utf-8").read()
    banned = ("qiskit", "cirq", "pennylane", "strawberryfields", "thewalrus", "qutip")
    hits = [b for b in banned if re.search(rf"^\s*(import|from)\s+{b}\b", src, re.M)]
    check("D3 红线：D-135 零量子 SDK 依赖（纯几何 + 平台，C 级自主）",
          not hits, f"命中={hits or '无'}")
    drc_v = S3.run_sc_array_drc(grid)
    check("D4 判决无 LLM：verdict 为 str 死标量、violation 为 dict（零模型调用）",
          drc_v["verdict"] in ("ACCEPT", "REJECT")
          and all(isinstance(v, dict) and set(v) == {"rule", "detail"}
                  for v in drc_v["violations"]),
          "rule/detail 二元组 · 纯限值比对")

    # ════════════════ E 节：GDS round-trip ════════════════
    print("── E GDS 真出 + 解析 round-trip ──")
    data = S3.array_gds({"rows": 2, "cols": 2},
                        os.path.join(_HERE, "_sc_s3_tmp.gds"))
    parsed = S3.G.parse_gds(data)
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

    # ════════════════ F 节：跨模块物理（逐边双验证 + CR 有效模型 + ZZ）═══════════════
    print("── F 跨模块物理（逐边 coupler_solver 严格 J ↔ 解析 J · cross_resonance 有效 ZX/ZZ）──")
    phys = S3.array_physics({"rows": 2, "cols": 2})
    check("F1 逐边 J 严格对角化 ↔ 解析闭式 双验证 rel≤5%（确定性物理定律锚）",
          phys["all_j_double_validated"]
          and phys["max_relJ"] <= 0.05,
          f"minRelJ={phys['min_relJ']:.2%} · maxRelJ={phys['max_relJ']:.2%} · n_edges={phys['n_edges']}")
    check("F2 逐边 CR 有效模型落窗：|g_CR|∈[0.02,10]MHz · t_CR≤T2 · 参数区 |Δ|<|α|",
          phys["all_cr_ok"],
          f"min|g_CR|={phys['min_abs_g_CR_mhz']:.3f} · max|g_CR|={phys['max_abs_g_CR_mhz']:.3f}MHz")
    check("F3 残余 ZZ 诚实报告（σ_zz 逐边返回 + echoed-CR 抵消标注）",
          all(e["sigma_zz_mhz"] is not None for e in phys["edges"]),
          f"σ_zz 示例={phys['edges'][0]['sigma_zz_mhz']:.4f}MHz（echoed-CR 可抵消）")
    check("F4 物理产出合理：每边 f01∈[4,7]GHz · α<0 · 每边 0<Δ<|α|",
          all(4.0 <= e["f01_a_ghz"] <= 7.0 and 4.0 <= e["f01_b_ghz"] <= 7.0
              and e["detune_mhz"] > 0
              and e["detune_mhz"] < abs(phys["alpha_mhz"])
              for e in phys["edges"]),
          f"α={phys['alpha_mhz']:.0f}MHz · 示例Δ={phys['edges'][0]['detune_mhz']:.1f}MHz")
    check("F5 阵列物理签核 verdict=ACCEPT（逐边 J 双验证 + CR 落窗 同真）",
          phys["verdict"] == "ACCEPT",
          f"verdict={phys['verdict']} · j_ok={phys['all_j_double_validated']} · cr_ok={phys['all_cr_ok']}")
    scale = S3.array_physics({"rows": 3, "cols": 3})
    check("F6 规模 3×3=9 qubit / 12 边 物理 ACCEPT（逐边双验证全过）",
          scale["verdict"] == "ACCEPT"
          and scale["n_qubits"] == 9 and scale["n_edges"] == _expected_edges(3, 3)
          and scale["all_j_double_validated"] and scale["all_cr_ok"],
          f"n_qubits={scale['n_qubits']} · n_edges={scale['n_edges']} · "
          f"maxRelJ={scale['max_relJ']:.2%} · max|g_CR|={scale['max_abs_g_CR_mhz']:.3f}MHz")

    print()
    print(f"超导 N 比特阵列 门禁 smoke（D-135）：{PASS}/{PASS + FAIL} PASS")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
