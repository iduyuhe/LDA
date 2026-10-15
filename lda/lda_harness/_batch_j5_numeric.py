# -*- coding: utf-8 -*-
"""Batch J5 量子网络与接口征程 · **M0** 数值核：**B519 分发后两体纠缠保真度**。

── 物理与锚形 ──────────────────────────────────────────────────────────────
J1–J4 全部建模「芯片内 / 实验室距离」；本条**第一次引入公里级距离**维度（章程 §3.1）。

  · 初始态：Bell 态 `|Φ+⟩=(|00⟩+|11⟩)/√2`（Werner 参数 p=1）。
  · 信道：光纤传输 + **偏振去相干**（退极化信道）⇒ 态进入 **Werner 族**
    `ρ(L) = p(L)·|Φ+⟩⟨Φ+| + (1−p(L))·I/4`，`p(L)=exp(−L/L_depol)`。
  · 读数：分发后**两体纠缠保真度** `F = Tr(ρ(L)·|Φ+⟩⟨Φ+|) = (1+3p(L))/4`。

**golden（闭式物理律 · 严格解析）**：`F(L)=(1+3·exp(−L/L_depol))/4`（Werner 族教科书闭式）。
**candidate（方法学独立）**：`dρ/dL = −(ρ − I/4)/L_depol` 的 **4×4 密度矩阵 RK4 距离步进**
（16 实分量全演化，末端读 `Tr(ρ·ρ_ideal)`）—— **静态算子代数 → 距离步进时间推进**。

── 同源体检（2026-10-15 实 grep `lda_harness/benchmark_defs/` · 如实登记）────────────
  · `werner` = **0 命中**；`entangl|bell|EPR|concurrence|CHSH|teleport` 在锚定义内 **0 命中**
    （唯一近邻 `part1.py:221`「EPR 哈密顿量对角化(pyEPR/Ansys)仅作外部 ORACLE」为**文本非锚**）。
  · 🔴 **`kraus` 已被 B453 占用**（`coherent_loss_fidelity` · 相干态经损耗通道 ·
    **静态 Fock 截断 Kraus 算子求和**）⇒ 本条候选**刻意避开 Kraus 求和**，改「距离步进 Liouvillian」。
  · `fiber` 命中为 **阶跃光纤 LP01 模式折射率**锚（part5 `fiber_lp01_neff_fd`）⇒ **模式求解**，
    与「信道损耗/保真度」**物理量不同**。

── 三方分歧（与既有保真度族）────────────────────────────────────────────────
  | 对 | ① 被测标量 | ② 物理构型 | ③ 数值格式 |
  |---|---|---|---|
  | **B453**（相干态损耗保真度） | **两体纠缠态**保真度（Werner · 含纠缠语义） | **含公里级信道传输**（距离 L 为自变量） | **距离步进 RK4 超算子**（vs 静态 Fock 截断 Kraus 求和） |
  | **B10**（单比特门保真度·退相干极限） | 两体纠缠态保真度 | 信道传输（vs 二能级 T1/T2 双通道） | RK4 距离步进（vs 4×4 PTM 时间步进） |
  | **B502/B503**（QEC 门/合并保真度） | 连续变量/纠缠态保真度 | 光纤信道（vs 表面码操作） | RK4 距离步进（vs 组合/数值链） |
  ⇒ **非重复计数**（先例：B452↔B33、B448/B449）。

── 后续档（同文件续登 · 本文件 = J5 征程数值核）──────────────────────────────
**M1 · B520 光子不可分辨性 → HOM 干涉可见度 V(δt,δω)**：`V=exp(−δt²/(4σ²))·exp(−δω²σ²)`
（高斯重叠闭式 · 见下方 §B520）⇄ **复值被积函数复合梯形时间域积分**。
**M2 · B521 中继站期望交换产出数 N_swap**（生成窗 ⊗ **存储窗** 嵌套卷积）：
闭式 `κλ/(γ−λ)·[(1−e^{−λT})/λ − (1−e^{−γT})/γ]` ⇄ **单重复合 Simpson 求积**（见下方 §B521）。

**M2 同源体检（2026-10-15 实 grep `lda_harness/benchmark_defs/` · 如实登记）**：
  · `中继|repeater|relay|swapping|交换|exchange` ⇒ **4 处命中全为其它锚 note 中的普通用词**
    （B491 数密度 / B506 CR 门 / B507 ZZ / B520 HOM）⇒ **中继族零锚占用**（本族首锚）。
  · `吞吐|throughput|产出|rate_equation` ⇒ **0 命中**；`T_mem|存储时间|存储窗` 仅 1 处（B519 note 用词）
    ⇒ **存储时间维度零占用**。
  · ⚠️ **B19 `passivity`（无源链路 · 判 max|T|≤1）** 与「增益」**语义相反** ⇒ note 首行已显式声明
    物理地位不同（本条 = 产出**计数**，既非传递矩阵、亦非增益比值）。
  · ⚠️ `增益|gain` 另有 **B482**（频锁鉴别器**斜率**，被称「锁定增益」）· **B467/B488**（跨阻/磁通聚焦）
    ⇒ 物理量均不同。
  · ⚠️ **矩阵指数族 B221/B222**（`状态转移矩阵 exp(At)[0,1]=−sin t` · 候选 = scaling–squaring +
    Taylor 截断）与 B521 的 golden「生成元指数」**结构邻接** ⇒ 三方分歧见下。

**M2 三方分歧（B521 与近邻）**：
  | 对 | ① 被测标量 | ② 物理构型 | ③ 数值格式 |
  |---|---|---|---|
  | **B221/B222**（矩阵指数族） | **期望交换产出计数**（κ 加权的累积 ∫P₁dt） | 三态**吸收型** Markov 生成-存储-交换竞争（三时间尺度） | **单重复合 Simpson 求积**（vs scaling–squaring + Taylor 截断） |
  | **B19**（无源链路 passivity） | 产出计数（非 0/1 判决） | 中继站动力学（vs 被动网络传递矩阵） | Simpson 求积（vs 解析 |T|≤1 判据） |
  | **B519**（J5 M0 分发保真度） | 产出**计数** | 中继站三态竞争（vs 距离步进退极化信道） | 求积（vs 距离步进 RK4） |
  | **B512/B519 等 RK4 族** | 同左 | 同左 | **本锚候选不含 ODE 步进**（纯求积）⇒ 与 RK4 簇格式分歧 |
  ⇒ **非重复计数**（先例：B452↔B33、B448/B449）。

── 判据 D（真离散误差）────────────────────────────────────────────────────
实测残差链 n=16→2.4914e-06 · 32→1.3823e-07 · 64→8.1415e-09 · 128→4.9399e-10 · 256→3.0420e-11
（比值 18.02/16.98/16.48/16.24 ⇒ **趋向 16 = O(h⁴)**；动态范围 1.32e6×）。
⇒ 粗端浮出双精度地板、严格单调、与 RK4 标称阶一致 ⇒ **真独立，非代数恒等**。

🔴 **诚实边界**：`L=100 km` / `L_depol=22 km` / `α=0.2 dB/km` 均为**公开典型值 / 设计示例**，
非任何实测链路；本锚只支撑预算与量级，**不作性能宣称**。残差 = RK4 截断误差。零商业依赖
（纯 `math` + `numpy`；零 RNG）。
"""

