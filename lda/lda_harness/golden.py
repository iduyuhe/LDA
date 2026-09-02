"""LDA 验证锚点 · 黄金参考（确定性物理定律锚）。

零外部依赖（仅标准库 math）。对应 L0 IR `verification.benchmarks` 的
B1–B4、B8（光子子集第一批）。所有返回值均为标量 metric，由 harness 与
候选求解器输出比对，按 tol 判定 pass/fail。

设计哲学（见《白皮书》§11 验证锚）：黄金参考必须是**非 AI 的确定性物理
定律/解析解**——方程的必然，而非某人意见。AI 写的内核输出须逐题对照此处。
"""
import math

import numpy as np

from .oracle_field import resolve_field_oracle
from .system_budget import (  # noqa: E402  # S 系统锚
    s1_power_budget_margin_dB, s2_channel_plan_no_collision,
    s3_osnr_budget, s4_fidelity_budget,
    s5_worst_case_budget, s6_detector_margin,
)
from .statistical_anchor import (  # noqa: E402  # Phase 3 统计锚
    s7_statistical_margin_anchor,
    s8_statistical_osnr_anchor,
)
from .lvs_anchor import (  # noqa: E402  # S9/S10 LVS 签核锚（Phase 4）
    s9_lvs_verdict,
    s10_lvs_multilayer_verdict,
)
from .scale_anchor import s11_large_scale_verdict  # noqa: E402  # S11 规模锚
from .array_distribution_anchor import (  # noqa: E402  # S12 阵列分布锚（v0.8.42）
    array_insertion_loss_anchor, array_fidelity_anchor,
    array_distribution_verdict, s12_array_distribution_verdict,
)
from .yield_anchor import (  # noqa: E402  # S13 设计良率锚（v0.9.1 · DFY）
    yield_analytic, monte_carlo_yield, nominal_ring_length,
    yield_report, yield_vs_tolerance_scan, s13_design_yield_anchor,
)
from .b28_modulator_vpi_anchor import (  # noqa: E402  # B28 MZM Vπ 锚（v0.9.1 · 钉子 D1b=A）
    b28_modulator_vpi, b28_modulator_vpi_report,
)
from .oracle_pyepr import resolve_pyepr_transmon

# B5–B7 设计守则锚（作为 ORACLE 缺失时的下限/上限验收基准）
B5_DESIGN_ANCHOR = 3.0    # Y 分支理想 50/50 分束下限 (dB)
B6_DESIGN_ANCHOR = 0.5    # 光栅耦合峰值效率下限
B7_DESIGN_ANCHOR = -40.0  # 交叉串扰上限 (dB)


# --------------------------------------------------------------------------
# 基础：对称平板波导基模有效折射率（解析本征方程二分求解）
# --------------------------------------------------------------------------
def _slab_neff(thickness, n_core, n_clad, wl, pol="TE"):
    """对称平板（芯层 thickness，两侧 cladding）基模有效折射率。

    thickness: 芯层总厚度(um)；n_core/n_clad: 折射率；wl: 波长(um)；pol: TE/TM。
    解 u·tan(u) = c·sqrt(V^2 - u^2)，u∈(0, min(V, π/2))，二分求解。
    基模 TE0 的 u 恒在 (0, π/2)，故括号恒成立，数值稳健。
    """
    d = thickness / 2.0
    arg = n_core ** 2 - n_clad ** 2
    if arg <= 0:
        return n_clad
    V = (2.0 * math.pi / wl) * d * math.sqrt(arg)
    if V < 1e-9:
        return n_clad
    umax = min(V, math.pi / 2.0 - 1e-9)
    lo, hi = 0.0, umax
    for _ in range(300):
        u = 0.5 * (lo + hi)
        v = math.sqrt(max(V * V - u * u, 0.0))
        if pol == "TE":
            f = u * math.tan(u) - v
        else:
            ne = math.sqrt(max(n_core ** 2 - (u * wl / (2.0 * math.pi * d)) ** 2, 0.0))
            f = u * math.tan(u) - (n_core ** 2 / (ne ** 2 + 1e-30)) * v
        if f > 0:
            hi = u
        else:
            lo = u
    u = 0.5 * (lo + hi)
    ne = math.sqrt(max(n_core ** 2 - (u * wl / (2.0 * math.pi * d)) ** 2, 0.0))
    return ne


