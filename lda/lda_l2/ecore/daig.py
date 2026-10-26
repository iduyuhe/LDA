# -*- coding: utf-8 -*-
"""E34 · **AIG 布尔网络**（`lda/lda_l2/ecore/daig.py` · D-211）。

══════════════════════════════════════════════════════════════════════════
定位：综合器的「中间表示」—— 让「逻辑」与「门」解耦
══════════════════════════════════════════════════════════════════════════
商业综合器分「与反相图（AIG）→ 优化 → 技术映射」两步，本模块做第一步。
AIG 只有一种节点（2 输入 AND）和一个自由的反相边 ⇒ 任何布尔表达式都能表示，
且**结构哈希去重**能让「同一个子函数只算一次」这一点变成机器保证而非人工约定。

══════════════════════════════════════════════════════════════════════════
🔴 编码约定（错了会静默算错，所以写死在这里）
══════════════════════════════════════════════════════════════════════════
    lit = 2*node + inv       inv=1 表示「取反」
    lit 0 = 常数 0           lit 1 = 常数 1（= NOT(0)）
    节点 0 = 常数占位        节点号从 1 起：先分配给输入，再分配给 AND

⇒ **AND(a,b) 返回的 lit 恒为 inv=0**（非反相），因为 AIG 节点本身是 AND。
⇒ 反相不花节点，只花 `lit ^ 1`。

══════════════════════════════════════════════════════════════════════════
🔴 为什么优化必须是「恒等式重写」而不是「启发式猜测」
══════════════════════════════════════════════════════════════════════════
本模块只做**可证明等价**的重写（常数传播 / 幂等 / 互补 / 结构哈希），
以及**可证明等价**的平衡（AND 结合律）。任何「可能更省但不保证等价」的
变换一律不做 —— 因为等价性是 E34 的绝对判据，**优化不能污染它**。

`AND` 的化简表（每一条都是布尔恒等式，不是经验规则）：

    AND(0,x)=0   AND(1,x)=x   AND(x,x)=x   AND(x,~x)=0

⭐ 这张表同时是**判别力的来源**：如果它没生效，`dequiv` 的穷举对拍会抓到
（因为网表会真的算出不同的值）；如果它错了一条，穷举也会抓到。
⇒ 优化器**不需要单独的单元测试**，它被绝对对拍覆盖。这是本段的设计选择：
**能放进绝对判据的东西，不再单独写一条弱判据。**
"""
from __future__ import annotations

C0 = 0
C1 = 1


class Aig:
    """与反相图。节点表 `kind[i]` ∈ {"const","input","and"}。"""

    __slots__ = ("kind", "fan", "_h", "_n_and")

    def __init__(self):
        self.kind = ["const"]      # index 0 = 常数占位
        self.fan = [(0, 0)]
        self._h = {}
        self._n_and = 0

    # -- 构造 --------------------------------------------------------------
    def inp(self) -> int:
        """新建输入节点，返回其**非反相** lit。"""
        self.kind.append("input")
        self.fan.append((0, 0))
        return (len(self.kind) - 1) << 1

    @property
    def n_inputs(self) -> int:
        return sum(1 for k in self.kind if k == "input")

    @property
    def n_ands(self) -> int:
        return self._n_and

    def AND(self, a: int, b: int) -> int:
        if a == C0 or b == C0:
            return C0
        if a == C1:
            return b
        if b == C1:
            return a
        if a == b:
            return a
        if a == (b ^ 1):
            return C0
        key = (a, b) if a <= b else (b, a)
        hit = self._h.get(key)
        if hit is not None:
            return hit
        self.kind.append("and")
        self.fan.append(key)
        lit = (len(self.kind) - 1) << 1
        self._h[key] = lit
        self._n_and += 1
        return lit

    # -- 派生（全部由 AND + 反相边构成） -----------------------------------
    def NOT(self, a: int) -> int:
        return a ^ 1

    def OR(self, a: int, b: int) -> int:
        return self.AND(a ^ 1, b ^ 1) ^ 1

    def XOR(self, a: int, b: int) -> int:
        if a == b:
            return C0
        if a == (b ^ 1):
            return C1
        if a == C0:
            return b
        if a == C1:
            return b ^ 1
        if b == C0:
            return a
        if b == C1:
            return a ^ 1
        return self.OR(self.AND(a, b ^ 1), self.AND(a ^ 1, b))

    def XNOR(self, a: int, b: int) -> int:
        return self.XOR(a, b) ^ 1

    def MUX(self, s: int, a: int, b: int) -> int:
        """`s ? a : b`。"""
        if a == b:
            return a
        if s == C1:
            return a
        if s == C0:
            return b
        if a == C1 and b == C0:
            return s
        return self.OR(self.AND(s, a), self.AND(s ^ 1, b))

    def is_const(self, lit: int) -> bool:
        return lit <= C1

    # -- 遍历 --------------------------------------------------------------
    def and_nodes(self):
        """按**节点号升序**（= 拓扑序）产出 `(node, lit_noninv, la, lb)`。"""
        for i in range(1, len(self.kind)):
            if self.kind[i] == "and":
                la, lb = self.fan[i]
                yield i, i << 1, la, lb

    def depth(self, lit: int, memo=None) -> int:
        """到常数的最大 AND 级数（逻辑深度）。"""
        memo = {} if memo is None else memo
        if self.is_const(lit):
            return 0
        node = lit >> 1
        if node in memo:
            return memo[node]
        if self.kind[node] == "input":
            memo[node] = 0
            return 0
        la, lb = self.fan[node]
        d = 1 + max(self.depth(la, memo), self.depth(lb, memo))
        memo[node] = d
        return d

    def stats(self) -> dict:
        return {
            "n_inputs": self.n_inputs,
            "n_ands": self._n_and,
            "n_nodes": len(self.kind) - 1,
        }


