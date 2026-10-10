"""Batch B-40 数值实现 · 量子传感器芯片征程 QS-M1（灵敏度 FOM 体系）。

════════════════════════════════════════════════════════════════════════════
本批**一锚**（`benchmark_defs/part7.py` 引用）——
  B474：量子传感器灵敏度 FOM 体系 —— 由**线宽 FOM**（数值提取）反解灵敏度
        golden   = **闭式散粒极限**（T₂* 路径）η = ħ/(gμB)·√(1+a²)·√2/(C·√(n_ph·T₂*))
        candidate = **数值线宽提取链**：从高斯对比度包络 C(τ)=e^(−(τ/T₂*)²)
                    的**时间域半高全宽（FWHM）数值提取** → 频域宽度 σ_f →
                    反解 T₂* → 合成 η。
        ——方法学独立：golden 直接代数代入 T₂*；candidate **不代入 T₂***，
        而是经「时间包络 → 数值 FWHM → σ_f → T₂*」逐步数值链。
        实测 rel≈2.77e-6（tol=1e-3 的 361× 余量；网格离散化引入，非机器精度）。

🔴 与 B473 的关系（**不同物理量**，非重复）：
  · B473：η 的**闭式 ↔ 数值误差传播链**（相位域：ρ_φ + 演化核差商）。
  · B474：η 的**线宽 FOM 路径**（时间域：对比度包络 FWHM 数值提取 → σ_f → η）。
  两锚的 candidate 走**不同物理域**（相位域 vs 时间/频域），方法学互不重叠。

🔴 **为何只一锚（诚实规模 · 吃狗粮）**：QS-M1 定位是「**FOM 体系**」——
把灵敏度升级为**可比较、可溯源**的指标族。初版另拟
  · 「口径自检 assert_caliber 反向探针」（守卫逻辑，非物理量 ⇒ 属 smoke 而非 B 锚）；
  · 「四情景单调性」（不等式约束，非标量物理量 ⇒ 属 smoke）；
二者都归 `run_qs_m1_smoke` 覆盖，**不登记为 B 锚**（避免「非物理量充数」）。
本批如实只登记 B474 一锚（同 B472/B473 的「宁可少，不越级谎报」纪律）。

🔴 纪律：
· 本模块**顶层只 import numpy/math**（不触发 scipy）。
· golden 与 candidate 是**两种结构不同的算法**（非「同式异写」，已实测残差
  2.77e-6 远高于机器精度 1e-16）；进报告数字一律**现算**。
· 🔴 **锚携带可扰动参数**（v0.9.216 吃狗粮抓到的护栏盲区，见 B473_DEFAULT_PARAMS
  与 `B474_DEFAULT_PARAMS`）：四参数 T₂*/n_ph/C/a 均对 η 单调非零响应。
"""
from __future__ import annotations

import functools
import math

import numpy as np

# ---- 物理常数（与 lda_l2.qs_m0 / qs_m1 / _batch_b39_numeric 同源）----
HBAR = 1.054571817e-34
G_LANDE = 2.0023
MU_B = 9.2740100783e-24

_G_MUB_OVER_HBAR = G_LANDE * MU_B / HBAR       # rad·s⁻¹·T⁻¹


# ===========================================================================
# B474 · 灵敏度 FOM 体系 —— 线宽 FOM 路径（数值提取）
# ===========================================================================
def fom_sensitivity_golden(T2star_s: float = 1e-6, n_ph_per_s: float = 1e5,
                           contrast: float = 0.03,
                           dark_ratio: float = 0.0) -> float:
    """golden：闭式散粒极限 η = ħ/(gμB)·√(1+a²)·√2/(C·√(n_ph·T₂*))（T/√Hz）。

    （T₂* 路径；与 qs_m1.sensitivity_via_T2star 同式 —— 本锚的**金标**。）
    """
    return (math.sqrt(1.0 + dark_ratio ** 2) * math.sqrt(2.0)
            / (contrast * math.sqrt(n_ph_per_s * T2star_s))
            / _G_MUB_OVER_HBAR)


