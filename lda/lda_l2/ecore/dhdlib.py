"""E53 · **HD 标准单元库**（高密度 INV/NAND2）—— 把 E52 的几何下界变成可布线实体。

═══════════════════════════════════════════════════════════════════════════════
为什么要有这个模块（E52 之后必须走的一步）
───────────────────────────────────────────────────────────────────────────────
E50/E51 查出的天花板（布通率 87%）根因链是：

    pad 240nm（= 布线 VIA 200 + 2·ENC 20 的**必然**）
      ⇒ 1500nm 行高的空闲带只剩 2 条 340nm 节距轨道
      ⇒ 而这 2 条正好被 pin access 自己用掉
      ⇒ M2 不能做布线层 ⇒ 只剩 M4 一层竖直资源
      ⇒ 列供给/需求比恒 1.33–1.43 ⇒ 渐近线

`dnode` 已经把「节点」参数化并算出：DEMO28（pad 70nm）行内有 **5 条**轨道、扣 pin
access 剩 3 条 ⇒ 行内布线可行 ⇒ 列需求降到 **0.512×**。但那只是**几何下界**。

本模块把那个下界变成**实体**：按 28nm 级规则重新画 INV/NAND2，使
  · 引脚 pad = **70×70nm**（= `VIA 50 + 2·ENC 10`，同样是必然，不是选美）；
  · 栅接触**不再需要 poly 焊盘**（`cont 20 + 2×enc 5 = 30 = poly_w`，恰好放得下）；
  · 行高 **1000nm**，行内留下 **≥5 条** 140nm 节距的 M2 轨道。

═══════════════════════════════════════════════════════════════════════════════
可复用 / 可扩展的设计（这一版真正想交付的架构）
───────────────────────────────────────────────────────────────────────────────
1. 🔴 **规则集是参数，不是常量**：`HD_RULES` 与 `dcells.RULES` 同形；所有坐标都由它派生，
   换节点只换 dict（`dcells.run_drc(cell, rules=...)` 也是同一份实现）。
2. 🔴 **判定器不重写**：DRC / LVS / 连通性 / 器件抽取 / 寄生 R 全部复用 `dcells` 的
   实现 —— 本模块**只描述几何**，不复制任何检查逻辑（两份真源必然漂移）。
3. 🔴 **单元由「拓扑约束 + 规则」生成，不是手抄一堆魔数**：`_Stack` 把「电源轨 / 有源行 /
   栅 / 接触孔 / M1 带」的推导写成一处，INV 与 NAND2 共享同一套放置原语。

═══════════════════════════════════════════════════════════════════════════════
诚实边界（必须随任何对外引用一起给出）
───────────────────────────────────────────────────────────────────────────────
1. 🔴 **规则集是自建的 LDA-DEMO28**（28nm 级**教科书尺度**），**不是任何 foundry PDK**。
   数字参照公开工艺讨论的量级，不保证可制造 ⇒ **不得作制造/性能宣称**。
2. 🔴 **不是 SPICE**：器件只有 W/L 与方块电阻；`device_scale` 只缩几何，**器件电学不变**
   ⇒ 本库与 `dcells`（DEMO45）之间的延迟/功耗**不可比**，只有**几何容量**可比。
3. 🔴 **引脚只做 M1**（无 M2 内部绕行、无多高度引脚）：真实 HD 库的 pin access 由单元库
   自带 M2 图形完成，本库把这件事留给布线器（这正是 E51 判定的边界）。
4. 🔴 判决路径不引入 LLM；全部确定性整数几何。
"""
from __future__ import annotations

from . import dnode as DN
from .dcells import (
    Cell,
    L_CONT,
    L_DIFF,
    L_M1,
    L_NWELL,
    L_POLY,
    R,
    run_drc,
    run_lvs,
)

# ═══════════════════════════════════════════════════════════════════════════
# ① 规则集（与 dcells.RULES 同形 ⇒ 同一份 DRC 可直接查）
# ═══════════════════════════════════════════════════════════════════════════
HD_RULES = {
    "diff_w": 50, "diff_s": 50, "diff_a": 2500,
    "poly_w": 30, "poly_s": 50, "poly_a": 900,
    "cont_w": 20, "cont_s": 25, "cont_enc_diff": 5, "cont_enc_poly": 5,
    "cont_enc_m1": 5, "gate_cont": 20,
    "m1_w": 30, "m1_s": 30, "m1_a": 900,
    "nwell_enc": 40,
}

