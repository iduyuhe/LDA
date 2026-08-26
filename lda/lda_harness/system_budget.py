"""LDA 系统级预算锚（Phase 0 试金石 · Merge-0）。

系统级第一道死标量锚：光链路功率预算（dB 域加法级联）。
物理本质：dB 域中损耗级联 = 加法（线性域乘法的对数像），
链路余量 margin = P_rx − Sens_rx 为纯算术确定量——无统计、无拟合，
任何实现（含链路引擎端到端输出）与此解析值之差必须 ≤ tol。

这是「光量子系统预算锚家族」的第一题（S1）：
  - 光子域：功率预算（dB 加法级联）
  - 量子域：保真度预算（∏fᵢ 乘法级联，对数域同构）——后续 S 题
锚语义：physical_law（确定性算术），LLM 不进判决路径。

诚实边界：有源器件（激光器/探测器）为行为级黑箱参数（文献典型值），
非物理级模型——Phase 0 试金石只验证「预算级联语义」可行，不声称
系统仿真能力（见《系统级探索预案》挑战 1/2）。
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

# ---- 行为级黑箱参数（文献典型值 · 发动期实测校准后升级） ----
# 激光器：光纤耦合输出功率 0 dBm（1 mW，DFB 典型）
LASER_P_TX_DBM = 0.0
# 光栅耦合器：峰值耦合效率 0.5（-3 dB，B6 设计守则锚同源）
GRATING_COUPLING_DB = -3.0
# SOI 波导传播损耗 3.0 dB/cm（CMOS 兼容 SOI 典型量级；
# 厚 SiN 低至 0.087 dB/cm 见实证语料 E-SIN-PL-800——平台依赖，参数化）
WG_LOSS_DB_CM_SOI = 3.0
# 环形 add-drop through 端插损 0.5 dB（文献典型）
RING_THROUGH_IL_DB = -0.5
# 探测器灵敏度 -20 dBm @ 10 Gbps（PIN 典型；APD 可达 -28~-30）
DETECTOR_SENS_DBM = -20.0


def link_budget_cascade(p_tx_dbm: float,
                        stages_db: List[float]) -> float:
    """dB 域预算级联（预算锚核心算子，纯算术）。

    p_tx_dbm : 发射功率 (dBm)
    stages_db: 各级损耗（dB，负值）
    返回接收功率 (dBm)。dB 加法 ≡ 线性乘法——确定性，无随机项。
    """
    p_rx = p_tx_dbm
    for s in stages_db:
        p_rx += s
    return p_rx


def budget_margin_db(p_rx_dbm: float, sens_dbm: float) -> float:
    """链路余量 = 接收功率 − 灵敏度（dB）。≥0 闭合（正余量），<0 断链。"""
    return p_rx_dbm - sens_dbm


def s1_power_budget_margin_dB(
        p_tx_dbm: float = LASER_P_TX_DBM,
        n_gratings: int = 2,
        grating_db: float = GRATING_COUPLING_DB,
        wg_length_cm: float = 1.0,
        wg_loss_db_cm: float = WG_LOSS_DB_CM_SOI,
        ring_il_db: float = RING_THROUGH_IL_DB,
        detector_sens_dbm: float = DETECTOR_SENS_DBM) -> float:
    """S1 · WDM 链路功率预算余量（系统级第一锚）。

    链路：激光器 → 光栅耦合(入) → 波导(1cm) → 环形 through → 光栅耦合(出) → 探测器

    golden（解析）：margin = p_tx + n·grating + α·L + ring_IL − sens
    默认参数：0 + 2×(−3) + (−3)×1 + (−0.5) − (−20) = **10.5 dB**

    判决：|candidate − golden| ≤ tol（tol=0.01，纯算术必须精确）。

    符号约定：grating_db/ring_il_db 为负 dB 增量；wg_loss_db_cm 为**正数损耗
    系数**（dB/cm 惯例），级联时取负号入 stages——损耗必须使 P_rx 递减
    （smoke 单调性检查曾抓到此处符号 bug，防自证门禁的价值实证）。
    """
    stages = ([grating_db] * int(n_gratings)
              + [-abs(wg_loss_db_cm) * wg_length_cm, ring_il_db])
    p_rx = link_budget_cascade(p_tx_dbm, stages)
    return round(budget_margin_db(p_rx_dbm=p_rx, sens_dbm=detector_sens_dbm), 6)


def budget_breakdown(params: Dict[str, float]) -> List[Tuple[str, float]]:
    """预算分解（报告用：逐级贡献，人可读）。"""
    p_tx = float(params.get("p_tx_dbm", LASER_P_TX_DBM))
    n_g = int(params.get("n_gratings", 2))
    g_db = float(params.get("grating_db", GRATING_COUPLING_DB))
    L = float(params.get("wg_length_cm", 1.0))
    a = float(params.get("wg_loss_db_cm", WG_LOSS_DB_CM_SOI))
    ring = float(params.get("ring_il_db", RING_THROUGH_IL_DB))
    rows = [("激光器 P_tx", p_tx)]
    rows += [("光栅耦合 ×%d" % (i + 1), g_db) for i in range(n_g)]
    rows += [("波导 %.2f cm" % L, a * L), ("环形 through", ring)]
    rows += [("接收功率 P_rx", p_tx + n_g * g_db + a * L + ring),
             ("探测器灵敏度", float(params.get("detector_sens_dbm",
                                                DETECTOR_SENS_DBM)))]
    return rows


# ---------------------------------------------------------------------------
# S2 · WDM 信道频率规划（无碰撞锚）
# ---------------------------------------------------------------------------
def s2_channel_plan_no_collision(
        f_center_thz: float = 193.4,   # C 波段中心 (THz)
        channel_spacing_ghz: float = 100.0,
        n_channels: int = 4,
        filter_bw_ghz: float = 50.0) -> float:
    """S2 · 信道频率规划无碰撞余量（GHz）。

    golden = 最小信道间隔余量 = spacing − filter_bw（>0 无碰撞）。
    默认：100 − 50 = 50 GHz。
    判决：|candidate − golden| ≤ tol。
    """
    return round(channel_spacing_ghz - filter_bw_ghz, 6)


# ---------------------------------------------------------------------------
# S3 · OSNR 解析预算（ASE 级联）
# ---------------------------------------------------------------------------
def s3_osnr_budget(
        p_sig_dbm: float = 0.0,       # 信号功率 (dBm)
        n_amp: int = 1,               # 放大器级数
        nf_db: float = 5.0,           # 每级噪声系数 (dB)
        bw_ghz: float = 50.0) -> float:
    """S3 · OSNR 预算（dB）：OSNR = P_sig − 10·log10(h·ν·bw·N·F)。

    确定性解析（ASE 噪声功率谱）：P_ase = h·ν·bw·(N·F)，hν=0.8eV@1550nm。
    golden（默认）：P_sig − P_ase_dBm。
    """
    h = 6.626e-34
    nu = 3.0e8 / (1.55e-6)
    p_ase_w = h * nu * (bw_ghz * 1e9) * (n_amp * 10.0 ** (nf_db / 10.0))
    p_ase_dbm = 30.0 + 10.0 * math.log10(p_ase_w)
    return round(p_sig_dbm - p_ase_dbm, 6)


# ---------------------------------------------------------------------------
# S4 · 量子保真度预算（∏fᵢ 乘法级联，对数域同构）
# ---------------------------------------------------------------------------
def s4_fidelity_budget(
        fidelities: tuple = (0.999, 0.999, 0.999, 0.998, 0.999),
        f_target: float = 0.995) -> float:
    """S4 · 量子门保真度预算余量：F_total = ∏fᵢ（乘法级联）。

    对数域：log F_total = Σ log fᵢ（与 dB 域同构——洞察 A 落地）。
    返回余量 = F_total − f_target（>0 满足预算）。
    """
    f_total = 1.0
    for f in fidelities:
        f_total *= f
    return round(f_total - f_target, 8)


# ---------------------------------------------------------------------------
# S5 · 最坏情况功率预算（工艺角最坏，确定性）
# ---------------------------------------------------------------------------
def s5_worst_case_budget(
        p_tx_dbm: float = 0.0,
        il_worst_db: float = 10.0,    # 最坏损耗合计（SS 角）
        sens_dbm: float = -20.0) -> float:
    """S5 · 最坏情况预算余量（dB）：margin_worst = P_tx − IL_worst − Sens。

    确定性最坏情况（漂移带的下界），与 Merge-1b 角扫语义同构。
    """
    return round(p_tx_dbm - il_worst_db - sens_dbm, 6)


# ---------------------------------------------------------------------------
# S6 · 探测器灵敏度预算（光电流 vs 阈值，黑箱收口）
# ---------------------------------------------------------------------------
def s6_detector_margin(
        p_rx_dbm: float = -8.5,       # 接收功率 (dBm)
        sens_dbm: float = -20.0) -> float:
    """S6 · 探测器灵敏度余量（dB）：margin = P_rx − Sens（>0 可探测）。"""
    return round(p_rx_dbm - sens_dbm, 6)
