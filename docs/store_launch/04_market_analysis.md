# LDA 设计商店 · 市场与行业趋势分析（v0.8.47–v0.8.51 扩货架依据）

> 用途：为「货架 → 下载付费」的开放范围、定价与叙事提供市场依据。数据来自 LightCounting / Yole / HDIN / Dataintelo / IIM 等公开报告及行业媒体（2026-08 检索），口径差异已在文中标注。本分析为筹划稿，不构成投资建议。

## 一、市场总览（规模与增速）

| 赛道 | 规模 / 增速（公开口径） | 关键拐点 |
|---|---|---|
| 光模块（全球） | 2024–2029 CAGR 22%，2029 破 **370 亿美元** | AI 数据中心驱动 |
| 硅光（SiPh） | 2026 近 **80 亿美元**，份额 25%→50%+；2029 硅光模块 **103 亿美元**，5 年 CAGR 45% | 从"前沿概念"转"主流技术" |
| CPO（共封装） | 2026 拐点年（NVIDIA Spectrum-X 已量产）；2027 破 **50 亿美元**，CAGR>100%；Coherent 估 2030 达 **150 亿美元** | 800G/1.6T 端口起量 |
| 50G-PON（接入） | ITU-T G.9804 标准 2021 发布、2023 增补对称型；工信部 2025 首批 168 试点→2026 商用启航（2026.4 验收 136：52 小区/38 工厂/46 园区） | 万兆光网主航道 |
| 可重构光交换（OCS） | Cignal AI 估 2029 ≥**25 亿美元**；LightCounting 估 Scale-Up 光互连 2027 规模商用；Lumentum OCS 季度收入 2026 底 ~$1 亿 | AI 超节点拓扑重构 |
| 高速光模块 | 800G 规模放量，1.6T 加速渗透（2026 出货 >1000 万只、规模 ~167 亿美元）；3.2T 研发 | 硅光在 800G 占比>50%、1.6T 占 70–80% |
| 光子 EDA 软件 | 2025 软件段 ~**12.3 亿美元**（占 68.4%），CAGR 12.9%→2034 | 分层/云化定价成主流 |
| 量子芯片设计软件 | 超导量子 2025 **4.82 亿美元**（CAGR 34%）；量子光子段 CAGR **22.4%（最快垂直）** | 国产化刚需 + 战略赛道 |

**结论**：硅光/CPO/高速收发是当下确定性最高的增量；量子是高增长但早期、且受出口管制与国产化双重约束的"战略储备"赛道。

## 二、光子主赛道拆解（对应本次开放的货架）

