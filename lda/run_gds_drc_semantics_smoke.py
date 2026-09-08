#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""几何级 DRC（`lda_l2.gds_drc.check_geometry`）语义 smoke · v0.9.60

**为什么要这个 smoke**：DRC 全链路盘点（2026-09-08）实测抓出两个真缺陷，
都是「判据看着在跑、其实不响/乱响」：

1. **最小线宽度量把「多边形细分步长」当成线宽** —— 旧 `_poly_width` 取相邻
   顶点最小距离。SymmetricYBranch 的 boundary 沿 x 以 0.039µm 步长离散
   （67 点），旧度量报「最小边 0.039µm < 0.12µm」，而实际波导宽 0.5µm
   ⇒ **几何 DRC 假红**。现改为凸包最小平行带宽度（标准定义）。
2. **`min_width_ok` / `min_spacing_ok` 两个标志位是死的（恒 True）** ——
   旧实现用 `v.startswith(("PATH 线宽","多边形最小边"))` 反解违规类别，而
   实际字符串以「结构名: 」开头 ⇒ 永不匹配；`min_spacing_ok` 更把正则
   `".*↔"` 当字面量传给 startswith ⇒ 同样恒 True。实测：构造 2 条线宽违规
   + 1 条间距违规，两标志仍报 True ⇒ **假绿**。现改为违规**分类累积**。

本 smoke 全部**实跑生产函数**（不在 smoke 内另写一份同式复算），并对每条
正向判据配反向个案。

CI core 135→136。
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA = os.path.dirname(_HERE)
for _p in (_LDA, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lda_l2 import gds_export                                    # noqa: E402
from lda_l2.gds_drc import (                                     # noqa: E402
    DEFAULT_GEOM_RULES, check_geometry,
)

_FAILED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> bool:
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}" + (f"  |  {detail}" if detail else ""))
    if not cond:
        _FAILED.append(name)
    return cond


def _structs(**struct_elements) -> dict:
    """把 {结构名: [gds 元素 bytes]} 走真实 GDS 编码+解析，拿到检查入参。"""
    b = gds_export.gds_library("SMOKE", struct_elements)
    return gds_export.parse_gds_polygons(b).get("structures", {})


def _taper(n: int = 60, x0: float = 0.0, x1: float = 1.25,
           w0: float = 0.5, w1: float = 0.8) -> list:
    """沿 x 细分、局部宽 0.5→0.8µm 的锥形边界（模拟 Y 分支渐变段）。

    细分步长 = (x1-x0)/n ≈ 0.021µm，**远小于**最小线宽 0.12µm——这正是旧
    度量会误报的构造。
    """
    top, bot = [], []
    for i in range(n + 1):
        t = i / n
        x = x0 + (x1 - x0) * t
        y = (w0 + (w1 - w0) * t) / 2.0
        top.append((x, y))
        bot.append((x, -y))
    return top + bot[::-1]


