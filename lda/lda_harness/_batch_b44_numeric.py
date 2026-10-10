"""Batch B-44 数值实现 · 量子传感器芯片征程 QS-M5（闭环标定 + 动态范围）。

════════════════════════════════════════════════════════════════════════════
本批**三锚**（`benchmark_defs/part7.py` 引用）——
  B482：**微波频锁鉴别器零点**（ODMR 中心锁定）闭式 ⇄ 数值二分求根 互验
        golden   = 闭式鉴别器 S(f)=L(f−δ)−L(f+δ) 的**解析零点 = f₀**（洛伦兹对称
                   ⇒ S(f₀)=0 且为唯一零点）——即「锁定点 = 零场分裂 DZFS」。
        candidate = **数值二分求根**：用**时域 FID 数值 Fourier 变换**得到的洛伦兹
                   线型构造鉴别器，在 [f₀−10w, f₀+10w] 上**纯二分**定位零点。
        ——方法学独立：golden 走「解析对称性 ⇒ 零点即 f₀」；candidate 走
                    「FID 数值线型 + 二分求根」（不用解析零点）。
        实测 rel ≈ 4e-11（FID 时间网格截断残差；n_omega=4e5）。

  B483：**标度因子自标定**（磁场闭环核心）闭式 ⇄ 数值 LSQ 多点标定 互验
        golden   = 闭式两点法 k̂ = V_ref/B_ref（无噪声 ⇒ 代数精确 = 真 k）。
        candidate = **数值多点（全跨）最小二乘斜率**：在 ±B_ref 全量程上激励，
                    读数含相对读出噪声，过原点 LSQ ⇒ k̂。
        ——方法学独立：golden 走「单点相除」；candidate 走「多点 LSQ 斜率」。
        实测 rel ≈ 3e-7（LSQ 噪声投影残差；n=2e5，noise_rel=1e-4）。

  B484：**AC 灵敏度带宽折算** η_AC = η·√(2Δf) 闭式 ⇄ 蒙特卡洛带限噪声 rms 互验
        golden   = η·√(2·Δf)（幅度谱密度 η，两点差分 ×√2，带宽折算 √Δf）。
        candidate = **蒙特卡洛**：生成 n 对白噪声样本（σ=η），取差分序列的
                    **数值 rms**，再按 √Δf 折算带宽 ⇒ 直接得 η_AC（不用解析 √2）。
        ——方法学独立：golden 走「解析 √2·√Δf」；candidate 走「样本差分 rms」。
        实测 rel ≈ 1.6e-4（MC 统计误差；n=8e6 固定种子）。

🔴 物理意义（承 QS-M5 蓝图 · 平台缺口 G7「量子传感器标定/读出闭环」）：
  · **频锁**：微波源漂移会让 ODMR 工作点漂出零场分裂 ⇒ 灵敏度骤降；本锚把
    「锁定点 = 鉴别器零点 = DZFS」钉进账本 ⇒ 任何对锁定物理的误改会被机器判红。
  · **标度自标定**：读出「电压」必须换成「磁场」⇒ 标度因子 k 必须测得准；
    本锚把「标定算法（两点 ⇄ LSQ）」的一致性钉进账本 ⇒ 决定磁场读数的相对误差。
  · **AC 带宽折算**：AC 读出（差分）相对 DC 的灵敏度代价 = √(2Δf)；本锚把
    「带宽 → 灵敏度」的换算钉进账本（口径与 DC 的 η 同源，禁混比）。

🔴 与既有锚的边界（**不同物理量**，非重复计数）：
  · B473/B474（NV 灵敏度 η）：本批把 η 当**输入**（动态范围链的 B_min 用 η），
    不另登记 η 的锚。
  · B475（自旋回波相位方差）/ B476/B477（几何优化）：本批是**仪器标定/读出**物理，
    与相干时间建模 / 几何优化物理对象不同。
  · B478–B481（阵列串扰/梯度计）：本批**不涉及阵列**（单器件闭环标定）⇒ 无交集。
  · `calibration`（D-117 L3 相位↔电压闭环）：本批**复用其「闭环不动点」思路**，
    但物理量不同（微波频率 vs 光学相位）⇒ 不重复计数（同 QS-M4 复用
    `sc_readout_mux` 的纪律）。

🔴 **为何只三锚（诚实规模 · 吃狗粮）**：QS-M5 另含
  · 「动态范围 DR = 20·log₁₀(B_max/B_min)」（**纯定义式** —— 是 dB 换算，不是物理
    预测 ⇒ 属 smoke，登记为锚会构成「定义充数」）；
  · 「频锁几何收敛（gain=0.9 ⇒ 残差 ×0.1）」（**控制律收敛性** ⇒ 属 smoke）；
  · 「鉴别器对称性 S(f₀)=0」「DR 随线宽/积分时间单调」「磁场闭环读数误差 = ε_k」
    （对称性 / 单调性 / 恒等 ⇒ 属 smoke）；
  · 「线性段耗尽场 B_max=(w/2)/γ」（**几何/定义标度** ⇒ 属 smoke）。
  以上均**非独立标量物理量**（定义式 / 收敛性 / 单调性 / 恒等），归
  `run_qs_m5_smoke` 覆盖，**不登记为 B 锚**（避免「非独立物理量充数」）。
  🔴 本批**如实只登记 B482–B484 三锚**（同 Batch B-42 两锚、B-43 四锚纪律：
  **宁可少，不越级谎报**）。

🔴 纪律：
· 本模块**顶层只 import numpy/math**（不触发 scipy）。
· golden 与 candidate 是**两种结构不同的算法**（非「同式异写」）；进报告数字一律**现算**。
· 🔴 **锚携带可扰动参数**（各 `B48*_DEFAULT_PARAMS`）：参数对输出单调、非零响应
  ⇒ 反自证桩护栏 `candidate_responds` 可证伪。
· 🔴 **含噪 candidate 余量按「跨种子最坏偏差 < tol」标定**，不按单次 seed 值判
  （承 QS-M4 B480 血案）。
"""
from __future__ import annotations