# --------------------------------------------------------------------------
# B1 · 米氏散射远场散射效率 Q_scat（解析解）
# --------------------------------------------------------------------------
def b1_mie_qscat(m, x, use_miepython=True):
    """散射效率因子 Q_scat。

    默认采用 **Rayleigh（偶极子）极限**——x<<1 时与完整 Mie 精确一致，
    是麦克斯韦方程的解析极限解（物理定律锚，零成本、确定性）。
    若环境装有 miepython（MIT，MIEV0 验证），自动改用完整 Mie 级数作
    ORACLE（覆盖任意 x，确定性、非负）。
    """
    if use_miepython:
        try:
            import miepython  # 可选 ORACLE
            _, q_sca, _, _ = miepython.efficiencies(m, x)
            return float(q_sca)
        except Exception:
            pass
    # Rayleigh 极限（Bohren & Huffman §5.4）
    ratio = (m * m - 1.0) / (m * m + 2.0)
    return (8.0 / 3.0) * (x ** 4) * (ratio * ratio)


# --------------------------------------------------------------------------
# B2 · SOI 条形波导有效折射率 n_eff（两步有效折射率法 EIM）
# --------------------------------------------------------------------------
def b2_soi_waveguide_neff(w_core, h_core, n_si, n_clad, wl, pol="TE"):
    """矩形 SOI 波导有效折射率（有效折射率法 EIM，解析）。

    第一步：横向（宽度 w_core）平板 -> n_x；
    第二步：纵向（厚度 h_core）平板，芯层折射率=n_x -> n_eff。
    注：EIM 为近似解析法（未来可升级为 MPB/FEM ORACLE 作更精确真值）。
    """
    n_x = _slab_neff(w_core, n_si, n_clad, wl, pol)
    n_eff = _slab_neff(h_core, n_x, n_clad, wl, pol)
    return n_eff


# --------------------------------------------------------------------------
# B3 · Fabry-Perot etalon 自由光谱范围 FSR（Airy 解析）
# --------------------------------------------------------------------------
def b3_fp_fsr_nm(wavelength, n, L):
    """FP 标准具自由光谱范围（波长域，nm）。

    FSR = λ^2 / (2·n·L)，λ、L 同单位（um）；返回 nm。
    解析 Airy 公式（物理定律），确定性。
    """
    fsr_um = (wavelength ** 2) / (2.0 * n * L)
    return fsr_um * 1000.0


# --------------------------------------------------------------------------
# B4 · add-drop 环形谐振器 FSR（解析传递函数）
# --------------------------------------------------------------------------
def b4_ring_fsr_nm(wavelength, n_g, R):
    """环形谐振器自由光谱范围（nm）。

    FSR = λ^2 / (n_g · 2π R)，λ、R 同单位（um）；返回 nm（×1000）。
    解析环形传递函数（物理定律），确定性。
    """
    fsr_um = (wavelength ** 2) / (n_g * 2.0 * math.pi * R)
    return fsr_um * 1000.0


# --------------------------------------------------------------------------
# B8 · 绝热锥度（taper）传输效率（绝热极限 = 物理定律）
# --------------------------------------------------------------------------
def b8_taper_transmission(w1, w2, L, wl, n_eff, n_core, n_clad):
    """绝热锥度传输效率 T。

    黄金参考取**绝热极限 T→1**（物理定律：绝热演化无辐射损耗）。
    本基准核查候选求解器能否复现 ≥(1-tol) 的锥度效率；参数化由 L0 组件
    提供（w1/w2/L）。绝热判据的实现细节留给候选求解器，harness 只卡
    "是否达到绝热极限" 这一物理上限。
    """
    # 绝热极限：T = 1（确定性物理上限）
    return 1.0


# --------------------------------------------------------------------------
# B9 · 超导 transmon 基态→第一激发态跃迁频率 f01（解析，Koch 2007）
# --------------------------------------------------------------------------
def b9_transmon_frequency(E_J, E_C):
    """transmon 第一跃迁频率 f01（GHz）。

    f01 = sqrt(8 · E_J · E_C) − E_C，E_J / E_C 为约瑟夫森能 / 充电能（GHz）。
    标准 transmon 解析色散近似（Koch et al. 2007, Eq.2.15），确定性物理定律。
    这是量子 EDA 验证锚的"物理定律地基"——对应光子侧的 B2/B4 解析解；
    真实 EPR 哈密顿量对角化(pyEPR/Ansys)仅作外部 ORACLE 交叉验证。
    """
    # 可选 pyEPR 外部 ORACLE（B 级：仅外部、核心不 import）；缺失回退解析解
    ora = resolve_pyepr_transmon({"E_J": E_J, "E_C": E_C})
    if ora and ora.get("value") is not None:
        return float(ora["value"])
    return math.sqrt(8.0 * E_J * E_C) - E_C


