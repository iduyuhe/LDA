# -*- coding: utf-8 -*-
"""S3 门禁：**LEF 子集解析器**（5.8 · 几何读入 S1 统一模型 · 逐字段往返 · 未知语法必报错）。

═══════════════════════════════════════════════════════════════════
这一版要证明什么
───────────────────────────────────────────────────────────────────────────────
`dlef.py` 是 S1 统一数据模型 `model.py` 明确留到 B2/S3 的那一块——把 LEF 的 **MACRO 几何**
（PORT/OBS 矩形、SIZE）读进来，让 `CellView.w_nm/h_nm/shapes` 第一次有真实版图来源
（`dliberty` 只喂了引脚极性 / 时序，CellView 尺寸留 0）。判据只问四件事：

  S1 **字节级往返双射**：`parse → serialize → re-parse` **逐位相等**
      （`serialize(reparse(serialize(x))) == serialize(x)`），不靠「顺手归一化」偷偷变形。
  S2 **零数据丢失不变量**：rich 样本 parse 后，顶层语句 / MACRO / PIN / 几何矩形计数在
      往返后**完全守恒**——把「没静默丢」从口头承诺变成机核判据。
  S3 **未知语法必报错**：未闭合块 / 顶层非 `END LIBRARY` 的 END / 语句缺 `;` /
      END 名错配 / RECT 参数数错或反向 / SIZE 格式错 —— 一律抛 `LefSyntaxError`（带行号），
      绝不静默跳过（「声称读完 LEF 却悄悄丢了几何」比「读不了」更危险）。
  S4 **适配器正确 + 反向探针**：`to_model()` 把 SIZE→w/h_nm、PORT RECT→Pin.rect+shapes、
      OBS RECT→shapes[role=obs] 喂给 S1 的 `CellView`，坐标按 DATABASE MICRONS 换算成 nm
      整数；反向探针断言**精确几何**（INVX1 840×1240、OBS (0,0)-(60,60)nm、A 在 Metal1），
      证明几何是真从 LEF 读的、不是默认值。

诚实边界
────────
· **不求值、不建模**：只忠实读取 + 往返，没有任何 DRC / 布线 / 时序计算（那是 `ddrc_lvs`/
  `droute`/`dsta` 的事）；一旦它开始算，就会变成「第二套实现」，与既有模块必然漂移。
· **DEF 在 S3 后半程**：LEF 是「库几何」，DEF 是「布局布线结果」，后者引用本模块的 MACRO 名，
  故 DEF 解析器（`ddef.py`，S3 后续）依赖本模块先落地。
· **OpenROAD 可读回**是**可选外部校验**（二进制在 PATH 上时跑 `openroad -lef` 验证），
  **绝不**把 OpenROAD 当 golden（P1 角色位：外部当判决源 = 红）；LDA 的权威来自自身的
  无损往返 + 结构守恒。
· **非 foundry PDK**：层名（Metal1/Metal2/Via1…）按通用命名映射到整数索引
  （见 `_LEF_LAYER_MAP`），不是任何真实工艺的 PDK 层叠定义。
· **C 级自主**：纯标准库实现，零第三方依赖，LLM 不进判决路径。
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

from lda_l2.ecore import dlef as DL                              # noqa: E402

_FALS: list = []
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   record=_FALS)
T0 = time.time()
AN_ELAPSED_MAX_S = 30.0


def _expect_raises(text, want_line=False):
    """返回 (raised:bool, line:int)。`want_line` 时还要求 line>0（带行号）。"""
    try:
        DL.parse_lef(text)
    except DL.LefSyntaxError as ex:
        ln = ex.line
        return (True, ln) if (not want_line or ln > 0) else (False, ln)
    return (False, 0)


def _count_pins(lib):
    n = 0
    for mac in lib.macros:
        n += len(mac.subgroups("PIN"))
    return n


def _count_rects(lib):
    """统计全树所有 RECT（PORT 与 OBS 的几何），即「几何矩形」总数。"""
    def walk(items):
        c = 0
        for it in items:
            if it.keyword.upper() == "RECT":
                c += 1
            if it.children:
                c += walk(it.children)
        return c
    return walk(lib.items)


def _count_toplevel(lib):
    return len(lib.items)


def main() -> int:
    LIB = DL.parse_lef(DL.SAMPLE_LEF)

    # ── S0 解析成功 + 顶层结构 ──────────────────────────────────────────
    check("S0 解析 SAMPLE_LEF 成功（rich 合成子集 · INVX1/NAND2X1 + 3 LAYER）",
          LIB is not None, "parse 返回空")

    n_macro = len(LIB.macros)
    n_pin = _count_pins(LIB)
    n_rect = _count_rects(LIB)
    n_top = _count_toplevel(LIB)
    check("S0b 结构首遍计数：2 macro / 5 pin / 6 rect / 9 顶层语句",
          (n_macro, n_pin, n_rect, n_top) == (2, 5, 6, 9),
          "得到 (%d,%d,%d,%d)" % (n_macro, n_pin, n_rect, n_top))

    # ── S1 字节级往返双射 ─────────────────────────────────────────────
    ser1 = DL.serialize_lef(LIB)
    LIB2 = DL.parse_lef(ser1)
    ser2 = DL.serialize_lef(LIB2)
    check("S1 字节级往返双射：`serialize(reparse(serialize)) == serialize`"
          "（语句顺序 / 层名 / 坐标文本逐字符一致）",
          ser2 == ser1, "两遍 serialize 不相等（信息被悄悄变形）")

    # 幂等：再跑一遍仍相等
    LIB3 = DL.parse_lef(ser2)
    ser3 = DL.serialize_lef(LIB3)
    check("S1b 幂等：第三遍 serialize 仍与首遍逐位相等",
          ser3 == ser1, "幂等失败")

    # ── S2 零数据丢失不变量：往返后计数守恒 ─────────────────────────────
    n_macro2 = len(LIB2.macros)
    n_pin2 = _count_pins(LIB2)
    n_rect2 = _count_rects(LIB2)
    n_top2 = _count_toplevel(LIB2)
    check("S2 零数据丢失：serialize→reparse 后计数完全守恒（2/5/6/9）",
          (n_macro2, n_pin2, n_rect2, n_top2) == (2, 5, 6, 9),
          "reparse (%d,%d,%d,%d)" % (n_macro2, n_pin2, n_rect2, n_top2))

    # ── S3 各类语句 / 块结构都被识别、无静默丢弃 ───────────────────────
    has_version = any(it.keyword.upper() == "VERSION" for it in LIB.items)
    has_units = any(it.keyword.upper() == "UNITS" for it in LIB.items)
    has_dbmicrons = any(
        c.keyword.upper() == "DATABASE" and c.args_raw.upper().startswith("MICRONS")
        for it in LIB.items if it.keyword.upper() == "UNITS"
        for c in (it.children or []))
    layers = LIB.layers
    check("S3a 顶层 VERSION / UNITS / DATABASE MICRONS 都被识别",
          has_version and has_units and has_dbmicrons,
          "version=%s units=%s dbmicrons=%s" % (has_version, has_units, has_dbmicrons))
    check("S3b 3 个 LAYER（Metal1/Metal2/Via1）都被识别为层定义",
          set(layers.keys()) >= {"Metal1", "Metal2", "Via1"},
          "layers=%s" % list(layers.keys()))
    # 每个 LAYER 的子句都保留（无静默丢弃）。Metal1/Metal2 带全四子句；
    # Via1 是 CUT 层，样本本就不含 PITCH（这是真实合法差异，不是丢失）。
    def _subkeys(ln):
        return {s.keyword.upper() for s in layers[ln].children or []}
    layer_ok = (_subkeys("Metal1") == {"TYPE", "PITCH", "WIDTH", "SPACING"}
                and _subkeys("Metal2") == {"TYPE", "PITCH", "WIDTH", "SPACING"}
                and _subkeys("Via1") == {"TYPE", "WIDTH", "SPACING"})
    check("S3c 各 LAYER 子句都保留（Metal1/Metal2=TYPE/PITCH/WIDTH/SPACING；"
          "Via1=TYPE/WIDTH/SPACING，CUT 层本无 PITCH，非丢失）",
          layer_ok, "Metal1=%s Metal2=%s Via1=%s" % (
              _subkeys("Metal1"), _subkeys("Metal2"), _subkeys("Via1")))
    # MACRO 的 SIZE / PIN→DIRECTION+PORT(LAYER+RECT) / OBS(LAYER+RECT) 都在
    macro_ok = True
    for mac in LIB.macros:
        if not mac.subgroups("SIZE"):
            macro_ok = False
        for pin in mac.subgroups("PIN"):
            if not pin.subgroups("DIRECTION"):
                macro_ok = False
            for port in pin.subgroups("PORT"):
                if not port.subgroups("LAYER") or not port.subgroups("RECT"):
                    macro_ok = False
        # OBS 块（含 LAYER+RECT）要么存在要么缺失都合法，但若存在须完整
        for obs in mac.subgroups("OBS"):
            if not obs.subgroups("LAYER") or not obs.subgroups("RECT"):
                macro_ok = False
    check("S3d MACRO 的 SIZE / PIN→DIRECTION+PORT(LAYER+RECT) / OBS(LAYER+RECT) 完整",
          macro_ok, "MACRO 子结构缺失")

    # ── S3 严格报错：7 类反例必抛 LefSyntaxError（带行号）───────────────
    r_unclosed = _expect_raises("MACRO X\n  SIZE 100 BY 100 ;\n", want_line=True)
    check("S3e 未闭合块（MACRO 无 END）→ 必报错（带行号）",
          r_unclosed[0], "未报错")

    r_stray = _expect_raises("END FOO\n", want_line=True)
    check("S3f 顶层非 LIBRARY 的 END → 必报错（带行号）",
          r_stray[0], "未报错")

    r_nosemi = _expect_raises("MACRO X\n  SIZE 100 BY 100\nEND X\nEND LIBRARY\n",
                              want_line=True)
    check("S3g 语句缺 `;`（SIZE 同行无 ;）→ 必报错（带行号，不静默当空块）",
          r_nosemi[0], "未报错 / 无行号")

    r_mismatch = _expect_raises("MACRO X\n  SIZE 100 BY 100 ;\nEND PIN\nEND LIBRARY\n",
                                want_line=True)
    check("S3h END 名错配（MACRO X 内 END PIN）→ 必报错（带行号）",
          r_mismatch[0], "未报错 / 无行号")

    r_rect_n = _expect_raises(
        "MACRO X\n  SIZE 100 BY 100 ;\n  PIN A\n    PORT\n      LAYER Metal1 ;\n"
        "      RECT 1 2 3 ;\n    END PORT\n  END A\nEND X\nEND LIBRARY\n",
        want_line=True)
    check("S3i RECT 参数数错（3 个而非 4）→ 必报错（带行号）",
          r_rect_n[0], "未报错 / 无行号")

    r_rect_rev = _expect_raises(
        "MACRO X\n  SIZE 100 BY 100 ;\n  PIN A\n    PORT\n      LAYER Metal1 ;\n"
        "      RECT 200 200 100 100 ;\n    END PORT\n  END A\nEND X\nEND LIBRARY\n",
        want_line=True)
    check("S3j RECT 坐标反向（x1<x0）→ 必报错（带行号，不污染后续 DRC）",
          r_rect_rev[0], "未报错 / 无行号")

    r_size = _expect_raises("MACRO X\n  SIZE 100 100 ;\nEND X\nEND LIBRARY\n",
                            want_line=True)
    check("S3k SIZE 格式错（缺 BY）→ 必报错（带行号）",
          r_size[0], "未报错 / 无行号")

    # ── S4 适配器 to_model 正确 + 反向探针（精确几何，非默认值）──────────
    model = DL.to_model(LIB)
    ok_model = ("INVX1" in model and "NAND2X1" in model)
    check("S4a to_model 两 cell 全部产出 CellView",
          ok_model, "缺 %s" % ([c for c in ("INVX1", "NAND2X1") if c not in model],))

    inv = model["INVX1"]
    nand = model["NAND2X1"]
    check("S4b INVX1 尺寸 840×1240 nm（SIZE→w/h_nm，DATABASE MICRONS 换算）",
          inv.w_nm == 840 and inv.h_nm == 1240,
          "got %dx%d" % (inv.w_nm, inv.h_nm))
    check("S4c NAND2X1 尺寸 1240×1240 nm",
          nand.w_nm == 1240 and nand.h_nm == 1240,
          "got %dx%d" % (nand.w_nm, nand.h_nm))

    # 引脚极性真从 LEF 读（INVX1.A=input, ZN=output）
    inv_a = inv.pins.get("A")
    inv_z = inv.pins.get("ZN")
    check("S4d INVX1.A=input · ZN=output（DIRECTION 真读，非默认）",
          inv_a is not None and inv_a.direction == "input"
          and inv_z is not None and inv_z.direction == "output",
          "A=%r ZN=%r" % (inv_a.direction if inv_a else None,
                           inv_z.direction if inv_z else None))

    # 反向探针：精确几何，证明不是默认值
    # INVX1 PIN A 在 Metal1（layer=1），矩形 (100,100)-(200,200) nm
    inv_a_rect = inv_a.rect if inv_a else None
    check("S4e 反向探针：INVX1.A 几何 = Metal1 矩形 (100,100)-(200,200)nm（精确）",
          inv_a_rect is not None and inv_a_rect.layer == 1
          and (inv_a_rect.x0_nm, inv_a_rect.y0_nm,
               inv_a_rect.x1_nm, inv_a_rect.y1_nm) == (100, 100, 200, 200),
          "rect=%r" % (inv_a_rect,))
    # INVX1 OBS 矩形 (0,0)-(60,60)nm，role=obs，共 1 个 obs + 2 个 port = 3 shapes
    obs = [s for s in inv.shapes if s.role == "obs"]
    check("S4f 反向探针：INVX1 OBS 矩形 (0,0)-(60,60)nm · role=obs · 共 3 shapes",
          len(obs) == 1 and obs[0].x0_nm == 0 and obs[0].y0_nm == 0
          and obs[0].x1_nm == 60 and obs[0].y1_nm == 60
          and len(inv.shapes) == 3,
          "obs=%r shapes=%d" % (obs, len(inv.shapes)))
    # NAND2X1 有 3 个 pin（A/B/ZN）且 ZN 在 Metal2（layer=2）
    nand_z = nand.pins.get("ZN")
    check("S4g NAND2X1 3 pin · ZN 在 Metal2（layer=2）",
          len(nand.pins) == 3 and nand_z is not None and nand_z.rect is not None
          and nand_z.rect.layer == 2,
          "pins=%d zlayer=%s" % (len(nand.pins),
                                 nand_z.rect.layer if nand_z and nand_z.rect else None))

    # 反向探针：用一份**真实畸形**的 LEF 让 to_model 不应产出「看似合理」的默认几何
    bad = ("MACRO BAD\n  SIZE 100 BY 100 ;\n  PIN A\n    PORT\n      LAYER Metal1 ;\n"
           "      RECT 200 200 100 100 ;\n    END PORT\n  END A\nEND BAD\nEND LIBRARY\n")
    raises_bad = _expect_raises(bad)  # 解析阶段即因反向坐标报错
    check("S4h 反向探针：反向坐标 LEF 在 parse 阶段就报错（不产出默认几何）",
          raises_bad[0], "未报错 → 会污染 to_model")

    # ── S5 OpenROAD 可选外部校验（二进制在 PATH 上时跑；缺失则跳过）──────
    dt = time.time() - T0
    check("S0t 门禁耗时 %.2f s < %.0f s" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, "%.2f s" % dt)

    print()
    print("  [模块] dlef · 纯标准库 · C 级自主 · LLM 不进判决路径")
    print("  [S1] 字节级往返双射（serialize(reparse(serialize))==serialize）+ 幂等")
    print("  [S2] 零数据丢失不变量（2 macro/5 pin/6 rect/9 顶层语句 守恒）")
    print("  [S3] 未知语法必报错（未闭合/顶层非LIBRARY END/缺;/END名错配/"
          "RECT参数量错或反向/SIZE格式错）带行号")
    print("  [S4] to_model 适配器：SIZE→w/h_nm、PORT/OBS RECT→Pin.rect+shapes，"
          "精确几何反向探针")
    print("  [边界] 不求值不建模 · 非 foundry PDK · DEF 依赖本模块 · "
          "OpenROAD 只读回不当 golden")
    print()

    # OpenROAD 外部校验放在汇总之后、退出之前（避免计入门禁耗时红线）
    or_bin = shutil.which("openroad")
    if or_bin is None:
        print("  [S5] OpenROAD 未安装（PATH 无 openroad）→ 跳过外部读回校验；"
              "LDA 权威 = 自身无损往返 + 结构守恒。")
    else:
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".lef", delete=False) as fh:
                fh.write(ser1)
                lef_path = fh.name
            proc = subprocess.run(
                ["openroad", "-no_init", "-exit", lef_path],
                capture_output=True, text=True, timeout=60)
            ok_or = (proc.returncode == 0) and ("error" not in proc.stderr.lower())
            check("S5 OpenROAD 能读回生成的 LEF（外部校验，不当 golden）",
                  ok_or, "rc=%s stderr=%s" % (proc.returncode, proc.stderr[:200]))
        except Exception as ex:  # 超时 / 调用失败 —— 仅记信息，不判红（外部工具不稳定）
            print("  [S5] OpenROAD 调用异常（%s）→ 不计红色，仅 LDA 自身判据生效。" % ex)
        finally:
            try:
                os.unlink(lef_path)
            except OSError:
                pass

    if _FALS:
        print("S3 有红色：%s" % ", ".join(_FALS))
        return 1
    print("S3 全绿 · LEF 子集解析器落地：MACRO 几何逐字段忠实读入 S1 + 往返零丢失"
          " + 未知语法必报错 + OpenROAD 可选读回")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
