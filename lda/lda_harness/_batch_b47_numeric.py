"""Batch B-47 数值实现 · 量子传感器芯片征程 QS-M9（光泵原子磁力计 OPM / SERF · 腿 C）。

════════════════════════════════════════════════════════════════════════════
本批**三锚**（`benchmark_defs/part7.py` 引用）——

  B491：**光抽运关闭后的自由进动横向极化** P_x(t*)
        golden   = 闭式 **P_x(t) = P₀·e^(−R_tot·t)·cos(2π·γ_e·B·t)**（2D 线性 Bloch
                   方程的**精确解** · 自由感应衰减 FID 信号）。
        candidate = **RK4 时间推进 2D Bloch 方程**（固定步长 h = t*/n，不含任何
                   解析指数/余弦成分）。
        ——方法学独立：golden 走「精确闭式」；candidate 走「数值时间推进」。
        🔴 实测 rel 链 2.77e-6 → 1.78e-7 → 1.13e-8 → **7.07e-10**（比值 ~16×/倍增
        ⇒ **O(h⁴)**，与 RK4 标称阶一致）⇒ **非代数恒等**。

  B492：**碱金属（Rb）饱和蒸气数密度** n(T)
        golden   = 闭式 **n(T) = n_ref·exp(−(ΔH/k_B)·(1/T − 1/T_ref))**（m⁻³ ·
                   Clausius–Clapeyron 常数汽化焓模型）。
        candidate = **复合梯形数值积分** `d(ln n)/dT = ΔH/(k_B·T²)`。
        ——方法学独立：golden 走「闭式指数」；candidate 走「数值求积」。
        🔴 实测 rel 链 3.01e-6 → 7.53e-7 → 1.88e-7 → **4.71e-8**（比值 **4.00×**
        ⇒ **O(h²)**，梯形标称阶一致）⇒ **非代数恒等**（被积函数 A/T² **非常数**
        ⇒ **非剖分守恒**，与 B28「均匀段剖分守恒」型恒等不同 ⇒ 反向探针确证）。

  B493：**泵浦光在碱金属气室中的 Beer–Lambert 透过率** T(L)
        golden   = 闭式 **T(L) = T₀·exp(−n·σ_abs·L)**（无量纲 · 光学厚度 τ=nσL）。
        candidate = **RK4 沿 z 数值积分** `dI/dz = −n·σ_abs·I`。
        ——方法学独立：golden 走「闭式指数」；candidate 走「数值空间推进」。
        🔴 实测 rel 链 2.26e-6 → 1.34e-7 → 8.16e-9 → **5.03e-10**（比值 ~16.4×
        ⇒ **O(h⁴)**）⇒ **非代数恒等**。

🔴 物理意义（承 QS-M9 蓝图层 §QS-M9 · 平台缺口 G11「多物理场量子传感整合」）：
  · **B491（自由进动横向极化）**：OPM 的**时域信号本体** —— 光抽运建立极化，
    静磁场下自由进动 ⇒ 横向极化按自旋相关时间 1/R_tot 衰减、按 Larmor 频率振荡。
    本锚把「光-自旋-磁」三场耦合的时域响应钉进账本（腿 C 的信号链）。
  · **B492（碱金属数密度）**：气室的**温度 → 密度**定标律 —— N_a 是自旋投影噪声
    的分母（N_a ↑ ⇒ 灵敏度 ↑），也是光抽运/弛豫速率的核心输入 ⇒ 多物理场
    「热-几何-自旋」耦合的第一环。本锚把它钉进账本。
  · **B493（泵浦光吸收）**：气室的**光路**物理 —— 光学厚度决定抽运均匀性与
    探测信噪比的权衡 ⇒ 多物理场「光-几何」耦合。本锚把它钉进账本。

🔴 与既有锚的边界（**不同物理量**，非重复计数）：
  · B473–B484（腿 A NV 色心 · 固体单自旋）：ODMR/Ramsey 换能与固体几何；本批是
    **碱金属蒸气集合自旋**的光抽运/FID/气室热力学/光路吸收 ⇒ 物理对象与换能机制
    均不同。
  · B485–B490（腿 B 超导 SQUID）：电-磁通宏观量子相位；本批是光-自旋。
  · B475（自旋回波相位方差 · 时间域数值积分）：**回波序列的相位方差**（退相干谱）；
    B491 是**自由进动的横向极化分量** ⇒ 被测标量不同（相位方差 vs 极化）且构型不同
    （脉冲序列 vs 自由进动）⇒ 记新锚（先例 B452 vs B33：同为 RC 一阶暂态而三处分歧）。
  · B452（驱动器一阶 RC 阶跃 · RK4）：本批 B491/B493 同为 RK4，但**被测标量**
    （横向极化 / 透过率 vs 电压）、**物理构型**（碱金属气室自旋进动 / 光吸收 vs RC
    驱动电路）、**是否含振荡解**（B491 是衰减振荡的 2D 耦合系统，B452 是 1D 单调）
    三者有分歧 ⇒ 记新锚（同上先例）。
  · B462（Langmuir 吸附 RK4）/B464（Washburn 后向欧拉）：非光抽运体系。
  · B488（离散 Neumann 互感 · 圆环离散）：本批**不含线圈磁场锚**（亥姆霍兹线圈
    B(0) 是闭式算术 ⇒ 归 `run_qs_m9_smoke` 覆盖，**如实不登记**）。

🔴 **为何只三锚（诚实规模 · 吃狗粮）**：QS-M9 另含
  · 「稳态极化 P∞ = R_op/(R_op+R_sd)」（**速率方程稳态** ⇒ 属 smoke）；
  · 「亥姆霍兹线圈 B(0) = (4/5)^{3/2}µ₀NI/R」（**闭式算术** ⇒ 属 smoke）；
  · 「自旋破坏率 = 壁 + 缓冲气体 + 探测光」（**定义式求和** ⇒ 属 smoke）；
  · 「SERF 灵敏度 η = √(R_tot/N_a)/(2πγ_e·P∞)」（**闭式整合标量**：其自旋投影噪声
    因子 √(1/N_a) 的**统计本质无可行数值候选** —— 任何 MC 都需模拟 N_a≈1e13 个
    独立自旋，不可行 ⇒ **如实不登记为锚**，改由 `run_qs_m9_smoke` 覆盖其
    单调性/量级/与三腿对照）；
  · 「P∞ → 1（R_sd→0）」「n(T_ref) = n_ref」「τ_opt = 1 ⇒ T = 1/e」等**极限/自洽点**
    （⇒ 属 smoke）。
  ⇒ 本批**如实只登记 B491–B493 三锚**（同 Batch B-44/B-45/B-46 三锚纪律：
  **宁可少，不越级谎报**）。

🔴 纪律：
· 本模块**顶层只 import math**（本批三锚全为标量闭式/标量数值 ⇒ **无 numpy / scipy 依赖**）。
· golden 与 candidate 是**两种结构不同的算法**（非「同式异写」）；进报告数字一律**现算**。
· 🔴 **锚携带可扰动参数**（各 `B49*_DEFAULT_PARAMS`）：参数对输出强敏感、无零响应键
  ⇒ 反自证桩护栏 `candidate_responds` 可证伪。
· 🔴 **默认档 = 判据 D 扫描网格末端**（纪律：定档必须 = 扫描网格最大档）。
"""
from __future__ import annotations

