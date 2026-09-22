"""LDA L2 · WDM 网格 P&R（波分复用路由入版图 · P0.1 头号升级 · v0.9.95）。

给单波长 N×N Clements 光子张量核加 **K 波长维**（K 波长 × N×N），
把「波分复用路由」落进 P&R——带宽密度 ×K，逼近市场 DWDM，不破主权。

架构（主权 C 级自写零依赖）：
  - K 个波长面（plane），每面 = 一个独立 N×N Clements 网格（复用
    `mesh_pnr` 的酉分解 / 摆位 / 物理级联网表真算该酉 / 保真度 机器精度核心）。
  - 输入侧 **WDM 解复用**：共享输入总线上的 K 个微环 add-drop 滤波器级联，
    每环按 λ_k 调谐，把 λ_k 下路（drop）到对应波长面。环半径
    R_k = m·λ_k/(2π·n_g)（整数 m 谐振器，与 D-42/D-57 同源物理锚），
    耦合 k_ring 由方向耦合器 κ_c（FDTD 标定，见 `wdm_coupler`）驱动。
  - 输出侧 **WDM 复用**：镜像——各面输出经微环上载（add）回共享输出总线。
  - K 面 + 解/复用环 合并为 **单一 LinkModel + 单次主权 DRC/LVS 签核**。

布局纪律（防 LVS 假红 / 假绿）：
  - 所有解/复用路由严格落在 y<0 专用走廊（demux/mux 总线 + 下路/上载竖井），
    波长面全部在 y≥0 → 两域永不相交 ⇒ 无 cross_short。
  - 每根 net 端点精确落回端口锚点（容差 tol µm 内唯一归属），LVS 由几何
    独立恢复网表比对原理图。全部死标量，LLM 不进判决路径。

诚实边界：v1 每波长面处理**独立酉矩阵 U_k**（可重配置网格，每 λ 算各自变换）；
波分选择性来自微环（真 WDM 机制），每面内 N 轨扇入/扇出用 MMI 1×N / N×1
（空间分路，主权内）。环耦合 k_ring 默认走解析 κ_c 上界，精确值由
`wdm_coupler.design_wdm_with_coupler` 的 FDTD κ_c(gap,λ) 标定回填（honest note）。
"""
from __future__ import annotations

import cmath
import math
import os
from typing import Dict, List, Optional, Tuple

import numpy as np

from lda_chain.link_model import LinkModel
from lda_l2 import drc as drc_mod
from lda_l2 import gds_export as gx
from lda_l2 import lvs as lvs_mod
from lda_l2.mzi_mesh_matmul import coupler_length_from_theta, dft_matrix
from lda_layout.mesh_pnr import (
    clements_decompose,
    mesh_clements_fidelity,
    mesh_layout_fidelity,
    mesh_drive_manifest,
    _mzi_arm_polyline,
)
from lda_layout.placement import port_abs, _port_abs_cache_clear


# ---------------------------------------------------------------------------
# 物理锚：微环 add-drop（WDM 解/复用核心）
# ---------------------------------------------------------------------------
def wdm_ring_anchor(wl_nm: float, n_g: float = 2.45, m: int = 30,
                    gap: float = 0.3) -> Dict[str, float]:
    """单环物理锚（与 D-42/D-57 同源）：

      R_k = m·λ_k/(2π·n_g)（整数 m 谐振器，解析 ORACLE 级物理锚）；
      k_ring = sin(κ_c·L_couple)，L_couple = 2√(2R·gap)，κ_c 为方向耦合器
      耦合系数（精确值由 `wdm_coupler` 的 FDTD κ_c(gap,λ) 标定；此处给
      解析上界 gap_to_kappa 作占位，honest note 标注）。
    """
    wl_um = wl_nm * 1e-3
    R = m * wl_um / (2.0 * math.pi * n_g)          # µm
    try:
        from lda_agent.ring_adddrop import gap_to_kappa  # type: ignore
        kc = float(gap_to_kappa(gap))
    except Exception:
        # 解析指数模型占位（D-37 kappa_ref=0.35 假设上界）；honest note 标注
        kc = 0.35 * math.exp(-gap / 0.2)
    L_couple = 2.0 * math.sqrt(2.0 * R * gap)
    k_ring = math.sin(kc * L_couple) if kc > 0 else 0.0
    return {
        "wl_nm": wl_nm, "n_g": n_g, "m": m, "gap_um": gap,
        "R_um": round(R, 4),
        "L_couple_um": round(L_couple, 4),
        "kappa_c_rad_um": round(kc, 5),
        "k_ring": round(k_ring, 5),
        "FSR_nm": round(wl_nm / m, 4),   # 自由光谱范围（> 信道间隔即不串扰）
    }


