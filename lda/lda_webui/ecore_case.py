"""电子计算芯片案例卡（WebUI 只读端点数据源）· D-155 建卡 → D-160（E10）升 E1–E9 →
E11-e 升 E1–E11 → E12-e 升 E1–E12 → D-173（E13-e）升 E1–E13 → D-177（E14-e）升 E1–E14 →
D-180（E15-e）升 E1–E15 → **D-184（E16-e）升 E1–E16** → **D-188（E17-e）升 E1–E17 全链**。

═══════════════════════════════════════════════════════════════════════════
定位
═══════════════════════════════════════════════════════════════════════════
电子计算征程「吃狗粮」**E1…E17（D-150…D-187）** 的**只读案例**：用 LDA 亲手设计一颗
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
    → E14 真 DAC / ADC / 行驱动外设（把「设计链」补成「系统链」）            （D-174…D-176）
    → E15 端到端误差预算链（把 E1–E14 串成一个答案：实际几个有效位）        （D-178…D-180）
    → E16 权重编程通路（权重怎么写进阵列 / 写进去有多准 / 写错多少）        （D-181…D-183）
    → E17 时序 / 时钟预算链（时间维度上的 E15：五阶段节拍 / 时间按拓扑合成）  （D-185…D-187）

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
    "DEVICE_PDE_FACTS", "DEVICE_LIMITS_FACTS", "DEVICE_2D_FACTS", "TIMING_FACTS",
    "DEVICE_TRANSPORT_FACTS", "DEVICE_PERIPHERY_FACTS", "BUDGET_FACTS",
    "WEIGHT_PROG_FACTS", "COL_SHARE_FACTS",
    "crossbar_capacity", "quant_error_rel_bound", "layout_elements_flat",
    "layout_elements_hier", "hier_compression_ratio", "sheet_resistance_ohm_per_sq",
    "wire_resistance_ohm", "pelgrom_sigma_vth_mv", "pelgrom_sigma_beta_pct",
    "elmore_tau_rc", "sigma_rel_vs_n",
    "lsb_to_rel_pct", "output_effective_bits",
    "case_card", "run_selfchecks",
]

# ═══════════════════════════ 常量（与平台模块同源）═══════════════════════════
CASE_ID = "LDA-E · 电子计算芯片（模拟计算核 / MVM 交叉阵列）· E1–E18 全链"

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


# ═══════════════════════ E15（D-178…D-180）端到端误差预算链 ═══════════════════════
#   ⚠️ 卡内数字必须与 ecore/budget.py **实测同口径**（案例卡门禁 B21 守着对拍）。
BUDGET_FACTS = {
    "budget_8x8": {
        "terms": [
            {"name": "ir_drop", "category": "systematic", "rel_pct": 0.87897, "source": "E7/E9"},
            {"name": "device_mismatch", "category": "random", "rel_pct": 0.59524, "source": "E8/E9"},
            {"name": "row_driver_load", "category": "systematic", "rel_pct": 0.79916, "source": "E14"},
            {"name": "adc_quantization", "category": "bounded", "rel_pct": 0.19531, "source": "E3"},
            {"name": "dac_inl", "category": "bounded", "rel_pct": 0.01035, "source": "E14"},
            {"name": "adc_sar", "category": "bounded", "rel_pct": 0.39062, "source": "E14"},
        ],
        "worst_pct": 4.06012, "typical_pct": 2.61762,
        "worst_bits": 4.622, "typical_bits": 5.256,
        "dominant": "device_mismatch", "dominant_share_pct": 44.0,
    },
    "scale_curve": [
        {"n": 8, "worst_pct": 4.0601, "worst_bits": 4.622, "dominant": "device_mismatch"},
        {"n": 16, "worst_pct": 6.4120, "worst_bits": 3.963, "dominant": "ir_drop"},
        {"n": 32, "worst_pct": 16.0547, "worst_bits": 2.639, "dominant": "ir_drop"},
        {"n": 64, "worst_pct": 39.4115, "worst_bits": 1.343, "dominant": "ir_drop"},
        {"n": 128, "worst_pct": 67.0083, "worst_bits": 0.578, "dominant": "ir_drop"},
        {"n": 256, "worst_pct": 84.1844, "worst_bits": 0.248, "dominant": "ir_drop"},
    ],
    "crossover": {"n_lo": 8, "dom_lo": "device_mismatch", "n_hi": 32, "dom_hi": "ir_drop",
                  "note": "小 N 由器件失配主导（σ∝1/√N ⇒ 小 N 更差）· 大 N 由 IR drop 主导（∝N²）"
                          "⇒ 小阵列先治失配（器件面积/校准）、大阵列先治 IR drop（驱动架构/金属）"},
    "scale_ceiling": {"budget_pct": 5.0, "full_chain_n_max": 12, "ir_drop_only_n_max": 18,
                      "note": "🔴 全链口径严格于仅 IR drop（E9 原口径乐观 33%）："
                              "只算 IR drop 得 N≤18，加入失配+行驱动+转换器后只能到 N≤12"},
    "bridge": {"lsb8_pct": 0.390625,
               "self_consistency": "bits_eff(lsb_to_rel_pct(k)) == k（纯代数自洽锚）"},
    "composition": {"systematic": "代数 Σ", "random": "RSS → 3σ", "bounded": "代数 Σ → √3（typical）",
                    "worst_pct": "Σsys + 3σ_tot + Σbnd",
                    "typical_pct": "Σsys + σ_tot + Σbnd/√3",
                    "note": "🔴 简单相加是错的、全用 RSS 也是错的"},
    "effective_bits_semantics": "🔴 `output_effective_bits` = log2(100/最坏相对误差[%])，"
                                "**本项目自定义量，不是 IEEE ENOB**；只覆盖静态（不含动态 / 时序）",
    "honest_boundary": "只覆盖静态（给定权重与输入的静态精度）—— 不含时序 / 动态 / 建立时间 / "
                       "采样率 / 时钟抖动 / 热梯度空间分布 / 老化漂移 / 电源噪声；"
                       "合成律是**保守工程口径**、**不是严格概率保证**（typical 的 Σb/√3 假设均匀分布）；"
                       "参数为公开典型量级占位（**非 PDK**）；器件侧仍 **DD 框架 + 常数迁移率**；"
                       "**不报 TOPS / TOPS-W / fJ/op**",
    "protection": "🔴 **只读消费** E7/E8/E9/E14 接口，**不改**任何既有默认值（门禁 G8 逐位守住）",
}

WEIGHT_PROG_FACTS = {
    # ① 写入噪声地板（G-4 闭式 ⟷ 独立 MC）
    "noise_floor": {
        "formula": "sigma_inf = sigma_p / sqrt(alpha*(2-alpha))",
        "sigma_cell_pct": 0.70014,          # 闭式
        "mc_pct": 0.69922,                  # 4000-trial MC（seed=0）
        "mc_rel_pct": 0.13,
        "alpha": 0.3, "sigma_pulse_pct": 0.5, "tol_pct": 1.0, "max_pulses": 64,
        "iters_to_tol": 13,                 # ceil(ln(tol/e0)/ln(1-alpha))
        "floor_range_pct": [0.5, 0.70014],  # [sigma_p, sigma_inf]
        "escalation_x": 1.40028,            # 1/sqrt(alpha*(2-alpha))
        "semantics": "🔴 **单脉冲噪声 sigma_p 是硬地板** —— 写-校验最多把地板抬升 "
                     "1/sqrt(alpha*(2-alpha)) 倍；tol < sigma_inf 时**期望意义上不可达** "
                     "⇒ 要提精度必须降 sigma_p（脉冲整形/电流限制），**不是加脉冲数**",
    },
    # ② 电平量化（G-1）
    "level": {
        "levels_6bit": 64, "lsb_rel_pct_6bit": 1.5873,
        "formula": "lsb_rel = 1/(2^k - 1)（相对**电导窗口**）",
        "bound_semantics": "🔴 电平在窗口内**等间距** ⇒ 每单元量化误差**绝对值同为半步长**（与 g 无关）"
                           "⇒ 输出相对界 = half_step·Σ|x|/|Σ g_i x_i| = **half_step / 平均电导**；"
                           "**低电导单元的「大相对误差」在求和里并不放大**",
    },
    # ③ 误差预算对比（8×8 · 接 E15）
    "budget": {
        "base":   {"worst_pct": 4.06012, "bits": 4.6223, "dominant": "device_mismatch", "dom_share_pct": 44.0},
        "analog": {"worst_pct": 4.20838, "bits": 4.5706, "dominant": "device_mismatch", "dom_share_pct": 37.2},
        "mlc6":   {"worst_pct": 5.27562, "bits": 4.2445, "dominant": "device_mismatch", "dom_share_pct": 30.4},
        "mlc8":   {"worst_pct": 4.47205, "bits": 4.4829, "dominant": "device_mismatch", "dom_share_pct": 35.2},
        "note": "🔴 口径：base = E15 四类误差（不含编程）· analog = 仅写入残差 · mlcN = 写入残差 + N 位电平量化",
    },
    # ④ 电平位数敏感性（≥8 位饱和）
    "level_sensitivity": {
        "4":  {"level_pct": 4.4824, "worst_pct": 8.69080, "bits": 3.5244},
        "6":  {"level_pct": 1.0672, "worst_pct": 5.27562, "bits": 4.2445},
        "8":  {"level_pct": 0.2637, "worst_pct": 4.47205, "bits": 4.4829},
        "10": {"level_pct": 0.0657, "worst_pct": 4.27410, "bits": 4.5482},
        "12": {"level_pct": 0.0164, "worst_pct": 4.22480, "bits": 4.5650},
        "note": "🔴 **≥8 位后收益饱和**（4.4829 → 4.5650，渐近 4.5706 = 纯模拟写入）"
                "—— 残余误差转由器件失配 + IR drop 决定 ⇒「多给几位电平」不是免费的午餐",
    },
    # ⑤ 5% 预算可及规模（收缩）
    "scale_ceiling": {
        "budget_pct": 5.0,
        "default_n_max": 12, "analog_n_max": 11, "mlc6_n_max": 1, "mlc8_n_max": 10,
        "note": "🔴 **电平项是 N 无关的常量**（有界项不被 1/sqrt(N) 平均）⇒ MLC 6 位下 5% 误差预算"
                "**连 2x2 都不满足**（n_max=1 是「无 N>=2 可行」的哨兵值）—— 本段最强的架构结论",
    },
    # ⑥ 漂移（幂律 + 重校准间隔 + 共模/离散分离）
    "drift": {
        "curve": [
            {"t_s": 1.0, "factor": 1.0, "common_mode_pct": 0.0, "spread_pct": 0.0},
            {"t_s": 10.0, "factor": 0.8913, "common_mode_pct": 10.87, "spread_pct": 0.345},
            {"t_s": 100.0, "factor": 0.7943, "common_mode_pct": 20.57, "spread_pct": 0.691},
            {"t_s": 1000.0, "factor": 0.7079, "common_mode_pct": 29.21, "spread_pct": 1.036},
            {"t_s": 10000.0, "factor": 0.631, "common_mode_pct": 36.9, "spread_pct": 1.382},
        ],
        "recalibration_s": {"beta_1pct": 1.2226, "beta_5pct": 2.7895, "beta_10pct": 8.2253},
        "nu": 0.05, "sigma_nu": 0.0015, "t0_s": 1.0,
        "semantics": "🔴 **共模漂移**（所有单元同向）**可被单次全局增益校准消除 ⇒ 不进预算**；"
                     "进预算的只有 **nu 的单元间离散（校准不掉）** —— "
                     "**一个能被单次校准消掉的项，不是精度上限**（与 E8 列系统项/L1 校准同型）",
        "conditional": "🔴 漂移结论**条件于 nu**（nu=0.05 为公开典型量级占位 · 非 PDK）"
                       "⇒ t_max 是**参数推论而非普适断言**；正确读法 =「RRAM 类模拟 CIM 必须频繁重刷」",
    },
    # ⑦ 良率 / 卡位
    "yield": {
        "formula": "Y = (1-p)^N",
        "cells_64_p_1e-3": 0.937975, "cells_48_p_1e-3": 0.953111,
        "stuck_tail": {"p": 1e-3, "mean_pct": 1.53, "max_pct": 22.83, "yield_48_pct": 95.31,
                       "note": "🔴 **卡位是良率问题、不是均值精度问题** ⇒ 预算默认不含卡位"
                               "（另设 include_stuck）"},
    },
    # ⑧ 端到端（接 E8 mvm_output）
    "end_to_end": {
        "trials": 600, "emp_sigma_pct": 0.2522, "strict_sigma_pct": 0.2514, "rel_pct": 0.31,
        "max_pct": 1.0692, "bound_pct": 1.76025,
        "semantics": "🔴 实测 sigma 必须与**矩阵感知严格式** sigma*sqrt(Sigma(gx)^2)/|Sigma gx| 对拍"
                     "（单列 · **带符号**序列）—— 拿「逐列 max」（极值统计量）比 sigma 必然对不上；"
                     "「1/sqrt(N)」是**理想化**（隐含各单元电导相同）",
    },
    # ⑨ 误差项分类（决定是否被 1/sqrt(N) 平均）
    "categories": {"residual": "random", "level": "bounded",
                   "note": "🔴 写入残差 = **RANDOM**（单元独立 ⇒ 被 1/sqrt(N) 平均）· "
                           "电平量化 = **BOUNDED**（**N 无关**）—— 分类不是形式主义"},
    "window": {"ratio": 4.9998, "worst_cell_level_pct": 2.401,
               "note": "由 E3 口径 g_base = 1.5·max|W|·s 导出（**非**器件窗口）；"
                       "最坏单元值仅作告警，**不进**预算"},
    # ⑩ 保护性约束
    "protection": "🔴 `budget.collect_terms` 新增的 `include_programming` **默认 False** ⇒ "
                  "**E15 已发布数字逐位不变**（8x8 worst 4.06012% / bits 4.6223 / 5% 上界 N<=12）；"
                  "门禁 B12 守住默认不变 + 探针 C5 专模拟「有人把默认改成 ON」⇒ 必红；"
                  "**E15 自己的门禁自动成为 E16 的回归保护**",
    "honest_boundary": "权重编程为**行为级**模型（比例修正 + 加性噪声）：参数（alpha / sigma_p / tol / nu / "
                       "p_stuck）均为**公开典型量级占位 · 非 PDK · 无实测锚** ⇒ 结论随参数变；"
                       "不含细丝动力学 / 脉冲宽度依赖 / 温度加速；无 endurance/retention 联合退化；"
                       "**只覆盖静态**（不含编程时间与能耗）；🔴 **共模漂移可被单次全局增益校准消除 "
                       "⇒ 不进预算**（进预算的只有 nu 的单元间离散）；**不报 TOPS / TOPS-W / fJ/op**",
}

TIMING_FACTS = {
    "process": {
        "bits": 8, "r_oc_ohm": 0.999, "r2r_node_cap_f_placeholder": 0.5e-12,
        "t_clk_from_cdac_ns": 10.2373, "non_pdk": True,
    },
    "stages": [
        {"name": "row_line", "t_ns": 0.000029, "share_pct": 0.0,
         "note": "Elmore 3.119 fs **+** 驱动源阻抗 1.545 fs（**串联**）· R_oc=0 ⇒ 退化为纯 Elmore"},
        {"name": "col_line", "t_ns": 0.000013, "share_pct": 0.0,
         "note": "TIA 虚地 ⇒ 无 Rf·C 项"},
        {"name": "sample_hold", "t_ns": 6.238325, "share_pct": 4.81,
         "note": "τ = rs·cs = 1 ns（**复用 E14 `CONV_PROCESS`**）"},
        {"name": "sar_convert", "t_ns": 92.135256, "share_pct": 71.11,
         "note": "`(bits+1)·t_clk` = 9 × 10.2373 ns · t_clk 由 **CDAC 建立推导**（G-5）"},
        {"name": "dac_settle", "t_ns": 31.191620, "share_pct": 24.07,
         "note": "τ = r_unit·c_node · 🔴 `c_node` 为**显式占位** ⇒ `param_sensitive=True`"},
    ],
    "totals": {
        "serial_ns": 129.565246, "pipelined_period_ns": 92.135256,
        "pipelined_latency_ns": 129.565246, "pipeline_gain_frac": 0.28889,
        "max_sample_rate_msa": 7.7181,
        "dominant": "sar_convert", "dominant_share_pct": 71.11,
    },
    "synthesis_law": {
        "serial": "Σ t_i", "pipelined_steady": "max t_i", "pipelined_latency": "Σ t_i",
        "wrong": "√Σt²（RSS）—— **对时间用 RSS 是错的**（串行阶段的时间必然叠加，"
                 "不满足「独立随机量」前提）",
        "contrast": "E15 `budget.combine` 按**类型**（系统 Σ / 随机 RSS→kσ / 有界 Σ→√3）；"
                    "E17 `timing.combine_time` 按**拓扑**（串行 Σ / 流水线 max）"
                    "⇒ 🔴 **E15 的合成律不可平移到 E17**",
        "demo": {"stages_ns": [3, 7, 11], "serial_ns": 21.0, "pipelined_ns": 11.0,
                 "rss_ns": 13.38, "gain": 0.4762},
        "note": "门禁 **B5** 特意断言「**对时间取 RSS 会给出不同值**」"
                "（13.38 ⟷ 21.0 ns）—— 否则「两套合成律」只是口号",
    },
    "scale_vs_time": {
        "n_pair": [8, 1024], "tau_row_span_x": 12556.5, "serial_span_x": 1.00469,
        "serial_n8_ns": 129.5652, "serial_n1024_ns": 130.1732,
        "conclusion": "阵列 τ_row 随 N 跨 **12556.5×**（∝N²）而**每样本耗时只跨 1.00469×** "
                      "⇒ 🔴 **规模墙是「精度墙」（E15：IR drop ∝N²、5% 预算只到 N≤12）"
                      "不是「速度墙」** —— 加行列**不拖慢采样率**，但**会毁掉有效位数**",
    },
    "crossover": {
        "ps": 135, "p_100ps": 1341, "ns": 4238,
        "analytic_ns": 4245.8, "rel_pct": 0.184,
        "conclusion": "阵列 τ 达 1 ns 需 **N≈4238**（解析 4245.8 ⟷ 二分 4238）"
                      "⇒ **远超 E15 的可及规模（N≤12）** ⇒ 在可达规模内阵列 RC **永不是时间瓶颈**",
    },
    "bits_cross": {
        "points": [
            {"bits": 4, "serial_ns": 22.5717, "dominant": "dac_settle", "share_pct": 76.8},
            {"bits": 6, "serial_ns": 43.0462, "dominant": "dac_settle", "share_pct": 56.4},
            {"bits": 8, "serial_ns": 129.5652, "dominant": "sar_convert", "share_pct": 71.1},
            {"bits": 10, "serial_ns": 596.2844, "dominant": "sar_convert", "share_pct": 92.3},
            {"bits": 12, "serial_ns": 3129.7906, "dominant": "sar_convert", "share_pct": 98.3},
        ],
        "why": "**SAR ∝ (bits+1)²**（拍数 × 每拍建立时间，而 `t_clk` 本身也 ∝ (bits+1)）"
               "而 **DAC ∝ (bits+1)** ⇒ **必然交叉**（本例交叉点在 6–8 bit 之间）",
        "design": "低位数优化 **DAC 建立**（降 `r_unit` 或节点电容）；高位数**只能优化 SAR**"
                  "（降 `C_u` / 更高 W/L 开关 / 分段 CDAC）",
    },
    "clock_budget": {
        "target_ns": 160.0, "fixed_ns": 37.43, "t_clk_max_ns": 13.6189,
        "back_calc_residual_s": 0.0, "cdac_t_clk_ns": 10.2373,
        "note": "反解 + **代回验证**（`fixed + (bits+1)·t_clk_max == target`）· "
                "目标小于固定开销时显式 `feasible=False`",
    },
    "roc_sensitivity": {
        "r_oc_ohm": 100.0, "row_stage_ns": 0.000984506, "serial_ns": 129.566201,
        "rel_increase_pct": 0.0000077,
        "note": "R_oc 从 0 → 100 Ω，行线阶段涨 50×（1.9e-5 → 9.85e-4 ns），"
                "而**每样本耗时相对增幅仅 7.7e-6 %** ⇒ 🔴 **R_oc 伤精度（E14 上界收缩），不伤速度**",
    },
    "closed_form": {
        "rc_settle": "t = τ·ln(1/ε)",
        "half_lsb": "t = τ·(k+1)·ln2",
        "elmore": "τ = r·c·n(n+1)/2（**复用 E7**）",
        "sar": "t = (n_bits+1)·t_clk",
        "cdac_tclk": "t_clk = settle_half_lsb(R_on·C_u·2^n, k)（**复用 E14**）",
    },
    "protection": {
        "e15_worst_pct": 4.06012, "e15_bits": 4.6223, "e15_n_max": 12,
        "periphery_keys": ["a_gain", "r_out_open_ohm", "vfs_v", "vdd_v"],
        "note": "**只读消费** E7/E14 · **不给** `PERIPHERY_PROCESS` 加时间键（E14 行驱动保持原样）"
                "⇒ **E15/E16 已发布数字逐位不变**（门禁 B15/B16 守着）",
    },
    "disclosure": "🔴 **只报「每样本耗时（ns）」与相对量 · 绝不报 TOPS / TOPS-W / fJ/op**"
                  "（既无功耗模型、也无实测硅）；五阶段为**宏模型级**估算"
                  "（行驱动仍 **VCVS + 开环输出电阻宏模型** · 无真实 GBW/摆率 · "
                  "**比较器延时 / 时钟树 / 抖动未建模** · R-2R 节点电容为**显式占位**）；"
                  "**只覆盖静态 + 一阶 RC 建立**（不含摆率 / 时钟偏斜与抖动 / 供电噪声 / "
                  "温度梯度 / 老化 / 工艺角）；**不做能量与功耗估算**；参数**非 PDK** ⇒ 结论随参数变。",
}


#: E18 · 列侧共享与架构权衡（面积维度 · 全仓此前空白）
COL_SHARE_FACTS = {
    "process": {
        "bits": 8, "c_unit_f": 1.0e-12, "cap_density_ff_per_um2": 2.0,
        "adc_logic_area_um2": 800.0, "tia_area_um2": 400.0,
        "mux_switch_area_um2": 25.0, "temperature_k": 300.0, "k_sigma": 3.0,
        "non_pdk": True,
    },
    # ① 量级事实：为什么列侧**必须**共享
    "magnitude": {
        "unit_cap_area_um2": 128000.0, "unit_cap_area_mm2": 0.128,
        "converter_area_um2": 128800.0,
        "converter_cap_over_logic": 160.0,
        "array_footprint_um": [152.4, 152.9], "array_footprint_um2": 23301.96,
        "readout_over_array_ratio": 354.923,
        "full_parallel_mm2": 8.2704, "fully_serial_mm2": 0.1308,
        "arch_ratio": 63.229,
        "note": "E1–E17 的列侧读出（TIA + ADC）**始终是「每列一份」**（`crossbar_mvm` 每列一个理想运放 · "
                "`mvm_datapath` 每列一个 ADC · `converter.sar_convert` 是单通道）⇒ 列侧读出**完全不进面积**。"
                "在二进制 CDAC 口径下（`C_tot = C_u·2^bits` · MIM 密度 2 fF/µm²）**单列电容面积 "
                "128 000 µm²**，而 64×64 阵列本体足迹仅 **23 301.96 µm²** ⇒ "
                "**读出 = 阵列的 354.92 倍**（全并行 N=64 列侧 **8.2704 mm²**）—— "
                "**列侧读出压倒性支配芯片面积**，这就是「为什么必须共享」。",
    },
    # ② 第一原理：面积-时间乘积守恒
    "first_principle": {
        "law": "A_total × 每列周期 = N·A_u·T_conv = **常数（与 K 无关）**",
        "pairing": "全并行 (K=1)：面积 N·A_u / 每列周期 T_conv；K 列共享：(N/K)·A_u / K·T_conv",
        "product_um2_s": 0.7594893422640095, "k_points": [1, 2, 4, 8, 16, 32],
        "spread": 0.0,
        "escape": "要突破这条双曲线只有两条路：**① 缩短 `T_conv` 本身**（→ 第二原理）；"
                  "**② 复制瓶颈级**（反向沿曲线走 → 接 E17 的 0.289 锚）",
        "note": "门禁 **B5** 断言跨 6 个 K 的乘积相对散布 **0.00e+00** ⇒ "
                "**共享只沿「等面积-时间双曲线」移动，不改变乘积**。",
    },
    # ③ 第二原理：保吞吐共享 ⇒ 面积 ∝1/K²
    "second_principle": {
        "law": "A(K) = (N/K)·( C_tot(1)/(ρ·K) + A_logic ) = "
               "N·C_tot(1)/(ρ·K²) + N·A_logic/K",
        "chain": "共享 K 倍同时保吞吐 ⇒ `T_conv` 须缩短 K 倍；由 E17 G-5 "
                 "`T_conv ∝ C_tot·(bits+1)²` ⇒ **缩 `T_conv` 的唯一物理路径是降 `C_tot`**"
                 "（`C_tot(K) = C_tot(1)/K`）",
        "slope_plain": -1.0, "slope_keep_cap": -2.0, "slope_keep_total": -1.952465,
        "k_points": [1, 2, 4, 8, 16, 32],
        "note": "门禁 **B6 三条分开判**：不保吞吐**严格 ∝1/K**（−1.000000）· 保吞吐"
                "**仅电容项严格 ∝1/K²**（−2.000000）· **双项混合 −1.952465 ∈ (−2,−1)**"
                "（`K*` 之后退化为 ∝1/K）—— 双项闭式的标度律**不能拿整体拟合断言单一指数**。",
    },
    "k_star": {
        "k_star": 160.0, "logic_area_um2": 800.0, "cap_over_logic_at_k1": 160.0,
        "law": "K* = C_tot(1)/(ρ·A_logic)",
        "note": "**拐点**：该点电容项 == 逻辑项（800 µm²）。`K<K*` 电容支配（**1/K² 收益显著**）；"
                "`K>K*` 逻辑面积支配（**退化为 ∝1/K**）",
    },
    # ④ 第三腿：诚实拒绝造腿
    "ktc": {
        "sigma_law": "σ = √(kT/C_tot)", "bits_law": "log2(V_ref/(k_σ·σ))",
        "bits_ceiling_at_256pF": 16.338559,
        "k_share_crit_8bit": 104788.4, "sigma_at_crit_v": 0.0013020833,
        "c_tot_at_crit_f": 2.4430197473280004e-15,
        "conclusion": "🔴 **诚实拒绝造腿**：kT/C 是物理律，但 8 bit / 1 pF / 300 K / k_σ=3 时位数上限 "
                      "**16.34 位**，跌到 8 位需共享度 **K ≈ 1.0479×10⁵** ⇒ **远超任何合理共享度**。"
                      "⇒ **共享的真实代价是「吞吐」不是「精度」** —— 把公式与交叉点如实给出，"
                      "**不硬造精度腿**。",
    },
    "architectures": {
        "n_cols": 64, "bits": 8,
        "rows": [
            {"name": "fully_parallel", "k_adc": 1, "area_um2": 8270400.0,
             "area_mm2": 8.2704, "per_col_sps": 10853608.53, "bits_ceiling": 16.338559},
            {"name": "tia_shared_k4", "k_adc": 1, "area_um2": 8251200.0,
             "area_mm2": 8.2512, "per_col_sps": 10853608.53, "bits_ceiling": 16.338559},
            {"name": "adc_shared_k4_plain", "k_adc": 4, "area_um2": 2088000.0,
             "area_mm2": 2.088, "per_col_sps": 2713402.13, "bits_ceiling": 15.338559},
            {"name": "adc_shared_k4_keep", "k_adc": 4, "area_um2": 552000.0,
             "area_mm2": 0.552, "per_col_sps": 10853608.53, "bits_ceiling": 15.338559},
            {"name": "fully_serial", "k_adc": 64, "area_um2": 130800.0,
             "area_mm2": 0.1308, "per_col_sps": 169587.63, "bits_ceiling": 13.338559},
        ],
        "plain_over_keep_k4": 3.782609,
        "note": "五条路线（N=64 / 8 bit）：**全并行 8.2704 mm² → 全串行 0.1308 mm²（63.229×）**，"
                "面积沿共享度**单调降**。🔴 **保吞吐 k4**（552 000 µm²）比**不保吞吐 k4**"
                "（2 088 000 µm²）**再省 3.782609×**（≈K 倍），且**每列速率 == 全并行**"
                "（10.8536 MSa/s）⇒ **吞吐真的被保住了**（这正是第二原理的兑现）。",
    },
    "recommend": {
        "n_cols": 64, "bits": 8, "target_sps": 10.0e6,
        "k_best": 64, "n_adc_units": 1, "c_tot_unit_f": 4.0e-12,
        "area_um2": 30000.0, "bits_ceiling": 13.338559,
        "area_ratio_vs_parallel": 275.68,
        "note": "共享度**饱和到列数**（k=64 ⇒ 只需 **1 个 ADC** · `C_tot` 降到 **4 pF**）⇒ "
                "面积 **30 000 µm²**（全并行 8 270 400 µm² 的 **1/275.68**）。"
                "🔴 上界 = **列数 N**（共享度 > N 无意义）与 **kT/C 位数上限**（本口径下远未触及）。",
    },
    "replication_vs_sharing": {
        "shared_k4_um2": 2088000.0, "shared_k4_sps": 2713402.13,
        "replicated_r4_um2": 33081600.0, "replicated_r4_sps": 43414434.10,
        "shared_spread": 0.047013, "replicated_spread": 0.0,
        "note": "🔴 接 E17 的 **0.289** 锚（流水线几无收益 ⇒ 提吞吐只能**并行复制瓶颈级**）："
                "**复制**方向 `A × 每列周期` **严格常数**（散布 0.0）⇒ "
                "**提吞吐（复制）与省面积（共享）是同一条 `A×周期 = 常数` 双曲线的两端**。",
    },
    "closed_form": {
        "thermal_noise": "σ = √(k_B·T/C)",
        "bits_ceiling": "log2(V_ref/(k_σ·σ))",
        "cap_area": "A = C/ρ",
        "area_time_product": "A_total × 每列周期 = N·A_u·T_conv（与 K 无关）",
        "keep_throughput_area": "A(K) = N·C_tot(1)/(ρK²) + N·A_logic/K",
        "k_star": "K* = C_tot(1)/(ρ·A_logic)",
        "ktc_crossing": "K_crit = C_tot(1)·V_ref²/(k_σ²·kT·4^bits)",
    },
    "protection": {
        "e15_worst_pct": 4.06012, "e15_bits": 4.6223, "e15_n_max": 12,
        "conv_process_keys_unchanged": True, "timing_process_keys_unchanged": True,
        "keep_throughput_default_off": True,
        "note": "**只读消费** E14/E17 —— **不改** `CONV_PROCESS` / `TIMING_PROCESS` / 任何既有默认值；"
                "`keep_throughput` **默认 False**（保守口径）⇒ **E15/E16/E17 已发布数字逐位不变**"
                "（模块门禁 B18/B19 守着）。",
    },
    "disclosure": "🔴 面积为**宏模型占位**（ρ=2 fF/µm² · A_logic=800 µm² · A_tia=400 µm² —— "
                  "**公开量级 · 非 PDK · 无实测锚**）⇒ 结论随参数变；真实芯片用分段 CDAC / 更小 `C_u` / "
                  "采样电容共享 ⇒ 面积远小于此；**只覆盖静态**（不含动态功耗 / 时钟树 / 供电网络 / "
                  "驱动器面积 / IO pad）；共享的**动态代价（多路开关电荷注入 / 串扰 / 采样孔径抖动）未建模**；"
                  "**不做功耗估算 ⇒ 不谈能效**；**绝不报 TOPS / TOPS-W / fJ/op**。",
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
    "结构为教科书突变结 + 2 nm 平滑，**无 LDD/halo/应力/栅重叠**；"
    "⑧ E16 的**权重编程通路**是**行为级**模型（写-校验 = 比例修正 + 加性噪声）："
    "参数（α / σ_p / tol / ν / p_stuck）均为**公开典型量级占位（非 PDK · 无实测锚）**"
    "⇒ 结论**随参数变**，漂移结论**条件于 ν**；**不含**细丝动力学 / 脉冲宽度依赖 / 温度加速，"
    "**无 endurance / retention 联合退化**；🔴 **共模漂移可被单次全局增益校准消除 ⇒ 不进预算**"
    "（进预算的只有 ν 的单元间离散）—— **一个能被单次校准消掉的项，不是精度上限**；"
    "⑨ E18 的**列侧共享 / 面积**是**宏模型级估算**（ρ=2 fF/µm² · 逻辑面积 800 µm² · TIA 400 µm² · "
    "开关 25 µm² 均为**公开量级占位 · 非 PDK · 无实测锚**）⇒ **结论随参数变**；"
    "真实芯片用分段 CDAC / 更小 `C_u` / 采样电容共享 ⇒ 面积远小于此；"
    "**只覆盖静态**（不含动态功耗 / 时钟树 / 供电网络 / 驱动器面积 / IO pad）；"
    "共享的**动态代价（多路开关电荷注入 / 串扰 / 采样孔径抖动）未建模**；"
    "🔴 **不做功耗估算 ⇒ 因此绝不报 TOPS / TOPS-W / fJ/op** —— 本段只报「面积（µm²/mm²）/ "
    "每列采样率（Sa/s）/ 相对倍数」；🔴 **kT/C 位数上限 16.34 位远高于 8 位** ⇒ "
    "本段**不宣称共享受精度限制**（真实代价是**吞吐**，**不硬造精度腿**）。"
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
    {"id": "E15", "code": "D-178…D-180",
     "title": "端到端误差预算链（把 E1–E14 串成一个答案）",
     "gate": 20, "seg_probes": 6,
     "result": "把前 14 段各自给出的**单点误差**合成**一条链**，回答「这颗阵列实际几个有效位」："
               "① **口径桥** —— 统一锚点 `1 LSB @ k bit = 100/2^k %FS`（自洽锚 "
               "`bits_eff(lsb_to_rel_pct(k)) == k`，纯代数）；"
               "② **三分类合成律**（系统 **Σ** / 随机 **RSS→3σ** / 有界 **Σ→√3**；"
               "🔴 **简单相加是错的、全用 RSS 也是错的**）⇒ **8×8 worst 4.0601% ⇒ 有效精度仅 "
               "4.622 位**（不是 8 位；typical 2.618% ⇒ 5.256 位）；"
               "③ **精度 vs N**：8→**4.622** · 16→3.963 · 32→2.639 · 64→1.343 · 128→0.578 · "
               "256→**0.248** 位；🔴 **主导项交叉点**：N≤8 由**器件失配**主导（44.0%）· "
               "N≥16 由 **IR drop** 主导 ⇒ **小阵列先治失配、大阵列先治 IR drop**；"
               "🔴 **全链 5% 可及上界 N≤12** ⟷ 仅 IR drop **N≤18** ⇒ **E9 原口径是乐观的**"
               "（严格 33%）。🔴 仅 IR drop 时**委托 E9** ⇒ **逐值相等**（泛化必须退化为特例）；"
               "全链用**扫描而非二分**（`worst(N)` 未必单调：IR drop 升 / 失配降）。"},
    {"id": "E16", "code": "D-181…D-183",
     "title": "权重编程通路（补上「权重怎么写进阵列」这一此前完全不存在的一环）",
     "gate": 25, "seg_probes": 6,
     "result": "E1–E15 全程把权重当**已知且精确**的输入（`crossbar_mvm` 直接吃电导/栅压 · "
               "`mvm_datapath` 用 `G=g_base+s·W` **解析**算出 · `layout` 的权重栅只是**对外端口**）"
               "⇒ 新增 `weight_prog`（第 20 模块 · 纯 numpy）：**写-校验**动力学 + **五个闭式 golden** —— "
               "电平步长 `1/(2^k−1)` · 轨迹 `e0(1−α)^k` · 脉冲数 `ceil(ln(tol/e0)/ln(1−α))`=**13** · "
               "🔴 **写入噪声地板 `σ_p/√(α(2−α))` = 0.7001%**（闭式 ⟷ 4000-trial MC 0.6992%，"
               "**rel 0.13%**）⇒ **单脉冲噪声是硬地板，写-校验最多抬升 1/√(α(2−α)) 倍；"
               "`tol < σ_∞` 时期望上不可达**（⇒ 要提精度须降 σ_p，**不是加脉冲数**）· "
               "漂移 `(t/t0)^(−ν)` 与**重校准间隔闭式** `t0(1−β)^(−1/ν)`（β=5% ⇒ **2.79 s**）；"
               "另有 **良率 `(1−p)^N`**（64 单元 1e-3 ⇒ **0.9380**）· **差分对** · "
               "**矩阵感知端到端**（接 E8 `mvm_output`，σ ⟷ 严格式 **rel 0.31%**）· "
               "**接 E15 误差预算链**（残差=**RANDOM** / 电平=**BOUNDED**）。"
               "🔴 **实测**：8×8 有效精度 **4.6223 → 4.5706 位（模拟写入）→ 4.2445 位（MLC 6 位，"
               "−0.378 位）**；电平敏感性 4/6/8/10/12 bit ⇒ 3.52/4.24/4.48/4.55/**4.57** 位"
               "（**≥8 位后饱和**）；🔴 **5% 预算可及规模 12 → 11 → 6 位「无解」**"
               "（电平项 **N 无关**、不被 1/√N 平均）；"
               "🔴 **卡位只影响尾部**（p=1e-3 时 max 1.07%→**22.83%**、mean 0.47%→1.53%、"
               "良率 **95.31%**）。🔴 **保护性约束**：`include_programming` **默认 False** ⇒ "
               "**E15 已发布数字逐位不变**（门禁 B12 + 探针 C5 专守）。"},
    {"id": "E17", "code": "D-185…D-187",
     "title": "时序 / 时钟预算链（时间维度上的 E15：E15 合成「误差」，E17 合成「时间」）",
     "gate": 28, "seg_probes": 6,
     "result": "E1–E16 把精度（E15）与写入（E16）都建起来了，但**时间**从未被建模 —— 全仓 "
               "`sample_rate` / `clock` / `latency` / `timing_budget` / `throughput` / "
               "`per_sample` / `settling_time` **零命中**，且 `PERIPHERY_PROCESS` 的键全为 "
               "`['a_gain','r_out_open_ohm','vdd_v','vfs_v']`（**一个时间参数都没有**）"
               "⇒ E14 行驱动是**无限带宽宏模型**、**采样率算不出来**。新增 `timing`（第 21 模块 · "
               "纯标准库 · **只读消费 E7/E14 · 不吃新物理**）："
               "🔴🔴 **第一原理「误差要分类合成，时间要分拓扑相加」** —— E15 按**类型**做 RSS，"
               "而时间阶段**物理串行** ⇒ `serial = Σ t_i` / 流水线稳态 `= max t_i`；"
               "**对时间取 RSS 是错的** ⇒ **E15 的合成律不可平移到 E17**。"
               "五个**闭式 golden**：`t = τ·ln(1/ε)` · `t = τ·(k+1)·ln2`（½LSB@k，"
               "⟷ **E14 实测** `t_to_half_lsb_8bit_s` 逐位一致）· Elmore `r·c·n(n+1)/2`（复用 E7）· "
               "`(n_bits+1)` 拍（⟷ E14 `len(sar_convert.trace)`）· "
               "`t_clk = settle_half_lsb(R_on·C_u·2^n, k)`（CDAC 建立 ⇒ 时钟，复用 E14）。"
               "**五阶段**：行线（Elmore **+** `R_oc·C_row_tot`）· 列线 · 采样保持 · SAR · DAC。"
               "🔴 **关键实测（8×8 / 8 bit）**：每样本 **129.565246 ns ⇒ 7.7181 MSa/s** —— "
               "**SAR 92.135256 ns 占 71.11%** · DAC 31.191620 ns 占 24.07% · 采样保持 6.238325 ns 占 4.81% · "
               "行线 **0.000029 ns** · 列线 0.000013 ns；流水线稳态 92.135256 ns（收益 **0.28889**）。"
               "🔴🔴 **规模 × 时间趋势相反**：N 8→1024 时阵列 `τ_row` 跨 **12556.5×**（∝N²）"
               "而**每样本耗时只跨 1.00469×** ⇒ **规模墙是「精度墙」（E15：IR drop ∝N²、"
               "5% 预算只到 N≤12）不是「速度墙」**；阵列 τ 达 1 ns 需 **N≈4238**"
               "（解析 4245.8 ⟷ 二分 4238）⇒ **在可达规模内阵列 RC 永不是时间瓶颈**。"
               "🔴 **主导项随位数交叉**：4/6 bit ⇒ **DAC 建立**（76.8% / 56.4%），"
               "8/10/12 bit ⇒ **SAR**（71.1% / 92.3% / 98.3%）—— 因 **SAR ∝ (bits+1)²** 而 "
               "**DAC ∝ (bits+1)** ⇒ **必然交叉**。**时钟预算**：固定开销 37.43 ns；目标 160 ns ⇒ "
               "`t_clk_max` 13.6189 ns（**代回残差 0.00e+00**）。**R_oc 敏感性**：0→100 Ω 时行线阶段涨 50×，"
               "而每样本耗时只涨 **7.7e-6 %** ⇒ **R_oc 伤精度、不伤速度**。"
               "🔴 **保护性约束**：**只读消费** E7/E14 · **不给** `PERIPHERY_PROCESS` 加时间键 ⇒ "
               "**E15/E16 已发布数字逐位不变**（门禁 B15/B16 守着；探针 C6 守「注入已报 TOPS 必红」）。"},
    {"id": "E18", "code": "D-189…D-191",
     "title": "列侧共享与架构权衡（补上全仓此前完全空白的「面积」维度）",
     "gate": 31, "seg_probes": 6,
     "result": "E1–E17 的列侧读出（TIA + ADC）**始终是「每列一份」**（`crossbar_mvm` 每列一个理想运放 · "
               "`mvm_datapath` 每列一个 ADC · `converter.sar_convert` 是单通道），"
               "**全仓 `share`/`mux`/`multiplex`/`复用器`/`时分` 在 `lda_l2/ecore/` 零命中**，"
               "面积维度只有 `array_footprint`（阵列本体）⇒ 列侧读出**完全不进面积**。"
               "新增 `col_share`（第 22 模块 · 纯标准库 · **只读消费 E14/E17 · 不吃新物理**）："
               "🔴🔴 **第一原理「面积-时间乘积守恒」** —— `A_total × 每列周期 = N·A_u·T_conv`"
               "（**与 K 无关**）⇒ 共享只沿「等面积-时间双曲线」移动，不改乘积"
               "（跨 6 个 K 的散布 **0.00e+00**）。"
               "🔴🔴 **第二原理「保吞吐共享 ⇒ 面积 ∝1/K²」** —— 缩 `T_conv` 的唯一物理路径是降 `C_tot`"
               "（`T_conv ∝ C_tot·(bits+1)²` · E17 G-5）⇒ **双项闭式** "
               "`A(K) = N·C_tot(1)/(ρK²) + N·A_logic/K`（电容项 ∝1/K² · 逻辑项 ∝1/K）；"
               "**拐点 K\\* = C_tot(1)/(ρ·A_logic) = 160** ⇒ 三条斜率分开判：不保吞吐 **−1.000000** · "
               "保吞吐仅电容项 **−2.000000** · 双项混合 **−1.952465 ∈ (−2,−1)**。"
               "🔴 **第三腿（诚实拒绝造腿）**：`σ = √(kT/C_tot)` 是物理律，但 8 bit / 1 pF / `k_σ=3` ⇒ "
               "位数上限 **16.338559**，跌到 8 位需共享度 **K ≈ 1.0479×10⁵** ≫ 可达 ⇒ "
               "**共享的真实代价是「吞吐」不是「精度」**（不硬造精度腿）。"
               "🔴 **量级事实**：单列 CDAC 电容面积 **128 000 µm²** vs 64×64 阵列本体 "
               "**23 301.96 µm²** ⇒ **读出 = 阵列的 354.92 倍**；全并行 N=64 = **8.2704 mm²** → "
               "全串行 **0.1308 mm²**（**63.229×**）；**保吞吐 k4 再省 3.782609×**（且速率 == 全并行）；"
               "**推荐**（N=64 / 8 bit / 10 MSa/s）共享度**饱和到列数**（1 个 ADC · `C_tot` 4 pF）⇒ "
               "**30 000 µm² = 1/275.68**。🔴 **接 E17 的 0.289 锚** —— **复制**方向 "
               "`A×周期` **严格常数**（散布 0.0）⇒ **提吞吐（复制）与省面积（共享）是同一条双曲线两端**。"
               "🔴 **保护性约束**：**只读消费** E14/E17 · `keep_throughput` **默认 False** ⇒ "
               "**E15/E16/E17 已发布数字逐位不变**（模块门禁 B18/B19 守着）。"},
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
    {"title": "把 14 段串成一个答案：8×8 只有 4.62 位 · 主导项在 N≈16 换手（E15）",
     "detail": "E1–E14 每段都给**单点误差**却**从未合成过**，且口径互不相同（相对 % / σ / LSB）、"
               "性质未分类（系统性 / 随机 / 有界）—— 所以「这颗阵列几个有效位」**此前无人能答**。"
               "E15 把四类误差接成一条链后：**8×8 全链最坏 4.0601% ⇒ 有效精度只有 4.622 位**"
               "（典型口径 5.256 位）；规模上去后 **N=256 只剩 0.248 位**。"
               "🔴 最有价值的是**主导项交叉点**：N≤8 由**器件失配**主导（σ∝1/√N ⇒ 小 N 更差），"
               "N≥16 由 **IR drop** 主导（∝N² 爆炸）⇒ 设计指令变得明确：**小阵列先治失配"
               "（器件面积 / 校准）、大阵列先治 IR drop（驱动架构 / 金属）**。"
               "🔴 顺带推翻了一个乐观结论：E9 的「5% 预算 ⇒ N≤18」**只算了 IR drop**；"
               "加入失配 + 行驱动 + 转换器后，同样 5% 只能到 **N≤12**（严格 33%）。"
               "**单看任何一段都得不出这个数** —— 这就是「串成一条链」的价值。"},
    {"title": "权重编程通路：8×8 有效精度再降 0.378 位 · 5% 预算可及规模 12 → 11 → 「无解」",
     "detail": "E16 补上「写入动作」这一此前完全不存在的一环后：**8×8 有效精度从 4.6223 位"
               "（E15 四类误差）降到 4.2445 位（MLC 6 位，−0.378 位）**。"
               "🔴 最有价值的两条：① **写入噪声有一个由「单脉冲噪声 σ_p」决定的硬地板** "
               "`σ_∞ = σ_p/√(α(2−α))` —— 加脉冲数**买不到**精度，必须降 σ_p；"
               "② **电平量化是 N 无关的常量**（有界项不被 1/√N 平均）⇒ 6 位 MLC 下 5% 误差预算的"
               "可及规模从 **N≤12 塌到「无解」**（连 2×2 都不满足）。"
               "🔴 还有一条反直觉的：**低电导单元的「大相对误差」在求和里并不放大** —— "
               "电平等间距 ⇒ 量化误差**绝对值同为半步长** ⇒ 输出界 = `half_step / **平均电导**`"
               "（初版误用最小电导 ⇒ 界放大 ~3×、结论整个带偏）。"},
    {"title": "时序：这套架构是「精度墙」不是「速度墙」 · 8×8 每样本 129.565 ns ⇒ 7.7181 MSa/s",
     "detail": "把 E1–E16 里**零散的时间量**（E7 的 Elmore τ · E14 的采样保持 τ / SAR 逐位试判）"
               "串成一条**节拍链**后得到：**8×8 / 8 bit 每样本 129.565246 ns ⇒ 7.7181 MSa/s**，"
               "其中 **SAR 独占 71.11%**（92.135 ns，`t_clk` 10.237 ns × 9 拍）、DAC 建立 24.07%、"
               "采样保持 4.81%，而**行线 + 列线合计不足 0.001%（fs 量级）**。"
               "🔴 **本段最可讲的结论**：**N 从 8 涨到 1024，阵列 `τ_row` 跨 12556.5×（∝N²），"
               "而每样本耗时只跨 1.00469×** ⇒ **时间几乎完全不随规模恶化** —— "
               "**规模墙是「精度墙」（E15：IR drop ∝N²、5% 预算只到 N≤12）不是「速度墙」**。"
               "阵列 τ 要到 **N≈4238** 才与 1 ns 可比，**远超可达规模** ⇒ 阵列 RC 永不是时间瓶颈。"
               "🔴 第二条：**主导项随位数交叉**（≤6 bit ⇒ DAC 建立主导；≥8 bit ⇒ SAR 主导）—— "
               "因为 **SAR ∝ (bits+1)²**（拍数 × 每拍建立）而 **DAC ∝ (bits+1)** ⇒ 必然交叉；"
               "⇒ **低位数该优化 DAC，高位数只能优化 SAR**。"
               "🔴 第三条：**流水线收益仅 0.28889**（最慢级独占预算）⇒ "
               "**提吞吐必须并行复制瓶颈级，而不是加深流水线**（面积代价 ⇒ 接 E18 架构权衡）。"},
    {"title": "面积瓶颈不在阵列、在**列侧读出** · 共享有两条闭式律（E18）",
     "detail": "E1–E17 的列侧读出（TIA + ADC）**始终是「每列一份」**，且**面积维度从未建模**。"
               "补上后得到一条反直觉的量级事实：在二进制 CDAC 口径下，**单列读出（128 000 µm²）"
               "是整片 64×64 阵列本体（23 301.96 µm²）的 354.92 倍**，全并行 N=64 的列侧读出高达 "
               "**8.2704 mm²** ⇒ **模拟 CIM 的面积瓶颈不在阵列，而在列侧读出** —— 这才是"
               "「共享」成为必答题的原因。两条闭式律："
               "① 🔴🔴 **面积-时间乘积守恒** —— `A_total × 每列周期 = N·A_u·T_conv`（**与 K 无关**）"
               "⇒ 共享只沿「等面积-时间双曲线」移动，**不改变乘积**；"
               "② 🔴🔴 **保吞吐共享 ⇒ 面积 ∝1/K²** —— 要同时保住吞吐就必须缩短 `T_conv`，"
               "而缩 `T_conv` 的唯一物理路径是降 `C_tot`（`T_conv ∝ C_tot·(bits+1)²`）⇒ 面积是"
               "**双项**的：`N·C_tot(1)/(ρK²) + N·A_logic/K`（电容项 ∝1/K²、逻辑项 ∝1/K），"
               "**拐点 `K* = 160`**。实测：全并行 **8.2704 mm² → 全串行 0.1308 mm²（63.229×）**；"
               "**保吞吐 k4 比不保吞吐 k4 再省 3.782609×**（且每列速率 == 全并行）；"
               "推荐方案（N=64 / 8 bit / 10 MSa/s）**30 000 µm² = 1/275.68**。"
               "🔴 与 E17 的 **0.28889** 锚合起来看：**提吞吐（并行复制瓶颈级）与省面积（共享）"
               "是同一条 `A×周期 = 常数` 双曲线的两端** —— 两者不是两条独立的设计维度，"
               "而是**同一个守恒量的两个方向**。"},
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
    {"id": "G-O", "title": "误差预算为**静态口径** · 合成律是**保守工程近似**（E15 新增能力的内在边界）",
     "detail": "① 🔴 `output_effective_bits` = `log2(100/最坏相对误差[%])` 是**本项目自定义量**，"
               "**不是 IEEE ENOB**（ENOB 含噪声 + 谐波 + 直流非线性、由 FFT 谱定义）—— 不得张冠李戴。"
               "② 只覆盖静态：给定权重与输入的静态精度，不含时序 / 动态 / 建立时间 / 采样率 / "
               "时钟抖动 / 热梯度空间分布 / 老化漂移 / 电源噪声。"
               "③ 合成律 `worst = Σsys + kσ + Σbnd` 是**保守工程口径**，**不是严格概率保证**"
               "（严格需分布假设与卷积）；`typical` 的 `Σb/√3` 假设误差均匀分布。"
               "④ 误差项参数均为公开典型量级占位（**非 PDK**）；器件侧仍 **DD 框架 + 常数迁移率**。"
               "⑤ **保护性约束**：本段**只读消费** E7/E8/E9/E14 接口，**不改**任何既有默认值"
               "（门禁 G8 逐位守住）⇒ 卡内数字与既有段**不冲突**。"},
    {"id": "G-P", "title": "权重编程是**行为级模型** · 参数为公开量级占位（E16 新增能力的内在边界）",
     "detail": "写-校验建模为「**比例修正 + 加性噪声**」的**现象学模型**，**不含**：真实 RRAM 的"
               "细丝动力学 / 非线性 / 脉冲宽度依赖 / 温度加速 / 器件级物理随机性谱；"
               "**无 endurance / retention 联合退化**；**只覆盖静态**（不含编程时间与能耗）。"
               "参数（α=0.30 / σ_p=0.5% / tol=1% / ν=0.05 / p=1e-3）均为**公开典型量级占位"
               "（非 PDK · 无实测锚）** ⇒ **结论随参数变**，报告必须携带参数。"
               "补真实器件行为需**器件级 RRAM/闪存物理模型**（属器件层，非本段范围）。"},
    {"id": "G-Q", "title": "🔴 漂移结论**条件于 ν** · 共模漂移可校准 ⇒ 不进预算（E16 的诚实要点）",
     "detail": "① 🔴 **可及规模与重校准间隔都是参数推出的**：ν=0.05 时 5% 漂移预算 ⇒ "
               "`t_max ≈ 2.79 s` —— 这是**参数推论而非普适断言**，换 ν 换数；"
               "正确读法是「**RRAM 类模拟 CIM 必须频繁重刷**」。"
               "② 🔴 **共模漂移（所有单元同向）可被单次全局增益校准消除** ⇒ **不进误差预算**；"
               "进预算的只有 **ν 的单元间离散**（校准不掉）。"
               "⇒ **通则：一个能被单次校准消掉的项，不是精度上限**"
               "（与 E8「列系统项可由 L1 校准、逐单元失配才需 L2」同型）。"
               "③ **卡位（stuck）是良率问题、不是均值精度问题** ⇒ 预算默认不含卡位"
               "（另设 `include_stuck`）—— 实测 p=1e-3 时 mean 仅 0.47%→1.53%，"
               "但 max 1.07%→**22.83%**、良率降到 **95.31%**。"},
    {"id": "G-R", "title": "时序为**宏模型级**估算 · 只覆盖静态 · **不做功耗**（E17 新增能力的内在边界）",
     "detail": "五阶段时间中：行驱动仍是 **VCVS + 开环输出电阻宏模型**（**无真实 GBW / 摆率**）；"
               "**比较器延时 / 时钟树 / 时钟抖动未建模**；R-2R 输出节点电容 `r2r_node_cap_f` 是**显式占位**"
               "（E14 未建 R-2R 动态）⇒ **DAC 阶段尤其参数敏感**（报告里标 `param_sensitive=True`）。"
               "**只覆盖静态 + 一阶 RC 建立**：不含摆率限制 / 时钟偏斜与抖动 / 供电噪声 / 温度梯度 / "
               "老化（接 E16 漂移）/ 工艺角；阵列 RC 沿用 E7/E9 一阶口径（**忽略列线电阻对行线的耦合**）。"
               "🔴 **不做能量与功耗估算** ⇒ 因而 **绝不报 TOPS / TOPS-W / fJ/op**"
               "（那是「吞吐 × 能效」的联合指标，本段既无功耗模型、也无实测硅）；"
               "**只报「每样本耗时（ns）」与相对量**。参数（`c_unit_f` / `r_unit_ohm` / "
               "`r2r_node_cap_f` / `rs` / `cs`）为**公开典型量级占位（非 PDK · 无实测锚）** "
               "⇒ **结论随参数变**，报告须携带参数。**保护性约束**：只读消费 E7/E14、"
               "**不给** `PERIPHERY_PROCESS` 加时间键（E17 的时间参数只进**自己的** `TIMING_PROCESS`）"
               "⇒ **E15/E16 已发布数字逐位不变**（门禁 B15/B16 守着）。"},
    {"id": "G-S", "title": "面积为**宏模型占位** · 只覆盖静态 · 共享的动态代价未建模（E18 新增能力的内在边界）",
     "detail": "① 🔴 **面积为宏模型占位**：ρ=2 fF/µm²（MIM）· A_logic=800 µm² · A_tia=400 µm² · "
               "开关 25 µm² 均为**公开典型量级（非 PDK · 无实测锚）** ⇒ **结论随参数变**，"
               "报告须携带参数；真实芯片用**分段 CDAC / 更小 `C_u` / 采样电容共享** ⇒ 面积远小于此。"
               "② **只覆盖静态**：不含动态功耗 / 时钟树与偏斜 / 供电网络（PDN）/ 驱动器面积 / IO pad；"
               "**共享的动态代价（多路开关电荷注入 / 串扰 / 采样孔径抖动 / 复用开关的建立时间）未建模**"
               "（本段只做**静态面积与周期**估算）。"
               "③ 🔴 **不做功耗估算 ⇒ 不谈能效**：**绝不报 TOPS / TOPS-W / fJ/op**；"
               "只报「面积（µm²/mm²）/ 每列采样率（Sa/s）/ 相对倍数」。"
               "④ 🔴 **不宣称共享受精度限制**：`σ = √(kT/C_tot)` 是物理律，但 8 bit / 1 pF / `k_σ=3` 时"
               "位数上限 **16.338559**，跌到 8 位需共享度 **K ≈ 1.0479×10⁵**"
               "（远超可达共享度，其上界为列数 N）⇒ **共享的真实代价是「吞吐」不是「精度」**；"
               "硬造一个精度腿是错的。"
               "⑤ **保护性约束**：本段**只读消费** E14/E17，**不改**任何既有默认值；"
               "`keep_throughput` **默认 False** ⇒ **E15/E16/E17 已发布数字逐位不变**。"},
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


def lsb_to_rel_pct(bits: int) -> float:
    """**口径桥闭式**：1 LSB 相对满量程的百分比 = `100 / 2**bits`（8 bit ⇒ 0.390625%）。"""
    return 100.0 / float(1 << int(bits))


def output_effective_bits(rel_pct: float) -> float:
    """**输出有效精度位数** = `log2(100 / rel_pct)`。

    🔴 **本项目自定义量，不是 IEEE ENOB**（ENOB 含噪声 + 谐波 + 直流非线性、由 FFT 谱定义）。
    自洽锚：`output_effective_bits(lsb_to_rel_pct(k)) == k`。
    """
    return math.log2(100.0 / float(rel_pct))


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
                 "真 DAC / ADC / 行驱动外设（系统链） + 端到端误差预算链 + "
                 "权重编程通路（写-校验 / 噪声地板 / 接误差预算） + "
                 "时序 / 时钟预算链（五阶段节拍 / 时间按拓扑合成 / 时钟反解） + "
                 "列侧共享与架构权衡（面积-时间乘积守恒 / 保吞吐 ∝1/K² / 架构族对照）**全链路验证",
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
            "modules": 22,               # ecore 包内模块数（含能力清单自身 · 不含 __init__.py）
            "capability_modules": 21,    # 登记进 ECORE_CAPABILITY_MANIFEST 的能力模块数
            "entrypoints": 20,           # 常驻门禁数（E1–E9 八道 + 能力守护 + 案例卡 + 红线 +
                                         #   E11 两道 + E12…E18 七道）
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
        "device_budget": BUDGET_FACTS,
        "device_weight_prog": WEIGHT_PROG_FACTS,
        "device_timing": TIMING_FACTS,
        "device_col_share": COL_SHARE_FACTS,
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

    # ⑩ 案例卡组装：17 里程碑 / 18 结论 / 19 缺口 / 判据合计 407（含 88 探针）
    card = case_card(repo_root="__nonexistent_root__")
    chk("⑩ 案例卡组装：17 里程碑 / 18 结论 / **19 缺口** / 门禁判据合计 407（含 88 探针）",
        len(card["milestones"]) == 17 and len(card["findings"]) == 18
        and card["gaps_total"] == 19 and card["span"]["gate_checks"] == 407
        and card["span"]["probe_checks"] == 88)

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
    chk("⑰ 里程碑完整：17 段 · 每段含 gate 数 + 结果文本",
        len(MILESTONES) == 17
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

    # ㉚ E15 误差预算面登记齐全（防「加了能力忘了卡」）
    dbf = card["device_budget"]
    chk("㉚ E15 误差预算面登记齐全（六项误差 · worst/bits · 精度vsN 六点 · 交叉点 · 全链上界）",
        len(dbf["budget_8x8"]["terms"]) == 6
        and abs(dbf["budget_8x8"]["worst_pct"] - 4.06012) < 0.001
        and abs(dbf["budget_8x8"]["worst_bits"] - 4.622) < 0.01
        and len(dbf["scale_curve"]) == 6
        and dbf["crossover"]["dom_lo"] == "device_mismatch"
        and dbf["crossover"]["dom_hi"] == "ir_drop"
        and dbf["scale_ceiling"]["full_chain_n_max"] < dbf["scale_ceiling"]["ir_drop_only_n_max"])

    # ㉛ 🔴 诚实（E15 · 抬高方向）：能力到手后最易滑成「这就是 ENOB / 已含动态」
    #     🔴 两条判据设计纪律（本轮实测踩到）：
    #       ① **不能要求跨 Markdown 加粗的连续子串** —— 文本里的 `只覆盖**静态**` 会被 `**` 打断，
    #          使 `"只覆盖静态" in blob` 恒假（假红）；
    #       ② **禁词必须精确** —— `"含时序"` 会**误伤** `"不含时序"`（否定词窗口问题，E12 血案同族）
    #          ⇒ 禁词只取肯定的表述（`已含时序` / `包含时序`），并在文本侧去掉跨词加粗。
    #       ③ 🔴 **多来源拼接会稀释判据**：若把 `device_budget` 与 `gaps` 拼成一个大 blob 再断言，
    #          任一来源被破坏都可能被另一来源掩盖（实测：改坏 `device_budget` 后，blob 里仍留有
    #          G-O 的「不是 IEEE ENOB」⇒ 判据**照样绿** ⇒ 探针假绿）。
    #          ⇒ **必须按来源分别断言**（下面两个来源各查一次）。
    _bdb = str(card["device_budget"])
    _bgp = " ".join(g["detail"] for g in card["gaps"])
    chk("㉛ 🔴 诚实（E15）：**两个来源各自**显式声明非 IEEE ENOB + 只覆盖静态；"
        "不得自称 ENOB / 已含动态 / 已含时序",
        ("不是 IEEE ENOB" in _bdb) and ("只覆盖静态" in _bdb)
        and ("不是 IEEE ENOB" in _bgp)
        and all(k not in (_bdb + _bgp) for k in ("这就是 ENOB", "等于 ENOB",
                                                 "已含动态", "已含时序", "包含时序")))

    # ㉜ E16 权重编程面登记齐全（防「加了能力忘了卡」）
    dwp = card["device_weight_prog"]
    chk("㉜ E16 权重编程面登记齐全（噪声地板闭式⟷MC · 预算四档 · 位数敏感性五点 · 上界收缩 · "
        "漂移/重校准 · 良率/卡位 · 端到端 · 项分类）",
        abs(dwp["noise_floor"]["sigma_cell_pct"] - 0.70014) < 0.001
        and abs(dwp["noise_floor"]["mc_pct"] - 0.69922) < 0.005
        and dwp["noise_floor"]["iters_to_tol"] == 13
        and len(dwp["budget"]) >= 5
        and abs(dwp["budget"]["mlc6"]["worst_pct"] - 5.27562) < 0.001
        and abs(dwp["budget"]["mlc6"]["bits"] - 4.2445) < 0.01
        and len(dwp["level_sensitivity"]) >= 5
        and dwp["scale_ceiling"]["analog_n_max"] < dwp["scale_ceiling"]["default_n_max"]
        and dwp["scale_ceiling"]["mlc6_n_max"] < dwp["scale_ceiling"]["analog_n_max"]
        and len(dwp["drift"]["curve"]) == 5
        and len(dwp["drift"]["recalibration_s"]) == 3
        and dwp["categories"]["residual"] == "random"
        and dwp["categories"]["level"] == "bounded")

    # ㉝ 🔴 诚实（E16 · 双向）：
    #     **抬高方向** —— 能力到手后最易滑成「参数已标定 PDK / 已报 TOPS /
    #        把共模漂移当成精度上限」（共模可被单次增益校准消除 ⇒ 不该进预算）；
    #     **贬低方向** —— E16 前的「权重直接灌入、无写入模型」口径必须显式标注已闭合（G-P/G-Q）。
    #     🔴 判据纪律（E15 血案）：**按来源分别断言** —— 多来源拼接会稀释判据（探针会假绿）。
    _dwp = str(card["device_weight_prog"])
    _bgp2 = " ".join(g["detail"] for g in card["gaps"])
    chk("㉝ 🔴 诚实（E16）：两个来源各自显式声明**非 PDK** + **不报 TOPS** + "
        "**共模漂移可校准 ⇒ 不进预算**；且漂移结论**条件于 ν**；"
        "不得自称已标定 PDK / 已含 TOPS / 把共模漂移当精度上限",
        ("非 PDK" in _dwp) and ("TOPS" in _dwp)
        and ("共模" in _dwp) and ("不进预算" in _dwp) and ("条件于" in _dwp)
        and ("非 PDK" in _bgp2)
        and (("不进预算" in _bgp2) or ("不进误差预算" in _bgp2))
        and all(k not in (_dwp + _bgp2) for k in ("已标定 PDK", "已含 TOPS",
                                                 "共模漂移是精度上限")))

    # ㉞ E17 时序面登记齐全（防「加了能力忘了卡」）
    dtm = card["device_timing"]
    chk("㉞ E17 时序面登记齐全（五阶段 · 总量/主导项/速率 · 时间合成律双口径 + RSS 反例 · "
        "规模×时间 · 交叉点 · 位数交叉 · 时钟反解 · R_oc 敏感性 · 保护性 · 闭式五项）",
        len(dtm["stages"]) == 5
        and abs(dtm["totals"]["serial_ns"] - 129.565246) < 1e-4
        and abs(dtm["totals"]["pipelined_period_ns"] - 92.135256) < 1e-4
        and abs(dtm["totals"]["pipeline_gain_frac"] - 0.28889) < 1e-4
        and abs(dtm["totals"]["max_sample_rate_msa"] - 7.7181) < 1e-3
        and dtm["totals"]["dominant"] == "sar_convert"
        and abs(dtm["synthesis_law"]["demo"]["serial_ns"] - 21.0) < 1e-9
        and abs(dtm["synthesis_law"]["demo"]["rss_ns"] - 13.38) < 0.01
        and dtm["scale_vs_time"]["tau_row_span_x"] > 10000
        and dtm["scale_vs_time"]["serial_span_x"] < 1.01
        and abs(dtm["crossover"]["ns"] - 4238) < 2
        and len(dtm["bits_cross"]["points"]) == 5
        and dtm["clock_budget"]["back_calc_residual_s"] == 0.0
        and len(dtm["closed_form"]) == 5
        and dtm["protection"]["e15_worst_pct"] == 4.06012)

    # ㉟ 🔴 诚实（E17 · 双向）：
    #     **抬高方向** —— 时间能力到手后最易滑成「已报 TOPS / 已含功耗 / 已含时钟树抖动」；
    #     **贬低方向** —— E17 前的「全仓时间零覆盖 / 行驱动无限带宽宏模型」口径必须显式标注已闭合。
    #     🔴 判据纪律（E15 血案）：**按来源分别断言** —— 多来源拼接会稀释判据（探针会假绿）。
    _dtm = str(card["device_timing"])
    _bgp3 = " ".join(g["detail"] for g in card["gaps"])
    _forbid_t = ("已报 TOPS", "已含功耗", "已含时钟树抖动", "已含摆率模型", "已完成功耗估算")
    chk("㉟ 🔴 诚实（E17）：两个来源各自显式声明**只报每样本耗时** + **不报 TOPS** + **非 PDK** + "
        "**不做功耗估算**；且必须给出「宏模型级」与「只覆盖静态」两条内在边界；"
        "不得自称已报 TOPS / 已含功耗 / 已含时钟树抖动",
        ("只报「每样本耗时（ns）」" in _dtm) and ("不报 TOPS" in _dtm)
        and ("非 PDK" in _dtm) and ("不做能量与功耗估算" in _dtm)
        and ("宏模型" in _dtm) and ("只覆盖静态" in _dtm)
        and ("不报 TOPS" in _bgp3) and ("不做能量与功耗估算" in _bgp3)
        and ("宏模型" in _bgp3) and ("只覆盖静态" in _bgp3)
        and all(k not in (_dtm + _bgp3) for k in _forbid_t))

    # ㊱ E18 列侧共享面登记齐全（防「加了能力忘了卡」）
    dcs = card["device_col_share"]
    chk("㊱ E18 列侧共享面登记齐全（量级事实 · 第一原理守恒 · 第二原理三斜率 + K* · kT/C 地板 · "
        "架构族五条 · 推荐 · 复制-共享 · 闭式七项 · 保护性）",
        abs(dcs["magnitude"]["unit_cap_area_um2"] - 128000.0) < 1e-6
        and abs(dcs["magnitude"]["readout_over_array_ratio"] - 354.923) < 1e-3
        and abs(dcs["magnitude"]["full_parallel_mm2"] - 8.2704) < 1e-9
        and abs(dcs["magnitude"]["arch_ratio"] - 63.229) < 1e-3
        and abs(dcs["first_principle"]["spread"]) < 1e-12
        and abs(dcs["second_principle"]["slope_plain"] + 1.0) < 1e-9
        and abs(dcs["second_principle"]["slope_keep_cap"] + 2.0) < 1e-9
        and -2.0 < dcs["second_principle"]["slope_keep_total"] < -1.0
        and abs(dcs["k_star"]["k_star"] - 160.0) < 1e-9
        and abs(dcs["ktc"]["bits_ceiling_at_256pF"] - 16.338559) < 1e-6
        and dcs["ktc"]["k_share_crit_8bit"] > 1.0e4
        and len(dcs["architectures"]["rows"]) == 5
        and dcs["recommend"]["k_best"] == 64 and dcs["recommend"]["n_adc_units"] == 1
        and abs(dcs["replication_vs_sharing"]["replicated_spread"]) < 1e-12
        and len(dcs["closed_form"]) == 7
        and dcs["protection"]["keep_throughput_default_off"] is True)

    # ㊲ 🔴 诚实（E18 · 双向）：
    #     **抬高方向** —— 列侧共享能力到手后最易滑成「面积已实测 / 已报 TOPS / 已含功耗 /
    #       已含复用开关建模（其实未建模）」；
    #     **贬低方向** —— E18 前的「列侧每列一份 / 面积维度零覆盖」口径必须显式标注为已补上；
    #     🔴 且必须显式**拒绝硬造精度腿**（kT/C 在可达共享度内不是约束 ⇒ 不得把共享说成精度瓶颈）。
    #     🔴 判据纪律（E15 血案）：**按来源分别断言** —— 多来源拼接会稀释判据（探针会假绿）。
    _dcs = str(card["device_col_share"])
    _bgp4 = " ".join(g["detail"] for g in card["gaps"])
    _forbid_c = ("已报 TOPS", "已含功耗", "已完成功耗估算", "面积已实测",
                 "已含动态功耗", "已含复用开关建模")
    chk("㊲ 🔴 诚实（E18 · 双向）：两个来源各自显式声明**不报 TOPS** + **非 PDK** + "
        "**不做功耗估算** + **宏模型占位**；🔴 且必须显式写明**拒绝硬造精度腿**；"
        "不得自称已报 TOPS / 已含功耗 / 面积已实测 / 已含复用开关建模",
        ("不报 TOPS" in _dcs) and ("非 PDK" in _dcs) and ("不做功耗估算" in _dcs)
        and ("宏模型占位" in _dcs) and ("不硬造精度腿" in _dcs)
        and ("不报 TOPS" in _bgp4) and ("不做功耗估算" in _bgp4)
        and ("不宣称共享受精度限制" in _bgp4)
        and ("硬造一个精度腿是错的" in _bgp4)
        and all(k not in (_dcs + _bgp4) for k in _forbid_c))

    ok_all = all(res.values())
    if verbose:
        for m in msgs:
            print("  " + m)
    return ok_all


if __name__ == "__main__":
    print("电子计算芯片案例卡自检：", "ALL PASS" if run_selfchecks(verbose=True) else "FAIL")
