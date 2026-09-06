# LDA · CI 门禁覆盖审计与防漏机制

- **日期**：2026-09-06（v0.9.41）
- **触发**：D 赛道（CPO 硅光 I/O）扩展交付后跑全量 `--tag core` 回归，97 条全绿。
  全绿之后追问「这 97 条是不是全部」⇒ 查出第四处潜伏断裂。
- **结论**：**全绿只覆盖「已接线」的部分**。97 条全绿时，有 36 个 smoke 从未进过门禁，
  其中包括研发生产系统的主护栏 `run_production_smoke.py` 与 4 条**锚 smoke**。

---

## 一、血案：`run_production_smoke.py` 从未进 CI

| 项 | 内容 |
|---|---|
| 建成时间 | M3（v0.9.39） |
| 文档记载 | `lda_production_system_design.md`、`production_plan.py` 注释、项目 memory —— **三处均写「进 CI 防回归」** |
| 实际情况 | `run_ci_regression.py` 中**零引用**；`_discover_all()` 能发现（走 `--tag all`），但 CI 真门禁是 `--tag core`，**不在 `CORE_SMOKES`** |
| 裸奔范围 | 研发生产系统四赛道 17 个任务 + D-67 能量守恒 / Q-D67 密钥率上界 / P-CPO 间距几何下界三道反向测试 |
| 定性 | **「标签≠行为」**——文档说有门禁 ≠ 门禁真在跑。与 Q-D67 反向测试 patch 错入口属同一类病：**以为的护栏所在处 ≠ 真正的护栏所在处** |

**根因**：`_discover_all()` 只负责发现，没有任何机制要求「新 smoke 必须进 core 或显式声明不进」
⇒ 漏接线成为**静默默认**，且无人复核。

### 同类病史（本项目已发生三处）

| # | 断裂 | 起因 | 发现方式 |
|---|---|---|---|
| 1 | `run_system_types_smoke.py` 等值断言 `types == [3 类]` | M2 加 `sensor_frontend` 时未改断言 | 本轮主动排查 |
| 2 | 定价归档只覆盖 58/75 条 | 货架 58→75 全程未同步 `shelf_pricing.py` | CI 变红 |
| 3 | `run_production_smoke.py` 从未进 CI | 建成时只写文档未登记回归集 | 全量回归后追问「97 是不是全部」 |
| 4 | 36 个 smoke 从未进门禁 | 只有发现机制，没有分类机制 | 逐项实测 |

| 5 | README 对外账本计数 97 ≠ 实际 117 | 接入 19 条 smoke 后未同步「当前账本」行 | **护栏抓到**（见下节） |

**共同模式**：**扩库/加件类改动只同步了「入口」，没同步「派生表 / 登记册」**。

---

## 二、36 个孤儿 smoke 逐项实测

方法：子进程逐个实跑，per-script 超时 60s；对超时项延长至 300s 复测，
以区分「慢」与「卡死」（二者排除理由完全不同——慢可豁免，卡死是缺陷）。

### A 组：快（<5s）—— 真门禁缺口，无权豁免

| smoke | 实测 | 说明 |
|---|---|---|
| `run_mzi_anchor_smoke.py` | 1.08s | **锚**：MZI FSR × 物理定律锚 B20 死标量比对（unittest 6 断言） |
| `run_qres_anchor_smoke.py` | 1.25s | **锚**：qubit-resonator（unittest 7 断言） |
| `run_fluxonium_anchor_smoke.py` | 1.16s | **锚**：fluxonium（unittest 13 断言） |
| `run_transmon_double_verify_smoke.py` | 0.59s | **锚**：transmon 双路互证 |
| `run_qeda_depth_smoke.py` | 0.33s | QEDA 纵深三件套（含驱动强场/串扰简并负例） |
| `run_qubit_resonator_smoke.py` | 0.28s | 求解器级（含色散区失效负例） |
| `run_mixed_system_smoke.py` | 0.30s | 光-量混合巨型系统（2 正例 + 3 负例） |
| `run_ir_solve_smoke.py` | 0.30s | L0/L3 直接消费 IR 真值计算 |
| `run_wdm_coupler_smoke.py` | 0.30s | ⚠️ 文件头旧注称其「重」→ **实测 0.30s，属过时排除** |
| `run_wdm_coupler_wl_smoke.py` | 0.30s | 同上 |
| `run_wdm_coupler_grid_smoke.py` | 0.29s | 同上 |
| `run_wdm_depth_smoke.py` | 0.30s | 同上 |
| `run_wdm_system_smoke.py` | 0.30s | 同上 |
| `run_api_v1_smoke.py` | 0.77s | v1 API：租户隔离 / 认证 / 插件安全 / license seam |
| `run_data_layer_smoke.py` | 1.11s | 多用户数据层：隔离 / API Key / 用量计量 |
| `run_ecosystem_review_smoke.py` | 0.31s | 生态共建社区评审流 |
| `run_ecosystem_review2_smoke.py` | 0.33s | 同上 |
| `run_ecosystem_review3_smoke.py` | 0.31s | 同上 |

