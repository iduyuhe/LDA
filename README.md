# LDA · Agent-native 光子/量子芯片设计软件

> LDA（Lightwave Design Agent）= 光子芯片(PDA) + 量子芯片(QEDA) 的开源、主权、Agent-native 设计软件。
> 核心主张：**底层核心求解器由 AI agent 递归自举开发**，人类做架构与验证，AI 不进入判决路径。
> 当前版本：**v0.6**（2026-08-24 · 3D 逆设计纵深 + QEDA 求解器级补强：破 3D 诚实边界（3D Yee 显式转置伴随 Mᵀ 1e-15 → 3D 截面 → 3D 端口验收 → 谱形×3D → 3D numba 性能 20×+ → **3D voxel 拓扑**）+ transmon-resonator 色散读出三能级严格求解（α 修正必要性 31×）+ QEDA 纵深三件套（多能级展开收敛 / Rabi+AC Stark / 读出串扰 ZZ 耦合）+ 五十二面板）

## 这是什么

LDA 是一套面向光子集成回路（PIC）与超导量子比特（QEDA）的**设计→验证闭环引擎**。它把"AI agent 写内核、确定性裁判验收"的工程范式落成可运行、可验证、可复现的代码，让普通算力（纯 numpy、零 GPU）就能自助完成**从设计目标到已验证器件/系统**的闭环，并把**物理定律锚 + 实证大数据锚**作为信任地基，而非依赖任意大模型意见。

**v0.6 的核心能力（D-36~D-89）**：给系统一个设计目标（如"f01=5GHz 的 Transmon"、"FSR=17.5nm 的环形分波器"、"N qubit 频率复用读出"、"多环 WDM × 量子读出混合系统"、"8 信道 WDM × 8 qubit 联合压测"、"3D 平板波导聚焦 taper"），LDA 自动完成 **参数搜索 → 真实求解器双重验证 → 返回被验证过的设计**，并以**统一设计包（DesignPackage）**格式交付——LLM 不进判决路径，是否 PASS 由死标量比对决定。**v0.6 在 v0.5 系统级（M7 + 护城河 + 逆设计纵深四阶）之上新增**：①**3D 逆设计全链（破 3D 诚实边界）**——3D adjoint 形状（D-84，3D Yee 显式转置伴随 Mᵀ 1e-15）、3D 截面形状（D-85，宽度×厚度双软边界 imp 3.17×）、3D 端口 S 参数联合验收（D-86，双独立确认 FOM 1.88×+S21 1.60×）、谱形目标×3D（D-87，加权 3.13×）、3D numba 性能升维（D-89，大域 forward 20-29× bit-level 一致）；②**QEDA 求解器级补强**（D-88，transmon-resonator 色散读出三能级严格求解，χ=g²α/(Δ(Δ+α)) α 修正必要性 31×，n_crit/Purcell/AC Stark）。

### 红线（设计原则）

- **LLM 不进判决路径**：求解器输出 vs 黄金参考的 PASS/FAIL 由死代码标量比对决定，AI 只写代码、不写判决。
- **主权优先**：核心求解器自研（FDTD/FDFD/Mie/TMM/严格对角化等），不外包、不借 GPL 源码；可借 ORACLE 真值校验与晶圆厂 PDK。
- **可验证**：每个能力都配确定性比对裁判或物理定律锚（解析闭式 ↔ 严格数值双验证），避免纯 AI 互证循环论证。

## 架构分层（从底层走）

```
L0  开放 IR / DSL     lda_ir/   光子+量子统一中间表示（schema v0.3，PhysicsAnchor 一等字段）
L1  智能体协议层      lda_agent/ 设计→验证闭环、逆设计、系统级设计（agent 可操作接口）
L2  开放器件库/Registry lda_l2/  已验证器件资产 + GDS 编码器 + DRC（社区共建）
L3  求解器后端        lda_solver/ 自研求解器（FDTD/FDFD/Transmon/Resonator/Coupler 严格数值）
L4  统一交付          lda_design/ 设计包规范（DesignPackage schema v0.1 + JSON Schema）
```

## 设计→验证闭环（核心能力）

```
给定设计目标 → 物理定律 ORACLE 瞬时搜索（逼近目标）
             → top-K 候选真实求解器双重验证（解析契约 + 严格数值物理自洽，纯 numpy 零 GPU）
             → 死标量验收判决（LLM 不进判决路径）
             → 统一设计包 DesignPackage（ir + design + verification + artifacts + honest_notes）
```

