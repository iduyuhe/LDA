# -*- coding: utf-8 -*-
"""S2 · **Liberty 子集解析器**（公开 PDK 的 `.lib` 读取 · 逐 cell 逐字段往返 · 未知语法必报错）。

═══════════════════════════════════════════════════════════════════════════════
定位：这是 `model.py`（S1 统一数据模型）在文档里**明确留到 B2/S2** 的那一块。
----------------------------------------------------------------------------
`model.py` 说「**不是** Liberty/LEF 解析器（那是阶段一 B2）」—— 本模块就是 B2 的
第一步：把**公开 PDK 的 `.lib`** 读进来，让 S1 的 `Pin.direction` / `TimingArc`
（以及后续 LEF 的几何）有「往哪儿填」的来源。

🔴 三条硬保证（主权红线在格式层的形式）
───────────────────────────────────────
① **逐 cell 逐字段往返一致**：`parse → serialize → re-parse` 结构**逐位相等**
   （连 NLDM 矩阵的行列数都不差），不靠「顺手归一化」偷偷变形 —— 与 S1 的 M2 同款纪律。
② **未知语法必报错、绝不静默跳过**：`define` / `type` / `group` 等**宏与类型定义指令**、
   `calc_mode` 之类的**表达式值**、**顶层非 `library` 组** → 一律抛 `LibertySyntaxError`
   （带行号）。因为「你声称读完了这个 .lib，却悄悄丢了 30% 的数据」比「读不了」更危险。
③ **零数据丢失不变量**：rich 样本 parse 后，所有 cell / pin / timing / attr 计数在
   往返后**完全守恒** —— 这把「没静默丢」从口头承诺变成机核判据。

═══════════════════════════════════════════════════════════════════════════════
支持的子集（明确边界，越界即报错）
───────────────────────────────────────
· **组**：`library / cell / pin / bus / timing / internal_power / lu_table_template /
  power_lut_template / voltage / input_voltage / output_voltage / cell_leakage_power /
  em_lut_template / delay_lut_template / scalar_template / poly_template /
  piece_wise_model / scaling_factors / nom_voltage_map / when` 等—— 全部按**通用组**读取
  （类型名只当字符串记），所以真实公开 PDK 的绝大多数数据组都能完整读入、零丢弃。
· **属性值**：`string` / `number`（含科学计数法、负号）/ `boolean` / `bareword`（标识）/ 
  `values (...)` **矩阵**（NLDM/LUT）/ `("a","b")` **字符串表**。
· **不支持（遇到即报错，不静默）**：`define` / `define_group` / `define_attribute` 宏、
  `type` / `group` / `library_domain` 等**类型/组定义指令**、`area : (2*3)` 这类**表达式值**、
  顶层出现非 `library` 的组。

⚠️ 诚实边界
──────────
· **不求值、不建模**：本模块只做「忠实读取 + 往返」，没有任何时序/功耗计算 ——
  那是 `dsta` 的事；一旦它开始算，就会变成「第二套实现」，与既有模块必然漂移。
· **几何在 LEF（S3）**：`.lib` 没有版图，所以 `to_model()` 喂给 S1 的只有 `Pin` 极性 /
  `TimingArc` 延迟，`CellView` 的尺寸留 0，等 LEF 接入。
· **非 foundry PDK**：本模块自带 `SAMPLE_LIBERTY` 是**代表性的合成子集**（按公开单元库惯例
  构造），用于机核验证；指向真实第三方 PDK 时走同一条 `parse_liberty_file()` 路径。
· **C 级自主**：纯标准库实现，零第三方依赖，LLM 不进判决路径。
"""
from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import List, Optional

LIBERTY_DISCLOSURE = {
    "route": "S2 · Liberty 子集解析（公开 PDK .lib 读取 · 逐 cell 逐字段往返 · 未知语法必报错）。",
    "s2_scope": "把 S1 统一数据模型「缺的输入源」补上：library/cell/pin/timing 等数据组全量忠实读取，"
                "未知构造（宏/类型定义/表达式值/顶层非 library）一律报错而非静默跳过；"
                "附带 to_model() 把 direction/timing_sense/cell_fall(单位换算) 喂给 S1 的 Pin/TimingArc。",
    "subset": "组：library/cell/pin/bus/timing/internal_power/lu_table_template/voltage 等通用组；"
              "值：string/number/boolean/bareword/values(矩阵)/字符串表。",
    "unsupported": "define/type/group/library_domain 宏与类型定义指令、表达式值、顶层非 library 组 —— 一律报错。",
    "honest_boundary": "只读取+往返，不求值不建模；几何在 LEF(S3)；非 foundry PDK；C 级自主纯标准库。",
}

