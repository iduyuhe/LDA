# -*- coding: utf-8 -*-
"""S3 · **DEF 子集解析器**（5.8 · 布局布线结果 · 引用 LEF MACRO 名 → S1 Layout）。

═══════════════════════════════════════════════════════════════════════════════
定位：S3 的「DEF 子集」是 LEF 的**下游**——LEF 描述**库几何**（MACRO 的 PORT/OBS 矩形、
SIZE），DEF 描述**一次具体布局布线**的结果（DESIGN 名、COMPONENTS 的实例落点、NETS 的走线）。
DEF 通过「实例名 → MACRO 名」**引用** `dlef.py` 解析出的库，故本模块**依赖 dlef** 先落地
（与 S3 规划一致：LEF 是库、DEF 是布局布线结果）。

═══════════════════════════════════════════════════════════════════════════════
支持的子集（**明确划界，越界即报错，绝不静默降级**）
───────────────────────────────────────────────────────────────────────────────
```def
DESIGN top ;
UNITS DISTANCE MICRONS 100 ;
DIEAREA ( 0 0 ) ( 1000 1000 ) ;
COMPONENTS 2 ;
  - u1 INVX1 + PLACED ( 100 200 ) N ;
  - u2 NAND2X1 + FIXED ( 300 400 ) FS ;
END COMPONENTS
NETS 1 ;
  - n1 ( u1 ZN ) ( u2 A ) + ROUTED METAL1 ( 0 0 ) ( 100 0 ) ;
END NETS
END DESIGN
```
· DESIGN / UNITS DISTANCE MICRONS / DIEAREA（多边形）/ COMPONENTS（实例 + PLACED/FIXED
  落点 + 朝向）/ NETS（终端 `( inst pin )` + `+ ROUTED` 走线层与坐标序列）。
· 坐标/朝向/层名逐字保留（µm·整数 MICRONS / 或按 UNITS 换算；本子集 UNITS 默认 100）。

🔴 不支持（抛 `DefSyntaxError`）：层次/分区、SPECIALNETS、VIAS 定义、SHAPE/FILL、
  非 `( x y )` 坐标串、缺 END 收口、COMPONENTS/NETS 计数与实际不符、引用未声明 MACRO 等。

═══════════════════════════════════════════════════════════════════════════════
两条硬保证（与 S2 dliberty / S3 dlef / S4 dverilog 同款主权红线）
───────────────────────────────────────────────────────────────────────────────
① **字节级往返双射**：`serialize(reparse(serialize(x))) == serialize(x)`
   （canonical 重写，门按名排序吐回，稳定幂等）。
② **未知语法必报错**：未闭合 END DESIGN / 缺 END COMPONENTS/NETS / 引用未声明 MACRO /
   坐标数错 / 计数不符 —— 一律抛 `DefSyntaxError`（带位置）。

⚠️ 诚实边界
──────────
· **几何来自 LEF**：本模块的 `to_model` 需要一张 `LefLibrary`（来自 `dlef`）来把实例的
  MACRO 名解析成真实 w/h 与端口几何；无 LEF 时实例 w/h 留 0（仅落点，无几何）。
· **C 级自主**：纯标准库递归下降，零第三方依赖，LLM 不进判决路径。
· **OpenROAD 可读回**：生成 DEF 能被 OpenROAD `-def` 读取是**可选外部校验**（PATH 有二进制时跑），
  **绝不**把 OpenROAD 当 golden（P1 角色位：外部当判决源 = 红）；LDA 权威来自自身无损往返。
"""
from __future__ import annotations

from dataclasses import dataclass, field


class DefSyntaxError(Exception):
    """DEF 语法错误（带 token 位置）。未知/非法语法 = 抛这个，绝不静默跳过。"""

    def __init__(self, message: str, pos: int = 0):
        self.pos = pos
        super().__init__("[位置 %d] %s" % (pos, message))


# ── 结构化模型 ────────────────────────────────────────────────────────────────
@dataclass
class DefComponent:
    name: str
    macro: str
    placed: bool           # True=PLACED, False=FIXED
    x: int
    y: int
    orient: str
    pos: int = 0           # 解析位置（用于 fail-closed 报错带位置）


