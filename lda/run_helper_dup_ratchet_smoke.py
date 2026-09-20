# -*- coding: utf-8 -*-
"""助手重复棘轮护栏（v0.9.113 · 波次 2 · 源自 2026-09-19 全面代码审计 F-07）。

防什么
------
审计 F-07 记「`check()` 助手复制 **86 份**」。波次 2 的 **AST 逐文件复测**给出更精确
的结论：全仓 **97 处** `def check(`（97 个文件，各 1 处），按「忽略标识符/常量/属性名
的 AST 骨架」分 **36 个结构类**——即它们**不是同一个助手复制 86 次**，而是 36 个各自
定制的局部助手共用一个名字。分歧点只有三类：① 计数器机制 ② 打印格式 ③ 返回值。

本波把其中**输出可证明逐字等价**的部分抽到公共模块：

  · `lda_harness/smoke_kit.py` ← `make_check` / `check_raise` / `free_port` /
    `run_unittest_suite`（**50 个 smoke 文件**：其中 **44 个含 `def check(`**（本轮
    唯一被抽走的 `def check(` 数，`git grep -l` 实测）+ **6 个只含 `_free_port`**；
    6 份 `_free_port` 合并为 1 份）
  · `lda_solver/redline.py` ← T1 红线守卫 `guard_t1_not_oracle`（**6 → 1**）

🔴 **未全量归一，是刻意决定而非遗漏**。实测口径：HEAD `def check(` **97 处** →
本轮抽走 **44 处** → 余 **53 处**（`smoke_kit` 自身的 1 处不计），分布 **31 个结构类**。
四类主因（逐条读原文实测，非推测）：

  | 主因 | ×文件 | 原形 | 不归一理由 |
  |---|---|---|---|
  | 非模块级 | 10 | 嵌套 `def check` + `nonlocal passed/failed`；**详情仅 FAIL 打印** | `make_check` 只产出**模块级**助手；且格式非对称 |
  | 4 参调用约定 | 7 | `check(cond, msg, out/report, key)`，状态词 `OK  `/`FAIL`，结果写 dict | 调用约定与状态词都不同 |
  | 必须写调用方自有容器 | 31 | 结果收集进 `CHECKS`/`_CHECKS`/`checks`/`_FAILED`/`_FAILS`/`_FATAL`/`(ok|fail).append` | `make_check` 只做「计数 + 打印」，不写调用方容器（其中 **4 处纯收集、无打印** ⇒ 归一后反而更长） |
  | 模块级计数器但格式各异 | 5 | `global PASS/FAIL` 或 `global _PASS/_FAIL` + 无条件打详情 / 非标准分隔符 / PASS·FAIL 分行 | 需再加 2~4 个 quirk 旋钮 ⇒ 参数汤，可读性劣于重复 |

⇒ 正确处理是**棘轮**（只许降不许升），不是 god-factory。

判据（死标量，LLM 不进判决路径）
--------------------------------
  J1 T1 红线守卫**单一来源**：`def guard_t1_not_oracle` 全仓恰好 1 处，且在
     `lda_solver/redline.py`
  J2 端口助手**单一来源**：`def [free_]port` 恰好 1 处，且在 `lda_harness/smoke_kit.py`
  J3 `def check(` 处数（不含 smoke_kit 自身）≤ 基线 ⇒ **只许降不许升**
  J4 参与「逐字完全相同」重复组的文件数 ≤ 基线（防「删一个 bespoke、添一对重复」）
  J5 `smoke_kit` 被 ≥ 基线个文件导入（防「抽了没人用」——抽象若无人接线即退回复制）
  J6 全量 AST 解析零错误
  J7 🔴 T1 红线语义：`T1_OUTPUT_IS_ORACLE is False`；6 个数值内核的
     `guard_t1_not_oracle` **绑定到同一个函数对象**（`partial.func is` 判据）⇒
     任何一处退回本地复制即红
  J8 🔴 反向测试（四条，证明判据真会变红，非假绿）：
     ① 基线调低 1 ⇒ J3 必报  ② 合成 2 处守卫定义 ⇒ J1 必报
     ③ 合成超限 check_defs ⇒ J3 必报  ④ 合成接线不足 ⇒ J5 必报
     ⑤ `force_oracle=True` 必 raise  ⑥ `is_oracle=True` 必 raise

基线来源：v0.9.113 波次 2 **归一后实测值**（见 `LDA_fix_workplan_2026-09-19.md`）。
运行：python run_helper_dup_ratchet_smoke.py
"""
from __future__ import annotations

