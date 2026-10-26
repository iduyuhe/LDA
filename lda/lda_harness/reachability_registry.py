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

from typing import Any, Dict, List, Optional, Sequence, Tuple

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
    # v0.9.306：d2 码容量阈值标定的三个入口 —— 它们若变回死函数，说明 L 节判据被拆了
    #   （「阈值是算出来的不是拟合出来的」这条结论就再无人守）。
    "lda/lda_l2/d2_threshold_mc.py::pfail_closed",
    "lda/lda_l2/d2_threshold_mc.py::crossing_closed",
    "lda/lda_l2/d2_threshold_mc.py::pfail_mc_pair",
    # v0.9.308：编译/映射（真嵌入）的三个入口 —— 它们若变回死函数，说明 K 节判据被拆了
    #   （「度 ≥ 4 只是必要条件、搜不到 ≠ 不存在」这两条结论就再无人守）。
    "lda/lda_qeda/sc_embedding.py::native_verdict",
    "lda/lda_qeda/sc_embedding.py::min_square_side",
    "lda/lda_qeda/sc_embedding.py::verify_map",
    # v0.9.309：时空解码器的三个入口 —— 若变回死函数，M 节判据就被拆了，
    #   「最小权 = 最大似然」与「阈值掉进百分量级」两条结论就再无人守。
    "lda/lda_l2/d2_spacetime_decoder.py::min_weight_decode",
    "lda/lda_l2/d2_spacetime_decoder.py::run_mc",
    "lda/lda_l2/d2_spacetime_decoder.py::brute_force_census",
    # v0.9.310：FAU 公差分布口径的三个入口 —— 若变回死函数，S 节判据就被拆了，
    #   「±tol 这句话单独不确定」与「角点是 3σ 期望的 4.5 倍」两条结论就再无人守。
    "lda/lda_l2/oi_fau_yield.py::convention_table",
    "lda/lda_l2/oi_fau_yield.py::yield_closed",
    "lda/lda_l2/oi_fau_yield.py::corner_vs_expected",
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
    # v0.9.280（D-228 · F-11）：独立性证据分档器
    #   `classify` 被 `run_harness.py`（生成证据）与门禁（反向探针）共用；
    #   `summary_of` 被 `report.py`（输出分布）与门禁（守恒判据）共用。
    #   🔴 这两个函数一旦变死，就等于「证据分档的接线被拆了」——
    #      报告会静默回落到「只有 passed」的旧状态，正是 F-11 要防的复发。
    "lda/lda_harness/independence_evidence.py::classify",
    "lda/lda_harness/independence_evidence.py::summary_of",
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
    # ── lda/lda_agent/*.py（v0.9.281 · D-229 · M7：扫描面扩容后才可见）──
    # 🔴 这两条**不是新产生的死代码**，而是「此前没人看」：`lda_agent` 从未进过
    #    `reachability.DEFAULT_TARGET_DIRS`。扫描面补入后一次性暴露 ⇒ 按纪律登记，
    #    不为了让数字好看去删代码，也不假装它们不存在。
    "lda/lda_agent/drc_fix_loop.py::demo_fix": "PUBLIC_API_NO_CONSUMER",
    "lda/lda_agent/inverse_design.py::list_designs": "PUBLIC_API_NO_CONSUMER",
    # ── 公开辅助函数（v0.9.298 · 可达性门禁**红了一段时间无人知**：它不在发布前子集里）──
    # 🔴 这三条与上面 `lda_agent` 同型：**不是新写出来的死代码**，而是「门禁没跑就一直没人看」。
    #    v0.9.298 跑通该门禁时一次性暴露 6 条：其中 3 条是 v0.9.293/294 我自己留下的
    #    （`pm_thermal.thermal_resistance_k_per_mw` · `qnet_throughput.end_to_end_rate` ·
    #    `segments_throughput_sweep`）—— 那 3 条**已接线**（前者改走单一 accessor，
    #    后两者并入 `throughput_report` 的 `end_to_end_rate_per_s` / `sweep` 字段），
    #    **不在基线里**；剩下这 3 条确认是「库语义的公开入口、目前无消费者」，如实留痕：
    #      · `scan_by_category` / `forbidden_terms` 的真源 `scan()` / `FORBIDDEN` 已在用，
    #        二者只是**便于打印与反向探针**的包装；
    #      · `honest_note_of` 是 N3-d 的**统一读取入口**（约定式，等有门禁用它时删本行）。
    "lda/lda_harness/outward_claim.py::scan_by_category": "PUBLIC_API_NO_CONSUMER",
    "lda/lda_harness/outward_claim.py::forbidden_terms": "PUBLIC_API_NO_CONSUMER",
    "lda/lda_harness/signing_schema.py::honest_note_of": "PUBLIC_API_NO_CONSUMER",
}