def main() -> int:
    print("=== 几何级 DRC 语义 smoke（v0.9.60）===")
    min_w = DEFAULT_GEOM_RULES["min_width_um"]

    # ① 细分步长不得被当成线宽（旧实现的假红）
    st = _structs(taper=[gds_export.boundary(1, _taper())])
    rep = check_geometry(st)
    check("① 细分步长≠线宽：锥形（局部宽 0.5→0.8µm，步长 0.021µm）不报宽度违规",
          rep["all_pass"] and rep["min_width_ok"],
          f"violations={rep['violations'][:2]}")
    # 反向：同一几何用「旧度量」（相邻顶点最小距离）确实会误报 ⇒ 证明①不是恒真
    pts = st["taper"][0]["points_um"]
    old_metric = min(((pts[i][0] - pts[i - 1][0]) ** 2
                      + (pts[i][1] - pts[i - 1][1]) ** 2) ** 0.5
                     for i in range(1, len(pts)))
    check("①-r 反向：旧度量（相邻顶点最小距离）在同一几何上会误报",
          old_metric < min_w,
          f"旧度量={old_metric:.4f}µm < {min_w}µm ⇒ 假红确实存在过")

    # ② 真细线必须检出，且 min_width_ok 必须跟着变 False（死标志修复）
    thin = [(0.0, 0.0), (5.0, 0.0), (5.0, 0.04), (0.0, 0.04)]
    st = _structs(thin=[gds_export.boundary(1, thin)])
    rep = check_geometry(st)
    check("② 真细线 0.04µm 检出宽度违规",
          (not rep["all_pass"]) and (not rep["min_width_ok"])
          and rep["n_width_violations"] >= 1,
          f"n_width={rep['n_width_violations']} v={rep['violations'][:1]}")
    check("②-b 报出的宽度值≈真值 0.040µm（不是 0、不是步长）",
          any("0.040µm" in v for v in rep["violations"]),
          str(rep["violations"][:2]))

    # ③ 小面积必须检出
    tiny = [(20.0, 20.0), (20.1, 20.0), (20.1, 20.1), (20.0, 20.1)]
    st = _structs(tiny=[gds_export.boundary(1, tiny)])
    rep = check_geometry(st)
    check("③ 小面积 0.01µm² 检出面积违规且 min_area_ok=False",
          (not rep["all_pass"]) and (not rep["min_area_ok"])
          and rep["n_area_violations"] >= 1,
          f"v={rep['violations'][:2]}")

    # ④ 间距必须检出，且 min_spacing_ok 必须跟着变 False（死标志修复）
    a = [(0.0, 0.0), (5.0, 0.0), (5.0, 0.5), (0.0, 0.5)]
    b = [(0.0, 0.53), (5.0, 0.53), (5.0, 1.0), (0.0, 1.0)]
    st = _structs(pa=[gds_export.boundary(1, a)], pb=[gds_export.boundary(1, b)])
    rep = check_geometry(st)
    check("④ 间距 0.03µm 检出间距违规且 min_spacing_ok=False",
          (not rep["min_spacing_ok"]) and rep["n_spacing_violations"] >= 1,
          f"n_sp={rep['n_spacing_violations']} v={rep['violations'][:1]}")

    # ⑤ 三类标志与分类计数必须自洽（杜绝「标签≠行为」回潮）
    allv = _structs(thin=[gds_export.boundary(1, thin)],
                    tiny=[gds_export.boundary(1, tiny)],
                    pa=[gds_export.boundary(1, a)],
                    pb=[gds_export.boundary(1, b)])
    rep = check_geometry(allv)
    check("⑤ 标志自洽：min_*_ok ⟺ 对应 n_*_violations == 0",
          rep["min_width_ok"] == (rep["n_width_violations"] == 0)
          and rep["min_spacing_ok"] == (rep["n_spacing_violations"] == 0)
          and rep["min_area_ok"] == (rep["n_area_violations"] == 0)
          and rep["all_pass"] == (len(rep["violations"]) == 0),
          f"w={rep['n_width_violations']} sp={rep['n_spacing_violations']} "
          f"a={rep['n_area_violations']} total={len(rep['violations'])}")
    check("⑤-b 三类违规都被计数（缺一即说明某类判定又变成死判定）",
          rep["n_width_violations"] >= 1 and rep["n_spacing_violations"] >= 1
          and rep["n_area_violations"] >= 1)

    # ⑥ 凹多边形必须诚实标注「上界」（不假称精确覆盖）
    ell = [(0, 0), (4, 0), (4, 1), (1, 1), (1, 3), (0, 3)]     # L 形（凹）
    st = _structs(L=[gds_export.boundary(1, ell)])
    rep = check_geometry(st)
    check("⑥ 凹多边形：标注凹形上界（不假称精确最小宽度）",
          rep["n_concave_polys"] >= 1 and ("凹多边形" in rep["width_note"]),
          f"concave={rep['n_concave_polys']} note={rep['width_note'][:80]}")

    # ⑦ 零元素：既不假绿也不假红，诚实标未覆盖
    st = _structs(empty=[])
    rep = check_geometry(st)
    check("⑦ 零元素：无违规但间距标「未覆盖」（不假称已查）",
          rep["n_elements"] == 0 and not rep["violations"]
          and "未覆盖" in rep["spacing_note"],
          f"n={rep['n_elements']} note={rep['spacing_note'][:40]}")

    # ⑧ PATH 声明线宽仍走 width 字段（不为新度量所动）
    st = _structs(p=[gds_export.path(1, 0.05, [(0, 0), (10, 0)])])
    rep = check_geometry(st)
    check("⑧ PATH 线宽 0.05µm 仍按声明线宽判违规",
          (not rep["all_pass"]) and any("PATH 线宽" in v for v in rep["violations"]),
          str(rep["violations"][:1]))

    print("\n=== 几何级 DRC 语义 smoke: "
          + ("ALL GREEN" if not _FAILED else f"{len(_FAILED)} FAIL") + " ===")
    if _FAILED:
        for n in _FAILED:
            print("   FAIL:", n)
    return 0 if not _FAILED else 1


if __name__ == "__main__":
    sys.exit(main())
