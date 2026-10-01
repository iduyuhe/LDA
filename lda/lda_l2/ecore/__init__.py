# -*- coding: utf-8 -*-
"""LDA · 电子计算征程（E1…Ex）核心包 ecore（electronic compute core）。

路线：模拟电子计算核（MVM 交叉阵列）——电子版的「光子 MZI 网格」。
E1 基座：晶体管级模型（mosfet）+ MNA 电路仿真器（mna）+ 最小模拟计算单元（analog_mvm）。
"""
from __future__ import annotations

from .analog_mvm import (
    inverting_summer,
    inverting_summer_golden,
    mosfet_saturation_bias,
    mosfet_saturation_golden,
)
from .crossbar_mvm import (
    CROSSBAR_DISCLOSURE,
    CrossbarMVM,
    build_ota_circuit,
    ota_open_loop_gain,
)
from .capability_manifest import (
    ECORE_CAPABILITY_DISCLOSURE,
    ECORE_CAPABILITY_MANIFEST,
    ecore_module_names,
    manifest_check,
)
from .mna import Circuit
from .mvm_datapath import (
    MVM_DATAPATH_DISCLOSURE,
    AnalogMvmUnit,
    MvmDatapath,
    mvm_datapath_self_check,
    quantize_uniform,
    relu,
    tiled_mvm,
)
from .scale_bench import (
    LANDMARKS,
    LDA_CAPABILITIES,
    NON_CLAIMED,
    SCALE_BENCH_DISCLOSURE,
    honest_boundary_ok,
    honest_comparison,
    scale_bench_self_check,
    scale_sweep,
)
from .mosfet import (
    MOSFET_DISCLOSURE,
    NmosParams,
    id_gm_gds,
    id_saturation_closed,
    mosfet_self_check,
    vdsat,
)
from .elayers import (
    DEFAULT_CMOS_STACK,
    ELEC_DESIGN_RULES,
    ELEC_DISCLOSURE,
    ELayer,
    ELayerStack,
    get_estack,
)
from .layout import (
    EDRC_RULES,
    LAYOUT_DISCLOSURE,
    array_footprint,
    crossbar_array,
    crosspoint_cell,
    elvs_signoff,
    expected_netlist,
    extract_wl,
    gds_roundtrip_check,
    layout_svg,
    run_edrc,
    to_gds,
)
from .parasitic import (
    ELEC_PROCESS,
    PARASITIC_DISCLOSURE,
    array_parasitics,
    build_network,
    elmore_delay,
    ideal_column_currents,
    ir_drop_report,
    solve_network,
    sneak_report,
    wire_capacitance,
    wire_resistance,
)
from .mismatch import (
    MISMATCH_DISCLOSURE,
    MISMATCH_PROCESS,
    calibration_report,
    flicker_input_noise_psd,
    flicker_output_noise_psd,
    input_referred_noise_psd,
    mc_output_error,
    mobility_ratio,
    mvm_output,
    nominal_conductances,
    pelgrom_sigma_beta_rel,
    pelgrom_sigma_vth_mv,
    sample_mismatch,
    sigma_vs_n,
    thermal_noise_psd,
    vth_at,
)
from .array_scale import (
    LANDMARKS as SCALE_LANDMARKS,
    LDA_CAPABILITIES as SCALE_LDA_CAPABILITIES,
    NON_CLAIMED as SCALE_NON_CLAIMED,
    SCALE_DISCLOSURE,
    array_scale_sweep,
    compression_ratio,
    elements_flat,
    elements_hierarchical,
    expanded_element_count,
    hierarchical_gds,
    honest_boundary_ok as scale_honest_boundary_ok,
    honest_comparison as scale_honest_comparison,
    max_scale_for_budget,
    row_line_profile,
    sigma_out_rel,
)
from .device_pde import (
    CM3_TO_M3,
    DEVICE_PDE_DISCLOSURE,
    DX_IF_NM_DEFAULT as DEVICE_PDE_DX_IF_NM,
    F_PER_UM2_TO_F_PER_M2,
    NA_CM3_DEFAULT as DEVICE_PDE_NA_CM3,
    NM_TO_M,
    T_OX_NM_DEFAULT as DEVICE_PDE_T_OX_NM,
    UM_TO_M,
    VFB_V_DEFAULT as DEVICE_PDE_VFB_V,
    cm3_to_m3,
    cox_f_per_um2_to_f_per_m2,
    cross_check_qs,
    cross_check_vth,
    device_pde_self_check,
    m3_to_cm3,
    m_to_nm,
    m_to_um,
    moscap_qs_pde,
    nm_to_m,
    parameter_consistency_report,
    pde_vs_closed_sweep,
    physics_qs_closed,
    physics_vth_closed,
    physics_vth_pde,
    um_to_m,
)
from .device_limits import (
    DEVICE_LIMITS_DISCLOSURE,
    LITERATURE_LIMITS,
    LITERATURE_PARAMS,
    N_CRIT_DEGENERATE,
    N_CRIT_NUMERICAL,
    WINDOW_HALF_WIDTH_PHI_F,
    WINDOW_REFERENCE_DX_IF_NM,
    capability_boundary_map,
    degeneracy_phi_f,
    dibl_characteristic_length,
    dibl_dvth,
    literature_gap_report,
    measure_window_edge,
    mobility_degradation_factor,
    numerical_window_grid_dependence,
    numerical_window_phi_f,
    run_selfchecks as device_limits_self_check,
    velocity_saturation_field,
    window_ratio_physical_over_numerical,
    yau_rolloff_dvth,
)

