"""LDA 系统级统计锚（Phase 3 · 专投区第一刀 · 蒙特卡洛 + 分布锚）。

背景（《系统级探索预案》挑战 5 / 洞察 B）：
  确定性锚回答「通不通」，统计锚回答「多稳」。系统级核心指标
  （误码率、良率、最坏情况）本质是分布，不是单点——Phase 3 引入
  蒙特卡洛采样 + 分布统计量判决。

红线（洞察 B · 严格保持）：
  随机在采样，判决在统计量的确定性函数：
    - 采样：参数加高斯容差扰动（random 模块，固定种子可控）
    - 判决：|E[margin] − 解析 margin| ≤ tol 与 p5 方向断言，
            全部是标准库算术——LLM 不进判决路径，在随机世界依然成立。

实现约束：纯标准库（random/statistics），零第三方依赖——
与项目「核心零依赖优雅降级」铁律一致（FDTD 内核同纪律）。

Phase 3 最小切片（纵向贯通律）：S7 = S1 功率预算的统计延伸——
同一链路、同一解析 golden，新增「工艺容差 → margin 分布」，
确定性前驱（S1）与统计延伸（S7）在同一题族内无缝衔接。
"""
from __future__ import annotations

import math
import random
import statistics
from typing import Dict, List, Tuple

# ---- 工艺容差（σ，dB 域；公开文献典型量级，发动期 PDK 校准替换） ----
GRATING_SIGMA_DB = 0.30      # 光栅耦合器耦合效率容差
WG_SIGMA_DB_CM = 0.50        # 波导传播损耗容差（dB/cm）
RING_IL_SIGMA_DB = 0.10      # 环形 through 插损容差

# 标准正态 5% 分位 |z|（单侧 5% 最坏情况：p5 = μ − z·σ）
# scipy.stats.norm.ppf(0.05) = −1.6448536269514722
GAUSS_Z05 = 1.6448536269514722


def monte_carlo_margins(
        p_tx_dbm: float = 0.0,
        n_gratings: int = 2,
        grating_db: float = -3.0,
        wg_length_cm: float = 1.0,
        wg_loss_db_cm: float = 3.0,
        ring_il_db: float = -0.5,
        detector_sens_dbm: float = -20.0,
        sigma_db: float = 0.5,
        n_samples: int = 2000,
        seed: int = 42) -> List[float]:
    """蒙特卡洛采样：链路各级损耗加高斯容差扰动，返回 margin 样本列表。

    物理语义：工艺漂移使每级损耗在名义值附近高斯分布（σ 为工艺容差），
    margin = P_tx − Σloss_i − Sens 为纯算术（与 S1 同式）。
    高斯对称扰动下 E[Σloss_i] = Σ名义值 → E[margin] ≈ 解析 margin，
    但 p5 低于解析值（损耗增大方向 margin 变差）——分布携带
    「最坏情况」信息，正是确定性锚缺失的维度。
    """
    rng = random.Random(seed)
    margins = []
    for _ in range(n_samples):
        total = 0.0
        # 损耗统一以「负数 dB」入级联（与 S1 语义一致）：
        # grating_db/ring_il_db 参数本身为负数（耦合/插损约定），
        # wg_loss_db_cm 为正数（传播损耗约定）须取负——历史参数约定
        # 不一致，统计锚的「均值收敛于解析值」自洽检查当场暴露。
        for _ in range(int(n_gratings)):
            total += grating_db + rng.gauss(0.0, GRATING_SIGMA_DB)
        total += -(wg_loss_db_cm + rng.gauss(0.0, WG_SIGMA_DB_CM)) * wg_length_cm
        total += ring_il_db + rng.gauss(0.0, RING_IL_SIGMA_DB)
        margins.append(p_tx_dbm + total - detector_sens_dbm)
    return margins


def margin_stats(margins: List[float]) -> Dict[str, float]:
    """分布统计量（判决输入，确定性函数）。

    mean：样本均值（收敛于解析值）；p5：5% 分位数（最坏情况下界）；
    p95：95% 分位数；std：样本标准差。
    """
    mean = statistics.fmean(margins)
    p5 = statistics.quantiles(margins, n=20)[0]   # 5% 分位
    p95 = statistics.quantiles(margins, n=20)[18]  # 95% 分位
    return {"mean": round(mean, 6), "p5": round(p5, 6),
            "p95": round(p95, 6), "std": round(statistics.pstdev(margins), 6),
            "n": len(margins)}


