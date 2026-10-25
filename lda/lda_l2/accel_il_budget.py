"""IL（插入损耗）对光子矩阵乘法精度的影响 —— 把「IL 只进功率预算、不进精度」这个论证做成可复算模型。

🔴 为什么要建模（accel 案例卡 G-A3）：卡上写着「插入损耗只进功率预算、不进精度」，
   理由是「均匀衰减可被差分检测 / 归一化消除」，但**这个论证从未建模**（只写在 detail 里）。

🔴 建模后必须披露的前提（本模块的核心结论）：
   · IL **按模式均匀**时，标量归一化即可精确恢复（误差 ~1e-16）；
   · 但本卡的 `per_mode_db = 31.2 dB` 是**最坏模**口径（穿越深度 13 × 2.4 dB/级），
     各模穿越深度不同 ⇒ IL **按模式非均匀** ⇒ 全局归一化会留下**百分级**误差；
   · **逐模标定**才能恢复；代价是标定精度本身成为新的误差源（本模块给出 dB → 相对误差的换算）。
   ⇒ 结论不是「论证错」，而是「**论证缺了前提**」：逐模标定是「IL 不损精度」的**必要条件**。

本模块纯 stdlib（`math` + `random.Random(seed)`），无时间戳、无外部数据 ⇒ 确定性可复算。
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Sequence, Tuple

__all__ = ["il_precision_report", "depth_profile", "DB_TO_NEPER"]

#: 1 dB 的幅度比换算（功率 dB → 幅度倍数 = 10**(dB/20)）
DB_TO_NEPER = math.log(10.0) / 20.0


def _orthogonal(n: int, seed: int) -> List[List[float]]:
    """用 Gram-Schmidt 造一个确定性的 n×n 实正交阵（模拟无损酉网格的输出映射）。

    只用来给「输入向量 → 输出模式」一个真实的混模结构；IL 本身是逐模实标量缩放，
    所以用实正交阵不影响结论，却省掉了复数运算。
    """
    rng = random.Random(seed)
    cols: List[List[float]] = []
    for _ in range(n):
        v = [rng.gauss(0.0, 1.0) for _ in range(n)]
        for c in cols:                      # 逐个减掉已正交化列的分量
            dot = sum(a * b for a, b in zip(v, c))
            v = [a - dot * b for a, b in zip(v, c)]
        norm = math.sqrt(sum(a * a for a in v))
        if norm < 1e-12:                    # 退化时换一个方向（概率极低，仍保证确定性）
            v = [1.0 if i == len(cols) else 0.0 for i in range(n)]
            norm = 1.0
        cols.append([a / norm for a in v])
    # 列 → 行（Q 的每行是一个输出模式对各输入的系数）
    return [[cols[j][i] for j in range(n)] for i in range(n)]


def depth_profile(n_mode: int, worst_depth: int) -> List[int]:
    """各模的 MZI 穿越深度：最坏模 = `worst_depth`，依次递减、下限 1。

    🔴 这一条是关键：卡上的 `per_mode_db` 用的是**最坏模**深度 ⇒ 各模深度**不同**
    ⇒ IL 必然是**按模式非均匀**的。任何「均匀衰减」论证都必须先承认这一点。
    """
    return [max(1, worst_depth - 2 * i) for i in range(n_mode)]


def _rel_err(approx: Sequence[float], ideal: Sequence[float]) -> float:
    num = math.sqrt(sum((a - b) ** 2 for a, b in zip(approx, ideal)))
    den = math.sqrt(sum(b * b for b in ideal))
    return num / den if den > 0 else 0.0


def il_precision_report(
    *,
    n_mode: int = 8,
    per_mzi_loss_db: float = 2.4,
    worst_depth: int = 13,
    seed: int = 20261025,
    drift_db_sweep: Tuple[float, ...] = (0.0, 0.1, 0.5, 1.0),
) -> Dict[str, Any]:
    """返回 IL → 精度 的三种标定策略对比（全部相对误差，无量纲）。"""
    q = _orthogonal(n_mode, seed)
    rng = random.Random(seed + 1)
    x = [rng.gauss(0.0, 1.0) for _ in range(n_mode)]
    nx = math.sqrt(sum(v * v for v in x))
    x = [v / nx for v in x]
    ideal = [sum(q[i][j] * x[j] for j in range(n_mode)) for i in range(n_mode)]

    depths = depth_profile(n_mode, worst_depth)
    # 幅度透过率 t_i = 10 ** (-per_mzi * depth_i / 20)
    t = [10.0 ** (-per_mzi_loss_db * d / 20.0) for d in depths]

    # ── ① IL 均匀（所有模同深度）：标量归一化即可精确恢复 ──
    t_uni = 10.0 ** (-per_mzi_loss_db * worst_depth / 20.0)
    y_uni = [t_uni * v for v in ideal]
    err_uniform = _rel_err([v / t_uni for v in y_uni], ideal)

    # ── ② IL 按模式非均匀（卡上的真实口径）：只用**一个**标量归一化 ──
    y_nu = [t[i] * ideal[i] for i in range(n_mode)]
    # 🔴 LS 标量：minimize ‖alpha·y − ideal‖ ⇒ alpha = <y, ideal> / <y, y>
    #    （曾写成 /<ideal,ideal> ⇒ 均匀 IL 也被判成 99.9% 误差 —— 分母用错了对象）
    alpha = (sum(a * b for a, b in zip(y_nu, ideal))
             / sum(a * a for a in y_nu))
    err_global = _rel_err([alpha * v for v in y_nu], ideal)

    # ── ③ 逐模标定（每模各自的 t_i 被标出来并除掉）：应恢复到机器精度 ──
    err_per_mode = _rel_err([y_nu[i] / t[i] for i in range(n_mode)], ideal)

    # ── ④ 逐模标定 + 标定漂移：漂移 δ dB ⇒ 残余 ≈ 10**(δ/20) - 1 ──
    drift = []
    for d_db in drift_db_sweep:
        rr = random.Random(seed + 2)
        errs = []
        for _ in range(64):                     # 多次抽样取 RMS，避免单次偶然
            cal = [t[i] * 10.0 ** (rr.uniform(-d_db, d_db) / 20.0) for i in range(n_mode)]
            errs.append(_rel_err([y_nu[i] / cal[i] for i in range(n_mode)], ideal))
        drift.append({
            "drift_db_p2p": d_db,
            "rel_err_rms": math.sqrt(sum(e * e for e in errs) / len(errs)),
            "rel_err_max": max(errs),
            "analytic_rms": math.sqrt(
                sum(((10.0 ** (u / 20.0) - 1.0) ** 2) for u in
                    [(-d_db + 2 * d_db * k / 63.0) for k in range(64)]) / 64.0),
        })

    loss_span_db = 20.0 * math.log10(t[-1] / t[0])      # 跨模损耗跨度（正数）
    # 剖面敏感性：卡片只钉住**最坏模**深度，各模剖面属模型假设 ⇒ 给出两种替代剖面的残差
    profiles = {
        "worst_only_uniform": [worst_depth] * n_mode,                      # 全模同深度（=均匀 IL）
        "linear_descent": depths,                                          # 本模块默认
        "mild_descent": [max(1, worst_depth - i // 2) for i in range(n_mode)],
    }
    sensitivity = []
    for name, dp in profiles.items():
        tt = [10.0 ** (-per_mzi_loss_db * d / 20.0) for d in dp]
        yy = [tt[i] * ideal[i] for i in range(n_mode)]
        al = (sum(a * b for a, b in zip(yy, ideal)) / sum(a * a for a in yy))
        sensitivity.append({
            "profile": name,
            "depth_profile": dp,
            "span_db": 20.0 * math.log10(max(tt) / min(tt)),
            "global_norm_rel_err": _rel_err([al * v for v in yy], ideal),
            "per_mode_cal_rel_err": _rel_err([yy[i] / tt[i] for i in range(n_mode)], ideal),
        })
    return {
        "n_mode": n_mode,
        "depth_profile": depths,
        "per_mzi_loss_db": per_mzi_loss_db,
        "mode_loss_db": [per_mzi_loss_db * d for d in depths],
        "loss_span_db_across_modes": loss_span_db,
        "uniform_il_rel_err": err_uniform,
        "global_norm_rel_err": err_global,
        "per_mode_cal_rel_err": err_per_mode,
        "drift": drift,
        "profile_sensitivity": sensitivity,
        "verdict": (
            "IL 均匀 ⇒ 标量归一化足够；IL 按模式非均匀 ⇒ **必须逐模标定**"
            "（本卡 per_mode_db 是最坏模口径 ⇒ 天然非均匀）"
        ),
        "basis_note": (
            "误差为 ‖近似 − 理想‖₂ / ‖理想‖₂；IL 取幅度透过率 10^(−dB/20)；"
            "网格用确定性实正交阵模拟混模，IL 为逐模实标量 ⇒ 与酉/实无本质差别。"
            "🔴 **各模穿越深度剖面是本模块的假设**（卡片只钉住最坏模 13 级）⇒ "
            "`profile_sensitivity` 给出三种剖面；**结论对剖面稳健，量级随之变化**。"
        ),
        "noise_note": (
            "🔴 本模型只回答「IL 是否改变**归一化后的相对精度**」；"
            "IL 抬高**噪声底**（67.2 dB 总损 ⇒ 光功率降约 5.2e6 倍）导致绝对 SNR 下降，"
            "那是**功率预算**问题，不在本函数范围 —— 两件事不能互相替代。"
        ),
    }
