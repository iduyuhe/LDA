"""幅度均衡 PDK 绑定框架 · 演示/复算脚本（D1 联动）。

从 grid2d 真实几何（与 build_mesh_pnr 同公式）抽取 L_bus / col_pitch / 每轨抽头度，
喂给 amplitude_equalization_manifest，按 D1 三场景（A/B/C）给出 N=4..512 的
幅度均衡判定（phase_only / requires_amp_eq_pdk / amp_eq_infeasible）。

几何为轻量复算（与 build_mesh_pnr grid2d 分支同公式，免 GDS 重算）；生产可直接
把 build_mesh_pnr(..., pdk=...) 的返回 dict 喂给 amplitude_equalization_manifest。

输出：
  _amp_eq_pdk_out.txt   三场景 × 五规模 判定表
  amp_eq_pdk_summary.csv   汇总（每行一 (N,场景)）
  amp_eq_pdk_N256_B_detail.csv   N=256 场景 B 每端口 att_db 分布（边际案例）
"""
import sys, math, cmath, csv
sys.path.insert(0, "D:/agent_LDA/lda")
sys.path.insert(0, "D:/agent_LDA")
import numpy as np
from lda.lda_layout import mesh_pnr as mp

OUT = "D:/agent_LDA/examples/_amp_eq_pdk_out.txt"
CSV_SUM = "D:/agent_LDA/examples/amp_eq_pdk_summary.csv"
CSV_DET = "D:/agent_LDA/examples/amp_eq_pdk_N256_B_detail.csv"

MESH_X0 = 10.0
LC_MARGIN = 6.0
COL_GAP = 8.0

# D1 三场景（alpha_prop dB/cm, alpha_tap dB）
SCEN = {
    "A": (1.0, 0.020),   # 优化 SOI + 绝热 MMI
    "B": (2.0, 0.050),   # 标准 SOI + 方向耦合器
    "C": (3.0, 0.100),   # 保守/未优化
}


def grid2d_geometry(N):
    """复算 grid2d 几何（与 build_mesh_pnr layout_mode='grid2d' 同公式）。"""
    w = cmath.exp(2j * math.pi / N)
    U = np.array([[w ** (i * j) / math.sqrt(N) for j in range(N)]
                  for i in range(N)], dtype=complex)
    bs_list, D = mp.clements_rect_decompose(U)
    color = mp._rect_column_assignment(bs_list)
    C_max = max(color)
    Lu_max = 0.0
    for (j, theta, phi) in bs_list:
        Lc = mp.coupler_length_from_theta(2.0 * theta)
        Lu = Lc + 2.0 * LC_MARGIN
        Lu_max = max(Lu_max, Lu)
    col_pitch = Lu_max + COL_GAP
    x_max = MESH_X0 + (C_max + 1) * col_pitch + LC_MARGIN + 18.0
    ops = [(int(j), float(th), float(ph), int(color[idx]))
           for idx, (j, th, ph) in enumerate(bs_list)]
    return {"N": N, "ops": ops, "x_max_um": x_max, "pitch_um": col_pitch}


def main():
    lines = []
    NS = [4, 16, 128, 256, 512]
    with open(CSV_SUM, "w", newline="") as fcsv:
        w = csv.writer(fcsv)
        w.writerow(["N", "scenario", "alpha_prop_db_cm", "alpha_tap_db",
                    "IL_mean_db", "IL_var_ports_db", "IL_var_io_db",
                    "IL_var_binding_db", "max_att_db", "eq_required",
                    "eq_feasible", "verdict"])
        header = (f"{'N':>4} {'scn':>3} {'a_prop':>6} {'a_tap':>6} "
                  f"{'ILmean':>7} {'var_p':>7} {'var_io':>7} {'var_b':>7} "
                  f"{'maxatt':>7} {'req?':>5} {'feas?':>5} {'verdict':>20}")
        lines.append(header)
        lines.append("-" * len(header))
        det_w = None
        for N in NS:
            geo = grid2d_geometry(N)
            for scn, (ap, at) in SCEN.items():
                pdk = {"alpha_prop_db_cm": ap, "alpha_tap_db": at,
                       "eq_threshold_db": 3.0, "eq_range_db": 20.0}
                m = mp.amplitude_equalization_manifest(geo, pdk)
                w.writerow([N, scn, ap, at,
                            f"{m['IL_mean_db']:.3f}", f"{m['IL_var_ports_db']:.3f}",
                            f"{m['IL_var_io_db']:.3f}", f"{m['IL_var_binding_db']:.3f}",
                            f"{m['max_att_db']:.3f}", m['eq_required'],
                            m['eq_feasible'], m['verdict']])
                lines.append(
                    f"{N:>4} {scn:>3} {ap:>6.1f} {at:>6.3f} "
                    f"{m['IL_mean_db']:>7.2f} {m['IL_var_ports_db']:>7.2f} "
                    f"{m['IL_var_io_db']:>7.2f} {m['IL_var_binding_db']:>7.2f} "
                    f"{m['max_att_db']:>7.2f} {str(m['eq_required']):>5} "
                    f"{str(m['eq_feasible']):>5} {m['verdict']:>20}")
                # N=256 场景 B 每端口明细
                if N == 256 and scn == "B":
                    with open(CSV_DET, "w", newline="") as fd:
                        dw = csv.writer(fd)
                        dw.writerow(["port", "L_path_um", "n_tap", "IL_db",
                                     "IL_linear", "att_db", "needs_eq"])
                        for p in m["per_port"]:
                            dw.writerow([p["port"], f"{p['L_path_um']:.1f}",
                                         p["n_tap"], f"{p['IL_db']:.3f}",
                                         f"{p['IL_linear']:.4f}",
                                         f"{p['att_db']:.3f}", p["needs_eq"]])
    txt = "\n".join(lines)
    open(OUT, "w").write(txt + "\n")
    print(txt)
    print(f"\n wrote {CSV_SUM}, {CSV_DET}, {OUT}")


if __name__ == "__main__":
    main()
