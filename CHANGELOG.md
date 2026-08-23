# Changelog

## v0.2（2026-08-21 · git tag v0.2）

**里程碑：设计→验证闭环引擎 + 统一设计包规范——LDA 从"组件集"成为"可用系统"**

### 核心能力（D-36~D-48，全部实测全绿 + WebUI 二十二面板）

- **D-36 设计→验证闭环引擎**：给定设计目标 → 物理定律 ORACLE 瞬时搜索 → top-K 真实求解器双重验证（解析契约 + 严格数值物理自洽，纯 numpy 零 GPU）→ 返回被验证过的最优设计。4 器件全覆盖（WG/Bragg/Transmon/Ring）。
- **D-37 环形 add-drop 完整产品链路**：目标 FSR → 半径反解 → 双 bus 版图（GDSII/SVG，自写零依赖编码器）→ DRC → bus 真实 FDTD → 耦合/损耗预算 → 可制造设计包。
- **D-38 agent 逆设计通用框架**：声明式注册表，同一框架落地 4 器件（Ring/Bragg/Transmon/AddDrop，跨 match/threshold、连续/离散、光子/量子）；新器件 = 注册一条 spec 零框架改动。
- **D-39 量子域补强**：Resonator（λ/4 闭式↔离散 TL 严格本征值，rel=0.25%）+ Coupler（解析 J↔441 维严格对角化，rel=4.15%）双验证——量子域三器件全带一等真实物理验证入口。
- **D-40 统一 IR 深化**：PhysicsAnchor 一等字段 + schema 受控升级 v0.3（0.2 向后兼容）；harness 新增 B12/B13 量子锚（**13 题 B1-B13**）。
- **D-41 量子 agent 逆设计闭环**：目标 f01/f0/J → IR → 闭式物理反解 → D-39 严格数值双验证 PASS（与光子栈对称）。
- **D-42 WDM 多环级联系统**：IR 网表驱动 N 环分波，级联传递 + 系统验收（IL≤3dB/XT≥15dB/单 FSR 防混叠）；超规格设计正确拒绝。
- **D-43 光子-量子混合链路**：芯片级 dispersive readout（Transmon↔readout↔feedline），JC 精确对角化 ↔ 色散 χ 交叉验证（共振分裂=2g 自洽）。
- **D-44 统一设计包规范**：DesignPackage schema v0.1（ir+design+verification+artifacts+honest_notes，verification.passed 唯一验收门）+ 正式 spec 文档 + JSON Schema（draft-07，全部 kind conforms）。
- **D-45 WDM 纵深（指标驱动）**：XT 指标反解 gap（bisection）、级联插损预算表、单 FSR 信道上限。
- **D-46 N-qubit 频率复用读出**：N qubit 沿公共力线错开读出频率（间隔≥3×κ_r），hanger 级联透射 + dip 可分辨判据（中点 T>0.5）；光子-量子混合系统级。
- **D-47 单发读出保真度预算**：相位积分 SNR 模型 + T1 弛豫污染 + 最优读出时间 t_m* 扫描 + 非破坏性约束（n̄≤100）；F1≥0.95 独立门槛。
- **D-48 正式发布准备**：README v0.2 发布版（架构分层图 + 能力阶梯表 + 面板清单）+ CHANGELOG + git tag v0.2（GitHub/Gitee 三端同步）。

### 新增/变更

- `lda_design/`（设计引擎 + 设计包规范）、`lda_ir/`（统一 IR）、`lda_webui/`（零依赖 WebUI 二十二面板）
- `lda_agent/`：design_engine 派生的 ring_adddrop / inverse_design / quantum_design / wdm_system / qubit_readout_chain / multiqubit_readout / readout_fidelity / multiqubit_fidelity / mixed_system
- harness 基准题 11 → **13**（B12 λ/4 f0、B13 耦合 J）
- 文档：`docs/design_package_spec.md` + `docs/design_package_schema.json`

### 兼容性

- IR schema 0.2 → 0.3（受控升级，0.2 遗留模型仍可校验）

## v0.3（2026-08-21 · git tag v0.3）

**里程碑：求解器 GPU 激活 + 量子读出最终形态 + 混合巨型系统 + 方向耦合器/耦合器×WDM 闭环（D-49~D-57）**

