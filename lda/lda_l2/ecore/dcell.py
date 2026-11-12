# -*- coding: utf-8 -*-
"""E34 · **自有标准单元库**（`lda/lda_l2/ecore/dcell.py` · D-209）。

══════════════════════════════════════════════════════════════════════════
定位：数字控制壳「自主建」的第 0 层 —— 没有单元库，综合器无处映射
══════════════════════════════════════════════════════════════════════════
E21 三条红线里第二条「数字链借不借」在 E34 由**人**裁决为「**自主建**」
（不借 Yosys / OpenROAD / 任何 GPL 或外部综合器）。代价是数字前端此前
**完全不存在**（不是「薄」而是「0」），收益是「C 级自主」对外口径不必改写。

本模块只负责最基本的一件事：**把「一个逻辑门」变成一个可计算的物理对象** ——
面积、延时、功耗、漏电、输入电容。后续 `dsynth` 拿它做技术映射，`dsta` 拿它做时序。

══════════════════════════════════════════════════════════════════════════
🔴🔴 判据第一原则：**绝对量级锚点必须来自「拓扑必然」，不能来自经验拟合**
══════════════════════════════════════════════════════════════════════════
`METHOD_NOTES` 的教训（293/294/296/299 四次）：**比值判据对量级错完全无能为力**。
若面积/延时全是可调系数，那么「把系数整体乘 1000」这类错误**任何比值判据都抓不住**。

⇒ 本库把**晶体管数 `n_tr`** 定为绝对锚，理由是它是**拓扑必然**而非拟合：

| 单元 | 拓扑 | n_tr | 为什么必然 |
|---|---|---|---|
| INV | 1 PMOS + 1 NMOS | 2 | 互补 CMOS 反相器的最小实现 |
| NAND2 | 2 并联 PMOS + 2 串联 NMOS | 4 | 每个输入需要一个 P 和一个 N |
| NOR2 | 2 串联 PMOS + 2 并联 NMOS | 4 | 同上（对偶） |
| NAND3 / NOR3 | 3+3 | 6 | 同上 |
| AND2 / OR2 | 基门 + INV | 6 | 非反相输出必须再加一级 |
| AND3 / OR3 | NAND3/NOR3 + INV | 8 | 同上 |
| AOI21 | 2 串联 P 支路 + 1 并联 P + 2 串 N + 1 N | 6 | 复合门：`~(ab+c)` |
| OAI21 | 对偶 | 6 | `~(a+b)c` |
| XOR2 / XNOR2 | 全互补 12T | 12 | 静态 CMOS XOR 的标准实现 |
| MUX2 | 2 TG + INV（或 12T 全 CMOS） | 12 | 取保守的全 CMOS 实现 |
| DFF | 2 级锁存器 + 输出缓冲 | 24 | 主从 D 触发器（每级 ~11T + 缓冲） |

这些数的**唯一可机核性质**：`n_tr` 与「输入个数 × 2 + 反相级数 × 2」的拓扑公式一致，
且**串联器件数 `n_series` 与驱动劣化系数 `k_drive` 必须同序**（见 `library_self_check`）。
⇒ 任何人把 NAND2 的 `n_tr` 改成 40，面积立刻偏 10×，而**绝对锚判据当场打红**。

⚠️ **本条锚只能锁住「相对拓扑」，锁不住「工艺绝对标定」**：`area_per_tr_um2`、
`r_on_ohm`、`ileak_na_per_tr` 都是**一阶估计**，误差可达 ±factor 2。
⇒ 凡由它们算出的面积/功耗一律 `claimable=False`（`MODEL_ESTIMATE`），
**永不作签核**，永不与任何外部芯片比绝对数值。这是 E21 三档口径的直接延伸。

══════════════════════════════════════════════════════════════════════════
延时模型（一阶 RC + 内在项）
══════════════════════════════════════════════════════════════════════════
    t_pd = ln2 · R_cell · (C_self + C_load)              （ln2 = 0.69，一阶 RC 的 50% 点）
    R_cell = max( s_n·ρ_n·L/W_n , s_p·ρ_p·L/W_p )

⇒ **两项都 ∝ `R_cell`**：`C_self`（自载）与 `C_load`（扇出）只差电容，没有“常数延时”。

单位约定：`R` 取 Ω、`C` 取 fF ⇒ `R·C = 1e-15 s = 1e-3 ps`。

🔴 **三次演进（每次只改一处、每次都必须有标定锚）**：

| 版本 | 公式 | 毛病 |
|---|---|---|
| ≤ v0.9.404 | `t_intr + k_drive·ln2·r_on·C_load` | `k_drive` 手填、`r_on` 与几何无关 ⇒ **对 W/L 零敏感** |
| v0.9.405 | `t_intr + ln2·R_cell·C_load` | 负载项几何化了，**自载项还是常数**（NAND3 的 R 是 INV 的 3 倍，延时却相同） |
| **v0.9.406** | `ln2·R_cell·(C_self + C_load)` | —— 本式；`C_self` 由 `t_intr_ps` 反解，**锚不变** |

⚠️ `C_self = 0.5771 fF` 是**旧常数所隐含的电容**，不是新测的器件数据。
`MU=0.40` / `ρ_p·ρ_n=2.5` / `r_on=5000 Ω` 也都是一阶估计 ⇒ 绝对延时仍 `claimable=False`。

🔴 **结构金标（`chain_golden_ps`）**：N 级**同构**单元串联、负载恒定 ⇒ 总延时**必然**
等于 `N · t_pd`（串行代数相加，不是 RSS —— 见 `timing.py` 的「时间要分拓扑相加」）。
这条在 `dsta` 里作为**解析金标判据**：STA 报的关键路径延时必须与它逐位相等（< 1e-12 相对误差）。
"""
from __future__ import annotations

