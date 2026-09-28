# LDA 设计能力评估与进化路线（2026-09-23）

> **性质**：战略评估 + 路线图。**不改任何锚、不动棘轮常数、不发版**。
> **方法**：① 仓库实测盘点（目录/文件/代码证据，非印象）② 国际对标调研（2026 年公开信息）③ 分层差距量化。
> **基线**：v0.9.127（`d4b2c44`）· 469 锚（strict 448 / degraded 3 / stub 18）= **95.52%** · 天花板 **97.44%** · CI core **194**。
> **诚实边界前置**：本评估中所有「国际水平」判断来自**公开资料**（可能滞后或为厂商自报）；所有「LDA 能力」判断来自**仓库实测**；凡属推断一律标注。**不替杜先生做投资/立项决策。**

---

## §0 一句话结论

**LDA 已经不是「追赶者」在做仿真器，而是一个「栈已完整、缺三样东西」的设计工具**：
**它的六层栈（器件仿真 → 版图签核 → PDK 生命周期 → 计算架构编译 → 验证账本 → Agent 接口）已经贯通**，
差的是 **① 真实 foundry PDK 准入 ② 一次真实流片闭环 ③ 与国际标准工具的互操作深度**。

而 2026 年的国际共识恰好落在 LDA 的强项上 —— **「自主性取决于验证器的质量，而不是模型的质量」**（DAC 2026 三条独立结论之一）。
LDA 手里那套 **469 道物理锚 + 判据 D + provenance** 的验证纪律，不是成本项，**是这个时代最稀缺的资产**。

---

## §1 坐标系：光子芯片设计能力六层模型

先立标尺。下面这套六层模型来自两条独立来源的交汇：
① 国际工具链的实际产品形态（Ansys/Synopsys/Cadence/Luceda/gdsfactory）；
② 国内产业界对「怎么判断一座硅光平台是否成熟」的公开框架（2026 年多篇行业分析一致给出**六层**：工艺模块 → PDK → 稳定复现 → 服务确定性 → TDK/ADK → 量产转移）。

| 层 | 名称 | 这一层「做到」的标志 | 国际最佳 |
|---|---|---|---|
| **L1** | **器件仿真** | 3D 全波 + 本征模 + EME + 多物理，且有**验证过**的精度 | Ansys Lumerical（FDTD/MODE/INTERCONNECT/Multiphysics）· Tidy3D · gSim |
| **L2** | **电路 / 链路级** | 频域 + 时域 + 光电混合（Verilog-A / SPICE 联合仿真） | Lumerical INTERCONNECT · VPIphotonics · Keysight Photonic Designer · Luceda+SPICE |
| **L3** | **版图 + 签核** | 参数化 PCell · 自动 P&R · DRC/LVS 与 foundry deck 对齐 | Synopsys OptoCompiler · Cadence EPDA · Luceda IPKISS · Siemens L-Edit+Calibre |
| **L4** | **PDK 生态** | 多家 foundry **官方** PDK，模型**硅验证**、带 corner | gdsfactory+（**50+ PDK**）· Luceda（多平台 PDK） |
| **L5** | **工艺对齐 / 量产转移** | MPW → 工程批 → 量产，交付历史与实测回流 | 各 foundry 自身 + AIM/IMEC/NOEIC/CUMEC |
| **L6** | **计算架构 / 编译** | 算法 → 光硬件映射 + 系统级联合优化 | **无公认标准工具**（各家自研，如 Lightmatter/Lightelligence 内部栈） |

**🔴 关键观察**：L6 是**全球都没有标准工具的层**。这一层谁先立起来，谁就定义标准。

---

## §2 2026 年的国际格局（三条硬事实）

### 2.1 Synopsys + Ansys 合并：统一签核**还没做到**

Synopsys 把 HFSS / Lumerical FDTD / Lumerical INTERCONNECT 与自身硅设计流程并入一个屋檐下。但 2026 R1 的实际交付物只是——
> **「Ansys Lumerical INTERCONNECT 2026 R1 release notes: Synopsys OptoCompiler interoperability」**

行业分析直接点破："**That is not a unified design environment. It is the first interoperability layer between two previously separate tools**"。
终点（production-quality co-simulation，让「DRC-clean 的光子版图同时是 verified 的光学设计」）**尚未达到**，
且给出一个明确窗口判断：**「若到 2028 年中还未进入客户生产使用，做 AI 共封装光学的团队会默认选开源路径」**。

> 🎯 **这句话就是 LDA 的战略机会**：它描述的那个终点 —— **「DRC 干净的光子版图同时是已验证的光学设计」** —— 正是 LDA 已经具备的**主权闭环（几何 DRC + LVS + 硬契约锚 S9/S10）**。

### 2.2 DAC 2026：自主性来自**验证器**，不是模型

2026 年 7 月，三大 EDA 厂同时把 AI 从 copilot 推向自主：Synopsys（AgentEngineer，**L1–L5 自主阶梯，当前 ~L3**，声称验证 RTL 快 50×）· Cadence（AuraStack，Q2'26 收入 **$1.584B / +24% YoY**、backlog **$8.1B**）· Siemens（Fuse，**核心逻辑 = 自验证：把大模型输出与确定性物理签核引擎交叉核对**，且**采用 MCP 协议**互联各厂工具）。

