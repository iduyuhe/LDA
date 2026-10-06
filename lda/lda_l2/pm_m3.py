# -*- coding: utf-8 -*-
"""PM-M3：单元/多电平 → **阵列版图**（真 GDS + DRC/LVS 签核）· 光子存储征程第五程第三档。

定位
----
M0 给「一个单元能不能写」、M1 给「能装几个电平」、M2 给「热与保持是否站得住」，
但三者都停在**标量设计**层面 —— 没有一张可交付的**版图**。M3 把三者落到
「可排布、可签核、可下载」的阵列版图上，并接 WebUI 案例卡（此前 PM 无 UI 入口）。

本档回答三问
------------
1. **单元落到几何**：Si 波导 + GST 相变段 + 双侧微加热器 + 四个电极 pad
   （新器件原语 `PCMCell`，五处契约同步：primitives / placement.port_anchor /
   placement.device_bbox / link_model._DEFAULT_PORTS / drc）。
2. **阵列怎么排**：`1×N` 串行总线阵列 + `R×C` 多总线阵列；光学 IO 经**引出波导**
   接到光栅耦合器（避免光栅与电 pad 几何打架）；单元间距取
   **max(热串扰隔离间距, 工艺间隙)**。
3. **排出来的东西站不站得住**：真 GDSII + 几何 DRC + LVS，且**判决不读生成端结论**
   —— 由自写的最小 GDSII 记录流解析器**从最终字节独立解码**复核结构。

🔴 与上游的**同源**（判据读「算出来的值」）
--------------------------------------------
- 单元光程长 `L`：读 `pm_m1.m1_report()["demo_design_point"]["l_mid_um"]`（M1 设计点）。
- 单元电平数：读 `pm_m1` 的 `n_levels`（4 bit/单元）。
- **单元间最小间距**：`k_iso × L_max`，`L_max` 读 `pm_m2.max_quench_thickness()`
  的热扩散口径上界（非晶相）—— 即「相邻单元的热扰动不得越过隔离倍数」。
- 单元双态插损：读 `pm_m0.cell_state()`（**含 Γ 假设**，一律区间口径）。
⇒ 阵列的任何规模数字都可由上游模块重算，**M3 不复制任何物理常数**。

🔴 诚实边界
-----------
- 全部为**设计期签核**（版图 + DRC/LVS + 预算），**非流片、非实测**。
- DRC 限值是**自建设计规则**（公开工艺近似 + 探针接触常识），**非 foundry PDK deck**。
- 热隔离倍数 `k_iso` 是**设计选择**（不是物理常数）：它决定「多大间距才认为热不串」，
  属设计者显式声明的规格；本模块**并报** L_max 的两个口径（扩散 / 集总 RC）。
- 阵列总插损是**串行累加**（N × 单元 IL），不含单元间连接波导的传播损耗
  （该损耗无本项目锚 ⇒ 不编数）。
- 🔴 **不报 pJ/bit、fJ/op、TOPS、TOPS-W 类能效指标**（红线）。
- LLM 不进判决路径：判据全为死标量 / 结构断言。
"""
from __future__ import annotations

import hashlib
import math
import struct
from typing import Any, Dict, List, Optional, Tuple

from lda_l2 import pm_m0 as M0
from lda_l2 import pm_m1 as M1
from lda_l2 import pm_m2 as M2
from lda_l2 import primitives as PR

#: 热隔离倍数（**设计选择** · 不是物理常数）：相邻单元间距 = k_iso × L_max(热扩散)。
#: 含义 = 「热扰动在传播 k_iso 个扩散长度后视为不可忽略地小」。取 8 由保密余量出发，
#: 属设计者声明的规格；改它会改版图（本模块并报两个 L_max 口径，不假装它是真值）。
K_ISOLATION_DEFAULT: float = 8.0
#: 工艺间隙下限（µm）：即使热学允许更近，也要给「pad 外扩 + 刻蚀偏差」留位置。
#: = pad 边长 + 2 µm（pad 两侧各留 1 µm 余量）。
PROCESS_GAP_MARGIN_UM: float = 2.0
#: IO 引出波导长度 / 引出段到首单元的直连长度（µm）—— 让光栅耦合器远离电极 pad。
IO_WG_LEN_UM: float = 20.0
IO_LEAD_UM: float = 10.0
#: 多总线阵列的行间距（µm）：必须 > 光栅耦合器纵向高度（10 µm）+ pad 半高（~3.1 µm）。
BUS_PITCH_UM: float = 16.0

