# -*- coding: utf-8 -*-
"""验证适配器 · 分片 2/6（F-08 拆分自 `verification_adapters.py` · v0.9.117）。

覆盖原文件 L1059..L2029（24 个顶层定义）。正文**逐字节**取自原文，不重排、不重格式化。
🔴 装配顺序由 `verification_adapters.py` 的 import 次序决定，勿单独调整。
"""

from __future__ import annotations

from ._adapter_core import (
    _HERE, _ensure_paths, _register_candidate,
)

import math

import numpy as np

import os

import sys

from typing import (
    Any, Callable, Dict, List, Optional, Tuple,
)

from .verification_spec import (
    VerificationSpec, cmp_abs, cmp_abs_balance, cmp_rel,
)

@_register_candidate(
    "tcoup_fock_exact",
    "三模 Fock 截断严格对角化激发带劈裂/2（ncut=3），符号由本征矢宇称独立判定"
    "—— 与 golden 的二阶微扰/SW 闭式方法学独立")
def _tcoup_fock_exact_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B24 独立候选：可调耦合器二阶有效耦合 g_eff（三模严格对角化 ↔ SW 闭式）。

    golden = g_eff = (g1·g2/2)·(1/Δ1 + 1/Δ2)（二阶微扰 / Schrieffer-Wolff）
    cand   = H = Σ ω_i a_i†a_i + g1(a_q1†a_c+h.c.) + g2(a_q2†a_c+h.c.)
             在 q1⊗q2⊗c 三模 Fock 截断下 eigh，取两个 qubit-like 态的
             劈裂 (E_hi−E_lo)/2，**符号由本征矢宇称独立判定**

    🔴 符号不能取绝对值：golden 在 Δ<0（qubit 低于耦合器）时为**负**
    （默认参数 Δ1=Δ2=−2.5 ⇒ golden=−0.004）。判定规则：两个 qubit-like 态
    ≈(|100⟩±|010⟩)/√2，若较低态的 |100⟩ 与 |010⟩ 振幅**同号**（对称态更低）
    则 g_eff<0。⚠️ 张量序是 q1⊗q2⊗c、q1 为最高位 ⇒ qubit2 激发的索引是
    `i010 = 1*ncut`（**不是** `1`，那是耦合器激发）。首版误用后端索引导致宇称
    判反、候选出正值、残差 7.99e-3（超 tol 7987×）—— 索引与构造序必须一致。

    ⚠️ tol 由 1e-6 **按实测重定为 3e-5**：1e-6 是「自证桩容差」（只容得下
    candidate≡golden），而闭式与严格解的**固有模型差**实测 1.272e-5
    （rel 0.32%，ncut=2/3/4/5 完全一致 ⇒ 已收敛，非截断噪声）。
    定 tol=3e-5 = 实测差 × 2.36 余量；判据窗口 (1.272e-5, 4.045e-4) = 31.8×，
    3e-5 落在窗内 ⇒ 正向 PASS 与「反向 10% 扰动必 FAIL」同时成立
    （实测 g1/g2 4.045e-4 · wc 9.289e-4 · wq 9.752e-4，四键全被抓）。
    """
    p = spec.params
    wq, wc = float(p["wq_ghz"]), float(p["wc_ghz"])
    g1, g2 = float(p["g1_ghz"]), float(p["g2_ghz"])
    ncut = 3
    n = np.arange(ncut, dtype=float)
    a = np.diag(np.sqrt(n[1:]), 1)
    eye = np.eye(ncut)
    h = (np.kron(np.kron(np.diag(wq * n), eye), eye)
         + np.kron(np.kron(eye, np.diag(wq * n)), eye)
         + np.kron(np.kron(eye, eye), np.diag(wc * n)))
    j1 = np.kron(np.kron(a.T, eye), a) + np.kron(np.kron(a, eye), a.T)
    j2 = np.kron(np.kron(eye, a.T), a) + np.kron(np.kron(eye, a), a.T)
    evals, evecs = np.linalg.eigh(h + g1 * j1 + g2 * j2)
    if evals[1] <= evals[2]:
        v_lo, e_lo, e_hi = evecs[:, 1], evals[1], evals[2]
    else:
        v_lo, e_lo, e_hi = evecs[:, 2], evals[2], evals[1]
    i100 = 1 * ncut * ncut          # |1,0,0>：qubit1 激发
    i010 = 1 * ncut                 # |0,1,0>：qubit2 激发（最高位是 q1！）
    mag = 0.5 * (e_hi - e_lo)
    return float(-mag if (v_lo[i100] * v_lo[i010]) > 0 else mag)

@_register_candidate(
    "yield_analytic",
    "S13 设计良率解析闭式（高斯积分 Φ 精确解，保留 1/L 非线性）↔ 蒙特卡洛双算法互证，"
    "与 golden 的 MC 仿真方法学独立（同一物理定律两种算法 = 非 AI ground）")
def _s13_yield_analytic_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """S13 独立候选：环形 FSR 命中规格窗口的设计良率（解析高斯积分）。

    golden = 蒙特卡洛仿真良率（固定种子 1313，采样 20000 点）
    cand   = 解析闭式 Y = Φ((L_hi−L0)/σ_L) − Φ((L_lo−L0)/σ_L)
             （FSR=c/L 单调 ⇒ 规格窗口逆变换为 L 区间 ⇒ 误差函数精确积分，
              非 δ/σ 一阶线性化，1/L 非线性完整保留）

    ⚠️ 实测（v0.9.18）：golden=0.954750、candidate=0.954413、baseline|diff|=3.37e-4
    （rel 0.035%，tol=0.01 余量 29.7×）。反向扰动信号谱：
    delta×1.1 → |cand−golden0|=1.73e-2（51×）✅ · sigma_rel×1.1 → 2.39e-2（71×）✅
    · fsr_nom×1.1 → 3.37e-4（=baseline，漏抓：yield 对 fsr_nom 免疫，因 σ 按比例缩放）
    ⇒ 盲区 fsr_nom_nm 已诚实披露，PERTURB 固定扰 delta（最强键）。
    """
    try:
        from lda_harness.yield_anchor import yield_analytic
    except ImportError:
        from lda.lda_harness.yield_anchor import yield_analytic
    p = spec.params
    return float(yield_analytic(
        fsr_nom_nm=float(p["fsr_nom_nm"]),
        delta=float(p["delta"]),
        sigma_rel=float(p["sigma_rel"]),
    ))

@_register_candidate(
    "bragg_bloch_exact",
    "反周期 Bloch 广义本征值问题 A ψ=β²B ψ（N=240，scipy eigvalsh）—— "
    "与 golden 的一阶相位匹配闭式方法学独立")
def _b15_bragg_bloch_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B15 独立候选：Bragg 光栅中心波长（Bloch 本征 ↔ 相位匹配闭式）。

    golden = 一阶 Bragg 条件 λ_B = 2·n_eff·Λ（运动学：k 演化只计基波）
    cand   = E(z)=n_eff²(1+m·cos(2πz/Λ)) 的广义本征值问题
             A ψ = β² B ψ（反周期边界 ψ(z+Λ)=−ψ(z) 锁定 k=±π/Λ，
             谱最低简并对即第一带隙边沿，中心 → λ_B=2π/β_c）
             —— 动力学全波本征谱，调制深度 m 进入算子。

    ⚠️ v0.9.18 曾判 B15「不可接」：当时唯一在库求解器 tmm.py 是垂直入射
    多层膜堆（折射率沿 z 分层、平面波正入射透射谱），与波导光栅（折射率
    沿传播方向周期调制、Bragg 反射带隙）物理对象不同 ⇒ 接它必成伪独立。
    v0.9.19 新写 bragg_solver.py（正确的物理对象 + 正确的本征值方法）。

    实测标定（n_eff=2.4 / Λ=0.323 / m=0.004 / N=240）：
    baseline |diff| = 8.356e-6（rel 5.4e-6，tol=0.01 未动，余量 1196×）。
    反向扰动信号谱：n_eff×1.1 → 1.55e-1（15.5×）✅ · period×1.1 → 1.55e-1
    （与 n_eff 一阶等价，λ_B∝n_eff·Λ）⇒ PERTURB 固定扰 n_eff（最强键）。
    网格双向标定：N=480 diff=5.4e-8 为偶然抵消点、N=960 起越过 LAPACK
    地板反升（2.0e-6）⇒ 取 N=240 收敛段稳定点（详 bragg_solver.py docstring）。
    """
    _ensure_paths()
    from bragg_solver import lambda_B_bloch

    p = spec.params
    return float(lambda_B_bloch(
        n_eff=float(p["n_eff"]),
        period=float(p["period"]),
        mod_depth=float(p.get("mod_depth", 0.004)),
        N=int(p.get("bloch_N", 240)),
    ))

