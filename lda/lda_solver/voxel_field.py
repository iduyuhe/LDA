"""LDA · 机器优先器件版图 → 体素场引擎（C 级自主，纯 numpy）。

把 L0 IR 的 geometry.voxel_field 原语落成可计算件：
  - voxelize_stack        : 复用已验证的 _build_interior，把 1D 层状 stack 退化为 3D 体素场
                            （y/z 均匀复制），保证与 solve_spectrum 入口逐位一致 —— 用于
                            "版图→体素→FDTD→ORACLE 验收"链路的退化等价验证。
  - LayoutLayer           : 机器优先矩形掩模（坐标 um，非 GUI）。
  - voxelize_rectangular  : 真 2D 矩形掩模体素化（器件雏形，下一步接真 2D ORACLE）。
  - to_gdsii / from_gdsii : GDSII 序列化适配器（gdsfactory 不可用时友好降级 + 预留接口）。

设计哲学（见 L0 IR 草案 §5 / 协作哲学）：机器优先、不依赖任何外部版图库的可计算件；
gdsfactory 仅是 B 级 fork 副本的"可选序列化通道"，缺失时体素化与 FDTD 仍完全可用。
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

# 复用已验证的 stack 几何构造，避免吸附逻辑漂移（保证 stack 退化逐位等价）
_SOLVER_DIR = os.path.dirname(os.path.abspath(__file__))
if _SOLVER_DIR not in sys.path:
    sys.path.insert(0, _SOLVER_DIR)
from fdtd3d import _build_interior  # noqa: E402


@dataclass
class LayoutLayer:
    """一个矩形掩模（机器优先版图层）。坐标单位 um；None 表示该轴全宽。"""
    material_ref: str
    x0: float
    x1: float
    y0: Optional[float] = None
    y1: Optional[float] = None
    z0: Optional[float] = None
    z1: Optional[float] = None
    comment: str = ""


@dataclass
class VoxelGrid:
    dl: float
    Nx: int
    Ny: int
    Nz: int


def voxelize_stack(layers: List[Tuple[float, float]], dl: float, buf: int,
                   sponge: int, ny: int = 2, nz: int = 2
                   ) -> Tuple[np.ndarray, Dict]:
    """stack 退化 → 3D 体素折射率场（含 n^2），shape=(Nx, Ny, Nz)。

    复用 fdtd3d._build_interior（已验证、selfcheck 5/5），仅把 1D prof 复制到
    y/z 维，故构造出的 eps 与 solve_spectrum 入口（_run_planewave）逐位一致。
    返回 (eps_field, meta{dl, n0, nL, Nx, src_x, mon_x, ny, nz})。
    """
    prof, n0, nL = _build_interior(layers, dl, buf)
    Nint = len(prof)
    Nx = Nint + 2 * sponge
    eps = np.empty((Nx, ny, nz), dtype=float)
    eps[:sponge] = n0 ** 2
    prof_arr = np.array(prof, dtype=float) ** 2
    eps[sponge:sponge + Nint, :, :] = prof_arr[:, None, None]
    eps[sponge + Nint:, :, :] = nL ** 2
    meta = {
        "dl": dl, "n0": n0, "nL": nL, "Nx": Nx,
        "src_x": sponge + 20, "mon_x": sponge + Nint - buf // 2,
        "ny": ny, "nz": nz,
    }
    return eps, meta


def _interval(lo: Optional[float], hi: Optional[float], N: int, dl: float
              ) -> Tuple[int, int]:
    """(lo, hi) um → (i0, i1) 单元区间；任一 None 取该轴边界。"""
    i0 = 0 if lo is None else max(0, int(round(lo / dl)))
    i1 = N if hi is None else min(N, int(round(hi / dl)))
    return i0, i1


def voxelize_rectangular(layers: List[LayoutLayer], materials: Dict[str, float],
                         grid: VoxelGrid, background_ref: str = "air"
                         ) -> np.ndarray:
    """真 2D 矩形掩模 → 3D 体素折射率场（含 n^2）。

    先填背景介质，再按 layers 顺序覆盖矩形（后者覆盖前者）。供真 2D 器件
    （波导 / 分束器横截面）使用；需另建真 2D ORACLE（本迭代暂不接验收，
    仅作为器件几何管线的可计算件与 smoke-test 对象）。
    """
    n_bg = materials.get(background_ref, 1.0)
    eps = np.full((grid.Nx, grid.Ny, grid.Nz), n_bg ** 2, dtype=float)
    for lay in layers:
        n = materials[lay.material_ref]
        i0, i1 = _interval(lay.x0, lay.x1, grid.Nx, grid.dl)
        j0, j1 = _interval(lay.y0, lay.y1, grid.Ny, grid.dl)
        k0, k1 = _interval(lay.z0, lay.z1, grid.Nz, grid.dl)
        if i1 > i0 and j1 > j0 and k1 > k0:
            eps[i0:i1, j0:j1, k0:k1] = n ** 2
    return eps


def to_gdsii(layout_layers: List[LayoutLayer], path: str) -> str:
    """版图层 → GDSII（gdsfactory 可选通道）。

    gdsfactory 为 B 级依赖（已 fork 主权副本），本环境未安装时友好降级报错，
    明确告知：voxel_field 引擎不依赖它即可体素化与仿真。
    """
    try:
        import gdsfactory as gf
    except Exception as e:
        raise RuntimeError(
            "GDSII 导出需 gdsfactory（B 级，已 fork 主权副本）。当前环境未安装；"
            "voxel_field 引擎不依赖它（纯 numpy 已可体素化与 FDTD 仿真）。"
            "请在已装 gdsfactory 主权副本的环境运行，或先 fork/安装。"
        ) from e
    c = gf.Component()
    for lay in layout_layers:
        c.add_polygon(
            [(lay.x0, lay.y0 or 0.0), (lay.x1, lay.y0 or 0.0),
             (lay.x1, lay.y1 or 1.0), (lay.x0, lay.y1 or 1.0)],
            layer=(1, 0),
        )
    c.write_gds(path)
    return path


def from_gdsii(path: str) -> List[LayoutLayer]:
    """GDSII → 版图层（gdsfactory 可选通道，未安装时友好降级）。"""
    try:
        import gdsfactory as gf
    except Exception as e:
        raise RuntimeError(
            "GDSII 导入需 gdsfactory（B 级，已 fork 主权副本）。当前环境未安装；"
            "voxel_field 引擎不依赖它（纯 numpy 已可体素化与 FDTD 仿真）。"
        ) from e
    c = gf.import_gds(path)
    layers: List[LayoutLayer] = []
    for poly in c.get_polygons():
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        layers.append(LayoutLayer(
            material_ref="imported", x0=min(xs), x1=max(xs),
            y0=min(ys), y1=max(ys), comment="from GDSII"))
    return layers
