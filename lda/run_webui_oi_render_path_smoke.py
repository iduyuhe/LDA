# -*- coding: utf-8 -*-
"""WebUI 光联接模块 M0 + M1 + M2 + M2b + M3 + M4 案例卡前端**取值路径 + onclick**门禁（新征程 · 2026-10-02）。

═══════════════════════════════════════════════════════════════════════════
为什么存在（血案 #18 / #19 机器化）
═══════════════════════════════════════════════════════════════════════════
E17-e 生产实测：`renderECore` 取 `synthesis_law.serial_ns`，而该值实际在
`synthesis_law.demo.serial_ns` ⇒ **三格显示 0.0**。后端侧一切门禁
（案例卡 B1–B24 / API 验收）**都看不到这一层**：它们只保证 JSON 里有值，
**不保证前端问对了地方**。

本门禁把 `renderOi`（`sec-oi` 面板）的每条取值路径（M0 根块 + M1 / M2 / M2b / M3 / M4 子块），
逐条拿到真实 `oi_case.case_card()` JSON 上解析，并验证 `onclick` 接线反向
完备——把「JSON 里有值 ≠ 前端问对了地方」这层钉死。

───────────────────────────────────────────────────────────────────────────
判什么
───────────────────────────────────────────────────────────────────────────
1. **onclick 接线**：$('runOi').onclick = runOi 在场（防「能力上线却点不动」）。
2. **函数定义**：runOi / renderOi 在 index.html 内定义（且真的含 M1/M2/M3/M4 块引用
   + ㉔–㉘ 五个表头 + ㉙–㉞ 六个表头，防「后端加了 M4、前端还是 M0–M3 壳」）。
3. **路径存在性**：renderOi 引用的每条 d./m1./rp./dv./sp./fx./rq./c./m./g./
   m2./m2rp./m2dv./m2g./m2fec./m2cf./m2rs./m2fm./m2b*/./m3./m3t./m3e./m3f./
   m3n./m3p./m3th./m3cl./m3pw./m3ly./m3os./m3ru./m3r2./m3r4./
   m4./m4c./m4p./m4r./m4fm./m4fx./m4x./m4q./pt./m4vl./m4w./m4b./m4s. 取值路径，在真实 JSON
   上逐段解析；**任一段不存在 ⇒ 红**（血案 #18/#19 要抓的）。
4. **反向完备**：case_card() 下每个展示字段——channels 元素、requested 子字段、
   milestones/gaps 元素字段，**以及 M1 块顶层 + `ring_plan` / `driver` /
   `spec_points[]` / `m0_fixes[]` 四组嵌套字段 + M2 块顶层 + `fec` /
   `fec.concatenated` / `fec.rs_only` / `fec.form_map` / `ring_plan` / `driver` /
   `spec_points[]` / `g_oi2` / `platform_fixes_m2[]` 九组嵌套字段 + M2b 十一格
   + **M3 十六格**（顶层 / twmzm / echannel / fdtd_telegraph / next / pdn /
   thermal / closed_loop_thermal / power / power.cpo / power.pluggable /
   layout_2p5d / layout_2p5d.oe_stats / reuse / reuse.at_200g / reuse.at_400g）
   + **M4 十三格**（顶层 / chain / prebias / replan / forms /
   forms.forms[CPO|OBO|pluggable] / cte / pareto / pareto.points[] / pareto.vpi_l /
   feasibility_wall / band_lock / slope_lock）**
   ——都必须被前端引用（防「后端加了、前端不显示」的静默盲区）。🔴 M2 / M2b / M3 / M4
   块都是**后加的新成员**：若本门禁不扩，各块会静默落进盲区（正是本条纪律要防的）。
5. **突变探针**（先证能变红）：
   ① 抹掉 case_card 某 channel 字段 ⇒ ③ 路径判据必红；
   ② 删掉 onclick 接线行 ⇒ ① 接线判据必红；
   ③ 抹掉 `m1.ring_plan.m` ⇒ ③ 的 M1 路径判据必红；
   ④ 往 `m1.ring_plan` 塞一个新字段 ⇒ ④ 的 ring 反向完备必红；
   ⑤ 往 `m1` 顶层塞一个新字段 ⇒ ④ 的 m1 顶层反向完备必红；
   ⑦ 往 `m2` 顶层塞一个新字段 ⇒ ④e-6 m2 顶层反向完备必红；
   ⑧ 抹掉 `m2.spec_points[].verdict_point` ⇒ ③ 的 M2 路径判据必红；
   ⑨ 往 `m2.fec` 塞一个新字段 ⇒ ④e-7 fec 反向完备必红。
   ⑯ 往 `m3` 顶层塞新字段 ⇒ ④e-27 必红；⑰ 抹掉 `m3.twmzm.margin_db` ⇒ ③ 必红；
   ⑱ 往 `m3.power.cpo` 塞新分项 ⇒ ④e-36 必红；
   ⑲ 抹掉**前端字面量** `m3cl.residual_nm` ⇒ ③ 的 js_ref 必红（证明两端都盯）；
   ⑳ 边界正则：`m3ly.gds_sha256` 被 `…_short` 前缀包含 ⇒ 纯子串假绿 / 边界必红；
   ㉑ 往 `oe_stats` 塞新成员 ⇒ ④e-42 必红。还原后复绿（R/R2）。
   ㉕ 往 `m4` 顶层塞新字段 ⇒ ④e-43 必红；㉖ 抹掉 `m4.pareto.points[].vpi_v` ⇒ ③ 必红；
   ㉗ 往 `m4.pareto.vpi_l` 塞新字段 ⇒ ④e-52 必红；
   ㉘ 抹掉**前端字面量** `m4vl.vpi_l_gap_ratio` ⇒ ③ 的 js_ref 必红；
   ㉙ 往 `m4.pareto` 塞**豁免外**新字段 ⇒ ④e-50 仍必红（证明豁免集不是万能挡箭牌）。
   还原后复绿（R/R2/R3）。
6. 自入 CI core（防静默漏接 · 血案 #28 同族）。

🔴 M3 段的特别纪律（两处**自造假绿**已被本门禁当场抓住）：
  · `m3.echannel.note` / `m3.power.unit_note` 曾在后端有值而前端**不引用** ⇒ ③ 直接红
    ⇒ 判据抓的正是「后端加了、前端不渲染」这类静默盲区，不是走过场。
  · `layout_2p5d.oe_stats` 首版被我塞进 `M3_LAYOPT` 豁免集（理由：字段多、只渲染紧凑行）
    ⇒ 它就**完全没有反向完备守护**了（后端往里加字段没人拦）⇒ 已改为**全字段渲染**，
    豁免集只剩 `geometry` / `lvs_report`（全量嵌套报告，前端只展示摘要，
    由 ④e-38 白名单 + `run_oi_m3_smoke` C 组签核判据守）。
    🔴 一般纪律：**豁免是最后手段，且必须显式登记 + 配探针证明不是死条款。**
  · M4 同族：`m4.pareto` 的 `front` / `feasible` / `m3_design_point` 是**重复副本**
    （与 `points` 同构）⇒ 显式白名单豁免；探针㉙ 专证「豁免集不能吞掉豁免外的成员」。

🔴 诚实边界：本门禁是**静态路径检查**，不执行 JS、不看渲染是否「好看」；
值存在但**语义不对**（口径漂移）仍由 oi_case.run_selfchecks + run_oi_m0_smoke /
run_oi_m1_smoke / run_oi_m2_smoke / run_oi_m2b_smoke / run_oi_m3_smoke /
run_oi_m4_smoke 那类「卡内数字 ≡ 模块现算」判据守。二者互补：
**那些守「值对不对」，本门禁守「问对没」**。
"""
from __future__ import annotations

import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

INDEX = os.path.join(_HERE, "lda_webui", "static", "index.html")

# (JS 字面引用, JSON 路径) —— JSON 路径支持 `arr[].key` 取首元素。
ROOT_PATHS = [
    ("d.case_id", "case_id"),
    ("d.verdict", "verdict"),
    ("d.verdict_label", "verdict_label"),
    ("d.b19_passivity", "b19_passivity"),
    ("d.honest_note", "honest_note"),
    ("d.design_notes", "design_notes"),
    ("d.milestones", "milestones"),
    ("d.gaps", "gaps"),
    ("d.channels", "channels"),
]
REQUESTED_PATHS = [  # renderOi 用 `var rq=d.requested||{}` 别名
    ("d.requested", "requested"),
    ("rq.n_lanes", "requested.n_lanes"),
    ("rq.channels_nm", "requested.channels_nm"),
    ("rq.v_pi_v", "requested.v_pi_v"),
    ("rq.gc_coupling", "requested.gc_coupling"),
    ("rq.fiber_span_db", "requested.fiber_span_db"),
]
CHANNEL_PATHS = [  # `var ch=d.channels||[]` 后 `c` 为元素
    ("ch", "channels"),
    ("c.lane", "channels[].lane"),
    ("c.channel_nm", "channels[].channel_nm"),
    ("c.R_um", "channels[].R_um"),
    ("c.il_closedform_db", "channels[].il_closedform_db"),
    ("c.il_cascade_db", "channels[].il_cascade_db"),
    ("c.il_ab_diff_db", "channels[].il_ab_diff_db"),
    ("c.isolation_db", "channels[].isolation_db"),
]
MILESTONE_PATHS = [  # `m` 为 milestones 元素
    ("m.id", "milestones[].id"),
    ("m.label", "milestones[].label"),
]
GAP_PATHS = [  # `g` 为 gaps 元素
    ("g.closed", "gaps[].closed"),
    ("g.id", "gaps[].id"),
    ("g.title", "gaps[].title"),
    # 🔴 F5（v0.9.185）：缺口**闭合证据链**（`closed ⇔ evidence_ok`，由 oi_case 门禁守）
    ("g.evidence", "gaps[].evidence"),
    ("g.evidence_ok", "gaps[].evidence_ok"),
    ("g.evidence_detail", "gaps[].evidence_detail"),
]

# ── M1（800G）块：`var m1=d.m1||{}, rp=m1.ring_plan||{}, dv=m1.driver||{}` ──
M1_TOP_PATHS = [
    ("d.m1", "m1"),
    ("m1.stage_label", "m1.stage_label"),
    ("m1.n_lanes", "m1.n_lanes"),
    ("m1.baud_gbd", "m1.baud_gbd"),
    ("m1.aggregate_gbps", "m1.aggregate_gbps"),
    ("m1.target_ber_kp4", "m1.target_ber_kp4"),
    ("m1.snr_db", "m1.snr_db"),
    ("m1.worst_required_snr_db", "m1.worst_required_snr_db"),
    ("m1.snr_margin_db", "m1.snr_margin_db"),
    ("m1.f_3db_eo_ghz", "m1.f_3db_eo_ghz"),
    ("m1.worst_q", "m1.worst_q"),
    ("m1.worst_ber", "m1.worst_ber"),
    ("m1.il_min_db", "m1.il_min_db"),
    ("m1.il_max_db", "m1.il_max_db"),
    ("m1.worst_isolation_db", "m1.worst_isolation_db"),
    ("m1.driver", "m1.driver"),
    ("m1.ring_plan", "m1.ring_plan"),
    ("m1.spec_points", "m1.spec_points"),
    ("m1.m0_fixes", "m1.m0_fixes"),
    ("m1.honest_note_m1", "m1.honest_note_m1"),
]
M1_DRIVER_PATHS = [  # `dv` 为 m1.driver
    ("dv.rise_ui", "m1.driver.rise_ui"),
    ("dv.tia_ghz", "m1.driver.tia_ghz"),
    ("dv.tia_over_nyquist", "m1.driver.tia_over_nyquist"),
    ("dv.t90_closed_ps", "m1.driver.t90_closed_ps"),
    ("dv.t90_rk4_ps", "m1.driver.t90_rk4_ps"),
]
M1_RING_PATHS = [  # `rp` 为 m1.ring_plan
    ("rp.m", "m1.ring_plan.m"),
    ("rp.R_um", "m1.ring_plan.R_um"),
    ("rp.gap_um", "m1.ring_plan.gap_um"),
    ("rp.min_fsr_nm", "m1.ring_plan.min_fsr_nm"),
    ("rp.min_comb_detune_nm", "m1.ring_plan.min_comb_detune_nm"),
    ("rp.min_xt_db", "m1.ring_plan.min_xt_db"),
    ("rp.max_il_drop_db", "m1.ring_plan.max_il_drop_db"),
    ("rp.max_fsr_at_rmin_nm", "m1.ring_plan.max_fsr_at_rmin_nm"),
    ("rp.fsr_rule_rejects_span", "m1.ring_plan.fsr_rule_rejects_span"),
    ("rp.m0_default_min_xt_db", "m1.ring_plan.m0_default_min_xt_db"),
    ("rp.n_solutions", "m1.ring_plan.n_solutions"),
]
M1_SPEC_PATHS = [  # `sp` 为 m1.spec_points 元素
    ("sp.key", "m1.spec_points[].key"),
    ("sp.band", "m1.spec_points[].band"),
    ("sp.wl_nm", "m1.spec_points[].wl_nm"),
    ("sp.reach_km", "m1.spec_points[].reach_km"),
    ("sp.expect", "m1.spec_points[].expect"),
    ("sp.q", "m1.spec_points[].q"),
    ("sp.ber", "m1.spec_points[].ber"),
    ("sp.disp_penalty_db", "m1.spec_points[].disp_penalty_db"),
    ("sp.sim_penalty_db", "m1.spec_points[].sim_penalty_db"),
    ("sp.required_snr_db", "m1.spec_points[].required_snr_db"),
    ("sp.required_snr_reachable", "m1.spec_points[].required_snr_reachable"),
]
M1_FIX_PATHS = [  # `fx` 为 m1.m0_fixes 元素
    ("fx.title", "m1.m0_fixes[].title"),
    ("fx.detail", "m1.m0_fixes[].detail"),
]

