# LDA 锚题覆盖矩阵（33 类 × 48 锚 · T-9）

> 生成：2026-09-04 · 生成器 `lda/run_anchor_coverage_matrix.py`（可复现：改归属表后重跑）
> 口径：**品类×锚覆盖** = 该锚的物理对象/判决对象落在该设计品类上。覆盖 ≠ 已接独立候选；●=严格独立已接、◐=自证桩（名义覆盖）。证据分级：**C**=引擎 specs 代码显式引用（最权威）· **T**=锚 title/metric 明写该品类 · **K**=引擎真判决锚在 48 集外（语料锚），所列 48 锚仅为名义邻居· **i**=编辑推断 · **P**=横向/系统层。

## 0 · 摘要

- 33 类 = 22 引擎（光子 15 + 量子 7）+ 11 包；48 锚（B28 + E7 + S13）；严格独立 **23** / 自证桩 **25**
- 有 ≥1 锚宿主（48 集内）：引擎 **21/22**、包 **7/11**
- 横向/系统层锚（无单一品类宿主）**13**：B1, B8, B17, B19, S1, S3, S5, S6, S7, S8, S9, S10, S11
- 零覆盖品类与接线建议见 §3；完整归属见 §2。

## 1 · 品类 → 锚覆盖矩阵（33 行）

每类一行：命中锚序列 `锚id(符号·证据)`；**空 = 48 集内零覆盖**。

| # | 品类（域） | 48 集覆盖锚 | 覆盖数 |
|---|---|---|---|
| 1 | **Waveguide**（引擎） | B2◐i · E1◐i · E2●C | 3 |
| 2 | **BraggMirror**（引擎） | B15●i | 1 |
| 3 | **RingResonator**（引擎） | B3●i · B4●C · B11◐T · E3◐T | 4 |
| 4 | **MziInterferometer**（引擎） | B20●i | 1 |
| 5 | **PhCCavity**（引擎） | B21◐C | 1 |
| 6 | **Mmi1x2**（引擎） | B16◐C | 1 |
| 7 | **GratingCoupler2**（引擎） | B15●i | 1 |
| 8 | **DirectionalCoupler2**（引擎） | B14●C | 1 |
| 9 | **YbranchLoss**（引擎） | B5◐K | 1 |
| 10 | **GratingEff**（引擎） | B6◐K | 1 |
| 11 | **Crossing**（引擎） | B7◐T · E4◐K · E7◐K | 3 |
| 12 | **MmiEl**（引擎） | E5◐K | 1 |
| 13 | **SinPl**（引擎） | E2●i · E6◐K | 2 |
| 14 | **PhaseShifter**（引擎） | 🚫 **零覆盖** | 0 |
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
| 28 | **readout_fidelity**（包） | 🚫 **零覆盖** | 0 |
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

## 2 · 锚 → 归属明细（48 行）