from __future__ import annotations

import math

import numpy as np

# ── 常量（设计示例 · 见诚实边界）──────────────────────────────────────────
#: 链路长度（m · 100 km）
_LINK_LENGTH_M = 1.0e5
#: 偏振去相干长度（m · 设计示例，与光纤 L_att 同量级）
_DEFAULT_L_DEPOL_M = 2.2e4

#: 完全混态 I/4 与理想 Bell 态 |Φ+⟩⟨Φ+|（4×4）
_I4 = np.eye(4, dtype=float) / 4.0
_PHI = np.zeros((4, 4), dtype=float)
_PHI[0, 0] = _PHI[3, 3] = 0.5
_PHI[0, 3] = _PHI[3, 0] = 0.5

# ── 三表（判据 D 扫描格 / 默认档 = 格末端 / tol 绝对口径按量级标定）───────────
_M_BY_BID = {"B519": 256, "B520": 28, "B521": 256}
_GRID_BY_BID = {"B519": [16, 32, 64, 128, 256], "B520": [8, 12, 16, 20, 24, 28],
                "B521": [8, 16, 32, 64, 128, 256]}
_TOL_BY_BID = {"B519": 1e-8, "B520": 3e-9, "B521": 1e-7}

#: 默认物理参数（只放 golden 接受的键；离散参数 n 由候选签名默认值承载）
_B519_DEFAULT = {"l_depol_m": 2.2e4}


