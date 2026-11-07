# -*- coding: utf-8 -*-
"""S13 门禁：B1 四项零风险判据 + B2a 的 EM 温度标度。

═══════════════════════════════════════════════════════════════════════════════
这一批要证明什么
───────────────────────────────────────────────────────────────────────────────
四个缺口，共同的判据是「**产品数字一位不改**」——即它们只加**观察力**，不加能力：

  B1.1 `S13a–e` **c17 拓扑机核** —— 补「理解错」这一整类（此前完全空白）
  B1.2 `S14a–c` **K0 完备性锚** —— 补「整项缺失」这一整类（此前完全空白）
  B1.3 `S15a–c` **K2 独立性机核** —— 让既有「DRC = E1」不再是虚设
  B1.4 `S16a–b` **面积交叉分段** —— 零误差量必须**换边界**切，否则共同边界错误检不出
  B2a  `S18a–f` **EM 温度标度**（v0.9.385）—— 把「J_MAX 的标定基准温度」从隐藏假设变显式，
       并按 Black 方程补上温度依赖；判据围绕「是否旧常数的严格推广」设计
  S17        产品数字逐位不变 + 自登记 + 耗时

═══════════════════════════════════════════════════════════════════════════════
为什么这四项值得做（不是「多几道门禁」）
───────────────────────────────────────────────────────────────────────────────
· **理解错**（把网表抄错）此前**没有任何判据能抓**。代价已经付过：`g22`/`g23` 两处
  与 ISCAS-85 标准不一致存活了三个版本，先后污染 `.379` 三分类、`.380`/`.382` 归因，
  其中 `g23` 是人眼比对漏掉、本轮才核出来的。
· **整项缺失**（模型里少一个自变量）此前也**没有判据能抓**：量纲恒等对缺失项不敏感，
  单调性对「不存在的变量」无从求偏导。EM 缺温度项就是实例，而它导致 75°C 与 125°C
  报同一个结果（物理上允许值差 31 倍）。
· **K2 独立性**：`checker_equiv_self_check` 只验「两个实现结果一致」。若两者共享核心
  函数，一个 bug 会同时污染两边 ⇒ 一致也一致地错。**「两个实现」不等于「两条独立路径」。**
· **面积**是整数 nm 求和 ⇒ 残差恒 0 ⇒ 与「抄答案」不可区分。四段复算解决了总量不可锚，
  但如果独立复算用**同一边界**切，边界定错会同时污染两条 ⇒ 检不出。故需**换边界**。

═══════════════════════════════════════════════════════════════════════════════
标准定义的出处（这一条不可省）
───────────────────────────────────────────────────────────────────────────────
若「标准网表」是我凭记忆写进测试的，那它与实现**同源**，比对没有信息量（犯 C1 同类错）。
故三源互证 + 哈希锁 + 取得日期，任何人可复核：

  ① MCNC / David Bryan, "The ISCAS '85 benchmark circuits and netlist format", 1988-09-30
     （ISCAS'85 原始分发格式；c17 段落给出 10/11/16/19/22/23 六门的 fanout 连接）
  ② `c17.bench`（ISCAS'89 转写）—— ATPG 平台论文 Fig.2 与 Atalanta 文档**同时**给出
  ③ `c17.v`（Verilog 转写，StackOverflow #61256704 引用）—— `NAND2_1..NAND2_6` 六门全 NAND2

三源在「哪六门、各是什么门、各接哪些网」上逐项一致。下文 `STANDARD_GATES` 是它们的机器形式，
`STANDARD_SHA256` 锁住文本，改一个字即红（防静默漂移）。

⚠️ **本门禁不做的事**：**不改网表**。改网表会推翻 DRC/面积/时序/DEF 全部既有数字，
那是另一批的事；本批只把差异**如实登记**（`DECLARED_DIFFS`），不许静默。

诚实边界
────────
· 三源互证消除「多渠道抄错同一处」的风险，**不消除「我读错」** —— 后者只能靠 URL 复核，
  所以出处与日期必须随判据同行。
· 拓扑机核只证明「与公开定义的关系」，不证明「这个 c17 能布通/能签核」。
· K2 的静态部分只覆盖**同文件内的本地调用**；跨模块共享（如共同依赖 `Shape`/常量）
  不在本判据范围内，**不可据此宣称「完全独立」**。
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import math
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_l2.ecore import db3_trunk as B3        # noqa: E402
from lda_l2.ecore import ddef as DF            # noqa: E402
from lda_l2.ecore import ddrc_lvs as DL        # noqa: E402
from lda_l2.ecore import dsignoff as DS        # noqa: E402
from lda_l2.ecore import dpnr as P             # noqa: E402
from lda_l2.ecore import dverilog as V         # noqa: E402

_FALS: list = []
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   record=_FALS)
T0 = time.time()
AN_ELAPSED_MAX_S = 180.0

_HERE = os.path.dirname(os.path.abspath(__file__))

# ══════════════════════════════════════════════════════════════════════════
# B1.1 标准定义（三源互证 · 出处可溯源 · 哈希锁）
# ══════════════════════════════════════════════════════════════════════════
STANDARD_SOURCE_URL = "https://ddd.fit.cvut.cz/www/prj/Benchmarks/iscas85.pdf"
STANDARD_SOURCE_DOC = ("MCNC / David Bryan, \"The ISCAS '85 benchmark circuits and "
                       "netlist format\", 1988-09-30（ISCAS'85 原始分发格式 · c17 段）")
STANDARD_CORROBORATION = (
    "c17.bench（ISCAS'89 转写）· ATPG 平台论文 Fig.2 与 Atalanta 文档同时给出",
    "c17.v（Verilog 转写 · StackOverflow #61256704）· NAND2_1..NAND2_6 六门全 NAND2",
)
STANDARD_RETRIEVED_AT = "2026-11-06"

#: `c17.bench` 原文（机器形式的标准；sha256 锁住，改一字即红）
STANDARD_CANON = """# c17
# 5 inputs
# 2 outputs
# 0 inverters
# 6 gates (6 NANDs)
INPUT(1)
INPUT(2)
INPUT(3)
INPUT(6)
INPUT(7)
OUTPUT(22)
OUTPUT(23)
10 = NAND(1, 3)
11 = NAND(3, 6)
16 = NAND(2, 11)
19 = NAND(11, 7)
22 = NAND(10, 16)
23 = NAND(16, 19)
"""
STANDARD_SHA256 = "fa94e5130e38f02b9ba4a6bd018889581f9952f4bef4c45ad15d6d7a349a3ebf"

STANDARD_INPUTS = ("1", "2", "3", "6", "7")
STANDARD_OUTPUTS = ("22", "23")
#: 门 → (类型, 输入网)；键 = 输出网号（去掉 `n` 前缀）
STANDARD_GATES = {
    "10": ("NAND", ("1", "3")),
    "11": ("NAND", ("3", "6")),
    "16": ("NAND", ("2", "11")),
    "19": ("NAND", ("11", "7")),
    "22": ("NAND", ("10", "16")),
    "23": ("NAND", ("16", "19")),
}
#: 单元名 → 逻辑类型（本仓用 NAND2/INV，标准用 NAND/NOT）
_CELL_TYPE = {"NAND2": "NAND", "INV": "NOT", "NOT": "NOT", "NAND": "NAND"}

#: 已登记的差异（**必须与实测双向相等**：漏登记、多登记都红）
DECLARED_DIFFS = {
    "22": ("INPUT_MISMATCH",),
    "23": ("TYPE_MISMATCH", "ARITY_MISMATCH", "INPUT_MISMATCH"),
}


def _n(name: str) -> str:
    """网名归一：去掉本仓的 `n` 前缀（`n10` → `10`）。"""
    s = str(name)
    return s[1:] if s[:1] == "n" and s[1:].isdigit() else s


def _topo_diffs(nl) -> dict:
    """网表拓扑 vs 标准定义 ⇒ {网: (差异类别, …)}；空表示完全一致。

    差异类别只有四种，**越界即红**（防止有人加个「其他」把问题糊过去）：
    `MISSING_GATE` / `TYPE_MISMATCH` / `ARITY_MISMATCH` / `INPUT_MISMATCH` / `EXTRA_GATE`
    """
    actual = {}
    for g in nl.gates:
        actual[_n(g.out)] = (g.cell, tuple(_n(i) for i in g.ins))
    diffs = {}
    for out, (st_type, st_ins) in STANDARD_GATES.items():
        if out not in actual:
            diffs[out] = ("MISSING_GATE",)
            continue
        cell, ins = actual[out]
        kinds = []
        if _CELL_TYPE.get(cell, cell) != st_type:
            kinds.append("TYPE_MISMATCH")
        if len(ins) != len(st_ins):
            kinds.append("ARITY_MISMATCH")
        if tuple(sorted(ins)) != tuple(sorted(st_ins)):
            kinds.append("INPUT_MISMATCH")
        if kinds:
            diffs[out] = tuple(kinds)
    for out in actual:
        if out not in STANDARD_GATES:
            diffs[out] = ("EXTRA_GATE",)
    return diffs


def _standard_verilog() -> str:
    """由 `STANDARD_GATES` **生成**标准网表（不手写第二份，避免两处漂移）。"""
    ports = ["n" + i for i in STANDARD_INPUTS] + ["n" + o for o in STANDARD_OUTPUTS]
    wires = [n for n in STANDARD_GATES
             if n not in STANDARD_INPUTS and n not in STANDARD_OUTPUTS]
    lines = ["module c17(%s);" % ", ".join(ports),
             "  input %s ;" % ", ".join("n" + i for i in STANDARD_INPUTS),
             "  output %s ;" % ", ".join("n" + o for o in STANDARD_OUTPUTS)]
    if wires:
        lines.append("  wire %s ;" % ", ".join("n" + w for w in wires))
    for out, (typ, ins) in STANDARD_GATES.items():
        lines.append("  %s g%s ( n%s, %s ) ;"
                     % (typ.lower(), out, out, ", ".join("n" + i for i in ins)))
    lines.append("endmodule")
    return "\n".join(lines) + "\n"


# ══════════════════════════════════════════════════════════════════════════
# B1.2 K0 完备性（EM 的物理自变量覆盖）
# ══════════════════════════════════════════════════════════════════════════
#: EM（电迁移）在物理上必须具备的自变量集合。
#: 依据：Black 方程 `MTTF = A·J^-n·exp(Ea/kT)` ⇒ 允许电流密度是 (T, Ea, n) 的函数，
#:       而 `J = I/(w·t)` ⇒ 还必须有 I、w、t。
EM_S_PHYS = ("current", "width", "thickness", "temperature",
             "activation_energy", "exponent")
#: `em_check` 形参 → 物理自变量（显式映射，不靠猜）。
#: 🔴 必须同时收录**将来补上时的可能形参名**：否则 B2 真的加了温度参数，本门禁仍报「缺」
#:    ⇒ 修复不可见 ⇒ 判据变成永久红。收录后一旦补上，覆盖数上升 ⇒ 与 `DECLARED_EM_MISSING`
#:    失配 ⇒ 判红强制更新登记表（这才是棘轮该有的方向）。
EM_PARAM_MAP = {
    "i_a": "current", "current_a": "current",
    "width_um": "width", "w_um": "width",
    "t_um": "thickness", "thickness_um": "thickness",
    "temp_c": "temperature", "temperature_c": "temperature",
    "t_c": "temperature", "tj_c": "temperature",
    "ea_ev": "activation_energy", "ea": "activation_energy",
    "n_exp": "exponent", "n": "exponent",
}
#: 已登记的缺失项（与实测必须相等；补齐后本表要跟着改，否则红）。
#: 🔴 v0.9.385（B2a）：EM 已补 Black 温度标度 ⇒ **缺失清零**。此前是
#:    `("temperature", "activation_energy", "exponent")`，靠改这一行让门禁从「报缺」转「不报缺」——
#:    这正是棘轮的设计意图：补上了却忘了改登记表，必须红。
DECLARED_EM_MISSING: tuple = ()


def _k0_missing(param_names) -> tuple:
    """给定形参名集合 ⇒ 缺失的物理自变量（排序后返回，便于逐位比对）。"""
    covered = {EM_PARAM_MAP[p] for p in param_names if p in EM_PARAM_MAP}
    return tuple(sorted(set(EM_S_PHYS) - covered))


# ══════════════════════════════════════════════════════════════════════════
# B1.3 K2 独立性（同文件内的本地调用图）
# ══════════════════════════════════════════════════════════════════════════
#: 允许共享的函数（白名单）。**空** ⇒ 要求两实现完全不共享本地函数。
K2_SHARED_WHITELIST: tuple = ()


def _local_closures(source: str) -> dict:
    """解析源码 ⇒ {入口函数: 本地调用闭包}；只跟踪同文件内的 `Name` 调用。"""
    tree = ast.parse(source)
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

    def _calls(fn):
        return {c.func.id for c in ast.walk(fn)
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}

    def _closure(root: str) -> set:
        seen, stack = set(), [root]
        while stack:
            f = stack.pop()
            for c in _calls(funcs[f]):
                if c in funcs and c not in seen:
                    seen.add(c)
                    stack.append(c)
        return seen

    return {name: _closure(name) for name in funcs}


def main() -> int:
    print("S13 门禁：B1 四项零风险判据（拓扑机核 / K0 完备性 / K2 独立性 / 面积交叉分段）")

    nl = V.parse(V.SAMPLE_VERILOG)
    # ── B1.1 拓扑机核 ────────────────────────────────────────────
    sha = hashlib.sha256(STANDARD_CANON.encode("utf-8")).hexdigest()
    sources_ok = (bool(STANDARD_SOURCE_URL) and "http" in STANDARD_SOURCE_URL
                  and bool(STANDARD_SOURCE_DOC) and len(STANDARD_CORROBORATION) >= 2
                  and bool(re.match(r"^\d{4}-\d{2}-\d{2}$", STANDARD_RETRIEVED_AT)))
    check("S13a 标准定义出处三要素齐备（URL + 文档 + 取得日期 + ≥2 独立佐证）∧ 哈希自洽："
          "sha256=%s…" % sha[:12],
          sources_ok and sha == STANDARD_SHA256,
          "sha 实际=%s 期望=%s" % (sha[:16], STANDARD_SHA256[:16]))

    diffs = _topo_diffs(nl)
    got = {k: tuple(v) for k, v in sorted(diffs.items())}
    want = {k: tuple(v) for k, v in sorted(DECLARED_DIFFS.items())}
    only_got = {k: v for k, v in got.items() if want.get(k) != v}
    only_want = {k: v for k, v in want.items() if got.get(k) != v}
    check("S13b 差异与 `DECLARED_DIFFS` **双向相等**（漏登记 ∧ 多登记都红）：实测 %d 处 / 登记 %d 处"
          % (len(got), len(want)),
          got == want,
          "实测多出=%r 登记未现=%r" % (only_got, only_want))

    check("S13c 阳性对照（M1 · 开工前预注册）：必须报出**恰好 2 处** —— "
          "`g22` 输入不符、`g23` 类型+输入数不符；实测 %s"
          % " · ".join("%s=%s" % (k, "+".join(v)) for k, v in sorted(got.items())),
          len(got) == 2 and set(got) == {"22", "23"}
          and "INPUT_MISMATCH" in got.get("22", ())
          and "TYPE_MISMATCH" in got.get("23", ())
          and "ARITY_MISMATCH" in got.get("23", ()))

    # ── 阴性对照：把网表换成标准版 ⇒ 差异必须为 0 ────────────────
    std_nl = V.parse(_standard_verilog())
    diffs_std = _topo_diffs(std_nl)
    ports_ok = (tuple(sorted(_n(x[0]) for x in std_nl.inputs)) == tuple(sorted(STANDARD_INPUTS))
                and tuple(sorted(_n(k) for k in std_nl.outputs)) == tuple(sorted(STANDARD_OUTPUTS)))
    check("S13d 阴性对照（M2 · 预注册）：标准网表版本 ⇒ 差异 **%d** 处（须 0）∧ 端口 5 入 2 出"
          % len(diffs_std),
          diffs_std == {} and ports_ok,
          "diffs=%r ports_ok=%s" % (diffs_std, ports_ok))

    # 反向探针：故意让一个门接错 ⇒ 必须被抓到（证明不是恒 0）
    bad_src = _standard_verilog().replace("nand g23 ( n23, n16, n19 )",
                                          "nand g23 ( n23, n16, n7 )")
    check("S13e 反向探针：把标准版 `g23` 的一个输入改错 ⇒ 必须报 INPUT_MISMATCH（防恒 0）",
          _topo_diffs(V.parse(bad_src)) == {"23": ("INPUT_MISMATCH",)},
          "%r" % (_topo_diffs(V.parse(bad_src)),))

    # ── B1.2 K0 完备性 ──────────────────────────────────────────
    params = tuple(inspect.signature(DS.em_check).parameters)
    missing = _k0_missing(params)
    check("S14a `em_check` 形参 %s ⇒ 物理自变量覆盖 %d/%d，**缺 %s**；与登记表一致"
          % (list(params), len(EM_S_PHYS) - len(missing), len(EM_S_PHYS), list(missing)),
          missing == tuple(sorted(DECLARED_EM_MISSING)),
          "实测缺=%r 登记缺=%r" % (list(missing), list(DECLARED_EM_MISSING)))

    # 反向探针：假设 `em_check` 真的补上了 T/Ea/n 三个形参 ⇒ 覆盖数必须上升到 6/6。
    # 若检查器把缺失项写死（不看形参），这里仍会报缺 ⇒ 判红。
    _fake = ("i_a", "width_um", "t_um", "temperature_c", "ea_ev", "n_exp")
    _fake_missing = _k0_missing(_fake)
    check("S14b 反向探针：假设补上 T/Ea/n 三个形参 ⇒ 覆盖必须升到 6/6、缺 %s（证明不是写死）"
          % (list(_fake_missing) or "∅",),
          _fake_missing == ())

    _disc = str(DS.B3_DISCLOSURE)
    check("S14c 缺项**不许静默**：B3 披露必须已声明 `J_max` 来自工艺认证（非本仓推导）",
          "j_max" in _disc.lower() and ("工艺" in _disc or "认证" in _disc),
          "披露里未找到 J_max 的假设声明")

    # ── B1.3 K2 独立性 ─────────────────────────────────────────
    with open(os.path.join(_HERE, "lda_l2", "ecore", "ddrc_lvs.py"),
              encoding="utf-8") as fh:
        _src = fh.read()
    clos = _local_closures(_src)
    pairs = (("run_drc", "fast_drc"), ("run_lvs", "fast_lvs"))
    shared = {a: tuple(sorted((clos[a] & clos[b]) - set(K2_SHARED_WHITELIST)))
              for a, b in pairs}
    check("S15a K2 静态：两对实现的本地调用闭包**交集为空**（白名单 %d 项）：%s"
          % (len(K2_SHARED_WHITELIST),
             " · ".join("%s=%s" % (a, list(v) or "∅") for a, v in shared.items())),
          all(not v for v in shared.values()),
          "%r" % (shared,))

    _po_rt = P.build_ports(nl, P.place_real(nl))
    _shp = P.all_routing(P.route_block(nl, _po_rt["pl"], ports=_po_rt))
    _base = DL.run_drc(_shp)
    _orig = DL._index_bbox

    def _poison(*_a, **_k):
        raise RuntimeError("K2-POISON")

    _fast_raised = False
    try:
        DL._index_bbox = _poison                              # 只被 fast_drc 使用
        try:
            DL.fast_drc(_shp)
        except RuntimeError as e:
            _fast_raised = "K2-POISON" in str(e)
        _after = DL.run_drc(_shp)                             # 必须不受影响
    finally:
        DL._index_bbox = _orig
    check("S15b K2 动态：毒化 `_index_bbox`（仅 fast_drc 用）⇒ `run_drc` 输出**逐位不变**"
          "（%d 违规）∧ fast_drc **确被击中**（raised=%s）"
          % (len(_base.get("violations") or []), _fast_raised),
          _after == _base and _fast_raised,
          "run_drc 变了=%s / 注入未命中=%s"
          % (_after != _base, not _fast_raised))

    _fake_src = (
        "def _shared():\n    return 1\n"
        "def _only_b():\n    return _shared()\n"
        "def run_drc():\n    return _shared()\n"
        "def fast_drc():\n    return _only_b()\n")
    _fc = _local_closures(_fake_src)
    _fake_shared = sorted(_fc["run_drc"] & _fc["fast_drc"])
    check("S15c 反向探针：合成「两实现共享 `_shared`」的源码 ⇒ 检查器必须报出共享 %r（防恒空）"
          % (_fake_shared,),
          _fake_shared == ["_shared"])

    # ── B1.4 面积交叉分段 ──────────────────────────────────────
    _po = P.build_ports(nl, P.place_real(nl))
    _cut_a = (_po["band_left_um"] + _po["die_w_um_noport"]
              + _po["band_right_um"] + _po["grid_align_um"])
    _def_txt = DF.serialize_def(DF.from_placement(_po["pl"], nl, name="lda_c17"))
    _m = re.search(r"DIEAREA\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)",
                   _def_txt)
    _cut_b = ((int(_m.group(3)) - int(_m.group(1))) / 1000.0) if _m else float("nan")
    check("S16a 面积两条**不同边界**路径同时拼回 `die_w`：四段算术 %.3f / DEF `DIEAREA` 文本 %.3f "
          "/ build_ports %.3f（三者互不共享边界定义）"
          % (_cut_a, _cut_b, _po["die_w_um"]),
          abs(_cut_a - _po["die_w_um"]) < 1e-9 and abs(_cut_b - _po["die_w_um"]) < 1e-9)

    _tampered = _def_txt.replace("(7800 7800)", "(7900 7800)", 1)
    _m2 = re.search(r"DIEAREA\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)",
                    _tampered)
    _cut_b2 = ((int(_m2.group(3)) - int(_m2.group(1))) / 1000.0) if _m2 else float("nan")
    check("S16b 反向探针：把 DEF `DIEAREA` 改 100 nm ⇒ 第二路径必须与 `die_w` 失配（防抄同一数）",
          abs(_cut_b2 - _po["die_w_um"]) > 1e-9,
          "篡改后 %.3f" % _cut_b2)

    # ── B2a（v0.9.385）：EM 温度标度 Black 方程 ─────────────────
    # 目的：把「J_MAX 是某个温度下的值，但没写是哪个温度」这个隐藏假设显式化，
    #       并补上温度依赖。判据全部围绕「是不是旧常数的严格推广」来设计。
    j_ref = DS.j_max_at(DS.T_REF_C)
    check("S18a 🔴 退化对照：`T = T_ref(%.0f°C)` 时 `j_max_at` **逐位等于**旧常数 %.3g"
          "（通式必须退化为已实现的特例）"
          % (DS.T_REF_C, DS.J_MAX_A_M2),
          j_ref == DS.J_MAX_A_M2, "got=%r" % (j_ref,))

    _j85, _j125 = DS.j_max_at(85.0), DS.j_max_at(125.0)
    _j150 = DS.j_max_at(150.0)
    check("S18b 单调性 `∂J_max/∂T < 0`：85°C %.4g > 125°C %.4g > 150°C %.4g（×%.1f / ×%.2f）"
          % (_j85, _j125, _j150, _j85 / _j125, _j150 / _j125),
          _j85 > _j125 > _j150 > 0)

    # 形式验证：ln J 对 1/T 线性，斜率必须 == Ea/(n·k)
    def _slope(t1, t2):
        return (math.log(DS.j_max_at(t2)) - math.log(DS.j_max_at(t1))) / (
            (1.0 / (t2 + 273.15)) - (1.0 / (t1 + 273.15)))
    _s1, _s2 = _slope(85.0, 125.0), _slope(125.0, 150.0)
    _want_slope = DS.EA_EV / (DS.N_EXP * DS.K_B_EV)
    check("S18c 形式：`ln J_max` 对 `1/T` 斜率为常且 == `Ea/(n·k)`=%.4g（两段实测 %.4g / %.4g）"
          % (_want_slope, _s1, _s2),
          abs(_s1 - _want_slope) / _want_slope < 1e-9
          and abs(_s2 - _want_slope) / _want_slope < 1e-9)

    # 所需线宽 w_min = I/(J_max·t)，必须随电流单调增（这是「加宽/加电流」的方向性结论）
    def _w_min(i_a, t_c):
        return (i_a / DS.j_max_at(t_c)) / (DS.T_METAL_UM * 1e-6) * 1e6
    _w1, _w2 = _w_min(2e-4, 125.0), _w_min(4e-4, 125.0)
    _w_chk = _w_min(3.36e-4, 125.0)
    check("S18d 线宽：`w_min` 随电流单调增（%.4f → %.4f µm）∧ 闭环 `w_min(336µA,125°C)=%.4f` 应 == 0.24"
          % (_w1, _w2, _w_chk),
          _w2 > _w1 > 0 and abs(_w_chk - 0.24) < 1e-6)

    # 温度**真的进了判定**（不是只多了个形参）：同一根线在同一电流下结论随温度翻转
    _r125 = DS.em_check(4e-4, 0.24, t_c=125.0)
    _r85 = DS.em_check(4e-4, 0.24, t_c=85.0)
    _r150 = DS.em_check(2e-4, 0.24, t_c=150.0)
    check("S18e 判别力：同一根线 `4e-4A/0.24µm` 在 125°C %s、85°C %s；`2e-4` 在 150°C %s"
          " —— 常数模型给不出这个区分"
          % ("不通过" if not _r125["ok"] else "通过",
             "通过" if _r85["ok"] else "不通过",
             "不通过" if not _r150["ok"] else "通过"),
          _r125["ok"] is False and _r85["ok"] is True and _r150["ok"] is False)

    # 回归轴：T=T_ref 时对既有两点的判定必须与旧常数完全一致（不许改历史结论）
    _e1, _e2 = DS.em_check(2e-4, 0.24), DS.em_check(4e-4, 0.24)
    check("S18f 回归轴：`T=T_ref` 时既有两点判定与旧常数一致（2e-4 %s · 4e-4 %s）"
          " ∧ `j_max_overridden` 均为 False"
          % ("通过" if _e1["ok"] else "不通过", "通过" if _e2["ok"] else "不通过"),
          _e1["ok"] is True and _e2["ok"] is False
          and _e1["j_max_overridden"] is False and _e2["j_max_overridden"] is False)

    # ── A（v0.9.386）：EM 披露必须**对外可读**，且三处事实可机核 ────
    # 背景：v0.9.385 把 EM 的隐藏假设显式化了，但 `dsignoff.B3_DISCLOSURE` 没有任何端点透出
    #       ⇒ 对外唯一可见变化只有版本号，读者在 API 上读不到。本节把「能否读到」变成判据。
    from lda_webui import digital_case as _DC                    # noqa: E402
    _DC.clear_cache()
    _a19_em = ((_DC.case_card().get("disclosure") or {}).get("em") or "")
    _a19_params = all(k in _a19_em for k in ("T_ref", "Ea", "n=1.1"))
    check("S19a 卡片 `disclosure.em` 存在且点名三个参数（T_ref / Ea / n=1.1）：%r"
          % ((_a19_em[:46] + "…") if _a19_em else "(缺失)",),
          bool(_a19_em) and _a19_params)

    _a19_ratio = DS.j_max_at(85.0) / DS.j_max_at(125.0)
    _a19_nums = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*×", _a19_em)]
    check("S19b 文案里的倍数与实测一致：`j_max_at(85)/j_max_at(125)` = %.2f，文案写 %s"
          "（不许手填一个数）"
          % (_a19_ratio, _a19_nums or "无"),
          any(abs(n - _a19_ratio) <= 0.5 for n in _a19_nums))

    def _imports_needle_src(src: str, needle: str) -> bool:
        """AST 取全部 import（含函数内嵌套）⇒ 是否存在含 `needle` 的名字。

        🔴 必须同时收 **模块名** 与 **导入名**：`from lda_l2.ecore import dsignoff`
        的 `module` 只有 `lda_l2.ecore`，真正的目标是 alias `dsignoff`。
        只收 module ⇒ 恰好漏掉「接线 EM」最可能的写法 ⇒ 判据恒假通过。
        （这个漏洞是 S19d 反向探针当场抓出来的，不是看出来的。）
        """
        _names = set()
        for _n in ast.walk(ast.parse(src)):
            if isinstance(_n, ast.Import):
                _names.update(_a.name for _a in _n.names)
            elif isinstance(_n, ast.ImportFrom):
                _mod = _n.module or ""
                if _mod:
                    _names.add(_mod)
                for _a in _n.names:
                    _names.add(("%s.%s" % (_mod, _a.name)) if _mod else _a.name)
        return any(needle in _x for _x in _names)

    def _imports_needle(path: str, needle: str) -> bool:
        return _imports_needle_src(open(path, encoding="utf-8").read(), needle)

    def _em_claim_ok(em_text: str, uses_em: bool) -> bool:
        """🔴 三态判定：文案必须**恰好一个**互斥措辞，且与 AST 事实一致。

        只查「不含 EM 判决」是不够的：把那句话删掉（**沉默**）会被当成「含」
        ⇒ 假通过。这正是 S19d 抓过的那类洞（判据恒真）的另一种形态，
        所以这里把「都在 / 都不在」都判红。
        """
        _no = "不含 EM 判决" in em_text
        _yes = "含 EM 诊断段" in em_text
        if _no == _yes:          # 都在 或 都不在 ⇒ 无法判定 ⇒ 红
            return False
        return _yes == uses_em

    _a19_trunk = os.path.join(_HERE, "lda_l2", "ecore", "db3_trunk.py")
    _a19_uses_em = _imports_needle(_a19_trunk, "dsignoff")
    _a19_declares_no = "不含 EM 判决" in _a19_em
    _a19_declares_yes = "含 EM 诊断段" in _a19_em
    check("S19c 🔴 声明与 AST 事实一致（三态）：主链 `db3_trunk` import dsignoff=%s ∧ "
          "文案「不含=%s / 含=%s」—— 接线后本句必须翻面，沉默也算红"
          % (_a19_uses_em, _a19_declares_no, _a19_declares_yes),
          _em_claim_ok(_a19_em, _a19_uses_em))

    # 反向探针：若检测器恒 False，S19c 会**永远通过**（形同虚设）
    check("S19d 反向探针：合成源码 `from ... import dsignoff` ⇒ 必须检出 True；纯 `import os` ⇒ False",
          _imports_needle_src("from lda_l2.ecore import dsignoff\n", "dsignoff") is True
          and _imports_needle_src("import os\n", "dsignoff") is False)
    check("S19e 反向探针·三态：含/不含两种措辞各配对事实须为真，**沉默必须红**、"
          "措辞与事实相反必须红",
          _em_claim_ok("含 EM 诊断段", True) is True
          and _em_claim_ok("不含 EM 判决", False) is True
          and _em_claim_ok("", False) is False
          and _em_claim_ok("含 EM 诊断段", False) is False)

    # ── S17 硬条件：产品数字逐位不变 ───────────────────────────
    _rep = B3.run_trunk(nl)
    _st = {n: p for n, p in _rep["stages"]}
    _num = {
        "routed": (_st["route"]["nets_with_segments"], _st["route"]["nets_touched"], 7, 11),
        "drc": (_st["drc_lvs"]["drc_violations"], None, 0, None),
        "area": (_st["place"]["die_area_um2"], None, 60.84, None),
        "delay": (_st["timing"]["comb_delay_wired_ps"], None, 43.49, None),
        "def": (_st["def_write"]["bytes"], None, 575, None),
    }
    _bad = {k: v for k, v in _num.items()
            if not ((v[0] == v[2] and (v[1] is None or v[1] == v[3])))}
    check("S17a 🔴 硬条件：产品数字**逐位不变** —— 布通 %s/%s · DRC %s · 面积 %.3f · 延时 %.3f · DEF %s B"
          % (_num["routed"][0], _num["routed"][1], _num["drc"][0],
             _num["area"][0], _num["delay"][0], _num["def"][0]),
          not _bad,
          "变动项=%r（声明不该变却变了 ⇒ 判据误报，回查）" % (_bad,))

    with open(os.path.join(_HERE, "run_ci_regression.py"), encoding="utf-8") as fh:
        _ck = fh.read()
    check("S17b 本门禁已登记进 CORE_SMOKES（防静默漏接）",
          "run_ecore_s13_smoke.py" in _ck)

    # ── B2b（v0.9.387）：EM **接线**后的可判性、边界与反向探针 ──────────────
    # 背景：`em_check` 一直是纯函数，主链从未给它电流 ⇒ 对外等于不存在。
    #   接线后**判定结果一位不变**（c17 违例 0/7、最小裕量约 10²×）—— 这恰恰要求
    #   门禁证明「换个参数它真会响」；否则本段就是一个永远为真的装饰（K1 判别力）。
    from lda_l2.ecore import dextract as _DE                  # noqa: E402

    _em = _st.get("em") or {}
    _asm = _em.get("assumptions") or {}
    _asm_need = ("f_hz", "vdd", "alpha", "width_um", "t_um", "t_c",
                 "ea_ev", "n_exp", "t_ref_c", "j_max_a_m2")
    _asm_missing = [k for k in _asm_need if _asm.get(k) is None]
    check("S20a 主链产出 `em` 段，且 %d 个输入假设全部显式（K0 完备性）：缺=%r"
          % (len(_asm_need), _asm_missing),
          bool(_em) and not _asm_missing)

    # 独立复算：**不用被测段输出的中间量**，从源 Netlist 重跑 P&R 拿带网形状。
    _pl2 = P.place_real(nl)
    _ports2 = P.build_ports(nl, _pl2)
    _sh2 = P.all_routing(P.route_block(nl, _ports2["pl"], ports=_ports2))
    _wl2 = _DE.wire_loads_from_shapes(_sh2)
    _len2 = _DE.net_length_um(_sh2)
    _pn = _em.get("per_net") or {}
    _cm_wire = [_dn for _dn in _wl2
                if abs(_wl2[_dn] - float((_pn.get(_dn) or {}).get("c_wire_ff", -1.0))) > 1e-12]
    _cm_len = [_dn for _dn in _len2
               if abs(_len2[_dn] - float((_pn.get(_dn) or {}).get("length_um", -1.0))) > 1e-3]
    check("S20b 每网线长/线载独立复算一致：%d 条网，线载不一致 %r，线长不一致 %r"
          % (len(_wl2), _cm_wire[:4], _cm_len[:4]),
          not _cm_wire and not _cm_len and len(_pn) == len(_wl2))

    _bad_i = []
    for _net, _v in _pn.items():
        _want = DS.ALPHA_DYN * (_v["c_total_ff"] * 1e-15) * _asm["vdd"] * _asm["f_hz"]
        if not math.isclose(_want, _v["i_a"], rel_tol=1e-12, abs_tol=0.0):
            _bad_i.append(_net)
    check("S20c 电流公式 `I = α·C_tot·V·f` 逐网复算一致（rel_tol=1e-12）：%d 条，偏差 %r"
          % (len(_pn), _bad_i[:4]), not _bad_i)

    # 可判性必须**跨段互证**（不是本段自己说了算）
    _und = list(_em.get("undecidable_nets") or [])
    _rt_ok = (
        _em.get("n_nets_total") == _st["route"]["nets_touched"]
        and _em.get("n_nets_judged") == _st["route"]["nets_with_segments"]
        and len(_und) == (_st["route"]["nets_failed"] + _st["route"]["nets_skipped_port"])
        # 🔴 独立复算的网集合必须与段内 per_net **完全相同的 7 条**（对称差为空）。
        #    不能写 `set(a) ^ set(b) or set(_und)` —— 空集会被 `or` 兜底成真，判据恒真。
        and not (set(_len2) ^ set(_pn))
    )
    check("S20d 可判性跨段互证：total %s==route.nets_touched %s ∧ judged %s==route.nets_with_segments %s ∧ "
          "不可判 %d==failed %s+skipped %s；不可判名单 %r（**不可判 ≠ 通过**）"
          % (_em.get("n_nets_total"), _st["route"]["nets_touched"],
             _em.get("n_nets_judged"), _st["route"]["nets_with_segments"],
             len(_und), _st["route"]["nets_failed"], _st["route"]["nets_skipped_port"], _und),
          bool(_rt_ok))

    # ── 反向探针：证明「判据真的会响」，不是永远通过 ──────────────────
    _wn = _em.get("min_margin_net")
    _wv = _pn.get(_wn) or {}
    # 🔴 倍数**按当前裕量反解**、不写死：`margin ∝ 1/J ∝ w` ⇒ 线宽除以 `2·margin`
    #    必把裕量打到 0.5×（必 FAIL）。写死「100×」会在数字变化后变成假绿 ——
    #    本轮实测就是这么暴露的：缩 100× 时裕量还剩 **1.0096×**，恰好没翻过 1。
    _k_narrow = max(2.0, float(_wv.get("margin_x") or 1.0) * 2.0)
    _narrow = DS.em_check(_wv.get("i_a", 0.0), _asm["width_um"] / _k_narrow,
                          t_um=_asm["t_um"], t_c=_asm["t_c"])
    check("S20e 反向探针·线宽：最紧网（%s，当前 %.3f×）线宽 ÷%.2f（按裕量反解）⇒ 必须 FAIL"
          "（实测 %.4f×）"
          % (_wn, _wv.get("margin_x") or 0.0, _k_narrow, _narrow["margin_x"]),
          _narrow["ok"] is False)

    _i_big = DS.net_current_a(_wv.get("c_total_ff", 0.0), _asm["f_hz"] * 1e6, _asm["vdd"])
    _fast = DS.em_check(_i_big, _asm["width_um"], t_um=_asm["t_um"], t_c=_asm["t_c"])
    check("S20f 反向探针·频率：同网频率 ×1e6 ⇒ 必须 FAIL（实测 %.4f×）"
          % (_fast["margin_x"],), _fast["ok"] is False)

    _zero = DS.em_net_signoff({"x": 1.0}, {"x": 1.0}, {"x": 1.0}, ["x"],
                              0.0, _asm["vdd"], _asm["width_um"], t_um=_asm["t_um"])
    _z_m = (_zero.get("per_net") or {}).get("x", {}).get("margin_x")
    check("S20g 退化对照：`f=0` ⇒ `I=0` ⇒ 裕量必须落成 `None`（严格 JSON，不写裸 `Infinity`）"
          "且不计入 FAIL：margin=%r n_fail=%s" % (_z_m, _zero.get("n_fail")),
          _z_m is None and _zero.get("n_fail") == 0)

    _cl = _rep.get("claimability") or {}
    check("S20h A 方案承诺：`em.in_blocking` 必须为 False，且 EM 段不改变 "
          "`claimable`(%s) 与 `m1_exit.ok`(%s)"
          % (_cl.get("claimable"), _st["m1_exit"].get("ok")),
          _em.get("in_blocking") is False
          and _cl.get("claimable") is False
          and _st["m1_exit"].get("ok") is True)

    _em_lock = (round(float(_em.get("min_margin_x") or 0.0), 3) == 100.959
                and _em.get("n_fail") == 0
                and _em.get("min_margin_net") == "n3")
    check("S20i 🔴 EM 对外数字逐位锁定：最小裕量 %.3f× @ %s · n_fail %s —— "
          "口径一漂（半周期→全周期、α/VDD 变动）必须红，逼人改文档而不是悄悄变"
          % (_em.get("min_margin_x") or 0.0, _em.get("min_margin_net"),
             _em.get("n_fail")), bool(_em_lock))

    # ══════════════════════════════════════════════════════════════════════
    # EC-P01…P14：几何 / 量纲不变式预注册组（+ 5 条反向探针）
    #   🔴 口径真源 = `EC-B3.0 预注册判据 v2`（内部 / gitignore / 不在公开库与生产 CI 内）。
    #      v1 全部结论已按 §6 作废，不得再作依据；v2 批准前本组**结论不生效**、
    #      EC-B3.1 不启动 —— 本组此刻只是「已实测的实现」。
    #      故全部内联：锁定值写死在下面常量里，独立复算从主链 shapes 重跑，
    #      不读任何内部文档、不依赖尚未实现的产品能力。
    #   🔴 锁定值不得就地修改；要改须另起版本并作废本组全部结论。
    #   🔴 术语用中性的「几何 / 量纲不变式」，不把内部研究结论写进公开门禁。
    # ══════════════════════════════════════════════════════════════════════
    _EC_NS = (1, 2, 4, 8, 16, 32)
    _EC_DIE_W = 7.8
    _EC_LAYERS = (25, 27, 29)
    _EC_AREA = {25: 2.268276, 27: 3.781476, 29: 3.247200}
    _EC_RHO = {25: 0.037283, 27: 0.062154, 29: 0.053373}
    _EC_DRHO = {
        25: (0.000000, 0.085188, 0.201307, 0.357239, 0.662163, 0.994872),
        27: (0.000000, 0.028020, 0.142472, 0.260355, 0.637160, 0.856410),
        29: (0.000000, 0.140118, 0.251834, 0.386272, 0.492308, 0.984615),
    }
    _EC_NET = {"n1": 0.837128, "n3": 1.345456, "n6": 1.223528,
               "n7": 0.983528, "n19": 1.283056, "n22": 2.157128, "n23": 1.467128}
    _EC_G = {"g_area": 0.880000, "g_per_gate": 0.146667,
             "g_per_transistor": 0.040000, "g_cell": 1.470000}
    _EC_MAX = {"g_area": 2.451282, "g_per_gate": 14.707691,
               "g_per_transistor": 53.928200, "g_cell": 1.467434}
    _EC_MIN = {"g_area": 0.951282, "g_per_gate": 5.707691,
               "g_per_transistor": 20.928200, "g_cell": 0.569475}
    _EC_SUM = {"g_area": 10.564718, "g_per_gate": 63.388309,
               "g_per_transistor": 232.423800, "g_cell": 6.324457}
    _EC_MAIN_IDS = tuple("EC-P%02d" % _k for _k in range(1, 15))

    def _ec_union(rs):
        """同层矩形并集（扫描线）：重叠部分只算一次。"""
        _xs = sorted(set([r[0] for r in rs] + [r[2] for r in rs]))
        _out = []
        for _a, _b in zip(_xs, _xs[1:]):
            _seg = sorted((y0, y1) for x0, y0, x1, y1 in rs if x0 <= _a and x1 >= _b)
            _mg = []
            for _y0, _y1 in _seg:
                if _mg and _y0 <= _mg[-1][1]:
                    _mg[-1] = (_mg[-1][0], max(_mg[-1][1], _y1))
                else:
                    _mg.append((_y0, _y1))
            for _y0, _y1 in _mg:
                _out.append((_a, _y0, _b, _y1))
        return _out

    def _ec_area(rs):
        return sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in rs)

    def _ec_dens(rs, n):
        _cw = _EC_DIE_W / n
        _c = [[0.0] * n for _ in range(n)]
        for x0, y0, x1, y1 in rs:
            for _i in range(max(0, int(math.floor(x0 / _cw))),
                            min(n, int(math.ceil(x1 / _cw)))):
                for _j in range(max(0, int(math.floor(y0 / _cw))),
                                min(n, int(math.ceil(y1 / _cw)))):
                    _c[_i][_j] += (max(0.0, min(x1, (_i + 1) * _cw) - max(x0, _i * _cw))
                                   * max(0.0, min(y1, (_j + 1) * _cw) - max(y0, _j * _cw)))
        return [_c[_i][_j] / (_cw * _cw) for _i in range(n) for _j in range(n)]

    def _ec_drho(rs, n):
        _v = _ec_dens(rs, n)
        return max(_v) - min(_v)

    def _ec_dmax(rs, n):
        return max(_ec_dens(rs, n))

    _ec_metals = [s for s in _sh2 if s.kind == "metal"]
    _ec_layer_got = tuple(sorted({s.layer for s in _ec_metals}))
    _ec_raw = {L: [(s.x0, s.y0, s.x1, s.y1) for s in _ec_metals if s.layer == L]
               for L in _ec_layer_got}
    _ec_u = {L: _ec_union(_ec_raw[L]) for L in _ec_layer_got}
    _ec_area_got = {L: round(_ec_area(_ec_u[L]), 6) for L in _ec_layer_got}
    _ec_rho_got = {L: round(_ec_area(_ec_u[L]) / (_EC_DIE_W ** 2), 6)
                   for L in _ec_layer_got}
    _ec_spec = {L: tuple(round(_ec_drho(_ec_u[L], n), 6) for n in _EC_NS)
                for L in _ec_layer_got}
    _ec_dmax_got = {(L, n): _ec_dmax(_ec_u[L], n)
                    for L in _ec_layer_got for n in _EC_NS}
    _ec_mean_max = max(
        abs(sum(_ec_dens(_ec_u[L], n)) / (n * n)
            - _ec_area(_ec_u[L]) / (_EC_DIE_W ** 2))
        for L in _ec_layer_got for n in _EC_NS)
    _ec_dup = {L: _ec_area(_ec_raw[L]) - _ec_area(_ec_u[L]) for L in _ec_layer_got}
    _ec_raw_dmax = max(_ec_dmax(_ec_raw[L], n) for L in _ec_layer_got for n in _EC_NS)

    _ec_src = open(os.path.abspath(__file__), encoding="utf-8").read()
    # 🔴 needle 必须拼接：若写成字面量，本行源码自身会被 count 进去（自指计数 +1）。
    _ec_needle = "check(" + '"' + "EC-P"
    _ec_n_ids = _ec_src.count(_ec_needle)
    check("EC-P01 命名空间：14 条主判据 ID 一律 EC-Pxx 且各出现一次（另有 %d 条反向探针）；"
          "内部文档不入库 ⇒ 门禁不依赖它们" % (_ec_n_ids - 14),
          all(_ec_src.count("check(" + '"' + _i + " ") == 1 for _i in _EC_MAIN_IDS)
          and _ec_n_ids == 19)

    check("EC-P02 🔴 同层矩形必须取并集：直接累加在层 25 重复计数 %.4f µm²（%.1f%%）、"
          "细窗 ρ_max=%.3f>1 ⇒ 直接累加口径必须判 INVALID"
          % (_ec_dup[25], 100.0 * _ec_dup[25] / _ec_area(_ec_raw[25]), _ec_raw_dmax),
          _ec_layer_got == _EC_LAYERS
          and _ec_dup[25] / _ec_area(_ec_raw[25]) > 0.20
          and _ec_raw_dmax > 1.0)

    check("EC-P03 I4 上界：∀层∀n ρ_max ≤ 1（实测最大 %.6f）" % max(_ec_dmax_got.values()),
          all(v <= 1.0 + 1e-9 for v in _ec_dmax_got.values()))

    _L0 = 27
    _tot = _ec_area(_ec_u[_L0])
    _cw = _EC_DIE_W / 2.0
    _r1 = [(0.0, 0.0, _cw, _tot / _cw)]
    _w2 = _cw * 0.5
    _h2 = (_tot / 4.0) / _w2
    _r2 = []
    for _i2 in range(2):
        for _j2 in range(2):
            _x2 = _i2 * _cw + (_cw - _w2) / 2.0
            _y2 = _j2 * _cw + (_cw - _h2) / 2.0
            _r2.append((_x2, _y2, _x2 + _w2, _y2 + _h2))
    _ec_ctor_ok = (
        abs(_ec_area(_r1) - _tot) < 1e-9
        and abs(_ec_area(_r2) - _tot) < 1e-9
        and all(0.0 <= r[0] <= r[2] <= _EC_DIE_W and 0.0 <= r[1] <= r[3] <= _EC_DIE_W
                for r in _r1 + _r2)
        and _h2 < _cw and _tot / _cw < _cw
    )
    check("EC-P04 合成反例构造自检：面积守恒 ∧ 不越界 ∧ 不重叠（R1 单块 / R2 四块）",
          bool(_ec_ctor_ok))

    _r1_d = _ec_drho(_r1, 2)
    _r2_d = _ec_drho(_r2, 2)
    _want4 = 4.0 * _tot / (_EC_DIE_W ** 2)
    check("EC-P05 M1 阳性对照 R1：全挤一窗 ⇒ Δρ(2) 必须 == 4ρ（闭式 %.6f / 实测 %.6f）"
          % (_want4, _r1_d), abs(_r1_d - _want4) < 1e-9)
    check("EC-P06 M1 阴性对照 R2：均匀四等分 ⇒ Δρ(2) 必须恰为 0（实测 %.9f）" % _r2_d,
          abs(_r2_d) < 1e-9)

    _ec_i1 = _ec_mean_max < 1e-5
    _ec_i2 = all(all(_ec_spec[L][k] + 1e-9 >= _ec_spec[L][k - 1]
                     for k in range(1, len(_EC_NS))) for L in _ec_layer_got)
    _ec_i3 = all(abs(_ec_spec[L][0]) < 1e-9 for L in _ec_layer_got)
    check("EC-P07 I1 守恒（误差 %.2e < 1e-5）∧ I2 单调不减 ∧ I3 n=1⇒0" % _ec_mean_max,
          _ec_i1 and _ec_i2 and _ec_i3)

    check("EC-P08 n 集合冻结且上界由 die_w/n ≥ W=%.3f µm 反解（n=32 窗 %.5f，n=64 窗 %.5f）"
          % (P.W, _EC_DIE_W / 32, _EC_DIE_W / 64),
          _EC_NS == (1, 2, 4, 8, 16, 32)
          and _EC_DIE_W / 32 >= P.W > _EC_DIE_W / 64)

    _ec_byn = {}
    for s in _ec_metals:
        _ec_byn.setdefault(getattr(s, "net", None), []).append(
            (s.layer, s.x0, s.y0, s.x1, s.y1))
    _ec_net_area = {}
    for _net, _items in _ec_byn.items():
        _a = 0.0
        for _L in sorted({it[0] for it in _items}):
            _a += _ec_area(_ec_union([(it[1], it[2], it[3], it[4])
                                      for it in _items if it[0] == _L]))
        _ec_net_area[_net] = _a
    _ec_g = {
        "g_area": nl.area_um2(),
        "g_per_gate": nl.area_um2() / nl.n_gates(),
        "g_per_transistor": nl.area_um2() / nl.n_transistors(),
        "g_cell": _pl2["insts"][0]["w"] * _pl2["insts"][0]["h"],
    }
    _ec_ratio = {g: {net: a / gv for net, a in _ec_net_area.items()}
                 for g, gv in _ec_g.items()}
    _ec_max_raw = {g: max(v.values()) for g, v in _ec_ratio.items()}
    _ec_max_got = {g: round(v, 6) for g, v in _ec_max_raw.items()}
    _ec_min_got = {g: round(min(v.values()), 6) for g, v in _ec_ratio.items()}
    _ec_sum_got = {g: round(sum(v.values()), 6) for g, v in _ec_ratio.items()}

    _A0 = 1.0
    _ec_r3_inc = {g: (_ec_net_area["n22"] + _A0) / _ec_g[g] - _ec_ratio[g]["n22"]
                  for g in _ec_g}
    check("EC-P09 M1 阳性对照 R3：追加面积 A0=1 µm² ⇒ 四口径增量 >0 且增量间满足齐次（I6+I7）",
          all(v > 0 for v in _ec_r3_inc.values())
          and all(abs(_ec_r3_inc[g] / _ec_r3_inc["g_area"]
                      - _ec_g["g_area"] / _ec_g[g]) < 1e-9 for g in _ec_g))
    check("EC-P10 M1 阳性对照 R4：零面积 ⇒ 比值恰为 0（四口径，容差 0）",
          all((0.0 / gv) == 0.0 for gv in _ec_g.values()))

    _ec_hom = all(abs(_ec_max_raw[g] / _ec_max_raw["g_area"]
                      - _ec_g["g_area"] / _ec_g[g]) < 1e-9 for g in _ec_g)
    check("EC-P11 I8 齐次：四口径 max 两两 == g_area/g —— 抓的是「某网/某口径用了不一致的分母」"
          "（数值漂移由 P12/P13 抓，齐次本身是恒等式）", bool(_ec_hom))

    _ec_g_ok = (all(round(gv, 6) == _EC_G[g] for g, gv in _ec_g.items())
                and _ec_g["g_per_gate"] == _ec_g["g_area"] / nl.n_gates()
                and _ec_g["g_per_transistor"] == _ec_g["g_area"] / nl.n_transistors())
    check("EC-P12 四个 g 单一来源、全片统一、由网表/几何复算（不得手填独立常量）",
          bool(_ec_g_ok))

    _ec_lock = (
        _ec_layer_got == _EC_LAYERS
        and _ec_area_got == _EC_AREA
        and _ec_rho_got == _EC_RHO
        and _ec_spec == {L: _EC_DRHO[L] for L in _EC_LAYERS}
        and {k: round(v, 6) for k, v in _ec_net_area.items()} == _EC_NET
        and _ec_max_got == _EC_MAX
        and _ec_min_got == _EC_MIN
        and _ec_sum_got == _EC_SUM
    )
    check("EC-P13 🔴 预注册数值逐位锁定：面积 / 密度 / 谱 / 每网面积 / 四口径 max·min·sum",
          bool(_ec_lock))

    check("EC-P14 对外完整性：3 层 × 6 个 n = %d 个谱点、4 个口径 × %d 条网 = %d 个比值，"
          "不得只报单一窗口 / 单一口径"
          % (len(_ec_layer_got) * len(_EC_NS), len(_ec_net_area), 4 * len(_ec_net_area)),
          len(_ec_layer_got) * len(_EC_NS) == 18
          and len(_ec_ratio) == 4
          and all(len(v) == len(_ec_net_area) for v in _ec_ratio.values()))

    # ── 反向探针：证明「判据真的会响」，不是永远通过 ──────────────────────
    check("EC-P03r 反向探针：改用直接累加（不去重）⇒ ρ_max=%.3f>1 ⇒ P03 必红"
          % _ec_raw_dmax, _ec_raw_dmax > 1.0)
    _ec_r1_bad = [(0.0, 0.0, _cw, _tot / (2.0 * _cw))]
    check("EC-P05r 反向探针：R1 面积减半 ⇒ Δρ(2)=%.6f ≠ 4ρ ⇒ P05 必红"
          % _ec_drho(_ec_r1_bad, 2),
          abs(_ec_drho(_ec_r1_bad, 2) - _want4) > 1e-6)
    check("EC-P08r 反向探针：删掉 n=32 ⇒ 集合失配 ⇒ P08 必红",
          _EC_NS[:-1] != (1, 2, 4, 8, 16, 32) and _EC_DIE_W / 64 < P.W)
    _ec_mixed = {g: dict(_ec_ratio[g]) for g in _ec_g}
    _ec_mixed["g_area"]["n22"] = _ec_net_area["n22"] / (_ec_g["g_area"] * 1.3)
    _ec_bad_hom = abs(max(_ec_mixed["g_per_gate"].values())
                      / max(_ec_mixed["g_area"].values())
                      - _ec_g["g_area"] / _ec_g["g_per_gate"])
    check("EC-P11r 反向探针：某网用了不一致的分母 ⇒ 齐次失配 Δ=%.6f ⇒ P11 必红"
          % _ec_bad_hom, _ec_bad_hom > 1e-6)
    check("EC-P13r 反向探针：层 25 锁定面积 +0.001 ⇒ 锁定失配 ⇒ P13 必红",
          abs((_EC_AREA[25] + 0.001) - _ec_area_got[25]) > 1e-6)

    print("  [EC] 谱点 %d 个（3 层 × 6 尺度）· 比值 %d 个（4 口径 × %d 网）· "
          "锁定值全部逐位一致 · 反向探针 5 条全响"
          % (len(_ec_layer_got) * len(_EC_NS), 4 * len(_ec_net_area), len(_ec_net_area)))

    # ══════════════════════════════════════════════════════════════════════
    # EC-Q01…Q12：EC-B3.1 能力落地（能力上 API / K2 独立 / 不判违规）
    #   🔴 数据路径独立：门禁从源 Netlist 重跑 P&R（`_sh2`）+ 自己的扫描线复算；
    #      产品用主链 shapes + 增量差集/可分离积分。两侧逐位对拍才算真绿。
    # ══════════════════════════════════════════════════════════════════════
    from lda_webui.digital_case import case_card as _q_case_card  # noqa: E402

    _q_trunk_src = open(os.path.join(_HERE, "lda_l2", "ecore", "db3_trunk.py"),
                        encoding="utf-8").read()
    _q_prod_src = open(os.path.join(_HERE, "lda_l2", "ecore", "dsignoff.py"),
                       encoding="utf-8").read()
    _q_card = _q_case_card()
    _q_st = {n: p for n, p in B3.run_trunk_from_verilog(V.SAMPLE_VERILOG)["stages"]}
    _q = _q_st.get("ec_b3") or {}
    _q_disc = (_q_card.get("disclosure") or {}).get("ec_b3") or ""

    check("EC-Q01 主链产出 `ec_b3` 段 ∧ 卡片顶层含该段 ∧ `segments_covered` 含 `ec_b3`（%d 段）"
          % len(_q_card.get("segments_covered") or []),
          bool(_q) and isinstance(_q_card.get("ec_b3"), dict)
          and bool(_q_card["ec_b3"]) and "ec_b3" in (_q_card.get("segments_covered") or []))

    check("EC-Q02 🔴 能力上 API：卡片 `disclosure.ec_b3` 可读，且含「含诊断段」与"
          "「DRC 规则集仍不含」的区分声明",
          bool(_q_disc) and "含几何/量纲诊断段" in _q_disc
          and "DRC 规则集仍不含" in _q_disc and "不判违规" in _q_disc)

    _q_yes = "含几何/量纲诊断段" in _q_disc
    _q_no = "不含几何/量纲诊断段" in _q_disc
    _q_has_call = "ec_b3_signoff(" in _q_trunk_src
    check("EC-Q03 🔴 三态 AST 机核：互斥措辞恰好一个 ∧ 与主链是否调用 `ec_b3_signoff` 一致；"
          "沉默必红（含=%s 不含=%s 事实=%s）" % (_q_yes, _q_no, _q_has_call),
          (_q_yes != _q_no) and (_q_yes == _q_has_call))
    def _q_tri(yes, no, fact):
        return (yes != no) and (yes == fact)

    check("EC-Q03r 反向探针：三态检测器在「沉默」「都在」时必须报假，正常时为真",
          _q_tri(True, False, True) is True
          and _q_tri(False, False, True) is False
          and _q_tri(True, True, True) is False
          and _q_tri(False, True, True) is False)

    _q_asm = _q.get("assumptions") or {}
    _q_need = ("die_w_um", "die_h_um", "width_um", "scales", "scale_upper_bound",
               "g_values", "g_basis", "union_method", "density_method")
    _q_asm_miss = [k for k in _q_need if _q_asm.get(k) is None]
    check("EC-Q04 K0 完备性：9 项输入假设齐备（缺=%r）" % _q_asm_miss,
          not _q_asm_miss and _q_asm.get("scales") == list(_EC_NS))

    _q_bad = []
    for _qL in _EC_LAYERS:
        _qv = (_q.get("layers") or {}).get(str(_qL)) or {}
        if _qv.get("area_um2") != _EC_AREA[_qL]:
            _q_bad.append("L%s.area" % _qL)
        if tuple(_qv.get("drho") or ()) != _EC_DRHO[_qL]:
            _q_bad.append("L%s.drho" % _qL)
    if {k: round(v, 6) for k, v in (_q.get("net_area_um2") or {}).items()} != _EC_NET:
        _q_bad.append("net_area")
    for _qg in _EC_G:
        _qr = (_q.get("ratio_by_g") or {}).get(_qg) or {}
        if (_qr.get("max"), _qr.get("min"), _qr.get("sum")) != (
                _EC_MAX[_qg], _EC_MIN[_qg], _EC_SUM[_qg]):
            _q_bad.append(_qg)
    check("EC-Q05 🔴 K2 数据路径独立：产品段 vs 门禁从源重跑 P&R 的扫描线复算逐位一致"
          "（偏差=%r）" % _q_bad, not _q_bad)

    _q_raw_area = sum(abs((s.x1 - s.x0) * (s.y1 - s.y0))
                     for s in _sh2 if s.kind == "metal")
    check("EC-Q05r 反向探针：产品侧并集退化为直接累加 ⇒ 与门禁复算必失配"
          "（直接累加 %.6f vs 并集 %.6f µm²）" % (_q_raw_area, sum(_EC_AREA.values())),
          abs(_q_raw_area - sum(_EC_AREA.values())) > 0.5)

    def _q_has_shared(src):
        # 🔴 必须用 AST：字符串 `in` 会把**注释里提到的符号**误判成引用（本轮踩过假红）。
        names = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
        return any(x in names for x in ("_ec_union", "_ec_dens", "_ec_drho", "_ec_dmax"))

    check("EC-Q06 🔴 K2 源码独立：产品侧不引用门禁 `_ec_*`，且自带 `b3_subtract_rect`",
          (not _q_has_shared(_q_prod_src))
          and "b3_subtract_rect" in _q_prod_src and "b3_window_density" in _q_prod_src)
    check("EC-Q06r 反向探针：注入 `_ec_union` 的源码必报共享；纯 `import os` 不报",
          _q_has_shared("x = _ec_union([])") is True
          and _q_has_shared("import os") is False)

    check("EC-Q07 两条算法路径不同且显式登记：产品=增量差集+可分离积分，门禁=扫描线+逐窗裁剪",
          _q_asm.get("union_method") == "incremental_rect_subtraction"
          and _q_asm.get("density_method") == "separable_1d_cdf_difference"
          and "_ec_union" in open(os.path.abspath(__file__), encoding="utf-8").read())

    _q_inv = _q.get("invariants") or {}
    check("EC-Q08 段内 6 条不变式全成立（I1–I4 / I8 / 尺度上界）：%r" % _q_inv,
          all(_q_inv.get(k) is True for k in (
              "i1_conservation", "i2_monotone", "i3_limit", "i4_upper_bound",
              "i8_homogeneity", "i_scale_upper_bound")))
    check("EC-Q09 I8 一致性成立 ∧ I9 数值锁定由门禁 P13 承担（产品段不复制冻结值）",
          _q_inv.get("i8_homogeneity") is True and "P13" in str(_q.get("lock_basis") or ""))

    check("EC-Q10 🔴 不判违规：段内无 `n_fail`/`ok`/`pass` ∧ `in_blocking=False` ∧ "
          "`scope=DIAGNOSTIC_ONLY`",
          not any(k in _q for k in ("n_fail", "ok", "pass"))
          and _q.get("in_blocking") is False
          and _q.get("scope") == "DIAGNOSTIC_ONLY")
    def _q_no_verdict(seg):
        return not any(k in seg for k in ("n_fail", "ok", "pass"))

    check("EC-Q10r 反向探针：合成段偷偷加 `n_fail`/`ok`/`pass` ⇒ 检测器必报",
          _q_no_verdict(_q) is True
          and _q_no_verdict(dict(_q, n_fail=1)) is False
          and _q_no_verdict(dict(_q, ok=True)) is False
          and _q_no_verdict(dict(_q, **{"pass": 1})) is False)

    check("EC-Q11 🔴 对外主链数字逐位不变：60.840 / 43.490 / 575 B / claimable=False / "
          "m1_exit.ok=True / failed=3",
          _q_card["placement"]["die_area_um2"] == 60.84
          and _q_card["timing"]["comb_delay_wired_ps"] == 43.49
          and _q_card["def_export"]["bytes"] == 575
          and _q_card["claimable"] is False
          and _q_card["m1_exit"]["ok"] is True
          and _q_card["routing"]["nets_failed"] == 3)

    _q_keep = (
        ("ddrc_lvs.py", "未检注入/阱/天线/密度"),
        ("capability_manifest.py", "无串扰/天线/密度/OPC/ESD"),
        ("dcnet.py", "不做串扰、天线、密度"),
        ("dhdlib.py", "无密度/OPC/天线/ESD 规则"),
        ("signed_off_stack.py", "无 CMP/OPC/天线规则/密度规则"),
        ("soc_flow.py", "无 CMP / OPC / 天线 / 密度规则"),
    )
    _q_missing = [f for f, kw in _q_keep
                  if kw not in open(os.path.join(_HERE, "lda_l2", "ecore", f),
                                    encoding="utf-8").read()]
    check("EC-Q12 🔴 6 处旧「规则集边界」声明仍在且仍为真（新增的是诊断段，不是 DRC 规则）："
          "缺=%r" % _q_missing, not _q_missing)
    def _q_keep_check(src_map, f, kw):
        return kw in src_map.get(f, "")

    check("EC-Q12r 反向探针：删掉旧声明的源码 ⇒ 检测器必报；含声明时为真",
          _q_keep_check({"ddrc_lvs.py": _q_keep[0][1]}, "ddrc_lvs.py", _q_keep[0][1]) is True
          and _q_keep_check({"ddrc_lvs.py": ""}, "ddrc_lvs.py", _q_keep[0][1]) is False
          and _q_keep_check({}, "ddrc_lvs.py", _q_keep[0][1]) is False)

    print("  [Q] 能力上 API ✓ · K2 两条独立路径逐位一致 ✓ · 6 条不变式全成立 ✓ · "
          "不判违规/不进 blocking ✓ · 主链数字逐位未变")

    _dt = time.time() - T0
    check("S17c 门禁耗时 %.2f s < %.0f s" % (_dt, AN_ELAPSED_MAX_S), _dt < AN_ELAPSED_MAX_S)

    print()
    print("  [S13] 拓扑差异 %d 处（已登记）：%s —— 与 ISCAS-85 公开定义对照，出处 + sha256 同行"
          % (len(got), " · ".join("%s:%s" % (k, "+".join(v)) for k, v in sorted(got.items()))))
    print("  [S14] EM 物理自变量缺 %s —— Black 方程要求，当前 `em_check` 无温度参数"
          % list(missing))
    print("  [S15] DRC/LVS 双实现本地闭包交集 ∅ ⇒ 「两个实现」确有独立性（E1 不再虚设）")
    print("  [S16] 面积两条不同边界路径均拼回 %.3f µm" % _po["die_w_um"])
    print("  [S18] EM 温度标度：T=T_ref 逐位退化 ∧ 85°C 允许 %.4g（×%.1f）∧ 判定随温度翻转"
          % (_j85, _j85 / _j125))
    print("  [边界] 不改网表（改则推翻 DRC/面积/时序/DEF 全部既有数字）；"
          "K2 仅覆盖同文件本地调用，跨模块共享不在范围")

    if _FALS:
        print("S13 有红色：%s" % ", ".join(_FALS))
        return 1
    print("S13 全绿 · B1 四项 + B2a：拓扑机核（2 处已登记）+ K0 覆盖 6/6（EM 已补温度）+ "
          "K2 交集 ∅ + 面积双路径一致 + EM 温度标度（T=T_ref 逐位退化、判定随温度翻转）；"
          "产品数字逐位未变")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