| 锚 | 判据态 | oracle | 宿主（品类 / 横向层） | 证据 |
|---|---|---|---|---|
| B1 | 严格独立 | analytical(Rayleigh-limit) | ⟂求解核·Mie 散射 | P ｜ ⟂求解核·Mie 散射: 散射效率 Q_scat（已接=严格独立）；33 类无散射体品类 ⇒ 求解核级锚（lda_solver/mie_solver） |
| B2 | 自证桩 | analytical(EIM) | Waveguide | i ｜ Waveguide: EIM/slab 有效折射率；引擎 cheap=_slab_te_neff 同族（gapdoc: 波导） |
| B3 | 严格独立 | analytical(Airy) | RingResonator | i ｜ RingResonator: Airy 腔 FSR 无独立品类；FSR 口径方法学挂谐振腔家族（与 B4/B20 并列对照） |
| B4 | 严格独立 | analytical(ring)/sax | RingResonator、add_drop | CT ｜ RingResonator: 引擎 FSR 解析锚 λ²/(n_g·2πR)，engine note 同式；add_drop: 锚对象即 add-drop 环形谐振器 drop 口传递函数 |
| B5 | 自证桩 | design-rule(Meep/Tidy3D field 预留) | YbranchLoss | K ｜ YbranchLoss: 引擎真判决锚 E-YBRANCH-LOSS 在 48 集外；B5=理想 50/50 下限 3.0dB 守则桩（同器件名义覆盖） |
| B6 | 自证桩 | design-rule(Tidy3D/Meep field 预留) | GratingEff | K ｜ GratingEff: 引擎真判决锚 E-GRATING-EFF 在 48 集外；B6=成熟工艺可达效率 0.5 守则桩（同器件名义覆盖） |
| B7 | 自证桩 | design-rule(Meep field 预留) | Crossing | T ｜ Crossing: 波导交叉串扰；引擎 IL+XT 双出口，E7=实测 XT 同器件（守则桩 vs 实证桩） |
| B8 | 严格独立 | analytical(adiabatic-limit) | ⟂求解核·绝热锥度 EME | P ｜ ⟂求解核·绝热锥度 EME: T→1 绝热极限（已接=严格独立）；33 类无锥度品类 ⇒ 求解核/互连级锚（EME 核，taper 内嵌于布局路由） |
| B9 | 严格独立 | analytical(transmon/Koch2007) | Transmon、quantum | Ci ｜ Transmon: 引擎 cheap=koch_f01 即 B9 golden 同式；quantum: 量子逆设计包（Transmon）同物理 |
| B10 | 严格独立 | analytical(lindblad-closed-form) | quantum | i ｜ quantum: 单比特门退相干极限保真度；门层无独立引擎品类 ⇒ 量子系统/门层锚；单比特门退相干保真度：量子门层锚；品类宿主仅 quantum 包（○），主缺口=两比特门锚（gapdoc 钉子 C 候选） |
| B11 | 自证桩 | analytical(ring-transfer-function) | RingResonator | T ｜ RingResonator: 环形谐振器 drop 口透射谱谱形 L2（结构性不可接，见 T-4 侦察） |
| B12 | 严格独立 | analytical(quarter-wave closed form) | ReadoutResonator | i ｜ ReadoutResonator: λ/4 超导谐振器通式（与 B22 CPW 具体化并列，同引擎宿主） |
| B13 | 严格独立 | analytical(charge-coupling closed form) | quantum、multiqubit | i ｜ quantum: 双 transmon 电容耦合 J；无独立双比特引擎 ⇒ quantum 包（频率/耦合设计）；multiqubit: N-qubit 频率复用读出依赖 J 间隔规划（弱） |
| B14 | 严格独立 | analytical(coupled-mode) | DirectionalCoupler2、coupler | CT ｜ DirectionalCoupler2: 引擎 cheap=b14_dc_coupling_length，note 显式 B14；coupler: 包=方向耦合器设计闭环（D-55），锚=3dB 耦合长度 |
| B15 | 严格独立 | analytical(Bragg condition) | BraggMirror、GratingCoupler2 | i ｜ BraggMirror: Bragg 条件 λ_B=2·n_eff·Λ；镜周期设计同族（gapdoc: Bragg）；GratingCoupler2: λ_B=Λ·n_eff 同一阶相位匹配 |
| B16 | 自证桩 | design-rule(general-interference) | Mmi1x2 | C ｜ Mmi1x2: 引擎 note 显式 B16 锚（结构性不可接 C5+C3） |
| B17 | 自证桩 | analytical(Josephson relation) | ⟂基础量·约瑟夫森 Ic | P ｜ ⟂基础量·约瑟夫森 Ic: I_c=2e·E_J/ℏ；量子结参数基础量，33 类无独立宿主 |
| B18 | 自证桩 | analytical(cavity-QED) | ReadoutPair、readout_chain | i ｜ ReadoutPair: 腔 QED 增强因子 F_P=4g²/(κγ₁)；读出/比特配对物理（弱）；readout_chain: 色散读出链路（复用 D-88 参数，弱） |
| B19 | 严格独立 | analytical(passive-network: 无外部泵浦 ⇒ |T|≤1) | ⟂物理·链路 passivity | P ｜ ⟂物理·链路 passivity: max|T|≤1 无源链路守恒（已接=严格独立）；宿主=全部无源链路品类 |
| B20 | 严格独立 | analytical(MZI interference) | MziInterferometer | i ｜ MziInterferometer: MZI FSR=λ²/(n_eff·ΔL) 同式（engine note 即 B20 物理） |
| B21 | 自证桩 | analytical(PhC Bragg/FP band-edge) | PhCCavity | C ｜ PhCCavity: 引擎 cheap=b21_phc_resonance，note 显式 B21（结构性不可接 C2） |
| B22 | 严格独立 | analytical(CPW λ/4 TL resonance) | ReadoutResonator、readout_chain | Ci ｜ ReadoutResonator: 引擎 cheap=b22_qres_frequency，note 显式 B22；readout_chain: CPW λ/4 读出谐振器=readout 链核心元件 |
| B23 | 严格独立 | analytical(LC oscillator strict limit E_J→0) | Fluxonium | C ｜ Fluxonium: 引擎 note 显式 B23 LC 极限边界校验 |
| B24 | 严格独立 | analytical(2nd-order perturbation / Schrieffer-Wolff) | TunableCoupler | C ｜ TunableCoupler: 引擎 cheap=b24_tcoup_geff，note 显式 B24 |
| B25 | 严格独立 | analytical(SQUID E_J(Φ)=E_JΣ·|cos(πΦ/Φ0)| + Koch) | TunableTransmon | C ｜ TunableTransmon: 引擎 cheap=b25_tunable_transmon_f01，note 显式 B25 |
| B26 | 严格独立 | analytical(Blais χ=g²α/(Δ(Δ+α))) | ReadoutPair、readout_chain | Ci ｜ ReadoutPair: 引擎 cheap=b26_dispersive_shift，note 显式 B26；readout_chain: 色散位移 χ=readout 链核心设计量 |
| B27 | 严格独立 | analytical(t_CZ=π/(2|χ|)) | CzGate | C ｜ CzGate: 引擎 cheap=b27_cz_gate_time，note 显式 B27 |
| B28 | 严格独立 | analytical(MZM Pockels half-wave) + integral-bisect cross-check | MziModulator | i ｜ MziModulator: 引擎目标 V_π（Pockels）与 B28 同物理量同闭式 |
| E1 | 自证桩 | empirical-measurement(E-SOI-NG-220) | Waveguide | i ｜ Waveguide: SOI 波导群折射率实测 4.18±0.05（AMF racetrack 反演）；波导模式核（gapdoc） |
| E2 | 严格独立 | empirical-measurement(E-SIN-NG-300) | Waveguide、SinPl | Ci ｜ Waveguide: 候选 semivec_ng=半矢量求解核 vs 实测 n_g（SiN 300nm 平台）；引擎 cheap 同 slab 核；SinPl: 同为 SiN 平台（但 E2=群折射率、E6=传播损耗，物理量不同） |
| E3 | 自证桩 | empirical-measurement(E-TBOX-FSR-TM) | RingResonator | T ｜ RingResonator: 薄埋氧 SOI 微环 FSR 实测 10.44nm（结构性不可接 C4 循环） |
| E4 | 自证桩 | empirical-measurement(E-SOI-CROSS-IL) | Crossing | K ｜ Crossing: corpus E-SOI-CROSS-IL = 48 集 E4；crossing 插入损耗实测 0.18±0.03dB |
| E5 | 自证桩 | empirical-measurement(E-MMI-1X2-EL) | MmiEl | K ｜ MmiEl: corpus E-MMI-1X2-EL = 48 集 E5；MMI 过量损耗实测 0.05dB |
| E6 | 自证桩 | empirical-measurement(E-SIN-PL-800) | SinPl | K ｜ SinPl: corpus E-SIN-PL-800 = 48 集 E6；厚 SiN 传播损耗实测 0.087dB/cm |
| E7 | 自证桩 | empirical-measurement(E-SOI-CROSS-XT) | Crossing | K ｜ Crossing: corpus E-SOI-CROSS-XT = 48 集 E7；crossing 串扰实测 −41±2dB |
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

