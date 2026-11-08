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
        topo_sort: bool = False) -> Timing:
    """静态时序（一阶）。`lib` 给 LibertyLibrary 时延时改查 NLDM 表，否则走闭式。

    🔴 **保护性约束**：`lib=None` 时走的是与历史**完全相同**的表达式
    `tin[k] + DC.cell_delay_ps(g.cell, load, tech)` ⇒ E34/E35 等既有数字逐位不变。
    `lib` 模式下：库里查不到该单元的**表** ⇒ 该单元回落闭式并记入
    `lib_fallback_cells`（不静默）；插值越界**钳位**（不外插）并计数 `lib_clamped`。

    🔴 `topo_sort=False`（默认）⇒ 完全沿用历史行为（按 `nl.gates` 书写顺序传播），
    既有调用与 E34/E35 金标**逐位不变**。`topo_sort=True` 时先用
    `dsynth.topo_order` 排序再传播 —— 供源文件顺序不保证拓扑序的网表（如 c17）使用；
    有组合环会直接抛错（fail-closed），不静默用旧值。
    """
    # 🔴 R5-fix（v0.9.394）：默认值必须**在调用时**取，不在 `def` 时绑定。
    #   原签名 `tech=DC.DEFAULT_TECH` 在 import 时求值一次 ⇒ 之后换 Tech 实例
    #   主链（`ST.sta(nl, topo_sort=True)` 不传 tech）永远读旧值，参数看似"死"。
    #   改为 None 后取值，`DEFAULT_TECH` 未变时**逐位不变**（T1a 零变化实证：
    #   base 43.490 不变；r_on×4 → 155.959、t_intr×4 → 61.490 两条手算吻合）。
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
        hold_ok=True,            # 单角零偏斜下形式上成立 —— 见 hold_checked
        hold_checked=False,      # 🔴 **没有真正检验**（无偏斜/无角/无串扰）
        lib_used=lib_tables is not None,
        lib_fallback_cells=tuple(sorted(set(fallback))),
        lib_clamped=clamped,
    )


def _inet(port, bit):
    return ("q_%s_%d" % (port[:-2], bit)) if port.endswith("@q") \
        else ("in_%s_%d" % (port, bit))


# ═══════════════════════════════════════════════════════════════════════════
# T1b · S1a / S1c 最小约束层（**零数字变化**：只把"量尺"造出来，不改量出的数）
# ═══════════════════════════════════════════════════════════════════════════
# 🔴 为什么这一层值得单独存在：在此之前，仓库里**没有任何地方定义"周期应该多长"**，
#   于是"延时 43.490 ps"这个数字**没有满足/不满足可言** —— 一个没有约束的数字无法
#   证伪，也无法在 T2 改几何后回答"是变好了还是变差了"。本层只做四件事：
#   把 `clock_period` / `max_fanout` / `max_transition` 由 `Tech` + 拓扑派生，
#   并给出两套口径的 `slack`（ideal / wired）—— **只给数，不给判决**。

#: 唯一扇出目标（U-1：S1a 的 `T_ref` 与 S1c 的 `max_fanout` 由**同一个数**派生，
#: 禁第二份定义）。预注册 = 3，依据是实测四组（legacy 口径）：
#: FO1 `−6.238 / −44.036`（全红）· FO3 `+31.192 / +18.655`（全绿）·
#: FO4 `+49.907 / +12.109`（全绿）；FO3 在 Q2 后翻转成 `+31.192 / −6.606`。
#: ⇒ 只有 FO3 在"改几何后才显现违例"，其余两组要么永远红、要么永远绿（无判别力）。
FO_TARGET = 3.0


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
                     comb_delay_wired_ps=None) -> dict:
    """S1a + S1c：由 `Tech` + 拓扑派生约束量（**禁出现字面量**）。

    定义（规划 §3-S1）::

        T_ref = Σ_{i ∈ L_top} cell_delay(k_drive_i, FO_target · cin_ff)
        max_fanout     = FO_target                 （与 S1a 同源，U-1）
        max_transition = _DEFAULT_SLEW_PS           （**显式假设**，slew 不传播）
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
        "max_transition_ps": _DEFAULT_SLEW_PS,
        "max_transition_is_assumption": True,
        # ── 两套口径的裕量（**只给数，不判满足**）──
        "slack_ideal_ps": sl_i,
        "slack_wired_ps": sl_w,
        "discriminates": discriminates(sl_i, sl_w),
        # ── 可追溯性：每个量的来源符号（禁字面量 DoD 的机核入口）──
        "sources": {
            "clock_period_ps": ["Tech.t_intr_ps", "Tech.r_on_ohm", "Tech.cin_ff",
                                "FO_TARGET", "Cell.k_drive", "LN2", "OHM_FF_TO_PS"],
            "max_fanout": ["FO_TARGET"],
            "max_transition_ps": ["_DEFAULT_SLEW_PS"],
            "slack_*": ["clock_period_ps", "comb_delay_ideal_ps",
                        "comb_delay_wired_ps"],
        },
        "assumptions": {
            "fo_target": "预注册 3（见 FO_TARGET 注释的四组实测）",
            "load_per_stage": "FO_target·cin_ff —— 每级按目标扇出计负载，非实际负载",
            "max_transition": "slew 不传播，取 _DEFAULT_SLEW_PS 常数（假设，非测量）",
            "dff": "DFF 段（clk→Q）不计入 T_ref：t_clk_q 在当前网表无消费者、未标定",
            "verdict": "本层不判满足；`discriminates` 只说明约束有没有判别力",
        },
        "not_included": "无时钟树 / 无偏斜 / 无多周期 / 无 IO 延时 / 无 keep-out；"
                        "周期是**一阶估计**，非时序签核",
        "claimable": False,
        "claimable_reason": "T_ref 由一阶 RC + 预注册扇出目标派生 ⇒ MODEL_ESTIMATE",
    }


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


def build_chain_nl(cell: str, n_stage: int, load_ff: float, name="chain"):
    """造一条 N 级同构串联链的门级网表（用于金标对拍）。"""
    from .dsynth import Gate, Netlist
    nl = Netlist(name=name)
    nl.inputs = (("a", 1),)
    nl.in_nets = {("a", 0): "in_a_0"}
    prev = "in_a_0"
    for k in range(n_stage):
        nm = "x%d" % k
        nl.gates.append(Gate(nm, cell, (prev,), nm))
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
