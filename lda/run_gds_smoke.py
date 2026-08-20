"""LDA · D-14 GDSII 版图出口 smoke（器件库/IR → 可制造版图）。

验证零依赖 GDSII 编码器 + IR→版图链路：
  1. 4 个已验证器件（Waveguide / RingResonator / DirectionalCoupler /
     SymmetricYBranch）由 L0 IR 生成 GDS 结构；
  2. GDSII 编码 → 写文件 → 最小解析器读回（round-trip：库名/结构数/元素数/层）；
  3. SVG 版图预览可渲染（浏览器可看）；
  4. 导出演示 GDS 文件。

退出码 0=全绿；非 0=有失败。
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.gds_export import (gds_library, layout_elements, layout_from_ir,
                               gds_bytes_for, layout_from_library, write_gds,
                               parse_gds, svg_preview, ring_polygon,
                               ring_ring_polygon)
from lda_ir import (IRModel, Waveguide, RingResonator, DirectionalCoupler,
                    SymmetricYBranch)


def check(cond: bool, msg: str) -> bool:
    if cond:
        print("OK  " + msg)
        return True
    print("FAIL " + msg)
    return False


def build_models() -> list:
    return [
        ("Waveguide", IRModel(domain="photon", name="wg-gds",
                              components=[Waveguide(id="wg", width=0.5)])),
        ("RingResonator", IRModel(domain="photon", name="ring-gds",
                                  components=[RingResonator(id="ring", R=10.0)])),
        ("DirectionalCoupler", IRModel(domain="photon", name="dc-gds",
                                       components=[DirectionalCoupler(
                                           id="dc", gap=0.3, Lc=10.0)])),
        ("SymmetricYBranch", IRModel(domain="photon", name="yb-gds",
                                     components=[SymmetricYBranch(
                                         id="yb", width=0.5, split_angle=10.0)])),
    ]


def main() -> int:
    print("=== D-14 GDSII 版图出口 smoke ===")
    ok = True

    # 1) 4 器件 IR → GDS 结构 + 编码 + 写文件 + 读回
    models = build_models()
    for name, m in models:
        structures = layout_from_ir(m)
        data = gds_library("LDA", structures)
        path = os.path.join(_HERE, "reports", f"gds_{name.lower()}.gds")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write_gds(path, data)
        ok &= check(len(data) > 50, f"{name}: GDS 文件非空（{len(data)} B）")
        parsed = parse_gds(data)
        ok &= check(parsed["libname"] == "LDA", f"{name}: 库名 LDA 读回正确")
        ok &= check(parsed["n_structures"] == 1, f"{name}: 结构数=1")
        prim = m.primary_component
        sid = prim.id
        ok &= check(sid in parsed["structures"]
                    and parsed["structures"][sid]["elements"] >= 1,
                    f"{name}: 结构[{sid}] 元素数≥1")
        ok &= check(1 in parsed["structures"][sid]["layers"],
                    f"{name}: 含 SOI 层(layer=1)")
        print(f"    {name:<20} GDS {len(data)} B  {path}")

    # 2) IR → GDS 字节便捷入口 + 多结构
    m1 = models[0][1]
    data1 = gds_bytes_for(m1, lib_name="LDA-DEMO")
    ok &= check(parse_gds(data1)["libname"] == "LDA-DEMO",
                "gds_bytes_for 便捷入口（自定义库名）")
    structures2 = {
        "TOP": layout_elements("Waveguide", {"width": 0.5}, length=20.0)
             + [layout_elements("RingResonator", {"R": 8.0}, wg_width=0.5)[0]],
    }
    data2 = gds_library("LDA-TOP", structures2)
    ok &= check(parse_gds(data2)["structures"]["TOP"]["elements"] == 2,
                "多元素结构（波导 PATH + 环形 BOUNDARY）")

    # 3) D-12 器件库 → GDS（批量导出已验证器件，串联 D-12→D-14）
    from lda_l2.device_library import get_default_library
    lib_structs = layout_from_library(get_default_library())
    for expect in ("Waveguide", "RingResonator", "DirectionalCoupler",
                   "SymmetricYBranch"):
        ok &= check(expect in lib_structs,
                    f"D-12 器件库→GDS 导出 {expect}")
    lib_data = gds_library("LDA-LIB", lib_structs)
    ok &= check(parse_gds(lib_data)["n_structures"] >= 4,
                "器件库 GDS 含 ≥4 结构（Bragg 一维堆叠跳过）")

    # 4) SVG 预览（几何描述渲染，浏览器可看）
    svg = svg_preview({
        "ring": [("boundary", {"points_um": ring_ring_polygon(10.0, 0.5)[0],
                               "layer": 1}),
                 ("boundary", {"points_um": ring_ring_polygon(10.0, 0.5)[1],
                               "layer": 1})],
        "bus":  [("path", {"points_um": [(-14, -10.25), (14, -10.25)],
                           "width_um": 0.5, "layer": 1})],
    })
    ok &= check("<svg" in svg and len(svg) > 300,
                "SVG 版图预览可渲染")
    svg_path = os.path.join(_HERE, "reports", "gds_preview.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"    SVG 预览 {len(svg)} B  {svg_path}")

    # 4) 导出演示 GDS（合成版图）
    demo_struct = {}
    for name, m in models:
        demo_struct.update(layout_from_ir(m))
    demo = gds_library("LDA-DEMO", demo_struct)
    demo_path = os.path.join(_HERE, "reports", "gds_demo.gds")
    write_gds(demo_path, demo)
    ok &= check(parse_gds(demo)["n_structures"] == 4,
                "演示 GDS 含 4 个器件结构（wg/ring/dc/yb）")
    print(f"    演示 GDS  {demo_path}  ({len(demo)} B, {len(demo_struct)} 结构)")

    print("\n=== D-14 GDSII 版图出口 smoke: "
          + ("ALL GREEN" if ok else "HAS FAIL") + " ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
