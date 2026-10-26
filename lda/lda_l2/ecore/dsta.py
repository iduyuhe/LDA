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


def loads_of(nl, port_load_ff: float = 0.0, tech=DC.DEFAULT_TECH,
             wire_load_ff: dict = None) -> dict:
    """每根网的**总负载电容**（fF）。

    🔴 E35 之前：走线电容 = 0（无 P&R ⇒ 诚实取 0，不编数）。
    🔴 E35 起：可选注入 `wire_load_ff[net] = 该网的走线电容（fF）`，
    由 `dextract` 根据真实布线线长算出。**零线时行为不变**（E34 三路径金标不受影响）。
    """
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


def sta(nl, tech=DC.DEFAULT_TECH, port_load_ff: float = 0.0,
        wire_load_ff: dict = None) -> Timing:
    load = loads_of(nl, port_load_ff, tech, wire_load_ff)
    arr = {}
    pred = {}

    for (port, w) in nl.inputs:
        for i in range(w):
            n = _inet(port, i)
            if port.endswith("@q"):
                arr[n] = tech.t_clk_q_ps      # 时钟沿之后 Q 才稳定
            else:
                arr[n] = 0.0

    for g in nl.gates:
        if g.cell == "DFF":
            continue
        tin = [arr[n] for n in g.ins if n != "CLK"]
        if not tin:
            tin = [0.0]
        k = max(range(len(tin)), key=lambda j: tin[j])
        ins = [n for n in g.ins if n != "CLK"]
        arr[g.out] = tin[k] + DC.cell_delay_ps(g.cell, load.get(g.out, 0.0), tech)
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
    )


def _inet(port, bit):
    return ("q_%s_%d" % (port[:-2], bit)) if port.endswith("@q") \
        else ("in_%s_%d" % (port, bit))


# ---------------------------------------------------------------------------
# 功耗（一阶 · **claimable=False**）
# ---------------------------------------------------------------------------
def switching_power_nw(nl, f_hz: float, alpha: float = 0.1,
                       tech=DC.DEFAULT_TECH, port_load_ff: float = 0.0) -> float:
    """动态功耗 P = α·Σ C_L·V²·f（单位 nW）。**α 是假设，不是测量。**"""
    load = loads_of(nl, port_load_ff, tech)
    c_tot_ff = 0.0
    for g in nl.gates:
        if g.cell == "DFF":
            continue
        c_tot_ff += load.get(g.out, 0.0)
    p_w = alpha * (c_tot_ff * 1e-15) * tech.vdd ** 2 * f_hz
    return p_w * 1e9


def clock_power_nw(nl, f_hz: float, tech=DC.DEFAULT_TECH) -> float:
    """时钟网功耗（每周期翻两次 ⇒ α=2）。一阶。"""
    c_ff = nl.n_dff() * tech.cin_ff
    return 2.0 * (c_ff * 1e-15) * tech.vdd ** 2 * f_hz * 1e9


# ---------------------------------------------------------------------------
# 解析金标（三条独立路径）
# ---------------------------------------------------------------------------
def chain_golden_from_loads(cell: str, loads, tech=DC.DEFAULT_TECH) -> float:
    """**路径 ②**：逐级累加（负载可逐级不同）。"""
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


def sta_self_check(n_stage: int = 17, tech=DC.DEFAULT_TECH) -> dict:
    """三条路径必须逐位相等；并验证「0 级链延时恰为 0」。"""
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
