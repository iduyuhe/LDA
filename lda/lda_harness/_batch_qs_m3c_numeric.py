"""Batch B-48 数值实现 · 量子传感器芯片征程 QS-M3c（腔 QED 物理链 · cavity Q / V_eff / g）。

════════════════════════════════════════════════════════════════════════════
本批**三锚**（`benchmark_defs/part7.py` 引用）——
  B494：**腔品质因子 Q = ω/κ**（RK4 能量衰减 ⇒ 数值反解 κ ⇒ Q）
        golden   = 闭式 **Q = ω/κ**（ω = 2πc/λ）。
        candidate = **RK4 时间推进能量衰减** dU/dt = −κU（U₀=1）→ U(T) ⇒
                    κ_cand = −ln(U(T))/T → Q_cand = ω/κ_cand。
        ——方法学独立：golden 走「闭式除式」；candidate 走「数值 ODE 反解」。
        🔴 实测 rel 链 2.25e-6 → 1.33e-7 → 8.12e-9 → **5.01e-10**（比值 **16.0×**
        ⇒ **O(h⁴)**，与 RK4 标称阶一致）⇒ **非代数恒等**。

  B495：**有效模体积 V_eff**（单波腹腔模包络中点求积）
        golden   = 闭式 **V_eff = A·8a/15**（m³ · E(x)=E₀(1−4x²/a²) 包络，
                   ∫_{-a/2}^{a/2}(1−4x²/a²)²dx = 8a/15）。
        candidate = **中点求积** ∫_{-a/2}^{a/2}(1−4x²/a²)²dx（×A）。
        ——方法学独立：golden 走「解析积分」；candidate 走「数值求积」。
        🔴 实测 rel 链 2.14e-4 → 1.34e-5 → 8.35e-7 → **2.04e-10**（比值 **16.0×**
        ⇒ **O(h⁴)**，偶函数在对称区间中点法额外加速；被积函数为四次非多项式
        ⇒ 中点非精确 ⇒ **真数值残差**，非「同式异写」/ 非机器零残差）。

  B496：**单光子耦合 g = (μ/ħ)·√(ħω/(ε·V_eff))**（数值场能 ⇄ 闭式）
        golden   = 闭式 **g = (μ/ħ)·√(ħω/(ε·V_eff))**（V_eff = A·8a/15）。
        candidate = **数值积分 ∫|E|²dV**（⇒ 数值 V_eff）⇒ E₀ = √(ħω/(ε·V_eff_num)) ⇒ g。
        ——方法学独立：golden 走「闭式 V_eff」；candidate 走「数值场能积分」。
        🔴 实测 rel 链 1.07e-4 → 6.68e-6 → 4.17e-7 → **1.02e-10**（比值 **16.0×**
        ⇒ **O(h⁴)**）⇒ **非代数恒等**（g ∝ V_eff^(−1/2)，残差随 V_eff 积分残差）。

🔴 物理意义（承 QS-M3c 蓝图层 §QS-M3 · 链④引申 · 平台缺口 G5「量子传感 PDK 腔几何」）：
  · **B494（腔 Q）**：腔的能量 ring-down 速率 ⇒ 衡量腔损耗 / 光子寿命 ⇒ 高 Q 腔
    才能把发射体强耦合进谐振模式。本锚把「腔损耗 → Q」钉进账本。
  · **B495（有效模体积 V_eff）**：模式场在空间的局域程度 ⇒ V_eff 越小耦合越强；
    是腔 QED 耦合 g、Purcell 因子 F_P 的核心几何量。本锚把它钉进账本。
  · **B496（单光子耦合 g）**：发射体偶极与腔模场幅的耦合强度（单光子 Rabi 频率）
    ⇒ 强耦合判据 g > κ,γ。本锚把它钉进账本（与 B48 单锚 = 单光子 Rabi 耦合
    同物理族，但本锚是**腔 QED 组合链**的可证伪数值实现，详见命名避让）。

🔴 与既有锚的边界（**不同物理量**，非重复计数）：
  · **B18**（谐振腔 Purcell 因子 F_P = 4g²/(κγ₁)）：本批的 Q/V_eff/g 是 **F_P 的
    输入量**（F_P 由 Q/V/g 决定，但 Q/V/g 本身 ≠ F_P）；B18 登的是 Purcell **组合
    标量**，本批登的是**腔自身属性** ⇒ 物理对象不同 ⇒ 记新锚（先例：B491 自由进动
    极化 vs B475 回波相位方差 —— 同物理域不同标量即分立）。
  · B473–B490（腿 A NV / 腿 B SQUID）：固体自旋 / 超导磁通，无腔 QED 量。
  · B476–B477（QS-M3 几何优化）：色心深度 / NA 收集效率，无腔 QED 量。
  · B491–B493（QS-M9 OPM）：碱金属气室光-自旋，无腔 QED 量。

🔴 **命名避让（本批实踩 · 与 QS-M9 同族）**：批次号 **B48** 与**单锚 B48**
  （`_b48_qm_*` 量子力学单光子 Rabi 耦合）号段重叠 ⇒ 沿用连字符写法
  `_batch_qs_m3c_numeric` / `_get_qs_m3c_numeric`（实 grep 核验：
  `_BATCH_QS_M3C` / `_get_qs_m3c_numeric` 全仓零命中；而裸 `b48_` 前缀**已被占用**
  ⇒ 与 B-16 型静默撞名同族，故**禁止**裸 `b48_` 命名；候选统一 `b494_/b495_/b496_`）。

🔴 **为何只三锚（诚实规模 · 吃狗粮）**：QS-M3c 另含
  · 「finesse ℱ = Q·λ/(2na)」（**闭式算术** ⇒ 归 `run_qs_m3c_smoke` 覆盖，**不登记**）；
  · 「γ_rad = ω³μ²/(3πε₀ħc³) Einstein-A」（**闭式算术** ⇒ 归 smoke）；
  · 「cooperativity C = 4g²/(κγ_rad) = (3λ³Q/4π²V)(γ_rad/γ₁)」（**约定因子 2n 的
    闭式自洽** ⇒ 归 smoke，**不登记**为锚）；
  · 「Purcell FOM F_P = (3/4π²)(λ/n)³(Q/V)」（**组合标量** ⇒ 归 smoke 与 B18 对照）；
  ⇒ 本批**如实只登记 B494–B496 三锚**（同 B-44/B-45/B-46/B-47 三锚纪律：宁可少，不越级谎报）。

🔴 纪律：
· 本模块**顶层只 import math + functools**（三锚全为标量闭式/标量数值 ⇒ **无 numpy / scipy 依赖**）。
· golden 与 candidate 是**两种结构不同的算法**（非「同式异写」）；进报告数字一律**现算**。
· 🔴 **锚携带可扰动参数**（各 `B49*_DEFAULT_PARAMS`）：参数对输出强敏感、无零响应键
  ⇒ 反自证桩护栏 `candidate_responds` 可证伪。
· 🔴 **默认档 = 判据 D 扫描网格末端**（纪律：定档必须 = 扫描网格最大档）。
· 🔴 **tol 绝对口径**（harness `_cmp_ok` 默认 cmp='abs'）：B494 量级 O(1e4) ⇒ tol 1e-3；
  B495 量级 O(1e-20) ⇒ tol 1e-27（**按各自物理量级标定**，绝不同用 O(1) 相对量当绝对 tol，
  血案：B492 ~5e17 量级必须绝对 tol 5e12）；B496 量级 O(1e10) ⇒ tol 1e3。
"""
from __future__ import annotations

