# -*- coding: utf-8 -*-
"""E34 · **静态时序分析（STA）+ 面积/功耗**（`lda/lda_l2/ecore/dsta.py` · D-213）。

══════════════════════════════════════════════════════════════════════════
定位：回答「这颗控制壳最快能跑多快」—— 而且是**能机核的**回答
══════════════════════════════════════════════════════════════════════════
E17 只到「阵列节拍」；E34 第一次有真正的**数字路径**可以定时刻。
本模块做四件事：负载提取 → 到达时间传播 → 建立检查 → 关键路径回溯。

══════════════════════════════════════════════════════════════════════════
🔴🔴 绝对金标：N 级同构链必须精确等于 N × t_pd
══════════════════════════════════════════════════════════════════════════
`dcell.chain_golden_ps` 走**代数相乘**，本模块走**图传播 + max 归约**。
两条代码路径毫无共享 ⇒ 若 STA 漏了一段、把深度算错、或把「串行」当「并行」，
两者必然不等，且**判据是 `< 1e-12` 相对误差，不是 5% 容差**。

这是 E20（IR-drop 解析金标与 Thomas 算法差 3.8e-14）的同型做法：
**「通式必须退化为已实现的特例」，且用机器可查的等式而不是口头断言。**

三条独立路径（`sta_self_check` 全跑）：
    ① 图传播（本模块 `sta`）
    ② 逐级累加（`chain_golden_from_loads`）
    ③ 代数相乘（`dcell.chain_golden_ps`，恒定负载时）
    ⇒ 恒定负载下三者必须**逐位相等**。

══════════════════════════════════════════════════════════════════════════
⚠️ 本模块的诚实边界（全部 `claimable=False`）
══════════════════════════════════════════════════════════════════════════
- **无布局布线** ⇒ 走线电容为 0（只算扇入电容）⇒ 真实延时**必然更大**
- **无 buffer insertion / 无 sizing** ⇒ 大扇出直接被高估延时（不做驱动优化）
- **单工艺角（tt）· 无 OCV/AOCV · 无可变性建模** ⇒ 这不是签核时序，是**一阶估算**
- **保持时间检查是形式性的**：单角零偏斜下 hold 恒满足 ⇒ 本模块报 `hold_ok=True`
  但**明确声明它没有被真正检验**（`hold_checked=False`），不制造「验过了」的错觉
"""
from __future__ import annotations

from dataclasses import dataclass

from . import dcell as DC


@dataclass
class Timing:
    """STA 结果。所有时间单位 **ps**，面积 **µm²**，功耗 **nW**。"""

    load_ff: dict
    arrival_ps: dict
    comb_delay_ps: float
    t_clk_min_ps: object          # None = 无寄存器（纯组合）
    fmax_mhz: object              # None = 同上
    critical_path: tuple
    critical_from: str
    n_comb_gates: int
    n_dff: int
    area_um2: float
    leak_nw: float
    hold_ok: bool
    hold_checked: bool
    # ── v0.9.366：Liberty 延时桥（`lib=None` 时三项保持默认 ⇒ 既有数字逐位不变）──
    lib_used: bool = False              # 本次是否用了 Liberty 表
    lib_fallback_cells: tuple = ()      # 库里查不到/无表 ⇒ 回落闭式的单元名
    lib_clamped: int = 0                # 插值越界被**钳位**的次数（不外插）
    # ── v0.9.415（F3）：时钟口径三件事必须显式 ──
    t_clk_source: str = "topology"      # "topology"（派生）| "external"（外部 spec）
    hold_time_is_assumption: bool = False   # True ⇒ `hold_time_ps` 是假设不是测量
    n_hold_excluded: int = 0            # D 端到达 ≤0（由 primary input 直驱）⇒ 不参与 hold
    clock_skew_ps: object = None        # None = 没给 skew（未真检）；数 = 已用该 skew 判 hold


def loads_of(nl, port_load_ff: float = 0.0, tech=None,
             wire_load_ff: dict = None) -> dict:
    """每根网的**总负载电容**（fF）。

    🔴 E35 之前：走线电容 = 0（无 P&R ⇒ 诚实取 0，不编数）。
    🔴 E35 起：可选注入 `wire_load_ff[net] = 该网的走线电容（fF）`，
    由 `dextract` 根据真实布线线长算出。**零线时行为不变**（E34 三路径金标不受影响）。
    """
    # R5-fix：默认值在调用时取，不在 def 时绑定
    if tech is None:
        tech = DC.DEFAULT_TECH
    fan = {}
    for g in nl.gates:
        if g.cell == "DFF":
            continue                       # DFF 的 clk 引脚不计入组合负载
        for n in g.ins:
            if n == "CLK":
                continue
            fan[n] = fan.get(n, 0.0) + tech.cin_ff
    for nts in nl.outputs.values():
        for n in nts:
            fan[n] = fan.get(n, 0.0) + port_load_ff
    if wire_load_ff:
        for n, c in wire_load_ff.items():
            fan[n] = fan.get(n, 0.0) + float(c)
    return fan


#: `lib` 模式下输入 transition 的默认假设（ps）。**是假设，不是测量** ——
#: 合成样本库只给 `cell_rise/cell_fall`（不含 rise_transition），故不做 slew 传播。
_DEFAULT_SLEW_PS = 50.0


def lib_defaults(lib):
    """从 Liberty 抽**库级默认**（T4 数据契约）：`{pv, 转换时间, 输入电容}`。

    返回 `None` 表示「没给库」；**键缺 → 值为 None**（"库没写" ≠ 0）。

    🔴 单位换算只有一条假设：Liberty 的 `time_unit` 在本仓按 **ns** 解释（`to_model`
    早已如此）；`capacitive_load_unit` 按 **pf**。换库若改这两条，必须同步改这里
    —— 已在 `assumption` 里写明，不静默。
    """
    if lib is None:
        return None
    a = getattr(lib, "attrs", {}) or {}

    def _num(key):
        v = a.get(key)
        return float(v.num) if (v is not None and getattr(v, "tag", "") == "num") else None

    _mt_ns, _cin_pf = _num("default_max_transition"), _num("default_input_pin_cap")
    return {
        "library": getattr(lib, "name", None),
        "nom_voltage_v": _num("nom_voltage"),
        "nom_temperature_c": _num("nom_temperature"),
        "default_max_transition_ps": None if _mt_ns is None else _mt_ns * 1000.0,
        "default_input_pin_cap_ff": None if _cin_pf is None else _cin_pf * 1000.0,
        "unit_assumption": "time_unit=ns · capacitive_load_unit=pf（与 to_model 同口径）",
        "source": "liberty",
    }


