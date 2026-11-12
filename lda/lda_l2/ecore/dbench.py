# -*- coding: utf-8 -*-
"""F1 · **ISCAS-85 `.bench` 入口**（解析 → 任意扇入门型分解 → `dsynth.Netlist`）。

═══════════════════════════════════════════════════════════════════════════════
定位：给数字链补**第二种真实输入格式**（`dverilog` 吃结构 Verilog，本模块吃 `.bench`），
并把「规模真值」测量所需的门型分解做成**可复算、可穷举验证**的显式口径。

═══════════════════════════════════════════════════════════════════════════════
🔴 实现前的只读测算推翻了两条原先的假设
───────────────────────────────────────────────────────────────────────────────
① 原先设想的门型分解只覆盖 2–3 输入门，隐含「c432 主要是 2 输入门」。
   **真实 c432 有 8/9 输入 AND ×4、4 输入 NAND ×14、3 输入 NAND ×1**，
   根本没有 NOR3。按原先指定的口径分解后是 **417 门**，不是原定的 `[160,300]`。
   ⇒ 本模块支持**任意扇入**，并把门数改成「闭式精确值」验收，而不是区间。
② 阶段验收里的「布通率 ≥50% / <30%」没绑定分母与库：同一份 c432，
   主链口径 18.5–29.3% 与 E53 实验口径 60.2–73.7% 会给出**相反决策**。
   ⇒ 本模块只产出网表与度量，**不做阶段决策**；口径定义与决策由报告显式承担。

═══════════════════════════════════════════════════════════════════════════════
三种分解口径（`DECOMP_MODES`）—— 都是**同一套逻辑**、不同的库/树策略
───────────────────────────────────────────────────────────────────────────────
| 口径 | 定义 | c432 门数 |
|---|---|---|
| `A` | 只用 `NAND2 + INV`（规划原话） | **417** |
| `B` | A + 允许 v0.9.408 新增的 `NOR2` 真实版图 | **360** |
| `C` | B + NAND/NOR 交替树（省掉大部分反相器） | **300** |

🔴 三个数是**闭式可算**的（由扇入分布与分解式决定），不是拟合出来的目标值。
🔴 门数更少 ≠ 更好布：实测 C 的主链布通率反而低于 A（见 F1 报告）。

═══════════════════════════════════════════════════════════════════════════════
语料来源与诚实边界（**先不对外**）
───────────────────────────────────────────────────────────────────────────────
`data/iscas85/*.bench` 是 **ISCAS-85 公开学术基准**，经
`xkllkx/CAD_for_VLSI_Design · PA1_Benchmark Translator/bench/` 镜像取得，
行尾归一为 LF（`BENCH_SOURCE` 里记 sha256，`load_corpus` 逐字节校验）。

- 语料是**被测输入**，不是运行时依赖、不是 golden、不是 PDK、不是 foundry 数据；
- 入库后全流程**零外部工具 / 零第三方包 / 零网络调用**；
- 不对其做任何流片、性能或制造宣称；本模块不做逻辑仿真之外的物理推断。

═══════════════════════════════════════════════════════════════════════════════
两条硬保证（与 S3 `dverilog` 同款主权红线）
───────────────────────────────────────────────────────────────────────────────
① **fail-closed**：未知语法 / 未知门型 / 重复驱动 / 引用未定义网 ⇒ 抛
   `BenchSyntaxError`，绝不静默跳过或降级；
② **逻辑等价可机核**：`template_truth_check` 对每个 (门型, 扇入) 模板做 **2^k 穷举**
   （k≤9 ⇒ ≤512 组），`equivalence_report` 用两套**零共享代码路径**的引擎对拍整电路 ——
   引擎 1 是本模块的 `.bench` 直接求值，引擎 2 是产品链 `dsynth.sim_netlist`
   （逐单元查 `dcell.eval_cell` 真值表）。

⚠️ 本模块**不含判据、不含阈值、不给结论**：它只产出事实（网表 + 度量），
   判据在 `run_ecore_s13_smoke.py`，阶段决策在内部报告。这是 F0 审计脚本定下的分工。
"""
from __future__ import annotations

import hashlib
import itertools
import os
import re
from collections import Counter

from .dsynth import Gate, Netlist

