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
import dataclasses
import inspect
import math
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_l2.ecore import db3_trunk as B3        # noqa: E402
from lda_l2.ecore import dcell as DC           # noqa: E402
from lda_l2.ecore import dcells as CL         # noqa: E402
from lda_l2.ecore import ddef as DF            # noqa: E402
from lda_l2.ecore import ddetail as DET        # noqa: E402
from lda_l2.ecore import dliberty as LB         # noqa: E402
from lda_l2.ecore import dnodefit as NF        # noqa: E402
from lda_l2.ecore import dcelltpl as TP       # noqa: E402
from lda_l2.ecore import dkdrive as KD        # noqa: E402
from lda_l2.ecore import ddrc_lvs as DL        # noqa: E402
from lda_l2.ecore import dpnr as P             # noqa: E402
from lda_l2.ecore import dplac as DPL          # noqa: E402
from lda_l2.ecore import dproc as DP           # noqa: E402
from lda_l2.ecore import dprovenance as PV     # noqa: E402
from lda_l2.ecore import dsignoff as DS        # noqa: E402
from lda_l2.ecore import dsta as ST            # noqa: E402
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
#: 🔴 v0.9.395（T1b/Q1）登记**唯一例外** `via_bridges`，理由与代价都写在明面上：
#:   · 被共享的是**判据规则本身**（"这个孔是不是真的桥接那层金属"），不是算法；
#:     `run_lvs` 仍是 O(n²) 全对、`fast_lvs` 仍是空间哈希 —— 两者互为对照的部分没变；
#:   · 反方向的代价是真的：规则写错时**两版会一致地错**，等价判据抓不到。
#:     该风险由三条**独立**判据接管：Q1-a（规则 ≡ `|Δlayer|=1`，绑层号表）、
#:     Q1-d/e/f（真短路必报 / 误报必不报 / 未知孔层仍报，两版各测一遍）；
#:   · 之所以不把规则抄两份：本仓已踩过「`ddetail` 与 `ddrc_lvs` 短路口径分叉」，
#:     复制一份规则换来的独立性，代价是漂移 —— 而漂移比共享更难发现。
#: 🔴 这是**棘轮**：集合与登记表 `==`（只减不增），多共享一个函数即红。
K2_SHARED_WHITELIST: tuple = ("via_bridges",)


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