- **D-49 设计包 spec/schema 扩展至 6 kind**：正式文档与代码注册表零漂移（§4 注册表/§7 artifacts/§9 校验枚举/变更记录 + JSON Schema enum 同步）。
- **D-50 fdtd3d GPU 实跑激活（L2-B 第三步验收 PASS）**：RTX 5060 Ti 实测——cuda 物理定律锚 selfcheck 4 例 PASS、**cuda↔cpu fp64 互证 5 例 bit-equivalent（max_rel=0.00e+00）**、greens N=120 cuda 19.43s；诚实说明消费卡 fp64 阉割（GPU 收益在显存容量，算力优先 numba-cpu 43.1×）。
- **D-51 N-qubit 复用读出逐 qubit 保真度**：D-46×D-47 集成——逐 qubit T1/n̄ 独立预算（t_m*/SNR/F），坏 qubit 独立 FAIL 不影响他者；设计包 7 kind。
- **D-52 多环 WDM × 量子读出混合巨型系统**：光子 WDM 分波（D-42）+ 量子读出（D-51）**同一 IR 网表**（10 器件+8 网表）——信道↔qubit 1:1 映射 + 系统联合验收；诚实标注光↔微波物理独立（桥接为接口规划）；设计包 **8 kind**。
- **D-53 README/CHANGELOG 更新**：能力阶梯表 13 行、二十四面板、8 kind 清单、快速开始 9 步——对外基线文档零漂移。
- **D-55 方向耦合器设计闭环**：目标分束比 → **2D FDTD 双点标定 κ**（秒级真实求解器）→ CMT 反解 L（物理长度=有效长度+offset）→ 实测-修正迭代收敛（50:50 命中 cross=0.503）；设计包 **9 kind**。
- **D-57 耦合器 × WDM 组合**：**FDTD 标定 PDK 文件**驱动 WDM 环耦合段 gap 选择——κ_c(gap) 5 点高分辨率实测沉淀为标定文件（一次性后台 ~20 分钟，设计时秒级），k_ring=sin(κ_c·L_couple) 换算后 gap 扫描设计；**诚实发现：k_ring=0.107 vs 解析假设 0.488（比值 0.218，解析偏乐观 4.6 倍）**；设计包 **10 kind**。

### 新增/变更（v0.3）

- `lda_agent/`：multiqubit_fidelity / mixed_system / directional_coupler / wdm_coupler + `data/kappa_calibration.json`（PDK 标定文件）
- `docs/design_package_spec.md` + `design_package_schema.json`：kind 6 → **10**
- WebUI：二十二 → **二十六**面板（㉓ 逐 qubit 保真度 / ㉔ 混合巨型系统 / ㉕ 方向耦合器设计闭环 / ㉖ 耦合器×WDM 组合）
- README：能力阶梯表 D-36~D-57、二十六面板、10 kind、快速开始 11 步
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 10 项枚举）

## v0.3.1（2026-08-22 · git tag v0.3.1）

**里程碑：PDK 标定库最终形态——κ_c(gap,λ) 全网格直接查表，无需任何解析假设（D-58~D-60）**

- **D-58 README/CHANGELOG 更新至 D-57**：能力阶梯表 15 行、二十六面板、10 kind、快速开始 11 步——对外基线文档零漂移。
- **D-59 波长相关标定库（κ_c(gap,λ) 二维）**：新增 `data/kappa_wavelength_calibration.json`（3 点 κ_c(λ)，gap=0.3 基线，FDTD 双点标定）；`wdm_coupler` 新增 `wavelength_calibrated` 模式——分离变量近似 κ_c(gap,λ)≈κ_c_gap(gap)·[κ_c_wl(λ)/κ_c_wl(1.55)]（诚实标注）→ 每信道按 λ 独立 k_ring → 最弱耦合保守验收 + 波长单调检查；实测 κ_c(λ)=0.0213/0.0241/0.0270（1.50/1.55/1.60，**单调增幅 ~27% 物理正确**）。
- **D-60 κ_c(gap,λ) 全网格标定库（最终形态）**：新增 `calibrate_kappa_grid.py`（9 点 gap×λ 全网格标定脚本，后台 ~81s）+ `data/kappa_grid_calibration.json`（二维网格，9 点全非缠绕）；`wdm_coupler` 新增 `grid_calibrated` 模式——**双线性插值直接查表**（替代分离变量近似，无需任何解析假设）→ 每信道独立 k_ring → 最弱耦合保守验收（优先级 grid > wavelength > gap 一维）；实测 3 信道每信道 k_ring=[0.10755/0.10833/0.1091] 单调、WDM 5/5 IL≤0.32dB/XT≥43.4dB，负例（弱耦合/超 FSR/标定缺失）正确 FAIL。

