# -*- coding: utf-8 -*-
"""Batch J3 数值实现 · 量子测控与读出征程（J3）M0–M4。

════════════════════════════════════════════════════════════════
本批**五锚**（`benchmark_defs/part7.py` 引用）——

  B510：**共振/失谐 Rabi 时域布居 P₁(t)**（驱动脉冲层 · M0）
        golden   = 广义 Rabi 闭式 **P₁(t) = (Ω²/Ω_R²)·sin²(Ω_R t / 2)**，
                   Ω_R = √(Ω² + δ²)
                   —— 二能级旋转波近似（RWA）哈密顿 H = (Ω/2)σ_x + (δ/2)σ_z 的
                   **精确解析解**（H 为常矩阵 ⇒ e^{−iHt} 严格解，**非截断近似**）。
        candidate = **时域 TDSE 四阶 RK4 步进**（i dψ/dt = Hψ，ψ(0)=|0⟩，n 步）
                   —— 与 golden 方法学独立（解析闭式 vs 数值时间推进）。

  B511：**三能级 transmon 驱动泄漏布居 P_leak(t)**（DRAG 抑制对象 · M1）
        golden   = 三能级 RWA 哈密顿
                     H = (Ω/2)(|0⟩⟨1|+|1⟩⟨0|) + (√2·Ω/2)(|1⟩⟨2|+|2⟩⟨1|) + α|2⟩⟨2|
                   的**精确谱分解闭式**：
                     P_leak(t) = |Σ_k ⟨0|v_k⟩⟨v_k|2⟩ e^{−iλ_k t}|²
                   特征多项式 λ³ − αλ² − (3Ω²/4)λ + αΩ²/4 = 0 经**三角法（depressed
                   cubic, λ = μ − A/3）**解析求根（**精确解、非数值迭代、非截断**）。
        candidate = **同一 ODE 的时域 RK4 步进**（3 维复态矢，ψ(0)=|0⟩，n 步）。

  B512：**去极化信道纯度衰减 P(t)（二阶 · unitarity）**（门保真标定 · M2）
        golden   = **去极化 Bloch 各向同性收缩的精确闭式**：
                     r(t) = r(0)·e^{−Γt}  ⇒  P(t) = Tr(ρ²) = (1 + |r₀|²·e^{−2Γt})/2
                   —— 由去极化 Lindblad 主方程 dρ/dt = (Γ/4)(Σᵢσᵢρσᵢ − 3ρ) 的**严格解**
                   （Bloch 向量线性 ODE ⇒ 指数严格解，**非截断近似**）。
        candidate = **密度矩阵 Liouvillian 的时域四阶 RK4 积分**（2×2 复密度矩阵，
                   步数 n）—— 与 golden 方法学独立（解析指数闭式 vs 数值时间推进）。
        🔴 物理意义：**unitarity（二阶纯度衰减）** 与一阶 RB 保真度是**不同阶**的量
                   —— 对相干（酉）误差纯度不衰减（u=1），对非相干（去极化）u=p²；
                   J3-M2 用它把「相干误差 vs 非相干误差」分离（章程 §3 M2）。

  B513：**Purcell 滤波器抑制比 S**（读出链 · M3）
        golden   = **并联开路 λ/4 短截线带阻滤波器的 ABCD 代数闭式**：
                     S21(f) = 2 / (2 + j·(Z₀/Z_s)·tan βl)（βl = (π/2)(f_q/f_s)）
                     S = Γ_P^{no}/Γ_P^{filter} = 1/|S21(f_q)|²
                   —— 传输线 ABCD 矩阵级联的**精确代数式**（**非近似**）。
        candidate = **导纳 ODE dy/dθ = j(1 − y²)（y(0)=0 ⇒ y = j·tanθ）的时域四阶
                   RK4 数值积分**（沿 stub 长度从负载积到输入端），步数 n 为离散参数。
        🔴 与 **B18**（谐振腔 Purcell 因子 F_P = 4g²/(κγ)，**器件级输入因子**）
                   三方分歧见文件尾注。

  B514：**相位不敏感放大链附加噪声光子数 n_add**（低温电子学 · M4）
        golden   = **分布式（行波）相位不敏感放大链的精确闭式**：
                     n_add = (η/g)·(1 − e^{−gL})
                   —— 逐段噪声 e^{−gz} 权重积分的**严格解析结果**；gL→∞ ⇒ n_add → η/g
                   = **Caves 量子极限 1/2 光子**（相位不敏感放大器）。
        candidate = **复合 Simpson 数值求积**（把 [0,L] 离散为 n 段，O(h⁴)），
                   离散参数 = n。
        🔴 与 **B467**（TIA 读出噪声底 kT/C，**µV 电压量纲**）三方分歧见文件尾注。

🔴 物理意义（承 J3 蓝图 · Layer 3 测控闭环 / 缺口 G-CTRL*）：
  · B510 = 脉冲层「怎么打」 · B511 = 泄漏抑制「打得多干净」（M0/M1）；
  · **B512 = 门保真「标得准不准」**（二阶纯度衰减 = unitarity，分离相干/非相干误差）；
  · **B513 = 读出链「漏不漏」**（Purcell 滤波器把 qubit 经 feedline 的外泄率压低几倍）；
  · **B514 = 低温电子学「噪不噪」**（放大链附加噪声离量子极限 1/2 多远）。
  ⇒ 四段构成 `lda_qeda/control_closed_loop.py` **测控闭环**的物理判据源头。

🔴 与既有锚的边界（**同源体检 · 实 grep 全仓核验**，每档第一道闸）：
  · 实 grep（`benchmark_defs/`）：`drag` **0 命中**；`leakage` **0 命中**；
    `unitarity` **0 命中**；`纯度|purity` 仅 `part5.py` B454（TMSS **光学连续变量**条件态
    纯度，与 qubit 门序列无关）；`Caves|n_add|量子极限|JPA|参量放大|级联噪声|噪声因子`
    **0 命中**；`解调|demod|匹配滤波|分配矩阵|assignment` **0 命中**；
    `purcell|Purcell` 仅 `part1.py` B18（**F_P 器件级因子**，见下）。
  · 与 **B10**（单比特门保真度 F · 退相干极限 `(3+2e^{−t/T2}+e^{−t/T1})/6`，**一阶**保真度）
    **三方分歧**：①被测标量：**二阶纯度 P=Tr(ρ²)** vs **一阶保真度 F**（对相干误差敏感度
    根本不同 —— 酉误差 u=1 而 F<1，正是 unitarity 的物理价值）；②物理构型：**对称去极化**
    （各向同性自旋弛豫，单率 Γ）vs **T1/T2 非对称**（振幅 + 相位双通道）；③数值格式：
    **2×2 复密度矩阵 Liouvillian RK4** vs **4×4 PTM 超算子积分** ⇒ 计新锚。
  · 与 **B18**（Purcell 因子 F_P = 4g²/(κγ)，**器件级衰减增强因子**）**三方分歧**：
    ①被测标量：**滤波器系统级抑制倍率 S**（加滤波器后的 T1 提升比）vs **器件级 F_P 因子**；
    ②物理构型：**传输线 + λ/4 短截线滤波器网络** vs **单腔-qubit 耦合**；
    ③数值格式：**导纳 ODE 的 RK4 数值积分** vs B18 的纯代数闭式 ⇒ 计新锚。
  · 与 **B467**（TIA 读出噪声底 kT/C）**三方分歧**：①被测标量：**附加噪声光子数 n_add**
    （无量纲/光子数）vs **输出 rms 噪声电压 v_n（µV）**；②物理构型：**微波分布式参量
    放大链** vs **跨阻放大器反馈电阻热噪声**；③数值格式：**复合 Simpson 求积** vs
    B467 的**时域冲激响应 Parseval 积分** ⇒ 计新锚。
  · B512 vs B513 vs B514 **互相分歧**：物理量纲（纯度 / 无量纲倍率 / 光子数）、构型
    （qubit 去极化信道 / 微波滤波网络 / 分布放大器链）、格式（Liouvillian RK4 / 导纳
    ODE RK4 / Simpson 求积）三者互不相同 ⇒ 各计一锚。
  · 与本征程 **D-91 `solve_drive`**（静态 RWA 本征分裂，**非账本锚**）分歧：B510/B511 已登记。

🔴 判据 D 双向标定（默认档必须落在**离散误差主导区**，且默认档 = 扫描格末端）：
  实测扫描（2026-10-14 现算）：
    B510（Ω=0.05, δ=0.03, t=100）：
        n= 8 → 1.218e-04     n= 32 → 5.269e-07     n=128 → 2.092e-09  ← 默认档
      比值 14.85/15.57/15.82/15.91 ⇒ **O(h⁴)**；动态范围 5.82e4×。
    B511（Ω=0.05, α=−0.3, t=π/Ω）：
        n= 16 → 4.461e-04     n= 64 → 2.715e-06     n=256 → 1.030e-08  ← 默认档
      比值 10.51/15.63/16.25/16.22 ⇒ **O(h⁴)**；动态范围 4.33e4×。
    B512（Γ=0.02, t=100）：
        n=  4 → 2.905e-05     n= 16 → 8.272e-08     n= 64 → 2.988e-10  ← 默认档
      比值 19.76/17.77/16.85/16.42 ⇒ **O(h⁴)**；动态范围 9.72e4×。
    B513（f_q=5.5, f_s=6.0, z_ratio=1.0）：
        n= 64 → 2.988e-04     n=256 → 1.193e-06     n=1024 → 4.652e-09 ← 默认档
      比值 15.69/15.96/16.02/16.02 ⇒ **O(h⁴)**；动态范围 6.42e4×。
    B514（eta_ratio=0.5, g=0.5, L=10）：
        n= 16 → 2.601e-05     n= 64 → 1.027e-07     n= 256 → 4.015e-10 ← 默认档
      比值 15.86/15.97/15.99/16.00 ⇒ **O(h⁴)**（复合 Simpson）；动态范围 6.48e4×。
  ⇒ tol 绝对口径按量级标定：B510 tol=1e-6（余量 478×）；B511 tol=1e-5（余量 971×）；
     **B512 tol=1e-7（余量 335×）· B513 tol=1e-6（余量 215×）· B514 tol=1e-6（余量 2493×）**。
  🔴 稳定性/口径边界（实测）：
    · B511 三能级含 α 实对角项 ⇒ RK4 稳定域 |hλ| ≤ 2√2，t=100/n=8 已越界发散 ⇒ 从 n=16 起；
    · B512 的 2×2 Liouvillian 谱半径 |Γ|=0.02 ⇒ n=4 时 |hλ|=0.5 ≪ 2.83 ⇒ n=4 起安全；
    · B513 的导纳 ODE 在 θ→π/2（谐振）处非线性极强 ⇒ 本档取 f_q/f_s=11/12（θ≈1.44 离极点
      有余量），且 y=j·tanθ 的实部为 tanθ（大）⇒ 以 |S21|² 而非 tan 直接作判据；
    · B514 的复合 Simpson 要求 n 为偶数（代码内自动 +1）。

🔴 命名避让：批次 `_batch_j3_numeric` / `_get_j3_numeric`（实 grep 零占用）；
  候选 key 前缀 `b510_`–`b514_` 未占用。磁盘 `_adapter_p*.py` **不新建**（L9 守卫：恒 6 片）。

🔴 纪律：
· golden 与 candidate 是**两种结构不同的算法**（解析谱/闭式 vs 数值时间推进/求积）；
  进报告数字一律**现算**。
· 零 RNG（五锚均为确定性数值格式）。
· 诚实边界：Ω/α/δ/Γ/t/f_q/f_s/η/g/L 为**设计示例量级**（非实测 PDK / 非流片）；
  只证「闭式 ⇄ 数值」一致这一数学事实 + 测控物理链自洽，
  **不作制造/性能宣称**，不报能效/TOPS/fJ-op。零商业依赖（纯 numpy + math）。
"""
from __future__ import annotations

