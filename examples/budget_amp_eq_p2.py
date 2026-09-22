# -*- coding: utf-8 -*-
"""P2 幅度均衡硬件选型（VOA vs MZI）跨规模复算（轻量几何，不跑全量 build）。

直接复用 grid2d 分解 + 列分配算 x_max / pitch（与 build_mesh_pnr 同公式），
再调 amplitude_equalization_manifest + equalizer_p2_manifest。落盘 CSV + txt。
"""
import sys, math, cmath, csv
sys.path.insert(0, "D:/agent_LDA/lda")
sys.path.insert(0, "D:/agent_LDA")
from lda.lda_layout import mesh_pnr as mp
import numpy as np


def dft(n):
    w = cmath.exp(2j * math.pi / n)
    return np.array([[w ** (i * j) / math.sqrt(n) for j in range(n)]
                     for i in range(n)], dtype=complex)


def grid2d_geometry(N):
    """复刻 build_mesh_pnr grid2d 分支的 x_max / pitch / ops（不走 DRC/LVS/GDS）。"""
    U = dft(N)
    bs_list, D = mp.clements_rect_decompose(U)
    color = mp._rect_column_assignment(bs_list)
    C_max = max(color)
    Lc_margin = 6.0
    col_gap = 8.0
    mesh_x0 = 10.0
    Lu_max = 0.0
    for (j, theta, phi) in bs_list:
        Lu = mp.coupler_length_from_theta(2.0 * theta) + 2.0 * Lc_margin
        Lu_max = max(Lu_max, Lu)
    col_pitch = Lu_max + col_gap
    x_max = mesh_x0 + (C_max + 1) * col_pitch + Lc_margin + 18.0
    ops = [(int(j), float(theta), float(phi), int(color[idx]))
           for idx, (j, theta, phi) in enumerate(bs_list)]
    return {"N": N, "ops": ops, "x_max_um": x_max, "pitch_um": col_pitch}


SCEN = {
    "A": {"alpha_prop_db_cm": 1.0, "alpha_tap_db": 0.020},
    "B": {"alpha_prop_db_cm": 2.0, "alpha_tap_db": 0.050},
    "C": {"alpha_prop_db_cm": 3.0, "alpha_tap_db": 0.100},
}
NS = [128, 256, 512]
PDK_P2 = {
    # 🔴 采用 VOA 级均衡器动态范围 30 dB（ supersedes D1 §六 保守 20 dB 假设）：
    #   升级到 VOA 类即把 512C 从「均衡器动态不足」救回「均衡可行」（残余阻断项变为
    #   绝对总线损耗 56 dB 的增益预算问题，非失衡）。
    "eq_threshold_db": 3.0, "eq_range_db": 30.0,
    "equalizer_tech": "auto", "has_voa_module": True, "voa_type": "eo",
    "voa_range_db": 30.0, "voa_floor_db": 0.3, "voa_eo_v": 3.0,
    "voa_thermal_mw": 15.0, "voa_len_um": 250.0,
    "mzi_er_db": 18.0, "mzi_floor_db": 1.2, "mzi_bias_v": 3.75,
    "mzi_len_um": 1100.0,
}

rows = []
out = []
for scn, sv in SCEN.items():
    for N in NS:
        pdk = dict(PDK_P2)
        pdk["alpha_prop_db_cm"] = sv["alpha_prop_db_cm"]
        pdk["alpha_tap_db"] = sv["alpha_tap_db"]
        geo = grid2d_geometry(N)
        amp = mp.amplitude_equalization_manifest(geo, pdk)
        p2 = mp.equalizer_p2_manifest(amp, pdk)
        out.append(
            f"N={N} {scn}: verdict={amp['verdict']:22s} max_att={amp['max_att_db']:6.2f}dB | "
            f"P2 tech={p2['verdict_p2']:11s} floor={p2['floor_db']:.1f}dB "
            f"thru={p2['throughput_factor']:.3f} area={p2['total_eq_area_um2']/1e6:6.2f}mm² "
            f"ctrl={p2['total_ctrl_lines']} dump={p2['dump_ports']} "
            f"pwr={p2['total_power_mw']:.0f}mW"
        )
        rows.append({
            "N": N, "scn": scn,
            "verdict": amp["verdict"],
            "max_att_db": round(amp["max_att_db"], 3),
            "p2_tech": p2["verdict_p2"],
            "voa_type": p2["voa_type"] or "",
            "floor_db": p2["floor_db"],
            "throughput_factor": round(p2["throughput_factor"], 4),
            "total_eq_area_mm2": round(p2["total_eq_area_um2"] / 1e6, 3),
            "total_ctrl_lines": p2["total_ctrl_lines"],
            "dump_ports": p2["dump_ports"],
            "total_power_mw": round(p2["total_power_mw"], 1),
        })

with open("D:/agent_LDA/examples/amp_eq_p2_summary.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

# ---- 强制对比：VOA vs MZI（代表性规模 N=512 场景 B）----
cmp_lines = ["", "=== VOA vs MZI 强制对比（N=512 场景 B，max_att=12.80dB）===",
             "tech      floor  thru    area_mm2  ctrl  dump  power_mW  drive"]
for forced in ("voa", "mzi"):
    pdk_c = dict(PDK_P2); pdk_c["equalizer_tech"] = forced
    pdk_c["alpha_prop_db_cm"] = SCEN["B"]["alpha_prop_db_cm"]
    pdk_c["alpha_tap_db"] = SCEN["B"]["alpha_tap_db"]
    geo = grid2d_geometry(512)
    amp = mp.amplitude_equalization_manifest(geo, pdk_c)
    p2 = mp.equalizer_p2_manifest(amp, pdk_c)
    drive = p2["per_port"][0]["drive"] if p2["per_port"] else ""
    cmp_lines.append("%-9s %.1f   %.3f  %7.2f  %4d  %4d  %6.0f   %s"
                     % (p2["verdict_p2"], p2["floor_db"], p2["throughput_factor"],
                        p2["total_eq_area_um2"]/1e6, p2["total_ctrl_lines"],
                        p2["dump_ports"], p2["total_power_mw"], drive))

with open("D:/agent_LDA/examples/_amp_eq_p2_out.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n" + "\n".join(cmp_lines) + "\n")
print("\n".join(out))
print("\n".join(cmp_lines))
print("\n[OK] rows=%d -> amp_eq_p2_summary.csv / _amp_eq_p2_out.txt" % len(rows))