行业复盘给出的结构性原因，值得逐字引用：
> **"EDA already owns trusted deterministic verifiers — simulators, formal engines, DRC, timing signoff — that can tell an agent it is wrong, cheaply and unambiguously."**
> **"The durable lesson for anyone building agents outside silicon: autonomy scales with the quality of your verifier, not the quality of your model. If you lack a deterministic oracle, manufacture one."**

⚠️ 同时有一条**反面警示**：中国大模型 Kimi K3 曾"自主设计芯片 48 小时、不碰商用软件"，但深挖后 —— **"对应约 20 年前的技术，比现有芯片慢 20–30 倍"**。
⇒ **「AI 自主设计」这类宣称极易做出但极易被证伪**。**谁有可验证的水平证据，谁才有资格说这句话。**

### 2.3 PDK 是命门，且开源栈已经起来了

- **gdsfactory+**：自称世界最流行开源芯片设计框架，**支持 50+ foundry PDK**（Tower PH18 系列 / GlobalFoundries AMF / AIM Photonics / Ligentec SiN / HHI III-V …），并有自研引擎 **gSim（FDTD+FEM）+ MEOW（EME）**，集成 Tidy3D / MEEP / DEVSIM / SAX / SPICE。**2026-03 已把 Lightwave Logic 的电光聚合物调制器并入其 PDK（GF 平台）并启动流片验证**。
- **国内工具**：**逍遥科技 PIC Studio**（光电子全流程自主 EDA，打通「原理图 → 光电混合仿真 → 自动布局布线 → 物理验证」闭环，被公开评价为国内 PIC EDA 佼佼者）；**芯华章 XEPIC Intelligent System**（Agentic EDA 底座，强调"**把 AI 输出变成可验证、可追溯、signoff-ready 的结果**"）；芯和半导体（DAC 2026 唯一国产落地案例）；广立微 UDA 2.0。
- **行业共识（对 LDA 最重要的一条警示）**：国内高端硅光代工国产化率极低，头部算力级硅光芯片流片**仍高度依赖台积电/格芯**；且——
  > **「行业早已走完设计端单点技术突破的阶段，现阶段核心攻坚重心全面转向制造体系补短板。」**
- 但同一批分析的结语又把 PDK/EDA 抬到地基位置：
  > **「PDK 作为比电子设计难十倍的硅光设计的核心保证……没有夯实的地基，芯片设计再好也只不过是空中楼阁。」**

⇒ **这两句话不矛盾，而是划出了 LDA 的生存空间**：**"设计算法"不是瓶颈，但"可信 PDK + 可签核的验证"是**。

---

## §3 LDA 现状实测（能力盘点）

### 3.1 栈的完整度：17 个功能模块，全链路贯通

> `lda/` 下实测 **30 个目录** = **17 个功能模块**（`lda_*` 包 15 个 + `ext_oracle` + `examples`）+ **13 个 `reports_*` 产物目录**。下表列功能模块。

| 层 | 模块 | 规模（实测） | 内容 |
|---|---|---|---|
| **IR** | `lda_ir/` | 8 文件 | `core` / `dsl` / `photon` / `quantum` / `spec_check` / `validate` / `bridge` |
| **求解器** | `lda_solver/` | **59 文件** | 见 §3.2 |
| **L1 协议** | `lda_l1/` | 4 文件 | `protocol`（KernelGateway）· **`mcp_server`（真 MCP，零依赖 stdio JSON-RPC 2.0，协议 `2024-11-05`）** · `gdsfactory_bridge` |
| **L2 设计核心** | `lda_l2/` | **31 文件** | `device_library`（**99.9 KB**）· `gds_export` / `gds_drc` / `drc` / `lvs` / `chip_layout_export` · `parasitic_rc` · `compact_model` · `compiler_frontend`（37 KB）· `mzi_mesh_matmul` · `spice_netlist` · `layers` / `pdk` / `pdk_examples` / `primitives` / `hierarchy` |
| **版图/P&R** | `lda_layout/` | 10 文件 | `mesh_pnr`（**55 KB**）· `wdm_mesh_pnr` · `wdm_shared_mesh_pnr` · `router` / `router_p1` · `placement` · `congestion` · `parallel_routing` · `spatial_index` |
| **PDK 生命周期** | `lda_pdk/` | 11 文件 | `registry` · `review`（22.6 KB）· `submit`（19.5 KB）· **`tapeout_pipeline`（23.8 KB）** · `empirical` · `corner_performance` · `packaging_tolerance` · `publish` · **`sovereign_deps`（主权依赖登记表）** |
| **链路** | `lda_chain/` | 10 文件 | `link_model` / `link_loss` / `link_harness` / `route_sim` / **`chip_acceptance`** / `verify_link` |
| **设计引擎** | `lda_design/` | 8 文件 | `design_engine`（38.5 KB）· `design_package`（31 KB）· `active_models` · **`cpo_engines`** · `loss_engines` · `qkd_engines` · `cli` |
| **Agent 层** | `lda_agent/` | **58 文件** | `agent_planner` / `agent_synthesis` / `agent_verify` / `agent_layout` / `orchestrator` · **`llm_proposer` + `redteam_proposer`** · `design_loop` / `design_pipeline` / `pipeline_realize` · `inverse_design` / `adjoint_design` / `adjoint3d_design` · **`drc_fix_loop`（DRC 自动修复）** · `multi_objective_design` · **`solver_writer`（28 KB）** · `large_scale_bench` · `sandbox` |
| **验证账本** | `lda_harness/` | **80 文件** | `golden`（72 KB）· `harness` · `proposal_compiler`（47.6 KB）· `provenance` · `deterministic` · **oracle 层（`oracle_pyepr` / `oracle_sax` / `oracle_tidy3d` / `oracle_mode` / `oracle_field` / `real_machine_oracle`）** · `empirical_bank` · `system_budget` · `cpo_array`（23.2 KB） |
| **量子** | `lda_qeda/` | 4 文件 | `gates` · **`surface_code`（表面码）** · `cross_resonance` |
| **外部 oracle** | `ext_oracle/` | 2 文件 | `meep_oracle`（**B 级借用，只回标量**） |
| **生产计划** | `lda_l3/` | 2 文件 | `production_plan`（⚠️ **L3 系统层为 Tier-1 自证桩**，见 §3.5 G21） |
| **数据/租户** | `lda_data/` | 5 文件 | `backend` / `models` / `service` / `auth`（多租户数据面） |
| **授权** | `lda_license/` | 1 文件 | 许可校验（单模块） |
| **对外** | `lda_webui/` | 13 文件 | REST + 静态前端 |
| **示例** | `examples/` | — | 端到端示例 |

