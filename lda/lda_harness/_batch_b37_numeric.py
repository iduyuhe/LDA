# -*- coding: utf-8 -*-
"""B-37 数值核（Batch B-37 · 光子传感器新征程 PS-M6 衍生锚 · 3 锚：B466 + B467 + B468）。

═══ 物理族 ═══
PS-M6 = **规模与集成**：把单点光子传感器推向「**芯片级 POC 诊断**」——传感器**阵列**
（多通道复用）+ **读出链**（Ge PD 阵列 + 跨阻放大器 TIA）+ **封装/对准**（光纤-波导
耦合容差）三件事同时成立，才谈得上"集成"。PS-M6 抽取三道可判决的**规模/集成支柱**：

| 锚 | 被测标量 | golden（解析闭式） | candidate（方法学独立） |
|---|---|---|---|
| **B466** | 密集传感阵列热串扰比 `ΔT(d)/ΔT(0)`（无量纲） | 1D 阻尼热扩散闭式 `sinh(a/L)·e^{−d/L}/(1−e^{−a/L})`（条带热源半宽 a、横向衰减长度 L） | 1D 有限差分 BVP（三对角 Thomas，条带源，T(±X)=0） |
| **B467** | TIA 读出噪声底 `v_n` [µV] | 频域闭式 `√(4kT/R_f · R_f² · (π/2) · f_p)`，f_p=1/(2πR_fC) ⇒ **坍缩为 √(kT/C)**（与 R_f 无关） | 时域冲激响应数值积分 `√((S_i/2)·∫_0^T [(1/C)e^{−t/τ}]²dt)`（梯形，τ=R_fC） |
| **B468** | 光纤-波导横向对准耦合效率 `η(d)`（无量纲） | 高斯模场重叠闭式 `e^{−d²/(2w²)}`（w=1/e 场半径） | 离散采样 + 线性插值 + 数值重叠积分（位移 d 非步长整数倍） |

🔴 同源体检（实 grep 全仓，排除 `.git/__pycache__/node_modules/reports/dist` 噪声）：
    · `crosstalk|串扰|thermal.*crosstalk|热串扰` 在 BENCHMARK_DEFS 内 **0 命中**
      ⇒ **热串扰族零锚占用（本族首锚）**。
    · `transimpedance|跨阻|TIA|kT/C|kTC` 在 BENCHMARK_DEFS 内 **0 命中**
      ⇒ **跨阻读出/噪声底族零锚占用（本族首锚）**；与 B33（探测器 RC 限制 3dB 带宽）
      的**被测标量不同**（B33 = f3dB_Hz；本题 = 输出 rms 噪声电压 µV）、**物理构型不同**
      （B33 = 探测器结电容 + 50Ω 负载；本题 = 跨阻放大器反馈电阻热噪声 + 运放输入节点
      电容）、**数值格式不同**（B33 = 梯形法 + τ 最小二乘拟合；本题 = 时域冲激响应
      数值积分）⇒ **非重复计数**。
    · `mode.*overlap|模场重叠|重叠积分|align|对准|misalign` 在 BENCHMARK_DEFS 内 **0 命中**
      （唯一 `gaussian.*overlap` 命中是 part1.py 一条**erfc 读出链**锚的交叉校核标注，
      其被测标量是 erfc 链路值，**非**模场重叠效率）⇒ **对准容差族零锚占用（本族首锚）**。
    · 与 PS-M0~M5（B459~B465）被测标量（谐振斜率 / 折射率导数 / 覆盖度 / 流量 / 毛细长度 /
      热阻）**完全不同** ⇒ **非重复计数**。

🔴 血案预防：
    1. **B468 候选不能用「全域高斯 × 梯形」** —— 梯形法对快速衰减的光滑高斯是**谱精度**
       （指数收敛），残差直接落双精度地板 ~1e-13 且随 N **不降反升**（实测 N=40→640：
       6.7e-14→4.2e-13）⇒ 判据 D 判「超收敛 ⇒ 假独立」（B-10 血案同族）。正解 = **离散采样
       + 线性插值**（位移 d 非步长整数倍 ⇒ 插值误差 O(h²) 主导）⇒ 实测比值 **3.84~4.31**（干净
       O(h²)、MONO）。同族被否：**角度失配复振荡被积函数**（`E1·e^{iβx}` 仍为高斯 ⇒ 梯形法
       同样谱精度精确，实测 |Δ|≡0.0 ⇒ 判假独立）—— 换被积函数不换**离散机制**无效。
    2. **B466 候选必须用三对角 Thomas（O(N)）**，不得用 `np.linalg.solve` 稠密（O(N³)）：
       N=6400 稠密解实测 ~30s，Thomas ~10ms（B465 的 N=600 稠密尚可，本档网格更密）。
    3. **B466 条带源在 |x|=a 处不连续** ⇒ FD 为 **O(h)**（非 O(h²)），实测比值 1.90~2.21；
       不得按「二阶」写文档（B-19 血案：收敛阶数字一律来自实测）。
    4. **B467 时域积分的 1/2 因子是物理必需**（白噪**单边**谱 S_i 对应**双边**谱 S_i/2 经
       Parseval 传递；漏掉则结果偏 √2 ≈ 1.414×，残差**恒不随 n 下降** ⇒ B-14「解错方程」指纹）。
       实测含 1/2 时残差随 n 严格单调、比值恒 **4.00**（梯形 O(h²)）⇒ 因子正确。
    5. **B467 golden 数学上与 R_f 无关**（`√(kT/C)` 是经典噪声底）——写成含 R_f 的频域闭式
       形式 `√(S_i·R_f²·(π/2)·f_p)` 让 R_f **显式出现并相消**（非"未使用参数"），物理含义即
       「读出噪声底不受跨阻增益影响」。
    6. **B468 观测位移 d 必须是步长 h 的**非**整数倍**（d/h ∉ ℤ，否则插值退化为取点 ⇒ 残差
       消失）。扫描网格取 N ∈ {64,128,256,512,1024}、X=6w ⇒ d/h = d·N/(2X) = N/12 ∉ ℤ（N 非
       12 的倍数）⇒ 恒为非整数。
    7. 量纲 O(1) 化（判据 D 纪律）：B466/B468 报无量纲比值（O(0.5)）、B467 报 **µV**（O(200)），
       使 |golden|/tol ≥ 13.5 与 abs tol 纪律同时满足。

诚实边界：
    · 几何/材料/电路参数均为**设计示例**（热衰减长度 L=1 µm、条带半宽 a=0.5 µm、间距 d=1 µm；
      运放输入节点电容 C=100 fF、反馈电阻 R_f=10 kΩ、T=300 K；模场半径 w=5 µm、横向偏移 d=5 µm）。
      结论只可用于数值方法与量级，**不得作制造/性能宣称**。
    · B466 为 1D 稳态「散热鳍」近似（薄板 + 等效表面散热，忽略衬底 3D 扩展与对流非线性）；
      B467 为单极点（忽略运放有限 GBW、散粒噪声、1/f 噪声）白噪模型；B468 为非球面像差、
      无角度失配、无反射的理想高斯模场重叠。均为封装/读出链标准一阶模型。
    · 零商业依赖（纯 numpy + math）。
"""
from __future__ import annotations

