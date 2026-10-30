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
    LIB_LAYER_E_POLY as L_POLY,
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

# ---- 方块电阻（Ω/□ · 教科书量级 · 一阶）----
RSH = {"poly": 8.0, "diff": 120.0, "m1": 0.10}
R_CONTACT = 6.0          # Ω / 个（单接触孔）

# ---- 单元行高与公共带（nm）----
H_ROW = 1240             # 单元高度（含上下电源轨）
RAIL_H = 70              # 电源轨高度（M1）
Y_VSS = (0, RAIL_H)                      # VSS 轨
Y_VDD = (H_ROW - RAIL_H, H_ROW)          # VDD 轨
Y_NDIFF = (180, 480)                     # NMOS 有源（W = 300）
Y_PDIFF = (700, 1000)                    # PMOS 有源（W = 300）
Y_NWELL = (620, 1080)                    # NWELL（包住 PMOS 有源 ±80）
GAP = (Y_NDIFF[1], Y_PDIFF[0])           # 有源之间的间隙（放栅接触与局部互连）


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

    def by_layer(self, layer: int) -> list:
        return [r for r in self.rects if r.layer == layer]

    @property
    def area_um2(self) -> float:
        return self.w * self.h / 1e6


# ═══════════════════════════════════════════════════════════════════════════
# ① 单元构建
# ═══════════════════════════════════════════════════════════════════════════
def _rails(w: int) -> list:
    return [R(L_M1, 0, Y_VSS[0], w, Y_VSS[1], role="rail"),
            R(L_M1, 0, Y_VDD[0], w, Y_VDD[1], role="rail")]


def _cont(cx: float, cy: float, size: int | None = None, role: str = "cont") -> R:
    s = size or RULES["cont_w"]
    x0, y0 = int(round(cx - s / 2.0)), int(round(cy - s / 2.0))
    return R(L_CONT, x0, y0, x0 + s, y0 + s, role=role)


def build_inv() -> Cell:
    """INV_X1：1 PMOS + 1 NMOS · 栅 A · 输出 Y（源漏各一接触孔）。

    布局（nm · x 向右 · y 向上）::

        y=1240 ┌────────────── VDD rail (M1) ──────────────┐
        1000   │             pfet diff  W=300               │ ← NWELL ±80 包住
         700   │   [p_src]        ‖gate‖        [p_drn]     │
               │        ↑ gap：栅接触 poly pad + 局部 M1     │
         480   │             nfet diff  W=300               │
          70   ├────────────── VSS rail (M1) ──────────────┤
           0   └────────────────────────────────────────────┘
    """
    w = 620
    rects = _rails(w)
    rects.append(R(L_NWELL, 30, Y_NWELL[0], 590, Y_NWELL[1], role="nwell"))
    rects += [R(L_DIFF, 110, Y_NDIFF[0], 510, Y_NDIFF[1], role="diff"),
              R(L_DIFF, 110, Y_PDIFF[0], 510, Y_PDIFF[1], role="diff")]

    gx0, gx1 = 290, 340                       # 栅（L = 50）
    rects.append(R(L_POLY, gx0, Y_NDIFF[0] - 50, gx1, Y_PDIFF[1] + 50, role="gate"))
    # 栅接触处的 poly 焊盘：poly 条仅 50 宽，放不下 45 孔 + 15 包围 ⇒ 局部加宽（合法）
    rects.append(R(L_POLY, 270, 545, 360, 620, role="gate_pad"))

    rects += [_cont(182.5, 312.5, role="cont_sd"),     # NMOS 源 → VSS
              _cont(442.5, 312.5, role="cont_sd"),     # NMOS 漏 → Y
              _cont(182.5, 772.5, role="cont_sd"),     # PMOS 源 → VDD
              _cont(442.5, 772.5, role="cont_sd"),     # PMOS 漏 → Y
              _cont(314.5, 582.5, role="cont_gate")]   # 栅接触 → A

    m_y = R(L_M1, 410, 280, 475, 810, role="strap")    # Y：NMOS 漏 ↔ PMOS 漏
    rects += [R(L_M1, 150, Y_VSS[1], 215, 350, role="strap"),   # VSS → NMOS 源
              R(L_M1, 150, 740, 215, Y_VDD[0], role="strap"),   # VDD → PMOS 源
              m_y,
              R(L_M1, 0, 550, 347, 615, role="pin")]            # A：栅接触 → 左边界

    pins = {"VDD": R(L_M1, 0, Y_VDD[0], w, Y_VDD[1], net="VDD"),
            "VSS": R(L_M1, 0, Y_VSS[0], w, Y_VSS[1], net="VSS"),
            "A": R(L_M1, 0, 550, 347, 615, net="A"),
            "Y": R(L_M1, 410, 280, 475, 810, net="Y")}
    devs = [("pmos", 300, 50, "A", "VDD", "Y"),
            ("nmos", 300, 50, "A", "VSS", "Y")]
    return Cell("INV_X1", w, H_ROW, rects, pins, devs)


