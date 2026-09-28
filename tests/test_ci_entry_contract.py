"""CI 入口契约（T5.1）——把「主入口的结构不变量」搬进 pytest。

这些判据**全部是静态的**（读文件 / 读配置 / 数条目，不起子进程、不跑数值），
故属默认档，`pytest` 一条命令秒级跑完。

为什么值得独立成文件：主入口 `run_ci_regression.py --tag core` 自己**没法把
自己**的成员表与配置对着 `pyproject.toml` 校一遍——而历史血案说明这恰恰是
最贵的失效模式（幽灵成员 ⇒ 账本 +1、判据全绿、那条 smoke 从未执行 = 假绿）。
"""
from __future__ import annotations

import os
import re
import tomllib

import pytest

# ---------------------------------------------------------------- fixture
@pytest.fixture(scope="module")
def pyproject(repo_root):
    with open(repo_root / "pyproject.toml", "rb") as f:
        return tomllib.load(f)


@pytest.fixture(scope="module")
def pytest_ini(pyproject):
    return pyproject["tool"]["pytest"]["ini_options"]


# ------------------------------------------------------- CORE_SMOKES 成员表
def test_core_smokes_members_exist(ci, lda_root):
    """每个 `CORE_SMOKES` 成员的文件**必须真实存在**（防幽灵成员 ⇒ 假绿）。

    对照 `run_ci_coverage_gate_smoke` 判据 ⑦/⑧：主入口那边用 `os.path.exists`
    **静默丢弃**不存在的项 ⇒ 登记一个建在别处的 smoke 会得到「账本 +1、全绿、
    从未执行」。那条血案是 v0.9.121；这里从 pytest 侧再钉一遍，使两个入口都拦。
    """
    missing = [s for s in ci.CORE_SMOKES if not (lda_root / s).is_file()]
    assert not missing, f"CORE_SMOKES 含不存在成员（幽灵 ⇒ 假绿）：{missing}"


def test_core_smokes_are_python_files_under_lda(ci, lda_root):
    bad = [s for s in ci.CORE_SMOKES
           if not s.endswith(".py") or os.path.isabs(s) or s.startswith("..")]
    assert not bad, f"CORE_SMOKES 成员须为 lda/ 下相对路径 .py：{bad}"


def test_core_smokes_no_duplicates(ci):
    dupes = sorted({s for s in ci.CORE_SMOKES if ci.CORE_SMOKES.count(s) > 1})
    assert not dupes, f"CORE_SMOKES 有重复项（会虚增条数）：{dupes}"


def test_pytest_entry_not_inside_core_smokes(ci):
    """🔴 本入口不得侵入主链路：pytest **不能**出现在 `CORE_SMOKES` 里。

    若哪天有人把 `pytest` 或某个 pytest-only 脚本登记进 core，CI 主链就会多出
    一条「依赖 pytest 已装」的成员 —— 依赖面被悄悄扩大，而 `CONTRIBUTING.md`
    明写主入口只依赖 numpy/scipy/jsonschema/pyflakes。
    """
    bad = [s for s in ci.CORE_SMOKES if "pytest" in s.lower()]
    assert not bad, f"CORE_SMOKES 不得含 pytest 相关成员：{bad}"


def test_timeout_override_keys_are_known_scripts(ci, lda_root):
    """超时覆盖表不得有**孤儿键**：键必须是真实存在的脚本（否则是死配置）。"""
    known = set(ci.CORE_SMOKES) | set(ci._discover_all())
    orphans = sorted(k for k in ci._BUILTIN_TIMEOUT_OVERRIDE if k not in known)
    assert not orphans, f"超时覆盖表含孤儿键（脚本不存在）：{orphans}"


def test_timeout_overrides_are_positive(ci):
    bad = [(k, v) for k, v in ci._BUILTIN_TIMEOUT_OVERRIDE.items()
           if not isinstance(v, (int, float)) or v <= 0]
    assert not bad, f"超时预算必须为正数：{bad}"


# ------------------------------------------------------------ pytest 自身配置
def test_pytest_collects_only_tests_dir(pytest_ini):
    """收集面锁死在 `tests/`：从根因上避开 `vendor/devsim_mirror` 的收集期
    `import devsim` 崩溃（2026-09-19 审计实测 rc=2 / 244.3s）。"""
    assert pytest_ini.get("testpaths") == ["tests"]


def test_pytest_ignores_third_party_isolation_zones(pytest_ini, repo_root):
    norec = pytest_ini.get("norecursedirs", [])
    missing = [p for p in ("vendor", "lda_cuda_venv", "node_modules")
               if p not in norec]
    assert not missing, f"norecursedirs 缺三方隔离区：{missing}（现在值：{norec}）"
    assert (repo_root / "vendor").is_dir()


def test_smoke_marker_registered_and_deselected_by_default(pytest_ini):
    """重档必须靠**已注册的 marker** 显式排除，而不是靠静默跳过。

    `addopts` 默认 `-m 'not smoke'`（快档秒级绿）· `pytest -m smoke` 跑 CI core
    全量（口径与主入口逐条一致）。marker 未注册 ⇒ `--strict-markers` 直接报错，
    杜绝「拼错 marker 名 ⇒ 悄悄全跑/悄悄全不跑」。
    """
    markers = pytest_ini.get("markers", [])
    assert any(m.split(":")[0].strip() == "smoke" for m in markers), markers

    addopts = pytest_ini.get("addopts", "")
    addopts = addopts if isinstance(addopts, str) else " ".join(addopts)
    assert re.search(r"-m\s+[\"']?not\s+smoke", addopts), (
        f"addopts 须默认排除 smoke 档（当前：{addopts!r}）")
    assert "--strict-markers" in addopts


def test_tests_dir_is_not_shipped_in_distribution(pyproject):
    """`tests/` 不得被打进发行包（setuptools 显式包列表里不应出现）。"""
    packages = pyproject["tool"]["setuptools"]["packages"]
    assert "tests" not in packages and not any(p.startswith("tests") for p in packages)