# ── M2（1.6T · LPO · G-OI2 真 GDS）块：`var m2=d.m2||{}, m2rp=m2.ring_plan||{}, ...` ──
M2_TOP_PATHS = [
    ("m2.stage_label", "m2.stage_label"),
    ("m2.n_lanes", "m2.n_lanes"),
    ("m2.net_per_lane_gbps", "m2.net_per_lane_gbps"),
    ("m2.baud_gbd", "m2.baud_gbd"),
    ("m2.nyquist_ghz", "m2.nyquist_ghz"),
    ("m2.aggregate_gbps", "m2.aggregate_gbps"),
    ("m2.channels_nm", "m2.channels_nm"),
    ("m2.eo_f3db_fast_ghz", "m2.eo_f3db_fast_ghz"),
    ("m2.eo_f3db_legacy_ghz", "m2.eo_f3db_legacy_ghz"),
    ("m2.bandwidth_headroom_fast_ghz", "m2.bandwidth_headroom_fast_ghz"),
    ("m2.bandwidth_headroom_legacy_ghz", "m2.bandwidth_headroom_legacy_ghz"),
    ("m2.snr_assumed_db", "m2.snr_assumed_db"),
    ("m2.tia_noise_snr_db", "m2.tia_noise_snr_db"),
    ("m2.fec", "m2.fec"),
    ("m2.driver", "m2.driver"),
    ("m2.ring_plan", "m2.ring_plan"),
    ("m2.spec_points", "m2.spec_points"),
    ("m2.g_oi2", "m2.g_oi2"),
    ("m2.platform_fixes_m2", "m2.platform_fixes_m2"),
    ("m2.honest_note_m2", "m2.honest_note_m2"),
]
M2_FEC_PATHS = [  # `m2fec` 为 m2.fec
    ("m2fec.concatenated", "m2.fec.concatenated"),
    ("m2fec.rs_only", "m2.fec.rs_only"),
    ("m2fec.ber_ratio", "m2.fec.ber_ratio"),
    ("m2fec.lpo_inner_code_gain_db", "m2.fec.lpo_inner_code_gain_db"),
    ("m2fec.form_map", "m2.fec.form_map"),
]
M2_FEC_MODE_PATHS = [  # `m2cf`/`m2rs` 为 m2.fec.concatenated / rs_only · `m2fm` 为 form_map
    ("m2cf.pre_fec_ber", "m2.fec.concatenated.pre_fec_ber"),
    ("m2cf.needs_module_dsp", "m2.fec.concatenated.needs_module_dsp"),
    ("m2cf.required_snr_ideal_db", "m2.fec.concatenated.required_snr_ideal_db"),
    ("m2cf.label", "m2.fec.concatenated.label"),
    ("m2rs.pre_fec_ber", "m2.fec.rs_only.pre_fec_ber"),
    ("m2rs.needs_module_dsp", "m2.fec.rs_only.needs_module_dsp"),
    ("m2rs.required_snr_ideal_db", "m2.fec.rs_only.required_snr_ideal_db"),
    ("m2rs.label", "m2.fec.rs_only.label"),
    ("m2fm.retimed", "m2.fec.form_map.retimed"),
    ("m2fm.lpo", "m2.fec.form_map.lpo"),
]
M2_DRIVER_PATHS = [  # `m2dv` 为 m2.driver
    ("m2dv.rise_ui", "m2.driver.rise_ui"),
    ("m2dv.tia_ghz", "m2.driver.tia_ghz"),
    ("m2dv.tia_over_nyquist", "m2.driver.tia_over_nyquist"),
    ("m2dv.t90_closed_ps", "m2.driver.t90_closed_ps"),
    ("m2dv.t90_rk4_ps", "m2.driver.t90_rk4_ps"),
]
M2_RING_PATHS = [  # `m2rp` 为 m2.ring_plan
    ("m2rp.m", "m2.ring_plan.m"),
    ("m2rp.R_um", "m2.ring_plan.R_um"),
    ("m2rp.gap_um", "m2.ring_plan.gap_um"),
    ("m2rp.min_xt_db", "m2.ring_plan.min_xt_db"),
    ("m2rp.max_il_drop_db", "m2.ring_plan.max_il_drop_db"),
    ("m2rp.max_fsr_at_rmin_nm", "m2.ring_plan.max_fsr_at_rmin_nm"),
    ("m2rp.fsr_rule_rejects_span", "m2.ring_plan.fsr_rule_rejects_span"),
    ("m2rp.n_solutions", "m2.ring_plan.n_solutions"),
]
M2_SPEC_PATHS = [  # `sp` 为 m2.spec_points 元素（与 M1 同名局部变量）
    ("sp.key", "m2.spec_points[].key"),
    ("sp.band", "m2.spec_points[].band"),
    ("sp.wl_nm", "m2.spec_points[].wl_nm"),
    ("sp.reach_km", "m2.spec_points[].reach_km"),
    ("sp.process", "m2.spec_points[].process"),
    ("sp.role", "m2.spec_points[].role"),
    ("sp.expect", "m2.spec_points[].expect"),
    ("sp.verdict_point", "m2.spec_points[].verdict_point"),
    ("sp.limiting_cause", "m2.spec_points[].limiting_cause"),
    ("sp.eo_f3db_ghz", "m2.spec_points[].eo_f3db_ghz"),
    ("sp.nyquist_ghz", "m2.spec_points[].nyquist_ghz"),
    ("sp.bandwidth_headroom_ghz", "m2.spec_points[].bandwidth_headroom_ghz"),
    ("sp.retimed_margin_db", "m2.spec_points[].retimed_margin_db"),
    ("sp.lpo_margin_db", "m2.spec_points[].lpo_margin_db"),
    ("sp.lpo_penalty_db", "m2.spec_points[].lpo_penalty_db"),
    ("sp.required_snr_retimed_db", "m2.spec_points[].required_snr_retimed_db"),
    ("sp.required_snr_lpo_db", "m2.spec_points[].required_snr_lpo_db"),
]
M2_GDS_PATHS = [  # `m2g` 为 m2.g_oi2
    ("m2g.n_devices", "m2.g_oi2.n_devices"),
    ("m2g.n_nets", "m2.g_oi2.n_nets"),
    ("m2g.gds_bytes", "m2.g_oi2.gds_bytes"),
    ("m2g.gds_elements", "m2.g_oi2.gds_elements"),
    ("m2g.drc_pass", "m2.g_oi2.drc_pass"),
    ("m2g.lvs_verdict", "m2.g_oi2.lvs_verdict"),
    ("m2g.lvs_n_violations", "m2.g_oi2.lvs_n_violations"),
    ("m2g.footprint_um2", "m2.g_oi2.footprint_um2"),
    ("m2g.ring_R_um", "m2.g_oi2.ring_R_um"),
    ("m2g.fiber_off_chip", "m2.g_oi2.fiber_off_chip"),
    ("m2g.layout_discipline_ok", "m2.g_oi2.layout_discipline_ok"),
]
M2_FIX_PATHS = [  # `fx` 为 m2.platform_fixes_m2 元素（与 M1 同名局部变量）
    ("fx.title", "m2.platform_fixes_m2[].title"),
    ("fx.detail", "m2.platform_fixes_m2[].detail"),
]

# ── M2b（G-OI5 · 多通道均衡/热调/热串扰Γ/良率MC/封装容差）块 ──
#    前端局部别名：m2b=d.m2b||{} · m2beq=equalizer · m2bct=ctle · m2ble=lane_equalizer
#    m2bth=thermal_tune · m2bg=crosstalk_gamma · m2by=yield · m2bp=packaging
#    m2beL=equalizer.lpo · m2beR=equalizer.retimed
M2B_TOP_PATHS = [
    ("m2b.stage_label", "m2b.stage_label"),
    ("m2b.equalizer", "m2b.equalizer"),
    ("m2b.ctle", "m2b.ctle"),
    ("m2b.lane_equalizer", "m2b.lane_equalizer"),
    ("m2b.thermal_tune", "m2b.thermal_tune"),
    ("m2b.crosstalk_gamma", "m2b.crosstalk_gamma"),
    ("m2b.yield", "m2b.yield"),
    ("m2b.packaging", "m2b.packaging"),
    ("m2b.honest_note_m2b", "m2b.honest_note_m2b"),
]
M2B_EQMODE_PATHS = [  # m2beL = m2b.equalizer.lpo · m2beR = m2b.equalizer.retimed
    ("m2beL.ctle", "m2b.equalizer.lpo.ctle"),
    ("m2beL.ffe", "m2b.equalizer.lpo.ffe"),
    ("m2beL.needs_dsp", "m2b.equalizer.lpo.needs_dsp"),
    ("m2beL.label", "m2b.equalizer.lpo.label"),
    ("m2beL.note", "m2b.equalizer.lpo.note"),
    ("m2beR.ctle", "m2b.equalizer.retimed.ctle"),
    ("m2beR.ffe", "m2b.equalizer.retimed.ffe"),
    ("m2beR.needs_dsp", "m2b.equalizer.retimed.needs_dsp"),
    ("m2beR.label", "m2b.equalizer.retimed.label"),
    ("m2beR.note", "m2b.equalizer.retimed.note"),
]
M2B_EQ_PATHS = [
    ("m2beq.why", "m2b.equalizer.why"),
]
M2B_CTLE_PATHS = [
    ("m2bct.f_z_hz", "m2b.ctle.f_z_hz"),
    ("m2bct.f_p_hz", "m2b.ctle.f_p_hz"),
    ("m2bct.boost_nom_db", "m2b.ctle.boost_nom_db"),
    ("m2bct.noise_penalty_db", "m2b.ctle.noise_penalty_db"),
    ("m2bct.noise_penalty_flat_db", "m2b.ctle.noise_penalty_flat_db"),
    ("m2bct.note", "m2b.ctle.note"),
]
M2B_LANE_PATHS = [
    ("m2ble.n_lanes", "m2b.lane_equalizer.n_lanes"),
    ("m2ble.boost_distinct", "m2b.lane_equalizer.boost_distinct"),
    ("m2ble.equalization_isi_spread", "m2b.lane_equalizer.equalization_isi_spread"),
    ("m2ble.design_roundtrip_spread_db", "m2b.lane_equalizer.design_roundtrip_spread_db"),
    ("m2ble.channel_source", "m2b.lane_equalizer.channel_source"),
    ("m2ble.flat_ok", "m2b.lane_equalizer.flat_ok"),
    ("m2ble.noise_penalty_min_db", "m2b.lane_equalizer.noise_penalty_min_db"),
    ("m2ble.noise_penalty_max_db", "m2b.lane_equalizer.noise_penalty_max_db"),
    ("m2ble.lanes", "m2b.lane_equalizer.lanes"),
]
M2B_LANE_ELEM_PATHS = [  # m2ble.lanes[] 元素
    ("l.lane", "m2b.lane_equalizer.lanes[].lane"),
    ("l.f_mod_ghz", "m2b.lane_equalizer.lanes[].f_mod_ghz"),
    ("l.boost_db", "m2b.lane_equalizer.lanes[].boost_db"),
    ("l.f_z_ghz", "m2b.lane_equalizer.lanes[].f_z_ghz"),
    ("l.pen_db", "m2b.lane_equalizer.lanes[].pen_db"),
]
M2B_THERMAL_PATHS = [
    ("m2bth.unit_note", "m2b.thermal_tune.unit_note"),
    ("m2bth.S_nm_per_mW", "m2b.thermal_tune.S_nm_per_mW"),
    ("m2bth.Ppi_mW", "m2b.thermal_tune.Ppi_mW"),
    ("m2bth.heater_length_um", "m2b.thermal_tune.heater_length_um"),
    ("m2bth.ring_R_um", "m2b.thermal_tune.ring_R_um"),
    ("m2bth.FSR_nm", "m2b.thermal_tune.FSR_nm"),
    ("m2bth.residual_detune_nm", "m2b.thermal_tune.residual_detune_nm"),
    ("m2bth.p_per_lane_mW", "m2b.thermal_tune.p_per_lane_mW"),
    ("m2bth.p_total_mW", "m2b.thermal_tune.p_total_mW"),
    ("m2bth.honest_note_m2b_thermal", "m2b.thermal_tune.honest_note_m2b_thermal"),
]
M2B_GAMMA_PATHS = [
    ("m2bg.n", "m2b.crosstalk_gamma.n"),
    ("m2bg.S_nm_per_mW", "m2b.crosstalk_gamma.S_nm_per_mW"),
    ("m2bg.diag_max_nm_per_mW", "m2b.crosstalk_gamma.diag_max_nm_per_mW"),
    ("m2bg.max_offdiag_nm_per_mW", "m2b.crosstalk_gamma.max_offdiag_nm_per_mW"),
    ("m2bg.symmetric_ok", "m2b.crosstalk_gamma.symmetric_ok"),
    ("m2bg.diagonal_max_ok", "m2b.crosstalk_gamma.diagonal_max_ok"),
    ("m2bg.monotonic_ok", "m2b.crosstalk_gamma.monotonic_ok"),
    ("m2bg.note", "m2b.crosstalk_gamma.note"),
]
M2B_YIELD_PATHS = [
    ("m2by.sigma_dn_eff", "m2b.yield.sigma_dn_eff"),
    ("m2by.tol_nm", "m2b.yield.tol_nm"),
    ("m2by.sigma_resonance_nm", "m2b.yield.sigma_resonance_nm"),
    ("m2by.yield_closed_form", "m2b.yield.yield_closed_form"),
    ("m2by.yield_mc", "m2b.yield.yield_mc"),
    ("m2by.mc_n_samples", "m2b.yield.mc_n_samples"),
    ("m2by.mc_seed", "m2b.yield.mc_seed"),
    ("m2by.note", "m2b.yield.note"),
]
M2B_PKG_PATHS = [
    ("m2bp.il_budget_db", "m2b.packaging.il_budget_db"),
    ("m2bp.il_mode_mismatch_db", "m2b.packaging.il_mode_mismatch_db"),
    ("m2bp.eta_mode", "m2b.packaging.eta_mode"),
    ("m2bp.dx_max_um", "m2b.packaging.dx_max_um"),
    ("m2bp.dx_max_numeric_um", "m2b.packaging.dx_max_numeric_um"),
    ("m2bp.temp_window_c", "m2b.packaging.temp_window_c"),
    ("m2bp.wl_drift_nm", "m2b.packaging.wl_drift_nm"),
    ("m2bp.dx_drift_um", "m2b.packaging.dx_drift_um"),
    ("m2bp.dx_tolerance_um", "m2b.packaging.dx_tolerance_um"),
    ("m2bp.temp_in_tolerance", "m2b.packaging.temp_in_tolerance"),
    ("m2bp.note", "m2b.packaging.note"),
]

