# 25 自证桩性质分层清单（Verification Maturity Model · Tier-1 资产台账）

> 配套模型：`docs/verification_maturity_model.md`
> 数据来源：本文件由 `lda/lda_harness/benchmarks.py` 的 `maturity_tier` / `provenance` / `upgrade_path` 三字段直接导出（2026-09-10 实测），非记忆推断。
> 三分类口径（C2 护栏守护）：严格独立 26 · 降级 1 · 自证桩 25（和 = 52）。

## 一、为什么这张表存在

自证桩（Tier-1）不是"未验证的缺口清单"，而是**带来源、带升级路线、守底线的合法第一阶段**。
但 25 个自证桩**性质并不相同**——有的 golden 曾算错、有的缺外部真值、有的本就不该升。
把性质摊开，才能：(1) 对外诚实交底；(2) 把升级资源投到对的地方；(3) 防止"安静地错"（如 B16）。

## 二、性质分层（5 类）

| 类别 | 含义 | 锚 |
|---|---|---|
| **Ⅰ·曾错已修** | golden 历史算错、已修正，但仍缺独立求解器，故仍 Tier-1 | B16 |
| **Ⅱ·缺外部 ORACLE/数据集** | 引擎已自洽/已内验，但需外部全波或实测真值才能升 Tier-3 | B21 E1 E3 E4 E5 E6 E7 |
| **Ⅲ·近可升待接线** | 独立异源解已存在且差<tol，仅 harness 未正式挂候选 | B2 |
| **Ⅳ·判据 D 陷阱** | candidate≡golden 残差≡0 的代数恒等，须双向标定才算真独立 | B11 |
| **Ⅴ·本就不升（terminal Tier-1）** | 定义同义反复 / regime 越界 / 纯算术合成校验，永不该升格 | B17 B18 S1 S2 S3 S4 S5 S6 S9 S10 S11 S12 |
| **Ⅵ·设计规则锚/场级ORACLE分层** | 来源为硅光行业共识下限/上限（**外部来源**，非自写）；ORACLE 命中即动态升格，**无需我们重测** | B5 B6 B7 |

**计数核对**：Ⅰ(1) + Ⅱ(7) + Ⅲ(1) + Ⅳ(1) + Ⅴ(12) + Ⅵ(3) = **25** ✓

> 🔑 **细分意义（用户定调 2026-09-10）**：原 Ⅱ 类把「B5/B6/B7（行业设计规则锚·外部来源）」与「B21/E系列（真需外部ORACLE）」混为一谈，会误导「这 10 个都缺外部验证、都要我们做」。细分后 Ⅵ 类明确：**B5/B6/B7 不是缺验证，是有外部行业背书、几何无关的下限/上限**——属于「不必要的验证」，无需重复投入；验证资源应集中在 Ⅰ/Ⅱ/Ⅳ 那几个真未验的自写闭式上。

## 三、逐锚可追溯表

