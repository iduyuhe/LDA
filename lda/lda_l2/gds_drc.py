"""LDA L2 · GDS 几何 DRC 快查（v0.8.30 · 主权零依赖）。

作用：对**任意来源 GDSII（含外部 gdsfactory/第三方工具导出）**做 LDA 侧
几何可制造性快查——最小线宽 / 最小间距 / 最小面积。这是 **GDS 输入路径**
（gdsfactory 兼容桥 `lda check --gds`）的诚实底线：LDA 主权 DRC 只覆盖
几何规则**子集**（不替代 foundry 官方 DRC deck），未知层/复杂规则显式标
"未覆盖"而非静默放过。

主权纪律（与 lda_l2.drc 同源）：
  - 零依赖（仅标准库 + lda_l2.gds_export.parse_gds_polygons）；
  - 仅几何维度死标量判决，无工艺魔法数硬编码；
  - 诚实边界：几何子集 ≠ foundry 全量 DRC，发动期真实 PDK deck 才完整。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# 默认几何规则（µm）：最小线宽 / 最小间距 / 最小面积（保守 SOI 量级默认值）
DEFAULT_GEOM_RULES = {
    "min_width_um": 0.12,
    "min_spacing_um": 0.12,
    "min_area_um2": 0.04,
}


def _bbox(poly: List[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _pt_seg_dist(p, s0, s1) -> float:
    """点到线段最短距离（几何内核原语，供线宽/间距共用）。"""
    dx, dy = s1[0] - s0[0], s1[1] - s0[1]
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return ((p[0] - s0[0]) ** 2 + (p[1] - s0[1]) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((p[0] - s0[0]) * dx + (p[1] - s0[1]) * dy) / L2))
    qx, qy = s0[0] + t * dx, s0[1] + t * dy
    return ((p[0] - qx) ** 2 + (p[1] - qy) ** 2) ** 0.5


# 同层「相接」判定阈值（µm）。1 pm 远小于 GDS DBU 网格 1 nm：任何真实
# 制造的间隙（≥nm 量级）都不会被误判成相接；只有真正共享边界 / 重合的
# 元素才会落到接触份 => 见 v0.9.61 说明。
_CONNECTED_TOUCH_EPS = 1e-6


def _is_concave(poly: List[Tuple[float, float]]) -> bool:
    """多边形凹凸性**精确**判定（叉积符号一致性，容共线零值）。

    ⚠️ v0.9.61 修正：旧判定用 `len(凸包) < len(顶点)`，而 GDS BOUNDARY 普遍
    把首点再写一遍闭合（解析到此重复点），且楔形直线的中间共线点也会被凸包
    丢    掉 ⇒ **每个矩形都被误判为凹多边形**，`width_note` 一律声称「该值为上界、
    可能高估」，把凸多边形的**精确**结果降级成含糊表述。改用叉积符号：去掉
    闭合重复点后，若叉积全 ≥0（逆时针）或全 ≤0（顺时针）⇒ 凸；否则凹。
    """
    pts = list(poly)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    n = len(pts)
    if n < 4:                       # 3 点及以下必凸（退化线段也按凸处理）
        return False
    mn = mx = 0.0
    for i in range(n):
        o, a, b = pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c = (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
        mn, mx = min(mn, c), max(mx, c)
    return mn < 0.0 and mx > 0.0


# 最小宽度度量的复杂度保护：O(h·n)，超过此点数先均匀抽稀。
_MAX_POLY_PTS_FOR_WIDTH = 600


def _convex_hull(poly: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Andrew monotone chain 凸包（逆时针，去掉共线中间点）。"""
    pts = sorted(set(poly))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _poly_width(poly: List[Tuple[float, float]]) -> float:
    """多边形最小宽度 = 最小平行带宽度（凸包上取到，标准定义）。

    ⚠️ v0.9.60 修正（DRC 全链路盘点实测抓出）：
    旧实现取「相邻顶点最小距离」，把**多边形细分步长**当成了线宽——
    SymmetricYBranch 的 boundary 沿 x 以 0.039µm 步长离散（67 点），旧度量报
    「最小边 0.039µm < 0.12µm」而实际波导宽 0.5µm ⇒ **几何 DRC 假红**。
    新度量 = 凸包的最小平行带宽度（对凸多边形必在某条边处取到）：
      · 细线矩形（5×0.04）→ 0.040µm，真违规照抓；
      · 锥形/梯形波导（0.5µm 宽）→ ≈0.65µm，细分步长不再参与 ⇒ 假红消除。
    🔴 诚实边界：凹多边形（如带 V 形缺口的分叉结构）的凸包会填平凹口，
    本度量给出的是**上界**，可能高估局部最小宽度 ⇒ 调用方须看
    `width_note`（凹形时标注「按凸包近似，可能高估」），不假称精确覆盖。
    """
    n = len(poly)
    if n < 2:
        return 0.0
    if n < 3:
        x0, y0, x1, y1 = _bbox(poly)
        return min(x1 - x0, y1 - y0)
    if n > _MAX_POLY_PTS_FOR_WIDTH:
        step = int(n / _MAX_POLY_PTS_FOR_WIDTH) + 1
        poly = poly[::step]
        n = len(poly)
    hull = _convex_hull(poly)
    h = len(hull)
    if h < 3:
        x0, y0, x1, y1 = _bbox(hull)
        return min(x1 - x0, y1 - y0)
    best = float("inf")
    for i in range(h):
        a, b = hull[i], hull[(i + 1) % h]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = (dx * dx + dy * dy) ** 0.5
        if L == 0:
            continue
        # 所有顶点到该边所在直线的距离最大值 = 该方向平行带宽度
        far = max(abs((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / L for p in hull)
        if far < best:
            best = far
    return best if best != float("inf") else 0.0


def _segments(poly: List[Tuple[float, float]]) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    segs = []
    for i in range(1, len(poly)):
        segs.append((poly[i - 1], poly[i]))
    return segs


def _seg_distance(a: Tuple[Tuple[float, float], Tuple[float, float]],
                  b: Tuple[Tuple[float, float], Tuple[float, float]]) -> float:
    """两线段最短距离（用于最小间距近似）。

    v0.8.42 实测结论：细粒度几何内核（4 元素 tuple 短调用）numba njit
    反而更慢（反射/装箱开销 > 编译收益，热路径 1.69s vs 纯 Python 0.44s）
    → **锁定纯 Python 为最优路径**，不做 numba 化（不引入无效依赖）。
    批量级热点（CongestionMap 标记 / 大数组）才值得 numba，见 router。
    """
    cand = [_pt_seg_dist(a[0], b[0], b[1]), _pt_seg_dist(a[1], b[0], b[1]),
            _pt_seg_dist(b[0], a[0], a[1]), _pt_seg_dist(b[1], a[0], a[1])]
    if a[0] != a[1] and b[0] != b[1]:
        # 简单交叉检测（近似）
        return min(cand)
    return min(cand)


def check_geometry(structures: Dict[str, List[Dict]],
                   rules: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """对 GDS 结构字典（parse_gds_polygons 输出）做几何 DRC 快查。

    返回 {all_pass, min_width_ok, min_spacing_ok, min_area_ok,
          violations[], n_*_violations, n_elements, n_polys, spacing_note,
          rules}。三个 *_ok 标志与 violations 分类累积同源（不会自相矛盾）。
    诚实标注 "未覆盖" 项。
    """
    r = dict(DEFAULT_GEOM_RULES)
    if rules:
        r.update(rules)
    violations: List[str] = []
    # v0.9.60：违规**分类累积**（非事后字符串反解）。旧实现用
    # `v.startswith(("PATH 线宽","多边形最小边"))` 判定 min_width_ok，而实际字符串
    # 以「结构名: 」开头 ⇒ 恒不匹配 ⇒ min_width_ok **恒 True**；min_spacing_ok
    # 更把正则 ".*↔" 当字面量传给 startswith ⇒ 同样恒 True。两个标志位是死的
    # （实测：构造 2 条线宽违规 + 1 条间距违规，两标志仍报 True —— 假绿）。
    # 无人消费只是运气；改为分类累积后标志与 violations 必然自洽。
    w_viol: List[str] = []
    sp_viol: List[str] = []
    a_viol: List[str] = []
    min_w = float(r["min_width_um"])
    min_sp = float(r["min_spacing_um"])
    min_a = float(r["min_area_um2"])

    all_polys: List[Tuple[str, Dict]] = []
    n_elements = 0
    n_concave = 0
    for sname, elems in structures.items():
        for e in elems:
            n_elements += 1
            pts = e.get("points_um") or []
            if e.get("kind") == "path" and (e.get("width") or 0) > 0:
                # PATH：用其 WIDTH 判线宽（更可靠）
                w = e["width"]
                if w < min_w:
                    msg = f"{sname}: PATH 线宽 {w:.3f}µm < {min_w}µm"
                    violations.append(msg)
                    w_viol.append(msg)
                # PATH 面积近似 = 长度×宽
                segs = _segments(pts)
                length = sum(((s[0][0] - s[1][0]) ** 2 + (s[0][1] - s[1][1]) ** 2) ** 0.5
                             for s in segs)
                if length * w < min_a:
                    msg = f"{sname}: PATH 面积 ≈ {length * w:.3f}µm² < {min_a}µm²"
                    violations.append(msg)
                    a_viol.append(msg)
            elif len(pts) >= 2:
                all_polys.append((sname, e))
                if e.get("kind") == "boundary":
                    w = _poly_width(pts)
                    if _is_concave(pts):
                        n_concave += 1      # 凹形 → 凸包近似，宽度是上界
                    if w < min_w:
                        msg = f"{sname}: 多边形最小局部宽度 {w:.3f}µm < {min_w}µm"
                        violations.append(msg)
                        w_viol.append(msg)
                    x0, y0, x1, y1 = _bbox(pts)
                    area = (x1 - x0) * (y1 - y0)
                    if area < min_a:
                        msg = f"{sname}: 面积 {area:.3f}µm² < {min_a}µm²"
                        violations.append(msg)
                        a_viol.append(msg)

    # 最小间距（仅相邻 bbox 重叠者计算，近似）
    # v0.8.41：O(n²) 双重循环 → 均匀网格候选（bbox 重叠 ⟺ 至少共享一格，
    # 精确等价——与 lvs._collect_cross_shorts 同法（线段网格超集，零语义变化）；
    # 仅候选对走精确段距）。
    spacing_checked = 0          # 跨域（不同连通域）对数
    spacing_intra = 0            # 域内对数（按同层并集语义豁免）
    n_components = len(all_polys)
    spacing_min = None
    if len(all_polys) > 1:
        # 网格分桶：cell = 总跨度 / sqrt(n)，每格期望 O(1) 元素
        bboxes = {i: _bbox(all_polys[i][1]["points_um"]) for i in range(len(all_polys))}
        all_x0 = min(b[0] for b in bboxes.values())
        all_y0 = min(b[1] for b in bboxes.values())
        all_x1 = max(b[2] for b in bboxes.values())
        all_y1 = max(b[3] for b in bboxes.values())
        span = max(all_x1 - all_x0, all_y1 - all_y0, 1e-9)
        cell = max(span / max(len(all_polys) ** 0.5, 1.0), 1e-6)
        # v0.9.60 修正：旧剪枝要求「bbox 重叠」才查间距，而**间距违规恰好发生在
        # 不重叠但过近**的元素之间（bbox 一重叠通常已是短路/相交）⇒ 真违规被
        # 成片剪掉（实测：两块间距 0.03µm 的图形 n_spacing=0，漏检）。改为
        # bbox **外扩 min_spacing** 后相交才保留——数学上保证「距离 < min_sp」
        # 的对无一漏检，同时仍剪掉远距对（保留 O(n) 网格加速）。
        pad = min_sp
        ebboxes = {i: (b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad)
                   for i, b in bboxes.items()}
        grid: Dict[Tuple[int, int], List[int]] = {}
        for i, (x0, y0, x1, y1) in ebboxes.items():
            for cx in range(int(x0 // cell), int(x1 // cell) + 1):
                for cy in range(int(y0 // cell), int(y1 // cell) + 1):
                    grid.setdefault((cx, cy), []).append(i)
        cand: set = set()
        for occupants in grid.values():
            m = len(occupants)
            for a in range(m):
                for b in range(a + 1, m):
                    i, j = occupants[a], occupants[b]
                    cand.add((i, j) if i < j else (j, i))
        # 精确化：外扩 bbox 相交者才走精确段距
        cand = {(i, j) for i, j in cand
                if not (ebboxes[i][2] < ebboxes[j][0] or ebboxes[j][2] < ebboxes[i][0]
                        or ebboxes[i][3] < ebboxes[j][1] or ebboxes[j][3] < ebboxes[i][1])}
        # 精确段距 + **同层连通域合并**（v0.9.61）
        # ------------------------------------------------------------------
        # 🔴 真缺陷（布拉格光栅导出后实测暴露）：一条连续光栅被拆成 2N 个首尾
        # 相接的矩形 ⊆ 同一层同一个铜/硅图形。真实 DRC 会先做**同层并集**
        # （AND/OR 布尔运算），最小间距规则只对**合并后的独立图形**生效；
        # 相接元素本身就是一个形状，不存在"间距"。旧实现对所有 pair 逐对判
        # 距 ⇒ 13 处「间距 0.000µm」假红，任何连续（光栅/锥形骨架/总线）都
        # 会被判违规 ⇒ 几何 DRC 在这些布局上完全不可用。
        # 解法：先按「距离 ≤ _CONNECTED_TOUCH_EPS」做并查集，域内 pair 豁免
        # 间距规则；跨域 pair 照旧严格判定。
        # 🔴 诚实边界：域内豁免意味着**同一图形的凹槽/内缝**不再被最小间距
        # 覆盖（那需 minimum-slot / min-notch 类规则，本 checker 未实现）⇒
        # spacing_note 必须显式写出豁免对数，不静默放过。
        parent = list(range(len(all_polys)))

        def _find(a: int) -> int:
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        def _union(a: int, b: int) -> None:
            ra, rb = _find(a), _find(b)
            if ra != rb:
                parent[rb] = ra

        dists: Dict[Tuple[int, int], float] = {}
        for i, j in cand:
            dists[(i, j)] = min(
                _seg_distance(s, t)
                for s in _segments(all_polys[i][1]["points_um"])
                for t in _segments(all_polys[j][1]["points_um"])
            )
        for (i, j), d in dists.items():
            if d <= _CONNECTED_TOUCH_EPS:
                _union(i, j)
        for i, j in sorted(dists):
            d = dists[(i, j)]
            if _find(i) == _find(j):
                spacing_intra += 1
                continue
            spacing_checked += 1
            spacing_min = d if spacing_min is None else min(spacing_min, d)
            if d < min_sp:
                msg = (f"{all_polys[i][0]}↔{all_polys[j][0]}: "
                       f"间距 {d:.3f}µm < {min_sp}µm")
                violations.append(msg)
                sp_viol.append(msg)
        n_components = len({_find(i) for i in range(len(all_polys))})
    if spacing_checked == 0 and spacing_intra == 0:
        # 单结构或无重叠：间距规则无法严格判定 → 诚实标 "未覆盖"
        spacing_note = "未覆盖（无相邻元素，间距规则需多元素叠加）"
    else:
        if spacing_checked:
            base = (f"已查 {spacing_checked} 对跨域元素"
                    f"（{n_components} 个同层连通域），"
                    f"最小间距 {spacing_min:.3f}µm")
        else:
            base = f"无跨域相邻元素（{n_components} 个同层连通域）"
        if spacing_intra:
            base += ("；域内 " + str(spacing_intra) + " 对首尾相接的元素按**同层"
                     "并集语义**视为同一图形而豁免（真实 DRC 先合并同层多边形，"
                     "最小间距只对独立图形生效）；未覆盖 min-slot/凹槽类规则")
        spacing_note = base

    return {
        "all_pass": len(violations) == 0,
        "min_width_ok": len(w_viol) == 0,
        "min_spacing_ok": len(sp_viol) == 0,
        "min_area_ok": len(a_viol) == 0,
        "n_width_violations": len(w_viol),
        "n_spacing_violations": len(sp_viol),
        "n_area_violations": len(a_viol),
        "violations": violations,
        "n_elements": n_elements,
        "n_polys": len(all_polys),
        "spacing_note": spacing_note,
        "width_note": (
            "最小宽度 = 凸包最小平行带宽度；本版图无 BOUNDARY 多边形，"
            "宽度检查仅覆盖 PATH 声明线宽（未覆盖多边形局部宽度）"
            if not all_polys else
            "最小宽度 = 凸包最小平行带宽度"
            + f"（{len(all_polys)} 个 BOUNDARY 多边形参与）"
            + (f"；其中 {n_concave} 个为凹多边形，凸包会填平凹口 ⇒ 该值为上界、"
               f"可能高估局部最小宽度（不假称精确覆盖）" if n_concave else
               "；全部为凸多边形 ⇒ 该值为精确最小宽度")
        ),
        "n_concave_polys": n_concave,
        "rules": r,
    }


def geometry_drc_markdown(report: Dict[str, Any]) -> str:
    L = []
    L.append("### GDS 几何 DRC 快查（主权子集 · 非 foundry 全量）")
    L.append("")
    if report["all_pass"]:
        L.append(f"- ✅ 几何可制造性子集通过（{report['n_elements']} 元素，{report['n_polys']} 多边形）")
    else:
        L.append(f"- ❌ 几何违规 {len(report['violations'])} 项（{report['n_elements']} 元素）")
    L.append(f"- 规则：最小线宽 {report['rules']['min_width_um']}µm · "
             f"最小间距 {report['rules']['min_spacing_um']}µm · "
             f"最小面积 {report['rules']['min_area_um2']}µm²")
    L.append(f"- 间距判定：{report['spacing_note']}")
    if report.get("width_note"):
        L.append(f"- 宽度判定：{report['width_note']}")
    for v in report["violations"][:12]:
        L.append(f"  - ❌ {v}")
    L.append("")
    L.append("*诚实边界：本快查仅覆盖几何维度**子集**，不替代晶圆厂官方 DRC "
             "deck；发动期真实 PDK 接入后几何规则与完整 DRC 由 foundry deck 提供。*")
    return "\n".join(L)
