# LDA · `lda_agent` 专项代码评审报告

> 评审对象：`D:/agent_LDA/lda/lda_agent/`（LDA 最大最复杂模块）
> 评审日期：2026-09-11 · 评审人：WorkBuddy（独立代码评审）
> 模块规模：**53 个 .py 文件 / 12,813 行**；被 `lda_design`、`lda_chain`、`lda_l2`、`lda_harness` 及 64 个测试/smoke 文件引用（占 `lda/` 下 200 个 `run_*.py` 近 1/3）——**活跃核心，非孤儿代码**。

---

## 0. 总体结论

| 维度 | 评价 |
|---|---|
| **红线合规（LLM 不进判决路径）** | ✅ 优良，应锁定 |
| **安全（AI 写代码→执行）** | ⚠️ 中高危，demo 阶段，须在上生产前修复 |
| **可维护性 / 复杂度** | ⚠️ 设计 loop 重复膨胀，需收敛 |
| **正确性（已实证核查）** | ✅ 无致命 bug（一处疑似 bug 经复现证伪） |
| **测试覆盖** | ✅ 扎实（64 个 smoke 引用本模块） |

**一句话**：架构红线守得对、守得死，是当前 LDA 最具价值的工程纪律体现；主要短板在"AI 写核→沙箱执行"这一实验性模块的安全隔离名不副实，以及设计 loop 的代码重复膨胀。两者都不阻塞当前生产路径，但前者是**上生产前的硬门槛**。

---

## 1. 红线合规审查（正面 · 应锁定）

逐项核对"生成与判决分离"纪律，结论：**LLM 仅产候选，判决全走确定性物理锚，红线未被触碰。**

- `orchestrator.py` / `agents.py`：声明"无 LLM、无 GUI、无状态"；四 Agent 经确定性 `AgentMsg` 协作，调度仅做黑板维护。✅
- `llm_proposer.py` / `redteam_proposer.py`：
  - 只输出候选**参数**（`_PARAM_BOUNDS` 四维钳制：越界/非有限数直接丢弃，零重试）。
  - 判卷交给 `proposal_compiler` 的四锚死标量（S1/S2/S5/S7），**LLM 无法跳过锚**。
  - 降级语义正确：未配置/调用失败/输出垃圾 → 返回空列表，调用方回退纯网格（零依赖优雅降级）。✅
- `agent_verify.py`：验证 Agent 用物理定律锚——①无源网络无增益 `|T|≤1`（tol=1e-9）②无缺模型器件 ③布线完整；并上提 B19 物理定律 harness + 级联乘法性死标量锚。无 LLM。诚实标注"链路级无实证锚，不判 E 题"。✅
- `solver_writer.py`：LLM **写求解核代码**（非返回标量），但 PASS/FAIL 由 ORACLE（tmm 解析解）死标量比对决定，与"谁写的代码"无关。✅
- `design_loop.py`：`_run_adjoint` / `_run_sparams3d` 验收均为死标量（`max_rel_err≤0.15`、`improvement≥1.5`）。✅

> **建议**：把上述"LLM 仅生成、判决走锚"作为不可回归的护栏写入 `run_redteam_llm_smoke` / `run_proposal_compiler_smoke` 的断言（目前纪律靠文档+约定，建议加一道"判卷函数不引用任何 llm 客户端对象"的静态/导入级守卫，防后世误改）。

---

## 2. 关键发现（按严重度）

### 🔴 [HIGH] `solver_writer.py`："沙箱"名不副实，AI 生成代码以宿主全部权限执行

**位置**：`solver_writer.py:214-280` `SandboxExecutor.run`

**问题**：候选代码经 `subprocess.run([sys.executable, drv_path, ...], cwd=tmp)` 在子进程执行，但**无任何 OS 级隔离**：