M3_TOP_PATHS = [
    ("d.m3", "m3"),
    ("m3.stage_label", "m3.stage_label"),
    ("m3.honest_note_m3", "m3.honest_note_m3"),
]
M3_TWMZM_PATHS = [
    ("m3t.family", "m3.twmzm.family"),
    ("m3t.f3db_ghz", "m3.twmzm.f3db_ghz"),
    ("m3t.nyquist_ghz", "m3.twmzm.nyquist_ghz"),
    ("m3t.margin_db", "m3.twmzm.margin_db"),
    ("m3t.ratio_to_nyquist", "m3.twmzm.ratio_to_nyquist"),
    ("m3t.in_window", "m3.twmzm.in_window"),
    ("m3t.bandwidth_ok", "m3.twmzm.bandwidth_ok"),
    ("m3t.f_rc_ghz", "m3.twmzm.f_rc_ghz"),
    ("m3t.l_electrode_mm", "m3.twmzm.l_electrode_mm"),
    ("m3t.dn_g_resid", "m3.twmzm.dn_g_resid"),
    ("m3t.f_pd_ghz", "m3.twmzm.f_pd_ghz"),
    ("m3t.f_tia_ghz", "m3.twmzm.f_tia_ghz"),
    ("m3t.ladder_n_grid", "m3.twmzm.ladder_n_grid"),
    ("m3t.ladder_rel_err", "m3.twmzm.ladder_rel_err"),
    ("m3t.ladder_monotonic", "m3.twmzm.ladder_monotonic"),
    ("m3t.ladder_f_eval_ghz", "m3.twmzm.ladder_f_eval_ghz"),
    ("m3t.ladder_err_largest", "m3.twmzm.ladder_err_largest"),
    ("m3t.ladder_err_smallest", "m3.twmzm.ladder_err_smallest"),
    ("m3t.note", "m3.twmzm.note"),
]
M3_ECH_PATHS = [
    ("m3e.bus_len_mm", "m3.echannel.bus_len_mm"),
    ("m3e.f_rl_ghz", "m3.echannel.f_rl_ghz"),
    ("m3e.window_ghz", "m3.echannel.window_ghz"),
    ("m3e.h_in_window", "m3.echannel.h_in_window"),
    ("m3e.drift_in_window", "m3.echannel.drift_in_window"),
    ("m3e.sqrtf_ok", "m3.echannel.sqrtf_ok"),
    ("m3e.h_outside", "m3.echannel.h_outside"),
    ("m3e.drift_outside", "m3.echannel.drift_outside"),
    ("m3e.disclosed_outside", "m3.echannel.disclosed_outside"),
    ("m3e.note", "m3.echannel.note"),
]
M3_FDTD_PATHS = [
    ("m3f.n_cells", "m3.fdtd_telegraph.n_cells"),
    ("m3f.n_step", "m3.fdtd_telegraph.n_step"),
    ("m3f.dt_ps", "m3.fdtd_telegraph.dt_ps"),
    ("m3f.tau_closed_ps", "m3.fdtd_telegraph.tau_closed_ps"),
    ("m3f.tau_fdtd_ps", "m3.fdtd_telegraph.tau_fdtd_ps"),
    ("m3f.rel_err", "m3.fdtd_telegraph.rel_err"),
    ("m3f.peak_out_v", "m3.fdtd_telegraph.peak_out_v"),
    ("m3f.v_fdtd_m_per_s", "m3.fdtd_telegraph.v_fdtd_m_per_s"),
    ("m3f.phase_ok", "m3.fdtd_telegraph.phase_ok"),
    ("m3f.lossy_term_included", "m3.fdtd_telegraph.lossy_term_included"),
    ("m3f.note", "m3.fdtd_telegraph.note"),
]
M3_NEXT_PATHS = [
    ("m3n.k", "m3.next.k"),
    ("m3n.f_ghz", "m3.next.f_ghz"),
    ("m3n.f0_ghz", "m3.next.f0_ghz"),
    ("m3n.ratio_linear", "m3.next.ratio_linear"),
    ("m3n.xtalk_db", "m3.next.xtalk_db"),
    ("m3n.xtalk_at_zero_coupling_db", "m3.next.xtalk_at_zero_coupling_db"),
    ("m3n.note", "m3.next.note"),
]
M3_PDN_PATHS = [
    ("m3p.l_pdn_nh", "m3.pdn.l_pdn_nh"),
    ("m3p.di_dt_a_per_s", "m3.pdn.di_dt_a_per_s"),
    ("m3p.v_bounce_v", "m3.pdn.v_bounce_v"),
    ("m3p.note", "m3.pdn.note"),
]
M3_TH_PATHS = [
    ("m3th.p_asic_w", "m3.thermal.p_asic_w"),
    ("m3th.t_amb_c", "m3.thermal.t_amb_c"),
    ("m3th.d_t_interposer_c", "m3.thermal.d_t_interposer_c"),
    ("m3th.t_interposer_c", "m3.thermal.t_interposer_c"),
    ("m3th.d_t_photon_c", "m3.thermal.d_t_photon_c"),
    ("m3th.t_photon_c", "m3.thermal.t_photon_c"),
    ("m3th.die_to_die_theta_k", "m3.thermal.die_to_die_theta_k"),
    ("m3th.theta_from_m2b_network", "m3.thermal.theta_from_m2b_network"),
    ("m3th.theta_channels_agree", "m3.thermal.theta_channels_agree"),
    ("m3th.note", "m3.thermal.note"),
]
M3_CL_PATHS = [
    ("m3cl.solution", "m3.closed_loop_thermal.solution"),
    ("m3cl.r_h_k_per_mw", "m3.closed_loop_thermal.r_h_k_per_mw"),
    ("m3cl.S_nm_per_mW", "m3.closed_loop_thermal.S_nm_per_mW"),
    ("m3cl.d_lambda_dT_nm_per_k", "m3.closed_loop_thermal.d_lambda_dT_nm_per_k"),
    ("m3cl.solve_mode", "m3.closed_loop_thermal.solve_mode"),
    ("m3cl.converged", "m3.closed_loop_thermal.converged"),
    ("m3cl.S_eff_nm_per_mW", "m3.closed_loop_thermal.S_eff_nm_per_mW"),
    ("m3cl.algebraic_matches_fixed_point",
     "m3.closed_loop_thermal.algebraic_matches_fixed_point"),
    ("m3cl.double_count_diverges", "m3.closed_loop_thermal.double_count_diverges"),
    ("m3cl.t_free_c", "m3.closed_loop_thermal.t_free_c"),
    ("m3cl.t_setpoint_c", "m3.closed_loop_thermal.t_setpoint_c"),
    ("m3cl.t_ring_c", "m3.closed_loop_thermal.t_ring_c"),
    ("m3cl.residual_nm", "m3.closed_loop_thermal.residual_nm"),
    ("m3cl.residual_frac_fsr", "m3.closed_loop_thermal.residual_frac_fsr"),
    ("m3cl.residual_lt_fsr", "m3.closed_loop_thermal.residual_lt_fsr"),
    ("m3cl.FSR_nm", "m3.closed_loop_thermal.FSR_nm"),
    ("m3cl.p_actuator_mw_per_lane", "m3.closed_loop_thermal.p_actuator_mw_per_lane"),
    ("m3cl.actuator_direction", "m3.closed_loop_thermal.actuator_direction"),
    ("m3cl.unidirectional_heater_feasible",
     "m3.closed_loop_thermal.unidirectional_heater_feasible"),
    ("m3cl.note", "m3.closed_loop_thermal.note"),
]
M3_PW_TOP_PATHS = [
    ("m3pw.unit_note", "m3.power.unit_note"),
    ("m3pw.energy_per_bit_banned", "m3.power.energy_per_bit_banned"),
    ("m3pw.cpo_per_lane_mw", "m3.power.cpo_per_lane_mw"),
    ("m3pw.pluggable_per_lane_mw", "m3.power.pluggable_per_lane_mw"),
    ("m3pw.cpo_total_w", "m3.power.cpo_total_w"),
    ("m3pw.pluggable_total_w", "m3.power.pluggable_total_w"),
    ("m3pw.cpo_advantage_thermal_mw", "m3.power.cpo_advantage_thermal_mw"),
    ("m3pw.cpo_penalty_interposer_mw", "m3.power.cpo_penalty_interposer_mw"),
    ("m3pw.reconciled", "m3.power.reconciled"),
    ("m3pw.note", "m3.power.note"),
    # 🔴 M5 口径接线：主账电容口径 + 旧口径并报 + 放大口径；`flip` 是**嵌套**子块
    #   （其内部叶子由 M5_FLIP_PATHS 覆盖，此处只登记顶层键 + 前端引用）。
    ("m3pw.cap_model_used", "m3.power.cap_model_used"),
    ("m3pw.driver_cap_fF", "m3.power.driver_cap_fF"),
    ("m3pw.driver_package_line_mw", "m3.power.driver_package_line_mw"),
    ("m3pw.flip", "m3.power.flip"),
    ("m3pwfl.advantage_flips", "m3.power.flip.advantage_flips"),
    ("m3pwfl.note", "m3.power.flip.note"),
    ("m3pwfp.cpo_per_lane_mw", "m3.power.flip.package_line_cap.cpo_per_lane_mw"),
    ("m3pwfp.delta_cpo_minus_pluggable_mw",
     "m3.power.flip.package_line_cap.delta_cpo_minus_pluggable_mw"),
    ("m3pwfe.cpo_per_lane_mw", "m3.power.flip.electrode_cap.cpo_per_lane_mw"),
    ("m3pwfe.delta_cpo_minus_pluggable_mw",
     "m3.power.flip.electrode_cap.delta_cpo_minus_pluggable_mw"),
]
_PW_ITEMS = ("driver_dynamic_mw", "driver_termination_mw", "tia_static_mw",
             "ctle_analog_mw", "thermal_steady_mw", "source_pump_mw",
             "interposer_pdn_mw")
M3_PW_CPO_PATHS = [("m3pw.cpo." + k, "m3.power.cpo." + k) for k in _PW_ITEMS]
M3_PW_PLUG_PATHS = [("m3pw.pluggable." + k, "m3.power.pluggable." + k) for k in _PW_ITEMS]
M3_LAY_PATHS = [
    ("m3ly.gds_structures", "m3.layout_2p5d.gds_structures"),
    ("m3ly.gds_elements", "m3.layout_2p5d.gds_elements"),
    ("m3ly.gds_bytes_len", "m3.layout_2p5d.gds_bytes_len"),
    ("m3ly.gds_sha256", "m3.layout_2p5d.gds_sha256"),
    ("m3ly.gds_sha256_short", "m3.layout_2p5d.gds_sha256_short"),
    ("m3ly.oe_elements_reused", "m3.layout_2p5d.oe_elements_reused"),
    ("m3ly.oe_drc_pass", "m3.layout_2p5d.oe_drc_pass"),
    ("m3ly.electrical_drc_pass", "m3.layout_2p5d.electrical_drc_pass"),
    ("m3ly.fiber_in_layout", "m3.layout_2p5d.fiber_in_layout"),
    ("m3ly.oe_lvs_verdict", "m3.layout_2p5d.oe_lvs_verdict"),
    ("m3ly.oe_lvs_n_violations", "m3.layout_2p5d.oe_lvs_n_violations"),
    ("m3ly.oe_lvs_pass", "m3.layout_2p5d.oe_lvs_pass"),
    ("m3ly.oe_lvs_honest_note", "m3.layout_2p5d.oe_lvs_honest_note"),
    ("m3ly.oe_stats", "m3.layout_2p5d.oe_stats"),   # 别名赋值行 `m3os=m3ly.oe_stats||{}`
]
M3_LAY_STAT_PATHS = [   # `oe_stats` 全字段渲染；`m3os = m3ly.oe_stats||{}` 别名
    ("m3os.n_devices", "m3.layout_2p5d.oe_stats.n_devices"),
    ("m3os.n_nets", "m3.layout_2p5d.oe_stats.n_nets"),
    ("m3os.area_um2", "m3.layout_2p5d.oe_stats.area_um2"),
    ("m3os.width_um", "m3.layout_2p5d.oe_stats.width_um"),
    ("m3os.height_um", "m3.layout_2p5d.oe_stats.height_um"),
    ("m3os.bbox_um", "m3.layout_2p5d.oe_stats.bbox_um"),
    ("m3os.n_io", "m3.layout_2p5d.oe_stats.n_io"),
    ("m3os.n_elements", "m3.layout_2p5d.oe_stats.n_elements"),
    ("m3os.n_structures", "m3.layout_2p5d.oe_stats.n_structures"),
    ("m3os.gds_bytes", "m3.layout_2p5d.oe_stats.gds_bytes"),
    ("m3os.multilayer", "m3.layout_2p5d.oe_stats.multilayer"),
]
# 🔴 `layout_2p5d` 里有两项**故意不渲染**（与 ④c 的 `detail` 同族豁免，理由不同）：
#   · `geometry` / `lvs_report` = 版图几何与 LVS 报告的**全量嵌套**（几十个子字段），
#     前端只展示其**摘要**（gds_elements / oe_lvs_verdict / oe_lvs_n_violations /
#     oe_lvs_honest_note）⇒ 渲染全量会把面板撑爆、且与「紧凑行」体例冲突。
# 豁免是**显式白名单**：新成员落进这两项 ⇒ 豁免集合不含它 ⇒ ④e-38 立刻变红。
# 🔴 `oe_stats` 首版曾被我塞进这个豁免集 ⇒ 它就**没有任何反向完备守护**了
#（真盲区：后端往里加字段前端不显示，无人拦）。现已改为**全字段渲染**，
# 豁免集里不再有它 ⇒ ④e-38 直接管住它。
M3_LAYOPT = {"geometry", "lvs_report"}
M3_REUSE_TOP_PATHS = [
    ("m3ru.lane_halved", "m3.reuse.lane_halved"),
    ("m3ru.density_still_below_ceiling", "m3.reuse.density_still_below_ceiling"),
    ("m3ru.pitch_still_above_floor", "m3.reuse.pitch_still_above_floor"),
    ("m3ru.energy_floor_still_positive", "m3.reuse.energy_floor_still_positive"),
    ("m3ru.reused_not_rebuilt", "m3.reuse.reused_not_rebuilt"),
]
_REUSE_OPTIONAL = {"model", "couple_mode", "bandwidth_density_gbps_mm",
                   "density_ceiling_gbps_mm", "energy_floor_dB",
                   "shoreline_width_mm", "pitch_um", "pitch_floor_um",
                   "lane_rate_gbps", "n_channels", "total_bandwidth_tbps",
                   "per_channel_il_dB", "link_margin_db"}
M3_REUSE_200_PATHS = [("m3r2." + k, "m3.reuse.at_200g." + k)
                      for k in sorted(_REUSE_OPTIONAL)]
M3_REUSE_400_PATHS = [("m3r4." + k, "m3.reuse.at_400g." + k)
                      for k in sorted(_REUSE_OPTIONAL)]

# ── M4（CPO 形态深化 · 热-光-电协同设计空间）块：`var m4=d.m4||{}, m4c=m4.chain||{}, ...` ──
M4_TOP_PATHS = [
    ("m4.stage_label", "m4.stage_label"),
    ("m4.chain", "m4.chain"),
    ("m4.prebias", "m4.prebias"),
    ("m4.replan", "m4.replan"),
    ("m4.forms", "m4.forms"),
    ("m4.cte", "m4.cte"),
    ("m4.pareto", "m4.pareto"),
    ("m4.feasibility_wall", "m4.feasibility_wall"),
    ("m4.band_lock", "m4.band_lock"),
    ("m4.slope_lock", "m4.slope_lock"),
    ("m4.honest_note_m4", "m4.honest_note_m4"),
]
M4_CHAIN_PATHS = [("m4c." + k, "m4.chain." + k) for k in (
    "p_asic_w", "d_t_photon_k", "slope_nm_per_k", "d_lambda_self_nm",
    "d_lambda_frac_fsr", "fsr_nm", "channels_shifted", "r_h_k_per_mw",
    "p_heat_required_mw_per_lane", "p_heat_supplyable_mw_per_lane",
    "actuator_direction", "unidirectional_heater_feasible",
    "chain_consistent_with_m3_residual", "note")]
