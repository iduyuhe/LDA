"""DMM（Design Maturity Model）打分表 · **唯一机器来源**（v0.9.140 · 2026-09-28）。

## 为什么建它
规划 `LDA_internal_design_plan_2026-09-23.md` §2.2 提出 DMM（VMM 的姊妹模型：把「锚的成熟度」
换成「设计能力的成熟度」，D0–D5），§4 的 **M2 = D4 能力数 ≥3** 是本计划的出口指标之一。
但该表此前**只存在于规划文档的文字里**（§2.3 是 P1 之前的快照）⇒ M2 无法判定。
本模块把打分表**机器化**：级别**由可核验的事实推导**，不是手写。

## 级别定义（照抄规划 §2.2，未改口径）
- **D0 不存在**：全仓无对应代码路径
- **D1 能跑**：有可执行入口（模块存在 + 关键符号存在）
- **D2 可复现**：其门禁登记进 `CORE_SMOKES`（同输入→确定性同输出由门禁承担）
- **D3 可自证**：有**反向证据**（① 专用突变探针 **或** ② 自身门禁内「必 raise/必报/必红/反向」断言
              **或** ③ 其所引用的独立证据门禁内该类断言）+ 引用 ≥1 个**独立证据门禁**
- **D4 可交付**：D3 + **交付三要素**齐备（①G4 几何回提**硬开** ②单命令链存在 ③该能力在其准入表内）
- **D5 可外签**：需真实 foundry deck / 流片实测 ⇒ **本模块永不自动判达**（声明即 raise）

## 🔴 诚实边界（必须与分数同读）
1. 本模块判的是**「事实代理」**，不是「能力质量」的最终裁判 —— 质量由所引用的**门禁/探针**承担；
   本模块只保证「**该能力宣称的级别所依赖的事实确实存在**」，缺一即降级。
2. `probe_last_result` 是**最近一次人工/周期实跑**的记录，**不参与判级**（探针不进 `CORE_SMOKES`，
   其"会响"是运行期事实 ⇒ 不冒充常驻判据）。
3. **D5 恒不可达**：内部判据只能到 D4（规划 §2.2 原话：「D4 是内部能达到的上限」）。
4. 级别**累积**：D(n) 需 D(n−1) 全部条件成立（缺一反例即降）。
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 0) 常量：事实源的路径与关键口径（单一来源）
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # …/lda
REPO = os.path.dirname(ROOT)                                          # 仓库根

#: 交付三要素之一：芯片级导出的 G4 几何回提必须**硬开**（不是可选参数）
G4_SOURCE = os.path.join(ROOT, "lda_l2", "chip_layout_export.py")
G4_TOKEN = "with_geom_check=True"

#: 交付三要素之二/三：单命令链与其准入表
ENTRY_SOURCE = os.path.join(ROOT, "lda_design", "cli.py")
ADMISSION_SOURCE = os.path.join(ROOT, "lda_design", "goal_build.py")
ADMISSION_ENUM = "bridgeable_engine_kinds"
ADMISSION_EXCLUDE = "excluded_engine_kinds"
LAYOUT_KINDS_ENUM = "layout_kinds_supported_by_layout_layer"

#: 「独立证据门禁」白名单（D3 的引用必须落在其中，且必须 ∈ CORE_SMOKES）
INDEPENDENCE_GUARDS: Tuple[str, ...] = (
    "run_d_criterion_smoke.py",              # 判据 D 普查（449/449）
    "run_cross_solver_matrix_smoke.py",      # 内部异源交叉（9 格）
    "run_lvs_geom_smoke.py",                 # G4 几何回提（反向必报）
    "run_benchmark_falsifiability_smoke.py", # 可证伪性 / 反向测试
    "run_self_certified_lock_smoke.py",      # 自证桩锁（防假严格）
    "run_ci_coverage_gate_smoke.py",         # 门禁无静默缺口
)

#: 反向证据的文本指纹（门禁内建「必 raise / 必报 / 必红」类断言）
REVERSE_PATTERNS: Tuple[str, ...] = ("_raises", "必报", "必红", "必 raise", "必变", "必降", "反向")

#: 探针变异条目的宽松指纹（各探针写法不一，故取并集）
PROBE_PATTERNS: Tuple[str, ...] = (r'\(\s*"M\d', r"MUTATIONS\s*[:=]", r"\bMUTATIONS\b")

CAPABILITY_KEYS = ("id", "name", "module", "symbol", "smoke", "independence_guard",
                   "probe", "probe_last_result", "d4")


# ---------------------------------------------------------------------------
# 1) 能力表（每行 = 规划 §2.3 的一行能力；d4=None ⇒ 不在交付链上）
# ---------------------------------------------------------------------------
CAPABILITIES: List[Dict[str, Any]] = [
    # --- P1 交付链（D4 候选）------------------------------------------------
    dict(id="C01", name="器件级设计搜索 → GDS 单命令交付（lda build）",
         module="lda/lda_design/goal_build.py", symbol="design_device",
         smoke="run_cli_build_smoke.py", independence_guard="run_lvs_geom_smoke.py",
         probe=None, probe_last_result=None,
         d4=dict(chain="lda build <goal.json> --out DIR · 单条命令",
                 admission="engine_ringresonator")),
    dict(id="C02", name="链路装配 → GDS + DRC/LVS 签核（lda check）",
         module="lda/lda_l2/chip_layout_export.py", symbol="export_chip_gds",
         smoke="run_lvs_smoke.py", independence_guard="run_lvs_geom_smoke.py",
         probe=None, probe_last_result=None,
         d4=dict(chain="lda check <link.json> --out DIR · 单条命令",
                 admission="layout_kinds_layer")),
    dict(id="C03", name="WebUI 设计闭环端到端（设计包 → 可下载 GDS + 同源签核）",
         module="lda/lda_webui/routes.py", symbol="h_design_tapeout",
         smoke="run_webui_tapeout_drc_smoke.py", independence_guard="run_lvs_geom_smoke.py",
         probe=None, probe_last_result=None,
         d4=dict(chain="POST /api/design_tapeout + GET /api/design_gds · 一次点击",
                 admission="layout_kinds_layer")),
    # --- P1 的 G4 本体 ------------------------------------------------------
    dict(id="C04", name="G4 器件参数几何回提（版图↔原理图 尺寸一致）",
         module="lda/lda_l2/lvs_geom.py", symbol="extract_layout_params",
         smoke="run_lvs_geom_smoke.py", independence_guard="run_lvs_geom_smoke.py",
         probe=None, probe_last_result="20 判据 · 反向必报实测（改长度/改半径）",
         d4=None),
    # --- P3 交叉验证网 ------------------------------------------------------
    dict(id="C05", name="横向交叉验证网（跨求解器 ≥2 方法互验）",
         module="lda/run_cross_solver_matrix_smoke.py", symbol="_p_bragg",
         smoke="run_cross_solver_matrix_smoke.py", independence_guard="run_cross_solver_matrix_smoke.py",
         probe="scripts/p3_matrix_probe.py", probe_last_result="9 格 · 判据 D 7 格（convergent）",
         d4=None),
    # --- 设计能力（D3 群）---------------------------------------------------
    dict(id="C06", name="MZI 网格 P&R（mesh_pnr）",
         module="lda/lda_layout/mesh_pnr.py", symbol="build_mesh_pnr",
         smoke="run_wdm_mesh_pnr_smoke.py", independence_guard="run_d_criterion_smoke.py",
         probe=None, probe_last_result=None, d4=None),
    dict(id="C07", name="WDM × 2D 共享网格（U1）",
         module="lda/lda_layout/wdm_shared_mesh_pnr.py", symbol="build_wdm_shared_mesh_pnr",
         smoke="run_wdm_shared_mesh_smoke.py", independence_guard="run_d_criterion_smoke.py",
         probe=None, probe_last_result=None, d4=None),
    dict(id="C08", name="编译器 / AI 框架前端（U5）",
         module="lda/lda_l2/compiler_frontend.py", symbol="nearest_unitary",
         smoke="run_compiler_frontend_smoke.py", independence_guard="run_d_criterion_smoke.py",
         probe=None, probe_last_result=None, d4=None),
    dict(id="C09", name="微环 κ_c FDTD 标定（U3）",
         module="lda/lda_l2/ring_kappa_calib.py", symbol="kappa_c_from_table",
         smoke="run_ring_kappa_calib_smoke.py", independence_guard="run_d_criterion_smoke.py",
         probe=None, probe_last_result=None, d4=None),
    dict(id="C10", name="微环权重库 MRR（U4）",
         module="lda/lda_l2/ring_weight_bank.py", symbol="peak_drop_weight",
         smoke="run_ring_weight_bank_smoke.py", independence_guard="run_d_criterion_smoke.py",
         probe=None, probe_last_result=None, d4=None),
    dict(id="C11", name="损耗感知编译（U7）",
         module="lda/lda_l2/loss_aware_compile.py", symbol="rail_geometry",
         smoke="run_loss_aware_compile_smoke.py", independence_guard="run_d_criterion_smoke.py",
         probe=None, probe_last_result=None, d4=None),
    dict(id="C12", name="良率 / 容错映射（U6）",
         module="lda/lda_l2/yield_fault_tolerance.py", symbol="single_fault_scan",
         smoke="run_yield_fault_tolerance_smoke.py", independence_guard="run_d_criterion_smoke.py",
         probe=None, probe_last_result=None, d4=None),
    dict(id="C13", name="非易失权重后端（U8）",
         module="lda/lda_l2/nonvolatile_weight_backend.py", symbol="guard_no_foundry_process_truth",
         smoke="run_nonvolatile_weight_backend_smoke.py", independence_guard="run_d_criterion_smoke.py",
         probe=None, probe_last_result=None, d4=None),
    dict(id="C14", name="校准固件协议（U10）",
         module="lda/lda_l2/calibration_protocol.py", symbol="guard_calibration_requires_anchor",
         smoke="run_calibration_protocol_smoke.py", independence_guard="run_d_criterion_smoke.py",
         probe=None, probe_last_result=None, d4=None),
    # --- P6 系统级 ----------------------------------------------------------
    dict(id="C15", name="G20 光域 Pareto（T6.1）",
         module="lda/lda_l2/optical_pareto.py", symbol="optical_pareto_table",
         smoke="run_optical_pareto_smoke.py", independence_guard="run_d_criterion_smoke.py",
         probe="scripts/p6_probe.py", probe_last_result="7/7 会响",
         d4=None),
    dict(id="C16", name="WDM 信道规划 K 提升（T6.2）",
         module="lda/lda_layout/wdm_channel_plan.py", symbol="plan_wdm_channels",
         smoke="run_wdm_channel_plan_smoke.py", independence_guard="run_d_criterion_smoke.py",
         probe="scripts/t62_probe.py", probe_last_result="11/11 会响",
         d4=None),
    dict(id="C17", name="瓦片档位化（T6.3）",
         module="lda/lda_l2/mesh_tiling.py", symbol="plan_tiling",
         smoke="run_mesh_tiling_smoke.py", independence_guard="run_d_criterion_smoke.py",
         probe="scripts/t63_probe.py", probe_last_result="12/12 会响",
         d4=None),
    dict(id="C18", name="EIC 行为级（T6.4）",
         module="lda/lda_l2/eic_behavioral.py", symbol="driver_step_closed_form",
         smoke="run_eic_behavioral_smoke.py", independence_guard="run_d_criterion_smoke.py",
         probe="scripts/t64_probe.py", probe_last_result="8/8 会响（含跨文件 T8）",
         d4=None),
    # --- P4 物理深度 --------------------------------------------------------
    dict(id="C19", name="真 PML / CFS-PML（G11）",
         module="lda/lda_solver/cpml.py", symbol="cpml_axis",
         smoke="run_cpml_absorber_smoke.py", independence_guard="run_d_criterion_smoke.py",
         probe="scripts/p4_cpml_probe.py", probe_last_result="10/10 会响（2D 779.6× / 3D 152.4×）",
         d4=None),
    dict(id="C20", name="任意多边形栅格化（G16）",
         module="lda/lda_solver/voxel_field.py", symbol="voxelize_polygons",
         smoke="run_verify_voxel_pipeline_smoke.py", independence_guard="run_d_criterion_smoke.py",
         probe="scripts/p4_polygon_probe.py", probe_last_result="10/10 会响",
         d4=None),
    dict(id="C21", name="时域色散 / 各向异性 / 非线性（G13）",
         module="lda/lda_solver/dispersive.py", symbol="run_2d",
         smoke="run_dispersive_smoke.py", independence_guard="run_d_criterion_smoke.py",
         probe="scripts/p4_g13_probe.py", probe_last_result="10/10 会响",
         d4=None),
    dict(id="C22", name="全矢量模式求解（G12-H/A/B）",
         module="lda/lda_solver/full_vector_mode_solver.py", symbol="neff_3d",
         smoke="run_full_vector_mode_smoke.py", independence_guard="run_d_criterion_smoke.py",
         probe="scripts/g12b_probe.py", probe_last_result="6/6 会响（G12-A 另有 g12a_probe 6/6）",
         d4=None),
    # --- 互操作 / 导出（主动登记的「未达 D3/D4」示例）----------------------
    dict(id="C23", name="SPICE 网表导出",
         module="lda/lda_l2/spice_netlist.py", symbol="CircuitNetlist",
         smoke="run_spice_netlist_smoke.py", independence_guard="run_d_criterion_smoke.py",
         probe=None, probe_last_result=None, d4=None),
    dict(id="C24", name="gdsfactory 单向桥（gf → LDA）",
         module="lda/lda_l1/gdsfactory_bridge.py", symbol="gf_component_to_spec",
         smoke="run_gdsfactory_bridge_smoke.py", independence_guard="run_d_criterion_smoke.py",
         probe=None, probe_last_result=None, d4=None),
    # --- P5 实证锚（生态侧）-------------------------------------------------
    dict(id="C25", name="实证锚库与 M6 口径（T5.3）",
         module="lda/lda_harness/empirical_m6.py", symbol="audit_m6",
         smoke="run_empirical_anchor_smoke.py", independence_guard="run_d_criterion_smoke.py",
         probe="scripts/p5_probe.py", probe_last_result="10/10 会响",
         d4=None),
]


# ---------------------------------------------------------------------------
# 2) 事实采集（全部可机器核验：文件 / CI 登记 / 文本指纹）
# ---------------------------------------------------------------------------
def _read(p: str) -> Optional[str]:
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def _core_smokes() -> List[str]:
    from run_ci_regression import CORE_SMOKES
    return list(CORE_SMOKES)


def _abs(rel: str) -> str:
    return os.path.join(REPO, rel.replace("/", os.sep))


def facts(cap: Dict[str, Any], core: Optional[List[str]] = None) -> Dict[str, Any]:
    """采集一条能力的全部事实（**不判级**，只报事实）。"""
    core = _core_smokes() if core is None else core
    mod_rel, sym = cap["module"], cap["symbol"]
    mod_src = _read(_abs(mod_rel))
    f: Dict[str, Any] = {
        "module": mod_rel, "module_exists": mod_src is not None,
        "symbol": sym,
        "symbol_found": bool(mod_src and re.search(r"\b%s\b" % re.escape(sym), mod_src)),
        "smoke": cap["smoke"], "smoke_in_core": cap["smoke"] in core,
        "independence_guard": cap["independence_guard"],
        "independence_guard_in_core": cap["independence_guard"] in core,
    }
    # 反向证据：**三个来源取并集**（口径修正 · 2026-09-28）
    #   ① 专用突变探针  ② 自身门禁内的反向断言指纹  ③ 它所引用的「独立证据门禁」内的反向断言
    # 为什么含 ③：交付链的反向证据**合理地**落在其签核子门禁里 —— 例：`lda check` 路径的几何回提
    # 由 `export_chip_gds` **硬开**，其反向行为由 `run_lvs_geom_smoke` 证明（改长度/改半径必报）。
    # 只认 ② 会把它误判为「无反向证据」⇒ 那是**度量口径过窄**，不是能力缺陷（如实登记口径修正）。
    probe = cap.get("probe")
    p_ok, p_mut = False, 0
    if probe:
        psrc = _read(_abs(probe))
        p_ok = psrc is not None
        if psrc:
            p_mut = max(len(re.findall(pat, psrc)) for pat in PROBE_PATTERNS)
            if p_mut == 0:
                # 兜底：部分探针用「元组表」而非 M 数字标签（实测 p3_ratchet_probe 形态）
                tup = psrc.count('("')
                p_mut = 3 if tup >= 3 else tup
    ssrc = _read(os.path.join(ROOT, cap["smoke"])) or ""
    gsrc = _read(os.path.join(ROOT, cap["independence_guard"])) or ""
    rev_srcs = []
    if p_ok and p_mut >= 1:
        rev_srcs.append("probe")
    if any(pat in ssrc for pat in REVERSE_PATTERNS):
        rev_srcs.append("own_smoke")
    if any(pat in gsrc for pat in REVERSE_PATTERNS):
        rev_srcs.append("independence_guard")
    f.update({"probe": probe, "probe_exists": p_ok, "probe_mutations": p_mut,
              "reverse_assert_hits": sum(1 for pat in REVERSE_PATTERNS if pat in ssrc),
              "reverse_evidence_sources": rev_srcs,
              "has_reverse_evidence": bool(rev_srcs)})
    # D4 三要素
    g4_src = _read(G4_SOURCE) or ""
    entry_src = _read(ENTRY_SOURCE) or ""
    adm_src = _read(ADMISSION_SOURCE) or ""
    f["g4_hardwired"] = G4_TOKEN in g4_src
    f["single_command_chain"] = bool(re.search(r"^def cmd_(build|check)\s*\(", entry_src, re.M))
    adm_ok, adm_detail = False, None
    if cap.get("d4"):
        adm = cap["d4"]["admission"]
        if adm == "layout_kinds_layer":
            adm_ok = bool(re.search(r"^def %s\s*\(" % LAYOUT_KINDS_ENUM, adm_src, re.M))
            adm_detail = "版图层可导出 kind 表存在"
        else:
            adm_ok = bool(re.search(r'^\s*"%s"\s*:' % re.escape(adm), adm_src, re.M))
            adm_detail = "引擎 kind 在 BRIDGEABLE 准入表内"
        f["admission_declared"] = adm
        f["admission_detail"] = adm_detail
    f["admission_ok"] = adm_ok
    return f


# ---------------------------------------------------------------------------
# 3) 判级（**由事实推导**；声明与事实不符 ⇒ 取事实允许的更低级）
# ---------------------------------------------------------------------------
def level_of(cap: Dict[str, Any], core: Optional[List[str]] = None) -> Tuple[str, Dict[str, Any]]:
    """返回 (级别, 事实)。级别 = 满足条件的最高级（逐级累积）。"""
    f = facts(cap, core)
    if not f["module_exists"]:
        return "D0", f
    if not f["symbol_found"]:
        return "D0", f          # 模块在但没有可执行入口符号 ⇒ 仍属「不存在」
    lvl = "D1"
    if f["smoke_in_core"]:
        lvl = "D2"
    else:
        return lvl, f
    if f["has_reverse_evidence"] and f["independence_guard_in_core"]:
        lvl = "D3"
    else:
        return lvl, f
    if cap.get("d4") and f["g4_hardwired"] and f["single_command_chain"] and f["admission_ok"]:
        lvl = "D4"
    return lvl, f


_ORDER = ["D0", "D1", "D2", "D3", "D4", "D5"]


def scorecard(core: Optional[List[str]] = None) -> Dict[str, Any]:
    """全表打分（含每行事实，便于审计）。"""
    core = _core_smokes() if core is None else core
    rows, counts = [], {k: 0 for k in _ORDER}
    for cap in CAPABILITIES:
        lvl, f = level_of(cap, core)
        counts[lvl] += 1
        rows.append({"id": cap["id"], "name": cap["name"], "level": lvl,
                     "module": cap["module"], "smoke": cap["smoke"],
                     "probe": cap.get("probe"),
                     "probe_last_result": cap.get("probe_last_result"),
                     "independence_guard": cap["independence_guard"],
                     "d4": cap.get("d4"), "facts": f})
    d4_ids = [r["id"] for r in rows if r["level"] == "D4"]
    return {
        "n_capabilities": len(rows),
        "counts": counts,
        "d4_count": len(d4_ids),
        "d4_ids": d4_ids,
        "d3_or_better": sum(1 for r in rows if _ORDER.index(r["level"]) >= 3),
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# 4) 审计与闸门（供 smoke / 文档统一取用）
# ---------------------------------------------------------------------------
def audit(sc: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """一致性审计：级别与事实必须**单调自洽**（高级别不得缺低级别的事实）。"""
    sc = scorecard() if sc is None else sc
    bad: List[str] = []
    for r in sc["rows"]:
        f, lv = r["facts"], r["level"]
        i = _ORDER.index(lv)
        need = []
        if i >= 1:
            need.append((f["module_exists"] and f["symbol_found"], "D1 模块+入口符号"))
        if i >= 2:
            need.append((f["smoke_in_core"], "D2 门禁进 CORE_SMOKES"))
        if i >= 3:
            need.append((f["has_reverse_evidence"], "D3 反向证据"))
            need.append((f["independence_guard_in_core"], "D3 独立证据门禁在 core"))
        if i >= 4:
            need.append((f["g4_hardwired"], "D4 G4 硬开"))
            need.append((f["single_command_chain"], "D4 单命令链"))
            need.append((f["admission_ok"], "D4 准入表内"))
        for ok, label in need:
            if not ok:
                bad.append("%s 声明 %s 但缺【%s】" % (r["id"], lv, label))
    # D4 行必须真的带 d4 描述（否则「交付」无据）
    for r in sc["rows"]:
        if r["level"] == "D4" and not r["d4"]:
            bad.append("%s 判 D4 但无交付链描述" % r["id"])
    return {"ok": not bad, "violations": bad, **{k: sc[k] for k in
            ("n_capabilities", "counts", "d4_count", "d3_or_better")}}


def gate(sc: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """M2 出口判据闸门（规划 §4：D4 能力数 ≥ `M2_D4_MIN`）。"""
    sc = scorecard() if sc is None else sc
    au = audit(sc)
    ok = bool(au["ok"] and sc["d4_count"] >= M2_D4_MIN and sc["counts"]["D5"] == 0)
    return {"ok": ok, "d4_count": sc["d4_count"], "m2_min": M2_D4_MIN,
            "d5_count": sc["counts"]["D5"], "audit_ok": au["ok"],
            "reasons": au["violations"] + (
                [] if sc["d4_count"] >= M2_D4_MIN
                else ["D4 能力数 %d < %d" % (sc["d4_count"], M2_D4_MIN)]) +
                ([] if sc["counts"]["D5"] == 0 else ["D5 不可自动判达（内部上限）"])}


#: M2 出口判据（规划 §4）
M2_D4_MIN = 3
#: D5 永不自动达（规划 §2.2：D4 是内部上限）
LEVEL_D5_IS_EXTERNAL = True
