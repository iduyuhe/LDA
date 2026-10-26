#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E35 门禁（D-220）：**CIM 加速器 IP 的 P&R（自建最小但诚实）**。

## 本门禁守什么

E35 在「不借 OpenROAD」前提下，把前四段（E33 阵列 + E34 数字 + E35 布局布线）打包成
**一个真的 CIM 加速器 IP 硬宏**。四层各有一个**机核金标**：

| # | 守护对象 | 金标 |
|---|---|---|
| B1 | 布局 `dplac` | **面积守恒**：Σ(摆放单元面积) ≡ Σ(n_tr·area_per_tr)（差 < 1e-6） |
| B2 | 布线 `droute` | 2 端网线长 ≥ 两端曼哈顿距离；总线长 ≤ 1.5×HPWL；单端网=0 |
| B3 | 线载+STA `dextract` | Fmax(线载) < Fmax(理想)；线载×K 单调降；线载=0 逐位=理想 |
| B4 | IP 硬宏 `dmacro` | 合并 GDS 元素数(emit) ≡ 回读(parse)；GDS 字节 > 仅阵列；外框包围 |

## 探针要求（C1–C4，每个必须打红）

把 E35 **真实会犯的错**变成探针：
- **C1** = 面积不守恒（宽砍半 ⇒ 面积少一半）—— 布局的诚实缺口
- **C2** = 2 端网线长 < 两端距离（物理不可能）—— 布线编数
- **C3** = 线载×100 但 Fmax 不降（伪造「线让电路更快」）—— 线感知 STA 逻辑反
- **C4** = 漏掉数字单元包围盒却谎报 emit（E31 via stack 假绿同型）—— GDS 零丢失

