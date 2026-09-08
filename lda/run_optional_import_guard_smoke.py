"""LDA · 可选后端（torch / numba / cupy）模块级硬依赖全包护栏（v0.9.59）。

背景（v0.9.53 治理⑤ 的收尾）：pyproject 中 torch/numba/cupy **仅作 optional extras**，
v0.9.53 已把核心导入链（fdtd3d_torch / fdtd3d_numba）改为 try/except 优雅降级，但
`activate_gpu_fdtd3d.py` / `run_fdtd3d3d_torch_selfcheck.py` / `run_large_grid.py` /
`verify_gpu_focused.py` 等**顶层 GPU 脚本**仍为模块级裸 `import torch`：一旦环境缺
torch，脚本不是"打印指引后退出"，而是 ImportError 裸崩。本护栏把这两件事钉死：

  ① 静态：`lda/` 包内**任何** .py 都不得在模块级（顶层，非 try / 非函数类体内）
     裸 import torch / numba / cupy。扫描范围是全包而非硬编码清单 —— 新增文件
     自动纳入，避免"清单会增长 ⇒ 断言静默漂移"的定时炸弹（v0.9.41 扩库铁律）。
  ② 动态：在**屏蔽 torch/numba/cupy 的子进程**里 runpy 实跑每个顶层 GPU 脚本，
     断言不裸崩（退出码语义 2 = 依赖不可用并打印指引）。测的是生产脚本本身。

反向测试（铁律：新护栏必须反向测试会响）：
  [R1] 静态扫描器喂"顶层裸 import torch"坏样本 → 必须抓到；喂"try 内 import"好样本
       → 必须放行（双向标定，防扫描器写反了还全绿）。
  [R2] 动态实跑喂一个"模块级裸 import torch"的临时坏脚本 → 必须裸崩（退出码≠2），
       证明步骤②真能区分"优雅降级"与"硬依赖"。
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PASS = 0
FAIL = 0

ROOT = Path(__file__).resolve().parent.parent          # D:\agent_LDA
PKG = ROOT / "lda"                                     # lda 包（lda_cuda_venv 在其外，天然排除）
OPT_MODULES = ("torch", "numba", "cupy")


def check(name: str, ok: bool, info: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {name}" + (f"  ({info})" if info else ""))
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f"  ({info})" if info else ""))


# ---------------------------------------------------------------------------
# ① 静态扫描：模块级硬依赖
# ---------------------------------------------------------------------------
def scan_module_level_hard_imports(src: str) -> list[str]:
    """返回源码中所有『模块级』（不在 try / 函数 / 类体内）的可选后端裸 import。"""
    tree = ast.parse(src)
    protected: set[int] = set()
    star = getattr(ast, "TryStar", ())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Try, star, ast.FunctionDef,
                             ast.AsyncFunctionDef, ast.ClassDef)):
            for sub in ast.walk(node):
                protected.add(id(sub))
    hits: list[str] = []
    for node in ast.walk(tree):
        if id(node) in protected:
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in OPT_MODULES:
                    hits.append(f"L{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in OPT_MODULES:
                hits.append(f"L{node.lineno}: from {node.module} import ...")
    return hits


# ---------------------------------------------------------------------------
# ② 动态实跑：屏蔽 torch/numba/cupy 后 runpy 顶层脚本
# ---------------------------------------------------------------------------
_BOOT = r'''
import builtins, contextlib, io, os, runpy, sys
script = sys.argv[1]
# 🔴 必须重置 argv：runpy 只改 argv[0]，残留的 argv[1]（本引导脚本用来收脚本路径）
#    会被带 argparse 的脚本当成"未知位置参数"而误报 usage 错误，把真结果盖掉。
sys.argv = [script]
sys.path.insert(0, os.path.dirname(os.path.abspath(script)))
sys.path.insert(0, os.getcwd())
_orig = builtins.__import__
def _block(name, *a, **k):
    if name.split(".")[0] in ("torch", "numba", "cupy"):
        raise ImportError("blocked for test: " + name)
    return _orig(name, *a, **k)
builtins.__import__ = _block
code, buf = 0, io.StringIO()
try:
    with contextlib.redirect_stdout(buf):
        runpy.run_path(script, run_name="__main__")
except SystemExit as e:
    code = e.code if isinstance(e.code, int) else 0
except BaseException as e:                      # noqa: BLE001
    print("CRASH", type(e).__name__, e)
    code = -999
print("EXITCODE", code)
print("HINT_TORCH", "torch" in buf.getvalue().lower())
'''


def run_blocked(script: str) -> tuple[int, bool, str]:
    """在屏蔽可选后端的子进程里实跑脚本，返回 (退出码, stdout 是否提到 torch, 尾部日志)。"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-c", _BOOT, script],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=120,
    )
    out = proc.stdout or ""
    code, hint = -999, False
    for line in out.splitlines():
        if line.startswith("EXITCODE "):
            code = int(line.split()[1])
        if line.startswith("HINT_TORCH "):
            hint = line.split()[1] == "True"
    tail = (out + (proc.stderr or "")).strip().splitlines()[-2:]
    return code, hint, " | ".join(tail)


