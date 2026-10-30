#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E41 门禁：**B2 完整 detail route** —— 真实单元引脚 + 轨道容量律 + DRC 零违规。

## 本门禁守什么
E37 的 `track_route` 已做「H 段区间着色分轨」，但有两处结构性简化：
① 引脚取**单元几何中心**（真实引脚在左边界/内部 strap 上）；② 容量**无上界**
（有几段分几条轨 ⇒ "布不通"在抽象里不可能发生，而 E38f/E38g 整条负结果正是从这里来的）。

B2 把这两点补上，并给出 E37 式基线的**对照**：

| # | 守护 | 金标 |
|---|---|---|
| B1 | 引脚来自真实单元 | A/B 引脚 x == 单元左边界；Y 引脚 x == strap 中心；**且 ≠ 几何中心** |
| B2 | 轨道容量律（与 A2 协同） | 所需轨道数 == `dmtrack.channel_density` == 左边界算法轨道数（最优） |
| B3 | 容量是硬的 | T ≥ d ⇒ 100% 布通；T = d-1 ⇒ 布通率 < 100%（不是"多画几条") |
| B4 | 真实 DRC | 本路由**零违规**（M3/M4 线宽间距 + VIA2 包围，`ddrc_lvs` 同一套口径） |
| B5 | 对照证明 | E37 式「中心点 + 同 y 集中」基线在同一网表下**必然违规**（> 0） |
| B6 | 连通性 | 每个网按层感知（M3/M4 仅经 VIA2 连）只有 **1 个**连通分量 |
| B7 | 判别力 | 把一条网硬塞到已占轨道 ⇒ DRC 必红（防「DRC 恒绿」） |
| B8 | 确定性 | 两次构建/路由/DRC ⇒ 逐字节一致 |
| B0 | 耗时 | < 阈值（纯几何，亚秒级） |

