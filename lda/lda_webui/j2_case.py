"""J2 超导 Transmon QPU 征程（物理比特层 L2 · M0–M4）案例卡（WebUI 只读端点数据源）。

═══════════════════════════════════════════════════════════════════════════
定位
═══════════════════════════════════════════════════════════════════════════
J2 征程「吃狗粮」LDA-J2（v0.9.230 … v0.9.233 · M0–M4）的**只读案例**：把
「**J1↔J2 复利闭环**」（物理错误率 → QEC 逻辑预算）连同 M0–M4 四档成果
（单比特门错误模型 / 两比特 CR 门 / 色散读出链 / QPU 误差预算 + 拓扑对接）
在一张卡里呈现。

🔴 **与 `/api/schip_demo`（S 分支超导**芯片级 P&R**案例卡 · D-148）分工不同**：
  · `schip_demo` = **器件/版图**层（真 GDS · DRC/LVS · 频率避撞 · 规模压力）；
  · 本卡 = **物理比特层 L2 · 错误率链**（门错误率 / 读出误判 / QPU 误差预算 /
    拓扑↔表面码）+ **J1↔J2 复利闭环**。二者互补，非重复。

🔴 **零重计算**（与站内 design_* 等重算端点不同）：本模块**不跑仿真、不 import
求解器、不读既有 report** —— 全部数字由**闭式算术现算**（退相干极限 / CR 有效模型 /
读出 SNR / ZZ 二阶微扰 / QPU 预算集成 / 方阵 Laplacian 谱定理），与 `lda_qeda`
各模块的现算值**逐值可对拍**（`run_webui_j2_render_path_smoke` 常驻）。
⇒ **微秒级、无 DoS 面**，故**免登录、不进 HEAVY_POST_PATHS**，与 `/api/schip_demo`、
`/api/qsensor_demo`、`/api/verification_ledger` 同属「公开只读验货」类。

🔴 **不伪装实测**：`verdict` 恒为 `DESIGN_BUDGET`（**非** ACCEPT/PASS），返回体自带
`honest_note`。

🔴 **顶层只 import `math` / `os`**（门禁 `run_webui_j2_render_path_smoke` 用 `ast`
断言）—— 保证「零重计算」不是口号。
"""
from __future__ import annotations

import math
import os
from typing import Any, Dict

__all__ = [
    "CASE_ID", "J2_HONEST_NOTE", "MILESTONES", "FINDINGS", "GAPS",
    "SELFCHECK_MODULES", "MODULE_SELFCHECKS_TOTAL", "RENDER_PATH_SMOKE",
    "gate_error_1q", "depolarizing_parameter", "cr_gate_time_us",
    "cr_gate_error_2q", "readout_snr", "residual_zz_error", "qpu_budget",
    "lambda2_closed_form", "orders_below_threshold", "logical_error_rate_ideal",
    "case_card", "run_selfchecks",
]

# ═══════════════════════════ 常量（与 lda_qeda 真源同口径）═══════════════════════
CASE_ID = "LDA-J2 · 超导 transmon QPU 物理比特层（J1↔J2 复利闭环）"

#: 设计示例工作点（**非实测 PDK** · 与 `qpu_error_budget.DEFAULT_QPU_BUDGET` 同口径）
T1_S = 80e-6
T2_S = 60e-6
T_1Q_S = 20e-9
T_IDLE_S = 300e-9
J_MHZ = 20.0
DELTA_MHZ = -200.0
ALPHA_MHZ = -250.0
CHI_GHZ = 0.05
KAPPA_R_GHZ = 0.005
NBAR = 2.0
ETA_READOUT = 0.5
N_AMP = 5.0
T_RO_S = 4.236705e-9
N_1Q, N_2Q, N_RO, N_IDLE = 2, 4, 1, 2
P_TH = 0.01
A_SCALE = 0.03
MARGIN_ORDERS = 2.0
#: 静态杂散 ZZ 上限（S 铁律② · 与 `sc_readout.ZZ_STRAY_LIMIT_MHZ` 同口径）
ZZ_STRAY_LIMIT_MHZ = 1.0
#: M4 拓扑对接默认档（方阵耦合图 · 4 邻居）
ROWS, COLS = 10, 10
#: 读出的最近邻静态 ZZ（**设计示例**：与 `sc_readout.crosstalk_budget` 同量级）
ZETA_ZZ_MHZ = 0.9871641527656998

