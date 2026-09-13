# LDA 战略审计与功能审计（完整版 · v0.9.77）

> 审计日：2026-09-14 · 基线版本：v0.9.77（2026-09-13 部署 · commit `764efdb`）
> 方法：所有状态均来自**代码实测 / 测试输出**，不采信文档声明（铁律：文档声明=会腐化的派生数据）。
> 对照基线：2026-09-11 战略审计报告（v0.9.67）

---

## 0. 执行概要（结论先行）

**总判定：战略地基扎实 ✅，愿景上层（四层系统 / L2 计算芯片）立项前闸门已全过 🟡（P1-3 红线闸门自检四层各挂 VMM 锚 ≥ self_certified；L3/L4 为 Tier-1 自证桩），验证地基持续增厚 🟡（自证桩占比仍偏高）。**

| 维度 | 结论 | 关键证据 |
|---|---|---|
| 战略地基（L0 双栈 EDA） | ✅ 已完成并持续增厚 | 33 类端到端 / 56 锚 / 452 py·97.5k 行 / GC-*48 全 PASS |
| 主权红线 | ✅ 守住 | MEsoft GPL 隔离（沙箱 5/5）· DEVSIM fork 冷备 · A 级零 import |
| 验证纪律（LLM 不进判决） | ✅ 守住 | `--ai` verified 诚实 2/56；`is_independent` 在 llm_enabled 时恒 False |
| 物理定律锚 + 实证锚判卷 | ✅ 守住 | 31 严格 / 2 降级 / 23 自证；实证语料 30 条全 A 级 |
| T1 分层解锁（电学内核） | ✅ T1 做 / T2 锁死 | drift_diffusion_1d/2d 就位；无 T2 求解器（工艺真值永久锁） |
| T1-C 主动器件扩展 | ✅ 完成 | B31/B32/B33/APD + W5/W6 真求解；33 注册候选 |
| T2 真值链（MPW 回流换锚） | 🟡 诚实降级已做，真值回流未启动 | U4/U5/U6 降为 degraded_ordinal；0 轮 MPW（等窗口） |
| 四层系统（L1→L2 鸿沟） | 🟡 立项前红线闸门全过（四层各挂 VMM 锚 ≥ self_certified） | MZI 网格矩阵乘 MVP 可演示；L1/L2 高于门槛，L3/L4 为 Tier-1 自证桩（待实测升级） |
| 开源 + 社区独立验货护城河 | 🟡 开源已做，标准位未达 | 三端 + Apache-2.0 + DCO；users=1，0 外部采用 |
| 功能对齐（验证机械） | ✅ 全绿 | v0.9.77 全量 CI 173（含 P1-3 红线闸门 smoke）全绿 |

**自 2026-09-11 基线的净变化**：代码 426→452 文件、92.4k→97.5k 行；锚 53→56（严格 28→31、降级 1→2、自证 24→23）；CORE_SMOKES 157→171。严格独立占比 52.8%→55.4%（目标 70%，未达）。

---

## 1. 战略对齐矩阵（目标 → 代码证据 → 状态）

> 证据格式：文件:行号 / smoke 实测 / grep 计数。状态 ✅完成 / 🟡部分 / 🔴未做。

### S1 · L0 双栈 EDA 底座做实（光子 PDA + 量子 QEDA）
- 证据：`README.md:325`「22 引擎 + 11 包 = 33 类端到端（光子 15 + 量子 7）」；`_audit_probe` 实跑 `ANCHOR_TOTAL=56`；`PY_FILES=452 PY_LOC=97539`。
- 状态：**✅** 底座做实并持续增厚。

### S2 · 主权红线（A 级永不借 / B 级借今踢后 / C 级自主）
- 证据：① GPL 隔离——`run_solver_writer_sandbox_smoke.py` 实跑 **5/5 PASS**（强隔离降权 nobody 读 /etc/shadow 被拒 + 网络命名空间禁外网），Windows CI 走 weak 自动跳过（不破红线）；`run_kernel_seal_smoke.py` OK。② Meep 21 处引用，subprocess 仅回标量（铁律：GPLv2+ 隔离）。③ DEVSIM（Apache-2.0 B 级）fork 冷备 `vendor/devsim_mirror` 锁定 r2.11.0 + `run_t1b_devsim_cold_backup_smoke`。④ `run_optional_import_guard_smoke`（ast 全包 import+license 双扫）门禁。
- 状态：**✅** 守住。零 A 级商业求解器 import。