| 锚 | 物理对象 | provenance | 性质分类 | 是否可升 | 升级条件 / 路径 | 置信度 |
|---|---|---|---|---|---|---|
| B16 | MMI 1×2 自映像长度 | self_authored_closed_form | Ⅰ·曾错已修 | 待接求解器 | rib-MMI 严格求解器（symmetric-slab EME 非同对象不可用）；golden 因子已修 3→9/4 | 低（已修但仍自证） |
| B2 | SOI 波导 n_eff | self_authored_closed_form | Ⅲ·近可升待接线 | **可升（漏接）** | 独立 1D 平板超越方程两步解已存在（2.6327 vs golden 2.6509，差 0.018<tol 0.05），仅 harness 未挂候选 | 中（golden 干净，独立解在手） |
| B11 | （判据 D 命中锚） | self_authored_closed_form | Ⅳ·判据D陷阱 | 待标定 | 需正交独立求解器；当前 candidate≡golden 残差≡0，须双向标定 | 低 |
| B5 | Y 分支分束插入损耗 | design_rule_anchor | Ⅵ·设计规则锚 | 无需重测（外部来源） | 行业设计规则锚 3.0dB 下限（硅光论文/流片共识；D-66 澄清含 3.01dB 理想分光）；真场级 ORACLE 命中即动态升格（B 级借今踢后）；已有回退下限护栏 | 中（外部行业背书·非低置信） |
| B6 | 光栅耦合峰值效率 | design_rule_anchor | Ⅵ·设计规则锚 | 无需重测（外部来源） | 行业设计规则锚 0.5 效率下限（硅光耦合器论文/流片共识）；Tidy3D ORACLE 命中即升格；已有回退下限护栏 | 中（外部行业背书·非低置信） |
| B7 | 波导交叉串扰 | design_rule_anchor | Ⅵ·设计规则锚 | 无需重测（外部来源） | 行业设计规则锚 -40dB 上限（硅光交叉器件论文/流片共识）；Meep ORACLE 命中即升格；已有回退下限护栏 | 中（外部行业背书·非低置信） |
| B21 | PhC 腔共振 | self_authored_closed_form_with_check | Ⅱ·已内验待ORACLE | 待ORACLE标定 | 弱调制布拉格 FP 一阶近似；已有 2D FDTD 全波内验~2%（已内验·非低置信·非高危）；待特定结构外部 ORACLE 标定升 Tier-3 | 中（已内验，非低置信·待再审计） |
| E1 | 量子实证锚 | external_empirical | Ⅱ·缺数据集 | 待数据集 | T2 实测数据集（量子 QEDA 实证锚）升 Tier-3 | 中（有实证来源，待扩样） |
| E3 | 量子实证锚 | external_empirical | Ⅱ·缺数据集 | 待数据集 | T2 实测数据集升 Tier-3 | 中 |
| E4 | 量子实证锚 | external_empirical | Ⅱ·缺数据集 | 待数据集 | T2 实测数据集升 Tier-3 | 中 |
| E5 | 量子实证锚 | external_empirical | Ⅱ·缺数据集 | 待数据集 | T2 实测数据集升 Tier-3 | 中 |
| E6 | 量子实证锚 | external_empirical | Ⅱ·缺数据集 | 待数据集 | T2 实测数据集升 Tier-3 | 中 |
| E7 | 量子实证锚 | external_empirical | Ⅱ·缺数据集 | 待数据集 | T2 实测数据集升 Tier-3 | 中 |
| B17 | （定义类锚） | self_authored_closed_form | Ⅴ·本就不升 | 永不 | 定义同义反复（terminal Tier-1） | 高（结构性无需升） |
| B18 | （regime 类锚） | self_authored_closed_form | Ⅴ·本就不升 | 永不 | regime 越界（terminal Tier-1） | 高 |
| S1 | 功率预算 | self_authored_closed_form | Ⅴ·本就不升 | 永不 | 系统/算术合成校验（非物理锚） | 高 |
| S2 | 频率碰撞 | self_authored_closed_form | Ⅴ·本就不升 | 永不 | 系统/算术合成校验 | 高 |
| S3 | （系统合成） | self_authored_closed_form | Ⅴ·本就不升 | 永不 | 系统/算术合成校验 | 高 |
| S4 | （系统合成） | self_authored_closed_form | Ⅴ·本就不升 | 永不 | 系统/算术合成校验 | 高 |
| S5 | 最坏情况 | self_authored_closed_form | Ⅴ·本就不升 | 永不 | 系统/算术合成校验 | 高 |
| S6 | （系统合成） | self_authored_closed_form | Ⅴ·本就不升 | 永不 | 系统/算术合成校验 | 高 |
| S9 | （结构不可接） | self_authored_closed_form | Ⅴ·本就不升 | 永不 | 系统/算术合成校验 | 高 |
| S10 | （结构不可接） | self_authored_closed_form | Ⅴ·本就不升 | 永不 | 系统/算术合成校验 | 高 |
| S11 | （结构不可接） | self_authored_closed_form | Ⅴ·本就不升 | 永不 | 系统/算术合成校验 | 高 |
| S12 | （结构不可接） | self_authored_closed_form | Ⅴ·本就不升 | 永不 | 系统/算术合成校验 | 高 |

## 四、关键发现与行动项

1. **B16 是唯一"曾错"的 golden**：因子 3→9/4 已修（W=2.8µm→27.3µm≈实测 27µm，误差<1%）。但它仍 Tier-1——因为没有合格的 rib-MMI 独立求解器。**教训已沉淀为红线**：独立候选必须建模与 golden 同一物理对象（B16 的 symmetric-slab EME 是错对象）。
2. **B2 是唯一"近可升待接线"**：独立 1D 平板超越方程两步解已存在且差 0.018<tol，仅 harness 未正式挂候选。这是 25 自证桩里**唯一一个低投入即可升 strict 的**——建议作为下一个轻量攻关（挂 `slab_te_neff` 类候选即可）。
3. **Ⅱ 类（7 个）是「必要且重投入」的验证区**：B21 的 2D FDTD 全波 ORACLE、E 系列的 T2 实测数据集，都需环境（资金/ORACLE 通道/C 期）具备时作为**专题 sprint**，不做主链路阻塞项。⚠️ **关键区分**：原混在 Ⅱ 类的 **B5/B6/B7 已细分到 Ⅵ 设计规则锚**——它们是外部行业共识的下限/上限（3dB/0.5/-40dB），**无需我们重测**，不属于「必要验证」；验证资源应集中在 Ⅱ/Ⅰ/Ⅳ 那几个真未验的自写闭式上，而非投在已有外部背书的锚。
4. **Ⅴ 类（12 个）永不升**：它们本就是定义/算术/合成校验，对外应明确标注"terminal Tier-1，非物理锚"，避免被误读为"未验证"。
5. **红队必须覆盖这 25 个（尤其 Ⅱ 类缺 ORACLE 的）**：见 `run_redteam_anchor_fuzz_smoke.py`——让外部攻击也打到物理锚，而非只打 S 系列预算锚。

## 五、与 B（provenance 标签）的关系

本表是 **A（性质分层分析层）**；`benchmarks.py` 的 `provenance`/`upgrade_path` 字段是 **B（来源标签层）**。
两者一一对应：本表每一行都能在 `benchmarks.py` 找到同 ID 的 `provenance` 与 `upgrade_path` 字段，经 `run_maturity_baseline_smoke.py` 护栏守护一致性。