def lib_map(lib):
    """`LibertyLibrary` → `{cell: CellView}`（**复用** `dliberty.to_model`，绝不另写解析）。

    延迟表布局由 dliberty 定：`(slew_ps, load_ff, delays_ps[slew][load])`。
    """
    from . import dliberty as DL

    return DL.to_model(lib)


def _bracket(vec, x: float):
    """在单调向量里找插值区间：返回 `(lo, hi, frac)`；端点退化时 `lo == hi`。"""
    n = len(vec)
    if n == 0:
        return 0, 0, 0.0
    if n == 1 or x <= vec[0]:
        return 0, min(1, n - 1), 0.0
    if x >= vec[-1]:
        return n - 2 if n >= 2 else 0, n - 1, 1.0
    for k in range(n - 1):
        if vec[k] <= x <= vec[k + 1]:
            span = vec[k + 1] - vec[k]
            return k, k + 1, (0.0 if span == 0 else (x - vec[k]) / span)
    return n - 2 if n >= 2 else 0, n - 1, 1.0


def interp_nldm(table, slew_ps: float, load_ff: float):
    """NLDM 双线性插值。返回 `(delay_ps, clamped)`。

    🔴 **越界钳位、不外插**：外插会给出无物理依据的延时（大负载时尤其危险）；
    钳位是确定性的，且调用方可数（`Timing.lib_clamped`）。
    """
    sl, ld, z = table
    s = min(max(float(slew_ps), sl[0]), sl[-1])
    l = min(max(float(load_ff), ld[0]), ld[-1])
    clamped = (s != float(slew_ps)) or (l != float(load_ff))
    s0, s1, fs = _bracket(sl, s)
    l0, l1, fl = _bracket(ld, l)
    v = (z[s0][l0] * (1.0 - fs) * (1.0 - fl)
         + z[s1][l0] * fs * (1.0 - fl)
         + z[s0][l1] * (1.0 - fs) * fl
         + z[s1][l1] * fs * fl)
    return float(v), clamped


def _delay_from_lib(lib_tables, cell: str, load_ff: float, slew_ps: float):
    """从 `{cell: CellView}` 取一条带表的 arc 求延时。返回 `(delay_ps|None, clamped)`。

    取**第一条有表的 arc**（`dliberty` 每 arc 只保留一张表：`cell_fall` 优先、否则
    `cell_rise`）—— 这是已知口径简化，不是「算了 rise 和 fall 再取大」。
    """
    cv = lib_tables.get(cell)
    if cv is None:
        return None, False
    for arc in getattr(cv, "arcs", ()) or ():
        t = getattr(arc, "table", None)
        if t:
            return interp_nldm(t, slew_ps, load_ff)
    return None, False


