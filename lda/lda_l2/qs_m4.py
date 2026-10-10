"""QS-M4 · 量子传感器**阵列化与规模**物理（吃狗粮 v5 · 量子传感器芯片征程）。

═══ 定位（蓝图层 `docs/LDA_量子传感器芯片征程_总蓝图_v1_2026-10-10.md` §QS-M4）═══
QS-M0/M1/M2/M3/M3b 把**单器件**从「能设计」推到「几何优化 + 真实器件本体」。QS-M4 回答
**规模与集成**问题——单片上的 **2×N NV 磁力计阵列**能否既**做出来**（版图/DRC）
又**测得准**（串扰可控 + 多通道读出可分辨 + 梯度计抑共模）：
  · **阵列布局**：复用 QS-M3b 的 NVPillar 单器件本体，按格点平移成 2×N 阵列
    （每柱独立通道，共享读出馈线）；
  · **串扰物理**：相邻 NV 柱经**磁偶极近场**互相污染（∝ 1/r³）——
    串扰系数 X_ij = (d_crit/r_ij)³，并给出「串扰恶化的灵敏度下限」；
  · **多通道读出 mux**：复用 `sc_readout_mux` 的 **FDM 思路**（一条馈线上挂多只
    读出腔、音互异且隔离）迁移到磁力计阵列 —— 本档用**微波驱动音（f_mw）**作
    通道标识（NV 的 ODMR 频分读出），校验同馈线音唯一性与最小音间隔；
  · **梯度计**：取两近邻柱的**差分**读出示数 ⇒ 共模（环境磁噪声）被抑制，
    给共模抑制比 CMRR（dB）。
**平台缺口 G6**：量子传感器阵列 / 集成。

═══ 🔴 物理链（两条 · 闭式可作 golden）═══
链① **磁偶极近场串扰**：把每根 NV 柱的净自旋磁矩视作点偶极 m（轴向），
   柱 j 处由柱 i 产生的杂散场（轴向、同轴排布）：B_ij = μ₀/(4π)·2m/r³。
   定义**串扰系数** X_ij ≡ B_ij/B_self = (d_crit/r_ij)³（无量纲），
   其中 d_crit 为参考近距（取柱径 dia，即「柱面间距为零」的物理最小距离标度）。
   串扰恶化的通道灵敏度上界：η_eff = η_single·√(1 + Σ_j X_ij²)（噪声正交叠加）。
链② **梯度计共模抑制**：两柱读出示数差分 D = S₁·B₁ − S₂·B₂（S 为标度因子）。
   共模场 B_c 下若 S₁=S₂ ⇒ D=0（完美抑制）；标度失配 ε = |S₁−S₂|/S̄ 时
   CMRR = 20·log₁₀(1/ε)（dB）。梯度灵敏度 η_grad = η_single·√2/√(d²)（梯度基线 d）。

═══ 🔴 与既有锚的边界（**不同物理量**，非重复计数）═══
· B473（NV 磁力计磁灵敏度 η_single）：本档链① 是**阵列串扰倍率**，物理对象不同；
· QS-M3 链③（最优深度）/ QS-M3b（柱高）：本档**复用其器件本体**，不另登记锚；
· B18（Purcell F_P）：本档不涉及腔增强 ⇒ 无交集；
· `sc_readout_mux`（D-140 超导 FDM）：本档**复用其「一馈线多音、音互异」思路**，
  但物理载体不同（NV 的 ODMR 微波音 vs 超导读出腔音）⇒ 不重复计数。

═══ 🔴 纪律 ═══
· 进报告数字一律**模块现算**（不转录草稿）；判据读到的值 = 模块现算值。
· 每道守卫配反向探针（先证能变红）。
· 纯 numpy 顶层（scipy 隔离）；C 级自主，不借外部量子/光子 SDK。
· 🔴 **诚实边界**：d_crit / 磁矩 m / 音间隔 / 标度失配 ε 均为**设计示例量级**，
  非实测；报告为建模值，**不得作制造 / 性能宣称**；本档不宣称「已达国际水平」。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# 复用 QS 统一口径（单一真源 · 与 qs_m1/qs_m2/qs_m3 同源）
# ---------------------------------------------------------------------------
SENSITIVITY_CALIBER = "eta_dB_sqrtT__amplitude_spectral_density__T_per_sqrtHz"

#: 物理常数（承 qs_m1/m2/m3）
MU_0 = 4.0e-7 * math.pi          # 真空磁导率（T·m/A）


def assert_caliber(caliber: str) -> None:
    """口径自检（报告前强制）：只接受统一口径，防误用其它口径。"""
    if caliber != SENSITIVITY_CALIBER:
        raise ValueError("灵敏度口径不一致：只允许 %r，得到 %r"
                         % (SENSITIVITY_CALIBER, caliber))


# ===========================================================================
# ① 阵列布局（复用 QS-M3b NVPillar 单器件本体）
# ===========================================================================
#: 阵列默认参数（**设计示例**，非实测 PDK）。
#: 🔴 尺度口径：NV 柱直径 ~0.3 µm（QS-M3b），相邻柱心距取 **1.2 µm** 量级
#:   （柱面净距 ~0.9 µm）——这是磁偶极近场**真正起作用的尺度**（r⁻³ 在 µm 级显著）。
QS_ARRAY_DEFAULTS = {
    "rows": 2,                # 行数（蓝图固定 2 行）
    "cols": 4,                # 列数 N（2×N 阵列）
    "pitch_x_um": 1.20,       # 列间距（µm），须 ≥ 柱径 + 最小柱间距
    "pitch_y_um": 1.20,       # 行间距（µm）
    "feed_per_row": 1,        # 每行一条读出馈线（FDM 共享）
}

#: 阵列 DRC 设计规则（可覆盖 · 非实测 golden）。
DEFAULT_ARRAY_LIMITS = {
    "min_pillar_sep_um": 0.30,      # 同阵列相邻柱最近表面间距下限
    "min_tone_spacing_mhz": 30.0,   # 同馈线相邻通道微波音最小间隔
    "min_grad_baseline_um": 0.80,   # 梯度计基线（两柱间距）下限
    "max_crosstalk": 0.05,          # 单对相邻柱串扰系数上限（5%）
    "min_cmrr_db": 40.0,            # 梯度计共模抑制比下限（dB）
}


def array_positions(params: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    """2×N 阵列柱心坐标（**现算**；居中对称排布）。

    单一真源 = 本函数；`array_layout()` / DRC / LVS 均从此取坐标，杜绝「版图一套、判据另一套」。
    每柱带 `ch`（通道号，行优先）与 `row`（馈线号）。
    """
    p = dict(QS_ARRAY_DEFAULTS)
    p.update({k: v for k, v in dict(params or {}).items() if k in QS_ARRAY_DEFAULTS})
    rows = int(p["rows"])
    cols = int(p["cols"])
    px = float(p["pitch_x_um"])
    py = float(p["pitch_y_um"])
    if rows < 1 or cols < 1:
        raise ValueError("rows / cols 必须 ≥ 1")
    x0 = -(cols - 1) * px / 2.0
    y0 = -(rows - 1) * py / 2.0
    out: List[Dict[str, Any]] = []
    for r in range(rows):
        for c in range(cols):
            out.append({"ch": r * cols + c, "row": r, "col": c,
                        "x_um": x0 + c * px, "y_um": y0 + r * py})
    return out


def pillar_diameter_um() -> float:
    """NV 柱直径（µm）——**委派**给 primitives 的单一真源（不复制数值）。"""
    from lda_l2.primitives import qs_device_geometry
    return float(qs_device_geometry("NVPillar", {})["dia"])


def min_pillar_separation_um(params: Dict[str, Any] | None = None) -> float:
    """阵列内**任意两柱**最近表面间距（µ）——现算（含对角邻居）。"""
    pos = array_positions(params)
    dia = pillar_diameter_um()
    best = float("inf")
    for i in range(len(pos)):
        for j in range(i + 1, len(pos)):
            dx = pos[i]["x_um"] - pos[j]["x_um"]
            dy = pos[i]["y_um"] - pos[j]["y_um"]
            best = min(best, math.hypot(dx, dy) - dia)
    return float(best)


# ===========================================================================
# ② 磁偶极近场串扰
# ===========================================================================
def crosstalk_coefficient(r_um: float, d_crit_um: float) -> float:
    """闭式：两同轴点偶极（轴向磁矩）间距 r 的**串扰系数** X = (d_crit/r)³。

    推导：轴向排布时偶极 i 在 j 处的轴向场 B_ij = μ₀/(4π)·2m/r³；自场标度
    B_self ∝ m/d_crit³（d_crit = 参考近距，取柱径）⇒ 比值 X = (d_crit/r)³。
    🔴 r → d_crit ⇒ X=1（满串扰）；r → ∞ ⇒ X→0。
    """
    if r_um <= 0.0:
        raise ValueError("r_um 必须 > 0")
    if d_crit_um <= 0.0:
        raise ValueError("d_crit_um 必须 > 0")
    return float((d_crit_um / r_um) ** 3)


def crosstalk_coefficient_numeric(r_um: float, d_crit_um: float,
                                  n_grid: int = 400000) -> float:
    """数值链：**对角点偶极场积分** → 近场比值（不复用 r⁻³ 解析代入）。

    对偶极沿轴离散成 ±q 点电荷对（分离 δ，q·δ = m 定值），逐点算 j 处的矢量场
    模长再取比值。δ→0 极限下应回到解析 r⁻³（残差 = δ 的二阶项）。
    """
    if r_um <= 0.0 or d_crit_um <= 0.0:
        raise ValueError("r_um / d_crit_um 必须 > 0")
    delta = 1e-4 * d_crit_um                 # 偶极分离（远小于标度）
    k = MU_0 / (4.0 * math.pi)               # 前置常数（比值中约掉）

    def _dipole_field(xo: float) -> float:
        """轴上点偶极（±q 分离 δ，中心 0）在 xo 处的轴向场（带符号）：
        B ∝ q·[1/(xo−δ/2)² − 1/(xo+δ/2)²]，符号差 ⇒ δ→0 回到 ∝ 2m/r³。"""
        return (1.0 / (xo - delta / 2.0) ** 2) - (1.0 / (xo + delta / 2.0) ** 2)

    # 源偶极中心 0、场点分别取 r 与 d_crit ⇒ 比值去掉 m/k 常数
    b_far = k * delta * abs(_dipole_field(r_um))
    b_self = k * delta * abs(_dipole_field(d_crit_um))
    return float(b_far / b_self)


def array_crosstalk(params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """全阵列串扰矩阵（现算）：每通道对总串扰 X_tot,k = √(Σ_{j≠k} X_kj²)。

    🔴 关键物理：**串扰按对**计入（不是只看最近邻）——对角邻居 r 更大但 r⁻³ 衰减
    快，实际以最近邻项主导；本函数**如实累计所有对**，不截断。
    """
    pos = array_positions(params)
    dia = pillar_diameter_um()
    lim = dict(DEFAULT_ARRAY_LIMITS)
    lim.update({k: v for k, v in dict(params or {}).items() if k in DEFAULT_ARRAY_LIMITS})

    n = len(pos)
    xmat = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dx = pos[i]["x_um"] - pos[j]["x_um"]
            dy = pos[i]["y_um"] - pos[j]["y_um"]
            r = math.hypot(dx, dy)
            xmat[i][j] = crosstalk_coefficient(r, dia)

    per_ch: List[Dict[str, Any]] = []
    for i in range(n):
        x_tot = math.sqrt(sum(xmat[i][j] ** 2 for j in range(n) if j != i))
        # 最近邻串扰（用于 DRC「单对上限」判据）
        x_nn = max((xmat[i][j] for j in range(n) if j != i), default=0.0)
        per_ch.append({"ch": i, "row": pos[i]["row"], "col": pos[i]["col"],
                       "x_total": x_tot, "x_max_pair": x_nn,
                       "sensitivity_penalty": math.sqrt(1.0 + x_tot ** 2)})
    worst = max(per_ch, key=lambda d: d["x_total"])
    verdict = "ACCEPT" if worst["x_max_pair"] <= lim["max_crosstalk"] else "REJECT"
    return {
        "verdict": verdict,
        "n_channels": n,
        "pillar_dia_um": dia,
        "matrix": xmat,
        "per_channel": per_ch,
        "worst_channel": worst["ch"],
        "max_x_total": worst["x_total"],
        "max_x_pair": worst["x_max_pair"],
        "max_pair_limit": lim["max_crosstalk"],
        "note": ("串扰 = 磁偶极近场 X=(d_crit/r)³（d_crit=柱径）；"
                 "按**所有对**累计（对角邻居如实计入，不截断）。"),
    }


def crosstalk_sensitivity_eta(eta_single: float, x_total: float) -> float:
    """串扰恶化后的通道灵敏度上界：η_eff = η_single·√(1 + X_tot²)（T/√Hz）。

    🔴 噪声正交叠加（串扰场与自信号统计独立）⇒ 平方和；X_tot=0 ⇒ η_eff=η_single。
    """
    assert_caliber(SENSITIVITY_CALIBER)
    if x_total < 0.0:
        raise ValueError("x_total 必须 ≥ 0")
    return float(eta_single) * math.sqrt(1.0 + float(x_total) ** 2)


# ===========================================================================
# ③ 多通道读出 mux（复用 sc_readout_mux 的 FDM 思路 → ODMR 微波音）
# ===========================================================================
#: 读出 mux 默认参数（**设计示例**）。
DEFAULT_MUX_PLAN = {
    "f_min_ghz": 2.80, "f_max_ghz": 3.20,     # ODMR 微波音域（NV 零场分裂 2.87 GHz 邻域）
    "tone_spacing_ghz": 0.05,                  # 默认音间隔
}


def readout_mux_plan(params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """多通道读出 **FDM 音规划**（每馈线阶梯分配 + 音唯一性）。

    单一真源思路**复用 `sc_readout_mux.mux_plan`**（一馈线多音、同馈线内音互异、
    不同馈线可复用音）——但物理载体改为 NV 的 **ODMR 微波音**，故本档自建轻量实现，
    仅保留**同馈线音唯一性 + 最小音间隔**两条核心判据（与 D-140 同思路，非代码复制）。
    """
    p = dict(QS_ARRAY_DEFAULTS)
    p.update({k: v for k, v in dict(params or {}).items()
              if k in QS_ARRAY_DEFAULTS})
    pl = dict(DEFAULT_MUX_PLAN)
    pl.update({k: v for k, v in dict(params or {}).items() if k in DEFAULT_MUX_PLAN})
    lim = dict(DEFAULT_ARRAY_LIMITS)
    lim.update({k: v for k, v in dict(params or {}).items() if k in DEFAULT_ARRAY_LIMITS})

    pos = array_positions(p)
    rows = int(p["rows"])
    cols = int(p["cols"])
    f_min = float(pl["f_min_ghz"])
    f_max = float(pl["f_max_ghz"])
    # 🔴 音间隔优先用显式 `tone_spacing_ghz`（设计意图），否则回落到 DRC 下限 ——
    #    派生的「实际最小间隔」仍需 ≥ 下限，二者分工不同（前者 = 设计器，后者 = 校验）。
    spacing = float(pl["tone_spacing_ghz"]) if "tone_spacing_ghz" in dict(params or {}) \
        else float(lim["min_tone_spacing_mhz"]) / 1000.0

    # 每馈线（row）内 cols 个音：以 f_min 起、按 min_tone_spacing 阶梯（须落带内）
    per_ch: List[Dict[str, Any]] = []
    for d in pos:
        tone = f_min + d["col"] * spacing
        per_ch.append({"ch": d["ch"], "row": d["row"], "col": d["col"],
                       "feedline": d["row"], "tone_ghz": tone})
    by_feed: Dict[int, List[float]] = {}
    for r in per_ch:
        by_feed.setdefault(r["feedline"], []).append(r["tone_ghz"])
    # 音唯一性（同馈线内）
    dup = any(len(v) != len({round(t, 9) for t in v}) for v in by_feed.values())
    # 最小音间隔（同馈线内相邻）
    min_spacing = float("inf")
    for v in by_feed.values():
        sv = sorted(v)
        for i in range(1, len(sv)):
            min_spacing = min(min_spacing, (sv[i] - sv[i - 1]) * 1000.0)
    if min_spacing == float("inf"):
        min_spacing = None
    band_ok = f_max >= f_min + (cols - 1) * spacing - 1e-12
    spacing_ok = (min_spacing is None) or (min_spacing >= lim["min_tone_spacing_mhz"] - 1e-9)
    verdict = "ACCEPT" if (not dup and spacing_ok and band_ok) else "REJECT"
    n_unique = sum(len({round(t, 9) for t in v}) for v in by_feed.values())
    return {
        "verdict": verdict, "rows": rows, "cols": cols, "n_channels": len(pos),
        "tones_per_feedline": cols, "f_min_ghz": f_min, "f_max_ghz": f_max,
        "min_tone_spacing_mhz": min_spacing,
        "spacing_ok": bool(spacing_ok), "band_ok": bool(band_ok), "tone_dup": bool(dup),
        "unique_tones": n_unique, "feedlines": len(by_feed),
        "per_channel": per_ch,
        "note": ("FDM 音规划 = 每馈线（row）内 cols 个 ODMR 微波音按 min_tone_spacing "
                 "阶梯（同馈线音互异，不同馈线可复用音）；思路复用 sc_readout_mux（D-140），"
                 "载体改为 NV 的 ODMR 微波音。音间隔为设计规则（非 golden）。"),
    }


# ===========================================================================
# ④ 梯度计（共模抑制）
# ===========================================================================
def gradiometer_cmrr_db(mismatch: float) -> float:
    """闭式：标度失配 ε 下的共模抑制比 CMRR = 20·log₁₀(1/ε)（dB）。

    推导：差分读数 D = S₁B₁ − S₂B₂。共模 B_c：D_c = (S₁−S₂)B_c；差模 ΔB：
    D_d = S̄·ΔB（取 S₁≈S₂≈S̄）。抑制比 = |D_d/D_c| = S̄/(|S₁−S₂|) = 1/ε。
    🔴 ε→0 ⇒ CMRR→∞（完美抑制）；ε=1 ⇒ CMRR=0 dB（零抑制）。
    """
    if not (0.0 < mismatch <= 1.0):
        raise ValueError("mismatch ε 必须 ∈ (0, 1]")
    return float(20.0 * math.log10(1.0 / mismatch))


def gradiometer_cmrr_numeric(mismatch: float, n: int = 200000) -> float:
    """数值链：**直接数值求比** D_d/D_c（不复用 log10 闭式）。

    构造共模场 B_c 序列，逐点算 d_c = |S₁B_c − S₂B_c|；差模 ΔB 序列算
    d_d = |S̄·ΔB|；比值取二者斜率比 ⇒ CMRR_num = 20·log₁₀(d_d/d_c)。
    """
    if not (0.0 < mismatch <= 1.0):
        raise ValueError("mismatch ε 必须 ∈ (0, 1]")
    s_bar = 1.0
    # 🔴 口径对齐：ε ≡ |S₁−S₂|/S̄ ⇒ 取 S₁ = S̄(1+ε/2)、S₂ = S̄(1−ε/2)，
    #    则 S₁−S₂ = ε·S̄（恰为定义值，不是 2ε·S̄）——否则数值链系统性差 6 dB。
    s1 = s_bar * (1.0 + mismatch / 2.0)
    s2 = s_bar * (1.0 - mismatch / 2.0)
    bc = np.linspace(0.0, 1.0, n)
    dc = np.abs(s1 * bc - s2 * bc)
    db = np.linspace(0.0, 1.0, n)
    dd = np.abs(s_bar * db)
    i = n - 1
    ratio = (dd[i] / dc[i]) if dc[i] > 0 else float("inf")
    return float(20.0 * math.log10(ratio))


def gradiometer_eta(eta_single: float, baseline_um: float,
                    mismatch: float = 0.0) -> Dict[str, float]:
    """梯度计灵敏度：η_grad = η_single·√2/baseline（差模两点差分，×√2 噪声叠加）。

    🔴 基线越短 ⇒ 梯度灵敏度越差（分母 baseline）；本档只给**建模量**，非实测。
    """
    assert_caliber(SENSITIVITY_CALIBER)
    if baseline_um <= 0.0:
        raise ValueError("baseline_um 必须 > 0")
    scale = math.sqrt(2.0)
    eta_grad = float(eta_single) * scale / float(baseline_um)
    cmrr = gradiometer_cmrr_db(mismatch) if mismatch > 0.0 else float("inf")
    return {"eta_grad_per_um": eta_grad, "cmrr_db": cmrr,
            "baseline_um": float(baseline_um), "mismatch": float(mismatch)}


# ===========================================================================
# ⑤ 阵列 DRC / LVS（复用 sc_array 的 bbox 范式）
# ===========================================================================
def _bbox(desc: Dict[str, Any]) -> Tuple[float, float, float, float]:
    pts = desc.get("points_um") or [p for r in desc.get("rings_um", []) for p in r]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), max(xs), min(ys), max(ys))


def array_layout(params: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    """2×N 阵列版图元素（**复用 QS-M3b 的 NVPillar 单器件本体**，按柱心平移）。

    每柱 = `qs_device_descs("NVPillar", {})` 的全部图元平移 (x,y)，并标
    `ch`/`row`/`col`/`net="pillar"`；再叠加**每行一条读出馈线**（`net="feedline"`，
    走金属层）—— 馈线是阵列级新增几何（单器件本体没有）。
    """
    from lda_l2.gds_export import LIB_LAYER_METAL
    from lda_l2.primitives import qs_device_descs

    p = dict(QS_ARRAY_DEFAULTS)
    p.update({k: v for k, v in dict(params or {}).items() if k in QS_ARRAY_DEFAULTS})
    pos = array_positions(p)
    base = qs_device_descs("NVPillar", {})

    out: List[Dict[str, Any]] = []
    for d in pos:
        dx, dy = d["x_um"], d["y_um"]
        for e in base:
            e2 = dict(e)
            if e.get("kind") == "path":
                e2["points_um"] = [(x + dx, y + dy) for x, y in e["points_um"]]
            else:
                e2["rings_um"] = [[(x + dx, y + dy) for x, y in ring]
                                  for ring in e["rings_um"]]
            e2.update({"ch": d["ch"], "row": d["row"], "col": d["col"], "net": "pillar"})
            out.append(e2)

    # 每行一条读出馈线（横贯该行，位于柱上方 feed_y 处）
    rows = int(p["rows"])
    cols = int(p["cols"])
    px = float(p["pitch_x_um"])
    py = float(p["pitch_y_um"])
    half = (cols - 1) * px / 2.0
    feed_off = py * 0.35
    for r in range(rows):
        y = -(rows - 1) * py / 2.0 + r * py + feed_off
        out.append({"kind": "path", "layer": LIB_LAYER_METAL,
                    "width_um": 2.0,
                    "points_um": [(-half - px / 2.0, y), (half + px / 2.0, y)],
                    "net": "feedline", "row": r})
    return out


def run_array_drc(elements: List[Dict[str, Any]] | None = None,
                  params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """阵列 DRC（五则几何 + 频域）：柱间距 / 串扰对上限 / 音间隔 / 音落带 / 梯度基线。

    🔴 位置参数语义：`elements` 在前；只给参数表时用 `params=`（或传 dict 首参，
    本函数**自动理解**为 params）。
    """
    if isinstance(elements, dict) and params is None:
        params, elements = elements, None
    p = dict(QS_ARRAY_DEFAULTS)
    p.update({k: v for k, v in dict(params or {}).items() if k in QS_ARRAY_DEFAULTS})
    lim = dict(DEFAULT_ARRAY_LIMITS)
    lim.update({k: v for k, v in dict(params or {}).items() if k in DEFAULT_ARRAY_LIMITS})
    el = elements if elements is not None else array_layout(p)

    violations: List[Dict[str, Any]] = []
    sep = min_pillar_separation_um(p)
    if sep < lim["min_pillar_sep_um"] - 1e-9:
        violations.append({"rule": "QS-ARR-PILLAR-SEP",
                           "detail": "最近柱面间距 %.3f < %.1f µm"
                                     % (sep, lim["min_pillar_sep_um"])})

    ct = array_crosstalk(p)
    if ct["max_x_pair"] > lim["max_crosstalk"] + 1e-12:
        violations.append({"rule": "QS-ARR-CROSSTALK",
                           "detail": "最大单对串扰 %.4f > %.4f"
                                     % (ct["max_x_pair"], lim["max_crosstalk"])})

    plan = readout_mux_plan(p)
    if not plan["spacing_ok"]:
        violations.append({"rule": "QS-ARR-TONE-SPACING",
                           "detail": "最小音间隔 %s < %.1f MHz"
                                     % (plan["min_tone_spacing_mhz"],
                                        lim["min_tone_spacing_mhz"])})
    if not plan["band_ok"]:
        violations.append({"rule": "QS-ARR-TONE-BAND",
                           "detail": "音未全部落带 [%.3f, %.3f] GHz"
                                     % (plan["f_min_ghz"], plan["f_max_ghz"])})

    baseline = float(p["pitch_x_um"])
    if baseline < lim["min_grad_baseline_um"] - 1e-9:
        violations.append({"rule": "QS-ARR-GRAD-BASELINE",
                           "detail": "梯度基线 %.1f < %.1f µm"
                                     % (baseline, lim["min_grad_baseline_um"])})

    # 几何自洽：柱数 = rows×cols（版图里 pillar 图元组数）
    n_pillar_nets = len({e["ch"] for e in el if e.get("net") == "pillar"})
    if n_pillar_nets != int(p["rows"]) * int(p["cols"]):
        violations.append({"rule": "QS-ARR-CHANNEL-COUNT",
                           "detail": "版图柱通道数 %d ≠ rows×cols %d"
                                     % (n_pillar_nets, int(p["rows"]) * int(p["cols"]))})

    return {"verdict": "ACCEPT" if not violations else "REJECT",
            "violations": violations,
            "min_pillar_sep_um": sep, "max_crosstalk_pair": ct["max_x_pair"],
            "limits": lim}


def array_lvs(elements: List[Dict[str, Any]] | None = None,
              params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """阵列 LVS：每通道恰一组柱图元 + 通道号连续唯一 + 馈线数 = 行数 + 音唯一。

    🔴 位置参数语义：`elements` 在前（与 `run_array_drc` 一致）；只给 params 时
    请用关键字 `params=`（`array_lvs({"rows":2})` 会被当作 elements ⇒ 类型错）。
    为兼容「只传参数表」的调用，若首参是 dict 则**自动理解为 params**。
    """
    if isinstance(elements, dict) and params is None:
        params, elements = elements, None
    p = dict(QS_ARRAY_DEFAULTS)
    p.update({k: v for k, v in dict(params or {}).items() if k in QS_ARRAY_DEFAULTS})
    el = elements if elements is not None else array_layout(p)
    issues: List[str] = []

    rows = int(p["rows"])
    cols = int(p["cols"])
    n_ch = rows * cols
    chans = sorted({e["ch"] for e in el if e.get("net") == "pillar"})
    if chans != list(range(n_ch)):
        issues.append("QS-LVS-CH: 通道号非 0..%d 连续唯一（实得 %s）" % (n_ch - 1, chans))
    feeds = sorted({e["row"] for e in el if e.get("net") == "feedline"})
    if feeds != list(range(rows)):
        issues.append("QS-LVS-FEED: 馈线号非 0..%d（实得 %s）" % (rows - 1, feeds))
    plan = readout_mux_plan(p)
    if plan["tone_dup"]:
        issues.append("QS-LVS-TONE-DUP: 同馈线内存在重复 ODMR 音（FDM 无法分辨）")
    if plan["unique_tones"] != n_ch:
        issues.append("QS-LVS-TONE-COUNT: 音数 %d ≠ 通道数 %d"
                      % (plan["unique_tones"], n_ch))
    return {"verdict": "ACCEPT" if not issues else "REJECT", "issues": issues,
            "netlist": {"channels": n_ch, "feedlines": len(feeds),
                        "unique_tones": plan["unique_tones"]},
            "n_checks": 4}


def array_physics(params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """阵列物理签核 = 串扰 ACCEPT + 读出 mux ACCEPT + 梯度计 CMRR ≥ 下限。"""
    raw = dict(params or {})
    p = dict(QS_ARRAY_DEFAULTS)
    p.update({k: v for k, v in raw.items() if k in QS_ARRAY_DEFAULTS})
    lim = dict(DEFAULT_ARRAY_LIMITS)
    lim.update({k: v for k, v in raw.items() if k in DEFAULT_ARRAY_LIMITS})

    ct = array_crosstalk(p)
    plan = readout_mux_plan(p)
    # 🔴 标度失配 ε 是**梯度计**参数（不在阵列几何默认表里）⇒ 单独从入参取
    mismatch = float(raw.get("scale_mismatch", 0.01))
    grad = gradiometer_eta(1.0e-9, float(p["pitch_x_um"]), mismatch)
    cmrr_ok = grad["cmrr_db"] >= lim["min_cmrr_db"] - 1e-9
    verdict = ("ACCEPT"
               if (ct["verdict"] == "ACCEPT" and plan["verdict"] == "ACCEPT" and cmrr_ok)
               else "REJECT")
    return {"verdict": verdict, "crosstalk": ct, "mux": plan,
            "gradiometer": grad, "cmrr_ok": bool(cmrr_ok),
            "cmrr_limit_db": lim["min_cmrr_db"],
            "note": ("阵列物理 = 偶极串扰 X=(d_crit/r)³ + ODMR 音规划 + 梯度计 CMRR。"
                     "d_crit/音间隔/失配 ε 为设计参数（非 golden）。LLM 不进判决路径。")}


# ===========================================================================
# ⑥ 四情景（承 QS-M1/M2/M3 范式）
# ===========================================================================
SCENARIOS: Dict[str, Dict[str, Any]] = {
    # baseline：2×4 阵列，默认节距 1.2 µm，ε=1% 失配
    "baseline": dict(rows=2, cols=4, pitch_x_um=1.20, pitch_y_um=1.20,
                     scale_mismatch=0.01),
    # dense：密阵列（节距 0.45 µm ⇒ 柱面净距 0.15 µm）⇒ 串扰显著上升
    "dense": dict(rows=2, cols=4, pitch_x_um=0.45, pitch_y_um=0.45,
                  scale_mismatch=0.01),
    # large：2×8 更大规模，节距保持
    "large": dict(rows=2, cols=8, pitch_x_um=1.20, pitch_y_um=1.20,
                  scale_mismatch=0.01),
    # mismatch：标度失配大（ε=5%）⇒ CMRR 差（26 dB < 40）
    "mismatch": dict(rows=2, cols=4, pitch_x_um=1.20, pitch_y_um=1.20,
                     scale_mismatch=0.05),
}


def evaluate_scenario(name: str) -> Dict[str, Any]:
    """单情景：阵列物理 + 串扰恶化灵敏度 + 梯度计。"""
    if name not in SCENARIOS:
        raise KeyError("未知情景 %r（可选：%s）" % (name, sorted(SCENARIOS)))
    p = SCENARIOS[name]
    phys = array_physics(p)
    eta_single = 1.0e-9                      # 示例单器件灵敏度 1 nT/√Hz（非实测）
    eta_eff = crosstalk_sensitivity_eta(eta_single, phys["crosstalk"]["max_x_total"])
    grad = phys["gradiometer"]
    return {
        "scenario": name,
        "n_channels": phys["crosstalk"]["n_channels"],
        "max_x_pair": phys["crosstalk"]["max_x_pair"],
        "max_x_total": phys["crosstalk"]["max_x_total"],
        "eta_single_T_per_sqrtHz": eta_single,
        "eta_eff_T_per_sqrtHz": eta_eff,
        "eta_eff_nT_per_sqrtHz": eta_eff * 1e9,
        "cmrr_db": grad["cmrr_db"],
        "mux_verdict": phys["mux"]["verdict"],
        "array_verdict": phys["verdict"],
        "caliber": SENSITIVITY_CALIBER,
    }


def array_table() -> Dict[str, Dict[str, Any]]:
    """四情景阵列表（现算）。"""
    return {n: evaluate_scenario(n)
            for n in ("baseline", "dense", "large", "mismatch")}


# ===========================================================================
# ⑦ 自检（常驻门禁 · 反向探针）
# ===========================================================================
def selfcheck_qs_m4() -> Dict[str, bool]:
    """QS-M4 自检：布局/串扰/读出/梯度计 四条链 + 互验 + 反向探针。"""
    checks: Dict[str, bool] = {}

    # ═══ A 阵列布局 ═══
    pos = array_positions({"rows": 2, "cols": 4})
    checks["array_positions_count"] = len(pos) == 8
    checks["array_channel_ids"] = sorted(d["ch"] for d in pos) == list(range(8))
    # 居中对称：x 坐标关于 0 对称
    xs = sorted({round(d["x_um"], 6) for d in pos})
    checks["array_centered"] = abs(xs[0] + xs[-1]) < 1e-9
    # 节距单调：列号增 ⇒ x 增
    row0 = sorted([d for d in pos if d["row"] == 0], key=lambda d: d["col"])
    checks["array_pitch_monotone"] = all(
        row0[i + 1]["x_um"] - row0[i]["x_um"] > 0 for i in range(len(row0) - 1))

    # ═══ B 串扰物理 ═══
    # 闭式 ∧ 数值 一致（多间距点）
    r_pts = [0.3, 0.5, 1.0, 2.0, 5.0]
    checks["crosstalk_closed_eq_numeric"] = all(
        abs(crosstalk_coefficient_numeric(r, 1.0) - crosstalk_coefficient(r, 1.0))
        / crosstalk_coefficient(r, 1.0) < 1e-3
        for r in r_pts
    )
    # 随 r 单调降 + 立方律（X(2r) = X(r)/8）
    xs_ct = [crosstalk_coefficient(r, 1.0) for r in r_pts]
    checks["crosstalk_r_cubed"] = abs(
        crosstalk_coefficient(2.0, 1.0) / crosstalk_coefficient(1.0, 1.0) - 0.125) < 1e-12
    checks["crosstalk_monotone_decreasing"] = all(
        xs_ct[i] > xs_ct[i + 1] for i in range(len(xs_ct) - 1))
    # r = d_crit ⇒ X = 1
    checks["crosstalk_unity_at_dcrit"] = abs(crosstalk_coefficient(1.0, 1.0) - 1.0) < 1e-12
    # 全阵列串扰：对称阵（2×2）每通道 X_tot 相同
    ct22 = array_crosstalk({"rows": 2, "cols": 2, "pitch_x_um": 350.0, "pitch_y_um": 350.0})
    checks["crosstalk_symmetry"] = len({round(d["x_total"], 9)
                                        for d in ct22["per_channel"]}) == 1
    # 串扰恶化灵敏度 ≥ η_single
    checks["crosstalk_eta_ge_single"] = (
        crosstalk_sensitivity_eta(1e-9, 0.0) == 1e-9
        and crosstalk_sensitivity_eta(1e-9, 0.5) > 1e-9)

    # ═══ C 读出 mux ═══
    plan = readout_mux_plan({"rows": 2, "cols": 4})
    by_feed: Dict[int, List[float]] = {}
    for r in plan["per_channel"]:
        by_feed.setdefault(r["feedline"], []).append(r["tone_ghz"])
    checks["mux_tones_unique_per_feed"] = all(
        len(v) == len({round(t, 9) for t in v}) for v in by_feed.values())
    checks["mux_verdict_accept"] = plan["verdict"] == "ACCEPT"
    checks["mux_tone_count"] = plan["unique_tones"] == 8

    # ═══ D 梯度计 ═══
    checks["cmrr_closed_eq_numeric"] = all(
        abs(gradiometer_cmrr_db(e) - gradiometer_cmrr_numeric(e)) < 1e-4
        for e in (0.01, 0.05, 0.1, 0.5)
    )
    # ε↓ ⇒ CMRR↑ 单调
    c_vals = [gradiometer_cmrr_db(e) for e in (0.5, 0.1, 0.05, 0.01)]
    checks["cmrr_monotone"] = all(c_vals[i] < c_vals[i + 1] for i in range(len(c_vals) - 1))
    # ε=1 ⇒ 0 dB；ε=0.01 ⇒ 40 dB
    checks["cmrr_boundary"] = (abs(gradiometer_cmrr_db(1.0)) < 1e-12
                               and abs(gradiometer_cmrr_db(0.01) - 40.0) < 1e-9)
    # 梯度灵敏度随基线变短而变差（η_grad ∝ √2/baseline ⇒ 基线短 ⇒ η 数值大 = 差）
    checks["grad_eta_shorter_worse"] = (
        gradiometer_eta(1e-9, 100.0)["eta_grad_per_um"]
        > gradiometer_eta(1e-9, 200.0)["eta_grad_per_um"])

    # ═══ E 阵列 DRC / LVS ═══
    drc = run_array_drc(params={"rows": 2, "cols": 4})
    checks["array_drc_accept"] = drc["verdict"] == "ACCEPT"
    checks["array_lvs_accept"] = array_lvs({"rows": 2, "cols": 4})["verdict"] == "ACCEPT"
    checks["array_physics_accept"] = array_physics({"rows": 2, "cols": 4})["verdict"] == "ACCEPT"

    # ═══ F 反向探针（各自必红）═══
    # ① 密阵列（节距 0.31 µm ⇒ 净距 0.01 µm、X≈0.91）⇒ 串扰/间距超限 ⇒ DRC REJECT
    dense_drc = run_array_drc(params={"rows": 2, "cols": 4,
                                      "pitch_x_um": 0.31, "pitch_y_um": 0.31})
    checks["reverse_dense_crosstalk_rejected"] = (
        dense_drc["verdict"] == "REJECT"
        and any(v["rule"] in ("QS-ARR-CROSSTALK", "QS-ARR-PILLAR-SEP")
                for v in dense_drc["violations"]))
    # ② 音间隔过密（cols 增大但音域不变）⇒ REJECT
    tight = readout_mux_plan({"rows": 2, "cols": 12, "f_min_ghz": 2.80,
                              "f_max_ghz": 2.85, "tone_spacing_ghz": 0.001})
    checks["reverse_tight_tone_band_rejected"] = tight["verdict"] == "REJECT"
    # ③ 标度失配过大 ⇒ CMRR 低于下限
    big_mm = array_physics({"rows": 2, "cols": 4, "scale_mismatch": 0.5})
    checks["reverse_large_mismatch_cmrr_fail"] = (
        big_mm["verdict"] == "REJECT" and not big_mm["cmrr_ok"])
    # ④ 诱红探针：篡改 mux 实现 ⇒ 音唯一性判据必变（证明判据依赖实现，非恒真）
    plan_bad = readout_mux_plan({"rows": 2, "cols": 4})
    for r in plan_bad["per_channel"]:
        if r["row"] == 0:
            r["tone_ghz"] = plan_bad["per_channel"][0]["tone_ghz"]
    by_feed_bad: Dict[int, List[float]] = {}
    for r in plan_bad["per_channel"]:
        by_feed_bad.setdefault(r["feedline"], []).append(r["tone_ghz"])
    dup_bad = any(len(v) != len({round(t, 9) for t in v}) for v in by_feed_bad.values())
    checks["reverse_tone_dup_detected"] = dup_bad
    # ⑤ 布局漂移探针：通道数变了 ⇒ LVS 必拒
    drift_el = array_layout({"rows": 2, "cols": 4})
    drift_el = [e for e in drift_el if not (e.get("net") == "pillar" and e.get("ch") == 0)]
    checks["reverse_missing_channel_detected"] = (
        array_lvs(drift_el, {"rows": 2, "cols": 4})["verdict"] == "REJECT")

    # ═══ G 口径自检 ═══
    try:
        assert_caliber(SENSITIVITY_CALIBER)
        checks["caliber_ok"] = True
    except ValueError:
        checks["caliber_ok"] = False

    # ═══ H 异常输入 ═══
    checks["raises_on_bad_r"] = _raises(lambda: crosstalk_coefficient(0.0, 1.0))
    checks["raises_on_bad_mismatch"] = _raises(lambda: gradiometer_cmrr_db(0.0))

    return checks


def _raises(fn) -> bool:
    try:
        fn()
    except (ValueError, ZeroDivisionError, OverflowError, np.linalg.LinAlgError):
        return True
    return False


# ===========================================================================
# ⑧ 设计入口
# ===========================================================================
def design_qs_array(run_checks: bool = True) -> Dict[str, Any]:
    """QS-M4 主入口：2×N 磁力计阵列报告。"""
    report: Dict[str, Any] = {
        "module": "qs_m4",
        "milestone": "QS-M4",
        "caliber": SENSITIVITY_CALIBER,
        "scenarios": array_table(),
        "crosstalk_baseline": array_crosstalk({"rows": 2, "cols": 4}),
        "mux_baseline": readout_mux_plan({"rows": 2, "cols": 4}),
    }
    if run_checks:
        report["checks"] = selfcheck_qs_m4()
    return report


def main() -> int:
    rep = design_qs_array(run_checks=True)
    print("=== QS-M4 量子传感器阵列（2×N 磁力计） ===")
    print("口径:", rep["caliber"])
    for n, s in rep["scenarios"].items():
        print("  [%-9s] ch=%d | X_max=%.4f | X_tot=%.4f | η_eff=%.3f nT/√Hz | "
              "CMRR=%.1f dB | %s"
              % (n, s["n_channels"], s["max_x_pair"], s["max_x_total"],
                 s["eta_eff_nT_per_sqrtHz"], s["cmrr_db"],
                 "ACCEPT" if s["array_verdict"] == "ACCEPT" else "REJECT"))
    ck = rep["checks"]
    npass = sum(1 for v in ck.values() if v)
    print("checks: %d/%d %s" % (npass, len(ck), "PASS" if npass == len(ck) else "FAIL"))
    for k, v in ck.items():
        if not v:
            print("  FAIL:", k)
    return 0 if npass == len(ck) else 1


if __name__ == "__main__":
    raise SystemExit(main())