M4_PREBIAS_PATHS = [("m4p." + k, "m4.prebias." + k) for k in (
    "p_asic_w", "t_amb_c", "d_t_photon_k", "t_eq_c", "setpoint_shift_nm",
    "d_lambda_self_nm", "residual_nm_without_prebias", "residual_nm_after_prebias",
    "p_heat_without_prebias_mw_per_lane", "p_heat_after_prebias_mw_per_lane",
    "tec_required", "solution", "bi_directional_margin_needed", "note")]
M4_REPLAN_PATHS = [("m4r." + k, "m4.replan." + k) for k in (
    "wl0_cold_nm", "wl0_hot_nm", "d_lambda_nm", "fsr_nm_cold", "fsr_nm_hot",
    "fsr_rel_change", "m_baseline", "m_at_t_eq", "m_changed",
    "min_xt_db_at_t_eq", "max_il_drop_db_at_t_eq", "n_solutions_at_t_eq",
    "plan_still_valid", "note")]
M4_FORMS_TOP_PATHS = [("m4fm." + k, "m4.forms." + k) for k in (
    "forms", "order", "thermal_coupling_rank", "elec_il_rank", "fiber_il_rank",
    "theta_monotonic_with_distance", "elec_il_monotonic_with_bus", "note")]
M4_FORMS_ELEM_KEYS = ("die_dist_um", "theta_k_per_w", "bus_len_mm",
                      "il_elec_db", "il_fiber_db", "il_total_db")
M4_FORMS_ELEM_PATHS = [("m4fx.%s.%s" % (fk, k), "m4.forms.forms.%s.%s" % (fk, k))
                       for fk in ("CPO", "OBO", "pluggable") for k in M4_FORMS_ELEM_KEYS]
M4_CTE_PATHS = [("m4x." + k, "m4.cte." + k) for k in (
    "p_asic_w", "d_t_k", "cte_si_per_k", "cte_glass_fau_per_k", "cte_mismatch_per_k",
    "arm_len_mm", "mfd_w_um", "dx_um", "dx_nm", "ratio_dx_over_w", "il_cte_db",
    "assembly_tol_um", "il_assembly_db", "cte_is_dominant", "note")]
M4_PARETO_TOP_PATHS = [("m4q." + k, "m4.pareto." + k) for k in (
    "points", "n_points", "n_front", "n_dominated", "all_points_non_dominated",
    "n_infeasible_bw", "n_infeasible_vpp", "n_feasible", "feasible_collapsed",
    "feasible_l_mm", "bw_death_line_ghz", "vpp_cmos_limit_v", "m3_design_l_mm",
    "m3_design_on_front", "m3_design_feasible", "vpi_l", "note")]
M4_PARETO_PT_PATHS = [("pt.%s" % k, "m4.pareto.points[].%s" % k) for k in (
    "l_mm", "bw_ghz", "il_db", "p_drv_mw", "vpi_v", "vpp_v",
    "feasible_bw", "feasible_vpp", "feasible")]   # 前端 `m4q.points[].map(function(pt){...})`
# 🔴 `pareto` 里三项**故意不渲染**（与 ④c 的 `detail` / M3 的 `geometry` 同族豁免）：
#   · `front` / `feasible` = Pareto 前沿与可行子集的**全量嵌套点数组**（与 `points` 同构的
#     重复副本），前端已用 `points` 逐点表 + 计数（n_front/n_feasible）表达 ⇒ 渲染全量纯冗余；
#   · `m3_design_point` = M3 设计点那一行 `points` 元素（同样已在逐点表中）⇒ 重复副本。
# 豁免是**显式白名单**：新成员落进这三项之外 ⇒ ④e-M4 立刻变红（与 oe_stats 血案同族纪律）。
M4_PARETO_OPT = {"front", "feasible", "m3_design_point"}
M4_VPIL_PATHS = [("m4vl." + k, "m4.pareto.vpi_l." + k) for k in (
    "vpi_l_implied_by_m3_v_cm", "vpi_l_public_typical_v_cm", "vpi_l_public_band_v_cm",
    "vpi_l_gap_ratio", "vpp_required_at_public_vpi_l_v", "l_needed_for_m3_vpp_mm",
    "public_vpi_l_in_band", "consistent_with_public_process", "note")]
M4_WALL_PATHS = [("m4w." + k, "m4.feasibility_wall." + k) for k in (
    "public_feasible_l_mm", "m3_implied_feasible_l_mm", "public_vpi_l_feasible_points",
    "m3_implied_vpi_l_feasible_points", "public_feasible_collapsed",
    "public_narrower_than_m3", "note")]
M4_BAND_PATHS = [("m4b." + k, "m4.band_lock." + k) for k in (
    "m4_wl0_nm", "m2_wl0_nm", "m1_default_wl0_nm", "same_as_m2",
    "differs_from_m1_default", "channels_match_m2", "gap_nm", "note")]
M4_SLOPE_PATHS = [("m4s." + k, "m4.slope_lock." + k) for k in (
    "slope_m3_calibrated_nm_per_k", "slope_material_closed_nm_per_k",
    "rel_diff", "agree_within_25pct", "note")]

# ── M5（VπL 断口结算 · 可行域闭式 + 双口径对拍 + 口径翻转）路径表 ──────────
M5_TOP_PATHS = [
    ("m5.status", "m5.status"),
    ("m5.implied_vpi_l_v_cm", "m5.implied_vpi_l_v_cm"),
    ("m5.vpi_l_critical_v_cm", "m5.vpi_l_critical_v_cm"),
    ("m5.public_band_v_cm", "m5.public_band_v_cm"),
    ("m5.gap_ratio_vs_typical", "m5.gap_ratio_vs_typical"),
    ("m5.gap_ratio_vs_band_low", "m5.gap_ratio_vs_band_low"),
    ("m5.design_point_self_consistent", "m5.design_point_self_consistent"),
    ("m5.public_low_feasible", "m5.public_low_feasible"),
    ("m5.public_typical_feasible", "m5.public_typical_feasible"),
    ("m5.public_high_feasible", "m5.public_high_feasible"),
    ("m5.required_l_at_public_typical_mm", "m5.required_l_at_public_typical_mm"),
    ("m5.l_max_at_bw_deadline_mm", "m5.l_max_at_bw_deadline_mm"),
    ("m5.vpp_needed_at_m3_l_v", "m5.vpp_needed_at_m3_l_v"),
    ("m5.vpp_required_reachable", "m5.vpp_required_reachable"),
    ("m5.feasible_bands", "m5.feasible_bands"),
    ("m5.bw_law", "m5.bw_law"),
    ("m5.dual_cap", "m5.dual_cap"),
    ("m5.cross_form_flip", "m5.cross_form_flip"),
    ("m5.honest_note_m5", "m5.honest_note_m5"),
]
M5_BANDS = ("public_low", "public_typical", "public_high", "m3_implied")
M5_BAND_KEYS = ("vpi_l_v_cm", "l_min_mm", "l_max_mm", "width_mm", "n_grid_hits", "non_empty")
M5_BAND_PATHS = [("m5fn." + b + "." + k, "m5.feasible_bands." + b + "." + k)
                 for b in M5_BANDS for k in M5_BAND_KEYS]
M5_LAW_PATHS = [("m5bw." + k, "m5.bw_law." + k) for k in (
    "is_inverse_l", "max_rel_err_inv_l", "is_inverse_l2", "max_rel_err_inv_l2")]
M5_DUAL_PATHS = [("m5dc." + k, "m5.dual_cap." + k) for k in (
    "cap_electrode_fF", "cap_package_line_fF", "driver_electrode_mw",
    "driver_package_line_mw", "ratio_package_over_electrode")]
_M5_FLIP_LEAVES = ("cpo_per_lane_mw", "pluggable_per_lane_mw",
                   "delta_cpo_minus_pluggable_mw")
M5_FLIP_PATHS = (
    [("m5fp." + k, "m5.cross_form_flip.package_line_cap." + k) for k in _M5_FLIP_LEAVES]
    + [("m5fe." + k, "m5.cross_form_flip.electrode_cap." + k) for k in _M5_FLIP_LEAVES]
    + [("m5fl.advantage_flips", "m5.cross_form_flip.advantage_flips"),
       ("m5fl.note", "m5.cross_form_flip.note")])

ALL_PATHS = (ROOT_PATHS + REQUESTED_PATHS + CHANNEL_PATHS + MILESTONE_PATHS
             + GAP_PATHS + M1_TOP_PATHS + M1_DRIVER_PATHS + M1_RING_PATHS
             + M1_SPEC_PATHS + M1_FIX_PATHS
             + M2_TOP_PATHS + M2_FEC_PATHS + M2_FEC_MODE_PATHS + M2_DRIVER_PATHS
             + M2_RING_PATHS + M2_SPEC_PATHS + M2_GDS_PATHS + M2_FIX_PATHS
             + M2B_TOP_PATHS + M2B_EQ_PATHS + M2B_EQMODE_PATHS + M2B_CTLE_PATHS
             + M2B_LANE_PATHS + M2B_LANE_ELEM_PATHS + M2B_THERMAL_PATHS
             + M2B_GAMMA_PATHS + M2B_YIELD_PATHS + M2B_PKG_PATHS
             + M3_TOP_PATHS + M3_TWMZM_PATHS + M3_ECH_PATHS + M3_FDTD_PATHS
             + M3_NEXT_PATHS + M3_PDN_PATHS + M3_TH_PATHS + M3_CL_PATHS
             + M3_PW_TOP_PATHS + M3_PW_CPO_PATHS + M3_PW_PLUG_PATHS
             + M3_LAY_PATHS + M3_LAY_STAT_PATHS + M3_REUSE_TOP_PATHS
             + M3_REUSE_200_PATHS + M3_REUSE_400_PATHS
             + M4_TOP_PATHS + M4_CHAIN_PATHS + M4_PREBIAS_PATHS + M4_REPLAN_PATHS
             + M4_FORMS_TOP_PATHS + M4_FORMS_ELEM_PATHS + M4_CTE_PATHS
             + M4_PARETO_TOP_PATHS + M4_PARETO_PT_PATHS + M4_VPIL_PATHS
             + M4_WALL_PATHS + M4_BAND_PATHS + M4_SLOPE_PATHS
             + M5_TOP_PATHS + M5_BAND_PATHS + M5_LAW_PATHS + M5_DUAL_PATHS
             + M5_FLIP_PATHS)

# 🔴 防假绿：纯子串匹配下 `rp.m` 会被 `rp.min_fsr_nm` / `rp.max_il_drop_db` 前缀命中
# ⇒ 「把 `rp.m` 从渲染里删掉」时 ③ 仍绿（门禁看不见的盲区）。对**是其它字面量前缀**
# 的短路径，改用「后随分隔符」的边界正则。`_js_ref_ok` 统一处理。
_DELIM_AFTER = re.compile(r"[^A-Za-z0-9_$]")  # 非标识符字符才算「路径引用收尾」


def _js_ref_ok(rsrc: str, js_lit: str, all_lits) -> bool:
    """JS 字面引用判定：短路径若被其它字面量「前缀包含」，必须边界收尾才算引用。"""
    idx = 0
    while True:
        k = rsrc.find(js_lit, idx)
        if k < 0:
            return False
        nxt = rsrc[k + len(js_lit):k + len(js_lit) + 1]
        ambiguous = any(o != js_lit and o.startswith(js_lit) for o in all_lits)
        if (not ambiguous) or (nxt == "" or _DELIM_AFTER.fullmatch(nxt)):
            return True
        idx = k + 1


def json_path_exists(card: dict, path: str) -> bool:
    """逐段解析 JSON 路径；`arr[].k` 取首元素。任一段缺失 ⇒ False。"""
    cur = card
    for part in path.split("."):
        if part.endswith("[]"):
            key = part[:-2]
            if not isinstance(cur, dict) or key not in cur:
                return False
            arr = cur[key]
            if not isinstance(arr, list) or not arr:
                return False
            cur = arr[0]
        else:
            if not isinstance(cur, dict) or part not in cur:
                return False
            cur = cur[part]
    return True


def renderOi_src(html: str) -> str:
    m = re.search(r"function\s+renderOi\s*\([^\n]*\)\s*\{(.*?)\n\}", html, re.S)
    return m.group(1) if m else ""


def runOi_src(html: str) -> str:
    m = re.search(r"function\s+runOi\s*\([^\n]*\)\s*\{(.*?)\n\}", html, re.S)
    return m.group(1) if m else ""


def _top_keys(paths) -> set:
    """由 `m1.x.y` 路径族派生出 m1 顶层的被引用键名。"""
    return {p[1].split(".", 1)[1].split(".", 1)[0] for p in paths
            if p[1].startswith("m1.")}


def _leaf_keys(paths, prefix: str) -> set:
    return {p[1].rsplit(".", 1)[1] for p in paths if p[1].startswith(prefix)}


def _tops_of(paths, root: str) -> set:
    """由 `root.a.b` 路径族派生 root 顶层的被引用键名（`_top_keys` 的通用版）。"""
    return {p[1][len(root) + 1:].split(".", 1)[0] for p in paths
            if p[1].startswith(root + ".")}


def _m1_reverse_flags(card: dict) -> dict:
    """M1 反向完备五格：顶层 / ring_plan / driver / spec_points[] / m0_fixes[]。

    返回 {格名: bool}；True = 「后端每个展示字段都被前端引用」。
    🔴 `m1.honest_note_m1` 也在 M1_TOP_PATHS 内（结论段引用它），故参与顶层判据。
    """
    m1 = card.get("m1") or {}
    ok_top = set(m1.keys()) <= _top_keys(M1_TOP_PATHS)
    ok_rp = set((m1.get("ring_plan") or {}).keys()) <= _leaf_keys(M1_RING_PATHS, "m1.ring_plan.")
    ok_dv = set((m1.get("driver") or {}).keys()) <= _leaf_keys(M1_DRIVER_PATHS, "m1.driver.")
    sp0 = (m1.get("spec_points") or [{}])[0]
    ok_sp = set(sp0.keys()) <= _leaf_keys(M1_SPEC_PATHS, "m1.spec_points[].")
    fx0 = (m1.get("m0_fixes") or [{}])[0]
    ok_fx = set(fx0.keys()) <= _leaf_keys(M1_FIX_PATHS, "m1.m0_fixes[].")
    return {"top": ok_top, "ring_plan": ok_rp, "driver": ok_dv,
            "spec_points": ok_sp, "m0_fixes": ok_fx}


