# -*- coding: utf-8 -*-
"""J5 量子网络与接口征程 · **M2 能力层：量子中继 / 存储窗与产出计数**（`qnet_repeater`）。

定位：M0（`qnet_channel` + `qnet_distribution`）解决**分发侧**、M1（`qnet_source`）解决**源侧**；
      本层解决**中继侧**「链路被切成 N 段后，单位时间能真正产出多少次交换」——
      即「**存储时间何时成为瓶颈**」（缺口 **G-QNET-3**）。这是量子网络区别于长光纤直连的
      **根本工程理由**：中继不是把损耗变小，而是把「指数衰减」换成「对存储时间的竞争」。

物理链（四环）：
  ① 存储存活     `S(t) = exp(−t/T_mem)`（**存储窗因子**；章程要求的 `∫e^{−t/T_mem}dt` 落点）
  ② 交换保真递推 `F' = (1 + 3·p₁p₂)/4`（Werner 族双对交换 · Bell 对角封闭闭式）
  ③ 期望交换产出 `N_swap(T) = κλ/(γ−λ)·[(1−e^{−λT})/λ − (1−e^{−γT})/γ]`（γ=μ+κ ·
     λ=1/T_gen · μ=1/T_mem · κ=1/T_swap）—— 生成窗 ⊗ 存储窗 **嵌套卷积**
  ④ 产出率/增益  `R = N_swap/T_obs`；增益 = 与**同长度直传**产出率之比（纯比值 · 见避让登记）

🔴 **与 `passivity` 锚（B19「无源链路 无增益 · max|T|≤1」）物理地位不同（章程 R4 声明义务）**：
  B19 判的是**光子链路传递矩阵**不得被放大（被动网络 |T|≤1，即「有增益 = FAIL」）；
  本层的 ④ 是**中继站的产出计数之比**（不同物理量纲、不同判决语义）——
  「中继增益 > 1」在此处**不表示任何能量增益**，只表示「单位时间产出更多可用纠缠对」。
  二者不共享标量、不共享判据方向 ⇒ 无重叠。

🔴🔴 **两条候选锚「净增 0」避让登记（如实 · 章程 §2 ③ 与 R2 已预警）**：
  · **② 交换后保真递推**：`p' = p₁·p₂` ⇒ `F' = (1+3p₁p₂)/4` 是**纯代数学积**；
    任何「Bell 投影 + 部分迹」候选对 Werner 族都是**机器精度精确**（残差恒 ~1e-16，
    与自证桩 |Δ|≡0 不可区分）⇒ 判据 D 不成立 ⇒ **不立锚**（纯代数式降为 smoke/能力层）。
  · **④ 中继增益**：`R_rep/R_dir` 是**两个闭式之比**，分母分子同源 ⇒ 扰动时同变 ⇒
    判据 D 不成立 ⇒ **不立锚**（如实登记，不硬做）。
  ⇒ 本档**仅净增 1 锚 B521**（③ 产出计数，含真离散误差），与 J4「M1/M2 净增 0 · M3 出锚」同型。

🔴 **诚实边界**：T_gen / T_mem / T_swap / T_obs 为**设计示例量级**（非任何实测中继链）；
  只建模**三态竞争这一最小骨架**（未含多段链级联、交换门保真度、探测器效率、多光子噪声、
  存储多模复用）⇒ 只支撑预算与量级，**不作制造/性能宣称**，不报能效/TOPS/fJ-op。
  零商业依赖（纯 `math`；零 RNG）；**LLM 不进判决路径**。
"""

from __future__ import annotations

import math
from typing import Dict

from lda_l2 import qnet_channel as CH

__all__ = [
    "QNET_REPEATER_CALIBER",
    "DEFAULT_T_OBS_S",
    "DEFAULT_T_GEN_S",
    "DEFAULT_T_MEM_S",
    "DEFAULT_T_SWAP_S",
    "storage_survival",
    "storage_window_factor",
    "swap_fidelity",
    "repeater_yield",
    "repeater_rate",
    "direct_rate",
    "repeater_gain",
    "repeater_report",
    "selfcheck_qnet_repeater",
]

QNET_REPEATER_CALIBER = "repeater_swap_yield_and_rate__unitless_or_per_second"

