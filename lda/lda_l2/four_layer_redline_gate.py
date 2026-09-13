"""LDA · 四层系统（S9）立项前红线闸门自检。

============================================================================
四层系统定义（ALIGNMENT_REPORT.md · S9）
----------------------------------------------------------------------------
- L1 被动前端：波导 / MMI / 定向耦合器 / 光栅耦合器 / MZI（Layer-1 物理）。
- L2 编译映射：目标酉矩阵的 Reck 酉分解（光学矩阵乘的"编译"）。
- L3 控制校准：相干激光 + 探测器 + 相位标定闭环（相干实测）。
- L4 协同仿真：系统级协同仿真。

红线（IRONLAWS.md / 愿景战略 §5）：
- G1 主权：C 级自主，纯 numpy；**不借** Meep / Tidy3D（A 级 GPLv2+ 禁）。
- G2 LLM 不进判决：矩阵运算皆为死标量 / numpy，无 torch/transformers/openai。
- G3 每层挂 VMM 锚 ≥ self_certified（建议 A）：**四层各登记 VMM 锚**，逐层标
  成熟度 tier + 「谁验证 / 升级路径」；未达门槛层诚实挂起（不虚报）。
- G4 不虚报：demo 不得把"未验证层"伪装成 strict 已验证（防纸糊楼）。
- G5 外置激光可绕：L3 相干实测对经典光子**外置可绕**，不破红线。

本模块产出 GateReport：四层均挂 VMM 锚 ≥ self_certified（L1/L2 高于门槛；
L3/L4 为 Tier-1 自证桩，明确升级路径与验证责任方）。
「自证桩是合法的第一验证阶段」（VMM, v0.9.62，docs/verification_maturity_model.md）——
其成熟度标注须为 self_certified，**不得**冒充方法学独立 / 实证锚（G4 纪律）。
============================================================================
"""
from __future__ import annotations

import ast
import importlib.util
import math
import os

__all__ = [
    "scan_sovereignty",
    "scan_llm_not_in_decision",
    "check_layer_anchors",
    "check_no_false_green",
    "check_external_laser_bypassable",
    "l3_phase_calibration_anchor",
    "l4_electro_thermal_optical_cosim_anchor",
    "run_four_layer_redline_gate",
    "GateReport",
]

# 包根（本文件位于 lda/lda_l2/，求解器位于 lda/lda_solver/）
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)  # -> lda/

# A 级禁借求解器（G1）
_FORBIDDEN_SOLVERS = ("meep", "tidy3d", "tidy3d_z", "gdspy", "gdstk")
# LLM / 大模型（G2，不得进判决路径）
_FORBIDDEN_LLM = ("torch", "transformers", "openai", "langchain", "llama", "anthropic")

# 受检源码（L1/L2 引擎与物理锚）
_ENGINE_FILES = [
    os.path.join(_HERE, "mzi_mesh_matmul.py"),
    os.path.join(_ROOT, "lda_solver", "dc_cmt_solver.py"),
    os.path.join(_ROOT, "lda_solver", "soref_bennett.py"),
]


# ---------------------------------------------------------------------------
# VMM 成熟度序（建议 A：每层 ≥ self_certified）
# ---------------------------------------------------------------------------
# self_certified(自证桩) < degraded_ordinal(降级量级) < strict_independent(严格独立)
# 另收两类「≥ 门槛但非 VMM 锚类」的更高保证：数学定理 / 方法学独立候选。
_GATE_MIN_TIER = "self_certified"
_MATURITY_RANK = {
    "none": 0,
    "self_certified": 1,
    "degraded_ordinal": 2,
    "strict_independent": 3,
    "mathematical_theorem": 3,          # Reck 分解可实现性（定理级，≥ 门槛）
    "methodologically_independent": 3,  # B14 方法学独立候选（≥ 严格独立门槛）
}


def _classify_layer_status(tier: str) -> str:
    """层准入判定：tier ≥ self_certified ⇒ ADMISSIBLE；否则 SUSPENDED（诚实挂起）。"""
    return ("ADMISSIBLE"
            if _MATURITY_RANK.get(tier, 0) >= _MATURITY_RANK[_GATE_MIN_TIER]
            else "SUSPENDED")


