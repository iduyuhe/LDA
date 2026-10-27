# -*- coding: utf-8 -*-
"""LDA · 电子计算征程 E5 · ecore 能力清单（平台能力硬化的**单一真源**）（D-154）。

============================================================================
设计定位（吃狗粮收尾：把征程逼出的平台短板**固化为平台常驻、可发现、被守护的能力**）
----------------------------------------------------------------------------
E 征程逐段逼出的平台能力（此前平台完全缺失）在此**机器可读**地登记：
  · E1 → 晶体管级长沟道 MOSFET 模型 + MNA 电路仿真器（DC/瞬态/AC） + 最小模拟计算单元
  · E2 → 参数化 N×M 模拟 MVM 交叉阵列 + 晶体管级 OTA 表征
  · E3 → MVM 数据通路（DAC→交叉阵列→ADC、多层/分块）
  · E4 → 规模对标（诚实边界）+ 诚实护栏

🔴 硬化的本质 = **把"能力面"钉成常驻门禁**（`run_ecore_capability_guard_smoke.py`）：
  · 正向：清单每条 ⇒ 模块可导入 + 关键符号齐备；
  · **反向完备**：`lda_l2/ecore/` 下每个模块 ⇒ 必须在清单中登记（防"隐身"模块悄悄进盲区）；
  · 披露一致：`ECORE_DISCLOSURE` 的 e1~e4 scope 与清单对应；
  · 诚实边界：能力面不得含 TOPS/TOPS-W 等 fabricated 指标（`scale_bench.honest_boundary_ok`）。

主权纪律（全平台同源）：C 级自主（纯 numpy）；LLM 不进判决路径；
**本包主动限定在电路级**（平台红线 = **分层口径**：器件级 T1 内核已解锁 · T2 工艺真值/流片永久锁）。
"""
from __future__ import annotations

import importlib
import os

# 非"能力"模块（包入口 + 本清单自身）不参与反向完备
ECORE_EXCLUDE_MODULES = {"__init__", "capability_manifest"}