@dataclass
class DefRoute:
    layer: str
    points: list           # [(x, y), ...]


@dataclass
class DefNet:
    name: str
    terms: list            # [(inst, pin), ...]
    routes: list = field(default_factory=list)   # [DefRoute, ...]


@dataclass
class DefDesign:
    name: str
    units: int = 100
    diearea: list = field(default_factory=list)   # [(x, y), ...]
    components: list = field(default_factory=list)  # [DefComponent, ...]
    nets: list = field(default_factory=list)        # [DefNet, ...]


# ── 词法器 ──────────────────────────────────────────────────────────────────
def _tokenize(s: str):
    """DEF 词法：标识符/数字/圆括号/`-`/`+`/`;` 各自成 token（记录位置）。"""
    toks = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c == ";" or c == "(" or c == ")" or c == "-" or c == "+":
            toks.append(("op", c, i))
            i += 1
            continue
        if c.isdigit() or (c == "-" and i + 1 < n and s[i + 1].isdigit()):
            # 数字（含负坐标，少见但允许）
            j = i + 1
            while j < n and (s[j].isdigit()):
                j += 1
            toks.append(("num", int(s[i:j]), i))
            i = j
            continue
        # 标识符（关键字/实例名/MACRO 名/层名/朝向/ORIENT）
        j = i
        while j < n and (s[j].isalnum() or s[j] in "_/"):
            j += 1
        toks.append(("id", s[i:j], i))
        i = j
    return toks


# ── 解析器 ──────────────────────────────────────────────────────────────────
class _Parser:
    def __init__(self, toks):
        self.t = toks
        self.i = 0
        self.n = len(toks)

    def _peek(self, k=0):
        return self.t[min(self.i + k, self.n - 1)]

    def _at(self, val):
        tk = self._peek()
        return tk[0] in ("op", "id") and tk[1] == val

    def _accept(self, val):
        if self._at(val):
            self.i += 1
            return True
        return False

    def _expect(self, val):
        tk = self._peek()
        if tk[1] != val:
            raise DefSyntaxError("期望 %r，得到 %r" % (val, tk[1]), tk[2])
        self.i += 1
        return tk

    def _expect_num(self):
        tk = self._peek()
        if tk[0] != "num":
            raise DefSyntaxError("期望整数坐标，得到 %r" % (tk[1],), tk[2])
        self.i += 1
        return tk[1]

    def _expect_id(self):
        tk = self._peek()
        if tk[0] != "id":
            raise DefSyntaxError("期望标识符，得到 %r" % (tk[1],), tk[2])
        self.i += 1
        return tk[1]

    def parse(self) -> DefDesign:
        d = DefDesign(name="")
        # DESIGN
        self._expect("DESIGN")
        d.name = self._expect_id()
        self._expect(";")
        # 可选 UNITS / DIEAREA（顺序宽松）
        while not (self._at("COMPONENTS") or self._at("NETS") or self._at("END")):
            tk = self._peek()
            if tk[1] == "UNITS":
                self.i += 1
                self._expect("DISTANCE")
                self._expect("MICRONS")
                d.units = self._expect_num()
                self._expect(";")
            elif tk[1] == "DIEAREA":
                self.i += 1
                d.diearea = self._parse_points()
                self._expect(";")
            else:
                raise DefSyntaxError("DESIGN 顶层无法识别：%r" % (tk[1],), tk[2])
        # COMPONENTS
        if self._at("COMPONENTS"):
            self._expect("COMPONENTS")
            n_comp = self._expect_num()
            self._expect(";")
            for _ in range(n_comp):
                d.components.append(self._component())
            self._expect("END")
            self._expect("COMPONENTS")
        # NETS
        if self._at("NETS"):
            self._expect("NETS")
            n_net = self._expect_num()
            self._expect(";")
            for _ in range(n_net):
                d.nets.append(self._net())
            self._expect("END")
            self._expect("NETS")
        # END DESIGN
        self._expect("END")
        self._expect("DESIGN")
        return d

    def _parse_points(self):
        """读一串 `( x y )`，返回 [(x,y), ...]。"""
        pts = []
        while self._accept("("):
            x = self._expect_num()
            y = self._expect_num()
            self._expect(")")
            pts.append((x, y))
        if not pts:
            raise DefSyntaxError("坐标串为空（至少一对 (x y)）", self._peek()[2])
        return pts

    def _component(self) -> DefComponent:
        self._expect("-")
        name_pos = self._peek()[2]
        name = self._expect_id()
        macro = self._expect_id()
        self._expect("+")
        if self._at("PLACED"):
            self.i += 1
            placed = True
        elif self._at("FIXED"):
            self.i += 1
            placed = False
        else:
            tk = self._peek()
            raise DefSyntaxError("COMPONENT 须 PLACED 或 FIXED，得到 %r" % (tk[1],), tk[2])
        self._expect("(")
        x = self._expect_num()
        y = self._expect_num()
        self._expect(")")
        orient = self._expect_id()
        self._expect(";")
        return DefComponent(name=name, macro=macro, placed=placed, x=x, y=y,
                            orient=orient, pos=name_pos)

    def _net(self) -> DefNet:
        self._expect("-")
        name = self._expect_id()
        net = DefNet(name=name, terms=[])
        # 终端 ( inst pin ) 若干
        while self._accept("("):
            inst = self._expect_id()
            pin = self._expect_id()
            self._expect(")")
            net.terms.append((inst, pin))
        # 可选 + ROUTED ...
        if self._accept("+"):
            while self._at("ROUTED"):
                self.i += 1
                layer = self._expect_id()
                pts = self._parse_points()
                net.routes.append(DefRoute(layer=layer, points=pts))
        self._expect(";")
        return net