- 候选 `import candidate as C` 后，**候选的顶层代码与 `fn` 调用均以宿主用户完整权限运行**——可 `import os/shutil/socket`、`open()` 任意路径、读写 `~/.ssh`、读 `D:/agent_LDA/.secrets/`、经网络外传、删除文件。
- `timeout=120s` 仅能在**挂死**时杀进程，对**破坏性/外传**动作毫无防护（动作在毫秒内完成，超时来不及）。
- 文档声称"仅能访问 numpy/math"——**此描述不实**，属 aspirational。Python 导入机制默认可及全部标准库。
- `tempfile.mkdtemp` 默认权限仍对同用户可读，且子进程 cwd 即该临时目录，但无只读根、无降权、无 seccomp/landlock、无禁网。

**为何此刻是"中高危"而非"立即爆炸"**：该模块目前是 `--demo` 自包含的离线闭环（`python -m lda_agent.solver_writer`，候选是脚本内置 v0/v1），**未接入生产验证链路**（生产判决走 `lda_harness` 53 锚）。但本模块的存在意义正是"AI 写核→跑→验→重写"，是**最可能被提升为生产能力的实验性路径**；一旦接外部 LLM 端点或并入 CI，当前伪沙箱会直接暴露。

**推荐修复（按成本递增）**：
1. 【最低成本·必须】删除不实文档措辞，改为诚实声明"以宿主权限在临时子进程运行，仅限可信 LLM 端点/本地使用"。
2. 【推荐】子进程加 `preexec_fn` 降权（去 CAP、setuid nobody）+ `env` 清空（仅留 `PATH`/`PYTHONPATH` 指向受限）+ `cwd` 指向不可写 tmpfs。
3. 【最强】用 `nsjail` / `firejail` / Docker `--network none --read-only` 包一层；或调 `lda_cuda_venv` 之外的隔离 runtime。候选 `numpy/math` 已够用，无需完整 site-packages。

### 🟠 [MED] 设计 loop 重复膨胀，模块"最大最复杂"的主因

**现象**：约 16 个"设计闭环/逆设计"类文件，且彼此语义重叠，难以判定哪个是 canonical：

```
design_loop.py        coupler_loop.py        coupler_band_loop.py
ring_loop.py          waveguide_loop.py      multiband_loop.py
inverse_design.py     spectral_inverse_design.py
adjoint_design.py     adjoint3d_design.py
hybrid_design.py      multi_objective_design.py  primitives_design.py
sparams_design.py     sparams_3d_design.py
design_pipeline.py     pipeline_realize.py
```
外加 ~10 个"package"构建器（`wdm_coupler/wdm_system/ring_adddrop/splitter_readout/mixed_system/...`）。

**风险**：
- 新成员（或后世 LLM 维护者）无法判断 `inverse_design` vs `spectral_inverse_design` vs `adjoint_design` 的取舍，易在错误的副本上改。
- 同一 bug 可能在多份副本各自存在/修复不一致。
- 与 LDA"主权可验货"叙事冲突：重复面越大，验证覆盖面越难说清。

**推荐**：① 抽一个统一的优化引擎（后端可插 `numpy/numba`）+ **每器件/每方法一份配置注册表**（`method=adjoint|sparams3d|inverse|...`），把上述 16 个文件收敛为 `engine/ + methods/*.py + registry.py`；② 在收敛前先写一份 `MODULE_MAP.md` 标注"canonical vs legacy（待删）"，防止误用。

### 🟠 [MED] `agent_verify.py` ↔ `lda_chain.link_harness` 隐式契约

**位置**：`agent_verify.py:89-93` 调 `link_physics_harness(ctx.link, sim, ctx.blocked_nets)` 并直接取 `harness_res["b19"]["status"]`、`harness_res["energy_conservation"]` 等键。

**核查结果**：`link_harness.py:138-149` 确实返回 `b19/energy_conservation/no_missing_models/routing_complete/status` 五键，**当前契约一致，未断裂**。