# 明确不支持的「指令」（宏 / 类型 / 组定义）—— 这些是编译器指令而非数据，越界即报错。
UNSUPPORTED_DIRECTIVES = frozenset(
    {"define", "define_group", "define_attribute", "type", "group", "library_domain"}
)

_NUM_RE = re.compile(r"-?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?")


class LibertySyntaxError(Exception):
    """Liberty 语法错误（带行号）。未知语法 = 抛这个，绝不静默跳过。"""

    def __init__(self, message: str, line: int = 0):
        self.line = line
        super().__init__("[行 %d] %s" % (line, message))


# ══════════════════════════════════════════════════════════════════════════════
# 数据模型（保序、可结构比较）
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class LibertyValue:
    """一个属性值。

    `tag` ∈ {str, num, bool, ident, matrix, strlist}；`raw` 是**原始文本**，用于无损回写；
    `num` 是标量数值；`rows` 是矩阵（list[list[float]]）；`strs` 是字符串表（list[str]）。
    """
    tag: str
    raw: str
    num: Optional[float] = None
    rows: Optional[List[List[float]]] = None
    strs: Optional[List[str]] = None


@dataclass
class LibertyGroup:
    """一个组：`type (args) { attrs + subgroups }`。

    `args_raw` 是括号里**逐字符保留**的原始文本（含可能的引号 / `A==B` 这类条件），
    回写时原样吐回 —— 这是往返 byte-faithful 的关键。
    """
    gtype: str
    args_raw: str
    attrs: "OrderedDict[str, LibertyValue]"
    groups: List["LibertyGroup"]
    line: int = 0

    def name(self) -> Optional[str]:
        """组的第一参数（cell/pin/bus 名）；匿名组（如 `timing ()`）返回 None。"""
        s = self.args_raw.strip()
        if not s:
            return None
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            return s[1:-1]
        return s

    def subgroups(self, gtype: str) -> List["LibertyGroup"]:
        return [g for g in self.groups if g.gtype == gtype]


@dataclass
class LibertyLibrary:
    """解析产物：一个 library 的全部内容。"""
    name: str
    attrs: "OrderedDict[str, LibertyValue]"
    top_groups: List[LibertyGroup]

    @property
    def cells(self) -> "OrderedDict[str, LibertyGroup]":
        return OrderedDict((g.name(), g) for g in self.top_groups if g.gtype == "cell")

    @property
    def templates(self) -> "OrderedDict[str, LibertyGroup]":
        return OrderedDict(
            (g.name(), g)
            for g in self.top_groups
            if g.gtype in ("lu_table_template", "power_lut_template",
                           "delay_lut_template", "scalar_template", "poly_template")
        )


# ══════════════════════════════════════════════════════════════════════════════
# 词法分析
# ══════════════════════════════════════════════════════════════════════════════
def _tokenize(text: str):
    """把文本切成 (kind, text, line, start, end) 序列；kind ∈ str/num/ident/punct。

    注释（`/* */`、`//`）与续行符（`\\`）被吞掉但行号累计；字符串/数字带原始终止偏移，
    供括号内容的逐字符还原。
    """
    tokens = []
    i, n, line = 0, len(text), 1
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c in " \t\r":
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            if j == -1:
                raise LibertySyntaxError("块注释未闭合", line)
            line += text[i:j].count("\n")
            i = j + 2
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            if j == -1:
                i = n
            else:
                line += 1
                i = j + 1
            continue
        if c == "\\":  # 续行符（Liberty 矩阵常用）
            j = text.find("\n", i)
            if j == -1:
                i = n
            else:
                line += 1
                i = j + 1
            continue
        if c == '"':
            start, i = i, i + 1
            buf = ['"']
            while i < n:
                if text[i] == "\\" and i + 1 < n:
                    buf.append(text[i]); buf.append(text[i + 1]); i += 2
                    continue
                if text[i] == '"':
                    buf.append('"'); i += 1
                    break
                buf.append(text[i]); i += 1
            else:
                raise LibertySyntaxError("字符串未闭合", line)
            tokens.append(("str", "".join(buf), line, start, i))
            continue
        m = _NUM_RE.match(text, i)
        if m:
            tokens.append(("num", m.group(), line, m.start(), m.end()))
            i = m.end()
            continue
        if c.isalpha() or c == "_":
            start, j = i, i
            while j < n and (text[j].isalnum() or text[j] in "_$"):
                j += 1
            tokens.append(("ident", text[start:j], line, start, j))
            i = j
            continue
        if c in "(){};:,":
            tokens.append(("punct", c, line, i, i + 1))
            i += 1
            continue
        raise LibertySyntaxError("无法识别的字符 '%s'" % c, line)
    return tokens


