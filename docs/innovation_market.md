# LDA 创新超市（Innovation Marketplace）· 前瞻预研货架目录

> 生成口径：每个货架 = 已锚定基元（产品级基准库 GP-*）+ 公开信号驱动的**前瞻预研**预设计。
> **75/75 货架通过结构可行 + 系统预算不破检查**。

**诚实边界（红线下护栏）**：
> 创新超市货架为**前瞻预研**预设计：组合已锚定基元（产品级基准库 GP-*）+ 公开信号驱动（行业 roadmap / 标准草案 / 厂商公开动向）。属等效验证（复用已锚定基元 + 系统预算不破），**非本团队流片验证**、**非对未来的承诺**。信号源可溯源；判决复用 system_type 已验证闭环，LLM 不进判决路径。
> - 货架仅由**已锚定基元**组装（组合创新），禁止含未锚定基元；
> - 判决复用 system_type 已验证闭环（B4 / D-46×D-47），LLM 不进判决路径；
> - 属等效验证（复用已锚定基元 + 系统预算不破），**非本团队流片验证**、**非对未来的承诺**。

## 货架明细

| 货架 ID | 标题 | 目标应用 | system_type | 已锚定基元 | 结构可行 |
|---|---|---|---|---|---|
| IM-CPO-WDM5 | CPO 多通道 WDM 共封装光模块预设计（5 通道基准） | 共封装光学（CPO）/ 数据中心光互连，单光纤多波长并行 | wdm_demux | GP-GRATING-EFF, GP-MMI-1X2, GP-CROSSING | OK |
| IM-QCHIP-INT | 量子芯片间读出互联模板（多比特保真度链） | 超导量子芯片读出总线 / 多比特频率复用读出链 | quantum_fidelity | GP-YBRANCH, GP-SIN-PL | OK |
| IM-SENSE-RING | 微环折射率传感前端预设计（复用光链路拓扑） | 生物/化学折射率传感、光纤传感前端、实验室芯片（LoC）片上传感 | link | GP-GRATING-EFF, GP-SIN-PL | OK |
| IM-LASER-INT | 片上激光源集成发射模板（异质集成黑箱源 + 已锚定无源网） | 共封装光模块发射端、硅光异质集成光源、片上收发前端 | link | GP-GRATING-EFF, GP-SIN-PL | OK |
| IM-QCOM-LINK | 量子计算频率复用读出链路（5 比特保真度链） | 超导量子计算多比特频率复用读出、量子处理器读出总线 | quantum_fidelity | GP-YBRANCH, GP-SIN-PL | OK |
| IM-800G-DR8 | 800G DR8 硅光发射引擎预设计（8×100G PAM4） | AI 数据中心 800G 光互连、1.6T DR8 前代平台 | link | GP-GRATING-EFF, GP-SIN-PL, GP-CROSSING | OK |
| IM-WDM-8CH-1D | 8 通道 CWDM/DWDM 解复用前端预设计（8×λ） | 800G FR8/LR8 类 WDM 模块解复用端、DWDM 城域前传 | wdm_demux | GP-GRATING-EFF, GP-MMI-1X2, GP-SIN-PL | OK |
| IM-DWDM-40CH | 40 通道 DWDM 阵列解复用预设计（C 波段 100GHz ITU 网格） | DWDM 城域/骨干、40ch 无热 AWG 替代方案、波长路由 | wdm_demux | GP-GRATING-EFF, GP-MMI-1X2, GP-SIN-PL | OK |
| IM-FTTH-PLC8 | FTTH 1×8 PLC 分光预设计（PON 无源分光网） | GPON/XGS-PON 光分配网（ODN）、楼宇/园区 FTTH 部署 | link | GP-YBRANCH, GP-SIN-PL | OK |
| IM-FTTH-PLC16 | FTTH 1×16 PLC 分光预设计（高密度分光） | 高密度 FTTH/FTTB、MDU 多住户单元部署 | link | GP-YBRANCH, GP-SIN-PL | OK |
| IM-CPO-OCS | OCS 直连光交换前端预设计（收发 + 交换矩阵黑箱） | AI 集群 OCS 直连（Google Jupiter/Palomar 类架构）、CPO+OCS 混合互连 | link | GP-GRATING-EFF, GP-SIN-PL | OK |
| IM-LIDAR-TX | FMCW 激光雷达发射前端预设计（1550nm 相干探测） | 汽车/机器人 4D 感知、OPA 固态扫描 FMCW LiDAR | link | GP-GRATING-EFF, GP-SIN-PL | OK |
| IM-QKD-TX-SHELF | QKD 发射端货架（Alice BB84 态制备） | 量子密钥分发网络发射端、城际 QKD 干线 | link | GP-GRATING-EFF, GP-YBRANCH, GP-SIN-PL | OK |
| IM-QKD-RX-SHELF | QKD 接收端货架（Bob 基矢测量） | 量子密钥分发网络接收端、MDI-QKD 不信节点 | link | GP-GRATING-EFF, GP-CROSSING, GP-SIN-PL | OK |
| IM-QKD-MULTI4 | 多用户 QKD 接收机货架（4 用户选路） | 量子密钥分发接入网、多用户 QKD 星形分发 | link | GP-GRATING-EFF, GP-SIN-PL | OK |
| IM-SENS-MZI | MZI 干涉传感前端货架（生物化学折射率感测） | 生物/化学传感、Lab-on-Chip 干涉检测、环境监测 | link | GP-GRATING-EFF, GP-YBRANCH, GP-SIN-PL | OK |
| IM-CHIPLET-IO | 光 chiplet 互连前端货架（XPU 光 IO） | AI 加速器光互连、CPO XPU attach、chiplet 间光 IO | link | GP-GRATING-EFF, GP-SIN-PL, GP-CROSSING | OK |
| IM-QCTRL-ZC3-10Q | 10 比特频率复用读出链货架（祖冲之三号量级） | 超导量子处理器读出总线、中等规模 NISQ 读出扩展 | quantum_fidelity | GP-YBRANCH, GP-SIN-PL | OK |
| IM-QCTRL-HERON-16Q | 16 比特频率复用读出链货架（IBM Heron R2 量级） | 超导量子处理器读出总线、heavy-hex 架构读出段 | quantum_fidelity | GP-YBRANCH, GP-SIN-PL | OK |
| IM-QCTRL-WILLOW-12Q | 12 比特频率复用读出链货架（Google Willow 量级） | 超导量子处理器读出总线、QEC 码字读出段（Willow 类架构） | quantum_fidelity | GP-YBRANCH, GP-SIN-PL | OK |
| IM-PSM4-SHELF | 100G PSM4 硅光收发前端预设计（4×25G，500m SMF） | 100G PSM4 数据中心光模块、边缘耦合低损并行光互连 | link | GP-GRATING-EFF, GP-SIN-PL, GP-CROSSING | OK |
| IM-FR4-SHELF | 400G FR4 硅光收发前端预设计（4×100G PAM4，2km） | 400G FR4 数据中心光模块、中距（2km）光互连 | link | GP-GRATING-EFF, GP-SIN-PL | OK |
| IM-CWDM4-SHELF | 100G CWDM4 解复用前端预设计（4×25G，2km） | 100G CWDM4 数据中心光模块、粗波分短距互连 | wdm_demux | GP-GRATING-EFF, GP-MMI-1X2, GP-SIN-PL | OK |
| IM-LPO-112G | LPO 线性直驱光模块前端预设计（112G 单通道） | Linear Pluggable Optics（LPO）112G/通道 短距线性直驱互连、AI 机柜内光互连 | link | GP-GRATING-EFF, GP-SIN-PL | OK |
| IM-1.6T-DR8 | 1.6T DR8 硅光发射引擎预设计（16×100G PAM4） | 1.6T DR8 数据中心光模块、AI 集群 scale-out 互连（16×100G PAM4） | link | GP-GRATING-EFF, GP-SIN-PL, GP-CROSSING | OK |
| IM-800G-FR4 | 800G FR4 硅光收发前端预设计（4×200G PAM4，2km） | 800G FR4 数据中心光模块、中距（2km）AI 互连（200G 每通道） | link | GP-GRATING-EFF, GP-SIN-PL, GP-CROSSING | OK |
| IM-1.6T-FR4 | 1.6T FR4 硅光发射引擎预设计（4×400G PAM4） | 1.6T FR4 数据中心光模块、AI 集群 scale-out 互连（400G 每通道） | link | GP-GRATING-EFF, GP-SIN-PL, GP-CROSSING | OK |
| IM-400G-DR4 | 400G DR4 硅光收发前端预设计（4×100G PAM4，500m） | 400G DR4 数据中心光模块、短距（500m SMF）并行光互连 | link | GP-GRATING-EFF, GP-SIN-PL, GP-CROSSING | OK |
| IM-100G-LR4 | 100G LR4 解复用前端预设计（4×25G LAN-WDM，10km） | 100G LR4 数据中心/城域/5G 前传光模块、长距（10km）粗波分 | wdm_demux | GP-GRATING-EFF, GP-MMI-1X2, GP-SIN-PL | OK |
| IM-PON-50G | 50G-PON 光前端预设计（OLT/ONU 无源网，ITU-T G.9804） | 50G-PON 万兆光网 OLT/ONU 光前端、下一代接入网（园区/工厂/小区） | link | GP-GRATING-EFF, GP-YBRANCH, GP-SIN-PL | OK |
| IM-OSW-1X8 | 1×8 可重构光开关前端预设计（OCS/dOCS 趋势） | 数据中心可重构光交换（OCS/dOCS）、AI 超节点拓扑实时重构、故障快速恢复 | link | GP-YBRANCH, GP-MMI-1X2, GP-SIN-PL | OK |
| IM-LIDAR-RX | FMCW 激光雷达相干接收前端预设计（90° 混频） | 汽车/机器人 4D 感知、FMCW LiDAR 相干接收（与 IM-LIDAR-TX 配套） | link | GP-GRATING-EFF, GP-SIN-PL, GP-CROSSING | OK |
| IM-BIOSENSE | 环形谐振生物/化学传感前端预设计（Lab-on-Chip） | 生物/化学折射率传感、Lab-on-Chip 干涉检测、医疗/环境即时检测（POCT） | link | GP-GRATING-EFF, GP-SIN-PL | OK |
| IM-COHERENT-400ZR | 400G ZR/ZR+ 相干收发前端预设计（DCI 120km，QSFP-DD/OSFP） | 数据中心互联（DCI）400G ZR/ZR+ 相干可插拔、城域相干传输 | link | GP-GRATING-EFF, GP-SIN-PL, GP-CROSSING | OK |
| IM-RING-MOD | 微环调制器（MRM）前端预设计（200Gbps/lane，CPO 高带宽密度） | 共封装光学（CPO）微环调制器、高密度硅光发射、AI 机柜内光互连 | link | GP-GRATING-EFF, GP-SIN-PL | OK |
| IM-XGS-PON | XGS-PON 光前端预设计（OLT/ONU 无源网，ITU-T G.9807.1，10G 对称） | XGS-PON 万兆对称光网 OLT/ONU 光前端、下一代接入网（园区/工厂/小区） | link | GP-GRATING-EFF, GP-YBRANCH, GP-SIN-PL | OK |
| IM-WSS-1X9 | 1×9 波长选择开关（WSS）前端预设计（ROADM 波长路由） | 可重构光分插复用（ROADM）波长选择开关、城域/骨干波长路由与功率均衡 | link | GP-GRATING-EFF, GP-MMI-1X2, GP-SIN-PL | OK |
| IM-VOA | 可变光衰减器（VOA）前端预设计（ROADM 功率均衡） | 可重构光网络动态功率均衡、ROADM 通道衰减、测试仪表可调衰减 | link | GP-GRATING-EFF, GP-SIN-PL | OK |
| IM-MZI-MOD | 马赫-曾德尔调制器（MZM）前端预设计（相干/直检发射） | 高速光发射机调制前端、相干 400ZR/800ZR 调制器、硅光收发共封装调制核 | link | GP-GRATING-EFF, GP-MMI-1X2, GP-SIN-PL | OK |
| IM-PSR | 偏振分束旋转器（PSR）前端预设计（TE/TM 复用） | 硅光收发器偏振解复用、CPO 前端偏振路由、片上偏振复用链路 | link | GP-GRATING-EFF, GP-YBRANCH, GP-SIN-PL | OK |
| IM-PHOTONIC-INTERPOSER | 光子中介层/共封装（CPO）前端预设计（2.5D 光互连） | CPU/GPU 共封装光互连、2.5D 硅中介层光路由面、chiplet 间光 I/O 背板 | link | GP-GRATING-EFF, GP-MMI-1X2, GP-CROSSING, GP-YBRANCH, GP-SIN-PL | OK |
| IM-OPTO-COMPUTE | 光计算/光神经网络（ONN）前端预设计（模拟矩阵乘） | 光神经网络推理加速、模拟矩阵-向量乘前端、光互连-计算混合芯片 | link | GP-MMI-1X2, GP-CROSSING, GP-SIN-PL | OK |
| IM-OCT | 光学相干层析（OCT）前端预设计（医疗成像干涉仪） | 眼科 OCT 成像干涉前端、医疗诊断光相干层析、工业无损检测 | link | GP-GRATING-EFF, GP-MMI-1X2, GP-YBRANCH, GP-SIN-PL | OK |
| IM-OPA-LIDAR | 光学相控阵（OPA）固态激光雷达前端预设计（无惯量大角度光束扫描） | 固态 LiDAR 光束赋形发射阵、ADAS/机器人无机械扫描感知、芯片化波导 OPA | link | GP-GRATING-EFF, GP-YBRANCH, GP-SIN-PL, GP-CROSSING | OK |
| IM-COHERENT-RX | 相干接收机（90° 光混频器）前端预设计（相干探测本振耦合） | 400G/800G/1.6T 相干接收 90° 混频前端、本振-信号干涉耦合、相干探测 | link | GP-GRATING-EFF, GP-MMI-1X2, GP-SIN-PL | OK |
| IM-ONCHIP-NOC | 片上光网络（ONoC）路由前端预设计（chiplet 光互连 fabric） | AI 加速器/CPU-GPU chiplet 片上光互连、低能耗高带宽 NoC 路由网格 | link | GP-CROSSING, GP-YBRANCH, GP-MMI-1X2, GP-SIN-PL | OK |
| IM-MCF-FANOUT | 多芯光纤扇出（MCF Fan-out）前端预设计（空分复用 SDM 过渡） | 多芯光纤（SDM）到单芯设备的无源扇出/扇入、AI 数据中心高密度互连 | link | GP-GRATING-EFF, GP-YBRANCH, GP-SIN-PL | OK |
| IM-OPTICAL-GYRO | 光纤陀螺（FOG/Sagnac 干涉仪）前端预设计（高精度角速率传感） | 干涉型光纤陀螺 Sagnac 干涉前端、惯性导航/无人机/船舶 AHRS 角速率传感 | link | GP-GRATING-EFF, GP-CROSSING, GP-YBRANCH, GP-SIN-PL | OK |
| IM-MRR-FILTER | 微环谐振滤波器（可重构光滤波 / add-drop）前端预设计 | WDM 灵活栅格信道选择、ROADM 滤波、相干收发器波长滤波、微波光子窄带滤波 | link | GP-GRATING-EFF, GP-MMI-1X2, GP-SIN-PL | OK |
| IM-SPLITTER-TREE | 1×N 功分树（PLC 功分网络）前端预设计 | FTTH/FTTR 光分路、数据中心 fan-out、PON ODN 功率均分 | link | GP-YBRANCH, GP-MMI-1X2, GP-SIN-PL | OK |
| IM-TRUE-TIME-DELAY | 微波光子真延时（TTD）波束成形网络前端预设计 | 5G-A/6G 基站波束成形、相控阵雷达、卫星通信 TTD 延时网络 | link | GP-SIN-PL, GP-YBRANCH, GP-CROSSING | OK |
| IM-GAS-SENSE | 波导气体/吸收光谱传感前端预设计（SiN 宽波段） | 环境 VOC/温室气体监测、医疗呼气诊断、工业排放多 analyte 检测 | link | GP-SIN-PL, GP-GRATING-EFF, GP-YBRANCH | OK |
| IM-GRATING-COUPLE | 光栅耦合阵列 / 光纤贴装接口前端预设计（CPO 光 IO） | 硅光芯片-光纤阵列耦合、CPO 片上级联光 IO、多通道高密度封装接口 | link | GP-GRATING-EFF, GP-SIN-PL | OK |
| IM-AWG-DEMUX | 阵列波导光栅解复用器（AWG DeMUX）前端预设计 | DWDM 信道解复用、CPO/光模块波分合分波、ROADM 波长路由、光谱处理前端 | link | GP-MMI-1X2, GP-SIN-PL | OK |
| IM-ONCHIP-SPECTROMETER | 片上微型光谱仪（Chip-scale Spectrometer）前端预设计 | 便携式光谱检测、消费电子/医疗即时诊断、环境气体监测、工业过程光谱分析 | link | GP-MMI-1X2, GP-YBRANCH, GP-SIN-PL | OK |
| IM-MDM-MUX | 模分复用器（Mode-division Multiplexer）前端预设计 | 少模光纤 MDM 收发前端、数据中心空分复用扩容、单模 Shannon 极限突破、模群延时补偿 | link | GP-YBRANCH, GP-SIN-PL | OK |
| IM-OPTCOMB | 芯片级光频梳（Microcomb）前端预设计 | DWDM 多波长光源、时频同步、相干光通信梳状源、量子频率计量 | link | GP-GRATING-EFF, GP-SIN-PL | OK |
| IM-POL-ROTATOR | 片上偏振旋转器（Polarization Rotator）前端预设计 | 偏振分集接收、相干收发器偏振管理、硅光集成偏振操控、CPO 偏振耦合接口 | link | GP-CROSSING, GP-SIN-PL | OK |
| IM-3.2T-DR8 | 3.2T DR8 硅光收发前端预设计（8×400G PAM4） | AI 数据中心 3.2T 光模块、DR8 多通道并行互连、CPO 光引擎通道 | link | GP-GRATING-EFF, GP-SIN-PL | OK |
| IM-1.6T-LPO | 1.6T LPO 线性直驱光模块前端预设计（8×200G） | AI 数据中心 1.6T LPO 可插拔、线性直驱低功耗互连、交换机近封装 | link | GP-GRATING-EFF, GP-SIN-PL | OK |
| IM-1.6T-ZR | 1.6T 相干 ZR 光模块前端预设计（相干 400ZR/1.6ZR） | DCI 相干互连、1.6ZR 长距离传输、城域/骨干相干收发 | link | GP-GRATING-EFF, GP-SIN-PL | OK |
| IM-CPO-16CH | CPO 16 通道 WDM 光引擎前端预设计 | 共封装光学（CPO）16 通道 WDM 解复用、高密度片上光 IO、AI 交换机共封装 | wdm_demux | GP-MMI-1X2, GP-SIN-PL | OK |
| IM-UCIE-OPTICAL | UCIe-Optical 光 chiplet 互连前端预设计 | die-to-die 光互连、光 chiplet/ONoC、异构集成封装内光互连 | wdm_demux | GP-MMI-1X2, GP-SIN-PL | OK |
| IM-LIDAR-FULL | FMCW 固态激光雷达全前端预设计（TX+RX 一体） | 车载/机器人 FMCW 固态 LiDAR、光探测与测距全光前端、同轴 TX/RX | sensor_frontend | GP-GRATING-EFF, GP-YBRANCH, GP-SIN-PL | OK |
| IM-POC-BIOSENSE | POCT 生物/气体 Lab-on-Chip 传感前端预设计 | 即时诊断（POCT）生物传感、片上气体/化学传感、医疗即时检测微流控光路 | sensor_frontend | GP-GRATING-EFF, GP-YBRANCH, GP-SIN-PL | OK |
| IM-FTTR-PLC32 | 50G-PON / FTTR 32 路 PLC 分路前端预设计 | 家庭/企业全光组网（FTTR）、50G-PON 无源分光、接入网无源光分路 | sensor_frontend | GP-GRATING-EFF, GP-YBRANCH, GP-SIN-PL | OK |
| IM-TTD-5G | 微波光子真时延（TTD）波束成形前端预设计 | 5G/6G 毫米波波束成形、微波光子真时延、相控阵光控时延网络 | sensor_frontend | GP-GRATING-EFF, GP-YBRANCH, GP-SIN-PL | OK |
| IM-QKD-FULL-LINK | QKD 干线收发全链路前端预设计（BB84 态制备/测量） | 量子密钥分发（QKD）干线、城域/骨干量子保密通信、BB84 收发前端 | qkd_link | GP-GRATING-EFF, GP-SIN-PL | OK |
| IM-QCTRL-32Q | 32 量子比特读出控制芯片前端预设计 | 超导量子计算读出/控制、NISQ 规模扩展、多量子比特复用读出链 | quantum_fidelity | GP-YBRANCH, GP-SIN-PL | OK |
| IM-OPA-2D | 2D 光学相控阵（OPA）固态雷达前端预设计 | 固态激光雷达光束 steering、光通信光束成形、自由空间光互连波束控制 | link | GP-GRATING-EFF, GP-SIN-PL | OK |
| IM-OPTCOMB-WDM | WDM 锁定芯片级光频梳（DWDM-grid Microcomb）预设计 | DWDM 多波长相干源、WDM-PON 梳状光源、信道化射频光子学、量子频率梳分发 | link | GP-GRATING-EFF, GP-SIN-PL, GP-MMI-1X2 | OK |
| IM-CPO-OIO-8CH | CPO 硅光 I/O 光引擎预设计（8×200G = 1.6T，标准 250 µm 光纤阵列） | 共封装光学（CPO）光引擎 I/O、AI 交换机/XPU 光接口、51.2T+ 以太网与 InfiniBand 光互连 | cpo_optical_io | GP-GRATING-EFF, GP-SIN-PL, GP-YBRANCH | OK |
| IM-CPO-OIO-16CH | CPO 高密度光引擎预设计（16×200G = 3.2T，127 µm 细间距光纤阵列） | 3.2T/6.4T CPO 光引擎、超大规模 AI 集群 scale-up 光互连、高密光纤阵列（FAU）耦合 | cpo_optical_io | GP-GRATING-EFF, GP-SIN-PL, GP-YBRANCH | OK |
| IM-CPO-OIO-CHIPLET | chiplet 间光 I/O 预设计（UCIe-Optical 类，8×32G 光栅阵列直连，无光纤） | chiplet 间光互连（die-to-die 光 I/O）、UCIe-Optical 光桥、光 CXL/内存池化、AI 加速器分解式互连 | cpo_optical_io | GP-GRATING-EFF, GP-SIN-PL | OK |
| IM-CPO-ELS-FIBER | CPO 外置可更换激光源（ELS）+ 光纤 I/O 前端预设计（OIF 3.2T IA 类 8×400G） | CPO 可维护性方案（前面板可更换光源）、OIF 3.2T 光引擎、NPO/CPO 混合演进、规避「光器件故障导致整交换机报废」的运维痛点 | cpo_optical_io | GP-GRATING-EFF, GP-SIN-PL, GP-YBRANCH, GP-CROSSING | OK |