def _m2_reverse_flags(card: dict) -> dict:
    """M2 反向完备十格：顶层 / fec / fec.concatenated / fec.rs_only / fec.form_map /
    ring_plan / driver / spec_points[] / g_oi2 / platform_fixes_m2[]。

    返回 {格名: bool}；True = 「后端每个展示字段都被前端引用」。
    🔴 `m2.honest_note_m2` 也在 M2_TOP_PATHS 内（结论段引用它），故参与顶层判据。
    """
    m2 = card.get("m2") or {}
    fec = m2.get("fec") or {}
    return {
        "top": set(m2.keys()) <= _tops_of(M2_TOP_PATHS, "m2"),
        "fec": set(fec.keys()) <= _tops_of(M2_FEC_PATHS, "m2.fec"),
        "fec_concat": set((fec.get("concatenated") or {}).keys())
                      <= _leaf_keys(M2_FEC_MODE_PATHS, "m2.fec.concatenated."),
        "fec_rs": set((fec.get("rs_only") or {}).keys())
                  <= _leaf_keys(M2_FEC_MODE_PATHS, "m2.fec.rs_only."),
        "form_map": set((fec.get("form_map") or {}).keys())
                    <= _leaf_keys(M2_FEC_MODE_PATHS, "m2.fec.form_map."),
        "ring_plan": set((m2.get("ring_plan") or {}).keys())
                     <= _leaf_keys(M2_RING_PATHS, "m2.ring_plan."),
        "driver": set((m2.get("driver") or {}).keys())
                  <= _leaf_keys(M2_DRIVER_PATHS, "m2.driver."),
        "spec_points": set(((m2.get("spec_points") or [{}])[0]).keys())
                       <= _leaf_keys(M2_SPEC_PATHS, "m2.spec_points[]."),
        "g_oi2": set((m2.get("g_oi2") or {}).keys())
                 <= _leaf_keys(M2_GDS_PATHS, "m2.g_oi2."),
        "platform_fixes": set(((m2.get("platform_fixes_m2") or [{}])[0]).keys())
                          <= _leaf_keys(M2_FIX_PATHS, "m2.platform_fixes_m2[]."),
    }


def _m2b_reverse_flags(card: dict) -> dict:
    """M2b（G-OI5）反向完备十一格：顶层 / equalizer / equalizer.lpo / equalizer.retimed /
    ctle / lane_equalizer / lane_equalizer.lanes[] / thermal_tune / crosstalk_gamma /
    yield / packaging。

    返回 {格名: bool}；True = 「后端每个展示字段都被前端引用」。
    🔴 `honest_note_m2b` 与 `thermal_tune.honest_note_m2b_thermal` 也在路径表内
    （前端结论段与热调段分别渲染）⇒ 参与反向完备。
    """
    m2b = card.get("m2b") or {}
    eq = m2b.get("equalizer") or {}
    le = m2b.get("lane_equalizer") or {}
    return {
        "top": set(m2b.keys()) <= _tops_of(M2B_TOP_PATHS, "m2b"),
        # `lpo` / `retimed` 两个形态的**叶子**由 M2B_EQMODE_PATHS 覆盖，
        # 这里只需证明「顶层每个键都被 ③ 的路径表登记」（lpo / retimed / why）。
        "equalizer": set(eq.keys()) <= _tops_of(M2B_EQ_PATHS + M2B_EQMODE_PATHS,
                                               "m2b.equalizer"),
        "eq_lpo": set((eq.get("lpo") or {}).keys())
                  <= _leaf_keys(M2B_EQMODE_PATHS, "m2b.equalizer.lpo."),
        "eq_retimed": set((eq.get("retimed") or {}).keys())
                      <= _leaf_keys(M2B_EQMODE_PATHS, "m2b.equalizer.retimed."),
        "ctle": set((m2b.get("ctle") or {}).keys())
                <= _leaf_keys(M2B_CTLE_PATHS, "m2b.ctle."),
        "lane_eq": set(le.keys()) <= _leaf_keys(M2B_LANE_PATHS, "m2b.lane_equalizer."),
        "lane_elem": set(((le.get("lanes") or [{}])[0]).keys())
                     <= _leaf_keys(M2B_LANE_ELEM_PATHS, "m2b.lane_equalizer.lanes[]."),
        "thermal": set((m2b.get("thermal_tune") or {}).keys())
                   <= _leaf_keys(M2B_THERMAL_PATHS, "m2b.thermal_tune."),
        "gamma": set((m2b.get("crosstalk_gamma") or {}).keys())
                 <= _leaf_keys(M2B_GAMMA_PATHS, "m2b.crosstalk_gamma."),
        "yield": set((m2b.get("yield") or {}).keys())
                 <= _leaf_keys(M2B_YIELD_PATHS, "m2b.yield."),
        "pkg": set((m2b.get("packaging") or {}).keys())
               <= _leaf_keys(M2B_PKG_PATHS, "m2b.packaging."),
    }


def _m3_reverse_flags(card: dict) -> dict:
    """M3（3.2T / CPO）反向完备十四格：顶层 / twmzm / echannel / fdtd_telegraph /
    next / pdn / thermal / closed_loop_thermal / power / power.cpo / power.pluggable /
    layout_2p5d / reuse / reuse.at_200g+at_400g。

    返回 {格名: bool}；True = 「后端每个展示字段都被前端引用」。
    🔴 `m3.honest_note_m3` 与各子块 `note` 也在路径表内（前端分段/结论渲染）
    ⇒ 参与反向完备。
    """
    m3 = card.get("m3") or {}
    pw = m3.get("power") or {}
    ru = m3.get("reuse") or {}
    return {
        "top": set(m3.keys()) <= _tops_of(M3_TOP_PATHS + M3_TWMZM_PATHS
                                         + M3_ECH_PATHS + M3_FDTD_PATHS
                                         + M3_NEXT_PATHS + M3_PDN_PATHS
                                         + M3_TH_PATHS + M3_CL_PATHS
                                         + M3_PW_TOP_PATHS + M3_LAY_PATHS
                                         + M3_REUSE_TOP_PATHS, "m3"),
        "twmzm": set((m3.get("twmzm") or {}).keys())
                  <= _leaf_keys(M3_TWMZM_PATHS, "m3.twmzm."),
        "echannel": set((m3.get("echannel") or {}).keys())
                    <= _leaf_keys(M3_ECH_PATHS, "m3.echannel."),
        "fdtd": set((m3.get("fdtd_telegraph") or {}).keys())
                 <= _leaf_keys(M3_FDTD_PATHS, "m3.fdtd_telegraph."),
        "next": set((m3.get("next") or {}).keys())
                 <= _leaf_keys(M3_NEXT_PATHS, "m3.next."),
        "pdn": set((m3.get("pdn") or {}).keys())
               <= _leaf_keys(M3_PDN_PATHS, "m3.pdn."),
        "thermal": set((m3.get("thermal") or {}).keys())
                   <= _leaf_keys(M3_TH_PATHS, "m3.thermal."),
        "closed_loop": set((m3.get("closed_loop_thermal") or {}).keys())
                       <= _leaf_keys(M3_CL_PATHS, "m3.closed_loop_thermal."),
        "power": set(pw.keys()) <= _tops_of(M3_PW_TOP_PATHS
                                            + M3_PW_CPO_PATHS + M3_PW_PLUG_PATHS,
                                            "m3.power"),
        "power_cpo": set((pw.get("cpo") or {}).keys())
                    <= _leaf_keys(M3_PW_CPO_PATHS, "m3.power.cpo."),
        "power_plug": set((pw.get("pluggable") or {}).keys())
                     <= _leaf_keys(M3_PW_PLUG_PATHS, "m3.power.pluggable."),
        "layout": (set((m3.get("layout_2p5d") or {}).keys()) - M3_LAYOPT)
                  <= _leaf_keys(M3_LAY_PATHS, "m3.layout_2p5d."),
        "layout_stats": set(((m3.get("layout_2p5d") or {}).get("oe_stats") or {}).keys())
                        <= _leaf_keys(M3_LAY_STAT_PATHS, "m3.layout_2p5d.oe_stats."),
        "reuse": set(ru.keys()) <= _tops_of(M3_REUSE_TOP_PATHS
                                           + M3_REUSE_200_PATHS + M3_REUSE_400_PATHS,
                                           "m3.reuse"),
        "reuse_200": set((ru.get("at_200g") or {}).keys())
                     <= _leaf_keys(M3_REUSE_200_PATHS, "m3.reuse.at_200g."),
        "reuse_400": set((ru.get("at_400g") or {}).keys())
                     <= _leaf_keys(M3_REUSE_400_PATHS, "m3.reuse.at_400g."),
    }


def _m5_reverse_flags(card: dict) -> dict:
    """M5（VπL 断口结算）反向完备五格：顶层 / feasible_bands / bw_law / dual_cap /
    cross_form_flip（含两个口径子块）。

    返回 {格名: bool}；True = 「后端每个展示字段都被前端引用」。
    🔴 M5 的 `honest_note_m5` 也在 `M5_TOP_PATHS` 内（前端末段渲染）⇒ 参与顶层反向完备；
       `feasible_bands` 的 `non_empty` **必须**参与（否则「空集档」可被静默渲染成有解
       —— 与 M4 `oe_stats` 血案同族）。
    """
    m5 = card.get("m5") or {}
    fb = m5.get("feasible_bands") or {}
    fl = m5.get("cross_form_flip") or {}
    return {
        "top": set(m5.keys()) <= _tops_of(M5_TOP_PATHS + M5_BAND_PATHS + M5_LAW_PATHS
                                          + M5_DUAL_PATHS + M5_FLIP_PATHS, "m5"),
        "bands": all(set((fb.get(b) or {}).keys()) <= set(M5_BAND_KEYS) for b in M5_BANDS),
        "law": set((m5.get("bw_law") or {}).keys()) <= _leaf_keys(M5_LAW_PATHS, "m5.bw_law."),
        "dual": set((m5.get("dual_cap") or {}).keys())
                <= _leaf_keys(M5_DUAL_PATHS, "m5.dual_cap."),
        "flip": (set(fl.keys()) <= {"package_line_cap", "electrode_cap",
                                    "advantage_flips", "note"}
                 and all(set((fl.get(s) or {}).keys()) <= set(_M5_FLIP_LEAVES)
                         for s in ("package_line_cap", "electrode_cap"))),
    }


def _m4_reverse_flags(card: dict) -> dict:
    """M4（CPO 形态深化 · 热-光-电协同）反向完备十一格：顶层 / chain / prebias / replan /
    forms / forms.forms[CPO|OBO|pluggable] / cte / pareto / pareto.vpi_l /
    feasibility_wall / band_lock / slope_lock。

    返回 {格名: bool}；True = 「后端每个展示字段都被前端引用」。
    🔴 `m4.honest_note_m4` 与各子块 `note` 也在路径表内（前端分段/结论渲染）⇒ 参与反向完备。
    🔴 `pareto` 的 `front` / `feasible` / `m3_design_point` 为**显式白名单豁免**（重复副本）。
    """
    m4 = card.get("m4") or {}
    pa = m4.get("pareto") or {}
    fo = m4.get("forms") or {}
    elem_ok = all(
        set((fo.get("forms") or {}).get(fk, {}).keys()) <= set(M4_FORMS_ELEM_KEYS)
        for fk in ("CPO", "OBO", "pluggable"))
    return {
        "top": set(m4.keys()) <= _tops_of(M4_TOP_PATHS + M4_CHAIN_PATHS + M4_PREBIAS_PATHS
                                          + M4_REPLAN_PATHS + M4_FORMS_TOP_PATHS + M4_CTE_PATHS
                                          + M4_PARETO_TOP_PATHS + M4_WALL_PATHS + M4_BAND_PATHS
                                          + M4_SLOPE_PATHS, "m4"),
        "chain": set((m4.get("chain") or {}).keys())
                 <= _leaf_keys(M4_CHAIN_PATHS, "m4.chain."),
        "prebias": set((m4.get("prebias") or {}).keys())
                   <= _leaf_keys(M4_PREBIAS_PATHS, "m4.prebias."),
        "replan": set((m4.get("replan") or {}).keys())
                  <= _leaf_keys(M4_REPLAN_PATHS, "m4.replan."),
        "forms": set(fo.keys()) <= _tops_of(M4_FORMS_TOP_PATHS, "m4.forms"),
        "forms_elem": elem_ok,
        "cte": set((m4.get("cte") or {}).keys()) <= _leaf_keys(M4_CTE_PATHS, "m4.cte."),
        "pareto": (set(pa.keys()) - M4_PARETO_OPT)
                  <= _tops_of(M4_PARETO_TOP_PATHS, "m4.pareto"),
        "pareto_pt": set(((pa.get("points") or [{}])[0]).keys())
                     <= _leaf_keys(M4_PARETO_PT_PATHS, "m4.pareto.points[]."),
        "vpi_l": set((pa.get("vpi_l") or {}).keys())
                 <= _leaf_keys(M4_VPIL_PATHS, "m4.pareto.vpi_l."),
        "wall": set((m4.get("feasibility_wall") or {}).keys())
                <= _leaf_keys(M4_WALL_PATHS, "m4.feasibility_wall."),
        "band": set((m4.get("band_lock") or {}).keys())
                <= _leaf_keys(M4_BAND_PATHS, "m4.band_lock."),
        "slope": set((m4.get("slope_lock") or {}).keys())
                 <= _leaf_keys(M4_SLOPE_PATHS, "m4.slope_lock."),
    }