from dataclasses import dataclass

LN2 = 0.6931471805599453

#: 单位换算：Ω·fF → ps（1 Ω × 1 fF = 1e-15 s = 1e-3 ps）
OHM_FF_TO_PS = 1e-3


@dataclass(frozen=True)
class Tech:
    """工艺参数（**全部是一阶估计** · 见模块 docstring 的诚实边界）。"""

    name: str = "lda28_est"
    vdd: float = 0.90                 # V · 供电
    cin_ff: float = 1.00              # fF · 每扇入引脚等效电容
    r_on_ohm: float = 5000.0          # Ω · **标定锚**：参考器件（300/50 nMOS）的导通电阻
    #: 🔴 v0.9.405：`ρ_p/ρ_n`（= `1/μ_p_over_n`）。电阻按 `R = ρ·L/W` 算之后，这是
    #: 唯一还需要假设的**器件**量。写成「比值」而不是 μ，是为了让它的物理方向与
    #: `Q0` 的「×1.05 扰动」一致（比值变大 ⇒ 上拉更弱 ⇒ 必然进延时，可判活）。
    r_sheet_p_over_n: float = 2.5
    #: 🔴 v0.9.406：**标定锚** —— 参考单元（INV，`R = r_on`）的自载延时。
    #: 它不再「给所有单元用同一个值」，而是反解出 `C_self`（`dcell.c_self_ff`），
    #: 再由 `t_intr(cell) = ln2·R_cell·C_self` 逐单元算出 ⇒ `t_intr ∝ R`。
    t_intr_ps: float = 2.0
    area_per_tr_um2: float = 0.040    # µm²/管 · 一阶（含布线余量）
    ileak_na_per_tr: float = 0.05     # nA/管 · 室温漏电
    t_setup_ps: float = 6.0           # ps · DFF 建立时间
    t_hold_ps: float = 1.0            # ps · DFF 保持时间
    t_clk_q_ps: float = 10.0          # ps · DFF clk→Q


DEFAULT_TECH = Tech()


@dataclass(frozen=True)
class Cell:
    """一个标准单元。

    `table[i]` 为真值表，索引 `i` 的第 `(n_in-1-j)` 位 = 第 `j` 个 pin 的取值
    ⇒ **pin0 是最高位**。`n_in == 0` 时 `table` 长度为 1（TIEHI/TIELO）。
    """

    name: str
    n_in: int
    n_tr: int
    table: tuple
    n_series: int = 1
    k_drive: float = 1.0
    is_seq: bool = False
    pins: tuple = ()
    family: str = ""
    #: ── W/L 数据层（v0.9.403 · 新开一批）────────────────────────────────────
    #: 沟道宽度（nm）。`0.0` = **未知**，出处见 `wl_src`。
    #: 🔴 这是**数据**不是模型：宽度由版图/单元高度预算决定，不由拓扑推导。
    w_n_nm: float = 0.0
    w_p_nm: float = 0.0
    #: 栅长（nm）。同一库同一 flavor 下全库一致，但仍逐单元登记
    #: （将来若加 L 变体单元，这里就是唯一落点）。
    l_nm: float = 0.0
    #: W/L 的**出处等级**（取值见 `WL_SRC`）。🔴 没有实测就必须写 `UNKNOWN`，
    #: 不允许用「推导出来的」冒充实测。
    wl_src: str = "UNKNOWN"
    #: v0.9.408：**版图单元名**（`dcells.CELLS` 的键，即 `NOR2` → `NOR2_X1`）。
    #: 空串 = 本单元还没有版图 ⇒ 面积代价不可算。这是「数据层说它有实测」
    #: 与「几何层真的能建出来」之间唯一的那根线，两边必须机核对拍。
    layout: str = ""

    @property
    def area_um2_est(self) -> float:
        return self.n_tr * DEFAULT_TECH.area_per_tr_um2


def _t(*specs) -> tuple:
    """按 pin 顺序（pin0 为 MSB）生成真值表。`specs` 是 n_in 个 lambda 组成的函数。"""
    fn = specs[0]
    n = len(fn.__code__.co_varnames)
    return tuple(1 if fn(*((i >> (n - 1 - j)) & 1 for j in range(n))) else 0
                 for i in range(1 << n))


