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
    s7_statistical_margin_p5_anchor,
    # S8 统计锚（Phase 3 · OSNR 统计延伸，模板复用）
    s8_statistical_osnr_anchor,
    s8_statistical_osnr_p5_anchor,
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
    # B-4 双方法独立锚（路径 B 扩基续三 · 量子隧穿/一维散射族 · v0.9.84）
    golden_b65, golden_b66, golden_b67, golden_b68, golden_b70, golden_b71,
    golden_b73, golden_b74, golden_b75, golden_b76, golden_b77, golden_b78,
    golden_b79, golden_b80, golden_b81, golden_b82, golden_b83, golden_b84,
    golden_b85, golden_b86, golden_b87, golden_b88,
)
from ._batch_b5_numeric import (  # noqa: E402  # Batch B-5 双方法独立锚数值核（路径 B 扩基续四 · 氢原子径向/3D-HO/圆波导/矩形波导族 · v0.9.85）
    golden_b89, golden_b90, golden_b91, golden_b92, golden_b93, golden_b94,
    golden_b95, golden_b96, golden_b97, golden_b98, golden_b99, golden_b100,
    golden_b101, golden_b102, golden_b103, golden_b104,
)
from ._batch_b6_numeric import (  # noqa: E402  # Batch B-6 双方法独立锚数值核（路径 B 扩基续五 · 刚性转子/2D 方势阱/三角势阱/球形势阱族 · v0.9.86 · 稀释 terminal）
    golden_b105, golden_b106, golden_b107, golden_b108, golden_b109, golden_b110,
    golden_b111, golden_b112, golden_b113, golden_b114,
    golden_b115, golden_b116, golden_b117,
    golden_b118, golden_b119, golden_b120,
)
from ._batch_b7_numeric import (  # noqa: E402  # Batch B-7 双方法独立锚数值核（路径 B 扩基续六 · Morse 势/2D 各向异性谐振子/3D 长方体势阱/类氢激发态族 · v0.9.87 · 腿① 续加锚稀释 terminal）
    golden_b121, golden_b122, golden_b123, golden_b124,
    golden_b125, golden_b126, golden_b127, golden_b128,
    golden_b129, golden_b130, golden_b131, golden_b132,
    golden_b133, golden_b134, golden_b135, golden_b136,
)
from ._batch_b8_numeric import (  # noqa: E402  # Batch B-8 双方法独立锚数值核（路径 B 扩基续七 · 2D 类氢/2D 圆环+AB 通量/3D 有限深球形势阱/各向异性 3D 谐振子族 · v0.9.88 · 腿① 续加锚稀释 terminal）
    golden_b137, golden_b138, golden_b139, golden_b140,
    golden_b141, golden_b142, golden_b143, golden_b144,
    golden_b145, golden_b146, golden_b147, golden_b148,
    golden_b149, golden_b150, golden_b151, golden_b152,
)
from ._batch_b9_numeric import (  # noqa: E402  # Batch B-9 双方法独立锚数值核（路径 B 扩基续八 · 4阶 Euler-Bernoulli 梁/Hulthen 势/Fock-Darwin 量子点/Rosen-Morse II 势族 · v0.9.89 · 腿① 续加锚稀释 terminal）
    golden_b153, golden_b154, golden_b155, golden_b156,
    golden_b157, golden_b158, golden_b159, golden_b160,
    golden_b161, golden_b162, golden_b163, golden_b164,
    golden_b165, golden_b166, golden_b167, golden_b168,
)
from ._batch_b10_numeric import (  # noqa: E402  # Batch B-10 双方法独立锚数值核（路径 B 扩基续九 · Mathieu 周期系数 ODE/椭圆积分与椭球静电/Fresnel 积分/线性扩散热核时间推进族 · v0.9.90 · 腿① 续加锚稀释 terminal）
    golden_b169, golden_b170, golden_b171, golden_b172, golden_b173,
    golden_b174, golden_b175, golden_b176, golden_b177, golden_b178,
    golden_b179, golden_b180, golden_b181, golden_b182, golden_b183,
    golden_b184,
)
from ._batch_b11_numeric import (  # noqa: E402  # Batch B-11 双方法独立锚数值核（路径 B 扩基续十 · 量子统计积分与 ζ 函数/Kepler 中心力轨道 ODE/辐射传热角系数/Voigt 谱线卷积族 · v0.9.91 · 腿① 续加锚稀释 terminal）
    golden_b185, golden_b186, golden_b187, golden_b188, golden_b189,
    golden_b190, golden_b191, golden_b192, golden_b193, golden_b194,
    golden_b195, golden_b196, golden_b197, golden_b198, golden_b199,
    golden_b200,
)
from ._batch_b12_numeric import (  # noqa: E402  # Batch B-12 双方法独立锚数值核（路径 B 扩基续十一 · 正交多项式高斯求积/连分数有理逼近/Durand–Kerner 求根/₂F₁ 超几何 Euler 积分族 · v0.9.92 · 腿① 续加锚稀释 terminal）
    golden_b201, golden_b202, golden_b203, golden_b204, golden_b205,
    golden_b206, golden_b207, golden_b208, golden_b209, golden_b210,
    golden_b211, golden_b212, golden_b213, golden_b214, golden_b215,
    golden_b216,
)
from ._batch_b13_numeric import (  # noqa: E402  # Batch B-13 双方法独立锚数值核（路径 B 扩基续十二 · 分数阶 Grünwald–Letnikov/矩阵指数 scaling–squaring/变分极值梯度下降/第二类 Volterra 积分方程族 · v0.9.93 · 腿① 续加锚稀释 terminal）
    golden_b217, golden_b218, golden_b219, golden_b220, golden_b221,
    golden_b222, golden_b223, golden_b224, golden_b225, golden_b226,
    golden_b227, golden_b228, golden_b229, golden_b230, golden_b231,
    golden_b232,
)
from ._batch_b14_numeric import (  # noqa: E402  # Batch B-14 双方法独立锚数值核（路径 B 扩基续十三 · 定常对流–扩散中心差分/第二类 Fredholm 可分核 Nyström/自然三次样条逼近/非线性两点边值打靶法族 · v0.9.94 · 腿① 续加锚稀释 terminal）
    golden_b233, golden_b234, golden_b235, golden_b236, golden_b237,
    golden_b238, golden_b239, golden_b240, golden_b241, golden_b242,
    golden_b243, golden_b244, golden_b245, golden_b246, golden_b247,
    golden_b248,
)

from ._batch_b15_numeric import (  # noqa: E402  # Batch B-15 双方法独立锚数值核（路径 B 扩基续十四 · 延迟泛函微分方程分步法/双调和薄板 13 点差分/一维输运半拉格朗日特征线/聚焦 NLSE 孤子分裂步 Fourier · v0.9.95 · 腿① 续加锚稀释 terminal）
    golden_b249, golden_b250, golden_b251, golden_b252, golden_b253,
    golden_b254, golden_b255, golden_b256, golden_b257, golden_b258,
    golden_b259, golden_b260, golden_b261, golden_b262, golden_b263,
    golden_b264,
)

from ._batch_b16_numeric import (  # noqa: E402  # Batch B-16 双方法独立锚数值核（路径 B 扩基续十五 · Burgers 方程 tanh 行波 RK4+中心差分/广义指数积分 E_n(x) 截断复合 Simpson/Haar 小波多分辨投影逐层低通 · v0.9.96 · 腿① 续加锚稀释 terminal）
    golden_b265, golden_b266, golden_b267, golden_b268, golden_b269,
    golden_b270, golden_b271, golden_b272, golden_b273, golden_b274,
    golden_b275, golden_b276, golden_b277, golden_b278, golden_b279,
    golden_b280,
)
from .b28_modulator_vpi_anchor import (  # noqa: E402  # B28 MZM Vπ 锚（v0.9.1 · 钉子 D1b=A）
    b28_modulator_vpi, b28_modulator_vpi_report,
)
from .b29_thermal_phase_anchor import (  # noqa: E402  # B29 热光相移效率锚（v0.9.39 · T-9 接线）
    b29_thermal_phase_efficiency, b29_thermal_phase_report,
)
from .b30_readout_anchor import (  # noqa: E402  # B30 读出保真度锚（v0.9.39 · T-9 接线）
    b30_readout_fidelity, b30_readout_report,
)
from .b33_detector_bandwidth_anchor import (  # noqa: E402  # B33 探测器 RC 带宽锚（v0.9.67 · A 档有源）
    b33_detector_bandwidth, b33_detector_bandwidth_report,
)
from .b31_soref_bennett_anchor import (  # noqa: E402  # B31 Si 载流子色散相移锚（v0.9.69 · T1-C W3）
    b31_soref_bennett_phase_shift, b31_phase_shift_report,
)
from .b32_qcse_anchor import (  # noqa: E402  # B32 EAM-QCSE 吸收边位移锚（v0.9.69 · T1-C W4）
    b32_qcse_edge_shift_meV, b32_qcse_report,
)
from ._batch_b_numeric import (  # noqa: E402  # Batch B-1 双方法独立锚数值核（v0.9.79 · 路径 B 扩基）
    golden_b34, golden_b36, golden_b37, golden_b40, golden_b41,
)
from ._batch_b2_numeric import (  # noqa: E402  # Batch B-2 双方法独立锚数值核（v0.9.79+ · 路径 B 扩基续）
    golden_b42, golden_b43, golden_b44, golden_b45, golden_b46, golden_b47,
    golden_b48, golden_b49, golden_b50, golden_b51,
)
from ._batch_b3_numeric import (  # noqa: E402  # Batch B-3 双方法独立锚数值核（v0.9.79++ · 路径 B 扩基续二）
    golden_b52, golden_b53, golden_b54, golden_b55, golden_b56, golden_b57,
    golden_b58, golden_b59, golden_b60, golden_b61, golden_b62, golden_b63, golden_b64,
)

