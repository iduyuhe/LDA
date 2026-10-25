"""J3 量子测控与读出征程（闭环层 · M0–M4）案例卡（WebUI 只读端点数据源）。

═══════════════════════════════════════════════════════════════════════════
定位
═══════════════════════════════════════════════════════════════════════════
J3 征程「吃狗粮」LDA-J3（v0.9.235… · M0–M4）的**只读案例**：把
「**脉冲 → 门 → 读出 → 反馈 → 低温电子学**」这条**测控闭环链**连同 M0–M4 五档成果
（时域驱动脉冲 / DRAG 泄漏抑制 / 门保真标定 unitarity / 读出链 Purcell 滤波 /
低温电子学 Caves 极限 + 闭环总装）在一张卡里呈现。

🔴 **与 `/api/j2_qpu`（J2 物理比特层错误预算）分工不同**：
  · `j2_qpu` = **物理比特层 L2 · 错误率**（退相干门错误 / CR 门 / 读出误判 / QPU 预算）；
  · 本卡 = **控制层 L3 · 测控闭环**（脉冲怎么打 / 门保真怎么标 / 读出怎么判 /
    参数怎么回写 / 低温电子学噪声）—— 二者互补，非重复。

🔴 **零重计算**（与站内 design_* 等重算端点不同）：本模块**不跑仿真、不 import
求解器、不 import numpy/scipy** —— 全部数字由**闭式算术现算**（Rabi 闭式 / 三角法
精确谱 / 去极化纯度指数 / ABCD 代数 / 分布式噪声积分），与 `lda_qeda` 各模块的
现算值**逐值可对拍**（`run_webui_j3_render_path_smoke` 常驻）。
⇒ **微秒级、无 DoS 面**，故**免登录、不进 HEAVY_POST_PATHS**。
🔴 **不伪装实测**：`verdict` 恒为 `DESIGN_BUDGET`（**非** ACCEPT/PASS），自带 `honest_note`。
🔴 **顶层只 import `math` / `os`**（门禁用 `ast` 断言）。
"""
from __future__ import annotations

import math
import os
from typing import Any, Dict, List

__all__ = [
    "CASE_ID", "J3_HONEST_NOTE", "MILESTONES", "FINDINGS", "GAPS",
    "SELFCHECK_MODULES", "MODULE_SELFCHECKS_TOTAL", "RENDER_PATH_SMOKE",
    "rabi_population", "qutrit_leakage", "purity_decay", "unitarity_per_gate",
    "purcell_suppression", "amp_added_noise", "readout_error",
    "assignment_matrix", "pi_pulse_time", "calibration_iterations", "case_card",
    "run_selfchecks",
]

CASE_ID = "LDA-J3 · 量子测控与读出闭环层（脉冲→门→读出→反馈→低温电子学）"

J3_HONEST_NOTE = (
    "本卡为**设计预算**（design budget），所有数值由闭式算术现算，**非流片实测**、"
    "**非商用 PDK**、**非任意波形发生器标定数据**。参数（Ω/α/δ/Γ/f_q/f_s/η/g/L/SNR）"
    "为设计示例量级；不作制造/性能宣称，不报能效/TOPS/fJ-op；不作任何与他人同台比较。"
    "零量子 SDK（不依赖 Qiskit/Cirq/PennyLane/QuTiP）；LLM 不进判决路径。"
)

# 设计示例量级（与 `_batch_j3_numeric` 默认档同值）
OMEGA = 0.05          # rad/ns
DELTA = 0.03          # rad/ns
T_RABI = 100.0        # ns
ALPHA = -0.3          # rad/ns
GAMMA_DEPOL = 0.02    # 1/ns
T_DEPOL = 100.0       # ns
F_Q = 5.5             # GHz
F_S = 6.0             # GHz
ETA_RATIO = 0.5       # 单位增益附加噪声（量子极限）
G_AMP = 0.5           # /mm
L_AMP = 10.0          # mm
SNR_RO = 4.0