# ---------------------------------------------------------------------------
# 单元定义（顺序固定 ⇒ 技术映射的确定性依赖它）
# ---------------------------------------------------------------------------
def _mk() -> dict:
    c = {}

    def add(name, n_in, n_tr, table, **kw):
        c[name] = Cell(name=name, n_in=n_in, n_tr=n_tr, table=table, **kw)

    # ── W/L 数据层的两个常量（**数据，不是拟合**）───────────────────────────
    #: 晶体管宽度 = `dcells` 里 DIFF 区的**高度**（沟道宽沿竖直方向）。
    #: 🔴 v0.9.404：布局已按**平衡反相器**重画（`w_p/w_n = 1/μ = 2.5`）⇒
    #: NMOS **300 nm**、PMOS **750 nm**。此前是 1:1（pMOS 未加宽），那正是
    #: 「手填 k 表与几何不相容」的根源（见 v0.9.403 的上限定理）。
    W_NM = 300.0
    W_PM = 750.0
    #: 栅长 = `dcells.RULES["poly_w"]`（50 nm）。与 DIFF 高度不同量纲，不要混。
    L_NM = 50.0
    #: 有真实版图的单元 ⇒ 它们的 W/L 是 **LAYOUT（实测）**；
    #: 其余 15 个沿用同一构造常量，属 **RULE_CONSTANT（未验证）**。
    #: 🔴 v0.9.408 加入 `NOR2`：它的版图是 `dcells.build_nor2`，与 NAND2 **同尺寸**
    #: （980×1950）—— 这是刻意约束，超出就会把 `dpnr` 的行高预算顶上去、主链作废。
    LAYOUT_CELLS = ("INV", "NAND2", "NOR2")

    def _wl(name, **kw):
        src = "LAYOUT" if name in LAYOUT_CELLS else "RULE_CONSTANT"
        lay = ("%s_X1" % name) if name in LAYOUT_CELLS else ""
        return dict(w_n_nm=W_NM, w_p_nm=W_PM, l_nm=L_NM, wl_src=src, layout=lay, **kw)

    # 单输入
    add("INV", 1, 2, (1, 0), n_series=1, k_drive=1.00, pins=("a",), family="inv",
        **_wl("INV"))
    add("BUF", 1, 4, (0, 1), n_series=1, k_drive=1.00, pins=("a",), family="inv",
        **_wl("BUF"))
    # 基础双输入
    add("NAND2", 2, 4, (1, 1, 1, 0), n_series=2, k_drive=1.80, pins=("a", "b"),
        family="nand", **_wl("NAND2"))
    add("NOR2", 2, 4, (1, 0, 0, 0), n_series=2, k_drive=2.40, pins=("a", "b"),
        family="nor", **_wl("NOR2"))
    add("AND2", 2, 6, (0, 0, 0, 1), n_series=2, k_drive=2.10, pins=("a", "b"),
        family="and", **_wl("AND2"))
    add("OR2", 2, 6, (0, 1, 1, 1), n_series=2, k_drive=2.70, pins=("a", "b"),
        family="or", **_wl("OR2"))
    add("XOR2", 2, 12, (0, 1, 1, 0), n_series=3, k_drive=3.00, pins=("a", "b"),
        family="xor", **_wl("XOR2"))
    add("XNOR2", 2, 12, (1, 0, 0, 1), n_series=3, k_drive=3.00, pins=("a", "b"),
        family="xor", **_wl("XNOR2"))
    # 复合
    add("MUX2", 3, 12, _t(lambda a, b, s: b if s else a),
        n_series=2, k_drive=1.60, pins=("a", "b", "s"), family="mux", **_wl("MUX2"))
    add("AOI21", 3, 6, _t(lambda a, b, c: 0 if ((a and b) or c) else 1),
        n_series=3, k_drive=2.00, pins=("a", "b", "c"), family="aoi", **_wl("AOI21"))
    add("OAI21", 3, 6, _t(lambda a, b, c: 0 if ((a or b) and c) else 1),
        n_series=3, k_drive=2.40, pins=("a", "b", "c"), family="oai", **_wl("OAI21"))
    # 三输入
    add("NAND3", 3, 6, _t(lambda a, b, c: 0 if (a and b and c) else 1),
        n_series=3, k_drive=2.60, pins=("a", "b", "c"), family="nand",
        **_wl("NAND3"))
    add("NOR3", 3, 6, _t(lambda a, b, c: 0 if (a or b or c) else 1),
        n_series=3, k_drive=3.40, pins=("a", "b", "c"), family="nor", **_wl("NOR3"))
    add("AND3", 3, 8, _t(lambda a, b, c: 1 if (a and b and c) else 0),
        n_series=3, k_drive=2.90, pins=("a", "b", "c"), family="and", **_wl("AND3"))
    add("OR3", 3, 8, _t(lambda a, b, c: 1 if (a or b or c) else 0),
        n_series=3, k_drive=3.60, pins=("a", "b", "c"), family="or", **_wl("OR3"))
    # 时序
    c["DFF"] = Cell(name="DFF", n_in=2, n_tr=24, table=(), n_series=1,
                    k_drive=1.0, is_seq=True, pins=("d", "clk"), family="seq",
                    **_wl("DFF"))
    # 常数
    add("TIEHI", 0, 2, (1,), n_series=1, k_drive=1.0, pins=(), family="tie",
        **_wl("TIEHI"))
    add("TIELO", 0, 2, (0,), n_series=1, k_drive=1.0, pins=(), family="tie",
        **_wl("TIELO"))
    return c


CELLS = _mk()

#: 组合单元（不含 DFF / TIE）
COMB_CELLS = tuple(k for k, v in CELLS.items() if not v.is_seq and v.n_in > 0)

#: 技术映射的**基元集**：NAND2 + INV 是布尔完备的最小集（成本最低）
BASE_PRIMS = ("NAND2", "INV")


# ---------------------------------------------------------------------------
# W/L 数据层（v0.9.403）—— **数据出处，不是模型**
# ---------------------------------------------------------------------------
#: 出处等级（**只允许这三档**；没有实测就必须写 `UNKNOWN`）
WL_SRC = {
    "LAYOUT": "从版图 DIFF 矩形实测（`dcells` 真实几何，可逐位对拍）",
    "RULE_CONSTANT": "沿用同一构造常量（未逐单元验证 —— 这些单元还没有版图）",
    "UNKNOWN": "未知（未建模）",
}


