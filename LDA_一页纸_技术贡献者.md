# LDA 一页纸 · 技术贡献者 / 学生

> 面向：开发者、研究生、本科生（想参与开源光子+量子 EDA）

---

## 一句话
LDA 是 agent-native 光子(PDA)+量子(QEDA) 芯片设计软件；**LLM 只写代码、不判对错**，对错由物理定律锚 + 真实测量决定。我们在找能写求解模块、能出题、能报缺陷的人。

## 你能得到什么
- **确定性裁判自动验收**你的求解模块——不用自己证明"对不对"。
- **真开源署名**——代码进 GitHub/Gitee，专家验收背书，简历有硬货。
- **毕设/竞赛挂钩**——"自然语言→GDSII"天然是毕设题；"破壁者"悬赏包装成校内赛题。
- **从使用者变建造者**——不是用 EDA，是和 AI 一起造 EDA。

## 怎么起步
1. 看 [README](README.md) + [RECRUIT.md](RECRUIT.md)，跑通 `run_harness.py`（B1–B11 裁判）。
2. 找 `good-first-issue` 标签，挑一个起步。
3. 提交实测语料 → `empirical_measurement.yml`；设计对抗题 → `adversarial_benchmark.yml`；报缺陷 → `bug_report.yml`。

## 技术栈与证据（已实跑）
- 主权求解核：自写 FDTD 1D/2D/3D（零依赖 numpy），TMM 物理定律锚交叉校验 5/5 PASS。
- GPU 实跑：N=100/200/400 三规模 ORACLE 全 PASS（N=400 跑通 6400 万点）。
- 真 2D 器件：标量 FDFD ORACLE + 标量 3D FDTD 投影，3/3 PASS。
- AI-dev 写核闭环：写→沙箱执行→ORACLE 判→失败重写，已验证。

## 红线（别碰）
主权求解器自研 · LLM 不进判决路径 · 任何声称必须有物理/测量兜底。

## 入口
[RECRUIT.md](RECRUIT.md) · GitHub `good-first-issue` · [CONTRIBUTING.md](CONTRIBUTING.md) · 仓库：GitHub `iduyuhe/LDA` / Gitee `i4hub/LDA`（MIT）