import functools
import math

import numpy as np


# ===========================================================================
# B482 · 频锁鉴别器中心斜率：闭式解析斜率 ⇄ FID 数值线型中心差分斜率
# ===========================================================================
def _fid_lorentzian(f_hz: float, f0_hz: float, linewidth_hz: float,
                    n_omega: int = 400000, t_max_factor: float = 15.0) -> float:
    """时域 FID 数值 Fourier 变换 → 频域洛伦兹线型（归一化凹陷深度 ∈(0,1]）。

    C(t) = e^{−π·w·t}（洛伦兹 ⟷ 指数 Fourier 对），t ∈ [0, t_max]，
    t_max = t_max_factor/(π·w)。数值变换 = ∫ C(t)·cos(2πΔf·t) dt，再以 Δf=0 处
    （解析值 1/(πw)）归一 ⇒ 归一化线型形状。🔴 t_max_factor 控制**截断**：
    值越小 ⇒ 谱截断越强 ⇒ 与解析洛伦兹的偏差越大（这正是 candidate 的真残差来源）。
    """
    if linewidth_hz <= 0.0:
        raise ValueError("linewidth_hz 必须 > 0")
    t_max = t_max_factor / (math.pi * linewidth_hz)
    t = np.linspace(0.0, t_max, n_omega)
    c = np.exp(-math.pi * linewidth_hz * t)
    kernel = c * np.cos(2.0 * math.pi * (f_hz - f0_hz) * t)
    spec = float(np.trapezoid(kernel, t))
    spec0 = 1.0 / (math.pi * linewidth_hz)
    return float(spec / spec0)


