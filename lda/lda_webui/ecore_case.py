"""电子计算芯片案例卡（WebUI 只读端点数据源）· D-155 建卡 → D-160（E10）升 E1–E9 →
E11-e 升 E1–E11 → E12-e 升 E1–E12 → **D-173（E13-e）升 E1–E13 全链**。

═══════════════════════════════════════════════════════════════════════════
定位
═══════════════════════════════════════════════════════════════════════════
电子计算征程「吃狗粮」**E1…E13（D-150…D-172）** 的**只读案例**：用 LDA 亲手设计一颗
**电子计算芯片**（模拟计算核 = 模拟 MVM 交叉阵列，电子版的「光子 MZI 网格」），走完全链路：

    晶体管级模型 → 电路仿真 → 阵列 → 数据通路 → 规模对标 → 能力硬化        （E1–E5 · 电路级）
    → 版图与几何签核（首次直出真 GDS）                                      （E6）
    → 寄生提取与后仿（IR drop / sneak path）                                （E7）
    → 非理想/失配/噪声 + 校准层级                                           （E8）
    → 千级阵列规模压力 + 同族维度诚实对标                                   （E9）
    → E10 平台硬化 + 案例卡升级 + 对外物料 + 生产部署                       （D-160）
    → E11 器件级内核接线（口径同步 / 接缝勘查 / MOSCAP 内核桥 / 失效边界）  （D-161…D-164）
    → E12 2D MOS 求解器（短沟道效应：算不了 → 算得了）                      （D-166…D-168）
    → E13 2D MOS 漂移扩散输运（I–V / 亚阈值摆幅：G-K 的「不产 I-V」关掉）   （D-170…D-172）

与 `/api/qchip_demo`（光量子 LOQC）、`/api/schip_demo`（超导 transmon）、
`/api/pchip_demo`（硅光张量核）**并列**：四条物理/器件路线在 LDA 均已吃狗粮。
本卡回答的是**同一个平台问题**——「同一条链路，换一种器件（电子/CMOS），是否还站得住？」

🔴 **零重计算**：本模块**不跑电路仿真、不 import 求解器/numpy** —— 全部数字取自
① 静态里程碑/结论（人工登记、可回溯到门禁与 report）② **纯 math 闭式**现算
⇒ **无 DoS 面**，故**免登录、不进 HEAVY_POST_PATHS**。

🔴 **不伪装实测 / 不报 fabricated 能效**：`verdict` 恒为 `DESIGN_VERIFIED`
（**非** ACCEPT/PASS），返回体自带 `honest_note`；本卡**不报任何 TOPS/TOPS-W/fJ/op**。
"""
from __future__ import annotations

import ast
import math
import os
from typing import Any, Dict, List, Optional

__all__ = [
    "CASE_ID", "ECORE_HONEST_NOTE", "MILESTONES", "FINDINGS", "GAPS",
    "SCALE_TIERS", "SCALE_PRESSURE_TIERS", "SCALE_CEILING",
    "MOSFET_FACTS", "KEY_METRICS", "LAYOUT_FACTS", "PARASITIC_FACTS",
    "MISMATCH_FACTS", "SCALE_FACTS", "GATE_CHECKS_TOTAL", "PROBE_CHECKS_TOTAL",
    "DEVICE_PDE_FACTS", "DEVICE_LIMITS_FACTS", "DEVICE_2D_FACTS",
    "DEVICE_TRANSPORT_FACTS", "DEVICE_PERIPHERY_FACTS",
    "crossbar_capacity", "quant_error_rel_bound", "layout_elements_flat",
    "layout_elements_hier", "hier_compression_ratio", "sheet_resistance_ohm_per_sq",
    "wire_resistance_ohm", "pelgrom_sigma_vth_mv", "pelgrom_sigma_beta_pct",
    "elmore_tau_rc", "sigma_rel_vs_n", "case_card", "run_selfchecks",
]

# ═══════════════════════════ 常量（与平台模块同源）═══════════════════════════
CASE_ID = "LDA-E · 电子计算芯片（模拟计算核 / MVM 交叉阵列）· E1–E14 全链"

#: 长沟道 NMOS 模型参数（E1 · D-150 · `lda_l2.ecore.mosfet.NmosParams` 默认值；公开典型量级占位）
MOSFET_FACTS = {
    "kp_a_per_v2": 120e-6,        # 跨导参数 KP = µn·Cox（A/V²）
    "vth0_v": 0.4,                # 零偏阈值电压
    "lambda_per_v": 0.02,         # 沟道长度调制
    "w_over_l": 10.0,             # 宽长比（占位）
    "model": "长沟道平方律（截止/三极管/饱和三区 + gm/gds 解析）· Level-1/Shichman–Hodges",
}

#: 关键实测（门禁值 · 可回溯到 run_ecore_e*_smoke）
KEY_METRICS = {
    # E1 · MNA 电路仿真器精度（vs 闭式）
    "mna_rc_transient_err": 2e-4,        # RC 瞬态 vs 指数闭式
    "mna_ac_err": 1e-13,                 # RC 交流 vs 闭式转移函数
    # E2 · 交叉阵列（MNA vs 闭式 golden）
    "xbar_ideal_8x8_err": 2e-4,          # 理想 TIA 路径
    "xbar_transistor_4x4_err": 2.4e-4,   # NMOS 三极管权重路径
    "ota_gain_20k": 7.5, "ota_gain_30k": 10.4,   # 晶体管级 OTA 开环增益（∝ Rd）
    # E3 · MVM 数据通路（vs 全精度数字 golden）
    "datapath_single_8bit_err": 0.0122,
    "datapath_mlp_2layer_6bit_err": 0.044,
    "datapath_tiling_err": 0.0,
    # E4 · 规模律
    "scale_rel_err_32": 0.018, "scale_rel_err_256": 0.030,
    "scale_abs_err_32": 0.08, "scale_abs_err_256": 0.54,
    "max_synapses_tested": 65536,
    # E6 · 版图与几何签核
    "layout_gds_roundtrip_match": True,  # AREF 展开 ≡ flat（120 ≡ 120 · 464 ≡ 464）
    "layout_wl_extract_um": (1.20, 0.30),
    # E7 · 寄生后仿
    "parasitic_ir_drop_rel_32": 0.270,   # N=32 最坏列相对误差
    "parasitic_sneak_ratio_16": 7.26,    # N=16 half-select 旁路比
    "parasitic_r0_vs_golden_max_abs": 1.08e-19,   # R=0 ⇒ 精确复现解析 golden
    # E8 · 失配 / 噪声 / 校准
    "mismatch_mc_sigma_rel_8x8": 0.00654,
    "mismatch_sqrtN_invariant": 0.0186,  # σ_rel·√N 近恒定（1/√N 律）
    "calib_L0_rel": 0.01696, "calib_L1_rel": 0.00212, "calib_L2_rel": 0.000743,
    # E9 · 千级规模压力
    "scale_hier_gds_bytes_1024": 86600,  # 1024×1024 层次化 GDS 字节
    "scale_hier_top_records_1024": 2049,
    "scale_compression_1024": 3571.0,    # 层次化压缩比（vs 物化）
}

#: E6 · 版图与几何签核（`lda_l2.ecore.elayers` + `layout`）
LAYOUT_FACTS = {
    "layers": "DIFF=20 / POLY=21 / CONT=22 / M1=23 / VIA1=24 / M2=25",
    "cell_elements": 7,                  # DIFF_D + DIFF_S + POLY 栅 + CONT×2 + M1 焊垫 + VIA1
    "arr_4x4_elements": 120, "arr_4x4_footprint_um": (8.40, 8.90),
    "arr_8x8_elements": 464,
    "gds_bytes_4x4": 936,
    "gds_top_records_4x4": 9,            # 层次化（cell + AREF）vs flat 120
    "w_um": 1.20, "l_um": 0.30,          # 几何回提（逐单元一致）
    "edrc_rules": 4,                     # 线宽 / 间距 / 接触孔包围 / 最小面积
    "elvs_checks": 7,                    # 连通分量 / 短路 / 悬空桥 / 端口实现 / 管数 / W·L / 零悬空
    "note": "电子芯片**首次直出真 GDS**（平台自写 GDSII 编码器 · AREF 层次化）；"
            "沟道区被 POLY 断开为 DIFF_D/DIFF_S 属**教学级简化**；几何判据为 **bbox 级**",
}

#: E7 · 寄生提取与后仿（`lda_l2.ecore.parasitic`）
PARASITIC_FACTS = {
    "sheet_r_m1_ohm_sq": 0.084,          # R□ = ρ_Cu / t_M1
    "r_row_seg_ohm": 0.504,              # 每段行线电阻（按 E6 节距/线宽提）
    "r_row_total_8x8_ohm": 3.53,
    "tau_row_s": 3.1e-15,                # Elmore 行线延迟
    "ir_drop_rel": [(4, 0.0042), (16, 0.0806), (32, 0.270)],   # 最坏列相对误差
    "sneak_ratio": [(4, 1.29), (8, 3.27), (16, 7.26)],         # half-select 旁路/理想比
    "r0_vs_golden_max_abs": 1.08e-19,    # R=0 网络 ≡ 解析 golden（验证网络装配 + 求解）
    "formulae": "R = ρL/(W·t) ≡ R□·L/W · C = ε₀ε_r·W/d · τ_Elmore → R·C/2",
    "note": "**IR drop 是模拟 MVM 第一号规模墙**（∝N² 量级）· **sneak 是拓扑效应**"
            "（R=0 时仍存在，与 IR drop 解耦）；`r_leak` 为**数值钉扎**（防浮空奇异），"
            "**非物理漏电**；提取为一阶几何闭式（无 3D 场解）· 后仿为 DC",
}

#: E8 · 非理想 / 失配 / 噪声 + 校准层级（`lda_l2.ecore.mismatch`）
MISMATCH_FACTS = {
    "process": {"a_vt_mv_um": 3.0, "a_beta_pct_um": 1.0, "vth_tc_mv_per_k": -1.0,
                "mu_temp_exponent": -1.5, "t_ref_c": 25.0},
    "sigma_vth_mv": 5.00,                # Pelgrom @ W/L = 1.20/0.30 µm
    "sigma_beta_rel_pct": 1.67,
    "vth_shift_25_85_mv": -60.0,         # 温度一阶
    "mobility_ratio_85_25": 0.760,
    "thermal_noise_psd_a2_per_hz": 1.098e-23,   # 4kTγg_m @ g_m = 1 mS
    "mc_sigma_rel_8x8": 0.00654,
    "sqrt_n_invariant": 0.0186,          # σ_rel·√N ≈ 恒定 ⇒ σ_rel ∝ 1/√N
    "calibration": {"L0_rel": 0.01696, "L1_rel": 0.00212, "L2_rel": 0.000743,
                    "L1": "列增益校准（消**系统项**：列热梯度/共模）",
                    "L2": "逐单元校准（压**随机项** · 残差由测量噪声决定）"},
    "note": "随机失配被 **1/√N 平均掉**（小阵列更脆弱）· **系统项不会被平均掉** ⇒ 必须列级校准；"
            "只有逐单元校准才压随机项 ⇒ **校准精度决定模拟 CIM 的有效位数上限**",
}

#: E9 · 千级阵列规模压力 + 同族维度诚实对标（`lda_l2.ecore.array_scale`）
SCALE_FACTS = {
    "hier_gds_bytes_1024": 86600,        # 1024×1024：层次化出图（**不物化 N²**）
    "hier_top_records_1024": 2049,
    "compression_1024": 3571.0,
    "structural_count_256": 459264,      # AREF 元数据结构性核算 ≡ flat 闭式
    "algorithms": "版图：cell + AREF 层次化（O(N)）· 后仿：一维三对角 Thomas（O(N)）",
    "one_d_vs_two_d": "1D 模型 ≡ E7 的 2D 稠密 MNA（最坏列口径 · 相对差 ≤1.7e-13）",
    "note": "1D 行线模型**忽略列线电阻**（二阶项，已披露）；千级阵列是**设计期版图与规模律**，非流片",
}

