# LDA 锚题覆盖矩阵（33 类 × 52 锚 · T-9）

> 生成：2026-09-07 · 生成器 `lda/run_anchor_coverage_matrix.py`（可复现：改归属表后重跑）
> 口径：**品类×锚覆盖** = 该锚的物理对象/判决对象落在该设计品类上。覆盖 ≠ 已接独立候选；●=严格独立已接、△=降级量级参考（有候选但不进死标量判决）、◐=自证桩（名义覆盖）。证据分级：**C**=引擎 specs 代码显式引用（最权威）· **T**=锚 title/metric 明写该品类 · **K**=引擎真判决锚在 52 集外（语料锚），所列 52 锚仅为名义邻居· **i**=编辑推断 · **P**=横向/系统层。

## 0 · 摘要

- 33 类 = 22 引擎（光子 15 + 量子 7）+ 11 包；52 锚（含 v0.9.39 B29/B30、v0.9.51 E8/E9 升格）；严格独立 **477** / 降级量级参考 **3** / 自证桩 **19**
- 有 ≥1 锚宿主（52 集内）：引擎 **22/22**、包 **8/11**
- 横向/系统层锚（无单一品类宿主）**13**：B1, B8, B17, B19, S1, S3, S5, S6, S7, S8, S9, S10, S11
- 零覆盖品类与接线建议见 §3；完整归属见 §2。

## 1 · 品类 → 锚覆盖矩阵（33 行）

每类一行：命中锚序列 `锚id(符号·证据)`；**空 = 52 集内零覆盖**。

| # | 品类（域） | 52 集覆盖锚 | 覆盖数 |
|---|---|---|---|
| 1 | **Waveguide**（引擎） | B2●i · E1◐i · E2●C | 3 |
| 2 | **BraggMirror**（引擎） | B15●i | 1 |
| 3 | **RingResonator**（引擎） | B3●i · B4●C · B11●T · E3◐T | 4 |
| 4 | **MziInterferometer**（引擎） | B20●i | 1 |
| 5 | **PhCCavity**（引擎） | B21△C | 1 |
| 6 | **Mmi1x2**（引擎） | B16●C | 1 |
| 7 | **GratingCoupler2**（引擎） | B15●i | 1 |
| 8 | **DirectionalCoupler2**（引擎） | B14●C | 1 |
| 9 | **YbranchLoss**（引擎） | B5●C · E9△T | 2 |
| 10 | **GratingEff**（引擎） | B6●C · E8●T | 2 |
| 11 | **Crossing**（引擎） | B7●T · E4◐K · E7◐K | 3 |
| 12 | **MmiEl**（引擎） | E5◐K | 1 |
| 13 | **SinPl**（引擎） | E2●i · E6◐K | 2 |
| 14 | **PhaseShifter**（引擎） | B29●T | 1 |
| 15 | **MziModulator**（引擎） | B28●i | 1 |
| 16 | **Transmon**（引擎） | B9●C | 1 |
| 17 | **ReadoutResonator**（引擎） | B12●i · B22●C | 2 |
| 18 | **Fluxonium**（引擎） | B23●C | 1 |
| 19 | **TunableCoupler**（引擎） | B24●C | 1 |
| 20 | **TunableTransmon**（引擎） | B25●C | 1 |
| 21 | **ReadoutPair**（引擎） | B18◐i · B26●C | 2 |
| 22 | **CzGate**（引擎） | B27●C | 1 |
| 23 | **add_drop**（包） | B4●T · S13●i | 2 |
| 24 | **quantum**（包） | B9●i · B10●i · B13●i · S4◐i | 4 |
| 25 | **wdm**（包） | S2◐T · S12◐T · S13●i | 3 |
| 26 | **readout_chain**（包） | B18◐i · B22●i · B26●i | 3 |
| 27 | **multiqubit**（包） | B13●i · S12◐T | 2 |
| 28 | **readout_fidelity**（包） | B30●T | 1 |
| 29 | **multiqubit_fidelity**（包） | S4◐i · S12◐T | 2 |
| 30 | **mixed_system**（包） | 🚫 **零覆盖** | 0 |
| 31 | **coupler**（包） | B14●T | 1 |
| 32 | **wdm_coupler**（包） | 🚫 **零覆盖** | 0 |
| 33 | **splitter_readout**（包） | 🚫 **零覆盖** | 0 |

**横向/系统层锚**（不归属单一品类，按适用层列出）：

| 锚 | 分类 | 适用层 / 宿主 | 态 |
|---|---|---|---|
| B1 | ⟂求解核·Mie 散射 | 散射效率 Q_scat（已接=严格独立）；33 类无散射体品类 ⇒ 求解核级锚（lda_solver/mie_solver） | ● |
| B8 | ⟂求解核·绝热锥度 EME | T→1 绝热极限（已接=严格独立）；33 类无锥度品类 ⇒ 求解核/互连级锚（EME 核，taper 内嵌于布局路由） | ● |
| B17 | ⟂基础量·约瑟夫森 Ic | I_c=2e·E_J/ℏ；量子结参数基础量，33 类无独立宿主 | ◐ |
| B19 | ⟂物理·链路 passivity | max|T|≤1 无源链路守恒（已接=严格独立）；宿主=全部无源链路品类 | ● |
| S1 | ⟂系统层·光链路预算 | 纯算术 dB 级联判决；宿主=lda_chain 全部光链路设计（wdm/add_drop/耦合器/…），不细分品类 | ◐ |
| S2 | ⟂系统层·WDM 信道规划 | 信道间隔−滤波器带宽>0 纯算术；宿主=wdm 包信道规划（title 明示 WDM 信道） | ◐ |
| S3 | ⟂系统层·OSNR | ASE 级联解析；宿主=含放大光链路设计流 | ◐ |
| S4 | ⟂系统层·量子保真度预算 | F_total=∏fᵢ 乘法级联；宿主=量子门序列/多比特系统设计流（quantum/multiqubit） | ◐ |
| S5 | ⟂系统层·最坏情况预算 | 工艺角最坏 margin；宿主=光链路设计流 | ◐ |
| S6 | ⟂系统层·探测器灵敏度 | P_rx−Sens margin；宿主=接收链路设计流 | ◐ |
| S7 | ⟂系统层·统计预算 p5 | MC 分布 p5（高斯闭式候选已接=严格独立）；宿主=光链路设计流 | ● |
| S8 | ⟂系统层·OSNR 统计 p5 | MC OSNR 分布 p5（已接=严格独立）；宿主=含放大链路设计流 | ● |
| S9 | ⟂签核·LVS | 版图-原理图一致性签核；宿主=全部含版图的品类（引擎/包通用，结构性不可接 C1+C3） | ◐ |
| S10 | ⟂签核·多层 LVS | M1/VIA/M2 层叠签核；宿主=多层布线版图品类（结构性不可接 C1+C3） | ◐ |
| S11 | ⟂签核·千器件规模 | 1000 器件全链路 ACCEPT；宿主=规模流水线（无独立品类） | ◐ |
| S12 | ⟂统计·阵列分布 | 均值+下界+离群三锚 AND；宿主=WDM/CPO 多通道、量子多比特阵列（wdm/multiqubit/multiqubit_fidelity） | ◐ |
| S13 | ⟂统计·设计良率 DFY | 环形 FSR 光刻容差命中概率（已接=严格独立）；宿主=环类产品（add_drop/wdm） | ● |

## 2 · 锚 → 归属明细（52 行）

