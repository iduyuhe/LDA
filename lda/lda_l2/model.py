"""LDA · **统一数据模型（B1）** —— 单元 / 引脚 / 时序弧 / 实例 / 线网 / 版图。

═══════════════════════════════════════════════════════════════════════════════
为什么要有这个模块（这是「基础」的第一项，不是又一个功能）
───────────────────────────────────────────────────────────────────────────────
推进规划（`docs/PLAN_foundation_2026-11.md` §一）实测过一个数字：
ecore 72 个模块里 **21 个零入度（29%）**，其中 **12 个是 E45 之后的成果**
（`dcnet` `dhdlib` `dinrow` `dmacro` `dpgrid` `dproc` `dpvt` `dscale` `dwidth`
`dwallrr` `ddroute_grid` `dpathfinder`）。**能演示，不能用。**

根因不是「模块写得差」，而是**没有一份公共数据模型**：全包 29 个 class 分散在 13 个模块里
各自定义类型，每接一次就要写一次转换 ⇒ 新增能力的默认结局是「再起一个孤岛」。

本模块只做一件事：**给「单元 / 引脚 / 时序弧 / 实例 / 线网 / 版图」定一份最小公共形状**，
并且**一行都不改既有模块**（用适配器进出）。这样下一次加能力时，第一个问题从
「我要定义什么类型」变成「我往模型里填什么」。

═══════════════════════════════════════════════════════════════════════════════
三条设计纪律
───────────────────────────────────────────────────────────────────────────────
1. 🔴 **单位进了字段名**。`_nm` / `_ff` / `_ps` 是后缀，不是注释。
   本仓踩过 `Ω×fF=fs`（写成 ps，差 1000×）的单位血案，而**比值判据看不见这类错**。
2. 🔴 **长度一律 nm 整数**（与 `dcells`/`gds_export` 同一口径）。
   布线器用 µm 浮点，但那属于布线器内部；模型层不允许浮点长度 ——
   浮点长度会在拼接时累积误差（E55 已量化过一次：`µm→nm` 唯一换算点必须收敛到一处）。
3. 🔴 **模型是「容器」，不是「实现」**。这里没有任何算法：没有 DRC、没有布线、没有时序计算。
   一旦它开始算东西，就会变成「第二套实现」，与既有模块必然漂移。

═══════════════════════════════════════════════════════════════════════════════
六类对象（最小字段集）
───────────────────────────────────────────────────────────────────────────────
`Rect`      几何矩形（层 + 四边 + 可选网标签/角色）—— 版图的最小原子
`Pin`       引脚（方向 + 几何 + 电容 + 是否时钟）
`TimingArc` 时序弧（起止引脚 + 极性 + 一阶延迟 / NLDM 表）—— Liberty 的落点
`CellView`  单元视图（尺寸 + 引脚 + 时序弧 + **全量几何** + 电源轨 + 来源）
`Instance`  实例（单元名 + 坐标 + 朝向）
`Net`       线网（网名 + 引脚列表）
`Layout`    版图（die 尺寸 + 实例 + 线网 + 非实例图形）

🔴 `CellView` 保留**全量几何**（`shapes`）而不只是引脚：E55 的教训是
「单元内部图形必须能被检查器看见」，模型层若只留引脚，等于把那个盲区重新造一遍。

═══════════════════════════════════════════════════════════════════════════════
适配器与往返（这是「可复用」的机核入口）
───────────────────────────────────────────────────────────────────────────────
`cellview_from_dcells(cell)`  ← `dcells.Cell`（DEMO45 与 HD 库都是这个类型）
`cell_to_dcells(view)`        → 回 `dcells.Cell`，用于**往返双射**判据
`instance_from_place(inst)`   ← `dpnr.place_real` 的实例字典
`layout_from_place(pl)`       ← `place_real` 的整块布局

🔴 往返不追求「顺手归一化」：`from(to(x))` 必须**逐位等于** `x`。
任何「归一化」都会让上游数字悄悄变形，而那种变形在本仓历史上极难归因。

═══════════════════════════════════════════════════════════════════════════════
诚实边界
───────────────────────────────────────────────────────────────────────────────
· **不是 Liberty/LEF/DEF 解析器**（那是 B2，下一步）：本模块只定义「解析结果往哪儿放」；
· **不含时序计算**：`TimingArc` 只是容器，怎么算仍由 `dsta` 负责；
· **不取代 `dcells.Cell`**：既有 62 道 ecore 门禁继续跑原类型，模型层是**并行视图**，
  不是重构。要它变成主链，得等 B3（端到端干线）把调用关系真正接起来；
· `meta` 是**逃生舱**：规则集名、器件表这类还没有正式字段的东西先放这里，
  等格式层（B2）落地后再升级为正式字段 —— 但**不许把算法结果塞进 `meta`**。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

#: 单位后缀契约（写进字段名，不靠注释）
UNIT_LEN = "nm"     # 长度
UNIT_CAP = "ff"     # 电容
UNIT_TIME = "ps"    # 时间

#: 引脚方向（Liberty 的三值 + LEF 的 inout）
DIRECTIONS = ("input", "output", "inout")

#: 时序极性（Liberty `timing_sense`）
SENSES = ("positive_unate", "negative_unate", "non_unate")


# ═══════════════════════════════════════════════════════════════════════════
# ① 几何
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Rect:
    """版图矩形（**nm 整数**）。`net` 是网标签（E55 的「设计意图」），空串表示未标。"""
    layer: int
    x0_nm: int
    y0_nm: int
    x1_nm: int
    y1_nm: int
    net: str = ""
    role: str = ""

    @property
    def w_nm(self) -> int:
        return self.x1_nm - self.x0_nm

    @property
    def h_nm(self) -> int:
        return self.y1_nm - self.y0_nm

    def __post_init__(self):
        # 🔴 上游类型不统一是**真事**：`dcells` 的 DEMO45 单元用 int，HD 库（E53/E54）
        # 有 10 处 `float` 但值都是整数（`70.0` 这类）。本层的口径是「**值为整数即合法，
        # 归一化成 int**」；真非整数（`70.5`）一律报错 —— 那才是精度问题，不能静默吞掉。
        # 归一化只做「float 整数值 → int」，不做任何舍入 ⇒ 往返仍逐位一致。
        for fname in ("x0_nm", "y0_nm", "x1_nm", "y1_nm"):
            v = getattr(self, fname)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise TypeError("Rect.%s 必须是 int 或值为整数的 float（nm）：%r"
                                % (fname, v))
            if isinstance(v, float):
                if not v.is_integer():
                    raise TypeError("Rect.%s 是**非整数** nm 坐标（精度问题，不可静默）：%r"
                                    % (fname, v))
                object.__setattr__(self, fname, int(v))
        if self.x1_nm < self.x0_nm or self.y1_nm < self.y0_nm:
            raise ValueError("Rect 需 x1>=x0 且 y1>=y0：%r" % (self,))


# ═══════════════════════════════════════════════════════════════════════════
# ② 引脚与时序弧
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Pin:
    """引脚：方向 + 几何 + 电容 + 是否时钟。

    `rect` 允许为空 —— 有些库只有抽象引脚（无 LEF 几何），此时仍可参与网表与 STA。
    """
    name: str
    direction: str = "input"
    rect: Optional[Rect] = None
    cap_ff: float = 0.0
    is_clock: bool = False

    def __post_init__(self):
        if self.direction not in DIRECTIONS:
            raise ValueError("Pin.direction 必须是 %s：%r" % (DIRECTIONS, self.direction))


@dataclass(frozen=True)
class TimingArc:
    """时序弧：起止引脚 + 极性 + **一阶延迟** 或 **NLDM 表**。

    `table` 形状 = `(slew_ps: tuple, load_ff: tuple, delays_ps: tuple[tuple])`，
    三者维度必须自洽（`len(delays) == len(slew)` 且每行 `len == len(load)`）。
    只给 `delay_ps` 不给表 = 一阶口径（`dsta` 现状即此）；两者都给 = 表优先。
    """
    from_pin: str
    to_pin: str
    sense: str = "positive_unate"
    delay_ps: Optional[float] = None
    table: Optional[Tuple[Tuple[float, ...], Tuple[float, ...],
                          Tuple[Tuple[float, ...], ...]]] = None

    def __post_init__(self):
        if self.sense not in SENSES:
            raise ValueError("TimingArc.sense 必须是 %s：%r" % (SENSES, self.sense))
        if self.table is not None:
            slew, load, vals = self.table
            if len(vals) != len(slew) or any(len(r) != len(load) for r in vals):
                raise ValueError("TimingArc.table 维度不自洽：%d×%d vs %d×%d"
                                 % (len(slew), len(load), len(vals),
                                    len(vals[0]) if vals else 0))


# ═══════════════════════════════════════════════════════════════════════════
# ③ 单元视图
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class CellView:
    """单元视图：几何 + 引脚 + 时序弧 + 电源轨 + **来源**。

    🔴 `shapes` 是**全量几何**（含 DIFF/POLY/CONT/各层金属）。只留引脚会把
    E55 修掉的「内部图形盲区」重新造一遍。
    """
    name: str
    w_nm: int
    h_nm: int
    pins: Dict[str, Pin] = field(default_factory=dict)
    arcs: List[TimingArc] = field(default_factory=list)
    shapes: List[Rect] = field(default_factory=list)
    rail_y_nm: Optional[Tuple[int, int]] = None
    source: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def area_um2(self) -> float:
        return self.w_nm * self.h_nm / 1e6

    def pin_names(self) -> frozenset:
        return frozenset(self.pins)

    def obstacles(self) -> List[Rect]:
        """非引脚图形（布线器要躲的部分）。派生量，不落盘。"""
        pin_rects = {(p.rect.layer, p.rect.x0_nm, p.rect.y0_nm,
                      p.rect.x1_nm, p.rect.y1_nm)
                     for p in self.pins.values() if p.rect is not None}
        return [r for r in self.shapes
                if (r.layer, r.x0_nm, r.y0_nm, r.x1_nm, r.y1_nm) not in pin_rects]


# ═══════════════════════════════════════════════════════════════════════════
# ④ 实例 / 线网 / 版图
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class Instance:
    name: str
    cell_name: str
    x_nm: int
    y_nm: int
    orient: str = "N"
    cell: Optional[CellView] = None


@dataclass
class Net:
    name: str
    pins: List[Tuple[str, str]] = field(default_factory=list)   # [(inst_name, pin_name)]


@dataclass
class Layout:
    die_w_nm: int
    die_h_nm: int
    instances: List[Instance] = field(default_factory=list)
    nets: List[Net] = field(default_factory=list)
    shapes: List[Rect] = field(default_factory=list)            # 非实例图形（填充/标记）


# ═══════════════════════════════════════════════════════════════════════════
# ⑤ 适配器：dcells.Cell ⇄ CellView（**唯一入口，不改既有模块**）
# ═══════════════════════════════════════════════════════════════════════════
def _rect_from_r(r, labels=None) -> Rect:
    net = getattr(r, "net", None) or ""
    if not net and labels:
        net = labels.get((r.layer, r.x0, r.y0, r.x1, r.y1), "") or ""
    return Rect(layer=r.layer, x0_nm=r.x0, y0_nm=r.y0, x1_nm=r.x1, y1_nm=r.y1,
                net=net, role=getattr(r, "role", "") or "")


def _r_from_rect(m: Rect):
    """建 `dcells.R`（延迟导入，避免模型层硬依赖 ecore）。"""
    from .ecore import dcells as CL
    return CL.R(m.layer, m.x0_nm, m.y0_nm, m.x1_nm, m.y1_nm,
                net=(m.net or None), role=m.role)


def rail_y_from_cell(cell) -> Optional[Tuple[int, int]]:
    """从电源轨矩形（`role == "rail"`）推 `(下轨底, 下轨顶)` 与 `(上轨…)` 的 y 带。

    返回 `(vss_y0, vss_y1, vdd_y0, vdd_y1)` 太宽；这里按模型定义返回
    `(下轨中心 y, 上轨中心 y)` —— 模型层只需要「电源轨在哪」，不需要厚度。
    """
    rails = [r for r in getattr(cell, "rects", []) if getattr(r, "role", "") == "rail"]
    if len(rails) < 2:
        return None
    rails.sort(key=lambda r: r.y0)
    lo = (rails[0].y0 + rails[0].y1) // 2
    hi = (rails[-1].y0 + rails[-1].y1) // 2
    return (lo, hi)


def cellview_from_dcells(cell, source: str = None) -> CellView:
    """`dcells.Cell` → `CellView`（DEMO45 与 HD 库同型，规则差异记在 `meta`）。"""
    labels = getattr(cell, "labels", None)
    shapes = [_rect_from_r(r, labels) for r in cell.rects]
    pins: Dict[str, Pin] = {}
    for nm, pr in cell.pins.items():
        pins[nm] = Pin(name=nm, direction=("inout" if nm in ("VDD", "VSS") else "input"),
                       rect=_rect_from_r(pr, labels))
    # 输出引脚的极性从几何分不出来（那是拓扑事实）⇒ 交给调用方或后续 B2 的 Liberty 补齐。
    return CellView(
        name=cell.name, w_nm=cell.w, h_nm=cell.h, pins=pins, arcs=[],
        shapes=shapes, rail_y_nm=rail_y_from_cell(cell),
        source=source or "dcells",
        meta={"devices_expected": list(getattr(cell, "devices_expected", []) or []),
              "n_shapes": len(shapes)},
    )


def cell_to_dcells(view: CellView):
    """`CellView` → `dcells.Cell`（往返用；不发明任何几何）。"""
    from .ecore import dcells as CL
    rects = [_r_from_rect(m) for m in view.shapes]
    pins = {nm: _r_from_rect(p.rect) for nm, p in view.pins.items() if p.rect is not None}
    return CL.Cell(name=view.name, w=view.w_nm, h=view.h_nm, rects=rects, pins=pins,
                   devices_expected=[tuple(d) for d in
                                     view.meta.get("devices_expected", []) or []])


def instance_from_place(inst: dict) -> Instance:
    """`dpnr.place_real` 的实例字典 → `Instance`（µm→nm 用 round，唯一换算点）。"""
    return Instance(name=inst["name"], cell_name=inst.get("kind") or inst.get("cell", ""),
                    x_nm=int(round(inst["x0"] * 1000.0)),
                    y_nm=int(round(inst["y0"] * 1000.0)),
                    cell=cellview_from_dcells(inst["geom"], source="dpnr.place_real"))


def layout_from_place(pl: dict, netlist=None) -> Layout:
    """`place_real` 的整块布局 → `Layout`（实例 + 线网）。"""
    insts = [instance_from_place(i) for i in pl["insts"]]
    nets: Dict[str, Net] = {}
    if netlist is not None:
        for inst in pl["insts"]:
            g = inst["gate"]
            nets.setdefault(g.out, Net(name=g.out)).pins.append((inst["name"], "Y"))
            for k, n in enumerate(list(g.ins)[:2]):
                nets.setdefault(n, Net(name=n)).pins.append((inst["name"], "AB"[k]))
    return Layout(die_w_nm=int(round(pl["die_w_um"] * 1000.0)),
                  die_h_nm=int(round(pl["die_h_um"] * 1000.0)),
                  instances=insts, nets=[nets[k] for k in sorted(nets)], shapes=[])


# ═══════════════════════════════════════════════════════════════════════════
# ⑥ 基础设施体检：**引脚声明 ⇄ 版图金属** 是否一致
# ═══════════════════════════════════════════════════════════════════════════
#: 🔴 **已知不一致登记**（棘轮：只许减少）。键 = 单元名，值 = 缺 pad 金属的引脚名集合。
#: 语义不是「豁免」，而是「**这条不一致被量化过、且知道为什么暂时修不了**」：
#: 一旦修好，`pin_metal_report()` 的 `unregistered` 会变空而 `stale` 会出现 ⇒ 门禁提示删登记。
KNOWN_PIN_METAL_GAP = {
    "DFF_X1_HD": ("CLK", "D", "Q", "QN"),
}


def pins_without_metal(cell) -> list:
    """返回「pin 矩形没有被同层版图金属**覆盖**」的引脚名（按名排序）。

    判据是**覆盖**不是相触：LEF PORT 的语义是「这块区域可以落孔」，所以区域内必须都是金属；
    只有一条 30nm 宽的走线穿过 70nm 高的 PORT，边缘就没有金属，VIA 落下去 ENC 不足。
    """
    out = []
    for nm, p in cell.pins.items():
        if p.rect is None:
            continue
        box = p.rect
        cov = False
        for r in cell.shapes:                 # 🔴 CellView 的几何字段是 `shapes`，不是 `rects`
            if r.layer != box.layer:
                continue
            if (r.x0_nm <= box.x0_nm and r.y0_nm <= box.y0_nm
                    and r.x1_nm >= box.x1_nm and r.y1_nm >= box.y1_nm):
                cov = True
                break
        if not cov:
            out.append(nm)
    return sorted(out)


def pin_metal_report(cases: dict = None) -> dict:
    """逐单元体检：缺失集合 vs 登记集合。三个数字都要报，缺一不可。

    · `unregistered` = 有缺口但**没登记** ⇒ 门禁红（新缺陷混进来）
    · `stale`        = 登记了但**实际已修好** ⇒ 门禁红（棘轮收紧，提示删登记）
    · `matched`      = 登记与实测一致 ⇒ 绿
    """
    if cases is None:
        from .ecore import dcells as CL
        from .ecore import dhdlib as HD
        cases = {"INV_X1": CL.CELLS["INV_X1"](), "NAND2_X1": CL.CELLS["NAND2_X1"](),
                 "INV_X1_HD": HD.build_inv_hd(), "NAND2_X1_HD": HD.build_nand2_hd(),
                 "DFF_X1_HD": HD.build_dff_hd()}
    got, unreg, stale, matched = {}, [], [], []
    for nm, cell in cases.items():
        view = cellview_from_dcells(cell)
        miss = pins_without_metal(view)
        got[nm] = miss
        known = set(KNOWN_PIN_METAL_GAP.get(view.name, ()))
        if set(miss) - known:
            unreg.append((view.name, sorted(set(miss) - known)))
        if known - set(miss):
            stale.append((view.name, sorted(known - set(miss))))
        if not (set(miss) - known) and not (known - set(miss)):
            matched.append(view.name)
    return {"got": got, "unregistered": unreg, "stale": stale,
            "matched": sorted(matched),
            "n_missing_total": sum(len(v) for v in got.values()),
            "ok": not unreg and not stale}


# ═══════════════════════════════════════════════════════════════════════════
# ⑦ 自检（供门禁与探针；不含算法，只做结构一致性）
# ═══════════════════════════════════════════════════════════════════════════
def roundtrip_ok(cell) -> dict:
    """`Cell → CellView → Cell` 是否**逐位**相等（往返双射）。"""
    view = cellview_from_dcells(cell)
    back = cell_to_dcells(view)
    same_geom = ([(r.layer, r.x0, r.y0, r.x1, r.y1) for r in cell.rects]
                 == [(r.layer, r.x0, r.y0, r.x1, r.y1) for r in back.rects])
    same_pin = ({k: (v.layer, v.x0, v.y0, v.x1, v.y1) for k, v in cell.pins.items()}
                == {k: (v.layer, v.x0, v.y0, v.x1, v.y1) for k, v in back.pins.items()})
    same_size = (cell.w, cell.h) == (back.w, back.h)
    same_dev = [tuple(d) for d in (cell.devices_expected or [])] == \
               [tuple(d) for d in (back.devices_expected or [])]
    return {"ok": same_geom and same_pin and same_size and same_dev,
            "geom": same_geom, "pins": same_pin, "size": same_size, "devices": same_dev,
            "n_shapes": len(cell.rects)}

def model_self_check() -> dict:
    """模型层自检：几何校验 + 单位契约 + 往返 + 结构同构（两套规则集）。"""
    from .ecore import dcells as CL
    from .ecore import dhdlib as HD

    out = {}
    # ① Rect 拒绝**非整数**坐标（真精度问题）
    try:
        Rect(23, 0.5, 0, 10, 10)
        out["rect_int"] = False
    except TypeError:
        out["rect_int"] = True
    # ①b Rect **归一化**「值为整数的 float」（上游 dcells 有 10 处 `70.0`），
    #    归一化无损 ⇒ 往返仍逐位一致；这条把「类型不统一」显式化而不是假装没看见
    m = Rect(23, 70.0, 0, 140.0, 70)
    out["rect_norm"] = (m.x0_nm == 70 and m.x1_nm == 140
                        and isinstance(m.x0_nm, int) and isinstance(m.x1_nm, int))
    # ② Rect 拒绝反向
    try:
        Rect(23, 10, 0, 0, 10)
        out["rect_order"] = False
    except ValueError:
        out["rect_order"] = True
    # ③ 往返：DEMO45 的 INV/NAND2 与 HD 的 INV/NAND2/DFF
    cases = {"INV_X1": CL.CELLS["INV_X1"](), "NAND2_X1": CL.CELLS["NAND2_X1"](),
             "INV_X1_HD": HD.build_inv_hd(), "NAND2_X1_HD": HD.build_nand2_hd(),
             "DFF_X1_HD": HD.build_dff_hd()}
    out["roundtrip"] = {k: roundtrip_ok(c)["ok"] for k, c in cases.items()}
    # ④ 结构同构：同一「单元视图」形状，两套规则集下字段齐全
    views = {k: cellview_from_dcells(c) for k, c in cases.items()}
    out["iso"] = {k: (bool(v.pins) and bool(v.shapes) and v.rail_y_nm is not None
                      and v.w_nm > 0 and v.h_nm > 0)
                  for k, v in views.items()}
    # ⑤ 引脚名集合（结构可比：DEMO45 与 HD 的 INV 都是 {A,Y,VDD,VSS}）
    out["pin_sets"] = {k: sorted(v.pin_names()) for k, v in views.items()}
    # ⑥ 障碍数 = 全量 − 引脚（派生量可复算）
    out["obstacles"] = {k: (len(v.obstacles()), len(v.shapes)) for k, v in views.items()}
    # ⑦ 引脚 ⇄ 金属 体检（已知缺口与登记一致）
    pm = pin_metal_report(cases)
    out["pin_metal"] = {"got": pm["got"], "unregistered": pm["unregistered"],
                        "stale": pm["stale"], "n_missing_total": pm["n_missing_total"]}
    out["all_ok"] = (out["rect_int"] and out["rect_norm"] and out["rect_order"]
                     and all(out["roundtrip"].values())
                     and all(out["iso"].values()) and pm["ok"])
    return out


if __name__ == "__main__":
    import json
    r = model_self_check()
    print(json.dumps(r, ensure_ascii=False, indent=1))
    raise SystemExit(0 if r["all_ok"] else 1)
