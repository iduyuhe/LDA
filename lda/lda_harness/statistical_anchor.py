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

import random
import statistics
from typing import Dict, List, Tuple

# ---- 工艺容差（σ，dB 域；公开文献典型量级，发动期 PDK 校准替换） ----
GRATING_SIGMA_DB = 0.30      # 光栅耦合器耦合效率容差
WG_SIGMA_DB_CM = 0.50        # 波导传播损耗容差（dB/cm）
RING_IL_SIGMA_DB = 0.10      # 环形 through 插损容差


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