**已验证能力阶梯（D-36~D-52，全部实测全绿）**：

| 编号 | 能力 | 实测亮点 |
|---|---|---|
| D-36 | 设计→验证闭环引擎 | WG/Bragg/Transmon/Ring 4 器件，最优设计被真实求解器验证 |
| D-37 | 环形 add-drop 产品链路 | 目标 FSR → R → GDS/DRC/FDTD → 损耗预算 → 可制造设计包 |
| D-38 | agent 逆设计通用框架 | 同一框架落地 4 器件（光子+量子，注册一条 spec 零框架改动）|
| D-39 | 量子多器件双验证 | Transmon/Resonator/Coupler 全带一等真实物理验证入口 |
| D-40 | 统一 IR 物理锚 | schema v0.3，同一 IR 表达两种物理，harness 达 **13 题（B1-B13）** |
| D-41 | 量子逆设计闭环 | 目标频率/耦合 → IR → 闭式反解 → 严格数值验证 PASS |
| D-42 | WDM 多环级联系统 | 4 信道分波 IL≤0.12dB、XT≥18.4dB，超规格正确拒绝 |
| D-43 | 光子-量子混合链路 | 芯片级 dispersive readout，JC 精确对角化↔色散 χ |
| D-44 | 统一设计包规范 | DesignPackage schema + JSON Schema（8 类包 conforms）|
| D-45 | WDM 指标驱动 | XT 指标反解 gap、插损预算、单 FSR 信道上限 |
| D-46 | N-qubit 频率复用读出 | 3 qubit 沿公共力线错开 200MHz，dip 可分辨 |
| D-47 | 单发读出保真度预算 | t_m*=53.6ns → SNR=3.50、F=0.9984（T1 限制）|
| D-48 | 正式发布准备 | README v0.2 + CHANGELOG + git tag v0.2（三端同步）|
| D-49 | 设计包 spec 6 kind | 文档与实现零漂移，JSON Schema enum 同步 |
| D-50 | fdtd3d GPU 实跑激活 | RTX 5060 Ti：cuda↔cpu **bit-equivalent 互证 PASS**（20 分钟实测）|
| D-51 | N-qubit 逐 qubit 保真度 | D-46×D-47 集成：坏 qubit 独立 FAIL 不影响他者 |
| D-52 | **混合巨型系统** | 光子 WDM 分波 + 量子读出**同一网表**（IR 10 器件+8 网表）联合验收 |
| D-55 | **方向耦合器设计闭环** | 目标分束比 → **2D FDTD 标定 κ** → CMT 反解 L → 迭代收敛（50:50 命中 cross=0.503）|
| D-57 | **耦合器 × WDM 组合** | **FDTD 标定 PDK 文件驱动 gap** → WDM 验收全过 + 诚实报告解析偏差 4.6 倍 |
| D-59 | **波长相关标定库** | κ_c(gap,λ) 二维：每信道按 λ 独立 k_ring，实测增幅 ~27% 物理正确 |
| D-60 | **κ_c(gap,λ) 全网格标定库** | **双线性插值查表**（9 点全网格）替代分离变量近似，无需任何解析假设 |
| D-63 | **方向耦合器 × 量子读出** | 光子**分束网络供电量子读出控制线**：级联功率=**FDTD 实测分束比之积** → 每 qubit n̄ 缩放 → SNR/F 预算（Δ≤0.003，F≥0.9996）|
| D-66 | **标定库 × 分束网络** | 分束网络 DC gap 由 κ_c(gap) 标定库驱动设计（标定 5/5 PASS）|
| D-67 | **分束网络 × WDM** | 光子域功率分配与分波联合：WDM 解复用 → 每信道 DC 分束树（FDTD 实测分束比级联）|
| D-68 | **PDK 标定库 4×5 升级** | 分辨率修正：κ_c 沿 gap/λ 双轴单调的干净网格（20 点，dl40），双线性插值查表 |
| D-69 | **伴随法拓扑逆设计（adjoint FDTD）** | 主权 2D FDTD **显式转置伴随**（Mᵀ 对拍 1e-15）+ 高斯脉冲源收集场能目标 + 回溯线搜索梯度优化：**对拍 max_rel_err=0.0**，**拓扑逆设计提升 15.1×**（3996 体素）|
| D-70 | **逆设计接入设计→验证引擎（method=adjoint）** | DesignAgent 统一入口按 **method** 分流（scan=布拉格扫描零改动 / adjoint=伴随梯度拓扑逆设计）：目标泛化为**「把指定孔径内收集场能最大化」**（设计区/孔径/材料对比度/波长全透传）→ 均匀平板初值 → FD 对拍锚（≤0.15）→ 回溯线搜索梯度优化（improvement≥1.5）→ 死标量验收输出 DesignOutcomeReport |
| D-71 | **真实版图基元库（foundry-ready）** | 4 基元替代玩具几何：Taper（线性/绝热余弦轮廓）、Euler 弯（clothoid 曲率连续，90° 终点角误差&lt;0.01°）、MMI 1×2 对称分束、光栅耦合器（周期部分刻蚀齿）→ **GDS 可编码（round-trip 回读一致）+ DRC 全绿**（min_width/min_space/min_bend_R）；几何交付，电特性归 D-72 |
| D-72 | **真实 2D FDTD 端口 S 参数验收（M5）** | MMI 全 2D FDTD 端口透反射谱（输入 CW 激励→多端口 DFT 收集→输入功率归一→S11/S21/S31）：**平衡度 max=0.078**、中心波长 **S11=0.094 / T=0.906** + **DRC 规则从真实 SOI 180nm PDK 注入**（NOEIC/CUMEC/SITRI 全绿）|
| D-72★ | **3D 端口 S 参数验收（SOI 220nm · numba 核）** | **MMI/DC/Ring** 全 3D FDTD 端口透反射谱（复用已验证 numba 核 + 截面匹配源）：**MMI 平衡度 0.015-0.083、DC cross_frac 端点趋势（CMT）、Ring drop 谐振峰检出**，3 器件全过 + **2D↔3D 对拍诊断**；**已接入设计闭环**（DesignAgent method=sparams3d，三 method 统一入口）|
| D-78 | **光栅耦合器端口验收（M6 起步 · 光栅方程 ORACLE）** | GC 2D FDTD 透射谱谷检测（D-78 修正真实方波光栅：齿=硅/凹槽=包层）：谷位置 vs **光栅方程 λ_rad=Λ·n_eff** 对拍（**rel=0.092**≤0.15，n_eff FDTD 独立测得非拟合）+ **Λ 趋势锚 dλ/dΛ=周期结构 n_eff（rel=0.020**≤0.10）：谷深 0.996、**验收 PASS**，smoke 3/3；诚实标注凹槽微扰负偏 ~9% + 2D≠3D 光纤耦合 |
| D-79 | **真实基元接入设计流水线（Track B 收口 · v0.4 门槛达成）** | 流水线默认几何切换到 D-71 真实基元：Ring/AddDrop 实心环带→**真实波导环 PATH**、YBranch 裸分叉→**输入绝热 taper**+双 arm、DC/Waveguide 已是 PATH、Taper/EulerBend/MMI/GC 沿用基元——全 **9 kind 真实 GDS + round-trip + 3×SOI PDK DRC 全绿**（NOEIC/CUMEC/SITRI），"设计→验证→版图"全链路真实化闭环 |
| D-73 | **热光可调 WDM（Track D 系统级 · M7 第一件）** | 静态 WDM（D-42/D-57）叠加**每环热光相位 shifter**：**Δλ/λ=(dn/dT)·R_th·P/n_eff 物理定律锚**（dn/dT=1.86e-4/K 材料常数、n_eff=2.4，ORACLE 比对真实 Si 加热器斜率 [0.02,0.5] nm/mW）→ 信道重分配验证 |P|≤P_max 且 |Δλ|≤FSR/2（无混叠）；默认 3 信道 S≈0.120 nm/mW、目标 [1552.7,1555.7,1558.7]nm 各 ~22.7mW、最大可达位移 6.0nm≥FSR/2；smoke 3/3 |
| D-74 | **量子门 / 纠错拓扑（Track D 系统级 · M7 第二件）** | 量子域从「读出」走向「计算」：①量子门库（I/X/Y/Z/H/S/T/CNOT/CZ/SWAP/Toffoli 解析矩阵，幺正性 ‖U†U−I‖≤1e-12 精确 + {H,T,CNOT} 通用性 **T∉24元Clifford 群论死标量锚**）②rotated surface code（**d² 数据比特、全对易、GF(2) 秩验证 k=1**、阈值标度 p_L=A·(p/p_th)^((d+1)/2)）③cross-resonance 门（g_CR=2J²Δ/(α²−Δ²) 有效模型 + t_CR≤T2）；ORACLE：|g_CR|∈[0.02,10]MHz、p<p_th（阈值门）；smoke 3/3 |
| D-75 | **大规模系统基准（Track D 系统级 · M7 第三件 · M7 收口）** | 把 WDM 级联 + 多 qubit 读出 + 混合巨型系统推进到 **N≥8 大规模**并做**性能与精度边界压测**：8 WDM 信道（1.2nm 密集 DWDM grid）级联 + 8-qubit 频率复用读出 + 联合 8×8 混合系统全过；**容量自洽**（实际最大可行 N=8 == 理论 floor(FSR/间隔)+1）、**IL 级联模型余量**（N=16 时 0.22dB，预算 3dB 的 7.3%）、**qubit 间隔临界**（默认 0.05GHz vs 失效 0.02GHz，余量 2.5×）、**标定网格分辨率**（κ_c 网格 λ 间距 25nm vs 信道间隔 1.2nm → 每信道变化 0.59%≤1%）；总压测耗时 0.056s；smoke 3/3 |
| D-76 | **L0 IR 开放标准（护城河与标准层 · v0.3 定稿）** | 把 schema 0.3 固化为**开放标准**（社区共建起点）：`docs/ir_spec.md`（LDA-STD-001 规范：9 kind 注册表 / 物理锚语义 / 校验规则 / 扩展指南）+ `docs/ir_schema.json`（JSON Schema draft-07）+ **零漂移校验**（Schema↔代码 9 kind 一致 / 全 kind conforms / 0.2 向后兼容 / physics 物理锚 round-trip——顺带修复 `dsl.py` 此前 round-trip 丢物理锚的序列化缺陷）；smoke 3/3 |
| D-77 | **验证合约工业化（护城河与标准层第二件）** | 全部验证收敛到**一条命令、一份机器可读报告**（社区协作门槛）：`run_ci_regression.py` 自动发现 54+ smoke + harness B1-B13 统一回归（SKIP=无 GPU/numba 降级、FAIL=真失败、新增零配置纳入；core 集实测 **27 PASS / 0 FAIL**）；`run_perf_bench.py` 求解器性能基准（greens numpy→numba **34.7×**、物理一致 rel=4.8e-16、GPU bit-equivalent、历史基线漂移 ±30% 预警）；CI 新增 `industrial-regression` job |
| D-80 | **谱形目标逆设计（Track A 深化）** | 把 adjoint 逆设计目标从「收集场能最大化」**泛化为三类谱形目标 FOM**（逼近商业 EDA 核心卖点）：**①split_ratio 分束比**（双输出监视器，对数加权 FOM，FDTD 实测命中 target±0.10——50:50 实测 0.574、imp 2.5×）；**②spectrum 多波长谱形**（FOM=Σw_λ·FOM_λ 加权联合，3 波长窄带 imp **11.7×**）；**③mode_match 模式匹配**（目标场投影，平坦目标 imp **8.6×**）；死标量验收 FD 对拍 ≤2e-4；smoke 3/3 |
| D-81 | **形状逆设计 + 多目标联合（Track A 纵深新线）** | 从 voxel 拓扑升级为**连续形状逆设计**（K 控制点宽度曲线 w(x) + sigmoid 软边界，**可制造性内建**：宽度界 + 平滑约束 + DRC 验收；形状梯度链式投影 FD 对拍 5e-4；imp **6.6×**）+ **多目标联合**（多波长加权 FOM 共享形状 + Pareto 前端扫描：2 波长加权 **5.6×** + 前端 3 点）；smoke 3/3 |
| D-82 | **形状+拓扑混合逆设计（Track A 纵深第二件）** | 形状主干（宽度曲线，可制造内建）⊕ **拓扑微调带**（voxel 密度，概率 OR 光滑组合——"任一有材料即材料"处处可导）分层表达；联合梯度 + 回溯线搜索 + **纯形状基线对比**（混合≥纯形状为验收判据）：混合 imp **18.3× vs 纯形状 6.0×（混合增益 3.06×）**；FD 对拍全过；smoke 3/3 |
| D-83 | **混合×多波长加权联合（Track A 纵深收官）** | 参数化×目标矩阵**全打通**（参数化∈{拓扑,形状,混合} × 目标∈{单场能,谱形,多波长}）：混合参数化共享形状主干+拓扑带，多波长加权 FOM=Σw_λ·FOM_λ（固定 dl 只变 omega）+ **分块归一化**（形状/拓扑各自尺度，保证拓扑带参与）+ Pareto 前端：加权 imp **19.35× vs 纯形状多波长基线（增益 3.18×）**，逐波长 22.2×/16.5×，Pareto 3 点；FD 对拍 9.8e-4；smoke 3/3 |
| D-84 | **3D adjoint 形状逆设计（破 3D 诚实边界）** | adjoint 从 2D 推向 **3D Yee 交错网格**（6 分量，更新算子**显式转置**伴随——数值 Mᵀ 对拍 **1e-15**，不依赖 torch/jax）+ 平板波导宽度曲线形状（K 控制点软边界 + 5 层核心 + 可制造 DRC）：imp **2.02×**（聚焦 taper 成形），3D adjoint FD 对拍 **9.4e-6**、形状梯度 8.2e-4；smoke 3/3 |
| D-85 | **3D 截面形状逆设计（3D 纵深）** | 把 z 截面也变成形状自由度——**宽度 w(x) × 厚度 h(x) 双软边界**（z 底固定 0、顶 z_top=h(x)，处处可导；联合梯度 [dFOM/dw ⊕ dFOM/dh] + 双界 DRC）：imp **3.17×**（**比平板 2.02× 提升 57%——厚度自由度增益显著**），截面梯度 1.0e-2；smoke 4/4 |
| D-86 | **3D 逆设计 × 端口 S 参数联合验收（补闭环最大缺口）** | 战略审计最大缺口：3D 逆设计无端口级验收。打通 **3D adjoint 场能优化 → 独立 3D CW 端口核**（S11/S21，src_profile 可配）→ **双独立确认**：FOM imp **1.88× 且 S21 0.132→0.211（1.60×）同向双过**；能量守恒 S11+S21≈1；**关键物理认知：聚焦 FOM ≠ 透射 S21**（两端收窄 taper 模式失配）→ w_min=4/init_w=6 对齐；smoke 3/3 |
| D-87 | **谱形目标 × 3D 截面（多波长加权联合）** | 2D 谱形/多波长目标扩展到 3D：**物理网格固定只变 omega**（归一化网格陷阱免疫）+ **多波长加权联合梯度**（分块归一化 w/h 各自尺度）+ 全波长线搜索：加权 imp **3.13×**（逐波长 3.18×/3.15×/3.06× 三波长同向 ≥3×）、联合梯度 **4.2e-4**、DRC 双界全过；smoke 5/5 |
| D-89 | **3D adjoint numba 化性能升维（突破 3D 域规模天花板）** | 3D Yee 核 + 显式转置反向 **prange 并行 JIT**（`backend` 参数 auto/numba/numpy，**无 numba 自动回退**）：forward 加速 **44 域 8-11× / 64 域 17-21× / 80 域 22-29×（最大域 ≥20×）**，与 numpy **bit-level 一致（FOM rel ≤ 3.7e-16）**；优化链路 64 域 **4.4-5.2×**（imp 完全一致）；梯度 2-5×；smoke 6/6（含 numba 一致性 + 回退） |
| D-88 | **QEDA 求解器级补强 · transmon-resonator 色散读出（量子蓝海占位）** | 三能级 transmon + Fock 谐振器**联合严格对角化**（D-43 二能级 JC 升级，引入 |f⟩ 态非谐性）：**真实色散 χ=g²α/(Δ(Δ+α))**（Blais 修正）↔ 数值 rel **2.5%**，二能级近似 rel 77.5%（**α 修正必要性 31×**，χ 为负即非谐性标志）；输出 **n_crit / Purcell 率 / AC Stark / 拉比自洽**（0.02%）；smoke 3/3（含色散区失效负例） |
| D-91 | **QEDA 纵深三件套（多能级展开 · 驱动场 · 读出串扰）** | ①多能级电荷基底展开：χ 3→6 能级**收敛 0.495%**（<1% 证明三能级自洽）+ Blais 解析 rel 1.98%；②驱动场 RWA：共振 **Rabi 自洽 rel 0** + 失谐 **AC Stark Ω²/4δ 对拍 rel 0.39%**；③多 qubit 读出串扰：共享谐振器媒介 **ZZ 耦合 J_zz=0.000831 GHz**（g=0 自洽 + 互换对称 rel 0 + |J_zz/χ|=0.369 弱耦合）；smoke 4/4（含驱动强场 + 串扰简并负例） |
| D-92 | **3D voxel 拓扑逆设计（3D 纵深最后一环）** | 3D 设计区**潜伏密度 + tanh 投影 beta 延拓**（先柔后硬二值化，可制造性内建）+ 3D adjoint 显式转置梯度链式：imp **6.30×**（44 域 iters=24）、拓扑梯度 FD 对拍 **5.9e-3**、二值化 **20.8%**（beta_max=16 重投影）；Track A 3D 参数化矩阵补上拓扑列；smoke 7/7 |