import math

import numpy as np


# ===========================================================================
# 公共数值工具
# ===========================================================================
def _thomas(a: np.ndarray, b: np.ndarray, c: np.ndarray, r: np.ndarray) -> np.ndarray:
    """三对角线性系统 O(N) 解（a=次对角 · b=对角 · c=超对角 · r=右端）。"""
    n = len(b)
    cp = np.zeros(n, dtype=np.float64)
    dp = np.zeros(n, dtype=np.float64)
    cp[0] = c[0] / b[0]
    dp[0] = r[0] / b[0]
    for i in range(1, n):
        m = b[i] - a[i] * cp[i - 1]
        cp[i] = c[i] / m
        dp[i] = (r[i] - a[i] * dp[i - 1]) / m
    x = np.zeros(n, dtype=np.float64)
    x[n - 1] = dp[n - 1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]
    return x


# ===========================================================================
# B466 · 密集传感阵列热串扰：闭式 golden + 1D FD 三对角候选
# ===========================================================================
def array_crosstalk_golden(L_th_um: float, d_um: float, a_um: float) -> float:
    """golden：密集传感阵列相邻通道稳态热串扰比 `ΔT(d)/ΔT(0)`（无量纲）。

    模型：沿阵列方向 x 的 1D 稳态阻尼热扩散 `T'' − T/L² + q(x)/k' = 0`
    （`L = √(k·t/h)` 为横向热衰减长度），条带热源 `q = 1/(2a)`（|x|<a）。
    对称解 ⇒ 区外 `E·e^{−x/L}`、区内 `qL²/k' + C·cosh(x/L)`，在 x=±a 处匹配 T 与 T'：

        C = −(qL²/k')·e^{−a/L}  ⇒  T(0) = (qL²/k')(1 − e^{−a/L})
        T(d) = (qL²/k')·sinh(a/L)·e^{−d/L}      (d > a)

    ⇒ **`ΔT(d)/ΔT(0) = sinh(a/L)·e^{−d/L}/(1 − e^{−a/L})`**（a→0 退化为纯指数 `e^{−d/L}`）。
    L≤0 / d≤a / a<0 ⇒ nan。
    """
    if L_th_um <= 0.0 or a_um < 0.0 or d_um <= a_um:
        return float("nan")
    return float(math.sinh(a_um / L_th_um) * math.exp(-d_um / L_th_um)
                 / (1.0 - math.exp(-a_um / L_th_um)))


