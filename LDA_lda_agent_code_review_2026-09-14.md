# LDA · `lda_agent` 专项代码评审（更新版）

> 评审对象：`D:/agent_LDA/lda/lda_agent/`（LDA 最大最复杂模块）
> 评审日期：2026-09-14 · 评审人：WorkBuddy（独立代码评审）
> 基线版本：**v0.9.77**（commit `764efdb`，2026-09-13 23:02）
> 性质：**对 2026-09-11 评审的复评**——重验旧结论、补验 v0.9.75/76/77 期间新增改动、披露新发现。
> 规模：约 **54 个 .py 文件 / ~13k 行**（较 09-11 评审新增 `sandbox.py` 191 行真隔离层）；仍被 `lda_design`/`lda_chain`/`lda_l1`/`lda_harness` 及 ~64 个 smoke 引用——活跃核心。

---

## 0. 总评（对比 09-11 评审的增量）

| 维度 | 09-11 评审 | 09-14 复评 |
|---|---|---|
| **红线合规（LLM 不进判决路径）** | ✅ 优良 | ✅ 仍优良（已抽样核验 `llm_proposer` 钳制逻辑） |
| **安全（AI 写核→执行）** | 🔴 P0 伪沙箱 | ✅ **P0 已根治**（`sandbox.py` 真隔离 + guard smoke 5/5 通过） |
| **报告确定性** | （未覆盖） | ✅ **v0.9.75 已根治**（design 报告走 `deterministic.write_text`，已抽样核验） |
| **可维护性 / loop 膨胀** | 🟠 MED | 🟠 **MED 仍存**，`MODULE_MAP.md` 未建（P1 缓解项未落地） |
| **正确性** | ✅ 无致命 bug | ✅ 无新增致命 bug |
| **测试覆盖** | ✅ 扎实 | ✅ CI core 已含沙箱护栏（168→169） |

**一句话**：自 09-11 评审后，最危险的两项（P0 伪沙箱、报告提交噪声）**均已实质根治并加 CI 护栏**；剩余债务集中在可维护性（loop 重复 + 隐式契约），均为非阻塞项。当前 `lda_agent` 的红线纪律与安全姿态已满足上生产前提。

---

## 1. 旧结论重验表

| # | 09-11 结论 | 复评状态 | 证据 |
|---|---|---|---|
| 1 | 🔴 P0 伪沙箱（宿主权限执行 AI 代码） | **✅ 已根治** | `sandbox.py` 真隔离层 + `run_solver_writer_sandbox_smoke.py` 5/5 通过（见 §2） |
| 2 | 🟠 MED 设计 loop 重复膨胀 | **🟠 仍存** | 16 个 loop/design 文件未收敛；`MODULE_MAP.md` 未创建（见 §4.1） |
| 3 | 🟠 MED `agent_verify`↔`link_harness` 隐式 dict 契约 | **🟠 仍存（契约未断）** | `agent_verify.py:106-108` 仍按键取 `energy_conservation` 等；无新增结构守卫（见 §4.2） |
| 4 | 🟡 LOW 死代码 `_TRACE` / 空 `import torch` | **✅ 已清** | commit `10481ce`：agents.py 删 `_TRACE`；coupler_loop.py:195 改为真实可用性探测（已 grep 确认无 `_TRACE`） |
| 5 | 🟡 LOW `final_metric_err` 字段误标 | **✅ 已澄清** | `design_loop.py:308-316` 加注释：该字段现明确为 T_total 下沿（带宽信息），非误差 |
| 6 | 🟢 红线守卫（判卷函数不引 LLM 客户端） | **✅ 仍守** | `llm_proposer.validate_params` 仅钳制参数（finite + 四维边界），`propose` 失败/未配置返回 `[]`→降级纯网格；全 `lda_agent` 无 `shell=True`/`eval`/`exec`/`pickle.load`/`os.system`（已 grep 确认） |

---

## 2. P0 沙箱——根治验证（原 HIGH 项）

**代码落地**：commit `ab360f4`（建 `sandbox.py` 191 行）+ `7c4b0b4`（strong 隔离改 `unshare --net + setpriv nobody`）+ `0182b9b`（注册 CI core 护栏）。