# ---------------------------------------------------------------------------
# 能力清单（单一真源）：capability / module / symbols / introduced_by / guard
# ---------------------------------------------------------------------------
ECORE_CAPABILITY_MANIFEST = [
    {
        "capability": "晶体管级长沟道 NMOS 模型（平方律 三区 + gm/gds 解析）",
        "module": "lda_l2.ecore.mosfet",
        "symbols": ["NmosParams", "id_gm_gds", "id_saturation_closed", "vdsat",
                    "mosfet_self_check", "MOSFET_DISCLOSURE"],
        "introduced_by": "D-150 (E1)", "guard": "run_ecore_e1_smoke.py",
    },
    {
        "capability": "MNA 电路仿真器（DC 牛顿 / 瞬态后向欧拉 / AC 复数）",
        "module": "lda_l2.ecore.mna",
        "symbols": ["Circuit"],
        "introduced_by": "D-150 (E1)", "guard": "run_ecore_e1_smoke.py",
    },
    {
        "capability": "最小模拟计算单元（反相求和 MAC + NMOS 饱和偏置）",
        "module": "lda_l2.ecore.analog_mvm",
        "symbols": ["inverting_summer", "inverting_summer_golden",
                    "mosfet_saturation_bias", "mosfet_saturation_golden"],
        "introduced_by": "D-150 (E1)", "guard": "run_ecore_e1_smoke.py",
    },
    {
        "capability": "参数化 N×M 模拟 MVM 交叉阵列（ideal/transistor）+ 晶体管级 OTA 表征",
        "module": "lda_l2.ecore.crossbar_mvm",
        "symbols": ["CrossbarMVM", "build_ota_circuit", "ota_open_loop_gain",
                    "CROSSBAR_DISCLOSURE"],
        "introduced_by": "D-151 (E2)", "guard": "run_ecore_e2_smoke.py",
    },
    {
        "capability": "MVM 数据通路（DAC→交叉阵列→ADC、多层级联、分块、输出定标）",
        "module": "lda_l2.ecore.mvm_datapath",
        "symbols": ["AnalogMvmUnit", "MvmDatapath", "tiled_mvm", "quantize_uniform",
                    "relu", "mvm_datapath_self_check", "MVM_DATAPATH_DISCLOSURE"],
        "introduced_by": "D-152 (E3)", "guard": "run_ecore_e3_smoke.py",
    },
    {
        "capability": "规模对标（诚实边界）+ 诚实护栏 + 公开 landmark 登记",
        "module": "lda_l2.ecore.scale_bench",
        "symbols": ["scale_sweep", "scale_bench_self_check", "honest_comparison",
                    "honest_boundary_ok", "LANDMARKS", "LDA_CAPABILITIES",
                    "NON_CLAIMED", "SCALE_BENCH_DISCLOSURE"],
        "introduced_by": "D-153 (E4)", "guard": "run_ecore_e4_smoke.py",
    },
    {
        "capability": "电子版图层栈（DIFF/POLY/CONT/M1/VIA1/M2）+ 层语义谓词 + 设计规则",
        "module": "lda_l2.ecore.elayers",
        "symbols": ["ELayer", "ELayerStack", "DEFAULT_CMOS_STACK", "get_estack",
                    "ELEC_DESIGN_RULES", "ELEC_DISCLOSURE", "run_selfcheck"],
        "introduced_by": "D-156 (E6)", "guard": "run_ecore_e6_smoke.py",
    },
    {
        "capability": "电子版图与几何签核（1T 交叉阵列 P&R + 几何 DRC + 段感知 LVS + AREF 层次化 GDS）",
        "module": "lda_l2.ecore.layout",
        "symbols": ["crosspoint_cell", "crossbar_array", "array_footprint",
                    "expected_netlist", "extract_wl", "run_edrc", "elvs_signoff",
                    "to_gds", "gds_roundtrip_check", "layout_svg",
                    "EDRC_RULES", "LAYOUT_DISCLOSURE", "run_selfchecks"],
        "introduced_by": "D-156 (E6)", "guard": "run_ecore_e6_smoke.py",
    },
    {
        "capability": "寄生提取与后仿（导线 RC 闭式 + 阵列 R 梯网络 + IR drop / sneak path + Elmore 延迟）",
        "module": "lda_l2.ecore.parasitic",
        "symbols": ["sheet_resistance", "wire_resistance", "cap_per_length",
                    "wire_capacitance", "elmore_delay", "array_parasitics",
                    "ideal_column_currents", "build_network", "solve_network",
                    "ir_drop_report", "sneak_report", "ELEC_PROCESS",
                    "PARASITIC_DISCLOSURE", "run_selfchecks"],
        "introduced_by": "D-157 (E7)", "guard": "run_ecore_e7_smoke.py",
    },
    {
        "capability": "非理想/失配/噪声通道（Pelgrom 失配 + 温度 + 热/闪烁噪声 + 失配 Monte Carlo + 校准层级 L0/L1/L2）",
        "module": "lda_l2.ecore.mismatch",
        "symbols": ["pelgrom_sigma_vth_mv", "pelgrom_sigma_beta_rel", "vth_at",
                    "mobility_ratio", "conductance_at_temperature",
                    "thermal_noise_psd", "flicker_input_noise_psd",
                    "flicker_output_noise_psd", "input_referred_noise_psd",
                    "nominal_conductances", "sample_mismatch",
                    "mismatched_conductances", "mvm_output", "mc_output_error",
                    "sigma_vs_n", "calibration_report", "MISMATCH_PROCESS",
                    "MISMATCH_DISCLOSURE", "run_selfchecks"],
        "introduced_by": "D-158 (E8)", "guard": "run_ecore_e8_smoke.py",
    },
    {
        "capability": "千级阵列规模压力（层次化 AREF 版图 O(N) + 一维三对角 IR-drop 求解 O(N) + 三重规模律 + 可及规模上界 + 同族维度诚实对标）",
        "module": "lda_l2.ecore.array_scale",
        "symbols": ["elements_flat", "elements_hierarchical", "compression_ratio",
                    "hierarchical_gds", "expanded_element_count", "row_line_profile",
                    "ir_drop_scaling", "max_scale_for_budget", "sigma_cell_rel",
                    "sigma_out_rel", "array_scale_sweep", "honest_comparison",
                    "honest_boundary_ok", "LANDMARKS", "LDA_CAPABILITIES",
                    "NON_CLAIMED", "SCALE_DISCLOSURE", "run_selfchecks"],
        "introduced_by": "D-159 (E9)", "guard": "run_ecore_e9_smoke.py",
    },
    {
        "capability": "器件级内核桥（MOSCAP 1D 自洽泊松 ⟷ 教科书闭式交叉验证：V_th 与 Q_s 跨点一致 + 量纲桥 + 参数自洽性显式报告）",
        "module": "lda_l2.ecore.device_pde",
        "symbols": ["UM_TO_M", "NM_TO_M", "CM3_TO_M3", "F_PER_UM2_TO_F_PER_M2",
                    "um_to_m", "m_to_um", "nm_to_m", "m_to_nm", "cm3_to_m3",
                    "m3_to_cm3", "cox_f_per_um2_to_f_per_m2",
                    "physics_vth_closed", "physics_qs_closed", "physics_vth_pde",
                    "moscap_qs_pde", "cross_check_vth", "cross_check_qs",
                    "pde_vs_closed_sweep", "parameter_consistency_report",
                    "device_pde_self_check", "DEVICE_PDE_DISCLOSURE"],
        "introduced_by": "D-163 (E11-c)", "guard": "run_ecore_e11_smoke.py",
    },
    {
        "capability": "器件级模型失效边界（数值窗口实测复现 + 物理模型边界文献登记 + 缺口量化 · 两类边界严格分离）",
        "module": "lda_l2.ecore.device_limits",
        "symbols": ["N_CRIT_NUMERICAL", "N_CRIT_DEGENERATE", "WINDOW_HALF_WIDTH_PHI_F",
                    "numerical_window_phi_f", "degeneracy_phi_f",
                    "window_ratio_physical_over_numerical", "LITERATURE_LIMITS",
                    "LITERATURE_PARAMS", "yau_rolloff_dvth", "dibl_characteristic_length",
                    "dibl_dvth", "velocity_saturation_field", "mobility_degradation_factor",
                    "literature_gap_report", "capability_boundary_map",
                    "DEVICE_LIMITS_DISCLOSURE", "run_selfchecks"],
        "introduced_by": "D-164 (E11-d)", "guard": "run_ecore_e11d_smoke.py",
    },
    {
        "capability": "2D MOS 求解器（四端栅/源/漏/衬底 · 变系数 FV 泊松 · 电子准费米势分裂 · "
                      "roll-off / DIBL 由 2D 数值解自然涌现 ⟷ 教科书 1D 闭式交叉验证）",
        "module": "lda_l2.ecore.device_2d",
        "symbols": ["LG_NM_DEFAULT", "XJ_NM_DEFAULT", "T_OX_NM_DEFAULT", "NA_CM3_DEFAULT",
                    "N_SD_CM3_DEFAULT", "T_SI_NM_DEFAULT", "L_SIDE_NM_DEFAULT",
                    "ROLLOFF_LS_NM", "LONG_CHANNEL_NM",
                    "dimension_roundtrip_report", "cross_check_vth_2d_longchannel",
                    "rolloff_2d_report", "dibl_2d_report", "natural_length_2d",
                    "short_channel_capability_report",
                    "device_2d_compute_rolloff_dibl_for_case",
                    "DEVICE_2D_DISCLOSURE", "device_2d_self_check"],
        "introduced_by": "D-166…D-168 (E12)", "guard": "run_ecore_e12_smoke.py",
    },
    {
        "capability": "2D MOS 漂移扩散输运（I–V / 亚阈值摆幅 / 恒定电流法 V_th）",
        "module": "lda_l2.ecore.device_transport",
        "symbols": ["transfer_curve", "ss_thermal_limit_report",
                    "cross_check_ss_closed_form", "ss_vs_length_report",
                    "current_conservation_report", "id_vd_report",
                    "vth_cc_vs_surface_potential", "transport_capability_closure",
                    "default_vg_list", "DEVICE_TRANSPORT_DISCLOSURE",
                    "device_transport_self_check"],
        "introduced_by": "D-170…D-172 (E13)", "guard": "run_ecore_e13_smoke.py",
    },
    {
        "capability": "真转换器电路：R-2R 梯形 DAC（NMOS 模拟开关 · R_on 精度上限）+ "
                      "SAR/CDAC 电荷重分配 ADC（真瞬态）+ 采样保持 RC",
        "module": "lda_l2.ecore.converter",
        "symbols": ["ideal_dac_voltage", "code_to_bits", "bits_to_code",
                    "r2r_rational_voltage", "nmos_switch_ron_ohm",
                    "r2r_ideal_network_dc", "r2r_nmos_dac_dc", "dac_static_report",
                    "cdac_top_closed_form", "sar_convert", "sar_error_report",
                    "sample_hold_transient", "CONV_PROCESS",
                    "CONVERTER_DISCLOSURE", "converter_self_check"],
        "introduced_by": "D-174…D-176 (E14)", "guard": "run_ecore_e14_smoke.py",
    },
    {
        "capability": "行驱动外设 + 系统链：单位增益缓冲闭式（增益误差 + 闭环输出电阻）· "
                      "R_oc 耦合三对角 IR-drop · 可及规模上界重算 · 端到端系统链（含行系统项）",
        "module": "lda_l2.ecore.periphery",
        "symbols": ["buffer_closed_loop_gain", "buffer_closed_loop_rout",
                    "buffered_row_voltage", "row_driver_mna_check", "vcvs_polarity_fact",
                    "row_line_profile_with_driver", "max_scale_with_driver",
                    "driver_scale_table", "row_load_conductance", "system_chain",
                    "row_system_error", "PERIPHERY_PROCESS",
                    "PERIPHERY_DISCLOSURE", "periphery_self_check"],
        "introduced_by": "D-174…D-176 (E14)", "guard": "run_ecore_e14_smoke.py",
    },
    {
        "capability": "端到端误差预算链（口径桥 LSB ⟷ 相对 % + 三分类合成律（系统 Σ / 随机 RSS+kσ / "
                      "有界 Σ 与 √3）+ 输出有效精度位数 + 误差主导项分析 + 全链预算可及规模上界）",
        "module": "lda_l2.ecore.budget",
        "symbols": ["SYSTEMATIC", "RANDOM", "BOUNDED", "CATEGORIES",
                    "DEFAULT_K_SIGMA", "DEFAULT_ADC_BITS", "DEFAULT_DAC_BITS",
                    "DEFAULT_SCAN_HI", "lsb_to_rel_pct", "rel_pct_to_lsb",
                    "output_effective_bits", "make_term", "combine", "dominant_term",
                    "cell_conductance", "row_segment_resistance", "collect_terms",
                    "error_budget_report", "budget_vs_n", "max_scale_full_chain",
                    "BUDGET_DISCLOSURE", "budget_self_check"],
        "introduced_by": "D-178…D-180 (E15)", "guard": "run_ecore_e15_smoke.py",
    },
    {
        "capability": "权重编程通路（写-校验动力学 · 电平量化 · 写入噪声地板 · 漂移与重校准 · "
                      "良率 · 差分对 · 接 E15 误差预算链）",
        "module": "lda_l2.ecore.weight_prog",
        "symbols": ["program_levels", "level_lsb_rel", "level_error_bound_rel",
                    "level_bound_in_output", "quantize_to_levels",
                    "write_verify_closed", "iter_to_tolerance", "noise_floor_sigma",
                    "write_verify_stochastic", "residual_sigma_out",
                    "output_sigma_matrix_aware",
                    "drift_factor", "drift_rel_pct", "recal_interval", "drift_curve",
                    "yield_fraction", "stuck_error_bound_rel", "differential_pair",
                    "canonical_weights", "program_array", "programming_error_matrix",
                    "programming_budget_terms", "programming_report",
                    "WEIGHT_PROG_DISCLOSURE", "weight_prog_self_check"],
        "introduced_by": "D-181…D-183 (E16)", "guard": "run_ecore_e16_smoke.py",
    },
    {
        "capability": "时序 / 时钟预算链（时间按拓扑合成 · 五阶段节拍 · 时钟反解 · "
                      "规模×时间 · 阵列 RC 交叉点）",
        "module": "lda_l2.ecore.timing",
        "symbols": ["normalize_stages", "serial_sum", "pipelined_period", "combine_time",
                    "rc_settle_time", "settle_half_lsb", "sar_period",
                    "row_stage_time", "col_stage_time", "sample_hold_stage_time",
                    "cdac_total_cap", "cdac_settle_tau", "cdac_clock_from_settle",
                    "sar_stage_time", "dac_stage_time", "stage_times",
                    "per_sample_report", "clock_budget", "time_vs_n", "crossover_n_ps",
                    "TIMING_PROCESS", "TIMING_DISCLOSURE", "timing_self_check"],
                    "introduced_by": "D-185…D-187 (E17)", "guard": "run_ecore_e17_smoke.py",
    },
    {
        "capability": "列侧共享与架构权衡（面积-时间乘积守恒 · 保吞吐 ⇒ 面积 ∝1/K² 的"
                      "双项闭式 N·C_tot/(ρK²)+N·A_logic/K · 拐点 K* · kT/C 位数地板 · "
                      "架构族对照 · 列侧读出面积 vs 阵列本体 · 复制 vs 共享同一双曲线）",
        "module": "lda_l2.ecore.col_share",
        "symbols": ["thermal_noise_rms_v", "thermal_noise_bits_ceiling",
                    "bits_ceiling_of_share", "ktc_crossing_share",
                    "cap_area_um2", "converter_area_um2", "readout_area_um2",
                    "analytic_area_um2", "area_period_product_um2_s",
                    "converter_period_s", "col_throughput_sps",
                    "k_star", "fit_loglog_slope", "scaling_law_report",
                    "architectures", "recommend_architecture",
                    "replication_vs_sharing", "COL_SHARE_PROCESS",
                    "COL_SHARE_DISCLOSURE", "col_share_self_check"],
        "introduced_by": "D-189…D-191 (E18)", "guard": "run_ecore_e18_smoke.py",
    },
    {
        "capability": "列侧共享的动态代价（复用开关电荷注入 + 时钟馈通 · 采样孔径抖动 · 多路开关建立时间"
                      "对吞吐的侵蚀）—— 闭合 E18 G-S 自点名缺口，把「静态面积」口径闭合成"
                      "「静态 + 动态」：① 电荷注入确定性 pedestal（可单点校准消除）+ Pelgrom 随机残差"
                      "② 孔径抖动 σ_v=π·f·V_ref·σ_t（地板=E18 kT/C）③ 保吞吐共享下 mux 建立侵蚀 ∝K",
        "module": "lda_l2.ecore.col_share_dynamic",
        "symbols": ["KB", "COL_SHARE_DYN_PROCESS", "COL_SHARE_DYN_DISCLOSURE",
                    "charge_injection_pedestal_v", "charge_injection_residual_sigma_v",
                    "aperture_jitter_sigma_v", "jitter_bandwidth_limits",
                    "mux_settling_tau", "mux_settling_erosion",
                    "dynamic_budget_terms", "dynamic_cost_report",
                    "col_share_dynamic_self_check"],
        "introduced_by": "D-194 (E19)", "guard": "run_ecore_e19_smoke.py",
    },
    {
        "capability": "规模/误差口径的单一真源 + 行线 IR-drop **解析金标**（闭式 p_m=(u^{m+1}+u^{−m})/(1+u) "
                      "⟷ Thomas 数值解独立对拍 <1e-9）· 五口径登记 + 成对约束机检 + 反向完备 · "
                      "对外载体取数（`card_pressure_tiers`）· **列线电阻贡献量化**（+29.8%~+40.7%，"
                      "推翻「二阶项」旧措辞）· 成对规模上界（仅IR ⟷ 全链）",
        "module": "lda_l2.ecore.scale_basis",
        "symbols": ["SCALE_BASIS", "PAIRED_GROUPS", "BUDGET_UNIT", "row_line_alpha",
                    "row_line_closed_form", "closed_form_sum_n", "dual_ir_basis",
                    "scale_ceiling_paired", "card_pressure_tiers",
                    "col_resistance_contribution", "col_contribution_sweep",
                    "basis_coverage_report", "pairing_report",
                    "scale_basis_self_check", "SCALE_BASIS_DISCLOSURE"],
        "introduced_by": "D-195 (E20)", "guard": "run_ecore_e20_smoke.py",
    },
    {
        "capability": "功耗模型 + 能效三档口径（`INTERNAL_TARGET` / `MODEL_ESTIMATE` / `MEASURED` 空置）· "
                      "逐部件功耗分解 · 吞吐 2N²/T_conv · 两条标度律（阵列主导 TOPS/W 与 N 无关 ⟷ "
                      "ADC 主导 ∝N）· Landauer 地板 · ½CV² 金标 · 电导敏感性（∝1/g，含精确偏离闭式）",
        "module": "lda_l2.ecore.energy",
        "symbols": ["ENERGY_TIERS", "ENERGY_PROCESS", "EFFICIENCY_LANDMARKS",
                    "MEASURED_AVAILABLE", "OUTPUT_TIER", "KB", "cap_energy_j",
                    "landauer_limit_j", "cdac_switching_energy_j", "cdac_total_cap_f",
                    "array_static_power_w", "row_line_dynamic_power_w", "adc_power_w",
                    "logic_power_w", "leakage_power_w", "throughput_ops_per_s",
                    "system_energy_report", "efficiency_vs_n",
                    "array_dominated_efficiency_gops_per_w", "crossover_n",
                    "sensitivity_on_unit_conductance", "energy_vs_landmark",
                    "energy_self_check", "ENERGY_DISCLOSURE"],
        "introduced_by": "D-196 (E21)", "guard": "run_ecore_e21_smoke.py",
    },
    {
        "capability": "器件族登记（NOR Flash / RRAM / PCM / 模拟 SRAM · 公开 A 级来源照录）· "
                      "**可行性反解**（目标 fJ/op ⇒ 所需 g，含 P_other 地板；低于地板**显式无解**）· "
                      "**能效地板** `P_other·T_conv/(2N²)` · 四必要条件逐族判定（电导/精度/耐久/工艺）· "
                      "**瓶颈迁移表**（器件 → 行线驱动/ADC/外围）",
        "module": "lda_l2.ecore.device_family",
        "symbols": ["DEVICE_FAMILIES", "EFFICIENCY_TARGETS", "DEFAULT_N", "DEFAULT_BITS",
                    "efficiency_floor_fj_per_op", "conductance_inverse", "roundtrip_error",
                    "family_feasibility", "recommend_family", "dominant_shift_table",
                    "device_family_self_check", "DEVICE_FAMILY_DISCLOSURE"],
        "introduced_by": "D-197 (E22)", "guard": "run_ecore_e22_smoke.py",
    },
    {
        "capability": "外围能耗空间（行线驱动 4 式 · ADC 列共享 · 逻辑时钟）· **优化阶梯**（逐杠杆改善与达标状态）· "
                      "**可达性矩阵**（只报「要到目标需要什么」，不宣称达到）· 🔴 行线电容**强制取 E7 真源**"
                      "（禁 τ/R 反解 —— 该缺陷曾使地板偏大 3.89×）",
        "module": "lda_l2.ecore.drive_scheme",
        "symbols": ["DRIVE_SCHEMES", "ADC_SCHEMES", "LADDER_STEPS", "scheme_energy_report",
                    "floor_by_scheme", "optimization_ladder", "reachability_matrix",
                    "drive_scheme_self_check", "DRIVE_SCHEME_DISCLOSURE"],
        "introduced_by": "D-198 (E23)", "guard": "run_ecore_e23_smoke.py",
    },
    {
        "capability": "ADC 架构能耗（标准 SAR / 单调 SAR / 两步式 / 两步+单调）· "
                      "**不变性** `E_op=e_sample/(2nK)` 与 f_s 无关 · 列共享功耗-带宽权衡 · "
                      "**未建模项区间披露**（比较器/参考缓冲/残差放大/校准 ⇒ ADC 能耗是**下界**）· "
                      "三项占位参数敏感性（duty_read/c_unit_fF/c_logic_fF_per_cell）",
        "module": "lda_l2.ecore.adc_arch",
        "symbols": ["ADC_ARCHITECTURES", "UNMODELED_OVERHEAD", "cdac_cap_units",
                    "adc_energy_per_op", "overhead_bounds", "sharing_tradeoff",
                    "sensitivity_analysis", "adc_arch_self_check", "ADC_ARCH_DISCLOSURE"],
        "introduced_by": "D-199 (E24)", "guard": "run_ecore_e24_smoke.py",
    },
    {
        "capability": "ADC 能耗**可信度校准**：真实单位电容（0.3~2 fF · 带出处）· "
                      "**三条实测 FOM 外锚**（16.8 / 2.07 / 15.99 fJ/c-s）· "
                      "🔴 **CDAC 只占 ADC 总能耗 0.6~3.6%%** ⇒ 优化电容抓错 98%% · "
                      "用实测锚反推**可信地板**（33.7 fJ/op，模型自算的 3.3×）",
        "module": "lda_l2.ecore.adc_calibration",
        "symbols": ["C_UNIT_LITERATURE", "PLACEHOLDER_C_UNIT_FF", "MEASURED_ADC_ANCHORS",
                    "anchor_energy_per_conversion", "cdac_share_vs_measured",
                    "cdac_share_table", "adc_energy_per_op_from_anchor",
                    "floor_with_measured_adc", "c_unit_sensitivity",
                    "adc_calibration_self_check", "ADC_CALIBRATION_DISCLOSURE"],
        "introduced_by": "D-200 (E25)", "guard": "run_ecore_e25_smoke.py",
    },
    {
        "capability": "ADC 能耗**四项物理预算**（CDAC / 比较器 / 时钟 / 逻辑，闭式齐全）· "
                      "**覆盖率分析**（跨设计 18~89%% · 4.9× 离散）· **单参数集可标定性**"
                      "（s_i = 1.13/5.46/5.63，常规档 3.2%% 一致 ⟷ 低速档偏离 4.83×）· "
                      "**自由度分析**（dof=−3 ⇒ 不可校核 · 守「不得宣称精度」）· "
                      "**区间地板**（14.9~66.2 fJ/op · 替代单点报法）· f_s 依赖结构性预言",
        "module": "lda_l2.ecore.adc_budget",
        "symbols": ["PROCESS_NODES", "CIRCUIT_ASSUMPTIONS", "UNEXPLAINED_SOURCES",
                    "budget_terms", "coverage_vs_measured", "coverage_table",
                    "coverage_spread", "required_scale", "scalability_analysis",
                    "dof_analysis", "fs_dependence", "floor_interval",
                    "adc_budget_self_check", "ADC_BUDGET_DISCLOSURE"],
        "introduced_by": "D-201 (E26)", "guard": "run_ecore_e26_smoke.py",
    },
    {
        "capability": "N×K **联合规模优化**：N 上界 vs 行线电阻（5%% 预算 12→26→42→140 行）· "
                      "ADC 项**摊薄 ∝1/N**（可及 N=12 是 N=64 的 5.33×）· "
                      "**列共享 K 净收益**（只有静态部分随 K 除 × E19 mux 侵蚀 · "
                      "**β* 盈亏平衡闭式**：K=64 需 β>0.0270）· **杠杆排序**（行线电阻 ≫ K）",
        "module": "lda_l2.ecore.joint_scale",
        "symbols": ["baseline_r_seg", "BETA_PLACEHOLDER", "BETA_SCENARIOS", "R_DIVS",
                    "n_ceiling", "n_ceiling_table", "adc_dilution", "k_net_gain",
                    "k_breakeven_beta", "k_gain_table", "attainable_efficiency",
                    "leverage_ranking", "joint_scale_self_check",
                    "JOINT_SCALE_DISCLOSURE"],
        "introduced_by": "D-202 (E27)", "guard": "run_ecore_e27_smoke.py",
    },
    {
        "capability": "行线电阻**反解与版图可行性**：金属层登记（M1→RDL）· 三条降阻路径"
                      "（换层 / 加宽 / 双端驱动）· **两条精确不变性**（`R·C` 与线宽无关 · "
                      "`C` 与金属厚度无关）· 方案表（N 12→29→42→87→125→200）· "
                      "**代价模型**（电容比/行线份额/via/掩模/驱动器 ×2 · 明写未做 DRC）",
        "module": "lda_l2.ecore.row_metal",
        "symbols": ["METAL_LAYERS", "DRIVE_MODES", "WIDTHS", "PLANS",
                    "seg_rc", "rc_invariance", "c_vs_thickness", "n_ceiling_for",
                    "plan_table", "best_plan", "cost_model", "row_metal_self_check",
                    "ROW_METAL_DISCLOSURE"],
        "introduced_by": "D-203 (E28)", "guard": "run_ecore_e28_smoke.py",
    },
    {
        "capability": "**版图可行性**：层栈缺口量化（平台 7 层 · E28 换层需 +8~+10 层）· "
                      "**DRC 临界线宽扫描**（0.52 µm 放行 / 0.55 REJECT）· "
                      "DRC/LVS/GDS 矩阵（roundtrip + 几何回提）· **三路径可行判定**"
                      "（realizable 全 False）· **DRC 复杂度 O(N⁴) 实测**· 双端端口代价（不编数）",
        "module": "lda_l2.ecore.layout_feasibility",
        "symbols": ["current_layers", "REQUIRED_LAYERS", "DRC_NS", "DRC_WIDTHS",
                    "layer_gap", "drc_width_scan", "max_drc_width", "drc_matrix",
                    "drc_scaling", "feasible_paths", "dual_drive_cost",
                    "layout_feasibility_self_check", "LAYOUT_FEASIBILITY_DISCLOSURE"],
        "introduced_by": "D-204 (E29)", "guard": "run_ecore_e29_smoke.py",
    },
    {
        "capability": "**层栈扩展**（6→16 层 · +M3/M4/M5/M6/AP + VIA2-VIA5/VIA_AP · 纯加法）· "
                      "行线可选层（`row_layer`）· **换层三障碍实测**（CONT 悬空 / AP 强制加宽 / "
                      "AP 行距约束）· **第一条 DRC 全过的换层路径**（AP W1.60 pitch_y3.20 ⇒ r×40）",
        "module": "lda_l2.ecore.layer_stack_ext",
        "symbols": ["BASELINE_STACK", "EXTENDED_STACK", "BASELINE_GDS", "AP_PATHWAYS",
                    "stack_comparison", "baseline_unchanged", "row_layer_matrix",
                    "dangling_analysis", "ap_pathway", "ap_forced_widen", "gap_closure",
                    "layer_stack_ext_self_check", "LAYER_STACK_EXT_DISCLOSURE"],
        "introduced_by": "D-205 (E30)", "guard": "run_ecore_e30_smoke.py",
    },
    {
        "capability": "**换层签核**：漏极 via stack（12 层链 · 落垫按上方 via enclosure 反算）· **层序审计**（每 via 严格夹层 · E30 曾错位一层）· **DRC/LVS 静默漏检修复**（`stack` 参数）· 签核矩阵（7 层 → 6 过 · M2 短路）· 规模能效表（N 12→87 · vs Mythic 21.6×→3.0×）· via 数量与良率风险（90,828 个未建模）",
        "module": "lda_l2.ecore.signed_off_stack",
        "symbols": ["MATRIX_N", "BASE_WIDTH_UM", "LAYER_THICKNESS_UM", "END_VIA_OF", "BASELINE_GDS", "z_order_audit", "pad_sizing_rule", "signoff_matrix", "signoff_summary", "m2_infeasibility", "attainable_table", "best_layer", "via_count_cost", "baseline_unchanged", "signed_off_stack_self_check", "SIGNED_OFF_STACK_DISCLOSURE"],
        "introduced_by": "D-206 (E31)", "guard": "run_ecore_e31_smoke.py",
    },
    {
        "capability": "**版图空间索引**（均匀网格 + 长条单列 · 候选筛选只缩小搜索范围、判定仍用 `_overlap`/`_gap`）· **新旧对拍**（9 案例含 5 个 REJECT · verdict + 违规集合逐条一致）· **规模表**（N=87 = 143,985 元素 · DRC+LVS **4.1s** 全 ACCEPT，旧实现外推 ~7h）· 经验复杂度 **N^2.35**（旧 N^4）· 超集性机核（`near ⊇ brute`）· 小规模回退阈值",
        "module": "lda_l2.ecore.spatial",
        "symbols": ["Grid", "near_pairs", "brute_pairs", "PARITY_CASES", "parity_matrix", "parity_summary", "SCALE_NS", "scale_table", "scale_summary", "spatial_self_check", "SPATIAL_DISCLOSURE"],
        "introduced_by": "D-207 (E32)", "guard": "run_ecore_e32_smoke.py",
    },
    {
        "capability": "**端到端流程编排**（8 Stage：device→scale→stack→layout→drc→lvs→gds→report · fail-fast · **反向完备**「少一步不算跑通」）· 🔴 **每数字带 basis/claimable**（能效双口径：实测锚 ✅ ⟷ 自算下界 ❌；面积双口径：同 N 代价 ✅ ⟷ 总比含规模 ❌）· **可复现对拍**（两次跑逐位一致）· **fail 与未达标分离**（4 场景机核）· **N=87 全链**（143,985 元素 · 5.8MB GDS · roundtrip）· 人可读签核报告渲染",
        "module": "lda_l2.ecore.soc_flow",
        "symbols": ["STAGES", "STAGE_ROLE", "SPEC_DEFAULT", "MIN_N", "G_READ_TYP_S", "stage_device", "stage_scale", "stage_stack", "stage_layout", "stage_drc", "stage_lvs", "stage_gds", "stage_report", "run_flow", "report_text", "flow_parity", "fail_semantics_check", "soc_flow_self_check", "SOC_FLOW_DISCLOSURE"],
        "introduced_by": "D-208 (E33)", "guard": "run_ecore_e33_smoke.py",
    },
    {
        "capability": "**自有标准单元库**（静态互补 CMOS · 18 单元 / 130 管）· "
                      "**晶体管数 `n_tr` 作绝对锚**（拓扑必然：INV=2T / NAND2=4T / DFF=24T，"
                      "非拟合）· 一阶 RC 延时 `t_intr + k·ln2·R·C` · "
                      "**族内 `k_drive` 与串联数同序 + 跨族方向判据**（NOR>NAND / AND>NAND）· "
                      "解析金标 `chain_golden_ps`（0 级恰为 0）",
        "module": "lda_l2.ecore.dcell",
        "symbols": ["Cell", "Tech", "CELLS", "COMB_CELLS", "BASE_PRIMS", "DEFAULT_TECH",
                    "cell", "eval_cell", "cell_delay_ps", "cell_area_um2", "cell_leak_nw",
                    "chain_golden_ps", "library_self_check", "DCELL_DISCLOSURE"],
        "introduced_by": "D-209 (E34)", "guard": "run_ecore_e34_smoke.py",
    },
    {
        "capability": "**可综合 Verilog 子集前端 + RTL 解释器（引擎 A）**：词法/递归下降语法 · "
                      "**位宽上下文传播**（`~0` 是 32 位；`[4:0]y=a+b` 必须保住进位）· "
                      "**非阻塞语义（读旧值）** · 状态外提为一级输入（`sig@q` / `sig@d`）· "
                      "超出子集显式抛 `Unsupported`（不静默降级）",
        "module": "lda_l2.ecore.drtl",
        "symbols": ["Unsupported", "Module", "parse", "tokenize", "Parser", "ev",
                    "rtl_eval_all", "drtl_self_check", "DRTL_DISCLOSURE"],
        "introduced_by": "D-210 (E34)", "guard": "run_ecore_e34_smoke.py",
    },
    {
        "capability": "**AIG 布尔网络**：单节点 AND + 反相边（`lit=2*node+inv`）· "
                      "常数传播 / 幂等 / 互补 / **结构哈希 CSE** · 派生 OR/XOR/XNOR/MUX · "
                      "归约 / 相等 / **无符号小于（累积方向必须 LSB→MSB）** / 行波加法 · "
                      "**只做可证明等价的变换**（不做可能更省但不保等价的优化）",
        "module": "lda_l2.ecore.daig",
        "symbols": ["Aig", "red_or", "red_and", "eq_bits", "ult_bits", "add_bits",
                    "mux_bits", "const_bits", "bits_value", "DAIG_DISCLOSURE"],
        "introduced_by": "D-211 (E34)", "guard": "run_ecore_e34_smoke.py",
    },
    {
        "capability": "**逻辑综合 + 门级网表仿真（引擎 B）**：AST→AIG 位展开（组合不动点 · "
                      "**latch 推断显式拒绝**）→ 技术映射（NAND2+INV+DFF+TIE）→ 网表 · "
                      "**网表真实性判据**（输出必被单元驱动 / DFF 数==状态位 / 拓扑无前向引用）· "
                      "`sim_netlist` 逐单元查真值表（与引擎 A 代码路径零共享）",
        "module": "lda_l2.ecore.dsynth",
        "symbols": ["Gate", "Netlist", "synth", "sim_netlist", "netlist_authenticity",
                    "input_net", "dsynth_self_check", "DSYNTH_DISCLOSURE"],
        "introduced_by": "D-212 (E34)", "guard": "run_ecore_e34_smoke.py",
    },
    {
        "capability": "**静态时序分析 + 面积/功耗**：拓扑序到达时间传播 · clk→Q 起点 · "
                      "建立检查 `t_clk_min=max(arrival(D)+t_setup)` · 关键路径回溯 · "
                      "**三条独立路径金标**（图传播 / 逐级累加 / 代数相乘，rel<1e-12）· "
                      "🔴 `hold_checked=False`（单角零偏斜下形式满足 ⇒ **不谎称验过**）",
        "module": "lda_l2.ecore.dsta",
        "symbols": ["Timing", "sta", "loads_of", "switching_power_nw", "clock_power_nw",
                    "chain_golden_from_loads", "build_chain_nl", "sta_self_check",
                    "DSTA_DISCLOSURE"],
        "introduced_by": "D-213 (E34)", "guard": "run_ecore_e34_smoke.py",
    },
    {
        "capability": "**等价性双引擎穷举 + 响应率 ρ + 锁步序列对拍**：逐位相等容差 0 · "
                      "端口集合/位宽双向对齐 · 位宽≤14 **全穷举**（否则定向角点+随机并报实跑数）· "
                      "**ρ ≡ 单门扰动被判红的比例（<0.8 视为判据无判别力，绿也不算数）** · "
                      "`lockstep` 两条状态轨迹独立推进，覆盖**可达状态空间**（随机向量对 70 位输入等于零覆盖）",
        "module": "lda_l2.ecore.dequiv",
        "symbols": ["equiv", "rho", "lockstep", "compare_on", "unpack", "n_bits",
                    "equiv_self_check", "DEQUIV_DISCLOSURE"],
        "introduced_by": "D-214 (E34)", "guard": "run_ecore_e34_smoke.py",
    },
    {
        "capability": "**CIM 控制壳（第一个真实数字设计）**：单 ADC 时分复用行扫描 FSM（5 态）· "
                      "**位宽由物理动态范围反解**（row_sel=⌈log2 87⌉=7 · bit_sel=3 · "
                      "**acc=⌈log2(87×8×255+1)⌉=18**（16/17 位会静默溢出）· scnt=5）· "
                      "18 拍 SPI 读回 · **闭环**：数字壳 Fmax vs SAR 由 CDAC 建立时间决定的时钟 · "
                      "架构差异显式声明（不与 E17 并行 ADC 相除）",
        "module": "lda_l2.ecore.dctrl",
        "symbols": ["CIM_CTRL_SRC", "ROW_N", "BITS", "ACC_EVENTS", "ACC_WIDTH",
                    "ACC_WIDTH_MIN", "ADC_MAX", "build", "stimulus", "lockstep",
                    "acc_width_witness", "closure", "power_at", "ctrl_self_check",
                    "DCTRL_DISCLOSURE"],
        "introduced_by": "D-215 (E34)", "guard": "run_ecore_e34_smoke.py",
    },
    {
        "capability": "**CIM 加速器 IP 的 P&R（E35 · 自建最小但诚实）· 第 0 层 标准单元布局**："
                      "行式布局（行高固定 · 宽=面积/行高 ⇒ **面积逐位守恒**）· 按连通度降序填充 + "
                      "有限随机爬山降 HPWL · 端口沿边界落点 · 环绕 IO ring",
        "module": "lda_l2.ecore.dplac",
        "symbols": ["Placement", "place", "ip_digital_region", "plac_self_check",
                    "DPLAC_DISCLOSURE", "IO_RING_UM", "H_ROW_UM", "SEED"],
        "introduced_by": "D-216 (E35)", "guard": "run_ecore_e35_smoke.py",
    },
    {
        "capability": "**P&R 第 1 层 全局布线**：曼哈顿度量 MST（Prim）把多端网拆成 2 端 L 形布线 · "
                      "**金标：2 端网线长 ≥ 两端曼哈顿距离（精确下界）** · 多端网必布 · "
                      "总线长 ≤ 1.5×HPWL（抓翻倍编数）",
        "module": "lda_l2.ecore.droute",
        "symbols": ["Route", "route", "route_self_check", "DROUTE_DISCLOSURE",
                    "_validate", "_break_one_two_pin", "_net_pins"],
        "introduced_by": "D-217 (E35)", "guard": "run_ecore_e35_smoke.py",
    },
    {
        "capability": "**P&R 第 2 层 线载提取 + 线感知 STA**：线长×c_per_um → 每网 C_wire → "
                      "注入 `dsta.sta` → **真实 Fmax** · 金标：Fmax(线载)<Fmax(理想) · "
                      "线载×K 单调降 · 线载=0 逐位=理想",
        "module": "lda_l2.ecore.dextract",
        "symbols": ["WireSTA", "wire_loads", "wire_aware_sta", "extract_self_check",
                    "DEXTRACT_DISCLOSURE", "C_WIRE_FF_PER_UM"],
        "introduced_by": "D-218 (E35)", "guard": "run_ecore_e35_smoke.py",
    },
    {
        "capability": "**P&R 第 3 层 IP 硬宏 + GDS 合并（E36 深化）**：阵列 GDS（E33 栈）+ 数字单元包围盒 + "
                      "**E36 detail route 真实金属(M3/M4/VIA2)** + **E36 真实单元几何(有源/M1/通孔栈)** + "
                      "外框 + 引脚 → 单一 IP GDS · **金标：合并元素 emit ≡ 回读 parse（零丢失，含 route+cell 形状）** · "
                      "对数字区路由几何跑 IP 级 DRC/LVS · 复用 gds_export 编码器与 parse_gds_polygons 回读",
        "module": "lda_l2.ecore.dmacro",
        "symbols": ["Macro", "build_ip", "closure", "macro_self_check",
                    "DMACRO_DISCLOSURE", "GAP_UM", "LAYER_DIGITAL",
                    "LAYER_IP_BOUNDARY", "LAYER_PIN", "_desc_bytes", "_box", "_pin"],
        "introduced_by": "D-219 (E35) · E36 深化", "guard": "run_ecore_e36_smoke.py",
    },
    {
        "capability": "**P&R 深化（D-220 detail route + D-221 真实单元几何）**：把 MST 每网画成真实金属多边形"
                      "（H=M3 / V=M4 / 弯角 VIA2）· 金标：每网布出中心线长 ≥ MST 长（2 端网 ≡ 曼哈顿距离）；"
                      "数字单元从包围盒升级为 有源区标记(E_DIFF/20) + M1 引脚焊垫 + 通孔栈(M1→M2→M3)；"
                      "金标：每单元 ≥1 有源 + ≥1 引脚 · 🔴 模型尺度下内部几何符号级(非 PDK)",
        "module": "lda_l2.ecore.ddetail",
        "symbols": ["Shape", "DetailRoute", "detail_route", "real_cell_geom",
                    "rects_overlap", "point_in_rect", "detail_self_check",
                    "cellgeom_self_check", "DDETAIL_DISCLOSURE", "L_M1", "L_M2",
                    "L_M3", "L_M4", "L_DIFF", "L_VIA1", "L_VIA2", "W_ROUTE",
                    "VIA", "ENC", "PIN_R", "_rect", "_mst_edges", "_net_pins"],
        "introduced_by": "D-220…D-221 (E36)", "guard": "run_ecore_e36_smoke.py",
    },
    {
        "capability": "**P&R 深化（D-222 IP DRC + D-223 IP LVS）**：对数字区路由几何做签核 · "
                      "DRC：最小线宽/最小间距(异网同层)/通孔包围+悬空；LVS：几何 flood-fill 连通性"
                      "（每网单分量 + 终端被覆盖）+ 异网同层短路 · "
                      "🔴 规则值假设(非 PDK) · 仅 M1/M3/M4+通孔 · 简化 L 路由 baseline 大量违例是已知诚实事实",
        "module": "lda_l2.ecore.ddrc_lvs",
        "symbols": ["W_MIN", "S_MIN", "ENC", "VIA_BRIDGE", "BRIDGE_PRESENT",
                    "run_drc", "_union_find", "run_lvs", "drc_self_check",
                    "lvs_self_check", "DDRC_LVS_DISCLOSURE"],
        "introduced_by": "D-222…D-223 (E36)", "guard": "run_ecore_e36_smoke.py",
    },
    {
        "capability": "**E37 校验器硬化（D-224）**：DRC/LVS 空间哈希加速版 `fast_drc`/`fast_lvs` "
                      "与原生 O(n²) `run_drc`/`run_lvs` **逐位一致**（DRC 总数+分类、LVS 总数+分类），"
                      "并修复两个真 bug：① fast_lvs 漏检 short_via；② 金属-金属短路误用 routed 网格"
                      "致下标串位重复计数 · 金标：等价 + 突变探针（窄金属/悬空孔）必红 · 大布局下 O(n²) 超时规避",
        "module": "lda_l2.ecore.ddrc_lvs",
        "symbols": ["fast_drc", "fast_lvs", "checker_equiv_self_check"],
        "introduced_by": "D-224 (E37)", "guard": "run_ecore_e37_smoke.py",
    },
    {
        "capability": "**E37 track 分配 + 拥堵负结果（D-224）**：interval 着色给 H(M3)/V(M4) 主段分配"
                      "独立轨道 + landing pad 修 via · **诚实负结果**：主段能上轨但引脚接入压在稠密共享行/列，"
                      "track 总 DRC=913k 反高于基线 204k；拥堵量化（每行 clique 87~120 vs 通道 2 轨）证"
                      "真清零需 ≥14.6× 面积 ⇒ 2 层 L 路由在本密度**不能清零**（清零留给真实 maze/multilayer router）",
        "module": "lda_l2.ecore.ddetail",
        "symbols": ["track_route", "interval_color", "track_self_check",
                    "congestion_analysis", "_via_landing", "TRACK_PITCH"],
        "introduced_by": "D-224 (E37)", "guard": "run_ecore_e37_smoke.py",
    },
    {
        "capability": "**E38a 网格迷宫路由器 + 可布通性（D-225）**：M3(横)/M4(竖) 两层网格 · 逐网 BFS "
                      "迷宫布线（贪心一次布）· 分层独立占用（异网横竖可在同点交叉不短路）· via 带 landing pad · "
                      "**金标**：稀疏合成控制组 100% 布通 + DRC=0 + LVS 通 + 线长≥MST；真实布局布通率如实报"
                      "（本密度仅 3.2%=44/1354）+ 密度扫描证放大即回升 · 🔴 真实几何 DRC/LVS 只作信息（单元黑盒共享终端）",
        "module": "lda_l2.ecore.ddroute_grid",
        "symbols": ["route_grid", "routability_vs_spread", "route_grid_self_check",
                    "grid_dims", "DDROUTE_GRID_DISCLOSURE", "PITCH"],
        "introduced_by": "D-225 (E38a)", "guard": "run_ecore_e38_smoke.py",
    },
]