import ast
import os
import re
import sys

from lda_harness.smoke_kit import make_check

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)          # D:/agent_LDA

# smoke_kit 的导入探测（覆盖 `from lda_harness.smoke_kit import X` 两路写法）
_IMPORT_RE = re.compile(
    r"^\s*from\s+[\w.]*smoke_kit\s+import|^\s*import\s+[\w.]*smoke_kit\b", re.M)

# 三方隔离区（与 run_pyflakes_ratchet_smoke._EXCLUDE_PARTS 同口径）
_EXCLUDE_PARTS = ("lda_cuda_venv", "node_modules", "vendor", ".cache", "site-packages",
                  "__pycache__")

_REDLINE_REL = "lda/lda_solver/redline.py"
_KIT_REL = "lda/lda_harness/smoke_kit.py"

# 🔴 棘轮基线（v0.9.113 波次 2 归一后实测）——**只许降，不许升**。
# 上调须付理由：确需新增独立 `def check` 时，须说明「为何不能复用 smoke_kit」，
# 并在本合同步留注（防静默放宽）。
_BASELINE = {
    "max_check_defs": 53,        # HEAD 97 处 − 本轮抽走 44 处 = 53（`smoke_kit` 自身不计 · 实测）
    "max_dup_files": 30,         # 仍处于「逐字重复组」的文件数（10 组）
    "min_kit_importers": 70,     # 50(波次2 Stage A) + 18(F-18 报告契约) + 1(本棘轮自身)
                                 #   + 1(v0.9.114：`run_bounty_ledger_smoke` 删死码时归一到 make_check)
}

# 6 个 T1 数值内核（守卫文案各不同，但实现必须同一份）
_T1_KERNELS = (
    "lda_solver.apd_avalanche_true",
    "lda_solver.detector_bandwidth_true",
    "lda_solver.drift_diffusion_1d",
    "lda_solver.drift_diffusion_2d",
    "lda_solver.ge_pd_responsivity_true",
    "lda_solver.mzm_vpi_depletion_true",
)

# 🔴 本 smoke **不得**再添一个本地 `def check`——那正是本棘轮要防的事。
# 复用公共模块（`detail_on="fail"` ⇒ 仅失败打详情，与 run_pyflakes_ratchet_smoke
# 的原惯用法逐字等价）。
_NP = 0
_NF = 0
check = make_check(globals(), ok_key="_NP", bad_key="_NF", indent="  ",
                   detail_fmt="  —— {d}", detail_on="fail", return_ok=True)


# --------------------------------------------------------------------------- 扫
def _iter_py():
    for dp, dns, fns in os.walk(os.path.join(_ROOT, "lda")):
        dns[:] = [d for d in dns if d not in _EXCLUDE_PARTS and not d.startswith(".")]
        for fn in sorted(fns):
            if fn.endswith(".py"):
                yield os.path.join(dp, fn)


def _rel(p):
    return os.path.relpath(p, _ROOT).replace("\\", "/")


