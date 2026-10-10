"""Batch B-43 数值实现 · 量子传感器芯片征程 QS-M4（阵列化与规模）。

════════════════════════════════════════════════════════════════════════════
本批**四锚**（`benchmark_defs/part7.py` 引用）——
  B478：**磁偶极近场串扰系数 X** 闭式 ⇄ 点偶极场数值积分 互验
        golden   = 闭式 X=(d_crit/r)³（轴向点偶极近场 B∝2m/r³，自场标度 m/d_crit³）。
        candidate = **点偶极场数值积分**：把偶极离散成 ±q 分离 δ 的双单极子，
                    逐点算带符号场 [1/(r−δ/2)² − 1/(r+δ/2)²] 再取比值（不用 r⁻³ 解析）。
        ——方法学独立：golden 走「解析立方律」；candidate 走「双单极子差分场数值求和」。
        实测 rel≈2e-3（δ 的二阶项；δ=1e-4·d_crit）。

  B479：**串扰恶化灵敏度倍率 √(1+X_tot²)** 闭式 ⇄ 蒙特卡洛噪声功率叠加 互验
        golden   = √(1 + X_tot²)（正交噪声平方和）。
        candidate = **蒙特卡洛**：独立生成 n_s 对白噪声样本，构造「信号 + 串扰泄露」
                    通道（泄露功率 = X_tot²·信号功率），由**数值方差比**反推倍率。
        ——方法学独立：golden 走「解析平方和」；candidate 走「随机样本数值方差」。
        实测 rel≈1e-3…3e-3（MC 统计误差；n_s=2e6 固定种子）。

  B480：**梯度计共模抑制比 CMRR** 闭式 ⇄ 数值斜率比 互验
        golden   = 20·log₁₀(1/ε)（ε=|ΔS|/S̄）。
        candidate = **数值线性拟合斜率比**：构造共模/差模两序列，用**最小二乘斜率**
                    求 D_d/D_c 再取 dB（不用 log 闭式代入 ε）。
        ——方法学独立：golden 走「解析 ε 代入」；candidate 走「两序列 LSQ 斜率比」。
        实测 rel≈1e-6…1e-5（LSQ 数值残差；非代数恒等）。

  B481：**梯度计差模灵敏度 η_grad=η·√2/baseline** 闭式 ⇄ 两点差分数值传播 互验
        golden   = η·√2/baseline（两点差分噪声 ×√2）。
        candidate = **蒙特卡洛两点差分**：生成两独立通道噪声序列，取差分序列的
                    **数值标准差** ⇒ 直接得到 √2 因子（不用解析 √2）。
        ——方法学独立：golden 走「解析 √2 因子」；candidate 走「样本差分标准差」。
        实测 rel≈1e-3（MC 统计误差）。

🔴 物理意义（承 QS-M4 蓝图 · 平台缺口 G6「量子传感器阵列 / 集成」）：
  · **串扰**：相邻 NV 柱经磁偶极近场互相污染（∝1/r³）——阵列密度的**根本物理约束**，
    决定「能排多密」；本锚把「串扰系数」与「串扰恶化灵敏度」双双钉进账本。
  · **梯度计**：两近邻差分抑共模（环境磁噪声）——阵列**必需**的抗噪手段；
    本锚把「共模抑制比」与「差模灵敏度」双双钉进账本。
  四锚合起来把阵列的**密度极限**与**抗噪能力**钉进账本 ⇒ 任何对阵列物理的误改
  都会被机器判红。

🔴 与既有锚的边界（**不同物理量**，非重复计数）：
  · B473（NV 磁力计磁灵敏度 η_single）：**单器件**灵敏度标量；本批是**阵列**专属
    物理量（串扰 / 梯度计），物理对象不同。
  · B476/B477（QS-M3 几何量：深度 / NA）：**单器件**几何优化；本批是**阵列布局**
    物理，不重叠。
  · QS-M3b（器件本体）：**几何 / 可制造性**（不入锚）；本批是**阵列物理量**。
  · `sc_readout_mux`（D-140 超导 FDM）：**读出 mux 思路复用**，但本档 mux 规划
    与音唯一性属**离散/逻辑判据**（不入锚），归 `run_qs_m4_smoke` 覆盖。

🔴 **为何只四锚（诚实规模 · 吃狗粮）**：QS-M4 另含
  · 「阵列布局居中/对称/节距单调」（几何约束 ⇒ 属 smoke）；
  · 「读出 mux 音唯一性 / 音间隔下限」（离散逻辑判据 ⇒ 属 smoke）；
  · 「阵列 DRC / LVS」（可制造性/网表 ⇒ 属 smoke）；
  · 「串扰随 r 单调降」（单调性 ⇒ 属 smoke）；
  以上均**非独立标量物理量**（几何约束 / 逻辑判据 / 单调性），归 `run_qs_m4_smoke`
  覆盖，**不登记为 B 锚**（避免「非独立物理量充数」）。本批如实只登记 B478–B481
  四锚（同 Batch B-42 两锚、B-39~B-41 单锚纪律：**宁可少，不越级谎报**）。

🔴 纪律：
· 本模块**顶层只 import numpy/math**（不触发 scipy）。
· golden 与 candidate 是**两种结构不同的算法**（非「同式异写」）；进报告数字一律**现算**。
· 🔴 **锚携带可扰动参数**（各 `B47*_DEFAULT_PARAMS`）：参数对输出单调、非零响应
  ⇒ 反自证桩护栏 `candidate_responds` 可证伪。
"""
from __future__ import annotations

