#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""容错编译层 门禁 smoke（D-218 · 净增 0 锚 · 能力层 + 整数恒等判据）。

═══ 判什么（分五节 · 16 条）═══
A 自检与门集 3 · X 路由与恒等式 5 · G 调度与覆盖 3 · H 资源与跨模块 3 · Z 负结果与红线 2。

🔴 **本门禁刻意只判整数与集合**（D3 裁决的落地）：
  · **不判浮点保真**——D3 已证伪：编译后总保真的两条独立实现只差 3–53 ulp，
    而跨平台判据线是 1e4·ulp ⇒ 原理上不可复现；
  · **不把深度当锚**——调度深度下界是整数或精确有理，闭式 vs 枚举差恒 0（resid ≡ 0）；
  · 只判：门计数守恒（I1）· 距离恒等（I2）· 置换复原（I3）· 同层不冲突（I4）·
    覆盖守恒（I5）· 边上合法性（I6）· T 态平衡（I7）。

🔴 **H2 是本门禁的跨模块对拍**：资源报告里的 `2d²−1` 必须与 `surface_code.rotated_surface_code(d)`
的真实输出（`n_data + n_stab`）逐点相等 —— 任一侧漂移当场红。

🔴 命名纪律：节标签 A/X/G/H/Z —— 避开 B/E/S（账本锚号前缀），防 K4 文本代理虚高覆盖。
"""

from __future__ import annotations

import io
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check          # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")


def _read(rel):
    fp = os.path.join(_HERE, rel)
    if not os.path.exists(fp):
        return ""
    with io.open(fp, encoding="utf-8", errors="replace") as f:
        return f.read()


def _grid_adj():
    from lda_qeda import sc_topology_core as TC
    return TC.grid_topology(3, 4)["adjacency"]


def main():
    from lda_qeda import ft_compiler as FT

    adj = _grid_adj()

    # ═══════════════ A 自检与门集 ═══════════════
    check("A1 模块自检 12/12 PASS", FT.run_selfchecks(verbose=False),
          "门集/路由/恒等式/调度/资源/负结果/护栏")

    c = FT.make_circuit([("H", 0), ("CX", 0, 1), ("T", 1), ("M", 0)])
    ck = FT.check_gate_set(c)
    check("A2 门集闭包：合法线路通过 ∧ 未登记门被拒",
          ck["ok"] is True and ck["bad_gates"] == []
          and _rejects(lambda: FT.make_circuit([("SWAP", 0, 1)])),
          "n_ops=%d n_qubits=%d" % (ck["n_ops"], ck["n_qubits"]))

    c_idle = FT.make_circuit([("H", 0), ("H", 2)])
    ck2 = FT.check_gate_set(c_idle)
    check("A3 空闲逻辑比特：允许通过但如实报告 idle_qubits=[1]",
          ck2["ok"] is True and ck2["idle_qubits"] == [1] and ck2["contiguous"] is False,
          "idle=%s contiguous=%s" % (ck2["idle_qubits"], ck2["contiguous"]))

    # ═══════════════ X 路由与恒等式 ═══════════════
    p = FT.bfs_path(adj, 0, 2)
    check("X1 BFS 最短路为整数跳数（0→2 距 2）",
          isinstance(p, list) and len(p) - 1 == 2, "path=%s" % (p,))

    r = FT.compile_circuit(FT.make_circuit([("H", 0), ("CX", 0, 2), ("T", 2),
                                            ("CX", 1, 3), ("M", 3)]), adj)
    idn = FT.integer_identities(r, adj, n_T_gates=1)

    check("X2 I1 门计数守恒：n_ops_out == n_gates_in + 3·n_swap（含恢复 SWAP）",
          idn["checks"]["I1_gate_count"]["pass"],
          "in=%d swap=%d out=%d" % (r["n_gates_in"], r["n_swap"], r["n_ops_out"]))

    check("X3 I2 路由距离恒等：逐对 n_swap == dist−1",
          idn["checks"]["I2_route_distance"]["pass"],
          "路由对数=%d" % len(r["route_checks"]))

    check("X4 I3 置换复原：restore ⇒ mapping_final 与 initial 逐键相等",
          r["restored"] and idn["checks"]["I3_mapping"]["pass"]
          and r["mapping_final"] == r["mapping_initial"],
          "n_logical=%d" % r["n_logical"])

    check("X5 I6 拓扑合法性：所有 CX 的物理对 ∈ 硬件 adjacency",
          idn["checks"]["I6_topology_edge"]["pass"],
          "n_cx=%d" % sum(1 for o in r["ops"] if o["kind"] == "CX"))

    # ═══════════════ G 调度与覆盖 ═══════════════
    check("G1 I4 分层合法性：同层任意两 op 不共享物理比特",
          idn["checks"]["I4_layer_disjoint"]["pass"],
          "层数=%d" % r["depth"])

    check("G2 I5 覆盖守恒：每个 op 恰出现一次且恰在一层",
          idn["checks"]["I5_cover"]["pass"],
          "ops=%d" % len(r["ops"]))

    r_par = FT.compile_circuit(FT.make_circuit([("H", 0), ("H", 1), ("H", 2)]), adj)
    check("G3 真并行（非串行兜底）：三个独立 1q 门 ⇒ depth=1",
          r_par["depth"] == 1 and len(r_par["layers"][0]) == 3,
          "depth=%d 层0_op数=%d" % (r_par["depth"], len(r_par["layers"][0])))

    # ═══════════════ H 资源与跨模块 ═══════════════
    rep = FT.resource_report(r, d=3)
    check("H1 资源报告全整数：2d²−1=17 ∧ n_physical=4·17=68 ∧ n_slots=depth",
          rep["phys_per_patch"] == 17 and rep["n_physical"] == 68
          and rep["n_slots"] == r["depth"]
          and all(isinstance(rep[k], int) for k in ("phys_per_patch", "n_physical", "n_slots")),
          "n_physical=%d slots=%d" % (rep["n_physical"], rep["n_slots"]))

    from lda_qeda import surface_code as SC
    mism = []
    for d in (3, 5, 7):
        s = SC.rotated_surface_code(d)
        if s["n_data"] + s["n_stab"] != 2 * d * d - 1:
            mism.append(d)
    check("H2 🔴 跨模块对拍：surface_code 的 n_data+n_stab ≡ 2d²−1（d=3/5/7 逐点）",
          not mism, "违例 d=%s" % (mism,))

    from lda_qeda import sc_topology_core as TC
    hh = TC.heavy_hex_topology(3, 3)["adjacency"]
    r_hh = FT.compile_circuit(FT.make_circuit([("H", 0), ("CX", 0, 5), ("T", 5)]), hh)
    id_hh = FT.integer_identities(r_hh, hh, n_T_gates=1)
    check("H3 拓扑无关：heavy-hex（maxDeg=3）上同一线路恒等式仍全过",
          id_hh["all_pass"] and r_hh["n_logical"] == 6,
          "swap=%d depth=%d" % (r_hh["n_swap"], r_hh["depth"]))

    # ═══════════════ Z 负结果与红线 ═══════════════
    w = FT.why_not_anchored()
    check("Z1 负结果机器化：anchorable=False ∧ 四类判死齐备 ∧ 重评条件",
          w["anchorable"] is False and len(w["four_dead_classes"]) == 4
          and all("replacement" in x for x in w["four_dead_classes"])
          and "revisit_condition" in w,
          "四类=%s" % [x["class"] for x in w["four_dead_classes"]])

    src = _read(os.path.join("lda_qeda", "ft_compiler.py"))
    banned = ("numpy", "scipy", "qiskit", "cirq", "pennylane", "qutip",
              "requests", "urllib", "socket", "openai", "anthropic")
    hit = [b for b in banned
           if ("import %s" % b) in src.lower() or ("from %s" % b) in src.lower()]
    guard = 0
    for bad in (lambda: FT.place_layout(999, adj),
                lambda: FT.resource_report(r, d=0),
                lambda: FT.bfs_path(adj, 0, 999)):
        try:
            bad()
        except ValueError:
            guard += 1
    check("Z2 红线：零第三方/零网络/零 LLM ∧ 三例非法输入均抛错 ∧ 无浮点判决",
          (not hit) and guard == 3 and "open(" not in src,
          "hit=%s guard=%d/3" % (hit, guard))

    bad_n = globals().get("FAIL", 0)
    good_n = globals().get("PASS", 0)
    print("")
    print("容错编译层 门禁 smoke（D-218）：%d PASS / %d FAIL" % (good_n, bad_n))
    return 0 if bad_n == 0 else 1


def _rejects(fn) -> bool:
    try:
        fn()
        return False
    except ValueError:
        return True


if __name__ == "__main__":
    sys.exit(main())