import cmath
import functools
import math

import numpy as np

# ── 三表（判据 D 扫描格 / 默认档 = 格末端 / tol 绝对口径按量级标定）─────────────
_M_BY_BID = {"B510": 128, "B511": 256, "B512": 64, "B513": 1024, "B514": 256}
_GRID_BY_BID = {
    "B510": [8, 16, 32, 64, 128],
    "B511": [16, 32, 64, 128, 256],
    "B512": [4, 8, 16, 32, 64],
    "B513": [64, 128, 256, 512, 1024],
    "B514": [16, 32, 64, 128, 256],
}
_TOL_BY_BID = {"B510": 1e-6, "B511": 1e-5, "B512": 1e-7, "B513": 1e-6, "B514": 1e-6}

#: 默认物理参数（只放 golden 接受的键；离散参数 n 由候选签名默认值承载）
_B510_DEFAULT = {"Omega": 0.05, "delta": 0.03, "t": 100.0}
#: B511 的 t = π/Ω（Ω=0.05 rad/ns ⇒ π 脉冲时长）
_B511_DEFAULT = {"Omega": 0.05, "alpha": -0.3, "t": math.pi / 0.05}
#: B512 去极化率 Γ（1/ns）与演化时长 t（ns）；Γt=2 ⇒ 纯度 1 → 0.509
_B512_DEFAULT = {"Gamma": 0.02, "t": 100.0}
#: B513 滤波器：qubit 频率 / stub 谐振频率 / 阻抗比 Z0:Zs
_B513_DEFAULT = {"f_q": 5.5, "f_s": 6.0, "z_ratio": 1.0}
#: B514 分布式放大链：单位增益附加噪声（相对量子极限）/ 增益率 / 长度
_B514_DEFAULT = {"eta_ratio": 0.5, "g": 0.5, "L": 10.0}