### S3 · 验证纪律（LLM 不进判决路径，PASS/FAIL 由死标量定）
- 证据：`lda_harness/l3_ai_solver.py:130-142` `is_independent()` 在 `llm_enabled` 时**恒返回 False**——AI 产出值绝不计入 verified；`README.md:336` `--ai` 实测 `verified=2/56`（仅 B1/B4 真实现，余 53 道为 `return golden` 自证桩），**不计入对外 verified**。`run_harness.py` 双向护栏（多算=假绿 / 少算=倒退 / verified+stub+degraded≡total）。
- 状态：**✅** 守住。「AI 出题、物理定律判卷」四层架构落实。

### S4 · 物理定律锚 + 实证锚判卷
- 证据：`_audit_probe` 三分类 = 严格 31 / 降级 2 / 自证 23（和=56），与 `README.md:327` 完全一致；实证语料 30 条全 A 级可公开溯源（DOI/arXiv/URL），B 级已清零（`README.md:332`）。
- 状态：**✅** 守住。降级 2 道 = E9 + E10（微环 FSR，独立 n_g 闭式交叉验证）。

### S5 · T1 分层解锁（电学/TCAD T1 内核解锁 + T2 锁死）
- 证据：T1 内核 `lda_solver/drift_diffusion_1d.py` + `drift_diffusion_2d.py` 就位；全仓**无 T2 工艺真值求解器**（foundry 专有 implant/diffusion/etch/stress 永久锁，`README.md:331` 主权纪律）；`T1_OUTPUT_IS_ORACLE=False` 守卫（W5/W6 smoke 反向测试必响）。
- 状态：**✅** T1 解锁并完成；T2 按红线永久锁死（只消费 PDK 接口）。

### S6 · T1-B 电学内核 N(x) 真求解
- 证据：W2 `drift_diffusion_1d.py`（自洽泊松-玻尔兹曼，4 判据）+ W4 `drift_diffusion_2d.py`（2D 漂移-扩散+连续性，4 判据，CI core 164→165）；终端 I(V) 比 Sze 短二极管闭式 golden ~4.6%<8%。
- **诚实边界（Task #4，v0.9.77 已文档化）**：`drift_diffusion_2d.py::solve_pn_junction_2d_bias` 仅在 **V≥0（正向/近平衡）可用**；V<0 反偏因「无复合项 + 少数载流子 Dirichlet BC 塌缩 + Gummel 准费米势发散」**非物理**。`docs/lda_reverse_bias_limitation.md` + `reverse_bias_unvalidated` 诚实标记 + `run_t1_reverse_bias_limitation_smoke.py` 8 判据护栏（反偏非饱和/不收敛/标记必 True）。
- 状态：**🟡** 正向/近平衡可用；反偏（V<0）诚实受限并已显式文档化（非静默缺陷）。

### S7 · T1-C 主动器件扩展（A 档闭式 ~8 锚 + B 档真求解）
- 证据：A 档 B31 Soref-Bennett（Drude 独立候选）、B32 EAM-QCSE（1D 薛定谔数值对角化）、B33 探测器 RC（+APD 闭式倍增扩展）；B 档真求解 W5 探测器带宽（T1 1D 渡越时间真算）、W6 APD 雪崩（碰撞电离积分+固定种子蒙特卡洛）。`_audit_probe` 注册候选 33 个含 `b31_drude_phase_shift`/`b32_qcse_numerical`/`rc_bandwidth_timestep`。
- 状态：**✅** T1-C 闭环完成（A 档 ~8 锚目标达成；B 档 W5/W6 真求解落地）。