def _looks_like_expression(raw: str) -> bool:
    """括号值里出现运算符/嵌套括号（而非数字或引号字符串）→ 视为表达式值，必须拒绝。"""
    in_q = False
    for i, ch in enumerate(raw):
        if ch == '"':
            in_q = not in_q
            continue
        if in_q:
            continue
        if ch in "*/=<>!%^&|()":
            return True
        if ch == "+":
            return True
        if ch == "-" and i > 0 and raw[i - 1].isdigit():
            return True
    return False


def _split_top_commas(s: str) -> List[str]:
    """按顶层逗号切分（引号内逗号不切），每个字段去除首尾空白。

    不 strip 会让 ` "a"` 这类带前导空格的字段在 strlist 判定（`startswith('"')`）时漏判，
    从而把字符串表误当成普通括号值 —— 这正是 SAMPLE 的 `library_features` 序列化丢括号的根因。
    """
    out, cur, in_q = [], [], False
    for ch in s:
        if ch == '"':
            in_q = not in_q
            cur.append(ch)
        elif ch == "," and not in_q:
            out.append("".join(cur).strip()); cur = []
        else:
            cur.append(ch)
    if cur:
        out.append("".join(cur).strip())
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 语法分析（递归下降）
# ══════════════════════════════════════════════════════════════════════════════
class _Parser:
    def __init__(self, tokens, src: str):
        self.tokens = tokens
        self.src = src
        self.pos = 0

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _err(self, msg: str, line: int = 0):
        if line == 0:
            tk = self._peek()
            if tk is not None:
                line = tk[2]
        raise LibertySyntaxError(msg, line)

    def parse_document(self) -> List[LibertyGroup]:
        groups: List[LibertyGroup] = []
        while self.pos < len(self.tokens):
            tk = self.tokens[self.pos]
            if tk[0] == "punct" and tk[1] == "}":
                self._err("多余的 '}'")
            if tk[0] != "ident":
                self._err("顶层期望组名，得到 '%s'" % tk[1])
            groups.append(self.parse_group())
        return groups

    def _read_paren_raw(self) -> str:
        open_t = self.tokens[self.pos]
        if not (open_t[0] == "punct" and open_t[1] == "("):
            self._err("期望 '('")
        start = open_t[4]          # '(' 的结束偏移 —— 内容起点
        depth, self.pos = 1, self.pos + 1
        while self.pos < len(self.tokens):
            tk = self.tokens[self.pos]
            if tk[0] == "punct" and tk[1] == "(":
                depth += 1
            elif tk[0] == "punct" and tk[1] == ")":
                depth -= 1
                if depth == 0:
                    end = tk[3]   # ')' 的起始偏移 —— 内容终点
                    self.pos += 1
                    # 去掉 Liberty 的行续接符 `\` + 换行（矩阵常用），否则会污染值解析。
                    return re.sub(r"\\\r?\n", "", self.src[start:end])
            self.pos += 1
        raise LibertySyntaxError("括号未闭合", open_t[2])

    def parse_group(self) -> LibertyGroup:
        t0 = self.tokens[self.pos]
        if t0[0] != "ident":
            self._err("期望组名")
        if t0[1] in UNSUPPORTED_DIRECTIVES:
            self._err("不支持的指令 '%s'（宏/类型定义不在子集内，拒绝静默跳过）" % t0[1], t0[2])
        gtype, line = t0[1], t0[2]
        self.pos += 1
        args_raw = ""
        tk = self._peek()
        if tk and tk[0] == "punct" and tk[1] == "(":
            args_raw = self._read_paren_raw()
        tk = self._peek()
        if tk and tk[0] == "punct" and tk[1] == "{":
            self.pos += 1
            attrs, subs = self.parse_body()
            close = self._peek()
            if close and close[0] == "punct" and close[1] == "}":
                self.pos += 1
            else:
                self._err("组 '%s' 未闭合 '}'" % gtype)
            return LibertyGroup(gtype, args_raw, attrs, subs, line)
        if tk and tk[0] == "punct" and tk[1] == ";":
            self.pos += 1
            return LibertyGroup(gtype, args_raw, OrderedDict(), [], line)
        self._err("组 '%s' 后期望 '{' 或 ';'" % gtype)

    def parse_body(self):
        attrs: "OrderedDict[str, LibertyValue]" = OrderedDict()
        subs: List[LibertyGroup] = []
        while self.pos < len(self.tokens):
            tk = self.tokens[self.pos]
            if tk[0] == "punct" and tk[1] == "}":
                break
            if tk[0] != "ident":
                self._err("组内期望属性名或子组，得到 '%s'" % tk[1])
            name = tk[1]
            if name in UNSUPPORTED_DIRECTIVES:
                self._err("不支持的指令 '%s'" % name, tk[2])
            nxt = self.tokens[self.pos + 1] if self.pos + 1 < len(self.tokens) else None
            if nxt is None:
                self._err("属性 '%s' 后无内容" % name)
            if nxt[0] == "punct" and nxt[1] == ":":
                self.pos += 2
                val = self.parse_value()
                semi = self._peek()
                if semi and semi[0] == "punct" and semi[1] == ";":
                    self.pos += 1
                else:
                    self._err("属性 '%s' 后缺 ';'" % name)
                attrs[name] = val
            elif nxt[0] == "punct" and nxt[1] == "(":
                # 读括号内容；括号后跟 '{' = 组，跟 ';' = 括号值属性（如 values/index_1/capacitive_load_unit）。
                self.pos += 1  # 消费 name
                args_raw = self._read_paren_raw()
                after = self._peek()
                if after and after[0] == "punct" and after[1] == "{":
                    subs.append(self._parse_group_after_paren(name, args_raw, tk[2]))
                elif after and after[0] == "punct" and after[1] == ";":
                    self.pos += 1
                    attrs[name] = _parse_paren_value(args_raw, tk[2])
                else:
                    self._err("属性/组 '%s' 后期望 '{' 或 ';'" % name)
            else:
                self._err("属性 '%s' 后期望 ':' 或 '('" % name)
        return attrs, subs

    def _parse_group_after_paren(self, gtype: str, args_raw: str, line: int) -> LibertyGroup:
        """括号已读完且紧跟 '{'：按组解析 body。"""
        if gtype in UNSUPPORTED_DIRECTIVES:
            self._err("不支持的指令 '%s'（宏/类型定义不在子集内，拒绝静默跳过）" % gtype, line)
        self.pos += 1  # 消费 '{'
        body_attrs, body_subs = self.parse_body()
        close = self._peek()
        if close and close[0] == "punct" and close[1] == "}":
            self.pos += 1
        else:
            self._err("组 '%s' 未闭合 '}'" % gtype)
        return LibertyGroup(gtype, args_raw, body_attrs, body_subs, line)

    def parse_value(self) -> LibertyValue:
        tk = self._peek()
        if tk is None:
            self._err("属性值缺失")
        if tk[0] == "str":
            self.pos += 1
            return LibertyValue("str", tk[1])
        if tk[0] == "num":
            self.pos += 1
            return LibertyValue("num", tk[1], float(tk[1]))
        if tk[0] == "ident":
            self.pos += 1
            if tk[1] in ("true", "false"):
                return LibertyValue("bool", tk[1], tk[1] == "true")
            return LibertyValue("ident", tk[1])
        if tk[0] == "punct" and tk[1] == "(":
            raw = self._read_paren_raw()
            return _parse_paren_value(raw, tk[2])
        self._err("无法识别的属性值 '%s'" % tk[1])

    def _parse_paren_value(self, raw: str, line: int) -> LibertyValue:
        # 委托给模块级函数（to_model 也要复用，解析 `values (...)` 这样的括号组）。
        return _parse_paren_value(raw, line)


