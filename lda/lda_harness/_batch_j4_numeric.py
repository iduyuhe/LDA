# -*- coding: utf-8 -*-
"""Batch J4 数值实现 · 量子传感系统集成征程（J4）M0。

════════════════════════════════════════════════════════════════
本批**一锚**（`benchmark_defs/part7.py` 引用）——

  B515：**多参数 NV 传感的交叉灵敏度解耦解（温度分量 τ̂）**（J4-M0 多参数传感）
        golden    = 4×4 交叉灵敏度矩阵方程的**闭式解析反演**（**Cramer 法则**：
                    行列式按第一行 Laplace 展开 → 3×3 余子式手写展开，
                    温度分量 τ̂ = det(S₁)/det(S)，S₁ = S 的第 1 列被读数向量 b 替换）
                    —— **精确代数式、非迭代、非截断**。
        candidate = **Landweber 迭代解耦**（固定最优步长 τ* = 2/(λ_min+λ_max) 的
                    梯度下降最小二乘：x_{k+1} = x_k + τ*·Sᵀ(b − S·x_k)，k 步 ⇒ τ̂_k）
                    —— 与 golden **方法学独立**（解析闭式求逆 vs 迭代逼近）。

🔴 物理意义（承 J4 蓝图 · `docs/LDA_J4_量子传感系统集成_..._2026-10-14.md` ·
   Layer 4 传感系统 / 缺口 **G-QSYS***）：
  NV 色心的 ODMR 谱特征同时被**四个物理参数**调制 —— ①磁场 B（Zeeman 分裂
  `Δf = 2γ_e B`）②温度 ΔT（零场劈裂温度系数 `dD/dT ≈ −74.2 kHz/K`）③轴向电场 E
  （Stark 位移 `dD/dE_⊥`）④应力 σ（`dD/dσ`）。因此单条谱线的读数
  `b_i = Σ_j S_ij·x_j` 是**四参数的耦合线性组合** ⇒ 「一次读数 = 一个参数」的
  朴素做法会把交叉项误当成本参数变化（**多参数串扰**）。
  解耦 = 求解 `S·x = b` 得各参数真值 ⇒ **多参数传感可用性的物理前提**；
  `τ̂`（温度分量）是其**核心被测量的代表**（温度漂移是多参数 NV 传感最容易被
  磁场串扰污染的一项 —— 见 `qs_m2.temperature_eta`：温度在 QS-M2 里是**噪声源**，
  本锚第一次把它升为**被测量**并给出解耦后的估计）。
  ⇒ 能力层 `lda_l2/qs_j4_multiparam.py` 用同一物理链（物理系数 → 无量纲响应矩阵 →
  解耦 → 条件数）实现，本锚为其账本判据源头。

🔴 建模口径（**归一化**，可复算）：
  令 g_j = 参数 j 的特征灵敏度标度（g = [γ_e, |dD/dT|, |dD/dE|, |dD/dσ|]），
  归一化参数 x_j ≥ g_j·(物理量 j) ⇒ 读数方程**无量纲化**为 `b = C·x`，
  C 即本批的**无量纲交叉响应矩阵**（对角 = 各谱特征对自身主参数的响应、
  非对角 = 交叉响应）· b = 归一化读数向量。二者均为**设计示例常量**。

🔴 与既有锚的边界（**同源体检 · 实 grep 全仓核验**，本档第一道闸）：
  · 实 grep（`benchmark_defs/`）：`解耦|decoupl` **0 命中**；`多参数|multi_param|
    multiparam` **0 命中**；`交叉灵敏度|cross_sensitivity|sensitivity_matrix` **0 命中**；
    `cramer|伴随矩阵|adjugate` **0 命中**；`landweber|梯度下降|gradient_descent` **0 命中**；
    `条件数|condition_number` **0 命中** ⇒ **多参数解耦族零锚占用（本族首锚）**。
  · 与 **B473**（NV 单参数磁力计**散粒极限灵敏度** η = ħ/(gμB)·√(1+a²)·√2/(C√(n_ph·T2*))，
    T/√Hz）**三方分歧**：①**被测标量**：**归一化解耦解 τ̂**（四参数联立反演的一个分量，
    **无量纲**）vs **灵敏度谱密度 η**（T/√Hz，单参数标量）②**物理构型**：**四场耦合的
    观测方程组（交叉灵敏度矩阵 + 读数向量）** vs **单场 Ramsey 自由进动 + 误差传播**；
    ③**数值格式**：**Cramer 解析求逆 ⇄ Landweber 迭代解耦** vs **闭式代数 ⇄ 复指数演化核
    数值差商** ⇒ 计新锚（承 B452↔B33 先例）。
  · 与 **B478/B479**（QS-M4 **阵列**串扰：磁偶极近场串扰系数 X / 灵敏度恶化倍率
    √(1+X_tot²)）三方分歧：①被测标量：**解耦反演解 τ̂** vs **串扰系数/恶化倍率**；
    ②构型：**单一 NV 内的四场参数耦合**（横跨参数空间）vs **相邻 NV 柱的空间磁偶极耦合**
    （横跨空间）；③数值格式：**Cramer/迭代线性反演** vs **点偶极场数值积分 / MC 噪声功率叠加**
    ⇒ 计新锚（J4 章程 §1.2 已预设「集成串扰」改靶，本锚**不碰空间串扰族**）。
  · 与 **B476/B477**（几何：最优深度 / NA 收集效率）、**B482–B484**（标定/动态范围）
    在被测标量上均不同 ⇒ 非重复计数。

🔴 判据 D（默认档必须落在**离散误差主导区**，且默认档 = 扫描格末端）
  实测扫描（2026-10-14 现算 · coupling=1.0 ⇒ κ(S)=5.9586 · τ*=1.589079）：
      k= 64 → 1.2170e-02     k=128 → 3.3125e-04     k=192 → 8.9958e-06
      k=256 → 2.4429e-07    **k=320 → 6.6341e-09 ← 默认档**
    比值 **36.74 / 36.82 / 36.82 / 36.82×**（扫描格等差 Δk=64 ⇒ 比值恒定
    = ρ^{−64}，ρ = (κ²−1)/(κ²+1) = 0.94521 ⇒ **几何收敛**，与 Landweber 标称收敛率一致）；
    动态范围 1.83e6×；余量 **150.7×**（tol=1e-6）；|golden|/tol = 6.5e5。
  ⇒ tol 绝对口径按量级标定：B515 tol=1e-6（归一化无量纲量，O(1) 量级）。
  🔴 稳定性/口径边界（实测）：
    · Landweber 固定步长须满足 0 < τ* < 2/λ_max（本档取**最大收敛速度**的
      τ* = 2/(λ_min+λ_max) ⇒ 谱半径 ρ=(λ_max−λ_min)/(λ_max+λ_min) < 1 恒收敛）；
    · κ 越大收敛越慢 ⇒ 本档 κ≈5.96 使「默认档残差 ∈[1e-10,1e-8] ∧ 动态范围 ≥1e4」
      同时成立（κ≲3.6 时收敛过快、k=64 即沉机器地板 ⇒ 不可锚；
      实测对角抬高族 κ=1.58/2.06 档链恒 1.11e-16）；命名避让：批次
      `_batch_j4_numeric` / `_get_j4_numeric`（实 grep 零占用）；候选 key 前缀
      `b515_` 未占用。磁盘 `_adapter_p*.py` **不新建**（L9 守卫：恒 6 片）。

🔴 纪律：
· golden 与 candidate 是**两种结构不同的算法**（解析行列式展开 vs 迭代逼近）；
  进报告数字一律**现算**。
· 零 RNG（确定性格点 + 确定性迭代）。
· 诚实边界：C/b/coupling 为**设计示例量级**（归一化无量纲响应矩阵，非实测 PDK /
  非流片标定）；本锚只证「闭式解析反演 ⇄ 迭代解耦」数值一致这一数学事实 +
  多参数解耦物理链自洽，**不作制造/性能宣称**，不报能效/TOPS/fJ-op。
  零商业依赖（纯 numpy + math）。
"""
from __future__ import annotations