### S8 · T2 真值链（MPW 回流换自证桩 ≥5）
- 证据：T2 第 3 阶段 U4（Ge PD 响应度 1D 内核）/ U5（MZM Vπ T1 1D 反偏施压）/ U6（量子 T1 量级带）已落地，但**诚实降为 `degraded_ordinal`**（E9/E10 同源逻辑）——残差主成分为未公开器件几何/材料假设，非数值误差，不放宽 tol 凑实测。
- **缺口**：「≥5 自证桩换真锚」依赖 3–4 轮 MPW + 委托封测实测回流——**当前 0 轮 MPW**（`README.md` 责任边界：封测验证委托伙伴，等您现实撬动 foundry/MPW 窗口）。
- 状态：**🟡** 诚实降级换锚已做；真值回流（物理真锚）未启动 = 等窗口（不属技术缺陷）。

### S9 · 四层系统（架构综合 / 编译映射 / 控制校准 / 协同仿真）—— L1→L2 最本质鸿沟
- 证据：`LDA_愿景战略与实施策略_...md:94` 明确标「**四层系统缺口（蓝·LDA 当前完全没有）**」；2026-09-11 战略审计结论「阶段 0 未完成前不启动愿景四层系统 / 光子计算 MVP」。
- **P1-3 红线闸门自检（2026-09-14 落地 · 建议 A 达成）**：新增 `lda/lda_l2/mzi_mesh_matmul.py`（MZI 网格矩阵乘引擎，C 级自主纯 numpy）+ `lda/lda_l2/four_layer_redline_gate.py`（五道闸门 G1–G5）+ `lda/run_mzi_mesh_matmul_demo.py`（对外可演示 HTML）+ `lda/run_four_layer_redline_gate_smoke.py`（CI core 173）。GateReport = **PASS**（建议 A：每层挂 VMM 锚 ≥ self_certified）：G1 主权(未借 Meep/Tidy3D)/G2 LLM 不进判决/G4 不虚报/G5 外置激光可绕 全 PASS；G3 **四层均 ADMISSIBLE**——L1 被动前端（B14 方法学独立锚·50/50 耦合长 7.75µm）/ L2 编译映射（Reck 定理，重构保真度 1.0 / fro_err 4.9e-16 机器精度）**高于门槛**；L3 控制校准（相位标定闭环）/ L4 协同仿真（电-热-光链式）登记 **Tier-1 自证桩**（候选≡golden、反解残差恒零、明确升级路径与验证责任方，**不冒充已验证**）。
- 状态：**🟡** 立项前闸门全过——四层各挂成熟度锚，L1+L2 光学矩阵乘 MVP 可演示且清白过红线闸门；L3/L4 为 Tier-1 自证桩（“自证桩是合法的第一验证阶段” VMM v0.9.62），待外置相干激光/探测器实测与多域协同仿真升级。符合「先夯实基础」纪律，非倒退。

### S10 · 开源 + 社区独立验货护城河 / 标准位 T4（L0 IR / DesignPackage JSON）
- 证据：三端开源（gitee `i4hub/LDA` + github `iduyuhe/LDA` + 生产 `root@115.191.20.92`），Apache-2.0，DCO `Signed-off-by` 就位；`L0 IR` / `DesignPackage JSON` 已存在（`lda_ir`/`lda_l1`）。
- **缺口**：`README.md:198`「标准是被采用出来的，当前 users=1」——**0 家外部机构采用、0 家 foundry 签 PDK**（T4 验收 ≥2 外部 + ≥1 foundry 未达）。
- 状态：**🟡** 开源与主权机制已就绪；标准位/外部采用未达（属获客与生态建设，非技术）。

### S11 · L2 光子计算芯片 / 量子计算芯片（愿景目标，光子优先）
- 证据：依赖 S9 四层系统；光子（经典）计算外置激光可绕（不破红线），量子（光量子）受单光子源硬卡。
- 状态：**🔴** 未启动（依赖 S9）。战略层「光子优先」已拍板，系统层照铺但不优先。