#: 阵列规模档（每档都真跑 P&R + GDS + DRC/LVS）
SCALE_TIERS: Tuple[Tuple[int, int], ...] = ((1, 4), (1, 8), (1, 16), (1, 32), (4, 8))


class PMM3Error(Exception):
    """PM-M3 域错误（越域 = 模型失效，拒绝静默截断）。"""


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise PMM3Error(msg)


# ═══════════════════════════ 1. 上游同源取值 ═══════════════════════════
def cell_length_um() -> Dict[str, Any]:
    """单元光程长（**读 M1 设计点**，不硬编码）。"""
    rep = M1.m1_report()
    d = rep["demo_design_point"]
    return {"l_um": float(d["l_mid_um"]), "source": d["source"],
            "spacing_frac": float(d["spacing_frac"]),
            "spacing_ok": bool(d["spacing_ok"]),
            "worst_ber": float(d["worst_ber"])}


def n_levels_upstream() -> Dict[str, Any]:
    """单元电平数（**读 M1**）。"""
    rep = M1.m1_report()
    f = rep["feasibility"]
    n = int(f["n_levels"])
    _require(n >= 2, "电平数必须 ≥ 2")
    bits = int(round(math.log2(n)))
    return {"n_levels": n, "bits_per_cell": bits}


def thermal_min_gap_um(mat: str = "GST",
                       k_iso: float = K_ISOLATION_DEFAULT) -> Dict[str, Any]:
    """热串扰隔离所需的最小单元间距（**由 M2 的热扩散长度算出**）。

    `L_max` 是「可非晶化最大膜厚」的热扩散口径上界 —— 在本语境里它就是
    「一次写脉冲的热扰动特征长度」。相邻单元间距 < `k_iso·L_max` 时，写入
    一个单元会扰动邻居的相态（多电平存储里即误码）。
    """
    _require(k_iso > 0.0, "k_iso 必须为正")
    q = M2.max_quench_thickness(mat)
    l_diff = float(q["l_max_diff_max_m"]) * 1e6      # m → µm
    l_rc = float(q["l_max_rc_max_m"]) * 1e6
    return {"material": mat, "k_iso": float(k_iso),
            "l_max_diff_um": l_diff, "l_max_rc_um": l_rc,
            "min_gap_um": k_iso * l_diff,
            "min_gap_um_rc_basis": k_iso * l_rc,
            "basis": "k_iso × L_max（热扩散口径上界）· k_iso 为设计选择",
            "literature_l_ref_um": float(q["literature_l_ref_m"]) * 1e6}


def cell_pitch_um(mat: str = "GST", pad_um: Optional[float] = None,
                  k_iso: float = K_ISOLATION_DEFAULT) -> Dict[str, Any]:
    """单元排布 pitch（µm）= 光程长 + max(热隔离间距, 工艺间隙)。"""
    p = dict(PR.PCM_CELL_DEFAULTS)
    if pad_um is not None:
        p["pad"] = float(pad_um)
    L = cell_length_um()["l_um"]
    th = thermal_min_gap_um(mat, k_iso)
    gap_proc = p["pad"] + PROCESS_GAP_MARGIN_UM
    gap = max(th["min_gap_um"], gap_proc)
    return {"l_cell_um": L, "gap_um": gap,
            "gap_thermal_um": th["min_gap_um"], "gap_process_um": gap_proc,
            "binding": "thermal" if th["min_gap_um"] >= gap_proc else "process",
            "pad_um": p["pad"], "pitch_um": L + gap, "thermal": th}


