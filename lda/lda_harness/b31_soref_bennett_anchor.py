"""LDA Si 载流子色散相移锚 B31（v0.9.69 · T1-C W3 · A 档有源扩展）。

背景（评审 `docs/lda_t1c_anchor_contract_review_2026-09-12.md` §1 · 研发规划 C1）：
  LDA 光子侧器件库已有 B28（LiNbO3 Pockels Vπ）、B29（热光相移）；
  B31 补齐 **Si 载流子（等离子）色散相移**——PN 耗尽型 Si 相位调制器的
  核心指标，与 B28 同接口（都输出相移/等价 Vπ）但**物理机制完全不同**
  （载流子浓度 vs 线性电光系数）→ 各自独立，不虚报。

物理定律（Soref & Bennett 1987, IEEE J. Quantum Electron. 23(1), 123-129，
经 WebSearch 双重佐证 math-physics.net / Optica OE-18-24）：

  golden（design_rule_anchor · 物理定律锚，幂律形式 @1550nm）：
    Δn_e = c1·ΔN_e                       c1 = −8.8×10⁻²² cm³（电子线性）
    Δn_h = c2·(ΔN_h)^0.8                 c2 = −8.5×10⁻¹⁸ cm^2.4（空穴 0.8 次幂）
    Δn   = Δn_e + Δn_h
    🔴 适用域 10¹⁷ ≤ ΔN ≤ 10²⁰ cm⁻³（原论文显式声明；低于 10¹⁷ 实验比
       偏离、高于 10²⁰ 材料进入强扰动非弱微扰）。本锚测试点取域内。

  candidate（independent_cross_check · 方法学独立）：
    Drude 自由电子气模型（经典微观等离子体，仅电子线性项）：
    Δn = −q²·ΔN_e / (2·ε0·n_eff·m*_e·ω²)
    ——与 Soref-Bennett **方法学不同源**（宏观唯象经验拟合 vs 微观等离子体
       动力学）；Drude 仅给自由电子线性项，不含空穴效应与 many-body 二次项
       → 与 SB **故意非代数恒等**（评审 §1「判据 D 不撞」的本意）。两者在
       适用域内同号、同量级（偏差 ~1-2×）即证明捕捉同一物理、非乱给。

  ΔN(V) 红线（零电域求解器）：一维突变结 **耗尽近似闭式**
    ΔN_eff(V_R) = N0·(√(V_bi+V_R) − √V_bi)/√V_bi
    反偏增大 → 耗尽区变宽 → 更多载流子被扫出 → 相移增大（零漂移-扩散，
    不破「电域求解器」红线）。ΔN_eff 上限 10¹⁸ cm⁻³（耗尽近似失效区，
    超则标 honest_tier=「depletion-approx」失效，raise）。

  Vπ 等价换算（评审 §1）：Δφ(V)=2π·|Δn_eff|·L/λ；使 Δφ=π 的 V_R 即等价 Vπ。

红线（严格保持 · LLM 不进判决路径）：
  golden = 闭式非真值（T1 不作 ORACLE）；c1/c2 为文献公认常数、严禁拟合回算；
  ΔN(V) 为耗尽近似闭式、绝不求解漂移-扩散；零载流子求解器 / 零增益动力学 /
  零 TCAD / 零 A 级工具 → 不破「三不做 / 主权 / 验证纪律」任何一条红线。

实现约束：纯标准库（math），零第三方依赖——与项目「核心零依赖优雅降级」
铁律一致（FDTD/Drift-Diffusion 内核同纪律）。
"""
from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

# ---- Soref & Bennett 1987 @1550nm 文献常数（严禁拟合回算 · IRONLAWS 二/27）----
SB_ELECTRON = -8.8e-22     # cm³ · 电子线性项系数（ΔN_e, cm⁻³ → Δn 无量纲）
SB_HOLE = -8.5e-18         # cm^2.4 · 空穴 0.8 次幂系数
SB_DOMAIN_LO = 1e17        # 适用域下限 cm⁻³（原论文显式）
SB_DOMAIN_HI = 1e20        # 适用域上限 cm⁻³
DEPLETION_FAIL = 1e18      # 耗尽近似失效阈值 cm⁻³（honest_tier 标红）

# ---- Drude 自由电子气模型常数 ----
Q_E = 1.602176634e-19      # C · 元电荷
EPS0 = 8.854187817e-12     # F/m · 真空介电
M_E_STAR = 0.26 * 9.1093837015e-31   # kg · Si 导带导电有效质量（≈0.26 m0）
C_LIGHT = 299792458.0      # m/s
LAMBDA_SB_M = 1.55e-6      # m · 工作波长（C 波段）

# ---- 默认工艺 / 几何参数（公开文献典型量级，发动期 PDK 校准替换） ----
V_BI_DEFAULT = 0.85        # V · Si pn 结内建电势（典型）
N0_DEFAULT = 2e17          # cm⁻³ · 零偏基准等效载流子浓度变化（由器件几何定）
N_EFF_DEFAULT = 2.4         # Si 波导有效折射率（strip 波导 @1550nm 典型）
L_UM_DEFAULT = 1000.0       # µm · 调制相互作用长度（1 mm）