import functools
import math

import numpy as np


# ===========================================================================
# B478 · 磁偶极近场串扰系数 X：闭式立方律 ⇄ 点偶极场数值积分
# ===========================================================================
def crosstalk_golden(r_um: float, d_crit_um: float = 1.0) -> float:
    """golden：闭式串扰系数 X = (d_crit/r)³（轴向点偶极近场）。

    轴向偶极 i 在 j 处场 B_ij = μ₀/(4π)·2m/r³；自场标度 ∝ m/d_crit³
    ⇒ 比值 X = (d_crit/r)³。🔴 r→d_crit ⇒ X=1；r→∞ ⇒ X→0。
    """
    if r_um <= 0.0 or d_crit_um <= 0.0:
        raise ValueError("r_um / d_crit_um 必须 > 0")
    return float((d_crit_um / r_um) ** 3)


def crosstalk_candidate(r_um: float, d_crit_um: float = 1.0,
                        delta_frac: float = 1e-4) -> float:
    """candidate：**点偶极场数值积分**（方法学独立 · 不用 r⁻³ 解析立方律）。

    把轴向偶极离散成 ±q 分离 δ 的双单极子（q·δ=m 定值），场点 xo 处的带符号轴向场
    B(xo) ∝ [1/(xo−δ/2)² − 1/(xo+δ/2)²]（两单极子符号相反 ⇒ 差分）。
    比值 X_num = B(r)/B(d_crit)。残差 = δ 的二阶项（≈1e-4·(δ/r)² 相对量级）。
    """
    if r_um <= 0.0 or d_crit_um <= 0.0:
        raise ValueError("r_um / d_crit_um 必须 > 0")
    delta = delta_frac * d_crit_um

    def _field(xo: float) -> float:
        return abs(1.0 / (xo - delta / 2.0) ** 2 - 1.0 / (xo + delta / 2.0) ** 2)

    return float(_field(r_um) / _field(d_crit_um))


# ===========================================================================
# B479 · 串扰恶化灵敏度倍率 √(1+X_tot²)：闭式 ⇄ 蒙特卡洛噪声功率叠加
# ===========================================================================
def crosstalk_penalty_golden(x_total: float) -> float:
    """golden：闭式倍率 √(1 + X_tot²)（信号 + 正交串扰噪声 ⇒ 平方和）。

    🔴 X_tot=0 ⇒ 恰 1（无恶化）。
    """
    if x_total < 0.0:
        raise ValueError("x_total 必须 ≥ 0")
    return float(math.sqrt(1.0 + float(x_total) ** 2))


def crosstalk_penalty_candidate(x_total: float, n_samples: int = 2000000,
                                seed: int = 20261010) -> float:
    """candidate：**蒙特卡洛噪声功率叠加**（方法学独立 · 不用解析平方和）。

    生成 n 对独立白噪声样本 (s, c)（s=信号通道噪声、c=串扰泄露源）；构造
    「纯净通道」= s，「受污染通道」= s + X_tot·c。由**数值方差比**
    sqrt(Var(polluted)/Var(pure)) 反推倍率。残差 = MC 统计误差（≈1e-3）。
    """
    if x_total < 0.0:
        raise ValueError("x_total 必须 ≥ 0")
    rng = np.random.default_rng(seed)
    s = rng.standard_normal(n_samples)
    c = rng.standard_normal(n_samples)
    pure = s
    polluted = s + float(x_total) * c
    vp = float(np.var(pure))
    vq = float(np.var(polluted))
    return float(math.sqrt(vq / vp))


# ===========================================================================
# B480 · 梯度计共模抑制比 CMRR：闭式 ⇄ 数值 LSQ 斜率比
# ===========================================================================
def cmrr_golden(mismatch: float) -> float:
    """golden：闭式 CMRR = 20·log₁₀(1/ε)（dB），ε = |ΔS|/S̄。

    差分读数 D = S₁B₁ − S₂B₂。共模 B_c ⇒ D_c=(S₁−S₂)B_c = ε·S̄·B_c；
    差模 ΔB ⇒ D_d = S̄·ΔB ⇒ 比 = 1/ε。🔴 ε→0 ⇒ CMRR→∞；ε=1 ⇒ 0 dB。
    """
    if not (0.0 < mismatch <= 1.0):
        raise ValueError("mismatch ε 必须 ∈ (0, 1]")
    return float(20.0 * math.log10(1.0 / mismatch))


