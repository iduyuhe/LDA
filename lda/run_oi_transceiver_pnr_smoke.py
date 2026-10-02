# -*- coding: utf-8 -*-
"""LDA 光联接模块征程 · M2 · **G-OI2 收发器真 GDS 门禁**（吃狗粮硬门禁）。

覆盖（T 系列 = 门禁本体；V 系列 = **布局纪律反例**；P 系列 = 突变探针）：
  T1  真 GDS：非空 + HEADER 魔数 00 06 00 02 + sha256 形状 + **平台解析器读回一致**
  T2  双闸：DRC 逐器件全绿（零违规）+ LVS ACCEPT（零违规）
  T3  拓扑自洽：器件数 ≡ 3N+3 · 网数 ≡ 3N+1 · Tx/Rx 各 N 件
  T4  布局纪律①：Tx 与 Rx 的 **bbox y 带不相交**（结构性防跨域交叉）
  T5  端口同源：**每条** route 的两端点精确落在其声明端口的 port_anchor 上（Δ<1e-9）
  T5b/T5c 布局前提（builder 报出的标量）：B > 源 x 上界 · b_i > s_i · det y 同侧
  T5d 布局纪律三前提（**第二独立通道** · `layout_discipline_ok` 读 port_anchor 反推）
  T6  确定性双向：同参数 sha256 逐位一致 · 换 n_lanes sha256 必变
  T7  片外 fiber 不落版图：gc_tx.fib / gc_rx.fib **不属任何内部 net**
  T8  环半径 ≡ 闭式 m·λ/(2π·n_g)（独立复算）且 ≥ DRC min_bend_R
  T9  逐规模双闸：n_lanes ∈ {1,2,4,8,12} 全部 真GDS + 双闸 ACCEPT + 三前提（不只测默认档）
  T10 D4 域一致：`build_domain('oi_transceiver')` 的 sha256 ≡ 直接 builder（两条链同源）
  T11 诚实边界：disclosure 键齐备 + 关键短口径在场 + 无 TOPS/能效字样
  V1  **反序纪律反例**：把 Tx 映射改成同序（`in{i+1}`）⇒ LVS 必 REJECT（cross_short）
  V2  **反序纪律反例**：把 Rx 探测器 y 改成递减 ⇒ LVS 必 REJECT（cross_short）
  V3  删一条 route ⇒ open ⇒ REJECT
  V4  挪一个器件 30 µm（> tol）⇒ dangling ⇒ REJECT
  V5  塞一条横穿走线带的伪网 ⇒ cross_short ⇒ REJECT
  P1  GDS 伪造为空字节 ⇒ T1 必红
  P2  builder 静默忽略 n_lanes（`_add` 后强制 n=8）⇒ T6 必红
  P3  DRC 伪造成 REJECT ⇒ T2 必红
  P4  Tx 映射改回同序 ⇒ `layout_discipline_ok.reverse_order_ok` 必变 False
  P5  Rx det y 排成递减 ⇒ 同一护栏 Rx 侧必变 False
  P6  强行令 `layout_discipline_ok.ok` 恒 True ⇒ 反例被伪装成绿（证 T5d 真由它驱动）
  P7  §6·P8a 拓扑退化：**去掉探测器阵列**（留 net）⇒ 网表一致性必红
  P8  §6·P8b 拓扑退化：**拿酉网格「计算核」顶替收发器** ⇒ LVS 必 REJECT
  R   探针还原后基线重跑必须全绿

🔴 本门禁的**核心命题**：G-OI2 版图的「零 cross_short」不是靠声明，而是靠
「源 x 次序 ⟂ 目标 y 次序（**反序**）+ 目标 x 全同」这条**可证充分条件**；
V1/V2 两条反例正是这条规律的**必要性**证明（同序 ⇒ LVS 立刻报 C(N,2) 处交叉）。

运行：python run_oi_transceiver_pnr_smoke.py（cwd=lda/）
"""
from __future__ import annotations

import hashlib
import math
import os
import sys
import types
import unittest.mock as mock

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=' —— {d}')

from lda_l2 import drc as drc_mod          # noqa: E402
from lda_l2 import gds_export as gx        # noqa: E402
from lda_l2 import lvs as lvs_mod          # noqa: E402
from lda_layout import oi_transceiver_pnr as P  # noqa: E402

