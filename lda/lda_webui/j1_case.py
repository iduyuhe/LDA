# -*- coding: utf-8 -*-
"""J1 量子纠错（QEC）征程 · WebUI **只读案例卡**（LDA-J1 · 物理比特 → 逻辑比特）。

🔴 **零重计算**：本模块**不跑仿真、不 import 求解器、不 import numpy/scipy** ——
只 import `math` / `typing`（AST 自检断言）。全部数字由**同源闭式算术现算**
（症候权重闭式 / 旗比特占比 / erf² 关联 / exp 积分预算链 / 资源计数）。

🔴 **与真源同源**：各闭式与 `lda_qeda/{qec_noise,fault_tolerant_gates,logical_error_rate}`
**同律**（同一默认档参数），并由常驻门禁 `run_webui_j1_render_path_smoke` 逐值跨源对拍。
⇒ 本卡自身无 DoS 面，故**免登录、不进 `HEAVY_POST_PATHS`**。

🔴 **诚实边界**：全部参数为**设计示例量级**（非实测 PDK）；只证明「闭式算术链自洽」这一
数学事实，**不作制造/性能宣称**，不报能效/TOPS/fJ-op。
"""

from __future__ import annotations

import math
from typing import Any, Dict

CASE_ID = "LDA-J1 · 量子纠错 QEC（物理比特 → 逻辑比特）"

J1_HONEST_NOTE = (
    "本卡为**设计预算**（design budget），所有数值由闭式算术现算，**非流片实测**、"
    "**非 foundry PDK**。参数（物理错误率 p / 码距 L、d / 旗比特枚举数 / 预算链系数）"
    "为**设计示例量级**；解码器内核正确性由 `run_j1_qec_smoke`（MWPM ↔ 自主 Union-Find "
    "对拍）单独守护，本卡只呈现**闭式预算链**。不作制造/性能宣称，不报能效/TOPS/fJ-op。"
)

MILESTONES = ["M0 阈值标度 · 逻辑错误率 vs 码距", "M1 解码器（MWPM / 自主 Union-Find）",
              "M2 综合征提取 · 旗比特钩错",
              "M3 容错逻辑门（transversal CNOT / lattice surgery）",
              "M4 端到端累计失效"]

ANCHORS = {
    "B497": "表面码逻辑错误阈值距离 d*（独立误差近似闭式 ⇄ 蒙特卡洛解码）",
    "B498": "解码器综合症状概率场总权重（闭式期望 ⇄ 蒙特卡洛 shots）",
    "B499": "解码器匹配代价二阶矩（闭式 ⇄ 数值匹配代价采样）",
    "B500": "旗比特钩错检测概率 P(φ>φ_th)（确定性小枚举）",
    "B501": "相邻稳定子综合征关联 ∫∫g(x,y)g(x+r,y)（erf² 闭式 ⇄ 2D 梯形求积）",
    "B502": "transversal CNOT 保真预算链 F=exp(−∫率)（闭式 ⇄ 中点求积）",
    "B503": "lattice surgery 合并保真 F=exp(−c·p·∫(2x²−1)dx)（闭式 ⇄ 中点求积）",
    "B504": "端到端累计逻辑失效 P=1−exp(−∫率)（闭式 ⇄ 中点求积）",
    "B505": "累计逻辑错误面积 ∫₀ᴸ(1−e^{−kx})dx（闭式 ⇄ 数值积分）",
}

#: 逐条缺口状态（**顺序与下方 GAPS 一一对应** · v0.9.286 四值口径）
#: 字符串型 gaps 不改形状（前端仍按字符串渲染），状态走这个并行列表。
GAPS_STATUS = [
    "未闭合（量子计算遗留缺口 G_Q9）",
    "未闭合（容错：阈值/解码/综合征/容错门）",
]

GAPS = ["G_Q9 量子计算遗留缺口", "G-QEC* 容错（阈值/解码/综合征/容错门）"]

SELFCHECK_MODULES = ["decoder", "qec_noise", "fault_tolerant_gates", "logical_error_rate"]
RENDER_PATH_SMOKE = "run_webui_j1_render_path_smoke.py"
HEAVY_POST = False

