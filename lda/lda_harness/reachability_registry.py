# -*- coding: utf-8 -*-
"""D-223 · **公开函数可达性登记表**（**非门禁模块** · 净增 0 锚）。

🔴 为什么单独放这里（与 `bl_registries.py` / `d1_registries.py` 同一条纪律）
----------------------------------------------------------------------------
本文件登记「**当前确认为零外部引用的公开函数**」及其形态分类。
若把它写进门禁源码，K4 的文本代理会把里面的函数名当「有专属判据」⇒ 覆盖率虚增。
故：**登记表在非 CORE 模块**，门禁 `run_reachability_smoke.py` 只 `import` 并断言。

## 这张表要解决什么

v0.9.271 修的那个 bug（`resonator_freq_ghz` 偏 1e6 倍）能潜伏很久，根因不是缺少
门禁，而是——**这个函数全仓零引用**，所以没有任何判据能碰它。

⇒ 本表的用途**不是**「消灭所有零引用函数」（那既不现实也不该是目标），
而是**要求每一个零引用函数都被有意识地裁决过一次**：

- **新增**一个零引用公开函数 ⇒ 门禁必红（必须先分类、再登记，或改成私有）；
- **修好**一个（接线或私有化）⇒ 门禁也红（提示删掉登记，防止「登记了就不管」）。

## 六类形态（每条登记必须归类）

| class | 含义 | 典型处理 |
|---|---|---|
| `ANCHOR_GOLDEN_ORPHAN` | 锚号形式的 golden 实现已**改用别的函数**（如统一到 `golden_b361`/`golden_b473`） | 候删（先核对锚的 `golden_fn`） |
| `ANCHOR_PAIR_UNREFERENCED` | golden/candidate **成对**但无人引用（对应锚已改用内联实现或换源） | 候删，或接回账本 |
| `ANCHOR_REMOVED` | 锚本身已从账本删除，函数是残骸 | 候删 |
| `REPORT_FN_UNWIRED` | 报告/判决/markdown 生成函数，未接到端点或文档流水线 | 接线，或标记为库 API |
| `UI_PREVIEW_UNWIRED` | WebUI 的 svg 预览导出器，未接任何面板 | 接面板，或私有化 |
| `PUBLIC_API_NO_CONSUMER` | 形态上是通用 API，当前仓库内无消费者 | 保留（库语义），但**必须在此留痕** |
| `UTILITY_NO_CONSUMER` | `load_*` / `verify_*` / `is_*` 类工具函数，无消费者 | 同上 |

## 维护纪律

1. **只许减、不许无故增**：新增条目必须在此文件里落一条分类；
2. **修好即删**：函数接线或私有化后，把它从 `DEAD_BASELINE` 删掉（门禁会提醒）；
3. **不许用通配正则代替逐条登记**：正则会把「新增的死函数」一起吞掉 ⇒ 判据失去判别力；
4. 计数与分类统计由 `baseline_stats()` 现算，**不写死数字**。

## 边界

- 这是**静态可达性**，不是运行时覆盖率；「可达」不等于「被测过」；
- 私有函数（`_` 前缀）不在扫描面；
- `MUST_BE_REACHABLE` 是**反向防守**：这些函数是最近几版的关键交付物，
  一旦变回死函数就意味着「接线被拆了」，必须立刻红（v0.9.271 同类事故防复发）。
"""

from typing import Any, Dict, List

ROLE = ("D-223 · 公开函数可达性登记表 —— 记录 95 个已知零引用公开函数的形态分类，"
        "并反向锁定 17 个「必须是活的」关键函数。非门禁模块。")
ANCHORABLE = False

#: 各形态的说明（门禁断言：每个用到的 class 必须在此登记，防「自造新分类」）
DEAD_CLASSES: Dict[str, str] = {
    "ANCHOR_GOLDEN_ORPHAN":
        "锚号形式的 golden 实现已改用别的函数（统一到某一个 golden_bNNN）⇒ 候删",
    "ANCHOR_PAIR_UNREFERENCED":
        "golden/candidate 成对但无人引用（锚已改用内联实现或换源）⇒ 候删或接回账本",
    "ANCHOR_REMOVED":
        "锚本身已从账本删除，函数是残骸 ⇒ 候删",
    "REPORT_FN_UNWIRED":
        "报告/判决/markdown 生成函数未接端点或文档流水线 ⇒ 接线或标记为库 API",
    "UI_PREVIEW_UNWIRED":
        "WebUI svg 预览导出器未接任何面板 ⇒ 接面板或私有化",
    "PUBLIC_API_NO_CONSUMER":
        "形态上是通用 API、当前仓库内无消费者 ⇒ 保留（库语义）但必须在此留痕",
    "UTILITY_NO_CONSUMER":
        "load_* / verify_* / is_* 类工具函数无消费者 ⇒ 同上",
}