# E12 · 2D MOS 桥（本模块**函数内惰性导入** lda_solver.mos_2d ⇒ 无 scipy 环境仍可导入）
from .device_transport import (
    DEVICE_TRANSPORT_DISCLOSURE,
    cross_check_ss_closed_form,
    current_conservation_report,
    default_vg_list,
    device_transport_self_check,
    id_vd_report,
    ss_thermal_limit_report,
    ss_vs_length_report,
    transfer_curve,
    transport_capability_closure,
    vth_cc_vs_surface_potential,
)
from .converter import (
    CONV_PROCESS, CONVERTER_DISCLOSURE, converter_self_check,
    ideal_dac_voltage, code_to_bits, bits_to_code, r2r_rational_voltage,
    nmos_switch_ron_ohm, r2r_ideal_network_dc, r2r_nmos_dac_dc,
    dac_static_report, cdac_top_closed_form, sar_convert, sar_error_report,
    sample_hold_transient,
)
from .periphery import (
    PERIPHERY_PROCESS, PERIPHERY_DISCLOSURE, periphery_self_check,
    buffer_closed_loop_gain, buffer_closed_loop_rout, buffered_row_voltage,
    row_driver_mna_check, vcvs_polarity_fact, row_line_profile_with_driver,
    max_scale_with_driver, driver_scale_table, row_load_conductance,
    system_chain, row_system_error,
)
from .budget import (
    SYSTEMATIC, RANDOM, BOUNDED, CATEGORIES,
    DEFAULT_K_SIGMA, DEFAULT_ADC_BITS, DEFAULT_DAC_BITS, DEFAULT_SCAN_HI,
    lsb_to_rel_pct, rel_pct_to_lsb, output_effective_bits,
    make_term, combine, dominant_term,
    cell_conductance, row_segment_resistance, collect_terms,
    error_budget_report, budget_vs_n, max_scale_full_chain,
    BUDGET_DISCLOSURE, budget_self_check,
)
from .weight_prog import (
    WEIGHT_PROG_PROCESS, WEIGHT_PROG_DISCLOSURE, weight_prog_self_check,
    DEFAULT_S as WEIGHT_PROG_DEFAULT_S,
    program_levels, level_lsb_rel, level_error_bound_rel, level_bound_in_output,
    quantize_to_levels, write_verify_closed, iter_to_tolerance, noise_floor_sigma,
    write_verify_stochastic, residual_sigma_out, output_sigma_matrix_aware,
    drift_factor, drift_rel_pct, recal_interval, drift_curve,
    yield_fraction, stuck_error_bound_rel, differential_pair,
    canonical_weights, program_array, programming_error_matrix,
    programming_budget_terms, programming_report,
)
from .timing import (
    TIMING_PROCESS, TIMING_DISCLOSURE, timing_self_check,
    normalize_stages, serial_sum, pipelined_period, combine_time,
    rc_settle_time, settle_half_lsb, sar_period,
    row_stage_time, col_stage_time, sample_hold_stage_time,
    cdac_total_cap, cdac_settle_tau, cdac_clock_from_settle,
    sar_stage_time, dac_stage_time, stage_times,
    per_sample_report, clock_budget, time_vs_n, crossover_n_ps,
)
from .col_share import (
    COL_SHARE_PROCESS, COL_SHARE_DISCLOSURE, col_share_self_check,
    thermal_noise_rms_v, thermal_noise_bits_ceiling, bits_ceiling_of_share,
    ktc_crossing_share, cap_area_um2, converter_area_um2, readout_area_um2,
    analytic_area_um2, area_period_product_um2_s, converter_period_s,
    col_throughput_sps, k_star, fit_loglog_slope, scaling_law_report,
    architectures, recommend_architecture, replication_vs_sharing,
)
from .col_share_dynamic import (
    COL_SHARE_DYN_PROCESS, COL_SHARE_DYN_DISCLOSURE,
    charge_injection_pedestal_v, charge_injection_residual_sigma_v,
    aperture_jitter_sigma_v, jitter_bandwidth_limits,
    mux_settling_tau, mux_settling_erosion,
    dynamic_budget_terms, dynamic_cost_report,
    col_share_dynamic_self_check,
)
from .device_2d import (
    DEVICE_2D_DISCLOSURE,
    LG_NM_DEFAULT as DEVICE_2D_LG_NM,
    LONG_CHANNEL_NM as DEVICE_2D_LONG_CHANNEL_NM,
    NA_CM3_DEFAULT as DEVICE_2D_NA_CM3,
    ROLLOFF_LS_NM as DEVICE_2D_ROLLOFF_LS_NM,
    T_OX_NM_DEFAULT as DEVICE_2D_T_OX_NM,
    XJ_NM_DEFAULT as DEVICE_2D_XJ_NM,
    cross_check_vth_2d_longchannel,
    device_2d_compute_rolloff_dibl_for_case,
    device_2d_self_check,
    dibl_2d_report,
    dimension_roundtrip_report as device_2d_dimension_roundtrip,
    natural_length_2d,
    rolloff_2d_report,
    short_channel_capability_report,
)