def parse_def(src: str, lef_lib=None) -> DefDesign:
    """解析 DEF 源文本 → `DefDesign` 结构化模型。

    `lef_lib` 提供时（来自 `dlef.LefLibrary`），额外校验每个 COMPONENT 的 MACRO 名
    在库中已声明——引用未声明 MACRO 一律抛 `DefSyntaxError`（fail-closed）。
    """
    toks = _tokenize(src)
    d = _Parser(toks).parse()
    if lef_lib is not None:
        validate_macro_refs(d, lef_lib)
    return d


def validate_macro_refs(d: DefDesign, lef_lib) -> None:
    """校验每个 COMPONENT 的 MACRO 名在 LEF 库中已声明；否则抛 `DefSyntaxError`。"""
    known = {m.name() for m in lef_lib.macros}
    for c in d.components:
        if c.macro not in known:
            raise DefSyntaxError(
                "COMPONENT %r 引用未声明 MACRO %r（LEF 库中不存在）" % (c.name, c.macro),
                c.pos)


def parse_def_file(path: str) -> DefDesign:
    with open(path, "r", encoding="utf-8") as fh:
        return parse_def(fh.read())


# ── 序列化（canonical · 稳定幂等）──────────────────────────────────────────
def serialize_def(d: DefDesign) -> str:
    """把 `DefDesign` 写成 canonical DEF 5.8（块内实例/网按名排序 ⇒ 往返双射）。"""
    L = []
    L.append("DESIGN %s ;" % d.name)
    L.append("UNITS DISTANCE MICRONS %d ;" % d.units)
    if d.diearea:
        L.append("DIEAREA %s ;" % " ".join("(%d %d)" % (x, y) for (x, y) in d.diearea))
    # COMPONENTS（按名排序）
    comps = sorted(d.components, key=lambda c: c.name)
    L.append("COMPONENTS %d ;" % len(comps))
    for c in comps:
        kw = "PLACED" if c.placed else "FIXED"
        L.append("- %s %s + %s ( %d %d ) %s ;" % (
            c.name, c.macro, kw, c.x, c.y, c.orient))
    L.append("END COMPONENTS")
    # NETS（按名排序）
    nets = sorted(d.nets, key=lambda x: x.name)
    L.append("NETS %d ;" % len(nets))
    for net in nets:
        terms = " ".join("(%s %s)" % (i, p) for (i, p) in net.terms)
        rout = ""
        if net.routes:
            rout = " + " + " ".join(
                "ROUTED %s %s" % (r.layer, " ".join("(%d %d)" % (x, y) for (x, y) in r.points))
                for r in net.routes)
        L.append("- %s %s%s ;" % (net.name, terms, rout))
    L.append("END NETS")
    L.append("END DESIGN")
    return "\n".join(L) + "\n"