# ===========================================================================
# 成对实现契约（v0.9.281 · D-229 · M7 · 光子域方法论回灌）
# ===========================================================================
#: 扫描面：光子侧「能力模块」两个包。**不含 lda_qeda** —— 量子侧的可锚性
#: 由各模块自己的 `ANCHORABLE` + `why_not_anchored()` 声明，机制不同不混用。
PAIRED_SCAN_DIRS: List[str] = ["lda_l2", "lda_agent"]

#: 「数值/独立方法」侧的**函数名后缀**（成对实现的第二半）
_NUMERIC_SUFFIXES: Tuple[str, ...] = (
    "_numeric", "_num", "_rk4", "_ladder", "_marching", "_fem", "_fdtd",
    "_mc", "_sim", "_candidate", "_cand", "_bisection", "_enumerated",
)
#: 「闭式/解析」侧的后缀（第一半**可带**后缀，也可以裸名，如 `odmr_lorentzian`）
_CLOSED_SUFFIXES: Tuple[str, ...] = (
    "_closed_form", "_closed", "_golden", "_analytic", "_exact",
)

#: 例外登记：模块 → 门禁文件名。**只给命名不符 `<stem>` 惯例的模块用**。
#: 空表 = 全部符惯例；出现条目必须同时在 `paired_gate_contract()["override_not_paired"]`
#: 里被判为「指向一个真的成对模块」，否则是**豁免换沉默**。
PAIRED_GATE_OVERRIDE: Dict[str, str] = {
    # 按**功能**命名而非模块名的门禁。本轮实测唯一一条：
    # `ring_loop.verify_ring` / `verify_ring_fdtd` 这对由 D-31 的「双重验证」
    # 门禁覆盖（它确实 `from lda_agent.ring_loop import ... verify_ring_fdtd`），
    # 只是文件名不叫 `run_ring_loop_smoke.py`。**方向是"补映射"，不是"免检"** ——
    # 若指向的门禁不存在或不 import 该模块，契约仍判红。
    "lda/lda_agent/ring_loop.py": "run_ring_double_verify_smoke.py",
    # v0.9.306：`d2_threshold_mc` 的成对实现（闭式二项尾 ⇄ Monte-Carlo/二分求根）
    # 由 **d2 卡自己的门禁**覆盖（L 节 6 条：`from lda_l2 import d2_threshold_mc`），
    # 不新开 `run_d2_threshold_mc_smoke.py` —— 新开 CORE 成员要走「七处 + 3h 全量重跑」，
    # 而这条能力的判据本来就属于 d2 卡。**同样不是免检**：门禁必须真 import 该模块。
    "lda/lda_l2/d2_threshold_mc.py": "run_v2d2_smoke.py",
    # 🔴 v0.9.308 记录一次**没有登记**的判断：`lda_qeda/sc_embedding` 里
    #    `min_square_side`（穷尽子图同构搜索）⇄ `min_square_side_closed`（闭式 2d−1）
    #    看起来像成对实现，但 **`PAIRED_SCAN_DIRS` 只扫 `lda_l2` / `lda_agent`，不含
    #    `lda_qeda`**（量子侧可锚性由各模块 `ANCHORABLE` + `why_not_anchored()` 管，
    #    机制不混用）。所以这里**不登记** —— 登记了会被 `override_not_paired` 判红
    #    （实测：加进去当场红）。这对的一致性由 `run_j2_qpu_smoke` K6 逐值对拍，
    #    但那是**判据**，不是「成对实现契约」的一部分。别把两者混成一张表。
}