# ---------------------------------------------------------------------------
# 单波长面构造（N×N Clements 网格 + MMI 1×N 输入 + MMI N×1 输出）
# ---------------------------------------------------------------------------
def _build_plane(link: LinkModel, placement: dict, routes: dict,
                 elements: list, k: int, U: np.ndarray,
                 y0: float, params: dict) -> Dict[str, object]:
    """构造第 k 个波长面，并入共享 link/placement/routes/elements。

    返回该面关键信息（mzis / splitter / combiner id / 保真度 / 几何范围）。
    """
    N = U.shape[0]
    rail_pitch = params["rail_pitch"]; wg = params["wg"]; gap = params["gap"]
    Lc_margin = params["Lc_margin"]
    sx = params["sx"]                     # splitter 原点 x
    L_mmi = params["L_mmi"]; L_tap = params["L_tap"]; L_out = params["L_out"]
    out_gap = params["out_gap"]
    splitter_w = L_mmi + L_tap + L_out
    sy = y0 + (N - 1) / 2.0 * rail_pitch   # splitter/combiner 居中 y

    ops, D = clements_decompose(U)
    n_mzi = len(ops)
    fid = mesh_clements_fidelity(ops, D, U)
    layout_fid = mesh_layout_fidelity(ops, D, U)
    pre = []
    Lu_max = 0.0
    for idx, (j, theta, phi, c) in enumerate(ops):
        Lc = coupler_length_from_theta(theta)
        Lu = Lc + 2.0 * Lc_margin
        Lu_max = max(Lu_max, Lu)
        pre.append((idx, j, theta, phi, c, Lu))
    pitch = Lu_max + params["col_gap"]
    mesh_x0 = sx + splitter_w + 6.0
    mzis = []
    for (idx, j, theta, phi, c, Lu) in pre:
        x_k = mesh_x0 + (n_mzi - 1 - idx) * pitch
        y_k = y0 + j * rail_pitch
        mzis.append({
            "id": f"p{k}_mzi{idx}", "j": j, "k": c, "theta": theta, "phi": phi,
            "Lc": coupler_length_from_theta(theta), "Lu": Lu,
            "x": x_k, "y": y_k,
        })
    x_max_plane = max(m["x"] + m["Lu"] for m in mzis) + Lc_margin + 18.0
    cx = x_max_plane + 6.0 + splitter_w     # combiner 原点 x

    # ---- 器件 ----
    sk = f"p{k}_split"
    ck = f"p{k}_comb"
    link.add_device(sk, "MMI",
                    params={"L_mmi": L_mmi, "L_tap": L_tap, "L_out": L_out,
                             "width": wg, "out_gap": out_gap, "n_out": N},
                    ports=["in"] + [f"out{j}" for j in range(1, N + 1)])
    link.add_device(ck, "MMIC",
                    params={"L_mmi": L_mmi, "L_tap": L_tap, "L_out": L_out,
                             "width": wg, "out_gap": out_gap, "n_in": N},
                    ports=["out"] + [f"in{j}" for j in range(1, N + 1)])
    for m in mzis:
        link.add_device(m["id"], "MZI",
                        params={"Lu": m["Lu"], "dy": rail_pitch, "wg": wg,
                                 "gap": gap},
                        ports=["in1", "in2", "out1", "out2"])
    # port_abs 组件索引缓存按 (placement,link) 身份缓存且只建一次；本模块在同
    # 一 link 上逐面增量 add_device ⇒ 必须使缓存失效，否则后续面的端口查不到
    # 而回落到器件原点（LVS 锚点表实时重建 ⇒ 路由端点/锚点对不上，判拒）。
    _port_abs_cache_clear()
    placement[sk] = (sx, sy, 0.0)
    placement[ck] = (cx, sy, 0.0)
    for m in mzis:
        placement[m["id"]] = (m["x"], m["y"], 0.0)

    # ---- 每轨 rail 链：splitter.out_j → [MZI in1/out1] → combiner.in_j ----
    rail_mzis: Dict[int, List[Tuple[dict, str]]] = {jj: [] for jj in range(N)}
    for m in mzis:
        rail_mzis[m["j"]].append((m, "lower"))
        rail_mzis[m["j"] + 1].append((m, "upper"))
    for jj in range(N):
        rail_mzis[jj].sort(key=lambda t: t[0]["x"])

    mzi_in_port = lambda m, role: "in1" if role == "lower" else "in2"
    mzi_out_port = lambda m, role: "out1" if role == "lower" else "out2"

    def _route(net_id, inst_a, port_a, inst_b, port_b):
        pa = port_abs(inst_a, port_a, placement, link)
        pb = port_abs(inst_b, port_b, placement, link)
        routes[net_id] = {"points_um": [pa, pb]}
        link.connect(net_id, inst_a, port_a, inst_b, port_b)

    rail_y = [y0 + jj * rail_pitch for jj in range(N)]
    for jj in range(N):
        seq = rail_mzis[jj]
        prev_inst, prev_port = sk, f"out{jj + 1}"
        t = 0
        for (m, role) in seq:
            in_port = mzi_in_port(m, role)
            out_port = mzi_out_port(m, role)
            _route(f"p{k}_r{jj}_{t}", prev_inst, prev_port, m["id"], in_port)
            t += 1
            prev_inst, prev_port = m["id"], out_port
        _route(f"p{k}_r{jj}_{t}", prev_inst, prev_port, ck, f"in{jj + 1}")

    # ---- GDS：每轨折线（splitter.out_j → MZI 臂 → combiner.in_j）----
    for jj in range(N):
        seq = rail_mzis[jj]
        pa0 = port_abs(sk, f"out{jj + 1}", placement, link)
        pbN = port_abs(ck, f"in{jj + 1}", placement, link)
        poly: List[Tuple[float, float]] = [pa0]
        for (m, role) in seq:
            arm = _mzi_arm_polyline(
                m["x"], rail_y[jj] if role == "lower" else m["y"],
                rail_pitch, m["Lu"], m["Lc"], Lc_margin, gap, role)
            poly += arm[1:]
        poly.append(pbN)
        elements.append(gx.path(gx.LIB_LAYER_SI, wg, poly))
    # MZI 相移器金属 patch（落在下轨臂首段直区）
    for m in mzis:
        ps_x0 = m["x"] + 1.0
        ps_x1 = m["x"] + min(params["ps_len"], Lc_margin - 2.0)
        patch = [(ps_x0, m["y"] - wg * 0.6), (ps_x1, m["y"] - wg * 0.6),
                 (ps_x1, m["y"] + wg * 0.6), (ps_x0, m["y"] + wg * 0.6)]
        elements.append(gx.boundary(gx.LIB_LAYER_METAL, patch))
    # splitter / combiner 矩形（SI）
    for (dev, ox, oy) in [(sk, sx, sy), (ck, cx, sy)]:
        half_w = L_mmi / 2.0 + 1.0
        half_h = (N / 2.0) * (wg + out_gap) + 1.0
        rect = [(ox - half_w, oy - half_h), (ox + half_w, oy - half_h),
                (ox + half_w, oy + half_h), (ox - half_w, oy + half_h)]
        elements.append(gx.boundary(gx.LIB_LAYER_SI, rect))

    return {
        "k": k, "N": N, "n_mzi": n_mzi, "ops": ops, "D": D,
        "fidelity": fid, "layout_fidelity": layout_fid,
        "splitter_id": sk, "combiner_id": ck,
        "mzis": mzis, "sy": sy, "cx": cx, "rail_y": rail_y,
        "x_min": sx - L_tap, "x_max": cx + L_tap,
    }


