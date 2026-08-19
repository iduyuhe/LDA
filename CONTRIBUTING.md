# 贡献指南（CONTRIBUTING）

感谢关注 **LDA**——一个 Agent-native 的光子芯片（PDA）+ 量子芯片（QEDA）设计软件，核心是 **AI agent 递归自举主权求解器**。

## 三条不可逾越的红线（红线即护城河）

1. **主权求解器**：FDTD / FDFD / Mie / TMM 等核心数值内核**不依赖** GPL/Meep/Tidy3D 等外部求解器，必须可独立运行、可逐位验证。
2. **LLM 不进判决路径**：大模型只负责"写代码 / 提方案"，**绝不**参与数值正确性判决。所有判分由确定性 ORACLE（物理定律锚 + 实测语料锚）完成。
3. **可验证优先**：任何新求解器 / 新器件模型，必须带可复现的自测（golden 物理定律锚 + 开放对抗题），否则不进主线。

## 如何贡献

- **Issue / 对抗题**：欢迎提交"让 AI 求解器翻车"的题——这正是 `lda/lda_harness/` 确定性裁判与实证锚要接住的。
- **求解器 PR**：请附带自测（参考 `run_harness.py` 的 B1–B11 范式），并在 PR 描述说明它守住哪条红线。
- **实测语料**：晶圆厂 / 退休专家 / 社区的真实测量数据，可通过 `empirical_bank.py` 的 `add` 接口登记，作为对抗纯 AI 互证的实证大数据锚。

## 本地自测

```bash
cd lda
python run_harness.py                 # 确定性比对裁判 B1-B11
cd lda/lda_harness
python run_empirical_bank.py          # 实证大数据锚
```

## 许可

本项目以 MIT 许可开源（见 `LICENSE`）。