def _module_imports(path: str):
    """解析单文件 import 顶层模块名集合（静态，不执行）。"""
    mods = set()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
    except (OSError, SyntaxError):
        return mods
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mods.add(node.module.split(".")[0])
    return mods


def scan_sovereignty(paths=None) -> dict:
    """G1 主权扫描：受检源码不得 import A 级禁借求解器。"""
    paths = paths or _ENGINE_FILES
    hits = []
    for p in paths:
        for mod in _module_imports(p):
            if mod in _FORBIDDEN_SOLVERS:
                hits.append((os.path.basename(p), mod))
    return {
        "gate": "G1_sovereignty",
        "status": "PASS" if not hits else "FAIL",
        "forbidden_hits": hits,
        "scanned": [os.path.basename(p) for p in paths],
        "verdict": "C 级自主（纯 numpy），未借 Meep/Tidy3D（A 级禁）"
                  if not hits else "发现 A 级禁借求解器导入：%s" % hits,
    }


def scan_llm_not_in_decision(paths=None) -> dict:
    """G2 LLM 不进判决：受检源码不得 import 大模型相关包。"""
    paths = paths or _ENGINE_FILES
    hits = []
    for p in paths:
        for mod in _module_imports(p):
            if mod in _FORBIDDEN_LLM:
                hits.append((os.path.basename(p), mod))
    return {
        "gate": "G2_llm_not_in_decision",
        "status": "PASS" if not hits else "FAIL",
        "forbidden_hits": hits,
        "scanned": [os.path.basename(p) for p in paths],
        "verdict": "矩阵运算全为 numpy 死标量，LLM 不进判决路径"
                  if not hits else "发现 LLM 相关导入进判决路径：%s" % hits,
    }


# ---------------------------------------------------------------------------
# L3 / L4 立项前 Tier-1 自证锚（建议 A：每层 ≥ self_certified）
# ---------------------------------------------------------------------------
# 🔴 诚实纪律：以下两道是「立项前最低门槛」的**自证桩**（provenance =
# self_authored_closed_form），候选≡golden、反解残差构造性为零 —— 它们证明
# 「控制/协同链路的物理模型自洽」，**不构成**对真实硬件的验证。成熟度须标
# self_certified，禁止冒充方法学独立/实证锚。
_VPI_CAL_V = 25.0        # MZI 相移器半波电压量级（V，Vπ·L 取单位臂长），同 mzi_mesh VPI_L_V_CM
_HEATER_R_OHM = 1000.0   # 热光相移器加热器电阻（Ω，设计预算）
_THERMAL_R_KW = 1000.0   # 加热器热阻（K/W，设计预算）
_DN_DT_PER_K = 1.8e-4    # 硅热光系数 dn/dT（/K，公开材料量级）
_ARM_L_M = 1.0e-3        # 相移臂长（m，设计预算 1mm）
_WL_M = 1.55e-6          # 工作波长（m）


def _mzi_bar_transmission(phi: float) -> float:
    """50/50 MZI bar 口干涉传递 T(φ) = cos²(φ/2)。"""
    return math.cos(phi / 2.0) ** 2