import functools
import math

import numpy as np

# ── 三表（判据 D 扫描格 / 默认档 = 格末端 / tol 绝对口径按量级标定）─────────────
_M_BY_BID = {"B515": 320, "B518": 512}
_GRID_BY_BID = {"B515": [64, 128, 192, 256, 320], "B518": [32, 64, 128, 256, 512]}
_TOL_BY_BID = {"B515": 1e-6, "B518": 1e-8}

#: 默认物理参数（只放 golden 接受的键；离散参数 k/n 由候选签名默认值承载）
#: coupling = 交叉耦合强度缩放（S(c) = diag(S₀) + c·(S₀ − diag(S₀))；c=1 为设计示例）
_B515_DEFAULT = {"coupling": 1.0}
#: B518 低温布线束：铜残差电阻率 ρ₀（Ω·m）与电子–声子斜率 β（Ω·m/K）
_B518_DEFAULT = {"rho0_ohm_m": 1.0e-10, "beta_ohm_m_per_K": 5.6e-11}


# ── 物理模型常量（设计示例量级 · 归一化前的物理链见能力层 qs_j4_multiparam.py）──
#: 归一化交叉灵敏度矩阵 C（4 条 ODMR 谱特征 × 4 参数 [B, ΔT, E, σ]）
#: 对角 = 各谱特征对自身主参数的响应；非对角 = 交叉响应（无量纲，O(1)）
_C_MP = np.array([[1.00, 0.25, 0.10, 0.04],
                  [0.15, 0.60, 0.08, 0.03],
                  [0.06, 0.14, 0.30, 0.05],
                  [0.04, 0.08, 0.03, 0.20]], dtype=float)

