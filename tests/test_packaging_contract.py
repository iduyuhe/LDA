"""打包契约（T5.2）——把「`pip install -e .` 之后真的能用」钉成常驻判据。

T5.2 的验收是「实跑一次装成功 + `lda --help` 可用」。一次性实跑会随版本腐坏
（新增包忘登记 ⇒ 装出来缺模块；改了入口点 ⇒ 命令消失），所以这里把**结构性
前提**变成每轮都会跑的断言：

* `[tool.setuptools].packages` ≡ `lda/` 下**真实存在**的包 —— 新增包忘登记时
  立刻红（否则只会表现为「wheel 里少一个包」，本地 editable 装还照样能跑 ⇒ 假绿）；
* `[project.scripts] lda` 的目标模块可导入、属性可调用 —— 入口点不能悬空；
* 测试目录不进发行包。
"""
from __future__ import annotations

import os
import tomllib

import pytest


@pytest.fixture(scope="module")
def pyproject(repo_root):
    with open(repo_root / "pyproject.toml", "rb") as f:
        return tomllib.load(f)


def _real_packages(lda_root):
    """`lda/` 下真实存在的包（含 `__init__.py` 的目录），扁平命名空间。"""
    out = set()
    for name in os.listdir(lda_root):
        if name.startswith("__"):
            continue
        if os.path.isfile(os.path.join(lda_root, name, "__init__.py")):
            out.add(name)
    return out


def test_declared_packages_match_real_packages(pyproject, lda_root):
    """声明包集 ≡ 真实包集（双向）：少登记 ⇒ 装出来缺模块；多登记 ⇒ 构建报错。"""
    declared = set(pyproject["tool"]["setuptools"]["packages"])
    real = _real_packages(lda_root)
    assert declared == real, (
        f"未登记的真实包（装出来会缺）：{sorted(real - declared)}；"
        f"登记了但不存在的包：{sorted(declared - real)}"
    )


def test_package_dir_maps_to_lda_subtree(pyproject):
    pd = pyproject["tool"]["setuptools"]["package-dir"]
    assert pd.get("") == "lda", f"package-dir 须为 {{'': 'lda'}}，当前 {pd}"


def test_console_script_entrypoint_is_importable_and_callable(pyproject, lda_root):
    """`lda = "pkg.module:attr"` 的目标必须真的存在且可调用。

    这是「命令消失」类回归的最省力护栏：入口点写错时 `pip install -e .` 仍会
    成功（setuptools 不校验属性），只有真跑 `lda --help` 才暴露。
    """
    import importlib
    import sys

    scripts = pyproject["project"]["scripts"]
    assert "lda" in scripts, f"缺少 lda 命令入口：{list(scripts)}"
    target = scripts["lda"]
    assert ":" in target, f"入口点须形如 pkg.module:attr，当前 {target!r}"
    mod_name, attr = target.split(":", 1)

    if str(lda_root) not in sys.path:
        sys.path.insert(0, str(lda_root))
    mod = importlib.import_module(mod_name)
    fn = getattr(mod, attr, None)
    assert fn is not None, f"{target} 的属性不存在"
    assert callable(fn), f"{target} 不可调用"


def test_core_metadata_present(pyproject):
    proj = pyproject["project"]
    assert proj["requires-python"].startswith(">=")
    assert proj["dependencies"], "运行时依赖不得为空"
    assert proj["license"], "缺少 license 声明（MIT 开源约束）"
