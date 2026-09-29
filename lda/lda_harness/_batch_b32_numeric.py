# -*- coding: utf-8 -*-
"""B-32 数值核（Batch B-32 · **几何栅格化收敛** · 1 锚 B458）。

物理族 = **解析几何闭式 × 数值栅格化亚格平均**——本项目**首个几何类锚**
（此前锚族集中在电磁/量子/电路数值核）。

| 锚 | 被测标量 | golden（解析闭式） | candidate（方法学独立） |
|---|---|---|---|
| **B458** | 多边形**面积**（版图几何 → 体素栅格化） | 教科书 **Shoelace 公式**（独立实现） | 平台 `lda_solver.voxel_field.rasterize_polygon` 的**亚格平均**面积 `Σ frac · dl²`（even-odd 交叉数 + s×s 子采样） |

残差来源 = **栅格化离散误差**（边界格的阶梯化）；随 `subpixel` 细化**单调下降并趋于 0**
（实测每步 ×0.5 ⇒ 线性收敛，见 §自检）。

判据 D：固定物理参数（多边形顶点 + 网格 nx=ny=50 + dl=0.05 µm），只扫**候选自身离散参数**
        `subpixel`（模块 docstring 明标其为「判据 D 的细化参数」）。
        窗口铁律 `1e-15 < 粗端残差 < tol`；随 subpixel 严格单调下降；默认档残差 > 1e-12；
        `|golden|/tol ≥ 13.5`；余量 `tol/|Δ| ≥ 2`。收敛阶数字**一律来自实测**，不按标称阶写死。

🔴 同源体检（实 grep 全仓，排除 `.git/__pycache__/node_modules/lda_cuda_venv/reports/dist` 噪声）：
    · `voxel|体素|rasteri|栅格|subpixel|亚像素|多边形面积|polygon.?area|shoelace`
      在 `BENCHMARK_DEFS` 的 title/metric/oracle/note/candidate_desc 内 **0 命中**
      ⇒ **几何栅格化族零锚占用**（本批为本族首锚）。
    · 与既有「几何回提」锚族（E1–E10，版图几何 → 器件参数**回提**）**不同**：E1–E10 是
      「从真实 GDS/版图**反推**器件参数并与实测/闭式比对」（几何 → 物理量映射）；
      本题是「**多边形 → 栅格化覆盖率**」的数值积分误差（几何 → 面积测度），
      被测标量、数值机制、golden 三处均不同 ⇒ **非重复计数**。
    · **B458 vs B1–B457**：既有锚无任何「面积测度 / 栅格覆盖率」类被测标量。

🔴 血案预防：
    1. `rasterize_polygon` 有硬限 `nx·ny·s² ≤ 5e7` ⇒ 本锚固定 50×50×16² = 6.4e5 ≪ 5e7，
       网格族不越限（越限会抛 ValueError 而非静默降级）。
    2. 候选面积**必须先乘 dl²**（`frac` 是无量纲覆盖率，不乘 dl² 会得到「格数」而非面积）
       ⇒ 量级失真 2.5e-3 倍。判据 D 实测对此敏感（见门禁突变）。
    3. `frac.sum()` 与解析面积的比较用 **绝对差**（面积量级 ~4 µm²）；
       相对误差仅作展示，不作判决位。
    4. golden **独立实现 Shoelace**（不调用平台 `polygon_area`）⇒ 避免「同式两写」；
       门禁另设**跨源一致**断言（本实现 ≡ 平台 `polygon_area`，机器精度）。

诚实边界：
    · 多边形顶点与网格分辨率均为**设计示例**（非实测版图）；结论只可用于数值方法与量级，
      不得作制造/性能宣称。
    · 栅格化是**面积测度**的数值近似（非电磁/量子计算）；本锚只证明「数值栅格化收敛到
      解析面积」这一几何事实，不含任何器件性能含义。
    · 零商业依赖（纯 numpy + 本项目 `lda_solver` 自研模块）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_LDA_DIR = Path(__file__).resolve().parents[1]        # …/lda（给出 `lda_solver` 包）
_VF = None

#: 🔴 固定物理参数（判据 D 只扫 subpixel，**不动**这些）
POLY = ((0.0, 0.0), (2.0, 0.0), (2.4, 1.1), (1.2, 2.5), (0.3, 1.6))
NX = 50
NY = 50
DL_UM = 0.05


def _vf():
    """双路兜底导入 `lda_solver.voxel_field`（缓存）。"""
    global _VF
    if _VF is not None:
        return _VF
    try:
        from lda_solver import voxel_field as _m
    except ImportError:                                # 裸模块名回退
        if str(_LDA_DIR) not in sys.path:
            sys.path.insert(0, str(_LDA_DIR))
        from lda_solver import voxel_field as _m       # type: ignore
    _VF = _m
    return _VF


# ===========================================================================
# B458 · 多边形面积（几何栅格化）
# ===========================================================================
def shoelace_area(points) -> float:
    """教科书 **Shoelace（鞋带）公式** —— golden 的**独立实现**。

    A = |Σ_i (x_i·y_{i+1} − x_{i+1}·y_i)| / 2（顶点按序，闭合隐含）。
    多边形（含凹形）面积是**解析闭式**，与栅格分辨率无关 ⇒ 确定性物理/几何定律锚。
    """
    n = len(points)
    if n < 3:
        raise ValueError("多边形至少 3 个顶点")
    s = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        s += float(x1) * float(y2) - float(x2) * float(y1)
    return abs(s) / 2.0


def golden_b458(_poly=POLY) -> float:
    """golden：解析面积（Shoelace 闭式）[µm²]。"""
    return float(shoelace_area(tuple(_poly)))


def cand_b458(N: int = 16, _poly=POLY, nx=NX, ny=NY, dl=DL_UM) -> float:
    """候选：**亚格平均**栅格化面积 `Σ frac · dl²` [µm²]（平台 `rasterize_polygon`）。

    `N` = 离散参数 `subpixel`（每格 s×s 子采样 ⇒ 边界格分数填充，s→∞ 精确）。
    """
    vf = _vf()
    s = int(N)
    if s < 1:
        raise ValueError("subpixel 须 ≥ 1")
    frac = vf.rasterize_polygon(list(_poly), int(nx), int(ny), float(dl), s)
    return float(np.asarray(frac, dtype=float).sum()) * float(dl) * float(dl)


# ===========================================================================
# 逐锚默认档 / 判据 D 扫描网格 / tol
# ===========================================================================
#: 默认档 = 判据 D 扫描网格**末端**（血案：默认档必须等于扫描末端）
_N_BY_BID = {
    "B458": 16,
}
#: 判据 D 扫描网格（5 档 · 等比 ⇒ 线性收敛型；覆盖 `1e-15 < 粗端 < tol` 窗口）
_GRID_BY_BID = {
    "B458": [1, 2, 4, 8, 16],
}
#: 逐锚 tol（按「余量 ≥ 2 且 |golden|/tol ≥ 13.5、粗端 < tol」标定；只收紧不放松）
_TOL_BY_BID = {
    "B458": 5e-2,
}

_CASES = [
    ("B458", golden_b458, cand_b458, {}),
]


if __name__ == "__main__":
    print("=== B-32 几何栅格化收敛 × 解析 Shoelace（B-458）自检 ===")
    print("\n%-6s %16s %18s %12s %10s %-9s %-9s %s"
          % ("锚", "golden", "cand(默认档)", "|Δ|", "margin", "基线>1e-12", "gold/tol", "判定"))
    bad = 0
    for bid, gf, cf, p in _CASES:
        g = gf(**p)
        c = cf(N=_N_BY_BID[bid], **p)
        dd = abs(g - c)
        tol = _TOL_BY_BID[bid]
        margin = (tol / dd) if dd > 0 else float("inf")
        base_ok = dd > 1e-12
        gr = abs(g) / tol
        ok = (margin >= 2.0) and base_ok and (gr >= 13.5)
        bad += 0 if ok else 1
        print("%-6s %16.10f %18.10f %12.3e %10.1f %-9s %-9.1f %s"
              % (bid, g, c, dd, margin, base_ok, gr, "OK" if ok else "BAD"))

    print("\n--- 判据 D 扫描（残差随 subpixel 单调下降；比值来自实测，不按标称阶写死）---")
    for bid, gf, cf, p in _CASES:
        g = gf(**p)
        grid = _GRID_BY_BID[bid]
        row, prev, mono, ratios = [], None, True, []
        for nn in grid:
            dd = abs(g - cf(N=nn, **p))
            if prev is not None:
                ratio = (prev / dd) if dd > 0 else float("nan")
                ratios.append(ratio)
                if dd > prev:
                    mono = False
                row.append("%d:%.2e(x%.2f)" % (nn, dd, ratio))
            else:
                row.append("%d:%.2e" % (nn, dd))
            prev = dd
        d_last, d_first = abs(g - cf(N=grid[-1], **p)), abs(g - cf(N=grid[0], **p))
        tol = _TOL_BY_BID[bid]
        print("%-6s %-58s %-8s 比值 %.2f~%.2f  粗端>1e-15:%s  粗端<tol:%s  默认档>1e-12:%s"
              % (bid, "  ".join(row), "MONO" if mono else "NONMONO",
                 min(ratios), max(ratios), d_first > 1e-15, d_first < tol, d_last > 1e-12))

    # 跨源一致：独立 Shoelace ≡ 平台 polygon_area（机器精度）
    vf = _vf()
    g_a, g_b = golden_b458(), float(vf.polygon_area(list(POLY)))
    print("\n跨源一致（独立 Shoelace ≡ 平台 polygon_area）：|Δ|=%.3e ⇒ %s"
          % (abs(g_a - g_b), "OK" if abs(g_a - g_b) < 1e-12 else "MISMATCH"))
    bad += 0 if abs(g_a - g_b) < 1e-12 else 1

    print("\nBAD =", bad, "（应为 0）")