def s7_statistical_margin_anchor(
        p_tx_dbm: float = 0.0,
        n_gratings: int = 2,
        grating_db: float = -3.0,
        wg_length_cm: float = 1.0,
        wg_loss_db_cm: float = 3.0,
        ring_il_db: float = -0.5,
        detector_sens_dbm: float = -20.0,
        n_samples: int = 2000,
        seed: int = 42) -> float:
    """S7 golden：固定种子下蒙特卡洛 margin 均值（确定性判决量）。

    语义：给定工艺容差与固定种子，margin 分布均值是唯一确定值——
    任何人重跑得到同一数字（可复现性 = 统计锚的判决前提）。
    判决（harness tol）：|candidate − golden| ≤ tol 即 PASS。
    """
    margins = monte_carlo_margins(
        p_tx_dbm=p_tx_dbm, n_gratings=n_gratings, grating_db=grating_db,
        wg_length_cm=wg_length_cm, wg_loss_db_cm=wg_loss_db_cm,
        ring_il_db=ring_il_db, detector_sens_dbm=detector_sens_dbm,
        n_samples=n_samples, seed=seed)
    return round(statistics.fmean(margins), 6)


def distribution_report() -> Dict[str, object]:
    """完整分布报告（smoke/WebUI 消费）：解析值 + 分布统计量 + 方向性。

    方向性断言：p5 < 解析 margin < p95（损耗随机增大时 margin 变差）——
    分布携带确定性锚缺失的「最坏情况」维度。
    """
    margins = monte_carlo_margins()
    st = margin_stats(margins)
    analytic = 10.5  # S1 解析 margin（0 − 6 − 3 − 0.5 + 20）
    return {"analytic_margin_dB": analytic,
            "stats": st,
            "direction_ok": st["p5"] < analytic < st["p95"],
            "mean_converged": abs(st["mean"] - analytic) < 0.15,
            "note": ("蒙特卡洛 N=%d 种子固定——均值收敛于解析 10.5dB，"
                     "p5 携带最坏情况下界（确定性锚缺失的维度）；"
                     "判决全部为统计量算术，LLM 不进路径。"
                     % st["n"])}


# ---------------------------------------------------------------------------
# S8 · OSNR 统计锚（S3 的统计延伸——模板复用验证：加题从开发变填表）
# ---------------------------------------------------------------------------
# 信号功率容差（激光器功率漂移，dB）与噪声系数容差（放大器，dB）
LASER_PWR_SIGMA_DB = 0.50
NF_SIGMA_DB = 0.30


def monte_carlo_osnr(
        p_sig_dbm: float = 0.0,
        n_amp: int = 1,
        nf_db: float = 5.0,
        bw_ghz: float = 50.0,
        n_samples: int = 2000,
        seed: int = 7) -> List[float]:
    """蒙特卡洛 OSNR 采样：信号功率与噪声系数加高斯容差扰动。

    OSNR = P_sig − 10·log10(h·ν·bw·(N_amp·F))（S3 同式）。
    - P_sig 扰动对称（激光器漂移）→ E[OSNR] 线性保持 ≈ 解析值；
    - F 扰动经 10·log10 非线性（log 凹）→ E[log F] < log(E[F])
      （Jensen 偏差）→ 均值系统性略低于解析值——物理真实，
      判决用宽容差 + 方向断言（E[OSNR] ≤ 解析值），不声称无偏。
    """
    h = 6.626e-34
    nu = 3.0e8 / (1.55e-6)
    rng = random.Random(seed)
    osnrs = []
    for _ in range(n_samples):
        p_sig = p_sig_dbm + rng.gauss(0.0, LASER_PWR_SIGMA_DB)
        f_lin = 10.0 ** ((nf_db + rng.gauss(0.0, NF_SIGMA_DB)) / 10.0)
        p_ase_w = h * nu * (bw_ghz * 1e9) * (n_amp * f_lin)
        p_ase_dbm = 30.0 + 10.0 * math.log10(p_ase_w)
        osnrs.append(p_sig - p_ase_dbm)
    return osnrs