def wl_table() -> dict:
    """逐单元的 W/L + 出处。**这是数据视图，不做任何推导**。

    设计意图：让「有实测」与「沿用常量」在数据层就分开，
    而不是等到比偏差时才用一句「假设」混过去。
    """
    out = {}
    for name, c in CELLS.items():
        out[name] = {
            "w_n_nm": c.w_n_nm, "w_p_nm": c.w_p_nm, "l_nm": c.l_nm,
            "src": c.wl_src, "family": c.family,
            "aspect_n": (c.w_n_nm / c.l_nm) if c.l_nm else 0.0,
            "aspect_p": (c.w_p_nm / c.l_nm) if c.l_nm else 0.0,
            "pn_ratio": (c.w_p_nm / c.w_n_nm) if c.w_n_nm else 0.0,
        }
    return out


def wl_provenance_summary() -> dict:
    """出处分布：`LAYOUT` 只有 3 个 —— 这个数必须如实，不能四舍五入成「都有」。"""
    cnt = {}
    for c in CELLS.values():
        cnt[c.wl_src] = cnt.get(c.wl_src, 0) + 1
    return {
        "n_cells": len(CELLS),
        "by_src": cnt,
        "n_measured": cnt.get("LAYOUT", 0),
        "measured_cells": sorted(n for n, c in CELLS.items() if c.wl_src == "LAYOUT"),
        "note": ("🔴 `LAYOUT` 之外一律**不是实测**：它们沿用同一构造常量，"
                 "没有版图可对拍。所以「全库 W=300」这句话里只有 3 个单元是证据，"
                 "另外 15 个是**规则外推**。"),
    }


# ---------------------------------------------------------------------------
# 上拉/下拉拓扑 + 电阻（v0.9.405 · `R = ρ·L/W`）
# ---------------------------------------------------------------------------
#: 🔴 **拓扑表归 `dcell`**（这是单元数据，不是判定逻辑）。
#: `(串联数, 并联数)`；`"n"` = 随 `n_in` 变。v0.9.405 从 `dkdrive` 搬过来 ——
#: 电阻要按「串联叠加 + 并联不折减（最坏路径）」算，那需要这张表；两处各存一份必漂。
STRUCT = {
    "inv": dict(pd=(1, 1), pu=(1, 1)),
    "nand": dict(pd="n", pu=(1, "n")),
    "nor": dict(pd=(1, "n"), pu="n"),
    "and": dict(pd="n", pu=(1, "n")),
    "or": dict(pd=(1, "n"), pu="n"),
    "aoi": dict(pd=(2, 1), pu=(2, 1)),
    "oai": dict(pd=(2, 1), pu=(2, 1)),
    "xor": dict(pd=(3, 1), pu=(2, 2)),
    "mux": dict(pd=(2, 1), pu=(2, 2)),
    "seq": dict(pd=(1, 1), pu=(1, 1)),
    "tie": dict(pd=(1, 1), pu=(1, 1)),
}

#: 标定锚：`Tech.r_on_ohm` 指的是**这个尺寸**的 nMOS（= 本库所有单元用的尺寸）
R_REF_W_NM = 300.0
R_REF_L_NM = 50.0


def series_counts(c: "Cell") -> tuple:
    """(下拉串联数, 上拉串联数) —— **最坏路径**口径。

    🔴 并联**不折减**：最坏情况下并联支路只有一路导通。把并联当受益是拿「典型值」
    冒充「最坏值」（`dkdrive.k_shape` 用的是受益口径，两者不可混用）。
    """
    st = STRUCT[c.family]
    out = []
    for spec in (st["pd"], st["pu"]):
        if spec == "n":
            out.append(float(c.n_in))
        else:
            out.append(float(c.n_in) if spec[0] == "n" else float(spec[0]))
    return out[0], out[1]


def r_sheet_ohm_sq(tech: Tech | None = None) -> tuple:
    """(ρ_n, ρ_p) —— 由标定锚反解。**`r_on_ohm` 是「参考器件 300/50 的 R」**，
    所以 `ρ_n = r_on · W/L`，于是任何 300/50 的 nMOS 都恰好回到 `r_on`。"""
    tech = tech or DEFAULT_TECH
    rho_n = tech.r_on_ohm * R_REF_W_NM / R_REF_L_NM
    return rho_n, rho_n * tech.r_sheet_p_over_n


def r_side_ohm(c: "Cell", tech: Tech | None = None,
               w_p_nm: float | None = None) -> tuple:
    """(下拉电阻, 上拉电阻) —— `R = 串联数 · ρ · L/W`（Ω）。

    `w_p_nm` 只用于**反事实**（把 p 侧退回某个宽度），默认取单元自己的 `w_p_nm`。
    🔴 反事实必须走**同一个函数**：另写一份「1:1 版」的实现必然与主式漂。
    """
    tech = tech or DEFAULT_TECH
    wp = c.w_p_nm if w_p_nm is None else float(w_p_nm)
    if not (c.l_nm and c.w_n_nm and wp):
        raise ValueError("单元 %s 缺 W/L 数据（`wl_src`=%s）" % (c.name, c.wl_src))
    rho_n, rho_p = r_sheet_ohm_sq(tech)
    sn, sp = series_counts(c)
    return (sn * rho_n * c.l_nm / c.w_n_nm,
            sp * rho_p * c.l_nm / wp)