def sta(nl, tech=None, port_load_ff: float = 0.0,
        wire_load_ff: dict = None, lib=None, slew_ps: float = None,
        topo_sort: bool = False,
        skew_ps: float = None, t_clk_ps: float = None,
        hold_time_ps: float = 0.0) -> Timing:
    """静态时序（一阶）。`lib` 给 LibertyLibrary 时延时改查 NLDM 表，否则走闭式。

    🔴 **保护性约束**：`lib=None` 时走的是与历史**完全相同**的表达式
    `tin[k] + DC.cell_delay_ps(g.cell, load, tech)` ⇒ E34/E35 等既有数字逐位不变。
    `lib` 模式下：库里查不到该单元的**表** ⇒ 该单元回落闭式并记入
    `lib_fallback_cells`（不静默）；插值越界**钳位**（不外插）并计数 `lib_clamped`。

    🔴 `topo_sort=False`（默认）⇒ 完全沿用历史行为（按 `nl.gates` 书写顺序传播），
    既有调用与 E34/E35 金标**逐位不变**。`topo_sort=True` 时先用
    `dsynth.topo_order` 排序再传播 —— 供源文件顺序不保证拓扑序的网表（如 c17）使用；
    有组合环会直接抛错（fail-closed），不静默用旧值。

    🔴 **F3（v0.9.415）三个时钟口径参数**，全部默认 `None`/`0` ⇒ 既有调用逐位不变：

    · `t_clk_ps`：外部时钟 spec。给定时**直接用**（`t_clk_source="external"`），
      不再由 `@d` 端口 + `t_setup` 派生；`fmax` 跟着重算。
    · `skew_ps`：时钟偏斜。给定 ⇒ `hold_checked=True` 且 hold 按
      `min(D 端到达) > skew + hold_time` 真检；`None` ⇒ `hold_checked=False`（历史行为）。
      🔴 `hold_checked=True` 的含义**只是**「skew 已占用的窗口之外还有余量」，
      **不是**「与真库 hold 时间比对通过」。
    · `hold_time_ps`：hold 时间。**本仓没有任何 hold 数据** ⇒ 默认 `0.0` 是**假设**，
      由 `hold_time_is_assumption=True` 显式标注（`skew_ps=None` 时为 `False`，因为没用到）。
    · D 端到达 ≤0 的端点（由 primary input 直驱）**不参与** hold 判定，
      计入 `n_hold_excluded` —— 不用 `> 0` 硬凑成「恒真」。
    """
    # 🔴 R5-fix（v0.9.394）：默认值必须**在调用时**取，不在 `def` 时绑定。
    #   原签名 `tech=DC.DEFAULT_TECH` 在 import 时求值一次 ⇒ 之后换 Tech 实例
    #   主链（`ST.sta(nl, topo_sort=True)` 不传 tech）永远读旧值，参数看似"死"。
    #   改为 None 后取值，`DEFAULT_TECH` 未变时**逐位不变**（T1a 零变化实证：
    #   T1a 时点 base 43.490 不变；r_on×4 → 155.959、t_intr×4 → 61.490 两条手算吻合。
    #   （T2 起 base = 74.990 ps；v0.9.404 pMOS 加宽后 78.358 ps —— 数值变、关系不变。）
    if tech is None:
        tech = DC.DEFAULT_TECH
    load = loads_of(nl, port_load_ff, tech, wire_load_ff)
    arr = {}
    pred = {}
    lib_tables = lib_map(lib) if lib is not None else None
    _slew = _DEFAULT_SLEW_PS if slew_ps is None else float(slew_ps)
    fallback = []
    clamped = 0

    for (port, w) in nl.inputs:
        for i in range(w):
            # 🔴 网名**以 `nl.in_nets` 为准**（权威映射），`_inet` 只是 `dsynth` 的历史约定。
            #   v0.9.377：`dverilog.parse` 的网名是源文件里的 `n1`/`n3`…，不是 `in_n1_0`
            #   ⇒ 只认约定会让 `arr` 里根本没有这些网，随后 `arr[n]` 直接 KeyError
            #   （c17 实测）。两种网表的 `in_nets` 与约定**逐位相同**（dsynth 恒等已验证），
            #   故以 `in_nets` 优先对既有数字（E34/E35）无影响。
            n = (nl.in_nets or {}).get((port, i)) or _inet(port, i)
            if port.endswith("@q"):
                arr[n] = tech.t_clk_q_ps      # 时钟沿之后 Q 才稳定
            else:
                arr[n] = 0.0

    gates = nl.gates
    if topo_sort:
        from .dsynth import topo_order
        gates = topo_order(nl)
    for g in gates:
        if g.cell == "DFF":
            continue
        tin = [arr[n] for n in g.ins if n != "CLK"]
        if not tin:
            tin = [0.0]
        k = max(range(len(tin)), key=lambda j: tin[j])
        ins = [n for n in g.ins if n != "CLK"]
        ld = load.get(g.out, 0.0)
        d = None
        if lib_tables is not None:
            d, cl = _delay_from_lib(lib_tables, g.cell, ld, _slew)
            if d is None:
                fallback.append(g.cell)       # 库里没有 ⇒ 明确回落，不静默
            elif cl:
                clamped += 1
        if d is None:
            d = DC.cell_delay_ps(g.cell, ld, tech)
        arr[g.out] = tin[k] + d
        pred[g.out] = (g.cell, ins[k] if ins else None)

    # ---- 建立检查 ----
    d_bits = [n for n in nl.outputs if n.endswith("@d")]
    t_clk_min = None
    if d_bits:
        t_clk_min = 0.0
        for p in d_bits:
            for n in nl.outputs[p]:
                t_clk_min = max(t_clk_min, arr.get(n, 0.0) + tech.t_setup_ps)
    # 🔴 F3-3：外部时钟 spec 优先（给了就**不派生**）—— 默认 None ⇒ 逐位不变
    if t_clk_ps is not None:
        t_clk_min = float(t_clk_ps)
        t_clk_source = "external"
    else:
        t_clk_source = "topology"
    fmax = (1e6 / t_clk_min) if (t_clk_min and t_clk_min > 0) else None

    # ---- 组合延时（对外输出端口的最晚到达）----
    comb_out = [n for p, nts in nl.outputs.items() if not p.endswith("@d")
                for n in nts]
    comb_delay = max((arr.get(n, 0.0) for n in comb_out), default=0.0)

    # ---- 关键路径：从最晚的终点回溯 ----
    ends = list(comb_out) + [n for p in d_bits for n in nl.outputs[p]]
    if ends:
        end = max(ends, key=lambda n: arr.get(n, 0.0))
        path = [end]
        cur = end
        while cur in pred:
            cell, src = pred[cur]
            path.append(src)
            cur = src
        path.reverse()
        crit = tuple(path)
        crit_from = "input" if (cur and not cur.startswith("q_")) else "dff_q"
    else:
        crit, crit_from = (), "none"

    # ---- hold 真检（F3-2）：只有给了 skew 才检；不给 ⇒ 历史行为逐位不变 ----
    hold_ok = True
    hold_checked = False
    n_hold_excluded = 0
    if skew_ps is not None:
        hold_checked = True
        d_nets = [g.ins[0] for g in nl.gates if g.cell == "DFF" and g.ins]
        vals = [arr.get(n, 0.0) for n in d_nets]
        active = [v for v in vals if v > 0.0]
        n_hold_excluded = len(vals) - len(active)
        # 🔴 只对「真有到达时间」的端点判；被排除的端点不参与（不用 >0 硬凑恒真）
        hold_ok = all(v > float(skew_ps) + float(hold_time_ps) for v in active)

    return Timing(
        load_ff=load,
        arrival_ps=arr,
        comb_delay_ps=comb_delay,
        t_clk_min_ps=t_clk_min,
        fmax_mhz=fmax,
        critical_path=crit,
        critical_from=crit_from,
        n_comb_gates=nl.n_gates(),
        n_dff=nl.n_dff(),
        area_um2=nl.area_um2(tech),
        leak_nw=nl.leak_nw(tech),
        hold_ok=hold_ok,
        hold_checked=hold_checked,
        lib_used=lib_tables is not None,
        lib_fallback_cells=tuple(sorted(set(fallback))),
        lib_clamped=clamped,
        t_clk_source=t_clk_source,
        hold_time_is_assumption=(skew_ps is not None),
        n_hold_excluded=n_hold_excluded,
        clock_skew_ps=skew_ps,
    )


def _inet(port, bit):
    return ("q_%s_%d" % (port[:-2], bit)) if port.endswith("@q") \
        else ("in_%s_%d" % (port, bit))


# ═══════════════════════════════════════════════════════════════════════════
# T1b · S1a / S1c 最小约束层（**零数字变化**：只把"量尺"造出来，不改量出的数）
# ═══════════════════════════════════════════════════════════════════════════
# 🔴 为什么这一层值得单独存在：在此之前，仓库里**没有任何地方定义"周期应该多长"**，
#   于是"延时 78.358 ps"（T2 口径）这个数字**没有满足/不满足可言** —— 没有约束的数字无法
#   证伪，也无法在 T2 改几何后回答"是变好了还是变差了"。本层只做四件事：
#   把 `clock_period` / `max_fanout` / `max_transition` 由 `Tech` + 拓扑派生，
#   并给出两套口径的 `slack`（ideal / wired）—— **只给数，不给判决**。

#: 唯一扇出目标（U-1：S1a 的 `T_ref` 与 S1c 的 `max_fanout` 由**同一个数**派生，
#: 禁第二份定义）。预注册 = 3，依据是实测四组（legacy 口径）：
#: FO1 `−6.238 / −44.036`（全红）· FO3 `+31.192 / +18.655`（全绿）·
#: FO4 `+49.907 / +12.109`（全绿）；FO3 在 Q2 后翻转成 `+31.192 / −6.606`。
#: ⇒ 只有 FO3 在"改几何后才显现违例"，其余两组要么永远红、要么永远绿（无判别力）。
FO_TARGET = 3.0