| 锚 | 判据态 | oracle | 宿主（品类 / 横向层） | 证据 |
|---|---|---|---|---|
| B1 | 严格独立 | analytical(Rayleigh-limit) | ⟂求解核·Mie 散射 | P ｜ ⟂求解核·Mie 散射: 散射效率 Q_scat（已接=严格独立）；33 类无散射体品类 ⇒ 求解核级锚（lda_solver/mie_solver） |
| B2 | 严格独立 | analytical(EIM) | Waveguide | i ｜ Waveguide: EIM/slab 有效折射率；引擎 cheap=_slab_te_neff 同族（gapdoc: 波导） |
| B3 | 严格独立 | analytical(Airy) | RingResonator | i ｜ RingResonator: Airy 腔 FSR 无独立品类；FSR 口径方法学挂谐振腔家族（与 B4/B20 并列对照） |
| B4 | 严格独立 | analytical(ring)/sax | RingResonator、add_drop | CT ｜ RingResonator: 引擎 FSR 解析锚 λ²/(n_g·2πR)，engine note 同式；add_drop: 锚对象即 add-drop 环形谐振器 drop 口传递函数 |
| B5 | 严格独立 | design-rule(Meep/Tidy3D field 预留) | YbranchLoss | C ｜ YbranchLoss: 引擎真判决锚已升格为 E9（E-YBRANCH-LOSS，degraded_ordinal 量级参考，c1 未标定唯象系数 rel≈43%）；B5=理想 50/50 下限 3.0dB 守则桩（同器件名义覆盖） |
| B6 | 严格独立 | design-rule(Tidy3D/Meep field 预留) | GratingEff | C ｜ GratingEff: 引擎真判决锚已升格为 E8（E-GRATING-EFF，strict 严格独立，rel≈3.3%）；B6=成熟工艺可达效率 0.5 守则桩（同器件名义覆盖） |
| B7 | 严格独立 | design-rule(+Meep field 预留) | Crossing | T ｜ Crossing: 波导交叉串扰；引擎 IL+XT 双出口，E7=实测 XT 同器件（守则桩 vs 实证桩） |
| B8 | 严格独立 | analytical(adiabatic-limit) | ⟂求解核·绝热锥度 EME | P ｜ ⟂求解核·绝热锥度 EME: T→1 绝热极限（已接=严格独立）；33 类无锥度品类 ⇒ 求解核/互连级锚（EME 核，taper 内嵌于布局路由） |
| B9 | 严格独立 | analytical(transmon/Koch2007) | Transmon、quantum | Ci ｜ Transmon: 引擎 cheap=koch_f01 即 B9 golden 同式；quantum: 量子逆设计包（Transmon）同物理 |
| B10 | 严格独立 | analytical(lindblad-closed-form) | quantum | i ｜ quantum: 单比特门退相干极限保真度；门层无独立引擎品类 ⇒ 量子系统/门层锚；单比特门退相干保真度：量子门层锚；品类宿主仅 quantum 包（○），主缺口=两比特门锚（gapdoc 钉子 C 候选） |
| B11 | 严格独立 | analytical(ring-transfer-function) | RingResonator | T ｜ RingResonator: 环形谐振器 drop 口透射谱谱形 L2（结构性不可接，见 T-4 侦察） |
| B12 | 严格独立 | analytical(quarter-wave closed form) | ReadoutResonator | i ｜ ReadoutResonator: λ/4 超导谐振器通式（与 B22 CPW 具体化并列，同引擎宿主） |
| B13 | 严格独立 | analytical(charge-coupling closed form) | quantum、multiqubit | i ｜ quantum: 双 transmon 电容耦合 J；无独立双比特引擎 ⇒ quantum 包（频率/耦合设计）；multiqubit: N-qubit 频率复用读出依赖 J 间隔规划（弱） |
| B14 | 严格独立 | analytical(coupled-mode) | DirectionalCoupler2、coupler | CT ｜ DirectionalCoupler2: 引擎 cheap=b14_dc_coupling_length，note 显式 B14；coupler: 包=方向耦合器设计闭环（D-55），锚=3dB 耦合长度 |
| B15 | 严格独立 | analytical(Bragg condition) | BraggMirror、GratingCoupler2 | i ｜ BraggMirror: Bragg 条件 λ_B=2·n_eff·Λ；镜周期设计同族（gapdoc: Bragg）；GratingCoupler2: λ_B=Λ·n_eff 同一阶相位匹配 |
| B16 | 严格独立 | design-rule(general-interference) | Mmi1x2 | C ｜ Mmi1x2: 引擎 note 显式 B16 锚（结构性不可接 C5+C3） |
| B17 | 自证桩 | analytical(Josephson relation) | ⟂基础量·约瑟夫森 Ic | P ｜ ⟂基础量·约瑟夫森 Ic: I_c=2e·E_J/ℏ；量子结参数基础量，33 类无独立宿主 |
| B18 | 自证桩 | analytical(cavity-QED) | ReadoutPair、readout_chain | i ｜ ReadoutPair: 腔 QED 增强因子 F_P=4g²/(κγ₁)；读出/比特配对物理（弱）；readout_chain: 色散读出链路（复用 D-88 参数，弱） |
| B19 | 严格独立 | analytical(passive-network: 无外部泵浦 ⇒ |T|≤1) | ⟂物理·链路 passivity | P ｜ ⟂物理·链路 passivity: max|T|≤1 无源链路守恒（已接=严格独立）；宿主=全部无源链路品类 |
| B20 | 严格独立 | analytical(MZI interference) | MziInterferometer | i ｜ MziInterferometer: MZI FSR=λ²/(n_eff·ΔL) 同式（engine note 即 B20 物理） |
| B21 | 降级量级参考 | analytical(PhC Bragg/FP band-edge) | PhCCavity | C ｜ PhCCavity: 引擎 cheap=b21_phc_resonance，note 显式 B21（结构性不可接 C2） |
| B22 | 严格独立 | analytical(CPW λ/4 TL resonance) | ReadoutResonator、readout_chain | Ci ｜ ReadoutResonator: 引擎 cheap=b22_qres_frequency，note 显式 B22；readout_chain: CPW λ/4 读出谐振器=readout 链核心元件 |
| B23 | 严格独立 | analytical(LC oscillator strict limit E_J→0) | Fluxonium | C ｜ Fluxonium: 引擎 note 显式 B23 LC 极限边界校验 |
| B24 | 严格独立 | analytical(2nd-order perturbation / Schrieffer-Wolff) | TunableCoupler | C ｜ TunableCoupler: 引擎 cheap=b24_tcoup_geff，note 显式 B24 |
| B25 | 严格独立 | analytical(SQUID E_J(Φ)=E_JΣ·|cos(πΦ/Φ0)| + Koch) | TunableTransmon | C ｜ TunableTransmon: 引擎 cheap=b25_tunable_transmon_f01，note 显式 B25 |
| B26 | 严格独立 | analytical(Blais χ=g²α/(Δ(Δ+α))) | ReadoutPair、readout_chain | Ci ｜ ReadoutPair: 引擎 cheap=b26_dispersive_shift，note 显式 B26；readout_chain: 色散位移 χ=readout 链核心设计量 |
| B27 | 严格独立 | analytical(t_CZ=π/(2|χ|)) | CzGate | C ｜ CzGate: 引擎 cheap=b27_cz_gate_time，note 显式 B27 |
| B28 | 严格独立 | analytical(MZM Pockels half-wave) + integral-bisect cross-check | MziModulator | i ｜ MziModulator: 引擎目标 V_π（Pockels）与 B28 同物理量同闭式 |
| B29 | 严格独立 | analytical(1D fin PDE closed-form) + FDM cross-check | PhaseShifter | T ｜ PhaseShifter: 热光相移效率锚（D-73 升格）：引擎 specs 标「D-73 同源锚」、cheap=phase_efficiency_deg_per_mW；B29=同 PDE 散热鳍稳态解 cosh 闭式（thermal_phase_fdm 独立候选）。v0.9.39 已落地，严格独立。 |
| B30 | 严格独立 | analytical(erfc readout chain) + gaussian-overlap quad cross-check | readout_fidelity | T ｜ readout_fidelity: 单发读出保真度 F 锚（Krantz 2019 色散读出链 erfc 闭式）；包名 readout_fidelity 即 B30 物理对象，候选=误判概率 ε 高斯重叠数值积分（readout_fidelity_quad）。v0.9.39 已落地，严格独立。 |
| B31 | 严格独立 | analytical(Soref-Bennett 1987 @1550nm 幂律闭式) + Drude 等离子体 independent_cross_check | 🚫 **零宿主** | — |
| B32 | 严格独立 | analytical(QCSE 二阶微扰闭式 Miller 1985) + 1D Schrodinger finite-difference diagonalization independent_cross_check | 🚫 **零宿主** | — |
| B33 | 严格独立 | analytical(RC bandwidth closed-form) + timestep-ODE-fit cross-check | 🚫 **零宿主** | — |
| B34 | 严格独立 | analytical(Marcatili 1969 等效宽度近似) + strict_transverse_resonance_bisection independent_cross_check | 🚫 **零宿主** | — |
| B36 | 严格独立 | analytical(TE10 cutoff c/(2a)) + 1D FD eigenmode_bisection independent_cross_check | 🚫 **零宿主** | — |
| B37 | 严格独立 | analytical(TE20 cutoff c/a) + 1D FD eigenmode_mode2 independent_cross_check | 🚫 **零宿主** | — |
| B40 | 严格独立 | analytical(TE11 cutoff c/(2π)√((π/a)²+(π/b)²)) + 2D FD eigenmode independent_cross_check | 🚫 **零宿主** | — |
| B41 | 严格独立 | analytical(FP resonance 2nL/m) + 1D FD cavity_mode independent_cross_check | 🚫 **零宿主** | — |
| B42 | 严格独立 | analytical(infinite square well E1=ℏ²π²/(2mL²)) + 1D FD Hamiltonian eigenmode independent_cross_check | 🚫 **零宿主** | — |
| B43 | 严格独立 | analytical(infinite square well E2=4ℏ²π²/(2mL²)) + 1D FD Hamiltonian eigenmode_mode2 independent_cross_check | 🚫 **零宿主** | — |
| B44 | 严格独立 | analytical(infinite square well E3=9ℏ²π²/(2mL²)) + 1D FD Hamiltonian eigenmode_mode3 independent_cross_check | 🚫 **零宿主** | — |
| B45 | 严格独立 | analytical(harmonic oscillator E0=½ℏω) + 1D FD oscillator Hamiltonian eigenmode independent_cross_check | 🚫 **零宿主** | — |
| B46 | 严格独立 | analytical(harmonic oscillator E1=1.5ℏω) + 1D FD oscillator Hamiltonian eigenmode_mode2 independent_cross_check | 🚫 **零宿主** | — |
| B47 | 严格独立 | analytical(harmonic oscillator E2=2.5ℏω) + 1D FD oscillator Hamiltonian eigenmode_mode3 independent_cross_check | 🚫 **零宿主** | — |
| B48 | 严格独立 | analytical(finite square well even-parity transcendental bisection) + 1D FD Hamiltonian eigenmode independent_cross_check | 🚫 **零宿主** | — |
| B49 | 严格独立 | analytical(barrier transmission T=1/(1+V0²sinh²(κa)/(4E(V0-E)))) + 1D FD Numerov scattering independent_cross_check | 🚫 **零宿主** | — |
| B50 | 严格独立 | analytical(TE30 cutoff 3c/(2a)) + 1D FD eigenmode_mode3 independent_cross_check | 🚫 **零宿主** | — |
| B51 | 严格独立 | analytical(TE40 cutoff 2c/a) + 1D FD eigenmode_mode4 independent_cross_check | 🚫 **零宿主** | — |
| B52 | 严格独立 | analytical(finite square well odd-parity transcendental bisection) + 1D FD Hamiltonian eigenmode_mode2 independent_cross_check | 🚫 **零宿主** | — |
| B53 | 严格独立 | analytical(finite square well even-parity transcendental bisection) + 1D FD Hamiltonian eigenmode_mode3 independent_cross_check | 🚫 **零宿主** | — |
| B54 | 严格独立 | analytical(infinite square well E4=16ℏ²π²/(2mL²)) + 1D FD Hamiltonian eigenmode_mode4 independent_cross_check | 🚫 **零宿主** | — |
| B55 | 严格独立 | analytical(infinite square well E5=25ℏ²π²/(2mL²)) + 1D FD Hamiltonian eigenmode_mode5 independent_cross_check | 🚫 **零宿主** | — |
| B56 | 严格独立 | analytical(harmonic oscillator E3=3.5ℏω) + 1D FD oscillator Hamiltonian eigenmode_mode4 independent_cross_check | 🚫 **零宿主** | — |
| B57 | 严格独立 | analytical(harmonic oscillator E4=4.5ℏω) + 1D FD oscillator Hamiltonian eigenmode_mode5 independent_cross_check | 🚫 **零宿主** | — |
| B58 | 严格独立 | analytical(3D cubic infinite well ground state 3E1) + 3×1D FD eigenmode_sum independent_cross_check | 🚫 **零宿主** | — |
| B59 | 严格独立 | analytical(Pöschl-Teller exact bound-state spectrum) + 1D FD Hamiltonian eigenmode independent_cross_check | 🚫 **零宿主** | — |
| B60 | 严格独立 | analytical(Pöschl-Teller exact bound-state spectrum n=1) + 1D FD Hamiltonian eigenmode_mode2 independent_cross_check | 🚫 **零宿主** | — |
| B61 | 严格独立 | analytical(rectangular waveguide TM11 cutoff c/2·√((1/a)²+(1/b)²)) + 2×1D Dirichlet box FD eigen_k product independent_cross_check | 🚫 **零宿主** | — |
| B62 | 严格独立 | analytical(rectangular waveguide TM21 cutoff c/2·√((2/a)²+(1/b)²)) + 2×1D Dirichlet box FD eigen_k product independent_cross_check | 🚫 **零宿主** | — |
| B63 | 严格独立 | analytical(circular waveguide TE11 cutoff x11·c/(2πa), x11=J1 first zero) + radial ODE integration + boundary root-find independent_cross_check | 🚫 **零宿主** | — |
| B64 | 严格独立 | analytical(uniform Bragg grating λB=2·n_eff·Λ) + transfer-matrix trace root-find independent_cross_check | 🚫 **零宿主** | — |
| B65 | 严格独立 | analytical(square-barrier sinh²) | 🚫 **零宿主** | — |
| B66 | 严格独立 | analytical(square-barrier sinh²) | 🚫 **零宿主** | — |
| B67 | 严格独立 | analytical(square-barrier sin²) | 🚫 **零宿主** | — |
| B68 | 严格独立 | analytical(square-barrier R=1−T) | 🚫 **零宿主** | — |
| B70 | 严格独立 | analytical(double-barrier resonance, T_peak→1) | 🚫 **零宿主** | — |
| B71 | 严格独立 | analytical(double-barrier transfer-matrix) | 🚫 **零宿主** | — |
| B73 | 严格独立 | analytical(finite-well scatter resonance) | 🚫 **零宿主** | — |
| B74 | 严格独立 | analytical(finite-well scatter antiresonance) | 🚫 **零宿主** | — |
| B75 | 严格独立 | analytical(delta-barrier T=1/(1+(mα/ℏ²k0)²)) | 🚫 **零宿主** | — |
| B76 | 严格独立 | analytical(delta-barrier R=1−T) | 🚫 **零宿主** | — |
| B77 | 严格独立 | analytical(step T=4k1k2/(k1+k2)²) | 🚫 **零宿主** | — |
| B78 | 严格独立 | analytical(step R=1, total reflection) | 🚫 **零宿主** | — |
| B79 | 严格独立 | analytical(Kronig-Penney exact M^N) | 🚫 **零宿主** | — |
| B80 | 严格独立 | analytical(asymmetric double-barrier transfer-matrix) | 🚫 **零宿主** | — |
| B81 | 严格独立 | analytical(square-barrier sinh²) | 🚫 **零宿主** | — |
| B82 | 严格独立 | analytical(square-barrier R=1−T) | 🚫 **零宿主** | — |
| B83 | 严格独立 | analytical(square-barrier sin²) | 🚫 **零宿主** | — |
| B84 | 严格独立 | analytical(finite-well R=1−T) | 🚫 **零宿主** | — |
| B85 | 严格独立 | analytical(delta-barrier T=1/(1+(mα/ℏ²k0)²)) | 🚫 **零宿主** | — |
| B86 | 严格独立 | analytical(step R=1, total reflection) | 🚫 **零宿主** | — |
| B87 | 严格独立 | analytical(square-barrier sinh²) | 🚫 **零宿主** | — |
| B88 | 严格独立 | analytical(double-barrier transfer-matrix) | 🚫 **零宿主** | — |
| B89 | 严格独立 | analytical(hydrogen Rydberg E_n=-RYDBERG·Z²/n²) | 🚫 **零宿主** | — |
| B90 | 严格独立 | analytical(hydrogen Rydberg E_n=-RYDBERG·Z²/n²) | 🚫 **零宿主** | — |
| B91 | 严格独立 | analytical(hydrogen Rydberg E_n=-RYDBERG·Z²/n²) | 🚫 **零宿主** | — |
| B92 | 严格独立 | analytical(hydrogen Rydberg E_n=-RYDBERG·Z²/n²) | 🚫 **零宿主** | — |
| B93 | 严格独立 | analytical(hydrogen Rydberg E_n=-RYDBERG·Z²/n²) | 🚫 **零宿主** | — |
| B94 | 严格独立 | analytical(hydrogen Rydberg E_n=-RYDBERG·Z²/n²) | 🚫 **零宿主** | — |
| B95 | 严格独立 | analytical(3D-HO E=(2n_r+l+3/2)·ℏω) | 🚫 **零宿主** | — |
| B96 | 严格独立 | analytical(3D-HO E=(2n_r+l+3/2)·ℏω) | 🚫 **零宿主** | — |
| B97 | 严格独立 | analytical(3D-HO E=(2n_r+l+3/2)·ℏω) | 🚫 **零宿主** | — |
| B98 | 严格独立 | analytical(circular waveguide cutoff fc=X·c/(2πa), Bessel zero X'_21) | 🚫 **零宿主** | — |
| B99 | 严格独立 | analytical(circular waveguide cutoff fc=X·c/(2πa), Bessel zero X_01) | 🚫 **零宿主** | — |
| B100 | 严格独立 | analytical(circular waveguide cutoff fc=X·c/(2πa), Bessel zero X'_01) | 🚫 **零宿主** | — |
| B101 | 严格独立 | analytical(rectangular waveguide cutoff fc=c/2·√((m/a)²+(n/b)²)) | 🚫 **零宿主** | — |
| B102 | 严格独立 | analytical(rectangular waveguide cutoff fc=c/2·√((m/a)²+(n/b)²)) | 🚫 **零宿主** | — |
| B103 | 严格独立 | analytical(rectangular waveguide cutoff fc=c/2·√((m/a)²+(n/b)²)) | 🚫 **零宿主** | — |
| B104 | 严格独立 | analytical(rectangular waveguide cutoff fc=c/2·√((m/a)²+(n/b)²)) | 🚫 **零宿主** | — |
| B105 | 严格独立 | analytical(rigid rotor E_J=ℏ²J(J+1)/(2I), associated-Legendre FD) | 🚫 **零宿主** | — |
| B106 | 严格独立 | analytical(rigid rotor E_J=ℏ²J(J+1)/(2I), associated-Legendre FD) | 🚫 **零宿主** | — |
| B107 | 严格独立 | analytical(rigid rotor E_J=ℏ²J(J+1)/(2I), associated-Legendre FD) | 🚫 **零宿主** | — |
| B108 | 严格独立 | analytical(rigid rotor E_J=ℏ²J(J+1)/(2I), associated-Legendre FD) | 🚫 **零宿主** | — |
| B109 | 严格独立 | analytical(rigid rotor E_J=ℏ²J(J+1)/(2I), associated-Legendre FD) | 🚫 **零宿主** | — |
| B110 | 严格独立 | analytical(rigid rotor E_J=ℏ²J(J+1)/(2I), associated-Legendre FD) | 🚫 **零宿主** | — |
| B111 | 严格独立 | analytical(2D infinite square well E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²), 2D FD Laplacian) | 🚫 **零宿主** | — |
| B112 | 严格独立 | analytical(2D infinite square well E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²), 2D FD Laplacian) | 🚫 **零宿主** | — |
| B113 | 严格独立 | analytical(2D infinite square well E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²), 2D FD Laplacian) | 🚫 **零宿主** | — |
| B114 | 严格独立 | analytical(2D infinite square well E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²), 2D FD Laplacian) | 🚫 **零宿主** | — |
| B115 | 严格独立 | analytical(triangular well E_n=(ℏ²F²/2m_e)^{1/3}·ζ_n, Airy zero, 1D FD) | 🚫 **零宿主** | — |
| B116 | 严格独立 | analytical(triangular well E_n=(ℏ²F²/2m_e)^{1/3}·ζ_n, Airy zero, 1D FD) | 🚫 **零宿主** | — |
| B117 | 严格独立 | analytical(triangular well E_n=(ℏ²F²/2m_e)^{1/3}·ζ_n, Airy zero, 1D FD) | 🚫 **零宿主** | — |
| B118 | 严格独立 | analytical(3D spherical well E_nl=x_nl²ℏ²/(2mR²), spherical Bessel zero, 3D radial FD) | 🚫 **零宿主** | — |
| B119 | 严格独立 | analytical(3D spherical well E_nl=x_nl²ℏ²/(2mR²), spherical Bessel zero, 3D radial FD) | 🚫 **零宿主** | — |
| B120 | 严格独立 | analytical(3D spherical well E_nl=x_nl²ℏ²/(2mR²), spherical Bessel zero, 3D radial FD) | 🚫 **零宿主** | — |
| B121 | 严格独立 | analytical(Morse E_n=ℏω(n+½)−[ℏω(n+½)]²/(4D_e), ω=a√(2D_e/μ), 1D FD Schrödinger) | 🚫 **零宿主** | — |
| B122 | 严格独立 | analytical(Morse E_n=ℏω(n+½)−[ℏω(n+½)]²/(4D_e), 1D FD Schrödinger) | 🚫 **零宿主** | — |
| B123 | 严格独立 | analytical(Morse E_n=ℏω(n+½)−[ℏω(n+½)]²/(4D_e), 1D FD Schrödinger) | 🚫 **零宿主** | — |
| B124 | 严格独立 | analytical(Morse E_n=ℏω(n+½)−[ℏω(n+½)]²/(4D_e), 1D FD Schrödinger) | 🚫 **零宿主** | — |
| B125 | 严格独立 | analytical(2D anisotropic HO E=ℏω_x(n_x+½)+ℏω_y(n_y+½), 2D FD Kronecker sum) | 🚫 **零宿主** | — |
| B126 | 严格独立 | analytical(2D anisotropic HO E=ℏω_x(n_x+½)+ℏω_y(n_y+½), 2D FD Kronecker sum) | 🚫 **零宿主** | — |
| B127 | 严格独立 | analytical(2D anisotropic HO E=ℏω_x(n_x+½)+ℏω_y(n_y+½), 2D FD Kronecker sum) | 🚫 **零宿主** | — |
| B128 | 严格独立 | analytical(2D anisotropic HO E=ℏω_x(n_x+½)+ℏω_y(n_y+½), 2D FD Kronecker sum) | 🚫 **零宿主** | — |
| B129 | 严格独立 | analytical(3D box E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²+n_z²/L_z²), 3D FD Kronecker sum) | 🚫 **零宿主** | — |
| B130 | 严格独立 | analytical(3D box E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²+n_z²/L_z²), 3D FD Kronecker sum) | 🚫 **零宿主** | — |
| B131 | 严格独立 | analytical(3D box E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²+n_z²/L_z²), 3D FD Kronecker sum) | 🚫 **零宿主** | — |
| B132 | 严格独立 | analytical(3D box E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²+n_z²/L_z²), 3D FD Kronecker sum) | 🚫 **零宿主** | — |
| B133 | 严格独立 | analytical(hydrogen-like E_n=−RYDBERG·Z²/n², radial FD Schrödinger) | 🚫 **零宿主** | — |
| B134 | 严格独立 | analytical(hydrogen-like E_n=−RYDBERG·Z²/n², radial FD Schrödinger) | 🚫 **零宿主** | — |
| B135 | 严格独立 | analytical(hydrogen-like E_n=−RYDBERG·Z²/n², radial FD Schrödinger) | 🚫 **零宿主** | — |
| B136 | 严格独立 | analytical(hydrogen-like E_n=−RYDBERG·Z²/n², radial FD Schrödinger) | 🚫 **零宿主** | — |
| B137 | 严格独立 | analytical(2D Coulomb E=−Z²·Ry/(N−½)², N=n_r+|m|+1, 2D radial FD) | 🚫 **零宿主** | — |
| B138 | 严格独立 | analytical(2D Coulomb E=−Z²·Ry/(N−½)², 2D radial FD) | 🚫 **零宿主** | — |
| B139 | 严格独立 | analytical(2D Coulomb E=−Z²·Ry/(N−½)², 2D radial FD) | 🚫 **零宿主** | — |
| B140 | 严格独立 | analytical(2D Coulomb E=−Z²·Ry/(N−½)², 2D radial FD) | 🚫 **零宿主** | — |
| B141 | 严格独立 | analytical(annulus Bessel cross-product J_ν(kR_i)Y_ν(kR_o)−Y_ν(kR_i)J_ν(kR_o)=0, E=ℏ²k²/2m) | 🚫 **零宿主** | — |
| B142 | 严格独立 | analytical(annulus Bessel cross-product zeros, E=ℏ²k²/2m) | 🚫 **零宿主** | — |
| B143 | 严格独立 | analytical(Aharonov-Bohm annulus Bessel cross-product, ν=|m+Φ/Φ₀|, E=ℏ²k²/2m) | 🚫 **零宿主** | — |
| B144 | 严格独立 | analytical(Aharonov-Bohm annulus Bessel cross-product, ν=|m+Φ/Φ₀|, E=ℏ²k²/2m) | 🚫 **零宿主** | — |
| B145 | 严格独立 | analytical(finite spherical well transcendental k·cot(kR)=−κ, 3D radial FD) | 🚫 **零宿主** | — |
| B146 | 严格独立 | analytical(finite spherical well transcendental k·cot(kR)=−κ, 3D radial FD) | 🚫 **零宿主** | — |
| B147 | 严格独立 | analytical(finite spherical well transcendental k·cot(kR)=−κ, 3D radial FD) | 🚫 **零宿主** | — |
| B148 | 严格独立 | analytical(finite spherical well transcendental k·cot(kR)=−κ, 3D radial FD) | 🚫 **零宿主** | — |
| B149 | 严格独立 | analytical(3D HO E=ℏ(ω_x(n_x+½)+ω_y(n_y+½)+ω_z(n_z+½)), 3D FD Kronecker sum) | 🚫 **零宿主** | — |
| B150 | 严格独立 | analytical(anisotropic 3D HO E=ℏ(ω_x(n_x+½)+ω_y(n_y+½)+ω_z(n_z+½)), 3D FD Kronecker sum) | 🚫 **零宿主** | — |
| B151 | 严格独立 | analytical(anisotropic 3D HO, 3D FD Kronecker sum) | 🚫 **零宿主** | — |
| B152 | 严格独立 | analytical(anisotropic 3D HO, 3D FD Kronecker sum) | 🚫 **零宿主** | — |
| B153 | 严格独立 | analytical(Euler-Bernoulli 固支梁超越方程 cos(βL)cosh(βL)=1 根 ⇒ f_n=(β_nL)²/(2πL²)·√(E·I/(ρ·A)), Hermite 梁单元 FEM) | 🚫 **零宿主** | — |
| B154 | 严格独立 | analytical(Euler-Bernoulli 固支梁 cos(βL)cosh(βL)=1 第 2 根, Hermite 梁单元 FEM) | 🚫 **零宿主** | — |
| B155 | 严格独立 | analytical(Euler-Bernoulli 固支梁 cos(βL)cosh(βL)=1 第 3 根, Hermite 梁单元 FEM) | 🚫 **零宿主** | — |
| B156 | 严格独立 | analytical(Euler-Bernoulli 固支梁 cos(βL)cosh(βL)=1 第 4 根, Hermite 梁单元 FEM) | 🚫 **零宿主** | — |
| B157 | 严格独立 | analytical(Hulthen s-wave E_n=-V₀[(β²-n²)/(2nβ)]², β²=2mV₀a²/ℏ², 3D 径向 FD) | 🚫 **零宿主** | — |
| B158 | 严格独立 | analytical(Hulthen s-wave 闭式, 3D 径向 FD) | 🚫 **零宿主** | — |
| B159 | 严格独立 | analytical(Hulthen s-wave 闭式, 3D 径向 FD) | 🚫 **零宿主** | — |
| B160 | 严格独立 | analytical(Hulthen s-wave 闭式, 3D 径向 FD) | 🚫 **零宿主** | — |
| B161 | 严格独立 | analytical(Fock-Darwin ε=ℏΩ(2n_r+|m|+1)−(ℏω_c/2)m, Ω=√(ω₀²+ω_c²/4), 2D 径向 FD) | 🚫 **零宿主** | — |
| B162 | 严格独立 | analytical(Fock-Darwin 闭式, 2D 径向 FD) | 🚫 **零宿主** | — |
| B163 | 严格独立 | analytical(Fock-Darwin 闭式, 2D 径向 FD) | 🚫 **零宿主** | — |
| B164 | 严格独立 | analytical(Fock-Darwin 闭式, 2D 径向 FD) | 🚫 **零宿主** | — |
| B165 | 严格独立 | analytical(Rosen-Morse II E_n=−(ℏ²α²/2μ)(a_n²+b_n²), b_n=√(γ+¼)−n−½, a_n=−β/(2b_n), 1D FD) | 🚫 **零宿主** | — |
| B166 | 严格独立 | analytical(Rosen-Morse II 闭式, 1D FD) | 🚫 **零宿主** | — |
| B167 | 严格独立 | analytical(Rosen-Morse II 闭式, 1D FD) | 🚫 **零宿主** | — |
| B168 | 严格独立 | analytical(Rosen-Morse II 闭式, 1D FD) | 🚫 **零宿主** | — |
| B169 | 严格独立 | special_function(Mathieu 特征值 scipy.special.mathieu_a/b 机器精度, 半周期 [0,π/2] P1-FEM 广义本征) | 🚫 **零宿主** | — |
| B170 | 严格独立 | special_function(Mathieu a₁, 半周期 P1-FEM 广义本征 BC=(N,D), k=0) | 🚫 **零宿主** | — |
| B171 | 严格独立 | special_function(Mathieu b₁, 半周期 P1-FEM 广义本征 BC=(D,N), k=0) | 🚫 **零宿主** | — |
| B172 | 严格独立 | special_function(Mathieu b₂, 半周期 P1-FEM 广义本征 BC=(D,D), k=0) | 🚫 **零宿主** | — |
| B173 | 严格独立 | special_function(Mathieu a₂, 半周期 P1-FEM 广义本征 BC=(N,N), k=1) | 🚫 **零宿主** | — |
| B174 | 严格独立 | special_function(椭圆积分闭式 L=4a·E(m), m=1−b²/a² 机器精度, 复合 Simpson n=12) | 🚫 **零宿主** | — |
| B175 | 严格独立 | special_function(椭圆积分闭式 L=4a·E(m), 复合 Simpson n=12) | 🚫 **零宿主** | — |
| B176 | 严格独立 | special_function(第一类椭圆积分闭式 T/T₀=(2/π)K(m), m=sin²(θ₀/2) 机器精度, 复合 Simpson n=16) | 🚫 **零宿主** | — |
| B177 | 严格独立 | special_function(第一类椭圆积分闭式 T/T₀=(2/π)K(m), 复合 Simpson n=16) | 🚫 **零宿主** | — |
| B178 | 严格独立 | closed_form(扁椭球 N_c=(1/e²)[1−(1/e)asin(e)√(1−e²)] 初等反正弦闭式, (A/2)∫₀¹(1−t)^½/[A(1−t)+t]dt Simpson n=256) | 🚫 **零宿主** | — |
| B179 | 严格独立 | closed_form(长椭球 N_a=((1−e²)/e³)[½ln((1+e)/(1−e))−e] 初等对数闭式, (ar/2)∫₀¹(1−t)^½/[A(1−t)+t]^{3/2}dt Simpson n=256) | 🚫 **零宿主** | — |
| B180 | 严格独立 | special_function(scipy.special.fresnel 机器精度, 复合 Simpson ∫₀^u cos(πt²/2)dt n=64) | 🚫 **零宿主** | — |
| B181 | 严格独立 | special_function(scipy.special.fresnel 机器精度, 复合 Simpson ∫₀^u sin(πt²/2)dt n=64) | 🚫 **零宿主** | — |
| B182 | 严格独立 | analytical(高斯热核 R(x)=exp(−x²/4Dt) 精确, 双端零通量 Crank-Nicolson 时间推进 M=4000/nt=960) | 🚫 **零宿主** | — |
| B183 | 严格独立 | analytical(高斯热核精确, 双端零通量 Crank-Nicolson M=4000/nt=960) | 🚫 **零宿主** | — |
| B184 | 严格独立 | analytical(高斯热核精确, 双端零通量 Crank-Nicolson M=4000/nt=960) | 🚫 **零宿主** | — |
| B185 | 严格独立 | special_function(Γ(s)ζ(s) 严格闭式 scipy.special.zeta, 换元 t=x/(1+x) 后 [0,1] 复合 Simpson n=64) | 🚫 **零宿主** | — |
| B186 | 严格独立 | special_function(Γ(s)ζ(s) 闭式, 换元后的 [0,1] 复合 Simpson n=64) | 🚫 **零宿主** | — |
| B187 | 严格独立 | special_function((1−2^{1−s})Γ(s)ζ(s) 闭式, 换元后的 [0,1] 复合 Simpson n=64) | 🚫 **零宿主** | — |
| B188 | 严格独立 | special_function(Γ(s)ζ(s−1) 闭式, 换元后的 [0,1] 复合 Simpson n=64) | 🚫 **零宿主** | — |
| B189 | 严格独立 | closed_form(Kepler 第三定律 T=2π√(a³/μ), 中心力 ODE 的 RK4 时间积分 + 三次 Hermite 近心点穿越定位) | 🚫 **零宿主** | — |
| B190 | 严格独立 | closed_form(r_p=a(1−e), RK4 轨道 + 三次 Hermite 穿越插值定位 min|r|) | 🚫 **零宿主** | — |
| B191 | 严格独立 | closed_form(v_p=√(μ(2/r_p−1/a)) 活力公式, RK4 轨道 + Hermite 插值取穿越时刻 |v|) | 🚫 **零宿主** | — |
| B192 | 严格独立 | closed_form(Kepler 第三定律 T=2π√(a³/μ), RK4 时间积分 + Hermite 穿越定位) | 🚫 **零宿主** | — |
| B193 | 严格独立 | closed_form(平行同轴等尺寸矩形解析式, 4D 张量积复合 Simpson n=16) | 🚫 **零宿主** | — |
| B194 | 严格独立 | closed_form(平行同轴等尺寸矩形解析式, 4D 复合 Simpson n=16) | 🚫 **零宿主** | — |
| B195 | 严格独立 | closed_form(垂直共边矩形解析式（含对数/反正切）, 4D 张量积分块复合 Simpson n=96) | 🚫 **零宿主** | — |
| B196 | 严格独立 | closed_form(垂直共边矩形解析式, 4D 分块复合 Simpson n=96) | 🚫 **零宿主** | — |
| B197 | 严格独立 | special_function(scipy.special.voigt_profile 机器精度（Faddeeva/wofz）, 卷积定义式 sinh 换元 + 复合 Simpson n=48) | 🚫 **零宿主** | — |
| B198 | 严格独立 | special_function(scipy.special.voigt_profile 机器精度, sinh 换元 + 复合 Simpson n=64) | 🚫 **零宿主** | — |
| B199 | 严格独立 | special_function(scipy.special.voigt_profile 机器精度, sinh 换元 + 复合 Simpson n=32) | 🚫 **零宿主** | — |
| B200 | 严格独立 | special_function(scipy.special.voigt_profile 机器精度, sinh 换元 + 复合 Simpson n=64) | 🚫 **零宿主** | — |
| B201 | 严格独立 | closed_form(∫₀¹ x^{−p}dx = 1/(1−p) 初等闭式, Gauss–Legendre n=256 节点高斯求积) | 🚫 **零宿主** | — |
| B202 | 严格独立 | closed_form(∫₀^∞ e^{−x}x^q dx = Γ(q+1) 闭式, Gauss–Laguerre n=64 节点高斯求积) | 🚫 **零宿主** | — |
| B203 | 严格独立 | closed_form(∫_{−∞}^{∞} e^{−x²}|x|^p dx = Γ((p+1)/2) 闭式, Gauss–Hermite n=128 节点高斯求积) | 🚫 **零宿主** | — |
| B204 | 严格独立 | closed_form(∫_{−1}¹ dx/((1+ax)√(1−x²)) = π/√(1−a²) 闭式, Gauss–Chebyshev 第一类 n=12 节点高斯求积) | 🚫 **零宿主** | — |
| B205 | 严格独立 | closed_form(tan x 初等超越闭式, Lambert 连分数 N=4 层截断) | 🚫 **零宿主** | — |
| B206 | 严格独立 | closed_form(arctan x 初等闭式, Euler 连分数 N=6 层截断) | 🚫 **零宿主** | — |
| B207 | 严格独立 | closed_form(coth x 初等闭式, 双曲连分数 N=3 层截断) | 🚫 **零宿主** | — |
| B208 | 严格独立 | closed_form(√(1+x) 初等闭式, 平方根连分数 N=6 层截断) | 🚫 **零宿主** | — |
| B209 | 严格独立 | closed_form(xⁿ−a=0 的实根 a^{1/n} 闭式, Durand–Kerner 同时迭代 m=8 步) | 🚫 **零宿主** | — |
| B210 | 严格独立 | closed_form(x⁴−a=0 实根 a^{1/4} 闭式, Durand–Kerner 同时迭代 m=8 步) | 🚫 **零宿主** | — |
| B211 | 严格独立 | closed_form(x⁵−a=0 实根 a^{1/5} 闭式, Durand–Kerner 同时迭代 m=17 步) | 🚫 **零宿主** | — |
| B212 | 严格独立 | closed_form(x⁶−a=0 实根 a^{1/6} 闭式, Durand–Kerner 同时迭代 m=16 步) | 🚫 **零宿主** | — |
| B213 | 严格独立 | closed_form(arcsin(z)/z 初等闭式, ₂F₁ Euler 积分表示 + Gauss–Jacobi 求积 n=6) | 🚫 **零宿主** | — |
| B214 | 严格独立 | closed_form(arctanh(z)/z 初等闭式, ₂F₁ Euler 积分表示 + Gauss–Jacobi 求积 n=6) | 🚫 **零宿主** | — |
| B215 | 严格独立 | closed_form(arctan(z)/z 初等闭式, ₂F₁ Euler 积分表示 + Gauss–Jacobi 求积 n=2) | 🚫 **零宿主** | — |
| B216 | 严格独立 | closed_form(arcsinh(z)/z 初等闭式, ₂F₁ Euler 积分表示 + Gauss–Jacobi 求积 n=4) | 🚫 **零宿主** | — |
| B217 | 严格独立 | closed_form(Riemann–Liouville 初等闭式 t^{−α}/Γ(1−α), GL 卷积差分 n=3200) | 🚫 **零宿主** | — |
| B218 | 严格独立 | closed_form(初等闭式 Γ(2)/Γ(2−α)·t^{1−α}, GL 卷积差分 n=3200) | 🚫 **零宿主** | — |
| B219 | 严格独立 | closed_form(初等闭式 Γ(4)/Γ(4−α)·t^{3−α}, GL 卷积差分 n=3200) | 🚫 **零宿主** | — |
| B220 | 严格独立 | closed_form(初等闭式 Γ(3)/Γ(3−α)·t^{2−α}, GL 卷积差分 n=3200) | 🚫 **零宿主** | — |
| B221 | 严格独立 | closed_form(线性系统状态转移矩阵初等闭式 −sin t, scaling–squaring s=8 + 截断 Taylor n=3) | 🚫 **零宿主** | — |
| B222 | 严格独立 | closed_form(初等闭式 −sin(2.5t), scaling–squaring s=8 + 截断 Taylor n=3) | 🚫 **零宿主** | — |
| B223 | 严格独立 | closed_form(初等闭式 e^{−t}, scaling–squaring s=8 + 截断 Taylor n=3) | 🚫 **零宿主** | — |
| B224 | 严格独立 | closed_form(初等闭式 2e^{−t}−e^{−2t}, scaling–squaring s=8 + 截断 Taylor n=3) | 🚫 **零宿主** | — |
| B225 | 严格独立 | closed_form(解析极小值 −a/4, 固定步长梯度下降 k=12) | 🚫 **零宿主** | — |
| B226 | 严格独立 | closed_form(解析极小值 2√a, 固定步长梯度下降 k=12) | 🚫 **零宿主** | — |
| B227 | 严格独立 | closed_form(解析极小值 −e^{b−1}, 固定步长梯度下降 k=12) | 🚫 **零宿主** | — |
| B228 | 严格独立 | closed_form(解析极小值 c−c·ln c, 固定步长梯度下降 k=12) | 🚫 **零宿主** | — |
| B229 | 严格独立 | closed_form(积分方程解析解 [1−λe^{−(1−λ)x}]/(1−λ), 分块梯形递推 n=1024) | 🚫 **零宿主** | — |
| B230 | 严格独立 | closed_form(积分方程解析解 [1−λe^{−1.5(1−λ)}]/(1−λ), 分块梯形递推 n=1024) | 🚫 **零宿主** | — |
| B231 | 严格独立 | closed_form(积分方程解析解 [2−λe^{−(2−λ)x}]/(2−λ), 分块梯形递推 n=1024) | 🚫 **零宿主** | — |
| B232 | 严格独立 | closed_form(积分方程解析解 cosh(√λ x), 分块梯形递推 n=1024) | 🚫 **零宿主** | — |
| B233 | 严格独立 | closed_form(θ(x)=(e^{Pe·x}−1)/(e^{Pe}−1), Pe=u/ε, 三点中心差分+Thomas 追赶法 n=640) | 🚫 **零宿主** | — |
| B234 | 严格独立 | closed_form(θ(x)=(e^{Pe·x}−1)/(e^{Pe}−1), Pe=u/ε, 三点中心差分+Thomas 追赶法 n=640) | 🚫 **零宿主** | — |
| B235 | 严格独立 | closed_form(θ(x)=(e^{Pe·x}−1)/(e^{Pe}−1), Pe=u/ε, 三点中心差分+Thomas 追赶法 n=640) | 🚫 **零宿主** | — |
| B236 | 严格独立 | closed_form(θ(x)=(e^{Pe·x}−1)/(e^{Pe}−1), Pe=u/ε, 三点中心差分+Thomas 追赶法 n=640) | 🚫 **零宿主** | — |
| B237 | 严格独立 | closed_form(resolvent 精确线性代数 c=(I−λA)^{−1}d, 均匀节点梯形权重 Nyström n=512) | 🚫 **零宿主** | — |
| B238 | 严格独立 | closed_form(resolvent 精确线性代数 c=(I−λA)^{−1}d, 均匀节点梯形权重 Nyström n=512) | 🚫 **零宿主** | — |
| B239 | 严格独立 | closed_form(resolvent 精确线性代数 c=(I−λA)^{−1}d, 均匀节点梯形权重 Nyström n=512) | 🚫 **零宿主** | — |
| B240 | 严格独立 | closed_form(resolvent 精确线性代数 c=(I−λA)^{−1}d, 均匀节点梯形权重 Nyström n=512) | 🚫 **零宿主** | — |
| B241 | 严格独立 | closed_form(初等闭式精确值, 均匀节点自然三次样条 n=64) | 🚫 **零宿主** | — |
| B242 | 严格独立 | closed_form(初等闭式精确值, 均匀节点自然三次样条 n=64) | 🚫 **零宿主** | — |
| B243 | 严格独立 | closed_form(初等闭式精确值, 均匀节点自然三次样条 n=64) | 🚫 **零宿主** | — |
| B244 | 严格独立 | closed_form(初等闭式精确值, 均匀节点自然三次样条 n=64) | 🚫 **零宿主** | — |
| B245 | 严格独立 | closed_form(y=(1+βx)^{−2}, RK4 打靶 + 割线/二分 n=32) | 🚫 **零宿主** | — |
| B246 | 严格独立 | closed_form(y=(1+βx)^{−1}, RK4 打靶 + 割线/二分 n=32) | 🚫 **零宿主** | — |
| B247 | 严格独立 | closed_form(y=√c·tan(√c·x), RK4 打靶 + 割线/二分 n=32) | 🚫 **零宿主** | — |
| B248 | 严格独立 | closed_form(y=ln(1+x(e^{y1}−1)), RK4 打靶 + 割线/二分 n=32) | 🚫 **零宿主** | — |
| B249 | 严格独立 | closed_form(y=e^{−rT}, 分步法 + 三次 Hermite 历史插值 n=64) | 🚫 **零宿主** | — |
| B250 | 严格独立 | closed_form(y=e^{−rT}, 分步法 + 三次 Hermite 历史插值 n=64) | 🚫 **零宿主** | — |
| B251 | 严格独立 | closed_form(y=e^{−rT}, 分步法 + 三次 Hermite 历史插值 n=64) | 🚫 **零宿主** | — |
| B252 | 严格独立 | closed_form(y=e^{−rT}, 分步法 + 三次 Hermite 历史插值 n=64) | 🚫 **零宿主** | — |
| B253 | 严格独立 | closed_form(w=q0/(4π⁴D), 13 点双调和差分 n=256) | 🚫 **零宿主** | — |
| B254 | 严格独立 | closed_form(w=q0/(4π⁴D), 13 点双调和差分 n=256) | 🚫 **零宿主** | — |
| B255 | 严格独立 | closed_form(w=q0/(4π⁴D), 13 点双调和差分 n=256) | 🚫 **零宿主** | — |
| B256 | 严格独立 | closed_form(w=q0/(4π⁴D), 13 点双调和差分 n=256) | 🚫 **零宿主** | — |
| B257 | 严格独立 | closed_form(u=u0(x−ct), 半拉格朗日特征线 + 4 点立方 Lagrange n=320) | 🚫 **零宿主** | — |
| B258 | 严格独立 | closed_form(u=u0(x−ct), 半拉格朗日特征线 + 4 点立方 Lagrange n=320) | 🚫 **零宿主** | — |
| B259 | 严格独立 | closed_form(u=u0(x−ct), 半拉格朗日特征线 + 4 点立方 Lagrange n=320) | 🚫 **零宿主** | — |
| B260 | 严格独立 | closed_form(u=u0(x−ct), 半拉格朗日特征线 + 4 点立方 Lagrange n=320) | 🚫 **零宿主** | — |
| B261 | 严格独立 | closed_form(Re u=A·sech(A(x−x0))·cos(A²T), 分裂步 Fourier Strang n=2048) | 🚫 **零宿主** | — |
| B262 | 严格独立 | closed_form(Re u=A·sech(A(x−x0))·cos(A²T), 分裂步 Fourier Strang n=2048) | 🚫 **零宿主** | — |
| B263 | 严格独立 | closed_form(Re u=A·sech(A(x−x0))·cos(A²T), 分裂步 Fourier Strang n=2048) | 🚫 **零宿主** | — |
| B264 | 严格独立 | closed_form(Re u=A·sech(A(x−x0))·cos(A²T), 分裂步 Fourier Strang n=2048) | 🚫 **零宿主** | — |
| B265 | 严格独立 | closed_form(u=c·[1−tanh(c·ξ/2ν)], ξ=0.5; RK4 + 二阶中心差分 n=1600) | 🚫 **零宿主** | — |
| B266 | 严格独立 | closed_form(u=c·[1−tanh(c·ξ/2ν)], ξ=0.5; RK4 + 二阶中心差分 n=1600) | 🚫 **零宿主** | — |
| B267 | 严格独立 | closed_form(u=c·[1−tanh(c·ξ/2ν)], ξ=0.5; RK4 + 二阶中心差分 n=1600) | 🚫 **零宿主** | — |
| B268 | 严格独立 | closed_form(u=c·[1−tanh(c·ξ/2ν)], ξ=0.5; RK4 + 二阶中心差分 n=1600) | 🚫 **零宿主** | — |
| B269 | 严格独立 | closed_form(u=c·[1−tanh(c·ξ/2ν)], ξ=0.5; RK4 + 二阶中心差分 n=1600) | 🚫 **零宿主** | — |
| B270 | 严格独立 | closed_form(u=c·[1−tanh(c·ξ/2ν)], ξ=0.5; RK4 + 二阶中心差分 n=1600) | 🚫 **零宿主** | — |
| B271 | 严格独立 | scipy.special.exp1/expn(x); 截断 [1,60] + 复合 Simpson（2N+1 节点, N=80） | 🚫 **零宿主** | — |
| B272 | 严格独立 | scipy.special.exp1/expn(x); 截断 [1,60] + 复合 Simpson（2N+1 节点, N=80） | 🚫 **零宿主** | — |
| B273 | 严格独立 | scipy.special.exp1/expn(x); 截断 [1,60] + 复合 Simpson（2N+1 节点, N=80） | 🚫 **零宿主** | — |
| B274 | 严格独立 | scipy.special.exp1/expn(x); 截断 [1,60] + 复合 Simpson（2N+1 节点, N=80） | 🚫 **零宿主** | — |
| B275 | 严格独立 | scipy.special.exp1/expn(x); 截断 [1,60] + 复合 Simpson（2N+1 节点, N=80） | 🚫 **零宿主** | — |
| B276 | 严格独立 | closed_form((b^{p+1}−a^{p+1})/((p+1)·h), 2^K 采样逐层 Haar 低通 K=13) | 🚫 **零宿主** | — |
| B277 | 严格独立 | closed_form((b^{p+1}−a^{p+1})/((p+1)·h), 2^K 采样逐层 Haar 低通 K=13) | 🚫 **零宿主** | — |
| B278 | 严格独立 | closed_form((b^{p+1}−a^{p+1})/((p+1)·h), 2^K 采样逐层 Haar 低通 K=13) | 🚫 **零宿主** | — |
| B279 | 严格独立 | closed_form((b^{p+1}−a^{p+1})/((p+1)·h), 2^K 采样逐层 Haar 低通 K=13) | 🚫 **零宿主** | — |
| B280 | 严格独立 | closed_form((b^{p+1}−a^{p+1})/((p+1)·h), 2^K 采样逐层 Haar 低通 K=13) | 🚫 **零宿主** | — |
| B281 | 严格独立 | closed_form((y0−C)e^{−aT}+C·cos ωT+D·sin ωT, C=ab/(a²+ω²), D=bω/(a²+ω²); ETD2 线性部分精确 + forcing 段内线性插值 n=1600) | 🚫 **零宿主** | — |
| B282 | 严格独立 | closed_form((y0−C)e^{−aT}+C·cos ωT+D·sin ωT, C=ab/(a²+ω²), D=bω/(a²+ω²); ETD2 线性部分精确 + forcing 段内线性插值 n=1600) | 🚫 **零宿主** | — |
| B283 | 严格独立 | closed_form((y0−C)e^{−aT}+C·cos ωT+D·sin ωT, C=ab/(a²+ω²), D=bω/(a²+ω²); ETD2 线性部分精确 + forcing 段内线性插值 n=1600) | 🚫 **零宿主** | — |
| B284 | 严格独立 | closed_form((y0−C)e^{−aT}+C·cos ωT+D·sin ωT, C=ab/(a²+ω²), D=bω/(a²+ω²); ETD2 线性部分精确 + forcing 段内线性插值 n=1600) | 🚫 **零宿主** | — |
| B285 | 严格独立 | closed_form((y0−C)e^{−aT}+C·cos ωT+D·sin ωT, C=ab/(a²+ω²), D=bω/(a²+ω²); ETD2 线性部分精确 + forcing 段内线性插值 n=1600) | 🚫 **零宿主** | — |
| B286 | 严格独立 | closed_form((y0−C)e^{−aT}+C·cos ωT+D·sin ωT, C=ab/(a²+ω²), D=bω/(a²+ω²); ETD2 线性部分精确 + forcing 段内线性插值 n=1600) | 🚫 **零宿主** | — |
| B287 | 严格独立 | closed_form(Parseval sqrt(a1²+a2²); 极坐标均匀中点求积 Nr=160, Nth=max(2Nr,64)) | 🚫 **零宿主** | — |
| B288 | 严格独立 | closed_form(Parseval sqrt(a1²+a2²); 极坐标均匀中点求积 Nr=160, Nth=max(2Nr,64)) | 🚫 **零宿主** | — |
| B289 | 严格独立 | closed_form(Parseval sqrt(a1²+a2²); 极坐标均匀中点求积 Nr=160, Nth=max(2Nr,64)) | 🚫 **零宿主** | — |
| B290 | 严格独立 | closed_form(Parseval sqrt(a1²+a2²); 极坐标均匀中点求积 Nr=160, Nth=max(2Nr,64)) | 🚫 **零宿主** | — |
| B291 | 严格独立 | closed_form(Parseval sqrt(a1²+a2²); 极坐标均匀中点求积 Nr=160, Nth=max(2Nr,64)) | 🚫 **零宿主** | — |
| B292 | 严格独立 | closed_form(A·cn(ω·t*, m), ω²=a+βA², m=βA²/(2ω²); Yoshida 四阶组合辛积分 S₂(z₁h)S₂(z₀h)S₂(z₁h) n=64) | 🚫 **零宿主** | — |
| B293 | 严格独立 | closed_form(A·cn(ω·t*, m), ω²=a+βA², m=βA²/(2ω²); Yoshida 四阶组合辛积分 S₂(z₁h)S₂(z₀h)S₂(z₁h) n=64) | 🚫 **零宿主** | — |
| B294 | 严格独立 | closed_form(A·cn(ω·t*, m), ω²=a+βA², m=βA²/(2ω²); Yoshida 四阶组合辛积分 S₂(z₁h)S₂(z₀h)S₂(z₁h) n=64) | 🚫 **零宿主** | — |
| B295 | 严格独立 | closed_form(A·cn(ω·t*, m), ω²=a+βA², m=βA²/(2ω²); Yoshida 四阶组合辛积分 S₂(z₁h)S₂(z₀h)S₂(z₁h) n=64) | 🚫 **零宿主** | — |
| B296 | 严格独立 | closed_form(A·cn(ω·t*, m), ω²=a+βA², m=βA²/(2ω²); Yoshida 四阶组合辛积分 S₂(z₁h)S₂(z₀h)S₂(z₁h) n=64) | 🚫 **零宿主** | — |
| B297 | 严格独立 | closed_form(Re[(e^{a+iω}−1)/(a+iω)]); Filon 型分段二次求积（段内解析 cos 核）N=128 | 🚫 **零宿主** | — |
| B298 | 严格独立 | closed_form(Re[(e^{a+iω}−1)/(a+iω)]); Filon 型分段二次求积（段内解析 cos 核）N=128 | 🚫 **零宿主** | — |
| B299 | 严格独立 | closed_form(Re[(e^{a+iω}−1)/(a+iω)]); Filon 型分段二次求积（段内解析 cos 核）N=128 | 🚫 **零宿主** | — |
| B300 | 严格独立 | closed_form(Re[(e^{a+iω}−1)/(a+iω)]); Filon 型分段二次求积（段内解析 cos 核）N=128 | 🚫 **零宿主** | — |
| B301 | 严格独立 | closed_form(Re[(e^{a+iω}−1)/(a+iω)]); Filon 型分段二次求积（段内解析 cos 核）N=128 | 🚫 **零宿主** | — |
| B302 | 严格独立 | closed_form(Re[(e^{a+iω}−1)/(a+iω)]); Filon 型分段二次求积（段内解析 cos 核）N=128 | 🚫 **零宿主** | — |
| B303 | 严格独立 | closed_form(ln(e^{y0}−aT)); Gauss–Legendre 2 级隐式 RK4（A-稳定 + Newton 解析雅可比）n=32 | 🚫 **零宿主** | — |
| B304 | 严格独立 | closed_form(ln(e^{y0}−aT)); Gauss–Legendre 2 级隐式 RK4（A-稳定 + Newton 解析雅可比）n=32 | 🚫 **零宿主** | — |
| B305 | 严格独立 | closed_form(ln(e^{y0}−aT)); Gauss–Legendre 2 级隐式 RK4（A-稳定 + Newton 解析雅可比）n=32 | 🚫 **零宿主** | — |
| B306 | 严格独立 | closed_form(ln(e^{y0}−aT)); Gauss–Legendre 2 级隐式 RK4（A-稳定 + Newton 解析雅可比）n=32 | 🚫 **零宿主** | — |
| B307 | 严格独立 | closed_form(ln(e^{y0}−aT)); Gauss–Legendre 2 级隐式 RK4（A-稳定 + Newton 解析雅可比）n=32 | 🚫 **零宿主** | — |
| B308 | 严格独立 | closed_form(2·arctan(tan(y0/2)·e^{−aT})); Adams–Bashforth 4 阶线性多步（RK4 同阶启动）n=256 | 🚫 **零宿主** | — |
| B309 | 严格独立 | closed_form(2·arctan(tan(y0/2)·e^{−aT})); Adams–Bashforth 4 阶线性多步（RK4 同阶启动）n=256 | 🚫 **零宿主** | — |
| B310 | 严格独立 | closed_form(2·arctan(tan(y0/2)·e^{−aT})); Adams–Bashforth 4 阶线性多步（RK4 同阶启动）n=256 | 🚫 **零宿主** | — |
| B311 | 严格独立 | closed_form(2·arctan(tan(y0/2)·e^{−aT})); Adams–Bashforth 4 阶线性多步（RK4 同阶启动）n=256 | 🚫 **零宿主** | — |
| B312 | 严格独立 | closed_form(2·arctan(tan(y0/2)·e^{−aT})); Adams–Bashforth 4 阶线性多步（RK4 同阶启动）n=256 | 🚫 **零宿主** | — |
| B313 | 严格独立 | closed_form(θ₀·sin(√λξ)/(√λξ)); 原点 Taylor 级数启动 + 经典 RK4（一阶化 y=θ,p=θ'）N=128 | 🚫 **零宿主** | — |
| B314 | 严格独立 | closed_form(θ₀·sin(√λξ)/(√λξ)); 原点 Taylor 级数启动 + 经典 RK4（一阶化 y=θ,p=θ'）N=128 | 🚫 **零宿主** | — |
| B315 | 严格独立 | closed_form(θ₀·(1+λθ₀⁴ξ²/3)^(−1/2)); 原点 Taylor 级数启动 + 经典 RK4（一阶化 y=θ,p=θ'）N=128 | 🚫 **零宿主** | — |
| B316 | 严格独立 | closed_form(θ₀·(1+λθ₀⁴ξ²/3)^(−1/2)); 原点 Taylor 级数启动 + 经典 RK4（一阶化 y=θ,p=θ'）N=128 | 🚫 **零宿主** | — |
| B317 | 严格独立 | closed_form(θ₀·(1+λθ₀⁴ξ²/3)^(−1/2)); 原点 Taylor 级数启动 + 经典 RK4（一阶化 y=θ,p=θ'）N=128 | 🚫 **零宿主** | — |
| B318 | 严格独立 | closed_form(θ₀·(1+λθ₀⁴ξ²/3)^(−1/2)); 原点 Taylor 级数启动 + 经典 RK4（一阶化 y=θ,p=θ'）N=128 | 🚫 **零宿主** | — |
| B319 | 严格独立 | closed_form(r^n·cos(nθ)); 间接单层位势边界元（N 段常数元 + 12 点 Gauss–Legendre）N=256 | 🚫 **零宿主** | — |
| B320 | 严格独立 | closed_form(r^n·cos(nθ)); 间接单层位势边界元（N 段常数元 + 12 点 Gauss–Legendre）N=256 | 🚫 **零宿主** | — |
| B321 | 严格独立 | closed_form(r^n·cos(nθ)); 间接单层位势边界元（N 段常数元 + 12 点 Gauss–Legendre）N=256 | 🚫 **零宿主** | — |
| B322 | 严格独立 | closed_form(r^n·cos(nθ)); 间接单层位势边界元（N 段常数元 + 12 点 Gauss–Legendre）N=256 | 🚫 **零宿主** | — |
| B323 | 严格独立 | closed_form(r^n·cos(nθ)); 间接单层位势边界元（N 段常数元 + 12 点 Gauss–Legendre）N=256 | 🚫 **零宿主** | — |
| B324 | 严格独立 | closed_form(f0·(x+y+y²/2)) 制造解；快速行进法 FMM（Godunov 一阶迎风 + 二叉堆）M=640 | 🚫 **零宿主** | — |
| B325 | 严格独立 | closed_form(f0·(x+y+y²/2)) 制造解；快速行进法 FMM（Godunov 一阶迎风 + 二叉堆）M=640 | 🚫 **零宿主** | — |
| B326 | 严格独立 | closed_form(f0·(x+y+y²/2)) 制造解；快速行进法 FMM（Godunov 一阶迎风 + 二叉堆）M=640 | 🚫 **零宿主** | — |
| B327 | 严格独立 | closed_form(f0·(x+y+y²/2)) 制造解；快速行进法 FMM（Godunov 一阶迎风 + 二叉堆）M=640 | 🚫 **零宿主** | — |
| B328 | 严格独立 | closed_form(f0·(x+y+y²/2)) 制造解；快速行进法 FMM（Godunov 一阶迎风 + 二叉堆）M=640 | 🚫 **零宿主** | — |
| B329 | 严格独立 | scipy.special.iv(ν,x) 精确特殊函数 oracle；修正 Bessel ODE x²y''+xy'-(x²+ν²)y=0 原点 Frobenius 启动 + 经典四阶 RK4 N=128 | 🚫 **零宿主** | — |
| B330 | 严格独立 | scipy.special.iv(ν,x) 精确特殊函数 oracle；修正 Bessel ODE 原点 Frobenius 启动 + 经典四阶 RK4 N=128 | 🚫 **零宿主** | — |
| B331 | 严格独立 | scipy.special.iv(ν,x) 精确特殊函数 oracle；修正 Bessel ODE 原点 Frobenius 启动 + 经典四阶 RK4 N=128 | 🚫 **零宿主** | — |
| B332 | 严格独立 | scipy.special.iv(ν,x) 精确特殊函数 oracle；修正 Bessel ODE 原点 Frobenius 启动 + 经典四阶 RK4 N=128 | 🚫 **零宿主** | — |
| B333 | 严格独立 | scipy.special.iv(ν,x) 精确特殊函数 oracle；修正 Bessel ODE 原点 Frobenius 启动 + 经典四阶 RK4 N=128 | 🚫 **零宿主** | — |
| B334 | 严格独立 | scipy.special.iv(ν,x) 精确特殊函数 oracle；修正 Bessel ODE 原点 Frobenius 启动 + 经典四阶 RK4 N=128 | 🚫 **零宿主** | — |
| B335 | 严格独立 | 正交归一恒等式 = 1（精确）；均匀网格（θ×φ）复合梯形球面积分 N=160 | 🚫 **零宿主** | — |
| B336 | 严格独立 | 正交归一恒等式 = 1（精确）；均匀网格（θ×φ）复合梯形球面积分 N=160 | 🚫 **零宿主** | — |
| B337 | 严格独立 | 正交归一恒等式 = 1（精确）；均匀网格（θ×φ）复合梯形球面积分 N=160 | 🚫 **零宿主** | — |
| B338 | 严格独立 | 正交归一恒等式 = 1（精确）；均匀网格（θ×φ）复合梯形球面积分 N=160 | 🚫 **零宿主** | — |
| B339 | 严格独立 | 正交归一恒等式 = 1（精确）；均匀网格（θ×φ）复合梯形球面积分 N=160 | 🚫 **零宿主** | — |
| B340 | 严格独立 | closed_form(sin(a·π·x/2)·(1+x/2))；一维 N 中心均匀网格 + MQ RBF（c=0.5h）二次多项式 N=256 | 🚫 **零宿主** | — |
| B341 | 严格独立 | closed_form(sin(a·π·x/2)·(1+x/2))；一维 N 中心均匀网格 + MQ RBF（c=0.5h）二次多项式 N=256 | 🚫 **零宿主** | — |
| B342 | 严格独立 | closed_form(sin(a·π·x/2)·(1+x/2))；一维 N 中心均匀网格 + MQ RBF（c=0.5h）二次多项式 N=256 | 🚫 **零宿主** | — |
| B343 | 严格独立 | closed_form(sin(a·π·x/2)·(1+x/2))；一维 N 中心均匀网格 + MQ RBF（c=0.5h）二次多项式 N=256 | 🚫 **零宿主** | — |
| B344 | 严格独立 | closed_form(sin(a·π·x/2)·(1+x/2))；一维 N 中心均匀网格 + MQ RBF（c=0.5h）二次多项式 N=256 | 🚫 **零宿主** | — |
| B345 | 严格独立 | closed_form(H_n(x)=numpy.polynomial.hermite.hermval(x,[0]*n+[1]))；n 阶中心差分 Rodrigues 导数 N=512 | 🚫 **零宿主** | — |
| B346 | 严格独立 | closed_form(H_n(x)=numpy.polynomial.hermite.hermval(x,[0]*n+[1]))；n 阶中心差分 Rodrigues 导数 N=512 | 🚫 **零宿主** | — |
| B347 | 严格独立 | closed_form(H_n(x)=numpy.polynomial.hermite.hermval(x,[0]*n+[1]))；n 阶中心差分 Rodrigues 导数 N=512 | 🚫 **零宿主** | — |
| B348 | 严格独立 | closed_form(H_n(x)=numpy.polynomial.hermite.hermval(x,[0]*n+[1]))；n 阶中心差分 Rodrigues 导数 N=512 | 🚫 **零宿主** | — |
| B349 | 严格独立 | closed_form(H_n(x)=numpy.polynomial.hermite.hermval(x,[0]*n+[1]))；n 阶中心差分 Rodrigues 导数 N=512 | 🚫 **零宿主** | — |
| B350 | 严格独立 | closed_form(L_n(x)=scipy.special.genlaguerre(n,0)(x))；n 阶中心差分 Rodrigues 导数 N=512 | 🚫 **零宿主** | — |
| B351 | 严格独立 | closed_form(L_n(x)=scipy.special.genlaguerre(n,0)(x))；n 阶中心差分 Rodrigues 导数 N=512 | 🚫 **零宿主** | — |
| B352 | 严格独立 | closed_form(L_n(x)=scipy.special.genlaguerre(n,0)(x))；n 阶中心差分 Rodrigues 导数 N=512 | 🚫 **零宿主** | — |
| B353 | 严格独立 | closed_form(L_n(x)=scipy.special.genlaguerre(n,0)(x))；n 阶中心差分 Rodrigues 导数 N=512 | 🚫 **零宿主** | — |
| B354 | 严格独立 | closed_form(L_n(x)=scipy.special.genlaguerre(n,0)(x))；n 阶中心差分 Rodrigues 导数 N=512 | 🚫 **零宿主** | — |
| B355 | 严格独立 | closed_form(f(t)=sin(2πt))；degree-N Bernstein 基求和 N=512 | 🚫 **零宿主** | — |
| B356 | 严格独立 | closed_form(f(t)=cos(2πt))；degree-N Bernstein 基求和 N=512 | 🚫 **零宿主** | — |
| B357 | 严格独立 | closed_form(f(t)=exp(t)-1)；degree-N Bernstein 基求和 N=512 | 🚫 **零宿主** | — |
| B358 | 严格独立 | closed_form(f(t)=1/(1+t))；degree-N Bernstein 基求和 N=512 | 🚫 **零宿主** | — |
| B359 | 严格独立 | closed_form(f(t)=1/(1+2t))；degree-N Bernstein 基求和 N=512 | 🚫 **零宿主** | — |
| B360 | 严格独立 | closed_form(f(t)=sqrt(t+0.1))；degree-N Bernstein 基求和 N=512 | 🚫 **零宿主** | — |
| B361 | 严格独立 | analytical(Snyder/Marcatili empirical b(V)=(1.1428-0.996/V)² → n_eff) + cylindrical radial weighted-general-eigen FD independent_cross_check | 🚫 **零宿主** | — |
| B362 | 严格独立 | analytical(Snyder/Marcatili empirical b(V)=(1.1428-0.996/V)² → n_eff) + cylindrical radial weighted-general-eigen FD independent_cross_check | 🚫 **零宿主** | — |
| B363 | 严格独立 | analytical(Snyder/Marcatili empirical b(V)=(1.1428-0.996/V)² → n_eff) + cylindrical radial weighted-general-eigen FD independent_cross_check | 🚫 **零宿主** | — |
| B364 | 严格独立 | analytical(Snyder/Marcatili empirical b(V)=(1.1428-0.996/V)² → n_eff) + cylindrical radial weighted-general-eigen FD independent_cross_check | 🚫 **零宿主** | — |
| B365 | 严格独立 | analytical(Snyder/Marcatili empirical b(V)=(1.1428-0.996/V)² → n_eff) + cylindrical radial weighted-general-eigen FD independent_cross_check | 🚫 **零宿主** | — |
| B366 | 严格独立 | analytical(Snyder/Marcatili empirical b(V)=(1.1428-0.996/V)² → n_eff) + cylindrical radial weighted-general-eigen FD independent_cross_check | 🚫 **零宿主** | — |
| B367 | 严格独立 | analytical(Snyder/Marcatili empirical b(V)=(1.1428-0.996/V)² → n_eff) + cylindrical radial weighted-general-eigen FD independent_cross_check | 🚫 **零宿主** | — |
| B368 | 严格独立 | analytical(Snyder/Marcatili empirical b(V)=(1.1428-0.996/V)² → n_eff) + cylindrical radial weighted-general-eigen FD independent_cross_check | 🚫 **零宿主** | — |
| B369 | 严格独立 | analytical(J0 first zero 2.4048255577) + cylindrical radial weighted-general-eigen FD mode-appearance-threshold independent_cross_check | 🚫 **零宿主** | — |
| B370 | 严格独立 | analytical(SiO₂ Sellmeier group index n_g=n−λ·dn/dλ, Malitson 1965) + cylindrical radial FD λ-scan finite-difference independent_cross_check | 🚫 **零宿主** | — |
| B371 | 严格独立 | analytical(SiO₂ Sellmeier group index n_g=n−λ·dn/dλ, Malitson 1965) + cylindrical radial FD λ-scan finite-difference independent_cross_check | 🚫 **零宿主** | — |
| B372 | 严格独立 | analytical(SiO₂ Sellmeier β₂=d²β/dω², ω-space, ps²/km) + cylindrical radial FD ω-space 2nd-difference independent_cross_check | 🚫 **零宿主** | — |
| B373 | 严格独立 | analytical(SiO₂ Sellmeier β₂=d²β/dω², ω-space, ps²/km) + cylindrical radial FD ω-space 2nd-difference independent_cross_check | 🚫 **零宿主** | — |
| B374 | 严格独立 | analytical(zR=π w0²/λ) + paraxial BPM(Crank-Nicolson FD) independent_cross_check | 🚫 **零宿主** | — |
| B375 | 严格独立 | analytical(w(z)=w0√(1+(z/zR)²)) + paraxial BPM independent_cross_check | 🚫 **零宿主** | — |
| B376 | 严格独立 | analytical(b=2π w0²/λ) + paraxial BPM independent_cross_check | 🚫 **零宿主** | — |
| B377 | 严格独立 | analytical(θ=λ/(π w0)) + paraxial BPM far-field slope independent_cross_check | 🚫 **零宿主** | — |
| B378 | 严格独立 | analytical(ABCD q-transform waist) + paraxial BPM lens propagation independent_cross_check | 🚫 **零宿主** | — |
| B379 | 严格独立 | analytical(ABCD q-transform Rayleigh range) + paraxial BPM independent_cross_check | 🚫 **零宿主** | — |
| B380 | 严格独立 | analytical(ABCD q-transform waist location) + paraxial BPM independent_cross_check | 🚫 **零宿主** | — |
| B381 | 严格独立 | analytical(Gouy 1D: ½[arctan(z2/zR)−arctan(z1/zR)]) + paraxial BPM phase independent_cross_check | 🚫 **零宿主** | — |
| B382 | 严格独立 | analytical(w(z)=w0√(1+(z/zR)²)) + paraxial BPM independent_cross_check | 🚫 **零宿主** | — |
| B383 | 严格独立 | analytical(θ=λ/(π w0), green λ=0.6328µm) + paraxial BPM far-field asymptotic independent_cross_check | 🚫 **零宿主** | — |
| B384 | 严格独立 | analytical(w(z)=w0√(1+(z/zR)²)) + paraxial BPM independent_cross_check | 🚫 **零宿主** | — |
| B385 | 严格独立 | analytical(w(z)=w0√(1+(z/zR)²)) + paraxial BPM independent_cross_check | 🚫 **零宿主** | — |
| B386 | 严格独立 | analytical(ABCD q-transform waist) + paraxial BPM lens propagation independent_cross_check | 🚫 **零宿主** | — |
| B387 | 严格独立 | analytical(sinθ₁=λ/a) + Fraunhofer 1D Simpson quadrature independent_cross_check | 🚫 **零宿主** | — |
| B388 | 严格独立 | analytical(sinc²) + Fraunhofer 1D Simpson quadrature independent_cross_check | 🚫 **零宿主** | — |
| B389 | 严格独立 | analytical(J₁ first zero /π) + Fraunhofer disk 2D polar Simpson quadrature independent_cross_check | 🚫 **零宿主** | — |
| B390 | 严格独立 | analytical([2J₁(x)/x]²) + Fraunhofer disk 2D polar Simpson quadrature independent_cross_check | 🚫 **零宿主** | — |
| B391 | 严格独立 | analytical(cos²·sinc²) + Fraunhofer double-slit 1D Simpson quadrature independent_cross_check | 🚫 **零宿主** | — |
| B392 | 严格独立 | analytical(Δsinθ=λ/d) + pure-interference numerical peak-finding independent_cross_check | 🚫 **零宿主** | — |
| B393 | 严格独立 | analytical(d sinθ=mλ) + pure-interference numerical peak-finding independent_cross_check | 🚫 **零宿主** | — |
| B394 | 严格独立 | analytical(R=mN) + pure-interference numerical first-zero independent_cross_check | 🚫 **零宿主** | — |
| B395 | 严格独立 | analytical(separable sinc²) + Fraunhofer rect 2D Cartesian Simpson quadrature independent_cross_check | 🚫 **零宿主** | — |
| B396 | 严格独立 | analytical(Δθ=2λ/a) + Fraunhofer 1D Simpson first-zero independent_cross_check | 🚫 **零宿主** | — |
| B397 | 严格独立 | analytical(angular far-field encircled ratio) + Fraunhofer disk 2D polar Simpson quadrature independent_cross_check | 🚫 **零宿主** | — |
| B398 | 严格独立 | analytical(Δλ=λ/(mN)) + Fraunhofer grating 1D Simpson first-zero independent_cross_check | 🚫 **零宿主** | — |
| B399 | 严格独立 | analytical(1.220) + Fraunhofer disk/slit Simpson first-zero independent_cross_check | 🚫 **零宿主** | — |
| B400 | 严格独立 | analytical(2πσ(1−z/√)) + Coulomb ring Simpson 1D quadrature independent_cross_check | 🚫 **零宿主** | — |
| B401 | 严格独立 | analytical(2πσ(z/√a − z/√b)) + Coulomb ring Simpson 1D quadrature independent_cross_check | 🚫 **零宿主** | — |
| B402 | 严格独立 | analytical(λL/(a√(L/2)²+a²)) + Coulomb line Simpson 1D quadrature independent_cross_check | 🚫 **零宿主** | — |
| B403 | 严格独立 | analytical(λL/(a√(L²+a²))) + Coulomb line Simpson 1D quadrature independent_cross_check | 🚫 **零宿主** | — |
| B404 | 严格独立 | analytical(Q/(ρ²+z²) shell theorem) + Coulomb shell 2D Simpson quadrature independent_cross_check | 🚫 **零宿主** | — |
| B405 | 严格独立 | analytical(2λL/((d/2)√)) + Coulomb line superposition Simpson 1D quadrature independent_cross_check | 🚫 **零宿主** | — |
| B406 | 严格独立 | analytical(I L/(4π d√)) + Biot–Savart finite wire Simpson 1D quadrature independent_cross_check | 🚫 **零宿主** | — |
| B407 | 严格独立 | analytical(2√2 I/(π a)) + Biot–Savart 4-segment Simpson quadrature independent_cross_check | 🚫 **零宿主** | — |
| B408 | 严格独立 | analytical(I N tan(π/N)/(2π R)) + Biot–Savart N-segment Simpson quadrature independent_cross_check | 🚫 **零宿主** | — |
| B409 | 严格独立 | analytical(K,E elliptic) + Biot–Savart loop Simpson 1D quadrature independent_cross_check | 🚫 **零宿主** | — |
| B410 | 严格独立 | analytical((nI/2)(cosα₁−cosα₂)) + Biot–Savart stacked-loop Simpson 1D quadrature independent_cross_check | 🚫 **零宿主** | — |
| B411 | 严格独立 | analytical(I L/(π d√)) + Biot–Savart two-wire Simpson 1D quadrature independent_cross_check | 🚫 **零宿主** | — |
| B412 | 严格独立 | analytical(K,E elliptic) + Biot–Savart loop Simpson 1D quadrature independent_cross_check | 🚫 **零宿主** | — |
| B413 | 严格独立 | analytical(R0=((n1−n2)/(n1+n2))²) + 1D FD Helmholtz total-field independent_cross_check | 🚫 **零宿主** | — |
| B414 | 严格独立 | analytical(Rs Fresnel s) + 1D FD Helmholtz TE independent_cross_check | 🚫 **零宿主** | — |
| B415 | 严格独立 | analytical(Rp Fresnel p) + 1D FD Helmholtz TM independent_cross_check | 🚫 **零宿主** | — |
| B416 | 严格独立 | analytical(Ts=1−Rs) + 1D FD Helmholtz TE independent_cross_check | 🚫 **零宿主** | — |
| B417 | 严格独立 | analytical(Tp=1−Rp) + 1D FD Helmholtz TM independent_cross_check | 🚫 **零宿主** | — |
| B418 | 严格独立 | analytical(Runpol=(Rs+Rp)/2) + 1D FD Helmholtz TE/TM independent_cross_check | 🚫 **零宿主** | — |
| B419 | 严格独立 | analytical(ΔR=Rs−Rp) + 1D FD Helmholtz TE/TM independent_cross_check | 🚫 **零宿主** | — |
| B420 | 严格独立 | analytical(Ts/Tp) + 1D FD Helmholtz TE/TM independent_cross_check | 🚫 **零宿主** | — |
| B421 | 严格独立 | analytical(θB=atan(n2/n1)) + 1D FD Helmholtz p-reflectance min-scan independent_cross_check | 🚫 **零宿主** | — |
| B422 | 严格独立 | analytical(|t_s|=2n1cθi/(n1cθi+n2cθt)) + 1D FD Helmholtz TE independent_cross_check | 🚫 **零宿主** | — |
| B423 | 严格独立 | analytical(R=1 TIR) + 1D FD Helmholtz TIR independent_cross_check | 🚫 **零宿主** | — |
| B424 | 严格独立 | analytical(β=k0√(n1²sin²θi−n2²)) + 1D FD Helmholtz field exponential-fit independent_cross_check | 🚫 **零宿主** | — |
| B425 | 严格独立 | analytical(Rs+Ts·(n2cθt)/(n1cθi)=1) + 1D FD Helmholtz independent_cross_check | 🚫 **零宿主** | — |
| B426 | 严格独立 | analytical(v_p=1/√(1−(ωp/ω)²)) + central-difference numerical derivative independent_cross_check | 🚫 **零宿主** | — |
| B427 | 严格独立 | analytical(v_g=√(1−(ωp/ω)²)) + central-difference numerical derivative independent_cross_check | 🚫 **零宿主** | — |
| B428 | 严格独立 | analytical(n_g=1/√(1−(ωp/ω)²)) + central-difference numerical derivative independent_cross_check | 🚫 **零宿主** | — |
| B429 | 严格独立 | analytical(v_p=ω/k(ω)) + central-difference numerical derivative independent_cross_check | 🚫 **零宿主** | — |
| B430 | 严格独立 | analytical(β2=−(ωp/ω)²/[ω·(1−(ωp/ω)²)^{3/2}]) + central second-difference numerical derivative independent_cross_check | 🚫 **零宿主** | — |
| B431 | 严格独立 | analytical(v_g=1/(β1+β2Δ+½β3Δ²)) + central-difference numerical derivative independent_cross_check | 🚫 **零宿主** | — |
| B432 | 严格独立 | analytical(τ_g=k'(ω)·L) + central-difference numerical derivative independent_cross_check | 🚫 **零宿主** | — |
| B433 | 严格独立 | analytical(β2=d²k/dω², n²=1+F·ωp²/(ω0_res²−ω²)) + central second-difference numerical derivative independent_cross_check | 🚫 **零宿主** | — |
| B434 | 严格独立 | analytical(τ_g=(n+ωn')·L) + central-difference numerical derivative independent_cross_check | 🚫 **零宿主** | — |
| B435 | 严格独立 | analytical(L_D=T0²/|β2|) + central second-difference numerical derivative independent_cross_check | 🚫 **零宿主** | — |
| B436 | 严格独立 | analytical(Δt=|β2|·L·Δω) + central second-difference numerical derivative independent_cross_check | 🚫 **零宿主** | — |
| B437 | 严格独立 | analytical(τ_g=n_g·L) + central-difference numerical derivative independent_cross_check | 🚫 **零宿主** | — |
| B438 | 严格独立 | analytical(v_g=1/(n+ωn')) + central-difference numerical derivative independent_cross_check | 🚫 **零宿主** | — |
| B439 | 严格独立 | scipy.special.betainc（精确特殊函数 oracle） + composite-Simpson double-integral independent_cross_check | 🚫 **零宿主** | — |
| B440 | 严格独立 | scipy.special.betainc（精确特殊函数 oracle） + composite-Simpson double-integral independent_cross_check | 🚫 **零宿主** | — |
| B441 | 严格独立 | scipy.special.betainc（精确特殊函数 oracle） + composite-Simpson double-integral independent_cross_check | 🚫 **零宿主** | — |
| B442 | 严格独立 | scipy.special.betainc（精确特殊函数 oracle） + composite-Simpson double-integral independent_cross_check | 🚫 **零宿主** | — |
| B443 | 严格独立 | scipy.special.betainc（精确特殊函数 oracle） + composite-Simpson double-integral independent_cross_check | 🚫 **零宿主** | — |
| B444 | 严格独立 | integer-parameter binomial closed form Σ_{j=a}^{a+b-1}C(n,j)x^j(1-x)^{n-j}（精确闭式，与 scipy.betainc 互校 <1e-14） + composite-Simpson double-integral independent_cross_check | 🚫 **零宿主** | — |
| B445 | 严格独立 | integer-parameter binomial closed form Σ_{j=a}^{a+b-1}C(n,j)x^j(1-x)^{n-j}（精确闭式，与 scipy.betainc 互校 <1e-14） + composite-Simpson double-integral independent_cross_check | 🚫 **零宿主** | — |
| B446 | 严格独立 | scipy.special.sici（精确特殊函数 oracle） + RK4-defining-ODE integration independent_cross_check | 🚫 **零宿主** | — |
| B447 | 严格独立 | scipy.special.sici（精确特殊函数 oracle） + RK4-defining-ODE integration independent_cross_check | 🚫 **零宿主** | — |
| B448 | 严格独立 | scipy.special.sici（精确特殊函数 oracle） + RK4-defining-ODE integration independent_cross_check | 🚫 **零宿主** | — |
| B449 | 严格独立 | scipy.special.sici（精确特殊函数 oracle） + RK4-defining-ODE integration independent_cross_check | 🚫 **零宿主** | — |
| B450 | 严格独立 | scipy.special.shichi（精确特殊函数 oracle） + RK4-defining-ODE integration independent_cross_check | 🚫 **零宿主** | — |
| B451 | 严格独立 | scipy.special.shichi（精确特殊函数 oracle） + RK4-defining-ODE integration independent_cross_check | 🚫 **零宿主** | — |
| B452 | 严格独立 | analytical(RC step-response closed-form) + RK4-defining-ODE integration independent_cross_check | 🚫 **零宿主** | — |
| B453 | 严格独立 | analytical(coherent-state overlap closed-form) + truncated-Fock Kraus operator-sum independent_cross_check | 🚫 **零宿主** | — |
| B454 | 严格独立 | analytical(geometric-series closed-form) + truncated-Fock matrix-exponential/projector/partial-trace independent_cross_check | 🚫 **零宿主** | — |
| B455 | 严格独立 | analytical(2λ² closed-form) + truncated-Fock matrix-exponential/projector/partial-trace independent_cross_check | 🚫 **零宿主** | — |
| B456 | 严格独立 | analytical(mu*exp(-mu) closed-form) + truncated-Fock normalized-density-matrix independent_cross_check | 🚫 **零宿主** | — |
| B457 | 严格独立 | analytical(1-exp(-mu)*(1+mu) closed-form) + truncated-Fock normalized-density-matrix independent_cross_check | 🚫 **零宿主** | — |
| B458 | 严格独立 | analytical(shoelace closed-form area) + subpixel-averaged rasterization independent_cross_check | 🚫 **零宿主** | — |
| B459 | 严格独立 | closed_form(slope_closed = depth·(3√3/4)/FWHM) + central-difference numerical derivative independent_cross_check | 🚫 **零宿主** | — |
| B460 | 严格独立 | closed_form(sensitivity_golden = (n_clad/n_eff)·Γ_clad, Γ_clad=实际场 L² 份额) + finite_difference independent_cross_check | 🚫 **零宿主** | — |
| B461 | 严格独立 | closed_form(sensitivity_golden = (n_a/n_eff)·Γ_adlayer, Γ_adlayer=Γ_clad·(1−e^(−2γ·ds)) 实际场 L² 份额) + three_layer_transfer_matrix independent_cross_check | 🚫 **零宿主** | — |
| B462 | 严格独立 | closed_form(θ_eq = K_A·C/(1+K_A·C), K_A=k_on/k_off) + rk4_integration independent_cross_check | 🚫 **零宿主** | — |
| B463 | 严格独立 | analytical(rectangular series Q=(ΔP/μL)·(a·b³/12)·C_f(α), α=b/a, C_f→1 平行板缝 / 0.4217 方管) + 2D finite-difference Poisson red-black SOR independent_cross_check | 🚫 **零宿主** | — |
| B464 | 严格独立 | closed_form(L=√[(D·γ·cosθ)/(4η)·t]) + backward-euler implicit integration independent_cross_check | 🚫 **零宿主** | — |
| B465 | 严格独立 | closed_form(R_th=ln(r_o/r_i)/(2πkL)) + 1D finite-difference radial Laplace conservative-flux independent_cross_check | 🚫 **零宿主** | — |
| B466 | 严格独立 | closed_form(sinh(a/L)·e^{−d/L}/(1−e^{−a/L}), 1D damped heat-diffusion T''−T/L²+q/k'=0) + 1D finite-difference BVP tridiagonal-Thomas independent_cross_check | 🚫 **零宿主** | — |
| B467 | 严格独立 | closed_form(sqrt(S_i·R_f²·(π/2)·f_p), f_p=1/(2πR_fC) ⇒ collapses to sqrt(kT/C), R_f-independent) + time-domain impulse-response numerical integration independent_cross_check | 🚫 **零宿主** | — |
| B468 | 严格独立 | closed_form(exp(−d²/(2w²)), Gaussian mode-field overlap) + discrete-sampled linear-interpolated overlap-integral independent_cross_check | 🚫 **零宿主** | — |
| B469 | 严格独立 | closed_form(Rayleigh 商一阶本征值微扰 + 左本征矢 w，非对称算子; S=dγ/dn_a/(2 k0² n_eff)) + FV-FD 有限差分独立_cross_check | 🚫 **零宿主** | — |
| B470 | 严格独立 | closed_form(Rayleigh 商一阶本征值微扰 + 左本征矢 w; S=dγ/dn_a/(2 k0² n_eff)) + FV-FD 有限差分独立_cross_check | 🚫 **零宿主** | — |
| B471 | 严格独立 | closed_form(Rayleigh 商一阶本征值微扰 + 左本征矢 w; S=dγ/dn_a/(2 k0² n_eff)) + FV-FD 有限差分独立_cross_check | 🚫 **零宿主** | — |
| B472 | 自证桩 | closed_form(LOD_real(Q)=√((LOD_elec_ref·Q0/Q)² + LOD_temp_ref²), Q↑⇒LOD↓∝1/Q) · 自证桩（无方法学独立候选） | 🚫 **零宿主** | — |
| B473 | 严格独立 | closed_form(η=ħ/(gμB)·√(1+a²)·√2/(C·√(n_ph·T2*)), Raman/散粒受限) + 数值误差传播链独立_cross_check | 🚫 **零宿主** | — |
| B474 | 严格独立 | closed_form(η=ħ/(gμB)·√(1+a²)·√2/(C·√(n_ph·T2*))) + 数值线宽提取链独立_cross_check | 🚫 **零宿主** | — |
| B475 | 严格独立 | closed_form(⟨Φ²⟩_echo=2(1−cos(ωt/2))²，归一化丢 (γb/ω)²) + 时间域数值积分链独立_cross_check | 🚫 **零宿主** | — |
| B476 | 严格独立 | closed_form(解 d⁴+d₀³·d=3·d₀³·d_att，由 d(ln η_tot)/dd=0 解析导出) + 网格扫描+抛物插值独立_cross_check | 🚫 **零宿主** | — |
| B477 | 严格独立 | closed_form(η_NA=[cos³θ/3−cosθ]₀^{θmax}/(2/3)，θmax=arcsin NA) + 数值角分布采样独立_cross_check | 🚫 **零宿主** | — |
| B478 | 严格独立 | closed_form(X=(d_crit/r)³，轴向点偶极近场 B∝2m/r³ 与自场标度 m/d_crit³ 之比) + 点偶极场数值积分独立_cross_check | 🚫 **零宿主** | — |
| B479 | 严格独立 | closed_form(√(1+X_tot²)，信号 + 正交串扰噪声平方和) + 蒙特卡洛噪声功率叠加独立_cross_check | 🚫 **零宿主** | — |
| B480 | 严格独立 | closed_form(CMRR=20·log₁₀(1/ε)，ε=|ΔS|/S̄ 标度失配) + 含噪样本 LSQ 斜率比独立_cross_check | 🚫 **零宿主** | — |
| B481 | 严格独立 | closed_form(η_grad=η_single·√2/baseline，两点差分噪声叠加) + 蒙特卡洛两点差分标准差独立_cross_check | 🚫 **零宿主** | — |
| E1 | 自证桩 | empirical-measurement(E-SOI-NG-220) | Waveguide | i ｜ Waveguide: SOI 波导群折射率实测 4.18±0.05（AMF racetrack 反演）；波导模式核（gapdoc） |
| E2 | 严格独立 | empirical-measurement(E-SIN-NG-300) | Waveguide、SinPl | Ci ｜ Waveguide: 候选 semivec_ng=半矢量求解核 vs 实测 n_g（SiN 300nm 平台）；引擎 cheap 同 slab 核；SinPl: 同为 SiN 平台（但 E2=群折射率、E6=传播损耗，物理量不同） |
| E3 | 自证桩 | empirical-measurement(E-TBOX-FSR-TM) | RingResonator | T ｜ RingResonator: 薄埋氧 SOI 微环 FSR 实测 10.44nm（结构性不可接 C4 循环） |
| E4 | 自证桩 | empirical-measurement(E-SOI-CROSS-IL) | Crossing | K ｜ Crossing: corpus E-SOI-CROSS-IL = 52 集 E4；crossing 插入损耗实测 0.18±0.03dB |
| E5 | 自证桩 | empirical-measurement(E-MMI-1X2-EL) | MmiEl | K ｜ MmiEl: corpus E-MMI-1X2-EL = 52 集 E5；MMI 过量损耗实测 0.05dB |
| E6 | 自证桩 | empirical-measurement(E-SIN-PL-800) | SinPl | K ｜ SinPl: corpus E-SIN-PL-800 = 52 集 E6；厚 SiN 传播损耗实测 0.087dB/cm |
| E7 | 自证桩 | empirical-measurement(E-SOI-CROSS-XT) | Crossing | K ｜ Crossing: corpus E-SOI-CROSS-XT = 52 集 E7；crossing 串扰实测 −41±2dB |
| E8 | 严格独立 | empirical-measurement(E-GRATING-EFF) | GratingEff | T ｜ GratingEff: E8=E-GRATING-EFF 严格独立判决锚（v0.9.51 升格进 52 题集）；光栅耦合器引擎真判决锚，取代 B6 名义守则桩的覆盖角色（B6 仍为理想 0.5 下限守则桩，作名义邻居并行保留）。 |
| E9 | 降级量级参考 | empirical-measurement(E-YBRANCH-LOSS) | YbranchLoss | T ｜ YbranchLoss: E9=E-YBRANCH-LOSS 降级量级参考判决锚（v0.9.51 升格，candidate_status=degraded_ordinal）；Y-branch 引擎真判决锚，取代 B5 名义守则桩的覆盖角色（诚实边界：c1 未标定真实 PDK，不进死标量判决列）。 |
| E10 | 降级量级参考 | empirical-measurement(E-RING-FSR) | 🚫 **零宿主** | — |
| S1 | 自证桩 | physical-law(dB-budget-cascade) | ⟂系统层·光链路预算 | P ｜ ⟂系统层·光链路预算: 纯算术 dB 级联判决；宿主=lda_chain 全部光链路设计（wdm/add_drop/耦合器/…），不细分品类 |
| S2 | 自证桩 | physical-law(channel-plan) | ⟂系统层·WDM 信道规划、wdm | PT ｜ ⟂系统层·WDM 信道规划: 信道间隔−滤波器带宽>0 纯算术；宿主=wdm 包信道规划（title 明示 WDM 信道）；wdm: 信道间隔−滤波器带宽 无碰撞=wdm 信道规划判决 |
| S3 | 自证桩 | physical-law(ASE-cascade) | ⟂系统层·OSNR | P ｜ ⟂系统层·OSNR: ASE 级联解析；宿主=含放大光链路设计流 |
| S4 | 自证桩 | physical-law(fidelity-product) | ⟂系统层·量子保真度预算、quantum、multiqubit_fidelity | Pi ｜ ⟂系统层·量子保真度预算: F_total=∏fᵢ 乘法级联；宿主=量子门序列/多比特系统设计流（quantum/multiqubit）；quantum: 门序列保真度预算 ∏fᵢ；multiqubit_fidelity: 多比特保真度预算同族 |
| S5 | 自证桩 | physical-law(worst-case) | ⟂系统层·最坏情况预算 | P ｜ ⟂系统层·最坏情况预算: 工艺角最坏 margin；宿主=光链路设计流 |
| S6 | 自证桩 | physical-law(detector-margin) | ⟂系统层·探测器灵敏度 | P ｜ ⟂系统层·探测器灵敏度: P_rx−Sens margin；宿主=接收链路设计流 |
| S7 | 严格独立 | statistical(monte-carlo, seed-fixed) | ⟂系统层·统计预算 p5 | P ｜ ⟂系统层·统计预算 p5: MC 分布 p5（高斯闭式候选已接=严格独立）；宿主=光链路设计流 |
| S8 | 严格独立 | statistical(monte-carlo, seed-fixed) | ⟂系统层·OSNR 统计 p5 | P ｜ ⟂系统层·OSNR 统计 p5: MC OSNR 分布 p5（已接=严格独立）；宿主=含放大链路设计流 |
| S9 | 自证桩 | deterministic(LVS-algorithm, geometry+set) | ⟂签核·LVS | P ｜ ⟂签核·LVS: 版图-原理图一致性签核；宿主=全部含版图的品类（引擎/包通用，结构性不可接 C1+C3） |
| S10 | 自证桩 | deterministic(multilayer-LVS, layer-stack+geometry) | ⟂签核·多层 LVS | P ｜ ⟂签核·多层 LVS: M1/VIA/M2 层叠签核；宿主=多层布线版图品类（结构性不可接 C1+C3） |
| S11 | 自证桩 | deterministic(scale-pipeline, build+place+route+LVS) | ⟂签核·千器件规模 | P ｜ ⟂签核·千器件规模: 1000 器件全链路 ACCEPT；宿主=规模流水线（无独立品类） |
| S12 | 自证桩 | statistical(array-distribution, deterministic) | ⟂统计·阵列分布、wdm、multiqubit、multiqubit_fidelity | PT ｜ ⟂统计·阵列分布: 均值+下界+离群三锚 AND；宿主=WDM/CPO 多通道、量子多比特阵列（wdm/multiqubit/multiqubit_fidelity）；wdm: 多实例 WDM/CPO 阵列分布判决；multiqubit: 量子多比特阵列分布判决；multiqubit_fidelity: 逐 qubit 保真度分布判决（均值+下界+离群三锚） |
| S13 | 严格独立 | statistical(monte-carlo, seed-fixed) + analytical(gaussian-integral) | ⟂统计·设计良率 DFY、add_drop、wdm | Pi ｜ ⟂统计·设计良率 DFY: 环形 FSR 光刻容差命中概率（已接=严格独立）；宿主=环类产品（add_drop/wdm）；add_drop: 环形 FSR 光刻容差→命中规格概率；wdm: 多环产品良率延伸 |

## 3 · 零覆盖区与缺口清单

### 3.1 品类零覆盖（52 集内无任何锚宿主）

| 品类 | 类型 | 缺口说明 |
|---|---|---|
| mixed_system（mixed_system） | 包 | 多环 WDM × 量子读出混合巨型系统（装配级）。非「零锚」真死角——组成器件锚已在宿主品类接严格独立候选：B4（环 FSR，ring_fsr_peakfit）、B14（方向耦合器，dc_cmt_fft）、B22（CPW λ/4，tl_eigen_qres）、B26（色散位移 χ，chi_exact）；系统级预算走 S 层锚（S1 链路 dB 级联 / S4 保真度乘积预算 / S7-S8 统计 p5 / S12 阵列分布）；整芯片验收走 GC-* 整芯片对标（system_type=link / quantum_fidelity，29 条 52 外）。稀疏是装配级预期，非不可验货。 |
| wdm_coupler（wdm_coupler） | 包 | 耦合器×WDM 组合（装配级，复合弱）。组成严格锚已在宿主品类：B14（方向耦合器 3dB 耦合长度，dc_cmt_fft）、B4（环形 FSR，ring_fsr_peakfit）；WDM 信道规划走 S2（信道间隔−带宽>0）。整系统验收走 GC-*（system_type=link）。 |
| splitter_readout（splitter_readout） | 包 | 方向耦合器×量子读出（分束供电控制，装配级，复合弱）。组成严格锚已在宿主品类：B14（方向耦合器，dc_cmt_fft）、B22（CPW λ/4 读出谐振器，tl_eigen_qres）、B26（色散位移 χ，chi_exact）。整系统验收走 GC-*（system_type=quantum_fidelity）。 |

### 3.2 仅名义覆盖（宿主锚全为自证桩 / corpus 判决锚在 52 外）

| 品类 | 名义锚 | 判据态 | 说明 |
|---|---|---|---|
| MmiEl | E5 | 全桩 | corpus E-MMI-1X2-EL = 52 集 E5；MMI 过量损耗实测 0.05dB |
| multiqubit_fidelity | S12, S4 | 全桩 | 多比特保真度预算同族；逐 qubit 保真度分布判决（均值+下界+离群三锚） |

### 3.3 横向/无载体锚（不归属单一品类）

| 锚 | 判据态 | 说明 |
|---|---|---|
| B1 | ● | 散射效率 Q_scat（已接=严格独立）；33 类无散射体品类 ⇒ 求解核级锚（lda_solver/mie_solver） |
| B8 | ● | T→1 绝热极限（已接=严格独立）；33 类无锥度品类 ⇒ 求解核/互连级锚（EME 核，taper 内嵌于布局路由） |
| B17 | ◐ | I_c=2e·E_J/ℏ；量子结参数基础量，33 类无独立宿主 |
| B19 | ● | max|T|≤1 无源链路守恒（已接=严格独立）；宿主=全部无源链路品类 |
| S1 | ◐ | 纯算术 dB 级联判决；宿主=lda_chain 全部光链路设计（wdm/add_drop/耦合器/…），不细分品类 |
| S3 | ◐ | ASE 级联解析；宿主=含放大光链路设计流 |
| S5 | ◐ | 工艺角最坏 margin；宿主=光链路设计流 |
| S6 | ◐ | P_rx−Sens margin；宿主=接收链路设计流 |
| S7 | ● | MC 分布 p5（高斯闭式候选已接=严格独立）；宿主=光链路设计流 |
| S8 | ● | MC OSNR 分布 p5（已接=严格独立）；宿主=含放大链路设计流 |
| S9 | ◐ | 版图-原理图一致性签核；宿主=全部含版图的品类（引擎/包通用，结构性不可接 C1+C3） |
| S10 | ◐ | M1/VIA/M2 层叠签核；宿主=多层布线版图品类（结构性不可接 C1+C3） |
| S11 | ◐ | 1000 器件全链路 ACCEPT；宿主=规模流水线（无独立品类） |
| B31 | ● |  |
| B32 | ● |  |
| B33 | ● |  |
| B34 | ● |  |
| B36 | ● |  |
| B37 | ● |  |
| B40 | ● |  |
| B41 | ● |  |
| B42 | ● |  |
| B43 | ● |  |
| B44 | ● |  |
| B45 | ● |  |
| B46 | ● |  |
| B47 | ● |  |
| B48 | ● |  |
| B49 | ● |  |
| B50 | ● |  |
| B51 | ● |  |
| B52 | ● |  |
| B53 | ● |  |
| B54 | ● |  |
| B55 | ● |  |
| B56 | ● |  |
| B57 | ● |  |
| B58 | ● |  |
| B59 | ● |  |
| B60 | ● |  |
| B61 | ● |  |
| B62 | ● |  |
| B63 | ● |  |
| B64 | ● |  |
| B65 | ● |  |
| B66 | ● |  |
| B67 | ● |  |
| B68 | ● |  |
| B70 | ● |  |
| B71 | ● |  |
| B73 | ● |  |
| B74 | ● |  |
| B75 | ● |  |
| B76 | ● |  |
| B77 | ● |  |
| B78 | ● |  |
| B79 | ● |  |
| B80 | ● |  |
| B81 | ● |  |
| B82 | ● |  |
| B83 | ● |  |
| B84 | ● |  |
| B85 | ● |  |
| B86 | ● |  |
| B87 | ● |  |
| B88 | ● |  |
| B89 | ● |  |
| B90 | ● |  |
| B91 | ● |  |
| B92 | ● |  |
| B93 | ● |  |
| B94 | ● |  |
| B95 | ● |  |
| B96 | ● |  |
| B97 | ● |  |
| B98 | ● |  |
| B99 | ● |  |
| B100 | ● |  |
| B101 | ● |  |
| B102 | ● |  |
| B103 | ● |  |
| B104 | ● |  |
| B105 | ● |  |
| B106 | ● |  |
| B107 | ● |  |
| B108 | ● |  |
| B109 | ● |  |
| B110 | ● |  |
| B111 | ● |  |
| B112 | ● |  |
| B113 | ● |  |
| B114 | ● |  |
| B115 | ● |  |
| B116 | ● |  |
| B117 | ● |  |
| B118 | ● |  |
| B119 | ● |  |
| B120 | ● |  |
| B121 | ● |  |
| B122 | ● |  |
| B123 | ● |  |
| B124 | ● |  |
| B125 | ● |  |
| B126 | ● |  |
| B127 | ● |  |
| B128 | ● |  |
| B129 | ● |  |
| B130 | ● |  |
| B131 | ● |  |
| B132 | ● |  |
| B133 | ● |  |
| B134 | ● |  |
| B135 | ● |  |
| B136 | ● |  |
| B137 | ● |  |
| B138 | ● |  |
| B139 | ● |  |
| B140 | ● |  |
| B141 | ● |  |
| B142 | ● |  |
| B143 | ● |  |
| B144 | ● |  |
| B145 | ● |  |
| B146 | ● |  |
| B147 | ● |  |
| B148 | ● |  |
| B149 | ● |  |
| B150 | ● |  |
| B151 | ● |  |
| B152 | ● |  |
| B153 | ● |  |
| B154 | ● |  |
| B155 | ● |  |
| B156 | ● |  |
| B157 | ● |  |
| B158 | ● |  |
| B159 | ● |  |
| B160 | ● |  |
| B161 | ● |  |
| B162 | ● |  |
| B163 | ● |  |
| B164 | ● |  |
| B165 | ● |  |
| B166 | ● |  |
| B167 | ● |  |
| B168 | ● |  |
| B169 | ● |  |
| B170 | ● |  |
| B171 | ● |  |
| B172 | ● |  |
| B173 | ● |  |
| B174 | ● |  |
| B175 | ● |  |
| B176 | ● |  |
| B177 | ● |  |
| B178 | ● |  |
| B179 | ● |  |
| B180 | ● |  |
| B181 | ● |  |
| B182 | ● |  |
| B183 | ● |  |
| B184 | ● |  |
| B185 | ● |  |
| B186 | ● |  |
| B187 | ● |  |
| B188 | ● |  |
| B189 | ● |  |
| B190 | ● |  |
| B191 | ● |  |
| B192 | ● |  |
| B193 | ● |  |
| B194 | ● |  |
| B195 | ● |  |
| B196 | ● |  |
| B197 | ● |  |
| B198 | ● |  |
| B199 | ● |  |
| B200 | ● |  |
| B201 | ● |  |
| B202 | ● |  |
| B203 | ● |  |
| B204 | ● |  |
| B205 | ● |  |
| B206 | ● |  |
| B207 | ● |  |
| B208 | ● |  |
| B209 | ● |  |
| B210 | ● |  |
| B211 | ● |  |
| B212 | ● |  |
| B213 | ● |  |
| B214 | ● |  |
| B215 | ● |  |
| B216 | ● |  |
| B217 | ● |  |
| B218 | ● |  |
| B219 | ● |  |
| B220 | ● |  |
| B221 | ● |  |
| B222 | ● |  |
| B223 | ● |  |
| B224 | ● |  |
| B225 | ● |  |
| B226 | ● |  |
| B227 | ● |  |
| B228 | ● |  |
| B229 | ● |  |
| B230 | ● |  |
| B231 | ● |  |
| B232 | ● |  |
| B233 | ● |  |
| B234 | ● |  |
| B235 | ● |  |
| B236 | ● |  |
| B237 | ● |  |
| B238 | ● |  |
| B239 | ● |  |
| B240 | ● |  |
| B241 | ● |  |
| B242 | ● |  |
| B243 | ● |  |
| B244 | ● |  |
| B245 | ● |  |
| B246 | ● |  |
| B247 | ● |  |
| B248 | ● |  |
| B249 | ● |  |
| B250 | ● |  |
| B251 | ● |  |
| B252 | ● |  |
| B253 | ● |  |
| B254 | ● |  |
| B255 | ● |  |
| B256 | ● |  |
| B257 | ● |  |
| B258 | ● |  |
| B259 | ● |  |
| B260 | ● |  |
| B261 | ● |  |
| B262 | ● |  |
| B263 | ● |  |
| B264 | ● |  |
| B265 | ● |  |
| B266 | ● |  |
| B267 | ● |  |
| B268 | ● |  |
| B269 | ● |  |
| B270 | ● |  |
| B271 | ● |  |
| B272 | ● |  |
| B273 | ● |  |
| B274 | ● |  |
| B275 | ● |  |
| B276 | ● |  |
| B277 | ● |  |
| B278 | ● |  |
| B279 | ● |  |
| B280 | ● |  |
| B281 | ● |  |
| B282 | ● |  |
| B283 | ● |  |
| B284 | ● |  |
| B285 | ● |  |
| B286 | ● |  |
| B287 | ● |  |
| B288 | ● |  |
| B289 | ● |  |
| B290 | ● |  |
| B291 | ● |  |
| B292 | ● |  |
| B293 | ● |  |
| B294 | ● |  |
| B295 | ● |  |
| B296 | ● |  |
| B297 | ● |  |
| B298 | ● |  |
| B299 | ● |  |
| B300 | ● |  |
| B301 | ● |  |
| B302 | ● |  |
| B303 | ● |  |
| B304 | ● |  |
| B305 | ● |  |
| B306 | ● |  |
| B307 | ● |  |
| B308 | ● |  |
| B309 | ● |  |
| B310 | ● |  |
| B311 | ● |  |
| B312 | ● |  |
| B313 | ● |  |
| B314 | ● |  |
| B315 | ● |  |
| B316 | ● |  |
| B317 | ● |  |
| B318 | ● |  |
| B319 | ● |  |
| B320 | ● |  |
| B321 | ● |  |
| B322 | ● |  |
| B323 | ● |  |
| B324 | ● |  |
| B325 | ● |  |
| B326 | ● |  |
| B327 | ● |  |
| B328 | ● |  |
| B329 | ● |  |
| B330 | ● |  |
| B331 | ● |  |
| B332 | ● |  |
| B333 | ● |  |
| B334 | ● |  |
| B335 | ● |  |
| B336 | ● |  |
| B337 | ● |  |
| B338 | ● |  |
| B339 | ● |  |
| B340 | ● |  |
| B341 | ● |  |
| B342 | ● |  |
| B343 | ● |  |
| B344 | ● |  |
| B345 | ● |  |
| B346 | ● |  |
| B347 | ● |  |
| B348 | ● |  |
| B349 | ● |  |
| B350 | ● |  |
| B351 | ● |  |
| B352 | ● |  |
| B353 | ● |  |
| B354 | ● |  |
| B355 | ● |  |
| B356 | ● |  |
| B357 | ● |  |
| B358 | ● |  |
| B359 | ● |  |
| B360 | ● |  |
| B361 | ● |  |
| B362 | ● |  |
| B363 | ● |  |
| B364 | ● |  |
| B365 | ● |  |
| B366 | ● |  |
| B367 | ● |  |
| B368 | ● |  |
| B369 | ● |  |
| B370 | ● |  |
| B371 | ● |  |
| B372 | ● |  |
| B373 | ● |  |
| B374 | ● |  |
| B375 | ● |  |
| B376 | ● |  |
| B377 | ● |  |
| B378 | ● |  |
| B379 | ● |  |
| B380 | ● |  |
| B381 | ● |  |
| B382 | ● |  |
| B383 | ● |  |
| B384 | ● |  |
| B385 | ● |  |
| B386 | ● |  |
| B387 | ● |  |
| B388 | ● |  |
| B389 | ● |  |
| B390 | ● |  |
| B391 | ● |  |
| B392 | ● |  |
| B393 | ● |  |
| B394 | ● |  |
| B395 | ● |  |
| B396 | ● |  |
| B397 | ● |  |
| B398 | ● |  |
| B399 | ● |  |
| B400 | ● |  |
| B401 | ● |  |
| B402 | ● |  |
| B403 | ● |  |
| B404 | ● |  |
| B405 | ● |  |
| B406 | ● |  |
| B407 | ● |  |
| B408 | ● |  |
| B409 | ● |  |
| B410 | ● |  |
| B411 | ● |  |
| B412 | ● |  |
| B413 | ● |  |
| B414 | ● |  |
| B415 | ● |  |
| B416 | ● |  |
| B417 | ● |  |
| B418 | ● |  |
| B419 | ● |  |
| B420 | ● |  |
| B421 | ● |  |
| B422 | ● |  |
| B423 | ● |  |
| B424 | ● |  |
| B425 | ● |  |
| B426 | ● |  |
| B427 | ● |  |
| B428 | ● |  |
| B429 | ● |  |
| B430 | ● |  |
| B431 | ● |  |
| B432 | ● |  |
| B433 | ● |  |
| B434 | ● |  |
| B435 | ● |  |
| B436 | ● |  |
| B437 | ● |  |
| B438 | ● |  |
| B439 | ● |  |
| B440 | ● |  |
| B441 | ● |  |
| B442 | ● |  |
| B443 | ● |  |
| B444 | ● |  |
| B445 | ● |  |
| B446 | ● |  |
| B447 | ● |  |
| B448 | ● |  |
| B449 | ● |  |
| B450 | ● |  |
| B451 | ● |  |
| B452 | ● |  |
| B453 | ● |  |
| B454 | ● |  |
| B455 | ● |  |
| B456 | ● |  |
| B457 | ● |  |
| B458 | ● |  |
| B459 | ● |  |
| B460 | ● |  |
| B461 | ● |  |
| B462 | ● |  |
| B463 | ● |  |
| B464 | ● |  |
| B465 | ● |  |
| B466 | ● |  |
| B467 | ● |  |
| B468 | ● |  |
| B469 | ● |  |
| B470 | ● |  |
| B471 | ● |  |
| B472 | ◐ |  |
| B473 | ● |  |
| B474 | ● |  |
| B475 | ● |  |
| B476 | ● |  |
| B477 | ● |  |
| B478 | ● |  |
| B479 | ● |  |
| B480 | ● |  |
| B481 | ● |  |
| E10 | △ |  |

### 3.4 接线优先级建议（历史记录 · 含已落地项）

1. ~~热光相移器零锚 → 新锚 B29（D-73 升格）~~ **✅ 已落地 v0.9.39**：B29=1D 散热鳍稳态 PDE cosh 闭式，candidate=thermal_phase_fdm（FDM 数值解，判据 D 真收敛）；严格独立、CI core 95→97。
2. ~~readout_fidelity 零锚 → 读出 SNR 锚（钉子 E）~~ **✅ 已落地 v0.9.39**：B30=色散读出 erfc 闭式链，candidate=readout_fidelity_quad（ε 高斯重叠数值积分，判据 D 真收敛）；严格独立。
3. **B5/B6/B7 守则桩**：非接线问题而是 ORACLE 缺口（Meep/Tidy3D 场级，C 期锁）；解锁后 YbranchLoss/GratingEff/Crossing 引擎获得集内真锚。
4. ~~引擎真判决锚入集~~ **✅ 锚集升格 v0.9.51**：E-YBRANCH-LOSS→E9 / E-GRATING-EFF→E8 升格进 52 题集，K 证据失真（原 corpus 在集外）消除；D-73 已于 v0.9.39 升格为 B29。可被外部验货比例 25/50 → 26/52。
   **✅ 覆盖矩阵层面收尾 v0.9.54（治理①）**：E8/E9 已登记为 GratingEff / YbranchLoss 宿主（取代 B6/B5 名义守则桩的覆盖角色），矩阵 §1 现同时展示真判决锚（E8●/E9△）与名义桩（B6◐/B5◐），K 证据口径失真在矩阵层面闭合；`run_coverage_deadzone_closure_smoke.py` 增 E8/E9 反向护栏。
5. taper（B8）与散射（B1）两无载体锚指向品类缺口：无「锥度/散射体」设计引擎 ⇒ 可评估新增品类，或明示 B8 归互连级。

> **覆盖死角收口结论（2026-09-06）**：原 §3.1 五处零覆盖中，PhaseShifter（B29）+ readout_fidelity（B30）已于 v0.9.39 接严格独立候选，本矩阵已登记宿主；剩余 mixed_system / wdm_coupler / splitter_readout 三处为**装配级弱复合包**，其组成器件锚（B14/B4/B22/B26 等）已在宿主品类接严格独立候选，系统级预算走 S 层锚、整芯片验收走 GC-*（52 集外，29 条）——稀疏为装配级预期，**非真死角**。零覆盖集现恰为这 3 个复合包。

## 4 · 口径、方法与诚实边界

- **数据源**：BENCHMARK_ORDER/DEFS（benchmarks.py）、BENCHMARK_CANDIDATES（verification_adapters.py）、ENGINE_KINDS/PACKAGE_KINDS/ENGINE_DOMAIN/_ENGINE_TITLE（design_package.py）、引擎 specs（design_engine.py）。接线态判序与 `harness.candidate_class()` 同源：`spec.candidate ∈ 登记表 ⇒ strict`。
- **包级品类注意**：包是装配级设计流，其整包验收门 = S 层系统/统计/签核锚 + GC-* 整芯片对标（29 条，52 集外）；本矩阵只标「组成器件的物理锚」→ 包行稀疏是预期的，不直接等于「包不可验货」。
- **K 证据含义（v0.9.54 已收尾）**：原 corpus 类引擎（YbranchLoss/GratingEff）的引擎级判决锚（E-YBRANCH-LOSS/E-GRATING-EFF）在 52 锚集外、表中宿主仅为名义邻居（B5/B6），构成口径失真。**v0.9.51 已将 E9/E8 升格进 52 题集、v0.9.54 进一步登记为宿主**⇒ 该失真已闭合（YbranchLoss/GratingEff 现同时展示真判决锚 E9△/E8● 与名义桩 B5◐/B6◐）。剩余 K 证据（E4/E5/E6/E7）为 corpus 实测锚本身的名义覆盖，属既定诚实边界。
- **推断标记**：所有 `i`（inferred）归属为编辑判断，供评审；`T/C` 为代码/标题直接证据。修正归属 = 改 `run_anchor_coverage_matrix.py` 的 ANCHOR_HOSTS 后重跑。
- 结构性不可接桩依据：`docs/anchor_wiring_survey_2026-09-03.md`（S9/S10 违 C1+C3、E3 违 C4、B21 违 C2、B16 违 C5+C3、B11 C1/C2/C4）。
- 无载体锚 B1/B8/B17 虽零品类宿主，但 B1/B8 为严格独立（求解核级验证）、B17 为确定性基础量 —— 属「能力有、品类载体缺」，非验证缺口。