def cell_r_ohm(name: str, tech: Tech | None = None,
               w_p_nm: float | None = None) -> float:
    """单元的**最坏路径等效导通电阻**（Ω）= `max(下拉, 上拉)`。

    🔴 这是 `k_drive` 被几何取代的落点：`k_drive ≡ R_cell / R_INV`，
    而 `R_INV` 在平衡版图下恰好等于 `Tech.r_on_ohm`（标定锚自洽）。
    """
    return max(*r_side_ohm(CELLS[name], tech, w_p_nm))


# ---------------------------------------------------------------------------
# pMOS 平衡的**收益结构**（v0.9.407）
# ---------------------------------------------------------------------------
#: 🔴 **pMOS 加宽只在「上拉侧是瓶颈」时才有用**。这个比例决定了收益上限。
#: 平衡版图把 p 侧单位电阻做成 `ρ_p·L/W_p = r_on`（= n 侧单位），
#: 1:1 版图则是 `ρ_p·L/W_n = r_on·(ρ比)`。两者之比就是**逐单元收益**。
DOMINANCE_PULLUP = "PULLUP"
DOMINANCE_PULLDOWN = "PULLDOWN"
DOMINANCE_BALANCED = "BALANCED"


def sizing_dominance(c: "Cell", tech: Tech | None = None) -> str:
    """**哪一侧限制了这个单元**：`PULLUP` / `PULLDOWN` / `BALANCED`。

    只看当前（平衡）版图：`R = max(R_pd, R_pu)`。
    `PULLUP` 意味着「再宽一点还能快」，`PULLDOWN` 意味着「加宽 p 侧完全没用」。
    """
    rn, rp = r_side_ohm(c, tech)
    if abs(rp - rn) <= 1e-9 * max(rn, rp):
        return DOMINANCE_BALANCED
    return DOMINANCE_PULLUP if rp > rn else DOMINANCE_PULLDOWN


def pmos_sizing_gain(c: "Cell", tech: Tech | None = None) -> float:
    """**逐单元收益**：把 p 侧退回 1:1（`w_p = w_n`）后 `R` 变成当前的几倍。

    ⇒ 等于「平衡版图在这一颗单元上省下的电阻倍数」。
    1.0 = 完全没用（下拉主导）；2.5 = 拿满（上拉主导且 p/n 比 = 2.5）。

    🔴 与 `sizing_dominance` 配对看：`PULLDOWN` 但收益 > 1 是可能的 ——
    因为 1:1 会把上拉侧**顶成**瓶颈（NAND2：1.25×）。这正是「平衡」的意义。
    """
    r_bal = cell_r_ohm(c.name, tech)
    r_11 = cell_r_ohm(c.name, tech, w_p_nm=c.w_n_nm)
    return r_11 / r_bal


def c_self_ff(tech: Tech | None = None) -> float:
    """单元的**自载电容**（fF）—— 由 `t_intr_ps` 反解，不是新数据。

    🔴 v0.9.406 的关键一步：`t_intr` 原来是**一个常数给所有单元**。
    这在物理上不自洽 —— `t_intr ≈ ln2·R·C_self`，而 `R` 对 NAND3 是 INV 的 3 倍，
    自载延时凭什么是同一个 2.0 ps？

    本函数把它翻译成几何形式：**保持 `t_intr` 对参考单元（INV，`R = r_on`）仍恰好 2.0 ps**，
    于是 `C_self = t_intr_ps/(ln2·r_on)` = **0.5771 fF**（= 0.5771·cin）。
    这不是新测得的器件数据，是**旧常数所隐含的那个电容** —— 写成电容只为了让它能
    跟着 `R` 缩放（电容不随驱动强度变，延时随 `R` 变）。
    """
    tech = tech or DEFAULT_TECH
    return tech.t_intr_ps / (LN2 * tech.r_on_ohm * OHM_FF_TO_PS)


def t_intr_ps_for(name: str, tech: Tech | None = None) -> float:
    """单元的**内在延时**（自载翻转，ps）= `ln2 · R_cell · C_self`。

    ⇒ `t_intr ∝ R`：INV 2.0 / NAND2 4.0 / NAND3 6.0 ps。串联级数越多，越慢（物理上对）。
    """
    tech = tech or DEFAULT_TECH
    return LN2 * cell_r_ohm(name, tech) * c_self_ff(tech) * OHM_FF_TO_PS


def cell(name: str) -> Cell:
    return CELLS[name]


def eval_cell(name: str, ins) -> int:
    """按真值表求值（组合单元）。`ins` 为 pin 顺序的 0/1 序列。"""
    c = CELLS[name]
    if c.is_seq:
        raise ValueError("eval_cell 不适用于时序单元 " + name)
    idx = 0
    for b in ins:
        idx = (idx << 1) | (1 if b else 0)
    return c.table[idx]


