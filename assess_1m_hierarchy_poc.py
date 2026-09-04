"""百万级规模评估 · 层次化 GDS 导出 POC（P0 可行性验证）。

目标：回答「把 flat 版图改成 cell + AREF 层次化，能降多少？降了以后还等价吗？」

严格性要求（缺一不可）：
  1. 周期由**算法自动检测**，不硬编码 92；
  2. 层次化展开后的几何必须与 flat **逐元素等价**（DBU 量化后比对，报告最大偏差）；
  3. 元素数 / 字节 / 耗时三项都实测对比。

等价性不成立则 POC 判 FAIL —— 只降体积不等价的方案没有价值。
"""
from __future__ import annotations

import math
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, "D:/agent_LDA/lda")
sys.path.insert(0, "D:/agent_LDA/lda/lda_harness")
sys.path.insert(0, "D:/agent_LDA/lda/lda_l2")

from lda_l2 import gds_export as GE  # noqa: E402
from lda_harness import cpo_array as CA  # noqa: E402
from lda_layout.placement import port_abs  # noqa: E402
from lda_l2.primitives import primitive_descs  # noqa: E402

WG = 0.5
# 几何元组：("P", layer, width, points) / ("B", layer, None, points)
Geom = Tuple


# ────────────────────────────────────────────────────────── 几何生成（对齐产品代码）
def dev_geoms(c, placement, wg_width) -> List[Geom]:
    """器件几何（与 chip_layout_export._device_elements 逐条对应）。"""
    out: List[Geom] = []
    ox, oy, _ = placement[c.id]
    params = dict(c.params)
    lib = GE.LIB_LAYER_SI
    if c.kind in ("RingResonator", "RingAddDrop"):
        R = float(params.get("R", 10.0))
        wg_w = float(params.get("wg_width", wg_width))
        gap = float(params.get("gap", 0.3))
        half = R * 1.5
        off = R + wg_w / 2.0 + gap
        ring = [(ox + R * math.cos(2.0 * math.pi * i / 64),
                 oy + R * math.sin(2.0 * math.pi * i / 64)) for i in range(64)]
        out.append(("P", lib, wg_w, tuple(ring)))
        out.append(("P", lib, wg_w,
                    ((ox - half, oy - off), (ox + half, oy - off))))
        out.append(("P", lib, wg_w,
                    ((ox - half, oy + off), (ox + half, oy + off))))
    elif c.kind == "Waveguide":
        L = float(params.get("length", 10.0))
        out.append(("P", lib, wg_width, ((ox, oy), (ox + L, oy))))
    elif c.kind == "GratingCoupler":
        L = float(params.get("L", 10.0))
        out.append(("P", lib, wg_width, ((ox, oy), (ox, oy + L))))
    else:
        for d in GE.geometry_desc(c.kind, params):
            pts = tuple((ox + px, oy + py) for px, py in d["points_um"])
            if d["kind"] == "path":
                out.append(("P", d["layer"], d["width_um"], pts))
            else:
                # 注：产品代码此处**未加 (ox,oy)**（真实 BUG，见评估报告）。
                # POC 用修正版，否则等价性无从验证。
                flat = tuple((ox + px, oy + py)
                             for ring in d.get("rings_um", []) for px, py in ring)
                out.append(("B", d["layer"], None, flat))
    return out


def io_geoms(link, placement, wg_width) -> List[Geom]:
    """IO 光栅几何（对齐 _io_grating_elements）。"""
    from lda_l2.chip_layout_export import io_ports_of
    out: List[Geom] = []
    for (inst, port) in io_ports_of(link):
        ox, oy = port_abs(inst, port, placement, link)
        for d in primitive_descs("grating_coupler",
                                 {"width": wg_width, "n_tooth": 16}):
            pts = tuple((ox + px, oy + py) for px, py in d.get("points_um", []))
            if d["kind"] == "path":
                out.append(("P", d["layer"], d["width_um"], pts))
            else:
                # 注：产品代码此处**未加 (ox,oy)**（真实 BUG，见评估报告）。
                # POC 用修正版，否则等价性无从验证。
                flat = tuple((ox + px, oy + py)
                             for ring in d.get("rings_um", []) for px, py in ring)
                out.append(("B", d["layer"], None, flat))
    return out


