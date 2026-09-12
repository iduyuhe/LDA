"""T1-B-W4 护栏 smoke · 自研 2D p-n 结漂移-扩散+连续性内核（C 级自主）vs Sze 教科书闭式。

golden（design_rule_anchor，Sze《Physics of Semiconductor Devices》§2.2 突变 p-n 结
耗尽近似 + 理想二极管律，确定性物理定律闭式）：
    V_bi = V_T·ln(N_A·N_D/n_i²)
    理想二极管 I = I_s·(exp(qV/kT) − 1)
    I_s_short（短二极管，无复合 ∇·J=0 数值解对应；准中性区宽 W_p,W_n 替代扩散长度）
        = q·(D_N·n_i²/(N_A·W_p) + D_P·n_i²/(N_D·W_n))·Ly

candidate（self_authored_t1_candidate，lda_solver.drift_diffusion_2d）：
    2D 自洽玻尔兹曼-泊松（平衡）→ 偏压漂移-扩散（Gummel 迭代：SG 离散连续性
    + 非线性泊松）→ 终端 I(V)。与 W2 的 1D 内核同一物理对象、方法学独立范式。

方法学独立性（判据 D 真数值）：
- golden = 解析耗尽近似 + 理想二极管律（突变结、耗尽区 n,p≈0、低注入长/短二极管）
- cand   = 自洽玻尔兹曼统计数值解（耗尽区少数载流子指数衰减，非严格 0）+ 无复合
          稳态输运 ⇒ 与短二极管 golden 比对（非长二极管，避免 mismatched golden）
⇒ |cand−golden| 反映耗尽近似 / 无复合短二极管近似的固有截断误差，随网格加密收敛。

4 判据（死标量，rc=0 PASS / ≠0 FAIL）：
  ① 正向 PASS：|I(V) − I_s_short·(exp(V/V_T)−1)| / golden ≤ TOL_I（余量 ≥ ~1.5×）；
     正偏 I>0（极性正确）；V=0 残差 |I| ≤ V0_TOL（≈0，理想二极管律锚定）
  ② 判据 D 网格收敛：nx 加密 → I@V=0.4 相对短二极管 golden 误差单调非增（真数值）
  ③ 反向必 FAIL：N_A×1.1 → |ΔI|/I ≥ REV_THRESH（防常数假绿）
  ④ 🔴 T1 输出不作 ORACLE 守卫：guard_t1_not_oracle 正常通过；force_oracle=True 必 raise

主权红线：纯 numpy+scipy、零外部依赖、不 import 任何 A 级商业求解器 / DEVSIM（B 级）；
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

from lda_solver.drift_diffusion_2d import (  # noqa: E402
    solve_pn_junction_2d_bias, sze_pn_junction_2d_closed_form,
    guard_t1_not_oracle, V_T, N_A_DEFAULT,
)

# ---- 容差（实测标定，见 tmp_thresh 诊断）----
TOL_I = 0.08          # 正向 I(V) 比对容差（实测 nx=60 V=0.4 → 4.61%，余量 ≥1.5×）
V0_TOL = 1e-9         # V=0 残差上限（实测 −5.97e-13 A ≈ 0）
REV_THRESH = 0.01     # 反向测试最小信号（N_A×1.1 实测 1.73% ≫ 噪声）
GRIDS = (40, 80)      # 判据 D 收敛网格序列（nx=ny）
FWD_NX = 60           # 正向比对基线网格
FWD_VS = (0.3, 0.4)   # 正向比对偏压点（理想二极管律指数段）


def _errI(sol: dict, gold: dict, V: float) -> float:
    I_gold = gold["I_s_short"] * (math.exp(V / V_T) - 1.0)
    return abs(sol["I"] - I_gold) / I_gold


def main() -> int:
    fails = []
    gold = sze_pn_junction_2d_closed_form()

    # ① 正向比对（基线网格，理想二极管律指数段）
    for V in FWD_VS:
        sol = solve_pn_junction_2d_bias(V, nx=FWD_NX, ny=FWD_NX)
        if not sol["converged"]:
            fails.append(f"①偏压 V={V:.1f} Gummel 未收敛（converged=False）")
            continue
        eI = _errI(sol, gold, V)
        if eI > TOL_I:
            fails.append(
                f"①正向 I(V={V:.1f}) 误差 {eI:.3%} > tol {TOL_I:.0%}")
        if sol["I"] <= 0.0:
            fails.append(f"①正向 I(V={V:.1f}) 极性错误（I={sol['I']:.3e} ≤ 0）")
    # ① V=0 残差（理想二极管律：V=0 ⇒ I≈0）
    s0 = solve_pn_junction_2d_bias(0.0, nx=FWD_NX, ny=FWD_NX)
    if abs(s0["I"]) > V0_TOL:
        fails.append(f"①V=0 残差 |I|={abs(s0['I']):.3e} > {V0_TOL:.0e}")

    # ② 判据 D：网格加密 → I@V=0.4 相对短二极管 golden 误差单调非增（真数值离散化）
    Vc = 0.4
    errs = [_errI(solve_pn_junction_2d_bias(Vc, nx=g, ny=g), gold, Vc)
            for g in GRIDS]
    mono = all(errs[i + 1] <= errs[i] * 1.02 for i in range(len(GRIDS) - 1))
    if not mono:
        fails.append(f"②判据D非单调收敛: {[f'{e:.3%}' for e in errs]}")

    # ③ 反向：N_A ×1.1 ⇒ I 必变（信号 ≫ 数值噪声，防常数假绿）
    s_base = solve_pn_junction_2d_bias(Vc, nx=FWD_NX, ny=FWD_NX)
    s_pert = solve_pn_junction_2d_bias(
        Vc, nx=FWD_NX, ny=FWD_NX, N_A=N_A_DEFAULT * 1.1)
    dI = abs(s_pert["I"] - s_base["I"]) / abs(s_base["I"])
    if dI < REV_THRESH:
        fails.append(f"③反向 N_A×1.1: I 变化 {dI:.2%} < {REV_THRESH:.0%}（假绿风险）")

    # ④ 🔴 T1 输出不作 ORACLE 守卫（双向）
    try:
        guard_t1_not_oracle(s_base)
    except Exception as exc:  # noqa: BLE001
        fails.append(f"④守卫正常调用失败: {exc}")
    raised = False
    try:
        guard_t1_not_oracle(s_base, force_oracle=True)
    except RuntimeError:
        raised = True
    if not raised:
        fails.append("④守卫反向测试未触发（force_oracle=True 应 raise）")

    if fails:
        print("FAIL · T1-B-W4 2D 漂移-扩散内核护栏：")
        for f in fails:
            print(f"  - {f}")
        return 1

    s_v04 = solve_pn_junction_2d_bias(FWD_VS[1], nx=FWD_NX, ny=FWD_NX)
    e_v04 = _errI(s_v04, gold, FWD_VS[1])
    print(
        f"PASS · T1-B-W4 2D 漂移-扩散内核(C级自主) vs Sze 短二极管闭式："
        f"I(V={FWD_VS[0]:.1f},{FWD_VS[1]:.1f})@nx{FWD_NX} 误差 {e_v04:.3%}"
        f"(tol {TOL_I:.0%}) | V=0 残差 {abs(s0['I']):.2e} | "
        f"判据D {[f'{e:.2%}' for e in errs]} | "
        f"反向 N_A×1.1 信号 {dI:.2%} | T1 不作ORACLE 守卫 OK | 纯numpy+scipy零依赖"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