# --------------------------------------------------------------------------
# B10 · 单量子比特门保真度 F（退相干极限，解析）
# --------------------------------------------------------------------------
def b10_gate_fidelity(T1, T2, t_gate):
    """单量子比特门保真度（退相干极限，解析）。

    F = exp( −t_gate·( 1/T1 + 1/(2·T2) ) )，T1/T2 为弛豫/退相干时间(µs)，
    t_gate 为门时长(µs)。这是门保真度的物理上限（只受相干时间限制），
    对应光子侧 B8 的"绝热极限"——确定性物理定律锚。
    更精细的 RB/XEB 模型(pyEPR/Qiskit)仅作外部 ORACLE 交叉验证。
    """
    return math.exp(-t_gate * (1.0 / T1 + 1.0 / (2.0 * T2)))


# --------------------------------------------------------------------------
# B12 · 超导谐振器 λ/4 最低模 f0（闭式，D-40 量子物理锚）
# --------------------------------------------------------------------------
def b12_resonator_frequency(Lp, Cp, l):
    """λ/4 谐振器最低模 f0（GHz，连续极限闭式）。

    f0 = 1/(4·l·√(L′·C′))，L′/C′ 为传输线分布电感/电容（H/m、F/m），l 为长度
    （m）。确定性物理定律（连续极限）；严格侧=D-39 离散 TL 三对角特征值
    （rel 收敛 <1%，N=400）。这是量子 EDA 验证锚的第二块"物理定律地基"。
    """
    return 1.0 / (4.0 * l * math.sqrt(Lp * Cp)) / 1e9


# --------------------------------------------------------------------------
# B13 · 双 transmon 电容耦合强度 J（解析，D-40 量子物理锚）
# --------------------------------------------------------------------------
def b13_coupler_coupling(E_J1, E_C1, E_J2, E_C2, Cc, C1, C2):
    """有效 qubit-qubit 耦合 J（GHz，解析闭式）。

    J = Jc·<0|n̂|1>₁·<0|n̂|1>₂，Jc=Cc/(C_Σ1·C_Σ2)，n01=(E_J/2E_C)^{1/4}/2
    （Koch 类闭式）。确定性物理定律（微扰闭式）；严格侧=D-39 双 qubit
    441 维电荷 basis 对角化（共振 rel~4%≤10%）。量子 EDA 第三块物理锚。
    """
    Jc = Cc / (C1 * C2)
    n01_1 = (E_J1 / (2.0 * E_C1)) ** 0.25 / 2.0
    n01_2 = (E_J2 / (2.0 * E_C2)) ** 0.25 / 2.0
    return Jc * n01_1 * n01_2


# --------------------------------------------------------------------------
# B14 · 定向耦合器 3dB 耦合长度（解析：偶/奇模拍波长法）
# --------------------------------------------------------------------------
def b14_dc_coupling_length(n_e, n_o, wl):
    """定向耦合器 3dB 耦合长度 L_3dB（um，确定性物理定律）。

    耦合模理论：P2(z)=sin²(κz)，κ=π|Δn|/λ。完全转移长度（P2=1）
    L_π=λ/(2|Δn|)；3dB 点（P2=0.5）= L_π/2 = λ/(4|Δn|)。

    🔴 v0.9.20 语义修正（D-66「怀疑 golden 本身」第 4 例）：原式
    λ/(2|n_e−n_o|) 是**完全转移长度**（P2=1.0，RK4 实证），被错标为
    3dB 点。P2(λ/2Δn)=sin²(π/2)=1.0、P2(λ/4Δn)=sin²(π/4)=0.5 ——
    3dB 点恰为完全转移长度之半。同源消费点（_dc_supermode_core 的
    相位校验 Δβ·L=π 正是完全转移点）一并修正。
    """
    return wl / (4.0 * abs(n_e - n_o))