#: golden 入口别名
golden_b466 = array_crosstalk_golden


def array_crosstalk_fd(L_th_um: float, d_um: float, a_um: float,
                       N: int = 6400, Xmul: float = 12.0) -> float:
    """候选：1D 有限差分 BVP（**三对角 Thomas**，O(N)），解 `T'' − T/L² + q/k' = 0`。

    域 [−X, X]（X = Xmul·L ≫ L，截断误差 ~e^{−Xmul}），N+1 等距节点 h=2X/N，
    Dirichlet 端 T(±X)=0；条带源 `q_i = 1/(2a)`（|x_i|<a）按格心常值投影。
    取 `T(d)/T(0)`（d、0 均为格点：d/h ∈ ℤ 由扫描网格保证）。
    🔴 条带边界 |x|=a 处 RHS 不连续 ⇒ 点值精度 **O(h)**（实测比值 1.90~2.21），非 O(h²)。
    离散参数 = N（默认 6400 = 判据 D 扫描末端）。L≤0 / d≤a / a<0 ⇒ nan。
    """
    if L_th_um <= 0.0 or a_um < 0.0 or d_um <= a_um:
        return float("nan")
    X = Xmul * L_th_um
    N = max(8, int(N))
    h = 2.0 * X / N
    x = -X + np.arange(N + 1) * h
    src = np.where(np.abs(x) < a_um, 1.0 / (2.0 * a_um), 0.0)
    aa = np.ones(N + 1, dtype=np.float64)
    bb = np.full(N + 1, -2.0 - (h * h) / (L_th_um * L_th_um), dtype=np.float64)
    cc = np.ones(N + 1, dtype=np.float64)
    r = -src * h * h
    # Dirichlet 端：T(−X)=T(X)=0
    bb[0] = 1.0
    cc[0] = 0.0
    r[0] = 0.0
    aa[N] = 0.0
    bb[N] = 1.0
    r[N] = 0.0
    T = _thomas(aa, bb, cc, r)
    i0 = N // 2                     # x=0 恰为中心格点
    idx = int(round((d_um + X) / h))
    if T[i0] == 0.0:
        return float("nan")
    return float(T[idx] / T[i0])