### 3.2 求解器清单（59 个，实测文件级）

| 类别 | 实现 | 证据 |
|---|---|---|
| **FDTD 1D/2D/3D** | `fdtd1d` · `fdtd2d` · `fdtd3d` | ✅ 全维 |
| **FDTD 加速** | `fdtd3d_numba` · `fdtd3d_torch` · `fdtd3d_waveguide_vec` · `activate_gpu_fdtd3d` | ✅ **含 GPU 路径** |
| **FDTD 器件专用** | `fdtd2d_waveguide` / `_coupler` / `_mmi` / `_ring` / `_dbr_cavity` · `fdtd3d_waveguide` / `_coupler` | ✅ |
| **伴随法逆向设计** | `adjoint_fdtd` · **`adjoint_fdtd3d`（64 KB）** · `hybrid_inverse` · `shape_inverse` | ✅ |
| **本征模** | `semivec_mode_solver`（半矢量）· `bend_mode`（弯曲）· `resonator` · `bragg` | ✅ |
| **EME** | `eme_taper` · `mmi_eme` | ✅ |
| **S 参数** | `port_sparams` · `port_sparams_3d` · `port_sparams_gc` | ✅ |
| **其他光学** | `tmm`（传输矩阵）· `mie_solver` · `dc_cmt_solver`（时域耦合模）· `voxel_field` | ✅ |
| **电学** | `drift_diffusion_1d` / `_2d`（31.7 KB）· `devsim_bridge` | ⚠️ 见 §3.4 |
| **有源器件真值** | `mzm_vpi_depletion_true` · `ge_pd_responsivity_true` · `apd_avalanche_true` · `detector_bandwidth_true` | ✅ |
| **热学** | `thermal_phase_efficiency` | ✅（单点） |
| **量子** | `transmon_solver` · `qubit_resonator_solver` · `lindblad_gate_fidelity` · `readout_fidelity_quad` · `qeda_depth_solver` | ✅ **超导量子方向** |
| **红线条** | `redline.py`（**T1 数值内核输出永不作 ORACLE**） | ✅ 红线守卫 |

**🔴 求解器的三条硬约束（代码自述，非推测）—— 这三条决定了 L1 的真实档位：**

| 约束 | 实测内容 | 后果 |
|---|---|---|
| **边界条件** | FDTD 一律用**梯度二次型海绵吸收层**；代码自述「**无 Mur-ABC、无 CPML**」 | 🔴 **不是真 PML** ⇒ 吸收精度弱于商用 |
| **材料模型** | FDTD 内 ε 为**标量实 n²**；**无各向异性、无时域色散、无非线性** | 🔴 色散只存在于**频域**模式求解的 Sellmeier；**χ²/χ³ 全仓缺失** |
| **模式求解** | 仅 **2D 半矢量**（`neff_2d`/`neff_strip`）；**无 3D 全矢量** | 🔴 SOI 高对比度**绝对 n_eff 偏高 +0.0276**（自写 2.5936 vs Lumerical FDE 2.566）⇒ 模块**自我禁止**用于 SOI 绝对 n_eff 判定；SiN 低对比度 ≲1e-3 |

> ⚠️ 另有两条同源代价：① **A 级商用求解器禁止在进程内 import**（仅外部 ORACLE 回标量）⇒ **无法在工具内做交叉验证**；
> ② `mma_eme` 自述**不足以判决 E5 锚**；`tmm` 仅垂直入射。

### 3.3 计算架构 / 编译层（这是 LDA 的**独有层**，国际无标准工具）

