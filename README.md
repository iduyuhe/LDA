# LDA · Agent-native 光子/量子芯片设计软件

> LDA（Lightwave Design Agent）= 光子芯片(PDA) + 量子芯片(QEDA) 的开源、主权、Agent-native 设计软件。
> 核心主张：**底层核心求解器由 AI agent 递归自举开发**，人类做架构与验证，AI 不进入判决路径。

## 这是什么

LDA 是一套面向光子集成回路（PIC）与超导量子比特版图的设计工具链原型。它把"AI agent 写内核、确定性裁判验收"的工程范式落成可运行、可验证、可复现的代码，目标是让一台普通算力就能自助完成从器件到系统的设计闭环，并把**物理定律锚 + 实证大数据锚**作为信任地基，而非依赖任意大模型意见。

### 红线（设计原则）

- **LLM 不进判决路径**：求解器输出 vs 黄金参考的 PASS/FAIL 由死代码标量比对决定，AI 只写代码、不写判决。
- **主权优先**：核心求解器自研（FDTD/FDFD/Mie/Rayleigh/TMM 等），不外包、不借 GPL/Meep/Tidy3D 源码；可借 ORACLE 真值校验与晶圆厂 PDK。
- **可验证**：每个能力都配确定性比对裁判或物理定律锚，避免纯 AI 互证循环论证。

## 阶段1 交付状态（已全部实跑验证）

| 任务 | 内容 | 状态 |
|---|---|---|
| 1.1 L0 IR | 光子子集规范 + schema | ✅ |
| 1.2 L1 agent | Interpreter/Designer/SolverAgent/Verifier 闭环 | ✅ |
| 1.3 器件级几何 | voxel 体素化，对 TMM 逐位一致 | ✅ |
| 1.4 AI-dev 自举写核 | SolverSpec + 沙箱 + ORACLE 校验 + BootstrapLoop | ✅ |
| 1.5 确定性比对裁判 | B1–B11 物理定律锚 harness | ✅ |
| 1.6 实证大数据锚 | 实测语料 + 对抗题库框架 | ✅ |
| 1.7 生产级超大网格 GPU | RTX 5060 Ti 跑通 6400 万点（ORACLE 全 PASS） | ✅ |
| 1.8 真2D ORACLE 验收 | 真 2D 矩形波导 3/3 PASS | ✅ |

## 目录结构

```
lda/                     核心软件包（主权求解器 + agent + harness）
  lda_solver/            FDTD/FDFD/Mie 等自研求解器
  lda_agent/            L1 agent 闭环 + AI-dev 写核闭环
  lda_harness/          确定性比对裁判 + 实证大数据锚
LDA_*.md / .docx        战略、白皮书、路线图、技术说明（中文）
```

## 快速开始

```bash
# 1D/2D/3D FDTD 透射谱（numpy 后端，无需 GPU）
python lda/lda_solver/fdtd3d.py --help

# 确定性比对裁判（11 标准题物理定律锚）
python lda/lda_harness/run_harness.py --ai

# 生产级超大网格（GPU 版 torch，需先装 CUDA torch）
python lda/lda_solver/run_large_grid.py --N 100 --device cuda
```

## 仓库镜像

- GitHub: https://github.com/iduyuhe/LDA
- Gitee:  https://gitee.com/i4hub/LDA

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

## 许可证

[MIT](LICENSE)