# ══════════════════════════════════════════════════════════════════════
# B510 · 二能级驱动态矢 + 广义 Rabi 布居
# ══════════════════════════════════════════════════════════════════════
def _two_level_H(Omega: float, delta: float) -> "np.ndarray":
    """RWA 驱动哈密顿 H = (δ/2)σ_z + (Ω/2)σ_x（|0⟩ 取 +δ/2）。"""
    return np.array([[delta / 2.0, Omega / 2.0],
                     [Omega / 2.0, -delta / 2.0]], dtype=complex)


def rabi_population_golden(Omega: float = 0.05, delta: float = 0.03,
                           t: float = 100.0) -> float:
    """B510 golden：广义 Rabi 时域布居闭式（**精确**，H 常矩阵的严格解）。

        P₁(t) = (Ω² / Ω_R²) · sin²(Ω_R · t / 2),   Ω_R = √(Ω² + δ²)

    推导：H = (δ/2)σ_z + (Ω/2)σ_x ⇒ 本征值 ±Ω_R/2、绕 (Ω,0,δ) 轴作角 Ω_R·t 的旋转；
    ψ(0)=|0⟩ ⇒ ⟨σ_z⟩ 与 |⟨1|ψ⟩|² 直接给出上式（δ=0 ⇒ sin²(Ωt/2)；Ω=0 ⇒ 0）。
    """
    orabi = math.hypot(float(Omega), float(delta))
    if orabi == 0.0:
        raise ValueError("Ω 与 δ 不可同时为 0（无驱动且无失谐 ⇒ 无演化）")
    frac = (float(Omega) ** 2) / (orabi ** 2)
    return frac * math.sin(orabi * float(t) / 2.0) ** 2