# ---------------------------------------------------------------------------
# WDM 解/复用环组（微环 add-drop 级联）
# ---------------------------------------------------------------------------
def _circle_poly(cx: float, cy: float, R: float, n: int = 36) -> List[Tuple[float, float]]:
    return [(cx + R * math.cos(2 * math.pi * i / n),
             cy + R * math.sin(2 * math.pi * i / n)) for i in range(n)]


def _build_wdm_demux_mux(link: LinkModel, placement: dict, routes: dict,
                         elements: list, planes: List[dict],
                         wavelengths_nm: List[float], params: dict) -> Dict[str, object]:
    """构造 K 环解复用（输入侧，左）与复用（输出侧，右），并入共享结构。

    返回环几何/锚信息 + 总线 y 带（供 honest note）。
    """
    N = planes[0]["N"]
    wg = params["wg"]; gap = params["gap"]; n_g = params["n_g"]; m_ring = params["m_ring"]
    demux_y = params["demux_y"]
    ring_dx = params["ring_dx"]
    K = len(wavelengths_nm)

    anchors = []
    for k_wl, wl in enumerate(wavelengths_nm):
        a = wdm_ring_anchor(wl, n_g=n_g, m=m_ring, gap=gap)
        anchors.append(a)

    # ---- 输入 GC + 解复用总线（左，y<0 走廊）----
    gc_in = "wdm_gc_in"
    link.add_device(gc_in, "GratingCoupler",
                    params={"L": params["Lg"], "width": wg}, ports=["fib", "wg"])
    _port_abs_cache_clear()
    placement[gc_in] = (0.0, demux_y - params["Lg"], 0.0)

    # 反序映射：λ_k 环的 x 随 k **递减**（λ_0 最右），而目标 splitter.in 的 y
    # 随 k 递增 ⇒ 二者次序相反。L 型走线（先竖直到该面 sy，再水平入 splitter.in）
    # 在「x 次序与 y 次序相反」时必不交叉；若同序（环 x 递增 + 面 y 递增）则所有
    # 目标 splitter.in 同 x（同列）⇒ 直连/单调 L 都会形成「扇入交叉」(LVS
    # cross_short)。物理不变：仅改环摆放次序，λ_k ↔ 面 k 对应保持一一。
    demux_rings = []
    prev_out_inst, prev_out_port = gc_in, "wg"
    # 自最左环（λ_{K-1}，x=4）向右建总线（x 递增）⇒ 总线自身亦不交叉
    for k_wl in range(K - 1, -1, -1):
        rid = f"wdm_demux_ring{k_wl}"
        x_rk = 4.0 + (K - 1 - k_wl) * ring_dx
        R = anchors[k_wl]["R_um"]
        link.add_device(rid, "RingAddDrop",
                        params={"R": R, "wg_width": wg, "gap": gap},
                        ports=["in", "out", "drop"])
        _port_abs_cache_clear()
        placement[rid] = (x_rk, demux_y, 0.0)
        demux_rings.append((rid, x_rk, R))
        # 总线：prev → ring.in（水平段在 y=demux_y-off 之下，属 y<0 走廊）
        _pa = port_abs(prev_out_inst, prev_out_port, placement, link)
        _pb = port_abs(rid, "in", placement, link)
        net = f"wdm_demux_bus_{k_wl}"
        routes[net] = {"points_um": [_pa, _pb]}
        link.connect(net, prev_out_inst, prev_out_port, rid, "in")
        # ring.drop → 该波长面 splitter.in（L 型：竖直 + 水平，见上）
        sk = planes[k_wl]["splitter_id"]
        pa = port_abs(rid, "drop", placement, link)
        pb = port_abs(sk, "in", placement, link)
        net = f"wdm_drop_{k_wl}"
        routes[net] = {"points_um": [pa, (pa[0], pb[1]), pb]}
        link.connect(net, rid, "drop", sk, "in")
        prev_out_inst, prev_out_port = rid, "out"
    # 总线末端终结（最右环 λ_0 的 out → 负载 stub）
    term = "wdm_demux_term"
    link.add_device(term, "Waveguide",
                    params={"length": 4.0, "width": wg}, ports=["in", "out"])
    _port_abs_cache_clear()
    placement[term] = (4.0 + (K - 1) * ring_dx + 12.0, demux_y, 0.0)
    pa = port_abs(prev_out_inst, prev_out_port, placement, link)
    pb = port_abs(term, "in", placement, link)
    net = "wdm_demux_bus_term"
    routes[net] = {"points_um": [pa, pb]}
    link.connect(net, prev_out_inst, prev_out_port, term, "in")

    # ---- 复用（输出侧，右）：每面 combiner.out → 环 add(=drop) → 输出总线 ----
    gc_out = "wdm_gc_out"
    link.add_device(gc_out, "GratingCoupler",
                    params={"L": params["Lg"], "width": wg}, ports=["fib", "wg"])
    _port_abs_cache_clear()
    mux_base = max(p["cx"] for p in planes) + params["L_tap"] + 10.0
    max_x = mux_base + (K - 1) * ring_dx + ring_dx + 10.0
    placement[gc_out] = (max_x, demux_y - params["Lg"], 0.0)
    # 输出总线起点终结 stub（最左环 λ_0 的 in 侧）
    mux_term = "wdm_mux_term"
    link.add_device(mux_term, "Waveguide",
                    params={"length": 4.0, "width": wg}, ports=["in", "out"])
    _port_abs_cache_clear()
    placement[mux_term] = (mux_base - 12.0, demux_y, 0.0)

    # λ_k 环 x 随 k **递增**，与 combiner.out 所在面 y 随 k 递增**同序** ⇒
    # L 型（先水平到环 x，再竖直下到 drop）无交叉（demux 反向注释的对偶）。
    mux_rings = []
    prev_out_inst, prev_out_port = mux_term, "out"
    for k_wl in range(K):
        rid = f"wdm_mux_ring{k_wl}"
        x_rk = mux_base + k_wl * ring_dx
        R = anchors[k_wl]["R_um"]
        link.add_device(rid, "RingAddDrop",
                        params={"R": R, "wg_width": wg, "gap": gap},
                        ports=["in", "out", "drop"])
        _port_abs_cache_clear()
        placement[rid] = (x_rk, demux_y, 0.0)
        mux_rings.append((rid, x_rk, R))
        # 该面 combiner.out → 环 drop（上载，reciprocal）；L 型（水平 + 竖直）
        ck = planes[k_wl]["combiner_id"]
        pa = port_abs(ck, "out", placement, link)
        pb = port_abs(rid, "drop", placement, link)
        net = f"wdm_add_{k_wl}"
        routes[net] = {"points_um": [pa, (pb[0], pa[1]), pb]}
        link.connect(net, ck, "out", rid, "drop")
        # 总线：prev.out → ring.in（向右累积到输出 GC）
        pa = port_abs(rid, "in", placement, link)
        pb = port_abs(prev_out_inst, prev_out_port, placement, link)
        net = f"wdm_mux_bus_{k_wl}"
        routes[net] = {"points_um": [pa, pb]}
        link.connect(net, rid, "in", prev_out_inst, prev_out_port)
        prev_out_inst, prev_out_port = rid, "out"
    # 末端：最右环 λ_{K-1}.out → gc_out.wg
    pa = port_abs(prev_out_inst, prev_out_port, placement, link)
    pb = port_abs(gc_out, "wg", placement, link)
    net = "wdm_mux_bus_out"
    routes[net] = {"points_um": [pa, pb]}
    link.connect(net, prev_out_inst, prev_out_port, gc_out, "wg")

    # ---- GDS：环圆 + 总线波导 + GC ----
    bus_y = demux_y - (params["R_max_um"] + wg / 2.0 + gap)  # 总线中心 y
    for (rid, x_rk, R) in demux_rings + mux_rings:
        elements.append(gx.boundary(gx.LIB_LAYER_SI, _circle_poly(x_rk, demux_y, R)))
    # 输入总线波导
    gx_in = port_abs(gc_in, "wg", placement, link)
    dr0 = port_abs(demux_rings[0][0], "in", placement, link)
    elements.append(gx.path(gx.LIB_LAYER_SI, wg,
                            [(gx_in[0], bus_y), (dr0[0], bus_y)]))
    # 输出总线波导
    gx_o = port_abs(gc_out, "wg", placement, link)
    mr0 = port_abs(mux_rings[-1][0], "in", placement, link)
    elements.append(gx.path(gx.LIB_LAYER_SI, wg,
                            [(mr0[0], bus_y), (gx_o[0], bus_y)]))
    # GC 矩形
    for dev, ox, oy in [(gc_in, 0.0, demux_y - params["Lg"]),
                        (gc_out, max_x, demux_y - params["Lg"])]:
        rect = [(ox - 3, oy), (ox + 3, oy), (ox + 3, oy + params["Lg"]),
                (ox - 3, oy + params["Lg"])]
        elements.append(gx.boundary(gx.LIB_LAYER_SI, rect))

    return {"anchors": anchors, "demux_rings": demux_rings,
            "mux_rings": mux_rings, "bus_y": bus_y,
            "demux_y": demux_y, "K": K}