**残留风险**：契约是"约定俗成"的 dict 形状，无类型/结构守卫。`link_harness` 一旦增删键或改嵌套，`agent_verify` 会 `KeyError` 静默炸（被 `BaseAgent.handle` 包成 `status:"error"`，链路判 FAIL 但根因不明）。

**推荐**：已有 `run_link_m3_smoke.py` 绑定两者（良好），建议**额外**加一道结构断言 smoke：`assert set(harness_res) >= {b19, energy_conservation, no_missing_models, routing_complete, status}`，契约漂移即红。

### 🟡 [LOW] 死代码 / 空导入

- `agents.py:18` 模块级 `_TRACE: List[Dict] = []` 声明后**全模块无任何 append/read**——早期 tracing 设计遗留，可删。
- `coupler_loop.py:195` `import torch  # noqa: F401`——`F401` 即"导入未使用"，这是一行**无效导入**（既不检查可用性也不做事），应删；真正用到 torch 的是 `:322` `import torch as _torch`（懒加载，可接受）。

### 🟡 [LOW] 报告字段语义误标（`design_loop._run_sparams3d`）

**位置**：`design_loop.py:318-319`

```python
final_metric_err=float(min(p["T_total"] for p in pts)),
final_max_metric_err=float(max(p["T_total"] for p in pts)),
```

字段名 `*_metric_err` 实为 **T_total 的最小/最大值（吞吐），并非误差**。下游若按"误差"消费会误读。建议改名 `final_metric_min`/`final_metric_max` 或加注释澄清。

---

## 3. 已实证核查项（避免误报）

- **疑似 bug：`_run_sparams3d` 的 `verdict` 三元拼接在 `accepted=False` 时重复 `vr["verdict"]`** → 经最小复现 **证伪**：Python 条件表达式把两侧 `+` 都纳入分支（`(A+f1) if c else (A+f2)`），输出仅单次，非 bug。不报。
- **`agent_verify` ↔ `link_physics_harness` 契约** → 键齐全，未断裂（见 §2 MED）。
- **红线"LLM 不进判决路径"** → 四层（proposer/redteam/verify/solver_writer）均合规，未见 LLM 对象渗入判卷函数（见 §1）。

---

## 4. 改进优先级清单

| 优先级 | 项 | 动作 | 成本 |
|---|---|---|---|
| P0（上生产前必做） | §2 HIGH 伪沙箱 | 至少做"诚实文档+降权+禁网"；接外部 LLM 前必须真隔离 | 中 |
| P1 | §2 MED loop 重复膨胀 | 写 `MODULE_MAP.md` 标注 canonical/legacy；中期内引擎+配置收敛 | 中-高 |
| P1 | §2 MED 隐式契约 | 加结构断言 smoke，契约漂移即红 | 低 |
| P2 | §2 LOW 死代码/`import torch` 空导入 | 删除 `_TRACE`、`:195` 空导入 | 低 |
| P2 | §2 LOW 字段误标 | 改名/注释 `final_metric_err` | 低 |
| P2 | §1 红线守卫 | 加"判卷函数不引用 llm 客户端"静态守卫 | 低 |

---

## 5. 评审结论

`lda_agent` 是 LDA 工程纪律的"高光模块"——**生成与判决分离的红线在四层全部兑现，且测试覆盖扎实（64 个 smoke 引用）**。当前不需要重构性改动即可守住生产路径（生产判决走 `lda_harness` 53 锚，本模块未入判决关键路径）。

唯一**上生产前的硬门槛**是 `solver_writer` 的伪沙箱：它今日是 demo，却承载着"AI 写核"这一 LDA 白皮书核心 thesis，一旦被提升为生产能力，当前隔离水平会直接暴露宿主。建议在其被任何外部 LLM 端点或 CI 引用前，完成 P0 隔离。

> 附：本评审未改动任何代码（纯评审）。如需，我可立即执行 P2 的低风险清理（删 `_TRACE`、空 `import torch`、字段改名），并就 P0 沙箱隔离给出可直接落地的 `nsjail`/降权实现方案。
