# -*- coding: utf-8 -*-
"""CI 门禁**自身契约**的护栏（v0.9.190）。

防两类缺陷 —— 都是本仓最忌的「假红 / 假绿 制造机」
---------------------------------------------------
① 🔴 **棘轮时序假红**（M0 / M1 / M2 连续三轮印证）
   `scripts/ci_core_batched.py --write-baseline` 把超时预算棘轮排在**普通批次**里执行，
   而基线文件在**全部批次跑完之后**才写回 ⇒ 棘轮读到的是**上一版基线** ⇒ 本轮刚登记
   进 CI core 的新成员在旧基线里没有行 ⇒ **B5「覆盖完备」必红**。
   这条红**信息量为零**（与代码/预算无关），却每加一个新成员必然出现一次 —— 典型
   假红制造机：稀释真红的信噪比，并诱导后人去「改判据」这条失真通道。
   根治：基线写回**之后**复跑棘轮并覆盖该条（不论红绿 —— **绝不掩盖真红**）。

② 🔴 **门禁退出码失效 = 假绿**（v0.9.190 实证发现）
   CI 判定 smoke 成败的口径是 `PASS if rc == 0 else FAIL`（`run_ci_regression._run_one`）。
   若某 smoke 的 `main()` 恒 `return 0`，则它的 FAIL 行**只是打印**、**永不被 CI 捕获**。
   实测血案：`run_pm_m1_smoke.py`（24 条判据失败）/ `run_pm_m2_smoke.py`（40 条）曾如此
   —— 注入恒 FAIL 时 rc 仍为 0（**假绿实证**，见 P 组探针），修后 rc=1。

判据（全部走**真代码路径 / 真源码**；不读字面量、不设手写豁免清单）
  组 A 棘轮时序      A1~A6  +  P1~P3 探针
  组 B 退出码契约    B1~B3  +  P4~P5 探针
    B1 判据**无手写豁免清单**：`有判据（check/assert）却无失败通道` 才判红；
       本就无判据的文件（如 CLI 演示入口）自动不判红 —— 避免清单静默进盲区。
  组 C 自测口径契约  C1~C2  +  P6~P7 探针（v0.9.194 新增）
    C1 🔴 `make_check(detail_fmt=...)` 是 **str.format 模板**（`{d}`）。传 printf
       模板（`" · %s"`）**不报错但恒印字面量** ⇒ 失败详情被静默吞掉（实证：
       `run_pm_m5_smoke.py` C1 真红时只打出 `· %s`，唯一线索被埋）。命中即判红。
    C2 🔴 门禁/脚本**不许用 cwd 相对路径**访问仓库产物（`"examples/..."` 直传
       `open`，或先赋值再传）。CI 以 `cwd=lda` 调起门禁，而人手多在仓库根跑 ⇒
       同一份代码两套结论（`run_pm_m5_smoke` 是「本地绿/CI 红」，
       `run_accel_case_smoke` 反着来；`run_ecosystem_report.py` 两处需求互斥 ⇒
       根本没有一个 cwd 能同时成立）。**cwd 也是口径的一部分。**
"""
from __future__ import annotations

import ast
import contextlib
import glob
import importlib.util
import io
import json
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ROOT = os.path.dirname(_HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=' —— {d}')

import run_ci_regression as R  # noqa: E402

_RATCHET = "run_timeout_budget_ratchet_smoke.py"
_CCB_REL = os.path.join("scripts", "ci_core_batched.py")
_SELF = "run_ci_gate_contract_smoke.py"

# 哨兵：与任何真实常量值都不相等（不能用 None —— 裸 return 就是 None）
_EXPR = object()


# ============================================================ 组 B：退出码契约
def _const_val(v):
    if isinstance(v, ast.Constant):
        return v.value
    if isinstance(v, ast.UnaryOp) and isinstance(v.operand, ast.Constant):
        return -v.operand.value
    return _EXPR


def _nonzero(x):
    """常量 0 / False 视为「绿」；非零常量或表达式视为「可能是失败码」。"""
    return x is _EXPR or (isinstance(x, (int, float)) and x != 0) or x is True