# ═══════════════════════════ 2. P&R（阵列构建）═══════════════════════════
def build_array(n_cells: int, n_buses: int = 1, mat: str = "GST",
                k_iso: float = K_ISOLATION_DEFAULT) -> Dict[str, Any]:
    """构建 `n_buses × n_cells` 串行总线阵列（LinkModel + placement + routes）。

    每条总线的器件序（**IO 引出波导是关键设计**）::

        gc_in(Waveguide) → c1 → c2 → … → cN → gc_out(Waveguide)

    引出波导把「光栅耦合器的落位」推到远离电极 pad 的地方 —— 否则光栅齿区
    （沿 y 伸出 ~10 µm）会与首单元的 h1/h2 pad 几何打架。
    """
    from lda_chain.link_model import LinkModel
    from lda_layout.placement import port_abs

    _require(int(n_cells) >= 1, "n_cells 必须 ≥ 1")
    _require(int(n_buses) >= 1, "n_buses 必须 ≥ 1")
    n_cells, n_buses = int(n_cells), int(n_buses)
    pit = cell_pitch_um(mat, k_iso=k_iso)
    L = pit["l_cell_um"]
    pitch = pit["pitch_um"]
    p = dict(PR.PCM_CELL_DEFAULTS)
    p["length"] = L

    link = LinkModel(domain="photon", name="pm_m3_array_%dx%d" % (n_buses, n_cells))
    placement: Dict[str, Tuple[float, float, float]] = {}
    routes: Dict[str, Dict[str, Any]] = {}
    per_bus: List[Dict[str, Any]] = []

    for b in range(n_buses):
        y = b * BUS_PITCH_UM
        gin = "b%d_gc_in" % b
        gout = "b%d_gc_out" % b
        cells = ["b%d_c%d" % (b, i) for i in range(n_cells)]
        link.add_device(gin, "Waveguide", {"length": IO_WG_LEN_UM, "width": 0.5})
        for cid in cells:
            link.add_device(cid, "PCMCell", dict(p))
        link.add_device(gout, "Waveguide", {"length": IO_WG_LEN_UM, "width": 0.5})

        # 摆放：引出波导的 out 指向首单元 in（x=0），单元按 pitch 排开
        x_gc_in = -(IO_WG_LEN_UM + IO_LEAD_UM)
        placement[gin] = (x_gc_in, y, 0.0)
        for i, cid in enumerate(cells):
            placement[cid] = (i * pitch, y, 0.0)
        x_gc_out = (n_cells - 1) * pitch + L + IO_LEAD_UM
        placement[gout] = (x_gc_out, y, 0.0)

        # 网表：光通路（net_id 必须与 route key 逐字一致 —— LVS 硬契约）
        link.connect("b%d_io_in" % b, gin, "out", cells[0], "in")
        for i in range(n_cells - 1):
            link.connect("b%d_n%d" % (b, i + 1), cells[i], "out", cells[i + 1], "in")
        link.connect("b%d_io_out" % b, cells[-1], "out", gout, "in")
        link.external_io("b%d_io_in_ext" % b, gin, "in")
        link.external_io("b%d_io_out_ext" % b, gout, "out")

        routes["b%d_io_in" % b] = {"points_um": [
            port_abs(gin, "out", placement, link), port_abs(cells[0], "in", placement, link)]}
        for i in range(n_cells - 1):
            routes["b%d_n%d" % (b, i + 1)] = {"points_um": [
                port_abs(cells[i], "out", placement, link),
                port_abs(cells[i + 1], "in", placement, link)]}
        routes["b%d_io_out" % b] = {"points_um": [
            port_abs(cells[-1], "out", placement, link),
            port_abs(gout, "in", placement, link)]}

        per_bus.append({
            "bus": b, "y_um": y, "n_cells": n_cells,
            "devices": [gin] + cells + [gout],
            "span_x_um": round(x_gc_out + IO_WG_LEN_UM - x_gc_in, 4),
        })

    return {"link": link, "placement": placement, "routes": routes,
            "n_cells": n_cells, "n_buses": n_buses,
            "n_cells_total": n_cells * n_buses,
            "pitch": pit, "per_bus": per_bus,
            "params": p}


