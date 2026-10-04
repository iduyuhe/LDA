# -*- coding: utf-8 -*-
"""光子存储阵列案例卡（WebUI 只读端点数据源）· PM 征程 M3。

定位
----
光子存储征程 PM-M0…M3 的**只读案例**：用 LDA 亲手设计一条**非易失光子存储
单元 → 阵列**（Si 波导 + GST 相变段 + 双侧微加热器 + 电极 pad），走完
**P&R → 布线路由 → 几何 DRC/LVS → 独立 GDS 字节复核 → 设计预算**全链路签核，
并出**真 GDSII**。

🔴 **零重计算**（与站内 cpo_array / design_* 等重算端点不同）：本模块**不跑
P&R、不 import 求解器、不解析 GDS** —— 全部数字取自
① 静态里程碑/结论（人工登记，可回溯到门禁与 report）
② **预生成报告 JSON**（`examples/photo_memory/lda_pm_m3_report.json`，由货架脚本
   `examples/photo_memory/build_pm_m3.py` 产出；本模块只 `json.load` + `stat`）。
⇒ **无 DoS 面**，故**免登录、不进 HEAVY_POST_PATHS**。

🔴 **不伪装实测**：`verdict` 恒为 `DESIGN_SIGNOFF`（**非** ACCEPT/PASS），
返回体自带 `honest_note`；DRC 限值为**自建设计规则**（非 foundry PDK deck）。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

__all__ = [
    "CASE_ID", "PM_HONEST_NOTE", "MILESTONES", "FINDINGS", "GAPS",
    "STATIC_SNAPSHOT", "case_card", "run_selfchecks",
]

CASE_ID = "LDA-PM · 非易失光子存储阵列版图（GST 相变 · 电辅助写）"

#: 单元/阵列的**版图契约**（与 `lda_l2.primitives` / `gds_export` 同源）
PCM_LAYERS = {"SI": 1, "PCM": 5, "HEATER": 6}
PCM_PORTS = ["in", "out", "h1", "h2", "h3", "h4"]

PM_HONEST_NOTE = (
    "① 本案例是**设计期签核**（版图 + 几何 DRC + LVS + 设计预算），**非流片、非实测**"
    "——无实测开关比/保持时间/循环寿命，无 foundry 回片；"
    "② DRC 限值是**自建设计规则**（公开工艺近似 + 探针接触常识），"
    "**非任何 foundry 的 PDK deck**；"
    "③ 单元插损含 **Γ（模场重叠）假设**（缺口 PM-G2 未闭合）⇒ 一律**区间**口径，"
    "跨来源材料常数离散度 >1 个数量级 ⇒ **任何单值结论都是伪精度**；"
    "④ 单元间距由 **k_iso × L_max** 给出，`k_iso` 是**设计选择**（不是物理常数）"
    "——本卡并报 L_max 的两个口径（扩散 / 集总 RC），不假装它是真值；"
    "⑤ 阵列总插损是**串行累加**（N × 单元），**不含**单元间连接波导的传播损耗"
    "（该损耗无本项目锚 ⇒ 不编数）；"
    "⑥ **无电学/热学联仿**：微加热器的电压/电流/焦耳热分布、热-光耦合动力学"
    "不在本档（属器件级 T1 与电路级 T2 锁死区）；"
    "⑦ 规模数字是**版图容量**（可排布且可签核的单元数），**非**已制备器件数；"
    "⑧ **不报 pJ/bit、fJ/op、TOPS、TOPS-W 类能效指标**（红线）；"
    "⑨ 全程零外部 EDA/光学框架（C 级自主，numpy/标准库自研），"
    "判决为死标量比对，**LLM 不进判决路径**。"
)

# ═══════════════════════ 四段征程（静态事实 · 可回溯门禁）════════════════════
# 🔴 口径（v0.9.191 修正）：`gate` = 该档**后端门禁判据数**，须与对应 smoke 实跑的
#   `[PASS]` 计数逐档相等（可人工复核 `grep -c '\[PASS\]'`）：
#   M0 `run_pm_m0_smoke`=33 · M1 `run_pm_m1_smoke`=24 · M2 `run_pm_m2_smoke`=40 ·
#   M3 `run_pm_m3_smoke`=22。
#   🔴 前端渲染门禁 `run_webui_pm_render_path_smoke`(=20) 是**另一个门禁**，不并入本表
#      —— 前三档没有对应前端门禁，混口径会让跨档数字不可比。
#   🔴 血案：M3 曾误登记 `gate=62`（把「后端判据 + 前端判据 + 案例卡自检 + 探针」混成
#      一个数），与 M0/M1/M2 口径不一致 ⇒ 本版修正为 22（= smoke 实跑值）。
MILESTONES = [
    {"id": "M0", "code": "v0.9.187", "title": "单元闭式基线 + 相变材料锚库",
     "gate": 33,
     "result": "🔴 核心闭式律：每 π 损耗 IL_π ≡ (10/ln10)·2πk/Δn —— **Γ 与器件长度"
               "同时约掉**；单元双态对比度 28.2–489.4 dB（跨 4 个独立来源，"
               "离散 15.2×）⇒ 一律区间口径"},
    {"id": "M1", "code": "v0.9.188", "title": "多电平设计层（JMAK 晶化动力学）",
     "gate": 24,
     "result": "几何无关可行性判据 r = k_a/(k_c−k_a) ≤ 0.198（**Γ 与 L 同约掉**）；"
               "GST 4/5 来源可行 ⇒ 设计点 L = 11.01 µm · 级间距 6.57% · "
               "worst BER 4.78e-14；4 bit/单元（16 电平）"},
    {"id": "M2", "code": "v0.9.189", "title": "热-可靠性层（瞬态热 + 非晶 drift）",
     "gate": 40,
     "result": "可非晶化最大膜厚 L_max **双口径**（扩散 768–879 nm / 集总 RC 240–272 nm）；"
               "冷却时间 τ_cool ≈ 1.3 ns ≪ 脉冲 ⇒ 冷却不是瓶颈；电学域保持窗口 "
               "34/199/1162 s（log_range 2/3/4 decade）；🔴 光学域 drift **无直接锚**"
               "⇒ 派生缺口 PM-G7 如实开放"},
    {"id": "M3", "code": "v0.9.191", "title": "阵列版图（真 GDS + DRC/LVS + 独立复核）",
     "gate": 22,
     "result": "新器件原语 **PCMCell**（五处契约同步）；单元间距 = max(k_iso×L_max, "
               "工艺间隙) ⇒ pitch 18.05 µm；1×N 与 R×C 两种阵列；"
               "**从最终 GDS 字节独立解码复核**（层 5 = 单元数、层 6 = 6×单元数）；"
               "规模档 4/8/16/32 单元 + 4×8 全部 **DRC PASS + LVS ACCEPT(0 违规)**"},
]

# 各档**后端**突变探针数（与各 smoke 输出的 `[PASS] P*` 计数一致；派生用，勿写死合计）
MILESTONE_PROBES = {"M0": 6, "M1": 5, "M2": 7, "M3": 5}

FINDINGS = [
    {"title": "热串扰间距是版图的**物理约束**（不是随意留白）",
     "detail": "相邻单元间距 = `k_iso × L_max`，`L_max` 取自 M2 的热扩散口径上界"
               "（0.8788 µm）⇒ 8 个扩散长度 = 7.03 µm，**大于**工艺间隙（6.0 µm）"
               "而成为 binding 约束 ⇒ 单元 pitch 18.05 µm。若热学给不出更小的 "
               "L_max，版图密度就上不去 —— 这是「材料/热学结论直接改版图」的实证。"},
    {"title": "光学 IO 必须**引出**，否则光栅与电极 pad 几何打架",
     "detail": "GratingCoupler 的齿区沿 y 伸出约 10 µm，而 PCM 单元的电极 pad 就在"
               "光端口旁（y = ±1.1 µm）⇒ 直接放光栅会与 pad 重叠。设计上在总线两端加"
               "**引出波导**（20 µm），把光栅推到远离 pad 处；多总线阵列的行间距"
               "（16 µm）亦由「光栅高度 + pad 半高」定出。"},
    {"title": "端口归属的**容差纪律**决定了器件几何",
     "detail": "LVS 以 1.0 µm 容差把布线端点归到最近端口。若电极 pad 中心离波导端点"
               "在容差内，端点会退化为「靠更近取胜」的脆弱判定 ⇒ 设计上把 "
               "`heat_gap` 取 0.35 µm（电极中心 y = 1.10 µm > 容差）使归属**无歧义**。"},
    {"title": "签核判决不读生成端结论：从**最终字节**独立解码复核",
     "detail": "阵列以 flat 导出（不做 AREF 压缩），由自写的最小 GDSII 记录流解析器"
               "（**刻意不复用** `gds_export` 解码器）从字节解出层分布："
               "层 5 元素数必须**恰等于**单元数、层 6 必须**恰等于** 6× 单元数，"
               "且必须真的走到 ENDLIB（截断即拒）。这与「声明闭合 ⇔ 证据机器可查」"
               "同一条纪律。"},
    {"title": "吃狗粮抓出的**框架级真缺陷**：端口锚点缓存被 id 复用毒化",
     "detail": "本档首次在同一进程内多次构建阵列时暴露：`placement.port_abs` 的组件"
               "索引缓存**仅以 `id()` 为键**，上一批对象被 GC 后新对象复用同一 id ⇒ "
               "命中陈旧索引 ⇒ 端口偏移静默退回器件原点 ⇒ 51 处 LVS 假红。已修："
               "缓存值**持有对象引用 + 身份校验 + 组件数版本**；并把 `port_abs` 的"
               "「实例不在 link ⇒ 静默返回器件原点」改为 **raise**。"},
]

GAPS = [
    {"id": "PM-G2", "title": "模场重叠因子 Γ 的 FDTD 标定（开放）",
     "detail": "Γ 仍为假设参数 ⇒ 单元绝对插损/长度结论对它的线性敏感被并报，"
               "但每 π 损耗与 Γ 无关（闭式已证）。"},
    {"id": "PM-G6", "title": "相位域（谐振/干涉）多电平读出与漂移口径（开放）",
     "detail": "本卡只走振幅域（波导直通 + 相变吸收调制）；相位域口径未建。"},
    {"id": "PM-G7", "title": "光学域 drift 定量锚（@1550 nm 的 n/k 随时间）（开放）",
     "detail": "电学域有 4 条 ν 锚；光学域**无直接锚**（M2 判定）⇒ 阵列长期保持"
               "只能给电学域口径。"},
    {"id": "PM-G8", "title": "加热器电-热联仿与 T1 器件级真值（本档新增登记）",
     "detail": "版图只交付**几何**（加热线 + pad 的尺寸/间距）；焦耳热分布、"
               "热-光耦合动力学、开关能耗真值属**器件级 T1 / 电路级 T2 锁死区**"
               "（无 PDK ⇒ 不报）。"},
]

#: 报告 JSON 不在本部署时的**内置快照**（2026-10-04 实测 · 仅供降级展示）。
#: 🔴 **schema 必须与 `examples/photo_memory/lda_pm_m3_report.json` 逐块同构** ——
#: 由 `run_pm_m3_smoke.py` 的「快照 == 仓库当前状态」判据常驻守（铁律：入库生成物
#: 必须配快照一致性判据，否则每加一批锚就多一份静默失真）。
STATIC_SNAPSHOT: Dict[str, Any] = {
    "array_8x1": {
        "kind": "1 bus × 8 cells",
        "stats": {"n_devices": 10, "n_nets": 11, "n_elements": 109,
                  "area_um2": 1223.44, "width_um": 197.33, "height_um": 6.2,
                  "bbox_um": [-40.0, -3.1, 157.33, 3.1], "gds_bytes": 6224,
                  "multilayer": False, "n_io": 2, "n_structures": 1},
        "drc": {"all_pass": True, "n_checked": 10, "n_pass": 10},
        "lvs": {"verdict": "ACCEPT", "n_violations": 0},
        "independent_scan": {
            "n_structures": 1, "n_elements": 109,
            "layers": {"1": 53, "5": 8, "6": 48},
            "by_kind": {"aref": 0, "boundary": 72, "path": 37, "sref": 0},
            "n_sref": 0, "n_aref": 0, "total_length_um": 379.57},
        "expected": {"PCM": 8, "HEATER": 48, "SI_devices": 10, "SI_routes": 9,
                     "layers_expected": {"5": 8, "6": 48},
                     "n_devices": 10, "n_nets": 9},
        "gds": {"bytes": 6224,
                "sha256": "（快照未含 sha；请以仓库 examples 报告为准）"},
    },
    "array_4x8": {
        "kind": "4 buses × 8 cells",
        "stats": {"n_devices": 40, "n_nets": 44, "n_elements": 436,
                  "area_um2": 10695.27, "width_um": 197.33, "height_um": 54.2,
                  "bbox_um": [-40.0, -3.1, 157.33, 51.1], "gds_bytes": 24710,
                  "multilayer": False, "n_io": 8, "n_structures": 1},
        "independent_scan": {
            "layers": {"1": 212, "5": 32, "6": 192},
            "by_kind": {"aref": 0, "boundary": 288, "path": 148, "sref": 0},
            "n_elements": 436, "n_sref": 0, "n_aref": 0,
            "n_structures": 1, "total_length_um": 1518.28},
        "drc_all_pass": True, "lvs_verdict": "ACCEPT", "lvs_n_violations": 0,
    },
    "pitch": {"l_cell_um": 11.0146, "gap_um": 7.0304, "gap_thermal_um": 7.0304,
              "gap_process_um": 6.0, "binding": "thermal", "pad_um": 4.0,
              "pitch_um": 18.045,
              "thermal": {"material": "GST", "k_iso": 8.0,
                          "l_max_diff_um": 0.8788, "l_max_rc_um": 0.2723,
                          "min_gap_um": 7.0304, "min_gap_um_rc_basis": 2.1787,
                          "literature_l_ref_um": 0.15,
                          "basis": "k_iso × L_max（热扩散口径上界）· k_iso 为设计选择"}},
    "budget": {"material": "GST", "n_cells_total": 8, "n_levels": 16,
               "bits_per_cell": 4, "l_cell_um": 11.0146,
               "array_states": 128, "array_bits": 32, "n_electrode_pads": 32,
               "n_heater_lines": 16,
               "single_cell_il_db": {"amorphous": [0.3878, 3.1026],
                                     "crystalline": [1.9391, 30.0561]},
               "single_cell_contrast_db": [1.5513, 26.9536],
               "array_il_db": {"amorphous": [3.1026, 24.8205],
                               "crystalline": [15.5128, 240.4490]},
               "il_model": "serial_sum(N × single_cell_il)；不含单元间连接波导传播损耗（无锚）",
               "gamma_note": "单元 IL 含 Γ 假设（PM-G2 未闭合）⇒ 区间口径，非单值",
               "contrast_reuse_note": "contrast 与 IL 来自同一 M0 双层调用（避免二次来源）"},
    "scale_tiers": [
        {"bus_x_cells": "1x4", "n_buses": 1, "n_cells_per_bus": 4, "n_cells_total": 4,
         "n_devices": 6, "n_nets": 7, "n_elements": 73, "gds_bytes": 4272,
         "area_um2": 775.93, "width_um": 125.15, "height_um": 6.2,
         "drc_pass": True, "lvs": "ACCEPT", "lvs_violations": 0,
         "independent_ok": True, "expected_pcm": 4, "got_pcm": 4},
        {"bus_x_cells": "1x8", "n_buses": 1, "n_cells_per_bus": 8, "n_cells_total": 8,
         "n_devices": 10, "n_nets": 11, "n_elements": 109, "gds_bytes": 6224,
         "area_um2": 1223.44, "width_um": 197.33, "height_um": 6.2,
         "drc_pass": True, "lvs": "ACCEPT", "lvs_violations": 0,
         "independent_ok": True, "expected_pcm": 8, "got_pcm": 8},
        {"bus_x_cells": "1x16", "n_buses": 1, "n_cells_per_bus": 16,
         "n_cells_total": 16, "n_devices": 18, "n_nets": 19, "n_elements": 181,
         "gds_bytes": 10128, "area_um2": 2118.48, "width_um": 341.72,
         "height_um": 6.2, "drc_pass": True, "lvs": "ACCEPT", "lvs_violations": 0,
         "independent_ok": True, "expected_pcm": 16, "got_pcm": 16},
        {"bus_x_cells": "1x32", "n_buses": 1, "n_cells_per_bus": 32,
         "n_cells_total": 32, "n_devices": 34, "n_nets": 35, "n_elements": 325,
         "gds_bytes": 17936, "area_um2": 3908.54, "width_um": 630.51,
         "height_um": 6.2, "drc_pass": True, "lvs": "ACCEPT", "lvs_violations": 0,
         "independent_ok": True, "expected_pcm": 32, "got_pcm": 32},
        {"bus_x_cells": "4x8", "n_buses": 4, "n_cells_per_bus": 8,
         "n_cells_total": 32, "n_devices": 40, "n_nets": 44, "n_elements": 436,
         "gds_bytes": 24710, "area_um2": 10695.27, "width_um": 197.33,
         "height_um": 54.2, "drc_pass": True, "lvs": "ACCEPT",
         "lvs_violations": 0, "independent_ok": True, "expected_pcm": 32,
         "got_pcm": 32},
    ],
    "upstream": {
        "cell_length": {"l_um": 11.0146, "spacing_frac": 0.0657,
                        "spacing_ok": True, "worst_ber": 4.78e-14,
                        "source": "ACS Photonics 2025 / arXiv 2512.23559"
                                  "（椭偏 · Cody-Lorentz 拟合 · 30nm 膜）"},
        "levels": {"n_levels": 16, "bits_per_cell": 4},
        "thermal": {"material": "GST", "k_iso": 8.0, "l_max_diff_um": 0.8788,
                    "l_max_rc_um": 0.2723, "min_gap_um": 7.0304,
                    "min_gap_um_rc_basis": 2.1787, "literature_l_ref_um": 0.15,
                    "basis": "k_iso × L_max（热扩散口径上界）· k_iso 为设计选择"},
    },
    "signoff_checks": {"drc_all_pass": True, "lvs_accept": True,
                       "pcm_layer_exact": True, "heater_layer_exact": True,
                       "si_layer_at_least_devices": True,
                       "no_hierarchy_refs": True, "single_structure": True},
}

_ARTIFACT_DIRS = (
    os.path.join("examples", "photo_memory"),
    os.path.join("lda", "examples", "photo_memory"),
)
_REPORT_NAME = "lda_pm_m3_report.json"


# ═══════════════════════════ 产出物探测（只读）═══════════════════════════
def _repo_root(repo_root: Optional[str]) -> str:
    if repo_root is not None:
        return repo_root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_report(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """读预生成报告 JSON（**只 json.load + stat**，绝不重算）。

    🔴 **聚合扫描**：源码仓产物在 `examples/photo_memory/`，部署形态可能在
    `lda/examples/photo_memory/` ⇒ 逐个候选目录扫描，取首个命中（同一份数据）。
    读不到 ⇒ 返回 `{}`（调用方回落 `STATIC_SNAPSHOT`，优雅降级）。
    """
    root = _repo_root(repo_root)
    for d in _ARTIFACT_DIRS:
        fp = os.path.join(root, d, _REPORT_NAME)
        if os.path.isfile(fp):
            try:
                with open(fp, encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    data["_source"] = d.replace(os.sep, "/") + "/" + _REPORT_NAME
                    return data
            except (OSError, ValueError):
                return {}
    return {}


def _manifest(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """产出物元信息（文件名 + 字节数）· 只 `stat`。"""
    root = _repo_root(repo_root)
    items: Dict[str, int] = {}
    hits: List[str] = []
    for d in _ARTIFACT_DIRS:
        p = os.path.join(root, d)
        if not os.path.isdir(p):
            continue
        hits.append(d.replace(os.sep, "/"))
        try:
            names = sorted(os.listdir(p))
        except OSError:
            continue
        for nm in names:
            if not nm.startswith("lda_pm_m3") or nm.endswith(".py"):
                continue
            fp = os.path.join(p, nm)
            try:
                if os.path.isfile(fp):
                    items[nm] = int(os.path.getsize(fp))
            except OSError:
                continue
    if not hits:
        return {"available": False, "dirs_scanned": [],
                "root_hint": _ARTIFACT_DIRS[0].replace(os.sep, "/"),
                "count": 0, "items": [],
                "note": "产出物目录不在本部署内（源码仓才含 examples/）"}
    lst = [{"name": k, "bytes": v} for k, v in sorted(items.items())]
    return {"available": True, "dirs_scanned": hits,
            "root_hint": _ARTIFACT_DIRS[0].replace(os.sep, "/"),
            "count": len(lst), "items": lst,
            "note": "只读元信息（文件名 + 字节数，已跨目录去重）；"
                    "在线生成请走源码仓的 examples/photo_memory/build_pm_m3.py"}


# ═══════════════════════════════ 案例卡 ═══════════════════════════════
def case_card(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """组装光子存储阵列案例卡（只读 · 零重计算 · 免登录）。"""
    rep = _load_report(repo_root)
    src = rep.get("_source")
    snap = STATIC_SNAPSHOT
    a8 = rep.get("array_8x1") or snap["array_8x1"]
    a32 = rep.get("array_4x8") or snap["array_4x8"]
    pitch = rep.get("pitch") or snap["pitch"]
    bud = rep.get("budget") or snap["budget"]
    tiers = rep.get("scale_tiers") or snap["scale_tiers"]
    ups = rep.get("upstream") or snap["upstream"]
    checks = rep.get("signoff_checks") or snap["signoff_checks"]

    gate_total = sum(m["gate"] for m in MILESTONES)
    return {
        "endpoint": "/api/pm_demo",
        "case_id": CASE_ID,
        "claim": "用 LDA 从零设计一条非易失光子存储单元 → 阵列（Si 波导 + GST 相变段 "
                 "+ 双侧微加热器 + 电极 pad）：P&R → 路由 → 几何 DRC/LVS → "
                 "**从最终 GDS 字节独立解码复核** → 设计预算，出真 GDSII",
        "verdict": "DESIGN_SIGNOFF",
        "verdict_label": "设计期签核（非流片实测）",
        "identity": {
            "physics": "Si 波导 + GST 相变材料（电辅助写）· 振幅域多电平存储",
            "device": "PCM 单元 = Si 直波导 + GST 覆盖段 + 双侧微加热线 + 4 电极 pad",
            "route_note": "光学 IO 经**引出波导**接光栅耦合器（避免光栅齿区与电极 pad 打架）；"
                          "阵列 = 串行总线（1×N）或多总线（R×C）",
            "layers": PCM_LAYERS,
            "ports": PCM_PORTS,
            "zero_external_eda": True,
        },
        "span": {
            "milestones": len(MILESTONES),
            "gate_checks": gate_total,
            "modules": 4,
            "probe_mutations": sum(MILESTONE_PROBES.values()),
        },
        "milestones": MILESTONES,
        "findings": FINDINGS,
        "gaps": GAPS,
        "gaps_total": len(GAPS),
        "device": {"kind": "PCMCell", "layers": PCM_LAYERS, "ports": PCM_PORTS,
                   "drc_rules": ["min_width", "min_space", "min_pad"]},
        "pitch": pitch,
        "upstream": ups,
        "array": {
            "main": {"kind": a8.get("kind"), "stats": a8.get("stats"),
                     "drc": a8.get("drc"), "lvs": a8.get("lvs")},
            "independent_scan": a8.get("independent_scan"),
            "expected_layers": a8.get("expected"),
            "gds_bytes": (a8.get("gds") or {}).get("bytes"),
            "gds_sha256": (a8.get("gds") or {}).get("sha256"),
            "wide": {"kind": a32.get("kind"), "stats": a32.get("stats"),
                     "drc_all_pass": a32.get("drc_all_pass"),
                     "lvs_verdict": a32.get("lvs_verdict"),
                     "lvs_n_violations": a32.get("lvs_n_violations")},
        },
        "signoff_checks": checks,
        "budget": bud,
        "scale_tiers": tiers,
        "artifacts": _manifest(repo_root),
        "data_source": src or "内置快照（2026-10-04 实测；本部署内无报告 JSON）",
        "ui": {
            "found_in_ui": True,
            "entry": "验证实力（accept）→「光子存储阵列（PM-M3）」卡",
            "related_panels": [],
            "scope_note": "本卡覆盖**单元/阵列版图与签核**；单元物理闭式见 "
                          "`lda_l2/pm_m0…pm_m3`，非 UI 可点面板。",
        },
        "honest_note": PM_HONEST_NOTE,
    }


# ═══════════════════════════════ 自检 ═══════════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检（门禁同源调用）。红线断言 + 零重算断言（不 import 求解器）。"""
    res: Dict[str, bool] = {}
    msgs: List[str] = []

    def chk(name: str, cond: bool) -> None:
        res[name] = bool(cond)
        msgs.append("%s | %s" % ("PASS" if cond else "FAIL", name))

    card = case_card(repo_root="__nonexistent_root__")

    # ① 优雅降级：根不存在 ⇒ 回落内置快照，不抛错
    chk("① 无报告时优雅降级（回落内置快照 + data_source 标注）",
        card["array"]["main"]["stats"]["n_devices"] == 10
        and "内置快照" in card["data_source"]
        and card["artifacts"]["available"] is False)

    # ② 🔴 不伪装实测：verdict 恒 DESIGN_SIGNOFF + 诚实边界关键词齐全
    note = card["honest_note"]
    chk("② 不伪装实测：verdict=DESIGN_SIGNOFF · 边界含「非流片」/「非 PDK」/"
        "「不报能效」",
        card["verdict"] == "DESIGN_SIGNOFF"
        and "非流片、非实测" in note and "非任何 foundry 的 PDK deck" in note
        and "不报 pJ/bit" in note)

    # ③ 🔴 零重计算：本模块不 import 求解器/P&R/EDA（**ast 扫真实 import**）
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    import ast
    banned_mods = {"numpy", "scipy", "lda_l2.pm_m3", "lda_l2.pm_m2",
                   "lda_l2.pm_m1", "lda_l2.pm_m0", "lda_l2.chip_layout_export",
                   "lda_layout.placement", "lda_chain.link_model"}
    bad_imports = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            bad_imports += [a.name for a in node.names if a.name in banned_mods]
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod in banned_mods:
                bad_imports.append(mod)
    chk("③ 零重计算：无 numpy / 求解器 / P&R 模块 import（ast 实证）"
        "· 仅 json/os/typing",
        not bad_imports)

    # ④ 层契约与版图同源：SI/PCM/HEATER = 1/5/6
    chk("④ 版图层契约 SI/PCM/HEATER = 1/5/6 · 端口 6 个",
        PCM_LAYERS == {"SI": 1, "PCM": 5, "HEATER": 6} and len(PCM_PORTS) == 6)

    # ⑤ 独立复核口径自洽：层 5 == 单元数、层 6 == 6× 单元数（快照与报告同规则）
    lay = card["array"]["independent_scan"]["layers"]
    l5 = lay.get("5") if isinstance(lay, dict) else None
    l6 = lay.get("6") if isinstance(lay, dict) else None
    chk("⑤ 独立解码口径：层 5 == 单元数 且 层 6 == 6 × 单元数",
        l5 == 8 and l6 == 48)

    # ⑥ 缺口如实开放（不粉饰）：4 条缺口 · 含光学域 drift 无锚
    chk("⑥ 缺口逐条登记（4 条）· 含「光学域 drift 无锚」与「无 PDK」",
        card["gaps_total"] == 4
        and any("光学域 drift" in g["title"] for g in card["gaps"])
        and any("T1" in g["detail"] for g in card["gaps"]))

    # ⑦ 里程碑计数与 span 一致（算出来的）
    chk("⑦ 里程碑数 == span.milestones 且门禁判据合计 == sum(gate)",
        len(card["milestones"]) == card["span"]["milestones"]
        and card["span"]["gate_checks"] == sum(m["gate"] for m in MILESTONES))

    # ⑧ 规模化口径明标「版图容量」（防误读为已制备器件数）
    chk("⑧ 规模口径明标「版图容量」（诚实边界内）", "版图容量" in card["honest_note"])

    # ⑨ 返回体无非有限 float（防标准 JSON 出口崩 —— v0.9.186 血案同族）
    bad_float = []

    def _scan(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                _scan(v, path + "/" + str(k))
        elif isinstance(o, (list, tuple)):
            for i, v in enumerate(o):
                _scan(v, path + "/[%d]" % i)
        elif isinstance(o, float):
            if o != o or o in (float("inf"), float("-inf")):
                bad_float.append(path)
    _scan(card)
    chk("⑨ 返回体无非有限 float（±inf/NaN 会让前端 JSON.parse 崩）",
        not bad_float)

    ok_all = all(res.values())
    if verbose:
        for m in msgs:
            print("  " + m)
    return ok_all


if __name__ == "__main__":
    print("光子存储案例卡自检：",
          "ALL PASS" if run_selfchecks(verbose=True) else "FAIL")
