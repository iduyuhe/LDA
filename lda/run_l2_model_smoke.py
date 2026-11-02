"""S1 门禁：**统一数据模型（B1）** —— 让「加新能力」不再默认长出一个孤岛。

═══════════════════════════════════════════════════════════════════════════════
这一版要证明什么
───────────────────────────────────────────────────────────────────────────────
`docs/PLAN_foundation_2026-11.md` §一 实测：ecore 72 模块里 **21 个零入度（29%）**，
其中 **12 个是 E45 之后的成果**。根因不是模块写得差，而是**没有公共数据模型** ——
29 个 class 分散在 13 个模块里各自定义类型，每接一次就要写一次转换，
新增能力的默认结局是「再起一个孤岛」。

本版只做一件事：给「单元/引脚/时序弧/实例/线网/版图」定一份最小公共形状，
**一行不改既有模块**（用适配器进出）。判据只问四个问题：

  M1 **单位契约**：长度必须是 nm 整数值（`70.0` 归一化，`70.5` 报错）
  M2 **往返双射**：`Cell → CellView → Cell` 逐位一致（不许「顺手归一化」）
  M3 **结构同构**：两套规则集（DEMO45 / HD）的单元产出**同一种** CellView 形状
  M6 **引脚⇄金属一致**：pin 声明的区域必须有同层金属**覆盖**（不是相触）

🔴 M6 是本版最有价值的一条：它一上线就抓到一个真缺口 ——
**DFF 的 D/CLK/Q/QN 四个信号引脚**只登记在 `pins` 字典里，`rects` 里**没有对应的 pad 金属**
（`dhdlib.py` 的注释写着「引脚（M1 pad 70×70）」，但那 4 个 `R` 对象从未 `append` 到 `rects`）。
后果：`dcnet.pin_shapes()` 会把这 4 个「引脚」交给布线器，而那里只有一条 30nm 宽的 bus 穿过
70nm 高的 PORT ⇒ 落孔 ENC 不足。

🔴 **为什么本版不直接修**（这是量化过的，不是偷懒）：
DFF 的电平间距是 **60nm**（`DFF_LEVELS`），而 pad 需要 **70nm**（VIA 50 + 2×ENC 10），
再加 `m1_s = 30` ⇒ 相邻电平放 pad 的最小间距是 **100nm > 60nm**。
也就是说这是 **E54 的结构性几何矛盾**，不是漏写一行 —— 修法要么加大电平间距（撑大面积），
要么在引脚处做邻线逃逸。所以本版把它登记为 `KNOWN_PIN_METAL_GAP` 并**双向判据**：
新增缺口 ⇒ 红；修好却忘删登记 ⇒ 也红（棘轮收紧）。

═══════════════════════════════════════════════════════════════════════════════
诚实边界
───────────────────────────────────────────────────────────────────────────────
· **不是 Liberty/LEF/DEF 解析器**（那是 S2/S3）：本模块只定义「解析结果往哪儿放」；
· **不含任何算法**：无 DRC、无布线、无时序计算 —— 一旦它开始算，就会变成「第二套实现」；
· **不取代 `dcells.Cell`**：既有 62 道 ecore 门禁继续跑原类型，模型层是**并行视图**；
  要它变成主链，得等 B3（端到端干线）把调用关系真正接起来；
· 引脚的**方向**目前只能从「是否电源网」推断（`VDD/VSS → inout`，其余 `input`），
  真实极性来自 Liberty 的 `direction`/`timing_sense`，待 S2 补齐。
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_l2 import model as MD                # noqa: E402
from lda_l2.ecore import dcells as CL         # noqa: E402
from lda_l2.ecore import dctrl as CT          # noqa: E402
from lda_l2.ecore import dhdlib as HD         # noqa: E402
from lda_l2.ecore import dpnr as PN           # noqa: E402

_FAILED: list = []
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   record=_FAILED)
T0 = time.time()
AN_ELAPSED_MAX_S = 60.0

CASES = ("INV_X1", "NAND2_X1", "INV_X1_HD", "NAND2_X1_HD", "DFF_X1_HD")


def _cells():
    return {"INV_X1": CL.CELLS["INV_X1"](), "NAND2_X1": CL.CELLS["NAND2_X1"](),
            "INV_X1_HD": HD.build_inv_hd(), "NAND2_X1_HD": HD.build_nand2_hd(),
            "DFF_X1_HD": HD.build_dff_hd()}


def main() -> int:
    # ── M1 单位契约 ───────────────────────────────────────────────────
    try:
        MD.Rect(23, 0.5, 0, 10, 10)
        bad = True
    except TypeError:
        bad = False
    check("M1 单位契约：**非整数** nm 坐标必须报错（0.5 ⇒ TypeError，不可静默舍入）",
          not bad, "0.5 被接受了")

    m = MD.Rect(23, 70.0, 0, 140.0, 70)
    norm = (m.x0_nm == 70 and m.x1_nm == 140
            and isinstance(m.x0_nm, int) and isinstance(m.x1_nm, int))
    check("M1b **值为整数的 float**（`70.0`）归一到 int 且无损 —— 上游 dcells 的 HD 库"
          "确有 10 处这种写法，必须显式化而不是假装没看见",
          norm, "归一化失败：%r %r" % (m.x0_nm, m.x1_nm))

    try:
        MD.Rect(23, 10, 0, 0, 10)
        rev = True
    except ValueError:
        rev = False
    check("M1c 反向矩形必须报错（x1<x0）", not rev, "反向被接受了")

    # ── M2 往返双射 ──────────────────────────────────────────────────
    rt = {k: MD.roundtrip_ok(c) for k, c in _cells().items()}
    bad_rt = {k: v for k, v in rt.items() if not v["ok"]}
    check("M2 往返双射：`Cell → CellView → Cell` **逐位一致**（%d 颗：%s）—— "
          "不许「顺手归一化」，否则上游数字会悄悄变形"
          % (len(rt), ", ".join(rt)), not bad_rt, "失配 %s" % (bad_rt,))

    # ── M3 结构同构 ──────────────────────────────────────────────────
    views = {k: MD.cellview_from_dcells(c) for k, c in _cells().items()}
    iso = {k: (bool(v.pins) and bool(v.shapes) and v.rail_y_nm is not None
               and v.w_nm > 0 and v.h_nm > 0) for k, v in views.items()}
    check("M3 结构同构：**两套规则集**（DEMO45 / HD）的单元产出同一种 CellView 形状"
          "（引脚 + 全量几何 + 电源轨 + 尺寸）",
          all(iso.values()), "缺字段 %s" % ([k for k, v in iso.items() if not v],))

    # ── M4 引脚名集合可对 ─────────────────────────────────────────────
    inv45 = sorted(views["INV_X1"].pin_names())
    invhd = sorted(views["INV_X1_HD"].pin_names())
    check("M4 引脚名集合跨规则集可比：DEMO45 INV=%s · HD INV=%s ⇒ 结构同构不靠数值相同"
          % (inv45, invhd), inv45 == invhd, "%s vs %s" % (inv45, invhd))

    # ── M5 障碍是派生量，可复算 ────────────────────────────────────────
    obs_ok = True
    detail = []
    for k, v in views.items():
        n_pin_rect = sum(1 for p in v.pins.values() if p.rect is not None)
        # 障碍 = 全量 − 能被某个引脚矩形**完全覆盖**的图形
        detail.append("%s:%d/%d" % (k, len(v.obstacles()), len(v.shapes)))
        if len(v.obstacles()) > len(v.shapes) or n_pin_rect > len(v.shapes):
            obs_ok = False
    check("M5 `obstacles()` 是**派生量**（不落盘、可复算）：全量 − 引脚覆盖（%s）"
          % " · ".join(detail), obs_ok, "障碍数越界")

    # ── M6 引脚 ⇄ 金属（本版最有价值的一条）───────────────────────────
    pm = MD.pin_metal_report()
    check("M6 引脚⇄金属体检：**实际缺口 == 登记缺口**（缺口 %d 个：%s）· 未登记 %d · 过期 %d"
          % (pm["n_missing_total"],
             ", ".join("%s:%s" % (k, "/".join(v)) for k, v in pm["got"].items() if v) or "无",
             len(pm["unregistered"]), len(pm["stale"])),
          pm["ok"], "unregistered=%s stale=%s" % (pm["unregistered"], pm["stale"]))

    # ── M7 反向探针：新增一个「无金属引脚」⇒ 未登记必红 ────────────────
    probe = MD.cellview_from_dcells(HD.build_inv_hd())
    fake = MD.Rect(CL.L_M1, 500, 400, 570, 470)          # 空中一块 pad，无金属覆盖
    probe.pins["NOPE"] = MD.Pin(name="NOPE", direction="input", rect=fake)
    rep = MD.pin_metal_report({"INV_X1_HD": MD.cell_to_dcells(probe)})
    check("M7 反向：注入一个**无金属覆盖的引脚**（NOPE）⇒ 体检必报未登记（证明 M6 不是恒绿）",
          bool(rep["unregistered"]), "未报 ⇒ 判据失靶")

    # ── M8 反向探针：修好后忘删登记 ⇒ stale 必红（棘轮收紧）────────────
    saved = dict(MD.KNOWN_PIN_METAL_GAP)
    try:
        MD.KNOWN_PIN_METAL_GAP["INV_X1_HD"] = ("A",)   # 给一个本来没缺口的单元造登记
        rep2 = MD.pin_metal_report()
    finally:
        MD.KNOWN_PIN_METAL_GAP.clear()
        MD.KNOWN_PIN_METAL_GAP.update(saved)
    check("M8 反向：登记表里留一条**已修好**的条目 ⇒ `stale` 必红（棘轮只许收紧，"
          "防「登记了就不管」）",
          bool(rep2["stale"]), "未报 stale")

    # ── M9 布局适配（实例/线网）──────────────────────────────────────
    netlist = CT.build()["netlist"]
    pl = PN.place_real(netlist, max_cells=8)
    lay = MD.layout_from_place(pl, netlist)
    ok_lay = (len(lay.instances) == len(pl["insts"])
              and len(lay.nets) > 0
              and all(isinstance(i.x_nm, int) and isinstance(i.y_nm, int)
                      for i in lay.instances)
              and lay.die_w_nm > 0 and lay.die_h_nm > 0)
    check("M9 布局适配：8 个实例 + %d 条网建成 `Layout`（坐标全 int nm，"
          "µm→nm 只在适配器里换算一次）" % len(lay.nets), ok_lay,
          "inst=%d nets=%d" % (len(lay.instances), len(lay.nets)))

    # ── M10 反向：适配器不许改原对象 ──────────────────────────────────
    c0 = HD.build_inv_hd()
    before = [(r.layer, r.x0, r.y0, r.x1, r.y1) for r in c0.rects]
    _ = MD.cellview_from_dcells(c0)
    after = [(r.layer, r.x0, r.y0, r.x1, r.y1) for r in c0.rects]
    check("M10 适配器**只读**：转换后原 `dcells.Cell` 的几何逐位不变"
          "（既有模块零改动的机核形式）", before == after, "原对象被改了")

    dt = time.time() - T0
    check("M0 门禁耗时 %.2f s < %.0f s" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, "%.2f s" % dt)

    print()
    print("  [模型] 六类对象：Rect / Pin / TimingArc / CellView / Instance / Net / Layout")
    print("  [契约] 长度 nm 整数值（float 整数值归一化、非整数报错）· 单位进字段名")
    print("  [适配] 五颗单元往返逐位一致 · 两套规则集结构同构 · 适配器只读")
    print("  [体检] 引脚⇄金属：INV/NAND2 全覆盖 · DFF 4 引脚缺 pad（已量化登记，非豁免）")
    print("  [边界] 非 Liberty/LEF 解析器 · 无算法 · 不取代 dcells.Cell（等 B3 接主干）")
    print()
    if _FAILED:
        print("S1 有红色：%s" % ", ".join(_FAILED))
        return 1
    print("S1 全绿 · 统一数据模型落地：新增能力从此有「往哪儿填」的答案")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