def _werner_rho(p: float) -> np.ndarray:
    """Werner 族密度矩阵 `ρ = p|Φ+⟩⟨Φ+| + (1−p)I/4`。"""
    return p * _PHI + (1.0 - p) * _I4


def _rhs(rho: np.ndarray, l_depol_m: float) -> np.ndarray:
    """退极化信道 Liouvillian（距离域）：`dρ/dL = −(ρ − I/4)/L_depol`。"""
    return -(rho - _I4) / l_depol_m


def distribution_fidelity_golden(l_depol_m: float = _DEFAULT_L_DEPOL_M) -> float:
    """B519 golden：Werner 族**分发后保真度**（**严格解析闭式**）。

        F(L) = (1 + 3·p(L)) / 4 ,   p(L) = exp(−L/L_depol)

    推导：退极化信道把 `ρ₀=|Φ+⟩⟨Φ+|` 映为 `ρ(L)=p|Φ+⟩⟨Φ+|+(1−p)I/4`；对理想态取重叠
    `Tr(ρ·ρ₀) = p + (1−p)/4 = (1+3p)/4`。**非迭代、非截断**。
    """
    l_depol_m = float(l_depol_m)
    if l_depol_m <= 0.0:
        raise ValueError("去相干长度 L_depol 须 > 0")
    p = math.exp(-_LINK_LENGTH_M / l_depol_m)
    return (1.0 + 3.0 * p) / 4.0


def distribution_fidelity_candidate(l_depol_m: float = _DEFAULT_L_DEPOL_M,
                                   n: int = _M_BY_BID["B519"]) -> float:
    """B519 candidate：**4×4 密度矩阵沿距离的 RK4 步进**（与 golden 方法学独立）。

    把信道写成距离域初值问题 `dρ/dL = −(ρ−I/4)/L_depol`，`ρ(0)=|Φ+⟩⟨Φ+|`，
    自 L=0 推进到 L=100 km（n 步四阶 RK4，**16 个实分量全演化**），末端读
    `F = Tr(ρ(L)·|Φ+⟩⟨Φ+|)`。残差 = RK4 截断误差（O(h⁴)，实测比值趋向 16）。

    🔴 与 B453 的数值格式分歧点：本条是**距离步进时间推进**（离散参数 = 步数 n），
    B453 是**静态算子代数**（离散参数 = Fock 截断维数）。
    """
    n = int(n)
    if n < 1:
        raise ValueError("步数 n 须 ≥ 1")
    l_depol_m = float(l_depol_m)
    if l_depol_m <= 0.0:
        raise ValueError("去相干长度 L_depol 须 > 0")
    h = _LINK_LENGTH_M / n
    rho = _werner_rho(1.0)
    for _ in range(n):
        k1 = _rhs(rho, l_depol_m)
        k2 = _rhs(rho + 0.5 * h * k1, l_depol_m)
        k3 = _rhs(rho + 0.5 * h * k2, l_depol_m)
        k4 = _rhs(rho + h * k3, l_depol_m)
        rho = rho + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return float(np.trace(rho @ _PHI).real)


# ══════════════════════════════════════════════════════════════════════
# B520 · 光子不可分辨性 → HOM 干涉可见度 V（高斯波包重叠闭式 ⇄ 复合梯形数值积分）
# ══════════════════════════════════════════════════════════════════════
#: 波包宽度 σ（s · 设计示例 1 ps）
_PACKET_SIGMA = 1.0e-12
#: 时间延迟 δt（取 2σ）
_PACKET_DELAY = 2.0 * _PACKET_SIGMA
#: 频率差 δω（取 1/σ ⇒ 被积函数含振荡因子，令求积误差可标定）
_PACKET_DW = 1.0 / _PACKET_SIGMA
#: 积分半域（10σ）
_INT_HALF = 10.0 * _PACKET_SIGMA

_B520_DEFAULT = {
    "packet_sigma_s": 1.0e-12,
    "delay_s": 2.0e-12,
    "dw_rad_s": 1.0e12,
}