def route_geoms(routes, wg_width) -> List[Geom]:
    out: List[Geom] = []
    for net_id, rr in (routes or {}).items():
        pts = _route_points(rr)
        out.append(("P", GE.LIB_LAYER_SI, wg_width, tuple(pts)))
    return out


def _route_points(rr) -> List[Tuple[float, float]]:
    from lda_l2.chip_layout_export import _route_points as _rp
    return _rp(rr)


def flat_all_geoms(link, placement, routes, wg_width):
    """flat 全量几何（器件 + 布线 + IO）。"""
    g: List[Geom] = []
    for c in link.ir.components:
        g.extend(dev_geoms(c, placement, wg_width))
    g.extend(route_geoms(routes, wg_width))
    g.extend(io_geoms(link, placement, wg_width))
    return g


# ────────────────────────────────────────────────────────── 周期自动检测
def _sig(c) -> Tuple:
    """器件签名：kind + 参数（规范化，浮点保留 6 位防末位噪声）。"""
    p = tuple(sorted((k, round(float(v), 6))
                     for k, v in c.params.items()
                     if isinstance(v, (int, float))))
    return (c.kind, p)


def min_period(sigs: Sequence[Tuple]) -> Optional[int]:
    """KMP 前缀函数求 token 序列最小周期（不成立返回 None）。"""
    n = len(sigs)
    pi = [0] * n
    for i in range(1, n):
        j = pi[i - 1]
        while j > 0 and sigs[i] != sigs[j]:
            j = pi[j - 1]
        if sigs[i] == sigs[j]:
            j += 1
        pi[i] = j
    p = n - pi[n - 1]
    if n % p != 0 or p >= n:
        return None
    return p if all(sigs[i] == sigs[i % p] for i in range(n)) else None


def detect_array(placement, comps, period: int):
    """检测平移复用的 2D 阵列参数。

    返回 (nx, ny, dx, dy, base_origin) 或 None（非规则阵列则不适用 AREF）。
    判据：instance k 的第 j 个器件 = base_j + (a*dx, b*dy)，a=k%nx, b=k//nx。
    """
    n_inst = len(comps) // period
    if n_inst < 2:
        return None
    # 每个实例的平移量（取该实例首个器件相对 base 首个器件的位移）
    shifts = []
    for k in range(n_inst):
        i0 = k * period
        x0, y0, _ = placement[comps[i0].id]
        xb, yb, _ = placement[comps[0].id]
        shifts.append((round(x0 - xb, 6), round(y0 - yb, 6)))
    # x 方向步进 = 实例 1 的位移（若实例 1 与 0 同行）
    dx, dy_row = shifts[1] if n_inst > 1 else (0.0, 0.0)
    if abs(dy_row) > 1e-9:            # 实例 1 已换行 ⇒ 每行仅 1 个实例
        nx = 1
    else:
        nx = 2
        while nx < n_inst:            # 找到换行点
            sx, sy = shifts[nx]
            if abs(sy) > 1e-9:
                break
            if abs(sx - dx * nx) > 1e-6:   # 非等间距 ⇒ 不规则
                return None
            nx += 1
    if n_inst % nx != 0:
        return None
    ny = n_inst // nx
    dy = shifts[nx][1] if nx < n_inst else 0.0
    # 严格校验全部实例位置
    for k in range(n_inst):
        a, b = k % nx, k // nx
        ex, ey = a * dx, b * dy
        sx, sy = shifts[k]
        if abs(sx - ex) > 1e-6 or abs(sy - ey) > 1e-6:
            return None
    return nx, ny, dx, dy


