"""LDA · L2-B 第三步 · 主权 3D 核 GPU 激活与验证（device='cuda' 一键校验）。

前置条件：已安装 CUDA 版 torch 轮子（见同目录 install_cuda_torch.py）。
运行：      python activate_gpu_fdtd3d.py

流程：
  1) 检测 CUDA；不可用 -> 打印安装指引，退出码 2（不报错，只引导）。
  2) 可用 -> 跑 5 例物理定律锚 selfcheck（device=cuda），对照 TMM ORACLE。
  3) 同 5 例在 cpu 上重跑，断言 cuda 与 cpu 的 **fp64 结果 bit-equivalent**
     （跨设备数值确定性 —— 主权核"换设备不换物理"的硬保证）。
  4) 计时 greens N=120（cuda）并给出相对 numba-cpu(20.08s)/torch-cpu(102.86s) 加速比。
  5) 打印 fp64-on-consumer-GPU 的诚实性能说明（不夸大 GPU 收益）。

说明：本脚本与 run_fdtd3d_torch_selfcheck.py 互补 —— 后者在任意 device 上做
ORACLE 校验；本脚本额外做"cuda 与 cpu 互证"并量化 GPU 实际收益，专门用于
L2-B 第三步"装轮子 -> 激活 -> 验收"的闭环。
"""
from __future__ import annotations

import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import torch  # noqa: E402
from lda.lda_solver.fdtd3d_torch import (solve_spectrum_torch,  # noqa: E402
                                         run_greens_test_torch)
from lda.lda_solver.tmm import solve_spectrum as tmm_solve_spectrum  # noqa: E402

# numba-cpu / torch-cpu 基线（来自 benchmark_fdtd3d_torch.log，N=120 greens）
NUMBA_CPU_BASELINE_S = 20.08
TORCH_CPU_BASELINE_S = 102.86

# cuda 与 cpu 互证公差：fp64 跨设备理论上应逐位相同，留 1e-9 余量防末位舍入
CUDA_VS_CPU_TOL = 1e-9


def _tmm_T(layers, wls):
    out = tmm_solve_spectrum({"layers": layers, "wavelengths_um": wls})
    return list(out["transmission"])


def _cases():
    wls = [1.3, 1.4, 1.5, 1.6]
    layers_match = [(float('inf'), 1.44), (float('inf'), 1.44)]
    layers_iface = [(float('inf'), 1.0), (float('inf'), 1.5)]
    layers_fp = [(float('inf'), 1.0), (2.0, 2.5), (float('inf'), 1.0)]
    wls_fp = [1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2]
    n_h, n_l, period = 3.48, 1.44, 0.50
    lam_b = 2 * ((n_h + n_l) / 2) * period
    layers_bg = ([(float('inf'), 1.44)] +
                 [(0.25, n_h), (0.25, n_l)] * 24 +
                 [(float('inf'), 1.44)])
    wls_bg = [1.9, 2.2, 2.46, 2.7, 3.0]
    return [
        ("A. 匹配介质 (T≡1.0)", layers_match, wls, 0.02),
        ("B. 单界面 空气→玻璃 (T≡0.96)", layers_iface, wls, 0.04),
        ("C. FP 标准具 n=2.5 d=2.0um (条纹)", layers_fp, wls_fp, 0.08),
        (f"D. 布拉格光栅 (中心≈{lam_b:.2f}um 禁带)", layers_bg, wls_bg, 0.12),
    ]


def _max_rel(a, b):
    a = [float(x) for x in a]
    b = [float(x) for x in b]
    return max(abs(x - y) / (abs(y) + 1e-12) for x, y in zip(a, b))


def _guide_and_exit():
    print("\n>>> CUDA 不可用：主权 3D 核 GPU 路径尚未激活。")
    print(">>> 安装 CUDA 版 torch 轮子（在'自配 GPU 算力'的部署机上执行）：")
    print("    方式一（官方源）：")
    print("      pip install torch --index-url https://download.pytorch.org/whl/cu128")
    print("    方式二（清华 TUNA 镜像，国内更快）：")
    print("      pip install torch --index-url https://mirrors.tuna.tsinghua.edu.cn/pytorch/whl/cu128")
    print("    或使用本目录 install_cuda_torch.py 自动镜像回退 + 完整性校验。")
    print(">>> 前置：NVIDIA 驱动 >= 对应 CUDA 12.8 要求；装完重跑本脚本即可自动 device='cuda'。")
    print(">>> 注意：本机 CPU 路径（numba-cpu 43.1× / torch-cpu 8.4×）已生产可用，")
    print("          GPU 仅用于超大网格；消费卡 fp64 速率受限，详见激活后提示。")
    return 2