# ═══════════════════════ 3. 导出 + 独立复核（GDS 字节）═══════════════════
#: 默认 DRC 规则（设计规则 · 非 foundry PDK deck）
DEFAULT_DRC_RULES: Dict[str, float] = {
    "min_width_um": 0.30, "min_space_um": 0.20,
    "min_bend_R_um": 5.0, "max_split_angle_deg": 30.0, "min_pad_um": 2.0,
}


def export_array_gds(arr: Dict[str, Any], rules: Optional[Dict[str, float]] = None
                     ) -> Dict[str, Any]:
    """阵列 → 真 GDSII + DRC + LVS（**flat 导出**：见下方为何不层次化）。"""
    from lda_l2 import chip_layout_export as CLE

    link, placement, routes = arr["link"], arr["placement"], arr["routes"]
    res = CLE.export_chip_gds(link, placement, routes, wg_width=0.5,
                              rules=dict(rules or DEFAULT_DRC_RULES),
                              with_hierarchy=False)
    return res


def independent_gds_scan(gds: bytes) -> Dict[str, Any]:
    """🔴 **独立**最小 GDSII 记录流解析器（**刻意不复用** `gds_export` 解码器）。

    只解本层复核需要的记录：BGNSTR(0x05) / BOUNDARY(0x08) / PATH(0x09) /
    SREF(0x0A) / AREF(0x0B) / LAYER(0x0D) / WIDTH(0x0F) / XY(0x10, INT4) /
    ENDEL(0x11) / ENDSTR(0x07)。坐标 DBU→µm（1 DBU = 1 nm，与 GDS UNITS 同口径）。

    **为何自写**：若复用编码器所在模块的解码器，判据读到的仍是**同源派生量**
    ⇒ 假判据高发区（本项目血案同族：`_pdn_lvs` 硬编码 True）。这里从**最终字节**
    独立解出「层 × 元素」分布，与生成端**零共享代码**。

    返回 `{"n_structures", "n_elements", "layers": {layer: n}, "by_kind": {...},
           "n_sref", "n_aref", "total_length_um"}`
    """
    if not isinstance(gds, (bytes, bytearray)):
        raise PMM3Error("GDS 必须是字节流")
    n = len(gds)
    dbu = 1e-3
    i = 0
    n_struct = 0
    n_elem = 0
    layers: Dict[int, int] = {}
    by_kind: Dict[str, int] = {"boundary": 0, "path": 0, "sref": 0, "aref": 0}
    total_len = 0.0
    cur_layer: Optional[int] = None
    cur_kind: Optional[str] = None
    cur_pts: Optional[List[Tuple[float, float]]] = None
    saw_endlib = False
    while i + 4 <= n:
        (ln,) = struct.unpack_from(">H", gds, i)
        if ln < 4 or i + ln > n:
            raise PMM3Error("GDS 记录长度越界（偏移 %d · 长度 %d）" % (i, ln))
        rt = gds[i + 2]
        payload = gds[i + 4:i + ln]
        if rt == 0x04:                         # ENDLIB ⇒ 记录流完整
            saw_endlib = True
        elif rt == 0x05:
            n_struct += 1
        elif rt == 0x08:
            cur_kind, cur_layer, cur_pts = "boundary", None, None
        elif rt == 0x09:
            cur_kind, cur_layer, cur_pts = "path", None, None
        elif rt == 0x0A:
            cur_kind, cur_layer, cur_pts = "sref", None, None
        elif rt == 0x0B:
            cur_kind, cur_layer, cur_pts = "aref", None, None
        elif rt == 0x0D:
            cur_layer = int(struct.unpack_from(">h", payload, 0)[0])
        elif rt == 0x10:
            cnt = len(payload) // 4
            vals = struct.unpack_from(">%di" % cnt, payload)
            cur_pts = [(vals[j] * dbu, vals[j + 1] * dbu) for j in range(0, cnt, 2)]
        elif rt == 0x11:                       # ENDEL
            if cur_kind in ("boundary", "path") and cur_layer is not None:
                n_elem += 1
                layers[cur_layer] = layers.get(cur_layer, 0) + 1
                by_kind[cur_kind] = by_kind.get(cur_kind, 0) + 1
                if cur_kind == "path" and cur_pts:
                    for k in range(len(cur_pts) - 1):
                        total_len += math.hypot(cur_pts[k + 1][0] - cur_pts[k][0],
                                                cur_pts[k + 1][1] - cur_pts[k][1])
            elif cur_kind in ("sref", "aref"):
                by_kind[cur_kind] = by_kind.get(cur_kind, 0) + 1
            cur_kind, cur_layer, cur_pts = None, None, None
        i += ln
    # 🔴 完整性：必须真的走到 ENDLIB(0x04)，否则字节流被截断/畸形 ⇒ 拒绝
    #    「解析到一半就当成功」（本项目血案同族：静默截断）。
    if not saw_endlib:
        raise PMM3Error("GDS 记录流不完整：未见 ENDLIB（长度 %d 字节）" % n)
    return {"n_structures": n_struct, "n_elements": n_elem,
            "layers": {int(k): int(v) for k, v in sorted(layers.items())},
            "by_kind": by_kind, "n_sref": by_kind.get("sref", 0),
            "n_aref": by_kind.get("aref", 0),
            "total_length_um": total_len}


