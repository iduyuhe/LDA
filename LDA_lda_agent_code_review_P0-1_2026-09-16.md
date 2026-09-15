# LDA · `lda_agent` 专项代码评审（P0-1：导入健康 / 异常路径 / 死代码 / 覆盖）

> 评审对象：`D:/agent_LDA/lda/lda_agent/`（54 个 .py / 约 13k 行，LDA 最大最复杂模块）
> 评审日期：2026-09-16 · 评审人：WorkBuddy（独立代码评审）
> 基线版本：**v0.9.78**（commit `ae836dc`，生产仍 0.9.75 未部署）
> 方法：**纯静态分析**（AST 自研扫描 + `pyflakes 3.4.0` 权威 lint）；未改动任何代码、未执行被测模块。
> 区别定位：本评审是对 2026-09-14 复评（红线/沙箱/确定性/可维护性）的**正交补刀**——
> 聚焦四个工程卫生维度，不重复已根治项。

---

## 0. 评分卡

| 维度 | 结论 | 风险等级 | 关键证据 |
|---|---|---|---|
| **导入健康** | 无通配符 import、无语法错、无断链 import；但 **34 处未用 import** 待清 | 🟢→🟡 | `pyflakes` 0 wildcard / 0 syntax error；34 unused import |
| **异常路径** | 无 `bare except`；21 处 `except Exception`，其中 **10 处静默吞掉** | 🟠 MED | 详见 §2，最险 `coupler_loop:81` 拟合失败→`None` 上溢 |
| **死代码** | 7 处"赋值未用"局部变量（疑似丢算）；整仓跨引用 84 候选多为动态派发（非真死） | 🟡 LOW→🟠 | `pyflakes` 7 unused-local；`MODULE_MAP.md` 已标注 loop 重复 |
| **覆盖** | **51/54** 被包/测试引用；3 个独立校验脚本 **无 CI 护栏** | 🟡 LOW | `calibrate_kappa_grid`/`verify_voxel_pipeline`/`verify_waveguide_2d` |

**一句话**：导入健康基本面良好（无危险原语、无 wildcard、无断链）；真正需止血的是
**10 处静默吞异常**（其中 1 处会向上游传 `None`）与 **3 个无 CI 护栏的验收脚本**；
未用 import / 未用局部变量属低风险的卫生债，建议一次性美容清理。

---

## 1. 导入健康（Import Health）

**`pyflakes` 权威结果**：`lda_agent` 全包 **0 个 wildcard import、0 个语法错误、0 个断链 import**；
发现 **34 处未用 import** + 4 处未定义名（见 §3）+ 2 处 f-string 空占位 + 7 处未用局部变量。

### 1.1 未用 import 分类（共 34，全部低风险，可安全删除）

| 类别 | 数量 | 代表 |
|---|---|---|
| `typing.*` 残留（`List`/`Dict`/`Tuple`/`Optional`/`Callable`/`field`） | 12 | `agent_planner:11`、`directional_coupler:26`、`spectrum_loop:23`、`waveguide_loop:22`、`port_acceptance:30`、`readout_fidelity:30`、`qubit_readout_chain:35`、`inverse_design:25` |
| `math` 残留 | 5 | `multiband_loop:15`、`multiqubit_readout:23`、`pipeline_realize:13`、`tunable_wdm:28`、`wdm_splitter:17`、`verify_waveguide_2d:22` |
| 跨模块 import 后未接（疑似重构遗留） | 9 | `adjoint_design:28`（2× adjoint_fdtd）、`coupler_loop:44` oracle_coupler、`inverse_design:32` spectrum_loop.metric_error、`large_scale_bench:50` wdm_system.channel_capacity、`multiqubit_fidelity:33` readout_fidelity、`primitives_design:26` gds_export、`qeda_topology:29` surface_code |
| 安全层/`torch` 死 import（已改可用探测） | 4 | `coupler_loop:203` `torch`、`coupler_loop:348` `torch as _torch`、`solver_writer:36` subprocess、`solver_writer:38` tempfile |
| 演示入口残留 | 2 | `ring_loop:22` os、`ring_loop:23` sys、`run_demo:14` json、`run_demo:22` design_loop.json_report |

> 注：自研 AST 初扫曾误报 74 处"未用 import"，经交叉核验（import 的绑定名在文件文本中均有出现，
> 多为属性基 / 字符串 / 动态派发），**真实未用数 = `pyflakes` 34 处**。本报告以 `pyflakes` 为准。

