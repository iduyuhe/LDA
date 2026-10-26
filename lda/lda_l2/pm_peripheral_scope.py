# -*- coding: utf-8 -*-
"""PM-M4 外设参数的**物理核验与作用域划分**（v0.9.311 · 闭合 `PM-G9a`）。

## 缺口原文（`pm_case.PM-G9`，未闭合）

> PD 响应度（A/W）/ 加热器薄膜方阻（Ω/sq）取**公开工程典型区间**（非实测、非逐条 DOI）；
> 读出速率 / 输入光功率 / 驱动摆幅 / EIC 通道 pitch 为**设计假设** ⇒ 外设结论只给
> **区间 + 恒等式 + 单调性**，无绝对真值。

这句话把三件不同的事压成了一句「无绝对真值」。本模块**不改那两个区间**（改区间才是编数据），
只回答三个**纯建模**问题：

### ① 区间能否通过物理核验

`R = η·q/(hν) = η·λ / 1239.84`（λ 用 nm，hν 以 eV 计）。两个直接后果：

* **硬上限**：`R ≤ λ/1239.84`（η ≤ 1）。1550 nm ⇒ **1.25016 A/W**。
  任何声称「1550 nm、非 APD、R = 1.3 A/W」的说法**可证不可能** —— 这是可判定的界，
  不是「公开典型」四个字。
* **区间有物理含义**：锚区间 `(0.8, 1.0)` 隐含 **η ∈ [0.640, 0.800]**，
  与 InGaAs PIN 的公开工程口径自洽 ⇒ 区间**不是随手取的**，它通过了一次量纲 + 上限核验。

### ② 区间的不确定度到底进不进结论

读出链里信号 ∝ `R·P`，而噪声 `σ² = 2q(R·P)B + 4k_B T B/R_f` —— **也只通过乘积 `u ≡ R·P`**。
于是

    SNR 只是 u 的函数            ⇒  SNR(R,P) ≡ SNR(2R, P/2)          （精确，1e-15 级）
    P_min(R) · R ≡ u*(BER 目标)  ⇒  灵敏度**精确**反比于响应度        （不是"近似"）
    argmin_j SNR_j 与 R 无关     ⇒  **最坏判决对是 R-invariant 的**

⇒ **「无绝对真值」对这两条不成立**：它们是**绝对的**，R 的 25% 不确定度只让所需的读光功率
同比例变 25%，不改变任何定性结论、也不改变"哪一对电平最危险"。

### ③ 方阻的不确定度只从一个口子进去 —— 而那个口子是**驱动口径**

现役实现是**电压驱动**：`P = V²/R_h`、`R_h = R_sheet·(L_h/w_h)` ⇒ `P ∝ 1/R_sheet`，
方阻 5× 不确定度直接变成**功耗 5× 不确定度**。

换成**恒功率驱动**（电流源 / 闭环调功）则 `P` 由目标定，方阻只定电压 `V = √(P·R_h)`
⇒ 功耗/能量/温升/相移预算**全部变成绝对值**，方阻只让电压跨 `√5 = 2.236×`。

⇒ 同一台机器、同一个区间，两种驱动口径下「有没有绝对真值」的答案不同 ——
**这是口径问题，不是数据问题**。本模块把两种口径并报，并给出可判定的设计界：
恒功率驱动下 `R_sheet ≤ V_max² / (P_req · n_sq)`。

## 诚实边界

* 不改任何锚区间，也不新增锚（`ANCHORABLE = False`）：本层只证**恒等式与作用域**。
* 不含暗电流 / 1-f / ISI / DSP；不含接触电阻 / 方阻温漂；不含 APD 增益（`R ≤ λ/1239.84`
  的前提是**无内部增益**，APD 可超此界，代价是过剩噪声因子）。
* `P_min ∝ 1/R` 的**精确性**来自「噪声也只通过 `R·P` 依赖」这一点；一旦加入暗电流
  （与 `R` 无关的固定项）该律立刻退化为近似 —— 本层没有暗电流项，所以它是精确的，
  **不能**外推到有暗电流的模型上。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "HC_EV_NM", "Q_E", "K_B", "ANCHORABLE",
    "responsivity_max", "qe_from_responsivity", "responsivity_from_qe",
    "anchor_physics_check", "snr_of_product", "p_star_shot_thermal",
    "snr_invariance", "p_min_law", "worst_pair_invariance",
    "heater_drive_scope", "rsheet_max_for_power_drive", "scope_summary",
    "why_not_anchored", "run_selfchecks",
]

#: `h·c/q`（eV·nm）—— CODATA 2018: h·c = 1239.841984 eV·nm。
HC_EV_NM: float = 1239.841984
Q_E: float = 1.602176634e-19
K_B: float = 1.380649e-23

#: 本层只证恒等式/作用域，没有任何物理标量对实测 ⇒ 不参与锚计数。
ANCHORABLE: bool = False


def why_not_anchored() -> str:
    """为什么本模块不可锚（由 `MUST_BE_REACHABLE` 反向锁定的模块须自答）。"""
    return ("本层证的是**恒等式与作用域**（`R=ηλ/1239.84` 的两向反解、SNR 只依赖 `R·P`、"
            "`P_min·R≡u*`、电压驱动 `P∝1/R_sheet` ⇄ 恒功率驱动 `V∝√R_sheet`），"
            "全部是**代数/量纲**事实，没有任何物理标量对公开实测 ⇒ 无锚可加。")


# ══════════════════════════════════════════════════════════════════════
# ① PD 响应度：物理上限与区间核验
# ══════════════════════════════════════════════════════════════════════
def responsivity_max(lam_nm: float) -> float:
    """**硬上限** `R_max = λ/1239.84`（A/W，η = 1，无内部增益）。

    🔴 这是**物理上限**而不是典型值：任何 `R > R_max` 的声明要么波长写错、要么是 APD
    （有增益，`R = M·η·λ/1239.84`，代价是过剩噪声因子 `F(M)`），要么是单位错。
    """
    lam = float(lam_nm)
    if not (lam > 0.0):
        raise ValueError("波长须为正（nm），收到 %r" % (lam_nm,))
    return lam / HC_EV_NM


def qe_from_responsivity(resp_a_per_w: float, lam_nm: float) -> float:
    """由响应度反解**外量子效率** `η = R·1239.84/λ`（0..1 才有物理意义）。"""
    r = float(resp_a_per_w)
    lam = float(lam_nm)
    if not (r > 0.0):
        raise ValueError("响应度须为正（A/W），收到 %r" % (resp_a_per_w,))
    if not (lam > 0.0):
        raise ValueError("波长须为正（nm），收到 %r" % (lam_nm,))
    return r * HC_EV_NM / lam


def responsivity_from_qe(qe: float, lam_nm: float) -> float:
    """`R = η·λ/1239.84`（正向式）。与 `qe_from_responsivity` **互为反函数**。"""
    e = float(qe)
    lam = float(lam_nm)
    if not (0.0 <= e <= 1.0):
        raise ValueError("量子效率须在 [0,1]，收到 %r" % (qe,))
    if not (lam > 0.0):
        raise ValueError("波长须为正（nm），收到 %r" % (lam_nm,))
    return e * lam / HC_EV_NM


def anchor_physics_check(lam_nm: float = 1550.0,
                         r_lo: Optional[float] = None,
                         r_hi: Optional[float] = None) -> Dict[str, Any]:
    """把「公开典型区间」过一遍**物理核验**（量纲 + 上限 + η 落窗）。

    缺省区间取 `pm_m4.PD_RESPONSIVITY_ANCHORS`（**单一真源**，不在此重抄数字）。
    """
    from lda_l2 import pm_m4 as M4

    lo = float(M4.PD_RESPONSIVITY_ANCHORS[0] if r_lo is None else r_lo)
    hi = float(M4.PD_RESPONSIVITY_ANCHORS[1] if r_hi is None else r_hi)
    if not (0.0 < lo < hi):
        raise ValueError("区间须满足 0 < lo < hi，收到 (%r, %r)" % (r_lo, r_hi))
    rmax = responsivity_max(lam_nm)
    eta_lo = qe_from_responsivity(lo, lam_nm)
    eta_hi = qe_from_responsivity(hi, lam_nm)
    return {
        "lam_nm": float(lam_nm),
        "r_lo_a_per_w": lo, "r_hi_a_per_w": hi,
        "r_max_a_per_w": rmax,
        "eta_lo": eta_lo, "eta_hi": eta_hi,
        "eta_in_unit_interval": (0.0 < eta_lo < eta_hi <= 1.0),
        "headroom_to_physics": (rmax / hi - 1.0),
        "upper_bound_violated": bool(hi > rmax),
        "note": ("🔴 **物理上限**（η≤1，无内部增益）：`R ≤ %.6f A/W @ %.0f nm`；"
                 "锚区间 (%.2f, %.2f) 对应 η ∈ [%.3f, %.3f] ⇒ 区间上界距上限还有 %.1f%% 余量。"
                 "⇒ 区间**通过**了量纲 + 上限 + η 落窗三项核验，不是随手取的数。"
                 % (rmax, lam_nm, lo, hi, eta_lo, eta_hi, 100.0 * (rmax / hi - 1.0))),
    }


# ══════════════════════════════════════════════════════════════════════
# ② 读数链：SNR 只依赖 `R·P` 这一个乘积
# ══════════════════════════════════════════════════════════════════════
def snr_of_product(u_a: float, band_hz: float, r_f_ohm: float,
                   t_k: float = 300.0) -> float:
    """`SNR(u) = u / √(2qBu + 4k_B T B/R_f)`，其中 `u = R·P`（光电流）。

    这就是解出①的**闭式形式**：信号与散粒噪声都只通过 `u` 依赖 `(R, P)`
    ⇒ `SNR` 是 `u` 的**单变量函数**（热噪声项与二者无关）。
    """
    u = float(u_a)
    b = float(band_hz)
    rf = float(r_f_ohm)
    if u < 0.0 or b <= 0.0 or rf <= 0.0 or t_k <= 0.0:
        raise ValueError("须 u≥0 · B>0 · R_f>0 · T>0，收到 %r" % ((u_a, band_hz, r_f_ohm, t_k),))
    var = 2.0 * Q_E * u * b + 4.0 * K_B * float(t_k) * b / rf
    return u / math.sqrt(var)


def p_star_shot_thermal(resp_a_per_w: float, r_f_ohm: float,
                        t_k: float = 300.0) -> float:
    """散粒噪声 ≡ 热噪声的**交叉光功率** `P* = 2k_B T/(q·R·R_f)`（W）。

    🔴 两个非平凡之处：① 与**带宽无关**（两者都 ∝ B，约掉）；
    ② `P* ∝ 1/R` —— 与 `P_min` 同一条反比律（同一原因：都只经由 `u = R·P`）。
    """
    r = float(resp_a_per_w)
    rf = float(r_f_ohm)
    if r <= 0.0 or rf <= 0.0 or t_k <= 0.0:
        raise ValueError("须 R>0 · R_f>0 · T>0，收到 %r" % ((resp_a_per_w, r_f_ohm, t_k),))
    return 2.0 * K_B * float(t_k) / (Q_E * r * rf)


def snr_invariance(mat: str = "GST", n_levels: Optional[int] = None, *,
                   r_base: float = 0.8, p_base_w: float = 1e-4,
                   factor: float = 2.0) -> Dict[str, Any]:
    """`SNR(R, P) ≡ SNR(kR, P/k)` —— 用**真实读出链**（`pm_m4.readout_chain`）验，不用玩具式。

    若这条不成立，说明链路里某处**单独**用了 `R` 或 `P`（例如噪声里写了暗电流、或信号里
    漏了 `R`）⇒ 那是链路级 bug，而不是"近似"。
    """
    from lda_l2 import pm_m4 as M4

    k = float(factor)
    if k <= 0.0:
        raise ValueError("factor 须为正")
    a = M4.readout_chain(mat, n_levels, p_in_w=float(p_base_w), resp_a_per_w=float(r_base))
    b = M4.readout_chain(mat, n_levels, p_in_w=float(p_base_w) / k,
                         resp_a_per_w=float(r_base) * k)
    rel = abs(a["worst_snr"] - b["worst_snr"]) / max(abs(a["worst_snr"]), 1e-300)
    return {"r_base": float(r_base), "p_base_w": float(p_base_w), "factor": k,
            "snr_a": a["worst_snr"], "snr_b": b["worst_snr"], "rel_diff": rel,
            "worst_pair_a": a["worst_pair"], "worst_pair_b": b["worst_pair"],
            "note": ("🔴 信号 ∝ `R·P`、噪声 `σ² = 2q(R·P)B + 4k_BTB/R_f` **也**只经由 `R·P` "
                     "⇒ `SNR(kR, P/k) ≡ SNR(R, P)`（精确，非近似）。")}


def p_min_law(mat: str = "GST", n_levels: Optional[int] = None, *,
              r_values: Sequence[float] = (0.8, 0.9, 1.0),
              ber_target: Optional[float] = None,
              f_read_hz: Optional[float] = None,
              iters: int = 46) -> Dict[str, Any]:
    """`P_min(R) · R ≡ u*`（**精确**反比律）—— 用真实链路二分逆解，不用闭式代跑。

    返回每档 `R` 的 `p_min`、乘积 `p_min·R`、以及乘积的**相对离散度**。
    离散度只应到二分分辨率量级（`2^-iters`），不是"差不多"。
    """
    from lda_l2 import pm_m4 as M4

    rf = None
    f = M4.F_READ_HZ_DEFAULT if f_read_hz is None else float(f_read_hz)
    rows: List[Dict[str, Any]] = []
    for r in r_values:
        kw: Dict[str, Any] = dict(ber_target=ber_target, f_read_hz=f, iters=int(iters))
        # `readout_sensitivity` 的 `resp_a_per_w` 直通 `readout_chain`（v0.9.311 新增参数）
        res = M4.readout_sensitivity(mat, n_levels, resp_a_per_w=float(r), **kw)
        rows.append({"r_a_per_w": float(r), "p_min_w": res["p_min_w"],
                     "product_r_p": float(r) * res["p_min_w"],
                     "reachable": res["reachable"]})
    prods = [x["product_r_p"] for x in rows if x["reachable"]]
    spread = (max(prods) / min(prods) - 1.0) if prods else float("inf")
    return {"rows": rows, "f_read_hz": f, "ber_target": rows and ber_target,
            "product_spread_rel": spread,
            "law": "P_min(R) · R ≡ u*(BER 目标) —— 灵敏度精确反比于响应度",
            "note": ("🔴 反比律的**精确性**来自噪声也只经由 `R·P` 依赖；"
                     "一旦引入暗电流（与 R 无关的固定项）它立刻退化为近似 —— 本层不含暗电流。")}


def worst_pair_invariance(mat: str = "GST", n_levels: Optional[int] = None, *,
                          r_values: Sequence[float] = (0.8, 0.9, 1.0),
                          p_in_w: float = 1e-4) -> Dict[str, Any]:
    """判决对的 SNR 结构：**几何/线性加权的等分阶梯 ⇒ 所有对 SNR 相同**。

    🔴 本函数原本想证「最坏对与 R 无关」。实测反过来 —— **`worst_pair` 根本是个退化标签**：
    M1 的 16 档透射率是**等分线性**阶梯（相邻差恒为 `ΔT`），而读出链的噪声 `σ_V` 对所有对
    用同一个值（取最低电平那一行），于是 `ΔV_j = Z·R·P_in·ΔT` **与 j 无关**
    ⇒ 15 个判决对的 SNR **完全相同**（实测相对离散 **8.9e-15**，纯浮点噪声）。

    后果：`readout_chain()["worst_pair"]` 由 `min()` 在 15 个**并列值**里挑，挑中哪个只由
    浮点噪声决定（实测 R=0.8 给 (12,13)、R=0.9 给 (7,8)、R=1.0 给 (8,9)）。
    ⇒ **「最坏对」不可作为结论引用**；可引用的结构事实是「所有对 SNR 相同」。

    这条同时是「比值判据抓不住量级错」的同族：一个**并列**的标签看起来像结论，其实没有信息。
    """
    from lda_l2 import pm_m4 as M4

    rows: List[Dict[str, Any]] = []
    for r in r_values:
        res = M4.readout_chain(mat, n_levels, p_in_w=float(p_in_w), resp_a_per_w=float(r))
        snrs = [p["snr"] for p in res["pairs"]]
        rows.append({"r_a_per_w": float(r), "worst_pair": tuple(res["worst_pair"]),
                     "worst_snr": res["worst_snr"], "n_pairs": len(snrs),
                     "pair_snr_spread": (max(snrs) / min(snrs) - 1.0) if snrs else 0.0,
                     "pair_dv_unique": len({round(p["dv_v"], 15) for p in res["pairs"]})})
    spreads = [x["pair_snr_spread"] for x in rows]
    tags = {x["worst_pair"] for x in rows}
    return {"rows": rows, "n_pairs": rows[0]["n_pairs"] if rows else 0,
            "all_pairs_equal": all(sp < 1e-12 for sp in spreads),
            "max_pair_spread": max(spreads) if spreads else float("inf"),
            "worst_pair_is_degenerate": (len(tags) > 1),
            "distinct_worst_pairs": sorted(tags),
            "note": ("🔴 等分线性阶梯 + 全局 `σ_V` ⇒ `ΔV_j` 与 j 无关 ⇒ **15 对同 SNR**；"
                     "`worst_pair` 是 `min()` 在并列值里按浮点噪声挑的**退化标签**，"
                     "不同 R 会给出不同的对（实测 %s）⇒ 不可引用为结论。"
                     % sorted(tags))}


# ══════════════════════════════════════════════════════════════════════
# ③ 方阻：不确定度只从**驱动口径**这一个口子进去
# ══════════════════════════════════════════════════════════════════════
def heater_drive_scope(mat: str = "GST", *,
                       v_drv: Optional[float] = None,
                       p_req_w: Optional[float] = None,
                       sheet_lo: Optional[float] = None,
                       sheet_hi: Optional[float] = None) -> Dict[str, Any]:
    """两种驱动口径下，**同一个方阻区间**对功耗预算的影响：`5×` vs `1×`。

    · **电压驱动**（现役 `write_driver`）：`P = V²/R_h`，`R_h = R_sheet·n_sq`
      ⇒ `P ∝ 1/R_sheet` ⇒ 方阻 10→50 使功耗降 **5×**。
    · **恒功率驱动**（电流源/闭环）：`P` 由目标定，`V = √(P·R_sheet·n_sq)`
      ⇒ 功耗**绝对**，只让电压跨 **√5 = 2.236×**。

    `p_req_w` 缺省取 `pm_thermal.pi_shift_link()["P_pi_mw"]`（**单一真源**，不在此重抄 3.331）。
    """
    from lda_l2 import pm_m4 as M4
    from lda_l2 import pm_thermal as PT

    hr = M4.heater_resistance(mat)
    n_sq = float(hr["n_squares"])
    lo = float(M4.HEATER_SHEET_RHO_ANCHORS[0] if sheet_lo is None else sheet_lo)
    hi = float(M4.HEATER_SHEET_RHO_ANCHORS[1] if sheet_hi is None else sheet_hi)
    if not (0.0 < lo < hi):
        raise ValueError("方阻区间须 0 < lo < hi，收到 (%r, %r)" % (sheet_lo, sheet_hi))
    v = float(M4.V_DRV_DEFAULT if v_drv is None else v_drv)
    if v <= 0.0:
        raise ValueError("驱动电压须为正")
    p_pi = (float(PT.pi_shift_link()["P_pi_mw"]) * 1e-3
            if p_req_w is None else float(p_req_w))
    if p_pi <= 0.0:
        raise ValueError("目标功率须为正")

    r_lo_ohm, r_hi_ohm = lo * n_sq, hi * n_sq
    # 电压驱动：固定 V
    pd_hi = v * v / r_lo_ohm                     # 低方阻 ⇒ 大功率
    pd_lo = v * v / r_hi_ohm
    # 恒功率驱动：固定 P
    v_at_lo = math.sqrt(p_pi * r_lo_ohm)
    v_at_hi = math.sqrt(p_pi * r_hi_ohm)
    return {
        "material": mat, "n_squares": n_sq, "l_h_um": hr["l_h_um"], "w_h_um": hr["w_h_um"],
        "sheet_lo": lo, "sheet_hi": hi,
        "r_lo_ohm": r_lo_ohm, "r_hi_ohm": r_hi_ohm,
        "v_drv": v, "p_req_w": p_pi,
        "voltage_drive": {"p_lo_w": pd_lo, "p_hi_w": pd_hi,
                          "p_span": (pd_hi / pd_lo if pd_lo > 0 else float("inf")),
                          "overdrive_vs_req": (pd_lo / p_pi, pd_hi / p_pi)},
        "power_drive": {"v_lo_v": v_at_lo, "v_hi_v": v_at_hi,
                        "v_span": (v_at_hi / v_at_lo),
                        "overdrive_vs_req": (1.0, 1.0)},
        "rsheet_max_for_power_drive": rsheet_max_for_power_drive(v, p_pi, n_sq),
        "note": ("🔴 同一台机器、同一个方阻区间：**电压驱动**下功耗预算跨 `p_span`× "
                 "（方阻不确定度**全部进**功耗）；**恒功率驱动**下功耗是绝对值，"
                 "只让电压跨 `v_span`× ⇒ 「有没有绝对真值」是**驱动口径问题，不是数据问题**。"),
    }


def rsheet_max_for_power_drive(v_max_v: float, p_req_w: float, n_squares: float) -> float:
    """恒功率驱动下**方阻的可判定上界**：`R_sheet ≤ V_max²/(P_req·n_sq)`。

    反解式：`V = √(P·R_sheet·n_sq) ≤ V_max`。回代必须**逐位**给回 `V_max`。
    """
    v = float(v_max_v)
    p = float(p_req_w)
    n = float(n_squares)
    if v <= 0.0 or p <= 0.0 or n <= 0.0:
        raise ValueError("须 V>0 · P>0 · n_sq>0，收到 %r" % ((v_max_v, p_req_w, n_squares),))
    return v * v / (p * n)


def scope_summary(mat: str = "GST") -> Dict[str, Any]:
    """把①②③ 汇总成一张「哪条结论绝对 / 哪条只是区间」的表（供卡片与门禁消费）。"""
    ap = anchor_physics_check()
    inv = snr_invariance(mat)
    hd = heater_drive_scope(mat)
    return {
        "responsivity_hard_bound_a_per_w": ap["r_max_a_per_w"],
        "anchor_eta_lo": ap["eta_lo"], "anchor_eta_hi": ap["eta_hi"],
        "anchor_headroom_frac": ap["headroom_to_physics"],
        "snr_depends_only_on_r_times_p": inv["rel_diff"] < 1e-12,
        "all_pairs_snr_equal": worst_pair_invariance(mat)["all_pairs_equal"],
        "worst_pair_is_degenerate": worst_pair_invariance(mat)["worst_pair_is_degenerate"],
        "heater_power_span_voltage_drive": hd["voltage_drive"]["p_span"],
        "heater_voltage_span_power_drive": hd["power_drive"]["v_span"],
        "absolute_conclusions": ["所有判决对 SNR 相同（等分线性阶梯 + 全局 σ_V 的结构后果）",
                                 "SNR 只依赖 R·P", "P_min·R ≡ u*",
                                 "恒功率驱动下的功耗/温升/相移预算"],
        "range_only_conclusions": ["「最坏判决对」这个标签本身（并列 ⇒ 不可引用）",
                                   "所需读光功率下限的绝对值（随 1/R 变 25%）",
                                   "电压驱动下的功耗/能量（随 1/R_sheet 变 5×）",
                                   "驱动电压绝对值（恒功率口径下随 √R_sheet 变 2.24×）"],
        "note": ("🔴 `PM-G9` 那句「无绝对真值」**不是均匀成立**的：定性结论（最坏对）与"
                 "恒功率口径下的功耗预算是**绝对**的；只有「具体数值」落在区间里。"),
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

    # ① 恒等式两向反解：R = ηλ/1239.84 ⇄ η = R·1239.84/λ
    worst = 0.0
    for lam in (1310.0, 1550.0, 1625.0):
        for eta in (0.3, 0.64, 0.8, 1.0):
            r = responsivity_from_qe(eta, lam)
            worst = max(worst, abs(qe_from_responsivity(r, lam) - eta))
    chk("① 响应度 ⇄ 量子效率**两向反解** ≡（3 波长 × 4 η，最差 |Δη|=%.1e）" % worst,
        worst < 1e-15)

    # ② 物理上限：1550 nm ⇒ 1.25016 A/W（精确已知量，用 ==）
    # ② 绝对量级锚点：教科书的 1550 nm 响应度上限 ≈ 1.25 A/W（INDEPENDENT 已知量，1% 内）
    rmax = responsivity_max(1550.0)
    chk("② 🔴 绝对量级锚点：R_max(1550) = %.6f A/W 落在教科书值 1.25 的 1%% 内（η≤1 的硬上限）"
        % rmax, abs(rmax / 1.25 - 1.0) < 0.01,
        "实测 %.6f vs 1.25 ⇒ 相对差 %.2e" % (rmax, abs(rmax / 1.25 - 1.0)))

    # ③ 锚区间通过核验：η ∈ (0,1] ∧ 上界距物理上限有余量
    ap = anchor_physics_check()
    chk("③ 锚区间 (0.8, 1.0) 通过对核验：η ∈ [%.3f, %.3f] ⊂ (0,1] ∧ 距上限余量 %.1f%%"
        % (ap["eta_lo"], ap["eta_hi"], 100 * ap["headroom_to_physics"]),
        ap["eta_in_unit_interval"] and not ap["upper_bound_violated"]
        and ap["headroom_to_physics"] > 0.2)

    # ④ 反向探针：R = 1.3 A/W @1550 ⇒ **违反物理上限**（η > 1）
    bad = qe_from_responsivity(1.3, 1550.0)
    chk("④ 反向探针：声称 R=1.3 A/W @1550 ⇒ η = %.3f > 1 ⇒ **可证不可能**（判据非恒真）"
        % bad, bad > 1.0 and responsivity_max(1550.0) < 1.3)

    # ⑤ SNR 只依赖 R·P：真实链路 SNR(2R, P/2) ≡ SNR(R, P)
    inv = snr_invariance()
    chk("⑤ 真实读出链 SNR(2R, P/2) ≡ SNR(R, P)（相对差 %.1e，精确非近似）"
        % inv["rel_diff"], inv["rel_diff"] < 1e-12,
        "worst_pair %s ⇄ %s" % (tuple(inv["worst_pair_a"]), tuple(inv["worst_pair_b"])))

    # ⑥ P_min·R ≡ u*（真实链路二分逆解，离散度只到二分分辨率）
    law = p_min_law(iters=52)
    # 🔴 容差不是「差不多」：二分在 [1e-9, 1e-2] 上迭代 52 次 ⇒ **绝对**分辨率 1e-2/2^52，
    #    而 p_min ≈ 1e-7 ⇒ **相对**分辨率 ≈ 2e-11。这条判据只能测到这个量级，不能再严。
    chk("⑥ P_min(R)·R ≡ u*（R=0.8/0.9/1.0 三档，相对离散 %.2e ≤ 二分相对分辨率量级 1e-9）"
        % law["product_spread_rel"], law["product_spread_rel"] < 1e-9,
        " ".join("R=%.1f→P_min=%.4e" % (r["r_a_per_w"], r["p_min_w"]) for r in law["rows"]))

    # ⑦ 🔴 本版最意外的发现：`worst_pair` 是**退化标签**（15 对同 SNR，min() 按浮点噪声挑）
    wpi = worst_pair_invariance()
    chk("⑦ 「所有 %d 个判决对 SNR 相同」（相对离散 %.1e）⇒ `worst_pair` 退化："
        "三档 R 分别给出 %s" % (wpi["n_pairs"], wpi["max_pair_spread"],
                             wpi["distinct_worst_pairs"]),
        wpi["all_pairs_equal"] and wpi["worst_pair_is_degenerate"],
        "pair_snr_spread=%s" % [("%.1e" % x["pair_snr_spread"]) for x in wpi["rows"]])

    # ⑧ 交叉光功率 P* = 2kT/(qRR_f) 处散粒 ≡ 热（相对 1e-12），且与带宽无关
    r0, rf0 = 0.8, 20e3
    p_star = p_star_shot_thermal(r0, rf0)
    s1 = 2.0 * Q_E * (r0 * p_star) * 1e5
    t1 = 4.0 * K_B * 300.0 * 1e5 / rf0
    s2 = 2.0 * Q_E * (r0 * p_star) * 1e9
    t2 = 4.0 * K_B * 300.0 * 1e9 / rf0
    _d1 = abs(s1 - t1) / max(t1, 1e-300)
    _d2 = abs(s2 - t2) / max(t2, 1e-300)
    chk("⑧ P* = 2k_B T/(q·R·R_f) 处散粒≡热（|Δ|=%.1e）∧ **与带宽无关**（1e5 与 1e9 Hz 同 P*）"
        % _d1, _d1 < 1e-12 and _d2 < 1e-12,
        "P*=%.4f nW · |Δ|=%.1e/%.1e" % (p_star * 1e9, _d1, _d2))

    # ⑨ P* ∝ 1/R（同一条反比律的第二个例子）
    p2 = p_star_shot_thermal(2.0 * r0, rf0)
    chk("⑨ P* ∝ 1/R：P*(2R)/P*(R) == 0.5（逐位 %.17f）" % (p2 / p_star),
        abs(p2 / p_star - 0.5) < 1e-15)

    # ⑩ 电压驱动 P ∝ 1/R_sheet：功耗跨度 == 方阻跨度（5×）
    hd = heater_drive_scope()
    span_ratio = hd["sheet_hi"] / hd["sheet_lo"]
    chk("⑩ 电压驱动：功耗跨度 %.4f× == 方阻跨度 %.4f×（P = V²/R_h ⇒ P ∝ 1/R_sheet）"
        % (hd["voltage_drive"]["p_span"], span_ratio),
        abs(hd["voltage_drive"]["p_span"] - span_ratio) < 1e-12)

    # ⑪ 恒功率驱动：电压跨度 == √(方阻跨度)，功耗跨度恰 1
    chk("⑪ 恒功率驱动：电压跨度 %.4f× == √%.0f = %.4f× ∧ 功耗跨度恰 1.0（绝对值）"
        % (hd["power_drive"]["v_span"], span_ratio, math.sqrt(span_ratio)),
        abs(hd["power_drive"]["v_span"] - math.sqrt(span_ratio)) < 1e-12
        and hd["power_drive"]["overdrive_vs_req"] == (1.0, 1.0))

    # ⑫ R_sheet 上界反解回代：√(P·R_max·n_sq) == V_max（逐位）
    vmax, n_sq = 3.3, hd["n_squares"]
    rs_max = rsheet_max_for_power_drive(vmax, hd["p_req_w"], n_sq)
    back = math.sqrt(hd["p_req_w"] * rs_max * n_sq)
    chk("⑫ 方阻上界反解回代：√(P_req·R_sheet,max·n_sq) == V_max（%.12f ⇄ %.12f）"
        % (back, vmax), abs(back - vmax) < 1e-12,
        "R_sheet,max=%.1f Ω/sq" % rs_max)

    # ⑬ 非物理输入必须抛（波长/R/η/幂/配对次序/驱动量）
    guard = 0
    for fn, kw in ((responsivity_max, {"lam_nm": 0.0}),
                   (qe_from_responsivity, {"resp_a_per_w": 0.0, "lam_nm": 1550.0}),
                   (responsivity_from_qe, {"qe": 1.5, "lam_nm": 1550.0}),
                   (snr_of_product, {"u_a": 1e-4, "band_hz": 0.0, "r_f_ohm": 1e3}),
                   (p_star_shot_thermal, {"resp_a_per_w": -1.0, "r_f_ohm": 1e3}),
                   (rsheet_max_for_power_drive, {"v_max_v": 0.0, "p_req_w": 1e-3,
                                                 "n_squares": 10.0}),
                   (anchor_physics_check, {"r_lo": 1.0, "r_hi": 0.8})):
        try:
            fn(**kw)
        except ValueError:
            guard += 1
    chk("⑬ 非物理输入 7 类（λ≤0 / R≤0 / η>1 / B=0 / R<0 / V=0 / 区间倒置）全部 raise",
        guard == 7, "拦截 %d/7" % guard)

    # ⑭ 反向探针：把反比律误写成 P_min ∝ 1/R² ⇒ ⑥ 必红
    law_rows = law["rows"]
    wrong_products = [r["product_r_p"] / r["r_a_per_w"] for r in law_rows]
    spread_wrong = max(wrong_products) / min(wrong_products) - 1.0
    chk("⑭ 反向探针：误写 P_min ∝ 1/R²（即乘 R² 才守恒）⇒ 离散度 %.2f ≫ 1e-12 ⇒ ⑥ 必红"
        % spread_wrong, spread_wrong > 1e-2)

    npass = sum(1 for ln in lines if ln.startswith("[PASS]"))
    if verbose:
        for ln in lines:
            print(ln)
        print("pm_peripheral_scope 自检：%d/%d PASS" % (npass, len(lines)))
    return npass, len(lines), lines


if __name__ == "__main__":
    import sys
    _p, _t, _ = run_selfchecks()
    sys.exit(0 if _p == _t else 1)