### 3.1 品类零覆盖（48 集内无任何锚宿主）

| 品类 | 类型 | 缺口说明 |
|---|---|---|
| engine_phaseshifter（PhaseShifter） | 引擎 | 热光相移器：唯一零覆盖引擎。引擎自锚 D-73（相移效率 deg/mW）在 48 集外；48 集最近邻 B28 为电光 Pockels（机制不同，不可顶替）⇒ 建议新锚 B29（热光相位效率，D-73 升格） |
| readout_fidelity（readout_fidelity） | 包 | 单发读出保真度预算：48 集无读出 SNR/保真度物理锚（gapdoc 08-29 已列缺口「钉子 E 读出 SNR 锚」） |
| mixed_system（mixed_system） | 包 | 多环 WDM × 量子读出混合巨型系统：组合系统无直接锚；组成器件锚在宿主品类，整系统验收走 GC-*（48 外） |
| wdm_coupler（wdm_coupler） | 包 | 耦合器×WDM 组合（FDTD 标定 gap）：复合弱；组成锚 B14（DC）与 B4（环）在其宿主品类 |
| splitter_readout（splitter_readout） | 包 | 方向耦合器×量子读出（分束供电控制）：复合弱；组成锚 B14/B22 在宿主品类 |

### 3.2 仅名义覆盖（宿主锚全为自证桩 / corpus 判决锚在 48 外）