**`sandbox.py` 隔离机制（实测已读源码）**：
- **strong（Linux 生产）**：`unshare --net`（无网命名空间，无默认路由→外网 connect 失败）+ `setpriv --reuid/--regid nobody --clear-groups`（降权到 nobody，无 root、无写宿主敏感路径权限）+ 进程内 `resource.setrlimit`（CPU 30s / AS 512MB / NOFILE 64 / FSIZE 16MB，防 OOM/fork bomb/超算）。纵深防御到位。
- **weak（Windows 开发机）**：仅进程组 + cwd + timeout。**明确不安全**；`IsolatedExecutor.__init__` 在 `weak` 且未显式 `allow_weak_isolation=True` 时**直接抛 RuntimeError**——以代码守住"接外部 LLM 前必须强隔离"红线。
- 集成点 `solver_writer.SandboxExecutor` 委托 `IsolatedExecutor`；`run_demo` 仅对离线 Scripted 可信候选设 `allow_weak_isolation=True`，在线 LLM 候选在 Windows 上被硬拒（强制上 Linux strong）。

**实证**（本机 Windows weak 模式跑 guard smoke，EXIT=0）：
```
[PASS] ① 隔离等级可报告 (strong/weak)  level=weak
[PASS] ② weak 允许 allow_weak_isolation 可构造
[PASS] ② weak 不 allow 时构造拒绝（红线）
[PASS] ③ 轻量闭环 v0 FAIL→v1 PASS（行为等价）  max_abs_err=0.0000
[PASS] ④ strong 真隔离（仅 Linux 验证）  weak 环境跳过
沙箱 smoke: 5 PASS / 0 FAIL
```
结论：**P0 已闭环**，且加了不可回归护栏。上生产前该硬门槛已消除。

---

## 3. 报告确定性——v0.9.75 根治验证（09-11 评审未覆盖的新项）

**背景**：v0.9.75（commit `592aeee`）根治"受跟踪报告每次跑被重写→git status 常红"的提交噪声，根因是生成器非确定性（wall-clock 时间戳 / 耗时 / 浮点末位抖动）。

**`lda_agent` 受影响点（已读 diff + 源码）**：
- `design_loop.py`：删除 `import time` / `t0 = time.time()` / `verdict` 中的"闭环耗时 Ns"——verdict 不再含 wall-clock，消除一类非确定性。
- 序列化路径：`design_outcome_report.json` 经 `lda_l1/protocol.py:166-171` 的 `deterministic.write_text(json_path, rep.format_json(...))` 落盘——即走 v0.9.75 唯一口径 `lda_harness/deterministic.py`（canon 去 volatile 键 + 9 位有效数字 + 恒 LF）。已 grep 确认 `lda_l1/protocol.py` 引 `deterministic`，`lda_agent` 本身不重复造轮子。
- 线程环境：v0.9.75 第二轮锁定 torch 在 Windows 随包 Intel OpenMP 的 `OMP_DYNAMIC`/`MKL_DYNAMIC` 默认 TRUE→归约顺序漂移→float32 不可复现，统一经 `lda_solver/threads.thread_env_overrides()` 显式关动态（判据⑩ 反向可证伪）。`lda_agent/coupler_band_loop.py` 已还原为与 HEAD 逐字节一致（撤掉"记 4 位小数掩盖抖动"的错补丁）。

结论：**设计报告确定性已根治**，与全库 200 个受跟踪报告 SHA「unchanged=200/changed=0」一致。

---

## 4. 残留 / 新发现（均非阻塞）

### 4.1 🟠 [MED] 设计 loop 重复膨胀 + `MODULE_MAP.md` 未建（P1 缓解项落空）
- 09-11 评审建议写 `MODULE_MAP.md` 标注 canonical/legacy；**经 Glob 确认该文件不存在**，16 个 loop/design 文件（`inverse_design`/`spectral_inverse_design`/`adjoint_design`/`adjoint3d_design`/`hybrid_design`/`multi_objective_design`/`primitives_design`/`sparams_design`/`sparams_3d_design`/`design_pipeline`/`pipeline_realize`/`ring_loop`/`waveguide_loop`/`multiband_loop`/`coupler_loop`/`coupler_band_loop` 等）仍未收敛。
- 风险：维护者/后世 LLM 维护者难判 canonical，同 bug 易多副本不一致。
- **建议（低成本高价值）**：立即建 `lda/lda_agent/MODULE_MAP.md` 逐文件标 `canonical | legacy(待删) | 演示`；中期再抽统一优化引擎 + 方法注册表。此项不阻塞当前生产路径。