J2_HONEST_NOTE = (
    "① 本卡为**设计预算 / 建模值**（闭式物理律 + 设计示例参数），"
    "**非流片后实测**——无低温实测 T1/T2、无实测门/读出台面保真度、无 foundry 回片；"
    "② T1/T2/J/Δ/α/χ/κ/n̄/η/rows/cols 均为**设计示例量级**（rotated surface code / "
    "transmon 典型），**非任何 foundry 的 PDK deck**、非实测标定值；"
    "③ **不含量子线路级仿真、不含脉冲级控制标定、不含解码器实测**；"
    "J1↔J2 桥只证「物理错误率 → QEC 逻辑预算」链路自洽（本质是标定/一致性关系，"
    "以常驻护栏承载，**不伪造独立锚**）；"
    "④ λ₂ 是**图论谱不变量**（不耦合器件物理常数）；拓扑↔表面码只做**设计对接**；"
    "⑤ **零量子 SDK**：不依赖 Qiskit / Cirq / PennyLane / QuTiP 等外部量子框架"
    "（本模块顶层仅 `math` / `os` · ast 断言）；"
    "⑥ 判决落**非 AI ground**：PASS/FAIL 由死标量比对，**LLM 不进判决路径**。"
)

# ═══════════════════════ 五档征程（静态事实 · 可回溯门禁）═══════════════════════
# 🔴 **口径（机器可核对 · 非手写漂移）**：`gate` = 该档**新增**的 `run_j2_qpu_smoke`
#    判据数（该门禁是**单脚本累计**，判据按字母带分档：A–E+R = M0+M1 · F = M2 ·
#    G = M3 · H = M4）；`gate_total` = 累计到该档的判据数。二者由常驻门禁
#    `run_webui_j2_render_path_smoke` 实跑该 smoke 并按字母带**逐档核对**。
MILESTONES = [
    {"id": "M0+M1", "code": "v0.9.230", "title": "物理错误模型 + J1 闭环校准",
     "gate": 15, "gate_total": 15, "bands": ["A", "B", "C", "D", "E", "R"],
     "result": "单比特门退相干极限闭式 F=(3+2e^{−t/T2}+e^{−t/T1})/6 ⇄ Bloch 向量 "
               "Lindblad 主方程 RK4（rel 1.11e-16）；J2 物理错误率 → J1 逻辑错误率标度；"
               "同源体检**否决宪章 B506/B508**（与既有锚 B10 三者全同）⇒ 净增 0"},
    {"id": "M2", "code": "v0.9.231", "title": "两比特 CR 门错误率",
     "gate": 6, "gate_total": 21, "bands": ["F"],
     "result": "净增 **B506**（CR 门退相干错误率 闭式 ⇄ 16×16 Liouvillian RK4）"
               "+ **B507**（残余 ZZ (4/5)sin²(ζt/2) 闭式 ⇄ 4×4 矩阵传播子 RK4）"},
    {"id": "M3", "code": "v0.9.232", "title": "色散读出链 + 串扰",
     "gate": 7, "gate_total": 28, "bands": ["G"],
     "result": "净增 **B508**（FDM 多音读出相邻通道频谱重叠串扰比 4γ²/(4γ²+δ²) 闭式 "
               "⇄ sinh 换元 + 复合 Simpson）；同源体检否决宪章 B511（被 B30 占用）/ "
               "B512（被 B507 占用）"},
    {"id": "M4", "code": "v0.9.233", "title": "QPU 误差预算集成 + 拓扑对接 + 收官",
     "gate": 9, "gate_total": 37, "bands": ["H"],
     "result": "净增 **B509**（QPU 耦合图代数连通度 λ₂ 谱定理闭式 2−2cos(π/max) "
               "⇄ 嵌套 Krylov Rayleigh–Ritz）；同源体检否决宪章 B513（布尔量不可锚）/ "
               "B514（与 S4 + J1 B502–B505 同源）⇒ 改靶 λ₂"},
]

#: 能力层模块（该征程落地的 `lda_qeda` 模块）⇒ 自检项总数由门禁**实跑**核对。
#: `run_webui_j2_render_path_smoke` 逐模块跑 `run_selfchecks(verbose=True)` 并数
#: 行首 `[PASS]` 行 ⇒ 与 `span.module_selfchecks` 对照（防手写数字漂移）。
SELFCHECK_MODULES = ("j2_readout_mux", "qpu_error_budget", "topology_qec_bridge")

#: 本卡配对的常驻门禁（探针条数 ⇒ `span.probe_mutations` 的核对真源）
RENDER_PATH_SMOKE = "run_webui_j2_render_path_smoke.py"

#: `SELFCHECK_MODULES` 的 `run_selfchecks()` 行首 `[PASS]` 行数之和（实跑值）。
#: 🔴 由 `run_webui_j2_render_path_smoke` 实跑三者并断言 `== MODULE_SELFCHECKS_TOTAL`。
MODULE_SELFCHECKS_TOTAL = 54      # j2_readout_mux 16 + qpu_error_budget 23 + topology_qec_bridge 15