@_register_candidate(
    "b35_reuse_b15",
    "B35 复用 B15：DBR/DFB 激光光栅布拉格波长，委托 B15 的反周期 Bloch 本征值"
    "候选（零新锚、不重复投入、不计入独立锚计数）")
def _b35_bragg_reuse_b15_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B35（DBR/DFB 激光光栅布拉格波长）复用 B15 的独立候选。

    物理对象与 B15 完全同一（λ_B=2·n_eff·Λ），仅应用场景从被动反射镜变
    主动腔镜，故直接委托 B15 的 Bloch 反周期本征值候选，不另写求解代码
    （评审裁决：零新锚）。标签≠行为纪律：本候选可解析、真实委托到 B15 实现。
    """
    return _b15_bragg_bloch_candidate(spec, oracle_value)

@_register_candidate(
    "dc_cmt_fft",
    "数值传播 + FFT 拍频谱峰提取 L_3dB（增量 2×2 复传播矩阵 + Hann 窗 rFFT"
    " + 三点抛物线细化）—— 与 golden 的耦合模解析闭式反解方法学独立")
def _b14_dc_cmt_fft_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B14 独立候选：定向耦合器 3dB 耦合长度（FFT 拍频 ↔ 解析闭式）。

    golden = 耦合模解析闭式 L_3dB = λ/(4|Δn|)（由 P2=sin²(κz) 反解 P2=0.5）
    cand   = 数值传播 [A1,A2] 序列 → P2(z) 的 FFT 拍频谱峰 → L_P=1/f_peak
             → L_3dB = L_P/4（B3/B4/B20 同款「数值序列提取频域周期」方法学）

    ⚠️ v0.9.20 语义修正（D-66「怀疑 golden 本身」第 4 例）：golden 原式
    λ/(2|Δn|) 是**完全转移长度**（P2=sin²(π/2)=1.0，RK4 实证），被错标
    为 3dB 点；真 3dB 点 = λ/(4|Δn|)（P2=sin²(π/4)=0.5）。修正后
    tol 从 0.5（旧值 3.2%）按同比重定 0.25（3.2%，余量不变）。

    实测标定（n_e=2.45/n_o=2.40/λ=1.55，golden=7.75）：
    baseline |diff| = 1.56e-4（rel 2.0e-5，tol=0.25 余量 1560×；
    残差由谱分辨率+抛物线近似控制，远离 1e-12 自证桩判据）。
    反向扰动信号谱：n_e×1.1 → 6.44（25.8×）✅ · n_o×1.1 → 5.71（22.9×）✅
    · wl×1.1 → 0.775（3.1×）✅ ⇒ PERTURB 固定扰 n_e（最强键）。
    """
    _ensure_paths()
    from dc_cmt_solver import dc_3dB_fft

    p = spec.params
    return float(dc_3dB_fft(
        n_e=float(p["n_e"]),
        n_o=float(p["n_o"]),
        wl=float(p["wl"]),
        dz=float(p.get("fft_dz", 0.01)),
        n_periods=int(p.get("fft_n_periods", 8)),
    ))

@_register_candidate(
    "mie_exact",
    "完整 Mie 级数 Q_scat（B&H 4.53 维度形式，Wiscombe 截断 nmax=x+4x^⅓+2，"
    "纯 numpy 递推）—— 与 golden 的 Rayleigh 一阶极限方法学独立")
