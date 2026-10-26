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
    t_pd = t_intr + k_drive · ln2 · R_on · C_load        （ln2 = 0.69，一阶 RC 的 50% 点）

单位约定：`R` 取 Ω、`C` 取 fF ⇒ `R·C = 1e-15 s = 1e-3 ps`。
⇒ `t_pd[ps] = t_intr + k_drive · 0.69 · r_on_ohm · load_ff · 1e-3`

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
    r_on_ohm: float = 5000.0          # Ω · 单管等效导通电阻（线性区）
    t_intr_ps: float = 2.0            # ps · 单元内在延时（自载翻转）
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

    # 单输入
    add("INV", 1, 2, (1, 0), n_series=1, k_drive=1.00, pins=("a",), family="inv")
    add("BUF", 1, 4, (0, 1), n_series=1, k_drive=1.00, pins=("a",), family="inv")
    # 基础双输入
    add("NAND2", 2, 4, (1, 1, 1, 0), n_series=2, k_drive=1.80, pins=("a", "b"), family="nand")
    add("NOR2", 2, 4, (1, 0, 0, 0), n_series=2, k_drive=2.40, pins=("a", "b"), family="nor")
    add("AND2", 2, 6, (0, 0, 0, 1), n_series=2, k_drive=2.10, pins=("a", "b"), family="and")
    add("OR2", 2, 6, (0, 1, 1, 1), n_series=2, k_drive=2.70, pins=("a", "b"), family="or")
    add("XOR2", 2, 12, (0, 1, 1, 0), n_series=3, k_drive=3.00, pins=("a", "b"), family="xor")
    add("XNOR2", 2, 12, (1, 0, 0, 1), n_series=3, k_drive=3.00, pins=("a", "b"), family="xor")
    # 复合
    add("MUX2", 3, 12, _t(lambda a, b, s: b if s else a),
        n_series=2, k_drive=1.60, pins=("a", "b", "s"), family="mux")
    add("AOI21", 3, 6, _t(lambda a, b, c: 0 if ((a and b) or c) else 1),
        n_series=3, k_drive=2.00, pins=("a", "b", "c"), family="aoi")
    add("OAI21", 3, 6, _t(lambda a, b, c: 0 if ((a or b) and c) else 1),
        n_series=3, k_drive=2.40, pins=("a", "b", "c"), family="oai")
    # 三输入
    add("NAND3", 3, 6, _t(lambda a, b, c: 0 if (a and b and c) else 1),
        n_series=3, k_drive=2.60, pins=("a", "b", "c"), family="nand")
    add("NOR3", 3, 6, _t(lambda a, b, c: 0 if (a or b or c) else 1),
        n_series=3, k_drive=3.40, pins=("a", "b", "c"), family="nor")
    add("AND3", 3, 8, _t(lambda a, b, c: 1 if (a and b and c) else 0),
        n_series=3, k_drive=2.90, pins=("a", "b", "c"), family="and")
    add("OR3", 3, 8, _t(lambda a, b, c: 1 if (a or b or c) else 0),
        n_series=3, k_drive=3.60, pins=("a", "b", "c"), family="or")
    # 时序
    c["DFF"] = Cell(name="DFF", n_in=2, n_tr=24, table=(), n_series=1,
                    k_drive=1.0, is_seq=True, pins=("d", "clk"), family="seq")
    # 常数
    add("TIEHI", 0, 2, (1,), n_series=1, k_drive=1.0, pins=(), family="tie")
    add("TIELO", 0, 2, (0,), n_series=1, k_drive=1.0, pins=(), family="tie")
    return c


CELLS = _mk()

#: 组合单元（不含 DFF / TIE）
COMB_CELLS = tuple(k for k, v in CELLS.items() if not v.is_seq and v.n_in > 0)

#: 技术映射的**基元集**：NAND2 + INV 是布尔完备的最小集（成本最低）
BASE_PRIMS = ("NAND2", "INV")


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


def cell_delay_ps(name: str, load_ff: float, tech: Tech = DEFAULT_TECH) -> float:
    """一阶 RC 延时：`t_intr + k·ln2·R·C_load`。"""
    c = CELLS[name]
    # Ω × fF = 1e-15 s = 1e-3 ps ⇒ 直接乘换算因子，**不得再乘 1e3**
    # （E34 第一版在这里多乘了 1e3，INV@4fF 报 13864 ps ⇒ 整个 STA 偏大 1000×）
    return tech.t_intr_ps + c.k_drive * LN2 * tech.r_on_ohm * load_ff * OHM_FF_TO_PS


def cell_area_um2(name: str, tech: Tech = DEFAULT_TECH) -> float:
    return CELLS[name].n_tr * tech.area_per_tr_um2


def cell_leak_nw(name: str, tech: Tech = DEFAULT_TECH) -> float:
    """漏电功率（nW）：`n_tr · I_leak · Vdd`，`I_leak` 以 nA 计 ⇒ nA·V = nW。"""
    return CELLS[name].n_tr * tech.ileak_na_per_tr * tech.vdd


def chain_golden_ps(cell_name: str, n_stage: int, load_ff: float,
                    tech: Tech = DEFAULT_TECH) -> float:
    """**解析金标**：N 级同构串联、负载恒定的总延时 = N × t_pd（串行代数相加）。

    🔴 这是 `dsta` 的绝对判据来源：STA 走图传播，本式走代数相乘，**两条独立路径**。
    任何「延时不可加」「深度算错」「路径漏一段」的缺陷都会让两者不等。
    """
    if n_stage < 0:
        raise ValueError("n_stage 必须 >= 0")
    return n_stage * cell_delay_ps(cell_name, load_ff, tech)


# ---------------------------------------------------------------------------
# 自检（门禁侧复算 · 不依赖任何外部语料）
# ---------------------------------------------------------------------------
def library_self_check(tech: Tech = DEFAULT_TECH) -> dict:
    """库的结构自检：真值表长度、拓扑锚一致、驱动系数与串联数同序。

    返回 dict，`ok` 为真才算通过。**这里刻意不做「延时数值是否合理」的判断** ——
    那是工艺标定问题，没有公开语料就不能机核（写进诚实边界，不假装能判）。
    """
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

    return {
        "ok": not problems,
        "problems": problems,
        "n_cells": len(CELLS),
        "n_comb": len(COMB_CELLS),
        "total_tr": sum(c.n_tr for c in CELLS.values()),
    }


DCELL_DISCLOSURE = {
    "route": "E34 · 数字控制壳自主建 · 第 0 层（自有标准单元库）",
    "family": "静态互补 CMOS · 单轨 · 单工艺角（tt）· 无多阈值/无低功耗单元",
    "absolute_anchor": "n_tr（晶体管数）是**拓扑必然**，可作绝对锚；面积/延时/漏电的工艺标定是一阶估计",
    "claimable": False,
    "claimable_reason": "面积/功耗/延时均由一阶模型给出（area_per_tr / r_on / ileak 无可核语料）⇒ MODEL_ESTIMATE，不作签核、不对外比绝对值",
    "not_included": "无标准单元版图（LEF/GDS）· 无多角 PVT · 无 OCV/AOCV · 无噪声/串扰 · 无 EM/IR · 无低功耗单元（电源门控/多阈值）",
    "verifiable": "真值表长度 · n_tr 拓扑公式 · k_drive 与 n_series 同序 · 金标 0 级恰为 0",
}