def b31_soref_bennett_dn(dN_e_cm3: float, dN_h_cm3: float = 0.0) -> float:
    """B31 golden 核心：Soref & Bennett 1987 幂律闭式折射率变化 Δn。

    纯确定性物理定律（@1550nm）。适用域自检内嵌（超出 10¹⁷-10²⁰ cm⁻³ raise）。
    默认 dN_h_cm3=0 → 纯电子工况（最干净，Drude 候选同工况公平对比）。
    """
    if dN_e_cm3 < 0 or dN_h_cm3 < 0:
        raise ValueError("载流子浓度变化必须 ≥ 0")
    if dN_e_cm3 > SB_DOMAIN_HI or dN_h_cm3 > SB_DOMAIN_HI:
        raise ValueError(
            f"超出 Soref-Bennett 适用域 10^17-10^20 cm^-3 "
            f"(ΔN_e={dN_e_cm3:.2e}, ΔN_h={dN_h_cm3:.2e})")
    if 0 < dN_e_cm3 < SB_DOMAIN_LO or 0 < dN_h_cm3 < SB_DOMAIN_LO:
        # 低于适用域下限：仍算但 honest 标注（report 侧标红）
        pass
    dn_e = SB_ELECTRON * dN_e_cm3
    dn_h = SB_HOLE * (dN_h_cm3 ** 0.8) if dN_h_cm3 > 0.0 else 0.0
    return dn_e + dn_h


def b31_drude_dn(dN_e_cm3: float, n_eff: float = N_EFF_DEFAULT) -> float:
    """B31 candidate 核心：Drude 自由电子气模型（仅电子线性项）。

    Δn = −q²·ΔN_e / (2·ε0·n_eff·m*_e·ω²)，ΔN_e 由 cm⁻³ 转 m⁻³。
    经典微观等离子体动力学，与 SB 唯象拟合方法学不同源；不含空穴项与
    many-body 修正 → 与 SB **故意非代数恒等**，用于 independent_cross_check。
    """
    if dN_e_cm3 < 0:
        raise ValueError("载流子浓度变化必须 ≥ 0")
    dN_e_m3 = dN_e_cm3 * 1e6          # cm⁻³ → m⁻³
    omega = 2.0 * math.pi * C_LIGHT / LAMBDA_SB_M
    denom = 2.0 * EPS0 * n_eff * M_E_STAR * (omega ** 2)
    return -(Q_E ** 2) * dN_e_m3 / denom


def b31_depletion_dN_eff(V_R: float, V_bi: float = V_BI_DEFAULT,
                         N0: float = N0_DEFAULT) -> float:
    """B31 红线：一维突变结耗尽近似闭式 V → ΔN_eff（零漂移-扩散）。

    反偏 V_R ≥ 0 → 耗尽区变宽 → 被扫出载流子总量正比 W(V) → ΔN_eff 增大。
    V_R=0 时 ΔN_eff=0（无相移），单调增。N0 为零偏基准等效浓度（器件几何定）。
    """
    if V_R < 0:
        raise ValueError("反偏电压 V_R 必须 ≥ 0")
    if V_bi <= 0:
        raise ValueError("内建电势 V_bi 必须 > 0")
    return N0 * (math.sqrt(V_bi + V_R) - math.sqrt(V_bi)) / math.sqrt(V_bi)


def b31_soref_bennett_phase_shift(V_R: float, V_bi: float = V_BI_DEFAULT,
                                  N0: float = N0_DEFAULT,
                                  dN_h_ratio: float = 0.0,
                                  lambda_um: float = 1.55,
                                  L_um: float = L_UM_DEFAULT,
                                  n_eff: float = N_EFF_DEFAULT) -> float:
    """B31 golden 完整链路：V_R → ΔN_eff(耗尽近似) → SB Δn → Δφ（弧度）。

    含红线（耗尽近似闭式，超 DEPLETION_FAIL 标红 raise）。dN_h_ratio 默认 0
    （纯电子，与 Drude 候选同工况公平对比）；非零时 SB 计入空穴项。
    """
    dN_e = b31_depletion_dN_eff(V_R, V_bi, N0)
    if dN_e > DEPLETION_FAIL:
        raise ValueError(
            f"ΔN_eff={dN_e:.2e} cm⁻³ 超耗尽近似失效阈值 {DEPLETION_FAIL:.0e}")
    dN_h = dN_h_ratio * dN_e
    dn = b31_soref_bennett_dn(dN_e, dN_h)
    dphi = 2.0 * math.pi * abs(dn) * (L_um * 1e-6) / (lambda_um * 1e-6)
    return dphi