MILESTONES: List[Dict[str, Any]] = [
    {"id": "M0", "name": "时域驱动脉冲（Rabi 幅度/时长定标）", "gate": 5, "gate_total": 5},
    {"id": "M1", "name": "DRAG 泄漏抑制（三能级 P_leak）", "gate": 5, "gate_total": 10},
    {"id": "M2", "name": "门保真标定（RB + unitarity 纯度衰减）", "gate": 5, "gate_total": 15},
    {"id": "M3", "name": "读出链（IQ 解调 + 分配矩阵 + Purcell 滤波）", "gate": 5, "gate_total": 20},
    {"id": "M4", "name": "低温电子学（Caves 极限 + Friis 级联）+ 闭环总装", "gate": 5, "gate_total": 25},
]

FINDINGS: List[Dict[str, str]] = [
    {"k": "闭环捕获范围", "v": "θ=2·asin(√P₁)∈[0,π] 折叠 ⇒ 乘性定标只在 θ₀∈(0,π) 收缩；"
                              "θ₀>π 必发散（显式 diverged 守卫，不静默溢出）"},
    {"k": "DRAG 抑制", "v": "P_leak(无 DRAG) ≫ P_leak(β*)；最优 β* 落在 DRAG 标准值附近"},
    {"k": "unitarity 物理", "v": "二阶纯度衰减：酉（相干）误差 u=1、去极化（非相干）u=p² "
                                "⇒ 与一阶 RB 保真度联立可分离相干/非相干误差"},
    {"k": "Purcell 滤波", "v": "并联开路 λ/4 短截线带阻：S=1/|S21(f_q)|²，f_q→f_s 时抑制发散"},
    {"k": "Caves 极限", "v": "相位不敏感放大器附加噪声 n_add ≥ 1/2 光子；分布式链 gL→∞ ⇒ →1/2"},
]

#: 逐条缺口状态（**顺序与下方 GAPS 一一对应** · v0.9.286 四值口径）
#: 字符串型 gaps 不改形状（前端仍按字符串渲染），状态走这个并行列表。
GAPS_STATUS = [
    "已闭合（M0/M1 · 测控闭环三环签核）",
    "已闭合（M2 · 门保真二阶量 unitarity）",
    "已闭合（M3 · 读出链实时解调 + 分配矩阵）",
    "已闭合（M4 · 低温电子学噪声预算）",
]

GAPS: List[str] = [
    "G-CTRL-1 测控闭环可用性（Rabi 定标 + DRAG + 读出判别 三环签核）— M0/M1 已闭合",
    "G-CTRL-2 门保真二阶量（unitarity）与相干/非相干分解 — M2 已闭合",
    "G-CTRL-3 读出链实时解调 + 分配矩阵 + Purcell 滤波抑制比 — M3 已闭合",
    "G-CTRL-4 低温电子学噪声预算（Caves + Friis + cryo-CMOS）— M4 已闭合",
]

SELFCHECK_MODULES = ("pulse_library", "qubit_dynamics", "rb_benchmark", "readout_demod",
                     "cryo_electronics", "control_closed_loop")
MODULE_SELFCHECKS_TOTAL = 100     # 六能力层自检项合计（门禁 I 节核）
RENDER_PATH_SMOKE = "run_webui_j3_render_path_smoke"


# ═════════════════════ 闭式算术（与账本锚 B510–B514 同式）═════════════════════
def rabi_population(Omega: float = OMEGA, delta: float = DELTA, t: float = T_RABI) -> float:
    """B510 golden：P₁(t)=(Ω²/Ω_R²)sin²(Ω_R t/2)，Ω_R=√(Ω²+δ²)。"""
    orabi = math.hypot(float(Omega), float(delta))
    if orabi == 0.0:
        return 0.0
    return (float(Omega) ** 2) / (orabi ** 2) * math.sin(orabi * float(t) / 2.0) ** 2