| 能力 | 模块 | 状态 |
|---|---|---|
| 任意酉矩阵 → MZI 网格 | **Clements 矩形分解** + 网格 P&R（`mesh_pnr` 55 KB） | ✅ 版级保真度**机器精度 1.0** |
| 网络矩阵 → 合法酉 + 驱动清单 | `compiler_frontend`（37 KB）：酉/非方阵/非酉三路；Procrustes + 正交补全 | ✅ 非酉残余**闭式**给出，不宣称精确 |
| 损耗感知编译 | `loss_aware_compile` | ✅ 并证得 **编译层对 IL_var 自由度 = 0** |
| 良率 / 容错 | `yield_fault_tolerance` | ✅ **结构冗余 = 0**（机器化证明） |
| 非易失权重后端 | `nonvolatile_weight_backend` | ⚠️ **条件式**（文献锚 ≠ 实测） |
| 校准固件协议 | `calibration_protocol` | ⚠️ **协议已设计，无物理锚 ⇒ 恒 `BLOCKED_NO_ANCHOR`** |
| 微环权重库 | `ring_weight_bank`（U4） | ✅ 含**不利结论**（动态范围仅 0.038 dB） |
| WDM 共享网格 | `wdm_shared_mesh_pnr` | ✅ 面积 ×K → ×1，含色散量化 |
| AI 框架前端 | `compiler_frontend` 的**只读守卫**（PyTorch/ONNX 只许进、不许进判决路径） | ✅ 机制级 |

### 3.4 版图 / 签核 / PDK 实测水位

| 项 | 实测 |
|---|---|
| 版图 | **自研零依赖 GDSII writer**（DBU=1 nm）· 13 类器件 · 层次化 cell + AREF（CPO 250k：897,600 元素 → 331 元素）· ⚠️ **无 3D 版图** |
| 布线 | 网格 A* + 曼哈顿 + 圆角 + 拥塞惩罚；⚠️ **无欧拉/曲线真布线、无长度匹配/相位匹配约束**；有损耗估计、**无相位误差估计** |
| DRC | 参数级 4 条 + 几何级 3 条；🔴 **模块自标「子集 ≠ foundry deck」** |
| LVS | 从几何**独立恢复**网表，8 类违规，**ACCEPT iff 零违规**；含硬契约锚 **S9/S10** |
| PDK | `PDK`/`DeviceTemplate`/`PDKRegistry`；**注册 5 个 foundry**（NOEIC / CUMEC / SITRI 的 SOI 180 nm + 量子 A/B Al-AlOx）；🔴 **全部为「公开近似」，非 NDA-PDK**；SiN / LiNbO₃ **无 PDK** |
| 寄生 | `parasitic_rc` 一阶估算；⚠️ **无 3D 场解提取** |
| 流片 | `tapeout_pipeline` S1–S5 就绪；🔴 **无 tape-out 记录、无实测硅回流**（S5 实测回流为占位且被溯源门禁拒绝） |

### 3.5 结构性缺口清单（诚实，不粉饰 · 22 项实测）

**A 组 · 物理与求解器层**

| # | 缺口 | 证据 | 性质 | 能否自研补 |
|---|---|---|---|---|
| G11 | **无真 PML** | FDTD 用梯度二次型海绵层，代码自述「无 Mur-ABC、无 CPML」 | 精度 | ✅ 可自研 |
| G12 | **3D 全矢量模式求解（部分落地·低对比度）** | 低对比度自研 E_t 求解器已准确（SiN 1.964~1.965 vs 目标 1.967，conf≈0.97，网格收敛）；**高对比度 SOI +0.0276 消除 = 未达成（研究级）**：Yee E-field + E_z 耦合（P1）实测会杀死导模（自伴性/线性化已验证无错，α=0 严格复现 F0），且 E_t-only 在 SOI 偏 +0.16~+0.23 且不收敛（5~8× 于生产 semivec）⇒ 根因是自研 ε 界面离散，正解须转 **H-field `∇×(ε⁻¹∇×H)=k0²H` + PML + 正确界面平均**（独立立项） | 精度 | ⚠️ 部分（高对比度待研） |
| G13 | **无时域色散 / 各向异性 / 非线性材料** | FDTD 内 ε 为标量实 n²；χ²/χ³ 全仓缺失 | 能力 | ✅ 可自研 |
| G14 | **无 RCWA / FEM / BPM / 3D EME** | 全仓实测无对应模块 | 能力 | ✅ 可自研 |
| G15 | **无多物理耦合**（电-热-光未耦合）；热仅 1D 稳态鳍方程 | `thermal_phase_efficiency.py` 仅 1D | 能力 | ✅ 可自研 |
| G16 | **无任意几何 3D 网格**（体素化限矩形） | `voxel_field.py` | 能力 | ✅ 可自研 |
| G17 | **电域反偏物理不可用** | 2D 漂移-扩散 V=−1 V 给 **350 A** vs 饱和电流 **5.8 pA**（非物理）；无 MOS/先进节点 TCAD（devsim 冷备未装） | **正确性** | ✅ 可自研（有 `docs/lda_reverse_bias_limitation.md`） |
| G18 | **主权代价：无法内置交叉验证** | A 级商用求解器禁止进程内 import（仅外部 ORACLE 回标量） | **战略选择** | — 保持（但需对外说清） |

**B 组 · 电路与系统层**

