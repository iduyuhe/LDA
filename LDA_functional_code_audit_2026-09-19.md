# LDA 全面功能审计 + 代码审计报告

- **审计对象**：`D:\agent_LDA` @ `HEAD = 0ad28ae`（v0.9.110 · 2026-09-19）
- **审计日期**：2026-09-19
- **审计方法**：全仓静态分析（pyflakes 3.4.0 + 内建 `compile()`）+ 动态复现实验 + 机器宣称逐条实测 + 护栏实跑
- **审计性质**：**只读**。除本报告外**未改动任何仓库源码、未动任何锚的定级、未动棘轮常数、未 commit**；15 个审计脚本与实跑日志已**移至仓库外**（见 §1 备份路径）
- **解释器**：`C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe`（3.13.14 · scipy 1.17.1 · numpy 2.4.6）

---

## 0. 结论先行

**总判：工程质量高于同规模开源项目的平均水平；账本诚实、红线合规、安全姿态干净。但存在 2 处 P1 真实缺陷（其中 1 处是"公开 HTTP 端点上的必然 500"），以及一批 P2 级一致性/可维护性债务。**

| 维度 | 判定 | 一句话 |
|---|---|---|
| **功能宣称真实性** | ✅ **通过** | 22 引擎/11 包/33 类、469 锚、75 货架、178 CI core、119 API 端点——**逐条实测全部与代码一致**，无虚报 |
| **锚库诚实性** | ✅ **通过** | 三分类 448/3/18 = 469 由 `BENCHMARK_DEFS` 动态推导实测复现；`physical_law=457=469−12` 自洽 |
| **安全姿态** | ✅ **干净** | 0 条硬编码凭证、0 个密钥类文件入库、0 个 >3MB 跟踪文件；`.secrets/`·`.cache/`·`vendor/` 均已 gitignore |
| **三方隔离红线** | ✅ **合规** | 7 个三方桥接器 **0 个模块级导入**，全部懒加载 + try 保护 + 凭证门控；Meep 走子进程只回标量 |
| **确定性** | ✅ **良好** | 全部随机源均显式播种；有 `run_report_determinism_smoke` 专护报告 |
| **编译健康** | ✅ **503/503** | 503 个 py 文件 `compile()` 全通过，**0 语法错误** |
| **代码卫生** | ⚠️ **中** | pyflakes 360 条（245 未用导入 / 75 未用赋值 / 25 空 f-string / **10 未定义名**）；重复助手 ×86；两个 6.6k+ 行巨石文件 |
| **发行/打包** | ⚠️ **有缺** | `lda_l3` 未声明打包 ⇒ pip 安装后 `run_production_smoke` 必 ImportError |
| **新人上手** | ⚠️ **有坑** | `pyproject` 声明 `pytest` 但仓内**无 pytest 套件 + 无配置**，根目录 `pytest` **rc=2 失败且耗时 244s** |

### 分级发现（P0 无 · P1 ×2 · P2 ×11 · P3 ×5）