def scan(lda_py=None):
    """纯扫描：返回判定所需的全部计数（可被反向测试喂合成数据）。"""
    out = {"guard_defs": [], "freeport_defs": [], "check_defs": [],
           "dup_groups": {}, "kit_importers": [], "parse_errs": []}
    paths = list(_iter_py()) if lda_py is None else lda_py
    for p in paths:
        rel = _rel(p)
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                src = fh.read()
        except OSError as exc:                              # pragma: no cover
            out["parse_errs"].append((rel, "OSError: %s" % exc))
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError as exc:
            out["parse_errs"].append((rel, "SyntaxError: %s" % exc))
            continue
        if "smoke_kit" in src and _IMPORT_RE.search(src):
            out["kit_importers"].append(rel)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name == "guard_t1_not_oracle":
                out["guard_defs"].append((rel, node.lineno))
            elif node.name in ("free_port", "_free_port"):
                out["freeport_defs"].append((rel, node.lineno))
            elif node.name == "check":
                seg = ast.get_source_segment(src, node) or ""
                out["check_defs"].append((rel, node.lineno, seg))
    # 逐字重复组：仅统计**出现在多个文件**的文本
    by_text = {}
    for rel, _ln, seg in out["check_defs"]:
        if rel == _KIT_REL:            # smoke_kit 自身的单一定义不算重复
            continue
        by_text.setdefault(seg, []).append(rel)
    out["dup_groups"] = {k: v for k, v in by_text.items() if len(v) > 1}
    return out


# ------------------------------------------------------------------------- 判
def judge(sc, baseline):
    """纯函数：返回 [(判据号, 是否通过, 详情)]。正向与反向测试共用同一实现。"""
    res = []

    def add(jid, ok, detail=""):
        res.append((jid, bool(ok), detail))

    gd = sc["guard_defs"]
    add("J1 T1 红线守卫单一来源（恰好 1 处 · 在 redline.py）",
        len(gd) == 1 and gd[0][0] == _REDLINE_REL,
        "实测 %d 处：%s" % (len(gd), gd[:5]))

    fd = sc["freeport_defs"]
    add("J2 端口助手单一来源（恰好 1 处 · 在 smoke_kit.py）",
        len(fd) == 1 and fd[0][0] == _KIT_REL,
        "实测 %d 处：%s" % (len(fd), fd[:5]))

    n = len([d for d in sc["check_defs"] if d[0] != _KIT_REL])
    add("J3 def check( 处数（不含 smoke_kit 单一实现）≤ 基线（只许降不许升）",
        n <= baseline["max_check_defs"],
        "实测 %d > 基线 %d" % (n, baseline["max_check_defs"]))

    nkit = len([d for d in sc["check_defs"] if d[0] == _KIT_REL])
    add("J3b smoke_kit 自身的规范定义恰好 1 处（make_check 内）",
        nkit == 1, "实测 %d 处" % nkit)

    ndup = sum(len(v) for v in sc["dup_groups"].values())
    add("J4 逐字重复组涉及文件数 ≤ 基线",
        ndup <= baseline["max_dup_files"],
        "实测 %d > 基线 %d（新增重复组 %s）"
        % (ndup, baseline["max_dup_files"],
           [v for v in sc["dup_groups"].values() if len(v) > 1][:4]))

    nk = len(sc["kit_importers"])
    add("J5 smoke_kit 接线数 ≥ 基线（防「抽了没人用」）",
        nk >= baseline["min_kit_importers"],
        "实测 %d < 基线 %d" % (nk, baseline["min_kit_importers"]))

    add("J6 全量 AST 解析零错误", len(sc["parse_errs"]) == 0,
        "解析错误：%s" % sc["parse_errs"][:3])
    return res