def hom_visibility_golden(packet_sigma_s: float = _PACKET_SIGMA,
                          delay_s: float = _PACKET_DELAY,
                          dw_rad_s: float = _PACKET_DW) -> float:
    """B520 golden：两高斯波包重叠幅度的**解析闭式**（高斯积分精确求值）。

        ψ_i(t) ∝ (2πσ_i²)^{−1/4}·exp(−(t−t_i)²/(4σ_i²))·exp(−iω_i t)
        M = ∫ψ₁*(t)ψ₂(t)dt  ⇒  |M|² =
            [2σ₁σ₂/(σ₁²+σ₂²)]·exp(−δt²/(2(σ₁²+σ₂²)))·exp(−2δω²σ₁²σ₂²/(σ₁²+σ₂²))

    推导：配方后两次用 ∫exp(−a x²+b x)dx=√(π/a)·exp(b²/4a)（**精确闭式，非截断**）。
    HOM 可见度 V = |M|²（两光子波包不可分辨性 ⇒ HOM dip 深度）。
    """
    s = float(packet_sigma_s)
    if s <= 0.0:
        raise ValueError("波包宽度 σ 须 > 0")
    s2sum = 2.0 * s * s                      # σ₁²+σ₂²（σ₁=σ₂=σ）
    return ((2.0 * s * s / s2sum)
            * math.exp(-float(delay_s) ** 2 / (2.0 * s2sum))
            * math.exp(-2.0 * float(dw_rad_s) ** 2 * s ** 4 / s2sum))


def hom_visibility_candidate(packet_sigma_s: float = _PACKET_SIGMA,
                             delay_s: float = _PACKET_DELAY,
                             dw_rad_s: float = _PACKET_DW,
                             n: int = _M_BY_BID["B520"]) -> float:
    """B520 candidate：**复合梯形法**时间域数值积分 `∫ψ₁*(t)ψ₂(t)dt` ⇒ |M|²。

    🔴 为何**不用 Simpson**：被积函数含振荡因子 exp(iδωt) ⇒ Simpson 在粗端**非单调**
    （实测 n=8→10 残差反升），判据 D 不成立；**复合梯形 O(h²)** 给出严格单调残差链。
    🔴 本问题为**超几何收敛**（高斯×振荡被积函数的解析性所致，非幂律）⇒ 比值单调递增，
    如实登记不假称「恰 4」。
    """
    n = int(n)
    if n < 2:
        raise ValueError("步数 n 须 ≥ 2")
    s = float(packet_sigma_s)
    if s <= 0.0:
        raise ValueError("波包宽度 σ 须 > 0")
    dt_lag = float(delay_s)
    dw = float(dw_rad_s)
    a = -_INT_HALF
    b = dt_lag + _INT_HALF
    t = np.linspace(a, b, n + 1)
    h = (b - a) / n
    norm = (2.0 * math.pi * s * s) ** (-0.5)
    psi1 = np.exp(-(t ** 2) / (4.0 * s * s))
    psi2 = np.exp(-((t - dt_lag) ** 2) / (4.0 * s * s)) * np.exp(-1j * dw * t)
    f = norm * np.conj(psi1) * psi2
    w = np.ones(n + 1)
    w[0] = w[-1] = 0.5
    # 🔴 必须保持**复数**（`float()` 作用于复数组会静默丢弃虚部 ⇒ 结果错）
    M = h * np.sum(w * f)
    return float(abs(M) ** 2)