GUARD_TOKENS = ("HAVE_TORCH", "HAVE_NUMBA", "HAVE_CUPY")


def _has_guard(src: str) -> bool:
    """是否有可选后端守卫标志（兼容 `_HAVE_TORCH` 与 `HAVE_NUMBA` 两种历史命名）。"""
    return any(tok in src for tok in GUARD_TOKENS)


def _opt_named_modules() -> list[Path]:
    """文件名直接点名可选后端（*torch* / *numba* / *cupy*）的模块与脚本。"""
    keys = ("torch", "numba", "cupy")
    return [p for p in PKG.rglob("*.py") if any(k in p.name for k in keys)]


def _gpu_scripts() -> list[Path]:
    """顶层 GPU/性能工具脚本（自动发现，非硬编码清单）。

    判定三条同时成立才是"要守护的顶层脚本"：
      ① 文件名匹配本项目顶层脚本命名约定 run_ / activate_ / verify_；
      ② 含 `__name__ == "__main__"`（可直接执行）；
      ③ 含 `_HAVE_TORCH` 守卫标志（作者已按可选依赖范式处理，值得被守护）。

    ⚠️ 不能只按"源码含 torch + 有 __main__"来找：求解核模块
    （fdtd2d_ring.py / fdtd3d_torch.py / adjoint_fdtd.py ...）自带 demo 型
    `__main__` 块，实跑会真的启动长时间 FDTD（>300s）甚至因缺后端而崩，
    把噪声灌进本护栏。核模块的"可 import 不崩"由 v0.9.53 的
    run_torch_numba_optional_smoke.py 负责，本护栏只管顶层脚本。
    """
    pat = re.compile(r"^(run_|activate_|verify_)")
    found = []
    for p in sorted((PKG / "lda_solver").rglob("*.py")):
        if not pat.match(p.name):
            continue
        try:
            src = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "_HAVE_TORCH" in src and '__name__ == "__main__"' in src:
            found.append(p)
    return found