def _parse_paren_value(raw: str, line: int) -> LibertyValue:
    """解析括号值：矩阵 / 字符串表 / 合法字面量 / 表达式值（拒绝）。模块级，供 parser 与 adapter 共用。"""
    s = raw.strip()
    if not s:
        raise LibertySyntaxError("空括号值", line)
    fields = _split_top_commas(s)
    rows: List[List[float]] = []
    cur: List[float] = []
    is_matrix = True
    for f in fields:
        f = f.strip()
        if f.startswith('"') and f.endswith('"') and len(f) >= 2:
            if cur:
                rows.append(cur); cur = []
            inner = f[1:-1]
            parts = [p.strip() for p in inner.split(",") if p.strip() != ""]
            try:
                rows.append([float(p) for p in parts])
            except ValueError:
                is_matrix = False
                break
        else:
            try:
                cur.append(float(f))
            except ValueError:
                is_matrix = False
                break
    if is_matrix:
        if cur:
            rows.append(cur)
        if rows and all(r for r in rows):
            return LibertyValue("matrix", s, rows=rows)
    # 退路：全引号字符串表（如 library_features ( "a", "b" )）
    if fields and all(f.startswith('"') and f.endswith('"') and len(f) >= 2
                      for f in fields):
        return LibertyValue("strlist", s, strs=[f[1:-1] for f in fields])
    # 兜底：合法字面量括号值（如 capacitive_load_unit ( 1.0, "pf" )）；
    # 含运算符/嵌套括号的（如 area : (2*3)）→ 明确拒绝，不静默吞掉。
    if _looks_like_expression(s):
        raise LibertySyntaxError(
            "不支持的属性值形式（表达式值）: (%s)" % s, line)
    return LibertyValue("paren", s)


