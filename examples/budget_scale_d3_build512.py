# -*- coding: utf-8 -*-
"""D3 · 512 全量 grid2d 主权 build（默认快版分解 O(N^3) + O(N^3) 保真度）。
生成 GDS + 驱动清单 CSV + 指标；逐阶段自落盘，便于长任务观测。
"""
import sys, os, math, time, traceback
sys.path.insert(0, r"D:/agent_LDA/lda")
sys.path.insert(0, r"D:/agent_LDA")
import numpy as np
from lda.lda_layout import mesh_pnr as mp

LOG = r"D:/agent_LDA/examples/_d3_build512_out.txt"

def dft_matrix(N):
    n = np.arange(N); k = n.reshape(-1, 1)
    return np.exp(-2j * np.pi * k * n / N) / math.sqrt(N)

def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

try:
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("")
    N = 512
    U = dft_matrix(N)
    log(f"[512 build] 开始 N={N} t={time.strftime('%H:%M:%S')}")
    t0 = time.time()
    bs, D = mp.clements_rect_decompose(U)
    log(f"[512 build] 分解完成 tdec={time.time()-t0:.2f}s n_bs={len(bs)} "
        f"dec_fid={mp.mesh_rect_decomp_fidelity(bs,D,U):.6f}")
    t0 = time.time()
    rep = mp.build_mesh_pnr(U, layout_mode="grid2d")
    tbuild = time.time() - t0
    log(f"[512 build] build_mesh_pnr 完成 tbuild={tbuild:.1f}s layout_fid={rep['layout_fidelity']:.6f} "
        f"cols={rep['n_cols']} footprint_mm2={rep['footprint_um2']/1e6:.3f} "
        f"x_max_um={rep['x_max_um']:.0f} Vmax={rep['v_max']:.2f}")
    gds = f"D:/agent_LDA/examples/mesh{N}x{N}_grid2d.gds"
    csv = f"D:/agent_LDA/examples/mesh{N}x{N}_grid2d_drive_manifest.csv"
    for p in (gds, csv):
        if os.path.exists(p):
            os.remove(p)
    t0 = time.time()
    mp.write_mesh_gds(rep, gds)
    log(f"[512 build] GDS 写出完成 tgds={time.time()-t0:.1f}s "
        f"size={os.path.getsize(gds)//1024}KB")
    t0 = time.time()
    dm = rep["drive_manifest"]
    with open(csv, "w", encoding="utf-8") as f:
        f.write("type,rail_or_j,col,phi_rad,V\n")
        for d in dm["mzi"]:
            f.write(f"MZI,{d['j']},{d['col_c']},{d['phi_rad']:.6f},{d['V']:.4f}\n")
        for d in dm["out"]:
            f.write(f"OUT,{d['rail']},{d['rail']},{d['phi_rad']:.6f},{d['V']:.4f}\n")
    log(f"[512 build] CSV 写出完成 tcsv={time.time()-t0:.1f}s csv_rows={len(dm['mzi'])+len(dm['out'])}")
    drc = "PASS" if rep["drc_pass"] else "FAIL"
    lvs = f"{rep['lvs_verdict']}(n={rep['lvs_n_violations']})"
    log(f"[512 build] DONE DRC={drc} LVS={lvs}")
except Exception:
    log("FATAL:\n" + traceback.format_exc())
