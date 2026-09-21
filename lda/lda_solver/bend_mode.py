# -*- coding: utf-8 -*-
"""弯曲波导群折射率求解（共形变换 + 半矢量本征模核）。

机制（共形变换 Heiblum-Harris）：在弯曲坐标系中，距中心横向坐标 x 处的等效
折射率分布满足 n'(x) = n(x) · (1 + x/R)，即 n'^2 = n^2 · (1 + x/R)^2。将该
等效折射率分布喂给现有半矢量 2D 本征模求解器
(``lda_solver.semivec_mode_solver``)，即可在**不引用任何 golden 值**的前提下
第一原理算出弯曲波导的有效折射率 n_eff 与群折射率 n_g。

诚实边界（见 ``LDA_wave7_closeout_plan_2026-09-21.md`` §3）：

* 本能力经只读探针实证：R=10µm 时弯曲修正 Δn_g ≈ +0.003778（严格符合
  Δn_g ∝ 1/R²，10→20→30µm 各减半/降为 1/9，误差 <1%），窗口
  L=2.4/3.6/6.0µm 三档逐位相同（无窗口敏感性）。
* **对 E10（微环 FSR）无帮助**：E10 残差 0.31nm 的主要来源是「参数化模型
  （半矢量直波导 + 色散）vs 真实环器件」的量纲差，而非弯曲几何。即便叠加
  弯曲修正，E10 残差仅从 0.313→0.304nm（几乎无改善）。弯曲效应本身仅 ~0.004
  （R=10µm），远小于 E10 实测 0.157 量级差（要复现 0.157 需 R≈1.55µm，辐射
  损耗 >10 dB/turn，物理不可能）。故 E10 仍无内部升格路径。
* 本模块定位为**设计侧**能力（弯曲/环类器件的本征模与群折射率估算），
  **不进**判决口径，不影响账本。

复现：``python -m lda_solver.bend_mode`` 跑 ``self_test()``，应复现波次 7
只读探针结论（直波导 n_g≈4.0228、弯曲 Δn_g ∝ 1/R²、窗口无关）。
"""
import math

import numpy as np

try:
    from lda_solver.semivec_mode_solver import (
        H_GRID, build_index_2d, neff_2d, sellmeier_si, sellmeier_sio2,
    )
except ImportError:  # 允许 `python lda/lda_solver/bend_mode.py` 直接运行
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from lda_solver.semivec_mode_solver import (
        H_GRID, build_index_2d, neff_2d, sellmeier_si, sellmeier_sio2,
    )


def bend_index_sq(n2_straight, x_grid_um, R_um):
    """对直波导 n^2 分布施加共形变换 n'^2 = n^2 · (1 + x/R)^2。

    ``R_um is None`` ⇒ 退化为直波导（返回原分布）。
    """
    if R_um is None:
        return n2_straight
    fac = 1.0 + x_grid_um / R_um
    return n2_straight * (fac * fac)[:, None]


def _neff_at(window_n, hw, hh, h, x, wl_um, R_um, n_core, n_clad):
    """单波长有效折射率（内部）。

    折射率（Sellmeier）随波长重算，使材料色散进入群折射率差分 ——
    与只读探针 ``_probe_bend.py`` 完全一致，否则 n_g 会被低估 ~3%。
    """
    nc = n_core if n_core is not None else sellmeier_si(wl_um)
    ncl = n_clad if n_clad is not None else sellmeier_sio2(wl_um)
    base = build_index_2d(window_n, window_n, h, 2.0 * hw, 2.0 * hh, nc, ncl)
    n2 = bend_index_sq(base, x, R_um)
    k0 = 2.0 * math.pi / wl_um
    ne, _, _ = neff_2d(n2, h, k0=k0, k=8, n_core=nc, n_clad=ncl)
    return ne


def bend_waveguide_ng(w_um=0.5, h_um=0.22, wl_um=1.5476, R_um=None,
                      window_um=3.6, d_wl_um=0.02, n_core=None, n_clad=None):
    """弯曲波导群折射率（第一原理，不引用 golden）。

    返回 ``(n_g, n_eff)``。``R_um=None`` 时退化为直波导。

    参数
    ----
    w_um, h_um : 波导芯宽/芯高（µm）
    wl_um : 工作波长（µm）
    R_um : 弯曲半径（µm）；``None`` 表示直波导
    window_um : 求解窗口宽度（µm），仅影响网格离散
    d_wl_um : 群折射率差分步长（µm）
    n_core, n_clad : 芯/包折射率；缺省按 Si / SiO2 Sellmeier 计算
    """
    h = H_GRID
    n = int(round(window_um / h))
    hw = max(int(round(w_um / 2.0 / h)), 1) * h
    hh = max(int(round(h_um / 2.0 / h)), 1) * h
    x = (np.arange(n) - n / 2.0 + 0.5) * h

    ne = _neff_at(n, hw, hh, h, x, wl_um, R_um, n_core, n_clad)
    nl = _neff_at(n, hw, hh, h, x, wl_um - d_wl_um, R_um, n_core, n_clad)
    nh = _neff_at(n, hw, hh, h, x, wl_um + d_wl_um, R_um, n_core, n_clad)
    ng = ne - wl_um * (nh - nl) / (2.0 * d_wl_um)
    return ng, ne


def self_test():
    """复现波次 7 只读探针结论（§3.1），作为本模块正确性自校。"""
    # 直波导 n_g 应与生产候选 n_g=4.023 逐位吻合（探针实测 4.022777）
    ng0, ne0 = bend_waveguide_ng(R_um=None, window_um=3.6)
    assert abs(ng0 - 4.022777) < 5e-3, "straight n_g mismatch: %r" % ng0
    # 弯曲使 n_g 单调升高，且 Δn_g ∝ 1/R²
    deltas = {}
    for R in (30.0, 20.0, 10.0, 5.0):
        g, _ = bend_waveguide_ng(R_um=R, window_um=3.6)
        deltas[R] = g - ng0
        assert g > ng0, "bend must raise n_g at R=%s" % R
    # 1/R² 检验：10→20µm 的 Δn_g 应降约 1/4
    ratio = deltas[10.0] / deltas[20.0]
    assert abs(ratio - 4.0) < 0.1, "1/R^2 scaling violated: ratio=%r" % ratio
    # 窗口无关性：R=10µm 在 L=2.4/3.6/6.0µm 三档应逐位相同
    g_r10 = [bend_waveguide_ng(R_um=10.0, window_um=L)[0] for L in (2.4, 3.6, 6.0)]
    assert max(g_r10) - min(g_r10) < 1e-4, "window sensitivity: %r" % g_r10
    return {
        "straight_ng": ng0,
        "straight_neff": ne0,
        "deltas_vs_straight": {str(k): v for k, v in deltas.items()},
    }


if __name__ == "__main__":
    import json
    print(json.dumps(self_test(), indent=2))
