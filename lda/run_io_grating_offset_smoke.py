"""v0.9.32 IO 光栅耦合器几何定位回归 smoke（P0-0 缺陷护栏）。

背景：2026-09-04 层次化 POC 发现 `_io_grating_elements` 的 BOUNDARY 分支
漏加端口绝对偏移——`path` 分支加了 (ox,oy)，`boundary` 分支没加，导致
光栅齿（primitive_descs('grating_coupler') 返回 1 path + 16 boundary）
全部堆在局部原点，而真正的 IO 端口处没有任何齿结构。

影响：CPO 250k 里 174,080 个齿（占元素 19.4%）全部错位；据此外协流片
IO 耦合器会全部失效。器件主体不受影响，所以此前的体积/元素数类断言
全部「看起来正常」——这正是它能长期潜伏的原因。

本 smoke 的判据全部为死标量（无阈值调参空间），且**反向可证伪**：
在缺陷修复前，A/B/C 三条判据必须 FAIL（已实测：去重位置 16 vs 应 80）。

判据：
  A 位置去重数：n_io 个端口的齿位置两两不同 ⇒ 去重位置数 == n_io × 16
    （缺陷态：所有端口齿重叠同一处 ⇒ 去重数 == 16）
  B 邻域覆盖：每个 IO 端口 20µm 邻域内齿数 ≥ 16
    （缺陷态：远端端口邻域齿数 == 0）
  C 齿总数守恒：boundary 数 == n_io × 16
  D 端口跟随：齿 bbox 中心 x 跨度 > 端口 x 跨度（齿必须铺开到端口范围外）

LLM 不进判决路径；纯标准库 + lda 内部模块。
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_agent.orchestrator import Orchestrator
from lda_layout.placement import port_abs
from lda_l2.chip_layout_export import export_chip_gds, io_ports_of
from lda_l2.gds_export import parse_gds_polygons

N_TOOTH = 16          # primitive_descs('grating_coupler', n_tooth=16)
TOOTH_REACH_UM = 12.0  # 齿相对本端口的最大合理偏移（光栅总长 10.54µm + 裕度）
CHECKS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}  ({detail})")


def _tooth_centers(elements):
    """BOUNDARY 元素 → bbox 中心列表（量化到 1nm=1DBU，消除浮点噪声）。"""
    out = []
    for e in elements:
        if e["kind"] != "boundary":
            continue
        xs = [p[0] for p in e["points_um"]]
        ys = [p[1] for p in e["points_um"]]
        out.append((round((min(xs) + max(xs)) / 2.0, 3),
                    round((min(ys) + max(ys)) / 2.0, 3)))
    return out


def _case(name: str, spec_or_ctx) -> None:
    if isinstance(spec_or_ctx, dict):
        ctx = Orchestrator().run(spec_or_ctx)
    else:                                    # 直接给 ctx（CPO 等自建链路）
        ctx = spec_or_ctx
    r = export_chip_gds(ctx.link, ctx.placement, ctx.routes)
    # 🔴 v0.9.33：层次化后结构名不再是 "CHIP"（变为 CHANNEL + TOP），
    #    且必须按 `top_structures` 取顶层——直接取某个固定结构名会 KeyError，
    #    按全部结构求和又会把 cell 自己的几何重复计入。
    pg = parse_gds_polygons(r["gds_bytes"])
    els = []
    for _n in pg["top_structures"]:
        els.extend(pg["structures"][_n])
    teeth = _tooth_centers(els)
    ports = [port_abs(i, p, ctx.placement, ctx.link)
             for i, p in io_ports_of(ctx.link)]
    n_io = len(ports)
    expect = n_io * N_TOOTH

    print(f"\n--- {name}：IO 端口 {n_io} · 齿 {len(teeth)}（应 {expect}） ---")

    # C 齿总数守恒
    check(f"{name} C 齿总数 == n_io×{N_TOOTH}",
          len(teeth) == expect, f"{len(teeth)}/{expect}")

    # A 位置去重数（最强判据：端口间齿不得重叠）
    uniq = len(set(teeth))
    check(f"{name} A 齿位置去重 == n_io×{N_TOOTH}（端口间不重叠）",
          uniq == expect, f"去重 {uniq}/{expect}")

    # B 每个端口邻域内齿数 ≥ 16（缺陷态：远端端口邻域齿数 0）
    #   注：曾设「每齿距最近端口 ≤ 12µm」判据，实测缺陷态下齿堆在局部原点、
    #   而原点附近必有一个端口 ⇒ 该判据恒 PASS、零判别力，已移除。判据必须
    #   经反向测试证明会响，否则不算护栏。
    worst = None
    ok_b = True
    for (px, py) in ports:
        cnt = sum(1 for (tx, ty) in teeth
                  if abs(tx - px) <= TOOTH_REACH_UM
                  and abs(ty - py) <= TOOTH_REACH_UM)
        if worst is None or cnt < worst:
            worst = cnt
        if cnt < N_TOOTH:
            ok_b = False
    check(f"{name} B 每端口 {TOOTH_REACH_UM:g}µm 邻域内齿 ≥ {N_TOOTH}",
          ok_b, f"最少端口 {worst} 个")

    # D 齿 x 跨度 > 端口 x 跨度（齿必须跟随端口铺开）
    if n_io >= 2 and teeth and ports:
        span_t = max(t[0] for t in teeth) - min(t[0] for t in teeth)
        span_p = max(p[0] for p in ports) - min(p[0] for p in ports)
        check(f"{name} D 齿 x 跨度 > 端口 x 跨度（齿跟随端口）",
              span_t > span_p + 1e-9,
              f"齿 {span_t:.2f}µm vs 端口 {span_p:.2f}µm")
    else:
        check(f"{name} D 端口数不足，跳过", True, "n_io<2")


def _cpo_ctx():
    """小规格 CPO 阵列：端口跨度达数百µm，给 B 判据提供分辨力。

    WDM 案例端口跨度仅 16µm < 邻域半径，B 判据在其上恒 PASS（判据零
    判别力）——必须配大跨度案例，否则护栏形同虚设。
    """
    from types import SimpleNamespace
    from lda_harness import cpo_array as CA
    cfg = CA.CPOArrayConfig(n_oe=2, n_ch=2, n_lane=8, ch_per_row=2)
    link, placement, routes, _meta = CA.build_cpo_array_case(cfg)
    return SimpleNamespace(link=link, placement=placement, routes=routes)


def main() -> int:
    print("IO 光栅几何定位回归 smoke（P0-0）")
    _case("WDM", {"type": "wdm", "channels_um": [1.53, 1.55, 1.57],
                  "R_um": 10.0, "gap_um": 0.3, "kappa": 0.05})
    _case("CPO", _cpo_ctx())
    npass = sum(1 for c in CHECKS if c[1])
    print("-" * 60)
    print(f"IO 光栅定位 smoke：{npass}/{len(CHECKS)} PASS")
    return 0 if npass == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