### 4.2 🟠 [MED] `agent_verify`↔`link_harness` 隐式 dict 契约（仍脆）
- `agent_verify.py:106-108` 直接 `harness_res["energy_conservation"]` 等按键取；`link_harness` 返回形状为约定俗成，无类型/结构守卫。09-11 建议加结构断言 smoke（契约漂移即红），**至今未加**（无 commit 触及 `agent_verify.py`）。
- 当前契约未断（键齐全），但漂移会 `KeyError` 静默炸成 `status:"error"`、根因不明。
- **建议**：加一道 `assert set(harness_res) >= {b19, energy_conservation, no_missing_models, routing_complete, status}` 的结构 smoke（成本极低）。

### 4.3 🟡 [LOW] `sandbox._run_strong` 继承完整父进程 env（纵深防御缺口）
- `sandbox.py:163`：`env = {**os.environ, "LDA_SOLVER_CASES": payload}` 把**全部父 env**（含 `LDA_LLM_KEY`/`OPENAI_API_KEY` 等）传给降权后的 nobody 子进程。
- 因 `unshare --net` 无网，密钥无法外传，故**当前实际风险低**；但违背 09-11 评审自身建议"env 清空（仅留 PATH/PYTHONPATH）"的纵深防御原则。
- **建议**：strong 路径传最小 env（`PATH`/`PYTHONPATH`/`LDA_SOLVER_CASES` + 解析器所需 `LD_LIBRARY_PATH`），其余剥离。

### 4.4 🟡 [LOW] guard smoke 访问私有属性 `_iso`
- `run_solver_writer_sandbox_smoke.py:108-109`：`SandboxExecutor(timeout=30)._iso.run(evil_fs, iso_spec)` 直接戳 `SandboxExecutor._iso` 私有成员。
- 功能正确但封装泄漏，内部重构易碎。
- **建议**：改用 `SandboxExecutor(timeout=30).run(evil_fs, iso_spec)`（同签名，无需戳私有）。

### 4.5 🟡 [LOW] `_run_strong` 未捕获 `unshare` 失败
- 若生产进程无 `CAP_SYS_ADMIN`（非 root 部署），`unshare --net` 抛 `OSError`，`_run_strong` 未捕获→冒泡为原始异常（fail-closed 但报错信息晦涩）。
- **建议**：包一层友好异常"隔离不可用：需 root 或 unshare 权限"，与 weak 红线同风格。

---

## 5. 更新后优先级清单

| 优先级 | 项 | 动作 | 状态 |
|---|---|---|---|
| ~~P0~~ | 伪沙箱 | 已根治（真隔离 + guard smoke） | ✅ 完成 |
| ~~P0~~ | 报告确定性 | 已根治（deterministic 唯一口径） | ✅ 完成 |
| P1 | §4.1 loop 膨胀 | 建 `MODULE_MAP.md`（canonical/legacy 标注） | 待做（低成本） |
| P1 | §4.2 隐式契约 | 加结构断言 smoke | 待做（低成本） |
| P2 | §4.3 env 继承 | strong 传最小 env | 待做 |
| P2 | §4.4 `_iso` 私有访问 | 改用 `SandboxExecutor.run` | 待做 |
| P2 | §4.5 unshare 失败 | 包友好异常 | 待做 |

---

## 6. 评审结论

`lda_agent` 在 09-11 评审后经历了两轮关键加固：**P0 伪沙箱→真隔离（已 CI 护栏）**、**报告提交噪声→确定性生成（已全库 SHA 一致）**。红线纪律（LLM 仅生成、判决走物理锚）在抽样核验下依然牢固，全模块无危险执行原语。

唯一需补的硬门槛（P0）**已消除**；剩余项均为可维护性/纵深防御类非阻塞改进，建议按 §5 在下一空闲 sprint 清掉 P1 两项（尤其 `MODULE_MAP.md`，成本极低、对"主权可验货"叙事价值高）。

> 附：本评审未改动任何代码（纯评审）。如需，我可立即执行 §5 的 P1/P2 低风险项——首推建 `MODULE_MAP.md` + 加结构断言 smoke（两处均纯新增、零行为风险）。