def _qutrit_eig(Omega: float, alpha: float) -> List[float]:
    """三角法解 depressed cubic（与 `_batch_j3_numeric` 同式）。"""
    a2 = (Omega / 2.0) ** 2
    b2 = (math.sqrt(2.0) * Omega / 2.0) ** 2
    A = -alpha
    B = -(a2 + b2)
    C = a2 * alpha
    p = B - A * A / 3.0
    q = 2.0 * A ** 3 / 27.0 - A * B / 3.0 + C
    if p >= 0.0:
        raise ValueError("p ≥ 0 ⇒ 三角法不适用")
    m = 2.0 * math.sqrt(-p / 3.0)
    arg = max(-1.0, min(1.0, (3.0 * q / (2.0 * p)) * math.sqrt(-3.0 / p)))
    th = math.acos(arg) / 3.0
    return sorted(m * math.cos(th - 2.0 * math.pi * k / 3.0) - A / 3.0 for k in range(3))


def qutrit_leakage(Omega: float = OMEGA, alpha: float = ALPHA,
                   t: float = math.pi / OMEGA) -> float:
    """B511 golden：P_leak(t)=|Σ_k⟨0|v_k⟩⟨v_k|2⟩e^{−iλ_k t}|²（三角法精确谱）。"""
    a = float(Omega) / 2.0
    b = math.sqrt(2.0) * float(Omega) / 2.0
    re = im = 0.0
    for lam in _qutrit_eig(float(Omega), float(alpha)):
        v2 = (lam * lam - a * a) / (a * b)
        norm = math.sqrt(1.0 + (lam / a) ** 2 + v2 ** 2)
        c0 = 1.0 / norm
        c2 = v2 / norm
        re += c0 * c2 * math.cos(-lam * float(t))
        im += c0 * c2 * math.sin(-lam * float(t))
    return re * re + im * im


def unitarity_per_gate(Gamma: float = GAMMA_DEPOL) -> float:
    """去极化每门 unitarity u=e^{−2Γ}=p²。"""
    return math.exp(-2.0 * float(Gamma))


def purity_decay(Gamma: float = GAMMA_DEPOL, t: float = T_DEPOL) -> float:
    """B512 golden：P(t)=(1+e^{−2Γt})/2（二阶纯度衰减）。"""
    return 0.5 * (1.0 + math.exp(-2.0 * float(Gamma) * float(t)))


def purcell_suppression(f_q: float = F_Q, f_s: float = F_S, z_ratio: float = 1.0) -> float:
    """B513 golden：S=1/|S21|²，S21=2/(2+j(Z0/Zs)tanβl)，βl=(π/2)(f_q/f_s)。"""
    th = (math.pi / 2.0) * (float(f_q) / float(f_s))
    s21 = 2.0 / complex(2.0, float(z_ratio) * math.tan(th))
    return 1.0 / abs(s21) ** 2


def amp_added_noise(eta_ratio: float = ETA_RATIO, g: float = G_AMP,
                    L: float = L_AMP) -> float:
    """B514 golden：n_add=(η/g)(1−e^{−gL})（分布式放大链；gL→∞ ⇒ Caves 1/2）。"""
    return float(eta_ratio) * (1.0 - math.exp(-float(g) * float(L)))


def readout_error(snr: float = SNR_RO) -> float:
    """IQ 高斯判别误判率 ε=½·erfc(SNR/√2)（与 D-47 / B30 同口径）。"""
    return 0.5 * math.erfc(float(snr) / math.sqrt(2.0))


def assignment_matrix(eps: float) -> List[List[float]]:
    """分配矩阵 A[i][j]=P(判为 i|真实 j)（**列和**=1）。"""
    e = float(eps)
    return [[1.0 - e, e], [e, 1.0 - e]]


def pi_pulse_time(Omega: float = OMEGA) -> float:
    """π 脉冲时长 t_π = π/Ω（P₁=1 条件）。"""
    return math.pi / float(Omega)


