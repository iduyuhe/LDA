# LDA · `lda_agent` 专项代码评审 —— 第三轮闭合报告（2026-09-16）

> 范围：`lda/lda_agent/`（54 个 .py，约 1.1 万行）+ `lda/run_solver_writer_sandbox_smoke.py`
> 结论：**三轮评审遗留全部闭合** —— P0-1 深化版的 P2/P3 卫生债清零、09-14 复评的 §4.3/4.4/4.5 安全纵深三项落地、新增 3 条回归护栏（含反向测试）。
> 定性：**零行为变更**（纯卫生清理 + 纵深防御加固 + 测试增强），三分类账本 **63/3/18（75.0%）不变**。

---

## 1. 三轮评审脉络与本轮定位

| 轮次 | 报告 | 结论 | 遗留 |
|---|---|---|---|
| 09-11 | 首轮评审建议 | 伪沙箱 / 报告确定性 / MODULE_MAP / 契约守卫 | 建议未落地 |
| 09-14 | `LDA_lda_agent_code_review_2026-09-14.md` | P0 伪沙箱**已根治**（真隔离 + guard smoke）；P1(a) MODULE_MAP / P1(b) 契约 smoke | **§4.3/4.4/4.5 三项 P2 未做** |
| 09-16 | `LDA_lda_agent_code_review_P0-1_2026-09-16.md` | P0-1 导入健康/异常/死代码/覆盖专项 | **P2 三项 + P3 卫生债未落地** |
| **09-16（本报告）** | **第三轮闭合** | **上述全部闭合 + 新增护栏** | 见 §7 |

**核实方式**：本轮以 `pyflakes==3.4.0` 全量复扫 + 逐项代码级人审 + 实跑守卫取证，**不以报告自述为准**（trust but verify）。

---

## 2. 本轮闭合清单（总览）

| # | 来源 | 项 | 处置 | 证据 |
|---|---|---|---|---|
| 1 | 09-14 §4.3 | `_run_strong` 继承**完整父进程 env**（含 `LDA_LLM_KEY`/`OPENAI_API_KEY`） | strong 路径改传**最小 env 白名单** | 护栏 ⑤ |
| 2 | 09-14 §4.4 | guard smoke 戳私有 `SandboxExecutor._iso` | 改用**公开 `SandboxExecutor.run`** | 护栏 ⑦ |
| 3 | 09-14 §4.5 | `_run_strong` 未捕获 `unshare` 失败（裸抛 `OSError`） | 包**友好 `RuntimeError`**（fail-closed） | 护栏 ⑥ |
| 4 | 09-16 P0-1 P2 | **9 处**静默吞异常（`except: pass`） | 补 `logging.warning`，**控制流不变** | `pyflakes` + 人审 |
| 5 | 09-16 P0-1 P2 | **7 处**赋值未用局部变量 | 人审判定为**冗余残留计算**（非漏判据）→ 删除 | 见 §4.2 |
| 6 | 09-16 P0-1 P2 | `design_loop.py` **前向引用** `json_report` | 定义上移至 `__main__` 之前 | — |
| 7 | 09-16 P0-1 P3 | **47 条** pyflakes 告警 | **清零**（见 §5） | `pyflakes` rc=0 |
| 8 | 本轮新增 | 回归护栏 ⑤⑥⑦ + 反向测试 | smoke 五判据 → **八 PASS** | 见 §6 |

---

## 3. 安全纵深三项（09-14 §4.3 / §4.4 / §4.5）

### 3.1 §4.3 · strong 路径最小 env（纵深防御）

**原状**：`sandbox.py:_run_strong` 用 `env = {**os.environ, "LDA_SOLVER_CASES": payload}`，把**全部父 env**（含 LLM 密钥）交给降权后的 `nobody` 子进程。因 `unshare --net` 无网，密钥无法外传 ⇒ **实际风险低**，但违背「纵深防御」（有网即泄露）。

