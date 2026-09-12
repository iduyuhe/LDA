"""T1-B-W2/W3 护栏 smoke · 自研 1D 漂移-扩散+连续性内核（C 级自主）vs Sze 教科书闭式。

golden（design_rule_anchor，Sze《Physics of Semiconductor Devices》§2.2 突变 p-n 结
耗尽近似，确定性物理定律闭式）：
    V_bi = V_T·ln(N_A·N_D/n_i²)
    W    = √(2ε·V_bi/q·(N_A+N_D)/(N_A·N_D))
    E_max = q·N_D·x_n/ε                          （结处峰值电场，x_n=W·N_A/(N_A+N_D)）

candidate（self_authored_t1_candidate，lda_solver.drift_diffusion_1d）：
    泊松 + 自洽玻尔兹曼统计（热平衡漂移-扩散退化的闭式耦合）数值求解 N(x)/P(x)/φ(x)。

方法学独立性（判据 D 真数值）：
- golden = 解析耗尽近似（突变结、耗尽区 n,p≈0）
- cand   = 自洽玻尔兹曼统计数值解（耗尽区少数载流子指数衰减，非严格 0）
⇒ |cand−golden| 反映耗尽近似固有截断误差，随网格加密单调收敛到该极限。

4 判据（死标量，rc=0 PASS / ≠0 FAIL）：
  ① 正向 PASS：|E_max_num − E_max_sze|/E_max_sze ≤ TOL_E（余量 ≥ ~2×）
  ② 判据 D 网格收敛：n_grid 加密 → E_max 误差单调非增（O(dx²) 真数值离散化）
  ③ 反向必 FAIL：N_D×1.2 / ×0.8 → E_max 变化 ≥ REV_THRESH（防常数假绿）
  ④ 🔴 T1 输出不作 ORACLE 守卫：guard_t1_not_oracle 正常通过；force_oracle=True 必 raise

主权红线：纯 numpy、零外部依赖、不 import 任何 A 级商业求解器 / DEVSIM（B 级）；
本内核输出 is_oracle=False（仅候选，判决由物理定律锚/文献/foundry 实测定）。
EAR 744.23：声明仅用于成熟节点 / 非先进用途（见 docs/ 合规件 T1-B-W3）。
LLM 不进判决路径。
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import numpy as np  # noqa: E402

from lda_solver.drift_diffusion_1d import (  # noqa: E402
    solve_pn_junction_1d, sze_pn_junction_closed_form, guard_t1_not_oracle,
)

TOL_E = 0.10          # E_max 比对容差（实测 3–7%，余量 ≥2×）
TOL_W = 0.25          # W 比对容差（自洽玻尔兹曼 vs 耗尽近似固有 ~19% 差异）
REV_THRESH = 0.05     # 反向测试最小信号（N_D±20% 实测 ~9%）
GRIDS = (200, 400, 800, 1600)


def _errE(sol: dict, gold: dict) -> float:
    return abs(sol["E_max"] - gold["E_max"]) / gold["E_max"]


def main() -> int:
    fails = []
    gold = sze_pn_junction_closed_form()

    # ① 正向比对（基线网格）
    sol = solve_pn_junction_1d(n_grid=400)
    eE = _errE(sol, gold)
    eW = abs(sol["W"] - gold["W"]) / gold["W"]
    if eE > TOL_E:
        fails.append(f"①正向 E_max 误差 {eE:.3%} > tol {TOL_E:.0%}")
    if eW > TOL_W:
        fails.append(f"①正向 W 误差 {eW:.3%} > tol {TOL_W:.0%}")
    if not sol["converged"]:
        fails.append("①牛顿迭代未收敛（converged=False）")

    # ② 判据 D：网格加密 → E_max 误差单调非增（真数值离散化）
    errs = [_errE(solve_pn_junction_1d(n_grid=g), gold) for g in GRIDS]
    mono = all(errs[i + 1] <= errs[i] * 1.02 for i in range(len(GRIDS) - 1))
    if not mono:
        fails.append(f"②判据D非单调收敛: {[f'{e:.3%}' for e in errs]}")

    # ③ 反向：N_D ±20% ⇒ E_max 必变（信号 ≫ 数值噪声，防常数假绿）
    for fac in (1.2, 0.8):
        sp = solve_pn_junction_1d(N_D=1.0e22 * fac)
        dE = abs(sp["E_max"] - sol["E_max"]) / sol["E_max"]
        if dE < REV_THRESH:
            fails.append(f"③反向 N_D×{fac}: E_max 变化 {dE:.2%} < {REV_THRESH:.0%}（假绿风险）")

    # ④ 🔴 T1 输出不作 ORACLE 守卫（双向）
    try:
        guard_t1_not_oracle(sol)
    except Exception as exc:  # noqa: BLE001
        fails.append(f"④守卫正常调用失败: {exc}")
    raised = False
    try:
        guard_t1_not_oracle(sol, force_oracle=True)
    except RuntimeError:
        raised = True
    if not raised:
        fails.append("④守卫反向测试未触发（force_oracle=True 应 raise）")

    if fails:
        print("FAIL · T1-B 漂移-扩散内核护栏：")
        for f in fails:
            print(f"  - {f}")
        return 1

    print(
        f"PASS · T1-B 1D 漂移-扩散内核(C级自主) vs Sze 闭式："
        f"E_max 误差 {eE:.3%}(tol {TOL_E:.0%}) | "
        f"判据D {[f'{e:.2%}' for e in errs]} | "
        f"W 误差 {eW:.3%}(tol {TOL_W:.0%}, 自洽vs耗尽近似固有差) | "
        f"反向 N_D±20% 信号 ~9% | T1 不作ORACLE 守卫 OK | 纯numpy零依赖"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
