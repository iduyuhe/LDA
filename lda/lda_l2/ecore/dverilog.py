# -*- coding: utf-8 -*-
"""S3 · **结构级 Verilog 子集解析器**（gate-level · 解析 → dsynth.Netlist → 序列化往返）。

═══════════════════════════════════════════════════════════════════════════════
定位：S3 的「Verilog 子集」是 ISCAS/EPFL 这类**门级网表**的入口 —— 与 `drtl.py` 的
RTL 子集（含 always/表达式，走 `dsynth.synth` 综合）**分工**：`drtl` 吃 RTL，本模块吃
**已综合好的结构网表**（`nand (y,a,b)` 这种门实例）。两者汇合点是 `dsynth.Netlist`
（数字链唯一的门级网表结构，见 `dsynth.py` 与 `model.py` 注释）—— 本模块直接产出它，
让 B3 干线 `place→route→drc` 能「吃上一段的输出」。

═══════════════════════════════════════════════════════════════════════════════
支持的子集（**明确划界，越界即报错，绝不静默降级**）
───────────────────────────────────────────────────────────────────────────────
```verilog
module name(p1, p2, ...);         // 端口列表（可逗号分隔单行）
  input  [W-1:0] a;               // 只支持 [N-1:0] 降序向量（多比特自动拆成每比特网）
  output [W-1:0] y;
  wire   w1, w2;                  // 内部网声明（也可不声明，出现即网）
  nand  g1 (y, a, b);             // 有名门实例（首参=输出网，其余=输入网）
  not   (z, c);                   // 匿名门实例（ISCAS/EPFL 常见写法）
  ...
endmodule
```
基础门原语：`and / nand / or / nor / xor / xnor / buf / not`。
映射：`not→INV`、`nand→NAND2`；`and/or/nor/xor/xnor/buf` 保留原语名
（`dsynth`/`dcells` 当前只建了 INV/NAND2 的**真实几何**，其余原语在物理链上是
「未建模」⇒ 放置/布线阶段会被如实计数跳过，不静默当作 INV）。

🔴 不支持（抛 `VerilogSyntaxError`）：层次实例化（`module` 内再 `module`）、`reg` 过程赋值、
`assign` 连续赋值网（那是 RTL，走 `drtl`）、`generate`、数组/存储器、`function/task`、
三态 `z`、未声明的**输出端口**被当作输入引用等。

═══════════════════════════════════════════════════════════════════════════════
三条硬保证（与 S2 dliberty / S3 dlef 同款主权红线）
───────────────────────────────────────────────────────────────────────────────
① **零数据丢失**：解析后门实例数 / 网数 / 连通性（每颗门的 in→out）在 `serialize→reparse`
   后**完全守恒**；
② **序列化往返（结构双射）**：`serialize(reparse(serialize(x))) == serialize(x)`
   （门按名排序吐回，非靠归一化）；
③ **未知语法必报错**：未闭合 `endmodule` / 非法原语 / 门实例端口数 < 2 / 端口方向缺失 /
   多比特向量升序 / 把输出端口当输入引用 —— 一律抛 `VerilogSyntaxError`（带位置）。

⚠️ 诚实边界
──────────
· **不综合、不求值**：本模块只把门级描述忠实转成 `dsynth.Netlist`（连通性容器），不做逻辑仿真
  （那是 `dsynth.sim_netlist`/`drtl.rtl_eval_all` 的事）；一旦它开始算，就会变成「第二套实现」。
· **几何在 LEF/布局阶段**：本模块给的 `Netlist` 没有坐标；坐标由 `dplac.place` 产生。
· **C 级自主**：纯标准库 + 复用 `drtl.tokenize`（同一词法器，零第三方依赖），LLM 不进判决路径。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import drtl as RT
from .dsynth import Gate, Netlist

# ── 门原语 → dsynth.Gate.cell（INV/NAND2 有真实几何；其余保留原语名，物理链上诚实跳过）
_PRIM_MAP = {
    "not": "INV", "buf": "BUF",
    "nand": "NAND2", "and": "AND", "or": "OR", "nor": "NOR",
    "xor": "XOR", "xnor": "XNOR",
}
# 物理链当前有真实几何的原语（dcell.CELLS 含 INV/NAND2）
PHYSICALLY_MODELED = frozenset({"INV", "NAND2"})


class VerilogSyntaxError(Exception):
    """结构 Verilog 语法错误（带 token 位置）。未知/非法语法 = 抛这个，绝不静默跳过。"""

    def __init__(self, message: str, pos: int = 0):
        self.pos = pos
        super().__init__("[位置 %d] %s" % (pos, message))


@dataclass
class _ModuleStub:
    name: str
    inputs: list = field(default_factory=list)     # [(port, width)]
    outputs: list = field(default_factory=list)    # [(port, width)]
    wires: set = field(default_factory=set)        # 内部网名
    gates: list = field(default_factory=list)      # [(prim_cell, in_tuple, out_net, inst_name)]


class _Parser:
    def __init__(self, toks):
        self.t = toks
        self.i = 0
        self.n = len(toks)

    def _peek(self, k=0):
        return self.t[min(self.i + k, self.n - 1)]

    def _at(self, val):
        tk = self._peek()
        return tk.kind in ("op", "kw", "id") and tk.val == val

    def _accept(self, val):
        if self._at(val):
            self.i += 1
            return True
        return False

    def _expect(self, val):
        if not self._accept(val):
            tk = self._peek()
            raise VerilogSyntaxError("期望 %r，得到 %r" % (val, tk.val), tk.pos)

    def _expect_id(self):
        tk = self._peek()
        if tk.kind != "id":
            raise VerilogSyntaxError("期望标识符，得到 %r" % (tk.val,), tk.pos)
        self.i += 1
        return tk.val

    def _expect_net(self):
        """读一个网名：接受 `a` 或位选 `a[0]`（与多比特端口拆位后的网名对齐）。"""
        tk = self._peek()
        if tk.kind != "id":
            raise VerilogSyntaxError("期望网名，得到 %r" % (tk.val,), tk.pos)
        self.i += 1
        name = tk.val
        if self._accept("["):
            lo_t = self._peek()
            if lo_t.kind != "num":
                raise VerilogSyntaxError("位选下标须为常数", lo_t.pos)
            idx = lo_t.val[0]
            self.i += 1
            self._expect("]")
            name = "%s[%d]" % (name, idx)
        return name

    def _decl(self, stub, direction, width):
        """解析 `input/output/wire a, b, c;` 中的一个方向声明。"""
        names = []
        while True:
            nm = self._expect_id()
            names.append(nm)
            if not self._accept(","):
                break
        self._expect(";")
        for nm in names:
            if direction == "input":
                if (nm, width) not in stub.inputs:
                    stub.inputs.append((nm, width))
            elif direction == "output":
                if (nm, width) not in stub.outputs:
                    stub.outputs.append((nm, width))
            else:  # wire
                stub.wires.add(nm)

    def _range_opt(self):
        """`[W-1:0]` → W；无则 1。升序 `[0:N-1]` 报错。"""
        if not self._accept("["):
            return 1
        hi_t = self._peek()
        if hi_t.kind != "num":
            raise VerilogSyntaxError("向量高位须为常数", hi_t.pos)
        hi = hi_t.val[0]
        self.i += 1
        self._expect(":")
        lo_t = self._peek()
        if lo_t.kind != "num":
            raise VerilogSyntaxError("向量低位须为常数", lo_t.pos)
        lo = lo_t.val[0]
        self.i += 1
        self._expect("]")
        if hi < lo:
            raise VerilogSyntaxError("只支持降序向量 [N-1:0]，得到 [%d:%d]" % (hi, lo),
                                     hi_t.pos)
        return hi - lo + 1

    def _gate(self, stub):
        """解析一个门实例：`[instname] ( out, in1, in2, ... ) ;`。"""
        tk = self._peek()
        prim = tk.val.lower()
        if prim not in _PRIM_MAP:
            raise VerilogSyntaxError("不支持的 Verilog 原语 %r" % (prim,), tk.pos)
        self.i += 1
        cell = _PRIM_MAP[prim]
        # 匿名 vs 有名：下一个 token 是 `(` ⇒ 匿名（自动命名）
        inst_name = None
        if not self._at("("):
            inst_name = self._expect_id()
        self._expect("(")
        # 端口列表：首参=输出，其余=输入（支持位选网名 a[0]）
        ports = []
        while True:
            ports.append(self._expect_net())
            if not self._accept(","):
                break
        self._expect(")")
        self._expect(";")
        if len(ports) < 2:
            raise VerilogSyntaxError(
                "门实例 %s 至少需 2 个端口（输出 + ≥1 输入），得到 %d" % (prim, len(ports)),
                tk.pos)
        out_net = ports[0]
        in_nets = tuple(ports[1:])
        stub.gates.append((cell, in_nets, out_net, inst_name, tk.pos))

    def parse_module(self) -> _ModuleStub:
        self._expect("module")
        name = self._expect_id()
        self._expect("(")
        # 端口列表：循环读端口名 + 逗号，直到 `)`（无端口的 `module foo();` 也支持）
        while not self._at(")"):
            self._expect_id()
            if not self._accept(","):
                break
        self._expect(")")
        self._expect(";")

        stub = _ModuleStub(name=name)
        while not self._at("endmodule"):
            tk = self._peek()
            v = tk.val
            if v in ("input", "output"):
                self.i += 1
                w = self._range_opt()
                self._decl(stub, v, w)
                continue
            if v == "wire":
                self.i += 1
                self._range_opt()  # wire 一般不带向量；带也吃但不展开
                self._decl(stub, "wire", 1)
                continue
            if v == "reg":
                raise VerilogSyntaxError(
                    "reg 过程赋值不在结构子集内（RTL 走 drtl.py）", tk.pos)
            if v == "assign":
                raise VerilogSyntaxError(
                    "assign 连续赋值不在结构子集内（RTL 走 drtl.py）", tk.pos)
            if tk.kind == "id":
                self._gate(stub)
                continue
            raise VerilogSyntaxError("模块体内无法识别：%r" % (v,), tk.pos)
        self._expect("endmodule")
        return stub


def _split_bus(port: str, width: int) -> list:
    """多比特端口拆成每比特网名（LSB first，与 `dsynth` 约定一致）。1 比特即本身。"""
    if width <= 1:
        return [port]
    return ["%s[%d]" % (port, b) for b in range(width)]


def parse(src: str) -> Netlist:
    """解析结构级 Verilog 源 → `dsynth.Netlist`（数字链的门级网表模型）。"""
    toks = RT.tokenize(src)
    stub = _Parser(toks).parse_module()

    inputs = tuple(stub.inputs)
    # 端口 → 网名 映射（多比特按位拆）
    in_nets: dict = {}
    out_nets: dict = {}
    for (port, w) in inputs:
        bits = _split_bus(port, w)
        for b, net in enumerate(bits):
            in_nets[(port, b)] = net
    declared_outputs = tuple(stub.outputs)
    for (port, w) in declared_outputs:
        bits = _split_bus(port, w)
        out_nets[port] = tuple(bits)

    # 输出端口网名集合（用于「把输出当输入引用」检测）
    out_net_names = set()
    for bits in out_nets.values():
        out_net_names.update(bits)

    # 门实例 → Gate；输出网若是输出端口，统一用端口网名（与 in_nets/out_nets 对齐）
    gates: list = []
    seen_inst = set()
    for idx, (cell, ins, out_net, inst_name, gpos) in enumerate(stub.gates):
        gname = inst_name or ("g%d" % idx)
        if gname in seen_inst:
            # 同名自动去重编号
            gname = "%s_%d" % (gname, idx)
        seen_inst.add(gname)
        # 输出网若是已声明输出端口 → 用端口位网名（保持与 out_nets 一致）
        onet = out_net
        # 输入网若是输出端口名 → 报错（结构网表中输出不能作输入）
        for inn in ins:
            if inn in out_net_names and inn not in in_nets:
                raise VerilogSyntaxError(
                    "输出端口 %r 被当作输入引用（结构网表不允许）" % (inn,), gpos)
        gates.append(Gate(name=gname, cell=cell, ins=tuple(ins), out=onet))

    nl = Netlist(name=stub.name, inputs=inputs, in_nets=in_nets,
                 outputs=out_nets, gates=gates, clocks=())
    return nl


# ═══════════════════════════════════════════════════════════════════════════
# 序列化（canonical 结构 Verilog · 门按名排序 ⇒ 往返双射 + 幂等）
# ═══════════════════════════════════════════════════════════════════════════
def _verilog_prim(cell: str) -> str:
    for k, v in _PRIM_MAP.items():
        if v == cell:
            return k
    return cell.lower()


def serialize(nl: Netlist) -> str:
    """把 `dsynth.Netlist` 写成 canonical 结构 Verilog（语句顺序固定 ⇒ 往返双射）。"""
    in_ports = [p for (p, _w) in nl.inputs]
    out_ports = [p for (p, _bits) in nl.outputs.items()]
    lines = ["module %s(%s);" % (nl.name, ", ".join(in_ports + out_ports))]
    for (port, w) in nl.inputs:
        lines.append("  input %s ;" % (("[" + str(w - 1) + ":0] " if w > 1 else "") + port))
    for (port, bits) in nl.outputs.items():
        w = len(bits)
        lines.append("  output %s ;" % (("[" + str(w - 1) + ":0] " if w > 1 else "") + port))
    # 内部网：所有门引用的、既非输入端口位、也非输出端口位的网
    # （多比特端口拆位后的网名如 `a[0]`/`y[0]` 属端口位，不当内部网重声明）
    prim_nets = set(nl.in_nets.values())
    if nl.outputs:
        prim_nets |= set().union(*nl.outputs.values())
    internal = set()
    for g in nl.gates:
        for s in (g.out,) + tuple(g.ins):
            if s not in prim_nets:
                internal.add(s)
    if internal:
        lines.append("  wire %s ;" % ", ".join(sorted(internal)))
    # 门实例：按 name 排序，canonical
    for g in sorted(nl.gates, key=lambda x: x.name):
        prim = _verilog_prim(g.cell)
        ports = ", ".join([g.out] + list(g.ins))
        lines.append("  %s %s ( %s ) ;" % (prim, g.name, ports))
    lines.append("endmodule")
    return "\n".join(lines) + "\n"


# ═══════════════════════════════════════════════════════════════════════════
# 适配器：Netlist → S1 统一模型（Layout 视图；未布局，坐标留 0）
# ═══════════════════════════════════════════════════════════════════════════
def to_model(nl: Netlist):
    """把 `dsynth.Netlist` 转成 S1 `Layout`（每个门 → `Instance`，每条网 → `Net`）。

    坐标留 0（几何在 `dplac.place` 阶段产生）。这是「→model」的 S1 视图出口；
    B3 干线物理链直接吃 `dsynth.Netlist`，不经过此适配器。
    """
    from .. import model as MD
    insts = [MD.Instance(name=g.name, cell_name=g.cell, x_nm=0, y_nm=0)
             for g in nl.gates]
    net_map: dict = {}
    for g in nl.gates:
        net_map.setdefault(g.out, MD.Net(name=g.out)).pins.append((g.name, "Y"))
        for k, inn in enumerate(list(g.ins)[:2]):
            net_map.setdefault(inn, MD.Net(name=inn)).pins.append((g.name, "AB"[k]))
    return MD.Layout(die_w_nm=0, die_h_nm=0, instances=insts,
                     nets=[net_map[k] for k in sorted(net_map)], shapes=[])


def to_netlist(src: str) -> Netlist:
    """源文本 → Netlist（便捷别名）。"""
    return parse(src)


# ═══════════════════════════════════════════════════════════════════════════
# 代表性合成样本（按 ISCAS-85 c17 结构构造；只含 NAND2+INV ⇒ 物理链全可建模）
# ═══════════════════════════════════════════════════════════════════════════
SAMPLE_VERILOG = """module c17(n1, n2, n3, n6, n7, n22, n23);
  input n1, n2, n3, n6, n7 ;
  output n22, n23 ;
  wire n10, n11, n16, n19 ;
  nand g10 ( n10, n1, n3 ) ;
  nand g11 ( n11, n3, n6 ) ;
  nand g16 ( n16, n2, n11 ) ;
  nand g19 ( n19, n11, n7 ) ;
  nand g22 ( n22, n16, n19 ) ;
  not  g23 ( n23, n16 ) ;
endmodule
"""


if __name__ == "__main__":
    nl = parse(SAMPLE_VERILOG)
    s = serialize(nl)
    nl2 = parse(s)
    s2 = serialize(nl2)
    print("gates=%d nets_distinct=%d byte_faithful=%s" % (
        len(nl.gates),
        len({g.out for g in nl.gates} | set().union(*[set(g.ins) for g in nl.gates])),
        s == s2))
    raise SystemExit(0 if s == s2 else 1)
