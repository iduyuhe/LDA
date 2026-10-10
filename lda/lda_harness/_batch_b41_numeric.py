"""Batch B-41 数值实现 · 量子传感器芯片征程 QS-M2（退相干 + 多源噪声）。

════════════════════════════════════════════════════════════════════════════
本批**一锚**（`benchmark_defs/part7.py` 引用）——
  B475：自旋**回波（Hahn echo）相位方差**闭式 ↔ **时间域数值积分**互验
        golden   = 闭式 ⟨Φ²⟩_echo = 2(1−cos(ωt/2))²（归一化：丢 (γb/ω)²）
        candidate = **时间域数值积分链**：把噪声波形 B(s)=cos(ωs+φ) 在细网格上
                    逐点采样 → 在 t/2 处翻转符号（π 脉冲）→ 梯形积分得 Φ(φ)
                    → 对均匀初相 φ 取 ⟨Φ²⟩ → 乘 (γb/ω)² 归一化恢复。
        ——方法学独立：golden 来自**解析推导**（∫cos 的闭式 + φ 平均恒等式）；
        candidate **不使用任何闭式**，纯靠「采样 + 梯形积分 + 数值 φ 平均」。
        实测 rel≈1e-7…1e-9（时间/φ 网格离散化引入，非机器精度 1e-16）。

🔴 物理意义（承 QS-M2 蓝图 §4 · 平台缺口 G4「自旋相干时间建模」）：
  回波相位方差对低频（DC）噪声是**四阶抑制** ⟨Φ²⟩_echo ~ (ωt)⁴/32，
  而 FID 仅**二阶** ⟨Φ²⟩_fid ~ (ωt)²。这正是**动力学去耦（DD）**提升
  相干时间的物理根因。本锚把「回波方差闭式」钉进账本 ⇒ 任何对 DD 物理的
  误改（如把四阶写成二阶）都会被机器判红。

🔴 与 B474 的关系（**不同物理量**，非重复）：
  · B474：灵敏度 η 的**线宽 FOM 路径**（时间域包络 FWHM → σ_f → η）。
  · B475：**相干时间建模**本身（回波相位方差闭式 ↔ 数值时域积分）。
  两锚的 candidate 走不同物理对象（η 标量 vs 相位方差函数族），方法学互不重叠。

🔴 **为何只一锚（诚实规模 · 吃狗粮）**：QS-M2 另含
  · 「四源噪声正交合成」（不等式/平方和恒等 ⇒ 属 smoke，非独立标量物理量）；
  · 「CPMG 滤波函数 F_n(ω→0)=0」（极限恒等 ⇒ 属 smoke）；
  二者归 `run_qs_m2_smoke` 覆盖，**不登记为 B 锚**（避免「非物理量充数」）。
本批如实只登记 B475 一锚（同 B472/B473/B474 的「宁可少，不越级谎报」纪律）。

🔴 纪律：
· 本模块**顶层只 import numpy/math**（不触发 scipy）。
· golden 与 candidate 是**两种结构不同的算法**（非「同式异写」，已实测残差
  1e-7…1e-9 远高于机器精度 1e-16）；进报告数字一律**现算**。
· 🔴 **锚携带可扰动参数**（`B475_DEFAULT_PARAMS`）：omega_t（无量纲归一频率）
  单调、非零响应 ⇒ 反自证桩护栏 `candidate_responds` 可证伪。
"""
from __future__ import annotations

import functools
import math

import numpy as np


# ===========================================================================
# B475 · 回波相位方差：闭式 ↔ 时间域数值积分互验
# ===========================================================================
def echo_variance_golden(omega_t: float) -> float:
    """golden：闭式 ⟨Φ²⟩_echo = 2(1−cos(ωt/2))²（归一化口径，丢 (γb/ω)²）。

    🔴 DC 极限 ~(ωt)⁴/32（**四阶**）；用 haversine 形式避免小 x 灾难性抵消。
    """
    s = math.sin(omega_t / 4.0)
    return 2.0 * (2.0 * s * s) ** 2


