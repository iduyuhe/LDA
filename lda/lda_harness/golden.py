"""LDA 验证锚点 · 黄金参考（确定性物理定律锚）。

零外部依赖（仅标准库 math）。对应 L0 IR `verification.benchmarks` 的
B1–B4、B8（光子子集第一批）。所有返回值均为标量 metric，由 harness 与
候选求解器输出比对，按 tol 判定 pass/fail。

设计哲学（见《白皮书》§11 验证锚）：黄金参考必须是**非 AI 的确定性物理
定律/解析解**——方程的必然，而非某人意见。AI 写的内核输出须逐题对照此处。
"""
import math

from .oracle_field import resolve_field_oracle
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
def golden_value(bid, params):
    """按 benchmark id 调用对应黄金参考函数（标量）。"""
    dispatch = {
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
    }
    if bid not in dispatch:
        raise KeyError(f"无黄金参考定义: {bid}")
    return dispatch[bid](**params)


def golden_with_source(bid, params):
    """返回 (value, source, note)。source 标明黄金参考的事实来源：
      - 'physical-law'           B1–B4、B8 确定性物理定律/解析解
      - 'meep-fdtd'              B5/B7 GPL 子进程真场级
      - 'numpy-fdtd-offline'     B7 numpy 2D-FDTD 离线近似
      - 'numpy-overlap-offline'  B5 numpy 重叠估计离线近似
      - 'design-anchor'          设计守则锚（ORACLE 不可用时的验收基准）
    """
    physical_law = {"B1", "B2", "B3", "B4", "B8", "B9", "B10", "B11"}
    if bid in physical_law:
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