#: 布线侧规则（nm）—— 🔴 **从 `dnode.DEMO28` 派生，不在这里手抄数字**。
#: `dproc.use()` 用的是同一份规则的 µm 版本（`Node.route_rules("um")`）。
HD_ROUTE = DN.DEMO28.route_rules("nm")

#: 行高（nm）。两单元**等高**（真实 std-cell 库的前提，E45 披露里那条「等高」限制在此消除）。
H_ROW_HD = 1000
RAIL_HD = 30          # M1 电源轨高度 = m1_w
W_DEV_HD = 200        # 器件宽度（有源高度）
L_GATE_HD = 30        # 栅长 = poly_w


def pad_nm(route: dict = None) -> int:
    """引脚 pad 边长。**由布线规则推出**（孔 + 两侧包围），不是手填的数。"""
    r = HD_ROUTE if route is None else route
    return r["via"] + 2 * r["enc"]


# ═══════════════════════════════════════════════════════════════════════════
# ② 放置原语（INV / NAND2 共用，避免手抄坐标）
# ═══════════════════════════════════════════════════════════════════════════
def _cont(cx: int, cy: int, role: str) -> R:
    """接触孔（正方形，边长 = `cont_w`），中心对齐 `(cx, cy)`。"""
    h = HD_RULES["cont_w"] // 2
    return R(L_CONT, cx - h, cy - h, cx + h, cy + h, role=role)


def _stack(h: int = H_ROW_HD) -> dict:
    """竖直「栈」的公共坐标：电源轨 + 有源行 + NWELL。

    布局（自下而上）::

        y=h        ┌──── VDD rail (M1) ────┐
        y=h-30     └───────────────────────┘
                   ↑ 25nm 缝（VDD 引下带在这里接轨）
        PMOS 有源   y=h-255 … h-55   (W=200)
        ─ 行内间隙（放输入引脚 + 输出绕行）─
        NMOS 有源   45 … 245         (W=200)
        y=0        ├──── VSS rail (M1) ────┤

    🔴 与 DEMO45 的关键差别：**PMOS 紧贴 VDD 轨**（间隙 25nm）。
    这样才能让「PMOS 中间那段的 VDD 引下带」很短，输出 Y 才能在 PMOS **下方**
    用 M1 绕行，而不必借 M2 跨越（借 M2 会吃掉行内一条宝贵轨道）。
    """
    vdd = (h - RAIL_HD, h)
    pmos = (h - 255, h - 55)
    nmos = (45, 45 + W_DEV_HD)
    nwell = (pmos[0] - HD_RULES["nwell_enc"], pmos[1] + HD_RULES["nwell_enc"])
    return {"h": h, "vdd": vdd, "vss": (0, RAIL_HD), "pmos": pmos,
            "nmos": nmos, "nwell": nwell}


def _rails(w: int, st: dict) -> list:
    return [R(L_M1, 0, st["vss"][0], w, st["vss"][1], role="rail"),
            R(L_M1, 0, st["vdd"][0], w, st["vdd"][1], role="rail")]


def _strap(x0: int, y0: int, y1: int, role: str = "strap") -> R:
    """竖直 M1 带（宽度 = `m1_w`）。"""
    return R(L_M1, x0, y0, x0 + HD_RULES["m1_w"], y1, role=role)


def _band(x0: int, x1: int, y0: int, role: str = "strap") -> R:
    """水平 M1 带（高度 = `m1_w`）。"""
    return R(L_M1, x0, y0, x1, y0 + HD_RULES["m1_w"], role=role)


def _pad(x0: int, y0: int, route: dict = None, net: str = None) -> R:
    """引脚 pad（正方形，边长由布线规则推出）。"""
    p = pad_nm(route)
    return R(L_M1, x0, y0, x0 + p, y0 + p, net=net, role="pin")


