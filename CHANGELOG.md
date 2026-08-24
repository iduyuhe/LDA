# Changelog

## v0.6（2026-08-24 · git tag v0.6 · 3D 逆设计纵深 + QEDA 求解器级补强）

**里程碑：破 3D 诚实边界（3D adjoint → 3D 截面 → 3D 端口验收 → 谱形×3D → 3D numba 性能 20×+）+ QEDA 求解器栈补强（transmon-resonator 色散读出三能级严格求解）**

### 核心能力（D-84~D-89，详见 `LDA_v0.6_Release_Notes.md`）

- **3D 逆设计纵深五阶**：D-84 3D adjoint 形状（3D Yee **显式转置伴随 Mᵀ 对拍 1e-15**、imp 2.02×、破 3D 诚实边界）；D-85 3D 截面形状（**宽度×厚度双软边界**、imp 3.17× 比平板提升 57%）；D-86 3D 逆设计 × 端口 S 参数联合验收（**双独立确认 FOM 1.88× + S21 1.60×**、补闭环最大缺口、聚焦 FOM≠透射 S21 认知）；D-87 谱形目标 × 3D 截面（**物理网格固定只变 omega**、加权 3.13× 逐波长 ≥3×、参数化×目标矩阵 3D 打通）；D-89 3D adjoint numba 化（**prange 并行 JIT、大域 forward 20-29× bit-level 一致、无 numba 自动回退**）。
- **QEDA 求解器级补强（D-88）**：三能级 transmon-resonator 色散读出严格求解（χ=g²α/(Δ(Δ+α)) **α 修正必要性 31×**、n_crit/Purcell/AC Stark 全套 readout 物理量、量子蓝海占位）。
- WebUI 五十二面板（v0.6 发布态）；harness 13 题（B1-B13）全过；64 smoke 全绿；三端 tree 零差异（389/389）。

### 新增/变更（post-v0.6 · D-93 生态共建框架 · 2026-08-24）
- **harness 题库扩充 B1-B13 → B1-B18**：新增 5 道物理定律锚（B14 定向耦合器 3dB 耦合长 / B15 Bragg 光栅中心波长 / B16 MMI 1×2 自成像长 / B17 约瑟夫森临界电流 / B18 腔 QED Purcell 因子）；经 `BENCHMARK_DEFS` 自动纳入统一回归（零接线），参考候选 18/18 PASS。
- **主权依赖三级分级代码化**（`lda_pdk/sovereign_deps.py`，来自战略审计 LDA-ST-001）：A 级永不借（Lumerical/Ansys、Synopsys、Cadence、Siemens、GDSFactory+商业 NDA-PDK 共 5 项）/ B 级借今踢后（gdsfactory 内核、Meep、KLayout、SAX、MPB、Nazca、Tidy3D 共 7 项，全部 fork 到 Gitee/GitCode）/ C 级第一天自主（L0 IR/DSL、L1 agent 协议、L3 AI 求解核、物理定律锚 共 4 项）。
- **开放 PDK/器件本体 Registry 地基接口**（`lda_pdk/registry.py` + `__init__.py`）：`PDKRegistry`（add/query/stats/to_json/load，与 `empirical_bank` 同构）承载社区共建器件元数据入口；诚实边界——真实晶圆厂 NDA-PDK 对接属发动期 D-62 暂缓、不在此硬编码。
- **WebUI 升级至五十三面板**：新增面板 53「生态共建框架」（D-93），后端 `/api/ecosystem` 暴露 harness(B1-B18)+主权 A/B/C+Registry 自检快照（验收 4/4 PASS）。
- 新增 `run_ecosystem_smoke.py`（4/4 PASS：harness 18/18、B14-B18 扰动 fail 检测 5/5、主权 A/B/C、Registry 接口自洽）；`run_ecosystem_report.py` 产出 `lda/reports/ecosystem_d93.json`。

### 新增/变更（post-v0.6 · D-94 生态共建深化 · 社区提交入口 · 2026-08-24）
- **社区提交入口（`lda_pdk/submit.py`，建在 D-93 Registry 地基之上）**：
  - `submit_device`：提交器件本体，自动推断主权分级（A/B/C）+ 校验 + 冲突感知 + 持久化贡献库 `contributions.json`（gitignore，不进版本库）。
  - `submit_devices_batch`：批量导入，逐条返回 accepted/conflict/rejected。
  - `BenchmarkProposal` + `ProposalStore` + `submit_benchmark_proposal`：社区可提案新的物理定律锚（id/title/metric/公式/oracle_fn/容差/默认参数），状态 = pending，**仅登记待代码评审 + golden.dispatch/physical_law 注册后纳入回归——绝不自动注入 golden 函数，LLM 不进判决路径**。
  - `list_contributions`：贡献库快照（Registry 计数 + 器件列表 + 提案列表）。
- **WebUI 升级至五十四面板**：新增面板 54「社区提交入口」，后端新增 `POST /api/ecosystem/submit|import|propose`，`GET /api/ecosystem` 增加 `community` 段；并修复面板 53 的 `runEco` 误用 POST 调只读接口（改为 `apiGet`）的隐性 bug。
- 新增 `run_ecosystem_submit_smoke.py`（10/10 PASS）、`run_ecosystem_d94_report.py`（7/7，产出 `lda/reports/ecosystem_d94.json`）。

### 新增/变更（post-v0.6 · D-95 生态共建闭环 · 社区评审流 + 提案落地 · 2026-08-24）
- **社区评审流 + 提案→golden 落地（`lda_pdk/review.py`，建在 D-94 提交入口之上）**：
  - `review_proposal`：仅 pending 可评审；approve 须附 ORACLE 参考实现源码并先过**前置确定性自测**（受限命名空间编译 + 默认参数返回有限标量），通过才置 approved；reject 直落 rejected；**缺具名评审人即拒（LLM 不进判决路径）**；每次评审写入审计轨迹（谁/何时/决定/理由/自测值）。
  - `land_proposal`：仅 approved 可落地；受限命名空间编译 ORACLE → `register_golden`（golden.py 新增模块级 `_GOLDEN_DISPATCH`/`_PHYSICAL_LAW` + 注册钩子）与 `register_benchmark`（benchmarks.py）**零接线接入统一回归** → 持久化 `landed.json`（gitignore）→ **生成 golden.py/benchmarks.py 补丁**供维护者 git 提交（**落库 live ≠ 进版本控制，权威 ORACLE 以维护者 git/PR 提交为准**）。
  - `reload_landed`：启动时按 landed.json 恢复已落地注册（live 一致性）；`list_proposals(status)`/`get_audit`/`list_landed` 查询。
- **WebUI 升级至五十五面板**：新增面板 55「社区评审流 + 提案落地」（评审/落地台 + 提案状态分布 + 审计轨迹 + 已落地补丁下载），后端新增 `POST /api/ecosystem/review|land`，`GET /api/ecosystem` 增加 `proposal_status`/`landed` 段。
- **实测闭环**：B19 微环 FSR 提案经评审落地后，harness 统一回归自动 18→**19 题 19/19 PASS**（零接线自动纳入）。
- 新增 `run_ecosystem_review_smoke.py`（18/18 PASS）、`run_ecosystem_d95_report.py`（10/10，产出 `lda/reports/ecosystem_d95.json`）。

