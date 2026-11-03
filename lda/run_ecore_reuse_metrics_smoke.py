# -*- coding: utf-8 -*-
"""S5 门禁：**基础复用度量**（R1 / R2 / R3）—— 把规划 §三 的三个指标变成机器守。

═══════════════════════════════════════════════════════════════════════════════
为什么存在（血案：治病的阶段又犯了同一个病）
═══════════════════════════════════════════════════════════════════════════════
`docs/PLAN_foundation_2026-11.md` 诊断出「新能力全在孤岛上」，并定了三条可机核指标
（R1 零入度占比 / R2 入度中位 / R3 新模块首版有非门禁下游）+ 一条纪律
「每轮收尾加一次依赖图体检」。**但三个指标从未固化成门禁**，只在规划里算过一次。

结果：S1–S4 加了 6 个模块，其中 **4 个一出生就是零入度**（`dliberty`/`ddef`/`db3_trunk`/
`dxcheck`），另外 2 个的下游本身也是孤岛 ⇒ **R3 = 0/6**；零入度从 26/72 涨到 30/78。
**这正是规划 §1.2 描述的病，在「治它」的过程中又长了一遍。**

本门禁做的事：把度量**固化**（脚本入库、口径写死、每次 CI 都打印），并把「债务」变成
**冻结上限**而不是可自由增长的注释。

───────────────────────────────────────────────────────────────────────────────
口径（必须写死，否则数字之间不可比）
───────────────────────────────────────────────────────────────────────────────
· 范围：`lda_l2/ecore/*.py`（不含 `__init__.py`）
· 边：AST `ImportFrom`，兼容 ① 相对 `from .x import y` / `from . import x`
      ② 绝对 `from lda_l2.ecore.x import y` / `from lda_l2.ecore import x`
· 入度 = **引用它的不同模块数**（同模块多条 import 只算 1）
· 不统计门禁（门禁在 `lda/`，不在本图内）⇒ R3 的分母天生不含「门禁消费者」

🔴 **口径警示**：规划正文自报基线「21/72=29%、中位 2、均值 3.32」，用本脚本复算基线
（`git archive ae369fb`）得「26/72=36%、中位 1、均值 3.00」。**跨口径绝对值不可比** ——
规划 §1.5 自己就栽过一次同类口径错（62/86% → 21/29%）。所以本门禁只做**同口径**的
「不倒退」约束，不引用规划里的绝对值。

───────────────────────────────────────────────────────────────────────────────
棘轮纪律（只许收紧）
───────────────────────────────────────────────────────────────────────────────
· `ZERO_MAX` 只降不升 · `MEDIAN_MIN` 只升不降 · `GE3_MIN` 只升不降
· `ZERO_ALLOWED` 是**冻结集合**：任何模块**新**变成零入度 ⇒ 必红（删模块/改依赖忘了接回）
· `R3_DEBT` 是**冻结债务表**：精确相等才算过 ⇒ 债务缩小了必须同步删表（强制收口），
  债务变大了必红。每条债务必须写「到期里程碑 + 理由」。
· 白名单（`TOPLEVEL_ALLOW`）**登记 ≠ 免检**：必须双向完备（写了必须真的零入度）+ 理由非空。

诚实边界
────────
· 本门禁只看**静态 import 图**，看不出「import 了但从不调用」——那种空洞由
  `run_reachability_smoke`（零引用函数）与 R3 的调用点判据（后续）分担。
· 入度 0 不等于「没用」：顶层流程与注册表天然被门禁/人读。故有白名单，但白名单是
  **逐条登记 + 理由**，不是「一类全放过」。
"""
from __future__ import annotations

import ast
import os
import statistics
import time

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.smoke_kit import make_check  # noqa: E402

_FALS: list = []
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   record=_FALS)
T0 = time.time()
AN_ELAPSED_MAX_S = 30.0

_HERE = os.path.dirname(os.path.abspath(__file__))
_ECORE = os.path.join(_HERE, "lda_l2", "ecore")

# ═══════════════════════════════════════════════════════════════════════════
# 阈值与冻结表（**只许收紧**；改动此块必须在提交信息里写明「棘轮收紧」）
# ═══════════════════════════════════════════════════════════════════════════
#: 零入度模块数上限（当前 30）—— 只降不升
ZERO_MAX = 30
#: 入度中位数下限（当前 1.0；规划目标 3.0）—— 只升不降
MEDIAN_MIN = 1.0
#: 入度 ≥3 的模块数下限（当前 28）—— 只升不降
GE3_MIN = 28
#: 模块总数下限（防「目录被抽空 ⇒ 空集永合规」）
MODULES_MIN = 70