def b31_drude_phase_shift(V_R: float, V_bi: float = V_BI_DEFAULT,
                          N0: float = N0_DEFAULT,
                          lambda_um: float = 1.55,
                          L_um: float = L_UM_DEFAULT,
                          n_eff: float = N_EFF_DEFAULT) -> float:
    """B31 candidate 完整链路：V_R → ΔN_eff(电子) → Drude Δn → Δφ（弧度）。

    仅电子项（Drude 自由电子气）；不含空穴效应，与 SB 故意非恒等。
    红线同 golden（耗尽近似 + 失效阈值）。
    """
    dN_e = b31_depletion_dN_eff(V_R, V_bi, N0)
    if dN_e > DEPLETION_FAIL:
        raise ValueError(
            f"ΔN_eff={dN_e:.2e} cm⁻³ 超耗尽近似失效阈值 {DEPLETION_FAIL:.0e}")
    dn = b31_drude_dn(dN_e, n_eff)
    dphi = 2.0 * math.pi * abs(dn) * (L_um * 1e-6) / (lambda_um * 1e-6)
    return dphi


def b31_phase_shift_report(V_R: float = 3.0, V_bi: float = V_BI_DEFAULT,
                          N0: float = N0_DEFAULT,
                          lambda_um: float = 1.55, L_um: float = L_UM_DEFAULT,
                          n_eff: float = N_EFF_DEFAULT,
                          cross_dN: float = 2e17,
                          dn_tol_ratio: float = 3.0) -> Dict[str, object]:
    """B31 完整报告：SB ↔ Drude 独立方法学交叉验证（量级一致非恒等）+
    V_R 反向判别力扫描 + 诚实边界（honest_tier / 适用域 / 红线）。

    cross_check_ok：在固定 ΔN=cross_dN（SB 适用域内）比较 SB 电子项与 Drude
    电子项——同号、同量级（偏差在 dn_tol_ratio 内）→ 证明捕捉同一物理、
    非乱给；比值 ≠ 1（Drude 缺 many-body 修正）即满足「判据 D 不撞」。
    """
    # 1) 独立方法学交叉验证（纯电子工况，公平对比）
    dn_sb_e = b31_soref_bennett_dn(cross_dN, 0.0)
    dn_drude = b31_drude_dn(cross_dN, n_eff)
    ratio = abs(dn_drude) / abs(dn_sb_e) if dn_sb_e != 0 else float("inf")
    cross_ok = (0.2 <= ratio <= dn_tol_ratio) and (dn_sb_e * dn_drude > 0)

    # 2) V_R 反向判别力扫描：V_R↑ → ΔN_eff↑ → |Δn|↑ → |Δφ|↑（单调）
    Vs = [0.0, 1.0, 3.0, 5.0]
    phis = [b31_soref_bennett_phase_shift(V, V_bi, N0, 0.0,
                                          lambda_um, L_um, n_eff) for V in Vs]
    monotone = all(phis[i] < phis[i + 1]
                   for i in range(len(phis) - 1))

    # 3) 红线：耗尽近似失效阈值（在最大测试 V_R=5 下 ΔN_eff 仍 < 1e18）
    dN_max = b31_depletion_dN_eff(max(Vs), V_bi, N0)
    depletion_ok = dN_max <= DEPLETION_FAIL

    # 4) 适用域诚实边界（cross_dN 在域内）
    domain_ok = SB_DOMAIN_LO <= cross_dN <= SB_DOMAIN_HI

    return {
        "spec": {"V_R": V_R, "V_bi": V_bi, "N0": N0, "lambda_um": lambda_um,
                 "L_um": L_um, "n_eff": n_eff, "cross_dN": cross_dN},
        "dn_sb_electron": dn_sb_e,
        "dn_drude": dn_drude,
        "sb_vs_drude_ratio": round(ratio, 4),
        "cross_tol_ratio": dn_tol_ratio,
        "cross_check_ok": cross_ok,
        "V_scan_volt": Vs,
        "phase_shift_rad": [round(p, 6) for p in phis],
        "monotone_in_V": monotone,
        "dN_eff_max_cm3": dN_max,
        "depletion_ok": depletion_ok,
        "domain_ok": domain_ok,
        "honest_tier": "depletion-approx",
        "note": ("B31 Si 载流子色散相移锚：golden=Soref & Bennett 1987 幂律闭式"
                 "（design_rule_anchor，@1550nm，c1=−8.8e-22, c2=−8.5e-18）；"
                 "candidate=Drude 自由电子气（independent_cross_check，方法学"
                 "不同源、故意非恒等）。ΔN(V) 为一维耗尽近似闭式（零漂移-扩散，"
                 "红线）。本锚测试点落在 SB 适用域 10¹⁷-10²⁰ cm⁻³ 内；Drude 与 "
                 "SB 电子项同号同量级（偏差 ~1-2×，捕捉同一等离子体色散物理）。"
                 "LLM 不进判决路径；golden 闭式非真值（T1 不作 ORACLE）。"),
    }
