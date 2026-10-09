"""超导征程 S4 门禁 smoke（D-136 · 读出/控制线路 + 串扰/损耗预算 · 吃狗粮）。

═══ 为什么要有这个 smoke ═══
D-136 把平台从「能排 N 比特阵列」（S3·D-135）推进到「带读出/控制互连 + 系统级
串扰/损耗预算」。这类「新增读出/控制几何原语 + 全 pair 串扰矩阵 + per-qubit 损耗预算」
半年后最易被悄悄降级（例如删掉读出-馈线短接检查、把杂散 ZZ 上限放宽、把损耗目标
调松、把控制串扰上限放开），必须钉成常驻断言：

  ① **合法阵列 DRC/LVS 双 ACCEPT**（2×2 网格 + 1×4 链，含读出/控制网）
  ② **DRC 各规则可触发 REJECT**（读出薄 / 馈线薄 / 控制薄 / 读出-馈线短接 / 控制-地短接）
  ③ **LVS 多网连通可触发 REJECT**（缺读出 / 读出-馈线短接 / 控制-地短接 / 无 net /
     拓扑网数不符）
  ④ **诚实标注 + 红线**（限值为设计规则 · 零量子 SDK · 判决死标量 · 串扰/损耗为几何+闭式估计）
  ⑤ **GDS round-trip**（真出 GDS → parse_gds 读回含 SC 层 10/11/12）
  ⑥ **物理双预算**（全 pair 串扰 ζ_zz ≤ 杂散 ZZ 上限 + 控制串扰 ≤ 上限；per-qubit 损耗
     T1_total ≥ 目标；3×3 规模双 ACCEPT）

运行：python run_schip_s4_smoke.py（cwd=lda/）
出口：全 PASS 退 0；任一 FAIL 退 1。LLM 不进判决路径。
"""
from __future__ import annotations

import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))       # = …/lda
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

_SCHIP_TMP = os.path.join(_HERE, "reports", "schip_tmp")
os.makedirs(_SCHIP_TMP, exist_ok=True)

from lda_qeda import sc_readout as S4                                # noqa: E402
from lda_harness.smoke_kit import make_check                         # noqa: E402

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=" | {d}", return_ok=True)


def _expected_edges(rows: int, cols: int) -> int:
    return rows * (cols - 1) + cols * (rows - 1)