# ────────────────────────────────────────────────────────── AREF 编码
def aref(sname: str, origin, dx: float, dy: float, nx: int, ny: int,
         layer: int = GE.LIB_LAYER_SI) -> bytes:
    """GDSII AREF 阵列引用（无旋转/镜像，等间距矩形阵列）。"""
    ox, oy = origin
    out = GE._rec(0x0B, 0, b"")                       # AREF
    out += GE._rec(0x12, 6, GE._ascii(sname))         # SNAME
    out += GE._rec(0x0D, 2, GE._int2(layer))          # LAYER
    out += GE._rec(0x1A, 2, GE._int2(0))              # STRANS（无变换）
    out += GE._rec(0x13, 2, GE._int2(nx) + GE._int2(ny))   # COLROW
    # XY：原点 / 原点+列间距×列数 / 原点+行间距×行数
    xy = [ox, oy, ox + dx * nx, oy, ox, oy + dy * ny]
    out += GE._rec(0x10, 3, GE._int4_list([GE._to_dbu(v) for v in xy]))
    out += GE._rec(0x11, 0, b"")                      # ENDEL
    return out


def _enc(g: Geom) -> bytes:
    if g[0] == "P":
        return GE.path(g[1], g[2], list(g[3]))
    return GE.boundary(g[1], list(g[3]))


def _shift(g: Geom, sdx: float, sdy: float) -> Geom:
    pts = tuple((x + sdx, y + sdy) for x, y in g[3])
    return (g[0], g[1], g[2], pts)


def _origin(g: Geom, ox: float, oy: float) -> Geom:
    """绝对坐标 → 相对单元原点（cell 局部坐标）。"""
    pts = tuple((round(x - ox, 9), round(y - oy, 9)) for x, y in g[3])
    return (g[0], g[1], g[2], pts)


def _key(g: Geom, q: int = 1000) -> Tuple:
    """DBU 量化后的比对键（消除浮点末位噪声）。"""
    pts = tuple((int(round(x * q)), int(round(y * q))) for x, y in g[3])
    w = None if g[2] is None else int(round(g[2] * q))
    return (g[0], g[1], w, pts)