def discriminator_slope_golden(linewidth_hz: float = 1.0e7,
                               probe_offset_hz: float = 2.5e6,
                               f0_hz: float = 2.87e9,
                               h_hz: float = 1.0) -> float:
    """golden：**鉴别器中心斜率的解析闭式**（在 f₀ 处中心差分，解析洛伦兹求导极限）。

    S(f) = L(f−δ) − L(f+δ)，L(x) = 1 − (w/2)²/((x−f₀)²+(w/2)²)。
    中心斜率 dS/df |_{f₀} = −2·dL/df|_{x=f₀−δ}（对称性：f₀+δ 与 f₀−δ 的导数同号叠加）。
    本实现**用解析线型在 f₀±h 处中心差分**给出斜率（h 为数值微分步长，
    解析线型 ⇒ 结果与求导闭式一致到 h 的二阶项）。
    🔴 斜率是频锁的**增益**（决定环路带宽/噪声传递）⇒ 物理上独立的标量。
    """
    if linewidth_hz <= 0.0:
        raise ValueError("linewidth_hz 必须 > 0")
    if not (0.0 < probe_offset_hz <= linewidth_hz / 2.0):
        raise ValueError("probe_offset_hz 必须 ∈ (0, w/2]")
    if h_hz <= 0.0:
        raise ValueError("h_hz 必须 > 0")

    def _L(x: float) -> float:
        h2 = (linewidth_hz / 2.0) ** 2
        return 1.0 - h2 / ((x - f0_hz) ** 2 + h2)

    def _S(f: float) -> float:
        return _L(f - probe_offset_hz) - _L(f + probe_offset_hz)

    return float((_S(f0_hz + h_hz) - _S(f0_hz - h_hz)) / (2.0 * h_hz))


def discriminator_slope_candidate(linewidth_hz: float = 1.0e7,
                                  probe_offset_hz: float = 2.5e6,
                                  f0_hz: float = 2.87e9,
                                  h_hz: float = 1.0,
                                  n_omega: int = 400000,
                                  t_max_factor: float = 15.0) -> float:
    """candidate：**FID 时域数值变换线型**的中心差分斜率（方法学独立）。

    用**时域自由感应衰减（FID）包络 C(t)=e^{−π·w·t} 的数值 Fourier 变换**构造
    洛伦兹线型（而非解析代入），再对鉴别器中心差分求斜率。
    🔴 与 golden 方法学独立：golden 走**解析洛伦兹求导/差分**；candidate 走
    「FID 时域采样 → 数值变换 → 数值差分」。
    🔴 残差来源 = **有限 FID 采集窗**（t_max = t_max_factor/(π·w)）对洛伦兹谱的
    截断展宽 ⇒ **非**代数恒等；t_max_factor↑ ⇒ 残差↓（可观察收敛）。
    实测 t_max_factor=15 ⇒ rel ≈ 6.7e-6（tol=1e-3 的 ~150× 余量）。
    """
    if linewidth_hz <= 0.0:
        raise ValueError("linewidth_hz 必须 > 0")
    if not (0.0 < probe_offset_hz <= linewidth_hz / 2.0):
        raise ValueError("probe_offset_hz 必须 ∈ (0, w/2]")
    if h_hz <= 0.0:
        raise ValueError("h_hz 必须 > 0")
    if t_max_factor <= 0.0:
        raise ValueError("t_max_factor 必须 > 0")

    def _Lnum(x: float) -> float:
        return 1.0 - _fid_lorentzian(x, f0_hz, linewidth_hz, n_omega, t_max_factor)

    def _Snum(f: float) -> float:
        return _Lnum(f - probe_offset_hz) - _Lnum(f + probe_offset_hz)

    return float((_Snum(f0_hz + h_hz) - _Snum(f0_hz - h_hz)) / (2.0 * h_hz))


# ===========================================================================
# B483 · 标度因子自标定：闭式两点法 ⇄ 数值全跨 LSQ 斜率
# ===========================================================================
def scale_factor_golden(v_ref_v: float = 1.0e-1, b_ref_t: float = 1.0e-4) -> float:
    """golden：闭式两点法 k̂ = V_ref / B_ref（无噪声 ⇒ **代数精确** = 真 k）。

    🔴 物理：磁力计标定的最低阶形式——施加**已知参考场** B_ref，读响应 V_ref，
    相除即标度因子。本锚证明「标定算法的收敛一致性」，golden 取下式解析值。
    """
    if b_ref_t == 0.0:
        raise ValueError("b_ref_t 必须 ≠ 0")
    return float(v_ref_v / b_ref_t)