def _b1_mie_exact_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B1 独立候选：米氏散射效率（完整级数 ↔ Rayleigh 一阶极限）。

    golden = Rayleigh（偶极子）极限 Q=(8/3)·x⁴·r²（x≪1 只保留 a₁ 首项）
    cand   = 完整 Mie 级数（所有多极子 a_n/b_n 求和到 nmax）

    二者物理同源（麦克斯韦方程）、方法独立（一阶展开 vs 全阶求和）⇒
    |cand−golden| = Rayleigh 固有截断误差（x⁶ 首项），随 x 单调增长
    （-0.001%@x=0.01 → 1.388%@x=0.4）——「x≪1 精确一致」的定量边界。

    ⚠️ 环境确定性：golden 的 b1_mie_qscat(use_miepython=True) 在装有
    miepython 的环境会切换到完整 Mie（ORACLE）⇒ golden 环境相关。
    接线后 default_params 钉死 use_miepython=False（golden 固定走
    Rayleigh，任何环境一致），Mie ORACLE 路径保留给显式外部验货。

    实测标定（m=1.33/x=0.4，golden=2.8413e-3）：
    baseline |diff| = 3.945e-5（rel 1.388%，tol=2e-4 未动，余量 5.1×）。
    反向扰动信号谱：m×1.1 → 2.357e-3（11.9×）✅ · x×1.1 → 1.246e-3
    （6.2×）✅ ⇒ PERTURB 固定扰 m（最强键）。
    递推已用 scipy.special.spherical_jn/yn 交叉验证（max|Δ|≤3e-8）。
    """
    _ensure_paths()
    from mie_solver import mie_q_scat

    p = spec.params
    return float(mie_q_scat(m=float(p["m"]), x=float(p["x"])))

@_register_candidate(
    "coupler_charge_exact",
    "双 transmon 441 维电荷基严格对角化 J（Nq=10，一般失谐提取 √((Δ/2)²−(δ/2)²)）"
    "—— 与 golden 的电荷矩阵元渐近闭式方法学独立")
def _coupler_charge_exact_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B13 独立候选：双 transmon 电容耦合 J（电荷基严格对角化 ↔ 渐近闭式）。

    golden = J = Jc·⟨0|n̂|1⟩₁·⟨0|n̂|1⟩₂，其中 n01≈(E_J/2E_C)^{1/4}/2（渐近式）
    cand   = 双比特电荷基（每比特 2Nq+1=21 维，联合 441 维）严格对角化，
             由单激发双重态劈裂按一般失谐提取 J=√((Δ/2)²−(δ/2)²)

    ⚠️ tol 由 0.10 **收紧 50× 到 2.0e-3**（是加严不是放宽）：0.10 相当于
    golden 的 316%，等于什么都抓不住。实测基线残差 1.3131e-3（rel 4.15%，
    与本锚 note 原就写着的「rel~4%」一致，Nq=8 起已收敛、Nq 增大不变）
    ⇒ 该 4.15% 是**渐近闭式的固有截断误差**，非数值噪声。

    🔴 **诚实披露：本锚的判据窗口很窄，有已知反向盲区。**
    10% 扰动逐键实测残差（golden 固定）：
        C1/C2   4.0686e-3（3.10× 基线）✅ 被抓
        E_C1/E_C2 2.0599e-3（1.57×）   ✅ 被抓
        Cc      1.7179e-3（1.31×）     ❌ 漏抓（< tol）
        E_J1/E_J2 5.5027e-4（0.42×）   ❌ 漏抓（**比基线还小**）
    E_J 扰动使严格解**朝渐近值靠近**（扰动与近似误差偶然抵消，同 B26 现象）
    ⇒ 任何 tol > 基线的取值都不可能抓住 E_J 键。取 tol=2.0e-3（基线 ×1.52）
    是「正向 PASS」与「尽量多抓反向键」的最优折中：4/7 键可抓。
    反向测试固定扰 C1（信号最强）。**盲区不掩盖，写进 note 与本 docstring。**
    """
    _ensure_paths()
    from coupler_solver import solve_coupler

    p = spec.params
    return float(solve_coupler(
        E_J1=float(p["E_J1"]), E_C1=float(p["E_C1"]),
        E_J2=float(p["E_J2"]), E_C2=float(p["E_C2"]),
        Cc=float(p["Cc"]), C1=float(p["C1"]), C2=float(p["C2"]),
        Nq=10)["J_num"])

_LINK_PASSIVITY_WL_MARGIN_NM = 100.0

_LINK_PASSIVITY_WL_STEP_NM = 0.01

@_register_candidate(
    "link_passivity",
    "lda_chain 链路引擎端到端级联（构建→布局→自动布线→带布线损耗→传递谱）"
    "在**全部传递路径 × 全部采样波长**上的 max|T| —— 与 golden 无源上界 1.0 "
    "死标量比对（cmp='le'）")
def _link_passivity_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B19 独立候选：无源链路无增益上界（max|T| ≤ 1）。

    golden = 常量 **1.0**（无源线性网络无外部泵浦 ⇒ 所有传递增益 |T(λ)| ≤ 1；
             能量守恒是其无损特例）。cmp='le'。
    cand   = `lda_chain` 引擎真跑一遍完整链路：
             `build_wdm_link` 建 N 环 WDM 级联 → `route_and_simulate` 布局 +
             自动布线（产出逐 net 的 `net_loss_db`）→ `engine.simulate` 级联
             → 取所有路径 × 所有波长上的 max|T|。

    **方法学独立性（最强一档）**：golden 是一个**不依赖任何模型的物理硬约束**
    （无源性/能量守恒），候选是一整套工程师序（耦合模谱 × 布线损耗 × 级联）。
    候选不可能"复述" golden —— 它甚至不知道 golden 是多少。

    🔴 **v0.9.25 诚实边界（三条，均已实测）：**
    1. **判据余量仅 ~1.04e-4**。max|T| 的真值 ≈ 0.9998962，缺口几乎全部来自
       环的弯曲损耗。若某天把损耗模型关掉，max|T| → 1.0，本锚会**顶到边界**
       （cmp='le' 下 1.0 恰好 PASS，但任何数值噪声都可能顶穿）。
    2. **网格非单调 + 覆盖盲区**。max|T| 随网格密度**非单调**（采样是否命中窄
       共振峰尖），粗网格会**低估** max ⇒ 步长固定 0.01 nm（已标定稳定）。
       即便如此，若存在 >1 的尖峰恰好落在采样点之间，仍会漏检 —— **加细网格
       只能缓解，不能根除**。这是本锚的结构性盲区，不掩盖。
    3. **`alpha_cm` 对本锚的指标无影响**。它确实被消费（bus0/1/2 的
       `net_loss_db` 随 alpha 增长，实测 alpha=2.5/25/250 时 ring3.out 的
       max|T| 0.9801→0.9594→0.7752），但**全局 max 落在 `ring0.in->ring0.drop`
       这条不经过任何 bus 的路径上**（三档 alpha 下恒为 0.9995947013）。
       ⇒ 候选对 alpha_cm 零响应；判据靠 gap_um / n_g 两键成立（Δ ~1e-4）。
    4. **只判合法性，不判精度**。本锚只回答"链路有没有产生增益"，不回答
       "级联算得准不准"。后者由 `link_harness.link_cascade_check` 负责，但
       它用**引擎同源**模型重建期望 ⇒ **不是独立验证，不得当独立凭据**。

    ⚠️ 布线被阻塞（`blocked_nets` 非空）时**抛异常上浮**，绝不静默回退 ——
    否则又变成自证桩（IndependentCandidateRouter 的既定设计原则）。
    """
    try:
        from lda_chain import build_wdm_link
        from lda_chain import route_sim
        from lda_chain.link_harness import max_transfer_of
    except ImportError:
        # 🔴 `lda_chain` 内部用**绝对**导入（`from lda_ir import ObjectiveSpec`），
        #    所以 `from lda.lda_chain import ...` 必然 ModuleNotFoundError；
        #    必须把 lda/ 根目录放进 sys.path，再按顶层包名导入。
        _root = os.path.dirname(_HERE)
        if _root not in sys.path:
            sys.path.insert(0, _root)
        from lda_chain import build_wdm_link
        from lda_chain import route_sim
        from lda_chain.link_harness import max_transfer_of

    p = spec.params
    if str(p.get("type", "wdm")) != "wdm":
        raise ValueError(f"B19 候选仅支持 type='wdm'，收到 {p.get('type')!r}")
    channels_nm = [float(c) for c in p["channels_nm"]]
    Rs_um = [float(r) for r in p["Rs_um"]]
    if not channels_nm or len(channels_nm) != len(Rs_um):
        raise ValueError(
            f"B19 候选 channels_nm({len(channels_nm)}) 与 "
            f"Rs_um({len(Rs_um)}) 必须非空且等长")

    lo = min(channels_nm) - _LINK_PASSIVITY_WL_MARGIN_NM
    hi = max(channels_nm) + _LINK_PASSIVITY_WL_MARGIN_NM
    n = int(round((hi - lo) / _LINK_PASSIVITY_WL_STEP_NM)) + 1
    wls = [(lo + (hi - lo) * i / (n - 1)) / 1000.0 for i in range(n)]

    link = build_wdm_link(channels_nm, Rs_um,
                          gap=float(p["gap_um"]), n_g=float(p["n_g"]))
    res = route_sim.route_and_simulate(
        link, wls, straight_loss_db_cm=float(p["alpha_cm"]))
    blocked = res.get("blocked_nets") or []
    if blocked:
        raise RuntimeError(f"B19 链路布线不完整 blocked_nets={blocked}"
                           f" —— 级联结果不可信，拒绝出数")
    # 🔴 float() 包裹：判决链上不许出现 numpy 标量（v0.9.24 B10 同类坑）
    return float(max_transfer_of(res["sim"]))

@_register_candidate(
    "taper_eme",
    "本征模展开（EME）逐切片解完整 Helmholtz + 模式重叠矩阵级联 —— 每片解的是"
    "**无旁轴假设的精确横向本征问题**，与 golden 的「绝热极限 T→1」死标量比对")
def _taper_eme_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B8 独立候选：绝热锥度传输效率 T（EME 本征模展开）。

    golden = 常量 **1.0**（绝热极限：锥度足够缓变时局部基模绝热跟随 ⇒ T→1，
             这是**能量守恒给出的物理上界**，不是任何引擎的输出）。
    cand   = `lda_solver.eme_taper` 真解一遍：把锥度切成 N 片，每片解
             一维横向 Helmholtz 本征问题（scipy `eigh_tridiagonal`），片内
             精确模态传播 exp(−iβ·dz)，片间用模式重叠矩阵投影级联，
             T = |c_out,0|²（末片基模功率占比）。

    **方法学独立性**：候选全程不知道 golden 是多少，也不调用任何闭式传输公式；
    它只解亥姆霍兹方程。golden 的「1.0」是上界，候选的 0.999953 是从
    Maxwell 方程算出来的**实测缺口**。

    🔴 **v0.9.26 四条诚实边界（均已实测）：**
    1. **判据余量只有 4.65e-5（占 tol 1e-2 的 0.47%）**。深度绝热区 T 离 1
       极近，本锚实际只回答「是否进入绝热极限」，**不回答精度**。
       ⚠️ 这与 B19（余量 1.04e-4）同型：两个"上界型"锚的余量都极小。
    2. **0.2→0.5 µm 这个几何的损耗上限仅 ~1.5%**（突变结模式重叠 0.9853）。
       ⇒ **单独扰动 L 无法击穿 tol**：L 缩到 0.2 µm 也只到 0.993。反向测试
       必须改成 w2=3.0/L=1.0 µm（T≈0.435）。这是几何本身的性质，非缺陷。
    3. **短锥度区（L≲2 µm）未收敛**：箱模谱在 Δβ·L≪1 时欠采样，窗口 8/16/32
       的 T 相差达 4e-3，且 EME 给出的 T（0.993）**高于**突变结重叠下界
       （0.9853）。已收敛区（L≥5 µm）窗口 16→32 只差 1.4e-5。
       单调性自校锚因此**只取 L≥5**。
    4. **EIM 降维 + 单向近似**：垂向压成常数 n_eff ⇒ 不含垂向辐射与极化耦合；
       只算前向模式不算背向反射。反射只会**降低** T ⇒ 对上界 golden 不会虚高。

    ⚠️ 失败即抛异常上浮，绝不静默回退（IndependentCandidateRouter 既定原则）。
    """
    try:
        from lda.lda_solver import eme_taper
    except ImportError:
        _ensure_paths()
        import eme_taper

    p = spec.params
    # 🔴 float() 包裹：判决链上不许出现 numpy 标量（v0.9.24 B10 同类坑）
    return float(eme_taper.taper_transmission(
        w1=float(p["w1"]), w2=float(p["w2"]), L=float(p["L"]),
        wl=float(p["wl"]), n_eff=float(p["n_eff"]),
        n_clad=float(p["n_clad"]),
        # 🔴 数值档位取**求解器生产档位常量**，不随 spec 参数变化：
        #    参数扰动只改几何/波长，不改网格（同 semivec 的网格纪律）。
        dz=eme_taper.DEFAULT_DZ, m_modes=eme_taper.DEFAULT_MMODES,
        dx=eme_taper.DEFAULT_DX, window=eme_taper.DEFAULT_WINDOW_UM))