def build_nand2() -> Cell:
    """NAND2_X1：2 串 NMOS + 2 并 PMOS（4 器件）。

    拓扑（LVS 对照面）::

        PMOS（并联）:  Y —|A|— VDD —|B|— Y
        NMOS（串联）:  VSS —|A|— n1 —|B|— Y

    版图约束（为什么本单元比 INV 高）：
      · 两个输入焊垫都要在 gap 里放（poly 条只有 50 宽，放不下 45 孔 + 15 包围 ⇒ 需局部加宽），
        而 poly 焊盘之间必须 ≥ `poly_s=120`、焊盘与有源之间必须不重叠；
      · 并联 PMOS 的两个 Y 端（左/右）必须互连，而中间那段是 VDD ⇒ Y 的横向连接只能走
        gap 里的一条专用 M1 带（y 620–690），它两侧要各留 60 给两个输入焊垫。
      ⇒ gap 至少 60+70+60+60+70+60 = 380，故 PMOS 行下移到 y=1000、单元高 1500。
    """
    w = 980
    y_pdiff = (1000, 1300)
    y_nwell = (920, 1380)
    y_vdd = (1430, 1500)
    rects = [R(L_M1, 0, Y_VSS[0], w, Y_VSS[1], role="rail"),
             R(L_M1, 0, y_vdd[0], w, y_vdd[1], role="rail"),
             R(L_NWELL, 30, y_nwell[0], 870, y_nwell[1], role="nwell"),
             R(L_DIFF, 110, Y_NDIFF[0], 790, Y_NDIFF[1], role="diff"),
             R(L_DIFF, 110, y_pdiff[0], 790, y_pdiff[1], role="diff")]

    # 两条栅（A / B）跨双有源；gap 内各自加宽成焊盘放接触孔
    rects += [R(L_POLY, 250, Y_NDIFF[0] - 50, 300, y_pdiff[1] + 10, role="gate"),
              R(L_POLY, 560, Y_NDIFF[0] - 50, 610, y_pdiff[1] + 10, role="gate"),
              R(L_POLY, 235, 485, 315, 560, role="gate_pad"),     # A 焊盘
              R(L_POLY, 545, 645, 625, 720, role="gate_pad")]     # B 焊盘

    # 源漏接触孔：NMOS 左=VSS / 右=Y；PMOS 左=Y / 中=VDD / 右=Y
    rects += [_cont(172.5, 312.5, role="cont_sd"),
              _cont(722.5, 312.5, role="cont_sd"),
              _cont(172.5, 1087.5, role="cont_sd"),
              _cont(422.5, 1087.5, role="cont_sd"),
              _cont(722.5, 1087.5, role="cont_sd"),
              _cont(274.5, 522.5, role="cont_gate"),
              _cont(584.5, 682.5, role="cont_gate")]

    # M1：电源引下 / 两输入焊垫（都从左边界出，分处两条 y 带）/ Y 三段（左竖 + gap 横 + 右竖）
    # 🔴 y 带分配（gap 480–1000）：A 输入 485–560 · B 输入 645–720 · Y 横连 780–850，
    #    两两间距 ≥60（M1 最小间距）。Y 左竖从 PMOS 左端下到横连带，途中不与任何输入网相交。
    m_y_r = R(L_M1, 690, 280, 755, 1120, role="strap")
    rects += [R(L_M1, 140, Y_VSS[1], 205, 345, role="strap"),          # VSS
              R(L_M1, 390, 1055, 455, y_vdd[0], role="strap"),         # VDD
              R(L_M1, 0, 485, 315, 560, role="pin"),                   # A
              R(L_M1, 0, 645, 625, 720, role="pin"),                   # B
              m_y_r,
              R(L_M1, 140, 780, 205, 1120, role="strap"),              # Y 接 PMOS 左端（左竖）
              R(L_M1, 140, 780, 755, 850, role="strap")]               # Y gap 横连

    pins = {"VDD": R(L_M1, 0, y_vdd[0], w, y_vdd[1], net="VDD"),
            "VSS": R(L_M1, 0, Y_VSS[0], w, Y_VSS[1], net="VSS"),
            "A": R(L_M1, 0, 485, 315, 560, net="A"),
            "B": R(L_M1, 0, 645, 625, 720, net="B"),
            "Y": R(L_M1, 690, 280, 755, 1120, net="Y")}
    devs = [("pmos", 300, 50, "A", "Y", "VDD"),
            ("pmos", 300, 50, "B", "VDD", "Y"),
            ("nmos", 300, 50, "A", "VSS", "n1"),
            ("nmos", 300, 50, "B", "n1", "Y")]
    return Cell("NAND2_X1", w, y_vdd[1], rects, pins, devs)