## WebUI（五十二面板，设计闭环可视化）

LDA 自带零依赖 WebUI（`python lda/lda_webui/deploy.py start`，默认 `http://127.0.0.1:8787`），首屏自动演示全部闭环：

`①求解器验收` `②1D FDTD` `③Mie` `④FDFD` `⑤耦合器验收` `⑥统一 IR` `⑦TMM` `⑧B 基准题` `⑨版图流水线` `⑩Bootstrap` `⑪多层验证` `⑫对抗基准` `⑬器件库（含量子双验证）` `⑭设计→验证闭环` `⑮环形 add-drop 产品链路` `⑯agent 逆设计框架` `⑰量子逆设计闭环` `⑱WDM 多环系统` `⑲readout 混合链路` `⑳统一设计包` `㉑N-qubit 频率复用读出` `㉒单发读出保真度预算` `㉓N-qubit 逐 qubit 保真度` `㉔WDM×readout 混合巨型系统` `㉕方向耦合器设计闭环` `㉖耦合器×WDM（标定库驱动：gap/波长/全网格三模式）` `㉗方向耦合器×量子读出（分束网络供电控制线）` `㉘分束网络×WDM（解复用→每信道分束树）` `㉙伴随法拓扑逆设计（主权 adjoint FDTD）` `㉚逆设计接入设计→验证引擎（method=adjoint）` `㉛真实版图基元库（foundry-ready）` `㉜端口 S 参数验收（MMI 2D FDTD + ORACLE 对拍）` `㉝3D 端口 S 参数验收（SOI 220nm · numba 核）` `㉞光栅耦合器端口验收（光栅方程 ORACLE）` `㉟真实基元接入设计流水线（Track B 收口）` `㊱热光可调 WDM（热光相位 shifter + 物理定律锚）` `㊲量子门/纠错拓扑（surface code + cross-resonance）` `㊳大规模系统基准（WDM 8×qubit 8 联合压测 + 容量/IL/间隔/网格边界）` `㊴L0 IR 开放标准（规范+JSON Schema 零漂移校验）` `㊵验证合约工业化（CI 全量回归 + 性能基准）` `㊶谱形目标逆设计（分束比/模式匹配/多波长谱形 FOM）` `㊷形状逆设计 + 多目标联合（宽度曲线控制点 + Pareto 前端）` `㊸形状+拓扑混合逆设计（分层表达：形状主干 + 拓扑微调带）` `㊹混合×多波长加权联合（参数化×目标矩阵全打通）` `㊺3D adjoint 形状逆设计（3D Yee 显式转置伴随）` `㊻3D 截面形状逆设计（宽度 × 厚度双软边界）` `㊼3D 逆设计 × 端口 S 参数联合验收（双独立确认）` `㊽谱形目标 × 3D 截面（多波长加权联合）` `㊾3D adjoint numba 性能基准（大域 20×+）` `㊿QEDA 求解器级补强 · transmon-resonator 色散读出（三能级严格求解）` `51 QEDA 纵深三件套（多能级展开 · 驱动场 Rabi/AC Stark · 读出串扰 ZZ 耦合）` `52 3D voxel 拓扑逆设计（潜伏密度 + 二值化投影 · 3D 纵深最后一环）`