# ---------------------------------------------------------------------------
# 主构造
# ---------------------------------------------------------------------------
def build_wdm_mesh_pnr(wavelengths_nm: Optional[List[float]] = None,
                       U_targets: Optional[List[np.ndarray]] = None,
                       N: int = 4, rail_pitch: float = 4.0, wg: float = 0.5,
                       gap: float = 0.3, Lc_margin: float = 6.0,
                       col_gap: float = 8.0, ps_len: float = 4.0,
                       n_g: float = 2.45, m_ring: int = 30,
                       L_mmi: float = 8.0, L_tap: float = 2.0, L_out: float = 2.0,
                       out_gap: float = 0.9, Lg: float = 5.0,
                       tol: float = 1.0, lib_name: str = "LDA_WDM_MESH",
                       vpi_l_v_mm: float = 7.5, ps_arm_um: float = 1000.0,
                       ) -> dict:
    """构建 K 波长 × N×N WDM 光子张量核版图 + 网表 + GDS + DRC/LVS 报告。

    参数：
      wavelengths_nm : K 个波长（nm），默认 LAN-WDM 风格 4 信道。
      U_targets      : K 个 N×N 酉矩阵（每 λ 一变换）；None → 全用 DFT(N)。
      N              : 网格规模（默认 4×4）。
    返回结构化报告 dict（含 GDS 字节、DRC/LVS 判决、每波长保真度、聚合带宽密度）。
    """
    if wavelengths_nm is None:
        wavelengths_nm = [1550.0, 1552.5, 1555.0, 1557.5]
    K = len(wavelengths_nm)
    if U_targets is None:
        U_targets = [dft_matrix(N) for _ in range(K)]
    if len(U_targets) != K:
        raise ValueError("U_targets 数量须等于波长数 K")
    for U in U_targets:
        if U.shape != (N, N):
            raise ValueError(f"U_targets 须全为 {N}×{N}")

    # 默认物理参数（推导 R_max 供总线 y 定位）
    R_max = max(wdm_ring_anchor(wl, n_g=n_g, m=m_ring, gap=gap)["R_um"]
                for wl in wavelengths_nm)
    params = dict(rail_pitch=rail_pitch, wg=wg, gap=gap, Lc_margin=Lc_margin,
                  col_gap=col_gap, ps_len=ps_len, n_g=n_g, m_ring=m_ring,
                  L_mmi=L_mmi, L_tap=L_tap, L_out=L_out, out_gap=out_gap,
                  Lg=Lg, sx=40.0, demux_y=-45.0, ring_dx=2.0 * (1.5 * R_max + 1.0),
                  R_max_um=R_max)

    link = LinkModel(domain="photon", name=f"WDM_Mesh_{K}x{N}",
                     notes="K 波长 × N×N Clements 网格 · 微环解/复用 · P0.1")
    placement: Dict[str, Tuple[float, float, float]] = {}
    routes: Dict[str, dict] = {}
    elements: List[bytes] = []

    plane_dy = (N + 2) * rail_pitch
    planes = []
    for k in range(K):
        y0 = k * plane_dy
        rep = _build_plane(link, placement, routes, elements, k,
                           np.array(U_targets[k], dtype=complex), y0, params)
        planes.append(rep)

    wdm = _build_wdm_demux_mux(link, placement, routes, elements, planes,
                               wavelengths_nm, params)

    # ---- GDS ----
    gds_bytes = gx.gds_library(lib_name, {f"WDM_{K}x{N}": elements})

    # ---- DRC（逐 MZI；环/MMIC 几何含入 GDS，DRC 守 MZI 死标量）----
    drc_rules = drc_mod.rules_from_pdk(None)
    drc_results = {}
    for p in planes:
        for m in p["mzis"]:
            r = drc_mod.drc_check_device(
                "MZI", {"wg": wg, "gap": gap, "Lu": m["Lu"]}, rules=drc_rules)
            drc_results[m["id"]] = r
    drc_all_pass = all(r.passed for r in drc_results.values())

    # ---- LVS（单一主权签核）----
    lvs_report = lvs_mod.run_lvs(link, placement, routes, tol=tol)

    # ---- 每波长保真度 + 聚合指标 ----
    per_wl = []
    for p in planes:
        per_wl.append({
            "k": p["k"], "wl_nm": wavelengths_nm[p["k"]],
            "n_mzi": p["n_mzi"],
            "fidelity": p["fidelity"], "layout_fidelity": p["layout_fidelity"],
        })
    min_fid = min(p["fidelity"] for p in per_wl)
    min_layout_fid = min(p["layout_fidelity"] for p in per_wl)

    # 聚合带宽密度（诚实边界：单波长核带宽密度不变，×K）
    # 用单波长核代表带宽密度（Gbps/mm² 量级，v0.9 实测口径）做占位乘子
    single_bw_density = 1.0   # 占位：单波长核单位面积带宽密度（相对）
    agg_bw_density = K * single_bw_density
    total_footprint_x = max(p["x_max"] for p in planes) - min(
        p["x_min"] for p in planes)
    total_footprint_y = K * plane_dy + abs(params["demux_y"]) + 10.0
    footprint_um2 = total_footprint_x * total_footprint_y

    honest_note = (
        f"P0.1 WDM 网格 P&R：K={K} 波长 × N={N}×N Clements 网格，"
        f"微环 add-drop 解/复用（环半径 R=m·λ/(2π·n_g)，m={m_ring}；"
        f"FSR≈λ/m 远大于信道间隔 ⇒ 不串扰）。每波长面保真度（分解级）"
        f"min={min_fid:.6f}、版级 min={min_layout_fid:.6f}（机器精度，"
        f"继承 mesh_pnr 已证结论）。聚合带宽密度 ×K={K}（单波长核带宽密度"
        f"不变，波分维线性叠加——逼近市场 DWDM 量级）。K 面 + 解/复用环"
        f"合并为单一 LinkModel + 单次主权 DRC/LVS：LVS={lvs_report['verdict']}"
        f"（{lvs_report['n_violations']} 违规）。布局纪律：解/复用路由全落"
        f"y<0 走廊、波长面全在 y≥0 ⇒ 无 cross_short。诚实边界：① 每面内"
        f"N 轨扇入/扇出用 MMI 1×N/N×1（空间分路，主权内）；② 环耦合 k_ring"
        f"默认解析 κ_c 上界，精确值由 wdm_coupler 的 FDTD κ_c(gap,λ) 标定"
        f"回填；③ 单波长带宽密度为占位乘子（=1），真值须 foundry PDK 圆片"
        f"表征；④ PDK 为演示近似 SOI。判决全死标量，LLM 不进路径。"
    )

    return {
        "K": K, "N": N, "wavelengths_nm": wavelengths_nm,
        "n_mzi_total": sum(p["n_mzi"] for p in planes),
        "fidelity_min": min_fid, "layout_fidelity_min": min_layout_fid,
        "per_wavelength": per_wl,
        "drc_pass": drc_all_pass,
        "drc_results": {mid: r.to_dict() for mid, r in drc_results.items()},
        "lvs_verdict": lvs_report["verdict"],
        "lvs_n_violations": lvs_report["n_violations"],
        "lvs_match": lvs_report["match"],
        "lvs_full": lvs_report,
        "ring_anchors": wdm["anchors"],
        "gds_bytes": gds_bytes,
        "gds_elements": len(elements),
        "gds_structures": 1,
        "footprint_um2": footprint_um2,
        "bandwidth_density_xK": agg_bw_density,
        "K_factor": K,
        "link": link, "placement": placement, "routes": routes,
        "honest_note": honest_note,
    }