### 新增/变更（post-v0.6 · D-96 生态共建进一步 · 评审门槛扩展 + 评审流 UI 增强 · 2026-08-24）
- **评审门槛扩展（全确定性门禁，LLM 不进判决路径；`lda_pdk/review.py` + `submit.py`）**：
  - `review_proposal` 新增三门槛：**签名完备性**（`inspect.signature`：ORACLE 必填参数 ⊆ default_params，明确报缺参）；**数值界限**（提案声明 `value_min`/`value_max`，自测值须落界内，死标量比对）；**core 双评审人 quorum**（`core=True` 提案需 2 位**不同**具名评审人批准；同评审人重复票不推进；票数入 `approvals` 列表 + 审计 `review_vote`；1 票保持 pending 记 votes=1/2，2 票才置 approved）。
  - `submit_benchmark_proposal` 新增**提交期防重守卫** `_dup_check`：oracle_fn_name 已落地（landed.json 全局权威）或公式规范化（去空白+小写）与现有 pending/approved/**landed** 提案重复 → 提交即拒。
  - 新增 **`resubmit_proposal`**：rejected → pending（被拒重提，可选更新公式/参数/值界/core），保留审计并追加 `resubmit` 记录。
  - 新增 **`review_stats`**：状态分布 + 批准/拒绝计数 + quorum 票 + 平均评审时延（review ts − submitted_at，ISO 解析）。
  - `BenchmarkProposal` 新增字段：`value_min`/`value_max`/`core`/`approvals`/`submitted_at`（缺省兼容旧 contributions.json）。
- **评审流 UI 增强（面板 55）**：评审统计条（批准/拒绝/quorum 票/平均时延）、状态筛选页签（全部/pending/approved/rejected/landed）、行内操作（批准→选中入表单、拒绝→prompt 理由、被拒→重新提交）、core 双评审徽标+票数、值界展示；面板 54 提案表单加 core 复选框 + 值界输入；后端新增 `POST /api/ecosystem/resubmit`，`GET /api/ecosystem` 增 `review_stats` 段。
- 新增 `run_ecosystem_review2_smoke.py`（13/13 PASS）、`run_ecosystem_d96_report.py`（10/10，产出 `lda/reports/ecosystem_d96.json`）；D-93/D-94/D-95 smoke 回归全绿。

### 新增/变更（post-v0.6 · D-97 生态共建进一步 · 评审门槛再扩展 + 多提案批量评审 · 2026-08-24）
- **可配置评审策略（`lda_pdk/submit.py`：`ReviewPolicy` + `get_policy` + `policy_info`）**：
  - 提交期预检：`enforce_positive_tol`（tol>0）/ `enforce_nonempty_params`（default_params 非空）/ value_min>value_max 即拒 / `enforce_value_bounds`（强制声明值界，策略开）。
  - 评审期门槛：`authorized_reviewers`（评审人白名单，空=任意具名；非空=白名单制）/ `min_source_length`（ORACLE 源码最短长度，防空壳）。
  - `strict_dedup`：严格防重（公式 token 集比较，"n_g·L"≡"n_g*L"）；`min_quorum`：core 双评审基准数可配（默认 2）。
  - 默认策略 = D-95/D-96 行为不变（全部既有 smoke 回归全绿证明）；env `LDA_REVIEW_*` 可调。
- **多提案批量评审/落地（`lda_pdk/review.py`）**：`review_proposals_batch(entries)`（逐条复用同一确定性门禁 + results/summary）、`land_proposals_batch(ids)`（批量落地，仅 approved）。
- **WebUI 面板 55 增强**：提案表加复选框多选 + 表头全选/清空 + "批量拒绝选中"/"批量落地选中"（结果表格渲染）+ 评审策略显示条；后端新增 `POST /api/ecosystem/review_batch|land_batch`，`GET /api/ecosystem` 增 `review_policy` 段。
- **实测**：批量拒绝 2/2、批量批准 2/2、批量落地 2/2（落地值 4.0，harness 自动 18→**20 题 20/20 PASS**）。
- 新增 `run_ecosystem_review3_smoke.py`（14/14 PASS）、`run_ecosystem_d97_report.py`（10/10，产出 `lda/reports/ecosystem_d97.json`）；D-93~D-96 smoke 回归全绿。

### 新增/变更（post-v0.6 · D-98 生态共建收官 · 评审流端到端发布 · 2026-08-24）
- **发布模块（`lda_pdk/publish.py`）**：评审流端到端最后一环，landed ORACLE 固化为**正式版本控制补丁 + Release Notes 草稿**：
  - `publish_proposal`：仅 landed 可发布；**须具名发布人**（git 提交是维护者动作）；确定性重编译 ORACLE 自测（死标量门禁）；difflib 生成 golden.py / benchmarks.py 的**可 `git apply` unified diff**（EOF 追加：ORACLE 函数 + `_GOLDEN_DISPATCH`/`_PHYSICAL_LAW` 注册 + `BENCHMARK_DEFS` 条目 + ORDER）；写 `reports/patches/{bid}.publish.patch` + `{bid}.RELEASE.md`（gitignore）；状态 landed→published；审计追加 `publish`；landed 记录补 published_at/published_by/patch_path/release_path。
  - `list_published`：已发布记录。
- **WebUI 升级至五十六面板**：新增面板 56「评审流端到端 · 发布」（状态机概览 pending→approved→landed→published + 可发布（landed 未发布）列表+发布表单（author/note）+ 已发布基准列表），后端新增 `POST /api/ecosystem/publish`，`GET /api/ecosystem` 增 `published`/`published_count`/`publish_pending` 段、`proposal_status` 加 published。
- **完整生命周期落地**：提案 → 具名人工评审 → 确定性自测 → 落地（自动纳入统一回归）→ 发布（补丁+Release Notes 草稿）→ 维护者 git 合并。
- 新增 `run_ecosystem_publish_smoke.py`（12/12 PASS）、`run_ecosystem_d98_report.py`（10/10，产出 `lda/reports/ecosystem_d98.json`）；D-93~D-97 smoke 回归全绿。

### 新增/变更（post-v0.6 · D-62 实证大数据锚 · 发动期联动框架落地 · 2026-08-24）
- **实证锚 = 验证的第二道非 AI ground**（与物理定律锚并列，对抗"纯 AI 互证循环论证"）：
  - **harness 实证锚题 E1-E3**（`benchmarks.py`）：BENCHMARK_DEFS 新增 E1（SOI neff）/E2（SiN neff）/E3（环形 FSR），oracle=empirical-measurement、`anchor="empirical"`、`empirical_id` 指向语料库、golden_fn=None（golden 来自实测语料而非解析函数）；BENCHMARK_DEFS 18→**21 题**。
  - **验证路径实证锚分支**（`harness.py` `VerificationHarness.__init__/resolve_specs/run` + `verification_adapters.build_harness_specs`）：实证锚题 golden 经 `EmpiricalAnchor.resolve(empirical_id)` 从语料库实时取（seed_empirical.json + 社区落库增量 `empirical_contributions.json`）；无 anchor 时**诚实降级不判 PASS**（empirical-missing）；比对=|candidate−measured|≤tol（死标量），LLM 永不进判决路径。
  - **语料评审流**（`lda_pdk/empirical.py`）：`submit_measurement`（确定性校验：id/device/metric 必填、measured_value 有限、σ≥0、**citation 必填=可追溯来源（无引用不予收录）**、防重）→ `review_measurement`（具名人工评审，LLM 不进判决路径）→ `land_measurement`（写 `empirical_contributions.json`（gitignore）+ reload 进语料库——harness E 题实时生效）；`list_measurements`/`measurement_stats`/`list_landed_measurements`。
- **WebUI 升级至五十七面板**：面板 57「实证大数据锚」（语料库统计+逐条溯源（fab/citation/σ/provenance）+ harness E 题 golden 来源 + 判题演示（候选值→死标量判定）+ 语料提交流（提交→评审→落库 UI））；后端 `GET /api/empirical` + `POST /api/ecosystem/measurement`（action=submit|review|land）。
- **实测**：E1-E3 golden=2.63/1.53/9.15（来自 seed 语料）；参考候选 **21/21 PASS**（B18 物理定律 + E3 实证锚双 ground）；扰动 10% 实证锚题全部 FAIL 检测；语料 提交→评审→落地→reload 生效；WebUI 全链 200；`run_webui_api_smoke.py` 处理 measurement 端点（空载荷 400 是正确行为，静态验证）。
- 新增 `run_empirical_anchor_smoke.py`（**17/17** PASS，已纳入 CI core 门禁 CORE_SMOKES 32 条）、`run_empirical_d62_report.py`（6/6，产出 `lda/reports/empirical_d62.json`）；D-93 smoke 回归全绿（n>=18 兼容 21 题）。
- **诚实边界**：种子语料为公开文献/PDK 量级（fab_source+citation 可追溯）；真实晶圆厂 NDA 流片实测属发动期联动，经「具名人工评审 → 落库」流持续流入（管道先建好）；落库(live) ≠ 进版本控制，权威语料以维护者 git 提交为准。

### 维护（v0.6.1 · D-99 生态共建收官维护 · 2026-08-24）
- **生态共建（D-93~D-98）收官基线**：「提交→评审→落地→发布」全链闭环，五十六面板。
- **CI core 门禁覆盖生态链**：`run_ci_regression.py` `CORE_SMOKES` 新增三 smoke——`run_ecosystem_smoke.py`（harness B1-B18 + 主权 A/B/C + Registry 自检）/ `run_ecosystem_submit_smoke.py`（提交入口）/ `run_ecosystem_publish_smoke.py`（评审→落地→发布全链）；CI 门禁（`--tag core`）从此覆盖共建链；文件头陈旧 "B1-B13"→"B1-B18"。
- **模块文档同步**：`lda_pdk/__init__.py` docstring 补齐 D-96/D-97/D-98（门槛扩展/ReviewPolicy 策略/批量评审/端到端发布）。
- **一致性审计**：面板 56 = README 五十六面板 ✓；README 无陈旧当前态计数（历史记录保留）✓。
- 新增维护回归报告 `lda/reports/ci_regression_core_v061.json`（CI core 全量，含生态链）。
- **维护回归结果：30 PASS / 0 SKIP / 0 FAIL（281.43s）全绿**。🔴 环境结论：managed base python（3.13.12）缺 `scipy`/`jsonschema`，core 集 11 项旧 smoke 因此瞬时 FAIL——非代码回归；以装齐依赖的 venv（`~/.workbuddy/binaries/python/envs/default`，scipy 1.17.1 + jsonschema 4.26.0）运行即全绿。CI/本机跑 core 集须确保 scipy+jsonschema 可用。

### 维护（v0.6.2 · D-101 持续维护 · all 集全量回归 + 环境固化 · 2026-08-24）
- **all 集全量回归（最强维护门禁）**：`run_ci_regression.py --tag all`（venv python）覆盖 **70 项 smoke**（D-01~D-98 全部资产，含重 FDTD/3D adjoint/hybrid 逆设计/sparams 3D/splitter_readout 203s 等）——**70 PASS / 0 SKIP / 0 FAIL，1602.72s 全绿**；报告 `lda/reports/ci_regression_all_v062.json`；派生报告（design_packages 等）随维护基线刷新。
- **环境固化（防 D-99 事故重演）**：新增 `requirements.txt`——必装 `numpy/scipy/jsonschema`（CI core 门禁所需）+ 可选 `numba/torch/matplotlib/pandas/networkx/tqdm`（缺失优雅降级或 SKIP），并注明 D-99 血泪教训。
- **一致性微修**：README 模块列表补 `lda_pdk/ 生态共建（L2 Registry + 主权 A/B/C + 社区提交→评审→落地→发布 全链）`；README CLI 示例/面板计数核验一致（⑩ 18 标准题 / ⑫ 五十六面板）。
- **持续维护结论**：v0.6.1+ 全项目（70 smoke + core 30）在标准 venv 环境零失败；生态共建链（D-93~D-98）六 smoke 全部纳入回归门禁。
- **维护发现（运行残留物）**：`run_ci_industrial_smoke.py` 故意创建的坏 smoke（`run_zz_bad_smoke.py`）因沙箱"回收站不可用"未能安全删除而残留——已清理；该文件为诊断产物，不进版本控制。

### 维护（v0.6.3 · D-102 持续维护 · WebUI 路由层门禁 + 一致性深审 · 2026-08-24）
- **WebUI API 路由层冒烟（新门禁，此前未覆盖路由层）**：新增 `run_webui_api_smoke.py`——静态提取 app.py 全部 64 条 /api 路由（GET 4 + POST 60）→ 启动 WebUI 子进程 → **实跑快路径 13 条**（4 GET 全绿 + /api/ecosystem/* 9 条提交/评审类 POST 200 JSON）+ **静态验证重计算端点 51 条**（adjoint/hybrid/inverse/sparams 等，内核由各专用 smoke 覆盖）；已纳入 `CORE_SMOKES`（CI core 门禁覆盖路由层）。
- 🔴 **血泪教训（挂起根因）**：初版对全部 60 个 POST 端点发空载荷 `{}` → 重计算端点（/api/adjoint_design、/api/hybrid_design 等）会**触发真实优化（数分钟/端）** → 冒烟无限挂起（timeout 124 确认）。修复：重计算端点不实跑、仅静态验证存在（其内核已有专用 smoke）。
- **一致性深审**：README "自动发现 63 smoke" → **70 smoke**（陈旧计数修正）；run_ci_regression 文件头 "60+ 个" → "70 个"；**harness 键集一致性核验**（`golden._GOLDEN_DISPATCH` 18 == `benchmarks.BENCHMARK_DEFS` 18，B5-B7 为 ORACLE 项属正确设计）；/api 端点 docstring 与代码路由核对。
- **维护结论**：v0.6.2+ 在标准 venv 环境全绿；路由层新增 64 端点门禁；README/规划/CHANGELOG 计数一致。

### 维护（v0.6.4 · D-103 持续维护 · WebUI 字段一致性门禁 + 深审固化 · 2026-08-24）
- **前端字段一致性深审（D-102 路由层之上补字段级）**：交叉核对「面板 JS 访问字段 ↔ 后端真实返回」——①端点层：36 个 JS 调用全部有后端路由（零缺失）；②GET /api/ecosystem：生态面板（53-56）函数访问的段字段 + 嵌套对象（review_stats/proposal_status/review_policy）**逐路径运行时解析零缺失**；③POST 四端点（import/review/land/publish）响应字段与前端访问全对齐（import 的 results/summary 为 app.py 包装键、review 的 votes 在 core quorum 分支、publish 的 diff_lines/patch_path/release_path 均确认存在）。
- **深审方法固化为 CI 门禁**：`run_webui_api_smoke.py` 新增 **31 条生态字段存在性断言**（`ECOSYSTEM_REQUIRED_FIELDS`：harness.total/passed、sovereign.A/B/C.count、review_stats 4 键、proposal_status 5 态、review_policy 7 键、published/publish_pending 等前端渲染硬依赖）——字段被删除/改名即 FAIL；实跑 PASS 13→**44**、静态 51、FAIL=0（秒级）。
- 🔴 **深审排除的误报源（记录）**：`c.detail/c.name/c.ok` 是 `['A','B','C'].map(c=>...)` 循环变量、`a.op/a.ts` 是 audit 循环变量、`d.status/d.value` 等是 POST 端点各自响应对象——均非 GET /api/ecosystem 缺失，逐项人工核实排除。
- **维护回归：CI core 31 PASS / 0 SKIP / 0 FAIL（279.56s）全绿**，报告 `ci_regression_core_v064.json`。
- **维护结论**：v0.6.3+ 全绿；WebUI 字段漂移现可被 CI 捕获（删除/改名即 FAIL）。

### 维护（v0.6.7 · D-105 持续维护 · L1 协议层全链路门禁 + 环境一致性 · 2026-08-25）
- **未覆盖模块盘点（D-104 之后的深审）**：发现 `run_agent.py`（L1 agent 协议层 CLI 演示，白皮书 §12「人操作壳 → agent 操作接口」翻译层最小可跑实证）的 KernelGateway 全链路路径**无 smoke 覆盖**——run_mcp_smoke 只覆盖 MCP 工具路径（verify_design/list_benchmarks），CLI 路径（L0 IR 驱动 + 三种 candidate + benchmarks 过滤）此前零门禁。
- **新门禁（实质增量）**：新增 `run_l1_agent_smoke.py`（6/6 PASS，库方式走同一 KernelGateway）——①reference 21/21（B1-B18 + E1-E3 双 ground，实证锚注入生效）；②perturbed(rel=0.10) 6/21 抓 FAIL；③l3_ai 18/21 法官抓 FAIL（LLM 候选被死标量驳回）；④list_benchmarks 21 题；⑤benchmarks 过滤 B1,B2,B4 → 3/3；⑥L0 IR 驱动（l0_demo_ring.json）→ 2/2。**纳入 CORE_SMOKES（33→34 条）**。
- **环境一致性核验**：requirements.txt 必装 3 包（numpy/scipy/jsonschema）与 venv 全齐（numpy 2.4.6 / scipy 1.17.1 / jsonschema 4.26.0）；可选包（numba/torch/matplotlib/pandas/networkx/tqdm）注释标注完整，venv 安装状态与语义一致。
- **残留扫描**：无未跟踪诊断残留（zz/bad/tmp/diag 类归零）。
- **维护回归：CI core 34 PASS / 0 SKIP / 0 FAIL**，报告 `ci_regression_core_v067.json`。
- **维护结论**：v0.6.6+ 全绿；L1 协议层（MCP + CLI 双路径）现受 core 门禁双覆盖。

### 维护（v0.6.6 · D-104 持续维护 · D-62 收官后全量回归 + 一致性深审 · 2026-08-25）
- **D-62 收官后 all 集全量回归（最强门禁）**：`run_ci_regression.py --tag all`（标准 venv）覆盖 **72 项 smoke**（D-01~D-103 全部资产 + WebUI 路由层 + 实证锚）→ **72 PASS / 0 SKIP / 0 FAIL**，报告 `ci_regression_all_v066.json`——实证锚收官后全项目零回归。
- **一致性深审（实证锚键集核验）**：`golden._GOLDEN_DISPATCH` 18 ⊂ `BENCHMARK_DEFS` 21（E1-E3 设计上不走 dispatch）；E 题三条消费路径全部正确——①`VerificationHarness` 有 anchor 时 21/21 PASS、无 anchor 时诚实降级（`empirical-missing` 不判 PASS）；②`verification_adapters.build_harness_specs` 实证锚走 `EmpiricalAnchor.resolve`（seed + 社区增量）；③`lda_ir/bridge.py` 对 E 题 `golden_with_source` 的 KeyError 有 try-except 兜底（error 行不崩溃）。**无路径可误触发**。
- **修复（D-62 适配 · 实质增量）**：`lda_l1/protocol.py` `KernelGateway.__init__` 注入实证锚（`_load_empirical_anchor`：seed + 社区增量）——L1 agent 验证链路默认携带第二道非 AI ground，`verify_design` reference 恢复 **21/21 PASS**（此前无 anchor → E 题诚实降级 18/21）；🔴 根因：D-62 新增 E1-E3 后 MCP smoke 断言未同步，且 `run_mcp_smoke.py` 不在 CORE_SMOKES（L1 协议层未被 core 门禁覆盖）→ all 集才捕获。**门禁改进**：`run_mcp_smoke.py` 纳入 CORE_SMOKES（33 条），L1 协议层此后受 core 门禁保护。
- **计数修复**：`_discover_all` 实际 72 项 → README「自动发现 70 smoke」→72、`run_ci_regression` 头部「70 个」→「72 个」（D-62 新增 `run_empirical_anchor_smoke.py` 后未同步）；README 当前态陈旧引用修复（模块列表/⑩ 章节 18→21 题、⑫ 章节五十六→五十七面板）。
- **任务台账清理**：16 项历史遗留任务（D-74~D-86 期间实际已交付但状态滞留的 in_progress/pending）标记 completed——台账与 D-01~D-103 全部收官事实对齐。
- **维护结论**：v0.6.5（实证锚收官）后全项目在标准 venv 环境零失败；72 项 smoke 全量门禁为最强基线。

### 新增/变更（post-v0.5 · D-84~D-89 全量 · 详见下方 v0.5 详细记录）

## v0.5（2026-08-23 · git tag v0.5 · 系统级里程碑）

**里程碑：M7 收口 + 护城河两件 + Track A 逆设计纵深四阶——"设计目标 → 已验证器件/系统/标准/逆设计"完整开源基线**

### 核心能力（D-73~D-82，详见 `LDA_v0.5_Release_Notes.md`）

- **M7 系统级三件**：D-73 热光可调 WDM（Δλ/λ=(dn/dT)·R_th·P/n_eff 物理定律锚 + 信道重分配验收）；D-74 量子门/纠错拓扑（11 门全幺正 + {H,T,CNOT} 通用 + surface code k=1 + CR 门）；D-75 大规模系统基准（8 WDM×8 qubit 联合压测 + 容量自洽 8=8 + IL 预算 7.3% + qubit 间隔余量 2.5× + 网格分辨率 0.59%≤1%，总压测 0.056s）。
- **护城河两件**：D-76 L0 IR 开放标准 v0.3（ir_spec + JSON Schema draft-07 + 零漂移校验，修复 dsl.py physics 序列化丢锚）；D-77 验证合约工业化（run_ci_regression.py 统一回归 core 27 PASS/0 FAIL + run_perf_bench.py 性能基准 greens 48.9× + 基线漂移监控 + CI job）。
- **Track A 逆设计纵深四阶**：D-80 谱形目标（split_ratio 分束比 0.574 / spectrum 11.7× / mode_match 8.6×）；D-81 形状逆设计 + 多目标（宽度曲线控制点 + 可制造性内建 DRC + Pareto 前端，imp 6.6×/多目标 5.6×）；D-82 形状+拓扑混合（概率 OR 光滑组合，混合 imp 18.3× vs 纯形状 6.0×，增益 3.06×）。
- WebUI 四十三面板（新增 ㊳~㊸ 六面板）；harness 13 题全过；CI 全量回归全绿；三端 tree 零差异（363/363）。

### 新增/变更（post-v0.4 · D-73~D-82 全量 · 详见下方 v0.5 详细记录）

## v0.2（2026-08-21 · git tag v0.2）

**里程碑：设计→验证闭环引擎 + 统一设计包规范——LDA 从"组件集"成为"可用系统"**

### 核心能力（D-36~D-48，全部实测全绿 + WebUI 二十二面板）

- **D-36 设计→验证闭环引擎**：给定设计目标 → 物理定律 ORACLE 瞬时搜索 → top-K 真实求解器双重验证（解析契约 + 严格数值物理自洽，纯 numpy 零 GPU）→ 返回被验证过的最优设计。4 器件全覆盖（WG/Bragg/Transmon/Ring）。
- **D-37 环形 add-drop 完整产品链路**：目标 FSR → 半径反解 → 双 bus 版图（GDSII/SVG，自写零依赖编码器）→ DRC → bus 真实 FDTD → 耦合/损耗预算 → 可制造设计包。
- **D-38 agent 逆设计通用框架**：声明式注册表，同一框架落地 4 器件（Ring/Bragg/Transmon/AddDrop，跨 match/threshold、连续/离散、光子/量子）；新器件 = 注册一条 spec 零框架改动。
- **D-39 量子域补强**：Resonator（λ/4 闭式↔离散 TL 严格本征值，rel=0.25%）+ Coupler（解析 J↔441 维严格对角化，rel=4.15%）双验证——量子域三器件全带一等真实物理验证入口。
- **D-40 统一 IR 深化**：PhysicsAnchor 一等字段 + schema 受控升级 v0.3（0.2 向后兼容）；harness 新增 B12/B13 量子锚（**13 题 B1-B13**）。
- **D-41 量子 agent 逆设计闭环**：目标 f01/f0/J → IR → 闭式物理反解 → D-39 严格数值双验证 PASS（与光子栈对称）。
- **D-42 WDM 多环级联系统**：IR 网表驱动 N 环分波，级联传递 + 系统验收（IL≤3dB/XT≥15dB/单 FSR 防混叠）；超规格设计正确拒绝。
- **D-43 光子-量子混合链路**：芯片级 dispersive readout（Transmon↔readout↔feedline），JC 精确对角化 ↔ 色散 χ 交叉验证（共振分裂=2g 自洽）。
- **D-44 统一设计包规范**：DesignPackage schema v0.1（ir+design+verification+artifacts+honest_notes，verification.passed 唯一验收门）+ 正式 spec 文档 + JSON Schema（draft-07，全部 kind conforms）。
- **D-45 WDM 纵深（指标驱动）**：XT 指标反解 gap（bisection）、级联插损预算表、单 FSR 信道上限。
- **D-46 N-qubit 频率复用读出**：N qubit 沿公共力线错开读出频率（间隔≥3×κ_r），hanger 级联透射 + dip 可分辨判据（中点 T>0.5）；光子-量子混合系统级。
- **D-47 单发读出保真度预算**：相位积分 SNR 模型 + T1 弛豫污染 + 最优读出时间 t_m* 扫描 + 非破坏性约束（n̄≤100）；F1≥0.95 独立门槛。
- **D-48 正式发布准备**：README v0.2 发布版（架构分层图 + 能力阶梯表 + 面板清单）+ CHANGELOG + git tag v0.2（GitHub/Gitee 三端同步）。

### 新增/变更

- `lda_design/`（设计引擎 + 设计包规范）、`lda_ir/`（统一 IR）、`lda_webui/`（零依赖 WebUI 二十二面板）
- `lda_agent/`：design_engine 派生的 ring_adddrop / inverse_design / quantum_design / wdm_system / qubit_readout_chain / multiqubit_readout / readout_fidelity / multiqubit_fidelity / mixed_system
- harness 基准题 11 → **13**（B12 λ/4 f0、B13 耦合 J）
- 文档：`docs/design_package_spec.md` + `docs/design_package_schema.json`

### 兼容性

- IR schema 0.2 → 0.3（受控升级，0.2 遗留模型仍可校验）

## v0.3（2026-08-21 · git tag v0.3）

**里程碑：求解器 GPU 激活 + 量子读出最终形态 + 混合巨型系统 + 方向耦合器/耦合器×WDM 闭环（D-49~D-57）**

- **D-49 设计包 spec/schema 扩展至 6 kind**：正式文档与代码注册表零漂移（§4 注册表/§7 artifacts/§9 校验枚举/变更记录 + JSON Schema enum 同步）。
- **D-50 fdtd3d GPU 实跑激活（L2-B 第三步验收 PASS）**：RTX 5060 Ti 实测——cuda 物理定律锚 selfcheck 4 例 PASS、**cuda↔cpu fp64 互证 5 例 bit-equivalent（max_rel=0.00e+00）**、greens N=120 cuda 19.43s；诚实说明消费卡 fp64 阉割（GPU 收益在显存容量，算力优先 numba-cpu 43.1×）。
- **D-51 N-qubit 复用读出逐 qubit 保真度**：D-46×D-47 集成——逐 qubit T1/n̄ 独立预算（t_m*/SNR/F），坏 qubit 独立 FAIL 不影响他者；设计包 7 kind。
- **D-52 多环 WDM × 量子读出混合巨型系统**：光子 WDM 分波（D-42）+ 量子读出（D-51）**同一 IR 网表**（10 器件+8 网表）——信道↔qubit 1:1 映射 + 系统联合验收；诚实标注光↔微波物理独立（桥接为接口规划）；设计包 **8 kind**。
- **D-53 README/CHANGELOG 更新**：能力阶梯表 13 行、二十四面板、8 kind 清单、快速开始 9 步——对外基线文档零漂移。
- **D-55 方向耦合器设计闭环**：目标分束比 → **2D FDTD 双点标定 κ**（秒级真实求解器）→ CMT 反解 L（物理长度=有效长度+offset）→ 实测-修正迭代收敛（50:50 命中 cross=0.503）；设计包 **9 kind**。
- **D-57 耦合器 × WDM 组合**：**FDTD 标定 PDK 文件**驱动 WDM 环耦合段 gap 选择——κ_c(gap) 5 点高分辨率实测沉淀为标定文件（一次性后台 ~20 分钟，设计时秒级），k_ring=sin(κ_c·L_couple) 换算后 gap 扫描设计；**诚实发现：k_ring=0.107 vs 解析假设 0.488（比值 0.218，解析偏乐观 4.6 倍）**；设计包 **10 kind**。