### 1.2 风险判定
- 🟢 **无 `from X import *`**：阻断静态分析、掩盖未定义符号的头号污染源不存在。
- 🟢 **无断链 import / 无语法错误**：模块可整体编译加载。
- 🟡 **34 处未用 import**：不影响运行，但拖慢阅读、误导"该符号被用"、掩盖真依赖。
  建议一次性 `pyflakes` 驱动删除（成本极低、零行为风险）。

---

## 2. 异常路径（Exception Paths）

全包 `except Exception` / `except BaseException` 共 **21 处**（**无 `bare except`**）。
按行为分两类：**11 处"捕获后未重抛"（broad）** + **10 处"静默吞掉"（swallowed）**。

### 2.1 静默吞异常（10 处——优先关注）

| 文件:行 | 现状 | 风险 | 建议 |
|---|---|---|---|
| `coupler_loop.py:81` | `least_squares` 拟合失败 → `return None` | 🔴 **中高**：`None` 直接上溢给 `float(res.x[0])` 调用方，可能 `TypeError`/静默错解 | 改显式 `raise FitError` 或返回 `(ok, val)`，调用方强制判空 |
| `quantum_design.py:67` | `_ensure_path()` 包 `_ensure_solver_on_path` → `pass` | 🟡 求解器不在 PATH 被静默忽略，错误延后到仿真时才暴露、根因难追 | 至少 `logging.debug` 记录失败原因 |
| `inverse_design.py:91` | 同上 `_ensure()` → `pass` | 🟡 同 2 | 同上 |
| `design_pipeline.py:131` | `_cuda_ok()` `import torch` 失败 → `return False` | 🟢 **可接受**：CUDA 可用性探测，失败即"无 CUDA"是设计意图 | 保持；可加 debug 日志 |
| `sandbox.py:136` | `os.chmod` 放宽 nobody 权限失败 → `pass` | 🟠 **中**：权限放宽失败被吞 → nobody 可能进不去 tmp → 候选执行静默失败（fail-closed 但难诊断） | 记录 warning；失败时应显式报错而非继续 |
| `sandbox.py:197` | `finally` 中 `rmtree(ignore_errors=True)` 包 `except pass` | 🟢 标准安全清理，可接受 | 保持 |
| `sandbox.py:150` | `_parse` JSON 解析失败 → 返回 `{"ok":False,"error":...}` | 🟢 **可接受**：fail-closed 且带完整 STDERR，非静默 | 保持 |
| `ring_adddrop.py:380`、`qubit_readout_chain.py:227`、`multiqubit_readout.py:328` | 各自吞异常 `pass`/`return` | 🟡 需逐个确认是否掩盖了关键物理判定失败 | 至少记录，避免 `status` 静默变 OK |
| `ring_loop.py`（main_ring 演示） | 演示内吞异常 | 🟢 演示路径，低风险 | 保持 |

### 2.2 捕获后未重抛（11 处 broad，非静默）
`agent_synthesis:52`、`agents:131`、`l1_protocol:61/69`、`llm_proposer:142`、`orchestrator:68`、
`pipeline_realize:117`、`primitives_design:99`、`redteam_proposer:141`、`ring_adddrop:219`。
- 其中 `llm_proposer:142` 是**红线设计意图**：LLM 提案异常 → 返回 `[]` 降级纯网格（与 09-14 评审一致，正确）。
- 其余多为"坏候选/外部依赖失败 → 降级"模式，可接受但**建议统一加 `logging.warning`**，避免根因不可见。

### 2.3 风险判定
- 🟢 无 `bare except`（不会吞 `SystemExit`/`KeyboardInterrupt`）。
- 🔴 **唯一需止血**：`coupler_loop.py:81` 拟合失败静默返 `None`——是 10 处静默里唯一会**向上游传脏值**的，建议优先修。
- 🟡 其余静默点建议"最低成本加日志"，不改控制流。

---

## 3. 死代码（Dead Code）

### 3.1 `pyflakes` 确认的"赋值未用"局部变量（7 处——疑似丢算，需人审）

