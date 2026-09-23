# -*- coding: utf-8 -*-
"""U4 · 微环权重库（MRR 替 MZI 做幅度控制）。

背景（内部总结 §4.2 U4 / §4.4 执行序第 4 项）
--------------------------------------------
「权重物理化」有两条路：① MZI（EO / 热光相位 ⇒ 面积大、静态功耗高）
② 微环 MRR（波长选择 + 小面积）。本模块交付 ② 的**设计层** ——
把微环 add-drop 的**谐振 drop 透射率**当作**非负实数幅度权重**，给出：

  · 闭式正/反演（κ ↔ w，机器精度往返）
  · 可达权重范围与「波长选择性 × 权重」的设计折中
  · **双旋钮**位深（制造期 gap / 运行期失谐），一律用「档位极差」口径
  · 面积对比（对 EO 调制器，参照源唯一 = `device_bbox`）
  · 「与 WDM 共享网格共网格」的保真度判据（复用 U1 已证网格）

复用（不重写任何已证数学）
--------------------------
| 复用对象 | 来源 | 用途 |
|---|---|---|
| `q_decomposition(R,n_g,kappa,alpha)` | `lda_agent.ring_adddrop`（D-37） | Q 分解 Q_c/Q_i/Q_L |
| `adddrop_spectrum(wls,R,n_g,kappa,alpha)` | 同上（D-37） | add-drop 透射谱（失谐编程） |
| `bending_loss_db_per_cm(R)` | 同上（D-37） | 弯曲损耗（Q_i 的来源） |
| `kappa_c_lookup(gap,wl,backend=…)` | `lda_l2.ring_kappa_calib`（U3） | κ_c 取数（analytic 占位 / FDTD 已签发表） |
| `wdm_ring_anchor(wl,n_g,m,gap)` | `lda_layout.wdm_mesh_pnr` | 环几何 R / L_couple / FSR |
| `device_bbox(kind,params)` | `lda_layout.placement` | 器件面积（**唯一权威源**） |
| `build_wdm_shared_mesh_pnr(…)` | `lda_layout.wdm_shared_mesh_pnr`（U1） | 共网格保真度锚 |

🔴 六条诚实边界（实测确立，写进 `RING_WEIGHT_DISCLOSURE`）
---------------------------------------------------------
① **权重非负**：透射率 ∈ [0, a] ⇒ 只表达非负实数权重；负权重需差分对 + 平衡探测
   （本模块**不建模**）。
② **绝对定标未达标**：同一 gap 下 analytic 占位与 U3 FDTD 标定的 w 相差
   **39.5×**（= **16.0 dB**）⇒ 只有**相对**编程分辨率有意义；绝对值必须标定
   （与 U6 校准固件强耦合，且 U6 需物理锚）。
③ **解析占位在物理域外**：`gap_to_kappa`（κ_ref=0.35）在 gap ≤ 0.21µm 处给出
   κ = κ_c·L_couple > 1 ⇒ w > 1（**违反能量守恒**）⇒ 本模块对 κ ∉ [0,1] 一律 raise，
   绝不静默截断（截断会把「模型失效」伪装成「器件饱和」）。
④ **单点导数骗人**：w(κ) 在 κ→1 处饱和（dw/dκ→0）⇒ 单点局部导数给出的位深
   **系统性偏高**（实测 gap 旋钮：单点 11.91 bit vs 档位极差 8.13 bit）。
   ⇒ 本模块一律报**档位极差口径**，并把单点值并列作反面对照。
⑤ **热漂移**：失谐编程靠热光 ⇒ 权重随温度漂移；本模块**只报灵敏度与位深**，
   **不宣称已校准**（无物理锚，T1 铁律）。
⑥ **权重带宽 = 谐振 FWHM**：FWHM 由 Q_L 决定，Q_L 上界 = Q_i（弯曲损耗）
   ⇒ 权重**不是**全带宽常数。WDM 场景须满足 FWHM ≪ 信道间隔。

耗时：全部为解析 / 查表 / 已证网格，**无 FDTD** ⇒ 单次 < 0.1s（可进 CI core）。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# 常量 / 设计预算（全部来自 §4.2 U4，不在此处放宽）
# ---------------------------------------------------------------------------
#: §4.2 U4 验收判据：面积 ≤ EO 调制的 ~10%
AREA_BUDGET_RATIO = 0.10

#: §4.2 U4 验收判据：权重级数 ≥ 5-bit（**设计预算**）
WEIGHT_BUDGET_BITS = 5.0

#: 面积参照：EO 调制的 π 相移臂长（µm）。
#: 与 `lda_layout.mesh_pnr.mesh_drive_manifest(ps_arm_um=1000.0)` 同源 ——
#: 这是项目自身「取到 π 相移」的物理臂长，**不是**局部单位胞元占位（Lu=20µm）。
PS_ARM_UM_DEFAULT = 1000.0

#: EO MZI 权重单元的臂间距（µm），与 `device_bbox("MZI", {"dy":…})` 同口径。
MZI_DY_UM_DEFAULT = 4.0

#: WDM 信道间隔（nm）——权重带宽判据的分母。
CHANNEL_SPACING_NM_DEFAULT = 2.5

#: 🔴 **假设值**（非实测、非标定）：光刻对 gap 的分辨率。用于制造期位深口径。
GAP_RESOLUTION_NM_DEFAULT = 1.0

#: 🔴 **假设值**（非实测）：热调失谐分辨率。用于运行期位深口径。
#: 公开热光调谐精度 ~ mK 量级 ⇒ 折算 pm 量级；此处取 0.1pm（保守乐观端）。
DETUNING_RESOLUTION_PM_DEFAULT = 0.1

#: 失谐扫描跨度 = 该倍数 × FWHM（覆盖到 T_drop → 近零）。
DETUNING_SPAN_FWHM = 5.0

#: 器件参数（与 D-37 / D-57 / U3 同源）
W_UM = 0.5
N_CORE = 3.48
N_CLAD = 1.44
N_G_DEFAULT = 2.45
M_RING_DEFAULT = 30
WL_UM_DEFAULT = 1.55
WL_NM_DEFAULT = 1550.0

#: κ_c 标定表锚点（用于判断「设计点 gap 是否落在已签发表内」）
TABLE_PROBE_GAP_UM = 0.30

#: analytic 后端「二分求 κ=1 穿越点」的硬括号（实测 κ(0.10) > 1 > κ(4.0)）。
_ANALYTIC_BRACKET: Tuple[float, float] = (0.10, 4.0)
#: analytic 后端可设计上界（µm）—— 此远处 κ → 0，权重不可用但仍在模型域内。
_ANALYTIC_GAP_HI = 4.0

#: κ 比较容差：仅用于「端点恰在可设计边界」的浮点噪声，非判据放宽
#: （真越域时偏差是量级性的，见 `gap_for_kappa` 注释与 smoke 反向用例）。
KAPPA_TOL = 1e-9

#: 诚实边界声明（smoke 断言其键存在，防被悄悄删掉）
RING_WEIGHT_DISCLOSURE: Dict[str, Any] = {
    "scope": (
        "只做「微环 add-drop 谐振 drop 透射率作非负幅度权重」的**设计层**建模："
        "闭式正反演 / 可达范围 / 双旋钮位深 / 面积对比 / 共网格保真度。"
        "不做器件级签核、不做热-电闭环校准、不做负权重网络。"
    ),
    "nonneg_weight_only": (
        "权重 = 透射率 ∈ [0, a]，**非负**。负权重须用差分对 + 平衡探测实现，"
        "本模块不建模；因此本模块只支撑「非负权重网络」类工作负载。"
    ),
    "absolute_weight_not_calibrated": (
        "🔴 **绝对定标未达标**：同一 gap 下 analytic 占位与 U3 FDTD 标定的 w 相差 "
        "**39.5×**（= 16.0 dB）⇒ 只有相对编程分辨率有意义；绝对值须实测标定"
        "（与 U6 强耦合，且 U6 需物理锚）。"
    ),
    "analytic_placeholder_out_of_domain": (
        "🔴 解析经验模型 `gap_to_kappa`（κ_ref=0.35 / L_ev=0.15µm）是**纯指数式、无域声明**："
        "实测 κ = κ_c·L_couple 在 **gap ≲ 0.288µm** 处 > 1 ⇒ w > 1，"
        "**违反能量守恒**（模型失效，非器件现象）。"
        "⇒ 本模块对 κ ∉ [0,1] 一律 raise、**不静默截断**，且可设计下界由 "
        "`_kappa_one_gap_analytic()` **每次重算**（不硬编码数字）。"
    ),
    "single_point_derivative_lies": (
        "🔴 w(κ) 在 κ→1 处饱和（dw/dκ→0）⇒ **单点局部导数**给出的位深系统性偏高"
        "（实测制造期口径：单点 12.32 bit vs 档位极差 8.13 bit ⇒ 高估 1.52×）。"
        "⇒ 一律用档位极差口径，单点值仅作反面对照。"
    ),
    "thermal_drift_not_calibrated": (
        "失谐编程靠热光（dλ_res/dT 量级 0.06–0.1 nm/K）⇒ 权重随温度漂移；"
        "本模块**只报灵敏度与位深，不宣称已校准**（无物理锚，T1 铁律）⇒ 与 U6 强耦合。"
    ),
    "weight_bandwidth_is_resonance_fwhm": (
        "权重不是全带宽常数：其带宽 = 谐振 FWHM = λ/Q_L，且 Q_L 上界 = Q_i（弯曲损耗）"
        "⇒ 小半径环的 Q_i 是硬地板。WDM 场景须满足 FWHM ≪ 信道间隔，否则相邻信道串扰。"
    ),
    "no_fdtd_no_3d": (
        "本模块不跑 FDTD、不做 3D：κ_c 一律经 U3 的取数接口（analytic 占位或已签发表）；"
        "2D 无垂直限制的偏置由 U3 承担并已披露。"
    ),
}


class RingWeightBankError(Exception):
    """参数越界 / 物理域外 / 前置条件不满足（不是「数值不达标」）。"""


# ---------------------------------------------------------------------------
# 1. 闭式权重核（add-drop 谐振 drop 透射率）
# ---------------------------------------------------------------------------
def roundtrip_amplitude(R_um: float, alpha_bend_dBcm: float) -> float:
    """环半程场振幅衰减 a = exp(−α_p·L/2)，α_p[1/m] = 23.03·α_bend[dB/cm]。"""
    if R_um <= 0:
        raise RingWeightBankError("R 必须 > 0（µm），收到 %r" % (R_um,))
    if alpha_bend_dBcm < 0:
        raise RingWeightBankError("弯曲损耗必须 ≥ 0（dB/cm），收到 %r" % (alpha_bend_dBcm,))
    L_m = 2.0 * math.pi * R_um * 1e-6
    alpha_p = 23.03 * alpha_bend_dBcm
    return math.exp(-alpha_p * L_m / 2.0)


def peak_drop_weight(kappa: float, R_um: float, alpha_bend_dBcm: float) -> float:
    """谐振点 drop 透射率（**闭式**）= a·κ⁴/(1 − a·t²)²，t² = 1 − κ²。

    域校验：κ ∈ [0,1]（κ > 1 表示解析占位失效，**不截断**）。
    无损（a→1）时恒为 1；有损时 w ∈ (0, a]，且对 κ **严格单调递增**。
    """
    if not (0.0 <= kappa <= 1.0):
        raise RingWeightBankError(
            "κ 必须 ∈ [0,1]（收到 %.6f）—— κ>1 是**模型失效**而非器件饱和，"
            "本模块拒绝静默截断。" % kappa)
    a = roundtrip_amplitude(R_um, alpha_bend_dBcm)
    t2 = 1.0 - kappa * kappa
    return a * kappa ** 4 / (1.0 - a * t2) ** 2


def kappa_for_peak_weight(w: float, R_um: float, alpha_bend_dBcm: float) -> float:
    """`peak_drop_weight` 的**闭式反演**：

        κ = sqrt( (1−a)·sqrt(w) / ( sqrt(a)·(1 − sqrt(a·w)) ) )

    实测往返误差 ~1e-15（机器精度）。可达范围 [0, a]：w > a ⇒ raise。
    """
    a = roundtrip_amplitude(R_um, alpha_bend_dBcm)
    if w < 0:
        raise RingWeightBankError("权重必须 ≥ 0，收到 %r" % (w,))
    if w > a:
        raise RingWeightBankError(
            "目标权重 %.6f > 可达上限 a = %.6f（= −%.2f dB，受环内损耗限制）"
            % (w, a, -10.0 * math.log10(a)))
    if w == 0.0:
        return 0.0
    if w == a:
        return 1.0
    num = (1.0 - a) * math.sqrt(w)
    den = math.sqrt(a) * (1.0 - math.sqrt(a * w))
    k2 = num / den
    if k2 > 1.0:                       # a 极接近 1 时的浮点保护（数学上 ≤ 1）
        k2 = 1.0
    return math.sqrt(k2)


# ---------------------------------------------------------------------------
# 2. Q / 波长选择性（复用 D-37 的 Q 分解）
# ---------------------------------------------------------------------------
def q_selectivity(kappa: float, R_um: float, n_g: float = N_G_DEFAULT,
                  alpha_bend_dBcm: float = 0.0,
                  wl_nm: float = WL_NM_DEFAULT) -> Dict[str, float]:
    """复用 `ring_adddrop.q_decomposition` + FWHM = λ/Q_L（**nm 与 pm 都报**）。"""
    from lda_agent.ring_adddrop import q_decomposition      # 局部导入
    if not (0.0 <= kappa <= 1.0):
        raise RingWeightBankError("κ 必须 ∈ [0,1]，收到 %r" % (kappa,))
    q = q_decomposition(R_um, n_g, max(kappa, 1e-12), alpha_bend_dBcm)
    fwhm_nm = wl_nm / q["Q_L"]
    return {"Q_c": q["Q_c"], "Q_i": q["Q_i"], "Q_L": q["Q_L"],
            "fwhm_nm": fwhm_nm, "fwhm_pm": 1000.0 * fwhm_nm,
            "kappa": kappa}


def intrinsic_fwhm_floor_pm(R_um: float, n_g: float = N_G_DEFAULT,
                            alpha_bend_dBcm: float = 0.0,
                            wl_nm: float = WL_NM_DEFAULT) -> float:
    """弯曲损耗决定的 FWHM **硬地板**（Q_L 上界 = Q_i）⇒ 无耦合可突破。"""
    return q_selectivity(0.0, R_um, n_g, alpha_bend_dBcm, wl_nm)["fwhm_pm"]


def kappa_for_fwhm(fwhm_pm: float, R_um: float, n_g: float = N_G_DEFAULT,
                   alpha_bend_dBcm: float = 0.0,
                   wl_nm: float = WL_NM_DEFAULT) -> float:
    """由目标 FWHM 反演 κ：1/Q_L = 2/Q_c + 1/Q_i，Q_c = 2π·n_g·L/(λ·κ²)。

    目标 FWHM 大于本征地板（Q_i 极限）⇒ raise（物理上不可达，不是数值问题）。
    """
    if fwhm_pm <= 0:
        raise RingWeightBankError("FWHM 必须 > 0（pm），收到 %r" % (fwhm_pm,))
    bl = alpha_bend_dBcm
    L_m = 2.0 * math.pi * R_um * 1e-6
    lam_m = wl_nm * 1e-9
    alpha_p = 23.03 * bl
    q_i = (2.0 * math.pi * n_g / (lam_m * alpha_p)) if alpha_p > 0 else float("inf")
    q_l_t = wl_nm / (fwhm_pm * 1e-3)
    inv = 1.0 / q_l_t - 1.0 / q_i
    if inv <= 0:
        raise RingWeightBankError(
            "目标 FWHM %.4f pm 宽于本征地板 %.4f pm（Q_i 限制）⇒ 物理上不可达"
            % (fwhm_pm, intrinsic_fwhm_floor_pm(R_um, n_g, bl, wl_nm)))
    q_c = 2.0 / inv
    k2 = 2.0 * math.pi * n_g * L_m / (lam_m * q_c)
    if k2 > 1.0:
        raise RingWeightBankError("反演得 κ² = %.4f > 1 ⇒ 目标 FWHM 过窄（超物理域）" % k2)
    return math.sqrt(k2)


# ---------------------------------------------------------------------------
# 3. 设计折中：选择性约束下的最大权重
# ---------------------------------------------------------------------------
def max_weight_under_selectivity(R_um: float, n_g: float = N_G_DEFAULT,
                                 alpha_bend_dBcm: float = 0.0,
                                 spacing_nm: float = CHANNEL_SPACING_NM_DEFAULT,
                                 fwhm_budget_ratio: float = 0.2,
                                 wl_nm: float = WL_NM_DEFAULT) -> Dict[str, Any]:
    """在「FWHM ≤ 比例 × 信道间隔」约束下可达的**最大权重**。

    🔴 这是 U4 的真代价：权重 w 对 κ **单调递增**，但 κ 增大 ⇒ Q_c 下降 ⇒ FWHM 变宽
    ⇒ 串扰。故「高权重」与「波长选择性」是一对**冲突目标**，不存在「都要」的解。
    """
    if not (0.0 < fwhm_budget_ratio < 1.0):
        raise RingWeightBankError("fwhm_budget_ratio 须 ∈ (0,1)，收到 %r" % (fwhm_budget_ratio,))
    budget_pm = spacing_nm * 1000.0 * fwhm_budget_ratio
    floor = intrinsic_fwhm_floor_pm(R_um, n_g, alpha_bend_dBcm, wl_nm)
    if budget_pm <= floor:
        return {"feasible": False, "fwhm_budget_pm": budget_pm, "fwhm_floor_pm": floor,
                "kappa": 0.0, "weight_max": 0.0, "weight_max_db": -math.inf,
                "reason": "FWHM 预算 %.2f pm 低于本征地板 %.2f pm ⇒ 无可行设计点"
                          % (budget_pm, floor)}
    kappa = kappa_for_fwhm(budget_pm, R_um, n_g, alpha_bend_dBcm, wl_nm)
    w = peak_drop_weight(kappa, R_um, alpha_bend_dBcm)
    a = roundtrip_amplitude(R_um, alpha_bend_dBcm)
    return {"feasible": True, "fwhm_budget_pm": budget_pm, "fwhm_floor_pm": floor,
            "fwhm_budget_ratio": fwhm_budget_ratio, "spacing_nm": spacing_nm,
            "kappa": kappa, "weight_max": w,
            "weight_max_db": 10.0 * math.log10(max(w, 1e-30)),
            "weight_ceiling_a": a,
            "weight_max_frac_of_ceiling": w / a,
            "reason": "受 FWHM 约束（非受损耗上限 a 约束）" if w < a * 0.999
                      else "受损耗上限 a 约束"}


# ---------------------------------------------------------------------------
# 4. gap ↔ κ 桥（经 U3 取数接口；不重写 FDTD）
# ---------------------------------------------------------------------------
def kappa_at_gap(gap_um: float, wl_um: float = WL_UM_DEFAULT,
                 n_g: float = N_G_DEFAULT, m: int = M_RING_DEFAULT,
                 backend: str = "analytic") -> float:
    """κ(gap) = κ_c(gap,λ)·L_couple(gap) —— 几何走 `wdm_ring_anchor`，κ_c 走 U3。"""
    from lda_l2.ring_kappa_calib import kappa_c_lookup       # 局部导入
    from lda_layout.wdm_mesh_pnr import wdm_ring_anchor
    Lc = wdm_ring_anchor(wl_um * 1000.0, n_g=n_g, m=m, gap=gap_um)["L_couple_um"]
    return kappa_c_lookup(gap_um, wl_um, backend=backend)["kappa_c_rad_um"] * Lc


def _kappa_one_gap_analytic(wl_um: float = WL_UM_DEFAULT, n_g: float = N_G_DEFAULT,
                            m: int = M_RING_DEFAULT, tol: float = 1e-12) -> float:
    """求 analytic 模型 κ(gap)=1 的穿越 gap ——— **模型有效域的下界**。

    🔴 为什么必须实测而不是照抄一个数：D-37 的 `gap_to_kappa` 是纯指数式，**没有
    定义域声明**；本轮实测 κ=1 的穿越点在 **gap ≈ 0.2877µm**（而非早期记录的
    「~0.21µm」）。若把下界定在穿越点**之下**（如 0.205µm），该处 κ=1.4675 > 1
    ⇒「可设计区间」自身就落在**违反能量守恒**的区域里，与披露 ③ 直接矛盾。
    """
    lo, hi = _ANALYTIC_BRACKET
    if kappa_at_gap(lo, wl_um, n_g, m, "analytic") <= 1.0:
        return lo                                   # 硬括号下界已合法
    if kappa_at_gap(hi, wl_um, n_g, m, "analytic") > 1.0:
        raise RingWeightBankError(
            "analytic 模型在硬括号 %s 内无 κ=1 穿越点 ⇒ 无法界定有效域" % (_ANALYTIC_BRACKET,))
    while hi - lo > tol:                            # κ(gap) 严格递减
        mid = 0.5 * (lo + hi)
        if kappa_at_gap(mid, wl_um, n_g, m, "analytic") > 1.0:
            lo = mid
        else:
            hi = mid
    # 返回 `hi` 而非中点：不变式保证 κ(hi) ≤ 1（中点可能因浮点舍入得 1+2e-16，
    # 从而把「恰好临界」误报成「越域」）。代价仅 ≤ tol 的边界保守量。
    return hi


def gap_bounds_for_backend(backend: str) -> Tuple[float, float]:
    """各 backend 的**可设计 gap 区间**：analytic 限模型有效域；已签发表限表内。

    🔴 这是硬约束而非便利，两处都来自**上游自身的域声明**：
      · `fdtd-table`：`kappa_c_lookup(..., 'fdtd-table')` 在表外**必 raise**
        （U3 刻意如此，防静默回退）⇒ 任何「反查 gap」都必须在表内闭合；
      · `analytic`：下界取 κ(gap)=1 的**实测穿越点**（≈0.2877µm）——
        更小的 gap 处解析模型给出 κ>1（违反能量守恒），不属于可设计域。
    """
    if backend == "analytic":
        return (_kappa_one_gap_analytic(), _ANALYTIC_GAP_HI)
    if backend == "fdtd-table":
        info = calibration_table_info()
        if not info.get("available") or not info.get("gaps_um"):
            raise RingWeightBankError("已签发标定表不可用 ⇒ 无法界定可设计 gap 区间")
        g = sorted(float(x) for x in info["gaps_um"])
        return (g[0], g[-1])
    raise RingWeightBankError("未知 backend：%r（可选 analytic / fdtd-table）" % (backend,))


def gap_for_kappa(kappa_target: float, wl_um: float = WL_UM_DEFAULT,
                  n_g: float = N_G_DEFAULT, m: int = M_RING_DEFAULT,
                  backend: str = "analytic",
                  lo_um: Optional[float] = None, hi_um: Optional[float] = None,
                  tol: float = 1e-10) -> float:
    """反查 gap：κ(gap) 单调递减 ⇒ 二分。区间缺省取 `gap_bounds_for_backend`。

    双侧都取不到 ⇒ raise（不返回边界值 —— 那会把「超出可设计域」伪装成合法解）。
    """
    if not (0.0 < kappa_target <= 1.0):
        raise RingWeightBankError("目标 κ 须 ∈ (0,1]，收到 %r" % (kappa_target,))
    b_lo, b_hi = gap_bounds_for_backend(backend)
    lo_um = b_lo if lo_um is None else lo_um
    hi_um = b_hi if hi_um is None else hi_um
    k_lo = kappa_at_gap(lo_um, wl_um, n_g, m, backend)
    k_hi = kappa_at_gap(hi_um, wl_um, n_g, m, backend)
    # 容差 KAPPA_TOL：端点恰好落在可设计边界（如 analytic 下界处 κ=1）时，浮点
    # 舍入会让 κ(lo) 略低于目标 ⇒ 会被误判「不可达」。但目标**真在域外**时偏差
    # 是量级性的（见探针：κ(0.25)=1.2006 vs 目标 0.05），1e-9 容差不会放过。
    if k_lo < kappa_target - KAPPA_TOL or k_hi > kappa_target + KAPPA_TOL:
        raise RingWeightBankError(
            "目标 κ=%.6f 在 %s 的可设计区间 [%.3f,%.3f]µm 上不可达"
            "（κ(lo)=%.6f, κ(hi)=%.6f）⇒ 须先扩表/改参考"
            % (kappa_target, backend, lo_um, hi_um, k_lo, k_hi))
    while hi_um - lo_um > tol:
        mid = 0.5 * (lo_um + hi_um)
        if kappa_at_gap(mid, wl_um, n_g, m, backend) > kappa_target:
            lo_um = mid
        else:
            hi_um = mid
    return 0.5 * (lo_um + hi_um)


def weight_reachable_interval(backend: str = "fdtd-table",
                             wl_um: float = WL_UM_DEFAULT,
                             n_g: float = N_G_DEFAULT, m: int = M_RING_DEFAULT,
                             alpha_bend_dBcm: Optional[float] = None) -> Dict[str, Any]:
    """给定 backend 的**可达权重区间**（κ 随 gap 单调递减 ⇒ w 亦单调递减）。"""
    from lda_agent.ring_adddrop import bending_loss_db_per_cm
    from lda_layout.wdm_mesh_pnr import wdm_ring_anchor
    lo, hi = gap_bounds_for_backend(backend)
    out: Dict[str, Any] = {"backend": backend, "gap_lo_um": lo, "gap_hi_um": hi}
    clamped: List[str] = []
    for tag, g in (("lo", lo), ("hi", hi)):
        k_raw = kappa_at_gap(g, wl_um, n_g, m, backend)
        k = min(max(k_raw, 0.0), 1.0)
        # 容差 1e-9：恰好临界（κ=1±1e-16）不是越域，不该报成域界不一致。
        if abs(k - k_raw) > 1e-9:
            clamped.append("%s(gap=%.4fµm,κ_raw=%.6f)" % (tag, g, k_raw))
        R = wdm_ring_anchor(wl_um * 1000.0, n_g=n_g, m=m, gap=g)["R_um"]
        bl = alpha_bend_dBcm if alpha_bend_dBcm is not None \
            else bending_loss_db_per_cm(R)
        out["kappa_" + tag + "_raw"] = k_raw
        out["kappa_" + tag] = k
        out["w_" + tag] = peak_drop_weight(k, R, bl)
    out["w_max"] = out["w_lo"]          # gap 最小 ⇒ κ 最大 ⇒ w 最大
    out["w_min"] = out["w_hi"]
    out["w_max_db"] = 10.0 * math.log10(max(out["w_max"], 1e-30))
    # 披露③：绝不静默截断。钳位仅在「上游域声明之外」发生，必须**显式报出**。
    out["clamped_at_domain_edge"] = clamped
    out["domain_ok"] = not clamped
    if clamped:
        out["warning"] = (
            "🔴 κ 在区间端点越出 [0,1]（%s）⇒ 该端点的权重上限 a 只是**物理上限**，"
            "不是该 backend 在该 gap 处的模型值。表明 `gap_bounds_for_backend` 的域界定"
            "与上游不一致，须先修正边界而非使用本区间。" % "; ".join(clamped))
    return out


def calibration_table_info() -> Dict[str, Any]:
    """已签发 κ_c 标定表的覆盖范围（**经 U3 接口取**，不重复路径逻辑）。"""
    from lda_l2.ring_kappa_calib import kappa_c_from_table   # 局部导入
    hit = kappa_c_from_table(TABLE_PROBE_GAP_UM, WL_UM_DEFAULT)
    if hit is None:
        return {"available": False, "gaps_um": None, "wls_um": None}
    return {"available": True,
            "gaps_um": hit.get("table_gaps_um"),
            "wls_um": hit.get("table_wls_um"),
            "dl_factor": hit.get("table_dl_factor"),
            "path": hit.get("table_path")}


# ---------------------------------------------------------------------------
# 5. 双旋钮位深（**档位极差口径**）
# ---------------------------------------------------------------------------
def _sweep_dwdgap(gaps_um: Sequence[float], wl_um: float, n_g: float, m: int,
                  R_of_gap, alpha_bend_dBcm: float, step_um: float,
                  backend: str) -> List[Tuple[float, float, List[str]]]:
    """逐档求 |dw/dgap|；返回 (gap, 导数, 越域原因列表)。

    🔴 不静默截断：若某档邻居点 κ ∉ [0,1]（解析模型越域），该档导数被钳到物理
    上限，因而**必须**把原因随行返回，由调用方写进报告的 `out_of_domain_points`。
    """
    out = []
    for g in gaps_um:
        k1 = kappa_at_gap(g - step_um, wl_um, n_g, m, backend)
        k2 = kappa_at_gap(g + step_um, wl_um, n_g, m, backend)
        bad = []
        if not (0.0 <= k1 <= 1.0):
            bad.append("κ⁻=%.6f" % k1)
        if not (0.0 <= k2 <= 1.0):
            bad.append("κ⁺=%.6f" % k2)
        k1 = min(max(k1, 0.0), 1.0)
        k2 = min(max(k2, 0.0), 1.0)
        w1 = peak_drop_weight(k1, R_of_gap(g), alpha_bend_dBcm)
        w2 = peak_drop_weight(k2, R_of_gap(g), alpha_bend_dBcm)
        out.append((g, abs(w2 - w1) / (2.0 * step_um), bad))
    return out


def gap_knob_bits(dgap_nm: float = GAP_RESOLUTION_NM_DEFAULT,
                  wl_um: float = WL_UM_DEFAULT, n_g: float = N_G_DEFAULT,
                  m: int = M_RING_DEFAULT, backend: str = "analytic",
                  gaps_um: Optional[Sequence[float]] = None,
                  design_gap_um: float = 0.30,
                  alpha_bend_dBcm: Optional[float] = None) -> Dict[str, Any]:
    """**制造期 gap 旋钮**的位深（档位极差口径 + 单点口径并列作反面对照）。"""
    from lda_agent.ring_adddrop import bending_loss_db_per_cm
    from lda_layout.wdm_mesh_pnr import wdm_ring_anchor

    def R_of_gap(g: float) -> float:
        return wdm_ring_anchor(wl_um * 1000.0, n_g=n_g, m=m, gap=g)["R_um"]

    if gaps_um is None:
        gaps_um = [0.25 + i * 0.025 for i in range(0, 71)]      # 0.25..2.0
    if alpha_bend_dBcm is None:
        alpha_bend_dBcm = bending_loss_db_per_cm(R_of_gap(design_gap_um))
    step = 1e-4
    rows = _sweep_dwdgap(gaps_um, wl_um, n_g, m, R_of_gap, alpha_bend_dBcm, step, backend)
    ood = [{"gap_um": r[0], "why": r[2]} for r in rows if r[2]]
    worst_gap, worst, _ = max(rows, key=lambda r: r[1])
    point = abs(next(r[1] for r in rows if abs(r[0] - design_gap_um) < 1e-9)) \
        if any(abs(r[0] - design_gap_um) < 1e-9 for r in rows) else None
    a = roundtrip_amplitude(R_of_gap(design_gap_um), alpha_bend_dBcm)
    dgap_um = dgap_nm * 1e-3
    bits_range = math.log2(a / (worst * dgap_um)) if worst > 0 else 0.0
    bits_point = (math.log2(a / (point * dgap_um)) if point and point > 0 else None)
    return {"knob": "gap(manufacturing)", "dgap_nm": dgap_nm,
            "worst_dwdgap_per_um": worst, "worst_gap_um": worst_gap,
            "point_dwdgap_per_um": point, "design_gap_um": design_gap_um,
            "weight_ceiling_a": a,
            "bits_range": bits_range, "bits_point": bits_point,
            "point_overestimates_x": (bits_point / bits_range)
                                     if bits_point and bits_range > 0 else None,
            "budget_met": bool(bits_range >= WEIGHT_BUDGET_BITS),
            "n_sweep_points": len(rows),
            "n_out_of_domain": len(ood), "out_of_domain_points": ood,
            "alpha_bend_dBcm": alpha_bend_dBcm, "backend": backend,
            "assumed_not_measured": "dgap_nm 是**假设值**（光刻分辨率），非实测/标定"}


def detuning_knob_bits(kappa: float, dlam_pm: float = DETUNING_RESOLUTION_PM_DEFAULT,
                       R_um: Optional[float] = None,
                       wl_um: float = WL_UM_DEFAULT, n_g: float = N_G_DEFAULT,
                       m: int = M_RING_DEFAULT,
                       alpha_bend_dBcm: Optional[float] = None,
                       n_grid: int = 4001) -> Dict[str, Any]:
    """**运行期失谐旋钮**的位深（档位极差口径；谱复用 D-37 `adddrop_spectrum`）。"""
    from lda_agent.ring_adddrop import (adddrop_spectrum,
                                        bending_loss_db_per_cm)
    from lda_layout.wdm_mesh_pnr import wdm_ring_anchor
    if R_um is None:
        R_um = wdm_ring_anchor(wl_um * 1000.0, n_g=n_g, m=m, gap=0.30)["R_um"]
    if alpha_bend_dBcm is None:
        alpha_bend_dBcm = bending_loss_db_per_cm(R_um)
    q = q_selectivity(kappa, R_um, n_g, alpha_bend_dBcm, wl_um * 1000.0)
    span_nm = DETUNING_SPAN_FWHM * q["fwhm_nm"]
    wls = [wl_um + i * (span_nm * 1e-3) / (n_grid - 1) for i in range(n_grid)]
    drop = adddrop_spectrum(wls, R_um, n_g, kappa, alpha_bend_dBcm)["drop"]
    per_nm = max(abs(drop[i + 1] - drop[i]) for i in range(n_grid - 1)) \
        / (span_nm * 1e-3 / (n_grid - 1))
    a = roundtrip_amplitude(R_um, alpha_bend_dBcm)
    dw = per_nm * (dlam_pm * 1e-3)
    bits = math.log2(a / dw) if dw > 0 else 0.0
    return {"knob": "detuning(runtime)", "dlam_pm": dlam_pm,
            "worst_dwdlam_per_nm": per_nm, "span_nm": span_nm,
            "fwhm_pm": q["fwhm_pm"], "Q_L": q["Q_L"],
            "peak_weight": drop[0], "weight_ceiling_a": a,
            "bits_range": bits, "budget_met": bool(bits >= WEIGHT_BUDGET_BITS),
            "alpha_bend_dBcm": alpha_bend_dBcm,
            "assumed_not_measured": "dlam_pm 是**假设值**（热调分辨率），非实测/标定"}


# ---------------------------------------------------------------------------
# 6. 面积对比（参照源唯一 = device_bbox）
# ---------------------------------------------------------------------------
def area_vs_eo_modulator(R_um: float, wg_width: float = W_UM, gap_um: float = 0.30,
                         ps_arm_um: float = PS_ARM_UM_DEFAULT,
                         dy_um: float = MZI_DY_UM_DEFAULT,
                         unit_cell_um: float = 20.0) -> Dict[str, Any]:
    """微环权重单元 vs EO（MZI）权重单元面积 —— 两个参照**并列**，不挑好看的。

    · `ratio_pi_arm`：对**真实 π 相移臂**（`ps_arm_um`，与 `mesh_drive_manifest`
      同源）—— 这是物理上有意义的 EO 权重单元。
    · `ratio_unit_cell`：对**局部单位胞元占位**（默认 Lu=20µm）—— 这不是物理
      调制器尺寸，仅作「若按占位胞元比」的对照，**不用于达标判定**。
    """
    from lda_layout.placement import device_bbox             # 局部导入
    ring_hw, ring_hh = device_bbox("RingAddDrop",
                                   {"R": R_um, "wg_width": wg_width, "gap": gap_um})
    ring_area = 4.0 * ring_hw * ring_hh
    eo_hw, eo_hh = device_bbox("MZI", {"Lu": ps_arm_um, "dy": dy_um})
    eo_area = 4.0 * eo_hw * eo_hh
    uc_hw, uc_hh = device_bbox("MZI", {"Lu": unit_cell_um, "dy": dy_um})
    uc_area = 4.0 * uc_hw * uc_hh
    r_pi = ring_area / eo_area
    r_uc = ring_area / uc_area
    return {"ring_area_um2": ring_area, "eo_area_pi_arm_um2": eo_area,
            "eo_area_unit_cell_um2": uc_area,
            "ratio_pi_arm": r_pi, "ratio_unit_cell": r_uc,
            "ps_arm_um": ps_arm_um, "unit_cell_um": unit_cell_um,
            "budget_ratio": AREA_BUDGET_RATIO,
            "budget_met_pi_arm": bool(r_pi <= AREA_BUDGET_RATIO),
            "budget_met_unit_cell": bool(r_uc <= AREA_BUDGET_RATIO),
            "honest_note": (
                "达标判定用 ratio_pi_arm（物理参照：真实 π 相移臂 %.0fµm，与 "
                "mesh_drive_manifest(ps_arm_um) 同源）；ratio_unit_cell 仅作对照 —— "
                "局部胞元（Lu=%.0fµm）不是物理调制器尺寸。" % (ps_arm_um, unit_cell_um))}


# ---------------------------------------------------------------------------
# 7. 权重库（weights → 每信道一个环）
# ---------------------------------------------------------------------------
def weight_bank_from_weights(weights: Sequence[float],
                             wl_nm: Any = WL_NM_DEFAULT,
                             n_g: float = N_G_DEFAULT,
                             m: int = M_RING_DEFAULT,
                             alpha_bend_dBcm: Optional[float] = None,
                             backend: str = "fdtd-table") -> Dict[str, Any]:
    """把目标权重向量映射成「每信道一个环」的物理参数（κ / gap / FWHM）。

    🔴 默认 backend = **`fdtd-table`（已签发标定表）** —— 权重库是要签核的设计产物，
    不能建立在 U3 已证「差 39.5×」的解析占位上。表内不可达的权重会**显式标注**
    （`gap_um=None` + `unreachable_reason`），**不静默外推**。

    `wl_nm` 可为标量或与 weights 等长的序列（WDM 每信道中心波长不同
    ⇒ 环半径按 FSR 锚逐信道微调，与 U1 `lambda_interface.ring_anchors` 同源）。
    """
    from lda_agent.ring_adddrop import bending_loss_db_per_cm
    from lda_layout.wdm_mesh_pnr import wdm_ring_anchor

    ws = [float(x) for x in weights]
    if not ws:
        raise RingWeightBankError("权重向量不能为空")
    wls = ([float(wl_nm)] * len(ws)) if isinstance(wl_nm, (int, float)) else \
        [float(x) for x in wl_nm]
    if len(wls) != len(ws):
        raise RingWeightBankError("wl_nm 长度 %d != weights 长度 %d" % (len(wls), len(ws)))

    table = calibration_table_info()
    t_gaps = table.get("gaps_um") or []
    info = table.get("available")
    reach = weight_reachable_interval(backend, alpha_bend_dBcm=alpha_bend_dBcm,
                                      n_g=n_g, m=m)
    entries: List[Dict[str, Any]] = []
    for w, wl in zip(ws, wls):
        R = wdm_ring_anchor(wl, n_g=n_g, m=m, gap=0.30)["R_um"]
        bl = alpha_bend_dBcm if alpha_bend_dBcm is not None \
            else bending_loss_db_per_cm(R)
        a = roundtrip_amplitude(R, bl)
        kappa = kappa_for_peak_weight(w, R, bl)
        gap, reason = None, None
        if kappa > 0:
            try:
                gap = gap_for_kappa(kappa, wl * 1e-3, n_g, m, backend)
            except RingWeightBankError as exc:
                reason = str(exc)
        in_table = bool(gap is not None and t_gaps and info
                        and min(t_gaps) <= gap <= max(t_gaps))
        q = q_selectivity(kappa, R, n_g, bl, wl)
        entries.append({
            "w_target": w, "wl_nm": wl, "R_um": R, "alpha_bend_dBcm": bl,
            "weight_ceiling_a": a, "kappa": kappa, "gap_um": gap,
            "unreachable_reason": reason,
            "gap_in_signed_table": in_table,
            "fwhm_pm": q["fwhm_pm"], "Q_L": q["Q_L"],
            "selectivity_ok": bool(q["fwhm_pm"]
                                   < 1000.0 * CHANNEL_SPACING_NM_DEFAULT),
        })
    n_out = sum(1 for e in entries if not e["gap_in_signed_table"])
    return {"n_channels": len(entries), "entries": entries,
            "backend": backend,
            "table_gaps_um": t_gaps,
            "reachable_interval": reach,
            "n_gap_outside_signed_table": n_out,
            "all_reachable_in_table": bool(n_out == 0),
            "honest_note": (
                "权重与 κ 一一对应（闭式反演）；κ 与 gap 的换算**只**在 backend=%s 的"
                "可设计区间 [%.3f,%.3f]µm 内闭合，该区间对应权重 [%.6f, %.6f]"
                "（上限 %.2f dB）。表外权重**不静默外推**，须先扩表（重跑 FDTD）。"
                % (backend, reach["gap_lo_um"], reach["gap_hi_um"],
                   reach["w_min"], reach["w_max"], reach["w_max_db"])),
            }


# ---------------------------------------------------------------------------
# 8. 与 WDM 共享网格共网格（保真度判据）
# ---------------------------------------------------------------------------
def weight_bank_on_shared_mesh(weights: Sequence[float],
                               wavelengths_nm: Optional[Sequence[float]] = None,
                               N: int = 16, rail_pitch: float = 4.0,
                               wl_nm: Any = None,
                               n_g: float = N_G_DEFAULT,
                               m: int = M_RING_DEFAULT,
                               backend: str = "fdtd-table") -> Dict[str, Any]:
    """把权重库接到 **U1 的 WDM 共享网格**上，并断言网格保真度**保持**。

    语义：权重层是**网格之外的对角幅度层**（每信道一个环，落在光接口层）
    ⇒ 网格本身仍精确实现酉 U（保真度 1.0），权重只做每信道的幅度缩放。

    🔴 默认 backend = `fdtd-table`，与 `weight_bank_from_weights` 一致 ——
    权重库是要签核的设计产物；U1 网格自带的 `ring_anchors` 用 κ_c=0.35 占位是
    **几何锚**（U1 已自披露），不是权重编程值，二者不应混淆。传 `analytic`
    可对照「若沿用 U1 占位口径」的结果。
    """
    import numpy as np

    from lda_layout.wdm_shared_mesh_pnr import build_wdm_shared_mesh_pnr
    ws = [float(x) for x in weights]
    rep = build_wdm_shared_mesh_pnr(wavelengths_nm=wavelengths_nm, N=N,
                                    rail_pitch=rail_pitch, n_g=n_g, m_ring=m)
    wls = wavelengths_nm if wavelengths_nm is not None else rep["wavelengths_nm"]
    if len(ws) != len(wls):
        raise RingWeightBankError(
            "权重数 %d != 信道数 %d（WDM 权重库须**每信道一个**）" % (len(ws), len(wls)))
    bank = weight_bank_from_weights(ws, wl_nm=wl_nm if wl_nm is not None else wls,
                                   n_g=n_g, m=m, backend=backend)
    wmat = np.diag(np.array(ws, dtype=float))
    offdiag = float(np.max(np.abs(wmat - np.diag(np.diag(wmat))))) if len(ws) else 0.0
    return {
        "K": rep["K"], "N": rep["N"], "n_mzi": rep["n_mzi"],
        "mesh_fidelity": rep["fidelity"],
        "mesh_layout_fidelity": rep["layout_fidelity"],
        "mesh_fidelity_preserved": bool(
            abs(rep["fidelity"] - 1.0) < 1e-12 and abs(rep["layout_fidelity"] - 1.0) < 1e-12),
        "weight_layer_is_diagonal": bool(offdiag == 0.0),
        "weight_matrix_offdiag_max": offdiag,
        "weights": ws,
        "wavelengths_nm": list(wls),
        "weight_bank": bank,
        "drc_pass": rep["drc_pass"], "lvs_verdict": rep["lvs_verdict"],
        "footprint_um2": rep["footprint_um2"],
        "channel_spacing_nm": rep["lambda_interface"]["channel_spacing_nm"],
        "all_selectivity_ok": bool(all(e["selectivity_ok"] for e in bank["entries"])),
        "honest_note": (
            "网格保真度是**继承** U1 已证结论（权重层在网格之外，为对角幅度层）；"
            "本判据只在「权重层不破坏网格」这一意义上成立，不代表权重本身已被标定。"),
    }


if __name__ == "__main__":       # pragma: no cover - 人工自测入口
    import json

    from lda_agent.ring_adddrop import (adddrop_spectrum,
                                        bending_loss_db_per_cm)
    from lda_layout.wdm_mesh_pnr import wdm_ring_anchor

    GAP = 0.30
    R = wdm_ring_anchor(1550.0, n_g=N_G_DEFAULT, m=M_RING_DEFAULT, gap=GAP)["R_um"]
    BL = bending_loss_db_per_cm(R)
    A = roundtrip_amplitude(R, BL)
    print("== U4 微环权重库（R=%.4f µm · α_bend=%.3f dB/cm）==" % (R, BL))
    print("  半程振幅 a = %.6f（权重上限 = −%.3f dB）" % (A, -10 * math.log10(A)))

    print("\n-- 闭式往返（κ → w → κ）--")
    worst = 0.0
    for k in (0.05, 0.1, 0.2, 0.4, 0.6, 0.8, 0.94, 1.0):
        w = peak_drop_weight(k, R, BL)
        k2 = kappa_for_peak_weight(w, R, BL)
        worst = max(worst, abs(k2 - k))
    print("  worst |Δκ| = %.3e" % worst)

    print("\n-- 闭式 vs 采样谱峰值（交叉验证 D-37 资产）--")
    k0 = 0.147
    w_closed = peak_drop_weight(k0, R, BL)
    wls = [WL_UM_DEFAULT + i * 1e-6 for i in range(-200, 201)]
    sp = adddrop_spectrum(wls, R, N_G_DEFAULT, k0, BL)
    print("  闭式 %.10f · 采样谱峰 %.10f · 差 %.2e"
          % (w_closed, max(sp["drop"]), abs(w_closed - max(sp["drop"]))))

    print("\n-- U3 取数：analytic vs FDTD 表 --")
    for bk in ("analytic", "fdtd-table"):
        kc = kappa_at_gap(GAP, backend=bk)
        print("  %-11s κ=%.6f  w=%.8f (%.2f dB)"
              % (bk, kc, peak_drop_weight(min(kc, 1.0), R, BL),
                 10 * math.log10(max(peak_drop_weight(min(kc, 1.0), R, BL), 1e-30))))

    print("\n-- 可设计域（两 backend，含 κ=1 穿越点）--")
    for bk in ("analytic", "fdtd-table"):
        rb = weight_reachable_interval(bk)
        print("  %-11s gap[%.4f,%.4f] κ[%.6f,%.6f] w[%.6f,%.6f] 域OK=%s"
              % (bk, rb["gap_lo_um"], rb["gap_hi_um"], rb["kappa_hi"], rb["kappa_lo"],
                 rb["w_min"], rb["w_max"], rb["domain_ok"]))
        for c in rb["clamped_at_domain_edge"]:
            print("     ⚠ 钳位: %s" % c)
    print("  κ=1 穿越 gap（analytic） = %.6f µm ⇒ κ(该点)=%.9f"
          % (_kappa_one_gap_analytic(),
             kappa_at_gap(_kappa_one_gap_analytic(), backend="analytic")))

    print("\n-- 选择性 × 权重 折中 --")
    print("  FWHM 地板 = %.2f pm（Q_i 限制）"
          % intrinsic_fwhm_floor_pm(R, N_G_DEFAULT, BL))
    for ratio in (0.05, 0.1, 0.2, 0.5):
        mw = max_weight_under_selectivity(R, N_G_DEFAULT, BL, fwhm_budget_ratio=ratio)
        print("  budget=%.0f%%·间隔(%.2f pm) ⇒ κ=%.6f w_max=%.6f (%.2f dB) %.0f%% of a"
              % (ratio * 100, mw["fwhm_budget_pm"], mw["kappa"],
                 mw["weight_max"], mw["weight_max_db"],
                 100 * mw.get("weight_max_frac_of_ceiling", 0)))

    print("\n-- 双旋钮位深（档位极差口径）--")
    gb = gap_knob_bits(alpha_bend_dBcm=None)
    print("  gap 旋钮 Δgap=%.0f nm: worst|dw/dgap|=%.4f /µm @gap=%.3f ⇒ bits=%.2f"
          " (单点 %.2f @0.30µm ⇒ 高估 %.2f×) 达标=%s"
          % (gb["dgap_nm"], gb["worst_dwdgap_per_um"], gb["worst_gap_um"],
             gb["bits_range"], gb["bits_point"] or -1,
             gb["point_overestimates_x"] or -1, gb["budget_met"]))
    print("    扫描 %d 档，越域 %d 档%s"
          % (gb["n_sweep_points"], gb["n_out_of_domain"],
             ("（" + "; ".join("gap=%.3f %s" % (p["gap_um"], ",".join(p["why"]))
                               for p in gb["out_of_domain_points"][:3]) + "）")
             if gb["n_out_of_domain"] else ""))
    for k in (0.0405, 0.147, 0.5):
        db = detuning_knob_bits(k, R_um=R, alpha_bend_dBcm=BL)
        print("  失谐旋钮 κ=%.4f: FWHM=%.2f pm worst|dw/dλ|=%.3f /nm ⇒ bits=%.2f 达标=%s"
              % (k, db["fwhm_pm"], db["worst_dwdlam_per_nm"], db["bits_range"],
                 db["budget_met"]))

    print("\n-- 面积对比 --")
    ar = area_vs_eo_modulator(R, gap_um=GAP)
    print("  环 %.2f µm² · EO(π臂 %.0fµm) %.1f µm² ⇒ %.4f%% (达标=%s)"
          % (ar["ring_area_um2"], ar["ps_arm_um"], ar["eo_area_pi_arm_um2"],
             100 * ar["ratio_pi_arm"], ar["budget_met_pi_arm"]))
    print("  对照：EO(胞元 %.0fµm) %.1f µm² ⇒ %.2f%%（非物理参照）"
          % (ar["unit_cell_um"], ar["eo_area_unit_cell_um2"],
             100 * ar["ratio_unit_cell"]))

    print("\n-- 权重库映射 + 共网格 --")
    bank = weight_bank_from_weights([0.02, 0.04, 0.06, 0.08], wl_nm=[1550, 1552.5, 1555, 1557.5])
    print("  表内 gap = %s · 表外 %d/%d 个"
          % (bank["table_gaps_um"], bank["n_gap_outside_signed_table"], bank["n_channels"]))
    for e in bank["entries"]:
        print("    w=%.3f wl=%.1f R=%.4f κ=%.6f gap=%s 表内=%s FWHM=%.1f pm 选择性=%s"
              % (e["w_target"], e["wl_nm"], e["R_um"], e["kappa"],
                 ("%.4f" % e["gap_um"]) if e["gap_um"] else "不可达",
                 e["gap_in_signed_table"], e["fwhm_pm"], e["selectivity_ok"]))
    mesh = weight_bank_on_shared_mesh([0.02, 0.04, 0.06, 0.08])
    print("  共网格 K=%d N=%d n_mzi=%d 网格保真度=%.15f (保持=%s) 对角=%s 选择性全通=%s"
          % (mesh["K"], mesh["N"], mesh["n_mzi"], mesh["mesh_fidelity"],
             mesh["mesh_fidelity_preserved"], mesh["weight_layer_is_diagonal"],
             mesh["all_selectivity_ok"]))
    print("\n披露键:", sorted(RING_WEIGHT_DISCLOSURE.keys()))
    print(json.dumps(bank["entries"][0], ensure_ascii=False, indent=1)[:400])