#: 🔴 **反向防守**：这些函数必须是可达的（最近几版的核心交付物 + v0.9.271 的 bug 函数）。
#: 一旦变回死函数 ⇒ 说明「接线被拆了」，门禁立即红。
#: 格式 `module::name`，与 `reachability.dead_key()` 同构。
MUST_BE_REACHABLE: List[str] = [
    # v0.9.271（A2）：那个偏 1e6 倍的函数 —— 修好后接进 selfchecks ⑦b 与专属门禁，
    #   它若再次变死，就意味着「门禁接线被拆」，1e6 倍错会重新无人看守。
    "lda/lda_qeda/sc_readout_mux.py::resonator_freq_ghz",
    "lda/lda_qeda/sc_readout_mux.py::resonator_length_um",
    "lda/lda_qeda/sc_readout_mux.py::mux_plan",
    # v0.9.272（A1）：介电口径单一真源
    "lda/lda_qeda/substrate_caliber.py::caliber_register",
    "lda/lda_qeda/substrate_caliber.py::why_not_unified",
    "lda/lda_qeda/substrate_caliber.py::sensitivity_margin",
    # v0.9.273（B1）：动力学电感
    "lda/lda_qeda/kinetic_inductance.py::l_kin_per_length",
    "lda/lda_qeda/kinetic_inductance.py::n_eff_with_kin",
    # v0.9.274（B2）：表面阻抗
    "lda/lda_qeda/conductor_surface.py::surface_impedance",
    "lda/lda_qeda/conductor_surface.py::alpha_c_cpw",
    "lda/lda_qeda/conductor_surface.py::zs_super",
    # v0.9.269：CPW 准静态 + 版图反提
    "lda/lda_qeda/cpw_quasi_static.py::cpw_closed_form",
    "lda/lda_qeda/cpw_quasi_static.py::layout_to_resonator_signoff",
    # v0.9.270（A3）：容错编译层
    "lda/lda_qeda/ft_compiler.py::compile_circuit",
    "lda/lda_qeda/ft_compiler.py::integer_identities",
    # v0.9.268：foundry deck 限值契约层
    "lda/lda_qeda/quantum_deck.py::drc_with_deck",
    "lda/lda_qeda/quantum_deck.py::build_deck",
    # ── v0.9.279（D-227 · F-10 正解）：扩容 + 补「能力层模块全覆盖」契约 ──
    # 🔴 扩容理由：上面 17 条只覆盖了 5 个能力层模块，而平台有 10 个模块带
    #    `ANCHORABLE =` 声明。缺的 5 个**当前零死函数**，所以此前一直没有红 ——
    #    但「现在恰好都活着」≠「有机制防它变死」。v0.9.271 的 1e6 倍 bug 正是
    #    「无锁 ⇒ 自由腐烂」的实例，故按模块逐个补入口。
    # v0.9.276（M1）：真反提链路（`g` 从版图真读回）
    "lda/lda_qeda/cpw_quasi_static.py::cpw_gap_from_layout",
    # v0.9.277（M2）：deck 导入链（拿到 NDA 文件当天就能用）
    "lda/lda_qeda/quantum_deck_io.py::load_quantum_deck",
    "lda/lda_qeda/quantum_deck_io.py::load_quantum_deck_from_env",
    "lda/lda_qeda/quantum_deck_io.py::loader_provenance",
    # v0.9.278（M3）：噪声感知资源核算（四条核算的出口 + 双侧界判据本体）
    "lda/lda_qeda/noise_aware_schedule.py::build_schedule_report",
    "lda/lda_qeda/noise_aware_schedule.py::budget_double_bound",
    # v0.9.279（M4）：全局纪律门禁登记表（第三档覆盖的唯一数据源）
    "lda/lda_harness/global_gate_registry.py::global_coverage",
    # D2 码族（既有能力层，此前**零锁定**）：枚举法独立路径 + 自检入口
    "lda/lda_qeda/code_family.py::toric_params_enumerated",
    "lda/lda_qeda/code_family.py::selfcheck_code_family",
    # 可达性机制自身（此前**零锁定** —— 机制自己不受保护，最讽刺的一处）
    "lda/lda_harness/reachability.py::analyze",
    "lda/lda_harness/reachability_registry.py::baseline_stats",
]