| 文件:行 | 变量 | 疑点 |
|---|---|---|
| `gc_design.py:24` | `pts` | 计算后未用，可能漏掉几何点校验 |
| `multi_objective_design.py:201` | `joint_ok` | 联合判据算而未用，可能漏掉一道验收 |
| `pipeline_realize.py:129` | `n_real` | 实层计数算而未用 |
| `readout_fidelity.py:125` | `Q_ext` | 外部 Q 算而未用，可能漏物理量 |
| `splitter_readout.py:245` | `dc_ir` | 直流项算而未用 |
| `tunable_wdm.py:127` | `realloc_ok` | 重分配结果算而未用 |
| `wdm_splitter.py:69` | `w` | 宽度算而未用 |

> 这些**不一定是 bug**（可能中间量被有意丢弃），但 7 处同时出现，建议逐个人审确认
> "是否漏掉一道应当落盘的判定"——尤其 `multi_objective_design.joint_ok` / `readout_fidelity.Q_ext` 涉及物理判据。

### 3.2 未定义名（4 处，均为低风险）
- `coupler_loop.py:167` `Tuple`、**`hybrid_design.py:120` `Tuple` / `:221` `List`**：
  仅出现在**函数签名注解**中，且三文件均含 `from __future__ import annotations`
  → 注解在运行时是字符串、**不触发 NameError**；仅破坏 `mypy`/静态类型检查。LOW（卫生债）。
- `design_loop.py:362` `json_report`：**真实前向引用**——`if __name__=="__main__"` 块在
  模块顶部（360 行）调用 `json_report`，但其 `def` 在 365 行（更下方）。
  作为**模块导入**时该块跳过、无碍；但**直接 `python design_loop.py` 运行会 NameError 崩溃**。
  → 把 `json_report` 定义上移到 `__main__` 块之前即可。LOW（仅演示入口路径）。

### 3.3 f-string 空占位（2 处，无害代码味）
`qeda_topology.py:82`、`solver_writer.py:367`：f-string 无 `{}` 占位符，等价于普通字符串。
无害，但属"误用 f 前缀"代码味。LOW。

### 3.4 整仓跨引用死代码候选（84 → 非真死，需澄清）
自研 AST 初扫标记 84 个"模块级 def 整仓无其他 .py 引用"。经核查：
- 大量是**动态派发目标**（orchestrator / registry / `run_demo` / `__main__` 通过字符串或基类调用），
  静态名字搜不到 ≠ 未用。
- `MODULE_MAP.md`（09-14 P1 已落地）已明确标注 loop 家族重复膨胀点，
  相关"重复"模块是**已知多副本、非死代码**，收敛计划见其 §3。
- **结论**：84 候选**不可自动判定为死代码**，不应批量删除；真死代码以 §3.1 的 7 处 pyflakes 确认项为准。

---

## 4. 覆盖（Coverage）

### 4.1 模块被引用情况
- **51/54** 模块被 `lda_design` / `lda_chain` / `lda_l1` / `lda_harness` / 顶层 `run_*.py` smoke 显式 import 或动态引用。
- **3 个独立校验脚本无 CI 护栏**：
  | 模块 | 性质 | 风险 |
  |---|---|---|
  | `calibrate_kappa_grid.py` | κ 网格标定脚本（`python` 直跑） | 🟡 验收逻辑无自动化门，回归靠人工 |
  | `verify_voxel_pipeline.py` | 体素化双 PASS 验收脚本 | 🟡 同上（文档称"双 PASS 逐位一致"，但未接 smoke） |
  | `verify_waveguide_2d.py` | 真 2D 波导验收脚本（v1.0 保留参考） | 🟡 同上；且被标"保留参考"，可能已冻结 |

> 这 3 个非"死代码"，而是**独立验收入口**；但其正确性仅靠人工运行保证，
> 与全库"CORE_SMOKES=173 + 56 锚"的强护栏叙事不一致。建议各补一道最小 smoke（调 `main()` 断言返回 PASS）。

### 4.2 既有护栏有效性（与 09-14 复评一致）
- 沙箱 guard smoke 5/5、隐式契约结构断言 smoke、计数护栏动态推导均已落地，未退化。
- 本评审四维度不与既有护栏冲突，属增量卫生补强。

---

## 5. 与 09-14 复评的增量

| 项 | 09-14 复评 | 本次 P0-1 |
|---|---|---|
| 导入健康 | 未覆盖 | 🟡 34 未用 import（低风险）、0 wildcard/0 断链/0 语法错 |
| 异常路径 | 仅抽验 `sandbox` | 🔴 `coupler_loop:81` 静默传 `None`；10 静默 / 21 总数 |
| 死代码 | 仅 `_TRACE`/空 `import torch`（已清） | 🟡 7 未用局部变量（疑似丢算）+ 前向引用 `json_report` |
| 覆盖 | "被 ~64 smoke 引用"定性 | 量化 51/54 + 3 独立脚本无 CI 护栏 |

