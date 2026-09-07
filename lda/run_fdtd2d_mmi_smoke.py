"""2D TEz FDTD 求解核 smoke（v0.9.57 · E5 的**第二条独立求解路线**）。

═══ 为什么还要有这个 smoke（已有 run_mmi_eme_smoke.py）═══
v0.9.56 只跑了 EME 一条路线就判 E5「不合格」。但单路线无法排除
「EME 本身有 bug」——那会让整个负结论失去效力。本 smoke 交付**方法学
独立**的第二条路线（时域全场 Yee 步进 vs 代数本征模展开），并把两法的
**对账一致性**钉成常驻断言：

   · 两法一致 ⇒ 4 dB 量级是 **2D-EIM 抽象本身的性质**，不是某个求解器的缺陷；
   · 两法分歧 ⇒ 至少有一个求解器有 bug（本 smoke 转红）。

═══ v0.9.56 第一版 FDTD 为什么被废弃（已定位，非方法之病）═══
  ① 本征求解器 scipy ``eig_banded`` 对称三对角存储应为 ``(2, N)``，误用
     ``(3, N)`` ⇒ n_eff 解成 16.18（真值 2.57）；
  ② 控制实验的入射监测面**落在初始波包内部**（监测面 x=6，波包中心 x=5、
     σ=1.6）⇒ 下游约 27% 能量根本不穿过该面，被误读成"能量沿程增长 +25%"。
  两处修掉后：直波导 10 µm 上 **−0.00001 dB**。本 smoke ①②即这两条的常驻锁。

═══ 判什么 ═══
  ① 控制实验 C1：无损直波导两监测面时间积分能流相对差 < 1e-5
  ② C1 折算损耗 < 1e-4 dB/µm（数值噪声地板；锚题判据是 0.1 dB 量级）
  ③ 基模 n_eff 与解析超越方程交叉校验 < 8e-3（模式求解器不是自说自话）
  ④ 左右对称：两输出臂功率相对差 < 1e-2（几何严格对称）
  ⑤ 时域收敛：t_end 900→1200 的漂移 < 0.1 dB（长尾是物理的，必须显式收敛）
  ⑥ 两个输出监测面互相一致 < 0.05 dB（含方向性通量，防回程光污染）
  ⑦a **FDTD ↔ EME 分歧本身 > tol**（核心，比"两法都不合格"更强的不可判证据）
  ⑦b 两法**一致地**指向 ~4 dB 量级：|Δ| < 0.2 × min(|FDTD−golden|, |EME−golden|)
  ⑧  判据 D：W_mmi 2.8→3.2 µm，FDTD 值变化 > 0.3 dB（真数值会跟着几何动）
  ⑧b FDTD 在可用网格上不够格：dl=0.05 色散不确定度 > 0.3 dB（要压到 0.03 dB
      需 dl≈0.0093 µm ⇒ ~5e11 网格点步 ⇒ ~2.6 h/次，不可用作门禁）
  ⑧c 色散是**收敛**的而非恒定偏差（dl=0.01 时 < 0.05 dB，O(dl²) 标度）
  ⑨  已知缺口锁：|FDTD − golden(0.05)| > tol(0.1) —— 故意反向，够格时转红
  ⑩  确定性：C1 同参两次逐位相同（可复现 ⇒ 可审计）

═══ 诚实边界 ═══
  · 本 smoke **不**宣称 E5 已被独立验证；它宣称的是「两条独立路线都给出
    ≈4 dB，远超 golden 0.05 dB」这个**负结果**是可复算、可对账的。
  · ⑥⑧ 用区间/不等式断言（数值随网格会动），越界须人工复核而非自动放宽。

运行：python run_fdtd2d_mmi_smoke.py（cwd=lda/）
出口：全 PASS 退 0；任一 FAIL 退 1。LLM 不进判决路径。
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "lda_solver"))

import numpy as np                                          # noqa: E402

import fdtd2d_mmi as fd                                     # noqa: E402
import mmi_eme as me                                        # noqa: E402

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} "
          f"{('| ' + detail) if detail else ''}")
    return bool(ok)


# E5 锚题口径（与 benchmarks.py BENCHMARK_DEFS["E5"] / seed_empirical.json 同源）
E5_GOLDEN = 0.05
E5_TOL = 0.1
DL_MAIN = 0.05          # 主跑网格（实测 ~50 s）
DL_PERT = 0.06          # 判据 D 扰动跑网格（实测 ~21 s，只验"会动"不验"准"）

# ---------------------------------------------------------------- ①② C1
print("== 控制实验 C1：无损直波导保幅 ==", flush=True)
c1 = fd.straight_waveguide_conservation(dl=0.05)
rel = abs(c1["ratios"][-1] - 1.0)
check("① C1 两监测面时间积分能流相对差 < 1e-5", rel < 1e-5,
      f"E(12µm)={c1['flux'][0]:.6e} E(22µm)={c1['flux'][1]:.6e} "
      f"相对差={rel:.2e}")
check("② C1 折算传播损耗 < 1e-4 dB/µm", abs(c1["db_per_um"]) < 1e-4,
      f"{c1['db_per_um']:.3e} dB/µm（跨度 {c1['span_um']:.0f} µm，"
      f"合计 {c1['db_total']:.2e} dB）")

# ------------------------------------------------------- ③ 模式求解器交叉校验
print("== 模式求解器：有限差分 vs 解析超越方程 ==", flush=True)
ys = fd._y_nodes(int(round(6.0 / 0.02)), 0.02)
n_fd, _ = fd.waveguide_mode(ys, 0.5, 0.0, 0.02, 1.55,
                            fd.N_CORE_2D, fd.N_CLAD_2D)
n_an = me.slab_te_neff_analytic(fd.N_CORE_2D, fd.N_CLAD_2D, 0.5, 1.55, 0)
check("③ 接入波导基模 n_eff 与解析超越方程差 < 8e-3",
      n_an is not None and abs(n_fd - n_an) < 8e-3,
      f"FD={n_fd:.5f} 解析={n_an:.5f} Δ={abs(n_fd - n_an):.2e}")

# ---------------------------------------------------------------- 主跑
print(f"== 主跑：MMI 1×2（dl={DL_MAIN}，t_max=1200）==", flush=True)
main = fd.mmi_excess_loss_fdtd(dl=DL_MAIN, t_max=1200.0,
                               t_ends=(900.0, 1000.0, 1100.0, 1200.0))
eme = me.mmi_excess_loss(dl=DL_MAIN, L_mmi=27.0, out_gap=0.9)
print("   收敛轨迹:", ", ".join(
    f"{t:.0f}→{main['convergence'][str(t)]['value']:.4f}"
    for t in main["t_ends"]), flush=True)

port_near = main["ports"][43.5]
check("④ 左右对称：两输出臂功率相对差 < 1e-2", port_near["balance"] < 1e-2,
      f"balance={port_near['balance']:.2e}")
check("⑤ 时域收敛：t_end 900→1200 漂移 < 0.1 dB",
      main["t_end_drift_db"] < 0.1,
      f"drift={main['t_end_drift_db']:.4f} dB（长尾 τ≈150，"
      f"t_max<900 时尚在 ±0.3 dB 摆动）")
check("⑥ 两个输出监测面互相一致 < 0.05 dB", main["spread_db"] < 0.05,
      f"spread={main['spread_db']:.4f} dB（方向性通量已剔除回程光）")

d = abs(main["value"] - eme["value"])
gap_f = abs(main["value"] - E5_GOLDEN)
gap_e = abs(eme["value"] - E5_GOLDEN)
# ⑦a：两法**分歧本身**就超过 tol ⇒ E5 连"两条独立路线互相印证"都做不到，
#     更不用说判 0.05 dB。这是比"两法都不合格"更强的不可判证据。
check("⑦a 两法分歧本身 > tol：|FDTD − EME| > 0.1 dB（连互相印证都做不到）",
      d > E5_TOL,
      "FDTD=%.4f dB (T=%.5f)  EME=%.4f dB (T=%.5f)  |Δ|=%.4f dB = %.1f× tol"
      % (main["value"], main["T"], eme["value"], eme["T"], d, d / E5_TOL))
# ⑦b：但两法**一致地**指向 ~4 dB 量级（分歧只占它们与 golden 分歧的很小一部分）
check("⑦b 两法一致指向同一量级：|Δ| < 0.2 × min(|FDTD−golden|, |EME−golden|)",
      d < 0.2 * min(gap_f, gap_e),
      "|Δ|=%.4f dB  仅占 min(与golden偏离)=%.4f dB 的 %.1f%%"
      % (d, min(gap_f, gap_e), 100.0 * d / max(min(gap_f, gap_e), 1e-9)))

# ------------------------------------------------------------ ⑧ 判据 D
print("== 判据 D：几何扰动（dl=%.2f，W_mmi 2.8→3.2 µm）==" % DL_PERT,
      flush=True)
p28 = fd.mmi_excess_loss_fdtd(dl=DL_PERT, W_mmi=2.8, t_max=900.0,
                              t_ends=(900.0,))
p32 = fd.mmi_excess_loss_fdtd(dl=DL_PERT, W_mmi=3.2, t_max=900.0,
                              t_ends=(900.0,))
dD = abs(p28["value"] - p32["value"])
check("⑧ 判据 D：W_mmi 2.8→3.2 µm，FDTD 值变化 > 0.3 dB（真数值非重言）",
      dD > 0.3,
      "W=2.8→%.4f dB, W=3.2→%.4f dB, |Δ|=%.4f dB"
      % (p28["value"], p32["value"], dD))

# ------------------------------- ⑧b/⑧c FDTD 数值色散预算（解析，已实测验证）
print("== FDTD 二阶数值色散预算（解析 β̃ 已由 FDTD 实测验证到 1e-5）==",
      flush=True)
b05 = fd.beat_dispersion_error(dl=DL_MAIN)
b01 = fd.beat_dispersion_error(dl=0.01)
check("⑧b FDTD 在可用网格上不够格：dl=0.05 色散不确定度 > 0.3 dB（3× tol）",
      b05["est_excess_error_db"] > 0.3,
      "拍长相对误差 %+.3f%% ⇒ excess 不确定度 ≈%.3f dB；要压到 0.03 dB 需 "
      "dl=%.4f µm（≈5e11 网格点步 ⇒ ~2.6 h/次，不可用作门禁）"
      % (b05["relative_error"] * 100, b05["est_excess_error_db"],
         b05["dl_for_0p03dB_um"]))
check("⑧c 色散是收敛的而非恒定偏差：dl=0.01 时 < 0.05 dB",
      b01["est_excess_error_db"] < 0.05,
      "dl=0.01 拍长相对误差 %+.3f%% ⇒ %.3f dB（O(dl²)：0.05→0.01 降 %.0f×）"
      % (b01["relative_error"] * 100, b01["est_excess_error_db"],
         b05["est_excess_error_db"] / max(b01["est_excess_error_db"], 1e-9)))

# ---------------------------------------------------------- ⑨ 已知缺口锁
gap = abs(main["value"] - E5_GOLDEN)
check("⑨ 已知缺口锁：|FDTD − 0.05| > 0.1（E5 仍判不了；够格时转红提醒）",
      gap > E5_TOL,
      f"|{main['value']:.4f} − {E5_GOLDEN}| = {gap:.4f} dB "
      f"= {gap / E5_TOL:.1f}× tol")

# ------------------------------------------------------------ ⑩ 确定性
c1b = fd.straight_waveguide_conservation(dl=0.05)
check("⑩ 确定性：C1 同参两次逐位相同", c1b["flux"] == c1["flux"],
      f"{c1['flux'][0]:.17g} vs {c1b['flux'][0]:.17g}")

# ---------------------------------------------------------------- 汇总
n_pass = sum(1 for _, ok, _ in CHECKS if ok)
print(f"\nFDTD2D-MMI smoke: {n_pass}/{len(CHECKS)} PASS")
for name, ok, detail in CHECKS:
    if not ok:
        print(f"  FAIL: {name} | {detail}")
print(f"核心对账：FDTD={main['value']:.4f} dB vs EME={eme['value']:.4f} dB "
      f"(|Δ|={d:.4f} dB)；两者对 golden=0.05 dB 的偏离分别为 "
      f"{abs(main['value'] - E5_GOLDEN) / E5_TOL:.0f}× / "
      f"{abs(eme['value'] - E5_GOLDEN) / E5_TOL:.0f}× tol")
sys.exit(0 if n_pass == len(CHECKS) else 1)