#: 归一化读数向量 b（4 条谱特征的读数偏移，设计示例）
_B_MP = np.array([1.00, 0.55, 0.28, 0.17], dtype=float)

#: NV 物理系数（设计示例量级；归一化后被约掉，此处保留供能力层构造物理矩阵）
GAMMA_E_HZ_PER_UT = 28.024e6      # Hz/µT（NV 电子自旋旋磁比 γ_e = gμB/h）
DD_DT_HZ_PER_K = -74.2e3          # Hz/K（零场劈裂温度系数 dD/dT）
DD_DE_HZ_PER_KV_CM = 17.0e3       # Hz/(kV/cm)（轴向 Stark 系数 dD/dE_⊥）
DD_DSIGMA_HZ_PER_MPA = 1.4e3      # Hz/MPa（应力系数 dD/dσ，= 1.4 MHz/GPa）


def _resp_matrix(coupling: float = 1.0) -> "np.ndarray":
    """交叉响应矩阵 S(c) = diag(C) + c·(C − diag(C))（c=0 ⇒ 纯对角，c=1 ⇒ 设计示例）。"""
    d = np.diag(np.diag(_C_MP))
    return d + float(coupling) * (_C_MP - d)


def _det3(m) -> float:
    """3×3 行列式（手写展开，闭式）。"""
    return float(m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
                 - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                 + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def _det4(M) -> float:
    """4×4 行列式（按第一行 Laplace 展开 → 3×3 余子式，闭式）。"""
    d = 0.0
    for j in range(4):
        minor = [[float(M[r][c]) for c in range(4) if c != j] for r in range(1, 4)]
        d += ((-1.0) ** j) * float(M[0][j]) * _det3(minor)
    return float(d)


def multiparam_decouple_golden(coupling: float = 1.0) -> float:
    """B515 golden：多参数交叉灵敏度方程 S·x = b 的**闭式解析反演**（Cramer 法则）。

    返回**温度分量** τ̂ = x[1] = det(S₁)/det(S)，S₁ = S 的第 1 列被读数向量 b 替换。
    —— 4×4 行列式按第一行 Laplace 展开、3×3 余子式手写展开 ⇒ **精确代数式**
    （无迭代、无截断、无近似）。c=0 ⇒ 退化为纯对角解 b[1]/S[1][1]。
    """
    S = _resp_matrix(coupling)
    S1 = S.copy()
    S1[:, 1] = _B_MP
    return float(_det4(S1) / _det4(S))


def multiparam_decouple_candidate(coupling: float = 1.0,
                                  n: int = _M_BY_BID["B515"]) -> float:
    """B515 candidate：**Landweber 迭代解耦**（梯度下降最小二乘，与 golden 方法学独立）。

    迭代 x_{k+1} = x_k + τ*·Sᵀ(b − S·x_k)，x₀ = 0；
    步长取**最大收敛速度** τ* = 2/(λ_min + λ_max)（λ 为 SᵀS 的特征值，np.linalg.eigvalsh
    精确对称特征分解）⇒ 谱半径 ρ = (λ_max−λ_min)/(λ_max+λ_min) < 1 恒收敛。
    返回 n 步后的温度分量 τ̂_n。残差 = 迭代截断误差（几何收敛 ρ^n）。
    """
    n = int(n)
    if n < 1:
        raise ValueError("迭代步数 n 须 ≥ 1")
    S = _resp_matrix(coupling)
    ev = np.linalg.eigvalsh(S.T @ S)
    lam_min, lam_max = float(ev[0]), float(ev[-1])
    tau = 2.0 / (lam_min + lam_max)
    x = np.zeros(4, dtype=float)
    for _ in range(n):
        x = x + tau * (S.T @ (_B_MP - S @ x))
    return float(x[1])


# ══════════════════════════════════════════════════════════════════════
# B518 · 低温布线束热负载（Wiedemann–Franz 电子热导 · 有理闭式 ⇄ RK4 积分定义 ODE）
# ══════════════════════════════════════════════════════════════════════
#: Lorenz 数 L₀ = π²k_B²/(3e²)（W·Ω/K²）
_LORENZ_NUMBER = 2.44e-8
#: 铜电阻率的**杂质散射残差项** ρ₀（Ω·m；低温主导）与**电子–声子线性斜率** β（Ω·m/K）
_CU_RESIDUAL_RHO = 1.0e-10
_CU_BETA = 5.6e-11
#: 线束有效传导截面 / 长度 / 两端温度（设计示例：单根 0.1 mm² 铜线跨 300 K→4 K）
_WIRE_AREA_M2 = 1.0e-7
_WIRE_LENGTH_M = 0.5
_T_HOT_K = 300.0
_T_COLD_K = 4.0


def _rho_copper(T: float, rho0: float, beta: float) -> float:
    """铜电阻率简化两区模型 ρ(T) = ρ₀ + β·T（低温残差 + 电子–声子线性项）。"""
    return float(rho0) + float(beta) * float(T)


def _k_electronic(T: float, rho0: float, beta: float) -> float:
    """Wiedemann–Franz 电子热导 k_el(T) = L₀·T/ρ(T)（**有理非线性** —— 非恒等来源）。"""
    return _LORENZ_NUMBER * float(T) / _rho_copper(T, rho0, beta)


def cryo_wiring_heat_golden(rho0_ohm_m: float = _CU_RESIDUAL_RHO,
                            beta_ohm_m_per_K: float = _CU_BETA) -> float:
    """B518 golden：低温布线束的 Wiedemann–Franz 电子热负载（**精确闭式**）。

        Q = (A/L)·∫_{T_c}^{T_h} L₀·T/(ρ₀+βT) dT
          = (A/L)·L₀/β² · { [(ρ₀+βT) − ρ₀·ln(ρ₀+βT)] }_{T_c}^{T_h}    [W]

    推导：无源稳态一维传导 ⇒ Q = (A/L)·∫k(T)dT（沿线温度积分）；Wiedemann–Franz
    k_el(T)=L₀T/ρ(T)，ρ(T)=ρ₀+βT（两区简化电阻率）⇒ 令 u=ρ₀+βT 得
    ∫T/(ρ₀+βT)dT = (1/β²)·[u − ρ₀·ln u] ⇒ **初等闭式（精确解析结果，非截断近似）**。
    β→0 退化纯 WF 极限 Q=(A/L)L₀(T_h²−T_c²)/(2ρ₀)。
    """
    rho0, beta = float(rho0_ohm_m), float(beta_ohm_m_per_K)
    if rho0 <= 0.0 or beta < 0.0:
        raise ValueError("须 ρ₀ > 0 且 β ≥ 0")
    if beta == 0.0:
        return (_WIRE_AREA_M2 / _WIRE_LENGTH_M) * _LORENZ_NUMBER \
            * (_T_HOT_K ** 2 - _T_COLD_K ** 2) / (2.0 * rho0)

    def _anti(T):
        u = rho0 + beta * T
        return (u - rho0 * math.log(u)) / (beta * beta)

    return (_WIRE_AREA_M2 / _WIRE_LENGTH_M) * _LORENZ_NUMBER \
        * (_anti(_T_HOT_K) - _anti(_T_COLD_K))


def cryo_wiring_heat_candidate(rho0_ohm_m: float = _CU_RESIDUAL_RHO,
                               beta_ohm_m_per_K: float = _CU_BETA,
                               n: int = _M_BY_BID["B518"]) -> float:
    """B518 candidate：**RK4 积分定义 ODE** dQ/dT = (A/L)·k_el(T)（与 golden 方法学独立）。

    把「沿线温度积分」写成以 T 为自变量的初值问题：
        dQ/dT = (A/L)·L₀·T/(ρ₀+βT),   Q(T_c) = 0
    从 T_c 到 T_h 做 n 步四阶 RK4 ⇒ Q(T_h)。残差 = RK4 截断误差（O(h⁴)）——
    🔴 被积函数为**有理非线性**（β>0），故 RK4 **不**精确 ⇒ 真离散化误差（β=0 的线性
    极限下 RK4 对该多项式精确 ⇒ 判据 D 不成立，故默认 β>0）。
    """
    n = int(n)
    if n < 1:
        raise ValueError("步数 n 须 ≥ 1")
    rho0, beta = float(rho0_ohm_m), float(beta_ohm_m_per_K)
    if rho0 <= 0.0 or beta < 0.0:
        raise ValueError("须 ρ₀ > 0 且 β ≥ 0")
    scale = _WIRE_AREA_M2 / _WIRE_LENGTH_M
    h = (_T_HOT_K - _T_COLD_K) / n
    q = 0.0
    t = _T_COLD_K

    def _f(tt):
        return scale * _k_electronic(tt, rho0, beta)

    for _ in range(n):
        k1 = _f(t)
        k2 = _f(t + 0.5 * h)
        k3 = _f(t + 0.5 * h)
        k4 = _f(t + h)
        q = q + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        t = t + h
    return float(q)


# ── 统一入口（harness / golden.py 按名调用）────────────────────────────────
def golden_b515(coupling: float = 1.0) -> float:
    return multiparam_decouple_golden(coupling)


def cand_b515(coupling: float = 1.0, n: int = _M_BY_BID["B515"]) -> float:
    return multiparam_decouple_candidate(coupling, n)


def golden_b518(rho0_ohm_m: float = _CU_RESIDUAL_RHO,
                beta_ohm_m_per_K: float = _CU_BETA) -> float:
    return cryo_wiring_heat_golden(rho0_ohm_m, beta_ohm_m_per_K)


def cand_b518(rho0_ohm_m: float = _CU_RESIDUAL_RHO,
              beta_ohm_m_per_K: float = _CU_BETA,
              n: int = _M_BY_BID["B518"]) -> float:
    return cryo_wiring_heat_candidate(rho0_ohm_m, beta_ohm_m_per_K, n)


@functools.lru_cache(maxsize=None)
def _g515_c(coupling: float) -> float:
    return golden_b515(coupling)


@functools.lru_cache(maxsize=None)
def _c515_c(coupling: float, k: int) -> float:
    return cand_b515(coupling, k)


B515_DEFAULT_PARAMS = dict(_B515_DEFAULT)
B518_DEFAULT_PARAMS = dict(_B518_DEFAULT)


#: 自检用例：bid, 物理参数（golden 键）
_CASES = (("B515", _B515_DEFAULT), ("B518", _B518_DEFAULT))

_GOLDEN_BY_BID = {"B515": golden_b515, "B518": golden_b518}
_CAND_BY_BID = {"B515": cand_b515, "B518": cand_b518}


def _measure_candidates():
    """现算：默认档 golden/cand/残差 + 判据 D 扫描链（粗→细）。"""
    out = {}
    for bid, params in _CASES:
        tol = _TOL_BY_BID[bid]
        grid = _GRID_BY_BID[bid]
        gold = _GOLDEN_BY_BID[bid](**params)
        chain = []
        for n in grid:
            chain.append((n, abs(_CAND_BY_BID[bid](n=n, **params) - gold)))
        resid = [r for _, r in chain]
        d_res = abs(_CAND_BY_BID[bid](n=_M_BY_BID[bid], **params) - gold)
        ratios = [resid[i] / resid[i + 1] for i in range(len(resid) - 1)
                  if resid[i + 1] > 0]
        out[bid] = {
            "golden": gold, "default_n": _M_BY_BID[bid], "tol": tol,
            "chain": chain, "resid": resid, "default_resid": d_res,
            "mono": all(resid[i] > resid[i + 1] for i in range(len(resid) - 1)),
            "ratios": ratios,
            "margin": tol / d_res if d_res > 0 else float("inf"),
            "gold_over_tol": abs(gold) / tol,
        }
    return out


if __name__ == "__main__":  # pragma: no cover —— 逐锚自检（判据 D 可标定 + 非代数恒等）
    print("=" * 72)
    print("Batch J4 数值核自检（B515 · 量子传感系统集成征程 M0 多参数解耦）")
    print("=" * 72)
    bad = 0
    for bid, m in _measure_candidates().items():
        print("\n[%s] golden=%.12e  tol=%.1e  默认 n=%d" % (bid, m["golden"], m["tol"],
                                                          m["default_n"]))
        print("  判据 D 残差链：" +
              "  ".join("k=%d→%.3e" % (n, r) for n, r in m["chain"]))
        print("  实测比值：  " + "  ".join("%.2f×" % x for x in m["ratios"]))
        print("  默认档残差=%.3e  余量=%.1f×  |golden|/tol=%.3e  MONO=%s"
              % (m["default_resid"], m["margin"], m["gold_over_tol"], m["mono"]))
        for name, cond in (
            ("默认档残差 > 1e-12（排除代数恒等）", m["default_resid"] > 1e-12),
            ("默认档残差 < tol", m["default_resid"] < m["tol"]),
            ("余量 ≥ 100×", m["margin"] >= 100.0),
            ("|golden|/tol ≥ 13.5", m["gold_over_tol"] >= 13.5),
            ("判据 D 严格单调（粗→细）", m["mono"]),
            ("粗端残差浮出地板（>1e-12）", m["resid"][0] > 1e-12),
            ("残差动态范围 ≥ 1e4×（排除「残差与离散参数无关」指纹）",
             m["resid"][0] / m["default_resid"] >= 1e4),
            ("每档比值 > 1（真下降）", all(x > 1.0 for x in m["ratios"])),
            # B515 = 几何收敛 + 等差扫描格 ⇒ 比值**恒定**；
            # B518 = RK4 的 O(h⁴) ⇒ 比值**趋向 16**（粗端未入渐近区偏低、单调增）
            ("比值形态与算法标称阶一致（B515 恒定 / B518 趋向 16）",
             (max(m["ratios"]) / min(m["ratios"]) < 1.05) if bid == "B515"
             else (4.0 <= m["ratios"][-1] <= 20.0 and m["ratios"][-1] > m["ratios"][0])),
        ):
            ok = bool(cond)
            bad += 0 if ok else 1
            print("    [%s] %s" % ("PASS" if ok else "FAIL", name))
    print("\n" + ("ALL PASS" if bad == 0 else "%d FAIL" % bad))
    raise SystemExit(0 if bad == 0 else 1)