## 货架设计说明（诚实标注）

- **IM-CPO-WDM5**：面向 8 通道 CPO 的预研货架；以 5ch@2.0nm 单 FSR 闭环（B4：drop IL≤3 / XT≥15 / 单 FSR 防混叠）验证基元可行性。8 通道扩展需 FSR 扩展（更小环 R）属参数化下一迭代，不破现有已验证闭环。
- **IM-QCHIP-INT**：4 比特频率复用读出链（D-46 复用 + D-47 保真度，已验证闭环）。基元复用 Y-branch（分束）+ SiN 低损波导（量子光路互联）。
- **IM-SENSE-RING**：环谐振器作折射率传感单元，复用 link 拓扑（激光→grating→SiN 波导→ring→探测器）+ 系统预算锚 S1/S2/S5/S7。基元复用 grating coupler（GP-GRATING-EFF）+ SiN 低损波导（GP-SIN-PL）。传感灵敏度由环 Q / 波长偏移换算，属参数化下一迭代，不破现有已验证闭环。
- **IM-LASER-INT**：激光源作为**异质集成黑箱源**（有源器件不物理级建模——负面清单：有源不物理级建模，行为黑箱 + 文献锚走完闭环），本货架组合其余已锚定基元：grating coupler（GP-GRATING-EFF）+ SiN 低损波导（GP-SIN-PL）。判决复用 link 系统预算锚 S1/S2/S5/S7（死标量，LLM 不进路径）。激光源本身**非本团队新锚定器件**——如要将其纳入锚集，须先按 v0.8.32 方式新增 golden 基准（待发动期/社区贡献）；本货架严守『组合创新、不新增未锚定基元』。
- **IM-QCOM-LINK**：5 比特频率复用读出链（D-46 复用 + D-47 保真度，已验证闭环）。基元复用Y-branch（分束，GP-YBRANCH）+ SiN 低损波导（GP-SIN-PL，量子光路互联）。与 IM-QCHIP-INT（4 比特）互补，演示库随比特数扩展仍零新物理。
- **IM-800G-DR8**：8×100G 并行单波长方案（DR8）：每通道 = 光栅 + 2cm SiN + crossing，链路预算锚 S1/S2/S5/S7 死标量判决。对标 GC-DR4-TX/ONCHIP 公开规格量级。
- **IM-WDM-8CH-1D**：8 通道解复用：wdm_demux 闭环（B4：drop IL≤3 / XT≥15 / 单 FSR / DRC）。对标 LR8 信道预算 6.3 dB（GC-LR8-CH 同源公开标准）。
- **IM-DWDM-40CH**：40 通道 DWDM 解复用：wdm_demux 闭环（B4 锚）演示大规模波长数扩展。对标 GC-AWG-40CH（商用 AWG datasheet 6.0 dB 死标量）。
- **IM-FTTH-PLC8**：1×8 = 3 级 Y-branch 级联 + SiN 波导；对标 GC-PLC-1X8（G.671 死标量）。PON 上行突发时序按黑箱，判决只认链路预算锚 S1/S2/S5/S7。
- **IM-FTTH-PLC16**：1×16 = 4 级 Y-branch 级联；对标 GC-PLC-1X16（G.671 死标量）。
- **IM-CPO-OCS**：OCS 收发前端：光栅 + SiN 波导，交换矩阵/MEMS 按黑箱（非片上器件）。对标 GC-OCS-FABRIC（2×FR4 预算 4.0 dB 公开死标量）。
- **IM-LIDAR-TX**：FMCW 发射前端：光栅 + 0.5cm SiN（相干混频/OPA 按黑箱）。对标 GC-LIDAR-FMCW（OE 2026 实测 3.3 dB 死标量）。
- **IM-QKD-TX-SHELF**：Alice 态制备 = 2×光栅 + 2×Y-branch（MZI）+ SiN；单光子衰减/调制按黑箱。对标 GC-QKD-TX（npj QI 实测 15 dB 死标量）。
- **IM-QKD-RX-SHELF**：Bob 基矢测量 = 2×光栅 + crossing + SiN；单光子探测器按黑箱。对标 GC-QKD-RX（npj QI 实测 8 dB 死标量）。
- **IM-QKD-MULTI4**：4 用户接收 = 3×光栅 + 5cm SiN（MZI 选路按黑箱）；SPD 按黑箱。判决用标准链路余量锚 S1/S2/S5/S7（要求 3 dB）；整芯片 13 dB 总插损对标见 GC-QKD-MULTI（OE 2020 实测死标量）。
- **IM-SENS-MZI**：MZI 传感 = 2×光栅 + 2×Y-branch（分/合束）+ 2cm SiN 双臂；传感元件按黑箱。判决用标准链路余量锚 S1/S2/S5/S7（要求 3 dB）；整芯片全链路 ≤15 dB 预算对标见 GC-SENSE（公开传感链路预算区间）。
- **IM-CHIPLET-IO**：XPU 光 IO 前端 = 光栅 + SiN + crossing（EIC/PIC 键合按黑箱）。对标 GC-CPO-8CH 同源（CPO 每通道 6–12 dB 公开区间）。
- **IM-QCTRL-ZC3-10Q**：10 比特复用读出链（D-46 复用 + D-47 保真度）。对标 GC-QCTRL-ZC3（公开 99.18% 死标量），演示读出链规模扩展零新物理。
- **IM-QCTRL-HERON-16Q**：16 比特复用读出链；对标 GC-QCTRL-HERON（公开 98.5% 死标量）。156 比特整芯片按 heavy-hex 分段，本货架为单段代表。
- **IM-QCTRL-WILLOW-12Q**：12 比特复用读出链；对标 GC-QCTRL-WILLOW（公开 99.33% 死标量）。JPA 放大链按黑箱（有源不物理级建模，负面清单）。
- **IM-PSM4-SHELF**：PSM4 单通道 = 光栅 + 2cm SiN（边缘耦合低损）+ crossing；链路预算锚 S1/S2/S5/S7 死标量判决。对标 GC-PSM4-CH（IEEE 802.3bm 4.0 dB 死标量）。
- **IM-FR4-SHELF**：FR4 单通道 = 光栅 + 1cm SiN；WDM 复用/串行器按黑箱（非片上器件），判决复用 link 系统预算锚死标量。对标 GC-FR4-CH（IEEE 802.3bs 4.5 dB 死标量）。
- **IM-CWDM4-SHELF**：4 通道 CWDM 解复用：wdm_demux 闭环（B4：drop IL≤3 / XT≥15 / 单 FSR / DRC）。对标 GC-CWDM4-CH（CWDM-MSA 4.0 dB 死标量）。
- **IM-LPO-112G**：LPO 线性直驱前端 = 光栅 + SiN 波导（去 DSP 后链路裕度收窄，链路预算锚 S1/S2/S5/S7 死标量判决）；无量级新物理，复用已锚定基元。对标公开 LPO 链路预算量级。
- **IM-1.6T-DR8**：1.6T DR8 = 800G DR8 的 16 通道扩展（composition 同源 GP-*），复用已锚定无源网 + 光栅耦合死标量；无量级新物理。对标公开 1.6T DR8 链路预算量级。
- **IM-800G-FR4**：800G FR4 = 4×200G PAM4 并行（与 800G DR8 同源无源网 + 光栅耦合，composition 同源 GP-*）；200G/lane DSP+SiPh 2026 成熟。对标公开 800G FR4 链路预算量级（单通道 ≤4.5 dB 量级）。
- **IM-1.6T-FR4**：1.6T FR4 = 1.6T DR8 的 4×400G 变体（composition 同源 GP-*），复用已锚定无源网 + 光栅耦合死标量；无量级新物理。对标公开 1.6T FR4 链路预算量级。
- **IM-400G-DR4**：400G DR4 = 4×100G 并行单波长（与 800G DR8 同源无源网 + 光栅耦合，composition 同源 GP-*）；链路预算锚 S1/S2/S5/S7 死标量判决。对标 IEEE 802.3bs 400G DR4 单通道 4.0 dB 量级。
- **IM-100G-LR4**：4 通道 LAN-WDM 解复用：wdm_demux 闭环（B4：drop IL≤3 / XT≥15 / 单 FSR / DRC）。与 CWDM4-SHELF 同属 4ch 解复用前端，但面向 10km 长距 LAN-WDM（vs CWDM4 2km）。对标 IEEE 802.3cu 100G LR4 单通道 4.5 dB 量级。
- **IM-PON-50G**：50G-PON 光前端 = 光栅耦合 + Y-branch 分束 + SiN 波导（OLT 发射/ONU 接收无源网）。PIC 自身 IL 预算 6 dB；整系统 29/32 dB 功率预算由 ODN 1:64 分光主导（黑箱，非片上器件），判决复用 link 系统预算锚 S1/S2/S5/S7。对标 G.9804 死标量量级。
- **IM-OSW-1X8**：1×8 光开关无源前端 = Y-branch/MMI 分束 + SiN 波导；MZI 热光开关矩阵按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。对标公开 SiPh MZI 矩阵开关 0.5 dB/级量级。
- **IM-LIDAR-RX**：FMCW 相干接收前端 = 光栅 + 0.5cm SiN + crossing（90° 混频/平衡探测按黑箱）。与 IM-LIDAR-TX 同源无源网，链路预算锚 3.3 dB（OE 2026 实测死标量）。
- **IM-BIOSENSE**：环谐振生物传感前端 = 光栅 + 1cm SiN（环形谐振腔传感单元，复用 SENSE-RING 拓扑）。传感灵敏度由环 Q / 波长偏移换算，属参数化下一迭代；判决复用 link 系统预算锚。
- **IM-COHERENT-400ZR**：400G ZR/ZR+ 相干收发 PIC 前端 = 光栅耦合 + 1cm SiN（低损）+ crossing；相干 DSP / IQ 调制器 / 平衡探测按黑箱（有源不物理级建模，负面清单）。PIC 自身 IL 预算 6 dB（非整系统 120km 链路，链路预算锚 S1/S2/S5/S7 死标量判决）。复用已锚定无源网 + 光栅耦合，无量级新物理。
- **IM-RING-MOD**：MRM 发射前端 = 光栅耦合 + 1cm SiN 波导；环形谐振调制单元（有源）按黑箱（有源不物理级建模，负面清单），其谐振/调制行为由文献锚走完闭环。判决复用 link 系统预算锚 S1/S2/S5/S7 死标量。复用已锚定无源网，无量级新物理。
- **IM-XGS-PON**：XGS-PON 光前端 = 光栅耦合 + Y-branch 分束 + SiN 波导（OLT 发射/ONU 接收无源网）。PIC 自身 IL 预算 6 dB；整系统功率预算由 ODN 1:64 分光主导（黑箱，非片上器件），判决复用 link 系统预算锚 S1/S2/S5/S7。对标 G.9807.1 量级（与 50G-PON 同族，速率 10G 对称）。
- **IM-WSS-1X9**：1×9 WSS 无源前端 = 光栅耦合 + MMI 分束 + SiN 波导；波长选择/切换矩阵（LCOS/MEMS）按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。复用已锚定无源网，无量级新物理。对标公开 ROADM WSS 量级。
- **IM-VOA**：VOA 前端 = 光栅耦合 + 1cm SiN 波导；可变衰减单元（MEMS/热光）按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚 S1/S2/S5/S7 死标量。复用已锚定无源网，无量级新物理。对标公开 VOA 量级。
- **IM-MZI-MOD**：MZM 前端 = 光栅耦合 + 1×2 MMI 分束（两相位臂）+ SiN 波导臂 + 1×2 MMI 合束（复用分束基元作合束）+ 光栅耦合出。电光调制相移单元按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚 S1/S2/S5/S7 死标量。复用已锚定无源网，无量级新物理。对标公开硅 MZM 量级。
- **IM-PSR**：PSR 前端 = 光栅耦合 + 非对称 Y 分支偏振路由 + SiN 波导；偏振旋转/耦合的亚波长结构按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。复用已锚定无源网，无量级新物理。对标公开 PSR 量级。
- **IM-PHOTONIC-INTERPOSER**：光子中介层前端 = 光栅阵列 I/O + MMI 扇出 + 交叉矩阵 + Y 分支 + SiN 波导面；TSV/微环驱动按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。复用已锚定无源网，无量级新物理。对标公开 CPO 光互连量级。
- **IM-OPTO-COMPUTE**：ONN 前端 = 1×2 MMI 分光权重分配 + 交叉干涉网格（MZI mesh）+ SiN 波导；相移/探测按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。复用已锚定无源网，无量级新物理。对标公开光计算量级。
- **IM-OCT**：OCT 前端 = 光栅耦合 + 1×2 MMI 分光（样品/参考臂）+ Y 分支 + SiN 波导干涉臂；扫描/探测按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。复用已锚定无源网，无量级新物理。对标公开 OCT 量级。
- **IM-OPA-LIDAR**：OPA 前端 = 光栅发射阵列 + Y 分支功分馈入阵元 + SiN 波导 + 交叉路由；相位调制单元按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。复用已锚定无源网，无量级新物理。对标公开 OPA LiDAR 量级。
- **IM-COHERENT-RX**：相干接收前端 = 光栅耦合（信号+本振双入）+ 1×2 MMI 4×4 混频（两 MMI 作分/合）+ SiN 波导；平衡探测按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。复用已锚定无源网，无量级新物理。对标公开相干接收量级。
- **IM-ONCHIP-NOC**：ONoC 前端 = 交叉矩阵（路由） + Y 分支功分 + 1×2 MMI + SiN 波导 fabric；调制/探测按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。复用已锚定无源网，无量级新物理。对标公开片上光互连量级。
- **IM-MCF-FANOUT**：MCF 扇出前端 = 光栅耦合阵列（多芯入） + Y 分支扇出到单芯 + SiN 波导；多芯对准按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。复用已锚定无源网，无量级新物理。对标公开 MCF 扇出量级。
- **IM-OPTICAL-GYRO**：FOG 前端 = 光栅耦合 + 交叉环形（Sagnac 环） + Y 分支分/合 + SiN 波导；光源/探测按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。复用已锚定无源网，无量级新物理。对标公开光纤陀螺量级。
- **IM-MRR-FILTER**：微环滤波前端 = 光栅耦合进/出 + 1×2 MMI 总线分光 + SiN 波导环形谐振（调谐/探测按黑箱，有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。复用已锚定无源网，无量级新物理。对标公开微环滤波器量级。
- **IM-SPLITTER-TREE**：功分树前端 = Y 分支级联 + 1×2 MMI 均分 + SiN 波导；纯无源功率分配（调制/探测按黑箱）。判决复用 link 系统预算锚死标量。复用已锚定无源网，无量级新物理。对标公开功分器量级。
- **IM-TRUE-TIME-DELAY**：TTD 前端 = 长 SiN 波导延迟线（不同长度阶梯） + Y 分支选择 + 交叉布线；RF 调制/探测按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。复用已锚定无源网，无量级新物理。对标公开微波光子 TTD 量级。
- **IM-GAS-SENSE**：气体传感前端 = SiN 长波导吸收臂 + 光栅耦合进/出 + Y 分支参考/样品臂；光源/探测按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。复用已锚定无源网，无量级新物理。对标公开波导气体传感量级。
- **IM-GRATING-COUPLE**：光栅耦合阵列前端 = 高效光栅耦合器（GP-GRATING-EFF 核心） + SiN 波导引出；光纤阵列对准/封装按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。复用已锚定无源网，无量级新物理。对标公开光栅耦合量级。
- **IM-AWG-DEMUX**：AWG 解复用前端 = 输入/输出 MMI 星形耦合器（GP-MMI-1X2 近似） + SiN 阵列波导（GP-SIN-PL 自由色散长度）；光源/探测按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。复用已锚定无源网，无量级新物理。对标公开 AWG DeMUX 量级。
- **IM-ONCHIP-SPECTROMETER**：片上光谱仪前端 = MMI 分光（GP-MMI-1X2） + Y 分支路由阵列（GP-YBRANCH） + SiN 波导色散/干涉臂（GP-SIN-PL）；探测器按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。复用已锚定无源网，无量级新物理。对标公开微型光谱仪量级。
- **IM-MDM-MUX**：模分复用前端 = 非对称 Y 分支模式合/分器（GP-YBRANCH 模式转换近似） + SiN 少模波导（GP-SIN-PL）；光源/探测按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。复用已锚定无源网，无量级新物理。对标公开 MDM 量级。
- **IM-OPTCOMB**：光频梳前端 = 高效光栅耦合 IO（GP-GRATING-EFF） + SiN 微环梳谐振波导（GP-SIN-PL，高 Q 色散工程）；泵浦/探测按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。复用已锚定无源网，无量级新物理。对标公开芯片级微梳量级。
- **IM-POL-ROTATOR**：偏振旋转器前端 = 波导交叉路由（GP-CROSSING） + SiN 双折射/非对称波导偏振旋转段（GP-SIN-PL）；光源/探测按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。复用已锚定无源网，无量级新物理。对标公开偏振旋转器量级。
- **IM-3.2T-DR8**：3.2T DR8 前端 = 高效光栅耦合阵列（GP-GRATING-EFF）+ SiN 波导引出（GP-SIN-PL）；8×400G PAM4 并行，调制器/激光器按黑箱（负面清单）。判决复用 link 系统预算锚死标量；复用已锚定无源网，无量级新物理。对标公开 DR8 量级。
- **IM-1.6T-LPO**：1.6T LPO 前端 = 高效光栅耦合（GP-GRATING-EFF）+ SiN 波导引出（GP-SIN-PL）；线性直驱省 retimer，调制器按黑箱。判决复用 link 系统预算锚死标量；复用已锚定无源网，无量级新物理。对标公开 LPO 量级。
- **IM-1.6T-ZR**：1.6T ZR 前端 = 高效光栅耦合（GP-GRATING-EFF）+ SiN 波导引出（GP-SIN-PL）；相干 DSP/调制器按黑箱。判决复用 link 系统预算锚死标量；复用已锚定无源网，无量级新物理。对标公开相干 ZR 量级。
- **IM-CPO-16CH**：CPO 16 通道 WDM 前端 = MMI 星形耦合（GP-MMI-1X2）+ SiN 阵列波导（GP-SIN-PL）；判决复用 wdm_demux 已验证闭环（B4 锚：drop IL≤3dB / XT≥15dB）。复用已锚定无源网，无量级新物理。对标公开 CPO WDM 量级。
- **IM-UCIE-OPTICAL**：UCIe-Optical 前端 = MMI 星形耦合（GP-MMI-1X2）+ SiN 波导（GP-SIN-PL）；判决复用 wdm_demux 已验证闭环（B4 锚）。复用已锚定无源网，无量级新物理。对标公开光 chiplet 互连量级。
- **IM-LIDAR-FULL**：FMCW LiDAR 全前端 = 光栅耦合（GP-GRATING-EFF）+ SiN 波导（GP-SIN-PL）+ Y-branch 路由（GP-YBRANCH）；OPA 扫描/相干混频按黑箱（负面清单）。判决复用 sensor_frontend 自带死标量锚 S1（预算）/S5（能量守恒下界·D-67）/S7（统计 p5）；复用已锚定无源网，无量级新物理。对标公开 FMCW LiDAR 链路量级。
- **IM-POC-BIOSENSE**：POCT 传感前端 = 光栅耦合（GP-GRATING-EFF）+ Y-branch 分/合束（GP-YBRANCH）+ SiN 波导传感臂（GP-SIN-PL）；传感元件按参数化黑箱（负面清单）。判决复用 sensor_frontend 自带死标量锚 S1/S5/S7；复用已锚定无源网，无量级新物理。对标公开传感链路预算量级。
- **IM-FTTR-PLC32**：FTTR 32 路 PLC = 5 级 Y-branch 级联（GP-YBRANCH，2^5=32 支路，含理想 5×3.01 dB 分光）+ SiN 波导（GP-SIN-PL）；判决复用 sensor_frontend 自带死标量锚 S1/S5/S7。复用已锚定无源网，无量级新物理。对标 ITU-T/G.671 公开规格。
- **IM-TTD-5G**：TTD 前端 = 光栅耦合（GP-GRATING-EFF）+ 2×crossing 时延路由（GP-SIN-PL 延迟线）+ SiN 波导（GP-SIN-PL）；电光调制按黑箱（负面清单）。判决复用 sensor_frontend 自带死标量锚 S1/S5/S7；复用已锚定无源网，无量级新物理。对标公开微波光子 TTD 链路量级。
- **IM-QKD-FULL-LINK**：QKD 干线收发前端 = 高效光栅耦合（GP-GRATING-EFF）+ SiN 波导引出（GP-SIN-PL）；QKD 本质是信息论安全问题，按物理诚实映射到 qkd_link 系统类型（decoy-BB84 安全密钥率锚 S-QKD-SKR），不冒用量子比特读出锚。判决复用 decoy-BB84 渐近下界（Lo–Ma–Chen 2005）已验证闭环，零新物理；含 Q-D67 护栏。对标公开 QKD 密钥率量级（等效验证）。
- **IM-QCTRL-32Q**：32-qubit 复用读出链 = Y-branch 路由（GP-YBRANCH）+ SiN 波导（GP-SIN-PL）读出网络；判决复用 quantum_fidelity 已验证闭环（D-46×D-47）。复用已锚定无源网，无量级新物理。对标公开超导量子系统读出保真度量级。
- **IM-OPA-2D**：OPA 2D 前端 = 高效光栅耦合（GP-GRATING-EFF）+ SiN 波导阵列（GP-SIN-PL）；OPA 是光波束控器件，按物理诚实映射到 link 系统类型（IL 基），不冒用量子比特读出锚。判决复用 link 系统预算锚死标量；复用已锚定无源网，无量级新物理。对标公开 OPA 光路量级。
- **IM-OPTCOMB-WDM**：WDM 锁定微梳 = 高效光栅耦合 IO（GP-GRATING-EFF） + SiN 高 Q 微环梳（GP-SIN-PL，色散工程 锁 ITU 网格） + MMI 分束复用（GP-MMI-1X2）；泵浦/探测/锁相环按黑箱（有源不物理级建模，负面清单）。判决复用 link 系统预算锚死标量。与 IM-OPTCOMB（通用微梳前端）区分：本货架专攻 WDM/ITU 网格锁定的多波长相干源，compositions 多纳入 MMI 复用，规格面向信道化 WDM。
- **IM-CPO-OIO-8CH**：CPO 光 I/O = 光栅耦合器阵列 IO（GP-GRATING-EFF）+ SiN 低损波导扇出（GP-SIN-PL）+ Y-branch 分光/监控支路（GP-YBRANCH）；判决走新系统类型 cpo_optical_io 三道死标量锚：每通道插损 S-CPO-IL（GP-* 级联，D-67 能量守恒下界护栏）+ 海岸线带宽密度 S-CPO-DENSITY（= 单通道速率/通道间距，P-CPO 间距几何下界护栏）+ 功率预算 S-CPO-BUDGET（S1 同式）。与 IM-CPO-WDM5（WDM 级联 B4 锚）/IM-CPO-16CH（通道数扩展）区分。EIC/驱动器/激光器按黑箱（有源不物理级建模，负面清单）。
- **IM-CPO-OIO-16CH**：把通道间距从 250 µm 压到 127 µm（标准光纤阵列细间距档）→ 总带宽 3.2 Tbps 而海岸线仅 2.03 mm，密度复现 1574.80 Gbps/mm。⚠️ 该复现值**已达 P-CPO 物理上界 1600 的 98.4%**（上界 = 200 Gbps / 125 µm G.652 包层直径）—— 再密就违反几何必然，护栏直接抛错拦截。本货架兼作 P-CPO 护栏的贴身回归用例。与 IM-CPO-16CH（既有，通道数扩展口径）区分。
- **IM-CPO-OIO-CHIPLET**：couple_mode=grating_array（片间光栅阵列**直连，无光纤**）⇒ P-CPO 间距物理下界由 G.652 包层直径 125 µm 换为**模场直径 MFD@1550 = 10.3 µm**，故 45 µm 间距合法。这验证 P-CPO 护栏**按耦合方式分档守下界**：一刀切用 125 µm 会误杀片间直连，放松到无下界则可虚报密度。片间短距无分束/交叉 → 插损仅 2×光栅耦合 + 0.2 cm 波导。与 IM-UCIE-OPTICAL（既有，电学接口标准口径）/IM-CHIPLET-IO（既有）区分。
- **IM-CPO-ELS-FIBER**：可维护性导向：把温度敏感的激光器外置为可现场更换模块（ELS/ELSFP），光经光纤送入CPO 引擎 ⇒ 光栅耦合 IO（GP-GRATING-EFF）+ SiN 波导（GP-SIN-PL）+ crossing 交叉（GP-CROSSING，ELS 光路与本地环路交汇）+ Y-branch 分光。8×400G = 3.2 Tbps 正对OIF 3.2T IA 光口配置，密度复现 1600 Gbps/mm（= 200G 档物理上界的 2 倍，因单通道速率翻倍，上界同步升至 3200）。与 IM-LASER-INT（片上异质集成光源黑箱）区分。