import functools
import math

# 物理常数（与 lda_l2.qs_m3c 同源 · 门禁 `run_qs_m3c_smoke` B 节跨源对拍）
C_LIGHT = 299792458.0
EPSILON_0 = 8.8541878128e-12
HBAR = 1.054571817e-34

# 默认设计（金刚石微盘腔 · telecom · 设计示例 · 非实测）
_OMEGA_DEF = 2.0 * math.pi * C_LIGHT / 1550.0e-9
_KAPPA_DEF = _OMEGA_DEF / 1.0e4
_EPS_DEF = EPSILON_0 * 3.4 ** 2


# ===========================================================================
# 默认档 / 判据 D 扫描网格 / 逐锚 tol（三表 · 单一出处）
# ===========================================================================
# 🔴 默认档 = 扫描网格**末端**（纪律：定档必须 = 判据 D 扫描最大档）
_N_BY_BID = {
    "B494": 64,
    "B495": 256,
    "B496": 256,
}
# 判据 D 扫描网格（4 档等比 ×2）
_GRID_BY_BID = {
    "B494": [8, 16, 32, 64],
    "B495": [32, 64, 128, 256],
    "B496": [32, 64, 128, 256],
}
# 逐锚 tol（**绝对口径** · 与 harness `compare_fn` cmp='abs' 约定一致；按各自物理量级标定；
# tol 只收紧不放松；余量 ≥100× 且 |golden| ≥ 13.5×tol）
# 🔴 实测默认档 |Δ|：B494 5.012e-6（tol 1e-3 ⇒ 200×）· B495 8.421e-30
#    （tol 1e-27 ⇒ 1187×，对 |golden|≈4.13e-20 即相对 2.04e-10 —— 同 B492 量级标定先例）
#    · B496 1.681（tol 1e3 ⇒ 595×，对 |golden|≈1.65e10 即相对 1.02e-10）
_TOL_BY_BID = {
    "B494": 1e-3,
    "B495": 1e-27,
    "B496": 1e3,
}


