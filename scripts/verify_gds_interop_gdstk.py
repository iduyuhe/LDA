# -*- coding: utf-8 -*-
"""W3-2 互操作最小可用验证：LDA ↔ gdstk（gdsfactory 的 GDS I/O 后端）双向实测。

方向 A（LDA → 生态 · 「行业能消费 LDA 产出」）：
    LDA 主权导出 GDSII → gdstk.read_gds 读回 → 单元数/元素数/层/包围盒 与
    LDA 自有 parse_gds_polygons 对拍（包围盒容差 1e-6 µm = 1 DBU）。

方向 B（生态 → LDA · 「LDA 能消费生态产出」）：
    gdstk 造 gdsfactory 风格 GDS（FlexPath 波导 + Polygon 圈层）→ LDA
    parse_gds_polygons 解析 → 主权几何 DRC（check_geometry）必须全绿；
    再造一条故意违规（线宽 0.05µm < 0.12µm）→ DRC 必须判 FAIL。

⚠️ 依赖 gdstk（MIT，可选）：未安装时本脚本退出码 3，不阻断 LDA 自有链路。
运行：python scripts/verify_gds_interop_gdstk.py（解释器需装有 gdstk + numpy）。
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "lda"))

try:
    import gdstk  # noqa: F401
except ImportError:
    print("[SKIP] gdstk 未安装（可选依赖）：pip install gdstk 后重试本验证。")
    sys.exit(3)

_FAIL = 0


def check(name, cond, detail=""):
    global _FAIL
    tag = "PASS" if cond else "FAIL"
    if not cond:
        _FAIL += 1
    print("  [%s] %s%s" % (tag, name, ("  (%s)" % detail) if detail else ""))


# ---------------------------------------------------------------------------
# 方向 A：LDA 导出 → gdstk 读回对拍
# ---------------------------------------------------------------------------
def direction_a():
    print("\n=== 方向 A：LDA 主权导出 GDS → gdstk（生态侧）读回 ===")
    from lda_l2 import gds_export
    from lda_l2.gds_export import parse_gds_polygons

    # 环形谐振器风格几何：双环 BOUNDARY + 直波导 PATH（层 1/0，LDA SOI 惯例）
    inner = gds_export.ring_ring_polygon(R_um=12.0, width_um=0.5, n_sides=96)
    elems = [gds_export.boundary(1, poly) for poly in inner]
    elems.append(gds_export.path(1, 0.5, [(0, 20), (40, 20)]))
    lda_bytes = gds_export.gds_library("LDA_RING", {"ring_top": elems})

    lda_parsed = parse_gds_polygons(lda_bytes)
    lda_structs = lda_parsed["structures"]

    tmpdir = tempfile.mkdtemp(prefix="lda_gdstk_interop_")
    lda_gds_path = os.path.join(tmpdir, "lda_ring.gds")
    with open(lda_gds_path, "wb") as f:
        f.write(lda_bytes)
    lib = gdstk.read_gds(lda_gds_path)
    gf_cells = {c.name: c for c in lib.cells}
    check("gdstk 识别单元名（LDA libname/结构名保留）",
          set(gf_cells) == set(lda_structs),
          "gdstk=%s lda=%s" % (sorted(gf_cells), sorted(lda_structs)))

    for sname, lda_elems in lda_structs.items():
        cell = gf_cells[sname]
        # 元素数对拍（BOUNDARY→polygon + PATH→flexpath）
        n_lda = len(lda_elems)
        n_gf = len(cell.polygons) + len(cell.paths) + len(cell.references)
        check("A/%s 元素数一致（LDA %d ↔ gdstk %d）" % (sname, n_lda, n_gf),
              n_lda == n_gf)
        # 层号对拍（FlexPath 的 layers 是列表）
        gf_layers = ({p.layer for p in cell.polygons}
                     | {l for p in cell.paths for l in p.layers})
        lda_layers = {e["layer"] for e in lda_elems}
        check("A/%s 层号一致" % sname, gf_layers == lda_layers,
              "gdstk=%s lda=%s" % (gf_layers, lda_layers))
        # 包围盒对拍（1 DBU = 1e-3 µm 容差）。🔴 口径：只比 BOUNDARY 多边形
        # （gdstk 的 FlexPath bbox 含线宽半宽，LDA 解析存中心线 —— 语义差非误差）；
        # PATH 单独比 WIDTH。
        lda_polys = [e for e in lda_elems if e["kind"] == "boundary"]
        lda_paths = [e for e in lda_elems if e["kind"] == "path"]
        gf_polys = cell.polygons
        gf_paths = cell.paths
        check("A/%s PATH 线宽一致" % sname,
              all(abs(w - e["width"]) <= 1e-6
                  for p, e in zip(gf_paths, lda_paths)
                  for ws in p.widths() for w in ws),
              "gdstk=%s lda=%s" % ([[w for ws in p.widths() for w in ws]
                                    for p in gf_paths],
                                   [e["width"] for e in lda_paths]))
        if lda_polys:
            lda_pts = [pt for e in lda_polys for pt in e["points_um"]]
            lda_bbox = (min(x for x, _ in lda_pts), min(y for _, y in lda_pts),
                        max(x for x, _ in lda_pts), max(y for _, y in lda_pts))
            gf_bbox_pts = [tuple(v) for p in gf_polys for v in p.points]
            gf_bbox_obj = (min(x for x, _ in gf_bbox_pts), min(y for _, y in gf_bbox_pts),
                           max(x for x, _ in gf_bbox_pts), max(y for _, y in gf_bbox_pts))
            dev = max(abs(a - b) for a, b in zip(lda_bbox, gf_bbox_obj))
            check("A/%s BOUNDARY 包围盒一致（≤1e-6 µm）" % sname, dev <= 1e-6,
                  "dev=%.3g µm  lda=%s gf=%s" % (dev,
                                                 tuple(round(v, 4) for v in lda_bbox),
                                                 tuple(round(v, 4) for v in gf_bbox_obj)))


# ---------------------------------------------------------------------------
# 方向 B：gdstk（生态侧）写 GDS → LDA 解析 + 主权 DRC
# ---------------------------------------------------------------------------
def direction_b():
    print("\n=== 方向 B：gdstk 写 gdsfactory 风格 GDS → LDA 主权解析 + DRC ===")
    from lda_l2.gds_export import parse_gds_polygons
    from lda_l2.gds_drc import check_geometry

    tmpdir = tempfile.mkdtemp(prefix="lda_gdstk_interop_")
    ok_path = os.path.join(tmpdir, "gf_ok.gds")
    bad_path = os.path.join(tmpdir, "gf_bad.gds")

    # 合法版图：0.5µm 波导 + 大多边形（gdsfactory 导出的典型形态）
    lib = gdstk.Library(name="GFWRITE", unit=1e-6, precision=1e-9)
    c = lib.new_cell("gf_waveguide_dev")
    c.add(gdstk.FlexPath([(0, 0), (20, 0), (20, 10)], 0.5,
                          layer=1, datatype=0, simple_path=True))
    c.add(gdstk.Polygon([(0, 0), (5, 0), (5, 5), (0, 5)], layer=1, datatype=0))
    lib.write_gds(ok_path)

    # 故意违规：线宽 0.05µm < 主权 DRC 下限 0.12µm
    lib2 = gdstk.Library(name="GFWRITE", unit=1e-6, precision=1e-9)
    c2 = lib2.new_cell("gf_violation_dev")
    c2.add(gdstk.FlexPath([(0, 0), (10, 0)], 0.05,
                           layer=1, datatype=0, simple_path=True))
    lib2.write_gds(bad_path)

    for tag, path, want_pass in (("合法", ok_path, True), ("违规", bad_path, False)):
        with open(path, "rb") as f:
            data = f.read()
        parsed = parse_gds_polygons(data)
        check("B/%s LDA 解析出结构" % tag, len(parsed["structures"]) >= 1,
              "structures=%s" % list(parsed["structures"]))
        rep = check_geometry(parsed["structures"])
        if want_pass:
            check("B/%s 主权几何 DRC 全绿" % tag, rep["all_pass"],
                  "violations=%s" % rep["violations"][:3])
        else:
            check("B/%s 主权几何 DRC 必判 FAIL（线宽违规）" % tag,
                  (not rep["all_pass"])
                  and any("线宽" in v for v in rep["violations"]),
                  "violations=%s" % rep["violations"][:2])


if __name__ == "__main__":
    print("=" * 76)
    print("W3-2 互操作验证：LDA ↔ gdstk（gdsfactory GDS I/O 后端）双向实测")
    print("=" * 76)
    direction_a()
    direction_b()
    print("\n互操作验证：%s" % ("ALL PASS ✅" if _FAIL == 0 else "HAS FAILURE ❌"))
    sys.exit(0 if _FAIL == 0 else 1)