# ── 语料登记表（单一真源：改语料必须改这里，否则 load_corpus 当场抛错）─────────
_ORIGIN = ("ISCAS-85 public benchmark · mirror: github.com/xkllkx/CAD_for_VLSI_Design"
           " · PA1_Benchmark Translator/bench/")
_BOUNDARY = ("公开学术基准语料，仅作被测输入；非 golden / 非 PDK / 非运行时依赖 / "
             "零网络调用 / 不作流片或性能宣称")
BENCH_SOURCE = {
    "c432": {"file": "c432.bench", "bytes": 3655,
             "sha256": "d2a0e9dcf384161ec8015c7fbbb429635b8a05edba8be00c81b2943b44ceff7b",
             "origin": _ORIGIN, "boundary": _BOUNDARY},
    "c17": {"file": "c17.bench", "bytes": 230,
            "sha256": "b3f8a6ba86c4a04b7ad9d44d8f56ebdfa8f35248cb8dd71810e39b8dac14185b",
            "origin": _ORIGIN, "boundary": _BOUNDARY},
}

DECOMP_MODES = ("A", "B", "C")
#: 分解只允许落到这三颗**有真实几何版图**的单元（v0.9.408 起含 NOR2）。
LIB_CELLS = frozenset({"INV", "NAND2", "NOR2"})
#: 每个 (门型, 扇入) 模板都要被 2^k 穷举覆盖（见 template_truth_check）。
DECOMP_TEMPLATES = (
    ("NOT", 1),
    ("NAND", 2), ("NAND", 3), ("NAND", 4), ("NAND", 8), ("NAND", 9),
    ("NOR", 2), ("NOR", 3), ("NOR", 4),
    ("AND", 2), ("AND", 3), ("AND", 4), ("AND", 8), ("AND", 9),
    ("XOR", 2), ("XOR", 3), ("XOR", 4),
)


class BenchSyntaxError(Exception):
    """`.bench` 语法/语义错误（未知语法一律抛，绝不静默降级）。"""


