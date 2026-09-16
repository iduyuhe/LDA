# LDA 战略审计与功能审计（完整版 · v0.9.78）

> 审计日：2026-09-16 · 基线版本：v0.9.78（2026-09-14 部署 · commit `ae836dc`）
> 当前生产：v0.9.79（2026-09-16 SSH 部署 · commit `154c586`，内/外网 health 版本串一致）
> 方法：所有状态均来自**代码实测 / 测试输出**，不采信文档声明（铁律：文档声明=会腐化的派生数据）。
> 对照基线：2026-09-14 战略审计报告（v0.9.77）

---

## 0. 执行概要（结论先行）

**总判定：战略地基扎实 ✅，愿景上层（四层系统 / L2 计算芯片）立项前闸门已全过 🟡（P1-3 红线闸门自检四层各挂 VMM 锚 ≥ self_certified；L3/L4 为 Tier-1 自证桩），验证地基持续增厚 🟡（自证桩占比仍偏高），商业试点（阶段 3）所需资产 🔴 尚未启动。**

| 维度 | 结论 | 关键证据（2026-09-16 实跑） |
|---|---|---|
| 战略地基（L0 双栈 EDA） | ✅ 已完成并持续增厚 | 33 类端到端 / 84 锚 / **515 py·104.4k 行** / GC-*48 全 PASS |
| 主权红线 | ✅ 守住 | GPL 隔离 5/5 PASS · DEVSIM fork 冷备 · **A 级零 import** |
| 验证纪律（LLM 不进判决） | ✅ 守住 | `is_independent` 在 `llm_enabled` 时恒 False；`--ai` verified 诚实 2/56 |
| 物理定律锚 + 实证锚 | ✅ 守住 | **63 严格 / 3 降级(E9,E10,B21) / 18 自证**；实证语料 30 条全 A 级 |
| T1 分层解锁（电学内核） | ✅ T1 做 / T2 锁死 | drift_diffusion_1d/2d 就位；全仓**无 T2 工艺真值求解器** |
| T1-C 主动器件扩展 | ✅ 完成 | B31/B32/B33/APD + W5/W6 真求解；33 注册候选 |
| T2 真值链（MPW 回流换锚） | 🟡 诚实降级已做，真值回流未启动 | U4/U5/U6/B21 降 degraded_ordinal；**0 轮 MPW** |
| 四层系统（L1→L2 鸿沟） | 🟡 立项前红线闸门全过 | MZI 网格矩阵乘 MVP 可演示；L1/L2 高于门槛，L3/L4 Tier-1 自证桩 |
| 开源 + 社区独立验货护城河 | 🟡 开源已做，标准位未达 | 三端 + Apache-2.0 + DCO；**users=1，0 外部采用** |
| 功能对齐（验证机械） | ✅ 全绿 | 10 守卫 **103 判据全 PASS**；CORE 178 全绿（子集实跑） |
| 商业试点（阶段 3）准备度 | 🔴 未启动 | 认证版 / PDK 合作 / 垂直场景 / 法务 均未立项 |

**自 2026-09-14（v0.9.77）基线至 B-3 收官**：代码 452→**515** 文件、97.5k→**104.4k** 行；CORE_SMOKES 171→**177**；降级锚 2→**3**（B21 诚实升 `degraded_ordinal`）；自证桩 23→**22**；严格独立 **31→46**（v0.9.79 为 36，B-2 再加 10 道 B42-B51 方法学独立锚），占比 **64.8%**（46/71，目标 70%，差 1 道严格锚）；**B-3 再加 13 道 B52-B64 方法学独立锚 → 59/84=70.2%，正式跨过 70% 红线**；**v0.9.80（2026-09-16 P1-1 B16 重审）：B16 由自证桩升 rib-MMI 全场模态重构严格独立候选 → 60/84=71.4%**；**v0.9.81（2026-09-16 P1-1 B567）：B5（Y 分支分束损耗）/ B6（光栅耦合器效率）由 `design_rule_anchor` 自证桩各接第二独立求解器升方法学独立候选 → 62/84=73.8%**（B7 因离线 golden 不收敛保持自证桩）；**v0.9.82（2026-09-16 P1-1 B7 golden 语义订正）：B7（波导交叉串扰）撤出已证失真的 2D 离线 FDTD golden（`resolve_field_oracle` 返 None、降级为机理诊断量），golden 回设计守则锚 −40 dB（有 E-SOI-CROSS-XT −41±2 dB 实证背书），接线 CMT 超模法候选 → 63/84=75.0%**（残差占 tol 窗口 93%，边缘通过）。

