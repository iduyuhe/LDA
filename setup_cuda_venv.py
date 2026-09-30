"""LDA · 一键预置 GPU/CUDA 隔离 venv（可复现 recipe，不污染用户/仓库环境）。

用法
----
    python setup_cuda_venv.py            # 创建（若不存在）+ 安装 torch cu128 + 校验
    python setup_cuda_venv.py --check    # 仅校验已预置的 venv，不安装

约束
----
  · 目标目录固定为 ``./lda_cuda_venv`` —— 已在 ``.gitignore`` 排除，故**不进 git
    追踪、不污染仓库与用户全局 Python 环境**（三方隔离）。
  · torch 经 CUDA 专用索引安装：
        --index-url https://download.pytorch.org/whl/cu128
  · 若安装被网络/沙箱阻断（审计 R7 缺口），**明确报错并以非零码退出**，绝不假装
    成功；同时打印手动补齐指引，供有外网/CUDA 机器的开发者本地补齐。

配套门禁：``lda/run_cuda_venv_selfcheck_smoke.py``（软/Advisory，CI 中 venv 缺席
即 SKIP，不阻断正确性门禁）。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV_DIR = HERE / "lda_cuda_venv"
VENV_PY = VENV_DIR / "Scripts" / "python.exe"
INDEX_URL = "https://download.pytorch.org/whl/cu128"
TORCH_SPEC = "torch>=2.0"


def _run(cmd) -> int:
    print("+ " + " ".join(str(c) for c in cmd))
    return subprocess.call(cmd)


def create_or_check(check_only: bool) -> int:
    if not VENV_PY.is_file():
        if check_only:
            print(f"[SKIP] 未预置 CUDA venv：{VENV_DIR}")
            print("       本环境 GPU 后端将自动回退 numpy/cpu（属 advisory，不影响门禁）。")
            print("       如需预置，运行： python setup_cuda_venv.py")
            return 0
        print(f"[*] 创建隔离 venv：{VENV_DIR}")
        rc = _run([sys.executable, "-m", "venv", str(VENV_DIR)])
        if rc != 0:
            print("[FAIL] venv 创建失败", file=sys.stderr)
            return rc

    # 校验 torch 是否已是健康的 CUDA build
    probe = (
        "import sys, torch\n"
        "print('TORCH', torch.__version__)\n"
        "print('CUDA_BUILD', torch.version.cuda or '')\n"
        "print('CUDA_AVAIL', torch.cuda.is_available())\n"
    )
    try:
        proc = subprocess.run([str(VENV_PY), "-c", probe],
                              capture_output=True, text=True, timeout=60)
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] 无法在 venv 内运行 torch 探针：{exc}", file=sys.stderr)
        return 2
    out = (proc.stdout or "") + (proc.stderr or "")
    print(out.strip())

    healthy = (proc.returncode == 0
               and "TORCH " in out
               and "CUDA_BUILD " in out
               and out.split("CUDA_BUILD ", 1)[1].splitlines()[0].strip() != "")
    if healthy:
        print("[PASS] 已预置健康的 CUDA torch：", end=" ")
        for ln in out.splitlines():
            if ln.startswith("TORCH "):
                print(ln.split(" ", 1)[1], end=" ")
            if ln.startswith("CUDA_BUILD "):
                print("(cuda", ln.split(" ", 1)[1], ")", end=" ")
        print()
        return 0

    if check_only:
        print("[FAIL] venv 存在但 torch 非健康 CUDA build；请重建。", file=sys.stderr)
        return 2

    print("[*] 安装/升级 torch CUDA wheel ...")
    rc = _run([str(VENV_PY), "-m", "pip", "install", "--upgrade",
               "--index-url", INDEX_URL, TORCH_SPEC])
    if rc != 0:
        print("[FAIL] torch CUDA wheel 安装失败（可能网络/沙箱阻断，审计 R7 缺口）。",
              file=sys.stderr)
        print("       手动补齐指引：", file=sys.stderr)
        print("         1) 进入有外网/CUDA 的机器；", file=sys.stderr)
        print(f"         2) .\\lda_cuda_venv\\Scripts\\python.exe -m pip install "
              f"--index-url {INDEX_URL} {TORCH_SPEC}", file=sys.stderr)
        print("         3) 重新运行 python setup_cuda_venv.py --check 校验。",
              file=sys.stderr)
        return rc
    # 安装后复校
    return create_or_check(check_only=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="预置 LDA GPU/CUDA 隔离 venv")
    ap.add_argument("--check", action="store_true",
                    help="仅校验已预置 venv，不安装")
    args = ap.parse_args()
    return create_or_check(check_only=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