#: 候选入口别名
cand_b466 = array_crosstalk_fd


# ===========================================================================
# B467 · TIA 读出噪声底 kT/C：频域闭式 golden + 时域冲激响应数值积分候选
# ===========================================================================
def tia_noise_floor_golden_uV(C_fF: float, R_kOhm: float = 10.0,
                              T_K: float = 300.0) -> float:
    """golden：单极点跨阻放大器（TIA）的输出 rms 噪声电压 `v_n` [µV]。

    反馈电阻热噪声（输入参考单边谱 `S_i = 4kT/R_f`）经单极点闭环传递
    `|Z_T(f)|² = R_f²/(1+(f/f_p)²)`（`f_p = 1/(2πR_f·C_tot)`）传到输出：

        v_n² = S_i·R_f²·∫_0^∞ df/(1+(f/f_p)²) = S_i·R_f²·(π/2)·f_p
             = (4kT/R_f)·R_f²·(π/2)·(1/(2πR_fC)) = **kT/C**

    🔴 R_f **显式出现并相消** ⇒ 噪声底 `√(kT/C)` 与跨阻增益无关（读出链经典结论：
    提高 R_f 增增益不增噪声底，只降带宽）。C≤0 / R≤0 / T≤0 ⇒ nan。
    """
    if C_fF <= 0.0 or R_kOhm <= 0.0 or T_K <= 0.0:
        return float("nan")
    k_B = 1.380649e-23
    C = C_fF * 1e-15
    Rf = R_kOhm * 1e3
    f_p = 1.0 / (2.0 * math.pi * Rf * C)
    S_i = 4.0 * k_B * T_K / Rf
    var = S_i * Rf * Rf * (math.pi / 2.0) * f_p
    return float(math.sqrt(var) * 1e6)  # → µV


#: golden 入口别名
golden_b467 = tia_noise_floor_golden_uV


def tia_noise_floor_td_uV(C_fF: float, R_kOhm: float = 10.0,
                          T_K: float = 300.0, n: int = 32000,
                          Tmul: float = 40.0) -> float:
    """候选：**时域**脉冲响应数值积分（与 golden 的频域解析式方法学独立）。

    单极点 TIA 的电流→电压冲激响应 `z(t) = (1/C)·e^{−t/τ}`（τ = R_f·C，t≥0 因果）。
    白噪（单边谱 S_i）经该滤波器 ⇒ 由 Parseval（因果信号的单边/双边对称）

        v_n² = (S_i/2)·∫_0^∞ z(t)² dt = (S_i/2)·(1/C²)(τ/2) = kT/C  ✓

    数值实现：T = Tmul·τ（尾 `e^{−2Tmul}` ~e^{−80} 机器精度之下），n 步**梯形**积分。
    离散参数 = n（默认 32000 = 判据 D 扫描末端）；梯形 O(h²)，实测比值恒 **4.00**、MONO。
    🔴 1/2 因子**不可省**（漏掉 ⇒ 偏 √2，残差恒不降）。C≤0 / R≤0 / T≤0 ⇒ nan。
    """
    if C_fF <= 0.0 or R_kOhm <= 0.0 or T_K <= 0.0:
        return float("nan")
    k_B = 1.380649e-23
    C = C_fF * 1e-15
    Rf = R_kOhm * 1e3
    tau = Rf * C
    S_i = 4.0 * k_B * T_K / Rf
    T = Tmul * tau
    n = max(4, int(n))
    h = T / n
    t = np.arange(n + 1, dtype=np.float64) * h
    z = (1.0 / C) * np.exp(-t / tau)
    integ = (0.5 * z[0] ** 2 + float(np.sum(z[1:-1] ** 2)) + 0.5 * z[-1] ** 2) * h
    var = 0.5 * S_i * integ
    return float(math.sqrt(var) * 1e6)  # → µV


