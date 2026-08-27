# 贡献指南（CONTRIBUTING）

感谢关注 **LDA**——一个 Agent-native 的光子芯片（PDA）+ 量子芯片（QEDA）开源设计软件，核心是 **AI agent 递归自举主权求解器**，人类做架构与验证，AI 不进判决路径。

当前版本：**v0.8.34** · 账本：**22 引擎（光子 15 + 量子 7）+ 11 包 = 33 类端到端 · 45 题锚（B1-B27 + E1-E7 + S1-S11）· CI core 68 条**。

## 三条不可逾越的红线（红线即护城河）

1. **主权求解器**：FDTD / FDFD / Mie / TMM / 严格对角化等核心数值内核**不依赖** GPL/Meep/Tidy3D 等外部求解器，必须可独立运行、可逐位验证。
2. **LLM 不进判决路径**：大模型只负责"写代码 / 提方案"，**绝不**参与数值正确性判决。所有判分由确定性 ORACLE（物理定律锚 + 实测语料锚）完成。
3. **可验证优先**：任何新求解器 / 新器件模型，必须带可复现的自测（golden 物理定律锚 + 开放对抗题），否则不进主线。

## 如何参与（阶段 B · 生态播种）

- **⭐ Star 仓库**：<https://github.com/iduyuhe/LDA>——你的 Star 是社区信号，也是对外可达性的杠杆。
- **🐛 认领 Good First Issue**：见 [Issues · good first issue 标签](https://github.com/iduyuhe/LDA/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)。挑一个、评论认领、按本指南提 PR。
- **📐 提交实测语料 / 对抗题**：见 `BOUNTY.md` 反向悬赏机制（实证大数据锚是验证的第二道非 AI ground）。
- **📖 技术叙事**：我们在公众号「工业5点0产业生态联盟」与知乎持续发布 LDA 设计哲学与闭环演示。

## 本地自测（CI core 门禁）

```bash
# 用项目 venv（Python 3.13），不要系统 3.14
cd lda
python run_ci_regression.py --tag core      # CI core 全量（65 条 smoke）
python run_count_consistency_smoke.py        # 计数守护：账本与 pyproject 一致性
python run_parasitic_rc_smoke.py             # 几何寄生估算
```

> 新增代码必须带自测并让 CI core 全绿（FAIL=0 即绿）。计数守护会校验「当前账本」与 `pyproject` 版本，改动账本请同步 README 与 `pyproject.toml`。

## PR 约定

- 一个 PR 做一件事；描述说明它守住哪条红线、动了哪些计数。
- 命名参考：`[GFI] ...` / `[fix] ...` / `[feat] ...`。
- 不 `git add -A`：运行产物（`lda/reports/*`）不入库，避免阻塞生产 `git pull`。
- 生成物的诚实边界（如"非 foundry 工艺级 deck"）必须在代码与文档中显式标注。

## 许可

本项目以 MIT 许可开源（见 `LICENSE`）。贡献即视为同意以同等许可收录。