#: 观测窗（s · 设计示例 200 µs）
DEFAULT_T_OBS_S = 2.0e-4
#: 生成尝试周期（s · 50 µs ⇒ λ=2e4 /s）
DEFAULT_T_GEN_S = 5.0e-5
#: 存储相干时间（s · 160 µs ⇒ μ=6.25e3 /s）
DEFAULT_T_MEM_S = 1.6e-4
#: 交换门耗时（s · 100 µs ⇒ κ=1e4 /s）
DEFAULT_T_SWAP_S = 1.0e-4


def _rates(t_gen_s: float, t_mem_s: float, t_swap_s: float):
    """🔴 先校验再取倒数（否则 t=0 抛 ZeroDivisionError 而非 ValueError · 契约不齐）。"""
    for _nm, _v in (("T_gen", t_gen_s), ("T_mem", t_mem_s), ("T_swap", t_swap_s)):
        if not float(_v) > 0.0:
            raise ValueError("%s 须 > 0" % _nm)
    lam = 1.0 / float(t_gen_s)
    mu = 1.0 / float(t_mem_s)
    kappa = 1.0 / float(t_swap_s)
    return lam, mu, kappa


def storage_survival(t_s: float, t_mem_s: float = DEFAULT_T_MEM_S) -> float:
    """① 存储存活因子 `S(t)=exp(−t/T_mem)`（**存储窗**的物理内核）。"""
    if float(t_mem_s) <= 0.0:
        raise ValueError("存储相干时间须 > 0")
    if float(t_s) < 0.0:
        raise ValueError("时间须 ≥ 0")
    return float(math.exp(-float(t_s) / float(t_mem_s)))


def storage_window_factor(window_s: float, t_mem_s: float = DEFAULT_T_MEM_S) -> float:
    """①b 存储窗**平均存活因子** `(1/W)∫₀^W e^{−t/T_mem}dt = (T_mem/W)(1−e^{−W/T_mem})`。

    这就是章程点名的 `∫e^{−t/T_mem}dt` 的**归一化落点**（W→0 时 →1；W≫T_mem 时 →T_mem/W）。
    """
    t_mem = float(t_mem_s)
    w = float(window_s)
    if t_mem <= 0.0:
        raise ValueError("存储相干时间须 > 0")
    if w <= 0.0:
        raise ValueError("窗宽须 > 0")
    return float(t_mem / w * (1.0 - math.exp(-w / t_mem)))


def swap_fidelity(p1: float, p2: float) -> float:
    """② 交换后 Werner 保真度 `F' = (1 + 3·p₁p₂)/4`。

    🔴 **纯代数学积** ⇒ 机器精度精确、判据 D 不成立 ⇒ **不立锚**（避让登记见模块头）。
    """
    for p in (p1, p2):
        if not (0.0 <= float(p) <= 1.0):
            raise ValueError("Werner 参数须落在 [0, 1]")
    return float((1.0 + 3.0 * float(p1) * float(p2)) / 4.0)


def repeater_yield(t_obs_s: float = DEFAULT_T_OBS_S, t_gen_s: float = DEFAULT_T_GEN_S,
                   t_mem_s: float = DEFAULT_T_MEM_S,
                   t_swap_s: float = DEFAULT_T_SWAP_S) -> float:
    """③ 期望交换产出数 `N_swap`（与 B521 golden **同律** · 初等闭式）。

        N_swap(T) = κλ/(γ−λ)·[(1−e^{−λT})/λ − (1−e^{−γT})/γ]，γ=μ+κ
    γ→λ 退化档取极限 `(κ/λ)[1−e^{−λT}(1+λT)]`。
    """
    lam, mu, kappa = _rates(t_gen_s, t_mem_s, t_swap_s)
    t_obs = float(t_obs_s)
    if t_obs <= 0.0:
        raise ValueError("观测窗须 > 0")
    g = mu + kappa
    if abs(g - lam) <= 1e-9 * lam:
        return float(kappa / lam * (1.0 - math.exp(-lam * t_obs) * (1.0 + lam * t_obs)))
    return float(kappa * lam / (g - lam)
                 * ((1.0 - math.exp(-lam * t_obs)) / lam
                    - (1.0 - math.exp(-g * t_obs)) / g))


