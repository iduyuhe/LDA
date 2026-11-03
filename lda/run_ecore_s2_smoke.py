# -*- coding: utf-8 -*-
"""S2 门禁：**Liberty 子集解析器**（公开 PDK 的 `.lib` 逐 cell 逐字段往返 · 未知语法必报错）。

═══════════════════════════════════════════════════════════════════════════════
这一版要证明什么
───────────────────────────────────────────────────────────────────────────────
`dliberty.py` 是 S1 统一数据模型 `model.py` 明确留到 B2/S2 的那一块——把**公开 PDK 的
`.lib`** 读进来，让 `Pin.direction` / `TimingArc` 有「往哪儿填」的来源。判据只问三件事：

  S1 **逐 cell 逐字段往返一致**：`parse → serialize → re-parse` **逐位相等**
      （连 NLDM 矩阵行列数都不差），不靠「顺手归一化」偷偷变形 —— 与 S1 的 M2 同款纪律。
  S2 **未知语法必报错**：`define` / `type` 等宏与类型定义指令、表达式值 `area:(2*3)`、
      **顶层非 `library` 组**、未闭合组、非法字符 —— 一律抛 `LibertySyntaxError`（带行号），
      绝不静默跳过（「声称读完了却丢了 30% 数据」比「读不了」更危险）。
  S3 **零数据丢失不变量**：rich 样本 parse 后，所有 cell / pin / timing / attr 计数在往返后
      **完全守恒**——把「没静默丢」从口头承诺变成机核判据。
  S4 **适配器正确**：`to_model()` 把 direction / 极性 / `capacitance` pf→ff / NLDM 表喂给
      S1 的 `Pin` / `TimingArc`（单位换算显式，不静默）。

诚实边界
────────
· **不求值、不建模**：只忠实读取 + 往返，没有任何时序/功耗计算（那是 `dsta` 的事）；
· **几何在 LEF（S3）**：`.lib` 没有版图，CellView 尺寸留 0，等 LEF 接入；
· **非 foundry PDK**：自带 `SAMPLE_LIBERTY` 是按公开单元库惯例构造的**代表性合成子集**；
· **C 级自主**：纯标准库实现，零第三方依赖，LLM 不进判决路径。
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_l2.ecore import dliberty as DL       # noqa: E402

_FALS: list = []
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   record=_FALS)
T0 = time.time()
AN_ELAPSED_MAX_S = 30.0


def _expect_raises(func, *args, want_line=False):
    """返回 (raised:bool, line:int)。`want_line` 时还要求 line>0（带行号）。"""
    try:
        func(*args)
    except DL.LibertySyntaxError as ex:
        ln = ex.line
        return (True, ln) if (not want_line or ln > 0) else (False, ln)
    return (False, 0)


def _count_timing(lib):
    n = 0
    for cell in lib.cells.values():
        for pin in cell.subgroups("pin"):
            n += len(pin.subgroups("timing"))
    return n


def _count_pins(lib):
    n = 0
    for cell in lib.cells.values():
        n += len(cell.subgroups("pin"))
    return n


def main() -> int:
    LIB = DL.parse_liberty(DL.SAMPLE_LIBERTY)

    # ── S1 解析成功 + 顶层结构 ──────────────────────────────────────────
    check("S0 解析 SAMPLE_LIBERTY 成功（rich 合成子集 · INVX1/NAND2X1/DFFX1 + 模板）",
          LIB is not None, "parse 返回空")

    n_cells = len(LIB.cells)
    n_pins = _count_pins(LIB)
    n_timing = _count_timing(LIB)
    n_tmpl = len(LIB.templates)
    check("S1 数据守恒：3 cell / 8 pin / 4 timing / 1 template（首遍）",
          (n_cells, n_pins, n_timing, n_tmpl) == (3, 8, 4, 1),
          "得到 (%d,%d,%d,%d)" % (n_cells, n_pins, n_timing, n_tmpl))

    # ── S2 值类型识别（各 Liberty 值形态都正确解析）─────────────────────
    lf = LIB.attrs.get("library_features")
    clu = LIB.attrs.get("capacitive_load_unit")
    check("S2a `library_features ( \"a\", \"b\" )` 识别为字符串表（strlist）",
          lf is not None and lf.tag == "strlist" and lf.strs == ["report_delay_calculation", "report_power_calculation"],
          "tag=%s" % (lf.tag if lf else None))
    check("S2b `capacitive_load_unit ( 1.0, \"pf\" )` 识别为括号值（paren）",
          clu is not None and clu.tag == "paren",
          "tag=%s" % (clu.tag if clu else None))

    # 模板的 index_1 是 `"1.0, 2.0, 3.0"` 引号串形态 → 解析为向量（matrix），
    # 适配器 `_index_values` 两种写法（matrix / 引号串）都读得出。
    tmpl = LIB.templates.get("delay_template_3x3")
    idx_vec = DL._index_values(tmpl, "index_1") if tmpl else None
    check("S2c 模板 index_1 向量提取为 [1.0, 2.0, 3.0]（引号串 / 矩阵两种写法都支持）",
          idx_vec == [1.0, 2.0, 3.0], "vec=%s" % (idx_vec,))

    # NLDM 矩阵（cell_fall 下的 values）必须是 matrix 且 3×3
    z_pin = None
    for pin in LIB.cells["INVX1"].subgroups("pin"):
        if pin.name() == "Z":
            z_pin = pin
            break
    cf = None
    if z_pin is not None:
        for tg in z_pin.subgroups("timing"):
            sg = tg.subgroups("cell_fall")
            if sg:
                cf = sg[0].attrs.get("values")
    check("S2d `cell_fall` 的 `values` 识别为矩阵（matrix）",
          cf is not None and cf.tag == "matrix" and len(cf.rows) == 3
          and len(cf.rows[0]) == 3,
          "tag=%s rows=%s" % (cf.tag if cf else None, cf.rows if cf else None))

    # ── S3 零数据丢失不变量：往返后计数守恒 ─────────────────────────────
    ser1 = DL.serialize_liberty(LIB)
    LIB2 = DL.parse_liberty(ser1)
    n_cells2 = len(LIB2.cells)
    n_pins2 = _count_pins(LIB2)
    n_timing2 = _count_timing(LIB2)
    n_tmpl2 = len(LIB2.templates)
    check("S3 零数据丢失：serialize→reparse 后计数完全守恒（3/8/4/1）",
          (n_cells2, n_pins2, n_timing2, n_tmpl2) == (3, 8, 4, 1),
          "reparse (%d,%d,%d,%d)" % (n_cells2, n_pins2, n_timing2, n_tmpl2))

    # 顺带：INVX1 Z 的 cell_fall 矩阵首格在 reparse 后仍精确
    z_pin2 = None
    for pin in LIB2.cells["INVX1"].subgroups("pin"):
        if pin.name() == "Z":
            z_pin2 = pin
            break
    cf2 = None
    if z_pin2 is not None:
        for tg in z_pin2.subgroups("timing"):
            sg = tg.subgroups("cell_fall")
            if sg:
                cf2 = sg[0].attrs.get("values")
    first_cell = cf2.rows[0][0] if (cf2 and cf2.rows) else None
    check("S3b NLDM 矩阵首格 0.012 在往返后逐位精确（非 0.01 类归一化失真）",
          first_cell == 0.012, "得到 %r" % first_cell)

    # ── S1 字节级往返双射 ─────────────────────────────────────────────
    ser2 = DL.serialize_liberty(LIB2)
    check("S1b 字节级往返双射：`serialize(reparse(serialize)) == serialize`"
          "（连属性顺序、NLDM 行列数都不差）",
          ser2 == ser1, "两遍 serialize 不相等（信息被悄悄变形）")

    # internal_power 子组也必须被保留（不能静默丢）
    has_ip = any(any(True for _ in pin.subgroups("internal_power"))
                 for cell in LIB2.cells.values() for pin in cell.subgroups("pin"))
    check("S3c 非 timing 子组（internal_power）在往返后仍存在（无静默丢弃）",
          has_ip, "internal_power 丢失")

    # ── S2 严格报错：6 类反例必抛 LibertySyntaxError ───────────────────
    r_top = _expect_raises(DL.parse_liberty, "cell (X) { area : 1 ; }")
    check("S2e 顶层非 library 组 → 必报错（不静默当普通组）",
          r_top[0], "未报错")

    r_def = _expect_raises(DL.parse_liberty,
                           'library (L) { define (cell_footprint, string) ; }',
                           want_line=True)
    check("S2f `define` 宏指令 → 必报错（带行号，不静默跳过）",
          r_def[0], "未报错 / 无行号")

    r_typ = _expect_raises(DL.parse_liberty,
                           'library (L) { type (bus) { base_type : "net"; } }',
                           want_line=True)
    check("S2g `type` 类型定义指令 → 必报错（带行号，不静默跳过）",
          r_typ[0], "未报错 / 无行号")

    r_expr = _expect_raises(DL.parse_liberty,
                            'library (L) { cell (X) { area : (2*3) ; } }',
                            want_line=True)
    check("S2h 表达式值 `area:(2*3)` → 必报错（拒绝求值，不静默吞掉）",
          r_expr[0], "未报错 / 无行号")

    r_unclosed = _expect_raises(DL.parse_liberty,
                                'library (L) { cell (X) { area : 1 ; ')
    check("S2i 未闭合组 → 必报错（不静默截断）",
          r_unclosed[0], "未报错")

    r_badchar = _expect_raises(DL.parse_liberty,
                               'library (L) { cell (X) { area : 1 @ bad ; } }',
                               want_line=True)
    check("S2j 非法字符 `@` → 必报错（带行号，不静默跳过）",
          r_badchar[0], "未报错 / 无行号")

    # ── S4 适配器 to_model 正确 ───────────────────────────────────────
    model = DL.to_model(LIB)
    ok_model = ("INVX1" in model and "NAND2X1" in model and "DFFX1" in model)
    check("S4a to_model 三 cell 全部产出 CellView",
          ok_model, "缺 %s" % ([c for c in ("INVX1", "NAND2X1", "DFFX1")
                               if c not in model],))

    inv_a = model["INVX1"].pins.get("A")
    inv_z = model["INVX1"].pins.get("Z")
    check("S4b INVX1.A 极性 input · cap_ff = 0.5pf→500ff（单位换算显式）",
          inv_a is not None and inv_a.direction == "input" and abs(inv_a.cap_ff - 500.0) < 1e-9,
          "A=%r" % (inv_a,))
    check("S4c INVX1.Z 极性 output",
          inv_z is not None and inv_z.direction == "output", "Z=%r" % (inv_z,))

    # INVX1.Z 的 arc：related=A、positive_unate、nominal=Z cell_fall 中心格 0.052ns→52ps
    z_arcs = [a for a in model["INVX1"].arcs if a.to_pin == "Z"]
    check("S4d INVX1.Z 的 TimingArc：related=A · positive_unate · delay_ps=52.0",
          z_arcs and z_arcs[0].from_pin == "A" and z_arcs[0].sense == "positive_unate"
          and abs((z_arcs[0].delay_ps or 0) - 52.0) < 1e-9,
          "arc=%r" % (z_arcs[0] if z_arcs else None,))

    # NLDM 表维度：slew(3) × load(3) × delays[3][3]
    tbl = z_arcs[0].table if z_arcs else None
    ok_tbl = (tbl is not None and len(tbl[0]) == 3 and len(tbl[1]) == 3
              and len(tbl[2]) == 3 and all(len(r) == 3 for r in tbl[2]))
    check("S4e INVX1.Z NLDM 表维度 (slew3, load3, delays[3][3]) 不丢不增",
          ok_tbl, "table=%r" % (tbl,))

    # DFF 的 Q 是 non_unate（多角/时钟类时序的真实极性，不得被默认成 positive）
    dff_q_arcs = [a for a in model["DFFX1"].arcs if a.to_pin == "Q"]
    check("S4f DFF.Q 极性 non_unate（真实极性来自 Liberty，不写死默认）",
          dff_q_arcs and dff_q_arcs[0].sense == "non_unate",
          "sense=%r" % (dff_q_arcs[0].sense if dff_q_arcs else None,))

    # 反向探针：把 INVX1 的弧数/极性搞错应红 —— 这里验证「适配器没把极性全写成同一个」
    senses = {a.sense for c in model.values() for a in c.arcs}
    check("S4g 反向：三种 sense 都在（positive/negative/non_unate 各有所属，"
          "证明 polarity 真从 Liberty 读而非恒值）",
          {"positive_unate", "negative_unate", "non_unate"} <= senses,
          "senses=%s" % senses)

    dt = time.time() - T0
    check("S0 门禁耗时 %.2f s < %.0f s" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, "%.2f s" % dt)

    print()
    print("  [模块] dliberty · 纯标准库 · C 级自主 · LLM 不进判决路径")
    print("  [S1] 逐 cell 逐字段往返字节级双射（含 NLDM 矩阵）")
    print("  [S2] 未知语法必报错（define/type/表达式值/顶层非library/未闭合/非法字符）带行号")
    print("  [S3] 零数据丢失不变量（3 cell/8 pin/4 timing/1 template 守恒）")
    print("  [S4] to_model 适配器：direction/cap_ff(pf→ff)/NLDM 表喂给 S1 Pin/TimingArc")
    print("  [边界] 不求值不建模 · 几何在 LEF(S3) · 非 foundry PDK")
    print()
    if _FALS:
        print("S2 有红色：%s" % ", ".join(_FALS))
        return 1
    print("S2 全绿 · Liberty 子集解析器落地：公开 PDK .lib 逐字段忠实读入 + 往返零丢失 + 未知语法必报错")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