## 诚实口径
- 两层通道模型（M3 横 / M4 竖 / VIA2），**不是通用迷宫路由器**，不做 rip-up、不优化线长。
- 单元内 M1→M3 的 via 串沿用 E37 `real_cell_geom` 约定（失效面见 E33）；本模块只负责 M3/M4 段。
- 演示用例 4+4 单元；**不宣称**真实设计的布通率/面积/能效。
- **净增 0 锚**（几何与容量结论为整数/闭式）⇒ 门禁形态（同 E39/E40）。
"""

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import dcroute as RT      # noqa: E402
from lda_l2.ecore import ddrc_lvs as DL     # noqa: E402
from lda_l2.ecore import ddetail as DD      # noqa: E402
from lda_harness.smoke_kit import make_check  # noqa: E402

AN_ELAPSED_MAX_S = 60.0

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


def _drc(shapes):
    return DL.run_drc(shapes)


def main():
    t0 = time.time()
    print("=" * 78)
    print("E41 · B2 完整 detail route（真实引脚 + 轨道容量律 + DRC 零违规）")
    print("=" * 78)

    case = RT.build_case()
    r = RT.route(case)
    drc = _drc(r["shapes"])
    base = RT.route_center_baseline(case)
    drc_b = _drc(base["shapes"])
    print("  [info] T=%d · d=%d · 布通 %d/%d · 形状 %d · DRC %d · 基线 DRC %d"
          % (r["t_avail"], r["d"], len(r["routed"]), len(case["nets"]),
             len(r["shapes"]), len(drc["violations"]), len(drc_b["violations"])))

    # ── B1 引脚来自真实单元（不是几何中心）────────────────────────────
    bad_pin = []
    for p in case["layout"]["cells"]:
        c = p.cell
        for net in ("A", "Y"):
            if net not in c.pins:
                continue
            rp = c.pins[net]
            px, py = RT.pin_point(p, net)
            cx, cy = RT.center_point(p, net)
            if net in ("A", "B"):
                want_x = p.x0 + rp.x0 / 1000.0
            else:
                want_x = p.x0 + (rp.x0 + rp.x1) / 2000.0
            if abs(px - want_x) > 1e-9:
                bad_pin.append((p.name, net, px, want_x))
            if abs(px - cx) < 1e-9 and abs(py - cy) < 1e-9:
                bad_pin.append((p.name, net, "等于中心"))
    check("B1 引脚取自真实单元：A/B 在左边界 · Y 在 strap 中心 · 且不等于几何中心",
          not bad_pin, bad_pin[:4] or "all real")

    # ── B2 容量律（A2 协同）──────────────────────────────────────────
    dn = RT.MT.channel_density([
        (int(round(min(n["a"][0], n["b"][0]) * 1000)),
         int(round(max(n["a"][0], n["b"][0]) * 1000))) for n in case["nets"]])
    need, assign = RT.MT.left_edge_tracks([
        (int(round(min(n["a"][0], n["b"][0]) * 1000)),
         int(round(max(n["a"][0], n["b"][0]) * 1000)), n["name"]) for n in case["nets"]])
    check("B2 轨道容量律：所需轨道数 == 通道密度 d == 左边界算法轨道数（最优）",
          r["d"] == dn == need == r["need"],
          "d=%s dn=%s need=%s 门禁=%s" % (r["d"], dn, need, r["need"]))

    # ── B3 容量是硬的（T ≥ d 布通 100%；T = d-1 布通率 < 100%）────────
    full = RT.route(case, t_avail=r["d"])
    short = RT.route(case, t_avail=max(0, r["d"] - 1))
    total = len(case["nets"])
    check("B3 容量是硬的：T≥d ⇒ 布通 100% ∧ T=d-1 ⇒ 布通率 <100%（不是多画几条）",
          len(full["routed"]) == total and len(short["routed"]) < total,
          "T=d:%d/%d · T=d-1:%d/%d unrouted=%s"
          % (len(full["routed"]), total, len(short["routed"]), total, short["unrouted"]))

    # ── B4 真实 DRC 零违规 ──────────────────────────────────────────
    check("B4 真实 DRC：M3/M4 线宽间距 + VIA2 包围 零违规",
          not drc["violations"], drc["violations"][:4] or "0 violations")

    # ── B5 对照：中心点基线必然违规 ─────────────────────────────────
    check("B5 对照证明：E37 式「中心点 + 同 y 集中」基线在同一网表下必违规（>0）",
          len(drc_b["violations"]) > 0,
          "baseline violations=%d" % len(drc_b["violations"]))

    # ── B6 连通性：每网 1 个分量（层感知）────────────────────────────
    comp = RT.net_components(r["shapes"])
    check("B6 连通性：每网层感知连通分量 == 1（M3/M4 仅经 VIA2 相连）",
          all(v == 1 for v in comp.values()) and len(comp) == len(case["nets"]),
          comp)

    # ── B7 判别力：硬塞同轨 ⇒ DRC 必红 ─────────────────────────────
    shapes_mut = [DD.Shape(s.layer, s.x0, s.y0, s.x1, s.y1, s.net, s.kind)
                  for s in r["shapes"]]
    # 把 n1 的 M3 主段平移到 n0 所在轨道（两条不同网的 H 段同层同 y）
    m3_n0 = [s for s in shapes_mut if s.net == "n0" and s.layer == DD.L_M3]
    if m3_n0:
        y_mid = (m3_n0[0].y0 + m3_n0[0].y1) / 2.0
        for s in shapes_mut:
            if s.net == "n1" and s.layer == DD.L_M3 and (s.x1 - s.x0) > 5 * RT.W:
                dy = y_mid - (s.y0 + s.y1) / 2.0
                s.y0 += dy
                s.y1 += dy
    drc_mut = _drc(shapes_mut)
    check("B7 判别力：把一条网硬塞到已占轨道 ⇒ DRC 必红（防 DRC 恒绿）",
          len(drc_mut["violations"]) > 0, "mut violations=%d" % len(drc_mut["violations"]))

    # ── B8 确定性 ─────────────────────────────────────────────────
    def sig():
        c2 = RT.build_case()
        r2 = RT.route(c2)
        return (tuple((n["name"], n["a"], n["b"]) for n in c2["nets"]),
                tuple((s.layer, round(s.x0, 9), round(s.y0, 9),
                       round(s.x1, 9), round(s.y1, 9), s.net) for s in r2["shapes"]),
                len(_drc(r2["shapes"])["violations"]))
    check("B8 确定性：两次构建/路由/DRC ⇒ 逐字节一致", sig() == sig())

    dt = time.time() - t0
    check("B0 门禁耗时 %.2f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, dt)

    print("-" * 78)
    print("E41 · 通过 %d · 失败 %d · 耗时 %.2f s" % (PASS, FAIL, dt))
    if FAIL:
        print("FAIL — E41 detail route（真实引脚/容量/DRC）出现问题，按上方 [FAIL] 项修复")
        return 1
    print("E41 全绿 · 真实引脚路由：轨道数==d（A2 容量律）· T≥d 才布通 · DRC 零违规 · "
          "对照基线必违规 · 净增 0 锚")
    return 0


if __name__ == "__main__":
    sys.exit(main())