# ═══════════════════════════════════════════════════════════════════════════
# ③ INV（1 PMOS + 1 NMOS）· w = 280 = 2×140（列网格整数倍）
# ═══════════════════════════════════════════════════════════════════════════
def build_inv_hd(route: dict = None) -> Cell:
    """INV_X1_HD：栅 A · 输出 Y。

    x 分配（nm）::

        0    70  125 155      240 280
        ├─A──┤   ├gate┤        │   │
              ↑ A 引下带(35..160) 到栅接触 y=300
                                    └ Y pad(210..280)

    · 有源 x 40..240；栅 125..155（L=30）；源漏段 40..125 / 155..240（各 85 ≥ diff_w 50）
    · 栅接触直接落在 30nm 宽的 poly 条内（`cont 20 + 2×5 = 30`）⇒ **不需要 poly 焊盘**
    """
    st = _stack()
    w = 280
    rects = _rails(w, st)
    rects.append(R(L_NWELL, 0, st["nwell"][0], w, st["nwell"][1], role="nwell"))
    rects += [R(L_DIFF, 40, st["nmos"][0], 240, st["nmos"][1], role="diff"),
              R(L_DIFF, 40, st["pmos"][0], 240, st["pmos"][1], role="diff")]
    # 栅：跨双有源，上下各延伸 poly_w 出有源
    rects.append(R(L_POLY, 125, st["nmos"][0] - 30, 155, st["pmos"][1] + 30, role="gate"))
    # 接触孔：两行各一对源漏，+ 一个栅接触（落在 poly 条内，居中）
    y_n = (st["nmos"][0] + st["nmos"][1]) // 2
    y_p = (st["pmos"][0] + st["pmos"][1]) // 2
    rects += [_cont(60, y_n, "cont_sd"), _cont(205, y_n, "cont_sd"),
              _cont(60, y_p, "cont_sd"), _cont(205, y_p, "cont_sd"),
              _cont(140, 310, "cont_gate")]
    # M1：电源引下 / 输出竖带 / A 与 Y 的 pin pad 及其连接
    rects += [_strap(45, st["vss"][1], 175),                     # VSS → NMOS 源
              _strap(45, y_p - 15, st["vdd"][0]),                # VDD → PMOS 源（只从孔起）
              _strap(190, y_n - 25, y_p + 25),                   # Y：两行漏端 ↔ pad
              _pad(0, 270, route, "A"),
              _band(35, 160, 295),                               # A pad → 栅接触
              _pad(210, 640, route, "Y")]
    pins = {"VDD": R(L_M1, 0, st["vdd"][0], w, st["vdd"][1], net="VDD"),
            "VSS": R(L_M1, 0, st["vss"][0], w, st["vss"][1], net="VSS"),
            "A": _pad(0, 270, route, "A"),
            "Y": _pad(210, 640, route, "Y")}
    devs = [("pmos", W_DEV_HD, L_GATE_HD, "A", "VDD", "Y"),
            ("nmos", W_DEV_HD, L_GATE_HD, "A", "VSS", "Y")]
    return Cell("INV_X1_HD", w, H_ROW_HD, rects, pins, devs)