#: 规模档（E4 实测 · 8bit · 数据通路）
SCALE_TIERS = [
    {"n": 32, "synapses": 1024, "rel_err": 0.018, "abs_err": 0.08},
    {"n": 64, "synapses": 4096, "rel_err": 0.027, "abs_err": 0.15},
    {"n": 128, "synapses": 16384, "rel_err": 0.024, "abs_err": 0.29},
    {"n": 256, "synapses": 65536, "rel_err": 0.030, "abs_err": 0.54},
]

#: 规模压力档（E9 实测 · **三重规模律**）
SCALE_PRESSURE_TIERS = [
    {"n": 16, "synapses": 256, "ir_drop_rel": 0.0375, "area_mm2": 0.0014,
     "sigma_rel": 0.004209, "tau_elmore_s": 1.34e-14},
    {"n": 64, "synapses": 4096, "ir_drop_rel": 0.152, "area_mm2": 0.0236,
     "sigma_rel": 0.001052, "tau_elmore_s": 2.15e-13},
    {"n": 256, "synapses": 65536, "ir_drop_rel": 0.549, "area_mm2": 0.3772,
     "sigma_rel": 0.000263, "tau_elmore_s": 3.44e-12},
    {"n": 1024, "synapses": 1048576, "ir_drop_rel": 0.956, "area_mm2": 6.035,
     "sigma_rel": 0.0000526, "tau_elmore_s": 5.50e-11},
]

#: 可及规模上界（按输出误差预算二分反解 · E9 实测）
SCALE_CEILING = [
    {"budget_rel": 0.10, "max_rows": 26},
    {"budget_rel": 0.05, "max_rows": 18},
    {"budget_rel": 0.02, "max_rows": 11},
    {"budget_rel": 0.01, "max_rows": 8},
]

#: 公开 landmark（A级公开来源·照录·未验证·仅背景坐标；不作 LDA 成就值）
#: E11-c 器件级内核桥（`ecore/device_pde.py` · 桥接平台器件级 T1 内核 `lda_solver/mos_1d.py`）
#: 🔴 卡内硬编码（本模块**零 numpy/零重计算**）；与模块实测值的一致性由
#:    `run_ecore_case_smoke.py` 的 B16/B17 **交叉核对**（真拉平，非自洽）。
DEVICE_PDE_FACTS = {
    "kernel": "MOSCAP（金属-氧化层-半导体）1D 自洽泊松 · `lda_solver/mos_1d.py`（E11-c 新增）",
    "bridge": "`ecore/device_pde.py`（量纲桥 + golden/candidate 分离 + G-3 参数自洽性报告）",
    "golden_a": "Sze 完整 Q_s 闭式（含反型层 + 玻尔兹曼尾）",
    "golden_b": "教科书耗尽近似 V_th 式",
    "vth_golden_v": 0.4260,
    "vth_pde_v": 0.426036,
    "vth_rel_err_pct": 1.6e-4,
    "qs_cross_point_worst_rel_pct": 0.0108,
    "qs_cross_point_span_phi_f": [0.5, 2.5],
    "tox_sweep_nm": [2.0, 4.0, 8.0],
    "tox_sweep_vth_v": [0.3297, 0.4260, 0.6187],
    "dim_bridge": "8.6 fF/µm² ≡ 8.6e-3 F/m²（与 4 nm SiO₂ 教科书值差 0.38%）",
    "param_consistency": {
        "mu_implied_cm2_vs": 140.0, "mu_typical_cm2_vs": 500.0,
        "ratio": 3.58, "consistent": False,
        "note": "`kp` 与 `C_ox` 两处占位值反推的 µ 与体硅典型量级差 3.58× ⇒ **显式暴露、不强行统一**"
                "（统一数值会改动 E1–E10 全部已上线数字）",
    },
    "no_replace": "🔴 物理 V_th 只作**并行第二器件模型 + 可核参数建议**；`NmosParams` 默认值逐位不变。",
    "oracle_semantics": "golden = 教科书闭式（`is_oracle=True`）；candidate = PDE 数值解（`is_oracle=False`）"
                        "；判据方向 = PDE 收敛到闭式。",
}

#: E11-d 失效边界（`ecore/device_limits.py` · 边界说明书，不新增能力）
DEVICE_LIMITS_FACTS = {
    "numerical_window_phi_f": [-0.54, 2.54],
    "physical_window_phi_f": [-0.286, 2.286],
    "physical_over_numerical_halfwidth": 0.835,
    "bottleneck": "物理模型（1D 无源漏 + 玻尔兹曼）—— **物理先失效、数值后崩**；细化网格推不动真正的边界",
    "grid_dependence_phi_f": {"0.05nm": [-0.40, 2.40], "0.02nm": [-0.50, 2.50],
                              "note": "数值窗口**随网格变宽**；物理窗口**与网格无关**"},
    "gap_at_L65nm": {"rolloff_frac_of_vth": 0.379, "dibl_frac_of_vth": 0.031,
                     "rolloff_dvth_v": -0.161, "vth_long_channel_v": 0.4260},
    "not_computed_by_lda": ["短沟道 V_th roll-off", "DIBL", "速度饱和", "迁移率退化"],
    "literature_only": "🔴 上述四项在 **E11-d 当时**均为**文献经验式缺口量化**（每项 `computed_by_lda=False`），"
                       "**不是 LDA 的计算结果**。🔴 **口径已换代（E13-e 订正）**：其中 **roll-off / DIBL "
                       "已由 E12 的 2D MOS 求解器、I–V / 亚阈值摆幅已由 E13 的 2D 漂移扩散输运**补上"
                       "（`computed_by_lda=True`）⇒ 本字段仅作**可追溯**记录，**不代表当前能力状态**；"
                       "仍在文献侧的是**速度饱和 / 迁移率退化**（DD 框架之外，见 `device_transport` 的"
                       "能力闭合表）。",
}

#: E12 2D MOS 求解器（`lda_solver/mos_2d.py` + `ecore/device_2d.py`）
#: 🔴 卡内硬编码（本模块**零 numpy/零重计算**）；与模块实测值的一致性由
#:    `run_ecore_case_smoke.py` 的 B18 **交叉核对**（真拉平，非自洽）。
DEVICE_2D_FACTS = {
    "kernel": "**四端（栅/源/漏/衬底）2D MOSFET 自洽泊松** · `lda_solver/mos_2d.py`（E12 新增）",
    "bridge": "`ecore/device_2d.py`（量纲桥 + 长沟道交叉验证 + roll-off/DIBL 报告 + 能力闭合表）",
    "numerics": "变系数**有限体积**离散（**按面中点判介质** ⇒ Si/SiO₂ 界面离散精确、"
                "C_ox 恰为 ε_ox/t_ox）+ **分段四端边界条件** + **电子准费米势分裂**"
                "（源侧 0 / 漏侧 V_d）+ 阻尼牛顿 / continuation",
    "golden": "教科书 1D 长沟道耗尽式（`device_pde.physics_vth_closed` · E11-c 单一定义）",
    "candidate": "2D 数值泊松解（`is_oracle=False`）—— 判据方向：**长沟道极限 2D → 1D 闭式**",
    "long_channel": {"Lg_nm": 1000.0, "vth_2d_v": 0.4239, "vth_golden_v": 0.4260,
                     "abs_diff_mv": -2.11, "rel_err_pct": 0.496},
    "rolloff": {"Ls_nm": [65.0, 100.0, 250.0],
                "dvth_vs_golden_mv": [-176.3, -101.3, -14.0],
                "yau_literature_mv": [-161.3, -104.9, -41.9],
                "ratio_at_65nm": 1.09,
                "note": "同量级**对照**（文献式非 golden）；L↑ 单调收敛"},
    "dibl": {"Lg_nm": 65.0, "dibl_mv_per_v": 153.6,
             "r2_exp_law": 0.99863, "decay_length_nm": 68.9,
             "literature_dibl_mv_per_v": 13.0,
             "literature_note": "🔴 文献经验式给 13.0 mV/V，与 2D 解 **差 ~12×** ⇒ 文献式只作"
                                "**存在性**坐标，**不作数值标定**（这正是 E11-d 结论的印证："
                                "文献式是量级估算，2D 解才是自产能力）"},
    "natural_length_nm": {"lda_2d": 18.97, "literature": 18.97, "same_formula": True},
    "capability_closure": {"closed": 3, "still_unavailable": 3,
                           "closed_items": ["V_th roll-off", "DIBL", "自然长度校验"],
                           "still_items": ["I–V / 亚阈值摆幅（**已由 E13 闭合** —— 见 `device_transport`）",
                                           "工艺角 / PDK / 硅验证（**T2 永久锁**）",
                                           "LDD / halo / 应力 / 量子修正"],
                           "note": "🔴 本表为 **E12 当时的**能力闭合表（闭合 3 / 仍不可用 3）；"
                                   "其中第一条「I–V / 亚阈值摆幅」**已由 E13 的 2D 漂移扩散输运闭合**"
                                   "（E13 侧另有一张 4/4 的闭合表）⇒ 本表仅作**可追溯**记录。"},
    "transport_closure": "🔴 **（E12 段原口径）** 本段为**准平衡静电求解、不含漂移扩散输运 ⇒ "
                         "当时不产 I-V**；「算得了」当时仅限**静电量**（roll-off / DIBL / 自然长度）。"
                         "🔴 **该缺口已由 E13 闭合**（`lda_solver/mos_2d_transport.py` + "
                         "`ecore/device_transport.py`：稳态漂移扩散 + Gummel ⇒ I–V / 亚阈值摆幅**可从"
                         "数值解提取**）⇒ 本字段仅作**可追溯**记录，**不代表当前能力状态**；"
                         "E13 之后**新的**内在边界见 `device_transport`（漂移扩散框架的硬边界）。",
    "oracle_semantics": "golden = 教科书 1D 闭式（`is_oracle=True`）；candidate = 2D 数值解"
                        "（`is_oracle=False`）；**只允许「长沟道 2D → 1D」方向，绝不反向**"
                        "（用 2D 当标定真值会当场破红线）。",
}