# ═══════════════════════ 关键结论（物理 + 方法学）═══════════════════════
FINDINGS = [
    {"title": "J1↔J2 复利闭环（本征程的核心）",
     "detail": "J2 给出**真实物理错误率** p_phys ⇒ 注入 J1 表面码阈值标度/解码器 ⇒ "
               "逻辑错误率曲线由「裸标度界」变为「物理标定曲线」；反之 J1 阈值 p_th≈1% "
               "成为 J2 门设计的**保真度硬指标**（须落阈值下 ≥2 数量级）。"
               "该桥**本质是标定/一致性关系**，故以常驻护栏承载、不伪造独立锚。"},
    {"title": "物理内核方法学独立（非自证）",
     "detail": "每道锚均为「闭式物理律 golden ⇄ 方法学独立数值候选」："
               "Lindblad RK4 / Liouvillian 超算子 / 矩阵传播子 / Simpson 求积 / "
               "Krylov Rayleigh–Ritz。判决为**死标量比对**。"},
    {"title": "同源体检否决 ≠ 少干活（四档连续两轮）",
     "detail": "宪章 M0/M1/M3/M4 四个候选锚共 **5 个**被同源体检证否"
               "（B506/B508 撞 B10；B511 撞 B30；B512 撞 B507；B513 布尔量不可锚；"
               "B514 撞 S4+J1 率积分族）—— 每例均**改靶到既有锚未覆盖的连续物理量**，"
               "而非降低标准充数。"},
    {"title": "层间分工：与 S 分支 schip 卡互补",
     "detail": "`/api/schip_demo` 覆盖**器件/版图**（真 GDS · DRC/LVS · 频率避撞 · "
               "规模压力）；本卡覆盖**物理比特层错误率链**（门错误率 / 读出 / "
               "QPU 预算 / 拓扑↔表面码）——同一条超导路线的两个不同抽象层。"},
    {"title": "预算口径：签核比「每操作平均错误率」",
     "detail": "表面码阈值 p_th≈1% 是 **circuit-level 每操作**错误率（非每周期总量）"
               "⇒ 签核比 p_op=Σ分量×次数/n_ops；同时**并列披露**每周期总量与最差分量"
               "（不选择性披露）——首版按每周期总量签核曾导致恒 REJECT 的口径错误。"},
]

# ═══════════════════════ 诚实边界（未闭合项 · 逐条登记）═══════════════════════
GAPS = [
    {"id": "J2-G-A", "title": "无流片 / 无低温实测",
     "status": "边界声明（v0.9.300 口径统一：**非流片纪律**属项目级永久边界，"
               "与 `ecore G-A` / `pchip G-A` / `schip G-A` 同口径）",
     "detail": "全部为设计预算；T1/T2、门保真度、读出保真度均未实测。"
               "🔴 **改状态不等于能力具备**：本卡仍无任何低温实测，"
               "只是这条要求的（流片预算 / 4 K 实验台）**不是本仓任何卡能完成的活** ⇒ 永久边界。"},
    {"id": "J2-G-B", "title": "无 foundry PDK / 无脉冲级标定",
     "status": "边界声明（v0.9.300 口径统一：PDK 须 **NDA + 工艺厂 deck**、"
               "脉冲级标定须 **实验台** ⇒ 与 `ecore G-B` 同口径）",
     "detail": "参数为设计示例量级；不含 Rabi/Ramsey 标定流程与器件回片。"
               "🔴 **能力事实不变**：参数仍是公开典型量级占位、仍无标定流程；"
               "判为边界是因为这两件事**都须外部硬件/产线**，不是本卡能做的活。"},
    {"id": "J2-G-C", "title": "不含线路级量子态仿真与解码器实测", "status": "未闭合",
     "detail": "**已有**容错编译（D-218 · ft_compiler）与编译后噪声感知资源核算"
               "（D-226 · noise_aware_schedule：累积上界 / 可证双侧界 / 并行化整数比 / 纠错轮数）；"
               "**仍缺**线路级量子态演化（不演化态、不算保真度）与解码器在真机上的表现。"},
    {"id": "J2-G-D", "title": "拓扑↔表面码仅设计对接", "status": "未闭合",
     "detail": "λ₂ 为图论谱不变量；2D 最近邻嵌入判定为设计规则。"
               "**已有** QEC 码族闭式与 hashing 界（D2 · 唯一可锚量）；"
               "**仍缺**编译/映射实测与真实硬件拓扑下的往返验证。"},
]


# ═══════════════════════════ 闭式（可反向测试）═══════════════════════════
def gate_error_1q(t_s: float, T1_s: float = T1_S, T2_s: float = T2_S) -> float:
    """单比特门退相干极限错误率 ε=1−F，F=(3+2e^{−t/T2}+e^{−t/T1})/6。

    与 `physical_error_model.gate_error_decoherence` **同一物理律**（B10 族）。
    """
    t = float(t_s)
    if t < 0.0:
        raise ValueError("t 须 ≥ 0")
    if T1_s <= 0.0 or T2_s <= 0.0:
        raise ValueError("T1 / T2 须 > 0")
    if T2_s > 2.0 * T1_s + 1e-18:
        raise ValueError("非物理输入：T2 > 2·T1")
    f = (3.0 + 2.0 * math.exp(-t / float(T2_s)) + math.exp(-t / float(T1_s))) / 6.0
    return 1.0 - f