BENCHMARK_DEFS = {
    "B1": {
        "title": "米氏散射远场散射效率 Q_scat",
        "metric": "Q_scat",
        "oracle": "analytical(Rayleigh-limit)",
        "tol": 2e-4,
        "default_params": {"m": 1.33, "x": 0.4},
        "golden_fn": b1_mie_qscat,
        # v0.9.21（P0 续）：接独立候选 —— 完整 Mie 级数 ↔ Rayleigh 一阶极限。
        # 🔴 use_miepython 钉死 False：否则装有 miepython 的环境 golden 会切
        # 完整 Mie（ORACLE）⇒ golden 环境相关、判决不可复现。
        "candidate": "mie_exact",
        "candidate_desc": ("完整 Mie 级数（B&H 4.53 全多极子求和，纯 numpy"
                           "递推）↔ Rayleigh 一阶极限（仅 a₁ 首项），方法学独立"),
        "note": "Rayleigh 极限 Q=(8/3)x⁴r²（x≪1 与完整 Mie 一致，误差 O(x²)："
                "实测 -0.001%@x=0.01 → 1.388%@x=0.4）。【v0.9.21 P0 续】候选="
                "自写完整 Mie 级数（lda_solver/mie_solver.py，递推经 scipy 交叉"
                "验证 ≤3e-8）；baseline 3.945e-5（tol=2e-4 未动余量 5.1×）；"
                "反向 m×1.1 信号 2.357e-3（11.9×）、x×1.1 信号 1.246e-3（6.2×）。"
                "miepython 可用时仍可作显式外部 ORACLE（判决路径不依赖）。",
    },
    "B2": {
        "title": "SOI 条形波导有效折射率 n_eff",
        "metric": "n_eff",
        "oracle": "analytical(EIM)",
        "tol": 0.05,
        "default_params": {"w_core": 0.5, "h_core": 0.22, "n_si": 3.48,
                            "n_clad": 1.44, "wl": 1.55},
        "golden_fn": b2_soi_waveguide_neff,
        "candidate": "b2_fvfdm_neff",
        "candidate_desc": ("全矢量有限差分 FV-FDM（纯 numpy/scipy）独立求解 SOI strip 波导 TE 基模 n_eff"
                           "—— 与 EIM 降维闭式方法学独立；三智能体终审（FV-FDM 2.644 + PWE 2.614）"
                           "均在 tol=0.05 内复现 golden，判据 C5 成立，v0.9.66 升 Tier-3 严格独立"),
        "note": "两步有效折射率法（EIM）解析近似；v0.9.66 已接 FV-FDM 独立候选升严格独立（三智能体终审）。文献锚点 ~2.4–2.6。",
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
        "candidate": "taper_eme",
        "candidate_desc": ("本征模展开（EME）：锥度逐切片解完整横向 Helmholtz "
                           "本征问题 + 模式重叠矩阵前向级联 ⇒ 末片基模功率占比"),
        "note": ("黄金=绝热极限 T→1（物理定律上界）；核查候选求解器能否达 ≥99% 效率。"
                 "【v0.9.26 接线完成】候选=taper_eme（EME 逐片解 Helmholtz，无旁轴"
                 "假设；实测 T=0.999953，1−T=4.65e-5），此前为 ReferenceCandidate "
                 "自证桩。"
                 "🔴 四条诚实边界（均已实测）：①**判据余量仅 4.65e-5**（占 tol 1e-2 "
                 "的 0.47%），本锚只回答「是否进入绝热极限」，不回答精度；"
                 "②**0.2→0.5µm 几何的损耗上限仅 ~1.5%**（突变结模式重叠 0.9853）"
                 "⇒ **单独扰动 L 无法击穿 tol**（L 缩到 0.2µm 也只到 0.993），"
                 "反向测试改用 w2=3.0/L=1.0µm（T≈0.435）；③**短锥度区 L≲2µm 未收敛**"
                 "（箱模谱欠采样，窗口 8/16/32 相差 4e-3，且 EME 值 0.993 高于突变"
                 "结下界 0.9853），已收敛区 L≥5µm 窗口 16→32 只差 1.4e-5 ⇒ 单调性"
                 "自校锚只取 L≥5；④**EIM 降维 + 单向近似**——垂向压成常数 n_eff，"
                 "不含垂向辐射与极化耦合，且只算前向模式不算背向反射（反射只会降低 "
                 "T，对上界 golden 不会虚高）。"),
    },
    "B5": {
        "title": "Y 分支(1×2) 分束插入损耗",
        "metric": "split_loss_dB",
        "oracle": "design-rule(Meep/Tidy3D field 预留)",
        "tol": 1.0,
        "default_params": {"w_core": 0.5, "h_core": 0.22, "n_si": 3.48,
                           "n_clad": 1.44, "wl": 1.55, "theta_deg": 10.0},
        "golden_fn": b5_ybranch_split_loss_dB,
        "candidate": "ybranch_eme",
        "candidate_desc": ("Y 分支双芯超模 EME（EIM 降维 + 逐片完整 Helmholtz 本征解 "
                           "+ 模式重叠矩阵级联）—— 与 golden 唯象拟合式方法学不同源"),
        "note": "黄金=离线场级重叠估计（numpy-overlap-offline，默认 theta=10° 得 3.4 dB；设计守则下限 3.0 dB）；精确真值待 Meep/Tidy3D 场级 ORACLE。"
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
        "candidate": "grating_fp",
        "candidate_desc": ("光栅峰值效率首原理四因子分解 η_dir(辐射对称=1/2) × "
                           "η_ov(高斯⊗指数模场重叠 0.785) × F(ff)=sin(π·ff) × "
                           "M(光栅方程相位匹配) —— 与常数 golden / E8 引擎模型均不同源"),
        "note": "黄金=成熟工艺可达效率 0.5(≈-3dB)（**design-anchor 回退值**：Tidy3D key 缺失时实际返回值）；精确真值待 Tidy3D 场级 ORACLE。",
    },
    "B7": {
        "title": "波导交叉串扰",
        "metric": "crosstalk_dB",
        "oracle": "design-rule(+Meep field 预留)",
        "tol": 5.0,
        "default_params": {"w_core": 0.5, "h_core": 0.22, "n_si": 3.48,
                           "n_clad": 1.44, "wl": 1.55, "gap": 0.2},
        "golden_fn": b7_crossing_crosstalk_dB,
        "candidate": "crossing_cmt",
        "candidate_desc": ("双芯超模/CMT 本征解：gap 相隔双芯横向剖面 Helmholtz "
                           "本征解给 even/odd 超模折射率 ⇒ κ=π|n_e−n_o|/λ ⇒ "
                           "串扰=sin²(κ·L_eff)。与 golden(守则锚) 及已撤出的 "
                           "2D FDTD 均方法学不同源，不读 golden、无标定系数"),
        "note": ("黄金=设计守则锚 −40 dB（**有独立实证背书**：语料 E-SOI-CROSS-XT "
                 "同几何实测 −41±2 dB，Zhang 2013 PTL 25(13):1225，"
                 "DOI 10.1109/LPT.2013.2241049）。🔒 v0.9.82 golden 语义订正：原先"
                 "覆盖 golden 的『离线 numpy 2D FDTD』于同版本**撤出调度**——该 2D "
                 "降维（裸十字）与其锚定器件（taper 优化交叉）相差 20~30 dB，且源"
                 "位置深扫 ±3 dB 无收敛趋势，作 golden 会把「模型-器件不匹配」伪装"
                 "成锚真值；修复后的 2D 核保留为**机理诊断量**（默认 −14.43 dB，"
                 "seg_drift 2.5e-4）。候选 crossing_cmt 给 −35.36 dB ⇒ |diff|=4.64 "
                 "< tol 5.0 升 Tier-3（**残差占窗口 93%，属边缘通过**）。彻底闭合需 "
                 "3D 全波 + 真实 taper 版图（T2 级缺口），见 "
                 "`P1-1_B7_golden_fix_report.md`。"),
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
        "oracle": "analytical(lindblad-closed-form)",
        # v0.9.24（P0 续 · D-66 第 8 例 + 接线）：
        #  ① **golden 语义修正**：旧式 F=exp(−t(1/T1+1/(2T2))) 不对应任何标准
        #     保真度定义（一阶系数是严格解的 2.727×，比值 30/11 无物理来源），
        #     与严格解差 2.638e-4 > 任何 10% 扰动信号 ⇒ 判据窗口不可能成立。
        #     改为 Lindblad 严格闭式 F=(3+2e^(−t/T2)+e^(−t/T1))/6（RB 可对标）。
        #  ② **tol 0.01 → 1e-8（收紧 1e6 倍）**：0.01 允许 F 掉到 0.99，比真实
        #     门误差 1.53e-4 大 65 倍 ⇒ 六路 10% 扰动信号（1.5e-5~4.2e-5）全部
        #     抓不住，该锚实际零判别力。收紧后判据窗口成立：
        #       baseline 1.11e-16  <  tol 1e-8  <  min(信号) 3.787e-6（T1+10%）
        #     余量：下界 9e7×，上界 379×。
        #  ③ 接入独立候选 lindblad_gate_f（数值积分 vs 解析闭式）。
        "tol": 1e-8,
        "default_params": {"T1": 80.0, "T2": 60.0, "t_gate": 0.02},
        "golden_fn": b10_gate_fidelity,
        "candidate": "lindblad_gate_f",
        "candidate_desc": ("Lindblad 4×4 超算子 RK4 数值积分 → 完整 PTM → 平均门保真度"
                           "—— 与 golden 的 Lindblad 解析闭式方法学独立"),
        "note": "F=(3+2e^(−t/T2)+e^(−t/T1))/6（µs）；物理上限锚，对应光子侧 B8 绝热极限。"
                "更精细 RB/XEB(Qiskit)仅作外部 ORACLE。"
                "【v0.9.24】golden 语义修正（D-66 第 8 例）：旧式 "
                "F=exp(−t(1/T1+1/(2T2))) 一阶系数是严格解的 2.727×（比值 30/11，"
                "无物理来源），与严格解差 2.638e-4；而全部 10% 扰动信号仅 "
                "1.5e-5~4.2e-5 ⇒ 旧 golden 下判据窗口不可能成立，tol 只能取 0.01 "
                "（真实门误差 1.53e-4 的 65 倍），该锚零判别力。现 golden 改为 "
                "T=0 Lindblad（γ₁·D[σ₋]+γ_φ·D[σ_z]）的严格平均门保真度闭式。"
                "【v0.9.24】tol 收紧 1e6 倍至 1e-8，判据窗口实测成立："
                "baseline 1.11e-16 < 1e-8 < min 信号 3.787e-6。"
                "🔴 **诚实边界一**：生产档位 |L|·t≈2.5e-4 ⇒ RK4 残差恒为 1.11e-16 "
                "且与步数 N 无关（N=5..400 实测）⇒ **残差不可标定**，与自证桩的 "
                "|Δ|≡0 数值上无法区分。「候选真在工作」由三条**可标定**自校锚"
                "证明（PTM 非对角元 Λ_Z,I≈−2.5e-4 逐元素比对 / 敏感 regime t=200µs "
                "残差 5.6e-9 且 N 加倍降 16.3× 呈 O(h⁴) / t→∞ 稳态 F→0.5），"
                "外加 harness 反向扰动测试。"
                "🔴 **诚实边界二**：T=0 热库假设（未含 n_th 热激发）；H=0 idle 门"
                "口径（未含脉冲形状误差/泄漏/串扰）⇒ 是退相干极限上界，不含控制误差。"
                "🔴 **诚实边界三**：T2 > 2·T1 属非物理输入（γ_φ<0），golden 与候选"
                "均抛 ValueError，不静默 clamp。",
    },
    "B11": {
        "title": "环形谐振器 drop 端口透射谱 · 目标谱形 L2 匹配",
        "metric": "spectrum_match",
        "oracle": "analytical(ring-transfer-function)",
        "tol": 0.03,
        # v0.9.68（P1①）：接入独立候选 —— 数值扫 add-drop 环 drop 口传递函数、
        # 定峰后对 1/λ 做等距拟合（频域周期 Δu=1/(n_g·2πR)），换算 FSR_λ=λ0²·Δu，
        # 再算 |FSR−target|/target 与 golden 同一标量（B4 同族谱拟合法，方法学独立）。
        "candidate": "ring_fsr_peakfit_b11",
        "candidate_desc": ("数值 add-drop 环传递函数（drop 口）峰周期拟合 FSR"
                           "—— 与 golden 闭式 FSR 方法学独立，同一标量"),
        "default_params": {"R": 10.0, "n_g": 4.2},
        "golden_fn": b11_ring_spectrum_match,
        "note": "误差=计算谱与目标洛伦兹梳谱形的逐波长 L2 距离；调 R 命中目标 FSR "
                "即匹配谱形。确定性物理定律（环形传递函数）。逆设计'目标谱形'基准。"
                "⚠️ 独立候选已接（v0.9.68）：数值峰周期拟合法与闭式 FSR 方法学独立，"
                "基线残差 ~1e-9 << tol=0.03，余量 >>1000×，判据 D 不触发假独立。",
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
        "oracle": "analytical(coupled-mode)",
        "tol": 0.25,
        "default_params": {"n_e": 2.45, "n_o": 2.40, "wl": 1.55},
        "golden_fn": b14_dc_coupling_length,
        # v0.9.20：①golden 语义修正（λ/(2Δn)=完全转移长度 → λ/(4Δn)=真 3dB 点）
        #         ②接独立候选：FFT 拍频谱峰 ↔ 解析闭式反解。
        "candidate": "dc_cmt_fft",
        "candidate_desc": ("数值传播序列 + FFT 拍频谱峰（B3/B4/B20 同款频域周期"
                           "提取方法学）↔ 耦合模解析闭式反解，方法学独立"),
        "note": "耦合模理论 P2(z)=sin²(κz)，κ=π|Δn|/λ。🔴 v0.9.20 语义修正"
                "（D-66「怀疑 golden 本身」第 4 例）：原式 λ/(2|Δn|) 是完全转移"
                "长度（P2=1.0，RK4 实证 sin²(π/2)=1），被错标为 3dB 点；真 3dB "
                "点=λ/(4|Δn|)（P2=sin²(π/4)=0.5）。golden 15.5→7.75，tol 0.5→"
                "0.25（同比 3.2% 重定）。同源消费点 _dc_supermode_core（相位校验"
                "Δβ·L=π 本就是完全转移点）一并修正为 Δβ·L=π/2。candidate=FFT "
                "拍频谱峰（dz=0.01/nP=8，baseline 1.56e-4 余量 1560×）；反向 "
                "n_e×1.1 信号 6.44（25.8×）。",
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
        "reuse_aliases": ["B35 (DBR/DFB 激光光栅布拉格波长 · 复用本锚)"],
        # 🔴 v0.9.73：机器可读的「复用携带候选」声明（此前只有人类可读的 reuse_aliases，
        # 而 BENCHMARK_CANDIDATES 里登记的 b35_reuse_b15 无人引用 ⇒ 可证伪性护栏的
        # 「已登记候选类型与实测独立锚一致（无登记未接线）」判 FAIL，自 v0.9.67/68
        # 起 CI core 一直红而未察觉）。B35 非独立锚（复用 B15）、其候选仅作委托记录，
        # 故以本字段显式豁免；真「登记了却没人用」的孤儿候选仍会被抓（见 fdfd_ng 先例）。
        "reuse_alias_candidates": ["b35_reuse_b15"],
        "reuse_note": ("B35 复用本锚（T1-C 评审 2026-09-12 裁决：零新锚、不重复投入、"
                       "不计入独立锚计数）。物理对象完全同一（λ_B=2·n_eff·Λ），仅应用场景"
                       "从被动 Bragg 反射镜变主动激光器腔镜（DBR/DFB）。B35 的 golden/candidate"
                       "委托 B15，守护由 run_bragg_gds_smoke.py 覆盖，判据 D 框架复用本锚候选。"),
    },
    "B16": {
        "title": "MMI 1×2 自映像长度",
        "metric": "L_mmi_um",
        "oracle": "design-rule(general-interference)",
        "tol": 3.0,
        "default_params": {"W_e": 2.0, "n_eff": 2.4, "wl": 1.55},
        "golden_fn": b16_mmi_length,
        "candidate": "rib_mmi_recon",
        "candidate_desc": ("脊形 MMI 全场模态重构：反演 core 折射率(平板基模≡器件 n_eff，对象一致) "
                           "+ 精确解 TE 平板本征方程 + 输入场按全部导模展开沿 z 精确传播 "
                           "+ 双度量联合定位 1×2 首像（不套 (9/8) 成像因子）"),
        "note": ("【v0.9.62·修正·诚实边界】历史 golden 因子 3（=3·n_eff·W²/λ）系统性高估 "
                 "33–55%（W=2.8µm 真实器件实测 ~27µm，旧 golden 给 ~36µm）。已修正为 "
                 "标准 MMI 自成像 1×2 第一双像长度 L=(9/4)·n_eff·W²/λ=(9/8)·L_π^wg "
                 "（L_π^wg=2·n_eff·W²/λ）；W=2.8/n_eff=2.4→27.3µm≈实测 27µm（<1%）。"
                 "🔴 **v0.9.80 前为自证桩**：repo `mmi_eme` 求解核建模的是「对称平板 "
                 "波导」（slab），而真实器件是「脊形(rib) MMI」——建模对象不同 ⇒ 其 EME "
                 "解（~24µm @W=2.8）与抛物线闭式 golden（27µm）差 ~13%，且在器件宽度处 "
                 "diff> tol 3.0µm，余量仅 ~1.3×。"
                 "【v0.9.80·2026-09-16 P1-1 B16 重审·升严格独立】对象一致性修正后实现 "
                 "rib-MMI 全场模态重构候选 `rib_mmi_recon`：① 由器件给定的基模有效折射率 "
                 "n_eff 反演对称平板 core 折射率 ⇒ 平板基模 ≡ 器件 MMI 基模（建模同一物理 "
                 "对象，正面修正 mmi_eme 的 slab≠rib 错配）；② 精确解 tan/cot 本征方程得"
                 "全部导模（非抛物线截断）；③ 输入场按全部导模展开、沿 z 精确传播，用"
                 "「双像重叠 ov + 双瓣对比 M=min(I(±a/2))/I(0)」联合判据定位首个 1×2 双像"
                 "（**不套用任何 (9/8)/(3) 成像因子**）。与 golden 抛物线闭式方法学独立，"
                 "残差 = 抛物线近似 + 有限模集的固有误差（有界、物理、非零 ⇒ 非假绿）。"
                 "实测 |cand−golden|：W=2.0→0.26µm、2.4→0.25、2.8→0.54、3.2→0.92、3.6→1.48、"
                 "4.0→2.21（全 < tol 3.0µm，覆盖 2.0–4.0µm 全宽度域）；n_eff/λ 变体亦 <1µm。"
                 "数值复核 golden(2.8,2.4,1.55)=27.314µm≈实测27µm 不变。"),
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
        "candidate": "link_passivity",
        "candidate_desc": ("lda_chain 引擎端到端级联（构建→布局→自动布线→带布线"
                           "损耗→传递谱）在全部路径×全部采样波长上的 max|T|"),
        "note": ("链路级第一道非 AI ground：无源网络无增益上界 1.0（损耗合法、"
                 "增益判 FAIL）；能量守恒为无损特例。由 lda_chain 引擎级联输出与"
                 "黄金上界死标量比对，LLM 不进判决路径。"
                 "【v0.9.25 接线完成】候选=link_passivity（lda_chain 真跑全链路，"
                 "网格窗口 ±100nm / 步长 0.01nm，实测 max|T|≈0.9998962），"
                 "此前为 ReferenceCandidate 自证桩。"
                 "🔴 三条诚实边界（均已实测）：①判据余量仅 ~1.04e-4，缺口几乎全部"
                 "来自环弯曲损耗，损耗模型若关闭则 max|T|→1.0 顶到边界；②max|T| "
                 "随网格**非单调**（采样是否命中窄峰尖），粗网格会低估 ⇒ 步长固定"
                 "0.01nm（step≤0.01 后稳定到 1e-12）；若 >1 的尖峰落在采样点之间"
                 "仍会漏检，加细只缓解不根除；③alpha_cm 被消费但对**本指标**无影响"
                 "—— 全局 max 落在 ring0.drop（不经任何 bus），三档 alpha 下恒为"
                 "0.9995947013 ⇒ 候选对 alpha_cm 零响应，判据靠 gap_um/n_g 成立。"
                 "④本锚只判合法性（有无增益），不判级联精度。"),
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
        # v0.9.78（用户授权「B 路径」）：诚实升 degraded_ordinal。
        # 候选 = 自研 2D FDTD 全波（b21_phc_fdtd，C 级自主、不借 Meep/Tidy3D）；
        # tol=66.0nm = 3%×golden(2214nm) 绝对带（harness 仅 abs 判据，无 rel 模式）。
        # 默认参数 λ_fdtd=2214.87nm vs golden 2214.0nm，rel=0.039%（余量 ~77×，
        # 低于严格 100× 故保守归 degraded，不进死标量判决列）。
        "tol": 66.0,
        "default_params": {"L_cav_um": 0.45, "n_core": 3.48, "n_clad": 1.44},
        "golden_fn": b21_phc_resonance,
        "candidate": "b21_phc_fdtd",
        "candidate_status": "degraded_ordinal",
        "note": ("2D 光子晶体腔 = 均匀高折射率波导腔（L_cav，n_eff=(n_core+n_clad)/2）"
                 "两端夹持 quarter-wave 布拉格镜（n_core/n_clad 交替）；腔共振"
                 "λ_res=(n_core+n_clad)·L_cav（FP/布拉格带边一阶近似）。"
                 "🔴 升级：自研 2D FDTD 全波求解（fdtd2d_dbr_cavity.py，纯 numpy）作方法学"
                 "独立候选，6 点参数扫描实证实残差 0.04%–8.06% 随几何变化（判据 D 满足，"
                 "非伪绿）；默认 rel=0.039% 极准，但保守标 degraded_ordinal（用户授权 B 路径"
                 "+ 严格余量 100× 未达 + 跨域偏差主成分系模型近似粗糙度）。"
                 "确定性物理定律锚，LLM 不进判决路径。"),
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
        # v0.9.28（T-2）：接入独立候选 mzm_vpi_nullfit —— 传输谱 T(V)=cos²(Δφ)
        # 数值采样 + 首个零点三点抛物线定顶（= 实验 Measure Vπ 流程数值化）。
        # 🔴 判据 D 实测（T-1 单一定义处）：残差 1.91e-3→2.34e-8 随 n_voltage
        # 真实收敛 ⇒ 真数值离散化。**同锚旧候选沿程积分（mzm_vpi_integral）
        # 是判据 D 的反例**：均匀段剖分守恒 ⇒ 与闭式代数恒等（残差恒
        # 4.44e-16、扰动同步响应）⇒ 沿程积分仅保留为报告侧交叉验证，
        # 不作 harness 独立候选（虚报）。
        "candidate": "mzm_vpi_nullfit",
        "candidate_desc": "数值零点拟合：传输谱采样 + 抛物线定顶（与解析反解方法学独立）",
        "default_params": {"lambda_vac_um": 1.55, "n_eff": 2.2,
                           "r_eff": 30.8e-12, "gamma": 0.5,
                           "L_um": 10000.0, "d_um": 8.0},
        "golden_fn": b28_modulator_vpi,
        "note": ("MZM 半波电压 Vπ=λ₀·d/(2·n_eff³·r_eff·Γ·L)（推挽 Pockels 电光"
                 "相位调制确定性物理定律，零模型假设）。golden=解析闭式。"
                 "v0.9.28 独立候选=数值零点拟合（`lda_solver/mzm_vpi_nullfit.py`）："
                 "按 Pockels 相位链算 T(V) 谱、采样找首个传输零点、三点抛物线"
                 "定顶——与 B3/B4/B20「数值谱特征拟合 vs 解析闭式」同族已判定"
                 "独立模式。基线残差 7.6e-9 V（tol 1e-3 的 0.0008%）；判据 D："
                 "n_voltage 2→512 残差 1.91e-3→2.34e-8 真实收敛。"
                 "旧 ORACLE 沿程积分+二分（通用 Γ(z)）保留于报告侧：均匀段与"
                 "闭式代数恒等（剖分守恒，判据 D 反例），仅作实现自洽检查，"
                 "**不构成独立验证**。实证量级（LiNbO3 x-cut MZM Vπ≈3.8V）仅作 "
                 "honest-sanity，不进死标量判决。与 B20 无源 MZI-FSR 双锚闭合"
                 "「MZI 无源+有源」。LLM 不进判决路径。"),
    },
    # ---- B29 / B30（v0.9.39 · T-9 锚题覆盖矩阵暴露的接线空白点）----
    "B29": {
        "title": "热光相移效率（热光系数 dn/dT · 1D 散热鳍 PDE 相移）",
        "metric": "phase_efficiency_deg_per_mW",
        "oracle": "analytical(1D fin PDE closed-form) + FDM cross-check",
        "tol": 2e-2,
        # v0.9.39（T-9 接线 #1）：D-73 升格为严格独立锚。golden = 1D 散热鳍
        # 稳态 PDE 闭式（cosh 解析积分）；candidate = 同 PDE 三对角 FDM + 梯形
        # 积分（不反解闭式）。判据 D 实测：N=50→6400 残差 0.45°→3.4e-3°
        # 单调收敛（O(1/N)，边界引线匹配斜率间断，一阶合理）= 真数值离散化。
        "candidate": "thermal_phase_fdm",
        "candidate_desc": "1D 散热鳍 FDM 求解 + 梯形相位积分（与闭式方法学独立）",
        "default_params": {"lambda_um": 1.55, "dn_dt": 1.86e-4, "h_p": 1.0,
                           "healing_length_um": 100.0, "L_um": 1000.0,
                           "P_mw": 1.0},
        "golden_fn": b29_thermal_phase_efficiency,
        "note": ("热光相移器在 P=1mW 下的相移效率（度/毫瓦）：Δφ=2π/λ·(dn/dT)·∫θ(z)dz，"
                 "θ(z) 由 1D 散热鳍方程控制（对称加热器 + 两端衰减引线）。golden=确定性"
                 "物理定律闭式（cosh 解析积分）。v0.9.39 独立候选=thermal_phase_fdm：同 PDE"
                 "三对角 FDM（Thomas）+ 梯形积分——与 golden 是同一物理定律的两种算法"
                 "（解析 vs 离散），判据 D 真数值收敛。基线残差（N=8000）≈2.7e-3°"
                 "（tol 2e-2 的 0.013%，≫1e-12 噪声地板，双向可标定）。归一化鳍模型"
                 "（h_p=1.0 W/K, healing=100µm）绝对温标为示意、非 PDK 声明（θ_avg≈0.9K）。"
                 "反向 dn_dt±10% ⇒ Δ=3.8°≫tol 必 FAIL。LLM 不进判决路径。"),
    },
    "B30": {
        "title": "读出保真度 F（色散读出 SNR → erfc 误判链 · Krantz 2019）",
        "metric": "readout_fidelity_F",
        "oracle": "analytical(erfc readout chain) + gaussian-overlap quad cross-check",
        "tol": 1e-3,
        # v0.9.39（T-9 接线 #2）：readout_fidelity 零覆盖锚升格为严格独立锚。
        # golden = ε=½erfc(SNR/√2) 闭式链；candidate = 误判概率 ε 的高斯重叠
        # 数值积分（两高斯均值 ±SNR、σ=1 ⇒ 重叠积分=erfc(SNR/√2)=2ε）。
        # 判据 D 实测：nx=2001→2e6 残差 9.4e-7→8e-13 单调收敛（真数值离散化，
        # 非代数恒等）。🔴 工作点取中等 SNR≈2.2（ε≈1.4e-2）而非 t_m* 饱和区
        # （ε≈4e-5）——饱和区 ±10% 扰动在 tol 内不可见，反向测试失敏。
        "candidate": "readout_fidelity_quad",
        "candidate_desc": "误判概率 ε 的高斯重叠数值积分（与 erfc 闭式方法学独立）",
        "default_params": {"chi_ghz": 0.05, "kappa_r_ghz": 0.005, "nbar": 2.0,
                           "eta": 0.5, "N_amp": 5.0,
                           "t_m_s": 4.236705e-9, "T1_s": 20e-6},
        "golden_fn": b30_readout_fidelity,
        "note": ("色散读出单发保真度 F=(1-ε+(1-ε)(1-t_m/T1))/2，ε=½erfc(SNR/√2)，"
                 "SNR=2χ_rad√(n̄ηt_m/(κ_rad(1+2N_amp)))（Krantz 2019）。golden=确定性"
                 "物理定律闭式。v0.9.39 独立候选=readout_fidelity_quad：ε 的高斯重叠"
                 "数值积分（erfc 闭式 vs 梯形积分，方法学独立），判据 D 真收敛。默认"
                 "工作点 SNR≈2.2、ε≈1.4e-2（固定 t_m_s 反解，非饱和 t_m*）保证反向"
                 "判别力：nbar/eta/N_amp±10% ⇒ ΔF≈3.4e-3≫tol 1e-3 必 FAIL。与 B10 门"
                 "保真度（Lindblad 数值 vs 闭式）同族「数值积分 ↔ 解析」独立模式。"
                 "LLM 不进判决路径。"),
    },
    # ---- B33（v0.9.67 · A 档有源扩展 #1）：探测器 RC 限制 3dB 带宽 ----
    "B33": {
        "title": "探测器 3dB 带宽（RC 限制 · 电路闭式）",
        "metric": "f3dB_Hz",
        "oracle": "analytical(RC bandwidth closed-form) + timestep-ODE-fit cross-check",
        "tol": 4e3,
        # v0.9.67（A 档有源开放后第一道真·新增严格独立锚）：golden = 反偏结
        # 电容 C=ε·A/d 的 RC 低通 3dB 带宽闭式 f_3dB=1/(2π·R·C)；candidate =
        # RC 一阶暂态 V(t)=V0(1−e^{−t/τ}) 梯形法数值积分 + 最小二乘拟合 τ
        # （与解析闭式方法学独立，判据 D 真数值收敛，n_time 2→512 残差单调下降）。
        # 纯电路闭式 + 数值积分，无光子有源物理 / 无载流子动力学 / 无 TCAD /
        # 无 A 级工具 ⇒ 不破三不做 / 主权 / 验证纪律任何红线（A 档授权依据见
        # docs/lda_active_device_redline_clarification_2026-09-10.md §七裁定①）。
        "candidate": "rc_bandwidth_timestep",
        "candidate_desc": ("RC 暂态梯形法数值积分 + 最小二乘拟合 τ（与解析闭式 "
                           "1/(2π·R·C) 方法学独立）—— 判据 D 真数值收敛"),
        "default_params": {"R": 50.0, "eps": 1.036e-10, "A": 9.653e-9, "d": 1.0e-6},
        "golden_fn": b33_detector_bandwidth,
        "note": ("pin/APD 探测器 RC 限制 3dB 带宽 f_3dB=1/(2π·R·C)，C=ε·A/d"
                 "（反偏结电容闭式，ε=1.036e-10 F/m ≈ Si ε_r·ε0）。默认 R=50Ω、"
                 "C≈1pF ⇒ f_3dB≈3.18 GHz（典型 pin 量级）。golden=确定性物理"
                 "定律闭式。v0.9.67 独立候选=rc_bandwidth_timestep：模拟 RC 一阶"
                 "暂态（梯形法数值积分）+ 拟合 τ ⇒ 1/(2π·τ)——与 golden 是同一"
                 "物理定律的两种算法（数值 ODE 拟合 vs 解析公式），判据 D 真数值"
                 "收敛（n_time 4→512 残差 5.5e8→2.5e4 Hz 单调下降）。基线残差"
                 "1.66e3 Hz（tol=4e3 的 ~2.4× 余量，≫1e-12 噪声地板）。反向 "
                 "R±10% ⇒ f_3dB∝1/R 信号 ~2.9e8 Hz ≫ tol 必 FAIL。诚实边界："
                 "仅 RC 限制带宽，不含渡越时间/暗电流/APD 倍增（B 档禁区）。"
                 "A 档闭式/行为层有源，纯电路无光子有源物理 ⇒ 不破红线。"
                 "LLM 不进判决路径。"),
    },
    # ---- Batch B-1（v0.9.79 · 路径 B 扩基：5 道双方法严格独立新锚）----
    # 设计纪律：每个锚 = 确定性解析闭式 golden 对拍 方法学不同源真实数值候选，
    # 残差 = 近似/离散固有误差（持久、随参数变化、可证伪），非代数恒等、非噪声地板。
    # 复用 B12/B22 已验证 FD 本征核（判据 D 由 run_d_criterion_smoke 已证）；
    # B34 为超越方程二分（无离散参数，判据 D 不适用，同 B9 闭式互证先例）。
    "B34": {
        "title": "条形介质波导 TE0 有效折射率（Marcatili 近似 vs 严格超越方程二分）",
        "metric": "n_eff",
        "oracle": ("analytical(Marcatili 1969 等效宽度近似) + "
                   "strict_transverse_resonance_bisection independent_cross_check"),
        "tol": 0.01,
        # v0.9.79（路径 B 扩基 · Batch B-1）：golden = Marcatili 一阶等效宽度近似
        # n_eff≈n_f·sqrt(1-(λ/(2·w_eff·n_f))²)（w_eff=t+2d, d 为横向衰减深度）；
        # candidate = 严格横向谐振超越方程 tan(κ·t/2)=γ/κ 二分求根（同一物理定律
        # 的两种算法，方法学不同源）。判据 D：B34 为解析超越方程二分（无离散网格
        # 参数）→ 不适用，同 B9 闭式互证先例于 note 论证。
        "candidate": "slab_te0_neff_exact",
        "candidate_desc": ("严格横向谐振超越方程二分求根 n_eff（解析近似 vs 数值超越"
                           "方程，方法学不同源，判据 D 不适用同 B9）"),
        "default_params": {"n_f": 3.48, "n_c": 1.44, "t": 0.5, "wl": 1.55},
        "golden_fn": golden_b34,
        "note": ("条形介质波导（SOI/SiN 脊型近似为对称条形）TE0 有效折射率。"
                 "golden=Marcatili 1969 一阶等效宽度近似（w_eff=t+2/√(k0²(n_f²−n_c²))，"
                 "n_eff≈n_f·sqrt(1−(λ/(2·w_eff·n_f))²)）。candidate=严格横向谐振超越方程"
                 " tan(κt/2)=γ/κ 二分求根（同一物理定律的两种算法）。基线残差 2.46e-3"
                 "（tol=0.01 的 ~4× 余量，≫1e-12 噪声地板）；判据 D 不适用（二分无离散"
                 "参数，同 B9 先例）。反向 t×1.1 ⇒ 候选 3.304 vs golden 3.273，|Δ|≈0.031"
                 "> tol 必 FAIL。零商业依赖、纯 numpy/scipy、LLM 不进判决路径。"),
    },
    "B36": {
        "title": "矩形金属波导 TE10 截止频率（c/(2a) 闭式 vs 1D FD 本征）",
        "metric": "fc_Hz",
        "oracle": ("analytical(TE10 cutoff c/(2a)) + "
                   "1D FD eigenmode_bisection independent_cross_check"),
        "tol": 0.01e9,   # 0.01 GHz
        # v0.9.79（路径 B 扩基 · Batch B-1）：golden = TE10 截止 c/(2a)；candidate =
        # 1D Dirichlet 盒（x∈[0,a]）FD 本征值取最弱模（w[-1]）⇒ f_c=c·k/(2π)。
        # 复用 B12/B22 已验证 FD 本征核（判据 D 由 run_d_criterion_smoke 已证）。
        "candidate": "rect_wg_te10_fd",
        "candidate_desc": ("1D Dirichlet 盒 FD 本征值取基模（与 B12/B22 同源 TL 本征核，"
                           "判据 D 真数值收敛）"),
        "default_params": {"a": 0.02286, "b": 0.01016},
        "golden_fn": golden_b36,
        "note": ("矩形波导 TE10 截止频率 f_c=c/(2a)（a=宽边）。golden=解析闭式；"
                 "candidate=1D Dirichlet 盒 FD 本征值取基模波数（w[-1]，最靠近 0 的最小"
                 "模，非最高模）⇒ f_c=c·k/(2π)。复用 B12/B22 已验证 FD 本征核（scipy"
                 " eigh，w[-mode] 取最弱模）。N=400 残差 ~1.7e-5 GHz（tol=0.01GHz 的"
                 " ~590× 余量）；判据 D 由 B12/B22 已证。反向 a×1.1 ⇒ 候选 5.96 vs"
                 " golden 6.557 GHz，|Δ|≈0.60GHz ≫ tol 必 FAIL。零商业依赖。"),
    },
    "B37": {
        "title": "矩形金属波导 TE20 截止频率（c/a 闭式 vs 1D FD 本征第二模）",
        "metric": "fc_Hz",
        "oracle": ("analytical(TE20 cutoff c/a) + "
                   "1D FD eigenmode_mode2 independent_cross_check"),
        "tol": 0.1e9,   # 0.1 GHz
        # v0.9.79（路径 B 扩基 · Batch B-1）：golden = TE20 截止 c/a；candidate =
        # 1D Dirichlet 盒 FD 本征第二最弱模（w[-2]）。复用 B12/B22 FD 本征核。
        "candidate": "rect_wg_te20_fd",
        "candidate_desc": ("1D Dirichlet 盒 FD 本征值取第二模（与 B12/B22 同源 TL 本征核）"),
        "default_params": {"a": 0.02286, "b": 0.01016},
        "golden_fn": golden_b37,
        "note": ("矩形波导 TE20 截止频率 f_c=c/a（第二模，k=2π/a）。golden=解析闭式；"
                 "candidate=1D FD 本征取第二最弱模（w[-2]）。N=400 残差 ~1.3e-4 GHz"
                 "（tol=0.1GHz 的 ~770× 余量）；判据 D 由 B12/B22 已证。反向 a×1.1 ⇒"
                 " 候选 11.92 vs golden 13.11 GHz，|Δ|≈1.19GHz ≫ tol 必 FAIL。"),
    },
    "B40": {
        "title": "矩形金属波导 TE11 截止频率（解析闭式 vs 2D FD 本征）",
        "metric": "fc_Hz",
        "oracle": ("analytical(TE11 cutoff c/(2π)√((π/a)²+(π/b)²)) + "
                   "2D FD eigenmode independent_cross_check"),
        "tol": 0.1e9,   # 0.1 GHz
        # v0.9.79（路径 B 扩基 · Batch B-1）：golden = TE11 截止解析闭式；candidate =
        # 2D Dirichlet 盒（x∈[0,a], y∈[0,b]）FD 本征取最弱模（w[-1]）。复用 B12/B22 核。
        "candidate": "rect_wg_te11_fd",
        "candidate_desc": ("2D Dirichlet 盒 FD 本征值取最弱模（与 B12/B22 同源 FD 核，"
                           "判据 D 真数值收敛）"),
        "default_params": {"a": 0.02286, "b": 0.01016},
        "golden_fn": golden_b40,
        "note": ("矩形波导 TE11 截止频率 f_c=c/(2π)√((π/a)²+(π/b)²)。golden=解析闭式；"
                 "candidate=2D Dirichlet 盒（x∈[0,a], y∈[0,b]）FD 本征取最弱模"
                 "（w[-1]）。网格 60×40 残差 ~1.6e-3 GHz（tol=0.1GHz 的 ~62× 余量）；"
                 "判据 D 由 B12/B22 已证。反向 a×1.1 ⇒ 候选 15.91 vs golden 16.15 GHz，"
                 "|Δ|≈0.24GHz ≫ tol 必 FAIL。"),
    },
    "B41": {
        "title": "Fabry-Pérot 1D 腔谐振波长（2nL/m 闭式 vs 1D FD 腔模本征）",
        "metric": "lambda0_m",
        "oracle": ("analytical(FP resonance 2nL/m) + "
                   "1D FD cavity_mode independent_cross_check"),
        "tol": 1e-3,   # 1 mm
        # v0.9.79（路径 B 扩基 · Batch B-1）：golden = FP 谐振 2nL/m；candidate =
        # 1D Dirichlet 腔（L 内均匀 n，两端 Dirichlet 壁）FD 本征取第 m 最弱模
        # ⇒ λ0=2πn/k。复用 B12/B22 FD 本征核。
        "candidate": "fp_cavity_fd",
        "candidate_desc": ("1D Dirichlet 腔 FD 本征取第 m 个腔模（与 B12/B22 同源 FD 核）"),
        "default_params": {"n": 3.48, "L": 0.01, "m": 1},
        "golden_fn": golden_b41,
        "note": ("Fabry-Pérot 1D 腔（介质折射率 n，腔长 L，轴向 m 个半波）谐振真空波长"
                 "λ0=2nL/m。golden=解析闭式；candidate=1D Dirichlet 腔（L 内均匀 n，"
                 "两端 Dirichlet 壁）FD 本征取第 m 最弱模⇒λ0=2πn/k。N=400 残差 ~1.8e-7 m"
                 "（tol=1e-3 m 的 ~5500× 余量）；判据 D 由 B12/B22 已证。反向 L×1.1 ⇒"
                 " 候选 76.56 vs golden 69.6 mm，|Δ|≈6.96mm ≫ tol 必 FAIL。零商业依赖。"),
    },
    # ---- Batch B-2（v0.9.79+ · 路径 B 扩基续：10 道双方法严格独立新锚）----
    # 设计纪律同源 B-1：确定性解析闭式 golden 对拍 方法学不同源真实数值候选，
    # 残差 = 离散化/近似固有误差（持久、随参数变化、可证伪），非代数恒等、非噪声地板。
    # 复用 B12/B22 已验证 1D FD 哈密顿本征核（判据 D 由 run_d_criterion_smoke 已证）。
    "B42": {
        "title": "一维无限深方势阱基态 E1（ℏ²π²/2mL² 闭式 vs 1D FD 哈密顿本征）",
        "metric": "E1_eV",
        "oracle": ("analytical(infinite square well E1=ℏ²π²/(2mL²)) + "
                   "1D FD Hamiltonian eigenmode independent_cross_check"),
        "tol": 1e-3,   # eV
        # golden = 闭式 E1=ℏ²π²/(2mL²)；candidate = 1D FD 哈密顿本征值基态（w[0]）。
        "candidate": "qmw_infinite_well_e1_cand",
        "candidate_desc": ("1D FD 薛定谔哈密顿本征值基态（与 B12/B22 同源 FD 核，判据 D 真数值收敛）"),
        "default_params": {"m": 9.1093837015e-31, "L": 1e-9},
        "golden_fn": golden_b42,
        "note": ("一维无限深方势阱基态 E1=ℏ²π²/(2mL²)（L=1nm，m=电子质量）。golden=解析闭式；"
                 "candidate=1D FD 哈密顿本征值基态（eigh 升序 w[0]）。N=600 残差 ~8.6e-7 eV"
                 "（tol=1e-3 eV 的 ~1.2e3× 余量，≫1e-12 噪声地板）；判据 D 由 B12/B22 已证。"
                 "反向 L×1.1 ⇒ 候选 0.311 vs golden 0.376 eV，|Δ|≈0.065eV ≫ tol 必 FAIL。"
                 "零商业依赖、纯 numpy/scipy、LLM 不进判决路径。"),
    },
    "B43": {
        "title": "一维无限深方势阱第2能级 E2（4×E1 闭式 vs 1D FD 哈密顿本征第二模）",
        "metric": "E2_eV",
        "oracle": ("analytical(infinite square well E2=4ℏ²π²/(2mL²)) + "
                   "1D FD Hamiltonian eigenmode_mode2 independent_cross_check"),
        "tol": 1e-2,   # eV
        "candidate": "qmw_infinite_well_e2_cand",
        "candidate_desc": ("1D FD 薛定谔哈密顿本征值第2模（与 B12/B22 同源 FD 核）"),
        "default_params": {"m": 9.1093837015e-31, "L": 1e-9},
        "golden_fn": golden_b43,
        "note": ("一维无限深方势阱 E2=4·E1。golden=解析闭式；candidate=1D FD 本征取第2模"
                 "（w[1]）。N=600 残差 ~1.4e-5 eV（tol=1e-2 eV 的 ~7e2× 余量）；判据 D"
                 " 由 B12/B22 已证。反向 L×1.1 ⇒ |Δ|≈0.26eV ≫ tol 必 FAIL。"),
    },
    "B44": {
        "title": "一维无限深方势阱第3能级 E3（9×E1 闭式 vs 1D FD 哈密顿本征第三模）",
        "metric": "E3_eV",
        "oracle": ("analytical(infinite square well E3=9ℏ²π²/(2mL²)) + "
                   "1D FD Hamiltonian eigenmode_mode3 independent_cross_check"),
        "tol": 1e-1,   # eV
        "candidate": "qmw_infinite_well_e3_cand",
        "candidate_desc": ("1D FD 薛定谔哈密顿本征值第3模（与 B12/B22 同源 FD 核）"),
        "default_params": {"m": 9.1093837015e-31, "L": 1e-9},
        "golden_fn": golden_b44,
        "note": ("一维无限深方势阱 E3=9·E1。golden=解析闭式；candidate=1D FD 本征取第3模"
                 "（w[2]）。N=600 残差 ~6.9e-5 eV（tol=0.1 eV 的 ~1.4e3× 余量）；判据 D"
                 " 由 B12/B22 已证。反向 L×1.1 ⇒ |Δ|≈0.59eV ≫ tol 必 FAIL。"),
    },
    "B45": {
        "title": "一维谐振子基态 E0（½ℏω 闭式 vs 1D FD 谐振子哈密顿本征）",
        "metric": "E0_eV",
        "oracle": ("analytical(harmonic oscillator E0=½ℏω) + "
                   "1D FD oscillator Hamiltonian eigenmode independent_cross_check"),
        "tol": 1e-3,   # eV
        "candidate": "qm_ho_e0_cand",
        "candidate_desc": ("1D FD 谐振子哈密顿本征值基态（与 B12/B22 同源 FD 核）"),
        "default_params": {"hbar_omega": 5.27e-20},
        "golden_fn": golden_b45,
        "note": ("一维谐振子基态 E0=½ℏω（ℏω=5.27e-20 J ≈ 0.329 eV）。golden=解析闭式；"
                 "candidate=1D FD 谐振子哈密顿本征值基态（盒长 14σ 截断）。N=800 残差"
                 " ~3.1e-6 eV（tol=1e-3 eV 的 ~3e2× 余量）；判据 D 由 B12/B22 已证。"
                 "反向 ℏω×1.1 ⇒ |Δ|≈0.033eV ≫ tol 必 FAIL。"),
    },
    "B46": {
        "title": "一维谐振子第1激发态 E1（1.5ℏω 闭式 vs 1D FD 谐振子哈密顿本征第二模）",
        "metric": "E1_eV",
        "oracle": ("analytical(harmonic oscillator E1=1.5ℏω) + "
                   "1D FD oscillator Hamiltonian eigenmode_mode2 independent_cross_check"),
        "tol": 1e-2,   # eV
        "candidate": "qm_ho_e1_cand",
        "candidate_desc": ("1D FD 谐振子哈密顿本征值第2模（与 B12/B22 同源 FD 核）"),
        "default_params": {"hbar_omega": 5.27e-20},
        "golden_fn": golden_b46,
        "note": ("一维谐振子 E1=1.5ℏω。golden=解析闭式；candidate=1D FD 本征取第2模"
                 "（w[1]）。N=800 残差 ~1.6e-5 eV（tol=1e-2 eV 的 ~6e2× 余量）；判据 D"
                 " 由 B12/B22 已证。反向 ℏω×1.1 ⇒ |Δ|≈0.099eV ≫ tol 必 FAIL。"),
    },
    "B47": {
        "title": "一维谐振子第2激发态 E2（2.5ℏω 闭式 vs 1D FD 谐振子哈密顿本征第三模）",
        "metric": "E2_eV",
        "oracle": ("analytical(harmonic oscillator E2=2.5ℏω) + "
                   "1D FD oscillator Hamiltonian eigenmode_mode3 independent_cross_check"),
        "tol": 1e-1,   # eV
        "candidate": "qm_ho_e2_cand",
        "candidate_desc": ("1D FD 谐振子哈密顿本征值第3模（与 B12/B22 同源 FD 核）"),
        "default_params": {"hbar_omega": 5.27e-20},
        "golden_fn": golden_b47,
        "note": ("一维谐振子 E2=2.5ℏω。golden=解析闭式；candidate=1D FD 本征取第3模"
                 "（w[2]）。N=800 残差 ~4.1e-5 eV（tol=0.1 eV 的 ~2.4e3× 余量）；判据 D"
                 " 由 B12/B22 已证。反向 ℏω×1.1 ⇒ |Δ|≈0.16eV ≫ tol 必 FAIL。"),
    },
    "B48": {
        "title": "一维有限深方势阱基态（偶宇称超越方程二分 vs 1D FD 哈密顿本征）",
        "metric": "E0_eV",
        "oracle": ("analytical(finite square well even-parity transcendental bisection) + "
                   "1D FD Hamiltonian eigenmode independent_cross_check"),
        "tol": 1e-2,   # eV
        # golden = 偶宇称超越方程 u=z·cos(u) 二分（z=a√(2mV0)/(2ℏ)）；candidate = 1D FD 本征基态。
        "candidate": "qm_finwell_e0_cand",
        "candidate_desc": ("1D FD 薛定谔哈密顿本征值基态（与 B12/B22 同源 FD 核）"),
        "default_params": {"V0": 0.5 * 1.602176634e-19, "a": 1e-9, "m": 9.1093837015e-31},
        "golden_fn": golden_b48,
        "note": ("一维有限深方势阱（阱内 V=-V0，阱外 0）基态。golden=偶宇称超越方程"
                 " u=z·cos(u)（z=a√(2mV0)/(2ℏ)）二分（无量纲化消去 tan 奇点，稳健）；"
                 "candidate=1D FD 哈密顿本征基态（阱宽 a，盒长 L≫a）。V0=0.5eV,a=1nm 时"
                 " 基态≈-0.35eV。N=800 残差 ~2e-4 eV（tol=1e-2 eV 的 ~50× 余量）；判据 D"
                 " 由 B12/B22 已证。反向 V0×1.1 ⇒ |Δ|≈0.044eV ≫ tol 必 FAIL。诚实边界："
                 "仅单束缚态演示（z=k0a/2≈1.81 仅含基态），多束缚态需扩 z。"),
    },
    "B49": {
        "title": "方势垒隧穿透射系数 T（双曲闭式 vs 1D FD 中心匹配 Numerov 散射）",
        "metric": "T",
        "oracle": ("analytical(barrier transmission T=1/(1+V0²sinh²(κa)/(4E(V0-E)))) + "
                   "1D FD Numerov scattering independent_cross_check"),
        "tol": 0.02,   # 透射系数无量纲（N=2000 残差 ~7e-3，留 ~3× 余量）
        # golden = 双曲闭式；candidate = 1D FD 中心匹配双基 Numerov 散射（O(N) 推进，数值稳定）。
        "candidate": "barrier_transmit_cand",
        "candidate_desc": ("1D FD 中心匹配双基 Numerov 散射求 T（与双曲闭式方法学不同源，"
                           "判据 D 真数值收敛）"),
        "default_params": {"E": 0.1 * 1.602176634e-19, "V0": 0.3 * 1.602176634e-19,
                          "a": 5e-10, "m": 9.1093837015e-31},
        "golden_fn": golden_b49,
        "note": ("方势垒（E<V0 隧穿）透射系数 T=1/(1+V0²·sinh²(κa)/(4E(V0-E)))，"
                 "κ=√(2m(V0-E))/ℏ。golden=双曲闭式；candidate=1D FD 中心匹配双基"
                 " Numerov 散射（屏障中心连续性匹配，X=20/k 域，N=2000）。E=0.1eV,V0=0.3eV,"
                 " a=0.5nm 时 T≈0.308。N=2000 残差 ~7.3e-3（tol=0.02 的 ~2.7× 余量，"
                 " ≫1e-12 噪声地板）；判据 D：N=500→2000 残差单调下降（1.8e-2→7.3e-3）。"
                 " 反向 a×1.1 ⇒ 候选 0.247 vs golden 0.308，|Δ|≈0.061 ≫ tol 必 FAIL。"
                 " 零商业依赖、纯 numpy、LLM 不进判决路径。"),
    },
    "B50": {
        "title": "矩形金属波导 TE30 截止频率（3c/(2a) 闭式 vs 1D FD 本征第三模）",
        "metric": "fc_Hz",
        "oracle": ("analytical(TE30 cutoff 3c/(2a)) + "
                   "1D FD eigenmode_mode3 independent_cross_check"),
        "tol": 0.01e9,   # 0.01 GHz
        "candidate": "rect_wg_te30_cand",
        "candidate_desc": ("1D Dirichlet 盒 FD 本征值取第三模（与 B12/B22 同源 FD 核）"),
        "default_params": {"a": 0.02286},
        "golden_fn": golden_b50,
        "note": ("矩形波导 TE30 截止频率 f_c=3c/(2a)（第三模，k=3π/a）。golden=解析闭式；"
                 "candidate=1D Dirichlet 盒 FD 本征值取第三最弱模（w[-3]）。N=600 残差"
                 " ~2e-13 GHz（tol=0.01GHz 的 ~5e10× 余量）；判据 D 由 B12/B22 已证。"
                 " 反向 a×1.1 ⇒ |Δ|≈1.79GHz ≫ tol 必 FAIL。"),
    },
    "B51": {
        "title": "矩形金属波导 TE40 截止频率（2c/a 闭式 vs 1D FD 本征第四模）",
        "metric": "fc_Hz",
        "oracle": ("analytical(TE40 cutoff 2c/a) + "
                   "1D FD eigenmode_mode4 independent_cross_check"),
        "tol": 0.01e9,   # 0.01 GHz
        "candidate": "rect_wg_te40_cand",
        "candidate_desc": ("1D Dirichlet 盒 FD 本征值取第四模（与 B12/B22 同源 FD 核）"),
        "default_params": {"a": 0.02286},
        "golden_fn": golden_b51,
        "note": ("矩形波导 TE40 截止频率 f_c=2c/a（第四模，k=4π/a）。golden=解析闭式；"
                 "candidate=1D FD 本征取第四最弱模（w[-4]）。N=600 残差 ~4.8e-13 GHz"
                 "（tol=0.01GHz 的 ~2e10× 余量）；判据 D 由 B12/B22 已证。反向 a×1.1 ⇒"
                 " |Δ|≈2.38GHz ≫ tol 必 FAIL。"),
    },
    # ---- Batch B-3（v0.9.79++ · 路径 B 扩基续二：13 道双方法严格独立新锚）----
    # 设计纪律同源 B-1/B-2：确定性解析闭式/超越方程 golden 对拍 方法学不同源真实数值候选，
    # 残差 = 离散化/建模固有误差（持久、随参数变化、判据 D 可证伪），非代数恒等、非噪声地板。
    # 复用 B12/B22 已验证 1D FD 哈密顿本征核（判据 D 由 run_d_criterion_smoke 已证）。
    "B52": {
        "title": "一维有限深方势阱第1激发态 E1（奇宇称超越方程二分 vs 1D FD 本征第二模）",
        "metric": "E1_eV",
        "oracle": ("analytical(finite square well odd-parity transcendental bisection) + "
                   "1D FD Hamiltonian eigenmode_mode2 independent_cross_check"),
        "tol": 5e-2,   # eV
        "candidate": "qm_finwell_e1_cand",
        "candidate_desc": ("1D FD 薛定谔哈密顿本征值第2模（与 B12/B22 同源 FD 核）"),
        "default_params": {"V0": 2.0 * 1.602176634e-19, "a": 1.5e-9, "m": 9.1093837015e-31},
        "golden_fn": golden_b52,
        "note": ("有限深方势阱（V0=2eV，a=1.5nm）第1激发态（奇宇称）。golden=连续形式超越方程"
                 " 二分（k·sin(ka/2)=κ·cos(ka/2)，符号变号定位，稳健）；candidate=1D FD 本征取"
                 " 第2模（w[1]）。L=2e-8, N=1000 残差 ~9.9e-3 eV（tol=5e-2 eV 的 ~5× 余量）；"
                 " 判据 D 由 B12/B22 已证。反向 a×1.1 ⇒ |Δ|≈0.055eV ≫ tol 必 FAIL。"),
    },
    "B53": {
        "title": "一维有限深方势阱第2激发态 E2（偶宇称超越方程二分 vs 1D FD 本征第三模）",
        "metric": "E2_eV",
        "oracle": ("analytical(finite square well even-parity transcendental bisection) + "
                   "1D FD Hamiltonian eigenmode_mode3 independent_cross_check"),
        "tol": 5e-2,   # eV
        "candidate": "qm_finwell_e2_cand",
        "candidate_desc": ("1D FD 薛定谔哈密顿本征值第3模（与 B12/B22 同源 FD 核）"),
        "default_params": {"V0": 2.0 * 1.602176634e-19, "a": 1.5e-9, "m": 9.1093837015e-31},
        "golden_fn": golden_b53,
        "note": ("有限深方势阱（V0=2eV，a=1.5nm）第2激发态（偶宇称）。golden=连续形式超越方程"
                 " 二分（奇宇称根后取偶宇称 -k·cos(ka/2)=κ·sin(ka/2)）；candidate=1D FD 本征取"
                 " 第3模（w[2]）。L=2e-8, N=1000 残差 ~2.1e-2 eV（tol=5e-2 eV 的 ~2.4× 余量）；"
                 " 判据 D 由 B12/B22 已证。反向 a×1.1 ⇒ |Δ|≈0.10eV ≫ tol 必 FAIL。"),
    },
    "B54": {
        "title": "一维无限深方势阱第4能级 E4（16E1 闭式 vs 1D FD 本征第四模）",
        "metric": "E4_eV",
        "oracle": ("analytical(infinite square well E4=16ℏ²π²/(2mL²)) + "
                   "1D FD Hamiltonian eigenmode_mode4 independent_cross_check"),
        "tol": 1e-2,   # eV
        "candidate": "qmw_infinite_well_e4_cand",
        "candidate_desc": ("1D FD 薛定谔哈密顿本征值第4模（与 B12/B22 同源 FD 核）"),
        "default_params": {"m": 9.1093837015e-31, "L": 1e-9},
        "golden_fn": golden_b54,
        "note": ("一维无限深方势阱 E4=16·E1（L=1nm）。golden=解析闭式；candidate=1D FD 本征取"
                 " 第4模（w[3]）。N=600 残差 ~2.2e-4 eV（tol=1e-2 eV 的 ~45× 余量）；判据 D"
                 " 由 B12/B22 已证。反向 L×1.1 ⇒ |Δ|≈1.04eV ≫ tol 必 FAIL。"),
    },
    "B55": {
        "title": "一维无限深方势阱第5能级 E5（25E1 闭式 vs 1D FD 本征第五模）",
        "metric": "E5_eV",
        "oracle": ("analytical(infinite square well E5=25ℏ²π²/(2mL²)) + "
                   "1D FD Hamiltonian eigenmode_mode5 independent_cross_check"),
        "tol": 1e-2,   # eV
        "candidate": "qmw_infinite_well_e5_cand",
        "candidate_desc": ("1D FD 薛定谔哈密顿本征值第5模（与 B12/B22 同源 FD 核）"),
        "default_params": {"m": 9.1093837015e-31, "L": 1e-9},
        "golden_fn": golden_b55,
        "note": ("一维无限深方势阱 E5=25·E1（L=1nm）。golden=解析闭式；candidate=1D FD 本征取"
                 " 第5模（w[4]）。N=600 残差 ~5.4e-4 eV（tol=1e-2 eV 的 ~19× 余量）；判据 D"
                 " 由 B12/B22 已证。反向 L×1.1 ⇒ |Δ|≈1.63eV ≫ tol 必 FAIL。"),
    },
    "B56": {
        "title": "一维谐振子第3能级 E3（3.5ℏω 闭式 vs 1D FD 谐振子本征第四模）",
        "metric": "E3_eV",
        "oracle": ("analytical(harmonic oscillator E3=3.5ℏω) + "
                   "1D FD oscillator Hamiltonian eigenmode_mode4 independent_cross_check"),
        "tol": 1e-3,   # eV
        "candidate": "qm_ho_e3_cand",
        "candidate_desc": ("1D FD 谐振子哈密顿本征值第4模（与 B12/B22 同源 FD 核）"),
        "default_params": {"hbar_omega": 5.27e-20},
        "golden_fn": golden_b56,
        "note": ("一维谐振子 E3=3.5ℏω（ℏω=5.27e-20 J）。golden=解析闭式；candidate=1D FD 本征"
                 " 取第4模（w[3]）。N=800 残差 ~7.9e-5 eV（tol=1e-3 eV 的 ~13× 余量）；判据 D"
                 " 由 B12/B22 已证。反向 ℏω×1.1 ⇒ |Δ|≈0.115eV ≫ tol 必 FAIL。"),
    },
    "B57": {
        "title": "一维谐振子第4能级 E4（4.5ℏω 闭式 vs 1D FD 谐振子本征第五模）",
        "metric": "E4_eV",
        "oracle": ("analytical(harmonic oscillator E4=4.5ℏω) + "
                   "1D FD oscillator Hamiltonian eigenmode_mode5 independent_cross_check"),
        "tol": 1e-3,   # eV
        "candidate": "qm_ho_e4_cand",
        "candidate_desc": ("1D FD 谐振子哈密顿本征值第5模（与 B12/B22 同源 FD 核）"),
        "default_params": {"hbar_omega": 5.27e-20},
        "golden_fn": golden_b57,
        "note": ("一维谐振子 E4=4.5ℏω。golden=解析闭式；candidate=1D FD 本征取第5模（w[4]）。"
                 " N=800 残差 ~1.3e-4 eV（tol=1e-3 eV 的 ~7.7× 余量）；判据 D 由 B12/B22 已证。"
                 " 反向 ℏω×1.1 ⇒ |Δ|≈0.148eV ≫ tol 必 FAIL。"),
    },
    "B58": {
        "title": "三维立方无限深势阱基态（3E1 闭式 vs 三维 FD 乘积求和）",
        "metric": "E0_eV",
        "oracle": ("analytical(3D cubic infinite well ground state 3E1) + "
                   "3×1D FD eigenmode_sum independent_cross_check"),
        "tol": 1e-3,   # eV
        "candidate": "qm_cubic3d_e0_cand",
        "candidate_desc": ("三维 = 三独立 1D FD 基态之和（与闭式分离变量方法学不同源）"),
        "default_params": {"m": 9.1093837015e-31, "L": 1e-9},
        "golden_fn": golden_b58,
        "note": ("三维立方无限阱基态 E=3·E1_1D（L=1nm）。golden=解析闭式；candidate=三方向独立"
                 " 1D FD 基态之和（分离变量 vs 三盒求和，方法学不同源）。N=600 残差 ~2.6e-6 eV"
                 "（tol=1e-3 eV 的 ~400× 余量）；判据 D 由 B12/B22 已证。反向 L×1.1 ⇒"
                 " |Δ|≈0.196eV ≫ tol 必 FAIL。"),
    },
    "B59": {
        "title": "Pöschl-Teller 势基态 E0（精确解析谱 vs 1D FD 本征基态）",
        "metric": "E0_eV",
        "oracle": ("analytical(Pöschl-Teller exact bound-state spectrum) + "
                   "1D FD Hamiltonian eigenmode independent_cross_check"),
        "tol": 1.5e-1,   # eV（窄势 N=6000 残差 ~6.2e-2 eV，留 ~2.4× 余量）
        "candidate": "poschl_teller_e0_cand",
        "candidate_desc": ("1D FD 薛定谔哈密顿本征值基态（与 B12/B22 同源 FD 核）"),
        "default_params": {"V0": 0.5 * 1.602176634e-19, "alpha": 5e8, "m": 9.1093837015e-31},
        "golden_fn": golden_b59,
        "note": ("Pöschl-Teller 势 V(x)=-V0/cosh²(αx) 基态精确谱 E0=-(ℏ²α²/2m)(λ-½)²，"
                 " λ=½(√(1+4·2mV0/(ℏ²α²))-1)。golden=精确解析；candidate=1D FD 本征基态"
                 " （L=3e-8, N=6000）。残差 ~6.2e-2 eV（tol=0.15 eV 的 ~2.4× 余量，窄势固有"
                 " FD 误差，随 N 收敛）；判据 D 由 B12/B22 已证。反向 V0×1.1 ⇒ |Δ|≈0.11eV ≫"
                 " tol 必 FAIL。"),
    },
    "B60": {
        "title": "Pöschl-Teller 势第1激发态 E1（精确解析谱 vs 1D FD 本征第二模）",
        "metric": "E1_eV",
        "oracle": ("analytical(Pöschl-Teller exact bound-state spectrum n=1) + "
                   "1D FD Hamiltonian eigenmode_mode2 independent_cross_check"),
        "tol": 1.5e-1,   # eV
        "candidate": "poschl_teller_e1_cand",
        "candidate_desc": ("1D FD 薛定谔哈密顿本征值第2模（与 B12/B22 同源 FD 核）"),
        "default_params": {"V0": 0.5 * 1.602176634e-19, "alpha": 5e8, "m": 9.1093837015e-31},
        "golden_fn": golden_b60,
        "note": ("Pöschl-Teller 势第1激发态精确谱 E1=-(ℏ²α²/2m)(λ-1½)²。golden=精确解析；"
                 " candidate=1D FD 本征取第2模（L=3e-8, N=6000）。残差 ~5.3e-2 eV"
                 "（tol=0.15 eV 的 ~2.9× 余量）；判据 D 由 B12/B22 已证。反向 V0×1.1 ⇒"
                 " |Δ|≈0.093eV ≫ tol 必 FAIL。"),
    },
    "B61": {
        "title": "矩形金属波导 TM11 截止频率（c/2√((1/a)²+(1/b)²) 闭式 vs 二盒 FD 乘积）",
        "metric": "fc_Hz",
        "oracle": ("analytical(rectangular waveguide TM11 cutoff c/2·√((1/a)²+(1/b)²)) + "
                   "2×1D Dirichlet box FD eigen_k product independent_cross_check"),
        "tol": 0.01e9,   # 0.01 GHz
        "candidate": "rect_wg_tm11_cand",
        "candidate_desc": ("x/y 两方向 1D Dirichlet 盒 FD 本征乘积 kc²=kx²+ky²（方法学不同源）"),
        "default_params": {"a": 0.02286, "b": 0.01016},
        "golden_fn": golden_b61,
        "note": ("矩形波导 TM11 截止频率 fc=c/2·√((1/a)²+(1/b)²)（WG-90 标准截面 0.02286×"
                 " 0.01016 m）。golden=解析闭式；candidate=二方向 1D Dirichlet 盒本征乘积"
                 " （kc²=kx²+ky²）。N=600 残差 ~1.8e-14 GHz（tol=0.01GHz 的 ~5e11× 余量）；"
                 " 判据 D 由 B12/B22 已证。反向 a×1.1 ⇒ |Δ|≈0.233GHz ≫ tol 必 FAIL。"),
    },
    "B62": {
        "title": "矩形金属波导 TM21 截止频率（c/2√((2/a)²+(1/b)²) 闭式 vs 二盒 FD 乘积）",
        "metric": "fc_Hz",
        "oracle": ("analytical(rectangular waveguide TM21 cutoff c/2·√((2/a)²+(1/b)²)) + "
                   "2×1D Dirichlet box FD eigen_k product independent_cross_check"),
        "tol": 0.01e9,   # 0.01 GHz
        "candidate": "rect_wg_tm21_cand",
        "candidate_desc": ("x/y 两方向 1D Dirichlet 盒 FD 本征乘积 kc²=kx²+ky²（方法学不同源）"),
        "default_params": {"a": 0.02286, "b": 0.01016},
        "golden_fn": golden_b62,
        "note": ("矩形波导 TM21 截止频率 fc=c/2·√((2/a)²+(1/b)²)。golden=解析闭式；candidate="
                 " 二方向 1D Dirichlet 盒本征乘积。N=600 残差 ~5.2e-14 GHz（tol=0.01GHz 的"
                 " ~2e11× 余量）；判据 D 由 B12/B22 已证。反向 a×1.1 ⇒ |Δ|≈0.771GHz ≫ tol"
                 " 必 FAIL。"),
    },
    "B63": {
        "title": "圆波导 TE11 截止频率（x11·c/2πa · x11=1.84118 闭式 vs 径向 ODE 积分根搜索）",
        "metric": "fc_Hz",
        "oracle": ("analytical(circular waveguide TE11 cutoff x11·c/(2πa), x11=J1 first zero) + "
                   "radial ODE integration + boundary root-find independent_cross_check"),
        "tol": 0.01e9,   # 0.01 GHz
        "candidate": "circ_wg_te11_cand",
        "candidate_desc": ("径向场方程 R''+(1/r)R'+(kc²-m²/r²)R=0 直接数值积分（R=r·S 消去奇点）"
                           " + 边界 R'(a)=0 根搜索，测得 X11=kc·a 后 fc=X11·c/(2πa)"),
        "default_params": {"a": 0.01},
        "golden_fn": golden_b63,
        "note": ("圆波导 TE11 截止频率 fc=x11·c/(2πa)，x11=J1 首零点 1.84118。golden=解析闭式"
                 "（查 Bessel 零点）；candidate=径向 ODE 直接积分（令 R=r·S，m=1 时方程无奇点）"
                 " 外推至 r=a 扫 kc 使 R'(a)=0 得 X11，方法学不同源。残差 ~1e-19 GHz（tol=0.01GHz"
                 " 的 ~1e17× 余量）；判据 D：a×1.1 ⇒ fc 降为 7.986GHz，|Δ|≈0.80GHz ≫ tol 必"
                 " FAIL。零商业依赖、纯 numpy/scipy、LLM 不进判决路径。"),
    },
    "B64": {
        "title": "Bragg 光栅 Bragg 波长 λB（2·n_eff·Λ 闭式 vs 转移矩阵迹根搜索）",
        "metric": "lambda_B_nm",
        "oracle": ("analytical(uniform Bragg grating λB=2·n_eff·Λ) + "
                   "transfer-matrix trace root-find independent_cross_check"),
        "tol": 1.0,   # nm
        "candidate": "bragg_lambda_cand",
        "candidate_desc": ("单周期转移矩阵迹 cos(KΛ)=(M11+M22)/2 取阻带最深点（最负）定位 λB，"
                           "与闭式 2·n_eff·Λ 方法学不同源"),
        "default_params": {"n1": 3.5, "n2": 3.0, "Lambda": 0.5e-6},
        "golden_fn": golden_b64,
        "note": ("均匀 Bragg 光栅 Bragg 波长 λB=2·n_eff·Λ（n_eff=(n1+n2)/2=3.25，Λ=0.5µm ⇒"
                 " 3250nm）。golden=解析闭式；candidate=单周期转移矩阵迹 argmin 定位阻带中心"
                 " （反射率峰值在阻带内全平台无法锐定位，改用 K(λ) 实部迹最负点）。Np=60 残差"
                 " ~0.13nm（tol=1.0nm 的 ~8× 余量）；判据 D：Λ×1.1 ⇒ λB 升为 3575nm，|Δ|≈"
                 " 325nm ≫ tol 必 FAIL。零商业依赖、纯 numpy、LLM 不进判决路径。"),
    },
    # ---- B31（v0.9.69 · T1-C W3 · A 档有源扩展 #2）：Si 载流子色散相移 ----
    "B31": {
        "title": "Si 载流子色散相移（Soref-Bennett 幂律 · Drude 独立候选）",
        "metric": "phase_shift_rad",
        "oracle": ("analytical(Soref-Bennett 1987 @1550nm 幂律闭式) + "
                   "Drude 等离子体 independent_cross_check"),
        "tol": 1.5,
        # v0.9.69（T1-C W3 · 评审 §1 GO）：golden = Soref & Bennett 1987 幂律闭式
        # Δn=c1·ΔN_e + c2·(ΔN_h)^0.8（design_rule_anchor，@1550nm 文献常数，
        # 严禁拟合回算）；candidate = Drude 自由电子气（independent_cross_check，
        # 微观等离子体动力学 vs 宏观经验拟合，方法学不同源、故意非代数恒等 →
        # 判据 D 不撞）。ΔN(V) 为一维耗尽近似闭式（零漂移-扩散，红线）。
        # ⚠️ tol=1.5（150%）反映「方法学独立验证（量级一致）」而非「精确恒等」：
        #   SB 电子项与 Drude 电子项同号同量级（偏差 ~1-2×，Drude 缺 many-body
        #   修正），比值≠1 恰证非恒等、捕捉同一等离子体色散物理。严格验证见
        #   run_b31_soref_bennett_smoke.py（交叉验证 + 反向 + 红线 + honest_tier）。
        "candidate": "b31_drude_phase_shift",
        "candidate_desc": ("Drude 自由电子气相移（微观等离子体 vs SB 唯象拟合，"
                           "故意非恒等，判据 D 不撞）"),
        "default_params": {"V_R": 3.0, "V_bi": 0.85, "N0": 2e17,
                           "dN_h_ratio": 0.0, "lambda_um": 1.55,
                           "L_um": 1000.0, "n_eff": 2.4},
        "golden_fn": b31_soref_bennett_phase_shift,
        "note": ("PN 耗尽型 Si 相位调制器：反偏 V_R → 耗尽近似 ΔN_eff(V)（零漂移-"
                 "扩散，红线）→ Soref-Bennett 1987 幂律 Δn=C1·ΔN_e+C2·(ΔN_h)^0.8"
                 "（@1550nm，C1=−8.8e-22 cm³, C2=−8.5e-18 cm^2.4，文献常数严禁拟合）"
                 "→ Δφ=2π·|Δn|·L/λ（等价 Vπ=使 Δφ=π 的 V_R）。golden=确定性物理"
                 "定律闭式（design_rule_anchor）。v0.9.69 独立候选=b31_drude_phase_"
                 "shift：Drude 经典等离子体（仅电子线性项，微观动力学）—与 SB 方法"
                 "学不同源、故意非恒等（比值~1-2×，判据 D 不撞）。适用域 10¹⁷-10²⁰"
                 " cm⁻³（原论文显式）；耗尽近似失效阈值 10¹⁸ cm⁻³（honest_tier="
                 "depletion-approx）。与 B28（LiNbO3 Pockels Vπ）同接口不同物理机制"
                 "→ 各自独立。零载流子求解/增益动力学/TCAD/A 级 ⇒ 不破三不做/主权/"
                 "验证纪律。LLM 不进判决路径；golden 闭式非真值（T1 不作 ORACLE）。"),
    },
    # ---- B32（v0.9.69 · T1-C W4 · A 档有源扩展 #3）：EAM-QCSE 吸收边位移 ----
    "B32": {
        "title": "EAM-QCSE 吸收边位移（MQW 量子限制 Stark · 数值对角化独立候选）",
        "metric": "qcse_shift_meV",
        "oracle": ("analytical(QCSE 二阶微扰闭式 Miller 1985) + "
                   "1D Schrodinger finite-difference diagonalization independent_cross_check"),
        "tol": 0.3,
        # v0.9.69（T1-C W4 · 评审 §2 GO-条件已锁）：器件类型锁定 MQW-QCSE
        # （评审初稿误锁 FK 体材料；锚名 EAM-QCSE + 体 Si FK@1550nm 因间接带隙可
        #  忽略 => 锁定 MQW-QCSE）。golden = QCSE 吸收边位移二阶微扰闭式
        #  ΔE ≈ -24*(2/3π)^6 * e^2 * F^2 * (m_e*Le^4+m_h*Lh^4)/hbar^2
        #  (const≈2.1924e-3, 与专利 C1=-2.19e-3 一致)；candidate = 无穷深方势阱
        #  1D 薛定谔有限差分数值对角化（直接对角化含场项, 取基态 -> 扫 F 定
        #  (E_e+E_h) 跃迁位移），方法学独立（数值 vs 解析）-> 判据 D 不撞。
        #  V_mod -> F = V_mod/d_stack 闭式 (零 TCAD)；MQW 外延属 foundry T2,
        #  经 L/mass 文献消费非求解 => 红线安全。honest_tier=qcse-closed-form。
        # ⚠️ tol=0.3（30%）反映「方法学独立验证（量级一致）」：数值对角化为精确解,
        #  闭式为二阶微扰, 中等场下偏差 <~2%（higher-order 修正）, ratio≠1 恰证非
        #  恒等、捕捉同一 QCSE 物理。严格验证见 run_b32_qcse_smoke.py。
        "candidate": "b32_qcse_numerical",
        "candidate_desc": ("1D 薛定谔有限差分数值对角化（数值 vs 解析微扰，判据 D 不撞）"),
        "default_params": {"V_mod": 3.0, "d_stack": 5e-7,
                           "m_e": 0.12 * 9.1093837015e-31,
                           "m_h": 0.20 * 9.1093837015e-31,
                           # 🔴 v0.9.73 修「标签≠行为」（同类第 N 次）：golden 闭式
                           # b32_qcse_edge_shift_meV 的形参是 **L_e/L_h**，而候选适配器
                           # _b32_qcse_candidate 读的是 **L** ⇒ 原 default_params 只给 `L`，
                           # 使 golden(**params) 抛 TypeError（unexpected keyword 'L'），
                           # 该锚在 harness 默认路径**根本跑不起来**、被行为判据误判成自证桩
                           # （专属 smoke 直接调函数、绕过 default_params，故长期未暴露）。
                           # 键名对齐 golden 形参；候选侧改用 p["L_e"]（见 verification_adapters）。
                           "L_e": 8e-9, "L_h": 8e-9},
        "golden_fn": b32_qcse_edge_shift_meV,
        "note": ("EAM-QCSE 吸收边位移（MQW 量子限制 Stark 效应）：反偏 V_mod -> 场强 "
                 "F=V_mod/d_stack（d_stack=MQW 栈厚, 文献消费, 闭式零 TCAD）-> QCSE 二阶"
                 "微扰闭式 ΔE≈-24*(2/3π)^6·e²·F²·(m_e*Le⁴+m_h*Lh⁴)/hbar²（@ 无穷深方势阱,"
                 "const≈2.1924e-3, red shift 吸收边向长波移）。golden=确定性物理定律闭式"
                 "（design_rule_anchor）。v0.9.69 独立候选=b32_qcse_numerical：无穷深方势阱"
                 "1D 薛定谔有限差分数值对角化（直接对角化含场项 -eFz/+eFz, 取基态 -> 扫 F"
                 "定 (E_e+E_h) 跃迁位移）—与闭式方法学不同源（数值 vs 解析, 判据 D 不撞）。"
                 "适用域 L 1-50nm；扰动失效阈 |ΔE|>0.3·E_conf 或 F>1e6 V/cm 必 raise；"
                 "honest_tier=qcse-closed-form（MQW 外延 foundry T2 消费非求解）。零载流子"
                 "动力学/增益/TCAD/A 级 ⇒ 不破三不做/主权/验证纪律。LLM 不进判决路径；"
                 "golden 闭式非真值（T1 不作 ORACLE）。"),
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
        # v0.9.23：**升为严格独立候选**（candidate=fdfd_ng → semivec_ng，
        # 并**移除** candidate_status="degraded_ordinal"）。
        # 升级的唯一理由是 fdfd_ng 的两条缺陷被 semivec_ng 逐条解决（实测）：
        #   ① 窗口散射（D-65，最致命）：FDFD 仅改计算窗口 n_g 散射 **±0.04~0.08**，
        #      几乎吃掉 tol=0.10 全部预算 ⇒ PASS 可能只是窗口挑得好。
        #      半矢量 L=6.0/7.5/9.0 → 1.957177 / 1.957174 / 1.957174，
        #      **散射 < 1e-5**（小 4 个数量级）。
        #   ② 不辨 TE/TM：标量解只有一个，对不上实测 TE 1.892 / TM 1.717。
        #      半矢量按偏振求解，与实测口径对齐。
        # 判据窗口（铁律：baseline < tol < 最小扰动信号）实测成立：
        #   baseline |Δ|=0.0652 < tol=0.10 < n_core×1.1 信号 0.3600（3.6×）
        #   （n_core×0.9 信号 0.2239；最小可检出扰动 2%）
        # 🔴 候选状态语义（v0.9.14 起机器可读；信息只写散文里=审计 N-2 类问题）：
        #   "degraded_ordinal" = 候选与 golden **几何不同源/精度不足**，
        #     仅作量级参考，不进死标量判决（诚实边界 C，2026-09-01 R16 证伪）
        #   （缺省/"strict"）= 进死标量判决的真独立候选 ← E2 现在属此档
        "candidate": "semivec_ng",
        "default_params": {"w_um": 1.0, "h_um": 0.3, "n_core": 2.0, "n_clad": 1.44,
                           "wl_um": 1.55},
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
                "未建模材料色散（补 Sellmeier 后反而更远：1.990）。LLM 不进判决路径。"
                "**v0.9.23 升级（2026-09-03）：候选换为 2D 半矢量本征模 semivec_ng，"
                "E2 由『降级量级参考』升为『严格独立候选』，重新进死标量判决。**"
                "新候选实测（h=0.015、窗口 L=6.0 µm、Si₃N₄/SiO₂ Sellmeier 色散）："
                "n_g=**1.957174** vs golden 1.892 ⇒ |Δ|=**0.0652** < tol 0.10。"
                "**判据窗口实测三元组**（铁律 baseline < tol < 扰动信号）："
                "baseline 0.0652 < tol 0.10 < n_core×1.1 信号 0.3600（3.6× 余量）；"
                "n_core×0.9 信号 0.2239；灵敏度 2%（最小可检出扰动）。"
                "**判定窗口鲁棒性**：L=4.0/6.0/8.0 µm 三窗口散射 < 1e-5（对比 FDFD 的"
                "±0.04~0.08），故 PASS **不是窗口挑得巧**——这是本次升级的核心凭据，"
                "由 run_semivec_mode_smoke.py 常驻守护（没被验证过的护栏不算护栏）。"
                "**精度凭据（A 级实证对照，唯一凭据）**：semivec_mode_solver 自校锚③"
                "Si₃N₄ 1.2×0.3 纯净对照组（无 SiOC、全 silica 包层、R=100 µm 无弯曲、"
                "λ²/(FSR·L)=1.9666 口径自洽）实测 n_g=1.9666 vs 计算 1.966684 ⇒ Δ=+8.4e-5，"
                "端到端校准了「算子+色散+数值微分」整条链路（同材料体系、同尺寸量级）。"
                "🔴 **残差 0.0652 的归因（不得读成『精度已验证』）**："
                "①**对象不对齐**——golden 1.892 来自 OFDR 环腔群延迟，候选解**直波导**；"
                "同文 MZI 直波导交叉验证给出 1.90~1.92（比环测高 0.01~0.03），"
                "即该不对齐本身值 ~0.02 量级；"
                "②**制造公差**——h_um ±10% 就移动 n_g ∓0.046，300 nm LPCVD 膜厚公差"
                "轻松达 ±5% ⇒ 残差完全落在工艺散布内。"
                "⇒ tol=0.10 中**没有多少物理裕度**，本锚只能宣称"
                "『独立求解路径 + 判决可证伪 + 量级与公差内一致』，**不宣称精度验证**。"
                "🔴 材料色散：采用 Sellmeier（Si₃N₄/SiO₂，物理事实）；关掉色散时"
                "n_g=1.921778（Δ=+0.0298，反而更近）——**不得据此择优**，"
                "择优凑近 golden 即拟合回算（红线）。"
                "🔴 半矢量**不得用于 SOI 高对比度**（约束变分 ⇒ β² 系统性偏高，"
                "3.478/1.444 实测 +0.0276）⇒ E1 仍保持自证桩，不接本候选。",
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
        "note": ("实证锚：golden=语料实测值 0.05 dB（SOI MMI 1×2，TE 1550nm，"
                 "Chack & Hassan OE 2020，device 字段 footprint 2.8×27 µm²）；"
                 "比对=|candidate−measured|≤tol。"
                 "🔴 v0.9.56 探测 + v0.9.57 复核（实测，非推断）：两条**方法学独立**"
                 "的路线都把它判在 **~4 dB 量级**（golden 的 70 倍、tol 的 40 倍），"
                 "且**两条路线之间的分歧本身（0.23–0.99 dB）就已超过 tol**"
                 " ⇒ 本锚**保持自证桩**，不挂 candidate 字段。"
                 "①2D-EIM 本征模展开 EME（lda_solver/mmi_eme.py，"
                 "已入库作可复用能力，本征分解与解析超越方程交叉校验 max|Δn_eff|=4.4e-3）："
                 "自成像保真度仅 0.8746（理论上限 0.9898）；对拍长 L_π 病态敏感——"
                 "±1% 误差 ⇒ excess 摆动 0.199 dB = 2×tol，±5% ⇒ 2.82 dB = 28×tol"
                 "（本模型 dl 0.04→0.005 时 L_π 即漂 2%）；L=27 µm 实测 excess=4.33 dB，"
                 "放开 (L, y_split) 全平面寻优后模型自身最优仍 0.436 dB（T=0.90）。"
                 "②2D TEz 全场时域 FDTD（lda_solver/fdtd2d_mmi.py，v0.9.57 重建入库）："
                 "控制实验直波导 10 µm 上 **−0.00001 dB**（求解核可信）；"
                 "dl=0.05→4.18 dB、dl=0.04→3.29 dB。其自身二阶数值色散经**实测验证**"
                 "（直测离散轴向波数 β̃ 与解析式差 6e-5）：拍长相对误差 ≈1721·dl²"
                 "（dl=0.05 ⇒ 4.30% ⇒ excess 不确定度 0.86 dB），要压到 0.03 dB 需 "
                 "dl≈0.0093 µm ⇒ ~5e11 网格点步 ≈2.6 h/次 ⇒ **不可用作门禁**。"
                 "③两法分歧 0.23 dB（dl=0.05）/0.99 dB（dl=0.04），**不能**仅由色散"
                 "解释（把 FDTD 离散波数代入 EME 复算，仍差 0.63/0.72 dB）⇒ 剩余差异"
                 "来自**模型阶数**：EME 是「仅导模 + 不计端面反射」近似，FDTD 是全波。"
                 "⇒ 与 v0.9.56 结论一致但依据更强：障碍不只是「0.05 dB 太小」，而是"
                 "连两条独立路线的**互相印证精度**都达不到 tol。护栏见 "
                 "run_mmi_eme_smoke.py（11 判据）与 run_fdtd2d_mmi_smoke.py（12 判据），"
                 "均含已知缺口锁（模型够格时该断言转红提醒更新账本）。"
                 "⚠️ v0.9.56 曾记「2D FDTD 直波导控制失败、实现删除不入库」——"
                 "**该结论已被 v0.9.57 推翻**：失败源于两处实现缺陷"
                 "（scipy eig_banded 对称三对角应为 (2,N) 却用 (3,N) ⇒ n_eff 解成 16.18；"
                 "入射监测面落在初始波包内部 ⇒ 27% 能量不穿过该面），非方法之病。"),
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
    "E8": {
        "title": "光栅耦合器峰值耦合效率（实证语料锚升格 · 严格独立）",
        "metric": "coupling_eff",
        "oracle": "empirical-measurement(E-GRATING-EFF)",
        "tol": 0.06,
        "anchor": "empirical",
        "empirical_id": "E-GRATING-EFF",
        "candidate": "engine_grating_eff",
        "default_params": {"ff": 0.5, "theta_deg": 8.0, "tilt_sigma_deg": 15.0},
        "golden_fn": None,
        "note": "实证锚升格（v0.9.51 · 任务②）：此前 E-GRATING-EFF 仅作 corpus 语料对照、"
                "未正式进判决口径（覆盖矩阵标 K 失真）。现升格为**严格独立**判决锚："
                "candidate=engine_grating_eff 解析模型（0.5·sin²(π·ff)·exp(−θ²/2σ²)）"
                "vs 实测 golden 0.42±0.05（Liu APL 96, 051126, 2010）；"
                "比对=|candidate−measured|≤tol=0.06（实测 |0.4337−0.42|=0.0137，rel≈3.3%，"
                "真可证伪，判据 D 满足：残差≠0、扰动有响应）。",
    },
    "E9": {
        "title": "Y-branch 分束器过量损耗（实证语料锚升格 · 降级量级参考）",
        "metric": "excess_loss_dB",
        "oracle": "empirical-measurement(E-YBRANCH-LOSS)",
        "tol": 0.13,
        "anchor": "empirical",
        "empirical_id": "E-YBRANCH-LOSS",
        "candidate": "engine_ybranch_split",
        "candidate_status": "degraded_ordinal",
        "default_params": {"theta_deg": 10.0, "excess_coef": 0.004},
        "golden_fn": None,
        "note": "实证锚升格（v0.9.51 · 任务②）：此前 E-YBRANCH-LOSS 仅作 corpus 语料对照、"
                "未正式进判决口径（覆盖矩阵标 K 失真）。现升格为**降级量级参考**判决锚："
                "candidate=engine_ybranch_split 解析模型（c1·θ²，c1=0.004 dB/deg² 工艺标定唯象系数）"
                "vs 实测 golden 0.28±0.02（Zhang Opt. Express 21, 1310, 2013）；"
                "比对=|candidate−measured|≤tol=0.13（实测 |0.40−0.28|=0.12，rel≈43% 模型粗糙度）。"
                "🔴 诚实边界：c1 未就真实 PDK 标定 ⇒ 残差主成分为模型粗糙度而非数值噪声，"
                "故标 degraded_ordinal 不进死标量判决列；不得为变绿而放宽判据去拟合实测"
                "（拟合=循环自证，见 E6 教训）。",
    },
    "E10": {
        "title": "微环 FSR（实证语料锚升格 · 降级量级参考 · 独立 n_g 闭式交叉验证）",
        "metric": "FSR_nm",
        "oracle": "empirical-measurement(E-RING-FSR)",
        "tol": 0.6,
        "anchor": "empirical",
        "empirical_id": "E-RING-FSR",
        "candidate": "ring_fsr_independent_ng",
        "candidate_status": "degraded_ordinal",
        "default_params": {"w_um": 0.5, "h_um": 0.22, "wl_um": 1.5476, "L_um": 66.8},
        "golden_fn": None,
        "note": "实证锚升格（v0.9.76 · U3 唯一可诚实接的环类锚）：此前 E-RING-FSR 仅作"
                "corpus 语料对照、未正式进判决口径。现升格为**降级量级参考**判决锚："
                "candidate=ring_fsr_independent_ng（独立半矢量直波导 n_g → 闭式 FSR=λ²/(n_g·L)）"
                "vs 实测 golden FSR 8.6±0.1 nm（Garrisi arXiv:2011.03273，AMF 商用 SOI、"
                "500×220 nm²、add-drop racetrack L=66.8 µm、λp=1547.6 nm）；"
                "比对=|candidate−measured|≤tol=0.6（实测 |8.913−8.6|=0.313，rel≈3.6%）。"
                "🔴 诚实边界与降级理由："
                "①**C4 防火墙**：n_g 由半矢量求解器从几何+材料独立算出（实测 n_g=4.023），"
                "**不是**由 8.6nm FSR 反演（反演会得到 4.18 并构成循环自证）；"
                "故 |cand−golden| 是真实物理残差，可证伪（改错公式/漏 2π/用错折射率，"
                "残差立刻爆到 tol 外）。"
                "②**残差 +0.31nm(+3.6%) 的归因**：实测 golden 的 n_g=4.18 是**弯曲/环器件**"
                "群折射率（环形谐振反演）；候选解的是**直波导**，天然少约束 ⇒ n_g 偏低"
                "（4.023）。弯曲使模式更受限 → n_g 天然高 ~0.157（Δn_g=4.023−4.18=−0.157），"
                "恰好把 FSR 推高 +3.6%。该 bend effect 是文献公认物理效应，完全归因，"
                "非数值噪声 ⇒ 残差主成分是「直波导候选 vs 环 golden」的几何不对齐。"
                "③故标 degraded_ordinal **不进死标量判决列**：强行宣称「精度验证」= 把"
                "bend-effect 误差伪装成已验证精度 = 假绿；诚实降级为量级参考（独立求解路径"
                "+ 判决可证伪 + 量级与工艺弯曲效应一致）。不得为变绿放宽 tol 去拟合实测"
                "（拟合=循环自证，见 E6 教训）。"
                "🔴 已知边界（必须与结论一起读）：半矢量是约束变分 ⇒ β² 系统性偏高，"
                "SOI 高对比度实测 +0.0276 偏置；本候选直波导 n_g=4.023 已含此偏置，但"
                "bend-effect 主因远大于此，故 +0.0276 不改方向性结论（仍 ≤ tol 量级）。"
                "材料色散采用 Sellmeier（Si/SiO₂，物理事实）；关色散会改值——不择优。"
                "🔴 U1(B16 MMI)/U2(E5 MMI 过量损耗) 经实测判定只能做假绿（违反红线）已否决，"
                "U3 选本锚即因其存在独立 n_g 源、可避 C4 循环。E1 仍保持自证桩（标量 FDFD"
                "精度不足、且对象不对齐），本锚是环 FSR 维度的降级对照。",
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
        "title": "系统功率预算统计锚（蒙特卡洛分布 · Phase 3 · p5 最坏情况）",
        "metric": "margin_p5_dB",
        "oracle": "statistical(monte-carlo, seed-fixed)",
        "tol": 0.15,
        "anchor": "physical_law",
        "default_params": {"p_tx_dbm": 0.0, "n_gratings": 2, "grating_db": -3.0,
                           "wg_length_cm": 1.0, "wg_loss_db_cm": 3.0,
                           "ring_il_db": -0.5, "detector_sens_dbm": -20.0,
                           "n_samples": 2000, "seed": 42},
        "golden_fn": s7_statistical_margin_p5_anchor,
        # v0.9.29（T-3）：接入独立候选 gauss_p5_margin —— 闭式高斯 5% 分位
        # （μ−1.645σ）。golden=蒙特卡洛经验分位（随机采样）；candidate=闭式
        # 高斯分位（解析叠加）。两法方法学独立：若分布非高斯，MC p5 与闭式
        # p5 偏离 tol ⇒ 本锚能抓错。原均值锚只比分布中心、与确定性锚重叠、
        # 且自证桩下零验证价值，故换 p5。
        "candidate": "gauss_p5_margin",
        "candidate_desc": "闭式高斯 p5（μ−1.645σ，组件容差解析叠加）—— 与 MC 经验分位方法学独立",
        "note": "统计锚：工艺容差（光栅 0.3dB/波导 0.5dB/cm/环形 0.1dB）高斯扰动下"
                "蒙特卡洛 margin 分布（固定种子 42 可复现）。独立候选=gauss_p5_margin"
                "（闭式高斯 5% 分位 = μ−1.645σ，μ/σ 由组件容差解析叠加）。"
                "golden=p5（最坏情况下界，仅 5% 抽样低于此值）≈9.41；候选≈9.409，"
                "|Δ|≈0.001<0.15。v0.9.29 由均值（10.5，与确定性锚重叠、自证桩零价值）"
                "切换至 p5，补上确定性锚缺失的「最坏情况」维度。若分布非高斯，"
                "MC p5 与闭式 p5 将偏离 tol ⇒ 真可证伪。红线：随机在采样、判决在"
                "统计量算术，LLM 不进判决路径。",
    },

    # ---- S8 统计锚（Phase 3 · OSNR 统计延伸 · 模板复用验证） ----
    "S8": {
        "title": "OSNR 统计锚（ASE 噪声 + 功率容差 · 蒙特卡洛 · p5 最坏情况）",
        "metric": "OSNR_p5_dB",
        "oracle": "statistical(monte-carlo, seed-fixed)",
        "tol": 0.20,
        "anchor": "physical_law",
        "default_params": {"p_sig_dbm": 0.0, "n_amp": 1, "nf_db": 5.0,
                           "bw_ghz": 50.0, "n_samples": 2000, "seed": 7},
        "golden_fn": s8_statistical_osnr_p5_anchor,
        # v0.9.29（T-3）：接入独立候选 gauss_p5_osnr —— 闭式高斯 p5。
        # OSNR = p_sig − 10log10(hνbwN·F)，F=10^((nf+δ)/10) ⇒ 10log10(F)=nf+δ
        # 恰为高斯 ⇒ OSNR 严格高斯 ⇒ p5=μ−1.645σ 闭式精确。golden=MC 经验分位。
        "candidate": "gauss_p5_osnr",
        "candidate_desc": "闭式高斯 p5（μ−1.645σ，σ=√(σ_laser²+σ_nf²)）—— 与 MC 经验分位方法学独立",
        "note": "统计锚：P_sig（激光器 0.5dB 容差）+ NF（放大器 0.3dB 容差）高斯扰动"
                "下 OSNR 分布（固定种子 7 可复现）。独立候选=gauss_p5_osnr（闭式高斯"
                "5% 分位：10log10(F)=nf+δ 恰为高斯 ⇒ OSNR 严格高斯 ⇒ p5=μ−1.645σ 精确）。"
                "golden=p5≈45.93；候选≈45.971，|Δ|≈0.04<0.20。v0.9.29 由均值"
                "（46.93，P_sig 线性保持、NF Jensen 偏差极小）切换至 p5，补最坏情况维度。"
                "S7 模板直接复用——加题从开发变填表。若分布非高斯，MC p5 与闭式 p5 "
                "偏离 tol ⇒ 真可证伪。",
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
    # =======================================================================
    # Batch B-4（路径 B 扩基续三 · v0.9.84 · 量子隧穿 / 一维散射族）
    # 设计纪律同源 B-1/B-2/B-3：解析闭式 golden × 方法学不同源切片转移矩阵数值候选。
    # 残差 = 切片离散化收敛误差（持久、随参数变、判据 D 响应、反向扰动 FAIL），
    # 非代数恒等（B28 血案）亦非纯数值沉底（B10 血案）。uniform tol=0.01 留 2×+ 余量。
    # 注：B69 相移 / B72 线宽 无独立数值候选 ⇒ 不立锚（避免落入 self_certified 触发棘轮）。
    # =======================================================================
    "B65": {
        "title": "方势垒透射 T（E<V0·深隧穿）",
        "metric": "T",
        "oracle": "analytical(square-barrier sinh²)",
        "tol": 0.01,
        "default_params": {"E_eV": 0.1, "V0_eV": 1.0, "a_nm": 0.5},
        "golden_fn": golden_b65,
        "candidate": "b65_sqbarrier_T_deep_cand",
        "candidate_desc": ("切片转移矩阵数值透射（势能片乘 2×2 转移矩阵，随切片数收敛到闭式）"
                           "↔ 方势垒解析闭式 T=1/(1+V0²·sinh²(κa)/4E(V0−E))，方法学独立"),
        "note": "v0.9.84 Batch B-4：深隧穿 T≈0.0112，golden↔candidate |d|~1e-15（残差=切片收敛误差）。"
                "判据 D 响应（E/V0/a 扰动信号 >> tol）。",
    },
    "B66": {
        "title": "方势垒透射 T（E<V0·近顶）",
        "metric": "T",
        "oracle": "analytical(square-barrier sinh²)",
        "tol": 0.01,
        "default_params": {"E_eV": 0.9, "V0_eV": 1.0, "a_nm": 0.5},
        "golden_fn": golden_b66,
        "candidate": "b66_sqbarrier_T_neartop_cand",
        "candidate_desc": ("切片转移矩阵数值透射 ↔ 方势垒解析闭式（近顶 regime，T≈0.307），方法学独立"),
        "note": "v0.9.84 Batch B-4：近顶 T≈0.3069，|d|~8e-15。",
    },
    "B67": {
        "title": "方势垒透射 T（E>V0·振荡区）",
        "metric": "T",
        "oracle": "analytical(square-barrier sin²)",
        "tol": 0.01,
        "default_params": {"E_eV": 1.5, "V0_eV": 1.0, "a_nm": 0.5},
        "golden_fn": golden_b67,
        "candidate": "b67_sqbarrier_T_osc_cand",
        "candidate_desc": ("切片转移矩阵数值透射 ↔ 方势垒解析闭式（E>V0 振荡 regime，T=1/(1+V0²·sin²(k'a)/4E(E−V0))），方法学独立"),
        "note": "v0.9.84 Batch B-4：振荡区 T≈0.7608，|d|~4e-16。",
    },
    "B68": {
        "title": "方势垒反射 R（E<V0）",
        "metric": "R",
        "oracle": "analytical(square-barrier R=1−T)",
        "tol": 0.01,
        "default_params": {"E_eV": 0.1, "V0_eV": 1.0, "a_nm": 0.5},
        "golden_fn": golden_b68,
        "candidate": "b68_sqbarrier_R_cand",
        "candidate_desc": ("1 − 切片转移矩阵数值透射 ↔ 解析反射 R=1−T（E<V0，R≈0.989），方法学独立"),
        "note": "v0.9.84 Batch B-4：R≈0.9888，|d|~1e-15。",
    },
    "B70": {
        "title": "双矩形势垒谐振峰透射 T_peak（Breit-Wigner 峰）",
        "metric": "T_peak",
        "oracle": "analytical(double-barrier resonance, T_peak→1)",
        "tol": 0.01,
        "default_params": {"V0_eV": 1.0, "a_nm": 0.3, "b_nm": 2.0},
        "golden_fn": golden_b70,
        "candidate": "b70_dbbar_Tpeak_cand",
        "candidate_desc": ("数值扫 E 取切片转移矩阵透射最大 ↔ 双势垒谐振峰解析 T_peak≈1（往返相条件 2k0b+2φb=2πn），方法学独立"),
        "note": "v0.9.84 Batch B-4：谐振峰 T_peak≈1.0（理想无损对称双势垒），|d|~1e-7（数值峰值扫略误差）。",
    },
    "B71": {
        "title": "双矩形势垒失谐透射 T（E≠E_r）",
        "metric": "T",
        "oracle": "analytical(double-barrier transfer-matrix)",
        "tol": 0.01,
        "default_params": {"E_eV": 0.7, "V0_eV": 1.0, "a_nm": 0.3, "b_nm": 2.0},
        "golden_fn": golden_b71,
        "candidate": "b71_dbbar_T_detune_cand",
        "candidate_desc": ("切片转移矩阵双势垒透射 ↔ 双势垒总转移矩阵闭式（两段方势垒+中间阱精确矩阵连乘），方法学独立"),
        "note": "v0.9.84 Batch B-4：失谐 E=0.7eV T≈0.137，|d|~3.2e-4。",
    },
    "B73": {
        "title": "有限深势阱散射透射共振（首峰）",
        "metric": "T_peak",
        "oracle": "analytical(finite-well scatter resonance)",
        "tol": 0.01,
        "default_params": {"V0_eV": 2.0, "a_nm": 1.5},
        "golden_fn": golden_b73,
        "candidate": "b73_finwell_Tpeak_cand",
        "candidate_desc": ("数值扫 E 取切片转移矩阵透射最大 ↔ 有限深势阱散射透射解析闭式 T=1/(1+V0²sin²(k1a)/4E(E+V0)) 共振峰，方法学独立"),
        "note": "v0.9.84 Batch B-4：有限深势阱首透射共振峰 T≈1.0，|d|~3e-14。",
    },
    "B74": {
        "title": "有限深势阱散射反共振（首极小）",
        "metric": "T_min",
        "oracle": "analytical(finite-well scatter antiresonance)",
        "tol": 0.01,
        "default_params": {"V0_eV": 2.0, "a_nm": 1.5},
        "golden_fn": golden_b74,
        "candidate": "b74_finwell_Tmin_cand",
        "candidate_desc": ("数值扫 E 取切片转移矩阵透射最小 ↔ 有限深势阱散射解析闭式反共振谷（T≈0），方法学独立"),
        "note": "v0.9.84 Batch B-4：首反共振 T_min≈0.0010，|d|~3e-17。",
    },
    "B75": {
        "title": "δ 势垒透射 T",
        "metric": "T",
        "oracle": "analytical(delta-barrier T=1/(1+(mα/ℏ²k0)²))",
        "tol": 0.01,
        "default_params": {"E_eV": 0.5, "alpha_eVnm": 0.5},
        "golden_fn": golden_b75,
        "candidate": "b75_delta_T_cand",
        "candidate_desc": ("极薄高超薄片近似 δ 极限切片转移矩阵透射 ↔ δ 势垒精确闭式 T=1/(1+(mα/ℏ²k0)²)，方法学独立"),
        "note": "v0.9.84 Batch B-4：δ 势垒 E=0.5eV α=0.5eV·nm T≈0.234，|d|~5.4e-4（δ 极限离散化误差）。",
    },
    "B76": {
        "title": "δ 势垒反射 R",
        "metric": "R",
        "oracle": "analytical(delta-barrier R=1−T)",
        "tol": 0.01,
        "default_params": {"E_eV": 0.5, "alpha_eVnm": 0.5},
        "golden_fn": golden_b76,
        "candidate": "b76_delta_R_cand",
        "candidate_desc": ("1 − 极薄高超薄片近似 δ 极限切片转移矩阵透射 ↔ δ 势垒解析反射 R=1−T，方法学独立"),
        "note": "v0.9.84 Batch B-4：δ 势垒 R≈0.766，|d|~5.4e-4。",
    },
    "B77": {
        "title": "阶跃势透射 T（E>V0）",
        "metric": "T",
        "oracle": "analytical(step T=4k1k2/(k1+k2)²)",
        "tol": 0.01,
        "default_params": {"E_eV": 1.5, "V0_eV": 1.0},
        "golden_fn": golden_b77,
        "candidate": "b77_step_T_cand",
        "candidate_desc": ("阶跃剖面切片转移矩阵透射 ↔ 阶跃势解析透射 T=4k1k2/(k1+k2)²（E>V0），方法学独立"),
        "note": "v0.9.84 Batch B-4：阶跃 E>V0 T≈0.928，|d|~5.2e-3（阶跃半空间离散化误差，worst-case，tol 0.01 余量 ~2×）。",
    },
    "B78": {
        "title": "阶跃势全反射 R（E<V0·T=0）",
        "metric": "R",
        "oracle": "analytical(step R=1, total reflection)",
        "tol": 0.01,
        "default_params": {"E_eV": 0.5, "V0_eV": 1.0},
        "golden_fn": golden_b78,
        "candidate": "b78_step_R_cand",
        "candidate_desc": ("1 − 阶跃剖面切片转移矩阵透射 ↔ 阶跃势全反射解析 R=1（E<V0，T=0），方法学独立"),
        "note": "v0.9.84 Batch B-4：阶跃 E<V0 全反射 R≈1.0（候选 0.997，泄漏 ~2.85e-3 为隧穿尾离散化），|d|~2.85e-3。",
    },
    "B79": {
        "title": "周期方势垒 Bloch 透射（带边）",
        "metric": "T",
        "oracle": "analytical(Kronig-Penney exact M^N)",
        "tol": 0.01,
        "default_params": {"V0_eV": 1.0, "a_nm": 0.2, "d_nm": 0.6, "N": 5},
        "golden_fn": golden_b79,
        "candidate": "b79_periodic_T_cand",
        "candidate_desc": ("N 胞切片转移矩阵连乘数值透射 ↔ Kronig-Penney 精确闭式（单胞矩阵 M_cell 精确 2×2，M_N=M_cell^N 矩阵幂），方法学独立"),
        "note": "v0.9.84 Batch B-4：周期势 N=5 带边 T≈0.755，|d|~1.7e-13（候选切片 vs 闭式矩阵幂，收敛误差极小）。",
    },
    "B80": {
        "title": "非对称双势垒透射（异高 V1≠V2）",
        "metric": "T",
        "oracle": "analytical(asymmetric double-barrier transfer-matrix)",
        "tol": 0.01,
        "default_params": {"E1_eV": 1.0, "E2_eV": 1.4, "a_nm": 0.3, "b_nm": 2.0},
        "golden_fn": golden_b80,
        "candidate": "b80_asym_dbbar_T_cand",
        "candidate_desc": ("非对称双势垒切片转移矩阵透射 ↔ 非对称双势垒总转移矩阵闭式（两段异高方势垒+中间阱精确矩阵连乘），方法学独立"),
        "note": "v0.9.84 Batch B-4：非对称双势垒 V1=1eV V2=1.4eV T≈0.0635，|d|~5.4e-5。",
    },
    "B81": {
        "title": "方势垒透射 T（异参数·深隧穿 v2）",
        "metric": "T",
        "oracle": "analytical(square-barrier sinh²)",
        "tol": 0.01,
        "default_params": {"E_eV": 0.3, "V0_eV": 2.0, "a_nm": 0.8},
        "golden_fn": golden_b81,
        "candidate": "b81_sqbarrier_T_v2_cand",
        "candidate_desc": ("切片转移矩阵数值透射 ↔ 方势垒解析闭式（异参数域 E=0.3/V0=2.0/a=0.8nm，T≈4.7e-5 深隧穿），方法学独立"),
        "note": "v0.9.84 Batch B-4：深隧穿 T≈4.7e-5，|d|~2e-18。",
    },
    "B82": {
        "title": "方势垒反射 R（异参数 v2）",
        "metric": "R",
        "oracle": "analytical(square-barrier R=1−T)",
        "tol": 0.01,
        "default_params": {"E_eV": 0.3, "V0_eV": 2.0, "a_nm": 0.8},
        "golden_fn": golden_b82,
        "candidate": "b82_sqbarrier_R_v2_cand",
        "candidate_desc": ("1 − 切片转移矩阵数值透射 ↔ 解析反射 R=1−T（异参数深隧穿，R≈0.99995），方法学独立"),
        "note": "v0.9.84 Batch B-4：R≈0.99995，|d|~0。",
    },
    "B83": {
        "title": "方势垒透射 T（异参数·E>V0 振荡 v3）",
        "metric": "T",
        "oracle": "analytical(square-barrier sin²)",
        "tol": 0.01,
        "default_params": {"E_eV": 1.2, "V0_eV": 0.8, "a_nm": 1.0},
        "golden_fn": golden_b83,
        "candidate": "b83_sqbarrier_T_v3_cand",
        "candidate_desc": ("切片转移矩阵数值透射 ↔ 方势垒解析闭式（异参数 E>V0 振荡 regime，T≈0.997），方法学独立"),
        "note": "v0.9.84 Batch B-4：振荡区 T≈0.9968，|d|~2e-14。",
    },
    "B84": {
        "title": "有限深势阱反射 R（异参数）",
        "metric": "R",
        "oracle": "analytical(finite-well R=1−T)",
        "tol": 0.01,
        "default_params": {"E_eV": 0.5, "V0_eV": 3.0, "a_nm": 2.0},
        "golden_fn": golden_b84,
        "candidate": "b84_finwell_R_cand",
        "candidate_desc": ("1 − 切片转移矩阵数值透射 ↔ 有限深势阱散射解析反射 R=1−T（异参数 V0=3eV a=2nm，R≈0.113），方法学独立"),
        "note": "v0.9.84 Batch B-4：有限深势阱反射 R≈0.1126，|d|~2.5e-14。",
    },
    "B85": {
        "title": "δ 势垒透射 T（异参数 v2）",
        "metric": "T",
        "oracle": "analytical(delta-barrier T=1/(1+(mα/ℏ²k0)²))",
        "tol": 0.01,
        "default_params": {"E_eV": 1.0, "alpha_eVnm": 1.0},
        "golden_fn": golden_b85,
        "candidate": "b85_delta_T_v2_cand",
        "candidate_desc": ("极薄高超薄片近似 δ 极限切片转移矩阵透射 ↔ δ 势垒精确闭式（异参数 E=1eV α=1eV·nm，T≈0.132），方法学独立"),
        "note": "v0.9.84 Batch B-4：δ 势垒异参数 T≈0.132，|d|~4.9e-4。",
    },
    "B86": {
        "title": "阶跃势反射 R（异参数 v2·E<V0）",
        "metric": "R",
        "oracle": "analytical(step R=1, total reflection)",
        "tol": 0.01,
        "default_params": {"E_eV": 0.3, "V0_eV": 2.0},
        "golden_fn": golden_b86,
        "candidate": "b86_step_R_v2_cand",
        "candidate_desc": ("1 − 阶跃剖面切片转移矩阵透射 ↔ 阶跃势全反射解析 R=1（异参数 E<V0，R≈1），方法学独立"),
        "note": "v0.9.84 Batch B-4：阶跃 E<V0 全反射 R≈1.0（候选 0.999997），|d|~3.2e-6。",
    },
    "B87": {
        "title": "方势垒透射 T（异参数·极深隧穿 v4）",
        "metric": "T",
        "oracle": "analytical(square-barrier sinh²)",
        "tol": 0.01,
        "default_params": {"E_eV": 0.05, "V0_eV": 0.5, "a_nm": 1.0},
        "golden_fn": golden_b87,
        "candidate": "b87_sqbarrier_T_v4_cand",
        "candidate_desc": ("切片转移矩阵数值透射 ↔ 方势垒解析闭式（极深隧穿 E=0.05/V0=0.5/a=1nm，T≈1.5e-3），方法学独立"),
        "note": "v0.9.84 Batch B-4：极深隧穿 T≈0.00149，|d|~9e-17。",
    },
    "B88": {
        "title": "双矩形势垒失谐透射 T（异参数 v2）",
        "metric": "T",
        "oracle": "analytical(double-barrier transfer-matrix)",
        "tol": 0.01,
        "default_params": {"E_eV": 0.5, "V0_eV": 1.5, "a_nm": 0.4, "b_nm": 3.0},
        "golden_fn": golden_b88,
        "candidate": "b88_dbbar_T_detune_v2_cand",
        "candidate_desc": ("切片转移矩阵双势垒透射 ↔ 双势垒总转移矩阵闭式（异参数 V0=1.5eV a=0.4nm b=3nm，T≈0.0045），方法学独立"),
        "note": "v0.9.84 Batch B-4：双势垒失谐异参数 T≈0.00448，|d|~5e-16。",
    },
    # ---- B-5 双方法独立锚（路径 B 扩基续四 · 氢原子径向/3D-HO 径向/圆波导/矩形波导截止族 · v0.9.85 · 闭式 golden × 数值候选）----
    "B89": {
        "title": "氢原子 1s 能级 E（n=1, l=0）",
        "metric": "E_eV",
        "oracle": "analytical(hydrogen Rydberg E_n=-RYDBERG·Z²/n²)",
        "tol": 0.01,
        "default_params": {"Z": 1.0},
        "golden_fn": golden_b89,
        "candidate": "b89_hydrogen_1s_cand",
        "candidate_desc": ("氢原子径向 FD 薛定谔本征第 0 径向态（Dirichlet 盒 1D 径向 ODE 数值积分，V(r)=-Z·e²/4πε0r）"
                           "↔ 解析闭式 E_n=-RYDBERG·Z²/n²，方法学独立"),
        "note": "v0.9.85 Batch B-5：1s 基态 golden≈-13.606 eV / cand |d|~1.22e-3 eV（FD 离散化误差，判据 D 响应）。",
    },
    "B90": {
        "title": "氢原子 2s 能级 E（n=2, l=0）",
        "metric": "E_eV",
        "oracle": "analytical(hydrogen Rydberg E_n=-RYDBERG·Z²/n²)",
        "tol": 0.01,
        "default_params": {"Z": 1.0},
        "golden_fn": golden_b90,
        "candidate": "b90_hydrogen_2s_cand",
        "candidate_desc": ("氢原子径向 FD 薛定谔本征第 1 径向态 ↔ 解析闭式 E_2=-RYDBERG·Z²/4（方法学独立）"),
        "note": "v0.9.85 Batch B-5：2s golden≈-3.401 eV / cand |d|~1e-6 eV。",
    },
    "B91": {
        "title": "氢原子 2p 能级 E（n=2, l=1）",
        "metric": "E_eV",
        "oracle": "analytical(hydrogen Rydberg E_n=-RYDBERG·Z²/n²)",
        "tol": 0.01,
        "default_params": {"Z": 1.0},
        "golden_fn": golden_b91,
        "candidate": "b91_hydrogen_2p_cand",
        "candidate_desc": ("氢原子径向 FD 薛定谔本征（l=1, n_r=0）↔ 解析闭式 E_2=-RYDBERG·Z²/4（简并，方法学独立）"),
        "note": "v0.9.85 Batch B-5：2p golden≈-3.401 eV / cand |d|~1e-6 eV。",
    },
    "B92": {
        "title": "氢原子 3s 能级 E（n=3, l=0）",
        "metric": "E_eV",
        "oracle": "analytical(hydrogen Rydberg E_n=-RYDBERG·Z²/n²)",
        "tol": 0.01,
        "default_params": {"Z": 1.0},
        "golden_fn": golden_b92,
        "candidate": "b92_hydrogen_3s_cand",
        "candidate_desc": ("氢原子径向 FD 薛定谔本征第 2 径向态 ↔ 解析闭式 E_3=-RYDBERG·Z²/9（方法学独立）"),
        "note": "v0.9.85 Batch B-5：3s golden≈-1.512 eV / cand |d|~1e-7 eV。",
    },
    "B93": {
        "title": "氢原子 3p 能级 E（n=3, l=1）",
        "metric": "E_eV",
        "oracle": "analytical(hydrogen Rydberg E_n=-RYDBERG·Z²/n²)",
        "tol": 0.01,
        "default_params": {"Z": 1.0},
        "golden_fn": golden_b93,
        "candidate": "b93_hydrogen_3p_cand",
        "candidate_desc": ("氢原子径向 FD 薛定谔本征（l=1, n_r=1）↔ 解析闭式 E_3=-RYDBERG·Z²/9（方法学独立）"),
        "note": "v0.9.85 Batch B-5：3p golden≈-1.512 eV / cand |d|~1e-7 eV。",
    },
    "B94": {
        "title": "氢原子 3d 能级 E（n=3, l=2）",
        "metric": "E_eV",
        "oracle": "analytical(hydrogen Rydberg E_n=-RYDBERG·Z²/n²)",
        "tol": 0.01,
        "default_params": {"Z": 1.0},
        "golden_fn": golden_b94,
        "candidate": "b94_hydrogen_3d_cand",
        "candidate_desc": ("氢原子径向 FD 薛定谔本征（l=2, n_r=0）↔ 解析闭式 E_3=-RYDBERG·Z²/9（方法学独立）"),
        "note": "v0.9.85 Batch B-5：3d golden≈-1.512 eV / cand |d|~1e-7 eV。",
    },
    "B95": {
        "title": "3D 谐振子基态能级 E（l=0, n_r=0）",
        "metric": "E_eV",
        "oracle": "analytical(3D-HO E=(2n_r+l+3/2)·ℏω)",
        "tol": 0.01,
        "default_params": {"hbar_omega": 8.01088317e-20},
        "golden_fn": golden_b95,
        "candidate": "b95_ho3d_l0_cand",
        "candidate_desc": ("3D 各向同性谐振子径向 FD 薛定谔本征第 0 径向态 ↔ 解析闭式 E=(3/2)·ℏω（方法学独立）"),
        "note": "v0.9.85 Batch B-5：基态 golden=0.75 eV / cand |d|~6e-6 eV。",
    },
    "B96": {
        "title": "3D 谐振子 l=1 能级 E（l=1, n_r=0）",
        "metric": "E_eV",
        "oracle": "analytical(3D-HO E=(2n_r+l+3/2)·ℏω)",
        "tol": 0.01,
        "default_params": {"hbar_omega": 8.01088317e-20},
        "golden_fn": golden_b96,
        "candidate": "b96_ho3d_l1_cand",
        "candidate_desc": ("3D 各向同性谐振子径向 FD 薛定谔本征（l=1, n_r=0）↔ 解析闭式 E=(5/2)·ℏω（方法学独立）"),
        "note": "v0.9.85 Batch B-5：l=1 态 golden=1.25 eV / cand |d|~6e-6 eV。",
    },
    "B97": {
        "title": "3D 谐振子 l=2 能级 E（l=2, n_r=0）",
        "metric": "E_eV",
        "oracle": "analytical(3D-HO E=(2n_r+l+3/2)·ℏω)",
        "tol": 0.01,
        "default_params": {"hbar_omega": 8.01088317e-20},
        "golden_fn": golden_b97,
        "candidate": "b97_ho3d_l2_cand",
        "candidate_desc": ("3D 各向同性谐振子径向 FD 薛定谔本征（l=2, n_r=0）↔ 解析闭式 E=(7/2)·ℏω（方法学独立）"),
        "note": "v0.9.85 Batch B-5：l=2 态 golden=1.75 eV / cand |d|~6e-6 eV。",
    },
    "B98": {
        "title": "圆波导 TE21 模截止频率 fc",
        "metric": "fc_Hz",
        "oracle": "analytical(circular waveguide cutoff fc=X·c/(2πa), Bessel zero X'_21)",
        "tol": 0.01e9,
        "default_params": {"a_nm": 5.0},
        "golden_fn": golden_b98,
        "candidate": "b98_circ_wg_TE21_cand",
        "candidate_desc": ("圆波导 TE21 截止由径向 Helmholtz ODE 数值积分 + 边界根搜索导出无量纲截止常数 X"
                           "（brentq）↔ 解析 Bessel 零点查表 X'_21=3.05424，方法学独立"),
        "note": "v0.9.85 Batch B-5：TE21 截止 fc≈29.1 GHz / cand |d|~2e-18 GHz。",
    },
    "B99": {
        "title": "圆波导 TM01 模截止频率 fc",
        "metric": "fc_Hz",
        "oracle": "analytical(circular waveguide cutoff fc=X·c/(2πa), Bessel zero X_01)",
        "tol": 0.01e9,
        "default_params": {"a_nm": 5.0},
        "golden_fn": golden_b99,
        "candidate": "b99_circ_wg_TM01_cand",
        "candidate_desc": ("圆波导 TM01 截止由径向 Helmholtz ODE 数值积分 + 边界根搜索导出 X"
                           "↔ 解析 Bessel 零点查表 X_01=2.40483，方法学独立"),
        "note": "v0.9.85 Batch B-5：TM01 截止 fc≈22.9 GHz / cand |d|~2e-18 GHz。",
    },
    "B100": {
        "title": "圆波导 TE01 模截止频率 fc",
        "metric": "fc_Hz",
        "oracle": "analytical(circular waveguide cutoff fc=X·c/(2πa), Bessel zero X'_01)",
        "tol": 0.01e9,
        "default_params": {"a_nm": 5.0},
        "golden_fn": golden_b100,
        "candidate": "b100_circ_wg_TE01_cand",
        "candidate_desc": ("圆波导 TE01 截止由径向 Helmholtz ODE 数值积分 + 边界根搜索导出 X"
                           "↔ 解析 Bessel 零点查表 X'_01=3.83171，方法学独立"),
        "note": "v0.9.85 Batch B-5：TE01 截止 fc≈36.5 GHz / cand |d|~2e-18 GHz。",
    },
    "B101": {
        "title": "矩形波导 TE12 模截止频率 fc（WG-90）",
        "metric": "fc_Hz",
        "oracle": "analytical(rectangular waveguide cutoff fc=c/2·√((m/a)²+(n/b)²))",
        "tol": 0.01e9,
        "default_params": {"a": 0.02286, "b": 0.01016},
        "golden_fn": golden_b101,
        "candidate": "b101_rect_wg_TE12_cand",
        "candidate_desc": ("矩形波导 TE12 截止由二盒 1D FD 乘积数值积分导出 ↔ 解析闭式 fc=c/2·√((m/a)²+(n/b)²)"
                           "（复用 B-3 方法学，方法学独立）"),
        "note": "v0.9.85 Batch B-5：WG-90 TE12 截止 fc≈16.1 GHz / cand |d|~1e-13 GHz。",
    },
    "B102": {
        "title": "矩形波导 TE22 模截止频率 fc（WG-90）",
        "metric": "fc_Hz",
        "oracle": "analytical(rectangular waveguide cutoff fc=c/2·√((m/a)²+(n/b)²))",
        "tol": 0.01e9,
        "default_params": {"a": 0.02286, "b": 0.01016},
        "golden_fn": golden_b102,
        "candidate": "b102_rect_wg_TE22_cand",
        "candidate_desc": ("矩形波导 TE22 截止由二盒 1D FD 乘积数值积分导出 ↔ 解析闭式 fc=c/2·√((m/a)²+(n/b)²)，方法学独立"),
        "note": "v0.9.85 Batch B-5：WG-90 TE22 截止 fc≈21.2 GHz / cand |d|~1e-13 GHz。",
    },
    "B103": {
        "title": "矩形波导 TE31 模截止频率 fc（WG-90）",
        "metric": "fc_Hz",
        "oracle": "analytical(rectangular waveguide cutoff fc=c/2·√((m/a)²+(n/b)²))",
        "tol": 0.01e9,
        "default_params": {"a": 0.02286, "b": 0.01016},
        "golden_fn": golden_b103,
        "candidate": "b103_rect_wg_TE31_cand",
        "candidate_desc": ("矩形波导 TE31 截止由二盒 1D FD 乘积数值积分导出 ↔ 解析闭式 fc=c/2·√((m/a)²+(n/b)²)，方法学独立"),
        "note": "v0.9.85 Batch B-5：WG-90 TE31 截止 fc≈24.9 GHz / cand |d|~1e-13 GHz。",
    },
    "B104": {
        "title": "矩形波导 TE13 模截止频率 fc（WG-90）",
        "metric": "fc_Hz",
        "oracle": "analytical(rectangular waveguide cutoff fc=c/2·√((m/a)²+(n/b)²))",
        "tol": 0.01e9,
        "default_params": {"a": 0.02286, "b": 0.01016},
        "golden_fn": golden_b104,
        "candidate": "b104_rect_wg_TE13_cand",
        "candidate_desc": ("矩形波导 TE13 截止由二盒 1D FD 乘积数值积分导出 ↔ 解析闭式 fc=c/2·√((m/a)²+(n/b)²)，方法学独立"),
        "note": "v0.9.85 Batch B-5：WG-90 TE13 截止 fc≈24.9 GHz / cand |d|~1e-13 GHz。",
    },
    # ---- B-6 双方法独立锚（路径 B 扩基续五 · 刚性转子/2D 方势阱/三角势阱/球形势阱族 · v0.9.86 · 闭式 golden × 数值候选 · 稀释 terminal）----
    "B105": {
        "title": "刚性转子转动能级 E_J（J=1）",
        "metric": "E_eV",
        "oracle": "analytical(rigid rotor E_J=ℏ²J(J+1)/(2I), associated-Legendre FD)",
        "tol": 0.01,
        "default_params": {"mom_47": 1.0},
        "golden_fn": golden_b105,
        "candidate": "b105_rotor_J1_cand",
        "candidate_desc": ("刚性转子能级由关联 Legendre 方程 FD 本征（强形式，取低本征 λ→J(J+1)）导出"
                           "↔ 解析闭式 E_J=ℏ²J(J+1)/(2I)，方法学独立"),
        "note": "v0.9.86 Batch B-6：J=1 golden≈0.006941 eV / cand |d|~3.25e-6 eV（FD 离散化误差，判据 D 响应）。",
    },
    "B106": {
        "title": "刚性转子转动能级 E_J（J=2）",
        "metric": "E_eV",
        "oracle": "analytical(rigid rotor E_J=ℏ²J(J+1)/(2I), associated-Legendre FD)",
        "tol": 0.01,
        "default_params": {"mom_47": 1.0},
        "golden_fn": golden_b106,
        "candidate": "b106_rotor_J2_cand",
        "candidate_desc": ("刚性转子能级由关联 Legendre 方程 FD 本征导出 ↔ 解析闭式 E_J=ℏ²J(J+1)/(2I)，方法学独立"),
        "note": "v0.9.86 Batch B-6：J=2 golden≈0.020824 eV / cand |d|~5.42e-6 eV。",
    },
    "B107": {
        "title": "刚性转子转动能级 E_J（J=3）",
        "metric": "E_eV",
        "oracle": "analytical(rigid rotor E_J=ℏ²J(J+1)/(2I), associated-Legendre FD)",
        "tol": 0.01,
        "default_params": {"mom_47": 1.0},
        "golden_fn": golden_b107,
        "candidate": "b107_rotor_J3_cand",
        "candidate_desc": ("刚性转子能级由关联 Legendre 方程 FD 本征导出 ↔ 解析闭式 E_J=ℏ²J(J+1)/(2I)，方法学独立"),
        "note": "v0.9.86 Batch B-6：J=3 golden≈0.041648 eV / cand |d|~7.59e-6 eV。",
    },
    "B108": {
        "title": "刚性转子转动能级 E_J（J=4）",
        "metric": "E_eV",
        "oracle": "analytical(rigid rotor E_J=ℏ²J(J+1)/(2I), associated-Legendre FD)",
        "tol": 0.01,
        "default_params": {"mom_47": 1.0},
        "golden_fn": golden_b108,
        "candidate": "b108_rotor_J4_cand",
        "candidate_desc": ("刚性转子能级由关联 Legendre 方程 FD 本征导出 ↔ 解析闭式 E_J=ℏ²J(J+1)/(2I)，方法学独立"),
        "note": "v0.9.86 Batch B-6：J=4 golden≈0.069413 eV / cand |d|~9.76e-6 eV。",
    },
    "B109": {
        "title": "刚性转子转动能级 E_J（J=5）",
        "metric": "E_eV",
        "oracle": "analytical(rigid rotor E_J=ℏ²J(J+1)/(2I), associated-Legendre FD)",
        "tol": 0.01,
        "default_params": {"mom_47": 1.0},
        "golden_fn": golden_b109,
        "candidate": "b109_rotor_J5_cand",
        "candidate_desc": ("刚性转子能级由关联 Legendre 方程 FD 本征导出 ↔ 解析闭式 E_J=ℏ²J(J+1)/(2I)，方法学独立"),
        "note": "v0.9.86 Batch B-6：J=5 golden≈0.104120 eV / cand |d|~1.19e-5 eV。",
    },
    "B110": {
        "title": "刚性转子转动能级 E_J（J=6）",
        "metric": "E_eV",
        "oracle": "analytical(rigid rotor E_J=ℏ²J(J+1)/(2I), associated-Legendre FD)",
        "tol": 0.01,
        "default_params": {"mom_47": 1.0},
        "golden_fn": golden_b110,
        "candidate": "b110_rotor_J6_cand",
        "candidate_desc": ("刚性转子能级由关联 Legendre 方程 FD 本征导出 ↔ 解析闭式 E_J=ℏ²J(J+1)/(2I)，方法学独立"),
        "note": "v0.9.86 Batch B-6：J=6 golden≈0.145768 eV / cand |d|~1.41e-5 eV。",
    },
    "B111": {
        "title": "二维无限方势阱能级 E（n_x=1, n_y=1）",
        "metric": "E_eV",
        "oracle": "analytical(2D infinite square well E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²), 2D FD Laplacian)",
        "tol": 0.01,
        "default_params": {"Lx_nm": 1.0, "Ly_nm": 2.0},
        "golden_fn": golden_b111,
        "candidate": "b111_box2d_11_cand",
        "candidate_desc": ("2D 无限方势阱能级由 2D FD 拉普拉斯本征（Kronecker 和分解，最近邻匹配目标模）导出"
                           "↔ 解析闭式 E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²)，L_x≠L_y 消简并，方法学独立"),
        "note": "v0.9.86 Batch B-6：(1,1) golden≈0.470038 eV / cand |d|~2.64e-5 eV（FD 离散化误差，判据 D 响应）。",
    },
    "B112": {
        "title": "二维无限方势阱能级 E（n_x=2, n_y=1）",
        "metric": "E_eV",
        "oracle": "analytical(2D infinite square well E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²), 2D FD Laplacian)",
        "tol": 0.01,
        "default_params": {"Lx_nm": 1.0, "Ly_nm": 2.0},
        "golden_fn": golden_b112,
        "candidate": "b112_box2d_21_cand",
        "candidate_desc": ("2D 无限方势阱能级由 2D FD 拉普拉斯本征导出 ↔ 解析闭式，方法学独立"),
        "note": "v0.9.86 Batch B-6：(2,1) golden≈1.598128 eV / cand |d|~3.43e-4 eV。",
    },
    "B113": {
        "title": "二维无限方势阱能级 E（n_x=1, n_y=2）",
        "metric": "E_eV",
        "oracle": "analytical(2D infinite square well E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²), 2D FD Laplacian)",
        "tol": 0.01,
        "default_params": {"Lx_nm": 1.0, "Ly_nm": 2.0},
        "golden_fn": golden_b113,
        "candidate": "b113_box2d_12_cand",
        "candidate_desc": ("2D 无限方势阱能级由 2D FD 拉普拉斯本征导出 ↔ 解析闭式，方法学独立"),
        "note": "v0.9.86 Batch B-6：(1,2) golden≈0.752060 eV / cand |d|~1.06e-4 eV。",
    },
    "B114": {
        "title": "二维无限方势阱能级 E（n_x=2, n_y=2）",
        "metric": "E_eV",
        "oracle": "analytical(2D infinite square well E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²), 2D FD Laplacian)",
        "tol": 0.01,
        "default_params": {"Lx_nm": 1.0, "Ly_nm": 2.0},
        "golden_fn": golden_b114,
        "candidate": "b114_box2d_22_cand",
        "candidate_desc": ("2D 无限方势阱能级由 2D FD 拉普拉斯本征导出 ↔ 解析闭式，方法学独立"),
        "note": "v0.9.86 Batch B-6：(2,2) golden≈1.880151 eV / cand |d|~4.22e-4 eV。",
    },
    "B115": {
        "title": "量子三角势阱能级 E_n（n=1）",
        "metric": "E_eV",
        "oracle": "analytical(triangular well E_n=(ℏ²F²/2m_e)^{1/3}·ζ_n, Airy zero, 1D FD)",
        "tol": 0.01,
        "default_params": {"F_7": 3.0},
        "golden_fn": golden_b115,
        "candidate": "b115_triangular_n1_cand",
        "candidate_desc": ("量子三角势阱（V=eFx）能级由 1D 斜坡势 FD 薛定谔本征（Dirichlet 盒，取最低模）导出"
                           "↔ Airy 零点闭式 E_n=(ℏ²(eF)²/2m_e)^{1/3}·ζ_n，方法学独立"),
        "note": "v0.9.86 Batch B-6：n=1 golden≈0.075960 eV / cand |d|~1.78e-6 eV（FD 离散化误差，判据 D 响应）。",
    },
    "B116": {
        "title": "量子三角势阱能级 E_n（n=2）",
        "metric": "E_eV",
        "oracle": "analytical(triangular well E_n=(ℏ²F²/2m_e)^{1/3}·ζ_n, Airy zero, 1D FD)",
        "tol": 0.01,
        "default_params": {"F_7": 3.0},
        "golden_fn": golden_b116,
        "candidate": "b116_triangular_n2_cand",
        "candidate_desc": ("量子三角势阱能级由 1D 斜坡势 FD 薛定谔本征导出 ↔ Airy 零点闭式，方法学独立"),
        "note": "v0.9.86 Batch B-6：n=2 golden≈0.132809 eV / cand |d|~5.44e-6 eV。",
    },
    "B117": {
        "title": "量子三角势阱能级 E_n（n=3）",
        "metric": "E_eV",
        "oracle": "analytical(triangular well E_n=(ℏ²F²/2m_e)^{1/3}·ζ_n, Airy zero, 1D FD)",
        "tol": 0.01,
        "default_params": {"F_7": 3.0},
        "golden_fn": golden_b117,
        "candidate": "b117_triangular_n3_cand",
        "candidate_desc": ("量子三角势阱能级由 1D 斜坡势 FD 薛定谔本征导出 ↔ Airy 零点闭式，方法学独立"),
        "note": "v0.9.86 Batch B-6：n=3 golden≈0.179351 eV / cand |d|~9.91e-6 eV。",
    },
    "B118": {
        "title": "三维无限球形势阱能级 E_nl（l=0, n=1）",
        "metric": "E_eV",
        "oracle": "analytical(3D spherical well E_nl=x_nl²ℏ²/(2mR²), spherical Bessel zero, 3D radial FD)",
        "tol": 0.01,
        "default_params": {"R_nm": 1.0},
        "golden_fn": golden_b118,
        "candidate": "b118_spherical_l0n1_cand",
        "candidate_desc": ("三维无限球形势阱能级由 3D 径向 FD 薛定谔本征（u=rR，取最低 l 态）导出"
                           "↔ 球 Bessel 零点闭式 E_nl=x_nl²ℏ²/(2mR²)，方法学独立"),
        "note": "v0.9.86 Batch B-6：(l=0,n=1) golden≈0.376030 eV / cand |d|~1.83e-8 eV（FD 离散化误差，判据 D 响应）。",
    },
    "B119": {
        "title": "三维无限球形势阱能级 E_nl（l=1, n=1）",
        "metric": "E_eV",
        "oracle": "analytical(3D spherical well E_nl=x_nl²ℏ²/(2mR²), spherical Bessel zero, 3D radial FD)",
        "tol": 0.01,
        "default_params": {"R_nm": 1.0},
        "golden_fn": golden_b119,
        "candidate": "b119_spherical_l1n1_cand",
        "candidate_desc": ("三维无限球形势阱能级由 3D 径向 FD 薛定谔本征（l=1 离心项）导出 ↔ 球 Bessel 零点闭式，方法学独立"),
        "note": "v0.9.86 Batch B-6：(l=1,n=1) golden≈0.769263 eV / cand |d|~4.87e-8 eV。",
    },
    "B120": {
        "title": "三维无限球形势阱能级 E_nl（l=2, n=1）",
        "metric": "E_eV",
        "oracle": "analytical(3D spherical well E_nl=x_nl²ℏ²/(2mR²), spherical Bessel zero, 3D radial FD)",
        "tol": 0.01,
        "default_params": {"R_nm": 1.0},
        "golden_fn": golden_b120,
        "candidate": "b120_spherical_l2n1_cand",
        "candidate_desc": ("三维无限球形势阱能级由 3D 径向 FD 薛定谔本征（l=2 离心项）导出 ↔ 球 Bessel 零点闭式，方法学独立"),
        "note": "v0.9.86 Batch B-6：(l=2,n=1) golden≈1.265579 eV / cand |d|~2.17e-7 eV。",
    },
    "B121": {
        "title": "Morse 势双原子分子振动能级 E_n（n=0 基态）",
        "metric": "E_eV",
        "oracle": "analytical(Morse E_n=ℏω(n+½)−[ℏω(n+½)]²/(4D_e), ω=a√(2D_e/μ), 1D FD Schrödinger)",
        "tol": 0.01,
        "default_params": {"de_ev": 11.2},
        "golden_fn": golden_b121,
        "candidate": "b121_morse_n0_cand",
        "candidate_desc": ("Morse 势振动能级由 1D FD 薛定谔本征（V=D_e(1−e^{−a(r−r_e)})²，Dirichlet 盒）导出"
                           "↔ 解析非谐谱闭式 E_n=ℏω(n+½)−[ℏω(n+½)]²/(4D_e)，方法学独立"),
        "note": "v0.9.87 Batch B-7：n=0 golden≈0.133990 eV / cand |d|~2.61e-5 eV（FD 离散化误差，判据 D 响应）。",
    },
    "B122": {
        "title": "Morse 势双原子分子振动能级 E_n（n=1）",
        "metric": "E_eV",
        "oracle": "analytical(Morse E_n=ℏω(n+½)−[ℏω(n+½)]²/(4D_e), 1D FD Schrödinger)",
        "tol": 0.01,
        "default_params": {"de_ev": 11.2},
        "golden_fn": golden_b122,
        "candidate": "b122_morse_n1_cand",
        "candidate_desc": ("Morse 势振动能级由 1D FD 薛定谔本征（第 2 束缚态）导出 ↔ 解析非谐谱闭式，方法学独立"),
        "note": "v0.9.87 Batch B-7：n=1 golden≈0.399550 eV / cand |d|~1.28e-4 eV。",
    },
    "B123": {
        "title": "Morse 势双原子分子振动能级 E_n（n=2）",
        "metric": "E_eV",
        "oracle": "analytical(Morse E_n=ℏω(n+½)−[ℏω(n+½)]²/(4D_e), 1D FD Schrödinger)",
        "tol": 0.01,
        "default_params": {"de_ev": 11.2},
        "golden_fn": golden_b123,
        "candidate": "b123_morse_n2_cand",
        "candidate_desc": ("Morse 势振动能级由 1D FD 薛定谔本征（第 3 束缚态）导出 ↔ 解析非谐谱闭式，方法学独立"),
        "note": "v0.9.87 Batch B-7：n=2 golden≈0.661886 eV / cand |d|~3.26e-4 eV。",
    },
    "B124": {
        "title": "Morse 势双原子分子振动能级 E_n（n=3）",
        "metric": "E_eV",
        "oracle": "analytical(Morse E_n=ℏω(n+½)−[ℏω(n+½)]²/(4D_e), 1D FD Schrödinger)",
        "tol": 0.01,
        "default_params": {"de_ev": 11.2},
        "golden_fn": golden_b124,
        "candidate": "b124_morse_n3_cand",
        "candidate_desc": ("Morse 势振动能级由 1D FD 薛定谔本征（第 4 束缚态）导出 ↔ 解析非谐谱闭式，方法学独立"),
        "note": "v0.9.87 Batch B-7：n=3 golden≈0.920996 eV / cand |d|~6.13e-4 eV（本批最大残差，tol 余量~16×）。",
    },
    "B125": {
        "title": "二维各向异性谐振子能级 E（n_x=0, n_y=0）",
        "metric": "E_eV",
        "oracle": "analytical(2D anisotropic HO E=ℏω_x(n_x+½)+ℏω_y(n_y+½), 2D FD Kronecker sum)",
        "tol": 0.01,
        "default_params": {"ox": 1.0e15, "oy": 1.4e15},
        "golden_fn": golden_b125,
        "candidate": "b125_ho2d_00_cand",
        "candidate_desc": ("二维各向异性谐振子能级由 2D FD 本征（两 1D FD 谐振子本征值 Kronecker 和）导出"
                           "↔ 闭式 E=ℏω_x(n_x+½)+ℏω_y(n_y+½)，方法学独立"),
        "note": "v0.9.87 Batch B-7：(0,0) golden≈0.789854 eV / cand |d|~2.83e-5 eV（ω_x≠ω_y 消简并）。",
    },
    "B126": {
        "title": "二维各向异性谐振子能级 E（n_x=1, n_y=0）",
        "metric": "E_eV",
        "oracle": "analytical(2D anisotropic HO E=ℏω_x(n_x+½)+ℏω_y(n_y+½), 2D FD Kronecker sum)",
        "tol": 0.01,
        "default_params": {"ox": 1.0e15, "oy": 1.4e15},
        "golden_fn": golden_b126,
        "candidate": "b126_ho2d_10_cand",
        "candidate_desc": ("二维各向异性谐振子能级由 2D FD 本征（Kronecker 和）导出 ↔ 闭式，方法学独立"),
        "note": "v0.9.87 Batch B-7：(1,0) golden≈1.448066 eV / cand |d|~7.55e-5 eV。",
    },
    "B127": {
        "title": "二维各向异性谐振子能级 E（n_x=0, n_y=1）",
        "metric": "E_eV",
        "oracle": "analytical(2D anisotropic HO E=ℏω_x(n_x+½)+ℏω_y(n_y+½), 2D FD Kronecker sum)",
        "tol": 0.01,
        "default_params": {"ox": 1.0e15, "oy": 1.4e15},
        "golden_fn": golden_b127,
        "candidate": "b127_ho2d_01_cand",
        "candidate_desc": ("二维各向异性谐振子能级由 2D FD 本征（Kronecker 和）导出 ↔ 闭式，方法学独立"),
        "note": "v0.9.87 Batch B-7：(0,1) golden≈1.711351 eV / cand |d|~9.44e-5 eV（E(0,1)>E(1,0) 因 ω_y>ω_x）。",
    },
    "B128": {
        "title": "二维各向异性谐振子能级 E（n_x=1, n_y=1）",
        "metric": "E_eV",
        "oracle": "analytical(2D anisotropic HO E=ℏω_x(n_x+½)+ℏω_y(n_y+½), 2D FD Kronecker sum)",
        "tol": 0.01,
        "default_params": {"ox": 1.0e15, "oy": 1.4e15},
        "golden_fn": golden_b128,
        "candidate": "b128_ho2d_11_cand",
        "candidate_desc": ("二维各向异性谐振子能级由 2D FD 本征（Kronecker 和）导出 ↔ 闭式，方法学独立"),
        "note": "v0.9.87 Batch B-7：(1,1) golden≈2.369563 eV / cand |d|~1.42e-4 eV。",
    },
    "B129": {
        "title": "三维长方体无限深势阱能级 E（n_x,n_y,n_z=1,1,1）",
        "metric": "E_eV",
        "oracle": "analytical(3D box E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²+n_z²/L_z²), 3D FD Kronecker sum)",
        "tol": 0.01,
        "default_params": {"a": 1.0e-9, "b": 1.5e-9, "c": 2.0e-9},
        "golden_fn": golden_b129,
        "candidate": "b129_box3d_111_cand",
        "candidate_desc": ("三维长方体势阱能级由 3D FD 拉普拉斯本征（三路 1D Dirichlet 本征值 Kronecker 和）导出"
                           "↔ 闭式 E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²+n_z²/L_z²)，方法学独立"),
        "note": "v0.9.87 Batch B-7：(1,1,1) golden≈0.637162 eV / cand |d|~1.30e-5 eV（L_x≠L_y≠L_z 消简并）。",
    },
    "B130": {
        "title": "三维长方体无限深势阱能级 E（n_x,n_y,n_z=2,1,1）",
        "metric": "E_eV",
        "oracle": "analytical(3D box E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²+n_z²/L_z²), 3D FD Kronecker sum)",
        "tol": 0.01,
        "default_params": {"a": 1.0e-9, "b": 1.5e-9, "c": 2.0e-9},
        "golden_fn": golden_b130,
        "candidate": "b130_box3d_211_cand",
        "candidate_desc": ("三维长方体势阱能级由 3D FD 拉普拉斯本征（Kronecker 和）导出 ↔ 闭式，方法学独立"),
        "note": "v0.9.87 Batch B-7：(2,1,1) golden≈1.765253 eV / cand |d|~1.28e-4 eV。",
    },
    "B131": {
        "title": "三维长方体无限深势阱能级 E（n_x,n_y,n_z=1,2,1）",
        "metric": "E_eV",
        "oracle": "analytical(3D box E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²+n_z²/L_z²), 3D FD Kronecker sum)",
        "tol": 0.01,
        "default_params": {"a": 1.0e-9, "b": 1.5e-9, "c": 2.0e-9},
        "golden_fn": golden_b131,
        "candidate": "b131_box3d_121_cand",
        "candidate_desc": ("三维长方体势阱能级由 3D FD 拉普拉斯本征（Kronecker 和）导出 ↔ 闭式，方法学独立"),
        "note": "v0.9.87 Batch B-7：(1,2,1) golden≈1.138536 eV / cand |d|~6.40e-5 eV。",
    },
    "B132": {
        "title": "三维长方体无限深势阱能级 E（n_x,n_y,n_z=1,1,2）",
        "metric": "E_eV",
        "oracle": "analytical(3D box E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²+n_z²/L_z²), 3D FD Kronecker sum)",
        "tol": 0.01,
        "default_params": {"a": 1.0e-9, "b": 1.5e-9, "c": 2.0e-9},
        "golden_fn": golden_b132,
        "candidate": "b132_box3d_112_cand",
        "candidate_desc": ("三维长方体势阱能级由 3D FD 拉普拉斯本征（Kronecker 和）导出 ↔ 闭式，方法学独立"),
        "note": "v0.9.87 Batch B-7：(1,1,2) golden≈0.919185 eV / cand |d|~4.17e-5 eV。",
    },
    "B133": {
        "title": "类氢离子激发态能级（H 4s，Z=1,l=0,n=4）",
        "metric": "E_eV",
        "oracle": "analytical(hydrogen-like E_n=−RYDBERG·Z²/n², radial FD Schrödinger)",
        "tol": 0.01,
        "default_params": {"Z": 1.0},
        "golden_fn": golden_b133,
        "candidate": "b133_h_4s_cand",
        "candidate_desc": ("类氢离子激发态能级由径向 FD 薛定谔本征（Coulomb 势，n_r=n−l−1 径向节点）导出"
                           "↔ Rydberg 闭式 E_n=−RYDBERG·Z²/n²，方法学独立"),
        "note": "v0.9.87 Batch B-7：H 4s golden≈−0.850356 eV / cand |d|~5.00e-6 eV。",
    },
    "B134": {
        "title": "类氢离子激发态能级（He⁺ 4d，Z=2,l=2,n=4）",
        "metric": "E_eV",
        "oracle": "analytical(hydrogen-like E_n=−RYDBERG·Z²/n², radial FD Schrödinger)",
        "tol": 0.01,
        "default_params": {"Z": 2.0},
        "golden_fn": golden_b134,
        "candidate": "b134_he_4d_cand",
        "candidate_desc": ("类氢离子激发态能级由径向 FD 薛定谔本征（Z=2 Coulomb + l=2 离心项）导出 ↔ Rydberg 闭式，方法学独立"),
        "note": "v0.9.87 Batch B-7：He⁺ 4d golden≈−3.401423 eV / cand |d|~1.49e-5 eV。",
    },
    "B135": {
        "title": "类氢离子激发态能级（Li²⁺ 4f，Z=3,l=3,n=4）",
        "metric": "E_eV",
        "oracle": "analytical(hydrogen-like E_n=−RYDBERG·Z²/n², radial FD Schrödinger)",
        "tol": 0.01,
        "default_params": {"Z": 3.0},
        "golden_fn": golden_b135,
        "candidate": "b135_li_4f_cand",
        "candidate_desc": ("类氢离子激发态能级由径向 FD 薛定谔本征（Z=3 Coulomb + l=3 强离心势垒）导出 ↔ Rydberg 闭式，方法学独立"),
        "note": "v0.9.87 Batch B-7：Li²⁺ 4f golden≈−7.653202 eV / cand |d|~1.03e-5 eV。",
    },
    "B136": {
        "title": "类氢离子激发态能级（H 5d，Z=1,l=2,n=5）",
        "metric": "E_eV",
        "oracle": "analytical(hydrogen-like E_n=−RYDBERG·Z²/n², radial FD Schrödinger)",
        "tol": 0.01,
        "default_params": {"Z": 1.0},
        "golden_fn": golden_b136,
        "candidate": "b136_h_5d_cand",
        "candidate_desc": ("类氢离子激发态能级由径向 FD 薛定谔本征（H n=5 d 态，l=2）导出 ↔ Rydberg 闭式，方法学独立"),
        "note": "v0.9.87 Batch B-7：H 5d golden≈−0.544228 eV / cand |d|~2.07e-4 eV。",
    },
    "B137": {
        "title": "2D 类氢原子能级（H, n_r=0,m=2, N=3）",
        "metric": "E_eV",
        "oracle": "analytical(2D Coulomb E=−Z²·Ry/(N−½)², N=n_r+|m|+1, 2D radial FD)",
        "tol": 0.01,
        "default_params": {"Z": 1.0},
        "golden_fn": golden_b137,
        "candidate": "b137_h2d_m2_cand",
        "candidate_desc": ("2D 类氢能级由 2D 径向 FD 薛定谔本征（u=√r·R，V_eff=(m²−¼)ℏ²/2mr²−Ze²/4πε₀r）导出"
                           "↔ 2D Coulomb 闭式 E=−Z²Ry/(N−½)²，方法学独立"),
        "note": "v0.9.88 Batch B-8：(m=2,n_r=0,Z=1) golden≈−2.176911 eV / cand |d|~9.55e-7 eV。",
    },
    "B138": {
        "title": "2D 类氢原子能级（H, n_r=1,m=2, N=4）",
        "metric": "E_eV",
        "oracle": "analytical(2D Coulomb E=−Z²·Ry/(N−½)², 2D radial FD)",
        "tol": 0.01,
        "default_params": {"Z": 1.0},
        "golden_fn": golden_b138,
        "candidate": "b138_h2d_m2n1_cand",
        "candidate_desc": ("2D 类氢 (m=2,n_r=1) 由 2D 径向 FD 本征导出 ↔ 2D Coulomb 闭式，方法学独立"),
        "note": "v0.9.88 Batch B-8：(m=2,n_r=1) golden≈−1.110669 eV / cand |d|~6.79e-7 eV。",
    },
    "B139": {
        "title": "2D 类氢原子能级（H, n_r=0,m=4, N=5）",
        "metric": "E_eV",
        "oracle": "analytical(2D Coulomb E=−Z²·Ry/(N−½)², 2D radial FD)",
        "tol": 0.01,
        "default_params": {"Z": 1.0},
        "golden_fn": golden_b139,
        "candidate": "b139_h2d_m4_cand",
        "candidate_desc": ("2D 类氢 (m=4) 强离心态由 2D 径向 FD 本征导出 ↔ 2D Coulomb 闭式，方法学独立"),
        "note": "v0.9.88 Batch B-8：(m=4,n_r=0) golden≈−0.671886 eV / cand |d|~1.54e-8 eV。",
    },
    "B140": {
        "title": "2D 类氢原子能级（He⁺ 类, Z=2, n_r=0,m=2, N=3）",
        "metric": "E_eV",
        "oracle": "analytical(2D Coulomb E=−Z²·Ry/(N−½)², 2D radial FD)",
        "tol": 0.01,
        "default_params": {"Z": 2.0},
        "golden_fn": golden_b140,
        "candidate": "b140_h2d_z2_cand",
        "candidate_desc": ("2D 类氢 (Z=2) 由 2D 径向 FD 本征导出 ↔ 2D Coulomb 闭式，方法学独立"),
        "note": "v0.9.88 Batch B-8：(Z=2,m=2,n_r=0) golden≈−8.707643 eV / cand |d|~1.45e-5 eV。",
    },
    "B141": {
        "title": "2D 圆环量子阱基态能级（ν=0，无通量）",
        "metric": "E_eV",
        "oracle": "analytical(annulus Bessel cross-product J_ν(kR_i)Y_ν(kR_o)−Y_ν(kR_i)J_ν(kR_o)=0, E=ℏ²k²/2m)",
        "tol": 0.01,
        "default_params": {"ri_nm": 0.5, "ro_nm": 1.0},
        "golden_fn": golden_b141,
        "candidate": "b141_annulus_nu0_cand",
        "candidate_desc": ("2D 圆环能级由径向 FD 本征（(ν²−¼)/r² 离心项，u(R_i)=u(R_o)=0）导出"
                           "↔ Bessel 交叉积零点闭式，方法学独立"),
        "note": "v0.9.88 Batch B-8：ν=0 golden≈1.486399 eV / cand |d|~1.40e-7 eV。",
    },
    "B142": {
        "title": "2D 圆环量子阱基态能级（ν=1，m=1）",
        "metric": "E_eV",
        "oracle": "analytical(annulus Bessel cross-product zeros, E=ℏ²k²/2m)",
        "tol": 0.01,
        "default_params": {"ri_nm": 0.5, "ro_nm": 1.0},
        "golden_fn": golden_b142,
        "candidate": "b142_annulus_nu1_cand",
        "candidate_desc": ("2D 圆环 (ν=1) 由径向 FD 本征导出 ↔ Bessel 交叉积零点闭式，方法学独立"),
        "note": "v0.9.88 Batch B-8：ν=1 golden≈1.557233 eV / cand |d|~1.35e-7 eV。",
    },
    "B143": {
        "title": "2D 圆环量子阱基态能级（ν=1/2，Aharonov-Bohm 通量 Φ=½Φ₀）",
        "metric": "E_eV",
        "oracle": "analytical(Aharonov-Bohm annulus Bessel cross-product, ν=|m+Φ/Φ₀|, E=ℏ²k²/2m)",
        "tol": 0.01,
        "default_params": {"ri_nm": 0.5, "ro_nm": 1.0},
        "golden_fn": golden_b143,
        "candidate": "b143_annulus_ab05_cand",
        "candidate_desc": ("AB 通量圆环 (ν=½) 由径向 FD 本征（半整数阶离心项）导出 ↔ 半整数阶 Bessel 交叉积零点闭式，方法学独立"),
        "note": "v0.9.88 Batch B-8：ν=½ golden≈1.504121 eV / cand |d|~1.35e-7 eV。",
    },
    "B144": {
        "title": "2D 圆环量子阱基态能级（ν=3/2，Aharonov-Bohm 通量 Φ=½Φ₀，m=1 支）",
        "metric": "E_eV",
        "oracle": "analytical(Aharonov-Bohm annulus Bessel cross-product, ν=|m+Φ/Φ₀|, E=ℏ²k²/2m)",
        "tol": 0.01,
        "default_params": {"ri_nm": 0.5, "ro_nm": 1.0},
        "golden_fn": golden_b144,
        "candidate": "b144_annulus_ab15_cand",
        "candidate_desc": ("AB 通量圆环 (ν=3/2) 由径向 FD 本征导出 ↔ 半整数阶 Bessel 交叉积零点闭式，方法学独立"),
        "note": "v0.9.88 Batch B-8：ν=3/2 golden≈1.645583 eV / cand |d|~1.36e-7 eV。",
    },
    "B145": {
        "title": "3D 有限深球形势阱束缚态能级（V₀=1 eV, R=2 nm, ℓ=0 基态）",
        "metric": "E_eV",
        "oracle": "analytical(finite spherical well transcendental k·cot(kR)=−κ, 3D radial FD)",
        "tol": 0.01,
        "default_params": {"V0_eV": 1.0, "R_nm": 2.0},
        "golden_fn": golden_b145,
        "candidate": "b145_fsph_v1_cand",
        "candidate_desc": ("3D 有限深球形阱由 3D 径向 FD 本征（V=−V₀ 内 / 0 外，大盒）导出"
                           "↔ 超越方程 k·cot(kR)=−κ 匹配闭式，方法学独立"),
        "note": "v0.9.88 Batch B-8：V₀=1 eV golden≈−0.922153 eV / cand |d|~3.12e-5 eV。",
    },
    "B146": {
        "title": "3D 有限深球形势阱束缚态能级（V₀=5 eV, R=2 nm, ℓ=0 基态）",
        "metric": "E_eV",
        "oracle": "analytical(finite spherical well transcendental k·cot(kR)=−κ, 3D radial FD)",
        "tol": 0.01,
        "default_params": {"V0_eV": 5.0, "R_nm": 2.0},
        "golden_fn": golden_b146,
        "candidate": "b146_fsph_v5_cand",
        "candidate_desc": ("3D 有限深球形阱 (V₀=5eV) 由 3D 径向 FD 本征导出 ↔ 超越方程闭式，方法学独立"),
        "note": "v0.9.88 Batch B-8：V₀=5 eV golden≈−4.913712 eV / cand |d|~3.64e-5 eV。",
    },
    "B147": {
        "title": "3D 有限深球形势阱束缚态能级（V₀=10 eV, R=2 nm, ℓ=0 基态）",
        "metric": "E_eV",
        "oracle": "analytical(finite spherical well transcendental k·cot(kR)=−κ, 3D radial FD)",
        "tol": 0.01,
        "default_params": {"V0_eV": 10.0, "R_nm": 2.0},
        "golden_fn": golden_b147,
        "candidate": "b147_fsph_v10_cand",
        "candidate_desc": ("3D 有限深球形阱 (V₀=10eV) 由 3D 径向 FD 本征导出 ↔ 超越方程闭式，方法学独立"),
        "note": "v0.9.88 Batch B-8：V₀=10 eV golden≈−9.911545 eV / cand |d|~3.76e-5 eV。",
    },
    "B148": {
        "title": "3D 有限深球形势阱束缚态能级（V₀=10 eV, R=2 nm, ℓ=0 第 2 态）",
        "metric": "E_eV",
        "oracle": "analytical(finite spherical well transcendental k·cot(kR)=−κ, 3D radial FD)",
        "tol": 0.01,
        "default_params": {"V0_eV": 10.0, "R_nm": 2.0},
        "golden_fn": golden_b148,
        "candidate": "b148_fsph_v10n2_cand",
        "candidate_desc": ("3D 有限深球形阱第 2 束缚态由 3D 径向 FD 本征导出 ↔ 超越方程闭式，方法学独立"),
        "note": "v0.9.88 Batch B-8：V₀=10 eV n=2 golden≈−9.646275 eV / cand |d|~1.50e-4 eV。",
    },
    "B149": {
        "title": "各向同性 3D 谐振子基态能级（ω_x=ω_y=ω_z）",
        "metric": "E_eV",
        "oracle": "analytical(3D HO E=ℏ(ω_x(n_x+½)+ω_y(n_y+½)+ω_z(n_z+½)), 3D FD Kronecker sum)",
        "tol": 0.01,
        "default_params": {"ox": 1.0, "oy": 1.0, "oz": 1.0},
        "golden_fn": golden_b149,
        "candidate": "b149_ho3d_iso_cand",
        "candidate_desc": ("3D 各向同性谐振子基态由三个 1D HO FD 谱 Kronecker 和导出 ↔ 可分离解析闭式，方法学独立"),
        "note": "v0.9.88 Batch B-8：各向同性 (0,0,0) golden≈0.987318 eV / cand |d|~1.02e-5 eV。",
    },
    "B150": {
        "title": "各向异性 3D 谐振子基态能级（ω=1.0:1.2:1.4）",
        "metric": "E_eV",
        "oracle": "analytical(anisotropic 3D HO E=ℏ(ω_x(n_x+½)+ω_y(n_y+½)+ω_z(n_z+½)), 3D FD Kronecker sum)",
        "tol": 0.01,
        "default_params": {"ox": 1.0, "oy": 1.2, "oz": 1.4},
        "golden_fn": golden_b150,
        "candidate": "b150_ho3d_aniso000_cand",
        "candidate_desc": ("各向异性 3D 谐振子基态由三个 1D HO FD 谱 Kronecker 和导出 ↔ 可分离解析闭式，方法学独立"),
        "note": "v0.9.88 Batch B-8：各向异性 (0,0,0) golden≈1.184782 eV / cand |d|~1.22e-5 eV。",
    },
    "B151": {
        "title": "各向异性 3D 谐振子激发态能级（ω=1.0:1.2:1.4, (1,0,0)）",
        "metric": "E_eV",
        "oracle": "analytical(anisotropic 3D HO, 3D FD Kronecker sum)",
        "tol": 0.01,
        "default_params": {"ox": 1.0, "oy": 1.2, "oz": 1.4},
        "golden_fn": golden_b151,
        "candidate": "b151_ho3d_aniso100_cand",
        "candidate_desc": ("各向异性 3D 谐振子 (1,0,0) 由 Kronecker 和导出 ↔ 可分离解析闭式，方法学独立"),
        "note": "v0.9.88 Batch B-8：(1,0,0) golden≈1.842993 eV / cand |d|~2.58e-5 eV。",
    },
    "B152": {
        "title": "各向异性 3D 谐振子激发态能级（ω=1.0:1.2:1.4, (1,1,1)）",
        "metric": "E_eV",
        "oracle": "analytical(anisotropic 3D HO, 3D FD Kronecker sum)",
        "tol": 0.01,
        "default_params": {"ox": 1.0, "oy": 1.2, "oz": 1.4},
        "golden_fn": golden_b152,
        "candidate": "b152_ho3d_aniso111_cand",
        "candidate_desc": ("各向异性 3D 谐振子 (1,1,1) 由 Kronecker 和导出 ↔ 可分离解析闭式，方法学独立"),
        "note": "v0.9.88 Batch B-8：(1,1,1) golden≈3.554345 eV / cand |d|~6.11e-5 eV。",
    },
    "B153": {
        "title": "固支-固支 Si 微梁第 1 阶横向振动频率（Euler-Bernoulli）",
        "metric": "f_MHz",
        "oracle": "analytical(Euler-Bernoulli 固支梁超越方程 cos(βL)cosh(βL)=1 根 ⇒ f_n=(β_nL)²/(2πL²)·√(E·I/(ρ·A)), Hermite 梁单元 FEM)",
        "tol": 0.01,
        "default_params": {"L_um": 5.0},
        "golden_fn": golden_b153,
        "candidate": "b153_beam_mode1_cand",
        "candidate_desc": ("固支梁第 1 阶频率由 Hermite 梁单元 FEM 广义本征 (Ne=200) 导出 ↔ 4 阶 ODE 超越方程根闭式，方法学独立"),
        "note": "v0.9.89 Batch B-9：L=5 µm golden≈175.087306 MHz / cand |d|~2.40e-7 MHz（余量 ~4.2e4×）。",
    },
    "B154": {
        "title": "固支-固支 Si 微梁第 2 阶横向振动频率（Euler-Bernoulli）",
        "metric": "f_MHz",
        "oracle": "analytical(Euler-Bernoulli 固支梁 cos(βL)cosh(βL)=1 第 2 根, Hermite 梁单元 FEM)",
        "tol": 0.01,
        "default_params": {"L_um": 5.0},
        "golden_fn": golden_b154,
        "candidate": "b154_beam_mode2_cand",
        "candidate_desc": ("固支梁第 2 阶频率由 Hermite 梁单元 FEM 广义本征导出 ↔ 超越方程根闭式，方法学独立"),
        "note": "v0.9.89 Batch B-9：L=5 µm golden≈482.634900 MHz / cand |d|~1.14e-6 MHz（余量 ~8.8e3×）。",
    },
    "B155": {
        "title": "固支-固支 Si 微梁第 3 阶横向振动频率（Euler-Bernoulli）",
        "metric": "f_MHz",
        "oracle": "analytical(Euler-Bernoulli 固支梁 cos(βL)cosh(βL)=1 第 3 根, Hermite 梁单元 FEM)",
        "tol": 0.01,
        "default_params": {"L_um": 5.0},
        "golden_fn": golden_b155,
        "candidate": "b155_beam_mode3_cand",
        "candidate_desc": ("固支梁第 3 阶频率由 Hermite 梁单元 FEM 广义本征导出 ↔ 超越方程根闭式，方法学独立"),
        "note": "v0.9.89 Batch B-9：L=5 µm golden≈946.157378 MHz / cand |d|~7.63e-6 MHz（余量 ~1.3e3×）。",
    },
    "B156": {
        "title": "固支-固支 Si 微梁第 4 阶横向振动频率（Euler-Bernoulli）",
        "metric": "f_MHz",
        "oracle": "analytical(Euler-Bernoulli 固支梁 cos(βL)cosh(βL)=1 第 4 根, Hermite 梁单元 FEM)",
        "tol": 0.01,
        "default_params": {"L_um": 5.0},
        "golden_fn": golden_b156,
        "candidate": "b156_beam_mode4_cand",
        "candidate_desc": ("固支梁第 4 阶频率由 Hermite 梁单元 FEM 广义本征导出 ↔ 超越方程根闭式，方法学独立"),
        "note": "v0.9.89 Batch B-9：L=5 µm golden≈1564.046209 MHz / cand |d|~2.77e-5 MHz（余量 ~3.6e2×）。",
    },
    "B157": {
        "title": "Hulthen 势 3D s-wave 第 1 束缚态（指数屏蔽 Coulomb）",
        "metric": "E_eV",
        "oracle": "analytical(Hulthen s-wave E_n=-V₀[(β²-n²)/(2nβ)]², β²=2mV₀a²/ℏ², 3D 径向 FD)",
        "tol": 0.01,
        "default_params": {"V0_eV": 0.5878, "a_nm": 1.5277},
        "golden_fn": golden_b157,
        "candidate": "b157_hulthen_n1_cand",
        "candidate_desc": ("Hulthen s-wave 第 1 束缚态由 3D 径向 FD 本征导出 ↔ 超几何/Jacobi 精确闭式，方法学独立"),
        "note": "v0.9.89 Batch B-9：β²=36 golden≈−5.001359 eV / cand |d|~1.84e-4 eV（余量 ~54×）；a→∞ 极限自检还原氢 1s（差 7.2e-7）。",
    },
    "B158": {
        "title": "Hulthen 势 3D s-wave 第 2 束缚态（指数屏蔽 Coulomb）",
        "metric": "E_eV",
        "oracle": "analytical(Hulthen s-wave 闭式, 3D 径向 FD)",
        "tol": 0.01,
        "default_params": {"V0_eV": 0.5878, "a_nm": 1.5277},
        "golden_fn": golden_b158,
        "candidate": "b158_hulthen_n2_cand",
        "candidate_desc": ("Hulthen s-wave 第 2 束缚态由 3D 径向 FD 本征导出 ↔ 精确闭式，方法学独立"),
        "note": "v0.9.89 Batch B-9：golden≈−1.045219 eV / cand |d|~1.14e-5 eV（余量 ~878×）。",
    },
    "B159": {
        "title": "Hulthen 势 3D s-wave 第 3 束缚态（指数屏蔽 Coulomb）",
        "metric": "E_eV",
        "oracle": "analytical(Hulthen s-wave 闭式, 3D 径向 FD)",
        "tol": 0.01,
        "default_params": {"V0_eV": 0.5878, "a_nm": 1.5277},
        "golden_fn": golden_b159,
        "candidate": "b159_hulthen_n3_cand",
        "candidate_desc": ("Hulthen s-wave 第 3 束缚态由 3D 径向 FD 本征导出 ↔ 精确闭式，方法学独立"),
        "note": "v0.9.89 Batch B-9：golden≈−0.330739 eV / cand |d|~2.17e-6 eV（余量 ~4.6e3×）。",
    },
    "B160": {
        "title": "Hulthen 势 3D s-wave 第 4 束缚态（指数屏蔽 Coulomb）",
        "metric": "E_eV",
        "oracle": "analytical(Hulthen s-wave 闭式, 3D 径向 FD)",
        "tol": 0.01,
        "default_params": {"V0_eV": 0.5878, "a_nm": 1.5277},
        "golden_fn": golden_b160,
        "candidate": "b160_hulthen_n4_cand",
        "candidate_desc": ("Hulthen s-wave 第 4 束缚态由 3D 径向 FD 本征导出 ↔ 精确闭式，方法学独立"),
        "note": "v0.9.89 Batch B-9：golden≈−0.102098 eV / cand |d|~6.14e-7 eV（余量 ~1.6e4×）。",
    },
    "B161": {
        "title": "Fock-Darwin 2D 量子点能级 (n_r=0, m=2, B=5 T)",
        "metric": "E_meV",
        "oracle": "analytical(Fock-Darwin ε=ℏΩ(2n_r+|m|+1)−(ℏω_c/2)m, Ω=√(ω₀²+ω_c²/4), 2D 径向 FD)",
        "tol": 0.01,
        "default_params": {"B_T": 5.0},
        "golden_fn": golden_b161,
        "candidate": "b161_fock_darwin_02_cand",
        "candidate_desc": ("Fock-Darwin (n_r=0,m=2) 由 2D 径向 FD 本征 + L_z 项解析本征导出 ↔ 精确闭式，方法学独立"),
        "note": "v0.9.89 Batch B-9：m*=0.067m₀、ℏω₀=5 meV、B=5 T golden≈11.183271 meV / cand |d|~9.82e-7 meV（余量 ~1.0e4×）。",
    },
    "B162": {
        "title": "Fock-Darwin 2D 量子点能级 (n_r=0, m=3, B=5 T)",
        "metric": "E_meV",
        "oracle": "analytical(Fock-Darwin 闭式, 2D 径向 FD)",
        "tol": 0.01,
        "default_params": {"B_T": 5.0},
        "golden_fn": golden_b162,
        "candidate": "b162_fock_darwin_03_cand",
        "candidate_desc": ("Fock-Darwin (n_r=0,m=3) 由 2D 径向 FD 本征 + L_z 项导出 ↔ 精确闭式，方法学独立"),
        "note": "v0.9.89 Batch B-9：golden≈13.471132 meV / cand |d|~8.54e-7 meV（余量 ~1.2e4×）。",
    },
    "B163": {
        "title": "Fock-Darwin 2D 量子点能级 (n_r=0, m=4, B=5 T)",
        "metric": "E_meV",
        "oracle": "analytical(Fock-Darwin 闭式, 2D 径向 FD)",
        "tol": 0.01,
        "default_params": {"B_T": 5.0},
        "golden_fn": golden_b163,
        "candidate": "b163_fock_darwin_04_cand",
        "candidate_desc": ("Fock-Darwin (n_r=0,m=4) 由 2D 径向 FD 本征 + L_z 项导出 ↔ 精确闭式，方法学独立"),
        "note": "v0.9.89 Batch B-9：golden≈15.758993 meV / cand |d|~6.39e-7 meV（余量 ~1.6e4×）。",
    },
    "B164": {
        "title": "Fock-Darwin 2D 量子点能级 (n_r=1, m=2, B=5 T)",
        "metric": "E_meV",
        "oracle": "analytical(Fock-Darwin 闭式, 2D 径向 FD)",
        "tol": 0.01,
        "default_params": {"B_T": 5.0},
        "golden_fn": golden_b164,
        "candidate": "b164_fock_darwin_12_cand",
        "candidate_desc": ("Fock-Darwin (n_r=1,m=2) 由 2D 径向 FD 本征 + L_z 项导出 ↔ 精确闭式，方法学独立"),
        "note": "v0.9.89 Batch B-9：golden≈24.398369 meV / cand |d|~3.70e-6 meV（余量 ~2.7e3×）。",
    },
    "B165": {
        "title": "Rosen-Morse II 势基态能级（sech²+tanh 双曲势）",
        "metric": "E_eV",
        "oracle": "analytical(Rosen-Morse II E_n=−(ℏ²α²/2μ)(a_n²+b_n²), b_n=√(γ+¼)−n−½, a_n=−β/(2b_n), 1D FD)",
        "tol": 0.01,
        "default_params": {"C_eV": 4.0, "B_eV": 0.4, "alpha_inv_nm": 1.0},
        "golden_fn": golden_b165,
        "candidate": "b165_rosen_morse_n0_cand",
        "candidate_desc": ("Rosen-Morse II 基态由 1D FD 本征导出 ↔ 超几何精确闭式，方法学独立（含奇宇称 tanh 项，非同 Pöschl-Teller）"),
        "note": "v0.9.89 Batch B-9：C=4 eV/B=0.4 eV/α⁻¹=1 nm golden≈−3.639227 eV / cand |d|~3.04e-7 eV（余量 ~3.3e4×）。",
    },
    "B166": {
        "title": "Rosen-Morse II 势第 1 激发态能级（sech²+tanh 双曲势）",
        "metric": "E_eV",
        "oracle": "analytical(Rosen-Morse II 闭式, 1D FD)",
        "tol": 0.01,
        "default_params": {"C_eV": 4.0, "B_eV": 0.4, "alpha_inv_nm": 1.0},
        "golden_fn": golden_b166,
        "candidate": "b166_rosen_morse_n1_cand",
        "candidate_desc": ("Rosen-Morse II 第 1 激发态由 1D FD 本征导出 ↔ 超几何精确闭式，方法学独立"),
        "note": "v0.9.89 Batch B-9：golden≈−2.936391 eV / cand |d|~1.31e-6 eV（余量 ~7.6e3×）。",
    },
    "B167": {
        "title": "Rosen-Morse II 势第 2 激发态能级（sech²+tanh 双曲势）",
        "metric": "E_eV",
        "oracle": "analytical(Rosen-Morse II 闭式, 1D FD)",
        "tol": 0.01,
        "default_params": {"C_eV": 4.0, "B_eV": 0.4, "alpha_inv_nm": 1.0},
        "golden_fn": golden_b167,
        "candidate": "b167_rosen_morse_n2_cand",
        "candidate_desc": ("Rosen-Morse II 第 2 激发态由 1D FD 本征导出 ↔ 超几何精确闭式，方法学独立"),
        "note": "v0.9.89 Batch B-9：golden≈−2.310850 eV / cand |d|~2.84e-6 eV（余量 ~3.5e3×）。",
    },
    "B168": {
        "title": "Rosen-Morse II 势第 3 激发态能级（sech²+tanh 双曲势）",
        "metric": "E_eV",
        "oracle": "analytical(Rosen-Morse II 闭式, 1D FD)",
        "tol": 0.01,
        "default_params": {"C_eV": 4.0, "B_eV": 0.4, "alpha_inv_nm": 1.0},
        "golden_fn": golden_b168,
        "candidate": "b168_rosen_morse_n3_cand",
        "candidate_desc": ("Rosen-Morse II 第 3 激发态由 1D FD 本征导出 ↔ 超几何精确闭式，方法学独立"),
        "note": "v0.9.89 Batch B-9：golden≈−1.763296 eV / cand |d|~4.39e-6 eV（余量 ~2.3e3×）。",
    },
    # -----------------------------------------------------------------------
    # Batch B-10（v0.9.90 · 腿① 续加锚稀释 terminal）：四族全新方程/特殊函数/
    # 数值方法类 —— Mathieu 周期系数 ODE / 椭圆积分与椭球静电 / Fresnel 积分 /
    # 线性扩散热核时间推进。同源体检详见 _batch_b10_numeric 模块 docstring。
    # -----------------------------------------------------------------------
    "B169": {
        "title": "Mathieu 方程偶族特征值 a₀(q=1)（周期系数 Hill ODE；MEMS 参数激励）",
        "metric": "char_value",
        "oracle": "special_function(Mathieu 特征值 scipy.special.mathieu_a/b 机器精度, 半周期 [0,π/2] P1-FEM 广义本征)",
        "tol": 0.01,
        "default_params": {"q": 1.0},
        "golden_fn": golden_b169,
        "candidate": "b169_mathieu_a0_cand",
        "candidate_desc": ("Mathieu 偶族 a₀ 由半周期 P1-FEM 广义本征（BC=(N,N), k=0）导出 ↔ scipy Mathieu 特征值特殊函数，方法学独立"),
        "note": "v0.9.90 Batch B-10：q=1 golden≈−0.455138604 / cand |d|~5.11e-07（余量 ~2.0e4×）；q→0 极限自检 a₀→0 精确。",
    },
    "B170": {
        "title": "Mathieu 方程偶族特征值 a₁(q=1)",
        "metric": "char_value",
        "oracle": "special_function(Mathieu a₁, 半周期 P1-FEM 广义本征 BC=(N,D), k=0)",
        "tol": 0.01,
        "default_params": {"q": 1.0},
        "golden_fn": golden_b170,
        "candidate": "b170_mathieu_a1_cand",
        "candidate_desc": ("Mathieu 偶族 a₁ 由半周期 P1-FEM（BC=(N,D), k=0）导出 ↔ scipy Mathieu 特征值，方法学独立"),
        "note": "v0.9.90 Batch B-10：q=1 golden≈1.859108073 / cand |d|~8.29e-07（余量 ~1.2e4×）。",
    },
    "B171": {
        "title": "Mathieu 方程奇族特征值 b₁(q=1)",
        "metric": "char_value",
        "oracle": "special_function(Mathieu b₁, 半周期 P1-FEM 广义本征 BC=(D,N), k=0)",
        "tol": 0.01,
        "default_params": {"q": 1.0},
        "golden_fn": golden_b171,
        "candidate": "b171_mathieu_b1_cand",
        "candidate_desc": ("Mathieu 奇族 b₁ 由半周期 P1-FEM（BC=(D,N), k=0）导出 ↔ scipy Mathieu 特征值，方法学独立"),
        "note": "v0.9.90 Batch B-10：q=1 golden≈−0.110248817 / cand |d|~6.34e-07（余量 ~1.6e4×）。",
    },
    "B172": {
        "title": "Mathieu 方程奇族特征值 b₂(q=1)",
        "metric": "char_value",
        "oracle": "special_function(Mathieu b₂, 半周期 P1-FEM 广义本征 BC=(D,D), k=0)",
        "tol": 0.01,
        "default_params": {"q": 1.0},
        "golden_fn": golden_b172,
        "candidate": "b172_mathieu_b2_cand",
        "candidate_desc": ("Mathieu 奇族 b₂ 由半周期 P1-FEM（BC=(D,D), k=0）导出 ↔ scipy Mathieu 特征值，方法学独立"),
        "note": "v0.9.90 Batch B-10：q=1 golden≈3.917024773 / cand |d|~5.67e-06（余量 ~1.8e3×）；FG 三对角构造因撞「代数恒等」红线被否。",
    },
    "B173": {
        "title": "Mathieu 方程偶族特征值 a₂(q=1)",
        "metric": "char_value",
        "oracle": "special_function(Mathieu a₂, 半周期 P1-FEM 广义本征 BC=(N,N), k=1)",
        "tol": 0.01,
        "default_params": {"q": 1.0},
        "golden_fn": golden_b173,
        "candidate": "b173_mathieu_a2_cand",
        "candidate_desc": ("Mathieu 偶族 a₂ 由半周期 P1-FEM（BC=(N,N), k=1）导出 ↔ scipy Mathieu 特征值，方法学独立"),
        "note": "v0.9.90 Batch B-10：q=1 golden≈4.371300983 / cand |d|~5.18e-06（余量 ~1.9e3×）；FEM 残差严格 O(h²)。",
    },
    "B174": {
        "title": "椭圆截面几何周长（a=2 µm, b=1 µm；第二类完全椭圆积分）",
        "metric": "perimeter_um",
        "oracle": "special_function(椭圆积分闭式 L=4a·E(m), m=1−b²/a² 机器精度, 复合 Simpson n=12)",
        "tol": 0.01,
        "default_params": {"a_um": 2.0, "b_um": 1.0},
        "golden_fn": golden_b174,
        "candidate": "b174_ellipse_perimeter_2_1_cand",
        "candidate_desc": ("椭圆周长由纯数值复合 Simpson 4∫₀^{π/2}√(a²sin²θ+b²cos²θ)dθ 导出 ↔ 第二类椭圆积分 E(m) 特殊函数闭式，方法学独立"),
        "note": "v0.9.90 Batch B-10：golden≈9.688448221 µm / cand |d|~7.87e-08（余量 ~1.3e5×）；n=12 避开超收敛 round-off 地板。",
    },
    "B175": {
        "title": "椭圆截面几何周长（a=3 µm, b=1 µm）",
        "metric": "perimeter_um",
        "oracle": "special_function(椭圆积分闭式 L=4a·E(m), 复合 Simpson n=12)",
        "tol": 0.01,
        "default_params": {"a_um": 3.0, "b_um": 1.0},
        "golden_fn": golden_b175,
        "candidate": "b175_ellipse_perimeter_3_1_cand",
        "candidate_desc": ("椭圆周长（高偏心度 a=3 µm, b=1 µm）由复合 Simpson 求积导出 ↔ 椭圆积分闭式，方法学独立"),
        "note": "v0.9.90 Batch B-10：golden≈13.364893221 µm / cand |d|~1.26e-05（余量 ~791×）。",
    },
    "B176": {
        "title": "大摆角单摆周期比 T/T₀（θ₀=135°；第一类完全椭圆积分）",
        "metric": "T_ratio",
        "oracle": "special_function(第一类椭圆积分闭式 T/T₀=(2/π)K(m), m=sin²(θ₀/2) 机器精度, 复合 Simpson n=16)",
        "tol": 0.01,
        "default_params": {"theta0_deg": 135.0},
        "golden_fn": golden_b176,
        "candidate": "b176_pendulum_135_cand",
        "candidate_desc": ("大摆角单摆周期比由纯数值复合 Simpson (2/π)∫₀^{π/2}dθ/√(1−m sin²θ) 导出 ↔ 第一类椭圆积分 K(m) 闭式，方法学独立"),
        "note": "v0.9.90 Batch B-10：θ₀=135° golden≈1.527947588 / cand |d|~3.75e-07（余量 ~2.7e4×）；θ₀=90° 因撞 round-off 地板弃用。",
    },
    "B177": {
        "title": "大摆角单摆周期比 T/T₀（θ₀=150°）",
        "metric": "T_ratio",
        "oracle": "special_function(第一类椭圆积分闭式 T/T₀=(2/π)K(m), 复合 Simpson n=16)",
        "tol": 0.01,
        "default_params": {"theta0_deg": 150.0},
        "golden_fn": golden_b177,
        "candidate": "b177_pendulum_150_cand",
        "candidate_desc": ("大摆角单摆周期比（θ₀=150°，m→1 端点近奇异）由复合 Simpson 导出 ↔ 椭圆积分 K(m) 闭式，方法学独立"),
        "note": "v0.9.90 Batch B-10：θ₀=150° golden≈1.762203730 / cand |d|~3.80e-05（余量 ~263×）。",
    },
    "B178": {
        "title": "扁椭球去极化因子 N_c（轴比 a/c=2；静电形状因子）",
        "metric": "N_c",
        "oracle": "closed_form(扁椭球 N_c=(1/e²)[1−(1/e)asin(e)√(1−e²)] 初等反正弦闭式, (A/2)∫₀¹(1−t)^½/[A(1−t)+t]dt Simpson n=256)",
        "tol": 0.01,
        "default_params": {"ar": 2.0},
        "golden_fn": golden_b178,
        "candidate": "b178_oblate_depol_Nc_cand",
        "candidate_desc": ("扁椭球 c 轴去极化因子由 s→t 变换后的复合 Simpson 数值积分导出 ↔ 初等反正弦闭式，方法学独立"),
        "note": "v0.9.90 Batch B-10：ar=2 golden≈0.527200283 / cand |d|~3.97e-05（余量 ~252×）；ar→1 球极限自检 N_c→1/3、求和律 N_c+2N_a=1。",
    },
    "B179": {
        "title": "长椭球去极化因子 N_a（轴比 a/b=2）",
        "metric": "N_a",
        "oracle": "closed_form(长椭球 N_a=((1−e²)/e³)[½ln((1+e)/(1−e))−e] 初等对数闭式, (ar/2)∫₀¹(1−t)^½/[A(1−t)+t]^{3/2}dt Simpson n=256)",
        "tol": 0.01,
        "default_params": {"ar": 2.0},
        "golden_fn": golden_b179,
        "candidate": "b179_prolate_depol_Na_cand",
        "candidate_desc": ("长椭球 a 轴去极化因子由 s→t 变换后的复合 Simpson 数值积分导出 ↔ 初等对数闭式，方法学独立"),
        "note": "v0.9.90 Batch B-10：ar=2 golden≈0.173563998 / cand |d|~1.99e-05（余量 ~503×）；ar→1 球极限自检 N_a→1/3。",
    },
    "B180": {
        "title": "Fresnel（Cornu）余弦积分 C(u=1)（衍射半波带）",
        "metric": "C_u",
        "oracle": "special_function(scipy.special.fresnel 机器精度, 复合 Simpson ∫₀^u cos(πt²/2)dt n=64)",
        "tol": 0.01,
        "default_params": {"u": 1.0},
        "golden_fn": golden_b180,
        "candidate": "b180_fresnel_C1_cand",
        "candidate_desc": ("Fresnel 余弦积分由纯数值复合 Simpson 求积导出 ↔ scipy fresnel 特殊函数，方法学独立"),
        "note": "v0.9.90 Batch B-10：u=1 golden≈0.779893400 / cand |d|~1.03e-08（余量 ~9.7e5×）；收敛严格 O(h⁴)。",
    },
    "B181": {
        "title": "Fresnel（Cornu）正弦积分 S(u=1)",
        "metric": "S_u",
        "oracle": "special_function(scipy.special.fresnel 机器精度, 复合 Simpson ∫₀^u sin(πt²/2)dt n=64)",
        "tol": 0.01,
        "default_params": {"u": 1.0},
        "golden_fn": golden_b181,
        "candidate": "b181_fresnel_S1_cand",
        "candidate_desc": ("Fresnel 正弦积分由纯数值复合 Simpson 求积导出 ↔ scipy fresnel 特殊函数，方法学独立"),
        "note": "v0.9.90 Batch B-10：u=1 golden≈0.438259147 / cand |d|~9.81e-09（余量 ~1.0e6×）。",
    },
    "B182": {
        "title": "线性扩散方程基础解归一剖面 R(x=50 nm, t=1800 s)（高斯热核）",
        "metric": "C_norm",
        "oracle": "analytical(高斯热核 R(x)=exp(−x²/4Dt) 精确, 双端零通量 Crank-Nicolson 时间推进 M=4000/nt=960)",
        "tol": 0.01,
        "default_params": {"x_nm": 50.0},
        "golden_fn": golden_b182,
        "candidate": "b182_diffusion_profile_50nm_cand",
        "candidate_desc": ("中心归一浓度剖面由双端零通量 Crank-Nicolson 时间推进（相邻格点线性插值）导出 ↔ 高斯热核解析基础解，方法学独立"),
        "note": "v0.9.90 Batch B-10：D=1e-18 m²/s、t₀=600 s、t₁=1800 s golden≈0.706648278 / cand |d|~2.00e-05（余量 ~499×）；一步保持性自检 1.1e-5/6.9e-7。",
    },
    "B183": {
        "title": "线性扩散方程基础解归一剖面 R(x=120 nm, t=1800 s)",
        "metric": "C_norm",
        "oracle": "analytical(高斯热核精确, 双端零通量 Crank-Nicolson M=4000/nt=960)",
        "tol": 0.01,
        "default_params": {"x_nm": 120.0},
        "golden_fn": golden_b183,
        "candidate": "b183_diffusion_profile_120nm_cand",
        "candidate_desc": ("归一扩散剖面（x=120 nm）由 Crank-Nicolson 时间推进导出 ↔ 高斯热核解析解，方法学独立"),
        "note": "v0.9.90 Batch B-10：golden≈0.135335283 / cand |d|~8.35e-06（余量 ~1.2e3×）；判据 D 随 M 严格 O(h²)。",
    },
    "B184": {
        "title": "线性扩散方程基础解归一剖面 R(x=200 nm, t=1800 s)",
        "metric": "C_norm",
        "oracle": "analytical(高斯热核精确, 双端零通量 Crank-Nicolson M=4000/nt=960)",
        "tol": 0.01,
        "default_params": {"x_nm": 200.0},
        "golden_fn": golden_b184,
        "candidate": "b184_diffusion_profile_200nm_cand",
        "candidate_desc": ("归一扩散剖面（x=200 nm，远场尾部）由 Crank-Nicolson 时间推进导出 ↔ 高斯热核解析解，方法学独立"),
        "note": "v0.9.90 Batch B-10：golden≈0.003865920 / cand |d|~1.69e-06（余量 ~5.9e3×）。",
    },
    # -----------------------------------------------------------------------
    # Batch B-11（v0.9.91 · 腿① 续加锚稀释 terminal）：四族全新方程/特殊函数/数值方法类
    # —— 量子统计积分与 ζ 函数（换元复合 Simpson）/ Kepler 中心力轨道 ODE（RK4 时间积分）/
    # 辐射传热角系数（4D 张量积分块复合 Simpson）/ Voigt 谱线卷积（sinh 换元 + Simpson）。
    # 同源体检（三条红线）详见 _batch_b11_numeric 模块 docstring。
    # 🔴 逐锚 tol 收紧至 0.001~0.005：族 C/D 指标动态范围仅 ~0.07–0.29 ⇒ 绝对 tol=0.01
    #    会把 10% 参数扰动信号淹没（零判别力）；反向注册键见 _batch_b11_numeric._PERTURB_KEYS。
    # -----------------------------------------------------------------------
    "B185": {
        "title": "玻色矩 ∫₀^∞x³/(eˣ−1)dx = π⁴/15（黑体辐射能量密度系数）",
        "metric": "bose_moment",
        "oracle": "special_function(Γ(s)ζ(s) 严格闭式 scipy.special.zeta, 换元 t=x/(1+x) 后 [0,1] 复合 Simpson n=64)",
        "tol": 0.01,
        "default_params": {"s": 4.0},
        "golden_fn": golden_b185,
        "candidate": "b185_bose_moment_s4_cand",
        "candidate_desc": "玻色矩 s=4 由 t=x/(1+x) 换元归约到 [0,1] 复合 Simpson 导出 ↔ Γ(s)ζ(s) 闭式，方法学独立",
        "note": "v0.9.91 Batch B-11：golden=6.493939402 / cand |Δ|=5.91e-06（余量 1693×）；判据 D 扫 n 单调 O(h⁴)。",
    },
    "B186": {
        "title": "玻色矩 ∫₀^∞x²/(eˣ−1)dx = 2ζ(3)（黑体光子数密度系数）",
        "metric": "bose_moment",
        "oracle": "special_function(Γ(s)ζ(s) 闭式, 换元后的 [0,1] 复合 Simpson n=64)",
        "tol": 0.01,
        "default_params": {"s": 3.0},
        "golden_fn": golden_b186,
        "candidate": "b186_bose_moment_s3_cand",
        "candidate_desc": "玻色矩 s=3 由换元 + 复合 Simpson 导出 ↔ 2ζ(3) 闭式，方法学独立",
        "note": "v0.9.91 Batch B-11：golden=2.404113806 / cand |Δ|=3.53e-06（余量 2833×）。",
    },
    "B187": {
        "title": "费米矩 ∫₀^∞x²/(eˣ+1)dx = (3/2)ζ(3)（费米气体低温 T² 比热系数，Sommerfeld）",
        "metric": "fermi_moment",
        "oracle": "special_function((1−2^{1−s})Γ(s)ζ(s) 闭式, 换元后的 [0,1] 复合 Simpson n=64)",
        "tol": 0.01,
        "default_params": {"s": 3.0},
        "golden_fn": golden_b187,
        "candidate": "b187_fermi_moment_s3_cand",
        "candidate_desc": "费米矩 s=3 由换元 + 复合 Simpson 导出 ↔ (3/2)ζ(3) 闭式，方法学独立",
        "note": "v0.9.91 Batch B-11：golden=1.803085355 / cand |Δ|=3.53e-06（余量 2837×）。",
    },
    "B188": {
        "title": "德拜矩 ∫₀^∞x⁴eˣ/(eˣ−1)²dx = 4π⁴/15（德拜固体低温 T³ 热容系数）",
        "metric": "debye_moment",
        "oracle": "special_function(Γ(s)ζ(s−1) 闭式, 换元后的 [0,1] 复合 Simpson n=64)",
        "tol": 0.01,
        "default_params": {"s": 5.0},
        "golden_fn": golden_b188,
        "candidate": "b188_debye_moment_s5_cand",
        "candidate_desc": "德拜矩 s=5 由换元 + 复合 Simpson 导出 ↔ Γ(5)ζ(4)=4π⁴/15 闭式，方法学独立",
        "note": "v0.9.91 Batch B-11：golden=25.975757609 / cand |Δ|=6.28e-04（余量 15.9×，本批最小之一）。",
    },
    "B189": {
        "title": "Kepler 二体轨道周期 T=2π√(a³/μ)（a=1，中心力 ODE）",
        "metric": "orbit_period",
        "oracle": "closed_form(Kepler 第三定律 T=2π√(a³/μ), 中心力 ODE 的 RK4 时间积分 + 三次 Hermite 近心点穿越定位)",
        "tol": 0.01,
        "default_params": {"a": 1.0},
        "golden_fn": golden_b189,
        "candidate": "b189_kepler_period_a1_cand",
        "candidate_desc": "轨道周期由 r''=−μr/|r|³ 的 RK4 时间积分（近心点-近心点穿越时刻差）导出 ↔ Kepler 解析闭式，方法学独立",
        "note": "v0.9.91 Batch B-11：golden=6.283185307 / cand |Δ|=6.62e-08（余量 1.5e5×）；偏心率 e 固定在候选内部（周期与 e 无关，Kepler 第三定律）。",
    },
    "B190": {
        "title": "Kepler 近心点距离 r_p=a(1−e)（a=1, e=0.6）",
        "metric": "r_peri",
        "oracle": "closed_form(r_p=a(1−e), RK4 轨道 + 三次 Hermite 穿越插值定位 min|r|)",
        "tol": 0.01,
        "default_params": {"a": 1.0, "ecc": 0.6},
        "golden_fn": golden_b190,
        "candidate": "b190_kepler_r_peri_cand",
        "candidate_desc": "近心点距离由 RK4 数值轨迹经三次 Hermite 插值定位穿越时刻后取 |r| 导出 ↔ a(1−e) 解析闭式，方法学独立",
        "note": "v0.9.91 Batch B-11：golden=0.400000000 / cand |Δ|=5.52e-09（余量 1.8e6×）；观测取穿越插值量而非守恒量（守恒量在 RK4 下直落机器精度地板——本批血案 1）。",
    },
    "B191": {
        "title": "Kepler 近心点速率 v_p=√(μ(2/r_p−1/a))（a=1, e=0.6）",
        "metric": "v_peri",
        "oracle": "closed_form(v_p=√(μ(2/r_p−1/a)) 活力公式, RK4 轨道 + Hermite 插值取穿越时刻 |v|)",
        "tol": 0.01,
        "default_params": {"a": 1.0, "ecc": 0.6},
        "golden_fn": golden_b191,
        "candidate": "b191_kepler_v_peri_cand",
        "candidate_desc": "近心点速率由 RK4 轨迹在 Hermite 定位的穿越时刻取 |v| 导出 ↔ 活力公式闭式，方法学独立",
        "note": "v0.9.91 Batch B-11：golden=2.000000000 / cand |Δ|=7.12e-09（余量 1.4e6×）。",
    },
    "B192": {
        "title": "Kepler 二体轨道周期 T=2π√(a³/μ)（a=2，宽轨道长时程）",
        "metric": "orbit_period",
        "oracle": "closed_form(Kepler 第三定律 T=2π√(a³/μ), RK4 时间积分 + Hermite 穿越定位)",
        "tol": 0.01,
        "default_params": {"a": 2.0},
        "golden_fn": golden_b192,
        "candidate": "b192_kepler_period_a2_cand",
        "candidate_desc": "宽轨道（a=2）周期由 RK4 时间积分导出 ↔ Kepler 解析闭式，方法学独立",
        "note": "v0.9.91 Batch B-11：golden=17.771531753 / cand |Δ|=8.78e-12（余量 1.1e9×）；定档 dt=0.008（原 dt=0.002 残差 2.1e-13 正落 round-off 地板——本批血案 8）。",
    },
    "B193": {
        "title": "平行同轴等尺寸矩形角系数 F₁₂（a=b=c=1，辐射传热）",
        "metric": "view_factor",
        "oracle": "closed_form(平行同轴等尺寸矩形解析式, 4D 张量积复合 Simpson n=16)",
        "tol": 0.001,
        "default_params": {"a": 1.0, "b": 1.0, "c": 1.0},
        "golden_fn": golden_b193,
        "candidate": "b193_vf_parallel_1x1_cand",
        "candidate_desc": "角系数由 F₁₂=(1/A₁)∫∫cosθ₁cosθ₂/(πR²)dA₂dA₁ 的 4D 张量积复合 Simpson 直接求积导出 ↔ 解析闭式，方法学独立",
        "note": "v0.9.91 Batch B-11：golden=0.199824896（文献 ≈0.1998）/ cand |Δ|=7.84e-07（余量 1275×）；tol 收紧至 1e-3 以保住 10% 几何扰动的判别力。",
    },
    "B194": {
        "title": "平行同轴等尺寸矩形角系数 F₁₂（a=1, b=2, c=1）",
        "metric": "view_factor",
        "oracle": "closed_form(平行同轴等尺寸矩形解析式, 4D 复合 Simpson n=16)",
        "tol": 0.001,
        "default_params": {"a": 1.0, "b": 2.0, "c": 1.0},
        "golden_fn": golden_b194,
        "candidate": "b194_vf_parallel_1x2_cand",
        "candidate_desc": "非方形平行矩形角系数由 4D 复合 Simpson 求积导出 ↔ 解析闭式，方法学独立",
        "note": "v0.9.91 Batch B-11：golden=0.285875385 / cand |Δ|=3.15e-06（余量 317×）。",
    },
    "B195": {
        "title": "垂直共边矩形角系数 F₁₂（A=B=1，辐射传热）",
        "metric": "view_factor",
        "oracle": "closed_form(垂直共边矩形解析式（含对数/反正切）, 4D 张量积分块复合 Simpson n=96)",
        "tol": 0.005,
        "default_params": {"a": 1.0, "b": 1.0, "c": 1.0},
        "golden_fn": golden_b195,
        "candidate": "b195_vf_perp_common_edge_1x1_cand",
        "candidate_desc": "垂直共边角系数由 R²=x²+(y₂−y₁)²+z² 的 4D 分块复合 Simpson 求积导出 ↔ 解析闭式，方法学独立",
        "note": ("v0.9.91 Batch B-11：golden=0.200043776（文献 ≈0.2000）/ cand |Δ|=1.80e-03（余量 2.8×，本批最小）。"
                 "共边角点 R²→0 使被积函数发散 ⇒ 仅 O(n⁻¹) 收敛（固有性质，慢收敛正是「真数值法」的正面证据）；"
                 "定档 n=96（分块累加破 (n+1)⁴ 内存墙——本批血案 7）。"),
    },
    "B196": {
        "title": "垂直共边矩形角系数 F₁₂（A=2, B=1）",
        "metric": "view_factor",
        "oracle": "closed_form(垂直共边矩形解析式, 4D 分块复合 Simpson n=96)",
        "tol": 0.005,
        "default_params": {"a": 2.0, "b": 1.0, "c": 1.0},
        "golden_fn": golden_b196,
        "candidate": "b196_vf_perp_common_edge_2x1_cand",
        "candidate_desc": "垂直共边角系数（A=2,B=1）由 4D 分块复合 Simpson 求导 ↔ 解析闭式，方法学独立",
        "note": ("v0.9.91 Batch B-11：golden=0.116426301 / cand |Δ|=1.70e-03（余量 2.9×）。"
                 "诚实边界：反向注册键 = a（1.9~2.2×tol）；b 为薄键（1.03~1.16×），c 为弱键（0.89~1.00×，抓不住）——如实登记不掩盖。"),
    },
    "B197": {
        "title": "Voigt 谱线轮廓 V(0; σ=1, γ=1)（多普勒 ⊗ 洛伦兹，线心）",
        "metric": "voigt_profile",
        "oracle": "special_function(scipy.special.voigt_profile 机器精度（Faddeeva/wofz）, 卷积定义式 sinh 换元 + 复合 Simpson n=48)",
        "tol": 0.002,
        "default_params": {"sigma": 1.0, "gamma": 1.0},
        "golden_fn": golden_b197,
        "candidate": "b197_voigt_s1_g1_x0_cand",
        "candidate_desc": "Voigt 轮廓由卷积定义式数值积分（τ=x+γ·sinh u 解析换元）导出 ↔ scipy voigt_profile 特殊函数，方法学独立",
        "note": "v0.9.91 Batch B-11：golden=0.208709281 / cand |Δ|=1.26e-10（余量 1.6e7×）；n=48（n=64 残差 1.7e-13 会踩 D-criterion 的 1e-12 地板——本批血案 11）。",
    },
    "B198": {
        "title": "Voigt 谱线轮廓 V(2; σ=1, γ=0.5)（远翼）",
        "metric": "voigt_profile",
        "oracle": "special_function(scipy.special.voigt_profile 机器精度, sinh 换元 + 复合 Simpson n=64)",
        "tol": 0.002,
        "default_params": {"sigma": 1.0, "gamma": 0.5, "x": 2.0},
        "golden_fn": golden_b198,
        "candidate": "b198_voigt_s1_g05_x2_cand",
        "candidate_desc": "Voigt 远翼值由卷积数值积分导出 ↔ scipy voigt_profile，方法学独立",
        "note": "v0.9.91 Batch B-11：golden=0.082424083 / cand |Δ|=6.90e-10（余量 2.9e6×）；判据 D 扫描须 n≥24（n≤20 高斯峰欠采样 ⇒ 残差链抖动非单调——本批血案 4 的近亲）。",
    },
    "B199": {
        "title": "Voigt 谱线轮廓 V(0; σ=0.5, γ=2)（洛伦兹主导，线心）",
        "metric": "voigt_profile",
        "oracle": "special_function(scipy.special.voigt_profile 机器精度, sinh 换元 + 复合 Simpson n=32)",
        "tol": 0.001,
        "default_params": {"sigma": 0.5, "gamma": 2.0},
        "golden_fn": golden_b199,
        "candidate": "b199_voigt_s05_g2_x0_cand",
        "candidate_desc": "洛伦兹主导 Voigt 线心值由卷积数值积分导出 ↔ scipy voigt_profile，方法学独立",
        "note": "v0.9.91 Batch B-11：golden=0.150657586 / cand |Δ|=1.23e-09（余量 8.1e5×）；n=32（σ<γ 极光滑，n=64 残差 2.8e-17 直落噪声地板——本批血案 8）。",
    },
    "B200": {
        "title": "Voigt 谱线轮廓 V(3; σ=2, γ=0.5)（深远翼）",
        "metric": "voigt_profile",
        "oracle": "special_function(scipy.special.voigt_profile 机器精度, sinh 换元 + 复合 Simpson n=64)",
        "tol": 0.001,
        "default_params": {"sigma": 2.0, "gamma": 0.5, "x": 3.0},
        "golden_fn": golden_b200,
        "candidate": "b200_voigt_s2_g05_x3_cand",
        "candidate_desc": "Voigt 深远翼值由卷积数值积分导出 ↔ scipy voigt_profile，方法学独立",
        "note": ("v0.9.91 Batch B-11：golden=0.067732553 / cand |Δ|=1.88e-09（余量 5.3e5×）。"
                 "诚实边界：反向注册键 σ/x；γ 为弱键（0.11~0.14×，抓不住——γ≪σ 且 x 深在线翼，物理上正确）——如实登记不掩盖。"),
    },
    # -----------------------------------------------------------------------
    # Batch B-12（v0.9.92 · 腿① 续加锚稀释 terminal）：四族全新数值方法/代数/特殊函数类
    # —— 正交多项式高斯求积 / 连分数有理逼近 / Durand–Kerner 同时迭代求根 / ₂F₁ 高斯超几何 Euler 积分表示。
    # 同源体检（三条红线）详见 _batch_b12_numeric 模块 docstring。
    # 🔴 逐锚 tol：B202 因 Γ 在 1.5 附近平坦、×1.1 信号仅 2.6e-3 ⇒ 收紧至 0.001（收紧≠放宽）。
    # -----------------------------------------------------------------------
    "B201": {
        "title": "Gauss–Legendre 高斯求积 ∫₀¹ x^{−0.5}dx = 2（端点幂奇性）",
        "metric": "gauss_quadrature",
        "oracle": "closed_form(∫₀¹ x^{−p}dx = 1/(1−p) 初等闭式, Gauss–Legendre n=256 节点高斯求积)",
        "tol": 0.01,
        "default_params": {"p": 0.5},
        "golden_fn": golden_b201,
        "candidate": "b201_gl_pow_singular_cand",
        "candidate_desc": "端点幂奇性积分由 Gauss–Legendre n 节点高斯求积导出 ↔ 1/(1−p) 闭式，方法学独立",
        "note": "v0.9.92 Batch B-12：golden=2.000000000 / cand |Δ|=3.395e-03（余量 2.9×，本批最小）；被积 x^{−0.5} 端点奇性 ⇒ 仅代数收敛，判据 D 扫 n 单调。",
    },
    "B202": {
        "title": "Gauss–Laguerre 高斯求积 ∫₀^∞ e^{−x}x^{0.5}dx = Γ(3/2)",
        "metric": "gauss_quadrature",
        "oracle": "closed_form(∫₀^∞ e^{−x}x^q dx = Γ(q+1) 闭式, Gauss–Laguerre n=64 节点高斯求积)",
        "tol": 0.001,
        "default_params": {"q": 0.5},
        "golden_fn": golden_b202,
        "candidate": "b202_lag_frac_power_cand",
        "candidate_desc": "分数幂矩由 Gauss–Laguerre n 节点高斯求积导出 ↔ Γ(q+1) 闭式，方法学独立",
        "note": "v0.9.92 Batch B-12：golden=0.886226925 / cand |Δ|=2.012e-04（余量 5.0×）；q=0.5 时 x→0 导奇 ⇒ 仅代数收敛；Γ 在 1.5 附近平坦、×1.1 信号仅 2.6e-3 ⇒ 逐锚收紧 tol 至 0.001。",
    },
    "B203": {
        "title": "Gauss–Hermite 高斯求积 ∫_{−∞}^{∞} e^{−x²}|x|dx = 1",
        "metric": "gauss_quadrature",
        "oracle": "closed_form(∫_{−∞}^{∞} e^{−x²}|x|^p dx = Γ((p+1)/2) 闭式, Gauss–Hermite n=128 节点高斯求积)",
        "tol": 0.01,
        "default_params": {"p": 1.0},
        "golden_fn": golden_b203,
        "candidate": "b203_herm_abs_power_cand",
        "candidate_desc": "绝对值幂矩由 Gauss–Hermite n 节点高斯求积导出 ↔ Γ((p+1)/2) 闭式，方法学独立",
        "note": "v0.9.92 Batch B-12：golden=1.000000000 / cand |Δ|=3.222e-03（余量 3.1×）；p=1 时 |x| 在 x=0 不可导（拐点）⇒ 代数收敛。",
    },
    "B204": {
        "title": "Gauss–Chebyshev 高斯求积 ∫_{−1}¹ dx/((1+ax)√(1−x²)) = π/√(1−a²)",
        "metric": "gauss_quadrature",
        "oracle": "closed_form(∫_{−1}¹ dx/((1+ax)√(1−x²)) = π/√(1−a²) 闭式, Gauss–Chebyshev 第一类 n=12 节点高斯求积)",
        "tol": 0.01,
        "default_params": {"a": 0.9},
        "golden_fn": golden_b204,
        "candidate": "b204_cheb_lorentz_cand",
        "candidate_desc": "Lorentz 型加权积分由 Gauss–Chebyshev n 节点高斯求积导出 ↔ π/√(1−a²) 闭式，方法学独立",
        "note": "v0.9.92 Batch B-12：golden=7.207307841 / cand |Δ|=1.949e-04（余量 51.3×）；a→0.9 逼近奇点 ⇒ 几何收敛放缓（仍单调）。",
    },
    "B205": {
        "title": "tan(1) 的 Lambert 连分数收敛值（N 层截断）",
        "metric": "continued_fraction",
        "oracle": "closed_form(tan x 初等超越闭式, Lambert 连分数 N=4 层截断)",
        "tol": 0.01,
        "default_params": {"x": 1.0},
        "golden_fn": golden_b205,
        "candidate": "b205_cf_tan_cand",
        "candidate_desc": "tan x 由 Lambert 连分数 N 层截断递推导出 ↔ 初等超越闭式，方法学独立",
        "note": "v0.9.92 Batch B-12：golden=1.557407725 / cand |Δ|=3.068e-05（余量 326×）；连分数偶/奇收敛子夹逼 ⇒ |误差| 单调下降。",
    },
    "B206": {
        "title": "arctan(1)= π/4 的 Euler 连分数（N 层截断）",
        "metric": "continued_fraction",
        "oracle": "closed_form(arctan x 初等闭式, Euler 连分数 N=6 层截断)",
        "tol": 0.01,
        "default_params": {"x": 1.0},
        "golden_fn": golden_b206,
        "candidate": "b206_cf_arctan_cand",
        "candidate_desc": "arctan x 由 Euler 连分数 N 层截断导出 ↔ π/4 闭式，方法学独立",
        "note": "v0.9.92 Batch B-12：golden=0.785398163 / cand |Δ|=3.231e-05（余量 309.5×）；系数 b₁=x、b_k=((k−1)x)²（原写 b_k=(kx)² 全盘错 ⇒ 只有 N=80 对精确值的闭式自检能抓住，本批血案 4）。",
    },
    "B207": {
        "title": "coth(1) 的双曲连分数（N 层截断）",
        "metric": "continued_fraction",
        "oracle": "closed_form(coth x 初等闭式, 双曲连分数 N=3 层截断)",
        "tol": 0.01,
        "default_params": {"x": 1.0},
        "golden_fn": golden_b207,
        "candidate": "b207_cf_coth_cand",
        "candidate_desc": "coth x 由双曲连分数 N 层截断（含 1/x 主项）导出 ↔ 初等闭式，方法学独立",
        "note": "v0.9.92 Batch B-12：golden=1.313035285 / cand |Δ|=8.193e-06（余量 1220.6×）。",
    },
    "B208": {
        "title": "√2 的平方根连分数逼近（N 层截断）",
        "metric": "continued_fraction",
        "oracle": "closed_form(√(1+x) 初等闭式, 平方根连分数 N=6 层截断)",
        "tol": 0.01,
        "default_params": {"x": 1.0},
        "golden_fn": golden_b208,
        "candidate": "b208_cf_sqrt1p_cand",
        "candidate_desc": "√(1+x) 由平方根连分数 N 层截断导出 ↔ 初等闭式（√2），方法学独立",
        "note": "v0.9.92 Batch B-12：golden=1.414213562 / cand |Δ|=1.238e-05（余量 807.8×）。",
    },
    "B209": {
        "title": "x³−27 = 0 的实根（Durand–Kerner 同时迭代）",
        "metric": "polynomial_root",
        "oracle": "closed_form(xⁿ−a=0 的实根 a^{1/n} 闭式, Durand–Kerner 同时迭代 m=8 步)",
        "tol": 0.01,
        "default_params": {"a": 27.0},
        "golden_fn": golden_b209,
        "candidate": "b209_dk_x3_27_cand",
        "candidate_desc": "x³−27 实根由 Durand–Kerner 同时迭代导出（按实部最大选根，不借 golden）↔ a^{1/3} 闭式，方法学独立",
        "note": "v0.9.92 Batch B-12：golden=3.000000000 / cand |Δ|=5.749e-04（余量 17.4×）；DK 迭代 m 为判据 D 离散参数，收敛单调。",
    },
    "B210": {
        "title": "x⁴−16 = 0 的实根（Durand–Kerner）",
        "metric": "polynomial_root",
        "oracle": "closed_form(x⁴−a=0 实根 a^{1/4} 闭式, Durand–Kerner 同时迭代 m=8 步)",
        "tol": 0.01,
        "default_params": {"a": 16.0},
        "golden_fn": golden_b210,
        "candidate": "b210_dk_x4_16_cand",
        "candidate_desc": "x⁴−16 实根由 DK 同时迭代导出 ↔ a^{1/4} 闭式，方法学独立",
        "note": "v0.9.92 Batch B-12：golden=2.000000000 / cand |Δ|=3.146e-08（余量 3.18e5×）。",
    },
    "B211": {
        "title": "x⁵−243 = 0 的实根（Durand–Kerner）",
        "metric": "polynomial_root",
        "oracle": "closed_form(x⁵−a=0 实根 a^{1/5} 闭式, Durand–Kerner 同时迭代 m=17 步)",
        "tol": 0.01,
        "default_params": {"a": 243.0},
        "golden_fn": golden_b211,
        "candidate": "b211_dk_x5_243_cand",
        "candidate_desc": "x⁵−243 实根由 DK 同时迭代导出 ↔ a^{1/5} 闭式，方法学独立",
        "note": "v0.9.92 Batch B-12：golden=3.000000000 / cand |Δ|=1.092e-04（余量 91.6×）；5 根情况收敛更慢 ⇒ 定档 m=17。",
    },
    "B212": {
        "title": "x⁶−64 = 0 的实根（Durand–Kerner）",
        "metric": "polynomial_root",
        "oracle": "closed_form(x⁶−a=0 实根 a^{1/6} 闭式, Durand–Kerner 同时迭代 m=16 步)",
        "tol": 0.01,
        "default_params": {"a": 64.0},
        "golden_fn": golden_b212,
        "candidate": "b212_dk_x6_64_cand",
        "candidate_desc": "x⁶−64 实根由 DK 同时迭代导出 ↔ a^{1/6} 闭式，方法学独立",
        "note": "v0.9.92 Batch B-12：golden=2.000000000 / cand |Δ|=6.426e-04（余量 15.6×）；DK 残差链在 m=12→13 处非单调（轨迹跳变）⇒ 扫描网格跳过 m=13,14（本批血案 3）。",
    },
    "B213": {
        "title": "₂F₁(½,½;3/2;z²) = arcsin(z)/z（Euler 积分表示）",
        "metric": "hypergeometric",
        "oracle": "closed_form(arcsin(z)/z 初等闭式, ₂F₁ Euler 积分表示 + Gauss–Jacobi 求积 n=6)",
        "tol": 0.01,
        "default_params": {"z": 0.9},
        "golden_fn": golden_b213,
        "candidate": "b213_hyp_asin_cand",
        "candidate_desc": "₂F₁(½,½;3/2;z²) 由 Euler 积分表示 + Gauss–Jacobi 求积导出 ↔ arcsin(z)/z 闭式，方法学独立",
        "note": "v0.9.92 Batch B-12：golden=1.244188350 / cand |Δ|=3.073e-06（余量 3254×）。",
    },
    "B214": {
        "title": "₂F₁(½,1;3/2;z²) = arctanh(z)/z（Euler 积分表示）",
        "metric": "hypergeometric",
        "oracle": "closed_form(arctanh(z)/z 初等闭式, ₂F₁ Euler 积分表示 + Gauss–Jacobi 求积 n=6)",
        "tol": 0.01,
        "default_params": {"z": 0.9},
        "golden_fn": golden_b214,
        "candidate": "b214_hyp_atanh_cand",
        "candidate_desc": "₂F₁(½,1;3/2;z²) 由 Euler 积分表示 + Gauss–Jacobi 求积导出 ↔ arctanh(z)/z 闭式，方法学独立",
        "note": "v0.9.92 Batch B-12：golden=1.635799433 / cand |Δ|=7.054e-06（余量 1418×）。",
    },
    "B215": {
        "title": "₂F₁(½,1;3/2;−z²) = arctan(z)/z（Euler 积分表示）",
        "metric": "hypergeometric",
        "oracle": "closed_form(arctan(z)/z 初等闭式, ₂F₁ Euler 积分表示 + Gauss–Jacobi 求积 n=2)",
        "tol": 0.01,
        "default_params": {"z": 0.9},
        "golden_fn": golden_b215,
        "candidate": "b215_hyp_atan_cand",
        "candidate_desc": "₂F₁(½,1;3/2;−z²) 由 Euler 积分表示 + Gauss–Jacobi 求积导出 ↔ arctan(z)/z 闭式，方法学独立",
        "note": "v0.9.92 Batch B-12：golden=0.814239002 / cand |Δ|=1.401e-04（余量 71.4×）。",
    },
    "B216": {
        "title": "₂F₁(½,½;3/2;−z²) = arcsinh(z)/z（Euler 积分表示）",
        "metric": "hypergeometric",
        "oracle": "closed_form(arcsinh(z)/z 初等闭式, ₂F₁ Euler 积分表示 + Gauss–Jacobi 求积 n=4)",
        "tol": 0.01,
        "default_params": {"z": 0.9},
        "golden_fn": golden_b216,
        "candidate": "b216_hyp_asinh_cand",
        "candidate_desc": "₂F₁(½,½;3/2;−z²) 由 Euler 积分表示 + Gauss–Jacobi 求积导出 ↔ arcsinh(z)/z 闭式，方法学独立",
        "note": "v0.9.92 Batch B-12：golden=0.898741040 / cand |Δ|=6.546e-08（余量 1.53e5×）；反向信号/tol=1.56×（本批最小，仍>1.4×）。",
    },
    # Batch B-13（v0.9.93 · 腿① 续加锚稀释 terminal）：四族全新数值方法/算子/方程类
    #   A 分数阶微积分 Grünwald–Letnikov（非整数阶非局部算子）/ B 矩阵指数 scaling–squaring /
    #   C 变分极值数值优化（梯度下降）/ D 第二类 Volterra 积分方程（分块梯形递推）。
    # 同源体检（三条红线）与被否 8 候选详见 _batch_b13_numeric 模块 docstring。
    #   被否：Airy≡B-6 / erfc≡B30 / 合流超几何≡B-12 族 D / Talbot 逆变换（超收敛地板）/
    #   复步长微分（残差恒机器精度）/ Wynn ε 序列加速（精确加速⇒地板）/ 2D 泊松 FDM≡drift_diffusion_2d / 蒙特卡洛。
    "B217": {
        "title": "分数阶导数 D^0.5[1] = 1/√(π·t)（Grünwald–Letnikov 非局部卷积差分）",
        "metric": "fractional_derivative",
        "oracle": "closed_form(Riemann–Liouville 初等闭式 t^{−α}/Γ(1−α), GL 卷积差分 n=3200)",
        "tol": 0.01,
        "default_params": {"alpha": 0.5, "t": 1.0},
        "golden_fn": golden_b217,
        "candidate": "b217_gl_dhalf_const_cand",
        "candidate_desc": "D^0.5[1] 由 Grünwald–Letnikov 卷积差分（非整数阶、非局部算子）导出 ↔ 1/√(πt) 闭式，方法学独立",
        "note": "v0.9.93 Batch B-13：golden=0.564189584 / cand |Δ|=2.204e-05（余量 453.8×）；GL 为 O(h) 一阶差分 ⇒ 残差随 n 单调减半（判据 D）。",
    },
    "B218": {
        "title": "分数阶导数 D^0.5[t] = √2/Γ(1.5)（GL 卷积差分，t=2）",
        "metric": "fractional_derivative",
        "oracle": "closed_form(初等闭式 Γ(2)/Γ(2−α)·t^{1−α}, GL 卷积差分 n=3200)",
        "tol": 0.01,
        "default_params": {"alpha": 0.5, "t": 2.0},
        "golden_fn": golden_b218,
        "candidate": "b218_gl_dhalf_linear_cand",
        "candidate_desc": "D^0.5[t] 由 Grünwald–Letnikov 卷积差分导出 ↔ √2/Γ(1.5) 闭式，方法学独立",
        "note": "v0.9.93 Batch B-13：golden=1.595769122 / cand |Δ|=6.233e-05（余量 160.4×）；原取 t=1 且只扰 α ⇒ 信号仅 0.07×tol（Γ 在 1.5 附近平坦 + t^{1−α}≡1）⇒ 改 t=2.0 放大信号至 5.34×tol（本批血案 5）。",
    },
    "B219": {
        "title": "分数阶导数 D^0.5[t³] = 6/Γ(3.5)",
        "metric": "fractional_derivative",
        "oracle": "closed_form(初等闭式 Γ(4)/Γ(4−α)·t^{3−α}, GL 卷积差分 n=3200)",
        "tol": 0.01,
        "default_params": {"alpha": 0.5, "t": 1.0},
        "golden_fn": golden_b219,
        "candidate": "b219_gl_dhalf_cubic_cand",
        "candidate_desc": "D^0.5[t³] 由 Grünwald–Letnikov 卷积差分导出 ↔ 6/Γ(3.5) 闭式，方法学独立",
        "note": "v0.9.93 Batch B-13：golden=1.805406667 / cand |Δ|=3.526e-04（余量 28.4×，本批最小）；p=3 ⇒ 卷积和幅度大、O(h) 收敛常数最大。",
    },
    "B220": {
        "title": "分数阶导数 D^0.25[t²] = 2/Γ(2.75)",
        "metric": "fractional_derivative",
        "oracle": "closed_form(初等闭式 Γ(3)/Γ(3−α)·t^{2−α}, GL 卷积差分 n=3200)",
        "tol": 0.01,
        "default_params": {"alpha": 0.25, "t": 1.0},
        "golden_fn": golden_b220,
        "candidate": "b220_gl_dquarter_quad_cand",
        "candidate_desc": "D^0.25[t²] 由 Grünwald–Letnikov 卷积差分导出 ↔ 2/Γ(2.75) 闭式，方法学独立",
        "note": "v0.9.93 Batch B-13：golden=1.243503145 / cand |Δ|=8.500e-05（余量 117.6×）；α=0.25 ⇒ 非整阶远离整数阶极限。",
    },
    "B221": {
        "title": "状态转移矩阵 exp(At)[0,1] = −sin t（旋转生成元）",
        "metric": "matrix_exponential",
        "oracle": "closed_form(线性系统状态转移矩阵初等闭式 −sin t, scaling–squaring s=8 + 截断 Taylor n=3)",
        "tol": 0.01,
        "default_params": {"t": 1.0},
        "golden_fn": golden_b221,
        "candidate": "b221_matexp_rot1_cand",
        "candidate_desc": "exp(At)[0,1] 由自研 scaling–squaring（Taylor 截断 + 自乘 2^8）导出 ↔ −sin t 闭式，方法学独立",
        "note": "v0.9.93 Batch B-13：golden=-0.841470985 / cand |Δ|=2.086e-09（余量 4.79e6×）；平方次数 s=8 会放大舍入 ×2^s ⇒ 扫描上限收在 n≤4（n≥5 残差已沉 4.77e-15 地板，本批血案 2）。",
    },
    "B222": {
        "title": "状态转移矩阵 exp(At)[0,1] = −sin(2.5t)",
        "metric": "matrix_exponential",
        "oracle": "closed_form(初等闭式 −sin(2.5t), scaling–squaring s=8 + 截断 Taylor n=3)",
        "tol": 0.01,
        "default_params": {"t": 1.0},
        "golden_fn": golden_b222,
        "candidate": "b222_matexp_rot25_cand",
        "candidate_desc": "exp(At)[0,1]（ω=2.5 旋转）由自研 scaling–squaring 导出 ↔ −sin(2.5t) 闭式，方法学独立",
        "note": "v0.9.93 Batch B-13：golden=-0.598472144 / cand |Δ|=5.866e-08（余量 1.70e5×）；反向信号/tol=21.68×。",
    },
    "B223": {
        "title": "状态转移矩阵 exp(At)[0,0] = e^{−t}（对角阻尼）",
        "metric": "matrix_exponential",
        "oracle": "closed_form(初等闭式 e^{−t}, scaling–squaring s=8 + 截断 Taylor n=3)",
        "tol": 0.01,
        "default_params": {"t": 1.5},
        "golden_fn": golden_b223,
        "candidate": "b223_matexp_damp_cand",
        "candidate_desc": "exp(At)[0,0]（A=diag(−1,−2)，t=1.5）由自研 scaling–squaring 导出 ↔ e^{−t} 闭式，方法学独立",
        "note": "v0.9.93 Batch B-13：golden=0.223130160 / cand |Δ|=2.819e-09（余量 3.55e6×）；对角矩阵 ⇒ Taylor 与 λ 级数等价但经矩阵幂路径。",
    },
    "B224": {
        "title": "状态转移矩阵 exp(At)[0,0] = 2e^{−t} − e^{−2t}（两模，本征值 −1,−2）",
        "metric": "matrix_exponential",
        "oracle": "closed_form(初等闭式 2e^{−t}−e^{−2t}, scaling–squaring s=8 + 截断 Taylor n=3)",
        "tol": 0.01,
        "default_params": {"t": 1.0},
        "golden_fn": golden_b224,
        "candidate": "b224_matexp_two_mode_cand",
        "candidate_desc": "exp(At)[0,0]（A=[[0,1],[−2,−3]]）由自研 scaling–squaring 导出 ↔ 2e^{−t}−e^{−2t} 闭式，方法学独立",
        "note": "v0.9.93 Batch B-13：golden=0.600423599 / cand |Δ|=3.578e-09（余量 2.79e6×）；非对角耦合 ⇒ 需真实矩阵幂而非标量指数。",
    },
    "B225": {
        "title": "变分极小 a(x⁴/4−x²/2) 的极小值 = −a/4（非谐双阱势）",
        "metric": "variational_minimum",
        "oracle": "closed_form(解析极小值 −a/4, 固定步长梯度下降 k=12)",
        "tol": 0.01,
        "default_params": {"a": 1.0},
        "golden_fn": golden_b225,
        "candidate": "b225_gd_quartic_cand",
        "candidate_desc": "a(x⁴/4−x²/2) 的极小值由固定步长梯度下降（x₀=1.5, η=0.25, k 步）导出 ↔ −a/4 解析极小，方法学独立",
        "note": "v0.9.93 Batch B-13：golden=-0.250000000 / cand |Δ|=1.933e-10（余量 5.17e7×）；f 沿负梯度下降 ⇒ 残差链可证严格单调（黄金分割的 running-min 有平坦段，本批血案 3）。",
    },
    "B226": {
        "title": "变分极小 a/x + x 的极小值 = 2√a（AM–GM）",
        "metric": "variational_minimum",
        "oracle": "closed_form(解析极小值 2√a, 固定步长梯度下降 k=12)",
        "tol": 0.01,
        "default_params": {"a": 1.0},
        "golden_fn": golden_b226,
        "candidate": "b226_gd_amgm_cand",
        "candidate_desc": "a/x + x 的极小值由固定步长梯度下降（x₀=3, η=0.30, k 步）导出 ↔ 2√a 解析极小，方法学独立",
        "note": "v0.9.93 Batch B-13：golden=2.000000000 / cand |Δ|=1.672e-04（余量 59.8×，本批最小）；收敛比仅 0.4 ⇒ 12 步后仍留 1.7e-4（>1e-12，不踩 D 判据门槛）。",
    },
    "B227": {
        "title": "变分极小 x ln x − b x 的极小值 = −e^{b−1}（自由能/熵项）",
        "metric": "variational_minimum",
        "oracle": "closed_form(解析极小值 −e^{b−1}, 固定步长梯度下降 k=12)",
        "tol": 0.01,
        "default_params": {"b": 0.5},
        "golden_fn": golden_b227,
        "candidate": "b227_gd_free_energy_cand",
        "candidate_desc": "x ln x − b x 的极小值由固定步长梯度下降（x₀=2, η=0.30, k 步）导出 ↔ −e^{b−1} 解析极小，方法学独立",
        "note": "v0.9.93 Batch B-13：golden=-0.606530660 / cand |Δ|=3.819e-06（余量 2618.6×）；超越极小（ln x = b−1）非代数可解 ⇒ 数值迭代必要。",
    },
    "B228": {
        "title": "变分极小 e^x − c x 的极小值 = c − c·ln c（指数型势）",
        "metric": "variational_minimum",
        "oracle": "closed_form(解析极小值 c−c·ln c, 固定步长梯度下降 k=12)",
        "tol": 0.01,
        "default_params": {"c": 2.0},
        "golden_fn": golden_b228,
        "candidate": "b228_gd_exp_potential_cand",
        "candidate_desc": "e^x − c x 的极小值由固定步长梯度下降（x₀=0, η=0.30, k 步）导出 ↔ c−c ln c 解析极小，方法学独立",
        "note": "v0.9.93 Batch B-13：golden=0.613705639 / cand |Δ|=6.999e-10（余量 1.43e7×）；反向信号/tol=14.83×。",
    },
    "B229": {
        "title": "第二类 Volterra 积分方程 φ(1)=[1−λe^{−(1−λ)}]/(1−λ)（K=e^{−(x−t)}, λ=0.5）",
        "metric": "integral_equation",
        "oracle": "closed_form(积分方程解析解 [1−λe^{−(1−λ)x}]/(1−λ), 分块梯形递推 n=1024)",
        "tol": 0.01,
        "default_params": {"lam": 0.5},
        "golden_fn": golden_b229,
        "candidate": "b229_volterra_exp_cand",
        "candidate_desc": "φ(1) 由分块梯形递推（含 k=j 隐式项移项）导出 ↔ 积分方程解析解，方法学独立",
        "note": "v0.9.93 Batch B-13：golden=1.393469340 / cand |Δ|=5.651e-08（余量 1.77e5×）；梯形 O(h²) ⇒ 残差随 n 单调降 4×/倍（判据 D）。",
    },
    "B230": {
        "title": "第二类 Volterra 积分方程 φ(1.5)（K=e^{−(x−t)}, λ=0.8）",
        "metric": "integral_equation",
        "oracle": "closed_form(积分方程解析解 [1−λe^{−1.5(1−λ)}]/(1−λ), 分块梯形递推 n=1024)",
        "tol": 0.01,
        "default_params": {"lam": 0.8},
        "golden_fn": golden_b230,
        "candidate": "b230_volterra_exp_long_cand",
        "candidate_desc": "φ(1.5) 由分块梯形递推导出 ↔ 积分方程解析解，方法学独立",
        "note": "v0.9.93 Batch B-13：golden=2.036727117 / cand |Δ|=5.200e-07（余量 1.92e4×）；λ→1 使解幅度放大（1/(1−λ) 型）⇒ 绝对残差同比例放大。",
    },
    "B231": {
        "title": "第二类 Volterra 积分方程 φ(1)=2−e^{−1}（K=e^{−2(x−t)}, λ=1）",
        "metric": "integral_equation",
        "oracle": "closed_form(积分方程解析解 [2−λe^{−(2−λ)x}]/(2−λ), 分块梯形递推 n=1024)",
        "tol": 0.01,
        "default_params": {"lam": 1.0},
        "golden_fn": golden_b231,
        "candidate": "b231_volterra_exp2_cand",
        "candidate_desc": "φ(1) 由分块梯形递推导出 ↔ 积分方程解析解 2−e^{−1}，方法学独立",
        "note": "v0.9.93 Batch B-13：golden=1.632120559 / cand |Δ|=3.727e-07（余量 2.68e4×）；核衰减率 2 ⇒ K(0)=1≠0，隐式项必须移项（本批血案 4）。",
    },
    "B232": {
        "title": "第二类 Volterra 积分方程 φ(1)=cosh 1（K=x−t, λ=1）",
        "metric": "integral_equation",
        "oracle": "closed_form(积分方程解析解 cosh(√λ x), 分块梯形递推 n=1024)",
        "tol": 0.01,
        "default_params": {"lam": 1.0},
        "golden_fn": golden_b232,
        "candidate": "b232_volterra_ramp_cand",
        "candidate_desc": "φ(1) 由分块梯形递推导出 ↔ 积分方程解析解 cosh(√λx)，方法学独立",
        "note": "v0.9.93 Batch B-13：golden=1.543080635 / cand |Δ|=4.670e-08（余量 2.14e5×）；线性核 K(0)=0 ⇒ k=j 项显式，与 B229/B231 的隐式情形互补。",
    },
    # Batch B-14（v0.9.94 · 腿① 续加锚稀释 terminal）：四族全新方程类/数值方法类
    #   A 定常对流–扩散方程（一维指数边界层）· 三点中心差分 + Thomas 追赶法
    #   B 第二类 Fredholm 积分方程（可分核）· Nyström 求积（均匀节点梯形权重）
    #   C 三次样条插值逼近（逼近论）· 均匀节点自然三次样条
    #   D 非线性两点边值问题 · RK4 打靶法（网格扫符号变化 + 有限性过滤 + 割线/二分混合）
    # 同源体检（三条红线）与被否 8 候选详见 _batch_b14_numeric 模块 docstring。
    #   被否：Biot–Savart 数值积分（近奇性+求积类近）/ Reynolds 润滑方程（与族 A 同构）/
    #   三次样条求积（≡B-12 求积类）/ Kronig–Penney 能带（≡B-10 Mathieu）/ QR 迭代（无离散
    #   参数+本征值已占用）/ CG·Jacobi（线性求解类+单调性需引用 golden ⇒ 自证桩）/
    #   Romberg–Richardson（超收敛沉地板）/ 3D Laplace·2D 泊松+SOR（≡ drift_diffusion_2d）/ 蒙特卡洛。
    "B233": {
        "title": "定常对流–扩散方程 θ(0.9)（Pe=3.5，一维指数边界层）",
        "metric": "convection_diffusion",
        "oracle": "closed_form(θ(x)=(e^{Pe·x}−1)/(e^{Pe}−1), Pe=u/ε, 三点中心差分+Thomas 追赶法 n=640)",
        "tol": 0.01,
        "default_params": {"pe": 3.5},
        "golden_fn": golden_b233,
        "candidate": "b233_conv_diff_pe35_cand",
        "candidate_desc": "θ(0.9) 由三点中心差分 + Thomas 追赶法导出 ↔ 定常对流–扩散方程闭式解，方法学独立",
        "note": "v0.9.94 Batch B-14：golden=0.695492768 / cand |Δ|=5.511e-07（余量 1.81e4×）；中心差分 O(h²) ⇒ 残差随 n 单调降 ~4×/倍（判据 D）。",
    },
    "B234": {
        "title": "定常对流–扩散方程 θ(0.9)（Pe=5，一维指数边界层）",
        "metric": "convection_diffusion",
        "oracle": "closed_form(θ(x)=(e^{Pe·x}−1)/(e^{Pe}−1), Pe=u/ε, 三点中心差分+Thomas 追赶法 n=640)",
        "tol": 0.01,
        "default_params": {"pe": 5.0},
        "golden_fn": golden_b234,
        "candidate": "b234_conv_diff_pe50_cand",
        "candidate_desc": "θ(0.9) 由三点中心差分 + Thomas 追赶法导出 ↔ 定常对流–扩散方程闭式解，方法学独立",
        "note": "v0.9.94 Batch B-14：golden=0.603861499 / cand |Δ|=1.485e-06（余量 6735.7×）；Pe=5 ⇒ 边界层厚 ~0.2，n=640 分辨。",
    },
    "B235": {
        "title": "定常对流–扩散方程 θ(0.9)（Pe=10，一维指数边界层）",
        "metric": "convection_diffusion",
        "oracle": "closed_form(θ(x)=(e^{Pe·x}−1)/(e^{Pe}−1), Pe=u/ε, 三点中心差分+Thomas 追赶法 n=640)",
        "tol": 0.01,
        "default_params": {"pe": 10.0},
        "golden_fn": golden_b235,
        "candidate": "b235_conv_diff_pe100_cand",
        "candidate_desc": "θ(0.9) 由三点中心差分 + Thomas 追赶法导出 ↔ 定常对流–扩散方程闭式解，方法学独立",
        "note": "v0.9.94 Batch B-14：golden=0.367850742 / cand |Δ|=7.479e-06（余量 1337.0×）；反向信号/tol=3.50×。",
    },
    "B236": {
        "title": "定常对流–扩散方程 θ(0.9)（Pe=20，一维指数边界层）",
        "metric": "convection_diffusion",
        "oracle": "closed_form(θ(x)=(e^{Pe·x}−1)/(e^{Pe}−1), Pe=u/ε, 三点中心差分+Thomas 追赶法 n=640)",
        "tol": 0.01,
        "default_params": {"pe": 20.0},
        "golden_fn": golden_b236,
        "candidate": "b236_conv_diff_pe200_cand",
        "candidate_desc": "θ(0.9) 由三点中心差分 + Thomas 追赶法导出 ↔ 定常对流–扩散方程闭式解，方法学独立",
        "note": "v0.9.94 Batch B-14：golden=0.135335281 / cand |Δ|=2.203e-05（余量 454.0×）；观测点定 x*=0.9（血案 6：x*=0.7 落在边界层平台区 ⇒ 信号仅 0.11×tol）。",
    },
    "B237": {
        "title": "第二类 Fredholm 积分方程 φ(0.5)（K=1+xt, f=1, λ=0.5）",
        "metric": "integral_equation_2nd_kind",
        "oracle": "closed_form(resolvent 精确线性代数 c=(I−λA)^{−1}d, 均匀节点梯形权重 Nyström n=512)",
        "tol": 0.01,
        "default_params": {"lam": 0.5},
        "golden_fn": golden_b237,
        "candidate": "b237_fredholm_lin2_one_cand",
        "candidate_desc": "φ(0.5) 由均匀节点梯形 Nyström 求积（稠密 (I−λWK)φ=f）导出 ↔ 第二类 Fredholm 可分核 resolvent 闭式，方法学独立",
        "note": "v0.9.94 Batch B-14：golden=2.705882353（=77/28）/ cand |Δ|=3.168e-07（余量 3.16e4×）；梯形 O(h²) ⇒ 残差随 n 单调降 ~4×/倍（判据 D）。",
    },
    "B238": {
        "title": "第二类 Fredholm 积分方程 φ(0.5)（K=1+xt, f=e^x, λ=0.9）",
        "metric": "integral_equation_2nd_kind",
        "oracle": "closed_form(resolvent 精确线性代数 c=(I−λA)^{−1}d, 均匀节点梯形权重 Nyström n=512)",
        "tol": 0.01,
        "default_params": {"lam": 0.9},
        "golden_fn": golden_b238,
        "candidate": "b238_fredholm_lin2_exp_cand",
        "candidate_desc": "φ(0.5) 由均匀节点梯形 Nyström 求积导出 ↔ 第二类 Fredholm 可分核 resolvent 闭式，方法学独立",
        "note": "v0.9.94 Batch B-14：golden=-12.543502293 / cand |Δ|=4.586e-06（余量 2180.8×）；λ→1 使解幅度放大（1/(1−λ) 型）⇒ 绝对残差同比例放大。",
    },
    "B239": {
        "title": "第二类 Fredholm 积分方程 φ(0.5)（K=1+xt+x²t², f=1, λ=0.4）",
        "metric": "integral_equation_2nd_kind",
        "oracle": "closed_form(resolvent 精确线性代数 c=(I−λA)^{−1}d, 均匀节点梯形权重 Nyström n=512)",
        "tol": 0.01,
        "default_params": {"lam": 0.4},
        "golden_fn": golden_b239,
        "candidate": "b239_fredholm_lin3_one_cand",
        "candidate_desc": "φ(0.5) 由均匀节点梯形 Nyström 求积导出 ↔ 第二类 Fredholm 可分核 resolvent 闭式，方法学独立",
        "note": "v0.9.94 Batch B-14：golden=2.217351712 / cand |Δ|=1.070e-06（余量 9343.7×）；三基可分核（1, x, x²）⇒ 3×3 resolvent 代数解。",
    },
    "B240": {
        "title": "第二类 Fredholm 积分方程 φ(0.5)（K=1+xt, f=cosπx, λ=0.8）",
        "metric": "integral_equation_2nd_kind",
        "oracle": "closed_form(resolvent 精确线性代数 c=(I−λA)^{−1}d, 均匀节点梯形权重 Nyström n=512)",
        "tol": 0.01,
        "default_params": {"lam": 0.8},
        "golden_fn": golden_b240,
        "candidate": "b240_fredholm_lin2_cos_cand",
        "candidate_desc": "φ(0.5) 由均匀节点梯形 Nyström 求积导出 ↔ 第二类 Fredholm 可分核 resolvent 闭式，方法学独立",
        "note": "v0.9.94 Batch B-14：golden=6.079271019 / cand |Δ|=2.731e-05（余量 **366.2×，本批最小**）；cos 源项 ⇒ 梯形求积常数最大。",
    },
    "B241": {
        "title": "三次样条插值逼近 exp(0.5x)·sin(4x) 在 x₀=0.4585",
        "metric": "spline_approximation",
        "oracle": "closed_form(初等闭式精确值, 均匀节点自然三次样条 n=64)",
        "tol": 0.01,
        "default_params": {"xq": 0.4585},
        "golden_fn": golden_b241,
        "candidate": "b241_spline_e05s4_cand",
        "candidate_desc": "x₀ 点值由均匀节点自然三次样条（三对角解 M_j + 分段落值）导出 ↔ 初等闭式精确值，方法学独立",
        "note": "v0.9.94 Batch B-14：golden=1.214344511 / cand |Δ|=4.118e-08（余量 2.43e5×）；自然样条 O(h⁴) ⇒ 残差随 n 单调降 ~16×/倍（判据 D）；x₀ 由自动搜索选定，避开 dyadic 格点邻域（血案 5）。",
    },
    "B242": {
        "title": "三次样条插值逼近 arctan(3x) 在 x₀=0.4165",
        "metric": "spline_approximation",
        "oracle": "closed_form(初等闭式精确值, 均匀节点自然三次样条 n=64)",
        "tol": 0.01,
        "default_params": {"xq": 0.4165},
        "golden_fn": golden_b242,
        "candidate": "b242_spline_at3_cand",
        "candidate_desc": "x₀ 点值由均匀节点自然三次样条导出 ↔ 初等闭式精确值，方法学独立",
        "note": "v0.9.94 Batch B-14：golden=0.895860215 / cand |Δ|=3.960e-09（余量 2.53e6×）；反向信号/tol=4.59×。",
    },
    "B243": {
        "title": "三次样条插值逼近 exp(2x) 在 x₀=0.3960",
        "metric": "spline_approximation",
        "oracle": "closed_form(初等闭式精确值, 均匀节点自然三次样条 n=64)",
        "tol": 0.01,
        "default_params": {"xq": 0.396},
        "golden_fn": golden_b243,
        "candidate": "b243_spline_e2x_cand",
        "candidate_desc": "x₀ 点值由均匀节点自然三次样条导出 ↔ 初等闭式精确值，方法学独立",
        "note": "v0.9.94 Batch B-14：golden=2.207807629 / cand |Δ|=4.510e-09（余量 2.22e6×）；反向信号/tol=18.20×。",
    },
    "B244": {
        "title": "三次样条插值逼近 1/(0.5+x) 在 x₀=0.6040",
        "metric": "spline_approximation",
        "oracle": "closed_form(初等闭式精确值, 均匀节点自然三次样条 n=64)",
        "tol": 0.01,
        "default_params": {"xq": 0.604},
        "golden_fn": golden_b244,
        "candidate": "b244_spline_rec_cand",
        "candidate_desc": "x₀ 点值由均匀节点自然三次样条导出 ↔ 初等闭式精确值，方法学独立",
        "note": "v0.9.94 Batch B-14：golden=0.905797101 / cand |Δ|=1.889e-09（余量 **5.30e6×，本批最大**）；原 cos(4πx)@0.6245 方案 golden=0.00628 < tol ⇒ 换函数（血案 7，非放宽 tol）。",
    },
    "B245": {
        "title": "非线性两点边值 y''=6β²y², y(0)=1, y(1)=(1+β)^{−2}（β=1, y(0.5)）",
        "metric": "nonlinear_bvp_shooting",
        "oracle": "closed_form(y=(1+βx)^{−2}, RK4 打靶 + 割线/二分 n=32)",
        "tol": 0.01,
        "default_params": {"beta": 1.0},
        "golden_fn": golden_b245,
        "candidate": "b245_bvp_quad_cand",
        "candidate_desc": "y(0.5) 由 RK4 + 未知初斜率 s 打靶命中右端 BC 导出 ↔ 非线性 ODE 初等闭式 y=(1+βx)^{−2}，方法学独立",
        "note": "v0.9.94 Batch B-14：golden=0.444444444（=4/9）/ cand |Δ|=1.149e-07（余量 8.70e4×）；y(0)=1 下解唯一 ⇒ 右端值不可扰动 ⇒ 改形状参数 β 参数化（血案 4）。",
    },
    "B246": {
        "title": "非线性两点边值 y''=2β²y³, y(0)=1, y(1)=(1+β)^{−1}（β=1, y(0.5)）",
        "metric": "nonlinear_bvp_shooting",
        "oracle": "closed_form(y=(1+βx)^{−1}, RK4 打靶 + 割线/二分 n=32)",
        "tol": 0.01,
        "default_params": {"beta": 1.0},
        "golden_fn": golden_b246,
        "candidate": "b246_bvp_cubic_cand",
        "candidate_desc": "y(0.5) 由 RK4 + 未知初斜率 s 打靶命中右端 BC 导出 ↔ 非线性 ODE 初等闭式 y=(1+βx)^{−1}，方法学独立",
        "note": "v0.9.94 Batch B-14：golden=0.666666667（=2/3）/ cand |Δ|=1.882e-08（余量 5.31e5×）；反向信号/tol=2.15×（**本批最小，仍>1.4×**）。",
    },
    "B247": {
        "title": "非线性两点边值 y''=2yy', y(0)=0, y(1)=√c·tan√c（c=1, y(0.5)）",
        "metric": "nonlinear_bvp_shooting",
        "oracle": "closed_form(y=√c·tan(√c·x), RK4 打靶 + 割线/二分 n=32)",
        "tol": 0.01,
        "default_params": {"cc": 1.0},
        "golden_fn": golden_b247,
        "candidate": "b247_bvp_tan_cand",
        "candidate_desc": "y(0.5) 由 RK4 + 未知初斜率 s 打靶命中右端 BC 导出 ↔ 非线性 ODE 初等闭式 √c·tan(√c x)，方法学独立",
        "note": "v0.9.94 Batch B-14：golden=0.546302490（=tan 0.5）/ cand |Δ|=2.627e-07（余量 3.81e4×）；y(0)=0 ⇒ 初值 y 非平凡、斜率为打靶未知量。",
    },
    "B248": {
        "title": "非线性两点边值 y''+(y')²=0, y(0)=0, y(1)=y1（y1=1, y(0.5)）",
        "metric": "nonlinear_bvp_shooting",
        "oracle": "closed_form(y=ln(1+x(e^{y1}−1)), RK4 打靶 + 割线/二分 n=32)",
        "tol": 0.01,
        "default_params": {"y1": 1.0},
        "golden_fn": golden_b248,
        "candidate": "b248_bvp_log_cand",
        "candidate_desc": "y(0.5) 由 RK4 + 未知初斜率 s 打靶命中右端 BC 导出 ↔ 非线性 ODE 初等闭式 ln(1+x(e^{y1}−1))，方法学独立",
        "note": "v0.9.94 Batch B-14：golden=0.620114507 / cand |Δ|=3.880e-08（余量 2.58e5×）；右端 BC 误填 ln2 ⇒ 残差恒 0.3466 且与 n 无关（血案 3）。",
    },
    # ---- Batch B-15（v0.9.95 · 腿① 续加锚 · 延迟泛函微分方程/双调和薄板/一维输运半拉格朗日/NLSE 孤子分裂步）----
    "B249": {
        "title": "延迟泛函微分方程 y'(t)=−α·y(t−τ)（α=r·e^{−rτ}, τ=0.25）指数衰减解（r=1.0, y(1.2)）",
        "metric": "delay_differential_equation",
        "oracle": "closed_form(y=e^{−rT}, 分步法 + 三次 Hermite 历史插值 n=64)",
        "tol": 0.01,
        "default_params": {"r": 1.0, "T": 1.2},
        "golden_fn": golden_b249,
        "candidate": "b249_dde_steps_cand",
        "candidate_desc": "y(1.2) 由分步法（每步 RK4 等效 Simpson）+ 已算出历史点的三次 Hermite 插值导出 ↔ 延迟微分方程初等闭式 e^{−rT}，方法学独立",
        "note": "v0.9.95 Batch B-15：golden=0.301194212 / cand |Δ|=3.51e-11（余量 2.85e8×）；临界延迟参数化（τ=π/2α）反向信号仅 0.25×tol ⇒ 改「指数衰减解」参数化（血案 5）。",
    },
    "B250": {
        "title": "延迟泛函微分方程指数衰减解（r=0.75, y(1.2)）",
        "metric": "delay_differential_equation",
        "oracle": "closed_form(y=e^{−rT}, 分步法 + 三次 Hermite 历史插值 n=64)",
        "tol": 0.01,
        "default_params": {"r": 0.75, "T": 1.2},
        "golden_fn": golden_b250,
        "candidate": "b250_dde_steps_cand",
        "candidate_desc": "y(1.2) 由分步法 + 历史点三次 Hermite 插值导出 ↔ 初等闭式 e^{−rT}，方法学独立",
        "note": "v0.9.95 Batch B-15：golden=0.406569660 / cand |Δ|=1.05e-11（余量 9.48e8×）。",
    },
    "B251": {
        "title": "延迟泛函微分方程指数衰减解（r=1.25, y(1.2)）",
        "metric": "delay_differential_equation",
        "oracle": "closed_form(y=e^{−rT}, 分步法 + 三次 Hermite 历史插值 n=64)",
        "tol": 0.01,
        "default_params": {"r": 1.25, "T": 1.2},
        "golden_fn": golden_b251,
        "candidate": "b251_dde_steps_cand",
        "candidate_desc": "y(1.2) 由分步法 + 历史点三次 Hermite 插值导出 ↔ 初等闭式 e^{−rT}，方法学独立",
        "note": "v0.9.95 Batch B-15：golden=0.223130160 / cand |Δ|=8.49e-11（余量 1.18e8×）。",
    },
    "B252": {
        "title": "延迟泛函微分方程指数衰减解（r=1.5, y(1.2)）",
        "metric": "delay_differential_equation",
        "oracle": "closed_form(y=e^{−rT}, 分步法 + 三次 Hermite 历史插值 n=64)",
        "tol": 0.01,
        "default_params": {"r": 1.5, "T": 1.2},
        "golden_fn": golden_b252,
        "candidate": "b252_dde_steps_cand",
        "candidate_desc": "y(1.2) 由分步法 + 历史点三次 Hermite 插值导出 ↔ 初等闭式 e^{−rT}，方法学独立",
        "note": "v0.9.95 Batch B-15：golden=0.165298888 / cand |Δ|=1.68e-10（余量 5.95e7×）；分步法硬约束 h≤τ ⇒ 扫描下界 n≥8（血案 3）。",
    },
    "B253": {
        "title": "Kirchhoff 薄板双调和方程 D∇⁴w=q0·sinπx·sinπy（简支, q0=100）中心挠度",
        "metric": "biharmonic_plate_fd",
        "oracle": "closed_form(w=q0/(4π⁴D), 13 点双调和差分 n=256)",
        "tol": 0.01,
        "default_params": {"q0": 100.0, "dp": 1.0},
        "golden_fn": golden_b253,
        "candidate": "b253_biharmonic_plate_cand",
        "candidate_desc": "中心挠度由 13 点双调和模板（≡5 点 Laplacian 复合）+ 简支 ghost 消去 w_ghost=−w_mirror 导出 ↔ 初等正弦闭式 q0/(4π⁴D)，方法学独立",
        "note": "v0.9.95 Batch B-15：golden=0.256649556 / cand |Δ|=6.44e-06（余量 1.55e3×）；4 阶椭圆算子（既有 4 阶算子仅 B-9 族 A 的 1D ODE）。",
    },
    "B254": {
        "title": "Kirchhoff 薄板双调和方程（简支, q0=150）中心挠度",
        "metric": "biharmonic_plate_fd",
        "oracle": "closed_form(w=q0/(4π⁴D), 13 点双调和差分 n=256)",
        "tol": 0.01,
        "default_params": {"q0": 150.0, "dp": 1.0},
        "golden_fn": golden_b254,
        "candidate": "b254_biharmonic_plate_cand",
        "candidate_desc": "中心挠度由 13 点双调和差分 + 简支 ghost 消去导出 ↔ 初等闭式 q0/(4π⁴D)，方法学独立",
        "note": "v0.9.95 Batch B-15：golden=0.384974335 / cand |Δ|=9.66e-06（余量 1.04e3×）。",
    },
    "B255": {
        "title": "Kirchhoff 薄板双调和方程（简支, q0=200）中心挠度",
        "metric": "biharmonic_plate_fd",
        "oracle": "closed_form(w=q0/(4π⁴D), 13 点双调和差分 n=256)",
        "tol": 0.01,
        "default_params": {"q0": 200.0, "dp": 1.0},
        "golden_fn": golden_b255,
        "candidate": "b255_biharmonic_plate_cand",
        "candidate_desc": "中心挠度由 13 点双调和差分 + 简支 ghost 消去导出 ↔ 初等闭式 q0/(4π⁴D)，方法学独立",
        "note": "v0.9.95 Batch B-15：golden=0.513299113 / cand |Δ|=1.29e-05（余量 7.76e2×）。",
    },
    "B256": {
        "title": "Kirchhoff 薄板双调和方程（简支, q0=250）中心挠度",
        "metric": "biharmonic_plate_fd",
        "oracle": "closed_form(w=q0/(4π⁴D), 13 点双调和差分 n=256)",
        "tol": 0.01,
        "default_params": {"q0": 250.0, "dp": 1.0},
        "golden_fn": golden_b256,
        "candidate": "b256_biharmonic_plate_cand",
        "candidate_desc": "中心挠度由 13 点双调和差分 + 简支 ghost 消去导出 ↔ 初等闭式 q0/(4π⁴D)，方法学独立",
        "note": "v0.9.95 Batch B-15：golden=0.641623891 / cand |Δ|=1.61e-05（余量 **621×，本批最小**）；默认档 n=128 时余量仅 155× ⇒ 提到 n=256（血案 7）。",
    },
    "B257": {
        "title": "一维线性输运 ∂u/∂t+c·∂u/∂x=0（周期域, c=0.5）u(0.40, 0.5)",
        "metric": "linear_transport_semilagrangian",
        "oracle": "closed_form(u=u0(x−ct), 半拉格朗日特征线 + 4 点立方 Lagrange n=320)",
        "tol": 0.01,
        "default_params": {"c": 0.5, "T": 0.5, "xs": 0.4},
        "golden_fn": golden_b257,
        "candidate": "b257_transport_semilag_cand",
        "candidate_desc": "u(0.40,0.5) 由特征线逆追踪（落点 x_j−CFL·h 非格点）+ 4 点立方 Lagrange 重构导出 ↔ 输运方程刚性平移闭式 u0(x−ct)，方法学独立",
        "note": "v0.9.95 Batch B-15：golden=0.246153846 / cand |Δ|=8.37e-08（余量 1.19e5×）；x*=0.30 处 T 键反向信号仅 1.44×tol ⇒ 移到 0.40（血案 8）。",
    },
    "B258": {
        "title": "一维线性输运方程（周期域, c=1.0）u(0.30, 0.5)",
        "metric": "linear_transport_semilagrangian",
        "oracle": "closed_form(u=u0(x−ct), 半拉格朗日特征线 + 4 点立方 Lagrange n=320)",
        "tol": 0.01,
        "default_params": {"c": 1.0, "T": 0.5, "xs": 0.3},
        "golden_fn": golden_b258,
        "candidate": "b258_transport_semilag_cand",
        "candidate_desc": "u(0.30,0.5) 由半拉格朗日特征线 + 4 点立方 Lagrange 重构导出 ↔ 刚性平移闭式 u0(x−ct)，方法学独立",
        "note": "v0.9.95 Batch B-15：golden=0.307692308 / cand |Δ|=1.13e-07（余量 8.87e4×）。",
    },
    "B259": {
        "title": "一维线性输运方程（周期域, c=1.5）u(0.30, 0.5)",
        "metric": "linear_transport_semilagrangian",
        "oracle": "closed_form(u=u0(x−ct), 半拉格朗日特征线 + 4 点立方 Lagrange n=320)",
        "tol": 0.01,
        "default_params": {"c": 1.5, "T": 0.5, "xs": 0.3},
        "golden_fn": golden_b259,
        "candidate": "b259_transport_semilag_cand",
        "candidate_desc": "u(0.30,0.5) 由半拉格朗日特征线 + 4 点立方 Lagrange 重构导出 ↔ 刚性平移闭式 u0(x−ct)，方法学独立",
        "note": "v0.9.95 Batch B-15：golden=0.941176471 / cand |Δ|=4.69e-06（余量 2.13e3×）；收敛 O(h³)（累计插值误差 ∝ m·h⁴）。",
    },
    "B260": {
        "title": "一维线性输运方程（周期域, c=2.0）u(0.30, 0.5)",
        "metric": "linear_transport_semilagrangian",
        "oracle": "closed_form(u=u0(x−ct), 半拉格朗日特征线 + 4 点立方 Lagrange n=320)",
        "tol": 0.01,
        "default_params": {"c": 2.0, "T": 0.5, "xs": 0.3},
        "golden_fn": golden_b260,
        "candidate": "b260_transport_semilag_cand",
        "candidate_desc": "u(0.30,0.5) 由半拉格朗日特征线 + 4 点立方 Lagrange 重构导出 ↔ 刚性平移闭式 u0(x−ct)，方法学独立",
        "note": "v0.9.95 Batch B-15：golden=0.5 / cand |Δ|=2.68e-06（余量 3.73e3×）；CFL=0.5（整数 CFL 退化为纯平移 ⇒ 残差恒 0，血案 9）。",
    },
    "B261": {
        "title": "聚焦 NLSE i·u_t+u_xx+2|u|²u=0 基态孤子（A=0.90）Re u(19.6, 3)",
        "metric": "nlse_soliton_splitstep",
        "oracle": "closed_form(Re u=A·sech(A(x−x0))·cos(A²T), 分裂步 Fourier Strang n=2048)",
        "tol": 0.01,
        "default_params": {"A": 0.9, "x0": 20.0},
        "golden_fn": golden_b261,
        "candidate": "b261_nlse_soliton_cand",
        "candidate_desc": "Re u(x*,T) 由算子分裂（NL(dt/2)→L(dt)→NL(dt/2)，NL 相位 2|u|²dt）+ FFT 谱精确线性步导出 ↔ 孤子闭式 A·sech·cos(A²T)，方法学独立",
        "note": "v0.9.95 Batch B-15：golden=−0.639689025 / cand |Δ|=1.74e-06（余量 5.75e3×）；非线性相位漏因子 2 会在残差上留下「不随 dt 下降」指纹（血案 1）。",
    },
    "B262": {
        "title": "聚焦 NLSE 基态孤子（A=1.00）Re u(19.6, 3)",
        "metric": "nlse_soliton_splitstep",
        "oracle": "closed_form(Re u=A·sech(A(x−x0))·cos(A²T), 分裂步 Fourier Strang n=2048)",
        "tol": 0.01,
        "default_params": {"A": 1.0, "x0": 20.0},
        "golden_fn": golden_b262,
        "candidate": "b262_nlse_soliton_cand",
        "candidate_desc": "Re u(x*,T) 由分裂步 Fourier（Strang）+ FFT 谱线性步导出 ↔ 孤子闭式，方法学独立",
        "note": "v0.9.95 Batch B-15：golden=−0.915750437 / cand |Δ|=1.36e-06（余量 7.35e3×）。",
    },
    "B263": {
        "title": "聚焦 NLSE 基态孤子（A=1.10）Re u(19.6, 3)",
        "metric": "nlse_soliton_splitstep",
        "oracle": "closed_form(Re u=A·sech(A(x−x0))·cos(A²T), 分裂步 Fourier Strang n=2048)",
        "tol": 0.01,
        "default_params": {"A": 1.1, "x0": 20.0},
        "golden_fn": golden_b263,
        "candidate": "b263_nlse_soliton_cand",
        "candidate_desc": "Re u(x*,T) 由分裂步 Fourier（Strang）+ FFT 谱线性步导出 ↔ 孤子闭式，方法学独立",
        "note": "v0.9.95 Batch B-15：golden=−0.884390326 / cand |Δ|=3.27e-06（余量 3.06e3×）。",
    },
    "B264": {
        "title": "聚焦 NLSE 基态孤子（A=1.20）Re u(19.6, 3)",
        "metric": "nlse_soliton_splitstep",
        "oracle": "closed_form(Re u=A·sech(A(x−x0))·cos(A²T), 分裂步 Fourier Strang n=2048)",
        "tol": 0.01,
        "default_params": {"A": 1.2, "x0": 20.0},
        "golden_fn": golden_b264,
        "candidate": "b264_nlse_soliton_cand",
        "candidate_desc": "Re u(x*,T) 由分裂步 Fourier（Strang）+ FFT 谱线性步导出 ↔ 孤子闭式，方法学独立",
        "note": "v0.9.95 Batch B-15：golden=−0.410653691 / cand |Δ|=1.39e-05（余量 719×）；级 L=20 时残差停滞 ~1e-5（周期镜像地板）⇒ 改 L=40（血案 2）。",
    },
    # ---- Batch B-16（v0.9.96 · 腿① 续加锚 · Burgers tanh 行波/广义指数积分 E_n/Haar 小波多分辨投影）----
    "B265": {
        "title": "Burgers 方程 tanh 行波精确解 u(x*,T)（c=1.0, nu=0.5, x*=0, T=4.0）",
        "metric": "burgers_tanh_traveling_wave",
        "oracle": "closed_form(u=c·[1−tanh(c·ξ/2ν)], ξ=0.5; RK4 + 二阶中心差分 n=1600)",
        "tol": 0.01,
        "default_params": {"c": 1.0, "nu": 0.5},
        "golden_fn": golden_b265,
        "candidate": "b265_burgers_tanh_cand",
        "candidate_desc": "u(x*,T) 由显式 RK4 时间推进 + 二阶中心差分（对流与扩散均中心）导出 ↔ tanh 行波闭式 c·[1−tanh(cξ/2ν)]，方法学独立",
        "note": "v0.9.96 Batch B-16：golden=+0.537882843 / cand |Δ|=5.405e-04（余量 18.5×）；中心差分对流稳定前提 = 网格 Peclet c·h/ν < 2（本档 0.029~0.117，安全；血案 1）。",
    },
    "B266": {
        "title": "Burgers 方程 tanh 行波精确解 u(x*,T)（c=1.2, nu=0.5, x*=0, T=4.0）",
        "metric": "burgers_tanh_traveling_wave",
        "oracle": "closed_form(u=c·[1−tanh(c·ξ/2ν)], ξ=0.5; RK4 + 二阶中心差分 n=1600)",
        "tol": 0.01,
        "default_params": {"c": 1.2, "nu": 0.5},
        "golden_fn": golden_b266,
        "candidate": "b266_burgers_tanh_cand",
        "candidate_desc": "u(x*,T) 由显式 RK4 时间推进 + 二阶中心差分（对流与扩散均中心）导出 ↔ tanh 行波闭式 c·[1−tanh(cξ/2ν)]，方法学独立",
        "note": "v0.9.96 Batch B-16：golden=+0.555540520 / cand |Δ|=8.747e-04（余量 11.4×）；中心差分对流稳定前提 = 网格 Peclet c·h/ν < 2（本档 0.029~0.117，安全；血案 1）。",
    },
    "B267": {
        "title": "Burgers 方程 tanh 行波精确解 u(x*,T)（c=0.9, nu=0.45, x*=0, T=4.0）",
        "metric": "burgers_tanh_traveling_wave",
        "oracle": "closed_form(u=c·[1−tanh(c·ξ/2ν)], ξ=0.5; RK4 + 二阶中心差分 n=1600)",
        "tol": 0.01,
        "default_params": {"c": 0.9, "nu": 0.45},
        "golden_fn": golden_b267,
        "candidate": "b267_burgers_tanh_cand",
        "candidate_desc": "u(x*,T) 由显式 RK4 时间推进 + 二阶中心差分（对流与扩散均中心）导出 ↔ tanh 行波闭式 c·[1−tanh(cξ/2ν)]，方法学独立",
        "note": "v0.9.96 Batch B-16：golden=+0.484094559 / cand |Δ|=4.783e-04（余量 20.9×）；中心差分对流稳定前提 = 网格 Peclet c·h/ν < 2（本档 0.029~0.117，安全；血案 1）。",
    },
    "B268": {
        "title": "Burgers 方程 tanh 行波精确解 u(x*,T)（c=1.4, nu=0.6, x*=0, T=4.0）",
        "metric": "burgers_tanh_traveling_wave",
        "oracle": "closed_form(u=c·[1−tanh(c·ξ/2ν)], ξ=0.5; RK4 + 二阶中心差分 n=1600)",
        "tol": 0.01,
        "default_params": {"c": 1.4, "nu": 0.6},
        "golden_fn": golden_b268,
        "candidate": "b268_burgers_tanh_cand",
        "candidate_desc": "u(x*,T) 由显式 RK4 时间推进 + 二阶中心差分（对流与扩散均中心）导出 ↔ tanh 行波闭式 c·[1−tanh(cξ/2ν)]，方法学独立",
        "note": "v0.9.96 Batch B-16：golden=+0.664882479 / cand |Δ|=9.914e-04（余量 10.1×）；中心差分对流稳定前提 = 网格 Peclet c·h/ν < 2（本档 0.029~0.117，安全；血案 1）。",
    },
    "B269": {
        "title": "Burgers 方程 tanh 行波精确解 u(x*,T)（c=1.0, nu=0.4, x*=0, T=4.0）",
        "metric": "burgers_tanh_traveling_wave",
        "oracle": "closed_form(u=c·[1−tanh(c·ξ/2ν)], ξ=0.5; RK4 + 二阶中心差分 n=1600)",
        "tol": 0.01,
        "default_params": {"c": 1.0, "nu": 0.4},
        "golden_fn": golden_b269,
        "candidate": "b269_burgers_tanh_cand",
        "candidate_desc": "u(x*,T) 由显式 RK4 时间推进 + 二阶中心差分（对流与扩散均中心）导出 ↔ tanh 行波闭式 c·[1−tanh(cξ/2ν)]，方法学独立",
        "note": "v0.9.96 Batch B-16：golden=+0.445400278 / cand |Δ|=7.568e-04（余量 13.2×）；中心差分对流稳定前提 = 网格 Peclet c·h/ν < 2（本档 0.029~0.117，安全；血案 1）。",
    },
    "B270": {
        "title": "Burgers 方程 tanh 行波精确解 u(x*,T)（c=1.1, nu=0.5, x*=0, T=4.0）",
        "metric": "burgers_tanh_traveling_wave",
        "oracle": "closed_form(u=c·[1−tanh(c·ξ/2ν)], ξ=0.5; RK4 + 二阶中心差分 n=1600)",
        "tol": 0.01,
        "default_params": {"c": 1.1, "nu": 0.5},
        "golden_fn": golden_b270,
        "candidate": "b270_burgers_tanh_cand",
        "candidate_desc": "u(x*,T) 由显式 RK4 时间推进 + 二阶中心差分（对流与扩散均中心）导出 ↔ tanh 行波闭式 c·[1−tanh(cξ/2ν)]，方法学独立",
        "note": "v0.9.96 Batch B-16：golden=+0.549427768 / cand |Δ|=7.015e-04（余量 14.3×）；中心差分对流稳定前提 = 网格 Peclet c·h/ν < 2（本档 0.029~0.117，安全；血案 1）。",
    },
    # ---- Batch B-16 · 族 B（广义指数积分 E_n）----
    "B271": {
        "title": "广义指数积分 E_n(x)=∫₁^∞ e^{−xt}/t^n dt（n=1, x=0.3）",
        "metric": "generalized_exponential_integral",
        "oracle": "scipy.special.exp1/expn(x); 截断 [1,60] + 复合 Simpson（2N+1 节点, N=80）",
        "tol": 0.01,
        "default_params": {"nn": 1, "x": 0.3},
        "golden_fn": golden_b271,
        "candidate": "b271_expn_simpson_cand",
        "candidate_desc": "E_n(x) 由区间 [1,60] 截断 + 复合 Simpson（2N+1 等距节点）数值求积导出 ↔ 特殊函数闭式库值，方法学独立",
        "note": "v0.9.96 Batch B-16：golden=+0.905676652 / cand |Δ|=4.826e-04（余量 20.7×）；截断上限 M 须让尾部 e^{−xM} 落到机器精度之下（x=0.3 时 M=40 仅 6e−6 会盖住最细档离散误差 ⇒ 取 M=60，尾部 ≤1.4e−18；血案 2）。",
    },
    "B272": {
        "title": "广义指数积分 E_n(x)=∫₁^∞ e^{−xt}/t^n dt（n=1, x=0.6）",
        "metric": "generalized_exponential_integral",
        "oracle": "scipy.special.exp1/expn(x); 截断 [1,60] + 复合 Simpson（2N+1 节点, N=80）",
        "tol": 0.01,
        "default_params": {"nn": 1, "x": 0.6},
        "golden_fn": golden_b272,
        "candidate": "b272_expn_simpson_cand",
        "candidate_desc": "E_n(x) 由区间 [1,60] 截断 + 复合 Simpson（2N+1 等距节点）数值求积导出 ↔ 特殊函数闭式库值，方法学独立",
        "note": "v0.9.96 Batch B-16：golden=+0.454379503 / cand |Δ|=4.807e-04（余量 20.8×）；截断上限 M 须让尾部 e^{−xM} 落到机器精度之下（x=0.3 时 M=40 仅 6e−6 会盖住最细档离散误差 ⇒ 取 M=60，尾部 ≤1.4e−18；血案 2）。",
    },
    "B273": {
        "title": "广义指数积分 E_n(x)=∫₁^∞ e^{−xt}/t^n dt（n=1, x=1.0）",
        "metric": "generalized_exponential_integral",
        "oracle": "scipy.special.exp1/expn(x); 截断 [1,60] + 复合 Simpson（2N+1 节点, N=80）",
        "tol": 0.01,
        "default_params": {"nn": 1, "x": 1.0},
        "golden_fn": golden_b273,
        "candidate": "b273_expn_simpson_cand",
        "candidate_desc": "E_n(x) 由区间 [1,60] 截断 + 复合 Simpson（2N+1 等距节点）数值求积导出 ↔ 特殊函数闭式库值，方法学独立",
        "note": "v0.9.96 Batch B-16：golden=+0.219383934 / cand |Δ|=4.712e-04（余量 21.2×）；截断上限 M 须让尾部 e^{−xM} 落到机器精度之下（x=0.3 时 M=40 仅 6e−6 会盖住最细档离散误差 ⇒ 取 M=60，尾部 ≤1.4e−18；血案 2）。",
    },
    "B274": {
        "title": "广义指数积分 E_n(x)=∫₁^∞ e^{−xt}/t^n dt（n=2, x=0.5）",
        "metric": "generalized_exponential_integral",
        "oracle": "scipy.special.exp1/expn(x); 截断 [1,60] + 复合 Simpson（2N+1 节点, N=80）",
        "tol": 0.01,
        "default_params": {"nn": 2, "x": 0.5},
        "golden_fn": golden_b274,
        "candidate": "b274_expn_simpson_cand",
        "candidate_desc": "E_n(x) 由区间 [1,60] 截断 + 复合 Simpson（2N+1 等距节点）数值求积导出 ↔ 特殊函数闭式库值，方法学独立",
        "note": "v0.9.96 Batch B-16：golden=+0.326643862 / cand |Δ|=1.502e-03（余量 6.7×）；截断上限 M 须让尾部 e^{−xM} 落到机器精度之下（x=0.3 时 M=40 仅 6e−6 会盖住最细档离散误差 ⇒ 取 M=60，尾部 ≤1.4e−18；血案 2）。",
    },
    "B275": {
        "title": "广义指数积分 E_n(x)=∫₁^∞ e^{−xt}/t^n dt（n=2, x=1.0）",
        "metric": "generalized_exponential_integral",
        "oracle": "scipy.special.exp1/expn(x); 截断 [1,60] + 复合 Simpson（2N+1 节点, N=80）",
        "tol": 0.01,
        "default_params": {"nn": 2, "x": 1.0},
        "golden_fn": golden_b275,
        "candidate": "b275_expn_simpson_cand",
        "candidate_desc": "E_n(x) 由区间 [1,60] 截断 + 复合 Simpson（2N+1 等距节点）数值求积导出 ↔ 特殊函数闭式库值，方法学独立",
        "note": "v0.9.96 Batch B-16：golden=+0.148495507 / cand |Δ|=1.263e-03（余量 7.9×）；截断上限 M 须让尾部 e^{−xM} 落到机器精度之下（x=0.3 时 M=40 仅 6e−6 会盖住最细档离散误差 ⇒ 取 M=60，尾部 ≤1.4e−18；血案 2）。",
    },
    # ---- Batch B-16 · 族 C（Haar 小波多分辨投影）----
    "B276": {
        "title": "Haar 小波多分辨投影 V_J 段内平均（f(x)=x^0.5, p=0.5, J=3, k=3）",
        "metric": "haar_mra_projection",
        "oracle": "closed_form((b^{p+1}−a^{p+1})/((p+1)·h), 2^K 采样逐层 Haar 低通 K=13)",
        "tol": 0.01,
        "default_params": {"p": 0.5, "J": 3, "k": 3},
        "golden_fn": golden_b276,
        "candidate": "b276_haar_mra_cand",
        "candidate_desc": "V_J 正交投影由 2^K 等距采样逐层 Haar 低通（等权平均）降到 J 层后取第 k 段导出 ↔ 段内平均闭式 (b^{p+1}−a^{p+1})/((p+1)h)，方法学独立",
        "note": "v0.9.96 Batch B-16：golden=+0.660873212 / cand |Δ|=4.626e-05（余量 216.2×）；等权低通 ≡ 段左端点矩形 ⇒ 一阶收敛 O(2^{−K})，比值 ~2 非 4（血案 3）。",
    },
    "B277": {
        "title": "Haar 小波多分辨投影 V_J 段内平均（f(x)=x^0.5, p=0.5, J=4, k=7）",
        "metric": "haar_mra_projection",
        "oracle": "closed_form((b^{p+1}−a^{p+1})/((p+1)·h), 2^K 采样逐层 Haar 低通 K=13)",
        "tol": 0.01,
        "default_params": {"p": 0.5, "J": 4, "k": 7},
        "golden_fn": golden_b277,
        "candidate": "b277_haar_mra_cand",
        "candidate_desc": "V_J 正交投影由 2^K 等距采样逐层 Haar 低通（等权平均）降到 J 层后取第 k 段导出 ↔ 段内平均闭式 (b^{p+1}−a^{p+1})/((p+1)h)，方法学独立",
        "note": "v0.9.96 Batch B-16：golden=+0.684526303 / cand |Δ|=4.460e-05（余量 224.2×）；等权低通 ≡ 段左端点矩形 ⇒ 一阶收敛 O(2^{−K})，比值 ~2 非 4（血案 3）。",
    },
    "B278": {
        "title": "Haar 小波多分辨投影 V_J 段内平均（f(x)=x^0.75, p=0.75, J=3, k=5）",
        "metric": "haar_mra_projection",
        "oracle": "closed_form((b^{p+1}−a^{p+1})/((p+1)·h), 2^K 采样逐层 Haar 低通 K=13)",
        "tol": 0.01,
        "default_params": {"p": 0.75, "J": 3, "k": 5},
        "golden_fn": golden_b278,
        "candidate": "b278_haar_mra_cand",
        "candidate_desc": "V_J 正交投影由 2^K 等距采样逐层 Haar 低通（等权平均）降到 J 层后取第 k 段导出 ↔ 段内平均闭式 (b^{p+1}−a^{p+1})/((p+1)h)，方法学独立",
        "note": "v0.9.96 Batch B-16：golden=+0.754817949 / cand |Δ|=5.029e-05（余量 198.8×）；等权低通 ≡ 段左端点矩形 ⇒ 一阶收敛 O(2^{−K})，比值 ~2 非 4（血案 3）。",
    },
    "B279": {
        "title": "Haar 小波多分辨投影 V_J 段内平均（f(x)=x^1.5, p=1.5, J=3, k=2）",
        "metric": "haar_mra_projection",
        "oracle": "closed_form((b^{p+1}−a^{p+1})/((p+1)·h), 2^K 采样逐层 Haar 低通 K=13)",
        "tol": 0.01,
        "default_params": {"p": 1.5, "J": 3, "k": 2},
        "golden_fn": golden_b279,
        "candidate": "b279_haar_mra_cand",
        "candidate_desc": "V_J 正交投影由 2^K 等距采样逐层 Haar 低通（等权平均）降到 J 层后取第 k 段导出 ↔ 段内平均闭式 (b^{p+1}−a^{p+1})/((p+1)h)，方法学独立",
        "note": "v0.9.96 Batch B-16：golden=+0.175567596 / cand |Δ|=5.109e-05（余量 195.7×）；等权低通 ≡ 段左端点矩形 ⇒ 一阶收敛 O(2^{−K})，比值 ~2 非 4（血案 3）。",
    },
    "B280": {
        "title": "Haar 小波多分辨投影 V_J 段内平均（f(x)=x^2.0, p=2.0, J=4, k=9）",
        "metric": "haar_mra_projection",
        "oracle": "closed_form((b^{p+1}−a^{p+1})/((p+1)·h), 2^K 采样逐层 Haar 低通 K=13)",
        "tol": 0.01,
        "default_params": {"p": 2.0, "J": 4, "k": 9},
        "golden_fn": golden_b280,
        "candidate": "b280_haar_mra_cand",
        "candidate_desc": "V_J 正交投影由 2^K 等距采样逐层 Haar 低通（等权平均）降到 J 层后取第 k 段导出 ↔ 段内平均闭式 (b^{p+1}−a^{p+1})/((p+1)h)，方法学独立",
        "note": "v0.9.96 Batch B-16：golden=+0.352864583 / cand |Δ|=7.248e-05（余量 138.0×）；等权低通 ≡ 段左端点矩形 ⇒ 一阶收敛 O(2^{−K})，比值 ~2 非 4（血案 3）。",
    },
}



# ===========================================================================
# 验证成熟度模型（VMM, v0.9.62）：maturity_tier / provenance / upgrade_path
# ---------------------------------------------------------------------------
# 详见 docs/verification_maturity_model.md。三字段为**作者声明 + 护栏强制**，
# 使「自证是合法第一阶段」可见、可追溯、可升级，且禁止越级谎报。
# 底线 6 条由 run_maturity_baseline_smoke.py 守护。
# ===========================================================================
# Tier-1（自证）的 provenance 与升级路径显式覆盖；其余按 DEFAULT 推导。
_VMM_OVERRIDES = {
    # id: (provenance, upgrade_path)
    "B2":  ("independent_cross_check",
            "🔒 终审锁定升 Tier-3 严格独立（2026-09-10 多智能体终审）：FV-FDM 全矢量（纯物理选模 2.644，Δ=0.0069）+ PWE 平面波展开（2.614，Δ=0.0369）两个方法学独立全波数值均在 tol=0.05 内复现 EIM golden 2.6509，golden 居二者之间，判据 C5 成立。推翻早间『半矢量 FDM=2.53 证伪』误判（该实现索引 bug，已废弃）。详见 _VMM_FINAL_VERDICT['B2']。勿反复审议。"),
    "B5":  ("independent_cross_check",
            "🔒 v0.9.81 升 Tier-3 严格独立（P1-1 B567）：候选 `ybranch_eme` 双芯超模 EME"
            "（EIM 降维 + 锥区逐片解完整横向 Helmholtz 本征问题 + 模式重叠矩阵级联），"
            "末片导模功率和 T ⇒ 分束损耗 = 3.0103 − 10log10(T)；实测 3.0321 dB vs golden "
            "3.4（|diff|=0.368 < tol 1.0），残差 = golden 唯象拟合式 0.4·(θ/10)² 的固有"
            "粗糙度（严格 EME 给出 excess 仅 0.008–0.061 dB，θ 5–20°，θ 依赖形状与拟合式"
            "完全不同源）。⚠️ tol=1.0 远宽于候选参数响应幅度（±10% 仅 ~0.005 dB）⇒ 本锚"
            "**无参数判别力**（同 B8 型），只回答「是否接近理想均分下限」，故不进 "
            "PERTURB_SPEC。（原 design_rule_anchor 升级路径已打通）"),
    "B6":  ("independent_cross_check",
            "🔒 v0.9.81 升 Tier-3 严格独立（P1-1 B567）：候选 `grating_fp` 首原理四因子"
            "分解 η = η_dir·η_ov·F(ff)·M ——η_dir=1/2（上下包层对称 ⇒ 一阶衍射上/下功率"
            "相等，由对称性推出）、η_ov=0.7846（指数辐射场⊗高斯光纤模 MFD=10.4µm 的"
            "归一化模场重叠，对 α 取设计最优）、F=sin(π·ff)（方波一阶傅里叶强度）、"
            "M=exp(−(Δβ·L_g/2)²)（光栅方程相位匹配，L_g=20 周期）。实测 0.3909 vs golden "
            "0.5（|diff|=0.109 < tol 0.15）：残差=设计守则把 η_ov 理想化为 1 的乐观偏差"
            "（无镜面光栅理论天花板）；不引用 E8 的 σ=15° 唯象倾斜散布系数。"
            "（原 design_rule_anchor 升级路径已打通）"),
    "B7":  ("independent_cross_check",
            "🔒 v0.9.82 升 Tier-3 严格独立：golden 语义订正为设计守则锚 −40 dB"
            "（独立实证背书 E7 同几何实测 −41±2 dB）；已证失真的 2D 离线 FDTD"
            "（裸十字 vs 锚定 taper 交叉差 20~30 dB、源位 ±3 dB 不收敛）撤出 "
            "golden 调度、降级为机理诊断量。候选=双芯超模/CMT 本征解"
            "（方法学独立于场级 FDTD），|diff|=4.64 < tol 5.0 —— 残差占窗口 "
            "93%，属边缘通过；彻底闭合需 3D 全波 + 真实版图"),
    "B11": ("independent_cross_check",
            "🔒 v0.9.68 升 Tier-3 严格独立：数值 add-drop 环 drop 口传递函数峰周期拟合"
            "FSR（同 B4 谱拟合族），再算 |FSR−target|/target 与 golden 同一标量。"
            "方法学独立于闭式 FSR；基线残差 ~1e-9 << tol=0.03，余量 >>1000×，判据 D 不触发。"
            "（原 self_authored_closed_form 升级路径已打通）"),
    "B16": ("independent_cross_check",
            "🔒 v0.9.80 升 Tier-3 严格独立（P1-1 B16 重审）：rib-MMI 全场模态重构候选 "
            "`rib_mmi_recon`——① 反演 core 折射率使平板基模 ≡ 器件 n_eff（对象一致，正面"
            "修正 mmi_eme 的 slab≠rib 错配）；② 精确解 tan/cot 本征方程得全部导模；"
            "③ 输入场按全部导模展开沿 z 精确传播，双度量联合定位 1×2 首像（**不套 (9/8) "
            "成像因子**）。方法学独立于 golden 抛物线闭式。实测 |cand−golden|：W=2.0→0.26µm、"
            "2.4→0.25、2.8→0.54、3.2→0.92、3.6→1.48、4.0→2.21（全 < tol 3.0µm，覆盖 "
            "2.0–4.0µm 全宽度域）；残差=抛物线近似固有误差（非零、有界、物理，非假绿）。"
            "（原 self_authored_closed_form 升级路径已打通；golden 因子 3→9/4 已修）"),
    "B17": ("self_authored_closed_form",
            "本就不升：定义同义反复（terminal Tier-1）"),
    "B18": ("self_authored_closed_form",
            "本就不升：regime 越界（terminal Tier-1）"),
    "B21": ("self_authored_closed_form_with_check",
            "v0.9.78 诚实升 degraded_ordinal（用户授权「B 路径」）：自研 2D FDTD 全波"
            "（fdtd2d_dbr_cavity.py，纯 numpy·C 级自主·不借 Meep/Tidy3D）作方法学独立候选，"
            "6 点扫描实证实残差 0.04%–8.06% 随几何变化（判据 D 满足，非伪绿）。默认"
            "λ_fdtd=2214.87nm vs golden 2214.0nm，rel=0.039%（余量 ~77×，低于严格 100×"
            "故保守归 degraded，不进死标量判决列）；tol=66.0nm=3%×golden(2214nm) 绝对带。"
            "跨域偏差主成分为一阶 FP 模型近似粗糙度，待放宽红线（借 A 级/补波导几何）方升 strict。"),
    "E1":  ("external_empirical", "T2 实测数据集（光子 PDA 实证锚）升 Tier-3"),
    "E3":  ("external_empirical", "T2 实测数据集（光子 PDA 实证锚）升 Tier-3"),
    "E4":  ("external_empirical", "T2 实测数据集（光子 PDA 实证锚）升 Tier-3"),
    "E5":  ("external_empirical", "T2 实测数据集（光子 PDA 实证锚）升 Tier-3"),
    "E6":  ("external_empirical", "T2 实测数据集（光子 PDA 实证锚）升 Tier-3"),
    "E7":  ("external_empirical", "T2 实测数据集（光子 PDA 实证锚）升 Tier-3"),
    "E9":  ("external_empirical", "用真实 PDK 标定 c1 工艺系数后升 Tier-3"),
    "S1":  ("self_authored_closed_form", "本就不升：系统/算术合成校验（terminal Tier-1，非物理锚）"),
    "S2":  ("self_authored_closed_form", "本就不升：系统/算术合成校验（terminal Tier-1，非物理锚）"),
    "S3":  ("self_authored_closed_form", "本就不升：系统/算术合成校验（terminal Tier-1，非物理锚）"),
    "S4":  ("self_authored_closed_form", "本就不升：系统/算术合成校验（terminal Tier-1，非物理锚）"),
    "S5":  ("self_authored_closed_form", "本就不升：系统/算术合成校验（terminal Tier-1，非物理锚）"),
    "S6":  ("self_authored_closed_form", "本就不升：系统/算术合成校验（terminal Tier-1，非物理锚）"),
    "S9":  ("self_authored_closed_form", "本就不升：系统/算术合成校验（terminal Tier-1，非物理锚）"),
    "S10": ("self_authored_closed_form", "本就不升：系统/算术合成校验（terminal Tier-1，非物理锚）"),
    "S11": ("self_authored_closed_form", "本就不升：系统/算术合成校验（terminal Tier-1，非物理锚）"),
    "S12": ("self_authored_closed_form", "本就不升：系统/算术合成校验（terminal Tier-1，非物理锚）"),
}


# ===========================================================================
# 🔒 终审分级锁（v0.9.66 · 2026-09-10）
# ---------------------------------------------------------------------------
# 目的：对「反复审议、已多方法终审」的锚打永久分级标志。任何人（含 AI）后续
#       想改其分级，必须先读此处结论，避免重复讨论（B2 已反反复复多轮）。
# 字段：verdict / date / methods / rationale / supersedes / no_revisit
_VMM_FINAL_VERDICT = {
    "B2": {
        "verdict": "LOCKED_STRICT_INDEPENDENT",  # 终审：已升 Tier-3 严格独立
        "date": "2026-09-10",
        "methods": [
            "FV-FDM 全矢量有限差分（纯 numpy/scipy，纯物理选模，n_eff=2.644，Δ=0.0069≤tol0.05）★已注册为 harness 独立候选 b2_fvfdm_neff",
            "PWE 平面波展开（傅里叶基，n_eff=2.614，Δ=0.0369≤tol0.05）—— 独立交叉验证",
            "Marcatili 1969 解析近似（n_eff=2.448，系统性低估 0.20）—— 仅作解析降维偏差方向对照，非 ORACLE",
        ],
        "rationale": ("EIM golden=2.6509 落在两个独立全波方法（FV-FDM 2.644 / PWE 2.614）之间，"
                      "二者均满足判据 C5（方法学独立候选在 tol=0.05 内复现 golden）。"
                      "golden 本身为合理中值，可信。B2 由自证桩升 Tier-3 严格独立。"),
        "supersedes": ("推翻 2026-09-10 早间『半矢量 FDM=2.53 证伪不可升 strict』的误判——"
                       "该实现存在折射率索引错位 bug（收敛到错误模式），非真物理结论，已废弃。"),
        "no_revisit": ("除非 tol 收紧至 <0.04，或出现与之矛盾的权威 ORACLE（MPB/FEM 实测），"
                       "否则本锚分级终审锁定，勿反复审议。"),
    },
}


def _vmm_classify(defn: dict) -> str:
    """与 harness（IndependentCandidateRouter.candidate_class）同构的分类。"""
    if defn.get("candidate_status") == "degraded_ordinal":
        return "degraded"
    if "candidate" in defn:
        return "strict_independent"
    return "self_certified"


def _vmm_provenance(bid: str, defn: dict) -> str:
    if bid in _VMM_OVERRIDES:
        return _VMM_OVERRIDES[bid][0]
    tier = _vmm_classify(defn)
    if tier == "strict_independent":
        return "independent_cross_check"
    if tier == "degraded":
        return "external_empirical"
    # self_certified 默认保守诚实：自写闭式（低置信·待 ORACLE）
    return "self_authored_closed_form"


def _vmm_upgrade_path(bid: str, defn: dict) -> str:
    if bid in _VMM_OVERRIDES:
        return _VMM_OVERRIDES[bid][1]
    tier = _vmm_classify(defn)
    if tier in ("strict_independent", "degraded"):
        return ""
    return "接独立候选 / 外部 ORACLE（按环境可用性做专题攻关）"


for _bid, _def in BENCHMARK_DEFS.items():
    _def.setdefault("maturity_tier", _vmm_classify(_def))
    _def.setdefault("provenance", _vmm_provenance(_bid, _def))
    _def.setdefault("upgrade_path", _vmm_upgrade_path(_bid, _def))


# 对齐顺序（报告展示用）
BENCHMARK_ORDER = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10",
                   "B11", "B12", "B13", "B14", "B15", "B16", "B17", "B18",
                   "B19", "B20", "B21", "B22", "B23", "B24", "B25",
                   "B26", "B27", "B28", "B29", "B30", "B31", "B32", "B33",
                   "B34", "B36", "B37", "B40", "B41",
                   "B42", "B43", "B44", "B45", "B46", "B47", "B48", "B49", "B50", "B51",
                   "B52", "B53", "B54", "B55", "B56", "B57", "B58", "B59", "B60", "B61", "B62", "B63", "B64",
                   "B65", "B66", "B67", "B68", "B70", "B71", "B73", "B74", "B75", "B76", "B77", "B78", "B79", "B80",
                   "B81", "B82", "B83", "B84", "B85", "B86", "B87", "B88",
                   "B89", "B90", "B91", "B92", "B93", "B94", "B95", "B96",
                   "B97", "B98", "B99", "B100", "B101", "B102", "B103", "B104",
                   "B105", "B106", "B107", "B108", "B109", "B110",
                   "B111", "B112", "B113", "B114", "B115", "B116", "B117",
                   "B118", "B119", "B120",
                   "B121", "B122", "B123", "B124", "B125", "B126", "B127", "B128",
                   "B129", "B130", "B131", "B132", "B133", "B134", "B135", "B136",
                   "B137", "B138", "B139", "B140", "B141", "B142", "B143", "B144",
                   "B145", "B146", "B147", "B148", "B149", "B150", "B151", "B152",
                   "B153", "B154", "B155", "B156", "B157", "B158", "B159", "B160",
                   "B161", "B162", "B163", "B164", "B165", "B166", "B167", "B168",
                   "B169", "B170", "B171", "B172", "B173", "B174", "B175", "B176",
                   "B177", "B178", "B179", "B180", "B181", "B182", "B183", "B184",
                   # Batch B-11（v0.9.91 · 腿① 续加锚 · 量子统计积分与 ζ/Kepler 中心力轨道/辐射传热角系数/Voigt 谱线）
                   "B185", "B186", "B187", "B188", "B189", "B190", "B191", "B192",
                   "B193", "B194", "B195", "B196", "B197", "B198", "B199", "B200",
                   # Batch B-12（v0.9.92 · 腿① 续加锚 · 正交多项式高斯求积/连分数有理逼近/Durand–Kerner 求根/₂F₁ 超几何）
                   "B201", "B202", "B203", "B204", "B205", "B206", "B207", "B208",
                   "B209", "B210", "B211", "B212", "B213", "B214", "B215", "B216",
                   # Batch B-13（v0.9.93 · 腿① 续加锚 · 分数阶 GL 微分/矩阵指数 scaling–squaring/变分极值梯度下降/第二类 Volterra 积分方程）
                   "B217", "B218", "B219", "B220", "B221", "B222", "B223", "B224",
                   "B225", "B226", "B227", "B228", "B229", "B230", "B231", "B232",
                   # Batch B-14（v0.9.94 · 腿① 续加锚 · 定常对流–扩散中心差分/第二类 Fredholm 可分核 Nyström/自然三次样条逼近/非线性两点边值打靶法）
                   "B233", "B234", "B235", "B236", "B237", "B238", "B239", "B240",
                   "B241", "B242", "B243", "B244", "B245", "B246", "B247", "B248",
                   # Batch B-15（v0.9.95 · 腿① 续加锚 · 延迟泛函微分方程分步法/双调和薄板 13 点差分/一维输运半拉格朗日特征线/聚焦 NLSE 孤子分裂步 Fourier）
                   "B249", "B250", "B251", "B252", "B253", "B254", "B255", "B256",
                   "B257", "B258", "B259", "B260", "B261", "B262", "B263", "B264",
                   # Batch B-16（v0.9.96 · 腿① 续加锚 · Burgers tanh 行波 RK4+中心差分/广义指数积分 E_n 复合 Simpson/Haar 小波多分辨投影逐层低通）
                   "B265", "B266", "B267", "B268", "B269", "B270",
                   "B271", "B272", "B273", "B274", "B275",
                   "B276", "B277", "B278", "B279", "B280",
                   "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10",
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
