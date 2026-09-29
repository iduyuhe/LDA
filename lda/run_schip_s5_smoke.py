"""超导征程 S5 规模压力 + P1 架构 + D-145 统一拓扑框架门禁 smoke（D-137..D-145 · 吃狗粮）。

═══ 为什么要有这个 smoke ═══
S5 把平台从「能排带 stub 的阵列」（S4·D-136·9 qubit）推进到「能把 N 个 qubit 的读出/控制
路由到焊盘 + 频率避撞 + 真实架构要素」，并在规模上压 DRC/LVS/预算。这类「规模 +
架构能力」最易被悄悄降级（把路由间距放宽、把频率碰撞检测删掉、把杂散 ZZ 上限调松、
把 heavy-hex 弄出 4 邻居、把可调耦合器关不断、把读出音重音、把封装模落带放行……），
必须钉成常驻断言：

  A  **G1/G6 模块自检全过**（12/13 项）
  B  **路由 DRC 各规则可触发 REJECT**（lane 太密 / 焊盘太小 / 焊盘太密）
  C  **段感知 LVS 可触发 REJECT**（缺控制 / 控制未达焊盘 / 缺焊盘）
  D  **诚实标注 + 红线**（限值为设计规则 · 零量子 SDK · 判决死标量）
  E  **GDS round-trip**（真出 GDS → parse_gds 读回含 SC 层 10/11/12）
  F  **规模压力**（N=53/127/433/1024：路由 DRC+LVS 全 ACCEPT；频率规划 + 杂散 ZZ 全 ACCEPT）
  ── S5 P1（D-138 heavy-hex / D-139 可调耦合器 / D-140 读出 mux / D-141 控制多线 / D-144 阵列损耗）──
  G  **P1 五模块自检全过**（8/9/9/5/9 项）
  H  G3 可调耦合器：SQUID 2 结 · flux 间隙 · J 双验证 + 可关比
  I  G4 读出 mux：每馈线音互异 · 音间隔 · qubit 保护带 · 重音
  J  G5 控制多线：三线（xy/z/cflux）角色互异 · 线间距 · XY↔Z 隔离
  K  G8 阵列损耗：封装参与比 · 封装腔模规避 · 阵列聚合良率
  L  G2 heavy-hex：**最大度 ≤ 3（无 4 邻居）** · 图计数 · 规模 4×5
  M  P1 诚实标注 + 红线（披露键 · 零量子 SDK · 判决死标量）
  N  P1 模块 GDS round-trip（G2/G3/G4/G5）
  O  P1 规模压力（N=53/127/433：mux/control/阵列损耗全 ACCEPT；1024 阵列损耗）
  ── S5 第三波 · 完善（D-145 统一拓扑 DRC/LVS 框架）──
  P  **方阵与 heavy-hex 共用**同一份拓扑抽象 + DRC/LVS/物理引擎（度上限由拓扑自声明
     4 vs 3 · 规则名统一 `SCD-TOPO-*` · 方阵实例与 S3 口径一致）

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
from lda_qeda import sc_coupler as SC                                # noqa: E402
from lda_qeda import sc_readout_mux as MX                            # noqa: E402
from lda_qeda import sc_control as CT                                # noqa: E402
from lda_qeda import sc_topology as TP                               # noqa: E402
from lda_qeda import sc_topology_core as TC                          # noqa: E402
from lda_qeda import sc_readout as S4                                # noqa: E402
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
    print("超导征程 S5 规模压力 + P1 架构 + D-145 统一拓扑框架门禁 smoke（D-137..D-145）")
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

    # ════════════════ G 节：P1 模块自检（G2/G3/G4/G5/G8）════════════════
    print("── G S5 P1 模块自检 ──")
    for gi, (nm, fn, cnt) in enumerate((
            ("G3 D-139 可调耦合器", SC.run_tunable_selfchecks, 8),
            ("G4 D-140 读出 mux", MX.run_selfchecks, 9),
            ("G5 D-141 控制多线", CT.run_selfchecks, 9),
            ("G8 D-144 阵列损耗", S4.run_array_loss_selfchecks, 5),
            ("G2 D-138 heavy-hex", TP.run_selfchecks, 9)), start=1):
        try:
            okm = fn(verbose=False)
        except Exception as e:                                       # noqa: BLE001
            okm = False
            print(f"  {nm} 自检异常：{type(e).__name__}: {e}")
        check(f"G{gi} {nm} 模块自检全 PASS", okm, f"期望 {cnt} 项全 PASS")

    # ════════════════ H 节：G3 可调耦合器（SQUID）════════════════
    print("── H G3 可调耦合器（D-139）──")
    tc = SC.tunable_coupler_cell({})
    hd = SC.run_tunable_drc(tc)
    hl = SC.tunable_coupler_lvs(tc)
    check("H1 合法可调耦合器 DRC+LVS 双 ACCEPT（S2 四则 + SQUID 三则）",
          hd["verdict"] == "ACCEPT" and hl["verdict"] == "ACCEPT",
          f"DRC={hd['verdict']} LVS={hl['verdict']}")
    check("H2 SQUID 结数 = 2（区别于 transmon 结）", hd["n_squid_jj"] == 2,
          f"n_squid_jj={hd['n_squid_jj']}")
    squid_ids = {id(d) for d in SC._squid_jjs(tc)}
    out = []
    removed = False
    for d in tc:
        if (not removed) and id(d) in squid_ids:
            removed = True
            continue
        out.append(d)
    vo = SC.run_tunable_drc(out)
    check("H3 SQUID 少一结 ⇒ DRC/LVS REJECT（SCD-SQUID-JJ-COUNT）",
          vo["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-SQUID-JJ-COUNT" for v in vo["violations"]), None)
    near = SC.run_tunable_drc(SC.tunable_coupler_cell({"flux_line_gap": -0.3}))
    check("H4 flux 线贴环(gap<0.3) ⇒ DRC REJECT（SCD-FLUX-LINE-GAP）",
          near["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-FLUX-LINE-GAP" for v in near["violations"]), None)
    hph = SC.tunable_coupler_physics({})
    check("H5 物理 ACCEPT：J 双验证 rel≤5% + J_on 落带 + 可关比≥阈值",
          hph["verdict"] == "ACCEPT" and hph["max_J_rel_err"] <= 0.05,
          f"rel={hph['max_J_rel_err']:.4f} J_on={hph['J_on_mhz']:.3f}MHz "
          f"off_ratio={hph['off_ratio']:.1f}")
    check("H6 SQUID 闭式：E_J(0)=2E_J0 · 对称结 E_J(0.5)≈0 · 不对称 = |ΔE_J|",
          abs(SC.squid_ej(10.0, 10.0, 0.0) - 20.0) < 1e-9
          and SC.squid_ej(10.0, 10.0, 0.5) < 1e-9
          and abs(SC.squid_ej(10.0, 9.0, 0.5) - 1.0) < 1e-9, None)

    # ════════════════ I 节：G4 读出频分复用 ════════════════
    print("── I G4 读出 mux（D-140）──")
    mcell = MX.mux_array_cell({"rows": 2, "cols": 2})
    mpl = MX.mux_plan({"rows": 2, "cols": 2})
    check("I1 合法 2×2 FDM 阵列 DRC+LVS 双 ACCEPT",
          MX.run_mux_drc(mcell, mpl)["verdict"] == "ACCEPT"
          and MX.mux_lvs(mcell, mpl)["verdict"] == "ACCEPT", None)
    by_feed = {}
    for r in mpl["per_readout"]:
        by_feed.setdefault(r["feedline"], []).append(r["tone_mhz"])
    check("I2 每馈线音互异 + 最小音间隔 ≥ 下限",
          all(len(v) == len({round(t, 6) for t in v}) for v in by_feed.values())
          and mpl["min_tone_spacing_mhz"] >= MX.DEFAULT_MUX_LIMITS["min_tone_spacing_mhz"],
          f"min_spacing={mpl['min_tone_spacing_mhz']}MHz")
    dense = MX.mux_plan({"rows": 2, "cols": 4, "f_min_ghz": 6.8, "f_max_ghz": 6.85})
    vden = MX.run_mux_drc(MX.mux_array_cell({"rows": 2, "cols": 4}), dense)
    check("I3 音域过窄 ⇒ 规划 + DRC REJECT（SCD-MUX-TONE-SPACING）",
          dense["verdict"] == "REJECT" and vden["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-MUX-TONE-SPACING" for v in vden["violations"]), None)
    guard = MX.mux_plan({"rows": 1, "cols": 1, "f_min_ghz": 5.05, "f_max_ghz": 5.05})
    check("I4 读出音贴 qubit f01 ⇒ 规划 REJECT（SCD-MUX-QUBIT-GUARD）",
          guard["verdict"] == "REJECT" and not guard["guard_ok"], None)
    dup_plan = dict(mpl)
    pr = [dict(x) for x in mpl["per_readout"]]
    pr[1] = dict(pr[1], tone_mhz=pr[0]["tone_mhz"])
    dup_plan["per_readout"] = pr
    vdup = MX.mux_lvs(mcell, dup_plan)
    check("I5 同馈线重音 ⇒ LVS REJECT（SCD-LVS-MUX-TONE-DUP）",
          vdup["verdict"] == "REJECT"
          and any("MUX-TONE-DUP" in i for i in vdup["issues"]), None)
    check("I6 物理 ACCEPT（频率规划 + per-读出 Purcell 双 ACCEPT）",
          MX.mux_physics({"rows": 2, "cols": 2})["verdict"] == "ACCEPT", None)

    # ════════════════ J 节：G5 控制多线 ════════════════
    print("── J G5 控制多线（D-141）──")
    ccell = CT.control_array_cell({"rows": 2, "cols": 2})
    check("J1 合法 2×2 多线控制 DRC+LVS 双 ACCEPT",
          CT.run_control_drc(ccell)["verdict"] == "ACCEPT"
          and CT.control_lvs(ccell)["verdict"] == "ACCEPT", None)
    n_ctrl = len([d for d in ccell if d.get("net") == "control"])
    check("J2 控制线数 = 4 qubit × 3 线（xy/z/cflux）= 12",
          n_ctrl == 12
          and all(d.get("control_role") in CT.CTRL_ROLES
                  for d in ccell if d.get("net") == "control"), f"n_ctrl={n_ctrl}")
    tight = CT.run_control_drc(CT.control_array_cell({"rows": 1, "cols": 2,
                                                     "ctrl_line_pitch": 0.2}))
    check("J3 三线太挤(pitch 0.2) ⇒ DRC REJECT（SCD-CTRL-LINE-SPACING）",
          tight["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-CTRL-LINE-SPACING" for v in tight["violations"]), None)
    missing = [d for d in ccell
               if not (d.get("net") == "control" and d.get("control_role") == "z")]
    vm = CT.control_lvs(missing)
    check("J4 缺 Z 线 ⇒ LVS REJECT（SCD-LVS-CTRL-LINE-COUNT）",
          vm["verdict"] == "REJECT" and any("CTRL-LINE-COUNT" in i for i in vm["issues"]), None)
    xt = CT.line_xtalk_budget({"rows": 2, "cols": 2})
    check("J5 逐线串扰 ACCEPT（含 XY↔Z 隔离）", xt["verdict"] == "ACCEPT",
          f"xy_z_X={xt['xy_z_isolation_X']:.2e}≤{xt['isolation_limit']}")
    xt_bad = CT.line_xtalk_budget({"rows": 2, "cols": 2, "ctrl_line_pitch": 0.1})
    check("J6 三线重叠 ⇒ 串扰/隔离 REJECT",
          xt_bad["verdict"] == "REJECT"
          and (xt_bad["xy_z_isolation_X"] > CT.CTRL_ISOLATION_LIMIT
               or xt_bad["max_intra_X"] > CT.CTRL_XTALK_LIMIT), None)

    # ════════════════ K 节：G8 阵列损耗 ════════════════
    print("── K G8 阵列损耗 + 封装（D-144）──")
    ab = S4.array_loss_budget({"rows": 2, "cols": 2})
    check("K1 合法 2×2 阵列损耗 ACCEPT（per-qubit + 封装 + 封装模规避）",
          ab["verdict"] == "ACCEPT" and ab["yield"] == 1.0,
          f"min_t1={ab['min_t1_total_us']:.1f}µs yield={ab['yield']:.2f}")
    bm = S4.array_loss_budget({"rows": 2, "cols": 2, "pkg_height_mm": 25.6})
    check("K2 封装模落 qubit 工作带 ⇒ REJECT（pkg_mode_ok=False）",
          bm["verdict"] == "REJECT" and not bm["pkg_mode_ok"], None)
    bl = S4.array_loss_budget({"rows": 2, "cols": 2, "tan_delta_pkg": 1e-3, "p_pkg": 0.5})
    check("K3 高封装损耗 ⇒ 阵列 T1 不足 ⇒ REJECT",
          bl["verdict"] == "REJECT" and bl["min_t1_total_us"] < S4.T1_TARGET_US, None)
    ab441 = S4.array_loss_budget({"rows": 21, "cols": 21})
    check("K4 规模 N=441 阵列损耗 ACCEPT（限带 qubit 工作区）",
          ab441["verdict"] == "ACCEPT" and ab441["yield"] == 1.0,
          f"min_t1={ab441['min_t1_total_us']:.1f}µs")

    # ════════════════ L 节：G2 heavy-hex（对标 IBM）════════════════
    print("── L G2 heavy-hex 拓扑（D-138）──")
    g33 = TP.heavy_hex_graph(3, 3)
    deg33 = TP.heavy_hex_degree_stats(g33)
    check("L1 3×3 heavy-hex 图：18 顶点 + 21 边 qubit = 39 qubit · 42 耦合",
          g33["n_vertices"] == 18 and g33["n_edge_qubits"] == 21
          and g33["n_qubits"] == 39 and g33["n_edges"] == 42,
          f"V={g33['n_vertices']} E={g33['n_edge_qubits']} N={g33['n_qubits']}")
    check("L2 **最大度 ≤ 3（无 4 邻居，IBM heavy-hex 定义式）** · 顶点 3 / 边 2",
          deg33["max_degree"] <= TP.HEAVYHEX_MAX_DEGREE and deg33["no_four_neighbor"]
          and deg33["vertex_deg_max"] == 3 and deg33["edge_deg_max"] == 2,
          f"maxDeg={deg33['max_degree']}")
    hc33 = TP.heavy_hex_cell({"rows": 3, "cols": 3})
    check("L3 合法 3×3 heavy-hex DRC+LVS 双 ACCEPT",
          TP.run_heavyhex_drc(hc33, g33)["verdict"] == "ACCEPT"
          and TP.heavyhex_lvs(hc33, g33)["verdict"] == "ACCEPT", None)
    bad_g = TP.heavy_hex_graph(3, 3)
    bad_g["adjacency"][0] = [1, 2, 3, 4]
    vb = TP.run_heavyhex_drc(hc33, bad_g)
    check("L4 出现 4 邻居 ⇒ DRC REJECT（SCD-TOPO-MAX-DEGREE，4>3）",
          vb["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-TOPO-MAX-DEGREE" for v in vb["violations"]), None)
    dense_hh = TP.run_heavyhex_drc(
        TP.heavy_hex_cell({"rows": 3, "cols": 3, "hex_unit": 16.0}), g33)
    check("L5 节点太挤(unit 16) ⇒ DRC REJECT（SCD-TOPO-NODE-SPACING）",
          dense_hh["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-TOPO-NODE-SPACING" for v in dense_hh["violations"]), None)
    g45 = TP.heavy_hex_graph(4, 5)
    hc45 = TP.heavy_hex_cell({"rows": 4, "cols": 5})
    check("L6 4×5 heavy-hex（40 顶点 + 51 边 qubit = 91 qubit）DRC+LVS 双 ACCEPT",
          g45["n_qubits"] == 91 and TP.run_heavyhex_drc(hc45, g45)["verdict"] == "ACCEPT"
          and TP.heavyhex_lvs(hc45, g45)["verdict"] == "ACCEPT",
          f"N={g45['n_qubits']} maxDeg={TP.heavy_hex_degree_stats(g45)['max_degree']}")
    check("L7 逐边物理 ACCEPT（J 双验证 + CR 落窗）",
          TP.heavy_hex_physics({"rows": 3, "cols": 3})["verdict"] == "ACCEPT", None)

    # ════════════════ M 节：诚实标注 + 红线（P1）════════════════
    print("── M 诚实标注 + 红线（P1）──")
    for nm, disc, keys in (
            ("G3", SC.TUNABLE_RED_LINE_DISCLOSURE,
             ("role", "layers", "limits", "lvs", "physics", "red_line")),
            ("G4", MX.RED_LINE_DISCLOSURE,
             ("role", "layers", "limits", "lvs", "physics", "mux", "red_line")),
            ("G5", CT.RED_LINE_DISCLOSURE,
             ("role", "layers", "limits", "lvs", "physics", "control", "red_line")),
            ("G2", TP.RED_LINE_DISCLOSURE,
             ("role", "layers", "limits", "lvs", "physics", "topology", "red_line"))):
        check(f"M {nm} 披露键齐备（{len(keys)} 键）",
              all(k in disc for k in keys), f"键={sorted(disc)}")
    check("M5 限值为设计规则 · 非实测 golden（各 P1 模块一致口径）",
          all("设计规则" in d["limits"] and "非实测 golden" in d["limits"]
              for d in (SC.TUNABLE_RED_LINE_DISCLOSURE, MX.RED_LINE_DISCLOSURE,
                        CT.RED_LINE_DISCLOSURE, TP.RED_LINE_DISCLOSURE)), None)
    banned = ("qiskit", "cirq", "pennylane", "strawberryfields", "thewalrus", "qutip")
    hits_p1 = []
    for fn in ("sc_coupler.py", "sc_readout_mux.py", "sc_control.py",
               "sc_topology.py", "sc_readout.py"):
        src = open(os.path.join(_HERE, "lda_qeda", fn), encoding="utf-8").read()
        hits_p1 += [(fn, b) for b in banned
                    if re.search(rf"^\s*(import|from)\s+{b}\b", src, re.M)]
    check("M6 红线：G2/G3/G4/G5/G8 零量子 SDK 依赖（纯几何 + 平台 numpy，C 级自主）",
          not hits_p1, f"命中={hits_p1 or '无'}")
    hv = TP.run_heavyhex_drc(hc33, g33)
    check("M7 判决无 LLM：verdict 为 str 死标量、violation 为 dict（零模型调用）",
          hv["verdict"] in ("ACCEPT", "REJECT")
          and all(isinstance(v, dict) and set(v) == {"rule", "detail"}
                  for v in hv["violations"]), "rule/detail 二元组 · 纯限值比对")

    # ════════════════ N 节：P1 模块 GDS round-trip ════════════════
    print("── N P1 模块 GDS 真出 + 解析 round-trip ──")
    for nm, fn, params, tag in (
            ("G3 可调耦合器", SC.tunable_coupler_gds, {}, "tunable"),
            ("G4 读出 mux", MX.mux_gds, {"rows": 2, "cols": 3}, "mux"),
            ("G5 控制多线", CT.control_gds, {"rows": 2, "cols": 3}, "control"),
            ("G2 heavy-hex", TP.heavy_hex_gds, {"rows": 3, "cols": 3}, "hex")):
        data = fn(params, os.path.join(_HERE, f"_sc_s5_{tag}_tmp.gds"))
        parsed = SR.G.parse_gds(data)
        layers = set()
        for st in parsed.get("structures", {}).values():
            layers |= set(st.get("layers", []))
        check(f"N {nm} 真出 GDSII 且含 SC 层 10/11/12",
              bool(data) and {10, 11, 12}.issubset(layers),
              f"layers={sorted(layers)} · bytes={len(data)}")

    # ════════════════ O 节：P1 规模压力 ════════════════
    print("── O P1 规模压力（N=53/127/433：mux + control + 阵列损耗）──")
    for (target, rows, cols) in SCALE_TIERS[:3]:
        t0 = time.time()
        mp = MX.mux_plan({"rows": rows, "cols": cols})
        mc = MX.mux_array_cell({"rows": rows, "cols": cols})
        md = MX.run_mux_drc(mc, mp)
        ml = MX.mux_lvs(mc, mp)
        mh = MX.mux_physics({"rows": rows, "cols": cols})
        ctl = CT.control_array_cell({"rows": rows, "cols": cols})
        cd = CT.run_control_drc(ctl)
        cl = CT.control_lvs(ctl)
        cx = CT.line_xtalk_budget({"rows": rows, "cols": cols})
        al = S4.array_loss_budget({"rows": rows, "cols": cols})
        dt = time.time() - t0
        check(f"O mux N={target}（{rows}×{cols}）规划+DRC+LVS+物理 全 ACCEPT",
              mp["verdict"] == "ACCEPT" and md["verdict"] == "ACCEPT"
              and ml["verdict"] == "ACCEPT" and mh["verdict"] == "ACCEPT",
              f"音间隔={mp['min_tone_spacing_mhz']:.0f}MHz · {dt:.2f}s")
        check(f"O control N={target} DRC+LVS+串扰 全 ACCEPT",
              cd["verdict"] == "ACCEPT" and cl["verdict"] == "ACCEPT"
              and cx["verdict"] == "ACCEPT",
              f"xy_z={cx['xy_z_isolation_X']:.2e}")
        check(f"O 阵列损耗 N={target} ACCEPT（min T1 ≥ 目标 · 良率 1.0）",
              al["verdict"] == "ACCEPT" and al["yield"] == 1.0,
              f"min_t1={al['min_t1_total_us']:.1f}µs")
    # 千比特级：阵列损耗（廉价项）单点复核（mux/control 的 1024 规模由 demo 覆盖）
    al1024 = S4.array_loss_budget({"rows": 32, "cols": 32})
    check("O 千比特级 N=1024 阵列损耗 ACCEPT（限带工作区 + 封装模规避）",
          al1024["verdict"] == "ACCEPT" and al1024["yield"] == 1.0
          and al1024["n_qubits"] == 1024,
          f"N={al1024['n_qubits']} min_t1={al1024['min_t1_total_us']:.1f}µs")

    # ════════════════ P 节：统一拓扑 DRC/LVS 框架（D-145 · 方阵 + heavy-hex 共用）════════════════
    print("── P 统一拓扑框架（D-145 · 方阵 + heavy-hex 共用 DRC/LVS）──")
    try:
        ok_core = TC.run_selfchecks(verbose=False)
    except Exception as e:                                           # noqa: BLE001
        ok_core = False
        print(f"  topology_core 自检异常：{type(e).__name__}: {e}")
    check("P1 topology_core（D-145 统一框架）自检全 PASS", ok_core, "期望 13 项全 PASS")

    tg33 = TC.grid_topology(3, 3)
    dg33 = TC.topology_degree_stats(tg33)
    check("P2 方阵实例 3×3：9 节点 · 12 耦合 · maxDeg=4 · 度上限声明 4",
          tg33["n_qubits"] == 9 and tg33["n_couplings"] == 12
          and dg33["max_degree"] == 4 and tg33["max_degree_limit"] == 4
          and dg33["within_limit"],
          f"N={tg33['n_qubits']} E={tg33['n_couplings']} maxDeg={dg33['max_degree']}")
    check("P3 heavy-hex 实例 3×3：39 qubit · 42 耦合 · maxDeg=3 · 度上限声明 3",
          g33["n_qubits"] == 39 and g33["n_couplings"] == 42
          and deg33["max_degree"] == 3 and g33["max_degree_limit"] == 3,
          f"maxDeg={deg33['max_degree']}")
    # 方阵实例与 S3 口径一致（耦合数 = rows(cols−1)+cols(rows−1)）
    grid_ok = all(
        TC.grid_topology(r, c)["n_qubits"] == r * c
        and TC.grid_topology(r, c)["n_couplings"] == r * (c - 1) + c * (r - 1)
        for (r, c) in ((2, 2), (3, 3), (7, 8)))
    check("P4 方阵实例与 S3 口径一致（2×2/3×3/7×8 耦合数闭式）", grid_ok, None)
    # 统一引擎对两种拓扑
    cg33 = TC.topology_cell(tg33)
    check("P5 **统一 DRC/LVS/物理** 对方阵 ACCEPT（与 heavy-hex 同一份代码）",
          TC.run_topology_drc(cg33, tg33)["verdict"] == "ACCEPT"
          and TC.topology_lvs(cg33, tg33)["verdict"] == "ACCEPT"
          and TC.topology_physics(tg33)["verdict"] == "ACCEPT", None)
    check("P6 **统一 DRC/LVS/物理** 对 heavy-hex ACCEPT（同一份代码）",
          TC.run_topology_drc(hc33, g33)["verdict"] == "ACCEPT"
          and TC.topology_lvs(hc33, g33)["verdict"] == "ACCEPT"
          and TC.topology_physics(g33)["verdict"] == "ACCEPT", None)
    check("P7 规则名统一：SCD-TOPO-NODE-SPACING / SCD-TOPO-MAX-DEGREE 在册（S1 四则 + TOPO 两则 = 6）",
          len(TC.TOPOLOGY_DRC_RULES) == 6
          and "SCD-TOPO-NODE-SPACING" in TC.TOPOLOGY_DRC_RULES
          and "SCD-TOPO-MAX-DEGREE" in TC.TOPOLOGY_DRC_RULES
          and not any("HEAVYHEX" in r for r in TC.TOPOLOGY_DRC_RULES),
          f"规则={list(TC.TOPOLOGY_DRC_RULES)}")
    # 度上限按拓扑声明：方阵 5>4 / hex 4>3
    bad_g2 = TC.grid_topology(3, 3)
    bad_g2["adjacency"][0] = [1, 2, 3, 4, 5]
    vg = TC.run_topology_drc(cg33, bad_g2)
    check("P8 度超上限 ⇒ DRC REJECT（方阵 5>4 · 声明式上限）",
          vg["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-TOPO-MAX-DEGREE" for v in vg["violations"]), None)
    dense_g = TC.grid_topology(3, 3, pitch_x=12.0, pitch_y=8.0)
    vdg = TC.run_topology_drc(TC.topology_cell(dense_g), dense_g)
    check("P9 方阵节点太挤 ⇒ DRC REJECT（SCD-TOPO-NODE-SPACING）",
          vdg["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-TOPO-NODE-SPACING" for v in vdg["violations"]), None)
    # 统一 GDS round-trip（方阵）
    dg_gds = TC.topology_gds(tg33, {}, os.path.join(_HERE, "_sc_s5_grid_tmp.gds"))
    pg = SR.G.parse_gds(dg_gds)
    glayers = set()
    for st in pg.get("structures", {}).values():
        glayers |= set(st.get("layers", []))
    check("P10 统一框架 GDS 真出（方阵）且含 SC 层 10/11/12",
          bool(dg_gds) and {10, 11, 12}.issubset(glayers),
          f"layers={sorted(glayers)} · bytes={len(dg_gds)}")
    # 方阵规模（7×8）统一 DRC/LVS
    t78 = TC.grid_topology(7, 8)
    c78 = TC.topology_cell(t78)
    check("P11 方阵规模 7×8 统一 DRC+LVS 双 ACCEPT（56 qubit · 97 耦合）",
          t78["n_qubits"] == 56 and t78["n_couplings"] == 97
          and TC.run_topology_drc(c78, t78)["verdict"] == "ACCEPT"
          and TC.topology_lvs(c78, t78)["verdict"] == "ACCEPT",
          f"N={t78['n_qubits']} E={t78['n_couplings']}")

    print()
    print(f"超导征程 S5 门禁 smoke（D-137..D-145）：{PASS}/{PASS + FAIL} PASS")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