def parse_liberty(text: str) -> LibertyLibrary:
    """解析一段 `.lib` 文本 → `LibertyLibrary`。

    顶层只允许**一个** `library` 组（公开 PDK 的常态）；否则报错。
    """
    toks = _tokenize(text)
    doc = _Parser(toks, text).parse_document()
    libs = [g for g in doc if g.gtype == "library"]
    if not libs:
        raise LibertySyntaxError("未找到 library 组")
    if len(doc) > 1:
        raise LibertySyntaxError("顶层只支持单个 library 组（得到 %d 个顶层组）" % len(doc))
    lib = libs[0]
    return LibertyLibrary(name=lib.name() or "", attrs=lib.attrs, top_groups=lib.groups)


def parse_liberty_file(path: str) -> LibertyLibrary:
    """从文件读取并解析（公开 PDK 的 `.lib` 走这条路径）。"""
    with open(path, "r", encoding="utf-8") as fh:
        return parse_liberty(fh.read())


# ══════════════════════════════════════════════════════════════════════════════
# 序列化（byte-faithful 回写）
# ══════════════════════════════════════════════════════════════════════════════
def _fmt_num(x: float) -> str:
    return format(x, ".12g")


def _emit_value(v: LibertyValue) -> str:
    if v.tag in ("str", "num", "bool", "ident"):
        return v.raw
    if v.tag == "matrix" and v.rows is not None:
        rows = ", ".join('"' + ", ".join(_fmt_num(x) for x in r) + '"'
                         for r in v.rows)
        return "( %s )" % rows
    if v.tag == "strlist" and v.strs is not None:
        return "( %s )" % ", ".join('"%s"' % s for s in v.strs)
    if v.tag == "paren":
        # 括号值（如 `capacitive_load_unit ( 1.0, "pf" )`）回写必须保留括号，
        # 否则 `: 1.0, "pf"` 重解析只会吃到 1.0 然后撞到逗号。
        return "( %s )" % v.raw
    return v.raw


def _emit_attrs(attrs, lines, indent):
    pad = "  " * indent
    for k, v in attrs.items():
        lines.append("%s%s : %s ;" % (pad, k, _emit_value(v)))


def _emit_group(g: LibertyGroup, lines, indent):
    pad = "  " * indent
    lines.append("%s%s (%s) {" % (pad, g.gtype, g.args_raw))
    _emit_attrs(g.attrs, lines, indent + 1)
    for sg in g.groups:
        _emit_group(sg, lines, indent + 1)
    lines.append("%s}" % pad)


def serialize_liberty(lib: LibertyLibrary) -> str:
    """把 `LibertyLibrary` 写回 `.lib` 文本（属性/子组顺序与原始一致）。"""
    lines = ["library (%s) {" % (lib.name or "")]
    _emit_attrs(lib.attrs, lines, 1)
    for g in lib.top_groups:
        _emit_group(g, lines, 1)
    lines.append("}")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# 适配器：喂给 S1 统一数据模型（补上 model.py deferred 的「真实极性来自 Liberty」）
# ══════════════════════════════════════════════════════════════════════════════
# Liberty direction → S1 的 DIRECTIONS 三值；电源/地/内部等不进 STA，返回 None 跳过。
_DIRECTION_MAP = {
    "input": "input", "output": "output",
    "inout": "inout", "bidirectional": "inout", "tri_state": "inout",
}
_SENSE_MAP = {
    "positive_unate": "positive_unate",
    "negative_unate": "negative_unate",
    "non_unate": "non_unate",
}


def _index_values(tmpl: LibertyGroup, attr: str):
    """取模板的 index_1 / index_2 数值向量（属性或子组 `index_1 ( "1,2,3" )` 两种写法都支持）。"""
    v = tmpl.attrs.get(attr)
    if v is not None:
        if v.tag == "matrix" and v.rows:
            return v.rows[0]
        if v.tag == "num":
            return [v.num]
        if v.tag == "str":
            nums = [float(p.strip()) for p in v.raw.strip().strip('"').split(",") if p.strip()]
            return nums
    for sg in tmpl.subgroups(attr):
        iv = sg.attrs.get("values")
        if iv is not None and iv.tag == "matrix" and iv.rows:
            return iv.rows[0]
    return None


