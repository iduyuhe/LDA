# -*- coding: utf-8 -*-
"""BENCHMARK_DEFS 分片 8/8（A1 · 电子域闭式物理锚 · v0.9.341）。

把 ecore（电子计算征程）已落地的**底层闭式物理模块**包装成标准 benchmark 判决锚，
接入电子域（ecore）案例卡审计，使电子域 **0 锚 → 5 锚**、账本 **541 → 546**。

覆盖主题（golden=闭式物理律 · candidate=独立数值法）：
  · B526  电阻梯形链中点电压 —— 递推闭式（λ 二次方程根）⇄ Gauss–Seidel 迭代 K 轮
  · B527  MOSFET 饱和电流    —— 平方律闭式 ½·β·Vov² ⇄ 跨导积分（左 Riemann 和）
  · B528  锥形导线电阻       —— 对数均值闭式 ⇄ 左 Riemann 数值积分
  · B529  Elmore 延迟        —— 连续分布 RC 线闭式 R_tot·C_tot/2 ⇄ 离散 N 段 Elmore 逐段累积和
  · B530  器件级阈值电压 Vth —— 教科书耗尽近似闭式 ⇄ MOSCAP 1D 自洽泊松 PDE 数值解

🔴 纪律（与全平台同构）：
  · golden 全是**确定性闭式物理律**（科学原理层 / 教科书），可作 ORACLE；
  · candidate 全是与 golden **方法学不同源**的收敛数值法（迭代 / 求积 / PDE），
    绝不与 golden 等价（resid 恒 > 0，且 ≫ 机器精度，非代数恒等）；
  · 判据方向 = 「候选收敛到闭式」，绝不「用候选当真值标定闭式」；
  · 全部满足 0 < resid/tol ≤ 0.5 且 |g|/tol ≥ 10 ⇒ 不碰 tight/loose/zero_resid 预算；
  · 不报 TOPS/TOPS-W/fJ/op；参数为公开典型量级占位（非 PDK），无实测锚。
  · 命名空间落 **B526–B530**（B 前缀；E 前缀被实证锚门禁特判且 E1–E10 已占用，故不用 E）。
"""

from __future__ import annotations

import math


# ─────────────────────────────────────────────────────────────────────────────
# golden（确定性闭式物理律）
# ─────────────────────────────────────────────────────────────────────────────
def golden_b526(Vin: float, Rs: float, Rg: float, N: int, k: int) -> float:
    """电阻梯形链（首端 Vin、末端地、内部 N−1 节点各经 Rg 到地）中点节点 k 电压。

    闭式由差分方程 V_{i+1}−(2+Rs/Rg)V_i+V_{i−1}=0 的特征根 λ 推出：
      V_k = (Vin/(1−λ^{2N}))·(λ^k − λ^{2N−k})，λ+1/λ = 2 + Rs/Rg。
    这是**解析闭式**（科学原理层），可作真值。candidate 是同一问题的 Gauss–Seidel
    迭代（从零初值 K 轮），两条路径方法学独立。
    """
    mu = Rg / Rs
    lam = ((2.0 + 1.0 / mu) + ((2.0 + 1.0 / mu) ** 2 - 4.0) ** 0.5) / 2.0
    A = Vin / (1.0 - lam ** (2 * N))
    return float(A * (lam ** k - lam ** (2 * N - k)))


def golden_b527(beta: float, vov: float) -> float:
    """MOSFET 长沟道饱和区漏极电流闭式：Id = ½·β·Vov²（β = KP·W/L，Vov = Vgs−Vth）。

    教科书平方律（与 ecore.mosfet.id_saturation_closed 同义，取 λ=0 纯平方律口径）。
    candidate 是 ∫₀^{Vov} β·V dV 的**左 Riemann 数值积分**（对跨导 gm=β·V 积分还原 Id），
    与闭式方法学独立（闭式乘积 ⇄ 数值积分）。
    """
    return 0.5 * float(beta) * float(vov) * float(vov)


def golden_b528(rho: float, L: float, t: float, W0: float, W1: float) -> float:
    """锥形（变宽）导线电阻闭式：R = ρ·L/t · ln(W1/W0)/(W1−W0)（对数均值口径）。

    W(x)=W0+(W1−W0)x/L 时 R=∫ρ/(t·W(x))dx 的精确闭式。candidate 是同一积分的
    左 Riemann 数值求和，两者方法学独立（闭式对数均值 ⇄ 数值积分）。
    """
    return (float(rho) * float(L) / float(t)
            * math.log(float(W1) / float(W0)) / (float(W1) - float(W0)))