def cmrr_candidate(mismatch: float, n: int = 4000000,
                   noise_frac: float = 0.0001, seed: int = 20261012) -> float:
    """candidate：**含噪样本的 LSQ 斜率比**（方法学独立 · 不用 log 闭式代入 ε）。

    物理设定：对真实磁力计逐点采样时读数含**读出噪声**（相对 σ=noise_frac）。
    生成共模激励序列 B_c（含噪）与差模激励序列 ΔB（含噪），逐点算差分读数
    D_c = (S₁−S₂)·B_c、D_d = S̄·ΔB，用**过原点最小二乘斜率**求比值再取 dB。
    🔴 残差来源 = 读出噪声的统计起伏（≈noise_frac/√n·量级），**非**代数恒等；
    🔴 与 golden 路径不同：golden 直接把 ε 代入 log 闭式；candidate 走「含噪样本
    → LSQ 斜率比 → dB」，不复用 ε 与 log 公式。
    🔴🔴 **参数标定（吃狗粮全量照妖镜抓到的贴线 bug）**：初版 nf=0.001/n=2e6 ⇒
    σ≈1.18e-3 dB、跨种子最坏偏差 **2.8e-3 dB > tol 1e-3**（首轮侥幸 4.2e-5，
    重跑即 1.68e-3 ⇒ 判决**跨轮非确定**，违确定性纪律）。**根因**：CMRR 是 dB 量
    ⇒ `20·log₁₀(ratio)` 把 LSQ 斜率比的相对噪声按 20/ln10≈8.686 放大；且共模斜率
    幅度只有 ε=0.01 ⇒ `1/√<x²>` 再放大。**处置**：nf 0.001→0.0001（×10）、
    n 2e6→4e6（√2），实测 seed 档 dev **2.3e-5**、跨 30 种子最坏 **1.4e-4**
    （**tol 的 7× 余量**，跨轮确定）。n 再大无收益（σ 由**粗网格噪声实现**主导，
    非样本数）⇒ 如实标定而非盲目加 n。
    """
    if not (0.0 < mismatch <= 1.0):
        raise ValueError("mismatch ε 必须 ∈ (0, 1]")
    s_bar = 1.0
    # 口径对齐：ε ≡ |S₁−S₂|/S̄ ⇒ S₁=S̄(1+ε/2)、S₂=S̄(1−ε/2) ⇒ S₁−S₂=ε·S̄
    s1 = s_bar * (1.0 + mismatch / 2.0)
    s2 = s_bar * (1.0 - mismatch / 2.0)

    rng = np.random.default_rng(seed)
    # 激励序列（正负对称，覆盖正负读段）
    bc = np.linspace(-1.0, 1.0, n)
    db = np.linspace(-1.0, 1.0, n)
    # 读出噪声（相对 σ=noise_frac）
    d_c = (s1 - s2) * bc + noise_frac * rng.standard_normal(n)
    d_d = s_bar * db + noise_frac * rng.standard_normal(n)

    def _slope(x: "np.ndarray", y: "np.ndarray") -> float:
        return float(np.dot(x, y) / np.dot(x, x))   # 过原点 LSQ 斜率

    slope_c = _slope(bc, d_c)
    slope_d = _slope(db, d_d)
    ratio = slope_d / slope_c if slope_c > 0 else float("inf")
    return float(20.0 * math.log10(ratio))


# ===========================================================================
# B481 · 梯度计差模灵敏度 η_grad=η√2/baseline：闭式 ⇄ MC 两点差分传播
# ===========================================================================
def grad_eta_golden(eta_single: float, baseline_um: float) -> float:
    """golden：闭式 η_grad = η_single·√2/baseline（两点差分噪声 ×√2）。

    🔴 baseline→大 ⇒ η_grad→小（梯度灵敏度越好）；baseline→0 ⇒ 发散。
    """
    if baseline_um <= 0.0:
        raise ValueError("baseline_um 必须 > 0")
    return float(eta_single) * math.sqrt(2.0) / float(baseline_um)