def _rk4_state(H: "np.ndarray", psi0: "np.ndarray", t: float, n: int) -> "np.ndarray":
    """四阶 RK4 推 i dψ/dt = Hψ（H 常矩阵）在 [0, t] 上 n 步。"""
    n = int(n)
    if n < 1:
        raise ValueError("步数 n 须 ≥ 1")
    h = float(t) / n
    psi = np.asarray(psi0, dtype=complex)

    def _f(y):
        return -1j * (H @ y)

    for _ in range(n):
        k1 = _f(psi)
        k2 = _f(psi + 0.5 * h * k1)
        k3 = _f(psi + 0.5 * h * k2)
        k4 = _f(psi + h * k3)
        psi = psi + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return psi


def rabi_population_candidate(Omega: float = 0.05, delta: float = 0.03, t: float = 100.0,
                              n: int = _M_BY_BID["B510"]) -> float:
    """B510 candidate：时域 TDSE 四阶 RK4 步进（与 golden 方法学独立）。"""
    H = _two_level_H(float(Omega), float(delta))
    psi = _rk4_state(H, np.array([1.0, 0.0], dtype=complex), float(t), int(n))
    return float(abs(psi[1]) ** 2)


# ══════════════════════════════════════════════════════════════════════
# B511 · 三能级 transmon 驱动泄漏（三角法精确谱 ⇄ 时域 RK4）
# ══════════════════════════════════════════════════════════════════════
def _qutrit_H(Omega: float, alpha: float) -> "np.ndarray":
    """三能级 transmon RWA 驱动哈密顿（√2 = 谐振子升降算符矩阵元）。"""
    a = float(Omega) / 2.0
    b = math.sqrt(2.0) * float(Omega) / 2.0
    return np.array([[0.0, a, 0.0],
                     [a, 0.0, b],
                     [0.0, b, float(alpha)]], dtype=float)