#: E13 2D MOS 漂移扩散输运（`lda_solver/mos_2d_transport.py` + `ecore/device_transport.py`）
#: 🔴 卡内硬编码（本模块**零 numpy/零重计算**）；与模块实测值的一致性由
#:    `run_ecore_case_smoke.py` 的 B19 **交叉核对**（真拉平，非自洽）。
#: ⚠️ SS 值随 **V_g 扫描点数**变化（拟合窗口）⇒ 卡内数字与 B19 核对参数**成对锁死**
#:    （口径 = `default_vg_list(n=13)`）。
DEVICE_TRANSPORT_FACTS = {
    "kernel": "**2D MOS 稳态漂移扩散输运** · `lda_solver/mos_2d_transport.py`（E13 新增）",
    "bridge": "`ecore/device_transport.py`（量纲桥复用 E11-c + G1–G6 判据 + 能力闭合表 · "
              "**惰性导入** scipy 内核 ⇒ 无 scipy 环境仍可 import）",
    "numerics": "**Si-only 掩码**稳态连续性（Scharfetter–Gummel 离散；氧化层节点逐出未知量集 ⇒ "
                "Si↔SiO₂ 界面自然 Neumann）+ **接触准费米势 BC**（φ_n = φ_p = V_c ⇒ n·p = n_i²，"
                "统一式自动给出 n⁺ 区 n=N_SD / p 区 p=N_A）+ Gummel 交替（非线性泊松 ⟷ 连续性）"
                "+ 终端电流（SG 守恒截面）",
    "golden_a": "**SS 热极限** `(kT/q)·ln10`—— **物理定律锚（不等式）**：扩散机制下 SS 不可能低于它",
    "golden_b": "**教科书 SS 闭式** `(kT/q)ln10·(1+Cd/Cox)`（耗尽近似 · 含体效应）",
    "candidate": "2D 漂移扩散数值解（`is_oracle=False`）",
    "thermal_limit_mv_dec": 59.53,
    "ss_closed_platform_mv_dec": 66.41,
    "cd_over_cox": 0.1156,
    "long_channel": {"Lg_nm": 1000.0, "ss_2d_mv_dec": 68.08, "ss_closed_mv_dec": 66.41,
                     "rel_err_pct": 2.52},
    "ss_vs_length": {"Ls_nm": [65.0, 100.0, 250.0, 1000.0],
                     "ss_mv_dec": [226.9, 88.0, 69.5, 68.1],
                     "note": "L↓ ⇒ SS↑（短沟道静电控制退化）· 与 E12 的 roll-off / DIBL **同向**"},
    "ss_at_100nm_mv_dec": 88.0,
    "conservation": {"worst_rel": 5.4e-5, "n_checked": 8, "n_total": 13,
                     "i_floor_a_per_m": 1e-3,
                     "note": "🔴 **相对判据必须带绝对下限**：深亚阈值电流可到 1e-10 A/m，"
                             "此时相对差被数值噪声主导（rel 可达 >1，绝对差仅 ~1e-9 A/m）"},
    "id_vd": {"V_d": [0.05, 0.2, 0.5, 1.0], "I_d_a_per_m": [265.7, 882.9, 1428.1, 1605.3],
              "note": "输出特性：低 V_d 线性 → 高 V_d 趋饱和（定性物理）"},
    "vth_two_methods": {"cc_v": 0.2475, "surface_potential_v": 0.3241, "abs_diff_mv": -76.6,
                        "note": "🔴 两法**均 `is_oracle=False`** · **互不充当 ORACLE**；口径不同"
                                "（恒流法在弱反型 I_ref；表面势法在 ψ_s=+φ_F）⇒ 系统性差异"},
    "capability_closure": {"closed": 4, "still": 4,
                           "closed_items": ["I–V 特性（I_d(V_g, V_d)）", "亚阈值摆幅 SS",
                                            "恒定电流法 V_th", "I_on / I_off"],
                           "still_items": ["量子修正 / 速度饱和 / 隧穿 / 弹道输运",
                                           "真实迁移率（场依赖退化 / 表面散射）",
                                           "工艺角 / PDK 标定 / 硅验证（**T2 永久锁**）",
                                           "LDD / halo / 应变 / 栅重叠 / 温度扫描 / AC·瞬态"]},
    "ss_target_note": "🔴 **「SS → 60 mV/dec」是错的目标**：`60` 只在 `Cd → 0`（FD-SOI / 双栅）时达到；"
                      "**体硅器件因体效应收敛到 `60·(1+Cd/Cox)` 的平台**（本例 ≈ 66.4）"
                      "⇒ 60 的角色是**硬下限（不等式 G1）**，**不是渐近目标**。",
    "honest_boundary": "🔴 **仍是漂移扩散（DD）框架**：不含量子修正 / 速度饱和 / 带间与栅隧穿 / "
                       "弹道输运；**迁移率为常数** ⇒ `I_on` 绝对值**不可当器件性能**"
                       "（**深亚阈值 SS 不受影响** —— 这正是 G1/G2 仍严格成立的原因 —— "
                       "但 I_on 偏高、I_off 偏低）；无 LDD/halo/应变/栅重叠；参数为公开典型量级占位"
                       "（**非 PDK**）；2D 仿真 = **每单位宽度电流（A/m）**；不报 TOPS/TOPS-W/fJ/op。",
    "oracle_semantics": "golden_A = **物理定律锚（不等式）** · golden_B = **教科书闭式**；"
                        "candidate = 2D 数值解（`is_oracle=False`）；V_th 双法为**内部交叉**"
                        "（两法均非 ORACLE）。",
}

#: E14 真 DAC / ADC / 行驱动外设（`ecore/converter.py` + `ecore/periphery.py`）
#: 🔴 卡内硬编码（本模块**零 numpy/零重计算**）；与模块实测值的一致性由
#:    `run_ecore_case_smoke.py` 的 B20 **交叉核对**（真拉平，非自洽）。
DEVICE_PERIPHERY_FACTS = {
    "kernel": "**真转换器电路 + 行驱动**：`ecore/converter.py`（R-2R 梯形 DAC + NMOS 模拟开关 · "
              "SAR/CDAC 电荷重分配 ADC · 采样保持）· `ecore/periphery.py`（行驱动 + 端到端系统链）",
    "why": "E1–E13 的 DAC/ADC 只是**行为级均匀量化模型**、行线由**理想电压源**钉住 ⇒ "
           "外围电路的精度 / 速度 / 负载代价从未计入。本段补上**真电路**，把「设计链」补成「系统链」。",
    "dac": {"topology": "R-2R 梯形：v[k]--R--v[k+1] · v[k]--2R--s[k]（开关接 V_ref / GND）· "
                        "v[N-1]--2R--GND（终端）",
            "n_bits": 8, "codes_scanned": 256,
            "max_abs_err_lsb": 0.0265, "inl_lsb_max": 0.0265, "monotone": True,
            "ron_ohm": 6.4, "ron_over_r": 0.00064,
            "sub_golden_max_abs_v": 1.1e-16,
            "switch_effect": "W/L ↑ ⇒ R_on ↓ ⇒ 误差 ↓（W/L=2000 → 0.0017 LSB；50 → 0.0660 LSB）",
            "note": "**开关导通电阻是 DAC 精度上限的一个来源**（行为级量化模型看不见）"},
    "adc": {"topology": "SAR + CDAC 电荷重分配（C_k = 2^k·C_u + 哑元 ⇒ C_total = 2^N·C_u）",
            "why_transient": "🔴 **电容在 DC 下开路** ⇒ DC 解里顶板电位与电荷分配**无关**"
                             "（拓扑退化）；后向欧拉伴随模型 ⇒ `Σ C_k(V_top−V_bk) = const`"
                             "（**电荷严格守恒**）⇒ 一步瞬态 = **精确**电荷守恒解",
            "charge_conservation_rel": 3.9e-12,
            "sar_max_err_lsb": 1, "sar_samples": 16,
            "comparator": "🔴 **判决器抽象**（有限增益 + 失调 + 噪声）—— **非晶体管级比较器**"},
    "sample_hold": {"tau_s": 1.0e-9,
                    "rel_err_vs_discrete": 5.6e-16,
                    "discretization_rel": [2.27e-3, 1.10e-3, 5.40e-4],
                    "discretization_steps": [40, 80, 160],
                    "note": "瞬态 ⟷ **后向欧拉离散闭式**（同口径 · 机器精度）；与**连续**闭式的偏差是"
                            "**离散化误差**，随步长加密单调降（**O(dt) 一阶**）—— 两个口径必须分清"},
    "row_driver": {"formula": "v_load = v_in·A/(1 + A + R_ol/R_L)",
                   "closed_loop_rout": "R_oc = R_ol/(1+A)（反馈降输出阻抗 1+A 倍）",
                   "mna_rel_err": 1.4e-16},
    "scale_ceiling": {"budget_rel": 0.05, "r_out_cl_ohm": [0.0, 1.0, 5.0, 20.0],
                      "n_max": [20, 17, 10, 3],
                      "e9_limit_match_max_abs": 0.0,
                      "note": "🔴 **器件级参数第一次反馈到规模律**：`R_oc` ↑ ⇒ 可及行数 ↓；"
                              "`R_oc = 0` 时与 E9 `row_line_profile` **逐位一致**（max|Δ| = 0）"},
    "row_system_term": {"spread_with_driver": 8.889e-4, "spread_ideal_driver": 0.0,
                        "note": "驱动负载调整引入**按行增益误差**（行负载 Σ_j g_ij 随行变）——"
                                "与 E8 的**列系统项**同型，**不会被 Monte Carlo 平均掉**"},
    "system_chain": {"max_rel_err_real": 3.019e-3, "max_rel_err_ideal": 1.0e-9,
                     "note": "DAC→行驱动→阵列→TIA→ADC vs E3 数字全精度通路"},
    "platform_defect": {
        "what": "`mna.Circuit.vcvs` 的 **实际极性与 docstring 相反**"
                "（声明 `V_out = gain·(V_cp−V_cn)`，实际 `gain·(V_cn−V_cp)`）",
        "probe_v": -1000.0,
        "why_not_fixed": "E1–E13 全部已上线数字（含 E2 ideal-TIA 虚地电路）建立其上 ⇒ "
                         "按保护性约束**不改 mna**，改为**适配 + 显式登记 + 判据锁死**",
        "still_valid": "E2/E3 结论仍成立：TIA 虚地是 `|A|→∞` 的**极限**，符号只改变放大器输出"
                       "**定向**、不改变虚地机制",
    },
    "honest_boundary": "🔴 **比较器是判决器抽象**（非晶体管级）· **CDAC 底板开关用理想电压源抽象**"
                       "（DAC 侧用真 NMOS 开关以暴露 R_on）· **行驱动器是 VCVS + 开环输出电阻宏模型**"
                       "（非晶体管级运放）· 电阻 / 电容为理想值（**不建匹配网络**）· R_on 取三极管区闭式 · "
                       "电荷注入 / 时钟馈通只给量级 · 阵列用 E2 已验证的解析列电流模型 · "
                       "参数为公开典型量级占位（**非 PDK**）· 不做流片 · **不报 TOPS/TOPS-W/fJ/op**。",
    "is_oracle": False,
}

LANDMARKS_BRIEF = [
    {"who": "Mythic AI", "item": "M1076 AMP：analog compute-in-memory MVM 交叉阵列"
                                 "（flash array + on-die ADC）· up to 25 TOPS · typ. 3–4 W · "
                                 "76 AMP tiles · up to 80M weights · INT4/INT8（厂商宣称）",
     "source": "https://mythic.ai/?p=134/"},
]

ECORE_HONEST_NOTE = (
    "① 本案例是**设计期验证**（晶体管级模型 + 电路仿真 + 阵列 + 数据通路 + 版图签核 + 寄生后仿 + "
    "失配/噪声 + 规模压力），**非流片后实测**——无硅、无实测精度/良率/工艺、无 foundry 回片；"
    "② 晶体管模型为**公开典型量级占位参数**（非 PDK 标定、无实测锚）⇒ 不宣称器件性能；"
    "版图层号/设计规则亦为**公开工艺近似**（非 PDK）；"
    "③ 数据通路主路径用**理想 TIA（放大器无限增益理想化）**；transistor 路径的列增益含"
    "**电阻负载因子**（golden 已计入）——二者均为建模口径，非实测；"
    "④ **不报任何 TOPS / TOPS-W / fJ/op 等能效或吞吐指标**（LDA 是设计&验证工具链，"
    "非流片芯片）；Mythic 等公开 landmark 仅作背景坐标，**不同台比较**；"
    "⑤ 电路级验证引擎是**设计验证引擎**，非签核级 SPICE（无温度/噪声/稀疏矩阵/收敛增强）；"
    "版图几何判据为 **bbox 级**、寄生提取为一阶几何闭式（无 3D 场解）、"
    "规模模型为 **1D 行线**（忽略列线电阻这一二阶项）；"
    "⑥ **LLM 不进判决路径**：判决为死标量比对（闭式物理律 golden）；"
    "全程零外部 SPICE 引擎——C 级自主（纯 numpy/标准库）；"
    "⑦ E12 的 **2D MOS 求解器（准平衡静电）**与 E13 的 **2D 漂移扩散输运**是**两段互补能力**："
    "2D 数值解一律只是 **candidate**（golden 仍是教科书闭式 / 物理定律锚）；"
    "E13 的 SS 判据用**双锚**——`60 mV/dec` 是**物理定律硬下限（不等式）**、"
    "`60·(1+Cd/Cox)` 才是**渐近平台**（把 60 当目标是错的）；"
    "🔴 但**仍是漂移扩散（DD）框架**：不含量子修正 / 速度饱和 / 隧穿 / 弹道输运，"
    "**迁移率为常数** ⇒ `I_on` 绝对值**不可当器件性能**（深亚阈值 SS 不受影响）；"
    "结构为教科书突变结 + 2 nm 平滑，**无 LDD/halo/应力/栅重叠**。"
)