def depolarizing_parameter(t_s: float, T1_s: float = T1_S, T2_s: float = T2_S) -> float:
    """去极化参数 p=2·ε（F_avg = 1 − p/2 口径）——**J1 注入用的物理错误率**。

    🔴 **口径关键**：`j2_to_j1_calibration` / `run_j2_qpu_smoke` 注入 J1 的是
    去极化参数 `p_depol = 2·E`（与 `physical_error_model.depolarizing_parameter` 同式），
    **不是**门错误率 ε 本身（二者恒差 2 倍）。用错即令 `orders_below` 偏 +0.301。
    """
    return 2.0 * gate_error_1q(t_s, T1_s, T2_s)


def cr_gate_time_us(J_mhz: float = J_MHZ, delta_mhz: float = DELTA_MHZ,
                    alpha_mhz: float = ALPHA_MHZ) -> Dict[str, float]:
    """CR 有效模型 g_CR=2J²Δ/(α²−Δ²)（MHz）⇒ t_CR=π/|g_CR|（µs）。

    与 `cross_resonance.cross_resonance` 同式；参数区无效（|Δ| ≥ |α|）⇒ 抛 ValueError。
    """
    J, delta, alpha = float(J_mhz), float(delta_mhz), float(alpha_mhz)
    if abs(delta) >= abs(alpha):
        raise ValueError("CR 有效模型参数区无效：须 |Δ| < |α|")
    denom = alpha * alpha - delta * delta
    if denom == 0.0:
        raise ValueError("α²−Δ² = 0 ⇒ g_CR 未定义")
    g = 2.0 * J * J * delta / denom
    if g == 0.0:
        raise ValueError("g_CR = 0 ⇒ t_CR 未定义")
    return {"g_CR_mhz": g, "t_CR_us": math.pi / abs(g)}


def cr_gate_error_2q(t_us: float, T1_s: float = T1_S, T2_s: float = T2_S) -> float:
    """两比特 CR 门退相干错误率（**与账本锚 B506 同一物理律**）。

    F_pro(T1,T2,t)=(1+e^{−t/T1}+2e^{−t/T2})/4；2q 张量 ⇒ ε=1−(4·F_pro²+1)/5。
    """
    t = float(t_us) * 1e-6

    def _fp(T1: float, T2: float) -> float:
        return (1.0 + math.exp(-t / float(T1)) + 2.0 * math.exp(-t / float(T2))) / 4.0

    fp = _fp(T1_s, T2_s) * _fp(T1_s, T2_s)
    return 1.0 - (4.0 * fp + 1.0) / 5.0


def readout_snr(chi_ghz: float = CHI_GHZ, kappa_r_ghz: float = KAPPA_R_GHZ,
                nbar: float = NBAR, eta: float = ETA_READOUT, N_amp: float = N_AMP,
                t_m_s: float = T_RO_S) -> float:
    """单发读出 SNR = 2·χ_rad·√(n̄·η·t_m/(κ_rad·(1+2N_amp)))（与 D-47 同式）。"""
    chi_rad = 2.0 * math.pi * float(chi_ghz) * 1e9
    kap_rad = 2.0 * math.pi * float(kappa_r_ghz) * 1e9
    return (2.0 * chi_rad
            * math.sqrt(float(nbar) * float(eta) * float(t_m_s)
                        / (kap_rad * (1.0 + 2.0 * float(N_amp)))))


def readout_eps(chi_ghz: float = CHI_GHZ, kappa_r_ghz: float = KAPPA_R_GHZ,
                nbar: float = NBAR, eta: float = ETA_READOUT, N_amp: float = N_AMP,
                t_m_s: float = T_RO_S) -> float:
    """读出误判概率 ε=½·erfc(SNR/√2)（**与 B30 同一物理律**）。"""
    snr = readout_snr(chi_ghz, kappa_r_ghz, nbar, eta, N_amp, t_m_s)
    return 0.5 * math.erfc(snr / math.sqrt(2.0))


def residual_zz_error(t_us: float, zeta_mhz: float = ZETA_ZZ_MHZ) -> float:
    """残余 ZZ 诱导错误率 ε=(4/5)·sin²(ζt/2)（**与账本锚 B507 同一物理律**）。

    ζ 以 MHz 计 ⇒ 角频率 ζ_rad/µs = 2π·ζ_MHz·1e-3。
    """
    zeta_rad_per_us = 2.0 * math.pi * (float(zeta_mhz) * 1e-3)
    phi = zeta_rad_per_us * float(t_us)
    return (4.0 / 5.0) * math.sin(phi / 2.0) ** 2


