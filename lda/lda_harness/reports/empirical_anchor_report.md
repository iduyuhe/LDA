# LDA 实证大数据锚 · 报告

- corpus 条目: 5
- adversarial 题目: 4

## 候选 vs 实测（实证锚）

| id | metric | 实测 | ±σ | 候选 | 误差 | 判定 |
|---|---|---|---|---|---|---|
| E-SOI-NEFF-220 | n_eff | 2.63 | 0.02 | 2.62 | 0.01 | PASS |
| E-SIN-NEFF-300 | n_eff | 1.53 | 0.02 | 1.58 | 0.05 | FAIL |
| E-YBRANCH-LOSS | split_loss_dB | 3.4 | 0.3 | 3.5 | 0.1 | PASS |
| E-RING-FSR | FSR_nm | 9.15 | 0.1 | 9.1 | 0.05 | PASS |
| E-GRATING-EFF | coupling_eff | 0.45 | 0.05 | 0.52 | 0.07 | FAIL |

## 对抗性题库
- **A-BEND-R2** (小弯曲半径弯曲损耗): 让求解器在 R=2um 强受限弯曲上翻车（弱导模辐射 + 模式失配） [tol=0.5]
- **A-CROSS-TIGHT** (紧间隙波导交叉串扰): gap=0.1um 紧间隙交叉，求解器常高估隔离度 [tol=5.0]
- **A-TAPER-FAST** (快速锥度（绝热失效区）传输效率): L=5um 极短锥度，绝热极限 T→1 失效，求解器易高估 [tol=0.02]
- **A-HETERO-MODE** (异质集成模场失配耦合): Si 波导到 III-V/光纤的模场失配耦合，求解器场重叠易算错 [tol=0.05]

*实证锚=真实器件测量语料；LLM 不进判决路径。种子为公开文献量级，须社区/退休专家补真实测量。*