__all__ = [
    "Circuit",
    "NmosParams",
    "id_gm_gds",
    "id_saturation_closed",
    "vdsat",
    "mosfet_self_check",
    "MOSFET_DISCLOSURE",
    "inverting_summer",
    "inverting_summer_golden",
    "mosfet_saturation_bias",
    "mosfet_saturation_golden",
    "CrossbarMVM",
    "build_ota_circuit",
    "ota_open_loop_gain",
    "CROSSBAR_DISCLOSURE",
    "AnalogMvmUnit",
    "MvmDatapath",
    "quantize_uniform",
    "relu",
    "tiled_mvm",
    "mvm_datapath_self_check",
    "MVM_DATAPATH_DISCLOSURE",
    "scale_sweep",
    "scale_bench_self_check",
    "honest_comparison",
    "honest_boundary_ok",
    "LANDMARKS",
    "LDA_CAPABILITIES",
    "NON_CLAIMED",
    "SCALE_BENCH_DISCLOSURE",
    "ECORE_CAPABILITY_MANIFEST",
    "ECORE_CAPABILITY_DISCLOSURE",
    "manifest_check",
    "ecore_module_names",
    "ELayer",
    "ELayerStack",
    "DEFAULT_CMOS_STACK",
    "get_estack",
    "ELEC_DESIGN_RULES",
    "ELEC_DISCLOSURE",
    "EDRC_RULES",
    "LAYOUT_DISCLOSURE",
    "crosspoint_cell",
    "crossbar_array",
    "array_footprint",
    "expected_netlist",
    "extract_wl",
    "run_edrc",
    "elvs_signoff",
    "to_gds",
    "gds_roundtrip_check",
    "layout_svg",
    "ELEC_PROCESS",
    "PARASITIC_DISCLOSURE",
    "array_parasitics",
    "build_network",
    "elmore_delay",
    "ideal_column_currents",
    "ir_drop_report",
    "solve_network",
    "sneak_report",
    "wire_capacitance",
    "wire_resistance",
    "MISMATCH_PROCESS",
    "MISMATCH_DISCLOSURE",
    "pelgrom_sigma_vth_mv",
    "pelgrom_sigma_beta_rel",
    "vth_at",
    "mobility_ratio",
    "thermal_noise_psd",
    "flicker_input_noise_psd",
    "flicker_output_noise_psd",
    "input_referred_noise_psd",
    "nominal_conductances",
    "sample_mismatch",
    "mvm_output",
    "mc_output_error",
    "sigma_vs_n",
    "calibration_report",
    "SCALE_DISCLOSURE",
    "SCALE_LANDMARKS",
    "SCALE_LDA_CAPABILITIES",
    "SCALE_NON_CLAIMED",
    "elements_flat",
    "elements_hierarchical",
    "compression_ratio",
    "hierarchical_gds",
    "expanded_element_count",
    "row_line_profile",
    "max_scale_for_budget",
    "sigma_out_rel",
    "array_scale_sweep",
    "scale_honest_comparison",
    "scale_honest_boundary_ok",
    # E11-c 器件级内核桥（量纲桥 + 教科书闭式 ⟷ MOSCAP PDE 交叉验证）
    "UM_TO_M",
    "NM_TO_M",
    "CM3_TO_M3",
    "F_PER_UM2_TO_F_PER_M2",
    "um_to_m",
    "m_to_um",
    "nm_to_m",
    "m_to_nm",
    "cm3_to_m3",
    "m3_to_cm3",
    "cox_f_per_um2_to_f_per_m2",
    "physics_vth_closed",
    "physics_qs_closed",
    "physics_vth_pde",
    "moscap_qs_pde",
    "cross_check_vth",
    "cross_check_qs",
    "pde_vs_closed_sweep",
    "parameter_consistency_report",
    "device_pde_self_check",
    "DEVICE_PDE_DISCLOSURE",
    "DEVICE_PDE_DX_IF_NM",
    "DEVICE_PDE_NA_CM3",
    "DEVICE_PDE_T_OX_NM",
    "DEVICE_PDE_VFB_V",
    # E11-d 器件级模型失效边界（数值窗口实测 + 物理窗口文献登记 + 缺口量化）
    "N_CRIT_NUMERICAL",
    "N_CRIT_DEGENERATE",
    "WINDOW_HALF_WIDTH_PHI_F",
    "WINDOW_REFERENCE_DX_IF_NM",
    "numerical_window_phi_f",
    "degeneracy_phi_f",
    "window_ratio_physical_over_numerical",
    "measure_window_edge",
    "numerical_window_grid_dependence",
    "LITERATURE_LIMITS",
    "LITERATURE_PARAMS",
    "yau_rolloff_dvth",
    "dibl_characteristic_length",
    "dibl_dvth",
    "velocity_saturation_field",
    "mobility_degradation_factor",
    "literature_gap_report",
    "capability_boundary_map",
    "DEVICE_LIMITS_DISCLOSURE",
    "device_limits_self_check",
    "DEVICE_2D_DISCLOSURE",
    "DEVICE_2D_LG_NM",
    "DEVICE_2D_XJ_NM",
    "DEVICE_2D_T_OX_NM",
    "DEVICE_2D_NA_CM3",
    "DEVICE_2D_ROLLOFF_LS_NM",
    "DEVICE_2D_LONG_CHANNEL_NM",
    "device_2d_dimension_roundtrip",
    "cross_check_vth_2d_longchannel",
    "rolloff_2d_report",
    "dibl_2d_report",
    "natural_length_2d",
    "short_channel_capability_report",
    "device_2d_compute_rolloff_dibl_for_case",
    "device_2d_self_check",
    "transfer_curve",
    "ss_thermal_limit_report",
    "cross_check_ss_closed_form",
    "ss_vs_length_report",
    "current_conservation_report",
    "id_vd_report",
    "vth_cc_vs_surface_potential",
    "transport_capability_closure",
    "default_vg_list",
    "device_transport_self_check",
    # —— E14（D-174…D-176）真 DAC / ADC / 行驱动外设
    "CONV_PROCESS", "CONVERTER_DISCLOSURE", "converter_self_check",
    "ideal_dac_voltage", "code_to_bits", "bits_to_code", "r2r_rational_voltage",
    "nmos_switch_ron_ohm", "r2r_ideal_network_dc", "r2r_nmos_dac_dc",
    "dac_static_report", "cdac_top_closed_form", "sar_convert", "sar_error_report",
    "sample_hold_transient",
    "PERIPHERY_PROCESS", "PERIPHERY_DISCLOSURE", "periphery_self_check",
    "buffer_closed_loop_gain", "buffer_closed_loop_rout", "buffered_row_voltage",
    "row_driver_mna_check", "vcvs_polarity_fact", "row_line_profile_with_driver",
    "max_scale_with_driver", "driver_scale_table", "row_load_conductance",
    "system_chain", "row_system_error",
    "DEVICE_TRANSPORT_DISCLOSURE",
    # —— E15（D-178…D-180）端到端误差预算链
    "SYSTEMATIC", "RANDOM", "BOUNDED", "CATEGORIES",
    "DEFAULT_K_SIGMA", "DEFAULT_ADC_BITS", "DEFAULT_DAC_BITS", "DEFAULT_SCAN_HI",
    "lsb_to_rel_pct", "rel_pct_to_lsb", "output_effective_bits",
    "make_term", "combine", "dominant_term",
    "cell_conductance", "row_segment_resistance", "collect_terms",
    "error_budget_report", "budget_vs_n", "max_scale_full_chain",
    "BUDGET_DISCLOSURE", "budget_self_check",
    "WEIGHT_PROG_PROCESS", "WEIGHT_PROG_DISCLOSURE", "weight_prog_self_check",
    "WEIGHT_PROG_DEFAULT_S", "program_levels", "level_lsb_rel",
    "level_error_bound_rel", "level_bound_in_output", "quantize_to_levels",
    "write_verify_closed", "iter_to_tolerance", "noise_floor_sigma",
    "write_verify_stochastic", "residual_sigma_out", "output_sigma_matrix_aware",
    "drift_factor", "drift_rel_pct", "recal_interval", "drift_curve",
    "yield_fraction", "stuck_error_bound_rel", "differential_pair",
    "canonical_weights", "program_array", "programming_error_matrix",
    "programming_budget_terms", "programming_report",
    "TIMING_PROCESS", "TIMING_DISCLOSURE", "timing_self_check",
    "normalize_stages", "serial_sum", "pipelined_period", "combine_time",
    "rc_settle_time", "settle_half_lsb", "sar_period",
    "row_stage_time", "col_stage_time", "sample_hold_stage_time",
    "cdac_total_cap", "cdac_settle_tau", "cdac_clock_from_settle",
    "sar_stage_time", "dac_stage_time", "stage_times",
    "per_sample_report", "clock_budget", "time_vs_n", "crossover_n_ps",
    # —— E18（D-189…D-191）列侧共享与架构权衡
    "COL_SHARE_PROCESS", "COL_SHARE_DISCLOSURE", "col_share_self_check",
    "thermal_noise_rms_v", "thermal_noise_bits_ceiling", "bits_ceiling_of_share",
    "ktc_crossing_share", "cap_area_um2", "converter_area_um2", "readout_area_um2",
    "analytic_area_um2", "area_period_product_um2_s", "converter_period_s",
    "col_throughput_sps", "k_star", "fit_loglog_slope", "scaling_law_report",
    "architectures", "recommend_architecture", "replication_vs_sharing",
    # —— E19（D-194）列侧共享的动态代价
    "COL_SHARE_DYN_PROCESS", "COL_SHARE_DYN_DISCLOSURE",
    "charge_injection_pedestal_v", "charge_injection_residual_sigma_v",
    "aperture_jitter_sigma_v", "jitter_bandwidth_limits",
    "mux_settling_tau", "mux_settling_erosion",
    "dynamic_budget_terms", "dynamic_cost_report", "col_share_dynamic_self_check",
]