# ── 适配器：Placement + Netlist → DefDesign（**只写落点与连接，不写 ROUTED**）──
#: DEF 数据库单位：1 DBU = 1 nm ⇒ `UNITS DISTANCE MICRONS 1000`（不丢 nm 精度）
DEF_DBUNIT_PER_UM = 1000

#: 🔴 **LDA 约定**：`dcell` 只声明**输入**引脚名（如 `("a","b")`），**输出引脚名未声明**，
#:    统一记为 `z`。这不是库真名（HD 库用 A/Y）——真实互通须由 LEF `PORT` 名覆盖；
#:    在拿到 LEF 之前，写「看起来像库名」的引脚才是编造。
DEF_OUT_PIN = "z"


def from_placement(placement, nl, *, name: str = "lda_design",
                   units: int = DEF_DBUNIT_PER_UM, out_pin: str = DEF_OUT_PIN,
                   fixed: bool = False) -> DefDesign:
    """`dplac.Placement` + `dsynth.Netlist` → `DefDesign`（**placed DEF**）。

    🔴 **只写「落点 + 连接」，不写 `ROUTED`**：`ddetail.DetailRoute.shapes` 是整块 Shape
    列表、**没有按网归属** —— 强行写 ROUTED 等于编造布线。布线导出须先给 shape 打网标签
    （已登记为后续里程碑）。

    坐标：`Placement.cell_xywh` 是 **µm**，按 `units` 换算成整数 DBU（默认 1000 ⇒ 1 nm）。
    引脚：输入取 `dcell.CELLS[cell].pins`（LDA 自有真源）；输出记 `out_pin`（见上注）。
    落点缺失 ⇒ `ValueError`（**fail-closed**，不写半个 DEF）。
    """
    from . import dcell as DC

    def dbu(v_um) -> int:
        return int(round(float(v_um) * units))

    xywh = getattr(placement, "cell_xywh", None) or {}
    lacking = [g.name for g in nl.gates if g.name not in xywh]
    if lacking:
        raise ValueError("from_placement：以下门没有落点，拒绝写出半个 DEF：%s" % (lacking,))

    d = DefDesign(name=name, units=int(units))
    dw = float(getattr(placement, "die_w_um", 0.0) or 0.0)
    dh = float(getattr(placement, "die_h_um", 0.0) or 0.0)
    if dw > 0.0 and dh > 0.0:
        d.diearea = [(0, 0), (dbu(dw), dbu(dh))]

    for g in nl.gates:
        x0, y0, _w, _h = xywh[g.name]
        d.components.append(DefComponent(
            name=g.name, macro=g.cell, placed=not fixed,
            x=dbu(x0), y=dbu(y0), orient="N"))

    terms: dict = {}
    for g in nl.gates:
        cell = DC.CELLS.get(g.cell)
        pins = tuple(getattr(cell, "pins", ()) or ())
        for k, net in enumerate(g.ins):
            if net == "CLK":
                pin = "CLK"
            else:
                pin = pins[k] if k < len(pins) else ("p%d" % k)
            terms.setdefault(net, []).append((g.name, pin))
        terms.setdefault(g.out, []).append((g.name, out_pin))
    for net in sorted(terms):
        d.nets.append(DefNet(name=net, terms=sorted(terms[net])))
    return d


# ── 适配器：DefDesign → S1 Layout（需 LEF 库解析 MACRO 几何）────────────────
# DEF 层名 → model 整数层（与 ddetail/ddrc_lvs 同约定：Metal1=1…Metal4=4, Via1=5…）
_LAYER_INDEX = {
    "METAL1": 1, "METAL2": 2, "METAL3": 3, "METAL4": 4,
    "VIA1": 5, "VIA2": 6, "VIA3": 7,
}