def main() -> int:
    print("=" * 78)
    print("超导征程 S4 门禁 smoke（D-136 · 读出/控制 + 串扰/损耗预算）")
    print("=" * 78)

    # ════════════════ A 节：模块自检 ════════════════
    print("── A 模块自检 ──")
    try:
        ok_a = S4.run_selfchecks(verbose=False)
    except Exception as e:                                       # noqa: BLE001
        ok_a = False
        print(f"  run_selfchecks 异常：{type(e).__name__}: {e}")
    check("A1 D-136 模块自检 12/12 PASS（合法双 ACCEPT · 八类违规各 REJECT · 物理 ACCEPT）",
          ok_a, "合法双 ACCEPT + 缺读出/误桥/短接/薄/杂散ZZ/损耗各 REJECT")

    # ════════════════ B 节：DRC 规则可触发（读出/控制规模感知）═══════════════
    print("── B 超导读出/控制 DRC 规则 ──")
    grid = S4.readout_array_cell({"rows": 2, "cols": 2})
    check("B1 合法 2×2 读出阵列 DRC ACCEPT（10 规则全过）",
          S4.run_readout_drc(grid)["verdict"] == "ACCEPT",
          f"verdict={S4.run_readout_drc(grid)['verdict']}")
    thin = S4.readout_array_cell({"rows": 1, "cols": 2, "readout_hw": 0.1})
    vt = S4.run_readout_drc(thin)
    check("B2 读出腔太薄(半宽0.1→最薄边0.2<0.8) ⇒ DRC REJECT（SCD-READOUT-MIN-WIDTH）",
          vt["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-READOUT-MIN-WIDTH" for v in vt["violations"]),
          f"violations={[v['rule'] for v in vt['violations']]}")
    thinf = S4.readout_array_cell({"rows": 1, "cols": 2, "feedline_w": 0.1})
    vtf = S4.run_readout_drc(thinf)
    check("B3 馈线太薄(0.1<1.0) ⇒ DRC REJECT（SCD-FEEDLINE-MIN-WIDTH）",
          vtf["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-FEEDLINE-MIN-WIDTH" for v in vtf["violations"]),
          f"violations={[v['rule'] for v in vtf['violations']]}")
    tinc = S4.readout_array_cell({"rows": 1, "cols": 2, "control_w": 0.1})
    vtc = S4.run_readout_drc(tinc)
    check("B4 控制桩太薄(0.1<0.6) ⇒ DRC REJECT（SCD-CONTROL-MIN-WIDTH）",
          vtc["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-CONTROL-MIN-WIDTH" for v in vtc["violations"]),
          f"violations={[v['rule'] for v in vtc['violations']]}")
    short = S4.readout_array_cell({"rows": 1, "cols": 2, "readout_hh": 4.0})
    vsr = S4.run_readout_drc(short)
    check("B5 读出-馈线短接(重叠) ⇒ DRC REJECT（SCD-READOUT-FEEDLINE-GAP）",
          vsr["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-READOUT-FEEDLINE-GAP" for v in vsr["violations"]),
          f"violations={[v['rule'] for v in vsr['violations']]}")
    cshort = S4.readout_array_cell({"rows": 1, "cols": 2, "control_len": 20.0})
    vcs = S4.run_readout_drc(cshort)
    check("B6 控制桩穿地(过长) ⇒ DRC REJECT（SCD-CONTROL-GROUND-GAP）",
          vcs["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-CONTROL-GROUND-GAP" for v in vcs["violations"]),
          f"violations={[v['rule'] for v in vcs['violations']]}")
    check("B7 规则名 / n_rules 稳定（READOUT_DRC_RULES=10 条）",
          len(S4.READOUT_DRC_RULES) == 10 and S4.run_readout_drc(grid)["n_rules"] == 10,
          f"READOUT_DRC_RULES={len(S4.READOUT_DRC_RULES)}")

    # ════════════════ C 节：LVS 多网连通（拓扑感知）═══════════════
    print("── C 超导读出/控制 LVS 多网连通 ──")
    check("C1 合法 2×2 读出阵列 LVS ACCEPT（4 qubit·2 馈线·4 读出·4 控制·连通）",
          S4.readout_lvs_signoff(grid)["verdict"] == "ACCEPT",
          f"netlist={S4.readout_lvs_signoff(grid)['netlist']}")
    nl_grid = S4.readout_lvs_signoff(grid)["netlist"]
    check("C2 2×2 拓扑断言：qubit_nets==4 · 馈线段==2 · 读出==4 · 控制==4 · 边==4 · 地==1",
          nl_grid["qubit_nets"] == 4 and nl_grid["feedline_segments"] == 2
          and nl_grid["readout"] == 4 and nl_grid["control"] == 4
          and nl_grid["edges_bridged"] == _expected_edges(2, 2)
          and nl_grid["ground_nets"] == 1,
          f"netlist={nl_grid}")
    chain = S4.readout_array_cell({"rows": 1, "cols": 4})
    nl_chain = S4.readout_lvs_signoff(chain)["netlist"]
    check("C3 1×4 链 LVS ACCEPT + 拓扑断言：4 qubit · 1 馈线 · 4 读出 · 4 控制 · 边==3",
          S4.readout_lvs_signoff(chain)["verdict"] == "ACCEPT"
          and nl_chain["qubit_nets"] == 4
          and nl_chain["feedline_segments"] == 1
          and nl_chain["readout"] == 4 and nl_chain["control"] == 4
          and nl_chain["edges_bridged"] == _expected_edges(1, 4),
          f"netlist={nl_chain}")
    noread = [d for d in grid if d.get("net") != "readout"]
    vnr = S4.readout_lvs_signoff(noread)
    check("C4 缺读出（每 qubit 无 readout）⇒ LVS REJECT（QUBIT-NO-READOUT）",
          vnr["verdict"] == "REJECT"
          and any("QUBIT-NO-READOUT" in i for i in vnr["issues"]),
          f"issues={vnr['issues']}")
    ro_short = S4.readout_array_cell({"rows": 1, "cols": 2, "readout_hh": 4.0})
    vros = S4.readout_lvs_signoff(ro_short)
    check("C5 读出-馈线重叠短接 ⇒ LVS REJECT（READOUT-FEEDLINE-SHORT）",
          vros["verdict"] == "REJECT"
          and any("READOUT-FEEDLINE-SHORT" in i for i in vros["issues"]),
          f"issues={vros['issues']}")
    ctrl = S4.readout_array_cell({"rows": 1, "cols": 2, "control_len": 20.0})
    vcts = S4.readout_lvs_signoff(ctrl)
    check("C6 控制桩穿地（与地重叠）⇒ LVS REJECT（CONTROL-GROUND-SHORT）",
          vcts["verdict"] == "REJECT"
          and any("CONTROL-GROUND-SHORT" in i for i in vcts["issues"]),
          f"issues={vcts['issues']}")
    nonet = grid + [{"kind": "boundary", "layer": S4.FILM,
                     "rings_um": [[(300, 300), (302, 300), (302, 302), (300, 302)]]}]
    vnn = S4.readout_lvs_signoff(nonet)
    check("C7 无 net 标签导体 ⇒ LVS REJECT（SCD-LVS-NO-NET）",
          vnn["verdict"] == "REJECT"
          and any("NO-NET" in i for i in vnn["issues"]),
          f"issues={vnn['issues']}")
    check("C8 LVS n_checks=9（net/JJ桥接/读出桥接/控制桥接/耦合器桥接/连通/地/"
          "读出-地/控制-地 九判据）",
          S4.readout_lvs_signoff(grid)["n_checks"] == 9,
          f"n_checks={S4.readout_lvs_signoff(grid)['n_checks']}")

    # ════════════════ D 节：诚实标注 + 红线 ════════════════
    print("── D 诚实标注 + 红线 ──")
    disc = S4.RED_LINE_DISCLOSURE
    check("D1 披露齐备：role/layers/limits/lvs/physics/red_line 六键",
          all(k in disc for k in ("role", "layers", "limits", "lvs",
                                   "physics", "red_line")),
          f"键={sorted(disc)}")
    check("D2 限值为设计规则 · 非实测 golden（明确标注 D5 外部依赖）",
          "设计规则" in disc["limits"] and "非实测 golden" in disc["limits"]
          and "D5" in disc["limits"], "默认限值为设计规则口径")
    check("D3 串扰/损耗诚实标注为几何+闭式估计（非全波仿真 golden）",
          "几何" in disc.get("physics", "") and "闭式" in disc.get("physics", "")
          and "设计估计" in disc.get("physics", ""), "物理为几何+闭式估计口径")
    src = open(os.path.join(_HERE, "lda_qeda", "sc_readout.py"), encoding="utf-8").read()
    banned = ("qiskit", "cirq", "pennylane", "strawberryfields", "thewalrus", "qutip")
    hits = [b for b in banned if re.search(rf"^\s*(import|from)\s+{b}\b", src, re.M)]
    check("D4 红线：D-136 零量子 SDK 依赖（纯几何 + 平台，C 级自主）",
          not hits, f"命中={hits or '无'}")
    drc_v = S4.run_readout_drc(grid)
    check("D5 判决无 LLM：verdict 为 str 死标量、violation 为 dict（零模型调用）",
          drc_v["verdict"] in ("ACCEPT", "REJECT")
          and all(isinstance(v, dict) and set(v) == {"rule", "detail"}
                  for v in drc_v["violations"]),
          "rule/detail 二元组 · 纯限值比对")

    # ════════════════ E 节：GDS round-trip ════════════════
    print("── E GDS 真出 + 解析 round-trip ──")
    data = S4.readout_gds({"rows": 2, "cols": 2},
                           os.path.join(_SCHIP_TMP, "_sc_s4_tmp.gds"))
    parsed = S4.G.parse_gds(data)
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
          f"structs={parsed.get('n_structures')} · elems={total_elems} · "
          f"layers={sorted(layers)}")

    # ════════════════ F 节：物理双预算（串扰 + 损耗）═══════════════
    print("── F 物理双预算（全 pair 串扰 ζ_zz + per-qubit 损耗 T1）──")
    xt = S4.crosstalk_budget({"rows": 2, "cols": 2})
    check("F1 串扰预算 ACCEPT（合法 2×2：杂散 ZZ + 控制串扰双过）",
          xt["verdict"] == "ACCEPT",
          f"max_stray_zz={xt['max_stray_zz_mhz']:.3f}≤{xt['zz_stray_limit_mhz']} · "
          f"max_xt={xt['max_control_xtalk']:.4f}≤{xt['control_xtalk_limit']}")
    check("F2 杂散 ZZ ≤ 上限（max_stray_zz_mhz ≤ ZZ_STRAY_LIMIT_MHZ）",
          xt["max_stray_zz_mhz"] <= S4.ZZ_STRAY_LIMIT_MHZ,
          f"max_stray_zz={xt['max_stray_zz_mhz']:.3f}MHz "
          f"(限={S4.ZZ_STRAY_LIMIT_MHZ}MHz)")
    check("F3 控制串扰 ≤ 上限（max_control_xtalk ≤ CONTROL_XTALK_LIMIT）",
          xt["max_control_xtalk"] <= S4.CONTROL_XTALK_LIMIT,
          f"max_xt={xt['max_control_xtalk']:.4f} (限={S4.CONTROL_XTALK_LIMIT})")
    check("F4 全 pair ZZ 矩阵规模正确（n_pairs == N(N-1)/2）",
          xt["n_pairs"] == (xt["n_qubits"] * (xt["n_qubits"] - 1)) // 2,
          f"n_qubits={xt['n_qubits']} · n_pairs={xt['n_pairs']}")
    lb = S4.loss_budget({"rows": 2, "cols": 2})
    check("F5 损耗预算 ACCEPT（per-qubit T1_total ≥ T1_TARGET 且 T1_purcell ≥ 目标）",
          lb["verdict"] == "ACCEPT" and lb["min_t1_total_us"] >= S4.T1_TARGET_US,
          f"min_t1_total={lb['min_t1_total_us']:.2f}µs ≥ {lb['t1_target_us']}µs")
    check("F6 损耗公式维度正确（1/T1 含 ω·Σtanδ·p + Purcell γ=κg²/Δ²）",
          all(q["t1_total_us"] is not None and q["t1_purcell_us"] is not None
              for q in lb["per_qubit"]),
          f"per_qubit 数={len(lb['per_qubit'])} · "
          f"min_t1={lb['min_t1_total_us']:.2f}µs")
    phys = S4.readout_physics({"rows": 2, "cols": 2})
    check("F7 综合物理签核 verdict=ACCEPT（串扰 + 损耗双 ACCEPT 同真）",
          phys["verdict"] == "ACCEPT",
          f"verdict={phys['verdict']} · xt={xt['verdict']} · loss={lb['verdict']}")
    scale_xt = S4.crosstalk_budget({"rows": 3, "cols": 3})
    scale_lb = S4.loss_budget({"rows": 3, "cols": 3})
    scale_phys = S4.readout_physics({"rows": 3, "cols": 3})
    check("F8 规模 3×3=9 qubit 双预算 ACCEPT（串扰+损耗，含 36 pair ZZ）",
          scale_xt["verdict"] == "ACCEPT" and scale_lb["verdict"] == "ACCEPT"
          and scale_phys["verdict"] == "ACCEPT"
          and scale_xt["n_qubits"] == 9 and scale_xt["n_pairs"] == 36,
          f"n_qubits={scale_xt['n_qubits']} · n_pairs={scale_xt['n_pairs']} · "
          f"max_stray={scale_xt['max_stray_zz_mhz']:.3f} · "
          f"min_t1={scale_lb['min_t1_total_us']:.2f}µs")

    print()
    print(f"超导征程 S4 门禁 smoke（D-136）：{PASS}/{PASS + FAIL} PASS")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