#: 🔴 冻结的零入度集合（v0.9.365 快照）。**新增零入度 ⇒ 必红。**
ZERO_ALLOWED = frozenset({
    # 顶层 / 注册表（白名单，见 TOPLEVEL_ALLOW）
    "capability_manifest", "soc_flow",
    # 历史孤岛债务（P1/P2 待接回，见 R3 之外的清单）
    "adc_budget", "analog_mvm", "device_2d", "device_transport", "drealcell",
    "dspread", "drive_scheme", "joint_scale", "layer_stack_ext",
    "layout_feasibility", "scale_basis", "scale_bench",
    "dcnet", "ddroute_grid", "dhdlib", "dinrow", "dmacro", "dpathfinder",
    "dpgrid", "dproc", "dpvt", "dscale", "dwallrr", "dwidth",
    # 本阶段（S1–S4）新增、尚未接回主链的 4 个 —— 见 R3_DEBT
    "dliberty", "ddef", "db3_trunk", "dxcheck",
})

#: 零入度**允许**的顶层项（登记 ≠ 免检：必须真的零入度 + 理由非空 + 双向完备）
TOPLEVEL_ALLOW = {
    "soc_flow": "顶层流程（模拟/存算阵列链：器件→规模→层栈→布局→DRC→LVS→GDS），"
                "没有上游是设计使然",
    "capability_manifest": "能力清单注册表：被门禁与人读，不是计算模块",
}

#: 🔴 R3 冻结债务表：本阶段新增但尚无「非门禁」下游的模块。
#: 契约 = **精确相等**：债务缩小了必须同步删表（强制收口）；债务变大必红。
R3_DEBT = {
    "dliberty": ("S6", "让 dsta 从 Liberty 查表取延时，替换 dcell 里的硬编码"),
    "ddef": ("S6", "让 db3_trunk 用它写出/读回 DEF，补 B3 的出口段"),
    "db3_trunk": ("S6", "给一个非门禁消费者（webui 只读端点或案例卡 facts）"),
    "dxcheck": ("S6", "差异表进 /api/ecore_demo 的只读 facts，让对拍对外可见"),
}

#: 本阶段新增模块（R3 的对象）。必须都真实存在（防拼错 ⇒ 判据空转）。
NEW_MODULES = ("dliberty", "dlef", "dverilog", "ddef", "db3_trunk", "dxcheck")


# ═══════════════════════════════════════════════════════════════════════════
# 度量核心（纯函数，便于用「人造图」自证口径）
# ═══════════════════════════════════════════════════════════════════════════
def graph_from_sources(sources: dict) -> dict:
    """`{模块名: 源码}` → `{模块名: set(它依赖的模块)}`（口径见文件头）。"""
    names = set(sources)
    edges = {m: set() for m in names}
    for m, src in sources.items():
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if not isinstance(n, ast.ImportFrom):
                continue
            if n.level >= 1:
                if n.module:
                    base = n.module.split(".")[0]
                    if base in names:
                        edges[m].add(base)
                for a in n.names:                     # from . import x
                    if a.name in names:
                        edges[m].add(a.name)
            elif n.module and n.module.startswith("lda_l2.ecore"):
                parts = n.module.split(".")
                if len(parts) >= 3 and parts[2] in names:
                    edges[m].add(parts[2])
                for a in n.names:
                    if a.name in names:
                        edges[m].add(a.name)
    return edges


def graph_from_dir(dirpath: str) -> dict:
    sources = {}
    for f in sorted(os.listdir(dirpath)):
        if f.endswith(".py") and f != "__init__.py":
            with open(os.path.join(dirpath, f), encoding="utf-8", errors="replace") as fh:
                sources[f[:-3]] = fh.read()
    return graph_from_sources(sources)


def indegree(edges: dict) -> dict:
    deg = {m: 0 for m in edges}
    for deps in edges.values():
        for d in deps:
            deg[d] += 1
    return deg