def harness_perturbed_candidate(rel_err: float):
    """扰动候选：golden·(1+rel_err)——用于演示 fail 检测（同 PerturbedCandidate）。"""
    def _cand(spec: VerificationSpec, oracle_value: Any) -> float:
        return oracle_value * (1.0 + rel_err)
    return _cand

def build_waveguide_specs(cases: Optional[List] = None,
                          backend: str = "numpy"
                          ) -> Tuple[List[VerificationSpec], Dict[str, Callable]]:
    """WG neff 契约构造。

    backend（v0.9.38 T-8）：
      "numpy" —— 原生产 numpy 实现（默认，**行为与新增前完全一致**）；
      "numba" —— 强制 numba-CPU 后端（缺 numba 直接抛错，不静默降级）；
      "auto"  —— numba 可用则用 numba，否则回退 numpy（DeviceLibrary live 用）。
    三种后端**同一物理、同一默认测量窗**（M=80 周期 / transient≥3000），
    差异只在计算内核，见 fdtd3d_waveguide_numba.py 的交叉验证判据。
    """
    _ensure_paths()
    from waveguide_loop import WaveguideTarget, _default_cases
    from fdtd3d_waveguide import build_waveguide_field_3d, solve_waveguide_neff_3d
    from oracle_mode import fdfd_mode_field

    if backend not in ("numpy", "numba", "auto"):
        raise ValueError(f"backend 必须是 numpy/numba/auto，收到 {backend!r}")

    _backend_used = {"name": "numpy"}
    if backend in ("numba", "auto"):
        try:
            from fdtd3d_waveguide_numba import (solve_waveguide_neff_3d_numba,
                                                backend_info)
            if backend_info()["have_numba"]:
                _backend_used["name"] = "numba"
            elif backend == "numba":
                raise RuntimeError("backend='numba' 但 numba 不可用："
                                   + backend_info()["import_error"])
        except ImportError:
            if backend == "numba":
                raise

    cases = cases if cases is not None else _default_cases()
    specs: List[VerificationSpec] = []
    cand_map: Dict[str, Callable] = {}
    for i, t in enumerate(cases):
        sid = f"WG-{t.label[:14]}"
        params = {
            "w_um": t.w_um, "h_um": t.h_um, "n_core": t.n_core,
            "n_clad": t.n_clad, "wl_um": t.wl_um,
            "dl": t.wl_um / t.dl_factor, "clad_um": t.clad_um,
            "Lz_um": t.Lz_um, "label": t.label, "tol": t.tolerance_abs,
        }

        def _oracle(p):
            eps3, meta = build_waveguide_field_3d(
                p["w_um"], p["h_um"], p["n_core"], p["n_clad"], p["wl_um"],
                dl=p["dl"], clad_um=p["clad_um"], Lz_um=p["Lz_um"])
            ne, _mode = fdfd_mode_field(eps3, meta["dl"], p["wl_um"])
            return ne

        def _cand(spec, oracle_value):
            p = spec.params
            eps3, meta = build_waveguide_field_3d(
                p["w_um"], p["h_um"], p["n_core"], p["n_clad"], p["wl_um"],
                dl=p["dl"], clad_um=p["clad_um"], Lz_um=p["Lz_um"])
            ne_oracle, mode2d = fdfd_mode_field(eps3, meta["dl"], p["wl_um"])
            solver = (solve_waveguide_neff_3d_numba
                      if _backend_used["name"] == "numba"
                      else solve_waveguide_neff_3d)
            return solver(
                eps3, meta["dl"], p["wl_um"], n_clad=p["n_clad"],
                n_core=p["n_core"], mode_source=mode2d)

        # 诚实披露：候选实际走哪个后端（供 DeviceLibrary / CI 报告）
        _cand.backend_used = lambda: _backend_used["name"]  # type: ignore[attr-defined]
        specs.append(VerificationSpec(
            spec_id=sid, metric="neff", oracle_kind="fdfd_eigen",
            oracle_fn=_oracle, compare_fn=cmp_abs,
            tol=params["tol"], tol_mode="abs",
            target_desc=t.label, params=params,
            source="fdfd 标量亥姆霍兹本征值（独立频域）",
            candidate_desc="标量 3D FDTD（独立时域）"))
        cand_map[sid] = _cand
    return specs, cand_map