### 新增/变更（v0.3.1）

- `lda_agent/`：calibrate_kappa_grid.py（全网格标定脚本）+ `data/kappa_wavelength_calibration.json` + `data/kappa_grid_calibration.json`（PDK 标定库三文件齐备）
- `wdm_coupler`：wavelength_calibrated / grid_calibrated 两种标定模式（CLI `--wavelength` / `--grid`，API 同参）
- WebUI：二十六面板（㉖ 扩展：gap/波长/全网格三模式）
- README：能力阶梯表 D-36~D-60、新增「PDK 标定库」章节、快速开始 11 步（⑧ 升级 --grid 全网格模式）
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 10 项枚举，延续）

## v0.3.2（2026-08-22 · git tag v0.3.2）

**里程碑：方向耦合器 × 量子读出——光子分束网络供电量子读出控制线（D-63）**

- **D-63 方向耦合器 × 量子读出（新 kind=splitter_readout）**：新增 `lda_agent/splitter_readout.py`——**二叉树级联 DC 分束网络**（权重二分递归建树，每级 target_cross=右子树权重/节点权重，每级 D-55 `design_coupler` **真实 2D FDTD 设计闭环**，级联功率=路径 FDTD 实测分束比之积）→ **readout_power_budget**（每 qubit 有效 n̄=nbar0×p_actual，P∝n̄、SNR∝√n̄，D-47 复用）→ **统一 IR 网表**（power+DC×m+Transmon×N+Resonator×N+objectives）→ 联合验收（分束命中 Δ≤0.05/SNR≥3.0/F≥0.98/IR/诚实标注光↔微波拓扑同构、物理独立）。实测 3 qubit：2 级 DC（dc1 1/3→FDTD 0.337、dc2 1/2→FDTD 0.502）→ 功率分配 [0.330/0.333/0.337]（Δ≤0.0034）→ SNR∈[3.95,3.99] F∈[0.9996]；4 qubit 3 级 DC PASS；负例（极端权重/低 nbar0/长度不匹配）正确 FAIL；**设计包 11 kind**。

### 新增/变更（v0.3.2）

- `lda_agent/`：splitter_readout.py（方向耦合器 × 量子读出联合设计）
- `lda_design` + spec/schema：kind 10 → **11**（加 `splitter_readout`，spec §4 注册表 / §9 枚举 / 变更记录 0.1.6 同步）
- WebUI：二十六 → **二十七面板**（㉗ 方向耦合器×量子读出：DC 网络 / 功率分配 / 每 qubit 预算，首屏自动演示纳入）
- API：`/api/splitter_readout`（nbar0/delta/g/kappa_r/T1_us/eta/N_amp/weights 全透传）
- README：能力阶梯表加 D-63 行、二十七面板、11 kind、快速开始 12 步（新增 ⑨ splitter_readout）
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 11 项枚举）

## Unreleased（v0.3.2 之后 · D-66~D-79）

**里程碑：PDK 标定库分辨率修正（D-68）+ 伴随法梯度拓扑逆设计（D-69）+ 逆设计接入 D-36 引擎（D-70，M4 Track A 收口）+ 真实版图基元库（D-71）+ 真实 2D FDTD 端口 S 参数验收（D-72，M5 Track B）+ 3D 端口验收与闭环集成（D-72★）+ 光栅耦合器端口验收（D-78）+ 真实基元接入设计流水线（D-79，M6 v0.4 门槛达成）**

