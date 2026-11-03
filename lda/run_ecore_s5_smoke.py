# -*- coding: utf-8 -*-
"""S5 门禁：**DEF 子集解析器**（5.8 · 布局布线结果 · 引用 LEF MACRO 名 → S1 Layout）。

═══════════════════════════════════════════════════════════════════════════════
这一版要证明什么
───────────────────────────────────────────────────────────────────────────────
`ddef.py` 是 S3 的「DEF 子集」—— LEF 的下游：LEF 描述**库几何**，DEF 描述**一次具体
布局布线**的结果（COMPONENTS 实例落点 + NETS 走线），通过「实例名 → MACRO 名」引用
`dlef.py` 解析出的库。判据只问四件事：

  S1 **字节级往返双射**：`parse → serialize → re-parse` **逐位相等**（canonical 重写，
      块内实例/网按名排序吐回，稳定幂等）。
  S2 **零数据丢失不变量**：SAMPLE_DEF parse 后，实例数 / 网数 / 终端数 / 走线点数
      在往返后**完全守恒**。
  S3 **未知语法必报错**：未闭合 END DESIGN / COMPONENT 既非 PLACED 也非 FIXED /
      引用未声明 MACRO（提供 LEF 时）/ 坐标数错 —— 一律抛 `DefSyntaxError`（带位置）。
  S4 **适配器正确 + 真实几何**：`to_model(defn, lef_lib)` 把实例的 MACRO 名解析成
      真实 w/h（INVX1=840×1240、NAND2X1=1240×1240，逐字来自 SAMPLE_LEF），
      布线走线还原成 `Rect` shapes。

诚实边界
────────
· **几何来自 LEF**：`to_model` 必须接收一张 `LefLibrary` 才能解析 MACRO 真实 w/h 与端口几何；
  无 LEF 时实例仅落点（cell=None，无几何）—— 这是诚实边界，不是缺陷。
· **OpenROAD 可选读回**：生成的 DEF 能被 OpenROAD `-def` 读取是**可选外部校验**，
  二进制在 PATH 上时跑；**绝不**把 OpenROAD 当 golden（LDA 权威来自自身无损往返）。
· **C 级自主**：纯标准库递归下降，零第三方依赖，LLM 不进判决路径。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_l2.ecore import ddef as DD                          # noqa: E402
from lda_l2.ecore import dlef as DL                           # noqa: E402

_FALS: list = []
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   record=_FALS)
T0 = time.time()
AN_ELAPSED_MAX_S = 30.0


def _expect_raises(src, want_pos=False, lef=None):
    """返回 (raised:bool, pos:int)。`want_pos` 时还要求 pos>0（带位置）。"""
    try:
        DD.parse_def(src, lef_lib=lef)
    except DD.DefSyntaxError as ex:
        pos = ex.pos
        return (True, pos) if (not want_pos or pos > 0) else (False, pos)
    return (False, 0)


def _count_terms(d):
    return sum(len(n.terms) for n in d.nets)


def _count_route_points(d):
    return sum(len(r.points) for n in d.nets for r in n.routes)


def main() -> int:
    LEF = DL.parse_lef(DL.SAMPLE_LEF)
    D = DD.parse_def(DD.SAMPLE_DEF, lef_lib=LEF)

    # ── S0 解析成功 + 顶层结构 ──────────────────────────────────────────
    check("S0 解析 SAMPLE_DEF 成功（DESIGN c17_placed · 2 COMPONENT · 1 NET）",
          D is not None, "parse 返回空")
    check("S0b 结构首遍计数：2 component / 1 net / 2 term / 2 route-pt",
          (len(D.components), len(D.nets), _count_terms(D), _count_route_points(D))
          == (2, 1, 2, 2),
          "得到 (%d,%d,%d,%d)" % (len(D.components), len(D.nets),
                                 _count_terms(D), _count_route_points(D)))

    # ── S1 字节级往返双射 ─────────────────────────────────────────────
    ser1 = DD.serialize_def(D)
    D2 = DD.parse_def(ser1)
    ser2 = DD.serialize_def(D2)
    check("S1 字节级往返双射：`serialize(reparse(serialize)) == serialize`"
          "（实例/网按名排序吐回，稳定幂等）",
          ser2 == ser1, "两遍 serialize 不相等")
    D3 = DD.parse_def(ser2)
    ser3 = DD.serialize_def(D3)
    check("S1b 幂等：第三遍 serialize 仍与首遍逐位相等",
          ser3 == ser1, "幂等失败")

    # ── S2 零数据丢失不变量 ───────────────────────────────────────────
    c2 = (len(D2.components), len(D2.nets), _count_terms(D2), _count_route_points(D2))
    check("S2 零数据丢失：实例/网/终端/走线点在往返后完全守恒（2/1/2/2）",
          c2 == (2, 1, 2, 2), "reparse %s" % (c2,))
    # 落点与朝向守恒
    xy1 = {(c.name, c.x, c.y, c.orient, c.placed) for c in D.components}
    xy2 = {(c.name, c.x, c.y, c.orient, c.placed) for c in D2.components}
    check("S2b 零数据丢失：实例落点/朝向/PLACED-FIXED 逐颗守恒",
          xy1 == xy2, "reparse xy=%s" % (xy2,))

    # ── S3 各类结构都被识别、无静默丢弃 ───────────────────────────────
    check("S3a DESIGN 名 = c17_placed · UNITS = 100 · DIEAREA 缺省（SAMPLE 未含）",
          D.name == "c17_placed" and D.units == 100 and D.diearea == [],
          "name=%s units=%s die=%s" % (D.name, D.units, D.diearea))
    macs = {c.macro for c in D.components}
    check("S3b COMPONENT 引用的 MACRO = {INVX1, NAND2X1}（与 SAMPLE_LEF 一致）",
          macs == {"INVX1", "NAND2X1"}, "macros=%s" % macs)
    check("S3c NET n1 终端 = [(u1,ZN),(u2,A)] · 含 ROUTED METAL1 两点",
          D.nets[0].terms == [("u1", "ZN"), ("u2", "A")]
          and D.nets[0].routes
          and D.nets[0].routes[0].layer == "METAL1"
          and len(D.nets[0].routes[0].points) == 2,
          "terms=%s routes=%s" % (D.nets[0].terms,
                                  [(r.layer, r.points) for r in D.nets[0].routes]))

    # ── S3 严格报错：反例必抛 DefSyntaxError（带位置）──────────────────
    r_unclosed = _expect_raises("DESIGN x ;", want_pos=True)
    check("S3d 未闭合 END DESIGN（DESIGN 后无 END）→ 必报错（带位置）",
          r_unclosed[0], "未报错")

    r_badplaced = _expect_raises(
        "DESIGN x ; COMPONENTS 1 ; - u1 INVX1 + PLACED ( 1 2 ) ; "
        "END COMPONENTS END DESIGN", want_pos=True)
    check("S3e COMPONENT 缺朝向（PLACED 后无 orient）→ 必报错（带位置）",
          r_badplaced[0], "未报错")

    # 引用未声明 MACRO（提供 LEF 时必报错）
    r_unkmacro = _expect_raises(
        "DESIGN x ; COMPONENTS 1 ; - u1 NOPE + PLACED ( 1 2 ) N ; "
        "END COMPONENTS END DESIGN", want_pos=True, lef=LEF)
    check("S3f 引用未声明 MACRO（提供 LEF）→ 必报错（带位置）",
          r_unkmacro[0], "未报错（引用了 LEF 中不存在的 MACRO 却放行）")

    r_coord = _expect_raises(
        "DESIGN x ; COMPONENTS 1 ; - u1 INVX1 + PLACED ( 1 ) N ; "
        "END COMPONENTS END DESIGN", want_pos=True)
    check("S3g 坐标数错（PLACED 只给 1 个坐标）→ 必报错（带位置）",
          r_coord[0], "未报错")

    # ── S4 适配器 to_model 正确 + 真实几何（来自 LEF）────────────────────
    m = DD.def_to_model(D, LEF)
    check("S4a to_model 产出 Layout · 实例数 == COMPONENT 数（2）",
          len(m.instances) == 2, "instances=%d" % len(m.instances))
    check("S4b 布线走线还原成 1 个 Rect shape（层=METAL1→1）",
          len(m.shapes) == 1 and m.shapes[0].layer == 1,
          "shapes=%d layer=%s" % (len(m.shapes),
                                  m.shapes[0].layer if m.shapes else None))
    # 反向探针：实例几何逐字来自 SAMPLE_LEF（INVX1=840×1240 / NAND2X1=1240×1240）
    u1 = next((i for i in m.instances if i.name == "u1"), None)
    u2 = next((i for i in m.instances if i.name == "u2"), None)
    u1_wh = (u1.cell.w_nm, u1.cell.h_nm) if (u1 and u1.cell) else None
    check("S4c 反向探针：u1(INVX1) w/h = 840×1240nm（真从 LEF 读，非默认）",
          u1_wh == (840, 1240), "u1 w/h=%s" % (u1_wh,))
    u2_wh = (u2.cell.w_nm, u2.cell.h_nm) if (u2 and u2.cell) else None
    u2_xy = (u2.x_nm, u2.y_nm) if u2 else None
    check("S4d 反向探针：u2(NAND2X1) w/h = 1240×1240nm · 落点 (300,400)",
          u2_wh == (1240, 1240) and u2_xy == (300, 400),
          "u2 w/h=%s xy=%s" % (u2_wh, u2_xy))

    # ── S0t 耗时红线 ───────────────────────────────────────────────────
    dt = time.time() - T0
    check("S0t 门禁耗时 %.2f s < %.0f s" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, "%.2f s" % dt)

    print()
    print("  [模块] ddef · 纯标准库 · C 级自主 · LLM 不进判决路径")
    print("  [S1] 字节级往返双射（serialize(reparse(serialize))==serialize）+ 幂等")
    print("  [S2] 零数据丢失不变量（实例/网/终端/落点守恒）")
    print("  [S3] 未知语法必报错（未闭合/缺朝向/未声明MACRO/坐标错）带位置")
    print("  [S4] to_model 适配器：实例几何逐字来自 LEF + 走线还原 Rect")
    print("  [边界] 几何依赖 LEF · OpenROAD 仅可选读回不当 golden · 非 foundry PDK")

    # OpenROAD 可选外部校验（二进制在 PATH 上时跑；缺失则跳过）
    or_bin = shutil.which("openroad")
    if or_bin is None:
        print("  [S5] OpenROAD 未安装（PATH 无 openroad）→ 跳过外部读回校验；"
              "LDA 权威 = 自身无损往返 + 结构守恒。")
    else:
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".def", delete=False) as fh:
                fh.write(ser1)
                def_path = fh.name
            proc = subprocess.run(
                ["openroad", "-no_init", "-exit", def_path],
                capture_output=True, text=True, timeout=60)
            ok_or = (proc.returncode == 0) and ("error" not in proc.stderr.lower())
            check("S5 OpenROAD 能读回生成的 DEF（外部校验，不当 golden）",
                  ok_or, "rc=%s stderr=%s" % (proc.returncode, proc.stderr[:200]))
        except Exception as ex:  # 超时 / 调用失败 —— 仅记信息，不判红
            print("  [S5] OpenROAD 调用异常（%s）→ 不计红色，仅 LDA 自身判据生效。" % ex)
        finally:
            try:
                os.unlink(def_path)
            except OSError:
                pass

    if _FALS:
        print("S5 有红色：%s" % ", ".join(_FALS))
        return 1
    print("S5 全绿 · DEF 子集解析器落地：布局布线结果逐字段忠实读入 + 往返零丢失 "
          "+ 未知语法必报错 + 实例几何逐字来自 LEF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