| 品类 | 名义锚 | 判据态 | 说明 |
|---|---|---|---|
| PhCCavity | B21 | 全桩 | 引擎 cheap=b21_phc_resonance，note 显式 B21（结构性不可接 C2） |
| Mmi1x2 | B16 | 全桩 | 引擎 note 显式 B16 锚（结构性不可接 C5+C3） |
| YbranchLoss | B5 | 全桩 | 引擎真判决锚 E-YBRANCH-LOSS 在 48 集外；B5=理想 50/50 下限 3.0dB 守则桩（同器件名义覆盖） |
| GratingEff | B6 | 全桩 | 引擎真判决锚 E-GRATING-EFF 在 48 集外；B6=成熟工艺可达效率 0.5 守则桩（同器件名义覆盖） |
| Crossing | B7, E4, E7 | 全桩 | 波导交叉串扰；引擎 IL+XT 双出口，E7=实测 XT 同器件（守则桩 vs 实证桩）；corpus E-SOI-CROSS-IL = 48 集 E4；crossing 插入损耗实测 0.18±0.03dB；corpus E-SOI-CROSS-XT = 48 集 E7；crossing 串扰实测 −41±2dB |
| MmiEl | E5 | 全桩 | corpus E-MMI-1X2-EL = 48 集 E5；MMI 过量损耗实测 0.05dB |
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

### 3.4 接线优先级建议

1. **热光相移器零锚 → 新锚 B29**（D-73 升格进 48 集）：唯一零覆盖引擎，工作量小；与 B28 电光并列构成有源调制双锚。
2. **readout_fidelity 零锚 → 读出 SNR 锚**（gapdoc 钉子 E）：单发读出保真度是量子读出货架卖点，缺物理 ground。
3. **B5/B6/B7 守则桩**：非接线问题而是 ORACLE 缺口（Meep/Tidy3D 场级，C 期锁）；解锁后 YbranchLoss/GratingEff/Crossing 引擎获得集内真锚。
4. **引擎真判决锚入集**：E-YBRANCH-LOSS / E-GRATING-EFF / D-73 三处引擎级判决锚在 48 集外 ⇒ 建议评估升格，否则 48 锚口径对 YbranchLoss / GratingEff / PhaseShifter 三类覆盖失真（矩阵 K 证据即此）。
5. taper（B8）与散射（B1）两无载体锚指向品类缺口：无「锥度/散射体」设计引擎 ⇒ 可评估新增品类，或明示 B8 归互连级。

## 4 · 口径、方法与诚实边界

- **数据源**：BENCHMARK_ORDER/DEFS（benchmarks.py）、BENCHMARK_CANDIDATES（verification_adapters.py）、ENGINE_KINDS/PACKAGE_KINDS/ENGINE_DOMAIN/_ENGINE_TITLE（design_package.py）、引擎 specs（design_engine.py）。接线态判序与 `harness.candidate_class()` 同源：`spec.candidate ∈ 登记表 ⇒ strict`。
- **包级品类注意**：包是装配级设计流，其整包验收门 = S 层系统/统计/签核锚 + GC-* 整芯片对标（29 条，48 集外）；本矩阵只标「组成器件的物理锚」→ 包行稀疏是预期的，不直接等于「包不可验货」。
- **K 证据含义**：corpus 类引擎（YbranchLoss/GratingEff 等）的引擎级判决锚（E-YBRANCH-LOSS/E-GRATING-EFF）不在 48 锚集内 ⇒ 表中宿主为名义/物理邻居（B5/B6），勿误读为「该品类已被 48 锚严格覆盖」。
- **推断标记**：所有 `i`（inferred）归属为编辑判断，供评审；`T/C` 为代码/标题直接证据。修正归属 = 改 `run_anchor_coverage_matrix.py` 的 ANCHOR_HOSTS 后重跑。
- 结构性不可接桩依据：`docs/anchor_wiring_survey_2026-09-03.md`（S9/S10 违 C1+C3、E3 违 C4、B21 违 C2、B16 违 C5+C3、B11 C1/C2/C4）。
- 无载体锚 B1/B8/B17 虽零品类宿主，但 B1/B8 为严格独立（求解核级验证）、B17 为确定性基础量 —— 属「能力有、品类载体缺」，非验证缺口。
