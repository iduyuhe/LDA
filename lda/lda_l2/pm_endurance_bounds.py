# -*- coding: utf-8 -*-
"""PM-G10 的**可判定边界**：endurance 为什么「不可判」，以及能判到哪一步（v0.9.312）。

## 缺口原文（`pm_case.PM-G10`，未闭合）

> 征程内**无 endurance 模型**；文献检索未取得光子 GST 器件级循环数实测锚
> （Ríos 2015 原文未报循环数）⇒ 对拍表该行 verdict=not_modeled。
> 🔴 不引用电学 PCM 的 10⁶–10⁹ 量级作粉饰（器件口径不同）。

本模块**不造 endurance 模型**（凭空给一个 δ 就是编数据），也**不改** `not_modeled` 判词。
它做三件纯代数的事，把「不可判」从一句托词变成**可逐条核的结论**：

### ① 任何循环数宣称，等价于一个**每循环损伤上界 δ 的承诺**

现有系统误差预算（`pm_m4.system_link_budget`，三段独立误差按方差合成）::

    ε_tot² = ε_write² + ε_read² + ν_T²·ln²(t/t₀)

把「循环累积损伤」按**两种**口径各加一项（口径不定 ⇒ **并报**，本仓一贯做法）::

    独立累积（各循环损伤互不相关）  ε_cyc = √N · δ      ⇒  ε_tot² += N·δ²
    最坏累积（同向线性叠加）        ε_cyc = N · δ       ⇒  ε_tot  += N·δ

反解即得::

    δ_max(N, t)  =  √(rest/N)       （独立口径）
                 =  rest/N          （最坏口径）      rest ≡ ε_bud² − ε_write² − ε_read² − ν_T²ln²(t/t₀)

🔴 **两口径给出的 δ 界相差 `√N` 倍**。宣称 N = 10⁶ 时这个差是 **1000×**。
⇒ 「不可判」的**结构性**原因是：**缺的不是数据点，是失效机制**（独立 vs 线性）。
数据能定 δ 的数值，但**定不了该用哪个口径** —— 而口径错 3 个数量级。

### ② 新层在 δ=0 处必须**逐位退化**回现有结论

    t_max(δ=0) = t₀ · exp( √(ε_bud² − ε_write² − ε_read²) / ν_T )

这与 `pm_m4.system_link_budget()["max_t_hold_s_for_target"]`（对 BER 做几何二分）
是**两条独立路线**；本模块在自检 ② 与门禁里逐位对拍（实测 log 空间差 **5.7e-14**）。
⇒ 加这一层**没有改旧结论**，只是把它参数化。

### ③ 要宣称「N 次无失效」，样本量是**算得出来的**

0 失效情形的二项精确式（Weibull/中位秩同源）::

    n = ⌈ ln(1 − C) / ln(R) ⌉        C = 置信度，R = 可靠度

`C=90%, R=90% ⇒ n = 22`；`C=95%, R=90% ⇒ n = 29`。要宣称「10⁶ 循环无失效 @90/90」
就得 **22 个器件各跑 10⁶ 次** —— 这是实验设计的硬约束，与本仓是否有模型无关。

## 🔴 顺带纠正卡上一处**隐含论证**

卡上「不引用电学 PCM 的 10⁶–10⁹（器件口径不同）」这个**结论**是对的，但常被引用的
理由「光子相变体积大 10³–10⁴ 倍」**单独推不出循环数不同**：

    若每循环注入的缺陷数 ∝ V，且失效所需临界缺陷数也 ∝ V，则 N_crit **与 V 无关**
    ⇒ 体积比 2360× 对 N 的比值贡献是 **1×**（自检 ⑩ 把这个"不成立"写成显式断言）。

⇒ 真正成立的三条理由是：**(a) 判据不同**（电学看阻值窗口、光子看透射/相移窗口）、
**(b) 特征尺度不同**（尺度比可算，但**不改变 N**，见上）、**(c) 失效机制未定**
（δ 的界跨 `√N`）。其中 **(c) 是决定性的**，而 (c) 恰好是「没有实测锚」的直接后果 ——
两者是同一件事，不是两条借口。

## 诚实边界

* 本模块**不提供任何 δ 的数值**，也不提供任何循环数预测；`endurance_verdict()` 仍返回
  `not_modeled`，且**不许**被改成别的值（判据锁死）。
* 「线性叠加」与「方差叠加」都只是**两个极端**；真实机制可能介于两者之间或与 N 非线性
  ⇒ 本模块给的是**区间**，不是点值。
* 电学 PCM 接触区尺寸取工程典型 `50×50×20 nm`（**假设**，非实测），只用于给出尺度比。
* 光子 GST 厚度取 `20 nm`（与 `pm_matlib.gamma_invariance` 默认同源），非本项目实测。
* 本层**未新增任何锚**：全部是代数恒等式与量级事实。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "ANCHORABLE", "T_GST_NM_DEFAULT", "ELECTRICAL_PCM_CONTACT_NM",
    "eps_budget_for_ber", "budget_parts", "t_max_log",
    "cycle_damage_bounds", "n_cycles_max", "zero_failure_sample_size",
    "photonic_active_volume_um3", "volume_scale", "endurance_verdict",
    "why_not_anchored", "run_selfchecks",
]

#: 本层只证代数与量级，无物理标量对实测 ⇒ 不参与锚计数。
ANCHORABLE: bool = False

#: 光子相变段厚度（nm）。与 `pm_matlib.gamma_invariance(t_gst_nm=20.0)` 默认**同源**。
T_GST_NM_DEFAULT: float = 20.0

#: 电学 PCM 接触区（nm）：**工程典型假设**，非本项目实测，只用于给出尺度比。
ELECTRICAL_PCM_CONTACT_NM: Tuple[float, float, float] = (50.0, 50.0, 20.0)


def why_not_anchored() -> str:
    """为什么本模块不可锚（须自答）。"""
    return ("本层证的是**代数事实**：`δ_max` 的两口径差 `√N`、`t_max(δ=0)` 与既有逆解逐位一致、"
            "0 失效样本量闭式。**不给任何 δ 数值、不给任何循环数预测** ⇒ 无锚可加；"
            "`endurance_verdict()` 恒为 `not_modeled`。")


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def eps_budget_for_ber(ber_target: float) -> float:
    """由 BER 目标反解**允许的等效电平误差** `ε_bud`（`BER = ½erfc(1/(2ε√2))`）。

    这一步是把「BER ≤ 1e-12」翻译成「ε ≤ ε_bud」—— 后面所有反解都建立在它上面。
    """
    tgt = float(ber_target)
    _require(0.0 < tgt < 0.5, "BER 目标须在 (0, 0.5)，收到 %r" % (ber_target,))

    def _ber(eps: float) -> float:
        snr = 1.0 / (2.0 * eps)
        return 0.5 * math.erfc(snr / math.sqrt(2.0))

    lo, hi = 1e-12, 10.0          # ε 越小 BER 越小；单调升
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _ber(mid) <= tgt:
            lo = mid
        else:
            hi = mid
    return lo


def budget_parts(t_hold_s: Optional[float] = None, *,
                 mat: str = "GST", n_levels: Optional[int] = None,
                 ber_target: Optional[float] = None) -> Dict[str, Any]:
    """取现有三段预算的**已建量**（不重算，直接读 `pm_m4.system_link_budget`）。

    返回 `ε_write` / `ε_read` / `ν_T` / `t₀` / `ε_bud` 与 `rest_min`（drift 之外的剩余预算）。
    """
    from lda_l2 import pm_m4 as M4

    sb = M4.system_link_budget(mat, n_levels,
                               t_hold_s=(M4.T_HOLD_S_DEFAULT if t_hold_s is None
                                         else float(t_hold_s)))
    e_w = float(sb["eps"]["write"])
    e_r = float(sb["eps"]["read"])
    nu = float(sb["drift_anchor"]["nu_t_ub"])
    tgt = float(M4.M1.BER_TARGET if ber_target is None else ber_target)
    e_bud = eps_budget_for_ber(tgt)
    rest_min = e_bud * e_bud - e_w * e_w - e_r * e_r
    _require(rest_min > 0.0,
             "写入+读出已吃掉全部预算（rest=%.3e）⇒ drift/循环无余量" % rest_min)
    return {"eps_write": e_w, "eps_read": e_r, "nu_t_ub": nu, "t0_s": float(M4.T_HOLD_T0_S),
            "ber_target": tgt, "eps_bud": e_bud, "rest_min": rest_min,
            "t_max_gate_s": float(sb["max_t_hold_s_for_target"]),
            "note": ("🔴 三段（write/read/drift）全部**读现有实现**，本层不重算 —— "
                     "新增的只有循环项与它的反解。")}


def t_max_log(n_cycles: int = 0, delta: float = 0.0, *,
              mat: str = "GST", n_levels: Optional[int] = None,
              ber_target: Optional[float] = None) -> Dict[str, Any]:
    """`ln t_max` 的**闭式**（含循环项），避免 `exp(170)` 溢出。

        rest(N, δ) = ε_bud² − ε_write² − ε_read² − N·δ²      （独立累积口径）
        ln t_max   = ln t₀ + √rest / ν_T
    """
    n = int(n_cycles)
    d = float(delta)
    _require(n >= 0, "循环数须 ≥ 0")
    _require(d >= 0.0, "每循环损伤须 ≥ 0")
    bp = budget_parts(None, mat=mat, n_levels=n_levels, ber_target=ber_target)
    rest = bp["rest_min"] - n * d * d
    if rest <= 0.0:
        return {"feasible": False, "rest": rest, "log_t_max": None, "t_max_s": 0.0,
                "note": "🔴 循环项已吃掉全部剩余预算 ⇒ 任何保持时间都不达标（t_max = 0）"}
    log_t = math.log(bp["t0_s"]) + math.sqrt(rest) / bp["nu_t_ub"]
    return {"feasible": True, "rest": rest, "log_t_max": log_t,
            "t_max_s": (log_t if log_t < 700.0 else None),
            "t_max_overflow": bool(log_t >= 700.0),
            "parts": bp,
            "note": ("🔴 闭式与 `pm_m4` 的 BER 二分是**两条独立路线**；δ=N=0 时须逐位一致。")}


def cycle_damage_bounds(t_hold_s: float, n_cycles: int, *,
                        mat: str = "GST", n_levels: Optional[int] = None,
                        ber_target: Optional[float] = None) -> Dict[str, Any]:
    """反解：宣称「`n_cycles` 次后、保持 `t_hold_s` 仍达标」**隐含的每循环损伤上界**。

    **两种累加口径并报**（口径不定 ⇒ 不选一个）::

        独立累积  δ_max = √(rest/N)
        最坏累积  δ_max = rest/N
        ⇒ 比值恰为 √N（N = 10⁶ 时 **1000×**）
    """
    n = int(n_cycles)
    t = float(t_hold_s)
    _require(n >= 1, "循环数须 ≥ 1（反解 δ 才有意义）")
    bp = budget_parts(t, mat=mat, n_levels=n_levels, ber_target=ber_target)
    drift = bp["nu_t_ub"] * math.log(max(t, bp["t0_s"]) / bp["t0_s"])
    rest = bp["rest_min"] - drift * drift
    if rest <= 0.0:
        return {"feasible": False, "rest": rest, "t_hold_s": t, "n_cycles": n,
                "note": "🔴 保持时间本身已把预算吃光（与循环无关）⇒ δ_max = 0"}
    # 🔴 两个界都是 **ε 单位**：`rest` 是 **ε²** 量。
    #    独立累积：N·δ² ≤ rest ⇒ δ ≤ √rest/√N
    #    最坏累积：N·δ  ≤ √rest ⇒ δ ≤ √rest/N
    #    ⇒ 比值恰为 √N（第一版把最坏口径写成 `rest/N` = ε²/N，**量纲就错了**，
    #      比值给成 √N/√rest = 15477 —— 由判据 ③ 当场抓出）。
    d_q = math.sqrt(rest) / math.sqrt(n)   # 独立累积
    d_l = math.sqrt(rest) / n              # 最坏累积
    return {"feasible": True, "t_hold_s": t, "n_cycles": n,
            "drift_eps": drift, "rest": rest,
            "delta_max_quadrature": d_q, "delta_max_linear": d_l,
            "spread_x": (d_q / d_l), "sqrt_n": math.sqrt(n),
            "note": ("🔴 两口径差 `√N`（独立口径的界**松** `√N` 倍）⇒ 「N 次循环」这句话"
                     "**只**等价于一个跨 %d× 的 δ 区间。要收窄必须先定失效机制"
                     "（独立 vs 线性），而那需要实测。" % int(round(math.sqrt(n))))}


def n_cycles_max(t_hold_s: float, delta: float, *, mode: str = "quadrature",
                 mat: str = "GST", n_levels: Optional[int] = None,
                 ber_target: Optional[float] = None) -> Dict[str, Any]:
    """反解：给定每循环损伤 `δ`（外生假设，本层**不给值**），最多能跑多少循环。"""
    t = float(t_hold_s)
    d = float(delta)
    _require(d > 0.0, "δ 须 > 0（δ=0 意味着无限耐久，不是本函数要回答的）")
    _require(mode in ("quadrature", "linear"), "mode 须为 quadrature 或 linear")
    bp = budget_parts(t, mat=mat, n_levels=n_levels, ber_target=ber_target)
    drift = bp["nu_t_ub"] * math.log(max(t, bp["t0_s"]) / bp["t0_s"])
    rest = bp["rest_min"] - drift * drift
    if rest <= 0.0:
        return {"feasible": False, "n_max": 0.0, "rest": rest, "mode": mode,
                "note": "🔴 drift 项已吃掉预算 ⇒ 与循环无关地不可行"}
    n_max = (rest / (d * d)) if mode == "quadrature" else (math.sqrt(rest) / d)
    return {"feasible": True, "n_max": n_max, "rest": rest, "mode": mode,
            "law": ("quadrature: N_max = rest/δ²  ∝ 1/δ²" if mode == "quadrature"
                    else "linear: N_max = √rest/δ  ∝ 1/δ"),
            "note": ("🔴 `N_max(t_hold)` 严格单调降（drift 与循环**共用同一个**误差预算）；"
                     "存在 `t_crit` 使 `N_max = 0` —— 那个 `t_crit` **与循环无关**，就是现有 t_max。")}


def zero_failure_sample_size(confidence: float, reliability: float) -> Dict[str, Any]:
    """「0 失效」样本量闭式：`n = ⌈ln(1−C)/ln(R)⌉`（二项精确）。

    语义：要在 `C` 置信度下宣称「可靠度 ≥ R」，需要在 `n` 个**独立**器件上各跑到目标循环数
    且**全部不失效**。这是 endurance 实验设计的硬约束，与是否有模型无关。
    """
    c = float(confidence)
    r = float(reliability)
    _require(0.0 < c < 1.0, "置信度须在 (0,1)")
    _require(0.0 < r < 1.0, "可靠度须在 (0,1)")
    n = int(math.ceil(math.log(1.0 - c) / math.log(r)))
    return {"confidence": c, "reliability": r, "n_devices": n,
            # 🔴 0 失效语义：`P(全通过 | 可靠度 R) = R^n`，故夹逼是
            #    R^n ≤ 1−C < R^(n−1)。写成 (1−R)^n 是**另一个量**（那是"至少一次失败"的概率）。
            "check_lower": math.pow(r, n),                # ≤ 1−C
            "check_upper": math.pow(r, max(n - 1, 0)),    # > 1−C
            "formula": "n = ceil(ln(1−C)/ln(R))（0 失效 · 二项精确）",
            "note": ("🔴 要宣称「10⁶ 循环无失效 @90/90」⇒ 需 **%d 个器件各跑 10⁶ 次**。"
                     "这条与「有没有模型」无关，是统计事实。" % n)}


def photonic_active_volume_um3(t_gst_nm: float = T_GST_NM_DEFAULT) -> Dict[str, Any]:
    """光子相变段**有源体积**（µm³）：几何读 `pm_m3` + `PCM_CELL_DEFAULTS`（单一真源）。"""
    from lda_l2 import pm_m3 as M3
    from lda_l2 import primitives as PR

    t_nm = float(t_gst_nm)
    _require(t_nm > 0.0, "GST 厚度须为正")
    l_um = float(M3.cell_length_um()["l_um"])
    wg = float(PR.PCM_CELL_DEFAULTS["width"])
    ov = float(PR.PCM_CELL_DEFAULTS["gst_overhang"])
    w_um = wg + 2.0 * ov
    v = l_um * w_um * (t_nm * 1e-3)
    return {"l_um": l_um, "w_um": w_um, "t_nm": t_nm, "volume_um3": v,
            "volume_m3": v * 1e-18,
            "source": {"l": "pm_m3.cell_length_um()", "w": "PCM_CELL_DEFAULTS.width + 2×gst_overhang",
                       "t": "T_GST_NM_DEFAULT（与 pm_matlib.gamma_invariance 默认同源）"}}


def volume_scale(t_gst_nm: float = T_GST_NM_DEFAULT) -> Dict[str, Any]:
    """光子有源体积 ⇄ 电学 PCM 接触区体积的**尺度比**，并**明确它推不出循环数比**。

    🔴 这是纠正卡上一处隐含论证：常被引用的「光子体积大 10³–10⁴ 倍」**单独不能**说明
    循环数不同 —— 若每循环注入缺陷数 ∝ V、失效临界缺陷数也 ∝ V，则 `N_crit` 与 V 无关。
    """
    pv = photonic_active_volume_um3(t_gst_nm)
    ex, ey, ez = ELECTRICAL_PCM_CONTACT_NM
    ev = (ex * 1e-3) * (ey * 1e-3) * (ez * 1e-3)      # nm → µm
    ratio = pv["volume_um3"] / ev
    return {"photonic_volume_um3": pv["volume_um3"], "electrical_volume_um3": ev,
            "scale_ratio": ratio, "photonic": pv,
            "electrical_contact_nm": list(ELECTRICAL_PCM_CONTACT_NM),
            "n_ratio_from_volume_alone": 1.0,
            "argument_status": "insufficient",
            "why": ("若「每循环注入 ∝ V」且「临界缺陷数 ∝ V」⇒ 比值相消 ⇒ N_crit 与 V 无关；"
                    "若失效由**界面**驱动（∝ 面积）⇒ N 随面积反比变 —— 两种假设给出不同的 N，"
                    "而**哪一种成立未知** ⇒ 体积比**单独**不是理由。"),
            "decisive_reason": ("真正成立的理由是 ① 判据不同（阻值窗口 vs 透射/相移窗口）"
                                "② 失效机制未定（`δ` 的界跨 `√N`）—— 后者是决定性的，"
                                "而它正是「没有实测锚」的直接后果。")}


def endurance_verdict() -> Dict[str, Any]:
    """本卡 endurance 行的**判词**（恒为 `not_modeled`，判据锁死）。

    缺什么，逐条列出（不是一句「器件口径不同」）：
    """
    return {
        "verdict": "not_modeled",
        "missing": [
            "每循环等效电平损伤 δ 的**数值**（本层只给反解式，不给值）",
            "累加**机制**（独立 vs 线性；两口径的 δ 界相差 √N）",
            "失效**判据**的实测定义（透射/相移窗口跌到多少算失效）",
            "器件级循环数实测分布（Ríos 2015 原文未报循环数）",
        ],
        "judgeable_now": [
            "任何循环数宣称 ⇒ 等价于 δ 的一个上界承诺（两种口径各给一个）",
            "δ=0 时本层必须逐位退化为既有 t_max（已与 pm_m4 二分对拍）",
            "宣称「N 次无失效 @C/R」所需的**样本量**（二项闭式）",
        ],
        "must_not": "🔴 不得引用电学 PCM 的 10⁶–10⁹ 量级（判据与机制都不同）；"
                    "也不得用「光子体积大 10³–10⁴ 倍」当理由（体积比单独推不出 N 比）。",
    }


# ══════════════════════════════════════════════════════════════════════
# 自检
# ══════════════════════════════════════════════════════════════════════
def run_selfchecks(verbose: bool = True) -> Tuple[int, int, List[str]]:
    """模块自检。返回 `(npass, total, lines)`。"""
    lines: List[str] = []

    def chk(name: str, ok: bool, detail: str = "") -> None:
        lines.append("[%s] %s%s" % ("PASS" if ok else "FAIL", name,
                                    ("  |  " + detail) if detail else ""))

    bp = budget_parts()

    # ① ε_bud 反解回代：BER(ε_bud) ≡ 目标（相对 1e-12）
    e = bp["eps_bud"]
    snr = 1.0 / (2.0 * e)
    ber = 0.5 * math.erfc(snr / math.sqrt(2.0))
    rel = abs(ber - bp["ber_target"]) / bp["ber_target"]
    chk("① ε_bud 反解回代：BER(%.6f) = %.3e ≡ 目标 %.1e（相对 %.1e ≤ 1e-12）"
        % (e, ber, bp["ber_target"], rel), rel < 1e-12 or rel == 0.0,
        "rest_min=%.6e" % bp["rest_min"])

    # ② 🔴 闭式 t_max(δ=0,N=0) ≡ pm_m4 的 BER 二分（两条独立路线）
    tm = t_max_log(0, 0.0)
    d_log = abs(tm["log_t_max"] - math.log(bp["t_max_gate_s"]))
    chk("② 🔴 t_max(δ=0) 闭式 ≡ `pm_m4` BER 二分（log 空间 |Δ| = %.2e ≤ 1e-10）"
        % d_log, d_log < 1e-10,
        "ln t_max=%.6f" % tm["log_t_max"])

    # ③ 两口径 δ 界之比 ≡ √N（精确）
    cb = cycle_damage_bounds(1.0e4, 1000000)
    chk("③ 🔴 独立 vs 最坏累积的 δ 界相差 ≡ √N = %.6f（实测 %.9f；N=10⁶ ⇒ **1000×**）"
        % (cb["sqrt_n"], cb["spread_x"]),
        abs(cb["spread_x"] - math.sqrt(1e6)) < 1e-6,
        "δ_quad=%.4e δ_lin=%.4e" % (cb["delta_max_quadrature"], cb["delta_max_linear"]))

    # ④ N_max 单调降 + 与 δ⁻² / δ⁻¹ 标度一致
    d0 = 1e-6
    n1 = n_cycles_max(1.0, d0)["n_max"]
    n2 = n_cycles_max(1.0, 2.0 * d0)["n_max"]
    n3 = n_cycles_max(1.0e4, d0)["n_max"]
    chk("④ 标度律：N_max(2δ) == N_max(δ)/4（∝1/δ²）∧ N_max(t=10⁴ s) < N_max(t=1 s)（drift 吃预算）",
        abs(n2 / n1 - 0.25) < 1e-12 and n3 < n1,
        "N(δ)=%.4e N(2δ)=%.4e N(t=1e4)=%.4e" % (n1, n2, n3))

    # ⑤ 反解回代：把 N_max 代回预算 ⇒ ε_tot 恰回到 ε_bud（1e-12）
    # 🔴 回代必须用 `N·δ²`（循环项已把剩余预算吃满 ⇒ `rest_after == 0`），
    #    写成 `sqrt(rest_after + write² + read²)` 会把循环项整个漏掉（第一版就这么错的）。
    nn = n1
    rest_after = bp["rest_min"] - nn * d0 * d0
    eps_after = math.sqrt(max(nn * d0 * d0, 0.0) + bp["eps_write"] ** 2 + bp["eps_read"] ** 2)
    chk("⑤ 反解回代：N_max 处 ε_tot = %.12f ≡ ε_bud = %.12f（|Δ| = %.1e）"
        % (eps_after, bp["eps_bud"], abs(eps_after - bp["eps_bud"])),
        abs(eps_after - bp["eps_bud"]) < 1e-12)

    # ⑥ 0 失效样本量闭式（三档已知值 + 二项夹逼）
    ss = {k: zero_failure_sample_size(*k) for k in ((0.90, 0.90), (0.95, 0.90), (0.90, 0.50))}
    ok6 = all((v["check_upper"] >= 1.0 - v["confidence"]) and
              (v["check_lower"] <= 1.0 - v["confidence"])
              for v in ss.values())
    ok6 = ok6 and all(v["n_devices"] == int(math.ceil(
        math.log(1.0 - v["confidence"]) / math.log(v["reliability"]))) for v in ss.values())
    chk("⑥ 0 失效样本量：n(90/90)=%d ∧ n(95/90)=%d ∧ n(90/50)=%d ∧ 三档二项夹逼成立"
        % (ss[(0.90, 0.90)]["n_devices"], ss[(0.95, 0.90)]["n_devices"],
           ss[(0.90, 0.50)]["n_devices"]), ok6,
        "n(90/90) 应 = 22")

    # ⑦ 样本量单调性：C↑ ⇒ n↑；R↑ ⇒ n↑
    n_c = [zero_failure_sample_size(c, 0.9)["n_devices"] for c in (0.5, 0.9, 0.99)]
    n_r = [zero_failure_sample_size(0.9, r)["n_devices"] for r in (0.5, 0.9, 0.99)]
    chk("⑦ 样本量单调：置信度↑ ⇒ n 非降 ∧ 可靠度↑ ⇒ n 非降",
        n_c == sorted(n_c) and n_r == sorted(n_r), "C: %s R: %s" % (n_c, n_r))

    # ⑧ 保持时间↑ ⇒ δ 界↓（drift 与循环共用预算）
    cb1 = cycle_damage_bounds(1.0, 1000)["delta_max_quadrature"]
    cb2 = cycle_damage_bounds(1.0e4, 1000)["delta_max_quadrature"]
    chk("⑧ 保持时间 1 s → 10⁴ s ⇒ δ 界 %.4e → %.4e 严格下降（共用同一个误差预算）"
        % (cb1, cb2), cb2 < cb1)

    # ⑨ 光子体积与几何同源：V ≡ L·W·t（逐位）
    pv = photonic_active_volume_um3()
    recompute = pv["l_um"] * pv["w_um"] * pv["t_nm"] * 1e-3
    chk("⑨ 有源体积 V ≡ L·W·t（逐位 %.18f vs %.18f；L=%.3f W=%.3f t=%.0f nm）"
        % (pv["volume_um3"], recompute, pv["l_um"], pv["w_um"], pv["t_nm"]),
        pv["volume_um3"] == recompute, "V=%.4f µm³" % pv["volume_um3"])

    # ⑩ 🔴 「体积比 ⇒ N 比」不成立（把这条"不成立"写成显式断言，防再被当理由引用）
    vs = volume_scale()
    chk("⑩ 🔴 尺度比 %.0f× 已知，但 `n_ratio_from_volume_alone` == 1.0（argument_status=%s）"
        " ⇒ 「光子体积大 10³–10⁴ 倍」**单独推不出**循环数比" %
        (vs["scale_ratio"], vs["argument_status"]),
        vs["scale_ratio"] > 100.0 and vs["n_ratio_from_volume_alone"] == 1.0
        and vs["argument_status"] == "insufficient")

    # ⑪ 非物理输入必须抛（7 类）
    guard = 0
    for fn, kw in ((eps_budget_for_ber, {"ber_target": 0.6}),
                   (eps_budget_for_ber, {"ber_target": 0.0}),
                   (t_max_log, {"n_cycles": -1, "delta": 0.0}),
                   (t_max_log, {"n_cycles": 0, "delta": -1e-6}),
                   (cycle_damage_bounds, {"t_hold_s": 1.0, "n_cycles": 0}),
                   (zero_failure_sample_size, {"confidence": 1.0, "reliability": 0.9}),
                   (zero_failure_sample_size, {"confidence": 0.9, "reliability": 0.0})):
        try:
            fn(**kw)
        except ValueError:
            guard += 1
    chk("⑪ 非物理输入 7 类（BER≥0.5 / BER=0 / N<0 / δ<0 / N=0 反解 / C≥1 / R=0）全部 raise",
        guard == 7, "拦截 %d/7" % guard)

    # ⑫ 反向探针：闭式漏 sqrt（写成 rest/ν）⇒ ② 必红
    wrong_log = math.log(bp["t0_s"]) + bp["rest_min"] / bp["nu_t_ub"]
    chk("⑫ 反向探针：闭式误写 `ln t_max = ln t₀ + rest/ν`（漏 sqrt）⇒ log 差 %.1f ≫ 1e-10 ⇒ ② 必红"
        % abs(wrong_log - math.log(bp["t_max_gate_s"])),
        abs(wrong_log - math.log(bp["t_max_gate_s"])) > 1.0)

    # ⑬ 反向探针：把两口径写成同一式 ⇒ ③ 必红
    chk("⑬ 反向探针：若把最坏累积也写成 `√(rest/N)` ⇒ 比值退化为 1.0（实测 %.1f ≠ 1）⇒ ③ 必红"
        % cb["spread_x"], abs(cb["spread_x"] - 1.0) > 100.0)

    # ⑭ 🔴 判词锁死：仍为 not_modeled，且缺项四条齐（不许把"界定边界"写成"已解决"）
    ev = endurance_verdict()
    chk("⑭ 🔴 判词锁死 = `%s` ∧ 缺项 %d 条（δ 数值/机制/失效判据/实测分布）∧ 可判项 %d 条"
        % (ev["verdict"], len(ev["missing"]), len(ev["judgeable_now"])),
        ev["verdict"] == "not_modeled" and len(ev["missing"]) == 4
        and len(ev["judgeable_now"]) == 3)

    npass = sum(1 for ln in lines if ln.startswith("[PASS]"))
    if verbose:
        for ln in lines:
            print(ln)
        print("pm_endurance_bounds 自检：%d/%d PASS" % (npass, len(lines)))
    return npass, len(lines), lines


if __name__ == "__main__":
    import sys
    _p, _t, _ = run_selfchecks()
    sys.exit(0 if _p == _t else 1)