# ══════════════════════════════════════════════════════════════════════
# B521 · 中继站期望交换产出数 N_swap（生成窗 ⊗ 存储窗 嵌套卷积闭式 ⇄ 复合 Simpson 求积）
# ══════════════════════════════════════════════════════════════════════
#: 🔴 **与 `passivity` 锚（B19「无源链路 无增益 max|T|≤1」）物理地位不同**：B19 判的是
#: **光子链路传递矩阵**不得被放大（被动网络 |T|≤1）；本条是**中继站的产出计数**
#: （生成-存储-交换三态竞争下的期望交换次数）—— 既非传递矩阵、亦非增益比值 ⇒ 无重叠。
#:
#: 模型（三态竞争 · **存储时间首次成为自变量**）：
#:   态 0 = 空闲（等待生成）· 态 1 = 已存储且存活 · 态 2 = 已交换产出
#:   速率：生成 λ=1/T_gen · 存储退相干 μ=1/T_mem · 交换消耗 κ=1/T_swap（**三时间尺度竞争**）
#:   P₀(t)=e^{−λt} ⇒ P₁(t)=∫₀ᵗ λ·e^{−λt'}·e^{−γ(t−t')}dt′（γ=μ+κ）
#:   ⇒ **期望交换产出数** `N_swap(T)=κ∫₀ᵀP₁dt=κλ∫₀ᵀ∫₀ᵗ e^{−λt'}·e^{−γ(t−t')}dt′dt`
#:     （生成窗 ⊗ **存储窗** 的嵌套卷积；**存储窗因子 `e^{−t/T_mem}`** 即章程
#:       「`P_succ` 含 `∫e^{−t/T_mem}dt`」要求的物理落点）
#: 闭式（**初等 · 精确**）：`N_swap=κλ/(γ−λ)·[(1−e^{−λT})/λ − (1−e^{−γT})/γ]`
#: 退化档 γ=λ（即 μ+κ=λ）取极限 `(κ/λ)·[1−e^{−λT}(1+λT)]`（消除 0/0）。
#: candidate = 对被积函数 `h(t)=(e^{−λt}−e^{−γt})/(γ−λ)` 的**单重复合 Simpson 求积**（n 段）
#: —— 与 golden「初等闭式」方法学独立；残差 = **Simpson 截断误差**（实测 O(h⁴)）。
#: 🔴 **嵌套双重复合 Simpson 实测被否**：内层域随外层节点变化 ⇒ 主误差退化为 O(h²)
#:   （比值恒 2.00）、动态范围仅 ~30×（< 章程 R2 要求的 1e4×）⇒ 不采用（如实登记）。
#: 🔴 集成隐患：t=0 处 h(0)=0（可去），且 γ→λ 时 h 为 0/0 ⇒ golden 与候选**均须**走极限档。

#: 观测窗（s · 设计示例 200 µs）
_T_OBS_S = 2.0e-4
#: 生成尝试周期（s · 50 µs ⇒ λ=2e4 /s · 生成窗）
_T_GEN_S = 5.0e-5
#: 存储相干时间（s · 160 µs ⇒ μ=6.25e3 /s · **存储窗**）
_T_MEM_S = 1.6e-4
#: 交换门耗时（s · 100 µs ⇒ κ=1e4 /s · 消耗速率）
_T_SWAP_S = 1.0e-4

_B521_DEFAULT = {
    "t_obs_s": 2.0e-4,
    "t_gen_s": 5.0e-5,
    "t_mem_s": 1.6e-4,
    "t_swap_s": 1.0e-4,
}


def _b521_rates(t_gen_s: float, t_mem_s: float, t_swap_s: float):
    """三态速率 λ=1/T_gen · μ=1/T_mem · κ=1/T_swap（须全 > 0）。

    🔴 **先校验再取倒数**：否则 T=0 抛 `ZeroDivisionError`（而非契约约定的 `ValueError`）。
    """
    for _nm, _v in (("T_gen", t_gen_s), ("T_mem", t_mem_s), ("T_swap", t_swap_s)):
        if not float(_v) > 0.0:
            raise ValueError("%s 须 > 0（λ/μ/κ 须有限正）" % _nm)
    lam = 1.0 / float(t_gen_s)
    mu = 1.0 / float(t_mem_s)
    kappa = 1.0 / float(t_swap_s)
    return lam, mu, kappa


def repeater_yield_golden(t_obs_s: float = _T_OBS_S, t_gen_s: float = _T_GEN_S,
                          t_mem_s: float = _T_MEM_S,
                          t_swap_s: float = _T_SWAP_S) -> float:
    """B521 golden：中继站期望交换产出数 N_swap（**精确初等闭式**）。

        N_swap(T) = κλ/(γ−λ)·[(1−e^{−λT})/λ − (1−e^{−γT})/γ]，  γ = μ+κ
    γ→λ 退化档取极限 `(κ/λ)·[1−e^{−λT}(1+λT)]`（0/0 消除）。
    """
    lam, mu, kappa = _b521_rates(t_gen_s, t_mem_s, t_swap_s)
    t_obs = float(t_obs_s)
    if t_obs <= 0.0:
        raise ValueError("观测窗 T 须 > 0")
    g = mu + kappa
    if abs(g - lam) <= 1e-9 * lam:
        return float(kappa / lam * (1.0 - math.exp(-lam * t_obs) * (1.0 + lam * t_obs)))
    return float(kappa * lam / (g - lam)
                 * ((1.0 - math.exp(-lam * t_obs)) / lam
                    - (1.0 - math.exp(-g * t_obs)) / g))