def s8_statistical_osnr_anchor(
        p_sig_dbm: float = 0.0,
        n_amp: int = 1,
        nf_db: float = 5.0,
        bw_ghz: float = 50.0,
        n_samples: int = 2000,
        seed: int = 7) -> float:
    """S8 golden：固定种子下 OSNR 分布均值（确定性判决量）。"""
    return round(statistics.fmean(monte_carlo_osnr(
        p_sig_dbm=p_sig_dbm, n_amp=n_amp, nf_db=nf_db, bw_ghz=bw_ghz,
        n_samples=n_samples, seed=seed)), 6)


# ---------------------------------------------------------------------------
# v0.9.29（T-3）：S7/S8 换指标 均值 → p5（最坏情况下界）
# ---------------------------------------------------------------------------
# 🔴 为什么换：原均值锚只比「分布中心」，与确定性锚（S1/S3）语义重叠、且
# 落在自证桩候选下时零验证价值（mean 是解析值 10.5/46.93，闭式即可得，
# 不构成独立验证）。确定性锚缺失的真正维度是「最坏情况」——分布尾部 p5。
# note 早就承认「p5=9.41/45.93 携带最坏情况下界」却一直没用上。
#
# 🔴 方法学独立性（与蒙特卡洛 golden 完全独立）：
#   S7 margin = p_tx + Σ(−loss_i) − Sens，各 loss_i 是**独立高斯**扰动
#     ⇒ margin 是独立正态之和 ⇒ **严格高斯**，μ/σ 闭式可得。
#   S8 OSNR = p_sig − 10·log10(h·ν·bw·N·F)，F=10^((nf+δ)/10)
#     ⇒ 10·log10(F) = nf + δ（恰为高斯！δ~N(0,σ_nf)），
#     ⇒ OSNR = (p_sig − 30 − 10log10(hνbwN) − nf) + (ξ − δ)，
#       ξ~N(0,σ_laser)、δ~N(0,σ_nf) 均高斯 ⇒ OSNR **严格高斯**。
#   故两题分布都是精确高斯 ⇒ p5 = μ − z·σ 是**闭式精确值**（非近似），
#   与「固定种子蒙特卡洛抽样 + 经验分位」是**两种不同算法**：
#     若分布非高斯（重尾/偏态），MC p5 与高斯 p5 会偏离 tol ⇒ 本锚能抓错。
#   这正是真可证伪验证（自证桩 |diff|≡0 不携带任何信息）。
#
# ⚠️ 已知边界（与结论一起读）：高斯 p5 候选对分布「高斯性」本身不做检验，
#   它验证的是「给定高斯性假设下，最坏情况 p5 的闭合值是否与抽样一致」。
#   分布是否真高斯由 s7/s8 的 `distribution_report` 方向性断言 + 实测语料背书，
#   不在本题死标量判决内。

def s7_gaussian_moments(
        p_tx_dbm: float = 0.0,
        n_gratings: int = 2,
        grating_db: float = -3.0,
        wg_length_cm: float = 1.0,
        wg_loss_db_cm: float = 3.0,
        ring_il_db: float = -0.5,
        detector_sens_dbm: float = -20.0
        ) -> Tuple[float, float]:
    """S7 闭式高斯矩（候选侧）：μ/σ 由组件容差解析叠加，不碰任何采样。

    margin = p_tx + (n_g·grating_db − wg_loss·wg_len + ring_il) − Sens。
    各损耗项独立高斯 ⇒ 方差直接相加（独立正态线性组合仍正态）：
      var = n_g·σ_grating² + (σ_wg·wg_len)² + σ_ring²
    σ_grating/σ_wg/σ_ring 为模块级工艺容差常量（与 monte_carlo_margins 同源）。
    """
    mu = (p_tx_dbm
          + (n_gratings * grating_db - wg_loss_db_cm * wg_length_cm + ring_il_db)
          - detector_sens_dbm)
    var = (n_gratings * GRATING_SIGMA_DB ** 2
           + (WG_SIGMA_DB_CM * wg_length_cm) ** 2
           + RING_IL_SIGMA_DB ** 2)
    return mu, math.sqrt(var)