def _top_level_public_fns(path: str) -> List[str]:
    """模块顶层公开函数名（跳过 `_` 前缀；保持源码顺序 ⇒ 确定性）。"""
    import ast
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            tree = ast.parse(fh.read())
    except (OSError, SyntaxError):
        return []
    return [n.name for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not n.name.startswith("_")]


def paired_implementation_modules() -> Dict[str, List[Tuple[str, str]]]:
    """现算「成对实现」模块：模块内同时有**闭式**与**独立数值**两条实现。

    判据（**结构性**，不靠散文关键词，也不靠文件名猜）：

    ① 裸名配对：`X` 与 `X<suffix>` 同时存在（`odmr_lorentzian` ⇄ `odmr_lorentzian_numeric`）
    ② 后缀配对：`X_closed` 与 `X<suffix>` 同时存在（`mode_volume_closed` ⇄ `mode_volume_numeric`）

    🔴 为什么这个信号值得立契约：**成对实现 = 天然的锚候选**（golden 与 candidate
       都已在模块里写好）。M7 结构扫描实测 **10/10** 个这样的模块都配了专属门禁，
       但这条依赖是**惯例**而非机制 —— 新模块一旦加了对函数却不写门禁，
       那对实现就是"做了但没人验"，与 F-11（声明存在、机器面无）同族。
    """
    import os

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out: Dict[str, List[Tuple[str, str]]] = {}
    for pkg in PAIRED_SCAN_DIRS:
        d = os.path.join(base, pkg)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".py") or fn == "__init__.py" or fn.startswith("_"):
                continue
            path = os.path.join(d, fn)
            fns = _top_level_public_fns(path)
            fset = set(fns)
            pairs: List[Tuple[str, str]] = []
            for f in fns:
                for suf in _NUMERIC_SUFFIXES:
                    if f.endswith(suf):
                        stem = f[:-len(suf)]
                        if stem and stem in fset and (stem, f) not in pairs:
                            pairs.append((stem, f))
                for suf in _CLOSED_SUFFIXES:
                    if f.endswith(suf):
                        stem = f[:-len(suf)]
                        for g in fns:
                            if (g != f and g.startswith(stem)
                                    and any(g.endswith(x) for x in _NUMERIC_SUFFIXES)
                                    and (f, g) not in pairs):
                                pairs.append((f, g))
            if pairs:
                out["lda/%s/%s" % (pkg, fn)] = sorted(pairs)
    return out