## PDK 标定库（真实 FDTD 实测沉淀，设计时秒级加载）

bus↔ring 耦合本质是方向耦合器——κ_c 由 2D FDTD（D-55 双点标定）实测并沉淀为 PDK 标定文件（一次性后台标定，设计时秒级加载/插值），驱动 WDM 环耦合段设计：

| 标定文件 | 维度 | 说明 |
|---|---|---|
| `lda_agent/data/kappa_calibration.json` | κ_c(gap) 一维 | 5 点 gap 扫描（dl=0.039µm 高分辨率），D-57 |
| `lda_agent/data/kappa_wavelength_calibration.json` | κ_c(λ) 一维 | 3 点波长扫描（gap=0.3 基线），D-59 |
| `lda_agent/data/kappa_grid_calibration.json` | κ_c(gap,λ) **二维** | **9 点全网格**，双线性插值直接查表（D-60，最终形态） |

三种模式（`wdm_coupler` CLI/API 可选，优先级 grid > wavelength > gap 一维），每信道独立 k_ring = sin(κ_c·L_couple)，最弱耦合保守验收；诚实标注 L_couple=2√(2R·gap) 为环形耦合近似，并显式报告 FDTD 校准 vs 解析假设偏差（D-57 实测解析偏乐观 4.6 倍）。

