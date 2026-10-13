"""J2 超导 Transmon QPU 征程 · J1↔J2 复利闭环校准（L2 物理比特层 · M0 核心能力层）。

🔴 主权纪律：本模块是**能力验证**模块（功能门禁 `run_j2_qpu_smoke` 覆盖），**不是账本锚**；
纯标准库（`math`）+ 可选懒载入 J1 解码器（`lda_qeda.logical_error_rate`，需 numpy）。
全确定性（解码器路径 seed 固定）。

═══ 复利闭环机制（用户强调的核心）═══
  · **J2 → J1（物理标定）**：J2 物理错误模型（`physical_error_model`）给出真实每门错误率
    p_phys ⇒ 注入 J1 表面码阈值标度/解码器 ⇒ 逻辑错误率曲线从「裸标度界」变「物理标定曲线」。
  · **J1 → J2（设计硬指标）**：J1 阈值 p_th≈1% ⇒ 成为 J2 比特/门设计的**保真度硬指标**：
    J2 门错误率须落阈值下**两数量级**（触发子阈值指数抑制 p_L(d)~A·(p/p_th)^((d+1)/2)）。
  · **设计⇄验证反馈环**：J2 参数 → p_phys → J1 逻辑预算检查 → 未达则 J2 收紧参数，循环至闭环。

🔴🔴 同源声明（诚实边界 · 必读）：
  · `logical_error_rate_ideal` 的阈值标度闭式与 J1 账本锚 **B497** 的 `note` 中同一标度律
    **同式**（B497 的 golden 是其**反解距离** d*，本模块是**正算逻辑错误率** p_L —— 标量不同但依据
    同一标度律）。⇒ **本模块不新增账本锚**（同源体检）。
  · 「J2 物理错误率 → J1 逻辑错误率」的**方法论独立性**天然受限：golden（理想去极化标度闭式）与
    候选（J1 数值解码器 MC）在物理上同属 J1 QEC 框架 ⇒ 该桥**本质是标定/一致性关系**，
    故以**常驻护栏**（`run_j2_qpu_smoke`）承载，而非伪造成「方法学独立锚」（避免虚假独立）。

🔴 诚实边界：p_th / A / 距离 d 为**公认/设计示例量级**（rotated surface code 典型阈值 + 设计前
因子），**非实测 PDK**；本模块只证明「物理层参数 → QEC 逻辑预算」链路自洽，**不作制造/性能宣称**。
"""
from __future__ import annotations

import math

__all__ = [
    "logical_error_rate_ideal",
    "logical_error_rate_decoder",
    "calibration_curve",
    "ideal_vs_physical",
    "orders_below_threshold",
    "j2_hard_target_met",
]

#: 与 J1（`benchmark_defs/part7.py` B497/B504 族）同一组设计示例常数（单一出处对齐）
P_TH_DEFAULT = 0.01      # 表面码阈值（公认量级）
A_SCALE_DEFAULT = 0.03   # 标度律前因子（设计示例）


def logical_error_rate_ideal(p_phys: float, d: int, p_th: float = P_TH_DEFAULT,
                             A: float = A_SCALE_DEFAULT) -> float:
    """J1 理想去极化噪声下逻辑错误率闭式 **p_L(d,p)=A·(p/p_th)^((d+1)/2)**（阈值以下）。

    阈值以上标度失效 ⇒ 保守返回饱和值 1.0（避免外推伪精度）。物理错误率须 0<p<p_th。
    """
    if p_phys <= 0.0 or p_th <= 0.0 or A <= 0.0:
        raise ValueError("p_phys / p_th / A 必须 > 0")
    if int(d) < 1:
        raise ValueError("d 必须 ≥ 1")
    if p_phys >= p_th:
        return 1.0
    return float(A * (p_phys / p_th) ** ((int(d) + 1) / 2.0))


def logical_error_rate_decoder(p_phys: float, d: int, n_shots: int = 2000,
                               seed: int = 1) -> float:
    """J2 物理错误率**注入 J1 端到端解码器**（真实物理层路径 · 蒙特卡洛 · seed 固定）。

    懒载入 `lda_qeda.logical_error_rate.end_to_end_p_logical`（需 numpy）⇒ 保持本模块
    在无 numpy 环境下的其余函数可用。输出为**仿真证据**（③级），只作标度关系交叉检查。
    """
    try:
        from lda_qeda.logical_error_rate import end_to_end_p_logical
    except ImportError:  # 双路兜底（脚本直跑场景）
        import sys
        import os
        _here = os.path.dirname(os.path.abspath(__file__))
        if os.path.dirname(_here) not in sys.path:
            sys.path.insert(0, os.path.dirname(_here))
        from lda_qeda.logical_error_rate import end_to_end_p_logical  # type: ignore
    return float(end_to_end_p_logical(p_phys, int(d), n_shots=int(n_shots), seed=int(seed)))


def calibration_curve(p_phys: float, d_values, p_th: float = P_TH_DEFAULT,
                      A: float = A_SCALE_DEFAULT):
    """物理标定逻辑错误曲线：[(d, p_L(d)) ...]（同一 p_phys 下随距离的指数抑制）。"""
    return [(int(d), logical_error_rate_ideal(p_phys, int(d), p_th, A)) for d in d_values]


def ideal_vs_physical(p_ideal: float, p_phys: float, d: int,
                      p_th: float = P_TH_DEFAULT, A: float = A_SCALE_DEFAULT):
    """同一距离下「理想噪声 p_ideal」vs「J2 物理标定 p_phys」逻辑错误率对照。

    返回 (p_L_ideal, p_L_physical, ratio=p_L_physical/p_L_ideal)；ratio>1 ⇔ 物理层比理想差。
    """
    li = logical_error_rate_ideal(p_ideal, int(d), p_th, A)
    lp = logical_error_rate_ideal(p_phys, int(d), p_th, A)
    r = float(lp / li) if li > 0.0 else float("inf")
    return float(li), float(lp), r


def orders_below_threshold(p_phys: float, p_th: float = P_TH_DEFAULT) -> float:
    """物理错误率位于阈值下方多少个**数量级**：log10(p_th/p_phys)（>0 ⇔ 子阈值）。"""
    if p_phys <= 0.0 or p_th <= 0.0:
        raise ValueError("p_phys / p_th 必须 > 0")
    return float(math.log10(p_th / p_phys))


def j2_hard_target_met(p_phys: float, p_th: float = P_TH_DEFAULT,
                       margin_orders: float = 2.0) -> bool:
    """J1→J2 **硬设计指标**：门错误率须落阈值下 ≥ margin_orders 个数量级（默认 2）。

    触发子阈值指数抑制的前提；未达 ⇒ J2 须收紧 transmon 参数（T1/T2/门时长）后再评估。
    """
    return bool(orders_below_threshold(p_phys, p_th) >= float(margin_orders))