#: T2 · S1b：**端口**扇出（一个输出端口驱动几个下游）。默认 1 ⇒ `port_load_ff = 1 fF`。
#: 🔴 旧口径把端口负载写死 0（"端口不驱动任何东西"），与 `FO_TARGET=3` 的口径不自洽
#: —— 引脚扇出算 3、端口算 0。补上它以后 ideal 30.953 → 37.192 ps。
FO_PORT = 1.0


def longest_path_gates(nl) -> list:
    """**拓扑最长路径**（按门数计）。由门级连接算，**不读时序**。

    🔴 为什么不能用到达时间找最长路径：那样 `T_ref` 与 `delay` **同源**，
    `slack = T_ref − delay` 就退化成自证（"用延时定义的周期当然容得下这个延时"），
    而这正是本仓反复踩过的"恒真判据"。拓扑只认 `ins`/`out`，与延时模型无关。

    DFF 是路径边界（`clk→Q` 之后重新起算），与 `sta` 的寄存器分隔口径一致；
    多驱动 / 组合环 ⇒ `topo_order` 直接抛（fail-closed，不静默猜一个顺序）。
    """
    from .dsynth import topo_order

    order = topo_order(nl)
    producer = {g.out: g for g in nl.gates}
    depth, prev = {}, {}
    for g in order:
        if g.cell == "DFF":
            depth[g.name], prev[g.name] = 1, None
            continue
        srcs = [producer[n] for n in g.ins if n in producer and n != "CLK"]
        if srcs:
            s = max(srcs, key=lambda x: depth.get(x.name, 1))
            depth[g.name] = depth.get(s.name, 1) + 1
            prev[g.name] = s.name
        else:
            depth[g.name], prev[g.name] = 1, None
    if not depth:
        return []
    by_name = {g.name: g for g in nl.gates}
    # 同深度取拓扑序里**最先**出现的那条（`max` 取首个极大）⇒ 结果确定、可复现
    cur = max(order, key=lambda g: depth[g.name])
    path = []
    while cur is not None:
        path.append(cur)
        p = prev.get(cur.name)
        cur = by_name.get(p) if p else None
    path.reverse()
    return path


def discriminates(slack_ideal_ps, slack_wired_ps) -> bool:
    """判别力**元**判据：`slack(ideal) > 0 > slack(wired)`。

    🔴 这不是签核判据，是"约束层有没有判别力"的判据：
    - 两侧都 >0 ⇒ 约束太松（改几何也看不出违例）⇒ 无判别力；
    - 两侧都 <0 ⇒ 约束太紧（永远违例）⇒ 无判别力。
    按规划 §3-DoD.2：**T1 只登记（legacy 上必不成立），T2 才裁决**。
    缺任一侧（`None`）按"无判别力"处理 —— 没算不等于有判别力。
    """
    if slack_ideal_ps is None or slack_wired_ps is None:
        return False
    return slack_ideal_ps > 0.0 > slack_wired_ps


