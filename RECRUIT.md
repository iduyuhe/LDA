# LDA 双引擎招募 · 参与共建入口

> LDA 是 agent-native 光子芯片(PDA) + 量子芯片(QEDA) 设计软件：AI agent 递归自举核心求解器，**LLM 永远不进判决路径**——求解对不对，只认物理定律锚与真实测量。
>
> 我们要的不是 star，是**两种人**：有时间有热情的**学生**，和有资源有情怀的**退休专业人士**。二者构成 LDA 开源生态的双引擎。

---

## 一、学生线（开源贡献生力军）

- 详细方案：[`LDA_学生贡献者招募方案.md`](LDA_学生贡献者招募方案.md)
- 布点：上交 / 华科 / 中科大 / 浙大 / 电子科大 / 西电
- 挂钩：毕业设计 / 竞赛 / 科研课题（"自然语言→GDSII" 天然是毕设题）
- 入口：
  - 提交实测数据 → [`empirical_measurement.yml`](.github/ISSUE_TEMPLATE/empirical_measurement.yml)
  - 设计对抗题 → [`adversarial_benchmark.yml`](.github/ISSUE_TEMPLATE/adversarial_benchmark.yml)
  - 报缺陷 → [`bug_report.yml`](.github/ISSUE_TEMPLATE/bug_report.yml)
  - 找 `good-first-issue` 标签起步

## 二、退休专家线（顾问 / 导师 / 质量策展）

- 详细方案：[`LDA_退休专家招募话术与顾问委员会架构.md`](LDA_退休专家招募话术与顾问委员会架构.md)
- 三类人群：EDA 老炮（PDK/签核/策展）· 光电半导体退休研究员（对接/背书）· 高校退休博导院士级（战略背书）
- 顾问委员会分层：名誉顾问（L1）/ 技术顾问（L2）/ 基准题库策展组（L3）
- 边界铁律：顾问**不参与代码判决**，只做策展、背书、对接——判决只走确定性裁判与实证锚

## 三、反向悬赏（破壁者计划）

- 文案：[`BOUNTY.md`](BOUNTY.md)
- 征集：真实实测语料 + "让 AI 求解器翻车"的对抗题
- 奖励：署名 Hall of Fame + 「破壁者」徽章（诚实标注：当前无现金赏金，视 sponsors 而定）
- 评审闭环：提交 → 入库 → AI-dev 写核 → 确定性裁判(B1–B11) + 实证锚验收 → 翻车记 release notes

## 四、三条红线（不可逾越）

1. **主权求解器**：核心 FDTD/FDFD/Mie/TMM 自研，不借 GPL/Meep/Tidy3D 当求解底座。
2. **LLM 不进判决路径**：LLM 只写**代码**，判"对不对"只用确定性裁判 + 实证锚。
3. **可验证优先**：任何能力圈外的声称，必须有物理定律锚或真实测量兜底。

---

*贡献者守则见 [`CONTRIBUTING.md`](CONTRIBUTING.md)；自动化自测见 CI（每次 push 跑 B1–B11 裁判 + 实证锚）。*