**处置**：新增模块级 `_minimal_env(payload)` + 白名单 `_STRONG_ENV_KEEP`：
```
PATH / PYTHONPATH / LD_LIBRARY_PATH / LANG / LC_ALL / LC_CTYPE / TMPDIR / TMP / TEMP
+ LDA_SOLVER_CASES
```
实测剥离效果：`LDA_LLM_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` **均不在子 env**，`PATH` 保留。

### 3.2 §4.4 · 去掉私有属性访问

**原状**：`run_solver_writer_sandbox_smoke.py:108-109` 直接戳 `SandboxExecutor(timeout=30)._iso.run(...)` —— 封装泄漏、内部重构易碎。
**处置**：改 `SandboxExecutor(timeout=30).run(...)`（同签名公开 API，`solver_writer.py:233` 已委托 `_iso.run`）。**行为等价**（④ strong 判据照旧）。

### 3.3 §4.5 · `unshare` 失败包友好异常

**原状**：生产进程若缺 `CAP_SYS_ADMIN`（非 root 部署），`unshare --net` 抛 `OSError` 冒泡为原始异常（fail-closed 但报错晦涩）。
**处置**：`_run_strong` 内 `try/except OSError` → `raise RuntimeError("隔离不可用：需 root 或 unshare 权限（CAP_SYS_ADMIN）…") from e`，与 weak 红线**同风格**。

---

## 4. P0-1 深化版的 P2 三项

### 4.1 静默吞异常 → 补日志（9 处，控制流不变）

| 文件 | 函数 | 语义 |
|---|---|---|
| `quantum_design.py` | `_ensure_path` | sys.path 注入失败告警 |
| `inverse_design.py` | `_ensure` | 同上 |
| `qubit_readout_chain.py` | `_ensure_path` | 同上 |
| `multiqubit_readout.py` | `_ensure_path` | 同上 |
| `design_pipeline.py` | `_cuda_ok` | CUDA 可用性探测失败告警 |
| `sandbox.py` | `_stage` | chmod 放宽失败告警（降权 nobody 可能读不到候选） |
| `ring_adddrop.py` | 摘要提取 | 提取失败告警 |
| …（其余 2 处同类） | | |

⚠️ **纪律**：仅**新增日志**，**不改控制流**（原吞异常后继续的语义保持）——避免引入行为回归。

### 4.2 未用局部变量（7 处）· 人审结论：**无漏判据**

逐个人审，**全部为「冗余/残留计算」**，非「算了没判」的真 bug：

| 变量 | 判定 |
|---|---|
| `gc_design.pts` / `pipeline_realize.n_real` / `wdm_splitter.w` | 中间量，结果已由后续 `checks` 独立覆盖 |
| `multi_objective_design.joint_ok` | 与 `passed` **语义等价**（同条件重复计算） |
| `splitter_readout.dc_ir` | 已被其它判据覆盖 |
| `readout_fidelity.Q_ext` | 中间量，最终判据用另一表达式 |
| `tunable_wdm.realloc_ok` | 与 `passed` 语义等价 |

⇒ 安全删除（零行为变更）。

### 4.3 前向引用

`design_loop.py`：`__main__` 块在 `json_report` **定义之前**就调用它（运行时不炸，因 `__main__` 在模块末尾执行，但静态检查报 `undefined name`）。**处置**：把 `json_report` 定义上移到 `__main__` 块之前，语义不变。

---

## 5. P0-1 深化版的 P3 卫生债 —— pyflakes 47 → 0

**复扫命令**：`python -m pyflakes lda/lda_agent`（`pyflakes==3.4.0`）

| 类别 | 条数 | 处置 |
|---|---|---|
| `imported but unused`（普通） | 31 | 删除 |
| `imported but unused`（**可用性/副作用探测**） | 2 | **保留** + 改**显式引用** `_ = torch`（`coupler_loop.py:210/355`，探测语义不可删） |
| `undefined name`（`typing.Tuple` / `List`） | 3 | 补 `from typing import ...`（`coupler_loop:174`、`hybrid_design:120/221`） |
| `undefined name`（前向引用） | 1 | 见 §4.3 |
| `local variable assigned but never used` | 7 | 见 §4.2 |
| `f-string is missing placeholders` | 3 | 去掉多余 `f` 前缀（`qeda_topology:82`、`solver_writer:367`、`wdm_system:161`） |
| **合计** | **47** | **→ 0（rc=0，输出空）** |