def constraint_layer(nl, tech=None, fo_target=None,
                     comb_delay_ideal_ps=None,
                     comb_delay_wired_ps=None, lib=None) -> dict:
    """S1a + S1c：由 `Tech` + 拓扑派生约束量（**禁出现字面量**）。

    定义（规划 §3-S1）::

        T_ref = Σ_{i ∈ L_top} cell_delay(k_drive_i, FO_target · cin_ff)
        max_fanout     = FO_target                 （与 S1a 同源，U-1）
        max_transition = _DEFAULT_SLEW_PS           （**显式假设**，slew 不传播）
                         └ T4 起：给 `lib=` 则改取 Liberty `default_max_transition`
                           ⇒ `max_transition_is_assumption` 由 True **翻成 False**
                           （出处从"假设"变"数据"）。**数字可以不变**，语义必须变。
        slack(X)       = T_ref − delay(X)           （X ∈ {ideal, wired}）

    🔴 三条纪律：
    ① `slack` **不得**由 `delay` 派生（`slack = margin·delay` 恒正 ⇒ 自证）；
    ② 判据**不许**写 `slack ≥ 0`：T2 预注册 `wired slack = −6.606 ps` 必然违例，
       写 `≥0` 的唯一"解法"是调 `FO_target` 造假 ⇒ 本函数只给数，判决留 T2；
    ③ 无门 / 无网表 ⇒ 相应量为 `None`，**不是 0**（"没算"≠"零裕量"）。

    `dff_on_path` 显式给出，且 DFF 段（`clk→Q`）**不计入** `T_ref`：
    `t_clk_q_ps` 在当前网表（c17 纯组合）没有消费者、未标定；把它当 0 是隐式假设，
    当 `t_intr` 是错的 —— 故计入会使 `T_ref` 变成"编出来的数"。此边界随返回值同报。
    """
    # R5-fix 同款：默认值在调用时取，不在 def 时绑定
    if tech is None:
        tech = DC.DEFAULT_TECH
    fo = FO_TARGET if fo_target is None else float(fo_target)
    # 🔴 T4：转换时间上限的出处 —— 库给就用库，库不给仍是**假设**（不许假装有出处）
    _ld = lib_defaults(lib)
    _mt_lib = None if _ld is None else _ld.get("default_max_transition_ps")
    mt_ps = _DEFAULT_SLEW_PS if _mt_lib is None else float(_mt_lib)
    mt_is_asm = _mt_lib is None
    path = longest_path_gates(nl)
    load_ff = fo * tech.cin_ff
    comb = [g for g in path if g.cell != "DFF"]
    stages = [(g.name, g.cell, DC.cell_delay_ps(g.cell, load_ff, tech)) for g in comb]
    t_ref = sum(d for (_n, _c, d) in stages) if stages else None

    sl_i = None if (t_ref is None or comb_delay_ideal_ps is None) \
        else t_ref - float(comb_delay_ideal_ps)
    sl_w = None if (t_ref is None or comb_delay_wired_ps is None) \
        else t_ref - float(comb_delay_wired_ps)

    return {
        # ── S1a 时钟周期 ──
        "clock_period_ps": t_ref,
        "fo_target": fo,
        "load_per_stage_ff": load_ff,
        "n_stages": len(stages),
        "path": [g.name for g in path],
        "dff_on_path": sum(1 for g in path if g.cell == "DFF"),
        "path_basis": "拓扑最长路径（门级连接，按门数；**不读时序**）",
        # ── S1c 扇出 / 转换 ──
        "max_fanout": fo,
        "max_transition_ps": mt_ps,
        "max_transition_is_assumption": mt_is_asm,
        "max_transition_source": ("_DEFAULT_SLEW_PS" if mt_is_asm
                                  else "Liberty.default_max_transition"),
        # ── 两套口径的裕量（**只给数，不判满足**）──
        "slack_ideal_ps": sl_i,
        "slack_wired_ps": sl_w,
        "discriminates": discriminates(sl_i, sl_w),
        # ── 可追溯性：每个量的来源符号（禁字面量 DoD 的机核入口）──
        "sources": {
            "clock_period_ps": ["Tech.t_intr_ps", "Tech.r_on_ohm", "Tech.cin_ff",
                                "FO_TARGET", "Cell.w_n_nm", "Cell.w_p_nm",
                                "Cell.l_nm", "Tech.r_sheet_p_over_n", "LN2",
                                "OHM_FF_TO_PS"],
            "max_fanout": ["FO_TARGET"],
            "max_transition_ps": (["_DEFAULT_SLEW_PS"] if mt_is_asm else
                                  ["Liberty.default_max_transition"]),
            "slack_*": ["clock_period_ps", "comb_delay_ideal_ps",
                        "comb_delay_wired_ps"],
        },
        "assumptions": {
            "fo_target": "预注册 3（见 FO_TARGET 注释的四组实测）",
            "load_per_stage": "FO_target·cin_ff —— 每级按目标扇出计负载，非实际负载",
            "max_transition": ("slew 不传播，取 _DEFAULT_SLEW_PS 常数（假设，非测量）"
                               if mt_is_asm else
                               "取自 Liberty `default_max_transition`（数据，非假设）；"
                               "slew 仍不传播（本项是**上限值**的出处，不是 slew 计算）"),
            "dff": "DFF 段（clk→Q）不计入 T_ref：t_clk_q 在当前网表无消费者、未标定",
            "verdict": "本层不判满足；`discriminates` 只说明约束有没有判别力",
        },
        "not_included": "无时钟树 / 无偏斜 / 无多周期 / 无 IO 延时 / 无 keep-out；"
                        "周期是**一阶估计**，非时序签核",
        # ── T4 库级默认（**只报不改**：vdd/温度/输入电容要改它们会动 EM 与几何，另批）──
        "lib_defaults": _ld,
        "lib_ignored": (None if _ld is None else {
            "nom_voltage_v": "库写了但**未接线**：接它会改 EM 电流（i ∝ V）与功耗 ⇒ 另批",
            "nom_temperature_c": "库写了但**未接线**：接它会改 EM 温度标度 ⇒ 另批",
            "default_input_pin_cap_ff": "库写了但**未接线**：接它会改 all 负载与几何 ⇒ 另批",
        }),
        "claimable": False,
        "claimable_reason": "T_ref 由一阶 RC + 预注册扇出目标派生 ⇒ MODEL_ESTIMATE",
    }


# ---------------------------------------------------------------------------
# T4b：三角签核（ff / tt / ss）—— **零改口**，但暴露一条结构性局限
# ---------------------------------------------------------------------------
def signoff_corners(nl, wire_load_ff=None, port_load_ff=None, corners=None,
                    lib=None) -> dict:
    """把 `Tech` 按 corner 缩放后重算 `T_ref` / `ideal` / `wired` / `slack` 三组。

    corner 因子来自 `dsignoff.CORNERS = {名: (k_r, k_c)}`：**`r_on` 乘 `k_r`、`cin_ff` 乘 `k_c`**。
    （`dsignoff` 里同一对因子用于网级 RC 的 `(kr, kc)`；此处用于门级 `Tech` —— 两者口径一致。）

    🔴 **tt 必须逐位等于单点口径**：不给 corner 时主链算什么，`tt` 就必须是什么。
    这是本函数的**保护性约束**，也是「三角签核没有偷偷改口径」的唯一证据。

    🔴🔴 **结构性局限（必须与结果同报，不许藏）**：
    `T_ref` 由 `Tech + 拓扑 + FO_target` 派生，而 `delay` 也由 `Tech` 派生 ⇒ **两者同源**，
    按同一套 `(kr, kc)` 缩放时**部分相互抵消** ⇒ `slack` 对 corner 极不敏感
    （实测 c17：`T_ref` 散布 44.4%，而 `slack(wired)` 只从 −19.40 动到 −22.42，**3.02 ps**）。
    ⇒ 本三角**抓不到真实的 corner 风险**。要抓，`T_ref` 必须来自**外部时钟 spec**（不由 Tech 派生），
    那时 T_ref 是常数、delay 随 corner 变，slack 才会真正散布。**这属 T5 的架构前提，不在本批。**
    """
    from dataclasses import replace as _dc_replace

    from . import dcell as _DC
    from . import dsignoff as _SG

    _c = dict(corners or _SG.CORNERS)
    if "tt" not in _c:
        raise ValueError("corner 表缺 `tt` —— 没有参考角就没有「相对 tt 的散布」")

    _pl0 = (FO_PORT * _DC.DEFAULT_TECH.cin_ff) if port_load_ff is None \
        else float(port_load_ff)
    out = {"corners": {}, "unit": "ps", "lib_chain":
                           ("closed" if lib is None else
                            "liberty:%s" % getattr(lib, "name", "?"))}
    for name, (kr, kc) in _c.items():
        tk = _dc_replace(_DC.DEFAULT_TECH,
                                 r_on_ohm=_DC.DEFAULT_TECH.r_on_ohm * float(kr),
                                 cin_ff=_DC.DEFAULT_TECH.cin_ff * float(kc))
        # 🔴 端口负载随 `cin_ff` 一起缩放（它是「扇出 × 输入电容」，不是独立量）
        pl = FO_PORT * tk.cin_ff if port_load_ff is None else float(port_load_ff)
        a = sta(nl, tech=tk, port_load_ff=pl, topo_sort=True, lib=lib)
        b = (sta(nl, tech=tk, wire_load_ff=wire_load_ff, port_load_ff=pl,
                 topo_sort=True, lib=lib)
             if wire_load_ff else a)
        cl = constraint_layer(nl, tech=tk, comb_delay_ideal_ps=a.comb_delay_ps,
                              comb_delay_wired_ps=b.comb_delay_ps, lib=lib)
        out["corners"][name] = {
            "k_r": float(kr), "k_c": float(kc),
            "r_on_ohm": tk.r_on_ohm, "cin_ff": tk.cin_ff,
            "t_ref_ps": cl["clock_period_ps"],
            "ideal_ps": a.comb_delay_ps,
            "wired_ps": b.comb_delay_ps,
            "slack_ideal_ps": cl["slack_ideal_ps"],
            "slack_wired_ps": cl["slack_wired_ps"],
            "max_transition_ps": cl["max_transition_ps"],
        }

    tt = out["corners"]["tt"]
    out["spread_pct"] = {}
    for key in ("t_ref_ps", "ideal_ps", "wired_ps"):
        vals = [v[key] for v in out["corners"].values()]
        out["spread_pct"][key] = ((max(vals) - min(vals)) / tt[key] * 100.0) \
            if tt[key] else None
    sl = [v["slack_wired_ps"] for v in out["corners"].values()]
    out["slack_wired"] = {
        "min_ps": min(sl), "max_ps": max(sl),
        "span_ps": max(sl) - min(sl),
        "all_negative": all(x < 0 for x in sl),
        "n_negative": sum(1 for x in sl if x < 0),
        "n_corners": len(sl),
    }
    out["tt_port_load_ff"] = _pl0
    out["corners_order"] = sorted(out["corners"], key=lambda k: out["corners"][k]["r_on_ohm"])
    out["in_blocking"] = False
    out["scope"] = "DIAGNOSTIC_ONLY"
    out["structural_limit"] = (
        "`T_ref` 与 `delay` **同源**（都来自 `Tech`）⇒ 按同一 `(kr,kc)` 缩放时部分抵消 ⇒ "
        "`slack` 对 corner 不敏感（T_ref 散布 %.1f%% 而 slack 只动 %.3f ps）"
        % (out["spread_pct"]["t_ref_ps"], out["slack_wired"]["span_ps"]))
    out["not_included"] = (
        "corner 只缩放 `r_on` / `cin_ff` 两个量；不含温度对迁移率/阈值的影响、不含电压对延时的影响、"
        "不含 clock uncertainty / OCV / AOCV / POCV —— 三角是**两个参数的散布**，不是 PVT 签核")
    return out