# ---------------------------------------------------------------------------
# 位向量级辅助（bit list · **LSB first**）
# ---------------------------------------------------------------------------
def red_or(g: Aig, bs):
    """OR 归约。空向量 ⇒ 常数 0（`any([]) = False` 的硬件对应）。"""
    if not bs:
        return C0
    while len(bs) > 1:
        nxt = []
        for i in range(0, len(bs) - 1, 2):
            nxt.append(g.OR(bs[i], bs[i + 1]))
        if len(bs) & 1:
            nxt.append(bs[-1])
        bs = nxt
    return bs[0]


def red_and(g: Aig, bs):
    """AND 归约。空向量 ⇒ 常数 1（`all([]) = True` 的硬件对应）——
    🔴 E30 曾在 Python 侧被 `all([])` 恒真坑过一次，这里显式写清空向量的语义。"""
    if not bs:
        return C1
    return red_or(g, [b ^ 1 for b in bs]) ^ 1


def eq_bits(g: Aig, a, b):
    """两个等宽位向量是否相等。"""
    return red_and(g, [g.XNOR(a[i], b[i]) for i in range(len(a))])


def ult_bits(g: Aig, a, b):
    """无符号 `a < b`。

    🔴 **累积方向必须从 LSB 往 MSB**：`lt_i = (a_i<b_i) OR (a_i==b_i AND lt_{i-1})`。
    E34 第一版写成从 MSB 往下（`range(w-1,-1,-1)`）⇒ 比较方向反了
    （实测 `2 < 1` 判为真），被 `dequiv` 的穷举当场抓出。
    这类错误**任何比值判据都看不见** —— 它只让某一半向量错。
    """
    w = len(a)
    lt = C0
    for i in range(w):
        lt = g.OR(g.AND(a[i] ^ 1, b[i]), g.AND(g.XNOR(a[i], b[i]), lt))
    return lt


def add_bits(g: Aig, x, y):
    """等宽无符号加法（行波进位），返回 w 位和（**丢弃最终进位** —— Verilog 语义）。"""
    s = []
    c = C0
    for i in range(len(x)):
        h = g.XOR(x[i], y[i])
        s.append(g.XOR(h, c))
        c = g.OR(g.AND(x[i], y[i]), g.AND(h, c))
    return s


def mux_bits(g: Aig, s, a, b):
    return [g.MUX(s, a[i], b[i]) for i in range(len(a))]


def const_bits(v: int, w: int):
    return [C1 if (v >> i) & 1 else C0 for i in range(w)]


def bits_value(bs) -> int:
    """把常数位向量还原成整数（非全常数会抛错）。"""
    v = 0
    for i, b in enumerate(bs):
        if not (b <= C1):
            raise ValueError("非常数位向量")
        if b == C1:
            v |= 1 << i
    return v


DAIG_DISCLOSURE = {
    "route": "E34 · 数字控制壳自主建 · 第 2 层（AIG 布尔网络）",
    "ops": "AND（唯一节点）· NOT/OR/XOR/XNOR/MUX（派生）· 归约 · 相等 · 无符号小于 · 行波加法",
    "optimizations": "常数传播 · 幂等 AND(x,x)=x · 互补 AND(x,~x)=0 · 结构哈希 CSE · "
                     "AND 结合律平衡（`dsta` 用其深度）",
    "no_unsafe_opt": "不做任何「可能更省但不保证等价」的变换（不重构时序、不改状态编码）",
    "known_open": "未做 SAT sweeping / 重写（rewrite）引擎 ⇒ 门数高于商业综合器；"
                  "这一差距是**公开承认**的，不以「面积接近」表述",
}