def _package_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def ecore_module_names() -> list:
    """返回 ecore 包内参与反向完备的模块名（不含排除项）。"""
    d = _package_dir()
    return sorted(f[:-3] for f in os.listdir(d)
                  if f.endswith(".py") and f[:-3] not in ECORE_EXCLUDE_MODULES)


def manifest_check() -> dict:
    """清单 ↔ 实际模块/符号 的双向完备检查（供常驻门禁调用）。"""
    missing_symbols = {}
    import_fail = {}
    for e in ECORE_CAPABILITY_MANIFEST:
        modname = e["module"]
        try:
            m = importlib.import_module(modname)
        except Exception as ex:                      # noqa: BLE001
            import_fail[modname] = repr(ex)
            continue
        miss = [s for s in e["symbols"] if not hasattr(m, s)]
        if miss:
            missing_symbols[modname] = miss
    declared = {e["module"].split(".")[-1] for e in ECORE_CAPABILITY_MANIFEST}
    undeclared = sorted(set(ecore_module_names()) - declared)
    return {
        "import_fail": import_fail,
        "missing_symbols": missing_symbols,
        "undeclared_modules": undeclared,
        "declared_modules": sorted(declared),
        "all_modules": ecore_module_names(),
        "guard_smokes": [e["guard"] for e in ECORE_CAPABILITY_MANIFEST],
    }