| # | 缺口 | 证据 | 性质 | 能否自研补 |
|---|---|---|---|---|
| G19 | **无电路级求解器** | `spice_netlist.py` 只**导出**网表；不跑瞬态/眼图/BER | 能力 | ✅ 可自研 |
| G20 | 🔴 **无系统级功耗 / 面积-性能联合优化** | **无 TOPS/W、无能耗/MAC**；仅 U7 一维权衡 | 能力 | ✅ 可自研（**对"光子计算机设计工具"最关键**） |
| G21 | 🔴 **L3/L4 系统层是 Tier-1 自证桩** | `four_layer_redline_gate.py` 实测审计：L1=B14 方法学独立、L2=Reck 数学定理、**L3/L4 自证桩** | 证据 | ✅ 可自研（需真验证） |

**C 组 · 版图与签核层**

| # | 缺口 | 证据 | 性质 | 能否自研补 |
|---|---|---|---|---|
| G1 | **无任何 foundry 官方 PDK / DRC deck 认证** | 仅 4 参数级 + 3 几何级规则；模块自标「子集 ≠ foundry deck」 | 生态 | ❌ 必须外部（NDA） |
| G3 | **无 3D 版图** | 自研 GDSII writer 为 2D 层次 + AREF | 工程 | ✅ 可自研（工作量大） |
| G4 | 🔴 **器件参数无几何回提** | LVS 器件 kind 来自 LinkModel 而非版图几何 ⇒ **画错尺寸查不出** | **正确性** | ✅ 可自研（**优先级最高**） |
| G5 | **寄生提取仅一阶** | `parasitic_rc.py` 一阶估算，无 3D 场解 | 精度 | ✅ 可自研 |
| G7 | **布线约束不足** | 网格 A* + 曼哈顿；**无欧拉/曲线真布线、无长度/相位匹配约束；无相位误差估计** | 能力 | ✅ 可自研 |

**D 组 · 证据、生态与量子**

| # | 缺口 | 证据 | 性质 | 能否自研补 |
|---|---|---|---|---|
| G2 | 🔴 **无流片记录 / 无实测硅回流** | `tapeout_pipeline` S5 槽位为占位且**被溯源门禁拒绝**；0 硅片、0 实测 | 证据 | ❌ 必须外部（花钱流片） |
| G22 | **未上 PyPI + 无 pytest 套件** | 入口为 `run_*smoke*.py`；无 `tests/` | 生态 | ✅ 可自研（**对生态最省力的改进**） |
| G8 | 🔴 **与商用工具零互操作** | 仅 `meep_oracle`（只读、只回标量）· `oracle_tidy3d`；**无 Lumerical/Tidy3D 双向交换** | 生态 | ✅ 可自研（格式层） |
| G10 | **SiN / LiNbO₃ 平台缺 PDK** | 仅 SOI 180 nm 近似（NOEIC/CUMEC/SITRI）+ 量子超导 Al-AlOx | 生态 | ❌ 外部 |
| G23 | 🔴 **无量子光子学** | 无 KLM / 玻色采样 / 压缩态 / H 光子 qubit；**无量子电路或算法模拟器** ⇒ 不能执行量子算法或光量子采样 | 能力 | ✅ 可自研（**外部表述需精确**：QEDA = **超导**量子芯片设计） |
| G24 | **WDM 仅 K=4 验证**；U10 物理锚为**空集** | `calibration_protocol.ANCHORS_AVAILABLE_TO_THIS_PROJECT = ()` | 覆盖 | ⏳ 外部 |
| G25 | **U12 / U13 / U14 三项被阻塞** | 阻塞原因：**NDA / 流片 / 现金** | 外部 | ❌ 外部 |

---

## §4 分层差距评估（LDA vs 国际）

**差距量级口径**：`≪` = 同代（可直接竞争）· `≈` = 差 1 代（1–2 年）· `>` = 差 2 代（需专项）· `≫` = 结构性（需外部条件）

| 层 | LDA 档位（实测） | 国际最佳 | 差距 | 差距**性质** | 追赶方式 |
|---|---|---|---|---|---|
| **L1 器件仿真** | 零依赖自研 **59 个求解器**：FDTD 1D/2D/3D(+GPU) 但**海绵边界≠PML** · **无时域色散/各向异性/非线性** · 模式仅 **2D 半矢量**（SOI 绝对 n_eff **+0.0276**）；EME / 伴随逆向 / 器件级电学可用 | Lumerical（3D 全波 + 真 PML + 色散/各向异性/非线性 + 多物理）· Tidy3D | **`>`（差 2 代）** | 🔴 **能力面广、物理深度不足** —— 材料/边界/维度是**真缺口**，不是工程细节；但 LDA 有 Lumerical 没有的**验证锚体系** | 自研（G11–G16：属"补物理"） |
| **L2 电路/链路级** | `lda_chain`（链路模型/损耗/验收）+ `spice_netlist`（**只导出，不求解**）+ `compact_model` | Lumerical INTERCONNECT · VPIphotonics · Keysight | `>` | **真能力缺口**（无电路级求解 ⇒ 无瞬态/眼图/BER） | 自研（G19，半年–1 年量级） |
| **L3 版图+签核** | 自研 GDSII + P&R + DRC(4+3) + **LVS 零违规硬契约** + 层次化；⚠️ 无 3D、无 foundry deck | Synopsys OptoCompiler · Cadence EPDA · Luceda IPKISS | `≈`**→ 但性质特殊** | **签核框架同代，规则深度差**（LDA 是"方法论对、deck 假"） | 🔴 **必须接真 deck**（G1） |
| **L4 PDK 生态** | **5 个 foundry（公开近似）**；gdsfactory 仅几何桥 | gdsfactory+ **50+ PDK** · Luceda 多平台 | `≫` | **生态差距（结构性）** | 🔴 **不能自造 ⇒ 必须对接** |
| **L5 工艺对齐/量产** | `tapeout_pipeline` 就绪但**从未流片** | 各 foundry 自身 | `≫` | **证据差距（0 → 1）** | 🔴 **必须花钱流一次** |
| **L6 计算架构/编译** | Clements 分解 + 损耗感知 + 良率 + **校准协议（无锚 ⇒ 恒阻塞）** + 非易失后端（条件式）+ WDM 共享网格 + AI 框架只读前端；⚠️ **无系统级功耗/面积-性能联合优化**（无 TOPS/W） | **无公认标准工具** | **`≪`（领先位）** | **无人占位 ⇒ 定义权机会**；但"系统级优化"这一半还缺 | ✅ **自研 + 立标准** |
| **Agent 原生** | **真 MCP server（零依赖 stdio，6 个工具）** + `llm_proposer` / `redteam_proposer` + 判决路径禁 LLM 的机器守卫 | 三大厂 2026 才上 agentic（Siemens 才采用 MCP） | **`≪`（领先位）** | **架构领先，需证明价值** | ✅ **自研 + 公开验证** |