def cell_delay_ps(name: str, load_ff: float, tech: Tech | None = None,
                  w_p_nm: float | None = None) -> float:
    """一阶 RC 延时：`ln2 · R_cell · (C_self + C_load)` —— **两项都 ∝ R**。

    🔴 v0.9.406 **改口**（`t_intr` 几何化）。三步演进，每一步都只改一处、都必须有锚：
      · v0.9.404 `t_intr + k_drive·ln2·r_on·C_load` —— 延时对 W/L 零敏感；
      · v0.9.405 `t_intr + ln2·R_cell·C_load` —— 负载项几何化了，但**自载项还是常数**；
      · v0.9.406 `ln2·R_cell·(C_self + C_load)` —— 自载项也几何化。

    为什么必须改：`t_intr` 是一个常数给所有单元，而 `R` 对 NAND3 是 INV 的 3 倍
    ⇒ 「自载延时相同」在物理上不成立。本批把这个**内部矛盾**消掉。

    🔴 **标定锚不变**：`C_self` 由 `t_intr_ps` 反解（= 0.5771 fF），所以
    `t_intr(INV) = 2.0 ps` **逐位不变**，INV 的延时与 v0.9.405 **完全一致**。
    整个变化可归因到一件事：**k>1 的单元变慢了**（NAND2 +2 ps/级）。

    🔴 `w_p_nm`（v0.9.408）：**反事实宽度**。给定时算「p 侧退回该宽度」的延时，
    与 `cell_r_ohm` 的同一个参数同源 —— 反事实必须走**同一个公式**，
    另写一份「1:1 版延时」的实现必然与主式漂。
    """
    # R5-fix：默认值在调用时取，不在 def 时绑定
    if tech is None:
        tech = DEFAULT_TECH
    # Ω × fF = 1e-15 s = 1e-3 ps ⇒ 直接乘换算因子，**不得再乘 1e3**
    # （E34 第一版在这里多乘了 1e3，INV@4fF 报 13864 ps ⇒ 整个 STA 偏大 1000×）
    return (LN2 * cell_r_ohm(name, tech, w_p_nm)
            * (c_self_ff(tech) + load_ff) * OHM_FF_TO_PS)


AREA_BASIS_LAYOUT = "LAYOUT_GEOMETRY"
AREA_BASIS_SYMBOLIC = "SYMBOLIC"


def area_basis(name: str) -> str:
    """该单元的面积**用哪一套口径**（v0.9.409）。

    🔴 这是对 `C1`（面积三套口径差 13.10×）的处置：不是「统一成一个数」，
    而是**让每颗单元自己说清用哪套**，并且**有版图的必须走几何**。

    · `LAYOUT_GEOMETRY`：有版图（`Cell.layout` 非空）⇒ `dcells` 真几何 w×h；
    · `SYMBOLIC`：无版图 ⇒ `n_tr × area_per_tr_um2`（一阶估计，**已知比几何小 13×**）。
    """
    return AREA_BASIS_LAYOUT if CELLS[name].layout else AREA_BASIS_SYMBOLIC


def cell_area_layout_um2(name: str) -> float:
    """该单元的**几何真值**（µm²，`dcells` 的 w×h）。无版图 ⇒ 抛错，不返回估计。"""
    c = CELLS[name]
    if not c.layout:
        raise ValueError("单元 %s 没有版图（`Cell.layout` 为空），无几何面积" % name)
    from . import dcells as _CL          # 惰性：`dcells` 不 import `dcell`，无环
    return _CL.cell_area_um2_at(c.layout)


def cell_area_um2(name: str, tech: Tech | None = None) -> float:
    """单元面积（µm²）——**符号口径**：`n_tr × area_per_tr_um2`。

    🔴🔴 **这个数比几何真值小 13 倍，且它仍是 `dsynth.area` / `dplac` 成本 /
    `dxcheck` / `ec_b3_signoff` 的输入**（v0.9.409 实测：INV 0.0800 vs 几何 1.0478）。

    为什么不直接改：改它会让 EC-B3 的四口径、EC-P12/P13/Q05/R01/R04 共 6 条判据
    一次全红 —— 那是**受控改口**（要重定 golden + 重生台账 + 全量），不属于
    「不改数字」的 F0 批次。⇒ 本批只做**强制声明口径**：

    · `area_basis(name)` 告诉调用方拿到的是哪一套；
    · `area_gap_report()` 把倍差**显式报出来**，让「差 13 倍」不再是一个没人看的注释。

    真正的归一排在 F5（受控改口，四项接线一起做）。
    """
    # R5-fix：默认值在调用时取，不在 def 时绑定
    if tech is None:
        tech = DEFAULT_TECH
    return CELLS[name].n_tr * tech.area_per_tr_um2


def area_gap_report() -> dict:
    """符号口径 vs 几何真值的**倍差**（只对有版图的单元）—— 让偏差可被看见。"""
    rows = {}
    for name, c in CELLS.items():
        if not c.layout:
            continue
        geo = cell_area_layout_um2(name)
        sym = cell_area_um2(name)
        rows[name] = {"symbolic_um2": sym, "layout_um2": geo,
                      "ratio": (geo / sym) if sym else None}
    ratios = [r["ratio"] for r in rows.values() if r["ratio"]]
    return {"by_cell": rows, "n_measured": len(rows),
            "ratio_min": min(ratios) if ratios else None,
            "ratio_max": max(ratios) if ratios else None,
            "note": ("符号口径系统性偏小；F5 受控改口前，凡用 `cell_area_um2` 的数字"
                     "都必须标 `basis=SYMBOLIC`")}


def cell_leak_nw(name: str, tech: Tech | None = None) -> float:
    """漏电功率（nW）：`n_tr · I_leak · Vdd`，`I_leak` 以 nA 计 ⇒ nA·V = nW。"""
    # R5-fix：默认值在调用时取，不在 def 时绑定
    if tech is None:
        tech = DEFAULT_TECH
    return CELLS[name].n_tr * tech.ileak_na_per_tr * tech.vdd