### 新增/变更（v0.3）

- `lda_agent/`：multiqubit_fidelity / mixed_system / directional_coupler / wdm_coupler + `data/kappa_calibration.json`（PDK 标定文件）
- `docs/design_package_spec.md` + `design_package_schema.json`：kind 6 → **10**
- WebUI：二十二 → **二十六**面板（㉓ 逐 qubit 保真度 / ㉔ 混合巨型系统 / ㉕ 方向耦合器设计闭环 / ㉖ 耦合器×WDM 组合）
- README：能力阶梯表 D-36~D-57、二十六面板、10 kind、快速开始 11 步
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 10 项枚举）

## v0.3.1（2026-08-22 · git tag v0.3.1）

**里程碑：PDK 标定库最终形态——κ_c(gap,λ) 全网格直接查表，无需任何解析假设（D-58~D-60）**

- **D-58 README/CHANGELOG 更新至 D-57**：能力阶梯表 15 行、二十六面板、10 kind、快速开始 11 步——对外基线文档零漂移。
- **D-59 波长相关标定库（κ_c(gap,λ) 二维）**：新增 `data/kappa_wavelength_calibration.json`（3 点 κ_c(λ)，gap=0.3 基线，FDTD 双点标定）；`wdm_coupler` 新增 `wavelength_calibrated` 模式——分离变量近似 κ_c(gap,λ)≈κ_c_gap(gap)·[κ_c_wl(λ)/κ_c_wl(1.55)]（诚实标注）→ 每信道按 λ 独立 k_ring → 最弱耦合保守验收 + 波长单调检查；实测 κ_c(λ)=0.0213/0.0241/0.0270（1.50/1.55/1.60，**单调增幅 ~27% 物理正确**）。
- **D-60 κ_c(gap,λ) 全网格标定库（最终形态）**：新增 `calibrate_kappa_grid.py`（9 点 gap×λ 全网格标定脚本，后台 ~81s）+ `data/kappa_grid_calibration.json`（二维网格，9 点全非缠绕）；`wdm_coupler` 新增 `grid_calibrated` 模式——**双线性插值直接查表**（替代分离变量近似，无需任何解析假设）→ 每信道独立 k_ring → 最弱耦合保守验收（优先级 grid > wavelength > gap 一维）；实测 3 信道每信道 k_ring=[0.10755/0.10833/0.1091] 单调、WDM 5/5 IL≤0.32dB/XT≥43.4dB，负例（弱耦合/超 FSR/标定缺失）正确 FAIL。

