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
    L_M2,
    L_NWELL,
    L_POLY,
    L_VIA1,
    R,
    connectivity,
    extract_devices,
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
    # M2/M3 与 M1 同尺度（这一版只在 DFF 内部用到 M2；M3 暂未使用，先登记规则）
    "m2_w": 30, "m2_s": 30, "m2_a": 900,
    "m3_w": 30, "m3_s": 30, "m3_a": 900,
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


# ═══════════════════════════════════════════════════════════════════════════
# ④ DFF（22T · 11 列 × 每列 1 PMOS + 1 NMOS）—— TG 主从 + 输出缓冲
# ═══════════════════════════════════════════════════════════════════════════
#: DFF 的电学结构（**开关级已验证**，见 `run_ecore_e54_smoke.py` 的 J1）::
#:
#:   ckb  = ~CLK ; ckbb = ~ckb
#:   TG1 : D  ↔ m   ，P 栅 = ckbb，N 栅 = ckb     （CLK=0 时主级透明）
#:   m   : m → mb → m（主级存储环）
#:   TG2 : m  ↔ s   ，P 栅 = ckb ，N 栅 = ckbb    （CLK=1 时从级透明）
#:   s   : s → sb → s（从级存储环）
#:   q1  = ~s ; Q = ~q1 = s ; QN = ~s（独立缓冲，与 Q 同相取反）
#:
#: 🔴 **为什么是 22T 而不是抽象模型里的 24T**：`dcell.DFF.n_tr = 24` 是**抽象口径**
#: （含第二级输出缓冲），本版实测 22 管。面积/器件数一律按**实测几何**报，不套抽象模型 ——
#: 由判据 `J2` 机核「声明 22 = 抽取 22 = `dcell` 口径差 2」。
DFF_PITCH = 220          # 列节距（nm）
DFF_ISL = 150            # 每列有源岛宽
DFF_GSEG = 60            # 栅左偏（岛内）
DFF_NCOL = 11
DFF_W = 40 + DFF_NCOL * DFF_PITCH + 40

#: 行内总线 y 电平（nm）：M1 水平总线用；8 条电平够 11 个信号网共享（x 不重叠即可）
DFF_LEVELS = (285, 345, 405, 465, 525, 585, 645, 705)

#: (类型, 左端网, 右端网, P 栅网, N 栅网)；inv 的左右端即「源轨/输出」，栅即输入
DFF_COLS = (
    ("inv", "CLK", "ckb", None, None),
    ("inv", "ckb", "ckbb", None, None),
    ("tg", "D", "m", "ckbb", "ckb"),
    ("inv", "m", "mb", None, None),
    ("inv", "mb", "m", None, None),
    ("tg", "m", "s", "ckb", "ckbb"),
    ("inv", "s", "sb", None, None),
    ("inv", "sb", "s", None, None),
    ("inv", "s", "q1", None, None),
    ("inv", "q1", "Q", None, None),
    ("inv", "Q", "QN", None, None),
)

#: 每个网的**总线电平与 x 跨度**（nm）。同一电平上的两个网必须 x 不重叠（判据 J4 机核）。
DFF_BUS = {
    "CLK":  (0, 0, 115),
    "ckb":  (1, 160, 665),          # 低段（N 栅）
    "ckbH": (5, 665, 1215),         # 高段（P 栅），与低段用 M2 竖链
    "ckbb": (4, 380, 1325),         # 高段（P 栅）
    "ckbbL": (2, 1215, 1325),       # 低段（N 栅）
    "D":    (6, 0, 510),
    "m":    (3, 600, 1170),
    "mb":   (2, 820, 995),
    "s":    (6, 1260, 1875),
    "sb":   (0, 1480, 1655),
    "q1":   (1, 1920, 2095),
    "Q":    (5, 2140, 2500),
    "QN":   (7, 2360, 2500),
}

#: 双电平网之间的 M2 竖直链（x, 低电平索引, 高电平索引）
DFF_LINKS = ((665, 1, 5), (1325, 2, 4))


def _dff_x0(i: int) -> int:
    return 40 + i * DFF_PITCH


def _dff_lx(i: int) -> int:
    """左接触孔 x。"""
    return _dff_x0(i) + 30