CELLS = {"INV_X1": build_inv, "NAND2_X1": build_nand2}


# ═══════════════════════════════════════════════════════════════════════════
# ② 连通性引擎（DIFF 被 POLY 切段 + 同层相接合并 + 接触孔跨层）
# ═══════════════════════════════════════════════════════════════════════════
def _touch(a: R, b: R, tol: int = 0) -> bool:
    """同层/异层矩形是否相接或重叠（含边贴边）。"""
    return (a.x0 <= b.x1 + tol and b.x0 <= a.x1 + tol
            and a.y0 <= b.y1 + tol and b.y0 <= a.y1 + tol)


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


def _groups(shapes: list) -> list:
    n = len(shapes)
    p = _uf(n)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = shapes[i], shapes[j]
            if a.layer == b.layer and _touch(a, b):
                _union(p, i, j)
    for k, c in enumerate(shapes):
        if c.layer != L_CONT:
            continue
        for i, s in enumerate(shapes):
            if s.layer in (L_DIFF, L_POLY, L_M1) and _touch(c, s):
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
            devs.append({"kind": "pmos" if inside else "nmos", "w": oy1 - oy0,
                         "l": ox1 - ox0, "gate": gate_node, "sd": sd})
    return devs


# ═══════════════════════════════════════════════════════════════════════════
# ④ DRC（显式规则集 · 逐层 width/space/area + 接触孔包围 + 栅-孔间距）
# ═══════════════════════════════════════════════════════════════════════════
def run_drc(cell: Cell) -> dict:
    """返回 {violations: [(规则, 明细)], n}。"""
    v: list = []
    cx = connectivity(cell)
    shapes, node_of = cx["shapes"], cx["node_of"]
    # 以「原始图形」查 width/area（段是派生量，不参与）
    wmin = {L_DIFF: RULES["diff_w"], L_POLY: RULES["poly_w"],
            L_CONT: RULES["cont_w"], L_M1: RULES["m1_w"]}
    amin = {L_DIFF: RULES["diff_a"], L_POLY: RULES["poly_a"],
            L_CONT: 0, L_M1: RULES["m1_a"]}
    for r in cell.rects:
        if r.layer in wmin:
            if min(r.w, r.h) < wmin[r.layer]:
                v.append(("min_width", "%s L%d w=%d h=%d" % (r.role, r.layer, r.w, r.h)))
            if amin[r.layer] and r.area < amin[r.layer]:
                v.append(("min_area", "%s L%d a=%d" % (r.role, r.layer, r.area)))

    # 同层 space：只在不同**节点**之间查（同节点重叠/相接不算违规）
    idx = {id(s): i for i, s in enumerate(shapes)}
    smin = {L_DIFF: RULES["diff_s"], L_POLY: RULES["poly_s"], L_M1: RULES["m1_s"]}
    for layer, s_rule in smin.items():
        rs = [s for s in shapes if s.layer == layer]
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                a, b = rs[i], rs[j]
                if node_of.get(idx[id(a)]) == node_of.get(idx[id(b)]):
                    continue
                if a.role == b.role and a.role.startswith("diff_seg@"):
                    continue                     # 同一有源行被栅切开的相邻段
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
        for bases, need, tag in ((base_diff, RULES["cont_enc_diff"], "diff"),
                                 (base_poly, RULES["cont_enc_poly"], "poly")):
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
        if enc < RULES["cont_enc_m1"]:
            v.append(("cont_enc_m1", "%s enc=%d < %d" % (c.role, enc, RULES["cont_enc_m1"])))

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
                if dx < RULES["gate_cont"]:
                    v.append(("gate_cont", "gate@%d-%d cont@%d gap=%d < %d"
                              % (ox0, ox1, c.x0, dx, RULES["gate_cont"])))

    # NWELL 包围 PMOS 有源
    wells = cell.by_layer(L_NWELL)
    for d in cell.by_layer(L_DIFF):
        inside = [w for w in wells if _touch(d, w)]
        if not inside:
            continue
        best = max(inside, key=lambda w: min(d.x0 - w.x0, w.x1 - d.x1,
                                             d.y0 - w.y0, w.y1 - d.y1))
        enc = min(d.x0 - best.x0, best.x1 - d.x1, d.y0 - best.y0, best.y1 - d.y1)
        if enc < RULES["nwell_enc"]:
            v.append(("nwell_enc", "diff@y%d-%d enc=%d < %d"
                      % (d.y0, d.y1, enc, RULES["nwell_enc"])))
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