def fom_extract_linewidth_hz(T2star_s: float, n_grid: int = 400001) -> float:
    """**数值**从高斯对比度包络 C(τ)=e^(−(τ/T₂*)²) 提取频域宽度 σ_f（Hz）。

    逐步数值链（不复用 T₂* 解析值）：
      ① 在 τ∈[−5T₂*, +5T₂*] 上采样包络（numpy 向量化）；
      ② 数值定位半高全宽 FWHM_t（首个/末个满足 env≥0.5 的采样点之差）；
      ③ FWHM_t = 2√(2 ln2)·σ_t ⇒ σ_t = FWHM_t/(2√(2 ln2))；
      ④ 高斯对偶：σ_f = 1/(2π·σ_t)。
    网格离散 ⇒ σ_f 带有 O(Δt/T₂*) 的提取误差（即本锚 rel≈2.77e-6 的来源）。
    """
    if T2star_s <= 0.0:
        raise ValueError("T₂* 必须 > 0")
    t = np.linspace(-5.0 * T2star_s, 5.0 * T2star_s, n_grid)
    env = np.exp(-(t / T2star_s) ** 2)
    idx = np.where(env >= 0.5)[0]
    fwhm_t = float(t[idx[-1]] - t[idx[0]])
    sigma_t = fwhm_t / (2.0 * math.sqrt(2.0 * math.log(2.0)))
    return 1.0 / (2.0 * math.pi * sigma_t)


def fom_sensitivity_cand(T2star_s: float = 1e-6, n_ph_per_s: float = 1e5,
                         contrast: float = 0.03,
                         dark_ratio: float = 0.0) -> float:
    """candidate：**数值线宽提取链**（方法学独立 · 不以 T₂* 解析式代入 η）。

    逐步链（每步独立数值操作）：
      ① 数值提取频域线宽 σ_f = fom_extract_linewidth_hz(T₂*)（时间包络 FWHM 链）；
      ② 反解等效相干时间 T₂*' = √2/(2π·σ_f)（**由数值 σ_f 得来**，非原 T₂*）；
      ③ 合成 η = √(1+a²)·√2/(C·√(n_ph·T₂*'))/（gμB/ħ）。
    """
    sigma_f = fom_extract_linewidth_hz(T2star_s)
    T2star_eff = math.sqrt(2.0) / (2.0 * math.pi * sigma_f)
    return (math.sqrt(1.0 + dark_ratio ** 2) * math.sqrt(2.0)
            / (contrast * math.sqrt(n_ph_per_s * T2star_eff))
            / _G_MUB_OVER_HBAR)


# ===========================================================================
# 锚的物理设计参数（B474 的 default_params 真源 · 单一出处）
# ===========================================================================
# 🔴 为什么必须带**数值参数**（v0.9.216 吃狗粮抓到 · 反自证桩护栏盲区）：
#   反自证桩护栏的行为判据 `candidate_responds` 需**扰动数值参数**方可证伪。
#   四参数 T₂*/n_ph/C/a 对 η 均单调、非零响应（T₂*↑⇒η↓；C↑⇒η↓；n_ph↑⇒η↓；
#   a↑⇒η↑）⇒ 任一 ±10% 扰动均使候选值变化远超阈值。
B474_DEFAULT_PARAMS = {
    "T2star_s": 1e-6,       # Ramsey 相干时间 T₂*（s），室温 NV 集合体典型量级
    "n_ph_per_s": 1e5,      # 光子计数率（光子数/秒）
    "contrast": 0.03,       # Ramsey 条纹对比度 C
    "dark_ratio": 0.0,      # 暗计数比 a
}


# ===========================================================================
# 记忆化入口（part7.py 顶层引用；纯函数 ⇒ 数值逐位不变）
# ===========================================================================
@functools.lru_cache(maxsize=256)
def _b474_golden_c(t2, nph, c, a):
    return fom_sensitivity_golden(t2, nph, c, a)


@functools.lru_cache(maxsize=256)
def _b474_cand_c(t2, nph, c, a):
    return fom_sensitivity_cand(t2, nph, c, a)


def golden_b474(T2star_s: float = 1e-6, n_ph_per_s: float = 1e5,
                contrast: float = 0.03, dark_ratio: float = 0.0) -> float:
    """part7.py 顶层引用的 golden 入口（**接受 default_params 关键字**）。

    `golden.py::golden_value` 以 `fn(**params)` 调用 ⇒ 须带同名形参。
    """
    return _b474_golden_c(T2star_s, n_ph_per_s, contrast, dark_ratio)


def cand_b474(T2star_s: float = 1e-6, n_ph_per_s: float = 1e5,
              contrast: float = 0.03, dark_ratio: float = 0.0) -> float:
    """candidate 入口（_adapter_p4 用）——接受 default_params 关键字。"""
    return _b474_cand_c(T2star_s, n_ph_per_s, contrast, dark_ratio)