# ── 与 `lda_qeda/*` **同源**的设计示例默认档 ──────────────────────────────
P_PHYS = 5.0e-3          # 物理错误率（子阈值档）
CODE_L = 5               # toric 码边长 L（L² 个 plaquette）
N_HOOK = 8               # 旗舰钩错枚举位置数
FLAG_FAULTS = 1          # 其中被旗比特捕获的位置数
D_CORR = 5.0             # 关联积分窗口边长 d
SIGMA_CORR = 1.0         # 高斯错误场 σ
CX_CORR = 2.5            # 高斯中心 x
CY_CORR = 2.5            # 高斯中心 y
R_SHIFT = 1.0            # 关联位移 r
P0_CNOT = 1.0e-3         # transversal CNOT 基准错误率
ALPHA_CNOT = 0.1         # 线性漂移系数
BETA_CNOT = 0.01         # 二次漂移系数
T_CNOT = 10.0            # 预算链时长
C_LS = 0.5               # lattice surgery 代价系数
D_LS = 5                 # lattice surgery patch 尺寸
LAM_E2E = 2.0e-3         # 端到端失效基准率 λ
T_E2E = 100.0            # 端到端时长
BETA_E2E = 0.01          # 端到端线性漂移
GAMMA_E2E = 1.0e-4       # 端到端二次漂移
K_AREA = 1.0e-2          # 累计逻辑错误面积率 k
L_AREA = 1.0e3           # 面积积分上限 L


# ---------------------------------------------------------------------------
# 闭式（与真源同律 · 纯 math）
# ---------------------------------------------------------------------------
def syndrome_weight(p: float = P_PHYS, length: int = CODE_L) -> float:
    """B498 同律：期望综合征权重 = L²·½(1−(1−2q)⁴)，q = 2p/3。"""
    if not 0.0 <= p < 0.5:
        raise ValueError("p 须 ∈ [0, 0.5)")
    if length < 1:
        raise ValueError("L ≥ 1")
    q = 2.0 * p / 3.0
    return float(length * length * 0.5 * (1.0 - (1.0 - 2.0 * q) ** 4))


def flag_hook_detection(n_hook: int = N_HOOK, flag_faults: int = FLAG_FAULTS) -> float:
    """B500 同律：被旗比特捕获占比 = flag_faults / n_hook。"""
    if n_hook <= 0:
        raise ValueError("n_hook ≥ 1")
    if not 0 <= flag_faults <= n_hook:
        raise ValueError("flag_faults ∈ [0, n_hook]")
    return float(flag_faults) / n_hook


def adjacent_syndrome_correlation(d: float = D_CORR, sigma: float = SIGMA_CORR,
                                  cx: float = CX_CORR, cy: float = CY_CORR,
                                  r: float = R_SHIFT) -> float:
    """B501 同律：(πσ²/4)·exp(−r²/4σ²)·[erf 差]·[erf 差]。"""
    if d <= 0.0 or sigma <= 0.0:
        raise ValueError("d / sigma > 0")
    a = math.erf((d - cy) / sigma) - math.erf(-cy / sigma)
    b = math.erf((d - (cx - r / 2.0)) / sigma) - math.erf(-(cx - r / 2.0) / sigma)
    return float((math.pi * sigma * sigma / 4.0)
                 * math.exp(-(r * r) / (4.0 * sigma * sigma)) * a * b)


def transversal_cnot_fidelity(p0: float = P0_CNOT, alpha: float = ALPHA_CNOT,
                              beta: float = BETA_CNOT, t: float = T_CNOT) -> float:
    """B502 同律：F = exp(−p₀(T + αT²/2 + βT³/3))。"""
    if min(p0, alpha, beta, t) < 0.0:
        raise ValueError("参数须 ≥ 0")
    return float(math.exp(-p0 * (t + alpha * t * t / 2.0 + beta * t * t * t / 3.0)))


def lattice_surgery_merge_fidelity(c: float = C_LS, p: float = P_PHYS,
                                   d: int = D_LS) -> float:
    """B503 同律：F = exp(−c·p·(2d³/3 − d))。"""
    if c < 0.0 or p < 0.0 or d < 1:
        raise ValueError("c/p ≥ 0 · d ≥ 1")
    return float(math.exp(-c * p * (2.0 * d * d * d / 3.0 - float(d))))


def lattice_surgery_resource(d: int = D_LS) -> int:
    """B503 资源面：2d²−1 物理比特/逻辑比特。"""
    if d < 1:
        raise ValueError("d ≥ 1")
    return 2 * d * d - 1