# ═══════════════════════ 九段征程（静态事实 · 可回溯门禁）═══════════════════════
# gate = 该段**常驻门禁实测判据数**（含突变探针）；seg_probes = 其中的反向突变探针数
MILESTONES = [
    {"id": "E1", "code": "D-150", "title": "基座：晶体管模型 + 电路仿真器 + 最小计算单元",
     "gate": 10, "seg_probes": 3,
     "result": "补齐平台两块短板（此前**无晶体管级模型 / 无电路仿真器**）：长沟道平方律 "
               "NMOS（三区 + gm/gds）+ MNA 仿真器（DC 牛顿/瞬态后向欧拉/AC 复数）+ 反相求和 MAC；"
               "RC 瞬态 vs 指数 <2e-4、AC vs 闭式 <1e-13"},
    {"id": "E2", "code": "D-151", "title": "参数化 N×M 模拟 MVM 交叉阵列",
     "gate": 9, "seg_probes": 3,
     "result": "参数化阵列（ideal TIA / transistor 权重 双路径）+ 晶体管级 OTA 表征；"
               "理想 8×8 <2e-4、transistor 4×4 <2.4e-4、OTA 开环增益 ∝ Rd（20k→7.5 / 30k→10.4）"},
    {"id": "E3", "code": "D-152", "title": "MVM 数据通路（计算架构 + 端到端正确性）",
     "gate": 10, "seg_probes": 3,
     "result": "数字→DAC→交叉阵列→ADC→数字；带符号权重参考列法 + 多层级联(MLP+ReLU) + 分块；"
               "单层 8bit 误差 0.012 · 2 层 MLP 0.044 · 分块=全阵（精确）"},
    {"id": "E4", "code": "D-153", "title": "规模对标（诚实边界）",
     "gate": 10, "seg_probes": 3,
     "result": "规模扫描 32→256（65536 突触）+ 公开 landmark 诚实对标；规模律："
               "**相对误差有界（0.018→0.030）· 绝对误差 ∝ N（0.08→0.54）**；不报 fabricated 能效"},
    {"id": "E5", "code": "D-154", "title": "平台能力硬化（能力清单 + 守护门禁）",
     "gate": 9, "seg_probes": 3,
     "result": "ECORE_CAPABILITY_MANIFEST（单一真源）+ 常驻守护门禁（清单↔模块/符号**双向完备** + "
               "披露一致 + 诚实边界）⇒ 能力面不再静默失守"},
    {"id": "E6", "code": "D-156", "title": "版图与几何签核（电子芯片**首次直出真 GDS**）",
     "gate": 36, "seg_probes": 4,
     "result": "新增电子版图层栈（DIFF/POLY/CONT/M1/VIA1/M2 + 层语义谓词 + 设计规则）+ "
               "1T 交叉阵列 P&R（节距闭式）+ 几何 DRC + 段感知 LVS（连通分量/短路/悬空桥/"
               "**W·L 几何回提**）+ AREF 层次化 GDS；4×4 = 120 元素 / 8.40×8.90 µm² / GDS 936 B；"
               "回提 W/L 注入 E1 模型 ⇒ Id(负载) ≡ Id(模型)"},
    {"id": "E7", "code": "D-157", "title": "寄生提取与后仿（理想互连 → 有阻互连）",
     "gate": 34, "seg_probes": 4,
     "result": "导线 RC 教科书闭式（R=ρL/(Wt) ≡ R□·L/W · C=ε₀ε_r·W/d）由 E6 几何提每段 R/C + "
               "Elmore 延迟；阵列 **R 梯网络**注入 MNA 后仿；**IR drop 相对误差 N=4 0.42% → "
               "N=32 27.0%**（超线性）· **sneak 比例 N=4 1.29× → N=16 7.26×**；"
               "R=0 网络 ≡ 解析 golden（max|Δ| = 1.08e-19）"},
    {"id": "E8", "code": "D-158", "title": "非理想 / 失配 / 噪声 + 校准层级",
     "gate": 36, "seg_probes": 4,
     "result": "Pelgrom 失配（σ_ΔVth = A_VT/√(W·L)）+ 温度（Vth 线性 + 迁移率 (T/T0)^m）+ "
               "热/闪烁噪声 + **失配 Monte Carlo** + **校准层级 L0/L1/L2**；"
               "σ_ΔVth = 5.00 mV · MC 8×8 σ_rel = 0.654% · **σ_rel·√N ≈ 0.0186 恒定（1/√N 律）** · "
               "校准 L0 1.696% → L1 0.212% → L2 0.0743%"},
    {"id": "E9", "code": "D-159", "title": "千级阵列规模压力 + 同族维度诚实对标",
     "gate": 34, "seg_probes": 4,
     "result": "换 O(N) 算法把规模推到千级：层次化 AREF 版图（1024×1024 → GDS 86.6 KB / "
               "top 2049 条 / 压缩比 **3571×**）+ 一维三对角 IR-drop（**1D ≡ 2D 的 2D 稠密 MNA，"
               "相对差 ≤1.7e-13**）；**三重规模律**（IR drop ∝N² · 面积 ∝N² · 失配 ∝1/√N）；"
               "**可及规模上界**：10% 预算 → N≤26 · 5% → N≤18 · 2% → N≤11 · 1% → N≤8"},
    {"id": "E11", "code": "D-161…D-164",
     "title": "器件级内核接线（口径同步 · 接缝勘查 · MOSCAP 内核桥 · 失效边界）",
     "gate": 47, "seg_probes": 15,
     "result": "E11-a 口径同步（把「本包的设计取舍」与「平台红线」两件事分离 + 防漂移门禁）→ "
               "E11-b 接缝勘查（查明与器件级内核零复用的根因 = **两侧非同一器件**："
               "`drift_diffusion_1d/2d` 是**两端 p-n 结**，本包要的是**三端 MOSFET**）→ "
               "E11-c **器件级内核桥**：新增 MOSCAP 1D 自洽泊松（`lda_solver/mos_1d.py`）"
               "⟷ 教科书闭式交叉验证（**V_th 一致到 2e-4%** · Q_s 跨点 ≤0.011% · 量纲桥 · "
               "G-3 参数自洽性显式报告）→ E11-d **失效边界**：数值窗口 vs 物理窗口严格分离 ⇒ "
               "**物理先失效、数值后崩**（半宽比 0.835）· 文献缺口量化（L=65 nm roll-off 占 V_th **37.9%**）"},
    {"id": "E12", "code": "D-166…D-168",
     "title": "2D MOS 求解器（短沟道效应：从「算不了」到「算得了」）",
     "gate": 24, "seg_probes": 7,
     "result": "把 E11-d 诚实登记为「平台算不了」的那一格**补上**：新增**四端 2D MOSFET 自洽泊松**"
               "（变系数有限体积 **按面中点判介质** ⇒ 界面离散精确 + **分段四端 BC** + "
               "**电子准费米势分裂** + 阻尼牛顿/continuation）⇒ roll-off 与 DIBL "
               "**由 2D 数值解自然涌现**（不再靠文献式代入）：长沟道极限收敛教科书 1D 闭式 "
               "**rel 0.496%** · roll-off L=65 nm **−176 mV**（Yau 文献式 −161 mV · **同量级对照**）· "
               "**DIBL 153.6 mV/V 且 ln(DIBL)–L 线性 R² 0.9986**（**指数衰减律** · ℓ_eff 68.9 nm）· "
               "网格收敛 <0.6 mV"},
    {"id": "E13", "code": "D-170…D-172",
     "title": "2D MOS 漂移扩散输运（I–V / 亚阈值摆幅：把 G-K 的「不产 I-V」关掉）",
     "gate": 18, "seg_probes": 5,
     "result": "把 E12 的诚实边界 **G-K**（「2D MOS 为准平衡静电求解 ⇒ 不产 I-V」，"
               "`short_channel_capability_report` 的 `still_not_available` 首条）**真正关掉**："
               "新增 **Si-only 掩码稳态漂移扩散输运**（Scharfetter–Gummel 离散 + **接触准费米势 BC** + "
               "Gummel 交替 + 终端电流）⇒ **I–V / 亚阈值摆幅由数值解提取**。🔴 **SS 双锚**："
               "**热极限 59.53 mV/dec 是硬下限（不等式）**、**教科书闭式 66.41 mV/dec 才是渐近平台** "
               "⇒ 长沟道 2D **68.08 ⟷ 闭式 66.41（rel 2.52%）**；栅长趋势 L↓⇒SS↑ "
               "（65 nm **226.9** → 100 nm 88.0 → 250 nm 69.5 → 1 µm 68.1，与 E12 roll-off **同向**）；"
               "电流守恒 **5.4e-5**（带绝对下限）· 输出特性单调趋饱和（1.0 V 时 **1605 A/m**）· "
               "**V_th 双法交叉**（恒流法 0.2475 ⟷ E12 表面势法 0.3241 V，差 76.6 mV；两法均非 ORACLE）"},
    {"id": "E14", "code": "D-174…D-176",
     "title": "真 DAC / ADC / 行驱动外设（把「设计链」补成「系统链」）",
     "gate": 26, "seg_probes": 6,
     "result": "把数据通路**两端的转换器**与**行驱动**从行为级换成**真电路**："
               "**R-2R 梯形 DAC**（无源网络 + **NMOS 模拟开关** ⇒ 8 bit **全码 256 点** max|Δ| "
               "**0.0265 LSB** · `R_on` **6.4 Ω** · **W/L ↑ ⇒ 误差 ↓**：0.0017 ⟷ 0.0660 LSB）+ "
               "**SAR + CDAC 电荷重分配 ADC**（🔴 **电容 DC 开路 ⇒ 必须走瞬态**：后向欧拉伴随模型给出 "
               "`Σ C_k(V_top−V_bk) = const` 即**电荷严格守恒**（rel 3.9e-12）；16 取样点 max ≤ **1 LSB**）+ "
               "**采样保持**（瞬态 ⟷ **后向欧拉离散闭式** rel **5.6e-16**；与**连续**闭式偏差 **O(dt) 一阶**）+ "
               "🔴 **行驱动 `R_oc` 串进 E9 三对角 IR-drop** ⇒ **可及规模上界重算**（5% 预算：理想源 "
               "**N≤20** → 1 Ω **N≤17** → 5 Ω **N≤10** → 20 Ω **N≤3**，`R_oc=0` 时与 E9 **逐位一致** "
               "max|Δ| = 0）—— **器件级参数第一次反馈到规模律** + **行系统项**（驱动负载调整 ⇒ "
               "行增益离散 **8.889e-4**，与 E8 列系统项同型、MC 平均不掉）。"
               "🔴 并**登记一个平台缺陷**：`mna.Circuit.vcvs` 实际极性与 docstring 相反"
               "（适配 + 判据锁死，**不改 mna** ⇒ 保护 E1–E13 已上线数字）"},
]

#: 门禁判据合计（= Σ MILESTONES.gate）与突变探针合计（= Σ seg_probes）
GATE_CHECKS_TOTAL = sum(m["gate"] for m in MILESTONES)
PROBE_CHECKS_TOTAL = sum(m["seg_probes"] for m in MILESTONES)