def build_coupler_specs(cases: Optional[List] = None
                        ) -> Tuple[List[VerificationSpec], Dict[str, Callable]]:
    _ensure_paths()
    from coupler_loop import CouplerTarget, _default_cases
    from fdtd3d_coupler import (
        build_coupler_field_3d, build_ybranch_field_3d,
        solve_supermode_projection_3d_torch, solve_port_powers_3d_torch,
    )
    from oracle_coupler import fdfd_coupler_supermodes, ybranch_oracle
    from oracle_mode import fdfd_mode_field

    cases = cases if cases is not None else _default_cases()
    specs: List[VerificationSpec] = []
    cand_map: Dict[str, Callable] = {}

    for i, t in enumerate(cases):
        dl = t.wl_um / t.dl_factor
        if t.kind == "dc":
            sid = f"DC-gap{t.gap_um}"
            params = {
                "kind": "dc", "w_um": t.w_um, "h_um": t.h_um,
                "gap_um": t.gap_um, "n_core": t.n_core, "n_clad": t.n_clad,
                "wl_um": t.wl_um, "dl": dl, "clad_um": t.clad_um,
                "Lz_um": t.dc_Lz_um, "label": t.label,
            }

            def _oracle(p):
                eps3, meta = build_coupler_field_3d(
                    p["w_um"], p["h_um"], p["gap_um"], p["n_core"], p["n_clad"],
                    p["wl_um"], dl=p["dl"], clad_um=p["clad_um"], Lz_um=p["Lz_um"])
                o = fdfd_coupler_supermodes(eps3[:, :, 0], meta["dl"], p["wl_um"],
                                            mask_a=meta["mask_a"], mask_b=meta["mask_b"])
                return o["kappa"]

            def _cand(spec, oracle_value):
                p = spec.params
                from coupler_loop import _beta_from_recurrence
                eps3, meta = build_coupler_field_3d(
                    p["w_um"], p["h_um"], p["gap_um"], p["n_core"], p["n_clad"],
                    p["wl_um"], dl=p["dl"], clad_um=p["clad_um"], Lz_um=p["Lz_um"])
                o = fdfd_coupler_supermodes(eps3[:, :, 0], meta["dl"], p["wl_um"],
                                            mask_a=meta["mask_a"], mask_b=meta["mask_b"])
                # 波导 A 单波导基模作源
                Nx, Ny = meta["Nx"], meta["Ny"]
                xs = (np.arange(Nx) - Nx / 2.0) * meta["dl"]
                ys = (np.arange(Ny) - Ny / 2.0) * meta["dl"]
                X, Y = np.meshgrid(xs, ys, indexing="ij")
                core_a = (np.abs(X - meta["xa_um"]) <= p["w_um"] / 2.0) & \
                         (np.abs(Y) <= p["h_um"] / 2.0)
                eps2_a = np.full((Nx, Ny), p["n_clad"] ** 2)
                eps2_a[core_a] = p["n_core"] ** 2
                _, src = fdfd_mode_field(eps2_a, meta["dl"], p["wl_um"])
                # 瞬态测量窗（与 coupler_loop 相同参数）
                sponge_z = max(8, min(60, meta["Nz"] // 4))
                src_um = meta["dl"] * (sponge_z + max(8, int(0.12 * (meta["Nz"] - 2 * sponge_z))))
                z_samp = src_um + 2.0 + 0.25 * np.arange(12)
                k0 = 2.0 * math.pi / p["wl_um"]
                dt_f = meta["dl"] * 0.95 / math.sqrt(3.0)
                period = int(round(2.0 * math.pi / (o["neff_s"] * k0 * dt_f)))
                prop = int(round((z_samp[0] - src_um) * o["neff_s"] / dt_f))
                transient = 400 + prop + 5 * period
                Os, Oa, zu = solve_supermode_projection_3d_torch(
                    eps3, meta["dl"], p["wl_um"], p["n_clad"], p["n_core"], src,
                    o["mode_s"], o["mode_a"], src_um=src_um, z_sample_um=z_samp,
                    M_cycles=20, transient=transient)
                bs = _beta_from_recurrence(Os, zu)
                ba = _beta_from_recurrence(Oa, zu)
                if bs is None or ba is None:
                    return float("nan")
                return (bs - ba) / 2.0

            specs.append(VerificationSpec(
                spec_id=sid, metric="kappa", oracle_kind="fdfd_supermode",
                oracle_fn=_oracle, compare_fn=cmp_rel,
                tol=t.tol_kappa, tol_mode="rel",
                target_desc=t.label, params=params,
                source="FDFD 超模法（对称/反对称超模 → κ）",
                candidate_desc="标量 3D FDTD 超模投影递推（独立时域）"))
            cand_map[sid] = _cand
        else:  # ybranch
            sid = "YB-1x2"
            params = {
                "kind": "ybranch", "w_um": t.w_um, "h_um": t.h_um,
                "n_core": t.n_core, "n_clad": t.n_clad, "wl_um": t.wl_um,
                "dl": dl, "clad_um": t.clad_um, "sep_um": t.sep_um,
                "l_in_um": t.l_in_um, "l_trans_um": t.l_trans_um,
                "l_out_um": t.l_out_um, "label": t.label,
                "tol_balance": t.tol_balance,
            }

            def _oracle(p):
                return ybranch_oracle()["target_frac"]

            def _cand(spec, oracle_value):
                p = spec.params
                eps3, meta = build_ybranch_field_3d(
                    p["w_um"], p["h_um"], p["n_core"], p["n_clad"], p["wl_um"],
                    sep_um=p["sep_um"], l_in_um=p["l_in_um"],
                    l_trans_um=p["l_trans_um"], l_out_um=p["l_out_um"],
                    dl=p["dl"], clad_um=p["clad_um"])
                Nx, Ny = meta["Nx"], meta["Ny"]
                xs = (np.arange(Nx) - Nx / 2.0) * p["dl"]
                ys = (np.arange(Ny) - Ny / 2.0) * p["dl"]
                X, Y = np.meshgrid(xs, ys, indexing="ij")
                inp_core = (np.abs(X) <= p["w_um"] / 2.0) & (np.abs(Y) <= p["h_um"] / 2.0)
                eps2_in = np.full((Nx, Ny), p["n_clad"] ** 2)
                eps2_in[inp_core] = p["n_core"] ** 2
                _, mode_in = fdfd_mode_field(eps2_in, p["dl"], p["wl_um"])
                src_um = p["l_in_um"] * 0.7
                z_out = meta["l_out_start_um"] + np.linspace(0.6, 4.2, 7)
                neff_avg = 0.5 * (p["n_core"] + p["n_clad"])
                dt_f = p["dl"] * 0.95 / math.sqrt(3.0)
                period = int(round(2.0 * math.pi / (neff_avg * 2.0 * math.pi / p["wl_um"] * dt_f)))
                prop = int(round((z_out[0] - src_um) * neff_avg / dt_f))
                transient = 400 + prop + 5 * period
                fa, fb, _zu, _pa, _pb, _srcz = solve_port_powers_3d_torch(
                    eps3, meta["dl"], p["wl_um"], p["n_clad"], p["n_core"], mode_in,
                    meta["mask_a"], meta["mask_b"], src_um=src_um,
                    z_sample_um=z_out, M_cycles=20, transient=transient, debug=True)
                n_avg = max(2, len(fa) // 2)
                return float(np.mean(fa[-n_avg:]))

            specs.append(VerificationSpec(
                spec_id=sid, metric="power_frac", oracle_kind="symmetry_theorem",
                oracle_fn=_oracle, compare_fn=cmp_abs_balance,
                tol=params["tol_balance"], tol_mode="abs_balance",
                target_desc=t.label, params=params,
                source="对称性定理（几何完全对称 ⇒ P1=P2=0.5·P_in）",
                candidate_desc="标量 3D FDTD 能流功率测量（独立时域）"))
            cand_map[sid] = _cand
    return specs, cand_map

def cmp_max_abs_err(candidate, oracle) -> float:
    """逐用例最大绝对误差（oracle/candidate 为 list[list[float]]，每用例多波长）。"""
    if not isinstance(candidate, list) or len(candidate) != len(oracle):
        return float("inf")
    errs = []
    for c, o in zip(candidate, oracle):
        if isinstance(o, (list, tuple)):
            if not isinstance(c, (list, tuple)) or len(c) != len(o):
                return float("inf")
            errs.append(max(abs(float(g) - float(oo)) for g, oo in zip(c, o)))
        else:
            errs.append(abs(float(c) - float(o)))
    return max(errs)

def build_solver_writer_specs(spec, candidate_code: str
                              ) -> Tuple[List[VerificationSpec], Dict[str, Callable]]:
    """把 solver_writer 的一个 SolverSpec + 候选代码适配成统一契约（单 spec）。

    oracle = 各测试用例 ORACLE 真值列表；candidate = 沙箱执行候选代码后的逐用例输出；
    compare = cmp_max_abs_err（同 solver_writer.Verifier 语义，max_abs_err ≤ tol）。
    """
    from .verification_spec import VerificationSpec

    # 序列化 test_cases（oracle 真值 + 输入）到 params
    cases_data = [{
        "name": c.name, "inputs": c.inputs,
        "oracle": list(c.oracle_value) if isinstance(c.oracle_value, (list, tuple))
                  else c.oracle_value,
        "tol": c.tol,
    } for c in spec.test_cases]

    def _oracle(p):
        return [c["oracle"] for c in p["cases"]]

    def _cand(spec_obj, oracle_value):
        p = spec_obj.params
        from solver_writer import SandboxExecutor
        # 构造临时 SolverSpec 以复用沙箱执行（只取 test_cases 的输入）
        from solver_writer import SolverSpec, TestCase
        tmp_cases = [TestCase(name=c["name"], inputs=c["inputs"],
                              oracle_value=c["oracle"], tol=c["tol"])
                     for c in p["cases"]]
        tmp_spec = SolverSpec(spec_id=spec.spec_id,
                              problem_statement=spec.problem_statement,
                              entrypoint=spec.entrypoint,
                              io_contract=spec.io_contract,
                              test_cases=tmp_cases,
                              oracle_kind=spec.oracle_kind)
        res = SandboxExecutor(timeout=120.0).run(p["code"], tmp_spec)
        if not res.get("ok"):
            return None
        out = []
        by_name = {r["name"]: r for r in res.get("results", [])}
        for c in p["cases"]:
            r = by_name.get(c["name"])
            out.append(r["value"] if r and r.get("ok") else None)
        return out

    specs = [VerificationSpec(
        spec_id=spec.spec_id, metric="transmission", oracle_kind="tmm_analytic",
        oracle_fn=_oracle, compare_fn=cmp_max_abs_err,
        tol=0.05, tol_mode="abs",
        target_desc=f"AI-dev 写核：{spec.entrypoint}（{len(spec.test_cases)} 用例）",
        params={"cases": cases_data, "code": candidate_code},
        source="tmm.py 解析透射谱（外部物理定律锚）",
        candidate_desc="AI-dev 候选求解核（沙箱执行）")]
    return specs, {spec.spec_id: _cand}

@_register_candidate(
    "mzm_vpi_nullfit",
    "推挽 MZM 传输谱 T(V)=cos²(Δφ_arm(V)) 数值采样 + 首个传输零点三点抛物线"
    "定顶 —— 与 golden 的解析反解闭式 Vπ=λ₀d/(2n³rΓL) 方法学独立"
    "（数值观测谱零点测量 vs 解析求根，与 B3/B4/B20 峰拟合同族）")
def _mzm_vpi_nullfit_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B28 独立候选：数值零点拟合半波电压 Vπ。

    golden = 解析闭式（对 T(V)=0 条件解析反解）
    cand   = 按 Pockels 相位链算传输谱 T(V)，采样 → 找首个局部极小 →
             三点抛物线定顶（= 实验 Measure Vπ 标准流程的数值化）。
             **从不求值闭式**，也不含任何剖分守恒结构。

    🔴 判据 D 实测（2026-09-03，判据 D 单一定义处复算）：
    n_voltage 2→512 残差 1.91e-3 → 2.34e-8，粗端（n≤8，零点两侧采样对称
    抵消）后 N 加倍误差降 ~8-87×（cos² 四次修正项），**真数值离散化**。
    对照：同锚的沿程积分候选（mzm_vpi_integral）残差恒 4.44e-16 = 代数恒等
    （判据 D 反例，T-1 已证）——**同锚两候选恰成判据 D 的教学对照**。

    基线（生产档位 n_voltage=400）：残差 7.6e-9 V（tol=1e-3 的 0.0008%，
    ≫1e-12 噪声地板，双向可标定）。

    ⚠️ 诚实边界：①同一 1D Pockels 模型，独立性在「解法」不在「模型」（与
    B20 同档）；②扫描上界由相位链 Δφ=π 反解（=2·Vπ），仅括住零点不影响
    定位（上界取 3π 反解结果不变）；③均匀 Γ 假设（求解器支持任意 Γ(z)）。

    ⚠️ 失败即抛异常上浮，绝不静默回退（IndependentCandidateRouter 既定原则）。
    """
    try:
        from lda.lda_solver import mzm_vpi_nullfit as mv
    except ImportError:
        _ensure_paths()
        import mzm_vpi_nullfit as mv

    p = spec.params
    return float(mv.mzm_vpi_nullfit(
        lambda_vac_um=float(p["lambda_vac_um"]),
        n_eff=float(p["n_eff"]),
        r_eff=float(p["r_eff"]),
        gamma=float(p["gamma"]),
        L_um=float(p["L_um"]),
        d_um=float(p["d_um"]),
        n_voltage=mv.DEFAULT_N_VOLTAGE))

@_register_candidate(
    "b31_drude_phase_shift",
    "Drude 自由电子气模型相移（V→ΔN_eff 电子项→Drude Δn→Δφ）—— 与 golden 的 "
    "Soref-Bennett 唯象幂律闭式方法学独立（微观等离子体动力学 vs 宏观经验拟合，"
    "故意非代数恒等，判据 D 不撞；不含空穴项与 many-body 修正）")
def _b31_drude_phase_shift_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B31 独立候选：Drude 自由电子气相移。

    golden = Soref & Bennett 1987 幂律闭式（唯象经验，含空穴 0.8 次幂）；
    cand   = Drude 经典等离子体（仅电子线性项，微观动力学）。
    两者方法学不同源，Drude 缺空穴效应与 many-body 修正 → 与 SB 故意非恒等
    （比值 ~1-2× 即证明捕捉同一等离子体色散物理）。评审 §1「判据 D 不撞」。

    ⚠️ 失败即抛异常上浮，绝不静默回退（IndependentCandidateRouter 既定原则）。
    """
    try:
        from lda.lda_harness import b31_soref_bennett_anchor as ba
    except ImportError:
        _ensure_paths()
        import b31_soref_bennett_anchor as ba
    p = spec.params
    return float(ba.b31_drude_phase_shift(
        V_R=float(p["V_R"]),
        V_bi=float(p.get("V_bi", 0.85)),
        N0=float(p.get("N0", 2e17)),
        lambda_um=float(p.get("lambda_um", 1.55)),
        L_um=float(p.get("L_um", 1000.0)),
        n_eff=float(p.get("n_eff", 2.4))))

@_register_candidate(
    "b32_qcse_numerical",
    "无穷深方势阱 1D 薛定谔有限差分数值对角化（直接对角化 Hamiltonian 含场项 "
    "-eFz/+eFz，取基态 -> 扫 F 定 (E_e+E_h) 跃迁位移）—— 与 golden 的 QCSE 二阶微扰"
    "闭式方法学独立（数值对角化 vs 解析微扰，判据 D 真数值收敛，非代数恒等）")
def _b32_qcse_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B32 独立候选：QCSE 吸收边位移的数值对角化。

    golden = QCSE 二阶微扰闭式 (Miller 1985 / Bastard)；cand = 1D 薛定谔有限差分
    直接对角化（无穷深方势阱，含场项），方法学不同源、数值 vs 解析 -> 判据 D 不撞。
    两者在中等场下偏差 <~2% 即证捕捉同一 QCSE 物理。评审 §2「判据 D 不撞」。

    ⚠️ 失败即抛异常上浮，绝不静默回退（IndependentCandidateRouter 既定原则）。
    """
    try:
        from lda.lda_harness import b32_qcse_anchor as ba
    except ImportError:
        _ensure_paths()
        import b32_qcse_anchor as ba
    p = spec.params
    # 🔴 v0.9.73：键名对齐 golden 形参 L_e/L_h（原读 "L" 与 default_params 只给 L
    # 曾使 harness 路径 golden 抛 TypeError；见 benchmarks.py B32 注记）。
    return float(ba.b32_qcse_edge_shift_meV_numerical(
        V_mod=float(p["V_mod"]),
        d_stack=float(p.get("d_stack", 5e-7)),
        m_e=float(p.get("m_e", ba.B32_M_E_DEFAULT)),
        m_h=float(p.get("m_h", ba.B32_M_H_DEFAULT)),
        L=float(p.get("L_e", p.get("L", ba.B32_L_DEFAULT)))))

@_register_candidate(
    "thermal_phase_fdm",
    "1D 散热鳍 FDM 求解 + 梯形相位积分（同 PDE 三对角离散）—— 与 golden 的 "
    "cosh 解析闭式方法学独立（离散 vs 解析，判据 D 真数值收敛）")
def _b29_thermal_phase_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B29 独立候选：1D 散热鳍 FDM。

    golden = 闭合形式（cosh 解析积分，见 b29_thermal_phase_anchor）；
    cand   = 同一 PDE 三对角 FDM（Thomas）+ 梯形相位积分，从不反解闭式。
    判据 D 实测（v0.9.39）：N=50→6400 残差 0.45°→3.4e-3° 单调收敛（一阶，
    边界引线斜率间断），**真数值离散化**——对照 B28 沿程积分（均匀 integrand
    梯形恒精确 = 代数恒等反例）。基线（N=8000）残差 2.7e-3°（tol 2e-2 的
    0.013%，≫1e-12，双向可标定）。反向 dn_dt±10% ⇒ Δ=3.8°≫tol 必 FAIL。

    ⚠️ 失败即抛异常上浮，绝不静默回退（IndependentCandidateRouter 既定原则）。
    """
    try:
        from lda.lda_solver import thermal_phase_efficiency as tp
    except ImportError:
        _ensure_paths()
        import thermal_phase_efficiency as tp
    p = spec.params
    return float(tp.thermal_phase_efficiency_fdm(
        lambda_um=float(p["lambda_um"]),
        dn_dt=float(p["dn_dt"]),
        h_p=float(p["h_p"]),
        healing_length_um=float(p["healing_length_um"]),
        L_um=float(p["L_um"]),
        P_mw=float(p["P_mw"]),
        n=tp.DEFAULT_N))

@_register_candidate(
    "readout_fidelity_quad",
    "误判概率 ε 的高斯重叠数值积分（两高斯均值 ±SNR）—— 与 golden 的 erfc "
    "闭式方法学独立（梯形积分 vs 闭式，判据 D 真数值收敛）")
def _b30_readout_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B30 独立候选：读出误判概率 ε 的高斯重叠数值积分 → F。

    golden = ε=½erfc(SNR/√2) 闭式（见 b30_readout_anchor）；
    cand   = ε=½·∫min(𝒩(x;-SNR,1), 𝒩(x;+SNR,1))dx（梯形积分）→ F。
    判据 D 实测（v0.9.39）：nx=2001→2e6 残差 9.4e-7→8e-13 单调收敛（真数值
    离散化，非代数恒等）。🔴 工作点取中等 SNR≈2.2（非 t_m* 饱和区）以保证
    反向判别力：nbar/eta/N_amp±10% ⇒ ΔF≈3.4e-3≫tol 1e-3 必 FAIL。

    ⚠️ 失败即抛异常上浮，绝不静默回退（IndependentCandidateRouter 既定原则）。
    """
    try:
        from lda.lda_solver import readout_fidelity_quad as rq
    except ImportError:
        _ensure_paths()
        import readout_fidelity_quad as rq
    p = spec.params
    return float(rq.readout_fidelity_quad(
        chi_ghz=float(p["chi_ghz"]),
        kappa_r_ghz=float(p["kappa_r_ghz"]),
        nbar=float(p["nbar"]),
        eta=float(p["eta"]),
        N_amp=float(p["N_amp"]),
        t_m_s=float(p["t_m_s"]),
        T1_s=float(p["T1_s"]),
        nx=rq.DEFAULT_NX))

@_register_candidate(
    "rc_bandwidth_timestep",
    "RC 暂态梯形法数值积分 + 最小二乘拟合 τ（与解析闭式 1/(2π·R·C) 方法学独立"
    "—— 数值 ODE 拟合 vs 解析公式，判据 D 真数值收敛（n_time 加密残差单调下降）")
def _b33_detector_bandwidth_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B33 独立候选：RC 一阶暂态时域数值积分 → 拟合 τ → f_3dB。

    golden = f_3dB = 1/(2π·R·C)（解析闭式，见 b33_detector_bandwidth_anchor）；
    cand   = 模拟 V(t)=V0(1−e^{−t/τ})（τ=R·C，梯形法数值积分）+ 最小二乘
             拟合 ln(V0−V) 得斜率 −1/τ ⇒ f_3dB=1/(2π·τ)。
    判据 D 实测（v0.9.67）：n_time 4→512 残差 5.5e8→2.5e4 Hz 单调收敛
    （梯形法 O(dt²)，真数值离散化）。基线（n_time=2000）残差 1.66e3 Hz
    （tol=4e3 的 ~2.4× 余量，≫1e-12 噪声地板）。反向 R±10% ⇒ f_3dB∝1/R
    信号 ~2.9e8 Hz ≫ tol 必 FAIL。

    ⚠️ 失败即抛异常上浮，绝不静默回退（IndependentCandidateRouter 既定原则）。
    """
    from lda_harness.b33_detector_bandwidth_anchor import b33_rc_bandwidth_candidate
    p = spec.params
    return float(b33_rc_bandwidth_candidate(
        R=float(p["R"]),
        eps=float(p["eps"]),
        A=float(p["A"]),
        d=float(p["d"]),
        n_time=int(p.get("n_time", 2000))))

@_register_candidate(
    "gauss_p5_margin",
    "闭式高斯 p5 = μ−1.645σ（组件容差解析叠加 μ/σ）—— 与 MC 经验 5% 分位方法学独立")
def _s7_gauss_p5_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """S7 独立候选：闭式高斯最坏情况 p5（margin_p5_dB）。

    golden = 蒙特卡洛 margin 分布经验 5% 分位（固定种子 42）；
    cand   = μ − 1.645σ，μ/σ 由组件工艺容差解析叠加。

    实测（默认参数）：μ=10.5、σ=√(2·0.3²+(0.5·1)²+0.1²)=0.6633、
    p5=10.5−1.6449·0.6633=9.409；golden(MC p5)≈9.41，
    |Δ|≈0.001<tol 0.15（基线属抽样噪声，非恒等）。

    反向 10% 扰动信号谱（candidate 对参数真实响应、golden 取原值）：
    detector_sens_dbm −20→−22 ⇒ μ+2.0 ⇒ |Δ|≈2.0（13×tol）✅
    wg_loss_db_cm 3.0→3.3 ⇒ μ−0.3 ⇒ |Δ|≈0.30（2×）✅
    ⇒ PERTURB 固定扰 detector_sens_dbm（最强键，1% 即抓、min_detect=0.01）。

    ⚠️ 已知边界：候选假设分布为高斯（由独立正态之和的闭式保证），不做
    分布形态检验；「高斯性是否成立」由 s7 distribution_report 方向性断言 +
    实测语料背书，不在本题死标量判决内。
    """
    from .statistical_anchor import s7_gaussian_moments
    p = spec.params
    mu, sigma = s7_gaussian_moments(
        p_tx_dbm=float(p.get("p_tx_dbm", 0.0)),
        n_gratings=int(p.get("n_gratings", 2)),
        grating_db=float(p.get("grating_db", -3.0)),
        wg_length_cm=float(p.get("wg_length_cm", 1.0)),
        wg_loss_db_cm=float(p.get("wg_loss_db_cm", 3.0)),
        ring_il_db=float(p.get("ring_il_db", -0.5)),
        detector_sens_dbm=float(p.get("detector_sens_dbm", -20.0)))
    from .statistical_anchor import GAUSS_Z05
    return float(mu - GAUSS_Z05 * sigma)

@_register_candidate(
    "gauss_p5_osnr",
    "闭式高斯 p5 = μ−1.645σ（σ=√(σ_laser²+σ_nf²)）—— 与 MC 经验 5% 分位方法学独立")
def _s8_gauss_p5_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """S8 独立候选：闭式高斯最坏情况 p5（OSNR_p5_dB）。

    golden = 蒙特卡洛 OSNR 分布经验 5% 分位（固定种子 7）；
    cand   = μ − 1.645σ，其中 10log10(F)=nf+δ 恰为高斯 ⇒ OSNR 严格高斯，
            μ = p_sig − 30 − 10log10(hνbwN) − nf，σ=√(σ_laser²+σ_nf²)。

    实测（默认参数）：μ=46.930、σ=√(0.5²+0.3²)=0.5831、
    p5=46.930−1.6449·0.5831=45.971；golden(MC p5)≈45.93，
    |Δ|≈0.04<tol 0.20（基线属抽样噪声，非恒等）。

    反向 10% 扰动信号谱：
    nf_db 5.0→5.5 ⇒ μ−0.5 ⇒ |Δ|≈0.5（2.5×tol）✅（min_detect=0.05）
    bw_ghz 50→55 ⇒ μ−0.414 ⇒ |Δ|≈0.41（2.1×）✅
    ⇒ PERTURB 固定扰 nf_db（最强键）。

    ⚠️ 已知边界：同 S7，候选假设 OSNR 为高斯（10log10(F)=nf+δ 闭式保证），
    不做形态检验；高斯性由 s8 osnr_distribution_report 方向性断言背书。
    """
    from .statistical_anchor import s8_gaussian_moments, GAUSS_Z05
    p = spec.params
    mu, sigma = s8_gaussian_moments(
        p_sig_dbm=float(p.get("p_sig_dbm", 0.0)),
        n_amp=int(p.get("n_amp", 1)),
        nf_db=float(p.get("nf_db", 5.0)),
        bw_ghz=float(p.get("bw_ghz", 50.0)))
    return float(mu - GAUSS_Z05 * sigma)
