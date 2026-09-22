"""P1-B 接受闸 demo · 4×4 MZI 网格物理综合端到端验证（主权零依赖）。

执行：PYTHONPATH=D:/agent_LDA/lda python examples/demo_mesh_pnr_4x4.py
硬接受闸：
  EXIT=0  且  DRC_pass=True  且  LVS_verdict=='ACCEPT'
          且  layout_fidelity >= 0.9999999  （版级前向下行传输 == U_target）
  → 证明 "酉分解 → 2D 网格摆位 → 连波导 → 输出相移 → 物理级联网表真算该酉
    → 工艺映射(θ→Lc, φ/D→V) → GDS → DRC/LVS 主权签核" 死缺口已闭合
    （保真度机器精度 + 驱动电压清单就绪）。

输出：
  - 结构化报告（分解/版级保真度 / MZI+PS 数 / DRC / LVS / footprint /
    工艺映射 Vπ·V_max / GDS 路径）
  - 真实 GDSII 文件 examples/mesh_4x4_dft.gds
"""
from __future__ import annotations

import os
import sys

from lda_layout.mesh_pnr import (
    build_mesh_pnr,
    write_mesh_gds,
)
from lda_l2.mzi_mesh_matmul import dft_matrix


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    out_gds = os.path.join(here, "mesh_4x4_dft.gds")

    # ---- 1) 4×4 DFT 酉矩阵 → 完整网格物理综合 + GDS + DRC + LVS ----
    rep = build_mesh_pnr(dft_matrix(4))
    rep["target"] = "DFT(4) — 4×4 离散傅里叶变换酉矩阵（光子计算基本 PE）"

    # ---- 2) 落 GDS ----
    gds_path = write_mesh_gds(rep, out_gds)
    rep["gds_path"] = gds_path

    # ---- 3) 结构化报告 ----
    print("=" * 68)
    print("P1-B · 4×4 MZI 网格物理综合端到端验证（Clements·主权零依赖）")
    print("=" * 68)
    print(f"目标        : {rep['target']}")
    print(f"N           : {rep['N']}")
    print(f"MZI 单元数  : {rep['n_mzi']}  （Clements 矩形网格相邻耦合）")
    print(f"输出相移器  : {rep['n_ps']}  （末端对角相位 D）")
    print(f"分解保真度  : {rep['fidelity']:.6f}  （编译映射数学可行）")
    print(f"版级保真度  : {rep['layout_fidelity']:.6f}  "
          f"（物理级联网表前向下行传输 == U_target）")
    print(f"版图尺寸    : x_max={rep['x_max_um']:.1f}µm · "
          f"步距={rep['pitch_um']:.1f}µm · 轨距={rep['rail_pitch_um']}µm")
    print(f"footprint   : {rep['footprint_um2']:.1f} µm² "
          f"（蛇形折叠展开宽 × N·轨距；压实 2D 网格见诚实边界）")
    print(f"GDS 元件    : {rep['gds_elements']} 条 PATH/BOUNDARY")
    print(f"几何最小间距: {rep['geo_min_space_um']:.3f}µm  "
          f"（≥ DRC min_space 0.20µm ⇒ 不桥接）")
    dm = rep["drive_manifest"]
    print(f"工艺映射    : Vπ·L={dm['vpi_l_v_mm']:.1f} V·mm · "
          f"臂长={dm['ps_arm_um']:.0f}µm ⇒ Vπ={dm['vpi_volts']:.2f}V · "
          f"V_max={dm['v_max']:.2f}V")
    print(f"DRC         : {'PASS' if rep['drc_pass'] else 'FAIL'}")
    print(f"LVS         : {rep['lvs_verdict']}  "
          f"（违规 {rep['lvs_n_violations']} · 网一致 {rep['lvs_match']}）")
    print(f"GDS 文件    : {gds_path}")
    print("-" * 68)
    print(rep["honest_note"])
    print("=" * 68)

    # ---- 4) 硬接受闸（版级保真度纳入门禁）----
    ok = (rep["drc_pass"] is True) and (rep["lvs_verdict"] == "ACCEPT") \
        and (rep["layout_fidelity"] >= 0.9999999)
    if not ok:
        print("\n❌ P1-B 接受闸失败：DRC/LVS 未全绿 或 版级保真度未达机器精度。")
        return 1
    print("\n✅ P1-B 接受闸通过：4×4 真实 2D 网格版图 + 主权 DRC/LVS ACCEPT + "
          "版级保真度机器精度（1.0）+ 工艺映射就绪 + GDS 落盘。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