# ---------------------------------------------------------------------------
# 功耗（一阶 · **claimable=False**）
# ---------------------------------------------------------------------------
def switching_power_nw(nl, f_hz: float, alpha: float = 0.1,
                       tech=None, port_load_ff: float = 0.0) -> float:
    """动态功耗 P = α·Σ C_L·V²·f（单位 nW）。**α 是假设，不是测量。**"""
    # R5-fix：默认值在调用时取，不在 def 时绑定
    if tech is None:
        tech = DC.DEFAULT_TECH
    load = loads_of(nl, port_load_ff, tech)
    c_tot_ff = 0.0
    for g in nl.gates:
        if g.cell == "DFF":
            continue
        c_tot_ff += load.get(g.out, 0.0)
    p_w = alpha * (c_tot_ff * 1e-15) * tech.vdd ** 2 * f_hz
    return p_w * 1e9


def clock_power_nw(nl, f_hz: float, tech=None) -> float:
    """时钟网功耗（每周期翻两次 ⇒ α=2）。一阶。"""
    # R5-fix：默认值在调用时取，不在 def 时绑定
    if tech is None:
        tech = DC.DEFAULT_TECH
    c_ff = nl.n_dff() * tech.cin_ff
    return 2.0 * (c_ff * 1e-15) * tech.vdd ** 2 * f_hz * 1e9


# ---------------------------------------------------------------------------
# 解析金标（三条独立路径）
# ---------------------------------------------------------------------------
def chain_golden_from_loads(cell: str, loads, tech=None) -> float:
    """**路径 ②**：逐级累加（负载可逐级不同）。"""
    # R5-fix：默认值在调用时取，不在 def 时绑定
    if tech is None:
        tech = DC.DEFAULT_TECH
    loads = list(loads)
    return sum(DC.cell_delay_ps(cell, l, tech) for l in loads)


def sizing_gain_chain(cells, load_ff=None, tech=None) -> dict:
    """**链级 pMOS 收益**：把 p 侧全部退回 1:1 后，这条链的延时变成当前的几倍。

    `cells` 是单元名序列（可**逐级不同负载**：给 `(name, load)` 对）。

    🔴 **结构性结论（本函数的全部意义）**：

        t_pd = ln2 · R · (C_self + C_load)        ← 两项都 ∝ R
        收益 = Σ R_i(1:1)·w_i / Σ R_i(平衡)·w_i    ← w_i = ln2·(C_self + C_load_i)

    ⇒ 当**所有级的负载相同**时，`w` 是公因子、直接约掉：

        **收益 = Σ R(1:1) / Σ R(平衡)** —— 一个**纯几何量**，与负载、`FO_target`、
        `cin_ff`、`C_self` **全都无关**。

    这不是近似：`v0.9.407` 在 FO=1..8 上实测同一条路径给出**同一个** 1.500000000×。

    ⚠️ 逐级负载**不同**时权重不能约，必须逐级加权 —— 所以本函数不返回
    「ΣR 比」而是逐级加权，两者在该退化的地方必须**逐位**相等（门禁侧有断言）。
    """
    tech = tech or DC.DEFAULT_TECH
    seq = normalize_chain(cells, load_ff, tech)

    cs = DC.c_self_ff(tech)
    rows = []
    num = den = 0.0
    sr_bal = sr_11 = 0.0          # 纯 ΣR（不经权重）—— 用来验证「均匀时可约」
    for name, lf in seq:
        c = DC.CELLS[name]
        r_bal = DC.cell_r_ohm(name, tech)
        r_11 = DC.cell_r_ohm(name, tech, w_p_nm=c.w_n_nm)
        w = DC.LN2 * (cs + lf) * DC.OHM_FF_TO_PS
        num += r_11 * w
        den += r_bal * w
        sr_bal += r_bal
        sr_11 += r_11
        rows.append({"cell": name, "load_ff": lf, "r_bal": r_bal, "r_1to1": r_11,
                     "cell_gain": r_11 / r_bal,
                     "delay_bal_ps": r_bal * w, "delay_1to1_ps": r_11 * w,
                     "dominance": DC.sizing_dominance(c, tech)})
    if not rows or den <= 0.0:
        raise ValueError("空路径或零电阻，算不出链级收益")
    return {
        "gain": num / den,
        "n_gates": len(rows),
        "sum_r_bal": sr_bal,
        "sum_r_1to1": sr_11,
        "gain_by_sum_r": sr_11 / sr_bal,
        "uniform_load": len({round(r["load_ff"], 12) for r in rows}) == 1,
        "delay_bal_ps": den, "delay_1to1_ps": num,
        "by_dominance": {d: sum(1 for r in rows if r["dominance"] == d)
                         for d in (DC.DOMINANCE_PULLUP, DC.DOMINANCE_PULLDOWN,
                                   DC.DOMINANCE_BALANCED)},
        "cells": rows,
    }


