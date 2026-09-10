# LDA 验证成熟度模型（Verification Maturity Model, VMM）

> **定位**：本项目（开源 Agent 原生光/量 EDA）的验证体系不是「要么 100% 独立验证、要么不准发布」的二元开关，而是一条**可审计、可逐步升级的成熟度阶梯**。本模型是项目自身的研究成果，是我们对外「底气」的公开依据，也是防止「卡在某一点耽误整个体系」的工程纪律。
>
> **确立时间**：v0.9.62（2026-09-09/10 严肃复核收口后）。背景：B16 假绿事件暴露「想多报一个数」的诱惑；同时确认 25 道自证桩是**真实验证缺口**而非低垂接线果。结论——自证是**合法的第一阶段**，但必须诚实标注、带升级路径、守底线。

---

## 1. 核心命题：自证是阶段，不是缺陷

验证成熟度分四级。任何锚都落在一级，且**只能由下往上、按环境可用性升级**，不得越级谎报。

| 层级 | 名称 | 判定标准（与 harness 一致） | 含义 | 升级触发条件 |
|---|---|---|---|---|
| **Tier-1** | 自证（self_certified） | 无有效独立候选；`candidate≡golden` 自洽 | 内部自洽的设计规则/闭式锚，**未获外部证伪** | 接独立候选 / 外部 ORACLE |
| **Tier-2** | 降级量级（degraded） | `candidate_status="degraded_ordinal"` | 有候选但模型粗糙度超死标量判决列，仅作量级参考 | 标定工艺系数后升 Tier-3 |
| **Tier-3** | 严格独立（strict_independent） | 有方法学独立的 `candidate` 且经死标量比对通过 | 已被异源方法/外部实测证伪过 | 红队持续攻击存活 |
| **Tier-4**（规划） | 红队存活（redteam_survived） | 经独立红队出题攻击 + 锚死标量判卷仍 PASS | 外部对抗下仍可证伪 | — |

**当前账本（权威，C2 护栏守护）**：Tier-3 = 26 道 · Tier-2 = 1 道(E9) · Tier-1 = 25 道 · **合计 52 道**。

---

## 2. 底线（Baseline，任何锚不可逾越的 6 条）

> 这是「先评估、把握一个底线、再逐步升级」的底线。护栏 `run_maturity_baseline_smoke.py` 强制守护。

1. **判决路径无 LLM**：PASS/FAIL 由死标量 `compare_fn` 定，LLM 只出题不参与判决（红队=生成侧）。
2. **死标量比对**：一律 `spec.compare_fn`，禁裸 `abs(diff)`；不等式锚 `cmp='le'`。
3. **不伪装独立**：不得把 `candidate≡golden` 包装成独立（判据 D：扫自身离散参数残差须浮出双精度噪声地板且单调收敛，否则=代数恒等虚报）。
4. **诚实标注**：Tier-1 不得标成 Tier-3；Tier-2 不得标成 Tier-3。错标由 C2 护栏抓（账本漂移即红）。
5. **provenance 标签（细分 6 类）**：每锚标来源（`external_textbook` / `external_empirical` / `independent_cross_check` / `design_rule_anchor` / `self_authored_closed_form` / `self_authored_closed_form_with_check`）。其中 **`self_authored_closed_form`（自写闭式未验）** 自动降权「低置信·待 ORACLE」；`design_rule_anchor`（行业设计规则/经验下限上限）与 `self_authored_closed_form_with_check`（自写闭式已内验）**不进**低置信名单——前者是外部来源、后者已交叉验证，二者均非「安静翻车」高危区。
6. **升级路径**：每道 Tier-1 必须写明「升 Tier-3 需要什么」（哪个 ORACLE / 求解器 / 数据集），无路径=设计边界（terminal Tier-1，如纯算术合成锚）。

---

## 3. provenance 分类法（golden 来源可信度 · 细分 6 类）

| provenance 值 | 含义 | Tier-1 内置信度 | 是否进低置信名单 |
|---|---|---|---|
| `external_textbook` | 教科书/第一性原理闭式（带 DOI） | 中 | 否 |
| `external_empirical` | 实证测量语料（带 empirical_id，论文/流片实测） | 中 | 否 |
| `independent_cross_check` | Tier-3：golden 已被独立候选证伪 | 高 | 否 |
| `design_rule_anchor` | **行业设计规则/经验下限上限**（硅光几十年论文与流片共识，如 B5 3dB/B6 0.5/B7 -40dB） | 中 | **否**（外部来源，非自写） |
| `self_authored_closed_form` | 项目自写闭式近似（**未经任何外部 ORACLE/内验**） | **低** | **是**（B16 即此类，曾错 33%） |
| `self_authored_closed_form_with_check` | 自写闭式但**已有内部全波/解析交叉验证**（如 B21 的 2D FDTD 内验~2%） | 中 | **否**（已内验，非高危） |

**关键纪律**：只有 `self_authored_closed_form`（**纯未验自写闭式**）是「安静翻车」高危区——B16 因子 3 错 33% 直到本轮才修。故**仅此类**自动进「低置信·待再审计」名单。`design_rule_anchor` 虽几何无关（仅下限/上限），但来源是外部行业共识，不算自写；`self_authored_closed_form_with_check` 已内验，置信度高于纯未验自写闭式。