# --------------------------------------------------------------------------
# B15 · Bragg 光栅中心波长（解析：一阶 Bragg 条件）
# --------------------------------------------------------------------------
def b15_bragg_wavelength(n_eff, period):
    """一阶 Bragg 光栅中心波长 λ_B（um，确定性物理定律）。

    λ_B = 2·n_eff·Λ（一级 Bragg 条件）。period 单位 um。
    """
    return 2.0 * n_eff * period


# --------------------------------------------------------------------------
# B16 · MMI 1×2 自映像长度（解析：general interference principle）
# --------------------------------------------------------------------------
def b16_mmi_length(W_e, n_eff, wl):
    """1×2 MMI 自映像长度 L_mmi（um，设计守则锚）。

    L_π = n_eff·W_e²/λ0（自映像条件简化，忽略 cladding 修正）；
    1×2 MMI 取 p=3 自映像 L = 3·L_π。确定性几何光学（MMI 自成像原理）。
    精确真值待 FEM ORACLE。
    """
    L_pi = n_eff * (W_e ** 2) / wl
    return 3.0 * L_pi


# --------------------------------------------------------------------------
# B17 · 约瑟夫森结临界电流（解析：Josephson 关系）
# --------------------------------------------------------------------------
def b17_jj_critical_current(E_J_ghz):
    """Al 约瑟夫森结临界电流 I_c（A，确定性物理定律）。

    E_J = (Φ0/2π)·I_c → I_c = 2·e·E_J/ℏ = E_J_ghz·1e9·4π·e。
    E_J 以频率单位(GHz)给出（E_J/h）。典型 E_J≈20GHz 对应 I_c≈40nA
    （铝 JJ 工艺）。量子 EDA 第四块物理锚（器件级）。
    """
    e = 1.602176634e-19
    return E_J_ghz * 1e9 * 4.0 * math.pi * e


# --------------------------------------------------------------------------
# B18 · 谐振腔 Purcell 因子（解析：腔 QED 增强因子）
# --------------------------------------------------------------------------
def b18_purcell_factor(g_ghz, kappa_ghz, gamma_ghz):
    """腔 QED Purcell 增强因子 F_P（无量纲，确定性物理定律）。

    F_P = 4·g²/(κ·γ_1)（标准腔 QED 定义：发射到腔模 vs 自由空间）。
    复用 D-88 物理：g=单光子 Rabi/耦合，κ=腔衰减率，γ_1=原子退相干率。
    量子 EDA 第五块物理锚。
    """
    return 4.0 * (g_ghz ** 2) / (kappa_ghz * gamma_ghz)


# --------------------------------------------------------------------------
# B11 · 环形谐振器 drop 端口透射谱 "目标谱形" 匹配误差（标量，越小越好）
# --------------------------------------------------------------------------
def b11_ring_spectrum_match(R, n_g, wl0=1.55, target_fsr=9.15):
    """环形谐振器 drop 端口透射谱 "目标谱形" 匹配误差（标量，越小越好）。

    均匀洛伦兹梳谱形完全由其共振周期 FSR 决定；agent 调 R 使计算 FSR 命中
    target_fsr 即匹配目标谱形。误差 = |FSR_c − FSR_t| / FSR_t（归一化周期失配），
    在 R 上单谷、随 R 单调（FSR∝1/R），对任意梯度/二分优化器都稳健收敛——
    这避免了"逐波长 L2 谱形误差"在梳状混频处产生的伪局部极小。误差是确定性
    物理定律（环形传递函数），零依赖。逆设计从"单/多标量指标"迈向"目标谱形"
    的关键一跃。
    """
    fsr_c = (wl0 ** 2) / (n_g * 2.0 * math.pi * R) * 1000.0   # 计算 FSR(nm)
    return abs(fsr_c - target_fsr) / target_fsr


# --------------------------------------------------------------------------
# B5 · Y 分支(1×2 分束器) 插入损耗(dB)
# --------------------------------------------------------------------------
def b5_ybranch_split_loss_dB(w_core, h_core, n_si, n_clad, wl, theta_deg):
    """Y-branch 1×2 分束插入损耗(dB)。

    优先取场级 ORACLE（Meep 子进程 → numpy 离线重叠估计）；ORACLE 缺失时
    回退到设计守则锚 B5_DESIGN_ANCHOR=3.0 dB（理想 50/50 下限）。
    真值 ORACLE 来源见 golden_with_source 的 source 字段。
    """
    params = dict(w_core=w_core, h_core=h_core, n_si=n_si, n_clad=n_clad,
                  wl=wl, theta_deg=theta_deg)
    oracle = resolve_field_oracle("B5", params)
    if oracle and oracle.get("value") is not None:
        return oracle["value"]
    return B5_DESIGN_ANCHOR


