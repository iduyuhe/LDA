# LDA v0.1 · 开源首发 Release Notes

> 发布日期：2026-08-19
> 标签：`v0.1`
> 许可：MIT
> 仓库：GitHub [`iduyuhe/LDA`](https://github.com/iduyuhe/LDA) · Gitee [`i4hub/LDA`](https://gitee.com/i4hub/LDA)

---

## LDA 是什么

LDA 是 **agent-native 的光子芯片(PDA) + 量子芯片(QEDA) 设计软件**：AI agent 递归自举核心求解器，但立了一条死规矩——

> **LLM 永远不进判决路径。** 求解对不对，只认物理定律锚与真实测量。

我们用"AI 写代码 +（定律 + 大数据）验"的开放内核，给行业一个**自主可控、不被卡脖子**的设计-验证选项。

---

## v0.1 交付了什么

### 阶段 1 · 技术验证（八任务全部实跑交付）

| # | 任务 | 交付 | 验证 |
|---|---|---|---|
| 1.1 | L0 IR（光子子集）草案 | 机器优先开放 IR 首个序列化格式 + 命名空间 | 从已验证 FDTD 核反推字段 |
| 1.2 | L1 agent + 端到端闭环 | Interpreter/Designer/SolverAgent/Verifier 编排 | 布拉格镜 R=0.9967 对 TMM \|ΔR\|=4.8e-3 PASS |
| 1.3 | 器件级几何 voxel | stack 退化与 voxel 逐位一致（max rel diff=0.0） | 真 2D 器件雏形 + TMM 双 PASS |
| 1.4 | AI-dev 自举写核闭环 | `solver_writer.py`：写→沙箱执行→ORACLE 判→失败重写 | 1D FDTD spec：v0 FAIL→v1 PASS（max_err=0.0326） |
| 1.5 | 确定性比对裁判 | `lda_harness/` B1–B11 + 物理定律锚 golden.py | 默认 11/11 PASS；`--perturb` 7/11 FAIL；`--ai` 8/11 部分 FAIL（判别均正常） |
| 1.6 | 实证大数据锚 | `empirical_bank.py` + 种子 5 实测 + 4 对抗题 | 候选 vs 实测 3/5 PASS（fail 检测正常） |
| 1.7 | 生产级超大网格 GPU 实跑 | `run_large_grid.py`（device-agnostic） | N=100(7.45s)/200(131.57s)/400(1074.27s) 三规模 ORACLE 全 PASS |
| 1.8 | 真 2D ORACLE + 器件验收闭环 | 标量 FDFD ORACLE + 标量 3D FDTD 模态源/投影 | 3 器件 3/3 PASS（Δ≤0.06，tol=0.15） |

**主权 B 级替代路径全维度实证**：1D/2D/3D 自写 FDTD 透射谱均已离线得出，踢掉 Meep 依赖；GPU 在 RTX 5060 Ti 激活验收（fp64 跨设备 bit-equivalence）。

### 阶段 2 · 生态启动（四咽喉全部材料就绪可发动）

1. **开源首发**：核心包 `lda/` + 战略文档，双平台公开 + MIT + CI 自测 + 本 tag `v0.1`（125 文件）。
2. **对抗基准 + 反向悬赏**：B1–B11 + 实证锚；Issue 模板（与 `seed_empirical.json` 字段对齐）；`BOUNTY.md`「破壁者」徽章 + Hall of Fame；GitHub 种子 Issue #1/#2。
3. **双引擎招募**：退休专家话术 + 顾问委架构、学生贡献者方案（核心 6 校）、`RECRUIT.md` 入口、`LDA_双引擎触达首信模板.md`。
4. **晶圆厂 PDK 对接**：`LDA_晶圆厂PDK对接首封话术与路线图.md`（NOEIC/CUMEC/SITRI 对接优先级 + 暖/冷双版话术 + 五步路线图）。

---

## 三条红线（不可逾越）

1. **主权求解器**：核心 FDTD/FDFD/Mie/TMM 自研，不借 GPL/Meep/Tidy3D 当求解底座。
2. **LLM 不进判决路径**：LLM 只写**代码**，判"对不对"只用确定性裁判 + 实证锚。
3. **可验证优先**：任何能力圈外的声称，必须有物理定律锚或真实测量兜底。

---

## 诚实边界

- 本版本为**研究级开源首发**，非商业签核工具；验证覆盖光子单点垂直场景（波导/布拉格镜），分束器/交叉等更复杂真 2D 器件待扩展 FDFD 验收锚。
- 种子实证数据为公开文献量级示例，真实测量语料待社区/退休专家/晶圆厂补登。
- GPU 价值在显存容量/带宽（消费卡 fp64≈1/64 fp32）；生产默认仍 numba-CPU（已 43.1×）。
- 晶圆厂 PDK 意向、顾问委员会成立、稳定外部贡献者三项为**发动期 KPI**，依赖实际触达，非代码可完成。

---

## 如何参与

- 贡献代码 / 找 `good-first-issue`：[RECRUIT.md](RECRUIT.md)
- 提交实测语料 / 设计对抗题：`.github/ISSUE_TEMPLATE/`
- 反向悬赏（破壁者计划）：[BOUNTY.md](BOUNTY.md)
- 晶圆厂 / 顾问对接：`LDA_晶圆厂PDK对接首封话术与路线图.md` · `LDA_退休专家招募话术与顾问委员会架构.md`

---

*LDA v0.1 — 自主可控光子+量子 EDA，从"AI 写 + 定律验"开始。*