def to_model(d: DefDesign, lef_lib=None):
    """把 `DefDesign` 转成 S1 `Layout`（实例按 DEF 落点摆；布线走线 → shapes）。

    `lef_lib` 为 `dlef.LefLibrary` 时，按 MACRO 名解析真实 w/h 与端口几何（经 `dlef.to_model`
    得到 CellView）；否则实例仅落点（cell=None，无几何）。坐标统一用 µm·整数 MICRONS。
    """
    from .. import model as MD
    from .dlef import to_model as lef_to_model

    cell_geom = {}
    if lef_lib is not None:
        cell_geom = lef_to_model(lef_lib)   # dict[macro_name] -> CellView

    insts = []
    for c in d.components:
        cv = cell_geom.get(c.macro)
        insts.append(MD.Instance(name=c.name, cell_name=c.macro,
                                 x_nm=c.x, y_nm=c.y, orient=c.orient, cell=cv))
    # 布线走线 → shapes（每个相邻点对画一段矩形；层取整数索引）
    shapes = []
    for net in d.nets:
        for r in net.routes:
            layer = _LAYER_INDEX.get(r.layer.upper(), 0)
            pts = r.points
            for a, b in zip(pts, pts[1:]):
                x0, y0 = a
                x1, y1 = b
                shapes.append(MD.Rect(x0_nm=min(x0, x1), y0_nm=min(y0, y1),
                                      x1_nm=max(x0, x1), y1_nm=max(y0, y1),
                                      layer=layer))
    # 网（含终端）
    nets = []
    net_map = {}
    for net in d.nets:
        for (inst, pin) in net.terms:
            net_map.setdefault(net.name, MD.Net(name=net.name))
            net_map[net.name].pins.append((inst, pin))
    nets = [net_map[k] for k in sorted(net_map)]
    dw = dh = 0
    if d.diearea:
        xs = [p[0] for p in d.diearea]
        ys = [p[1] for p in d.diearea]
        dw = max(xs) - min(xs)
        dh = max(ys) - min(ys)
    return MD.Layout(die_w_nm=dw, die_h_nm=dh, instances=insts, nets=nets,
                     shapes=shapes)


# 别名：与 __init__ 导出名一致（def_to_model = to_model）
def_to_model = to_model


# ═══════════════════════════════════════════════════════════════════════════
# 代表性合成样本（引用 dlef.SAMPLE_LEF 的 INVX1/NAND2X1）
# ═══════════════════════════════════════════════════════════════════════════
SAMPLE_DEF = """DESIGN c17_placed ;
UNITS DISTANCE MICRONS 100 ;
COMPONENTS 2 ;
- u1 INVX1 + PLACED ( 100 200 ) N ;
- u2 NAND2X1 + FIXED ( 300 400 ) FS ;
END COMPONENTS
NETS 1 ;
- n1 ( u1 ZN ) ( u2 A ) + ROUTED METAL1 ( 0 0 ) ( 100 0 ) ;
END NETS
END DESIGN
"""


DDEF_DISCLOSURE = {
    "route": "S3 · DEF 子集（5.8 · 布局布线结果 · 引用 LEF MACRO 名）",
    "analysis": "递归下降读 DESIGN/UNITS/DIEAREA/COMPONENTS(PLACED|FIXED)/NETS(ROUTED)；"
                "canonical 重写 ⇒ 往返双射；to_model 需 LEF 库解析 MACRO 几何。",
    "golden": "LDA 权威 = 自身无损往返 + 结构守恒；OpenROAD 仅可选读回校验，不当 golden。",
    "not_included": "SPECIALNETS/VIAS/分区/SHAPE 等未建模（越界即报错，不静默降级）。",
    "claimable": False,
    "claimable_reason": "DEF 是布局布线结果的容器；本子集坐标/层名逐字保留，但真实签核需商业工具。"
}