# ═══════════════════════════════════════════════════════════════════════════
# ④ NAND2（2 串 NMOS + 2 并 PMOS）· w = 430
# ═══════════════════════════════════════════════════════════════════════════
def build_nand2_hd(route: dict = None) -> Cell:
    """NAND2_X1_HD：输入 A/B · 输出 Y。

    · 有源 x 40..360；两条栅 100..130 / 180..210（间距 50 = `poly_s`）
      ⇒ 三个源漏段 40..100(60) / 130..180(50) / 210..360(150)，全部 ≥ `diff_w 50`
    · NMOS：VSS | A | n1 | B | Y；PMOS：Y | A | VDD | B | Y
    · 输出 Y 的**左右两段互连**走 `y=700..730` 的 M1 横带（在 PMOS 下方）——
      因为 VDD 引下带紧贴 PMOS（只到 y 830..970），**不会挡住这条横带**
    """
    st = _stack()
    w = 430
    rects = _rails(w, st)
    rects.append(R(L_NWELL, 0, st["nwell"][0], w, st["nwell"][1], role="nwell"))
    rects += [R(L_DIFF, 40, st["nmos"][0], 360, st["nmos"][1], role="diff"),
              R(L_DIFF, 40, st["pmos"][0], 360, st["pmos"][1], role="diff")]
    # 🔴 栅距取 **60** 而不是规则下限 50：中间源漏段要同时放「接触孔 20 + 栅-孔间距 20×2」
    #  ⇒ 段宽必须 ≥60，否则 `gate_cont` 必红（这是组合约束，不是放宽规则）。
    rects += [R(L_POLY, 90, st["nmos"][0] - 30, 120, st["pmos"][1] + 30, role="gate"),
              R(L_POLY, 200, st["nmos"][0] - 30, 230, st["pmos"][1] + 30, role="gate")]
    y_n = (st["nmos"][0] + st["nmos"][1]) // 2
    y_p = (st["pmos"][0] + st["pmos"][1]) // 2
    rects += [_cont(60, y_n, "cont_sd"), _cont(150, y_n, "cont_sd"), _cont(315, y_n, "cont_sd"),
              _cont(60, y_p, "cont_sd"), _cont(150, y_p, "cont_sd"), _cont(315, y_p, "cont_sd"),
              _cont(105, 310, "cont_gate"), _cont(215, 310, "cont_gate")]
    rects += [_strap(45, st["vss"][1], 175),                    # VSS → NMOS A 源
              _strap(135, 120, 175),                            # n1（内部节点）
              _strap(135, y_p - 15, st["vdd"][0]),              # VDD → PMOS 中间段（只从孔起）
              _pad(0, 270, route, "A"),
              _band(35, 125, 295),                              # A pad → 栅 A 接触
              _pad(195, 270, route, "B"),                       # B pad 直接盖住栅 B 接触
              _strap(45, 660, y_p + 25),                        # Y 左竖（PMOS 左段）
              _band(45, w, 660),                                # Y 横带（PMOS 下方，直达 pad）
              _strap(300, 120, y_p + 25),                       # Y 右竖（两行右段 + 横带）
              _pad(360, 640, route, "Y")]
    pins = {"VDD": R(L_M1, 0, st["vdd"][0], w, st["vdd"][1], net="VDD"),
            "VSS": R(L_M1, 0, st["vss"][0], w, st["vss"][1], net="VSS"),
            "A": _pad(0, 270, route, "A"),
            "B": _pad(195, 270, route, "B"),
            "Y": _pad(360, 640, route, "Y")}
    devs = [("pmos", W_DEV_HD, L_GATE_HD, "A", "Y", "VDD"),
            ("pmos", W_DEV_HD, L_GATE_HD, "B", "VDD", "Y"),
            ("nmos", W_DEV_HD, L_GATE_HD, "A", "VSS", "n1"),
            ("nmos", W_DEV_HD, L_GATE_HD, "B", "n1", "Y")]
    return Cell("NAND2_X1_HD", w, H_ROW_HD, rects, pins, devs)


CELLS = {"INV_X1_HD": build_inv_hd, "NAND2_X1_HD": build_nand2_hd}

#: 网表单元名 → HD 库单元名（键与 `dpnr.CELL_MAP` 同口径：网表里是 `INV`/`NAND2`）
CELL_MAP = {"INV": "INV_X1_HD", "NAND2": "NAND2_X1_HD"}


# ═══════════════════════════════════════════════════════════════════════════
# ⑤ 「行内可用轨道」实测（从**真实矩形**量，不再用 dnode 的估算）
# ═══════════════════════════════════════════════════════════════════════════
def pin_bands(cell: Cell, route: dict = None, grow: int = None) -> list:
    """该单元**引脚 pad 在 y 上占用的带**（含 M2 接入焊盘的额外占用）。

    `grow`：布线时每个引脚还要落一块 M2 焊盘（边长 = pad），实际占用比 M1 pad 更宽，
    这里按「M1 pad 与 M2 焊盘取并集」算 —— 保守，避免把「实际不能用」的轨道算成可用。
    """
    p = pad_nm(route)
    g = p if grow is None else grow
    out = []
    for name, r in cell.pins.items():
        if name in ("VDD", "VSS"):
            continue
        cy = (r.y0 + r.y1) / 2.0
        half = max(r.h, g) / 2.0
        out.append((cy - half, cy + half, name))
    return out