def _delay_table(tg: LibertyGroup, lib: LibertyLibrary, attr_name: str):
    """从 timing 子组里取 `cell_fall`/`cell_rise` 的 NLDM 表，转成 S1 的 `table` 元组。

    返回 `(table, nominal_ps)`：`table = (slew_ps, load_ff, delays_ps[slew][load])`，
    单位按模板显式换算（load: pf→ff；slew/delay: ns→ps）；`nominal_ps` 是该表的代表标量
    （取中心格，纯为了给「只要一阶延迟」的下游一个兜底值，不是时序解算）。

    template 缺失 / index 缺失 / values 非矩阵 → 返回 `(None, None)`，绝不编造。
    """
    grps = tg.subgroups(attr_name)
    if not grps:
        return None, None
    vg = grps[0]
    # `values ( "..." ) ;` 在 Liberty 里是「括号值属性」，其矩阵已直接解析为 matrix 标签的 LibertyValue。
    vals = vg.attrs.get("values")
    if vals is None or vals.tag != "matrix" or vals.rows is None:
        return None, None
    mv = vals
    tmpl = lib.templates.get(vg.name() or "")
    if tmpl is None:
        return None, None
    idx_load = _index_values(tmpl, "index_1")   # variable_1 = 输出负载电容
    idx_slew = _index_values(tmpl, "index_2")   # variable_2 = 输入 transition
    if idx_load is None or idx_slew is None:
        return None, None
    load_ff = tuple(x * 1000.0 for x in idx_load)   # pf → ff
    slew_ps = tuple(x * 1000.0 for x in idx_slew)   # ns → ps
    # Liberty 矩阵：行=index_1(load)，列=index_2(slew)；S1 约定 delays[slew][load] → 转置。
    matrix = mv.rows
    delays_ps = tuple(
        tuple(matrix[l][s] * 1000.0 for l in range(len(idx_load)))
        for s in range(len(idx_slew))
    )
    table = (slew_ps, load_ff, delays_ps)
    n_l = len(idx_load)
    n_s = len(idx_slew)
    nominal_ps = matrix[n_l // 2][n_s // 2] * 1000.0 if (n_l and n_s) else None
    return table, nominal_ps


def to_model(lib: LibertyLibrary):
    """把解析出的 library 转成 `lda_l2.model.CellView` 字典（Pin 极性 + TimingArc 延迟表）。

    单位换算（显式、不可静默）：`capacitance` pf → `cap_ff`；NLDM 表 load pf→ff、slew/delay ns→ps。
    `cell_fall`/`cell_rise` 在 Liberty 里是 **子组**（带 `values` 矩阵），不是属性 —— 这里按子组读。
    几何（面积/尺寸）在 LEF(S3)，本模块只留 0。
    """
    from lda_l2 import model as MD

    out: "OrderedDict[str, object]" = OrderedDict()
    for cname, cell in lib.cells.items():
        cv = MD.CellView(name=cname, w_nm=0, h_nm=0, source="liberty:%s" % lib.name)
        for pin in cell.subgroups("pin"):
            pname = pin.name()
            if pname is None:
                continue
            direction = _DIRECTION_MAP.get(
                pin.attrs.get("direction").raw if pin.attrs.get("direction") else "")
            if direction is None:
                continue  # 电源/地/内部引脚不进 STA 的 Pin 极性
            cap = pin.attrs.get("capacitance")
            cap_ff = 0.0
            if cap is not None and cap.tag == "num":
                cap_ff = cap.num * 1000.0  # pf → ff
            cv.pins[pname] = MD.Pin(name=pname, direction=direction, cap_ff=cap_ff)
            for tg in pin.subgroups("timing"):
                rel = tg.attrs.get("related_pin")
                from_pin = ""
                if rel is not None and rel.tag in ("str", "ident"):
                    from_pin = rel.raw.strip().strip('"')
                sense = _SENSE_MAP.get(
                    tg.attrs.get("timing_sense").raw
                    if tg.attrs.get("timing_sense") else "",
                    "positive_unate")
                table, nominal_ps = _delay_table(tg, lib, "cell_fall")
                if table is None:
                    table, nominal_ps = _delay_table(tg, lib, "cell_rise")
                cv.arcs.append(MD.TimingArc(
                    from_pin=from_pin, to_pin=pname, sense=sense,
                    delay_ps=nominal_ps, table=table))
        out[cname] = cv
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 代表性合成样本（按公开单元库惯例构造；用于机核验证，非真实第三方 PDK）
# ══════════════════════════════════════════════════════════════════════════════
SAMPLE_LIBERTY = r"""library ("SAMPLE_PDK") {
  comment : "Representative synthetic subset for S2 verification";
  library_features ( "report_delay_calculation", "report_power_calculation" ) ;
  time_unit : "1ns" ;
  voltage_unit : "1V" ;
  current_unit : "1mA" ;
  capacitive_load_unit ( 1.0, "pf" ) ;
  nom_voltage : 1.0 ;
  nom_temperature : 25 ;
  default_cell_leakage_power : 0.0 ;
  default_fanout_load : 1.0 ;
  default_inout_pin_cap : 0.0 ;
  default_input_pin_cap : 1.0 ;
  default_output_pin_cap : 0.0 ;
  default_max_transition : 0.5 ;

  lu_table_template (delay_template_3x3) {
    variable_1 : "total_output_net_capacitance" ;
    variable_2 : "input_net_transition" ;
    index_1 ( "1.0, 2.0, 3.0" ) ;
    index_2 ( "0.1, 0.2, 0.3" ) ;
  }

  cell (INVX1) {
    area : 12.34 ;
    cell_footprint : "inv" ;
    pin (A) {
      direction : input ;
      capacitance : 0.5 ;
      timing () {
        related_pin : "Z" ;
        timing_sense : negative_unate ;
        cell_fall (delay_template_3x3) {
          values ( "0.010, 0.020, 0.030", \
                   "0.040, 0.050, 0.060", \
                   "0.070, 0.080, 0.090" ) ;
        }
        cell_rise (delay_template_3x3) {
          values ( "0.011, 0.021, 0.031", \
                   "0.041, 0.051, 0.061", \
                   "0.071, 0.081, 0.091" ) ;
        }
      }
    }
    pin (Z) {
      direction : output ;
      capacitance : 0.2 ;
      timing () {
        related_pin : "A" ;
        timing_sense : positive_unate ;
        cell_fall (delay_template_3x3) {
          values ( "0.012, 0.022, 0.032", \
                   "0.042, 0.052, 0.062", \
                   "0.072, 0.082, 0.092" ) ;
        }
      }
      internal_power () {
        related_pin : "A" ;
        rise_power (delay_template_3x3) {
          values ( "0.001, 0.002, 0.003", \
                   "0.004, 0.005, 0.006", \
                   "0.007, 0.008, 0.009" ) ;
        }
      }
    }
  }

  cell (NAND2X1) {
    area : 20.0 ;
    pin (A) {
      direction : input ;
      capacitance : 0.6 ;
    }
    pin (B) {
      direction : input ;
      capacitance : 0.6 ;
    }
    pin (ZN) {
      direction : output ;
      capacitance : 0.3 ;
      timing () {
        related_pin : "A" ;
        timing_sense : negative_unate ;
        cell_fall (delay_template_3x3) {
          values ( "0.020, 0.030, 0.040", \
                   "0.050, 0.060, 0.070", \
                   "0.080, 0.090, 0.100" ) ;
        }
      }
    }
  }

  cell (DFFX1) {
    area : 40.0 ;
    pin (CLK) {
      direction : input ;
      capacitance : 0.8 ;
    }
    pin (D) {
      direction : input ;
      capacitance : 0.7 ;
    }
    pin (Q) {
      direction : output ;
      capacitance : 0.4 ;
      timing () {
        related_pin : "CLK" ;
        timing_sense : non_unate ;
        cell_fall (delay_template_3x3) {
          values ( "0.030, 0.040, 0.050", \
                   "0.060, 0.070, 0.080", \
                   "0.090, 0.100, 0.110" ) ;
        }
      }
    }
  }
}
"""

# ══════════════════════════════════════════════════════════════════════════════
# T4 数据契约：**与本仓 Tech 尺度对齐**的合成库（`SAMPLE_LIBERTY` 是 pF 尺度，
#   与本仓 c17（0–2 fF、0.77 µm²）差 3 个数量级 —— 直接接线会 100% 钳位，见 T4 测算）。
#
# 🔴 **本库是什么**：把 `dcell.DEFAULT_TECH` 与 `dcells` 的几何**显式化成一份 Liberty 文本**。
#    值完全一致（vdd 0.9 / 125 °C / max_transition 50 ps / cin 1 fF / area 0.7688·1.47 µm²），
#    表值 = 闭式延时在该网格点上的采样。
# 🔴 **本库不是什么**：**不是**任何真实工艺数据、**不是** foundry PDK、**不是**独立实测语料。
#    它的唯一用途是证明「把代码常量换成数据文件」这条**通路**不引入偏差
#    （数字逐位不变 + 改 Tech 时库表不动 = 库确是独立数据源）。
#    换真库数据⇒会改口，那需要外部输入，本仓没有。
#
# 🔴 **slew 轴是退化维度**：每行 4 个值完全相同，因为被显式化的闭式模型不含 slew 项。
#    真库会有真实 slew 依赖 —— 这一点**不做假**，如实保留平的列。
#    `default_max_transition = 0.05 ns = 50 ps` 与本仓 `dsta._DEFAULT_SLEW_PS` **同值**；
#    这是「库与设计对齐」的选择，不是巧合 —— 换真库它会不同（那才是改口点）。
# ══════════════════════════════════════════════════════════════════════════════
SAMPLE_LIBERTY_L2 = r"""
library ("SAMPLE_PDK_L2") {
  comment : "LDA L2-scale synthetic library: explicit data contract of the in-repo Tech";
  library_features ( "report_delay_calculation", "report_power_calculation" ) ;
  time_unit : "1ns" ;
  voltage_unit : "1V" ;
  current_unit : "1mA" ;
  capacitive_load_unit ( 1.0, "pf" ) ;
  nom_voltage : 0.9 ;
  nom_temperature : 125 ;
  default_cell_leakage_power : 0.0 ;
  default_fanout_load : 1.0 ;
  default_inout_pin_cap : 0.0 ;
  default_input_pin_cap : 0.001 ;
  default_output_pin_cap : 0.0 ;
  default_max_transition : 0.05 ;

  lu_table_template (delay_l2) {
    variable_1 : "total_output_net_capacitance" ;
    variable_2 : "input_net_transition" ;
    index_1 ( "0.0, 0.001, 0.002, 0.004, 0.008" ) ;
    index_2 ( "0.01, 0.05, 0.1, 0.2" ) ;
  }

  cell (INV) {
    area : 1.0478 ;
    pin (A) {
      direction : input ;
      capacitance : 0.001 ;
      timing () {
        related_pin : "Z" ;
        timing_sense : negative_unate ;
        cell_fall (delay_l2) {
          values (                    "0.002, 0.002, 0.002, 0.002", \
                   "0.005465735902799727, 0.005465735902799727, 0.005465735902799727, 0.005465735902799727", \
                   "0.008931471805599453, 0.008931471805599453, 0.008931471805599453, 0.008931471805599453", \
                   "0.015862943611198905, 0.015862943611198905, 0.015862943611198905, 0.015862943611198905", \
                   "0.02972588722239781, 0.02972588722239781, 0.02972588722239781, 0.02972588722239781" ) ;
        }
      }
    }
    pin (Z) {
      direction : output ;
      capacitance : 0.0 ;
      timing () {
        related_pin : "A" ;
        timing_sense : positive_unate ;
        cell_fall (delay_l2) {
          values (                    "0.002, 0.002, 0.002, 0.002", \
                   "0.005465735902799727, 0.005465735902799727, 0.005465735902799727, 0.005465735902799727", \
                   "0.008931471805599453, 0.008931471805599453, 0.008931471805599453, 0.008931471805599453", \
                   "0.015862943611198905, 0.015862943611198905, 0.015862943611198905, 0.015862943611198905", \
                   "0.02972588722239781, 0.02972588722239781, 0.02972588722239781, 0.02972588722239781" ) ;
        }
      }
    }
  }

  cell (NAND2) {
    area : 1.911 ;
    pin (A) {
      direction : input ;
      capacitance : 0.001 ;
      timing () {
        related_pin : "ZN" ;
        timing_sense : negative_unate ;
        cell_fall (delay_l2) {
          values (                    "0.002, 0.002, 0.002, 0.002", \
                   "0.008931471805599453, 0.008931471805599453, 0.008931471805599453, 0.008931471805599453", \
                   "0.015862943611198905, 0.015862943611198905, 0.015862943611198905, 0.015862943611198905", \
                   "0.02972588722239781, 0.02972588722239781, 0.02972588722239781, 0.02972588722239781", \
                   "0.05745177444479563, 0.05745177444479563, 0.05745177444479563, 0.05745177444479563" ) ;
        }
      }
    }
    pin (B) {
      direction : input ;
      capacitance : 0.001 ;
    }
    pin (ZN) {
      direction : output ;
      capacitance : 0.0 ;
    }
  }
}
"""