# ═══════════════════════ 关键结论（物理 + 方法学）═══════════════════════
FINDINGS = [
    {"title": "吃狗粮逼出并补齐平台四块真短板（E1–E5）",
     "detail": "此前 LDA 电子域只到行为级——**无晶体管级模型 / 无电路仿真器 / 无模拟计算原语 / "
               "无规模定标与诚实护栏**。本征程新增 `lda_l2/ecore/` 包逐一补齐。"},
    {"title": "补上最大平台缺口：电子芯片**首次直出真 GDS**（E6）",
     "detail": "此前 ecore **一条版图链都没有**——严格讲「设计出了电路，但签不出芯片」。E6 补齐"
               "电子版图层栈 + 1T 交叉阵列 P&R + 几何 DRC + 段感知 LVS + AREF 层次化，与光子/量子"
               "征程收尾同构：**电路模型 → 可签核版图 → GDS**。"},
    {"title": "架构族同构：电子版「光子 MZI 网格」",
     "detail": "模拟 MVM 交叉阵列 = 行电压 × 交叉点电导 → 列电流求和 → TIA，正是电子域的"
               "矩阵-向量乘；与光子 MZI mesh、与商业模拟 AI 加速器（Mythic 类）**同族**。"},
    {"title": "方法学独立：闭式物理律 golden",
     "detail": "MOSFET 三区解析 ↔ 平方律闭式、RC 瞬态 ↔ 指数、AC ↔ 复导纳转移函数、"
               "导线 RC ↔ 方块电阻闭式、AREF 展开 ↔ flat、R=0 网络 ↔ 解析求和 —— "
               "判决全为**死标量比对**，LLM 不进判决路径，零外部 SPICE。"},
    {"title": "IR drop 是模拟 MVM 的**第一号规模墙**；sneak 是**拓扑效应**（E7）",
     "detail": "N=32 时 IR drop 相对误差已达 **27%**，且按 **∝N²** 超线性增长 ⇒ 被动式单端驱动的"
               "模拟交叉阵列**不能只靠加行/列数扩规模**（须分段/双侧驱动、加宽加厚金属、降单元电导、"
               "分块 tiling）。sneak 在 R=0 时仍存在 ⇒ 属**拓扑效应**，与 IR drop 解耦，"
               "需正规选通方案（1T「栅压即权重」在未选通浮空时无选择器隔离）。"},
    {"title": "失配：随机项被 1/√N 平均掉，系统项不会 ⇒ 分层校准（E8）",
     "detail": "σ_rel ∝ **1/√N**（小阵列更脆弱，但绝对值 ∝√N 上升，动态范围仍被失配底噪占据）；"
               "**列系统项（热梯度/共模）不会被平均掉** ⇒ 必须**列级校准**（L1）；只有**逐单元"
               "校准**（L2）才压随机项，而 L2 残差由**测量噪声**决定 ⇒ **校准精度决定模拟 CIM "
               "的有效位数上限**。实测：L0 1.696% → L1 0.212% → L2 0.0743%。"},
    {"title": "规模压力：千级阵列在被动驱动下**不可达**（E9）",
     "detail": "换 O(N) 算法后可建模到 1024×1024（层次化 GDS 86.6 KB · 压缩比 3571×），"
               "但三重规模律显示 IR drop **3.75% → 95.6%**（超线性）、失配 σ **0.4209% → 0.0526%**"
               "（反降）——**两约束方向相反，规模由 IR drop 主导**：5% 输出误差预算只支持 **~18 行**。"},
    {"title": "规模律（诚实报告）：相对误差有界、绝对误差 ∝ N",
     "detail": "MVM 输出幅度随 N 增长；固定位数 ADC 下绝对 LSB 随之增大 ⇒ **须按层输出定标**"
               "（`out_norm`）；相对误差 ≈ 1/2^bits 与 N 无关。这是「规模墙」暴露的真实架构约束。"},
    {"title": "诚实对标：不报 fabricated 能效",
     "detail": "LDA 是设计&验证工具链（非流片芯片）⇒ **不报任何 TOPS/TOPS-W**；公开 landmark "
               "照录来源、仅作背景坐标、不作 LDA 成就值；护栏机器化（注入造假指标必红）。"},
    {"title": "器件级内核接线：ecore 首次被**器件级 PDE** 校验（E11-c）",
     "detail": "此前 ecore 的器件模型只与**自身闭式**自洽（自证桩）。E11-b 查明根因——**平台器件级内核"
               "是两端 p-n 结，本包要的是三端 MOSFET**，故不是「接线」问题而是**缺器件内核**。"
               "E11-c 补上 MOSCAP 1D 自洽泊松，使本包首次拥有「**教科书闭式 ⟷ 器件级 PDE**」独立交叉"
               "验证：V_th 一致到 **2e-4%**、Q_s 跨点 ≤**0.011%**。🔴 golden 仍是教科书闭式，"
               "PDE 只是 candidate（`is_oracle=False`）。"},
    {"title": "失效边界：**物理模型先失效、数值后崩**（E11-d）",
     "detail": "把两类边界严格分开：**数值窗口**（LDA 实测，随网格变宽）与**物理窗口**（文献判据，"
               "与网格无关）⇒ 半宽比 **0.835 < 1** ⇒ **瓶颈是物理模型（1D 无源漏 + 玻尔兹曼），"
               "不是数值精度**。文献缺口量化：L=65 nm 时短沟道 roll-off 让 V_th 偏 **37.9%**、"
               "DIBL 3.1%（L↑ 单调收敛）。⇒「达到国际水平」的真实瓶颈在 **T2（工艺/PDK/流片）**，"
               "不在求解器精度——加求解器补不上这一格。"},
    {"title": "短沟道效应：从「文献代入」到「2D 解自然涌现」（E12）",
     "detail": "E11-d 曾把 roll-off / DIBL 登记为**平台算不了**（只引文献经验式）。E12 新增四端 "
               "2D MOSFET 自洽泊松求解器后，两者均由**二维场解自然涌现**：长沟道极限收敛到教科书 "
               "1D 闭式（**rel 0.496%**）· roll-off L=65 nm **−176 mV**（与 Yau 文献式 −161 mV "
               "**同量级对照**）· **DIBL 153.6 mV/V 且满足 ln(DIBL)–L 指数衰减律"
               "（R² 0.9986 · ℓ_eff 68.9 nm）**——数值假象不会给出干净的指数律，"
               "**这是该能力「真做出来了」的决定性证据**。🔴 但本段为**准平衡静电求解、"
               "不含输运 ⇒ 不产 I-V**；golden 仍是教科书 1D 闭式，2D 解只是 candidate。"},
    {"title": "亚阈值摆幅：**60 mV/dec 是硬下限，不是目标**（E13）",
     "detail": "E12 登记的「不产 I-V」缺口由 E13 的**稳态漂移扩散输运**（SG 离散 + 接触准费米势 BC + "
               "Gummel）关掉 ⇒ I–V / SS 可从数值解提取。🔴 本段最重要的物理澄清："
               "**「SS → 60」是错的目标** —— `60 mV/dec` 只在 `Cd → 0`（FD-SOI / 双栅）时达到，"
               "**体硅器件因体效应收敛到 `60·(1+Cd/Cox)` 的平台**（本例 ≈ **66.4**）⇒ 60 的正确角色是"
               "**物理定律硬下限（不等式 G1）**，**不是渐近目标**。实测长沟道 2D **68.08** ⟷ 闭式 "
               "**66.41**（rel 2.52%）；短沟道退化 **65 nm → 226.9 mV/dec**（与 E12 的 roll-off/DIBL "
               "**同向**，两条独立路径互证）。🔴 **仍是 DD 框架**：不含量子修正 / 速度饱和 / 隧穿 / "
               "弹道；**迁移率为常数** ⇒ `I_on` 绝对值**不可当器件性能**。"},
    {"title": "外围电路：从「行为级量化」到「真电路」——**驱动阻抗反向决定规模上界**（E14）",
     "detail": "E1–E13 的 DAC/ADC 一直只是 `quantize_uniform`（行为级）**、行线由理想电压源钉住** ⇒ "
               "**外围电路的代价从未进入任何规模结论**。E14 补上真电路后发现两件事："
               "① **真器件参数会反过来限制系统规模** —— 把行驱动的**闭环输出电阻 `R_oc`** 串进 E9 的三对角 "
               "IR-drop 模型后，5% 误差预算下的可及行数从 **N≤20（理想源）掉到 N≤17（1 Ω）/ N≤10（5 Ω）/ "
               "N≤3（20 Ω）** ⇒ **行驱动输出阻抗必须远小于行线总电阻**；而一个再普通不过的缓冲"
               "（开环输出 1 kΩ · A=1e3）就已经是 1 Ω 量级。"
               "② **行系统项** —— 行负载 `Σ_j g_ij` 随行变化 ⇒ 驱动负载调整引入**按行增益误差**"
               "（实测行增益离散 **8.889e-4**，理想驱动下为 0）—— 与 E8 的**列系统项**同型，"
               "**不会被 Monte Carlo 平均掉** ⇒ 要么 `R_oc` 足够低，要么**行级校准**。"
               "🔴 转换器侧的两个数值纪律同样重要：**电容在 DC 下开路** ⇒ CDAC 必须走瞬态"
               "（后向欧拉的电荷守恒是**精确**的，不是近似）；**离散闭式 ≠ 连续闭式** ⇒ 对拍要先问"
               "「求解器实际在解哪个方程」。"},
]

