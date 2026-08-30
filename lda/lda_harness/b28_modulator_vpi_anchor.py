"""LDA MZM 调制器半波电压 Vπ 锚 B28（v0.9.1 · 电光相位调制 · 钉子 D1b=A）。

背景（锚缺口分析 2026-08-30 · 钉子 D1b=A）：
  LDA 光子侧器件库尚缺有源调制器的核心指标。商业 EDA（Lumerical
  INTERCONNECT、Ansys OptoDesigner）对 MZM 的半波电压 Vπ 是必标量；
  B20 已覆盖 MZI 干涉 FSR（无源），B28 补齐有源调制器的 Vπ（电光
  相位调制的确定性物理定律），闭合「MZI 无源+有源」双锚。

物理定律（线性电光 / Pockels 效应，确定性麦克斯韦-光学关系，零模型假设）：
  横向电极电场 E(z) = V(z)/d
  折射率变化 Δn(z) = −½·n_eff³·r_eff·Γ(z)·E(z)      （Pockels，r_eff=r33 等）
  单臂相位累积 Δφ_arm(V) = (2π/λ₀)·∫₀ᴸ Δn(z) dz
                          = −(π·n_eff³·r_eff/(λ₀·d))·∫₀ᴸ Γ(z)·V(z) dz
  推挽 MZM：Δφ_total = 2·Δφ_arm（两臂反相）；传输 T=cos²(Δφ_arm)
  半波电压 Vπ：使 T 从最大(1)→最小(0)，需 Δφ_arm(Vπ)=π/2
  均匀段闭式（Γ(z)=const）：  Vπ = λ₀·d / (2·n_eff³·r_eff·Γ·L)

红线（严格保持 · LLM 不进判决路径）：
  判决 = 死标量比对，且是**同一物理定律的两种独立算法互证**：
    ① 解析闭式（均匀段直接公式，精确）；
    ② 沿程积分 + 二分（任意 Γ(z) 通用；均匀段剖分守恒 → 退化等于闭式）。
  两者在均匀段应机器精度一致（|Δ| ≤ cross_tol）→ 非 AI ground。
  实证量级（LiNbO3 x-cut MZM Vπ≈3.8V）仅作 honest-sanity，不进死标量
  判决（B 级纯物理定律锚定位，与 E 级实证语料锚区分）。

实现约束：纯标准库（math），零第三方依赖——与项目「核心零依赖优雅降级」
铁律一致（FDTD 内核同纪律）。
"""
from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

# ---- 默认工艺 / 几何参数（公开文献典型量级，发动期 PDK 校准替换） ----
LAMBDA_VAC_UM = 1.55       # 工作波长（C 波段，µm）
N_EFF = 2.2                # 波导有效折射率（LiNbO3 脊波导典型 ~2.2）
R_EFF = 30.8e-12           # 有效电光系数（LiNbO3 r33，m/V）
GAMMA = 0.5                # 光-电模场重叠因子（行波电极典型 ~0.5）
L_UM = 10000.0             # 调制相互作用长度（10 mm = 1 cm，µm）
D_UM = 8.0                 # 电极间隙（µm）
_N_SEGMENTS = 2000         # 积分剖分段数（均匀段剖分守恒，与闭式一致）


def mzm_vpi_analytic(lambda_vac_um: float = LAMBDA_VAC_UM,
                     n_eff: float = N_EFF,
                     r_eff: float = R_EFF,
                     gamma: float = GAMMA,
                     L_um: float = L_UM,
                     d_um: float = D_UM) -> float:
    """解析闭式半波电压 Vπ（推挽 MZM，Pockels 效应）。

    Vπ = λ₀·d / (2·n_eff³·r_eff·Γ·L)   （单位统一为米，V 量纲自洽）
    这是 B28 的 golden 确定性值，也是 harness 默认 ReferenceCandidate
    自洽 PASS 的基准点。
    """
    lam = lambda_vac_um * 1e-6
    L = L_um * 1e-6
    d = d_um * 1e-6
    return (lam * d) / (2.0 * (n_eff ** 3) * r_eff * gamma * L)


def _phase_arm(lam_m: float, n_eff: float, r_eff: float, d_m: float,
               V: float, gamma_profile: Sequence[Tuple[float, float, float]]) -> float:
    """单臂相位累积 Δφ_arm(V)（沿程积分，对任意 Γ(z) 通用）。

    Δφ_arm = (π·n_eff³·r_eff·V / (λ₀·d)) · Σ Γ_i·Δz_i
    均匀段 Σ Γ_i·Δz_i = Γ·L → 退化为闭式；剖分守恒保证与解析一致。
    """
    total = 0.0
    for z0, z1, g in gamma_profile:
        total += g * (z1 - z0)
    return (math.pi * (n_eff ** 3) * r_eff * V / (lam_m * d_m)) * total