def _exit_channel(tree):
    """源码里是否存在**能把失败传播到进程退出码**的通道。

    覆盖本仓三种主流形态：
      · `main()` 里 `return <非常量>` / `return <非零>`（如 `return 0 if FAIL==0 else 1`）
      · `sys.exit(x)` / `raise SystemExit(x)`，x 非常量或非零
      · 任意 `raise`，或**任意 `assert`**（断言失败 ⇒ AssertionError ⇒ 非零 rc；
        本仓 d06/d10 等历史文件即此风格）
    🔴 特判 `sys.exit(main())`：其通道性**继承 main 自身**（否则会把最主流写法误判为无通道）。
    """
    main = None
    for f in tree.body:
        if isinstance(f, ast.FunctionDef) and f.name == "main":
            main = f
    main_ok = False
    if main is not None:
        has_raise = any(isinstance(n, ast.Raise) for n in ast.walk(main))
        has_ret = any(isinstance(n, ast.Return) and n.value is not None
                      and _nonzero(_const_val(n.value)) for n in ast.walk(main))
        main_ok = has_raise or has_ret

    def _is_exit_call(n):
        if not isinstance(n, ast.Call) or not n.args:
            return False
        fn = n.func
        nm = fn.attr if isinstance(fn, ast.Attribute) else (
            fn.id if isinstance(fn, ast.Name) else "")
        return nm in ("exit", "SystemExit")

    for n in ast.walk(tree):
        if _is_exit_call(n):
            a = n.args[0]
            is_main_call = (isinstance(a, ast.Call) and isinstance(a.func, ast.Name)
                            and a.func.id == "main")
            if is_main_call:
                if main_ok:
                    return True
            elif _nonzero(_const_val(a)):
                return True
    return (main_ok or any(isinstance(n, ast.Raise) for n in ast.walk(tree))
            or _n_assert(tree) > 0)


def _gate_calls(tree):
    n = 0
    for x in ast.walk(tree):
        if isinstance(x, ast.Call):
            f = x.func
            nm = f.attr if isinstance(f, ast.Attribute) else (
                f.id if isinstance(f, ast.Name) else "")
            if nm in ("check", "_gate"):
                n += 1
    return n


def _n_assert(tree):
    return sum(1 for x in ast.walk(tree) if isinstance(x, ast.Assert))


_ASSERT_OK = ("有判据（check/assert）⇒ 必须有失败退出通道（rc≠0），"
              "否则门禁的 FAIL 永不被 CI 捕获 = 假绿")


# ==================================================== 组 C：自测口径契约
#: 仓库顶层目录名（出现这些字面开头 ⇒ 该路径是**仓库内**产物、不该相对 cwd）
_REPO_DIR_HEADS = ("examples", "docs", "lda", "scripts", "reports", "assets",
                   "webui", "lda_webui")
#: 视作「文件访问」的调用名（open/存在性/读取）
_FILE_APIS = ("open", "exists", "isfile", "islink", "load", "read_text",
              "read_bytes")


def _fn_name(n):
    if isinstance(n, ast.Attribute):
        return n.attr
    if isinstance(n, ast.Name):
        return n.id
    return ""


def _is_cwd_relative_repo(n):
    """判断 AST 表达式是否是**相对 cwd** 的仓库路径。

    `"examples/x.json"`（字面量）或 `os.path.join("examples", ...)`（首参字面量）
    ⇒ True。`os.path.join(_ROOT, "examples", ...)` ⇒ False（已锚定）。
    """
    if isinstance(n, ast.Constant) and isinstance(n.value, str):
        return n.value.replace("\\", "/").split("/")[0] in _REPO_DIR_HEADS
    if isinstance(n, ast.Call) and _fn_name(n.func) == "join" and n.args:
        return _is_cwd_relative_repo(n.args[0])
    return False


