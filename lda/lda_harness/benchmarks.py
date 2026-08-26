"""LDA 验证 harness · 标准题定义（B1–B4、B8，光子子集第一批）。

对应《LDA 领域文献与工具知识基线》模块4 标准题清单；与 L0 IR
`verification.benchmarks` 字段一一对应（id/metric/target/tol/oracle）。
golden_fn 为确定性物理定律锚；target 默认取 golden 计算值（自洽），
可由 L0 IR 覆盖为设计规格目标。
"""
from .golden import (
    b1_mie_qscat, b2_soi_waveguide_neff, b3_fp_fsr_nm,
    b4_ring_fsr_nm, b5_ybranch_split_loss_dB, b6_grating_coupling_eff,
    b7_crossing_crosstalk_dB, b8_taper_transmission,
    b9_transmon_frequency, b10_gate_fidelity, b11_ring_spectrum_match,
    b12_resonator_frequency, b13_coupler_coupling,
    b14_dc_coupling_length, b15_bragg_wavelength, b16_mmi_length,
    b17_jj_critical_current, b18_purcell_factor, b19_link_passivity_bound,
    b20_mzi_fsr,
    b21_phc_resonance,
)

BENCHMARK_DEFS = {
    "B1": {
        "title": "米氏散射远场散射效率 Q_scat",
        "metric": "Q_scat",
        "oracle": "analytical(Mie/Rayleigh)",
        "tol": 2e-4,
        "default_params": {"m": 1.33, "x": 0.4},
        "golden_fn": b1_mie_qscat,
        "note": "Rayleigh 极限（x<<1 与完整 Mie 一致）；miepython 可用时自动升级为完整 Mie ORACLE。",
    },
    "B2": {
        "title": "SOI 条形波导有效折射率 n_eff",
        "metric": "n_eff",
        "oracle": "analytical(EIM)",
        "tol": 0.05,
        "default_params": {"w_core": 0.5, "h_core": 0.22, "n_si": 3.48,
                            "n_clad": 1.44, "wl": 1.55},
        "golden_fn": b2_soi_waveguide_neff,
        "note": "两步有效折射率法（EIM）解析近似；未来升级 MPB/FEM ORACLE。文献锚点 ~2.4–2.6。",
    },
    "B3": {
        "title": "Fabry-Perot etalon 自由光谱范围 FSR",
        "metric": "FSR_nm",
        "oracle": "analytical(Airy)",
        "tol": 1.0,
        "default_params": {"wavelength": 1.55, "n": 1.0, "L": 10.0},
        "golden_fn": b3_fp_fsr_nm,
        "note": "Airy 解析公式 FSR=λ²/(2nL)。",
    },
    "B4": {
        "title": "add-drop 环形谐振器 FSR",
        "metric": "FSR_nm",
        "oracle": "analytical(ring)/sax",
        "tol": 0.3,
        "default_params": {"wavelength": 1.55, "n_g": 4.18, "R": 10.0},
        "golden_fn": b4_ring_fsr_nm,
        "note": "环形传递函数 FSR=λ²/(n_g·2πR)；SAX 电路级 ORACLE 可作交叉验证（见 oracle_sax）。",
    },
    "B8": {
        "title": "绝热锥度（taper）传输效率",
        "metric": "T_taper",
        "oracle": "analytical(adiabatic-limit)",
        "tol": 0.01,
        "default_params": {"w1": 0.2, "w2": 0.5, "L": 200.0,
                            "wl": 1.55, "n_eff": 2.44,
                            "n_core": 3.48, "n_clad": 1.44},
        "golden_fn": b8_taper_transmission,
        "note": "黄金=绝热极限 T→1（物理定律）；核查候选求解器能否达 ≥99% 效率。",
    },
    "B5": {
        "title": "Y 分支(1×2) 分束插入损耗",
        "metric": "split_loss_dB",
        "oracle": "design-rule(Meep/Tidy3D field 预留)",
        "tol": 1.0,
        "default_params": {"w_core": 0.5, "h_core": 0.22, "n_si": 3.48,
                           "n_clad": 1.44, "wl": 1.55, "theta_deg": 10.0},
        "golden_fn": b5_ybranch_split_loss_dB,
        "note": "黄金=理想 50/50 下限 3.0 dB（设计守则锚）；精确真值待 Meep/Tidy3D 场级 ORACLE。",
    },
    "B6": {
        "title": "光栅耦合器峰值耦合效率",
        "metric": "coupling_eff",
        "oracle": "design-rule(Tidy3D/Meep field 预留)",
        "tol": 0.15,
        "default_params": {"wl": 1.55, "n_si": 3.48, "n_clad": 1.44,
                           "period": 0.63, "ff": 0.5, "theta_deg": 8.0},
        "golden_fn": b6_grating_coupling_eff,
        "note": "黄金=成熟工艺可达效率 0.5(≈-3dB)（设计守则锚）；精确真值待 Tidy3D 场级 ORACLE。",
    },
    "B7": {
        "title": "波导交叉串扰",
        "metric": "crosstalk_dB",
        "oracle": "design-rule(Meep field 预留)",
        "tol": 5.0,
        "default_params": {"w_core": 0.5, "h_core": 0.22, "n_si": 3.48,
                           "n_clad": 1.44, "wl": 1.55, "gap": 0.2},
        "golden_fn": b7_crossing_crosstalk_dB,
        "note": "黄金=成熟交叉典型串扰 -40 dB（设计守则锚）；精确真值待 Meep 场级 ORACLE。",
    },
    "B9": {
        "title": "超导 transmon 跃迁频率 f01",
        "metric": "f01_GHz",
        "oracle": "analytical(transmon/Koch2007)",
        "tol": 0.05,
        "default_params": {"E_J": 20.0, "E_C": 0.30},
        "golden_fn": b9_transmon_frequency,
        "note": "transmon 色散近似 f01=√(8·E_J·E_C)−E_C（GHz）；确定性物理定律锚。"
                "EPR 哈密顿量对角化(pyEPR/Ansys)仅作外部 ORACLE。典型 E_J/E_C≈60。",
    },
    "B10": {
        "title": "单量子比特门保真度 F（退相干极限）",
        "metric": "F_gate",
        "oracle": "analytical(decoherence-limit)",
        "tol": 0.01,
        "default_params": {"T1": 80.0, "T2": 60.0, "t_gate": 0.02},
        "golden_fn": b10_gate_fidelity,
        "note": "F=exp(−t_gate·(1/T1+1/(2T2)))（µs）；物理上限锚，对应光子侧 B8 绝热极限。"
                "更精细 RB/XEB(Qiskit)仅作外部 ORACLE。",
    },
    "B11": {
        "title": "环形谐振器 drop 端口透射谱 · 目标谱形 L2 匹配",
        "metric": "spectrum_match",
        "oracle": "analytical(ring-transfer-function)",
        "tol": 0.03,
        "default_params": {"R": 10.0, "n_g": 4.2},
        "golden_fn": b11_ring_spectrum_match,
        "note": "误差=计算谱与目标洛伦兹梳谱形的逐波长 L2 距离；调 R 命中目标 FSR "
                "即匹配谱形。确定性物理定律（环形传递函数）。逆设计'目标谱形'基准。",
    },
    "B12": {
        "title": "超导谐振器 λ/4 最低模 f0",
        "metric": "f0_GHz",
        "oracle": "analytical(quarter-wave closed form)",
        "tol": 0.02,
        "default_params": {"Lp": 0.4e-6, "Cp": 1.5e-10, "l": 3000e-6},
        "golden_fn": b12_resonator_frequency,
        "note": "f0=1/(4l√(L′C′))（GHz，连续极限）；严格侧=D-39 离散 TL 三对角 "
                "特征值（rel~0.25%）。D-40 量子物理锚：同一 IR 表达两种物理。",
    },
    "B13": {
        "title": "双 transmon 电容耦合强度 J",
        "metric": "J_GHz",
        "oracle": "analytical(charge-coupling closed form)",
        "tol": 0.10,
        "default_params": {"E_J1": 20.0, "E_C1": 0.25, "E_J2": 20.0,
                           "E_C2": 0.25, "Cc": 0.02, "C1": 1.0, "C2": 1.0},
        "golden_fn": b13_coupler_coupling,
        "note": "J=Jc·<0|n̂|1>₁·<0|n̂|1>₂（GHz，n01=(E_J/2E_C)^{1/4}/2）；严格侧="
                "D-39 441 维电荷 basis 对角化（rel~4%）。D-40 量子物理锚。",
    },
    "B14": {
        "title": "定向耦合器 3dB 耦合长度",
        "metric": "L_3dB_um",
        "oracle": "analytical(beat-length)",
        "tol": 0.5,
        "default_params": {"n_e": 2.45, "n_o": 2.40, "wl": 1.55},
        "golden_fn": b14_dc_coupling_length,
        "note": "拍波长法 L=λ0/(2|n_e−n_o|)；3dB 点=耦合长度。n_e/n_o 为偶/奇模有效折射率。",
    },
    "B15": {
        "title": "Bragg 光栅中心波长",
        "metric": "lambda_B_um",
        "oracle": "analytical(Bragg condition)",
        "tol": 0.01,
        "default_params": {"n_eff": 2.4, "period": 0.323},
        "golden_fn": b15_bragg_wavelength,
        "note": "一阶 Bragg 条件 λ_B=2·n_eff·Λ；给定 n_eff/Λ 直接算。",
    },
    "B16": {
        "title": "MMI 1×2 自映像长度",
        "metric": "L_mmi_um",
        "oracle": "design-rule(general-interference)",
        "tol": 3.0,
        "default_params": {"W_e": 2.0, "n_eff": 2.4, "wl": 1.55},
        "golden_fn": b16_mmi_length,
        "note": "L=3·L_π，L_π=n_eff·W_e²/λ0（自映像简化，设计守则锚）；精确真值待 FEM ORACLE。",
    },
    "B17": {
        "title": "约瑟夫森结临界电流 I_c",
        "metric": "I_c_A",
        "oracle": "analytical(Josephson relation)",
        "tol": 1e-9,
        "default_params": {"E_J_ghz": 20.0},
        "golden_fn": b17_jj_critical_current,
        "note": "I_c=2e·E_J/ℏ=E_J·1e9·4π·e（A）；确定性约瑟夫森关系。典型 E_J=20GHz→I_c≈40nA。",
    },
    "B18": {
        "title": "谐振腔 Purcell 因子 F_P",
        "metric": "F_purcell",
        "oracle": "analytical(cavity-QED)",
        "tol": 1.0,
        "default_params": {"g_ghz": 0.1, "kappa_ghz": 0.005, "gamma_ghz": 0.001},
        "golden_fn": b18_purcell_factor,
        "note": "F_P=4g²/(κ·γ_1)（标准腔 QED 增强因子）；复用 D-88 物理参数。",
    },
    # ---- P1-M4 链路级物理定律锚（第一道非 AI ground 上提为 B 类题）----
    # 无源线性网络（无外部泵浦）硬约束：所有传递增益 max|T(λ)| ≤ 1 + tol。
    # 能量守恒是其无损（α=0）特例。cmp='le' ⇒ candidate ≤ golden+tol。
    # 链路级缺系统级实证语料 → 仅物理定律锚，不判 E 题（诚实边界）。
    "B19": {
        "title": "无源链路物理定律锚：无增益（passivity / max|T|≤1）",
        "metric": "max|T(λ)| over all transfer paths",
        "oracle": "analytical(passive-network: 无外部泵浦 ⇒ |T|≤1)",
        "tol": 1e-9,
        "default_params": {"type": "wdm", "channels_nm": [1530, 1550, 1570, 1590],
                            "Rs_um": [10.0, 10.34, 10.68, 11.02],
                            "gap_um": 0.3, "n_g": 4.2, "alpha_cm": 2.5},
        "golden_fn": b19_link_passivity_bound,
        "cmp": "le",
        "note": ("链路级第一道非 AI ground：无源网络无增益上界 1.0（损耗合法、"
                 "增益判 FAIL）；能量守恒为无损特例。由 lda_chain 引擎级联输出与"
                 "黄金上界死标量比对，LLM 不进判决路径。"),
    },
    # ---- 内核纵深（D-112 后）：MZI 干涉型 FSR 物理定律锚 ----
    "B20": {
        "title": "MZI 马赫曾德尔干涉仪自由光谱范围 FSR",
        "metric": "FSR_nm",
        "oracle": "analytical(MZI interference)",
        "tol": 1e-6,
        "default_params": {"wl0_um": 1.55, "n_core": 3.48, "deltaL_um": 34.5},
        "golden_fn": b20_mzi_fsr,
        "note": ("MZI 干涉传输 T=½(1+cos(2π·n_eff·ΔL/λ))；FSR=λ²/(n_eff·ΔL)"
                 "（干涉型，与 B4 环形谐振型并列对照）。确定性物理定律锚，"
                 "LLM 不进判决路径；harness 默认 ReferenceCandidate 自洽 PASS。"),
    },
    # ---- 内核纵深（v0.8.3）：光子晶体腔 Fabry–Perot 共振波长物理定律锚 ----
    "B21": {
        "title": "光子晶体腔（布拉格镜 FP 腔）共振波长",
        "metric": "cavity_wl_nm",
        "oracle": "analytical(PhC Bragg/FP band-edge)",
        "tol": 1e-6,
        "default_params": {"L_cav_um": 0.45, "n_core": 3.48, "n_clad": 1.44},
        "golden_fn": b21_phc_resonance,
        "note": ("2D 光子晶体腔 = 均匀高折射率波导腔（L_cav）两端夹持 50% 占空比"
                 "周期性布拉格光栅镜；腔共振 λ_res=(n_core+n_clad)·L_cav"
                 "（FP/布拉格带边，n_eff,grating=(n_core+n_clad)/2 一阶近似，"
                 "2D FDTD 全波验证吻合 ~2%）。确定性物理定律锚，"
                 "LLM 不进判决路径；harness 默认 ReferenceCandidate 自洽 PASS。"),
    },
    # ---- D-62 实证大数据锚（第二道非 AI ground：真实测量语料）----
    # anchor=empirical 的题：golden 来自 EmpiricalCorpus 实测语料（seed_empirical.json
    # + 社区经评审流落库的语料），非解析函数（golden_fn=None）。
    # 比对 = |candidate − measured| ≤ tol（死标量），LLM 永不进判决路径。
    # 诚实边界：种子语料为公开文献/PDK 量级（fab_source 标注来源），
    # 真实晶圆厂 NDA 流片实测属发动期 D-62 联动，经社区提交流持续流入。
    "E1": {
        "title": "SOI 波导有效折射率（实证语料锚）",
        "metric": "n_eff",
        "oracle": "empirical-measurement(E-SOI-NEFF-220)",
        "tol": 0.02,
        "anchor": "empirical",
        "empirical_id": "E-SOI-NEFF-220",
        "default_params": {"w_um": 0.5, "h_um": 0.22, "wl_um": 1.55},
        "golden_fn": None,
        "note": "实证锚：golden=语料实测值 2.63±0.02（IMEC iSiPP50G 公开 PDK 文献量级）；比对=|candidate−measured|≤σ。",
    },
    "E2": {
        "title": "SiN 波导有效折射率（实证语料锚）",
        "metric": "n_eff",
        "oracle": "empirical-measurement(E-SIN-NEFF-300)",
        "tol": 0.02,
        "anchor": "empirical",
        "empirical_id": "E-SIN-NEFF-300",
        "default_params": {"w_um": 0.5, "h_um": 0.3, "wl_um": 1.55},
        "golden_fn": None,
        "note": "实证锚：golden=语料实测值 1.53±0.02（公开 SiN 工艺文献量级）；比对=|candidate−measured|≤σ。",
    },
    "E3": {
        "title": "环形谐振器 FSR（实证语料锚）",
        "metric": "FSR_nm",
        "oracle": "empirical-measurement(E-RING-FSR)",
        "tol": 0.1,
        "anchor": "empirical",
        "empirical_id": "E-RING-FSR",
        "default_params": {"R_um": 10.0, "n_g": 4.18, "wl_um": 1.55},
        "golden_fn": None,
        "note": "实证锚：golden=语料实测值 9.15±0.1（环形谐振器公开测试数据）；比对=|candidate−measured|≤σ。",
    },
}

# 对齐顺序（报告展示用）
BENCHMARK_ORDER = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10",
                   "B11", "B12", "B13", "B14", "B15", "B16", "B17", "B18",
                   "B19", "B20", "B21",
                   "E1", "E2", "E3"]


def register_benchmark(def_dict: dict) -> str:
    """运行时注册一道新 benchmark（社区提案评审→落地用）。

    def_dict 与 BENCHMARK_DEFS 条目同构（title/metric/oracle/tol/default_params/
    golden_fn/note）。golden_fn 必须已是确定性物理定律实现（经具名人工评审的
    ORACLE）。注册后 build_harness_specs 自动纳入统一回归（零接线）。
    """
    bid = str(def_dict.get("bid", "")).strip()
    if not bid:
        raise ValueError("register_benchmark: 缺少 bid")
    if not callable(def_dict.get("golden_fn")):
        raise ValueError(f"register_benchmark: {bid} 的 golden_fn 不可调用")
    item = {k: v for k, v in def_dict.items() if k != "bid"}
    BENCHMARK_DEFS[bid] = item
    if bid not in BENCHMARK_ORDER:
        BENCHMARK_ORDER.append(bid)
    return bid
