# LDA 一页纸 · 概览（对外可达性 · 5 分钟读懂）

> 面向：开源社区、潜在贡献者、合作方、关注光子/量子芯片设计的任何人
> 配套：完整 [README](README.md) · [LDA_项目介绍.md](LDA_项目介绍.md) · 仓库 GitHub `iduyuhe/LDA` / Gitee `i4hub/LDA`（MIT）

---

## 一句话定位
**LDA（Lightwave Design Agent）= 开源、主权、Agent-native 的光子芯片(PDA) + 量子芯片(QEDA) 设计软件**——底层核心求解器由 AI agent 递归自举开发，人类做架构与验证，**AI 只写代码、不判对错**，对错由物理定律 + 真实测量决定。

## 三句话价值
1. **主权自研内核**：FDTD 1D/2D/3D 等求解器零依赖纯 numpy 自写，通过物理定律锚校验（非借商业 EDA）；A 级商业工具永不借，B 级（gdsfactory/Meep/KLayout）可选借用并 fork 主权副本，C 级（IR/协议/求解核/物理锚）第一天自主。
2. **死标量判决、可独立验证**：22 引擎 / 45 锚（物理定律锚 + 实证语料锚 + 系统锚）全部用非 AI 的确定性标量比对——丢一个设计进来，一条命令告诉你 DRC/LVS/验收结论，无需信任何"AI 说它对"。
3. **开源即生态**：设计包、统一 IR、社区提交→评审→落地→发布全链开放；开发者一条命令（`lda design` / `lda check` / `lda report`）即可复现全部闭环。

## 5 分钟上手
```bash
# ① 设计闭环：跑一个器件，输出最优已验证候选
lda design RingResonator --target 9.0 --top-k 3

# ② 版图签核：链路 JSON → DRC/LVS 双闸报告 + GDS 落盘
lda check examples/cli_check_example.json --out reports

# ③ 对照报告：设计包 vs 解析锚/实证锚/ORACLE 死标量对照
lda report --out reports --quick

# ④ 生态互通：导入任意 GDSII（含 gdsfactory 导出）做主权几何 DRC 快查
lda check --gds your_design.gds --out reports
```
（无需 GPU；纯 numpy 快速路径。gdsfactory 为可选依赖，未装不影响以上 ①/②/③。）

## 护城河（为什么是持久窗口）
- **标准 + 生态 + PDK 供给**，而非某个求解器代码（巨头因商业模式自噬结构性不能做开放内核）。
- 物理定律锚红线：LLM 不进判决路径，PASS/FAIL 由死标量比对决定——这是对抗"纯 AI 互证"信任崩塌的地基。
- 光子 PDA + 量子 QEDA **统一**中间表示（L0）+ agent 协议层（L1），跨域复用同一套设计—验证范式。

## 路线图（三阶段 · 有序）
- **阶段 A（现在·对外可达性）**：CLI 深化 + gdsfactory 兼容 + 对照报告飞轮 + 计数守护固化——把已验证能力包装成独立可验证入口（本轮已完成）。
- **阶段 B（轻量·生态播种）**：GitHub Good First Issue、技术叙事、试点内部分享——等发动期信号，不提前外联。
- **阶段 C（发动期·解锁）**：接 B 级开源 PDK（AIM/SiEPIC/Sky130）、外部 ORACLE 进判决、实测回流、真实层表——严格等信号，启动前翻"影响半径"底稿再评估。

## 诚实边界
当前属**原理验证级非流片级**；实证锚为公开文献量级（9 条 DOI 可溯源），真实晶圆厂 NDA 实测仍属发动期。主权纪律：A 级永不借 / B 级借今踢后 / C 级第一天自主。

## 入口
[README](README.md) · [RECRUIT.md](RECRUIT.md) · `good-first-issue` · 仓库：GitHub `iduyuhe/LDA` / Gitee `i4hub/LDA`（MIT）