# --------------------------------------------------------------------------
# B6 · 光栅耦合器峰值耦合效率
# --------------------------------------------------------------------------
def b6_grating_coupling_eff(wl, n_si, n_clad, period, ff, theta_deg):
    """光栅耦合器峰值耦合效率。

    优先取场级 ORACLE（需 Tidy3D 3D，离线无近似）；缺失时回退设计守则锚
    B6_DESIGN_ANCHOR=0.5（工艺成熟下限）。
    """
    params = dict(wl=wl, n_si=n_si, n_clad=n_clad, period=period,
                  ff=ff, theta_deg=theta_deg)
    oracle = resolve_field_oracle("B6", params)
    if oracle and oracle.get("value") is not None:
        return oracle["value"]
    return B6_DESIGN_ANCHOR


# --------------------------------------------------------------------------
# B7 · 波导交叉串扰(dB)
# --------------------------------------------------------------------------
def b7_crossing_crosstalk_dB(w_core, h_core, n_si, n_clad, wl, gap):
    """波导交叉串扰(dB)。

    优先取场级 ORACLE（Meep 子进程 → numpy 2D-FDTD 离线真场计算）；缺失时
    回退设计守则锚 B7_DESIGN_ANCHOR=-40 dB（典型上限）。
    """
    params = dict(w_core=w_core, h_core=h_core, n_si=n_si, n_clad=n_clad,
                  wl=wl, gap=gap)
    oracle = resolve_field_oracle("B7", params)
    if oracle and oracle.get("value") is not None:
        return oracle["value"]
    return B7_DESIGN_ANCHOR


# --------------------------------------------------------------------------
# 调度器 + 来源标注
# --------------------------------------------------------------------------
# 模块级调度表与物理定律锚集合：支持运行时 register_golden 动态注册
# （社区提案经「具名人工评审 → 确定性自测」后落地接入统一回归；
#  仅登记确定性物理定律，LLM 不进判决路径）。

# --------------------------------------------------------------------------
# B19 · 链路级物理定律锚：无源网络无增益（passivity）
# --------------------------------------------------------------------------
def b19_link_passivity_bound(**kwargs):
    """无源线性网络（无外部泵浦）的物理硬约束：所有传递增益 |T(λ)| ≤ 1。

    这是链路级第一道非 AI ground（与 B1–B19 同框架、同死标量比对）；
    能量守恒是其无损（α=0）特例——无损 ⇒ S 幺正 ⇒ 功率守恒。本锚以
    「无增益上界」表达，损耗（|T|<1）合法，增益（|T|>1）判 FAIL。

    golden 为无源上界常量 1.0；配合 harness cmp='le' 判定
    candidate(=max|T(λ)|) ≤ 1.0 + tol。
    """
    return 1.0


def b20_mzi_fsr(wl0_um: float = 1.55, n_core: float = 3.48,
                deltaL_um: float = 34.5) -> float:
    """MZI 马赫曾德尔干涉仪自由光谱范围 FSR（确定性物理定律锚）。

    MZI 两臂几何长度差 ΔL 导致单程相位累积 φ(λ)=2π·n_eff·ΔL/λ，干涉传输
    T(λ)=½(1+cos φ)。波长自由光谱范围（相邻透射峰间距）：
        FSR_λ = λ² / (n_eff · ΔL)
    确定性物理定律（麦克斯韦干涉解，与 B4 环形 FSR=λ²/(n_g·2πR) 并列：
    MZI 为「干涉型」、Ring 为「谐振型」，两道锚互为对照验证地基）。
    返回单位 nm。
    """
    return 1000.0 * wl0_um ** 2 / (n_core * deltaL_um)