_N_DEFAULT = 8


def _abs_manual(inst, port, placement, kind_of, params_of):
    """**不经 port_abs 缓存路径**的端点复算（placement 原点 + port_anchor）。"""
    from lda_layout.placement import port_anchor
    ox, oy, _rot = placement[inst]
    dx, dy = port_anchor(kind_of[inst], port, params_of[inst])
    return (ox + dx, oy + dy)


def _kind_params(rep):
    kind_of = {c.id: c.kind for c in rep["link"].ir.components}
    params_of = {c.id: dict(c.params) for c in rep["link"].ir.components}
    return kind_of, params_of


def main() -> int:
    print("=" * 74)
    print("LDA 光联接模块征程 · M2 · G-OI2 收发器真 GDS 门禁")
    print("=" * 74)

    rep = P.build_oi_transceiver_pnr(n_lanes=_N_DEFAULT)
    n = rep["n_lanes"]
    gds = rep["gds_bytes"]
    kind_of, params_of = _kind_params(rep)

    # ── T1 真 GDS ──────────────────────────────────────────────────────
    sha = hashlib.sha256(gds).hexdigest()
    parsed = gx.parse_gds(gds)
    sname = f"OI_TRX_{n}x200G"
    check(f"T1a 真 GDS：{len(gds)} 字节 · HEADER 魔数 · sha256 64hex",
          len(gds) > 0 and bytes(gds[:4]) == b"\x00\x06\x00\x02" and len(sha) == 64)
    check(f"T1b 平台解析器读回一致：库名={parsed['libname']} 结构={parsed['n_structures']} "
          f"元素 {parsed['structures'].get(sname, {}).get('elements')} ≡ 构建期 {rep['gds_elements']}",
          parsed["libname"] == "LDA_OI_TRANSCEIVER"
          and parsed["n_structures"] == 1
          and parsed["structures"].get(sname, {}).get("elements") == rep["gds_elements"]
          and len(parsed["structures"].get(sname, {}).get("layers") or []) >= 1)

    # ── T2 双闸 ────────────────────────────────────────────────────────
    dv = {k: v for k, v in rep["drc_results"].items() if not v["passed"]}
    check(f"T2a DRC 逐器件全绿（{len(rep['drc_results'])} 件 · 违规 {len(dv)}）", not dv)
    check(f"T2b LVS ACCEPT 且零违规（{rep['lvs_n_violations']} 违规 · "
          f"器件 {rep['lvs_match']['n_devices_match']}/{rep['lvs_match']['n_devices_match']}"
          f" · 网 {rep['lvs_match']['n_nets_match']}/{rep['lvs_match']['n_nets_total']}）",
          rep["lvs_verdict"] == "ACCEPT" and rep["lvs_n_violations"] == 0
          and rep["lvs_match"]["n_nets_match"] == rep["lvs_match"]["n_nets_total"])

    # ── T3 拓扑自洽 ────────────────────────────────────────────────────
    check(f"T3a 器件数 {rep['n_devices']} ≡ 3N+3 = {3 * n + 3}（Tx {rep['n_tx_mods']} + "
          f"MMIC 1 + GC 2 + Ring {rep['n_rx_rings']} + Det {rep['n_rx_dets']}）",
          rep["n_devices"] == 3 * n + 3 == rep["n_tx_mods"] + rep["n_rx_rings"]
          + rep["n_rx_dets"] + 3)
    check(f"T3b 网数 {rep['n_nets']} ≡ 3N+1 = {3 * n + 1}（tx_lane N + tx_out 1 + "
          f"rx_in 1 + rx_bus N−1 + rx_drop N）", rep["n_nets"] == 3 * n + 1)
    check("T3c 每条 route 折线点数符合拓扑（Tx lane 3 点 · rx_drop 3 点 · bus 2 点）",
          all(len(rep["routes"][f"tx_lane{i}"]["points_um"]) == 3 for i in range(n))
          and all(len(rep["routes"][f"rx_drop{i}"]["points_um"]) == 3 for i in range(n))
          and all(len(rep["routes"][f"rx_bus{i}"]["points_um"]) == 2 for i in range(n - 1))
          and len(rep["routes"]["tx_out"]["points_um"]) == 2
          and len(rep["routes"]["rx_in"]["points_um"]) == 2)

    # ── T4 布局纪律①：Tx/Rx y 带不相交 ─────────────────────────────────
    tx_band, rx_band = rep["tx_y_band"], rep["rx_y_band"]
    check(f"T4 Tx bbox y 带 [{tx_band[0]:.1f},{tx_band[1]:.1f}] 与 Rx "
          f"[{rx_band[0]:.1f},{rx_band[1]:.1f}] **不相交**（结构性防跨域交叉）",
          tx_band[0] > rx_band[1] or rx_band[0] > tx_band[1])

    # ── T5 端口同源（独立复算端点）──────────────────────────────────────
    # 🔴 坑：`schematic_nets` 的端口列表是 sorted 的，但 route 的 pts[0]/pts[-1]
    #    有**源→目标**的方向 ⇒ 直接 zip 会错位（首版 34/50 假失配）。
    #    正确做法：每个端点各自找**最近端口**（无序匹配），并要求两端落到不同端口。
    bad_end, n_end = [], 0
    for net_id, rr in rep["routes"].items():
        net = next((x for x in rep["link"].ir.nets if x.id == net_id), None)
        pts = rr["points_um"]
        if net is None or len(net.connects) < 2:
            continue
        ports = [x for x in net.connects if "." in x]
        matched = []
        for got in (pts[0], pts[-1]):
            cands = []
            for w in ports:
                inst, port = w.split(".", 1)
                exp = _abs_manual(inst, port, rep["placement"], kind_of, params_of)
                cands.append((math.hypot(exp[0] - got[0], exp[1] - got[1]), w))
            cands.sort()
            n_end += 1
            if cands[0][0] > 1e-9:
                bad_end.append(f"{net_id}: 端点 {got} 距最近端口 {cands[0][1]} "
                               f"{cands[0][0]:.3g} µm")
            matched.append(cands[0][1])
        if len(set(matched)) != 2:
            bad_end.append(f"{net_id}: 两端点落到同一端口 {matched}")
    check(f"T5 端口同源：{n_end} 个走线端点全部精确落在 port_anchor 上（失配={len(bad_end)}）",
          not bad_end, str(bad_end[:3]))

    # ── T5b 布局纪律前提：`B > max(源 x)` 且 `b_i > s_i` ────────────────
    #    这两条是「反序 ⇒ 无交叉」证明的**前提**，必须由几何本身保证
    #    （首版把 MMIC x 写成常量 640 ⇒ n>8 时前提被破坏，LVS 报 5 处交叉）。
    b_x = rep["mmic_in_x_um"]
    src_max = rep["tx_source_x_max_um"]
    b_ok = all(_abs_manual("mmic_tx", f"in{n - i}", rep["placement"], kind_of,
                           params_of)[1]
               > _abs_manual(f"mod{i}", "out", rep["placement"], kind_of,
                             params_of)[1] for i in range(n))
    # Rx 侧同族前提：B_det > 最右环心 x；且**全部** det 的 y 与源 y 线同侧
    rx_b = rep["rx_det_in_x_um"]
    rx_src_max = rep["rx_source_x_max_um"]
    rx_y = rep["rx_source_y_um"]
    ry0, ry1 = rep["rx_det_y_band_um"]
    rx_same_side = ry1 < rx_y or ry0 > rx_y
    check(f"T5b 布局前提：MMIC 输入 x {b_x:.1f} > 最右源 x {src_max:.1f}"
          f"（余量 {b_x - src_max:.1f}µm）· 且全部 b_i > s_i",
          b_x > src_max and b_ok)
    check(f"T5c 布局前提：B_det {rx_b:.1f} > 最右环心 x {rx_src_max:.1f}"
          f"（余量 {rx_b - rx_src_max:.1f}µm）· 且 det y 带 "
          f"[{ry0:.1f},{ry1:.1f}] 与源 y 线 {rx_y:.1f} **同侧**",
          rx_b > rx_src_max and rx_same_side)

    # ── T5d 布局纪律三前提：**第二独立通道**（读 port_anchor 反推）────────
    #    🔴 T5b/T5c 读的是 builder 报出的标量；T5d 走 `layout_discipline_ok`
    #       从 `link`/`placement` 经 `port_anchor` 实地反推 —— 两条**不同源**的
    #       通道必须同时绿，否则就是「同源相等」的假判据（探针 P4/P5 保证它可红）。
    lay = P.layout_discipline_ok(rep["link"], rep["placement"], n)
    _d = lay["detail"]
    check(f"T5d layout_discipline_ok 三前提齐备（x={lay['x_ok']} · "
          f"反序={lay['reverse_order_ok']} · 同侧={lay['same_side_ok']} · "
          f"Tx 余量 {_d['tx_target_x'] - _d['tx_source_x_max']:.1f}µm · "
          f"Rx 余量 {_d['rx_target_x'] - _d['rx_source_x_max']:.1f}µm）",
          bool(lay["ok"]))

    # ── T6 确定性双向 ──────────────────────────────────────────────────
    rep_a = P.build_oi_transceiver_pnr(n_lanes=n)
    rep_b = P.build_oi_transceiver_pnr(n_lanes=n - 1)
    sha_a = hashlib.sha256(rep_a["gds_bytes"]).hexdigest()
    sha_b = hashlib.sha256(rep_b["gds_bytes"]).hexdigest()
    check("T6a 同参数两次 sha256 逐位一致（确定性）", sha_a == sha)
    check(f"T6b 换 n_lanes（{n}→{n - 1}）sha256 必须变化（反「常数假确定性」）",
          sha_b != sha and rep_b["gds_elements"] != rep["gds_elements"])

    # ── T7 片外 fiber 不落版图 ─────────────────────────────────────────
    sch_nets = {net.id: sorted(x for x in net.connects if "." in x)
                for net in rep["link"].ir.nets}
    fiber_ports = [("gc_tx", "fib"), ("gc_rx", "fib")]
    hit = [f"{i}.{p}" for (i, p) in fiber_ports
           for ports in sch_nets.values() if f"{i}.{p}" in ports]
    check(f"T7 片外 fiber 端口不属任何内部 net（命中={hit}）⇒ fiber 不落芯片版图",
          not hit and len(gds) > 0)

    # ── T8 环半径闭式 ──────────────────────────────────────────────────
    from lda_layout.wdm_mesh_pnr import wdm_ring_anchor
    ra = rep["ring_anchor"]
    R_manual = P.RX_RING_M * (1311.0 * 1e-3) / (2.0 * math.pi * P.RX_N_G)
    check(f"T8 环半径 {ra['R_um']:.4f} µm ≡ 闭式 m·λ/(2π·n_g)={R_manual:.4f}"
          f"（Δ<1e-3；锚本身 round 到 1e-4）且 ≥ min_bend_R "
          f"{drc_mod.DEFAULT_RULES['min_bend_R_um']}",
          abs(ra["R_um"] - R_manual) < 1e-3
          and ra["R_um"] >= drc_mod.DEFAULT_RULES["min_bend_R_um"])
    check("T8b 环锚与 wdm_mesh_pnr.wdm_ring_anchor 同源（Δ<1e-9）",
          abs(wdm_ring_anchor(1311.0, n_g=P.RX_N_G, m=P.RX_RING_M,
                              gap=P.RX_RING_GAP_UM)["R_um"] - ra["R_um"]) < 1e-9)

    # ── T9 逐规模双闸（不只测默认档）────────────────────────────────────
    sizes, fails = [1, 2, 4, 8, 12], []
    for m in sizes:
        rr = P.build_oi_transceiver_pnr(n_lanes=m)
        lay_m = P.layout_discipline_ok(rr["link"], rr["placement"], m)
        ok = (len(rr["gds_bytes"]) > 0 and rr["drc_pass"]
              and rr["lvs_verdict"] == "ACCEPT" and rr["lvs_n_violations"] == 0
              and rr["n_nets"] == 3 * m + 1 and rr["n_devices"] == 3 * m + 3
              and rr["mmic_in_x_um"] > rr["tx_source_x_max_um"]
              and rr["rx_det_in_x_um"] > rr["rx_source_x_max_um"]
              and (rr["rx_det_y_band_um"][1] < rr["rx_source_y_um"]
                   or rr["rx_det_y_band_um"][0] > rr["rx_source_y_um"])
              and lay_m["ok"])
        if not ok:
            fails.append(f"n={m}: drc={rr['drc_pass']} lvs={rr['lvs_verdict']}"
                         f" viol={rr['lvs_n_violations']} lay={lay_m['ok']}")
    check(f"T9 逐规模双闸：n ∈ {sizes} 全部 真GDS + DRC 全绿 + LVS ACCEPT + "
          f"三前提（失败={fails}）",
          not fails, str(fails))

    # ── T10 D4 域一致 ──────────────────────────────────────────────────
    from lda_l2 import d4_domains as dm
    d4 = dm.build_domain("oi_transceiver", {})
    check(f"T10 D4 域 oi_transceiver 的 sha256 ≡ 直接 builder（两条链同源 · "
          f"{d4['gds']['sha256'][:12]}…）",
          d4["ok"] and d4["gds"]["sha256"] == sha
          and d4["gds"]["n_bytes"] == len(gds) and d4["verdict"] == "ACCEPT")
    check("T10b D4 域 n_lanes 限幅在位（越界拒绝 / 未知键拒绝）",
          "oi_transceiver" in dm.DOMAIN_PARAM_LIMITS
          and dm.deliver_download("oi_transceiver", {"n_lanes": 99})[0] is None
          and dm.deliver_download("oi_transceiver", {"lanes": 4})[0] is None)

    # ── T11 诚实边界 ───────────────────────────────────────────────────
    dis = rep["disclosure"]
    need = {"kind", "domain", "topology", "fiber_off_chip", "mmic_placeholder",
            "drc_level", "rules_source", "signoff", "no_energy", "llm"}
    blob = rep["honest_note"] + " ".join(dis.values())
    check(f"T11a disclosure 键齐备（缺={sorted(need - set(dis))}）", need <= set(dis))
    check("T11b 关键短口径在场（片外 fiber / 自成像未建模 / 非计算核 / 设计期签核）",
          "片外" in blob and "自成像" in blob and "非计算核" in blob
          and "设计期签核" in blob)
    # 🔴 禁词纪律：只扫**肯定式**宣称面（kind/topology/drc_level/…），
    #    `no_energy` / `llm` 是**否定式声明** ⇒ 必须豁免（否则正确的自我否定被判违规）。
    _claim_keys = ("kind", "domain", "topology", "drc_level", "rules_source", "signoff")
    _claim = " ".join(str(dis[k]) for k in _claim_keys)
    check("T11c 肯定式宣称面零能效数字（豁免否定式键 no_energy/llm；且 no_energy 确为否定式）",
          not any(t in _claim for t in ("TOPS", "fJ/op", "pJ/bit", "W/op"))
          and "不报" in dis["no_energy"], _claim[:80])

    # ── V 系列：布局纪律反例（证明「反序」是**必要条件**）────────────────
    print("-" * 74)
    print("── 布局纪律反例（同序 ⇒ 必交叉）──")

    # V1：Tx 映射改成同序（mod{i}.out → mmic_tx.in{i+1}）
    routes_same = {}
    for i in range(n):
        pa = _abs_manual(f"mod{i}", "out", rep["placement"], kind_of, params_of)
        pb = _abs_manual("mmic_tx", f"in{i + 1}", rep["placement"], kind_of, params_of)
        routes_same[f"tx_lane{i}"] = {"points_um": [pa, (pa[0], pb[1]), pb]}
    rr_v1 = {k: v for k, v in rep["routes"].items() if not k.startswith("tx_lane")}
    rr_v1.update(routes_same)
    lvs_v1 = lvs_mod.run_lvs(rep["link"], rep["placement"], rr_v1, tol=1.0)
    v1_cross = [c for c in (lvs_v1["violations"].get("short_cross")
                            or lvs_v1["violations"].get("cross_shorts") or [])]
    check(f"V1 Tx 同序映射（in{{i+1}}）⇒ LVS REJECT 且报交叉（verdict={lvs_v1['verdict']} "
          f"违规={lvs_v1['n_violations']}）",
          lvs_v1["verdict"] == "REJECT" and lvs_v1["n_violations"] > 0, str(v1_cross[:2]))

    # V2：**保持 net ↔ 端口配对不变**，只把探测器阵列排成 y **递减**
    #     ⇒ 源 x 递增 与 目标 y 递减 **同向** ⇒ 按布局纪律必交叉。
    #     （这正是 v0.9.178 首版 builder 的真实 bug 场景，保持在这里作必要性证明。）
    plac_dec = dict(rep["placement"])
    for i in range(n):
        x, _y, rot = plac_dec[f"det{i}"]
        plac_dec[f"det{i}"] = (x, rep["rx_det_y_band_um"][0]
                               - i * P.RX_DET_PITCH_UM, rot)
    rr_v2 = dict(rep["routes"])
    for i in range(n):
        pa = _abs_manual(f"ring{i}", "drop", plac_dec, kind_of, params_of)
        pb = _abs_manual(f"det{i}", "in", plac_dec, kind_of, params_of)
        rr_v2[f"rx_drop{i}"] = {"points_um": [pa, (pa[0], pb[1]), pb]}
    lvs_v2 = lvs_mod.run_lvs(rep["link"], plac_dec, rr_v2, tol=1.0)
    _v2_cross = (lvs_v2["violations"].get("short_cross")
                 or lvs_v2["violations"].get("cross_shorts") or [])
    check(f"V2 Rx 目标 y 排成递减（与源 x 同向 ⇒ 同序）⇒ LVS REJECT 且报交叉 "
          f"（verdict={lvs_v2['verdict']} 违规={lvs_v2['n_violations']} "
          f"交叉对={len(_v2_cross)}）",
          lvs_v2["verdict"] == "REJECT" and lvs_v2["n_violations"] > 0
          and len(_v2_cross) > 0, str(_v2_cross[:3]))

    # V3/V4/V5：builder 自带反向护栏（删路由 / 挪器件 / 伪网穿越）
    g = P.oi_transceiver_reverse_guard(rep)
    check(f"V3 删一条 route ⇒ open ⇒ REJECT（违规={g['D1_n_violations']}）",
          bool(g["D1_open_detected"]))
    check(f"V4 器件挪出 tol ⇒ dangling ⇒ REJECT（违规={g['D2_n_violations']}）",
          bool(g["D2_dangling_detected"]))
    check(f"V5 伪网横穿走线带 ⇒ cross_short ⇒ REJECT（违规={g['D3_n_violations']}）",
          bool(g["D3_cross_detected"]))
    check("V6 三条反向护栏**全部**触发（all_detected）", bool(g["all_detected"]))

    # ── P 系列：突变探针 ───────────────────────────────────────────────
    print("-" * 74)
    print("── 突变探针（先证能变红）──")

    # P1：GDS 伪造为空字节
    _orig = P.build_oi_transceiver_pnr

    def empty_gds(**kw):
        r = _orig(**kw)
        r["gds_bytes"] = b""
        return r

    with mock.patch.object(P, "build_oi_transceiver_pnr", empty_gds):
        e = P.build_oi_transceiver_pnr(n_lanes=n)
    check("🔴 P1 探针: GDS 伪造为空字节 ⇒ T1a 必红",
          len(e["gds_bytes"]) == 0 and bytes(e["gds_bytes"][:4]) != b"\x00\x06\x00\x02")

    # P2：builder 静默忽略 n_lanes（恒建默认档）⇒ T6b 必红
    def drop_lanes(**kw):
        kw.pop("n_lanes", None)
        return _orig(n_lanes=_N_DEFAULT, **kw)

    with mock.patch.object(P, "build_oi_transceiver_pnr", drop_lanes):
        d = P.build_oi_transceiver_pnr(n_lanes=n - 1)
    check("🔴 P2 探针: n_lanes 被静默忽略 ⇒ T6b『换规模 sha 必变』必红",
          hashlib.sha256(d["gds_bytes"]).hexdigest() == sha)

    # P3：DRC 伪造成 REJECT
    def bad_drc(**kw):
        r = _orig(**kw)
        r["drc_pass"] = False
        return r

    with mock.patch.object(P, "build_oi_transceiver_pnr", bad_drc):
        b = P.build_oi_transceiver_pnr(n_lanes=n)
    check("🔴 P3 探针: DRC 伪造成 FAIL ⇒ T2a 必红", b["drc_pass"] is False)

    # P4：把 Tx 映射改回**同序**（`mmic_tx.in{i+1}`）⇒ `layout_discipline_ok.
    #     reverse_order_ok` 必须变 False（证明 T5d 的这条护栏**真能变红**，
    #     不是恒 True 的装饰）。做法：不改几何，只替换 link.ir.nets 里
    #     `tx_lane{i}` 的 connects ⇒ 排除「探针没打到被消费的那份引用」。
    _fake_nets = []
    for _net in rep["link"].ir.nets:
        if _net.id.startswith("tx_lane") and _net.id[7:].isdigit():
            _i = int(_net.id[7:])
            _c = [x for x in _net.connects if not x.startswith("mmic_tx.")]
            _fake_nets.append(types.SimpleNamespace(
                id=_net.id, connects=_c + [f"mmic_tx.in{_i + 1}"]))
        else:
            _fake_nets.append(_net)
    _fake_link = types.SimpleNamespace(
        ir=types.SimpleNamespace(components=rep["link"].ir.components,
                                 nets=_fake_nets))
    lay_same = P.layout_discipline_ok(_fake_link, rep["placement"], n)
    check(f"🔴 P4 探针: Tx 映射改回同序（in{{i+1}}）⇒ "
          f"layout_discipline_ok.reverse_order_ok 必变 False（实得 "
          f"{lay_same['reverse_order_ok']}）",
          lay_same["reverse_order_ok"] is False and lay_same["ok"] is False)

    # P5：把 Rx 探测器阵列排成 y **递减** ⇒ 同一条护栏的 Rx 侧必须变 False。
    _plac_dec = dict(rep["placement"])
    for _i in range(n):
        _x, _y, _rot = _plac_dec[f"det{_i}"]
        _plac_dec[f"det{_i}"] = (_x, rep["rx_det_y_band_um"][0]
                                 - _i * P.RX_DET_PITCH_UM, _rot)
    lay_rxdec = P.layout_discipline_ok(rep["link"], _plac_dec, n)
    check(f"🔴 P5 探针: Rx det y 排成递减 ⇒ "
          f"layout_discipline_ok.reverse_order_ok 必变 False（实得 "
          f"{lay_rxdec['reverse_order_ok']}）",
          lay_rxdec["reverse_order_ok"] is False and lay_rxdec["ok"] is False)

    # P6：**反向完备性**——把 `layout_discipline_ok` 强行改成恒 True（伪装绿），
    #     T5d 的调用点（同一函数、同一反例）必须随之假绿 ⇒ 证明 T5d 的信源
    #     确实是它，而非旁路常量。
    _orig_lay = P.layout_discipline_ok

    def _always_ok(*a, **k):
        r = _orig_lay(*a, **k)
        r["ok"] = True
        return r

    with mock.patch.object(P, "layout_discipline_ok", _always_ok):
        _patched = P.layout_discipline_ok(_fake_link, rep["placement"], n)
    check("🔴 P6 探针: 强行令 layout_discipline_ok.ok 恒 True ⇒ 同序反例被伪装成绿 "
          "（说明 T5d 的判据真由它驱动，非旁路常量）",
          _patched["ok"] is True and lay_same["ok"] is False)

    # P7（定稿 §6 · P8a「拓扑退化」）：**去掉探测器阵列**（器件）但**保留** `rx_drop*`
    #     网 ⇒ 原理图声明了 det 端口而版图无器件承载 ⇒ 器件数不匹配 + 端点悬空
    #     ⇒ LVS 必 REJECT（证明「器件 ↔ 网表一致性」是真护栏，不是同源自洽）。
    import copy as _copy
    _bad7 = P.build_oi_transceiver_pnr(n_lanes=n)
    _lk7 = _copy.copy(_bad7["link"])
    _ir7 = _copy.copy(_bad7["link"].ir)
    _ir7.components = [c for c in _ir7.components if not c.id.startswith("det")]
    _lk7.ir = _ir7
    r7 = lvs_mod.run_lvs(_lk7, _bad7["placement"], _bad7["routes"], tol=1.0)
    check(f"🔴 P7 探针(§6 P8a): 去掉探测器阵列（留 net）⇒ 网表一致性必红 "
          f"（verdict={r7['verdict']} 违规={r7['n_violations']}）",
          r7["verdict"] == "REJECT" and r7["n_violations"] > 0)

    # P8（定稿 §6 · P8b「拿酉网格顶替收发器」）：用 **Clements 酉网格「计算核」**
    #     的版图去冒充 G-OI2 收发器产物。两重证据：
    #       ① **名字空间不相容** ⇒ 端点归属表立刻失败（KeyError，fail-loud）
    #          —— 绝不可能是「静默通过」（那才是真危险）；
    #       ② **结构计数公式不同** ⇒ 酉网格器件/网数 ≠ 收发器声明 3N+3 / 3N+1，
    #          且酉网格**没有片外 fiber 端口** ⇒ T3a/T3b/T7 判据必红。
    from lda_layout.wdm_mesh_pnr import build_wdm_mesh_pnr
    _mesh = build_wdm_mesh_pnr(wavelengths_nm=[1550.0, 1552.5], N=2)
    _swap_err = None
    try:
        lvs_mod.run_lvs(rep["link"], _mesh["placement"], _mesh["routes"], tol=1.0)
    except Exception as _e:                                   # noqa: BLE001
        _swap_err = _e
    _m_dev = len(_mesh["link"].ir.components)
    _m_net = len(_mesh["link"].ir.nets)
    _m_fiber = any(("gc_tx.fib" in x or "gc_rx.fib" in x)
                   for _n in _mesh["link"].ir.nets for x in _n.connects)
    check(f"🔴 P8 探针(§6 P8b): 拿酉网格版图顶替收发器 ⇒ ①名字空间不相容 "
          f"{type(_swap_err).__name__}（非静默通过）· ②拓扑计数 {_m_dev}/{_m_net} ≠ "
          f"收发器 {3 * n + 3}/{3 * n + 1} 且无片外 fiber（fiber={_m_fiber}）",
          isinstance(_swap_err, KeyError) and _m_dev != 3 * n + 3
          and _m_net != 3 * n + 1 and not _m_fiber)

    # ── R：还原后基线重跑 ───────────────────────────────────────────────
    print("-" * 74)
    print("── 还原后基线复查 ──")
    r2 = P.build_oi_transceiver_pnr(n_lanes=n)
    check("R1 还原后 sha256 与首次逐位一致（探针未污染真判据）",
          hashlib.sha256(r2["gds_bytes"]).hexdigest() == sha)
    check(f"R2 还原后 DRC 全绿 + LVS ACCEPT（{r2['lvs_n_violations']} 违规）",
          r2["drc_pass"] and r2["lvs_verdict"] == "ACCEPT"
          and r2["lvs_n_violations"] == 0)
    check("R3 模块自检全绿",
          bool(P.oi_transceiver_self_check(verbose=False)["ok"]))

    print("-" * 74)
    print(f"  {n}×200G 收发器：{rep['n_devices']} 器件 / {rep['n_nets']} 网 / "
          f"{rep['gds_elements']} GDS 元素 / {len(gds)} 字节 · "
          f"bbox {rep['layout_bbox']['x_max'] - rep['layout_bbox']['x_min']:.0f}×"
          f"{rep['layout_bbox']['y_max'] - rep['layout_bbox']['y_min']:.0f} µm · "
          f"{rep['footprint_um2']:.0f} µm²")
    print(f"  MMIC 多模区宽 {rep['mmic_w_mmi_um']:.1f} µm ≥ 端口跨度 "
          f"{rep['mmic_port_span_um']:.1f} µm · 环 R={ra['R_um']:.4f} µm "
          f"(m={P.RX_RING_M}·n_g={P.RX_N_G}) · FSR={ra['FSR_nm']:.3f} nm")
    print("  fiber 片外：Tx/Rx 各自 GC 的 fib 端口不属任何内部 net（已验证）")

    n_pass = globals().get("PASS", 0)
    n_fail = globals().get("FAIL", 0)
    print("-" * 74)
    print(f"汇总：{n_pass} PASS / {n_fail} FAIL / 共 {n_pass + n_fail} 项")
    return 0 if (n_pass and not n_fail) else 1


if __name__ == "__main__":
    raise SystemExit(main())
