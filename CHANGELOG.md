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

## v0.0（阶段 0/1/2，此前交付）

- 自研 1D/2D/3D FDTD（numpy 零依赖，物理定律锚校验）+ Numba-CPU JIT + PyTorch GPU 升维
- L0 IR 光子子集（D-01~D-05）、L1 agent 闭环、L2 器件库（GDS/DRC/版图仿真）
- 确定性比对裁判 B1-B11（含量子 B9/B10）
- AI-dev 自举写核（SolverSpec + ORACLE + BootstrapLoop）、生产级 GPU 网格（6400 万点）
