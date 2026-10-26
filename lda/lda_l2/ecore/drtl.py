# -*- coding: utf-8 -*-
"""E34 · **可综合 Verilog 子集前端 + 独立 RTL 解释器**（`lda/lda_l2/ecore/drtl.py` · D-210）。

══════════════════════════════════════════════════════════════════════════
定位：自主数字链的「入口」—— 把人的意图变成机器可综合的结构
══════════════════════════════════════════════════════════════════════════
不借 Yosys ⇒ 连**前端**也得自己写。本模块做两件事：

1. **词法 + 语法**：把一个明确划定的 Verilog 子集解析成 AST；
2. **解释执行**（`rtl_eval_all`）：直接按 Verilog 的位宽/阻塞/非阻塞语义求值 ——
   这是等价性检查的**引擎 A**。

══════════════════════════════════════════════════════════════════════════
🔴🔴 为什么解释器必须与网表仿真器**代码路径完全无关**
══════════════════════════════════════════════════════════════════════════
`METHOD_NOTES`：「同一事实写两次必须机核」。但**更危险的相反情形**是：
「两处看起来不同、实际共用同一段求值代码」—— 那不是对拍，是**自证**。

⇒ 本模块的解释器走 **Python 原生整数按位运算**（`& | ^ + <<`），
网表仿真器（`dsynth.sim_netlist`）走 **逐单元查真值表传播**。
两者唯一共享的是「输入向量枚举」与「信号名映射」，
**任何位宽/符号/进位/优先级的缺陷都只能落在其中一条路径上** ⇒ 必然对拍不上。

══════════════════════════════════════════════════════════════════════════
支持的子集（**明确划界，超出即报错，绝不静默降级**）
══════════════════════════════════════════════════════════════════════════
```verilog
module name(a, b, y);                    // non-ANSI 端口（体内声明方向）
  parameter W = 8;
  input  [W-1:0] a;                      // 只支持 [N-1:0] 降序向量
  output [W-1:0] y;
  reg    [W-1:0] r;  wire [W-1:0] w;
  assign y = expr;
  always @(*)         begin ... end      // 组合
  always @(posedge clk) begin ... end    // 时序（DFF）
endmodule
```
表达式运算符：`~ ! - ` 单目；`& | ^ ~^ << >> + - == != < <= > >= && ||` 双目；
`? :`；位选 `s[i]`、部分选择 `s[hi:lo]`；拼接 `{a,b}`、复制 `{n{a}}`。
语句：`=` / `<=`、`begin…end`、`if/else`、`case/default`。

**不支持（会抛 `Unsupported`，不是静默忽略）**：
`*` `/` `%` · 层次实例化 · `generate` · 数组/存储器 · 有符号数 · 函数/任务 ·
`for/while` · 延迟 `#` · 三态 `z` · `x` 传播（等价性只判 0/1 二值域）。

══════════════════════════════════════════════════════════════════════════
🔴 位宽语义（这里最容易出「假绿」）
══════════════════════════════════════════════════════════════════════════
- 无宽度十进制常数 = **32 位**（Verilog 规则）⇒ `~0` 是 32'hFFFF_FFFF，不是 1'b1。
  E34 若把常数压成「最小位宽」，`~0` 会变成 1，赋给 8 位信号就得 1（真值 255）——
  这类错误**比值判据完全看不见**，只有绝对对拍能抓。
- 算术/位运算结果宽度 = `max(wl, wr)`；比较/逻辑 = 1；移位 = 左操作数宽度。
- 赋值时截断到左值宽度（**不报溢出**，与 Verilog 一致）。

══════════════════════════════════════════════════════════════════════════
时序语义：把「状态」外提成一级输入
══════════════════════════════════════════════════════════════════════════
`rtl_eval_all(m, pin)` 里，`posedge` 块中的寄存器**当前值**由 `pin["sig@q"]` 提供
（缺省取 `pin["sig"]` 或 0），next 值单独返回。
⇒ 序列等价性 = **纯组合等价性**（状态只是额外输入），穷举向量空间因此可闭合。
⚠️ 这只证明「单周期」等价；**多周期复位序列等价不在本段范围**（写进披露）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

# ---------------------------------------------------------------------------
# 词法
# ---------------------------------------------------------------------------
_KW = {
    "module", "endmodule", "input", "output", "inout", "reg", "wire",
    "assign", "always", "begin", "end", "if", "else", "case", "endcase",
    "default", "parameter", "posedge", "negedge", "or", "localparam",
}
_OPS = (
    "<<<", ">>>",                      # 词法识别但语法层拒绝
    "<<", ">>", "<=", ">=", "==", "!=", "&&", "||", "~^", "^~",
    "+", "-", "*", "/", "%", "&", "|", "^", "~", "!", "<", ">",
    "?", ":", ";", ",", "(", ")", "[", "]", "{", "}", "=", ".", "#", "@",
)
_WORD = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_$")


class Unsupported(Exception):
    """子集之外的语法/语义 —— **必须显式抛，不允许静默降级**。"""


class Tok:
    __slots__ = ("kind", "val", "pos")

    def __init__(self, kind, val, pos):
        self.kind = kind
        self.val = val
        self.pos = pos

    def __repr__(self):
        return "Tok(%s,%r)" % (self.kind, self.val)


def _parse_num_text(s):
    """`8'd255` / `4'b1010` / `12` → (value, width)。无宽度十进制**恒为 32 位**。"""
    if "'" in s:
        w, rest = s.split("'", 1)
        base = rest[0].lower()
        digits = rest[1:].replace("_", "")
        if not digits:
            raise Unsupported("空位值：" + s)
        b = {"b": 2, "d": 10, "h": 16, "o": 8}[base]
        return int(digits, b), (int(w) if w else 32)
    return int(s, 10), 32


def tokenize(src: str):
    toks = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in " \t\r\n":
            i += 1
            continue
        # 注释
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j + 1
            continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            if j < 0:
                raise Unsupported("未闭合的块注释")
            i = j + 2
            continue
        # 数字（含位宽写法）
        if c.isdigit():
            j = i
            while j < n and (src[j] in "0123456789_"):
                j += 1
            if j < n and src[j] == "'":
                j += 1
                if j < n:
                    j += 1                       # 进制字符
                while j < n and (src[j] in "0123456789abcdefABCDEF_xzXZ_"):
                    j += 1
            toks.append(Tok("num", _parse_num_text(src[i:j]), i))
            i = j
            continue
        # 标识符/关键字
        if c.isalpha() or c == "_":
            j = i
            while j < n and src[j] in _WORD:
                j += 1
            w = src[i:j]
            toks.append(Tok("kw" if w in _KW else "id", w, i))
            i = j
            continue
        # 运算符（最长匹配）
        for op in _OPS:
            if src.startswith(op, i):
                toks.append(Tok("op", op, i))
                i += len(op)
                break
        else:
            raise Unsupported("无法识别的字符 %r @%d" % (c, i))
    toks.append(Tok("eof", None, n))
    return toks


# ---------------------------------------------------------------------------
# AST
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Num:
    val: int
    width: int


@dataclass(frozen=True)
class Sig:
    name: str
    idx: tuple = ()        # () | (i,) | (hi, lo)


@dataclass(frozen=True)
class Un:
    op: str
    a: object


@dataclass(frozen=True)
class Bin:
    op: str
    a: object
    b: object


@dataclass(frozen=True)
class Ter:
    c: object
    a: object
    b: object


@dataclass(frozen=True)
class Concat:
    parts: tuple


@dataclass(frozen=True)
class Repl:
    n: int
    parts: tuple


@dataclass(frozen=True)
class Assign:
    lhs: Sig
    rhs: object
    nb: bool = False       # True = 非阻塞（<=）


@dataclass(frozen=True)
class Block:
    stmts: tuple


@dataclass(frozen=True)
class If:
    cond: object
    then: object
    els: object = None


@dataclass(frozen=True)
class Case:
    sel: object
    items: tuple           # ((tuple_of_Num | None, stmt), ...) · None = default


# ---------------------------------------------------------------------------
# 语法（递归下降）
# ---------------------------------------------------------------------------
class Parser:
    def __init__(self, toks):
        self.t = toks
        self.i = 0

    def peek(self, k=0):
        return self.t[min(self.i + k, len(self.t) - 1)]

    def next(self):
        t = self.t[self.i]
        if t.kind != "eof":
            self.i += 1
        return t

    def at(self, val):
        t = self.peek()
        return t.kind in ("op", "kw") and t.val == val

    def accept(self, val):
        if self.at(val):
            self.next()
            return True
        return False

    def expect(self, val):
        if not self.accept(val):
            raise Unsupported("期望 %r，得到 %r @%d" % (val, self.peek().val, self.peek().pos))

    # -- 顶层 --------------------------------------------------------------
    def parse_module(self):
        self.expect("module")
        name = self.next().val
        self.expect("(")
        ports = []
        if not self.at(")"):
            while True:
                ports.append(self.next().val)
                if not self.accept(","):
                    break
        self.expect(")")
        self.expect(";")

        widths, inputs, outputs, regs = {}, [], [], []
        params = {}
        assigns, comb, seq = [], [], []

        while not self.at("endmodule"):
            t = self.peek()
            v = t.val
            if v in ("parameter", "localparam"):
                self.next()
                pname = self.next().val
                self.expect("=")
                e = self.expr(params)
                self.expect(";")
                params[pname] = _const_eval(e)
                continue
            if v in ("input", "output", "inout"):
                if v == "inout":
                    raise Unsupported("不支持 inout（数字链本段只做单向端口）")
                self.next()
                w = self._range_opt(params)
                while True:
                    nm = self.next().val
                    widths[nm] = w
                    (inputs if v == "input" else outputs).append(nm)
                    if not self.accept(","):
                        break
                self.expect(";")
                continue
            if v == "reg":
                self.next()
                w = self._range_opt(params)
                while True:
                    nm = self.next().val
                    widths[nm] = w
                    regs.append(nm)
                    if not self.accept(","):
                        break
                self.expect(";")
                continue
            if v == "wire":
                self.next()
                w = self._range_opt(params)
                while True:
                    nm = self.next().val
                    widths.setdefault(nm, w)
                    if not self.accept(","):
                        break
                self.expect(";")
                continue
            if v == "assign":
                self.next()
                lhs = self._lval()
                self.expect("=")
                rhs = self.expr(params)
                self.expect(";")
                assigns.append((lhs, rhs))
                continue
            if v == "always":
                self.next()
                self.expect("@")
                if self.accept("*"):
                    self.seq_or_comb(comb, seq, None)
                    continue
                self.expect("(")
                if self.accept("*"):
                    self.expect(")")
                    self.seq_or_comb(comb, seq, None)
                    continue
                edge = self.next().val
                if edge not in ("posedge", "negedge"):
                    raise Unsupported("always 敏感表只支持 @(*) 或 @(posedge clk)")
                clk = self.next().val
                if not self.accept(")"):
                    raise Unsupported("always 敏感表只支持单个时钟（多时钟/复位列表不在子集内）")
                if edge == "negedge":
                    raise Unsupported("不支持 negedge（本子集统一上升沿）")
                self.seq_or_comb(comb, seq, clk)
                continue
            if t.kind == "id":
                raise Unsupported("不支持层次实例化/任务调用：%r @%d" % (v, t.pos))
            raise Unsupported("模块体内无法识别：%r @%d" % (v, t.pos))

        self.expect("endmodule")
        for p in ports:
            if p not in widths:
                raise Unsupported("端口 %r 未声明方向/位宽（本子集要求 non-ANSI 体内声明）" % p)
        return Module(name=name, widths=widths, inputs=inputs, outputs=outputs,
                      regs=regs, params=params, assigns=assigns,
                      comb=comb, seq=seq)

    def seq_or_comb(self, comb, seq, clk):
        st = self.stmt(None)
        (seq if clk else comb).append((clk, st) if clk else st)

    def _range_opt(self, params):
        if not self.accept("["):
            return 1
        hi = _const_eval(self.expr(params))
        if self.accept(":"):
            lo = _const_eval(self.expr(params))
            self.expect("]")
            if hi < lo:
                raise Unsupported("[%d:%d] 升序向量不在子集内（统一 [N-1:0]）" % (hi, lo))
            return hi - lo + 1
        self.expect("]")
        raise Unsupported("不支持存储器/数组声明")

    def _lval(self):
        nm = self.next().val
        idx = ()
        if self.accept("["):
            a = _const_eval(self.expr(None))
            if self.accept(":"):
                b = _const_eval(self.expr(None))
                idx = (a, b)
            else:
                idx = (a,)
            self.expect("]")
        return Sig(nm, idx)

    # -- 语句 --------------------------------------------------------------
    def stmt(self, params):
        if self.accept("begin"):
            out = []
            while not self.at("end"):
                out.append(self.stmt(params))
            self.expect("end")
            return Block(tuple(out))
        if self.accept("if"):
            self.expect("(")
            c = self.expr(params)
            self.expect(")")
            th = self.stmt(params)
            el = self.stmt(params) if self.accept("else") else None
            return If(c, th, el)
        if self.accept("case"):
            self.expect("(")
            sel = self.expr(params)
            self.expect(")")
            items = []
            while not self.at("endcase"):
                if self.accept("default"):
                    self.expect(":")
                    items.append((None, self.stmt(params)))
                    continue
                vals = []
                while True:
                    vals.append(self.expr(params))
                    if not self.accept(","):
                        break
                self.expect(":")
                items.append((tuple(vals), self.stmt(params)))
            self.expect("endcase")
            return Case(sel, tuple(items))
        lhs = self._lval()
        if self.accept("<="):
            rhs = self.expr(params)
            self.expect(";")
            return Assign(lhs, rhs, True)
        if self.accept("="):
            rhs = self.expr(params)
            self.expect(";")
            return Assign(lhs, rhs, False)
        raise Unsupported("无法识别的语句起始：%r" % (self.peek().val,))

    # -- 表达式 ------------------------------------------------------------
    def expr(self, params):
        return self.ternary(params)

    def ternary(self, params):
        c = self.lor(params)
        if self.accept("?"):
            a = self.expr(params)
            self.expect(":")
            b = self.ternary(params)
            return Ter(c, a, b)
        return c

    def _bin(self, nxt, ops, params):
        e = nxt(params)
        while True:
            t = self.peek()
            if t.kind == "op" and t.val in ops:
                self.next()
                e = Bin(t.val, e, nxt(params))
            else:
                return e

    def lor(self, p):
        return self._bin(self.land, ("||",), p)

    def land(self, p):
        return self._bin(self.bor, ("&&",), p)

    def bor(self, p):
        return self._bin(self.bxor, ("|",), p)

    def bxor(self, p):
        return self._bin(self.band, ("^", "~^", "^~"), p)

    def band(self, p):
        return self._bin(self.beq, ("&",), p)

    def beq(self, p):
        return self._bin(self.brel, ("==", "!="), p)

    def brel(self, p):
        return self._bin(self.bshift, ("<", "<=", ">", ">="), p)

    def bshift(self, p):
        return self._bin(self.badd, ("<<", ">>"), p)

    def badd(self, p):
        return self._bin(self.bmul, ("+", "-"), p)

    def bmul(self, p):
        e = self.unary(p)
        while self.peek().kind == "op" and self.peek().val in ("*", "/", "%", "<<<", ">>>"):
            raise Unsupported("运算符 %r 不在自主子集内（乘法/除法/算术移位需专门模块，本段不做）"
                              % (self.peek().val,))
        return e

    def unary(self, p):
        t = self.peek()
        if t.kind == "op" and t.val in ("~", "!", "-"):
            self.next()
            return Un(t.val, self.unary(p))
        return self.primary(p)

    def primary(self, p):
        t = self.peek()
        if t.kind == "num":
            self.next()
            return Num(t.val[0], t.val[1])
        if t.kind == "id":
            self.next()
            idx = ()
            if self.accept("["):
                a = _const_eval(self.expr(p))
                if self.accept(":"):
                    b = _const_eval(self.expr(p))
                    idx = (a, b)
                else:
                    idx = (a,)
                self.expect("]")
            return Sig(t.val, idx)
        if self.accept("("):
            e = self.expr(p)
            self.expect(")")
            return e
        if self.accept("{"):
            # 复制 {n{a,b}}
            if self.peek().kind == "num" and self.peek(1).kind == "op" and self.peek(1).val == "{":
                n = _const_eval(self.expr(p))
                self.expect("{")
                parts = self._concat_parts(p)
                self.expect("}")
                self.expect("}")
                return Repl(n, parts)
            parts = self._concat_parts(p)
            self.expect("}")
            return Concat(parts)
        raise Unsupported("表达式无法识别：%r @%d" % (t.val, t.pos))

    def _concat_parts(self, p):
        parts = [self.expr(p)]
        while self.accept(","):
            parts.append(self.expr(p))
        return tuple(parts)


def _const_eval(a):
    """只接受常数的求值（用于位宽/索引/参数）。"""
    if isinstance(a, Num):
        return a.val
    if isinstance(a, Un) and a.op == "-":
        return -_const_eval(a.a)
    if isinstance(a, Bin):
        x, y = _const_eval(a.a), _const_eval(a.b)
        return {"+": x + y, "-": x - y, "<<": x << y, ">>": x >> y,
                "&": x & y, "|": x | y, "^": x ^ y}.get(a.op, 0)
    raise Unsupported("位宽/索引/参数必须是常数表达式：%r" % (a,))


# ---------------------------------------------------------------------------
# 模块对象
# ---------------------------------------------------------------------------
@dataclass
class Module:
    name: str
    widths: dict
    inputs: list
    outputs: list
    regs: list
    params: dict
    assigns: list
    comb: list
    seq: list
    state_regs: set = field(default_factory=set)
    comb_regs: set = field(default_factory=set)

    def __post_init__(self):
        seq_names, comb_names = set(), set()
        for _, st in self.seq:
            _collect_lhs(st, seq_names)
        self.state_regs = seq_names
        for st in self.comb:
            _collect_lhs(st, comb_names)
        self.comb_regs = comb_names - seq_names
        # 一致性：所有被赋值的信号必须有声明宽度
        for s in seq_names | comb_names | {l.name for l, _ in self.assigns}:
            self.widths.setdefault(s, 1)

    #: 「组合等价模型」的输入 = 主输入 + 状态位
    def comb_inputs(self):
        return list(self.inputs) + sorted(s + "@q" for s in self.state_regs)

    #: 「组合等价模型」的输出 = 主输出（reg 输出取其**当前值**）+ 各状态寄存器的 D 端
    def comb_outputs(self):
        outs = list(self.outputs)
        for s in sorted(self.state_regs):
            outs.append(s + "@d")
        return outs


def _collect_lhs(st, acc):
    if isinstance(st, Assign):
        acc.add(st.lhs.name)
        if st.lhs.idx:
            acc.add(st.lhs.name)
    elif isinstance(st, Block):
        for s in st.stmts:
            _collect_lhs(s, acc)
    elif isinstance(st, If):
        _collect_lhs(st.then, acc)
        if st.els is not None:
            _collect_lhs(st.els, acc)
    elif isinstance(st, Case):
        for _, s in st.items:
            _collect_lhs(s, acc)


# ---------------------------------------------------------------------------
# 引擎 A：RTL 解释器（Python 原生整数语义）
# ---------------------------------------------------------------------------
@lru_cache(maxsize=4096)
def _mask(w):
    return (1 << w) - 1


def _width(a, widths):
    """表达式的**自决定宽度**（Verilog 规则）。"""
    if isinstance(a, Num):
        return a.width
    if isinstance(a, Sig):
        if not a.idx:
            return widths.get(a.name, 1)
        if len(a.idx) == 1:
            return 1
        return a.idx[0] - a.idx[1] + 1
    if isinstance(a, Un):
        return 1 if a.op == "!" else _width(a.a, widths)
    if isinstance(a, Bin):
        op = a.op
        if op in ("==", "!=", "<", "<=", ">", ">=", "&&", "||"):
            return 1
        if op in ("<<", ">>"):
            return _width(a.a, widths)
        return max(_width(a.a, widths), _width(a.b, widths))
    if isinstance(a, Ter):
        return max(_width(a.a, widths), _width(a.b, widths))
    if isinstance(a, Concat):
        return sum(_width(p, widths) for p in a.parts)
    if isinstance(a, Repl):
        return a.n * sum(_width(p, widths) for p in a.parts)
    raise Unsupported("宽度：表达式类型 " + type(a).__name__)


def ev(a, env, widths, ctx=0):
    """返回 `(value, width)`。

    🔴 `ctx` = **上位上下文宽度**（Verilog 的 context-determined width）。
    不传播它会**静默丢进位**：`output [4:0] y = a + b`（a,b 各 4 位、15+1）
    在自决定宽度 4 位下算出 0，再零扩展成 5 位 ⇒ 得到 0 而不是 16。
    E34 第一版正是这样，被 `drtl_self_check` 的 15+1 对照组当场抓出。
    """
    if isinstance(a, Num):
        w = max(a.width, ctx)
        return a.val & _mask(w), w
    if isinstance(a, Sig):
        w = widths.get(a.name, 1)
        v = env.get(a.name, 0) & _mask(w)
        if not a.idx:
            return v, w
        if len(a.idx) == 1:
            return (v >> a.idx[0]) & 1, 1
        hi, lo = a.idx
        return (v >> lo) & _mask(hi - lo + 1), hi - lo + 1
    if isinstance(a, Un):
        if a.op == "!":
            x, _ = ev(a.a, env, widths, 0)
            return (0 if x else 1), 1
        x, wx = ev(a.a, env, widths, ctx)
        if a.op == "~":
            return (~x) & _mask(wx), wx
        return (-x) & _mask(wx), wx
    if isinstance(a, Bin):
        op = a.op
        if op in ("&&", "||"):
            x, _ = ev(a.a, env, widths, 0)
            y, _ = ev(a.b, env, widths, 0)
            if op == "&&":
                return (1 if (x and y) else 0), 1
            return (1 if (x or y) else 0), 1
        if op in ("==", "!=", "<", "<=", ">", ">="):
            w = max(_width(a.a, widths), _width(a.b, widths))
            x, _ = ev(a.a, env, widths, w)
            y, _ = ev(a.b, env, widths, w)
            r = {"==": x == y, "!=": x != y, "<": x < y,
                 "<=": x <= y, ">": x > y, ">=": x >= y}[op]
            return (1 if r else 0), 1
        if op in ("<<", ">>"):
            w = max(_width(a.a, widths), ctx)
            x, _ = ev(a.a, env, widths, w)
            y, _ = ev(a.b, env, widths, 0)
            n = y & 31
            return (((x << n) if op == "<<" else (x >> n)) & _mask(w)), w
        w = max(_width(a.a, widths), _width(a.b, widths), ctx)
        x, _ = ev(a.a, env, widths, w)
        y, _ = ev(a.b, env, widths, w)
        if op == "+":
            return (x + y) & _mask(w), w
        if op == "-":
            return (x - y) & _mask(w), w
        if op == "&":
            return x & y, w
        if op == "|":
            return x | y, w
        if op == "^":
            return x ^ y, w
        if op in ("~^", "^~"):
            return (~(x ^ y)) & _mask(w), w
        raise Unsupported("运算符 " + op)
    if isinstance(a, Ter):
        w = max(_width(a.a, widths), _width(a.b, widths), ctx)
        c, _ = ev(a.c, env, widths, 0)
        return ev(a.a if c else a.b, env, widths, w)
    if isinstance(a, Concat):
        v, w = 0, 0
        for p in a.parts:
            pv, pw = ev(p, env, widths, 0)
            v = (v << pw) | (pv & _mask(pw))
            w += pw
        return v, w
    if isinstance(a, Repl):
        v, w = 0, 0
        for p in a.parts:
            pv, pw = ev(p, env, widths, 0)
            v = (v << pw) | (pv & _mask(pw))
            w += pw
        full = 0
        for _ in range(a.n):
            full = (full << w) | (v & _mask(w))
        return full, w * a.n
    raise Unsupported("表达式类型 " + type(a).__name__)


def assign_to(lhs: Sig, val: int, width: int, env, widths):
    """把 `val`（宽 `width`）写入左值 —— 截断到左值宽度；部分选择是读改写。"""
    name = lhs.name
    tw = widths.get(name, 1)
    cur = env.get(name, 0) & _mask(tw)
    if not lhs.idx:
        env[name] = val & _mask(tw)
        return
    if len(lhs.idx) == 1:
        i = lhs.idx[0]
        bit = val & 1
        env[name] = (cur & ~(1 << i)) | (bit << i)
        return
    hi, lo = lhs.idx
    nw = hi - lo + 1
    env[name] = (cur & ~(_mask(nw) << lo)) | ((val & _mask(nw)) << lo)


def exec_stmt(st, env, widths):
    if isinstance(st, Block):
        for s in st.stmts:
            exec_stmt(s, env, widths)
        return
    if isinstance(st, Assign):
        lw = _width(st.lhs, widths)
        v, _ = ev(st.rhs, env, widths, lw)
        assign_to(st.lhs, v, lw, env, widths)
        return
    if isinstance(st, If):
        c, _ = ev(st.cond, env, widths)
        if c:
            exec_stmt(st.then, env, widths)
        elif st.els is not None:
            exec_stmt(st.els, env, widths)
        return
    if isinstance(st, Case):
        sv, sw = ev(st.sel, env, widths)
        hit = None
        dflt = None
        for vals, body in st.items:
            if vals is None:
                dflt = body
                continue
            for v in vals:
                cv, cw = ev(v, env, widths)
                w = max(sw, cw)
                if (sv & _mask(w)) == (cv & _mask(w)):
                    hit = body
                    break
            if hit is not None:
                break
        body = hit if hit is not None else dflt
        if body is not None:
            exec_stmt(body, env, widths)
        return
    raise Unsupported("语句类型 " + type(st).__name__)


def _exec_nb(st, rd, wr, widths):
    """**非阻塞执行**：读 `rd`（时钟沿前的旧值），写 `wr`（D 端）。

    🔴 必须是双环境。E34 第一版在 `rtl_eval_all` 里用单环境顺序执行，
    于是 `scnt <= scnt+1;  if (scnt == 17) ...` 读到了**已经加过 1 的新值**
    ⇒ 完成条件整体偏移 1 拍（实测 `scnt=16` 就触发完成）。
    这是**引擎 A 错、引擎 B 对**的一次 —— 对拍的价值不是「B 一定错」，
    而是「谁错都藏不住」。
    """
    if isinstance(st, Block):
        for s in st.stmts:
            _exec_nb(s, rd, wr, widths)
        return
    if isinstance(st, Assign):
        lw = _width(st.lhs, widths)
        v, _ = ev(st.rhs, rd, widths, lw)
        assign_to(st.lhs, v, lw, wr, widths)
        return
    if isinstance(st, If):
        c, _ = ev(st.cond, rd, widths)
        if c:
            _exec_nb(st.then, rd, wr, widths)
        elif st.els is not None:
            _exec_nb(st.els, rd, wr, widths)
        return
    if isinstance(st, Case):
        sv, sw = ev(st.sel, rd, widths)
        body = None
        dflt = None
        for vals, b in st.items:
            if vals is None:
                dflt = b
                continue
            for v in vals:
                cv, cw = ev(v, rd, widths)
                w = max(sw, cw)
                if (sv & _mask(w)) == (cv & _mask(w)):
                    body = b
                    break
            if body is not None:
                break
        b = body if body is not None else dflt
        if b is not None:
            _exec_nb(b, rd, wr, widths)
        return
    raise Unsupported("语句类型 " + type(st).__name__)


def rtl_eval_all(m: Module, pin: dict, max_iter: int = 400) -> dict:
    """**引擎 A**：给定主输入 + 状态当前值，求所有输出与各状态寄存器的 D 端。

    `pin` 的键：主输入名 · 状态寄存器名 + `"@q"`（缺省退化为 `pin[name]`）。
    返回：主输出（多位 int）+ `"<reg>@d"`。
    """
    widths = m.widths
    env = {}
    for nm in m.inputs:
        env[nm] = pin.get(nm, 0) & _mask(widths.get(nm, 1))
    for s in m.state_regs:
        env[s] = pin.get(s + "@q", pin.get(s, 0)) & _mask(widths.get(s, 1))

    prev = None
    for _ in range(max_iter):
        for lhs, rhs in m.assigns:
            lw = _width(lhs, widths)
            v, _ = ev(rhs, env, widths, lw)
            assign_to(lhs, v, lw, env, widths)
        for st in m.comb:
            exec_stmt(st, env, widths)
        snap = tuple(sorted(env.items()))
        if snap == prev:
            break
        prev = snap
    else:
        raise Unsupported("组合逻辑在 %d 轮内未收敛（疑似组合环）" % max_iter)

    out = {}
    for nm in m.outputs:
        out[nm] = env.get(nm, 0) & _mask(widths.get(nm, 1))
    # 时序块：**读旧值快照、写新值副本**（非阻塞语义）
    if m.state_regs:
        pre = dict(env)
        wr = dict(env)
        for _, st in m.seq:
            _exec_nb(st, pre, wr, widths)
        for s in m.state_regs:
            out[s + "@d"] = wr.get(s, env.get(s, 0)) & _mask(widths.get(s, 1))
    return out


def parse(src: str) -> Module:
    return Parser(tokenize(src)).parse_module()


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
_SELFTEST_SRC = """
module t(a, b, y);
  input  [3:0] a;
  input  [3:0] b;
  output [4:0] y;
  assign y = a + b;