| 方向 | 代表货架 | 市场信号 |
|---|---|---|
| 高速收发 | 1.6T DR8/FR4、800G DR8/FR4、400G DR4、PSM4、FR4、CWDM4、LPO-112G | 800G 规模放量、1.6T 2026 量产拐点（H1 主力上行）；FR4（200G/400G 每通道）随 IEEE 802.3dj 定稿起量；400G 传统云负载仍高量；LPO 去 DSP 降功耗成重要路径 |
| WDM 解复用 | 8CH / 40CH DWDM / 100G LR4（LAN-WDM） | 数据中心波分复用、C 波段 ITU 网格、10km 长距（5G 前传/城域）需求 |
| CPO / OCS | CPO-WDM5 / CPO-OCS | NVIDIA/谷歌押注，2026 量产拐点 |
| 可重构互连 | 1×8 光开关 OSW（OCS/dOCS 趋势） | Cignal AI 估 OCS 市场 2029 ≥$25 亿；LightCounting 估 Scale-Up 光互连 2027 规模商用；AI 超节点拓扑实时重构 |
| 接入网 | FTTH PLC 1×8 / 1×16 / 50G-PON | PON 无源分光量大面广；50G-PON（ITU-T G.9804）2026 商用启航（工信部 136 试点验收），万兆光网主航道 |
| 传感 | 微环 RING / MZI / FMCW LIDAR TX+RX / 环形生物传感 | 生物化学折射率感测、激光雷达（发射+接收配套）、Lab-on-Chip 即时检测 |
| 相干收发 | 400G ZR/ZR+ 相干（IM-COHERENT-400ZR） | OIF 800ZR IA 2024-11、IEEE 802.3dj 1600ZR 2026 中；ZR+ 相干模块市场 $18.4亿→$21.9亿（CAGR 18.9%），800ZR/ZR+ 2026 大规模部署 |
| 微环调制 | 微环调制器 MRM（IM-RING-MOD） | NVIDIA CPO 采用 MRM（带宽密度 >1 Tbps/mm）；TSMC COUPE 2026 量产 200Gbps/lane MRM；Ayar/NewPhotonics 无热 MRM（OFC 2026） |
| 接入网 | FTTH PLC 1×8 / 1×16 / 50G-PON / XGS-PON | PON 无源分光量大面广；50G-PON（G.9804）与 XGS-PON（G.9807.1 10G 对称）双线并进，XGS-PON 占 PON 市场 15%→55%、中国 10G PON 端口 3286 万 |
| ROADM 光层 | 1×9 WSS（IM-WSS-1X9）/ VOA（IM-VOA） | WSS $1.8B→$4.76B（CAGR 11.4%）、支撑 400G/800G/1.6T 相干；VOA $380M→$551.7M（CAGR 5.4%）、>70% 光网络用动态衰减（功率均衡） |
| 先进封装 | 光 Chiplet IO | XPU 光 IO、异质集成趋势 |
| 异质集成 | 片上激光集成 LASER-INT | 硅光缺光源，III-V 异质集成热点 |
| 调制器 | 马赫-曾德尔调制器 MZM（IM-MZI-MOD） | 硅 MZM 市场 $1.51B(2025)→$7.24B(2034) CAGR 19.0%；Tower Semiconductor+Coherent（2026-03）400 Gbps/lane 硅 MZM 量产就绪；200+ GHz 带宽、sub-0.5 dB 插损；硅 MZM 占 2025 MZM 市场 45.8% |
| 偏振路由 | 偏振分束旋转器 PSR（IM-PSR） | Sama et al. Optics and Laser Technology 2026 vol 203，高隔离 PSR（SOI 220nm+70nm 部分刻蚀），TM-to-TE 损耗 0.71 dB @1550nm、PER 最差 30.95 dB；偏振分束器市场 $1.2-1.5B(2025)→$2.2-3.2B(2035) CAGR 7-9% |
| CPO 2.5D | 光子中介层 / 共封装（IM-PHOTONIC-INTERPOSER） | IDTechEx 预测 CPO 市场 2036 破 $20B、CAGR 37%；TSMC COUPE 2026-04 量产；NVIDIA Quantum-X/Spectrum-X Photonics CPO 2026 出货；Ayar Labs TeraPHY $500M E 轮 2026-03；2.5D 硅中介层+TSV 路径 |
| 光计算 | 光神经网络 ONN（IM-OPTO-COMPUTE） | 光神经网络处理器市场 Lightmatter/Lightelligence/Celestial AI/Intel/Ayar Labs 占 56.3%；北美光子神经形态芯片 $180-240M(2026) CAGR 32-38%；Lightmatter 1.2 petaflops 模拟 ONN、Lightelligence 8.3 pJ/op |
| 医疗成像 | 光学相干层析 OCT（IM-OCT） | OCT 市场 $2.36B(2026)→$4.01B(2032) CAGR 9.08%；眼科 OCT $1.52B(2025)→$2.52B(2032) CAGR 6.49%；糖尿病视网膜病变+AMD 驱动 |
| 固态感知 | 光学相控阵 LiDAR（IM-OPA-LIDAR） | OPA LiDAR $1.8B(2025)→$9.6B(2034) CAGR 20.4%；单芯片集成 OPA 占 63.7%；Yole：车规原型 12 家、2026 乘用车前装渗透率破 5%；CMOS 兼容硅光波导型 OPA |
| 相干接收 | 90° 光混频器（IM-COHERENT-RX） | Optical Hybrid $483M(2025)→$1.10B(2032) CAGR 12.48%；90° 混频占 67.3%；400G/800G/1.6T 相干可插拔驱动、SiPh+InP 集成 |
| 片上光互连 | 光网络 NoC / 芯片光 I/O（IM-ONCHIP-NOC） | Chiplet 互连光子 $1.8B(2025)→$52.1B(2034) CAGR 38.5%；光互连 $13.69B→$15.28B(2026) CAGR 11.6%→$23.54B(2030)；Ayar TeraPHY 8Tbps、Intel 光 I/O 4Tbps/5pJ/bit |
| 空分复用 | 多芯光纤扇出（IM-MCF-FANOUT） | MCF Fanouts $640M(2025)→$1.25B(2032) CAGR 11.8%；OFC 2026 SDM4 MCF MSA（Corning/AFL/Sumitomo）4 芯；TPU 首条商用 MCF 2025-2026 |
| 惯性传感 | 光纤陀螺 Sagnac（IM-OPTICAL-GYRO） | FOG $1.2B(2026)→$2.0B(2033) CAGR 7.5%；干涉型（Sagnac）占 78%；GNSS 拒止 + 国防现代化驱动 |
| 光滤波 | 微环谐振滤波器 add-drop（IM-MRR-FILTER） | Silicon Microring Resonators $450M(2025)→$1.66B(2032) CAGR 20.5%；Microring Filter Array $41.58M→$245M CAGR 27.8%；add-drop 占 55.5%；AI 集群 DWDM/CPO 阵列化 |
| 无源分配 | 1×N 功分树 PLC（IM-SPLITTER-TREE） | PLC Splitter $2.8B(2025)→$5.6B(2034) CAGR 8.1%；1×N 占 62.4%；FTTR/XGS-PON 推升 1×32+ 高通道数 |
| 微波光子 | 真延时 TTD 波束成形（IM-TRUE-TIME-DELAY） | Phased Array Antenna $3.90B(2026)→$8.38B(2034) CAGR 10.04%；相控阵系统 $18.7B→$38.5B CAGR 12.8%；MWP 真延时用于相控阵雷达/5G-A |
| 环境/医疗 | 波导气体吸收光谱（IM-GAS-SENSE） | SiN PIC $320M(2025)→$1113.58M(2032) CAGR 19.5%；SiN 宽透明窗口；VOC 中红外检测灵敏度较 Si 提升 5× |
| 封装接口 | 光栅耦合阵列 CPO 光 IO（IM-GRATING-COUPLE） | Grating Coupler Array $1.45B(2024)→$3.07B(2033) CAGR 8.7%；耦合效率 >90%；CPO 共封装光学量产拉动 |