### 新增/变更（v0.3.1）

- `lda_agent/`：calibrate_kappa_grid.py（全网格标定脚本）+ `data/kappa_wavelength_calibration.json` + `data/kappa_grid_calibration.json`（PDK 标定库三文件齐备）
- `wdm_coupler`：wavelength_calibrated / grid_calibrated 两种标定模式（CLI `--wavelength` / `--grid`，API 同参）
- WebUI：二十六面板（㉖ 扩展：gap/波长/全网格三模式）
- README：能力阶梯表 D-36~D-60、新增「PDK 标定库」章节、快速开始 11 步（⑧ 升级 --grid 全网格模式）
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 10 项枚举，延续）

## v0.3.2（2026-08-22 · git tag v0.3.2）

**里程碑：方向耦合器 × 量子读出——光子分束网络供电量子读出控制线（D-63）**

- **D-63 方向耦合器 × 量子读出（新 kind=splitter_readout）**：新增 `lda_agent/splitter_readout.py`——**二叉树级联 DC 分束网络**（权重二分递归建树，每级 target_cross=右子树权重/节点权重，每级 D-55 `design_coupler` **真实 2D FDTD 设计闭环**，级联功率=路径 FDTD 实测分束比之积）→ **readout_power_budget**（每 qubit 有效 n̄=nbar0×p_actual，P∝n̄、SNR∝√n̄，D-47 复用）→ **统一 IR 网表**（power+DC×m+Transmon×N+Resonator×N+objectives）→ 联合验收（分束命中 Δ≤0.05/SNR≥3.0/F≥0.98/IR/诚实标注光↔微波拓扑同构、物理独立）。实测 3 qubit：2 级 DC（dc1 1/3→FDTD 0.337、dc2 1/2→FDTD 0.502）→ 功率分配 [0.330/0.333/0.337]（Δ≤0.0034）→ SNR∈[3.95,3.99] F∈[0.9996]；4 qubit 3 级 DC PASS；负例（极端权重/低 nbar0/长度不匹配）正确 FAIL；**设计包 11 kind**。

### 新增/变更（v0.3.2）

- `lda_agent/`：splitter_readout.py（方向耦合器 × 量子读出联合设计）
- `lda_design` + spec/schema：kind 10 → **11**（加 `splitter_readout`，spec §4 注册表 / §9 枚举 / 变更记录 0.1.6 同步）
- WebUI：二十六 → **二十七面板**（㉗ 方向耦合器×量子读出：DC 网络 / 功率分配 / 每 qubit 预算，首屏自动演示纳入）
- API：`/api/splitter_readout`（nbar0/delta/g/kappa_r/T1_us/eta/N_amp/weights 全透传）
- README：能力阶梯表加 D-63 行、二十七面板、11 kind、快速开始 12 步（新增 ⑨ splitter_readout）
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 11 项枚举）

## v0.4（2026-08-23 · git tag v0.4）

**里程碑（真实化里程碑 · M4/M5/M6 三里程碑达成）：PDK 标定库分辨率修正（D-68）+ 伴随法梯度拓扑逆设计（D-69）+ 逆设计接入 D-36 引擎（D-70，M4）+ 真实版图基元库（D-71）+ 真实 2D/3D FDTD 端口 S 参数验收（D-72，M5）+ 光栅耦合器端口验收（D-78，光栅方程 ORACLE）+ 真实基元接入设计流水线（D-79，M6 · v0.4 门槛达成 · Track B 收口）**