def metrics(deg: dict) -> dict:
    vals = sorted(deg.values())
    n = len(vals) or 1
    zero = sorted(m for m, d in deg.items() if d == 0)
    return {
        "n_modules": len(vals),
        "mean": round(sum(vals) / n, 3),
        "median": float(statistics.median(vals)),
        "ge3": sum(1 for v in vals if v >= 3),
        "ge3_pct": round(100.0 * sum(1 for v in vals if v >= 3) / n, 1),
        "zero": zero,
        "zero_pct": round(100.0 * len(zero) / n, 1),
    }


def zero_violations(zero, allowed=ZERO_ALLOWED) -> list:
    """零入度里**不在冻结集合**的项（新增孤岛）—— 反向探针直接喂变异体。"""
    return sorted(set(zero) - set(allowed))


def r3_debt_growth(deg: dict, debt=R3_DEBT, mods=NEW_MODULES) -> list:
    """R3：新模块里「零下游」但**不在债务表**的项（债务扩大）。"""
    zero_down = [m for m in mods if deg.get(m, 0) == 0]
    return sorted(set(zero_down) - set(debt))


def r3_debt_resolved(deg: dict, debt=R3_DEBT, mods=NEW_MODULES) -> list:
    """R3：债务表里写了但**已经有下游**（或模块不存在）的项 —— 该删表却没删。"""
    return sorted(m for m in debt if deg.get(m, 0) != 0)