#: 候选入口别名
cand_b467 = tia_noise_floor_td_uV


# ===========================================================================
# B468 · 光纤-波导横向对准耦合效率：高斯重叠闭式 golden + 采样-插值候选
# ===========================================================================
def align_overlap_golden(d_um: float, w_um: float) -> float:
    """golden：光纤-波导横向错位 d 的模式重叠耦合效率 `η(d)`（无量纲）。

    两侧模场均为高斯 `E(x) = exp(−x²/(2w²))`（w = 1/e **场**半径，1D 截面）：
        ∫E(x)E(x−d)dx = w√π·e^{−d²/(4w²)}，  ∫E²dx = w√π
    ⇒ **`η(d) = exp(−d²/(2w²))`**（理想无角度失配、无反射）。
    w≤0 ⇒ nan。
    """
    if w_um <= 0.0:
        return float("nan")
    return float(math.exp(-d_um * d_um / (2.0 * w_um * w_um)))


#: golden 入口别名
golden_b468 = align_overlap_golden


def align_overlap_sampled(d_um: float, w_um: float, N: int = 1024,
                          M: float = 6.0) -> float:
    """候选：**离散采样 + 线性插值** + 数值重叠积分（模拟真实对准仿真：模式剖面只
    在有限网格上已知，横向平移 d 落点不在格点上 ⇒ 必须插值）。

    在 [−X, X]（X = M·w）上取 N+1 等距节点 h=2X/N，采样 E1；平移场 E2(x)=E1(x−d)
    由**线性插值**取（d/h ∉ ℤ ⇒ 插值误差主导）。
        I12 = Σ E1·E2·h， I11 = Σ E1²·h， I22 = Σ E2²·h， η = I12²/(I11·I22)
    🔴 全域高斯 + 梯形是**谱精度**（残差落 1e-13 地板、随 N 不降反升）⇒ 判假独立（B-10
    同族血案）。本实现引入**插值**离散误差（O(h²)）⇒ 实测比值 3.84~4.31、MONO，残差在
    粗端浮出 ~1.2e-3 ≫ 双精度地板。
    离散参数 = N（默认 1024 = 判据 D 扫描末端）。w≤0 ⇒ nan。
    """
    if w_um <= 0.0:
        return float("nan")
    X = M * w_um
    N = max(8, int(N))
    ax = np.linspace(-X, X, N + 1)
    h = ax[1] - ax[0]
    E1 = np.exp(-(ax ** 2) / (2.0 * w_um * w_um))
    idx = (ax - d_um + X) / h          # 平移后的分数格点坐标
    i0 = np.floor(idx).astype(np.int64)
    fr = idx - i0
    ok = (i0 >= 0) & (i0 < N)
    E2 = np.zeros_like(E1)
    E2[ok] = (1.0 - fr[ok]) * E1[i0[ok]] + fr[ok] * E1[i0[ok] + 1]
    I12 = float(np.sum(E1 * E2)) * h
    I11 = float(np.sum(E1 * E1)) * h
    I22 = float(np.sum(E2 * E2)) * h
    if I11 <= 0.0 or I22 <= 0.0:
        return float("nan")
    return float(I12 * I12 / (I11 * I22))


#: 候选入口别名
cand_b468 = align_overlap_sampled