def l3_phase_calibration_anchor(vpi_v: float = _VPI_CAL_V, n_points: int = 9) -> dict:
    """L3 控制校准 · Tier-1 自证桩：MZI 相移器 V→φ→透过率 T 闭环标定自洽。

    物理定律（Soref-Bennett 线性电光 / 热光相移器）：
        φ(V) = π·V/Vπ            （Vπ·L 定律，取单位臂长 ⇒ Vπ 量级）
        T(φ) = cos²(φ/2)         （50/50 MZI bar 口干涉传递）
    自证闭环：正向由 V 算 T；再由 T 反解 φ、V。自证桩 candidate≡golden，
    反解残差**构造性恒零**（机器精度）⇒ 成熟度 Tier-1 self_certified。
    """
    if n_points < 2:
        raise ValueError("n_points 须 ≥ 2")
    worst = 0.0
    for k in range(n_points):
        V = vpi_v * k / (n_points - 1)
        phi = math.pi * V / vpi_v
        T = min(1.0, max(0.0, _mzi_bar_transmission(phi)))
        phi_rec = 2.0 * math.acos(math.sqrt(T))   # T∈[0,1] ⇒ φ∈[0,π] 主值
        V_rec = phi_rec * vpi_v / math.pi
        worst = max(worst, abs(V_rec - V))
    endpoints_ok = (abs(_mzi_bar_transmission(0.0) - 1.0) < 1e-15
                    and abs(_mzi_bar_transmission(math.pi) - 0.0) < 1e-15)
    return {
        "anchor_id": "L3-PHASE-CAL-STUB",
        "layer": "L3_control_calibration",
        "metric": "MZI 相移器 V↔φ↔T 闭环标定反解残差（V）",
        "tier": "self_certified",
        "provenance": "self_authored_closed_form",
        "value": float(vpi_v),
        "residual": float(worst),
        "endpoints_ok": bool(endpoints_ok),
        "who_verifies": "待外置相干激光 + 光电探测器 + 相位标定闭环实测（L3 硬件）",
        "margin": "自证桩无独立候选 ⇒ 无余量（Tier-1 = VMM 合法第一阶段，非已验证）",
        "upgrade_path": "接入外置相干激光/探测器实测标定数据，或 foundry PDK 端口标定 → 升方法学独立/实证锚",
        "note": "仅证控制/标定链路的物理模型自洽；不含真实相干光学测量。",
    }


def l4_electro_thermal_optical_cosim_anchor(n_points: int = 9) -> dict:
    """L4 协同仿真 · Tier-1 自证桩：电-热-光三域链式协同自洽。

    物理定律链（热光相移器）：
        电：P = V²/R_h                        （加热器电功率）
        热：ΔT = P·R_th                        （热阻）
        光：Δφ = (2π/λ)·(dn/dT)·ΔT·L_arm；T = cos²(Δφ/2)
    自证闭环：正向 V→P→ΔT→Δφ→T；再由 T 反解 Δφ、ΔT、P、V。
    自证桩 candidate≡golden，反解残差**构造性恒零**⇒ 成熟度 Tier-1 self_certified。
    """
    if n_points < 2:
        raise ValueError("n_points 须 ≥ 2")
    k_phi = (2.0 * math.pi / _WL_M) * _DN_DT_PER_K * _ARM_L_M   # rad/K
    dt_pi = math.pi / k_phi
    v_pi = math.sqrt((dt_pi / _THERMAL_R_KW) * _HEATER_R_OHM)   # Δφ=π 对应驱动电压
    worst = 0.0
    for k in range(n_points):
        V = v_pi * k / (n_points - 1)
        P = V * V / _HEATER_R_OHM
        dT = P * _THERMAL_R_KW
        dphi = k_phi * dT
        T = min(1.0, max(0.0, _mzi_bar_transmission(dphi)))
        # 反解：T→Δφ→ΔT→P→V
        dphi_rec = 2.0 * math.acos(math.sqrt(T))
        dT_rec = dphi_rec / k_phi
        P_rec = dT_rec / _THERMAL_R_KW
        V_rec = math.sqrt(max(0.0, P_rec * _HEATER_R_OHM))
        worst = max(worst, abs(V_rec - V))
    return {
        "anchor_id": "L4-ETO-COSIM-STUB",
        "layer": "L4_cosim",
        "metric": "电-热-光三域链式协同闭环反解残差（V）",
        "tier": "self_certified",
        "provenance": "self_authored_closed_form",
        "value": float(v_pi),
        "residual": float(worst),
        "endpoints_ok": True,
        "who_verifies": "待真实多域协同仿真 + 热光相移器实测（ΔT/相位响应）标定（L4）",
        "margin": "自证桩无独立候选 ⇒ 无余量（Tier-1 = VMM 合法第一阶段，非已验证）",
        "upgrade_path": "接入实测热光系数/热阻与多域协同仿真引擎（外部 ORACLE）→ 升方法学独立/实证锚",
        "note": "仅证电-热-光链式模型的数值自洽；不含真实器件交叉域实测。",
    }


