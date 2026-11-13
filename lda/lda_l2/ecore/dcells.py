"""B1 · 标准单元**内部几何**（晶体管级）—— 把 E36 的「包围盒 + 有源标记」换成真几何。

═══════════════════════════════════════════════════════════════════════════════
为什么要有这个模块（B1 的定位）
───────────────────────────────────────────────────────────────────────────────
`ddetail.real_cell_geom()` 的诚实原文是：**「单元尺度仅 ~0.08µm 宽，内部画不下真实
晶体管，故以单元中心固定边长的小方块标记『此处有源器件』」**。也就是说此前的
「真实单元几何」只有：有源标记方块 + 引脚焊垫 + 通孔栈 —— **没有栅/源漏/接触孔**，
因此：

  · 真实 DRC 做不了（没有 poly/contact 可查，只有金属与孔）；
  · 真实 LVS 做不了（抽不出器件，只能比对金属连通）；
  · 真实 R 提取做不了（无栅电阻、无扩散电阻、无接触电阻）。

本模块给出**可机核的晶体管级单元**：每颗标准单元由 DIFF / POLY / CONT / M1 / NWELL
矩形构成，器件（NMOS/PMOS 的 W/L）由**几何求交**抽出，连通性由**接触孔 + 同层合并 +
DIFF 被 POLY 切段**共同推出，DRC 按显式规则集查，寄生 R 按方块电阻逐段积分。

═══════════════════════════════════════════════════════════════════════════════
诚实边界（必须随任何对外引用一起给出）
───────────────────────────────────────────────────────────────────────────────
1. 🔴 **规则集是自建的「LDA-DEMO45」，不是任何 foundry 的 PDK 真值**。数字取自
   45nm 量级的公开教科书尺度（M1 线宽 60nm / 间距 60nm、栅长 50nm、接触孔 45nm），
   但**不保证与任何真实工艺可制造**。因此本模块的任何结论**不得作制造/性能宣称**。
2. 🔴 **不是 SPICE**：器件模型只有 W/L 与方块电阻，无 I-V、无电容、无温度/噪声。
   R 提取是**一阶方块电阻**（sheet resistance）口径，不是场求解器。
3. 🔴 **判决路径不引入 LLM**；本模块全部是确定性整数几何 + 闭式算术。
4. 🔴 **不报 TOPS / fJ-op / 能效**（未流片）。面积/晶体管数只作设计期口径。
5. ⚠️ 一阶近似：接触孔按固定电阻、扩散按单方块串、栅按单段 poly 条 —— 与真实
   3D 电流分布相比**偏乐观**（尤其窄宽度下的电流拥挤未建模）。

═══════════════════════════════════════════════════════════════════════════════
坐标与单位
───────────────────────────────────────────────────────────────────────────────
· 全部整数，单位 **nm**（1 dbu = 1 nm，与 `gds_export.DBU` 一致）。
· 矩形 `R(layer, x0, y0, x1, y1)`；「相接」判定含边贴边（`x1 == other.x0`）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ---- 层号（真源 = gds_export.LIB_LAYER_E_*；此处断言，防两份真源漂移）----
from ..gds_export import (
    LIB_LAYER_E_CONT as L_CONT,
    LIB_LAYER_E_DIFF as L_DIFF,
    LIB_LAYER_E_M1 as L_M1,
    LIB_LAYER_E_M2 as L_M2,
    LIB_LAYER_E_M3 as L_M3,
    LIB_LAYER_E_POLY as L_POLY,
    LIB_LAYER_E_VIA1 as L_VIA1,
)
from .ddetail import L_V2

#: 🔴 **v0.9.358/E55 补层**：布线器（`dpnr`/`ddrc_lvs`）用 `gds_export` 的真源层号，
#: 而本模块此前只认到 M3 ⇒ M4 与 VIA2（M3↔M4）在联合场景里**没有连通性**，
#: 走线自身被切成多个分量（实测 8 单元 `label_report.n_unrouted` 从 7 涨到 56）。
#: 这里从**真源**取号，不另立常量。
#: ⚠️ 诚实披露一处历史双口径：`ddetail.L_V2 = 26` 注释写「M2↔M3 通孔」，而
#: `gds_export` 的 26 是 **PAD（钝化开口）**、真正的 M2↔M3 是 28。单元几何（E53/E54）
#: 一直用 26 画内部通孔 ⇒ 内部自洽但落库后层号含义与真源不一致。本版**不改**它
#: （改号会让 E53/E54 的既有几何与 GDS 字节全部变动），只把 28/29 补进桥接表，
#: 使布线侧与单元侧能在同一张图上求连通性。这个不一致列为已知边界。
from ..gds_export import (
    LIB_LAYER_E_M4 as L_M4,
    LIB_LAYER_E_VIA2 as L_VIA2,
)

#: NWELL 无现成真源（此前电子域只用 DIFF/POLY/CONT/M1），取未占用号 19 并在此登记。
L_NWELL = 19

# ---- 自建规则集 LDA-DEMO45（nm）----
RULES = {
    "diff_w": 100, "diff_s": 100, "diff_a": 20000,
    "poly_w": 50, "poly_s": 120, "poly_a": 2500,
    "cont_w": 45, "cont_s": 60, "cont_enc_diff": 15, "cont_enc_poly": 15,
    "cont_enc_m1": 10, "gate_cont": 40,
    "m1_w": 60, "m1_s": 60, "m1_a": 3600,
    "nwell_enc": 80,
}

#: 🔴 **v0.9.349 引脚可接入化**（`PINS_V2_NOTE`）。判据不是「好看」，是几何硬约束：
#:  · 路由器在每个引脚上要落 `VIA1 = 0.20` 见方，并由引脚金属提供 `ENC = 0.02` 单边包围
#:    ⇒ 引脚 pad 两维必须 ≥ `0.20 + 2×0.02 = 0.24`；接入点还要离 pad 边 ≥0.12。
#:  · 同一单元的多个引脚最终都要各自占用一条 M4 列（同一行内的 M4 y 区间必然重叠），
#:    两个不同网的 M3 接入焊盘 = 0.242 见方 + 间距 0.10 ⇒ **接入点必须 ≥0.342µm**。
#:  旧几何（v0.9.348）：A/Y 中心只差 **0.0375µm**、NAND2 的 B/Y 差 **0.0175µm**，
#:  引脚高度 65–75nm（装不下 0.20 孔）⇒ 只能由路由器外挂 M1 焊盘、再把接入点沿 x 硬挪，
#:  结果 M3 焊盘/跳线互相叠 ⇒ E45 的 14 条残差（8 条间距 + 6 条孔包围）。
#:  本版：**pad 统一 240×240**，pad 中心 x 取 120 / 480 / 840 nm（库级列网格，两两恰一个 pitch），
#:  纵向按「不同网的 y 带 ≥0.36」分配 ⇒ 接入点 = pad 中心（**零移动**）、跳线长度归零。
PINS_V2_NOTE = {
    "pad_nm": 240,
    "access_x_nm": {"INV_X1": {"A": 120, "Y": 480},
                    "NAND2_X1": {"A": 120, "B": 480, "Y": 840},
                    #: 🔴 NOR2 的 Y 在**中间段**（并联结构的输出），若沿用 NAND2 的
                    #: 三格分配，Y 的绕行竖条必然穿过 B pad（实测短路）⇒ 改「A/B 同带
                    #: 两侧、Y 下沉」：A 120 · B 720 · Y 120@y900。
                    "NOR2_X1": {"A": 120, "B": 720, "Y": 120}},
    "need_pad_nm": 240,      # VIA 200 + 2×ENC 20
    "need_sep_um": 0.342,    # M3 pad 0.242 + S_MIN 0.10
    "before": {"INV_X1_min_sep_um": 0.0375, "NAND2_X1_min_sep_um": 0.0175,
               "pin_h_nm": (65, 75)},
    "after": {"INV_X1_min_sep_um": 0.435, "NAND2_X1_min_sep_um": 0.360,
              #: NOR2：A↔B 同带 x 差 0.60 · A↔Y 同 x 纵向差 0.370 · B↔Y 两维都远
              "NOR2_X1_min_sep_um": 0.370},
}

# ---- 方块电阻（Ω/□ · 教科书量级 · 一阶）----
RSH = {"poly": 8.0, "diff": 120.0, "m1": 0.10}
R_CONTACT = 6.0          # Ω / 个（单接触孔）

# ---- 单元行高与公共带（nm）----
#: 🔴 **pMOS sizing（v0.9.404）**：平衡反相器要求 `w_p/w_n = 1/μ`。
#: `MU_P_OVER_N` 是**教科书假设**（本仓无器件测量，与 `dkdrive.WL_MU` 同值）；
#: 一旦有实测 μ，改这一个数即可，几何与器件表都跟着走。
MU_P_OVER_N = 0.40
W_N = 300                                     # NMOS 沟道宽 = DIFF 高度（nm）
P_RATIO = 1.0 / MU_P_OVER_N                   # = 2.5
W_P = W_N * P_RATIO                           # = 750 nm

RAIL_H = 70              # 电源轨高度（M1）
Y_NDIFF = (180, 480)                     # NMOS 有源（W = 300）
Y_PDIFF = (700, 700 + int(round(W_P)))   # PMOS 有源（W = 750 —— 加宽后只能向上长）
Y_NWELL = (Y_PDIFF[0] - 80, Y_PDIFF[1] + 80)
#: INV 行高 = p-diff 顶 + nwell 余量 80 + 与轨间距 90 + 轨高 70 = **1690**
H_ROW = Y_PDIFF[1] + 80 + 90 + RAIL_H
Y_VSS = (0, RAIL_H)                      # VSS 轨
Y_VDD = (H_ROW - RAIL_H, H_ROW)          # VDD 轨
GAP = (Y_NDIFF[1], Y_PDIFF[0])           # 有源之间的间隙（放栅接触与局部互连）
#: 🔴 NAND2 的高度**不在这里写常量**：它由「gap 要塞 3 个 pin pad + p-diff 加宽到 750」
#: 现算得出（`build_nand2` 的 `y_vdd[1]`）。行高由 `dpnr.row_height_um()` 取各单元最大值。
#: 曾经想加一个 `H_ROW_NAND2 = 1950` 常量做「对齐」，但它是零引用的死声明 —— 删掉。


@dataclass(frozen=True)
class R:
    """版图矩形（nm · 整数 · 左下/右上）。"""
    layer: int
    x0: int
    y0: int
    x1: int
    y1: int
    net: str | None = None      # 仅 pin 用（网名标签）
    role: str = ""              # rail/strap/pad/cont/gate/pin/diff/nwell

    @property
    def w(self) -> int:
        return self.x1 - self.x0

    @property
    def h(self) -> int:
        return self.y1 - self.y0

    @property
    def area(self) -> int:
        return self.w * self.h

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2.0

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2.0


@dataclass
class Cell:
    """一颗标准单元：几何 + 期望器件表（LVS 的对照面）。"""
    name: str
    w: int
    h: int
    rects: list = field(default_factory=list)
    pins: dict = field(default_factory=dict)      # net -> R（网名标签）
    devices_expected: list = field(default_factory=list)   # [(kind, w, l, gate, sd_a, sd_b)]
    #: v0.9.358/E55：**网标签**（几何键 → 网名）。空 = 未标，DRC 退回几何连通性口径。
    #: 由 `label_cell()` 生成、`compose()` 迁移；这是「设计意图」这一侧的对照面。
    labels: dict = field(default_factory=dict)
    #: v0.9.358/E55：`compose()` 发现的**图形位置冲突**（同一几何键被两个不同网占用）。
    #: 🔴 为什么必须单独记：标签以**纯几何键**索引，两块图形若完全重合，键相同 ⇒ 后者覆盖
    #: 前者 ⇒ 两组标签塌成一个 ⇒ 「同网」⇒ DRC 静默放行。这是几何键的固有盲区，
    #: 只能由拼接器在**写入时**比对发现（实测：两颗 INV 完全叠放，DRC=0）。
    conflicts: list = field(default_factory=list)

    def by_layer(self, layer: int) -> list:
        return [r for r in self.rects if r.layer == layer]

    @property
    def area_um2(self) -> float:
        return self.w * self.h / 1e6


# ═══════════════════════════════════════════════════════════════════════════
# ① 单元构建
# ═══════════════════════════════════════════════════════════════════════════
def _rails(w: int, h: int | None = None) -> list:
    """两根电源轨。`h` 给定时 VDD 轨跟着单元高度走（v0.9.408 反事实面积用）。"""
    y_vdd = Y_VDD if h is None else (h - RAIL_H, h)
    return [R(L_M1, 0, Y_VSS[0], w, Y_VSS[1], role="rail"),
            R(L_M1, 0, y_vdd[0], w, y_vdd[1], role="rail")]


def _cont_box(cx: float, cy: float, size: int | None = None) -> tuple:
    """接触孔的**整数边界** `(x0, y0, x1, y1)`。

    🔴 派生 M1 时必须用它，不能自己写 `round(cy) ± k`：孔的 y0 是
    `int(round(cy − 22.5))`，而 `round(1227.5)=1228`、`round(1477.5)=1478`
    （偶数舍入）—— 手工补偿量在两组孔上**不相等**，实测导致 `cont_enc_m1`
    差 1nm（v0.9.408 首跑 2 条违例）。
    """
    s = size or RULES["cont_w"]
    x0, y0 = int(round(cx - s / 2.0)), int(round(cy - s / 2.0))
    return x0, y0, x0 + s, y0 + s


def _cont(cx: float, cy: float, size: int | None = None, role: str = "cont") -> R:
    x0, y0, x1, y1 = _cont_box(cx, cy, size)
    return R(L_CONT, x0, y0, x1, y1, role=role)


def build_inv(w_p_nm: int | None = None) -> Cell:
    """INV_X1：1 PMOS + 1 NMOS · 栅 A · 输出 Y（源漏各一接触孔）。

    `w_p_nm`（v0.9.408）：**反事实宽度**，只用于算「p 侧退回 1:1 后面积是多少」。
    默认 `None` ⇒ 用平衡宽度 `W_P`，几何与 v0.9.407 **逐位相同**（有判据守护）。

    布局（nm · x 向右 · y 向上）::

        y=1240 ┌────────────── VDD rail (M1) ──────────────┐
        1090   │                        ┌──── Y pin pad ──┐ │ ← 240×240，可落 VIA1
        1000   │             pfet diff  │   W=300         │ │ ← NWELL ±80 包住
         850   │                        └─────────────────┘ │
         700   │   [p_src]        ‖gate‖        [p_drn]     │
         650   │ ┌── A pin pad ──┐      ↑ gap：栅接触      │
         480   │ │               │      poly pad + M1      │
         410   │ └───────────────┘                          │
          70   ├────────────── VSS rail (M1) ──────────────┤
           0   └────────────────────────────────────────────┘

    🔴 **v0.9.349 引脚重画（E46）**：信号引脚从「65nm 高的窄条」改成 **240×240 的
    pin pad**，且 A（中心 y=0.535）与 Y（中心 y=0.970）纵向拉开 **0.435µm**。
    理由不是美观，是物理：路由器在引脚处要落 `VIA1(0.20) + 包围(0.02×2) = 0.24`
    的焊盘，相邻**不同网**焊盘之间还要 ≥`S_MIN(0.10)` ⇒ 两引脚接入点必须 ≥**0.342µm**。
    旧几何 A/Y 只差 0.0375µm（见 `PINS_V2_NOTE`），任何列分配策略都会让两个 M3
    焊盘叠在一起 —— 这就是 E45 那 14 条残差的来源。
    """
    w = 620
    wp = W_P if w_p_nm is None else int(w_p_nm)     # 反事实宽度（默认 = 平衡版 750）
    y_p1 = Y_PDIFF[0] + wp                          # p-diff 顶 = 700 + W_p
    h = y_p1 + 80 + 90 + RAIL_H                     # 与 H_ROW 同式 ⇒ wp=W_P 时恰为 1690
    rects = _rails(w, h)
    rects.append(R(L_NWELL, 30, Y_NWELL[0], 590, y_p1 + 80, role="nwell"))
    rects += [R(L_DIFF, 110, Y_NDIFF[0], 510, Y_NDIFF[1], role="diff"),
              R(L_DIFF, 110, Y_PDIFF[0], 510, y_p1, role="diff")]

    gx0, gx1 = 290, 340                       # 栅（L = 50）
    rects.append(R(L_POLY, gx0, Y_NDIFF[0] - 50, gx1, y_p1 + 50, role="gate"))
    # 栅接触处的 poly 焊盘：poly 条仅 50 宽，放不下 45 孔 + 15 包围 ⇒ 局部加宽（合法）
    rects.append(R(L_POLY, 225, 540, 335, 625, role="gate_pad"))

    rects += [_cont(182.5, 312.5, role="cont_sd"),     # NMOS 源 → VSS
              _cont(442.5, 312.5, role="cont_sd")]     # NMOS 漏 → Y
    # 🔴 v0.9.404 pMOS 加宽：W=750 ⇒ 每个源漏沿宽度**均布 2 个孔**。
    #   单个 45nm 孔去承担 750nm 的沟道宽，扩展电阻不可忽略，也不是真实做法。
    #   y 取 1/3·W 与 2/3·W（两端各留 250nm 给 `cont_enc_diff`）。
    for cy in (Y_PDIFF[0] + wp / 3.0, Y_PDIFF[0] + 2.0 * wp / 3.0):
        rects += [_cont(182.5, cy, role="cont_sd"), _cont(442.5, cy, role="cont_sd")]
    rects.append(_cont(267.5, 582.5, role="cont_gate"))   # 栅接触 → A

    m_y = R(L_M1, 410, 280, 475, y_p1 - 50, role="strap")   # Y：漏↔漏（延到新 p-diff 顶）
    rects += [R(L_M1, 150, Y_VSS[1], 215, 350, role="strap"),   # VSS → NMOS 源
              R(L_M1, 150, 740, 215, Y_VDD[0], role="strap"),   # VDD → PMOS 源
              m_y,
              # A：240×240 pin pad（x 中心 120 = 列网格点），另有 240–315 的连接条接栅接触
              R(L_M1, 0, 415, 240, 655, role="pin"),
              R(L_M1, 233, 550, 300, 620, role="strap"),           # A pad → 栅接触（留 75 余量给 Y pad）
              # Y：240×240 pin pad（中心 495 ⇒ 与 A 的 120 差 0.375µm）
              R(L_M1, 375, 850, 615, 1090, role="pin")]

    pins = {"VDD": R(L_M1, 0, h - RAIL_H, w, h, net="VDD"),
            "VSS": R(L_M1, 0, Y_VSS[0], w, Y_VSS[1], net="VSS"),
            "A": R(L_M1, 0, 415, 240, 655, net="A"),
            "Y": R(L_M1, 375, 850, 615, 1090, net="Y")}
    devs = [("pmos", wp, 50, "A", "VDD", "Y"),
            ("nmos", W_N, 50, "A", "VSS", "Y")]
    return Cell("INV_X1", w, h, rects, pins, devs)


def build_nand2(w_p_nm: int | None = None) -> Cell:
    """NAND2_X1：2 串 NMOS + 2 并 PMOS（4 器件）。

    `w_p_nm`：反事实宽度（见 `build_inv`），默认平衡版。

    拓扑（LVS 对照面）::

        PMOS（并联）:  Y —|A|— VDD —|B|— Y
        NMOS（串联）:  VSS —|A|— n1 —|B|— Y

    版图约束（为什么本单元比 INV 高）：
      · 两个输入焊垫都要在 gap 里放（poly 条只有 50 宽，放不下 45 孔 + 15 包围 ⇒ 需局部加宽），
        而 poly 焊盘之间必须 ≥ `poly_s=120`、焊盘与有源之间必须不重叠；
      · 并联 PMOS 的两个 Y 端（左/右）必须互连，而中间那段是 VDD ⇒ Y 的横向连接只能走
        gap 里的一条专用 M1 带（y 780–850），它上方还要放三个靠 0.36 分开的 pin pad。
      ⇒ gap 至少 60+70+60+60+70+60 = 380，故 PMOS 行下移到 y=1000、单元高 1500。
    """
    w = 980
    wp = W_P if w_p_nm is None else int(w_p_nm)
    y_pdiff = (1000, 1000 + wp)                  # pMOS 加宽：1000..1750（默认）
    y_nwell = (y_pdiff[0] - 80, y_pdiff[1] + 80)
    y_vdd = (y_pdiff[1] + 130, y_pdiff[1] + 200)  # 1880..1950
    rects = [R(L_M1, 0, Y_VSS[0], w, Y_VSS[1], role="rail"),
             R(L_M1, 0, y_vdd[0], w, y_vdd[1], role="rail"),
             R(L_NWELL, 30, y_nwell[0], 870, y_nwell[1], role="nwell"),
             R(L_DIFF, 110, Y_NDIFF[0], 790, Y_NDIFF[1], role="diff"),
             R(L_DIFF, 110, y_pdiff[0], 790, y_pdiff[1], role="diff")]

    # 两条栅（A / B）跨双有源；gap 内各自加宽成焊盘放接触孔
    rects += [R(L_POLY, 250, Y_NDIFF[0] - 50, 300, y_pdiff[1] + 10, role="gate"),
              R(L_POLY, 560, Y_NDIFF[0] - 50, 610, y_pdiff[1] + 10, role="gate"),
              R(L_POLY, 145, 545, 310, 660, role="gate_pad"),     # A 焊盘（含栅接触位）
              R(L_POLY, 505, 545, 615, 660, role="gate_pad")]     # B 焊盘

    # 源漏接触孔：NMOS 左=VSS / 右=Y；PMOS 左=Y / 中=VDD / 右=Y
    rects += [_cont(172.5, 312.5, role="cont_sd"),
              _cont(722.5, 312.5, role="cont_sd")]
    # 🔴 v0.9.404：pMOS 每个源漏沿 750nm 宽度均布 2 个孔（理由同 INV）
    for cy in (y_pdiff[0] + wp / 3.0, y_pdiff[0] + 2.0 * wp / 3.0):
        for cx in (172.5, 422.5, 722.5):
            rects.append(_cont(cx, cy, role="cont_sd"))
    rects += [_cont(260.0, 585.0, role="cont_gate"),
              _cont(565.0, 585.0, role="cont_gate")]

    # M1：电源引下 / 两输入 pin pad / 输出 pin pad / Y 三段（左竖 + gap 横 + 右竖）
    # 🔴 y 带分配（v0.9.349 重画后）：A/B 输入 pad 410–650 · Y pad 780–1020。
    #    输入 pad 高 240、中心 y=0.530 两两 x 间距 0.360（A 0–300 / B 390–630）；
    #    Y pad 下沉到 780–1020（中心 y=0.900），与输入中心纵向差 0.370 ⇒ 三引脚的
    #    M3 接入焊盘（0.242）两两间距 ≥0.10 全部成立（见 `PINS_V2_NOTE`）。
    m_y_r = R(L_M1, 690, 280, 755, y_pdiff[1] - 50, role="strap")
    rects += [R(L_M1, 140, Y_VSS[1], 205, 345, role="strap"),          # VSS
              R(L_M1, 390, 1055, 455, y_vdd[0], role="strap"),         # VDD
              R(L_M1, 0, 410, 240, 650, role="pin"),                   # A pin pad（x 中心 120）
              R(L_M1, 226, 550, 294, 620, role="strap"),               # A pad → 栅接触
              R(L_M1, 360, 410, 600, 650, role="pin"),                 # B pin pad（x 中心 480）
              m_y_r,
              R(L_M1, 720, 780, 960, 1020, role="pin"),                # Y pin pad（x 中心 840）
              R(L_M1, 140, 780, 205, y_pdiff[1] - 50, role="strap"),   # Y 接 PMOS 左端（左竖）
              R(L_M1, 140, 780, 755, 850, role="strap")]               # Y gap 横连

    pins = {"VDD": R(L_M1, 0, y_vdd[0], w, y_vdd[1], net="VDD"),
            "VSS": R(L_M1, 0, Y_VSS[0], w, Y_VSS[1], net="VSS"),
            "A": R(L_M1, 0, 410, 240, 650, net="A"),
            "B": R(L_M1, 360, 410, 600, 650, net="B"),
            "Y": R(L_M1, 720, 780, 960, 1020, net="Y")}
    devs = [("pmos", wp, 50, "A", "Y", "VDD"),
            ("pmos", wp, 50, "B", "VDD", "Y"),
            ("nmos", W_N, 50, "A", "VSS", "n1"),
            ("nmos", W_N, 50, "B", "n1", "Y")]
    return Cell("NAND2_X1", w, y_vdd[1], rects, pins, devs)


def build_nor2(w_p_nm: int | None = None) -> Cell:
    """NOR2_X1：2 串 PMOS + 2 并 NMOS（4 器件）—— NAND2 的**对偶**。

    拓扑（LVS 对照面）::

        PMOS（串联）:  Y —|A|— p1 —|B|— VDD
        NMOS（并联）:  VSS —|A|— Y —|B|— VSS

    🔴 **为什么这一版的 pad / 段分配与 NAND2 不同**（v0.9.408，实测逼出来的）：
    NAND2 的 Y 从**右端**引出（n 段 2 = Y），所以 Y pad 可以放在右侧 x=840，
    A/B pad 占左侧两格。NOR2 的 Y 在 **n 段 1（中间）** —— 并联结构的中间节点才是输出。
    若沿用 NAND2 的 pad 布局（A 120 / B 480 / Y 840），Y 的竖段（x≈422）必然穿过
    B pad（360–600 @410–650）⇒ 实测**直接短路**。三格 pad 宽 240 + 间距 60 = 840，
    在 980 宽的单元里只剩 140 余量，**放不下一条 65nm 宽的绕行竖条**。

    ⇒ 本版换分配：**A(0–240) 与 B(600–840) 同带（y 410–650），Y(0–240) 下沉到 780–1020**。
    Y 与 A 同 x 但纵向差 370nm（≥ 需要的 0.342），且 Y 的 p 侧引出点（x=172.5）正好在
    Y pad 正上方 ⇒ **零绕行**；n 段的 Y（x=422.5）向上走 x 390–455、在 y 780–845
    横折到 x=205 与 pad 相接 —— 这条路整段避开 A/B pad 的 x 区间。

    🔴 **尺寸与 NAND2 完全相同（980×1950）**：这不是巧合，是**刻意约束** ——
    `dpnr.row_height_um()` / `CELL_W_UM` 取 `CL.CELLS` 的最大值，新单元一旦超出，
    主链（c17 的 9 个固定口径数字）全部作废。NOR2 落在包络内 ⇒ 主链逐位不动。
    """
    w = 980
    wp = W_P if w_p_nm is None else int(w_p_nm)
    y_pdiff = (1000, 1000 + wp)
    y_nwell = (y_pdiff[0] - 80, y_pdiff[1] + 80)
    y_vdd = (y_pdiff[1] + 130, y_pdiff[1] + 200)
    rects = [R(L_M1, 0, Y_VSS[0], w, Y_VSS[1], role="rail"),
             R(L_M1, 0, y_vdd[0], w, y_vdd[1], role="rail"),
             R(L_NWELL, 30, y_nwell[0], 870, y_nwell[1], role="nwell"),
             R(L_DIFF, 110, Y_NDIFF[0], 790, Y_NDIFF[1], role="diff"),
             R(L_DIFF, 110, y_pdiff[0], 790, y_pdiff[1], role="diff")]

    # 两条栅跨双有源。B 的焊盘只向左伸到 527（更左就会与 Y 的绕行竖条只剩 <60 间距）
    rects += [R(L_POLY, 250, Y_NDIFF[0] - 50, 300, y_pdiff[1] + 10, role="gate"),
              R(L_POLY, 560, Y_NDIFF[0] - 50, 610, y_pdiff[1] + 10, role="gate"),
              R(L_POLY, 145, 545, 310, 660, role="gate_pad"),
              R(L_POLY, 527, 545, 615, 660, role="gate_pad")]

    # NMOS 并联：段0=VSS · 段1=Y · 段2=VSS（A、B 的源都接 VSS，漏都接 Y）
    rects += [_cont(172.5, 312.5, role="cont_sd"),
              _cont(422.5, 312.5, role="cont_sd"),
              _cont(722.5, 312.5, role="cont_sd")]
    # PMOS 串联：段0=Y · 段1=p1 · 段2=VDD（A: Y→p1，B: p1→VDD）
    _cy1 = y_pdiff[0] + wp / 3.0
    _cy2 = y_pdiff[0] + 2.0 * wp / 3.0
    for cy in (_cy1, _cy2):
        for cx in (172.5, 422.5, 722.5):
            rects.append(_cont(cx, cy, role="cont_sd"))
    rects += [_cont(260.0, 585.0, role="cont_gate"),
              _cont(565.0, 585.0, role="cont_gate")]

    # 两个 p 孔的**实际整数边界** —— M1 由它派生（见 `_cont_box` 的取整说明）
    _pa = _cont_box(422.5, _cy1)[1]          # 上孔 y0
    _pb = _cont_box(422.5, _cy2)[3]          # 下孔 y1
    # M1。y 带：输入 pad 410–650 · Y pad 780–1020（与 NAND2 的「纵向差 0.37」同口径）
    rects += [R(L_M1, 140, Y_VSS[1], 205, 345, role="strap"),        # VSS → n 段0
              R(L_M1, 690, Y_VSS[1], 755, 345, role="strap"),        # VSS → n 段2
              R(L_M1, 690, _pa - 10, 755, y_vdd[0], role="strap"),   # VDD → p 段2
              # p1（内部节点）：一块 M1 同时盖住两个孔，上下各留 10 给 `cont_enc_m1`
              R(L_M1, 390, _pa - 10, 455, _pb + 10, role="strap"),
              # Y：p 段0（左）→ Y pad（同一 x ⇒ 直下）
              R(L_M1, 140, 1020, 205, _pb + 10, role="strap"),
              R(L_M1, 390, 280, 455, 780, role="strap"),             # Y：n 段1 上行
              R(L_M1, 205, 780, 455, 845, role="strap"),             # Y 横带 → 左接 pad
              R(L_M1, 0, 410, 240, 650, role="pin"),                 # A pad（x 中心 120）
              R(L_M1, 226, 550, 294, 620, role="strap"),             # A pad → 栅接触
              R(L_M1, 600, 410, 840, 650, role="pin"),               # B pad（x 中心 720）
              R(L_M1, 530, 550, 640, 620, role="strap"),             # B pad → 栅接触
              R(L_M1, 0, 780, 240, 1020, role="pin")]                # Y pad（x 中心 120）

    pins = {"VDD": R(L_M1, 0, y_vdd[0], w, y_vdd[1], net="VDD"),
            "VSS": R(L_M1, 0, Y_VSS[0], w, Y_VSS[1], net="VSS"),
            "A": R(L_M1, 0, 410, 240, 650, net="A"),
            "B": R(L_M1, 600, 410, 840, 650, net="B"),
            "Y": R(L_M1, 0, 780, 240, 1020, net="Y")}
    devs = [("pmos", wp, 50, "A", "Y", "p1"),
            ("pmos", wp, 50, "B", "p1", "VDD"),
            ("nmos", W_N, 50, "A", "VSS", "Y"),
            ("nmos", W_N, 50, "B", "Y", "VSS")]
    return Cell("NOR2_X1", w, y_vdd[1], rects, pins, devs)


CELLS = {"INV_X1": build_inv, "NAND2_X1": build_nand2, "NOR2_X1": build_nor2}


def cell_area_um2_at(kind: str, w_p_nm: int | None = None) -> float:
    """单元面积（µm²）；`w_p_nm` 给定时算**反事实**版（p 侧退回该宽度）。

    🔴 走**真几何**：真的调 `CELLS[kind](w_p_nm=...)` 重建单元再取 `area_um2`，
    不用「高度 ≈ 常数 + W_p」外推。理由：外推虽然对当前三个单元都成立，但那是一条
    **未机核的断言**；重建还能顺手跑 DRC/LVS（v0.9.408 判据两条都做）。

    用途只有一个：把「面积代价」与「延时收益」放进同一个分母（见 `dsta.sizing_tradeoff`）。
    """
    return CELLS[kind](w_p_nm=w_p_nm).area_um2


# ═══════════════════════════════════════════════════════════════════════════
# ② 连通性引擎（DIFF 被 POLY 切段 + 同层相接合并 + 接触孔跨层）
# ═══════════════════════════════════════════════════════════════════════════
def _touch(a: R, b: R, tol: int = 0) -> bool:
    """同层/异层矩形是否相接或重叠（含边贴边）。"""
    return (a.x0 <= b.x1 + tol and b.x0 <= a.x1 + tol
            and a.y0 <= b.y1 + tol and b.y0 <= a.y1 + tol)


def _split_by_gate(a: "R", b: "R", polys: list) -> bool:
    """两段 DIFF 是否「同一有源行、被栅**完全覆盖**的间隙切开」—— 物理判据，不看 role 字符串。

    🔴 为什么必须换掉字符串判据（v0.9.358/E55）：旧版跳过条件 `a.role == b.role`，
    而 `diff_seg` 的 role 只写 y 区间、**不写父有源**，因此拼接后来自**不同实例**的两段
    必然同名 ⇒ 跨单元异网有源相接被当成「同一行被栅切开」而静默跳过（实测两个 INV
    贴合放置，DRC=0 但其实是真短路）。
    正解不是往 role 里塞更多字符串（那就成了「靠命名约定保证正确性」），而是直接问几何：
    **这两段之间那块间隙上，有没有栅盖住？** 有 ⇒ 是沟道两侧的源漏，本就不适用间距规则；
    没有 ⇒ 两段有源是裸露相邻，必须查间距。
    """
    if a.y0 != b.y0 or a.y1 != b.y1:
        return False
    lo, hi = (a.x1, b.x0) if a.x1 <= b.x0 else (b.x1, a.x0)
    if hi <= lo:
        return False                     # 重叠或贴合：不是「被切开」，要照常查间距
    return any(p.x0 <= lo and p.x1 >= hi and p.y0 <= a.y0 and p.y1 >= a.y1
               for p in polys)


def diff_segments(cell: Cell) -> list:
    """把每块 DIFF 按覆盖它的 POLY（栅）在 x 上切开，返回各段矩形。

    🔴 **必须切开**：栅下那一段是**沟道**，不是导体。不切会把源漏短成一个网，
       进而把 VDD/VSS/Y 全并成同一个节点（本模块首版就是这么错的）。
    """
    out: list = []
    gates = cell.by_layer(L_POLY)
    for d in cell.by_layer(L_DIFF):
        cuts = sorted({(g.x0, g.x1) for g in gates
                       if _touch(g, d) and min(g.y1, d.y1) > max(g.y0, d.y0)})
        spans = [(d.x0, d.x1)]
        for cx0, cx1 in cuts:
            nxt = []
            for (sx0, sx1) in spans:
                if cx1 <= sx0 or cx0 >= sx1:
                    nxt.append((sx0, sx1))
                    continue
                if cx0 > sx0:
                    nxt.append((sx0, cx0))
                if cx1 < sx1:
                    nxt.append((cx1, sx1))
            spans = nxt
        for (sx0, sx1) in spans:
            # 🔴 role 里带上**父有源的行号**：同一行被栅切开的各段之间不适用
            #    「同层最小间距」（它们本来就只隔一个栅长），跨行才适用。
            out.append(R(L_DIFF, sx0, d.y0, sx1, d.y1,
                         role="diff_seg@%d-%d" % (d.y0, d.y1)))
    return out


def _shapes(cell: Cell) -> list:
    """连通性用的形状表：DIFF 换成段，其余原样保留。"""
    return [r for r in cell.rects if r.layer != L_DIFF] + diff_segments(cell)


def _uf(n: int) -> list:
    return list(range(n))


def _find(p: list, i: int) -> int:
    while p[i] != i:
        p[i] = p[p[i]]
        i = p[i]
    return i


def _union(p: list, i: int, j: int) -> None:
    ri, rj = _find(p, i), _find(p, j)
    if ri != rj:
        p[ri] = rj


#: 单元内的跨层桥接：通孔层 → 它能连通的金属/扩散层。
#: 🔴 与 `ddrc_lvs.VIA_BRIDGE` 是**同一个物理事实**的两种用途（这里判连通，那里判包围），
#: 两边都必须改才自洽 —— 由 E54 判据 `J3` 机核两张表逐项一致。
_VIA_BRIDGE = {
    L_CONT: (L_DIFF, L_POLY, L_M1),
    L_VIA1: (L_M1, L_M2),
    L_V2: (L_M2, L_M3),
    #: v0.9.358/E55：布线器的 M3↔M4 通孔与 M4（真源层号）。缺这两项 ⇒ 联合场景里
    #: 走线被切成多个分量，「同网多片段」数量会假性暴涨（实测 7 → 56）。
    L_VIA2: (L_M3, L_M4),
}


def _groups(shapes: list) -> list:
    n = len(shapes)
    p = _uf(n)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = shapes[i], shapes[j]
            if a.layer == b.layer and _touch(a, b):
                _union(p, i, j)
    # 跨层桥接：接触孔连「它压在的东西」，通孔连「它桥接的两层」。
    # 🔴 v0.9.357（E54）：原先只硬编码了 CONT ⇒ 单元里一放 M2/M3 走线，
    # 连通性就断（LVS 会看到「PMOS 漏和 NMOS 漏不是一个网」）。这里改成**表驱动**：
    # 每类通孔声明它能桥接哪些层，和 `ddrc_lvs.VIA_BRIDGE` 是同一个物理事实的两种用途。
    for k, c in enumerate(shapes):
        bridges = _VIA_BRIDGE.get(c.layer)
        if bridges is None:
            continue
        for i, s in enumerate(shapes):
            if s.layer in bridges and _touch(c, s):
                _union(p, k, i)
    g: dict = {}
    for i in range(n):
        g.setdefault(_find(p, i), []).append(i)
    return list(g.values())


def connectivity(cell: Cell) -> dict:
    """返回 {shapes, groups, node_of(shape_idx), net_of(shape_idx)}。"""
    shapes = _shapes(cell)
    groups = _groups(shapes)
    node_of: dict = {}
    for gi, grp in enumerate(groups):
        for i in grp:
            node_of[i] = gi
    # 网名：pin 落在哪个节点上
    net_of: dict = {}
    net_of_group: dict = {}
    for n, grp in enumerate(groups):
        name = None
        for i in grp:
            for net, pr in cell.pins.items():
                s = shapes[i]
                if s.layer == pr.layer and _touch(s, pr):
                    name = net
                    break
            if name:
                break
        if name:
            net_of_group[n] = name
            for i in grp:
                net_of[i] = name
    return {"shapes": shapes, "groups": groups, "node_of": node_of,
            "net_of": net_of, "net_of_group": net_of_group}


# ═══════════════════════════════════════════════════════════════════════════
# ②b 网标签（E55）—— 把「设计意图」变成可机核的一等公民
# ═══════════════════════════════════════════════════════════════════════════
#: 跨实例**直接相连**的网（电源/地）。拼接时不加实例前缀 —— 它们本来就是同一根轨。
GLOBAL_NETS = ("VDD", "VSS")

#: **非信号层**：工艺岛/标记层，不是互连。拼接时相邻合法，不参与短路判定。
#: 🔴 NWELL 是其中最容易被误判的一个（E55 实测）：两颗单元贴合，两块 NWELL 正好接上，
#: 几何上并成一个节点、标签却是两个无名网 ⇒ 被 `bridges` 当成跨实例短路（假红）。
#: 真实版图里 NWELL 本来就是可以连成一片的工艺岛，所以它必须**同标签且不参与网比对**。
NON_SIGNAL_LAYERS = (L_NWELL,)
_NON_SIGNAL_NAME = "NWELL"


def _geom_key(r) -> tuple:
    """几何键（层 + 四边）—— 网标签以它索引，**纯平移即可迁移**，不依赖对象身份。"""
    return (r.layer, r.x0, r.y0, r.x1, r.y1)


def _qualify(name, prefix, global_nets=GLOBAL_NETS):
    """给非全局网加实例前缀。已带前缀的幂等（可重复调用）。"""
    if not prefix or name in global_nets or name.startswith(prefix + "/"):
        return name
    return "%s/%s" % (prefix, name)


def label_cell(cell: Cell, prefix: str = None,
               global_nets=GLOBAL_NETS, pin_names: dict = None) -> dict:
    """**几何键 → 网标签**（`{_geom_key: name}`）。

    规则只有两条，且都可机核：
      · 连通分量上有引脚落入 ⇒ 用**引脚网名**（真名，唯一真源是 `cell.pins`）；
      · 没有 ⇒ 无名内部节点，按 `(层, y0, x0)` **稳定排序**编号 `#1, #2, …`。

    🔴 为什么要它（E55 的核心）：在此之前「哪块图形属于哪个网」只存在于
    **几何连通性**里 —— 而连通性是**结果**，不是**意图**。单元一旦拼接，两条本不该
    相接的走线若真的搭上，几何会「正确地把它们并成一个网」，于是 DRC 的
    「同网跳过间距」判据把**短路当成同网**放行。标签把意图单独记一份，两者不一致
    就是缺陷 ⇒ 短路必报（见 `run_drc(labels=)` 的 docstring）。

    🔴 `prefix` 的作用不是美化：两个 INV 实例各有 `A`/`Y`，拼接后若不加前缀，
    调用方会把它们误当同一网 ⇒ 假「同网」⇒ 又回到静默放行。全局网（VDD/VSS）例外。

    🔴 `pin_names`（v0.9.358/E55 追加）：**电路网名**映射 `{引脚名: 网表网名}`。
    真实装配时「u0.Y 与 u1.A 是同一个网」是**电路事实**，此时标签必须用网表网名、
    且**不加实例前缀**（网表网名本来就全局唯一）。不给 `pin_names` 时保持
    「一实例一前缀」的保守语义 —— 那种语义下两个实例的引脚**永远不同网**，
    只适合「检查单个/并排摆放是否打架」，不适合「判断真实网表连得对不对」。
    """
    cx = connectivity(cell)
    shapes, groups = cx["shapes"], cx["groups"]
    named = dict(cx["net_of_group"])            # group_idx -> 真名
    anon = [gi for gi in range(len(groups)) if gi not in named]

    def _min_key(gi):
        return min((s.layer, s.y0, s.x0) for s in (shapes[i] for i in groups[gi]))

    anon.sort(key=_min_key)                     # 编号只依赖几何，与遍历顺序无关
    name_of = dict(named)
    for k, gi in enumerate(anon):
        name_of[gi] = "#%d" % (k + 1)

    out: dict = {}
    for gi, grp in enumerate(groups):
        raw = name_of[gi]
        if pin_names and raw in pin_names:
            nm = pin_names[raw]                 # 电路网名：全局唯一，不加实例前缀
        else:
            nm = _qualify(raw, prefix, global_nets)
        for i in grp:
            s = shapes[i]
            # 非信号层统一标成固定名（相邻合法、且不参与网比对，见 NON_SIGNAL_LAYERS）
            out[_geom_key(s)] = (_NON_SIGNAL_NAME if s.layer in NON_SIGNAL_LAYERS else nm)
    return out


def compose(tiles: list, name: str = "COMPOSED",
            global_nets=GLOBAL_NETS) -> Cell:
    """把多个单元实例拼成**一个 Cell** —— 于是联合场景也走同一份 `run_drc`/`extract_devices`。

    `tiles = [(cell, dx, dy, prefix), …]`，`dx/dy` 为 **nm 整数**（与单元几何同单位）。

    🔴 为什么不新写一个「多单元 DRC」（E55 的架构决定）：单元内、单元间、单元↔走线
    的检查规则**完全一样**（同层宽/距、孔包围、NWELL 包住）。造第二套检查器必然与第一套
    漂移 —— 本仓已踩过（E53 的 `run_drc(rules=)`、E54 的 `_VIA_BRIDGE` 表驱动都是同一
    教训）。**拼接成一个大 Cell** 就能让现有实现原样覆盖联合场景，新增代码只有「平移 + 标签迁移」。

    器件表按 tile 顺序累加、网名加前缀；`run_lvs_pos` 的排序键是**全局沟道 x**，
    因此 `tiles` 必须**按 x 升序**给出（判据 E55-K3 机核：走查器 vs 声明表的 kind 序列逐项相等）。
    """
    if not tiles:
        raise ValueError("compose 需要至少一个 tile")
    rects: list = []
    pins: dict = {}
    devs: list = []
    labels: dict = {}
    conflicts: list = []
    x1 = y1 = 0
    seen_pins: dict = {}
    for tile in tiles:
        # tile = (cell, dx, dy, prefix) 或 (cell, dx, dy, prefix, pin_names)
        if len(tile) == 4:
            cell, dx, dy, prefix = tile
            pin_names = None
        else:
            cell, dx, dy, prefix, pin_names = tile
        dx, dy = int(dx), int(dy)
        for r in cell.rects:
            rects.append(R(r.layer, r.x0 + dx, r.y0 + dy, r.x1 + dx, r.y1 + dy,
                           net=r.net, role=r.role))
        x1 = max(x1, cell.w + dx)
        y1 = max(y1, cell.h + dy)

        def _name(pn):
            """网名定名规则（**唯一**一处）：电路网名 > 全局网 > 实例前缀。"""
            if pin_names and pn in pin_names:
                return pin_names[pn]        # 电路网名：全局唯一，不再加实例前缀
            return _qualify(pn, prefix, global_nets)

        # 🔴 自带标签优先（E55）：走线 Cell 的网名不是「从几何推出来的」，而是**外部给定**的
        # 事实（哪条线属于哪一网）。若这里无条件重算 `label_cell`，走线网名会被重新编号成
        # `rt/#1`，与布线的网名全部失配 ⇒ 同网接触被误报成短路。
        if cell.labels:
            raw = {k: _qualify(v, prefix, global_nets) for k, v in cell.labels.items()}
        else:
            raw = label_cell(cell, prefix=prefix, global_nets=global_nets,
                             pin_names=pin_names)
        for k, v in raw.items():
            key = (k[0], k[1] + dx, k[2] + dy, k[3] + dx, k[4] + dy)
            old = labels.get(key)
            if old is not None and old != v:
                conflicts.append(("shape_conflict",
                                  "L%d@(%d,%d)-(%d,%d): %s vs %s"
                                  % (key[0], key[1], key[2], key[3], key[4], old, v)))
            labels[key] = v
        for pn, pr in cell.pins.items():
            key = _name(pn)
            if key in seen_pins:
                # 🔴 三种情形必须分开（E55）：
                #   · 全局网（VDD/VSS）：每颗单元都有这两根轨，重复是**必然**的 ⇒ 跳过；
                #   · 有 `pin_names`（真实网表装配）：同一网连多个引脚本来就是对的
                #     （u0.Y 与 u1.A 同属 n3）⇒ 必须允许；`pins` 只保留一个代表矩形，
                #     因为它的用途是「网名集合 + 命中判定」，不是「引脚清单」；
                #   · 无 `pin_names`（并排摆放）：同名非全局网出现在两个实例里 = 前缀缺失，
                #     那是调用方的错，不能静默合并 ⇒ 抛错。
                if key in global_nets or pin_names:
                    continue
                raise ValueError("实例引脚网名冲突：%r（请给唯一 prefix 或 pin_names）" % key)
            seen_pins[key] = 1
            pins[key] = R(pr.layer, pr.x0 + dx, pr.y0 + dy,
                          pr.x1 + dx, pr.y1 + dy, net=key, role=pr.role)
        for (kind, w, l, gate, a, b) in cell.devices_expected:
            devs.append((kind, w, l,
                         _name(gate) if gate else gate,
                         _name(a) if a else a,
                         _name(b) if b else b))
    return Cell(name=name, w=x1, h=y1, rects=rects, pins=pins,
                devices_expected=devs, labels=labels, conflicts=conflicts)


def label_report(cell: Cell, global_nets=GLOBAL_NETS,
                 allow_multi_fragment: bool = False) -> dict:
    """机核「标签 ⇔ 几何连通性」一致性 —— 两者互为对照面，不一致就是缺陷。

    返回 {groups, named, anon, mismatches, n, unrouted}：
      · `split` = 同一连通分量被标成两个网（意图说分开、实际连着 ⇒ **短路**）；
      · `merge` = **同一实例内**两个不同分量被标成同一网（意图说连着、实际断开 ⇒ **开路**）。

    🔴 `allow_multi_fragment`（v0.9.358/E55）：真实网表装配时必须开。
    因为「`u0.Y` 与 `u1.A` 同属网 n3、几何上还没连」**不是缺陷，是待布线的网** ——
    把它判成开路会让任何多单元场景恒红。开启后这些分量计入 `unrouted`（信息性），
    只有**同一个实例内部**被拆开的网仍算 `merge`。

    另有两处刻意豁免，都是物理事实而不是放水：
      · **全局网**（VDD/VSS）允许同名的多个几何片段 —— 单元电源轨本来就靠**上层金属/共用
        轨**连起来，本模块只画 M1..M3 的单元内部，不画那条上层连接。
      · **非信号层**（NWELL 工艺岛）不参与网比对，见 `NON_SIGNAL_LAYERS`。
    """
    lab = cell.labels or label_cell(cell)
    cx = connectivity(cell)
    shapes, groups = cx["shapes"], cx["groups"]
    gnet: dict = {}
    net_g: dict = {}
    mism: list = []
    unrouted: list = []

    def _signal(grp):
        """该组里有**信号层**图形才参与网比对；纯工艺岛（NWELL）跳过。"""
        return any(shapes[i].layer not in NON_SIGNAL_LAYERS for i in grp)

    for gi, grp in enumerate(groups):
        if not _signal(grp):
            continue
        names = {lab.get(_geom_key(shapes[i])) for i in grp
                 if shapes[i].layer not in NON_SIGNAL_LAYERS}
        names.discard(None)
        if len(names) > 1:
            mism.append(("split", "group#%d: %s" % (gi, sorted(names))))
        if len(names) == 1:
            nm = names.pop()
            if nm in global_nets:
                gnet[gi] = nm
                continue            # 电源轨跨实例可多片段（靠上层金属连，模块不画）
            if nm in net_g and net_g[nm] != gi:
                prev = net_g[nm]
                if allow_multi_fragment:
                    unrouted.append((nm, prev, gi))     # 待布线的网（信息性，非缺陷）
                else:
                    mism.append(("merge", "%s: group#%d vs group#%d" % (nm, prev, gi)))
            net_g[nm] = gi
            gnet[gi] = nm
    n_named = sum(1 for v in lab.values() if not str(v).startswith("#")
                  and "/#" not in str(v) and v != _NON_SIGNAL_NAME)
    return {"groups": len(groups), "named": n_named,
            "anon": len(lab) - n_named, "mismatches": mism, "n": len(mism),
            "unrouted": unrouted, "n_unrouted": len(unrouted),
            "labels": len(lab), "net_of_group": gnet}


def bridges(cell: Cell, tiles: list, global_nets=GLOBAL_NETS) -> list:
    """跨实例**意外桥接**：合成后某个连通分量同时含有**两个不同实例**的非全局图形。

    合法情形只有一种：两者标签相同（确实是同一根网被连上，例如 VDD 轨对接）。
    其余一律是短路 —— 这条判据补上了「拼接后 DRC 看不到单元间短路」的最后一个口子。
    """
    lab = cell.labels or label_cell(cell)
    cx = connectivity(cell)
    shapes, groups = cx["shapes"], cx["groups"]
    origin: dict = {}          # 几何键 -> prefix
    for tile in tiles:
        c, dx, dy, prefix = tile[0], tile[1], tile[2], tile[3]
        dx, dy = int(dx), int(dy)
        for r in c.rects:
            origin[(r.layer, r.x0 + dx, r.y0 + dy, r.x1 + dx, r.y1 + dy)] = prefix
        for s in diff_segments(c):
            origin[(s.layer, s.x0 + dx, s.y0 + dy, s.x1 + dx, s.y1 + dy)] = prefix
    out: list = []
    for gi, grp in enumerate(groups):
        who: dict = {}
        for i in grp:
            s = shapes[i]
            if s.layer in NON_SIGNAL_LAYERS:
                continue
            k = _geom_key(s)
            p = origin.get(k)
            if p is None:
                continue
            who.setdefault(p, set()).add(lab.get(k))
        if len(who) < 2:
            continue
        allnames = set()
        for v in who.values():
            allnames |= v
        allnames.discard(None)
        if len(allnames) > 1:
            out.append(("cross_instance", "group#%d: %s"
                        % (gi, sorted((p, sorted(v)) for p, v in who.items()))))
    return out


# ═══════════════════════════════════════════════════════════════════════════
# ③ 器件抽取（几何求交）
# ═══════════════════════════════════════════════════════════════════════════
def extract_devices(cell: Cell) -> list:
    """POLY∩DIFF = 沟道：W = 交叠高度，L = 交叠宽度；源漏 = 被切开后左右相邻的段。

    PMOS/NMOS 由「沟道是否被 NWELL 完全包住」判定。
    """
    cx = connectivity(cell)
    shapes, node_of = cx["shapes"], cx["node_of"]
    segs = [i for i, s in enumerate(shapes) if s.role.startswith("diff_seg")]
    wells = cell.by_layer(L_NWELL)
    devs = []
    for g in cell.by_layer(L_POLY):
        for d in cell.by_layer(L_DIFF):
            if not _touch(g, d):
                continue
            ox0, ox1 = max(g.x0, d.x0), min(g.x1, d.x1)
            oy0, oy1 = max(g.y0, d.y0), min(g.y1, d.y1)
            if ox1 <= ox0 or oy1 <= oy0:
                continue
            inside = any(wl.x0 <= ox0 and wl.x1 >= ox1
                         and wl.y0 <= oy0 and wl.y1 >= oy1 for wl in wells)
            sd = []
            for i in segs:
                s = shapes[i]
                if s.y0 != d.y0 or s.y1 != d.y1:
                    continue
                if s.x1 == ox0 or s.x0 == ox1:      # 紧邻栅两侧的那一段
                    sd.append(node_of.get(i))
            gate_node = None
            for i, s in enumerate(shapes):
                if s.layer == L_POLY and _touch(s, g) and s.x0 == g.x0 and s.x1 == g.x1:
                    gate_node = node_of.get(i)
                    break
            # `x`/`y`：沟道左下角（v0.9.357 新增，供**几何排序**用）。
            # 🔴 不能拿「栅网的 x」当排序键 —— 同一个网可能驱动多列（如 ckb 同时驱动
            # INV_CK2 与 TG1 的 N 栅），取 min 会把不同列压成同一个键。
            devs.append({"kind": "pmos" if inside else "nmos", "w": oy1 - oy0,
                         "l": ox1 - ox0, "gate": gate_node, "sd": sd,
                         "x": ox0, "y": oy0})
    return devs


# ═══════════════════════════════════════════════════════════════════════════
# ④ DRC（显式规则集 · 逐层 width/space/area + 接触孔包围 + 栅-孔间距）
# ═══════════════════════════════════════════════════════════════════════════
def run_drc(cell: Cell, rules: dict = None, labels: dict = None) -> dict:
    """返回 {violations: [(规则, 明细)], n}。

    🔴 `rules`（v0.9.356）：规则集参数，默认 `RULES`（LDA-DEMO45）。
    这是「可复用/可扩展」的关键 —— **同一份 DRC 实现**可以查不同节点的单元，
    不必为 HD 库再写一套检查器（两份真源 = 必然漂移）。

    🔴 `labels`（v0.9.358/E55）：**网标签**（几何键 → 网名，见 `label_cell`）。
    给定时，同层间距的「同网跳过」判据从「几何连通分量相同」改成「**标签相同**」。
    两处差别就是 E55 要消灭的盲区：

      · 旧口径：两块金属只要在几何上被并进同一连通分量，就当作同网 ⇒ 间距不查。
        单元拼接后，若两条**本不该相接**的走线真的搭在一起，几何上**恰好并成一个分量**
        ⇒ 「短路」反而成了「同网」，DRC 静默放行。
      · 新口径：标签来自**设计意图**（谁该连谁），几何来自**实际图形**。两者矛盾时
        「标签不同 ⇒ 必须按异网查间距」⇒ 短路必报。这是「同一事实写两次必须机核」的
        构造函数化用法：标签与几何**互为对照**，不一致就是缺陷，不是豁免。

    未给 `labels` 时行为与旧版**逐位相同**（向后兼容，E40–E54 的门禁不受影响）。
    """
    R = RULES if rules is None else rules
    # 标签优先级：显式参数 > 单元自带 > 空（退回旧口径）
    _labels = labels if labels is not None else (getattr(cell, "labels", None) or {})
    # 拼接器在写入时发现的图形位置冲突（几何键相同 ⇒ 标签会塌成一个）必须先报
    v: list = list(getattr(cell, "conflicts", None) or [])
    cx = connectivity(cell)
    shapes, node_of = cx["shapes"], cx["node_of"]
    # 以「原始图形」查 width/area（段是派生量，不参与）
    wmin = {L_DIFF: R["diff_w"], L_POLY: R["poly_w"], L_CONT: R["cont_w"],
            L_M1: R["m1_w"], L_M2: R.get("m2_w", R["m1_w"]),
            L_M3: R.get("m3_w", R["m1_w"]),
            # M4 只在联合场景出现（单元内部不用 M4）⇒ 规则缺省回退到 M3，不新造规则键
            L_M4: R.get("m4_w", R.get("m3_w", R["m1_w"]))}
    amin = {L_DIFF: R["diff_a"], L_POLY: R["poly_a"], L_CONT: 0,
            L_M1: R["m1_a"], L_M2: R.get("m2_a", R["m1_a"]),
            L_M3: R.get("m3_a", R["m1_a"]),
            L_M4: R.get("m4_a", R.get("m3_a", R["m1_a"]))}
    for r in cell.rects:
        if r.layer in wmin:
            if min(r.w, r.h) < wmin[r.layer]:
                v.append(("min_width", "%s L%d w=%d h=%d" % (r.role, r.layer, r.w, r.h)))
            if amin[r.layer] and r.area < amin[r.layer]:
                v.append(("min_area", "%s L%d a=%d" % (r.role, r.layer, r.area)))

    # 同层 space：只在**不同网**之间查（同网重叠/相接不算违规）。
    # E55：判「同网」优先用标签（设计意图），无标签才退回几何连通分量（旧口径）。
    idx = {id(s): i for i, s in enumerate(shapes)}
    smin = {L_DIFF: R["diff_s"], L_POLY: R["poly_s"], L_M1: R["m1_s"],
            L_M2: R.get("m2_s", R["m1_s"]), L_M3: R.get("m3_s", R["m1_s"]),
            L_M4: R.get("m4_s", R.get("m3_s", R["m1_s"]))}
    polys = [p for p in cell.by_layer(L_POLY)]
    for layer, s_rule in smin.items():
        rs = [s for s in shapes if s.layer == layer]
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                a, b = rs[i], rs[j]
                la, lb = _labels.get(_geom_key(a)), _labels.get(_geom_key(b))
                if la is not None and lb is not None:
                    same_net = (la == lb)
                else:
                    same_net = (node_of.get(idx[id(a)]) == node_of.get(idx[id(b)]))
                if same_net:
                    continue
                # 🔴 v0.9.358/E55：**同一有源行被栅切开的相邻段**不适用同层间距。
                # 旧版按 `role` 字符串相等判（`diff_seg@y0-y1`）—— 单单元内恰好等价，
                # 但**拼接后来自不同实例的两段 role 完全相同** ⇒ 跨单元的真短路被静默跳过
                # （E55 判据 K5 实测：两个 INV 贴合放，DIFF 异网相接却 DRC=0）。
                # 正解是**物理判据**：两段同 y 行且它们之间的间隙被**栅（POLY）完全覆盖**。
                if (a.role.startswith("diff_seg@") and b.role.startswith("diff_seg@")
                        and _split_by_gate(a, b, polys)):
                    continue
                dx = max(0, max(a.x0, b.x0) - min(a.x1, b.x1))
                dy = max(0, max(a.y0, b.y0) - min(a.y1, b.y1))
                gap = max(dx, dy)
                if gap < s_rule:
                    v.append(("min_space_L%d" % layer,
                              "%s/%s gap=%d < %d" % (a.role, b.role, gap, s_rule)))

    # 接触孔：包围只对它**真正压在**的层查（首版错在要求每个孔都有 poly 底）
    #   · 每个孔必须压在 DIFF 或 POLY 上（否则是「空中孔」= 无效接触）；
    #   · 压在谁上面，就按那层的包围规则查；M1 包围对所有孔都查。
    for c in cell.by_layer(L_CONT):
        base_diff = [s for s in cell.by_layer(L_DIFF) if _touch(c, s)]
        base_poly = [s for s in cell.by_layer(L_POLY) if _touch(c, s)]
        if not base_diff and not base_poly:
            v.append(("cont_no_base", c.role))
            continue
        for bases, need, tag in ((base_diff, R["cont_enc_diff"], "diff"),
                                 (base_poly, R["cont_enc_poly"], "poly")):
            if not bases:
                continue
            best = max(bases, key=lambda s: min(c.x0 - s.x0, s.x1 - c.x1,
                                                c.y0 - s.y0, s.y1 - c.y1))
            enc = min(c.x0 - best.x0, best.x1 - c.x1, c.y0 - best.y0, best.y1 - c.y1)
            if enc < need:
                v.append(("cont_enc_" + tag, "%s enc=%d < %d" % (c.role, enc, need)))
        m1s = [s for s in cell.by_layer(L_M1) if _touch(c, s)]
        if not m1s:
            v.append(("cont_no_m1", c.role))
            continue
        best = max(m1s, key=lambda s: min(c.x0 - s.x0, s.x1 - c.x1,
                                          c.y0 - s.y0, s.y1 - c.y1))
        enc = min(c.x0 - best.x0, best.x1 - c.x1, c.y0 - best.y0, best.y1 - c.y1)
        if enc < R["cont_enc_m1"]:
            v.append(("cont_enc_m1", "%s enc=%d < %d" % (c.role, enc, R["cont_enc_m1"])))

    # 栅到有源上接触孔的间距（栅-孔间距是真实 DRC 规则，不能漏）
    for g in cell.by_layer(L_POLY):
        for d in cell.by_layer(L_DIFF):
            if not _touch(g, d):
                continue
            ox0, ox1 = max(g.x0, d.x0), min(g.x1, d.x1)
            if ox1 <= ox0:
                continue
            for c in cell.by_layer(L_CONT):
                if _touch(c, g) or not _touch(c, d):
                    continue
                dx = max(0, max(ox0, c.x0) - min(ox1, c.x1))
                if dx < R["gate_cont"]:
                    v.append(("gate_cont", "gate@%d-%d cont@%d gap=%d < %d"
                              % (ox0, ox1, c.x0, dx, R["gate_cont"])))

    # NWELL 包围 PMOS 有源
    wells = cell.by_layer(L_NWELL)
    for d in cell.by_layer(L_DIFF):
        inside = [w for w in wells if _touch(d, w)]
        if not inside:
            continue
        best = max(inside, key=lambda w: min(d.x0 - w.x0, w.x1 - d.x1,
                                             d.y0 - w.y0, w.y1 - d.y1))
        enc = min(d.x0 - best.x0, best.x1 - d.x1, d.y0 - best.y0, best.y1 - d.y1)
        if enc < R["nwell_enc"]:
            v.append(("nwell_enc", "diff@y%d-%d enc=%d < %d"
                      % (d.y0, d.y1, enc, R["nwell_enc"])))
    return {"violations": v, "n": len(v)}


# ═══════════════════════════════════════════════════════════════════════════
# ⑤ LVS（抽出器件表 vs 期望表 + 短路/悬空检查）
# ═══════════════════════════════════════════════════════════════════════════
def _canon(devs: list, pins, net_of_group: dict | None = None) -> list:
    """规范化：内部节点按**首次出现顺序**重命名，pin 网保留原名。

    这是标准 LVS 的「内部节点匹配」—— 不做则串联 NAND 的中间节点永远对不上。
    `got`（几何抽出）用**节点 id** 表示未命名节点，`exp`（期望表）用字符串网名；
    两者都走同一套别名分配，故只要结构同构，规范形必然逐项相等。
    """
    alias: dict = {}

    def nm(x):
        if net_of_group is not None and x is not None:
            name = net_of_group.get(x)
            if name is not None:
                return name
            key = ("node", x)
        else:
            if x is not None and x in pins:
                return x
            key = ("net", x)
        if key not in alias:
            alias[key] = "n%d" % (len(alias) + 1)
        return alias[key]

    out = []
    for d in sorted(devs, key=lambda y: (y["kind"], y["w"], y["l"], str(y["gate"]))):
        out.append((d["kind"], d["w"], d["l"], nm(d["gate"]),
                    tuple(sorted((nm(x) for x in d["sd"]), key=str))))
    return out


def run_lvs(cell: Cell) -> dict:
    cx = connectivity(cell)
    got = extract_devices(cell)
    exp = [{"kind": k, "w": w, "l": l, "gate": g, "sd": [a, b]}
           for (k, w, l, g, a, b) in cell.devices_expected]

    mism = []
    cg = _canon(got, cell.pins, cx["net_of_group"])
    ce = _canon(exp, cell.pins)
    if cg != ce:
        mism.append(("device_set", "got=%s exp=%s" % (cg, ce)))
    net_of = cx["net_of"]
    for grp in cx["groups"]:
        names = {net_of.get(i) for i in grp if net_of.get(i)}
        if len(names) > 1:
            mism.append(("short", "同一节点多网名：%s" % sorted(names)))
    known = set(net_of.values())
    for net in cell.pins:
        if net not in known:
            mism.append(("floating_pin", net))
    return {"devices": got, "mismatches": mism, "n": len(mism)}


# ═══════════════════════════════════════════════════════════════════════════
# ⑥ 寄生 R 提取（方块电阻逐段积分 · 一阶）
# ═══════════════════════════════════════════════════════════════════════════
def _seg_r(rsh: float, length: float, width: float) -> float:
    return rsh * length / width if width > 0 else float("inf")


def gate_r(reach_nm: float, w_poly_nm: int, l_nm: int) -> float:
    """栅电阻闭式：`Rsh_poly · reach / W_poly`（reach = 接触孔到沟道边缘的距离）。

    `l_nm` 只作一致性断言用（栅长变了 reach 会跟着变；此式不显含 L，是**一阶**
    口径的诚实交代：真实栅电阻还含分布效应，本模型不含）。
    """
    assert l_nm > 0
    return _seg_r(RSH["poly"], reach_nm, w_poly_nm)


def extract_r(cell: Cell) -> dict:
    """每器件：栅 R + 左右源漏 R（扩散段 + 接触孔）；并给全单元金属段 R 汇总。"""
    out = {"devices": [], "metal": {}}
    for g in cell.by_layer(L_POLY):
        for d in cell.by_layer(L_DIFF):
            if not _touch(g, d):
                continue
            ox0, ox1 = max(g.x0, d.x0), min(g.x1, d.x1)
            if ox1 <= ox0:
                continue
            gconts = [c for c in cell.by_layer(L_CONT) if _touch(c, g)]
            reach = min([abs(c.cx - ox0) for c in gconts] or [0.0])
            sd = []
            for (sx0, sx1) in ((d.x0, ox0), (ox1, d.x1)):
                if sx1 <= sx0:
                    continue
                probe = R(L_DIFF, sx0, d.y0, sx1, d.y1)
                cs = [c for c in cell.by_layer(L_CONT) if _touch(c, probe)]
                dist = min([min(abs(c.cx - sx0), abs(sx1 - c.cx)) for c in cs] or [0.0])
                sd.append({"len_nm": sx1 - sx0, "dist_nm": dist,
                           "n_cont": len(cs),
                           "r_ohm": _seg_r(RSH["diff"], dist, d.h) + R_CONTACT * len(cs)})
            out["devices"].append({"gate_ohm": gate_r(reach, g.w, ox1 - ox0),
                                   "reach_nm": reach, "sd": sd,
                                   "l_nm": ox1 - ox0, "w_nm": d.h})
    for m in cell.by_layer(L_M1):
        length, width = max(m.w, m.h), min(m.w, m.h)
        out["metal"].setdefault(m.role, 0.0)
        out["metal"][m.role] += _seg_r(RSH["m1"], length, width)
    return out


# ═══════════════════════════════════════════════════════════════════════════
# ⑦ 自检
# ═══════════════════════════════════════════════════════════════════════════
def cell_self_check(verbose: bool = False) -> dict:
    problems: list = []
    per: dict = {}
    for name, fn in CELLS.items():
        c = fn()
        drc, lvs = run_drc(c), run_lvs(c)
        rp = extract_r(c)
        devs = lvs["devices"]
        n_tr = len(devs)
        per[name] = {"area_um2": c.area_um2, "n_tr": n_tr,
                     "area_per_tr": c.area_um2 / n_tr if n_tr else None,
                     "drc": drc["n"], "lvs": lvs["n"],
                     "w_list": sorted({d["w"] for d in devs}),
                     "l_list": sorted({d["l"] for d in devs}),
                     "gate_r": [round(d["gate_ohm"], 3) for d in rp["devices"]]}
        if drc["n"]:
            problems.append("%s DRC %d: %s" % (name, drc["n"], drc["violations"][:5]))
        if lvs["n"]:
            problems.append("%s LVS %d: %s" % (name, lvs["n"], lvs["mismatches"][:4]))
        if n_tr == 0:
            problems.append("%s 未抽出器件" % name)
        for k, dv in enumerate(rp["devices"]):
            if not (dv["gate_ohm"] > 0):
                problems.append("%s 器件%d 栅 R=%.3f 非正" % (name, k, dv["gate_ohm"]))
            if len(dv["sd"]) != 2 or any(s["r_ohm"] <= 0 for s in dv["sd"]):
                problems.append("%s 器件%d S/D R 异常 %s" % (name, k, dv["sd"]))
        if verbose:
            print("[%s] %s" % (name, per[name]))
    return {"ok": not problems, "problems": problems, "per_cell": per}


B1_DISCLOSURE = {
    "what": "标准单元晶体管级内部几何（DIFF/POLY/CONT/M1/NWELL）+ 几何抽器件 + DRC/LVS/R",
    "ruleset": "LDA-DEMO45（自建 · 45nm 量级尺度 · 非任何 foundry PDK 真值）",
    "claimable": False,
    "not_a_spice": True,
    "why_not_signoff_grade": (
        "器件模型只有 W/L 与方块电阻；无 I-V/C/温度/噪声；规则集非 PDK 真值；"
        "无流片实测 ⇒ 只把 design-period 签核的**几何/连通/寄生**三件事机器化，"
        "不构成 signoff-grade 结论（B3 才谈多角/IR/EM）。"),
}


# ═══════════════════════════════════════════════════════════════════════════
# ⑥ A1（v0.9.413）：DEMO45 规则下的时序单元版图 `CELLS_DH`
# ═══════════════════════════════════════════════════════════════════════════
#: 🔴 **独立集合，绝不并入 `CELLS`**：`dpnr.CELL_W_UM` / `row_height_um()` 只取
#: `CELLS` 三项的最大宽高；把 DH 单元并进去会顶起主链 c17 的 9 个固定口径数字。
#: 双库布局由 A2 的 `place_real(..., dh_lib=)` 显式启用，pitch_x / 行高单独返回。
#:
#: 🔴 **为什么自带一份拓扑表而不 import `dhdlib.DFF_COLS`**：`dhdlib` 顶层
#: `from .dcells import ...`，反向 import 会形成循环。两处声明由 s13 的 EC-G36
#: 用「多重集逐项一致」机核守护，不是静默的第二份真源。
#:
#: 🔴 **LVS 口径（D6 已拍板）**：22T 有大量无名内部节点，通用 `run_lvs` 的
#: `device_set` 集合比对必然报 1 条（电路其实是对的，`dhdlib.py:590` 已登记）；
#: 拓扑等价改由 `dhdlib.run_lvs_pos` 的几何序 + 单值双射判定。**报 LVS 必须写清
#: 是哪一套**，不得笼统写「LVS 0」。DRC 一律走本模块的 `run_drc(cell, RULES)`，
#: 绝不另写一套检查器。
DH_DFF_COLS = (
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

#: 几何常量（nm）。闭式来源见 `LDA_电子域_F2_A1-1_几何可行性测算_2026-11-13.md`：
#: `gate_cont 40` ⇒ 岛内两孔距 ≥175；`cont_enc_diff 15` ⇒ 岛宽 ≥250；
#: `diff_s 100` ⇒ 节距 ≥350。11 列 ⇒ `80 + 11×350 + 80 = 4010`。
DH_X0, DH_PITCH, DH_ISL, DH_NCOL = 80, 350, 250, 11
DH_W_DFF = DH_X0 + DH_NCOL * DH_PITCH + 80        # 4010
DH_W_BUF = DH_X0 + 2 * DH_PITCH + 80              # 860
DH_H_DFF, DH_H_BUF = 4370, 1950
DH_N_DIFF, DH_P_DIFF = (180, 480), (3400, 4150)
DH_N_CY, DH_P_CY = 330, 3775
DH_NSEG_TOP, DH_PSEG_BOT, DH_POLY_TOP = 900, 1050, 4200
DH_VSS, DH_VDD = (0, 70), (4300, 4370)
DH_NWELL = (3320, 4230)
DH_Y0, DH_PLV = 620, 215

#: 13 条全宽 M1 总线电平：`ckb` / `ckbb` 各占低/高两条，由该网自身的
#: 全高 M2 竖带在两个电平各打 VIA1 自然连通（不需要额外 M2 link）。
DH_LEVEL_NET = {
    0: "ckb", 1: "ckbb", 2: "D", 3: "m", 4: "mb", 5: "s", 6: "sb",
    7: "Q", 8: "q1", 9: "CLK", 10: "QN", 11: "ckb", 12: "ckbb",
}
DH_NET_LEVELS = {
    "ckb": [0, 11], "ckbb": [1, 12], "CLK": [9], "D": [2], "m": [3],
    "mb": [4], "s": [5], "sb": [6], "q1": [8], "Q": [7], "QN": [10],
}
DH_TG_NG_LEVEL = {2: 0, 5: 1}
DH_TG_PG_LEVEL = {2: 12, 5: 11}
DH_PIN_LEVEL = {"D": 2, "CLK": 9, "Q": 7, "QN": 10}


def _dh_ylv(k: int) -> int:
    return DH_Y0 + DH_PLV * k


def _dh_x0(i: int) -> int:
    return DH_X0 + i * DH_PITCH


def _dh_lx(i: float) -> float:
    return _dh_x0(i) + 37.5


def _dh_rx(i: float) -> float:
    return _dh_x0(i) + 212.5


def _dh_gx(i: float) -> float:
    return _dh_x0(i) + 125.0


def _dh_cont(cx, cy, role: str) -> R:
    return R(L_CONT, *_cont_box(cx, cy), role=role)


def _dh_m1pad(cx, cy) -> R:
    a, b, c, d = _cont_box(cx, cy)
    return R(L_M1, a - 10, b - 10, c + 10, d + 10, role="pad")


def _dh_polypad(cx, cy) -> R:
    a, b, c, d = _cont_box(cx, cy)
    return R(L_POLY, a - 15, b - 15, c + 15, d + 15, role="gate_pad")


def _dh_strap_x(cx) -> tuple:
    a, _b, c, _d = _cont_box(cx, DH_N_CY)
    return a - 8, c + 8


def _dh_via(cx, cy) -> R:
    a, b, c, d = _cont_box(cx, cy)
    return R(L_VIA1, a - 8, b - 8, c + 8, d + 8, role="via1")


def build_dff_dh() -> Cell:
    """DFF_X1_DH：DEMO45 规则下的 22T 主从 DFF（11 列独立岛）。

    与 `dhdlib.DFF_COLS` 的开关级拓扑同构；几何按 LDA-DEMO45 规则放大：
    每列一对独立 DIFF 岛（250 宽 / 350 节距）、栅宽 50、孔 45；
    M1 只做 13 条全宽水平总线，M2 只做全高竖带，VIA1 在两层间跨接。
    W=4010 / H=4370；22 器件；`run_drc(RULES)=0`、`run_lvs_pos=0`。
    """
    W, H = DH_W_DFF, DH_H_DFF
    rects = [R(L_M1, 0, DH_VSS[0], W, DH_VSS[1], role="rail"),
             R(L_M1, 0, DH_VDD[0], W, DH_VDD[1], role="rail"),
             R(L_NWELL, 0, DH_NWELL[0], W, DH_NWELL[1], role="nwell")]
    for k in DH_LEVEL_NET:
        y = _dh_ylv(k)
        rects.append(R(L_M1, 0, y - 30, W, y + 30, role="bus"))

    devs = []
    for i, (kind, a, b, pg, ng) in enumerate(DH_DFF_COLS):
        X = _dh_x0(i)
        gxl, gxr = X + 100, X + 150
        rects += [R(L_DIFF, X, DH_N_DIFF[0], X + DH_ISL, DH_N_DIFF[1], role="diff"),
                  R(L_DIFF, X, DH_P_DIFF[0], X + DH_ISL, DH_P_DIFF[1], role="diff")]
        if kind == "inv":
            rects.append(R(L_POLY, gxl, 130, gxr, DH_POLY_TOP, role="gate"))
        else:
            rects += [R(L_POLY, gxl, 130, gxr, DH_NSEG_TOP, role="gate_n"),
                      R(L_POLY, gxl, DH_PSEG_BOT, gxr, DH_POLY_TOP, role="gate_p")]
        for cy in (DH_N_CY, DH_P_CY):
            for cx in (_dh_lx(i), _dh_rx(i)):
                rects += [_dh_cont(cx, cy, "cont_sd"), _dh_m1pad(cx, cy)]
        if kind == "inv":
            k = DH_NET_LEVELS[a][0]
            rects += [_dh_cont(_dh_gx(i), _dh_ylv(k), "cont_gate"),
                      _dh_polypad(_dh_gx(i), _dh_ylv(k)),
                      _dh_m1pad(_dh_gx(i), _dh_ylv(k))]
        else:
            for k in (DH_TG_NG_LEVEL[i], DH_TG_PG_LEVEL[i]):
                rects += [_dh_cont(_dh_gx(i), _dh_ylv(k), "cont_gate"),
                          _dh_polypad(_dh_gx(i), _dh_ylv(k)),
                          _dh_m1pad(_dh_gx(i), _dh_ylv(k))]
        if kind == "inv":
            rects += [R(L_M1, X + 5, DH_VSS[1], X + 70, DH_N_CY + 33, role="strap"),
                      R(L_M1, X + 5, DH_P_CY - 33, X + 70, DH_VDD[0], role="strap")]
        # 声明顺序 = 每列 (pmos, nmos) 交错；run_lvs_pos 按 kind 稳定重排后与几何序一致
        if kind == "inv":
            devs += [("pmos", 750, 50, a, "VDD", b), ("nmos", 300, 50, a, "VSS", b)]
        else:
            devs += [("pmos", 750, 50, pg, a, b), ("nmos", 300, 50, ng, a, b)]

    for i, (kind, a, b, _pg, _ng) in enumerate(DH_DFF_COLS):
        pairs = [(_dh_rx(i), b)] if kind == "inv" else [(_dh_lx(i), a), (_dh_rx(i), b)]
        for cx, net in pairs:
            sx0, sx1 = _dh_strap_x(cx)
            rects.append(R(L_M2, sx0, 280, sx1, 3820, role="m2"))
            rects += [_dh_via(cx, DH_N_CY), _dh_via(cx, DH_P_CY)]
            for k in DH_NET_LEVELS[net]:
                rects.append(_dh_via(cx, _dh_ylv(k)))

    d_pad = R(L_M1, 0, _dh_ylv(DH_PIN_LEVEL["D"]) - 120, 240,
              _dh_ylv(DH_PIN_LEVEL["D"]) + 120, net="D", role="pin")
    clk_pad = R(L_M1, 0, _dh_ylv(DH_PIN_LEVEL["CLK"]) - 120, 240,
                _dh_ylv(DH_PIN_LEVEL["CLK"]) + 120, net="CLK", role="pin")
    q_pad = R(L_M1, W - 240, _dh_ylv(DH_PIN_LEVEL["Q"]) - 120, W,
              _dh_ylv(DH_PIN_LEVEL["Q"]) + 120, net="Q", role="pin")
    qn_pad = R(L_M1, W - 240, _dh_ylv(DH_PIN_LEVEL["QN"]) - 120, W,
               _dh_ylv(DH_PIN_LEVEL["QN"]) + 120, net="QN", role="pin")
    rects += [d_pad, clk_pad, q_pad, qn_pad]
    pins = {"VDD": R(L_M1, 0, DH_VDD[0], W, DH_VDD[1], net="VDD"),
            "VSS": R(L_M1, 0, DH_VSS[0], W, DH_VSS[1], net="VSS"),
            "D": d_pad, "CLK": clk_pad, "Q": q_pad, "QN": qn_pad}
    return Cell("DFF_X1_DH", W, H, rects, pins, devs)


def build_buf_dh() -> Cell:
    """BUF_X1_DH：两级 INV 串联（4T），DEMO45 规则下的独立岛几何。

    与 `dhdlib.build_buf_hd` 电路同构（A → n1 → Y）。W=860 / H=1950；
    4 器件；`run_drc(RULES)=0`、`run_lvs_pos=0`、`run_lvs=0`。
    """
    W, H = DH_W_BUF, DH_H_BUF
    py0, py1 = 1000, 1750
    pcy = 1375
    rects = [R(L_NWELL, 0, 920, W, 1830, role="nwell"),
             R(L_M1, 0, 0, W, 70, role="rail"),
             R(L_M1, 0, 1880, W, 1950, role="rail")]
    for i in range(2):
        X = _dh_x0(i)
        gxl, gxr = X + 100, X + 150
        rects += [R(L_DIFF, X, DH_N_DIFF[0], X + DH_ISL, DH_N_DIFF[1], role="diff"),
                  R(L_DIFF, X, py0, X + DH_ISL, py1, role="diff"),
                  R(L_POLY, gxl, 130, gxr, 1800, role="gate")]
        for cy in (DH_N_CY, pcy):
            for cx in (_dh_lx(i), _dh_rx(i)):
                rects += [_dh_cont(cx, cy, "cont_sd"), _dh_m1pad(cx, cy)]
        lx = _dh_lx(i)
        a, b, c, d = _cont_box(lx, DH_N_CY)
        rects.append(R(L_M1, a - 10, 70, c + 10, d + 10, role="strap_vss"))
        a, b, c, d = _cont_box(lx, pcy)
        rects.append(R(L_M1, a - 10, b - 10, c + 10, 1880, role="strap_vdd"))
    for i, yb in enumerate((800, 930)):
        cx = _dh_rx(i)
        sx0, sx1 = _dh_strap_x(cx)
        rects.append(R(L_M2, sx0, 300, sx1, 1400, role="m2"))
        for cy in (DH_N_CY, pcy, yb):
            rects.append(_dh_via(cx, cy))
    for i, cy in enumerate((560, 800)):
        gx = _dh_gx(i)
        rects += [_dh_polypad(gx, cy), _dh_cont(gx, cy, "cont_gate"),
                  _dh_m1pad(gx, cy)]
    c0r, c1g, c1r = _dh_rx(0), _dh_gx(1), _dh_rx(1)
    rects += [R(L_M1, c0r - 32.5, 770, c1g + 32.5, 830, role="bus"),
              R(L_M1, c1r - 32.5, 900, W, 960, role="bus")]
    pa = R(L_M1, 0, 430, 240, 670, net="A", role="pin")
    py = R(L_M1, 620, 900, 860, 1140, net="Y", role="pin")
    rects += [pa, py]
    pins = {"VDD": R(L_M1, 0, 1880, W, 1950, net="VDD"),
            "VSS": R(L_M1, 0, 0, W, 70, net="VSS"), "A": pa, "Y": py}
    devs = [("nmos", 300, 50, "A", "VSS", "n1"),
            ("nmos", 300, 50, "n1", "VSS", "Y"),
            ("pmos", 750, 50, "A", "VDD", "n1"),
            ("pmos", 750, 50, "n1", "VDD", "Y")]
    return Cell("BUF_X1_DH", W, H, rects, pins, devs)


#: 🔴 **独立集合**：绝不并入 `CELLS`；`dcell.CELLS` 18/3 数据层一字不动。
#: 两单元**不等高**（DFF 4370 / BUF 1950）是显式登记边界，A2 双库路径的
#: 行高与 pitch_x 必须单独返回并取实际 max，不得复用 `CELL_W_UM=0.98`。
CELLS_DH = {"DFF_X1_DH": build_dff_dh, "BUF_X1_DH": build_buf_dh}

#: 口径声明（EC-G39 机核）：几何层 DH，不与数据层 `LAYOUT` 混称；
#: 规则集仍是自建 LDA-DEMO45，非 foundry PDK。
DH_BASIS_NOTE = {
    "basis": "GEOMETRY_DH",
    "ruleset": "LDA-DEMO45（自建 · 非 foundry PDK）",
    "drc": "dcells.run_drc(cell, RULES)",
    "lvs_topology": "dhdlib.run_lvs_pos（几何序 + 单值双射）",
    "lvs_generic_boundary": "dcells.run_lvs 的 device_set 对无名内部节点不适用，差异显式登记",
    "claimable": False,
    "not_equal_height": True,
}