**合计 9.6s**，全部：纯 numpy（无 torch/numba/cupy/meep/tidy3d/scipy）、失败会 `return 1`
（经查 9 个 print 风格脚本均含退出码分支，**非空壳**）、结果 PASS。

> 🔴 其中 **4 条锚 smoke 不在门禁内 = 锚失真无警报**。锚失真是本项目最危险的失败模式：
> v0.9.10 漏算 3.0103dB 曾在 84 条全绿下溜过。

### B 组：慢 5–60s —— 重仿真，登记豁免

| smoke | 实测 | 理由 |
|---|---|---|
| `run_design_outcome_smoke.py` | 59.70s | 设计闭环全链路 |
| `run_adjoint_loop_smoke.py` | 57.12s | 伴随优化迭代循环 |
| `run_coupler_design_smoke.py` | 55.60s | 耦合器参数扫描反解 |
| `run_adjoint_design_smoke.py` | 40.63s | 伴随法设计 |
| `run_shape_design_smoke.py` | 32.69s | 形状优化迭代 |
| `run_spectral_design_smoke.py` | 27.58s | 谱响应设计扫描 |
| `run_adjoint3d_smoke.py` | 27.16s | 3D 伴随仿真 |
| `run_sparams_smoke.py` | 25.67s | FDTD 分束仿真 |
| `run_ir_smoke.py` | 20.19s | IR 全量求解回归 |
| `run_inverse_design_smoke.py` | 19.82s | 逆向设计迭代 |
| `run_hybrid_design_smoke.py` | 17.31s | 混合参数化设计扫描 |
| `run_port_acceptance_smoke.py` | 10.59s | 端口验收 3D 判据 |
| `run_phc_anchor_smoke.py` | 6.82s | 光子晶体本征解（ARPACK） |

### C 组：60s 超时 —— 延长至 300s 复测，**判明「慢而能完成」而非卡死**

| smoke | 60s | 300s 复测 | 结论 |
|---|---|---|---|
| `run_wdm_splitter_smoke.py` | TIMEOUT | **164s rc=0** | 慢（WDM×分束树联合设计闭环） |
| `run_design_package_smoke.py` | TIMEOUT | **119s rc=0** | 慢（4 类设计包 schema 全链路） |
| `run_hybrid_multi_smoke.py` | TIMEOUT | **73s rc=0** | 慢（多波长加权联合） |
| `run_sparams_3d_smoke.py` | TIMEOUT | — | 重（3D 端口 S 参数仿真） |
| `run_sparams_loop_smoke.py` | TIMEOUT | — | 重 + 需 numba JIT（首次编译慢，脚本自述） |

> 注：C 组前三项文件都很短（41/46/47 行），「小文件超时」首先怀疑卡死；
> 延长复测后确认能正常完成，才准登记豁免。**豁免理由必须写真实耗时，不得写「超时」了事。**

---

### 附：接入 19 条后全量回归抓出 2 红 —— **护栏正常工作**

改动后第一轮全量 core：`115 PASS / 0 SKIP / **2 FAIL**`。两个失败项**同一根因**：

| 失败项 | 直接原因 |
|---|---|
| `run_count_consistency_smoke.py` | `AssertionError: 97 != 117` —— README「当前账本」写 CI core 97 条，实际 `CORE_SMOKES=117` |
| `run_ci_industrial_smoke.py` | 其内部 `_SUBSET_CONTRACT` 子集含 `run_count_consistency_smoke.py`，被连带判红 |

✅ 这是**护栏按设计生效**，不是新缺陷：README 计数与 `CORE_SMOKES` 的一致性本来就是
`run_count_consistency_smoke.py` 的守护目标。修复 = 同步 README 两处（第 281 行「当前账本」
97→117、第 202 行注释 97→117 / ~25min→~32min）；历史版本行里的 97 属史料，不动。
复验：count_consistency 11/11 OK、industrial **3/3 ALL PASS**、webui_api 89 PASS / 0 FAIL。

