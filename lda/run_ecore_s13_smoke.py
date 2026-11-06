# -*- coding: utf-8 -*-
"""S13 门禁：B1 四项零风险判据（拓扑机核 / K0 完备性 / K2 独立性 / 面积交叉分段）。

═══════════════════════════════════════════════════════════════════════════════
这一批要证明什么
───────────────────────────────────────────────────────────────────────────────
四个缺口，共同的判据是「**产品数字一位不改**」——即它们只加**观察力**，不加能力：

  B1.1 `S13a–e` **c17 拓扑机核** —— 补「理解错」这一整类（此前完全空白）
  B1.2 `S14a–c` **K0 完备性锚** —— 补「整项缺失」这一整类（此前完全空白）
  B1.3 `S15a–c` **K2 独立性机核** —— 让既有「DRC = E1」不再是虚设
  B1.4 `S16a–b` **面积交叉分段** —— 零误差量必须**换边界**切，否则共同边界错误检不出
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
#: 已登记的缺失项（与实测必须相等；补齐后本表要跟着改，否则红）
DECLARED_EM_MISSING = ("temperature", "activation_energy", "exponent")


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

    _dt = time.time() - T0
    check("S17c 门禁耗时 %.2f s < %.0f s" % (_dt, AN_ELAPSED_MAX_S), _dt < AN_ELAPSED_MAX_S)

    print()
    print("  [S13] 拓扑差异 %d 处（已登记）：%s —— 与 ISCAS-85 公开定义对照，出处 + sha256 同行"
          % (len(got), " · ".join("%s:%s" % (k, "+".join(v)) for k, v in sorted(got.items()))))
    print("  [S14] EM 物理自变量缺 %s —— Black 方程要求，当前 `em_check` 无温度参数"
          % list(missing))
    print("  [S15] DRC/LVS 双实现本地闭包交集 ∅ ⇒ 「两个实现」确有独立性（E1 不再虚设）")
    print("  [S16] 面积两条不同边界路径均拼回 %.3f µm" % _po["die_w_um"])
    print("  [边界] 不改网表（改则推翻 DRC/面积/时序/DEF 全部既有数字）；"
          "K2 仅覆盖同文件本地调用，跨模块共享不在范围")

    if _FALS:
        print("S13 有红色：%s" % ", ".join(_FALS))
        return 1
    print("S13 全绿 · B1 四项：拓扑机核（2 处已登记）+ K0 缺 3 项已声明 + K2 交集 ∅ + 面积双路径一致；"
          "产品数字逐位未变")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