> 🔑 **细分的目的（用户定调）**：把 provenance 拆细，是为了**精准区分「必要的验证」与「不必要的验证」**——见 §4.1。避免对已有外部背书的锚重复投入验证资源，把精力集中在真正未验的自写闭式上。

---

## 4. 升级路径政策（专题攻关，不阻塞主链路）

- **不阻塞**：52 锚全在、全自洽、全诚实标注即可交付完整系统；不为「证明」卡住主链路。
- **专题攻关**：高投入升级（接 Tidy3D 外部 ORACLE、量子 T2 实测数据集、rib-MMI 严格求解器）作为**专项 sprint**，按**环境可用性 + 业务价值**排优先级，非日常阻塞项。

### 4.1 🔑 必要验证 vs 不必要验证（资源投放纪律）

> 用户定调（2026-09-10）：「必要的验证一定要做，但不必要的验证一定要避免。」这是 provenance 细分的直接目的。

| 类别 | 判定标准 | 是否需要我们亲手验证 | 项目处置 |
|---|---|---|---|
| **`self_authored_closed_form`（纯未验自写闭式）** | 来源是项目自写近似、无任何外部 ORACLE/内验背书（如 B16 旧因子、B11 判据 D 陷阱） | **必要** | 必须接独立求解器/外部 ORACLE 才算真升 Tier-3；在此之前保持低置信·待再审计 |
| **`design_rule_anchor`（行业设计规则锚）** | 来源是硅光几十年论文与流片经验共识的下限/上限（B5 3dB/B6 0.5/B7 -40dB） | **不必要** | 已有外部来源背书，无需我们重流片复测；仅在需要几何相关精确真值时接 ORACLE **动态升格**（可排期，非阻塞） |
| **`external_empirical`（论文实测语料）** | 来源是可溯源论文/流片实测（E1–E7 带 DOI/arXiv） | **不必要**（验证已由其来源完成） | 接受为合法 ORACLE；仅需**几何/工艺对齐 + 不确定度量化**后可升 Tier-3，无需重测 |
| **`self_authored_closed_form_with_check`（已内验自写闭式）** | 自写但已有内部全波/解析交叉验证（B21 的 2D FDTD 内验~2%） | **局部必要** | 内验已覆盖量级，待特定结构外部 ORACLE 标定即可升格；非高危区 |

**结论**：B5/B6/B7、E1–E7 这 10 个锚**不必我们亲手验证**——它们的真值已由论文/行业共识背书。我们的验证资源应**集中投放在 `self_authored_closed_form` 那几个真未验的锚**（B2 已近可升、B11 判据 D、B16/B21 待求解器/ORACLE），以及红队对 Tier-3 的持续攻击。这正避免「为证明而证明」卡住体系。

- **优先级建议（按 §4.1 收紧）**：
  - 已可得（必要且低投入）：B2（独立 1D 平板超越方程两步解已存在，差 0.018<tol，近期可权线升 Tier-3）。
  - 待环境但**非必要亲自验证**：B5/B6/B7（设计规则锚，ORACLE 命中即升；不命中也已有下限护栏）、E1/E3–E7（论文实证锚，几何对齐后升）。
  - 待求解器（必要·高投入）：B16（rib-MMI 严格求解器）、B21（独立 PhC 2D FDTD 全波 ORACLE）。
  - 本就不升（terminal Tier-1）：B17（定义同义反复）、B18（regime 越界）、S1–S6/S9–S12（系统/算术合成校验，非物理锚）。

---

## 5. 与现有护栏的衔接

- **C2 三分类护栏**（`run_three_class_consistency_smoke.py`）：README 账本 ≡ harness 推导 ≡ `/api/verification_ledger` 端点，漂移即红。守护「标签≠行为」。
- **可证伪性 smoke**（`run_benchmark_falsifiability_smoke.py`）：52 锚无回归、灵敏度上界、行为判据反向自检。守护「全绿≠无失真」。
- **成熟度基线 smoke**（新增 `run_maturity_baseline_smoke.py`）：每锚含 `maturity_tier`+`provenance`，Tier-1 必含 `upgrade_path`，**仅 `self_authored_closed_form`（纯未验自写闭式）自动入低置信名单**（不含 `design_rule_anchor` 与 `self_authored_closed_form_with_check`）。守护「底线 6 条」。
- **红队自动化**（已建 `run_redteam_anchor_fuzz_smoke.py`，接 `generator="llm"` + BOUNTY.md）：让 Tier-3 也被外部攻击过一遍，迈向 Tier-4。

---

## 6. 对外叙事（底气话术）

> 「LDA 已交付完整 52 锚验证体系：26 道经异源方法严格独立证伪（Tier-3），1 道降级量级参考（Tier-2），25 道为内部自洽的设计规则锚（Tier-1）——每道均带 **细分 provenance 来源标签**（外部教科书 / 外部实证论文 / 异源交叉验证 / 行业设计规则锚 / 自写闭式 / 自写闭式已内验）与明确升级路径。**其中仅纯未验自写闭式（15 道）显式降权待外部 ORACLE**；行业设计规则锚（3 道 B5/B6/B7）与自写闭式已内验（B21）不进低置信名单——它们的可信度由外部行业共识或内部全波验证背书，无需我们重复验证。验证成熟度阶梯是项目自身的工程纪律，不是缺陷清单。」

——这把「48% 未独立验证」的潜在质疑，转化为「透明、可审计、有路线图的成熟度模型」，正是护城河可信度的来源。