import functools
import math

# 物理常数（与 lda_l2.qs_m9 同源 · 门禁 `run_qs_m9_smoke` B 节跨源对拍）
_GAMMA_RB_HZ_T = 6.995e9
_DH_OVER_KB_RB_K = 8384.0


# ===========================================================================
# 默认档 / 判据 D 扫描网格 / 逐锚 tol（三表 · 单一出处）
# ===========================================================================
# 🔴 默认档 = 扫描网格**末端**（纪律：定档必须 = 判据 D 扫描最大档）
_N_BY_BID = {
    "B491": 64,
    "B492": 256,
    "B493": 64,
}
# 判据 D 扫描网格（4 档等比 ×2）
_GRID_BY_BID = {
    "B491": [8, 16, 32, 64],
    "B492": [32, 64, 128, 256],
    "B493": [8, 16, 32, 64],
}
# 逐锚 tol（**绝对口径** · 与本仓 `compare_fn` 约定一致；按「余量 ≥100× 且
# |golden| ≥ 13.5×tol」标定；tol 只收紧不放松）
# 🔴 实测默认档 |Δ|：B491 2.475e-10（tol 1e-7 ⇒ 404×）· B492 2.349e10（**tol 5e12**
#    ⇒ 213×，对 |golden|≈4.99e17 即相对 1.0e-5 —— 同 B486「量级标定」先例）
#    · B493 1.851e-10（tol 1e-7 ⇒ 540×）
_TOL_BY_BID = {
    "B491": 1e-7,
    "B492": 5e12,
    "B493": 1e-7,
}