- **D-66 标定库 × 分束网络**：`splitter_readout_cal` 模式——DC gap 由 κ_c(gap) 标定库驱动设计（标定 5/5 PASS）。
- **D-67 分束网络 × WDM（新 kind=wdm_splitter 流程）**：`lda_agent/wdm_splitter.py`——WDM 多环级联解复用（D-42 + D-57 标定库驱动 gap）→ 每信道 drop 口接二叉树级联 DC 分束树（D-63 复用，每级 D-55 真实 2D FDTD 设计）→ 信道输入 = drop 扣除实测 IL 的剩余功率（10^(-IL/10) 诚实标注）→ 统一 IR 网表（Ring×N + DC×M）+ 联合验收。纯光子域，无跨物理域声称。
- **D-68 PDK 标定库 4×5 升级**：诊断性 5×5 dl40 标定发现原 3×3（dl20）中 gap 0.25/0.30 的 κ_c 完全相同（分辨率假象）→ 生产库升级为干净 4×5 网格（gaps 0.25/0.30/0.35/0.40 × 5 波长 = 20 点，dl40，κ_c 沿 gap 与 λ 双轴单调，双线性插值查表）；`calibrate_kappa_grid.py` 参数化（--gaps/--wls/--dl_factor/--out）成复用基础设施。
- **D-69 伴随法梯度逆设计核（adjoint FDTD，M4 Track A）**：`lda_solver/adjoint_fdtd.py` + `lda_agent/adjoint_design.py`——对主权 2D FDTD（TEz，Yee + 海绵 PML，零额外依赖）实现 **adjoint 灵敏度**（FDTD 更新算子**显式转置**，数值 Mᵀ 逐元素对拍 ~1e-15），从"参数扫描 + 闭式反解"升级为**梯度驱动拓扑逆设计**。工程决策（诚实记录）：CW 源 + P_out 目标无上界（高 Q 谐振腔蓄能病态）→ **高斯脉冲源 + 窄孔径收集场能 FOM**（能量有界，adjoint 观测 obs=2·Ez 无 DFT/共轭陷阱）；优化器 = 密度投影（beta 延拓 2→14 二值化）+ **回溯线搜索**（FOM 单调不降）。M4 双标准实测：①adjoint vs 中心有限差分对拍 max_rel_err=**0.0**（≤0.15）②一例拓扑逆设计 improvement=**15.1×**（≥1.5，110×90 网格 3996 体素，FOM 36.2→548）。FOM 语义诚实标注：收集场能（聚焦增益可致 T>1），非功率透射。
- **D-70 逆设计目标泛化接入 D-36 引擎（method=adjoint，M4 Track A 收口）**：`lda_agent/design_loop.py` 的 `DesignAgent` 统一入口按 **method** 分流——默认 `scan`（布拉格参数扫描，原路径零改动）+ `adjoint`（伴随梯度拓扑逆设计）；`l1_protocol.DesignTarget` 新增 `method` 字段透传意图。目标从"布拉格周期数"泛化为**「把指定孔径内的收集场能最大化」**（设计区/孔径/材料对比度/波长/分辨率全部由意图 extra 透传 `AdjointProblem`）。闭环 = 均匀平板初值 → FD 对拍锚（adjoint vs 中心有限差分 max_rel_err≤0.15）→ 密度投影 + 回溯线搜索梯度优化（improvement≥1.5）→ 死标量验收，输出 `DesignOutcomeReport` 兼容格式（target/accepted/iterations/loop_trace/verdict，final_oracle_metric=均匀平板初值基线，诚实标注）。M4 双标准实测：smoke 4/4（正例 improvement=15.13× + 空设计区 FAIL + 0 迭代 FAIL + 布拉格兼容）、全参报告 improvement=**15.13×**（FOM 36.2→547.9，FD 对拍 err=2.4e-5）。LLM 不进判决路径。
- **D-71 真实版图基元库（Track B 起步，foundry-ready）**：`lda_l2/primitives.py`（纯几何核心，零依赖）——①**Taper**（线性/绝热余弦轮廓，两端斜率 0 减模式失配）②**Euler 弯**（clothoid：曲率 0→1/R→0 连续无折角，90°/180°/45° 终点角误差 &lt;0.01°）③**MMI 1×2 对称分束**（输入 taper + 多模干涉区 + 双输出 taper，7 元素）④**光栅耦合器**（周期部分刻蚀齿，齿宽=Λ·duty，22 元素）。注册进 `gds_export.geometry_desc`（GDS/SVG/DRC 单一来源）+ `drc.drc_check_device`（min_width/min_space/min_bend_R）。`lda_agent/primitives_design.py` 封装：GDS 编码（round-trip 回读一致）+ DRC 自查 + SVG 预览 + 死标量验收（smoke 3/3：4 基元全过 + 非法 kind 优雅 + min_width 违规 FAIL；报告 PASS，GDS 628B/8312B/1936B/1462B）。**诚实边界**：只交付 foundry 可接受几何；分束比/透射谱等电特性归 D-72 2D FDTD 端口 S 参数验收，不做性能声称。
- **D-72 真实 2D FDTD 端口 S 参数验收（M5 Track B 首个里程碑）**：`lda_solver/port_sparams.py` + `lda_agent/sparams_design.py`——对 D-71 真实基元（MMI 1×2 对称分束器）做**全 2D FDTD 端口透反射谱**验收：输入 CW 激励 → 输出/回波端口 DFT 收集 → 输入功率归一 → **S 参数谱**（|S11|² 回波 / |S21|² 上输出 / |S31|² 下输出，能量守恒自动满足）。死标量验收（LLM 不进判决路径）：仿真有效 + 双输出平衡度 ≤0.15 + 透射 ≥0.05（自成像对称 ORACLE 物理定律锚）+ **DRC 工艺规则从真实 SOI 180nm PDK 注入**（NOEIC/CUMEC/SITRI design_rules → rules_from_pdk，D-21 落地，3/3 全绿）。实测（W=4/L=12µm，5 波长，dl=1.55/20，1200 瞬态）：**平衡度 max=0.078**（≤0.15）、中心波长 **S11=0.094 / T=0.906**、5/5 波长全过；smoke 3/3。**关键 bug 修复（诚实记录，22:40 修订）**：①偶数 Ny 网格对称轴在 y=−dl/2 → 多模区上下栅格化差一格 → S21/S31 系统性不对称 → **Ny 取奇数根治**；②**栅格化范围公式误加 Ly 偏移 → mask 为空（core frac=0.0）**——此前验收基于空 mask 伪结果（均匀介质源扩散的"好看"数值），22:40 定位修复（j(y)=y/dl+(Ny−1)/2 无偏移）后**报告重新生成（真实 S 参数），验收仍 PASS**。教训：mask 空时 y-flip 恒对称——对称性验证必须同时断言 mask 非空。诚实边界：2D TEz 近似；分束比绝对值依赖自成像长度精确设计，不声称与商业 EDA 数值库逐点一致。
- **D-72 深化 3D 端口 S 参数验收（SOI 220nm，mmi/dc/ring）**：`lda_solver/port_sparams_3d.py` + `lda_agent/sparams_3d_design.py`——**MMI / 方向耦合器(DC) / 环形谐振器(Ring)**（SOI 220nm 波导层 + 上下包层）**全 3D FDTD** 端口透反射谱（复用已验证 numba 核 `_fdtd3d_core`，零新依赖；numba 需 `python envs/default` venv）：3D 波导截面匹配源注入（TE 主极化 Ez，矩形近似基模）→ 多端口 DFT 收集 → 输入功率归一 → S 参数谱 → 死标量验收：**MMI** 平衡度 ≤0.15、**DC** cross_frac 端点趋势（CMT 物理，cf≈0.5 恰在 sin² 拐点 π/4 处导数最大、数值噪声放大 → 端点趋势 + 容差而非逐点严格单调，诚实标注）、**Ring** drop 谐振峰检出（Lorentzian ORACLE），均 + 仿真有效 + 透射 ≥0.05；附 **2D↔3D 连续性对拍诊断**（垂直模式物理差异，非判据）。实测：MMI 平衡度 0.015-0.083、DC cf 端点上升、Ring drop 峰检出（max 0.202/med 0.140），3/3 全过；smoke 5/5（三器件 + 非法 kind + out_gap 离线）；WebUI ㉝ 面板（mmi/dc/ring 选择）。**已接入设计闭环**：`DesignAgent` 新增 `method="sparams3d"` 分支（`_run_sparams3d`）——意图解析 kind + 几何 → 3D FDTD S 谱 → 死标量验收 → `DesignOutcomeReport` 兼容输出（iterations=波长数、loop_trace 每波长 S11/S21/S31、final_metric=中心波长 T_total）；无 numba 环境优雅 FAIL。smoke 4/4（MMI/DC 闭环 + 非法 kind + 布拉格兼容）；三器件闭环报告 `reports/sparams_loop_d72.json` PASS。DesignAgent 三 method 齐备：scan / adjoint / sparams3d。**关键坑（诚实记录）**：①3D 源 profile 过宽能量泄漏 → 波导截面匹配矩形分布；②**sponge 自适应 clamp（≤Ny/4、Nz/4）**——小域 Nz≈19 时两端 sponge 重叠覆盖波导层，场被整体吸收（S11=1.0 伪全反射）→ z 包层加厚 + clamp 根治；③双向源后向波使 S11 偏高（仿真设定伪影，判据不依赖 S11）。
- **D-78 光栅耦合器端口验收（M6 v0.4 门槛起步 · 光栅方程 ORACLE）**：`lda_solver/port_sparams_gc.py` + `lda_agent/gc_design.py`——4 基元最后一块电特性验收。**几何修正（诚实记录）**：D-71 GC 原"齿区主体+齿"同层合并（GDS 合并填充语义）实心=直波导、无周期调制 → D-78 修正为真实方波光栅（齿=硅、凹槽=包层）。**2D FDTD 端口透射谱**：CW 注入 → thru/in 归一 → 透射谷检测（周期调制耦合损耗，预测窗内局部谷——谱为级联干涉梳结构，全局最小谷≠光栅方程谷）→ 谷位置 vs **光栅方程** λ_rad=Λ·n_eff 解析预测对拍（n_eff 由同宽直波导 FDTD 双监视点相位差法独立测得，**非拟合**）+ **Λ 扫描趋势锚**（dλ/dΛ=周期结构实测 n_eff）。死标量验收：**谷检出 depth≥0.10 + 谷位置 rel≤0.15 + 趋势斜率 rel≤0.10**。实测：neff=3.699、谷 λ=2.283µm vs 预测 2.515µm（**rel=0.092**）、Λ 扫描斜率 3.290 vs 周期结构 neff 3.357（**rel=0.020**）、谷深 0.996，**验收 PASS**；smoke 3/3（正例 + duty=1.0 无调制 FAIL + Lambda=0 优雅 FAIL）；报告 `reports/gc_d78.json`；WebUI ㉞ 面板 + `/api/gc_sparams`（HTTP 实测通，passed=True）。**诚实标注**：①谷位置对直波导 neff 预测系统性负偏 ~9%（凹槽微扰使周期结构平均传播常数低于直波导 neff，Λ 无关恒定比例，物理预期非 bug），趋势斜率锚定反解值不受影响；②2D 全刻蚀方波 ≠ 3D 浅刻蚀 GC 光纤耦合（无光纤模/方向性），不声称耦合效率。
- **D-79 真实基元接入设计流水线（M6 v0.4 门槛达成 · Track B 收口）**：`gds_export.geometry_desc` 默认几何从玩具矩形/圆形切换到 D-71 真实基元——**RingResonator/RingAddDrop 实心环带 BOUNDARY → 真实波导环**（中心线 PATH + width，foundry 弯曲波导标准表达，可 DRC 检查环宽）；**SymmetricYBranch 裸分叉 → 输入绝热 taper**（D-71 taper_polygon 余弦轮廓）+ 双 arm PATH；DC/Waveguide 已是 PATH 波导表达（确认沿用）；Taper/EulerBend/MMI/GratingCoupler 沿用 D-71 基元（GC=D-78 修正方波光栅）。`lda_agent/pipeline_realize.py`：全 9 kind 真实 GDS 出图 + round-trip 一致 + **3×SOI PDK DRC 复查**（NOEIC/CUMEC/SITRI design_rules 注入）+ 玩具→真实几何对比诊断。实测：9/9 kind PASS（Waveguide 100B / Ring 638B / AddDrop 680B / DC 142B / YB 702B / Taper 618B / Euler 8298B / MMI 1928B / GC 1380B，全 rt=OK drc 三厂全绿）；smoke 3/3（全 kind + 几何真实化断言 + 非法 kind 优雅 FAIL）；报告 `reports/pipeline_realize_d79.json`；WebUI ㉟ 面板 + `/api/pipeline_realize`（HTTP 实测通）。**诚实边界**：环 path 为圆弧中心线（曲率恒定），Euler 弯无缝拼合环留作深化；几何真实化不改变电特性判据（归 D-72/D-78 端口验收）。**Track B 至此收口，"设计→验证→版图"全链路真实化闭环，v0.4 门槛达成。**

### 新增/变更（v0.4）

- `lda_solver/`：adjoint_fdtd.py（主权 2D adjoint FDTD 核：脉冲前向 + 显式转置伴随 + FD 对拍验证 + 拓扑优化器）+ port_sparams.py（D-72 端口 S 参数框架：MMI eps 场构建 + CW 多端口收集 + 输入功率归一 + 自成像 ORACLE 验收）+ port_sparams_3d.py（D-72 深化：3D MMI/DC/Ring 体素场 + 3D CW 多端口收集 + kind 分支判据 + 2D↔3D 对拍诊断）+ port_sparams_gc.py（D-78：GC 方波光栅场构建 + 透射谱谷检测 + 光栅方程 ORACLE 验收 + Λ 趋势锚）
- `lda_agent/`：adjoint_design.py（D-69 设计闭环封装）+ wdm_splitter.py（D-67）+ calibrate_kappa_grid.py（D-68 参数化标定）+ design_loop.py（D-70 method=adjoint 逆设计分支）+ l1_protocol.py（DesignTarget.method 字段）+ primitives_design.py（D-71 基元库封装）+ sparams_design.py（D-72 S 参数验收封装 + PDK 规则注入 DRC）+ sparams_3d_design.py（D-72 深化 3D 验收封装）+ gc_design.py（D-78 GC 验收封装）
- `lda_l2/`：primitives.py（D-71 真实版图基元：taper/euler_bend/mmi/grating_coupler 纯几何；D-78 修正 GC 为真实方波光栅）+ gds_export.py（geometry_desc 注册 4 新 kind；D-79 升级 Ring/AddDrop/YBranch 真实基元几何）+ drc.py（drc_check_device 支持 4 新 kind）
- `data/`：kappa_grid_calibration.json 升级 4×5（20 点，dl40，双轴单调）
- WebUI：二十七 → **三十五面板**（㉘ 分束网络×WDM、㉙ 伴随法拓扑逆设计、㉚ 逆设计接入 D-36 引擎、㉛ 真实版图基元库、㉜ 端口 S 参数验收、㉝ 3D 端口 S 参数验收、㉞ 光栅耦合器端口验收、㉟ 真实基元接入设计流水线）
- API：`/api/wdm_splitter`（D-67）、`/api/adjoint_design`（D-69）、`/api/adjoint_loop`（D-70）、`/api/primitives`（D-71）、`/api/sparams`（D-72）、`/api/sparams_3d`（D-72 深化）、`/api/gc_sparams`（D-78）、`/api/pipeline_realize`（D-79，全 kind 真实 GDS + DRC）
- README：能力阶梯表加 D-66~D-79 行（含 D-72★ 3D 深化、D-78 GC 验收、D-79 流水线真实化）、三十五面板、㉘~㉟ 面板清单
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 11 项枚举，延续）

## v0.5 详细记录（D-73~D-82 · 全部实测全绿）

**里程碑（M7 第一件）：热光可调 WDM（D-73）—— 静态 WDM 升级为运行时可重构**

- **D-73 热光/电光可调 WDM（Track D 系统级 · M7）**：`lda_agent/tunable_wdm.py`——静态 WDM（D-42/D-57，FDTD 标定 κ_c 驱动 gap 多环级联解复用）叠加**每环热光相位 shifter**：**Δλ/λ=(dn/dT)·R_th·P/n_eff 物理定律锚**（dn/dT=1.86e-4/K 硅热光系数材料常数、n_eff=2.4 波导有效折射率，**非拟合**，ORACLE 比对真实 Si 加热器调谐斜率区间 [0.02,0.5] nm/mW）→ 信道重分配验证 **|P|≤P_max 且 |Δλ|≤FSR/2（无 FSR 混叠）** + 整 FSR 内可重构（P_max·S_min≥FSR_min/2）。实测：默认 3 信道 S≈0.120 nm/mW（命中真实区间）、目标 [1552.7,1555.7,1558.7]nm 各需 ~22.7mW（≤P_max=50）、最大可达位移 6.0nm≥FSR/2=4.56nm，**验收 PASS**；smoke 3/3（正例 + FSR 混叠负例 + 单信道负例）；报告 `reports/tunable_wdm_d73.json`；WebUI ㊱ 面板 + `/api/tunable_wdm`（HTTP 实测通）。**诚实边界**：①未建模环间热串扰（默认加热器热隔离）；②仅热光调谐（未实现电光载流子注入型）；③静态重配置（信道再分配）非高速调制（不声称调制带宽）；④FSR 仍由静态环半径决定，调谐仅在其内重分配。LLM 不进判决路径。

