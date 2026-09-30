"""真机 ORACLE **import 边界** CI 门禁（P2.4 · 2026-09-30）。

验收判据（LDA_P2_实施规划_2026-09-30.md §3 P2.4）：**内核零依赖不被污染**
（CI 门禁守 import 边界）。本 smoke 把「可选层 real_machine_oracle 不得被内核
反向 import」从约定下沉为机器守卫：

  A. 内核模块（golden / benchmarks / harness / verification_adapters /
     empirical_bank / empirical_m6 / provenance / report / lda_solver 入口 /
     lda_design 入口）**不得** import `real_machine_oracle`（含桥接示例层
     `real_machine_oracle_example`）—— AST 扫描 Import/ImportFrom 节点，
     **不扫 docstring**（full_vector_mode_solver.py 的 docstring 提及本层属正常
     技术表述，不应触发）。
  B. 可选层 `real_machine_oracle.py` 自身**仅依赖 `lda_pdk` + 标准库**——
     证明依赖方向是**单向**（内核 ⊥ 可选层），可选层不反向拉拽内核。

零真实数据、纯静态 AST、秒级、不污染任何运行时状态。
"""
import ast
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 仓库根
_LDA = os.path.join(_ROOT, "lda")


# 🔴 内核受守护模块（显式清单：文档化究竟哪些内核面被守）。
_KERNEL_MODULES = [
    "lda/lda_harness/golden.py",
    "lda/lda_harness/benchmarks.py",
    "lda/lda_harness/harness.py",
    "lda/lda_harness/verification_adapters.py",
    "lda/lda_harness/empirical_bank.py",
    "lda/lda_harness/empirical_m6.py",
    "lda/lda_harness/provenance.py",
    "lda/lda_harness/report.py",
    "lda/lda_solver/full_vector_mode_solver.py",
    "lda/lda_design/__init__.py",
]

_FORBIDDEN_OPTIONAL_IMPORTS = ("real_machine_oracle", "real_machine_oracle_example")

# 可选层允许依赖的包前缀（单向依赖铁律）。
_OPTIONAL_LAYER_ALLOWED_PREFIXES = ("lda_pdk",)


def _imports_of(path: str):
    """返回该文件所有 import 的「模块名 / 被导入名」集合（AST，不含 docstring）。"""
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.append(a.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            names.append(mod)
            for a in node.names:
                names.append((mod + "." + a.name) if mod else a.name)
    return names


def main() -> int:
    fails = []

    # A. 内核模块不得 import 可选层（含桥接示例）。
    for rel in _KERNEL_MODULES:
        path = os.path.join(_ROOT, rel)
        if not os.path.exists(path):
            fails.append("内核模块缺失（清单过期）：%s" % rel)
            continue
        for imp in _imports_of(path):
            base = imp.split(".")[0]
            if base in _FORBIDDEN_OPTIONAL_IMPORTS:
                fails.append("import 边界违反：内核 %s 反向 import %r"
                            "（内核不得依赖可选层）" % (rel, imp))

    # B. 可选层 real_machine_oracle.py 仅依赖 lda_pdk + 标准库（单向）。
    opt_path = os.path.join(_LDA, "lda_harness", "real_machine_oracle.py")
    if not os.path.exists(opt_path):
        fails.append("可选层 real_machine_oracle.py 缺失")
    else:
        for imp in _imports_of(opt_path):
            base = imp.split(".")[0]
            if base in ("real_machine_oracle", "real_machine_oracle_example"):
                continue  # 自引用忽略
            if base in _FORBIDDEN_OPTIONAL_IMPORTS:
                fails.append("依赖方向违反：可选层反向 import %r" % imp)
                continue
            # 标准库（无点、且非 lda_* 包）放行；lda_* 仅允许 lda_pdk。
            if "." not in base and base not in _FORBIDDEN_OPTIONAL_IMPORTS:
                continue
            if not any(base == p or base.startswith(p + ".")
                       for p in _OPTIONAL_LAYER_ALLOWED_PREFIXES):
                fails.append("可选层依赖越界：real_machine_oracle.py import %r"
                            "（仅允许 %s + 标准库）"
                            % (imp, _OPTIONAL_LAYER_ALLOWED_PREFIXES))

    if fails:
        print("FAIL")
        for f in fails:
            print("  -", f)
        return 1
    print("PASS · import 边界守卫生效（内核 %d 模块零反向依赖可选层；"
          "可选层仅依赖 %s + 标准库，依赖方向单向）"
          % (len(_KERNEL_MODULES), _OPTIONAL_LAYER_ALLOWED_PREFIXES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