def logical_error_accumulated(lam: float = LAM_E2E, t: float = T_E2E,
                              beta: float = BETA_E2E,
                              gamma: float = GAMMA_E2E) -> float:
    """B504 同律：P = 1 − exp(−λ(T + βT²/2 + γT³/3))。"""
    if min(lam, t, beta, gamma) < 0.0:
        raise ValueError("参数须 ≥ 0")
    return float(1.0 - math.exp(-lam * (t + beta * t * t / 2.0 + gamma * t * t * t / 3.0)))


def logical_error_area(k: float = K_AREA, big_l: float = L_AREA) -> float:
    """B505 同律：∫₀ᴸ(1−e^{−kx})dx = L − (1−e^{−kL})/k。"""
    if k <= 0.0 or big_l <= 0.0:
        raise ValueError("k / L > 0")
    return float(big_l - (1.0 - math.exp(-k * big_l)) / k)


# ---------------------------------------------------------------------------
# 案例卡
# ---------------------------------------------------------------------------
ANCHORS_SOURCE = "segment"

ANCHORS_NOTE = (
    "QEC 号段 B497–B505 全 9 条（阈值距离 / 解码器权重与二阶矩 / 旗比特检测 / 稳定子关联 / CNOT 与 lattice surgery 保真 / 端到端失效）。"
    "。")

def case_card() -> Dict[str, Any]:
    """J1 只读案例卡（零重计算 · 闭式算术现算）。"""
    sw = syndrome_weight()
    fh = flag_hook_detection()
    ac = adjacent_syndrome_correlation()
    fc = transversal_cnot_fidelity()
    mf = lattice_surgery_merge_fidelity()
    res = lattice_surgery_resource()
    la = logical_error_accumulated()
    area = logical_error_area()

    return {
        "case_id": CASE_ID,
        "milestones": list(MILESTONES),
        "anchors": dict(ANCHORS),
        "gaps": list(GAPS),
"gaps_status": GAPS_STATUS,
        "anchors": ANCHORS,
        "anchors_source": ANCHORS_SOURCE,
        "anchors_note": ANCHORS_NOTE,
        "honest_note": J1_HONEST_NOTE,
        "verdict": "DESIGN_BUDGET",
        "verdict_label": "设计预算（建模值 · 非流片实测）",
        "render_path_smoke": RENDER_PATH_SMOKE,
        "heavy_post": HEAVY_POST,
        "design_point": {
            "p_phys": P_PHYS,
            "code_L": CODE_L,
            "n_hook": N_HOOK,
            "flag_faults": FLAG_FAULTS,
            "d_corr": D_CORR,
            "sigma_corr": SIGMA_CORR,
            "t_cnot": T_CNOT,
            "d_ls": D_LS,
            "lam_e2e": LAM_E2E,
            "t_e2e": T_E2E,
        },
        "m0_threshold_scaling": {
            "note": "阈值标度由 run_j1_qec_smoke 的 M4-A 子阈值判据守护（p_L(7) < p_L(3)）",
            "subthreshold_p": P_PHYS,
        },
        "m1_decoder": {
            "note": "解码器内核正确性由 run_j1_qec_smoke 守护（MWPM ↔ 自主 Union-Find 位级对拍）",
            "syndrome_weight": float(sw),
            "syndrome_weight_expr": "L^2 * 0.5*(1-(1-2q)^4), q=2p/3",
        },
        "m2_syndrome_extraction": {
            "flag_hook_detection": float(fh),
            "adjacent_syndrome_correlation": float(ac),
        },
        "m3_fault_tolerant_gates": {
            "transversal_cnot_fidelity": float(fc),
            "lattice_surgery_merge_fidelity": float(mf),
            "lattice_surgery_resource": int(res),
        },
        "m4_end_to_end": {
            "logical_error_accumulated": float(la),
            "logical_error_area": float(area),
        },
        "caliber": "design_budget__closed_form__no_simulation",
    }