def repeater_yield_candidate(t_obs_s: float = _T_OBS_S, t_gen_s: float = _T_GEN_S,
                             t_mem_s: float = _T_MEM_S, t_swap_s: float = _T_SWAP_S,
                             n: int = _M_BY_BID["B521"]) -> float:
    """B521 candidate：**单重复合 Simpson 求积**（n 段 · n 须为 ≥2 的偶数）。

    被积函数 h(t)=(e^{−λt}−e^{−γt})/(γ−λ)（内层解析积分后由 N_swap=κλ∫₀ᵀh dt 导出）。
    🔴 粗端未入渐近区 ⇒ 比值偏高（实测 15.52→16.00），如实登记不假称「恰 16」。
    """
    n = int(n)
    if n < 2 or n % 2:
        raise ValueError("复合 Simpson 段数 n 须为 ≥2 的偶数")
    lam, mu, kappa = _b521_rates(t_gen_s, t_mem_s, t_swap_s)
    t_obs = float(t_obs_s)
    if t_obs <= 0.0:
        raise ValueError("观测窗 T 须 > 0")
    g = mu + kappa
    h_step = t_obs / n
    if abs(g - lam) <= 1e-9 * lam:
        def f(t):
            return t * math.exp(-lam * t)
    else:
        def f(t):
            return (math.exp(-lam * t) - math.exp(-g * t)) / (g - lam)
    s = f(0.0) + f(t_obs)
    for i in range(1, n):
        s += (4.0 if i % 2 else 2.0) * f(i * h_step)
    return float(kappa * lam * s * h_step / 3.0)


# ── 统一入口（harness / golden.py 按名调用）────────────────────────────────
def golden_b519(l_depol_m: float = _DEFAULT_L_DEPOL_M) -> float:
    return distribution_fidelity_golden(l_depol_m)


def cand_b519(l_depol_m: float = _DEFAULT_L_DEPOL_M,
              n: int = _M_BY_BID["B519"]) -> float:
    return distribution_fidelity_candidate(l_depol_m, n)


def golden_b520(packet_sigma_s: float = _PACKET_SIGMA,
                delay_s: float = _PACKET_DELAY,
                dw_rad_s: float = _PACKET_DW) -> float:
    return hom_visibility_golden(packet_sigma_s, delay_s, dw_rad_s)


def cand_b520(packet_sigma_s: float = _PACKET_SIGMA,
              delay_s: float = _PACKET_DELAY,
              dw_rad_s: float = _PACKET_DW,
              n: int = _M_BY_BID["B520"]) -> float:
    return hom_visibility_candidate(packet_sigma_s, delay_s, dw_rad_s, n)


def golden_b521(t_obs_s: float = _T_OBS_S, t_gen_s: float = _T_GEN_S,
                t_mem_s: float = _T_MEM_S, t_swap_s: float = _T_SWAP_S) -> float:
    return repeater_yield_golden(t_obs_s, t_gen_s, t_mem_s, t_swap_s)


def cand_b521(t_obs_s: float = _T_OBS_S, t_gen_s: float = _T_GEN_S,
              t_mem_s: float = _T_MEM_S, t_swap_s: float = _T_SWAP_S,
              n: int = _M_BY_BID["B521"]) -> float:
    return repeater_yield_candidate(t_obs_s, t_gen_s, t_mem_s, t_swap_s, n)


#: 暴露给锚定义（键集必须 ⊆ golden 形参集）
B519_DEFAULT_PARAMS = dict(_B519_DEFAULT)
B520_DEFAULT_PARAMS = dict(_B520_DEFAULT)
B521_DEFAULT_PARAMS = dict(_B521_DEFAULT)

_GOLDEN_BY_BID = {"B519": golden_b519, "B520": golden_b520, "B521": golden_b521}
_CAND_BY_BID = {"B519": cand_b519, "B520": cand_b520, "B521": cand_b521}

#: 自检用例：bid, 物理参数（golden 键）
_CASES = (("B519", _B519_DEFAULT), ("B520", _B520_DEFAULT), ("B521", _B521_DEFAULT))


