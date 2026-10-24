"""J4 量子传感系统集成征程（Layer 4 · M0–M4）案例卡（WebUI 只读端点数据源）。

═══════════════════════════════════════════════════════════════════════════
定位
═══════════════════════════════════════════════════════════════════════════
J4 征程「吃狗粮」LDA-J4（v0.9.237… · M0–M4 收官）的**只读案例**：把
「**器件 → 系统**」这一 QS 器件征程（M0–M9，B473–B496）刻意留下的缺口，
连同四档成果（多参数解耦 / 芯片级 OPM 微型化 / 单芯片集成 / 封装热负载）
收进一张卡。

🔴 **与 `/api/qsensor_demo`（QS 器件级）分工不同**：
  · `qsensor_demo` = **器件级**（NV/SQUID/OPM 三腿灵敏度）；
  · 本卡 = **系统级**（多参数解耦可用性 / 微型化代价 / 集成隔离度 / 热负载预算）
    —— 二者互补，非重复。

🔴 **零重计算**：本模块**不跑仿真、不 import 求解器、不 import numpy/scipy** ——
全部数字由**闭式算术现算**（Cramer 行列式展开 / WF 有理积分 / dB 比值 / 弛豫求和），
与 `lda_l2/qs_j4_*` 各模块的现算值**逐值可对拍**（`run_webui_j4_render_path_smoke` 常驻）。
⇒ **微秒级、无 DoS 面**，故**免登录、不进 HEAVY_POST_PATHS**。
🔴 **不伪装实测**：`verdict` 恒为 `DESIGN_BUDGET`（**非** ACCEPT/PASS），自带 `honest_note`。
🔴 **顶层只 import `math` / `os` / `typing`**（门禁用 `ast` 断言）。
"""
from __future__ import annotations

import math
import os
from typing import Any, Dict, List

__all__ = [
    "CASE_ID", "J4_HONEST_NOTE", "MILESTONES", "FINDINGS", "GAPS",
    "SELFCHECK_MODULES", "MODULE_SELFCHECKS_TOTAL", "RENDER_PATH_SMOKE", "HEAVY_POST",
    "cramer_temperature", "wiring_heat_load", "net_sensitivity_penalty",
    "microcell_rates", "case_card", "run_selfchecks",
]

CASE_ID = "LDA-J4 · 量子传感系统集成（器件 → 系统）"

J4_HONEST_NOTE = (
    "本卡为**设计预算**（design budget），所有数值由闭式算术现算，**非流片实测**、"
    "**非 foundry PDK**、**非商用器件数据表**。参数（γ_e/dD_dT/耦合强度/ρ₀/β/隔离度/"
    "气室几何）为**文献量级的设计示例**；模型为**一阶线性化**。"
    "不作制造/性能宣称，不报能效/TOPS/fJ-op；不作任何与他人同台比较。"
    "零量子 SDK；LLM 不进判决路径。"
)

# 设计示例量级（与 `_batch_j4_numeric` / `qs_j4_*` 默认档同值）
_C = ((1.00, 0.25, 0.10, 0.04),
      (0.15, 0.60, 0.08, 0.03),
      (0.06, 0.14, 0.30, 0.05),
      (0.04, 0.08, 0.03, 0.20))
_B = (1.00, 0.55, 0.28, 0.17)
COUPLING = 1.0
LORENZ = 2.44e-8          # W·Ω/K²
RHO0 = 1.0e-10            # Ω·m
BETA = 5.6e-11            # Ω·m/K
WIRE_A = 1.0e-7           # m²
WIRE_L = 0.5              # m
T_HOT = 300.0
T_COLD = 4.0
ISO_MW_OPT_DB = 55.0
ISO_OPT_RO_DB = 40.0
DRIVE_NONUNIF_DB = 0.2

MILESTONES: List[Dict[str, Any]] = [
    {"id": "M0", "name": "多参数 NV 交叉灵敏度解耦（B515）", "gate": 5, "gate_total": 5},
    {"id": "M1", "name": "芯片级 OPM 微型化（锚净增 0 · 如实登记）", "gate": 0, "gate_total": 0},
    {"id": "M2", "name": "单芯片集成预算（锚净增 0 · 如实登记）", "gate": 0, "gate_total": 0},
    {"id": "M3", "name": "低温布线热负载（B518）", "gate": 5, "gate_total": 5},
    {"id": "M4", "name": "系统总装签核（本卡）", "gate": 0, "gate_total": 0},
]