def b21_phc_resonance(L_cav_um: float = 0.45, n_core: float = 3.48,
                      n_clad: float = 1.44) -> float:
    """光子晶体腔（布拉格反射镜 Fabry–Perot 腔）共振波长（确定性物理定律锚）。

    2D 光子晶体腔 = 均匀高折射率波导腔（长 L_cav）两端由 50% 占空比周期性
    布拉格光栅镜（周期 a_m、折射率 n_core/n_clad 交替）夹持。其腔共振由
    Fabry–Perot / 布拉格带边条件决定：
        λ_res = 2 · n_eff,grating · L_cav
    其中 50% 占空比深调制光栅的本征有效折射率取两介质折射率的算术平均
    n_eff,grating = (n_core + n_clad)/2（一阶近似；2D FDTD 全波验证吻合 ~2%）。
    故 λ_res = (n_core + n_clad) · L_cav。
    返回单位 nm。与 B4（环形谐振 FSR）、B15（布拉格波长）、B20（MZI 干涉 FSR）
    同属"周期结构带边"物理定律锚家族，互为对照验证地基。
    """
    return 1000.0 * (n_core + n_clad) * L_cav_um


def b22_qres_frequency(L_um: float = 4000.0, n_eff: float = 2.5) -> float:
    """CPW λ/4 读出谐振器基模频率（确定性物理定律锚）。

    超导量子比特读出谐振器 = 共面波导（CPW）传输线 λ/4 谐振器：远端短路
    （接地）、近端（耦合端）开路。其基模谐振频率由传输线理论确定：
        f0 = c0 / (4 · L · n_eff)
    其中 c0 为真空中光速（um/ps），L 为谐振器物理长度（um），
    n_eff = √ε_eff 为 CPW 有效折射率（ε_eff 为等效介电常数；Si 衬底
    （ε_r≈11.7）上对称 CPW 典型 ε_eff≈(ε_r+1)/2≈6.35 → n_eff≈2.52）。
    返回单位 GHz。与 B4（环形谐振 FSR）、B12（集总 LC 谐振）、B21（光子晶体腔
    共振）同属"周期/谐振结构"物理定律锚家族，互为对照验证地基；并直接补强
    QEDA 栈——与 Transmon 引擎配对构成"比特 + 读出"基础单元。
    """
    return 1000.0 * 299.792458 / (4.0 * L_um * n_eff)


def b23_fluxonium_lc_limit(ec_ghz: float = 1.0, el_ghz: float = 1.0) -> float:
    """Fluxonium LC 谐振严格极限（确定性物理定律锚）。

    Fluxonium 哈密顿量 H = 4·E_C·n² + ½·E_L·(φ−φ_ext)² − E_J·cos(φ)。
    在 E_J → 0 严格极限下退化为 LC 谐振子，能级间隔解析精确：
        f01 = √(8·E_C·E_L) / h
    （能量以 GHz 计即 E/h，该式直接给出 GHz）。此极限是 Fluxonium 任意
    参数数值对角化的物理边界校验点；任意 E_J 的 f01 无解析闭式（正是
    Fluxonium 必须数值对角化的原因），其验证采用双基独立数值对拍
    （相位网格有限差分 vs 谐振子基展开，见 verify_fluxonium）。
    返回单位 GHz。与 B9（Transmon）、B22（读出谐振器）同属超导量子
    器件物理定律锚家族。
    """
    return float(np.sqrt(8.0 * ec_ghz * el_ghz))


def b24_tcoup_geff(wq_ghz: float = 5.0, wc_ghz: float = 7.5,
                   g1_ghz: float = 0.10, g2_ghz: float = 0.10) -> float:
    """可调耦合器二阶有效耦合强度（确定性物理定律锚）。

    两个 transmon 量子比特（频率 wq，经中间可调耦合器 wc）的等效直接
    耦合由二阶微扰论（Schrieffer-Wolff / 中间态虚跃迁）解析给出：
        g_eff = (g1·g2/2) · (1/Δ1 + 1/Δ2)，  Δi = wi − wc
    共振情形 w1=w2=wq 时 g_eff = g1·g2·wq/(wc²−wq²)，严格成立；数值
    验证 = 三模 Fock 截断对角化激发带对称/反对称劈裂 /2（见
    verify_tunable_coupler）。该锚是 QEDA 架构（可调耦合器开/关两比特
    门）的核心解析基准。
    返回单位 GHz（代数值；负值表示可调"关"点一侧）。
    """
    d1 = wq_ghz - wc_ghz
    d2 = wq_ghz - wc_ghz
    return 0.5 * g1_ghz * g2_ghz * (1.0 / d1 + 1.0 / d2)