# ── 自检 ───────────────────────────────────────────────────────────────────
def _selfcheck() -> int:
    bad = 0
    print("=" * 78)
    print("Batch J5 数值核自检（B519 分发后两体纠缠保真度）")
    print("=" * 78)
    for bid, params in _CASES:
        gold = _GOLDEN_BY_BID[bid](**params)
        tol = float(_TOL_BY_BID[bid])
        n_end = int(_M_BY_BID[bid])
        grid = list(_GRID_BY_BID[bid])

        chain = []
        for n in grid:
            chain.append((n, abs(_CAND_BY_BID[bid](n=n, **params) - gold)))
        d_res = abs(_CAND_BY_BID[bid](n=n_end, **params) - gold)

        ratios = []
        for i in range(1, len(chain)):
            ratios.append(chain[i - 1][1] / chain[i][1] if chain[i][1] > 0 else float("inf"))

        dyn = chain[0][1] / chain[-1][1] if chain[-1][1] > 0 else float("inf")
        mono = all(chain[i][1] > chain[i + 1][1] for i in range(len(chain) - 1))
        margin = tol / d_res if d_res > 0 else float("inf")

        print("\n[%s] golden=%.15e  tol=%.1e  默认 n=%d" % (bid, gold, tol, n_end))
        print("  残差链: " + " → ".join("n=%d:%.4e" % (n, d) for n, d in chain))
        print("  比值:   " + " / ".join("%.2f" % r for r in ratios))
        print("  动态范围=%.4g×  余量=%.1f×  |golden|/tol=%.4g×  单调=%s"
              % (dyn, margin, abs(gold) / tol, mono))

        checks = {
            "残差 > 0（非代数恒等）": d_res > 0.0,
            "残差 < tol（判决通过）": d_res < tol,
            "基线残差 > 1e-12（不沉双精度地板）": d_res > 1e-12,
            "粗端残差 > 1e-13（离散误差主导）": chain[0][1] > 1e-13,
            "残差链严格单调递减": mono,
            "动态范围 ≥ 1e4×": dyn >= 1.0e4,
            "余量 ≥ 100×": margin >= 100.0,
            "|golden| / tol ≥ 13.5×": abs(gold) / tol >= 13.5,
            # B519 = RK4 ⇒ O(h⁴)，比值从**上方**逼近 16（18.02→16.24）；
            # B521 = 复合 Simpson ⇒ O(h⁴)，比值从**下方**逼近 16（15.52→16.00）；
            # ⇒ 判据 = 「趋近标称阶 16」（不限方向）+ 落在量级带内（粗端未入渐近区，如实登记）。
            # B520 = 复合梯形 ⇒ **超几何收敛**（比值单调递增，非幂律 ⇒ 不假称「恰 4」）。
            "比值形态与算法一致（B519/B521 趋近 16 · B520 超几何递增）":
                all(ratios[i] < ratios[i + 1] for i in range(len(ratios) - 1))
                if bid == "B520"
                else (4.0 <= ratios[-1] <= 22.0
                      and abs(ratios[-1] - 16.0) <= abs(ratios[0] - 16.0)),
            "默认档 = 扫描格末端": n_end == grid[-1],
        }
        for k, v in checks.items():
            print("  [%s] %s" % ("PASS" if v else "FAIL", k))
            if not v:
                bad += 1

        # 反向探针：物理参数扰动 ±10% 必须显著改变候选（C3/C5）
        # 🔴 通用化：取 params 字典序第一个键作扰动键（B519=l_depol_m · B520=delay_s）
        key0 = sorted(params)[0]
        d_pert = abs(_CAND_BY_BID[bid](n=n_end, **{**params, key0: params[key0] * 1.1})
                     - _CAND_BY_BID[bid](n=n_end, **params))
        sig = d_pert / tol
        ok_sig = sig >= 1.4
        print("  [%s] 扰动 %s ×1.1 ⇒ 信号 %.4e（%.1f× tol ≥ 1.4×）"
              % ("PASS" if ok_sig else "FAIL", key0, d_pert, sig))
        if not ok_sig:
            bad += 1

        # 反向探针：非法离散参数必抛
        raised = False
        try:
            _CAND_BY_BID[bid](n=0, **params)
        except ValueError:
            raised = True
        print("  [%s] 反向：n=0 必抛 ValueError" % ("PASS" if raised else "FAIL"))
        if not raised:
            bad += 1

    print("\n" + "=" * 78)
    print("自检结果：%s（bad=%d）" % ("ALL PASS" if bad == 0 else "FAIL", bad))
    print("=" * 78)
    return bad


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_selfcheck())