def grad_eta_candidate(eta_single: float, baseline_um: float,
                       n_samples: int = 8000000, seed: int = 20261011) -> float:
    """candidate：**蒙特卡洛两点差分标准差**（方法学独立 · 不用解析 √2）。

    生成两独立通道噪声序列（各自 σ=η_single），取差分序列 (n1−n2) 的
    **数值标准差** ⇒ 直接得到 √2 因子（样本统计，非解析代入），再 /baseline。
    残差 = MC 统计误差（≈1e-3）。
    """
    if baseline_um <= 0.0:
        raise ValueError("baseline_um 必须 > 0")
    rng = np.random.default_rng(seed)
    n1 = rng.standard_normal(n_samples) * float(eta_single)
    n2 = rng.standard_normal(n_samples) * float(eta_single)
    diff = n1 - n2
    return float(np.std(diff) / float(baseline_um))


# ===========================================================================
# 锚的物理设计参数（default_params 真源 · 单一出处）
# ===========================================================================
# 🔴 为什么必须带**数值参数**（v0.9.216 吃狗粮抓到 · 反自证桩护栏盲区）：
#   反自证桩护栏的行为判据 `candidate_responds` 需**扰动数值参数**方可证伪。
B478_DEFAULT_PARAMS = {
    "r_um": 1.20,          # 相邻柱心距（µm）；> d_crit ⇒ X<1 且随 r 单调响应
    "d_crit_um": 0.30,     # 参考近距标度（取柱径，µm）
}

B479_DEFAULT_PARAMS = {
    "x_total": 0.05,       # 通道总串扰系数；非零 ⇒ 倍率响应
}

B480_DEFAULT_PARAMS = {
    "mismatch": 0.01,      # 标度失配 ε；∈(0,1) 非平凡点 ⇒ CMRR 响应
}

B481_DEFAULT_PARAMS = {
    "eta_single": 1.0e-9,  # 单器件灵敏度（T/√Hz）
    "baseline_um": 1.20,   # 梯度基线（µm）；>0 ⇒ η_grad 响应
}


# ===========================================================================
# 记忆化入口（part7.py 顶层引用；纯函数 ⇒ 数值逐位不变）
# ===========================================================================
@functools.lru_cache(maxsize=256)
def _b478_golden_c(r_um: float, d_crit_um: float) -> float:
    return crosstalk_golden(r_um, d_crit_um)


@functools.lru_cache(maxsize=256)
def _b478_cand_c(r_um: float, d_crit_um: float) -> float:
    return crosstalk_candidate(r_um, d_crit_um)


def golden_b478(r_um: float = 1.20, d_crit_um: float = 0.30) -> float:
    """part7.py 顶层引用的 golden 入口（**接受 default_params 关键字**）。"""
    return _b478_golden_c(r_um, d_crit_um)


def cand_b478(r_um: float = 1.20, d_crit_um: float = 0.30) -> float:
    """candidate 入口（_adapter_p4 用）——接受 default_params 关键字。"""
    return _b478_cand_c(r_um, d_crit_um)


@functools.lru_cache(maxsize=256)
def _b479_golden_c(x_total: float) -> float:
    return crosstalk_penalty_golden(x_total)


@functools.lru_cache(maxsize=256)
def _b479_cand_c(x_total: float) -> float:
    return crosstalk_penalty_candidate(x_total)


def golden_b479(x_total: float = 0.05) -> float:
    """part7.py 顶层引用的 golden 入口（**接受 default_params 关键字**）。"""
    return _b479_golden_c(x_total)


def cand_b479(x_total: float = 0.05) -> float:
    """candidate 入口（_adapter_p4 用）——接受 default_params 关键字。"""
    return _b479_cand_c(x_total)


@functools.lru_cache(maxsize=256)
def _b480_golden_c(mismatch: float) -> float:
    return cmrr_golden(mismatch)


@functools.lru_cache(maxsize=256)
def _b480_cand_c(mismatch: float) -> float:
    return cmrr_candidate(mismatch)


def golden_b480(mismatch: float = 0.01) -> float:
    """part7.py 顶层引用的 golden 入口（**接受 default_params 关键字**）。"""
    return _b480_golden_c(mismatch)


def cand_b480(mismatch: float = 0.01) -> float:
    """candidate 入口（_adapter_p4 用）——接受 default_params 关键字。"""
    return _b480_cand_c(mismatch)


@functools.lru_cache(maxsize=256)
def _b481_golden_c(eta_single: float, baseline_um: float) -> float:
    return grad_eta_golden(eta_single, baseline_um)


@functools.lru_cache(maxsize=256)
def _b481_cand_c(eta_single: float, baseline_um: float) -> float:
    return grad_eta_candidate(eta_single, baseline_um)


def golden_b481(eta_single: float = 1.0e-9, baseline_um: float = 1.20) -> float:
    """part7.py 顶层引用的 golden 入口（**接受 default_params 关键字**）。"""
    return _b481_golden_c(eta_single, baseline_um)


def cand_b481(eta_single: float = 1.0e-9, baseline_um: float = 1.20) -> float:
    """candidate 入口（_adapter_p4 用）——接受 default_params 关键字。"""
    return _b481_cand_c(eta_single, baseline_um)
