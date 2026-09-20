# -*- coding: utf-8 -*-
"""smoke 公共助手模块（v0.9.113 · 波次 2 · 源自 2026-09-19 全面代码审计 F-07）。

背景（实证，非推测）
--------------------
审计 F-07 记「`check()` 助手复制 86 份」。波次 2 的 AST 逐文件复测给出更精确的
结论：全仓 **97 处** `def check(`，按「忽略标识符/常量/属性名的 AST 骨架」分 **36 个
结构类**——即它们**不是同一个助手复制 86 次**，而是 36 个各自定制的局部助手共用了一个
名字。分歧点只有三类：

  ① **计数器机制**：`global PASS/FAIL` · `global _PASS/_FAIL` · `nonlocal passed/failed` ·
     `CHECKS.append((name, ok, detail))` · `report["checks"][key]` · `_FAILED.append(name)`
  ② **打印格式**：缩进（`"  "` vs `""`）· 详情分隔（`" —— "` / `"  ({d})"` / `"  |  "` /
     `"  ·  "` / `" — "`）· 详情是否**无条件**打印
  ③ **返回值**：`None` vs `bool(cond)`

本模块只收敛**真正重复**的那几类（可证明输出逐字等价），其余保持原样并在
`run_pyflakes_ratchet_smoke` 的「助手重复棘轮」里锁成基线——**只许降不许升**。

设计原则
--------
- **零行为变化**是硬要求：本模块的工厂函数按参数复现各文件原有 stdout 逐字输出与
  返回值；调用方**只删本地 `def`、换一行绑定**，其余代码（含模块级计数器）不动。
- `make_check(ns, ...)` 写入 **调用方的模块命名空间**（`ns=globals()`），因此调用方
  尾部照旧读 `PASS` / `FAIL` 无需改动 ⇒ 迁移是**单点改动**。
- 纯标准库、无副作用、不导入数值内核。
"""
from __future__ import annotations

import socket
import sys
import unittest

__all__ = ["free_port", "check_raise", "make_check", "Counter", "run_unittest_suite"]


class Counter:
    """PASS/FAIL 计数器（供不便复用模块全局名字的场景使用）。"""

    __slots__ = ("passed", "failed")

    def __init__(self):
        self.passed = 0
        self.failed = 0

    @property
    def total(self):
        return self.passed + self.failed

    def exit_code(self):
        """CI 约定：任一 FAIL ⇒ 非零退出。"""
        return 1 if self.failed else 0


def make_check(ns, ok_key="PASS", bad_key="FAIL", indent="  ",
               detail_fmt=None, always_detail=False, return_ok=False,
               detail_on="both"):
    """生成 ``check(name, cond, detail="")``，计数写进 ``ns[ok_key] / ns[bad_key]``。

    参数
    ----
    ns            : 计数所在命名空间（迁移场景传 ``globals()`` ⇒ 调用方尾部零改动）
    ok_key/bad_key: 通过 / 失败计数键名（如 ``"PASS"`` / ``"_FAIL"``）
    indent        : 行首缩进（原实现有 ``"  "`` 与 ``""`` 两种）
    detail_fmt    : 详情后缀模板（``str.format(d=detail)``），``None`` ⇒ 无详情后缀
    always_detail : True ⇒ 详情**无条件**打印（原实现有 ``f"  ({detail})"`` 不判空的一类）
    return_ok     : True ⇒ 返回 ``bool(cond)``（原实现有返回 None 与返回 cond 两类）
    detail_on     : ``"both"``（默认，详情非空即打）/ ``"fail"``（**仅失败**打详情）/
                    ``"pass"``（仅通过打详情）。原实现有一类只在失败时追详情
                    （``if (not ok) and detail: line += ...``，见
                    ``run_pyflakes_ratchet_smoke.py``）；该语义由本参数表达，
                    避免调用方为此另写一个局部助手。

    输出（与迁移前逐字一致）::

        {indent}[PASS|FAIL] {name}{detail 后缀（若需要）}
    """
    def check(name, cond, detail=""):
        ok = bool(cond)
        k = ok_key if ok else bad_key
        # `.get` 兜底：调用方若把计数器声明放在 `def check` 之后（或 `__main__` 内），
        # 原实现的 `global X; X += 1` 会 NameError，这里退化为自动建立。
        ns[k] = ns.get(k, 0) + 1
        suffix = ""
        if detail_fmt is not None:
            want = always_detail or bool(detail) and (
                detail_on == "both"
                or (detail_on == "fail" and not ok)
                or (detail_on == "pass" and ok))
            if want:
                suffix = detail_fmt.format(d=detail)
        print("%s[%s] %s%s" % (indent, "PASS" if ok else "FAIL", name, suffix))
        return ok if return_ok else None

    return check


def check_raise(cond, msg):
    """抛异常式 check：``print("OK  " + msg)`` / ``print("FAIL " + msg)``，返回 bool。

    对应结构类「`check(cond, msg)` 6 行 · 10 个文件」（drc / gds / ir_* / pipeline …）。
    """
    ok = bool(cond)
    print(("OK  " if ok else "FAIL ") + msg)
    return ok


def free_port():
    """取一个空闲本地端口（原 6 份 ``_free_port`` 的单一定义）。"""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# --------------------------------------------------------------------------- F-18
class _KitTextResult(unittest.TextTestResult):
    """在标准 TextTestResult 上加两行统一报告（不改其失败/错误输出，保证痕迹可判）。"""

    def addSuccess(self, test):
        super().addSuccess(test)
        self.stream.writeln("  [PASS] %s" % test.id().split(".")[-1])

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.stream.writeln("  [SKIP] %s  \u2014\u2014 %s" % (test.id().split(".")[-1], reason))


def run_unittest_suite(tc, title=None):
    """跑一个 ``unittest.TestCase``，但**用 smoke_kit 的统一报告/退出契约**。

    F-18（审计：19 个 smoke 用 unittest（84 test 方法）、其余用自研 check() ⇒
    「两套范式并存」）的处置：**统一「怎么报告、怎么退出」**，而不是把标准
    ``unittest`` 重写成第三套自研模板——

      · 每条 test 一行 ``  [PASS] <name>`` / ``  [SKIP] <name>``（与全仓 ``check()``
        家族的报告风格一致）；失败/错误仍走 ``unittest`` 标准 ``FAIL:`` / ``ERROR:``
        块（含完整 traceback）⇒ ``run_ci_regression`` 的「失败痕迹」正则
        （Traceback / AssertionError / 行首 FAIL）必然命中，**不会被误判 SKIP**；
      · **整 suite 只跑一次** ⇒ ``setUpClass`` / ``tearDownClass`` 语义与
        ``unittest.main()`` 逐位一致（不会每用例重跑类级夹具）；
      · 退出码与 ``unittest.main()`` 逐位一致：有 failure/error ⇒ 1；
        全过或全 skip ⇒ 0（CI 判定只看 rc）。
    """
    suite = unittest.TestLoader().loadTestsFromTestCase(tc)
    runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=0,
                                     resultclass=_KitTextResult)
    res = runner.run(suite)
    print("-" * 70)
    print("%s：%d 用例 · %d FAIL · %d ERROR · %d SKIP"
          % (title or tc.__name__, res.testsRun, len(res.failures),
             len(res.errors), len(res.skipped)))
    return 0 if res.wasSuccessful() else 1