**编译校验**：54 文件 `py_compile` **0 失败**。

---

## 6. 验证矩阵（本轮实跑）

| 守卫 | 结果 | 关键判据 |
|---|---|---|
| `run_p0_count_guard_sync_smoke` | **6/6 PASS** | 三分类真值 ≡ 四处硬编码护栏（含反向篡改测试） |
| `run_count_consistency_smoke` | **11/11 PASS** | README 计数/版本一致性 |
| `run_three_class_consistency_smoke` | **4/4 PASS** | README ≡ harness ≡ 端点 = **63/3/18**（含反向篡改） |
| `run_ci_coverage_gate_smoke` | **6/6 PASS** | 无静默缺口（含反向撤登记测试） |
| `run_maturity_baseline_smoke` | **M1–M5 PASS** | strict=63 / degraded=3 / self_certified=18，和=84 |
| `run_webui_verification_ledger_smoke` | **15/15 PASS** | 端点三分类 + VMM 渲染接线 |
| `run_solver_writer_sandbox_smoke` | **8/8 PASS** | ①–④ 原判据 + **⑤§4.3 ⑥§4.5 ⑦§4.4** |
| `run_agent_verify_link_contract_smoke` | **7/7 PASS** | 契约结构守卫（§4.2） |
| `run_optional_import_guard_smoke` | **16/16 PASS** | 模块级硬依赖=0（生权红线） |
| `run_b5b7_rollback_floor_smoke` | **ALL PASS** | B5/B7 回退下限 = 守则锚 −40 dB |
| `run_d_criterion_smoke` | **10/10 PASS** | 已接线严格候选 0 道代数恒等 |
| `run_report_determinism_smoke` | **10/10 PASS** | 报告字节确定性 + 线程环境关闭动态调整 |
| `run_benchmark_falsifiability_smoke` | **13/13 PASS** | verified=63 · 按题标注 84/84 · 路径②口径一致 |

**新护栏反向测试（§6.1）**：把 §4.3/§4.5 修复临时还原 ⇒ ⑤ 判据返回 `False`、⑥ 裸抛 `OSError`（护栏**确实会响**，非假绿）；⑦ needle 拼接避免自指（真实源码不含私有串）。

**静态检查**：`pyflakes==3.4.0` rc=0（输出空）· `py_compile` 54 文件 0 失败。

**账本不变性**：三分类 **63 / 3 / 18（75.0%）** 与 README ≡ harness ≡ 端点 ≡ ledger 四方一致 —— 证明本轮**零行为变更**。

---

## 7. 残留与后续

| 优先级 | 项 | 状态 |
|---|---|---|
| ✅ 已闭合 | P0-1 的 P2/P3 · 09-14 的 §4.3/4.4/4.5 · §4.1 MODULE_MAP · §4.2 契约 smoke | 本轮/前轮落地 |
| ✅ 已闭合 | `run_self_certified_lock_smoke.py`（自证桩锁定机器断言） | 本轮落地：棘轮上限 `≤18` + 无锁定原因 = 0 + 反向测试；登 `CORE_SMOKES`（CI core 177→178，发现 smoke 190→191） |
| 🟡 观察 | `lda_agent` loop 家族重复膨胀（§4.1 缓解项已建图，未做结构性合并） | 结构性重构，非阻塞 |
| 🔴 业务阻塞 | E1/E3–E7 共 6 道真候选 + B7 3D 彻底闭合 | 卡 T2 实测通道（业务 KPI） |

**结论**：`lda_agent` 专项评审的**全部技术闭合项已清零** —— 代码卫生（pyflakes 47→0）、安全纵深（§4.3/4.4/4.5）、回归护栏（⑤⑥⑦ 含反向测试）三项全绿，且**零行为变更**（三分类 63/3/18 不变）。