def expected_layer_counts(arr: Dict[str, Any]) -> Dict[str, Any]:
    """生成端**声明**的层元素计数（与独立解码结果比对 —— 不一致必红）。"""
    from lda_l2 import gds_export as GX

    n_cells = arr["n_cells_total"]
    n_bus = arr["n_buses"]
    n_cell_dev = n_cells
    n_wg = 2 * n_bus
    n_nets = arr["n_buses"] * (arr["n_cells"] + 1)
    # 每单元：1 GST 矩形（层 PCM）+ 2 加热线 + 4 pad（层 HEATER）
    return {"PCM": n_cell_dev,
            "HEATER": 6 * n_cell_dev,
            "SI_devices": n_cell_dev + n_wg,       # 每器件 1 条 Si path
            "SI_routes": n_nets,                   # 每条 net 1 条 route path（空网除外）
            "layers_expected": {
                int(GX.LIB_LAYER_PCM): n_cell_dev,
                int(GX.LIB_LAYER_HEATER): 6 * n_cell_dev,
            },
            "n_nets": n_nets, "n_devices": n_cell_dev + n_wg}


def layout_signoff(arr: Dict[str, Any], rules: Optional[Dict[str, float]] = None
                   ) -> Dict[str, Any]:
    """阵列签核：真 GDS + DRC + LVS + **从字节独立解码**的结构复核。"""
    res = export_array_gds(arr, rules=rules)
    gds = res["gds_bytes"]
    scan = independent_gds_scan(gds)
    exp = expected_layer_counts(arr)
    from lda_l2 import gds_export as GX

    got_pcm = scan["layers"].get(int(GX.LIB_LAYER_PCM), 0)
    got_heat = scan["layers"].get(int(GX.LIB_LAYER_HEATER), 0)
    # Si 层可能出现空 path（历史行为：每条 net 无条件产出一条 path）⇒ 只断言 ≥
    got_si = scan["layers"].get(int(GX.LIB_LAYER_SI), 0)

    lvs = res["lvs_report"]
    drc = res["drc_report"]
    checks = {
        "drc_all_pass": bool(drc["all_pass"]),
        "lvs_accept": bool(lvs["verdict"] == "ACCEPT" and lvs["n_violations"] == 0),
        "pcm_layer_exact": bool(got_pcm == exp["PCM"]),
        "heater_layer_exact": bool(got_heat == exp["HEATER"]),
        "si_layer_at_least_devices": bool(got_si >= exp["SI_devices"]),
        "no_hierarchy_refs": bool(scan["n_sref"] == 0 and scan["n_aref"] == 0),
        "single_structure": bool(scan["n_structures"] == 1),
    }
    return {
        "gds_bytes": gds,                     # 原始字节（供货架脚本落盘；不参与 JSON）
        "gds_bytes_len": len(gds),
        "gds_sha256": hashlib.sha256(gds).hexdigest(),
        "gds_stats": res["gds_stats"],
        "independent_scan": scan,
        "expected": exp,
        "checks": checks,
        "all_pass": all(checks.values()),
        "drc_report": drc,
        "lvs_report": lvs,
        "io_ports": res.get("io_ports", []),
    }