def load_corpus(name: str = "c432") -> str:
    """读取内置语料并**逐字节校验 sha256**（语料被改动会当场发现）。"""
    rec = BENCH_SOURCE.get(name)
    if rec is None:
        raise BenchSyntaxError("未知语料 %r；已登记=%r" % (name, sorted(BENCH_SOURCE)))
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "data", "iscas85", rec["file"])
    with open(path, "rb") as fh:
        raw = fh.read()
    if len(raw) != rec["bytes"] or hashlib.sha256(raw).hexdigest() != rec["sha256"]:
        raise BenchSyntaxError("语料 %r 与登记表不符（可能被改动）：bytes=%d sha=%s"
                               % (name, len(raw), hashlib.sha256(raw).hexdigest()))
    return raw.decode("utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# ① 解析（fail-closed）
# ═══════════════════════════════════════════════════════════════════════════
_RE_INPUT = re.compile(r"^INPUT\(\s*([A-Za-z0-9_\[\]]+)\s*\)$", re.I)
_RE_OUTPUT = re.compile(r"^OUTPUT\(\s*([A-Za-z0-9_\[\]]+)\s*\)$", re.I)
_RE_GATE = re.compile(r"^([A-Za-z0-9_\[\]]+)\s*=\s*([A-Za-z][A-Za-z0-9_]*)\s*\(([^)]*)\)$")


def parse_bench(src: str) -> dict:
    """解析 ISCAS-85 简化 `.bench` → `{inputs, outputs, gates}`。

    `gates` = `[(out_net, KIND, (in_net, ...)), ...]`，**保持源文件顺序**
    （ISCAS-85 是 levelized order；拓扑合法性另由 `dsynth.topo_order` 守）。
    """
    inputs, outputs, gates = [], [], []
    seen_nets = set()
    driven = set()
    for lineno, raw in enumerate(src.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _RE_INPUT.match(line)
        if m:
            n = m.group(1)
            if n in seen_nets:
                raise BenchSyntaxError("第 %d 行：输入网 %r 重复声明" % (lineno, n))
            seen_nets.add(n)
            inputs.append(n)
            continue
        m = _RE_OUTPUT.match(line)
        if m:
            outputs.append(m.group(1))
            continue
        m = _RE_GATE.match(line)
        if not m:
            raise BenchSyntaxError("第 %d 行：无法识别的语法 %r" % (lineno, line))
        out, kind, argtxt = m.group(1), m.group(2).upper(), m.group(3)
        args = tuple(x.strip() for x in argtxt.split(",") if x.strip())
        if not args:
            raise BenchSyntaxError("第 %d 行：门 %s 没有输入" % (lineno, out))
        if out in driven:
            raise BenchSyntaxError("第 %d 行：网 %r 被重复驱动" % (lineno, out))
        driven.add(out)
        if kind == "NOT" and len(args) != 1:
            raise BenchSyntaxError("第 %d 行：NOT 须 1 输入，得到 %d" % (lineno, len(args)))
        if kind not in ("NOT", "NAND", "NOR", "AND", "OR", "XOR", "XNOR", "BUF"):
            raise BenchSyntaxError("第 %d 行：未支持的门型 %r" % (lineno, kind))
        gates.append((out, kind, args))
    if not inputs or not outputs or not gates:
        raise BenchSyntaxError("空网表：inputs=%d outputs=%d gates=%d"
                               % (len(inputs), len(outputs), len(gates)))
    # 🔴 引用完整性：任何输入网必须是 primary input、或由**前序**门驱动（levelized）。
    known = set(inputs)
    for out, kind, args in gates:
        for a in args:
            if a not in known:
                raise BenchSyntaxError("门 %s 引用了未定义/后向的网 %r" % (out, a))
        known.add(out)
    for o in outputs:
        if o not in known:
            raise BenchSyntaxError("输出网 %r 未被任何门驱动、也不是输入" % o)
    return {"inputs": inputs, "outputs": outputs, "gates": gates}


# ═══════════════════════════════════════════════════════════════════════════
# ② 门型分解（任意扇入）
# ═══════════════════════════════════════════════════════════════════════════
class _Builder:
    """把任意扇入门展开成 `INV / NAND2 / NOR2` 的确定性序列。"""

    def __init__(self, mode: str = "A"):
        if mode not in DECOMP_MODES:
            raise BenchSyntaxError("未知分解口径 %r；可用 %r" % (mode, DECOMP_MODES))
        self.mode = mode
        self.g = []
        self.k = 0

    def _new(self):
        self.k += 1
        return "__t%d" % self.k

    def _emit(self, cell, *args):
        out = self._new()
        self.g.append((out, cell, args))
        return out

    def inv(self, x):
        return self._emit("INV", x)

    def nand2(self, a, b):
        return self._emit("NAND2", a, b)

    def nor2(self, a, b):
        if self.mode == "A":
            # 只用 NAND2+INV：NOR(x,y) = NAND2(~x, ~y) 再取反
            return self.inv(self.nand2(self.inv(a), self.inv(b)))
        return self._emit("NOR2", a, b)

    def and2(self, a, b):
        return self.inv(self.nand2(a, b))

    def or2(self, a, b):
        if self.mode == "A":
            return self.nand2(self.inv(a), self.inv(b))   # x∨y = ~(~x·~y)
        return self.inv(self.nor2(a, b))

    def _and_tree(self, args):
        """AND_k：A/B 走朴素 AND2 左折叠；C 走 NAND/NOR 交替平衡树。"""
        if self.mode != "C":
            v = args[0]
            for a in args[1:]:
                v = self.and2(v, a)
            return v

        def _and(a):
            if len(a) == 1:
                return a[0]
            if len(a) == 2:
                return self.and2(a[0], a[1])
            h = len(a) // 2
            return self._emit("NOR2", _nand(a[:h]), _nand(a[h:]))

        def _nand(a):
            if len(a) == 1:
                return self.inv(a[0])
            if len(a) == 2:
                return self.nand2(a[0], a[1])
            return self.inv(_and(a))

        return _and(args)

    def _nand_tree(self, args):
        if self.mode == "C" and len(args) >= 3:
            def _and(a):
                if len(a) == 1:
                    return a[0]
                if len(a) == 2:
                    return self.and2(a[0], a[1])
                h = len(a) // 2
                return self._emit("NOR2", _nand(a[:h]), _nand(a[h:]))

            def _nand(a):
                if len(a) == 1:
                    return self.inv(a[0])
                if len(a) == 2:
                    return self.nand2(a[0], a[1])
                return self.inv(_and(a))

            return _nand(args)
        if len(args) == 2:
            return self.nand2(args[0], args[1])
        return self.inv(self._and_tree(args))

    def _or_chain(self, args):
        v = args[0]
        for a in args[1:]:
            v = self.or2(v, a)
        return v

    def xor2(self, a, b):
        t = self.nand2(a, b)
        u = self.nand2(a, t)
        v = self.nand2(b, t)
        return self.nand2(u, v)

    def build_one(self, kind, args):
        """返回**最后一颗门**的输出网名；调用方负责把它重命名为原始输出网。"""
        if kind == "NOT":
            return self.inv(args[0])
        if kind == "NAND":
            return self._nand_tree(args)
        if kind == "NOR":
            return self.nor2(*args) if len(args) == 2 else self.inv(self._or_chain(args))
        if kind == "AND":
            return self._and_tree(args)
        if kind == "OR":
            return self._or_chain(args)
        if kind == "XOR" or kind == "XNOR":
            v = args[0]
            for a in args[1:]:
                v = self.xor2(v, a)
            return self.inv(v) if kind == "XNOR" else v
        if kind == "BUF":
            # BUF 无真实版图；两级 INV 是库内唯一等价实现
            return self.inv(self.inv(args[0]))
        raise BenchSyntaxError("未支持的门型 %r" % (kind,))


def decompose(spec: dict, mode: str = "A") -> list:
    """把 `.bench` 网表分解成 **库内单元序列** `[(out, cell, (in, ...)), ...]`。

    确定性：网名按 `__t<n>` 递增、门序按源文件顺序 ⇒ 两次调用逐字节相同。
    原始输出网名直接落到该门的最后一颗单元上（不多造一颗反相器）。
    """
    b = _Builder(mode)
    for out, kind, args in spec["gates"]:
        b.build_one(kind, args)
        _o, cell, ins = b.g[-1]
        b.g[-1] = (out, cell, ins)
    return b.g


def decompose_report(spec: dict, mode: str = "A") -> dict:
    """**只度量**：扇入分布、分解前后门数、单元直方图、内部网名数。"""
    gates = decompose(spec, mode)
    hist = Counter(c for _, c, _ in gates)
    fanin = Counter((k, len(a)) for _, k, a in spec["gates"])
    internal = {o for o, _, _ in gates if o.startswith("__t")}
    return {
        "mode": mode,
        "n_source_gates": len(spec["gates"]),
        "n_inputs": len(spec["inputs"]),
        "n_outputs": len(spec["outputs"]),
        "n_decomposed_gates": len(gates),
        "cell_hist": dict(sorted(hist.items())),
        "fanin_hist": {"%s/%d" % kv: n for kv, n in sorted(fanin.items())},
        "n_internal_nets": len(internal),
        "cells_all_in_library": all(c in LIB_CELLS for c in hist),
        "library_cells": sorted(LIB_CELLS),
    }


_RE_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def normalize_net_name(s: str) -> str:
    """`.bench` 网名 → DEF/Verilog 合法标识符（**确定性 + 单射**）。

    ISCAS-85 用纯数字作网名（`1` / `22` / `432`），而 `ddef._expect_id` 要求
    字母开头 ⇒ 不规范化会在 DEF 往返段直接抛 `DefSyntaxError`。
    非法字符用 `_<hex>_` 转义（含下划线自身），保证任意两串不会撞名。
    🔴 只改**网名标签**，`Netlist.inputs` 的端口名保持原样 ⇒
    `sim_netlist` 的 `pin` 仍用 `.bench` 原名，两套引擎对拍不受影响。
    """
    if _RE_ID.match(s):
        return s
    return "bn_" + "".join(c if c.isalnum() else "_%x_" % ord(c) for c in s)


def to_netlist(spec: dict, gates: list, name: str = None) -> Netlist:
    """分解结果 → 数字链唯一的门级容器 `dsynth.Netlist`（不含坐标）。"""
    def _n(x):
        return normalize_net_name(x)

    return Netlist(
        name=name or "bench",
        inputs=tuple((x, 1) for x in spec["inputs"]),
        in_nets={(x, 0): _n(x) for x in spec["inputs"]},
        outputs={o: (_n(o),) for o in spec["outputs"]},
        gates=[Gate(name="g%d" % i, cell=c, ins=tuple(_n(a) for a in a_list),
                    out=_n(o))
               for i, (o, c, a_list) in enumerate(gates)],
        clocks=())


# ═══════════════════════════════════════════════════════════════════════════
# ③ 逻辑等价性（**两套零共享代码路径**的引擎）
# ═══════════════════════════════════════════════════════════════════════════
def bench_eval(spec: dict, vals: dict) -> tuple:
    """引擎 1（测试侧 oracle）：直接按 `.bench` 语义求值，不经过产品网表。"""
    v = dict(vals)
    for out, kind, args in spec["gates"]:
        a = [v[x] for x in args]
        if kind == "NOT":
            v[out] = 1 - a[0]
        elif kind == "NAND":
            v[out] = 1 - (1 if all(a) else 0)
        elif kind == "NOR":
            v[out] = 1 - (1 if any(a) else 0)
        elif kind == "AND":
            v[out] = 1 if all(a) else 0
        elif kind == "OR":
            v[out] = 1 if any(a) else 0
        elif kind in ("XOR", "XNOR"):
            p = 0
            for x in a:
                p ^= x
            v[out] = p if kind == "XOR" else 1 - p
        elif kind == "BUF":
            v[out] = a[0]
        else:
            raise BenchSyntaxError(kind)
    return tuple(v[o] for o in spec["outputs"])


def _truth(kind: str, bits) -> int:
    b = list(bits)
    if kind == "NOT":
        return 1 - b[0]
    if kind == "NAND":
        return 1 - (1 if all(b) else 0)
    if kind == "NOR":
        return 1 - (1 if any(b) else 0)
    if kind == "AND":
        return 1 if all(b) else 0
    if kind == "OR":
        return 1 if any(b) else 0
    if kind in ("XOR", "XNOR"):
        p = 0
        for x in b:
            p ^= x
        return p if kind == "XOR" else 1 - p
    if kind == "BUF":
        return b[0]
    raise BenchSyntaxError(kind)


def template_truth_check(mode: str = "A") -> dict:
    """对每个 (门型, 扇入) 模板做 **2^k 全穷举**（k≤9），验分解式本身。

    这是「通式必须退化为已实现的特例」那一类最强判据的**度量面**：
    不看整电路随机向量，直接把每个模板的真值表逐行对拍。
    """
    from .dsynth import sim_netlist
    rows = []
    for kind, k in DECOMP_TEMPLATES:
        names = ["a%d" % i for i in range(k)]
        spec = {"inputs": names, "outputs": ["y"],
                "gates": [("y", kind, tuple(names))]}
        nl = to_netlist(spec, decompose(spec, mode), name="tmpl")
        bad = 0
        for bits in itertools.product((0, 1), repeat=k):
            pin = {n: b for n, b in zip(names, bits)}
            got = sim_netlist(nl, pin)["y"]
            if got != _truth(kind, bits):
                bad += 1
        rows.append({"kind": kind, "fanin": k, "n_vectors": 1 << k,
                     "mismatches": bad})
    return {"mode": mode, "n_templates": len(rows),
            "n_vectors": sum(r["n_vectors"] for r in rows),
            "mismatches": sum(r["mismatches"] for r in rows), "rows": rows}


def equivalence_report(spec: dict, gates: list, n_vectors: int = 64,
                       seed: int = 20261112) -> dict:
    """整电路对拍：产品引擎 `dsynth.sim_netlist` vs 直接 `.bench` 求值。

    ⚠️ 36 输入的 2³⁶ 不可穷举 ⇒ 这里是**随机 + 定向向量**；完备性由
    `template_truth_check` 的模板级穷举承担，两者分工不互相顶替。
    """
    import random
    from .dsynth import sim_netlist
    nl = to_netlist(spec, gates, name=spec.get("name", "bench"))
    rng = random.Random(seed)
    names = spec["inputs"]
    bad = []
    for i in range(n_vectors):
        if i == 0:
            vals = {n: 0 for n in names}
        elif i == 1:
            vals = {n: 1 for n in names}
        elif i == 2:
            vals = {n: (1 if j == 0 else 0) for j, n in enumerate(names)}
        else:
            vals = {n: rng.getrandbits(1) for n in names}
        got = tuple(sim_netlist(nl, vals)[o] for o in spec["outputs"])
        want = bench_eval(spec, vals)
        if got != want:
            bad.append({"vector": i, "got": got, "want": want})
    return {"n_vectors": n_vectors, "mismatches": len(bad),
            "examples": bad[:3], "engine_product": "dsynth.sim_netlist/dcell.eval_cell",
            "engine_oracle": "dbench.bench_eval"}