### S12 · 生态开放四层光谱（判据先于代码 / 主权扫描）
- 证据：`run_optional_import_guard_smoke`（ast import+license 双扫，含 DEVSIM/T1 许可扫描）；DCO 闸门；生态四层光谱文档（实测/PDK/边缘求解/核心分层）。
- 状态：**✅** 机制就位（最大风险「假绿=自证桩批量生产」由「判据先于代码 + maintainer 写判据」规避）。

### S13 · 全能力盘点（GC-*48 / 75 货架 / 实证 30 A）
- 证据：`run_gc_smoke.py` 实跑 **3/3 PASS**（D-78 GC 全链路）；`README.md:329`「75 货架（50 开放 + 25 咨询制）· 5 赛道 + 24 应用域 · 定价归档 75/75」；实证语料 30 条全 A 级（D-66 逐字核实，B 级清零）。
- 状态：**✅** 全绿。

### 前次审计（2026-09-11）P0/P1 收口追踪
| 项 | 状态 | 证据 |
|---|---|---|
| P0 计数一致性守卫漂移 | ✅ 已修 + 本次 U3 后再同步 | `run_count_consistency_smoke` 11/11；U3 加 E10 后 ledger 锁 1→2 已显式同步（非静默） |
| P1① 自证桩升级 53%→70% | 🟡 进行中未达 | 28/53=52.8% → 31/56=**55.4%**（目标 70% 需 ~39 严格） |
| P1② `lda_agent` 专项代码评审 | 🔴 未完成 | 12.8k 行 / 53 文件，全仓最大最复杂 AI 递归自举核心，未专项评审 |
| P1③ 完整 CI core 回归确认全绿 | ✅ 已完成 | v0.9.77 部署前全量 171 smoke 实跑全绿（post ledger-fix） |

---

## 2. 功能对齐（验证机械 · 实跑取真证据）

### 2.1 本次实跑子集（2026-09-14，受管 venv 3.13.14，4 线程单实例）
| 守卫 smoke | 结果 |
|---|---|
| `run_count_consistency_smoke.py` | OK（计数一致性） |
| `run_three_class_consistency_smoke.py` | **4/4 PASS**（三分类对外一致） |
| `run_webui_verification_ledger_smoke.py` | **15/15 PASS**（账本三分类 ≡ 端点） |
| `run_benchmark_falsifiability_smoke.py` | **13/13 PASS**（严格 31 · 降级 2 · 自证 23/56） |
| `run_maturity_baseline_smoke.py` | PASS（VMM 底线 M1–M5） |
| `run_d_criterion_smoke.py` | **10/10 PASS**（判据 D 防代数恒等假独立） |
| `run_gc_smoke.py` | **3/3 PASS**（GC-*48 全链路） |
| `run_solver_writer_sandbox_smoke.py` | **5/5 PASS**（GPL 隔离真门禁） |
| `run_kernel_seal_smoke.py` | OK |
| `run_ci_coverage_gate_smoke.py` | **6/6 PASS**（门禁无静默缺口） |
| `run_e10_ring_fsr_smoke.py` | **12/12 PASS**（U3 微环 FSR） |
| `run_t1_reverse_bias_limitation_smoke.py` | **8/8 PASS**（反偏局限护栏） |
| **合计** | **77 PASS / 0 FAIL（12 守卫全绿）** |

### 2.2 全量 CI core 门禁（v0.9.77 部署前，2026-09-13）
- 实跑 `run_ci_regression.py`（CORE_SMOKES=171，4 线程单实例，~55 min）：**全绿**。
- 收口实战抓到 1 FAIL：`run_webui_verification_ledger_smoke` 硬编码 `degraded_ordinal==1`，未随 U3(E10 升 degraded_ordinal) 同步（铁律「计数护栏定时炸弹」）→ 显式同步为 2（E9+E10），复跑 **15/15 PASS**，三类护栏 4/4 确认 README≡harness≡端点三面一致。
- 56 锚三分类闭合：严格 31 / 降级 2 / 自证 23（`run_harness` verified=31/56）。

