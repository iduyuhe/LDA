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
                    "input_net", "dsynth_self_check", "DSYNTH_DISCLOSURE", "topo_order"],
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
                    "DEXTRACT_DISCLOSURE", "C_WIRE_FF_PER_UM", "net_length_um", "wire_loads_from_shapes", "loads_from_lengths"],
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
    {
        "capability": "**E38b 多轮 R&R + 完整密度曲线 + 多层对比（D-226）**：抽象多层网格(H/V 交替) · "
                      "单阻塞者**原子 R&R**（net_occ 精确记账 ⇒ rip 后必还原、绝不丢网）· 密度曲线 ×K · "
                      "层数对比 2/4/6 · **金标**：控制组 100% / R&R 原子性 routed(R&R)≥routed(贪心) / "
                      "多层单调 layers4≥layers2 / 密度单调 ×K 非减 · 🔴 结论：R&R/加层/温和摊开都救不了，"
                      "根因是符号级超窄单元密度（cells/node@K1≈0.5），需真实单元面积 · 抽象容量研究不产 GDS",
        "module": "lda_l2.ecore.ddroute_rr",
        "symbols": ["route_rr", "density_curve", "layer_compare", "route_rr_self_check",
                    "make_layers", "DDROUTE_RR_DISCLOSURE", "PITCH"],
        "introduced_by": "D-226 (E38b)", "guard": "run_ecore_e38b_smoke.py",
    },
    {
        "capability": "**E38c 真实标准单元面积标定 + 可布通性重测（D-227）**：area_per_tr 0.040(符号) → "
                      "0.266(Nangate45 NAND2_X1 量级参考) ⇒ dplac.place(tech=real) 重摆（不动 DEFAULT_TECH）· "
                      "**金标**：面积守恒 Σ(w·h)≡Σn_tr·area_per_tr(逐位) / cells/row 显著下降(223→89) / "
                      "routability(real)>symbolic(3.8%→9.7% @2 层) / route-over-cell 层数单调(4L 21.9%≥2L) · "
                      "🔴 诚实：真实面积只抬 2.6×，仍非 100%；残余瓶颈=粗引脚接入(无细 M1/M2)",
        "module": "lda_l2.ecore.drealcell",
        "symbols": ["real_tech", "realistic_place", "realistic_routability", "realcell_self_check",
                    "cells_per_row", "placed_area_um2", "expected_area_um2",
                    "REAL_AREA_PER_TR_45", "AREA_PER_TR_SYMBOLIC", "DREALCELL_DISCLOSURE"],
        "introduced_by": "D-227 (E38c)", "guard": "run_ecore_e38c_smoke.py",
    },
    {
        "capability": "**E38d 细引脚接入逃逸 + 现实线距联调 + 容量结论（D-228）**：access_radius(细层逃逸) + "
                      "现实线距(0.24µm) + 真实单元面积(0.266) + 跨单元布线 + 多层 联调 · **金标**：引脚接入单调 / "
                      "层数单调(4L≥2L) / 线距单调(细≥粗) / 联调≥仅真实单元 / **诚实(联调<90%)** · "
                      "实测联调 ~38.7%（vs 符号 3.8% / 仅真实单元 9.7%）· 🔴 瓶颈已迁到网络密度/布线容量，"
                      "需更大 die（摊开 ×K）· 抽象容量研究不产 GDS",
        "module": "lda_l2.ecore.dpinaccess",
        "symbols": ["pin_access_routability", "pinaccess_self_check", "REAL_AREA_PER_TR",
                    "PITCH_SYMBOLIC", "PITCH_REAL", "DPINACCESS_DISCLOSURE"],
        "introduced_by": "D-228 (E38d)", "guard": "run_ecore_e38d_smoke.py",
    },
    {
        "capability": "**E38e 摊开 ×K 的可测边界 + 失败模式诊断（D-229）**：真实三要素下摊开 die ×K · "
                      "报 util=布线占用/网格容量 · 失败二分(fail_source_blocked/fail_walled) · "
                      "**截断计数 n_truncated + A 星选项**（默认 BFS 保历史口径）· **金标**：跨档一致"
                      "(K=1 == E38d 38.7%) / 参与比较的点零截断 / 失败二分恒等 / 摊开不劣 / 成本 expanded∝K² / "
                      "利用率未被摊开缓解(|Δ|≤5pp) / 紧预算必报截断且有牙 / BFS≡A* · "
                      "🔴 实测 K=1 38.70%(util 27.8%) → K=2(面积 ×4) 66.67%(util 27.9%, 扩展 ×3.82, "
                      "失败 453 网**全是墙切断**) ⇒ **修正 E38d**：根因是贪心 L 型走线的**墙效应**，"
                      "不是容量/密度 ⇒ 加面积不是唯一杠杆 · 抽象容量研究不产 GDS",
        "module": "lda_l2.ecore.dspread",
        "symbols": ["real_place", "spread_point", "capacity_model", "spread_self_check",
                    "E38D_PUBLISHED_COMBINED", "COST_RATIO_MIN", "COST_RATIO_MAX",
                    "UTIL_DRIFT_MAX", "REAL_AREA_PER_TR", "PITCH_REAL", "DSPREAD_DISCLOSURE"],
        "introduced_by": "D-229 (E38e)", "guard": "run_ecore_e38e_smoke.py",
    },
    {
        "capability": "**E38f 破墙路由器（D-230 · 诚实负结果）**：三种选网策略（`frontier` 失败前沿 top-k / "
                      "`corridor` 沿 A→B 全路径 / `tunnel` 用可达集把「口袋界面」定位到格子）+ "
                      "**原子多阻塞者 R&R**（先重布失败网、再让被撕网绕行，任一环失败即原样回滚）+ "
                      "回滚原因分离计数（`r_net_fail`/`r_victim_fail`）· **金标**：原子不丢网（只增不减 + "
                      "已布集合 ⊆ 贪心集）/ 回滚恒等 / 对比零截断 / 机制成立 / 开关无副作用 / 对照命中率 ≤10% · "
                      "🔴 实测 K=1：greedy 38.70% → tunnel 38.70%（**Δ+0，40 次尝试：15 次失败网仍不通、"
                      "25 次隧道已开但牺牲网无法重布 ⇒ 回滚**）⇒ **破墙是零和的**（前沿由 ~340 个网缝成）；"
                      "杠杆只剩加面积(E38e ×3→94.26%) 或全局协商拥塞 · 抽象容量研究不产 GDS",
        "module": "lda_l2.ecore.dwallrr",
        "symbols": ["wall_break", "wall_self_check", "E38E_K1_ROUTABILITY", "FRONTIER_HIT_MAX",
                    "PITCH_REAL", "DWALLRR_DISCLOSURE"],
        "introduced_by": "D-230 (E38f)", "guard": "run_ecore_e38f_smoke.py",
    },
    {
        "capability": "**E38g 全局协商拥塞路由 PathFinder（D-231 · 诚实负结果）**：每轮**全量重布全部网** + "
                      "present-cost 协商（被多网占的节点代价抬高、不累积 runaway）⇒ 全局协商绕开热点；"
                      "松弛布线(允许临时重叠、代价避让) + A*(Manhattan 启发式 admissible) 控展开量；"
                      "冲突判定=本网全部节点 occ_count==1（否则=与他网同层短路=over-congested）· "
                      "🔴 实测 **否证了「全局协商能破墙」的猜想**：本抽象网格每(格,层)只有一条线、无平行走线"
                      "资源 ⇒ 温和代价下网宁可重叠也不绕远（死锁）、陡峭代价下绕远又撞进别处拥塞（乱窜、"
                      "overflow 反升），两种 regime 都**不收敛到更优解**；根因是 K=1 下贪心已有 833 个网"
                      "根本不存在无冲突路径（结构性不可布）。**结论：墙效应是结构性的，PathFinder（同局部"
                      "破墙）救不了；E38 调查确定性收尾，唯一有效杠杆=加面积/层(E38e ×3→94.26%)** · "
                      "机制门禁(记账/确定性/控制组/协商改善初值)全绿 · 抽象容量研究不产 GDS",
        "module": "lda_l2.ecore.dpathfinder",
        "symbols": ["route_pathfinder", "pathfinder_real", "pathfinder_self_check",
                    "PF_K1_OFFLINE", "PF_K2_OFFLINE", "PF_K3_OFFLINE", "DPATHFINDER_DISCLOSURE",
                    "PITCH_REAL", "REAL_AREA_PER_TR", "E38D_PUBLISHED_COMBINED"],
        "introduced_by": "D-231 (E38g)", "guard": "run_ecore_e38g_smoke.py",
    },
    {
        "capability": "**E39 多 track 通道路由模型（D-232 · A2：把 E38g 负结果消化成可机核几何律）**："
                      "把「单 track 网格零 slack」抽成一维**通道密度**问题 —— `channel_density` 由"
                      "**三法互证**（`brute_max_overlap` O(n·span) / `sweep_density` 事件扫描线 / "
                      "`diff_array_density` 坐标压缩差分数组）给出区间最大重叠 d；`left_edge_tracks` "
                      "左边界算法按 `l` 升序优先复用 `r_prev ≤ l` 的轨（区间图完美 ⇒ 色数 == 最大团 == d）；"
                      "`multitrack_route(T)` 判据 **可布通 ⇔ T ≥ d**，布通率 = min(1, T/d)。"
                      "🔴 **消化 E38g**：T=1 且 d=6 ⇒ 布通率 0.167（「单 track 布不通」精确复现）；T=d ⇒ 1.0"
                      "（多 track 解锁）⇒ 结构性缺口不再是玄学，被刻画为 **T 与 d 的比较**。"
                      "🔴 **诚实边界**：一维通道模型，**不复现** E38g 的 2D 墙效应（只抽出可精确判定的子结构）；"
                      "密度/轨道数为整数精确量（`resid≡0`）⇒ 以**门禁几何律**形态落地，**不登记 ledger 锚**"
                      "（否则撞 zero_resid 棘轮被判自证桩）；抽象容量研究不产 GDS",
        "module": "lda_l2.ecore.dmtrack",
        "symbols": ["channel_density", "brute_max_overlap", "sweep_density", "diff_array_density",
                    "left_edge_tracks", "multitrack_route", "dmtrack_self_check",
                    "DMTRACK_DISCLOSURE", "E39_CHANNEL_CAPACITY"],
        "introduced_by": "D-232 (A2/E39)", "guard": "run_ecore_e39_smoke.py",
    },
    {
        "capability": "**B1 标准单元内部几何（晶体管级 · D-233）**：把 E36 的「包围盒 + 0.06µm 有源标记」"
                      "换成**真几何** —— 每颗单元由 DIFF / POLY / CONT / M1 / NWELL 矩形构成，栅（POLY∩DIFF）"
                      "即沟道、源漏 = DIFF 被栅切开的相邻段，PMOS/NMOS 由「沟道是否被 NWELL 完全包住」判定。"
                      "于是三件此前做不到的事第一次有真对象：**① 真实 DRC**（线宽/间距/面积 + 接触孔对 "
                      "DIFF/POLY/M1 的单边包围 + 栅-孔间距 + NWELL 包围）；**② 真实 LVS**（几何抽器件 "
                      "⇄ 期望网表，含**内部节点匹配**：NAND 串联中间节点）；**③ 真实寄生 R**（栅 = poly "
                      "接触→沟道 = Rsh·d/W、源漏 = 扩散方块 + 接触电阻、金属段按长宽比）。"
                      "实测：INV_X1 0.769µm²/2 管 = **0.384 µm²/管**、NAND2_X1 1.470µm²/4 管 = 0.368 µm²/管，"
                      "均**大于**E38c 符号模型 0.266 µm²/管 ⇒ 真实几何比符号模型更贵，为 E38e「加面积是"
                      "唯一有效杠杆」提供定量依据。🔴 **净增 0 锚**（整数几何 + 闭式算术 ⇒ resid≡0，硬做 "
                      "ledger 锚会撞 zero_resid 棘轮）⇒ 以门禁几何律形态落地（E40 · 9 判据 · 反向探针 9 条）。"
                      "⚠️ 诚实边界：规则集是**自建 LDA-DEMO45**（45nm 量级教科书尺度），**非任何 foundry "
                      "PDK 真值**；**不是 SPICE**（只有 W/L + 方块电阻，无 I-V/C/温度/噪声）；"
                      "电流拥挤未建模 ⇒ R 偏乐观；不含 M2 内部走线；不报 TOPS/fJ/能效（未流片）",
        "module": "lda_l2.ecore.dcells",
        "symbols": ["build_inv", "build_nand2", "CELLS", "RULES", "RSH", "R_CONTACT",
                    "diff_segments", "connectivity", "extract_devices", "run_drc",
                    "run_lvs", "extract_r", "gate_r", "cell_self_check", "B1_DISCLOSURE",
                    "PINS_V2_NOTE"],
        "introduced_by": "D-233 (B1)", "guard": "run_ecore_e40_smoke.py",
    },
    {
        "capability": "**B2 完整 detail route（D-234）**：把 E37 `track_route` 的两处结构性简化补上 —— "
                      "① **引脚取自真实单元**（`dcells` 的引脚 pad 接入点；v0.9.349 起为 240×240 pad 中心），"
                      "不是几何中心；② **容量设上界**（行间通道只有 T 条 M3 轨道，"
                      "所需轨道数 d 由 A2 的 `dmtrack.channel_density` 给出、左边界算法分配）⇒ "
                      "**T < d 就是布不通**，而不是「多画几条」。"
                      "实测：4+4 单元交叉网表 d=4 / T=5 ⇒ **4/4 全布通且 DRC 零违规**；"
                      "同一网表用 E37 式「中心点 + 同 y 集中」基线 ⇒ **14 条 min_spacing 违规**"
                      "（E36 报的 baseline DRC 就是这个成因）。T=d-1 ⇒ 布通降到 3/4（容量是硬的）。"
                      "🔴 **净增 0 锚**（整数/闭式 ⇒ resid≡0）⇒ 门禁形态（E41 · 9 判据 · 含 T<d 与塞同轨两条反向探针）。"
                      "⚠️ 诚实边界：两层通道模型（M3 横 / M4 竖 / VIA2），**不是通用迷宫路由器**、无 rip-up、"
                      "不优化线长；单元内 M1→M3 via 串沿用 E37 约定（失效面见 E33）；演示用例 4+4 单元，"
                      "不宣称真实设计布通率；不报面积/能效",
        "module": "lda_l2.ecore.dcroute",
        "symbols": ["build_case", "place_rows", "pin_point", "center_point",
                    "train_tracks", "route", "route_center_baseline",
                    "net_components", "dcroute_self_check", "B2_DISCLOSURE"],
        "introduced_by": "D-234 (B2)", "guard": "run_ecore_e41_smoke.py",
    },
    {
        "capability": "**B3 签核级提取/时序骨架（D-235）**：补上 B1/B2 缺的三件 —— "
                      "① **电容**（平板 `ε₀ε_r·A/h` × 边缘因子，按走线段逐段求和）；"
                      "② **多角**（ff/ss 对 R、C 各乘一套系数 ⇒ 给出延迟**区间**而非单点）；"
                      "③ **IR / EM**（均匀抽流的均匀轨末端压降 `I·R/2`；`J=I/(w·t)` 对 `J_MAX` 判定）。"
                      "每条判据都**两法互证**：电容「逐段求和 ≡ 总长闭式」；Elmore「n 段梯形解 → 闭式 "
                      "`R(C/2+C_load)`」；IR「闭式 ⇄ 离散节点解」；多角**两侧都验**（C 主导区比值 == kr·kc、"
                      "负载主导区比值 == kr）。实测：B2 实布 4 条网提取后三角延迟区间 **31.0–31.4%** 散布"
                      "（tt≈3.16ps / ss≈4.15ps 量级），EM 标称 0.2mA 通过（裕量 1.68×）、0.4mA 必红。"
                      "🔴 **不是 signoff**：一阶解析模型，真实签核还需 foundry ITF/3D 场/SPEF/PVT/EM 规则表/"
                      "硅实测 —— 七项缺口在 `B3_DISCLOSURE.missing_for_real_signoff` 里逐条列出（对外必须同给）。"
                      "⚠️ 多角系数与 `J_MAX` 是**演示量级假设**，非工艺认证；**净增 0 锚**（闭式算术 ⇒ 门禁形态，E42 · 9 判据）",
        "module": "lda_l2.ecore.dsignoff",
        "symbols": ["wire_r", "wire_c", "net_rc", "elmore_closed", "elmore_ladder",
                    "delay_at_corner", "corner_table", "ir_drop_closed", "ir_drop_ladder",
                    "em_check", "CORNERS", "B3_DISCLOSURE"],
        "introduced_by": "D-235 (B3)", "guard": "run_ecore_e42_smoke.py",
    },
    {
        "capability": "**B3+ SPEF 级提取（D-236）**：把寄生从「两个标量 R/C」升级成**分布式 RC 网络**，"
                      "并交出/读回 IEEE 1481-1998 子集。① **提取**：从 B2 真实矩形几何（M3/M4/VIA2）建树 —— "
                      "同一层同一线中心的重叠矩形先按**区间并集去重**（焊盘画在线上，逐矩形求和会重复计面积），"
                      "长段按 seg_um 切分，via 作为电阻接入；② **写出**：`*NAME_MAP`/`*PORTS`/`*D_NET`/`*CONN`/"
                      "`*CAP`/`*RES`；③ **读回**：自解析器还原成网络且**逐位相等**。"
                      "能逐位相等的原因是数值走**整数定点网格**（R 1e-6 Ω、C 1e-6 fF）而非浮点，"
                      "文本 `%d.%0*d` 与整数**十进制双射**，超网格即报错不静默截断。"
                      "量化用**最大余数法** ⇒ 逐项量化之和 ≡ 量化总量（否则 8×312.5mΩ 会得 2496≠2500），"
                      "故网络总量能与 B3 的 `net_rc` 标量口径**逐位对拍**。"
                      "实测：4 网 / 3136 字节 / 227 行 · round-trip 差异 **0** · 与 net_rc 相对差 R 1.3e-7 / C 5.6e-6 · "
                      "单段控制 Elmore 与闭式 `R(C/2+C_load)` 相对差 ≤4.8e-7（n=1,2,4,8,16 逐点）。"
                      "🔴 **无第三方工具回读**：只是格式合规 + 自解析可逆，**不宣称**与商业 STA 流程互通；"
                      "**精度未提升**（仍是 B3 一阶平板+边缘修正）；耦合只算相邻同层平行段；"
                      "**净增 0 锚**（整数定点 ⇒ 门禁形态，E43 · 13 判据 · 含 8 类篡改必红）",
        "module": "lda_l2.ecore.dspef",
        "symbols": ["extract_network", "spef_write", "spef_parse", "elmore_network",
                    "net_totals", "net_decl_total", "net_signature", "compare_networks",
                    "build_wire_network", "q_r", "q_c", "fmt_fixed", "parse_fixed",
                    "SpefError", "SPEF_DISCLOSURE"],
        "introduced_by": "D-236 (B3+/E43)", "guard": "run_ecore_e43_smoke.py",
    },
    {
        "capability": "**B3+ 电源网格全域 IR 求解（D-237）**：把 IR 从「单轨 + 均匀抽流 + 只看末端」"
                      "的一阶闭式 `I·R/2` 升级为**真矩阵解** `G·V = I`。① **建网**：`nx` 列 M4 竖条 × `ny` 行 "
                      "M3 横条 + 每个交叉一个 via，节点分 M3/M4 **两套**由 via 电阻连接（这样 via 电阻真的进方程，"
                      "不被并进金属段）；② **双解法**：自组装电导矩阵 + Dirichlet 边界（numpy 稠密解）⇄ 复用仓内 "
                      "E1 `mna.Circuit`（电阻+电压源+电流源通用 MNA），两者相对差 <1e-14 才算过；"
                      "③ **判据**：KCL 残差、能量守恒、Rayleigh 单调性（via 减半/加第二源必不升）、EM 段电流密度。"
                      "🔴 **最强判据是退化**：网格退化成「单链 + 均匀抽流」时，全域解必须**精确等于** B3 的 "
                      "`ir_drop_ladder = R·I·(n+1)/(2n)`（实测 n=1..64 相对差 ≤9.7e-12），n→大收敛到 `I·R/2`。"
                      "🔴 **可证的假设差异**：同一总电流压在**远端单点**时压降恰为闭式的 **2×**（精确，"
                      "`ratio=1.999999999996`）⇒ 用 `I·R/2` 报点负载工况会**系统性低估一半** —— 这是假设问题，"
                      "不是精度问题。🔴 **反面必须同给**：**不能说「网格压降一定大于闭式」**（8×8 实测只有单轨闭式的 "
                      "0.46×，因 ny 条横条并联），也**不能说「加列数一定降」**（加列同时拉宽网格，nx=8→16 反升 27.8%）"
                      "⇒ 比值只报告不设带宽。实测 16×16（512 节点/736 支路）≈1 s。"
                      "⚠️ 诚实边界：**只解静态 DC**（无 di/dt、无 decap、无封装/板级）、单角 tt、负载为理想电流沉"
                      "（偏低估计 ⇒ 偏保守）、规则网格（不支持非均匀 pitch/阻挡/多源不等压）；**净增 0 锚**（门禁形态，E44 · 12 判据）",
        "module": "lda_l2.ecore.dpgrid",
        "symbols": ["build_grid", "build_ladder", "add_source", "solve_reduced", "solve_mna",
                    "compare_solvers", "uniform_loads", "em_segments", "topology_report",
                    "DPGRID_DISCLOSURE"],
        "introduced_by": "D-237 (B3+/E44)", "guard": "run_ecore_e44_smoke.py",
    },
    {
        "capability": "**B 系列接入 P&R 主链（D-238）**：把 B1/B2/B3 从演示用例接进 E35/E36 主链，"
                      "替换三处结构性简化 —— ① 单元几何从「索引形（0.06µm 有源标记 + 中心焊盘）」换成 "
                      "`dcells` **真几何**（DIFF/POLY/CONT/M1/NWELL）；② 引脚从「塌缩到单元中心」换成 "
                      "**逐引脚真矩形**（INV 的 A/Y、NAND2 的 A/B 各自独立）；③ 布线从「无容量上界」换成 "
                      "**按通道分轨 + 列分配 + `T<d` 即布不通**。另接 B3+ 的分布式 RC 网络提取与网格 IR。"
                      "🔴 **顺带查出两个真缺陷**：① `VIA_BRIDGE` 缺 **M2–M3 通孔**（原表只有 M1-M2 / M3-M4）"
                      "⇒ 单元引脚（M1）在几何上根本到不了 M3 —— 本版补 **V2（层 26）**；"
                      "② `dcells` **引脚不可做 pin access**（M1 引脚矩形仅 65nm 高，装不下 200nm 孔 + 20nm 包围；"
                      "相邻引脚 INV A-Y 0.2716µm / NAND2 A-B 0.2228µm < 两条 M4 需的 0.36µm）。"
                      "实测（12 单元 / 4 列 / 同网表同布局）：路由 DRC **34 → 14（2.43×）**，"
                      "连通性 **100%**（无断网），容量律无越界，提取 10 网全 `R>0∧C>0`。"
                      "🔴 v0.9.348 **不宣称零 DRC**：残差 14 条全部落在引脚邻近的 M3 间距/孔包围，"
                      "归因是**单元引脚几何**而非路由算法 ⇒ 修法在单元版图（引脚重画）。"
                      "✅ **v0.9.349 已收口（引脚可接入化）**：`dcells` 信号引脚改成 **240×240 pad**，"
                      "接入点落在库级列网格 120/480/840nm（两两恰一个 pitch）；同时修掉路由器两个真缺陷"
                      "（trunk 着色改按「引脚 ∪ 列」真实跨度、通道数改成 == 行数）⇒ 路由 DRC **34 → 0**、"
                      "全量 DRC **0**、10/10 网布通、每网 1 连通分量、列失败 0。"
                      "🔴 **零 DRC 只对这一个用例成立**（12 单元 / 4 列 / INV+NAND2 / LDA-DEMO45），"
                      "换单元类型（DFF 未建模）、列数、通道高度都要重测。"
                      "⚠️ 子块接入非全 IP（dcells 仅 INV/NAND2，DFF 跳过并计数；DRC 为 O(n²) 规模受限）；"
                      "非通用路由器（每网单 trunk 星形，无 maze/rip-up）；M2 只画焊盘；行高取 max 底对齐；"
                      "单元间距 0.46µm（=1.44−0.98，为轨道间距整数倍）换 pin 可达性；"
                      "只布内部网（端口网如实计入未布）；**净增 0 锚**（E45 · 12 判据）"
                      "✅ **v0.9.351（E48 · D-240）M2 逃逸走线**：把「引脚 → 列」的横向偏移交给 **M2**"
                      "（M1 pad --VIA1--> M2 横条 --> V2 --> M3），于是 M3 侧永远落在列网格上、"
                      "**M3 跳线 8→0**、**trunk 总长 −22.6%**（trunk 只覆盖列）。"
                      "🔴 但「把间距从 0.46 收回到 0.36 以赚回 ≈8% 面积」这个假设**被证伪**："
                      "gap 0.36 时路由层 DRC 归零（4→0），却在 **M2 层**出 4 条 —— 同 y 两引脚"
                      "（NAND2 的 A/B）净空只有 `P − pad = 0.12µm`，扣 S_MIN 后**内向逃逸总量仅 0.02µm**；"
                      "外向逃逸又在单元边界撞上。⇒ **0.46µm 不是保守取值，是必要代价**"
                      "（扫描 0.36/0.40/0.44 恒 4 条，≥0.46 才为 0）。要真正回收只能把同 y 引脚的 y 带分开，"
                      "而 NAND2 的 gap 需 660nm > 现有 520nm ⇒ +140nm（面积 +9.3%）> 省下的 8% ⇒ **不做**。",
        "module": "lda_l2.ecore.dpnr",
        "symbols": ["place_real", "cell_shapes", "pin_points", "pin_access_points",
                    "pin_legality", "pin_access_conflicts", "pin_stub", "net_pins",
                    "route_block", "net_coverage", "pins_for_lvs", "lvs_scoped", "LVS_ADAPTER_NOTE", "route_baseline",
                    "cell_drc_lvs", "routing_only", "access_only", "all_routing",
                    "net_components_rt", "CELL_GAP_UM", "CELL_GAP_TIGHT_UM", "M2_JOG_MAX",
                    "DPNR_DISCLOSURE"],
        "introduced_by": "D-238 (B-series → P&R)", "guard": "run_ecore_e45_smoke.py",
    },
    {
        "capability": "**多角（PVT）互连线延迟窗口（D-239）**：把主链的「单角 tt 单点」升级为 "
                      "**min/typ/max 窗口**。核心是**一个定理 + 一个刻意的破例**："
                      "① 纯 RC 树 + 统一缩放时 `τ_corner = kr·kc·τ_tt` **精确成立** ⇒ 只有片电阻的模型，"
                      "多角窗口退化成**单一标量**，各网宽度完全相同（这种「多角」是空转的，判据 D4 用 "
                      "`kv:=kr` 精确复现该退化）；② 让窗口有结构的必须是**不跟片电阻同角**的量 —— "
                      "本模型取**通孔电阻**：`τ_k = kr_k·kc_k·τ_metal + kv_k·kc_k·τ_via`，两项之比随网自身"
                      "构成变化 ⇒ 每网窗口不同（实测 **1.9134× .. 1.9646×**，判据 D5 守「确有差异」）。"
                      "实测（E45 那条主链的 12 单元块 / 10 网）：延迟 **0.0818 .. 3.1627 fs**（网间 38.65×）、"
                      "**通孔电阻贡献 79.2%–93.9%**（本块尺度下延迟由通孔主导，片电阻只占 6%–21%）、"
                      "拆分加法闭合残差 **4.4e-16 fs**、tt 角与 v0.9.349 既有 `elmore_network` 逐位一致、"
                      "窗口全部落在**闭式界** [1.6536, 1.9861]（全金属界 … 全通孔界，由角因子直接推出）。"
                      "🔴 **只做互连线**：不含标准单元/器件角 ⇒ **不是**「路径延迟窗口」；"
                      "**不是 OCV/AOCV/POCV**（无 derating、无统计变异、无 clock）；角因子（含 "
                      "`VIA_CORNERS` 比片电阻更宽这一点）是**演示假设**，非任何 foundry PVT 数据；"
                      "一阶 Elmore（无 RLC / 无串扰时延 / 无 R(T)）。**净增 0 锚**（E47 · 12 判据）",
        "module": "lda_l2.ecore.dpvt",
        "symbols": ["CORNERS", "VIA_CORNERS", "CORNER_ORDER", "VIA_EDGE_R",
                    "split_tau", "corner_tau", "net_window", "block_window",
                    "theorem_check", "DPVT_DISCLOSURE"],
        "introduced_by": "D-239 (PVT corners)", "guard": "run_ecore_e47_smoke.py",
    },
    {
        "capability": "**规模上探与复杂度界（D-241）**：把「这套链路能用到多大规模」变成可引用的数。"
                      "12…1024 单元阶梯实测：**全档路由 DRC 恒 0**，但代价如实变成「布不通」——"
                      "列失败率 **0% → 51.3%**（单调不降）。"
                      "🔴 **上限来自布线资源，不是算法**：M4 列数由 **die 宽度**决定、与行数无关 "
                      "⇒ 行数一多列必然枯竭；扩规模必须等比加宽 die（与 E38 链「唯一杠杆是加面积」同向）。"
                      "**时间界**：DRC 占绝对主导（1024 单元 **96.2%**），`t_drc ∝ M^1.96`（R²=0.9999）"
                      "与逐对 O(M²) 一致；按该幂律外推 1 万单元 DRC ≈ **130 s（上界，纯 Python 单核）**。"
                      "🔴 **查出并修掉两个真缺陷**：① 列被推远超过 M2 逃逸上限后，旧代码退回 **M3 长跳线**，"
                      "而跳线只能画在**引脚 y** 上 ⇒ 同行同 y 的跳线全叠死（64 单元实测 **41 条**）；"
                      "修成把逃逸上限当**硬约束**，超出如实报 `too_far`/`no_column`。"
                      "② 逐引脚逃逸额度必须**按方向**算（向左只受左邻约束），且判邻必须按 "
                      "**y 区间重叠**（`round(y,2)` 分带会把 INV 535nm 与 NAND2 530nm 错开 ⇒ 漏 2 条）。"
                      "🔴 外推是**上界不是点估计**（`metals/cells` 随规模下降 ⇒ 系统性高估，实测 +85%）；"
                      "**布通率不外推**。**净增 0 锚**（E49 · 10 判据）",
        "module": "lda_l2.ecore.dscale",
        "symbols": ["LADDER", "COLS", "probe", "size_ladder", "fit_exponent",
                    "complexity", "extrapolate", "failure_breakdown", "monotonic",
                    "DSCALE_DISCLOSURE"],
        "introduced_by": "D-241 (scale ladder)", "guard": "run_ecore_e49_smoke.py",
    },
    {
        "capability": "**宽度/通道二维权衡（D-242）**：E49 说「扩规模必须等比加宽 die」，"
                      "本模块把它做二维扫描量化，结论是那句话**不完整**："
                      "① **加宽 die 单独做是负收益** —— CH=1.60（T=4）下 cols 4→32 布通率 "
                      "**51.3% → 0.0%**；机制是 cols 增大 ⇒ rows 减小 ⇒ **通道数减少**"
                      "（每行上方一条），T 不变 ⇒ 通道容量律先崩。⇒ 必须**同时加高通道**。"
                      "② **最优点真实存在且布通率对 cols 单峰**（4 个 CH 切片全单峰）："
                      "256 单元在 cols≈24 / CH=3.40 达 **87.3%**（默认 56.9%），面积 **+71%**；"
                      "峰值随 CH 单调抬升 56.9%→73.0%→85.8%→87.3%，最优 cols 随之上移 8→16→20→24。"
                      "越过最优点必崩（cols=32 时通道只剩 8 条、4 个通道超容量覆盖 124 网 ⇒ 43%）。"
                      "③ **证伪「候选列不够」**：`M2_JOG_MAX` 0.72→2.16（每引脚候选列 **5→13**，2.6×）"
                      "只多布通 **2 个网** ⇒ 剩余 ~13% 的真根因是**每网独占一条跨行 M4 竖线**"
                      "（星形拓扑），出路是**加层 M5** 或**行内局部布线**，不是继续加宽。"
                      "面积代价（Pareto）：85% 档需 **1691 µm²（+47%）**。"
                      "🔴 依赖「通道数 == 行数」这条实现约定，真实设计不可直接外推；"
                      "最优点随规模漂移（64/128/256 单元实测 cols≈20/24/24）不是常数。"
                      "**净增 0 锚**（E50 · 10 判据）",
        "module": "lda_l2.ecore.dwidth",
        "symbols": ["COLS_GRID", "CH_GRID", "CASE_CELLS", "tracks_for", "probe_config",
                    "width_sweep", "slice_at", "best_of", "is_unimodal",
                    "monotonically_non_increasing", "pareto", "min_area_for",
                    "jog_probe", "DWIDTH_DISCLOSURE"],
        "introduced_by": "D-242 (width/channel trade-off)", "guard": "run_ecore_e50_smoke.py",
    },
    {
        "capability": "**行内局部布线可行性判定（D-243）** —— **负结果**：E50 的 87% 卡在"
                      "「每网独占一条跨行 M4 竖线」，本文去验最直接的出路「让网在行内互联」"
                      "（动机很强：**60–80% 的内部网全引脚同行**，256 单元 cols=8 时 61%、cols=24 时 79%）。"
                      "**三个独立证据表明这条路走不通**："
                      "① 行内 M3 水平段**必撞**同行异网 pad —— 布通 **+0 网**、DRC 从 **0 爆到 786 条**"
                      "（cols=16 时 288、cols=8 时 70）；"
                      "② 行内 M2 **没空间**（闭式）：INV 最大空隙 **345nm**、NAND2 **410nm**，"
                      "而一条 M2 走线需 `W+S_MIN=340nm` ⇒ **最多 1 条轨道**，INV 余量只剩 **5nm**；"
                      "③ 列分配迭代**零收益**（iters 1/2/3 布通 233/233/233、no_column 34/34/34）"
                      "⇒ 冲突不是来自 y 区间长度，而是「同行引脚 y **必然重叠**」。"
                      "🔴 并给出 **87% 的结构解释**：加宽 die 让「列数」与「每行引脚数」**同比例**增长，"
                      "实测**供给/需求比恒定 1.33–1.43** ⇒ `no_column` 从 89 降到 34 却**永不归零**；"
                      "通道从 CH=3.40 加到 6.00（**T 9→17**）布通率**一动不动 87.3%**、通道一个不满 ⇒ "
                      "瓶颈只剩列。⇒ **唯一能突破的杠杆是加一层垂直层（M5）**：分子（列）可翻倍、分母不变。"
                      "🔴 渐近线依赖本实现的**星形拓扑**，换 Steiner/多干后会变，**不是能力上限**；"
                      "**不是**说「行内布线在真实设计里也不行」（真实 std-cell 的 pin access 由单元库自带 M2 绕行）。"
                      "**净增 0 锚**（E51 · 10 判据）",
        "module": "lda_l2.ecore.dinrow",
        "symbols": ["CASE_CELLS", "COLS_GRID", "CH_GRID", "ITER_GRID", "row_gaps",
                    "net_row_span", "in_row_probe", "col_iter_probe",
                    "channel_saturation", "supply_demand", "DINROW_DISCLOSURE"],
        "introduced_by": "D-243 (in-row feasibility)", "guard": "run_ecore_e51_smoke.py",
    },
    {
        "capability": "**工艺节点参数化（D-244）**：把「节点」变成可替换参数集（器件缩放与金属规则**分离**），"
                      "派生「行内可用轨道数」这个关键量。**回答「成熟 EDA 肯定做得到布通」这个质疑：成立** ——"
                      "E45–E51 的 87% 不是物理极限，而是把一套 **0.35µm 级规则写死**的结果："
                      "`W=240/S=100/VIA=200/ENC=20/行高1500nm` ⇒ 引脚 pad 必须 **240×240nm**（VIA+2·ENC 的必然），"
                      "而 pad 是**行内资源的头号消费者** —— 它把行内空闲带压到 **2 条** 340nm 节距轨道，"
                      "而 **pin access 正好用掉这 2 条** ⇒ M2 不能做布线层（实测：直接用它布线 DRC **0→65 条**）"
                      "⇒ 只剩 **M4 一层竖直** ⇒ 列供给/需求比恒 1.33–1.43 ⇒ **87% 渐近线**。"
                      "换 DEMO28（pad **70nm**）：行内 **5 条**，扣 pin access 剩 **3 条** ⇒ 行内布线可行 "
                      "⇒ 每网只需 1 条锚列 ⇒ **列需求 0.512×**（同行网 78.7%、平均 2.63 引脚）。"
                      "🔴 **关键反例：等比缩规则无效** —— pad/节距/行高**同比**缩 0.6，轨道数**仍是 2**"
                      "（比值不变）；只有「金属规则比器件缩得更快」才腾出空间，这正是真实工艺演进的形态。"
                      "🔴 **本模块不做布通率实测宣称**：0.512× 是几何下界；"
                      "要把它变成实测需**重做 HD 单元库**（pad 70nm + M1 strap 重画 + DRC/LVS 归零），"
                      "那是独立里程碑。两个节点都是**教科书尺度参数，非 any foundry PDK**。"
                      "**净增 0 锚**（E52 · 9 判据）",
        "module": "lda_l2.ecore.dnode",
        "symbols": ["NM", "Node", "DEMO45", "DEMO28", "NODES", "DEFAULT_NODE", "get",
                    "compare", "inner_tracks_for", "capacity_projection", "NODE_DISCLOSURE"],
        "introduced_by": "D-244 (node parametrization)", "guard": "run_ecore_e52_smoke.py",
    },
    {
        "capability": "**HD 标准单元库（D-245）**：按 28nm 级规则（LDA-DEMO28）重画 INV/NAND2，"
                      "把 E52 的**几何下界**变成可布线实体。三处关键差别，全部由规则派生而非手抄："
                      "① 引脚 pad **240 → 70nm**（= `VIA 50 + 2·ENC 10`，同样是**必然**不是选美）；"
                      "② 栅接触**不再需要 poly 焊盘**（`cont 20 + 2×enc 5 = 30 = poly_w`，恰好放得下）；"
                      "③ **两单元等高 1000nm** ⇒ 消除 E45 披露里的「行高取 max、INV 上方留空行」限制。"
                      "实测：DRC/LVS 双零；面积 INV **2.75×** / NAND2 **3.42×** 更小"
                      "（0.7688→0.2800、1.4700→0.4300 µm²）；每管面积 0.3844/0.3675 → 0.1400/0.1075；"
                      "行内可用水平轨道 **5 条**，且**两单元轨道 y 完全一致**（70/410/550/780/920nm）"
                      "⇒ 库级共用轨道网格，行内线可跨单元连通；DEMO45 的 INV 只有 **1 条**。"
                      "🔴 **规则参数化是参数不是常量**：`dcells.run_drc(cell, rules=...)` 用**同一份检查器**"
                      "查不同节点的单元（同一块 HD 单元换 45nm 规则立刻报 **22 条**，换规则真的会翻面）；"
                      "反方向（45nm 单元过 28nm 规则）**本应为 0**，那是性质不是缺陷。"
                      "🔴 规则集是**自建教科书尺度**，非 foundry PDK；器件电学不变（只有 W/L 与方块电阻）"
                      "⇒ 与 DEMO45 之间**只能比几何容量**，不可比延迟/功耗；只有 INV/NAND2（DFF 未建模）；"
                      "无 M2 内部绕行/多高度引脚/dummy/well-tap。**净增 0 锚**（E53 · 11 判据）",
        "module": "lda_l2.ecore.dhdlib",
        "symbols": ["HD_RULES", "HD_ROUTE", "H_ROW_HD", "RAIL_HD", "W_DEV_HD", "L_GATE_HD",
                    "pad_nm", "build_inv_hd", "build_nand2_hd", "CELLS", "CELL_MAP",
                    "pin_bands", "inner_tracks", "lib_summary", "run_drc",
                    "HD_DISCLOSURE"],
        "introduced_by": "D-245 (HD cell library)", "guard": "run_ecore_e53_smoke.py",
    },
    {
        "capability": "**工艺规则运行期切换（D-245）**：`use(node)` 在**一个上下文内**把布线/DRC 规则"
                      "（`PITCH/W/EXT/PAD_HALF/M2_HALF/S_MIN/ENC/W_MIN/VIA/TRACK_PITCH/CH/CELL_GAP`"
                      "以及单元库与 `CELL_MAP`）整体切到指定节点，退出时**逐项还原**（13 项逐位一致）。"
                      "🔴 **为什么不是再造一套 HD 布线器**：两份实现必然漂移（`dnode.tracks_for` 自己重算 `T` "
                      "已经踩过一次）⇒ 只做「参数切换」，**算法一份**。默认不进入 ⇒ 现有门禁读到原值、"
                      "行为逐位不变。🔴 运行期可变状态、**非线程安全**（本仓门禁单进程串行）；"
                      "只切规则数值、不提高算法能力；不切器件电学。**净增 0 锚**（E53 · 11 判据）",
        "module": "lda_l2.ecore.dproc",
        "symbols": ["TOUCHED", "snapshot", "diff", "use", "DPROC_DISCLOSURE"],
        "introduced_by": "D-245 (proc switch)", "guard": "run_ecore_e53_smoke.py",
    },
    {
        "capability": "**DFF 进 HD 库（D-246）**：库里唯一的**时序单元**，22T = 11 列 ×（1 PMOS + 1 NMOS），"
                      "TG 主从 + 输出缓冲，**正沿触发**，输出 Q/QN。这是「按规则生成单元」这条路的真正验收 ——"
                      "器件数是 INV 的 11 倍、大半栅网是**内部无名节点**。"
                      "**为画它必须先补两处基础能力**：① `dcells` 的跨层桥接从「只有 CONT 硬编码」改成**表驱动**"
                      "（`_VIA_BRIDGE`: CONT→DIFF/POLY/M1、VIA1→M1/M2、V2→M2/M3），否则单元里一放 M2 走线，"
                      "LVS 就看不到连通（实测：每个器件第二个端子都成独立无名网）；"
                      "② DRC 增加 M2/M3 的宽/间距（`m2_w/m2_s/m3_w/m3_s`）。"
                      "**版图三处关键设计**：M1 只做水平总线（13 网共享 8 条电平，同电平 x 不相交，判据 J4 机核）、"
                      "M2 只做竖直跨层（正交两层，交叉不必让步）、TG 的 P/N 栅**断成两条 poly**（互补控制，"
                      "占空比 430..505nm），互补时钟拆成低段+高段并用 M2 竖链跨接（P 栅接触只能落上半区、"
                      "N 栅只能落下半区）。"
                      "实测：**DRC 0 / 双射 LVS 0**（22 器件 / 13 网）、面积 **2.5000 µm² = 8.93× INV**、"
                      "等高 1000nm、行内可用轨道 **3 条**（4 个引脚吃掉更多空隙）、功能**开关级 16 拍逐拍**"
                      "与理想正沿 DFF 一致且「非沿不跟随」。"
                      "🔴 **22T ≠ 抽象模型 24T**（`dcell.DFF.n_tr`）⇒ 面积按实测几何报，不套抽象模型。"
                      "🔴 **无 SPICE**：功能证据只到开关级，不含时序/噪声/亚稳态。"
                      "🔴 **单元内部用了 M2**，而布线器只认引脚 ⇒ **本版不接入布线**（接之前必须先把单元内部"
                      "图形纳入 DRC，否则是盲区）。规则集 LDA-DEMO28 非 foundry PDK。"
                      "**净增 0 锚**（E54 · 10 判据）",
        "module": "lda_l2.ecore.dhdlib",
        "symbols": ["DFF_PITCH", "DFF_NCOL", "DFF_LEVELS", "DFF_COLS", "DFF_BUS",
                    "DFF_LINKS", "build_dff_hd", "run_lvs_pos"],
        "introduced_by": "D-246 (DFF in HD lib)", "guard": "run_ecore_e54_smoke.py",
    },
    {
        "capability": "**E55 单元内部图形接入 DRC（D-247）**：把「哪块图形属于哪个网」从"
                      "**几何连通性**（结果）里拆出来，单独记成**网标签**（设计意图）—— "
                      "`dcells.label_cell` 给每块形状定名（引脚分量用真引脚名、其余按几何稳定编号 `#k`），"
                      "`compose` 把多颗单元/走线**拼成一个 Cell**，于是联合场景原样复用**同一份** "
                      "`run_drc`（不造第二套检查器，E53/E54 的教训）。"
                      "🔴 **修的是判据方向**：旧口径「几何并成同一分量 ⇒ 视为同网 ⇒ 跳过间距」会让"
                      "**短路被当成同网**而静默通过；新口径标签不同即按异网查 ⇒ 必报。"
                      "实测三处旧口径静默现已必红：两单元**完全重合**（conflicts 10 条，旧 DRC=0）、"
                      "**跨行错位**（DRC 4 + 短路 1）、**走线穿过单元内部**（DRC 5）。"
                      "🔴 另修一处真缺陷：`diff_seg` 的跳过条件原按 `role` 字符串相等，"
                      "而 role 只写 y 区间不写父有源 ⇒ 拼接后**不同实例的两段必然同名**，"
                      "跨单元异网有源相接被静默跳过；改为**物理判据**（间隙是否被栅完全覆盖）。"
                      "🔴 补层：`_VIA_BRIDGE` 原止于 M3 ⇒ 走线在联合图上没有连通性"
                      "（8 单元 `n_unrouted` 7→56）；补 VIA2/M4 后 **unrouted=0**，"
                      "这是「走线真的接到引脚」的机核证据。"
                      "实测：8 单元真实布局 + `route_block` 走线联合签核 **DRC 0 / 短路 0 / 待布线 0**；"
                      "abutment 下界 = M1 最小间距 **30nm**（可推可测单调）；abutment 后"
                      "**合成电路双射 LVS 仍通过**（拼起来电路还对），带缝则如实报开路。"
                      "🔴 边界：只做几何间距/短路，无串扰/天线/密度/OPC/ESD；LDA-DEMO28/45 非 foundry PDK；"
                      "`ddetail.L_V2=26` 与真源（26=PAD、28=M2↔M3）存在历史双口径，本版不动单元几何。"
                      "**净增 0 锚**（E55 · 21 判据）",
        "module": "lda_l2.ecore.dcnet",
        "symbols": ["to_nm", "from_nm", "route_tile", "pin_shapes", "obstacles",
                    "place_tiles", "joint_drc", "row_of"],
        "introduced_by": "D-247 (cell-internal DRC)", "guard": "run_ecore_e55_smoke.py",
    },
    {
        "capability": "S2 Liberty 子集解析器（D-248 · B2/S2）：把公开 PDK 的 .lib 读进来，让 S1 统一数据模型（model.py）的 Pin.direction / TimingArc 有往哪儿填的来源。递归下降解析 + 保序 OrderedDict + 括号内容逐字符保留（args_raw/raw）⇒ parse→serialize→re-parse 逐位相等（连 NLDM 矩阵行列数都不差），不靠归一化偷偷变形。未知语法必报错、绝不静默跳过：define/type/group/library_domain 等宏与类型定义指令、表达式值 area:(2*3)、顶层非 library 组、未闭合组、非法字符 —— 一律抛 LibertySyntaxError（带行号）。零数据丢失不变量：rich 样本 parse 后 cell/pin/timing/attr 计数往返完全守恒。to_model() 把 direction/极性/capacitance pf→ff/NLDM 表（load pf→ff、slew/delay ns→ps，矩阵按 S1 约定 delays[slew][load] 转置）喂给 S1 的 Pin/TimingArc。不求值不建模（那会是第二套实现、与既有模块漂移）；几何在 LEF(S3)；非 foundry PDK（自带按公开单元库惯例构造的 SAMPLE_LIBERTY）；C 级自主纯标准库、LLM 不进判决路径。",
        "module": "lda_l2.ecore.dliberty",
        "symbols": ["LibertySyntaxError", "LibertyValue", "LibertyGroup", "LibertyLibrary",
                    "parse_liberty", "parse_liberty_file", "serialize_liberty", "to_model",
                    "SAMPLE_LIBERTY", "LIBERTY_DISCLOSURE"],
        "introduced_by": "D-248 (S2)",
        "guard": "run_ecore_s2_smoke.py",
    },
    {
        "capability": "S3 LEF 子集解析器（B2/S3 · 几何落地）：把公开 PDK 的 .lef 库几何（MACRO 的 PORT/OBS 矩形、SIZE）逐字段读进 S1 统一模型 CellView（尺寸 DATABASE MICRONS 换算成 nm 整数）。递归下降 + 括号内容逐字符保留（args_raw/raw）⇒ parse→serialize→re-parse 字节级往返双射 + 幂等；零数据丢失不变量（2 macro/5 pin/6 rect/9 顶层语句守恒）；未知语法必报错（未闭合块/顶层非LIBRARY END/语句缺;/END名错配/RECT参数量错或反向/SIZE格式错 带行号）；to_model 精确几何反向探针。不求值不建模；DEF(S3后半)引用本模块 MACRO 名；OpenROAD 仅可选读回不当 golden；非 foundry PDK；C 级自主纯标准库、LLM 不进判决路径。",
        "module": "lda_l2.ecore.dlef",
        "symbols": ["DLEF_DISCLOSURE", "LefItem", "LefLibrary", "LefSyntaxError",
                    "SAMPLE_LEF", "parse_lef", "parse_lef_file", "serialize_lef", "to_model"],
        "introduced_by": "S3 LEF",
        "guard": "run_ecore_s3_smoke.py",
    },
    {
        "capability": "S4 结构级 Verilog 子集解析器（B2/S3 · 门级网表入口）：把 ISCAS/EPFL 这类已综合好的结构网表（nand g(y,a,b) 门实例）读进 dsynth.Netlist（与 drtl RTL 子集分工，汇合点同为 dsynth.Netlist），让 B3 干线 place→route→drc 能直接吃上一段输出。字节级往返双射（门按名排序吐回）+ 幂等；零数据丢失不变量（门实例/网名集合守恒）；未知语法必报错（未闭合/非法原语/升序向量/输出当输入/缺; 带位置）；多比特端口拆位（LSB first）+ 位选门引用；to_model→S1 Layout（坐标留 0，几何在布局阶段）；PHYSICALLY_MODELED={INV,NAND2}（其余原语物理链诚实跳过）。不综合不求值；非 foundry PDK；C 级自主纯标准库、LLM 不进判决路径。",
        "module": "lda_l2.ecore.dverilog",
        "symbols": ["PHYSICALLY_MODELED", "SAMPLE_VERILOG", "VerilogSyntaxError",
                    "parse", "serialize", "to_model", "to_netlist"],
        "introduced_by": "S3 Verilog",
        "guard": "run_ecore_s4_smoke.py",
    },
    {
        "capability": "S5 DEF 子集解析器（B2/S3 · 布局布线结果）：把引用 LEF MACRO 名的「一次具体布局布线」结果（DESIGN/COMPONENTS 落点/NETS 走线）读进 S1 Layout。递归下降解析 + canonical 重写 ⇒ 字节级往返双射（实例/网按名排序）+ 幂等；零数据丢失不变量（实例/网/终端/落点守恒）；未知语法必报错（未闭合/缺朝向/未声明MACRO/坐标错 带位置）；to_model 需 LEF 库解析 MACRO 真实 w/h 与端口几何。OpenROAD 仅可选读回不当 golden；非 foundry PDK；C 级自主纯标准库、LLM 不进判决路径。",
        "module": "lda_l2.ecore.ddef",
        "symbols": ["DDEF_DISCLOSURE", "DefDesign", "DefSyntaxError",
                    "SAMPLE_DEF", "parse_def", "parse_def_file", "serialize_def", "to_model",
                    "from_placement", "DEF_DBUNIT_PER_UM", "DEF_OUT_PIN"],
        "introduced_by": "S3 DEF",
        "guard": "run_ecore_s5_smoke.py",
    },
    {
        "capability": "B3 数字链干线（S3→B3）：把 S3 结构级 Verilog 子集直接喂进现状数字链 dverilog.parse→dsynth.Netlist→dplac.place→ddetail.detail_route→ddrc_lvs，跑通 ISCAS-85 c17，并每段显式断言「吃的是上一段的输出」（place 覆盖每颗门 / route 覆盖每条网 / drc-lvs 如实报告 claimable=False 不伪造 clean）。fail-closed：空输入直接报错；ddetail 路由器 claimable=False 为已知诚实边界（c17 实测 **DRC 87 处间距违规** "
            "＋ **LVS 183 条短路条目（78 short + 105 short_via，去重 43 对网）** —— 弯角孔包围于 v0.9.370 修至 0，余下全是**容量不足**：通道 2 轨 < 需求 7、单元宽 0.067µm 而单引脚槽需 0.96µm、17 条引脚访问列需 6.12µm > die 1.09µm，见 `ddetail.drc_capacity_bound` 与 `/api/digital_demo` 的 `capacity` 段）；几何/时序为模型假设；非 foundry PDK；C 级自主纯标准库、LLM 不进判决路径。",
        "module": "lda_l2.ecore.db3_trunk",
        "symbols": ["run_trunk", "run_trunk_from_verilog", "claimability", "CLAIMABLE_CONDITIONS"],
        "introduced_by": "B3 trunk",
        "guard": "run_ecore_s6_smoke.py",
    },
    {
        "capability": "B4 对拍框架（差分差异表）：逐项产出「metric / lda / reference / golden / baseline_used / delta / band / exceeds / attribution / evidence_level」。覆盖面积（闭式 Σ 单元面积）、线长（闭式中心矩 HPWL）、WNS（target 周期 − t_clk_min；纯组合无时钟域则三态 null）。🔴 三条纪律：① `exceeds` **三态** true/false/null，无基线一律 null（禁压扁成 false）；② 每行归因必须在**闭式词表**内且非空，禁用「参考工具如此」式借口（P5，判决权不进外部工具）；③ 外部参考只经**独立进程 + 文本**（P3）、只作 candidate 不作 golden（P1）。输出无时间戳/路径/版本、浮点 round 6、sort_keys ⇒ 两次构建字节一致（sha256 digest 机核，跨进程 × 不同 PYTHONHASHSEED 亦一致）。参考工具缺席时降级为 SELF_CONSISTENCY_ONLY，绝不冒充外部对拍；claimable=False。",
        "module": "lda_l2.ecore.dxcheck",
        "symbols": ["DXCHECK_DISCLOSURE", "ATTRIBUTION_CODES", "CrossCheckError",
                    "Band", "build_diff_table", "validate_table", "serialize", "digest",
                    "golden_area_um2", "golden_hpwl_center_um", "probe_reference",
                    "run_reference_text", "parse_openroad_area_text",
                    "parse_opensta_wns_text", "xcheck", "sample_seq_netlist"],
        "introduced_by": "S4 B4",
        "guard": "run_ecore_s7_smoke.py",
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
    "route": "电子计算征程 E5 · 平台能力硬化（ecore 能力清单 + 常驻守护门禁）· E10 收官扩面至 e1~e10 · E11-c 扩面至 e1~e11 · E12 扩面至 e1~e12 · E18 扩面至 e1~e18 · E19 扩面至 e1~e19 · E20 扩面至 e1~e20 · E21 扩面至 e1~e21 · E22 扩面至 e1~e22 · E23 扩面至 e1~e23 · E24 扩面至 e1~e24 · E25 扩面至 e1~e25 · E26 扩面至 e1~e26 · E27 扩面至 e1~e27 · E28 扩面至 e1~e28 · E29 扩面至 e1~e29 · E30 扩面至 e1~e30 · E31 扩面至 e1~e31 · E32 扩面至 e1~e32 · E33 扩面至 e1~e33 · E35 扩面至 e1~e35 · E36 扩面至 e1~e36（D-220~D-223：detail route / 真实单元几何 / IP DRC / IP LVS）· E37 扩面至 e1~e37（D-224：DRC/LVS 校验器硬化 fast≡native + track 分配/拥堵负结果）· E38a 扩面至 e1~e38（D-225：网格迷宫路由器 + 可布通性诚实布通率）· E38b 扩面至 e1~e38（D-226：多轮 R&R + 密度曲线 + 多层对比）· E38c 扩面至 e1~e38（D-227：真实标准单元面积标定）· E38d 扩面至 e1~e38（D-228：细引脚接入逃逸 + 现实线距联调）· E38e 扩面至 e1~e38（D-229：摊开 ×K 可测边界 + 失败模式诊断，修正 E38d 根因为墙效应）· E38f 扩面至 e1~e38（D-230：破墙路由器三策略 + 原子多阻塞者 R&R，实测零和）",
    "e5_scope": "把 E1~E9 逼出的平台能力固化为机器可读清单（单向真源）+ 常驻门禁（正向完备 + 反向完备 + 披露一致 + 诚实边界）",
    "hardening_semantics": "能力面必须被门禁守着：任一模模块/符号缺失、隐身模块出现、或注入 fabricated 指标 ⇒ 门禁必红",
    "redline": "红线 = 分层口径（器件级 T1 内核已解锁 · T2 工艺真值/工艺角/流片永久锁）；"
               "**本包主动限定在电路级**；C 级自主（纯 numpy/标准库）；LLM 不进判决路径",
}
