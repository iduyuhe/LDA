"""超导征程 S5 规模压力门禁 smoke（D-137/D-142/D-143 · 吃狗粮）。

═══ 为什么要有这个 smoke ═══
S5 首刀把平台从「能排带 stub 的阵列」（S4·D-136·9 qubit）推进到「能把 N 个 qubit 的
读出/控制路由到焊盘（G1·D-137）+ 频率避撞分配（G6·D-142）」，并在 53→127→433→1024
的规模上压 DRC/LVS/预算的**运行时与元素数**（G7·D-143）。这类「规模能力」最易被悄悄降级
（例如把路由间距放宽、把频率碰撞检测删掉、把杂散 ZZ 上限调松、把规模压测缩回 9 qubit），
必须钉成常驻断言：

  ① **两模块自检全过**（G1 12 项 · G6 13 项）
  ② **路由 DRC 各规则可触发 REJECT**（lane 太密 / 焊盘太小 / 焊盘太密）
  ③ **段感知 LVS 可触发 REJECT**（缺控制 / 控制未达焊盘 / 缺焊盘）
  ④ **诚实标注 + 红线**（限值为设计规则 · 零量子 SDK · 判决死标量）
  ⑤ **GDS round-trip**（真出 GDS → parse_gds 读回含 SC 层 10/11/12）
  ⑥ **规模压力**（N=56/130/441/1024：路由 DRC+LVS 全 ACCEPT；频率规划 + 杂散 ZZ 全 ACCEPT；
     路由容量闭式自洽）

运行：python run_schip_s5_smoke.py（cwd=lda/）
出口：全 PASS 退 0；任一 FAIL 退 1。LLM 不进判决路径。
"""
from __future__ import annotations

import os
import re
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))       # = …/lda
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_qeda import sc_routing as SR                                # noqa: E402
from lda_qeda import sc_freq_alloc as FA                             # noqa: E402
from lda_harness.smoke_kit import make_check                         # noqa: E402

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=" | {d}", return_ok=True)

# 规模档：目标 N → 阵列 (rows, cols)（rows×cols ≥ 目标）
SCALE_TIERS = [(53, 7, 8), (127, 13, 10), (433, 21, 21), (1024, 32, 32)]


def _expected_edges(rows: int, cols: int) -> int:
    return rows * (cols - 1) + cols * (rows - 1)


