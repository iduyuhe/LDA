"""pytest 入口的公共装配（T5.1 · **双入口**中的第二入口）。

本仓库的**主入口**仍是 `python run_ci_regression.py --tag core`（见 `CONTRIBUTING.md`
与 `pyproject.toml` 的 `[tool.pytest.ini_options]`）。pytest 是**并存的第二入口**，
只做三件事：

1. 把 `lda/`（包根）放上 `sys.path`，使扁平 `lda_*` 命名空间与仓内 smoke 脚本
   都能被直接 `import`；
2. 提供极小的会话夹具（`repo_root` / `lda_root` / `ci`），避免每个测试文件各自
   重复路径推导；
3. 让 pytest 的收集面**只**是本目录（配 `testpaths = ["tests"]`），从根因上避开
   三方隔离区（`vendor/devsim_mirror` 收集期 `import devsim` 会让 pytest 整体
   error，2026-09-19 审计实测 rc=2 / 244.3s）。

🔴 红线（本入口不得越界）
-----------------------
* **不改 CI 主链路口径**：`run_ci_regression.CORE_SMOKES` 一字不动；
* **pytest 自身不进 `CORE_SMOKES`**：否则 CI 主链会多出一条「依赖 pytest 已装」
  的成员，把 CI 的依赖面悄悄扩大（由 `tests/test_ci_entry_contract.py` 机器守护）；
* **判决逻辑单一来源**：smoke 判据仍然只在 smoke 里定义，pytest 只做**转发**
  （见 `tests/test_smoke_core.py`），不复制判据、不另立口径。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_LDA_ROOT = _REPO_ROOT / "lda"
if str(_LDA_ROOT) not in sys.path:
    sys.path.insert(0, str(_LDA_ROOT))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """仓库根（含 `pyproject.toml`）。"""
    return _REPO_ROOT


@pytest.fixture(scope="session")
def lda_root() -> Path:
    """包根 `lda/`（扁平 `lda_*` 命名空间所在目录）。"""
    return _LDA_ROOT


@pytest.fixture(scope="session")
def ci():
    """`run_ci_regression` 模块——复用其 `_run_one` / 超时表 / SKIP 语义。"""
    import run_ci_regression

    return run_ci_regression