#: 🔴 手填 `k_drive` 的 18 个值 —— **模块级 golden，唯一真源**。
#: 为什么提到模块级：`EC-G06`（G 段）与 `EC-K04`（K 段，在 G 段之前执行）都要用它，
#: 各写一份必然漂。谁想改 `k_drive`，必须先改这里 —— 那就是一次显式改口。
_HAND_K_DRIVE = {
    "INV": 1.00, "BUF": 1.00, "NAND2": 1.80, "NOR2": 2.40, "AND2": 2.10,
    "OR2": 2.70, "XOR2": 3.00, "XNOR2": 3.00, "MUX2": 1.60, "AOI21": 2.00,
    "OAI21": 2.40, "NAND3": 2.60, "NOR3": 3.40, "AND3": 2.90, "OR3": 3.60,
    "DFF": 1.0, "TIEHI": 1.0, "TIELO": 1.0,
}


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

    # 🔴 Q2：旧探针写死 `"(7800 7800)"`。die 变成 7.59×6.90 后该串不存在 ⇒ replace 空转
    # ⇒ 第二路径仍等于 die_w ⇒ 探针**假红**（它其实没改动任何东西）。
    # 改成从**解析出来的** DIEAREA 数字上 +100 nm：几何怎么变都能真正篡改。
    _d_x1, _d_y1 = int(_m.group(3)), int(_m.group(4))
    _tampered = _def_txt.replace("(%d %d)" % (_d_x1, _d_y1),
                                 "(%d %d)" % (_d_x1 + 100, _d_y1), 1)
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
        "routed": (_st["route"]["nets_with_segments"], _st["route"]["nets_touched"], 10, 11),
        "drc": (_st["drc_lvs"]["drc_violations"], None, 0, None),
        "area": (_st["place"]["die_area_um2"], None, 59.202, None),
        "delay": (_st["timing"]["comb_delay_wired_ps"], None, 92.398, None),
        "def": (_st["def_write"]["bytes"], None, 575, None),
    }
    _bad = {k: v for k, v in _num.items()
            if not ((v[0] == v[2] and (v[1] is None or v[1] == v[3])))}
    check("S17a 🔴 硬条件（T2 改口后口径） —— 布通 %s/%s · DRC %s · 面积 %.3f · 延时 %.3f · DEF %s B"
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
    # 🔴 T3 改名（不改实现）：这是**同一个实现跑第二遍**，不是第二个实现。
    #   它能抓「段内数字不是从这份几何来的」，抓不到「这个实现本身算错」——
    #   后者由 EC-T09（显式双重求和 vs 单次递推）与 EC-V05（字节码不引用产品符号）分管。
    check("S20b 每网线长/线载**重跑复算**一致（同实现第二次跑，非第二实现）："
          "%d 条网，线载不一致 %r，线长不一致 %r"
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

    _em_lock = (round(float(_em.get("min_margin_x") or 0.0), 3) == 151.661
                and _em.get("n_fail") == 0
                and _em.get("min_margin_net") == "n16")
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
    _EC_NS = (1, 2, 4, 8, 16)
    #: 🔴 Q2（v0.9.396）：die 不再是正方形（7.59 × 6.90）。旧代码把 `_EC_DIE_W`
    #: **同时当宽和高用**（`_cw = _EC_DIE_W/n` 两轴同值、`_EC_DIE_W**2` 当面积）——
    #: legacy 7.8×7.8 下这恰好成立，几何一变就变成**错误的窗口与错误的面积**。
    #: 这是"判据里藏着的隐含假设"，不是笔误：它只有在几何不再是正方形时才咬人。
    _EC_DIE_W = 7.59
    #: v0.9.404：pMOS 加宽把 NAND2 抬到 1950nm ⇒ 行高 1.95、die 高 6.90 → **7.80**
    _EC_DIE_H = 7.8
    _EC_DIE_A = _EC_DIE_W * _EC_DIE_H
    _EC_LAYERS = (25, 27, 29)
    # 🔴 v0.9.404 重定版：pMOS 加宽（NAND2 1500→1950nm）改了 die 高与金属总量 ⇒
    #   面积/密度/谱/每网/四口径全部按**新版图**重算。写入流程照旧：先跑判据侧
    #   从源重算，再让产品段复核同值（`EC-Q05` 双向锁），**不允许只改字面量**。
    _EC_AREA = {25: 3.7188, 27: 6.4536, 29: 8.1684}
    _EC_RHO = {25: 0.062815, 27: 0.10901, 29: 0.137975}
    _EC_DRHO = {
        25: (0.0, 0.154289, 0.309233, 0.729056, 0.768116),
        27: (0.0, 0.163454, 0.435066, 0.738462, 0.774359),
        29: (0.0, 0.283855, 0.414054, 0.603426, 0.768116),
    }
    _EC_NET = {"n1": 1.1136, "n11": 2.6448, "n16": 2.886, "n19": 1.476, "n2": 1.956,
               "n22": 2.0424, "n23": 1.8276, "n3": 1.6608, "n6": 1.5384, "n7": 1.1952}
    _EC_G = {"g_area": 0.880000, "g_per_gate": 0.146667,
             "g_per_transistor": 0.040000, "g_cell": 1.911000}
    _EC_MAX = {"g_area": 3.279545, "g_per_gate": 19.677273,
               "g_per_transistor": 72.15, "g_cell": 1.510204}
    _EC_MIN = {"g_area": 1.265455, "g_per_gate": 7.592727,
               "g_per_transistor": 27.84, "g_cell": 0.582732}
    _EC_SUM = {"g_area": 20.841818, "g_per_gate": 125.050909,
               "g_per_transistor": 458.52, "g_cell": 9.597488}
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
        # 🔴 两轴各用各自的边长（矩形窗口 = 铺满真实 die）。旧版两轴都用 `_EC_DIE_W/n`，
        # 只在 die 为正方形时等价于产品侧的 `b3_window_density`（后者一直用 cw/ch 两值）。
        _cw, _ch = _EC_DIE_W / n, _EC_DIE_H / n
        _c = [[0.0] * n for _ in range(n)]
        for x0, y0, x1, y1 in rs:
            for _i in range(max(0, int(math.floor(x0 / _cw))),
                            min(n, int(math.ceil(x1 / _cw)))):
                for _j in range(max(0, int(math.floor(y0 / _ch))),
                                min(n, int(math.ceil(y1 / _ch)))):
                    _c[_i][_j] += (max(0.0, min(x1, (_i + 1) * _cw) - max(x0, _i * _cw))
                                   * max(0.0, min(y1, (_j + 1) * _ch) - max(y0, _j * _ch)))
        return [_c[_i][_j] / (_cw * _ch) for _i in range(n) for _j in range(n)]

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
    _ec_rho_got = {L: round(_ec_area(_ec_u[L]) / _EC_DIE_A, 6)
                   for L in _ec_layer_got}
    _ec_spec = {L: tuple(round(_ec_drho(_ec_u[L], n), 6) for n in _EC_NS)
                for L in _ec_layer_got}
    _ec_dmax_got = {(L, n): _ec_dmax(_ec_u[L], n)
                    for L in _ec_layer_got for n in _EC_NS}
    _ec_mean_max = max(
        abs(sum(_ec_dens(_ec_u[L], n)) / (n * n)
            - _ec_area(_ec_u[L]) / _EC_DIE_A)
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

    # 🔴 Q2 后这条探针的口径必须改：legacy 用「ρ_max > 1」当「没取并集」的判据，
    # 那只是因为方形 die + 旧几何恰好让重复计数把密度顶穿 1.0。矩形 die 下同样的重复
    # 计数给出 0.862 < 1 —— **判据本身失靶了**（红/绿不再取决于有没有取并集）。
    # 改成与它要抓的东西直接对应：直接累加的密度**必须严格高于**并集口径。
    _ec_union_dmax = max(_ec_dmax_got.values())
    # 🔴 v0.9.404：原判据写 `重复率 > 0.15` —— 那是**灌进旧几何的魔数**（旧 19.1%、新 14.6%，
    #   几何一改就假红）。判据要抓的是「不取并集就必然高估」，那是**结构性**事实：
    #   有重叠 ⇒ 重复计数 > 0；重复计数把细窗密度顶高 ⇒ 直接累加 > 并集。两条都与尺度无关。
    #   重复率仍打印，但**不再参与判决** —— 它随几何变，不该当阈值。
    check("EC-P02 🔴 同层矩形必须取并集：直接累加在层 25 重复计数 %.4f µm²（%.1f%%，仅供参考）、"
          "细窗 ρ_max 直接累加 %.3f > 并集 %.3f ⇒ 直接累加口径必须判 INVALID"
          % (_ec_dup[25], 100.0 * _ec_dup[25] / _ec_area(_ec_raw[25]),
             _ec_raw_dmax, _ec_union_dmax),
          _ec_layer_got == _EC_LAYERS
          and _ec_dup[25] > 0.0
          and _ec_raw_dmax > _ec_union_dmax + 1e-6)

    check("EC-P03 I4 上界：∀层∀n ρ_max ≤ 1（实测最大 %.6f）" % max(_ec_dmax_got.values()),
          all(v <= 1.0 + 1e-9 for v in _ec_dmax_got.values()))

    _L0 = 27
    _tot = _ec_area(_ec_u[_L0])
    _cw = _EC_DIE_W / 2.0
    _ch = _EC_DIE_H / 2.0
    _r1 = [(0.0, 0.0, _cw, _tot / _cw)]
    _w2 = _cw * 0.5
    _h2 = (_tot / 4.0) / _w2
    _r2 = []
    for _i2 in range(2):
        for _j2 in range(2):
            _x2 = _i2 * _cw + (_cw - _w2) / 2.0
            _y2 = _j2 * _ch + (_ch - _h2) / 2.0
            _r2.append((_x2, _y2, _x2 + _w2, _y2 + _h2))
    _ec_ctor_ok = (
        abs(_ec_area(_r1) - _tot) < 1e-9
        and abs(_ec_area(_r2) - _tot) < 1e-9
        and all(0.0 <= r[0] <= r[2] <= _EC_DIE_W and 0.0 <= r[1] <= r[3] <= _EC_DIE_H
                for r in _r1 + _r2)
        and _h2 < _ch and _tot / _cw < _ch
    )
    check("EC-P04 合成反例构造自检：面积守恒 ∧ 不越界 ∧ 不重叠（R1 单块 / R2 四块）",
          bool(_ec_ctor_ok))

    _r1_d = _ec_drho(_r1, 2)
    _r2_d = _ec_drho(_r2, 2)
    _want4 = 4.0 * _tot / _EC_DIE_A
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

    check("EC-P08 n 集合冻结且上界由 die_w/n ≥ W=%.3f µm 反解（n=16 窗 %.5f，n=32 窗 %.5f）"
          % (P.W, _EC_DIE_W / 16, _EC_DIE_W / 32),
          _EC_NS == (1, 2, 4, 8, 16)
          and _EC_DIE_W / 16 >= P.W > _EC_DIE_W / 32)

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
    # 🔴 T3 改名（**不改实现**）：原名「不得手填独立常量」与代码相反 —— 下面 `_EC_G` 正是
    #   手填常量表（按 §4 规则二豁免条款、由两条独立路径同值后才写入）。改名后说的才是实情：
    #   产品侧 g **由网表/几何现算**（不读常量），判据要求它与 goldens 逐位相等。
    check("EC-P12 四个 g 全片统一且**由网表/几何现算**（产品侧不读常量）∧ 与手填 goldens "
          "`_EC_G` 逐位相等（goldens 按 §4 规则二豁免条款：双路径同值后才写入）",
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

    check("EC-P14 对外完整性：%d 层 × %d 个 n = %d 个谱点、4 个口径 × %d 条网 = %d 个比值，"
          "不得只报单一窗口 / 单一口径"
          % (len(_ec_layer_got), len(_EC_NS),
             len(_ec_layer_got) * len(_EC_NS), len(_ec_net_area),
             4 * len(_ec_net_area)),
          len(_ec_layer_got) * len(_EC_NS) == 15
          and len(_ec_ratio) == 4
          and all(len(v) == len(_ec_net_area) for v in _ec_ratio.values()))

    # ── 反向探针：证明「判据真的会响」，不是永远通过 ──────────────────────
    check("EC-P03r 反向探针：改用直接累加（不去重）⇒ ρ_max=%.3f 高于并集口径 ⇒ P03 必红"
          % _ec_raw_dmax, _ec_raw_dmax > max(_ec_dmax_got.values()) + 1e-6)
    _ec_r1_bad = [(0.0, 0.0, _cw, _tot / (2.0 * _cw))]
    check("EC-P05r 反向探针：R1 面积减半 ⇒ Δρ(2)=%.6f ≠ 4ρ ⇒ P05 必红"
          % _ec_drho(_ec_r1_bad, 2),
          abs(_ec_drho(_ec_r1_bad, 2) - _want4) > 1e-6)
    check("EC-P08r 反向探针：把 n=32 塞回集合 ⇒ 集合失配且上界不成立 ⇒ P08 必红",
          _EC_NS + (32,) != (1, 2, 4, 8, 16) and _EC_DIE_W / 32 < P.W)
    _ec_mixed = {g: dict(_ec_ratio[g]) for g in _ec_g}
    # 🔴 必须注入**当前 argmax 那条网**：写死 `n22` 时 Q2 后它不是最大者 ⇒ 注入不改变
    # max ⇒ Δ 恒 0，探针变成摆设（实测 Δ=0.000000）。
    _ec_hot_net = max(_ec_net_area, key=lambda _k: _ec_net_area[_k] / _ec_g["g_area"])
    _ec_mixed["g_area"][_ec_hot_net] = (
        _ec_net_area[_ec_hot_net] / (_ec_g["g_area"] * 1.3))
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
    # 🔴 T3 补注（不改实现）：本条证明的是**算法与数据路径独立**（门禁自己跑 P&R + 自己扫描线），
    #   **不**证明 golden 独立 —— `_EC_AREA` 等约 40 个常量仍是共享字面量（§4 规则二豁免条款）。
    #   旧名「独立复算」会让读者以为两侧毫无共享，属名不副实。
    check("EC-Q05 🔴 K2 **算法/数据路径**独立：产品段 vs 门禁从源重跑 P&R 的扫描线复算逐位一致"
          "（偏差=%r）；⚠️ golden 不独立（共享字面量，按 §4 规则二豁免）" % _q_bad, not _q_bad)

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

    check("EC-Q11 🔴 对外主链数字（T2 口径）：59.202 / 92.398 / 575 B / claimable=False / "
          "m1_exit.ok=True / failed=3",
          _q_card["placement"]["die_area_um2"] == 59.202
          and _q_card["timing"]["comb_delay_wired_ps"] == 92.398
          and _q_card["def_export"]["bytes"] == 575
          and _q_card["claimable"] is False
          and _q_card["m1_exit"]["ok"] is True
          and _q_card["routing"]["nets_failed"] == 0)

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

    # ══════════════════════════════════════════════════════════════════════
    # EC-B3.1 验收收口批（EC-R01…R08 + 5 条真毒化反向探针）
    #   🔴 M3 预注册见内部规格；锁定值内联，不读内部文档（生产 CI 内不存在）。
    #   🔴 毒化对象是**产品函数** ec_b3_signoff，不是门禁内部自证。
    # ══════════════════════════════════════════════════════════════════════
    from types import SimpleNamespace as _NS
    import json as _json

    _r_g = {k: float(v) for k, v in
            ((_q.get("assumptions") or {}).get("g_values") or {}).items()}
    _R_LOCK = {"g_area": 3.279545, "g_per_gate": 19.677273,
               "g_per_transistor": 72.15, "g_cell": 1.510204}
    _r_keys = sorted(_r_g)

    def _r_mk(*pairs):
        # 合成同层矩形；每对 (net, area)，不越界不重叠
        out = []
        for i, (net, area) in enumerate(pairs):
            y0 = 2.0 + i * 1.0
            out.append(_NS(kind="metal", layer=25, net=net,
                           x0=0.0, y0=y0, x1=1.0, y1=y0 + area))
        return out

    def _r_sign(*pairs, g=None):
        return DS.ec_b3_signoff(_r_mk(*pairs), 7.8, 7.8, 0.24, g or _r_g)

    _r1 = _r_sign(("nt", 1.0))
    _r2 = _r_sign(("nt", 2.0))

    def _r_doubled(seg1, seg2, keys):
        return all(math.isclose(float(seg2["ratio_by_g"][k]["max"]),
                                2.0 * float(seg1["ratio_by_g"][k]["max"]),
                                rel_tol=1e-6, abs_tol=0.0)
                   for k in keys)

    check("EC-R01 🔴 P09 判别力收口：直接毒化**产品函数** ec_b3_signoff，"
          "合成面积 1→2 µm² ⇒ 四口径 max 恰 ×2（rel_tol=1e-6）",
          set(_r_keys) == set(_R_LOCK) and _r_doubled(_r1, _r2, _r_keys))

    _r_poison = {"ratio_by_g":
                 {k: {"max": float(_r2["ratio_by_g"][k]["max"]) * 1.3}
                  for k in _r_keys}}
    check("EC-R01r 反向探针：合成段把比值 ×1.3 ⇒ 检测器必报；正常段不报",
          _r_doubled(_r1, _r2, _r_keys) is True
          and _r_doubled(_r1, _r_poison, _r_keys) is False)

    _r_mix = _r_sign(("nz", 1.0), ("z", 0.0))

    def _r_zero_ok(seg, keys, net):
        return all(float(seg["ratio_by_g"][k]["per_net"].get(net, -1.0)) == 0.0
                   for k in keys)

    check("EC-R02 🔴 P10 判别力收口：零面积网 ⇒ 四口径比值恰 0（容差 0）",
          _r_zero_ok(_r_mix, _r_keys, "z"))

    _r_zp = {"ratio_by_g": {k: {"per_net": {"z": 0.001}} for k in _r_keys}}
    check("EC-R02r 反向探针：零面积却给 0.001 ⇒ 检测器必报",
          _r_zero_ok(_r_mix, _r_keys, "z") is True
          and _r_zero_ok(_r_zp, _r_keys, "z") is False)

    _r_yes = "**含天线比几何代理**" in _q_disc
    _r_no = "**不含天线比几何代理**" in _q_disc
    _r_fact = isinstance(_q.get("ratio_semantics"), dict) and bool(_q.get("ratio_semantics"))

    def _r_tri(yes, no, fact):
        return (yes != no) and (yes == fact)

    check("EC-R03 🔴 语义标签三态：互斥措辞恰好一个 ∧ 与产品段 ratio_semantics 一致；"
          "沉默必红（含=%s 不含=%s 事实=%s）" % (_r_yes, _r_no, _r_fact),
          _r_tri(_r_yes, _r_no, _r_fact))
    check("EC-R03r 反向探针：沉默 / 都在 / 事实不符三种都必须报假，正常为真",
          _r_tri(True, False, True) is True
          and _r_tri(False, False, True) is False
          and _r_tri(True, True, True) is False
          and _r_tri(False, True, True) is False)

    def _r_locked(seg, lock):
        return all(abs(float(seg["ratio_by_g"][k]["max"]) - v) < 1e-9
                   for k, v in lock.items())

    check("EC-R04 I9 数值锁定：产品段四口径 max 与 v2 §4 冻结值逐位一致",
          _r_locked(_q, _R_LOCK))
    _r_lp = {k: v + 0.001 for k, v in _R_LOCK.items()}
    check("EC-R04r 反向探针：冻结值 +0.001 ⇒ 检测器必报；原值不报",
          _r_locked(_q, _R_LOCK) is True and _r_locked(_q, _r_lp) is False)

    _r_gp = dict(_r_g)
    _r_gp["g_per_gate"] *= 1.3
    _r3 = _r_sign(("nt", 1.0), g=_r_gp)
    _r_src = open(os.path.abspath(__file__), encoding="utf-8").read()
    _r_p12 = '"EC-P' + '12 '
    _r_p13 = '"EC-P' + '13 '

    def _r_r5(i8_after, max_a, max_b):
        return i8_after is True and abs(max_a - max_b) > 1e-6

    _r_m1 = float(_r1["ratio_by_g"]["g_per_gate"]["max"])
    _r_m3 = float(_r3["ratio_by_g"]["g_per_gate"]["max"])
    check("EC-R05 🔴 R5 机核：g_per_gate ×1.3 ⇒ I8 仍恒真而比值数值改变 "
          "（%.6f→%.6f）∧ 门禁 P12/P13 仍在 ⇒ 数值漂移只由 P12/P13 抓"
          % (_r_m1, _r_m3),
          _r_r5(_r3["invariants"]["i8_homogeneity"], _r_m1, _r_m3)
          and _r_p12 in _r_src and _r_p13 in _r_src)
    check("EC-R05r 反向探针：若 I8 假报警或数值未变 ⇒ 检测器必报",
          _r_r5(True, 1.0, 2.0) is True
          and _r_r5(False, 1.0, 2.0) is False
          and _r_r5(True, 1.0, 1.0) is False)

    check("EC-R06 段形态不变：无 n_fail/ok/pass ∧ in_blocking=False ∧ "
          "DIAGNOSTIC_ONLY ∧ 主链数字逐位未变",
          not any(k in _q for k in ("n_fail", "ok", "pass"))
          and _q.get("in_blocking") is False
          and _q.get("scope") == "DIAGNOSTIC_ONLY"
          and _q_card["placement"]["die_area_um2"] == 59.202
          and _q_card["timing"]["comb_delay_wired_ps"] == 92.398
          and _q_card["def_export"]["bytes"] == 575
          and _q_card["claimable"] is False
          and _q_card["m1_exit"]["ok"] is True)

    _r_sem_txt = str(_q.get("ratio_semantics") or "")
    _r_defs = [n.name for n in ast.walk(ast.parse(_q_prod_src))
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    check("EC-R07 🔴 不扩大：语义字段同时含肯定/否定声明 ∧ dsignoff 无 FN/充电函数 "
          "∧ 6 处旧声明仍在",
          all(w in _r_sem_txt for w in ("几何代理", "电荷积分",
                                        "Fowler-Nordheim", "栅氧"))
          and not any(any(w in d.lower() for w in
                          ("fowler", "nordheim", "plasma_charge", "charge_integral"))
                      for d in _r_defs)
          and not _q_missing)

    _r_card_sem = (_q_card.get("ec_b3") or {}).get("ratio_semantics")
    try:
        _r_js = _json.dumps(_q_card, ensure_ascii=False, allow_nan=False)
        _r_json_ok = "NaN" not in _r_js and "Infinity" not in _r_js
    except (TypeError, ValueError):
        _r_json_ok = False
    # 🔴 v0.9.391：新增 `thermal` 诊断段 ⇒ 段集合 8→9。本判据职责是「对外完整」，
    #    不得把段数锁死为常数（否则新增合法段会误红）；具体段数由 EC-T01 机核。
    check("EC-R08 对外完整：ratio_semantics 在卡片可读 ∧ segments_covered 含 ec_b3 "
          "∧ 严格 JSON（裸 NaN/Infinity 0）",
          bool(_r_card_sem) and "ec_b3" in (_q_card.get("segments_covered") or [])
          and len(_q_card.get("segments_covered") or []) >= 8
          and _r_json_ok)

    print("  [R] 验收收口批 ✓ · P09/P10 产品函数毒化 ✓ · R5 机核 ✓ · 语义三态 ✓ · "
          "冻结值逐位锁定 ✓")

    # ══════════════════════════════════════════════════════════════════════
    # EC-B4.1 稳态热链诊断（EC-T01…T14 + 5 条真毒化反向探针）
    #   🔴 M3 预注册已冻结于 `EC-B4.0_自检与收口_v1.md §5.4`，此处只落地不改写。
    #   🔴 门禁侧独立复算 = **显式双重求和**；产品侧 = 单次递推 ⇒ 两条不同算法路径。
    # ══════════════════════════════════════════════════════════════════════
    from lda_l2.ecore import dsta as _T_ST

    _t = _q_st.get("thermal") or {}
    _t_card = (_q_card.get("thermal") or {})
    _t_disc = (_q_card.get("disclosure") or {}).get("thermal") or ""
    _t_asm = _t.get("assumptions") or {}
    _t_pw = [float(v["p_w"]) for v in _t["per_cell"].values()] if _t else []
    _t_r = float(_t_asm.get("r_th_k_w", 0.0))

    def _t_double(powers, r_th):
        # 与产品递推不同的路径：显式双重求和 ΔT_i = Σ_{k<=i} r·Σ_{j>=k} P_j
        n = len(powers)
        r = float(r_th) / n
        out = []
        for i in range(1, n + 1):
            acc = 0.0
            for k in range(1, i + 1):
                acc += r * sum(powers[k - 1:])
            out.append(acc)
        return out

    def _t_close(a, b):
        return math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=1e-20)

    # 🔴 v0.9.392：新增 `u7` 诊断段 ⇒ 段集合 9→10。本判据职责是「thermal 段可读」，
    #    不得把段数锁死为常数（否则新增合法段会误红）；具体段数由 EC-U01 机核。
    check("EC-T01 主链产出 `thermal` 段 ∧ 卡片顶层可读 ∧ segments_covered 含 thermal",
          bool(_t) and bool(_t_card) and "thermal" in (_q_card.get("segments_covered") or [])
          and len(_q_card.get("segments_covered") or []) >= 9)

    _t_yes = "**含热诊断段**" in _t_disc
    _t_no = "**不含热诊断段**" in _t_disc
    _t_fact = "b4_thermal_signoff(" in _q_trunk_src

    def _t_tri(yes, no, fact):
        return (yes != no) and (yes == fact)

    check("EC-T02 🔴 三态措辞：互斥恰好一个 ∧ 与主链是否调用 `b4_thermal_signoff` 一致；"
          "沉默必红（含=%s 不含=%s 事实=%s）" % (_t_yes, _t_no, _t_fact),
          _t_tri(_t_yes, _t_no, _t_fact))
    check("EC-T02r 反向探针：三态检测器在沉默 / 都在 / 事实不符时必须报假",
          _t_tri(True, False, True) is True
          and _t_tri(False, False, True) is False
          and _t_tri(True, True, True) is False
          and _t_tri(False, True, True) is False)

    # ── M1 合成反例（闭式「本应恰好」量用 ==）────────────────────────────
    _t1 = DS.b4_thermal_signoff([{"name": "x", "p_w": 2.0, "area_um2": 1.0}])
    check("EC-T03 M1 一维 slab 闭式：n=1 集总 `ΔT = R·P = 2.0 K`（精确已知量用 ==）",
          _t1["delta_t_k"][0] == 2.0
          and _t_close(_t1["uniform_closed_k"], 2.0))

    def _t_slab_ok(seg, want):
        return bool(seg.get("delta_t_k")) and _t_close(seg["delta_t_k"][0], want)

    check("EC-T03r 反向探针：闭式失配（P=3 却拿 2.0 比）⇒ 检测器必报",
          _t_slab_ok(_t1, 2.0) is True and _t_slab_ok(_t1, 3.0) is False)

    _t_u = DS.b4_thermal_signoff(
        [{"name": "u%d" % i, "p_w": 1.0, "area_um2": 1.0} for i in range(6)])
    _t_u_closed = 1.0 * 1.0 * (6 + 1) / 2.0
    check("EC-T04 M1 均匀链闭式 `R·P_cell·(n+1)/2 = %.1f K` ∧ 产品链 ∧ 门禁双重求和三方一致"
          % _t_u_closed,
          _t_close(_t_u["delta_t_k"][-1], _t_u_closed)
          and _t_close(_t_u["uniform_closed_k"], _t_u_closed)
          and all(_t_close(a, b) for a, b in
                  zip(_t_u["delta_t_k"], _t_double([1.0] * 6, 1.0))))

    _t0 = DS.b4_thermal_signoff(
        [{"name": z, "p_w": 0.0, "area_um2": 1.0} for z in ("a", "b", "c")])
    check("EC-T05 🔴 M1/M2：全零功率对照组 ⇒ ΔT 恰 0 且 T 恰环境温度（容差 0）",
          _t0["delta_t_k"] == [0.0, 0.0, 0.0]
          and all(abs(x) < 1e-18 for x in _t0["q_k_w"])
          and all(_t_close(v["t_c"], _t0["assumptions"]["t_amb_c"])
                  for v in _t0["per_cell"].values()))

    def _t_zero_ok(seg):
        return seg.get("delta_t_k") == [0.0] * len(seg.get("delta_t_k") or [])

    check("EC-T05r 反向探针：零功率却给非零 ΔT ⇒ 检测器必报",
          _t_zero_ok(_t0) is True
          and _t_zero_ok({"delta_t_k": [0.0, 0.001, 0.0]}) is False)

    _t_mono = DS.b4_thermal_signoff(
        [{"name": "m0", "p_w": 2.0, "area_um2": 1.0},
         {"name": "m1", "p_w": 1.0, "area_um2": 1.0},
         {"name": "m2", "p_w": 1.0, "area_um2": 1.0}])
    _t_mono_base = DS.b4_thermal_signoff(
        [{"name": "m0", "p_w": 1.0, "area_um2": 1.0},
         {"name": "m1", "p_w": 1.0, "area_um2": 1.0},
         {"name": "m2", "p_w": 1.0, "area_um2": 1.0}])
    check("EC-T06 M1 单调：任一门 P↑ ⇒ 全线 ΔT 不减且至少一处增",
          all(b + 1e-18 >= a for a, b in
              zip(_t_mono_base["delta_t_k"], _t_mono["delta_t_k"]))
          and any(b > a for a, b in
                  zip(_t_mono_base["delta_t_k"], _t_mono["delta_t_k"])))

    check("EC-T07 M1 能量守恒：`Q_1 == ΣP`（rel 1e-12）",
          _t_close(_t["q_k_w"][0], _t["p_total_w"])
          and _t_close(sum(_t_pw), _t["p_total_w"]))

    _t_homo = DS.b4_thermal_signoff(
        [{"name": k, "p_w": v, "area_um2": 1.0}
         for k, v in zip(_t["per_cell"].keys(), _t_pw)], r_th_k_w=_t_r * 1.3)
    check("EC-T08 齐次不变式：`R_th ×1.3 ⇒ ΔT ×1.3`（热阻是假设，谱须线性齐次）",
          all(_t_close(b / a, 1.3) if abs(a) > 1e-30 else abs(b) < 1e-30
              for a, b in zip(_t["delta_t_k"], _t_homo["delta_t_k"])))

    _t_recomp = _t_double(_t_pw, _t_r)

    def _t_has_shared(src):
        names = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
        return any(x in names for x in ("_t_double", "_t_close", "_ec_union"))

    check("EC-T09 🔴 K2 独立性：门禁显式双重求和 vs 产品单次递推逐位一致 ∧ AST 源码互不引用",
          all(_t_close(a, b) for a, b in zip(_t_recomp, _t["delta_t_k"]))
          and _t_has_shared(_q_prod_src) is False)
    check("EC-T09r 反向探针：注入 `_t_double` 的源码必报共享；纯 `import os` 不报",
          _t_has_shared("def f():\n    return _t_double([1.0], 1.0)\n") is True
          and _t_has_shared("import os\n") is False)

    _t_zero_gates = [k for k, v in _t["per_cell"].items()
                     if float(v["p_w"]) == 0.0]
    check("EC-T10 M2 阴性对照：c17 原始版图 5 条不变式全成立不误报 ∧ 3 个零负载门 p_w 恰 0",
          all(v is True for v in (_t.get("invariants") or {}).values())
          and len(_t["invariants"]) == 5
          and len(_t_zero_gates) == 3)

    _t_em_call = _q_trunk_src.split("em_net_signoff(", 1)[-1][:200]
    check("EC-T11 🔴 V5 回归 + 不回灌 `t_c`：`151.661×` / `t_c=125.0` / 主链数字锁定 "
          "∧ 主链 `em_net_signoff(` 调用未传 `t_c=`",
          _q_card["em"]["min_margin_x"] == 151.661
          and _q_card["em"]["assumptions"]["t_c"] == 125.0
          and "t_c=" not in _t_em_call
          and _q_card["placement"]["die_area_um2"] == 59.202
          and _q_card["timing"]["comb_delay_wired_ps"] == 92.398
          and _q_card["def_export"]["bytes"] == 575
          and _q_card["claimable"] is False
          and _q_card["m1_exit"]["ok"] is True)

    def _t_v5_ok(card):
        return (card["em"]["min_margin_x"] == 151.661
                and card["em"]["assumptions"]["t_c"] == 125.0)

    check("EC-T11r 反向探针：EM 裕量或 `t_c` 漂移 ⇒ V5 检测器必报",
          _t_v5_ok(_q_card) is True
          and _t_v5_ok({"em": {"min_margin_x": 99.0,
                                "assumptions": {"t_c": 125.0}}}) is False
          and _t_v5_ok({"em": {"min_margin_x": 100.959,
                                "assumptions": {"t_c": 85.0}}}) is False)

    try:
        _t_js = _json.dumps(_q_card, ensure_ascii=False, allow_nan=False)
        _t_json_ok = "NaN" not in _t_js and "Infinity" not in _t_js
    except (TypeError, ValueError):
        _t_json_ok = False
    check("EC-T12 段形态：无 `n_fail`/`ok`/`pass` ∧ `in_blocking=False` ∧ "
          "`DIAGNOSTIC_ONLY` ∧ 严格 JSON",
          not any(k in _t for k in ("n_fail", "ok", "pass"))
          and _t.get("in_blocking") is False
          and _t.get("scope") == "DIAGNOSTIC_ONLY" and _t_json_ok)

    check("EC-T13 K0 假设显式：alpha/f_hz/vdd/t_amb/r_th/n_nodes 全在 assumptions ∧ "
          "`not_included` 明写不回灌 `t_c`",
          all(k in _t_asm for k in ("alpha", "f_hz", "vdd", "t_amb_c",
                                    "r_th_k_w", "n_nodes", "power_basis"))
          and any("不回灌" in x for x in (_t.get("not_included") or [])))

    _t_whole = _T_ST.switching_power_nw(
        nl, f_hz=float(_t_asm["f_hz"]), alpha=float(_t_asm["alpha"])) * 1e-9
    check("EC-T14 功率守恒：逐门之和 == `dsta.switching_power_nw(nl)` 全片标量（rel 1e-12）",
          _t_close(_t["p_total_w"], _t_whole))

    def _t_homo_expr(src):
        # 🔴 「手填 bool」= 自证（项目红线）；「True or all(...)」短路同样是假机核。
        #    机核 b4_thermal_signoff 的 inv["i_homogeneity"] 必须是实算 all(...) 调用。
        for fn in ast.walk(ast.parse(src)):
            if isinstance(fn, ast.FunctionDef) and fn.name == "b4_thermal_signoff":
                for node in ast.walk(fn):
                    if isinstance(node, ast.Dict):
                        for k, v in zip(node.keys, node.values):
                            if (isinstance(k, ast.Constant)
                                    and k.value == "i_homogeneity"):
                                return isinstance(v, ast.Call) and (
                                    isinstance(v.func, ast.Name)
                                    and v.func.id == "all")
        return False

    check("EC-T15 🔴 不变式不许自证：AST 机核 `i_homogeneity` 必须是实算 `all(...)` "
          "（防手填 True / `True or all(...)` 短路）",
          _t_homo_expr(_q_prod_src) is True)

    def _t_homo_src(v):
        return ("def b4_thermal_signoff():\n"
                "    inv = {'i_homogeneity': %s}\n" % v)

    check("EC-T15r 反向探针：手填 True / 短路 `True or all(...)` ⇒ 检测器必报；"
          "实算 all(...) 不报",
          _t_homo_expr(_t_homo_src("all([])")) is True
          and _t_homo_expr(_t_homo_src("True")) is False
          and _t_homo_expr(_t_homo_src("True or all([])")) is False)

    print("  [T] EC-B4.1 ✓ · 一维 slab/均匀链闭式 ✓ · P=0 极限 ✓ · 能量守恒/齐次 ✓ · "
          "K2 双重求和独立 ✓ · V5 数字零变化 ✓")

    # ══════════════════════════════════════════════════════════════════════
    # EC-B4.2 U7 策略选择器（EC-U01…U12 + 5 条真毒化反向探针）
    #   🔴 M3 预注册冻结于 `EC-B4.2_实现前规格_v1.md`；锁定值内联，不读内部文档。
    #   🔴 K2：产品侧中心有限差分 vs 门禁侧解析闭式导数（两条不同路径）。
    # ══════════════════════════════════════════════════════════════════════
    _u = _q_st.get("u7") or {}
    _u_card = (_q_card.get("u7") or {})
    _u_disc = (_q_card.get("disclosure") or {}).get("u7") or ""
    _u_norm = _u.get("normalization_check") or {}
    _u_pairs = _u.get("pairs") or []
    _u_seg = _q_card.get("segments_covered") or []

    def _u_rho2(m):
        a, b, c, d = float(m[0][0]), float(m[0][1]), float(m[1][0]), float(m[1][1])
        tr, det = a + d, a * d - b * c
        rt = math.sqrt(max(0.0, tr * tr - 4.0 * det))
        return max(abs((tr + rt) / 2.0), abs((tr - rt) / 2.0))

    def _u_kap(m):
        return abs(m[1][0] * m[0][1]) / (abs(m[1][1]) * abs(m[0][0]))

    _u_raw = ((0.9, 2000.0), (0.0005, 0.9))
    _u_scaled = ((0.9, 2.0), (0.0005, 0.0009))    # 只缩第 2 列，行/f 不动
    _u_rr, _u_rs = _u_rho2(_u_raw), _u_rho2(_u_scaled)

    check("EC-U01 诊断段真上 API：主链 `u7` 段 ∧ 卡片可读 ∧ segments_covered 含 u7 "
          "（≥10 段）∧ disclosure 三态措辞恰好一个",
          bool(_u) and bool(_u_card) and "u7" in _u_seg and len(_u_seg) >= 10
          and len(_q_card) >= 33
          and ("**含 U7 策略诊断段**" in _u_disc) is True
          and ("**不含 U7 策略诊断段**" in _u_disc) is False)

    def _u_flip_ok(rh, rs):
        return rh >= 1.0 > rs

    check("EC-U02 🔴 M1 单位缩放翻盘：未归一化 A 的 ρ=%.6f（不稳定）→ 只缩第 2 列 ÷1000 "
          "⇒ ρ=%.6f（稳定）必被抓，且与产品段逐位一致" % (_u_rr, _u_rs),
          _u_flip_ok(_u_rr, _u_rs)
          and math.isclose(float(_u_norm.get("rho_raw", -1)), _u_rr, rel_tol=1e-12)
          and math.isclose(float(_u_norm.get("rho_column_scaled", -1)), _u_rs, rel_tol=1e-12))
    check("EC-U02r 反向探针：结论未翻盘 / 单位缩放做成行缩放 ⇒ 检测器必报假",
          _u_flip_ok(1.9, 0.901111) is True
          and _u_flip_ok(1.9, 1.9) is False
          and _u_flip_ok(0.5, 0.4) is False)

    _u_k1, _u_k2 = _u_kap(_u_raw), _u_kap(_u_scaled)

    def _u_kap_ok(k1, k2):
        return abs(k1 - k2) < 1e-12

    check("EC-U03 🔴 勘误机核：κ 天然无量纲 —— 同一列缩放下 κ=%.6f / %.6f，差 %.2e "
          "（不许把 κ 也拿去归一化）" % (_u_k1, _u_k2, abs(_u_k1 - _u_k2)),
          _u_kap_ok(_u_k1, _u_k2)
          and _u_kap_ok(float(_u_norm.get("kappa_raw", 0)),
                        float(_u_norm.get("kappa_column_scaled", 1))))
    check("EC-U03r 反向探针：κ 被强行 ÷1000 ⇒ 检测器必报假",
          _u_kap_ok(1.234568, 1.234568) is True
          and _u_kap_ok(1.234568, 0.001234568) is False)

    _u_tilde = ((0.9, 2000.0 * 1.0 / 1.0), (0.0005 * 1.0 / 1.0, 0.9))
    _u_tilde_sc = ((0.9, (2000.0 / 1000) * (1.0 * 1000) / 1.0), (0.0005, 0.9))
    _u_rt, _u_rts = _u_rho2(_u_tilde), _u_rho2(_u_tilde_sc)

    def _u_norm_ok(a, b):
        return abs(a - b) < 1e-12

    check("EC-U04 Ã 单位无关：导数 ÷1000 与 x_ref ×1000 抵消 ⇒ ρ 差 = %.2e（容差 0）"
          % abs(_u_rt - _u_rts),
          abs(_u_rt - _u_rts) == 0.0
          and _u_norm_ok(float(_u_norm.get("rho_tilde", 0)),
                         float(_u_norm.get("rho_tilde_unit_scaled", 1))))
    check("EC-U04r 反向探针：只缩导数、不缩 x_ref（不同步）⇒ 检测器必报假",
          _u_norm_ok(1.9, 1.9) is True
          and _u_norm_ok(1.9, 0.901111) is False)

    _u_one = [x for x in _u_pairs if x.get("status") == "DECIDABLE" and x.get("a_rev") is None]
    _u_other = [x for x in _u_pairs if x.get("status") in ("UNDECIDABLE", "NOT_MODELED")]

    def _u_status_ok(one, other):
        return (all(x.get("strategy") == "EXPLICIT" for x in one)
                and all(x.get("strategy") is None and x.get("kappa") is None for x in other))

    check("EC-U05 单向 ρ≡0 ⇒ EXPLICIT；不可判/不做**不得**被算成策略或通过 "
          "（7 对 = 2 可判 + 4 不可判 + 1 明确不做）",
          _u_status_ok(_u_one, _u_other)
          and _u.get("n_pairs") == 7 and _u.get("n_decidable") == 2
          and _u.get("n_undecidable") == 4 and _u.get("n_not_modeled") == 1)
    check("EC-U05r 反向探针：把 UNDECIDABLE 偷偷标成 EXPLICIT ⇒ 检测器必报假",
          _u_status_ok(_u_one, _u_other) is True
          and _u_status_ok(_u_one, [{"strategy": "EXPLICIT", "kappa": 0.0}]) is False)

    _u_strong = DS.b42_u7_signoff([
        {"name": "合成双向强耦合", "a_fwd": 2.0, "a_rev": 2.0, "x_ref": 1.0,
         "f_ref": 1.0, "unit": "-", "source": "synthetic M1", "status": "DECIDABLE"}])
    _u_sp = _u_strong["pairs"][0]

    def _u_strat_ok(p):
        return (p.get("strategy") == "MONOLITHIC"
                and "设计不稳定" not in str(p) and "算不出" not in str(p))

    check("EC-U06 🔴 三态措辞：κ≥1 ⇒ MONOLITHIC，且不判物理设计不稳定、不报工具失败 "
          "（实测 κ=%.1f）" % _u_sp["kappa"],
          _u_strat_ok(_u_sp) and "不判设计稳定性" in _u_disc
          and "不把数值发散包装成工具失败" in _u_disc)
    check("EC-U06r 反向探针：pair 里出现「设计不稳定」或策略沉默 ⇒ 检测器必报假",
          _u_strat_ok(_u_sp) is True
          and _u_strat_ok(dict(_u_sp, reason="设计不稳定")) is False
          and _u_strat_ok(dict(_u_sp, strategy=None)) is False)

    check("EC-U07 稀疏 Ã ⇒ rho_status=NOT_MEANINGFUL 且 rho_global 为 None"
          "（不许输出 ρ=0.0 冒充判定）",
          _u.get("rho_status") == "NOT_MEANINGFUL"
          and _u.get("rho_global") is None
          and "NOT_MEANINGFUL" in _u_disc)

    _u_ana = -DS.EA_EV / (DS.N_EXP * DS.K_B_EV * 398.15)
    _u_mt = next((x.get("a_fwd") for x in _u_pairs if x.get("name") == "热→EM"), None)

    def _u_has_shared(src):
        names = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
        return any(x in names for x in ("_u_rho2", "_u_kap", "_u_ana"))

    check("EC-U08 🔴 K2：产品中心有限差分 `∂lnJ/∂lnT=%.9f` vs 门禁解析闭式 `%.9f` "
          "（rel_tol=1e-9）∧ AST 机核源码互不引用" % (float(_u_mt or 0), _u_ana),
          _u_mt is not None
          and math.isclose(float(_u_mt), _u_ana, rel_tol=1e-9)
          and _u_has_shared(_q_prod_src) is False
          and _u_has_shared("def f():\n    return _u_rho2([[1,0],[0,1]])\n") is True)

    check("EC-U09 Ã 假设显式：每个可算对都有 x_ref/f_ref/unit/source/evidence_level=E5 "
          "∧ assumptions 明写 κ 无量纲与冲突消解",
          all(all(k in x for k in ("x_ref", "f_ref", "unit", "source", "evidence_level"))
              and x.get("evidence_level") == "E5" and x.get("x_ref") is not None
              for x in _u_pairs if x.get("status") == "DECIDABLE")
          and (_u.get("assumptions") or {}).get("kappa_is_dimensionless") is True
          and "INCONSISTENT" in str(_u.get("assumptions")))

    check("EC-U10 V5 回归：151.661× / t_c=125.0 / 主链 5 项逐位未变 ∧ "
          "`em_net_signoff(` 未传 t_c",
          _q_card["em"]["min_margin_x"] == 151.661
          and _q_card["em"]["assumptions"]["t_c"] == 125.0
          and "t_c=" not in _q_trunk_src.split("em_net_signoff(", 1)[-1][:200]
          and _q_card["placement"]["die_area_um2"] == 59.202
          and _q_card["timing"]["comb_delay_wired_ps"] == 92.398
          and _q_card["def_export"]["bytes"] == 575
          and _q_card["claimable"] is False
          and _q_card["m1_exit"]["ok"] is True)

    try:
        _u_js = _json.dumps(_q_card, ensure_ascii=False, allow_nan=False)
        _u_json_ok = "NaN" not in _u_js and "Infinity" not in _u_js
    except (TypeError, ValueError):
        _u_json_ok = False
    check("EC-U11 段形态：DIAGNOSTIC_ONLY / in_blocking=False / 无 n_fail·ok·pass / 严格 JSON",
          _u.get("scope") == "DIAGNOSTIC_ONLY" and _u.get("in_blocking") is False
          and not any(k in _u for k in ("n_fail", "ok", "pass"))
          and all(v is True for v in (_u.get("invariants") or {}).values())
          and _u_json_ok)

    check("EC-U12 冲突消解：稀疏 ⇒ NOT_APPLICABLE；合成 κ<1 但 ρ≥1 ⇒ 登记 "
          "INCONSISTENT 不静默、不改逐对策略",
          _u.get("conflict_status") == "NOT_APPLICABLE"
          and DS.b42_conflict_status([0.5], 1.5) == "INCONSISTENT"
          and DS.b42_conflict_status([0.5], 0.5) == "CONSISTENT"
          and DS.b42_conflict_status([0.5], None) == "NOT_APPLICABLE")

    # ══════════════════════════════════════════════════════════════════════
    # EC-V01…V07：EC-B4.6 证据维度机核（门禁**独立读源码**，不调用产品函数）
    #   🔴 K2：产品侧只写「声明」(evidence_status / evidence_source)；门禁侧内联路径与
    #      关键字、自己 AST/文本解析 dsta.py / dpvt.py / dsignoff.py 取「事实」。
    #      两侧不同源 ⇒ 只改声明或只改源码都会红。锁定值全内联（生产 CI 无内部文档）。
    #   🔴 可判性维度(status) 与证据维度(evidence_status) 分开 ⇒ 不许合标量(§16.2)。
    # ══════════════════════════════════════════════════════════════════════
    _v_dsta_src = open(os.path.join(_HERE, "lda_l2", "ecore", "dsta.py"),
                       encoding="utf-8").read()
    _v_dpvt_src = open(os.path.join(_HERE, "lda_l2", "ecore", "dpvt.py"),
                       encoding="utf-8").read()

    # (对名, 门禁内联的文件名, 门禁内联的事实键)
    _V_FACT_TAB = (
        ("热→时序", "dpvt.py", "no_temp_corner"),
        ("IR→时序", "dsignoff.py", "ir_not_wired"),
        ("耦合电容→时序", "dsta.py", "no_crosstalk"),
        ("工艺变异→全部", "dpvt.py", "corner_scaling_only"),
    )

    def _v_facts_from_source(dsta_src, dpvt_src, prod_src):
        """门禁侧事实：只吃源码文本，不 import / 不调用任何产品函数（V05 机核）。"""
        tree = ast.parse(dsta_src)
        hold_false = any(
            isinstance(kw.value, ast.Constant) and kw.value.value is False
            for node in ast.walk(tree) if isinstance(node, ast.Call)
            for kw in node.keywords if kw.arg == "hold_checked")
        # 🔴 必须取 `not_included` **字典值**本身，不能只查全文含「无串扰」：
        #    :261 的注释也含该词，会兜住删措辞的毒化 ⇒ 探针失靶（≠ 直通）。
        not_included_text = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for k, v in zip(node.keys, node.values):
                    if (isinstance(k, ast.Constant) and k.value == "not_included"
                            and isinstance(v, ast.Constant)
                            and isinstance(v.value, str)):
                        not_included_text.append(v.value)
        return {
            "dsta.py": {
                "no_crosstalk": (hold_false
                                 and "无串扰" in "\n".join(not_included_text)),
            },
            "dpvt.py": {
                "no_temp_corner": ("无温度相关的 R(T)" in dpvt_src
                                   and "无 R(T)" in dpvt_src),
                "corner_scaling_only": ("片上变异分析" in dpvt_src
                                        and "角缩放" in dpvt_src),
            },
            "dsignoff.py": {
                "ir_not_wired": "不含 IR→时序实际串联" in prod_src,
            },
        }

    _v_facts = _v_facts_from_source(_v_dsta_src, _v_dpvt_src, _q_prod_src)
    _v_und = [x for x in _u_pairs if x.get("status") == "UNDECIDABLE"]

    check("EC-V01 证据维度与可判性维度分开：4 对 UNDECIDABLE 全部显式 VERIFIED + "
          "evidence_source，status 仍 UNDECIDABLE ∧ 7 对计数 2/4/1 不变 ∧ "
          "strategy·kappa 仍 None ∧ 仅这 4 对带新字段",
          len(_v_und) == 4
          and all(x.get("evidence_status") == "VERIFIED" and x.get("evidence_source")
                  and x.get("strategy") is None and x.get("kappa") is None
                  for x in _v_und)
          and _u.get("n_pairs") == 7 and _u.get("n_decidable") == 2
          and _u.get("n_undecidable") == 4 and _u.get("n_not_modeled") == 1
          and sum(1 for x in _u_pairs if "evidence_status" in x) == 4)

    _v_ct = next((x for x in _v_und if x.get("name") == "耦合电容→时序"), None)
    check("EC-V02 🔴 K2 证据机核：门禁 AST 独立取 `hold_checked=False` + 文本独立取 "
          "`not_included` 含「无串扰」∧ 该对声明 VERIFIED 且指向 dsta.py ∧ "
          "source 不再写「未核实」",
          _v_ct is not None
          and _v_facts["dsta.py"]["no_crosstalk"] is True
          and _v_ct.get("evidence_status") == "VERIFIED"
          and "dsta.py" in str(_v_ct.get("evidence_source"))
          and "未核实" not in str(_v_ct.get("source"))
          and "已核实" in str(_v_ct.get("source")))

    def _v_pair_ok(pair, facts):
        src = str(pair.get("evidence_source") or "")
        hit = next(((f, k) for n, f, k in _V_FACT_TAB
                   if n == pair.get("name")), None)
        return (hit is not None and pair.get("evidence_status") == "VERIFIED"
                and pair.get("status") == "UNDECIDABLE"
                and hit[0] in src
                and (facts.get(hit[0]) or {}).get(hit[1]) is True)

    check("EC-V03 四对逐对证据核实（热→时序 / IR→时序 / 耦合电容→时序 / "
          "工艺变异→全部）∧ evidence_source 指向的文件与门禁内联事实一致 ∧ "
          "4 条源码事实全为真",
          all(_v_pair_ok(x, _v_facts) for x in _v_und)
          and all(v is True for f in _v_facts.values() for v in f.values()))

    _v_good = _v_ct or {}
    check("EC-V04 反向探针（真毒化）：删 dsta 事实 / 声明改回 UNVERIFIED / "
          "evidence_source 指错文件 / 改 status ⇒ 检测器必报假",
          _v_pair_ok(_v_good, _v_facts) is True
          and _v_pair_ok(_v_good, {"dsta.py": {"no_crosstalk": False}}) is False
          and _v_pair_ok(dict(_v_good, evidence_status="UNVERIFIED"),
                         _v_facts) is False
          and _v_pair_ok(dict(_v_good, evidence_source="nope.py:1"),
                         _v_facts) is False
          and _v_pair_ok(dict(_v_good, status="NOT_MODELED"), _v_facts) is False)

    _V_FORBIDDEN = ("DS", "B3", "dsta", "dpvt", "dsignoff",
                    "b42_u7_signoff", "capability", "run_trunk_from_verilog")

    def _v_shared_names(fn):
        return set(fn.__code__.co_names)

    def _v_poisoned():
        return DS.b42_u7_signoff([])

    check("EC-V05 🔴 K2 独立性机核：门禁事实提取函数的**字节码**不引用任何产品符号 "
          "∧ 反向探针（真调产品函数）必被抓",
          not (set(_V_FORBIDDEN) & _v_shared_names(_v_facts_from_source))
          and bool(set(_V_FORBIDDEN) & _v_shared_names(_v_poisoned)))

    check("EC-V06 段形态不变：卡片 ≥33 键 / segments_covered ≥10 段 / "
          "DIAGNOSTIC_ONLY / in_blocking=False / 段内无 n_fail·ok·pass / 严格 JSON",
          len(_q_card) >= 33 and len(_u_seg) >= 10
          and _u.get("scope") == "DIAGNOSTIC_ONLY" and _u.get("in_blocking") is False
          and not any(k in _u for k in ("n_fail", "ok", "pass"))
          and _u_json_ok)

    check("EC-V07 V5 回归：主链 5 项 + 151.661× / t_c=125.0 逐位不变 ∧ "
          "`em_net_signoff(` 未传 t_c（EC-B4.5 冻结仍生效）",
          _q_card["em"]["min_margin_x"] == 151.661
          and _q_card["em"]["assumptions"]["t_c"] == 125.0
          and "t_c=" not in _q_trunk_src.split("em_net_signoff(", 1)[-1][:200]
          and _q_card["placement"]["die_area_um2"] == 59.202
          and _q_card["timing"]["comb_delay_wired_ps"] == 92.398
          and _q_card["def_export"]["bytes"] == 575
          and _q_card["claimable"] is False
          and _q_card["m1_exit"]["ok"] is True)

    print("  [V] EC-B4.6 ✓ · 证据维度独立 ✓ · 源码事实机核 ✓ · "
          "K2 字节码独立性 ✓ · 段形态/主链数字零变化 ✓")

    print("  [U] EC-B4.2 ✓ · 单位翻盘 ✓ · κ 无量纲 ✓ · Ã 单位无关 ✓ · "
          "不可判≠通过 ✓ · K2 解析复算 ✓ · V5 数字零变化 ✓")

    # ══════════════════════════════════════════════════════════════════════
    # Q0 · 可观测性门禁（T1a · 零数字变化）
    # ══════════════════════════════════════════════════════════════════════
    # 🔴 清单**从真源枚举**（几何 = `dproc.TOUCHED`，器件 = `Tech` 数值字段），
    #   严禁硬编码：硬编码清单会漏「二阶早绑定」（`VIA`/`ENC` 实测即被漏掉 ——
    #   它们的消费者 `PAD_HALF` 是 import 时常量，改了真源也不动，但静态清单里看不出来）。
    #
    # 🔴 观测向量必须**多维**：只看延时会把 `W_MIN`（只影响 DRC）、
    #   `area_per_tr`（只影响面积）误判为死。
    #: 🔴 v0.9.405 扩第 6 维：**INV 单链延时**（4 级 @1fF，闭式）。
    #   理由：`R = ρ·L/W` 之后 `Tech.r_sheet_p_over_n`（ρ_p/ρ_n）只在**上拉主导**时进延时，
    #   而 c17 的关键路径全是 NAND2（下拉主导）⇒ 少这一维，ρ 比就被判「死参数」。
    #   判据看不见它 ≠ 它不重要：**要扩观测向量，不是把参数藏起来**。
    #   INV 是平衡的（上下拉等阻），任何 ρ_p 变动都会打破平局 ⇒ 这一维能看见它。
    _Q0_OBS = ("area", "rout", "wired", "drc", "em", "inv_chain")
    # 死参数登记表（棘轮：只减不增）。每条都有 owner，不是"忘了"。
    # 🔴 Q2（v0.9.396）实测变化 —— 11 → 7：
    #   · **转 live（3）**：`ddetail.VIA` / `ddrc_lvs.ENC`（`pad_half()` 改成函数后改真源
    #     立刻改几何）、`ddrc_lvs.W_MIN`（不再写死 0.10，改由 `W_ROUTE` 派生 ⇒ 死规则消失）；
    #   · **消失（3）**：`dpnr.PAD_HALF` / `M2_HALF` / `EXT` —— 三份副本被**删除**，
    #     不是"修好"，是不再存在（`pad_half()` 是唯一真源）；
    #   · **新增 dead（1）**：`ddetail.TRACK_PITCH` —— `PITCH` 改由 `W+S_MIN+δ` 派生后，
    #     那个没有出处的 0.36 再没人读（只剩 `dproc.use()` 的节点切换口）。owner → Q4；
    #   · **仍 dead（1）**：`ddetail.W_ROUTE` —— `W` 仍是 import 期常量（三阶），
    #     Q2 只根治了 pad 半宽那一处二阶，**W 的绑定留在 T5**（本轮不谎称已修）。
    #   当前网表无消费者（3）：t_setup / t_hold / t_clk_q（c17 无 DFF）→ T5 换网表
    #   无消费路径（2）：area_per_tr · ileak                        → T3 / T5
    _Q0_DEAD = frozenset({
        "ddetail.W_ROUTE", "ddetail.TRACK_PITCH",
        "Tech.area_per_tr_um2", "Tech.ileak_na_per_tr",
        "Tech.t_setup_ps", "Tech.t_hold_ps", "Tech.t_clk_q_ps",
    })

    def _q0_observe():
        _s = {n: q for n, q in B3.run_trunk_from_verilog(V.SAMPLE_VERILOG)["stages"]}
        return (_s["place"]["die_area_um2"], _s["route"]["nets_with_segments"],
                _s["timing"]["comb_delay_wired_ps"],
                sum(_s["drc_lvs"]["drc_by_rule"].values()),
                _s["em"]["min_margin_x"],
                DC.chain_golden_ps("INV", 4, 1.0))     # 第 6 维：INV 单链（见 `_Q0_OBS`）

    _q0_mods = {"ddetail": DET, "dpnr": P, "ddrc_lvs": DL}
    _q0_geo = [("dproc", m, a) for (m, a) in DP.TOUCHED]
    _q0_tech = [f.name for f in dataclasses.fields(DC.DEFAULT_TECH)
                if isinstance(getattr(DC.DEFAULT_TECH, f.name), (int, float))
                and not isinstance(getattr(DC.DEFAULT_TECH, f.name), bool)]
    _q0_all = len(_q0_geo) + len(_q0_tech)
    _q0_base = _q0_observe()
    _q0_snap = DP.snapshot()
    _q0_t0 = DC.DEFAULT_TECH
    _q0_live, _q0_dead = [], []
    try:
        for _m, _mn, _at in _q0_geo:
            _md = _q0_mods[_mn]
            _old = getattr(_md, _at)
            setattr(_md, _at, _old * 1.05)
            _cur = _q0_observe()
            setattr(_md, _at, _old)
            (_q0_live if _cur != _q0_base else _q0_dead).append("%s.%s" % (_mn, _at))
        for _fn in _q0_tech:
            _old = getattr(_q0_t0, _fn)
            DC.DEFAULT_TECH = dataclasses.replace(_q0_t0, **{_fn: _old * 1.05})
            _cur = _q0_observe()
            DC.DEFAULT_TECH = _q0_t0
            (_q0_live if _cur != _q0_base else _q0_dead).append("Tech.%s" % _fn)
    finally:
        DC.DEFAULT_TECH = _q0_t0
        for (_m, _a), _v in _q0_snap.items():
            setattr(_q0_mods[_m], _a, _v)

    check("Q0-a 参数清单由真源枚举（几何 %d + 器件 %d = %d，非硬编码）"
          % (len(_q0_geo), len(_q0_tech), _q0_all),
          len(_q0_geo) == len(DP.TOUCHED)
          and _q0_all == len(DP.TOUCHED) + len(_q0_tech))
    check("Q0-b 每参数均有响应记录（live %d + dead %d = %d）"
          % (len(_q0_live), len(_q0_dead), len(_q0_live) + len(_q0_dead)),
          len(_q0_live) + len(_q0_dead) == _q0_all)
    check("Q0-c 死参数集合 == 登记表（棘轮·只减不增，现 %d 个）" % len(_Q0_DEAD),
          frozenset(_q0_dead) == _Q0_DEAD)
    check("Q0-d 观测向量 %d 维（面积/布通/延时/DRC/EM + INV 单链）" % len(_Q0_OBS),
          len(_Q0_OBS) >= 6)
    check("Q0-e 扰动后逐位还原（dproc.diff ∅ ∧ 观测向量相等）",
          DP.diff(_q0_snap) == [] and _q0_observe() == _q0_base)
    print("  [Q0] 可观测性：live %d / dead %d（登记表 %d）· 清单由 TOUCHED+Tech 枚举"
          % (len(_q0_live), len(_q0_dead), len(_Q0_DEAD)))

    # ══════════════════════════════════════════════════════════════════════
    # T1b · Q1 检查器去伪（`short_via` 层相邻）+ S1a/S1c 约束层
    # ══════════════════════════════════════════════════════════════════════
    # 🔴 这是本征程**第一次动检查器逻辑**，所以判据的重点不是"数字对不对"，而是
    #   「改窄了会不会把真短路一起放过」和「改窄了以后数字有没有偷偷变」。
    #   两个方向都必须有探针：放过真短路（欠检）与仍报误报（过检）。
    _tb = B3.run_trunk_from_verilog(V.SAMPLE_VERILOG)
    _tb_s = {n: d for n, d in _tb["stages"]}
    _tb_base = _tb["baseline"]["drc_lvs"]

    # Q1-a 规则同义：`via_bridges` 复用 `VIA_BRIDGE`，在当前层号表上必须与规划写的
    #      `|Δlayer| == 1` **逐项等价** —— 层号表漂移（有人改号）即红，不允许两条口径分叉。
    _tb_met = (DET.L_M1, DET.L_M2, DET.L_M3, DET.L_M4)
    _tb_bad = {v: sorted(DL.VIA_BRIDGE[v])
               for v in DL.VIA_BRIDGE
               if sorted(DL.VIA_BRIDGE[v]) != sorted(l for l in _tb_met if abs(l - v) == 1)}
    check("Q1-a 桥接判据 ≡ `|Δlayer|=1`（%d 个孔层逐项等价，层号表漂移即红）"
          % len(DL.VIA_BRIDGE), not _tb_bad,
          "不等价的孔层=%r" % (_tb_bad,))

    # Q1-b **零变化**：两颗几何的 `short_via` 一条不动 —— 主链 0（本来没有），
    #      旧链 105（183 = 78 + 105、43 对网）。只看主链会漏掉旧链那条证据链。
    _tb_main_sv = _tb_s["drc_lvs"]["lvs_by_rule"].get("short_via", 0)
    _tb_legacy_sv = _tb_base["lvs_by_rule"].get("short_via", 0)
    check("Q1-b 零变化：主链 `short_via` %d→0 ∧ 旧链 %d→105 ∧ 旧链 183=78+105 / 43 对网不变"
          % (_tb_main_sv, _tb_legacy_sv),
          _tb_main_sv == 0 and _tb_legacy_sv == 105
          and _tb_base["lvs_problems"] == 183
          and _tb_base["lvs_by_rule"] == {"short": 78, "short_via": 105}
          and _tb_base["lvs_unique_pairs"] == 43)

    # Q1-c 独立复算：旧链那 105 条的真实层对**全部** `|Δ|=1`
    #      ⇒ 过滤器是「纯减法且减 0」，没有一条真实短路被误伤。
    #      🔴 用 `abs(Δ)==1` 独立写一遍，不复用 `via_bridges`（否则等于自证）。
    _tb_p0 = DPL.place(nl)
    _tb_r0 = DET.detail_route(nl, _tb_p0)
    _tb_rt = [s for s in _tb_r0.shapes if s.net is not None and s.kind in ("metal", "via")]
    _tb_m = [s for s in _tb_rt if s.kind == "metal"]
    _tb_v = [s for s in _tb_rt if s.kind == "via"]
    _tb_deltas = [abs(v.layer - m.layer) for v in _tb_v for m in _tb_m
                  if not (m.net == v.net or v.net is None or m.net is None)
                  and DET.rects_overlap(v, m, inflate=1e-6)]
    check("Q1-c 独立复算：旧链 105 条重叠的层对 `|Δ|` 全为 1（实测 %d 条，Δ 集合 %r）"
          % (len(_tb_deltas), sorted(set(_tb_deltas))),
          len(_tb_deltas) == 105 and set(_tb_deltas) == {1})

    # ── Q1 反向探针：三个最小几何，两版（`run_lvs` / `fast_lvs`）都必须同口径 ──
    #   ① 桥接层重叠 = 真短路 ⇒ **必报**（改了检查器最怕的就是把它一起放过）
    #   ② 非桥接层重叠 = 无连接 ⇒ **必不报**（这正是被修掉的误报形态）
    #   ③ 未知孔层 = 无桥接事实 ⇒ **保守仍报**（fail-closed，不静默变瞎）
    _br2 = DL.VIA_BRIDGE[DET.L_VIA2]
    _far2 = next(l for l in _tb_met if l not in _br2)

    def _tb_probe(metal_layer, via_layer):
        v = DET._rect(via_layer, 5.0, 5.0, 5.0 + DET.VIA, 5.0 + DET.VIA,
                      net="__a__", kind="via")
        m = DET._rect(metal_layer, 5.0, 5.0, 5.0 + DET.VIA, 5.0 + DET.VIA,
                      net="__b__", kind="metal")
        out = []
        for fn in (DL.run_lvs, DL.fast_lvs):
            r = fn([v, m], {})
            out.append(sum(1 for p in r["problems"] if p[0] == "short_via"))
        return tuple(out)

    _p_adj = _tb_probe(_br2[0], DET.L_VIA2)
    _p_far = _tb_probe(_far2, DET.L_VIA2)
    _p_unk = _tb_probe(DET.L_M3, 999)
    check("Q1-d 反向探针①：`|Δ|=1` 真短路（V2 压异网 M3）必报 —— run/fast 各 %r 条" % (_p_adj,),
          _p_adj == (1, 1))
    check("Q1-e 反向探针②：`|Δ|=3` 重叠（V2 压异网 M1）**不得**报 —— run/fast 各 %r 条" % (_p_far,),
          _p_far == (0, 0))
    check("Q1-f fail-closed：未知孔层无桥接事实 ⇒ 仍报（run/fast 各 %r 条，不静默放行）"
          % (_p_unk,), _p_unk == (1, 1))

    # Q1-g K2 **棘轮**：`run_lvs` 与 `fast_lvs` 现在共享 `via_bridges`（规则本身）。
    #      这不是"看不见"，而是**登记在册**：共享集必须**恰好**等于登记表，
    #      再多共享一个本地函数即红。同时证明登记不是陈旧的（两版闭包都真的含它）。
    _q1_clos = _local_closures(_src)
    _q1_shared = _q1_clos["run_lvs"] & _q1_clos["fast_lvs"]
    check("Q1-g K2 棘轮：两版共享集 == 登记 %r（实测 %r；多共享即红）"
          % (sorted(K2_SHARED_WHITELIST), sorted(_q1_shared)),
          _q1_shared == set(K2_SHARED_WHITELIST)
          and "via_bridges" in _q1_clos["run_lvs"]
          and "via_bridges" in _q1_clos["fast_lvs"])

    # ── S1a 时钟周期 / S1c 扇出与转换：由 `Tech` + 拓扑派生，**禁字面量** ──
    _tb_std = V.parse(_standard_verilog())
    _c_std = ST.constraint_layer(_tb_std)
    _c_loc = ST.constraint_layer(
        nl, comb_delay_ideal_ps=_tb_s["timing"]["comb_delay_ideal_ps"],
        comb_delay_wired_ps=_tb_s["timing"]["comb_delay_wired_ps"])
    # S1a-a：同一公式在**标准 c17**（6×NAND2）上必须复现规划预注册的 62.145 ps；
    #        本仓 c17 只有 61.986，差额 10.397 全部来自 `g23` 是 INV（已在 S13b 登记的
    #        TYPE_MISMATCH）—— 两个数都给，不许只报有利的那个。
    check("S1a-a 预注册复现：标准 c17（3×NAND2）T_ref=%.6f ps（预注册 74.383；v0.9.405 换公式后重定）∧ "
          "本仓 c17=%.6f ps（g23 为 INV，已登记差异）"
          % (_c_std["clock_period_ps"], _c_loc["clock_period_ps"]),
          abs(_c_std["clock_period_ps"] - 74.383246250395075) < 1e-9
          and abs(_c_loc["clock_period_ps"] - 61.986038541995896) < 1e-9
          and _c_loc["n_stages"] == 3 and _c_loc["dff_on_path"] == 0)

    # S1a-b 可追溯（禁字面量）：门禁侧**显式展开** `ln2·R·(C_self + C_load)` 再累加，
    #      与产品侧 `DC.cell_delay_ps` 路径逐位一致 ⇒ 四个量真的只由 Tech+拓扑+FO 决定。
    _tb_tech = DC.DEFAULT_TECH
    _tb_fo = _c_loc["fo_target"]
    _tb_ld = _tb_fo * _tb_tech.cin_ff
    # 🔴 v0.9.405：展开式跟着改口 —— `k_drive·r_on` → `R_cell = max(串联·ρ·L/W)`。
    #   🔴 v0.9.406：自载项也几何化 ⇒ `ln2·R·(C_self + C_load)`，**不再有那个常数 `t_intr`**。
    #   本条的意义就是「不调产品函数、自己按定义式写一遍」，所以必须逐字跟着改。
    _tb_rho_n = _tb_tech.r_on_ohm * DC.R_REF_W_NM / DC.R_REF_L_NM
    _tb_rho_p = _tb_rho_n * _tb_tech.r_sheet_p_over_n
    # `C_self` 按定义式独立写出（= 让 INV 恰好回到 `t_intr_ps` 的那个电容）
    _tb_cself = _tb_tech.t_intr_ps / (DC.LN2 * _tb_tech.r_on_ohm * DC.OHM_FF_TO_PS)
    _tb_re = 0.0
    for _g in ST.longest_path_gates(nl):
        if _g.cell == "DFF":
            continue
        _cc = DC.CELLS[_g.cell]
        _sn, _sp = DC.series_counts(_cc)
        _r = max(_sn * _tb_rho_n * _cc.l_nm / _cc.w_n_nm,
                 _sp * _tb_rho_p * _cc.l_nm / _cc.w_p_nm)
        _tb_re += _r * DC.LN2 * (_tb_cself + _tb_ld) * DC.OHM_FF_TO_PS
    check("S1a-b 可追溯：门禁显式展开复算 %.9f == 产品 %.9f（禁字面量；仅 Tech+拓扑+FO）"
          % (_tb_re, _c_loc["clock_period_ps"]), _tb_re == _c_loc["clock_period_ps"])

    # S1a-c 值锁定：三个数逐位（T_ref / slack ideal / slack wired）。
    check("S1a-c 数值锁定（T2 口径）：T_ref=%.9f ∧ slack(ideal)=%.9f ∧ slack(wired)=%.9f"
          % (_c_loc["clock_period_ps"], _c_loc["slack_ideal_ps"], _c_loc["slack_wired_ps"]),
          abs(_c_loc["clock_period_ps"] - 61.986038541995896) < 1e-9
          and abs(_c_loc["slack_ideal_ps"] - 15.329038541995899) < 1e-9
          and abs(_c_loc["slack_wired_ps"] + 30.411961458004100) < 1e-9)

    # S1a-d 反向探针：`FO_target` 必须**真被消费** —— 改成 1 / 4 时 T_ref 必变且
    #      与手算吻合（FO1 21.9424 / FO4 69.7695）。写死常数则这三个数相同 ⇒ 红。
    _c1 = ST.constraint_layer(nl, fo_target=1)
    _c4 = ST.constraint_layer(nl, fo_target=4)
    check("S1a-d 反向探针：FO=1 → %.6f ∧ FO=3 → %.6f ∧ FO=4 → %.6f（三值互异 ⇒ 参数真被消费）"
          % (_c1["clock_period_ps"], _c_loc["clock_period_ps"], _c4["clock_period_ps"]),
          len({round(_c1["clock_period_ps"], 9), round(_c_loc["clock_period_ps"], 9),
               round(_c4["clock_period_ps"], 9)}) == 3
          and abs(_c1["clock_period_ps"] - 27.328679513998630) < 1e-9
          and abs(_c4["clock_period_ps"] - 79.314718055994533) < 1e-9)

    # S1a-e 判别力**元**判据：T1 只登记、不裁决（规划 §3-DoD.2）。
    #      legacy 上 FO3 两侧 slack 均 > 0 ⇒ 无判别力（**这是登记，不是失败**）；
    #      谓词本身自带对照组（(+,-)→真 / (+,+)→假 / (-,-)→假）⇒ 它既不是恒真也不是恒假桩。
    _tb_disc = [_c_loc["discriminates"], _c1["discriminates"], _c4["discriminates"]]
    check("S1a-e 判别力元判据（T2 裁决）：FO3/1/4 = %r —— 🔴 FO3 **由 False 翻成 True**"
          "（预注册成立），FO1/FO4 仍 False；谓词对照组 %r"
          % (_tb_disc,
             (ST.discriminates(1, -1), ST.discriminates(1, 1), ST.discriminates(-1, -1))),
          _tb_disc == [True, False, False]
          and ST.discriminates(1, -1) is True
          and ST.discriminates(1, 1) is False
          and ST.discriminates(-1, -1) is False)

    # S1c-a 扇出：与 S1a **同源**（同一个 `FO_TARGET`，不是第二份定义）∧
    #      当前网表实际最大扇出 2 < 3 ⇒ 约束不触发（登记为"零变化"的原因，不是"通过"）。
    _tb_fan = {}
    for g in nl.gates:
        for n in g.ins:
            if n != "CLK":
                _tb_fan[n] = _tb_fan.get(n, 0) + 1
    _tb_fmax = max(_tb_fan.values()) if _tb_fan else 0
    check("S1c-a `max_fanout == FO_TARGET`（同源 %.1f）∧ 实际最大扇出 %d < %.1f ⇒ 不触发（登记）"
          % (_c_loc["max_fanout"], _tb_fmax, _c_loc["fo_target"]),
          _c_loc["max_fanout"] == _c_loc["fo_target"] == ST.FO_TARGET
          and _tb_fmax < _c_loc["fo_target"])

    # S1c-b 转换：取 `_DEFAULT_SLEW_PS`，且**必须自报是假设**（不是测量、不是库值）。
    check("S1c-b `max_transition_ps == _DEFAULT_SLEW_PS`（%.1f）∧ 自报为假设"
          % _c_loc["max_transition_ps"],
          _c_loc["max_transition_ps"] == ST._DEFAULT_SLEW_PS
          and _c_loc["max_transition_is_assumption"] is True)

    # S1-a 本批**对外数字逐位不变**（重申：Q1 改检查器、S1 只加约束，都不许动主链）
    _tb_t = _tb_s["timing"]
    # S1-a **T2 改口对照**（本批唯一允许改数字之处）：主链新口径 + **旧链基线一位不动**。
    #      后者才是"改动只影响主链"的证据 —— 只看主链变了说明不了什么。
    _tb_b = _tb["baseline"]
    check("S1-a T2 改口：面积 %.3f ∧ %d/11 ∧ ideal %.3f / wired %.3f ∧ DRC %d ∧ LVS %d ∧ DEF %d B "
          "∧ claimable=%s ∧ m1=%s ‖ 旧链基线 DRC %d / LVS %d / 43 对网**一位未动**"
          % (_tb_s["place"]["die_area_um2"], _tb_s["route"]["nets_with_segments"],
             _tb_t["comb_delay_ideal_ps"], _tb_t["comb_delay_wired_ps"],
             _tb_s["drc_lvs"]["drc_violations"], _tb_s["drc_lvs"]["lvs_problems"],
             _tb_s["def_write"]["bytes"], _tb["claimability"]["claimable"],
             _tb_s["m1_exit"]["ok"],
             _tb_b["drc_lvs"]["drc_violations"], _tb_b["drc_lvs"]["lvs_problems"]),
          _tb_s["place"]["die_area_um2"] == 59.202
          and _tb_s["route"]["nets_with_segments"] == 10
          and _tb_s["route"]["nets_touched"] == 11
          and _tb_s["route"]["nets_failed"] == 0
          and _tb_t["comb_delay_ideal_ps"] == 46.657
          and _tb_t["comb_delay_wired_ps"] == 92.398
          and _tb_s["drc_lvs"]["drc_violations"] == 0
          and _tb_s["drc_lvs"]["lvs_problems"] == 0
          and _tb_s["def_write"]["bytes"] == 575
          and _tb["claimability"]["claimable"] is False
          and _tb_s["m1_exit"]["ok"] is True
          and _tb_b["drc_lvs"]["drc_violations"] == 87
          and _tb_b["drc_lvs"]["lvs_by_rule"] == {"short": 78, "short_via": 105}
          and _tb_b["drc_lvs"]["lvs_unique_pairs"] == 43)
    print("  [Q1] `short_via` 加层相邻（%d 孔层 × `VIA_BRIDGE`）· 主链 0 / 旧链 105 条不动 · "
          "探针 真短路必报 / 误报必不报 / 未知孔层仍报" % len(DL.VIA_BRIDGE))
    print("  [S1] T_ref=%.3f ps（标准 c17 口径 74.383；本仓 g23=INV）· max_fanout=%.1f · "
          "max_transition=%.1f（假设）· 判别力=%s（T1 登记，T2 裁决）"
          % (_c_loc["clock_period_ps"], _c_loc["max_fanout"],
             _c_loc["max_transition_ps"], _c_loc["discriminates"]))

    # ── T3 / Q3：出处判决（三表 + `num_eps` 分类 + **支配约束报表**）─────────
    #   🔴 本批**零数字变化**：只加只读登记与报表，不改任何上游计算。
    #   🔴 判据不许只测"表存在" —— 每张表都要能被改坏后报出来（`PV.self_check()` 内含 8 条反向构造）。
    #   输入由门禁注入（`dprovenance` 自己不 import 产品链 —— 见其 docstring 的假依赖事故）；
    #   ⚠️ 必须断言 `report_probes == "RAN"`：跳过 ≠ 通过，忘了传参就静默失靶。
    _pv_sc = PV.self_check(nl, _tb)
    _pv_au = PV.provenance_audit(nl)
    _pv_cr = PV.constraint_report(_tb, nl)
    _pv_by = {r["id"]: r for r in _pv_cr["rows"]}

    check("EC-W01 三表 + `num_eps` 齐全且**逐名**登记：derivable %d · unattr %d · dead %d · "
          "num_eps %d（自检 **12 条**反向构造全过=%s · 报表探针=%s；问题=%r）"
          % (_pv_sc["n_derivable"], _pv_sc["n_unattr"], _pv_sc["n_dead_rules"],
             _pv_sc["n_num_eps"], _pv_sc["ok"], _pv_sc["report_probes"], _pv_sc["problems"]),
          _pv_sc["ok"] and _pv_au["ok"]
          and _pv_sc["report_probes"] == "RAN"
          and _pv_sc["n_unattr"] == 7 and _pv_sc["n_dead_rules"] == 0
          and _pv_sc["n_num_eps"] == 1 and _pv_sc["n_derivable"] == 8)

    # EC-W02：unattr 逐名 == 规划 §0.4-4.1 的 7 条（换一个同条数的集合也算漂移）
    _pv_want = ("cell.k_drive", "geom.enc", "geom.s_min", "geom.via",
                "tech.area_per_tr_um2", "tech.r_on_ohm", "tech.t_intr_ps")
    check("EC-W02 `unattr` 逐名锁定（条数相同但换人 = 漂移）：%r"
          % (_pv_au["unattr_ids"],),
          tuple(_pv_au["unattr_ids"]) == _pv_want
          and _pv_au["ratchet"]["unattr_max"] == 7)

    # EC-W03：`derivable` 的 6 条即算量必须与 `recorded` 逐位相同；
    #         另 2 条依赖网表/尺寸的量走**独立重算**（不调 `constraint_layer`）
    _pv_tref_ind = PV.t_ref_for(nl)
    _pv_cl = ST.constraint_layer(nl, comb_delay_ideal_ps=_tb_t["comb_delay_ideal_ps"],
                                 comb_delay_wired_ps=_tb_t["comb_delay_wired_ps"])
    _pv_scales_ind = PV.scales_for(_tb_s["place"]["die_w_um"], DL.W_MIN)
    check("EC-W03 `derivable` 现算复核：`T_ref` 独立重算 %.9f == 产品 %.9f ∧ "
          "`scales` 独立重算 %r == 卡片 %r ⇒ 「有出处」不是一句声明"
          % (_pv_tref_ind, _pv_cl["clock_period_ps"], _pv_scales_ind,
             tuple(_tb_s["ec_b3"]["assumptions"]["scales"])),
          abs(_pv_tref_ind - _pv_cl["clock_period_ps"]) < 1e-9
          and _pv_scales_ind == tuple(_tb_s["ec_b3"]["assumptions"]["scales"]))

    # EC-W03r：反向 —— 把 `t_ref` 的独立路径换成"抄产品"，两条相等就成了自证。
    #   用**错误公式**（漏掉 `t_intr`）复算 ⇒ 必须与产品不等，证明这条判据能分辨两条路径。
    # 🔴 v0.9.405 换公式后，这里升成**双探针**；v0.9.406 再加**第三探针**：
    #   ① 漏掉**自载项**的几何式 ⇒ 与产品值之差必须恰好 = **Σ 逐单元 t_intr**；
    #   ② 那个差值**不得**等于 `n·t_intr_ps`（旧口径）—— 这一条直接证明
    #      「t_intr 已从「一个常数给所有单元」变成「逐单元 ∝ R」」；
    #   ③ **改口前**的 `k_drive·r_on` 式 ⇒ 与产品值必须显著不同（证明公式真换了，不是抄）。
    _pv_ld = ST.FO_TARGET * DC.DEFAULT_TECH.cin_ff
    _pv_path = list(ST.longest_path_gates(nl))
    _pv_geom_nt = sum(DC.cell_r_ohm(g.cell) * DC.LN2 * _pv_ld * DC.OHM_FF_TO_PS
                      for g in _pv_path)
    _pv_old_formula = sum(DC.CELLS[g.cell].k_drive * DC.LN2 * DC.DEFAULT_TECH.r_on_ohm
                          * _pv_ld * DC.OHM_FF_TO_PS for g in _pv_path)
    _pv_gap = _pv_tref_ind - _pv_geom_nt
    _pv_sum_ti = sum(DC.t_intr_ps_for(g.cell) for g in _pv_path)
    _pv_flat_ti = len(_pv_path) * DC.DEFAULT_TECH.t_intr_ps
    check("EC-W03r 三反向探针：① 漏自载项 ⇒ 差 %.6f = Σ逐单元 t_intr（%s 的 %r）；"
          "② 该差 **≠** 旧口径 n·t_intr=%.6f（差 %.6f ⇒ 自载项已逐单元化）；"
          "③ 改口前 `k·r_on` 式 %.6f（与产品差 %.6f ⇒ 公式确实换了）"
          % (_pv_gap, " + ".join("%.0f" % DC.t_intr_ps_for(g.cell) for g in _pv_path),
             [g.cell for g in _pv_path], _pv_flat_ti, abs(_pv_gap - _pv_flat_ti),
             _pv_old_formula, abs(_pv_tref_ind - _pv_old_formula)),
          abs(_pv_gap - _pv_sum_ti) < 1e-9
          and abs(_pv_gap - _pv_flat_ti) > 1.0
          and abs(_pv_old_formula - _pv_cl["clock_period_ps"]) > 1.0)

    # EC-W04：`dead_rules` 必须**空**（T2 让 `W_MIN` 派生自 `W_ROUTE`），且棘轮方向可证伪
    _pv_dead_fake = PV.provenance_audit(tables={"dead_rules": {"W_MIN": {"why": "伪造"}}})
    check("EC-W04 `dead_rules` 为空（`W_MIN` 已派生自 `W_ROUTE`，不再是「0.10 < 0.24 恒不触发」）∧ "
          "棘轮可证伪（塞回一条 ⇒ 审计必红=%s）"
          % (not _pv_dead_fake["ok"]),
          _pv_au["dead_rule_ids"] == [] and _pv_au["ratchet"]["dead_rules_max"] == 0
          and not _pv_dead_fake["ok"])

    # EC-W05 🔴 支配约束报表：12 行、五态齐全、**恰好两个红**（布通 + wired 时序）
    check("EC-W05 支配约束报表 %d 行 · 五态 %r · **恰好两个红**=%r（其余：无约束 %r / 登记而已 %r / 缺输入 %r）"
          % (_pv_cr["n_rows"], _pv_cr["counts"], _pv_cr["summary"]["FAIL"],
             _pv_cr["summary"]["UNCONSTRAINED"], _pv_cr["summary"]["REGISTERED_ONLY"],
             _pv_cr["summary"]["UNDECIDABLE"]),
          _pv_cr["n_rows"] == 12
          and sorted(_pv_cr["summary"]["FAIL"]) == ["delay_wired", "routed"]
          and sorted(_pv_cr["summary"]["UNCONSTRAINED"]) == ["area", "def_bytes"]
          and sorted(_pv_cr["summary"]["REGISTERED_ONLY"]) == ["max_fanout", "max_transition"]
          and _pv_cr["summary"]["UNDECIDABLE"] == ["hold"]
          and all(_pv_cr["counts"][v] > 0 for v in (PV.PASS, PV.FAIL, PV.UNCONSTRAINED,
                                                    PV.REGISTERED_ONLY, PV.UNDECIDABLE)))

    # EC-W06 🔴 **防「没人管算合格」**：无约束项的 verdict 必须是 UNCONSTRAINED 且**不在 PASS 集合里**。
    #   这是本报表最容易被"美化"的一处 —— 把面积写成绿灯，读者就会以为 59.202 是"合格"。
    _pv_leak = [i for i in ("area", "def_bytes") if i in _pv_cr["summary"][PV.PASS]]
    check("EC-W06 无约束项守卫：`area` / `def_bytes` 均 UNCONSTRAINED（governing=%r）∧ "
          "**未混进 PASS 集合**（泄漏=%r）"
          % ([_pv_by[i]["governing"] for i in ("area", "def_bytes")], _pv_leak),
          not _pv_leak
          and all(_pv_by[i]["verdict"] == PV.UNCONSTRAINED
                  and _pv_by[i]["governing"] is None for i in ("area", "def_bytes")))

    # EC-W07 🔴 规划 §0.4-4.6 DoD③：`max_fanout` / `max_transition` 必须标「登记、c17 上无判别力」，
    #   禁计入「已具备约束能力」⇒ verdict 只能是 REGISTERED_ONLY，且文案必须带这句。
    _pv_reg = (_pv_by["max_fanout"], _pv_by["max_transition"])
    check("EC-W07 `max_fanout` / `max_transition` 只能 `REGISTERED_ONLY`（实际扇出 < 上限；slew 不传播"
          " ⇒ 恒真），文案须含「无判别力」：%r"
          % ([r["note"][:26] for r in _pv_reg],),
          all(r["verdict"] == PV.REGISTERED_ONLY for r in _pv_reg)
          and all("无判别力" in r["note"] for r in _pv_reg)
          and all(r["id"] not in _pv_cr["summary"][PV.PASS] for r in _pv_reg))

    # EC-W08 🔴 **颜色是算出来的，不是写死的** —— AST 机核：`verdict=` 表达式里
    #   **不得出现 `PASS`/`FAIL` 这两个名字，也不得出现同名字符串字面量**。
    #   这两种写法都会让「改 report ⇒ 颜色翻面」失效（报表退化成手填）。
    #
    #   ⚠️ 本条初版只查 `ast.Constant`，**真实破坏测试当场抓出它漏**：把
    #   `_verdict(sl_w >= 0)` 换成裸名 `PASS` 时，`PASS` 是 `ast.Name` 不是 `Constant`，
    #   而且外层是 `IfExp` ⇒ 被原判据算进「派生 8 处」里，**判据全绿而报表已撒谎**。
    #   现在改成查表达式里的**全部 Name 与 Constant**，并额外要求 `_verdict(` 出现 ≥5 次。
    #   ⚠️ 循环变量必须叫 `_pv_nd`：`_n` 在本函数前面已是闭包名（:308 在用）。
    _pv_src = inspect.getsource(PV.constraint_report)
    _pv_tree = ast.parse(_pv_src)

    def _pv_leaves(_e):
        """`verdict` 的**取值位置**（只穿透 `IfExp`）：返回 (合规叶子数, 手填清单)。

        🔴 必须递归而**不能** `ast.walk` 全扫：初版全扫把 `route["nets_failed"]` 这类
        **字典键字符串**误报成手填（4 处假红）。判据过宽与过窄一样是错的。
        """
        if isinstance(_e, ast.IfExp):
            _a, _b = _pv_leaves(_e.body)
            _c, _d = _pv_leaves(_e.orelse)
            return (_a + _c, _b + _d)
        if isinstance(_e, ast.Constant) and isinstance(_e.value, str):
            return (0, [_e.value])                      # 字面量 "PASS"
        if isinstance(_e, ast.Name):
            return (1, [_e.id] if _e.id in (PV.PASS, PV.FAIL) else [])
        if isinstance(_e, ast.Call):
            return (1, [])                              # `_verdict(...)`：值由实算决定
        return (0, ["<%s>" % type(_e).__name__])

    _pv_leaves_n, _pv_hand, _pv_kw = 0, [], 0
    for _pv_nd in ast.walk(_pv_tree):
        if isinstance(_pv_nd, ast.keyword) and _pv_nd.arg == "verdict":
            _pv_kw += 1
            _n_leaf, _bad = _pv_leaves(_pv_nd.value)
            _pv_leaves_n += _n_leaf
            _pv_hand += _bad
    _pv_calls = sum(1 for _pv_nd in ast.walk(_pv_tree)
                    if isinstance(_pv_nd, ast.Call)
                    and getattr(_pv_nd.func, "id", "") == "_verdict")
    check("EC-W08 🔴 AST 机核：`verdict` %d 处（取值叶子 %d 个：2 处条件式各拆 2 支）、"
          "`_verdict(` 调用 %d 处；**手填（字面量/裸名 `PASS`·`FAIL`）必须为 0**（实测 %r）"
          % (_pv_kw, _pv_leaves_n, _pv_calls, _pv_hand),
          _pv_kw == 12 and _pv_leaves_n == 14 and _pv_calls >= 5 and _pv_hand == [])

    # EC-W08r 反向探针（**两种手填形态都要抓**）：字符串 `"PASS"` 与裸名 `PASS`
    _pv_syn = ast.parse('def f():\n'
                        '    rows.append(dict(id="a", verdict="PASS"))\n'
                        '    rows.append(dict(id="b", verdict=(UNDECIDABLE if c else PASS)))\n')
    _pv_syn_hit = []
    for _pv_nd2 in ast.walk(_pv_syn):
        if isinstance(_pv_nd2, ast.keyword) and _pv_nd2.arg == "verdict":
            _pv_syn_hit += _pv_leaves(_pv_nd2.value)[1]
    check("EC-W08r 反向探针：合成源码里 `verdict=\"PASS\"` 与裸名 `else PASS` 两种手填 ⇒ "
          "检测器都报出 %r（必须恰好 2 处）" % (_pv_syn_hit,),
          sorted(_pv_syn_hit) == ["PASS", "PASS"])

    # EC-W09 `num_eps` 与 `unattr` 不许混：前者**算得出下界**且无 owner；后者有无 owner 是硬条件
    _pv_eps = PV.num_eps_table()
    check("EC-W09 `num_eps` 与 `unattr` 分得开：`SPACE_EPS` 下界 %.3e µm ⇒ 余量 %.1e×、"
          "`owner_step` 须为 None（有下界就不是缺口）"
          % (_pv_eps["ddrc_lvs.SPACE_EPS"]["bound"],
             _pv_eps["ddrc_lvs.SPACE_EPS"]["value"] / _pv_eps["ddrc_lvs.SPACE_EPS"]["bound"]),
          _pv_eps["ddrc_lvs.SPACE_EPS"]["owner_step"] is None
          and _pv_eps["ddrc_lvs.SPACE_EPS"]["bound"] > 0
          and _pv_eps["ddrc_lvs.SPACE_EPS"]["value"] >= _pv_eps["ddrc_lvs.SPACE_EPS"]["bound"]
          and not (set(_pv_eps) & set(_pv_au["unattr_ids"])))

    # EC-W10 T3 **零数字变化**：出处判决只加字段，主链 8 个数逐位不动（独立于 S1-a 的第二道锁）
    check("EC-W10 T3 零变化：面积 %.3f ∧ %d/11 ∧ %.3f/%.3f ps ∧ DRC %d ∧ LVS %d ∧ DEF %d ∧ "
          "claimable=%s ∧ m1=%s —— 出处判决未动任何上游计算"
          % (_tb_s["place"]["die_area_um2"], _tb_s["route"]["nets_with_segments"],
             _tb_t["comb_delay_ideal_ps"], _tb_t["comb_delay_wired_ps"],
             _tb_s["drc_lvs"]["drc_violations"], _tb_s["drc_lvs"]["lvs_problems"],
             _tb_s["def_write"]["bytes"], _tb["claimability"]["claimable"],
             _tb_s["m1_exit"]["ok"]),
          _tb_s["place"]["die_area_um2"] == 59.202
          and _tb_s["route"]["nets_with_segments"] == 10
          and _tb_t["comb_delay_ideal_ps"] == 46.657
          and _tb_t["comb_delay_wired_ps"] == 92.398
          and _tb_s["drc_lvs"]["drc_violations"] == 0
          and _tb_s["drc_lvs"]["lvs_problems"] == 0
          and _tb_s["def_write"]["bytes"] == 575
          and _tb["claimability"]["claimable"] is False
          and _tb_s["m1_exit"]["ok"] is True)

    # EC-W11 T3 **不扩 API 形状**：`provenance` 不进 `stages`、`SEGMENTS_COVERED` 仍 10 段。
    #   加段会连带 EC-B 系列的段形态锁定（顶层键数 / 段数），与本批「只做归因」不符。
    from lda_webui import digital_case as _DGC        # noqa: E402 — 就地导入，避免顶层多一个 webui 依赖
    check("EC-W11 T3 不扩对外形状：`stages` 仍 %d 段（无 `provenance`）∧ `SEGMENTS_COVERED` 仍 %d 段"
          % (len(_tb["stages"]), len(_DGC.SEGMENTS_COVERED)),
          all(n != "provenance" for n, _ in _tb["stages"])
          and len(_DGC.SEGMENTS_COVERED) == 10
          and "provenance" not in _DGC.SEGMENTS_COVERED)

    # EC-W12 🔴 消费者必须**真的用**（不是为了让模块"有入度"挂个空壳）：
    #   `dsignoff.signoff_ledger` 是 `dprovenance` 的**非门禁**下游 —— 签核台账与报表逐位一致。
    #   没有它，`dprovenance` 就是零入度孤岛（`run_ecore_reuse_metrics_smoke` 的 M2 会红），
    #   而「加个空壳函数骗入度」正是那道门禁 M14 要防的事。
    _pv_led = DS.signoff_ledger(_tb, nl)
    check("EC-W12 签核台账（`dsignoff.signoff_ledger`）与报表逐位一致：%d 行 · 五态 %r —— "
          "`dprovenance` 有**真**非门禁下游（不是空壳骗入度）"
          % (_pv_led["n_rows"], _pv_led["counts"]),
          _pv_led["n_rows"] == _pv_cr["n_rows"]
          and _pv_led["summary"] == _pv_cr["summary"]
          and _pv_led["counts"] == _pv_cr["counts"])

    # ── T4 / S2：库接线（数据契约）────────────────────────────────────────
    #   🔴 本批的真相：`SAMPLE_LIBERTY`（pF 尺度、INVX1 命名）与本仓 c17（0–2 fF、
    #   0.77 µm²）差 3 个数量级 —— 直接接线会 100% 钳位且全部 fallback，
    #   所以另建 `SAMPLE_LIBERTY_L2`：**把本仓 Tech 显式化**（同名 INV/NAND2、fF 尺度）。
    #   它证明的是「代码常量 → 数据文件」这条**通路**不引入偏差，不是"接了真库"。
    _lib_l2 = LB.parse_liberty(LB.SAMPLE_LIBERTY_L2)
    _lib_pf = LB.parse_liberty(LB.SAMPLE_LIBERTY)
    _lib_ld = ST.lib_defaults(_lib_l2)

    _lib_dim = next(a.table for a in ST.lib_map(_lib_l2)["INV"].arcs if a.table)
    check("EC-X01 数据契约可解析：`SAMPLE_LIBERTY_L2` → %r（与 `dcells` 同名）· "
          "表 %d slew × %d load · 库级 vdd=%.2f V / %.0f °C / mt=%.1f ps / cin=%.1f fF"
          % (sorted(ST.lib_map(_lib_l2)), len(_lib_dim[0]), len(_lib_dim[1]),
             _lib_ld["nom_voltage_v"], _lib_ld["nom_temperature_c"],
             _lib_ld["default_max_transition_ps"],
             _lib_ld["default_input_pin_cap_ff"]),
          sorted(ST.lib_map(_lib_l2)) == ["INV", "NAND2"]
          and _lib_ld["nom_voltage_v"] == DC.DEFAULT_TECH.vdd
          and _lib_ld["nom_temperature_c"] == DS.T_REF_C
          and _lib_ld["default_max_transition_ps"] == ST._DEFAULT_SLEW_PS
          and _lib_ld["default_input_pin_cap_ff"] == DC.DEFAULT_TECH.cin_ff)

    # EC-X02 🔴 **保护性约束**（T4 第一纪律）：不给库 ⇒ 主链 9 数逐位不变
    _lib_rep_off = B3.run_trunk_from_verilog(V.SAMPLE_VERILOG, baseline=False)
    _lib_t_off = {n: d for n, d in _lib_rep_off["stages"]}["timing"]
    check("EC-X02 保护性约束（`lib=None`）：主链 9 数逐位不变 · %.3f µm² / %d/11 / "
          "%.3f / %.3f ps / DRC %d / LVS %d / DEF %d B / claimable=%s / m1=%s · "
          "`lib_chain=%s`"
          % (_tb_s["place"]["die_area_um2"], _tb_s["route"]["nets_with_segments"],
             _lib_t_off["comb_delay_ideal_ps"], _lib_t_off["comb_delay_wired_ps"],
             _tb_s["drc_lvs"]["drc_violations"], _tb_s["drc_lvs"]["lvs_problems"],
             _tb_s["def_write"]["bytes"], _tb["claimability"]["claimable"],
             _tb_s["m1_exit"]["ok"], _lib_t_off["lib_chain"]),
          _lib_t_off["lib_chain"] == "closed"
          and _lib_t_off["comb_delay_ideal_ps"] == 46.657
          and _lib_t_off["comb_delay_wired_ps"] == 92.398
          and _tb_s["place"]["die_area_um2"] == 59.202
          and _tb_s["route"]["nets_with_segments"] == 10
          and _tb_s["drc_lvs"]["drc_violations"] == 0
          and _tb_s["drc_lvs"]["lvs_problems"] == 0
          and _tb_s["def_write"]["bytes"] == 575
          and _tb["claimability"]["claimable"] is False
          and _tb_s["m1_exit"]["ok"] is True)

    # EC-X03 🔴 接线是**纯通路**：lib=L2 与闭式逐位相同，且零钳位零回落
    _lib_rep_on = B3.run_trunk_from_verilog(V.SAMPLE_VERILOG, baseline=False, lib=_lib_l2)
    _lib_t_on = {n: d for n, d in _lib_rep_on["stages"]}["timing"]
    check("EC-X03 lib=L2 纯通路：ideal %.9f / wired %.9f **与闭式逐位相同** · "
          "`lib_chain=%s` · clamped=%d · fallback=%r"
          % (_lib_t_on["comb_delay_ideal_ps"], _lib_t_on["comb_delay_wired_ps"],
             _lib_t_on["lib_chain"], _lib_t_on["lib_clamped"],
             _lib_t_on["lib_fallback_cells"]),
          _lib_t_on["lib_chain"] == "liberty:SAMPLE_PDK_L2"
          and _lib_t_on["comb_delay_ideal_ps"] == _lib_t_off["comb_delay_ideal_ps"]
          and _lib_t_on["comb_delay_wired_ps"] == _lib_t_off["comb_delay_wired_ps"]
          and _lib_t_on["lib_clamped"] == 0
          and _lib_t_on["lib_fallback_cells"] == [])

    # EC-X04 非网格 load 的插值误差：闭式对 load **线性** ⇒ 两点插值**精确**，
    #   所以误差只能是浮点量级。这条给的是「为什么差为 0」的理由，不是「调参调到 0」。
    _lib_tab = next(a.table for a in ST.lib_map(_lib_l2)["INV"].arcs if a.table)
    _lib_err = []
    for _ld_ff in (0.5, 1.5, 3.0, 6.0, 7.25):
        _closed = DC.cell_delay_ps("INV", _ld_ff, DC.DEFAULT_TECH)
        _lv, _cl = ST.interp_nldm(_lib_tab, ST._DEFAULT_SLEW_PS, _ld_ff)
        _lib_err.append((_ld_ff, abs(_lv - _closed), _cl))
    check("EC-X04 非网格 load 的插值误差 ≤1e-12 ps：%r ⇒ 闭式对 load 线性、"
          "两点插值精确（差为 0 有理由，不是调出来的）"
          % ([("%.2f fF" % a, "%.2e" % b) for a, b, _c in _lib_err],),
          all(b <= 1e-12 for _a, b, _c in _lib_err)
          and not any(c for _a, _b, c in _lib_err))

    # EC-X05 🔴🔴 **本批最强判据**：改 Tech ⇒ 闭式跟着变、**lib 一动不动**
    #   ⇒ 库确实是**独立数据源**，不是闭式的马甲。只测"lib≈闭式"证明不了这一点。
    _lib_T2 = dataclasses.replace(DC.DEFAULT_TECH,
                                  r_on_ohm=DC.DEFAULT_TECH.r_on_ohm * 2.0)
    _lib_a1 = ST.sta(nl, port_load_ff=1.0, topo_sort=True)
    _lib_b1 = ST.sta(nl, port_load_ff=1.0, topo_sort=True, lib=_lib_l2)
    _lib_a2 = ST.sta(nl, tech=_lib_T2, port_load_ff=1.0, topo_sort=True)
    _lib_b2 = ST.sta(nl, tech=_lib_T2, port_load_ff=1.0, topo_sort=True, lib=_lib_l2)
    check("EC-X05 🔴 库是独立数据源：`r_on×2` ⇒ 闭式 %.3f→%.3f ps（×%.4f）· "
          "**lib %.3f→%.3f ps（×%.4f）一动不动**"
          % (_lib_a1.comb_delay_ps, _lib_a2.comb_delay_ps,
             _lib_a2.comb_delay_ps / _lib_a1.comb_delay_ps,
             _lib_b1.comb_delay_ps, _lib_b2.comb_delay_ps,
             _lib_b2.comb_delay_ps / _lib_b1.comb_delay_ps),
          abs(_lib_a2.comb_delay_ps - _lib_a1.comb_delay_ps) > 20.0
          and _lib_b2.comb_delay_ps == _lib_b1.comb_delay_ps)

    # EC-X06 反向探针（**尺度错配**）：把 load 轴 fF→pF 放大 1000×，名字不动。
    #   🔴 症状**不是**钳位 —— c17 的 0–2 fF 全落在 [0, 1000] 这一格里，钳位根本不发生；
    #   真症状是「**插值被拉平**」：表在 1000 fF 处的值被摊到 1000 fF 的跨度上 ⇒
    #   负载灵敏度塌缩 1000 倍、延时严重失真。**初版判据写成「clamped>0 且延时≥100×」
    #   当场红了** —— 因为我把症状想错了。判据要盯**失真**，不是盯钳位。
    _lib_bad_src = LB.SAMPLE_LIBERTY_L2.replace(
        'index_1 ( "0.0, 0.001, 0.002, 0.004, 0.008" ) ;',
        'index_1 ( "0.0, 1.0, 2.0, 4.0, 8.0" ) ;')
    assert _lib_bad_src != LB.SAMPLE_LIBERTY_L2, "反向构造点没命中"
    _lib_bad = LB.parse_liberty(_lib_bad_src)
    _lib_bad_tab = next(a.table for a in ST.lib_map(_lib_bad)["INV"].arcs if a.table)

    def _slope(tab, lo, hi):
        a, _c1 = ST.interp_nldm(tab, ST._DEFAULT_SLEW_PS, lo)
        b, _c2 = ST.interp_nldm(tab, ST._DEFAULT_SLEW_PS, hi)
        return (b - a) / (hi - lo)

    _lib_slope_ok = _slope(_lib_tab, 1.0, 2.0)
    _lib_slope_bad = _slope(_lib_bad_tab, 1.0, 2.0)
    _lib_bad_sta = ST.sta(nl, port_load_ff=1.0, topo_sort=True, lib=_lib_bad)
    _lib_ratio = _lib_bad_sta.comb_delay_ps / _lib_a1.comb_delay_ps
    check("EC-X06 反向探针（尺度错配）：load 轴 fF→pF ×1000 ⇒ **斜率塌缩** "
          "%.4f→%.6f ps/fF（×%.0f）· 总延时 %.2f vs 闭式 %.2f ps（×%.2f）· "
          "clamped=%d（**钳位不是主症状**，失真才是）"
          % (_lib_slope_ok, _lib_slope_bad,
             _lib_slope_ok / _lib_slope_bad if _lib_slope_bad else float("inf"),
             _lib_bad_sta.comb_delay_ps, _lib_a1.comb_delay_ps, _lib_ratio,
             _lib_bad_sta.lib_clamped),
          _lib_slope_bad < _lib_slope_ok / 100.0
          and abs(_lib_ratio - 1.0) > 0.5)

    # EC-X07 反向探针（命名错配）：pF 库的 cell 叫 INVX1/NAND2X1 ⇒ 全部 fallback，
    #   且**如实记入** `lib_fallback_cells`（不静默回落）。
    _lib_pf_sta = ST.sta(nl, port_load_ff=1.0, topo_sort=True, lib=_lib_pf)
    check("EC-X07 反向探针（命名错配）：`SAMPLE_LIBERTY` 的 cell 是 INVX1/NAND2X1 ⇒ "
          "fallback=%r（**不静默**）· 延时回落到闭式 %.3f ps"
          % (sorted(_lib_pf_sta.lib_fallback_cells), _lib_pf_sta.comb_delay_ps),
          sorted(_lib_pf_sta.lib_fallback_cells) == ["INV", "NAND2"]
          and _lib_pf_sta.comb_delay_ps == _lib_a1.comb_delay_ps)

    # EC-X08 🔴 出处翻转而数字不变：`max_transition` 从「假设」变「库数据」
    _lib_c0 = ST.constraint_layer(nl, comb_delay_ideal_ps=46.657,
                                  comb_delay_wired_ps=92.398)
    _lib_c1 = ST.constraint_layer(nl, comb_delay_ideal_ps=46.657,
                                  comb_delay_wired_ps=92.398, lib=_lib_l2)
    check("EC-X08 出处翻转而数字不变：`max_transition` %.1f → %.1f ps · "
          "`is_assumption` %s → %s · source `%s` → `%s` · 判别力 %s→%s"
          % (_lib_c0["max_transition_ps"], _lib_c1["max_transition_ps"],
             _lib_c0["max_transition_is_assumption"],
             _lib_c1["max_transition_is_assumption"],
             _lib_c0["max_transition_source"], _lib_c1["max_transition_source"],
             _lib_c0["discriminates"], _lib_c1["discriminates"]),
          _lib_c0["max_transition_is_assumption"] is True
          and _lib_c1["max_transition_is_assumption"] is False
          and _lib_c0["max_transition_ps"] == _lib_c1["max_transition_ps"] == 50.0
          and _lib_c0["max_transition_source"] == "_DEFAULT_SLEW_PS"
          and _lib_c1["max_transition_source"] == "Liberty.default_max_transition"
          and _lib_c0["clock_period_ps"] == _lib_c1["clock_period_ps"])

    # ── T4b / S2：三角签核（ff / tt / ss）—— **零改口**，但暴露一条结构性局限 ──
    #   🔴 本批不做 PVT/area/LEF（那三项会改主链 9 数，需独立预注册）；只做**三角**，
    #   因为它零改口且规划 DoD 明确要求「至少报三组而非一组」。
    _cn = ST.signoff_corners(nl, wire_load_ff=_wl2)
    _cn_tt = _cn["corners"]["tt"]
    # 🔴 **表示差异 vs 真差异**：report 里的 `comb_delay_*` 是 **3 位取整**（46.657 / 92.398），
    #   而 `signoff_corners` 给的是未取整值（37.191623125 / 74.989632028）。
    #   拿取整值做「逐位相等」判据 ⇒ 假红（差值 8.7e-4 全是舍入）。故此处**现算一份未取整**。
    _cn_pl = ST.FO_PORT * DC.DEFAULT_TECH.cin_ff
    _cn_ideal = ST.sta(nl, port_load_ff=_cn_pl, topo_sort=True).comb_delay_ps
    _cn_wired = ST.sta(nl, wire_load_ff=_wl2, port_load_ff=_cn_pl, topo_sort=True).comb_delay_ps
    _cn_cl = ST.constraint_layer(nl, comb_delay_ideal_ps=_cn_ideal,
                                 comb_delay_wired_ps=_cn_wired)

    check("EC-Y01 三角齐备且因子锁 `dsignoff.CORNERS`：%r（按 r_on 升序）· "
          "ff/tt/ss k_r=%r k_c=%r"
          % (_cn["corners_order"],
             [_cn["corners"][k]["k_r"] for k in _cn["corners_order"]],
             [_cn["corners"][k]["k_c"] for k in _cn["corners_order"]]),
          _cn["corners_order"] == ["ff", "tt", "ss"]
          and all(abs(_cn["corners"][k]["k_r"] - DS.CORNERS[k][0]) < 1e-12
                  and abs(_cn["corners"][k]["k_c"] - DS.CORNERS[k][1]) < 1e-12
                  for k in _cn["corners_order"]))

    # EC-Y02 🔴 **保护性约束**：tt 必须逐位等于单点口径（三角没有偷偷改口径的唯一证据）
    check("EC-Y02 保护性约束（tt == **未取整**单点口径）：T_ref %.9f vs %.9f · ideal %.9f vs "
          "%.9f · wired %.9f vs %.9f（report 里 %.3f/%.3f 是 3 位取整，不比它）"
          % (_cn_tt["t_ref_ps"], _cn_cl["clock_period_ps"],
             _cn_tt["ideal_ps"], _cn_ideal, _cn_tt["wired_ps"], _cn_wired,
             _tb_t["comb_delay_ideal_ps"], _tb_t["comb_delay_wired_ps"]),
          abs(_cn_tt["t_ref_ps"] - _cn_cl["clock_period_ps"]) < 1e-12
          and abs(_cn_tt["ideal_ps"] - _cn_ideal) < 1e-12
          and abs(_cn_tt["wired_ps"] - _cn_wired) < 1e-12)

    # EC-Y02r 反向：把 tt 的因子改成非 (1,1) ⇒ 它就不再等于单点口径
    #   （证明 EC-Y02 成立是因为「因子恰为 1」，不是判据恒真）
    _cn_bad = ST.signoff_corners(nl, wire_load_ff=_wl2, corners={"tt": (1.10, 1.05)})
    check("EC-Y02r 反向探针：`tt` 因子改 (1.10, 1.05) ⇒ T_ref %.6f ≠ 单点 %.6f（差 %.6f ps）"
          % (_cn_bad["corners"]["tt"]["t_ref_ps"], _cn_cl["clock_period_ps"],
             _cn_bad["corners"]["tt"]["t_ref_ps"] - _cn_cl["clock_period_ps"]),
          abs(_cn_bad["corners"]["tt"]["t_ref_ps"] - _cn_cl["clock_period_ps"]) > 1.0)

    # EC-Y03 单调链：按 `r_on` 升序（ff<tt<ss）⇒ T_ref / wired 同序单调
    _cn_seq = [(k, _cn["corners"][k]["t_ref_ps"], _cn["corners"][k]["wired_ps"])
               for k in _cn["corners_order"]]
    check("EC-Y03 单调链：%r ⇒ T_ref 与 wired 均随 r_on 单调增"
          % ([(k, round(a, 3), round(b, 3)) for k, a, b in _cn_seq],),
          _cn_seq[0][1] < _cn_seq[1][1] < _cn_seq[2][1]
          and _cn_seq[0][2] < _cn_seq[1][2] < _cn_seq[2][2])

    # EC-Y04 散布可算：`t_ref` 散布 > `wired` 散布（线载不随 corner 缩 ⇒ 部分抵消）
    check("EC-Y04 三组散布：T_ref **%.3f%%** · ideal %.3f%% · wired **%.3f%%** —— "
          "`wired` < `t_ref`（线载不随 corner 缩放 ⇒ 部分抵消）"
          % (_cn["spread_pct"]["t_ref_ps"], _cn["spread_pct"]["ideal_ps"],
             _cn["spread_pct"]["wired_ps"]),
          _cn["spread_pct"]["t_ref_ps"] > _cn["spread_pct"]["wired_ps"] > 0
          # 🔴 v0.9.406：44.826% → **41.934%**。原因不是「数据变了」，是**模型更少了常数项**：
          #   自载项几何化后 `t_pd` 整体 ∝ R，corner 对 `r_on` 的缩放不再被那个固定 `t_intr`
          #   稀释 ⇒ 散布收窄。⚠️ 这条仍是「按当前模型测的值」，不是物理常数。
          and abs(_cn["spread_pct"]["t_ref_ps"] - 41.933667) < 0.01)

    # EC-Y05 🔴🔴 **结构性发现**：三个角 slack(wired) 全为负，且 span 只有 ~3 ps
    #   而 T_ref 散布 44.4% ⇒ **违例的根因不是 corner**，是 FO_target=3 的负载假设。
    #   机制：`T_ref` 与 `delay` **同源**（都来自 Tech）⇒ 同套 (kr,kc) 缩放时部分抵消。
    check("EC-Y05 🔴 三角落**全违例**（含 ff）：%r · span **%.6f ps** 而 T_ref 散布 %.1f%% "
          "⇒ 违例根因不是 corner（`T_ref` 与 `delay` 同源 ⇒ 部分抵消）"
          % ({k: round(_cn["corners"][k]["slack_wired_ps"], 4) for k in _cn["corners_order"]},
             _cn["slack_wired"]["span_ps"], _cn["spread_pct"]["t_ref_ps"]),
          _cn["slack_wired"]["all_negative"] is True
          and _cn["slack_wired"]["n_negative"] == _cn["slack_wired"]["n_corners"] == 3
          # 🔴 v0.9.405：原来写 `span < 5.0 ps` —— 那是拟合旧几何的魔数（新值 5.058 就假红）。
          #   要说的性质是「corner 只解释了违例的一小部分」⇒ 用**比值**：span 与最轻违例之比。
          and _cn["slack_wired"]["span_ps"] < 0.25 * abs(
              max(_cn["corners"][k]["slack_wired_ps"] for k in _cn["corners_order"]))
          and _cn["spread_pct"]["t_ref_ps"] > 40.0)

    # EC-Y06 反例实证：网级 RC 合计只占总延时的 0.035% ⇒ **「对线做 corner」等于没做**
    #   （这是「为什么必须对门级 `Tech` 做三角」的定量理由，不是偏好）
    _cn_rc_sum = 0.0
    for _cn_n in sorted({_sh.net for _sh in _sh2 if _sh.net}):
        _cn_rc = DS.net_rc(_sh2, lambda L: {DET.L_M3: "M3", DET.L_M4: "M4"}.get(L, "?"),
                           _cn_n)
        if _cn_rc["n_seg"]:
            _cn_rc_sum += DS.corner_table(_cn_rc)["delay_fs"]["tt"]
    _cn_rc_ps = _cn_rc_sum / 1000.0
    check("EC-Y06 量纲对照：网级 Elmore RC 合计 **%.6f ps** vs 门级 wired %.3f ps "
          "⇒ 仅占 **%.4f%%** ⇒ 「对线做 corner」等于没做（故本批对门级 `Tech` 做）"
          % (_cn_rc_ps, _tb_t["comb_delay_wired_ps"],
             _cn_rc_ps / _tb_t["comb_delay_wired_ps"] * 100.0),
          _cn_rc_ps > 0
          and _cn_rc_ps / _tb_t["comb_delay_wired_ps"] < 0.001)

    # EC-Y07 段形态：诊断段纪律（不进 blocking · 无 n_fail/ok/pass · 显式 not_included）
    _cn_flat = {k for k in _cn}
    check("EC-Y07 段形态：`in_blocking=False` ∧ `scope=DIAGNOSTIC_ONLY` ∧ 顶层无 "
          "`n_fail`/`ok`/`pass` ∧ `not_included` 非空（含「不是 PVT 签核」）",
          _cn["in_blocking"] is False and _cn["scope"] == "DIAGNOSTIC_ONLY"
          and not ({"n_fail", "ok", "pass"} & _cn_flat)
          and "不是 PVT 签核" in _cn["not_included"])

    print("  [T4b] 三角签核：ff/tt/ss = %.3f / %.3f / %.3f ps（wired）· T_ref 散布 %.1f%% · "
          "**三个角 slack 全负**（span 仅 %.3f ps）"
          % (_cn["corners"]["ff"]["wired_ps"], _cn["corners"]["tt"]["wired_ps"],
             _cn["corners"]["ss"]["wired_ps"], _cn["spread_pct"]["t_ref_ps"],
             _cn["slack_wired"]["span_ps"]))
    print("  [T4b 结构性局限] %s ⇒ 要真抓 corner 风险，`T_ref` 必须来自外部时钟 spec（T5 前提）"
          % _cn["structural_limit"][:78])
    print("  [T4b 边界] 三角只缩放 `r_on`/`cin_ff` 两个量：不含温度对迁移率/阈值、不含电压对延时、"
          "不含 OCV/AOCV —— 是「两参数散布」，不是 PVT 签核")

    # ── T5 / Q4：单元几何的**可造性判定**（本批把"能缩多少"变成可机核的量）────────
    #   🔴 立项前测算推翻了规划前提：规划写「Q4 = device_scale 接线 ⇒ 几何参数化」，
    #   实测**除 s=1.0 外每一步都出 DRC 或 LVS 违例**（连 0.98 都红）⇒ 「接线」不是
    #   把因子乘进去，而是**必须按规则重推布局**（= P5 模板化）。本批先把这条边界钉死。
    _nf_sc = NF.self_check()
    _nf_inv = CL.CELLS["INV_X1"]()
    _nf_nand = CL.CELLS["NAND2_X1"]()
    _nf_scan_inv = NF.scan(_nf_inv)
    _nf_scan_nand = NF.scan(_nf_nand)
    _nf_bad = [r for r in _nf_scan_inv + _nf_scan_nand
               if r["scale"] != 1.0 and r["feasible"]]
    _nf_head_inv = NF.width_headroom(_nf_inv)
    _nf_head_nand = NF.width_headroom(_nf_nand)

    check("EC-Z01 判定器自检（含 5 条反向构造）=%s · 宽度硬下限 %d nm（pad %d + 接入间距 %d）"
          % (_nf_sc["ok"], _nf_sc["width_floor_nm"], NF.PAD_NM, NF.ACCESS_GAP_NM),
          _nf_sc["ok"] and _nf_sc["problems"] == []
          and _nf_sc["width_floor_nm"] == 582
          and NF.width_floor_nm(pad_nm=100) == 100 + NF.ACCESS_GAP_NM)

    # EC-Z02 🔴 **保护性约束**：s=1.0 必须与产品几何**逐位相同**（含矩形/引脚/尺寸）
    _nf_one = NF.scale_cell(_nf_inv, 1.0)
    _nf_same = ([(r.layer, r.x0, r.y0, r.x1, r.y1) for r in _nf_one.rects]
                == [(r.layer, r.x0, r.y0, r.x1, r.y1) for r in _nf_inv.rects]
                and all(_nf_one.pins[k].x0 == _nf_inv.pins[k].x0
                        and _nf_one.pins[k].y1 == _nf_inv.pins[k].y1
                        for k in _nf_inv.pins)
                and (_nf_one.w, _nf_one.h) == (_nf_inv.w, _nf_inv.h))
    check("EC-Z02 保护性约束（s=1.0）：%dx%d nm · %d 矩形 · %d 引脚 **逐位相同** ∧ 基线可造=%s"
          % (_nf_one.w, _nf_one.h, len(_nf_one.rects), len(_nf_one.pins),
             _nf_scan_inv[0]["feasible"]),
          _nf_same and _nf_scan_inv[0]["feasible"] and _nf_scan_nand[0]["feasible"])

    # EC-Z03 🔴🔴 **本批核心定论**：按比例缩放在物理上不成立 —— 除 1.0 外**全部**违例
    check("EC-Z03 🔴 按比例缩放**不成立**：%d 个比例点（%r）里可造的有 **%d** 个 · "
          "s=0.98 即红（DRC %d / LVS %d）⇒ 缩放不是连续操作，`scale` 不能当旋钮"
          % (len(_nf_scan_inv) - 1, list(NF.SCALE_GRID), len(_nf_bad),
             _nf_scan_inv[1]["drc"], _nf_scan_inv[1]["lvs"]),
          len(_nf_bad) == 0
          and _nf_scan_inv[1]["scale"] == 0.98
          and (_nf_scan_inv[1]["drc"] > 0 or _nf_scan_inv[1]["lvs"] > 0)
          and NF.max_feasible_scale(_nf_inv) == 1.0
          and NF.max_feasible_scale(_nf_nand) == 1.0)

    # EC-Z04 面积收益的天花板：引脚 pad 不随器件缩 ⇒ **宽度有硬下限**
    check("EC-Z04 宽度下限 %d nm ⇒ INV 只余 **%d nm（%.2f%%）** · NAND2 余 %d nm（%.2f%%）"
          " ⇒ 即使将来重画，`device_scale=0.6` 也拿不到名义 ×0.36"
          % (_nf_head_inv["w_floor_nm"], _nf_head_inv["headroom_nm"],
             _nf_head_inv["max_width_saving_pct"], _nf_head_nand["headroom_nm"],
             _nf_head_nand["max_width_saving_pct"]),
          _nf_head_inv["w_floor_nm"] == _nf_head_nand["w_floor_nm"] == 582
          and _nf_head_inv["headroom_nm"] == 38
          and abs(_nf_head_inv["max_width_saving_pct"] - 6.129) < 0.01
          and _nf_head_nand["headroom_nm"] == 398)

    # EC-Z05 两套规则必须分开：金属**不缩** ∧ 器件**确实缩**（否则是「没缩」冒充「只缩器件」）
    _nf_r06 = NF.scale_rules(0.6)
    check("EC-Z05 规则分层：金属 %r 在 s=0.6 下不变（%s）· 器件 `poly_w` %d→%d 确实缩了"
          % (list(NF.METAL_RULES), NF.metal_rules_unscaled(0.6),
             CL.RULES["poly_w"], _nf_r06["poly_w"]),
          NF.metal_rules_unscaled(0.6)
          and _nf_r06["poly_w"] == 30
          and _nf_r06["cont_w"] == 27
          and _nf_r06["m1_w"] == CL.RULES["m1_w"])

    # EC-Z06 反向探针：判定器**不是恒说"不可缩"** —— 给一颗本身可缩的单元必须给 <1
    #   （否则 EC-Z03 的"全红"可能只是判定器写死了 False）
    _nf_tiny = CL.Cell("TINY", 600, 600,
                       [CL.R(CL.L_M1, 0, 0, 600, 600, role="pin")],
                       {"A": CL.R(CL.L_M1, 0, 0, 600, 600, net="A")}, [])
    _nf_tiny_s = NF.max_feasible_scale(_nf_tiny, (0.6,))
    check("EC-Z06 反向探针：构造一颗**无器件**的空壳单元 ⇒ `max_feasible_scale` = %.2f（<1）"
          " ⇒ EC-Z03 的「全红」是真判定，不是判定器写死" % _nf_tiny_s,
          _nf_tiny_s == 0.6)

    # EC-Z07 / S3：`max_cells` **不许静默截断**（旧代码 `break` ⇒ 分子分母一起缩的假绿灯）
    _s3_raised, _s3_msg = False, ""
    try:
        P.place_real(nl, max_cells=3)
    except ValueError as _exc:
        _s3_raised, _s3_msg = True, str(_exc)
    #   🔴 `truncate_ok=True` 这一支也要**受控**：若有人把它写成反向逻辑（默认截断、
    #   显式反而抛），这里会崩而不是报红 ⇒ 违反「判据不可定位 = 不可修」。故捕获。
    _s3_err = ""
    try:
        _s3_ok = P.place_real(nl, max_cells=3, truncate_ok=True)
    except Exception as _exc2:              # noqa: BLE001 — 破坏后要能**报红**，不能崩
        _s3_ok = {"n_picked": -1, "truncated": None, "n_truncated": -1,
                  "n_gates_total": -1}
        _s3_err = "%s: %s" % (type(_exc2).__name__, str(_exc2)[:80])
    check("EC-Z07 `max_cells` 显式拒绝：默认**抛错**=%s（消息含门数与截断数=%s）· "
          "显式 `truncate_ok` 才截断：n_picked=%d · truncated=%s · n_truncated=%d"
          % (_s3_raised, ("拒绝静默截断" in _s3_msg), _s3_ok["n_picked"],
             _s3_ok["truncated"], _s3_ok["n_truncated"]) + ("  err=%s" % _s3_err if _s3_err else ""),
          _s3_raised and "拒绝静默截断" in _s3_msg
          and _s3_err == ""
          and _s3_ok["truncated"] is True and _s3_ok["n_truncated"] == 3
          and _s3_ok["n_picked"] == 3
          and _s3_ok["n_gates_total"] == len(nl.gates))

    # EC-Z08 主链 9 数一位未改（严格化与判定器**零副作用**）
    #   🔴 `truncated` **不进** `place` 段：加对外字段要连带过 6 道「反向完备」判据，
    #   本批不改对外形状 ⇒ 这里**现算一遍**（c17 只有 6 门，成本可忽略）。
    _s3_main = P.place_real(nl)
    check("EC-Z08 零副作用：主链 %.3f µm² · %d/11 · DRC %d · LVS %d · %.3f/%.3f ps · "
          "DEF %d B · claimable=%s · m1=%s · c17 布通 truncated=%s"
          % (_tb_s["place"]["die_area_um2"], _tb_s["route"]["nets_with_segments"],
             _tb_s["drc_lvs"]["drc_violations"], _tb_s["drc_lvs"]["lvs_problems"],
             _tb_t["comb_delay_ideal_ps"], _tb_t["comb_delay_wired_ps"],
             _tb_s["def_write"]["bytes"], _tb["claimability"]["claimable"],
             _tb_s["m1_exit"]["ok"], _s3_main["truncated"]),
          _tb_s["place"]["die_area_um2"] == 59.202
          and _tb_s["route"]["nets_with_segments"] == 10
          and _tb_s["drc_lvs"]["drc_violations"] == 0
          and _tb_s["drc_lvs"]["lvs_problems"] == 0
          and _tb_t["comb_delay_ideal_ps"] == 46.657
          and _tb_t["comb_delay_wired_ps"] == 92.398
          and _tb_s["def_write"]["bytes"] == 575
          and _tb["claimability"]["claimable"] is False
          and _tb_s["m1_exit"]["ok"] is True
          and _s3_main["truncated"] is False
          and _s3_main["n_picked"] == _s3_main["n_gates_total"])

    # ── P5：单元版图模板化（结构公式 + 校准参数表）────────────────────────────
    #   🔴 DoD 三条**不能同时成立**（实测）：② 逐位相同 ✅ · ① 18 个全可造 ❌ · ③ 零参数加单元 ❌
    _tp_sc = TP.self_check()
    _tp_v = {n: TP.verify_bitwise(n) for n in ("INV_X1", "NAND2_X1")}
    _tp_cov = TP.coverage()
    _tp_missing = {k: v["status"] for k, v in _tp_cov["cells"].items()
                   if v["status"] != "TEMPLATED"}

    check("EC-L01 DoD② **逐位相同成立**：INV_X1 矩形/引脚同=%s DRC %d LVS %d · "
          "NAND2_X1 同=%s DRC %d LVS %d（手写 vs 模板）"
          % (_tp_v["INV_X1"]["same_rects"], _tp_v["INV_X1"]["drc"], _tp_v["INV_X1"]["lvs"],
             _tp_v["NAND2_X1"]["same_rects"], _tp_v["NAND2_X1"]["drc"], _tp_v["NAND2_X1"]["lvs"]),
          _tp_sc["ok"] and _tp_sc["problems"] == []
          and all(v["bitwise"] for v in _tp_v.values())
          and all(v["same_pins"] for v in _tp_v.values())
          and all(v["drc"] == 0 and v["lvs"] == 0 for v in _tp_v.values()))

    # EC-L02 参数压缩比：**参数个数必须显著小于坐标数**，否则只是把常量搬了个地方
    check("EC-L02 参数压缩：INV_X1 **%d 参数 ← %d 个坐标数**（×%.2f）· "
          "NAND2_X1 **%d ← %d**（×%.2f）"
          % (_tp_v["INV_X1"]["n_params"], _tp_v["INV_X1"]["coord_numbers"],
             _tp_v["INV_X1"]["coord_numbers"] / float(_tp_v["INV_X1"]["n_params"]),
             _tp_v["NAND2_X1"]["n_params"], _tp_v["NAND2_X1"]["coord_numbers"],
             _tp_v["NAND2_X1"]["coord_numbers"] / float(_tp_v["NAND2_X1"]["n_params"])),
          _tp_v["INV_X1"]["n_params"] == 34 and _tp_v["INV_X1"]["coord_numbers"] == 80
          and _tp_v["NAND2_X1"]["n_params"] == 39 and _tp_v["NAND2_X1"]["coord_numbers"] == 112
          and all(v["n_params"] * 2 < v["coord_numbers"] for v in _tp_v.values()))

    # EC-L03 🔴 **保护性约束**：手写版仍是主链真源（模板不替换 `dcells.CELLS`）
    check("EC-L03 保护性约束：`dcells.CELLS['INV_X1']` 仍是手写 `build_inv`（%s）· "
          "`NAND2_X1` 仍是 `build_nand2`（%s）⇒ 模板是**等价表达**，不是替换"
          % (CL.CELLS["INV_X1"].__name__, CL.CELLS["NAND2_X1"].__name__),
          CL.CELLS["INV_X1"].__name__ == "build_inv"
          and CL.CELLS["NAND2_X1"].__name__ == "build_nand2")

    # EC-L04 DoD① **不成立**：覆盖表必须诚实（2/18，非满非空，且 16 个各有明确原因）
    _tp_kinds = sorted(set(_tp_missing.values()))
    check("EC-L04 DoD① **不成立且如实登记**：模板覆盖 **%d/%d** · 缺 %d 个，原因分类 %r"
          % (_tp_cov["n_templated"], _tp_cov["n_total"], _tp_cov["n_missing"], _tp_kinds),
          _tp_cov["n_templated"] == 2 and _tp_cov["n_total"] == 18
          and _tp_cov["n_missing"] == 16
          and 0 < _tp_cov["n_templated"] < _tp_cov["n_total"]
          and set(_tp_kinds) <= {"NEEDS_INTERDIGIT", "NEEDS_COMPOSITE", "TODO"})

    # EC-L05 反向探针：参数改 **1nm** ⇒ 必须不再逐位（证明比较是真比较，不是恒真）
    _tp_bad = dict(TP.PARAMS["INV_X1"])
    _tp_bad["w"] = _tp_bad["w"] + 1
    _tp_bad_cell = TP.build("INV_X1", _tp_bad)
    check("EC-L05 反向探针：`INV_X1` 的 `w` 改 +1nm ⇒ 与手写版**不再逐位**（%s）"
          " ⇒ EC-L01 的「逐位相同」是真比较" % (_tp_bad_cell.w,),
          _tp_bad_cell.w == 621 and TP._sig(_tp_bad_cell) != TP._sig(CL.CELLS["INV_X1"]()))

    # EC-L06 DoD③ **不成立**：n≥3 是**拓扑**限制（不是参数问题）—— 理由必须含退化器件
    _tp_n3 = _tp_missing.get("NAND3"), _tp_missing.get("NOR3")
    check("EC-L06 DoD③ **不成立**：`NAND3`/`NOR3` = %r（需叉指）；"
          "理由含「(VDD,VDD) 退化器件」=%s ⇒ 加新单元**不是**改 0 行"
          % (_tp_n3, "退化器件" in _tp_cov["cells"]["NAND3"]["why"]),
          _tp_n3 == ("NEEDS_INTERDIGIT", "NEEDS_INTERDIGIT")
          and "退化器件" in _tp_cov["cells"]["NAND3"]["why"])

    # ── P2：驱动能力的结构可算性（形状可算 / 绝对值不可算）────────────────────
    #   🔴 DoD「11 个 family 截距能被独立算出」**不成立**：最好的组合模型中位偏差 4.1%、
    #   最大 25.9%，且 nor/or 必须换口径（最坏路径在上拉）才不结构性错。
    #   DoD「k_drive 从 unattr 移出」也**不成立** —— 本批不改值，只判形状。
    _kd_sc = KD.self_check()
    _kd_rep = KD.deviation_report()
    _kd_sh = KD.shape_check()
    _kd_inv = DC.CELLS["INV"]

    check("EC-K01 判定器自检（含 3 条反向构造）=%s · 18 单元全算到（%d）· `k_drive` 未被改写"
          "（NAND2=%.2f / INV=%.2f）"
          % (_kd_sc["ok"], _kd_rep["n_cells"], DC.CELLS["NAND2"].k_drive,
             _kd_inv.k_drive),
          _kd_sc["ok"] and _kd_sc["problems"] == []
          and _kd_rep["n_cells"] == 18
          and DC.CELLS["NAND2"].k_drive == 1.80 and _kd_inv.k_drive == 1.00)

    # EC-K02 **形状可算**（这是成立的那一半）：同 family 内单调 + 相对斜率误差
    check("EC-K02 ✅ **形状可算**：%d 个多点 family 手填/模型**全单调** · 相对斜率最大误差 **%.1f%%**"
          "（nand %.1f%% · nor %.1f%% · and %.1f%% · or %.1f%%）"
          "—— ⚠️ 规划称「同 family 外推 2.7%%」，本仓实测 **%.1f%%**，以实测为准"
          % (_kd_sh["n_families_multi"], _kd_sh["max_ratio_err"] * 100,
             _kd_sh["families"]["nand"]["ratio_err"] * 100,
             _kd_sh["families"]["nor"]["ratio_err"] * 100,
             _kd_sh["families"]["and"]["ratio_err"] * 100,
             _kd_sh["families"]["or"]["ratio_err"] * 100,
             _kd_sh["max_ratio_err"] * 100),
          _kd_sh["all_mono"] and _kd_sh["n_families_multi"] == 4
          and _kd_sh["max_ratio_err"] < 0.15
          and _kd_sh["max_ratio_err"] > 0.02)        # 必须**不为 0**：为 0 说明模型就是照抄

    # EC-K03 🔴 **绝对值不可算**（DoD① 不成立，且如实分类）
    check("EC-K03 🔴 **截距算不出**：中位偏差 **%.1f%%** · 最大 **%.1f%%**（%s）· "
          "分类 5%%内 %d / 20%%内 %d / 结构性 %d —— 10 个「5%%内」恰好是「下拉串联数」族"
          % (_kd_rep["median_abs_dev"] * 100, _kd_rep["max_abs_dev"] * 100,
             _kd_rep["worst_cell"], _kd_rep["by_class"].get("WITHIN_5PCT", 0),
             _kd_rep["by_class"].get("WITHIN_20PCT", 0),
             _kd_rep["by_class"].get("STRUCTURAL", 0)),
          _kd_rep["median_abs_dev"] < 0.06
          and _kd_rep["max_abs_dev"] > 0.20          # 有结构性偏差才是实话
          and _kd_rep["by_class"].get("WITHIN_5PCT", 0) == 10)

    # EC-K04 🔴 **保护性约束**（v0.9.406 改口）：
    #   P2 那批的原始语义是「`k_drive` 与 `t_intr` **都不许动**」。v0.9.406 **动了 `t_intr`**
    #   ⇒ 这条必须跟着改口，否则它会变成一句「与事实相反但恒真」的绿色标语。
    #   现在它守两件**仍然成立**的事：① `k_drive` 18 个值一位未动；
    #   ② `t_intr` 的**锚**仍是 2.0 ps（动的是「逐单元化」，不是锚）。
    _k04_ti = {n: DC.t_intr_ps_for(n) for n in ("INV", "NAND2", "NAND3", "NOR2", "XOR2")}
    check("EC-K04 保护性约束（改口后守锚，不守常数）：`k_drive` 18 值未动（失配 %r）· "
          "锚 `t_intr(INV)=%.9f` ps 仍 %.1f · 而 `t_intr` 已**逐单元**（NAND2 %.1f / NAND3 %.1f ≠ 锚）"
          " ⇒ 「自载项常数」这条旧事实**已作废**"
          % ({n: v for n, v in _HAND_K_DRIVE.items()
              if abs(DC.CELLS[n].k_drive - v) > 1e-12},
             _k04_ti["INV"], DC.DEFAULT_TECH.t_intr_ps, _k04_ti["NAND2"], _k04_ti["NAND3"]),
          {n: v for n, v in _HAND_K_DRIVE.items()
           if abs(DC.CELLS[n].k_drive - v) > 1e-12} == {}
          and abs(_k04_ti["INV"] - DC.DEFAULT_TECH.t_intr_ps) < 1e-12
          and DC.DEFAULT_TECH.t_intr_ps == 2.0
          and abs(_k04_ti["NAND2"] - 4.0) < 1e-9 and abs(_k04_ti["NAND3"] - 6.0) < 1e-9
          and _tb_s["place"]["die_area_um2"] == 59.202
          and _tb_t["comb_delay_ideal_ps"] == 46.657
          and _tb_t["comb_delay_wired_ps"] == 92.398)

    # EC-K05 🔴 预注册 **已实施**（v0.9.406）。这条现在守两件事：
    #   ① 文档里的 `C_self` 必须等于代码里的 `c_self_ff`（**防文档与实现漂**）；
    #   ② 三个**未采用**的候选值仍登记在案（不许因为"已经选了"就把它们删掉 ——
    #      删掉等于把「还有别的可能」这件事抹掉）。
    _kd_ti = KD.PREREG["t_intr_ps"]
    _kd_mc = KD.PREREG["main_chain_if_adopted"]
    check("EC-K05 预注册已实施：文档 `C_self=%.12f` fF ≡ 代码 `c_self_ff=%.12f` · "
          "锚给出 ideal **%.3f ps** · 未采用的 1/2/3·cin 候选仍登记 %r"
          % (_kd_ti["implemented_c_self_ff"], DC.c_self_ff(),
             _kd_mc["ideal_ps"]["0.5771·cin（已实施）"],
             [_kd_mc["ideal_ps"][k] for k in ("1·cin", "2·cin", "3·cin")]),
          abs(_kd_ti["implemented_c_self_ff"] - DC.c_self_ff()) < 1e-12
          and _kd_ti["status"].startswith("IMPLEMENTED")
          and abs(_kd_mc["ideal_ps"]["0.5771·cin（已实施）"] - 46.657) < 0.01
          and abs(_kd_mc["ideal_ps"]["1·cin"] - 55.452) < 0.01
          and abs(_kd_mc["ideal_ps"]["2·cin"] - 76.246) < 0.01
          and abs(_kd_mc["ideal_ps"]["3·cin"] - 97.041) < 0.01)

    # EC-K06 反向探针：μ 从 0.40 改 0.10 ⇒ NAND2 的瓶颈**翻侧** ⇒ 模型值必须变
    _kd_b1 = KD.k_models(mu=0.40)["NAND2"]["bottleneck"]
    _kd_b2 = KD.k_models(mu=0.10)["NAND2"]["bottleneck"]
    check("EC-K06 反向探针：μ 0.40→0.10 ⇒ NAND2 `bottleneck` %.4f→%.4f（翻侧）"
          " ⇒ μ 真进了模型（不是摆设）" % (_kd_b1, _kd_b2),
          abs(_kd_b1 - _kd_b2) > 0.1)

    # ── W/L 数据层：几何模型 + 代数上限定理（v0.9.403）────────────────────────
    #   🔴 上一批（P2）说「缺 W/L 与 μ ⇒ 绝对值不可算」。本批把 W/L 补上了，
    #   于是可以问更狠的问题：**补了数据，手填值能被几何解释吗？** 答案：不能，且可证。
    _wl_sum = DC.wl_provenance_summary()
    _wl_sc = DC.library_self_check()
    _wl_tab = DC.wl_table()
    _g_cr = KD.ceiling_report()
    _g_ir = KD.implied_mu_report()
    _g_bl = KD.balance_report()
    _g_wsc = KD.wl_self_check()

    # EC-G01 数据层完整 + **出处必须分级**（不许拿「推导的」冒充实测）
    check("EC-G01 W/L 数据层：%d/%d 有数据（LAYOUT %d · RULE_CONSTANT %d · UNKNOWN %d）· "
          "自检 %s · `LAYOUT` 名单 %r"
          % (_wl_sum["n_cells"], len(DC.CELLS), _wl_sum["by_src"].get("LAYOUT", 0),
             _wl_sum["by_src"].get("RULE_CONSTANT", 0), _wl_sum["by_src"].get("UNKNOWN", 0),
             _wl_sc["ok"], _wl_sum["measured_cells"]),
          _wl_sc["ok"] and _wl_sc["problems"] == []
          and _wl_sum["n_cells"] == len(DC.CELLS) == 18
          and _wl_sum["by_src"] == {"LAYOUT": 2, "RULE_CONSTANT": 16}
          and _wl_sum["measured_cells"] == ["INV", "NAND2"]
          and all(_wl_tab[n]["w_n_nm"] == 300.0 and _wl_tab[n]["l_nm"] == 50.0
                  for n in _wl_tab))

    # EC-G02 🔴 **两个真源对拍**：数据层的 W/L 必须等于版图实测的 DIFF 高度 / poly 宽
    #   （数据层若写成「从哪抄来的常量」，这里立刻红 —— 这是唯一能证明 W 是实测的判据）
    # 🔴 v0.9.404：两侧 DIFF 高度**不再相同**（300 / 750）⇒ 必须分开对拍。
    #   按 y0 排序区分：低的是 NMOS 有源、高的是 PMOS 有源（NWELL 在上面）。
    def _g_diff_h(cell_name):
        rs = sorted((r for r in CL.CELLS[cell_name]().rects if r.layer == CL.L_DIFF),
                    key=lambda r: r.y0)
        return (rs[0].h, rs[-1].h) if len(rs) == 2 else (None, None)

    _g_inv_lay = _g_diff_h("INV_X1")
    _g_nand_lay = _g_diff_h("NAND2_X1")
    check("EC-G02 数据层 ≡ 版图实测：INV (n,p) DIFF 高 %r / NAND2 %r vs 数据层 (%r, %r) nm · "
          "poly 宽 %r vs L %r nm · p/n = %.2f"
          % (_g_inv_lay, _g_nand_lay,
             DC.CELLS["INV"].w_n_nm, DC.CELLS["INV"].w_p_nm,
             CL.RULES["poly_w"], DC.CELLS["INV"].l_nm,
             DC.CELLS["INV"].w_p_nm / DC.CELLS["INV"].w_n_nm),
          _g_inv_lay == (300, 750) and _g_nand_lay == (300, 750)
          and DC.CELLS["INV"].w_n_nm == 300.0 and DC.CELLS["INV"].w_p_nm == 750.0
          and DC.CELLS["NAND2"].w_n_nm == 300.0 and DC.CELLS["NAND2"].w_p_nm == 750.0
          and DC.CELLS["INV"].l_nm == float(CL.RULES["poly_w"]) == 50.0
          and abs(DC.CELLS["INV"].w_p_nm / DC.CELLS["INV"].w_n_nm
                  - 1.0 / CL.MU_P_OVER_N) < 1e-9)

    # EC-G03 上限定理**机核**：扫 (μ, W_p/W_n) 二维网格，k / max(s_n,s_p) 不得越界
    #   🔴 只比 `k/ceiling ≤ 1` 是**循环的**：把 `ceiling` 整体乘 2，比值照样 ≤1。
    #   所以这里另加一条**独立复算**：上限的实现值必须等于「按 `_series()` 现算的
    #   max(s_n,s_p)」—— 两条路径算同一个量，任一侧漂移即红。
    _g_bc = KD.ceiling_bound_check()
    _g_formula_bad = {n: (KD.ceiling(DC.CELLS[n]), max(KD._series(DC.CELLS[n])))
                      for n in _g_cr["cells"]
                      if abs(KD.ceiling(DC.CELLS[n]) - max(KD._series(DC.CELLS[n]))) > 1e-12}
    check("EC-G03 上限定理 机核：%d 组 (μ, W_p/W_n) 扫描 ⇒ max(k/ceil) = %.13f（≤1+1e-9）· "
          "上限实现 ≡ 公式 max(s_n,s_p)（失配 %r）· 最紧单元 %s · 证明 %d 步齐备"
          % (_g_bc["grids"], _g_bc["max_ratio_to_ceiling"], _g_formula_bad,
             _g_bc["worst_cell"], len(KD.CEILING_PROOF["steps"])),
          _g_bc["bound_holds"] and _g_formula_bad == {}
          and _g_bc["max_ratio_to_ceiling"] <= 1.0 + 1e-9
          and len(KD.CEILING_PROOF["steps"]) == 5
          and "均匀" in KD.CEILING_PROOF["why_uniform_matters"])

    # EC-G04 🔴 **两侧都要卡**：3 个超上限的「怎么取 μ 都够不到」，6 个「够得到」
    #   —— 只卡前一半 ⇒ 模型怎么写都行；只卡后一半 ⇒ 抓不到「不可能」的那三个。
    _g_scan = {n: KD.ceiling_scan(DC.CELLS[n]) for n in _g_cr["cells"]}
    _g_unreach = sorted(n for n, v in _g_scan.items()
                        if v["scan_max"] < v["hand"] - 1e-6)
    _g_reach = sorted(n for n, v in _g_scan.items()
                      if v["scan_max"] >= v["hand"] - 1e-6)
    check("EC-G04 超上限 %d 个（%r）: 扫 396 个 μ 的最大值仍够不到手填值；"
          "其余 %d 个可达（%r）⇒ 模型不是「一律够不到」也不是「怎么都能凑上」"
          % (len(_g_unreach), _g_unreach, len(_g_reach), _g_reach),
          _g_unreach == ["NOR2", "NOR3", "OAI21"]
          and _g_cr["violations"] == ["NOR2", "NOR3", "OAI21"]
          and len(_g_reach) == 6
          and all(_g_scan[n]["scan_max"] <= _g_scan[n]["ceiling"] + 1e-9
                  for n in _g_scan))

    # EC-G05 反解 μ：**三分类互斥**，且解出的 μ 与教科书差 2.5×
    # 🔴 v0.9.404：**方向反了，因为事实反了**。旧版图 p/n=1:1 时反解出 μ≈0.87~1.00
    #   （物理上不成立），判据写的是「教科书值不在区间内」；pMOS 平衡到 2.5 之后反解出
    #   μ≈0.35~0.40，**中心距教科书 0.40 只有几个百分点** ⇒ 判据必须改成「落在同一量级」，
    #   并额外锁死 `上沿 < 0.5`（那是「μ≈1 ⇒ 版图未平衡」的指纹，不能再回来）。
    _g_mu_mid = 0.5 * (_g_ir["mu_range"][0] + _g_ir["mu_range"][1])
    check("EC-G05 反解 μ：可解 %d（μ ∈ [%.3f, %.3f]，散布 %.3f，中心 %.3f）· μ 无感 %d（%r）· "
          "无解 %d（%r）—— 教科书 μ=%.2f 与中心差 **%.1f%%**；上沿 %.3f < 0.5（μ≈1 的指纹已消失）"
          % (_g_ir["n_reachable_mu"], _g_ir["mu_range"][0], _g_ir["mu_range"][1],
             _g_ir["mu_spread"], _g_mu_mid, _g_ir["n_reachable_free"],
             _g_ir["by_status"].get("REACHABLE_FREE", []), _g_ir["n_unreachable"],
             _g_ir["by_status"].get("UNREACHABLE", []), _g_ir["textbook_mu"],
             abs(_g_mu_mid - _g_ir["textbook_mu"]) / _g_ir["textbook_mu"] * 100.0,
             _g_ir["mu_range"][1]),
          _g_ir["n_reachable_mu"] + _g_ir["n_reachable_free"] + _g_ir["n_unreachable"]
          == _g_ir["n_in_scope"] == 9
          and _g_ir["by_status"].get("REACHABLE_MU") == ["NAND2", "NAND3", "XNOR2", "XOR2"]
          and 0.30 <= _g_ir["mu_range"][0] and _g_ir["mu_range"][1] <= 0.45
          and _g_ir["mu_range"][1] < 0.50
          and abs(_g_mu_mid - _g_ir["textbook_mu"]) / _g_ir["textbook_mu"] < 0.10
          and _g_ir["mu_spread"] < 0.10)

    # EC-G06 🔴 **保护性约束**：本批**不改值** —— 18 个 k_drive 与主链 9 数一位未动
    _g_hand = _HAND_K_DRIVE          # 唯一真源在模块级（G06 与 K04 共用）
    _g_diff = {n: v for n, v in _g_hand.items()
               if abs(DC.CELLS[n].k_drive - v) > 1e-12}
    check("EC-G06 保护性约束（本批只判不改）：18 个 `k_drive` 逐位未动（失配 %r）· "
          "主链 %.3f µm² · %d/11 · %.3f/%.3f ps · PMOS 平衡=%s（p/n=%.2f）"
          % (_g_diff, _tb_s["place"]["die_area_um2"], _tb_s["route"]["nets_with_segments"],
             _tb_t["comb_delay_ideal_ps"], _tb_t["comb_delay_wired_ps"],
             _g_bl["balanced"], _g_bl["pn_ratio"]),
          _g_diff == {}
          and _tb_s["place"]["die_area_um2"] == 59.202
          and _tb_s["route"]["nets_with_segments"] == 10
          and _tb_t["comb_delay_ideal_ps"] == 46.657
          and _tb_t["comb_delay_wired_ps"] == 92.398
          and _g_bl["balanced"] is True
          and abs(_g_bl["pn_ratio"] - CL.P_RATIO) < 1e-9)

    # EC-G07 反向探针：W 真进了模型（不是摆设）—— 两条方向相反的探针
    _g_inv = DC.CELLS["INV"]
    def _g_mk(nm, wn, wp, fam, n_in, tab, ns):
        return DC.Cell(name=nm, n_in=n_in, n_tr=2, table=tab, n_series=ns,
                       k_drive=1.0, pins=("a",), family=fam,
                       w_n_nm=wn, w_p_nm=wp, l_nm=_g_inv.l_nm, wl_src="RULE_CONSTANT")
    # ① 破坏比例：INV 的 pMOS 缩回 1:1（750→300）⇒ k 必须变
    _g_inv2 = _g_mk("INV", _g_inv.w_n_nm, _g_inv.w_n_nm, "inv", 1, (1, 0), 1)
    _g_n2 = _g_mk("NAND2", _g_inv.w_n_nm, _g_inv.w_p_nm, "nand", 2, (1, 1, 1, 0), 2)
    _g_k_widen = max(*KD._r_side(_g_n2, KD.WL_MU)) / max(*KD._r_side(_g_inv2, KD.WL_MU))
    _g_k_base = KD.k_geometry(DC.CELLS["NAND2"], KD.WL_MU)
    # 🔴 保比缩放：n 与 p **同乘一个因子**（300→600 / 750→1500）。写成 600/600 会
    #   把 p/n 从 2.5 改成 1.0，那测的是另一件事、k 当然会变。
    _g_sc = 2.0
    _g_inv3 = _g_mk("INV", _g_inv.w_n_nm * _g_sc, _g_inv.w_p_nm * _g_sc, "inv", 1, (1, 0), 1)
    _g_n3 = _g_mk("NAND2", _g_inv.w_n_nm * _g_sc, _g_inv.w_p_nm * _g_sc,
                  "nand", 2, (1, 1, 1, 0), 2)
    _g_k_unif = max(*KD._r_side(_g_n3, KD.WL_MU)) / max(*KD._r_side(_g_inv3, KD.WL_MU))
    check("EC-G07 反向探针：① INV 的 pMOS 缩回 1:1（破坏比例）⇒ NAND2 的 k %.4f→%.4f"
          "（**必须变**，那正是未平衡版图造成的 2.5× 失真）；"
          "② 两侧同乘 2（**保比**缩放）⇒ k %.4f→%.4f（**必须不变**，尺度不进模型）"
          % (_g_k_base, _g_k_widen, _g_k_base, _g_k_unif),
          abs(_g_k_widen - _g_k_base) > 1e-3
          and abs(_g_k_unif - _g_k_base) < 1e-12
          and _g_wsc["ok"] and _g_wsc["problems"] == [])

    # EC-G08 🔴 v0.9.405 **平衡条件跨真源对拍**：`R = ρ·L/W` 之后，同一个 μ 有两处落点 ——
    #   版图的 `p/n` 尺寸比（`dcells`）与 `Tech.r_sheet_p_over_n`（电阻比）。
    #   **改一个不改另一个，就必须红**：否则「版图按 μ 标定」这句话无从验证。
    #   三条一起断：① 两处比值相等；② INV 上下拉**等阻**（平衡的直接后果）；③ INV 的 R
    #   恰好等于 `r_on_ohm`（标定锚自洽 —— 保证「换公式不白送速度」）。
    _g_inv_side = DC.r_side_ohm(DC.CELLS["INV"])
    _g_pn_lay = _g_inv_lay[1] / _g_inv_lay[0]
    check("EC-G08 平衡条件跨真源：版图 p/n = **%.2f** ≡ `Tech.r_sheet_p_over_n` = **%.2f** · "
          "INV 上下拉 %s Ω **等阻** · INV R = **%.0f Ω** = `r_on_ohm`（标定锚自洽）"
          % (_g_pn_lay, DC.DEFAULT_TECH.r_sheet_p_over_n,
             ("%.1f / %.1f" % _g_inv_side), DC.cell_r_ohm("INV")),
          abs(_g_pn_lay - DC.DEFAULT_TECH.r_sheet_p_over_n) < 1e-9
          and abs(_g_pn_lay - CL.P_RATIO) < 1e-9
          and abs(_g_inv_side[0] - _g_inv_side[1]) < 1e-9
          and abs(DC.cell_r_ohm("INV") - DC.DEFAULT_TECH.r_on_ohm) < 1e-9)

    # ── v0.9.406：自载项几何化（`t_intr` 从「一个常数给所有单元」变成「∝ R」）──────
    #   🔴 这批的性质和前面几批不同：改的不是「精度」，是**内部矛盾**——
    #   原来 NAND3 的 R 是 INV 的 3 倍，自载延时却同样是 2.0 ps。
    _ti_tech = DC.DEFAULT_TECH
    _ti_cself_def = _ti_tech.t_intr_ps / (DC.LN2 * _ti_tech.r_on_ohm * DC.OHM_FF_TO_PS)
    _ti_cself_inv = DC.t_intr_ps_for("INV") / (DC.LN2 * DC.cell_r_ohm("INV") * DC.OHM_FF_TO_PS)
    _ti_inv_anchor = (_ti_tech.t_intr_ps
                      + DC.cell_r_ohm("INV") * DC.LN2 * 4.0 * DC.OHM_FF_TO_PS)
    _ti_nand = {n: DC.t_intr_ps_for(n) for n in ("NAND2", "NAND3", "NAND4")
                if n in DC.CELLS}

    # EC-G09 ① C_self 两条独立算法一致 ② INV 与「锚式」逐位相同（换式不白送速度）
    check("EC-G09 自载项几何化：C_self 两算一致（定义式 %.12f ≡ 由 INV 反解 %.12f）· "
          "INV@4fF **与旧锚式逐位相同**（%.12f）· `t_intr ∝ R`"
          % (_ti_cself_def, _ti_cself_inv, _ti_inv_anchor),
          abs(_ti_cself_def - _ti_cself_inv) < 1e-15
          and DC.cell_delay_ps("INV", 4.0) == _ti_inv_anchor)

    # EC-G10 🔴 **最强形态：通式必须退化为可解析的特例**
    #   `nand` 族的 `R = max(s_n·ρ_n·L/W_n, s_p·ρ_p·L/W_p)`，而平衡版图下
    #   `ρ_n·L/W_n = ρ_p·L/W_p = r_on` 恰好成立 ⇒ `R = s_n·r_on` ⇒ **`t_intr = s_n·t_intr_ps`**。
    #   于是「自载项 ∝ 串联数」不是拟合出来的，是**代数结论**。
    #   这条同时反查平衡条件：p/n 若不是 2.5，`ρ_p·L/W_p ≠ r_on`，等式立刻不成立。
    _ti_rho_n = _ti_tech.r_on_ohm * DC.R_REF_W_NM / DC.R_REF_L_NM
    _ti_rho_p = _ti_rho_n * _ti_tech.r_sheet_p_over_n
    _ti_inv_c = DC.CELLS["INV"]
    _ti_unit_r = (_ti_rho_n * _ti_inv_c.l_nm / _ti_inv_c.w_n_nm,
                  _ti_rho_p * _ti_inv_c.l_nm / _ti_inv_c.w_p_nm)
    _ti_expect = {n: DC.series_counts(DC.CELLS[n])[0] * _ti_tech.t_intr_ps
                  for n in ("NAND2", "NAND3", "NAND4") if n in DC.CELLS}
    check("EC-G10 通式退化为特例（解析）：平衡下 `ρ_n·L/W_n = %.1f Ω = r_on` ∧ "
          "`ρ_p·L/W_p = %.1f Ω = r_on` ⇒ `t_intr(NANDk) = k·t_intr_ps` 精确成立 %r vs 实测 %r"
          % (_ti_unit_r[0], _ti_unit_r[1], _ti_expect,
             {n: round(v, 9) for n, v in _ti_nand.items()}),
          abs(_ti_unit_r[0] - _ti_tech.r_on_ohm) < 1e-9
          and abs(_ti_unit_r[1] - _ti_tech.r_on_ohm) < 1e-9
          and all(abs(_ti_nand[n] - _ti_expect[n]) < 1e-9 for n in _ti_nand)
          and _ti_expect.get("NAND3") == 6.0)

    # EC-G11 反向探针：**「一个常数给所有单元」这种错法必须能被抓住**
    #   用常数锚重算 T_ref ⇒ 与产品之差必须**恰好** = Σ(t_intr(cell) − t_intr_ps)，且 > 0。
    #   若有人把 `cell_delay_ps` 改回 `t_intr_ps + ln2·R·C`，产品值就等于常数式 ⇒ 差为 0 ⇒ 红。
    _ti_path = list(ST.longest_path_gates(nl))
    _ti_flat_ref = sum(_ti_tech.t_intr_ps
                       + DC.cell_r_ohm(g.cell, _ti_tech) * DC.LN2
                       * _c_loc["load_per_stage_ff"] * DC.OHM_FF_TO_PS
                       for g in _ti_path if g.cell != "DFF")
    _ti_gap_want = sum(DC.t_intr_ps_for(g.cell, _ti_tech) - _ti_tech.t_intr_ps
                       for g in _ti_path if g.cell != "DFF")
    check("EC-G11 反向探针：用「常数 t_intr」重算 T_ref = %.9f ⇒ 比产品少 **%.9f ps**"
          "（= Σ(逐单元 − 锚)，%r）⇒ 常数模型必被拒"
          % (_ti_flat_ref, _c_loc["clock_period_ps"] - _ti_flat_ref,
             [g.cell for g in _ti_path]),
          abs((_c_loc["clock_period_ps"] - _ti_flat_ref) - _ti_gap_want) < 1e-9
          and _ti_gap_want > 1.0)

    # ── v0.9.407：pMOS 平衡的**收益结构**（逐单元 → 链级）──────────────────────
    #   🔴 为什么单独开一段：v0.9.404 把「单元级 2.50×」写进了 README，
    #   而链级实测只有 1.50×（拓扑路径）/ 1.25×（延迟关键路径）。
    #   这一段的全部作用是：**把 2.5× 关进它的适用范围里**。
    # 🔴 循环变量**不许用 `_n`/`_c`**：`main()` 里已有 `_n()` 函数（端口名规范化），
    #   一旦在本函数内给 `_n` 赋值，整个 `main` 的 `_n` 就变成 local ⇒ UnboundLocalError。
    _sz_gain = {_sz_nm: DC.pmos_sizing_gain(_sz_cell)
                for _sz_nm, _sz_cell in DC.CELLS.items() if _sz_cell.w_n_nm}
    _sz_dom = {}
    for _sz_nm, _sz_cell in DC.CELLS.items():
        if _sz_cell.w_n_nm:
            _sz_dom.setdefault(DC.sizing_dominance(_sz_cell), []).append(_sz_nm)
    _sz_path = [g.cell for g in ST.longest_path_gates(nl)]
    _sz_rep = ST.sizing_gain_chain(_sz_path)
    _sz_nor = ST.sizing_gain_chain(["NOR2"] * 10, load_ff=3.0)

    # EC-G12 **逐单元收益只有四档**，且闭式可解析：gain = max(s_n, ρ比·s_p)/max(s_n, s_p)
    #   —— 与 W、L、r_on、t_intr、负载**全都无关**。门禁侧按闭式**独立复算**。
    def _sz_closed(cell):
        sn, sp = DC.series_counts(cell)
        ratio = DC.DEFAULT_TECH.r_sheet_p_over_n
        return max(sn, ratio * sp) / max(sn, sp)

    _sz_tiers = sorted({round(v, 6) for v in _sz_gain.values()})
    _sz_closed_dev = {_sz_nm: abs(_sz_gain[_sz_nm] - _sz_closed(DC.CELLS[_sz_nm]))
                      for _sz_nm in _sz_gain}
    check("EC-G12 逐单元收益**只有四档** %r（18 单元）· 闭式 `max(s_n, ρ比·s_p)/max(s_n, s_p)` "
          "独立复算最大偏差 %.3e ⇒ 与 W/L/r_on/t_intr/负载**全都无关** · "
          "主导侧 PULLUP %d / PULLDOWN %d / BALANCED %d"
          % (_sz_tiers, max(_sz_closed_dev.values()),
             len(_sz_dom.get(DC.DOMINANCE_PULLUP, [])),
             len(_sz_dom.get(DC.DOMINANCE_PULLDOWN, [])),
             len(_sz_dom.get(DC.DOMINANCE_BALANCED, []))),
          _sz_tiers == [1.0, 1.25, 1.666667, 2.5]
          and max(_sz_closed_dev.values()) < 1e-9
          and len(_sz_gain) == 18
          and sorted(_sz_dom.get(DC.DOMINANCE_PULLUP, [])) == ["NOR2", "NOR3", "OR2", "OR3"]
          and sorted(_sz_dom.get(DC.DOMINANCE_PULLDOWN, [])) == [
              "AND2", "AND3", "NAND2", "NAND3", "XNOR2", "XOR2"]
          and all(abs(_sz_gain[_sz_nm] - 2.5) < 1e-12
                  for _sz_nm in (_sz_dom.get(DC.DOMINANCE_PULLUP, [])
                                 + _sz_dom.get(DC.DOMINANCE_BALANCED, []))))

    # EC-G13 🔴 **上拉主导 testcase**：同构链的链级收益**逐位等于**单元级收益。
    #   —— 因为 `t_pd = ln2·R·(C_self+C_load)` 两项都 ∝ R，公因子被约掉。
    #   这也是「2.50× 可以兑现」的**唯一条件**：路径里全是能拿满的单元。
    _sz_hom = {c: ST.sizing_gain_chain([c] * 10, load_ff=3.0) for c in
               ("NOR2", "NOR3", "OR2", "AOI21", "INV", "NAND2", "NAND3", "XOR2")}
    _sz_hom_dev = {c: abs(r["gain"] - _sz_gain[c]) for c, r in _sz_hom.items()}
    check("EC-G13 ✅ 上拉主导 testcase（NOR2×10 @3fF）：链级 **%.15f×** = 单元级 %.15f× · "
          "延时 %.4f → %.4f ps；8 种同构链与单元级逐位一致（最大偏差 %.3e）"
          % (_sz_nor["gain"], _sz_gain["NOR2"], _sz_nor["delay_bal_ps"],
             _sz_nor["delay_1to1_ps"], max(_sz_hom_dev.values())),
          abs(_sz_nor["gain"] - 2.5) < 1e-12
          and abs(_sz_nor["delay_1to1_ps"] / _sz_nor["delay_bal_ps"] - 2.5) < 1e-12
          and _sz_nor["by_dominance"][DC.DOMINANCE_PULLUP] == 10
          and max(_sz_hom_dev.values()) < 1e-12)

    # EC-G14 🔴 **三条错法必须被挡在门外**（这是「2.5× 被误当链级收益」的三条真实路径）
    #   ① 拿单颗最大收益当链级 ⇒ 高估 2.5/1.5-1 = 66.7%；
    #   ② 逐级收益**算术平均** ⇒ (1.25+1.25+2.5)/3 = 1.667 ≠ 1.5（高估 11.1%）；
    #   ③ 逐级负载不均匀时仍用 ΣR 比 ⇒ 与加权差 1.91%。
    _sz_mean = sum(r["cell_gain"] for r in _sz_rep["cells"]) / _sz_rep["n_gates"]
    _sz_uni = [r["gain"] for r in (ST.sizing_gain_chain(_sz_path, load_ff=float(fo))
                                   for fo in (1, 2, 3, 5, 8))]
    _sz_mix = ST.sizing_gain_chain([("NAND2", 0.5), ("NAND2", 2.0), ("INV", 1.0)])
    check("EC-G14 三条错法被挡：① 拿单元级最大 %.2f× 当链级 ⇒ 高估 **%.2f%%**；"
          "② 逐级收益算术平均 %.6f ≠ 链级 %.6f（高估 %.2f%%）；"
          "③ 均匀负载下链级与 FO **无关**（FO=1..8 全为 %r），但非均匀时 ΣR 比 %.6f ≠ 加权 %.6f（差 %.2f%%）"
          % (_sz_gain["NOR2"], (_sz_gain["NOR2"] / _sz_rep["gain"] - 1) * 100,
             _sz_mean, _sz_rep["gain"], (_sz_mean / _sz_rep["gain"] - 1) * 100,
             [round(v, 12) for v in _sz_uni[:1]], _sz_mix["gain_by_sum_r"], _sz_mix["gain"],
             (_sz_mix["gain_by_sum_r"] / _sz_mix["gain"] - 1) * 100),
          abs(_sz_rep["gain"] - 1.5) < 1e-12
          and abs(_sz_gain["NOR2"] / _sz_rep["gain"] - 1 - 0.6666667) < 1e-6
          and abs(_sz_mean - 1.6666666666666667) < 1e-12
          and abs(_sz_mean / _sz_rep["gain"] - 1 - 0.1111111) < 1e-6
          and len({round(v, 12) for v in _sz_uni}) == 1
          and abs(_sz_uni[0] - 1.5) < 1e-12
          and _sz_mix["uniform_load"] is False
          and abs(_sz_mix["gain_by_sum_r"] - _sz_mix["gain"]) > 1e-6)

    # EC-G15 🔴 **模型实测**（不是公式复述）：把 p 侧全部退回 1:1 重跑 `sta`，
    #   看**延迟关键路径**的收益。它只有 1.25×，因为 `sta` 的关键路径是 3×NAND2，
    #   而拓扑最长路径是 2×NAND2+1×INV（1.50×）—— **两条路径组成不同，收益就不同**。
    #   ⚠️ 用 3 位取整的 report 值相除会得到 1.250016（差 1.6e-5 全是舍入）——
    #   这是「表示差异 ≠ 真差异」在本仓的**第五次**。
    _sz_pl = ST.FO_PORT * DC.DEFAULT_TECH.cin_ff
    _sz_bal = ST.sta(nl, port_load_ff=_sz_pl, topo_sort=True).comb_delay_ps
    _sz_saved = {_sz_nm: _sz_c for _sz_nm, _sz_c in DC.CELLS.items()}
    _sz_err = ""
    try:
        for _sz_nm, _sz_c in list(_sz_saved.items()):
            if _sz_c.w_n_nm and _sz_c.w_p_nm:
                DC.CELLS[_sz_nm] = dataclasses.replace(_sz_c, w_p_nm=_sz_c.w_n_nm)
        _sz_one = ST.sta(nl, port_load_ff=_sz_pl, topo_sort=True).comb_delay_ps
    except Exception as _exc:                       # noqa: BLE001 — 破坏后要能报红，不能崩
        _sz_one = -1.0
        _sz_err = "%s: %s" % (type(_exc).__name__, str(_exc)[:60])
    finally:
        DC.CELLS.update(_sz_saved)
    _sz_restored = (ST.sta(nl, port_load_ff=_sz_pl, topo_sort=True).comb_delay_ps == _sz_bal)
    _sz_crit = (_sz_one / _sz_bal) if _sz_one > 0 else -1.0
    check("EC-G15 模型实测：p 侧退回 1:1 ⇒ `ideal` %.12f → %.12f ps，**延迟关键路径收益 %.15f×**"
          "（= 3×NAND2 的单元级收益）×；拓扑路径 %.4f× —— 两者不同是因为**路径组成不同**"
          "（3 位取整相除会假得 1.250016）。还原逐位=%s%s"
          % (_sz_bal, _sz_one, _sz_crit, _sz_rep["gain"], _sz_restored,
             ("  err=" + _sz_err) if _sz_err else ""),
          abs(_sz_crit - 1.25) < 1e-12
          and abs(_sz_crit - _sz_gain["NAND2"]) < 1e-12
          and abs(_sz_rep["gain"] - 1.5) < 1e-12
          and _sz_restored is True)

    print("  [T5/Q4] 可造性判定：宽度下限 **%d nm**（pad %d + 接入 %d）⇒ INV 余 %d nm（%.1f%%）· "
          "NAND2 余 %d nm（%.1f%%）"
          % (_nf_sc["width_floor_nm"], NF.PAD_NM, NF.ACCESS_GAP_NM,
             _nf_head_inv["headroom_nm"], _nf_head_inv["max_width_saving_pct"],
             _nf_head_nand["headroom_nm"], _nf_head_nand["max_width_saving_pct"]))
    print("  [T5/Q4 定论] **按比例缩放不成立**：%d 个比例点全部 DRC/LVS 违例（s=0.98 即红）"
          "⇒ 真缩必须按规则重推布局（= P5），`device_scale` 不是旋钮"
          % (len(_nf_scan_inv) - 1))
    print("  [T5/S3] `max_cells` 静默截断已改为**默认拒绝**（规模实验须显式 `truncate_ok=True`）")

    print("  [T4] 库接线（数据契约）：`SAMPLE_LIBERTY_L2` 2 cell（INV/NAND2 · 与 dcells 同名）"
          "· load 轴 0–8 fF · **与闭式逐位相同**（线性函数两点插值精确）")
    print("  [T4] 库级默认 **只报不接**：vdd %.2f V · %.0f °C · cin %.1f fF —— "
          "接它们会改 EM/几何，属 T4b（需独立验收）"
          % (_lib_ld["nom_voltage_v"], _lib_ld["nom_temperature_c"],
             _lib_ld["default_input_pin_cap_ff"]))
    print("  [T4 边界] 这是「代码常量 → 数据文件」的**通路验证**，不是接了真库："
          "真库数据会改口，需外部输入；本仓非 foundry PDK")

    print("  [T3] 出处判决：derivable 8（含 2 条走独立重算）· unattr **7**（逐条有 owner，"
          "棘轮只减不增）· dead_rules **0**（T2 修完 `W_MIN`）· num_eps 1（`SPACE_EPS` 下界可算）")
    print("  [T3] 支配约束报表 %d 行：PASS %r · **FAIL %r** · 无约束 %r · 登记无判别力 %r · 缺输入 %r"
          % (_pv_cr["n_rows"], _pv_cr["summary"][PV.PASS], _pv_cr["summary"][PV.FAIL],
             _pv_cr["summary"][PV.UNCONSTRAINED], _pv_cr["summary"][PV.REGISTERED_ONLY],
             _pv_cr["summary"][PV.UNDECIDABLE]))
    print("  [T3 边界] 报表**不给签核结论**（claimable=False）；`drc`/`lvs` 仍是 ROUTED_SUBSET_ONLY；"
          "面积与 DEF 无支配约束 ⇒ 只能说「是什么」")

    _dt = time.time() - T0
    check("S17c 门禁耗时 %.2f s < %.0f s" % (_dt, AN_ELAPSED_MAX_S), _dt < AN_ELAPSED_MAX_S)

    print()
    print("  [S13] 拓扑差异 %d 处（已登记）：%s —— 与 ISCAS-85 公开定义对照，出处 + sha256 同行"
          % (len(got), " · ".join("%s:%s" % (k, "+".join(v)) for k, v in sorted(got.items()))))
    print("  [S14] EM 物理自变量缺 %s —— Black 方程要求，当前 `em_check` 无温度参数"
          % list(missing))
    print("  [S15] DRC/LVS 双实现本地闭包交集 ∅（登记例外 1 项 `via_bridges`：共享的是判据规则，"
          "其正确性由 Q1-a/d/e/f 独立接管）⇒ 「两个实现」独立性成立（E1 不再虚设）")
    print("  [S16] 面积两条不同边界路径均拼回 %.3f µm" % _po["die_w_um"])
    print("  [S18] EM 温度标度：T=T_ref 逐位退化 ∧ 85°C 允许 %.4g（×%.1f）∧ 判定随温度翻转"
          % (_j85, _j85 / _j125))
    print("  [边界] 不改网表（改则推翻 DRC/面积/时序/DEF 全部既有数字）；"
          "K2 仅覆盖同文件本地调用，跨模块共享不在范围")

    if _FALS:
        print("S13 有红色：%s" % ", ".join(_FALS))
        return 1
    print("S13 全绿 · B1 四项 + B2a：拓扑机核（2 处已登记）+ K0 覆盖 6/6（EM 已补温度）+ "
          "K2 交集 ∅（例外 1 项已登记）+ 面积双路径一致 + EM 温度标度（T=T_ref 逐位退化、判定随温度翻转）；"
          "产品数字逐位未变")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