def _dff_rx(i: int) -> int:
    """右接触孔 x。"""
    return _dff_x0(i) + 120


def _dff_gx(i: int) -> int:
    """栅接触孔 x。"""
    return _dff_x0(i) + 75


def _pad30(cx: int, cy: int, role: str = "pad") -> R:
    """30×30 的 M1 焊盘（接触孔 20 + 单边 5 包围）。"""
    return R(L_M1, cx - 15, cy - 15, cx + 15, cy + 15, role=role)


def _cont20(cx: int, cy: int, role: str = "cont_sd") -> R:
    return R(L_CONT, cx - 10, cy - 10, cx + 10, cy + 10, role=role)


def _m2v(x: int, y0: int, y1: int, net: str = None) -> R:
    return R(L_M2, x - 15, y0, x + 15, y1, net=net, role="m2")


def _m1h(xa: int, xb: int, y: int, net: str = None) -> R:
    return R(L_M1, xa, y - 15, xb, y + 15, net=net, role="bus")


def _via1(x: int, y: int, net: str = None) -> R:
    return R(L_VIA1, x - 15, y - 15, x + 15, y + 15, net=net, role="via1")


def build_dff_hd(route: dict = None) -> Cell:  # noqa: ARG001  (签名与其它单元一致)
    """DFF_X1_HD：**正沿触发** D 触发器（22T），输出 Q / QN。

    布局（nm · 11 列，每列一对 PMOS/NMOS）::

        y=1000 ┌────────────── VDD rail (M1) ──────────────┐
         945   │  PMOS 岛  [左段|栅|右段] × 11 列            │
         745   ├────────────────────────────────────────────┤
               │  行内总线区（M1 水平 × 8 电平 / M2 竖直）    │
         245   ├────────────────────────────────────────────┤
          45   │  NMOS 岛  [左段|栅|右段] × 11 列            │
           0   └────────────── VSS rail (M1) ──────────────┘

    三处关键设计（缺一条就布不通）：

    ① **每列只有一对器件** ⇒ 每列正好 1 条 poly，跨两行即 1P+1N；TG 列的 P/N 栅必须
       **断开成两条 poly**（互补控制），栅接触分别落在上/下半区的合法 y 上。
    ② **M1 只做水平总线、M2 只做竖直跨层** ⇒ 正交两层，交叉不必让步；
       11 个信号网按 x 跨度共享 8 条电平（判据 J4 机核「同电平不重叠」）。
    ③ **互补时钟要同时到上下半区**：`ckb`/`ckbb` 各拆成低段 + 高段，段间用 M2 竖链跨接
       （`DFF_LINKS`）—— 因为 TG 的 P 栅接触只能落在上半区、N 栅只能落在下半区。
    """
    rects = [R(L_M1, 0, 0, DFF_W, RAIL_HD, role="rail"),
             R(L_M1, 0, H_ROW_HD - RAIL_HD, DFF_W, H_ROW_HD, role="rail"),
             R(L_NWELL, 0, 705, DFF_W, 985, role="nwell")]
    devs = []
    for i, (kind, a, b, pg, ng) in enumerate(DFF_COLS):
        X = _dff_x0(i)
        rects += [R(L_DIFF, X, 45, X + DFF_ISL, 245, role="diff"),
                  R(L_DIFF, X, 745, X + DFF_ISL, 945, role="diff")]
        if kind == "inv":
            rects.append(R(L_POLY, X + DFF_GSEG, 15, X + DFF_GSEG + L_GATE_HD, 975, role="gate"))
        else:
            # TG：P/N 栅必须互补 ⇒ 两条 poly 断开（430..505 间隔 75 ≥ poly_s 50）
            rects += [R(L_POLY, X + DFF_GSEG, 15, X + DFF_GSEG + L_GATE_HD, 430, role="gate_n"),
                      R(L_POLY, X + DFF_GSEG, 505, X + DFF_GSEG + L_GATE_HD, 975, role="gate_p")]
        # 接触孔 + M1 焊盘（两行各左右一个）
        for cy in (145, 845):
            for cx in (_dff_lx(i), _dff_rx(i)):
                rects += [_cont20(cx, cy), _pad30(cx, cy)]
        devs.append(("pmos", W_DEV_HD, L_GATE_HD, a if kind == "inv" else pg,
                     "VDD" if kind == "inv" else a, b))
        devs.append(("nmos", W_DEV_HD, L_GATE_HD, a if kind == "inv" else ng,
                     "VSS" if kind == "inv" else a, b))

    lv = DFF_LEVELS
    # ① 电源引下（INV 列）：P 左 → VDD 轨；N 左 → VSS 轨（不同网，各自独立竖带）
    for i, (kind, _a, _b, _p, _n) in enumerate(DFF_COLS):
        if kind != "inv":
            continue
        rects += [R(L_M1, _dff_lx(i) - 15, 830, _dff_lx(i) + 15, H_ROW_HD - RAIL_HD, role="strap"),
                  R(L_M1, _dff_lx(i) - 15, RAIL_HD, _dff_lx(i) + 15, 160, role="strap")]
    # ② 信号列：左右两侧各一条 M2 竖带（跨 130..860 把 P/N 两个焊盘连成同一网），
    #    再在总线电平处打 V1 接到 M1 总线
    for i, (kind, a, b, _p, _n) in enumerate(DFF_COLS):
        # 🔴 INV 列**左侧是电源轨**（P 接 VDD、N 接 VSS），绝不能加竖带 —— 加了就是把
        # VDD 与 VSS 短在一起（初版就这么错的：LVS 里每个器件第二个端子都成了独立无名网）。
        # TG 列的左右两侧才是「同一个网的两个器件端子」，需要竖带。
        sides = ([(_dff_lx(i), a)] if kind == "tg" else []) + [(_dff_rx(i), b)]
        for (x, net) in sides:
            if net in ("VDD", "VSS"):
                continue
            key = net
            if net == "ckb" and kind == "tg":
                key = "ckb" if i == 2 else "ckbH"
            if net == "ckbb" and kind == "tg":
                key = "ckbb" if i == 2 else "ckbbL"
            rects.append(_m2v(x, 130, 860, net=net))
            # 🔴 竖带与**两端焊盘**之间也必须有 V1：M1 焊盘和 M2 竖带是不同层，
            # 少了这两个孔，LVS 会看到「每个器件的第二个端子都是独立无名网」（初版就是这样）。
            rects += [_via1(x, 145, net=net), _via1(x, 845, net=net),
                      _via1(x, lv[DFF_BUS[key][0]], net=net)]
    # ③ 栅接触：INV 在自身输入网的电平；TG 的 P/N 栅分别在各自电平
    for i, (kind, a, _b, pg, ng) in enumerate(DFF_COLS):
        if kind == "inv":
            y = lv[DFF_BUS[a][0]]
            rects += [_cont20(_dff_gx(i), y, "cont_gate"), _pad30(_dff_gx(i), y)]
        else:
            yp, yn = lv[DFF_BUS[pg if i == 2 else "ckbH"][0]], lv[DFF_BUS[ng if i == 2 else "ckbbL"][0]]
            rects += [_cont20(_dff_gx(i), yp, "cont_gate"), _pad30(_dff_gx(i), yp),
                      _cont20(_dff_gx(i), yn, "cont_gate"), _pad30(_dff_gx(i), yn)]
    # ④ M1 水平总线
    for net, (lv_i, xa, xb) in DFF_BUS.items():
        rects.append(_m1h(xa, xb, lv[lv_i], net=net))
    # ⑤ 双电平时钟的 M2 竖链
    for (x, lo, hi) in DFF_LINKS:
        rects.append(_m2v(x, lv[lo], lv[hi]))
        rects += [_via1(x, lv[lo]), _via1(x, lv[hi])]
    # ⑥ 引脚（M1 pad 70×70；D/CLK 在左缘，Q/QN 在右缘）
    pins = {"VDD": R(L_M1, 0, H_ROW_HD - RAIL_HD, DFF_W, H_ROW_HD, net="VDD"),
            "VSS": R(L_M1, 0, 0, DFF_W, RAIL_HD, net="VSS"),
            "D": R(L_M1, 0, lv[6] - 35, 70, lv[6] + 35, net="D"),
            "CLK": R(L_M1, 0, lv[0] - 35, 70, lv[0] + 35, net="CLK"),
            "Q": R(L_M1, DFF_W - 70, lv[5] - 35, DFF_W, lv[5] + 35, net="Q"),
            "QN": R(L_M1, DFF_W - 70, lv[7] - 35, DFF_W, lv[7] + 35, net="QN")}
    return Cell("DFF_X1_HD", DFF_W, H_ROW_HD, rects, pins, devs)