# ===========================================================================
# B491 · 自由进动横向极化 P_x(t*)：闭式精确解 ⇄ RK4 时间推进 2D Bloch
# ===========================================================================
def fid_polarization_golden(p0: float, r_tot_s1: float, b_t: float,
                            t_s: float) -> float:
    """golden：闭式 **P_x(t) = P₀·e^(−R_tot·t)·cos(2π·γ_e·B·t)**（无量纲）。

    🔴 物理：光抽运关闭后（或弱抽运下）自旋在静磁场 B 中**自由进动**，Bloch 方程
      dP_x/dt = −R_tot·P_x − ω_L·P_y ,  dP_y/dt = −R_tot·P_y + ω_L·P_x
    在初值 (P₀, 0) 下的**精确解**（ω_L = 2π·γ_e·B）⇒ 可作 golden（不含近似）。
    """
    if p0 <= 0.0:
        raise ValueError("p0 必须 > 0")
    if r_tot_s1 <= 0.0:
        raise ValueError("r_tot_s1 必须 > 0")
    if t_s <= 0.0:
        raise ValueError("t_s 必须 > 0")
    w = 2.0 * math.pi * _GAMMA_RB_HZ_T * b_t
    return float(p0 * math.exp(-r_tot_s1 * t_s) * math.cos(w * t_s))


def fid_polarization_candidate(p0: float, r_tot_s1: float, b_t: float,
                               t_s: float, n_steps: int = 64) -> float:
    """candidate：**RK4 时间推进 2D Bloch 方程**（方法学独立 · 无解析成分）。

    固定步长 h = t*/n_steps，四阶经典 Runge–Kutta 逐点推进，取 t* 处 P_x。
    🔴 残差来源 = **时间离散化截断**（实测 O(h⁴)，比值 ~16×/倍增）⇒ **非**代数恒等
    （n_steps=8 ⇒ 残差放大 ~4000×，反向探针确证）。
    """
    if p0 <= 0.0 or r_tot_s1 <= 0.0 or t_s <= 0.0:
        raise ValueError("p0/r_tot/t_s 必须 > 0")
    if n_steps < 4:
        raise ValueError("n_steps 必须 ≥ 4")
    w = 2.0 * math.pi * _GAMMA_RB_HZ_T * b_t
    h = t_s / int(n_steps)
    x, y = float(p0), 0.0
    for _ in range(int(n_steps)):
        k1x, k1y = -r_tot_s1 * x - w * y, -r_tot_s1 * y + w * x
        x2, y2 = x + 0.5 * h * k1x, y + 0.5 * h * k1y
        k2x, k2y = -r_tot_s1 * x2 - w * y2, -r_tot_s1 * y2 + w * x2
        x3, y3 = x + 0.5 * h * k2x, y + 0.5 * h * k2y
        k3x, k3y = -r_tot_s1 * x3 - w * y3, -r_tot_s1 * y3 + w * x3
        x4, y4 = x + h * k3x, y + h * k3y
        k4x, k4y = -r_tot_s1 * x4 - w * y4, -r_tot_s1 * y4 + w * x4
        x += (h / 6.0) * (k1x + 2.0 * k2x + 2.0 * k3x + k4x)
        y += (h / 6.0) * (k1y + 2.0 * k2y + 2.0 * k3y + k4y)
    return float(x)