endmodule
"""


def drtl_self_check() -> dict:
    """前端最小自检：解析 / 位宽 / `~0` 的 32 位语义。"""
    problems = []
    m = parse(_SELFTEST_SRC)
    if m.widths["y"] != 5:
        problems.append(("width_y", m.widths["y"]))
    got = rtl_eval_all(m, {"a": 15, "b": 1})["y"]
    if got != 16:
        problems.append(("adder_15p1", got))

    # 🔴 `~0` 必须是 32 位全 1，赋给 4 位信号 ⇒ 15（不是 1）
    m2 = parse("""
module n(y);
  output [3:0] y;
  assign y = ~0;
endmodule
""")
    v = rtl_eval_all(m2, {})["y"]
    if v != 15:
        problems.append(("tilde_zero_is_32b", v))

    # 状态寄存器外提成一级输入
    m3 = parse("""
module c(clk, d, q);
  input clk; input d; output q;
  reg q;
  always @(posedge clk) begin q <= d; end
endmodule
""")
    a = rtl_eval_all(m3, {"clk": 1, "d": 1, "q@q": 0})
    if a["q@d"] != 1 or a["q"] != 0:
        problems.append(("dff_semantics", a["q@d"], a["q"]))

    # 🔴 非阻塞语义：**先写后读同一信号必须读到旧值**
    #    y<=y+1; if (y==3) y<=0;  在 y=2 时应得 3（if 读到旧值 2，不成立）
    #    若读新值（3）则得 0 —— E34 第一版正是这样，完成条件整体偏 1 拍。
    m4 = parse("""