def main() -> int:
    print("=" * 70)
    print(">> LDA 可选后端（torch/numba/cupy）模块级硬依赖护栏")
    print("=" * 70)

    # ---- R1：扫描器双向标定（先证明扫描器本身有效） ----
    print("\n[R1] 静态扫描器双向标定")
    bad = scan_module_level_hard_imports("import torch\nimport numpy as np\n")
    check("R1-a 坏样本（顶层裸 import torch）必须被抓到",
          len(bad) == 1 and bad[0].endswith("import torch"), str(bad))
    good = scan_module_level_hard_imports(
        "try:\n    import torch\n    _HAVE = True\nexcept Exception:\n"
        "    torch = None\n    _HAVE = False\n"
    )
    check("R1-b 好样本（try 内 import）必须放行", good == [], str(good))
    good2 = scan_module_level_hard_imports(
        "def f():\n    import torch\n    return torch\n"
    )
    check("R1-c 延迟导入（函数体内）必须放行", good2 == [], str(good2))
    bad2 = scan_module_level_hard_imports("from numba import njit\n")
    check("R1-d 坏样本（顶层 from numba import）必须被抓到", len(bad2) == 1, str(bad2))
    check("R1-e 守卫探测：无 HAVE_* 标志的源码必须判为缺守卫",
          not _has_guard("import numpy as np\nx = 1\n"))
    check("R1-f 守卫探测：含 _HAVE_NUMBA 的源码必须判为有守卫",
          _has_guard("try:\n    from numba import njit\n    _HAVE_NUMBA = True\n"
                     "except Exception:\n    _HAVE_NUMBA = False\n"))

    # ---- ① 全包静态扫描 ----
    print("\n[1] 全包静态扫描：lda/ 下不得有模块级裸 import torch/numba/cupy")
    py_files = sorted(PKG.rglob("*.py"))
    offenders: dict[str, list[str]] = {}
    unparsable: list[str] = []
    for p in py_files:
        try:
            src = p.read_text(encoding="utf-8", errors="ignore")
            hits = scan_module_level_hard_imports(src)
        except (OSError, SyntaxError) as exc:
            unparsable.append(f"{p.relative_to(ROOT)}: {type(exc).__name__}")
            continue
        if hits:
            offenders[str(p.relative_to(ROOT))] = hits
    check("1-a 扫描覆盖文件数 > 200（防止范围写窄后静默失效）",
          len(py_files) > 200, f"scanned={len(py_files)}")
    check("1-b 无文件解析失败", not unparsable, "; ".join(unparsable[:3]))
    check("1-c 全包模块级硬依赖 = 0",
          not offenders, "; ".join(f"{k}:{v}" for k, v in list(offenders.items())[:5]))

    # 1-d：点名可选后端的模块/脚本必须自带 HAVE_* 守卫（含会增长 ⇒ 自动纳入新增文件）
    opt_named = _opt_named_modules()
    missing_guard = []
    for p in opt_named:
        try:
            if not _has_guard(p.read_text(encoding="utf-8", errors="ignore")):
                missing_guard.append(str(p.relative_to(ROOT)))
        except OSError:
            continue
    check("1-d 文件名含 torch/numba/cupy 的模块必须有 HAVE_* 守卫标志",
          not missing_guard and len(opt_named) >= 5,
          f"checked={len(opt_named)} missing={missing_guard}")

    # ---- ② 屏蔽环境实跑顶层 GPU 脚本 ----
    print("\n[2] 屏蔽 torch/numba/cupy 后实跑顶层 GPU 脚本（不得裸崩）")
    scripts = _gpu_scripts()
    check("2-a 自动发现顶层 GPU 脚本 >= 4（防止清单写死后收不到新脚本）",
          len(scripts) >= 4, f"found={len(scripts)}: " + ", ".join(p.name for p in scripts))
    for p in scripts:
        code, hint, tail = run_blocked(str(p))
        rel = p.relative_to(ROOT)
        if code == 2:
            check(f"2-{p.name} 优雅降级（退出码 2 + 打印 torch 指引）", hint, tail)
        else:
            # 环境真的装了 torch：则脚本会真跑到底（0/1），也不允许裸崩
            check(f"2-{p.name} 未裸崩（退出码 {code}；本机 torch 在场则为真跑）",
                  code in (0, 1), tail)

    # ---- R2：动态实跑反向测试 ----
    print("\n[R2] 动态实跑反向测试：模块级裸 import 的坏脚本必须裸崩")
    with tempfile.TemporaryDirectory() as td:
        bad_script = Path(td) / "bad_hard_import.py"
        bad_script.write_text(
            'import torch\n\n\ndef main():\n    return 0\n\n\n'
            'if __name__ == "__main__":\n    raise SystemExit(main())\n',
            encoding="utf-8",
        )
        code, _, tail = run_blocked(str(bad_script))
        check("R2 坏脚本（顶层裸 import torch）必须裸崩退出码 -999，而非优雅 2",
              code == -999, f"code={code} | {tail}")

    print("\n" + "=" * 70)
    print(f">> 结果：{PASS} PASS / {FAIL} FAIL")
    print("=" * 70)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