# ═══════════════════════════ 4. 设计预算（阵列级）═══════════════════════════
def array_budget(arr: Dict[str, Any], mat: str = "GST") -> Dict[str, Any]:
    """阵列设计预算（全部由上游模块现算；不含单元间连接波导损耗）。"""
    L = arr["pitch"]["l_cell_um"]
    n_tot = arr["n_cells_total"]
    n_lev = n_levels_upstream()
    cell = M0.cell_two_state(mat, l_um=L)          # 含 Γ 假设 ⇒ 区间口径
    # 单元总插损（两态）：直接读 M0 的 il_db（区间）
    st_a = M0.cell_state(mat, "amorphous", l_um=L)
    st_c = M0.cell_state(mat, "crystalline", l_um=L)
    il_a = (float(st_a["il_db_min"]), float(st_a["il_db_max"]))
    il_c = (float(st_c["il_db_min"]), float(st_c["il_db_max"]))
    return {
        "material": mat,
        "n_cells_total": n_tot,
        "l_cell_um": L,
        "single_cell_il_db": {"amorphous": list(il_a), "crystalline": list(il_c)},
        "single_cell_contrast_db": [float(cell["contrast_min_db"]),
                                    float(cell["contrast_max_db"])],
        "array_il_db": {"amorphous": [n_tot * il_a[0], n_tot * il_a[1]],
                        "crystalline": [n_tot * il_c[0], n_tot * il_c[1]]},
        "n_levels": n_lev["n_levels"], "bits_per_cell": n_lev["bits_per_cell"],
        "array_states": n_tot * n_lev["n_levels"],
        "array_bits": n_tot * n_lev["bits_per_cell"],
        "n_electrode_pads": 4 * n_tot,
        "n_heater_lines": 2 * n_tot,
        "il_model": "serial_sum(N × single_cell_il)；不含单元间连接波导传播损耗（无锚）",
        "gamma_note": "单元 IL 含 Γ **假设 0.05**（Γ 已有自研场求解标定 pm_gamma≈0.084 ⇒ PM-G2 v0.9.198 结算）；🔴 L ∝ 1/Γ ⇒ 本档版图按假设出图，标定口径下设计点**越窗**须重标定（PM-G11 开放 · 两口径并报）⇒ 一律**区间**口径，非单值",
        "contrast_reuse_note": "contrast 与 IL 来自同一 M0 双层调用（避免二次来源）",
    }


# ═══════════════════════════ 5. 汇总报告 ═══════════════════════════
def scale_table(mat: str = "GST", tiers: Optional[Tuple[Tuple[int, int], ...]] = None
                ) -> List[Dict[str, Any]]:
    """规模档：每档**真跑** P&R + GDS + DRC/LVS + 独立复核。"""
    out = []
    for (nb, nc) in (tiers or SCALE_TIERS):
        arr = build_array(nc, n_buses=nb, mat=mat)
        so = layout_signoff(arr)
        st = so["gds_stats"]
        out.append({
            "bus_x_cells": "%dx%d" % (nb, nc),
            "n_buses": nb, "n_cells_per_bus": nc, "n_cells_total": arr["n_cells_total"],
            "n_devices": st["n_devices"], "n_nets": st["n_nets"],
            "n_elements": st["n_elements"], "gds_bytes": so["gds_bytes_len"],
            "area_um2": st["area_um2"], "width_um": st["width_um"],
            "height_um": st["height_um"],
            "drc_pass": so["checks"]["drc_all_pass"],
            "lvs": so["lvs_report"]["verdict"],
            "lvs_violations": so["lvs_report"]["n_violations"],
            "independent_ok": so["all_pass"],
            "expected_pcm": so["expected"]["PCM"],
            "got_pcm": so["independent_scan"]["layers"].get(5, 0),
        })
    return out


