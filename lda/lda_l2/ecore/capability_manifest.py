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
    "route": "电子计算征程 E5 · 平台能力硬化（ecore 能力清单 + 常驻守护门禁）· E10 收官扩面至 e1~e10 · E11-c 扩面至 e1~e11 · E12 扩面至 e1~e12",
    "e5_scope": "把 E1~E9 逼出的平台能力固化为机器可读清单（单向真源）+ 常驻门禁（正向完备 + 反向完备 + 披露一致 + 诚实边界）",
    "hardening_semantics": "能力面必须被门禁守着：任一模模块/符号缺失、隐身模块出现、或注入 fabricated 指标 ⇒ 门禁必红",
    "redline": "红线 = 分层口径（器件级 T1 内核已解锁 · T2 工艺真值/工艺角/流片永久锁）；"
               "**本包主动限定在电路级**；C 级自主（纯 numpy/标准库）；LLM 不进判决路径",
}