def b25_tunable_transmon_f01(phi_frac: float = 0.0,
                             e_j_sum_ghz: float = 20.0,
                             e_c_ghz: float = 0.30) -> float:
    """可调 transmon（SQUID 磁通调谐）f01（确定性物理定律锚）。

    SQUID 有效约瑟夫森能随外磁通调谐：E_J(Φ) = E_JΣ·|cos(π·Φ/Φ0)|
    （对称双结 SQUID 的一阶近似）。transmon 频率（Koch 一阶）：
        f01(Φ) = √(8·E_C·E_J(Φ)) − E_C
    返回单位 GHz。Φ/Φ0=0 时 E_J=E_JΣ（最大频率）；Φ/Φ0=0.5 时
    E_J→0（调谐"关"点，频率降至 E_C 以下）。与 B9（固定频率 transmon）
    互补——本锚给出磁通调谐自由度，是 QEDA 可调比特/可调耦合的基础。
    """
    ej_phi = e_j_sum_ghz * abs(math.cos(math.pi * phi_frac))
    return float(math.sqrt(8.0 * e_c_ghz * ej_phi) - e_c_ghz)


def b26_dispersive_shift(f_q_ghz: float = 5.0, alpha_ghz: float = -0.30,
                         f_r_ghz: float = 6.0,
                         g_ghz: float = 0.10) -> float:
    """量子比特-读出谐振器色散位移（确定性物理定律锚）。

    超导量子比特（transmon/fluxonium）与读出谐振器在失谐区（|Δ|≫g，
    Δ=f_q−f_r）的色散耦合导致读出频率依赖比特态的移动（Blais 修正）：
        χ = g²·α / (Δ·(Δ+α))
    返回单位 GHz（代数值；负 α ⇒ 负 χ）。数值验证 = 多能级+Fock 联合
    严格对角化提取 χ（见 qeda_depth_solver），实测 rel ~0.6~2%。
    是读出保真度 / 色散读出架构的核心物理量。
    """
    delta = f_q_ghz - f_r_ghz
    return float(g_ghz * g_ghz * alpha_ghz
                 / (delta * (delta + alpha_ghz)))


def b27_cz_gate_time(f_q_ghz: float = 5.0, alpha_ghz: float = -0.30,
                     f_r_ghz: float = 6.0,
                     g_ghz: float = 0.10) -> float:
    """色散 CZ 门时间（确定性物理定律锚）。

    基于色散耦合实现受控-Z（CZ）门：|11⟩ 态相对相移 φ = 2·χ·t，条件相位
    π 所需时间（GHz→ns，频率单位 GHz 时 t=π/(2|χ|) 直接给 ns）：
        t_CZ = π / (2·|χ|)，χ 见 B26
    数值验证：2·|χ|·t_CZ = π 精确成立（rel=0.000%）。返回单位 ns。
    是固定频率比特 CZ 门 / 门时间预算的核心解析基准。
    """
    chi = b26_dispersive_shift(f_q_ghz, alpha_ghz, f_r_ghz, g_ghz)
    return float(math.pi / (2.0 * abs(chi)))


_GOLDEN_DISPATCH = {
    "B1": b1_mie_qscat,
    "B2": b2_soi_waveguide_neff,
    "B3": b3_fp_fsr_nm,
    "B4": b4_ring_fsr_nm,
    "B5": b5_ybranch_split_loss_dB,
    "B6": b6_grating_coupling_eff,
    "B7": b7_crossing_crosstalk_dB,
    "B8": b8_taper_transmission,
    "B9": b9_transmon_frequency,
    "B10": b10_gate_fidelity,
    "B11": b11_ring_spectrum_match,
    "B12": b12_resonator_frequency,
    "B13": b13_coupler_coupling,
    "B14": b14_dc_coupling_length,
    "B15": b15_bragg_wavelength,
    "B16": b16_mmi_length,
    "B17": b17_jj_critical_current,
    "B18": b18_purcell_factor,
    "B19": b19_link_passivity_bound,
    "B20": b20_mzi_fsr,
    "B21": b21_phc_resonance,
    "B22": b22_qres_frequency,
    "B23": b23_fluxonium_lc_limit,
    "B24": b24_tcoup_geff,
    "B25": b25_tunable_transmon_f01,
    "B26": b26_dispersive_shift,
    "B27": b27_cz_gate_time,
    "B28": b28_modulator_vpi,                  # v0.9.1 MZM 调制器半波电压 Vπ（Pockels 电光）
    # ---- S 系统锚（Phase 0-1，2026-08-26）----
    "S1": s1_power_budget_margin_dB,
    "S2": s2_channel_plan_no_collision,
    "S3": s3_osnr_budget,
    "S4": s4_fidelity_budget,
    "S5": s5_worst_case_budget,
    "S6": s6_detector_margin,
    "S7": s7_statistical_margin_anchor,
    "S8": s8_statistical_osnr_anchor,
    "S9": s9_lvs_verdict,
    "S10": s10_lvs_multilayer_verdict,
    "S11": s11_large_scale_verdict,
    "S12": s12_array_distribution_verdict,   # v0.8.42 阵列分布锚（锚+统计混合）
    "S13": s13_design_yield_anchor,          # v0.9.1 设计良率锚（DFY）
}