- **D-74 量子门 / 纠错拓扑（Track D 系统级 · M7 第二件）**：`lda/lda_qeda/`（gates/surface_code/cross_resonance）+ `lda/lda_agent/qeda_topology.py`——量子域从读出走向计算：①量子门库 11 门解析矩阵（I/X/Y/Z/H/S/T/CNOT/CZ/SWAP/Toffoli），幺正性 ‖U†U−I‖≤1e-12 精确 + {H,T,CNOT} 通用性（**T∉24元Clifford 群论死标量锚**）；②rotated surface code **d² 数据比特、全部稳定子对易（精确 Pauli）、GF(2) 秩验证 k=1**、阈值标度 p_L=A·(p/p_th)^((d+1)/2)；③cross-resonance 门 g_CR=2J²Δ/(α²−Δ²) 有效模型 + t_CR=π/|g_CR|≤T2（ORACLE |g_CR|∈[0.02,10]MHz、p<p_th 阈值门）。默认 d=3/p=5e-3：门库全幺正+通用、surface code 全对易 k=1、|g_CR|=0.095MHz、t_CR=33µs≤T2=100µs，**验收 PASS**；smoke 3/3（正例 + 超阈值 FAIL + CR 失效 FAIL）；报告 `lda/reports/qeda_topology_d74.json`；WebUI ㊲ 面板 + `/api/qeda_topology`。**诚实边界**：CR 为 Schrieffer-Wolff 主导阶有效模型（非 transmon 多能级数值）、σ_zz 由 echoed-CR 抵消、表面码 p_th=1% 为公认模拟常数（非本系统逐周期解码仿真）、本设计给出拓扑与资源不含 GDS 版图。LLM 不进判决路径。

- **D-75 大规模系统基准（Track D 系统级 · M7 第三件 · M7 收口）**：`lda/lda_agent/large_scale_bench.py`——把 WDM 级联（D-42/45）+ 多 qubit 读出（D-51）+ 混合巨型系统（D-52）推进到 **N≥8 大规模**并做**性能与精度边界压测**：①WDM 8 信道（间隔 1.2nm 密集 DWDM grid、gap=0.4µm 弱耦合高 XT）级联设计 + 插损预算；②8-qubit 沿公共力线频率复用读出（间隔 50MHz ≫ 3κ_r=22.5MHz）逐 qubit 保真度 + dip 可分辨；③联合 8×8 混合巨型系统（光子 WDM 信道 ↔ qubit 1:1 映射）；④边界压测：**WDM 容量自洽**（实际最大可行 N=8 == 理论 floor(FSR 9.12nm/1.2nm)+1=8，单 FSR 工作区）、**IL 级联模型余量**（N=16 时 max_total_il=0.22dB，3dB 预算的 7.3%，thru 残差累积趋势）、**qubit 间隔临界**（0.02GHz≈3κ_r=0.0225GHz 失效，默认 0.05GHz 余量 2.5×）、**标定网格分辨率**（κ_c 网格 λ 间距 25nm vs 信道间隔 1.2nm → 每信道相对变化 0.59% ≤1%）。实测：默认 8×8 全过（WDM 5/5：IL≤0.09dB XT≥24.1dB；qubit 13/13：F∈[0.9978]；联合 4/4），**总压测耗时 0.056s**（解析物理模型性能基准）；smoke 3/3（正例 8×8 + WDM 超容量 N=10 跨 FSR FAIL + qubit 过密 0.02<3κ_r FAIL）；报告 `lda/reports/large_scale_bench_d75.json`；WebUI ㊳ 面板 + `/api/large_scale_bench`（HTTP 实测 200 passed=True、负例正确 FAIL）。**诚实边界**：级联为解析物理模型（FSR 2D 有效折射率容差 30% 已知）、性能为解析模型耗时非商业级 FDTD、网格分辨率诊断基于标定库内插值相对变化（标定自身已由 D-68 dl40 验证）。LLM 不进判决路径。

### 新增/变更（post-v0.4 · D-73/D-74）

- `lda_agent/tunable_wdm.py`：热光可调 WDM 设计封装（静态 WDM 复用 design_wdm_with_coupler + 每环热模型 + 信道重分配死标量验收）
- `run_tunable_wdm_smoke.py`：3/3 smoke（正例 + FSR 混叠 FAIL + 单信道 FAIL）
- `lda_webui/app.py`：`/api/tunable_wdm`（channels/target/R_th/n_eff/P_max 透传 → 可调 WDM 验收）
- `lda_webui/static/index.html`：㊱ 面板（热模型 + 信道重分配计划表 + 死标量验收）
- README：能力阶梯表加 D-73 行、三十六面板、㊱ 面板清单
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 11 项枚举，延续）

### 新增/变更（post-v0.4 · D-74）
- `lda/lda_qeda/__init__.py`、`gates.py`、`surface_code.py`、`cross_resonance.py`：量子门库（解析矩阵+幺正性+通用性死标量锚）+ rotated surface code（全对易+GF(2)秩 k=1+阈值标度）+ cross-resonance（有效模型+退相干预算）
- `lda/lda_agent/qeda_topology.py`：量子门/纠错拓扑设计→验证封装（门库 + surface code + CR 死标量验收）
- `lda/run_qeda_topology_smoke.py`：3/3 smoke（正例 + 超阈值 FAIL + CR 失效 FAIL）
- `lda_webui/app.py`：`/api/qeda_topology`（d/p_phys/J/delta/alpha/T2 透传 → 容错拓扑验收）
- `lda_webui/static/index.html`：㊲ 面板（门库 + surface code + CR + 死标量验收）
- `lda/reports/qeda_topology_d74.json`：D-74 验收报告
- README：能力阶梯表加 D-74 行、三十七面板、㊲ 面板清单 + 目录结构加 `lda_qeda/`
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 11 项枚举，延续）

### 新增/变更（post-v0.4 · D-75）
- `lda/lda_agent/large_scale_bench.py`：大规模系统基准（run_large_scale_bench + wdm_scale_scan 容量扫描 + il_cascade_scan 级联 IL 模型 + qubit_spacing_scan 间隔临界 + kappa_grid_resolution_diag 标定网格分辨率）
- `lda/run_large_scale_smoke.py`：3/3 smoke（正例 8×8 + WDM 超容量 N=10 跨 FSR FAIL + qubit 过密 0.02<3κ_r FAIL）
- `lda_webui/app.py`：`/api/large_scale_bench`（n_wdm/n_qubit/wdm_spacing/wdm_gap/qubit_spacing 透传 → 联合压测 + 边界验收）
- `lda_webui/static/index.html`：㊳ 面板（WDM/qubit/联合概览 + 容量边界表 + IL 级联表 + qubit 间隔临界表 + 网格分辨率 + 死标量验收）
- `lda/reports/large_scale_bench_d75.json`：D-75 验收报告
- README：能力阶梯表加 D-75 行（M7 收口）、三十七→三十八面板、㊳ 面板清单 + 目录结构加 `large_scale_bench.py`
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 11 项枚举，延续）

### 新增/变更（post-v0.4 · D-76 · 护城河与标准层）
- `docs/ir_spec.md`：L0 IR 开放标准规范（LDA-STD-001 v0.3 定稿：顶层/组件/子对象模型 + 9 kind 注册表 + 物理锚语义 + 校验 7 规则 + 扩展指南 + 0.2→0.3 变更记录）
- `docs/ir_schema.json`：L0 IR 机器可读标准（JSON Schema draft-07，kind enum 9 / physics bid enum B9/B12/B13 / 0.2+0.3 schema_version / spectrum·foundry_plan 允许 null）
- `lda/lda_ir/spec_check.py`：零漂移校验（文档↔Schema↔代码：kind 注册表 / Schema 合法 / 全 kind conforms / 0.2 兼容 / physics round-trip / validate 负例）
- `lda/lda_ir/dsl.py`：**修复 physics 序列化缺陷**——`_comp_to_dict`/`_comp_from_dict` 此前 round-trip 丢 `Component.physics`（D-40 物理锚），已补齐（量子 3 kind round-trip 保留验证）
- `lda/run_ir_spec_smoke.py`：3/3 smoke（正例零漂移 + 未知 kind 被 schema 拒绝 + 缺设计意图被 validate 检出；jsonschema 校验需 venv）
- `lda_webui/app.py`：`/api/ir_spec`（零漂移校验现场跑）
- `lda_webui/static/index.html`：㊴ 面板（标准资产 + kind 注册表 + 零漂移校验表）
- `lda/reports/ir_spec_d76.json`：D-76 验收报告
- README：能力阶梯表加 D-76 行、三十八→三十九面板、㊴ 面板清单 + docs 目录补 ir_spec/ir_schema
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 11 项枚举，延续）

### 新增/变更（post-v0.4 · D-77 · 护城河与标准层第二件）
- `lda/run_ci_regression.py`：验证合约工业化全量回归统一入口——自动发现 `run_*smoke*.py`（54+）+ run_harness.py，每项独立子进程 + 超时 + 输出尾部捕获；**SKIP 语义**（退出非 0 且含"无 GPU/未安装/SKIP"标记 → SKIP 非 FAIL）；`--tag core`（CI 安全纯 numpy 集）/ `--tag all`（全量）；机器可读 JSON 报告
- `lda/run_perf_bench.py`：求解器性能基准——greens/透射谱 numpy vs numba-cpu 计时 + 加速比 + 物理一致（rel≤1e-2）+ GPU cuda↔cpu fp64 bit-equivalent（可用时）+ **历史基线漂移监控**（reports/perf_baseline.json，±30% 预警，预警=黄灯非硬判据）
- `.github/workflows/ci.yml`：新增 `industrial-regression` job（统一入口 core 集一键回归）
- `lda/run_ci_industrial_smoke.py`：3/3 smoke（回归子集全过 + 性能基准 PASS + 坏 smoke 被检出）
- `lda_webui/app.py`：`/api/ci_regression`（webui/core/all 三模式）+ `/api/perf_bench`（quick 重跑）
- `lda_webui/static/index.html`：㊵ 面板（回归结果表 + 性能基准表 + 验收）
- `lda/reports/perf_bench_d77.json` + `lda/reports/ci_regression_core_d77.json` + `lda/reports/perf_baseline.json`：基准报告与基线
- **实测**：core 回归 **27 PASS / 0 SKIP / 0 FAIL**（358s）；greens numpy→numba **34.7×**（rel=4.8e-16）；透射谱 overall 2.6×；GPU SKIP（CUDA 不可用，非失败）
- README：能力阶梯表加 D-77 行、三十九→四十面板、㊵ 面板清单 + 目录结构补 ci/perf 入口
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 11 项枚举，延续）