# ===========================================================================
# B492 · 碱金属饱和蒸气数密度 n(T)：闭式指数 ⇄ 复合梯形数值积分
# ===========================================================================
def alkali_density_golden(n_ref_m3: float, t_ref_k: float, dh_over_kb_k: float,
                          t_k: float) -> float:
    """golden：闭式 **n(T) = n_ref·exp(−(ΔH/k_B)·(1/T − 1/T_ref))**（m⁻³）。"""
    if n_ref_m3 <= 0.0 or t_ref_k <= 0.0 or t_k <= 0.0:
        raise ValueError("n_ref / t_ref / t_k 必须 > 0")
    if dh_over_kb_k <= 0.0:
        raise ValueError("dh_over_kb_k 必须 > 0")
    return float(n_ref_m3 * math.exp(-dh_over_kb_k
                                     * (1.0 / t_k - 1.0 / t_ref_k)))


def alkali_density_candidate(n_ref_m3: float, t_ref_k: float,
                             dh_over_kb_k: float, t_k: float,
                             n_seg: int = 256) -> float:
    """candidate：**复合梯形数值积分** `d(ln n)/dT = ΔH/(k_B·T²)`（方法学独立）。

    🔴 残差来源 = **梯形求积截断**（实测 O(h²)，比值 **4.00×**/倍增）。
    🔴 被积函数 A/T² **非常数** ⇒ **非剖分守恒** ⇒ 与 B28「均匀段 ΣΓ·Δz ≡ ΓL
    剖分守恒」型代数恒等**不同**（n_seg=32 ⇒ 残差放大 ~64×，反向探针确证）。
    """
    if n_ref_m3 <= 0.0 or t_ref_k <= 0.0 or t_k <= 0.0:
        raise ValueError("n_ref / t_ref / t_k 必须 > 0")
    if dh_over_kb_k <= 0.0:
        raise ValueError("dh_over_kb_k 必须 > 0")
    if n_seg < 4:
        raise ValueError("n_seg 必须 ≥ 4")
    h = (t_k - t_ref_k) / int(n_seg)
    acc = 0.0
    for i in range(int(n_seg)):
        ta = t_ref_k + i * h
        tb = ta + h
        acc += 0.5 * h * (dh_over_kb_k / (ta * ta) + dh_over_kb_k / (tb * tb))
    return float(n_ref_m3 * math.exp(acc))


# ===========================================================================
# B493 · 泵浦光 Beer–Lambert 透过率 T(L)：闭式指数 ⇄ RK4 空间推进
# ===========================================================================
def pump_transmission_golden(trans0: float, n_density_m3: float,
                             sigma_abs_m2: float, length_m: float) -> float:
    """golden：闭式 **T(L) = T₀·exp(−n·σ_abs·L)**（无量纲 · Beer–Lambert）。"""
    if trans0 <= 0.0:
        raise ValueError("trans0 必须 > 0")
    if n_density_m3 < 0.0 or sigma_abs_m2 < 0.0:
        raise ValueError("n / σ 必须 ≥ 0")
    if length_m <= 0.0:
        raise ValueError("length_m 必须 > 0")
    return float(trans0 * math.exp(-n_density_m3 * sigma_abs_m2 * length_m))