_PHYSICAL_LAW = {"B1", "B2", "B3", "B4", "B8", "B9", "B10", "B11",
                 "B12", "B13", "B14", "B15", "B16", "B17", "B18",
                 "B19", "B20", "B21", "B22", "B23", "B24", "B25",
                 "B26", "B27", "B28",
                 "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8",
                 "S9", "S10", "S11", "S12",
                 "S13"}  # S 系统锚（…+S12 阵列分布+S13 设计良率）


def golden_value(bid, params):
    """按 benchmark id 调用对应黄金参考函数（标量）。"""
    if bid not in _GOLDEN_DISPATCH:
        raise KeyError(f"无黄金参考定义: {bid}")
    return _GOLDEN_DISPATCH[bid](**params)


def register_golden(bid, fn, physical_law=True):
    """运行时注册黄金参考（社区提案评审→落地用）。

    bid: benchmark id（如 'B19'）；fn: 确定性物理定律实现（ORACLE）；
    physical_law=True 时同时标记为物理定律锚，纳入 golden_with_source 的
    'physical-law' 来源判定。仅登记经具名人工评审通过的 ORACLE，LLM 不进判决路径。
    """
    if not callable(fn):
        raise ValueError(f"register_golden: {bid} 的 fn 不可调用")
    _GOLDEN_DISPATCH[bid] = fn
    if physical_law:
        _PHYSICAL_LAW.add(bid)
    return bid


def golden_with_source(bid, params):
    """返回 (value, source, note)。source 标明黄金参考的事实来源：
      - 'physical-law'           B1–B4、B8 确定性物理定律/解析解
      - 'meep-fdtd'              B5/B7 GPL 子进程真场级
      - 'numpy-fdtd-offline'     B7 numpy 2D-FDTD 离线近似
      - 'numpy-overlap-offline'  B5 numpy 重叠估计离线近似
      - 'design-anchor'          设计守则锚（ORACLE 不可用时的验收基准）
    """
    if bid in _PHYSICAL_LAW:
        return (golden_value(bid, params), "physical-law", "确定性物理定律/解析解")
    # B5–B7：查 ORACLE 来源
    if bid in ("B5", "B6", "B7"):
        ora_params = dict(params)
        if bid == "B5":
            ora_params = dict(w_core=params.get("w_core", 0.4),
                              h_core=params.get("h_core", 0.22),
                              n_si=params.get("n_si", 3.48),
                              n_clad=params.get("n_clad", 1.44),
                              wl=params.get("wl", 1.55),
                              theta_deg=params.get("theta_deg", 15.0))
        elif bid == "B6":
            ora_params = dict(wl=params.get("wl", 1.55),
                              n_si=params.get("n_si", 3.48),
                              n_clad=params.get("n_clad", 1.44),
                              period=params.get("period", 0.6),
                              ff=params.get("ff", 0.5),
                              theta_deg=params.get("theta_deg", 8.0))
        else:  # B7
            ora_params = dict(w_core=params.get("w_core", 0.4),
                              h_core=params.get("h_core", 0.22),
                              n_si=params.get("n_si", 3.48),
                              n_clad=params.get("n_clad", 1.44),
                              wl=params.get("wl", 1.55),
                              gap=params.get("gap", 0.0))
        res = resolve_field_oracle(bid, ora_params)
        if res and res.get("value") is not None:
            return (res["value"], res.get("source", "field-oracle"),
                    res.get("note", ""))
        anchor = {"B5": B5_DESIGN_ANCHOR, "B6": B6_DESIGN_ANCHOR,
                  "B7": B7_DESIGN_ANCHOR}[bid]
        return (anchor, "design-anchor", "ORACLE 不可用，回退设计守则锚")
    raise KeyError(f"无黄金参考定义: {bid}")