def chain_golden_ps(cell_name: str, n_stage: int, load_ff: float,
                    tech: Tech | None = None) -> float:
    """**解析金标**：N 级同构串联、负载恒定的总延时 = N × t_pd（串行代数相加）。

    🔴 这是 `dsta` 的绝对判据来源：STA 走图传播，本式走代数相乘，**两条独立路径**。
    任何「延时不可加」「深度算错」「路径漏一段」的缺陷都会让两者不等。
    """
    # R5-fix：默认值在调用时取，不在 def 时绑定
    if tech is None:
        tech = DEFAULT_TECH
    if n_stage < 0:
        raise ValueError("n_stage 必须 >= 0")
    return n_stage * cell_delay_ps(cell_name, load_ff, tech)


# ---------------------------------------------------------------------------
# 自检（门禁侧复算 · 不依赖任何外部语料）
# ---------------------------------------------------------------------------
def library_self_check(tech: Tech | None = None) -> dict:
    """库的结构自检：真值表长度、拓扑锚一致、驱动系数与串联数同序。

    返回 dict，`ok` 为真才算通过。**这里刻意不做「延时数值是否合理」的判断** ——
    那是工艺标定问题，没有公开语料就不能机核（写进诚实边界，不假装能判）。
    """
    # R5-fix：默认值在调用时取，不在 def 时绑定
    if tech is None:
        tech = DEFAULT_TECH
    problems = []

    # ① 真值表长度 = 2^n_in（时序单元表留空）
    for name, c in CELLS.items():
        if c.is_seq:
            if c.table:
                problems.append(("seq_cell_has_table", name))
            continue
        if len(c.table) != (1 << c.n_in):
            problems.append(("table_len", name, len(c.table), 1 << c.n_in))
        if len(c.pins) != c.n_in:
            problems.append(("pin_count", name, len(c.pins), c.n_in))

    # ② 拓扑锚：n_tr 必须等于「输入数×2 + 反相级×2」的拓扑公式
    for name, c in CELLS.items():
        if c.is_seq or c.n_in == 0:
            continue
        inv_stage = 1 if name in ("BUF", "AND2", "OR2", "AND3", "OR3") else 0
        if name in ("XOR2", "XNOR2", "MUX2"):
            expect = 12                      # 全互补实现，非公式族
        else:
            expect = 2 * c.n_in + 2 * inv_stage
        if c.n_tr != expect:
            problems.append(("n_tr_topology", name, c.n_tr, expect))

    # ③ 驱动劣化必须随串联器件数**单调不减**（物理必然：串联 = 电阻叠加）
    # 🔴 但**只能在族内比较**：跨族不可比 —— NOR 的串联器件是 PMOS（迁移率低），
    #    同一 n_series 下 NOR 族的 k_drive 必然大于 NAND 族。
    #    E34 第一版把全库按 n_series 排序统一比较 ⇒ 28 个假违规；
    #    这不是库错，是**判据把不可比对象放进了同一个序**。
    by_family = {}
    for nm, cc in CELLS.items():
        if not cc.is_seq and cc.n_in > 0:
            by_family.setdefault(cc.family, []).append(cc)
    for fam, items in sorted(by_family.items()):
        items = sorted(items, key=lambda x: (x.n_series, x.name))
        for i in range(1, len(items)):
            if items[i].k_drive < items[i - 1].k_drive - 1e-12:
                problems.append(("k_drive_monotone", fam,
                                 items[i - 1].name, items[i].name))

    # ③b 跨族**方向**判据（同样物理必然，两条独立方向）：
    #   · 同串联数下 NOR 族 > NAND 族（PMOS 迁移率 < NMOS）
    #   · 同串联数下 AND/OR 族 > NAND/NOR 族（多一级反相）
    for ns in (2, 3):
        for hi, lo in (("nor", "nand"), ("and", "nand"), ("or", "nor")):
            his = [x for x in by_family.get(hi, []) if x.n_series == ns]
            los = [x for x in by_family.get(lo, []) if x.n_series == ns]
            if his and los:
                if min(x.k_drive for x in his) <= max(x.k_drive for x in los):
                    problems.append(("family_order", hi, lo, ns))

    # ④ k_drive 必须 >= 1（不能比理想单管更快）
    for name, c in CELLS.items():
        if not c.is_seq and c.k_drive < 1.0:
            problems.append(("k_drive_floor", name, c.k_drive))

    # ⑤ 基元集必须布尔完备（NAND2 单独即完备，INV 提供反相）
    for p in BASE_PRIMS:
        if p not in CELLS:
            problems.append(("missing_prim", p))
    if CELLS["NAND2"].table != (1, 1, 1, 0):
        problems.append(("nand2_truth", CELLS["NAND2"].table))

    # ⑥ 金标自洽：0 级链延时恰为 0（「本应恰好为 0」的对照组）
    if chain_golden_ps("INV", 0, 1.0, tech) != 0.0:
        problems.append(("golden_zero", chain_golden_ps("INV", 0, 1.0, tech)))

    # ⑦ W/L 数据层自洽（v0.9.403）：**要么是正数，要么显式 UNKNOWN，不许留半截**
    for name, c in CELLS.items():
        if c.wl_src not in WL_SRC:
            problems.append(("wl_src_bad", name, c.wl_src))
        if c.l_nm <= 0.0:
            problems.append(("l_zero", name, c.l_nm))
        if c.w_n_nm < 0.0 or c.w_p_nm < 0.0:
            problems.append(("w_negative", name, c.w_n_nm, c.w_p_nm))
        if (c.w_n_nm == 0.0) != (c.wl_src == "UNKNOWN"):
            # 宽度未知 ⇔ 出处必须是 UNKNOWN。反过来：写了 UNKNOWN 就不许填宽度
            problems.append(("wl_unknown_mismatch", name, c.w_n_nm, c.wl_src))
        # 串联器件的栅长必须一致（同一 flavor 只有一个 L）
        if c.l_nm != CELLS["INV"].l_nm:
            problems.append(("l_inconsistent", name, c.l_nm, CELLS["INV"].l_nm))

    # ⑨ 自载项的**锚自洽 + 逐单元化**（v0.9.406）
    #    ① `t_intr(INV)` 必须回到锚 `t_intr_ps`（容差 1e-12：反解 `C_self` 有一次浮点往返）；
    #    ② `t_intr(cell)/t_intr(INV)` 必须**恰好**等于 `R_cell/R_INV` ⇒ `t_intr ∝ R`；
    #    ③ 至少要有一个单元的 `t_intr` **不等于**锚（否则「逐单元化」没发生）。
    _ti_inv = t_intr_ps_for("INV", tech)
    if abs(_ti_inv - tech.t_intr_ps) > 1e-12:
        problems.append(("t_intr_anchor", _ti_inv, tech.t_intr_ps))
    def _has_wl(c):
        return bool(c.w_n_nm and c.w_p_nm and c.l_nm)

    # 🔴 数据缺失**不是 ⑨ 的事**（⑦ 已负责报）。⑨ 若在这里抛错，会把
    #   「e34 的 C1 探针（改 n_tr 必须打红）」从**受控红**变成**崩溃** ——
    #   那正是本仓红线「判据不可定位 = 不可修」说的情形。
    for _n in ("NAND2", "NAND3", "NOR2", "XOR2"):
        if _n not in CELLS or not _has_wl(CELLS[_n]):
            continue
        _want = tech.t_intr_ps * (cell_r_ohm(_n, tech) / cell_r_ohm("INV", tech))
        if abs(t_intr_ps_for(_n, tech) - _want) > 1e-9:
            problems.append(("t_intr_not_prop_to_R", _n,
                             t_intr_ps_for(_n, tech), _want))
    _with_wl = [c for c in CELLS.values() if _has_wl(c)]
    if _with_wl and all(abs(t_intr_ps_for(c.name, tech) - tech.t_intr_ps) <= 1e-12
                        for c in _with_wl):
        problems.append(("t_intr_not_per_cell", "全部单元都等于锚 ⇒ 又退回常数"))

    # ⑧ W/L 的**内部一致性**：同一 family 内 p/n 宽度比必须一致
    #    （同一套布局规则生成 ⇒ 比例是族的属性，不是单元的属性。
    #      若哪天有人给某个单元单独改宽，这里会红 —— 那正是需要显式登记的改动）
    ratio_by_family = {}
    for name, c in CELLS.items():
        if c.wl_src == "UNKNOWN" or not c.w_n_nm:
            continue
        r = round(c.w_p_nm / c.w_n_nm, 6)
        ratio_by_family.setdefault(c.family, {}).setdefault(r, []).append(name)
    for fam, m in sorted(ratio_by_family.items()):
        if len(m) > 1:
            problems.append(("pn_ratio_inconsistent", fam, sorted(m)))

    return {
        "ok": not problems,
        "problems": problems,
        "n_cells": len(CELLS),
        "n_comb": len(COMB_CELLS),
        "total_tr": sum(c.n_tr for c in CELLS.values()),
        "wl": wl_provenance_summary(),
    }