# ═══════════════════════ 诚实边界（未闭合项 · 逐条登记）═══════════════════════
GAPS = [
    {"id": "G-A", "title": "无流片 / 无实测",
     "detail": "全部为设计期验证；无硅、无实测精度/良率、无 foundry 回片。"},
    {"id": "G-B", "title": "无 foundry PDK（器件）",
     "detail": "晶体管参数为公开典型量级占位（非 PDK 标定、无实测锚）。"},
    {"id": "G-C", "title": "理想 TIA 路径 / 非签核级 SPICE",
     "detail": "数据通路主路径用理想运放（无限增益）；电路引擎无温度/噪声/稀疏矩阵/收敛增强。"},
    {"id": "G-D", "title": "无实测能效 / 吞吐",
     "detail": "不报任何 TOPS / TOPS-W / fJ/op（无流片、无硅实测）。"},
    {"id": "G-E", "title": "transistor 路径列增益含电阻负载因子",
     "detail": "晶体管权重路径的列增益随该列总电导变化（电阻负载固有特性，golden 已计入）。"},
    {"id": "G-F", "title": "版图层 / 规则为公开近似（非 PDK）",
     "detail": "层号与设计规则取公开工艺近似（可覆盖）；几何判据为 **bbox 级**；"
               "沟道区被 POLY 断开为 DIFF_D/DIFF_S 属**教学级简化**。"},
    {"id": "G-G", "title": "寄生提取为一阶几何闭式 · 后仿为 DC",
     "detail": "无 3D 场解、无频变 R/L、无衬底耦合；sneak 分析中的 `r_leak` 为**数值钉扎**"
               "（防浮空节点奇异），**非物理漏电**。"},
    {"id": "G-H", "title": "失配/噪声/温度参数为公开量级 · 校准为理想化",
     "detail": "A_VT / A_β / k_T / K_f 为公开典型量级；L2 逐单元校准为理想化模型；"
               "噪声仅给谱密度量级；假定**独立同分布**（不建模空间相关）。"},
    {"id": "G-I", "title": "规模模型为 1D 行线（忽略列线电阻）",
     "detail": "千级阵列的 IR-drop 用一维三对角线模型，**忽略列线电阻**（二阶项）；"
               "在校核规模内与 E7 的 2D 稠密 MNA 对拍一致；千级是**设计期版图与规模律**，非流片。"},
    {"id": "G-J", "title": "短沟道效应原不在模型内（E11-d 测绘）→ **已由 E12 闭合**（历史项 · 保留可追溯）",
     "detail": "E11-d 曾登记「平台无 2D MOS 能力」并用**文献经验式**量化缺口（L=65 nm roll-off "
               "占 V_th **37.9%**，每项 `computed_by_lda=False`）。**E12 已补上该能力**："
               "roll-off / DIBL 现由 **2D 数值泊松解**给出。本项保留作**可追溯**记录，"
               "**不代表当前能力状态**；闭合之后**新的**内在边界见 **G-K**。"},
    {"id": "G-K", "title": "2D MOS 原不产 I-V（E12 测绘）→ **已由 E13 闭合**（历史项 · 保留可追溯）",
     "detail": "E12 的 2D 求解器**不含漂移扩散输运** ⇒ 当时**无 I–V、无亚阈值摆幅（从电流）**"
               "（V_th 用「界面最低表面势达 +φ_F」判据，**非恒定电流法**）。**E13 已补上该能力**："
               "稳态漂移扩散（SG 离散 + 接触准费米势 BC + Gummel）⇒ I–V / SS **可从数值解提取**。"
               "本项保留作**可追溯**记录，**不代表当前能力状态**；闭合之后**新的**内在边界见 **G-L**。"},
    {"id": "G-L", "title": "漂移扩散（DD）框架的内在边界（E13 新增能力的内在边界）",
     "detail": "E13 的输运内核**仍是漂移扩散框架** ⇒ 不含量子修正 / 速度饱和 / 带间与栅隧穿 / "
               "弹道输运；**迁移率为常数**（无场依赖退化 / 无表面散射）⇒ `I_on` 绝对值**不可当器件性能**"
               "（但**深亚阈值 SS 不受影响** —— 由玻尔兹曼尾决定，这正是 SS 热极限与教科书闭式两条判据"
               "仍严格成立的原因；代价是 **I_on 偏高、I_off 偏低**）。结构为教科书突变结 + 2 nm 平滑，"
               "**无 LDD / halo / 应变 / 栅重叠**；固定 300 K、只做 DC（无温度扫描 / 无 AC·瞬态）。"
               "参数（N_A / N_SD / t_ox / x_j / V_FB）为公开典型量级占位（**非 PDK**、无实测锚）；"
               "2D 仿真 = **每单位宽度电流（A/m）**；**EAR 744.23**（成熟节点 / 非先进用途）。"
               "补量子修正 / 弹道需 NEGF 或量子修正 DD；工艺角 / PDK / 硅验证 ⇒ **T2 永久锁**"
               "（商业路径，非求解器精度问题）。"},
    {"id": "G-M", "title": "外围电路为宏模型 / 抽象（E14 新增能力的内在边界）",
     "detail": "**比较器是「有限增益 + 输入失调 + 噪声」的判决器抽象，非晶体管级比较器**"
               "（MNA 无非线性饱和器件，且 E2 已证朴素 NMOS 差分对无法闭合高增益环路）；"
               "**CDAC 的底板开关用理想电压源抽象**（DAC 侧则用真 NMOS 开关以暴露 `R_on` —— 这是"
               "**有意的工程取舍**）；**行驱动器是 VCVS + 开环输出电阻的宏模型，非晶体管级运放**；"
               "电阻 / 电容为**理想值**（**不建匹配网络**，失配沿用 E8 的 Pelgrom/MC 口径）；"
               "`R_on` 取平方律**三极管区闭式**；**电荷注入 / 时钟馈通只给量级估算**；"
               "阵列用 E2 已验证的解析列电流模型；**无建立时间 / 摆率 / 输出级非线性建模**；"
               "位数 ≤ 8 bit（更高位带来规模与收敛成本）。参数为公开典型量级占位（**非 PDK**）。"},
    {"id": "G-N", "title": "🔴 平台缺陷登记：`mna.vcvs` 实际极性与 docstring 相反（E14 发现 · 未修）",
     "detail": "`mna.Circuit.vcvs` 的 **docstring 声明** `V(out_p)−V(out_n) = gain·(V(ctl_p)−V(ctl_n))`，"
               "但 `_stamp_dc` 的 E 分支实际给出 **`gain·(V(ctl_n) − V(ctl_p))`（极性相反）**"
               "（实测 `ctl_p = +1 V` ⇒ `V_out = −1000 V`）。**E1–E13 全程带着它上线**。"
               "**为什么不就地修**：E1–E13 全部已上线数字（含 E2 的 ideal-TIA 虚地电路）建立其上 ⇒ "
               "按保护性约束（同 `NmosParams` 默认值）**不改 mna**，改为**适配 + 显式登记 + 判据锁死**"
               "（本包 `periphery.row_driver_mna_check` 把 `ctl_p`/`ctl_n` 对调；门禁 B14 用 "
               "`vcvs_polarity_fact()` 把事实锁死 ⇒ 若未来有人「顺手改正」 mna.py，B14 会红并提示适配过期）。"
               "**既有结论是否失效**：不失效 —— TIA 虚地是 `|A|→∞` 的**极限**，符号只改变放大器输出的"
               "**定向**，不改变虚地机制 ⇒ **E2/E3 结论仍成立**。"},
]

_ARTIFACT_DIRS = ("examples", "lda/examples")


# ═══════════════════════════ 闭式（可反向测试 · 纯 math）═══════════════════════════
def crossbar_capacity(n_rows: int, n_cols: int) -> Dict[str, Any]:
    """模拟 MVM 交叉阵列容量闭式（纯计数）：突触数 = rows×cols。

    - 突触数（交叉点）= rows · cols
    - 数据列 = cols；参考列（承载带符号权重）= 1 ⇒ 物理列 = cols + 1
    - 每列输出 = −Rf · Σ_i g_ij·Vin_i（TIA 虚地电流求和）
    """
    r, c = int(n_rows), int(n_cols)
    if r < 1 or c < 1:
        raise ValueError("n_rows / n_cols 须 ≥ 1")
    return {
        "n_rows": r, "n_cols": c,
        "n_synapses": r * c,
        "n_data_cols": c,
        "n_phys_cols_incl_ref": c + 1,
        "fan_in_per_col": r,
    }


def quant_error_rel_bound(bits: int) -> float:
    """均匀量化（mid-tread）相对误差上界 ≈ 1/(2^bits − 1)（LSB/2 归一）。

    bits ≤ 0 视为理想（不量化）⇒ 返回 0.0。
    """
    b = int(bits)
    if b <= 0:
        return 0.0
    if b > 60:
        raise ValueError("bits 过大（>60）无意义")
    return 1.0 / (2 ** b - 1)


def layout_elements_flat(n: int, m: int) -> int:
    """**物化**整阵列版图元素数（E6 `layout.crossbar_array` 的规模）= n·m·7 + n + m（纯计数）。

    7 = 1T 单元元素数（DIFF_D/DIFF_S/POLY/CONT×2/M1 焊垫/VIA1）；+n 行线；+m 列线。
    """
    r, c = int(n), int(m)
    if r < 1 or c < 1:
        raise ValueError("n / m 须 ≥ 1")
    return r * c * 7 + r + c


def layout_elements_hier(n: int, m: int) -> int:
    """**层次化** GDS 的元素记录数（E9 `array_scale`）= cell(7) + 1 条 AREF + n 行 + m 列 = **O(N)**。"""
    r, c = int(n), int(m)
    if r < 1 or c < 1:
        raise ValueError("n / m 须 ≥ 1")
    return 8 + r + c


def hier_compression_ratio(n: int, m: int) -> float:
    """层次化压缩比 = 物化 / 层次化（🔴 **∝N**，非 ∝N²：flat = 7N²+2N、hier = 8+N+M）。"""
    return layout_elements_flat(n, m) / float(layout_elements_hier(n, m))


def sheet_resistance_ohm_per_sq(rho_ohm_um: float, t_um: float) -> float:
    """金属方块电阻 R□ = ρ / t（Ω/□）。"""
    if float(t_um) <= 0:
        raise ValueError("厚度须 > 0")
    return float(rho_ohm_um) / float(t_um)


def wire_resistance_ohm(rho_ohm_um: float, length_um: float, width_um: float,
                        t_um: float) -> float:
    """导线电阻 R = ρL/(W·t) ≡ R□·L/W（Ω）。"""
    if float(width_um) <= 0 or float(t_um) <= 0:
        raise ValueError("W / t 须 > 0")
    return float(rho_ohm_um) * float(length_um) / (float(width_um) * float(t_um))


def pelgrom_sigma_vth_mv(a_vt_mv_um: float, w_um: float, l_um: float) -> float:
    """Pelgrom 阈值失配标准差 σ_ΔVth = A_VT / √(W·L)（mV，W·L 单位 µm²）。"""
    wl = float(w_um) * float(l_um)
    if wl <= 0:
        raise ValueError("W·L 须 > 0")
    return float(a_vt_mv_um) / math.sqrt(wl)


def pelgrom_sigma_beta_pct(a_beta_pct_um: float, w_um: float, l_um: float) -> float:
    """Pelgrom 电流因子失配 σ_Δβ/β = A_β / √(W·L)（%）。"""
    wl = float(w_um) * float(l_um)
    if wl <= 0:
        raise ValueError("W·L 须 > 0")
    return float(a_beta_pct_um) / math.sqrt(wl)


def elmore_tau_rc(r_total_ohm: float, c_total_f: float) -> float:
    """分布 RC 线的 Elmore 延迟极限 τ = R·C/2（s）。"""
    if float(r_total_ohm) < 0 or float(c_total_f) < 0:
        raise ValueError("R / C 须 ≥ 0")
    return 0.5 * float(r_total_ohm) * float(c_total_f)


def sigma_rel_vs_n(sigma_cell_rel: float, n: int) -> float:
    """输出相对误差的 **1/√N 律**：σ_out = σ_cell / √N（独立同分布求和平均）。"""
    if int(n) < 1:
        raise ValueError("n 须 ≥ 1")
    return float(sigma_cell_rel) / math.sqrt(int(n))