def mzm_vpi_integral(lambda_vac_um: float = LAMBDA_VAC_UM,
                     n_eff: float = N_EFF,
                     r_eff: float = R_EFF,
                     gamma: float = GAMMA,
                     L_um: float = L_UM,
                     d_um: float = D_UM,
                     n_segments: int = _N_SEGMENTS) -> float:
    """沿程积分 + 二分半波电压（算法②，独立于闭式的通用 ORACLE）。

    对 Γ(z) 分段常数剖分，积分得 Δφ_arm(V) 的线性映射，二分求根使
    Δφ_arm(V)=π/2。均匀段时二分收敛点等于解析闭式（机器精度）。
    """
    lam = lambda_vac_um * 1e-6
    L = L_um * 1e-6
    d = d_um * 1e-6
    dz = L / n_segments
    profile = [(i * dz, (i + 1) * dz, gamma) for i in range(n_segments)]
    lo, hi = 0.0, 1000.0  # Vπ 搜索区间（覆盖所有合理器件）
    for _ in range(100):  # 二分 100 次 → 1e-30 相对精度，足够
        mid = 0.5 * (lo + hi)
        ph = _phase_arm(lam, n_eff, r_eff, d, mid, profile)
        if ph < math.pi / 2.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def b28_modulator_vpi(lambda_vac_um: float = LAMBDA_VAC_UM,
                     n_eff: float = N_EFF,
                     r_eff: float = R_EFF,
                     gamma: float = GAMMA,
                     L_um: float = L_UM,
                     d_um: float = D_UM) -> float:
    """B28 golden：解析闭式半波电压 Vπ（确定性，harness 判决基准）。

    语义：给定波导/电极几何与材料电光系数，Vπ 是唯一确定值——任何人
    重跑同一组参数得到同一数字（可复现性 = 物理定律锚的判决前提）。
    物理正确性由 `b28_modulator_vpi_report()` 中的积分交叉验证守护
    （非本函数职责）。
    """
    return mzm_vpi_analytic(lambda_vac_um=lambda_vac_um, n_eff=n_eff,
                            r_eff=r_eff, gamma=gamma, L_um=L_um, d_um=d_um)


def b28_vpi_vs_length_scan(lambda_vac_um: float = LAMBDA_VAC_UM,
                          n_eff: float = N_EFF,
                          r_eff: float = R_EFF,
                          gamma: float = GAMMA,
                          d_um: float = D_UM,
                          lengths_um: Tuple[float, ...] = (5000.0, 10000.0,
                                                          20000.0, 40000.0)
                          ) -> Dict[str, object]:
    """相互作用长度 → Vπ 扫描（调制器设计空间，商业演示素材）。

    回答「把调制臂加长到 4cm，Vπ 能压到多少」这类客户真正关心的问题。
    同时给出单调性断言：L 增大 → Vπ 单调下降（否则锚的判别力存疑）。
    """
    rows = []
    for L in lengths_um:
        v = mzm_vpi_analytic(lambda_vac_um=lambda_vac_um, n_eff=n_eff,
                             r_eff=r_eff, gamma=gamma, L_um=L, d_um=d_um)
        rows.append({"L_um": L, "Vpi_volts": round(v, 6)})
    v_series = [r["Vpi_volts"] for r in rows]
    monotone = all(v_series[i] > v_series[i + 1]
                   for i in range(len(v_series) - 1))
    return {"rows": rows, "monotone_decreasing": monotone}


def b28_modulator_vpi_report(lambda_vac_um: float = LAMBDA_VAC_UM,
                             n_eff: float = N_EFF,
                             r_eff: float = R_EFF,
                             gamma: float = GAMMA,
                             L_um: float = L_UM,
                             d_um: float = D_UM,
                             n_segments: int = _N_SEGMENTS,
                             cross_tol: float = 1e-6) -> Dict[str, object]:
    """B28 完整报告：解析闭式 ↔ 沿程积分+二分 交叉验证 + 判别力扫描
    + 实证量级 sanity（诚实边界）。

    cross_check_ok 是 B28 的核心判决：两种独立算法（解析公式 / 数值
    积分+二分求根）在同一物理定律上的偏差 ≤ cross_tol（机器精度级）。
    """
    v_an = mzm_vpi_analytic(lambda_vac_um=lambda_vac_um, n_eff=n_eff,
                            r_eff=r_eff, gamma=gamma, L_um=L_um, d_um=d_um)
    v_int = mzm_vpi_integral(lambda_vac_um=lambda_vac_um, n_eff=n_eff,
                             r_eff=r_eff, gamma=gamma, L_um=L_um, d_um=d_um,
                             n_segments=n_segments)
    delta_abs = abs(v_an - v_int)
    # 实证量级 sanity（LiNbO3 x-cut MZM，文献 Vπ≈3-5V）—不进死标量判决
    v_lnb03 = mzm_vpi_analytic(lambda_vac_um=1.55, n_eff=2.2,
                               r_eff=30.8e-12, gamma=0.5, L_um=10000.0,
                               d_um=8.0)
    scan = b28_vpi_vs_length_scan(lambda_vac_um=lambda_vac_um, n_eff=n_eff,
                                  r_eff=r_eff, gamma=gamma, d_um=d_um)
    return {
        "spec": {"lambda_vac_um": lambda_vac_um, "n_eff": n_eff,
                 "r_eff_m_per_V": r_eff, "gamma": gamma,
                 "L_um": L_um, "d_um": d_um},
        "Vpi_analytic_volts": round(v_an, 6),
        "Vpi_integral_volts": round(v_int, 6),
        "cross_delta": round(delta_abs, 9),
        "cross_tol": cross_tol,
        "cross_check_ok": delta_abs <= cross_tol,
        "empirical_sanity": {
            "lnb03_xcut_Vpi_volts": round(v_lnb03, 4),
            "reference_range_volts": [3.0, 5.0],
            "in_range": 3.0 <= v_lnb03 <= 5.0,
        },
        "monotone_in_L": scan["monotone_decreasing"],
        "length_scan": scan["rows"],
        "note": ("B28 MZM 调制器半波电压锚：解析闭式 Vπ=λd/(2n³rΓL) ↔ 沿程"
                 "积分+二分（通用 Γ(z)）双算法互证，死标量比对；LLM 不进"
                 "判决路径。载体为 Pockels 电光相位调制确定性物理定律，"
                 "零模型假设；实证量级仅作 honest-sanity。"),
    }