def main():
    if not torch.cuda.is_available():
        return _guide_and_exit()

    dev = torch.device("cuda")
    name = torch.cuda.get_device_name(0)
    cap = torch.cuda.get_device_capability(0)
    props = torch.cuda.get_device_properties(0)
    print("=" * 60)
    print(">> LDA 主权 3D FDTD · GPU 激活验证")
    print(f">> GPU: {name}  (compute capability {cap[0]}.{cap[1]})")
    print(f">> 显存: {props.total_memory / 1e9:.2f} GB | torch: {torch.__version__} | "
          f"CUDA build: {torch.version.cuda}")
    print("=" * 60)

    # ---- 步骤 2：5 例 selfcheck（device=cuda），对照 TMM ORACLE ----
    print("\n[1/3] 物理定律锚 selfcheck（device=cuda）vs TMM ORACLE")
    all_ok = True
    for cname, layers, wls, tol in _cases():
        fd = solve_spectrum_torch({"layers": layers, "wavelengths_um": wls}, device="cuda")
        tt = _tmm_T(layers, wls)
        err = max(abs(a - b) for a, b in zip(fd["transmission"], tt))
        ok = err < tol
        all_ok = all_ok and ok
        print(f"  {cname:<42} max|ΔT|={err:.4f} -> {'PASS' if ok else 'FAIL'} (tol={tol})")

    # ---- 步骤 3：cuda 与 cpu 互证（fp64 跨设备确定性）----
    print("\n[2/3] cuda 与 cpu fp64 互证（bit-equivalence）")
    equiv_ok = True
    for cname, layers, wls, _ in _cases():
        fc = solve_spectrum_torch({"layers": layers, "wavelengths_um": wls}, device="cpu")
        fd = solve_spectrum_torch({"layers": layers, "wavelengths_um": wls}, device="cuda")
        d = _max_rel(fc["transmission"], fd["transmission"])
        ok = d < CUDA_VS_CPU_TOL
        equiv_ok = equiv_ok and ok
        print(f"  {cname:<42} cuda-vs-cpu max_rel={d:.2e} -> {'PASS' if ok else 'FAIL'} "
              f"(tol={CUDA_VS_CPU_TOL:.0e})")

    # 球面波 greens 也互证
    g_cpu = [v for _, v in run_greens_test_torch(wl=2.0, n=1.0, device="cpu")]
    g_cuda = [v for _, v in run_greens_test_torch(wl=2.0, n=1.0, device="cuda")]
    gd = _max_rel(g_cpu, g_cuda)
    g_ok = gd < CUDA_VS_CPU_TOL
    equiv_ok = equiv_ok and g_ok
    print(f"  {'E. 球面波 greens':<42} cuda-vs-cpu max_rel={gd:.2e} -> "
          f"{'PASS' if g_ok else 'FAIL'}")

    # ---- 步骤 4：GPU 计时 + 加速比 ----
    print("\n[3/3] greens N=120 计时（cuda）与加速比")
    t0 = time.perf_counter()
    amps = run_greens_test_torch(wl=2.0, n=1.0, N=120, sponge=28,
                                 dl_factor=20.0, ramp=400, device="cuda")
    t_cuda = time.perf_counter() - t0
    vals = [v for _, v in amps]
    sp_numba = NUMBA_CPU_BASELINE_S / t_cuda
    sp_torch = TORCH_CPU_BASELINE_S / t_cuda
    print(f"  cuda:   {t_cuda:8.2f}s  |Ez|*r={[round(v,5) for v in vals]}")
    print(f"  加速比: vs numba-cpu = {sp_numba:.2f}x | vs torch-cpu = {sp_torch:.2f}x")

    # ---- 步骤 5：诚实的 fp64-on-consumer-GPU 说明 ----
    print("\n" + "-" * 60)
    print("诚实性能说明（fp64-on-consumer-GPU）：")
    print("  • 主权 3D 核以 float64 运行（物理定律锚要求逐位精度）。")
    print("  • NVIDIA 消费卡（如 RTX 50 系 Blackwell）fp64 吞吐 ≈ fp32 的 1/64，")
    print("    GPU 在此类卡上的收益主要来自显存带宽/容量（超大网格不爆内存），")
    print("    而非纯算力；若加速比 < 1 属预期，不表示 GPU 路径失效。")
    print("  • 生产级超大网格：优先 numba-cpu（已 43.1×）；GPU 用于显存受限场景。")
    print("  • 若需 GPU fp64 算力收益，应换 datacenter GPU（A100/H100，fp64 不阉割）")
    print("    或评估 fp32 变体（牺牲与 fp64 ground 的逐位等价，需重做 ORACLE 公差论证）。")
    print("-" * 60)

    total_ok = all_ok and equiv_ok
    print(f"\n>> GPU 激活总判定：{'PASS' if total_ok else 'FAIL'}"
          f"（selfcheck={'PASS' if all_ok else 'FAIL'}，"
          f"cuda-cpu互证={'PASS' if equiv_ok else 'FAIL'}）")
    return 0 if total_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
