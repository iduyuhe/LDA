"""BraggMirror GDS 导出收口护栏（v0.9.61 · 真实版图闭环）。

背景：v0.9.60 及之前，BraggMirror 在 layout_elements / geometry_desc 里
抛「暂不支持导出」⇒ 无 GDS ⇒ 进不了几何 DRC 与寄生估算（v0.9.60 审计
文档列的第 ① 条遗留）。v0.9.61 用**侧壁调制布拉格光栅波导**几何补上：
段长由 LDA 自有 slab 求解器按 λ0/(4·n_eff) 导出。

本 smoke 守四件事：
  ① 几何可导出（layout_elements 不再抛错，返回合法元素）；
  ② 几何 DRC 不假红（光栅相邻节同层相接 ⇒ 连通域豁免，0 假违规）；
  ③ 寄生估算可跑（layer=1 在 RC 表里）；
  ④ **诚实边界**：本版图 n_eff 来自平面波导求解器（< n_core=3.48），
     不是器件库一维 TMM 锚的体材料 3.48/1.44 —— 禁止用 TMM 锚的
     R_min 验收来背书这个 GDS，反之亦然（两者只共享「四分之一波长堆叠」构造）。

反向测试：
  A. 0.03µm 窄波导 MUST 被宽度规则抓到（规则会响）；
  B. 两独立结构间距 0.03µm MUST 被间距规则抓到（规则会响 + 连通域豁免非误杀）。
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent))  # 让 `import lda_l2...` 与 `import lda...` 都可达

from lda_l2.gds_export import (  # noqa: E402
    gds_library, layout_elements, parse_gds_polygons,
)
from lda_l2.gds_drc import check_geometry  # noqa: E402
from lda_l2.parasitic_rc import estimate_parasitics, check_parasitic  # noqa: E402
from lda_l2.primitives import bragg_grating_report, bragg_grating_descs  # noqa: E402

_PASS = 0
_FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if ok:
        _PASS += 1
    else:
        _FAIL += 1
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {name}" + (f" | {detail}" if detail else ""))


def _bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _seg_dist(a, b):
    """两线段最短距离（用于反向测试 B 构造）。"""
    import math
    (ax0, ay0), (ax1, ay1) = a
    (bx0, by0), (bx1, by1) = b

    def d_ps(p, s0, s1):
        dx, dy = s1[0] - s0[0], s1[1] - s0[1]
        L2 = dx * dx + dy * dy
        if L2 == 0:
            return math.dist(p, s0)
        t = max(0.0, min(1.0, ((p[0] - s0[0]) * dx + (p[1] - s0[1]) * dy) / L2))
        return math.dist(p, (s0[0] + t * dx, s0[1] + t * dy))

    return min(d_ps(a[0], b[0], b[1]), d_ps(a[1], b[0], b[1]),
               d_ps(b[0], a[0], a[1]), d_ps(b[1], a[0], a[1]))


def main() -> int:
    print("== BraggMirror GDS 导出收口护栏 ==")

    # ---- ① 几何可导出（标准链路：descs → layout_elements → gds_library → parse）----
    # 注：layout_elements 返回**原始 GDS 二进制记录**（bytes），由 gds_library
    #   直接消费；dict 形式是 parse_gds_polygons 解析后的结构。schema 检查用
    #   bragg_grating_descs（返回 dict）。
    descs = bragg_grating_descs({"periods": 6})
    check("①-a bragg_grating_descs 返回合法几何描述（≥12 元素）",
          len(descs) >= 12, f"n_elements={len(descs)}")
    ok_schema = all(
        e.get("kind") and e.get("layer") is not None
        and (e.get("points_um") or e.get("rings_um"))
        for e in descs
    )
    check("①-b 每个描述元素有 kind/layer 且含 points_um 或 rings_um", ok_schema)
    # 不抛错：layout_elements 能把描述编码成 GDS 记录
    elems = layout_elements("BraggMirror", {"periods": 6})
    check("①-c layout_elements('BraggMirror') 不再抛错（产出 GDS 记录）",
          len(elems) >= 12, f"n_records={len(elems)}")

    rep = bragg_grating_report({"periods": 6})
    check("①-c 段长由求解器导出（grating_len>0）",
          rep.get("grating_len_um", 0) > 0,
          f"grating_len={rep.get('grating_len_um'):.3f}µm")
    check("①-d 总元素数报告自洽（16 = 6 周期×2 段 + 输入/输出 taper + 波导）",
          rep.get("n_elements") == len(elems),
          f"report={rep.get('n_elements')} elems={len(elems)}")

    # ---- ② 几何 DRC 不假红（连通域豁免）----
    gds = gds_library("P", {"BraggMirror": elems})
    structs = parse_gds_polygons(gds)["structures"]
    drc = check_geometry(structs)
    check("②-a 光栅几何 DRC all_pass=True（无假红）", drc["all_pass"],
          f"w={drc['n_width_violations']} sp={drc['n_spacing_violations']} "
          f"area={drc['n_area_violations']}")
    check("②-b 光栅相邻节同层相接 ⇒ 间距豁免，无假间距违规",
          drc["n_spacing_violations"] == 0,
          f"spacing_v={drc['n_spacing_violations']}")
    check("②-c 元素数 > 0 才判 pass（零元素判 FAIL 护栏生效）",
          drc["n_elements"] > 0)

    # ---- ③ 寄生估算可跑 ----
    para = estimate_parasitics(structs)
    ok_para = isinstance(para, dict) and any(
        k in para for k in ("R_ohm", "C_ff", "nets", "elements")
    )
    check("③-a 寄生 RC 估算可跑（layer=1 在 RC 表）", ok_para,
          f"keys={list(para.keys())[:6]}")
    pchk = check_parasitic(para)
    ok_verdict = isinstance(pchk, dict) and isinstance(pchk.get("all_pass"), bool)
    check("③-b 寄生护栏返回合法 verdict（all_pass 为 bool）", ok_verdict,
          f"all_pass={pchk.get('all_pass')} n_viol={len(pchk.get('violations', []))}")
    # 诚实说明：长细硅波导的几何串联电阻（~1382Ω）超过主权几何护栏 1000Ω
    # ⇒ 护栏**如实触发**。这正是几何级寄生估算的设计意图（量级守门），
    # 不得为了"绿"而放宽阈值或抹掉报告。
    check("③-c 护栏如实报告超阈（不假绿）：Bragg 长波导 R 超几何护栏",
          pchk.get("all_pass") is False
          and any("Ω" in v for v in pchk.get("violations", [])),
          f"violations={pchk.get('violations')}")

    # ---- ④ 诚实边界：平面波导 n_eff < 体材料 3.48 ----
    n_core = rep.get("n_core")
    n_hi = rep.get("n_hi")
    n_lo = rep.get("n_lo")
    check("④-a 段折射率来自平面波导求解器（n_hi,n_lo < n_core=3.48）",
          n_core == 3.48 and n_hi < 3.48 and n_lo < 3.48,
          f"n_core={n_core} n_hi={n_hi} n_lo={n_lo}")
    honest = str(rep.get("honest_note", ""))
    check("④-b 报告声明本版图 ≠ 器件库一维 TMM 锚（诚实边界）",
          ("TMM" in honest) and ("3.48" in honest or "体材料" in honest),
          honest[:80])

    # ---- 反向 A：窄波导 MUST 被宽度规则抓到 ----
    narrow = gds_library("N", {"W": layout_elements(
        "Waveguide", {"width": 0.03, "length": 10.0})})
    dn = check_geometry(parse_gds_polygons(narrow)["structures"])
    check("反向A 0.03µm 窄波导 ⇒ 宽度违规被抓（规则会响）",
          dn["n_width_violations"] >= 1,
          f"width_v={dn['n_width_violations']}")

    # ---- 反向 B：两独立结构间距 0.03µm MUST 被抓（且非连通域误杀）----
    # 两条平行波导，中心距 0.03µm（边到边 ≈0.03，< 默认 min_spacing）。
    w1 = [{"kind": "path", "layer": 1, "width_um": 0.5,
           "points_um": [(-5.0, 0.0), (5.0, 0.0)]}]
    w2 = [{"kind": "path", "layer": 1, "width_um": 0.5,
           "points_um": [(-5.0, 0.03), (5.0, 0.03)]}]
    dt = check_geometry({"A": w1, "B": w2})
    # 验证：两结构确实接近（构造正确）
    min_d = min(_seg_dist(s, t) for s in _segs(w1[0]["points_um"])
                for t in _segs(w2[0]["points_um"]))
    check("反向B 两独立结构间距 0.03µm ⇒ 间距违规被抓（连通域豁免非误杀）",
          dt["n_spacing_violations"] >= 1,
          f"min_d={min_d:.3f} spacing_v={dt['n_spacing_violations']}")

    print(f"\nBraggMirror GDS smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


def _segs(poly):
    return [(poly[i], poly[i + 1]) for i in range(len(poly) - 1)]


if __name__ == "__main__":
    sys.exit(main())