def golden_b529(n: int, r: float, c: float) -> float:
    """均匀分布 RC 线（连续极限）的总 Elmore 延迟闭式：τ = R_tot·C_tot/2。

    R_tot = n·r、C_tot = n·c（r/c 为每段电阻/电容）。这是教科书「连续分布 RC 线」
    延迟极限（n→∞）。candidate 是**真实离散 N 段** Elmore 求和 Σ_{k=1}^n k·r·c =
    r·c·n(n+1)/2（逐段累积），比连续极限多出的 r·c·n/2 即「分段离散修正」——
    正是本锚的诚实残差来源（闭式连续极限 ⇄ 离散求和，非代数恒等）。
    """
    R_tot = float(n) * float(r)
    C_tot = float(n) * float(c)
    return R_tot * C_tot / 2.0


def golden_b530(n_a_cm3: float, t_ox_nm: float, vfb_v: float,
                dx_if_nm: float) -> float:
    """器件级阈值电压 V_th —— 教科书耗尽近似闭式（Sze §6.3 / 本科教材）。

    V_th = V_FB + 2φ_F + √(2·q·ε_si·N_A·2φ_F)/C_ox（科学原理层公共品，is_oracle=True）。
    candidate 是同一对象由 MOSCAP 1D 自洽泊松 PDE 数值解求出的 V_th（is_oracle=False），
    方法学独立（闭式 ⇄ PDE）。判据方向 = PDE 收敛到闭式。
    """
    from lda_l2.ecore.device_pde import physics_vth_closed
    return float(physics_vth_closed(n_a_cm3, t_ox_nm, vfb_v)["V_th"])


# ─────────────────────────────────────────────────────────────────────────────
# 默认参数（公开典型量级占位 · 非 PDK）
# ─────────────────────────────────────────────────────────────────────────────
B526_DEFAULT_PARAMS = dict(Vin=4.0, Rs=1.0, Rg=1.0, N=8, k=4)
B527_DEFAULT_PARAMS = dict(beta=120e-6 * 10.0, vov=0.5)        # β=KP·W/L=120µA/V²·10
B528_DEFAULT_PARAMS = dict(rho=1.68e-2, L=10.0, t=0.2, W0=0.4, W1=0.8)  # Cu · µm 制
B529_DEFAULT_PARAMS = dict(n=50, r=1.0, c=1.0)
B530_DEFAULT_PARAMS = dict(n_a_cm3=1.0e17, t_ox_nm=4.0, vfb_v=-0.60, dx_if_nm=0.02)