| ID | 级 | 发现 | 证据 | 影响面 |
|---|---|---|---|---|
| **F-01** | **P1** | `lda_pdk/review.py:228` 调用未导入的 `_norm_params` ⇒ **NameError** | 复现：`eval("_norm_params", vars(review))` → `NameError` | **`POST /api/ecosystem/resubmit`** 带 `default_params` 时必 500 |
| **F-02** | **P1** | `lda_l3` 未在 `pyproject.toml` 的 `packages` 中声明 | `run_production_smoke.py:29` `from lda_l3 import production_plan`；`"lda_l3" in pyproject` = False | pip 安装版无法运行 production smoke |
| **F-03** | P2 | `pytest` 被声明为 dev 依赖，但无套件/无配置/根目录收集失败 | `pytest --collect-only` rc=2 · 244s · 收集到 `vendor/devsim_mirror/testing/` 触发 `import devsim` 失败 | 新贡献者第一条命令即红 |
| **F-04** | P2 | `drift_diffusion_2d.py` 作脚本运行时 `v_t` 未定义 | 实跑 rc=1：`NameError: name 'v_t' is not defined. Did you mean: 'V_T'?` | 仅 `__main__` 演示段（库函数正常） |
| **F-05** | P2 | `_solve_poisson` 算出 `converged` 但**从不返回** ⇒ 未收敛解被静默当有效解 | pyflakes F841 @ `drift_diffusion_2d.py:414` | 静默失败（无告警） |
| **F-06** | P2 | `adjoint_fdtd.py:409` / `adjoint_fdtd3d.py:653,897` `rng` 创建后未使用 ⇒ `seed` 参数是死参数 | pyflakes F841 ×3 | 误导 API 语义 |
| **F-07** | P2 | `check()` 助手复制 **86 份**；`_http`/`_free_port` ×6；`guard_t1_not_oracle` ×6 | AST 同名函数扫描 | 红线守卫被复制 6 处，任一处漂移即削弱保护 |
| **F-08** | P2 | `verification_adapters.py` **6789 行** / `benchmarks.py` **6635 行** 巨石 | 行数统计 | 每批必改 ⇒ 合并冲突/注册漂移风险 |
| **F-09** | P2 | 10 处 F821 未定义名（9 处因 `from __future__ import annotations` 而无害，1 处=F-01 真 bug） | pyflakes F821 | 类型提示卫生 |
| **F-10** | P2 | 14 个根目录诊断脚本**已入库**（`assess_*` · `build_*` · `spike_*` · `md2docx_batch` · `verify_*_equiv` · `decrypt_redteam`）+ `spike_v3_out.txt` · `nav-index.png` · `reports_verification_ledger_sample.json` 散落根目录 | `git ls-files` | 仓库卫生 |
| **F-11** | P2 | `device_library.py` 7 处 `dict` 快照/映射构建后未用；`gds_export.py` `datatype` 赋值未用等 75 处 F841 | pyflakes | 死代码 |
| **F-12** | P2 | 245 处未使用导入（`lda_webui/app.py` 19 · `lda_harness/golden.py` 16 · `lda_l2/device_library.py` 10 …） | pyflakes F401 | 静态噪声掩盖真问题 |
| **F-13** | P3 | 25 处 f-string 无占位符（F541） | pyflakes | 风格 |
| **F-14** | P3 | `lda_agent/solver_writer.py:535` 自述已知缺陷「原始出射场幅平方当透射，无参考跑归一化、无 nL/n0 阻抗因子」 | 源码注释 | L3 AI 写内核 demo 路径 |
| **F-15** | P3 | `verification_adapters.py` 等文件中 `device_library` 契约/live 两分支重复导入同一符号 | pyflakes F811 ×4 | 冗余 |
| **F-16** | P3 | `run_loss_engine_smoke.py:112` 重复导入 `CORPUS_ENGINE_MAP`（L25 已导入） | pyflakes F811 | 冗余 |
| **F-17** | P3 | `oracle_tidy3d.py` 文档称 Tidy3D 为 "GPL"（Tidy3D 实际为商业产品/部分组件 Apache-2.0）；**处理方式不受影响**，但许可表述宜核对 | 源码 docstring | 对外文档严谨性 |
| **F-18** | P3 | 19 个 smoke 用 `unittest` 风格（84 test 方法），其余 ~172 个用自研 `check()` 断言 —— 两套测试范式并存 | AST + 实跑 | 一致性 |

---

## 1. 审计范围与方法（可复现）

| 脚本 | 覆盖 |
|---|---|
| `_audit_recon.py` | 规模基线 / 模块地图 / 入口清单 / 依赖声明 |
| `_audit_struct.py` | 打包声明 vs 实际包 / 隔离区 / 仓库卫生 / gitignore |
| `_audit_git.py` | git 跟踪面 / 敏感文件 / 硬编码凭证 / 大二进制 / 远端 |
| `_audit_static.py` | `py_compile` + pyflakes 全仓聚合 |
| `_audit_f821.py` | 10 处 F821 逐条取证 + 内建 `compile()` 编译检查 |
| `_audit_deep.py` | F821 作用域溯源 / F841 抽样 / F811 |
| `_audit_func.py` · `_audit_claims.py` · `_audit_enum.py` | 功能宣称逐条实测 |
| `_audit_det.py` | 确定性 / 时钟 / 三方红线 / 线程环境 |
| `_audit_iso.py` | 三方隔离 AST 核验 / MCP / pytest 体系 |
| `_audit_qual.py` | 测试入口一致性 / TODO / 重复代码 / 巨石文件 |
| `_audit_final.py` | 决定性收口（命名空间解析 / fresh 进程 path 实验） |