def pump_transmission_candidate(trans0: float, n_density_m3: float,
                                sigma_abs_m2: float, length_m: float,
                                n_steps: int = 64) -> float:
    """candidate：**RK4 沿 z 数值积分** `dI/dz = −n·σ_abs·I`（方法学独立）。

    🔴 残差来源 = **空间离散化截断**（实测 O(h⁴)，比值 ~16.4×/倍增）。
    """
    if trans0 <= 0.0 or length_m <= 0.0:
        raise ValueError("trans0 / length_m 必须 > 0")
    if n_steps < 4:
        raise ValueError("n_steps 必须 ≥ 4")
    alpha = n_density_m3 * sigma_abs_m2
    h = length_m / int(n_steps)
    i_val = float(trans0)
    for _ in range(int(n_steps)):
        k1 = -alpha * i_val
        k2 = -alpha * (i_val + 0.5 * h * k1)
        k3 = -alpha * (i_val + 0.5 * h * k2)
        k4 = -alpha * (i_val + h * k3)
        i_val += (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return float(i_val)


# ===========================================================================
# 锚的物理设计参数（default_params 真源 · 单一出处）
# ===========================================================================
#: 🔴 `default_params` 的键集 **⊆ golden 形参集**（血案：多键会让 golden_value 抛 TypeError）
B491_DEFAULT_PARAMS = {
    "p0": 1.0,            # FID 初始横向极化（非零 ⇒ 响应）
    "r_tot_s1": 300.0,    # 自旋总弛豫率 300 1/s（1:1 对应自旋相关时间 3.3 ms）
    "b_t": 10.0e-9,       # 持场 10 nT（非零 ⇒ 进动响应）
    "t_s": 2.0e-3,        # FID 观测时刻 2 ms（ω_L·t* ≈ 0.88 rad）
}

B492_DEFAULT_PARAMS = {
    "n_ref_m3": 1.0e17,     # 参考点数密度（40 °C）
    "t_ref_k": 313.15,      # 参考温度
    "dh_over_kb_k": 8384.0,  # Rb 汽化焓 / k_B
    "t_k": 333.15,          # 工作温度（60 °C）
}

B493_DEFAULT_PARAMS = {
    "trans0": 1.0,             # 入射光强（归一）
    "n_density_m3": 1.0e19,    # 碱金属数密度（~100 °C）
    "sigma_abs_m2": 5.0e-18,   # 缓冲气体展宽后 D1 有效吸收截面
    "length_m": 0.02,          # 气室长度 2 cm ⇒ 光学厚度 = 1.0
}


# ===========================================================================
# 记忆化入口（part7.py 顶层引用；纯函数 ⇒ 数值逐位不变）
# ===========================================================================
@functools.lru_cache(maxsize=256)
def _b491_golden_c(p0: float, r: float, b: float, t: float) -> float:
    return fid_polarization_golden(p0, r, b, t)


@functools.lru_cache(maxsize=256)
def _b491_cand_c(p0: float, r: float, b: float, t: float) -> float:
    return fid_polarization_candidate(p0, r, b, t)


def golden_b491(p0: float = 1.0, r_tot_s1: float = 300.0, b_t: float = 10.0e-9,
                t_s: float = 2.0e-3) -> float:
    """part7.py 顶层引用的 golden 入口（**接受 default_params 关键字**）。"""
    return _b491_golden_c(p0, r_tot_s1, b_t, t_s)


def cand_b491(p0: float = 1.0, r_tot_s1: float = 300.0, b_t: float = 10.0e-9,
              t_s: float = 2.0e-3) -> float:
    """candidate 入口（_adapter_p4 用）——接受 default_params 关键字。"""
    return _b491_cand_c(p0, r_tot_s1, b_t, t_s)


@functools.lru_cache(maxsize=256)
def _b492_golden_c(nr: float, tr: float, dh: float, tk: float) -> float:
    return alkali_density_golden(nr, tr, dh, tk)


@functools.lru_cache(maxsize=256)
def _b492_cand_c(nr: float, tr: float, dh: float, tk: float) -> float:
    return alkali_density_candidate(nr, tr, dh, tk)


def golden_b492(n_ref_m3: float = 1.0e17, t_ref_k: float = 313.15,
                dh_over_kb_k: float = 8384.0, t_k: float = 333.15) -> float:
    """part7.py 顶层引用的 golden 入口。"""
    return _b492_golden_c(n_ref_m3, t_ref_k, dh_over_kb_k, t_k)


def cand_b492(n_ref_m3: float = 1.0e17, t_ref_k: float = 313.15,
              dh_over_kb_k: float = 8384.0, t_k: float = 333.15) -> float:
    """candidate 入口（_adapter_p4 用）。"""
    return _b492_cand_c(n_ref_m3, t_ref_k, dh_over_kb_k, t_k)


@functools.lru_cache(maxsize=256)
def _b493_golden_c(t0: float, nd: float, sg: float, lm: float) -> float:
    return pump_transmission_golden(t0, nd, sg, lm)


@functools.lru_cache(maxsize=256)
def _b493_cand_c(t0: float, nd: float, sg: float, lm: float) -> float:
    return pump_transmission_candidate(t0, nd, sg, lm)


def golden_b493(trans0: float = 1.0, n_density_m3: float = 1.0e19,
                sigma_abs_m2: float = 5.0e-18, length_m: float = 0.02) -> float:
    """part7.py 顶层引用的 golden 入口。"""
    return _b493_golden_c(trans0, n_density_m3, sigma_abs_m2, length_m)


def cand_b493(trans0: float = 1.0, n_density_m3: float = 1.0e19,
              sigma_abs_m2: float = 5.0e-18, length_m: float = 0.02) -> float:
    """candidate 入口（_adapter_p4 用）。"""
    return _b493_cand_c(trans0, n_density_m3, sigma_abs_m2, length_m)


# ===========================================================================
# 自检（`python -m lda.lda_harness._batch_b47_numeric` 或直接运行）
# ===========================================================================
_CASES = (
    ("B491", golden_b491, cand_b491, fid_polarization_candidate,
     B491_DEFAULT_PARAMS, "n_steps"),
    ("B492", golden_b492, cand_b492, alkali_density_candidate,
     B492_DEFAULT_PARAMS, "n_seg"),
    ("B493", golden_b493, cand_b493, pump_transmission_candidate,
     B493_DEFAULT_PARAMS, "n_steps"),
)


def _measure_candidates():
    """逐锚实测：默认档残差 / 网格残差链 / 单调性 / 收敛比 / tol 余量。

    🔴 扫描走**底层函数**（接受离散参数 n_steps/n_seg）；`cand_b49x` 是适配器入口
    （离散参数不进 `default_params`，按 B-46 纪律固定在默认档）。
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
    print("Batch B-47 数值核自检（QS-M9 · OPM/SERF · B491–B493）")
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
        for cond, msg in ((r["default_rel"] > 1e-12, "默认档 rel > 1e-12"),
                          (r["mono"], "残差链严格单调"),
                          (r["abs_default"] > 1e-12, "默认档 abs > 1e-12"),
                          (r["margin_x"] >= 100.0, "余量 ≥ 100×"),
                          (r["golden_over_tol"] >= 13.5, "|golden| ≥ 13.5×tol")):
            if not cond:
                print("   [FAIL] %s" % msg)
                bad += 1
        # 反向探针：粗端残差必须**显著**大于默认档（证明非代数恒等）。
        # 🔴 阈值 20×（非 100×）：4 档等比 ×2 的网格上，O(h²) 候选的总放大上界
        #    只有 4³ = 64×（B492 实测 64.0×）；用 100× 会**误判** O(h²) 锚。
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