### 新增/变更（post-v0.4 · D-80 · Track A 深化）
- `lda/lda_solver/adjoint_fdtd.py`：**谱形目标 FOM 泛化**——AdjointProblem 增 `target_type`（field_energy/split_ratio/mode_match）+ 第二监视器（mon2）+ `target_ratio` + `mode_profile`；forward 返回 E_A/E_B/ratio/FOM_geom；compute_gradient 按目标类型生成观测（split_ratio 对数加权 FOM=a·log E_A+b·log E_B，观测线性化无 FOM 系数；mode_match 场投影 obs=2·proj/‖p‖²·p）；新增 `spectrum_optimize`（多波长加权联合，固定 dl 只变 omega——修复归一化网格陷阱）
- `lda/lda_agent/spectral_inverse_design.py`：谱形目标逆设计统一入口（FD 对拍 + 优化 + 死标量验收 + 报告）
- `lda/lda_agent/design_loop.py`：`_run_adjoint` 支持 target_type（split_ratio/spectrum 追加验收：分束比 err≤0.10、多波长加权）
- `lda/run_spectral_design_smoke.py`：3/3 smoke（split_ratio 50:50 + spectrum 3 波长 + 非法 target_type 优雅 FAIL）
- `lda_webui/app.py`：`/api/spectral_design`（target_type/target_ratio/wavelengths/Nx/Ny/iters 透传）
- `lda_webui/static/index.html`：㊶ 面板（目标类型下拉 + 结果表 + 死标量验收）
- `lda/reports/spectral_inverse_design_d80.json`：D-80 验收报告（split 2.5× / spectrum 11.7× / mode 8.6× 全 PASS）
- **实测**：split_ratio 50:50 实测比 0.574（err 0.074≤0.10）；spectrum 3 波长（1.53/1.55/1.57）imp 11.7×；mode_match 平坦 imp 8.6×；全目标 FD 对拍 ≤2e-4
- README：能力阶梯表加 D-80 行、四十→四十一面板、㊶ 面板清单
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 11 项枚举，延续）

### 新增/变更（post-v0.4 · D-81 · Track A 纵深新线）
- `lda/lda_solver/shape_inverse.py`：**形状逆设计核**——ShapeProblem（K 控制点宽度曲线 + sigmoid 软边界介电 + `project()` 可行性投影：宽度界 clip + 正反贪心平滑迭代）+ shape_gradient（链式 dFOM/dw=Σgeps·dε/dw）+ verify_shape_gradient（控制点 FD 方向对拍）+ shape_drc（宽度界 + 相邻控制点变化率）+ optimize_shape（线搜索 + 投影）
- `lda/lda_agent/multi_objective_design.py`：design_shape（单目标形状逆设计）+ design_multi_objective（多波长加权 FOM 共享形状 + Pareto 前端权重网格扫描）
- `lda/run_shape_design_smoke.py`：3/3 smoke（形状正例 + 多目标正例 + 宽度界非法优雅 FAIL）
- `lda_webui/app.py`：`/api/shape_design`（mode=shape|multi / n_controls / iters / wavelengths 透传）
- `lda_webui/static/index.html`：㊷ 面板（模式下拉 + 宽度曲线/多目标/Pareto 结果 + 死标量验收）
- `lda/reports/shape_multi_objective_d81.json`：D-81 验收报告（shape 6.6× / multi 5.6× 全 PASS）
- **实测**：形状逆设计 imp 6.6×（smoke 10.3×，宽度 taper 成形平滑 1.5≤1.5 DRC 过）；多目标 2 波长加权 5.6× + Pareto 3 点；形状梯度 FD 对拍 5e-4
- README：能力阶梯表加 D-81 行、四十一→四十二面板、㊷ 面板清单 + 目录结构补 shape/multi 模块
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 11 项枚举，延续）

### 新增/变更（post-v0.4 · D-82 · Track A 纵深第二件）
- `lda/lda_solver/hybrid_inverse.py`：**混合逆设计核**——HybridProblem（形状主干 K 控制点宽度曲线 + 拓扑微调带 M voxel 密度；**概率 OR 光滑组合** frac_total=frac_shape+ρ(1−frac_shape)，处处可导）+ 联合梯度（形状链式×(1−ρ) ⊕ 拓扑×(1−frac_shape)）+ verify_hybrid_gradient（混合参数 FD 对拍，ρ=0.5 远离边界）+ optimize_hybrid（联合线搜索 + 可行性投影 + 纯形状基线）
- `lda/lda_agent/hybrid_design.py`：混合逆设计统一入口（混合优化 + 纯形状基线对比 + 死标量验收：FD 对拍 / improvement / **混合≥纯形状** / DRC）
- `lda/run_hybrid_design_smoke.py`：3/3 smoke（混合正例 + 混合≥纯形状 + 拓扑带非法优雅 FAIL）
- `lda_webui/app.py`：`/api/hybrid_design`（n_controls/iters/topo_band 透传）
- `lda_webui/static/index.html`：㊸ 面板（分层表达结果 + 混合增益对比 + 死标量验收）
- `lda/reports/hybrid_inverse_d82.json`：D-82 验收报告（imp 18.3× / 增益 3.06× 全 PASS）
- **实测**：混合 imp 18.3× vs 纯形状 6.0×（**混合增益 3.06×**，smoke 29.5×/10.2× 增益 2.89×）；混合梯度 FD 对拍全过
- **工程坑**：①`min(1,frac+ρ)` 截断不可导 → 概率 OR 光滑组合；②拓扑 FD 对拍 ρ=0 单边差分半值假象 → ρ=0.5 对拍
- README：能力阶梯表加 D-82 行、四十二→四十三面板、㊸ 面板清单 + 目录结构补 hybrid 模块
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 11 项枚举，延续）

### D-83 混合参数化 × 多波长加权联合（2026-08-23 · Track A 纵深收官）

**里程碑：参数化×目标矩阵全打通——参数化∈{拓扑,形状,混合} × 目标∈{单场能,谱形目标,多波长}，本件 = 混合 × 多波长谱形**

- `lda/lda_solver/hybrid_inverse.py`：新增 `optimize_hybrid_multi`——多波长 HybridProblem（共享拓扑结构，固定 dl 只变 omega）+ 联合 FOM=Σw_λ·FOM_λ + 联合梯度=Σw_k·[gs,gt] + **分块归一化**（形状/拓扑块各自归一化，根治合并 max 归一化压制拓扑梯度）+ 逐波长 improvement + 基线对比
- `lda/lda_agent/hybrid_design.py`：新增 `design_hybrid_multi` 统一入口（多波长联合 FD 对拍 + 纯形状多波长基线 + Pareto 权重网格前端）+ main CLI `--mode multi`
- `lda/run_hybrid_multi_smoke.py`：3/3 smoke（混合×多波长正例 + Pareto 正例 + 单波长优雅 FAIL）
- `lda_webui/app.py`：`/api/hybrid_multi`（wavelengths/n_controls/iters/pareto 透传）
- `lda_webui/static/index.html`：㊹ 面板（逐波长 improvement + 混合增益 + Pareto 前端表 + 死标量验收）
- `lda/reports/hybrid_multi_d83.json`：D-83 验收报告（加权 imp 19.35× / 增益 3.18× / Pareto 3 点 全 PASS）
- **实测**：加权 improvement 19.35× vs 纯形状多波长基线（**混合增益 3.18×**，smoke 32.1×/10.7× 增益 3.01×）；逐波长 λ1.53:22.19× / λ1.57:16.50×；FD 对拍 9.8e-4
- **工程坑**：①基线 dict 键不匹配（improvement vs weighted_improvement）→ 兼容两键；②拓扑参与度统计口径——ρ_max=0.93 但 fill>0.5 近 0（稀疏关键体素），报告用 ρ_max/ρ_mean
- README：能力阶梯表加 D-83 行、四十三→四十四面板、㊹ 面板清单 + 目录结构补 hybrid 多波长说明
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 11 项枚举，延续）

### D-84 3D adjoint 形状逆设计（2026-08-23 · 破 3D 诚实边界第一步）

**里程碑：adjoint 从 2D 推向 3D Yee 交错网格——3D 更新算子显式转置伴随（数值 Mᵀ 对拍 1e-15）**

- `lda/lda_solver/adjoint_fdtd3d.py`：3D Yee 6 分量核（数组切片版）+ 差分转置 `_fd_t`/`_bd_t`（边界掩码严格镜像正演有效范围）+ `AdjointProblem3D`（平板波导：5 层核心 + 源匹配 + 海绵）+ `forward3d`（高斯脉冲软源 + 设计区 curlE 三分量记录 + 监视器 Ez 场能 FOM）+ `compute_gradient3d`（显式转置反向 + ε 灵敏度）+ `ShapeProblem3D`（宽度曲线 w(x) 软边界）+ `verify_adjoint3d`/`verify_shape_gradient3d`/`optimize_shape3d`
- `lda/lda_agent/adjoint3d_design.py`：统一入口（死标量验收：3D adjoint FD 对拍 + 形状梯度链式 + improvement + DRC）+ CLI
- `lda/run_adjoint3d_smoke.py`：3/3 smoke（正例 + 不同网格 + 域过小优雅 FAIL）
- `lda_webui/app.py`：`/api/adjoint3d`（Nx/Ny/Nz/n_controls/iters 透传）
- `lda_webui/static/index.html`：㊺ 面板（3D 域 + FD 对拍 + taper + 死标量验收）
- `lda/reports/adjoint3d_shape_d84.json`：D-84 验收报告（imp 2.02× 全 PASS）
- **实测**：FOM improvement 2.02×（聚焦 taper [2.29,3.66,5.02,4.30,5.80,4.86,4.65,3.15]）；3D adjoint FD 对拍 9.4e-6、形状梯度 8.2e-4（≤0.15）；Mᵀ 对拍 P_H 1.3e-15 / P_E 1.4e-15 / FULL 6.9e-16
- **工程坑**：①差分转置边界掩码——后向差分 g[0]=0 → tf[0]=-λ[1] 非 0（初版 j=0 置零致对拍 0.26）；②形状梯度 FD 对拍 delta≤0.02（0.05 时二阶非线性超阈 0.178）；③源-波导失配 → 源收窄 + 核心 5 层；④i_mon 贴设计区测近场 / 设计区压缩 → 恢复 ±6/±8；⑤48 域传播 20 格泄漏 imp 1.35 → 生产网格 44×36×12（imp 2.02）
- README：能力阶梯表加 D-84 行、四十四→四十五面板、㊺ 面板清单 + 目录结构补 adjoint3d 模块
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 11 项枚举，延续）

### D-85 3D 截面形状逆设计（2026-08-23 · 3D 纵深第二件）

**里程碑：把 z 截面也变成形状自由度——宽度 w(x) × 厚度 h(x) 双软边界（imp 3.17×，比平板 2.02× 提升 57%）**

- `lda/lda_solver/adjoint_fdtd3d.py`：`ShapeProblem3DSection`（z 底固定 0、顶 z_top=h(x)，介电=Δeps·σ_w·σ_h 双软边界处处可导；联合梯度 [dFOM/dw ⊕ dFOM/dh] 链式）+ `verify_section_gradient`（w+h 控制点混合采样 FD 对拍）+ `_section_drc`（宽度/厚度双界 + 双平滑）+ `optimize_section3d`（联合线搜索 + 双可行性投影）
- `lda/lda_agent/adjoint3d_design.py`：`design_section3d`（mode=section 统一入口）+ CLI `--mode section`
- `lda/run_adjoint3d_smoke.py`：4/4 smoke（shape 正例 + **section 正例** + 不同网格 + 域过小负例）
- `lda_webui/app.py`：`/api/adjoint3d` 加 `mode=section` 分支
- `lda_webui/static/index.html`：㊻ 面板（宽度/厚度双曲线 + 双界 DRC + 死标量验收）
- `lda/reports/section3d_d85.json`：D-85 验收报告（imp 3.17× 全 PASS）
- **实测**：FOM improvement 3.17×（宽度 [2.58,4.08,4.61,4.18,4.54,4.91,4.26,2.76] + 厚度 [2.98,4.48,3.74,2.83,2.67,3.50,3.60,2.34]）；3D adjoint FD 对拍 1.1e-4、截面梯度 1.0e-2；DRC 双界双平滑全过（w 1.50 / h 1.50 ≤1.5）
- **工程坑**：①`ShapeProblem3DSection.knots` 误用域宽度（di1-di0）作控制点数 → np.interp fp/xp 长度不匹配 ValueError（探针 40×32×12 域宽恰 =8 掩盖 bug）→ 改 `linspace(di0, di1-1, n_controls)`
- README：能力阶梯表加 D-85 行、四十五→四十六面板、㊻ 面板清单
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 11 项枚举，延续）