### 附 2：`routes.py` 兜底常数 82（对外验货面潜在失真）

`/api/verification_ledger` 主路径已动态取 `len(CORE_SMOKES)`，但 `except` 兜底写死 **82**
（v0.9.9 前遗留）。失败时静默报一个过时常数 ⇒ 悖「宁红不可假绿」。改为 `count=None` +
可机读 `stale=true` 标记（前端显示 `?` 而非假数字）。

## 三、修复：机制级（防复发，而非补一次）

### 1. `NON_CORE_SMOKES` 显式豁免登记表

`run_ci_regression.py` 新增 `NON_CORE_SMOKES: Dict[str, str]`（18 项，每项必附实测理由）。

**准入准则**：core = 纯 numpy 快速（ubuntu CI 可跑）。
凡**实测 <5s 且无重依赖者，无权豁免，必须进 core**。

### 2. 18 个快速孤儿接入 `CORE_SMOKES`

core **98 → 117**，运行时仅 **+9.6s**。

### 3. 新建 `lda/run_ci_coverage_gate_smoke.py`（覆盖门禁）

六道判据，且**该门禁自身也在 core 集内**（自食其规则，防门禁自己被漏接）：

| # | 判据 | 实测 |
|---|---|---|
| ① | 每个 `run_*_smoke.py` ∈ `CORE_SMOKES` ∪ `NON_CORE_SMOKES` | 覆盖 **130/130** |
| ② | 豁免项均附非空理由（禁止空洞豁免） | 18 项理由齐备 |
| ③ | `CORE_SMOKES` 无重复项 | 无 |
| ④ | 本 smoke 自身在 `CORE_SMOKES` 内 | 在 |
| ⑤ | **反向测试**：撤掉一项登记 ⇒ 必须报缺口 | 撤 `run_b30_readout_smoke.py` → 报 1 项 ✅ |
| ⑥ | 反向测试后状态复原（测试不污染真判据） | 复原 |

**6/6 PASS，EXIT=0**。

### 4. 顺带修掉同类定时炸弹

`run_ci_regression.py` 文件头「74 个 run_*smoke*.py」→ 130 个。

---

## 三之二、第六处：`run_coupler_band_smoke.py` 被硬杀，却报成普通 FAIL

接入 19 条后的全量回归出现一条陌生失败：

```
[FAIL  ] run_coupler_band_smoke.py  (136.4s)
         │ (无输出)
```

**三个异常点同时成立**：① 前两轮同样全量都 PASS（303.15s / 319.67s）；
② 本轮只跑了 136.4s，**远短于**正常耗时；③ **零输出**。

单独重跑复验：**rc=0，267s，ALL GREEN**。⇒ 不是断言失败，是**进程被硬杀**。

### 为什么「零输出」等于「被杀」

Python 的 stdout 在重定向到管道时是**块缓冲**（8KB）。进程若在 flush 前被
`SIGKILL` / 掉电 / OOM-killer 干掉，缓冲里的全部 print 一并丢失 —— 于是
「跑了 136 秒却一个字都没有」。这与断言失败（必然留下 `[FAIL]` 行）有本质区别。

### 为什么必须区分（不是洁癖，是防失真）

该 smoke 是本仓**最重的 CPU 任务**（torch CPU 全波段 3D FDTD），文档里已记载
20 线程满载曾两次触发**整机硬掉电**（Kernel-Power 41 / BugcheckCode=0 +
固件限速 Event 37，内存 63GB 已排除 OOM），v0.9.38 起由 `lda_solver/threads.py`
把并发压到一半核心（上限 10）。**持续负载下的偶发抖动属已知硬件边界。**

若把这类抖动报成普通 `FAIL`，后人的第一反应会是「去修那条物理判据」——
**而判据根本没错**。这正是本项目最危险的失真通道：v0.9.10 的漏算 3.0103dB
就是在 84 条全绿下溜过去的；反过来，为一次掉电而放宽判据，是同等量级的
自伤。故单列 **`CRASH`** 状态，语义明确为：**需人工复验，不是判据错**。

### 修复