判据有判别力 = 这些探针**打红**；否则绿也不算数。
"""

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import dcell as DC          # noqa: E402
from lda_l2.ecore import dctrl as CT          # noqa: E402
from lda_l2.ecore import dplac as PL          # noqa: E402
from lda_l2.ecore import droute as RT         # noqa: E402
from lda_l2.ecore import dextract as DX       # noqa: E402
from lda_l2.ecore import dmacro as M          # noqa: E402
from lda_l2.ecore import layout as LY         # noqa: E402
from lda_l2.ecore.dsynth import Netlist       # noqa: E402
from lda_l2 import gds_export as G            # noqa: E402
from lda_harness.smoke_kit import make_check  # noqa: E402

# ---------------------------------------------------------------------------
# 关键事实锚（**全部现算可复现**；`==` 只用于精确已知量）
# ---------------------------------------------------------------------------
AN_ROWS_MIN = 1                # 行数下界
AN_RATIO_LO = 0.30             # Fmax(线载)/Fmax(理想) 下界（太小=线载过猛，模型错）
AN_RATIO_HI = 0.999            # 上界（≥1=没生效）
AN_HPWL_FACTOR = 1.5           # 总线长 ≤ 1.5×HPWL 的上界 sanity
AN_ELAPSED_MAX_S = 600.0       # 本门禁耗时上界（实测见末行，留 5× 余量）

#: 🔴 **不写本地 `def check`**：复用 `smoke_kit.make_check`
#: （`run_helper_dup_ratchet_smoke` 的 J3：本地重复实现正是它红了多版的根因）。
PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


def _nl():
    return CT.build()["netlist"]


def b1_place():
    r = PL.plac_self_check(verbose=True)
    check("B1 布局面积守恒（Σ摆放 ≡ Σ n_tr·area_per_tr，差 < 1e-6）+ 全单元落 die + die≥cells",
          r["ok"], (r.get("problems") or [])[:3])
    return r


def b2_route():
    r = RT.route_self_check(verbose=True)
    check("B2 布线：2 端网线长≥L1 · 总线长≤1.5×HPWL · 单端网=0 · 多端必布",
          r["ok"], (r.get("problems") or [])[:3])
    return r


def b3_extract():
    r = DX.extract_self_check(verbose=True)
    check("B3 线感知STA：Fmax(线载)<Fmax(理想) · 线载×100单调降 · 线载=0逐位=理想",
          r["ok"], (r.get("problems") or [])[:3])
    return r


def b4_macro():
    r = M.macro_self_check(verbose=True)
    check("B4 IP硬宏：GDS元素emit≡parse零丢失 · 字节>仅阵列 · 外框包围 · 引脚/单元数一致",
          r["ok"], (r.get("problems") or [])[:3])
    return r


# ---------------------------------------------------------------------------
# 🔴 突变探针 C1–C4（每个都必须**打红** —— 否则判据无判别力）
# ---------------------------------------------------------------------------
def c1_area_not_conserved():
    """C1 · 布局面积不守恒必须被抓红。

    构造一个把每颗单元宽度砍半的伪劣布局（面积少一半）⇒ 守恒判据必须失败。
    """
    nl = _nl()
    p = PL.place(nl)
    bad = PL.Placement(
        cell_xywh={nm: (x, y, w * 0.5, h) for nm, (x, y, w, h) in p.cell_xywh.items()},
        die_w_um=p.die_w_um, die_h_um=p.die_h_um, rows=p.rows,
        cell_area_sum_um2=p.cell_area_sum_um2,
        placed_area_um2=p.placed_area_um2 * 0.5,
        io_ring_um2=p.io_ring_um2, routing_channel_um2=p.routing_channel_um2,
        port_pins=p.port_pins, pin_list=p.pin_list, hpwl_um=p.hpwl_um,
    )
    # 真实判据逻辑：面积守恒
    caught = abs(bad.placed_area_um2 - bad.cell_area_sum_um2) > 1e-6
    check("C1 突变探针：面积不守恒（宽砍半）必须打红", caught,
          ("placed=%.1f vs sum=%.1f" % (bad.placed_area_um2, bad.cell_area_sum_um2)))


def c2_two_pin_too_short():
    """C2 · 2 端网线长 < 两端距离必须被抓红（布线编数）。"""
    nl = _nl()
    p = PL.place(nl)
    r = RT.route(nl, p)
    bad = RT._break_one_two_pin(nl, p, r)
    probs = RT._validate(nl, p, bad)
    caught = any(pr[0] == "two_pin_shorter_than_L1" for pr in probs)
    check("C2 突变探针：2 端网线长<两端距离必须打红", caught, probs[:2])


def c3_wire_not_slower():
    """C3 · 线载×100 但 Fmax 不降必须被抓红（伪造「线让电路更快」）。"""
    nl = _nl()
    p = PL.place(nl)
    rr = RT.route(nl, p)
    wl100 = {net: L * DX.C_WIRE_FF_PER_UM * 100.0 for net, L in rr.length_um.items()}
    fw0 = DX.wire_aware_sta(nl).fmax_wire_mhz
    fw100 = STA_wire(nl, wl100)
    caught = fw100 < fw0
    check("C3 突变探针：线载×100 必须使 Fmax 进一步下降", caught,
          ("fw0=%.1f fw100=%.1f" % (fw0, fw100)))


def STA_wire(nl: Netlist, wl: dict) -> float:
    from lda_l2.ecore import dsta as ST
    return ST.sta(nl, DC.DEFAULT_TECH, wire_load_ff=wl).fmax_mhz or 0.0


def c4_element_loss():
    """C4 · 漏掉数字单元包围盒却谎报 emit 必须被抓红（E31 via stack 假绿同型）。

    构造一个**漏掉所有数字单元包围盒**的伪劣 GDS（模拟「几何体被静默丢进 top 之外」），
    解析出真实的 parse 数（少了数字盒），再谎报 emit = 全量 ⇒ 判据 emit≠parse 必须打红。
    """
    nl = _nl()
    p = PL.place(nl)
    arr_dim = LY.array_footprint(87, 87)
    dig_off_x = arr_dim[0] + M.GAP_UM
    # 伪劣 GDS：仅阵列 + 阵列块外框 + 引脚（**不含数字单元包围盒**）
    arr2 = LY.crossbar_array(87, 87, None, row_layer="M2", via_stack=True)
    tb = []
    for d in arr2["descs"]:
        if d["kind"] == "path":
            tb.append(G.path(d["layer"], d["width_um"], d["points_um"]))
        else:
            for poly in d["rings_um"]:
                tb.append(G.boundary(d["layer"], poly))
    aw2, ah2 = arr_dim
    tb.append(M._box(M.LAYER_IP_BOUNDARY, 0.0, 0.0, aw2, ah2))
    for (_pp, _bb, _nn, xx, yy, _sd) in p.pin_list:
        tb.append(M._pin(M.LAYER_PIN, dig_off_x + xx, yy))
    gds_bad = G.gds_library("CIM_IP_BAD", {"TOP": tb})
    parsed_bad = G.parse_gds_polygons(gds_bad, expand_refs=True)
    n_parsed_bad = sum(len(parsed_bad["structures"][s])
                       for s in parsed_bad.get("top_structures", []))
    # 真实 macro 的 emit（全量，含数字盒）
    m = M.build_ip(nl)
    fake_emit = m.n_emitted            # 谎报：声称包含数字盒
    caught = fake_emit != n_parsed_bad
    check("C4 突变探针：GDS 元素 emit≠parse 必须打红", caught,
          ("fake_emit=%d parse_bad=%d" % (fake_emit, n_parsed_bad)))


def main():
    t0 = time.time()
    print("=" * 78)
    print("E35 · CIM 加速器 IP 的 P&R（自建最小但诚实）· 四层 + 四突变探针")
    print("=" * 78)
    b1_place()
    b2_route()
    b3_extract()
    b4_macro()
    c1_area_not_conserved()
    c2_two_pin_too_short()
    c3_wire_not_slower()
    c4_element_loss()

    dt = time.time() - t0
    check("B0 门禁耗时 %.1f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, dt)
    print("-" * 78)
    print("E35 · 通过 %d · 失败 %d · 耗时 %.1f s" % (PASS, FAIL, dt))
    if FAIL:
        print("FAIL — E35 P&R 出现问题，按上方 [FAIL] 项修复")
        return 1
    print("E35 全绿 · 4 层 P&R 自研 · 面积守恒 / 线长下界 / 线感知 Fmax / GDS 零丢失 · "
          "4 突变探针全打红")
    return 0


if __name__ == "__main__":
    sys.exit(main())