def qutrit_eigenvalues_trig(Omega: float = 0.05, alpha: float = -0.3):
    """三能级驱动的**精确**本征值（三角法解 depressed cubic）。

    特征多项式（det(H − λI) = 0）：
        λ³ − α·λ² − (a² + b²)·λ + a²·α = 0,   a = Ω/2, b = √2Ω/2
    ⇒ 令 λ = μ − A/3（A = −α）得 μ³ + pμ + q = 0，其中
        p = −(a² + b²) − α²/3  (< 0 ∀Ω>0)
        q = −2α³/27           （Ω 在 q 中恰好相消 —— 闭式化简的直接后果）
    ⇒ 三实根 μ_k = 2√(−p/3)·cos[(1/3)arccos(χ) − 2πk/3]，χ = (3q/2p)·√(−3/p)。
    返回升序三本征值（list[float]）。
    """
    Omega, alpha = float(Omega), float(alpha)
    a2 = (Omega / 2.0) ** 2
    b2 = (math.sqrt(2.0) * Omega / 2.0) ** 2
    big_a = -alpha
    big_b = -(a2 + b2)
    big_c = a2 * alpha
    p = big_b - big_a * big_a / 3.0
    q = 2.0 * big_a ** 3 / 27.0 - big_a * big_b / 3.0 + big_c
    if p >= 0.0:
        raise ValueError("p ≥ 0（Ω 与 α 同时退化）⇒ 三角法不适用")
    m_amp = 2.0 * math.sqrt(-p / 3.0)
    arg = (3.0 * q / (2.0 * p)) * math.sqrt(-3.0 / p)
    arg = max(-1.0, min(1.0, arg))
    theta = math.acos(arg) / 3.0
    lam = [m_amp * math.cos(theta - 2.0 * math.pi * k / 3.0) - big_a / 3.0
           for k in range(3)]
    return sorted(lam)


def qutrit_leakage_golden(Omega: float = 0.05, alpha: float = -0.3,
                          t: float = None) -> float:
    """B511 golden：三能级驱动泄漏布居闭式（**精确**谱分解，非截断近似）。

        P_leak(t) = |Σ_k ⟨0|v_k⟩·⟨v_k|2⟩·e^{−iλ_k t}|²

    其中 (λ_k, v_k) 为 **H 的精确本征对**（λ_k 由 `qutrit_eigenvalues_trig` 三角法给出；
    解析本征矢 v_k ∝ (1, λ_k/a, (λ_k² − a²)/(a·b))，随后归一化）。
    ψ(0)=|0⟩ ⇒ c_k = ⟨v_k|0⟩ = v_k[0]（实）。
    """
    if t is None:
        t = _B511_DEFAULT["t"]
    Omega, alpha = float(Omega), float(alpha)
    a = Omega / 2.0
    b = math.sqrt(2.0) * Omega / 2.0
    acc = 0.0 + 0.0j
    for lam in qutrit_eigenvalues_trig(Omega, alpha):
        v2 = (lam * lam - a * a) / (a * b)
        norm = math.sqrt(1.0 + (lam / a) ** 2 + v2 ** 2)
        v0 = 1.0 / norm
        acc += v0 * (v2 / norm) * cmath.exp(-1j * lam * float(t))
    return float(abs(acc) ** 2)


def qutrit_leakage_candidate(Omega: float = 0.05, alpha: float = -0.3, t: float = None,
                             n: int = _M_BY_BID["B511"]) -> float:
    """B511 candidate：三能级同一 ODE 的时域 RK4 步进（与 golden 方法学独立）。"""
    if t is None:
        t = _B511_DEFAULT["t"]
    H = _qutrit_H(float(Omega), float(alpha))
    psi = _rk4_state(H, np.array([1.0, 0.0, 0.0], dtype=complex), float(t), int(n))
    return float(abs(psi[2]) ** 2)


# ══════════════════════════════════════════════════════════════════════
# B512 · 去极化信道纯度衰减（二阶 · unitarity 闭式 ⇄ Liouvillian RK4）
# ══════════════════════════════════════════════════════════════════════
_SX = np.array([[0, 1], [1, 0]], dtype=complex)
_SY = np.array([[0, -1j], [1j, 0]], dtype=complex)
_SZ = np.array([[1, 0], [0, -1]], dtype=complex)