def repeater_rate(t_obs_s: float = DEFAULT_T_OBS_S, t_gen_s: float = DEFAULT_T_GEN_S,
                  t_mem_s: float = DEFAULT_T_MEM_S,
                  t_swap_s: float = DEFAULT_T_SWAP_S) -> float:
    """④ 中继站产出率 `R = N_swap / T_obs`（1/s）。"""
    return float(repeater_yield(t_obs_s, t_gen_s, t_mem_s, t_swap_s) / float(t_obs_s))


def direct_rate(length_m: float, t_obs_s: float = DEFAULT_T_OBS_S,
                alpha_db_per_km: float = CH.DEFAULT_ALPHA_DB_PER_KM) -> float:
    """④b 同长度**直传**产出率 `R_dir = T(L)/T_obs`（复用 `qnet_channel.transmission`）。

    T(L)=10^{−α·L_km/10} ⇒ 直传随长度**指数衰减**（这正是中继要打败的那一项）。
    """
    if float(length_m) <= 0.0:
        raise ValueError("长度须 > 0")
    return float(CH.transmission(float(length_m), alpha_db_per_km) / float(t_obs_s))


def repeater_gain(length_m: float = 1.0e5, t_obs_s: float = DEFAULT_T_OBS_S,
                  t_gen_s: float = DEFAULT_T_GEN_S, t_mem_s: float = DEFAULT_T_MEM_S,
                  t_swap_s: float = DEFAULT_T_SWAP_S,
                  alpha_db_per_km: float = CH.DEFAULT_ALPHA_DB_PER_KM) -> float:
    """④c 中继增益 = 产出率之比 `R_rep / R_dir`（**纯比值 · 不立锚** · 避让登记见模块头）。

    ⚠️ 与 `passivity` 锚（B19 · 判「有增益 = FAIL」，即被动网络 |T|≤1）**语义相反且无关**：
    此处「增益 > 1」只表示**单位时间产出更多可用纠缠对**，不表示任何能量/光子数放大。
    """
    return float(repeater_rate(t_obs_s, t_gen_s, t_mem_s, t_swap_s)
                 / direct_rate(length_m, t_obs_s, alpha_db_per_km))


def repeater_report(length_m: float = 1.0e5) -> Dict[str, float]:
    """中继能力层报告（四环一次给全 · 零重计算）。"""
    lam, mu, kappa = _rates(DEFAULT_T_GEN_S, DEFAULT_T_MEM_S, DEFAULT_T_SWAP_S)
    n_swap = repeater_yield()
    return {
        "lambda_s1": float(lam),
        "mu_s1": float(mu),
        "kappa_s1": float(kappa),
        "yield": float(n_swap),
        "rate_s1": float(n_swap / DEFAULT_T_OBS_S),
        "storage_window_factor": storage_window_factor(DEFAULT_T_OBS_S),
        "direct_rate_s1": direct_rate(length_m),
        "gain": repeater_gain(length_m),
        "f1": float(swap_fidelity(0.9, 0.9)),
        "caliber": QNET_REPEATER_CALIBER,
    }