**🔴 这张表的读法（三条）**：

1. **差距分两类，性质完全不同**：
   - **靠写代码能补的** —— L1 物理深度（G11–G18）、L2 电路级（G19）、L6 系统级优化（G20）、版图层（G3/G4/G5/G7）⇒ **AI 可自主推进**。
   - 🔴 **靠写代码补不了的** —— **L4 PDK 生态**（G1/G10）、**L5 流片证据**（G2）⇒ **必须外部动作（NDA + 花钱 + 签名）**。**这是路线的真正瓶颈。**

2. **LDA 的优势全部集中在"无人占位"的两层**（L6 + Agent）—— 这是**定义标准的机会**，不是"领先多少"的问题。

3. ⚠️ **一处需要精确化的表述**：`four_layer_redline_gate` 里的「L1–L4」是**项目内部的四层系统**（与上表六层模型**不是同一套编号**）；实测审计显示其中 **L3/L4 目前只是 Tier-1 自证桩**（L1 = B14 方法学独立、L2 = Reck 数学定理）。⇒ **对外引用时两套编号不可混用**（详见 §3.5 G21）。

---

## §5 四条战略判断（本轮核心洞察）

### 判断 1：LDA 的价值主张必须锚在「**可验证**」，不能锚在「更好的仿真」

国内产业共识是「**设计端单点突破已完成，瓶颈在制造端**」。若 LDA 宣称"我们的仿真器更准"，那是在一个**已被认为不是瓶颈**的维度竞争，且要面对 Lumerical/Tidy3D 的云+GPU 规模优势（打不赢，也不需要打）。

但同一批分析把 **PDK 抬为「地基」「命门」**，并指出成熟平台的核心差异是：
> **「PDK 里是示意图，还是硅验证模型？模型覆盖多少晶圆与批次，是否提供温度、偏振和工艺 corner？」**

⇒ **LDA 应该卖的是「让 PDK 模型变得可证」的方法学与工具**。它那套 **469 锚 + 判据 D（残差严格单调）+ provenance + 拒收同源数据**，正是"硅验证模型"所缺的**证据纪律**。

### 判断 2：DAC 2026 的行业结论，逐字印证了 LDA 的红线

> **"autonomy scales with the quality of your verifier, not the quality of your model. If you lack a deterministic oracle, manufacture one."**

LDA 从第一天起就在做这件事：**物理定律锚作 deterministic oracle、LLM 不进判决路径、判决落非 AI ground**。
同时 **Siemens Fuse 的"自验证"逻辑（大模型输出 vs 确定性物理签核引擎交叉核对）** 与 LDA 的架构**同构**。

⇒ **LDA 的红线不是保守，是超前。这一点应当在对外材料里从"我们的纪律"改写为"我们符合 2026 的行业共识"。**

### 判断 3：PDK 生态**不能自造，必须对接** —— 而且要快

gdsfactory+ 已有 **50+ PDK** 且**从开源起家**、已拉进 Lightwave Logic 这类器件厂共建 PDK 并联合流片。
自造 PDK 生态在时间上不可能赢。**LDA 的正解是把自己做成"gdsfactory 生态的可验证签核层 + 计算架构编译层"** ——
即：**几何/PDK 从生态取，判决与编译由 LDA 主权给出**。这与项目既有纪律**不冲突**：
- gdsfactory = MIT（B 级可借），且**已有桥**（`gdsfactory_bridge.py`）；
- 红线是"求解器与判决不借" —— **PDK 数据本来就不是求解能力，是工艺事实**。

### 判断 4（⚠️ 最重要的警示）：**"追赶现实"的第一步不是写代码，是花一次流片的钱**

当前 LDA 的最大风险**不是技术**，而是——
**一个"验证纪律极其严格"的项目，自己却没有任何一项经过真实流片验证的设计。**

这构成一个**结构性自相矛盾**：项目用 469 道锚证明"我们不接受未验证的声明"，但它**自己关于"能设计出可流片芯片"这个最大的声明，恰恰是未验证的**。
DAC 2026 的 Kimi K3 教训（"AI 自主设计芯片"→ 实为 20 年前水平）说明：**这类声明一旦被外部检验，代价极大**。