def self_load_default(load_ff, tech=None):
    """缺省每级负载 = `FO_TARGET · cin_ff`（与 `constraint_layer` 同源）。"""
    tech = tech or DC.DEFAULT_TECH
    return (FO_TARGET * tech.cin_ff) if load_ff is None else float(load_ff)


def normalize_chain(cells, load_ff, tech):
    """把 `cells` 归一成 `[(name, load_ff)]`。

    🔴 `sizing_gain_chain` 与 `area_delay_tradeoff` **共用这一份**：
    「路径上的负载怎么定」如果两处各写一次，一个改了另一个不改就会给出
    「延时收益按 A 口径、面积代价按 B 口径」的合成指标 —— 那比没有指标更坏。

    🔴 **为什么是公开名（不带下划线）**：`lda_harness.reachability` 的引用图
    **只连公开函数**（`public_funcs` ⇒ `edges = {t for t in ids_in(node) if t in funcs}`）
    ⇒ 私有 helper 对它是**透明**的：私有函数体内引用到的公开函数会被判成「零引用」。
    v0.9.408 首版用 `_normalize_chain`，它体内的 `self_load_default` 立刻被 R1 判死
    （全量 405 PASS / 1 FAIL 的唯一来源）。这不是「改名换绿」——本函数被两个公开 API
    共用，公开是它真实的可见性；改名让引用图**如实反映**调用关系。
    ⚠️ 反向的教训：**把公开函数重构成私有 helper，会触发 reachability 假红**，
    不要为此去扩 `DEAD_BASELINE`。
    """
    seq = []
    for item in cells:
        if isinstance(item, (tuple, list)):
            seq.append((item[0], (float(item[1]) if item[1] is not None
                                 else self_load_default(load_ff, tech))))
        else:
            seq.append((item, self_load_default(load_ff, tech)))
    return seq


def area_delay_tradeoff(cells, load_ff=None, tech=None) -> dict:
    """**面积 ↔ 延时联合指标**（v0.9.408）—— 把两笔账放进同一个分母。

    ═══════════════════════════════════════════════════════════════════════
    为什么必须合成一个数
    ───────────────────────────────────────────────────────────────────────
    v0.9.404 报「面积 +13.0%」，v0.9.407 报「延时 2.50×」—— 两个数**并排看**
    读者会得到相反印象：悲观的人说「贵了 13%」，乐观的人说「快了 2.5 倍」。
    真正的问题是「这份面积买回了多少延时」，它只能是一个比值。

    ═══════════════════════════════════════════════════════════════════════
    两个指标（互补，不能用其中一个代替另一个）
    ───────────────────────────────────────────────────────────────────────
    · `elasticity`（无量纲）= `(延时收益 − 1) / (面积比 − 1)`
      = **每花 1% 面积，买回百分之几的延时**。跨规模、跨路径可比。
    · `ps_per_um2`（有量纲）= `(延时差 ps) / (面积差 µm²)`
      = **每多 1 µm² 省下多少 ps**。坪效，可与其他设计直接比。

    ═══════════════════════════════════════════════════════════════════════
    🔴 三个口径必须分开记，混起来就是系统性高估
    ───────────────────────────────────────────────────────────────────────
    ① **瓦片面积**（本函数）= Σ 各级单元的 `w×h`。不含布线通道、不含单元间隙。
    ② **布局面积**（主链 59.202 µm²）= `dpnr.place_real` 的 die，含通道与间隙 ——
       它比瓦片面积大，两者**不可互相引用**。
    ③ **反事实面积**：把 p 侧退回 `W_n`（1:1）后**重建版图**再量 ——
       走真几何（`dcells.cell_area_um2_at` → `build_*(w_p_nm=)`），不是高度外推。

    ═══════════════════════════════════════════════════════════════════════
    ⚠️ 谁的面积不变就没指标
    ───────────────────────────────────────────────────────────────────────
    纯下拉主导的单元（NAND3/AND3）加宽 p 侧**不改变** `max(R_pd, R_pu)`，
    也不改变单元高度（高度由 p-diff 宽度决定，但它不是瓶颈）…… 具体地：
    `area_ratio == 1` 时分母为零 ⇒ `elasticity = None`。
    **这一条是特性不是缺陷**：它如实说「这笔改动在这个单元上没有可报的收益」。
    """
    from . import dcells as CL
    tech = tech or DC.DEFAULT_TECH
    seq = normalize_chain(cells, load_ff, tech)
    rows = []
    a_bal = a_11 = d_bal = d_11 = 0.0
    for name, lf in seq:
        c = DC.CELLS[name]
        if not c.layout:
            raise ValueError(
                "单元 %s 没有版图（`Cell.layout` 为空）⇒ 面积代价不可算。"
                "合成指标拒绝用「面积未知」去配「延时已知」。" % name)
        a_b = CL.cell_area_um2_at(c.layout)
        a_1 = CL.cell_area_um2_at(c.layout, w_p_nm=c.w_n_nm)
        # 🔴 延时走**同一个** `cell_delay_ps`（只多一个 `w_p_nm`），不另写 1:1 公式
        d_b = DC.cell_delay_ps(name, lf, tech)
        d_1 = DC.cell_delay_ps(name, lf, tech, w_p_nm=c.w_n_nm)
        a_bal += a_b
        a_11 += a_1
        d_bal += d_b
        d_11 += d_1
        rows.append({"cell": name, "layout": c.layout, "load_ff": lf,
                     "area_bal_um2": a_b, "area_11_um2": a_1,
                     "delay_bal_ps": d_b, "delay_11_ps": d_1,
                     "cell_area_ratio": (a_b / a_1) if a_1 else None,
                     "cell_delay_gain": (d_1 / d_b) if d_b else None,
                     "dominance": DC.sizing_dominance(c, tech)})
    if not rows or a_bal <= 0.0 or d_bal <= 0.0:
        raise ValueError("空路径或零面积/零延时，算不出联合指标")
    area_ratio = a_bal / a_11
    delay_gain = d_11 / d_bal
    da, dd = a_bal - a_11, d_11 - d_bal
    return {
        "n_gates": len(rows),
        "area_bal_um2": a_bal, "area_11_um2": a_11, "area_ratio": area_ratio,
        "delay_bal_ps": d_bal, "delay_11_ps": d_11, "delay_gain": delay_gain,
        #: 每 1% 面积买回的 % 延时（无量纲 · 跨规模可比）
        "elasticity": (delay_gain - 1.0) / (area_ratio - 1.0)
                      if abs(area_ratio - 1.0) > 1e-12 else None,
        #: 每多 1 µm² 省下的 ps（有量纲 · 坪效）
        "ps_per_um2": (dd / da) if abs(da) > 1e-12 else None,
        "uniform_load": len({round(r["load_ff"], 12) for r in rows}) == 1,
        "area_basis": "TILE（Σ w×h · 不含通道/间隙 · 不是主链的布局面积）",
        "cells": rows,
    }