### 2.3 测试卫生
- 全量确定性：`deterministic.py` 唯一口径（浮点 9 位有效数字 + 去 volatile 键），`git status` 常绿（v0.9.75 根因修复）。
- 无残留未提交测试产物；本次审计 scratch（`_audit_probe.py`/`_audit_func.py`）已计划删除，不进提交。

---

## 3. 诚实缺口与风险（照写，不粉饰）

1. **反偏模型局限（V<0）**：T1-B 2D 内核反偏非物理，已文档化 + 护栏，但仍是真实能力边界（正向可用、反偏不可用）。所有已验证反偏分析均绕开该路径。
2. **自证桩占比 44.6%（23/56）**：验证地基最大短板。严格独立 55.4% < 目标 70%。升级路径明确（B11/B16-B19/S1-S13 等），但进度慢于战略预期。
3. **`lda_agent` 未专项评审**：12.8k 行 AI 递归自举核心，前次审计 P1② 仍挂起，存在未量化覆盖风险。
4. **T2 真值回流 = 0**：等 foundry/MPW 窗口（您现实 KPI），非技术阻塞。
5. **四层系统 / L2 计算芯片未启动**：设计递延，符合「先夯实」纪律；但意味着「愿景兑现」尚在早期地基阶段，对外叙事须诚实区分「底座就绪」与「计算芯片可用」。
6. **标准位外部采用 = 0**：users=1，护城河差异化尚未被外部采用验证。

---

## 4. 综合优先行动清单

### 🔴 P0（立即）
- **P0-1**：`lda_agent` 专项代码评审（导入健康 / 异常路径 / 死代码 / 覆盖）——前次 P1② 挂起过久，是全仓最大未量化风险面。
- **P0-2**：任何加 `degraded_ordinal`/严格锚的 PR，必须 `grep degraded_ordinal` + `grep strict_independent` 全仓同步所有硬编码计数护栏（ledger smoke `_DOC_TIERS`、README 三分类、three_class、count_consistency）——本次 U3 险些漏更 ledger 锁，已固化为必查项。

### 🟠 P1（近期，优先于新功能）
- **P1-1**：自证桩升级冲刺 70%（当前 55.4%）——优先 B2/B11 已升路径的同类（B16 重审留桩、B17-B19/S1-S13 方法学独立候选）。
- **P1-2**：T2 真值链启动（您现实）：foundry PDK 只读接口接触 + MPW 排期撬动，把 U4/U5/U6 的 `degraded_ordinal` 升为 strict（需实测回流）。
- **P1-3**：四层系统立项前过红线闸门自检——**✅ 已达成（2026-09-14）**：建议 A（每层挂 VMM 锚 ≥ self_certified）四层全过、整体 PASS；建议 B（MZI 网格矩阵乘 MVP demo 对外可演示）已交付 HTML。后续升级=L3/L4 接外部实测/ORACLE 升 `degraded_ordinal`→`strict_independent`。

### 🟡 P2（观察/追踪）
- 10 处 `NotImplementedError` + 41 处占位注释：均为意图明确设计留口（FoundryPDKClient / IR 未接路线），非缺陷；建「留口清单」集中追踪。
- 根目录 190 `run_*.py`：季度复核 CI 覆盖 / NON_CORE 豁免登记。

---

## 5. 附录 · 复现命令

```bash
# 环境（受管 venv，绝不用 lda_cuda_venv）
PY=C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe
export OMP_DYNAMIC=FALSE MKL_DYNAMIC=FALSE PYTHONPATH=D:/agent_LDA

# 战略对齐证据（锚/三分类/CORE/候选/代码规模）
$PY lda/_audit_probe.py

# 功能对齐子集（12 守卫）
$PY lda/_audit_func.py

# 全量 CI core 门禁（~55 min，4 线程单实例，无蓝屏）
$PY -u lda/run_ci_regression.py

# 56 锚三分类闭合（路径① 对外口径 verified=31/56）
$PY -u lda/run_harness.py
```

> 注：本报告为审计交付物，未自动提交仓库。如需随 `LDA_战略审计报告_*` 系列入档，请指示。