## 统一设计包规范（对外标准 · 11 kind）

- 正式规范文档：[docs/design_package_spec.md](docs/design_package_spec.md)（schema 定义 / kind 注册表 / 校验规则 / 扩展指南）
- 机器可读 JSON Schema：[docs/design_package_schema.json](docs/design_package_schema.json)（draft-07，jsonschema 校验全部 kind conforms）
- kind：`add_drop` `quantum` `wdm` `readout_chain` `multiqubit` `readout_fidelity` `multiqubit_fidelity` `mixed_system` `coupler` `wdm_coupler` `splitter_readout`

## 目录结构

```
lda/                     核心软件包（主权求解器 + agent + 设计引擎 + harness）
  lda_solver/            FDTD/FDFD/Mie/TMM/Transmon/Resonator/Coupler 自研求解器
  lda_agent/             设计→验证闭环、逆设计框架、WDM/readout 系统级设计、AI-dev 写核
  lda_qeda/              量子门库 + surface code + cross-resonance（D-74 QEDA 容错拓扑设计）
  lda_agent/large_scale_bench.py  大规模系统基准（D-75 · WDM×qubit 联合压测 + 边界扫描）
  lda_design/            设计引擎 + 统一设计包规范（DesignPackage）
  lda_ir/                统一 IR（光子+量子，schema v0.3，PhysicsAnchor）
  lda_l2/                器件库（已验证资产）+ GDS 编码器 + DRC + 版图仿真
  lda_harness/           确定性比对裁判（13 标准题物理定律锚 B1-B13）
  lda_webui/             零依赖 WebUI（五十二面板）
  run_ci_regression.py   验证合约工业化·全量回归统一入口（D-77，自动发现 63 smoke）
  run_perf_bench.py      求解器性能基准（D-77，numba/GPU 加速比 + 基线漂移监控）
  run_perf_adjoint3d.py  3D adjoint numba 性能基准（D-89，大域 forward ≥20× + bit-level 一致性）
  lda_solver/port_sparams_3d.py  3D 端口 S 参数核（D-72/86，src_profile 可配源截面）
  lda_agent/port_acceptance.py   3D 逆设计 × 端口联合验收（D-86，双独立确认）
  lda_solver/hybrid_inverse.py  混合逆设计核（D-82/83，形状主干 + 拓扑微调带 + 多波长联合）
  lda_agent/hybrid_design.py    混合逆设计入口（D-82/83，纯形状基线对比 + Pareto 前端）
  lda_solver/adjoint_fdtd3d.py  3D adjoint 逆设计核（D-84，3D Yee 显式转置伴随 + 平板形状）
  lda_agent/adjoint3d_design.py 3D adjoint 设计入口（D-84，FD 对拍 + 优化验收）
  lda_solver/shape_inverse.py  形状逆设计核（D-81，宽度曲线控制点 + 可制造性 DRC）
  lda_agent/multi_objective_design.py  多目标联合（D-81，多波长加权 + Pareto 前端）
docs/                    ir_spec.md + ir_schema.json（L0 开放标准）· design_package_spec.md + design_package_schema.json
```