**脚本与实跑日志备份**：`C:\Users\Administrator\lda_scratch_backup\2026-09-19\audit\`
（15 个 `_audit_*.py` + 15 份 `audit_*.log` 全量 stdout 存档；按项目纪律**未留在仓库内**，避免制造与 F-10 同类的根目录污染）

**排除范围**：`lda_cuda_venv/`（三方 venv）· `node_modules/` · `vendor/devsim_mirror/`（DEVSIM 冷备镜像）· `.git/` · `.cache/` · `.workbuddy/`

---

## 2. 功能审计：宣称 vs 实测

### 2.1 逐条核验（全部通过）

| 宣称（README/账本） | 实测 | 判定 |
|---|---|---|
| 22 引擎 + 11 包 = 33 类端到端 | `ENGINE_KINDS`=22 · `PACKAGE_KINDS`=11 · 合计 33（**机器断言** `run_count_consistency_smoke` 11/11 OK） | ✅ |
| 光子 15 + 量子 7 | `ENGINE_DOMAIN` 动态统计 = `{'photon': 15, 'quantum': 7}` | ✅ |
| 469 道锚（B1-B451 + E1-E10 + S1-S13） | `BENCHMARK_ORDER`=469 · 前缀 `{B:446, E:10, S:13}` | ✅ |
| 严格独立 448 / 降级 3 / 自证桩 18 | 动态推导 **448/3/18 = 469** | ✅ |
| 独立率 / 天花板 | **95.5224%** / **97.4414%**（=(469−12)/469） | ✅ |
| CI core 178 条 | `run_ci_coverage_gate_smoke` 自报 `core = 178 · 豁免 = 18 · 覆盖 191/191` · 6/6 PASS | ✅ |
| 创新超市 75 货架 | `DEFAULT_SHELF` 实测 **75**（datacom 25+sensing 15+component 13+cpo 12+quantum 10） | ✅ |
| 5 赛道 + 24 应用域 | `SHELF_TRACKS`=5 · 应用域实测 **24** | ✅ |
| 定价归档 75/75 | `tier_of()` 缺档数 = **0** | ✅ |
| 物理定律锚 | `_PHYSICAL_LAW`=**457** = 469 − 12（10 系统锚 + B17/B18） | ✅ 自洽 |
| 主权 DRC 仅几何子集 | CLI/README 均显式标注"非晶圆厂官方 DRC deck 全量" | ✅ 诚实 |

### 2.2 真实能力盘点（实测枚举）

| 能力面 | 实测规模 |
|---|---|
| **WebUI API** | **119 个端点**（`GET_ROUTES` 30 + `POST_ROUTES` 88 + `PATCH_ROUTES` 1），基于**标准库 `http.server`**（零 web 框架依赖） |
| **WebUI 前端** | 11 个静态页 + 8 个 JS（`index.html` 单页 **368 KB**） |
| **CLI** | 4 子命令 `design` / `check` / `gf` / `report`，实测 `--help` rc=0 可跑 |
| **MCP server** | `LdaMcpServer`（154 行）· stdio JSON-RPC 2.0 · 工具 `lda.verify_design` / `lda.list_benchmarks`，委托 `KernelGateway` |
| **锚库** | 469 defs · golden dispatch 460 · 候选注册表 437 key |
| **护栏** | 191 个 `run_*_smoke.py`，178 入 core + 18 书面豁免（自食者门禁 6/6 PASS，含 2 道反向自检） |
| **测试资产** | 19 个 smoke 用 `unittest`（84 test 方法 / 355 assert）+ 其余用自研 `check()` |
| **代码规模** | 633 py 文件 / **139,724 行** / 6.6 MB（`lda/` 占 492 文件 / 123,533 行） |

### 2.3 一处需注意的"合理但易误读"项

- **`_GOLDEN_DISPATCH` 缺 10 道 E 锚**：E1–E10 的 golden 来自**实证语料**（`oracle=empirical-measurement(...)`）而非函数 ⇒ 本就不该有 dispatch 条目。**属设计，非缺陷**。
- **`B35` 有 dispatch 无锚**：B35≡B15 的**别名复用**（账本明文"B35≡B15 去重复用，不新建"）。**属设计**。
- **448 strict 锚 → 433 唯一 key**：7 个 key 被多锚共享（如 `fiber_lp01_neff_fd` 承载 B361–B368 共 8 锚）。**已核实为参数化共享**（注册表值无重名、`Counter(values())` 重复=0）⇒ **不是 B-28 那种"同名静默覆盖"**。

---

## 3. 代码审计

### 3.1 真缺陷（含复现证据）

#### F-01（P1）`lda_pdk/review.py:228` — 公开 HTTP 端点上的必然 NameError

```python
# review.py:36-39 从 .submit 导入 6 个符号，唯独漏了 _norm_params
from .submit import (
    BenchmarkProposal, ProposalStore, _load_store, _save_store, _resolve_path,
    ReviewPolicy, get_policy,
)
...
# review.py:227-228（运行时表达式，非注解；from __future__ import annotations 救不了）
if "default_params" in updates and updates.get("default_params"):
    p.default_params = dict(_norm_params(updates["default_params"]))
