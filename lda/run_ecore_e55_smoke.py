"""E55 门禁：**单元内部图形接入 DRC**（网标签 · 拼接 · 联合签核）。

═══════════════════════════════════════════════════════════════════════════════
这一版要证明什么
───────────────────────────────────────────────────────────────────────────────
E54 把 DFF 画出来了（DRC 0 / 双射 LVS 0），但它接不进布线。理由不是「布线器不会连引脚」，
而是检查面本身缺失：

    `run_drc(cell)` 只看一颗单元内部 · `route_block` 只看走线自己
    ⇒ 单元↔单元、单元↔走线之间**没有任何检查器**。

而且旧口径有个**方向性错误**：同层间距用「几何连通分量相同 ⇒ 同网 ⇒ 跳过」。
两条本不该相接的走线一旦真的搭上，几何会「正确地把它们并成一个网」⇒ 短路被当成同网放行。
本版把**设计意图**（网标签）单独记一份，让两套口径互为对照：标签不同而几何相连 ⇒ 必报。

六件事分开证，互不代替：
  A **标签**：每块图形都有网名，且与几何连通性逐组一致（三颗单元）；
  B **拼接间距**：abutment 下界可闭式推出并被实测钉住；
  C **反例**：旧口径静默的两种情形（完全重合 / 跨行错位）现在必须红，且撤掉扰动要能复绿；
  D **真实网表装配**：`place_real` 布局 + 电路网名，联合 DRC 零违例；
  E **走线联合**：`route_block` 的走线与单元几何一起签核，且层桥接表覆盖到 M4；
  F **合成可复用**：abutment 后 LVS 仍通过（拼起来电路还对），带缝则如实报开路。

🔴 诚实边界（随任何引用一起给）：
  · 只做几何间距/短路：无串扰、天线、密度、OPC、ESD、well-tap；
  · 规则集 LDA-DEMO28/DEMO45 是**自建教科书尺度**，非 foundry PDK ⇒ 不得作制造宣称；
  · `ddetail.L_V2 = 26` 与真源（26=PAD、28=M2↔M3）存在**历史双口径**：本版不动单元几何，
    只把 28/29 补进桥接表（否则走线在联合图上没有连通性，见 E2/E3）；
  · 走线↔引脚的网名对齐靠调用方显式给（`netlist` / `route_prefix=""`），不给则按
    「未声明连接即短路」处理 —— 保守方向。
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_l2.ecore import dcells as CL       # noqa: E402
from lda_l2.ecore import dcnet as NT        # noqa: E402
from lda_l2.ecore import ddrc_lvs as DL     # noqa: E402
from lda_l2.ecore import dctrl as CT        # noqa: E402
from lda_l2.ecore import dhdlib as HD       # noqa: E402
from lda_l2.ecore import dpnr as PN         # noqa: E402

_FAILED: list = []
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   record=_FAILED)
T0 = time.time()
AN_ELAPSED_MAX_S = 240.0

#: 🔴 abutment 下界：INV/NAND2/DFF 都有引脚**贴到单元边界**（pad 外沿 = 边界），
#: 零间隙时相邻单元的引脚 pad 必然相距 0 ⇒ 必须 ≥ M1 最小间距才不违例。
#: 这不是调参调出来的，是从规则 + 引脚位置推出来的（判据 B2/B3 实测钉住）。
ABUT_MIN_NM = HD.HD_RULES["m1_s"]


def _row(cells, gap):
    return NT.row_of(cells, gap_nm=gap)


# ---------------------------------------------------------------------------
# A · 网标签：每块图形都有网名，且与几何连通性逐组一致
# ---------------------------------------------------------------------------
def a_labels():
    trio = (("INV", HD.build_inv_hd()), ("NAND2", HD.build_nand2_hd()),
            ("DFF", HD.build_dff_hd()))
    ok_cov, ok_rep, named_seen, anon_seen = True, True, set(), set()
    detail = []
    for nm, c in trio:
        lab = CL.label_cell(c)
        n_shapes = len(CL._shapes(c))
        cov = (len(lab) == n_shapes and all(v is not None for v in lab.values()))
        rep = CL.label_report(c)
        ok_cov = ok_cov and cov
        ok_rep = ok_rep and (rep["n"] == 0)
        for v in lab.values():
            (anon_seen if str(v).startswith("#") else named_seen).add(str(v))
        detail.append("%s:lab=%d/shapes=%d,rep=%d" % (nm, len(lab), n_shapes, rep["n"]))
    check("A1 三颗单元的**每块图形都有网标签**（无 None、无漏标）且标签⇔连通性零不一致",
          ok_cov and ok_rep, "; ".join(detail))

    # A2 命名规则：有引脚的分量用真引脚名，其余按几何稳定编号 #k
    ok_names = ({"A", "Y"} <= named_seen) and bool(anon_seen)
    check("A2 命名规则：引脚网用真名（A/Y 等 %d 个）· 无名内部节点编 #k（%d 个）"
          % (len(named_seen), len(anon_seen)),
          ok_names, "named=%s anon=%s" % (sorted(named_seen)[:6], sorted(anon_seen)[:4]))

    # A3 非信号层（NWELL 工艺岛）统一标签、且不参与网比对
    inv = HD.build_inv_hd()
    lab = CL.label_cell(inv)
    nwell = {lab.get(CL._geom_key(r)) for r in inv.by_layer(CL.L_NWELL)}
    ex = CL.NON_SIGNAL_LAYERS == (CL.L_NWELL,)
    check("A3 非信号层：NWELL 标签统一为 %r 且列入 NON_SIGNAL_LAYERS（不参与网比对）"
          % CL._NON_SIGNAL_NAME,
          nwell == {CL._NON_SIGNAL_NAME} and ex, "nwell=%s ex=%s" % (nwell, ex))

    # A4/A5 布线器要的两个视图：**能连的**（引脚）与**要躲的**（内部非引脚图形）。
    # 这正是 E54 那句「cell_shapes 只带引脚 ⇒ 内部 M2 是盲区」的正面回答：
    # 不是把内部图形藏起来，而是把两类图形**分开、各自带网名**交出去。
    pins = NT.pin_shapes(inv)
    obs = NT.obstacles(inv)
    obs_all = NT.obstacles(inv, include_pins=True)
    n_pin_rects = len(inv.pins)
    ok_pin = (len(pins) == n_pin_rects
              and all(p["net"] and p["x1"] > p["x0"] for p in pins))
    ok_obs = (len(obs) + n_pin_rects == len(obs_all) and len(obs) > 0
              and all(o["layer"] != CL.L_NWELL for o in obs))
    check("A4 布线器视图：`pin_shapes` 只给引脚（%d 个，全带网名）· `obstacles` 给内部非引脚"
          "图形（%d 块，不含工艺岛），两者并集 == 全量（%d）"
          % (len(pins), len(obs), len(obs_all)),
          ok_pin and ok_obs,
          "pins=%d obs=%d all=%d" % (len(pins), len(obs), len(obs_all)))

    # A5 障碍视图**带网名**：布线器据此区分「这是别人的网（要躲）」和「这是我自己的网（可接）」
    lab_all = [o["net"] for o in obs]
    check("A5 障碍视图逐块带网名（有网名 %d/%d）—— 否则布线器无法区分「要躲」与「可接」"
          % (sum(1 for v in lab_all if v), len(lab_all)),
          all(lab_all), "无网名 %d 块" % sum(1 for v in lab_all if not v))


# ---------------------------------------------------------------------------
# B · 拼接间距：abutment 下界可推、可测、单调
# ---------------------------------------------------------------------------
def b_abut():
    trio = [HD.build_inv_hd(), HD.build_nand2_hd(), HD.build_dff_hd()]

    tiles, w0 = _row(trio, 0)
    j0 = NT.joint_drc(tiles, rules=HD.HD_RULES)
    kinds0 = sorted({v[0] for v in j0["drc"]["violations"]})
    check("B1 零间隙 abutment 必报：DRC=%d（%s）· 短路 bridges=%d（NAND2.Y ↔ DFF.D 真接触）"
          % (j0["n_drc"], ",".join(kinds0), len(j0["bridges"])),
          j0["n_drc"] > 0 and len(j0["bridges"]) > 0,
          "drc=%d bridges=%d" % (j0["n_drc"], len(j0["bridges"])))

    tiles, w = _row(trio, ABUT_MIN_NM)
    j1 = NT.joint_drc(tiles, rules=HD.HD_RULES)
    check("B2 间隙 == M1 最小间距（%d nm）即全零：DRC=%d · bridges=%d · 标签不一致=%d"
          % (ABUT_MIN_NM, j1["n_drc"], len(j1["bridges"]), j1["labels"]["n"]),
          j1["n_drc"] == 0 and not j1["bridges"] and j1["labels"]["n"] == 0,
          "drc=%d bridges=%d rep=%d" % (j1["n_drc"], len(j1["bridges"]),
                                        j1["labels"]["n"]))

    below = [g for g in (0, ABUT_MIN_NM // 3, ABUT_MIN_NM - 10)
             if NT.joint_drc(_row(trio, g)[0], rules=HD.HD_RULES)["n_drc"] > 0]
    at = [g for g in (ABUT_MIN_NM, ABUT_MIN_NM * 2, ABUT_MIN_NM * 4)
          if NT.joint_drc(_row(trio, g)[0], rules=HD.HD_RULES)["n_drc"] == 0]
    check("B3 阈值单调：gap<abut 全部非零（%d/3）· gap≥abut 全部零（%d/3）"
          % (len(below), len(at)), len(below) == 3 and len(at) == 3,
          "below=%s at=%s" % (below, at))


# ---------------------------------------------------------------------------
# C · 反例：旧口径静默的两种情形必须红，撤掉扰动必须复绿
# ---------------------------------------------------------------------------
def c_probes():
    inv = HD.build_inv_hd()

    # C1 完全重合：几何键相同 ⇒ 标签会塌成一个 ⇒ 旧口径 DRC=0。现在由 compose 记 conflicts。
    tiles = [(inv, 0, 0, "u0"), (inv, 0, 0, "u1")]
    c = CL.compose(tiles)
    j = NT.joint_drc(tiles, rules=HD.HD_RULES)
    check("C1 两单元**完全重合**必被抓住（conflicts=%d 条，DRC 计入 %d）—— 旧口径此处静默"
          % (len(c.conflicts), j["n_drc"]),
          len(c.conflicts) > 0 and j["n_drc"] > 0,
          "conflicts=%d drc=%d" % (len(c.conflicts), j["n_drc"]))

    # C2 跨行错位：不同网的 M1 焊盘压到一起
    bad = [(inv, 0, 0, "u0"), (inv, 220, 370, "u1")]
    jb = NT.joint_drc(bad, rules=HD.HD_RULES)
    # C3 撤掉错位（同排相邻）⇒ 复绿
    good = [(inv, 0, 0, "u0"), (inv, inv.w + ABUT_MIN_NM, 0, "u1")]
    jg = NT.joint_drc(good, rules=HD.HD_RULES)
    check("C2 跨行错位(220,370) 必红：DRC=%d · 短路=%d" % (jb["n_drc"], len(jb["bridges"])),
          jb["n_drc"] > 0 and len(jb["bridges"]) > 0,
          "drc=%d bridges=%d" % (jb["n_drc"], len(jb["bridges"])))
    check("C3 同排正常间距复绿：DRC=%d · 短路=%d（证明 C2 不是恒红）"
          % (jg["n_drc"], len(jg["bridges"])),
          jg["n_drc"] == 0 and not jg["bridges"],
          "drc=%d bridges=%d" % (jg["n_drc"], len(jg["bridges"])))


# ---------------------------------------------------------------------------
# D · 真实网表装配：place_real 布局 + 电路网名
# ---------------------------------------------------------------------------
def d_netlist():
    nl = CT.build()["netlist"]
    pl = PN.place_real(nl, max_cells=8, truncate_ok=True)

    tiles_pre, _ = NT.place_tiles(pl)                     # 无网表：每实例前缀
    jp = NT.joint_drc(tiles_pre, rules=CL.RULES)
    tiles, meta = NT.place_tiles(pl, netlist=nl)          # 有网表：电路网名
    j = NT.joint_drc(tiles, rules=CL.RULES, allow_multi_fragment=True)

    check("D1 8 单元真实布局联合 DRC 零违例（无网表口径 %d → 电路网名口径 %d）"
          % (jp["n_drc"], j["n_drc"]),
          jp["n_drc"] == 0 and j["n_drc"] == 0,
          "prefix=%d netlist=%d" % (jp["n_drc"], j["n_drc"]))
    check("D2 µm→nm 换算**零误差**（偏差 %.3e µm，唯一换算点在 `dcnet.to_nm`）"
          % meta["max_origin_err_um"],
          meta["max_origin_err_um"] == 0.0, "%.3e" % meta["max_origin_err_um"])
    check("D3 「同网多片段」判为**待布线**（%d 条）而不是缺陷（mismatch=%d）—— "
          "口径分开才不会被假开路淹掉" % (j["labels"]["n_unrouted"], j["labels"]["n"]),
          j["labels"]["n"] == 0 and j["labels"]["n_unrouted"] > 0,
          "unrouted=%d mism=%d" % (j["labels"]["n_unrouted"], j["labels"]["n"]))


# ---------------------------------------------------------------------------
# E · 走线联合：层桥接覆盖到 M4，走线与单元一起签核
# ---------------------------------------------------------------------------
def e_route():
    nl = CT.build()["netlist"]
    pl = PN.place_real(nl, max_cells=8, truncate_ok=True)
    res = PN.route_block(nl, pl)
    tiles, _ = NT.place_tiles(pl, netlist=nl)
    j = NT.joint_drc(tiles, route=res["shapes"], rules=CL.RULES,
                     route_prefix="", allow_multi_fragment=True)

    check("E1 走线 + 单元**联合签核**：%d 形状 → DRC=%d · 短路=%d · 标签不一致=%d"
          % (j["n_rects"], j["n_drc"], len(j["bridges"]), j["labels"]["n"]),
          j["n_drc"] == 0 and not j["bridges"] and j["labels"]["n"] == 0,
          "drc=%d bridge=%d rep=%d" % (j["n_drc"], len(j["bridges"]),
                                       j["labels"]["n"]))

    check("E2 走线**真的接到引脚**：几何上零个待布线网（unrouted=%d）—— 这要求 M3↔M4 桥接在位"
          % j["labels"]["n_unrouted"],
          j["labels"]["n_unrouted"] == 0,
          "unrouted=%d（缺 VIA2/M4 桥接时实测会涨到 56）" % j["labels"]["n_unrouted"])

    # E3 层桥接表两处一致（与 E54 J3 同源：同一物理事实不能有两份真源）
    missing = [hex(k) for k in DL.VIA_BRIDGE if k not in CL._VIA_BRIDGE]
    same = all([int(x) for x in CL._VIA_BRIDGE[k]] == [int(x) for x in v]
               for k, v in DL.VIA_BRIDGE.items() if k in CL._VIA_BRIDGE)
    check("E3 `dcells._VIA_BRIDGE` 覆盖 `ddrc_lvs.VIA_BRIDGE` 全部 %d 层且逐项一致"
          % len(DL.VIA_BRIDGE),
          not missing and same, "missing=%s same=%s" % (missing, same))

    # E4 反例：一条 M1 走线横穿 INV 内部 ⇒ 必报
    class _S:
        def __init__(self, layer, x0, y0, x1, y1, net=None):
            self.layer, self.x0, self.y0, self.x1, self.y1, self.net = \
                layer, x0, y0, x1, y1, net

    inv = HD.build_inv_hd()
    through = [_S(CL.L_M1, 0.1, 0.1, 0.2, 0.9, "zz")]
    jt = NT.joint_drc([(inv, 0, 0, "u0", None)], route=through,
                      rules=HD.HD_RULES, route_prefix="")
    outside = [_S(CL.L_M1, 2.0, 0.1, 2.1, 0.9, "zz")]
    jo = NT.joint_drc([(inv, 0, 0, "u0", None)], route=outside,
                      rules=HD.HD_RULES, route_prefix="")
    check("E4 走线**穿过单元内部**必红（%d 条）· 移出单元后复绿（%d 条）"
          % (jt["n_drc"], jo["n_drc"]),
          jt["n_drc"] > 0 and jo["n_drc"] == 0,
          "through=%d outside=%d" % (jt["n_drc"], jo["n_drc"]))


# ---------------------------------------------------------------------------
# F · 合成可复用：拼起来电路还对（abutment LVS 通过；带缝如实报开路）
# ---------------------------------------------------------------------------
def f_compose_lvs():
    inv, nan = HD.build_inv_hd(), HD.build_nand2_hd()

    t_abut = [(inv, 0, 0, "u0"), (nan, inv.w, 0, "u1")]
    j_abut = NT.joint_drc(t_abut, rules=HD.HD_RULES)
    lv_abut = HD.run_lvs_pos(j_abut["cell"])

    t_gap = [(inv, 0, 0, "u0"), (nan, inv.w + ABUT_MIN_NM, 0, "u1")]
    j_gap = NT.joint_drc(t_gap, rules=HD.HD_RULES)
    lv_gap = HD.run_lvs_pos(j_gap["cell"])

    check("F1 abutment 后**双射 LVS 仍通过**（%d 器件 / 网双射，失配 %d）—— 拼起来电路还对"
          % (lv_abut["n_got"], lv_abut["n"]),
          j_abut["n_drc"] == 0 and lv_abut["n"] == 0,
          "drc=%d lvs=%d" % (j_abut["n_drc"], lv_abut["n"]))
    check("F2 带缝则**如实报开路**（LVS 失配 %d）—— 同一网被拆不算通过" % lv_gap["n"],
          lv_gap["n"] > 0, "drc=%d lvs=%d" % (j_gap["n_drc"], lv_gap["n"]))


# ---------------------------------------------------------------------------
# G · 可扩展：规则是参数，标签自动导出
# ---------------------------------------------------------------------------
def g_extend():
    inv = HD.build_inv_hd()
    n_hd = CL.run_drc(inv, HD.HD_RULES)["n"]
    n_45 = CL.run_drc(inv, CL.RULES)["n"]
    check("G1 **规则是参数**：同一颗 28nm 单元用 DEMO28 规则 DRC=%d、用 DEMO45 规则 DRC=%d"
          "（判定器同一份实现）" % (n_hd, n_45),
          n_hd == 0 and n_45 > 0, "hd=%d dem45=%d" % (n_hd, n_45))

    # 库里的老单元（DEMO45）也能**自动**拿到标签，不需要作者写网表
    c45 = CL.CELLS["INV_X1"]()
    lab = CL.label_cell(c45)
    rep = CL.label_report(c45)
    check("G2 未登记到新框架的老单元（`dcells.CELLS['INV_X1']`）**自动获得标签**"
          "（%d 块 / 不一致 %d）" % (len(lab), rep["n"]),
          len(lab) == len(CL._shapes(c45)) and rep["n"] == 0,
          "lab=%d rep=%d" % (len(lab), rep["n"]))


def main() -> int:
    a_labels()
    b_abut()
    c_probes()
    d_netlist()
    e_route()
    f_compose_lvs()
    g_extend()

    dt = time.time() - T0
    check("H0 门禁耗时 %.2f s < %.0f s" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, "%.2f s" % dt)

    print()
    print("  [标签] 三单元逐块有网名 · 与几何连通性零不一致 · 无名节点按几何稳定编号")
    print("  [拼接] abutment 下界 = M1 最小间距 %d nm（可推可测 · 单调）" % ABUT_MIN_NM)
    print("  [盲区] 完全重合 / 跨行错位 / 走线穿单元 —— 三种旧口径静默情形现已必红")
    print("  [联合] 8 单元 + 走线：DRC 0 · 短路 0 · 待布线 0（M3↔M4 桥接在位）")
    print("  [复用] abutment 后合成电路 LVS 仍通过 · 规则换 dict 不换实现")
    print("  [边界] 只做几何间距/短路 · LDA-DEMO28/45 非 foundry PDK · "
          "ddetail.L_V2=26 与真源存在历史双口径（本版不动单元几何）")
    print()
    if _FAILED:
        print("E55 有红色：%s" % ", ".join(_FAILED))
        return 1
    print("E55 全绿 · 单元内部图形接入 DRC：网标签成为一等公民，联合签核零违例")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