- **D-66 标定库 × 分束网络**：`splitter_readout_cal` 模式——DC gap 由 κ_c(gap) 标定库驱动设计（标定 5/5 PASS）。
- **D-67 分束网络 × WDM（新 kind=wdm_splitter 流程）**：`lda_agent/wdm_splitter.py`——WDM 多环级联解复用（D-42 + D-57 标定库驱动 gap）→ 每信道 drop 口接二叉树级联 DC 分束树（D-63 复用，每级 D-55 真实 2D FDTD 设计）→ 信道输入 = drop 扣除实测 IL 的剩余功率（10^(-IL/10) 诚实标注）→ 统一 IR 网表（Ring×N + DC×M）+ 联合验收。纯光子域，无跨物理域声称。
- **D-68 PDK 标定库 4×5 升级**：诊断性 5×5 dl40 标定发现原 3×3（dl20）中 gap 0.25/0.30 的 κ_c 完全相同（分辨率假象）→ 生产库升级为干净 4×5 网格（gaps 0.25/0.30/0.35/0.40 × 5 波长 = 20 点，dl40，κ_c 沿 gap 与 λ 双轴单调，双线性插值查表）；`calibrate_kappa_grid.py` 参数化（--gaps/--wls/--dl_factor/--out）成复用基础设施。
- **D-69 伴随法梯度逆设计核（adjoint FDTD，M4 Track A）**：`lda_solver/adjoint_fdtd.py` + `lda_agent/adjoint_design.py`——对主权 2D FDTD（TEz，Yee + 海绵 PML，零额外依赖）实现 **adjoint 灵敏度**（FDTD 更新算子**显式转置**，数值 Mᵀ 逐元素对拍 ~1e-15），从"参数扫描 + 闭式反解"升级为**梯度驱动拓扑逆设计**。工程决策（诚实记录）：CW 源 + P_out 目标无上界（高 Q 谐振腔蓄能病态）→ **高斯脉冲源 + 窄孔径收集场能 FOM**（能量有界，adjoint 观测 obs=2·Ez 无 DFT/共轭陷阱）；优化器 = 密度投影（beta 延拓 2→14 二值化）+ **回溯线搜索**（FOM 单调不降）。M4 双标准实测：①adjoint vs 中心有限差分对拍 max_rel_err=**0.0**（≤0.15）②一例拓扑逆设计 improvement=**15.1×**（≥1.5，110×90 网格 3996 体素，FOM 36.2→548）。FOM 语义诚实标注：收集场能（聚焦增益可致 T>1），非功率透射。
- **D-70 逆设计目标泛化接入 D-36 引擎（method=adjoint，M4 Track A 收口）**：`lda_agent/design_loop.py` 的 `DesignAgent` 统一入口按 **method** 分流——默认 `scan`（布拉格参数扫描，原路径零改动）+ `adjoint`（伴随梯度拓扑逆设计）；`l1_protocol.DesignTarget` 新增 `method` 字段透传意图。目标从"布拉格周期数"泛化为**「把指定孔径内的收集场能最大化」**（设计区/孔径/材料对比度/波长/分辨率全部由意图 extra 透传 `AdjointProblem`）。闭环 = 均匀平板初值 → FD 对拍锚（adjoint vs 中心有限差分 max_rel_err≤0.15）→ 密度投影 + 回溯线搜索梯度优化（improvement≥1.5）→ 死标量验收，输出 `DesignOutcomeReport` 兼容格式（target/accepted/iterations/loop_trace/verdict，final_oracle_metric=均匀平板初值基线，诚实标注）。M4 双标准实测：smoke 4/4（正例 improvement=15.13× + 空设计区 FAIL + 0 迭代 FAIL + 布拉格兼容）、全参报告 improvement=**15.13×**（FOM 36.2→547.9，FD 对拍 err=2.4e-5）。LLM 不进判决路径。
- **D-71 真实版图基元库（Track B 起步，foundry-ready）**：`lda_l2/primitives.py`（纯几何核心，零依赖）——①**Taper**（线性/绝热余弦轮廓，两端斜率 0 减模式失配）②**Euler 弯**（clothoid：曲率 0→1/R→0 连续无折角，90°/180°/45° 终点角误差 &lt;0.01°）③**MMI 1×2 对称分束**（输入 taper + 多模干涉区 + 双输出 taper，7 元素）④**光栅耦合器**（周期部分刻蚀齿，齿宽=Λ·duty，22 元素）。注册进 `gds_export.geometry_desc`（GDS/SVG/DRC 单一来源）+ `drc.drc_check_device`（min_width/min_space/min_bend_R）。`lda_agent/primitives_design.py` 封装：GDS 编码（round-trip 回读一致）+ DRC 自查 + SVG 预览 + 死标量验收（smoke 3/3：4 基元全过 + 非法 kind 优雅 + min_width 违规 FAIL；报告 PASS，GDS 628B/8312B/1936B/1462B）。**诚实边界**：只交付 foundry 可接受几何；分束比/透射谱等电特性归 D-72 2D FDTD 端口 S 参数验收，不做性能声称。
- **D-72 真实 2D FDTD 端口 S 参数验收（M5 Track B 首个里程碑）**：`lda_solver/port_sparams.py` + `lda_agent/sparams_design.py`——对 D-71 真实基元（MMI 1×2 对称分束器）做**全 2D FDTD 端口透反射谱**验收：输入 CW 激励 → 输出/回波端口 DFT 收集 → 输入功率归一 → **S 参数谱**（|S11|² 回波 / |S21|² 上输出 / |S31|² 下输出，能量守恒自动满足）。死标量验收（LLM 不进判决路径）：仿真有效 + 双输出平衡度 ≤0.15 + 透射 ≥0.05（自成像对称 ORACLE 物理定律锚）+ **DRC 工艺规则从真实 SOI 180nm PDK 注入**（NOEIC/CUMEC/SITRI design_rules → rules_from_pdk，D-21 落地，3/3 全绿）。实测（W=4/L=12µm，5 波长，dl=1.55/20，1200 瞬态）：**平衡度 max=0.078**（≤0.15）、中心波长 **S11=0.094 / T=0.906**、5/5 波长全过；smoke 3/3。**关键 bug 修复（诚实记录，22:40 修订）**：①偶数 Ny 网格对称轴在 y=−dl/2 → 多模区上下栅格化差一格 → S21/S31 系统性不对称 → **Ny 取奇数根治**；②**栅格化范围公式误加 Ly 偏移 → mask 为空（core frac=0.0）**——此前验收基于空 mask 伪结果（均匀介质源扩散的"好看"数值），22:40 定位修复（j(y)=y/dl+(Ny−1)/2 无偏移）后**报告重新生成（真实 S 参数），验收仍 PASS**。教训：mask 空时 y-flip 恒对称——对称性验证必须同时断言 mask 非空。诚实边界：2D TEz 近似；分束比绝对值依赖自成像长度精确设计，不声称与商业 EDA 数值库逐点一致。
- **D-72 深化 3D 端口 S 参数验收（SOI 220nm，mmi/dc/ring）**：`lda_solver/port_sparams_3d.py` + `lda_agent/sparams_3d_design.py`——**MMI / 方向耦合器(DC) / 环形谐振器(Ring)**（SOI 220nm 波导层 + 上下包层）**全 3D FDTD** 端口透反射谱（复用已验证 numba 核 `_fdtd3d_core`，零新依赖；numba 需 `python envs/default` venv）：3D 波导截面匹配源注入（TE 主极化 Ez，矩形近似基模）→ 多端口 DFT 收集 → 输入功率归一 → S 参数谱 → 死标量验收：**MMI** 平衡度 ≤0.15、**DC** cross_frac 端点趋势（CMT 物理，cf≈0.5 恰在 sin² 拐点 π/4 处导数最大、数值噪声放大 → 端点趋势 + 容差而非逐点严格单调，诚实标注）、**Ring** drop 谐振峰检出（Lorentzian ORACLE），均 + 仿真有效 + 透射 ≥0.05；附 **2D↔3D 连续性对拍诊断**（垂直模式物理差异，非判据）。实测：MMI 平衡度 0.015-0.083、DC cf 端点上升、Ring drop 峰检出（max 0.202/med 0.140），3/3 全过；smoke 5/5（三器件 + 非法 kind + out_gap 离线）；WebUI ㉝ 面板（mmi/dc/ring 选择）。**已接入设计闭环**：`DesignAgent` 新增 `method="sparams3d"` 分支（`_run_sparams3d`）——意图解析 kind + 几何 → 3D FDTD S 谱 → 死标量验收 → `DesignOutcomeReport` 兼容输出（iterations=波长数、loop_trace 每波长 S11/S21/S31、final_metric=中心波长 T_total）；无 numba 环境优雅 FAIL。smoke 4/4（MMI/DC 闭环 + 非法 kind + 布拉格兼容）；三器件闭环报告 `reports/sparams_loop_d72.json` PASS。DesignAgent 三 method 齐备：scan / adjoint / sparams3d。**关键坑（诚实记录）**：①3D 源 profile 过宽能量泄漏 → 波导截面匹配矩形分布；②**sponge 自适应 clamp（≤Ny/4、Nz/4）**——小域 Nz≈19 时两端 sponge 重叠覆盖波导层，场被整体吸收（S11=1.0 伪全反射）→ z 包层加厚 + clamp 根治；③双向源后向波使 S11 偏高（仿真设定伪影，判据不依赖 S11）。
- **D-78 光栅耦合器端口验收（M6 v0.4 门槛起步 · 光栅方程 ORACLE）**：`lda_solver/port_sparams_gc.py` + `lda_agent/gc_design.py`——4 基元最后一块电特性验收。**几何修正（诚实记录）**：D-71 GC 原"齿区主体+齿"同层合并（GDS 合并填充语义）实心=直波导、无周期调制 → D-78 修正为真实方波光栅（齿=硅、凹槽=包层）。**2D FDTD 端口透射谱**：CW 注入 → thru/in 归一 → 透射谷检测（周期调制耦合损耗，预测窗内局部谷——谱为级联干涉梳结构，全局最小谷≠光栅方程谷）→ 谷位置 vs **光栅方程** λ_rad=Λ·n_eff 解析预测对拍（n_eff 由同宽直波导 FDTD 双监视点相位差法独立测得，**非拟合**）+ **Λ 扫描趋势锚**（dλ/dΛ=周期结构实测 n_eff）。死标量验收：**谷检出 depth≥0.10 + 谷位置 rel≤0.15 + 趋势斜率 rel≤0.10**。实测：neff=3.699、谷 λ=2.283µm vs 预测 2.515µm（**rel=0.092**）、Λ 扫描斜率 3.290 vs 周期结构 neff 3.357（**rel=0.020**）、谷深 0.996，**验收 PASS**；smoke 3/3（正例 + duty=1.0 无调制 FAIL + Lambda=0 优雅 FAIL）；报告 `reports/gc_d78.json`；WebUI ㉞ 面板 + `/api/gc_sparams`（HTTP 实测通，passed=True）。**诚实标注**：①谷位置对直波导 neff 预测系统性负偏 ~9%（凹槽微扰使周期结构平均传播常数低于直波导 neff，Λ 无关恒定比例，物理预期非 bug），趋势斜率锚定反解值不受影响；②2D 全刻蚀方波 ≠ 3D 浅刻蚀 GC 光纤耦合（无光纤模/方向性），不声称耦合效率。
- **D-79 真实基元接入设计流水线（M6 v0.4 门槛达成 · Track B 收口）**：`gds_export.geometry_desc` 默认几何从玩具矩形/圆形切换到 D-71 真实基元——**RingResonator/RingAddDrop 实心环带 BOUNDARY → 真实波导环**（中心线 PATH + width，foundry 弯曲波导标准表达，可 DRC 检查环宽）；**SymmetricYBranch 裸分叉 → 输入绝热 taper**（D-71 taper_polygon 余弦轮廓）+ 双 arm PATH；DC/Waveguide 已是 PATH 波导表达（确认沿用）；Taper/EulerBend/MMI/GratingCoupler 沿用 D-71 基元（GC=D-78 修正方波光栅）。`lda_agent/pipeline_realize.py`：全 9 kind 真实 GDS 出图 + round-trip 一致 + **3×SOI PDK DRC 复查**（NOEIC/CUMEC/SITRI design_rules 注入）+ 玩具→真实几何对比诊断。实测：9/9 kind PASS（Waveguide 100B / Ring 638B / AddDrop 680B / DC 142B / YB 702B / Taper 618B / Euler 8298B / MMI 1928B / GC 1380B，全 rt=OK drc 三厂全绿）；smoke 3/3（全 kind + 几何真实化断言 + 非法 kind 优雅 FAIL）；报告 `reports/pipeline_realize_d79.json`；WebUI ㉟ 面板 + `/api/pipeline_realize`（HTTP 实测通）。**诚实边界**：环 path 为圆弧中心线（曲率恒定），Euler 弯无缝拼合环留作深化；几何真实化不改变电特性判据（归 D-72/D-78 端口验收）。**Track B 至此收口，"设计→验证→版图"全链路真实化闭环，v0.4 门槛达成。**

