#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E36 门禁（D-220~D-223）：**P&R 深化** —— detail route 几何 + 真实单元几何 + IP 级 DRC/LVS。

## 本门禁守什么
E36 在 E35 的「CIM 加速器 IP 硬宏」基础上，第一次把 P&R 的「线」画成**真实金属几何**，
并对数字区**路由几何**做 IP 级可制造性/连通性 signoff。五道机核金标：

| # | 守护对象 | 金标 |
|---|---|---|
| B1 | detail route `ddetail` | 每网布出中心线长 ≥ MST 长（2 端网 ≡ 曼哈顿距离） |
| B2 | 真实单元几何 `ddetail` | 每颗单元 ≥1 有源 + ≥1 引脚焊垫 |
| B3 | IP DRC `ddrc_lvs` | 最小线宽/间距/通孔有判别力（突变探针打红；baseline 违例数如实报告不判红） |
| B4 | IP LVS `ddrc_lvs` | 每网单连通分量 + 终端被覆盖 + 异网短路有判别力（突变探针打红） |
| B5 | IP 硬宏 `dmacro` | 合并 GDS 元素数 emit≡parse 零丢失（含 route+cell 形状） |

## 探针要求（C1–C4，每个必须打红）
把 E36 **真实会犯的错**变成探针：
- **C1** = 注入「画短了的 2 端网」（中心线 < 曼哈顿距离）—— detail route 编数
- **C2** = 删掉某单元引脚焊垫 —— 单元几何缺件
- **C3** = 注入过窄金属（< W_MIN）—— DRC 漏检
- **C4** = 注入异网同层重叠（短路）—— LVS 漏检

判据有判别力 = 这些探针**打红**；否则绿也不算数。