⇒ **必须先做一次真实的、最小的、可公开的流片闭环。** 这既是能力证明，也是路线的第一个里程碑。

### 判断 5：「主权」是一笔交易 —— 换来**不可污染**，付出**无法自证**

| 这笔交易的收益 | 这笔交易的成本（必须承认） |
|---|---|
| 判决路径永远不依赖外部黑盒 ⇒ 结果**可复现、可审计** | 🔴 **无法内置交叉验证**：A 级商用求解器禁止进程内 import，只能外部 ORACLE 回标量 ⇒ 用户拿不到「LDA vs Lumerical 逐点对比」这种最直观的信任凭据 |
| 符合 2026 行业共识（验证器质量决定自主性） | 🔴 **验证只能靠外部真值**：469 锚中 9 道只能等 foundry 数据到手（见 G2） |
| 不被 vendor lock-in（供应链风险归零） | 🔴 **性能与功能必须全部自建**：59 个求解器每一个都要自己写、自己验 —— 这既是 469 锚的由来，也是**进度慢的根因** |

**结论**：这笔交易**方向正确**，但**必须把"成本"写进对外叙事** ——
否则外部看到的只会是「功能比 Lumerical 少、没有 3D 全矢量、没有非线性」，
而看不到「**每一处能力边界都是自己算出来并写在代码里的**」（这在商业工具里恰恰**没有**：商用工具从不告诉你它的 n_eff 在 SOI 上偏高 0.0276）。

---

## §6 进化路线（三阶段）

### 阶段 0 · **追赶现实**（目标：从"能设计"到"设计过"）

| 项 | 内容 |
|---|---|
| **唯一目标** | **跑通一次真实流片闭环**：LDA 设计 → 真实 PDK → GDS → foundry → 芯片回来 → 实测回流进账本 |
| **关键动作** | ① **PDK 准入**（NDA + 拿 deck）② **最小设计**（不要复杂：波导 + 弯曲 + MMI + 光栅耦合器 + cut-back 结构，面积压到最小）③ **实测回流**（把测到的值接进 `provenance`，这正是 9 道外部锚缺的东西） |
| **为什么必须先做** | 国内 MPW 价格已降到 **2.9 万–19 万元/block**（见 §7 表）；**一次最小无源流片 ≈ 6–8 万元**。这个钱买的是**"我们设计过"这件事本身**。 |
| **可验证验收判据** | ① `tapeout_pipeline` 的 S5 槽位**被真实数据填满**（不再是占位）② 至少**1 道锚**由 own-design 实测升 strict ③ 公开一份含 DRC/LVS 签核证据 + 实测对比的设计报告 |
| **外部条件** | 🔴 **杜先生**：选平台（建议 CUMEC / NOEIC / 陕西先导院）+ 定预算 + 亲签 NDA |
| **阻塞项对照** | 项目内已登记的 **U12 / U13 / U14** 三项，正是被 **NDA / 流片 / 现金** 阻塞 ⇒ 阶段 0 一旦完成，这三项**同时解锁**（不是新增工作量，是解阻塞） |
| **与 A1 发函的关系** | **合并** —— A1 致 CUMEC 的那封函，应同时问「PDK 准入 + MPW 排期」，而不是只问数据。**一封函办两件事。** |

### 阶段 1 · **向国际水平靠拢**（目标：从"设计过"到"能签核"）

| 项 | 内容 |
|---|---|
| **目标** | **签核深度**达到"可交付 foundry"的门槛；工具**可被外部工程师使用** |
| **关键动作** | ① **DRC/LVS 对齐真 deck**（从 4+3 条 → 全规则）；② **器件几何回提**（补 G4，让"画错尺寸"能被查出）；③ **3D 版图**（补 G3）；④ **寄生提取升场解**（补 G5）；⑤ **与 gdsfactory/Lumerical 双向互操作**（补 G8）；⑥ **电路级时域仿真**（补 G6） |
| **可验证验收判据** | ① DRC 能通过**某家 foundry 的真实 deck**（有对方签认）② 布局↔原理图 双向一致性有机器判据（LVS 升级为含几何回提）③ 至少 1 个**外部工程师**（非项目成员）能用 LDA 完成一次设计 |
| **外部条件** | foundry 合作（NDA/deck）、可能需第二轮流片 |

### 阶段 2 · **世界一流**（目标：从"能签核"到"定义标准"）

| 项 | 内容 |
|---|---|
| **目标** | 在**全球都没人占位的两层**立标准：**L6 计算架构编译** + **Agent 原生设计流** |
| **关键动作** | ① 把「**可验证 PDK 方法论**」发布为**公开规范**（把 469 锚的纪律外化为行业可采纳的判据集）② 把 **MCP 原生设计原语**做成生态事实标准（Siemens 2026 才用 MCP ⇒ 窗口在）③ **计算架构编译**开源立标杆（Clements/损耗感知/良率/校准协议 + 硬件后端抽象）④ 与 AI 框架（PyTorch/ONNX）的**只读安全通道**公开化 |
| **可验证验收判据** | ① 有**外部机构**引用/采纳该规范 ② 有**第三方**基于 LDA 完成独立设计 ③ 在计算架构编译层有可对比的公开基准（且是 LDA 定的） |
| **外部条件** | 社区运营（投入人力）、可能需商业化载体 |