FINDINGS: List[Dict[str, str]] = [
    {"k": "多参数解耦", "v": "四场灵敏度矩阵解耦后温度分量可恢复（Cramer 闭式 ⇄ Landweber 迭代）"},
    {"k": "微型化代价", "v": "气室 2 mm vs 台式 20 mm ⇒ 壁弛豫率按 (a_bulk/a_cell)² = 100× 上升（涂层压制后）"},
    {"k": "集成隔离度", "v": "微波–光 55 dB / 光–读出 40 dB ⇒ 净灵敏度劣化 < 1.01×"},
    {"k": "封装热负载", "v": "单根铜线 300 K→4 K 约 25 mW（WF 电子热导通道 · 下界估算）"},
    {"k": "诚实边界", "v": "M1/M2 两档候选物理量经实 grep 逐条被既有锚占用 ⇒ **净增 0 如实登记**"},
]

GAPS: List[Dict[str, str]] = [
    {"id": "G-QSYS-1", "name": "多参数解耦", "state": "闭合（B515）"},
    {"id": "G-QSYS-2", "name": "芯片级微型化", "state": "能力层已建 · 锚净增 0（四重避让）"},
    {"id": "G-QSYS-3", "name": "单芯片集成", "state": "能力层已建 · 锚净增 0（三重避让）"},
    {"id": "G-QSYS-4", "name": "封装热负载", "state": "闭合（B518）"},
]

SELFCHECK_MODULES = ("qs_j4_multiparam", "qs_j4_microcell", "qs_j4_integration",
                     "qs_j4_packaging", "qs_j4_system")
MODULE_SELFCHECKS_TOTAL = 20 + 14 + 14 + 14 + 10
RENDER_PATH_SMOKE = "run_webui_j4_render_path_smoke.py"
HEAVY_POST = False


# ── 闭式算术（零重计算 · 纯 math）─────────────────────────────────────────
def _resp(coupling: float = COUPLING):
    d = [[1.00 if i == j else 0.0 for j in range(4)] for i in range(4)]
    return [[d[i][j] + float(coupling) * (_C[i][j] - d[i][j]) for j in range(4)]
            for i in range(4)]


def _det3(m) -> float:
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def _det4(M) -> float:
    d = 0.0
    for j in range(4):
        minor = [[M[r][c] for c in range(4) if c != j] for r in range(1, 4)]
        d += ((-1.0) ** j) * M[0][j] * _det3(minor)
    return d


def cramer_temperature(coupling: float = COUPLING) -> float:
    """多参数解耦的温度分量 τ̂（Cramer 法则 · 与 B515 golden 同律）。"""
    S = _resp(coupling)
    S1 = [row[:] for row in S]
    for i in range(4):
        S1[i][1] = _B[i]
    return _det4(S1) / _det4(S)


def wiring_heat_load(rho0: float = RHO0, beta: float = BETA) -> float:
    """低温线束热负载 Q（W · WF 有理闭式 · 与 B518 golden 同律）。"""
    def anti(T):
        u = rho0 + beta * T
        return (u - rho0 * math.log(u)) / (beta * beta)
    return (WIRE_A / WIRE_L) * LORENZ * (anti(T_HOT) - anti(T_COLD))


def net_sensitivity_penalty(iso_mw: float = ISO_MW_OPT_DB,
                            iso_ro: float = ISO_OPT_RO_DB,
                            nonunif_db: float = DRIVE_NONUNIF_DB) -> float:
    """净灵敏度劣化倍率（三源正交合成）。"""
    x_mw = 10.0 ** (-iso_mw / 20.0)
    x_ro = 10.0 ** (-iso_ro / 20.0)
    x_d = 10.0 ** (nonunif_db / 20.0) - 1.0
    return math.sqrt(1.0 + x_mw ** 2 + x_ro ** 2 + x_d ** 2)


def microcell_rates(cell_mm: float = 2.0, bulk_mm: float = 20.0,
                    coated: bool = True) -> Dict[str, float]:
    """芯片级 OPM 微型化的总弛豫率与劣化倍率（闭式 · 与 qs_j4_microcell 同口径）。

    🔴 口径含**缓冲气体项** γ_buf（= k_sd·p_bg = 3e4 × 100 Torr），与 `qs_j4_microcell.
    microcell_report` 的 `miniaturization_penalty = γ_total_cell / γ_total_bulk` 一致。
    """
    D = 1.9e-4 / 100.0     # m²/s —— D₀=1.9e-4 @1 Torr ÷ 缓冲气体 100 Torr（与 qs_j4_microcell 同律）
    supp = 100.0 if coated else 1.0
    g_buf = 3.0e4 * 100.0
    g_cell = D * (math.pi / (cell_mm * 1e-3)) ** 2 / supp + g_buf
    g_bulk = D * (math.pi / (bulk_mm * 1e-3)) ** 2 / supp + g_buf
    return {"wall_cell_s1": g_cell, "wall_bulk_s1": g_bulk,
            "penalty": g_cell / g_bulk}