def s8_gaussian_moments(
        p_sig_dbm: float = 0.0,
        n_amp: int = 1,
        nf_db: float = 5.0,
        bw_ghz: float = 50.0
        ) -> Tuple[float, float]:
    """S8 闭式高斯矩（候选侧）：OSNR 高斯性的闭式 μ/σ（见上方推导）。

    μ = p_sig − 30 − 10·log10(h·ν·bw·N) − nf
    σ = sqrt(σ_laser² + σ_nf²)   （ξ 与 δ 独立正态）
    """
    h = 6.626e-34
    nu = 3.0e8 / (1.55e-6)
    mu = (p_sig_dbm - 30.0
          - 10.0 * math.log10(h * nu * (bw_ghz * 1e9) * n_amp)
          - nf_db)
    sigma = math.sqrt(LASER_PWR_SIGMA_DB ** 2 + NF_SIGMA_DB ** 2)
    return mu, sigma


def s7_statistical_margin_p5_anchor(
        p_tx_dbm: float = 0.0,
        n_gratings: int = 2,
        grating_db: float = -3.0,
        wg_length_cm: float = 1.0,
        wg_loss_db_cm: float = 3.0,
        ring_il_db: float = -0.5,
        detector_sens_dbm: float = -20.0,
        n_samples: int = 2000,
        seed: int = 42) -> float:
    """S7 golden（v0.9.29 · T-3）：固定种子下蒙特卡洛 margin 分布 5% 分位。

    语义：最坏情况下界——只有 5% 的工艺漂移抽样会让 margin 低于此值。
    判决（harness tol=0.15）：|cand(闭式高斯 p5) − golden(本函数)| ≤ tol。
    """
    margins = monte_carlo_margins(
        p_tx_dbm=p_tx_dbm, n_gratings=n_gratings, grating_db=grating_db,
        wg_length_cm=wg_length_cm, wg_loss_db_cm=wg_loss_db_cm,
        ring_il_db=ring_il_db, detector_sens_dbm=detector_sens_dbm,
        n_samples=n_samples, seed=seed)
    return margin_stats(margins)["p5"]


def s8_statistical_osnr_p5_anchor(
        p_sig_dbm: float = 0.0,
        n_amp: int = 1,
        nf_db: float = 5.0,
        bw_ghz: float = 50.0,
        n_samples: int = 2000,
        seed: int = 7) -> float:
    """S8 golden（v0.9.29 · T-3）：固定种子下 OSNR 分布 5% 分位（最坏情况）。"""
    return margin_stats(monte_carlo_osnr(
        p_sig_dbm=p_sig_dbm, n_amp=n_amp, nf_db=nf_db, bw_ghz=bw_ghz,
        n_samples=n_samples, seed=seed))["p5"]


def osnr_distribution_report() -> Dict[str, object]:
    """OSNR 分布报告：解析值 + 统计量 + Jensen 方向断言。"""
    osnrs = monte_carlo_osnr()
    st = margin_stats(osnrs)
    # 解析 OSNR（S3 默认 46.93dB）
    h = 6.626e-34
    nu = 3.0e8 / (1.55e-6)
    p_ase_w = h * nu * (50.0e9) * (10.0 ** (5.0 / 10.0))
    analytic = 0.0 - (30.0 + 10.0 * math.log10(p_ase_w))
    return {"analytic_osnr_dB": round(analytic, 3),
            "stats": st,
            # Jensen 偏差：均值 ≤ 解析（log 凹），方向物理正确
            "jensen_ok": st["mean"] <= analytic + 0.02,
            "note": ("OSNR 统计锚：P_sig 对称扰动线性保持 + NF 非线性 Jensen "
                     "偏差（均值略低物理真实）；判决统计量算术，LLM 不进路径。")}


def convergence_scan(ns: Tuple[int, ...] = (500, 1000, 2000, 4000),
                     seed: int = 42) -> Dict[str, float]:
    """蒙特卡洛收敛性扫描：N 增大 → 均值收敛带（统计锚可信度前提）。

    返回各 N 的均值与最大收敛偏移（N=4000 与 N=500 的差）——
    采样充分性死标量（若偏移 > tol 说明 N 不足，判决不可信）。
    """
    means = {}
    for n in ns:
        means[n] = s7_statistical_margin_anchor(n_samples=n, seed=seed)
    spread = max(means.values()) - min(means.values())
    return {"means": means, "spread": round(spread, 6),
            "converged": spread < 0.05}