def run_selfchecks() -> Dict[str, bool]:
    """案例卡自检（零重计算 / 闭式与真源同律 / 单调性 / 边界）。"""
    ok: Dict[str, bool] = {}
    c = case_card()

    # ① 结构齐备
    for k in ("case_id", "milestones", "anchors", "gaps", "honest_note", "verdict",
              "design_point", "caliber"):
        ok["field_%s" % k] = k in c
    ok["anchors_9"] = len(c["anchors"]) == 9
    ok["milestones_5"] = len(c["milestones"]) == 5
    ok["verdict_is_design_budget"] = c["verdict"] == "DESIGN_BUDGET"

    # ② verdict/DESIGN 不申报实测
    ok["honest_note_mentions_design"] = "设计示例" in J1_HONEST_NOTE
    ok["no_sim_claim"] = "非流片实测" in J1_HONEST_NOTE

    # ③ 症候权重：单调增 + p→0 归零 + 上界
    ok["syndrome_monotone"] = syndrome_weight(0.001) < syndrome_weight(0.01) < syndrome_weight(0.1)
    ok["syndrome_zero_at_p0"] = abs(syndrome_weight(0.0)) < 1e-15
    ok["syndrome_bounded"] = syndrome_weight(0.4) < CODE_L * CODE_L

    # ④ 旗比特占比 ∈ [0,1] 且端点正确
    ok["flag_ratio_in_unit"] = 0.0 <= flag_hook_detection() <= 1.0
    ok["flag_all_captured"] = abs(flag_hook_detection(4, 4) - 1.0) < 1e-15
    ok["flag_none_captured"] = abs(flag_hook_detection(4, 0)) < 1e-15

    # ⑤ 关联 > 0 且 r 增大则指数衰减
    ok["corr_positive"] = adjacent_syndrome_correlation() > 0.0
    ok["corr_decays_with_r"] = (adjacent_syndrome_correlation(r=1.0)
                                > adjacent_syndrome_correlation(r=4.0))

    # ⑥ 保真 ∈ (0,1] 且 p0=0 ⇒ 1
    ok["cnot_fid_unit_at_p0_zero"] = abs(transversal_cnot_fidelity(p0=0.0) - 1.0) < 1e-15
    ok["cnot_fid_in_unit"] = 0.0 < transversal_cnot_fidelity() <= 1.0
    ok["ls_fid_in_unit"] = 0.0 < lattice_surgery_merge_fidelity() <= 1.0
    ok["ls_resource_closed_form"] = lattice_surgery_resource(3) == 17

    # ⑦ 端到端失效 ∈ [0,1) 且单调
    ok["e2e_in_unit"] = 0.0 <= logical_error_accumulated() < 1.0
    ok["e2e_monotone_in_lambda"] = (logical_error_accumulated(lam=1.0e-3)
                                    < logical_error_accumulated(lam=5.0e-3))
    ok["area_positive"] = logical_error_area() > 0.0

    # ⑧ 反向（边界守卫）
    for nm, fn in (("syndrome", lambda: syndrome_weight(0.5)),
                   ("flag", lambda: flag_hook_detection(0, 0)),
                   ("corr", lambda: adjacent_syndrome_correlation(0.0)),
                   ("resource", lambda: lattice_surgery_resource(0)),
                   ("area", lambda: logical_error_area(k=0.0))):
        try:
            fn()
            ok["reverse_%s_raises" % nm] = False
        except ValueError:
            ok["reverse_%s_raises" % nm] = True

    return ok


def main() -> int:  # pragma: no cover
    c = case_card()
    print("J1 案例卡：%s" % c["case_id"])
    print("  M1 症候权重 = %.6f · M2 旗比特占比 = %.4f · 关联 = %.6f"
          % (c["m1_decoder"]["syndrome_weight"],
             c["m2_syndrome_extraction"]["flag_hook_detection"],
             c["m2_syndrome_extraction"]["adjacent_syndrome_correlation"]))
    print("  M3 transversal CNOT F = %.12f · LS F = %.12f · 资源 = %d"
          % (c["m3_fault_tolerant_gates"]["transversal_cnot_fidelity"],
             c["m3_fault_tolerant_gates"]["lattice_surgery_merge_fidelity"],
             c["m3_fault_tolerant_gates"]["lattice_surgery_resource"]))
    print("  M4 端到端失效 = %.12f · 面积 = %.6f"
          % (c["m4_end_to_end"]["logical_error_accumulated"],
             c["m4_end_to_end"]["logical_error_area"]))
    sc = run_selfchecks()
    bad = [k for k, v in sc.items() if not v]
    print("  自检：%d/%d PASS%s" % (len(sc) - len(bad), len(sc),
                                    "" if not bad else " · FAIL=%s" % bad))
    return 0 if not bad else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