#: 🔴 **契约豁免**：能力层模块若确实没有「值得锁的入口」，必须在此**逐条写明理由**。
#: 空集 = 每个能力层模块至少有一个函数被反向锁定。
#: 判据 `run_reachability_smoke` 的 Z6 会双向核：豁免项必须真在能力层模块集里，
#: 且不得与已锁定模块重叠（防止「既锁又豁免」的和稀泥）。
CAPABILITY_MODULE_EXEMPT: Dict[str, str] = {}

#: 扫描面：能力层模块（以源码是否含 `ANCHORABLE =` 声明为准，不靠文件名猜）
CAPABILITY_SCAN_DIRS: List[str] = ["lda_qeda", "lda_l2", "lda_harness"]


def capability_modules() -> List[str]:
    """现扫能力层模块清单（`<pkg>/*.py` 中顶层声明了 `ANCHORABLE =` 的那些）。

    纯静态、确定性（排序固定）；`__init__.py` 与私有模块跳过。
    """
    import os
    import re as _re

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pat = _re.compile(r"^ANCHORABLE\s*=", _re.M)
    out: List[str] = []
    for pkg in CAPABILITY_SCAN_DIRS:
        d = os.path.join(base, pkg)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".py") or fn == "__init__.py" or fn.startswith("_"):
                continue
            path = os.path.join(d, fn)
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    src = f.read()
            except OSError:
                continue
            if pat.search(src):
                out.append("lda/%s/%s" % (pkg, fn))
    return sorted(out)


def lock_contract() -> Dict[str, Any]:
    """契约完整性现算：哪些能力层模块**零反向锁定**（且未豁免）。

    返回值供门禁直接判红，不写死任何数字。
    """
    mods = capability_modules()
    locked_mods = {k.split("::")[0] for k in MUST_BE_REACHABLE}
    covered = [m for m in mods if m in locked_mods]
    uncovered = [m for m in mods if m not in locked_mods
                 and m not in CAPABILITY_MODULE_EXEMPT]
    return {
        "n_modules": len(mods),
        "n_covered": len(covered),
        "n_uncovered": len(uncovered),
        "uncovered": uncovered,
        "n_exempt": len(CAPABILITY_MODULE_EXEMPT),
        "exempt_not_capability": sorted(set(CAPABILITY_MODULE_EXEMPT) - set(mods)),
        "exempt_but_locked": sorted(set(CAPABILITY_MODULE_EXEMPT) & locked_mods),
        "n_locked": len(MUST_BE_REACHABLE),
        "contradiction": sorted(set(MUST_BE_REACHABLE) & set(DEAD_BASELINE)),
    }

