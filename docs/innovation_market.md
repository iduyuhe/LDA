# LDA 创新超市（Innovation Marketplace）· 前瞻预研货架目录

> 生成口径：每个货架 = 已锚定基元（产品级基准库 GP-*）+ 公开信号驱动的**前瞻预研**预设计。
> **24/24 货架通过结构可行 + 系统预算不破检查**。

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

---
_LDA · 开源 Agent-native EDA（光子 PDA + 量子 QEDA）· 物理定律锚红线 · LLM 不进判决路径_