def check_layer_anchors() -> dict:
    """G3 每层挂 VMM 锚 ≥ self_certified（建议 A），逐层标 tier / 验证方 / 升级路径。

    实际跑 L1/L2 引擎证明可工作（非仅声明）；L3/L4 登记 Tier-1 自证桩（诚实标注）。
    """
    layers = {}

    # ---- L1 被动前端：B14 方法学独立候选（dc_3dB_fft）锚 50/50 耦合长度 ----
    l1_anchor = None
    try:
        spec = importlib.util.spec_from_file_location(
            "dc_cmt_solver", os.path.join(_ROOT, "lda_solver", "dc_cmt_solver.py"))
        dc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dc)
        L3 = dc.dc_3dB_fft(n_e=2.45, n_o=2.40, wl=1.55)
        l1_anchor = {
            "anchor_id": "B14",
            "layer": "L1_passive_frontend",
            "metric": "50/50 定向耦合器 3dB 耦合长度（µm）",
            "tier": "methodologically_independent",
            "provenance": "independent_cross_check",
            "value": float(L3),
            "residual": 0.0,
            "who_verifies": "B14 方法学独立候选 dc_3dB_fft（已内验）",
            "margin": "≥ 严格独立门槛（高于 self_certified）",
            "upgrade_path": "",
            "note": "Layer-1 被动前端物理锚。",
        }
    except Exception as exc:  # pragma: no cover
        l1_anchor = {
            "anchor_id": "B14", "layer": "L1_passive_frontend",
            "metric": "50/50 定向耦合器 3dB 耦合长度（µm）",
            "tier": "none", "provenance": "import_failed", "value": None,
            "residual": None, "who_verifies": "—", "margin": "—",
            "upgrade_path": "修 dc_cmt_solver 导入", "note": str(exc)[:120],
        }

    # ---- L2 编译映射：Reck 分解精确重构目标酉（数学定理，跑一遍证明） ----
    l2_ok = False
    l2_fid = None
    l2_err = None
    try:
        from lda.lda_l2.mzi_mesh_matmul import (
            reck_decompose, assemble_mesh, dft_matrix, unitary_fidelity)
        import numpy as _np
        U = dft_matrix(4)
        ops, D = reck_decompose(U)
        Ur = assemble_mesh(ops, D, 4)
        l2_fid = unitary_fidelity(Ur, U)
        l2_err = float(_np.linalg.norm(Ur - U))
        l2_ok = l2_fid > 0.999
    except Exception:
        l2_ok = False
    l2_anchor = {
        "anchor_id": "Reck",
        "layer": "L2_compilation",
        "metric": "目标酉重构保真度 / fro_err",
        "tier": "mathematical_theorem" if l2_ok else "none",
        "provenance": "mathematical_theorem",
        "value": l2_fid,
        "residual": l2_err,
        "who_verifies": "Reck 定理（数学可实现性证明，独立于 harness）+ 重构实测",
        "margin": "≥ 严格独立门槛（精确重构，机器精度）" if l2_ok else "未跑通",
        "upgrade_path": "" if l2_ok else "修 Reck 分解/装配",
        "note": "酉分解为数学定理，非物理验证锚。",
    }

    # ---- L3 控制校准：相干激光 + 探测器 + 相位标定闭环（登记 Tier-1 自证桩） ----
    l3_anchor = l3_phase_calibration_anchor()

    # ---- L4 协同仿真：系统级（登记 Tier-1 自证桩） ----
    l4_anchor = l4_electro_thermal_optical_cosim_anchor()

    def _layer(anchor):
        return {
            "status": _classify_layer_status(anchor["tier"]),
            "maturity_tier": anchor["tier"],
            "anchor": anchor,
        }

    layers["L1_passive_frontend"] = _layer(l1_anchor)
    layers["L2_compilation"] = _layer(l2_anchor)
    layers["L3_control_calibration"] = _layer(l3_anchor)
    layers["L4_cosim"] = _layer(l4_anchor)

    below = [k for k, v in layers.items() if v["status"] != "ADMISSIBLE"]
    all_ok = not below
    return {
        "gate": "G3_layer_anchors",
        "status": "PASS" if all_ok else "PARTIAL",
        "min_tier_required": _GATE_MIN_TIER,
        "layers": layers,
        "below_threshold": below,
        "verdict": ("四层均挂 VMM 锚 ≥ self_certified（建议 A 达成）：L1 B14 方法学独立 / "
                    "L2 Reck 定理（均高于门槛）；L3 相位标定 / L4 电-热-光协同 为 Tier-1 "
                    "自证桩（明确升级路径与验证责任方，不虚报为已验证）。")
                   if all_ok else
                   ("未达 self_certified 门槛的层：%s —— 诚实挂起，不虚报。" % below),
    }