def _t1_runtime_judges():
    """J7 运行时：单一来源 + 行为。失败返回 (ok, detail) 列表。"""
    import importlib
    from functools import partial

    res = []
    try:
        rl = importlib.import_module("lda_solver.redline")
    except Exception as exc:                                # noqa: BLE001
        res.append(("J7a redline 可导入", False, "%s: %s" % (type(exc).__name__, exc)))
        return res

    res.append(("J7a T1_OUTPUT_IS_ORACLE 恒 False（铁律开关）",
                getattr(rl, "T1_OUTPUT_IS_ORACLE", None) is False,
                "实测 %r" % (getattr(rl, "T1_OUTPUT_IS_ORACLE", "<缺失>"),)))

    same, bad = [], []
    for mod in _T1_KERNELS:
        try:
            m = importlib.import_module(mod)
            g = getattr(m, "guard_t1_not_oracle")
        except Exception as exc:                            # noqa: BLE001
            bad.append("%s 导入失败 %s" % (mod, exc))
            continue
        if isinstance(g, partial) and g.func is rl.guard_t1_not_oracle:
            same.append(mod)
        else:
            bad.append("%s 未绑定到 redline 单一定义（%r）" % (mod, g))
    res.append(("J7b 6 个 T1 内核绑定同一函数对象（partial.func is）",
                len(same) == len(_T1_KERNELS), "; ".join(bad[:3])))

    # 反向：守卫真会拦（铁律：没被验证过的护栏不算护栏）
    def _raises(kw, sol=None):
        try:
            rl.guard_t1_not_oracle(sol if sol is not None else {}, **kw)
            return False, "未 raise"
        except RuntimeError as exc:
            return True, str(exc)
        except Exception as exc:                            # noqa: BLE001
            return False, "%s: %s" % (type(exc).__name__, exc)

    ok, d = _raises({"force_oracle": True})
    res.append(("J8a 反向：force_oracle=True ⇒ RuntimeError", ok, d))
    ok, d = _raises({}, {"is_oracle": True})
    res.append(("J8b 反向：is_oracle=True ⇒ RuntimeError", ok, d))
    return res


# ------------------------------------------------------------------------ main
def main() -> int:
    print("== 助手重复棘轮（F-07 · 只降不升）==")
    sc = scan()
    print("  check_defs=%d · dup 组 %d（涉及 %d 文件）· kit 接线 %d · "
          "guard 定义 %d · free_port 定义 %d"
          % (len(sc["check_defs"]), len(sc["dup_groups"]),
             sum(len(v) for v in sc["dup_groups"].values()),
             len(sc["kit_importers"]), len(sc["guard_defs"]),
             len(sc["freeport_defs"])))
    print("  基线：%s" % _BASELINE)

    rc = 0
    for jid, ok, detail in judge(sc, _BASELINE):
        rc |= not check(jid, ok, detail)

    for jid, ok, detail in _t1_runtime_judges():
        rc |= not check(jid, ok, detail)

    # 🔴 反向测试：同一 judge 必须能报出违规（防「判据永真」）
    n_real = len([d for d in sc["check_defs"] if d[0] != _KIT_REL])
    lower = dict(_BASELINE)
    lower["max_check_defs"] = max(0, _BASELINE["max_check_defs"] - 1)
    probe = dict(sc)
    if n_real <= lower["max_check_defs"]:
        probe["check_defs"] = list(probe["check_defs"]) + [("__synth__", 1, "x")] * (
            lower["max_check_defs"] + 1 - n_real)
    rc |= not check("J8c 反向：基线调低 1 ⇒ J3 必报",
                    any(j.startswith("J3 ") and not ok
                        for j, ok, _ in judge(probe, lower)),
                    "判据未响应")

    syn2 = dict(sc, guard_defs=[(_REDLINE_REL, 1), ("lda/x.py", 2)])
    rc |= not check("J8d 反向：合成 2 处守卫定义 ⇒ J1 必报",
                    any(j.startswith("J1 ") and not ok for j, ok, _ in judge(syn2, _BASELINE)),
                    "判据未响应")

    syn3 = dict(sc, kit_importers=sc["kit_importers"][:5])
    rc |= not check("J8e 反向：接线不足 ⇒ J5 必报",
                    any(j.startswith("J5 ") and not ok for j, ok, _ in judge(syn3, _BASELINE)),
                    "判据未响应")

    print("-" * 74)
    print("汇总：%d PASS / %d FAIL / 共 %d 项" % (_NP, _NF, _NP + _NF))
    if rc == 0:
        print("ALL PASS — 助手重复只降不升，棘轮在位（check_defs≤%d / dup_files≤%d / "
              "kit_importers≥%d）"
              % (_BASELINE["max_check_defs"], _BASELINE["max_dup_files"],
                 _BASELINE["min_kit_importers"]))
    else:
        print("FAIL — 助手重复劣化或棘轮失效，请按上方 FAIL 项修复")
    return int(rc)


if __name__ == "__main__":
    sys.path.insert(0, _HERE)
    raise SystemExit(main())