---

## 6. 优先级行动清单

| 优先级 | 项 | 位置 | 动作 | 风险 |
|---|---|---|---|---|
| **P1** | 拟合失败静默传 `None` | `coupler_loop.py:81` | 改显式异常 / `(ok,val)` 元组，调用方强制判空 | 🔴 中高 |
| **P1** | 3 个验收脚本无 CI 门 | `calibrate_kappa_grid`/`verify_voxel_pipeline`/`verify_waveguide_2d` | 各补最小 smoke 断言返回 PASS | 🟡 中 |
| **P2** | 静默吞异常加日志 | §2.1 所列 9 处（除 sandbox 清理） | 至少 `logging.warning` 记录根因 | 🟡 低 |
| **P2** | 7 处"赋值未用"局部变量逐个人审 | §3.1 | 确认是否漏判据；是则补落盘，否则删 | 🟡 低 |
| **P2** | `json_report` 前向引用 | `design_loop.py:362` | 定义上移到 `__main__` 前 | 🟡 低（仅演示入口） |
| **P3** | 34 未用 import 删除 | §1.1 | `pyflakes` 驱动一次性清理 | 🟢 零行为风险 |
| **P3** | typing 注解未定义名 + f-string 空占位 | §3.2/§3.3 | 补 `from typing import` / 去多余 f | 🟢 卫生债 |

---

## 7. 评审结论

`lda_agent` 的**红线纪律与安全姿态（09-14 已根治项）在本次四维度扫描下无退化**：
无 wildcard import、无断链/语法错、无 `bare except`、无 `shell=True`/`eval`/`exec`。
主要增量风险集中在**工程卫生层**：

1. **唯一需止血的是 `coupler_loop.py:81`**——拟合异常静默返 `None`，会向上游传脏值；
2. **3 个独立验收脚本无 CI 护栏**，与全库强护栏叙事不一致，建议补最小 smoke；
3. 34 未用 import + 7 未用局部变量 + 前向引用属低风险债，可一次性美容清理，零行为风险。

> 附：本评审纯静态、未改代码。可执行 §6 的 P1/P2 项——
> 首推修 `coupler_loop:81` + 给 3 验收脚本补 smoke（两处均小改、低风险、对"主权可验货"叙事价值高）。
> 原始证据：`_p0_pyflakes.txt`（pyflakes 全量输出）、`_p0_review_out.json`（AST 扫描结构化结果）。

---

## 8. P1 修复状态（2026-09-16 已落地 · v0.9.79）

两项 P1 已全部修复并实跑验证，零回归：

- **P1a · `coupler_loop._beta_from_bidi_fit` 静默异常**：补 `import logging` + 模块 `_log`，将
  `except Exception: return None` 改为 `_log.warning("β 双向拟合失败（least_squares 异常）：%r；…")`
  后返 None。调用方 `_run_dc` 已对 `None` 做 fail-closed（「β 提取失败」判 FAIL），**未改签名、未改判决**。
- **P1b · 3 独立验收脚本补 CI 护栏并登 core**：新增 `run_verify_waveguide_2d_smoke.py` /
  `run_verify_voxel_pipeline_smoke.py` / `run_calibrate_kappa_grid_smoke.py`（各 3 判据，均 3/3 PASS、RC=0，
  纯 numpy、零 A 级·DEVSIM 依赖、无权豁免），注册进 `CORE_SMOKES`（CI core **173→176**）。

验证门禁（全绿）：
- `CORE_SMOKES` = **176**
- `run_count_consistency_smoke` → **11/11 OK**（含 `test_ci_core_count_matches_readme_top`）
- `run_ci_coverage_gate_smoke` → **6/6 PASS**（189 发现 / 176 core / 18 豁免 / 0 孤儿，反向测试 OK）
- 3 个新 smoke 各 **3/3 PASS**

README 同步：当前账本 `CI core 173 条`→`176 条`；新增 **v0.9.79** 当前版本行（v0.9.78 降上一版）。
pyflakes 复检 `coupler_loop.py`：仅 4 处预先存在的未用 import（非本改动引入），P2/P3 项未动。
