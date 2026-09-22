"""P3 · 16×16 tiling + 几何寄生协同损耗预算（定天花板）。

主权零依赖；复用 build_mesh_pnr + gds_export.parse_gds_polygons + parasitic_rc。
运行：PYTHONPATH=D:/agent_LDA/lda python examples/budget_p3_tile_loss.py
  （系统 Python 需含 numpy）

设计（诚实边界严守，不纸糊楼）：
- 16×16 瓦片 = N_TILE=16 的 Clements 矩形网格（DFT(16)），复用 build_mesh_pnr
  主权 P&R（分解/版级保真度/DRC/LVS 全死标量）。这是 P3 的「瓦片」交付物。
- tiling = 把 T 个独立 16×16 瓦片经波导级联（块分解架构：大酉 = 多块级联，
  块间走互连波导），故总损耗 = T×瓦片内部损耗(D1@16) + (T−1)×瓦片间互连路由损耗
  + 寄生衬底代理损耗。此模型**不重复计 D1 单总线**（D1 假设单一融合总线，
  tiling 保留独立瓦片 + 显式互连开销，故 tiling 损耗略高于融合单总线——如实）。
- 几何寄生协同：对瓦片 GDS 跑 parasitic_rc 提取全版图 R_series / C_total（fF），
  衬底电容 C_total 经透明系数折算为光学衬底泄漏代理损耗（亚 dB/瓦片量级），
  随瓦片数线性增长；这是「损耗预算协同仿真（几何寄生工具）」的实体贡献。
- 天花板（定天花板）：扫描 T，取 IL_total ≤ equalizer_range(30dB) 与
  IL_total ≤ receiver_margin(20dB) 的最大 N=16T，给出三场景可达天花板。

硬断言（EXIT=0 为 PASS）：
- 瓦片 layout_fidelity == 1.0；drc_pass True；lvs_verdict == "ACCEPT"
- 寄生 R/C 有限且 C_total>0
- 瓦片间路由损耗随 T 单调增
- 优化场景 A 的免均衡接收天花板 N ≥ 128（确认 P1-B 安全区）
"""
from __future__ import annotations

import os
import sys

