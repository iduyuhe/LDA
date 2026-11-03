# -*- coding: utf-8 -*-
"""S4 门禁：**结构级 Verilog 子集解析器**（gate-level · 网表入口 → dsynth.Netlist · 往返零丢失）。

═══════════════════════════════════════════════════════════════════════════════
这一版要证明什么
───────────────────────────────────────────────────────────────────────────────
`dverilog.py` 是 S3 的「Verilog 子集」—— ISCAS/EPFL 这类**门级网表**的入口。它与
`drtl.py` 的 RTL 子集（走 `dsynth.synth` 综合）**分工**，两者汇合点是 `dsynth.Netlist`
（数字链唯一的门级网表结构）。本模块**直接产出它**，让 B3 干线 `place→route→drc`
能「吃上一段的输出」。判据只问四件事：

  S1 **字节级往返双射**：`parse → serialize → re-parse` **逐位相等**
      （`serialize(reparse(serialize(x))) == serialize(x)`），门按名排序吐回，非靠归一化。
  S2 **零数据丢失不变量**：c17 样本 parse 后，门数 / 网数 / 连通性（每颗门 in→out）
      在往返后**完全守恒**——把「没静默丢」从口头承诺变成机核判据。
  S3 **未知语法必报错**：未闭合 endmodule / 非法原语 / 升序向量 / 把输出端口当输入引用 /
      缺 `;` —— 一律抛 `VerilogSyntaxError`（带位置），绝不静默降级。
  S4 **适配器正确 + 反向探针**：`to_model()` 把 `dsynth.Netlist` 转成 S1 `Layout`
      （每颗门 → Instance、每条网 → Net），断言门数与 Netlist 一致；反向探针断言
      精确连通性（g10 = NAND2、out=n10、ins=(n1,n3)），证明连通性是真从源读的不是默认。

诚实边界
────────
· **不综合、不求值**：本模块只忠实转成 `dsynth.Netlist`（连通性容器），不做逻辑仿真
  （那是 `dsynth.sim_netlist`/`drtl.rtl_eval_all` 的事）；一旦它开始算，就会变成「第二套实现」。
· **几何在 LEF/布局阶段**：本模块给的 Netlist 没有坐标；坐标由 `dplac.place` 产生。
· **物理链建模边界**：`PHYSICALLY_MODELED={INV,NAND2}`（dcell.CELLS 含真实几何），
  其余原语（AND/OR/...）在物理链上是「未建模」⇒ 放置/布线阶段如实计数跳过，不静默当 INV。
· **C 级自主**：纯标准库 + 复用 `drtl.tokenize`（同一词法器，零第三方依赖），LLM 不进判决路径。
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_l2.ecore import dverilog as DV                       # noqa: E402
from lda_l2.ecore import dplac                                # noqa: E402

_FALS: list = []
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   record=_FALS)
T0 = time.time()
AN_ELAPSED_MAX_S = 30.0


def _expect_raises(src, want_pos=False):
    """返回 (raised:bool, pos:int)。`want_pos` 时还要求 pos>0（带位置）。"""
    try:
        DV.parse(src)
    except DV.VerilogSyntaxError as ex:
        pos = ex.pos
        return (True, pos) if (not want_pos or pos > 0) else (False, pos)
    return (False, 0)


def _distinct_nets(nl):
    s = set()
    for g in nl.gates:
        s.add(g.out)
        s.update(g.ins)
    return s


def main() -> int:
    NL = DV.parse(DV.SAMPLE_VERILOG)

    # ── S0 解析成功 + 顶层结构 ──────────────────────────────────────────
    check("S0 解析 SAMPLE_VERILOG 成功（ISCAS-85 c17 · 5×NAND2 + 1×INV）",
          NL is not None, "parse 返回空")
    n_gate = len(NL.gates)
    n_in = len(NL.inputs)
    n_out = len(NL.outputs)
    check("S0b 结构首遍计数：6 gate / 5 input / 2 output",
          (n_gate, n_in, n_out) == (6, 5, 2),
          "得到 (%d,%d,%d)" % (n_gate, n_in, n_out))

    # ── S1 字节级往返双射 ─────────────────────────────────────────────
    ser1 = DV.serialize(NL)
    NL2 = DV.parse(ser1)
    ser2 = DV.serialize(NL2)
    check("S1 字节级往返双射：`serialize(reparse(serialize)) == serialize`"
          "（门按名排序吐回，非靠归一化）",
          ser2 == ser1, "两遍 serialize 不相等（信息被悄悄变形）")
    NL3 = DV.parse(ser2)
    ser3 = DV.serialize(NL3)
    check("S1b 幂等：第三遍 serialize 仍与首遍逐位相等",
          ser3 == ser1, "幂等失败")

    # ── S2 零数据丢失不变量：往返后门数 / 连通性守恒 ─────────────────────
    g2 = {(g.name, g.cell, g.out, g.ins) for g in NL2.gates}
    g1 = {(g.name, g.cell, g.out, g.ins) for g in NL.gates}
    check("S2 零数据丢失：门实例（名/原语/输出/输入）逐颗守恒",
          g1 == g2, "reparse 门集合 != 原门集合")
    nets1 = _distinct_nets(NL)
    nets2 = _distinct_nets(NL2)
    check("S2b 零数据丢失：网名集合守恒（%d 条网）" % len(nets1),
          nets1 == nets2, "reparse nets=%s" % (nets2,))

    # ── S3 各类结构都被识别、无静默丢弃 ───────────────────────────────
    by_cell = {}
    for g in NL.gates:
        by_cell[g.cell] = by_cell.get(g.cell, 0) + 1
    check("S3a 原语映射正确：5×NAND2 + 1×INV（INV/NAND2 在 PHYSICALLY_MODELED）",
          by_cell.get("NAND2") == 5 and by_cell.get("INV") == 1
          and "NAND2" in DV.PHYSICALLY_MODELED and "INV" in DV.PHYSICALLY_MODELED,
          "by_cell=%s modeled=%s" % (by_cell, sorted(DV.PHYSICALLY_MODELED)))
    # 输入端口与输出端口名都被识别
    in_ports = {p for (p, _w) in NL.inputs}
    out_ports = set(NL.outputs.keys())
    check("S3b 端口被识别：input={n1,n2,n3,n6,n7} · output={n22,n23}",
          in_ports == {"n1", "n2", "n3", "n6", "n7"} and out_ports == {"n22", "n23"},
          "in=%s out=%s" % (in_ports, out_ports))

    # ── S3 严格报错：6 类反例必抛 VerilogSyntaxError（带位置）───────────
    r_unclosed = _expect_raises("module m(a); input a; wire b;", want_pos=True)
    check("S3c 未闭合 endmodule（模块体未终结）→ 必报错（带位置）",
          r_unclosed[0], "未报错")

    r_badprim = _expect_raises(
        "module m(a); input a; foo g(z,a); endmodule", want_pos=True)
    check("S3d 非法原语（foo）→ 必报错（带位置）",
          r_badprim[0], "未报错")

    r_asc = _expect_raises("module m(a); input [0:3] a; endmodule", want_pos=True)
    check("S3e 升序向量 [0:3]（只支持降序 [N-1:0]）→ 必报错（带位置）",
          r_asc[0], "未报错")

    r_outin = _expect_raises(
        "module m(a,y); input a; output y; nand g(y,a,y); endmodule", want_pos=True)
    check("S3f 输出端口被当输入引用 → 必报错（带位置）",
          r_outin[0], "未报错")

    r_nosemi = _expect_raises("module m(a) input a endmodule", want_pos=True)
    check("S3g 缺 `;`（module 头无 ;）→ 必报错（带位置，不静默）",
          r_nosemi[0], "未报错")

    # 多比特端口合法拆位（位选门引用往返）
    bus_src = ("module m(a,b,y); input [1:0] a; input b; output [1:0] y; "
               "nand g0(y[0],a[0],b); nand g1(y[1],a[1],b); endmodule")
    nl_bus = DV.parse(bus_src)
    ser_bus = DV.serialize(nl_bus)
    nl_bus2 = DV.parse(ser_bus)
    ser_bus2 = DV.serialize(nl_bus2)
    check("S3h 多比特端口拆位 + 位选门引用：往返逐位一致",
          ser_bus == ser_bus2 and len(nl_bus.gates) == 2,
          "byte_faithful=%s gates=%d" % (ser_bus == ser_bus2, len(nl_bus.gates)))
    check("S3i 多比特拆位：input a 拆成 a[0]/a[1]，gate 引用 y[0]/a[0] 正确对齐",
          nl_bus.in_nets == {("a", 0): "a[0]", ("a", 1): "a[1]", ("b", 0): "b"}
          and nl_bus.outputs == {"y": ("y[0]", "y[1]")},
          "in_nets=%s outputs=%s" % (nl_bus.in_nets, nl_bus.outputs))

    # ── S4 适配器 to_model 正确 + 反向探针（精确连通性，非默认值）──────────
    layout = DV.to_model(NL)
    check("S4a to_model 产出 Layout · 实例数 == 门数（6）",
          len(layout.instances) == 6, "instances=%d" % len(layout.instances))
    # 反向探针：精确连通性，证明不是默认
    g10 = next((g for g in NL.gates if g.name == "g10"), None)
    check("S4b 反向探针：g10 = NAND2 · out=n10 · ins=(n1,n3)（精确连通性）",
          g10 is not None and g10.cell == "NAND2" and g10.out == "n10"
          and g10.ins == ("n1", "n3"),
          "g10=%r" % (g10,))
    g23 = next((g for g in NL.gates if g.name == "g23"), None)
    check("S4c 反向探针：g23 = INV · out=n23 · ins=(n16,)",
          g23 is not None and g23.cell == "INV" and g23.out == "n23"
          and g23.ins == ("n16",),
          "g23=%r" % (g23,))

    # ── S5 链路咬合：parse 输出（Netlist）能被 dplac.place 直接消费 ────────
    p = dplac.place(NL)  # 默认 tech=DC.DEFAULT_TECH
    check("S5 链路咬合：dplac.place(parse 输出) 覆盖全部 6 颗门"
          "（Netlist 真正喂进数字链，非另起一份）",
          len(p.cell_xywh) == len(NL.gates),
          "placed=%d gates=%d" % (len(p.cell_xywh), len(NL.gates)))

    # ── S0t 耗时红线 ───────────────────────────────────────────────────
    dt = time.time() - T0
    check("S0t 门禁耗时 %.2f s < %.0f s" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, "%.2f s" % dt)

    print()
    print("  [模块] dverilog · 纯标准库 · C 级自主 · LLM 不进判决路径")
    print("  [S1] 字节级往返双射（serialize(reparse(serialize))==serialize）+ 幂等")
    print("  [S2] 零数据丢失不变量（门实例 / 网名集合守恒）")
    print("  [S3] 未知语法必报错（未闭合/非法原语/升序向量/输出当输入/缺;）带位置")
    print("  [S4] to_model 适配器：Netlist→Layout，精确连通性反向探针")
    print("  [S5] 链路咬合：parse 输出被 dplac.place 直接消费（覆盖全部门）")
    print("  [边界] 不综合不求值 · 几何在布局阶段 · 非建模原语诚实跳过 · "
          "非 foundry PDK")

    if _FALS:
        print("S4 有红色：%s" % ", ".join(_FALS))
        return 1
    print("S4 全绿 · Verilog 子集解析器落地：c17 门级网表逐门忠实读入 dsynth.Netlist "
          "+ 往返零丢失 + 未知语法必报错 + 直接喂入数字链")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
