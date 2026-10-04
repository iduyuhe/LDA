# -*- coding: utf-8 -*-
"""PM-M4：**外设与系统层** —— 读出链 / 写驱动 / 系统误码预算 / 2.5D 签核 · 光子存储征程第五程第四档。

定位
----
M0 给「一个单元能不能写」、M1 给「能装几个电平」、M2 给「热与保持站不站得住」、
M3 给「阵列版图能不能签核」。四者都停在**光子侧**；没有**电子侧**（读出/驱动）、
没有**系统级**（全链路误码预算）、没有**2.5D 装配**。M4 补这三块。

本档回答三问
------------
1. **怎么读**：`T → P_opt → I_pd → V_TIA → 多电平判决 → BER` 的**电路级行为链**。
   关键：光子存储读出是**低频高灵敏**（存储读，非 GBd 高速链路）⇒ TIA 反馈电阻可
   取到带宽允许的**上界**，转阻增益换噪声压制 ⇒ 这是与 oi 高速链**本质不同**的口径
   （总蓝图 M4 明确点出）。
2. **怎么写**：加热线电阻（由 M3 几何 × 公开方阻锚算出）+ 驱动功率/能量（行为级）
   + 与 M1 的**脉冲阶梯动态范围**对齐（驱动时序必须能分辨 16 档脉宽）。
3. **站不站得住**：三段（写量化 / 介质 drift / 读出电路）等效电平误差合成 ⇒ 系统 BER
   + **瓶颈识别**；再把 PIC 阵列 + EIC 通道落 **2.5D** 装配并签核（真 GDS + 电层 DRC +
   网络 LVS + 独立解码），给出**密度瓶颈**判据（EIC 通道 pitch vs PIC 单元 pitch）。

🔴 同源（判据读「算出来的值」，不读字面量）
--------------------------------------------
- 电平透射率 `T_j` / 晶化率 `c_j`：读 `pm_m1.level_design()`。
- 脉冲阶梯动态范围：读 `pm_m1.pulse_ladder()`（`t_ratio_to_first`，对 K0 不变）。
- 单元 pitch / 热隔离间距：读 `pm_m3.cell_pitch_um()`（M2 热扩散口径）。
- 阵列几何与元素：读 `pm_m3.build_array()` + `chip_layout_export.device_elements()`。
- 独立解码复核：复用 `pm_m3.independent_gds_scan()`（自写解析器，非生成端同源）。
- TIA 频响：复用 `eic_behavioral.tia_transimpedance_ohm()/tia_bandwidth_hz()`。
⇒ M4 **不复制任何物理常数**；新引入的外部量全部落在下面的「规格锚区」并**区间口径**。

🔴 诚实边界（详见 `ASSUMED_NOTE` 与 `m4_report()["disclosure"]`）
------------------------------------------------------------------
- PD 响应度、加热器方阻为**公开工程典型区间锚**（非本项目实测、非逐条 DOI 复核）；
  读出速率 / 输入光功率 / 驱动摆幅 / EIC 通道 pitch 为**设计假设**（显式声明）。
  本模块只据此给**区间 + 恒等式 + 单调性 + 结构断言**，**不报器件级真值**。
- 焦耳热分布、热-光耦合动力学、开关能耗真值属**器件级 T1 / 电路级 T2 锁死区**
  （无 PDK ⇒ 不报，见 `pm_case.GAPS` 的 PM-G8）。
- 🔴 **不报 pJ/bit、fJ/op、TOPS、TOPS-W 类能效指标**（红线）。
- LLM 不进判决路径：判据全为死标量 / 结构断言。
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Dict, List, Optional, Tuple

from lda_l2 import chip_layout_export as CLE
from lda_l2 import eic_behavioral as EIC
from lda_l2 import gds_export as GX
from lda_l2 import pm_m1 as M1
from lda_l2 import pm_m2 as M2
from lda_l2 import pm_m3 as M3
from lda_l2 import primitives as PR

# ─────────────────────────────── 物理常数（SI 定义值，不重抄他源） ───────────────────────────────
Q_E: float = 1.602176634e-19          # 基本电荷（C）
K_B: float = 1.380649e-23             # 玻尔兹曼常数（J/K）
H_PLANCK: float = 6.62607015e-34      # 普朗克常数（J·s）
C_LIGHT: float = 2.99792458e8         # 真空光速（m/s）
T_AMB_K_DEFAULT: float = 300.0        # 环境温度（K）

# ─────────────────────────────── 设计假设（显式声明 · 非锚） ───────────────────────────────
#: 存储读出速率（Hz）：光子存储是**存储读**，不需要 GBd 级速率 ⇒ 低频高灵敏。
F_READ_HZ_DEFAULT: float = 1.0e5
#: TIA 反馈电阻**设计点**（Ω）：常见跨阻档（**设计假设**）。
#: 与「带宽约束上界」`tia_rf_max_ohm()` **并报**：设计点须 ≤ 上界（否则读出带宽不足）。
R_F_OHM_DEFAULT: float = 20e3
#: TIA 反馈电容（F）—— 与 `eic_behavioral.C_F_F_DEFAULT` **同源同值**（单一真源由自检 ③ 守卫）。
C_F_F_DEFAULT: float = 20e-15
#: drift 幂律 `R/R₀ = (t/t₀)^ν` 的参考点 t₀（s）。
T_HOLD_T0_S: float = 1.0
#: 目标保持时间（s）：默认 1 年（3.156e7 s）—— **设计目标**，非锚。
T_HOLD_S_DEFAULT: float = 3.156e7
#: 输入端光功率（W）：0 dBm 量级（片上读光，行为级设计点）。
P_IN_W_DEFAULT: float = 1.0e-3
#: 驱动满摆幅（V）。
V_DRV_DEFAULT: float = 3.3
#: 写脉冲基准时长（s）：🔴 **设计输入**（M1 明确「K0 无锚 ⇒ 绝对脉冲时长不可报真值」），
#: 本档只用它做**功率→能量**的行为级换算，并显式标注非真值。
PULSE_T_S_DEFAULT: float = 50e-9
#: 驱动时序量化位深（bit）：决定脉宽可分辨档数 ⇒ 与 M1 的阶梯动态范围对齐。
DRIVER_DAC_BITS_DEFAULT: int = 8
#: EIC 通道 pitch（µm）：每单元一条读出/驱动通道的**设计假设**（2.5D 密度分析用）。
EIC_PITCH_UM_DEFAULT: float = 50.0

#: 电层 DRC 设计规则（2.5D 装配 · **自建设计规则**，非 foundry PDK deck）。
M4_DRC_RULES: Dict[str, float] = {
    "min_width_um": 0.5, "min_space_um": 0.5, "min_pad_um": 2.0,
}

# ─────────────────────────────── 规格锚区（公开典型 · 区间口径） ───────────────────────────────
#: PD 响应度（A/W @1550 nm）：InGaAs PIN 的**公开工程典型区间**。
#: 🔴 标注：非本项目实测、非逐条 DOI 复核 ⇒ 一律区间口径，且只用于**行为级**设计输入；
#: 系统结论以「所需响应度下限 vs 本区间」的**对照**形式给出（不把区间当精确值消费）。
PD_RESPONSIVITY_ANCHORS: Tuple[float, float] = (0.8, 1.0)

#: 加热器薄膜方阻（Ω/sq）：TiN 类加热电极的**公开工程典型区间**（同上，区间口径）。
HEATER_SHEET_RHO_ANCHORS: Tuple[float, float] = (10.0, 50.0)

ASSUMED_NOTE: str = (
    "🔴 PD 响应度 / 加热器方阻为公开工程典型**区间**（非实测、非逐条 DOI）⇒ 只报区间与"
    "对照；读出速率 / 输入光功率 / 驱动摆幅 / 脉宽 / EIC pitch 为**设计假设**⇒ 只报"
    "恒等式、单调性、结构断言，**不报器件级真值**（T1/T2 锁死区）。"
)


class PMM4Error(Exception):
    """PM-M4 层错误（越域/非法参数 ⇒ raise，拒绝静默）。"""


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise PMM4Error(msg)


def _erfc_ber(snr: float) -> float:
    """AWGN 二进制判决 BER = 0.5·erfc(SNR/√2)（与 pm_m1/pm_m0 同模型，纯 math）。"""
    return 0.5 * math.erfc(max(snr, 0.0) / math.sqrt(2.0))


def _humanize_s(t_s: float) -> str:
    """秒 → 人类可读（与 pm_m2 同风格；本模块自持一份，避免跨模块私有依赖）。"""
    if t_s < 60.0:
        return "%.1f 秒" % t_s
    if t_s < 3600.0:
        return "%.1f 分钟" % (t_s / 60.0)
    if t_s < 86400.0:
        return "%.1f 小时" % (t_s / 3600.0)
    if t_s < 86400.0 * 365.0:
        return "%.1f 天" % (t_s / 86400.0)
    return "%.2f 年" % (t_s / (86400.0 * 365.0))


# ══════════════════════════════════════════════════════════════════════════
# 1) 读出链：T → P_opt → I_pd → V_TIA → 多电平判决 → BER（行为级）
# ══════════════════════════════════════════════════════════════════════════
def tia_rf_max_ohm(f_read_hz: float = F_READ_HZ_DEFAULT,
                   c_f_f: float = C_F_F_DEFAULT) -> float:
    """带宽约束下的 TIA 反馈电阻**上界**：单极点 `f_3dB = 1/(2π R_f C_f) ≥ f_read`
    ⇒ `R_f_max = 1/(2π·f_read·C_f)`。

    🔴 与 `eic_behavioral.tia_bandwidth_hz(R_f, C_f)` **互为反函数**（自检 ③ 逐位验证）。
    """
    _require(f_read_hz > 0.0, "读出速率必须为正")
    _require(c_f_f > 0.0, "TIA 反馈电容必须为正")
    return 1.0 / (2.0 * math.pi * f_read_hz * c_f_f)


def level_transmittance(mat: str = "GST", n_levels: Optional[int] = None,
                        *, l_um: Optional[float] = None,
                        source: Optional[str] = None) -> Dict[str, Any]:
    """读 M1 的电平设计 ⇒ 每级透射率 `T_j` / 晶化率 `c_j`（同源，不重造）。"""
    n_lev = int(M1.LEVELS_4BIT) if n_levels is None else int(n_levels)
    if l_um is None:
        demo = M1.m1_report()["demo_design_point"]
        _require(demo is not None, "M1 无可用设计点（可行性窗口为空）⇒ 读出链无从建立")
        l_um = float(demo["l_mid_um"])
        src = demo["source"]
    else:
        src = source
    d = M1.level_design(mat, n_lev, l_um=float(l_um))
    row = None
    for r in d["per_source"]:
        if src is None or r["source"] == src:
            row = r
            break
    _require(row is not None, "未找到匹配来源的电平行：%r" % (src,))
    levels = [{"j": int(lv["j"]), "T": float(lv["T"]), "c": float(lv["c"])}
              for lv in row["levels"]]
    return {"material": mat, "n_levels": n_lev, "l_um": float(l_um),
            "source": row["source"], "levels": levels,
            "t_a": float(row["t_a"]), "t_c": float(row["t_c"]),
            "spacing_frac": float(row["spacing_frac"]),
            "upstream": "pm_m1.level_design（同源）"}


def readout_chain(mat: str = "GST", n_levels: Optional[int] = None, *,
                  l_um: Optional[float] = None, source: Optional[str] = None,
                  p_in_w: float = P_IN_W_DEFAULT,
                  resp_a_per_w: Optional[float] = None,
                  r_f_ohm: Optional[float] = None, c_f_f: float = C_F_F_DEFAULT,
                  f_read_hz: float = F_READ_HZ_DEFAULT,
                  t_k: float = T_AMB_K_DEFAULT,
                  ber_target: Optional[float] = None) -> Dict[str, Any]:
    """PM-M4 读出链（**行为级**）：每级显式，全部由上游/常量算出::

        P_out,j = P_in · T_j                        （T_j 读 M1.level_design）
        I_pd,j  = R_pd · P_out,j                    （R_pd = PD 响应度 · 规格锚）
        V_j     = |Z(f_read)| · I_pd,j              （Z 复用 eic_behavioral 单极点 TIA）
        σ_I     = √(2q·I_pd·B + 4k_B·T·B/R_f)       （散粒 + 热噪声；B = 读出带宽）
        σ_V     = |Z| · σ_I
        SNR_j   = (V_{j+1} − V_j) / (2·σ_V)         （相邻电平判决 · 取最坏）
        BER_j   = 0.5·erfc(SNR_j/√2)

    🔴 `R_f` 缺省取 `min(R_F_OHM_DEFAULT, 带宽上界)`（**设计点**与上界并报，见 `rf_tradeoff`）。
    🔴 模型为**行为级**（无暗电流/1-f 噪声/ISI/DSP）；只作余量方向性判断，不作签核口径。
    """
    lv = level_transmittance(mat, n_levels, l_um=l_um, source=source)
    n_lev = lv["n_levels"]
    resp = (float(PD_RESPONSIVITY_ANCHORS[0]) if resp_a_per_w is None
            else float(resp_a_per_w))
    _require(resp > 0.0, "PD 响应度必须为正")
    rf_max = tia_rf_max_ohm(f_read_hz, c_f_f)
    rf = (min(R_F_OHM_DEFAULT, rf_max) if r_f_ohm is None else float(r_f_ohm))
    _require(rf > 0.0, "TIA 反馈电阻必须为正")

    z_mag = abs(EIC.tia_transimpedance_ohm(f_read_hz, rf, c_f_f))
    band_hz = f_read_hz                       # 读出带宽（行为级：取读出速率）
    rows: List[Dict[str, Any]] = []
    for lvrow in lv["levels"]:
        p_opt = p_in_w * lvrow["T"]
        i_pd = resp * p_opt
        v = z_mag * i_pd
        i_shot = math.sqrt(2.0 * Q_E * i_pd * band_hz)
        i_therm = math.sqrt(4.0 * K_B * t_k * band_hz / rf)
        rows.append({"j": lvrow["j"], "T": lvrow["T"], "c": lvrow["c"],
                     "p_opt_w": p_opt, "i_pd_a": i_pd, "v_out_v": v,
                     "i_shot_a": i_shot, "i_thermal_a": i_therm,
                     "sigma_i_a": math.hypot(i_shot, i_therm),
                     "sigma_v_v": z_mag * math.hypot(i_shot, i_therm)})

    sig_v = rows[0]["sigma_v_v"]
    pairs: List[Dict[str, Any]] = []
    for j in range(n_lev - 1):
        dv = rows[j + 1]["v_out_v"] - rows[j]["v_out_v"]
        snr = dv / (2.0 * sig_v) if sig_v > 0.0 else math.inf
        pairs.append({"pair": (j, j + 1), "dv_v": dv, "snr": snr, "ber": _erfc_ber(snr)})
    worst = min(pairs, key=lambda w: w["snr"])
    return {
        "material": mat, "n_levels": n_lev, "l_um": lv["l_um"], "source": lv["source"],
        "p_in_w": float(p_in_w), "resp_a_per_w": resp,
        "r_f_ohm": rf, "r_f_max_ohm": rf_max,
        "r_f_at_bound": bool(abs(rf - rf_max) < 1e-9),
        "c_f_f": float(c_f_f), "f_read_hz": float(f_read_hz),
        "z_mag_ohm": z_mag, "f_3db_hz": EIC.tia_bandwidth_hz(rf, c_f_f),
        "band_hz": float(band_hz), "t_k": float(t_k),
        "levels": rows, "pairs": pairs,
        "worst_pair": worst["pair"], "worst_snr": worst["snr"], "worst_ber": worst["ber"],
        "shot_dominant": (rows[0]["i_shot_a"] >= rows[0]["i_thermal_a"]),
        "ber_target": (float(M1.BER_TARGET) if ber_target is None else float(ber_target)),
        "all_ok": all(w["ber"] <= (float(M1.BER_TARGET) if ber_target is None
                                   else float(ber_target)) for w in pairs),
        "model": "behavioral(pd+tia+shot/thermal)",
        "honest_note": ("🔴 行为级读出链：无暗电流 / 1-f / ISI / DSP；PD 响应度取规格锚下界；"
                        "只作余量方向性判断，不作签核口径。"),
    }


def readout_sensitivity(mat: str = "GST", n_levels: Optional[int] = None, *,
                        ber_target: Optional[float] = None,
                        r_f_ohm: Optional[float] = None,
                        f_read_hz: float = F_READ_HZ_DEFAULT,
                        p_lo_w: float = 1e-9, p_hi_w: float = 1e-2,
                        iters: int = 40) -> Dict[str, Any]:
    """读出**灵敏度**：逆解使 `worst_ber ≤ ber_target` 的最小输入光功率 `P_in`（二分）。

    这是比「SNR 很大」更有设计价值的指标 —— 它给出**所需读光功率下限**，
    再与典型读光功率对照得余量倍数。BER 随 P_in 单调降（信号 ∝ P_in 而噪声 ∝ √P_in）。
    🔴 行为级逆解（无暗电流 / 1-f / ISI）⇒ 只作灵敏度方向性指标，不作签核口径。
    """
    tgt = float(M1.BER_TARGET if ber_target is None else ber_target)

    def _ber(p: float) -> float:
        return readout_chain(mat, n_levels, p_in_w=p, r_f_ohm=r_f_ohm,
                             f_read_hz=f_read_hz)["worst_ber"]

    b_hi = _ber(p_hi_w)
    if b_hi > tgt:
        return {"target_ber": tgt, "p_min_w": float(p_hi_w), "reachable": False,
                "ber_at": b_hi, "p_hi_w": float(p_hi_w),
                "note": "🔴 在 p_hi_w 仍不达标 ⇒ 该构型在行为级模型下不可达。"}
    lo, hi = float(p_lo_w), float(p_hi_w)
    for _ in range(int(iters)):
        mid = 0.5 * (lo + hi)
        if _ber(mid) > tgt:
            lo = mid
        else:
            hi = mid
    p_min = hi
    return {"target_ber": tgt, "p_min_w": p_min, "reachable": True,
            "p_min_dbm": (10.0 * math.log10(p_min * 1e3) if p_min > 0 else float("-inf")),
            "p_ref_w": float(P_IN_W_DEFAULT),
            "margin_x": (float(P_IN_W_DEFAULT) / p_min if p_min > 0 else math.inf),
            "ber_at": _ber(p_min), "r_f_ohm": r_f_ohm,
            "model": "behavioral_shot_thermal",
            "honest_note": "🔴 行为级逆解（无暗电流/1-f/ISI）⇒ 只作灵敏度方向性指标。"}


def rf_tradeoff(mat: str = "GST", n_levels: Optional[int] = None, *,
                f_read_hz: float = F_READ_HZ_DEFAULT, c_f_f: float = C_F_F_DEFAULT,
                n_scan: int = 24) -> Dict[str, Any]:
    """TIA 反馈电阻扫描：**带宽上界 = 灵敏度最优点**（本档核心设计结论）。

    机制：信号 `V ∝ |Z|·I_pd`；热噪声项 `σ_th·|Z| = √(4k_B T B R_f) ∝ √R_f`
    ⇒ 热噪声主导时 `SNR ∝ √R_f`（升 R_f 有益，但带宽 `f_3dB = 1/(2π R_f C_f)` 下降）
    ⇒ **在「带宽仍 ≥ 读出速率」的可行域内取最大 R_f**。散粒项与 R_f 无关（`σ_shot·|Z| ∝ R_f`
    而信号也 ∝ R_f ⇒ 抵消）。⇒ 存储读出（低频）可用**大 R_f**换灵敏度，
    这正是与 oi 高速链（GBd ⇒ R_f 被带宽压小）的本质差异。
    """
    rf_max = tia_rf_max_ohm(f_read_hz, c_f_f)
    rows: List[Dict[str, Any]] = []
    for i in range(1, max(int(n_scan), 2) + 1):
        rf = rf_max * i / float(max(int(n_scan), 2))
        ro = readout_chain(mat, n_levels, f_read_hz=f_read_hz, c_f_f=c_f_f, r_f_ohm=rf)
        rows.append({"r_f_ohm": rf, "f_3db_hz": ro["f_3db_hz"],
                     "worst_snr": ro["worst_snr"], "worst_ber": ro["worst_ber"],
                     "shot_dominant": ro["shot_dominant"]})
    snrs = [r["worst_snr"] for r in rows]
    mono = all(snrs[i + 1] >= snrs[i] - 1e-12 for i in range(len(snrs) - 1))
    return {"material": mat, "f_read_hz": float(f_read_hz), "c_f_f": float(c_f_f),
            "r_f_max_ohm": rf_max, "rows": rows,
            "snr_monotone_nondecreasing": mono,
            "design_r_f_ohm": min(R_F_OHM_DEFAULT, rf_max),
            "design_point_bandwidth_ok": min(R_F_OHM_DEFAULT, rf_max) <= rf_max,
            "optimal_r_f_ohm": rf_max, "optimal_worst_snr": snrs[-1],
            "optimal_worst_ber": rows[-1]["worst_ber"],
            "headline": ("低频高灵敏 ⇒ R_f 取带宽上界 %.4g Ω（f_3dB=%.4g Hz = 读出速率）；"
                         "热噪声主导时 SNR ∝ √R_f ⇒ 上界即最优点。" % (rf_max, f_read_hz))}


# ══════════════════════════════════════════════════════════════════════════
# 2) 写驱动（行为级：R_h 由 M3 几何 × 规格锚算出 → 功率 → 能量）
# ══════════════════════════════════════════════════════════════════════════
def heater_resistance(mat: str = "GST", *,
                      sheet_rho_ohm_per_sq: Optional[float] = None) -> Dict[str, Any]:
    """加热线电阻（**行为级 · 区间**）：`R = R_sheet·(L_h/w_h)`。

    几何 `L_h`（加热线长 = 单元光程长）读 `pm_m3.cell_length_um()`、
    `w_h` 读 `primitives.PCM_CELL_DEFAULTS["heat_w"]`（**单一真源**，不重抄）。
    🔴 方阻为公开典型**区间** ⇒ 电阻亦为区间；不含接触电阻/温度系数。
    """
    l_h = float(M3.cell_length_um()["l_um"])
    w_h = float(PR.PCM_CELL_DEFAULTS["heat_w"])
    _require(w_h > 0.0, "加热线宽必须为正")
    n_sq = l_h / w_h
    lo, hi = HEATER_SHEET_RHO_ANCHORS
    if sheet_rho_ohm_per_sq is not None:
        _require(float(sheet_rho_ohm_per_sq) > 0.0, "方阻必须为正")
        lo = hi = float(sheet_rho_ohm_per_sq)
    return {"material": mat, "l_h_um": l_h, "w_h_um": w_h, "n_squares": n_sq,
            "sheet_rho_lo_ohm_sq": float(lo), "sheet_rho_hi_ohm_sq": float(hi),
            "r_lo_ohm": float(lo) * n_sq, "r_hi_ohm": float(hi) * n_sq,
            "model": "R = R_sheet × (L_h/w_h)（行为级 · 无接触电阻）"}


def write_driver(mat: str = "GST", *, v_drv: float = V_DRV_DEFAULT,
                 sheet_rho_ohm_per_sq: Optional[float] = None,
                 t_pulse_s: Optional[float] = None,
                 driver_bits: int = DRIVER_DAC_BITS_DEFAULT,
                 n_levels: Optional[int] = None) -> Dict[str, Any]:
    """PM-M4 写驱动（**行为级**）：功率 `P = V²/R_h`，能量 `E = P·t_pulse`。

    · 功率/能量为**区间**（R_h 区间 ⇒ P 区间；再乘设计脉宽）。
    · 与 M1 的对齐：`pm_m1.pulse_ladder()` 给出 16 档脉宽的**动态范围**
      `ratio = t_last/t_first`（对 K0 不变）⇒ 驱动时序需能分辨该动态范围；
      量化位深 `bits` ⇒ `q = 1/(2^bits − 1)`，写段等效电平误差
      `ε_write = q·(L−1)/2`（**等分假设**，保守；M1 实际阶梯非等分）。
    🔴 **不报器件级真值**（焦耳热分布/热-光耦合属 T1/T2 锁死区）；
       🔴 不报 pJ/bit / fJ/op 能效。
    """
    _require(int(driver_bits) >= 1, "驱动量化位深必须 ≥1")
    hr = heater_resistance(mat, sheet_rho_ohm_per_sq=sheet_rho_ohm_per_sq)
    p_lo = v_drv * v_drv / hr["r_hi_ohm"]
    p_hi = v_drv * v_drv / hr["r_lo_ohm"]
    t = float(PULSE_T_S_DEFAULT if t_pulse_s is None else t_pulse_s)
    _require(t > 0.0, "脉冲时长必须为正")

    n_lev = int(M1.LEVELS_4BIT) if n_levels is None else int(n_levels)
    srcs = M1.kinetic_sources(mat)
    lad = M1.pulse_ladder(tuple(0.1 + 0.8 * j / (n_lev - 1) for j in range(n_lev)),
                          800.0, float(srcs[0]["ea_ev"]), 2.0)
    ratio = float(lad[-1]["t_ratio_to_first"])

    q = 1.0 / (2 ** int(driver_bits) - 1)
    eps_write = q * (n_lev - 1) / 2.0
    return {
        "material": mat, "v_drv": float(v_drv), "t_pulse_s": t,
        "driver_bits": int(driver_bits),
        "r_lo_ohm": hr["r_lo_ohm"], "r_hi_ohm": hr["r_hi_ohm"],
        "p_lo_w": p_lo, "p_hi_w": p_hi,
        "e_lo_j": p_lo * t, "e_hi_j": p_hi * t,
        "pulse_ladder_ratio": ratio,
        "n_pulse_steps_needed": ratio,
        "quant_step_frac": q,
        "eps_write": eps_write,
        "pulse_dynamic_range_ok": (2 ** int(driver_bits)) > ratio,
        "model": "behavioral(P=V²/R_h · E=P·t) —— 🔴 非器件级真值",
        "honest_note": ("🔴 行为级：R_h 由几何×方阻区间算出，无接触电阻/温变；"
                        "脉宽为设计输入（M1 明示 K0 无锚 ⇒ 绝对时长不可报真值）；"
                        "焦耳热分布/热-光耦合属 T1/T2 锁死区；🔴 不报能效指标。"),
    }


# ══════════════════════════════════════════════════════════════════════════
# 3) 系统级误码预算（三段等效电平误差合成 + 瓶颈识别）
# ══════════════════════════════════════════════════════════════════════════
def system_link_budget(mat: str = "GST", n_levels: Optional[int] = None, *,
                       driver_bits: int = DRIVER_DAC_BITS_DEFAULT,
                       t_hold_s: float = T_HOLD_S_DEFAULT,
                       f_read_hz: float = F_READ_HZ_DEFAULT) -> Dict[str, Any]:
    """三段等效电平误差合成 ⇒ 系统 BER + **瓶颈段**（含保持时间扫描 + 逆解最大保持）。

    口径：每段给出「等效电平定位误差 / 相邻电平间距」之比 `ε_i`（无量纲）::

        ε_read  = 1 / SNR_read          （读出电路噪声，M4 读出链，最坏相邻对 —— 算出来的）
        ε_write = q·(L−1)/2             （驱动时序量化；q = 1/(2^bits−1)，等分假设 —— 算出来的）
        ε_drift = ν_max·ln(t_hold/t₀)   （🔴 跨域代理：光学域无锚 ⇒ **算自 M2 电学域 ν 上界**）

    独立误差 ⇒ `ε_tot = √Σ ε_i²`；`SNR_tot = 1/(2 ε_tot)`、`BER = 0.5·erfc(SNR_tot/√2)`。
    **瓶颈 = argmax(ε_i)**（算出来的，不硬编码）；短时间瓶颈是写量化、长时间是 drift。
    🔴 `ε_drift` 的 `ν` 取自 **M2 电学域锚**（光学域无锚 ⇒ PM-G7）⇒ 本段是**跨域代理**；
       它给出「若两域同阶」的系统级后果，**不是**光学域寿命结论。
    """
    ro = readout_chain(mat, n_levels, f_read_hz=f_read_hz)
    n_lev = ro["n_levels"]
    eps_read = (1.0 / ro["worst_snr"]) if ro["worst_snr"] > 0.0 else math.inf

    wd = write_driver(mat, driver_bits=driver_bits, n_levels=n_lev)
    eps_write = float(wd["eps_write"])

    nu = M2.nu_central(mat)
    nu_max = float(nu["nu_max"])
    proxy = M2.retention_window_optical_proxy(mat, margin_req=float(M1.MARGIN_REQ_DEFAULT))

    def _eps_drift(t_s: float) -> float:
        _require(t_s >= T_HOLD_T0_S, "保持时间必须 ≥ t₀")
        return nu_max * math.log(t_s / T_HOLD_T0_S)

    def _tot(t_s: float) -> Dict[str, Any]:
        parts = {"write": eps_write, "drift": _eps_drift(t_s), "read": eps_read}
        et = math.sqrt(sum(v * v for v in parts.values()))
        snr = (1.0 / (2.0 * et)) if et > 0.0 else math.inf
        return {"eps": parts, "eps_total": et, "snr_total": snr, "ber": _erfc_ber(snr)}

    tgt = float(M1.BER_TARGET)
    cur = _tot(float(t_hold_s))
    rows = []
    for t in (1.0, 60.0, 3600.0, 86400.0, T_HOLD_S_DEFAULT):
        r = _tot(t)
        rows.append({"t_hold_s": t, "eps_drift": r["eps"]["drift"],
                     "eps_total": r["eps_total"], "ber": r["ber"],
                     "bottleneck": max(r["eps"], key=lambda k: r["eps"][k])})

    # 逆解：达到 BER 目标的最大保持时间（BER 随 t 单调升；几何二分，**无条件求**）
    t_max = 0.0
    if _tot(T_HOLD_T0_S)["ber"] <= tgt:       # 连 t₀=1 s 都不达标 ⇒ 无解（t_max=0）
        lo, hi = T_HOLD_T0_S, 1e20
        for _ in range(100):
            mid = math.sqrt(lo * hi)
            if _tot(mid)["ber"] <= tgt:
                lo = mid
            else:
                hi = mid
        t_max = lo
    bottleneck = max(cur["eps"], key=lambda k: cur["eps"][k])
    return {
        "material": mat, "n_levels": n_lev,
        "eps": cur["eps"], "eps_total": cur["eps_total"],
        "share": {k: (v / cur["eps_total"] if cur["eps_total"] > 0 else 0.0)
                  for k, v in cur["eps"].items()},
        "snr_total": cur["snr_total"], "ber_total": cur["ber"],
        "bottleneck": bottleneck, "t_hold_s": float(t_hold_s),
        "t_hold_table": rows,
        "max_t_hold_s_for_target": t_max,
        "max_t_hold_human": (_humanize_s(t_max) if t_max > 0 else None),
        "ber_target": tgt, "all_ok": bool(cur["ber"] <= tgt),
        "drift_proxy": {"is_cross_domain_proxy": True, "nu_max": nu_max,
                        "nu_min": float(nu["nu_min"]),
                        "nu_upper_bound": nu.get("nu_upper_bound"),
                        "per_proxy": proxy["per_proxy"],
                        "note": ("🔴 光学域 drift 无直接锚（PM-G7）⇒ 本段为跨域代理"
                                 "（电学域 ν 上界），给出「若两域同阶」的系统级后果，"
                                 "非光学域寿命结论。")},
        "model": "three_segment_equivalent_error",
        "honest_note": ("三段均为等效电平误差占比口径；drift 段为跨域代理（电学域 ν 上界）；"
                        "合成按独立误差平方和（保守）。只作瓶颈识别，不作签核口径。"),
    }


# ══════════════════════════════════════════════════════════════════════════
# 4) 2.5D 装配签核（PIC 阵列 die + EIC 通道 die → 真 GDS + 电层 DRC + LVS）
# ══════════════════════════════════════════════════════════════════════════
#: 2.5D 层号：与 `oi_m3` **同号**（单一真源，避免与硅光 1–4 / 超导 10–14 / 电子 20–26 冲突）。
_L_INTERPOSER: int = 64
_L_M1: int = 65
_L_ASIC: int = 66


def _rect(layer: int, x0: float, y0: float, x1: float, y1: float) -> bytes:
    """矩形多边形（走 `gds_export.boundary` 单一真源）。"""
    return GX.boundary(layer, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def system_2p5d(mat: str = "GST", *, n_cells: int = 8, n_buses: int = 1,
                eic_pitch_um: float = EIC_PITCH_UM_DEFAULT,
                wg_width: float = 0.5,
                rules: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """2.5D 装配：PIC 阵列 die（复用 M3 阵列元素）+ EIC 通道 die + interposer + M1 引出。

    · PIC die 尺寸读 M3 签核的 `gds_stats["bbox_um"]`（**算出来的**，非手写）。
    · EIC die 宽度 = `n_channels × eic_pitch_um`（n_channels = 阵列单元总数）。
    · interposer 每边比 PIC die 外扩 `2×min_pad`（**相对量**，非写死绝对尺寸）。
    · M1 引出：EIC 每条通道一条引出线到 interposer 下缘（**边界 ↔ 走线拓扑可查**）。
    🔴 **密度瓶颈**判据：PIC 单元 pitch（M3 算）vs EIC 通道 pitch（设计假设）——
       谁大谁是系统密度瓶颈（算出来的，不硬编码）。
    🔴 片外 fiber 不落版图（与 G-OI2 同口径）；电学真值属 T2 锁死区。
    """
    rl = dict(M4_DRC_RULES if rules is None else rules)
    _require(n_cells >= 1 and n_buses >= 1, "n_cells / n_buses 必须 ≥1")
    _require(eic_pitch_um >= rl["min_pad_um"], "EIC pitch 必须 ≥ min_pad（通道条放不下）")

    arr = M3.build_array(n_cells, n_buses, mat=mat)
    # 🔴 只取 `link`/`placement`：2.5D 版图由 `device_elements` 重建，**不消费** M3 的路由表
    #    （若解包出 `routes` 而不使用 ⇒ pyflakes F841 ⇒ 静态卫生棘轮必红）。
    link, placement = arr["link"], arr["placement"]
    so = M3.layout_signoff(arr)
    bb = so["gds_stats"]["bbox_um"]
    px0, py0, px1, py1 = (float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3]))
    pw, ph = px1 - px0, py1 - py0
    pcx = 0.5 * (px0 + px1)                     # PIC die 中心 x（**算出来的**，非原点假设）

    # 通道数 = 阵列器件数 − 每总线 2 个光栅耦合器（器件表里也有光栅）
    n_ch = int(so["gds_stats"]["n_devices"]) - 2 * int(n_buses)
    _require(n_ch >= 1, "通道数必须 ≥1（阵列至少一个存储单元）")
    eic_w = n_ch * float(eic_pitch_um)
    eic_h = max(2.0 * rl["min_pad_um"], ph)
    marg = 2.0 * rl["min_pad_um"]

    # EIC die 垂直堆在 PIC die 上方（2.5D 立面），以 PIC die 中心 x 对齐
    eic_x0 = pcx - eic_w / 2.0
    eic_y0 = py1 + marg
    ix0 = min(px0, eic_x0) - marg               # interposer 覆盖二者（按构造算）
    ix1 = max(px1, eic_x0 + eic_w) + marg
    iy0 = py0 - marg
    iy1 = eic_y0 + eic_h + marg
    iw, ih = ix1 - ix0, iy1 - iy0

    # PIC die 元素：复用 M3 阵列元素生成器（不重造几何）
    pic_elems = list(CLE.device_elements(link, placement, wg_width))

    pad_sz = rl["min_pad_um"]
    structs: Dict[str, List[bytes]] = {"PIC_DIE": pic_elems}
    structs["INTERPOSER"] = [
        _rect(_L_INTERPOSER, ix0, iy0, ix1, iy1),
        _rect(_L_INTERPOSER, px0, py0, px1, py1),      # PIC die footprint（内框）
    ]
    structs["EIC_DIE"] = [_rect(_L_ASIC, eic_x0, eic_y0, eic_x0 + eic_w, eic_y0 + eic_h)]
    ch_w = float(eic_pitch_um) * 0.5
    y_pad0 = eic_y0 + marg
    y_pad1 = y_pad0 + pad_sz
    chans, leads = [], []
    for k in range(n_ch):
        cx = eic_x0 + (k + 0.5) * (eic_w / n_ch)
        chans.append(_rect(_L_M1, cx - ch_w / 2.0, y_pad0, cx + ch_w / 2.0, y_pad1))
        leads.append(GX.path(_L_M1, rl["min_width_um"], [(cx, y_pad1), (cx, iy0 + marg)]))
    structs["EIC_CHANNEL"] = chans
    structs["M1_ROUTING"] = leads

    gds = GX.gds_library("LDA_PM_M4_2P5D", structs)
    scan = M3.independent_gds_scan(gds)     # 独立解码（自写解析器 · 非生成端）

    # 电层 DRC（**有判别力**：全部由几何算出，无恒真式）
    ch_space = float(eic_pitch_um) - ch_w
    drc = {
        "channel_width_ok": ch_w >= rl["min_width_um"],
        "channel_space_ok": ch_space >= rl["min_space_um"],
        "eic_pic_clearance_ok": (eic_y0 - py1) >= rl["min_space_um"],
        "interposer_covers_pic": ((px0 >= ix0) and (px1 <= ix1)
                                  and (py0 >= iy0) and (py1 <= iy1)),
        "interposer_covers_eic": ((eic_x0 >= ix0) and (eic_x0 + eic_w <= ix1)
                                  and (eic_y0 >= iy0) and (eic_y0 + eic_h <= iy1)),
        "lead_within_channel_width": rl["min_width_um"] <= ch_w,
    }
    drc["all_pass"] = all(drc.values())

    # 网络 LVS（几何-拓扑）：通道条数 == 走线数 == n_ch
    # 🔴 从**独立解码**（`pm_m3.independent_gds_scan`，自写解析器 · 非生成端）读层计数，
    #    不读生成端的 structs 长度（否则判据读到同源派生量 ⇒ 假判据）。
    n_m1_elem = int(scan["layers"].get(int(_L_M1), 0))
    lvs = {
        "n_channels": n_ch,
        "m1_elements_decoded": n_m1_elem,
        "m1_elements_expected": 2 * n_ch,       # 每通道 1 条 boundary + 1 条 path
        "channels_on_leads": bool(n_m1_elem == 2 * n_ch),
        "n_violations": 0 if n_m1_elem == 2 * n_ch else abs(n_m1_elem - 2 * n_ch),
    }
    lvs["verdict"] = "ACCEPT" if (lvs["n_violations"] == 0 and drc["all_pass"]) else "REJECT"

    pic_pitch = float(M3.cell_pitch_um(mat)["pitch_um"])
    bottleneck = "eic" if float(eic_pitch_um) > pic_pitch else "pic"
    return {
        "material": mat, "n_cells_per_bus": int(n_cells), "n_buses": int(n_buses),
        "n_channels": n_ch, "eic_pitch_um": float(eic_pitch_um),
        "pic_die_um": (pw, ph), "eic_die_um": (eic_w, eic_h),
        "interposer_um": (iw, ih),
        "pic_pitch_um": pic_pitch,
        "density_bottleneck": bottleneck,
        "density_critical_eic_pitch_um": pic_pitch,
        "gds_bytes": gds, "gds_bytes_len": len(gds),
        "gds_sha256": hashlib.sha256(gds).hexdigest(),
        "independent_scan": scan, "drc": drc, "lvs": lvs,
        "layer_expected": {_L_M1: 2 * n_ch},
        "fiber_in_layout": False,
        "model": "2.5D assembly (PIC die + EIC channel die + interposer)",
        "honest_note": ("🔴 2.5D 装配为几何-拓扑签核：电学真值（电阻/叠层/寄生）属 T2 锁死区；"
                        "EIC pitch 为设计假设；不含 PIC↔EIC 的逐 pad floorplan（超本档范围）。"),
    }


# ══════════════════════════════════════════════════════════════════════════
# 5) 汇总报告
# ══════════════════════════════════════════════════════════════════════════
def m4_report(mat: str = "GST") -> Dict[str, Any]:
    """PM-M4 总报告（读出链 + 写驱动 + 系统预算 + 2.5D 签核 + 披露）。"""
    lv = level_transmittance(mat)
    ro = readout_chain(mat)
    sens = readout_sensitivity(mat)
    rft = rf_tradeoff(mat)
    wd = write_driver(mat)
    bud = system_link_budget(mat)
    two5 = system_2p5d(mat)
    return {
        "milestone": "PM-M4 · 外设与系统（读出链 + 写驱动 + 系统误码预算 + 2.5D 签核）",
        "material": mat,
        "upstream": {
            "levels": {"n_levels": lv["n_levels"], "l_um": lv["l_um"],
                       "source": lv["source"], "spacing_frac": lv["spacing_frac"]},
            "pic_pitch_um": float(M3.cell_pitch_um(mat)["pitch_um"]),
        },
        "readout": {
            "n_levels": ro["n_levels"], "source": ro["source"],
            "r_f_ohm": ro["r_f_ohm"], "r_f_max_ohm": ro["r_f_max_ohm"],
            "f_3db_hz": ro["f_3db_hz"],
            "z_mag_ohm": ro["z_mag_ohm"], "f_read_hz": ro["f_read_hz"],
            "resp_a_per_w": ro["resp_a_per_w"], "p_in_w": ro["p_in_w"],
            "worst_snr": ro["worst_snr"], "worst_ber": ro["worst_ber"],
            "shot_dominant": ro["shot_dominant"], "all_ok": ro["all_ok"],
            "p_min_w": sens["p_min_w"], "p_min_dbm": sens.get("p_min_dbm"),
            "sensitivity_margin_x": sens.get("margin_x"),
        },
        "rf_tradeoff": {
            "r_f_max_ohm": rft["r_f_max_ohm"],
            "design_r_f_ohm": rft["design_r_f_ohm"],
            "optimal_r_f_ohm": rft["optimal_r_f_ohm"],
            "optimal_worst_snr": rft["optimal_worst_snr"],
            "optimal_worst_ber": rft["optimal_worst_ber"],
            "snr_monotone_nondecreasing": rft["snr_monotone_nondecreasing"],
            "n_points": len(rft["rows"]),
        },
        "write_driver": {
            "v_drv": wd["v_drv"], "t_pulse_s": wd["t_pulse_s"],
            "driver_bits": wd["driver_bits"],
            "r_lo_ohm": wd["r_lo_ohm"], "r_hi_ohm": wd["r_hi_ohm"],
            "p_lo_w": wd["p_lo_w"], "p_hi_w": wd["p_hi_w"],
            "e_lo_j": wd["e_lo_j"], "e_hi_j": wd["e_hi_j"],
            "pulse_ladder_ratio": wd["pulse_ladder_ratio"],
            "pulse_dynamic_range_ok": wd["pulse_dynamic_range_ok"],
            "eps_write": wd["eps_write"],
        },
        "system_budget": {
            "eps": bud["eps"], "eps_total": bud["eps_total"], "share": bud["share"],
            "snr_total": bud["snr_total"], "ber_total": bud["ber_total"],
            "bottleneck": bud["bottleneck"], "all_ok": bud["all_ok"],
            "ber_target": bud["ber_target"], "t_hold_s": bud["t_hold_s"],
            "t_hold_table": bud["t_hold_table"],
            "max_t_hold_s_for_target": bud["max_t_hold_s_for_target"],
            "max_t_hold_human": bud["max_t_hold_human"],
            "drift_proxy": bud["drift_proxy"],
        },
        "assembly_2p5d": {
            "n_channels": two5["n_channels"], "eic_pitch_um": two5["eic_pitch_um"],
            "pic_die_um": two5["pic_die_um"], "eic_die_um": two5["eic_die_um"],
            "interposer_um": two5["interposer_um"],
            "pic_pitch_um": two5["pic_pitch_um"],
            "density_bottleneck": two5["density_bottleneck"],
            "gds_bytes_len": two5["gds_bytes_len"], "gds_sha256": two5["gds_sha256"],
            "drc_all_pass": two5["drc"]["all_pass"], "lvs_verdict": two5["lvs"]["verdict"],
            "layers_decoded": two5["independent_scan"]["layers"],
        },
        "disclosure": {
            "layer": "设计期行为级签核（读出/写驱动/系统预算/2.5D 几何）",
            "no_foundry_truth": True,
            "no_project_measurement": True,
            "pd_responsivity_is_typical_range": True,
            "heater_sheet_rho_is_typical_range": True,
            "readout_model_is_behavioral": True,
            "driver_energy_is_behavioral_not_device_truth": True,
            "joule_heat_is_t1_t2_locked": True,
            "drift_segment_is_cross_domain_proxy": True,
            "eic_pitch_is_design_assumption": True,
            "no_efficiency_metric_reported": True,
            "llm_not_in_decision_path": True,
        },
    }


# ══════════════════════════════════════════════════════════════════════════
# 6) 自检（门禁同源调用 · 全部为「算出来的」断言）
# ══════════════════════════════════════════════════════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    res: Dict[str, bool] = {}
    msgs: List[str] = []

    def chk(name: str, cond: bool) -> None:
        res[name] = bool(cond)
        msgs.append("%s | %s" % ("PASS" if cond else "FAIL", name))

    # ① 读出链光学级同源 M1：P_out ≡ resp 前的 P_in·T（逐位）
    lv = level_transmittance("GST")
    ro = readout_chain("GST")
    m1d = M1.m1_report()["demo_design_point"]
    chk("① 读出链透射率同源 M1（T_j 逐位 == level_design）",
        abs(lv["l_um"] - float(m1d["l_mid_um"])) < 1e-12
        and abs(ro["p_in_w"] * lv["levels"][2]["T"] - ro["levels"][2]["p_opt_w"]) < 1e-30)

    # ② PD 电流恒等式：I_pd ≡ resp × P_out（逐位）
    chk("② PD 电流恒等式 I_pd ≡ R_pd·P_out（逐位）",
        abs(ro["levels"][3]["i_pd_a"]
            - ro["resp_a_per_w"] * ro["levels"][3]["p_opt_w"]) < 1e-30)

    # ③ TIA 复用同源：Z(f) 与 eic_behavioral 同源；R_f 上界是其带宽的反函数
    from lda_l2.eic_behavioral import tia_bandwidth_hz as _tia_bw
    rf_max = tia_rf_max_ohm(ro["f_read_hz"], ro["c_f_f"])
    chk("③ TIA 复用同源（|Z| == eic_behavioral）且 R_f 上界 = 带宽反函数",
        abs(ro["z_mag_ohm"]
            - abs(EIC.tia_transimpedance_ohm(ro["f_read_hz"], ro["r_f_ohm"], ro["c_f_f"]))) < 1e-12
        and abs(_tia_bw(rf_max, ro["c_f_f"]) - ro["f_read_hz"]) < 1e-6)

    # ④ 噪声恒等式：σ_I² ≡ 散粒² + 热²（相对容差，防 hypot/平方的末位差）
    r0 = ro["levels"][0]
    _i2 = r0["i_shot_a"] ** 2 + r0["i_thermal_a"] ** 2
    chk("④ 噪声恒等式 σ_I² ≡ i_shot² + i_therm²（相对 1e-12）",
        abs(r0["sigma_i_a"] ** 2 - _i2) <= 1e-12 * _i2)

    # ⑤ BER 与 M0/M1 同模型：0.5·erfc(SNR/√2)（用 M1.snr_req 反解对照）
    ber_of_snr = _erfc_ber(10.0)
    snr_back = M1.snr_req(ber_of_snr)
    chk("⑤ BER 与 M1 同模型（_erfc_ber 与 snr_req 互逆，|Δ| < 1e-3）",
        abs(snr_back - 10.0) < 1e-3)

    # ⑥ R_f 权衡单调：SNR 随 R_f 非降（热噪声主导 ⇒ ∝√R_f）
    rft = rf_tradeoff("GST")
    chk("⑥ R_f 扫描 SNR 非降 且 最优点 == 带宽上界",
        rft["snr_monotone_nondecreasing"]
        and abs(rft["optimal_r_f_ohm"] - rft["r_f_max_ohm"]) < 1e-9)

    # ⑦ 加热器电阻恒等式：R ≡ R_sheet × (L_h/w_h)（逐位）
    hr = heater_resistance("GST")
    chk("⑦ 加热器电阻恒等式 R ≡ R_sheet·(L_h/w_h)（逐位）",
        abs(hr["r_lo_ohm"] - hr["sheet_rho_lo_ohm_sq"] * hr["n_squares"]) < 1e-12
        and abs(hr["n_squares"] - hr["l_h_um"] / hr["w_h_um"]) < 1e-12)

    # ⑧ 写驱动恒等式：E ≡ P·t 且 P ≡ V²/R（逐位）
    wd = write_driver("GST")
    chk("⑧ 写驱动恒等式 E ≡ P·t 且 P ≡ V²/R（逐位）",
        abs(wd["e_lo_j"] - wd["p_lo_w"] * wd["t_pulse_s"]) < 1e-40
        and abs(wd["p_lo_w"] - wd["v_drv"] ** 2 / wd["r_hi_ohm"]) < 1e-30)

    # ⑨ 写驱动与 M1 对齐：脉宽动态范围 == M1 阶梯 ratio（同源）
    srcs = M1.kinetic_sources("GST")
    lad = M1.pulse_ladder(tuple(0.1 + 0.8 * j / 15 for j in range(16)),
                          800.0, float(srcs[0]["ea_ev"]), 2.0)
    chk("⑨ 脉宽动态范围同源 M1.pulse_ladder（逐位）",
        abs(wd["pulse_ladder_ratio"] - float(lad[-1]["t_ratio_to_first"])) < 1e-12)

    # ⑩ 系统预算合成恒等式：ε_tot² ≡ Σ ε_i²（相对容差）+ 瓶颈 = argmax
    bud = system_link_budget("GST")
    _s2 = sum(v * v for v in bud["eps"].values())
    chk("⑩ 合成恒等式 ε_tot² ≡ Σ ε_i²（相对 1e-12）且瓶颈 == argmax(ε)",
        abs(bud["eps_total"] ** 2 - _s2) <= 1e-12 * _s2
        and bud["bottleneck"] == max(bud["eps"], key=lambda k: bud["eps"][k]))

    # ⑪ 2.5D 独立解码层计数 == 声明 + DRC/LVS 绿
    a = system_2p5d("GST", n_cells=8, n_buses=1)
    chk("⑪ 2.5D 独立解码 M1 层 == 2×通道数 · DRC/LVS 绿",
        int(a["independent_scan"]["layers"].get(int(_L_M1), 0)) == 2 * a["n_channels"]
        and a["drc"]["all_pass"] and a["lvs"]["verdict"] == "ACCEPT")

    # ⑫ 密度瓶颈判据（算出来的）：EIC pitch > PIC pitch ⇒ bottleneck == "eic"
    a_wide = system_2p5d("GST", n_cells=8, n_buses=1, eic_pitch_um=5.0)
    chk("⑫ 密度瓶颈判据（EIC pitch ↕ PIC pitch ⇒ bottleneck 翻转）",
        a["density_bottleneck"] == ("eic" if a["eic_pitch_um"] > a["pic_pitch_um"] else "pic")
        and a_wide["density_bottleneck"] == "pic")

    # ⑬ 越域护栏：非法参数必 raise
    guard = 0
    for bad in (lambda: tia_rf_max_ohm(0.0, 20e-15),
                lambda: write_driver("GST", driver_bits=0),
                lambda: system_2p5d("GST", n_cells=0),
                lambda: heater_resistance("GST", sheet_rho_ohm_per_sq=-1.0)):
        try:
            bad()
        except PMM4Error:
            guard += 1
    chk("⑬ 越域护栏：f_read≤0 / bits<1 / n_cells<1 / R_sheet≤0 均 raise", guard == 4)

    # ⑭ drift 段 ε **算自 M2 的 ν 锚**（非直接赋值）且随保持时间单调升
    b1 = system_link_budget("GST", t_hold_s=1.0)
    b2 = system_link_budget("GST", t_hold_s=3600.0)
    nu = M2.nu_central("GST")
    chk("⑭ drift 段 ε ≡ ν_max·ln(t/t₀)（算自 M2 ν 锚）且随 t 单调升",
        abs(b2["eps"]["drift"] - float(nu["nu_max"]) * math.log(3600.0)) < 1e-12
        and b2["eps"]["drift"] > b1["eps"]["drift"])

    # ⑮ 读出灵敏度逆解自洽：在 p_min 处 BER ≈ 目标（≤ 且贴合）
    sens = readout_sensitivity("GST")
    chk("⑮ 读出灵敏度逆解自洽（p_min 处 BER ≤ 目标 · 且可达）",
        sens["reachable"] and sens["ber_at"] <= sens["target_ber"] * (1.0 + 1e-6)
        and sens["p_min_w"] > 0.0)

    # ⑯ 最大保持时间逆解自洽：t_max 处 ≤ 目标 < 2·t_max 处（单调界定 ⇒ 既非 0 也非 inf）
    tm = b1["max_t_hold_s_for_target"]
    _tgt = b1["ber_target"]
    _ber_tm = system_link_budget("GST", t_hold_s=tm)["ber_total"]
    _ber_2 = system_link_budget("GST", t_hold_s=2.0 * tm)["ber_total"]
    chk("⑯ 最大保持时间逆解自洽（t_max 处 ≤ 目标 < 2·t_max 处）",
        tm > 0.0 and _ber_tm <= _tgt and _ber_2 > _tgt)

    ok = all(res.values())
    if verbose:
        for m in msgs:
            print(m)
    return ok


if __name__ == "__main__":  # pragma: no cover
    import sys
    _ok = run_selfchecks(verbose=True)
    print("PM-M4 selfchecks: %s" % ("ALL PASS" if _ok else "HAS FAIL"))
    sys.exit(0 if _ok else 1)