## 快速开始

```bash
# ① 设计→验证闭环（4 器件：WG/Bragg/Transmon/Ring）
python lda/run_design_demo.py

# ② agent 逆设计通用框架（4 器件同一框架）
python lda/run_inverse_design_smoke.py

# ③ WDM 多环级联系统（4 信道）
python -m lda.lda_agent.wdm_system --channels "1550,1552.5,1555,1557.5"

# ④ N-qubit 频率复用读出（光子-量子混合）
python -m lda.lda_agent.multiqubit_readout --f01s "4.8,5.0,5.2"

# ⑤ N-qubit 逐 qubit 保真度（D-46×D-47 集成，逐 qubit T1）
python -m lda.lda_agent.multiqubit_fidelity --f01s "4.8,5.0,5.2" --t1_us "20,15,25"

# ⑥ 混合巨型系统（光子 WDM 分波 + 量子读出同一网表）
python -m lda.lda_agent.mixed_system --wdm_channels "1550,1553,1556" --f01s "4.8,5.0,5.2"

# ⑦ 方向耦合器设计闭环（目标分束比 → 2D FDTD 标定 → 迭代收敛）
python -m lda.lda_agent.directional_coupler --target_cross 0.5 --gap 0.3

# ⑧ 耦合器 × WDM 组合（FDTD 标定 PDK 文件驱动 gap 选择；--wavelength 波长相关 / --grid 全网格双线性插值）
python -m lda.lda_agent.wdm_coupler --channels "1550,1553,1556" --gap_scan "0.25,0.30,0.35" --grid

# ⑨ 方向耦合器 × 量子读出（光子分束网络供电量子读出控制线）
python -m lda.lda_agent.splitter_readout --f01s "4.8,5.0,5.2"

# ⑩ 确定性比对裁判（13 标准题物理定律锚）
python lda/run_harness.py --ai

# ⑪ GPU 实跑激活（L2-B 第三步：CUDA 检测 → 5 例锚 selfcheck → cuda↔cpu bit-equivalent 互证 → 加速比）
python lda/lda_solver/activate_gpu_fdtd3d.py

# ⑫ WebUI（三十六面板，首屏自动演示）
python lda/lda_webui/deploy.py start --port 8787
```