### D-86 3D 逆设计 × 3D 端口 S 参数联合验收（2026-08-23 · 补闭环最大缺口）

**里程碑：3D 逆设计结果首次获得端口级验收（战略审计 LDA-ST-001 最大缺口的闭环）**

- `lda/lda_solver/port_sparams_3d.py`：`cw3d_port_powers` 加 **`src_profile` 可配源截面**（None = 默认 SOI 0.5×0.22µm 矩形，向后兼容 D-72；D-86 起支持 3D adjoint 域平板波导适配）
- `lda/lda_agent/port_acceptance.py`：`design_port_acceptance`（3D adjoint 场能优化 → 独立 3D CW 端口核测 S11/S21 → **双独立确认**验收：FOM imp ≥1.5 且 S21 imp ≥1.5 + 能量守恒 + FD 对拍 + DRC）+ CLI
- `lda/run_port_acceptance_smoke.py`：3/3 smoke（正例 + 不同波长 + 宽度界非法负例）
- `lda_webui/app.py`：`/api/port_acceptance`（w_min/init_w/iters 透传）
- `lda_webui/static/index.html`：㊼ 面板（FOM×S21 双确认 + 能量守恒 + 死标量验收）
- `lda/reports/port_acceptance_d86.json`：D-86 验收报告（FOM 1.88× + S21 1.60× 双过 全 PASS）
- **实测**：场能 FOM imp 1.88× **且** 端口 S21 0.132→0.211（1.60×）——两个独立测量同向双过；能量守恒 S11+S21≈1；3D adjoint FD 对拍 1e-4；smoke 3/3；D-72 端口核回归 5/5、D-84/85 回归 4/4 零影响
- **关键物理认知**：①**聚焦 FOM ≠ 透射 S21**——收集场能 FOM 优化"聚焦"，两端收窄 taper 端口模式失配 → S21 反降（w_min=2：FOM 2.02× 但 S21 0.80×）；**对齐 = w_min=4 + init_w=6**（初始比源宽，优化 taper 收窄匹配源）→ FOM 与 S21 同向；②S21 提升对网格/域配置敏感（40 域 1.19×、dlf=12 1.28×）、对波长鲁棒（1.5/1.6 均 1.57×）——最优配置 dlf=10 + 44 域
- **诚实标注**：S 参数为两端口功率占比（P_out/(P_in+P_out)），非严格模式分解 S 参数（无模式正交投影）；FOM 为收集场能
- README：能力阶梯表加 D-86 行、四十六→四十七面板、㊼ 面板清单 + 目录结构补 port 模块
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 11 项枚举，延续）

#### D-87 谱形目标 × 3D 截面（2026-08-24 · 参数化×目标矩阵 3D 打通）
- **新增**：`adjoint_fdtd3d.py`——`make_wl_problems3d`（多波长问题族：deepcopy 保留惰性 dl/dt 基准网格，只改 omega/period_steps → **归一化网格陷阱免疫**）、`verify_section_gradient_multi`（多波长加权联合梯度 FD 对拍：联合 FOM=Σw_λ·FOM_λ 中心差分）、`optimize_section3d_multi`（**分块归一化** w/h 各自尺度 + 全波长线搜索同投影一致）；`adjoint3d_design.py`——`design_spectral3d`（mode=spectral）+ CLI choices 扩 spectral；`run_adjoint3d_smoke.py` 扩到 5 例
- **实测**（生产网格 44×36×12，三波长 1.5/1.55/1.6）：加权 improvement **3.13×**（逐波长 3.18×/3.15×/3.06×——三波长同向 ≥3×，远超 1.2 门槛）、多波长联合梯度 FD 对拍 **4.2e-4**、3D adjoint 对拍 1.1e-4、DRC 双界全过（w=1.50/h=1.50）；smoke 5/5；D-84/85 回归零影响；WebUI ㊽ 面板 + `/api/adjoint3d` mode=spectral（HTTP 实测 wimp 1.92×）
- **工程坑**：`verify_section_gradient_multi` 返回缺 `nsamples` 键 → verdict KeyError（补齐）
- README：能力阶梯表加 D-87 行、四十七→四十八面板、㊽ 面板清单
- 兼容性：IR schema 0.3（延续）；设计包 schema 0.1（kind 11 项枚举，延续）

#### D-89 · 3D adjoint numba 化性能升维（2026-08-24，突破 3D 域规模天花板）
- **核**：3D Yee 步进 + 显式转置反向 **prange 并行 JIT**（`_step_h_nb`/`_step_e_nb`/`_fwd_nb3d` + `_bd_t_nb`/`_fd_t_nb` 逐点差分转置 + `_grad_nb3d`）；`forward3d`/`compute_gradient3d`/三个 optimize 函数加 `backend`（auto/numba/numpy，**无 numba 自动回退纯 numpy**）
- **实测**（repeat=3 取最好）：forward 加速 **44 域 8-11× / 64 域 17-21× / 80 域 22-29×**（最大域 ≥20× 验收过）；FOM/curlE/梯度 **bit-level 一致（rel ≤ 3.7e-16）**；梯度 2-5×；**优化链路 64 域 4.4-5.2×**（imp 1.336==1.336 完全一致）；无 numba 回退正常（managed smoke 6/6、numba 环境 smoke 6/6 全过 16s vs 146s）；报告 `reports/perf_adjoint3d_d89.json`
- **工程坑**：① dampE/dampH 为 (Nx,1,Nz) 广播形状 → numba 逐点索引 j 越界读垃圾（物理 NaN）→ 包装层广播全尺寸化；② curlE 记录误带 cH/eps 系数 → 去掉（与 numpy 版记录 curl(H) 差分组合一致）；③ 小域优化链路加速被 eps 构造 Python 开销稀释（0.9×）→ 大域才是主战场
- **文档/UI**：README D-89 行 + 四十八→四十九面板 + ㊾ 清单 + 目录补 run_perf_adjoint3d；WebUI ㊾ 面板 + `/api/adjoint3d_perf`；D-77 回归 9 PASS 零影响

#### D-88 · QEDA 求解器级补强：transmon-resonator 色散读出（2026-08-24，量子蓝海占位）
- **核**：`lda_solver/qubit_resonator_solver.py`——三能级 transmon（|g⟩|e⟩|f⟩，E_f=2f_q+α）+ Fock 谐振器**联合严格对角化**（耦合 g·(n̂₀₁σ+n̂₁₂√2)(a+a†)）；Blais 修正解析 χ=g²α/(Δ(Δ+α))；最近能量匹配提取 qubit 态依赖谐振器频移
- **实测**（f_q=5.0, α=-0.3, f_r=6.0, g=0.1, κ=0.005）：χ_num=-0.002251 ↔ χ_an=-0.002308（**rel 2.5%** ≤10%）；二能级近似 rel **77.5%**（**α 修正必要性 31×**，χ 为负即非谐性标志）；拉比分裂自洽 0.02%；**n_crit=25 / Purcell γ=5e-5 GHz（T1≈3.2e6 µs）/ AC Stark 1ph=-0.0045 GHz**；smoke 3/3（含色散区失效 Δ/g<5 负例）；量子链回归全绿（D-23/D-43/D-46/D-51/D-55）；报告 `reports/qubit_resonator_d88.json`
- **工程坑**：三能级低能谱顺序 |g,0⟩<|e,0⟩<|g,1⟩<|f,0⟩<|e,1⟩——固定索引错取态（χ 假值 -1.94）→ **最近能量匹配**提取四态
- **文档/UI**：README D-88 行 + 四十九→五十面板 + ㊿ 清单；WebUI ㊿ 面板 + `/api/qubit_resonator`；D-77 回归 9 PASS 零影响

#### D-91 · QEDA 纵深三件套（2026-08-24，QEDA 求解器栈纵深）
- **核**：`lda_solver/qeda_depth_solver.py`——①**多能级电荷基底展开**（`tls_spectrum_L`：L 能级 E_s=s·f_q+s(s-1)/2·α + 耦合矩阵元 √(s+1) + Fock 谐振器严格对角化，χ 收敛性验证）；②**驱动场 Rabi/AC Stark**（`rwa_spectrum`：RWA 静态哈密顿 H=−(δ/2)σz+(Ω/2)σx）；③**多 qubit 读出串扰**（`twoq_resonator_spectrum`：2 transmon 异频 + 共享谐振器，`_jzz_from_spectrum`：J_zz=(E_ee−E_eg−E_ge+E_gg)/2）
- **实测**：①χ(L=3)=−0.002251→L=6=−0.002262（**收敛 0.495%** <1% + Blais 解析 rel 1.98%）；②共振 **Rabi rel 0.0000**、失谐 **AC Stark 0.001556 vs 解析 0.001563（rel 0.39%）**；③**J_zz=0.000831 GHz**、g=0 自洽 −4.4e-16、**互换对称 rel 0**、|J_zz/χ|=0.369 弱耦合；smoke 4/4（标准点 + 不同参数 + 驱动强场负例 + 串扰简并负例）；量子链回归全绿；报告 `reports/qeda_depth_d91.json`
- **工程坑**：双 qubit 同频简并使最近匹配态标记错乱（χ1 假值 −0.0107 vs 单 qubit −0.00225）→ **异频打破简并 + ZZ 耦合提取**（无需谐振器态标记）；驱动强场 Ω/δ_d>1 时 AC Stark 弱驱动近似失效 → 负例诚实捕获
- **文档/UI**：README D-91 行 + 五十→五十一面板 + 面板 51 清单；WebUI 面板 51 + `/api/qeda_depth`；D-77 回归 9 PASS 零影响

#### D-92 · 3D voxel 拓扑逆设计（2026-08-24，3D 纵深最后一环）
- **核**：`adjoint_fdtd3d.py` 新增 `TopologyProblem3D`（设计区 = 核心层体素 `_dr`，潜伏密度 r∈[0,1] + **tanh 投影 beta 2→beta_max 延拓**（先柔后硬二值化，可制造性内建）+ 链式 dFOM/dr=Δeps·geps·dρ̄/dr）+ `verify_topo_gradient3d` + `optimize_topology3d`（最大分量归一化 + Armijo 回溯线搜索同投影一致）+ `design_topology3d`（mode=topology）
- **实测**（44×36×12, iters=24, beta_max=16）：**imp 6.30×**（FOM 33.7→212）、3D adjoint FD 对拍 1e-4、**拓扑梯度链式 5.9e-3**、**二值化 20.8%**；HTTP 40 域 imp 7.76×；smoke **7/7**；shape/section/spectral 回归零影响；报告 `reports/topology3d_d92.json`
- **工程坑**：3D 拓扑二值化收敛慢（44 域 18 迭代仅 18% 二值）→ **iters=24 + beta_max=16 达 20.8%**；beta 太激进损 FOM（28 迭代 bm=18 → imp 4.67×）→ 平衡点 24/16
- **文档/UI**：README D-92 行 + 五十一→五十二面板 + 面板 52 清单；WebUI 面板 52 + `/api/adjoint3d` mode=topology；D-77 回归 9 PASS 零影响

## v0.0（阶段 0/1/2，此前交付）

- 自研 1D/2D/3D FDTD（numpy 零依赖，物理定律锚校验）+ Numba-CPU JIT + PyTorch GPU 升维
- L0 IR 光子子集（D-01~D-05）、L1 agent 闭环、L2 器件库（GDS/DRC/版图仿真）
- 确定性比对裁判 B1-B11（含量子 B9/B10）
- AI-dev 自举写核（SolverSpec + ORACLE + BootstrapLoop）、生产级 GPU 网格（6400 万点）