def _depol_rhs(rho: "np.ndarray", Gamma: float) -> "np.ndarray":
    """去极化 Lindblad 右端 dρ/dt = (Γ/4)(σ_x ρ σ_x + σ_y ρ σ_y + σ_z ρ σ_z − 3ρ)。

    Bloch 检验：该式等价于 dr/dt = −Γr（各向同性收缩）⇒ r(t) = r(0)e^{−Γt}。
    """
    return (Gamma / 4.0) * (_SX @ rho @ _SX + _SY @ rho @ _SY + _SZ @ rho @ _SZ
                            - 3.0 * rho)


def purity_decay_golden(Gamma: float = 0.02, t: float = 100.0) -> float:
    """B512 golden：去极化信道纯度衰减闭式（**精确**，Bloch 线性 ODE 的严格解）。

        P(t) = Tr(ρ²) = (1 + |r₀|²·e^{−2Γt}) / 2

    初态 |0⟩ ⇒ |r₀| = 1 ⇒ P(0) = 1、P(∞) = 1/2。
    🔴 **二阶量**：P ∝ e^{−2Γt}（衰减率是 Bloch 收缩率 Γ 的 2 倍 = unitarity 的物理内容），
    与一阶保真度 F ∝ e^{−Γt} 是**不同阶**的量。
    """
    return 0.5 * (1.0 + math.exp(-2.0 * float(Gamma) * float(t)))


def purity_decay_candidate(Gamma: float = 0.02, t: float = 100.0,
                           n: int = _M_BY_BID["B512"]) -> float:
    """B512 candidate：密度矩阵 Liouvillian 时域四阶 RK4 积分（与 golden 方法学独立）。

    2×2 复密度矩阵 ρ（初态 |0⟩⟨0|），RK4 推 dρ/dt = `_depol_rhs`，返回 Tr(ρ²)。
    残差 = RK4 截断误差（O(h⁴)）。
    """
    n = int(n)
    if n < 1:
        raise ValueError("步数 n 须 ≥ 1")
    Gamma, t = float(Gamma), float(t)
    rho = np.array([[1.0, 0.0], [0.0, 0.0]], dtype=complex)
    h = t / n
    for _ in range(n):
        k1 = _depol_rhs(rho, Gamma)
        k2 = _depol_rhs(rho + 0.5 * h * k1, Gamma)
        k3 = _depol_rhs(rho + 0.5 * h * k2, Gamma)
        k4 = _depol_rhs(rho + h * k3, Gamma)
        rho = rho + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return float(np.real(np.trace(rho @ rho)))


# ══════════════════════════════════════════════════════════════════════
# B513 · Purcell 滤波器抑制比（ABCD 代数闭式 ⇄ 导纳 ODE RK4）
# ══════════════════════════════════════════════════════════════════════
def purcell_suppression_golden(f_q: float = 5.5, f_s: float = 6.0,
                               z_ratio: float = 1.0) -> float:
    """B513 golden：并联开路 λ/4 短截线带阻滤波器的抑制比（**精确** ABCD 代数闭式）。

    滤波器 = 并联在主线上的开路 λ/4 短截线（谐振频率 f_s）：
        ABCD = [[1, 0], [Y_stub, 1]],   Y_stub = j·Y_s·tan(βl)
        S21  = 2 / (2 + j·(Z₀/Z_s)·tan(βl)),   βl = (π/2)·(f_q/f_s)
    抑制比 S = Γ_P^{no}/Γ_P^{filter} = 1/|S21(f_q)|²（qubit 频率处外泄率被压低的倍率）。
    f_q→f_s ⇒ tan→∞ ⇒ S21→0 ⇒ S→∞（完美带阻）；f_q 远离 f_s ⇒ S→1（透明）。
    """
    th = (math.pi / 2.0) * (float(f_q) / float(f_s))
    s21 = 2.0 / complex(2.0, float(z_ratio) * math.tan(th))
    return 1.0 / abs(s21) ** 2