def _cwd_relative_reads(src):
    """返回「用 cwd 相对路径访问仓库文件」的调用点（AST · 不读字面量清单）。

    口径（两类，覆盖本仓全部实证形态）：
      · 当场就是相对字面量：`open("examples/x.json")` / `join("examples", ...)`
        直接作为文件 API 的第一实参；
      · 同一函数内先赋值再使用：`p = join("examples", ...)` … `open(p)`。
    **不算**违约：`open(os.path.join(_ROOT, ...))`，以及经助手函数转发
    （`_read(join("lda", ...))` + `def _read(rel): open(join(_ROOT, rel))`）——
    那类最终仍锚在仓库根；这两类正是本判据的假阳性来源，已由 P7 样例钉死。
    """
    tree = ast.parse(src)
    hits = []

    def _scan(stmts, names, scope):
        """在给定语句集合里找「第一实参是 cwd 相对仓库路径」的文件 API 调用。"""
        for st in stmts:
            for n in ast.walk(st):
                if not (isinstance(n, ast.Call) and n.args):
                    continue
                if _fn_name(n.func) not in _FILE_APIS:
                    continue
                a0 = n.args[0]
                if _is_cwd_relative_repo(a0) or (isinstance(a0, ast.Name)
                                                 and a0.id in names):
                    hits.append("%s:%s(%s)" % (scope, _fn_name(n.func),
                                               ast.unparse(a0)))

    mod_rel = {t.id for n in tree.body if isinstance(n, ast.Assign)
               and _is_cwd_relative_repo(n.value)
               for t in n.targets if isinstance(t, ast.Name)}
    _scan(tree.body, mod_rel, "module")           # 模块级（含 __main__ 块内语句）
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        names = set(mod_rel)
        for n in ast.walk(fn):
            if isinstance(n, ast.Assign) and _is_cwd_relative_repo(n.value):
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        names.add(t.id)
        _scan(fn.body, names, fn.name)
    return sorted(set(hits))


def _fmt_guard_raises(fmt):
    """`make_check` 对 printf 模板是否 raise（还原 pre-fix 行为用）。"""
    try:
        make_check({}, detail_fmt=fmt)
        return False
    except ValueError:
        return True