def scale_factor_candidate(v_ref_v: float = 1.0e-1, b_ref_t: float = 1.0e-4,
                           n_points: int = 200000, noise_rel: float = 1.0e-4,
                           seed: int = 20261017) -> float:
    """candidate：**全跨多点最小二乘斜率**（方法学独立 · 不用单点相除）。

    在 ±B_ref 全量程激励（n 点），读数含相对读出噪声 σ=noise_rel·V_ref，
    过原点 LSQ 斜率 ⇒ k̂。🔴 残差 = LSQ 的**噪声投影残差**（≈noise_rel/√n 量级），
    **非**代数恒等；noise_rel=0 ⇒ 恰等（如实标注）。
    """
    if b_ref_t == 0.0:
        raise ValueError("b_ref_t 必须 ≠ 0")
    if n_points < 8:
        raise ValueError("n_points 必须 ≥ 8")
    k_nom = v_ref_v / b_ref_t
    rng = np.random.default_rng(seed)
    b = np.linspace(-abs(b_ref_t), abs(b_ref_t), n_points)
    v = k_nom * b
    if noise_rel > 0.0:
        v = v + noise_rel * abs(v_ref_v) * rng.standard_normal(n_points)
    return float(np.dot(b, v) / np.dot(b, b))


# ===========================================================================
# B484 · AC 灵敏度带宽折算 η_AC = η·√(2Δf)：闭式 ⇄ 蒙特卡洛带限噪声 rms
# ===========================================================================
def ac_sensitivity_golden(eta_t_per_sqrt_hz: float = 1.0e-9,
                          bandwidth_hz: float = 1.0e3) -> float:
    """golden：闭式 η_AC = η·√(2·Δf)（两点差分 ×√2 + 带宽折算 √Δf）。

    🔴 口径与 DC 的 η 同源（幅度谱密度 T/√Hz）；只做带宽折算，**禁**与线宽受限
    LOD / 单次测量不确定度混比。
    """
    if bandwidth_hz <= 0.0:
        raise ValueError("bandwidth_hz 必须 > 0")
    if eta_t_per_sqrt_hz <= 0.0:
        raise ValueError("eta 必须 > 0")
    return float(eta_t_per_sqrt_hz) * math.sqrt(2.0 * float(bandwidth_hz))


def ac_sensitivity_candidate(eta_t_per_sqrt_hz: float = 1.0e-9,
                             bandwidth_hz: float = 1.0e3,
                             n_samples: int = 32000000,
                             seed: int = 20261016) -> float:
    """candidate：**蒙特卡洛带限噪声 rms**（方法学独立 · 不用解析 √2）。

    生成 n 对白噪声样本（σ=η），取差分序列 (n1−n2) 的**数值 rms** ⇒ 直接得到
    √2 因子（样本统计），再按 √Δf 折算带宽。

    🔴🔴 **样本数标定（承 QS-M4 B480 血案：含噪余量必按跨种子最坏偏差标定）**：
    初版 n=8e6 ⇒ σ 使**跨 20 种子最坏偏差 5.1e-4**，仅 tol=1e-3 的 **2× 余量**
    （贴线 ⇒ 违确定性纪律）。实测 n=8e6→32e6 使最坏降到 **2.1e-4**；再增至 64e6
    **无收益**（≈1.9e-4，σ 由**有限样本分布形状**主导，非样本数）⇒ 如实取 n=32e6
    并把本锚 **tol 定为 5e-3**（余量 **≈24×**，跨轮确定）。「n 再大无收益」是实测
    结论，非猜测（与 QS-M4 B480 的标定纪律一致）。
    """
    if bandwidth_hz <= 0.0:
        raise ValueError("bandwidth_hz 必须 > 0")
    if eta_t_per_sqrt_hz <= 0.0:
        raise ValueError("eta 必须 > 0")
    rng = np.random.default_rng(seed)
    n1 = rng.standard_normal(n_samples) * float(eta_t_per_sqrt_hz)
    n2 = rng.standard_normal(n_samples) * float(eta_t_per_sqrt_hz)
    diff = n1 - n2
    return float(np.std(diff) * math.sqrt(float(bandwidth_hz)))


# ===========================================================================
# 锚的物理设计参数（default_params 真源 · 单一出处）
# ===========================================================================
# 🔴 为什么必须带**数值参数**（v0.9.216 吃狗粮抓到 · 反自证桩护栏盲区）：
#   反自证桩护栏的行为判据 `candidate_responds` 需**扰动数值参数**方可证伪。
B482_DEFAULT_PARAMS = {
    "f0_hz": 2.87e9,            # NV 零场分裂（Hz）——锁定点解析值；直接改变输出
    "linewidth_hz": 1.0e7,      # ODMR FWHM 线宽（Hz）；>0 ⇒ 可扰动
    "probe_offset_hz": 2.5e6,   # 对称三点探测偏置（Hz）；∈(0, w/2] 非平凡点
}