## 信号来源（可溯源）

- **IM-CPO-WDM5** · CPO 多通道 WDM 共封装光模块预设计（5 通道基准）：OIF CPO 2.0 共封装光学路线图（公开草案）；业界 8× 100G/200G WDM 硅光 CPO 模组量产前夕动向（公开报道）
- **IM-QCHIP-INT** · 量子芯片间读出互联模板（多比特保真度链）：量子计算多比特频率复用读出公开路线（IBM/Google 公开架构文档）；D-46×D-47 已验证保真度预算框架
- **IM-SENSE-RING** · 微环折射率传感前端预设计（复用光链路拓扑）：微环谐振传感公开路线（硅光折射率/生物传感 roadmap、公开文献与标准草案）；复用 link 系统预算锚 S1/S2/S5/S7 已验证闭环
- **IM-LASER-INT** · 片上激光源集成发射模板（异质集成黑箱源 + 已锚定无源网）：异质集成 III-V/Si 片上光源公开路线图（AIM Photonics 等公开 PDK 动向 / 学术异质集成 laser 公开文献）；复用 link 系统预算锚
- **IM-QCOM-LINK** · 量子计算频率复用读出链路（5 比特保真度链）：IBM/Google 公开多比特频率复用读出架构；D-46×D-47 已验证保真度预算框架
- **IM-800G-DR8** · 800G DR8 硅光发射引擎预设计（8×100G PAM4）：Hyperphotonix Hyper Silicon™ 公开平台（400G DR4/800G DR8/1.6T DR8 PIC 路线）；IEEE 802.3 800G 光接口标准进程
- **IM-WDM-8CH-1D** · 8 通道 CWDM/DWDM 解复用前端预设计（8×λ）：IEEE 802.3bs 400GBASE-FR8/LR8（8 波 WDM 信道 IL 6.3 dB 上限，公开标准）；AWG 40ch datasheet 量级参照
- **IM-DWDM-40CH** · 40 通道 DWDM 阵列解复用预设计（C 波段 100GHz ITU 网格）：Qualinet/NTT-ID 40ch 100GHz Athermal AWG 公开 datasheet（插损 typ 4.5/max 6.0 dB）；ITU-T G.694.1 DWDM 网格标准
- **IM-FTTH-PLC8** · FTTH 1×8 PLC 分光预设计（PON 无源分光网）：ITU-T G.671 / Telcordia GR-1209 公开典型最大插损 1×8 ≤10.7 dB；ITU-T G.984.3 GPON ODN 预算标准
- **IM-FTTH-PLC16** · FTTH 1×16 PLC 分光预设计（高密度分光）：ITU-T G.671 / Telcordia GR-1209 公开典型最大插损 1×16 ≤14.0 dB；商用 PLC datasheet 实测一致性（LuLeey ≤14.0 dB）
- **IM-CPO-OCS** · OCS 直连光交换前端预设计（收发 + 交换矩阵黑箱）：UC Berkeley EECS-2024-213：Polatis 576×576 中位 1.4/max 3 dB、Google 136×136 ≤2 dB；arXiv 2411.01503：2×FR4 功率预算 4.0 dB 公开
- **IM-LIDAR-TX** · FMCW 激光雷达发射前端预设计（1550nm 相干探测）：Optics Express 34, 7415 (2026)：片上 FMCW 单方向全光链路 ≈3.3 dB 实测；Pointcloud Nature 2026 纯固态 FMCW 焦平面阵列公开路线
- **IM-QKD-TX-SHELF** · QKD 发射端货架（Alice BB84 态制备）：npj Quantum Information 3, e1700262 (2017)：Alice 芯片总插损 15 dB 实测；中国 QKD 干线（京沪干线）公开路线
- **IM-QKD-RX-SHELF** · QKD 接收端货架（Bob 基矢测量）：npj Quantum Information 3, e1700262 (2017)：Bob 芯片总插损 8 dB 实测；OE 28, 18449 (2020) 多用户接收机 13 dB 公开
- **IM-QKD-MULTI4** · 多用户 QKD 接收机货架（4 用户选路）：Optics Express 28, 18449 (2020)：4 用户 MZI 选路接收机总损耗 13 dB 实测（公开）
- **IM-SENS-MZI** · MZI 干涉传感前端货架（生物化学折射率感测）：公开 PICS/FBG 传感链路综述：干涉型传感前端全链路插损预算通常 ≤15 dB（商用光纤传感模块 10–18 dB 区间）
- **IM-CHIPLET-IO** · 光 chiplet 互连前端货架（XPU 光 IO）：Broadcom 公开 CPO 路线（TH5-Bailly 6.4T 引擎，XPU 光连接演示）；OIF CPO 2.0 公开路线图
- **IM-QCTRL-ZC3-10Q** · 10 比特频率复用读出链货架（祖冲之三号量级）：上海科技情报研究所公开对比表：电子科大祖冲之三号 (2024, 105 qubit) 读出保真度 99.18%；D-46×D-47 已验证保真度预算框架
- **IM-QCTRL-HERON-16Q** · 16 比特频率复用读出链货架（IBM Heron R2 量级）：上海科技情报研究所公开对比表：IBM Heron R2 (2024, 156 qubit) 读出保真度 98.5%；IBM Quantum Cloud 公开 readout error ~1%
- **IM-QCTRL-WILLOW-12Q** · 12 比特频率复用读出链货架（Google Willow 量级）：Applied Quantum 公开技术分析：Google Willow (2024, 105 qubit) 复用色散读出 + JPA，读出保真度 ~99.3%；arXiv 公开架构文档
- **IM-PSM4-SHELF** · 100G PSM4 硅光收发前端预设计（4×25G，500m SMF）：IEEE 802.3bm 100GBASE-PSM4（4×25G，500m SMF）公开标准；商用 PSM4 平台 datasheet 单通道插损 ≤4.0 dB
- **IM-FR4-SHELF** · 400G FR4 硅光收发前端预设计（4×100G PAM4，2km）：IEEE 802.3bs 400GBASE-FR4（clause 121）单通道插损预算 ≤4.5 dB；Hyperphotonix 平台同量级
- **IM-CWDM4-SHELF** · 100G CWDM4 解复用前端预设计（4×25G，2km）：CWDM4 MSA（100G CWDM4：4×25G，2km）单通道插损 ≤4.0 dB；商用 100G CWDM4 光模块 datasheet 一致
- **IM-LPO-112G** · LPO 线性直驱光模块前端预设计（112G 单通道）：LPO（线性可插拔光模块）公开产业路线（业界 112G/通道 线性直驱，去 Retimer/DSP 降功耗）：链路预算量级与 FR4/DR 同源
- **IM-1.6T-DR8** · 1.6T DR8 硅光发射引擎预设计（16×100G PAM4）：1.6T DR8（16×100G PAM4）公开产业路线（OIF / 光模块厂商 1.6T DR8 MSA 量级）：单通道 100G PAM4，链路预算与 800G DR8 同源、通道翻倍
- **IM-800G-FR4** · 800G FR4 硅光收发前端预设计（4×200G PAM4，2km）：OIF/光模块厂商 800G FR4（4×200G PAM4）公开路线：2026 均价 $400–480（硅光方案）；LightCounting 2026 高速数通市场 ~$12B、800G+ 出货 6300 万只（2.6×）；IEEE 802.3dj（200G/lane PAM4）预计 2026 中定稿
- **IM-1.6T-FR4** · 1.6T FR4 硅光发射引擎预设计（4×400G PAM4）：1.6T FR4（4×400G PAM4）公开产业路线：NVIDIA GB300 标配、2026 量产拐点（H1 主力上行）；硅光方案 $1000–1100；对标 1.6T DR8 同源、通道数减半
- **IM-400G-DR4** · 400G DR4 硅光收发前端预设计（4×100G PAM4，500m）：IEEE 802.3bs 400GBASE-DR4（4×100G，500m SMF）公开标准；QYResearch 2026 全球 400G 光模块市场 ~$11.3 亿、传统云负载仍高量；商用 400G-DR4 平台单通道插损 ≤4.0 dB
- **IM-100G-LR4** · 100G LR4 解复用前端预设计（4×25G LAN-WDM，10km）：IEEE 802.3cu-2021 100GBASE-LR4（4×25G LAN-WDM，10km）公开标准；5G 前传/城域/企业网高量部署；商用 100G LR4 光模块单通道插损 ≤4.5 dB
- **IM-PON-50G** · 50G-PON 光前端预设计（OLT/ONU 无源网，ITU-T G.9804）：ITU-T G.9804（Higher Speed PON）50G-PON 标准 2021 发布、2023 增补对称型；工信部 2025 首批 168 试点→2026 商用启航（2026.4 验收 136：52 小区/38 工厂/46 园区）；功率预算 N1(29dB)/C+(32dB)、1:64 分光
- **IM-OSW-1X8** · 1×8 可重构光开关前端预设计（OCS/dOCS 趋势）：数据中心可重构光交换（OCS/dOCS）趋势：Cignal AI 预测 OCS 全球市场 2029 ≥$25 亿；LightCounting 预计 Scale-Up 光互连 2027 规模商用；SiPh MZI 矩阵开关（8–72 端口，0.5 dB/级）公开；Google TPU v4 9216 卡 OCS 互联
- **IM-LIDAR-RX** · FMCW 激光雷达相干接收前端预设计（90° 混频）：FMCW 激光雷达相干接收机公开路线（Aeva/Bosch 等全固态 FMCW）；与 IM-LIDAR-TX（Optics Express 34,7415 (2026) 实测 3.3 dB）配套，90° 混频 + 平衡探测按黑箱；相干探测公开链路预算量级
- **IM-BIOSENSE** · 环形谐振生物/化学传感前端预设计（Lab-on-Chip）：公开 Lab-on-Chip 环形谐振传感文献综述：微环折射率传感在生物/化学检测（如多路免疫传感）的成熟应用；复用 SENSE-RING 拓扑与 GP-GRATING-EFF+GP-SIN-PL 基元
- **IM-COHERENT-400ZR** · 400G ZR/ZR+ 相干收发前端预设计（DCI 120km，QSFP-DD/OSFP）：OIF 800ZR 互操作 IA（2024-11 发布）公开；IEEE 802.3dj 1600ZR 预计 2026 中定稿；Research and Markets：ZR+ 相干光模块市场 2025 $18.4 亿→2026 $21.9 亿（CAGR 18.9%）；Dell'Oro/Cignal AI：800ZR/ZR+ 2026 进入大规模部署
- **IM-RING-MOD** · 微环调制器（MRM）前端预设计（200Gbps/lane，CPO 高带宽密度）：NVIDIA CPO 采用微环调制器（MRM，带宽密度 >1 Tbps/mm 公开路线）；TSMC COUPE 2026 量产 200Gbps/lane MRM、带宽密度 0.5→4 Tbps/mm (2030)；Ayar Labs TeraPHY / NewPhotonics 无热 MRM（OFC 2026 公开）
- **IM-XGS-PON** · XGS-PON 光前端预设计（OLT/ONU 无源网，ITU-T G.9807.1，10G 对称）：ITU-T G.9807.1（XGS-PON，10G 对称）标准；Dell'Oro：PON 设备营收 $8.3B(2021)→$9.8B(2026)，XGS-PON 占 PON 市场 15%(2021)→55%(2026)；中国 10G PON 端口 3201 万(2026-03)→3286 万(2026-06)；Openreach 英国扩 XGS-PON
- **IM-WSS-1X9** · 1×9 波长选择开关（WSS）前端预设计（ROADM 波长路由）：MarkWide：ROADM WSS 市场 $1.8B(2026)→$4.76B(2035) CAGR 11.4%；Dual WSS $325M(2025)→$384.43M(2026)；支撑 400G/800G/1.6T 相干；Lumentum/Coherent 主导
- **IM-VOA** · 可变光衰减器（VOA）前端预设计（ROADM 功率均衡）：MEMS VOA 市场 $215.5M(2025)→$320.89M(2032) CAGR 5.85%；Variable Optical Attenuators $380M(2025)→$551.7M(2032) CAGR 5.4%；>70% 光网络用动态衰减（ROADM 功率均衡）
- **IM-MZI-MOD** · 马赫-曾德尔调制器（MZM）前端预设计（相干/直检发射）：硅基 MZM 市场 $1.51B(2025)→$7.24B(2034) CAGR 19.0%（Growth Market Reports 2026-06）；Tower Semiconductor+Coherent（2026-03）400 Gbps/lane 硅 MZM 量产就绪；200+ GHz 带宽、sub-0.5 dB 插损；硅 MZM 占 2025 MZM 市场 45.8%。
- **IM-PSR** · 偏振分束旋转器（PSR）前端预设计（TE/TM 复用）：Sama et al. Optics and Laser Technology 2026 vol 203，高隔离 PSR（SOI 220nm+70nm 部分刻蚀），TM-to-TE 损耗 0.71 dB @1550nm、PER 最差 30.95 dB、C 波段；偏振分束器市场 $1.2-1.5B(2025)→$2.2-3.2B(2035) CAGR 7-9%（IndexBox）。
- **IM-PHOTONIC-INTERPOSER** · 光子中介层/共封装（CPO）前端预设计（2.5D 光互连）：IDTechEx 预测 CPO 市场 2036 破 $20B、CAGR 37%；TSMC COUPE 2026-04 量产；NVIDIA Quantum-X/Spectrum-X Photonics CPO 2026 出货；Ayar Labs TeraPHY $500M E 轮 2026-03；2.5D 硅中介层+TSV 路径。
- **IM-OPTO-COMPUTE** · 光计算/光神经网络（ONN）前端预设计（模拟矩阵乘）：光神经网络处理器市场 Lightmatter/Lightelligence/Celestial AI/Intel/Ayar Labs 占 56.3%（Global Market Insights）；北美光子神经形态芯片 $180-240M(2026) CAGR 32-38%；Lightmatter 1.2 petaflops 模拟 ONN、Lightelligence 8.3 pJ/op。
- **IM-OCT** · 光学相干层析（OCT）前端预设计（医疗成像干涉仪）：OCT 市场 $2.36B(2026)→$4.01B(2032) CAGR 9.08%（Research and Markets）；眼科 OCT $1.52B(2025)→$2.52B(2032) CAGR 6.49%；糖尿病视网膜病变+AMD 驱动。
- **IM-OPA-LIDAR** · 光学相控阵（OPA）固态激光雷达前端预设计（无惯量大角度光束扫描）：OPA LiDAR 市场 Dataintelo $1.8B(2025)→$9.6B(2034) CAGR 20.4%；单芯片集成 OPA 占 63.7%（2025）；Yole：投入 OPA 研发厂商>35 家、车规原型 12 家，2026 乘用车前装渗透率破 5%（~$4.2 亿）；CMOS 兼容硅光波导型 OPA（MZI 阵列/级联光栅阵列）为主流。
- **IM-COHERENT-RX** · 相干接收机（90° 光混频器）前端预设计（相干探测本振耦合）：Optical Hybrid 市场 $483.33M(2025)→$1.10B(2032) CAGR 12.48%；90° 光混频占 67.3%（2025）；由 400G→800G→1.6T 相干可插拔驱动，SiPh+InP 集成降 footprint/功耗；相干光通信占应用 75.9%。
- **IM-ONCHIP-NOC** · 片上光网络（ONoC）路由前端预设计（chiplet 光互连 fabric）：Chiplet 互连光子市场 $1.8B(2025)→$52.1B(2034) CAGR 38.5%（Market Intelo）；光互连 $13.69B(2025)→$15.28B(2026) CAGR 11.6%→$23.54B(2030)；Ayar TeraPHY（UCIe 光 chiplet 8Tbps）、Intel 光 I/O 4Tbps/5pJ/bit。
- **IM-MCF-FANOUT** · 多芯光纤扇出（MCF Fan-out）前端预设计（空分复用 SDM 过渡）：MCF Fanouts 市场 $640M(2025)→$1.25B(2032) CAGR 11.8%（Strategic Market Research）；窄口径 $87.5M(2025)→$504.85M(2032) CAGR 28.45%；OFC 2026 SDM4 MCF MSA（Corning/AFL/Sumitomo）4 芯；TPU 首条商用 MCF（2025-2026）。
- **IM-OPTICAL-GYRO** · 光纤陀螺（FOG/Sagnac 干涉仪）前端预设计（高精度角速率传感）：FOG 市场 $1.2B(2026)→$2.0B(2033) CAGR 7.5%（Persistence）；或 $1.96B(2025)→$4.60B(2034) CAGR 9.93%；干涉型 FOG（Sagnac 效应）占 78%（2026）；GNSS 拒止环境 + 国防现代化驱动。
- **IM-MRR-FILTER** · 微环谐振滤波器（可重构光滤波 / add-drop）前端预设计：Silicon Microring Resonators 市场 $450M(2025)→$1.66B(2032) CAGR 20.5%（PMarketResearch）；Microring Filter Array $41.58M(2025)→$245M(2032) CAGR 27.8%（MarketPublishers）；add-drop 型占 55.5%(2025)；AI 集群 DWDM/CPO 推升阵列化需求。
- **IM-SPLITTER-TREE** · 1×N 功分树（PLC 功分网络）前端预设计：PLC Splitter 市场 $2.8B(2025)→$5.6B(2034) CAGR 8.1%（Dataintelo）；1×N 型占 62.4%(2025)；全球光分路器 $1.28B(2026)→$1.94B(2030) CAGR 8.7%（IIM）；XGS-PON/FTTR 推升 1×32 及以上高通道数需求。
- **IM-TRUE-TIME-DELAY** · 微波光子真延时（TTD）波束成形网络前端预设计：Phased Array Antenna 市场 $3.90B(2026)→$8.38B(2034) CAGR 10.04%（ValueMarketResearch）；相控阵天线系统 2025 $18.7B→2030 $38.5B CAGR 12.8%（IIM）；微波光子真延时用于相控阵雷达波束赋形，电子移相器无法复制。
- **IM-GAS-SENSE** · 波导气体/吸收光谱传感前端预设计（SiN 宽波段）：SiN PIC 市场 $320M(2025)→$1113.58M(2032) CAGR 19.5%（PW Consulting）；SiN 宽透明窗口（可见-中红外）适合分子指纹吸收；VOC 片上中红外检测灵敏度较 Si 提升 5×（TAMU 2022）；环境/医疗光子传感需求增长。
- **IM-GRATING-COUPLE** · 光栅耦合阵列 / 光纤贴装接口前端预设计（CPO 光 IO）：Grating Coupler Array 市场 $1.45B(2024)→$3.07B(2033) CAGR 8.7%（GrowthMarketReports）；Grating Coupler 2025 APAC $0.31B 占 36.5%，耦合效率 >90%；CPO 共封装光学（Azure/Google/AWS）从试点转向早期量产，结构性拉动。
- **IM-AWG-DEMUX** · 阵列波导光栅解复用器（AWG DeMUX）前端预设计：AWG MUX/DeMUX 市场 $735M(2025)→$1.375B(2031) CAGR 8.14%；Arrayed Waveguide Market $320-570M(2026) CAGR 6.5-11.7%；QYResearch $270M(2025)→$427M(2032) CAGR 6.9%；Thermal AWG $1.55B(2026)→$2.84B(2033) CAGR 9.1%；AI 数据中心 DWDM/CPO 结构性推升需求。
- **IM-ONCHIP-SPECTROMETER** · 片上微型光谱仪（Chip-scale Spectrometer）前端预设计：Chip-scale Spectrometer $2.44B(2025)→$8.7B(2033) CAGR 17.2%；Chip/Modular Spectrometers $546M(2026)→$886M(2032) CAGR 8.4%；Miniature Spectrometer IC $1.36B(2025)→$3.99B(2034) CAGR 12.7%（医疗/环境/消费电子驱动）。
- **IM-MDM-MUX** · 模分复用器（Mode-division Multiplexer）前端预设计：Few-Mode Fibers $10.74B(2025) CAGR 6.86%；MDM Equipment $1.42B(2024)→$4.16B(2033) CAGR 12.6%；Market Intelo →$6.89B CAGR 18.9%；Growth Market Reports CAGR 13.7%（突破单模容量极限）。
- **IM-OPTCOMB** · 芯片级光频梳（Microcomb）前端预设计：Intel Market Research $58M(2025)→$108M(2034) CAGR 7.4%；全球光频梳 $1.87B(2026) 年增 31.7%；Archive Market Research $1.8B(2025) CAGR 11%；芯片级微梳 CAGR 47.8%（DWDM/时频同步/量子）。
- **IM-POL-ROTATOR** · 片上偏振旋转器（Polarization Rotator）前端预设计：光偏振控制器 $480M(2026) 增 12.3% / $4.72B(2026) 增 12.9%；Polarization Rotator CAGR 10.3%(2026-2033)；Stats N Data CAGR 6%；集成波导型增速 28%（硅光量产拉动）。
- **IM-3.2T-DR8** · 3.2T DR8 硅光收发前端预设计（8×400G PAM4）：中际旭创/新易盛 1.6T&3.2T OSFP DR8 公开规格（单通道插损 ≤4.5 dB）；Hyperphotonix 800G/1.6T DR8 平台；IEEE 802.3df 800G/1.6T 进程
- **IM-1.6T-LPO** · 1.6T LPO 线性直驱光模块前端预设计（8×200G）：新易盛/云晖 1.6T LPO 公开规格（单通道插损 ≤4.5 dB）；LPO 线性直驱 MSA 路线
- **IM-1.6T-ZR** · 1.6T 相干 ZR 光模块前端预设计（相干 400ZR/1.6ZR）：光迅/Acacia 相干 400ZR/1.6ZR 公开规格；OIF 400ZR/800ZR/1.6ZR 标准
- **IM-CPO-16CH** · CPO 16 通道 WDM 光引擎前端预设计：OIF CPO 3.2T/6.4T 白皮书；CPO 共封装光学（Azure/Google/AWS）从试点转早期量产
- **IM-UCIE-OPTICAL** · UCIe-Optical 光 chiplet 互连前端预设计：UCIe 2.0 新增光互连（UCIe-Optical）标准草案；Intel/Ayarl 光 chiplet 公开路线
- **IM-LIDAR-FULL** · FMCW 固态激光雷达全前端预设计（TX+RX 一体）：Optics Express 34, 7415 (2026) 公开论文：片上 FMCW LiDAR 单方向链路损耗 ≈3.3 dB；FMCW 固态雷达产业（Aeva/Mobileye）公开路线
- **IM-POC-BIOSENSE** · POCT 生物/气体 Lab-on-Chip 传感前端预设计：公开 PICS / 生物光子传感综述：干涉型传感前端全链路插损预算通常 ≤15 dB；POCT 生物传感产业（国内外 IVD）公开路线
- **IM-FTTR-PLC32** · 50G-PON / FTTR 32 路 PLC 分路前端预设计：ITU-T G.671 / Telcordia GR-1209：1×32 PLC 每支路最大插损 ≤14.0 dB；50G-PON（ITU-T G.hsp.50Gpon）公开路线
- **IM-TTD-5G** · 微波光子真时延（TTD）波束成形前端预设计：微波光子 TTD 公开综述：真时延网络片上光路损耗典型 ≤10 dB；5G/6G 相控阵（国内外射频光子系统）公开路线
- **IM-QKD-FULL-LINK** · QKD 干线收发全链路前端预设计（BB84 态制备/测量）：npj Quantum Information 3, e1700262 (2017) 公开论文：QKD Alice/Bob 芯片总插损 15/8 dB；国内量子保密通信干线（京沪/武合）公开路线
- **IM-QCTRL-32Q** · 32 量子比特读出控制芯片前端预设计：IBM Heron R2 (2024, 156 qubit) 公开读数保真度 98.5%；本源悟空-180 读数 99.0%；NISQ 典型单发读出 ≥97.5%（PostQuantum 2026 基准）
- **IM-OPA-2D** · 2D 光学相控阵（OPA）固态雷达前端预设计：公开 OPA 硅光相控阵综述：片上 OPA 光路损耗典型 ≤12 dB；固态雷达（国内外 OPA 路线）公开路线
- **IM-OPTCOMB-WDM** · WDM 锁定芯片级光频梳（DWDM-grid Microcomb）预设计：Intel Market Research 光频梳 $58M(2025)→$108M(2034) CAGR 7.4%；芯片级微梳 CAGR 47.8%（DWDM/时频同步/量子）；ITU-T G.694.1 DWDM 网格需求。
- **IM-CPO-OIO-8CH** · CPO 硅光 I/O 光引擎预设计（8×200G = 1.6T，标准 250 µm 光纤阵列）：OIF-Co-Packaging-3.2T-Module-01.0（3.2T 引擎 = 32×CEI-112G-XSR 电 + 8×400G FR4/DR4 光口）；Broadcom TH5-Bailly CPO 已部署；NVIDIA Quantum-X Photonics Q3450-LD（144×800G InfiniBand，液冷）2026 出货；Spectrum-X Ethernet Photonics 2H2026 爬坡
- **IM-CPO-OIO-16CH** · CPO 高密度光引擎预设计（16×200G = 3.2T，127 µm 细间距光纤阵列）：OIF-Co-Packaging-3.2T-Module-01.0（3.2T CPO 引擎，8×400G 光口，~140 G/mm 海岸线）；Semiconductor Engineering：缩小光纤阵列间距（FAU scaling）是提升 CPO 带宽密度的两条主路径之一（另一为 WDM），「fiber pitches often exceed 100 microns」；OIF EEI Panel OFC26：超大规模 scale-up 目标区 CPO 3 pJ/b @ 2.0 Tbps/mm
- **IM-CPO-OIO-CHIPLET** · chiplet 间光 I/O 预设计（UCIe-Optical 类，8×32G 光栅阵列直连，无光纤）：OIF EEI Panel OFC26 官方表（oiforum.com）：ASIC UCIe-32G 标准封装 95 µm pitch 记 2.0 Tbps/mm，ASIC SerDes-200G 记 1.9–2.7 Tbps/mm；Semiconductor Engineering：AI chiplet（UCIe/OIF）边缘带宽密度 ≈3 Tbps/mm，与 CPO ≈0.5 Tbps/mm 存在 6× 差距；OIF Compute Optics Interface（COI）面向 AI scale-up；Intel OCI 光计算互连 chiplet
- **IM-CPO-ELS-FIBER** · CPO 外置可更换激光源（ELS）+ 光纤 I/O 前端预设计（OIF 3.2T IA 类 8×400G）：OIF-Co-Packaging-3.2T-Module-01.0（3.2T = 32×CEI-112G-XSR + 8×400G FR4/DR4 光口）；Broadcom 第三代 102.4T Davisson（TH6）CPO 交换机引入**前面板可现场更换激光源**，规避 CPO 维护痛点；锐捷 25.6T 硅光 NPO、Ragile RA-BC6932 引入 ELSFP 接口；CPO 单端口功耗 5.5–7W（800G），较可插拔降低 50–70%（Yole/OIF 公开汇总）

---
_LDA · 开源 Agent-native EDA（光子 PDA + 量子 QEDA）· 物理定律锚红线 · LLM 不进判决路径_