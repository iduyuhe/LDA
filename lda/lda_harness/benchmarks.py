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
}

# 对齐顺序（报告展示用）
BENCHMARK_ORDER = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10",
                   "B11", "B12", "B13"]