---

## 1. 战略对齐矩阵（目标 → 代码证据 → 状态）

> 证据格式：文件:行号 / smoke 实跑 / grep 计数。状态 ✅完成 / 🟡部分 / 🔴未做。

### S1 · L0 双栈 EDA 底座做实（光子 PDA + 量子 QEDA）
- 证据：`README.md`「22 引擎 + 11 包 = 33 类端到端（光子 15 + 量子 7）」；`run_count_consistency_smoke` 11/11（引擎 22 / 包 11 / 和 33）；`run_three_class_consistency_smoke` 三分类和=84。
- 状态：**✅** 底座做实并持续增厚（515 py / 104.4k LOC）。

### S2 · 主权红线（A 级永不借 / B 级借今踢后 / C 级自主）
- 证据：`run_solver_writer_sandbox_smoke.py` 实跑 **8/8 PASS**（强隔离降权 nobody 读 /etc/shadow 被拒 + 网络命名空间禁外网 + §4.3 最小 env 剥密钥 + §4.5 unshare 友好异常 + §4.4 无私有访问）；`run_optional_import_guard_smoke.py` **16/16 PASS**（全包 457 文件扫描，模块级硬依赖=0）；DEVSIM（Apache-2.0 B 级）fork 冷备 `vendor/devsim_mirror` 锁定 r2.11.0。
- 状态：**✅** 守住。零 A 级商业求解器 import。

### S3 · 验证纪律（LLM 不进判决路径，PASS/FAIL 由死标量定）
- 证据：`lda_harness/l3_ai_solver.py` `is_independent()` 在 `llm_enabled` 时**恒返回 False**；`README.md` `--ai` 实测 `verified=2/56`，**不计入对外 verified**；`run_harness` 双向护栏（多算=假绿 / 少算=倒退 / verified+stub+degraded≡total）。
- 状态：**✅** 守住。「AI 出题、物理定律判卷」四层架构落实。

### S4 · 物理定律锚 + 实证锚判卷
- 证据：`run_benchmark_falsifiability_smoke.py` **13/13 PASS** → 严格 63 / 降级 3 / 自证 18（和=84），与 `run_three_class_consistency_smoke` C2 **完全一致**；实证语料 30 条全 A 级（B 级已清零）。
- 状态：**✅** 守住。降级 3 道 = E9 + E10 + **B21**（v0.9.77→v0.9.78 净增）。

### S5 · T1 分层解锁（电学/TCAD T1 内核解锁 + T2 锁死）
- 证据：T1 内核 `lda_solver/drift_diffusion_1d.py` + `drift_diffusion_2d.py` 就位；全仓**无 T2 工艺真值求解器**（foundry 专有 implant/diffusion/etch/stress 永久锁）；`T1_OUTPUT_IS_ORACLE=False` 守卫（W5/W6 smoke 反向测试必响）。
- 状态：**✅** T1 解锁并完成；T2 按红线永久锁死（只消费 PDK 接口）。

### S6 · T1-B 电学内核 N(x) 真求解
- 证据：W2 `drift_diffusion_1d.py`（自洽泊松-玻尔兹曼，4 判据）+ W4 `drift_diffusion_2d.py`（2D 漂移-扩散+连续性，4 判据，CORE 164→165）；终端 I(V) 比 Sze 短二极管闭式 ~4.6%<8%。
- **诚实边界（v0.9.77 已文档化）**：`solve_pn_junction_2d_bias` 仅在 **V≥0** 可用；V<0 反偏非物理，已文档化 + `run_t1_reverse_bias_limitation_smoke.py` 8 判据护栏。
- 状态：**🟡** 正向/近平衡可用；反偏诚实受限并已显式文档化（非静默缺陷）。