# ═══════════════════════════════════════════════════════════════════════════
# N3-a · 签核锚登记（v0.9.283 · 让"签的是哪些锚"外部可复核）
# ---------------------------------------------------------------------------
# 🔴 `ANCHORS_SOURCE` 是**证据等级**，不是装饰：
#      "runtime"  该卡代码**真的跑**这条锚（可观测字段/调用）
#      "segment"  依据账本**号段归属**登记，卡内无运行时引用
#      "none"     本卡确实不依赖账本锚（如实登记为空，非缺漏）
#    把 segment 当 runtime 读，就是"把号段归属当已验证" —— 本项目的头号复发错。
# ═══════════════════════════════════════════════════════════════════════════
ANCHORS = {
    "B515": "多参数 NV 传感交叉灵敏度解耦温度分量 τ̂（J4 量子传感系统集成 · M0 多参数传感）：Cramer 闭式解析反演 golden vs Landweber 迭代解耦候选 · 无量纲",
    "B518": "低温布线束热负载 Q（J4 量子传感系统集成 · M3 封装热负载）：Wiedemann–Franz 电子热导有理闭式 golden vs RK4 积分定义 ODE 候选 · W",
}
ANCHORS_SOURCE = 'segment'

ANCHORS_NOTE = (
    "J4 号段 B515（多参数交叉灵敏度解耦）+ B518（低温布线束热负载）；**B516/B517 是账本 reserved_null 空位**，不计入。"
    "🔴 卡内无运行时锚引用。。")

def case_card() -> Dict[str, Any]:
    """案例卡数据（只读 GET 用）。"""
    tau = cramer_temperature()
    q = wiring_heat_load()
    pen = net_sensitivity_penalty()
    mc = microcell_rates()
    return {
        "case_id": CASE_ID,
        "verdict": "DESIGN_BUDGET",
        "anchors": ANCHORS,
        "anchors_source": ANCHORS_SOURCE,
        "anchors_note": ANCHORS_NOTE,
        "honest_note": J4_HONEST_NOTE,
        "milestones": MILESTONES,
        "findings": FINDINGS,
        "gaps": GAPS,
        "multiparam": {"tau_hat": tau, "coupling": COUPLING},
        "microcell": mc,
        "integration": {"net_penalty": pen, "penalty_ppm": (pen - 1.0) * 1e6},
        "packaging": {"single_wire_load_w": q, "k_at_300K": LORENZ * T_HOT / (RHO0 + BETA * T_HOT)},
        "span": {"modules": list(SELFCHECK_MODULES),
                 "module_selfchecks": MODULE_SELFCHECKS_TOTAL,
                 "render_path_smoke": RENDER_PATH_SMOKE,
                 "heavy_post": HEAVY_POST},
        "gate_checks": 25,
    }


def run_selfchecks() -> Dict[str, bool]:
    """案例卡自检（零重计算 + 与闭式同律）。"""
    checks = {}
    tau = cramer_temperature()
    checks["tau_matches_b515"] = bool(abs(tau - 0.6475252706753245) < 1e-12)
    q = wiring_heat_load()
    checks["heat_matches_b518"] = bool(abs(q - 0.025178944264050384) < 1e-15)
    checks["heat_positive"] = bool(q > 0.0)
    pen = net_sensitivity_penalty()
    checks["penalty_near_one"] = bool(1.0 <= pen < 1.01)
    mc = microcell_rates()
    checks["miniaturization_penalty_near_one"] = bool(1.0 < mc["penalty"] < 1.001)
    checks["microcell_cell_gt_bulk"] = bool(mc["wall_cell_s1"] > mc["wall_bulk_s1"])
    cc = case_card()
    checks["card_verdict_design_budget"] = bool(cc["verdict"] == "DESIGN_BUDGET")
    checks["card_five_milestones"] = bool(len(cc["milestones"]) == 5)
    checks["card_four_gaps"] = bool(len(cc["gaps"]) == 4)
    checks["card_span_heavy_post_false"] = bool(cc["span"]["heavy_post"] is False)
    checks["card_module_selfchecks_total"] = bool(
        cc["span"]["module_selfchecks"] == sum((20, 14, 14, 14, 10)))
    checks["no_solver_import"] = bool("numpy" not in globals() and "scipy" not in globals())
    checks["reverse_bad_coupling_changes_tau"] = bool(
        abs(cramer_temperature(0.0) - cramer_temperature(1.0)) > 1e-3)
    return checks
