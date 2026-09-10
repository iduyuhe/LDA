# LDA 研发生产系统设计稿（讨论稿 · 待杜先生批动手）

> 版本：v0.9.40 衍生 · 日期：2026-09-05
> 决策来源：杜先生 17:21 讨论定调（4 项）
> 关联：`lda_product_plan_2027.md`（研发计划）· `design_alliance_resource_planning_report.md`（资源规划总报告）· `lda/lda_harness/proposal_compiler.py` · `lda/lda_agent/design_pipeline.py` · `lda/lda_l2/innovation_market.py` · `lda/lda_l2/golden_product_benchmarks.py`

---

## 0. 决策落定（4 项）

| # | 决策点 | 杜先生定调 |
|---|---|---|
| 1 | 系统定位 | **设计生产线**（产出可售/可流片设计方案 + 反向验证报告 + 超市货架，不碰真实流片制造，守 C 闸门） |
| 2 | 自动化度 | **半自动**（每款产品投产前人工确认需求与规格，agent 只管设计-验证-上架） |
| 3 | 计划驱动 | **解析规划文件**（直接读 `lda_product_plan_2027.md` 拆解成产品需求，规划即输入） |
| 4 | 首批范围 | **A+B+C 全上**（数通 + 传感 + 量子三赛道全部纳入生产计划） |

---

## 1. 系统定位与边界

**一句话**：在 LDA 已有"需求编译→编排→设计→超市上架→流片"骨架上，补一个**生产调度层**，让它能读《2027 产品规划》、半自动批量产出"经过物理定律锚反向验证的可售设计方案"，并自动沉淀进创新超市货架。

**边界（红线不越）**：
- ✅ 产出 = 设计方案（参数 + GDS + SVG）+ 反向验证报告 + 超市货架条目；
- ❌ 不调用 `lda_pdk/tapeout_pipeline.py`（真实 PDK/流片属 C 期，现在不做）；
- ❌ LLM 不进判决路径（PASS/FAIL 由死标量定，复用现有四锚/系统锚机制）；
- ✅ 每次产出强制过 `golden_product_benchmarks.evaluate_all()`（反向验证护栏）。

---

## 2. 现有能力盘点（实测，非假设）

| 模块 | 位置 | 现状 | 生产系统怎么用 |
|---|---|---|---|
| 需求编译 | `lda/lda_harness/proposal_compiler.py` | `compile_proposal` + `SYSTEM_TYPES` 注册表（**link / wdm_demux / quantum_fidelity 3 类已有**） | 扩 B 赛道 sensor 类；作为任务执行入口 |
| 系统类型分发 | 同上 `design_pipeline(req, system_type)` | 把 req 分发到对应 system_type 引擎，走死标量锚 | 生产任务直接复用，不另造 |
| 器件级流水线 | `lda/lda_agent/design_pipeline.py` | `run_pipeline(kind)` 支持 **Waveguide/RingResonator/DirectionalCoupler/SymmetricYBranch** 4 类 | 产品级任务在器件级之上做编排封装 |
| 创新超市 | `lda/lda_l2/innovation_market.py` | `ShelfItem` + `evaluate_all` + `save/load_library_json` | 产出包装成 ShelfItem 上架，货架 58→~70 |
| 反向验证 | `lda/lda_l2/golden_product_benchmarks.py` | `evaluate_all()` **29/29 PASS** | 每次生产产出强制过此护栏 |
| 流片流水线 | `lda/lda_pdk/tapeout_pipeline.py` | 真实流片（**C 期，本系统不调**） | 留接口，不接 |

**结论**：骨架齐全，**唯一实质缺口 = B 赛道（传感）缺 system_type + 死标量锚**；外加"规划解析器"和"生产调度层"两件新件。

---

## 3. 目标架构

```
┌─────────────────────────────────────────────────────────┐
│          研发生产系统（新建 lda/lda_l3/production_plan.py） │
├─────────────────────────────────────────────────────────┤
│ ① 规划解析器  parse_plan(md) → 结构化生产任务清单           │
│ ② 确认门      dump pending_tasks.json → 人工 review/确认   │  ← 半自动落点
│ ③ 执行器      per 任务:                                   │
│      proposal_compiler.design_pipeline(req, system_type)  │
│      + design_pipeline.run_pipeline(kind) 器件级封装       │
│      → 包装 ShelfItem                                     │
│ ④ 反向验证护栏 golden_product_benchmarks.evaluate_all()    │  ← 红线必跑
│ ⑤ 上架        innovation_market.save_library_json()        │
│ ⑥ 报告        production_report.md + .json               │
└─────────────────────────────────────────────────────────┘
            ↑ 复用（不另造）            ↑ 复用（不另造）
   proposal_compiler / design_pipeline   innovation_market / golden_product_benchmarks
```

---

## 4. 数据流（一次生产闭环）