def main() -> int:
    print("=" * 74)
    print("WebUI 光联接模块 M0+M1+M2+M2b+M3+M4 案例卡 前端取值路径 + onclick 门禁"
          "（血案 #18/#19 机器化）")
    print("=" * 74)

    html = open(INDEX, encoding="utf-8").read()
    from lda_webui import oi_case as oi
    card = oi.case_card(use_cache=False)
    rsrc = renderOi_src(html)
    usrc = runOi_src(html)

    # ── 1. onclick 接线 ─────────────────────────────────────────────────
    check("① onclick 接线：$('runOi').onclick = runOi 在场（防「点不动」）",
          "$('runOi').onclick = runOi" in html)

    # ── 2. 函数定义 ─────────────────────────────────────────────────────
    check("② runOi 在 index.html 内定义", "function runOi(" in html)
    check("② renderOi 在 index.html 内定义", "function renderOi(" in html)
    # runOi 必须真的调 apiGet + renderOi（不是空壳）
    check("② runOi 调用 apiGet('/api/oi_demo') 并转交 renderOi",
          "/api/oi_demo" in usrc and "renderOi(" in usrc)
    # M1 段必须真的写进了 renderOi（防「后端加了 M1、前端还是 M0 壳」）
    check("② renderOi 内出现 M1 块引用（d.m1 + §⑥⑦⑧⑨ 表头）",
          "d.m1" in rsrc and "⑥ M1 信道规划" in rsrc and "⑦ M1 800G 设计点" in rsrc)
    # M2 段必须真的写进了 renderOi（防「后端加了 M2、前端还是 M0/M1 壳」）
    check("② renderOi 内出现 M2 块引用（d.m2 + ⑩⑪⑮ 表头）",
          "d.m2" in rsrc and "⑩ M2 规模 × 形态" in rsrc
          and "⑪ M2 带宽墙" in rsrc and "⑮ G-OI2 收发器真 GDS" in rsrc)
    # M3 段必须真的写进了 renderOi（防「后端加了 M3、前端还是 M0/M1/M2 壳」）
    check("② renderOi 内出现 M3 块引用（d.m3 + ㉔–㉘ 五个表头）",
          "d.m3" in rsrc and "㉔ M3 400G/lane 带宽墙" in rsrc
          and "㉕ CPO 电通道" in rsrc and "㉖ die↔die 热 + 闭环热调" in rsrc
          and "㉗ M3 功耗账" in rsrc and "㉘ M3 2.5D 版图签核" in rsrc)
    # M4 段必须真的写进了 renderOi（防「后端加了 M4、前端还是 M0–M3 壳」）
    check("② renderOi 内出现 M4 块引用（d.m4 + ㉙–㉞ 六个表头）",
          "d.m4" in rsrc and "㉙ M4 热-光-电耦合链" in rsrc
          and "㉚ M4 固化点预偏移" in rsrc and "㉛ M4 热致偏移" in rsrc
          and "㉜ M4 三形态三域矩阵" in rsrc and "㉝ M4 FAU CTE" in rsrc
          and "㉞ M4 三域 Pareto 前沿" in rsrc)

    # ── 3. 路径存在性（前端引用 ∧ 后端 JSON 真有值）─────────────────────
    _all_lits = [p[0] for p in ALL_PATHS]
    for js_lit, json_path in ALL_PATHS:
        js_ok = _js_ref_ok(rsrc, js_lit, _all_lits)
        json_ok = json_path_exists(card, json_path)
        check("③ 路径 %s ⇒ JSON %s（前端引用 ∧ 后端存在）"
              % (js_lit, json_path),
              js_ok and json_ok,
              "js_ref=%s json_ok=%s" % (js_ok, json_ok))

    # ── 4. 反向完备（后端每个「展示」字段都必须被前端引用）────────────
    # 🔴 `detail` 是紧凑行之外的辅助长文，前端 compact 行有意不渲染 ⇒ 允许不引用。
    OPTIONAL_UNREF = {"detail"}
    ch_keys = (set(card["channels"][0].keys()) if card.get("channels") else set()) - OPTIONAL_UNREF
    req_keys = (set(card["requested"].keys()) if isinstance(card.get("requested"), dict) else set()) - OPTIONAL_UNREF
    ms_keys = (set(card["milestones"][0].keys()) if card.get("milestones") else set()) - OPTIONAL_UNREF
    gp_keys = (set(card["gaps"][0].keys()) if card.get("gaps") else set()) - OPTIONAL_UNREF

    ref_ch = {p[1].split("[].", 1)[1] for p in CHANNEL_PATHS if p[1].startswith("channels[].")}
    ref_req = {p[1].split(".", 1)[1] for p in REQUESTED_PATHS if p[1].startswith("requested.")}
    ref_ms = {p[1].split("[].", 1)[1] for p in MILESTONE_PATHS if p[1].startswith("milestones[].")}
    ref_gp = {p[1].split("[].", 1)[1] for p in GAP_PATHS if p[1].startswith("gaps[].")}

    check("④a 反向完备：channels 每个展示字段都被前端引用（无静默盲区）",
          ch_keys <= ref_ch, "后端=%s 前端引用=%s" % (sorted(ch_keys), sorted(ref_ch)))
    check("④b 反向完备：requested 每个子字段都被前端引用",
          req_keys <= ref_req, "后端=%s 前端引用=%s" % (sorted(req_keys), sorted(ref_req)))
    check("④c 反向完备：milestones 每个展示字段都被前端引用（detail 为辅助长文，有意不渲染）",
          ms_keys <= ref_ms, "后端=%s 前端引用=%s" % (sorted(ms_keys), sorted(ref_ms)))
    check("④d 反向完备：gaps 每个展示字段都被前端引用（detail 同）",
          gp_keys <= ref_gp, "后端=%s 前端引用=%s" % (sorted(gp_keys), sorted(ref_gp)))

    rf = _m1_reverse_flags(card)
    check("④e-1 反向完备：m1 顶层每个展示字段都被前端引用",
          rf["top"], "后端=%s 前端引用=%s"
          % (sorted((card.get("m1") or {}).keys()), sorted(_top_keys(M1_TOP_PATHS))))
    check("④e-2 反向完备：m1.ring_plan 每个字段都被前端引用",
          rf["ring_plan"], "后端=%s 前端引用=%s"
          % (sorted((card["m1"].get("ring_plan") or {}).keys()),
             sorted(_leaf_keys(M1_RING_PATHS, "m1.ring_plan."))))
    check("④e-3 反向完备：m1.driver 每个字段都被前端引用",
          rf["driver"], "后端=%s 前端引用=%s"
          % (sorted((card["m1"].get("driver") or {}).keys()),
             sorted(_leaf_keys(M1_DRIVER_PATHS, "m1.driver."))))
    check("④e-4 反向完备：m1.spec_points[] 每个字段都被前端引用",
          rf["spec_points"], "后端=%s 前端引用=%s"
          % (sorted((card["m1"]["spec_points"][0]).keys()),
             sorted(_leaf_keys(M1_SPEC_PATHS, "m1.spec_points[]."))))
    check("④e-5 反向完备：m1.m0_fixes[] 每个字段都被前端引用",
          rf["m0_fixes"], "后端=%s 前端引用=%s"
          % (sorted((card["m1"]["m0_fixes"][0]).keys()),
             sorted(_leaf_keys(M1_FIX_PATHS, "m1.m0_fixes[]."))))

    # ── 4b. M2（1.6T）反向完备十格 ─────────────────────────────────────
    _m2 = card.get("m2") or {}
    _fec = _m2.get("fec") or {}
    rf2 = _m2_reverse_flags(card)
    check("④e-6 反向完备：m2 顶层每个展示字段都被前端引用",
          rf2["top"], "后端=%s 前端引用=%s"
          % (sorted(_m2.keys()), sorted(_tops_of(M2_TOP_PATHS, "m2"))))
    check("④e-7 反向完备：m2.fec 每个字段都被前端引用",
          rf2["fec"], "后端=%s 前端引用=%s"
          % (sorted(_fec.keys()), sorted(_tops_of(M2_FEC_PATHS, "m2.fec"))))
    check("④e-8 反向完备：m2.fec.concatenated 每个字段都被前端引用",
          rf2["fec_concat"], "后端=%s 前端引用=%s"
          % (sorted((_fec.get("concatenated") or {}).keys()),
             sorted(_leaf_keys(M2_FEC_MODE_PATHS, "m2.fec.concatenated."))))
    check("④e-9 反向完备：m2.fec.rs_only 每个字段都被前端引用",
          rf2["fec_rs"], "后端=%s 前端引用=%s"
          % (sorted((_fec.get("rs_only") or {}).keys()),
             sorted(_leaf_keys(M2_FEC_MODE_PATHS, "m2.fec.rs_only."))))
    check("④e-10 反向完备：m2.fec.form_map 每个字段都被前端引用",
          rf2["form_map"], "后端=%s 前端引用=%s"
          % (sorted((_fec.get("form_map") or {}).keys()),
             sorted(_leaf_keys(M2_FEC_MODE_PATHS, "m2.fec.form_map."))))
    check("④e-11 反向完备：m2.ring_plan 每个字段都被前端引用",
          rf2["ring_plan"], "后端=%s 前端引用=%s"
          % (sorted((_m2.get("ring_plan") or {}).keys()),
             sorted(_leaf_keys(M2_RING_PATHS, "m2.ring_plan."))))
    check("④e-12 反向完备：m2.driver 每个字段都被前端引用",
          rf2["driver"], "后端=%s 前端引用=%s"
          % (sorted((_m2.get("driver") or {}).keys()),
             sorted(_leaf_keys(M2_DRIVER_PATHS, "m2.driver."))))
    check("④e-13 反向完备：m2.spec_points[] 每个字段都被前端引用",
          rf2["spec_points"], "后端=%s 前端引用=%s"
          % (sorted(((_m2.get("spec_points") or [{}])[0]).keys()),
             sorted(_leaf_keys(M2_SPEC_PATHS, "m2.spec_points[]."))))
    check("④e-14 反向完备：m2.g_oi2 每个字段都被前端引用",
          rf2["g_oi2"], "后端=%s 前端引用=%s"
          % (sorted((_m2.get("g_oi2") or {}).keys()),
             sorted(_leaf_keys(M2_GDS_PATHS, "m2.g_oi2."))))
    check("④e-15 反向完备：m2.platform_fixes_m2[] 每个字段都被前端引用",
          rf2["platform_fixes"], "后端=%s 前端引用=%s"
          % (sorted(((_m2.get("platform_fixes_m2") or [{}])[0]).keys()),
             sorted(_leaf_keys(M2_FIX_PATHS, "m2.platform_fixes_m2[]."))))

    # ── 4c. M2b（G-OI5）反向完备十一格 ────────────────────────────────
    _m2b = card.get("m2b") or {}
    _eq = _m2b.get("equalizer") or {}
    _le = _m2b.get("lane_equalizer") or {}
    rf3 = _m2b_reverse_flags(card)
    check("④e-16 反向完备：m2b 顶层每个展示字段都被前端引用",
          rf3["top"], "后端=%s 前端引用=%s"
          % (sorted(_m2b.keys()), sorted(_tops_of(M2B_TOP_PATHS, "m2b"))))
    check("④e-17 反向完备：m2b.equalizer 每个字段都被前端引用",
          rf3["equalizer"], "后端=%s 前端引用=%s"
          % (sorted(_eq.keys()), sorted(_tops_of(M2B_EQ_PATHS, "m2b.equalizer"))))
    check("④e-18 反向完备：m2b.equalizer.lpo 每个字段都被前端引用",
          rf3["eq_lpo"], "后端=%s 前端引用=%s"
          % (sorted((_eq.get("lpo") or {}).keys()),
             sorted(_leaf_keys(M2B_EQMODE_PATHS, "m2b.equalizer.lpo."))))
    check("④e-19 反向完备：m2b.equalizer.retimed 每个字段都被前端引用",
          rf3["eq_retimed"], "后端=%s 前端引用=%s"
          % (sorted((_eq.get("retimed") or {}).keys()),
             sorted(_leaf_keys(M2B_EQMODE_PATHS, "m2b.equalizer.retimed."))))
    check("④e-20 反向完备：m2b.ctle 每个字段都被前端引用",
          rf3["ctle"], "后端=%s 前端引用=%s"
          % (sorted((_m2b.get("ctle") or {}).keys()),
             sorted(_leaf_keys(M2B_CTLE_PATHS, "m2b.ctle."))))
    check("④e-21 反向完备：m2b.lane_equalizer 每个字段都被前端引用",
          rf3["lane_eq"], "后端=%s 前端引用=%s"
          % (sorted(_le.keys()), sorted(_leaf_keys(M2B_LANE_PATHS, "m2b.lane_equalizer."))))
    check("④e-22 反向完备：m2b.lane_equalizer.lanes[] 每个字段都被前端引用",
          rf3["lane_elem"], "后端=%s 前端引用=%s"
          % (sorted(((_le.get("lanes") or [{}])[0]).keys()),
             sorted(_leaf_keys(M2B_LANE_ELEM_PATHS, "m2b.lane_equalizer.lanes[]."))))
    check("④e-23 反向完备：m2b.thermal_tune 每个字段都被前端引用",
          rf3["thermal"], "后端=%s 前端引用=%s"
          % (sorted((_m2b.get("thermal_tune") or {}).keys()),
             sorted(_leaf_keys(M2B_THERMAL_PATHS, "m2b.thermal_tune."))))
    check("④e-24 反向完备：m2b.crosstalk_gamma 每个字段都被前端引用",
          rf3["gamma"], "后端=%s 前端引用=%s"
          % (sorted((_m2b.get("crosstalk_gamma") or {}).keys()),
             sorted(_leaf_keys(M2B_GAMMA_PATHS, "m2b.crosstalk_gamma."))))
    check("④e-25 反向完备：m2b.yield 每个字段都被前端引用",
          rf3["yield"], "后端=%s 前端引用=%s"
          % (sorted((_m2b.get("yield") or {}).keys()),
             sorted(_leaf_keys(M2B_YIELD_PATHS, "m2b.yield."))))
    check("④e-26 反向完备：m2b.packaging 每个字段都被前端引用",
          rf3["pkg"], "后端=%s 前端引用=%s"
          % (sorted((_m2b.get("packaging") or {}).keys()),
             sorted(_leaf_keys(M2B_PKG_PATHS, "m2b.packaging."))))

    # ── 4d. M3（3.2T / CPO）反向完备十五格 ────────────────────────────
    _m3 = card.get("m3") or {}
    _pw3 = _m3.get("power") or {}
    _ru3 = _m3.get("reuse") or {}
    rf4 = _m3_reverse_flags(card)
    check("④e-27 反向完备：m3 顶层每个展示字段都被前端引用",
          rf4["top"], "后端=%s 前端引用=%s"
          % (sorted(_m3.keys()),
             sorted(_tops_of(M3_TOP_PATHS + M3_TWMZM_PATHS + M3_ECH_PATHS
                             + M3_FDTD_PATHS + M3_NEXT_PATHS + M3_PDN_PATHS
                             + M3_TH_PATHS + M3_CL_PATHS + M3_PW_TOP_PATHS
                             + M3_LAY_PATHS + M3_REUSE_TOP_PATHS, "m3"))))
    check("④e-28 反向完备：m3.twmzm 每个字段都被前端引用",
          rf4["twmzm"], "后端=%s 前端引用=%s"
          % (sorted((_m3.get("twmzm") or {}).keys()),
             sorted(_leaf_keys(M3_TWMZM_PATHS, "m3.twmzm."))))
    check("④e-29 反向完备：m3.echannel 每个字段都被前端引用",
          rf4["echannel"], "后端=%s 前端引用=%s"
          % (sorted((_m3.get("echannel") or {}).keys()),
             sorted(_leaf_keys(M3_ECH_PATHS, "m3.echannel."))))
    check("④e-30 反向完备：m3.fdtd_telegraph 每个字段都被前端引用",
          rf4["fdtd"], "后端=%s 前端引用=%s"
          % (sorted((_m3.get("fdtd_telegraph") or {}).keys()),
             sorted(_leaf_keys(M3_FDTD_PATHS, "m3.fdtd_telegraph."))))
    check("④e-31 反向完备：m3.next 每个字段都被前端引用",
          rf4["next"], "后端=%s 前端引用=%s"
          % (sorted((_m3.get("next") or {}).keys()),
             sorted(_leaf_keys(M3_NEXT_PATHS, "m3.next."))))
    check("④e-32 反向完备：m3.pdn 每个字段都被前端引用",
          rf4["pdn"], "后端=%s 前端引用=%s"
          % (sorted((_m3.get("pdn") or {}).keys()),
             sorted(_leaf_keys(M3_PDN_PATHS, "m3.pdn."))))
    check("④e-33 反向完备：m3.thermal 每个字段都被前端引用",
          rf4["thermal"], "后端=%s 前端引用=%s"
          % (sorted((_m3.get("thermal") or {}).keys()),
             sorted(_leaf_keys(M3_TH_PATHS, "m3.thermal."))))
    check("④e-34 反向完备：m3.closed_loop_thermal 每个字段都被前端引用",
          rf4["closed_loop"], "后端=%s 前端引用=%s"
          % (sorted((_m3.get("closed_loop_thermal") or {}).keys()),
             sorted(_leaf_keys(M3_CL_PATHS, "m3.closed_loop_thermal."))))
    check("④e-35 反向完备：m3.power 每个字段都被前端引用",
          rf4["power"], "后端=%s 前端引用=%s"
          % (sorted(_pw3.keys()),
             sorted(_tops_of(M3_PW_TOP_PATHS + M3_PW_CPO_PATHS + M3_PW_PLUG_PATHS,
                             "m3.power"))))
    check("④e-36 反向完备：m3.power.cpo 每个分项都被前端引用",
          rf4["power_cpo"], "后端=%s 前端引用=%s"
          % (sorted((_pw3.get("cpo") or {}).keys()),
             sorted(_leaf_keys(M3_PW_CPO_PATHS, "m3.power.cpo."))))
    check("④e-37 反向完备：m3.power.pluggable 每个分项都被前端引用",
          rf4["power_plug"], "后端=%s 前端引用=%s"
          % (sorted((_pw3.get("pluggable") or {}).keys()),
             sorted(_leaf_keys(M3_PW_PLUG_PATHS, "m3.power.pluggable."))))
    check("④e-38 反向完备：m3.layout_2p5d 每个展示字段都被前端引用"
          "（geometry/lvs_report 为显式白名单豁免）",
          rf4["layout"], "后端=%s 前端引用=%s"
          % (sorted(set((_m3.get("layout_2p5d") or {}).keys()) - M3_LAYOPT),
             sorted(_leaf_keys(M3_LAY_PATHS, "m3.layout_2p5d."))))
    check("④e-39 反向完备：m3.reuse 每个字段都被前端引用",
          rf4["reuse"], "后端=%s 前端引用=%s"
          % (sorted(_ru3.keys()),
             sorted(_tops_of(M3_REUSE_TOP_PATHS + M3_REUSE_200_PATHS
                             + M3_REUSE_400_PATHS, "m3.reuse"))))
    check("④e-40 反向完备：m3.reuse.at_200g 每个字段都被前端引用",
          rf4["reuse_200"], "后端=%s 前端引用=%s"
          % (sorted((_ru3.get("at_200g") or {}).keys()),
             sorted(_leaf_keys(M3_REUSE_200_PATHS, "m3.reuse.at_200g."))))
    check("④e-41 反向完备：m3.reuse.at_400g 每个字段都被前端引用",
          rf4["reuse_400"], "后端=%s 前端引用=%s"
          % (sorted((_ru3.get("at_400g") or {}).keys()),
             sorted(_leaf_keys(M3_REUSE_400_PATHS, "m3.reuse.at_400g."))))
    # 🔴 oe_stats 已改为**全字段渲染**（首版把它塞进豁免集 ⇒ 无人守护的真盲区）。
    check("④e-42 反向完备：m3.layout_2p5d.oe_stats 每个字段都被前端引用（零豁免）",
          rf4["layout_stats"], "后端=%s 前端引用=%s"
          % (sorted(((_m3.get("layout_2p5d") or {}).get("oe_stats") or {}).keys()),
             sorted(_leaf_keys(M3_LAY_STAT_PATHS, "m3.layout_2p5d.oe_stats."))))

    # ── 4e. M4（CPO 形态深化 · 热-光-电协同）反向完备十三格 ──────────────
    _m4 = card.get("m4") or {}
    _pa4 = _m4.get("pareto") or {}
    _fo4 = _m4.get("forms") or {}
    rf5 = _m4_reverse_flags(card)
    check("④e-43 反向完备：m4 顶层每个展示字段都被前端引用",
          rf5["top"], "后端=%s 前端引用=%s"
          % (sorted(_m4.keys()),
             sorted(_tops_of(M4_TOP_PATHS + M4_CHAIN_PATHS + M4_PREBIAS_PATHS
                             + M4_REPLAN_PATHS + M4_FORMS_TOP_PATHS + M4_CTE_PATHS
                             + M4_PARETO_TOP_PATHS + M4_WALL_PATHS + M4_BAND_PATHS
                             + M4_SLOPE_PATHS, "m4"))))
    check("④e-44 反向完备：m4.chain 每个字段都被前端引用",
          rf5["chain"], "后端=%s 前端引用=%s"
          % (sorted((_m4.get("chain") or {}).keys()),
             sorted(_leaf_keys(M4_CHAIN_PATHS, "m4.chain."))))
    check("④e-45 反向完备：m4.prebias 每个字段都被前端引用",
          rf5["prebias"], "后端=%s 前端引用=%s"
          % (sorted((_m4.get("prebias") or {}).keys()),
             sorted(_leaf_keys(M4_PREBIAS_PATHS, "m4.prebias."))))
    check("④e-46 反向完备：m4.replan 每个字段都被前端引用",
          rf5["replan"], "后端=%s 前端引用=%s"
          % (sorted((_m4.get("replan") or {}).keys()),
             sorted(_leaf_keys(M4_REPLAN_PATHS, "m4.replan."))))
    check("④e-47 反向完备：m4.forms 每个字段都被前端引用",
          rf5["forms"], "后端=%s 前端引用=%s"
          % (sorted(_fo4.keys()), sorted(_tops_of(M4_FORMS_TOP_PATHS, "m4.forms"))))
    check("④e-48 反向完备：m4.forms.forms[CPO|OBO|pluggable] 每个字段都被前端引用",
          rf5["forms_elem"], "后端=%s 前端引用=%s"
          % (sorted(set().union(*[set(((_fo4.get("forms") or {}).get(fk) or {}).keys())
                                  for fk in ("CPO", "OBO", "pluggable")])),
             sorted(M4_FORMS_ELEM_KEYS)))
    check("④e-49 反向完备：m4.cte 每个字段都被前端引用",
          rf5["cte"], "后端=%s 前端引用=%s"
          % (sorted((_m4.get("cte") or {}).keys()),
             sorted(_leaf_keys(M4_CTE_PATHS, "m4.cte."))))
    check("④e-50 反向完备：m4.pareto 每个展示字段都被前端引用"
          "（front/feasible/m3_design_point 为显式白名单豁免）",
          rf5["pareto"], "后端=%s 前端引用=%s"
          % (sorted(set(_pa4.keys()) - M4_PARETO_OPT),
             sorted(_tops_of(M4_PARETO_TOP_PATHS, "m4.pareto"))))
    check("④e-51 反向完备：m4.pareto.points[] 每个字段都被前端引用",
          rf5["pareto_pt"], "后端=%s 前端引用=%s"
          % (sorted(((_pa4.get("points") or [{}])[0]).keys()),
             sorted(_leaf_keys(M4_PARETO_PT_PATHS, "m4.pareto.points[]."))))
    check("④e-52 反向完备：m4.pareto.vpi_l 每个字段都被前端引用",
          rf5["vpi_l"], "后端=%s 前端引用=%s"
          % (sorted((_pa4.get("vpi_l") or {}).keys()),
             sorted(_leaf_keys(M4_VPIL_PATHS, "m4.pareto.vpi_l."))))
    check("④e-53 反向完备：m4.feasibility_wall 每个字段都被前端引用",
          rf5["wall"], "后端=%s 前端引用=%s"
          % (sorted((_m4.get("feasibility_wall") or {}).keys()),
             sorted(_leaf_keys(M4_WALL_PATHS, "m4.feasibility_wall."))))
    check("④e-54 反向完备：m4.band_lock 每个字段都被前端引用",
          rf5["band"], "后端=%s 前端引用=%s"
          % (sorted((_m4.get("band_lock") or {}).keys()),
             sorted(_leaf_keys(M4_BAND_PATHS, "m4.band_lock."))))
    check("④e-55 反向完备：m4.slope_lock 每个字段都被前端引用",
          rf5["slope"], "后端=%s 前端引用=%s"
          % (sorted((_m4.get("slope_lock") or {}).keys()),
             sorted(_leaf_keys(M4_SLOPE_PATHS, "m4.slope_lock."))))

    # ── 4f. M5（VπL 断口结算）反向完备五格 ────────────────────────────
    _m5 = card.get("m5") or {}
    _fb5 = _m5.get("feasible_bands") or {}
    rf6 = _m5_reverse_flags(card)
    check("④e-56 反向完备：m5 顶层每个展示字段都被前端引用",
          rf6["top"], "后端=%s 前端引用=%s"
          % (sorted(_m5.keys()),
             sorted(_tops_of(M5_TOP_PATHS + M5_BAND_PATHS + M5_LAW_PATHS
                             + M5_DUAL_PATHS + M5_FLIP_PATHS, "m5"))))
    check("④e-57 反向完备：m5.feasible_bands[四档] 每个字段都被前端引用"
          "（含 non_empty，防空集档被渲染成有解）",
          rf6["bands"], "后端=%s 前端引用=%s"
          % (sorted(set().union(*[set((_fb5.get(b) or {}).keys()) for b in M5_BANDS])),
             sorted(M5_BAND_KEYS)))
    check("④e-58 反向完备：m5.bw_law 每个字段都被前端引用",
          rf6["law"], "后端=%s 前端引用=%s"
          % (sorted((_m5.get("bw_law") or {}).keys()),
             sorted(_leaf_keys(M5_LAW_PATHS, "m5.bw_law."))))
    check("④e-59 反向完备：m5.dual_cap 每个字段都被前端引用",
          rf6["dual"], "后端=%s 前端引用=%s"
          % (sorted((_m5.get("dual_cap") or {}).keys()),
             sorted(_leaf_keys(M5_DUAL_PATHS, "m5.dual_cap."))))
    check("④e-60 反向完备：m5.cross_form_flip 每个字段都被前端引用（两口径并列）",
          rf6["flip"], "后端=%s 前端引用=%s"
          % (sorted((_m5.get("cross_form_flip") or {}).keys()),
             sorted({"package_line_cap", "electrode_cap", "advantage_flips", "note"})))

    # ── 5. 突变探针（先证能变红）───────────────────────────────────────
    import copy
    # 探针①：抹掉 case_card 的某 channel 字段 ⇒ ③ 的路径判据必红
    card_mut = copy.deepcopy(card)
    del card_mut["channels"][0]["il_cascade_db"]
    probe1 = json_path_exists(card_mut, "channels[].il_cascade_db")
    check("🔴 探针①: 抹掉 channels[].il_cascade_db ⇒ ③ 路径判据必红",
          probe1 is False)

    # 探针①b：往 gaps[0] 塞一个新字段 ⇒ ④d 反向完备必红
    #          （F5：缺口**闭合证据链**字段必须一一被前端引用，不许静默增字段）
    card_mut1b = copy.deepcopy(card)
    card_mut1b["gaps"][0]["brand_new_probe_gap_field"] = 1
    _gpk = ((set(card_mut1b["gaps"][0].keys()) if card_mut1b.get("gaps") else set())
            - OPTIONAL_UNREF)
    _rgp = {p[1].split("[].", 1)[1] for p in GAP_PATHS if p[1].startswith("gaps[].")}
    check("🔴 探针①b: gaps[] 多一个新字段 ⇒ ④d 反向完备必红（缺口证据字段无静默盲区）",
          (_gpk <= _rgp) is False)

    # 探针②：删掉 onclick 接线行 ⇒ ① 接线判据必红
    html_mut = html.replace("$('runOi').onclick = runOi", "$('runOi').onclick = null")
    probe2 = "$('runOi').onclick = runOi" in html_mut
    check("🔴 探针②: 删掉 onclick 接线 ⇒ ① 接线判据必红", probe2 is False)

    # 探针③：抹掉 m1.ring_plan.m ⇒ ③ 的 M1 路径判据必红
    card_mut3 = copy.deepcopy(card)
    del card_mut3["m1"]["ring_plan"]["m"]
    probe3 = json_path_exists(card_mut3, "m1.ring_plan.m")
    check("🔴 探针③: 抹掉 m1.ring_plan.m ⇒ ③ 路径判据必红", probe3 is False)

    # 探针④：往 m1.ring_plan 塞一个新字段 ⇒ ④e-2 ring 反向完备必红
    #         （防「后端加了字段、前端不显示」的静默盲区——这是本门禁的存在理由）
    card_mut4 = copy.deepcopy(card)
    card_mut4["m1"]["ring_plan"]["brand_new_probe_field"] = 1
    probe4 = _m1_reverse_flags(card_mut4)["ring_plan"]
    check("🔴 探针④: m1.ring_plan 多一个新字段 ⇒ ④e-2 反向完备必红", probe4 is False)

    # 探针⑤：往 m1 顶层塞一个新字段 ⇒ ④e-1 顶层反向完备必红
    card_mut5 = copy.deepcopy(card)
    card_mut5["m1"]["brand_new_probe_top"] = 1
    probe5 = _m1_reverse_flags(card_mut5)["top"]
    check("🔴 探针⑤: m1 顶层多一个新字段 ⇒ ④e-1 反向完备必红", probe5 is False)

    # 探针 R：还原探针（未被污染的原卡必须全绿）——防「探针把卡改脏后判据仍绿」假象
    check("🔴 探针R: 未被污染的 case_card 在 M1+M2 反向完备上仍全绿（探针无副作用）",
          all(_m1_reverse_flags(card).values())
          and all(_m2_reverse_flags(card).values()))

    # 探针⑦：往 m2 顶层塞一个新字段 ⇒ ④e-6 顶层反向完备必红
    card_mut7 = copy.deepcopy(card)
    card_mut7["m2"]["brand_new_probe_top2"] = 1
    probe7 = _m2_reverse_flags(card_mut7)["top"]
    check("🔴 探针⑦: m2 顶层多一个新字段 ⇒ ④e-6 反向完备必红", probe7 is False)

    # 探针⑧：抹掉 m2.spec_points[0] 的 verdict_point ⇒ ③ 的 M2 路径判据必红
    card_mut8 = copy.deepcopy(card)
    del card_mut8["m2"]["spec_points"][0]["verdict_point"]
    probe8 = json_path_exists(card_mut8, "m2.spec_points[].verdict_point")
    check("🔴 探针⑧: 抹掉 m2.spec_points[].verdict_point ⇒ ③ 路径判据必红",
          probe8 is False)

    # 探针⑨：往 m2.fec 塞一个新字段 ⇒ ④e-7 fec 反向完备必红
    card_mut9 = copy.deepcopy(card)
    card_mut9["m2"]["fec"]["brand_new_probe_fec"] = 1
    probe9 = _m2_reverse_flags(card_mut9)["fec"]
    check("🔴 探针⑨: m2.fec 多一个新字段 ⇒ ④e-7 反向完备必红", probe9 is False)

    # 探针⑥：证明「边界正则」不是摆设——一段**只**提到 rp.min_/rp.max_ 的源码
    #        在纯子串口径下会假绿，在边界口径下必须为 False（先证能变红）。
    _fake = "var a=rp.min_fsr_nm+rp.max_il_drop_db;"
    _plain = "rp.m" in _fake
    _strict = _js_ref_ok(_fake, "rp.m", _all_lits)
    check("🔴 探针⑥: 只剩 rp.min_/rp.max_ 的源码 ⇒ 纯子串假绿=%s 而边界判据必红=%s"
          % (_plain, not _strict), _plain is True and _strict is False)

    # ── 5b. M2b（G-OI5）突变探针（先证能变红，再信 ③/④e-16…④e-26）────
    card_m10 = copy.deepcopy(card)
    card_m10["m2b"]["brand_new_probe_top3"] = 1
    probe10 = _m2b_reverse_flags(card_m10)["top"]
    check("🔴 探针⑩: m2b 顶层多一个新字段 ⇒ ④e-16 反向完备必红", probe10 is False)

    card_m11 = copy.deepcopy(card)
    del card_m11["m2b"]["thermal_tune"]["p_per_lane_mW"]
    probe11 = json_path_exists(card_m11, "m2b.thermal_tune.p_per_lane_mW")
    check("🔴 探针⑪: 抹掉 m2b.thermal_tune.p_per_lane_mW ⇒ ③ 路径判据必红",
          probe11 is False)

    card_m12 = copy.deepcopy(card)
    del card_m12["m2b"]["lane_equalizer"]["lanes"][0]["pen_db"]
    probe12 = json_path_exists(card_m12, "m2b.lane_equalizer.lanes[].pen_db")
    check("🔴 探针⑫: 抹掉 m2b.lane_equalizer.lanes[].pen_db ⇒ ③ 路径判据必红",
          probe12 is False)

    card_m13 = copy.deepcopy(card)
    card_m13["m2b"]["packaging"]["brand_new_probe_pkg"] = 1
    probe13 = _m2b_reverse_flags(card_m13)["pkg"]
    check("🔴 探针⑬: m2b.packaging 多一个新字段 ⇒ ④e-26 反向完备必红", probe13 is False)

    card_m14 = copy.deepcopy(card)
    del card_m14["m2b"]["thermal_tune"]["honest_note_m2b_thermal"]
    probe14 = json_path_exists(card_m14, "m2b.thermal_tune.honest_note_m2b_thermal")
    check("🔴 探针⑭: 抹掉 m2b.thermal_tune.honest_note_m2b_thermal ⇒ ③ 路径判据必红",
          probe14 is False)

    # 探针⑮：证明 ③ 真的盯「前端字面量」本身——把 ④e-20 依赖的 `m2bct.noise_penalty_flat_db`
    # 从 renderOi 源码里抹掉 ⇒ 该路径的 js_ref 必红（只有后端 JSON 有值而不盯前端 = 假绿）。
    rsrc_m15 = rsrc.replace("m2bct.noise_penalty_flat_db", "")
    probe15 = _js_ref_ok(rsrc_m15, "m2bct.noise_penalty_flat_db", _all_lits)
    check("🔴 探针⑮: 前端抹掉 m2bct.noise_penalty_flat_db 字面量 ⇒ ③ 的 js_ref 必红",
          probe15 is False)

    check("🔴 探针R: 未被污染的 case_card 在 M1+M2+M2b 反向完备上仍全绿（探针无副作用）",
          all(_m1_reverse_flags(card).values())
          and all(_m2_reverse_flags(card).values())
          and all(_m2b_reverse_flags(card).values()))

    # ── 5c. M3（3.2T / CPO）突变探针（先证能变红，再信 ③/④e-27…④e-41）──
    card_m16 = copy.deepcopy(card)
    card_m16["m3"]["brand_new_probe_top4"] = 1
    probe16 = _m3_reverse_flags(card_m16)["top"]
    check("🔴 探针⑯: m3 顶层多一个新字段 ⇒ ④e-27 反向完备必红", probe16 is False)

    card_m17 = copy.deepcopy(card)
    del card_m17["m3"]["twmzm"]["margin_db"]
    probe17 = json_path_exists(card_m17, "m3.twmzm.margin_db")
    check("🔴 探针⑰: 抹掉 m3.twmzm.margin_db ⇒ ③ 路径判据必红", probe17 is False)

    card_m18 = copy.deepcopy(card)
    card_m18["m3"]["power"]["cpo"]["brand_new_probe_pw"] = 1
    probe18 = _m3_reverse_flags(card_m18)["power_cpo"]
    check("🔴 探针⑱: m3.power.cpo 多一个新分项 ⇒ ④e-36 反向完备必红",
          probe18 is False)

    # 探针⑲：抹掉 `m3cl.residual_nm` 的**前端字面量** ⇒ ③ 的 js_ref 必红
    #（只有后端 JSON 有值而不盯前端 = 假绿；这条证明 ③ 真的两端都盯）。
    rsrc_m19 = rsrc.replace("m3cl.residual_nm", "")
    probe19 = _js_ref_ok(rsrc_m19, "m3cl.residual_nm", _all_lits)
    check("🔴 探针⑲: 前端抹掉 m3cl.residual_nm 字面量 ⇒ ③ 的 js_ref 必红",
          probe19 is False)

    # 探针⑳：M3 路径表里 `m3ly.gds_sha256` 被 `m3ly.gds_sha256_short` **前缀包含**
    # ⇒ 纯子串口径下「只留 short」会让短路径假绿；边界正则必须为 False。
    _fake3 = "h+=m3ly.gds_sha256_short;"
    _plain3 = "m3ly.gds_sha256" in _fake3
    _strict3 = _js_ref_ok(_fake3, "m3ly.gds_sha256", _all_lits)
    check("🔴 探针⑳: 只留 m3ly.gds_sha256_short 的源码 ⇒ 纯子串假绿=%s 而边界判据必红=%s"
          % (_plain3, not _strict3), _plain3 is True and _strict3 is False)

    check("🔴 探针R2: 未被污染的 case_card 在 M3 反向完备十五格上仍全绿（探针无副作用）",
          all(_m3_reverse_flags(card).values()))

    # 探针㉑：往 oe_stats 里塞一个新成员 ⇒ ④e-42 必红（证明「零豁免」不是死条款）
    card_m21 = copy.deepcopy(card)
    card_m21["m3"]["layout_2p5d"]["oe_stats"]["brand_new_stat"] = 1
    probe21 = _m3_reverse_flags(card_m21)["layout_stats"]
    check("🔴 探针㉑: m3.layout_2p5d.oe_stats 多一个新成员 ⇒ ④e-42 必红",
          probe21 is False)

    # 探针㉒：ladder 收敛五字段是**新加**的 ⇒ 必须证明「后端塞进 ladder_* 新字段会被反向完备抓住」。
    #   （旧口径下 M3 是 462 判据，加字段后若 ④e 不覆盖，就会静默进盲区）
    card_m22 = copy.deepcopy(card)
    card_m22["m3"]["twmzm"]["ladder_err_convergence_rate"] = 0.5
    probe22 = _m3_reverse_flags(card_m22)["twmzm"]
    check("🔴 探针㉒: m3.twmzm 多一个 ladder_err_convergence_rate ⇒ ④e twmzm 必红",
          probe22 is False)

    # 探针㉓：前缀包含对 —— `m3t.ladder_err_largest` 与 `m3t.ladder_err_smallest` 互不为前缀，
    #   但 `m3t.ladder_err` 是**两者共同前缀**且在路径表里不存在 ⇒ 纯子串口径会把它误判为已引用。
    #   证明边界判定把 `m3t.ladder_err`（未在路径表）判为「不引用任何一条真实路径」。
    _plain4 = "h+=m3t.ladder_err;"
    _strict4 = _js_ref_ok(_fake3, "m3t.ladder_err_largest", _all_lits)
    check("🔴 探针㉓: 只留 m3t.ladder_err（共同前缀）的源码 ⇒ 不得满足 ladder_err_largest 的引用判定",
          _strict4 is False)
    check("🔴 探针㉓b: 真实源码确实同时引用了 ladder_err_largest 与 ladder_err_smallest（防路径表写成死条款）",
          _js_ref_ok(rsrc_m19, "m3t.ladder_err_largest", _all_lits) is True
          and _js_ref_ok(rsrc_m19, "m3t.ladder_err_smallest", _all_lits) is True)

    # 探针㉔：把 ladder 收敛判据**改成恒真的假值**（monotonic=False）⇒ ④e 只管「引用」不管「取值」，
    #   所以这条探针锁定的是另一件事：门禁必须确认前端**不是**只渲染 largest 而漏 smallest。
    #   做法：抹掉 smallest 的字面量 ⇒ 必红。
    _fake5 = "h+='最大 '+(m3t.ladder_err_largest*100).toFixed(4);"
    check("🔴 探针㉔: 前端只渲染 ladder_err_largest、漏掉 ladder_err_smallest ⇒ 必红",
          _js_ref_ok(_fake5, "m3t.ladder_err_smallest", _all_lits) is False
          and _plain4 == "h+=m3t.ladder_err;")

    # ── M4 探针（先证能变红）──────────────────────────────────────────
    # 探针㉕：往 m4 顶层塞一个新字段 ⇒ ④e-43 反向完备必红
    card_m25 = copy.deepcopy(card)
    card_m25["m4"]["brand_new_probe_top4"] = 1
    probe25 = _m4_reverse_flags(card_m25)["top"]
    check("🔴 探针㉕: m4 顶层多一个新字段 ⇒ ④e-43 反向完备必红", probe25 is False)

    # 探针㉖：抹掉 m4.pareto.points[].vpi_v ⇒ ③ 的路径判据必红（前端逐点表引用了它）
    card_m26 = copy.deepcopy(card)
    del card_m26["m4"]["pareto"]["points"][0]["vpi_v"]
    probe26 = json_path_exists(card_m26, "m4.pareto.points[].vpi_v")
    check("🔴 探针㉖: 抹掉 m4.pareto.points[].vpi_v ⇒ ③ 路径判据必红", probe26 is False)

    # 探针㉗：往 m4.pareto.vpi_l 塞一个新字段 ⇒ ④e-52 必红（VπL 断口不能静默加字段）
    card_m27 = copy.deepcopy(card)
    card_m27["m4"]["pareto"]["vpi_l"]["brand_new_vpil_field"] = 1
    probe27 = _m4_reverse_flags(card_m27)["vpi_l"]
    check("🔴 探针㉗: m4.pareto.vpi_l 多一个新字段 ⇒ ④e-52 反向完备必红", probe27 is False)

    # 探针㉘：抹掉 `m4vl.vpi_l_gap_ratio` 的**前端字面量** ⇒ ③ 的 js_ref 必红
    #   （只有后端 JSON 有值而不盯前端 = 假绿；证明 ③ 在 M4 上也真的两端都盯）
    rsrc_m28 = rsrc.replace("m4vl.vpi_l_gap_ratio", "")
    probe28 = _js_ref_ok(rsrc_m28, "m4vl.vpi_l_gap_ratio", _all_lits)
    check("🔴 探针㉘: 前端抹掉 m4vl.vpi_l_gap_ratio 字面量 ⇒ ③ 的 js_ref 必红",
          probe28 is False)

    # 探针㉙：把 `m4.pareto` 的**豁免集**当挡箭牌 —— 往豁免外的字段塞成员仍必须红
    #   （防「豁免集一扩，新成员又静默进盲区」；与 oe_stats 血案同族）
    card_m29 = copy.deepcopy(card)
    card_m29["m4"]["pareto"]["brand_new_pareto_field"] = 1
    probe29 = _m4_reverse_flags(card_m29)["pareto"]
    check("🔴 探针㉙: m4.pareto 塞豁免外新字段 ⇒ ④e-50 仍必红（豁免集不是万能挡箭牌）",
          probe29 is False)

    # 探针㉚：往 `m5` 顶层塞新字段 ⇒ ④e-56 必红（M5 无豁免集 ⇒ 零盲区）
    card_m30 = copy.deepcopy(card)
    card_m30["m5"]["brand_new_probe_top5"] = 1
    probe30 = _m5_reverse_flags(card_m30)["top"]
    check("🔴 探针㉚: m5 顶层多一个新字段 ⇒ ④e-56 反向完备必红", probe30 is False)

    # 探针㉛：把「空集档」伪装成有解（public_high.non_empty ← True）⇒ ④e-57 结构上仍绿，
    #   但**语义**由 oi_case 探针 `probe_m5_settlement_disclosed` 判死 ⇒ 本门禁必须承认
    #   自己**看不到**语义（如实披露边界，不假装拦得住）。
    card_m31 = copy.deepcopy(card)
    card_m31["m5"]["feasible_bands"]["public_high"]["non_empty"] = True
    probe31 = _m5_reverse_flags(card_m31)["bands"]
    check("🔴 探针㉛: 空集档伪装成有解 ⇒ 本门禁（静态结构）**仍绿** ⇒ 语义由 oi_case "
          "探针判死（如实披露：结构检查拦不住口径撒谎）", probe31 is True)

    check("🔴 探针R3: 未被污染的 case_card 在 M4 反向完备十三格上仍全绿（探针无副作用）",
          all(_m4_reverse_flags(card).values()))

    # ── 6. 自入 CI core ────────────────────────────────────────────────
    ci = os.path.join(_ROOT, "lda", "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28 同族）",
          "run_webui_oi_render_path_smoke.py" in ck)

    # ── 汇总（make_check 已逐行打印；此处只出计数）────────────────────
    npass = globals().get("PASS", 0)
    nfail = globals().get("FAIL", 0)
    print()
    print("RESULT: %d PASS / %d FAIL" % (npass, nfail))
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
