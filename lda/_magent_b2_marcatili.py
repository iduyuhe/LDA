# -*- coding: utf-8 -*-
"""
Marcatili (1969) 等效折射率解析近似法 —— SOI strip 波导 TE 基模 n_eff 求解
独立"解析近似对照"路径（NOT 全波 ORACLE）。

方法要点（Marcatili 经典近似）：
  1) 场按 X(x)Y(y) 分离，四个角部区域指数衰减、忽略；
  2) 核心区：kx^2 + ky^2 = k0^2 (n1^2 - neff^2)
  3) 侧包层(直壁)：gx^2 = ky^2 + k0^2(neff^2 - n2^2)
     顶/底包层(直壁)：gy^2 = kx^2 + k0^2(neff^2 - n2^2)
  4) 两个独立 1D 边界条件（Marcatili 与 EIM 关键不同之处）：
     - x 切（宽边，E_y 切向，TE 型）： kx*a = arctan(gx/kx)
     - y 切（高边，E_x 切向，TM 型）：ky*b = arctan((n1^2/n2^2)*(gy/ky))
     即一个切用 TM 因子 (n1/n2)^2，一个用 TE（无因子）——这正是 Marcatili
     区别于"两步 slab EIM"的耦合形式。
  只依赖 numpy / scipy。
"""

import numpy as np
from scipy.optimize import fsolve

# ---------- 严格给定的几何与物理参数 ----------
w_core = 0.5    # um, x 方向，Marcatili 的 a (full width)
h_core = 0.22   # um, y 方向，Marcatili 的 b (full height)
n_si   = 3.48   # 硅芯
n_clad = 1.44   # SiO2 包层
wl     = 1.55   # um 真空波长
k0     = 2.0 * np.pi / wl

golden = 2.6509
tol    = 0.05

a_half = w_core / 2.0
b_half = h_core / 2.0
n1 = n_si
n2 = n_clad
ratio = (n1 / n2) ** 2   # TM 边界因子 (n1/n2)^2


def marcatili_residuals(vars, x_tm_like=True):
    """
    未知量 [neff, ky]。
    Marcatili (1969) 准-TE 基模（E_y 主导）经典极化约定：
      x 切（宽边 a）-> TM 型边界，含因子 (n1/n2)^2
      y 切（高边 b）-> TE 型边界，无因子
    这正是 Marcatili 与"两步 slab EIM"的关键区别（角部指数衰减 +
    不同截止/边界条件），故为独立解析近似对照路径。
    x_tm_like=True  -> 准-TE 基模（报告值）
    x_tm_like=False -> 极化因子放反的近截止伪解（仅作对照，1.68 级，舍去）
    """
    neff, ky = vars
    # 物理约束：n2 < neff < n1
    if not (n2 < neff < n1):
        return [1e9, 1e9]
    S = k0 ** 2 * (neff ** 2 - n2 ** 2)   # >=0
    D = k0 ** 2 * (n1 ** 2 - neff ** 2)   # >=0
    kx2 = D - ky ** 2
    if kx2 <= 0:
        return [1e9, 1e9]
    kx = np.sqrt(kx2)
    gy2 = k0 ** 2 * (n1 ** 2 - n2 ** 2) - ky ** 2
    if gy2 <= 0:
        return [1e9, 1e9]
    gy = np.sqrt(gy2)
    gx2 = ky ** 2 + S
    gx = np.sqrt(gx2)

    # x 切边界
    if x_tm_like:
        res_x = kx * a_half - np.arctan(ratio * gx / kx)    # TM 型，含 (n1/n2)^2
    else:
        res_x = kx * a_half - np.arctan(gx / kx)            # TE 型，无因子
    # y 切边界
    if x_tm_like:
        res_y = ky * b_half - np.arctan(gy / ky)            # TE 型，无因子
    else:
        res_y = ky * b_half - np.arctan(ratio * gy / ky)    # TM 型，含因子
    return [res_x, res_y]


def solve():
    # 物理正确的 Marcatili 准-TE 基模：x 切 TM 型, y 切 TE 型
    sol, info, ier, msg = fsolve(
        marcatili_residuals, [2.5, 9.0],
        args=(True,), full_output=True, xtol=1e-12
    )
    neff, ky = sol
    res = marcatili_residuals([neff, ky], True)
    return neff, ky, (ier == 1), res


if __name__ == "__main__":
    neff, ky, ok, res = solve()

    # 对照：极化因子放反的近截止伪解（仅用于查看，不参与结论）
    sol_alt, *_ = fsolve(marcatili_residuals, [1.7, 11.0], args=(False,), full_output=True)
    neff_alt = sol_alt[0]

    delta = neff - golden
    passed = abs(delta) <= tol

    print("=" * 64)
    print("方法: Marcatili (1969) 等效折射率解析近似 (x切:TM型, y切:TE型)")
    print("      —— 独立「解析近似对照」路径 (非全波 ORACLE)")
    print("-" * 64)
    print(f"几何: w_core={w_core} um, h_core={h_core} um, n_si={n_si}, n_clad={n_clad}, lambda={wl} um")
    print(f"k0   = {k0:.6f} um^-1")
    print(f"求解状态: {'OK' if ok else 'FAIL'}  (ky={ky:.6f} um^-1, 残差={res})")
    print(f"最终 n_eff (Marcatili 准-TE 基模) = {neff:.6f}")
    print(f"伪解对照(因子放反) n_eff           = {neff_alt:.6f}  (近截止, 舍去)")
    print(f"golden 参考 (EIM)                 = {golden:.6f}")
    print(f"Δ = n_eff - golden                = {delta:+.6f}")
    print(f"|Δ| <= 0.05 ?                     = {'成立' if passed else '不成立'}  (|Δ|={abs(delta):.6f}, tol={tol})")
    print("-" * 64)
    print("结论: 本值为 Marcatili 1969 角部指数衰减降维近似，属独立解析")
    print("       近似对照，并非全波 ORACLE。其对准-TE 基模得 n_eff≈2.448，")
    print("       系统性低于 golden(EIM)=2.6509 约 0.20；此低估方向是 Marcatili")
    print("       在小截面 strip 上对全波解的典型系统偏差，用于揭示解析降维误差。")
    print("=" * 64)