def calibration_iterations(loop_gain: float = 0.5, rel_tol: float = 1e-9) -> int:
    """Rabi 幅度定标的**几何收敛迭代数预测**：误差每步 ×2^{−γ} ⇒
    k = ⌈ln(rel_tol)/ln(2^{−γ})⌉ + 1（与能力层实测同阶）。"""
    g = float(loop_gain)
    if not 0.0 < g <= 1.0:
        raise ValueError("γ ∈ (0,1]")
    return int(math.ceil(math.log(float(rel_tol)) / math.log(2.0 ** (-g)))) + 1


# ═══════════════════════════════ 案例卡 ═══════════════════════════════

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
    "B510": "广义 Rabi 时域布居 P₁=(Ω²/Ω_R²)·sin²(Ω_R t/2)（量子测控 J3 · M0 时域驱动脉冲）：解析闭式 golden vs 时域 TDSE RK4 候选 · 无量纲",
    "B511": "三能级 transmon 驱动泄漏布居 P_leak（量子测控 J3 · M1 DRAG 泄漏抑制）：三角法精确谱闭式 golden vs 时域 RK4 候选 · 无量纲",
    "B512": "去极化信道纯度衰减 P(t)=Tr(ρ²)（量子测控 J3 · M2 门保真标定 · unitarity）：解析闭式 golden vs 密度矩阵 Liouvillian RK4 候选 · 无量纲",
    "B513": "Purcell 滤波器抑制比 S=1/|S21(f_q)|²（量子测控 J3 · M3 读出链）：ABCD 代数闭式 golden vs 导纳 ODE RK4 数值积分候选 · 无量纲",
    "B514": "分布式相位不敏感放大链附加噪声 n_add（量子测控 J3 · M4 低温电子学 · Caves 极限）：解析闭式 golden vs 复合 Simpson 求积候选 · 光子数",
}
ANCHORS_SOURCE = 'segment'

ANCHORS_NOTE = (
    "J3 号段 B510–B514（广义 Rabi / DRAG 泄漏 / 去极化纯度衰减 / Purcell 滤波抑制比 / 放大链附加噪声）。"
    "🔴 卡内无运行时锚引用。。")