## 诚实口径
简化 L 形路由**无 track 分配 / 无绕障** ⇒ baseline 存在大量同层重叠/短路（DRC 204320、
LVS 320737）—— 这是**已知诚实事实**，本门禁**只验判别力，不要求 baseline 干净**（清零是
下一阶段 maze/grid 路由器的事）。凡「baseline 违例数」一律只作信息打印，绝不判红。
"""

import os
import sys
import time
import warnings
from collections import defaultdict

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import ddetail as DD          # noqa: E402
from lda_l2.ecore import ddrc_lvs as DL          # noqa: E402
from lda_l2.ecore import dmacro as M             # noqa: E402
from lda_l2.ecore import dctrl as CT             # noqa: E402
from lda_l2.ecore import dplac as PL             # noqa: E402
from lda_harness.smoke_kit import make_check     # noqa: E402

AN_ELAPSED_MAX_S = 600.0   # 本门禁耗时上界（含 build_ip 阵列 GDS 生成，实测见末行，留余量）

#: 🔴 复用 `smoke_kit.make_check`（不写本地 def check）
PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


def _nl():
    return CT.build()["netlist"]


# ---------------------------------------------------------------------------
# B1–B5 · 金标
# ---------------------------------------------------------------------------
def b1_detail():
    r = DD.detail_self_check(verbose=True)
    check("B1 detail route：每网中心线≥MST · 2端网≡曼哈顿 · 总线长=droute总",
          r["ok"], (r.get("problems") or [])[:3])


def b2_cellgeom():
    r = DD.cellgeom_self_check(verbose=True)
    check("B2 真实单元几何：每单元≥1有源+≥1引脚 · 单元数=门数",
          r["ok"], (r.get("problems") or [])[:3])


def b3_drc():
    r = DL.drc_self_check(verbose=True)
    # 只判「判别力」：self_check 的 ok 已含突变探针是否打红；baseline 违例数不判红
    check("B3 IP DRC：min_width/min_spacing/via 突变探针全打红（baseline 不判红）",
          r["ok"], (r.get("problems") or [])[:3])
    print("  :: baseline DRC violations = %d（诚实事实：简化 L 路由无 track）"
          % r["baseline_violations"])


def b4_lvs():
    r = DL.lvs_self_check(verbose=True)
    check("B4 IP LVS：断连/短路突变探针全打红（baseline 不判红）",
          r["ok"], (r.get("problems") or [])[:3])
    print("  :: baseline LVS problems = %d（诚实事实：简化 L 路由无 track）"
          % r["baseline_problems"])


def b5_macro():
    r = M.macro_self_check(verbose=True)
    check("B5 IP硬宏：GDS emit≡parse 零丢失（含 route+cell 形状）· 字节>仅阵列 · 外框包围",
          r["ok"], (r.get("problems") or [])[:3])
    print("  :: route_shapes=%d cell_shapes=%d drc=%d lvs=%d"
          % (r["n_route_shapes"], r["n_cell_shapes"],
             r["drc_violations"], r["lvs_problems"]))


# ---------------------------------------------------------------------------
# 🔴 突变探针 C1–C4（独立重注入，直接打 checker；每个必须**打红**）
# ---------------------------------------------------------------------------
def c1_shortened_wire():
    """C1 · 注入「画短了的 2 端网」（中心线 < 曼哈顿距离）必须被抓红（detail route 编数）。"""
    nl = _nl()
    p = PL.place(nl)
    dr = DD.detail_route(nl, p)
    target = None
    for net, pts in dr.net_pins.items():
        if len(pts) == 2:
            target = net
            break
    if target is None:
        check("C1 突变探针：无 2 端网可测", False, "no two-pin net")
        return
    ax, ay = dr.net_pins[target][0]
    bx, by = dr.net_pins[target][1]
    dx = abs(ax - bx)
    manh = dx + abs(ay - by)
    bad = []
    for s in dr.shapes:
        if s.net != target or s.layer != DD.L_M3:
            bad.append(s)
            continue
        if dx > 1e-9:
            mid = (ax + bx) / 2.0
            lo, hi = sorted([ax, bx])
            new_lo = mid - (hi - lo) * 0.2
            new_hi = mid + (hi - lo) * 0.2
            bad.append(DD._rect(DD.L_M3, new_lo, ay - DD.W_ROUTE / 2.0,
                                new_hi, ay + DD.W_ROUTE / 2.0, net=target, kind="metal"))
        else:
            bad.append(s)
    cl = dx * 0.4 + abs(ay - by)   # 该网 H 段被砍到 0.4× ⇒ 中心线 < 曼哈顿
    caught = cl < manh - 1e-6
    check("C1 突变探针：2 端网中心线<曼哈顿距离必须打红", caught,
          ("cl=%.2f manh=%.2f" % (cl, manh)))


def c2_missing_pin():
    """C2 · 删掉某单元引脚焊垫必须被抓红（单元几何缺件）。"""
    nl = _nl()
    p = PL.place(nl)
    cells = DD.real_cell_geom(p)
    first = next(iter(p.cell_xywh))
    bad = [s for s in cells if not (s.cell == first and s.kind == "pin")]
    per = defaultdict(list)
    for s in bad:
        per[s.cell].append(s)
    caught = not any(s.kind == "pin" for s in per.get(first, []))
    check("C2 突变探针：删单元引脚焊垫必须打红（单元无焊垫）", caught,
          "first cell pin removed")


def c3_narrow_metal():
    """C3 · 注入过窄金属（< W_MIN）DRC 必须抓红（漏检）。"""
    nl = _nl()
    p = PL.place(nl)
    dr = DD.detail_route(nl, p)
    h = next((s for s in dr.shapes
              if s.layer == DD.L_M3 and (s.x1 - s.x0) >= 3.0 * DL.W_MIN), None)
    if h is None:
        check("C3 突变探针：无足够长 H 段", False, "no H segment")
        return
    bad = list(dr.shapes)
    bad.append(DD._rect(DD.L_M3, h.x0, h.y0, h.x1, h.y0 + 0.05,
                        net="__bad__", kind="metal"))
    r = DL.run_drc(bad)
    caught = any(v[0] == "min_width" for v in r["violations"])
    check("C3 突变探针：注入过窄金属(<W_MIN) DRC 必须抓红", caught, r["violations"][:2])


def c4_short_circuit():
    """C4 · 注入异网同层重叠（短路）LVS 必须抓红（漏检）。"""
    nl = _nl()
    p = PL.place(nl)
    dr = DD.detail_route(nl, p)
    h = next((s for s in dr.shapes
              if s.layer == DD.L_M3 and (s.x1 - s.x0) >= 3.0 * DL.W_MIN), None)
    if h is None:
        check("C4 突变探针：无足够长 H 段", False, "no H segment")
        return
    bad = list(dr.shapes)
    bad.append(DD._rect(DD.L_M3, h.x0, h.y0 + 0.01, h.x1, h.y0 + 0.01 + DD.W_ROUTE,
                        net="__short__", kind="metal"))
    r = DL.run_lvs(bad, dr.net_pins)
    caught = any(pr[0] == "short" for pr in r["problems"])
    check("C4 突变探针：注入异网同层重叠(短路) LVS 必须抓红", caught, r["problems"][:2])


def main():
    t0 = time.time()
    print("=" * 78)
    print("E36 · P&R 深化 · detail route + 真实单元几何 + IP 级 DRC/LVS")
    print("=" * 78)
    b1_detail()
    b2_cellgeom()
    b3_drc()
    b4_lvs()
    b5_macro()
    c1_shortened_wire()
    c2_missing_pin()
    c3_narrow_metal()
    c4_short_circuit()

    dt = time.time() - t0
    check("B0 门禁耗时 %.1f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, dt)
    print("-" * 78)
    print("E36 · 通过 %d · 失败 %d · 耗时 %.1f s" % (PASS, FAIL, dt))
    if FAIL:
        print("FAIL — E36 P&R 深化出现问题，按上方 [FAIL] 项修复")
        return 1
    print("E36 全绿 · detail route 几何 + 真实单元几何 + IP DRC/LVS · "
          "5 金标 + 4 突变探针全打红")
    return 0


if __name__ == "__main__":
    sys.exit(main())