1. **解析**：读 `lda_product_plan_2027.md` → 提取 A/B/C 三赛道的「目标产品 + 拟增货架 ID + 目标 golden 死标量占位」→ 生成 `production_tasks.json`（结构化）。
2. **确认门（半自动）**：把 `production_tasks.json` 落盘，标记 `status=pending`；人工删除/修改/追加后，置 `status=approved` 才执行。**这是"半自动"的物理落点**——agent 不擅自动手，等杜先生/团队确认。
3. **执行**：对每个 approved 任务，按 `system_type` 调 `proposal_compiler.design_pipeline` → 若需器件级 GDS，调 `design_pipeline.run_pipeline(kind)` 封装。
4. **护栏**：产出自动过 `golden_product_benchmarks.evaluate_all()`，任一 FAIL 则该产品 `status=blocked` 不进货架，进报告待查。
5. **上架**：通过护栏的产出包装成 `ShelfItem`，`save_library_json` 进超市（货架 58→~70）。
6. **报告**：`production_report.md` 列每产品：设计参数 / GDS / 反向验证结果 / 货架 ID / PASS·BLOCKED，并附护栏反向测试状态（D-67 类）。

---

## 5. 一期实施计划（M1–M3，严守红线）

### M1 — 骨架打通 + A/C 赛道验证（复用既有）
- 新建 `lda/lda_l3/production_plan.py`：`parse_plan()` + `confirm_gate()` + `execute_task()` + `run_production()` + `write_report()`。
- `parse_plan` 先支持 A（link/wdm_demux）、C（quantum_fidelity）两赛道的货架 ID 映射（这两类 SYSTEM_TYPES 已有）。
- 跑通一条端到端：规划里 A 赛道 `IM-1.6T-DR8`/C 赛道 `IM-QCTRL-32Q` → 确认门 → 执行 → 反向验证 → 上架 → 报告。
- **不动既有护栏、不碰 C 闸门**。

### M2 — B 赛道补齐（最大实质缺口）
- 在 `proposal_compiler.SYSTEM_TYPES` 新增 `sensor_lidar`（FMCW 全前端）、`sensor_pon`（50G-PON/FTTR PLC）、可选 `sensor_bio`（POCT 生物传感），每类**自带死标量锚**（如 LiDAR：测距精度/插损预算；PON：IL/XT 闭式），复用 S1/S2/S5 同式或新增 B 类锚。
- `parse_plan` 扩展支持 B 赛道货架（`IM-LIDAR-FULL`/`IM-FTTR-PLC32` 等）。
- 反向验证库同步扩 B 类 golden（对应 `lda_product_plan_2027.md` §1.3 的 12 条目标里传感相关项）。

### M3 — 三赛道全跑通 + 闭环收口
- A+B+C 全部纳入 `production_tasks.json`，半自动确认后批量执行。
- 货架 58 → ~70；golden 反向验证 29 → ~41（与产品规划 §1.3 节奏对齐）。
- 出 `production_report.md` 总报告 + 接入 CI（新护栏：`run_production_smoke.py`，防回归）。

---

## 6. 三赛道覆盖缺口与对策

| 赛道 | 现有 SYSTEM_TYPES | 缺口 | 对策（M 阶段） |
|---|---|---|---|
| A 数通 | link ✅ / wdm_demux ✅ | 无（货架 ID 映射待接） | M1 接 parse_plan |
| B 传感 | **无 ❌** | 缺 system_type + 死标量锚 | M2 新增 sensor_* |
| C 量子 | quantum_fidelity ✅ | 无（货架 ID 映射待接） | M1 接 parse_plan |

---

## 7. 红线对齐表

| 红线 | 落实方式 |
|---|---|
| LLM 不进判决 | 复用 proposal_compiler 四锚/系统锚，生成器失败自动降级网格基线 |
| 物理定律锚 | 每次产出强制 `golden_product_benchmarks.evaluate_all()`，FAIL 即 blocked |
| C 闸门不越 | 生产系统不 import / 不调用 tapeout_pipeline |
| 护栏反向测试 | 报告含 D-67 类护栏状态；新增 `run_production_smoke.py` 进 CI |
| 诚实标注 | ShelfItem 标注"等效验证"，不冒充流片验证 |

---

## 8. 验收标准（一期完成判定）

- [ ] `lda/lda_l3/production_plan.py` 存在且 `run_production()` 可端到端跑通；
- [ ] 能从 `lda_product_plan_2027.md` 解析出 A+B+C 三赛道任务（B 在 M2 后）；
- [ ] 半自动确认门生效（无 approved 不执行）；
- [ ] 每次产出过 golden 反向验证，FAIL 不进货架；
- [ ] 货架 58 → ~70，golden 29 → ~41；
- [ ] 出 `production_report.md` + CI 护栏 `run_production_smoke.py` 全绿。

---

## 9. 风险与对策

| 风险 | 对策 |
|---|---|
| 规划文件自然语言，解析脆弱 | parse_plan 用"货架 ID + 赛道标题"正则提取，留人工确认门兜底 |
| B 赛道死标量锚设计不当致假绿 | M2 新增锚先过 `run_golden_product_smoke.py` 反向测试再接入 |
| 批量产出稀释护栏 | 单任务单护栏，FAIL 即 blocked，不批量放行 |
| 越 C 闸门 | 代码审查禁止 import tapeout_pipeline；CI 加 import 扫描 |

---

## 10. 下一步动手授权点

本稿为讨论稿。**请你确认后，我按 M1 启动**：新建 `lda/lda_l3/production_plan.py` 骨架 + 解析器（A/C 两赛道）+ 确认门 + 端到端跑通一条 A 赛道样例，并出 `production_report.md`。M2/M3 在 M1 验收后依次推进。