def purcell_suppression_candidate(f_q: float = 5.5, f_s: float = 6.0, z_ratio: float = 1.0,
                                  n: int = _M_BY_BID["B513"]) -> float:
    """B513 candidate：导纳 ODE 的时域四阶 RK4 数值积分（与 golden 方法学独立）。

    归一化导纳 y = Y_in/Y_s 满足 dy/dθ = j(1 − y²)，y(0)=0（开路负载）⇒ y(θ) = j·tanθ。
    沿 stub 长度（θ ∈ [0, βl]）RK4 步进 n 步，取 tanθ = (y/j) 的实部构造 S21。
    残差 = RK4 截断误差（O(h⁴)）。
    """
    n = int(n)
    if n < 1:
        raise ValueError("步数 n 须 ≥ 1")
    theta = (math.pi / 2.0) * (float(f_q) / float(f_s))
    h = theta / n
    y = 0j

    def _f(v):
        return 1j * (1.0 - v * v)

    for _ in range(n):
        k1 = _f(y)
        k2 = _f(y + 0.5 * h * k1)
        k3 = _f(y + 0.5 * h * k2)
        k4 = _f(y + h * k3)
        y = y + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    tan_v = (y / 1j).real
    s21 = 2.0 / complex(2.0, float(z_ratio) * float(tan_v))
    return 1.0 / abs(s21) ** 2


# ══════════════════════════════════════════════════════════════════════
# B514 · 分布式相位不敏感放大链附加噪声（闭式 ⇄ 复合 Simpson 求积）
# ══════════════════════════════════════════════════════════════════════
def amp_noise_golden(eta_ratio: float = 0.5, g: float = 0.5, L: float = 10.0) -> float:
    """B514 golden：分布式相位不敏感放大链的输入参考附加噪声光子数（**精确**闭式）。

        n_add = (η/g)·(1 − e^{−gL})

    推导：z 处每单位长度产生 η 光子噪声，传播到输出被增益 e^{g(L−z)} 放大；
    输入参考（除总增益 e^{gL}）⇒ n_add = ∫₀^L (η/g)·g·e^{−gz} dz = (η/g)(1 − e^{−gL})。
    单位增益附加噪声 η/g = 1/2 ⇒ **Caves 量子极限**（相位不敏感放大器）；gL→∞ ⇒ n_add→1/2。
    """
    return float(eta_ratio) * (1.0 - math.exp(-float(g) * float(L)))


def amp_noise_candidate(eta_ratio: float = 0.5, g: float = 0.5, L: float = 10.0,
                        n: int = _M_BY_BID["B514"]) -> float:
    """B514 candidate：复合 Simpson 数值求积（与 golden 解析闭式方法学独立）。

    n_add = (η/g)·∫₀^L g·e^{−gz} dz，域 [0,L] 等分 n 段（n 自动取偶），
    复合 Simpson 权重 1,4,2,4,…,4,1。残差 = O(h⁴)（Simpson 标称阶）。
    """
    n = int(n)
    if n < 2:
        raise ValueError("步数 n 须 ≥ 2")
    if n % 2:
        n += 1
    g, L = float(g), float(L)
    h = L / n
    s = 1.0 + math.exp(-g * L)
    for k in range(1, n):
        s += (4.0 if k % 2 else 2.0) * math.exp(-g * k * h)
    integral = (h / 3.0) * s
    return float(eta_ratio) * g * integral


# ── 统一入口（harness / golden.py 按名调用）────────────────────────────────
def golden_b510(Omega: float = 0.05, delta: float = 0.03, t: float = 100.0) -> float:
    return rabi_population_golden(Omega, delta, t)


def cand_b510(Omega: float = 0.05, delta: float = 0.03, t: float = 100.0,
              n: int = _M_BY_BID["B510"]) -> float:
    return rabi_population_candidate(Omega, delta, t, n)


def golden_b511(Omega: float = 0.05, alpha: float = -0.3, t: float = None) -> float:
    if t is None:
        t = _B511_DEFAULT["t"]
    return qutrit_leakage_golden(Omega, alpha, t)


def cand_b511(Omega: float = 0.05, alpha: float = -0.3, t: float = None,
              n: int = _M_BY_BID["B511"]) -> float:
    if t is None:
        t = _B511_DEFAULT["t"]
    return qutrit_leakage_candidate(Omega, alpha, t, n)


def golden_b512(Gamma: float = 0.02, t: float = 100.0) -> float:
    return purity_decay_golden(Gamma, t)


def cand_b512(Gamma: float = 0.02, t: float = 100.0,
              n: int = _M_BY_BID["B512"]) -> float:
    return purity_decay_candidate(Gamma, t, n)


