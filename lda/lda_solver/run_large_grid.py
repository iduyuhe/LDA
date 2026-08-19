"""LDA · L2-B 生产级超大网格 GPU/CPU 实跑（阶段1 任务 1.7）。

复用 fdtd3d_torch 张量化后端（device-agnostic），用 run_greens_test_torch 驱动
一个 N×N×N 真三维网格（点源球面波），量化「生产级超大网格」的可行性与性能：
  - 网格规模 N³、场点数、估算内存占用
  - 总耗时
  - ORACLE 校验：|Ez|·r 常数（真三维球面波，确定性物理定律）

device 默认 auto（cuda 优先）。在自配 GPU 算力机上一行切 cuda 即跑超大网格；
当前无 GPU 的沙箱回退 cpu 做中等网格可行性验证。GPU 的真实价值在显存容量/
带宽（超大网格不爆内存），而非消费卡 fp64 纯算力（≈1/64 fp32，加速比≈1 属预期）。
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # 项目根 D:\agent_LDA（lda 包所在）
sys.path.insert(0, ROOT)

import torch
from lda.lda_solver.fdtd3d_torch import run_greens_test_torch


def _estimate_mem_gb(N):
    # 6 场 + 4 damp + 源/辅助 ≈ 12 个 N^3 float64 数组
    return N * N * N * 12 * 8 / 1e9


def main():
    ap = argparse.ArgumentParser(description="LDA 生产级超大网格实跑")
    ap.add_argument("--N", type=int, default=200, help="网格每维点数（N×N×N）")
    ap.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    ap.add_argument("--wl", type=float, default=2.0)
    ap.add_argument("--n", type=float, default=1.0)
    ap.add_argument("--tol", type=float, default=0.20, help="|Ez|·r 常数校验公差")
    args = ap.parse_args()

    device = ("cuda" if torch.cuda.is_available() else "cpu") if args.device == "auto" else args.device

    N = args.N
    mem = _estimate_mem_gb(N)
    npts = N ** 3
    print("=" * 56)
    print(">> LDA 生产级超大网格实跑（任务 1.7）")
    print(f">> device = {device}  (torch {torch.__version__})")
    if device == "cuda":
        print(f">> GPU: {torch.cuda.get_device_name(0)}")
    print(f">> 网格: {N}x{N}x{N} = {npts:,} 点 | 估算场内存 ~= {mem:.2f} GB")
    print("=" * 56)

    t0 = time.perf_counter()
    amps = run_greens_test_torch(wl=args.wl, n=args.n, N=N, device=device)
    t_total = time.perf_counter() - t0

    print(f"\n>> 球面波 |Ez|*r 探头 (r, |Ez|*r):")
    vals = []
    for r, v in amps:
        print(f"   r={r:>4}  |Ez|*r={v:.5f}")
        vals.append(v)
    mean = sum(vals) / len(vals)
    rel = [abs(v - mean) / mean for v in vals]
    max_rel = max(rel)
    ok = max_rel < args.tol

    print(f"\n>> 总耗时: {t_total:.2f}s | mean(|Ez|*r)={mean:.5f} | max_rel_dev={max_rel:.4f}")
    print(f">> ORACLE 校验 (|Ez|*r 常数): {'PASS' if ok else 'FAIL'} (tol={args.tol})")
    print(f">> 结论: 网格 N={N} 在 {device} 上{'可运行且通过 ORACLE' if ok else '运行但 ORACLE 未过'}"
          f"（规模 {npts:,} 点 / ~{mem:.2f}GB）")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
