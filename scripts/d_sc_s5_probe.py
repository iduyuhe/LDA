"""D-137/D-142/D-143 突变探针（scratch · 不入 CI）：证明 run_schip_s5_smoke.py 能变红。

惯例：scripts/*_probe.py 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块函数（**不碰源文件** ⇒ 无需文件还原/哈希复核），
逐条造假后重跑门禁，确认 exit≠0 且 [FAIL] 计数 > 0。全绿门禁无此反证 = 不可信。

🔴 教训（见 d_sc_s1..s4_probe.py 文件头）：探针必须 patch 门禁**同一模块对象**
（SM.SR / SM.FA）——门禁走 `from lda_qeda import sc_routing as SR`，另起
`from lda_qeda import sc_routing` 会拿到不同实例 ⇒ 假绿。故一律经 SM 取对象。

人工记录（改动 → 应红判据）：
  · M1 run_routing_drc 恒 ACCEPT     ⇒ B2/B3/B4（路由 DRC 违规漏判）应红
  · M2 routed_array_lvs 恒 ACCEPT    ⇒ C3/C4/C5（LVS 违规漏判）应红
  · M3 routing_capacity 错值         ⇒ F9（路由容量自洽）应红
  · M4 路由披露缺 routing 键         ⇒ D1（披露缺漏）应红
  · M5 routed_gds 返空字节           ⇒ E1（GDS 真出失败）应红
  · M6 FA.check_plan 恒 ok=True      ⇒ A2（频率自检：碰撞/共振/近邻漏检）应红
  · M7 FA.plan 恒 REJECT             ⇒ F 四个规模的频率规划应红
  ── S5 P1（D-138/139/140/141/144）──────────────────────────────
  · M8  MX.mux_plan 恒合规            ⇒ I3（音密）/I4（保护带）应红
  · M9  MX.mux_lvs 恒 ACCEPT          ⇒ I5（同馈线重音）/I1 应红
  · M10 CT.control_lvs 恒 ACCEPT      ⇒ J4（缺 Z 线）/J1 应红
  · M11 TP.heavy_hex_graph 退化（丢边中点）⇒ L1/L2/L3/L6（拓扑形状）应红
  · M12 S4.array_loss_budget 恒 ACCEPT ⇒ K2（封装模落带）/K3（T1 不足）应红
  · M13 SC.run_tunable_drc 恒 ACCEPT   ⇒ H3（少一结）/H4（flux 贴环）应红
  · M14 SC.squid_ej 恒常量             ⇒ H6（SQUID 闭式）应红
  · M15 TP.run_heavyhex_drc 恒 ACCEPT  ⇒ L4/L5 应红
  ── S5 第三波 · 完善（D-145 统一拓扑框架）─────────────────────
  · M16 TC.topology_degree_stats 恒合规 ⇒ P8（度上限声明式判据漏判）应红
  · M17 TC.run_topology_drc 恒 ACCEPT   ⇒ P5/P6/P8/P9 应红
  · M18 TC.grid_topology 少边（丢纵向）  ⇒ P4/P11（方阵与 S3 口径一致）应红
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_schip_s5_smoke as SM                            # noqa: E402

SR = SM.SR
FA = SM.FA
SC = SM.SC
MX = SM.MX
CT = SM.CT
TP = SM.TP
S4 = SM.S4
TC = SM.TC


def run_smoke() -> int:
    SM.PASS = 0
    SM.FAIL = 0
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = SM.main()
    return rc


def _accept_drc(els, limits=None):
    return {"verdict": "ACCEPT", "violations": [], "n_rules": len(SR.ROUTING_DRC_RULES),
            "limits": SR.DEFAULT_ROUTING_LIMITS, "checked": 0}


def _accept_lvs(els):
    return {"verdict": "ACCEPT", "issues": [],
            "netlist": {"qubit_nets": 4, "feedline_segments": 2, "readout": 4,
                        "control": 4, "pads_control": 4, "pads_total": 6, "coupler": 4,
                        "ground_nets": 1, "edges_bridged": 4},
            "n_checks": 11}


def _make_mutations():
    orig = {
        "drc": SR.run_routing_drc,
        "lvs": SR.routed_array_lvs,
        "cap": SR.routing_capacity,
        "disc": SR.RED_LINE_DISCLOSURE,
        "gds": SR.routed_gds,
        "check": FA.check_plan,
        "plan": FA.plan,
    }

    def m1():
        SR.run_routing_drc = _accept_drc

    def m2():
        SR.routed_array_lvs = _accept_lvs

    def m3():
        def bad(p=None):
            r = orig["cap"](p)
            r["n_signals"] = 0
            r["pitch_y_eff_um"] = 0.0
            return r
        SR.routing_capacity = bad

    def m4():
        SR.RED_LINE_DISCLOSURE = {k: v for k, v in orig["disc"].items()
                                  if k != "routing"}

    def m5():
        SR.routed_gds = lambda *a, **k: b""

    def m6():
        o = orig["check"]

        def bad(freqs, edges, params=None):
            r = o(freqs, edges, params)
            r["ok"] = True
            r["n_collisions"] = 0
            r["n_resonance_hits"] = 0
            r["nn_violations"] = []
            r["detune_violations"] = []
            return r
        FA.check_plan = bad

    def m7():
        o = orig["plan"]

        def bad(params=None):
            r = o(params)
            r["verdict"] = "REJECT"
            return r
        FA.plan = bad

    orig.update({
        "mx_plan": MX.mux_plan, "mx_lvs": MX.mux_lvs,
        "ct_lvs": CT.control_lvs, "tp_deg": TP.heavy_hex_degree_stats,
        "s4_alb": S4.array_loss_budget, "sc_drc": SC.run_tunable_drc,
        "sc_ej": SC.squid_ej, "tp_drc": TP.run_heavyhex_drc,
    })

    def m8():
        o = orig["mx_plan"]

        def bad(params=None):
            r = o(params)
            r["spacing_ok"] = True
            r["guard_ok"] = True
            r["verdict"] = "ACCEPT"
            return r
        MX.mux_plan = bad

    def m9():
        o = orig["mx_lvs"]

        def bad(els, plan=None):
            r = o(els, plan)
            r["verdict"] = "ACCEPT"
            r["issues"] = []
            return r
        MX.mux_lvs = bad

    def m10():
        o = orig["ct_lvs"]

        def bad(els):
            r = o(els)
            r["verdict"] = "ACCEPT"
            r["issues"] = []
            return r
        CT.control_lvs = bad

    def m11():
        o = orig["tp_graph"]

        def bad(rows=3, cols=3, unit_um=TP.DEFAULT_HEX_UNIT_UM):
            g = o(rows, cols, unit_um)
            # 丢掉边中点 qubit ⇒ 退化为纯蜂窝骨架（不再是 heavy-hex）
            pos = {n: xy for n, xy in g["positions"].items() if g["kind"][n] == "vertex"}
            pairs = [(a, b) for (a, b) in g["couplers"] if a in pos and b in pos]
            return TC._finalize("heavy-hex-degraded", pos,
                                {n: "vertex" for n in pos}, pairs,
                                g["max_degree_limit"],
                                {"rows": rows, "cols": cols,
                                 "unit_um": unit_um, "n_vertices": len(pos),
                                 "n_edge_qubits": 0, "edges": [], "n_edges": 0})
        TP.heavy_hex_graph = bad

    def m12():
        o = orig["s4_alb"]

        def bad(params=None):
            r = o(params)
            r["verdict"] = "ACCEPT"
            r["pkg_mode_ok"] = True
            r["yield"] = 1.0
            r["min_t1_total_us"] = 999.0
            return r
        S4.array_loss_budget = bad

    def m13():
        o = orig["sc_drc"]

        def bad(els, limits=None):
            r = o(els, limits)
            r["verdict"] = "ACCEPT"
            r["violations"] = []
            return r
        SC.run_tunable_drc = bad

    def m14():
        SC.squid_ej = lambda a, b, f: 7.0       # 破坏 SQUID 闭式（E_J(0)≠2E_J0）

    def m15():
        o = orig["tp_drc"]

        def bad(els, graph=None, limits=None):
            r = o(els, graph, limits)
            r["verdict"] = "ACCEPT"
            r["violations"] = []
            return r
        TP.run_heavyhex_drc = bad

    orig.update({
        "tp_graph": TP.heavy_hex_graph,
        "tc_deg": TC.topology_degree_stats, "tc_drc": TC.run_topology_drc,
        "tc_grid": TC.grid_topology,
    })

    def m16():
        o = orig["tc_deg"]

        def bad(topo):
            r = o(topo)
            r["max_degree"] = topo["max_degree_limit"]
            r["within_limit"] = True
            return r
        TC.topology_degree_stats = bad

    def m17():
        o = orig["tc_drc"]

        def bad(els, topo, limits=None):
            r = o(els, topo, limits)
            r["verdict"] = "ACCEPT"
            r["violations"] = []
            return r
        TC.run_topology_drc = bad

    def m18():
        o = orig["tc_grid"]

        def bad(rows=3, cols=3, pitch_x=22.0, pitch_y=14.0):
            r = o(rows, cols, pitch_x, pitch_y)
            cols_i = int(cols)
            pairs = [(i, j) for (i, j) in r["couplers"]
                     if j - i == 1 and (i % cols_i) != (cols_i - 1)]
            return TC._finalize("grid", r["positions"], r["kind"], pairs,
                                r["max_degree_limit"],
                                {"rows": rows, "cols": cols})
        TC.grid_topology = bad

    def restore():
        SR.run_routing_drc = orig["drc"]
        SR.routed_array_lvs = orig["lvs"]
        SR.routing_capacity = orig["cap"]
        SR.RED_LINE_DISCLOSURE = orig["disc"]
        SR.routed_gds = orig["gds"]
        FA.check_plan = orig["check"]
        FA.plan = orig["plan"]
        MX.mux_plan = orig["mx_plan"]
        MX.mux_lvs = orig["mx_lvs"]
        CT.control_lvs = orig["ct_lvs"]
        TP.heavy_hex_degree_stats = orig["tp_deg"]
        TP.heavy_hex_graph = orig["tp_graph"]
        S4.array_loss_budget = orig["s4_alb"]
        SC.run_tunable_drc = orig["sc_drc"]
        SC.squid_ej = orig["sc_ej"]
        TP.run_heavyhex_drc = orig["tp_drc"]
        TC.topology_degree_stats = orig["tc_deg"]
        TC.run_topology_drc = orig["tc_drc"]
        TC.grid_topology = orig["tc_grid"]

    muts = [("M1-路由DRC恒ACCEPT", m1), ("M2-路由LVS恒ACCEPT", m2),
            ("M3-路由容量错值", m3), ("M4-路由披露缺键", m4),
            ("M5-路由GDS空", m5), ("M6-频率校验恒ok", m6),
            ("M7-频率规划恒REJECT", m7),
            ("M8-读出mux音规划恒合规", m8), ("M9-读出mux LVS恒ACCEPT", m9),
            ("M10-控制多线LVS恒ACCEPT", m10), ("M11-heavyhex拓扑退化(丢边中点)", m11),
            ("M12-阵列损耗恒ACCEPT", m12), ("M13-可调耦合器DRC恒ACCEPT", m13),
            ("M14-SQUID闭式失效", m14), ("M15-heavyhex DRC恒ACCEPT", m15),
            ("M16-拓扑度统计恒合规", m16), ("M17-统一拓扑DRC恒ACCEPT", m17),
            ("M18-方阵拓扑少边", m18)]
    return muts, restore


def main() -> int:
    print("=" * 78)
    print("D-137..D-145 S5 门禁 突变探针（18 突变各必红 · 还原复绿）")
    print("=" * 78)

    rc0 = run_smoke()
    base_green = (rc0 == 0)
    print(f"[基线] smoke 返回 {rc0}（期望 0=全绿）· {'绿' if base_green else '基线红(异常)'}")
    if not base_green:
        return 1

    muts, restore = _make_mutations()
    all_red = True
    for name, apply in muts:
        apply()
        rc = run_smoke()
        reddened = (rc != 0)
        all_red = all_red and reddened
        print(f"[{name}] 突变后 smoke 返回 {rc} · {'红(断言活)' if reddened else '仍绿(死断言!)'}")
        restore()

    rc2 = run_smoke()
    restored_green = (rc2 == 0)
    print(f"[还原] smoke 返回 {rc2} · {'复绿' if restored_green else '未复绿'}")
    ok = base_green and all_red and restored_green
    print()
    print(f"突变探针结论：基线绿={base_green} · 18 突变各红={all_red} · 还原绿={restored_green}"
          f" => {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