def m3_report(mat: str = "GST") -> Dict[str, Any]:
    """PM-M3 总报告（阵列版图 + 签核 + 预算 + 规模档）。"""
    pit = cell_pitch_um(mat)
    arr = build_array(8, n_buses=1, mat=mat)
    so = layout_signoff(arr)
    bud = array_budget(arr, mat=mat)
    return {
        "milestone": "PM-M3 · 阵列版图（真 GDS + DRC/LVS + 独立解码复核）",
        "material": mat,
        "device": {
            "kind": "PCMCell",
            "structure": "Si 波导 + GST 相变段 + 双侧微加热器 + 4 电极 pad",
            "layers": {"SI": 1, "PCM": 5, "HEATER": 6},
            "ports": ["in", "out", "h1", "h2", "h3", "h4"],
            "drc_checks": ["min_width", "min_space", "min_pad"],
        },
        "upstream": {
            "cell_length": cell_length_um(),
            "levels": n_levels_upstream(),
            "thermal": thermal_min_gap_um(mat),
        },
        "pitch": pit,
        "array_8x1": {
            "n_devices": so["gds_stats"]["n_devices"],
            "n_nets": so["gds_stats"]["n_nets"],
            "n_elements": so["gds_stats"]["n_elements"],
            "area_um2": so["gds_stats"]["area_um2"],
            "signoff": {k: so[k] for k in ("gds_bytes_len", "gds_sha256", "checks",
                                           "all_pass", "independent_scan")},
        },
        "signoff_checks": so["checks"],
        "budget": bud,
        "scale_tiers": scale_table(mat),
        "disclosure": {
            "layer": "设计期签核（版图 + DRC/LVS + 预算）",
            "no_foundry_truth": True,
            "no_project_measurement": True,
            "drc_rules_are_design_rules": True,
            "k_iso_is_design_choice": True,
            "flat_export": "阵列以 flat 导出（不做层次化压缩）⇒ 独立解码器逐元素复核",
            "no_efficiency_metric_reported": True,
            "llm_not_in_decision_path": True,
        },
    }


