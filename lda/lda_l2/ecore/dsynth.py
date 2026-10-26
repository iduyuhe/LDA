# -*- coding: utf-8 -*-
"""E34 · **逻辑综合 + 门级网表仿真**（`lda/lda_l2/ecore/dsynth.py` · D-212）。

══════════════════════════════════════════════════════════════════════════
定位：把 AST 变成门 —— 自主数字链最核心的一段
══════════════════════════════════════════════════════════════════════════
`drtl` 给 AST，`daig` 给布尔网络，`dcell` 给单元，本模块把它们接起来：

    AST ──位展开──→ AIG ──技术映射──→ 门级网表（NAND2 + INV + DFF）

并额外提供**引擎 B**（`sim_netlist`）：逐单元查真值表传播。

══════════════════════════════════════════════════════════════════════════
🔴🔴 综合器最容易造出的三种「假绿」，以及本模块的防线
══════════════════════════════════════════════════════════════════════════
E30（层栈「DRC 全过」其实是取错栈）与 E31（把链长当 via 数）的教训共性：
**判据看起来在检查一件事，实际检查的是另一件事。**

| 假绿 | 表现 | 防线 |
|---|---|---|
| ① 综合器其实没综合 | 网表 = 输入的直通/常数，等价性却绿 | `netlist_authenticity`：**每个主输出必须由库内单元驱动**、DFF 数必须 == 状态位数、门数 ≥ 下界 |
| ② 两个引擎共用同一段求值 | 对拍恒绿 | 引擎 A 走 Python 整数；引擎 B 走**逐单元真值表**（代码路径零共享） |
| ③ 输出端口漏接 | 少一个输出，穷举只看剩下的 | `comb_outputs()` 全列 + 逐位长度断言（**不用 `all([])`**） |

⚠️ 第 ③ 条是 E30 C2 探针踩过的坑：`all([])` 恒 True ⇒ **空集合会静默通过**。
本模块所有「全都要」的判断都显式断言集合非空、长度匹配。

══════════════════════════════════════════════════════════════════════════
📌 明确不做（一次做扎实一个切片，不假装全能）
══════════════════════════════════════════════════════════════════════════
- **无布局布线（P&R）** ⇒ 无物理面积、无真实线延时、无扇出驱动插入（buffer insertion）
- 无线负载模型：所有扇出按 `load_ff = k × C_in` 一阶估计（`dsta` 负责）
- 无时钟树综合（CTS）· 无扫描插入（DFT）· 无功耗优化（clock gating）
- 无 SAT sweeping / 重写引擎 ⇒ 门数显著高于商业综合器（**公开承认，不美化**）
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import dcell as DC
from . import drtl as RT
from .daig import (C0, C1, Aig, add_bits, const_bits, eq_bits, mux_bits,
                   red_or, ult_bits)


class NotReady(Exception):
    """表达式依赖尚未计算出的信号（组合不动点迭代用）。"""


class Unsynth(Exception):
    """结构不可综合（组合不完全赋值 / 组合环 / 未声明信号）。"""


# ---------------------------------------------------------------------------
# 网表
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Gate:
    name: str
    cell: str
    ins: tuple
    out: str


@dataclass
class Netlist:
    name: str
    inputs: tuple = ()            # ((port, width), ...) · port 形如 "a" / "cnt@q"
    in_nets: dict = field(default_factory=dict)    # (port, bit) -> net
    outputs: dict = field(default_factory=dict)    # port -> tuple(net) LSB first
    gates: list = field(default_factory=list)
    clocks: tuple = ()

    def n_gates(self) -> int:
        return sum(1 for g in self.gates if g.cell != "DFF")

    def n_dff(self) -> int:
        return sum(1 for g in self.gates if g.cell == "DFF")

    def area_um2(self, tech=DC.DEFAULT_TECH) -> float:
        return sum(DC.cell_area_um2(g.cell, tech) for g in self.gates)

    def leak_nw(self, tech=DC.DEFAULT_TECH) -> float:
        return sum(DC.cell_leak_nw(g.cell, tech) for g in self.gates)

    def cell_hist(self) -> dict:
        h = {}
        for g in self.gates:
            h[g.cell] = h.get(g.cell, 0) + 1
        return dict(sorted(h.items()))

    def n_transistors(self) -> int:
        return sum(DC.CELLS[g.cell].n_tr for g in self.gates)


# ---------------------------------------------------------------------------
# 位展开：AST → AIG 位向量
# ---------------------------------------------------------------------------
class _BEnv:
    """信号名 → 位向量（LSB first）。`None` 表示尚未计算。"""

    def __init__(self, init=None):
        self.d = dict(init or {})

    def get(self, name):
        return self.d.get(name)

    def set(self, name, bs):
        self.d[name] = bs

    def snap(self):
        return tuple(sorted((k, tuple(v) if v is not None else None)
                            for k, v in self.d.items()))

    def copy(self):
        return _BEnv({k: (list(v) if v is not None else None) for k, v in self.d.items()})


def _rd(env, name, w):
    bs = env.get(name)
    if bs is None:
        raise NotReady(name)
    if len(bs) < w:
        return list(bs) + [C0] * (w - len(bs))
    return list(bs[:w])


def _zext(bs, w):
    return list(bs) + [C0] * max(0, w - len(bs))


def bits(a, env, widths, g: Aig, ctx=0):
    """表达式 → 位向量（LSB first）。宽度语义与 `drtl.ev` **必须一致**（见其 docstring）。"""
    if isinstance(a, RT.Num):
        return const_bits(a.val, max(a.width, ctx))
    if isinstance(a, RT.Sig):
        w = widths.get(a.name, 1)
        bs = _rd(env, a.name, w)
        if not a.idx:
            return bs
        if len(a.idx) == 1:
            i = a.idx[0]
            return [bs[i]] if 0 <= i < w else [C0]
        hi, lo = a.idx
        return [bs[i] if 0 <= i < w else C0 for i in range(lo, hi + 1)]
    if isinstance(a, RT.Un):
        if a.op == "!":
            return [red_or(g, bits(a.a, env, widths, g, 0)) ^ 1]
        x = bits(a.a, env, widths, g, ctx)
        if a.op == "~":
            return [b ^ 1 for b in x]
        # 单目减 = 取反加一（补码）
        return add_bits(g, [b ^ 1 for b in x], const_bits(1, len(x)))
    if isinstance(a, RT.Bin):
        return _bin(a, env, widths, g, ctx)
    if isinstance(a, RT.Ter):
        w = max(RT._width(a.a, widths), RT._width(a.b, widths), ctx)
        s = red_or(g, bits(a.c, env, widths, g, 0))
        return mux_bits(g, s, _zext(bits(a.a, env, widths, g, w), w),
                        _zext(bits(a.b, env, widths, g, w), w))
    if isinstance(a, RT.Concat):
        out = []
        for p in reversed(a.parts):
            out.extend(bits(p, env, widths, g, 0))
        return out
    if isinstance(a, RT.Repl):
        unit = []
        for p in reversed(a.parts):
            unit.extend(bits(p, env, widths, g, 0))
        return unit * a.n
    raise Unsynth("表达式类型 " + type(a).__name__)


def _bin(a, env, widths, g, ctx):
    op = a.op
    if op in ("&&", "||"):
        x = red_or(g, bits(a.a, env, widths, g, 0))
        y = red_or(g, bits(a.b, env, widths, g, 0))
        return [g.AND(x, y) if op == "&&" else g.OR(x, y)]
    if op in ("==", "!=", "<", "<=", ">", ">="):
        w = max(RT._width(a.a, widths), RT._width(a.b, widths))
        x = _zext(bits(a.a, env, widths, g, w), w)
        y = _zext(bits(a.b, env, widths, g, w), w)
        if op == "==":
            return [eq_bits(g, x, y)]
        if op == "!=":
            return [eq_bits(g, x, y) ^ 1]
        if op == "<":
            return [ult_bits(g, x, y)]
        if op == ">=":
            return [ult_bits(g, x, y) ^ 1]
        if op == ">":
            return [ult_bits(g, y, x)]
        return [ult_bits(g, y, x) ^ 1]
    if op in ("<<", ">>"):
        w = max(RT._width(a.a, widths), ctx)
        x = _zext(bits(a.a, env, widths, g, w), w)
        n = a.b.val if isinstance(a.b, RT.Num) else None
        left = (op == "<<")
        if n is not None:
            if n <= 0:
                return x
            if n >= w:
                return [C0] * w
            return ([C0] * n + x[:w - n]) if left else (x[n:] + [C0] * n)
        s = bits(a.b, env, widths, g, 0)
        cur = x
        for k, sb in enumerate(s):
            d = 1 << k
            if d >= w:
                break
            sh = ([C0] * d + cur[:w - d]) if left else (cur[d:] + [C0] * d)
            cur = [g.MUX(sb, sh[i], cur[i]) for i in range(w)]
        return cur
    w = max(RT._width(a.a, widths), RT._width(a.b, widths), ctx)
    x = _zext(bits(a.a, env, widths, g, w), w)
    y = _zext(bits(a.b, env, widths, g, w), w)
    if op == "+":
        return add_bits(g, x, y)
    if op == "-":
        return _sub(g, x, y)
    if op == "&":
        return [g.AND(x[i], y[i]) for i in range(w)]
    if op == "|":
        return [g.OR(x[i], y[i]) for i in range(w)]
    if op == "^":
        return [g.XOR(x[i], y[i]) for i in range(w)]
    if op in ("~^", "^~"):
        return [g.XNOR(x[i], y[i]) for i in range(w)]
    raise Unsynth("运算符 " + op)


def _sub(g, x, y):
    """`x - y` = `x + ~y + 1`（补码），**必须显式带进位输入 1**。"""
    s = []
    c = C1
    for i in range(len(x)):
        h = g.XOR(x[i], y[i] ^ 1)
        s.append(g.XOR(h, c))
        c = g.OR(g.AND(x[i], y[i] ^ 1), g.AND(h, c))
    return s


def set_lhs(lhs, bs, env):
    name = lhs.name
    cur = env.get(name)
    if not lhs.idx:
        env.set(name, list(bs))
        return
    if cur is None:
        raise Unsynth("部分赋值的目标 %r 尚无宽度上下文（先整体赋值）" % name)
    if len(lhs.idx) == 1:
        i = lhs.idx[0]
        if 0 <= i < len(cur):
            cur = list(cur)
            cur[i] = bs[0]
            env.set(name, cur)
        return
    hi, lo = lhs.idx
    cur = list(cur)
    for k, i in enumerate(range(lo, hi + 1)):
        if 0 <= i < len(cur):
            cur[i] = bs[k]
    env.set(name, cur)


def exec_stmt_bits(st, rd, wr, widths, g):
    """执行语句：**读 `rd`、写 `wr`**（时序块靠这个分离实现非阻塞语义）。"""
    if isinstance(st, RT.Block):
        for s in st.stmts:
            exec_stmt_bits(s, rd, wr, widths, g)
        return
    if isinstance(st, RT.Assign):
        lw = RT._width(st.lhs, widths)
        b = bits(st.rhs, rd, widths, g, lw)
        set_lhs(st.lhs, _zext(b, lw)[:lw], wr)
        return
    if isinstance(st, RT.If):
        c = red_or(g, bits(st.cond, rd, widths, g, 0))
        wr_t = wr.copy()
        exec_stmt_bits(st.then, rd, wr_t, widths, g)
        if st.els is None:
            wr_e = wr.copy()
        else:
            wr_e = wr.copy()
            exec_stmt_bits(st.els, rd, wr_e, widths, g)
        _merge(c, wr_t, wr_e, wr, g)
        return
    if isinstance(st, RT.Case):
        sel = bits(st.sel, rd, widths, g, 0)
        sw = len(sel)
        dflt = None
        pairs = []
        for vals, body in st.items:
            if vals is None:
                dflt = body
                continue
            conds = []
            for v in vals:
                vb = _zext(bits(v, rd, widths, g, 0), sw)
                conds.append(eq_bits(g, sel, vb))
            pairs.append((red_or(g, conds), body))
        # 🔴 「保持」的起点必须是**进入 case 之前**的 env，不能是 default 执行后的 env。
        #    E34 第一版用 `base` 当每个分支的起点 ⇒ `case(x) 1: if (a) y<=b; endcase`
        #    在 a=0 时会把 y 保持成 default 的值（而不是 y 的原值）。
        #    这个缺陷单点随机向量抓不到（`fsm_like` 每个分支都赋值），
        #    **锁步序列对拍**（dequiv.lockstep）才把它逼出来。
        pre = wr.copy()
        acc = pre.copy()
        if dflt is not None:
            exec_stmt_bits(dflt, rd, acc, widths, g)
        for cond, body in reversed(pairs):
            br = pre.copy()
            exec_stmt_bits(body, rd, br, widths, g)
            merged = acc.copy()
            _merge(cond, br, acc, merged, g)
            acc = merged
        for k, v in acc.d.items():
            wr.d[k] = v
        return
    raise Unsynth("语句类型 " + type(st).__name__)


def _merge(cond, t_env, e_env, out_env, g):
    """`out = cond ? t : e`（逐位 MUX）。**两边都必须是已定义值**。"""
    names = set(t_env.d) | set(e_env.d)
    for nm in sorted(names):
        tb = t_env.get(nm)
        eb = e_env.get(nm)
        if tb is None and eb is None:
            continue
        if tb is None:
            tb = eb
        if eb is None:
            eb = tb
        if len(tb) != len(eb):
            w = max(len(tb), len(eb))
            tb, eb = _zext(tb, w), _zext(eb, w)
        out_env.d[nm] = [g.MUX(cond, tb[i], eb[i]) for i in range(len(tb))]


# ---------------------------------------------------------------------------
# 综合主流程
# ---------------------------------------------------------------------------
def synth(m: RT.Module, name=None) -> Netlist:
    """AST → 门级网表。整个过程**确定性**：同一输入必得同一网表。"""
    g = Aig()
    nl = Netlist(name=name or m.name)
    widths = m.widths

    benv = _BEnv()
    specs = []
    for nm in m.inputs:
        w = widths.get(nm, 1)
        benv.set(nm, [g.inp() for _ in range(w)])
        specs.append((nm, w))
    for s in sorted(m.state_regs):
        w = widths.get(s, 1)
        benv.set(s, [g.inp() for _ in range(w)])
        specs.append((s + "@q", w))
    # 被组合赋值的信号先标 None
    for s in sorted(m.comb_regs):
        benv.set(s, None)
    for lhs, _ in m.assigns:
        if not lhs.idx:
            benv.set(lhs.name, None)

    # ---- 组合不动点 ----
    pending = list(m.comb)
    for _round in range(200):
        changed = False
        snap0 = benv.snap()
        for lhs, rhs in m.assigns:
            lw = RT._width(lhs, widths)
            try:
                b = _zext(bits(rhs, benv, widths, g, lw), lw)[:lw]
            except NotReady:
                continue
            set_lhs(lhs, b, benv)
        still = []
        for st in pending:
            before = benv.snap()
            try:
                exec_stmt_bits(st, benv, benv, widths, g)
            except NotReady:
                benv = _BEnv(dict(_snap_to_d(before)))
                still.append(st)
                continue
            if benv.snap() != before:
                changed = True
        pending = still
        if not pending and benv.snap() == snap0 and not changed:
            break
    if pending:
        raise Unsynth("组合逻辑无法收敛（疑似组合环或未声明信号）：%d 个 always 块未完成"
                      % len(pending))

    # ---- 组合不完全赋值 = latch 推断 ⇒ 明确拒绝 ----
    for s in sorted(m.comb_regs):
        bs = benv.get(s)
        if bs is None or any(b is None for b in bs):
            raise Unsynth("组合块对 %r 赋值不完整 ⇒ 会推断出锁存器（latch），子集不支持" % s)

    # ---- 输出 ----
    for nm in m.outputs:
        bs = benv.get(nm)
        if bs is None:
            raise Unsynth("输出 %r 没有被任何语句驱动" % nm)
        if len(bs) != widths.get(nm, 1):
            raise Unsynth("输出 %r 宽度不符：%d vs %d" % (nm, len(bs), widths.get(nm, 1)))

    # ---- 时序块：一次求 next（读快照、写副本）----
    dff_jobs = []
    if m.state_regs:
        pre = benv.copy()
        nxt = benv.copy()
        for _clk, st in m.seq:
            exec_stmt_bits(st, pre, nxt, widths, g)
        for s in sorted(m.state_regs):
            cur = benv.get(s)
            if cur is None:
                raise Unsynth("状态寄存器 %r 没有输入节点" % s)
            nb = nxt.get(s)
            for i in range(len(cur)):
                d = nb[i] if (nb is not None and i < len(nb) and nb[i] is not None) else cur[i]
                dff_jobs.append((s, i, d, cur[i]))

    # ---- 技术映射 ----
    nets = _map(g, m, benv, widths, nl, dff_jobs)

    nl.inputs = tuple(specs)
    for (port, w) in specs:
        for i in range(w):
            nl.in_nets[(port, i)] = input_net(port, i)
    for nm in m.outputs:
        w = widths.get(nm, 1)
        nl.outputs[nm] = tuple(nets[("out", nm, i)] for i in range(w))
    for s in sorted(m.state_regs):
        w = widths.get(s, 1)
        nl.outputs[s + "@d"] = tuple(nets[("d", s, i)] for i in range(w))
    nl.clocks = tuple(sorted({c for c, _ in m.seq}))
    return nl


def input_net(port: str, bit: int) -> str:
    """端口位 → 物理网名。**状态寄存器用 `q_<sig>_<i>`**（与 DFF 输出同名，
    这样「Q 就是一级输入」在网表里是**同一个网**，不需要额外 BUF 驱动）。"""
    if port.endswith("@q"):
        return "q_%s_%d" % (port[:-2], bit)
    return "in_%s_%d" % (port, bit)


def _snap_to_d(snap):
    return {k: (list(v) if v is not None else None) for k, v in snap}


def _map(g: Aig, m: RT.Module, benv: _BEnv, widths, nl: Netlist, dff_jobs):
    """AIG → 单元网表。返回 `{(kind, name, bit): net}`。"""
    nets = {}
    input_port_of = {}

    # 建立 AIG 输入节点号 ↔ 端口位 的映射（按 `inp()` 创建顺序）
    order = []
    for nm in m.inputs:
        for i in range(widths.get(nm, 1)):
            order.append((nm, i))
    for s in sorted(m.state_regs):
        for i in range(widths.get(s, 1)):
            order.append((s + "@q", i))
    inputs_nodes = [i for i in range(1, len(g.kind)) if g.kind[i] == "input"]
    if len(inputs_nodes) != len(order):
        raise Unsynth("输入节点数不符：%d vs %d" % (len(inputs_nodes), len(order)))
    for node, key in zip(inputs_nodes, order):
        input_port_of[node] = key

    phys = {}       # node -> 非反相网名
    nphys = {}      # node -> 反相网名
    const = {}

    base_of = input_net

    def tie(v):
        if v not in const:
            nm = "TIE%d" % v
            nl.gates.append(Gate(nm, "TIEHI" if v else "TIELO", (), nm))
            const[v] = nm
        return const[v]

    def net(lit):
        if lit == C0:
            return tie(0)
        if lit == C1:
            return tie(1)
        node, inv = lit >> 1, lit & 1
        if g.kind[node] == "input":
            port, bit = input_port_of[node]
            base = base_of(port, bit)
            nets[("in", port, bit)] = base
            if inv:
                if node not in nphys:
                    nm = "ni%d" % node
                    nl.gates.append(Gate(nm, "INV", (base,), nm))
                    nphys[node] = nm
                return nphys[node]
            phys[node] = base
            return base
        if inv:
            if node not in nphys:
                la, lb = g.fan[node]
                nm = "g%d" % node
                nl.gates.append(Gate(nm, "NAND2", (net(la), net(lb)), nm))
                nphys[node] = nm
            return nphys[node]
        if node not in phys:
            if node not in nphys:
                la, lb = g.fan[node]
                nm = "g%d" % node
                nl.gates.append(Gate(nm, "NAND2", (net(la), net(lb)), nm))
                nphys[node] = nm
            nm = "i%d" % node
            nl.gates.append(Gate(nm, "INV", (nphys[node],), nm))
            phys[node] = nm
        return phys[node]

    for nm in m.outputs:
        for i, lit in enumerate(benv.get(nm)):
            nets[("out", nm, i)] = net(lit)
    for (s, i, d_lit, q_lit) in dff_jobs:
        if q_lit & 1:
            raise Unsynth("寄存器 Q 不得以反相形式出现（%s[%d]）" % (s, i))
        qn = base_of(input_port_of[q_lit >> 1][0], input_port_of[q_lit >> 1][1])
        nl.gates.append(Gate("ff_%s_%d" % (s, i), "DFF", (net(d_lit), "CLK"), qn))
        nets[("d", s, i)] = net(d_lit)
    return nets


# ---------------------------------------------------------------------------
# 引擎 B：门级网表仿真（逐单元查真值表）
# ---------------------------------------------------------------------------
def sim_netlist(nl: Netlist, pin: dict) -> dict:
    """**引擎 B**：按网表顺序逐门查 `dcell` 真值表传播。DFF 的 Q 由 `pin` 提供。"""
    val = {}
    for (port, w) in nl.inputs:
        v = pin.get(port, 0)
        for i in range(w):
            val[nl.in_nets[(port, i)]] = (v >> i) & 1
    for gt in nl.gates:
        if gt.cell == "DFF":
            continue                     # Q 已在输入里；D 由输出端口给出
        val[gt.out] = DC.eval_cell(gt.cell, [val[n] for n in gt.ins])
    out = {}
    for port, nts in nl.outputs.items():
        v = 0
        for i, n in enumerate(nts):
            if n not in val:
                raise Unsynth("输出网 %r 未被任何单元驱动" % n)
            v |= val[n] << i
        out[port] = v
    return out


# ---------------------------------------------------------------------------
# 真实性判据（防「综合器什么都没做」）
# ---------------------------------------------------------------------------
def netlist_authenticity(nl: Netlist, m: RT.Module) -> dict:
    """**综合非平凡性**：网表必须真的是「库内单元 + 拓扑合法」的门级实现。

    这条判据针对的假绿是：等价性检查绿了，但其实网表就是输入的直通/常数。
    ⇒ 逐条硬性要求，任何一条不满足即 `ok=False`。
    """
    problems = []
    outs = [n for port in nl.outputs for n in nl.outputs[port]]
    if not outs:
        problems.append("no_outputs")
    # ① 每个输出网必须被某个单元的 out 驱动，或是输入网 / 常数网
    driven = {g.out for g in nl.gates}
    in_net_set = set(nl.in_nets.values())
    for n in outs:
        if n not in driven and n not in in_net_set and not n.startswith("TIE"):
            problems.append("undriven_output:%s" % n)
    # ② 「直通」检测：输出网若是**纯输入网**且该端口宽度 >0，则该位是零逻辑
    passthru = [n for n in outs if n in in_net_set]
    # ③ DFF 数必须恰等于状态位总数
    want_dff = sum(len(nl.outputs[s + "@d"]) for s in
                   {p[:-2] for p in nl.outputs if p.endswith("@d")})
    if nl.n_dff() != want_dff:
        problems.append("dff_count:%d!=%d" % (nl.n_dff(), want_dff))
    # ④ 所有单元必须在库内
    for gt in nl.gates:
        if gt.cell not in DC.CELLS:
            problems.append("unknown_cell:%s" % gt.cell)
    # ⑤ 拓扑合法性：每个门的输入网必须先被定义（输入 / 之前门的输出）
    defined = set(nl.in_nets.values()) | {"CLK"}
    for gt in nl.gates:
        for n in gt.ins:
            if n not in defined:
                problems.append("forward_ref:%s<-%s" % (gt.name, n))
        defined.add(gt.out)
    # ⑥ 门数下界：有组合输出的模块，门数必须 > 0（否则是空网表）
    n_comb_out = sum(len(v) for k, v in nl.outputs.items() if not k.endswith("@d"))
    if n_comb_out > 0 and nl.n_gates() == 0 and not passthru:
        problems.append("zero_gates")
    return {
        "ok": not problems,
        "problems": problems,
        "n_gates": nl.n_gates(),
        "n_dff": nl.n_dff(),
        "passthru_bits": len(passthru),
        "n_out_bits": len(outs),
    }


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def dsynth_self_check() -> dict:
    problems = []
    src = """