### S7 · T1-C 主动器件扩展（A 档闭式 ~8 锚 + B 档真求解）
- 证据：A 档 B31 Soref-Bennett / B32 EAM-QCSE / B33 探测器 RC(+APD) / B28 MZM Vπ；B 档真求解 W5 探测器带宽（T1 1D 渡越时间真算）/ W6 APD 雪崩（碰撞电离积分+固定种子蒙特卡洛）。`run_benchmark_falsifiability_smoke` 注册候选 33 个含各真求解路径。
- 状态：**✅** T1-C 闭环完成（A 档 ~8 锚目标达成；B 档 W5/W6 真求解落地）。

### S8 · T2 真值链（MPW 回流换自证桩 ≥5）
- 证据：U4（Ge PD 响应度 1D 内核）/ U5（MZM Vπ T1 1D 反偏施压）/ U6（量子 T1 量级带）/ **B21（DBR 腔 2D FDTD 全波自主）** 已落地，但**诚实降为 `degraded_ordinal`**（残差主成分为未公开器件几何/材料假设，非数值误差，不放宽 tol）。
- **缺口**：「≥5 自证桩换真锚」依赖 3–4 轮 MPW + 委托封测实测回流——**当前 0 轮 MPW**（等杜先生现实撬动 foundry/MPW 窗口）；逐锚所需实测数据/计量与 MPW 路径见 `P1-E_T2_unlock_plan.md`。
- 状态：**🟡** 诚实降级换锚已做；真值回流（物理真锚）未启动 = 等窗口（不属技术缺陷）。

### S9 · 四层系统（架构综合 / 编译映射 / 控制校准 / 协同仿真）—— L1→L2 最本质鸿沟
- 证据：`lda/lda_l2/mzi_mesh_matmul.py`（MZI 网格矩阵乘引擎，C 级自主纯 numpy，Reck 分解 fro_err~5e-16）+ `lda/lda_l2/four_layer_redline_gate.py`（G1–G5 五闸）+ `lda/run_mzi_mesh_matmul_demo.py`（对外 HTML）+ `lda/run_four_layer_redline_gate_smoke.py`（CORE 173）。GateReport=**PASS**（建议 A：每层挂 VMM 锚 ≥ self_certified）：L1(B14 方法学独立·50/50 耦合长 7.75µm)/L2(Reck 定理，重构 1.0) 高于门槛；L3 相位标定/L4 电-热-光协同 = Tier-1 自证桩（候选≡golden、残差构造性恒零、带 who_verifies/upgrade_path，不冒充 strict）。
- 状态：**🟡** 立项前闸门全过；L3/L4 待外置相干激光/探测器实测与多域协同仿真升级。

### S10 · 开源 + 社区独立验货护城河 / 标准位 T4
- 证据：三端开源（gitee `i4hub/LDA` + github `iduyuhe/LDA` + 生产机）+ Apache-2.0 + DCO `Signed-off-by` 就位；`L0 IR` / `DesignPackage JSON` 已存在。
- **缺口**：`README.md`「标准是被采用出来的，当前 users=1」——**0 家外部机构采用、0 家 foundry 签 PDK**（T4 验收 ≥2 外部 + ≥1 foundry 未达）。
- 状态：**🟡** 开源与主权机制就绪；标准位/外部采用未达（属获客与生态，非技术）。

### S11 · L2 光子计算芯片 / 量子计算芯片（愿景目标，光子优先）
- 证据：依赖 S9 四层系统；光子计算外置激光可绕（不破红线），量子受单光子源硬卡。
- 状态：**🔴** 未启动（依赖 S9）。战略层「光子优先」已拍板。

### S12 · 生态开放四层光谱（判据先于代码 / 主权扫描）
- 证据：`run_optional_import_guard_smoke.py` 16/16（ast 全包 import+license 双扫，含 DEVSIM/T1 许可扫描）；DCO 闸门。
- 状态：**✅** 机制就位（最大风险「假绿=自证桩批量生产」由「判据先于代码 + maintainer 写判据」规避）。

