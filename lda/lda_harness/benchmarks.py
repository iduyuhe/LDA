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
    b22_qres_frequency,
    b23_fluxonium_lc_limit,
    b24_tcoup_geff,
    b25_tunable_transmon_f01,
    b26_dispersive_shift,
    b27_cz_gate_time,
    # S 系统锚（Phase 0 · Merge-0）
    s1_power_budget_margin_dB,
    # S2-S6 系统锚（Merge-2b · Phase 1 锚题库）
    s2_channel_plan_no_collision,
    s3_osnr_budget,
    s4_fidelity_budget,
    s5_worst_case_budget,
    s6_detector_margin,
    # S7 统计锚（Phase 3 · 专投区第一刀，蒙特卡洛分布）
    s7_statistical_margin_anchor,
    # S8 统计锚（Phase 3 · OSNR 统计延伸，模板复用）
    s8_statistical_osnr_anchor,
    # S9 LVS 签核锚（Phase 4 · 版图-原理图一致性判决）
    s9_lvs_verdict,
    # S10 多层 LVS 锚（Phase 4 · 金属/通孔层叠，版图差距 #6）
    s10_lvs_multilayer_verdict,
    # S11 千器件规模锚（Phase 4 · 版图差距 #7 收官）
    s11_large_scale_verdict,
    # S12 阵列分布锚（Phase 4 · v0.8.42 · 锚+统计混合判决）
    s12_array_distribution_verdict,
    # S13 设计良率锚（v0.9.1 · DFY · 解析闭式 ↔ 蒙特卡洛双算法互证）
    s13_design_yield_anchor,
)
from .b28_modulator_vpi_anchor import (  # noqa: E402  # B28 MZM Vπ 锚（v0.9.1 · 钉子 D1b=A）
    b28_modulator_vpi, b28_modulator_vpi_report,
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
        # v0.9.16（P0 续）：接入独立候选 —— 数值扫 Airy 透射谱、定峰后对 1/λ
        # 做等距拟合（频域周期 Δu=1/(2nL)），再换算回波长域。**不调用**闭式。
        "candidate": "fp_fsr_peakfit",
        "candidate_desc": ("数值 Airy 响应谱峰周期拟合 FSR（自适应开窗 + 抛物线定峰"
                           " + 1/λ 等距最小二乘）—— 与 golden 闭式方法学独立"),
        "default_params": {"wavelength": 1.55, "n": 1.0, "L": 10.0},
        "golden_fn": b3_fp_fsr_nm,
        "note": ("Airy 解析公式 FSR=λ²/(2nL)。"
                 "⚠️ 口径澄清（v0.9.16 接线时实测）：峰满足 2nL=mλ ⇒ 1/λ 严格等距，"
                 "闭式 λ²/(2nL) 是该频域等距性的**一阶连续化**，与「相邻峰的波长实测间距」"
                 "相差 O(1/m)。本锚 m=2nL/λ≈12.9 ⇒ 该差约 6.7%（8.1nm，超出 tol=1.0）。"
                 "故候选统一按**频域周期**口径取值（与闭式同一物理量），"
                 "而非量「相邻峰波长差」——后者测的是另一个量，会假红。"),
    },
    "B4": {
        "title": "add-drop 环形谐振器 FSR",
        "metric": "FSR_nm",
        "oracle": "analytical(ring)/sax",
        "tol": 0.3,
        # v0.9.16（P0 续）：接入独立候选 —— 数值扫 add-drop 环 drop 口传递函数、
        # 定峰后对 1/λ 做等距拟合（频域周期 Δu=1/(n_g·2πR)），再换算回波长域。
        "candidate": "ring_fsr_peakfit",
        "candidate_desc": ("数值 add-drop 环传递函数（drop 口）峰周期拟合 FSR"
                           "—— 与 golden 闭式方法学独立"),
        "default_params": {"wavelength": 1.55, "n_g": 4.18, "R": 10.0},
        "golden_fn": b4_ring_fsr_nm,
        "note": ("环形传递函数 FSR=λ²/(n_g·2πR)；SAX 电路级 ORACLE 可作交叉验证（见 oracle_sax）。"
                 "⚠️ 同 B3 口径：闭式是频域等距性的一阶连续化，本锚 m=n_g·2πR/λ≈169 "
                 "⇒ 与「相邻峰波长实测间距」相差约 0.59%（0.054nm）。"
                 "候选按频域周期口径取值，与闭式同一物理量。"),
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
        "note": "黄金=理想 50/50 下限 3.0 dB（设计守则锚）；精确真值待 Meep/Tidy3D 场级 ORACLE。"
                "D-66 澄清：本锚的 split_loss_dB **含 3.01dB 理想分光**（1×2 均分的几何必然），"
                "与实证锚 E-YBRANCH-LOSS 的「过量损耗 excess_loss_dB=0.28±0.02dB」**非同一量**，"
                "二者互补（本锚=下界，实证锚=实测过量），不可互相替代或相加混用。",
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
        "candidate": "transmon_exact",
        "candidate_desc": ("电荷基严格对角化 f01（N=20，41 维 eigh）——"
                           "与 golden 的 Koch 色散近似方法学独立"),
        "note": "transmon 色散近似 f01=√(8·E_J·E_C)−E_C（GHz）；确定性物理定律锚。"
                "EPR 哈密顿量对角化(pyEPR/Ansys)仅作外部 ORACLE。典型 E_J/E_C≈60。"
                "【v0.9.14 P0-1】48 锚中**首道接真独立候选**的题：golden=Koch 解析"
                "渐近，candidate=电荷基严格对角化（41 维 eigh）。实测偏差 rel=0.22%"
                "（6.628203→6.613449，diff=1.475e-2 GHz），落在既有 tol=0.05 内"
                "——本锚 tol 早期即按物理容差设定，无需放宽（对照：B20-B28 后期"
                "锚清一色 tol=1e-6，该量级设计上只容得下 candidate≡golden）。",
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
        # v0.9.17（P0 续）：接入独立候选 —— 二阶 ghost-point 边界的离散传输线
        # 三对角本征值（N=400）。本锚 note 原就写着「严格侧=离散 TL 三对角特征值」，
        # 但 harness 从未真接过（一直落自证桩）；现在把宣称接成事实。
        # ⚠️ tol=0.02 **未放宽**：实测残差 6.913e-6（d/tol=3.5e-4，余量 2894×）。
        "candidate": "tl_eigen_f0",
        "candidate_desc": ("二阶 ghost-point 边界离散传输线三对角本征值 f0（N=400）"
                           "—— 与 golden 的连续极限闭式方法学独立"),
        "default_params": {"Lp": 0.4e-6, "Cp": 1.5e-10, "l": 3000e-6},
        "golden_fn": b12_resonator_frequency,
        "note": "f0=1/(4l√(L′C′))（GHz，连续极限）；严格侧=D-39 离散 TL 三对角 "
                "特征值（rel~0.25%）。D-40 量子物理锚：同一 IR 表达两种物理。"
                "⚠️ v0.9.17 实测订正：库内 `_discrete_f0` 开路端用单边一阶差分"
                "（A[N-1,N-1]=-1）⇒ 收敛仅 O(1/N)、N=200 残差 2.7e-2，连 tol=0.02 "
                "都过不去。候选改用 ghost point（Dirichlet 端 d[0]=-3 / Neumann 端 "
                "d[-1]=-1）恢复 O(1/N²)，N=400 残差 6.9e-6（rel 0.0064%，非原 note "
                "的 0.25%）。反向 10% 扰动 Lp/Cp/l 残差 0.50/0.50/0.98 GHz 全被抓。",
    },
    "B13": {
        "title": "双 transmon 电容耦合强度 J",
        "metric": "J_GHz",
        "oracle": "analytical(charge-coupling closed form)",
        # v0.9.17（P0 续）：tol 由 0.10 **收紧 50× 到 2.0e-3**（加严不是放宽）。
        # 0.10 相当于 golden（0.0316）的 316% —— 等于什么都抓不住的自证桩容差。
        # 实测基线残差 1.3131e-3（rel 4.15%，与本 note 原写的「rel~4%」吻合，
        # Nq=8 起已收敛）⇒ 该 4.15% 是渐近闭式的固有截断误差，tol 取其 1.52 倍。
        "tol": 2.0e-3,
        "candidate": "coupler_charge_exact",
        "candidate_desc": ("双 transmon 441 维电荷基严格对角化 J（Nq=10）"
                           "—— 与 golden 的电荷矩阵元渐近闭式方法学独立"),
        "default_params": {"E_J1": 20.0, "E_C1": 0.25, "E_J2": 20.0,
                           "E_C2": 0.25, "Cc": 0.02, "C1": 1.0, "C2": 1.0},
        "golden_fn": b13_coupler_coupling,
        "note": "J=Jc·<0|n̂|1>₁·<0|n̂|1>₂（GHz，n01=(E_J/2E_C)^{1/4}/2）；严格侧="
                "D-39 441 维电荷 basis 对角化（rel~4%）。D-40 量子物理锚。"
                "🔴 v0.9.17 诚实披露：本锚判据窗口窄、有**已知反向盲区**。"
                "10% 扰动逐键实测残差：C1/C2 4.07e-3（3.10× 基线）✅被抓 · "
                "E_C1/E_C2 2.06e-3（1.57×）✅被抓 · Cc 1.72e-3（1.31×）❌漏抓 · "
                "E_J1/E_J2 5.50e-4（0.42×，**比基线还小**）❌漏抓 —— E_J 扰动使"
                "严格解朝渐近值靠近（扰动与近似误差偶然抵消，同 B26 现象），故"
                "任何 tol>基线的取值都抓不住 E_J 键。tol=2.0e-3 是「正向 PASS」与"
                "「尽量多抓反向键」的最优折中（4/7 键可抓），反向测试固定扰 C1。",
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
        # v0.9.19（P0 续）：接独立候选 —— 反周期 Bloch 广义本征值 ↔ 相位匹配闭式。
        # v0.9.18 曾判「不接」：在库 tmm.py 是垂直入射多层膜（物理对象错配）。
        # v0.9.19 新写 lda_solver/bragg_solver.py：E(z) 周期调制的波动方程
        # 广义本征值问题，反周期边界锁定 k=±π/Λ，谱最低简并对=第一带隙。
        "candidate": "bragg_bloch_exact",
        "candidate_desc": ("反周期 Bloch 广义本征值 A ψ=β²B ψ（N=240，带隙中心"
                           "2π/β_c）↔ 一阶相位匹配闭式 λ_B=2·n_eff·Λ，方法学独立"),
        "note": "一阶 Bragg 条件 λ_B=2·n_eff·Λ；给定 n_eff/Λ 直接算。"
                "【v0.9.19 P0 续】候选=Bloch 本征值（golden=运动学闭式 vs cand="
                "动力学全波本征谱，调制深度 m 进入算子）。实测 baseline|diff|="
                "8.356e-6（tol=0.01 未动，余量 1196×）；反向 n_eff×1.1 信号 "
                "1.55e-1（15.5×）。网格 N=240 双向标定（N=480 偶然抵消点 5.4e-8、"
                "N=960 越 LAPACK 地板反升，均避开，详 bragg_solver.py）。",
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
        # v0.9.16（P0 续）：接入独立候选 —— 数值扫 MZI 干涉谱、定峰后对 1/λ 做
        # 等距拟合（频域周期 Δu=1/(n_eff·ΔL)），再换算回波长域。**不调用**闭式。
        # ⚠️ tol=1e-6 原是「自证桩容差」量级（相对量 5e-8）；接线前担心真独立候选
        # 满足不了，实测残差 4.7e-10（d/tol≈4.7e-4，余量 2000×）⇒ 无需动 tol。
        "candidate": "mzi_fsr_peakfit",
        "candidate_desc": ("数值 MZI 干涉谱 T=½(1+cos φ) 峰周期拟合 FSR"
                           "—— 与 golden 闭式方法学独立"),
        "default_params": {"wl0_um": 1.55, "n_core": 3.48, "deltaL_um": 34.5},
        "golden_fn": b20_mzi_fsr,
        "note": ("MZI 干涉传输 T=½(1+cos(2π·n_eff·ΔL/λ))；FSR=λ²/(n_eff·ΔL)"
                 "（干涉型，与 B4 环形谐振型并列对照）。确定性物理定律锚，"
                 "LLM 不进判决路径。"
                 "⚠️ 同 B3 口径：闭式是频域等距性的一阶连续化，本锚 m=n_eff·ΔL/λ≈77.5 "
                 "⇒ 与「相邻峰波长实测间距」相差约 1.29%（0.26nm，是 tol=1e-6 的 26 万倍）。"
                 "候选按频域周期口径取值，与闭式同一物理量；**tol 未因接线而放宽**"
                 "（放宽 tol 等于取消验证，是 P0 的纪律红线）。"),
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
    # ---- 内核纵深（v0.8.4）：CPW λ/4 读出谐振器基模频率物理定律锚 ----
    "B22": {
        "title": "CPW λ/4 读出谐振器基模频率 f0",
        "metric": "qres_f_ghz",
        "oracle": "analytical(CPW λ/4 TL resonance)",
        "tol": 1e-6,
        # v0.9.17（P0 续）：接入独立候选 —— 与 B12 同一台离散 TL 本征求解器
        # （二阶 ghost 边界），相速 v=c0/n_eff。⚠️ tol=1e-6 **未放宽**：
        # 实测 N=4000 残差 4.982e-8（d/tol=4.98e-2，余量 20×）。
        "candidate": "tl_eigen_qres",
        "candidate_desc": ("二阶 ghost-point 边界离散传输线三对角本征值 f0（N=4000）"
                           "—— 与 golden 的 CPW λ/4 闭式方法学独立"),
        "default_params": {"L_um": 4000.0, "n_eff": 2.5},
        "golden_fn": b22_qres_frequency,
        "note": ("超导量子比特读出谐振器 = 共面波导（CPW）λ/4 谐振器（远端短路/"
                 "近端开路）；基模 f0=c0/(4·L·n_eff)（传输线理论，n_eff=√ε_eff "
                 "为 CPW 有效折射率，Si 衬底典型 ≈2.5）。确定性物理定律锚，"
                 "LLM 不进判决路径。与 Transmon 引擎配对补强 QEDA「比特+读出」"
                 "基础单元。"
                 "⚠️ v0.9.17 实测证伪：**TL-FDTD 路线不可用于本锚** —— "
                 "`device_library._qres_tlfdtd_core` 的 FFT 记录长度 ∝ dt ∝ 1/N，"
                 "网格细化反而缩短时窗、降低频率分辨率 ⇒ 残差随 N **恶化**"
                 "（N=200: 8.4e-2 → N=1600: 3.6e-2，全部远超 tol）。故候选走"
                 "本征值路线。N 也不能无限加大：N=8000 残差 2.6e-8、N=16000 反升到 "
                 "1.0e-7（越过 LAPACK 数值地板，已非离散误差主导）⇒ 标定 N=4000。"
                 "反向 10% 扰动 L_um/n_eff 残差均 0.68 GHz（tol 的 6.8e5 倍）。"),
    },
    # ---- 内核纵深（v0.8.5）：Fluxonium LC 极限 / 可调耦合器二阶锚 ----
    "B23": {
        "title": "Fluxonium LC 谐振严格极限 f01",
        "metric": "fluxonium_f01_ghz",
        "oracle": "analytical(LC oscillator strict limit E_J→0)",
        "tol": 1e-6,
        # v0.9.17（P0 续）：接入独立候选 —— 谐振子基矩阵严格对角化（ncut=24，
        # Ej=0 严格极限）。⚠️ tol=1e-6 **未放宽**：实测残差 7.752e-9
        # （d/tol=7.8e-3，余量 129×）。
        "candidate": "fluxonium_ho_exact",
        "candidate_desc": ("Fluxonium 谐振子基矩阵严格对角化 f01（ncut=24）"
                           "—— 与 golden 的 LC 极限闭式 √(8·Ec·El) 方法学独立"),
        "default_params": {"ec_ghz": 1.0, "el_ghz": 1.0},
        "golden_fn": b23_fluxonium_lc_limit,
        "note": ("Fluxonium H=4Ec·n²+½El(φ−φext)²−Ej·cosφ 在 Ej→0 严格极限"
                 "退化为 LC 谐振子 f01=√(8·Ec·El)（GHz 计能直接给出）。任意 Ej "
                 "无解析闭式 → 数值对角化双基对拍验证（相位网格 vs 谐振子基）。"
                 "确定性物理定律锚，LLM 不进判决路径。"
                 "⚠️ v0.9.17 ncut 双向标定：ncut=20 ⇒ 4.89e-7（d/tol=0.49，余量"
                 "不足 2×）· ncut=24 ⇒ 7.75e-9（d/tol=7.8e-3，余量 129×）✅ 选定 · "
                 "ncut=28 ⇒ 1.19e-10 · ncut=32 ⇒ 1.73e-12 —— 后两档已贴到 1e-12 "
                 "自证桩判据，再精就与「直接 return golden」按值不可区分，自动护栏"
                 "会误报假独立。反向 10% 扰动 ec/el 残差均 0.138 GHz。"),
    },
    "B24": {
        "title": "可调耦合器二阶有效耦合 g_eff",
        "metric": "tcoup_geff_ghz",
        "oracle": "analytical(2nd-order perturbation / Schrieffer-Wolff)",
        # v0.9.17（P0 续）：tol 由 1e-6 **按实测重定为 3e-5**。1e-6 是「自证桩容差」
        # （只容得下 candidate≡golden）；闭式与三模严格解的**固有模型差**实测
        # 1.272e-5（rel 0.32%，ncut=2/3/4/5 完全一致 ⇒ 已收敛、非截断噪声）。
        # 3e-5 = 实测差 × 2.36 余量，且落在判据窗口 (1.272e-5, 4.045e-4)=31.8× 内
        # ⇒ 正向 PASS 与「反向 10% 扰动必 FAIL」同时成立（四键全被抓）。
        "tol": 3e-5,
        "candidate": "tcoup_fock_exact",
        "candidate_desc": ("三模 Fock 截断严格对角化激发带劈裂/2（ncut=3），符号由"
                           "本征矢宇称独立判定 —— 与 golden 的二阶微扰/SW 闭式方法学独立"),
        "default_params": {"wq_ghz": 5.0, "wc_ghz": 7.5,
                           "g1_ghz": 0.10, "g2_ghz": 0.10},
        "golden_fn": b24_tcoup_geff,
        "note": ("两 transmon 经可调耦合器的等效直接耦合（二阶微扰/SW 变换）"
                 "g_eff=(g1g2/2)(1/Δ1+1/Δ2)，共振 w1=w2 时严格。数值验证 = "
                 "三模 Fock 截断对角化激发带劈裂/2。QEDA 可调耦合器架构核心"
                 "解析基准。确定性物理定律锚，LLM 不进判决路径。"
                 "🔴 v0.9.17 符号纪律：golden 在 Δ<0（qubit 低于耦合器）时为**负**"
                 "（默认 Δ1=Δ2=−2.5 ⇒ golden=−0.004），候选**不得取绝对值** —— "
                 "符号由本征矢宇称独立判定（较低的 qubit-like 态若 |100⟩ 与 |010⟩ "
                 "振幅同号则 g_eff<0）。⚠️ 张量序 q1⊗q2⊗c、q1 为最高位 ⇒ qubit2 "
                 "激发索引是 1*ncut（不是 1，那是耦合器激发）；首版误用后端索引导致"
                 "宇称判反、候选出正值、残差 7.99e-3（超 tol 7987×）。"
                 "反向 10% 扰动：g1/g2 4.05e-4 · wc 9.29e-4 · wq 9.75e-4，四键全被抓。"),
    },
    # ---- 器件库主流封口（v0.8.7）：可调 transmon / 色散读出 / CZ 门 ----
    "B25": {
        "title": "可调 transmon（SQUID 磁通调谐）f01(Φ)",
        "metric": "tunable_f01_ghz",
        "oracle": "analytical(SQUID E_J(Φ)=E_JΣ·|cos(πΦ/Φ0)| + Koch)",
        "tol": 0.05,
        "default_params": {"phi_frac": 0.0, "e_j_sum_ghz": 20.0,
                           "e_c_ghz": 0.30},
        "golden_fn": b25_tunable_transmon_f01,
        "candidate": "transmon_exact",
        "candidate_desc": ("电荷基严格对角化 f01(E_J(Φ))（N=20，41 维 eigh）——"
                           "与 golden 的 Koch 色散近似方法学独立"),
        "note": ("可调 transmon f01(Φ)=√(8·Ec·EJ(Φ))−Ec，EJ(Φ)=EJΣ·|cos(πΦ/Φ0)|"
                 "（SQUID 磁通调谐）。Φ=0 最大频率、Φ=0.5 调谐关点。确定性物理"
                 "定律锚，LLM 不进判决路径。"
                 "【v0.9.14 P0-1】接独立候选（电荷基严格对角化），脱离自证桩。"
                 "tol 1e-6→0.05（依据：与 B9 同一物理同一方法学，实测 Φ=0/0.1/"
                 "0.2/0.3 四点偏差 1.475e-2~2.011e-2 GHz，rel=0.22%~0.40%；"
                 "0.05 为该实测最大偏差的 2.5 倍余量，且仍远小于典型设计误差"
                 "量级 ⇒ 既能容纳近似式固有误差，又能抓住真错误，"
                 "由反向测试（扰动必 FAIL）兜底防止容差放水）。"),
    },
    "B26": {
        "title": "量子比特-读出谐振器色散位移 χ",
        "metric": "dispersive_chi_ghz",
        "oracle": "analytical(Blais χ=g²α/(Δ(Δ+α)))",
        "tol": 1e-4,
        "default_params": {"f_q_ghz": 5.0, "alpha_ghz": -0.30,
                           "f_r_ghz": 6.0, "g_ghz": 0.10},
        "golden_fn": b26_dispersive_shift,
        "candidate": "chi_exact",
        "candidate_desc": ("L=6 能级 transmon + Fock 谐振器联合严格对角化"
                           "（162 维 eigh）—— 与 golden 的 Blais 微扰闭式"
                           "方法学独立"),
        "note": ("色散位移 χ=g²α/(Δ(Δ+α))（Blais 修正），失谐区 |Δ|≫g。数值"
                 "验证 = 多能级+Fock 联合严格对角化提取（实测 rel 0.6~2%）。"
                 "确定性物理定律锚，LLM 不进判决路径。"
                 "【v0.9.14 P0-1】接独立候选（L=6 多能级 + Fock 联合严格"
                 "对角化，162 维 eigh），脱离自证桩。tol 1e-6→1e-4"
                 "（依据：实测 χ_golden=−2.307692e-3 vs χ_num=−2.261958e-3，"
                 "diff=4.573e-5，rel=1.98%；L 收敛扫描 L=3→6 得 2.46%/1.98%/"
                 "1.98%/1.98%，L=5→6 已稳定 ⇒ 该偏差是**微扰闭式在 g/Δ=0.1 "
                 "下的固有误差**、非数值噪声。1e-4 为实测偏差的 2.2 倍余量，"
                 "反向测试兜底）。"),
    },
    "B27": {
        "title": "色散 CZ 门时间 t_CZ",
        "metric": "cz_gate_time_ns",
        "oracle": "analytical(t_CZ=π/(2|χ|))",
        "tol": 30.0,
        "default_params": {"f_q_ghz": 5.0, "alpha_ghz": -0.30,
                           "f_r_ghz": 6.0, "g_ghz": 0.10},
        "golden_fn": b27_cz_gate_time,
        "candidate": "cz_exact",
        "candidate_desc": ("t_CZ=π/(2|χ_num|)，χ_num 由 L=6 多能级+Fock 联合"
                           "对角化给出 —— 与 golden 的闭式 χ 方法学独立"),
        "note": ("色散 CZ 门时间 t_CZ=π/(2|χ|)（GHz→ns）；校验 2|χ|·t_CZ=π 精确"
                 "成立。确定性物理定律锚，LLM 不进判决路径。"
                 "【v0.9.14 P0-1】接独立候选（χ 取严格对角化值后反推 t_CZ），"
                 "脱离自证桩。tol 1e-6→30ns"
                 "（依据：实测 golden=680.678ns vs cand=694.441ns，"
                 "diff=13.76ns，rel=2.02%；30ns 为实测偏差的 2.2 倍余量）。"
                 "⚠️ 诚实边界：B27 与 B26 **共用同一数值 χ**，故 B27 并非"
                 "完全独立于 B26（一荣俱荣）。它真正验证的是"
                 "「χ→t_CZ 换算链路」+「χ 数值侧自洽」，能抓住换算因子错误"
                 "（如漏 1/2），但独立性弱于 B26——不重复计入独立锚强度。"),
    },
    # ---- 有源调制器封口（v0.9.1 · 钉子 D1b=A）：MZM 半波电压 Vπ ----
    "B28": {
        "title": "MZM 调制器半波电压 Vπ（电光相位调制 · Pockels）",
        "metric": "Vpi_volts",
        "oracle": "analytical(MZM Pockels half-wave) + integral-bisect cross-check",
        "tol": 1e-3,
        "default_params": {"lambda_vac_um": 1.55, "n_eff": 2.2,
                           "r_eff": 30.8e-12, "gamma": 0.5,
                           "L_um": 10000.0, "d_um": 8.0},
        "golden_fn": b28_modulator_vpi,
        "note": ("MZM 半波电压 Vπ=λ₀·d/(2·n_eff³·r_eff·Γ·L)（推挽 Pockels 电光"
                 "相位调制确定性物理定律，零模型假设）。golden=解析闭式；ORACLE"
                 "交叉验证=沿程积分+二分（通用 Γ(z)），均匀段退化等于闭式、"
                 "机器精度一致（Δ<1e-6V）→ 非 AI ground。实证量级（LiNbO3 "
                 "x-cut MZM Vπ≈3.8V）仅作 honest-sanity，不进死标量判决。与 "
                 "B20 无源 MZI-FSR 双锚闭合「MZI 无源+有源」。LLM 不进判决路径；"
                 "harness 默认 ReferenceCandidate 自洽 PASS。"),
    },
    # ---- D-62 实证大数据锚（第二道非 AI ground：真实测量语料）----
    # anchor=empirical 的题：golden 来自 EmpiricalCorpus 实测语料（seed_empirical.json
    # + 社区经评审流落库的语料），非解析函数（golden_fn=None）。
    # 比对 = |candidate − measured| ≤ tol（死标量），LLM 永不进判决路径。
    # 诚实边界：种子语料为公开文献/PDK 量级（fab_source 标注来源），
    # 真实晶圆厂 NDA 流片实测属发动期 D-62 联动，经社区提交流持续流入。
    "E1": {
        "title": "SOI 波导群折射率（实证语料锚 · AMF racetrack 实测 FSR 反演）",
        "metric": "n_g",
        "oracle": "empirical-measurement(E-SOI-NG-220)",
        "tol": 0.10,
        "anchor": "empirical",
        "empirical_id": "E-SOI-NG-220",
        "default_params": {"w_um": 0.5, "h_um": 0.22, "wl_um": 1.5476,
                           "L_um": 66.8, "shape": "racetrack"},
        "golden_fn": None,
        "note": "实证锚（**A 级可溯源**，D-66 逐字核实后由 B 级升级）："
                "golden=**实测**群折射率 n_g=4.18±0.05 —— Advanced Micro Foundry 商用 SOI 平台、"
                "二氧化硅埋层条形波导 500×220 nm²、add-drop racetrack 谐振腔 L=66.8 µm，"
                "透射谱 FSR **实测** 8.6 nm 反演（λp=1547.6 nm）。"
                "来源 arXiv:2011.03273，DOI 10.48550/arXiv.2011.03273（可公开取回）。"
                "自洽校验：λ²/(n_g·L) = 1547.6²/(4.18×66800) = 8.59 nm ≈ 实测 8.6 nm。"
                "**D-66 改判说明（必须一并阅读）**：原 E-SOI-NEFF-220 声称 n_eff=2.63±0.02 @1550 nm，"
                "逐字核实后判定**该值有误** —— 公开文献与 3 个独立模式求解器一致给出"
                "500×220 SOI TE0 的 n_eff = 2.44~2.46（2.63 实为 λ≈1.39 µm 处的取值，"
                "偏离 0.19，为其自称不确定度 ±0.02 的近 10 倍）。且 n_eff 本身极少直接测量"
                "（D-64 定论：多为 MZI/谐振反演的导出量），未找到任何可公开溯源的"
                "500×220 n_eff 实测出处。故**改判为群折射率 n_g 锚**并取同一文献的实测量。"
                "⚠️ **判决路径仍为自证桩**：candidate 尚未接独立求解器（ReferenceCandidate，"
                "|candidate−golden|≡0）。且已知 LDA 现有**标量**亥姆霍兹 FDFD 对 SOI 高对比度波导"
                "（3.48/1.44）不达标：FDFD 算直波导 n_g=3.74 对实测 4.18 差约 10% —— "
                "🔴 **R16（FDFD 网格收敛缺口）已于 2026-09-01 实测证伪**：上 sub-cell averaging "
                "+ 网格细化 dl=24→64 均无效（n_g 纹丝不动 ~3.74，偏差与网格无关）；根因两层——"
                "①FDFD 标量求解器本身精度不足（直波导 n_eff 偏差 0.18~0.37）②**对象不对齐**："
                "golden 4.18 是**弯曲/环器件**群折射率（Garrisi 用 ring FSR 反演），FDFD 解直波导，"
                "弯曲使模式更受限→n_g 天然高 ~0.46。故 E1 保持自证桩、不强行接 FDFD 对照"
                "（**C 方案诚实边界降级**：FDFD 直波导候选与环 golden 几何不同源、精度不足，仅作量级参考）。"
                "本条升级仅表示 **golden 已可公开溯源**，**不表示求解器已通过验证**。"
                "比对为死标量 |candidate−measured|≤tol，LLM 永不进判决路径。",
    },
    "E2": {
        "title": "SiN 波导群折射率（实证语料锚 · 实测↔FDFD 独立频域交叉验证）",
        "metric": "n_g",
        "oracle": "empirical-measurement(E-SIN-NG-300)",
        "tol": 0.10,
        "anchor": "empirical",
        "empirical_id": "E-SIN-NG-300",
        "candidate": "fdfd_ng",
        # v0.9.14：候选状态**机器可读**化（此前仅写在 note 散文里，无法被程序
        # 统计，正是审计 N-2 类问题的根源——信息只存在于人类可读文本中）。
        #   "degraded_ordinal" = 候选与 golden **几何不同源/精度不足**，
        #     仅作量级参考，不进死标量判决（诚实边界 C，2026-09-01 R16 证伪）
        #   （缺省/"strict"）= 进死标量判决的真独立候选
        "candidate_status": "degraded_ordinal",
        "default_params": {"w_um": 1.0, "h_um": 0.3, "n_core": 2.0, "n_clad": 1.44,
                           "wl_um": 1.55, "clad_um": 3.0, "dl_factor": 24.0},
        "golden_fn": None,
        "note": "实证锚（A 级可溯源）：golden=**实测**群折射率 n_g=1.892 —— "
                "300nm LPCVD Si3N4 平台、1.0×0.3μm 全刻蚀条形波导，OFDR 环形谐振腔群延迟实测"
                "（MZI 传输谱交叉验证 1.90–1.92，TM=1.717），公开 URL 可溯源。"
                "几何已对齐实测器件（原 500nm 宽 → 1000nm 宽），避免「异器件测量冒充实测」。"
                "**D-64 关键整改**：本锚首次接入**独立候选求解器**（candidate=fdfd_ng）——"
                "由标量亥姆霍兹 FDFD 本征模算 n_eff(λ) 后中心差分得 n_g"
                "（固定网格 dl=λ/24、δ=20nm；f=24→48 收敛差 0.008），**不再返回 golden 自身**。"
                "实测 1.892 vs FDFD 1.959（clad=3.0/λ24），差 0.067（3.5%），容差 0.10 覆盖。"
                "⚠️ **D-65 精度边界（必须与结论一起读，2026-09-01 实测）**：该候选的"
                "**数值不确定度本身就有 ±0.04** —— 同一器件仅改计算窗口"
                "（clad=1.5/2.0/2.5/3.0/4.0 µm），n_g 在 1.878~1.962 间散射"
                "（f=24 散射 0.084、f=32 散射 0.053），n_eff 散射更大（SOI 侧达 0.25）。"
                "🔴 **根因已修正（2026-09-01 实测）**：原 D-65 诊断「网格过粗」**不准确**——"
                "实测 dl=24→64（λ/64）n_g 变化 <0.02，早已收敛，非网格截断误差；"
                "±0.04~0.08 散射实为**计算窗口尺寸扫描**造成（clad 改变波导约束），非网格。"
                "两层真因：①FDFD 标量求解器对高反差细波导精度不足（直波导 n_eff "
                "SOI=2.62 文献~2.44/+0.18、SiN=1.61 文献~1.98/−0.37）②**对象不对齐**："
                "golden 来自弯曲/环器件，FDFD 解直波导。🔴 **R16（亚网格 ε 平均）已证伪**："
                "averaging + 细网格均不能把 E1/E2 拉进容差（SOI n_g 反而 3.776→3.741 恶化）。"
                "**故本锚当前只能判定『量级一致 + 判决路径真实』，不能宣称『精度验证』**——"
                "所有测试窗口下均落在容差内（最大 |diff|=0.078 < 0.10），判定本身鲁棒"
                "（已钉进 smoke 窗口鲁棒性断言），但 0.10 容差中约 ±0.08 是数值不确定度、非物理裕度。"
                "🔴 **R16 降级为诚实边界 C**：FDFD 直波导候选与环 golden 几何不同源、精度不足，"
                "仅作量级参考，不宣称精度验证（与 D-66 诚实边界一致）。"
                "另：差距主因=标量近似不辨 TE/TM（实测 TE 1.892/TM 1.717，标量解偏高）+"
                "未建模材料色散（补 Sellmeier 后反而更远：1.990）。LLM 不进判决路径。",
    },
    "E3": {
        "title": "薄埋氧 SOI 微环 FSR（实证语料锚 · 实测↔解析交叉验证）",
        "metric": "FSR_nm",
        "oracle": "empirical-measurement(E-TBOX-FSR-TM)",
        "tol": 0.1,
        "anchor": "empirical",
        "empirical_id": "E-TBOX-FSR-TM",
        "default_params": {"R_um": 7.5, "n_g": 4.92, "wl_um": 1.5576},
        "golden_fn": None,
        "note": "实证锚：golden=**实测** FSR 10.44 nm（Sridaran & Bhave, Opt. Express 18(4) 3850 (2010)，"
                "R=7.5um 环扫频实测峰间距）。解析式 λ²/(ng·2πR)=10.46 nm 与实测差 0.02 nm——"
                "golden 取自真实测量而非公式，实测↔解析构成交叉验证。"
                "（旧版 golden 9.15 系由 FSR=λ²/(ng·2πR) 反算且 ng 源自 2D FDTD 仿真，"
                "属「物理定律/仿真值冒充实测」，已于 D-63 溯源整改时替换。）",
    },
    "E4": {
        "title": "SOI 波导 crossing 插入损耗（实证语料锚）",
        "metric": "insertion_loss_dB",
        "oracle": "empirical-measurement(E-SOI-CROSS-IL)",
        "tol": 0.1,
        "anchor": "empirical",
        "empirical_id": "E-SOI-CROSS-IL",
        "default_params": {"w_um": 0.5, "h_um": 0.22, "wl_um": 1.55},
        "golden_fn": None,
        "note": "实证锚：golden=语料实测值 0.18±0.03 dB（CMOS 兼容 crossing，8 英寸晶圆，Zhang PTL 2013）；比对=|candidate−measured|≤tol。",
    },
    "E5": {
        "title": "MMI 1×2 过量损耗（实证语料锚）",
        "metric": "excess_loss_dB",
        "oracle": "empirical-measurement(E-MMI-1X2-EL)",
        "tol": 0.1,
        "anchor": "empirical",
        "empirical_id": "E-MMI-1X2-EL",
        "default_params": {"w_um": 0.5, "h_um": 0.22, "wl_um": 1.55},
        "golden_fn": None,
        "note": "实证锚：golden=语料实测值 0.05 dB（SOI MMI 1×2，TE 1550nm，Chack & Hassan OE 2020）；比对=|candidate−measured|≤tol。",
    },
    "E6": {
        "title": "厚 SiN 波导传播损耗（实证语料锚）",
        "metric": "propagation_loss_dBcm",
        "oracle": "empirical-measurement(E-SIN-PL-800)",
        "tol": 0.05,
        "anchor": "empirical",
        "empirical_id": "E-SIN-PL-800",
        "default_params": {"w_um": 0.8, "h_um": 0.8, "wl_um": 1.55},
        "golden_fn": None,
        "note": "实证锚：golden=语料实测值 0.087±0.01 dB/cm（8 英寸厚 SiN cut-back，1550nm，光子学报 2024）；比对=|candidate−measured|≤tol。",
    },
    "E7": {
        "title": "SOI 波导 crossing 串扰（实证语料锚）",
        "metric": "crosstalk_dB",
        "oracle": "empirical-measurement(E-SOI-CROSS-XT)",
        "tol": 5.0,
        "anchor": "empirical",
        "empirical_id": "E-SOI-CROSS-XT",
        "default_params": {"w_um": 0.5, "h_um": 0.22, "wl_um": 1.55},
        "golden_fn": None,
        "note": "实证锚：golden=语料实测值 −41±2 dB（CMOS 兼容 crossing 串扰，Zhang PTL 2013）；比对=|candidate−measured|≤tol。",
    },

    # ---- S 系统锚（Phase 0 · Merge-0，2026-08-26）----
    "S1": {
        "title": "系统功率预算余量（dB 级联 · 系统级第一锚）",
        "metric": "margin_dB",
        "oracle": "physical-law(dB-budget-cascade)",
        "tol": 0.01,
        "anchor": "physical_law",
        "default_params": {"p_tx_dbm": 0.0, "n_gratings": 2,
                           "grating_db": -3.0, "wg_length_cm": 1.0,
                           "wg_loss_db_cm": 3.0, "ring_il_db": -0.5,
                           "detector_sens_dbm": -20.0},
        "golden_fn": s1_power_budget_margin_dB,
        "note": "系统锚：激光→光栅×2→波导1cm→环形thru→探测器，margin=0−6−3−0.5+20=10.5dB（纯算术）。"
                "链路引擎端到端输出须与此解析值一致——锚前置剪枝的第一道可行域判决。",
    },

    # ---- S2-S6 系统锚（Merge-2b · Phase 1 锚题库，5 题连发） ----
    "S2": {
        "title": "WDM 信道频率规划无碰撞（系统锚）",
        "metric": "margin_GHz",
        "oracle": "physical-law(channel-plan)",
        "tol": 1e-6,
        "anchor": "physical_law",
        "default_params": {"channel_spacing_ghz": 100.0,
                           "filter_bw_ghz": 50.0},
        "golden_fn": s2_channel_plan_no_collision,
        "note": "系统锚：信道间隔 − 滤波器带宽 > 0 无碰撞（100−50=50GHz 纯算术）。",
    },
    "S3": {
        "title": "OSNR 解析预算（ASE 级联）",
        "metric": "OSNR_dB",
        "oracle": "physical-law(ASE-cascade)",
        "tol": 0.01,
        "anchor": "physical_law",
        "default_params": {"p_sig_dbm": 0.0, "n_amp": 1, "nf_db": 5.0,
                           "bw_ghz": 50.0},
        "golden_fn": s3_osnr_budget,
        "note": "系统锚：OSNR=P_sig−10log(hν·bw·N·F)（ASE 确定性解析，46.93dB 默认）。",
    },
    "S4": {
        "title": "量子门保真度预算（∏fᵢ 乘法级联）",
        "metric": "margin",
        "oracle": "physical-law(fidelity-product)",
        "tol": 1e-6,
        "anchor": "physical_law",
        "default_params": {"fidelities": (0.999, 0.999, 0.999, 0.998, 0.999),
                           "f_target": 0.995},
        "golden_fn": s4_fidelity_budget,
        "note": "系统锚：F_total=∏fᵢ（对数域同构洞察 A）——默认 0.994 略低于 0.995 目标"
                "（margin<0 语义：预算略超，须提保真度或减门数）。",
    },
    "S5": {
        "title": "最坏情况功率预算（工艺角最坏）",
        "metric": "margin_dB",
        "oracle": "physical-law(worst-case)",
        "tol": 1e-6,
        "anchor": "physical_law",
        "default_params": {"p_tx_dbm": 0.0, "il_worst_db": 10.0,
                           "sens_dbm": -20.0},
        "golden_fn": s5_worst_case_budget,
        "note": "系统锚：margin_worst=P_tx−IL_worst−Sens（确定性最坏情况，"
                "与 Merge-1b 角扫下界同构）。",
    },
    "S6": {
        "title": "探测器灵敏度预算（光电流 vs 阈值）",
        "metric": "margin_dB",
        "oracle": "physical-law(detector-margin)",
        "tol": 1e-6,
        "anchor": "physical_law",
        "default_params": {"p_rx_dbm": -8.5, "sens_dbm": -20.0},
        "golden_fn": s6_detector_margin,
        "note": "系统锚：margin=P_rx−Sens（−8.5+20=11.5dB 可探测）。",
    },

    # ---- S7 统计锚（Phase 3 · 专投区 · 蒙特卡洛分布） ----
    "S7": {
        "title": "系统功率预算统计锚（蒙特卡洛分布 · Phase 3）",
        "metric": "margin_mean_dB",
        "oracle": "statistical(monte-carlo, seed-fixed)",
        "tol": 0.15,
        "anchor": "physical_law",
        "default_params": {"n_samples": 2000, "seed": 42},
        "golden_fn": s7_statistical_margin_anchor,
        "note": "统计锚：工艺容差（光栅 0.3dB/波导 0.5dB/cm/环形 0.1dB）高斯扰动下"
                "蒙特卡洛 margin 分布（固定种子 42 可复现）。golden=分布均值≈解析 10.5"
                "（采样噪声 <0.15）；p5=9.41 携带最坏情况下界——确定性锚缺失的维度。"
                "红线：随机在采样、判决在统计量算术，LLM 不进判决路径。",
    },

    # ---- S8 统计锚（Phase 3 · OSNR 统计延伸 · 模板复用验证） ----
    "S8": {
        "title": "OSNR 统计锚（ASE 噪声 + 功率容差 · 蒙特卡洛）",
        "metric": "OSNR_mean_dB",
        "oracle": "statistical(monte-carlo, seed-fixed)",
        "tol": 0.20,
        "anchor": "physical_law",
        "default_params": {"n_samples": 2000, "seed": 7},
        "golden_fn": s8_statistical_osnr_anchor,
        "note": "统计锚：P_sig（激光器 0.5dB 容差）+ NF（放大器 0.3dB 容差）高斯扰动"
                "下 OSNR 分布（固定种子 7 可复现）。golden=均值 46.93≈解析 46.93"
                "（P_sig 线性保持；NF 非线性 Jensen 偏差极小，均值≤解析物理真实）；"
                "p5=45.93 最坏情况。S7 模板直接复用——加题从开发变填表。",
    },

    # ---- S9 LVS 签核锚（Phase 4 · 版图-原理图一致性判决） ----
    "S9": {
        "title": "LVS 版图-原理图一致性签核锚（签核级）",
        "metric": "verdict(ACCEPT=1, REJECT=0)",
        "oracle": "deterministic(LVS-algorithm, geometry+set)",
        "tol": 1e-9,
        "anchor": "physical_law",
        "default_params": {"case": "consistent"},
        "golden_fn": s9_lvs_verdict,
        "note": "系统锚（签核级）：LVS 判决确定性可复现——一致版图 ACCEPT=1.0；"
                "断路/错连/短路/悬空四类失配 REJECT=0.0。版图网表由布线几何独立"
                "恢复（端点→端口锚点归属），比对纯集合运算，判决零 LLM。"
                "正例 case=consistent；反例由 smoke 逐案例断言。",
    },

    # ---- S11 千器件规模锚（Phase 4 · 版图差距 #7 收官） ----
    "S11": {
        "title": "千器件规模扩展锚（链式 + 多层跨行跳线 · 版图差距 #7）",
        "metric": "verdict(ACCEPT=1, REJECT=0)",
        "oracle": "deterministic(scale-pipeline, build+place+route+LVS)",
        "tol": 1e-9,
        "anchor": "physical_law",
        "default_params": {"case": "consistent", "n_devices": 1000},
        "golden_fn": s11_large_scale_verdict,
        "note": "规模锚（收官）：1000 器件链式链路全链路（构建+2D 放置+多层布线+LVS 签核）ACCEPT=1.0——跨行跳线走 M2 层（与 S10 多层协同）；局部破坏（断路/错连）REJECT=0.0。性能预算 5s（bbox 预检后实测 ~0.9s），正确性由 golden 判、性能由预算断。判决零 LLM。",
    },

    # ---- S10 多层 LVS 锚（Phase 4 · 版图差距 #6：金属/通孔层叠） ----
    "S10": {
        "title": "多层 LVS 签核锚（M1/VIA12/M2 层叠 · 版图差距 #6）",
        "metric": "verdict(ACCEPT=1, REJECT=0)",
        "oracle": "deterministic(multilayer-LVS, layer-stack+geometry)",
        "tol": 1e-9,
        "anchor": "physical_law",
        "default_params": {"case": "consistent"},
        "golden_fn": s10_lvs_multilayer_verdict,
        "note": "系统锚（多层签核）：层感知几何恢复——M1 段只接 M1 端口、跨层段"
                "端点重合自动发现 via 桥接；短路判定用层栈 can_cross 谓词（同层"
                "相交才 short、跨层投影重叠安全=介质隔离——多层版图可叠布线的"
                "物理依据）。一致跨层版图 1.0；同层交叉/通孔短路/端口共享/悬空"
                "四类失配 0.0。判决零 LLM。",
    },
    # ---- S12 阵列分布锚（Phase 4 · v0.8.42 · 锚+统计混合判决） ----
    "S12": {
        "title": "阵列分布锚（多实例插损/保真度分布 · 锚+统计混合）",
        "metric": "verdict(ACCEPT=1, REJECT=0)",
        "oracle": "statistical(array-distribution, deterministic)",
        "tol": 1e-9,
        "anchor": "physical_law",
        "default_params": {"kind": "insertion_loss", "seed": 42, "n_instances": 8},
        "golden_fn": s12_array_distribution_verdict,
        "note": "统计锚（阵列分布）：多实例（WDM/CPO 多通道、量子多比特）分布级"
                "判决——均值锚（|mean−golden|≤tol）+ 下界锚（min≥规格下限，抓个别"
                "通道劣化）+ 离群锚（max≤median+margin，防孤立崩坏），三者 AND 才"
                "ACCEPT。单点锚抓不到的『均值好看但某通道崩』盲区由此覆盖。判决纯"
                "算术（statistics），LLM 不进路径；确定性可复现。",
    },
    # ---- S13 设计良率锚（v0.9.1 · DFY · 对标 EDA yield 能力） ----
    "S13": {
        "title": "设计良率锚 DFY（工艺容差→命中规格概率 · 解析↔蒙特卡洛互证）",
        "metric": "yield(0~1)",
        "oracle": "statistical(monte-carlo, seed-fixed) + analytical(gaussian-integral)",
        "tol": 0.01,
        "anchor": "physical_law",
        "default_params": {"fsr_nom_nm": 17.5, "delta": 0.02, "sigma_rel": 0.01,
                           "n_samples": 20000, "seed": 1313},
        "golden_fn": s13_design_yield_anchor,
        # v0.9.18（P0 续）：接入独立候选 —— 解析闭式良率（高斯积分）↔ 蒙特卡洛双算法互证。
        # 注意：S7/S8 的「解析均值」是硬编码常量且对工艺容差 σ 不敏感（均值定理）→
        # 接独立候选必成伪独立（反向扰动信号=MC 涨落恒被 tol 吞没），故 S7/S8 不接；
        # S13 的解析与 MC 是**真正不同方法**（精确积分 vs 采样估计），对 delta/σ 敏感 → 可接。
        "candidate": "yield_analytic",
        "candidate_desc": ("解析闭式良率 Y=Φ((L_hi−L0)/σ_L)−Φ((L_lo−L0)/σ_L)（高斯积分，"
                           "保留 1/L 非线性）↔ 蒙特卡洛双算法互证，与 golden 方法学独立"),
        "note": "设计良率锚（DFY）：环形 FSR 在光刻容差（环周长 σ=±1% 高斯）下命中"
                "±2% 规格窗口的概率。golden=蒙特卡洛固定种子 1313 的仿真良率 0.95475，"
                "并与**解析闭式**交叉验证——FSR=c/L 单调 → 规格窗口逆变换为 L 区间 →"
                "Y=Φ((L_hi−L0)/σ_L)−Φ((L_lo−L0)/σ_L)，精确闭式（保留 1/L 非线性，非一阶"
                "近似）；解析 0.954413 vs MC 0.954750，偏差 0.034pp ≤ tol 1pp。"
                "同一物理定律两种独立算法互证 = 非 AI ground。载体 B4 环形 FSR 定律，"
                "零新物理；判决死标量，LLM 不进路径。"
                "⚠️ v0.9.18 实测订正：接入独立候选 yield_analytic 后，golden(MC 0.954750)"
                " vs candidate(解析 0.954413) 残差 3.37e-4（rel 0.035%，tol 0.01 余量 29.7×）。"
                "反向扰动信号谱：delta×1.1→1.73e-2（51×）✅ · sigma_rel×1.1→2.39e-2（71×）✅"
                " · fsr_nom×1.1→3.37e-4（=baseline，漏抓：yield 对 fsr_nom 免疫因 σ 按比例缩放）"
                " —— 盲区 fsr_nom_nm 已诚实披露，PERTURB 固定扰 delta（最强键）。",
    },
}

# 对齐顺序（报告展示用）
BENCHMARK_ORDER = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10",
                   "B11", "B12", "B13", "B14", "B15", "B16", "B17", "B18",
                   "B19", "B20", "B21", "B22", "B23", "B24", "B25",
                   "B26", "B27", "B28",
                   "E1", "E2", "E3", "E4", "E5", "E6", "E7",
                   "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8",
                   "S9", "S10", "S11", "S12", "S13"]  # S 系统锚（Phase 0-4；S9=LVS/S10=多层/S11=规模/S12=阵列分布/S13=设计良率）


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