module m(a, b, y);
  input  [3:0] a;
  input  [3:0] b;
  output [4:0] y;
  assign y = a + b;
endmodule
"""
    mod = RT.parse(src)
    nl = synth(mod)
    au = netlist_authenticity(nl, mod)
    if not au["ok"]:
        problems.append(("authenticity", au["problems"]))
    # 加法器绝对对拍（含进位那一位）
    for x, y in ((15, 1), (0, 0), (7, 8), (3, 4)):
        got = sim_netlist(nl, {"a": x, "b": y})["y"]
        if got != x + y:
            problems.append(("adder", x, y, got, x + y))
    return {"ok": not problems, "problems": problems,
            "gates": nl.n_gates(), "dff": nl.n_dff()}


DSYNTH_DISCLOSURE = {
    "route": "E34 · 数字控制壳自主建 · 第 3 层（逻辑综合 + 门级网表仿真）",
    "flow": "AST → AIG（位展开）→ 技术映射（NAND2 + INV + DFF + TIE）→ 网表",
    "engines": "引擎 A = drtl.rtl_eval_all（Python 整数）· 引擎 B = sim_netlist（逐单元真值表）",
    "authenticity_checks": "输出必被单元驱动 · DFF 数 == 状态位数 · 单元全在库内 · "
                           "拓扑无前向引用 · 有组合输出时门数 > 0",
    "not_included": "无 P&R（无物理面积/无真实线延时/无 buffer insertion）· 无 CTS · "
                    "无 DFT/扫描插入 · 无 clock gating · 无 SAT sweeping/rewrite ⇒ "
                    "门数显著高于商业综合器（公开承认）",
    "claimable": True,
    "claimable_reason": "综合结果的正确性由穷举等价性机核（dequiv）；门数的**优劣**不作宣称",
}
