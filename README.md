# LDA · Agent-native 光子/量子芯片设计软件

> LDA（Lightwave Design Agent）= 光子芯片(PDA) + 量子芯片(QEDA) 的开源、主权、Agent-native 设计软件。
> 核心主张：**底层核心求解器由 AI agent 递归自举开发**，人类做架构与验证，AI 不进入判决路径。
> 当前版本：**v0.3**（2026-08-21 · 设计→验证闭环引擎 + 统一设计包规范 + 混合巨型系统）

## 这是什么

LDA 是一套面向光子集成回路（PIC）与超导量子比特（QEDA）的**设计→验证闭环引擎**。它把"AI agent 写内核、确定性裁判验收"的工程范式落成可运行、可验证、可复现的代码，让普通算力（纯 numpy、零 GPU）就能自助完成**从设计目标到已验证器件/系统**的闭环，并把**物理定律锚 + 实证大数据锚**作为信任地基，而非依赖任意大模型意见。

**v0.3 的核心能力（D-36~D-53）**：给系统一个设计目标（如"f01=5GHz 的 Transmon"、"FSR=17.5nm 的环形分波器"、"N qubit 频率复用读出"、"多环 WDM × 量子读出混合系统"），LDA 自动完成 **参数搜索 → 真实求解器双重验证 → 返回被验证过的设计**，并以**统一设计包（DesignPackage）**格式交付——LLM 不进判决路径，是否 PASS 由死标量比对决定。

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

## WebUI（二十五面板，设计闭环可视化）

LDA 自带零依赖 WebUI（`python lda/lda_webui/deploy.py start`，默认 `http://127.0.0.1:8787`），首屏自动演示全部闭环：

`①求解器验收` `②1D FDTD` `③Mie` `④FDFD` `⑤耦合器验收` `⑥统一 IR` `⑦TMM` `⑧B 基准题` `⑨版图流水线` `⑩Bootstrap` `⑪多层验证` `⑫对抗基准` `⑬器件库（含量子双验证）` `⑭设计→验证闭环` `⑮环形 add-drop 产品链路` `⑯agent 逆设计框架` `⑰量子逆设计闭环` `⑱WDM 多环系统` `⑲readout 混合链路` `⑳统一设计包` `㉑N-qubit 频率复用读出` `㉒单发读出保真度预算` `㉓N-qubit 逐 qubit 保真度` `㉔WDM×readout 混合巨型系统` `㉕方向耦合器设计闭环`

## 统一设计包规范（对外标准 · 9 kind）

- 正式规范文档：[docs/design_package_spec.md](docs/design_package_spec.md)（schema 定义 / kind 注册表 / 校验规则 / 扩展指南）
- 机器可读 JSON Schema：[docs/design_package_schema.json](docs/design_package_schema.json)（draft-07，jsonschema 校验全部 kind conforms）
- kind：`add_drop` `quantum` `wdm` `readout_chain` `multiqubit` `readout_fidelity` `multiqubit_fidelity` `mixed_system` `coupler`

## 目录结构

```
lda/                     核心软件包（主权求解器 + agent + 设计引擎 + harness）
  lda_solver/            FDTD/FDFD/Mie/TMM/Transmon/Resonator/Coupler 自研求解器
  lda_agent/             设计→验证闭环、逆设计框架、WDM/readout 系统级设计、AI-dev 写核
  lda_design/            设计引擎 + 统一设计包规范（DesignPackage）
  lda_ir/                统一 IR（光子+量子，schema v0.3，PhysicsAnchor）
  lda_l2/                器件库（已验证资产）+ GDS 编码器 + DRC + 版图仿真
  lda_harness/           确定性比对裁判（13 标准题物理定律锚 B1-B13）
  lda_webui/             零依赖 WebUI（二十五面板）
docs/                    design_package_spec.md + design_package_schema.json
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

# ⑧ 确定性比对裁判（13 标准题物理定律锚）
python lda/run_harness.py --ai

# ⑨ GPU 实跑激活（L2-B 第三步：CUDA 检测 → 5 例锚 selfcheck → cuda↔cpu bit-equivalent 互证 → 加速比）
python lda/lda_solver/activate_gpu_fdtd3d.py

# ⑩ WebUI（二十五面板，首屏自动演示）
python lda/lda_webui/deploy.py start --port 8787
```

## 仓库镜像

- GitHub: https://github.com/iduyuhe/LDA
- Gitee:  https://gitee.com/i4hub/LDA

## 变更记录

见 [CHANGELOG.md](CHANGELOG.md)（v0.2：设计→验证闭环引擎 + 统一设计包规范；**v0.3：GPU 激活 + 量子读出最终形态 + 混合巨型系统**）。

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