## 仓库镜像

- GitHub: https://github.com/iduyuhe/LDA
- Gitee:  https://gitee.com/i4hub/LDA

## 变更记录

见 [CHANGELOG.md](CHANGELOG.md)（v0.2：设计→验证闭环引擎 + 统一设计包规范；**v0.3：GPU 激活 + 量子读出最终形态 + 混合巨型系统**；**v0.4：真实版图基元 + 2D/3D 端口 S 参数验收 + 伴随法逆设计 + 流水线真实化**）。

## 参与共建 · 反向悬赏

LDA 把「真实测量 + 开放对抗题」作为信任地基（对抗纯 AI 互证）。欢迎社区 / 退休专家 / 学生
提交**实测语料**与**让 AI 求解器翻车的对抗题**：

- 提交通道：`New Issue → 实测语料提交` / `对抗基准题提交`（结构化模板）
- 悬赏与评审机制详见 [BOUNTY.md](BOUNTY.md)
- 征集字段与 `lda/lda_harness/seed_empirical.json` 完全对齐

## 双引擎招募（学生 + 退休专家）

LDA 开源生态靠**双引擎**驱动——有时间有热情的**学生**、有资源有情怀的**退休专业人士**。完整招募入口、布点、话术与顾问委员会架构见 [**RECRUIT.md**](RECRUIT.md)：

- 学生线（毕设/竞赛/科研挂钩、good-first-issue）→ [LDA_学生贡献者招募方案.md](LDA_学生贡献者招募方案.md)
- 退休专家线（EDA 老炮/光电退休研究员/院士级，分层顾问委）→ [LDA_退休专家招募话术与顾问委员会架构.md](LDA_退休专家招募话术与顾问委员会架构.md)

## 项目介绍物料（对外一整套）

想快速了解 / 转发 / 触达不同对象，直接用这套分受众物料：

- **总览**：[LDA_项目介绍.md](LDA_项目介绍.md)（定位/证据/路线图/参与方式 + 全文档索引）
- 一页纸·技术贡献者：[LDA_一页纸_技术贡献者.md](LDA_一页纸_技术贡献者.md)
- 一页纸·双引擎招募：[LDA_一页纸_双引擎招募.md](LDA_一页纸_双引擎招募.md)
- 一页纸·合作对接（晶圆厂/合作方）：[LDA_一页纸_合作对接.md](LDA_一页纸_合作对接.md)
- 一页纸·产业投资：[LDA_一页纸_产业投资.md](LDA_一页纸_产业投资.md)

## 许可证

[MIT](LICENSE)