def _gate_imports_module(gate_path: str, pkg: str, stem: str) -> bool:
    """门禁是否**真的拿到了**该模块（AST 判据，不看散文）。

    接受的三种形态（都是**结构性**证据，不是文本匹配）：

    1. `import lda_l2.qs_m3c` / `import lda_l2.qs_m3c as M`
    2. `from lda_l2 import qs_m3c` / `from lda_l2.qs_m3c import X`
    3. `importlib.import_module("lda_l2.qs_m3c")` —— 含 `_M3 = "lda_l2.oi_m3"`
       再 `import_module(_M3)` 这种**先赋给模块级常量**的写法（本轮就踩到：
       `run_oi_m3_smoke.py` 正是这么写的，第一版判据把它误判成"没 import"）。

    🔴 **刻意不认「文档字符串里出现了模块名」**：那正是文本代理（K4 的锚号字面量
       教训）。`run_oi_m3_smoke.py` 的 docstring 里就有 `lda_l2.oi_m3`，若把它算
       证据，任意门禁只要在注释/说明里写一句就能"满足"契约 —— 判据立刻失去判别力。
    """
    import ast
    try:
        with open(gate_path, encoding="utf-8", errors="replace") as fh:
            src = fh.read()
        tree = ast.parse(src)
    except (OSError, SyntaxError):
        return False
    want = "%s.%s" % (pkg, stem)

    # ① 模块级字符串常量 → 名字（供 import_module(NAME) / patch(NAME, ...) 解析）
    consts: Dict[str, str] = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) \
                and isinstance(n.value.value, str):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    consts[t.id] = n.value.value

    def _hits_call_arg(node) -> bool:
        """调用参数位置出现 `want`（字面量或指向它的模块级常量）。"""
        for n in ast.walk(node):
            if not isinstance(n, ast.Call):
                continue
            fname = ""
            f = n.func
            if isinstance(f, ast.Attribute):
                fname = f.attr
            elif isinstance(f, ast.Name):
                fname = f.id
            if fname not in ("import_module", "patch"):
                continue
            for a in n.args:
                if isinstance(a, ast.Constant) and a.value == want:
                    return True
                if isinstance(a, ast.Name) and consts.get(a.id) == want:
                    return True
        return False

    # ③ `_M3 = "lda_l2.oi_m3"` 且该常量在别处被**读取**（如 `def _mod(name: str = _M3)`）
    #    —— 仍是结构性证据：值出现在**表达式位置**，不是文档字符串里的叙述。
    for _nm, _v in consts.items():
        if _v != want:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Name) and n.id == _nm and isinstance(n.ctx, ast.Load):
                return True

    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            if (n.module or "") == want:
                return True
            # `from lda_l2 import qs_m3c` 形态
            if (n.module or "") == pkg and any(a.name == stem for a in n.names):
                return True
        elif isinstance(n, ast.Import):
            if any(a.name == want for a in n.names):
                return True
    return _hits_call_arg(tree)


def paired_gate_contract(core: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """成对实现 ⇄ 专属门禁 的契约完整性现算（不写死任何数字）。

    `core` 传 CI 门禁清单时，额外要求**门禁真的在 CI 里跑**（`gate_in_core`）。

    🔴 为什么需要这一层：只判"文件存在 + import 了模块"能被一个**永不被执行**的
       门禁文件糊弄过去 —— 那就是"写了门禁但没人跑"，与「子集全绿 ≠ 全量绿」
       是同一类失效。本版实测 12/12 都在 `CORE_SMOKES` 里，所以这条**起步即绿**，
       作用是棘轮：新加的成对实现不能配一个不跑的门禁。
    """
    import os

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    core_set = set(core) if core is not None else None
    mods = paired_implementation_modules()
    details: Dict[str, Dict[str, Any]] = {}
    ungated: List[str] = []
    not_in_core: List[str] = []
    for rel, pairs in sorted(mods.items()):
        _, pkg, fn = rel.split("/")
        stem = fn[:-3]
        gate = PAIRED_GATE_OVERRIDE.get(rel) or ("run_%s_smoke.py" % stem)
        gate_path = os.path.join(base, gate)
        exists = os.path.isfile(gate_path)
        imports = exists and _gate_imports_module(gate_path, pkg, stem)
        in_core = (gate in core_set) if core_set is not None else None
        details[rel] = {"pairs": len(pairs), "gate": gate,
                        "gate_exists": exists, "gate_imports": bool(imports),
                        "gate_in_core": in_core}
        if not (exists and imports):
            ungated.append(rel)
        elif in_core is False:
            not_in_core.append(rel)
    return {
        "n_modules": len(mods),
        "n_pairs": sum(len(v) for v in mods.values()),
        "n_gated": len(mods) - len(ungated),
        "ungated": ungated,
        "not_in_core": not_in_core,
        "core_checked": core_set is not None,
        "modules": sorted(mods),
        "details": details,
        "override_not_paired": sorted(set(PAIRED_GATE_OVERRIDE) - set(mods)),
        "n_override": len(PAIRED_GATE_OVERRIDE),
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