1. `_run_one` 新增分类：非零 rc **且** 零输出 ⇒ `CRASH`，tail 打印可操作提示。
2. 新增 `_FAIL_STATUSES = ("FAIL", "ERROR", "TIMEOUT", "CRASH")` 常量，
   **统一**驱动 tail 打印 / fail_fast / `n_fail` 计数三处。
3. 新建 `lda/run_ci_crash_classify_smoke.py`（7 判据，**含反向测试**：
   撤掉 CRASH 登记 ⇒ `n_fail` 4→3 立刻降，证明判据会响），并登记进 core。

### 🔴 本处最致命的不是 CRASH 本身，是**记账漏计**

`n_fail` 原本按 `status in ("FAIL","ERROR","TIMEOUT")` 统计。新增状态若忘了
同步进这个元组，**红灯会直接变绿 —— 静默假绿，比红更危险**。这正是「宁红
不假绿」的记账底线，故把它抽成单一常量 `_FAIL_STATUSES` 并配专属门禁守护。

---

## 四、教训（升级为铁律）

**扩库/加件类改动必须同步五处**：

1. **条目库**（golden / 货架 / 系统类型 / 引擎）
2. **CI 断言计数**（等值断言 + 会增长的集合 = 定时炸弹 ⇒ 改包含式 / 动态计数）
3. **派生表**（定价归档、白名单、覆盖矩阵……）
4. **回归集登记**（写了 smoke 不等于进了 CI）
5. **对外账本**（README「当前账本」计数、`/api/verification_ledger` 等对外展示数字）

第 1–3、5 处此前全靠人肉发现（本轮第 5 处由 `run_count_consistency_smoke.py` 抓到）；
第 4 处现已由 `run_ci_coverage_gate_smoke.py` 自动兜底。

**两条衍生判据**：

- 凡「**只发现不分类**」的机制 = 静默缺口温床。发现必须伴随强制归类。
- **排除理由会腐化**。`run_ci_regression.py` 旧注称 `wdm_coupler` 属「重 FDTD/GPU 项」，
  实测 **0.30s**——实现换了、变快了，但没人复查。故豁免表强制写明**实测耗时与日期**，
  便于日后重新评估。
- **失败状态必须穷举记账**（第六处）。`n_fail` 用「状态 ∈ 某元组」统计时，
  新增状态漏登记 ⇒ **红变绿**。故抽成单一常量 `_FAIL_STATUSES` + 专属门禁
  （反向测试：撤掉一项登记必须立刻响）。
- **「异常短 + 零输出」是进程被杀的指纹，不是失败**。CI 看到非 PASS 时先问
  「是判据错了，还是进程死了」——两者处置完全相反。

---

## 五、验证

| 项 | 结果 |
|---|---|
| `run_ci_coverage_gate_smoke.py` | 6/6 PASS，覆盖 130/130，EXIT=0 |
| `run_ci_crash_classify_smoke.py` | 7/7 PASS（含反向测试 n_fail 4→3），EXIT=0 |
| `run_production_smoke.py` | 17/17 done（A5/B4/C4/D4）· golden 48/48 · 货架 75 · 三道反向测试全命中，EXIT=0，0.84s |
| `run_golden_product_smoke.py` | 48/48 PASS，EXIT=0 |
| `run_count_consistency_smoke.py` | 11/11 OK（README 计数 118 ≡ `CORE_SMOKES` 118） |
| `run_ci_industrial_smoke.py` | 3/3 ALL PASS，EXIT=0 |
| `run_webui_api_smoke.py` | 89 PASS / 0 FAIL，EXIT=0 |
| 全量 `--tag core` 回归（改动前） | 97 PASS / 0 SKIP / 0 FAIL，1875.62s，EXIT=0 |
| 全量 `--tag core` 回归（接入 19 条后） | 115 PASS / 0 SKIP / 2 FAIL —— **护栏正常工作**（README 计数未同步），已修 |
| 全量 `--tag core` 回归（终版 118 条） | **118 PASS / 0 SKIP / 0 FAIL，1827.51s，EXIT=0** |

🔑 **终版回归的关键一条**：`run_coupler_band_smoke.py` **249.78s PASS** —— 证实
上一轮 136.4s 的「零输出 FAIL」确属偶发硬杀（flaky），**判据本身无病**。
若当时按普通 FAIL 处理，就会有人去"修"一条根本没错的物理判据。

红线全程未破：LLM 不进判决路径 · 不调 tapeout · honest_tier=前瞻预研 · 判决纯死标量比对。