**开放策略**：上述光子主流方向全量开放（45 个货架），覆盖预研企业最密集的需求面，含 FR4 200G/400G 每通道、400G DR4、100G LR4、50G-PON、XGS-PON、可重构光交换、FMCW 接收、环形生物传感、相干 ZR、微环调制器、WSS、VOA、MZM、PSR、光子中介层/CPO、光计算 ONN、OCT、OPA LiDAR、相干接收、片上光互连、多芯光纤扇出、光纤陀螺、微环谐振滤波、1×N 功分树、微波光子真延时、波导气体传感、光栅耦合阵列等真实缺口品类。

## 三、量子赛道（高价值、暂列咨询制）

| 方向 | 代表货架 | 判断 |
|---|---|---|
| 量子通信 | QKD 发射/接收/多用户 ×3 | 国内战略刚需，但属量子技术，跨境受 EAR 管控；国内可售、出海需法律评估 |
| 量子保真度链 | 祖冲之三号/IBM Heron/Google Willow 量级 ×5 | 当前货架 composition 仅无源（GP-YBRANCH/GP-SIN-PL），量子部分靠死锚仿真复现；诚实可交付但**非真量子 EDA** |

**开放策略**：量子类 8 个货架**暂列"咨询制 / 即将开放"**，不进自动下载白名单。原因：① 出口管制合规红线；② 受众小、需更强诚实标注；③ 当前交付物为无源互联 + 仿真报告，待 C 阶段（真实量子 PDK 外联）后再升级为合格设计包。

## 四、客户痛点（我们切中的缝隙）

| 痛点 | 数据 | 对 LDA 的意义 |
|---|---|---|
| 商业 EDA 贵 | 单座许可 **$15k–$45k/年**，企业套件 **>$500k/年** | 我们的设计包定价几百–几万/单次，1/10–1/100 |
| 采购门槛高 | 62% 光子初创视软件费为主要瓶颈；68% 因互操作性延迟采购 | 免费开源引擎引流 + 轻量付费包降低首单决策 |
| 人才稀缺 | 全球光子工程师 **<1.5 万**，73% 在大厂/学术；68% 初创依赖 $300–500/小时顾问 | 设计就绪包 = "开箱即用"，绕开人才缺口 |
| PDK 缺 | 新进入者需 12–18 月 + $2–5M 逆向工程 foundry 行为 | 我们诚实标注"主权近似 + 公开标准"，不冒充 foundry 认证 |
| 流片贵 | 重复流片时间与资金成本高 | 高保真可验证设计降低原型迭代风险 |

## 五、竞争格局与差异化

- **商业巨头**：Synopsys（PIC EDA 29.4%）、Ansys/Lumerical（18.7%）、Luceda IPKISS（9.3%）—— 贵、绑定 foundry PDK。
- **开源挑战者**：IPKISS、MIT Photonic Bands 以免费层切入口，但企业支持付费。
- **LDA 差异化 = 护城河一致**：开源引擎（免费、对标求解器）+ 付费「设计就绪包」（可溯源、可验证、死锚比对、非黑箱）。不是卖软件，是卖**经验证的设计交付物**。

## 六、定价与变现印证

- 行业趋势：光子软件收入 2026 年 **55% 来自分层/定制定价**（2023 仅 35%）；量子软件订阅制占比 38%→54%（2024→2026）。
- 对齐我们 T1–T4 阶梯：T1 单器件破冰（¥199–399）、T2 无源链路（¥2–5k）、T3 系统级/量子（¥7k–2w）、T4 定制/PDK 适配（询价）。价值导向、模块化，与行业同向。

## 七、风险与边界（持续守）

1. **出口管制**：量子类跨境受 EAR 管控，国内可售、出海前必须过法律评估。
2. **诚实层级**：所有包 `design_ready（预研级）`，附 HONESTY.md —— 非 foundry 认证、非本团队流片、主权近似 + 公开标准。这是信任资产，不是负担。
3. **叙事一致**：开源引擎 vs 付费设计，不可混淆为"卖软件"。
4. **质量底线**：开放货架须能由 ship_package 干净出包（GP-* 映射 + DRC + 死锚报告），任意无锚基元不强行新增。

---
*分析日期：2026-08-28 · 检索源：LightCounting、Yole Group、HDIN Research、Dataintelo、IIM、格隆汇、东方财富、arXiv 等公开资料。*