def build_chain_nl(cell: str, n_stage: int, load_ff: float, name="chain",
                   tie_inputs: bool = False):
    """造一条 N 级同构串联链的门级网表（用于金标对拍）。

    🔴 `tie_inputs`（v0.9.408）：多输入单元的**其余输入共接**到一条输入网 `in_tie_0`。

    为什么必须补：本函数原来无条件只连一个脚（`Gate(nm, cell, (prev,), nm)`）。
    对 INV 正确，对 NAND2/NOR2 却是**悬空脚** —— 网表在物理链上非法（布线器看到
    单端点脚，LVS 也对不上），于是「NOR 链能跑 P&R」这件事根本测不了。
    默认 `False` ⇒ 与旧行为**逐位相同**（金标对拍那批判据不受影响）。
    """
    from .dsynth import Gate, Netlist
    nl = Netlist(name=name)
    prev = "in_a_0"
    nl.inputs = (("a", 1),)
    nl.in_nets = {("a", 0): "in_a_0"}
    extra = 0
    if tie_inputs:
        extra = max(0, DC.CELLS[cell].n_in - 1)
        if extra:
            nl.inputs = (("a", 1), ("tie", 1))
            nl.in_nets[("tie", 0)] = "in_tie_0"
    for k in range(n_stage):
        nm = "x%d" % k
        nl.gates.append(Gate(nm, cell, (prev,) + ("in_tie_0",) * extra, nm))
        prev = nm
    nl.outputs = {"y": (prev,)}
    return nl


def sta_self_check(n_stage: int = 17, tech=None) -> dict:
    """三条路径必须逐位相等；并验证「0 级链延时恰为 0」。"""
    # R5-fix：默认值在调用时取，不在 def 时绑定
    if tech is None:
        tech = DC.DEFAULT_TECH
    problems = []
    # ① 恒定负载：图传播 vs 逐级累加 vs 代数相乘
    nl = build_chain_nl("INV", n_stage, 1.0)
    t = sta(nl, tech, port_load_ff=1.0)
    # 每级负载：中间级被下一级驱动（1 个扇入 = 1 fF）；末级接端口负载 1 fF
    # ⇒ 所有级负载恒为 1.0 fF
    p1 = t.comb_delay_ps
    p2 = chain_golden_from_loads("INV", [1.0] * n_stage, tech)
    p3 = DC.chain_golden_ps("INV", n_stage, 1.0, tech)
    for tag, x, y in (("graph_vs_sum", p1, p2), ("sum_vs_mul", p2, p3)):
        rel = abs(x - y) / max(abs(y), 1e-30)
        if rel > 1e-12:
            problems.append((tag, x, y, rel))

    # ② 「本应恰好为 0」的对照组：0 级链
    nl0 = build_chain_nl("INV", 0, 1.0)
    if sta(nl0, tech, port_load_ff=1.0).comb_delay_ps != 0.0:
        problems.append(("zero_stage_not_zero", sta(nl0, tech, 1.0).comb_delay_ps))

    # ③ 深度线性：级数翻倍 ⇒ 延时翻倍（比值判据只作**辅助**，主判据是上面两条绝对值）
    t2 = sta(build_chain_nl("INV", 2 * n_stage, 1.0), tech, port_load_ff=1.0)
    if abs(t2.comb_delay_ps - 2 * p1) > 1e-9:
        problems.append(("double_stage", t2.comb_delay_ps, 2 * p1))

    return {
        "ok": not problems,
        "problems": problems,
        "n_stage": n_stage,
        "delay_ps": p1,
        "per_stage_ps": p1 / n_stage,
    }


DSTA_DISCLOSURE = {
    "route": "E34 · 数字控制壳自主建 · 第 4 层（静态时序 + 面积/功耗）",
    "analysis": "拓扑序到达时间传播 · clk→Q 起点 · 建立检查 t_clk_min = max(arrival(D)+t_setup) · "
                "关键路径回溯 · 面积 = Σ 单元面积 · 漏电 = Σ 单元漏电",
    "golden": "N 级同构链：图传播 / 逐级累加 / 代数相乘 **三条独立路径逐位相等（<1e-12）**；"
              "0 级链延时恰为 0",
    "not_included": "无 P&R ⇒ 走线电容恒取 0（真实延时必然更大）· 无 buffer insertion/sizing ⇒ "
                    "大扇出延时被高估 · 单角 tt · 无 OCV/AOCV · 无串扰/噪声 · 无 EM/IR",
    "hold_time": "hold 形式上恒满足（单角零偏斜），但 `hold_checked=False` —— **没有真正检验**，"
                 "不制造「验过了」的错觉",
    "claimable": False,
    "claimable_reason": "延时/面积/功耗全部由一阶模型给出（r_on / area_per_tr / α 均为假设）；"
                        "可 signoff 的只有**结构性事实**（门数、DFF 数、深度、路径节点序）",
}