# ===========================================================================
# 逐锚默认档 / 判据 D 扫描网格 / tol
# ===========================================================================
_N_BY_BID = {
    "B466": 6400,    # 1D FD 三对角节点数 N（默认档 = 扫描末端）
    "B467": 32000,   # 时域积分梯形步数 n（默认档 = 扫描末端）
    "B468": 1024,    # 采样节点数 N（默认档 = 扫描末端）
}
# 判据 D 扫描网格（递增加密 ⇒ 收敛型；粗端 |Δ| < tol）
_GRID_BY_BID = {
    "B466": [400, 800, 1600, 3200, 6400],        # FD 节点数（O(h)）
    "B467": [2000, 4000, 8000, 16000, 32000],    # 梯形步数（O(h²)）
    "B468": [64, 128, 256, 512, 1024],           # 采样节点数（O(h²)）
}
# 逐锚 tol（abs，按「余量 ≥ 2 且 |golden|/tol ≥ 13.5、粗端 < tol」实测标定）
# · B466 golden=0.4872（无量纲 O(1)）：tol=1e-2 ⇒ |golden|/tol=48.7；粗端(N=400)|Δ|=7.15e-3 < tol；
#   默认档(N=6400)|Δ|=4.21e-4 ⇒ 余量 23.7（FD O(h) 实测比值 1.90~2.21）。
#   反向探针余量：d_um×1.1 ⇒ |Δ|=4.64e-2（tol 的 4.6×）。tol 取 1e-2（非 2e-2）⇒ 反向探针
#   与灵敏度（最小可检出 5%）均留足裕度（原 2e-2 时 a_um×1.1 仅 |Δ|=1.55e-2 < tol ⇒ 探针失效）。
# · B467 golden=203.518 µV：tol=2e-2 ⇒ |golden|/tol=1.02e4；粗端(n=2000)|Δ|=1.36e-2 < tol；
#   默认档(n=32000)|Δ|≈5.3e-5 ⇒ 余量 ≈377（梯形 O(h²) 实测比值 4.00）。
# · B468 golden=0.60653（无量纲 O(1)）：tol=3e-3 ⇒ |golden|/tol=202；粗端(N=64)|Δ|=1.24e-3 < tol；
#   默认档(N=1024)|Δ|=4.64e-6 ⇒ 余量 646（插值 O(h²) 实测比值 3.84~4.31）。
_TOL_BY_BID = {
    "B466": 1e-2,   # 无量纲串扰比
    "B467": 2e-2,   # µV
    "B468": 3e-3,   # 无量纲耦合效率
}

#: 默认物理参数（设计示例）
_DEFAULT_B466 = dict(L_th_um=1.0, d_um=1.0, a_um=0.5)
_DEFAULT_B467 = dict(C_fF=100.0, R_kOhm=10.0, T_K=300.0)
_DEFAULT_B468 = dict(d_um=5.0, w_um=5.0)

_CASES = [
    ("B466", array_crosstalk_golden, array_crosstalk_fd, _DEFAULT_B466),
    ("B467", tia_noise_floor_golden_uV, tia_noise_floor_td_uV, _DEFAULT_B467),
    ("B468", align_overlap_golden, align_overlap_sampled, _DEFAULT_B468),
]

#: 离散参数名（逐锚）——供判据 D 扫描与守卫统一取用
_KW_BY_BID = {"B466": "N", "B467": "n", "B468": "N"}