def selfcheck_qnet_repeater() -> Dict[str, bool]:
    """中继能力层自检（含与数值核 B521 的同律逐位对拍 + 两条避让登记）。"""
    checks: Dict[str, bool] = {}

    # ① 存储窗：极限行为
    checks["storage_survival_at_zero_is_one"] = bool(abs(storage_survival(0.0) - 1.0) < 1e-15)
    checks["storage_survival_monotone"] = bool(
        storage_survival(0.0) > storage_survival(1.0e-4) > storage_survival(4.0e-4))
    # W→0 ⇒ 因子→1；W≫T_mem ⇒ 因子→T_mem/W
    checks["storage_window_small_w_to_one"] = bool(
        abs(storage_window_factor(1e-9) - 1.0) < 1e-5)
    checks["storage_window_large_w_to_ratio"] = bool(
        abs(storage_window_factor(1e-2) - DEFAULT_T_MEM_S / 1e-2) < 1e-12)

    # ② 交换保真递推：代数性质（p=1 理想 ⇒ F=1；p=0 ⇒ F=1/4）
    checks["swap_fidelity_ideal_is_one"] = bool(abs(swap_fidelity(1.0, 1.0) - 1.0) < 1e-15)
    checks["swap_fidelity_fully_mixed_is_quarter"] = bool(
        abs(swap_fidelity(0.0, 0.0) - 0.25) < 1e-15)
    checks["swap_fidelity_symmetric"] = bool(
        abs(swap_fidelity(0.9, 0.4) - swap_fidelity(0.4, 0.9)) < 1e-15)

    # ③ 产出数：与数值核 golden **同律逐位**（防两处口径漂移）
    r = repeater_report()
    try:
        from lda_harness import _batch_j5_numeric as J5
        checks["matches_b521_golden"] = bool(
            abs(J5.repeater_yield_golden() - repeater_yield()) < 1e-15)
        checks["matches_b521_default_params"] = bool(
            abs(J5.B521_DEFAULT_PARAMS["t_mem_s"] - DEFAULT_T_MEM_S) < 1e-18)
    except Exception:
        checks["matches_b521_golden"] = False
        checks["matches_b521_default_params"] = False

    # ③b 单调性/极限：κ→0 ⇒ 无交换 ⇒ 产出→0；T→0 ⇒ 产出→0
    checks["yield_zero_when_swap_instant_never"] = bool(
        repeater_yield(t_swap_s=1e6) < 1e-9)
    checks["yield_zero_at_zero_window"] = bool(
        abs(repeater_yield(t_obs_s=1e-12)) < 1e-12)
    checks["yield_monotone_in_storage_time"] = bool(
        repeater_yield(t_mem_s=1e-3) > repeater_yield() > repeater_yield(t_mem_s=1e-5))

    # ③c 退化档 γ=λ（μ+κ=λ）走极限式而非 0/0
    lam = 1.0 / DEFAULT_T_GEN_S
    t_mem_degen = 1.0 / (lam - 1.0 / DEFAULT_T_SWAP_S)
    y_degen = repeater_yield(t_mem_s=t_mem_degen)
    checks["degenerate_gamma_equals_lambda_finite"] = bool(
        math.isfinite(y_degen) and y_degen > 0.0)

    # ④ 增益：非负且与直传相关
    checks["gain_positive"] = bool(r["gain"] > 0.0)
    checks["direct_rate_monotone_decreasing_in_length"] = bool(
        direct_rate(1.0e4) > direct_rate(1.0e5) > direct_rate(2.0e5))
    checks["rate_equals_yield_over_window"] = bool(
        abs(repeater_rate() - repeater_yield() / DEFAULT_T_OBS_S) < 1e-18)

    # 反向探针：非法入参必抛
    def _raises(fn):
        try:
            fn()
        except ValueError:
            return True
        return False

    checks["reverse_bad_times_raise"] = bool(_raises(lambda: repeater_yield(t_gen_s=0.0)))
    checks["reverse_bad_probability_raise"] = bool(_raises(lambda: swap_fidelity(1.5, 0.5)))
    checks["reverse_bad_window_raise"] = bool(_raises(lambda: storage_window_factor(0.0)))
    checks["reverse_bad_length_raise"] = bool(_raises(lambda: direct_rate(-1.0)))
    return checks


def main() -> int:  # pragma: no cover
    checks = selfcheck_qnet_repeater()
    bad = [k for k, v in checks.items() if not v]
    for k, v in checks.items():
        print("  [%s] %s" % ("PASS" if v else "FAIL", k))
    r = repeater_report()
    print("\nλ=%.6e /s  μ=%.6e /s  κ=%.6e /s" % (r["lambda_s1"], r["mu_s1"], r["kappa_s1"]))
    print("产出数 N_swap = %.12e · 产出率 = %.6e /s" % (r["yield"], r["rate_s1"]))
    print("存储窗因子 = %.12e · 直传率 = %.6e /s · 增益 = %.6e"
          % (r["storage_window_factor"], r["direct_rate_s1"], r["gain"]))
    print("自检：%s（FAIL=%s）" % ("ALL PASS" if not bad else "FAIL", bad or "无"))
    return 0 if not bad else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