# 征程入口披露（对外引用须携此诚实边界）
ECORE_DISCLOSURE: dict = {
    "route": "模拟电子计算核（MVM 交叉阵列）：电子版的「光子 MZI 网格」。",
    "e1_scope": "E1 基座：晶体管级长沟道模型 + MNA 电路仿真器（DC/瞬态/AC）+ 最小模拟计算单元。",
    "e2_scope": "E2 参数化阵列：N×M 模拟 MVM 交叉阵列生成器（amp='ideal' VCVS TIA / amp='transistor' NMOS三极管权重）；另含晶体管级 OTA 开环增益表征。",
    "e3_scope": "E3 数据通路：数字→DAC→交叉阵列→ADC→数字 的模拟计算引擎；多层级联(MLP+ReLU)+分块(tiling)；带符号权重用参考列法映射；端到端 vs 全精度数字 golden 正确性判据。",
    "e4_scope": "E4 规模对标（诚实边界）：N×N 数据通路规模扫描(至 256×256=65536 突触) + 公开模拟加速器 landmark 诚实对标；不报 TOPS/TOPS/W；相对误差有界/绝对误差 ∝N。",
    "e5_scope": "E5 平台能力硬化：ecore 能力清单（ECORE_CAPABILITY_MANIFEST·单一真源）+ 常驻守护门禁（清单↔模块/符号双向完备 + 披露一致 + 诚实边界）。",
    "e6_scope": "E6 版图与几何签核：电子版图层栈（DIFF/POLY/CONT/M1/VIA1/M2 + 层语义谓词 + 设计规则）+ 1T 交叉阵列版图 P&R（节距闭式 + AREF 层次化）+ 几何 DRC（线宽/间距/包围/面积）+ 段感知 LVS（连通分量/短路/悬空桥/W-L 几何回提）+ 真 GDSII 出口。",
    "e7_scope": "E7 寄生提取与后仿：从 E6 版图按教科书闭式提导线 RC（R=ρL/(Wt)·C=ε₀ε_r·W/d）+ 阵列 R 梯网络（行/列分段电阻 + 交叉点电导）注入 MNA 后仿，量化 IR drop（随规模超线性增）与 sneak path（half-select 浮空方案旁路电流）+ Elmore 互连延迟；golden = 解析 I_j=Σg_ij·V_i（R=0 精确复现）。",
    "e8_scope": "E8 非理想/失配/噪声：Pelgrom 器件失配（σ_ΔVth=A_VT/√(W·L)、σ_Δβ/β）+ 温度一阶模型（Vth 线性漂移 · 迁移率 (T/T0)^m · 片内列热梯度）+ 噪声（热 4kTγg_m · 闪烁 K_f/(C_ox·W·L·f)）+ 失配 Monte Carlo 输出误差分布（自证 σ_rel ∝ 1/√N）+ 校准层级 L0 原始 / L1 列增益 / L2 逐单元。",
    "e9_scope": "E9 规模压力与诚实对标：E6 物化版图与 E7 稠密 MNA 都只到 N≈32 ⇒ 换 O(N) 算法（cell+AREF 层次化出图 + 一维三对角 IR-drop 求解）推到千级阵列；三重规模律（IR drop 超线性 · 面积 ∝N² · 失配 σ ∝1/√N · Elmore ∝N²）+ 按误差预算反解可及规模上界 + 同族维度诚实对标（landmark 照录·不报 TOPS）。",
    "e10_scope": "E10 收官（平台硬化 + 案例卡升级 + 对外物料 + 生产部署）：把 E1–E9 全链固化为**对外只读案例卡**（`/api/ecore_demo` · 九段里程碑 + 四块新能力面 facts + 9 条诚实边界）+ 守护 scope 扩到本段 + 对外物料与生产上线；本段**不新增求解器能力**，属集成/对外/验收段（新增判据由 run_ecore_case_smoke 承载）。",
    "e11_scope": "E11 器件级内核接线：**E11-a** 口径同步（把「本包的设计取舍」与「平台红线」两件事分离，统一订正为**分层口径** + 防漂移门禁）；**E11-b** 接缝勘查（查明 ecore 与器件级内核零复用的根因 = 两侧非同一器件：`drift_diffusion_1d/2d` 是两端 p-n 结，本包要的是三端 MOSFET）；**E11-c 器件级内核桥** = 平台新增 MOS 结构 1D 自洽泊松内核（`lda_solver/mos_1d.py` · MOSCAP）+ 本包 `device_pde.py`：量纲桥（SI ⟷ µm 制）+ 教科书闭式（Sze 完整 Q_s 式 / 耗尽近似 V_th 式）⟷ PDE 数值解交叉验证（V_th 与 Q_s 跨点一致 ≤0.02% · 工作区 ψ_s ≤ 2.5φ_F）+ 参数自洽性显式报告（G-3）。🔴 golden = 教科书闭式，PDE 只是 candidate（`is_oracle=False`）；**不替换**任何电路级默认参数（`NmosParams` 逐位不变）。**E11-d 失效边界测绘** = `device_limits.py`：**两类边界严格分离** —— A **数值窗口**（LDA 实测：ψ_s ∈ φ_F·[1±1.54]，**随网格变化**：0.05→0.02 nm 时窗口变宽）/ B **物理窗口**（文献判据：玻尔兹曼简并 + 1D 无源漏，**与网格无关**）⇒ **物理模型先失效、数值后崩**（半宽比 0.835）；另含文献经验式**缺口量化**（L=65 nm 时短沟道 roll-off 占 V_th **37.9%**）· 每项标 `computed_by_lda=False`。",
    "e12_scope": "E12 2D MOS 求解器（短沟道效应：**算不了 → 算得了**）：E11-d 曾把 V_th roll-off / DIBL 登记为平台算不了（只引文献经验式），本段补上能力本身 —— 平台新增 `lda_solver/mos_2d.py`（**四端**栅/源/漏/衬底 2D 自洽泊松：变系数有限体积离散（**按面中点判介质** ⇒ Si/SiO₂ 界面离散精确，氧化层电容恰为 ε_ox/t_ox）+ **分段边界条件** + **电子准费米势分裂**（源侧 0 / 漏侧 V_d ⇒ n⁺ 区自然中性、偏压真正进得去）+ 阻尼牛顿 / continuation）+ 本包 `device_2d.py`（量纲桥 + 长沟道极限 ⟷ 教科书 1D 闭式交叉验证 + roll-off / DIBL 报告 + 与 E11-d 文献式**对照** + 能力闭合表）。🔴 golden = 教科书 1D 长沟道耗尽式（`device_pde.physics_vth_closed` 单一定义），2D 数值解只是 candidate（`is_oracle=False`）；**只允许「长沟道极限 2D → 1D」方向，绝不反向**。核心判据：长沟道收敛（rel 0.50%）· roll-off 单调且 L=65nm 下降 **−176 mV**（文献式对照 −161 mV）· DIBL **153 mV/V** 且满足 **ln(DIBL)–L 线性（R² 0.9986，指数衰减律）** · 两变体互验（majority ⟷ boltzmann 差 11 mV = 反型层电荷贡献）。🔴 **本段（E12）为准平衡静电求解，不含漂移扩散输运 ⇒ 不产 I-V —— 该缺口已由 E13 闭合**（`lda_solver/mos_2d_transport.py` + 本包 `device_transport.py`；详见 `e13_scope`）；结构为教科书突变结 + 2 nm 平滑（无 LDD/halo/应力/量子修正）；参数为公开典型量级占位（非 PDK）；不报 TOPS/TOPS-W/fJ/op。",

    "e13_scope": "E13 2D MOS 漂移扩散输运（I–V / 亚阈值摆幅 —— 把 E12 的 G-K「不含输运 ⇒ 不产 I-V」关掉）：平台新增 `lda_solver/mos_2d_transport.py`（**Si-only 掩码**稳态连续性（Scharfetter–Gummel 离散；氧化层节点逐出未知量集 ⇒ Si↔SiO₂ 界面自然 Neumann；y 网格非均匀 ⇒ 逐边取间距）+ **接触准费米势 BC**（φ_n = φ_p = V_c ⇒ n·p = n_i²，统一式自动给出 n⁺ 区 n=N_SD / p 区 p=N_A）+ Gummel 交替（非线性泊松 ⟷ 连续性）+ 终端电流（SG 守恒截面 · 源≡漏））+ 本包 `device_transport.py`（量纲桥复用 E11-c + G1–G6 判据 + 能力闭合表）。🔴 **golden 双锚**：**SS 热极限 `(kT/q)·ln10 = 59.53 mV/dec`（物理定律锚 · 不等式，数值解不得突破）** 与 **教科书闭式 `(kT/q)ln10·(1+Cd/Cox)`（含体效应）** ⇒ 长沟道（1 µm）数值 SS **68.08 ⟷ 闭式 66.41 mV/dec（rel 2.5%）**；栅长趋势 L↓ ⇒ SS↑（65 nm **232** → 100 nm 88.0 → 250 nm 69.5 → 1 µm 68.1）与 E12 的 roll-off/DIBL **同向**；电流守恒（大电流点 rel 5.4e-5）；输出特性单调且趋饱和；**V_th 双法交叉**（恒流法 0.2475 ⟷ E12 表面势法 0.3241 V，差 76.6 mV；**两法均 `is_oracle=False`**，互不充当 ORACLE）。🔴 **仍为漂移扩散（DD）框架**：不含量子修正 / 速度饱和 / 带间与栅隧穿 / 弹道输运；**迁移率为常数**（无场依赖退化 / 无表面散射）⇒ `I_on` 绝对值**不可当器件性能**（深亚阈值 SS 不受影响，但 I_on 偏高、I_off 偏低）；无 LDD/halo/应变/栅重叠；参数为公开典型量级占位（非 PDK）；2D 仿真 = **每单位宽度电流（A/m）**；不报 TOPS/TOPS-W/fJ/op。",
    "e14_scope": "E14 真 DAC / ADC / 行驱动外设（把「设计链」补成「系统链」）：E1–E13 的数据通路里 DAC/ADC 一直只是**行为级均匀量化模型**（`mvm_datapath.quantize_uniform`）、行线由**理想电压源**钉住（`crossbar_mvm.py`）—— 本段补上两端转换器与行驱动的**真电路**。① `converter.py`：**R-2R 梯形 DAC**（无源电阻网络 + **NMOS 模拟开关** ⇒ 暴露导通电阻 `R_on` 对精度的限制：8 bit 全码扫描 max|Δ| **0.0265 LSB** · `R_on`=6.4 Ω）与 **SAR + CDAC 电荷重分配 ADC**（真电容阵列 + 真瞬态 + 逐次逼近逻辑；🔴 **电容 DC 开路 ⇒ 必须走瞬态**：后向欧拉伴随模型给出 `Σ C(V_top−V_bk) = const` 即**电荷严格守恒**，一步瞬态 = 精确电荷守恒解）+ **采样保持 RC**（瞬态 ⟷ 后向欧拉离散闭式 rel **5.6e-16**，与连续闭式偏差 **O(dt)** 且随步长加密单调降）。② `periphery.py`：**行驱动闭式** `v_load = v_in·A/(1+A+R_ol/R_L)`（含增益误差与**闭环输出电阻** `R_oc=R_ol/(1+A)`；与 **MNA 真实电路**（VCVS 闭环 + R_ol + R_L）对拍 rel 1.4e-16）+ 🔴 **把 `R_oc` 串进 E9 的三对角 IR-drop 模型** ⇒ **可及规模上界重算**（5% 预算：理想源 N≤**20** → `R_oc`=1 Ω N≤17 → 5 Ω N≤**10** → 20 Ω N≤**3**）—— **器件级参数第一次反馈到规模律**；`R_oc = 0` 时与 E9 `array_scale.row_line_profile` **逐位一致**（max|Δ| = 0，极限交叉核对）。③ **端到端系统链**（DAC→行驱动→阵列→TIA→ADC）与 **行系统项**：驱动负载调整引入**按行增益误差**（行负载随行权重和变化 ⇒ 行增益**离散** 8.889e-4；理想驱动下离散 = 0）—— 与 E8 的**列系统项**同型，**不会被 MC 平均掉**。🔴 **诚实体积**：**比较器是「有限增益 + 失调 + 噪声」判决器抽象、非晶体管级**（MNA 无非线性饱和器件，E2 已证朴素差分对无法闭合高增益环路）；**CDAC 底板开关用理想电压源抽象**（DAC 侧用真 NMOS 开关以暴露 R_on）；行驱动器为 **VCVS + 开环输出电阻的宏模型**；电阻/电容为理想值（不建匹配网络）；参数为公开典型量级占位（非 PDK）；不做流片；不报 TOPS/TOPS-W/fJ/op。🔴🔴 **平台缺陷登记（本段发现 · 不修 mna）**：`mna.Circuit.vcvs` 的 **docstring 声明** `V_out = gain·(V_cp−V_cn)`，但 `_stamp_dc` 实际给出 **`gain·(V_cn−V_cp)`（极性相反）** —— 按保护性约束（E1–E13 全部已上线数字建立其上，含 E2 ideal-TIA 的虚地电路）**不改 mna**，改为**适配 + 显式登记 + 判据锁死**；E2/E3 结论仍成立（TIA 虚地是 `|A|→∞` 极限，符号只改变放大器输出定向、不改变虚地机制）。",
    "e15_scope": "E15 端到端误差预算链（**把已走过的四类误差合成一条链**）：E1–E14 每段都给了**单点误差**，但**从未合成过**，且口径互不相同（相对 % / σ / LSB）、性质未分类（系统性 / 随机 / 有界）。本段新增 `budget.py`（ecore 第 19 个模块 · **不吃新物理**，只读消费既有接口）：① **口径桥** —— 统一锚点 `1 LSB @ k bit = 100/2^k %FS`（自洽判据 `bits_eff(lsb_to_rel_pct(k)) == k`，纯代数、无需任何模块）；② **三分类合成律** —— 系统性 **Σ**（代数）/ 随机 **RSS(→kσ)** / 有界 **Σ(→√3 折减)**，`worst = Σsys + kσ_tot + Σbnd`、`typical = Σsys + σ_tot + Σbnd/√3`（🔴 简单相加是错的，全用 RSS 也是错的）；③ **输出有效精度位数**（🔴 自定义量，**不是 IEEE ENOB**）· **误差主导项分析**（给设计者的行动指令）· **全链预算下的可及规模上界**（泛化 E9：仅 IR drop 时**委托** E9 ⇒ 逐值相等；全链时用**扫描而非二分**，因 `worst(N)` 未必单调）。🔴 **关键实测**：**8×8 ⇒ worst 4.0601% ⇒ 有效精度仅 4.622 位**（不是 8 位）；**精度 vs N**：N=8 **4.622** → 16 3.963 → 32 2.639 → 64 1.343 → 128 0.578 → 256 **0.248**；🔴 **主导项交叉点** —— N≤8 由**器件失配**主导（44.0%）、N≥16 由 **IR drop** 主导；🔴 **全链上界（5% 预算）N≤12**，而仅 IR drop 口径为 **N≤18** ⇒ **E9 原来的「5% ⇒ N≤18」是乐观的**（漏计失配 / 行驱动 / 转换器后只能到 12）。🔴 **诚实边界**：`output_effective_bits` **非 IEEE ENOB**（口径 = `log2(100/最坏相对误差[%])`）；**只覆盖静态**（不含时序 / 动态 / 采样率 / 时钟抖动 / 热梯度空间分布 / 老化 / 电源噪声）；合成律是**保守工程口径**（`worst = Σsys + kσ + Σbnd`），**不是严格概率保证**；`typical` 的 `Σb/√3` 假设均匀分布；参数为公开典型量级占位（**非 PDK**）；器件侧仍 **DD 框架 + 常数迁移率**；**不报 TOPS/TOPS-W/fJ/op**。🔴 **保护性约束**：本段**只读消费** E7/E8/E9/E14 接口，**不改**任何既有默认值（门禁 G8 逐位守住）。",
    "e16_scope": "E16 权重编程通路（补上「权重怎么写进阵列」这一此前完全不存在的一环）：E1–E15 全程把权重当**已知且精确**的输入（`crossbar_mvm` 的 weights 直接是电导/栅压 · `mvm_datapath` 用 `G=g_base+s·W` 解析算出 · `layout` 的权重栅只是对外端口），**从未建模「写入动作」**。本段新增 `weight_prog.py`（ecore 第 20 个模块 · 纯 numpy · **不吃新物理**）：① **写-校验**动力学（比例修正 α + 加性写入噪声 σ_p）；② 五个**闭式 golden** —— 电平步长 `1/(2^k−1)` · 确定性轨迹 `e0(1−α)^k` · 到容差脉冲数 `ceil(ln(tol/e0)/ln(1−α))` · 🔴 **写入噪声地板 `σ_p/√(α(2−α))`**（无穷级数精确解 ⇒ **单脉冲噪声是硬地板，写-校验最多把地板抬升 1/√(α(2−α)) 倍；tol<σ_∞ 时期望上不可达** ⇒ 设计指令 = 降 σ_p 而非加脉冲数）· 漂移幂律 `(t/t0)^(−ν)` 与**重校准间隔闭式** `t0(1−β)^(−1/ν)`；③ **良率 `(1−p)^N`** · **差分对** · **矩阵感知端到端**（接 E8 `mvm_output`）；④ **接 E15 误差预算链** —— `programming_budget_terms()` 输出 E15 `make_term` 格式（写入残差 = **RANDOM**（被 1/√N 平均）· 电平量化 = **BOUNDED**（N 无关）；🔴 电平在窗口内**等间距 ⇒ 误差绝对值与 g 无关 ⇒ 输出界 = 半步长/**平均电导**，不是最小电导）。🔴 **关键实测**：写入噪声地板 σ_cell **0.7001%**（闭式 ⟷ MC rel 0.13%）· 8×8 有效精度 **4.6223 位 → 4.5706 位（模拟写入）→ 4.2445 位（MLC 6 位，−0.378 位）**；**5% 预算可及规模 12 → 11（模拟写入）→ 无解（MLC 6 位）**；电平位数 ≥8 位后**收益饱和**（4.4829 → 4.5650，渐近 4.5706）。🔴 **诚实边界**：参数（α/σ_p/tol/ν/p_stuck）为**公开典型量级占位 · 非 PDK · 无实测锚** ⇒ 结论随参数变（漂移结论**条件于 ν**）；器件模型为**行为级**（比例修正 + 加性噪声），**不含**细丝动力学/脉冲宽度依赖/温度加速；无 endurance/retention 联合退化；**只覆盖静态**；**共模漂移可被单次全局增益校准消除 ⇒ 不进预算**（进预算的只有 ν 的单元间离散）—— 一个能被单次校准消掉的项不是精度上限；**不报 TOPS/TOPS-W/fJ/op**。🔴 **保护性约束**：`budget.collect_terms` 新增的 `include_programming` **默认 False** ⇒ **E15 已发布数字逐位不变**（门禁 B12 + 探针 C5 专守此线，与 `NmosParams`/`mna.vcvs` 同族纪律）。",
    "e17_scope": "E17 时序 / 时钟预算链（**时间维度上的 E15**）：E1–E16 全程把时间当**不存在** —— "
             "全仓 `sample_rate` / `clock` / `latency` / `timing_budget` / `throughput` / `per_sample` / "
             "`settling_time` **零命中**；有**零散时间量**却从未串成链（`parasitic.tau_row_s` 只是裸时间常数 · "
             "`converter.sample_hold_transient` 只覆盖一级 · `sar_convert` 逐位试判却从未折算成时间），"
             "且 `PERIPHERY_PROCESS` **一个时间参数都没有**（行驱动是**无限带宽宏模型** ⇒ 采样率算不出来）。"
             "本段新增 `timing.py`（ecore 第 21 个模块 · 纯标准库 · **只读消费 E7/E14 · 不吃新物理**）："
             "① 🔴🔴 **第一原理「误差要分类合成，时间要分拓扑相加」** —— E15 `budget.combine` 按**类型**做 "
             "RSS（系统性 Σ / 随机 RSS→kσ / 有界 Σ→√3），而时间阶段是**物理串行**的 ⇒ `serial = Σ t_i`，"
             "流水线稳态 `= max t_i`（首样本延迟仍 = Σ）；**对时间取 RSS 是错的**（串行阶段的时间必然叠加，"
             "不满足「独立随机量」前提）⇒ **E15 的合成律不可平移到 E17**。"
             "② **五个闭式 golden**：`t = τ·ln(1/ε)`（一阶 RC 建立）· `τ·(k+1)·ln2`（建立到 k-bit ½LSB）· "
             "Elmore `r·c·n(n+1)/2`（复用 E7）· `(n_bits+1)`（SAR 拍数）· "
             "`t_clk = settle_half_lsb(R_on·C_u·2^n, k)`（CDAC 建立 ⇒ 时钟，复用 E14 `nmos_switch_ron_ohm`）。"
             "③ **五阶段**（行线 / 列线 / 采样保持 / SAR / DAC），全部**复用**已有效量；"
             "🔴 行线建立 = **分布式 Elmore + 驱动源阻抗 `R_oc·C_row_tot`**（串联）⇒ `R_oc=0` 时"
             "**退化为纯 Elmore**（泛化必须退化为特例）。"
             "④ **报告 / 反解 / 规模**：`per_sample_report` · `clock_budget`（给定目标周期反解 `t_clk` 上限 + 代回验证）· "
             "`time_vs_n` · `crossover_n_ps`（阵列 RC 何时达目标 τ）。"
             "🔴 **关键实测**：8×8 / 8 bit 每样本 **129.565246 ns ⇒ 7.7181 MSa/s**（SAR 92.135 ns 占 **71.11%** · "
             "DAC 31.192 ns 占 24.07% · 采样保持 6.238 ns 占 4.81% · 行线 **0.000029 ns** · 列线 0.000013 ns）；"
             "🔴🔴 **规模 × 时间趋势相反** —— N 8→1024 时阵列 τ_row 跨 **12556.5×**（∝N²）而**每样本耗时只跨 1.00469×** "
             "⇒ **规模墙是「精度墙」（E15：IR drop ∝N²，5% 预算只到 N≤12）不是「速度墙」**；"
             "阵列 τ 达 1 ns 需 **N≈4238**（解析 4245.8 ⟷ 二分 4238）⇒ **在可达规模内阵列 RC 永不是时间瓶颈**；"
             "🔴 **主导项随位数交叉**：4/6 bit ⇒ **DAC 建立**主导（76.8% / 56.4%），8/10/12 bit ⇒ **SAR** 主导"
             "（71.1% / 92.3% / 98.3%）—— 因为 SAR ∝ (bits+1)²（拍数 × 每拍建立）而 DAC ∝ (bits+1) ⇒ **必然交叉**；"
             "流水线收益 (Σ−max)/Σ = 0.289（最慢级独占 ⇒ **流水线几无收益，提吞吐须并行复制瓶颈级**）。"
             "🔴 **诚实边界**：**只报「每样本耗时（ns）」与相对量 · 绝不报 TOPS/TOPS-W/fJ/op**（既无功耗模型也无实测硅）；"
             "五阶段为**宏模型级**估算（行驱动仍为 VCVS + 开环输出电阻宏模型 · 无真实 GBW/摆率 · 比较器延时/时钟树/抖动"
             "**未建模** · R-2R 节点电容为**显式占位**）；**只覆盖静态 + 一阶 RC 建立**（不含摆率/时钟偏斜与抖动/供电噪声/"
             "温度梯度/老化/工艺角）；**不做能量与功耗估算**；参数非 PDK ⇒ 结论随参数变。"
             "🔴 **保护性约束**：**只读消费** E7/E14，**不改**任何既有默认值；**不给** `PERIPHERY_PROCESS` 加时间键"
             "（E14 行驱动保持原样，E17 的时间参数只进自己的 `TIMING_PROCESS`）⇒ E15/E16 已发布数字**逐位不变**"
             "（门禁 B15/B16 守着）。",
    "e18_scope": "E18 列侧共享与架构权衡（补上全仓此前**完全没有建模**的「面积」维度）："
                 "E1–E17 的列侧读出（TIA + ADC）**始终是「每列一份」**（`crossbar_mvm` 每列一个理想运放 · "
                 "`mvm_datapath` 每列一个 ADC · `converter.sar_convert` 是单通道），"
                 "全仓 `share`/`mux`/`multiplex`/`复用器`/`时分` 在 `lda_l2/ecore/` **零命中** ⇒ "
                 "「列侧电路能不能共享、共享的代价是什么」此前无人能答。本段新增 `col_share.py`"
                 "（ecore 第 22 个模块 · 纯标准库 · **只读消费 E14/E17 · 不吃新物理**）："
                 "① 🔴 **第一原理「面积-时间乘积守恒」** —— 全并行 `N·A_u`/`T_conv` 与 K 列共享 "
                 "`(N/K)·A_u`/`K·T_conv` 给出 **`A_total × 每列周期 = N·A_u·T_conv`（与 K 无关）**；"
                 "② 🔴 **第二原理「保吞吐共享 ⇒ 面积 ∝1/K²」** —— 缩 `T_conv` 的唯一物理路径是降 `C_tot`"
                 "（`T_conv ∝ C_tot·(bits+1)²` · E17 G-5）⇒ **双项闭式** "
                 "`A(K) = N·C_tot(1)/(ρK²) + N·A_logic/K`（电容项 ∝1/K² · 逻辑项 ∝1/K），"
                 "拐点 `K* = C_tot(1)/(ρ·A_logic) = 160`；"
                 "③ **第三腿（诚实结论）** —— `σ = √(kT/C_tot)` 是物理律，但 kT/C 跌到 8 位需共享度 "
                 "**K ≈ 1.05×10⁵**（≫ 任何合理共享度）⇒ **共享的真实代价是「吞吐」不是「精度」**"
                 "（**不硬造精度腿**）；"
                 "④ **量级事实** —— 8 bit CDAC 单列电容面积 **128 000 µm²**，而 64×64 阵列本体足迹仅 "
                 "**23 302 µm²** ⇒ **读出 = 阵列的 355 倍**（全并行 N=64 = **8.27 mm²**）；"
                 "⑤ **架构族对照 / 推荐 / 复制-共享** —— 五条路线（全并行 / TIA 共享 / ADC 共享不保吞吐 / "
                 "ADC 共享保吞吐 / 全串行，面积比 **63.2×**）；**推荐**（N=64 / 8 bit / 10 MSa/s）"
                 "共享度饱和到列数 ⇒ 面积由 8.27 mm² 降到 **30 000 µm²（1/276）**；"
                 "🔴 **接 E17 的 0.289 锚** —— **提吞吐（并行复制瓶颈级）与省面积（共享）是同一条 "
                 "`A×周期 = 常数` 双曲线的两端**。"
                 "🔴 **诚实边界**：面积为**宏模型占位**（ρ=2 fF/µm² · A_logic=800 µm² · A_tia=400 µm² · "
                 "非 PDK）；**只覆盖静态**（不含动态功耗 / 时钟树 / 供电网络 / 驱动器面积）；"
                 "共享的**动态代价（多路开关电荷注入 / 串扰 / 采样孔径抖动）未建模**；"
                 "**不做功耗估算 ⇒ 不谈能效**；**绝不报 TOPS / TOPS-W / fJ/op**。"
                 "🔴 **保护性约束**：**只读消费** E14/E17，**不改**任何既有默认值；"
                 "`keep_throughput` **默认 False** ⇒ E15/E16/E17 已发布数字**逐位不变**。",
    "e19_scope": "E19 列侧共享的动态代价（**闭合 E18 G-S 自点名缺口**，把「静态面积」口径闭合成「静态+动态」）："
                 "E18 补上「面积」维度却自点名漏了「共享的动态代价」。本段新增 `col_share_dynamic.py`"
                 "（ecore 第 23 个模块 · 纯标准库 · **只读消费 E14/E17/E18/E8/E15 · 不吃新物理**）："
                 "① 🔴 **复用开关电荷注入 + 时钟馈通 = 确定性 pedestal**（~12% FS 量级）**可单点校准消除**"
                 "⇒ 不进精度预算；其 **Pelgrom 随机残差 ~29 µV ≪ kT/C/LSB** ⇒ 不是墙；"
                 "**真成本 = 校准负担（N 列需 N 次失调校准）**（与 E16 共模漂移同口径）。"
                 "② 🔴 **采样孔径抖动** σ_v = π·f·V_ref·σ_t（满量程正弦最陡斜率最坏口径）；"
                 "地板仍是 E18 的 kT/C：仅当 **f > ~20.5 MHz** 越过热噪地板、**f > ~1.24 GHz** 越 LSB"
                 "（保吞吐共享抬高 kT/C 地板 ⇒ 更早触发）；**条件性，非墙**。"
                 "③ 🔴 **多路开关建立时间对吞吐的侵蚀**（复用 E14 R_on·E17 建立律）：C_s 固定绝对开销 ⇒ "
                 "plain 共享下侵蚀**恒定 ~0.04%**（可忽略）；**保吞吐共享下随 K 回升、K*≈160 处 ≈7% 每列周期**"
                 "—— E18 静态模型此前未计的真实动态代价，且**反相关于 E18 面积收益**。"
                 "🔴 **诚实结论**：三项动态代价在可达共享度内**都不是精度墙**；共享的真实新代价 = "
                 "「保吞吐开关建立开销」+「高带宽孔径抖动」，二者皆反相关于 E18 静态收益，但**都不造新墙**（不硬造精度腿 / 不报 TOPS）。"
                 "🔴 **诚实边界**：开关尺寸/重叠/抖动/信号频率均为**公开量级占位（非 PDK）**；"
                 "电荷注入用 α=0.5 经典模型、时钟馈通用栅漏重叠 C_gd 一阶模型；"
                 "**不做功耗估算 ⇒ 不谈能效**；**绝不报 TOPS / TOPS-W / fJ/op**。"
                 "🔴 **保护性约束**：**只读消费** E14/E17/E18/E8/E15，**不改**任何既有默认值；"
                 "`keep_throughput` **默认 False** ⇒ E15/E16/E17/E18 已发布数字**逐位不变**；"
                 "**不覆盖** E18 `converter_period_s`/`col_throughput_sps`。",
    "redline": "红线 = **分层口径**（2026-09-11 §八§九 · 2026-09-23 逐步解锁）：平台**器件级 T1 内核已解锁**"
               "（`lda_solver/drift_diffusion_1d/2d`）；**T2 工艺真值 / 工艺角 / 流片永久锁**。"
               "**本包主动限定在电路级**——这是设计取舍，不是红线要求。",
    "sovereignty": "C 级自主（纯 numpy），不借 HSPICE/Spectre 等商业 SPICE 引擎；LLM 不进判决路径。",
    "honest_boundary": "电路级设计验证引擎，非签核级 SPICE（无温度/噪声/稀疏矩阵/收敛增强）；"
                       "晶体管参数为公开典型量级占位，非 PDK 标定，无实测锚 ⇒ 不宣称器件性能。",
    "not_oracle": "golden 均为闭式物理律（分压/平方律/一阶 RC）；不引入任何外部 ORACLE。",
}
