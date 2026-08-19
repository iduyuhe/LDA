"""LDA · L2-B 第三步 · CUDA 版 torch 轮子安装器（主权 3D 核 GPU 激活前置）。

背景：本机（沙箱）实测 download.pytorch.org CDN 限速，1.7GB 轮子难以下完；
故提供官方源 + 清华 TUNA 镜像双回退 + 装后完整性校验。

用途：在"自配 GPU 算力"的部署机上运行（该机需 NVIDIA 驱动 + 匹配 CUDA）。
      GPU 激活后重跑 activate_gpu_fdtd3d.py 即完成 L2-B 第三步验收。

用法：
  python install_cuda_torch.py            # 检测环境 -> 装 CUDA torch（镜像回退）
  python install_cuda_torch.py --check    # 仅检测当前环境，不安装
  python install_cuda_torch.py --cu 128   # 指定 cu 版本（默认自动选 128）
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys


def _detect_cu():
    """优先用 nvidia-smi 推断驱动支持的 CUDA 主版本；否则默认 128。"""
    smi = shutil.which("nvidia-smi")
    if smi:
        try:
            out = subprocess.run([smi, "--query-gpu=driver_version",
                                  "--format=csv,noheader"],
                                 capture_output=True, text=True, timeout=20)
            if out.returncode == 0 and out.stdout.strip():
                return "128"  # 当前主流驱动均支持 12.x；固定 128 最稳
        except Exception:
            pass
    return "128"


def _check_current():
    print(">>> 当前环境检测：")
    try:
        import torch
        print(f"  torch 版本      : {torch.__version__}")
        print(f"  CUDA build      : {torch.version.cuda}")
        print(f"  cuda.is_available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"  GPU             : {torch.cuda.get_device_name(0)}")
            return True
        print("  -> 当前为 CPU 轮子或无 GPU，需安装 CUDA 轮子。")
        return False
    except ImportError:
        print("  -> 未安装 torch，需全新安装 CUDA 轮子。")
        return False


def _pip_install(index_url):
    print(f"  >> pip install（index={index_url}）...")
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade",
           "torch", "--index-url", index_url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        # 打印尾部错误便于诊断
        tail = "\n".join(r.stderr.strip().splitlines()[-8:])
        print("  !! 安装失败：\n" + tail)
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="仅检测，不安装")
    ap.add_argument("--cu", default=None, help="cu 版本，如 128（默认自动）")
    args = ap.parse_args()

    if args.check:
        _check_current()
        return

    cu = args.cu or _detect_cu()
    print(f">>> 目标 CUDA 轮子：cu{cu}")
    if _check_current():
        print(">>> 已具备 CUDA torch，无需重装。直接跑 activate_gpu_fdtd3d.py。")
        return

    # 双源回退：官方 -> 清华 TUNA 镜像
    sources = [
        f"https://download.pytorch.org/whl/cu{cu}",
        f"https://mirrors.tuna.tsinghua.edu.cn/pytorch/whl/cu{cu}",
    ]
    ok = False
    for src in sources:
        if _pip_install(src):
            ok = True
            break
        print(f"  -> 源 {src} 失败，尝试下一个。")

    if not ok:
        print("\n>>> 所有源安装失败。排查：")
        print("  - 网络是否能访问上述源（国内优先 TUNA 镜像）。")
        print("  - 磁盘空间是否足够（CUDA 轮子 ~1.7GB）。")
        print("  - 可手动下载轮子后离线安装：")
        print(f"      pip install <torch-cu{cu}-xxx.whl>")
        return

    # 装后校验
    print("\n>>> 装后校验：")
    if _check_current():
        print(">>> 成功。下一步：python activate_gpu_fdtd3d.py")
    else:
        print(">>> 安装完成但 CUDA 仍不可用：检查 NVIDIA 驱动与 CUDA 版本匹配。")


if __name__ == "__main__":
    main()