# ═══════════════════════════════ 产出物探测（只读元信息）═══════════════════════
def _artifact_manifest(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """探测 `examples/` 下 E 征程产出物**元信息**（文件名 + 字节数 · 只 stat）。

    🔴 **聚合扫描**：逐个候选目录扫描后**按文件名去重合并**（防「假空」）；
    目录都不存在则优雅降级 `available=False`。
    """
    root = repo_root
    if root is None:
        root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
    items: Dict[str, int] = {}
    hits: List[str] = []
    for d in _ARTIFACT_DIRS:
        p = os.path.join(root, d)
        if not os.path.isdir(p):
            continue
        hits.append(d)
        try:
            names = sorted(os.listdir(p))
        except OSError:
            continue
        for nm in names:
            if not nm.startswith("lda_ecore") or nm.endswith(".py"):
                continue
            fp = os.path.join(p, nm)
            try:
                if os.path.isfile(fp):
                    items[nm] = int(os.path.getsize(fp))
            except OSError:
                continue
    if not hits:
        return {"available": False, "root_hint": _ARTIFACT_DIRS[0], "count": 0,
                "items": [], "note": "产出物目录不在本部署内（源码仓才含 examples/）"}
    lst = [{"name": k, "bytes": v} for k, v in sorted(items.items())]
    return {"available": True, "dirs_scanned": hits, "root_hint": hits[0],
            "count": len(lst), "items": lst,
            "note": "只读元信息（文件名 + 字节数，已跨目录去重）"}


# ═══════════════════════════════ 案例卡 ═══════════════════════════════
def case_card(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """组装电子计算芯片案例卡（只读 · 零重计算 · 免登录）。

    `verdict` 恒为 `DESIGN_VERIFIED` —— **明标「设计期验证」而非实测**。
    """
    flag = crossbar_capacity(256, 256)
    return {
        "endpoint": "/api/ecore_demo",
        "case_id": CASE_ID,
        "claim": "用 LDA 从零设计一颗电子计算芯片（模拟计算核 / MVM 交叉阵列）："
                 "晶体管级模型 + 电路仿真 + 参数化阵列 + 数据通路 + 规模对标 + 版图签核 + "
                 "寄生后仿 + 失配/噪声 + 千级规模压力 + **器件级 PDE 交叉验证 + 失效边界测绘 + "
                 "2D 短沟道效应（roll-off/DIBL） + 2D 漂移扩散输运（I–V / 亚阈值摆幅） + "
                 "真 DAC / ADC / 行驱动外设（系统链）**全链路验证",
        "verdict": "DESIGN_VERIFIED",
        "verdict_label": "设计期验证（非流片实测）",
        "identity": {
            "physics": "模拟 compute-in-memory（MVM 交叉阵列）· 电子/CMOS 电路级 + 版图级",
            "device": "NMOS 差分对 OTA / 交叉点电导 / TIA（大增益运放）",
            "unit": "模拟 MVM 砖 = 行电压 × 交叉点电导 → 列电流求和 → TIA 转电压",
            "route_note": "吃狗粮第四条路线（光子计算 / 光量子 LOQC / 超导 transmon 之后）；"
                          "与光子 MZI mesh 同构（电子版）；**版本征程中唯一出真 GDS 的电子路线**",
            "zero_quantum_sdk": True,
            "zero_spice_engine": True,
            "zero_commercial_eda": True,
        },
        "span": {
            "milestones": len(MILESTONES),
            "gate_checks": GATE_CHECKS_TOTAL,
            "probe_checks": PROBE_CHECKS_TOTAL,
            "modules": 18,               # ecore 包内模块数（含能力清单自身 · 不含 __init__.py）
            "capability_modules": 17,    # 登记进 ECORE_CAPABILITY_MANIFEST 的能力模块数
            "entrypoints": 16,           # 常驻门禁数（E1–E9 八道 + 能力守护 + 案例卡 + 红线 +
                                         #   E11 两道 + E12 + E13 + E14）
            "modules_dir": "lda/lda_l2/ecore/",
        },
        "milestones": MILESTONES,
        "findings": FINDINGS,
        "gaps": GAPS,
        "gaps_total": len(GAPS),
        "flagship": {
            "kind": "N×M 模拟 MVM 交叉阵列",
            "n_rows": flag["n_rows"], "n_cols": flag["n_cols"],
            "n_synapses": flag["n_synapses"],
            "n_phys_cols_incl_ref": flag["n_phys_cols_incl_ref"],
            "fan_in_per_col": flag["fan_in_per_col"],
        },
        "scale_tiers": {
            "tiers": SCALE_TIERS,
            "max_synapses_tested": KEY_METRICS["max_synapses_tested"],
            "note": "规模 = **可建模并可验证的交叉点容量**，非已流片器件数；"
                    "相对误差有界、绝对误差 ∝ N（固定位数 ADC 固有律）",
        },
        "layout": LAYOUT_FACTS,
        "parasitic": PARASITIC_FACTS,
        "mismatch": MISMATCH_FACTS,
        "device_pde": DEVICE_PDE_FACTS,
        "device_limits": DEVICE_LIMITS_FACTS,
        "device_2d": DEVICE_2D_FACTS,
        "device_transport": DEVICE_TRANSPORT_FACTS,
        "device_periphery": DEVICE_PERIPHERY_FACTS,
        "scale_pressure": {
            "facts": SCALE_FACTS,
            "tiers": SCALE_PRESSURE_TIERS,
            "ceiling": SCALE_CEILING,
            "note": "**三重规模律**：IR drop ∝N²（超线性）· 面积 ∝N² · 失配 σ ∝1/√N（方向相反）；"
                    "**规模上界由 IR drop 主导**：5% 输出误差预算 ⇒ 被动单端驱动 ~18 行",
        },
        "physics": {
            "mosfet": MOSFET_FACTS,
            "metrics": KEY_METRICS,
            "scale_law": {
                "rel_err_bound_formula": "≈ 1/(2^bits − 1)",
                "rel_err_bound_8bit": quant_error_rel_bound(8),
                "abs_err_grows_with_N": True,
            },
        },
        "artifacts": _artifact_manifest(repo_root),
        "ui": {
            "found_in_ui": True,
            "entry": "验证实力（accept）→「电子计算芯片案例」卡",
            "scope_note": "UI 电子/CMOS 面板覆盖**电路级仿真**；本卡覆盖**芯片级模拟计算架构与验证**"
                          "（含版图签核 / 寄生后仿 / 失配校准 / 规模压力 / 器件级 PDE 交叉验证 / "
                          "2D 短沟道效应 / 2D 漂移扩散输运 I–V 与亚阈值摆幅）。",
        },
        "positioning": _positioning(),
        "honest_note": ECORE_HONEST_NOTE,
    }


def _positioning() -> Dict[str, Any]:
    """先进性定位（公开来源 · 只作背景，不与本案例同台比较）。"""
    return {
        "disclaimer": "下列为公开报道的**产业界/学术界模拟计算（compute-in-memory）**数字，"
                      "仅作背景坐标；本案例为**设计期验证**（无流片），两者**不同台比较**；"
                      "LDA **不报任何 TOPS / TOPS-W**。",
        "public_landscape": LANDMARKS_BRIEF + [
            {"who": "学术界", "item": "RRAM/ReRAM MVM 交叉阵列加速器提案"
                                     "（ISAAC / PUMA 系列，架构族参照）"},
        ],
        "what_is_different": [
            {"axis": "交付物", "industry": "流片硅产品 + 云访问（或有硅实测）",
             "lda": "**设计期验证**：可复现、可审计的工具链输出（无硅）"},
            {"axis": "工具链来源", "industry": "各自闭源 CAD/PDK + 商业 SPICE",
             "lda": "**开源（MIT）· Agent-native · 零外部 SPICE/EDA 引擎**：晶体管模型 + MNA "
                    "求解器 + 版图/GDS/DRC/LVS 全自研（纯 numpy/标准库）"},
            {"axis": "判决路径", "industry": "通常为实测 + 数值仿真混合",
             "lda": "**LLM 不进判决路径**：判决为死标量比对；红线为物理定律锚"},
            {"axis": "架构族", "industry": "analog CIM MVM 交叉阵列",
             "lda": "**同族**：MVM 交叉阵列（电子版「光子 MZI 网格」）——同族维度可比"},
            {"axis": "能效口径", "industry": "有实测/宣称 TOPS 与 W",
             "lda": "**不报能效/吞吐**（无流片）——口径不同，不可比数"},
        ],
        "honest_limits": [
            "无数值/能效同台比较：LDA 不宣称在 TOPS/W 或吞吐上优于任何厂商。",
            "晶体管参数为公开典型量级占位（非 PDK、无实测锚）⇒ 不代表任何工艺实现。",
            "规模数字须按「可建模/可验证容量」解读，误读成「已流片芯片」即为失真。",
        ],
    }


# ═══════════════════════════════ 自检 ═══════════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检（门禁同源调用）。闭式断言 + 红线断言（不 import 求解器 / numpy）。"""
    res: Dict[str, bool] = {}
    msgs: List[str] = []

    def chk(name: str, cond: bool) -> None:
        res[name] = bool(cond)
        msgs.append(f"{'PASS' if cond else 'FAIL'} | {name}")

    # ① 交叉阵列容量闭式：256×256 ⇒ 65536 突触 · 257 物理列
    f = crossbar_capacity(256, 256)
    chk("① 256×256 容量闭式：65536 突触 · 257 物理列（含参考列）",
        f["n_synapses"] == 65536 and f["n_phys_cols_incl_ref"] == 257)

    # ② 容量闭式与逐点一致（N=2..10 方阵）
    ok = True
    for k in range(2, 11):
        ok = ok and crossbar_capacity(k, k)["n_synapses"] == k * k
    chk("② 方阵突触数 ≡ k²（k=2..10 逐点）", ok)

    # ③ 量化相对误差上界 = 1/(2^bits−1)
    chk("③ 量化相对误差上界：8bit ⇒ 1/255 ≈ 0.00392",
        abs(quant_error_rel_bound(8) - 1.0 / 255.0) < 1e-15)

    # ④ 版图元素闭式（E6/E9）：4×4 ⇒ flat 120 · hier 16
    chk("④ 版图元素闭式：flat(4,4)=120 · flat(8,8)=464 · hier(4,4)=16",
        layout_elements_flat(4, 4) == 120 and layout_elements_flat(8, 8) == 464
        and layout_elements_hier(4, 4) == 16)

    # ⑤ 层次化压缩比 ∝ N（N ×4 ⇒ 比值 ≈ ×4，渐近）
    r256, r1024 = hier_compression_ratio(256, 256), hier_compression_ratio(1024, 1024)
    chk("⑤ 层次化压缩比 ∝ N：ratio(1024)/ratio(256) ∈ (4.0, 4.3)（非 ∝N²）",
        4.0 < r1024 / r256 < 4.3)

    # ⑥ 导线方块电阻闭式：R□(M1) = ρ/t = 0.0168/0.20 = 0.084 Ω/□
    chk("⑥ 导线方块电阻闭式：R□(M1) = ρ_Cu/t_M1 = 0.084 Ω/□",
        abs(sheet_resistance_ohm_per_sq(1.68e-2, 0.20) - 0.084) < 1e-12)

    # ⑦ Pelgrom 失配闭式：σ_ΔVth(A_VT=3.0, W/L=1.20/0.30) = 5.00 mV
    chk("⑦ Pelgrom 失配闭式：σ_ΔVth = A_VT/√(W·L) = 5.00 mV @ 1.20/0.30 µm",
        abs(pelgrom_sigma_vth_mv(3.0, 1.20, 0.30) - 5.00) < 1e-9
        and abs(pelgrom_sigma_beta_pct(1.0, 1.20, 0.30) - 1.0 / 0.6) < 1e-9)

    # ⑧ 1/√N 律：σ_rel(4N) = σ_rel(N)/2
    s1, s4 = sigma_rel_vs_n(0.01, 1), sigma_rel_vs_n(0.01, 4)
    chk("⑧ 失配 1/√N 律：σ_rel(4) = σ_rel(1)/2（独立同分布求和平均）",
        abs(s4 - s1 / 2.0) < 1e-15)

    # ⑨ Elmore 闭式：τ = R·C/2
    chk("⑨ Elmore 延迟闭式：τ(R=1, C=1) = 0.5 s",
        abs(elmore_tau_rc(1.0, 1.0) - 0.5) < 1e-15)

    # ⑩ 案例卡组装：13 里程碑 / 14 结论 / 14 缺口 / 判据合计 303（含 64 探针）
    card = case_card(repo_root="__nonexistent_root__")
    chk("⑩ 案例卡组装：13 里程碑 / 14 结论 / 14 缺口 / 门禁判据合计 303（含 64 探针）",
        len(card["milestones"]) == 13 and len(card["findings"]) == 14
        and card["gaps_total"] == 14 and card["span"]["gate_checks"] == 303
        and card["span"]["probe_checks"] == 64)

    # ⑪ 产出物优雅降级（root 不存在 ⇒ available False，不抛错）
    chk("⑪ 产出物探测优雅降级（root 不存在 ⇒ available=False）",
        card["artifacts"]["available"] is False)

    # ⑫ 🔴 不伪装实测：verdict 恒 DESIGN_VERIFIED，且诚实边界齐全
    note = card["honest_note"]
    chk("⑫ 不伪装实测：verdict=DESIGN_VERIFIED · 诚实边界含「非流片后实测」/「非 PDK」/"
        "「不报任何 TOPS」",
        card["verdict"] == "DESIGN_VERIFIED"
        and "非流片后实测" in note and "非 PDK" in note and "不报任何 TOPS" in note)

    # ⑬ 🔴 不报 fabricated 能效：定位声明 + 3 条诚实限制
    pos = card["positioning"]
    chk("⑬ 先进性定位：含不同台比较声明 + 3 条诚实限制 + 「不报任何 TOPS/TOPS-W」",
        bool(pos["disclaimer"]) and len(pos["honest_limits"]) == 3
        and "不报任何 TOPS / TOPS-W" in pos["disclaimer"])

    # ⑭ 🔴 规模口径明标「可建模/可验证容量」
    chk("⑭ 规模口径明标「可建模并可验证的交叉点容量」",
        "可建模并可验证的交叉点容量" in card["scale_tiers"]["note"])

    # ⑮ 🔴 零外部框架：**ast 遍历真实 import**（不用源码字符串 in）⇒ 无 numpy/scipy/SPICE
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    mods: List[str] = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods += [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mods.append(node.module.split(".")[0])
    banned = {"numpy", "scipy", "ahkab", "PySpice", "ngspice", "pyspice"}
    hit = sorted(set(mods) & banned)
    chk("⑮ 零重计算/零外部框架：本模块不 import numpy/scipy/SPICE（ast 判定）", not hit)

    # ⑯ 护栏：非法输入抛错（0 行列 / bits 过大 / 零厚度）
    guard = 0
    for bad in (lambda: crossbar_capacity(0, 4),
                lambda: crossbar_capacity(4, 0),
                lambda: quant_error_rel_bound(61),
                lambda: layout_elements_flat(0, 4),
                lambda: sheet_resistance_ohm_per_sq(1.0, 0.0),
                lambda: sigma_rel_vs_n(0.01, 0)):
        try:
            bad()
        except ValueError:
            guard += 1
    chk("⑯ 护栏：非法 rows/cols · bits>60 · 零厚度 · n<1 均抛 ValueError", guard == 6)

    # ⑰ 每里程碑都有门禁数 + 结果文本（防空洞）
    chk("⑰ 里程碑完整：13 段 · 每段含 gate 数 + 结果文本",
        len(MILESTONES) == 13
        and all(m.get("gate", 0) > 0 and m.get("result") and m.get("seg_probes", 0) > 0
                for m in MILESTONES))

    # ⑱ landmark 登记含来源（A 级公开·未验证）
    chk("⑱ landmark 登记含 source（Mythic · mythic.ai）",
        bool(LANDMARKS_BRIEF) and all(e.get("source") for e in LANDMARKS_BRIEF))

    # ⑲ E6–E9 四块新能力面登记齐全（防「加了能力忘了卡」）
    chk("⑲ E6–E9 四块能力面登记齐全（layout/parasitic/mismatch/scale_pressure）",
        card["layout"].get("cell_elements") == 7
        and abs(card["parasitic"]["sheet_r_m1_ohm_sq"] - 0.084) < 1e-12
        and abs(card["mismatch"]["sigma_vth_mv"] - 5.00) < 1e-9
        and card["scale_pressure"]["facts"].get("compression_1024") == 3571.0)

    # ⑳ 可及规模上界单调（预算越紧 ⇒ N 越小）
    ceil_ = [c["max_rows"] for c in SCALE_CEILING]
    chk("⑳ 可及规模上界单调：预算越紧 ⇒ 可及行数越小（26 > 18 > 11 > 8）",
        ceil_ == sorted(ceil_, reverse=True) and len(set(ceil_)) == len(ceil_))

    # ㉑ E11-c 器件级内核面登记齐全（防「加了能力忘了卡」）
    dp = card["device_pde"]
    chk("㉑ E11-c 器件级内核面登记齐全（V_th 闭式⟷PDE · Q_s 跨点 · 量纲桥 · G-3 显式不自洽）",
        abs(dp["vth_golden_v"] - 0.4260) < 5e-4
        and dp["vth_rel_err_pct"] < 0.01
        and abs(dp["qs_cross_point_worst_rel_pct"] - 0.0108) < 1e-3
        and dp["param_consistency"]["consistent"] is False
        and dp["no_replace"].startswith("🔴"))

    # ㉒ E11-d 失效边界面登记齐全（两类边界分离 · 瓶颈判定 · 缺口量化 · 非 LDA 计算）
    dl = card["device_limits"]
    chk("㉒ E11-d 失效边界面登记齐全（数值/物理窗口 · 半宽比 · 缺口 · 文献项非 LDA 计算）",
        dl["numerical_window_phi_f"] == [-0.54, 2.54]
        and abs(dl["physical_over_numerical_halfwidth"] - 0.835) < 1e-3
        and abs(dl["gap_at_L65nm"]["rolloff_frac_of_vth"] - 0.379) < 1e-3
        and len(dl["not_computed_by_lda"]) == 4)

    # ㉓ 🔴 诚实（**E13-e 换代** · 能力升级必须**前后各扫一次方向**）：
    #     · 方向一（**贬低自身**）：E12 面的「不产 I-V」**已由 E13 闭合** ⇒ 卡内必须**显式标注**
    #       「已由 E13 闭合 / 不代表当前能力状态」，**不得**把它当**当前**能力状态复述
    #       （否则就是 E12-e 前的假贬低，会在对外演示时自相矛盾）。
    #     · 方向二（**抬高自身**）见 ㉗。
    #     口径演进：E12-e 前守「不许假称有 2D MOS」→ E12-e 改守「不许假称已产 I-V」
    #     → **E13-e 再换代**（该能力已真实存在）。
    blob12 = str(card["device_2d"]) + str(card["device_limits"])
    chk("㉓ 🔴 诚实（**贬低方向**）：E12 面的「不产 I-V」必须显式标注「已由 E13 闭合 / "
        "不代表当前能力状态」，且不得仍写成「E13 候选」",
        ("已由 E13 闭合" in blob12) and ("不代表当前能力状态" in blob12)
        and ("E13 候选" not in blob12))

    # ㉔ E12 2D MOS 面登记齐全（防「加了能力忘了卡」）
    d2 = card["device_2d"]
    chk("㉔ E12 2D 面登记齐全（长沟道收敛 · roll-off 对照 · DIBL/指数律 · 自然长度同式 · 能力闭合表）",
        d2["long_channel"]["rel_err_pct"] < 2.0     # 百分数（0.496 %）⇒ 阈值取 2 %
        and abs(d2["rolloff"]["dvth_vs_golden_mv"][0] + 176.3) < 1.0
        and d2["dibl"]["dibl_mv_per_v"] > 100.0
        and d2["dibl"]["r2_exp_law"] > 0.99
        and d2["natural_length_nm"]["same_formula"] is True
        and d2["capability_closure"]["closed"] == 3
        and d2["capability_closure"]["still_unavailable"] == 3)

    # ㉕ 🔴 方法学：2D 数值解只是 candidate（**不作 ORACLE**）；golden 仍指向教科书 1D 闭式
    chk("㉕ 🔴 2D 解只是 candidate（非 ORACLE）：golden 仍指向教科书 1D 闭式 · 只允许 2D→1D 方向",
        d2["golden"].startswith("教科书 1D")
        and "is_oracle=False" in d2["candidate"]
        and "只允许" in d2["oracle_semantics"])

    # ㉖ E13 输运面登记齐全（防「加了能力忘了卡」）
    dtf = card["device_transport"]
    chk("㉖ E13 输运面登记齐全（SS 双锚 · 长沟道 ⟷ 闭式 · 栅长趋势 · 守恒 · 输出特性 · "
        "V_th 双法 · 闭合表 4/4）",
        abs(dtf["thermal_limit_mv_dec"] - 59.53) < 0.01
        and dtf["long_channel"]["rel_err_pct"] < 10.0
        and dtf["ss_vs_length"]["ss_mv_dec"][0] > dtf["ss_vs_length"]["ss_mv_dec"][-1]
        and dtf["conservation"]["worst_rel"] < 1e-3
        and len(dtf["id_vd"]["I_d_a_per_m"]) == 4
        and dtf["capability_closure"]["closed"] == 4
        and dtf["capability_closure"]["still"] == 4)

    # ㉗ 🔴 诚实（**抬高方向** · E13-e 立）：能力到手后最容易滑成「已含量子修正 / 已算弹道 /
    #     已通过 PDK 标定 / 报了 TOPS」⇒ 必须**显式声明 DD 框架边界**，且说明
    #     **SS 热极限是硬下限而非渐近目标**、**迁移率常数 ⇒ I_on 不可当器件性能**。
    blob_all = (str(card["device_transport"]) + str(card["device_2d"]) + str(card["device_limits"])
                + str(card["device_pde"]) + " ".join(g["detail"] for g in card["gaps"])
                + card["honest_note"])
    forbidden_claims_hi = ("已含量子修正", "已支持量子修正", "已算弹道", "已支持弹道",
                           "已含速度饱和", "已算速度饱和", "已通过 PDK 标定", "已报 TOPS",
                           "已突破热极限", "2D 解作真值", "2D 为 ORACLE")
    chk("㉗ 🔴 诚实（**抬高方向**）：DD 框架边界显式（不含量子修正/隧穿/弹道 + 迁移率常数 ⇒ "
        "I_on 不可当器件性能）+ SS 热极限是**硬下限非渐近目标**，且不得声称已含量子修正/弹道/"
        "PDK/TOPS",
        ("漂移扩散" in blob_all) and ("迁移率" in blob_all)
        and ("不可当器件性能" in blob_all) and ("硬下限" in blob_all)
        and ("不是渐近目标" in blob_all)
        and all(k not in blob_all for k in forbidden_claims_hi))

    # ㉘ E14 外围面登记齐全（防「加了能力忘了卡」）
    dpf = card["device_periphery"]
    chk("㉘ E14 外围面登记齐全（DAC 全码扫描 · ADC 电荷守恒 · 采样保持离散闭式 · "
        "R_oc ⇒ 规模上界 · 行系统项 · 平台缺陷登记）",
        dpf["dac"]["codes_scanned"] == 256 and dpf["dac"]["max_abs_err_lsb"] < 1.0
        and dpf["adc"]["charge_conservation_rel"] < 1e-6
        and dpf["sample_hold"]["rel_err_vs_discrete"] < 1e-9
        and dpf["scale_ceiling"]["n_max"][0] > dpf["scale_ceiling"]["n_max"][-1]
        and dpf["row_system_term"]["spread_with_driver"] > 1e-4
        and dpf["platform_defect"]["probe_v"] < 0.0)

    # ㉙ 🔴 诚实（E14 · 两个方向）：① 外围建模取舍必须**显式**（比较器判决器抽象 / 行驱动宏模型 /
    #     不报 TOPS）——**抬高方向**（把宏模型说成真晶体管电路）；② 平台缺陷（vcvs 极性）
    #     必须**已登记且未被抹掉** —— **贬低方向**（假装平台无缺陷）。
    blob_e14 = str(card["device_periphery"]) + " ".join(g["detail"] for g in card["gaps"])
    chk("㉙ 🔴 诚实（E14 · 双向）：外围建模取舍显式（判决器抽象 / 宏模型 / 不报 TOPS）+ "
        "平台缺陷（vcvs 极性相反）**已登记**且不得被抹掉",
        ("判决器抽象" in blob_e14) and ("宏模型" in blob_e14) and ("TOPS" in blob_e14)
        and ("vcvs" in blob_e14) and ("极性相反" in blob_e14)
        and all(k not in blob_e14 for k in ("已修 mna", "已修复 vcvs", "无建模取舍",
                                            "无平台缺陷")))

    ok_all = all(res.values())
    if verbose:
        for m in msgs:
            print("  " + m)
    return ok_all


if __name__ == "__main__":
    print("电子计算芯片案例卡自检：", "ALL PASS" if run_selfchecks(verbose=True) else "FAIL")
