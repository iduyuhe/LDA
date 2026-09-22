"""P1-C 接受闸 · 跨分解对照（Clements 矩形 vs Reck 三角）免交叉收益量化。

主权红线：C 级自写零依赖；LLM 不进判决路径；全部死标量。
对照口径：
  - 两分解 MZI 单元数相同 = N(N-1)/2（数学定理）。
  - Clements 矩形网格：相邻耦合 + 模式恒驻留固定 lane ⇒ 波导交叉 = 0。
  - Reck 三角网格：三角扫略使模式须横穿网格 ⇒ 波导交叉 > 0（本脚本用 faithful
    邻接耦合路由器模拟计数）。
  - 免交叉收益 = Reck 交叉数 − Clements 交叉数 = Reck 交叉数（Clements 归零）。

EXIT=0 为接受；否则非 0。
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lda"))
from lda_layout.mesh_pnr import (
    clements_decompose,
    reck_decompose,
    assemble_clements,
    mesh_clements_fidelity,
    reck_mesh_crossings,
    clements_mesh_crossings,
    clements_vs_reck_table,
)


def random_unitary(N, seed):
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((N, N)) + 1j * rng.standard_normal((N, N))
    Q, R = np.linalg.qr(X)
    d = np.diagonal(R)
    return Q * (d / np.abs(d))[None, :]


def main() -> int:
    N_list = [4, 8, 16, 32, 64, 128]
    print("=" * 78)
    print("P1-C 跨分解对照 · Clements(矩形) vs Reck(三角) 免交叉收益量化")
    print("=" * 78)
    print(f"{'N':>4} | {'MZI(两分解)':>11} | {'Reck交叉':>9} | {'Clem交叉':>9} | {'免交叉收益':>10} | {'Reck保真度':>10}")
    print("-" * 78)

    prev_reck = 0
    failures = []

    for N in N_list:
        # 1) 两分解重建保真度 = 机器精度（faithfulness）
        U = random_unitary(N, seed=20260922 + N)
        r_ops, r_D = reck_decompose(U)
        c_ops, c_D = clements_decompose(U)
        r_fid = mesh_clements_fidelity(r_ops, r_D, U)
        c_fid = mesh_clements_fidelity(c_ops, c_D, U)

        # 2) MZI 数（两分解相同）
        mzi = N * (N - 1) // 2
        if len(r_ops) != mzi or len(c_ops) != mzi:
            failures.append(f"N={N} MZI 数不符：reck={len(r_ops)} clements={len(c_ops)} 期望={mzi}")

        # 3) 交叉计数
        reck_x = reck_mesh_crossings(N)
        clem_x = clements_mesh_crossings(N)

        # 4) 断言
        if r_fid < 0.9999999:
            failures.append(f"N={N} Reck 重建保真度过低 {r_fid:.6e}")
        if c_fid < 0.9999999:
            failures.append(f"N={N} Clements 重建保真度过低 {c_fid:.6e}")
        if clem_x != 0:
            failures.append(f"N={N} Clements 交叉应=0，得 {clem_x}")
        if reck_x <= 0:
            failures.append(f"N={N} Reck 交叉应>0，得 {reck_x}")
        if N > 4 and reck_x <= prev_reck:
            failures.append(f"N={N} Reck 交叉未随 N 增长：{reck_x} <= {prev_reck}")
        prev_reck = reck_x

        benefit = reck_x - clem_x
        print(f"{N:>4} | {mzi:>11} | {reck_x:>9} | {clem_x:>9} | {benefit:>10} | {r_fid:>10.6f}")

    # 5) 交叉数缩放拟合（应 ~ N^3，验证免交叉收益随规模立方放大）
    rows = clements_vs_reck_table(N_list)
    reck_vals = [r["reck_cross"] for r in rows]
    # 用 N=4 与 N=128 估计指数
    ratio = math.log(reck_vals[-1] / reck_vals[0]) / math.log(N_list[-1] / N_list[0])
    print("-" * 78)
    print(f"Reck 交叉数缩放指数（N=4→128 拟合）≈ {ratio:.3f} （理论三角网格 ~ N^3 ⇒ ≈3.0）")
    # 我们用 SIMULATED reck_vals 拟合缩放指数，不硬编码封闭形式。
    if not (2.5 <= ratio <= 3.5):
        failures.append(f"Reck 交叉数缩放指数偏离 ~3.0：得 {ratio:.3f}（允许 2.5–3.5）")

    if failures:
        print("\n[FAIL] P1-C 接受闸未通过：")
        for f in failures:
            print("  -", f)
        return 1

    print("\n[PASS] P1-C 接受闸通过：两分解 MZI 数相同=N(N-1)/2；Clements 交叉=0；"
          "Reck 三角交叉>0 且随 N 立方增长；免交叉收益=Clements 归零的全部 Reck 交叉。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