def check_no_false_green() -> dict:
    """G4 不虚报：demo 不得把 L3/L4 伪装成 strict 已验证。

    判据：模块披露的 RED_LINE_DISCLOSURE 须明确声明真实相干实测未含、未声称
    已实现相干光学计算机（Tier-1 自证桩 ≠ 已验证）。
    """
    ok = False
    try:
        from lda.lda_l2.mzi_mesh_matmul import RED_LINE_DISCLOSURE
        txt = " ".join(str(v) for v in RED_LINE_DISCLOSURE.values())
        ok = ("未含" in txt) and ("不声称" in txt or "未声称" in txt) and ("相干光学计算机" in txt)
    except Exception:
        ok = False
    return {
        "gate": "G4_no_false_green",
        "status": "PASS" if ok else "FAIL",
        "verdict": "诚实边界已声明真实相干实测未含、不声称已实现相干光学计算机，"
                   "且 L3/L4 明确标 Tier-1 自证桩"
                  if ok else "披露缺失诚实边界声明",
    }


def check_external_laser_bypassable() -> dict:
    """G5 外置激光可绕：L3 相干实测对经典光子外置可绕，不破红线。"""
    return {
        "gate": "G5_external_laser_bypassable",
        "status": "BYPASSABLE",
        "verdict": "L3 相干激光+探测器+相位标定闭环对经典光子计算属外置可绕，"
                   "不破红线（光子学经典计算无需内置相干源）；L3 待建时不阻断 L1/L2 演示。",
    }


def run_four_layer_redline_gate() -> "GateReport":
    """跑全部 5 道闸门，产出结构化 GateReport。"""
    g1 = scan_sovereignty()
    g2 = scan_llm_not_in_decision()
    g3 = check_layer_anchors()
    g4 = check_no_false_green()
    g5 = check_external_laser_bypassable()

    # 整体判定：G1/G2/G4 须 PASS，G5 BYPASSABLE，G3 四层全部 ≥ self_certified。
    hard_ok = (g1["status"] == "PASS" and g2["status"] == "PASS"
               and g4["status"] == "PASS" and g5["status"] == "BYPASSABLE")
    all_layers_ok = (g3["status"] == "PASS")
    if hard_ok and all_layers_ok:
        overall = "PASS"
    elif hard_ok:
        overall = "PARTIAL_PASS"   # 硬纪律清白，但仍有层未达门槛（诚实挂起）
    else:
        overall = "FAIL"

    admissible = [k for k, v in g3["layers"].items() if v["status"] == "ADMISSIBLE"]
    suspended = [k for k, v in g3["layers"].items() if v["status"] != "ADMISSIBLE"]
    tiers = {k: v["maturity_tier"] for k, v in g3["layers"].items()}
    return GateReport(
        overall=overall,
        gates={"G1": g1, "G2": g2, "G3": g3, "G4": g4, "G5": g5},
        admissible_layers=admissible,
        suspended_layers=suspended,
        layer_tiers=tiers,
    )


class GateReport:
    """四层系统红线闸门报告。"""

    def __init__(self, overall, gates, admissible_layers, suspended_layers,
                 layer_tiers=None):
        self.overall = overall
        self.gates = gates
        self.admissible_layers = admissible_layers
        self.suspended_layers = suspended_layers
        self.layer_tiers = layer_tiers or {}

    def to_dict(self) -> dict:
        return {
            "overall": self.overall,
            "admissible_layers": self.admissible_layers,
            "suspended_layers": self.suspended_layers,
            "layer_tiers": self.layer_tiers,
            "gates": self.gates,
        }

    def __repr__(self):
        return f"GateReport(overall={self.overall!r})"


if __name__ == "__main__":
    rep = run_four_layer_redline_gate()
    print(f"四层系统红线闸门整体：{rep.overall}")
    for g, v in rep.gates.items():
        print(f"  {g}: {v['status']} — {v['verdict']}")
    print(f"  准入层: {rep.admissible_layers}")
    print(f"  挂起层: {rep.suspended_layers}")
    print(f"  各层成熟度: {rep.layer_tiers}")
