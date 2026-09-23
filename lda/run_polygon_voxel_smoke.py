"""v0.9.133 P4-G16 · 任意几何 3D 网格 smoke（里程碑 **M-4** 下半）。

## 为什么建它

`voxel_field.LayoutLayer` 只有**矩形**（x0/x1/y0/y1/z0/z1）⇒ 锥形、弯曲、
斜栅、带孔结构**表达不了**。规划 P4 的出口判据第二条正是
**「非矩形几何可体素化」**，并把它定为 G13/G14 的**前置**。

本 smoke 把「非矩形能体素化」变成 9 组死判据，且**判据 D 用「亚格平均」**
做细化参数（subpixel 1→2→4→8 ⇒ 面积误差**严格单调降**）。

## 断言清单

  ①a 凹形 L：解析面积 vs 栅格（精确）
  ①b 斜边三角形：亚格平均下与解析面积一致
  ①c 带孔（even-odd + 反向内环）：填充面积 / 孔心为 0 / 环上为 1
  ①d 自交（弓形）：**even-odd 填充 = 8**，而**鞋带公式 = 0**
      ⇒ 把「代数面积 ≠ 填充面积」这件容易搞错的事钉成判据
  ② **判据 D**：subpixel 1/2/4/8 ⇒ 面积相对误差严格单调降、粗端 > 1e-13、细端 < tol
  ③ 与既有矩形管线 `voxelize_rectangular` **逐位一致**（0° 对齐矩形）
  ④a 取向无关（顶点反转 ⇒ 逐位相同）
  ④b 旋转十二边形（12 个角度 / 非矩形）：**细端**（s=16/32/64）误差 < tol
  ④c 旋转 45° 矩形（一般位置）：**整体**收敛 `err(s=1)/err(s=128) ≥ 10×`
      🔴 并**如实登记**其**非严格单调**的实测序列 —— 见下方「亚格量化相干」注
  ⑤ 反向护栏：畸形输入**必 raise**（5 类）+ 合法**必过**
  ⑥ 空 layers ⇒ 全背景；z 挤出区间外保持背景
  ⑦ 亚格平均语义：内部格恰为 1.0 / 外部格恰为 0.0 / 边界格 ∈ (0,1)；ε 按面积加权
  ⑧ 管线等价：与 `voxelize_stack`（**已进 FDTD 链路**的退化路径）逐位一致
  ⑨ 判决依据零 LLM / 零网络

运行：python run_polygon_voxel_smoke.py
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "lda_solver"))

from lda_harness.smoke_kit import make_check                    # noqa: E402

_PASS = 0
_FAIL = 0

check = make_check(globals(), ok_key="_PASS", bad_key="_FAIL",
                   indent="  ", detail_fmt='  ({d})', return_ok=True)

DL = 0.25
N = 24                      # 24×24 格 ⇒ 6µm × 6µm
N32 = 32
TOL_D = 5e-3                # 判据 D 的细端容差

# 几何常量（全部坐标是 dl 的整数倍 ⇒ 与矩形管线可逐位对齐）
L_SHAPE = [(0, 0), (4, 0), (4, 1), (1, 1), (1, 4), (0, 4)]
L_AREA = 4.0 * 1.0 + 1.0 * 3.0                     # 取并集：4 + 3 = 7
TRI = [(0, 0), (4, 0), (0, 3)]
TRI_AREA = 0.5 * 4.0 * 3.0                          # 6
BOWTIE = [(0, 0), (4, 4), (4, 0), (0, 4)]
BOWTIE_FILL = 8.0                                   # 两瓣各 4
RING = [(0, 0), (4, 0), (4, 4), (0, 4), (0, 0),     # 外环
        (1, 1), (1, 3), (3, 3), (3, 1), (1, 1)]     # 反向内环（孔）+ 桥
RING_FILL = 12.0                                    # 16 − 4


def _circle(R, cx, cy, n=360):
    return [(cx + R * math.cos(2 * math.pi * k / n),
             cy + R * math.sin(2 * math.pi * k / n)) for k in range(n)]


def _area(frac, dl=DL):
    return float(frac.sum()) * dl * dl


def _strictly_decreasing(v):
    return all(v[i] > v[i + 1] for i in range(len(v) - 1))


def _ngon(R, cx, cy, k, phase_deg):
    """正 k 边形（相位 phase_deg）—— 多角度非矩形几何。"""
    ph = math.radians(phase_deg)
    return [(cx + R * math.cos(ph + 2 * math.pi * i / k),
             cy + R * math.sin(ph + 2 * math.pi * i / k)) for i in range(k)]


def _rot_sq(side, cx, cy, deg, dx=0.0, dy=0.0):
    """边长 side 的矩形：绕中心旋转 deg 度再平移 (dx, dy)（矩形管线表达不了）。"""
    a = math.radians(deg)
    h = side / 2.0
    return [(cx + dx + px * math.cos(a) - py * math.sin(a),
             cy + dy + px * math.sin(a) + py * math.cos(a))
            for px, py in ((-h, -h), (h, -h), (h, h), (-h, h))]


# 🔴 亚格量化相干（本轮实测）：`subpixel=s` 的每格填充率 = s² 个采样点的**计数**/s²
#   ⇒ 固有量化台阶 1/s²。对**高对称斜边**（如 45° 正方形）每个边界格的量化误差
#   **同号**（实测 8 个边界格误差全为 +0.0165），于是**相干叠加**成面积偏置，并使
#   误差序列**非严格单调**（实测 s=1..128：6.250e-02 → 3.125e-02 → 1.172e-02 →
#   1.074e-02 → 2.441e-04 → 5.310e-03 → 2.548e-03 → 1.167e-03，收敛仅 ~1/s）。
#   对照：曲线（②）与多角度（④b）几何的误差在不同角度间**互相抵消** ⇒ 序列光滑单调。
#   ⇒ 判据口径（不是调松容差，是换承担者）：「严格单调的判据 D」由**曲线几何**承担；
#   斜边几何只声称「整体收敛」+「细端可达精度」，序列**如实登记**，不粉饰成单调。
#   另一独立佐证：**对称配置下栅格化精确到机器精度**（正十二边形中心置于格点角 ⇒
#   面积误差 1.8948e-16）⇒ 说明实现语义正确，误差纯属量化相干，不是算法缺陷。


def main() -> int:
    t0 = time.time()
    from lda_solver import voxel_field as vf

    # ---------------------------------------------------------------
    print("① 非矩形几何正确体素化")
    fL = vf.rasterize_polygon(L_SHAPE, N, N, DL, subpixel=1)
    eL = abs(_area(fL) - L_AREA) / L_AREA
    check("①a 凹形 L：栅格面积 == 解析面积（rel < 1e-12）", eL < 1e-12,
          "解析 %.3f vs 栅格 %.6f（rel %.2e）" % (L_AREA, _area(fL), eL))

    fT = vf.rasterize_polygon(TRI, N32, N32, DL / 2, subpixel=8)
    eT = abs(_area(fT, DL / 2) - TRI_AREA) / TRI_AREA
    check("①b 斜边三角形：亚格平均面积为解析值（rel < 5e-3）", eT < TOL_D,
          "解析 %.3f vs 栅格 %.6f（rel %.2e）" % (TRI_AREA, _area(fT, DL / 2), eT))

    fR = vf.rasterize_polygon(RING, N32, N32, DL, subpixel=4)
    centre = float(fR[16, 16])                 # 孔心（x≈4.1µm, y≈4.1µm）应 0
    on_ring = float(fR[2, 6])                  # 外环与孔之间（x≈0.6, y≈1.6）应 1
    eR = abs(_area(fR) - RING_FILL) / RING_FILL
    check("①c 带孔（even-odd + 反向内环）：填充面积正确", eR < 1e-3,
          "解析 %.1f vs 栅格 %.4f（rel %.2e）" % (RING_FILL, _area(fR), eR))
    check("①c 带孔：孔心为 0 且环上为 1（even-odd 语义正确）",
          centre < 1e-6 and on_ring > 0.999,
          "孔心格 %.6f（应 0）· 环上格 %.6f（应 1）" % (centre, on_ring))

    fB = vf.rasterize_polygon(BOWTIE, N32, N32, DL, subpixel=4)
    aB = _area(fB)
    shoe = vf.polygon_area(BOWTIE)
    check("①d 自交弓形：even-odd 填充 == 解析 8（rel < 1e-3）",
          abs(aB - BOWTIE_FILL) / BOWTIE_FILL < 1e-3,
          "解析 %.1f vs 栅格 %.4f" % (BOWTIE_FILL, aB))
    check("①d 自交弓形：**鞋带公式给出 0**（代数面积 ≠ 填充面积）",
          shoe < 1e-12, "polygon_area = %.3e" % shoe)

    # ---------------------------------------------------------------
    print("② 判据 D：亚格平均细化 ⇒ 面积误差严格单调降")
    print("③④ 回归等价与几何不变量")
    circ = _circle(2.0, 3.0, 3.0)
    exact = math.pi * 4.0
    errs = []
    for s in (1, 2, 4, 8):
        errs.append(abs(_area(vf.rasterize_polygon(circ, N, N, DL, subpixel=s))
                        - exact) / exact)
    seq = " → ".join("%.4e" % e for e in errs)
    check("②a 判据 D：面积相对误差随 subpixel（1/2/4/8）严格单调降",
          _strictly_decreasing(errs), "序列 %s" % seq)
    check("②b 判据 D：粗端未落地板（> 1e-13）", errs[0] > 1e-13,
          "粗端 %.4e" % errs[0])
    check("②c 判据 D：细端 < tol（%.0e）" % TOL_D, errs[-1] < TOL_D,
          "细端 %.4e（余量 %.1f×）" % (errs[-1], TOL_D / errs[-1]))

    g = vf.VoxelGrid(dl=DL, Nx=N, Ny=N, Nz=3)
    mats = {"air": 1.0, "core": 3.5}
    rect_lays = [vf.LayoutLayer("core", 4 * DL, 12 * DL, 4 * DL, 12 * DL, None, None)]
    poly_lays = [vf.LayoutPolygon("core", [(4 * DL, 4 * DL), (12 * DL, 4 * DL),
                                           (12 * DL, 12 * DL), (4 * DL, 12 * DL)])]
    e_rect = vf.voxelize_rectangular(rect_lays, mats, g, "air")
    e_poly = vf.voxelize_polygons(poly_lays, mats, g, "air", subpixel=1)
    dmax = float(np.abs(e_rect - e_poly).max())
    check("③ 与既有矩形管线逐位一致（0° 对齐矩形）", dmax == 0.0,
          "max|Δ| = %.3e" % dmax)

    fL_rev = vf.rasterize_polygon(list(reversed(L_SHAPE)), N, N, DL, subpixel=1)
    check("④a 取向无关：顶点反转 ⇒ 栅格逐位相同",
          bool(np.array_equal(fL, fL_rev)), "")

    # ④b 多角度非矩形（正十二边形，两个相位）⇒ 细端可达精度
    _R12 = 2.5
    _A12 = 0.5 * 12 * _R12 ** 2 * math.sin(2 * math.pi / 12)          # == 18.75
    fine_max, fine_det = 0.0, []
    for _ph in (30.0, 7.3):
        _pts = _ngon(_R12, 4.0, 4.0, 12, _ph)
        _ef = max(abs(_area(vf.rasterize_polygon(_pts, N32, N32, DL, subpixel=s))
                      - _A12) / _A12 for s in (16, 32, 64))
        fine_det.append("%.1f°→%.3e" % (_ph, _ef))
        fine_max = max(fine_max, _ef)
    check("④b 旋转十二边形（12 个角度 / 非矩形，矩形管线表达不了）：细端（s=16/32/64）< tol",
          fine_max < TOL_D,
          "细端 max %s（余量 %.1f×）" % (" · ".join(fine_det), TOL_D / fine_max))

    # ④c 45° 矩形（一般位置）：整体收敛 + **如实登记**非单调序列（见上方「量化相干」注）
    sq45 = _rot_sq(2.0, 4.0, 4.0, 45.0, 0.037, 0.011)
    seq45 = [abs(_area(vf.rasterize_polygon(sq45, N32, N32, DL, subpixel=s)) - 4.0) / 4.0
             for s in (1, 2, 4, 8, 16, 32, 64, 128)]
    check("④c 旋转 45° 矩形（一般位置）：整体收敛 err(s=1)/err(s=128) ≥ 10×",
          seq45[0] / seq45[-1] >= 10.0,
          "s=1..128 %s ⇒ %.1f×（**非严格单调**，成因见「亚格量化相干」注）"
          % (" → ".join("%.3e" % e for e in seq45), seq45[0] / seq45[-1]))

    # ---------------------------------------------------------------
    print("⑤ 反向护栏：畸形必 raise + 合法必过")
    bad_cases = [
        ("顶点数 < 3", lambda: vf.rasterize_polygon([(0, 0), (1, 1)], N, N, DL)),
        ("坐标 NaN", lambda: vf.rasterize_polygon(
            [(0, 0), (1, float("nan")), (2, 0)], N, N, DL)),
        ("坐标非数值", lambda: vf.rasterize_polygon(
            [(0, 0), (1, 1), ("a", 0)], N, N, DL)),
        ("subpixel < 1", lambda: vf.rasterize_polygon(L_SHAPE, N, N, DL, 0)),
        ("网格非法（nx=0）", lambda: vf.rasterize_polygon(L_SHAPE, 0, N, DL)),
    ]
    raised, missed = [], []
    for name, fn in bad_cases:
        try:
            fn()
            missed.append(name)
        except ValueError:
            raised.append(name)
        except Exception as exc:                       # noqa: BLE001
            missed.append("%s(%s)" % (name, type(exc).__name__))
    check("⑤a 畸形输入必 raise ValueError（%d 类）" % len(bad_cases),
          not missed, "应 raise 未 raise: %s" % missed if missed
          else "全部 raise：%s" % "/".join(raised))
    good = vf.rasterize_polygon(L_SHAPE, 8, 8, DL, subpixel=2)
    check("⑤b 合法必过（配 ⑤a 的反向护栏）",
          good.shape == (8, 8) and float(good.min()) >= 0.0
          and float(good.max()) <= 1.0,
          "shape=%s 值域 [%.3f, %.3f]" % (good.shape, good.min(), good.max()))

    # ---------------------------------------------------------------
    print("⑥⑦ 空集 / z 挤出 / 亚格平均语义")
    empty = vf.voxelize_polygons([], mats, g, "air")
    check("⑥a 空 layers ⇒ 全背景", bool((empty == 1.0).all()),
          "唯一值 %s" % np.unique(empty).tolist())
    gz = vf.VoxelGrid(dl=DL, Nx=N, Ny=N, Nz=4)
    lay_z = [vf.LayoutPolygon("core", [(0.0, 0.0), (4 * DL, 0.0), (4 * DL, 4 * DL),
                                       (0.0, 4 * DL)], z0=DL, z1=3 * DL)]
    ez = vf.voxelize_polygons(lay_z, mats, gz, "air")
    ok_z = (float(ez[:, :, 0].max()) == 1.0 and float(ez[:, :, 1].max()) == 3.5 ** 2
            and float(ez[:, :, 3].max()) == 1.0)
    check("⑥b z 挤出：区间外保持背景、区间内为材料", ok_z,
          "z=0 %.1f · z=1 %.2f · z=3 %.1f" % (ez[:, :, 0].max(),
                                              ez[:, :, 1].max(), ez[:, :, 3].max()))

    fC8 = vf.rasterize_polygon(circ, N, N, DL, subpixel=8)
    interior = float((fC8 == 1.0).sum())
    exterior = float((fC8 == 0.0).sum())
    boundary = int(((fC8 > 0.0) & (fC8 < 1.0)).sum())
    check("⑦a 亚格平均语义：内部格恰 1.0 / 外部格恰 0.0 / 边界格分数（∈(0,1)）",
          interior > 0 and exterior > 0 and boundary > 0
          and interior + exterior + boundary == N * N,
          "内 %d / 外 %d / 边界 %d（总 %d）"
          % (interior, exterior, boundary, N * N))
    lay_c = [vf.LayoutPolygon("core", circ)]
    ec = vf.voxelize_polygons(lay_c, mats, g, "air", subpixel=8)
    lo = float(ec[:, :, 0][fC8 == 0.0].max()) if exterior else 0.0
    hi = float(ec[:, :, 0][fC8 == 1.0].min()) if interior else 0.0
    check("⑦b ε 按面积加权：外部格 == ε_bg、内部格 == ε_mat",
          lo == 1.0 and hi == 3.5 ** 2,
          "外 %.6f（应 1）· 内 %.6f（应 12.25）" % (lo, hi))

    # ---------------------------------------------------------------
    print("⑧ 管线等价：与 voxelize_stack（已进 FDTD 链路）逐位一致")
    wl, dl_f, buf, sponge, ny, nz = 1.55, 20.0, 40, 60, 2, 2
    layers = [(float("inf"), 1.0), (0.2, 2.0), (float("inf"), 1.0)]
    # 复刻 _build_interior 的整数吸附（与 voxel_field 内同一内核）
    from fdtd3d import _build_interior
    th_min = 0.2
    k = max(2, int(round(th_min / (wl / dl_f))))
    dl = th_min / k
    prof, n0, nL = _build_interior(layers, dl, buf)
    eps_stack, meta = vf.voxelize_stack(layers, dl, buf, sponge, ny, nz)
    Nx = eps_stack.shape[0]
    i0 = sponge + buf
    nc = int(round(th_min / dl))
    poly = [vf.LayoutPolygon("film", [(i0 * dl, 0.0), ((i0 + nc) * dl, 0.0),
                                      ((i0 + nc) * dl, ny * dl), (i0 * dl, ny * dl)])]
    gp = vf.VoxelGrid(dl=dl, Nx=Nx, Ny=ny, Nz=nz)
    eps_poly = vf.voxelize_polygons(poly, {"air": 1.0, "film": 2.0}, gp, "air",
                                    subpixel=1)
    dmax2 = float(np.abs(eps_stack - eps_poly).max())
    check("⑧ 多边形路径与 stack 退化路径**逐位一致**（⇒ 可直接进 FDTD 链路）",
          dmax2 == 0.0,
          "Nx=%d 膜 %d 格 · max|Δ| = %.3e" % (Nx, nc, dmax2))

    # ---------------------------------------------------------------
    # ⑨ 红线：判决依据零 LLM / 零网络（扫登记数据，不扫源码）
    #
    # 🔴 v0.9.133（护栏自证纪律）：登记数据**必须含至少一处可注入的文本**，否则本
    #   判据在结构上**不可证伪**（数值 payload 下的数据侧突变只会让比较式抛
    #   TypeError = 崩溃，而非判据变红）⇒ 「没被验证过的护栏」。故登记**内核模块名**
    #   作为出处身份，使 `scripts/p4_polygon_probe.py` 能注入网络 token 证明**会响**。
    # ---------------------------------------------------------------
    payload = json.dumps({"kernels": [vf.__name__],
                          "L": _area(fL), "ring": _area(fR), "bowtie": aB,
                          "circle_errs": errs, "tri": _area(fT, DL / 2),
                          "dodec_fine": fine_det, "sq45_seq": seq45},
                         ensure_ascii=False).lower()
    net_pat = ("openai", "anthropic", "chatgpt", "requests.", "http://", "https://")
    hit = [t for t in net_pat if t in payload]
    check("⑨ 判决依据（栅格化登记数据）零 LLM / 零网络引用", not hit, "命中 %s" % hit)

    elapsed = time.time() - t0
    report = {
        "p4_g16": "arbitrary-polygon voxelization",
        "dl_um": DL, "grid": [N, N],
        "areas": {"L": _area(fL), "L_exact": L_AREA,
                  "triangle": _area(fT, DL / 2), "triangle_exact": TRI_AREA,
                  "ring": _area(fR), "ring_exact": RING_FILL,
                  "bowtie_fill": aB, "bowtie_fill_exact": BOWTIE_FILL,
                  "bowtie_shoelace": shoe},
        "criterion_D": {"param": "subpixel", "values": [1, 2, 4, 8],
                        "rel_err": errs, "tol": TOL_D,
                        "strictly_decreasing": _strictly_decreasing(errs)},
        "rotated_geom": {
            "dodecagon_R": _R12, "dodecagon_fine_s": [16, 32, 64],
            "dodecagon_fine": fine_det, "dodecagon_fine_max": fine_max,
            "sq45_seq_s": [1, 2, 4, 8, 16, 32, 64, 128],
            "sq45_rel_err": seq45,
            "sq45_strictly_decreasing": _strictly_decreasing(seq45),
            "note": "高对称斜边 ⇒ 半格量化误差相干 ⇒ 序列非单调；判据 D 由曲线几何承担",
        },
        "rect_bitwise_equal": dmax == 0.0,
        "stack_bitwise_equal": dmax2 == 0.0,
        "malformed_raised": raised,
        "elapsed_s": round(elapsed, 2),
    }
    out_dir = os.path.join(_HERE, "reports")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "polygon_voxel_report.json")
    from lda_harness import deterministic as _det
    _det.write_json(out_path, report)
    print("\n报告：%s" % out_path)
    print("\nP4-G16 任意几何网格 smoke：%s  (%.1fs)"
          % ("ALL GREEN" if _FAIL == 0 else "HAS FAILURE", elapsed))
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