def inner_tracks(cell: Cell, route: dict = None) -> dict:
    """**行内可用水平轨道**（nm，相对行底）。

    🔴 这是把 E52 的「几何下界」换成**实测**的那一步：跑遍该单元**真实**的
    引脚 pad 带，取补集，再按 `pitch` 切片。返回的不只是条数，还有每条轨道的 y。

    🔴 只避开**引脚 pad**，不避 M1 内部带 —— 因为行内布线用的是 **M2**（在 M1 之上）。
    这是 E51 的教训：它把水平段放在**引脚 y** 上（M3 层），必然撞同行异网 pad。
    """
    r = HD_ROUTE if route is None else route
    pitch, w = r["pitch"], r["w_min"]
    raw = pin_bands(cell, r)
    bands = sorted((a, b) for (a, b, _n) in raw)
    merged: list = []
    for (a, b) in bands:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    free, prev = [], 0
    for (a, b) in merged:
        if a > prev:
            free.append((prev, a))
        prev = max(prev, b)
    h = cell.h
    if h > prev:
        free.append((prev, h))
    # 电源轨本身也要让开（轨是 M1，但 M2 在其上无所谓；真正要让的是「pad + 轨」？
    # 轨不挡 M2 ⇒ 只按容量切轨道，起点从 rail 上方半个 w 开始，保证金属不压轨边）
    tracks, per_band = [], []
    for (a, b) in free:
        n = int((b - a) // pitch)
        if n <= 0:
            per_band.append(0)
            continue
        per_band.append(n)
        for i in range(n):
            tracks.append(round(a + pitch / 2.0 + i * pitch, 3))
    return {"n": len(tracks), "tracks": tracks, "free_bands": free,
            "per_band": per_band, "pitch": pitch, "w": w,
            "pin_bands": [(round(a, 1), round(b, 1), n) for (a, b, n) in raw]}


def lib_summary(route: dict = None) -> dict:
    """整库汇总：面积 / pad / 行内轨道 —— 与 DEMO45 逐项对照的输入。"""
    out = {"cells": {}, "pad_nm": pad_nm(route), "h_row": H_ROW_HD}
    for name, f in sorted(CELLS.items()):
        c = f(route)
        it = inner_tracks(c, route)
        d = run_drc(c, HD_RULES)
        lv = run_lvs(c)
        out["cells"][name] = {
            "w_nm": c.w, "h_nm": c.h, "area_um2": c.w * c.h / 1e6,
            "n_dev": len(c.devices_expected), "drc": d["n"], "lvs": lv["n"],
            "n_inner_tracks": it["n"], "tracks_nm": it["tracks"],
            "pin_y": {k: ((v.y0 + v.y1) / 2.0, (v.x0 + v.x1) / 2.0)
                      for k, v in c.pins.items() if k not in ("VDD", "VSS")},
            "cells_per_um2": 1e6 / (c.w * c.h),
        }
    return out


HD_DISCLOSURE = {
    "what": "28nm 级（LDA-DEMO28）HD 标准单元 INV/NAND2：pad 70nm、等高行 1000nm、行内 5 条 M2 轨道",
    "claimable": False,
    "not_foundry_pdk": True,
    "limits": [
        "规则集 LDA-DEMO28 是**自建教科书尺度**，量级参照公开工艺讨论，非任何 foundry PDK",
        "器件电学不随节点变（只有 W/L 与方块电阻，无 I-V/电容/温度）⇒ 与 DEMO45 之间"
        "只能比**几何容量**，不可比延迟/功耗",
        "只有 M1 内部互连与 M1 引脚；无 M2 内部绕行、无多高度引脚、无 dummmy/filler/well-tap",
        "只做 INV/NAND2 两种单元（DFF 仍未建模）⇒ 不是完整标准单元库",
        "DRC 只查 min width/space/area/enclosure/nwell 包住，无密度/OPC/天线/ESD 规则",
        "净增 0 锚（整数几何与计数 ⇒ resid≡0）⇒ 能力以门禁形态落地",
    ],
}