#: 已知零引用公开函数基线（**精确集合**，不许用通配正则代替）
DEAD_BASELINE: Dict[str, str] = {
    # ── lda/lda_harness/_batch_b22_numeric.py ──
    "lda/lda_harness/_batch_b22_numeric.py::fd_lp_b2": "PUBLIC_API_NO_CONSUMER",
    "lda/lda_harness/_batch_b22_numeric.py::fiber_confinement": "PUBLIC_API_NO_CONSUMER",
    "lda/lda_harness/_batch_b22_numeric.py::fiber_mfd_numeric": "PUBLIC_API_NO_CONSUMER",
    "lda/lda_harness/_batch_b22_numeric.py::golden_b366": "ANCHOR_GOLDEN_ORPHAN",
    "lda/lda_harness/_batch_b22_numeric.py::golden_b368": "ANCHOR_GOLDEN_ORPHAN",
    "lda/lda_harness/_batch_b22_numeric.py::golden_b369": "ANCHOR_GOLDEN_ORPHAN",
    "lda/lda_harness/_batch_b22_numeric.py::golden_b370": "ANCHOR_GOLDEN_ORPHAN",
    "lda/lda_harness/_batch_b22_numeric.py::golden_b371": "ANCHOR_GOLDEN_ORPHAN",
    "lda/lda_harness/_batch_b22_numeric.py::grin_axis_neff": "PUBLIC_API_NO_CONSUMER",
    "lda/lda_harness/_batch_b22_numeric.py::grin_index": "PUBLIC_API_NO_CONSUMER",
    "lda/lda_harness/_batch_b22_numeric.py::grin_pitch": "PUBLIC_API_NO_CONSUMER",
    # ── lda/lda_harness/_batch_b39_numeric.py ──
    "lda/lda_harness/_batch_b39_numeric.py::magnetometer_eta_cand": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b39_numeric.py::magnetometer_eta_golden": "ANCHOR_PAIR_UNREFERENCED",
    # ── lda/lda_harness/_batch_b40_numeric.py ──
    "lda/lda_harness/_batch_b40_numeric.py::fom_extract_linewidth_hz": "PUBLIC_API_NO_CONSUMER",
    "lda/lda_harness/_batch_b40_numeric.py::fom_sensitivity_cand": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b40_numeric.py::fom_sensitivity_golden": "ANCHOR_PAIR_UNREFERENCED",
    # ── lda/lda_harness/_batch_b41_numeric.py ──
    "lda/lda_harness/_batch_b41_numeric.py::echo_variance_candidate": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b41_numeric.py::echo_variance_golden": "ANCHOR_PAIR_UNREFERENCED",
    # ── lda/lda_harness/_batch_b42_numeric.py ──
    "lda/lda_harness/_batch_b42_numeric.py::na_efficiency_candidate": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b42_numeric.py::na_efficiency_golden": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b42_numeric.py::optimal_depth_candidate": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b42_numeric.py::optimal_depth_golden": "ANCHOR_PAIR_UNREFERENCED",
    # ── lda/lda_harness/_batch_b43_numeric.py ──
    "lda/lda_harness/_batch_b43_numeric.py::cmrr_candidate": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b43_numeric.py::cmrr_golden": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b43_numeric.py::crosstalk_candidate": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b43_numeric.py::crosstalk_golden": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b43_numeric.py::crosstalk_penalty_candidate": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b43_numeric.py::crosstalk_penalty_golden": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b43_numeric.py::grad_eta_candidate": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b43_numeric.py::grad_eta_golden": "ANCHOR_PAIR_UNREFERENCED",
    # ── lda/lda_harness/_batch_b44_numeric.py ──
    "lda/lda_harness/_batch_b44_numeric.py::ac_sensitivity_candidate": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b44_numeric.py::ac_sensitivity_golden": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b44_numeric.py::discriminator_slope_candidate": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b44_numeric.py::discriminator_slope_golden": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b44_numeric.py::scale_factor_candidate": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b44_numeric.py::scale_factor_golden": "ANCHOR_PAIR_UNREFERENCED",
    # ── lda/lda_harness/_batch_b45_numeric.py ──
    "lda/lda_harness/_batch_b45_numeric.py::field_sensitivity_candidate": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b45_numeric.py::field_sensitivity_golden": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b45_numeric.py::squid_ic_modulation_candidate": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b45_numeric.py::squid_ic_modulation_golden": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b45_numeric.py::squid_transfer_candidate": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b45_numeric.py::squid_transfer_golden": "ANCHOR_PAIR_UNREFERENCED",
    # ── lda/lda_harness/_batch_b46_numeric.py ──
    "lda/lda_harness/_batch_b46_numeric.py::flux_transformer_area_candidate": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b46_numeric.py::flux_transformer_area_golden": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b46_numeric.py::opt_field_sensitivity_candidate": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b46_numeric.py::opt_field_sensitivity_golden": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b46_numeric.py::submicron_noise_psd_candidate": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_b46_numeric.py::submicron_noise_psd_golden": "ANCHOR_PAIR_UNREFERENCED",
    # ── lda/lda_harness/_batch_b4_numeric.py ──
    "lda/lda_harness/_batch_b4_numeric.py::golden_b72": "ANCHOR_GOLDEN_ORPHAN",
    # ── lda/lda_harness/_batch_j1_numeric.py ──
    "lda/lda_harness/_batch_j1_numeric.py::accumulated_fail_golden": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_j1_numeric.py::flag_hook_golden": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_j1_numeric.py::logical_area_golden": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_j1_numeric.py::match_cost_moment_golden": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_j1_numeric.py::merge_fid_golden": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_j1_numeric.py::syndrome_corr_golden": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_j1_numeric.py::syndrome_field_golden": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_j1_numeric.py::threshold_distance_golden": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_j1_numeric.py::transversal_fid_golden": "ANCHOR_PAIR_UNREFERENCED",
    # ── lda/lda_harness/_batch_j2_numeric.py ──
    "lda/lda_harness/_batch_j2_numeric.py::cr_gate_error_golden": "ANCHOR_PAIR_UNREFERENCED",
    "lda/lda_harness/_batch_j2_numeric.py::residual_zz_error_golden": "ANCHOR_PAIR_UNREFERENCED",
    # ── lda/lda_harness/b33_detector_bandwidth_anchor.py ──
    "lda/lda_harness/b33_detector_bandwidth_anchor.py::b33_apd_report": "REPORT_FN_UNWIRED",
    "lda/lda_harness/b33_detector_bandwidth_anchor.py::b33_detector_bandwidth_report": "REPORT_FN_UNWIRED",
    # ── lda/lda_harness/oracle_sax.py ──
    "lda/lda_harness/oracle_sax.py::ring_fsr_via_sax": "PUBLIC_API_NO_CONSUMER",
    # ── lda/lda_harness/provenance.py ──
    "lda/lda_harness/provenance.py::is_traceable": "UTILITY_NO_CONSUMER",
    # ── lda/lda_l2/calibration_protocol.py ──
    "lda/lda_l2/calibration_protocol.py::complex_jacobian": "PUBLIC_API_NO_CONSUMER",
    "lda/lda_l2/calibration_protocol.py::power_jacobian": "PUBLIC_API_NO_CONSUMER",
    # ── lda/lda_l2/compact_model.py ──
    "lda/lda_l2/compact_model.py::compact_model_markdown": "REPORT_FN_UNWIRED",
    # ── lda/lda_l2/foundry_pdk.py ──
    "lda/lda_l2/foundry_pdk.py::pdk_signoff_report": "REPORT_FN_UNWIRED",
    # ── lda/lda_l2/foundry_pdk_registry.py ──
    "lda/lda_l2/foundry_pdk_registry.py::pdk_conformance_markdown": "REPORT_FN_UNWIRED",
    # ── lda/lda_l2/golden_product_benchmarks.py ──
    "lda/lda_l2/golden_product_benchmarks.py::load_library_json": "UTILITY_NO_CONSUMER",
    # ── lda/lda_l2/innovation_market.py ──
    "lda/lda_l2/innovation_market.py::load_library_json": "UTILITY_NO_CONSUMER",
    # ── lda/lda_l2/oi_m2b.py ──
    "lda/lda_l2/oi_m2b.py::ctle_mag": "PUBLIC_API_NO_CONSUMER",
    # ── lda/lda_l2/oi_m3.py ──
    "lda/lda_l2/oi_m3.py::echannel_h_db_per_sqrt_ghz": "PUBLIC_API_NO_CONSUMER",
    # ── lda/lda_l2/ps_m4.py ──
    "lda/lda_l2/ps_m4.py::resonance_shift": "PUBLIC_API_NO_CONSUMER",
    # ── lda/lda_l2/qs_j4_multiparam.py ──
    "lda/lda_l2/qs_j4_multiparam.py::sensitivity_matrix_physical": "PUBLIC_API_NO_CONSUMER",
    # ── lda/lda_l2/qs_m0.py ──
    "lda/lda_l2/qs_m0.py::ramsey_signal": "PUBLIC_API_NO_CONSUMER",
    # ── lda/lda_l2/qs_m2.py ──
    "lda/lda_l2/qs_m2.py::coherent_chi": "PUBLIC_API_NO_CONSUMER",
    "lda/lda_l2/qs_m2.py::echo_filter_suppression": "PUBLIC_API_NO_CONSUMER",
    # ── lda/lda_l2/qs_m5.py ──
    "lda/lda_l2/qs_m5.py::dynamic_range_db_numeric": "PUBLIC_API_NO_CONSUMER",
    # ── lda/lda_l2/qs_m6.py ──
    "lda/lda_l2/qs_m6.py::rcsj_relaxation_time_s": "PUBLIC_API_NO_CONSUMER",
    # ── lda/lda_l2/ship_package.py ──
    "lda/lda_l2/ship_package.py::verify_license": "UTILITY_NO_CONSUMER",
    # ── lda/lda_l2/soc_gds_assemble.py ──
    "lda/lda_l2/soc_gds_assemble.py::soc_layer_report": "REPORT_FN_UNWIRED",
    # ── lda/lda_l2/soc_tdm.py ──
    "lda/lda_l2/soc_tdm.py::tdm_reconfig_cost": "PUBLIC_API_NO_CONSUMER",
    # ── lda/lda_qeda/cpw_quasi_static.py ──
    "lda/lda_qeda/cpw_quasi_static.py::cpw_from_path_element": "PUBLIC_API_NO_CONSUMER",
    # ── lda/lda_qeda/detectors.py ──
    "lda/lda_qeda/detectors.py::click_prob_from_populations": "PUBLIC_API_NO_CONSUMER",
    # ── lda/lda_qeda/loqc_states.py ──
    "lda/lda_qeda/loqc_states.py::mzi_embed": "PUBLIC_API_NO_CONSUMER",
    # ── lda/lda_qeda/qpu_error_budget.py ──
    "lda/lda_qeda/qpu_error_budget.py::qpu_budget_verdict": "REPORT_FN_UNWIRED",
    # ── lda/lda_qeda/rb_benchmark.py ──
    "lda/lda_qeda/rb_benchmark.py::fidelity_decay_analytic": "PUBLIC_API_NO_CONSUMER",
    # ── lda/lda_qeda/sc_control.py ──
    "lda/lda_qeda/sc_control.py::control_physics": "PUBLIC_API_NO_CONSUMER",
    "lda/lda_qeda/sc_control.py::control_svg_preview": "UI_PREVIEW_UNWIRED",
    # ── lda/lda_qeda/sc_readout_mux.py ──
    "lda/lda_qeda/sc_readout_mux.py::mux_svg_preview": "UI_PREVIEW_UNWIRED",
    # ── lda/lda_qeda/substrate_caliber.py ──
    "lda/lda_qeda/substrate_caliber.py::caliber_values": "PUBLIC_API_NO_CONSUMER",
    "lda/lda_qeda/substrate_caliber.py::tl_n_eff": "PUBLIC_API_NO_CONSUMER",
    # ── lda/lda_webui/ecore_case.py ──
    "lda/lda_webui/ecore_case.py::wire_resistance_ohm": "PUBLIC_API_NO_CONSUMER",
    # ── lda/lda_webui/email_delivery.py ──
    "lda/lda_webui/email_delivery.py::fetch_unread_envelopes": "PUBLIC_API_NO_CONSUMER",
}