# 兜底路径（优先依赖 PYTHONPATH 环境变量，符合铁律）
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (os.path.join(_ROOT, "lda"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402

from lda_layout.mesh_pnr import build_mesh_pnr, write_mesh_gds  # noqa: E402
from lda_l2.mzi_mesh_matmul import dft_matrix  # noqa: E402
from lda_l2.gds_export import parse_gds_polygons  # noqa: E402
from lda_l2 import parasitic_rc  # noqa: E402

N_TILE = 16
# D1 损耗律（≥16 经验证线性）：L_bus(N)=35.6·N µm；n_tap=1.3·(N−1)
L_BUS_PER_N_UM = 35.6
N_TAP_FACTOR = 1.3
# 16×16 瓦片 x 向跨度（D1 表 L_bus@16=561.1 µm）→ 瓦片间互连路由基准长度
L_TILE_X_UM = 561.1
# 寄生衬底泄漏代理系数（几何级、透明、亚 dB/瓦片量级，非 foundry 签核值）
C_SUB_LOSS_DB_PER_FF = 1e-4
# 系统级代价阈值
EQUALIZER_RANGE_DB = 30.0     # P2 EO-VOA 级动态范围
RECEIVER_MARGIN_DB = 20.0    # 链路预算免均衡接收余量（D1 §六）

# 三场景（α_prop dB/cm, α_tap dB）：同 D1
SCEN = {
    "A": (1.0, 0.020),  # 优化 SOI + 绝热 MMI
    "B": (2.0, 0.050),  # 标准 SOI + 方向耦合器
    "C": (3.0, 0.100),  # 保守/未优化
}


def d1_bus_loss(N: int, a_prop: float, a_tap: float) -> float:
    """单融合总线损耗（dB），D1 律：IL = α_prop·L_bus + n_tap·α_tap。"""
    l_bus_um = L_BUS_PER_N_UM * N
    n_tap = N_TAP_FACTOR * (N - 1)
    return a_prop * (l_bus_um / 1e4) + n_tap * a_tap


def main() -> int:
    # ---- 1. 构建 16×16 瓦片 + 主权 DRC/LVS ----
    U = dft_matrix(N_TILE)
    rep = build_mesh_pnr(U, ps_arm_um=1000.0, vpi_l_v_mm=7.5)
    fid = float(rep["layout_fidelity"])
    drc_pass = bool(rep["drc_pass"])
    lvs_verdict = rep["lvs_verdict"]
    gds_bytes = rep["gds_bytes"]
    footprint_um2 = float(rep["footprint_um2"])

    # 落盘瓦片 GDS（P3 交付物：16×16 瓦片）
    tile_gds = os.path.join(_HERE, "mesh16x16_tile_p3.gds")
    write_mesh_gds(rep, tile_gds)

    # ---- 2. 几何寄生协同提取 ----
    parsed = parse_gds_polygons(gds_bytes)
    prc = parasitic_rc.estimate_parasitics(parsed["structures"])
    c_tile_ff = float(prc["totals"]["C_total_ff"])
    r_tile_ohm = float(prc["totals"]["R_series_ohm"])
    n_elem = int(prc["totals"]["n_elements"])

    # 寄生衬底代理损耗/瓦片（透明折算）
    il_par_per_tile = C_SUB_LOSS_DB_PER_FF * c_tile_ff

    # 瓦片内部损耗（D1@16，三场景）
    tile_internal = {s: d1_bus_loss(N_TILE, ap, at) for s, (ap, at) in SCEN.items()}
    # 瓦片间互连路由损耗/边界（α_prop·L_tile_x）
    link_loss_per_boundary = {
        s: ap * (L_TILE_X_UM / 1e4) for s, (ap, at) in SCEN.items()
    }

    # ---- 3. tiling 扫描 + 定天花板 ----
    T_list = [1, 2, 4, 8, 16, 32, 64, 128]
    rows = []
    ceiling_eq = {}     # 需幅度均衡仍可工作（≤30dB）的最大 N
    ceiling_rx = {}     # 免均衡接收余量内（≤20dB）的最大 N
    for s, (ap, at) in SCEN.items():
        last_eq = 0
        last_rx = 0
        for T in T_list:
            N = N_TILE * T
            il_bus = tile_internal[s] * T
            il_link = link_loss_per_boundary[s] * (T - 1)
            il_par = il_par_per_tile * T
            il_total = il_bus + il_link + il_par
            feas_eq = il_total <= EQUALIZER_RANGE_DB
            feas_rx = il_total <= RECEIVER_MARGIN_DB
            rows.append((s, T, N, il_bus, il_link, il_par, il_total, feas_eq, feas_rx))
            if feas_eq:
                last_eq = N
            if feas_rx:
                last_rx = N
        ceiling_eq[s] = last_eq
        ceiling_rx[s] = last_rx

    # ---- 4. 硬断言 ----
    assert abs(fid - 1.0) < 1e-9, f"tile layout_fidelity={fid} (期望 1.0)"
    assert drc_pass is True, "tile DRC 未 PASS"
    assert lvs_verdict == "ACCEPT", f"tile LVS verdict={lvs_verdict}"
    assert c_tile_ff > 0 and r_tile_ohm >= 0, "寄生 R/C 异常"
    # 路由损耗单调（逐场景独立校验）
    for s in SCEN:
        prev = 0.0
        for T in T_list:
            cur = link_loss_per_boundary[s] * (T - 1)
            assert cur >= prev - 1e-12, "路由损耗非单调"
            prev = cur
    # 优化场景 A 免均衡接收天花板确认 P1-B 安全区（N≤128）
    assert ceiling_rx["A"] >= 128, f"A 免均衡天花板={ceiling_rx['A']} < 128"

    # ---- 5. 输出 ----
    print("=== P3 · 16×16 tiling + 几何寄生协同损耗预算 ===")
    print(f"瓦片: N={N_TILE} | layout_fid={fid:.6f} | DRC={drc_pass} | "
          f"LVS={lvs_verdict} | footprint={footprint_um2:.1f}µm² | GDS={tile_gds}")
    print(f"几何寄生(瓦片): R_series={r_tile_ohm:.3f}Ω | C_total={c_tile_ff:.3f}fF "
          f"| 元素={n_elem} | 衬底代理损耗/瓦片={il_par_per_tile:.4f}dB")
    print()
    print(f"{'scn':<4}{'T':>4}{'N':>6}{'IL_bus':>9}{'IL_link':>9}"
          f"{'IL_par':>9}{'IL_tot':>9}  eq≤30  rx≤20")
    for (s, T, N, il_bus, il_link, il_par, il_total, fe, fr) in rows:
        print(f"{s:<4}{T:>4}{N:>6}{il_bus:>9.3f}{il_link:>9.3f}"
              f"{il_par:>9.3f}{il_total:>9.3f}  {'Y' if fe else 'N':>5}  "
              f"{'Y' if fr else 'N':>5}")
    print()
    print("=== 天花板（定天花板，最大 N=16T）===")
    for s in SCEN:
        print(f"  场景 {s}: 需均衡可工作 N≤{ceiling_eq[s]}  |  "
              f"免均衡接收 N≤{ceiling_rx[s]}")
    print("\n[OK] P3 tile+parasitic loss co-sim PASS "
          "(tile DRC/LVS ACCEPT, fidelity 1.0)")

    # 落盘原始数值
    out = os.path.join(_HERE, "_p3_tile_loss_out.txt")
    with open(out, "w") as f:
        f.write(f"tile N={N_TILE} fid={fid} drc={drc_pass} lvs={lvs_verdict} "
                f"C_total_ff={c_tile_ff:.4f} R_ohm={r_tile_ohm:.4f}\n")
        for (s, T, N, il_bus, il_link, il_par, il_total, fe, fr) in rows:
            f.write(f"{s} T={T} N={N} bus={il_bus:.3f} link={il_link:.3f} "
                    f"par={il_par:.3f} tot={il_total:.3f} eq={int(fe)} rx={int(fr)}\n")
        f.write(f"ceiling_eq={ceiling_eq}\nceiling_rx={ceiling_rx}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