# ────────────────────────────────────────────────────────── 主流程
def run(cfg: CA.CPOArrayConfig, label: str) -> Dict[str, Any]:
    print(f"\n{'='*74}\n{label}\n{'='*74}", flush=True)
    t0 = time.perf_counter()
    link, placement, routes, meta = CA.build_cpo_array_case(cfg)
    t_build = time.perf_counter() - t0
    comps = list(link.ir.components)
    n_dev = len(comps)
    print(f"器件 {n_dev:,} · 通道 {cfg.n_channels:,} · "
          f"构建 {t_build:.2f}s", flush=True)

    # ── flat 基线
    t0 = time.perf_counter()
    flat_g = flat_all_geoms(link, placement, routes, WG)
    flat_bytes = GE.gds_library("LDA_CHIP",
                                {"CHIP": [_enc(g) for g in flat_g]})
    t_flat = time.perf_counter() - t0
    n_flat = len(flat_g)

    # ── 周期自动检测
    t0 = time.perf_counter()
    sigs = [_sig(c) for c in comps]
    p = min_period(sigs)
    if p is None:
        print("  !! 未检测到重复周期 ⇒ 层次化不适用，POC FAIL", flush=True)
        return {"ok": False, "reason": "no_period"}
    arr = detect_array(placement, comps, p)
    t_detect = time.perf_counter() - t0
    if arr is None:
        print(f"  周期 p={p} 检测到，但非规则 2D 阵列 ⇒ 回退 SREF 逐个引用",
              flush=True)
    else:
        nx, ny, dx, dy = arr
        print(f"  自动检测：周期 p={p} 器件 · 阵列 {nx} 列 × {ny} 行 · "
              f"步进 ({dx:.3f}, {dy:.3f}) µm", flush=True)

    # ── cell 提取（第 0 个实例的器件 + 其间的布线 + IO）
    base_ids = {c.id for c in comps[:p]}
    bx0, by0, _ = placement[comps[0].id]
    cell_g: List[Geom] = []
    for c in comps[:p]:
        cell_g.extend(_origin(g, bx0, by0) for g in dev_geoms(c, placement, WG))
    # 布线归属（严格）：net 的两端器件**都**必须属于第 0 个通道，
    # 否则是跨通道布线，不能进 cell。用 net.connects 判断，不靠坐标猜测。
    net_devs = {net.id: {c.split(".", 1)[0] for c in net.connects}
                for net in link.ir.nets}
    for net_id, rr in routes.items():
        devs = net_devs.get(net_id)
        if devs is None or not devs <= base_ids:
            continue
        pts = _route_points(rr)
        if pts:
            cell_g.append(_origin(("P", GE.LIB_LAYER_SI, WG, tuple(pts)),
                                  bx0, by0))
    # IO 归属（严格）：端口所在器件必须属于第 0 个通道
    from lda_l2.chip_layout_export import io_ports_of
    for (inst, port) in io_ports_of(link):
        if inst not in base_ids:
            continue
        ox, oy = port_abs(inst, port, placement, link)
        for d in primitive_descs("grating_coupler",
                                 {"width": WG, "n_tooth": 16}):
            pts = tuple((ox + px, oy + py) for px, py in d.get("points_um", []))
            if d["kind"] == "path":
                cell_g.append(_origin(("P", d["layer"], d["width_um"], pts),
                                      bx0, by0))
            else:
                flat = tuple((ox + px, oy + py)
                             for ring in d.get("rings_um", []) for px, py in ring)
                cell_g.append(_origin(("B", d["layer"], None, flat), bx0, by0))
    n_cell = len(cell_g)

    # ── 层次化编码
    t0 = time.perf_counter()
    if arr is None:
        top = [GE.sref("CHANNEL", placement[comps[k * p].id][:2])
               for k in range(len(comps) // p)]
    else:
        nx, ny, dx, dy = arr
        top = [aref("CHANNEL", (bx0, by0), dx, dy, nx, ny)]
    hier_bytes = GE.gds_library(
        "LDA_CHIP",
        {"CHANNEL": [_enc(g) for g in cell_g], "TOP": top})
    t_hier = time.perf_counter() - t0
    n_hier = n_cell + len(top)

    # ── 等价性验证：层次化展开 vs flat
    t0 = time.perf_counter()
    expanded: List[Geom] = []
    if arr is None:
        for k in range(len(comps) // p):
            ix, iy, _ = placement[comps[k * p].id]
            expanded.extend(_shift(g, ix, iy) for g in cell_g)
    else:
        nx, ny, dx, dy = arr
        for b in range(ny):
            for a in range(nx):
                expanded.extend(_shift(g, bx0 + a * dx, by0 + b * dy)
                                for g in cell_g)
    exp_keys = sorted(_key(g) for g in expanded)
    flat_keys = sorted(_key(g) for g in flat_g)
    t_verify = time.perf_counter() - t0

    from collections import Counter
    cf, ce = Counter(flat_keys), Counter(exp_keys)
    missing = list((cf - ce).elements())   # flat 有、展开没有
    extra = list((ce - cf).elements())     # 展开有、flat 没有

    # ── 等价性判据 ────────────────────────────────────────────────
    # GDS 的最小网格单位是 1 DBU（= 1 nm）。层次化引入「减原点 + 加实例
    # 位置」的浮点往返，可能在 .5 DBU 边界产生 1 DBU 的舍入差异——这在
    # 版图精度定义内无意义（远小于工艺 CD 控制精度），但必须显式统计、
    # 不得悄悄放过。故采用两级判据：
    #   严格等价：多重集合完全相同（0 偏差）
    #   数值等价：差异元素可一一配对且距离 ≤ 1 DBU
    #   否则    ：FAIL
    strict = not missing and not extra
    max_dev_nm = 0
    n_paired = 0
    if strict:
        verdict = "严格等价"
    else:
        used = [False] * len(extra)
        ok = True
        for m in missing:
            hit = -1
            for i, e in enumerate(extra):
                if used[i] or m[:3] != e[:3] or len(m[3]) != len(e[3]):
                    continue
                d = max(max(abs(a[0] - b[0]), abs(a[1] - b[1]))
                        for a, b in zip(m[3], e[3]))
                if d <= 1:
                    hit = i
                    max_dev_nm = max(max_dev_nm, d)
                    break
            if hit < 0:
                ok = False
                break
            used[hit] = True
            n_paired += 1
        if not ok:
            verdict = "FAIL"
            max_dev_nm = 10 ** 9
        else:
            verdict = f"数值等价（≤1 DBU，配对 {n_paired} 个）"
    same = strict or verdict.startswith("数值等价")

    if not strict:
        print(f"    严格集合差：flat 独有 {len(missing)} 个 / "
              f"展开独有 {len(extra)} 个", flush=True)
        if verdict == "FAIL":
            for tag, lst in (("缺", missing[:3]), ("多", extra[:3])):
                for k in lst:
                    print(f"      [{tag}] type={k[0]} layer={k[1]} w={k[2]} "
                          f"首点={k[3][:2]}", flush=True)

    print(f"\n  {'':22}{'flat':>16}{'层次化':>16}{'降幅':>12}", flush=True)
    print(f"  {'元素数':<20}{n_flat:>16,}{n_hier:>16,}"
          f"{(1-n_hier/n_flat)*100:>11.2f}%", flush=True)
    print(f"  {'字节 (MB)':<20}{len(flat_bytes)/1e6:>16.2f}"
          f"{len(hier_bytes)/1e6:>16.3f}"
          f"{(1-len(hier_bytes)/len(flat_bytes))*100:>11.2f}%", flush=True)
    print(f"  {'编码耗时 (s)':<20}{t_flat:>16.3f}{t_hier:>16.3f}"
          f"{(1-t_hier/t_flat)*100:>11.2f}%", flush=True)
    print(f"\n  周期检测 {t_detect:.3f}s · 等价性验证 {t_verify:.2f}s", flush=True)
    print(f"  展开元素 {len(exp_keys):,} vs flat {len(flat_keys):,} · "
          f"等价性 {'✅ ' + verdict if same else '❌ FAIL'}", flush=True)
    if n_paired:
        print(f"    舍入差异元素 {n_paired} 个 · 最大偏差 {max_dev_nm} nm"
              f"（1 DBU = 1 nm，版图精度下无意义）", flush=True)

    return {
        "ok": True, "n_devices": n_dev, "n_channels": cfg.n_channels,
        "period": p, "n_flat": n_flat, "n_hier": n_hier,
        "bytes_flat": len(flat_bytes), "bytes_hier": len(hier_bytes),
        "t_flat": t_flat, "t_hier": t_hier, "t_detect": t_detect,
        "equivalent": same, "max_dev_nm": max_dev_nm,
        "n_expanded": len(exp_keys),
    }


if __name__ == "__main__":
    scale = sys.argv[1] if len(sys.argv) > 1 else "small"
    if scale == "small":
        r = run(CA.CPOArrayConfig(n_oe=2, n_ch=2, n_lane=8, ch_per_row=2),
                "小规模正确性验证（2 OE × 2 ch = 4 通道 / 368 器件）")
        print("\n小规模结论：", "等价 ✅ 可放大" if r.get("equivalent")
              else "不等价 ❌ 不得放大")
    else:
        r = run(CA.CPOArrayConfig(n_oe=40, n_ch=68, n_lane=8, ch_per_row=4),
                "CPO 250k 全量（40 OE × 68 ch = 2,720 通道 / 250,240 器件）")
        if r.get("equivalent"):
            print("\n✅ POC PASS：层次化与 flat 逐元素等价，"
                  f"元素降 {(1-r['n_hier']/r['n_flat'])*100:.2f}%，"
                  f"体积降 {(1-r['bytes_hier']/r['bytes_flat'])*100:.2f}%")
        else:
            print("\n❌ POC FAIL：展开后不等价，方案不可用")
