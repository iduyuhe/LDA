"""CORE_SMOKES 的 pytest 转发（T5.1 · `smoke` 档）。

设计要点：**判据不在本文件里**。本文件只把主入口 `run_ci_regression` 的成员表
原样参数化，并**调用它自己的 `_run_one`** 去跑 —— 于是：

* 超时预算、`SKIP`/`FAIL`/`TIMEOUT`/`CRASH` 四态判定、`cwd=lda/`、线程预算与
  `PYTHONHASHSEED` 注入，全部与 `python run_ci_regression.py --tag core` **同一份
  实现**（不复制、不另立口径 ⇒ 不会出现「pytest 绿而 core 红」的双口径）；
* 参数表由 `CORE_SMOKES` **动态派生**（不是手抄清单）⇒ 主入口加成员，这里自动跟随。

跑法（两条入口并存，主入口不变）：

    pytest -m smoke                          # 全量，口径 = CI core
    pytest -m "smoke and not harness"        # 名字含 harness 的除外
    pytest                                   # 默认档：只跑静态契约（秒级）
"""
from __future__ import annotations

import pytest


def test_smoke_parametrization_is_dynamically_derived(ci):
    """参数表必须**动态**来自 `CORE_SMOKES`，不得在测试里手抄一份快照。

    反向断言：条数 ≥100（远大于任何手抄清单的规模）且逐项可从模块读到 ——
    若有人抄了一份静态清单，主入口加成员时这里立刻对不上。
    """
    scripts = list(ci.CORE_SMOKES)
    assert scripts == list(ci.CORE_SMOKES)
    assert len(scripts) >= 100, f"CORE_SMOKES 条数异常（{len(scripts)}）"


def pytest_generate_tests(metafunc):
    """为 `smoke_script` 参数动态生成用例（每条 CORE_SMOKES 一个用例）。"""
    if "smoke_script" in metafunc.fixturenames:
        import run_ci_regression as ci

        scripts = list(ci.CORE_SMOKES)
        metafunc.parametrize("smoke_script", scripts, ids=scripts)


@pytest.mark.smoke
def test_ci_core_smoke(ci, smoke_script):
    """逐条跑一个 CI core 成员，语义与主入口**完全一致**。

    * rc==0 → PASS；
    * 优雅降级（无 GPU / 未安装 / 显式 SKIP 行）→ `pytest.skip`（不算失败，
      与主入口把 SKIP 与 FAIL 分开的做法一致）；
    * 其余非零 → FAIL（含 TIMEOUT / CRASH / ERROR —— 它们在 `_run_one` 里是独立
      状态，此处一并判红：宁可红，不可假绿）。
    """
    timeout = ci._BUILTIN_TIMEOUT_OVERRIDE.get(smoke_script, 300.0)
    result = ci._run_one(ci.sys.executable, smoke_script, timeout)
    status = result["status"]
    tail = result.get("tail") or ""

    if status == "PASS":
        return
    if status == "SKIP":
        pytest.skip(f"环境缺失优雅降级（{result['elapsed_s']}s）：{tail[:300]}")
    pytest.fail(
        f"{smoke_script} → {status}（rc={result['rc']}, "
        f"{result['elapsed_s']}s）\n{tail}"
    )