ECORE_CAPABILITY_DISCLOSURE = {
    "route": "电子计算征程 E5 · 平台能力硬化（ecore 能力清单 + 常驻守护门禁）· E10 收官扩面至 e1~e10 · E11-c 扩面至 e1~e11 · E12 扩面至 e1~e12 · E18 扩面至 e1~e18 · E19 扩面至 e1~e19 · E20 扩面至 e1~e20 · E21 扩面至 e1~e21 · E22 扩面至 e1~e22 · E23 扩面至 e1~e23 · E24 扩面至 e1~e24 · E25 扩面至 e1~e25 · E26 扩面至 e1~e26 · E27 扩面至 e1~e27 · E28 扩面至 e1~e28 · E29 扩面至 e1~e29 · E30 扩面至 e1~e30 · E31 扩面至 e1~e31 · E32 扩面至 e1~e32 · E33 扩面至 e1~e33 · E35 扩面至 e1~e35 · E36 扩面至 e1~e36（D-220~D-223：detail route / 真实单元几何 / IP DRC / IP LVS）· E37 扩面至 e1~e37（D-224：DRC/LVS 校验器硬化 fast≡native + track 分配/拥堵负结果）· E38a 扩面至 e1~e38（D-225：网格迷宫路由器 + 可布通性诚实布通率）",
    "e5_scope": "把 E1~E9 逼出的平台能力固化为机器可读清单（单向真源）+ 常驻门禁（正向完备 + 反向完备 + 披露一致 + 诚实边界）",
    "hardening_semantics": "能力面必须被门禁守着：任一模模块/符号缺失、隐身模块出现、或注入 fabricated 指标 ⇒ 门禁必红",
    "redline": "红线 = 分层口径（器件级 T1 内核已解锁 · T2 工艺真值/工艺角/流片永久锁）；"
               "**本包主动限定在电路级**；C 级自主（纯 numpy/标准库）；LLM 不进判决路径",
}