### 新增/变更（Unreleased）

- `lda_solver/`：adjoint_fdtd.py（主权 2D adjoint FDTD 核：脉冲前向 + 显式转置伴随 + FD 对拍验证 + 拓扑优化器）+ port_sparams.py（D-72 端口 S 参数框架：MMI eps 场构建 + CW 多端口收集 + 输入功率归一 + 自成像 ORACLE 验收）+ port_sparams_3d.py（D-72 深化：3D MMI/DC/Ring 体素场 + 3D CW 多端口收集 + kind 分支判据 + 2D↔3D 对拍诊断）+ port_sparams_gc.py（D-78：GC 方波光栅场构建 + 透射谱谷检测 + 光栅方程 ORACLE 验收 + Λ 趋势锚）
- `lda_agent/`：adjoint_design.py（D-69 设计闭环封装）+ wdm_splitter.py（D-67）+ calibrate_kappa_grid.py（D-68 参数化标定）+ design_loop.py（D-70 method=adjoint 逆设计分支）+ l1_protocol.py（DesignTarget.method 字段）+ primitives_design.py（D-71 基元库封装）+ sparams_design.py（D-72 S 参数验收封装 + PDK 规则注入 DRC）+ sparams_3d_design.py（D-72 深化 3D 验收封装）+ gc_design.py（D-78 GC 验收封装）
- `lda_l2/`：primitives.py（D-71 真实版图基元：taper/euler_bend/mmi/grating_coupler 纯几何；D-78 修正 GC 为真实方波光栅）+ gds_export.py（geometry_desc 注册 4 新 kind；D-79 升级 Ring/AddDrop/YBranch 真实基元几何）+ drc.py（drc_check_device 支持 4 新 kind）
- `data/`：kappa_grid_calibration.json 升级 4×5（20 点，dl40，双轴单调）
- WebUI：二十七 → **三十五面板**（㉘ 分束网络×WDM、㉙ 伴随法拓扑逆设计、㉚ 逆设计接入 D-36 引擎、㉛ 真实版图基元库、㉜ 端口 S 参数验收、㉝ 3D 端口 S 参数验收、㉞ 光栅耦合器端口验收、㉟ 真实基元接入设计流水线）
- API：`/api/wdm_splitter`（D-67）、`/api/adjoint_design`（D-69）、`/api/adjoint_loop`（D-70）、`/api/primitives`（D-71）、`/api/sparams`（D-72）、`/api/sparams_3d`（D-72 深化）、`/api/gc_sparams`（D-78）、`/api/pipeline_realize`（D-79，全 kind 真实 GDS + DRC）
- README：能力阶梯表加 D-66~D-79 行（含 D-72★ 3D 深化、D-78 GC 验收、D-79 流水线真实化）、三十五面板、㉘~㉟ 面板清单
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 11 项枚举，延续）

## v0.0（阶段 0/1/2，此前交付）

- 自研 1D/2D/3D FDTD（numpy 零依赖，物理定律锚校验）+ Numba-CPU JIT + PyTorch GPU 升维
- L0 IR 光子子集（D-01~D-05）、L1 agent 闭环、L2 器件库（GDS/DRC/版图仿真）
- 确定性比对裁判 B1-B11（含量子 B9/B10）
- AI-dev 自举写核（SolverSpec + ORACLE + BootstrapLoop）、生产级 GPU 网格（6400 万点）