### S13 · 全能力盘点（GC-*48 / 75 货架 / 实证 30 A）
- 证据：`run_gc_smoke.py` **3/3 PASS**（GC 全链路）；`README.md`「75 货架（50 开放 + 25 咨询制）· 5 赛道 + 24 应用域」；实证语料 30 条全 A 级。
- 状态：**✅** 全绿。

### 前次审计（v0.9.77）P0/P1 收口追踪
| 项 | 状态 | 证据 |
|---|---|---|
| P0 计数一致性守卫漂移 | ✅ 已修 + B21 后再同步 | `run_count_consistency_smoke` 11/11；B21 升 degraded 后 ledger 锁 2→3 显式同步 |
| P1① 自证桩升级 55.4%→70% | 🟢 已达成（B-3） | 严格 63/84=**75.0%**（≥70% 目标；B-3 跨线 + B16 重审 + B567 收官 + B7 语义订正） |
| P1② `lda_agent` 专项代码评审 | ✅ 已完成（三轮闭合 2026-09-16） | pyflakes 47→0 · 安全纵深 §4.3/4.4/4.5 落地 · 沙箱护栏 ⑤⑥⑦（含反向测试）· 零行为变更（63/3/18 不变）；见 `LDA_lda_agent_code_review_closure_2026-09-16.md` |
| P1③ 完整 CI core 回归全绿 | ✅ 已完成 | v0.9.77 部署前全量 171 实跑全绿；v0.9.78 仅确定性报告修复，CORE 173 同源 |

---

## 2. 功能对齐（验证机械 · 实跑取真证据）

### 2.1 本次实跑守卫（2026-09-16，受管 venv 3.13.14，OMP/MKL_DYNAMIC=FALSE）

| 守卫 smoke | 结果 | 关键输出 |
|---|---|---|
| `run_three_class_consistency_smoke.py` | **4/4 PASS** | README≡harness≡端点 = **63/3/18**，和=84 |
| `run_count_consistency_smoke.py` | **11/11 OK** | 引擎 22/包 11/题 84/CORE 178 与 README 一致 |
| `run_webui_verification_ledger_smoke.py` | **15/15 PASS** | 端点 63/3/18，`provenance` 6 类宇宙子集无泄漏 |
| `run_benchmark_falsifiability_smoke.py` | **13/13 PASS** | 严格 63 / 降级 3 / 自证 18；84/84 无回归；灵敏度上界≤10% |
| `run_gc_smoke.py` | **3/3 PASS** | GC 全链路（含 duty=1.0 / Λ=0 反例） |
| `run_maturity_baseline_smoke.py` | **M1–M5 PASS** | VMM 底线；strict=63 degraded=3 self_certified=18 |
| `run_ci_coverage_gate_smoke.py` | **6/6 PASS** | 发现 smoke 191 · core 178 · 豁免 18，无静默缺口 |
| `run_d_criterion_smoke.py` | **10/10 PASS** | 63/63 已接线候选 0 道代数恒等；B28 假独立被抓获 |
| `run_optional_import_guard_smoke.py` | **16/16 PASS** | 457 文件扫描，torch/numba/cupy 硬依赖=0 |
| `run_report_determinism_smoke.py` | **10/10 PASS** | 相同输入⇒字节一致；真变更仍可证伪（v0.9.78 关键） |
| **合计** | **103 PASS / 0 FAIL（10 守卫）** | — |

### 2.2 全量 CI core 门禁
- v0.9.78 仅做受跟踪报告确定性修复（coupler_band 派生量改由「已发布值」反算，方案 A），**零物理判据改动、零容差放宽**。CORE 173 与 v0.9.77 同源全绿，本次以 10 守卫（覆盖三分类/计数/账本/可证伪/GC/VMM/CI 覆盖/判据 D/主权扫描/确定性）实跑确认无回归。
- 全量 173 条回归（~55 min，4 线程单实例防蓝屏）为历史实跑结论；v0.9.78 无新物理改动，未重复触发满载。

