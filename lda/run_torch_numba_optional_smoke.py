"""LDA · torch/numba 可选依赖反向护栏（v0.9.53）。

铁律背景：torch / numba 在 pyproject.toml 中**仅作 optional extras**（[torch]/[numba]），
生产核心（lda_solver / lda_layout / lda_webui 导入链）不得硬依赖这二者。
T-8（v0.9.38）已去 GPU，但 fdtd3d_numba.py / fdtd3d_torch.py 仍残留模块级硬 import，
会在缺失库时令模块导入即崩溃——本护栏将其改为优雅降级（与 fdtd3d_waveguide_numba /
adjoint_fdtd3d 同范式），并锁死「无 torch/numba 也能 import 核心」这一不变量。

反向测试设计（铁律：新护栏必须反向测试会响）：
  [A] 正常环境（torch/numba 在场）：两后端 _HAVE_* = True，证明可选后端仍可加载。
  [B] 屏蔽环境（子进程内拦截 import torch/numba）：
        - fdtd3d_numba / fdtd3d_torch 模块级导入不崩溃（_HAVE_* = False）
        - lda_solver 包 + lda_webui.app 导入链无硬依赖
        - 调用入口明确抛 ImportError（而非 AttributeError 裸崩）
  若将来有人把 `import torch` 重新写回模块顶层硬 import，[B] 必红。
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap

PASS = 0
FAIL = 0


def check(name: str, ok: bool, info: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {name}" + (f"  ({info})" if info else ""))
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f"  ({info})" if info else ""))


# 在 lda_solver 目录注入 sys.path 后导入 fdtd3d_*（复刻 _ensure_solver_on_path 行为）
_BOOTSTRAP = textwrap.dedent(
    """
    import os, sys, builtins
    sys.path.insert(0, os.path.join(os.getcwd(), "lda_solver"))
    _orig = builtins.__import__
    def _block(name, *a, **k):
        if name.split('.')[0] in ('torch', 'numba'):
            raise ImportError('blocked for test: ' + name)
        return _orig(name, *a, **k)
    builtins.__import__ = _block
    import fdtd3d_numba as m
    import fdtd3d_torch as t
    assert m._HAVE_NUMBA is False, "fdtd3d_numba 必须在无 numba 时优雅降级"
    assert t._HAVE_TORCH is False, "fdtd3d_torch 必须在无 torch 时优雅降级"
    import lda_solver                      # 包 __init__ 仅 numpy 模块
    import lda_webui.app as app            # webui 导入链不得硬依赖 torch/numba
    for fn in (t.solve_spectrum_torch, t.run_greens_test_torch):
        try:
            fn({})
            raise SystemExit("ERROR: 入口未抛出 ImportError")
        except ImportError:
            pass
    print("OK_NO_TORCH_NUMBA")
    """
)


def _run_blocked_subprocess() -> tuple[bool, str]:
    """在屏蔽 torch/numba 的子进程里验证核心可导入。"""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.getcwd() + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-c", _BOOTSTRAP],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    ok = proc.returncode == 0 and "OK_NO_TORCH_NUMBA" in proc.stdout
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-3:]
    return ok, " | ".join(tail)


def main() -> int:
    print("[A] 正常环境（torch/numba 在场）：可选后端仍可加载")
    try:
        import os as _os
        sys.path.insert(0, _os.path.join(os.getcwd(), "lda_solver"))
        import fdtd3d_numba as m  # noqa: F401
        import fdtd3d_torch as t  # noqa: F401
        check("fdtd3d_numba 在场 _HAVE_NUMBA=True", m._HAVE_NUMBA is True)
        check("fdtd3d_torch 在场 _HAVE_TORCH=True", t._HAVE_TORCH is True)
    except Exception as e:  # noqa: BLE001
        check("正常环境导入两后端", False, f"{type(e).__name__}: {e}")

    print("[B] 屏蔽环境（子进程拦截 import torch/numba）：核心无硬依赖")
    ok, info = _run_blocked_subprocess()
    check("无 torch/numba 时核心可导入（fdtd3d_* 优雅降级 + lda_solver + lda_webui）",
          ok, info)

    print(f"\ntorch/numba 可选依赖护栏：{PASS} PASS / {FAIL} FAIL")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