def echo_variance_candidate(omega_t: float, t: float = 1.0,
                            n_phi: int = 4000, n_t: int = 40000) -> float:
    """candidate：**时间域数值积分链**（方法学独立 · 不用任何闭式）。

    逐步数值链（每步独立数值操作）：
      ① 时间网格 s∈[0,t]（n_t 段）+ 均匀初相 φ_k（n_phi 点）；
      ② 噪声波形 B(s;φ)=cos(ω s + φ)，ω=omega_t/t；
      ③ **π 脉冲**：s>t/2 处符号翻转（Hahn 回波时序）；
      ④ 梯形积分 Φ(φ_k)=∫ sign(s)·B(s;φ_k) ds（逐 k 向量化）；
      ⑤ 对 φ 取 ⟨Φ²⟩，再乘 (γb/ω)²（这里 γb=1 ⇒ 乘 ω²）恢复归一化口径。
    网格离散 ⇒ 残差 O(Δt·ω + 1/n_phi)（即本锚 rel≈1e-7…1e-9 的来源）。
    """
    if omega_t <= 0.0:
        raise ValueError("omega_t 必须 > 0")
    if n_t < 2 or n_phi < 2:
        raise ValueError("网格点数 n_t/n_phi 必须 ≥ 2")
    w = omega_t / t
    s = np.linspace(0.0, t, n_t + 1)
    ds = s[1] - s[0]
    sign = np.where(s <= t / 2.0, 1.0, -1.0)
    phis = (np.arange(n_phi) + 0.5) * 2.0 * math.pi / n_phi
    # (n_phi, n_t+1) 波形矩阵 × 符号翻转
    b = np.cos(w * s[None, :] + phis[:, None]) * sign[None, :]
    phi = np.sum((b[:, 1:] + b[:, :-1]) * 0.5 * ds, axis=1)   # 梯形积分
    return float(np.mean(phi ** 2)) * w * w


# ===========================================================================
# 锚的物理设计参数（B475 的 default_params 真源 · 单一出处）
# ===========================================================================
# 🔴 为什么必须带**数值参数**（v0.9.216 吃狗粮抓到 · 反自证桩护栏盲区）：
#   反自证桩护栏的行为判据 `candidate_responds` 需**扰动数值参数**方可证伪。
#   omega_t（无量纲 ωt）对 ⟨Φ²⟩ 单调、非零响应（在非整数倍 2π 处）⇒
#   任一 ±10% 扰动均使候选值变化远超阈值。
B475_DEFAULT_PARAMS = {
    "omega_t": 2.0,        # 无量纲 ωt（归一化频率×时间）；非 2π 整数倍 ⇒ 响应非零
    "t": 1.0,              # 演化时间（归一化单位）
}


# ===========================================================================
# 记忆化入口（part7.py 顶层引用；纯函数 ⇒ 数值逐位不变）
# ===========================================================================
@functools.lru_cache(maxsize=256)
def _b475_golden_c(omega_t: float) -> float:
    return echo_variance_golden(omega_t)


@functools.lru_cache(maxsize=256)
def _b475_cand_c(omega_t: float, t: float) -> float:
    return echo_variance_candidate(omega_t, t)


def golden_b475(omega_t: float = 2.0, t: float = 1.0) -> float:
    """part7.py 顶层引用的 golden 入口（**接受 default_params 关键字**）。

    `golden.py::golden_value` 以 `fn(**params)` 调用 ⇒ 须带同名形参。
    """
    return _b475_golden_c(omega_t)


def cand_b475(omega_t: float = 2.0, t: float = 1.0) -> float:
    """candidate 入口（_adapter_p4 用）——接受 default_params 关键字。"""
    return _b475_cand_c(omega_t, t)