# ═══════════════════════════ 6. 自检 ═══════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检（门禁同源调用）。全部为「算出来的」断言，不读字面量。"""
    res: Dict[str, bool] = {}
    msgs: List[str] = []

    def chk(name: str, cond: bool) -> None:
        res[name] = bool(cond)
        msgs.append("%s | %s" % ("PASS" if cond else "FAIL", name))

    # ① 单元长读 M1（同源）：与 M1 报告逐位相等
    cl = cell_length_um()
    m1d = M1.m1_report()["demo_design_point"]
    chk("① 单元光程长同源 M1（现算 == M1 demo）",
        abs(cl["l_um"] - float(m1d["l_mid_um"])) < 1e-12 and cl["spacing_ok"])

    # ② 热隔离间距 = k_iso × L_max（读 M2，逐位复算）
    th = thermal_min_gap_um("GST")
    m2q = M2.max_quench_thickness("GST")
    chk("② 热隔离间距 ≡ k_iso × L_max（M2 热扩散口径 · 逐位）",
        abs(th["min_gap_um"] - K_ISOLATION_DEFAULT * float(m2q["l_max_diff_max_m"]) * 1e6) < 1e-12)

    # ③ pitch = L + max(热, 工艺)，且 binding 与两者大小一致（**算出来的**）
    pit = cell_pitch_um("GST")
    want_bind = "thermal" if pit["gap_thermal_um"] >= pit["gap_process_um"] else "process"
    chk("③ pitch 派生自 max(热隔离, 工艺间隙) 且 binding 与实算一致",
        abs(pit["pitch_um"] - (pit["l_cell_um"] + max(pit["gap_thermal_um"],
                                                      pit["gap_process_um"]))) < 1e-12
        and pit["binding"] == want_bind)

    # ④ 器件层号跨源一致（primitives ↔ gds_export —— 防静默失配）
    from lda_l2 import gds_export as GX
    chk("④ 层号跨源一致（primitives._LAYER_PCM/HEATER == gds_export.LIB_LAYER_*）",
        int(PR._LAYER_PCM) == int(GX.LIB_LAYER_PCM)
        and int(PR._LAYER_HEATER) == int(GX.LIB_LAYER_HEATER)
        and int(PR._LAYER_SI) == int(GX.LIB_LAYER_SI))

    # ⑤ 独立解码器 ≠ 编码器：同一 GDS 的层计数 == 生成端声明（8 单元）
    arr = build_array(8, n_buses=1)
    so = layout_signoff(arr)
    chk("⑤ 独立解码层计数 == 生成端声明（PCM 8 / HEATER 48）· 且 DRC/LVS 双绿",
        so["checks"]["pcm_layer_exact"] and so["checks"]["heater_layer_exact"]
        and so["checks"]["drc_all_pass"] and so["checks"]["lvs_accept"]
        and so["independent_scan"]["layers"].get(5) == 8
        and so["independent_scan"]["layers"].get(6) == 48)

    # ⑥ 多总线阵列也签核（4×8 = 32 单元 ⇒ PCM 32 / HEATER 192）
    arr4 = build_array(8, n_buses=4)
    so4 = layout_signoff(arr4)
    chk("⑥ 4×8 阵列签核（PCM 32 / HEATER 192 / LVS ACCEPT）",
        so4["independent_scan"]["layers"].get(5) == 32
        and so4["independent_scan"]["layers"].get(6) == 192
        and so4["checks"]["lvs_accept"])

    # ⑦ 容量与 pad 数由上游电平数算出（非硬编码）
    bud = array_budget(build_array(8, 1))
    nlev = n_levels_upstream()
    chk("⑦ 容量/pad 数由上游算出（8 单元 × 16 电平 = 128 态 · pad 32）",
        bud["array_states"] == 8 * nlev["n_levels"] and bud["n_electrode_pads"] == 32
        and bud["array_bits"] == 8 * nlev["bits_per_cell"])

    # ⑧ 阵列总损 = N × 单元损（串行累加恒等式，逐位）
    st_c = M0.cell_state("GST", "crystalline", l_um=pit["l_cell_um"])
    chk("⑧ 阵列总损 ≡ N × 单元损（串行累加恒等式）",
        abs(bud["array_il_db"]["crystalline"][0]
            - 8 * float(st_c["il_db_min"])) < 1e-12)

    # ⑨ 独立解码器对**畸形输入**不静默（长度越界必须 raise）
    guard = 0
    for bad in (lambda: independent_gds_scan(b"\x00\x02\x00"),
                lambda: independent_gds_scan(b"\xff\xff\x00\x00")):
        try:
            bad()
        except PMM3Error:
            guard += 1
    chk("⑨ 独立解码器护栏：短记录/越界长度必 raise（不静默截断）", guard == 2)

    # ⑩ 越域参数必拒（n_cells<1 / n_buses<1 / k_iso≤0）
    guard2 = 0
    for bad in (lambda: build_array(0, 1), lambda: build_array(1, 0),
                lambda: thermal_min_gap_um("GST", k_iso=0.0)):
        try:
            bad()
        except PMM3Error:
            guard2 += 1
    chk("⑩ 越域护栏：n_cells/n_buses < 1 · k_iso ≤ 0 均 raise", guard2 == 3)

    ok_all = all(res.values())
    if verbose:
        for m in msgs:
            print("  " + m)
    return ok_all


if __name__ == "__main__":
    print("PM-M3 自检：", "ALL PASS" if run_selfchecks(verbose=True) else "FAIL")