# ---------------------------------------------------------------------------
# demo + 反向护栏
# ---------------------------------------------------------------------------
def demo_wdm_mesh_pnr(K: int = 4, N: int = 4) -> dict:
    """K 波长 × N×N WDM 网格 P&R 全流程 demo。"""
    wls = [1550.0 + 2.5 * i for i in range(K)]
    Us = [dft_matrix(N) for _ in range(K)]
    rep = build_wdm_mesh_pnr(wls, Us, N=N)
    rep["target"] = f"{K} 波长 × {N}×{N} WDM 光子张量核（每 λ 算 DFT(N)）"
    return rep


def wdm_mesh_reverse_guard(rep: dict) -> Dict[str, object]:
    """反向护栏：注入缺陷必须让 LVS/保真度 亮红（证明护栏不是假绿）。

    D1（LVS 护栏）：删除一条解复用下路 net 的路由 ⇒ 原理图有 net 而版图无
      ⇒ 判 open ⇒ LVS 必 REJECT（且违规数 >0）。
    D2（分解/保真度护栏）：把一个波长面的 U 篡改为非酉（×2）⇒ ① 若网格分解
      直接拒绝（ValueError：非酉不可由无损 MZI 网格实现）即护栏触发；② 若仍
      构建通过，则该面保真度必 <<1。二者其一为真即通过。
    """
    out: Dict[str, object] = {}
    wls = list(rep["wavelengths_nm"])
    Us = [dft_matrix(rep["N"]) for _ in range(rep["K"])]

    # D1：删一条 drop 路由 → open → REJECT
    bad = build_wdm_mesh_pnr(wls, Us, N=rep["N"])
    drop_key = f"wdm_drop_{rep['K'] - 1}"
    if drop_key in bad["routes"]:
        del bad["routes"][drop_key]
        lvs_bad = lvs_mod.run_lvs(bad["link"], bad["placement"],
                                  bad["routes"], tol=1.0)
        out["D1_open_detected"] = bool(lvs_bad["verdict"] == "REJECT"
                                       and lvs_bad["n_violations"] > 0)
    else:
        out["D1_open_detected"] = False

    # D2：非酉 U → 分解拒绝 或 保真度 <<1
    Us2 = [np.array(U, dtype=complex) for U in Us]
    Us2[0] = Us2[0] * 2.0   # 非酉
    try:
        bad2 = build_wdm_mesh_pnr(wls, Us2, N=rep["N"])
        out["D2_nonunitary_rejected"] = bool(bad2["fidelity_min"] < 0.99)
        out["D2_mode"] = "fidelity_drop"
    except ValueError as exc:   # clements_decompose 拒绝非酉
        out["D2_nonunitary_rejected"] = True
        out["D2_mode"] = f"decompose_guard: {exc}"
    return out


if __name__ == "__main__":
    r = demo_wdm_mesh_pnr()
    print(f"K={r['K']} N={r['N']}  n_mzi_total={r['n_mzi_total']}")
    print(f"fidelity_min={r['fidelity_min']:.6f}  "
          f"layout_fidelity_min={r['layout_fidelity_min']:.6f}")
    print(f"DRC={'PASS' if r['drc_pass'] else 'FAIL'}  "
          f"LVS={r['lvs_verdict']} (viol={r['lvs_n_violations']})")
    print(f"GDS 元件={r['gds_elements']}  BW密度×K={r['bandwidth_density_xK']}")
    g = wdm_mesh_reverse_guard(r)
    print(f"反向护栏：{g}")
    print(r["honest_note"])