DCELL_DISCLOSURE = {
    "route": "E34 · 数字控制壳自主建 · 第 0 层（自有标准单元库）",
    "family": "静态互补 CMOS · 单轨 · 单工艺角（tt）· 无多阈值/无低功耗单元",
    "absolute_anchor": "n_tr（晶体管数）是**拓扑必然**，可作绝对锚；面积/延时/漏电的工艺标定是一阶估计",
    "claimable": False,
    "claimable_reason": "面积/功耗/延时均由一阶模型给出（area_per_tr / r_on / ileak 无可核语料）⇒ MODEL_ESTIMATE，不作签核、不对外比绝对值",
    "not_included": "无标准单元版图（LEF/GDS）· 无多角 PVT · 无 OCV/AOCV · 无噪声/串扰 · 无 EM/IR · 无低功耗单元（电源门控/多阈值）",
    "verifiable": "真值表长度 · n_tr 拓扑公式 · k_drive 与 n_series 同序 · 金标 0 级恰为 0 · "
                  "W/L 出处分级（LAYOUT 的 3 个可与版图逐位对拍）",
    "wl_layer": {
        "added": "v0.9.403 · W/L 数据层（`w_n_nm` / `w_p_nm` / `l_nm` / `wl_src`）",
        "measured": "INV / NAND2 / NOR2（源自 `dcells` 的 DIFF 实测：W_n=300nm、W_p=750nm、"
                    "L=50nm，与版图矩形逐位对拍）",
        "assumed": "其余 15 个沿用同一构造常量（`RULE_CONSTANT`，**未验证**）",
        "not_claimed": ("① 宽度是**布局决策**，不是拓扑必然 —— 补 W/L 不会让 k_drive 变得可算，"
                        "只让它变得**可判**；② 全库 p/n = 2.5（平衡反相器尺寸），"
                        "但 `ρ_p/ρ_n = 2.5` 本身是**教科书假设**、无器件测量"
                        "（见 `dkdrive.implied_mu_report` 的反解区间）"),
    },
}