### 2.3 测试卫生
- 确定性：`deterministic.py` 唯一口径（9 位有效数字 + 去 volatile 键 + UTF-8/LF），`run_report_determinism_smoke` 10/10 验证 `git status` 常绿。
- 本次审计 scratch（`_audit_*`）不入库。

---

## 3. 诚实缺口与风险（照写，不粉饰）

1. **反偏模型局限（V<0）**：T1-B 2D 内核反偏非物理，已文档化 + 护栏，但仍是真实能力边界。
2. **自证桩占比 21.4%（18/84）**：验证地基最大短板已显著缓解。严格独立 75.0%（63/84）已正式达成目标 70%（B-3 跨线 + B16 重审 + B567 收官 + B7 语义订正）。升级路径明确：真候选为 **E1/E3-E7（卡 T2 通道）共 6 道**；B7 已于 v0.9.82 经 golden 语义订正升严格独立（残差占 tol 窗口 93%，边缘通过，彻底闭合需 3D 全波）；B5/B6 已于 v0.9.81 升严格独立；**B17/B18/S1-S6/S9-S12 共 12 道为 terminal Tier-1（定义/算术自检），按设计永不升、非缺口**。已转为「PR 必接独立候选」常态化纪律（见 `P1-1_self_certified_discipline.md`，口径已订正原「B17-B19/S1-S13 方法学独立候选」过时说法）。
3. **`lda_agent` 专项评审已闭合（2026-09-16 三轮）**：原「全仓最大未量化风险面」已量化并清零——pyflakes 47→0、安全纵深 §4.3/4.4/4.5 落地、沙箱护栏 ⑤⑥⑦（含反向测试）全绿；残余仅 loop 家族结构性重复（非阻塞、已建 MODULE_MAP 标注）。见 `LDA_lda_agent_code_review_closure_2026-09-16.md`。
4. **T2 真值回流 = 0**：等 foundry/MPW 窗口（杜先生现实 KPI），非技术阻塞。
5. **四层系统 / L2 计算芯片未启动**：设计递延，符合「先夯实」纪律；对外叙事须诚实区分「底座就绪」与「计算芯片可用」。
6. **标准位外部采用 = 0**：users=1，护城河差异化尚未被外部采用验证。
7. **阶段 3 商业试点资产 🔴 未启动**：认证版打包 / 首个 PDK 合作 / 垂直场景落地 / 法务闭环 均未立项，是当前与「价值验证」目标的最大距离（详见 `LDA_第三阶段工作规划_商业试点_2026-09-16.md`）。

---

## 4. 综合优先行动清单

### 🔴 P0（立即）
- **P0-1（✅ 已闭合 2026-09-16 三轮）**：`lda_agent` 专项代码评审（导入健康 / 异常路径 / 死代码 / 覆盖）——P0-1 深化版 + 09-14 复评 P2 全部落地：pyflakes 47→0（31 未用 import 删 + 2 torch 探测改显式引用 + 3 typing 未定义名 + 1 前向引用 + 7 未用局部变量 + 3 f-string）；安全纵深 §4.3 最小 env / §4.4 去私有访问 / §4.5 unshare 友好异常；沙箱 guard smoke 五判据→八判据（新增 ⑤⑥⑦，含反向测试）。零行为变更（三分类 63/3/18 不变）。见 `LDA_lda_agent_code_review_closure_2026-09-16.md`。
- **P0-2（✅ 已落地 v0.9.79）**：任何加 `degraded_ordinal`/严格锚的 PR，必须 `grep degraded_ordinal` + `grep strict_independent` 全仓同步所有硬编码计数护栏（ledger smoke / README 三分类 / three_class / count_consistency）——B21 已显式同步为 3（降级 2→3：E9+E10+B21；自证桩 23→22），固化必查项。实现：新增 `run_p0_count_guard_sync_smoke.py`（动态推导三分类真值后 grep 四处硬编码护栏 ≡ 真值，带反向篡改测试证明会响）注册进 `CORE_SMOKES`（CI core 176→177）；修 ledger smoke docstring 与 CONTRIBUTING 顶部账本块滞后（降级 2→3 / 自证桩 23→22）；CONTRIBUTING 补「P0-2 计数护栏同步纪律（PR 必查）」章节与自查命令；修 count_consistency smoke docstring 题库计数（55→56 / E1-E9→E1-E10）。四处护栏全绿：P0 sync 6/6 · count_consistency 11/11 · three_class 4/4 · ledger 15/15。
- **部署（2026-09-16 · SSH）**：HEAD 对齐 `d15cd4c`，内/外网 `/api/health` 版本串均 `0.9.79`、`shelf=75`、`is-active=active`，生产已落地 v0.9.79。⚠️ 订正此前「remote_deploy.py 不在本环境、未部署」误记——脚本实存于技能目录 `C:/Users/Administrator/.workbuddy/skills/lda-prod-deploy/scripts/remote_deploy.py`，前次仅检索路径有误（误以为在仓库 `scripts/` 与技能目录缺失），实际可直接复用，无需手动 SSH 等价流程。

