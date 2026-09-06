"""LDA · CI 回归器「失败状态分类」门禁 smoke（v0.9.41）。

守护对象：**`run_ci_regression.py` 自身的失败状态记账**。

背景（2026-09-06 血案）：全量 core 回归里 `run_coupler_band_smoke.py` 偶发
**136.4s + 零输出 + 非零 rc** —— 单独重跑 267s ALL GREEN。Python 重定向到管道时
stdout 是块缓冲，进程被硬杀则缓冲全部丢失，故「非零 rc + 零输出」= 被外部杀死
（OOM / Kernel-Power 掉电 / 热保护），**不是断言失败**。

危害：若这类硬件抖动与断言 FAIL 混为一谈，后人会去"修"物理判据来对付一次
掉电 —— 那是本项目最危险的失真通道（参 v0.9.10 漏算 3.0103dB 从 84 条全绿下
溜过）。故单列 `CRASH` 状态，语义为「需人工复验，不是判据错」。

🔴 本 smoke 守护的真正红线：**新增失败状态若漏登记进 `_FAIL_STATUSES`，
`n_fail` 就统计不到 ⇒ 红灯变绿 ⇒ 静默假绿**。这是「宁红不假绿」的记账底线，
比 CRASH 分类本身更致命，故必须反向测试（撤掉登记必须立刻响）。

判据（6 项，全死标量/行为）：
  ① 硬杀模拟（非零 rc + 零输出）→ 判 CRASH，且 tail 含可操作提示
  ② 真断言失败（非零 rc + 有输出）→ 必须仍判 FAIL，不得被误吞为 CRASH
  ③ 正常 PASS（rc=0）→ 判 PASS
  ④ 混合状态计数：CRASH 必须计入 n_fail（漏计 = 假绿）
  ⑤ `_FAIL_STATUSES` 必须含 FAIL/ERROR/TIMEOUT/CRASH 四类
  ⑥ 🔴 反向测试：撤掉 CRASH 登记 → 计数必须下降（证明判据会响，非纸上谈兵）
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from run_ci_regression import _run_one, _FAIL_STATUSES  # noqa: E402

PY = sys.executable
_FIX1 = "_tmp_g1_crash_fixture.py"
_FIX2 = "_tmp_g1_fail_fixture.py"
_FIX3 = "_tmp_g1_pass_fixture.py"


def _write_fixtures() -> None:
    with open(os.path.join(_HERE, _FIX1), "w", encoding="utf-8") as f:
        f.write("import sys\nsys.exit(3)\n")          # 零输出 + 非零 rc
    with open(os.path.join(_HERE, _FIX2), "w", encoding="utf-8") as f:
        f.write("print('[FAIL] x')\n"                  # 有输出 = 真断言失败
                "print('AssertionError: 1 != 2')\n"
                "import sys\nsys.exit(1)\n")
    with open(os.path.join(_HERE, _FIX3), "w", encoding="utf-8") as f:
        f.write("print('[OK  ] ok')\nimport sys\nsys.exit(0)\n")


def _cleanup() -> None:
    for n in (_FIX1, _FIX2, _FIX3):
        p = os.path.join(_HERE, n)
        if os.path.exists(p):
            os.remove(p)


def main() -> int:
    ok = True

    def check(cond: bool, msg: str) -> None:
        nonlocal ok
        print(f"[{'OK  ' if cond else 'FAIL'}] {msg}")
        ok = ok and bool(cond)

    try:
        _write_fixtures()

        # ① 硬杀模拟 → CRASH
        r1 = _run_one(PY, _FIX1, 30.0)
        check(r1["status"] == "CRASH",
              f"① 硬杀模拟（rc≠0 + 零输出）判 CRASH：{r1['status']} rc={r1['rc']}")
        check("复验" in (r1["tail"] or ""),
              "① tail 含可操作提示（要求人工复验，非判据错）")

        # ② 真断言失败 → 仍 FAIL（不得被 CRASH 吞掉，否则丢掉真失败证据）
        r2 = _run_one(PY, _FIX2, 30.0)
        check(r2["status"] == "FAIL",
              f"② 真断言失败仍判 FAIL（未被误归 CRASH）：{r2['status']}")

        # ③ 正常 PASS 不受影响（rc=0 + 有输出 → PASS）
        r3 = _run_one(PY, _FIX3, 30.0)
        check(r3["status"] == "PASS",
              f"③ 正常通过（rc=0）判 PASS：{r3['status']}")

        # ④ 混合状态计数：CRASH 必须计入 n_fail
        fake = [{"status": s} for s in
                ("PASS", "CRASH", "FAIL", "TIMEOUT", "ERROR", "SKIP")]
        n_fail = sum(1 for x in fake if x["status"] in _FAIL_STATUSES)
        check(n_fail == 4,
              f"④ 混合状态 n_fail={n_fail}（期望 4：CRASH/FAIL/TIMEOUT/ERROR）")

        # ⑤ 四类齐全
        need = {"FAIL", "ERROR", "TIMEOUT", "CRASH"}
        check(need <= set(_FAIL_STATUSES),
              f"⑤ _FAIL_STATUSES 含四类：{_FAIL_STATUSES}")

        # ⑥ 🔴 反向测试：撤掉 CRASH 登记 → 计数必须下降（判据真的会响）
        stripped = tuple(s for s in _FAIL_STATUSES if s != "CRASH")
        n_stripped = sum(1 for x in fake if x["status"] in stripped)
        check(n_stripped == 3 and n_stripped < n_fail,
              f"⑥ 反向测试：撤掉 CRASH 登记后 n_fail {n_fail}→{n_stripped}"
              f"（判据会响，非纸上谈兵）")
    finally:
        _cleanup()

    print("\n" + ("CI 失败状态分类门禁: ALL GREEN" if ok
                  else "CI 失败状态分类门禁: FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