def orders_below_threshold(p_phys: float, p_th: float = P_TH) -> float:
    """物理错误率位于阈值下方多少个数量级：log10(p_th/p_phys)。"""
    if p_phys <= 0.0 or p_th <= 0.0:
        raise ValueError("p_phys / p_th 须 > 0")
    return math.log10(float(p_th) / float(p_phys))


def logical_error_rate_ideal(p_phys: float, d: int, p_th: float = P_TH,
                             A: float = A_SCALE) -> float:
    """J1 阈值下逻辑错误率标度 **p_L=A·(p/p_th)^((d+1)/2)**（阈值以上保守饱和 1.0）。"""
    if p_phys <= 0.0 or p_th <= 0.0 or A <= 0.0:
        raise ValueError("p_phys / p_th / A 须 > 0")
    if int(d) < 1:
        raise ValueError("d 须 ≥ 1")
    if p_phys >= p_th:
        return 1.0
    return float(A * (p_phys / p_th) ** ((int(d) + 1) / 2.0))


def lambda2_closed_form(rows: int, cols: int) -> float:
    """方阵耦合图 Laplacian 代数连通度闭式 λ₂=2−2cos(π/max(rows,cols))。

    （方阵耦合图 = Cartesian 积 P_rows□P_cols ⇒ Laplacian 谱 = 因子谱的 Kronecker 和
    ⇒ 精确解析解、非截断近似。**与账本锚 B509 golden 同一物理律**。）
    """
    r, c = int(rows), int(cols)
    if r < 1 or c < 1:
        raise ValueError("rows / cols 须 ≥ 1")
    return 2.0 - 2.0 * math.cos(math.pi / float(max(r, c)))


def qpu_budget() -> Dict[str, Any]:
    """QPU 每周期误差预算集成（**与 `qpu_error_budget.qpu_cycle_error_budget` 同口径**）。

    五分量（1q / 2q CR / 读出 / idle / 残余 ZZ）× 周期内次数 ⇒
    每周期总量 p_cycle_sum、**每操作平均** p_op_avg（签核口径）与最差分量。
    """
    eps = {
        "1q": gate_error_1q(T_1Q_S),
        "2q": cr_gate_error_2q(cr_gate_time_us()["t_CR_us"]),
        "ro": readout_eps(),
        "idle": gate_error_1q(T_IDLE_S),
        "zz": residual_zz_error(cr_gate_time_us()["t_CR_us"]),
    }
    counts = {"1q": N_1Q, "2q": N_2Q, "ro": N_RO, "idle": N_IDLE, "zz": N_2Q}
    p_sum = sum(eps[k] * counts[k] for k in eps)
    n_ops = sum(counts.values())
    p_op_avg = p_sum / float(n_ops)
    margin = P_TH - p_op_avg
    labels = {"1q": "单比特门", "2q": "两比特 CR 门", "ro": "色散读出",
              "idle": "闲置", "zz": "残余 ZZ"}
    rows = [{"key": k, "label": labels[k], "eps": float(eps[k]),
             "count": int(counts[k]), "subtotal": float(eps[k] * counts[k])}
            for k in ("1q", "2q", "ro", "idle", "zz")]
    return {
        "components": rows,
        "n_ops": int(n_ops),
        "p_cycle_sum": float(p_sum),
        "p_op_avg": float(p_op_avg),
        "p_op_max": float(max(eps.values())),
        "p_th": float(P_TH),
        "threshold_margin": float(margin),
        "signoff": "ACCEPT" if margin > 0.0 else "REJECT",
        "zz_within_limit": bool(ZETA_ZZ_MHZ <= ZZ_STRAY_LIMIT_MHZ),
        "zeta_limit_mhz": float(ZZ_STRAY_LIMIT_MHZ),
    }


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
    "B506": "两比特 CR 门退相干错误率 ε=1−(4·F_pro^A·F_pro^B+1)/5（超导 Transmon J2 · M2 两比特门层）：张量 A+D 信道闭式 golden vs 16×16 Liouvillian RK4 候选 · 无量纲",
    "B507": "残余 ZZ 诱导门错误率 ε=(4/5)·sin²(ζt/2)（超导 Transmon J2 · M2 两比特门层）：闭式 golden vs 矩阵传播子 RK4 候选 · 无量纲",
    "B508": "FDM 多音读出相邻通道频谱重叠串扰比 X=4γ²/(4γ²+δ²)（超导 Transmon J2 · M3 色散读出链 + 串扰）：闭式 golden vs sinh 换元+复合 Simpson 数值卷积候选 · 无量纲",
    "B509": "QPU 耦合图代数连通度 λ₂（Fiedler 值）（超导 Transmon J2 · M4 QPU 误差预算集成 + 拓扑对接）：谱定理闭式 golden vs 嵌套 Krylov 子空间 Rayleigh–Ritz 候选 · 无量纲",
}
ANCHORS_SOURCE = 'segment'