```

- `_norm_params` **确实存在**于 `lda_pdk/submit.py:119`，但 **review.py 既未定义也未导入**。
- 复现（决定性）：`eval("_norm_params", vars(review))` → **`NameError: name '_norm_params' is not defined`**
- **可达路径（这是它成为 P1 的原因）**：
  - 公开 API：`lda_pdk/__init__.py` 的 `__all__` 导出 `resubmit_proposal`
  - **WebUI 端点**：`routes.py:1712` `POST /api/ecosystem/resubmit` → `h_eco_resubmit`（routes.py:1344）→ `resubmit_proposal(...)`
- **为什么 CI 全绿**：唯一两个调用点 `run_ecosystem_review2_smoke.py:105` 与 `run_ecosystem_d96_report.py:51` 都只传 `{"by": "community"}`，**从不传 `default_params`** ⇒ 该分支是**测试盲区**。
- **影响**：社区贡献者"重提被拒提案并更新默认参数"时，端点返回 500（`NameError`）。
- **修法（1 行）**：在 review.py 的 `.submit` 导入清单中加入 `_norm_params`。

```python
from .submit import (
    BenchmarkProposal, ProposalStore, _load_store, _save_store, _resolve_path,
    ReviewPolicy, get_policy, _norm_params,      # ← 补这一个
)
```

**🔴 纪律提醒**：修完后必须**补一条覆盖 `default_params` 分支的断言**，否则修完仍是盲区（"没被验证过的修复不算修复"）。

#### F-02（P1）`lda_l3` 未声明打包 ⇒ pip 安装版功能缺失

- `pyproject.toml` 的 `packages = [...]` 列了 16 个包，**不含 `lda_l3`**；而 `lda/lda_l3/`（`__init__.py` + `production_plan.py` 193 行）是真实可导入包。
- 直接后果：`lda/run_production_smoke.py:29` `from lda_l3 import production_plan as pp` ⇒ **pip 安装环境下 ImportError**；源码树运行才正常（所以本地 CI 不会红）。
- 同类风险：`vendor/devsim_mirror` 与 `ext_oracle` 的处理是对的（前者 gitignore，后者已声明）——唯独 `lda_l3` 漏了。
- **修法**：`packages` 列表加 `"lda_l3"`。

#### F-04（P2）`drift_diffusion_2d.py` 作脚本运行必崩

```
$ python lda/lda_solver/drift_diffusion_2d.py
...
=== 2D 偏压 I(V) vs 理想二极管律 ===
    V(V)           I(A)    I_s*(exp-1)     ln|I|
Traceback (most recent call last):
  File "...\drift_diffusion_2d.py", line 567, in <module>
    Ith = gold["I_s"] * (math.exp(v / v_t) - 1.0)