def main() -> int:
    edges = graph_from_dir(_ECORE)
    deg = indegree(edges)
    M = metrics(deg)

    # ── M0 规模下限（防抽空）─────────────────────────────────────────────
    check("M0 模块数 %d ≥ %d（防目录被抽空 ⇒ 空集永合规）"
          % (M["n_modules"], MODULES_MIN), M["n_modules"] >= MODULES_MIN)

    # ── M1 R1 零入度占比上限 ────────────────────────────────────────────
    check("M1 R1 零入度 %d/%d = %.1f%% ≤ 上限 %d 个（规划目标 ≤12%%）"
          % (len(M["zero"]), M["n_modules"], M["zero_pct"], ZERO_MAX),
          len(M["zero"]) <= ZERO_MAX,
          "超出=%d" % (len(M["zero"]) - ZERO_MAX))

    # ── M2 冻结集合：新增孤岛必红 ───────────────────────────────────────
    v2 = zero_violations(M["zero"])
    check("M2 零入度集合 ⊆ 冻结快照（%d 项）—— 新增孤岛必红" % len(ZERO_ALLOWED),
          not v2, "新增孤岛=%r" % (v2,))

    # ── M3 白名单双向完备：写了必须真的零入度 ───────────────────────────
    not_zero = sorted(m for m in TOPLEVEL_ALLOW if deg.get(m, 0) != 0)
    missing = sorted(m for m in TOPLEVEL_ALLOW if m not in deg)
    check("M3 白名单双向完备：%d 项都真实存在且真的零入度（写了却不零 ⇒ 死条款）"
          % len(TOPLEVEL_ALLOW), not not_zero and not missing,
          "已非零=%r 不存在=%r" % (not_zero, missing))

    # ── M4 白名单理由非空 ───────────────────────────────────────────────
    empty = sorted(m for m, why in TOPLEVEL_ALLOW.items() if not str(why).strip())
    check("M4 白名单每项都有非空理由（登记 ≠ 免检）", not empty, "空理由=%r" % (empty,))

    # ── M5 R2 入度中位数下限 ────────────────────────────────────────────
    check("M5 R2 入度中位 %.1f ≥ 下限 %.1f（规划目标 ≥3.0）"
          % (M["median"], MEDIAN_MIN), M["median"] >= MEDIAN_MIN,
          "低于下限")

    # ── M6 入度 ≥3 的模块数下限 ─────────────────────────────────────────
    check("M6 入度 ≥3 的模块 %d 个（%.1f%%）≥ 下限 %d"
          % (M["ge3"], M["ge3_pct"], GE3_MIN), M["ge3"] >= GE3_MIN)

    # ── M7 R3 债务未扩大（精确契约）─────────────────────────────────────
    grew = r3_debt_growth(deg)
    check("M7 R3 债务未扩大：新模块零下游集合 ⊆ 冻结债务表（%d 条）" % len(R3_DEBT),
          not grew, "债务扩大=%r" % (grew,))

    # ── M8 R3 债务该删没删 ⇒ 红（强制收口，防「永久欠账」）──────────────
    stale = r3_debt_resolved(deg)
    check("M8 R3 债务表无过期条目（已有下游却仍在表内 ⇒ 必须删表）",
          not stale, "过期=%r" % (stale,))

    # ── M9 债务条目必须有「到期里程碑 + 理由」───────────────────────────
    bad9 = []
    for m, (due, why) in R3_DEBT.items():
        if not str(due).strip() or not str(why).strip():
            bad9.append(m)
        if m not in deg:
            bad9.append(m + "(不存在)")
    check("M9 债务每项都有到期里程碑 + 理由 + 模块真实存在", not bad9, "问题=%r" % (bad9,))

    # ── M10 度量口径自证（人造图：A→B、A→C ⇒ B/C 入度 1，A 零入度）────
    toy = graph_from_sources({
        "a": "from .b import x\nfrom . import c\n",
        "b": "x = 1\n",
        "c": "y = 2\n",
    })
    tdeg = indegree(toy)
    tm = metrics(tdeg)
    check("M10 度量口径自证：A→B/A→C ⇒ 边 %r · 入度 %r · 零入度 %r"
          % (sorted(toy["a"]), tdeg, tm["zero"]),
          toy["a"] == {"b", "c"} and tdeg == {"a": 0, "b": 1, "c": 1}
          and tm["zero"] == ["a"] and tm["ge3"] == 0)

    # ── M11 反向：边的**指向**变 ⇒ 入度分布必变（有区分度）─────────────
    #   注意：只改「链式」是无效探针 —— A→B→C 与 A→B/A→C 的入度分布相同，
    #   必须改成「两条边指向同一节点」（a→b、c→b）才能拉开分布。
    toy2 = graph_from_sources({
        "a": "from .b import x\n",
        "b": "x = 1\n",
        "c": "from .b import y\n",
    })
    check("M11 反向：两条边改指向同一节点 ⇒ 入度分布必变（判据有区分度）",
          indegree(toy2) != tdeg and indegree(toy2)["b"] == 2,
          "toy2=%r" % (indegree(toy2),))

    # ── M12 反向：新增孤岛 / 债务扩大 ⇒ 检测器必报 ──────────────────────
    probe_zero = zero_violations(M["zero"] + ["__fake_new_island__"])
    probe_debt = r3_debt_growth(dict(deg, **{"dliberty": 0}),
                               debt={k: v for k, v in R3_DEBT.items() if k != "dliberty"})
    check("M12 反向：塞一个假孤岛 ⇒ M2 必报 ∧ 从债务表删一条（模块仍零下游）⇒ M7 必报",
          probe_zero == ["__fake_new_island__"] and probe_debt == ["dliberty"],
          "zero=%r debt=%r" % (probe_zero, probe_debt))

    # ── M13 自入 CI core ────────────────────────────────────────────────
    with open(os.path.join(_HERE, "run_ci_regression.py"), encoding="utf-8") as fh:
        ck = fh.read()
    check("M13 本门禁已登记进 CORE_SMOKES（防静默漏接）",
          "run_ecore_reuse_metrics_smoke.py" in ck)

    # ── M14 耗时 ────────────────────────────────────────────────────────
    dt = time.time() - T0
    check("M0t 门禁耗时 %.2f s < %.0f s" % (dt, AN_ELAPSED_MAX_S), dt < AN_ELAPSED_MAX_S)

    print("")
    print("  度量口径：lda_l2/ecore/*.py · 入度=引用它的不同模块数 · 不数门禁")
    print("  R1 零入度 %d/%d = %.1f%%（上限 %d · 目标 ≤12%%）"
          % (len(M["zero"]), M["n_modules"], M["zero_pct"], ZERO_MAX))
    print("  R2 入度中位 %.1f · 均值 %.2f · 入度≥3 %d（%.1f%%）（目标中位 ≥3）"
          % (M["median"], M["mean"], M["ge3"], M["ge3_pct"]))
    print("  R3 新模块 %d 个 · 已接回 %d · 债务 %d 条（%s）"
          % (len(NEW_MODULES), sum(1 for m in NEW_MODULES if deg.get(m, 0) > 0),
             len(R3_DEBT), ", ".join("%s(→%s)" % (k, v[0]) for k, v in sorted(R3_DEBT.items()))))
    print("")
    if _FALS:
        print("复用度量有红色：%s" % ", ".join(_FALS))
        return 1
    print("复用度量全绿 · 零入度与环境已被冻结上限锁住（只许收紧），债务表每次 CI 打印在脸上")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