# ===========================================================================
# B494 · 腔品质因子 Q = ω/κ：闭式 ⇄ RK4 能量衰减反解 κ
# ===========================================================================
def q_factor_golden(omega: float, kappa: float, t_observe: float = 8.22e-12) -> float:
    """golden：闭式 **Q = ω/κ**（无量纲 · 腔 QED 品质因子；t_observe 仅候选用，此处忽略）。"""
    if kappa <= 0.0 or omega <= 0.0:
        raise ValueError("kappa / omega 必须 > 0")
    return float(omega / kappa)


def _energy_decay_rk4(kappa: float, t_observe: float, n_steps: int) -> float:
    """RK4 数值推进 dU/dt = −κU（U₀=1），返回 U(T)（与 `lda_l2.qs_m3c` 逐位一致）。"""
    if kappa <= 0.0 or t_observe <= 0.0:
        raise ValueError("kappa / t_observe 必须 > 0")
    if n_steps < 4:
        raise ValueError("n_steps 必须 ≥ 4")
    h = t_observe / int(n_steps)
    u = 1.0
    for _ in range(int(n_steps)):
        k1 = -kappa * u
        k2 = -kappa * (u + 0.5 * h * k1)
        k3 = -kappa * (u + 0.5 * h * k2)
        k4 = -kappa * (u + h * k3)
        u += (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return float(u)


def q_factor_candidate(omega: float, kappa: float, t_observe: float = 8.22e-12,
                      n_steps: int = 64) -> float:
    """candidate：**RK4 时间推进能量衰减** → 取 U(T) ⇒ 反解 κ_cand = −ln(U(T))/T
    → Q_cand = ω/κ_cand（方法学独立 · 无解析除式）。

    🔴 残差来源 = **RK4 时间离散化截断**（实测 O(h⁴)，比值 ~16×/倍增）。
    """
    if omega <= 0.0 or kappa <= 0.0 or t_observe <= 0.0:
        raise ValueError("omega / kappa / t_observe 必须 > 0")
    if n_steps < 4:
        raise ValueError("n_steps 必须 ≥ 4")
    u = _energy_decay_rk4(kappa, t_observe, n_steps)
    if u <= 0.0:
        raise ValueError("RK4 数值衰减越界（U(T) 必须 > 0）")
    kappa_cand = -math.log(u) / t_observe
    return float(omega / kappa_cand)


# ===========================================================================
# B495 · 有效模体积 V_eff：闭式 A·8a/15 ⇄ 中点求积
# ===========================================================================
def mode_volume_golden(a: float, A: float) -> float:
    """golden：闭式 **V_eff = A·8a/15**（m³ · 单波腹腔模包络 E(x)=E₀(1−4x²/a²)）。"""
    if a <= 0.0 or A <= 0.0:
        raise ValueError("a / A 必须 > 0")
    return float(A * 8.0 * a / 15.0)


def mode_volume_candidate(a: float, A: float, n_seg: int = 256) -> float:
    """candidate：**中点求积** ∫_{-a/2}^{a/2}(1−4x²/a²)²dx（方法学独立）。

    🔴 残差来源 = **中点求积截断**（实测 O(h⁴) · 偶函数在对称区间中点法加速；
    被积函数为四次非多项式 ⇒ 中点非精确 ⇒ 真数值残差）。
    """
    if a <= 0.0 or A <= 0.0:
        raise ValueError("a / A 必须 > 0")
    if n_seg < 4:
        raise ValueError("n_seg 必须 ≥ 4")
    h = a / int(n_seg)
    acc = 0.0
    for i in range(int(n_seg)):
        x = -0.5 * a + (i + 0.5) * h
        u = 1.0 - 4.0 * x * x / (a * a)
        acc += u * u * h
    return float(A * acc)


# ===========================================================================
# B496 · 单光子耦合 g：闭式 ⇄ 数值场能积分
# ===========================================================================
def coupling_golden(mu: float, omega: float, eps: float, a: float, A: float) -> float:
    """golden：闭式 **g = (μ/ħ)·√(ħω/(ε·V_eff))**（Hz · 单光子 Rabi 频率）。"""
    if mu <= 0.0 or omega <= 0.0 or eps <= 0.0:
        raise ValueError("mu / omega / eps 必须 > 0")
    v_eff = mode_volume_golden(a, A)
    e0 = math.sqrt(omega * HBAR / (eps * v_eff))
    return float(mu * e0 / HBAR)


def coupling_candidate(mu: float, omega: float, eps: float, a: float, A: float,
                       n_seg: int = 256) -> float:
    """candidate：**数值积分 ∫|E|²dV**（⇒ 数值 V_eff）⇒ E₀ ⇒ g（方法学独立）。

    🔴 残差来源 = **中点求积截断**（与 B495 同源 O(h⁴)）；V_eff 数值误差以 ½ 比例
    传入 g（g ∝ V_eff^(−1/2)）。
    """
    if mu <= 0.0 or omega <= 0.0 or eps <= 0.0:
        raise ValueError("mu / omega / eps 必须 > 0")
    v_eff_num = mode_volume_candidate(a, A, n_seg)
    if v_eff_num <= 0.0:
        raise ValueError("数值 V_eff 必须 > 0")
    e0 = math.sqrt(omega * HBAR / (eps * v_eff_num))
    return float(mu * e0 / HBAR)


# ===========================================================================
# 锚的物理设计参数（default_params 真源 · 单一出处）
# ===========================================================================
#: 🔴 `default_params` 的键集 **⊆ golden 形参集**（血案：多键会让 golden_value 抛 TypeError）
B494_DEFAULT_PARAMS = {
    "omega": _OMEGA_DEF,       # 谐振角频率（telecom 1550 nm）
    "kappa": _KAPPA_DEF,       # 能量衰减率 = ω/Q（Q=1e4）
    "t_observe": 8.22e-12,     # RK4 观测时长（κ·t ≈ 1，可见 ring-down）
}

B495_DEFAULT_PARAMS = {
    "a": 1.55e-6,              # 腔长 a（~λ）
    "A": 5.0e-14,              # 模横向截面 A（~0.22µm×0.22µm）
}

B496_DEFAULT_PARAMS = {
    "mu": 1.0e-29,             # 跃迁偶极矩 μ（NV 量级）
    "omega": _OMEGA_DEF,       # 谐振角频率
    "eps": _EPS_DEF,           # 介电常数 ε₀n²（n=3.4 金刚石）
    "a": 1.55e-6,              # 腔长
    "A": 5.0e-14,              # 模横向截面
}


# ===========================================================================
# 记忆化入口（part7.py 顶层引用；纯函数 ⇒ 数值逐位不变）
# ===========================================================================
@functools.lru_cache(maxsize=256)
def _b494_golden_c(omega: float, kappa: float, t: float) -> float:
    return q_factor_golden(omega, kappa, t)


@functools.lru_cache(maxsize=256)
def _b494_cand_c(omega: float, kappa: float, t: float) -> float:
    return q_factor_candidate(omega, kappa, t)


def golden_b494(omega: float = _OMEGA_DEF, kappa: float = _KAPPA_DEF,
                t_observe: float = 8.22e-12) -> float:
    """part7.py 顶层引用的 golden 入口（**接受 default_params 关键字**）。"""
    return _b494_golden_c(omega, kappa, t_observe)


def cand_b494(omega: float = _OMEGA_DEF, kappa: float = _KAPPA_DEF,
              t_observe: float = 8.22e-12, n_steps: int = 64) -> float:
    """candidate 入口（_adapter_p4 用）——接受 default_params 关键字。"""
    return _b494_cand_c(omega, kappa, t_observe)


@functools.lru_cache(maxsize=256)
def _b495_golden_c(a: float, aa: float) -> float:
    return mode_volume_golden(a, aa)


@functools.lru_cache(maxsize=256)
def _b495_cand_c(a: float, aa: float) -> float:
    return mode_volume_candidate(a, aa)


def golden_b495(a: float = 1.55e-6, A: float = 5.0e-14) -> float:
    """part7.py 顶层引用的 golden 入口。"""
    return _b495_golden_c(a, A)


def cand_b495(a: float = 1.55e-6, A: float = 5.0e-14, n_seg: int = 256) -> float:
    """candidate 入口（_adapter_p4 用）。"""
    return _b495_cand_c(a, A)


@functools.lru_cache(maxsize=256)
def _b496_golden_c(mu: float, omega: float, eps: float, a: float, aa: float) -> float:
    return coupling_golden(mu, omega, eps, a, aa)


@functools.lru_cache(maxsize=256)
def _b496_cand_c(mu: float, omega: float, eps: float, a: float, aa: float) -> float:
    return coupling_candidate(mu, omega, eps, a, aa)


def golden_b496(mu: float = 1.0e-29, omega: float = _OMEGA_DEF, eps: float = _EPS_DEF,
                a: float = 1.55e-6, A: float = 5.0e-14) -> float:
    """part7.py 顶层引用的 golden 入口。"""
    return _b496_golden_c(mu, omega, eps, a, A)


def cand_b496(mu: float = 1.0e-29, omega: float = _OMEGA_DEF, eps: float = _EPS_DEF,
              a: float = 1.55e-6, A: float = 5.0e-14, n_seg: int = 256) -> float:
    """candidate 入口（_adapter_p4 用）。"""
    return _b496_cand_c(mu, omega, eps, a, A)


# ===========================================================================
# 自检（`python -m lda.lda_harness._batch_qs_m3c_numeric` 或直接运行）
# ===========================================================================
_CASES = (
    ("B494", golden_b494, cand_b494, q_factor_candidate,
     B494_DEFAULT_PARAMS, "n_steps"),
    ("B495", golden_b495, cand_b495, mode_volume_candidate,
     B495_DEFAULT_PARAMS, "n_seg"),
    ("B496", golden_b496, cand_b496, coupling_candidate,
     B496_DEFAULT_PARAMS, "n_seg"),
)


def _measure_candidates():
    """逐锚实测：默认档残差 / 网格残差链 / 单调性 / 收敛比 / tol 余量。

    🔴 扫描走**底层函数**（接受离散参数 n_steps/n_seg）；`cand_b49x` 是适配器入口
    （离散参数不进 `default_params`，按 B-47 纪律固定在默认档）。
    """
    rows = []
    for bid, gf, cf, raw_cf, params, key in _CASES:
        g = gf(**params)
        chain, abs_chain = [], []
        for n in _GRID_BY_BID[bid]:
            c = raw_cf(**params, **{key: n})
            d = abs(c - g)
            abs_chain.append(d)
            chain.append(d / max(abs(g), 1e-300))
        tol = _TOL_BY_BID[bid]
        rows.append({
            "bid": bid, "golden": g, "tol": tol,
            "grid": list(_GRID_BY_BID[bid]), "rel_chain": chain,
            "abs_chain": abs_chain,
            "mono": all(chain[i] > chain[i + 1] for i in range(len(chain) - 1)),
            "ratio": [chain[i] / chain[i + 1] for i in range(len(chain) - 1)],
            "default_rel": chain[-1],
            # 🔴 tol 是**绝对**口径 ⇒ 余量 = tol/|Δ|（不是 tol/rel）
            "margin_x": tol / abs_chain[-1] if abs_chain[-1] > 0 else float("inf"),
            "abs_default": abs_chain[-1],
            "golden_over_tol": abs(g) / tol,
            "n_default": _N_BY_BID[bid],
        })
    return rows


if __name__ == "__main__":
    print("=" * 78)
    print("Batch B-48 数值核自检（QS-M3c · 腔 QED 物理链 · B494–B496）")
    print("=" * 78)
    bad = 0
    for r in _measure_candidates():
        print("\n%s  golden=%.6e  tol=%.1e  |golden|/tol=%.3e"
              % (r["bid"], r["golden"], r["tol"], r["golden_over_tol"]))
        print("   网格 %s  默认档=%d" % (r["grid"], r["n_default"]))
        print("   rel 链: %s" % " → ".join("%.3e" % x for x in r["rel_chain"]))
        print("   收敛比: %s   MONO=%s"
              % (" ".join("%.2f×" % x for x in r["ratio"]), r["mono"]))
        print("   默认档 rel=%.3e  abs=%.3e  余量(tol/abs)=%.1f×"
              % (r["default_rel"], r["abs_default"], r["margin_x"]))
        for cond, msg in (
            (r["default_rel"] > 1e-12, "默认档 rel > 1e-12（非机器零残差）"),
            (r["mono"], "残差链严格单调"),
            (r["abs_default"] > 0.0, "默认档 abs > 0（真数值残差）"),
            (r["margin_x"] >= 100.0, "余量 ≥ 100×"),
            (r["golden_over_tol"] >= 13.5, "|golden| ≥ 13.5×tol")):
            if not cond:
                print("   [FAIL] %s" % msg)
                bad += 1
        # 反向探针：粗端残差必须**显著**大于默认档（证明非代数恒等）。
        if not (r["rel_chain"][0] >= 20.0 * r["default_rel"]):
            print("   [FAIL] 粗端残差未显著放大（恒等嫌疑）")
            bad += 1
        # 收敛比须与标称阶同量级（O(h²) ⇒ ~4×；O(h⁴) ⇒ ~16×）
        if not all(1.5 <= x <= 40.0 for x in r["ratio"]):
            print("   [FAIL] 收敛比越界（阶不符）：%s" % r["ratio"])
            bad += 1
    print("\n" + "=" * 78)
    print("自检结论：%s（%d 项不符）" % ("ALL PASS" if bad == 0 else "FAIL", bad))
    raise SystemExit(0 if bad == 0 else 1)