NameError: name 'v_t' is not defined. Did you mean: 'V_T'?
```

- 根因：`v_t` 只是**函数形参**（L164 `v_t: float = V_T`），而 L567 在 `if __name__ == "__main__":` 模块作用域 ⇒ 应为 `V_T`。
- 范围：**仅演示段**。库函数（`solve_pn_junction_2d_equilibrium` 等）实测正常（上方网格收敛扫描 40/60/80/120 全打印正常）。

### 3.2 静态分析汇总（pyflakes 3.4.0）

| 类型 | 数量 | 判读 |
|---|---|---|
| F401 未使用导入 | **245** | 噪声（掩盖真问题），Top：`app.py` 19 · `golden.py` 16 · `device_library.py` 10 |
| F841 赋值未使用 | **75** | 多为历史批次数值核内的中间量；**3 条可疑**（见 F-05/F-06） |
| F541 f-string 无占位符 | 25 | 风格 |
| **F821 未定义名** | **10** | **1 条真 bug（F-01）**；9 条因 `from __future__ import annotations` 而无运行时影响（`List`/`Optional`/`Dict` 类型提示未导入） |
| F811 重复导入/重定义 | 5 | 冗余（见 F-15/F-16） |
| **语法错误** | **0** | ✅ |

**编译检查**：503/503 `compile()` 通过，**0 语法错误**。

**9 条"无害但应修"的 F821**（缺 typing 导入，一旦有人移除 `from __future__ import annotations` 或用 `typing.get_type_hints()` 即爆）：

| 位置 | 缺失名 |
|---|---|
| `lda_ir/dsl.py:158` | `List` |
| `lda_solver/port_sparams_3d.py:120` | `Optional` |
| `run_ci_regression.py:726,728,729,730` | `Optional` |
| `run_parasitic_rc_smoke.py:22,32` | `Dict` |

### 3.3 安全审计

| 检查项 | 结果 |
|---|---|
| 硬编码凭证（api_key/secret/password/token ≥12 字符） | **0 条** ✅ |
| 密钥/证书扩展名入库（`.pem/.key/.p12/.pfx/.jks/.enc`） | **0 个** ✅ |
| >3MB 已跟踪文件 | **0 个** ✅ |
| `.secrets/redteam_fernet.key`（44 B Fernet key） | 存在本地，**gitignore 覆盖 · 从未提交**（`git log --all -- .secrets` 空） ✅ |
| `.cache/`（30 文件含 JS 复现脚本 + 截图） | **gitignore 覆盖**（`.gitignore:52`） ✅ |
| `vendor/devsim_mirror/`（92 py · Apache-2.0 冷备） | **gitignore 覆盖**（`.gitignore:66`） ✅ |
| `decrypt_redteam.py`（已入库） | 仅引用被忽略的 `.secrets/` 路径，**不含任何密钥材料** ✅（P3：对外暴露内部缺陷跟踪流程） |

**三方隔离红线（AST 级核验）** —— **全部合规**：

| 桥接器 | 模块级导入 | 函数内(懒)导入 | try 保护 | 判定 |
|---|---|---|---|---|
| `ext_oracle/meep_oracle.py` | **无** | `meep` | ✅ + 子进程隔离 | ✅ GPL 走外部，只回标量 |
| `lda_harness/oracle_tidy3d.py` | **无** | `tidy3d` | ✅ + `TIDY3D_API_KEY` 门控，默认返回 `None` | ✅ 核心零污染 |
| `lda_harness/oracle_sax.py` / `oracle_pyepr.py` | **无** | — | ✅ 缺失降级 | ✅ |
| `lda_l1/gdsfactory_bridge.py` | **无** | `gdsfactory` | ✅ | ✅ B 级可选 |
| `lda_solver/voxel_field.py` | **无** | `gdsfactory` | ✅ | ✅ |
| `lda_solver/devsim_bridge.py` | **无** | `devsim` | ✅ + 镜像冷备 | ✅ |

⇒ **"A 级永不借 / B 级借今踢后 / 核心永不污染"在代码层可验证成立**，且文档明写纪律。

### 3.4 确定性审计

| 项 | 结果 |
|---|---|
| 随机源 | **全部显式播种**：`random.Random(seed)` ×14 · `np.random.default_rng(seed)` ×10 · `random.seed()` ×1；**无裸 `random.random()` 判决路径** ✅ |
| 时钟依赖 | 104 处 `time.time()/datetime.now()`，**绝大多数是 smoke 的耗时计时**；报告内容由 `run_report_determinism_smoke.py` 专护 ✅ |
| 线程预算 | `lda_solver/threads.py` 把内核并发压到 `DEFAULT_CAP=10`（`LDA_FDTD_THREADS` 可覆盖），docstring 完整记录 **Kernel-Power Event 41 掉电血案**取证 ✅ |
| `PYTHONHASHSEED` | **未设置**（0 文件）——若某处把 `set` 直接序列化进报告/dict，跨进程顺序会变。**当前有 report-determinism 护栏兜底**，建议一并钉死（P3） |
| 环境变量读取 | 54 处（`os.environ.get/getenv`）——皆为配置项，非判决输入 |
| tempfile | 59 处——smoke 隔离用，正常 |

### 3.5 可维护性

| 项 | 实测 | 判读 |
|---|---|---|
| **巨石文件** | `verification_adapters.py` **6789 行** · `benchmarks.py` **6635 行** · `app.py` 3547 · `innovation_market.py` 3477 | ⚠️ 前两个**每批必改**，是注册漂移/合并冲突的结构性风险源 |
| **重复助手** | `check()` **86 份** · `_http`/`_free_port` ×6 · `guard_t1_not_oracle` ×6 · `_ensure_path` ×4 · `_report` ×10 | ⚠️ 尤其 `guard_t1_not_oracle`（T1 不作 ORACLE 红线守卫）被复制 6 份 ⇒ 改一处漏五处即削弱红线 |
| 超长函数 | 仅 2 个 >400 行（`design_engine._build_specs` 426 · `falsifiability_smoke.main` 419） | ✅ 可接受 |
| TODO/FIXME/HACK | **仅 5 处**（123k 行） | ✅ 极干净 |
| 测试范式 | 两套并存（19 个 `unittest` + ~172 个自研 `check()`） | ⚠️ 一致性 |

### 3.6 发行与新人上手

| 检查 | 结果 |
|---|---|
| `[tool.pytest.ini_options]` / `pytest.ini` / `setup.cfg` / `tox.ini` / `conftest.py` / `tests/` | **全部不存在** |
| `pytest --collect-only`（仓库根） | **rc=2 · 244.32s** · `no tests collected, 1 error`（错误源 `vendor/devsim_mirror/testing/test_common.py` 的 `import devsim`） |
| `pyproject` `dev` extras | 声明 `["build", "wheel", "pytest"]` ⇒ **暗示 pytest 是测试入口，实际不是** |
| `CONTRIBUTING.md` 指引 | 正确（写的是 `run_ci_regression.py --tag core`），**未提 pytest** ⇒ 文档没错，是 `pyproject` 误导 |

⇒ 建议：`dev` extras 去掉 `pytest`（或补 `norecursedirs = ["vendor", "lda_cuda_venv", ".cache"]` + `testpaths`）。

### 3.7 仓库卫生

**已入库的根目录诊断/构建脚本（14 个）**：`assess_1m_circuit.py` · `assess_1m_hierarchy_poc.py` · `assess_1m_layout.py` · `assess_1m_route_e2e.py` · `assess_p00_cpo250k_verify.py` · `assess_p01_hierarchy_250k.py` · `assess_p02_lvs_baseline.py` · `assess_p02_lvs_profile.py` · `build_rdplan_output.py` · `build_resource_map.py` · `build_wechat_draft.py` · `decrypt_redteam.py` · `md2docx_batch.py` · `spike_scale_100k_v3.py` · `verify_gds_library_equiv.py` · `verify_lvs_cross_equiv.py`

**根目录散落产物**：`spike_v3_out.txt` · `nav-index.png`（87 KB 截图）· `reports_verification_ledger_sample.json`

**对比**：`diag_*.py`（12 个）与 `test_wg_quick.py` **已正确 gitignore**（"本仓库不发布，留在本地工作区"）——说明**这套纪律已有先例，只是没铺到 `assess_*`/`build_*`/`spike_*`**。

**远端配置**：远端名为 `gitee`（gitee.com/i4hub/LDA）与 `github`（github.com/iduyuhe/LDA），**无 `origin`** —— `git ls-remote origin` 失败。建议补 `origin` 别名或文档说明（P3）。

**README 数字漂移核查**：检索到 README 中出现 `58 货架`/`34 货架`/`5 货架`，**逐条核实均为历史版本叙述**（如"另修对外账本腐化：README 仍写 58 货架，实际 75"），**非当前口径漂移** ✅。

---

## 4. 已撤销的假设（诚实边界）

审计过程中有 **1 条假设被自己的实验推翻**，如实记录以免误导：

| 假设 | 实验 | 结论 |
|---|---|---|
| `lda_l2/device_library.py` 的 `verify_bragg_fdtd(mode="contract")` 分支缺 `_ensure_solver_on_path()` ⇒ `fdtd3d_import` 恒为 `False`（静默降级） | fresh 进程首调该 contract 分支，打印 `checks` | **假设错误**：实测 `fdtd3d_import: True` / `tmm_import: True`。路径由模块导入期设置，contract 自检正常。**该条不作发现** |

另有 2 条**初判后被证为"设计如此"**，已在 §2.3 说明（E 锚无 golden dispatch、448 锚→433 key 共享）。

---

## 5. 修复建议（按优先级 + 是否需发版）

| 序 | 动作 | 级 | 需发版？ |
|---|---|---|---|
| 1 | `review.py` 导入清单补 `_norm_params`，**并补一条覆盖 `default_params` 分支的断言** | P1 | ✅ 需（建议 v0.9.111） |
| 2 | `pyproject.toml` `packages` 补 `"lda_l3"` | P1 | ✅ 同版 |
| 3 | `dev` extras 去掉 `pytest`（或补 `norecursedirs`/`testpaths`） | P2 | ✅ 同版 |
| 4 | `drift_diffusion_2d.py:567` `v_t` → `V_T`（并让 `_solve_poisson` **返回** `converged`） | P2 | ✅ 同版 |
| 5 | 9 处 typing 名补导入（`List`/`Optional`/`Dict`） | P2 | ✅ 同版 |
| 6 | 抽出共享 `check()` / `_http` / `_free_port` / **`guard_t1_not_oracle`** 到公共模块 | P2 | 可分批 |
| 7 | 根目录 14 个诊断脚本迁 `scripts/`（或 gitignore），并清 `spike_v3_out.txt`/`nav-index.png` | P2 | 可分批 |
| 8 | 245 处 F401 + 75 处 F841 批量清理（先只清 `lda_harness`/`lda_webui` 两个热点） | P2 | 可分批 |
| 9 | `verification_adapters.py` / `benchmarks.py` 按批次族拆分（巨石治理） | P2 | **需专项** |
| 10 | `PYTHONHASHSEED=0` 写进 CI env；`oracle_tidy3d.py` 许可表述核对；补 `origin` 远端别名 | P3 | 可随批 |

> **本审计不改代码**（审计当时的性质）。修复已于同日作为 **v0.9.111** 落地，逐条状态见 §5.1。

---

## 5.1 修复落地记录（v0.9.111 · 2026-09-19 · 口径「P1 + P2 一批」）

| 序 | 发现 | 级 | 状态 | 落地方式 |
|---|---|---|---|---|
| 1 | F-01 `review.py` 缺 `_norm_params` | P1 | ✅ 已修 | 补导入 + **补 4 条覆盖 `default_params` 分支的断言** + **反向测试**（撤掉导入 ⇒ smoke rc=1、报 `NameError: name '_norm_params' is not defined`，证明确能变红） |
| 2 | F-02 `lda_l3` 未声明打包 | P1 | ✅ 已修 | `packages` 补 `"lda_l3"`（17 包）；声明/磁盘**双向对账零缺漏** |
| 3 | F-03 pytest 无套件却声明 | P2 | ✅ 已修 | 补 `[tool.pytest.ini_options]`（`norecursedirs` 排除 `vendor`/`lda_cuda_venv`/`.cache`/`node_modules`/`build`/`dist`/`*.egg`） |
| 4 | F-04 `v_t` 未定义 | P2 | ✅ 已修 | `drift_diffusion_2d.py:567` `v_t` → 模块级 `V_T`（`v_t` 仅为函数形参） |
| 5 | F-05 `converged` 算出即丢弃 | P2 | ✅ 已修 | **保号修复**：不改签名/返回值/数值行为（T1 数值内核历史行为冻结），未收敛时发 `RuntimeWarning` |
| 6 | F-06 三处 `rng` 死参数 | P2 | ✅ 已修 | 删死赋值 + docstring 如实改写（原称「随机」实为 **top-k 确定性采样**）；`seed` 参数保留兼容 |
| 7 | F-07 重复助手 ×86 | P2 | ⛔ 未执行 | **纯重构**：86 文件改动面，收益仅为一致性 ⇒ 建议专项批次 |
| 8 | F-08 巨石文件拆分 | P2 | ⛔ 未执行 | 本报告原已标「**需专项**」 |
| 9 | F-09 9 处 typing 名缺失 | P2 | ✅ 已修 | 4 文件补导入；**pyflakes F821 由 10 → 0** |
| 10 | F-10 根目录脚本已入库 | P2 | ✅ 已修 | 16 脚本 + 3 产物 `git rm --cached` + `.gitignore`（`check-ignore` 19/19 命中；本地文件与 git 历史均保留）。**选 ignore 而非迁 `scripts/`**：迁移会破坏脚本内 `os.path.dirname(__file__)` 的根定位，且 `docs/*.md` 以文件名引用它们 |
| 11 | F-11 / F-12 死代码 · 245 处 F401 | P2 | ⛔ 未执行 | **已实证存在 re-export 依赖**（`run_shelf_listing_smoke.py:154,273` 与 `run_shelf_taxonomy_smoke.py:141` 均 `from lda_webui.app import shelf_status`）⇒ 盲删会破坏调用方。本报告原亦标「可分批」 |
| 12 | F-13 空 f-string ×25 | P3 | ⛔ 未执行 | 纯风格；且 `f"{{}}"` 类需先处理转义再摘 `f`，盲改会**改变输出语义** |
| 13 | F-14 `solver_writer` 自述数值缺陷 | P3 | ⛔ 未执行 | 需重做归一化 / 阻抗因子，属数值工程而非代码卫生 |
| 14 | F-15 / F-16 重复导入 | P3 | ✅ 部分修 | F-16（`run_loss_engine_smoke.py:112`）已删冗余行；F-15（`device_library.py` 4 处）**保留** —— 未证伪其分支必要性 |
| 15 | F-17 Tidy3D 误称 GPL | P3 | ✅ 已修（**范围扩大**） | 核实官方 `flexcompute/tidy3d` LICENSE = **GNU LGPL-2.1**（客户端；求解服务为 Flexcompute 商业云）⇒ 全仓 **7 处**订正 |
| 16 | F-18 两套测试范式并存 | P3 | ⛔ 未执行 | 一致性债务，不影响正确性 |

### 审计时未列、修复轮新发现

- **N-1（P3）**：`four_layer_redline_gate.py:12` 与 `mzi_mesh_matmul.py:6` 把 Meep/Tidy3D 写作「**A 级 GPLv2+ 禁**」，与权威登记表 `sovereign_deps.py`（二者均 **B 级**）**直接矛盾** ⇒ 已订正为「B 级依赖，仅可作外部 ORACLE，本层以纯 numpy 自写取代」。该分级已被 `run_ecosystem_smoke:57` 的 `classify_dependency("Meep") == "B"` 护栏锁定，故属**表述错误**，`sovereign_deps.py` 的定级**一字未动**。
- **N-2（P3）**：CI 子进程未钉 `PYTHONHASHSEED` ⇒ 已在 `run_ci_regression._child_env()` 注入 `"0"`（子进程启动前生效，把报告确定性防线由「护栏兜底」前移到「源头消除」）。
- **N-3（信息 · 未处理）**：`origin` 远端别名**未补** —— 双远端纪律下 `sync_push.py` 硬依赖 `gitee`/`github` 两个远端名，加 `origin` 语义不明确且无实际收益，故仅在此记录，不动作。

### 验证记录（v0.9.111）

- **针对性 smoke 8/8 rc=0**（`run_ecosystem_smoke` 204.4s · `run_pdk_smoke` 19.2s · `run_loss_engine_smoke` · `run_parasitic_rc_smoke` · `run_ecosystem_review2_smoke` 16 PASS/0 FAIL · `run_report_determinism_smoke` · `run_mzi_anchor_smoke` · `run_coverage_deadzone_closure_smoke` 33 PASS · `run_ci_coverage_gate_smoke` 6 PASS）。
- **账本护栏 6/6 rc=0**：`run_count_consistency_smoke`（Ran 11 tests · OK）· `run_three_class_consistency_smoke` · `run_p0_count_guard_sync_smoke`（Ran 6 tests · OK）· `run_shelf_taxonomy_smoke`（12 PASS）· `run_shelf_listing_smoke`（13 PASS）· `run_ci_coverage_gate_smoke`（6 PASS）。
- **静态面**：pyflakes **F821 10 → 0**、语法错误 0（545 文件扫描）。F401/F841/F541 因未做批量清理而**刻意保持不变**（已在上表列明，非遗漏）。
- **全量 CI core 178**：见 §5.2。

---

## 5.2 全量 CI core 实跑结果（v0.9.111）

**结论：178 PASS / 0 SKIP / 0 FAIL · 5596.0s（93.3 min）· 全绿。**

命令：`python run_ci_regression.py --tag core`（不分批 · **不覆盖线程数** ⇒ 由 `_child_env()` 注入项目默认 `DEFAULT_CAP=10` · 单实例）。

🔴 **首轮实跑出现过 2 项 TIMEOUT（假红）**：`run_benchmark_falsifiability_smoke.py`（600s 预算）与 `run_redteam_anchor_fuzz_smoke.py`（原**无覆盖**、走全局默认 300s）。独立复跑取证 ⇒ 两者 **rc=0 功能全绿**（实测 1098.6s / 1315.8s），即报出的 TIMEOUT 是**超时预算不足**、非功能回归。根因：存量超时预算未随 B-25~B-28 四轮扩基（+52 锚）同步，**与本轮任何改动无关**。修复：`_BUILTIN_TIMEOUT_OVERRIDE` 中 falsifiability 600→**1800**、fuzz 补 **2000**（≈1.5–1.6× 余量），**判据一字未改**。

> 纪律提示：`_FAIL_STATUSES` 含 `TIMEOUT`（「宁红不假绿」的记账底线），因此超时预算必须随锚数增长同步上调，否则会周期性产生**假红**。已把该标定写进 `lda-ci-batched-power-safe` 技能，并配套新增 `scripts/ci_core_batched.py`。

---

## 6. 未覆盖范围（诚实披露）

1. **全量 CI core 178 条**——本审计**首轮（只读阶段）未跑**，理由：满载 CI 有 Kernel-Power 41 掉电史（见 `threads.py` 血案），只读审计不做长时满载。**已在 v0.9.111 修复轮补齐**：**178 PASS / 0 SKIP / 0 FAIL · 5596.0s**（见 §5.2）。
2. **未做数值正确性复核**——469 锚的 golden/candidate 数值未逐一复算（属 `lda-anchor-wiring` 技能范畴，历批已做判据 D + 反向测试）。
3. **未审计 WebUI 前端 JS 质量**（`index.html` 368 KB / `store.html` 75 KB 内联脚本未做 lint）。
4. **未审计 `vendor/devsim_mirror` 镜像内容**（三方代码，Apache-2.0，属外部）。
5. **未评估性能/扩展性**（仅有 `bench_router_scale.py` 等基准脚本存在，未实跑）。
6. **未做依赖漏洞扫描**（无 `pip-audit`/`safety` 环境）。

---

## 7. 一句话总结

**这套系统的"账本诚实性"是真的**——469/448/3/18、75 货架、33 类、178 门禁、三方隔离、凭证纪律，**逐条实测全部对得上，没有一条虚报**。它的问题不在"说自己有什么"，而在**"公开的 API 面上有一处必然崩溃的分支（F-01）没被任何测试摸到"**——这恰恰印证了项目自己反复强调的那句话：**"没被验证过的护栏不算护栏"**。F-01 与 F-02 修掉之后，这份代码的工程质量在同规模开源项目里属于上游。

---

## 8. v0.9.111 收口记录（修复轮结项）

- **全量 CI core 单次实跑 = 178 PASS / 0 SKIP / 0 FAIL · 5596.0s（93.3 min）**（见 §5.2）。
- **§5.1 表中 14 项修复全部落地**；P1×2（F-01 / F-02）均带「断言 + 反向测试」双证；未执行项与理由已逐条列明。
- 首轮 2 项 TIMEOUT 经独立复跑证实为**假红**（rc=0 · 1098.6s / 1315.8s），根因是存量超时预算未随扩基同步 ⇒ 已修复（600→1800 / 新增 2000），**判据未改**。
- 4 份受跟踪派生报告已随 CI 实跑刷新（**纯「锚数增长」· 零口径劣化**）；**锚的定级与棘轮常数一字未动**，账本零变化。
- 审计时给出的两条 P1 建议**现已闭环**；§6 中「未跑全量 CI core」一项已在修复轮补齐。
- 修复轮另发现并随批处理：**N-1**（Meep/Tidy3D 分级错写「A 级」→ 按权威表 `sovereign_deps.py` 改 **B 级**）、**N-2**（CI 子进程钉死 `PYTHONHASHSEED=0`）、**N-3**（补 `origin` 远端 —— 经核实与 `scripts/sync_push.py` 的双远端硬依赖冲突且无收益，**明确不做**）。
- 新增配套产物：`scripts/ci_core_batched.py`（分批防掉电跑法，默认不改线程数）+ 技能 `lda-ci-batched-power-safe` 三处缺陷订正（失效脚本引用 / 条数 173→178 / 超时表与线程标定脱钩）。