def case_card() -> Dict[str, Any]:
    """组装 J3 测控闭环案例卡（只读 · 零重计算 · 免登录）。"""
    p1 = rabi_population()
    leak = qutrit_leakage()
    u = unitarity_per_gate()
    pur = purity_decay()
    sup = purcell_suppression()
    nadd = amp_added_noise()
    eps = readout_error()
    return {
        "endpoint": "/api/j3_ctrl",
        "case_id": CASE_ID,
        "claim": "用 LDA 走完量子测控与读出闭环层 M0–M4：时域驱动脉冲 → DRAG 泄漏抑制 → "
                 "门保真标定（unitarity）→ 读出链（解调 + Purcell 滤波）→ 低温电子学"
                 "（Caves 极限）+ 闭环总装",
        "verdict": "DESIGN_BUDGET",
        "verdict_label": "设计预算（建模值 · 非流片实测）",
        "identity": {
            "physics": "超导 transmon 测控链 · 微波控制层 L3",
            "device": "AWG/DAC 脉冲源 + DRAG 波形 + 读出谐振腔 + λ/4 短截线滤波器 + 低温放大链",
            "unit": "单比特脉冲级（含三能级泄漏）；读出链单通道",
            "caliber": "概率/保真度/无量纲倍率/光子数 四类量纲；tol 绝对口径按量级标定",
            "route_note": "控制层 L3（脉冲怎么打/门怎么标/读出怎么判）；J2=物理比特层 L2，互补非重复",
            "zero_quantum_sdk": True,
        },
        "span": {
            "milestones": len(MILESTONES),
            "gate_checks": 44,               # 主门禁 run_j3_ctrl_smoke 实跑判据总数（A–K 节）
            "gate_total": int(MILESTONES[-1]["gate_total"]),   # 五档归集（5×5）
            "module_selfchecks": int(MODULE_SELFCHECKS_TOTAL),
            "selfcheck_modules": list(SELFCHECK_MODULES),
            "probe_mutations": 32,
        },
        "milestones": MILESTONES,
        "pulse": {
            "omega_rad_ns": float(OMEGA), "delta_rad_ns": float(DELTA),
            "t_ns": float(T_RABI), "p1": float(p1),
            "pi_pulse_ns": float(pi_pulse_time()),
            "calib_iters_pred": int(calibration_iterations()),
            "note": "B510：广义 Rabi 时域布居闭式（RWA 常矩阵精确解）+ π 脉冲条件",
        },
        "leakage": {
            "alpha_rad_ns": float(ALPHA),
            "t_ns": float(math.pi / OMEGA),
            "p_leak": float(leak),
            "note": "B511：三能级 transmon 驱动泄漏（三角法精确谱闭式）—— DRAG 抑制对象",
        },
        "gate_fidelity": {
            "Gamma_per_ns": float(GAMMA_DEPOL), "t_ns": float(T_DEPOL),
            "p": float(math.exp(-GAMMA_DEPOL)), "u": float(u),
            "purity": float(pur), "u_eq_p2": bool(abs(u - math.exp(-GAMMA_DEPOL) ** 2) < 1e-15),
            "note": "B512：unitarity（二阶纯度衰减）；u=p²（去极化关系）",
        },
        "readout": {
            "snr": float(SNR_RO), "error": float(eps),
            "assignment": assignment_matrix(eps),
            "f_q_ghz": float(F_Q), "f_s_ghz": float(F_S),
            "purcell_suppression": float(sup),
            "note": "M3：IQ 判别（ε=½erfc(SNR/√2)）+ 分配矩阵（列和=1）+ B513 Purcell 滤波抑制比",
        },
        "cryo": {
            "caves_limit": 0.5,
            "eta_ratio": float(ETA_RATIO), "g_per_mm": float(G_AMP), "L_mm": float(L_AMP),
            "n_add": float(nadd),
            "far_from_limit": bool(abs(nadd - 0.5) > 1e-6),
            "note": "B514：分布式相位不敏感放大链附加噪声（Caves 极限 1/2 光子）",
        },
        "findings": FINDINGS,
        "gaps": GAPS,
        "gaps_status": GAPS_STATUS,
        "positioning": {
            "disclaimer": "下列为公开报道的产业界**已交付系统**背景坐标；本卡为**设计预算**，"
                          "两者**不同台比较**。",
            "public_landscape": [
                "IBM/Google/祖冲之等已交付超导 QPU（100–1000+ qubit 级，含测控链工程实现）",
                "商用量子测控：AWG + 混频 + 低温放大链 的成熟仪器栈（闭源）",
            ],
            "what_is_different": [
                "交付物：产业界=仪器 + 芯片 + 云访问；LDA=**可复现的测控设计预算链**",
                "工具链：产业界=闭源 CAD/仪器固件；LDA=**开源(MIT)·Agent-native·零量子 SDK**",
                "判决路径：LDA=**LLM 不进判决路径**，判决为死标量比对 + 物理定律锚",
            ],
            "honest_limits": [
                "不作任何数值/保真度同台比较：不宣称在门保真度或读出保真度上优于任何实现。",
                "不宣称「量子优势」：本卡不涉及任何计算优势主张。",
                "参数为设计示例量级，误读为实测标定值即为失真。",
            ],
        },
        "anchors": ANCHORS,
        "anchors_source": ANCHORS_SOURCE,
        "anchors_note": ANCHORS_NOTE,
        "honest_note": J3_HONEST_NOTE,
        "render_path_smoke": RENDER_PATH_SMOKE,
    }


