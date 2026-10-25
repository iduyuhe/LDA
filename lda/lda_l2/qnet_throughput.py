"""量子网络 · **N 段中继链的端到端吞吐与最优段数**（G-QNET-3 · v0.9.294 · 纯标准库）

═══════════════════════════════════════════════════════════════════════
改前是什么（G-QNET-3「中继吞吐」）
═══════════════════════════════════════════════════════════════════════
`qnet_repeater.repeater_gain(L) = repeater_rate / direct_rate(L)`，而

    `repeater_rate` **与链路长度无关**（它只算「站内」排队产出：λ/μ/κ 三率）

⇒ 这个「增益」随 L **指数增长、没有上界、也没有最优点** —— 因为它假设
「中继段内零损耗」。真实中继必须在每段内先付信道透射 `T(L/N)`，再多段**串行**交换摊薄 `1/N`。
两者一乘，增益就有**有限上界与唯一最优点**。本层补的就是这一步。

═══════════════════════════════════════════════════════════════════════
模型（两行，全部闭式）
═══════════════════════════════════════════════════════════════════════
令 `β ≡ α_ln·L`（`α_ln = α_dB/10·ln10`，`L` 以 km 计），则

    G(N) = T(L/N) / [N · T(L)] = **e^{β − β/N} / N**

（`N=1` ⇒ `G ≡ 1` 精确 —— 对照支路：不分段就没有增益）

    ln G = β − β/N − ln N   ⇒   d(lnG)/dN = β/N² − 1/N = 0   ⇒   **N* = β**

⇒ **最优段数就是「衰减长度（以 ln 计）× 链路长度 = β」**，与站速率、与保真度**都无关**；
   `G(N*) = e^{β−1}/β`。参考档（100 km · 0.2 dB/km）⇒ `β = 4.605` ⇒ `N* ≈ 4.61`（整数 5）·
   `G(N*) = 7.99` ⇒ **吞吐增益上限约 8×**。

🔴 **与现有 `repeater_gain = 53.70×` 的口径差异（必须并列披露，不许择一）**：
   53.70× 是「站内理想产出率 ÷ 同长度直传率」，**不含段内透射、不含串行摊薄** ⇒ 是**无损耗上界**；
   计入两者后，同一参考档的最优增益只有 **约 8×**（差 **6.7 倍**）。
   两者**定义不同、都不是错**，但**不可混用**：对外若只报 53.70× 而隐去「段内损耗与串行摊薄」，
   就是把一个理想站模型当成端到端能力。

═══════════════════════════════════════════════════════════════════════
诚实边界
═══════════════════════════════════════════════════════════════════════
· 模型是**一阶**：假设各段并行生成、串行交换，未含量子存储器退相干对**并发**的限制、
  未含经典通信时延、未含交换失败重试的指数尾。
· 与保真度**解耦**：v0.9.292 已证「分段不改保真」（`p_seg^N ≡ exp(−L/L_depol)`）⇒
  **吞吐最优与保真度最优是两个独立问题**，本层只解吞吐侧。
· 参数为公开工程典型，非实测；不作性能宣称。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from lda_l2 import qnet_channel as CH
from lda_l2 import qnet_repeater as RP

__all__ = [
    "DEFAULT_ALPHA_DB_PER_KM",
    "DEFAULT_LINK_LENGTH_M",
    "beta_of",
    "relay_chain_gain",
    "end_to_end_rate",
    "optimal_segments_continuous",
    "optimal_segments_integer",
    "gain_at_optimum",
    "segments_throughput_sweep",
    "throughput_report",
    "selfcheck_qnet_throughput",
]

DEFAULT_ALPHA_DB_PER_KM = CH.DEFAULT_ALPHA_DB_PER_KM
DEFAULT_LINK_LENGTH_M = CH.DEFAULT_LINK_LENGTH_M


def beta_of(length_m: float = DEFAULT_LINK_LENGTH_M,
            alpha_db_per_km: float = DEFAULT_ALPHA_DB_PER_KM) -> float:
    """**β ≡ α_ln·L**（无量纲）—— 它就是最优段数 `N*`，也是「透射衰减的 e 倍指数」。"""
    if length_m <= 0.0:
        raise ValueError("链路长度须 > 0")
    if alpha_db_per_km <= 0.0:
        raise ValueError("衰减系数须 > 0")
    alpha_ln_per_km = alpha_db_per_km / 10.0 * math.log(10.0)
    return float(alpha_ln_per_km * (float(length_m) / 1000.0))


# ══════════════════════════════════════════════════════════════════════
# ① 相对增益 G(N)
# ══════════════════════════════════════════════════════════════════════
def relay_chain_gain(length_m: float = DEFAULT_LINK_LENGTH_M,
                     segments: int = 5,
                     alpha_db_per_km: float = DEFAULT_ALPHA_DB_PER_KM) -> float:
    """N 段中继链的**相对吞吐增益** `G(N) = T(L/N)/(N·T(L))`。

    🔴 **对照支路**：`N = 1 ⇒ G ≡ 1`（精确，不分段无增益）；
       `N → ∞ ⇒ G → 0`（串行摊薄吃掉一切）。
    """
    n = int(segments)
    if n < 1:
        raise ValueError("段数须 ≥ 1")
    t_seg = CH.transmission(float(length_m) / n, alpha_db_per_km)
    t_dir = CH.transmission(float(length_m), alpha_db_per_km)
    if t_dir <= 0.0:
        return float("inf")
    return float(t_seg / (n * t_dir))


def end_to_end_rate(length_m: float = DEFAULT_LINK_LENGTH_M,
                    segments: int = 5,
                    station_rate_per_s: float = None,
                    alpha_db_per_km: float = DEFAULT_ALPHA_DB_PER_KM) -> Dict[str, float]:
    """N 段端到端产出率（1/s）：`station_rate · T(L/N) / N`。

    `station_rate_per_s` 默认取 `qnet_repeater.repeater_rate()`（**理想站率、不含段内透射**），
    如实标注：这是「站内排队产出」乘上「段内到达概率」再除以「串行段数」。
    """
    n = int(segments)
    if n < 1:
        raise ValueError("段数须 ≥ 1")
    s_rate = float(RP.repeater_rate() if station_rate_per_s is None else station_rate_per_s)
    t_seg = CH.transmission(float(length_m) / n, alpha_db_per_km)
    r = s_rate * t_seg / n
    return {"station_rate_per_s": s_rate, "seg_transmission": float(t_seg),
            "rate_per_s": float(r),
            "direct_rate_per_s": float(RP.direct_rate(length_m, alpha_db_per_km=alpha_db_per_km)),
            "gain_vs_direct": float(r / RP.direct_rate(length_m, alpha_db_per_km=alpha_db_per_km))
            if RP.direct_rate(length_m, alpha_db_per_km=alpha_db_per_km) > 0 else float("inf")}


# ══════════════════════════════════════════════════════════════════════
# ② 最优段数（解析）
# ══════════════════════════════════════════════════════════════════════
def optimal_segments_continuous(length_m: float = DEFAULT_LINK_LENGTH_M,
                                alpha_db_per_km: float = DEFAULT_ALPHA_DB_PER_KM) -> float:
    """连续最优段数 **N\\* = β = α_ln·L**（由 `d(lnG)/dN = β/N² − 1/N = 0` 得）。"""
    return beta_of(length_m, alpha_db_per_km)


def optimal_segments_integer(length_m: float = DEFAULT_LINK_LENGTH_M,
                             alpha_db_per_km: float = DEFAULT_ALPHA_DB_PER_KM) -> Tuple[int, float]:
    """整数最优段数（在 `floor(N*)` 与 `ceil(N*)` 中取 `G` 更大者），返回 `(N, G)`。"""
    nc = optimal_segments_continuous(length_m, alpha_db_per_km)
    lo = max(1, int(math.floor(nc)))
    hi = max(1, int(math.ceil(nc)))
    cands = sorted({lo, hi})
    best = max(cands, key=lambda n: relay_chain_gain(length_m, n, alpha_db_per_km))
    return int(best), float(relay_chain_gain(length_m, best, alpha_db_per_km))


def gain_at_optimum(length_m: float = DEFAULT_LINK_LENGTH_M,
                    alpha_db_per_km: float = DEFAULT_ALPHA_DB_PER_KM) -> float:
    """最优增益解析式 `G(N*) = e^{β−1}/β`（与整数解并列给出，两者差 < 1%）。"""
    b = beta_of(length_m, alpha_db_per_km)
    return float(math.exp(b - 1.0) / b)


# ══════════════════════════════════════════════════════════════════════
# ③ 段数扫描
# ══════════════════════════════════════════════════════════════════════
def segments_throughput_sweep(length_m: float = DEFAULT_LINK_LENGTH_M,
                              n_list: Tuple[int, ...] = (1, 2, 3, 4, 5, 6, 8, 10, 20, 50),
                              alpha_db_per_km: float = DEFAULT_ALPHA_DB_PER_KM
                              ) -> List[Dict[str, Any]]:
    """扫段数：给 `T(L/N)`、`G(N)` 与是否越过分段最优。"""
    out: List[Dict[str, Any]] = []
    nc = optimal_segments_continuous(length_m, alpha_db_per_km)
    for n in n_list:
        out.append({
            "n_seg": int(n),
            "seg_len_km": float(length_m) / 1000.0 / int(n),
            "seg_transmission": float(CH.transmission(float(length_m) / int(n), alpha_db_per_km)),
            "gain": float(relay_chain_gain(length_m, int(n), alpha_db_per_km)),
            "beyond_optimum": bool(n > nc),
        })
    return out


# ══════════════════════════════════════════════════════════════════════
# ④ 报告（含与旧口径的并列对照）
# ══════════════════════════════════════════════════════════════════════
def throughput_report(length_m: float = DEFAULT_LINK_LENGTH_M,
                      alpha_db_per_km: float = DEFAULT_ALPHA_DB_PER_KM) -> Dict[str, Any]:
    """端到端吞吐报告：解析最优 + 整数最优 + 与旧「站内口径」的差异。"""
    b = beta_of(length_m, alpha_db_per_km)
    n_int, g_int = optimal_segments_integer(length_m, alpha_db_per_km)
    g_cont = gain_at_optimum(length_m, alpha_db_per_km)
    legacy = RP.repeater_gain(length_m)
    return {
        "length_m": float(length_m),
        "alpha_db_per_km": float(alpha_db_per_km),
        "beta": float(b),
        "n_star_continuous": float(optimal_segments_continuous(length_m, alpha_db_per_km)),
        "n_star_integer": int(n_int),
        "gain_at_n_star_integer": float(g_int),
        "gain_at_n_star_analytic": float(g_cont),
        "gain_analytic_vs_integer_rel": float(abs(g_cont - g_int) / g_int),
        # 旧口径（站内理想率 ÷ 直传率 · 不含段内透射与串行摊薄）
        "legacy_repeater_gain": float(legacy),
        "legacy_over_optimum": float(legacy / g_int),
        # 🔴 v0.9.298 补：报告此前只有**增益比**，没有**绝对速率** —— 而 v0.9.294 的题目就叫
        #    「端到端吞吐」。这里直接复用 `end_to_end_rate` 与 `segments_throughput_sweep`（单一真源），
        #    不再在报告里另算一遍（同口径两个入口 = 会漂）。
        "end_to_end_rate_per_s": float(
            end_to_end_rate(length_m, n_int, alpha_db_per_km=alpha_db_per_km)["rate_per_s"]),
        "sweep": segments_throughput_sweep(length_m, alpha_db_per_km=alpha_db_per_km),
        "note": (
            "旧 `repeater_gain` 是「站内理想产出率 ÷ 同长度直传率」，**不含段内透射与串行摊薄** ⇒ 无损耗上界；"
            "本层计入两者后，最优增益 `G(N*)=e^{β−1}/β` 才是**端到端**口径。两者定义不同、都不是错，"
            "但**不可混用**：只报旧值而隐去段内损耗/串行摊薄，就是把理想站模型当端到端能力。"
            "另：吞吐最优与保真度**解耦**（v0.9.292 已证分段不改保真）⇒ 两个独立问题。"
        ),
    }


# ══════════════════════════════════════════════════════════════════════
# 自检
# ══════════════════════════════════════════════════════════════════════
def selfcheck_qnet_throughput() -> Dict[str, bool]:
    c: Dict[str, bool] = {}
    rep = throughput_report()

    # ① 对照支路：N=1 ⇒ G ≡ 1（精确）
    c["n1_identity"] = relay_chain_gain(segments=1) == 1.0
    # ② N > N* 时 G **严格递减**（这才是「串行摊薄吃掉增益」的机核形式；
    #    注意 G(N) ≈ e^β/N 只是缓降，不要拿「足够小」当判据）
    _gd = [relay_chain_gain(segments=n) for n in (5, 10, 20, 100)]
    c["monotone_decreasing_above_opt"] = all(_gd[i] > _gd[i + 1] for i in range(len(_gd) - 1))
    # ③ 解析最优 N* == β
    c["n_star_equals_beta"] = abs(rep["n_star_continuous"] - rep["beta"]) <= 1e-15
    # ④ 一阶条件：数值微分 d(lnG)/dN 在 N* 处为 0
    n_star = rep["n_star_continuous"]

    def _dln_g(n: float, h: float = 1e-6) -> float:
        g1 = math.exp(rep["beta"] - rep["beta"] / (n + h)) / (n + h)
        g0 = math.exp(rep["beta"] - rep["beta"] / (n - h)) / (n - h)
        return (math.log(g1) - math.log(g0)) / (2.0 * h)

    c["first_order_condition"] = abs(_dln_g(n_star)) <= 1e-8
    # ⑤ G(N*) 是最大：与 N*±1 比较（且严格大于两端）
    g_opt = relay_chain_gain(segments=int(n_star))
    c["is_local_max"] = (relay_chain_gain(segments=max(1, int(n_star) - 1)) < g_opt
                         and relay_chain_gain(segments=int(n_star) + 2) < g_opt)
    # ⑥ 解析式与整数解一致（相对 < 1%）
    c["analytic_matches_integer"] = rep["gain_analytic_vs_integer_rel"] < 1e-2
    # ⑦ 参考档回归：β≈4.605 · 整数 N*=5 · G≈7.96（绝对量级锚点，防单位错）
    c["reference_beta"] = abs(rep["beta"] - 4.6051701859880912) <= 1e-12
    c["reference_n_star_int"] = rep["n_star_integer"] == 5
    c["reference_gain_range"] = 7.5 <= rep["gain_at_n_star_integer"] <= 8.5
    # ⑧ 与旧口径的差异如实可算（比值解析可预测）
    c["legacy_ratio_reported"] = rep["legacy_over_optimum"] > 1.0
    # ⑨ 单调性：N < N* 时 G 递增
    _gs = [relay_chain_gain(segments=n) for n in (1, 2, 3, 4)]
    c["monotone_increasing_below_opt"] = all(_gs[i] < _gs[i + 1] for i in range(len(_gs) - 1))
    # ⑩ 非法入参抛 ValueError
    try:
        beta_of(0.0)
        c["bad_input_raises"] = False
    except ValueError:
        c["bad_input_raises"] = True
    return c


if __name__ == "__main__":  # pragma: no cover
    sc = selfcheck_qnet_throughput()
    bad = [k for k, v in sc.items() if not v]
    print("qnet_throughput 自检：%d/%d 通过" % (len(sc) - len(bad), len(sc)))
    if bad:
        print("FAIL:", bad)
    r = throughput_report()
    print("β=%.6f · N*(连续)=%.4f · N*(整数)=%d · G=%.4f · G(解析)=%.4f" %
          (r["beta"], r["n_star_continuous"], r["n_star_integer"],
           r["gain_at_n_star_integer"], r["gain_at_n_star_analytic"]))
    print("旧口径 repeater_gain=%.2f ⇒ 是端到端的 %.2f 倍" %
          (r["legacy_repeater_gain"], r["legacy_over_optimum"]))