ANCHORS_NOTE = (
    "J2 号段 B506–B509（CR 门退相干错误率 / 残余 ZZ / FDM 多音串扰 / 耦合图代数连通度 λ₂）。"
    "🔴 卡内无运行时锚引用。。")

def case_card() -> Dict[str, Any]:
    """组装 J2 QPU 案例卡（只读 · 零重计算 · 免登录）。

    `verdict` 恒为 `DESIGN_BUDGET` —— 明标「设计预算 / 建模值」而非实测。
    """
    cr = cr_gate_time_us()
    p_phys = depolarizing_parameter(T_1Q_S)
    loop_curve = [{"d": d, "p_logic": logical_error_rate_ideal(p_phys, d)}
                  for d in (3, 5, 7, 9)]
    budget = qpu_budget()
    lam = lambda2_closed_form(ROWS, COLS)
    required_d3 = 2 * 3 * 3 - 1
    n_qubits = ROWS * COLS
    return {
        "endpoint": "/api/j2_qpu",
        "case_id": CASE_ID,
        "claim": "用 LDA 走完超导 transmon QPU 物理比特层 M0–M4：物理错误模型 → 两比特 CR 门 "
                 "→ 色散读出链 → QPU 误差预算 + 拓扑↔表面码对接，并闭 J1↔J2 复利环",
        "verdict": "DESIGN_BUDGET",
        "verdict_label": "设计预算（建模值 · 非流片实测）",
        "identity": {
            "physics": "超导 transmon（固定频率）· 微波 QPU 物理比特层 L2",
            "device": "transmon 比特 + 可调耦合器（SQUID 有效模型）+ 读出谐振腔 + FDM 馈线",
            "unit": "transmon 单元（十字岛 + Josephson 结）；方阵 4 邻居 / heavy-hex 度 3",
            "caliber": "错误率口径 = 每门 / 每操作错误率 ε；λ₂ 为图论谱不变量（不耦合器件常数）",
            "route_note": "超导路线的**物理比特层**（与 S 分支 schip 卡的器件/版图层互补）；"
                          "J2 供物理错误率、J1 返逻辑预算",
            "zero_quantum_sdk": True,
        },
        "span": {
            "milestones": len(MILESTONES),
            "gate_checks": sum(m["gate"] for m in MILESTONES),
            "gate_total": int(MILESTONES[-1]["gate_total"]),
            "module_selfchecks": int(MODULE_SELFCHECKS_TOTAL),
            "selfcheck_modules": list(SELFCHECK_MODULES),
            "probe_mutations": 19,
        },
        "milestones": MILESTONES,
        "loop": {
            "p_th": float(P_TH),
            "a_scale": float(A_SCALE),
            "p_phys_used": float(p_phys),
            "p_phys_caliber": "去极化参数 p=2·ε（F_avg=1−p/2 口径 · J1 注入口径）",
            "orders_below": float(orders_below_threshold(p_phys)),
            "margin_orders": float(MARGIN_ORDERS),
            "target_met": bool(orders_below_threshold(p_phys) >= MARGIN_ORDERS),
            "curve": loop_curve,
            "note": "p_L(d)=A·(p_phys/p_th)^((d+1)/2)（阈值下）；目标 = p_phys 落阈值下 "
                    "≥2 数量级（触发子阈值指数抑制）",
        },
        "errors": {
            "t_1q_ns": float(T_1Q_S * 1e9),
            "eps_1q": float(gate_error_1q(T_1Q_S)),
            "t_cr_us": float(cr["t_CR_us"]),
            "g_cr_mhz": float(cr["g_CR_mhz"]),
            "eps_2q": float(cr_gate_error_2q(cr["t_CR_us"])),
            "zeta_zz_mhz": float(ZETA_ZZ_MHZ),
            "zeta_limit_mhz": float(ZZ_STRAY_LIMIT_MHZ),
            "eps_zz": float(residual_zz_error(cr["t_CR_us"])),
        },
        "readout": {
            "chi_ghz": float(CHI_GHZ),
            "kappa_r_ghz": float(KAPPA_R_GHZ),
            "nbar": float(NBAR),
            "eta": float(ETA_READOUT),
            "n_amp": float(N_AMP),
            "t_ro_ns": float(T_RO_S * 1e9),
            "snr": float(readout_snr()),
            "eps": float(readout_eps()),
            "t1_pollution_rel": float(T_RO_S / T1_S),
        },
        "budget": budget,
        "topology": {
            "rows": int(ROWS), "cols": int(COLS), "n_qubits": int(n_qubits),
            "max_degree": 4,
            "lambda2_closed": float(lam),
            "native_degree": 4,
            "embedding": "DIRECT" if 4 >= 4 else "ADAPTED",
            "n_couplings": int(ROWS * (COLS - 1) + COLS * (ROWS - 1)),
            "resource_required_d3": int(required_d3),
            "resource_ok": bool(required_d3 <= n_qubits),
            "n_logical_capacity": int(n_qubits // required_d3),
        },
        "findings": FINDINGS,
        "gaps": GAPS,
        "positioning": {
            "disclaimer": "下列为公开报道的产业界**已交付芯片**数字，仅作背景坐标；"
                          "本卡为**设计预算**，两者**不同台比较**。",
            "public_landscape": [
                "IBM Heron r2/r3 156 qubit（固定频率 transmon + 可调耦合器）· "
                "Condor 1,121 qubit（2023）· Nighthawk 120 qubit 方格 4-度连通",
                "Google Willow 105 qubit（2024-12 首次 below-threshold纠错）",
                "祖冲之 3.2 107 qubit（全微波控制 · 低于阈值纠错）",
                "Fujitsu + RIKEN 256 qubit（2025-04）· Rigetti/IQM 84–150 qubit 级",
            ],
            "what_is_different": [
                "交付物：产业界=已制备芯片 + 云访问；LDA=**设计预算链**（可复现、可审计）",
                "工具链：产业界=闭源 CAD/PDK + 各自 SDK；LDA=**开源(MIT)·Agent-native·零量子 SDK**",
                "判决路径：LDA=**LLM 不进判决路径**，判决为死标量比对 + 物理定律锚",
            ],
            "honest_limits": [
                "不作任何数值/保真度同台比较：不宣称在门保真度、相干时间或纠错阈值上优于任何厂商。",
                "不宣称「量子优势」：本卡不涉及任何计算优势主张。",
                "参数为设计示例量级，误读为实测标定值即为失真。",
            ],
        },
        "anchors": ANCHORS,
        "anchors_source": ANCHORS_SOURCE,
        "anchors_note": ANCHORS_NOTE,
        "honest_note": J2_HONEST_NOTE,
    }


# ═══════════════════════════════ 自检 ═══════════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检（门禁同源调用）。闭式断言 + 红线断言（顶层不 import 求解器）。"""
    import ast

    res: Dict[str, bool] = {}

    def chk(name: str, cond: bool) -> None:
        res[name] = bool(cond)

    # ① 1q 门错误率：t→0 ⇒ ε→0；且与解析式一致
    chk("① 1q 门错误率 t→0 ⇒ ε→0（退相干极限自洽）",
        gate_error_1q(0.0) == 0.0 and gate_error_1q(1e-30) < 1e-12)

    # ② 1q 错误率随 t 单调升（20ns < 300ns）
    chk("② 1q 错误率随门时长单调升（ε(20ns) < ε(300ns)）",
        gate_error_1q(T_1Q_S) < gate_error_1q(T_IDLE_S))

    # ③ CR 门时间闭式：g_CR=2J²Δ/(α²−Δ²)=−7.111…；t_CR=π/|g_CR|
    cr = cr_gate_time_us()
    chk("③ CR 闭式：g_CR=2J²Δ/(α²−Δ²) 与 t_CR=π/|g_CR| 自洽",
        abs(cr["g_CR_mhz"] - (-7.111111111111111)) < 1e-12
        and abs(cr["t_CR_us"] - math.pi / 7.111111111111111) < 1e-12)

    # ④ CR 参数区无效 ⇒ 抛错（|Δ| ≥ |α|）
    try:
        cr_gate_time_us(delta_mhz=-300.0)
        bad = False
    except ValueError:
        bad = True
    chk("④ CR 参数区守护：|Δ| ≥ |α| ⇒ 抛 ValueError", bad)

    # ⑤ 2q CR 错误率 t→0 ⇒ ε→0
    chk("⑤ 2q CR 错误率 t→0 ⇒ ε→0", cr_gate_error_2q(0.0) == 0.0)

    # ⑥ 残余 ZZ：ζ→0 ⇒ ε→0；φ=π ⇒ ε=4/5
    chk("⑥ 残余 ZZ ζ→0 ⇒ ε→0；φ=π ⇒ ε=4/5（B507 同律）",
        residual_zz_error(0.0) == 0.0
        and abs(residual_zz_error(500.0, 1.0) - 0.8) < 1e-12)

    # ⑦ 读出 SNR / ε 自洽（ε=½erfc(SNR/√2)）
    snr = readout_snr()
    chk("⑦ 读出 ε=½·erfc(SNR/√2) 自洽（与 D-47 同式）",
        abs(readout_eps() - 0.5 * math.erfc(snr / math.sqrt(2.0))) < 1e-15
        and snr > 0.0)

    # ⑧ QPU 预算组装：分量 5 · 次数为正 · p_op_avg == p_cycle_sum/n_ops
    b = qpu_budget()
    chk("⑧ QPU 预算：5 分量 · 次数全正 · p_op_avg ≡ p_cycle_sum/n_ops",
        len(b["components"]) == 5 and all(c["count"] > 0 for c in b["components"])
        and abs(b["p_op_avg"] - b["p_cycle_sum"] / b["n_ops"]) < 1e-15)

    # ⑨ 预算签核二值 ∧ 与每操作余量同号
    chk("⑨ 预算签核二值 ∧ signoff ≡ (p_th − p_op_avg > 0)",
        b["signoff"] in ("ACCEPT", "REJECT")
        and (b["signoff"] == "ACCEPT") == (b["threshold_margin"] > 0.0))

    # ⑩ 默认档欠阈值（ACCEPT）· 反向 ÷10 时长不改变（口径守恒）
    chk("⑩ 默认档预算欠阈值（ACCEPT）· ζ 在限内",
        b["signoff"] == "ACCEPT" and b["zz_within_limit"] is True)

    # ⑪ 谱定理：λ₂(2,2)=2；λ₂(10,10)=2−2cos(π/10)；随规模单调降
    chk("⑪ 谱定理 λ₂=2−2cos(π/max)：λ₂(2,2)=2 · λ₂(10,10) 解析吻合 · 随 max 单调降",
        abs(lambda2_closed_form(2, 2) - 2.0) < 1e-15
        and abs(lambda2_closed_form(10, 10) - (2.0 - 2.0 * math.cos(math.pi / 10.0))) < 1e-15
        and lambda2_closed_form(20, 20) < lambda2_closed_form(10, 10))

    # ⑫ J1↔J2 环：注入口径 = 去极化参数 2ε · orders_below > 0 · p_L 随 d 单调降
    p_phys = depolarizing_parameter(T_1Q_S)
    curve = [logical_error_rate_ideal(p_phys, d) for d in (3, 5, 7, 9)]
    chk("⑫ J1↔J2 环：注入量 = 去极化参数 2ε（非 ε）· p_phys 落阈值下 · p_L 随 d 单调降",
        abs(p_phys - 2.0 * gate_error_1q(T_1Q_S)) < 1e-18
        and orders_below_threshold(p_phys) > 0.0
        and all(curve[i] > curve[i + 1] for i in range(len(curve) - 1)))

    # ⑬ 案例卡组装：4 里程碑 · 5 结论 · 4 缺口 · 顶层 verdict=DESIGN_BUDGET
    #    ∧ gate 口径自洽（逐档累计 == gate_total ∧ sum(gate) == span.gate_checks）
    card = case_card()
    _ms = card["milestones"]
    _cum, _bands_ok = 0, True
    for _m in _ms:
        _cum += _m["gate"]
        if _m["gate_total"] != _cum or not _m["bands"]:
            _bands_ok = False
    chk("⑬ 案例卡组装：4 里程碑 / 5 结论 / 4 缺口 / verdict=DESIGN_BUDGET ∧ gate 口径自洽",
        len(_ms) == 4 and len(card["findings"]) == 5
        and len(card["gaps"]) == 4 and card["verdict"] == "DESIGN_BUDGET"
        and _bands_ok and _cum == card["span"]["gate_checks"])

    # ⑭ 🔴 不伪装实测：verdict 非 PASS/ACCEPT ∧ 诚实边界关键词齐全
    note = card["honest_note"]
    chk("⑭ 不伪装实测：verdict∉{PASS,ACCEPT} ∧ honest_note 含「非流片后实测」/"
        "「非任何 foundry」/「零量子 SDK」/「LLM 不进判决路径」",
        card["verdict"] not in ("PASS", "ACCEPT")
        and "非流片后实测" in note and "非任何 foundry" in note
        and "零量子 SDK" in note and "LLM 不进判决路径" in note)

    # ⑮ 🔴 顶层 import 白名单（ast 真遍历 · 不用源码字符串判定 ⇒ 不误命中 docstring）
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    tree = ast.parse(src)
    mods = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                mods.add(node.module.split(".")[0])
    allowed = {"math", "os", "typing", "__future__"}
    chk("⑮ 顶层 import 白名单（math/os/typing/__future__）—— 零求解器 / 零量子 SDK",
        mods <= allowed)

    # ⑯ 护栏：非法 rows/cols · 非物理 T2 ⇒ 抛 ValueError
    guard = 0
    for fn in (lambda: lambda2_closed_form(0, 4),
               lambda: gate_error_1q(1e-9, T1_s=80e-6, T2_s=200e-6),
               lambda: logical_error_rate_ideal(0.01, 0)):
        try:
            fn()
        except ValueError:
            guard += 1
    chk("⑯ 护栏：rows<1 · 非物理 T2>2T1 · d<1 均抛 ValueError", guard == 3)

    ok_all = all(res.values())
    if verbose:
        for k, v in res.items():
            print("  [%s] %s" % ("PASS" if v else "FAIL", k))
        if not ok_all:
            print("  FAIL 项：%s" % [k for k, v in res.items() if not v])
    return ok_all


if __name__ == "__main__":
    print("J2 QPU 案例卡自检：",
          "ALL PASS" if run_selfchecks(verbose=True) else "FAIL")