### 路线的时间/成本坐标（用 2026 真实行情锚定）

| 平台/路径 | 价格（2026 实测成交） | 周期 | 备注 |
|---|---|---|---|
| 中科院微电子所 8″ 180 nm 无源+热电极 | **2.9 万元/block** | — | 每年 6–8 班次；**最低门槛** |
| 华中科大 硅光无源 MPW（25 片，3×10 mm） | **7.98 万元** | — | |
| 华中科大 超低损耗 SiN（300 nm，5×5 mm） | **6.06 万元** | — | |
| 紫金山实验室 90 nm 硅光**有源**（25 片） | **12.8 万元** | — | |
| 华科大 12″ 硅光**有源**（20 颗） | **18.9 万元** | — | |
| NOEIC 武汉光谷 12″ 40 nm 全国产化 | **约 13 万元/次** | 合同交付 180 天 | **PDK+TDK+ADK 整体释放**；3 工作日 DRC 反馈、3 次改版 |
| IMEC（比利时） | ~**5 万美元**/block | 3–4 个月 | 国内同类的 2–3 倍 |
| AIM Photonics（美国）无源 25 mm² | 会员 **$28,600** / 非会员 $34,320 | — | 有源 25 mm² 非会员 **$85,800** |
| 陕西光电子先导院 8″ 中试 + LPSIN400 SiN PDK | 未公开（称成本降至海外 **1/3 以内**） | **2–3 个月** | 2026-08 起全行业开放 |

> 💡 **路线含义**：阶段 0 的**最小可行动作**（一次无源验证流片）≈ **3–8 万元**，周期 **2–3 个月**。
> 这不是"要不要投几百万"的问题，而是"要不要花几万块把 '0 次流片' 变成 '1 次流片'"的问题。

---

## §7 需杜先生裁决的决策点

| # | 决策 | 影响 | 我的建议 |
|---|---|---|---|
| **R1** | **阶段 0 是否启动？选哪个平台？** | 决定 0→1 能否发生 | 建议**先发 A1 函（询价 + PDK 准入）**，用回函决定平台；**不建议**先自造 PDK |
| **R2** | **A1 发函是否合并"PDK 准入 + MPW 排期"** | 一函两用 vs 分两步 | 建议**合并**（同一次沟通成本，多拿一个答案） |
| **R3** | **是否接受"LDA 定位为 gdsfactory 生态的可验证签核层"** | 决定生态策略（自造 vs 对接） | 建议**接受对接**（PDK 生态自造在时间上不可能赢；且与红线不冲突） |
| **R4** | **是否把验证账本纪律外化为公开规范**（阶段 2 的立标准动作） | 决定能否从"工具"升级为"标准" | 建议**先内部跑通，待阶段 1 有外部用户后再公开** |
| **R5** | **电域红线是否维持** | 决定能否做 CPO 全栈 | 建议**维持**（光电协同是市场热点，但破红线会让"不借主权"的核心叙事崩塌） |
| **R6** | **阶段 1 的 6 个补丁（G3/G4/G5/G6/G7/G8）优先级** | 决定 AI 侧自主推进次序 | 建议 **G4（几何回提）→ G8（互操作）→ G6（电路级）** 优先 —— G4 是正确性缺口（最危险），G8 是生态缺口（最省力），G6 是能力缺口（最耗时） |

---

## §8 诚实边界

1. **「国际水平」判断来自公开资料**（2026 年厂商公告、行业分析、展会报道），**未经我方独立实测**；其中性能数字多为厂商自报。
2. **「LDA 能力」判断来自仓库实测**（目录结构、文件、代码、既有锚账本 + 两路独立盘点），其中求解器/物理层与系统/量子层已取得**代码自述级证据**（边界条件、材料模型、维度、反偏非物理、自证桩认定），但**尚未做逐项数值复算** ⇒ §3.2/§3.5 的缺口判断是**代码级**证据，非**实验级**。
2b. 🔴 **发现一处红线口径与实际不一致**：「三不做」表述为「不做电域求解器」，但仓库实测**已有** `drift_diffusion_1d` / `drift_diffusion_2d` / `devsim_bridge`（器件级电学）。⇒ 建议把该条**精确化**为「**不借外部电域求解器 / 不宣称 foundry TCAD 真值 / 不做封测产线**」，否则对外引用时会被当场问出矛盾（`docs/lda_reverse_bias_limitation.md` 与 `lda_pdks/sovereign_deps.py` 可作依据）。
3. **本评估不含任何商业化判断**（定价、市场进入、竞争策略），按既有纪律"商业/战略不入库"。
4. **未评估**：阶段 1/2 的人力与时间估算（本项目不设到达时间）；也未评估"若阶段 0 流片失败"的后果。
5. **一处内部的、必须承认的自相矛盾**（判断 4）：项目以"拒绝未验证声明"为纪律，但**自身"能设计出可流片芯片"这一最大声明目前未验证**。这是本评估给出的**最紧迫结论**。
6. **一句话**：**LDA 的栈已经比大多数人以为的完整；它缺的不是代码，是两次外部动作 —— 一次 PDK 准入，一次真实流片。**
