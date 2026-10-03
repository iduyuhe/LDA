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

import io
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.gds_export import (gds_library, layout_elements, layout_from_ir,
                               gds_bytes_for, layout_from_library, write_gds,
                               parse_gds, svg_preview, 
                               ring_ring_polygon)
from lda_ir import (IRModel, Waveguide, RingResonator, DirectionalCoupler,
                    SymmetricYBranch)


# 🔴 check 已归一：实现**单一定义**在 lda_harness/smoke_kit.py
#   （v0.9.113 · 波次 2 · 源自 2026-09-19 审计 F-07）。调用方尾部
#   （含模块级计数器读取）与输出格式**均未改**，见 smoke_kit 模块 docstring。
from lda_harness.smoke_kit import check_raise as check  # noqa: E402


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


# ---------------------------------------------------------------------------
# GDSII UNITS 互操作性门禁（v0.9.184 补）
#   背景：v0.9.170 前 REAL8 编码器把 UNITS 第二值写成 1/DBU=1000（语义错位），
#   标准生态工具（gdstk / KLayout / gdsfactory）读到的**物理尺度全错**。编码器
#   修好后，**已入库的 GDS 未重生成** ⇒ 直到一次全量 CI 才暴露（30/47 个坏）。
#   本段把「UNITS 必须为标准 (0.001, 1e-9)」钉成常驻判据 + 反向探针。
# ---------------------------------------------------------------------------
_GDS_UNITS_OK = (0.001, 1e-9)
_GDS_SCAN_SKIP = {".git", "node_modules", "__pycache__", ".venv", "build", "dist",
                  ".mypy_cache", ".pytest_cache"}


def _decode_gds_real8(b: bytes) -> float:
    """独立实现 GDSII REAL8：bit7=符号 · bit0-6=excess-64 指数 · 56-bit 基-16 尾数。

    刻意**不复用** `lda_l2.gds_export` 的编码器 —— 同源实现会让「编码器坏 ⇒ 读回
    也坏」的自证闭环掩盖真实缺陷。本门禁正是靠这条独立性抓出 v0.9.170 前的坏文件。
    """
    sign = -1.0 if (b[0] & 0x80) else 1.0
    exp = (b[0] & 0x7F) - 64
    frac = int.from_bytes(b[1:8], "big") / float(1 << 56)
    return sign * frac * (16.0 ** exp)


def _gds_units_of(data: bytes):
    """按记录流精确走到 UNITS(type=0x03) 记录，返回 (u1, u2)；结构坏则 None。

    不按字节串搜索 `00 14 03 05`：该序列在坐标数据里也可能出现（歧义）。
    """
    i, n = 0, len(data)
    while i + 4 <= n:
        ln = int.from_bytes(data[i:i + 2], "big")
        if ln < 4 or i + ln > n:
            return None
        rtype = data[i + 2]
        if rtype == 0x03:                      # UNITS
            if ln != 20:
                return None
            return (_decode_gds_real8(data[i + 4:i + 12]),
                    _decode_gds_real8(data[i + 12:i + 20]))
        if rtype == 0x04:                      # ENDLIB
            return None
        i += ln
    return None


def _iter_repo_gds() -> list:
    """全仓 glob `*.gds`。**不做目录白名单** —— 白名单式门禁会让新落点静默进盲区。"""
    root = os.path.dirname(_HERE)
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _GDS_SCAN_SKIP]
        for fn in filenames:
            if fn.lower().endswith(".gds"):
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def _units_ok(path: str) -> bool:
    try:
        data = io.open(path, "rb").read()
    except OSError:
        return False
    u = _gds_units_of(data)
    if u is None:
        return False
    return (abs(u[0] - _GDS_UNITS_OK[0]) < 1e-12
            and abs(u[1] - _GDS_UNITS_OK[1]) < 1e-24)


def check_gds_units_interop() -> bool:
    """全仓 GDS 的 UNITS 必须 == (0.001, 1e-9)（标准 GDSII 物理尺度）+ 反向探针。"""
    ok = True
    root = os.path.dirname(_HERE)
    paths = _iter_repo_gds()
    ok &= check(len(paths) >= 40,
                f"全仓 GDS 扫描覆盖（{len(paths)} 个 ≥ 40，防集合空/盲区）")
    bad = [p for p in paths if not _units_ok(p)]
    for p in bad[:10]:
        u = _gds_units_of(io.open(p, "rb").read())
        print(f"    🔴 UNITS 非标准：{os.path.relpath(p, root)}  (实测 {u})")
    ok &= check(not bad,
                f"全部 GDS 的 UNITS == (0.001, 1e-9)（坏 {len(bad)}/{len(paths)}）")
    # 🔴 反向探针：判据须能因「坏 UNITS」变红，否则同源恒绿、门禁形同虚设
    good = gds_library("LDA-PROBE", layout_from_ir(build_models()[0][1]))
    bad_bytes = good.replace(bytes.fromhex("3e4189374bc6a7f0"),
                             bytes.fromhex("3f50624dd2f1a9fc"), 1)
    ok &= check(bad_bytes != good and _gds_units_of(bad_bytes)[0] != _GDS_UNITS_OK[0],
                "反向探针：UNITS 篡改为旧坏编码(0.019625) ⇒ 判据可判坏（非恒绿）")
    return ok


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
                   "SymmetricYBranch", "BraggMirror"):
        ok &= check(expect in lib_structs,
                    f"D-12 器件库→GDS 导出 {expect}")
    lib_data = gds_library("LDA-LIB", lib_structs)
    ok &= check(parse_gds(lib_data)["n_structures"] >= 5,
                "器件库 GDS 含 ≥5 结构（含 Bragg 光栅 GDS 导出，v0.9.61 收口）")

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

    # 5) GDSII UNITS 互操作性（v0.9.184 补）
    ok &= check_gds_units_interop()

    print("\n=== D-14 GDSII 版图出口 smoke: "
          + ("ALL GREEN" if ok else "HAS FAIL") + " ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