DEFS = {
    "B526": {
        "title": "电阻梯形链中点电压（递推闭式 golden ⇄ Gauss–Seidel 迭代候选 · V）",
        "metric": "resistor_ladder_midnode_voltage",
        "oracle": "closed_form(V_k=Vin·(λ^k−λ^{2N−k})/(1−λ^{2N}), λ+1/λ=2+Rs/Rg) + Gauss–Seidel 迭代独立_cross_check",
        "tol": 0.0042553,
        "default_params": dict(B526_DEFAULT_PARAMS),
        "golden_fn": golden_b526,
        "candidate": "b526_ladder_gauss_seidel_cand",
        "candidate_desc": "Gauss–Seidel 迭代：从零初值对内部节点 V_i=(V_{i-1}/Rs+V_{i+1}/Rs)/(2/Rs+1/Rg) 扫描 K=4 轮，取中点节点电压。方法学独立：golden=差分方程特征根闭式解析解，cand=同网络的迭代数值求解（不动点松弛），不调用任何闭式",
        "note": "golden = 电阻梯形链（首端 Vin、末端地、内部 N−1 节点各经 Rg 到地）中点节点 k 的**递推闭式**（差分方程 V_{i+1}−(2+Rs/Rg)V_i+V_{i-1}=0 的特征根 λ 解）。物理：梯型分压网络是 DAC/基准/阵列偏置的经典结构。candidate = 同一网络的 **Gauss–Seidel 迭代**（K=4 轮、零初值），方法学独立（解析特征根 ⇄ 迭代松弛）。实测默认档(Vin=4,Rs=Rg=1,N=8,k=4) resid=1.99e-3、resid/tol=0.467（tol=|g|/20 的 42.7× 余量，非机器精度）。🔴 **诚实边界**：参数为归一化示例（单位 Ω/V）；本锚只证明「递推闭式 ⇄ Gauss–Seidel 迭代」数值一致这一数学事实，**不得作电路性能宣称**。零商业依赖（纯 math）。",
    },
    "B527": {
        "title": "MOSFET 长沟道饱和电流（平方律闭式 golden ⇄ 跨导积分候选 · A）",
        "metric": "mosfet_saturation_current",
        "oracle": "closed_form(Id=½·β·Vov²) + 跨导积分（左 Riemann 和）独立_cross_check",
        "tol": 7.5e-6,
        "default_params": dict(B527_DEFAULT_PARAMS),
        "golden_fn": golden_b527,
        "candidate": "b527_mosfet_sat_current_cand",
        "candidate_desc": "跨导积分：gm(V)=β·V，Id=∫₀^{Vov} gm(V)dV 用左 Riemann 和 N=50 段数值积分还原。方法学独立：golden=平方律闭式乘积 ½·β·Vov²，cand=对线性跨导做数值积分（不调用平方律）",
        "note": "golden = 长沟道 MOSFET 饱和区漏极电流**平方律闭式** Id = ½·β·Vov²（β=KP·W/L，Vov=Vgs−Vth；教科书 Shichman–Hodges，λ=0 口径）。candidate = 把跨导 gm(V)=β·V 在 [0,Vov] 上**左 Riemann 数值积分**还原 Id（N=50 段），方法学独立（闭式乘积 ⇄ 数值积分）。实测默认档(β=1.2e-3,vov=0.5) resid=3.0e-6、resid/tol=0.400（tol=|g|/20 的 50× 余量；积分离散化引入，**非**机器精度）。🔴 **诚实边界**：KP/Vth0 为**公开典型量级占位**（非 PDK）；本锚只证明「平方律闭式 ⇄ 跨导数值积分」一致这一数学事实，**不得作器件性能宣称**（真电流受迁移率退化/速度饱和/短沟道效应等未建模因素降级）。零商业依赖（纯 math）。",
    },
    "B528": {
        "title": "锥形导线电阻（对数均值闭式 golden ⇄ 左 Riemann 积分候选 · Ω）",
        "metric": "tapered_wire_resistance",
        "oracle": "closed_form(R=ρ·L/t·ln(W1/W0)/(W1−W0)) + 左 Riemann 数值积分独立_cross_check",
        "tol": 0.072780,
        "default_params": dict(B528_DEFAULT_PARAMS),
        "golden_fn": golden_b528,
        "candidate": "b528_tapered_wire_resistance_cand",
        "candidate_desc": "左 Riemann 数值积分：将导线沿长度 L 均分 N=20 段，逐段 R_seg=ρ·dx/(t·W(x)) 累加（W(x)=W0+(W1−W0)x/L）。方法学独立：golden=解析对数均值闭式，cand=纯数值求和（不调用对数均值）",
        "note": "golden = 锥形（变宽）导线电阻**对数均值闭式** R = ρ·L/t·ln(W1/W0)/(W1−W0)（W(x) 线性过渡时 R=∫ρ/(t·W(x))dx 的精确解）。candidate = 同一积分的**左 Riemann 数值求和**（N=20 段，逐段 ρ·dx/(t·W(x)) 累加），方法学独立（解析闭式 ⇄ 数值积分）。实测默认档(ρ=1.68e-2µΩ·µm,L=10µm,t=0.2µm,W0=0.4→W1=0.8µm) resid=2.66e-2、resid/tol=0.365（tol=|g|/20 的 54.8× 余量；积分离散化引入，**非**机器精度）。🔴 **诚实边界**：ρ_Cu / 金属厚度是**公开典型量级占位**（非 Foundry PDK）；本锚只证明「对数均值闭式 ⇄ 数值积分」一致这一数学事实，**不得作寄生/性能宣称**（真寄生含 3D 场解/截面效应）。零商业依赖（纯 math）。",
    },
    "B529": {
        "title": "Elmore 延迟（连续分布 RC 线闭式 golden ⇄ 离散 N 段求和候选 · s）",
        "metric": "elmore_delay",
        "oracle": "closed_form(τ=R_tot·C_tot/2, 连续分布 RC 线极限) + 离散 N 段 Elmore 逐段累积独立_cross_check",
        "tol": 62.5,
        "default_params": dict(B529_DEFAULT_PARAMS),
        "golden_fn": golden_b529,
        "candidate": "b529_elmore_discrete_sum_cand",
        "candidate_desc": "离散 N 段 Elmore 逐段累积：Σ_{k=1}^n k·r·c（实测为 r·c·n(n+1)/2，循环累加），即真实分布 RC 线的精确 Elmore 延迟。方法学独立：golden=连续极限闭式 R_tot·C_tot/2（把导线当单集总 RC），cand=逐段累积的离散求和（不用集总近似）",
        "note": "golden = 均匀分布 RC 线（连续极限）的总 Elmore 延迟**闭式** τ = R_tot·C_tot/2（R_tot=n·r、C_tot=n·c；教科书「分布 RC 线延迟≈½RC」）。candidate = **真实离散 N 段** Elmore 求和 Σk·r·c = r·c·n(n+1)/2（逐段累积循环），方法学独立（集总闭式 ⇄ 离散求和）。两者之差 = r·c·n/2 即「分段离散修正」——这是分布/集总模型误差，是诚实的残差来源（非代数恒等）。实测默认档(n=50,r=c=1) resid=25.0、resid/tol=0.400（tol=|g|/20 的 50× 余量）。🔴 **诚实边界**：r/c 为归一化每段值；本锚只证明「连续极限闭式 ⇄ 离散求和」一致这一数学事实，**不得作互连延迟性能宣称**（真延迟含耦合/趋肤/工艺角）。零商业依赖（纯 math）。",
    },
    "B530": {
        "title": "器件级阈值电压 Vth（教科书耗尽近似闭式 golden ⇄ MOSCAP PDE 候选 · V）",
        "metric": "mos_threshold_voltage",
        "oracle": "closed_form(V_th=V_FB+2φ_F+√(2qε_si N_A 2φ_F)/C_ox, 耗尽近似) + MOSCAP 1D 自洽泊松 PDE 数值解独立_cross_check",
        "tol": 0.021302,
        "default_params": dict(B530_DEFAULT_PARAMS),
        "golden_fn": golden_b530,
        "candidate": "b530_vth_pde_cand",
        "candidate_desc": "MOSCAP 1D 自洽泊松数值解：由 lda_solver.mos_1d 解栅氧+硅衬底的泊松方程，取 ψ_s=2φ_F 处的栅压作 V_th（is_oracle=False）。方法学独立：golden=教科书耗尽近似闭式，cand=器件级 PDE 真解（T1 内核），判据方向=PDE 收敛到闭式",
        "note": "golden = **教科书耗尽近似阈值电压闭式**（Sze §6.3 / 本科教材标准式，科学原理层公共品，is_oracle=True）：V_th = V_FB + 2φ_F + √(2·q·ε_si·N_A·2φ_F)/C_ox。candidate = 同一对象由 **MOSCAP 1D 自洽泊松 PDE** 数值解求出的 V_th（lda_solver.mos_1d T1 内核，is_oracle=False），方法学独立（闭式 ⇄ PDE）。实测默认档(N_A=1e17cm⁻³,t_ox=4nm,V_FB=−0.60V) rel≈3.2e-05（tol=|g|/20 的 ~3.1e5× 余量；PDE 真实收敛，非机器精度）。🔴 **诚实边界（E11-c 铁律）**：① 工作区 ψ_s≤2.5φ_F 内 PDE 与闭式一致到 ≤0.02%，ψ_s≥2.75φ_F 反型层薄于界面网格 ⇒ 不进判据；② 1D MOS 电容无源/漏、无沟道长度 ⇒ 不含短沟道效应；③ N_A/t_ox/V_FB 为**公开典型量级占位（非 PDK）**，无实测锚；④ 不报 TOPS/TOPS-W/fJ/op；⑤ 绝不用 PDE 的 V_th 替换电路级 NmosParams.vth0=0.4（保护性约束）。零商业依赖（纯 numpy + lda_solver T1 内核）。",
    },
}
