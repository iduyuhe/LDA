# LDA 代码审计报告（独立版）

> 版本基线：v0.9.169 · 日期：2026-10-01 · 性质：**代码审计（静态/结构层）**（不改锚、不动棘轮、不发版）
> 方法：Explore agent 盘仓（`lda/` 全包结构 + 关键文件点验）+ Grep 计数核验；**不含全动态审计**（272 smoke 全跑 + import-graph 死代码分析），后者列为主文档 §7 阶段 6 工作流 W6-3。
> 主文档：`docs/LDA_战略总纲与全面审计_实施规划_v0.9.169_2026-10-01.md` §4；本报告为其独立展开版。

---

## 0. 一句话结论

**架构分层（lda_solver / lda_l2 / lda_l3 / lda_layout / lda_pdk / lda_agent / lda_webui）清晰、主权隔离实现干净、pyflakes 棘轮在守；但存在 8 项结构问题——最重的是文档↔代码漂移与 smoke 平铺无包、源码树混入大型 artifact。无致命项，均为可维护性/可信度侵蚀。**

---

## 1. 包结构概览（实测）

| 子包 | 职责 | 状态 |
|---|---|---|
| `lda/lda_solver/` | 求解核 + redline 主权单一真源 | 健全 |
| `lda/lda_l2/` | 二层能力域（含 `ecore/` 电子征程 24 模块） | 健全；ecore 按功能命名（无 E1.py 等编号文件） |
| `lda/lda_l3/` | 三层（production_plan） | **实质空壳（仅 2 模块）**，若文档称 L3 成熟须纠正 |
| `lda/lda_layout/` | 版图 / 布线 / GDS 导出 | 健全（主权全链路已实证） |
| `lda/lda_pdk/` | PDK 生命周期框架 | 框架在，无 foundry 官方 PDK（外部阻塞） |
| `lda/lda_agent/` | Agent 编排层 | 健全 |
| `lda/lda_webui/` | 零依赖后端 + 静态控制台 | 健全（app.py / routes.py / static/index.html） |
| 根 `lda/` | benchmarks.py / golden.py / verification_adapters.py + **272 个 run_*_smoke.py 平铺** | 平铺问题见 C3 |

规模：`lda/` 下 **686** 个 .py 模块；CI core 260 条（run_ci_regression.py CORE_SMOKES 编排）。

---

## 2. 已确认的结构问题（按严重度）

| # | 问题 | 证据 | 严重度 | 建议 |
|---|---|---|---|---|
| C1 | **文档↔代码严重漂移** | README 曾写「B1–B11」级旧口径；golden.py `_PHYSICAL_LAW` 实际覆盖至 B458 | 中 | 文档对齐（W1 线，本轮已基本完成） |
| C2 | **E 模块命名错位** | 文档称「23 模块/E1–E19」；磁盘 `ecore/` 实际 **24** 个 .py，且按功能命名（无 E1.py） | 低 | 文档统一口径（以 24 为准） |
| C3 | **smoke 平铺无 tests/ 包** | 272 个 `run_*_smoke.py` 直接落 `lda/` 根；CORE_SMOKES 硬编码 | 中 | 迁 `tests/` 或 `smokes/`；门禁反向完备（成员⊆白名单，防新成员静默进盲区） |
| C4 | **源码树混入大型 JSON artifact** | `redteam_*.json`(103/54/82KB)、`timeout_budget_baseline.json`(85KB)、`noncore_replay_ledger.json`、`reports*/`(~20 目录) | 中 | 移出源码树→`.artifacts/` 并 gitignore；受跟踪复测台账类文件迁移须同步改消费方路径 |
| C5 | **scratch 残留** | `lda/_assess_b2_semi_fd.py`、`_magent_b2_*.py` 等下划线前缀实验件 | 低 | 归档/清理（lda-scratch-cleanup 技能流程） |
| C6 | **`lda_l3` 实质空壳** | 仅 2 模块（production_plan + __init__） | 低 | 若文档称 L3 成熟须纠正 |
| C7 | **无 `__version__` 常量** | 版本仅散落 docstring/注释；真源在 pyproject.toml | 低 | 引入单一 `lda/__init__.__version__` 真源（与版本线三同步纪律一致） |
| C8 | **build artifact 入树** | `lda/lda_design.egg-info/` | 低 | gitignore（注意：`.gitignore` 不能取消已跟踪文件，须 `git rm --cached`） |

---

## 3. 正向发现（值得保留的纪律）

- **pyflakes 棘轮**（`run_pyflakes_ratchet_smoke`）在位：死代码/未用导入/`.gitignore` 误伤（⑥ `git ls-files -i -c --exclude-standard == ∅`）均有门禁。
- **主权隔离实现干净**：Meep subprocess 只回标量、Tidy3D 仅 ORACLE、`redline.py` 单一真源。
- **门禁反向完备意识已建立**：E19 前端取值路径门禁（路径存在性+别名时间线+反向完备）、NON_CORE_SMOKES 复测台账（`noncore_replay_ledger.json` + `scripts/noncore_replay.py --check`）。

---

## 4. 审计边界与后续

- 本审计为**静态/结构层**，未执行全量 smoke 运行与死代码 import-graph 分析。
- 后续动作映射主文档 §7 阶段 6：W6-1 artifact 迁出（C4/C5/C8）、W6-2 smoke 归包（C3）、W6-3 全动态审计（272 smoke 全跑 + 死代码分析，C1 闭环验证）。
- 迁移类动作（C3/C4/C8）须遵守既有纪律：改 `.gitignore` 后必跑 `run_pyflakes_ratchet_smoke`；宽模式宁窄勿宽；受跟踪文件先 `git rm --cached`。

---

*报告主体版权：上海杜特企业管理咨询有限公司 · LDA 工程（AI 代行工程决策）· 2026-10-01*
