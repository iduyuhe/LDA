# -*- coding: utf-8 -*-
"""D1 总线传播损耗预算（随 N 线性增长）。

从 P1-B 续 grid2d 真实几何（clements_rect_decompose + _rect_column_assignment）
抽取全宽总线长 L_bus、列距 col_pitch、每轨耦合器抽头数 deg，套用参数化损耗模型：
    IL = alpha_prop * L_bus + n_tap * alpha_tap        (dB)
给出 mean / worst / 路径间损耗方差，并对照系统容忍度给出裁定与缓解。

仅 numpy，不跑 DRC/LVS（损耗估算不依赖签核）。
"""
import sys, os, math, traceback
sys.path.insert(0, r"D:/agent_LDA/lda")   # 使顶层 lda_agent 可导入（lda_agent 在 lda/ 下）
sys.path.insert(0, r"D:/agent_LDA")
def _hook(et, ev, tb):
    with open(r"D:/agent_LDA/examples/_d1_err.txt", "w", encoding="utf-8") as f:
        f.write("".join(traceback.format_exception(et, ev, tb)))
sys.excepthook = _hook
sys.path.insert(0, r"D:/agent_LDA/examples")
os.environ["PYTHONPATH"] = r"D:/agent_LDA/lda"
import numpy as np
from lda.lda_layout.mesh_pnr import (
    clements_rect_decompose, _rect_column_assignment, coupler_length_from_theta)

Lc_margin = 6.0
col_gap = 8.0
mesh_x0 = 10.0
Ns = [4, 16, 128, 256]   # 512 由线性外推（几何 ∝N，col_pitch 饱和）
# 损耗场景 (波导传播 dB/cm, 每抽头耦合器插入 dB)
scenarios = [(1.0, 0.02), (2.0, 0.05), (3.0, 0.10)]

geom = []
for N in Ns:
    U = np.fft.fft(np.eye(N)).astype(complex) / math.sqrt(N)   # 酉 DFT(N)
    bs_list, D = clements_rect_decompose(U)
    color = _rect_column_assignment(bs_list)
    C_max = max(color)
    Lu_max = 0.0
    for (j, theta, phi) in bs_list:
        Lc = coupler_length_from_theta(2.0 * theta)
        Lu = Lc + 2.0 * Lc_margin
        Lu_max = max(Lu_max, Lu)
    col_pitch = Lu_max + col_gap
    x_max = mesh_x0 + (C_max + 1) * col_pitch + Lc_margin + 18.0
    L_bus = x_max  # 每根 rail 折线 0 -> x_max (µm)
    n_mzi = len(bs_list)
    deg = [0] * N
    for (j, _, _) in bs_list:
        deg[j] += 1
        deg[j + 1] += 1
    avg_taps = sum(deg) / N
    max_taps = max(deg)
    geom.append(dict(N=N, n_mzi=n_mzi, n_cols=C_max + 1, col_pitch=col_pitch,
                     L_bus=L_bus, avg_taps=avg_taps, max_taps=max_taps))

# 路径损耗模型：
#  - 全宽路径（跨所有列）：传播 L_bus + 抽头≈avg_taps（若在轨上切换再加，保守取 avg_taps*1.3）
#  - 最短路径（相邻 I/O，仅 1~2 列）：传播 col_pitch + 抽头≈1
#  - 路径间损耗方差 = IL_full - IL_short  （相位校准无法补偿幅度失衡）
out_lines = []
out_lines.append("=== D1 总线传播损耗预算（grid2d，参数化估算）===")
for (ap, at) in scenarios:
    out_lines.append("")
    out_lines.append("--- 场景 alpha_prop=%.1f dB/cm, alpha_tap=%.3f dB/tap ---" % (ap, at))
    out_lines.append("%4s %8s %9s %9s %9s %9s %9s %9s %9s" %
                     ("N", "L_bus(µm)", "col_pitch", "n_cols", "avg_tap",
                      "IL_mean", "IL_worst", "IL_short", "IL_var"))
    for g in geom:
        L_bus_cm = g["L_bus"] / 1e4
        col_cm = g["col_pitch"] / 1e4
        path_taps_full = g["avg_taps"] * 1.3       # 含轨切换余量
        path_taps_short = 1.0
        IL_full = ap * L_bus_cm + path_taps_full * at
        IL_short = ap * col_cm + path_taps_short * at
        IL_mean = ap * L_bus_cm + g["avg_taps"] * at
        IL_var = IL_full - IL_short
        out_lines.append("%4d %8.1f %9.2f %9d %9.1f %9.2f %9.2f %9.2f %9.2f" %
                         (g["N"], g["L_bus"], g["col_pitch"], g["n_cols"],
                          g["avg_taps"], IL_mean, IL_full, IL_short, IL_var))

# 关键分项：把方差拆成「抽头主导」vs「传播主导」
out_lines.append("")
out_lines.append("=== 方差拆解（场景 alpha_prop=2.0, alpha_tap=0.05）===")
out_lines.append("N     var_tap(dB)  var_prop(dB)  var_total(dB)")
for g in geom:
    var_tap = (g["avg_taps"] * 1.3 - 1.0) * 0.05
    var_prop = 2.0 * (g["L_bus"] - g["col_pitch"]) / 1e4
    out_lines.append("%4d  %11.2f  %12.2f  %13.2f" %
                     (g["N"], var_tap, var_prop, var_tap + var_prop))

log = "\n".join(out_lines)
with open(r"D:/agent_LDA/examples/_d1_bus_loss_out.txt", "w", encoding="utf-8") as f:
    f.write(log + "\n")
print(log)