module nb(clk, y);
  input clk; output [1:0] y; reg [1:0] y;
  always @(posedge clk) begin
    y <= y + 2'd1;
    if (y == 2'd3) y <= 2'd0;
  end
endmodule
""")
    if rtl_eval_all(m4, {"clk": 1, "y@q": 2})["y@d"] != 3:
        problems.append(("nonblocking_reads_old", rtl_eval_all(m4, {"clk": 1, "y@q": 2})["y@d"]))
    if rtl_eval_all(m4, {"clk": 1, "y@q": 3})["y@d"] != 0:
        problems.append(("nonblocking_last_wins", rtl_eval_all(m4, {"clk": 1, "y@q": 3})["y@d"]))

    return {"ok": not problems, "problems": problems}


DRTL_DISCLOSURE = {
    "route": "E34 · 数字控制壳自主建 · 第 1 层（可综合 Verilog 子集前端 + RTL 解释器）",
    "subset": "non-ANSI 单模块 · [N-1:0] 向量 · assign/always@(*)/always@(posedge) · "
              "if/case/begin-end · 位选/部分选择/拼接/复制 · "
              "运算符 ~ ! - & | ^ ~^ << >> + - == != < <= > >= && || ?:",
    "not_included": "乘法/除法/取模/算术移位 · 层次实例化 · generate · 数组/存储器 · 有符号数 · "
                    "函数/任务 · for/while · 延迟 · 三态 · x/z 传播 · 多时钟/异步复位",
    "width_rule": "无宽度十进制常数 = 32 位（Verilog 规则）⇒ ~0 = 0xFFFF_FFFF；"
                  "算术/位运算 max(wl,wr)；比较/逻辑 =1；移位 = wl；赋值截断",
    "seq_semantics": "状态外提为一级输入（sig@q）· next 单列（sig@d）⇒ 等价性是**纯组合**的；"
                     "多周期复位序列等价**不在本段范围**",
    "engine_roles": "本模块 = 引擎 A（Python 原生整数按位运算）；dsynth.sim_netlist = 引擎 B（逐单元查表）",
    "claimable": True,
    "claimable_reason": "语言子集的解析/位宽/时序语义由穷举对拍机核（dequiv），不依赖工艺参数",
}