# ============================================================ 组 A：棘轮时序
def _load_ccb():
    """按路径加载 `scripts/ci_core_batched.py`（不在包内，须 importlib）。"""
    p = os.path.join(_ROOT, _CCB_REL)
    spec = importlib.util.spec_from_file_location("_ccb_under_test", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_driver(CCB, *, post_status="PASS", write_baseline=True,
                disable_rerun=False, tmpdir="."):
    """在**受控 fake** 下跑一遍 `CCB.main()`，返回 (rc, out, events, calls)。

    被替换的只有两个外部副作用（跑子进程 / 写基线），**驱动逻辑本身全走真代码**：
      · `run_ci_regression`：批次调用返回「棘轮假红 + 普通成员 PASS」；
        `scripts=` 非空的调用（= 后置复跑）返回 `post_status` 的棘轮结果。
      · `_write_baseline`：记账 no-op（**绝不碰真基线**）。
    """
    events, calls = [], []
    out_path = os.path.join(tmpdir, "_ccb_contract_report.json")

    def fake_run(python=None, tag="all", timeout=300.0, fail_fast=False,
                 exclude=None, timeout_override=None, scripts=None):
        calls.append(list(scripts) if scripts else None)
        if scripts:                                    # ← 后置复跑（只跑棘轮）
            events.append("rerun_ratchet")
            ok = post_status == "PASS"
            return {"results": [{"script": _RATCHET, "status": post_status,
                                 "rc": 0 if ok else 1, "elapsed_s": 0.5}],
                    "summary": {"pass": 1 if ok else 0, "skip": 0,
                                "fail": 0 if ok else 1}}
        events.append("batch")
        return {"results": [
            # 批次内：棘轮「时序假红」（读旧基线 ⇒ B5 缺行）
            {"script": _RATCHET, "status": "FAIL", "rc": 1, "elapsed_s": 0.82},
            {"script": "run_pm_m2_smoke.py", "status": "PASS", "rc": 0, "elapsed_s": 20.0},
        ], "summary": {"pass": 1, "skip": 0, "fail": 1}}

    def fake_write_baseline(results, *, label, threads, dst=None):
        events.append("write_baseline")
        return {}

    old = (CCB.run_ci_regression, CCB._write_baseline, CCB._rerun_ratchet, sys.argv)
    CCB.run_ci_regression = fake_run
    CCB._write_baseline = fake_write_baseline
    if disable_rerun:                                  # 探针：模拟「未修」的旧行为
        CCB._rerun_ratchet = lambda *a, **k: None
    argv = ["ci_core_batched.py", "--tag", "core", "--batch", "9999",
            "--cooldown", "0", "--out", out_path]
    if write_baseline:
        argv.append("--write-baseline")
    sys.argv = argv
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            rc = CCB.main()
        with open(out_path, encoding="utf-8") as fh:
            out = json.load(fh)
    finally:
        (CCB.run_ci_regression, CCB._write_baseline,
         CCB._rerun_ratchet, sys.argv) = old
    return rc, out, events, calls


# ============================================================ main
def main() -> int:
    CCB = _load_ccb()
    tmpdir = tempfile.mkdtemp(prefix="lda_ccb_contract_")

    print("== 组 A：棘轮时序（--write-baseline 下必须后置复跑）==")
    rc_ok, out_ok, ev_ok, calls_ok = _run_driver(CCB, post_status="PASS", tmpdir=tmpdir)
    rc_bad, out_bad, _, _ = _run_driver(CCB, post_status="FAIL", tmpdir=tmpdir)
    _, out_none, ev_none, calls_none = _run_driver(CCB, write_baseline=False, tmpdir=tmpdir)
    rc_off, out_off, ev_off, _ = _run_driver(CCB, post_status="PASS",
                                             disable_rerun=True, tmpdir=tmpdir)
    biz = out_ok.get("ratchet_post_baseline") or {}

    check("A1 汇总可重入且字段齐（summary/budget_audit/verdict 三件齐）",
          all(k in out_ok for k in ("summary", "budget_audit", "verdict"))
          and isinstance(out_ok["summary"].get("by_status"), dict))
    check("A2 后置复跑已消除时序假红（batch 内 FAIL ⇒ 终局 rc=0 / fail=0）",
          rc_ok == 0 and out_ok["summary"]["fail"] == 0,
          "rc=%r fail=%r" % (rc_ok, out_ok["summary"]["fail"]))
    check("A3 🔴 不掩盖真红（后置仍 FAIL ⇒ rc=1 / fail=1 / verdict 非『已消除』）",
          rc_bad == 1 and out_bad["summary"]["fail"] == 1
          and (out_bad.get("ratchet_post_baseline") or {}).get("verdict") != "时序假红已消除",
          "rc=%r fail=%r verdict=%r" % (rc_bad, out_bad["summary"]["fail"],
                                        (out_bad.get("ratchet_post_baseline") or {}).get("verdict")))
    check("A4 事件序：批次 → 写基线 → 后置复跑，且后置**只**跑棘轮",
          ev_ok == ["batch", "write_baseline", "rerun_ratchet"]
          and len(calls_ok) == 2 and calls_ok[1] == [_RATCHET],
          "events=%r calls=%r" % (ev_ok, calls_ok))
    check("A5 非 --write-baseline 模式行为不变（无写基线/无后置、报告无证据块）",
          ev_none == ["batch"] and calls_none == [None]
          and "ratchet_post_baseline" not in out_none)
    check("A6 证据块由实际红绿算出（pre=FAIL ∧ post=PASS ∧ verdict=已消除 ∧ reason 非空）",
          biz.get("pre_status") == "FAIL" and biz.get("post_status") == "PASS"
          and biz.get("verdict") == "时序假红已消除" and bool(biz.get("reason")))

    # ---------------- 组 B：退出码契约 ----------------
    print("\n== 组 B：门禁退出码契约（有判据 ⇒ 必须有失败通道）==")
    viol, scanned, missing = [], 0, []
    for s in R.CORE_SMOKES:
        p = os.path.join(_HERE, s)
        if not os.path.exists(p):
            missing.append(s)
            continue
        scanned += 1
        with open(p, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        if (_gate_calls(tree) or _n_assert(tree)) and not _exit_channel(tree):
            viol.append(s)
    check("B1 无『有判据却无失败通道』的门禁（%s）" % _ASSERT_OK, not viol,
          "违约：%s" % (viol if viol else "无"))
    check("B2 覆盖面完整（CORE_SMOKES 每个成员都真被扫到，无静默跳过）",
          scanned == len(R.CORE_SMOKES) and not missing,
          "scanned=%d / total=%d · missing=%s" % (scanned, len(R.CORE_SMOKES), missing))
    check("B3 自食其规则（本 smoke 自身在 CORE_SMOKES 内且过契约）",
          _SELF in R.CORE_SMOKES)

    # ---------------- 突变探针（每条先证能变红）----------------
    # P1 禁用后置复跑（= 未修前的旧行为）⇒ 时序假红必须仍在
    check("P1 探针须造分歧（禁用后置 ⇒ 假红仍在：rc=1 / fail=1）",
          rc_off == 1 and out_off["summary"]["fail"] == 1 and ev_off == ["batch", "write_baseline"],
          "rc=%r fail=%r events=%r" % (rc_off, out_off["summary"]["fail"], ev_off))
    # P2 `_overlay` 若不覆盖只追加 ⇒ 同名条目重复 ⇒ 计数虚高
    dup = CCB._overlay([{"script": _RATCHET, "status": "FAIL", "rc": 1, "elapsed_s": 1.0}],
                       {"script": _RATCHET, "status": "PASS", "rc": 0, "elapsed_s": 2.0})
    naive = [{"script": _RATCHET, "status": "FAIL", "rc": 1, "elapsed_s": 1.0},
             {"script": _RATCHET, "status": "PASS", "rc": 0, "elapsed_s": 2.0}]
    check("P2 探针须造分歧（改为『不覆盖只追加』⇒ 同名 %d 条 ⇒ A4/A2 必红）"
          % len(naive), len(dup) == 1 and len(naive) == 2)
    # P3 后置结果若被丢弃（写死批次内 FAIL）⇒ A2 必红
    check("P3 探针须造分歧（丢弃后置结果 ⇒ fail=1 ⇒ A2 必红）",
          out_off["summary"]["fail"] == 1 and out_ok["summary"]["fail"] == 0)
    # P4 内联样例：有 check 但恒 return 0 ⇒ 判据必须判红
    bad_sample = ast.parse("import sys\n"
                           "def check(n, c, d=''):\n    pass\n"
                           "def main():\n    check('x', False)\n    return 0\n"
                           "if __name__ == '__main__':\n    sys.exit(main())\n")
    check("P4 探针须造分歧（样例『有 check + 恒 return 0』⇒ 判据必判红）",
          bool(_gate_calls(bad_sample)) and not _exit_channel(bad_sample))
    # P5 内联样例：有 check + 条件返回 ⇒ 判据必须**不**判红（证明判据非恒真）
    good_sample = ast.parse("import sys\n"
                            "def check(n, c, d=''):\n    pass\n"
                            "def main():\n    check('x', False)\n"
                            "    return 0 if True else 1\n"
                            "if __name__ == '__main__':\n    sys.exit(main())\n")
    check("P5 探针须造分歧（样例『有 check + 条件返回』⇒ 判据**不**判红，非恒真）",
          bool(_gate_calls(good_sample)) and _exit_channel(good_sample))

    # ---------------- 组 C：自测口径契约 ----------------
    print("\n== 组 C：自测口径契约（format 模板 + 禁 cwd 相对路径）==")
    # C1 `make_check(detail_fmt)` 是 str.format 模板，printf 模板必须当场 raise
    _ns, _buf = {}, io.StringIO()
    _ck = make_check(_ns, ok_key="P", bad_key="F", detail_fmt=" · {d}")
    with contextlib.redirect_stdout(_buf):
        _ck("样例判据", True, "详情X")
    _line = _buf.getvalue().strip()
    check("C1 🔴 make_check 拒 printf 模板（%s 型）∧ {d} 模板真插值"
          "（否则失败详情恒印字面量、被静默吞掉）",
          _fmt_guard_raises(" · %s") and not _fmt_guard_raises(" · {d}")
          and "详情X" in _line and "%s" not in _line,
          "raise(%s)=%s · 输出=%r" % (" · %s", _fmt_guard_raises(" · %s"), _line))

    # C2 门禁/脚本不许用 cwd 相对路径访问仓库产物（**全仓 glob · 不做白名单**）
    _cwd_files = []
    for _pat in (os.path.join(_HERE, "**", "*.py"),          # lda/ 全包（含 run_*.py）
                 os.path.join(_ROOT, "scripts", "*.py"),
                 os.path.join(_ROOT, "examples", "**", "*.py"),
                 os.path.join(_ROOT, "*.py")):                # 仓库根脚本
        _cwd_files.extend(glob.glob(_pat, recursive=True))
    _cwd_files = sorted(set(_cwd_files))
    _cwd_hits = []
    for _p in _cwd_files:
        _h = _cwd_relative_reads(open(_p, encoding="utf-8").read())
        if _h:
            _cwd_hits.append("%s%s" % (os.path.relpath(_p, _ROOT), _h))
    _run_names = {os.path.basename(p) for p in glob.glob(os.path.join(_HERE, "run_*.py"))}
    _scanned = {os.path.basename(p) for p in _cwd_files}
    check("C2 🔴 门禁/脚本不用 cwd 相对路径访问仓库产物"
          "（全仓 %d 个 .py 全扫 · CI 的 cwd 与手跑不同 ⇒ 否则同码两结论）"
          % len(_cwd_files),
          not _cwd_hits and _run_names <= _scanned and len(_cwd_files) >= 800,
          "违约=%s · 覆盖率=%d/%d" % (_cwd_hits if _cwd_hits else "无",
                                      len(_run_names & _scanned), len(_run_names)))

    # P6 make_check 守卫三向探针（printf 必 raise · format 不 raise · 纯字面量不 raise）
    _p6 = [_fmt_guard_raises(" · %s"), _fmt_guard_raises(" · %d"),
           not _fmt_guard_raises(" · {d}"), not _fmt_guard_raises(" (100%)"),
           not _fmt_guard_raises(" (50% done)"), not _fmt_guard_raises(None)]
    check("P6 探针须造分歧（printf 模板 raise ∧ format/纯字面量不 raise）",
          all(_p6), "p6=%s" % _p6)

    # P7 CWD 扫描器五向探针（真违约必命中 · 已锚定/经助手转发必不误报）
    _bad1 = "import os\np = os.path.join('examples', 'x.json')\nopen(p)\n"
    _bad2 = "open('docs/a.md')\n"
    _bad3 = ("import os, json\n"
             "def main():\n"
             "    p = os.path.join('reports', 'r.json')\n"
             "    return json.load(open(p))\n")
    _good1 = ("import os\n_R = '/repo'\n"
              "open(os.path.join(_R, 'examples', 'x.json'))\n")
    _good2 = ("import os\n_R = '/repo'\n"
              "def _read(rel):\n"
              "    with open(os.path.join(_R, rel)) as fh:\n"
              "        return fh.read()\n"
              "def main():\n"
              "    return _read(os.path.join('lda', 'x.py'))\n")
    _p7 = [len(_cwd_relative_reads(_bad1)) == 1,
           len(_cwd_relative_reads(_bad2)) == 1,
           len(_cwd_relative_reads(_bad3)) == 1,
           _cwd_relative_reads(_good1) == [],
           _cwd_relative_reads(_good2) == []]
    check("P7 探针须造分歧（三种相对读法必命中 ∧ 锚定/助手转发不误报）",
          all(_p7), "p7=%s" % _p7)

    print()
    return 0 if (globals().get("PASS", 0) and not globals().get("FAIL", 0)) else 1


if __name__ == "__main__":
    sys.exit(main())