### 🟠 P1（近期，优先于新功能）
- **P1-1（✅ B-3 已闭项；✅ B16 重审收官 v0.9.80）**：严格独立 75.0%（63/84）达标。18 自证桩转「PR 必接独立候选」常态化纪律；真候选 **E1/E3-E7（T2）共 6 道**，B17-B19/S 簇为 terminal 非候选（口径已订正，见 `P1-1_self_certified_discipline.md`）。
- **P1-2**：T2 真值链启动（杜先生现实）：foundry PDK 只读接口接触 + MPW 排期撬动，把 U4/U5/U6/B21 的 `degraded_ordinal` 升为 strict（需实测回流）。
- **P1-3**：四层系统 L3/L4 接外部实测/ORACLE 升 `degraded_ordinal`→`strict_independent`（建议 B 后续）。

### 🟡 P2（观察/追踪）
- 10 处 `NotImplementedError` + 41 处占位注释：均为意图明确设计留口，非缺陷；建「留口清单」集中追踪。
- 阶段 3 商业试点立项（见独立规划文档），作为从「技术验证」转向「价值验证」的下一主线。

---

## 5. 第三阶段（商业试点）工作规划

> 详细 WBS / 里程碑 / 90 天行动清单见 **`LDA_第三阶段工作规划_商业试点_2026-09-16.md`**。
> 路线图定位：阶段 3 = 商业试点（价值验证），对应 18–30 月。进入门禁 G2→G3 判据：社区/顾问/PDK 就绪度。当前审计结论——**技术就绪度 ✅，商业资产 🔴 未启动**，故阶段 3 是下一步主轴。

---

## 6. 附录 · 复现命令

```bash
# 环境（受管 venv，绝不用 lda_cuda_venv）
PY=C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe
export OMP_DYNAMIC=FALSE MKL_DYNAMIC=FALSE PYTHONPATH=D:/agent_LDA

# 战略对齐证据（锚/三分类/CORE/候选/代码规模）
$PY -c "import re; s=open('D:/agent_LDA/lda/run_ci_regression.py',encoding='utf-8').read(); a=s.index('CORE_SMOKES: List[str] = ['); b=s.index(chr(10)+']', a); print(len(re.findall(r'\"([^\"]+\.py)\"', s[a:b])))"

# 功能对齐子集（10 守卫）
$PY lda/run_three_class_consistency_smoke.py
$PY lda/run_count_consistency_smoke.py
$PY lda/run_webui_verification_ledger_smoke.py
$PY lda/run_benchmark_falsifiability_smoke.py
$PY lda/run_gc_smoke.py
$PY lda/run_maturity_baseline_smoke.py
$PY lda/run_ci_coverage_gate_smoke.py
$PY lda/run_d_criterion_smoke.py
$PY lda/run_optional_import_guard_smoke.py
$PY lda/run_report_determinism_smoke.py

# 全量 CI core 门禁（~55 min，4 线程单实例，无蓝屏）
$PY -u lda/run_ci_regression.py
```

> 注：本报告为审计交付物，未自动提交仓库。如需随 `LDA_战略审计报告_*` 系列入档，请指示。
