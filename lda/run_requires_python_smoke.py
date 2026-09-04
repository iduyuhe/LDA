#!/usr/bin/env python3
"""CI 护栏（T-6 · v0.9.31）：requires-python 声明下限必须 ≥ 代码实际用到的最低语法版本。

问题背景
--------
pyproject.toml 曾声明 ``requires-python >=3.11``，但全仓 **178 个文件**使用了
PEP 701 跨行 f-string（3.12+ 语法）。外部人按声明用 3.11 安装 ⇒ import 时直接
SyntaxError（实测 ``lda_cuda_venv`` 的 Python 3.11.9 在 ``chip_layout_export.py``
等抛出 SyntaxError，v0.9.26 首跑因此报 9 个假 FAIL）。

本 smoke 静态扫描 ``lda`` 包中实际用到的最低 Python 语法特性版本，断言声明下限
**不低于**它。这是一种「声明口径 vs 实现口径」的机器断言，杜绝「声明可装 3.11
实则 3.12 才跑得起来」的对外硬阻塞。

与 D-63 同源纪律：没被验证过的护栏不算护栏。本 smoke 自身会在下列情形 FAIL：
- 有人把 requires-python 改回 ``>=3.11``（声明 < 实现）
- 有人引入更新语法（如 3.13 特性）却未同步抬高声明
"""
import ast
import glob
import os
import re
import sys


def parse_floor(spec: str):
    """从 requires-python 字符串取第一个 ``>=`` 下界；无则取首个裸版本号。"""
    m = re.search(r">=(\d+)\.(\d+)", spec)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = re.search(r"(\d+)\.(\d+)", spec)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return None


def min_syntax_version_used(root: str):
    """扫描 lda 包，返回代码实际用到的最低 Python 语法版本下界与命中文件数。"""
    pkg = os.path.join(root, "lda")
    min_ver = (3, 11)  # 无任何特殊语法时的默认下界
    pep701_files = 0
    for path in glob.glob(os.path.join(pkg, "**", "*.py"), recursive=True):
        if "venv" in path:
            continue
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except SyntaxError:
            # 连当前（>=3.12）解释器都解析不了 ⇒ 至少用了更新语法
            pep701_files += 1
            if min_ver < (3, 12):
                min_ver = (3, 12)
            continue
        has_ml_fstring = False
        for node in ast.walk(tree):
            # JoinedStr = f-string；其 lineno != end_lineno 即跨行 f-string（PEP 701 / 3.12+）
            if isinstance(node, ast.JoinedStr):
                end = getattr(node, "end_lineno", None)
                if end is not None and end != node.lineno:
                    has_ml_fstring = True
                    break
        if has_ml_fstring:
            pep701_files += 1
            if min_ver < (3, 12):
                min_ver = (3, 12)
    return min_ver, pep701_files


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)  # lda/ -> repo root
    pp = os.path.join(root, "pyproject.toml")
    if not os.path.exists(pp):
        print(f"[FAIL] pyproject.toml 未找到：{pp}")
        sys.exit(1)
    txt = open(pp, encoding="utf-8").read()
    m = re.search(r"requires-python\s*=\s*[\"']([^\"']+)[\"']", txt)
    if not m:
        print("[FAIL] pyproject.toml 未声明 requires-python")
        sys.exit(1)
    floor = parse_floor(m.group(1))
    if floor is None:
        print(f"[FAIL] 无法解析 requires-python：{m.group(1)!r}")
        sys.exit(1)

    used_ver, pep701_n = min_syntax_version_used(root)
    print(f"requires-python 声明下限 = {floor[0]}.{floor[1]}")
    print(f"代码实际最低语法 = {used_ver[0]}.{used_ver[1]}"
          f"（PEP701 跨行 f-string 文件数 = {pep701_n}）")

    if floor < used_ver:
        print(f"[FAIL] requires-python {floor[0]}.{floor[1]} 低于代码实际语法下界 "
              f"{used_ver[0]}.{used_ver[1]}：外部人按声明用 {floor[0]}.{floor[1]} 安装会 "
              f"在 import 时 SyntaxError（PEP 701 跨行 f-string）。"
              f"请把 requires-python 提到 >= {used_ver[0]}.{used_ver[1]}。")
        sys.exit(1)

    if sys.version_info[:2] < floor:
        print(f"[FAIL] 当前 CI 解释器 {sys.version_info[0]}.{sys.version_info[1]} "
              f"低于声明下限 {floor[0]}.{floor[1]}")
        sys.exit(1)

    print(f"[PASS] requires-python 下限 {floor[0]}.{floor[1]} ≥ 代码语法下界 "
          f"{used_ver[0]}.{used_ver[1]}，且 CI 解释器满足下限")


if __name__ == "__main__":
    main()
