# -*- coding: utf-8 -*-
"""WebUI 光联接模块 M0 + M1 + M2 案例卡前端**取值路径 + onclick**门禁（新征程 · 2026-10-02）。

═══════════════════════════════════════════════════════════════════════════
为什么存在（血案 #18 / #19 机器化）
═══════════════════════════════════════════════════════════════════════════
E17-e 生产实测：`renderECore` 取 `synthesis_law.serial_ns`，而该值实际在
`synthesis_law.demo.serial_ns` ⇒ **三格显示 0.0**。后端侧一切门禁
（案例卡 B1–B24 / API 验收）**都看不到这一层**：它们只保证 JSON 里有值，
**不保证前端问对了地方**。

本门禁把 `renderOi`（`sec-oi` 面板）的每条取值路径（M0 根块 + M1 子块 + M2 子块），
逐条拿到真实 `oi_case.case_card()` JSON 上解析，并验证 `onclick` 接线反向
完备——把「JSON 里有值 ≠ 前端问对了地方」这层钉死。

───────────────────────────────────────────────────────────────────────────
判什么
───────────────────────────────────────────────────────────────────────────
1. **onclick 接线**：$('runOi').onclick = runOi 在场（防「能力上线却点不动」）。
2. **函数定义**：runOi / renderOi 在 index.html 内定义（且真的含 M1/M2 块引用）。
3. **路径存在性**：renderOi 引用的每条 d./m1./rp./dv./sp./fx./rq./c./m./g./
   m2./m2rp./m2dv./m2g./m2fec./m2cf./m2rs./m2fm. 取值路径，在真实 JSON 上逐段
   解析；**任一段不存在 ⇒ 红**（血案 #18/#19 要抓的）。
4. **反向完备**：case_card() 下每个展示字段——channels 元素、requested 子字段、
   milestones/gaps 元素字段，**以及 M1 块顶层 + `ring_plan` / `driver` /
   `spec_points[]` / `m0_fixes[]` 四组嵌套字段 + M2 块顶层 + `fec` /
   `fec.concatenated` / `fec.rs_only` / `fec.form_map` / `ring_plan` / `driver` /
   `spec_points[]` / `g_oi2` / `platform_fixes_m2[]` 九组嵌套字段**——都必须被前端
   引用（防「后端加了、前端不显示」的静默盲区）。🔴 M2 块是**新成员**：若本门禁
   不扩，M2 全块会静默落进盲区（正是本条纪律要防的）。
5. **突变探针**（先证能变红）：
   ① 抹掉 case_card 某 channel 字段 ⇒ ③ 路径判据必红；
   ② 删掉 onclick 接线行 ⇒ ① 接线判据必红；
   ③ 抹掉 `m1.ring_plan.m` ⇒ ③ 的 M1 路径判据必红；
   ④ 往 `m1.ring_plan` 塞一个新字段 ⇒ ④ 的 ring 反向完备必红；
   ⑤ 往 `m1` 顶层塞一个新字段 ⇒ ④ 的 m1 顶层反向完备必红；
   ⑦ 往 `m2` 顶层塞一个新字段 ⇒ ④e-6 m2 顶层反向完备必红；
   ⑧ 抹掉 `m2.spec_points[].verdict_point` ⇒ ③ 的 M2 路径判据必红；
   ⑨ 往 `m2.fec` 塞一个新字段 ⇒ ④e-7 fec 反向完备必红。还原后复绿。
6. 自入 CI core（防静默漏接 · 血案 #28 同族）。

🔴 诚实边界：本门禁是**静态路径检查**，不执行 JS、不看渲染是否「好看」；
值存在但**语义不对**（口径漂移）仍由 oi_case.run_selfchecks + run_oi_m0_smoke /
run_oi_m1_smoke / run_oi_m2_smoke 那类「卡内数字 ≡ 模块现算」判据守。二者互补：
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

ALL_PATHS = (ROOT_PATHS + REQUESTED_PATHS + CHANNEL_PATHS + MILESTONE_PATHS
             + GAP_PATHS + M1_TOP_PATHS + M1_DRIVER_PATHS + M1_RING_PATHS
             + M1_SPEC_PATHS + M1_FIX_PATHS
             + M2_TOP_PATHS + M2_FEC_PATHS + M2_FEC_MODE_PATHS + M2_DRIVER_PATHS
             + M2_RING_PATHS + M2_SPEC_PATHS + M2_GDS_PATHS + M2_FIX_PATHS)

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


def main() -> int:
    print("=" * 74)
    print("WebUI 光联接模块 M0+M1+M2 案例卡 前端取值路径 + onclick 门禁（血案 #18/#19 机器化）")
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

    # ── 5. 突变探针（先证能变红）───────────────────────────────────────
    import copy
    # 探针①：抹掉 case_card 的某 channel 字段 ⇒ ③ 的路径判据必红
    card_mut = copy.deepcopy(card)
    del card_mut["channels"][0]["il_cascade_db"]
    probe1 = json_path_exists(card_mut, "channels[].il_cascade_db")
    check("🔴 探针①: 抹掉 channels[].il_cascade_db ⇒ ③ 路径判据必红",
          probe1 is False)

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
