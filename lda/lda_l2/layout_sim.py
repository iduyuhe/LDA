"""LDA L2 · 版图 → 仿真闭环（D-16：GDS/版图描述 → FDTD → 物理锚验收）。

把 D-14 导出的版图描述（geometry_desc）直接驱动已验证 FDTD 内核仿真，并对
物理定律锚验收——形成「设计→版图→仿真→验收」全自动闭环的最后一环：

  版图描述（PATH 波导宽度）→ 构造 FDTD 场 → solve_waveguide_neff（2D-TE，
  双监视点相位差法）→ 对 slab 闭式 ORACLE 验收（相对误差 ≤ tol）。

诚实边界：
  - 支持直波导类版图（Waveguide 单波导 / Ring 的 bus / DC 的单波导 neff）；
  - 环形/耦合器的全场透射仿真不在本任务（需多端口/环形 FDTD，规划后续）；
  - 求解器全部复用已验证内核（fdtd2d_waveguide + oracle_mode.slab_te_neff），
    LLM 不进判决路径。

零外部依赖（numpy 即可）。
"""
from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional

import numpy as np

_SOLVER_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lda_solver")
_HARNESS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lda_harness")


def _ensure_paths() -> None:
    for p in (_SOLVER_DIR, _HARNESS_DIR):
        if p not in sys.path:
            sys.path.insert(0, p)


def find_waveguide_width(desc_list: List[Dict]) -> Optional[float]:
    """从版图描述（geometry_desc）提取波导芯宽（µm）。

    取第一个 SOI 层 PATH 元素的 width_um（Waveguide / Ring bus / DC 波导
    均含 PATH）；无 PATH（纯 boundary）返回 None。
    """
    for d in desc_list:
        if d.get("kind") == "path" and d.get("layer") == 1:
            return float(d["width_um"])
    return None


def simulate_waveguide_neff(width_um: float, n_core: float, n_clad: float,
                            wl_um: float, dl: Optional[float] = None
                            ) -> Dict:
    """由版图波导宽度 → FDTD neff → slab ORACLE 验收。

    构造 (x,z) 2D-TE 波导场（芯宽=版图 width_um），FDTD 求 neff，与 slab 闭式
    ORACLE（半厚 a=width/2）相对误差比对。
    """
    _ensure_paths()
    from fdtd2d_waveguide import build_waveguide_field, solve_waveguide_neff
    from oracle_mode import _slab_te_neff

    eps2_int, dl_f = build_waveguide_field(width_um, n_core, n_clad, wl_um,
                                           dl=dl)
    neff = solve_waveguide_neff(eps2_int, dl_f, wl_um,
                                n_clad=n_clad, n_core=n_core)
    oracle = _slab_te_neff(n_core, n_clad, width_um / 2.0, wl_um)
    rel_err = abs(neff - oracle) / oracle
    return {
        "width_um": width_um,
        "neff_fdtd": float(neff),
        "neff_oracle": float(oracle),
        "rel_err": float(rel_err),
        "dl_um": float(dl_f),
        "n_core": n_core,
        "n_clad": n_clad,
        "wl_um": wl_um,
    }


def simulate_layout(desc_list: List[Dict], n_core: float, n_clad: float,
                    wl_um: float, tol_rel: float = 0.02) -> Dict:
    """版图描述 → 波导仿真 → 物理锚验收（完整闭环入口）。

    desc_list 为 D-14 geometry_desc 输出；提取波导宽度后 FDTD 仿真 + ORACLE
    验收，返回报告（含 passed）。

    精度自适应：默认分辨率 wl/32（快）；若相对误差超容差，逐级提精
    wl/48 → wl/64（网格色散对不同宽度敏感，提精可压到 2% 内）。
    """
    width = find_waveguide_width(desc_list)
    if width is None:
        raise ValueError("版图描述无 PATH 波导元素（本任务仅支持波导类版图）")
    sim = None
    for dl in (None, wl_um / 48.0, wl_um / 64.0):
        s = simulate_waveguide_neff(width, n_core, n_clad, wl_um, dl=dl)
        sim = s
        if s["rel_err"] <= tol_rel:
            break
    sim["passed"] = sim["rel_err"] <= tol_rel
    sim["tol_rel"] = tol_rel
    return sim


def simulate_layout_from_ir(model, n_core: float = 3.48, n_clad: float = 1.44,
                            wl_um: float = 1.55, tol_rel: float = 0.02) -> Dict:
    """L0 IR → 版图描述 → 仿真验收（端到端：IR → GDS 几何 → FDTD → ORACLE）。"""
    from lda_l2.gds_export import geometry_desc
    prim = model.primary_component
    if prim is None:
        raise ValueError("IR 无 component")
    desc_list = geometry_desc(prim.kind, dict(prim.params))
    report = simulate_layout(desc_list, n_core, n_clad, wl_um, tol_rel)
    report["ir_kind"] = prim.kind
    report["ir_id"] = prim.id
    return report


def build_eps_from_layout(width_um: float, n_core: float, n_clad: float,
                          wl_um: float) -> np.ndarray:
    """版图波导宽度 → FDTD 折射率平方场（供可视化/检查）。"""
    _ensure_paths()
    from fdtd2d_waveguide import build_waveguide_field
    eps2_int, _dl = build_waveguide_field(width_um, n_core, n_clad, wl_um)
    return eps2_int