def main() -> int:
    print("=" * 78)
    print("超导征程 S5 规模压力门禁 smoke（D-137 路由 · D-142 频率 · D-143 规模）")
    print("=" * 78)

    # ════════════════ A 节：模块自检 ════════════════
    print("── A 模块自检 ──")
    for nm, mod, cnt in (("G1 D-137 路由", SR, 12), ("G6 D-142 频率", FA, 13)):
        try:
            okm = mod.run_selfchecks(verbose=False)
        except Exception as e:                                       # noqa: BLE001
            okm = False
            print(f"  {nm} run_selfchecks 异常：{type(e).__name__}: {e}")
        check(f"A {'1' if mod is SR else '2'} {nm} 模块自检全 PASS", okm,
              f"期望 {cnt} 项全 PASS")

    # ════════════════ B 节：路由 DRC 规则可触发 ════════════════
    print("── B G1 路由 DRC 规则 ──")
    g22 = SR.routed_array_cell({"rows": 2, "cols": 2})
    check("B1 合法 2×2 路由阵列 DRC ACCEPT（14 规则全过）",
          SR.run_routing_drc(g22)["verdict"] == "ACCEPT",
          f"verdict={SR.run_routing_drc(g22)['verdict']}")
    thin = SR.routed_array_cell({"rows": 1, "cols": 3, "routing_pitch": 0.3})
    vt = SR.run_routing_drc(thin)
    check("B2 路由 lane 太密(pitch0.3·线宽1) ⇒ DRC REJECT（SCD-ROUTING-WIRE-SPACING）",
          vt["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-ROUTING-WIRE-SPACING" for v in vt["violations"]),
          f"violations={sorted(set(v['rule'] for v in vt['violations']))}")
    sp = SR.routed_array_cell({"rows": 1, "cols": 2, "bond_pad_w": 0.5, "bond_pad_h": 0.5})
    vsp = SR.run_routing_drc(sp)
    check("B3 焊盘太小(0.5<2.0) ⇒ DRC REJECT（SCD-ROUTING-PAD-MIN-WIDTH）",
          vsp["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-ROUTING-PAD-MIN-WIDTH" for v in vsp["violations"]),
          f"violations={sorted(set(v['rule'] for v in vsp['violations']))}")
    dp = SR.routed_array_cell({"rows": 1, "cols": 2, "routing_pitch": 2.0,
                               "bond_pad_h": 2.0})
    vdp = SR.run_routing_drc(dp)
    check("B4 焊盘过密(pitch2.0·pad_h2.0) ⇒ DRC REJECT（SCD-ROUTING-PAD-SPACING）",
          vdp["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-ROUTING-PAD-SPACING" for v in vdp["violations"]),
          f"violations={sorted(set(v['rule'] for v in vdp['violations']))}")
    check("B5 规则名 / n_rules 稳定（ROUTING_DRC_RULES = S4 十则 + 路由四则 = 14）",
          len(SR.ROUTING_DRC_RULES) == 14 and SR.run_routing_drc(g22)["n_rules"] == 14,
          f"ROUTING_DRC_RULES={len(SR.ROUTING_DRC_RULES)}")

    # ════════════════ C 节：段感知 LVS ════════════════
    print("── C G1 段感知 LVS（控制网精确桥接 1 qubit + 1 焊盘）──")
    check("C1 合法 2×2 路由阵列 LVS ACCEPT（4 控制网·焊盘 4+2·连通）",
          SR.routed_array_lvs(g22)["verdict"] == "ACCEPT",
          f"netlist={SR.routed_array_lvs(g22)['netlist']}")
    nl = SR.routed_array_lvs(g22)["netlist"]
    check("C2 2×2 网表断言：qubit 4 · 控制 4 · 控制焊盘 4 · 焊盘 6 · 馈线 2 · 边 4 · 地 1",
          nl["qubit_nets"] == 4 and nl["control"] == 4 and nl["pads_control"] == 4
          and nl["pads_total"] == 6 and nl["feedline_segments"] == 2
          and nl["edges_bridged"] == _expected_edges(2, 2) and nl["ground_nets"] == 1,
          f"netlist={nl}")
    no_ctrl = [d for d in g22
               if d.get("net") != "control"
               and not (d.get("net") == "pad" and d.get("pad_role") == "control")]
    vnc = SR.routed_array_lvs(no_ctrl)
    check("C3 缺控制线 ⇒ LVS REJECT（QUBIT-NO-CONTROL）",
          vnc["verdict"] == "REJECT" and any("QUBIT-NO-CONTROL" in i for i in vnc["issues"]),
          f"issues={vnc['issues'][:3]}")
    cut = []
    for d in g22:
        if d.get("net") == "control":
            d2 = dict(d)
            p0, p1, _p2 = d["points_um"]
            d2["points_um"] = [p0, p1, (p1[0] + 0.5, p1[1])]
            cut.append(d2)
        else:
            cut.append(d)
    vcut = SR.routed_array_lvs(cut)
    check("C4 控制线未达焊盘 ⇒ LVS REJECT（CONTROL-NO-PAD）",
          vcut["verdict"] == "REJECT" and any("CONTROL-NO-PAD" in i for i in vcut["issues"]),
          f"issues={vcut['issues'][:3]}")
    nopad = [d for d in g22
             if not (d.get("net") == "pad" and d.get("pad_role") == "control")]
    vnp = SR.routed_array_lvs(nopad)
    check("C5 缺控制焊盘 ⇒ LVS REJECT（PAD-COUNT）",
          vnp["verdict"] == "REJECT" and any("PAD-COUNT" in i for i in vnp["issues"]),
          f"issues={vnp['issues'][:3]}")
    check("C6 LVS n_checks=11（net/JJ/qubit网/馈线/读出/控制/焊盘/耦合器/连通/地/短接）",
          SR.routed_array_lvs(g22)["n_checks"] == 11,
          f"n_checks={SR.routed_array_lvs(g22)['n_checks']}")

    # ════════════════ D 节：诚实标注 + 红线 ════════════════
    print("── D 诚实标注 + 红线 ──")
    disc = SR.RED_LINE_DISCLOSURE
    check("D1 路由披露齐备：role/layers/limits/lvs/physics/routing/red_line 七键",
          all(k in disc for k in ("role", "layers", "limits", "lvs", "physics",
                                   "routing", "red_line")),
          f"键={sorted(disc)}")
    check("D2 路由限值为设计规则 · 非实测 golden（标注 D5 外部依赖）",
          "设计规则" in disc["limits"] and "非实测 golden" in disc["limits"]
          and "D5" in disc["limits"], "默认限值为设计规则口径")
    fdisc = FA.RED_LINE_DISCLOSURE
    check("D3 频率披露齐备：role/limits/method/physics/red_line 五键",
          all(k in fdisc for k in ("role", "limits", "method", "physics", "red_line")),
          f"键={sorted(fdisc)}")
    banned = ("qiskit", "cirq", "pennylane", "strawberryfields", "thewalrus", "qutip")
    hits = []
    for fn in ("sc_routing.py", "sc_freq_alloc.py"):
        src = open(os.path.join(_HERE, "lda_qeda", fn), encoding="utf-8").read()
        hits += [(fn, b) for b in banned
                 if re.search(rf"^\s*(import|from)\s+{b}\b", src, re.M)]
    check("D4 红线：G1/G6 零量子 SDK 依赖（纯几何 + 平台 numpy，C 级自主）",
          not hits, f"命中={hits or '无'}")
    drc_v = SR.run_routing_drc(g22)
    check("D5 判决无 LLM：verdict 为 str 死标量、violation 为 dict（零模型调用）",
          drc_v["verdict"] in ("ACCEPT", "REJECT")
          and all(isinstance(v, dict) and set(v) == {"rule", "detail"}
                  for v in drc_v["violations"]),
          "rule/detail 二元组 · 纯限值比对")

    # ════════════════ E 节：GDS round-trip ════════════════
    print("── E GDS 真出 + 解析 round-trip ──")
    data = SR.routed_gds({"rows": 3, "cols": 3},
                         os.path.join(_HERE, "_sc_s5_tmp.gds"))
    parsed = SR.G.parse_gds(data)
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
          f"structs={parsed.get('n_structures')} · elems={total_elems}")

    # ════════════════ F 节：规模压力 ════════════════
    print("── F 规模压力（N=53→127→433→1024：路由 + 频率）──")
    for (target, rows, cols) in SCALE_TIERS:
        t0 = time.time()
        els = SR.routed_array_cell({"rows": rows, "cols": cols})
        drc = SR.run_routing_drc(els)
        lvs = SR.routed_array_lvs(els)
        dt = time.time() - t0
        check(f"F 路由规模 N={target}（{rows}×{cols}={rows * cols}）DRC+LVS 双 ACCEPT",
              drc["verdict"] == "ACCEPT" and lvs["verdict"] == "ACCEPT",
              f"DRC={drc['verdict']} LVS={lvs['verdict']} · 元素={len(els)} · "
              f"{dt:.2f}s")
        fpl = FA.plan({"rows": rows, "cols": cols})
        check(f"F 频率规模 N={target}（{rows}×{cols}）规划 + 杂散 ZZ ACCEPT",
              fpl["verdict"] == "ACCEPT",
              f"mode={fpl['mode']} · 杂散ZZ={fpl['max_stray_zz_mhz']:.4f}≤"
              f"{fpl['zz_stray_limit_mhz']} · path={fpl['zz_path']}")
    # 规模综合断言：1024 档元素数、容量、路由自洽
    els1024 = SR.routed_array_cell({"rows": 32, "cols": 32})
    cap = SR.routing_capacity({"rows": 32, "cols": 32})
    check("F9 千比特级 32×32：元素数 > 9000 · 路由容量自洽（pitch_y 自洽放大 ∝ cols）",
          len(els1024) > 9000 and cap["n_signals"] == 1056
          and cap["pitch_y_eff_um"] >= cap["band_needed_um"] + cap["qubit_half_um"],
          f"元素={len(els1024)} · n_signals={cap['n_signals']} · "
          f"pitch_y_eff={cap['pitch_y_eff_um']:.1f}")
    lb = SR.S4.loss_budget({"rows": 21, "cols": 21})
    check("F10 损耗预算在规模 N=441 下仍 ACCEPT（per-qubit T1 ≥ 目标）",
          lb["verdict"] == "ACCEPT" and lb["min_t1_total_us"] >= SR.S4.T1_TARGET_US,
          f"min_t1={lb['min_t1_total_us']:.2f}µs ≥ {lb['t1_target_us']}µs")

    print()
    print(f"超导征程 S5 规模压力门禁 smoke（D-137/D-142/D-143）：{PASS}/{PASS + FAIL} PASS")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