CELLS = {"INV_X1_HD": build_inv_hd, "NAND2_X1_HD": build_nand2_hd,
         "DFF_X1_HD": build_dff_hd}

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


def run_lvs_pos(cell: Cell) -> dict:
    """**按版图顺序的双射 LVS**（补 `dcells.run_lvs` 在大单元上的不足）。

    🔴 为什么需要它：`dcells.run_lvs` 用 `_canon` 做规范形，而 `_canon` 的排序键里
    含 `str(gate)` —— 对 2–4 个器件的 INV/NAND2 恰好稳定，但 22 个器件、大半栅网是
    **无名内部节点**时，两侧的排序必然不同 ⇒ **必然误报**（实测 22/22 条全不匹配，
    而电路其实是对的）。这是既有实现的**口径问题**，不是版图问题。

    判据是**双射**而不是排序：
      · 版图器件按 (类型, 栅节点号) 排序 —— 节点号随版图列序单调，故等价于「从左到右」；
      · 每对 (版图网节点 ↔ 声明网名) 建立映射，同一节点被绑到两个名字即判失败；
      · 每个声明引脚必须有对应的版图网。
    这**不会漏判**（单值双射，接错必被抓），只在「合法但器件次序不同」时误报 ——
    对自生成版图无影响，但**不宣称是通用 LVS**。
    """
    _ = connectivity(cell)
    # 器件排序键 = **沟道自身的 x**（几何序，与「声明按列序」一致）。
    # 🔴 两版都错过的坑：① 按节点号排 —— 节点号不保证单调；② 按「栅网的 x」排 ——
    # 同一个网驱动多列时（ckb 同时驱动 INV_CK2 与 TG1 的 N 栅）取 min 会把不同列压成同键。
    got = sorted(extract_devices(cell),
                 key=lambda d: (d["kind"], d.get("x", 10 ** 9), d.get("y", 0)))
    exp = [{"kind": k, "w": w, "l": l, "gate": g, "sd": [a, b]}
           for (k, w, l, g, a, b) in cell.devices_expected]
    exp = sorted(exp, key=lambda d: d["kind"])          # 稳定排序：保留声明列序
    if len(got) != len(exp):
        return {"n": 1, "mismatches": [("device_count", "%d vs %d" % (len(got), len(exp)))],
                "n_got": len(got), "n_exp": len(exp)}
    nmap, rmap, mism = {}, {}, []

    def bind(node, name, where):
        if node is None:
            mism.append(("dangling", where))
            return
        if node in nmap and nmap[node] != name:
            mism.append(("net_split", "%s: %s vs %s" % (where, nmap[node], name)))
        if name in rmap and rmap[name] != node:
            mism.append(("net_merge", "%s: %s" % (where, name)))
        nmap[node] = name
        rmap[name] = node

    for i, (g, e) in enumerate(zip(got, exp)):
        if (g["kind"], g["w"], g["l"]) != (e["kind"], e["w"], e["l"]):
            mism.append(("device", "#%d %s/%d/%d vs %s/%d/%d"
                         % (i, g["kind"], g["w"], g["l"], e["kind"], e["w"], e["l"])))
            continue
        bind(g["gate"], e["gate"], "d%d.gate" % i)
        # 🔴 **按几何位置成对**（左=sd[0]、右=sd[1]），不能排序后配对：
        #   `sorted()` 对「网名」和「节点号」的排序口径不同，会把左右对调 ⇒ 16 条假失配。
        gsd = g["sd"]
        esd = list(e["sd"])
        if len(gsd) != 2:
            mism.append(("sd_count", "d%d: %d" % (i, len(gsd))))
            continue
        for k in range(2):
            bind(gsd[k], esd[k], "d%d.sd%d" % (i, k))
    for name in cell.pins:
        if name not in rmap:
            mism.append(("floating_pin", name))
    return {"n": len(mism), "mismatches": mism, "n_got": len(got), "n_exp": len(exp),
            "nodes": len(nmap)}


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