def golden_b513(f_q: float = 5.5, f_s: float = 6.0, z_ratio: float = 1.0) -> float:
    return purcell_suppression_golden(f_q, f_s, z_ratio)


def cand_b513(f_q: float = 5.5, f_s: float = 6.0, z_ratio: float = 1.0,
              n: int = _M_BY_BID["B513"]) -> float:
    return purcell_suppression_candidate(f_q, f_s, z_ratio, n)


def golden_b514(eta_ratio: float = 0.5, g: float = 0.5, L: float = 10.0) -> float:
    return amp_noise_golden(eta_ratio, g, L)


def cand_b514(eta_ratio: float = 0.5, g: float = 0.5, L: float = 10.0,
              n: int = _M_BY_BID["B514"]) -> float:
    return amp_noise_candidate(eta_ratio, g, L, n)


@functools.lru_cache(maxsize=None)
def _g510_c(Omega: float, delta: float, t: float) -> float:
    return golden_b510(Omega, delta, t)


@functools.lru_cache(maxsize=None)
def _c510_c(Omega: float, delta: float, t: float, n: int) -> float:
    return cand_b510(Omega, delta, t, n)


@functools.lru_cache(maxsize=None)
def _g511_c(Omega: float, alpha: float, t: float) -> float:
    return golden_b511(Omega, alpha, t)


@functools.lru_cache(maxsize=None)
def _c511_c(Omega: float, alpha: float, t: float, n: int) -> float:
    return cand_b511(Omega, alpha, t, n)


@functools.lru_cache(maxsize=None)
def _g512_c(Gamma: float, t: float) -> float:
    return golden_b512(Gamma, t)


@functools.lru_cache(maxsize=None)
def _c512_c(Gamma: float, t: float, n: int) -> float:
    return cand_b512(Gamma, t, n)


@functools.lru_cache(maxsize=None)
def _g513_c(f_q: float, f_s: float, z_ratio: float) -> float:
    return golden_b513(f_q, f_s, z_ratio)


@functools.lru_cache(maxsize=None)
def _c513_c(f_q: float, f_s: float, z_ratio: float, n: int) -> float:
    return cand_b513(f_q, f_s, z_ratio, n)


@functools.lru_cache(maxsize=None)
def _g514_c(eta_ratio: float, g: float, L: float) -> float:
    return golden_b514(eta_ratio, g, L)


@functools.lru_cache(maxsize=None)
def _c514_c(eta_ratio: float, g: float, L: float, n: int) -> float:
    return cand_b514(eta_ratio, g, L, n)


B510_DEFAULT_PARAMS = dict(_B510_DEFAULT)
B511_DEFAULT_PARAMS = dict(_B511_DEFAULT)
B512_DEFAULT_PARAMS = dict(_B512_DEFAULT)
B513_DEFAULT_PARAMS = dict(_B513_DEFAULT)
B514_DEFAULT_PARAMS = dict(_B514_DEFAULT)


#: 自检用例：bid, 物理参数（golden 键）
_CASES = (
    ("B510", _B510_DEFAULT),
    ("B511", _B511_DEFAULT),
    ("B512", _B512_DEFAULT),
    ("B513", _B513_DEFAULT),
    ("B514", _B514_DEFAULT),
)

_GOLDEN_BY_BID = {"B510": golden_b510, "B511": golden_b511, "B512": golden_b512,
                  "B513": golden_b513, "B514": golden_b514}
_CAND_BY_BID = {"B510": cand_b510, "B511": cand_b511, "B512": cand_b512,
                "B513": cand_b513, "B514": cand_b514}


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
    print("Batch J3 数值核自检（B510–B514 · 量子测控与读出征程 M0–M4）")
    print("=" * 72)
    bad = 0
    for bid, m in _measure_candidates().items():
        print("\n[%s] golden=%.12e  tol=%.1e  默认 n=%d" % (bid, m["golden"], m["tol"],
                                                          m["default_n"]))
        print("  判据 D 残差链：" +
              "  ".join("n=%d→%.3e" % (n, r) for n, r in m["chain"]))
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
        ):
            ok = bool(cond)
            bad += 0 if ok else 1
            print("    [%s] %s" % ("PASS" if ok else "FAIL", name))
    print("\n" + ("ALL PASS" if bad == 0 else "%d FAIL" % bad))
    raise SystemExit(0 if bad == 0 else 1)