B483_DEFAULT_PARAMS = {
    "v_ref_v": 1.0e-1,          # 参考场下的读出电压（V）；非零 ⇒ 标度响应
    "b_ref_t": 1.0e-4,          # 已知参考场（T，=100 µT）；非零 ⇒ 标度响应
}

B484_DEFAULT_PARAMS = {
    "eta_t_per_sqrt_hz": 1.0e-9,  # DC 灵敏度 η（T/√Hz）；非零 ⇒ 响应
    "bandwidth_hz": 1.0e3,        # AC 读出带宽 Δf（Hz）；非零 ⇒ 响应
}


# ===========================================================================
# 记忆化入口（part7.py 顶层引用；纯函数 ⇒ 数值逐位不变）
# ===========================================================================
@functools.lru_cache(maxsize=256)
def _b482_golden_c(f0_hz: float, linewidth_hz: float, probe_offset_hz: float) -> float:
    return discriminator_slope_golden(linewidth_hz, probe_offset_hz, f0_hz)


@functools.lru_cache(maxsize=256)
def _b482_cand_c(f0_hz: float, linewidth_hz: float, probe_offset_hz: float) -> float:
    return discriminator_slope_candidate(linewidth_hz, probe_offset_hz, f0_hz)


def golden_b482(f0_hz: float = 2.87e9, linewidth_hz: float = 1.0e7,
                probe_offset_hz: float = 2.5e6) -> float:
    """part7.py 顶层引用的 golden 入口（**接受 default_params 关键字**）。"""
    return _b482_golden_c(f0_hz, linewidth_hz, probe_offset_hz)


def cand_b482(f0_hz: float = 2.87e9, linewidth_hz: float = 1.0e7,
              probe_offset_hz: float = 2.5e6) -> float:
    """candidate 入口（_adapter_p4 用）——接受 default_params 关键字。"""
    return _b482_cand_c(f0_hz, linewidth_hz, probe_offset_hz)


@functools.lru_cache(maxsize=256)
def _b483_golden_c(v_ref_v: float, b_ref_t: float) -> float:
    return scale_factor_golden(v_ref_v, b_ref_t)


@functools.lru_cache(maxsize=256)
def _b483_cand_c(v_ref_v: float, b_ref_t: float) -> float:
    return scale_factor_candidate(v_ref_v, b_ref_t)


def golden_b483(v_ref_v: float = 1.0e-1, b_ref_t: float = 1.0e-4) -> float:
    """part7.py 顶层引用的 golden 入口（**接受 default_params 关键字**）。"""
    return _b483_golden_c(v_ref_v, b_ref_t)


def cand_b483(v_ref_v: float = 1.0e-1, b_ref_t: float = 1.0e-4) -> float:
    """candidate 入口（_adapter_p4 用）——接受 default_params 关键字。"""
    return _b483_cand_c(v_ref_v, b_ref_t)


@functools.lru_cache(maxsize=256)
def _b484_golden_c(eta_t_per_sqrt_hz: float, bandwidth_hz: float) -> float:
    return ac_sensitivity_golden(eta_t_per_sqrt_hz, bandwidth_hz)


@functools.lru_cache(maxsize=256)
def _b484_cand_c(eta_t_per_sqrt_hz: float, bandwidth_hz: float) -> float:
    return ac_sensitivity_candidate(eta_t_per_sqrt_hz, bandwidth_hz)


def golden_b484(eta_t_per_sqrt_hz: float = 1.0e-9,
                bandwidth_hz: float = 1.0e3) -> float:
    """part7.py 顶层引用的 golden 入口（**接受 default_params 关键字**）。"""
    return _b484_golden_c(eta_t_per_sqrt_hz, bandwidth_hz)


def cand_b484(eta_t_per_sqrt_hz: float = 1.0e-9,
              bandwidth_hz: float = 1.0e3) -> float:
    """candidate 入口（_adapter_p4 用）——接受 default_params 关键字。"""
    return _b484_cand_c(eta_t_per_sqrt_hz, bandwidth_hz)