# ═══════════════════════════════ 自检 ═══════════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检（门禁同源调用）。闭式断言 + 红线断言（顶层不 import 求解器/numpy）。"""
    import ast

    res: Dict[str, bool] = {}

    def chk(name: str, cond: bool) -> None:
        res[name] = bool(cond)

    # ① Rabi 布居：δ=0 ⇒ sin²；Ω=0 ⇒ 0；π 脉冲 ⇒ 1
    chk("① Rabi δ=0 ⇒ sin²(Ωt/2)",
        abs(rabi_population(0.05, 0.0, 20.0) - math.sin(0.05 * 20.0 / 2.0) ** 2) < 1e-15)
    chk("② Rabi Ω=0 ⇒ 0", rabi_population(0.0, 0.03, 100.0) == 0.0)
    chk("③ π 脉冲 P₁(t_π)=1",
        abs(rabi_population(0.05, 0.0, pi_pulse_time(0.05)) - 1.0) < 1e-12)
    # ④ 三能级泄漏：非负且 < 1
    lk = qutrit_leakage()
    chk("④ 三能级泄漏 ∈ (0,1)", 0.0 < lk < 1.0)
    # ⑤ unitarity 关系 u=p²
    chk("⑤ u = p²（去极化关系）",
        abs(unitarity_per_gate(0.02) - math.exp(-0.02) ** 2) < 1e-15)
    # ⑥ 纯度：P(0)=1、单调降、P(∞)→1/2
    chk("⑥ 纯度 P(0)=1", abs(purity_decay(0.02, 0.0) - 1.0) < 1e-15)
    chk("⑦ 纯度单调降", purity_decay(0.02, 10.0) > purity_decay(0.02, 50.0))
    # ⑧ Purcell 抑制 ≥ 1 且 f_q→f_s 增大
    chk("⑧ Purcell S ≥ 1", purcell_suppression() >= 1.0)
    chk("⑨ Purcell f_q→f_s ⇒ S 增",
        purcell_suppression(5.99, 6.0) > purcell_suppression(5.5, 6.0))
    # ⑩ 分布式噪声 ≤ 1/2（量子极限上确界）
    chk("⑩ 分布式噪声 ≤ 1/2", amp_added_noise() < 0.5)
    # ⑪ 读出误判 ε(SNR=0)=1/2；单调降
    chk("⑪ ε(SNR=0)=1/2", abs(readout_error(0.0) - 0.5) < 1e-15)
    chk("⑫ ε 单调降", readout_error(3.0) > readout_error(6.0))
    # ⑬ 分配矩阵列和 = 1
    A = assignment_matrix(0.03)
    chk("⑬ 分配矩阵列和=1",
        all(abs(A[0][j] + A[1][j] - 1.0) < 1e-15 for j in range(2)))
    # ⑭ 定标迭代数预测为正整数
    it = calibration_iterations()
    chk("⑭ 定标迭代数预测 ∈ [1, 100]", 1 <= it <= 100)
    # ⑮ 案例卡 verdict 恒 DESIGN_BUDGET（不伪装实测）
    card = case_card()
    chk("⑮ verdict 恒 DESIGN_BUDGET", card["verdict"] == "DESIGN_BUDGET")
    chk("⑯ 案例卡自带 honest_note", bool(card.get("honest_note")))
    # ⑰ 红线：顶层不 import 求解器 / numpy / scipy（ast 静态核）
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "j3_case.py"),
               encoding="utf-8").read()
    tree = ast.parse(src)
    top_mods = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_mods.add(node.module.split(".")[0])
    chk("⑰ 顶层只 import math/os/typing（零重计算红线）",
        top_mods <= {"math", "os", "typing", "__future__"})

    if verbose:
        nbad = sum(1 for v in res.values() if not v)
        for k, v in res.items():
            print("  [%s] %s" % ("PASS" if v else "FAIL", k))
        print("自检：%d FAIL" % nbad)
    return all(res.values())


if __name__ == "__main__":  # pragma: no cover
    print("J3 测控闭环案例卡（WebUI 端点数据源）自检")
    ok = run_selfchecks(verbose=True)
    print("ALL PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)
