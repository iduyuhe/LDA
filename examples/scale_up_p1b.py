"""P1-B 规模爬升验证 · 16×16 与 128×128 光子张量核（主权零依赖）。

执行：PYTHONPATH=D:/agent_LDA/lda python examples/scale_up_p1b.py
对 N=16 与 N=128：
  - Clements 矩形分解（N(N-1)/2 个 MZI + N 个输出相移器）
  - 版级前向下行传输保真度（物理联网表真算该酉）
  - 主权 DRC / LVS 签核
  - 工艺映射：θ→耦合器长度 Lc(CMT)；φ/D→驱动电压(Vπ·L 定律)
  - 真实 GDSII + 驱动电压 manifest CSV 落盘
16×16：硬断言全绿（EXIT=0）。128×128：全绿（重超时），报告 footprint/驱动。

输出：
  - examples/mesh16x16_dft.gds / mesh128x128_dft.gds
  - examples/mesh16x16_drive_manifest.csv / mesh128x128_drive_manifest.csv
"""
from __future__ import annotations

import csv
import os
import sys
import time

from lda_layout.mesh_pnr import build_mesh_pnr, write_mesh_gds
from lda_l2.mzi_mesh_matmul import dft_matrix


def write_manifest_csv(path: str, rep: dict) -> None:
    dm = rep["drive_manifest"]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["# P1-B 驱动电压清单", rep["N"], "x", rep["N"],
                    "Vpi_L_mm", dm["vpi_l_v_mm"], "arm_um", dm["ps_arm_um"],
                    "Vpi_volts", round(dm["vpi_volts"], 3), "Vmax", round(dm["v_max"], 3)])
        w.writerow(["kind", "idx", "col_c_or_rail", "phi_rad", "V"])
        for d in dm["mzi"]:
            w.writerow(["mzi", d["j"], d["col_c"], round(d["phi_rad"], 6), round(d["V"], 4)])
        for d in dm["out"]:
            w.writerow(["out", d["rail"], "-", round(d["phi_rad"], 6), round(d["V"], 4)])


def run_one(N: int, here: str) -> dict:
    t0 = time.time()
    U = dft_matrix(N)
    rep = build_mesh_pnr(U, ps_arm_um=1000.0, vpi_l_v_mm=7.5)
    gds_path = write_mesh_gds(rep, os.path.join(here, f"mesh{N}x{N}_dft.gds"))
    csv_path = os.path.join(here, f"mesh{N}x{N}_drive_manifest.csv")
    write_manifest_csv(csv_path, rep)
    dt = time.time() - t0
    rep["gds_path"] = gds_path
    rep["csv_path"] = csv_path
    rep["elapsed_s"] = dt
    return rep


def report(rep: dict) -> None:
    N = rep["N"]
    print("=" * 70)
    print(f"P1-B · {N}×{N} 光子张量核（酉分解→物理综合→签核→工艺映射）")
    print("=" * 70)
    print(f"MZI 单元数      : {rep['n_mzi']}  (= N(N-1)/2 = {N*(N-1)//2})")
    print(f"输出相移器      : {rep['n_ps']}")
    print(f"分解保真度      : {rep['fidelity']:.6f}")
    print(f"版级保真度      : {rep['layout_fidelity']:.6f}  "
          f"(物理级联网表前向下行传输 == U_target)")
    print(f"版图展开宽 x_max: {rep['x_max_um']:.1f} µm  (步距 {rep['pitch_um']:.1f}µm)")
    print(f"footprint       : {rep['footprint_um2']:.1f} µm²")
    print(f"GDS 元件        : {rep['gds_elements']}")
    print(f"几何最小间距    : {rep['geo_min_space_um']:.3f} µm")
    dm = rep["drive_manifest"]
    print(f"工艺映射        : Vπ·L={dm['vpi_l_v_mm']:.1f} V·mm · 臂={dm['ps_arm_um']:.0f}µm "
          f"⇒ Vπ={dm['vpi_volts']:.2f}V · V_max={dm['v_max']:.2f}V")
    print(f"DRC             : {'PASS' if rep['drc_pass'] else 'FAIL'}")
    print(f"LVS             : {rep['lvs_verdict']}  (违规 {rep['lvs_n_violations']} · "
          f"网一致 {rep['lvs_match']})")
    print(f"耗时            : {rep['elapsed_s']:.1f}s")
    print(f"GDS / manifest  : {rep['gds_path']}")
    print(f"                 : {rep['csv_path']}")


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    ok = True
    for N in (16, 128):
        rep = run_one(N, here)
        report(rep)
        gate = (rep["drc_pass"] is True and rep["lvs_verdict"] == "ACCEPT"
                and rep["layout_fidelity"] >= 0.9999999
                and rep["fidelity"] >= 0.9999999)
        print(f"  → {N}×{N} 接受闸: {'✅ PASS' if gate else '❌ FAIL'}")
        if not gate:
            ok = False
        print()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