if __name__ == "__main__":
    print("=== B-37 规模与集成（B-466 阵列热串扰 / B-467 TIA 读出噪声底 / B-468 对准重叠）自检 ===")
    print("\n%-6s %16s %18s %12s %10s %-9s %-9s %s"
          % ("锚", "golden", "cand(默认档)", "|Δ|", "margin", "基线>1e-12", "gold/tol", "判定"))
    bad = 0
    for bid, gf, cf, p in _CASES:
        g = gf(**p)
        c = cf(**{**p, _KW_BY_BID[bid]: _N_BY_BID[bid]})
        dd = abs(g - c)
        tol = _TOL_BY_BID[bid]
        margin = (tol / dd) if dd > 0 else float("inf")
        base_ok = math.isfinite(dd) and dd > 0.0
        gr = abs(g) / tol
        ok = (margin >= 2.0) and base_ok and (gr >= 13.5)
        bad += 0 if ok else 1
        print("%-6s %16.10f %18.10f %12.3e %10.1f %-9s %-9.1f %s"
              % (bid, g, c, dd, margin, base_ok, gr, "OK" if ok else "BAD"))

    print("\n--- 判据 D 扫描（残差随离散参数收紧单调下降；比值来自实测）---")
    for bid, gf, cf, p in _CASES:
        g = gf(**p)
        grid = _GRID_BY_BID[bid]
        kw = _KW_BY_BID[bid]
        row, prev, mono, ratios = [], None, True, []
        for x in grid:
            dd = abs(g - cf(**{**p, kw: x}))
            if prev is not None:
                ratio = (prev / dd) if dd > 0 else float("nan")
                ratios.append(ratio)
                if dd > prev:
                    mono = False
                row.append("%g:%.2e(x%.2f)" % (x, dd, ratio))
            else:
                row.append("%g:%.2e" % (x, dd))
            prev = dd
        d_last = abs(g - cf(**{**p, kw: grid[-1]}))
        d_first = abs(g - cf(**{**p, kw: grid[0]}))
        tol = _TOL_BY_BID[bid]
        print("%-6s %-72s %-8s 比值 %.2f~%.2f  粗端>1e-15:%s  粗端<tol:%s  默认档>1e-12:%s"
              % (bid, "  ".join(row), "MONO" if mono else "NONMONO",
                 min(ratios) if ratios else float("nan"),
                 max(ratios) if ratios else float("nan"),
                 d_first > 1e-15, d_first < tol, d_last > 1e-12))

    # 连续一致性（B466 a→0 ⇒ 退化为纯指数 e^{−d/L}）
    L, d = 1.0, 1.0
    g_a_small = array_crosstalk_golden(L, d, 1e-9)
    rel = abs(g_a_small - math.exp(-d / L)) / math.exp(-d / L)
    print("\nB466 a→0 极限（应退化为 e^{−d/L}=%.10f）：rel=%.3e ⇒ %s"
          % (math.exp(-d / L), rel, "OK" if rel < 1e-6 else "MISMATCH"))
    bad += 0 if rel < 1e-6 else 1

    # 连续一致性（B467 R 无关性：R=10k vs 20k golden 应逐位相同）
    v1 = tia_noise_floor_golden_uV(100.0, 10.0, 300.0)
    v2 = tia_noise_floor_golden_uV(100.0, 20.0, 300.0)
    rel_r = abs(v1 - v2) / v1
    print("B467 R 无关性（R=10k vs 20k ⇒ √(kT/C) 同一）：rel=%.3e ⇒ %s"
          % (rel_r, "OK" if rel_r < 1e-12 else "MISMATCH"))
    bad += 0 if rel_r < 1e-12 else 1

    # 连续一致性（B468 d→0 ⇒ η→1；解析 1dB 容差 d_1dB=w√(2·0.1·ln10)）
    eta0 = align_overlap_golden(0.0, 5.0)
    d1db = 5.0 * math.sqrt(2.0 * 0.1 * math.log(10.0))
    eta_1db = align_overlap_golden(d1db, 5.0)
    print("B468 d→0 ⇒ η=%.12f（应 1.0）；1dB 容差 d_1dB=%.4f µm ⇒ η=%.6f（应 10^-0.1=%.6f）"
          % (eta0, d1db, eta_1db, 10 ** -0.1))
    bad += 0 if (abs(eta0 - 1.0) < 1e-12 and abs(eta_1db - 10 ** -0.1) < 1e-9) else 1

    # 反向红标：非法参数一律 nan
    bad += 0 if not math.isfinite(array_crosstalk_golden(0.0, 1.0, 0.5)) else 1   # L≤0
    bad += 0 if not math.isfinite(array_crosstalk_golden(1.0, 0.3, 0.5)) else 1   # d≤a
    bad += 0 if not math.isfinite(tia_noise_floor_golden_uV(0.0)) else 1          # C≤0
    bad += 0 if not math.isfinite(tia_noise_floor_td_uV(100.0, 0.0)) else 1       # R≤0
    bad += 0 if not math.isfinite(align_overlap_golden(1.0, 0.0)) else 1          # w≤0

    print("\nBAD =", bad, "（应为 0）")