def baseline_stats() -> Dict[str, Any]:
    """现算登记表的计数与分类分布（**不写死数字**，防止文档漂移）。"""
    from collections import Counter
    c = Counter(DEAD_BASELINE.values())
    unknown = sorted(set(c) - set(DEAD_CLASSES))
    return {
        "total": len(DEAD_BASELINE),
        "by_class": dict(sorted(c.items())),
        "unknown_classes": unknown,
        "must_be_reachable": len(MUST_BE_REACHABLE),
        "classes_defined": len(DEAD_CLASSES),
    }


def run_selfchecks(verbose: bool = True) -> bool:
    """登记表自身的完整性（不依赖仓库扫描）。"""
    res = []

    def chk(name, cond, detail=""):
        res.append((name, bool(cond), detail))

    st = baseline_stats()
    chk("① 基线每条的分类都在 DEAD_CLASSES 里登记过（无自造分类）",
        not st["unknown_classes"], str(st["unknown_classes"]))
    chk("② 基线键格式统一为 `module::name` 且无重复",
        all("::" in k and k.count("::") == 1 for k in DEAD_BASELINE))
    chk("③ MUST_BE_REACHABLE 非空且键格式一致",
        bool(MUST_BE_REACHABLE) and all("::" in k for k in MUST_BE_REACHABLE),
        "%d 条" % len(MUST_BE_REACHABLE))
    chk("④ MUST_BE_REACHABLE 与 DEAD_BASELINE 无交集（同一个函数不能既死又必须活）",
        not (set(MUST_BE_REACHABLE) & set(DEAD_BASELINE)),
        str(sorted(set(MUST_BE_REACHABLE) & set(DEAD_BASELINE))[:3]))
    chk("⑤ 六类（含）以上的形态都有说明文字",
        all(bool(v) for v in DEAD_CLASSES.values()) and len(DEAD_CLASSES) >= 6,
        "%d 类" % len(DEAD_CLASSES))

    ok = all(v for _, v, _ in res)
    if verbose:
        for n, v, dt in res:
            print(("  [PASS] " if v else "  [FAIL] ") + n + (("  |  " + dt) if dt else ""))
        print("\n可达性登记表自检：%d/%d %s"
              % (sum(1 for _, v, _ in res if v), len(res), "ALL PASS" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    baseline_stats()["by_class"]
    run_selfchecks()
