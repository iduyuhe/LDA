# Changelog

## v0.9.14（2026-09-02 · P0-1 锚题独立候选化 · 反自证桩第一刀）

**指令**：战略审计（v0.9.13 基线）后，杜先生拍板 E1=A「锚题独立候选化」，开工 P0。

**起因（2026-09-02 战略审计实测）**：
- 48 锚实跑 48 PASS，其中 **47 道是自证桩**——`build_harness_specs` 对所有非实证锚
  一律落 `_harness_reference_candidate`（直接返回 golden），|cand−golden| ≡ 0 恒 PASS、零验证价值。
- 结构性缺陷：**B 类 28 道连"接入独立候选"的入口都没有**（只有 E 类能指定 `candidate: "fdfd_ng"`）。
- **全绿 ≠ 可证伪**：84/84 全绿与 47/48 自证桩并不矛盾，前者只证明无回归。

**改动（P0-1 · 4 道真独立候选）**：
1. **首开 B 类接入口**：`verification_adapters.py` 新增 `BENCHMARK_CANDIDATES` 注册表 +
   `_register_candidate` 装饰器；`build_harness_specs` 按 `BENCHMARK_DEFS[x]["candidate"]`
   查表分发（未登记者诚实保留自证桩，不假装已独立）。
2. **接通 4 道**（golden=解析闭式 ↔ candidate=严格数值对角化，方法学独立）：
   | 锚题 | golden | 独立候选 | 实测偏差 | tol 变更 |
   |---|---|---|---|---|
   | **B9** | Koch 色散近似 | 电荷基严格对角化（41 维 eigh） | rel 0.22% | 0.05（原就合理，未动） |
   | **B25** | Koch(Φ) | 同上（E_J(Φ)） | rel 0.22~0.40% | 1e-6 → 0.05 |
   | **B26** | Blais 微扰闭式 | L=6 多能级+Fock 联合对角化（162 维 eigh） | rel 1.98% | 1e-6 → 1e-4 |
   | **B27** | t_CZ=π/(2\|χ\|) | 严格 χ 反推 | rel 2.02% | 1e-6 → 30ns |
   - tol 放宽依据：实测偏差的 **2.2~2.5 倍余量**，逐条写入 note（不拍脑袋）。
   - 🔍 顺带实证：**B9 的 tol=0.05 是早期按物理容差设的**，恰好合理；B20–B28 后期锚清一色
     `tol=1e-6`——该量级设计上只容得下 candidate≡golden，即"自证桩容差"。
3. **`candidate_status` 字段**：把「降级量级参考」（E2，FDFD 直波导候选 vs 环 golden 几何不同源）
   从散文 note 变为**机器可读**，杜绝用已降级锚充数虚报独立强度。

**新增常驻护栏 `run_benchmark_falsifiability_smoke.py`（入 CI core，84→85）**：
- ① 独立候选数下限（当前 4，随进度递增）② 正向 PASS ③ **反向测试：10% 参数扰动必 FAIL**
  ④ 灵敏度登记（最小可检出扰动）⑤ 全量 48 锚无回归 ⑥ 披露剩余自证桩清单。
- **为什么③比②重要**：②只能证明"没坏"，③才能证明"坏了能发现"。只做②不做③，
  等于把「放宽容差」变成「取消验证」——正是自证桩的翻版。

**⚠️ 诚实边界（反向测试实测暴露）**：
- **B26 在 g 扰动 +1% 处 diff=1.68e-6，反而小于未扰动时的 4.57e-5** —— 扰动方向与
  （闭式↔数值）近似误差**偶然抵消**。属物理正常现象，但意味着**小幅系统误差存在检测盲点**，
  这是放宽容差所付的代价 → 反向测试取 10% 稳健档（该档 4 道全 FAIL），而非单点小扰动。
- **B27 与 B26 共用同一数值 χ**，独立性弱于 B26，只验证「χ→t_CZ 换算链路」，不重复计入独立强度。
- 灵敏度实测：B9 ≤2%、B25/B26/B27 ≤5%（断言上界 ≤10%）。

**验证**：独立候选 0→**4 道**（严格独立，E2 另计为降级量级参考）；48 PASS / 0 FAIL，耗时仍 1.1s；
关键 smoke 全绿（harness 48/48、实证锚 29/29、计数守护 11/11、新冒烟 6/6、
benchmark crosscheck / quantum design / quantum devices / device_library / statistical 均 EXIT=0）。

**⚠️ 作用域澄清（重要，避免高估本轮成果）**

LDA 存在**三条验证路径，各自用不同 candidate**，本轮改动**只覆盖第 ① 条**：

| # | 路径 | candidate | 使用方 | 本轮后状态 |
|---|---|---|---|---|
| ① | `build_harness_specs` + `cand_map` | 按题查表分发 | `run_empirical_anchor_smoke`、新增的 `run_benchmark_falsifiability_smoke` | ✅ **4 道独立**（B9/B25/B26/B27） |
| ② | `harness.run(specs, ReferenceCandidate)` | 恒定 `return golden` | **`run_harness.py`（对外主报告）** | ❌ 仍全自证，`verified=0` |
| ③ | `L3AISolverCandidate` → `_local_approx` | 未配置 LLM 时回退；41 道 `return golden` | **MCP / L1 协议 / WebUI** | ❌ 仍全自证 |

- 因此「48 锚中 4 道可证伪」**仅在路径①成立**。对外验货面走的是 ②③，仍显示 `diff=0`。
  报告里 `verified=0` 在 ②③ 下是**准确的**（不是失真），因为它如实反映那两条路径仍是自证。
- 接线成本很低（② 只需一个按 `spec_id` 路由的适配器，约 15 行；`harness.run` 已接受
  `callable(spec, golden, params)`），但会改变对外报告与 `run_harness.py:117` 的
  `verified==0` 断言 ⇒ **登记 P0-2，本轮不动**（回归在跑，不叠加改动面）。

**未做（按 P0 计划顺延）**：剩余 **43/48 仍为自证桩**（全部 S 类 13 道 + E1/E3-E7 +
B1-B8/B10-B24/B28），需继续接线；E2 建议的 numpy 版 DC/YB 候选（E2 决策点）未动。

**🔴 本轮顺带挖出：第二条自证桩路径（登记为 P0-2，本轮不动代码）**

改动 B25/B26/B27 的 tol 后复跑，发现 `lda/reports_mcp/verification_report.md` 里这三道
**diff 仍是 0** —— 该报告头部写明 `candidate：L3AISolverCandidate`，走的是**不同于**
`build_harness_specs` 的第二条验证路径（`lda_harness/l3_ai_solver.py`）。

- 机制：`L3AISolverCandidate` 未配置 LLM 端点时回退 `_local_approx()`，而该函数
  **只对 B1/B2/B3/B4/B8/B9/B10 七道有实现**（其中 B2/B8/B9 还是**故意**写错以演示
  harness 的 FAIL 判别能力），**其余 41 道一律 `return golden`** ⇒ diff=0、全 PASS。
- 影响面：该路径被 **`lda_webui/app.py:356`** 与 `lda_l1/protocol.py:121` 直接使用，
  **对外可见** —— 外部验货者看到的「全 PASS + diff=0」实为自证，非验证。
- 性质判定：这条是 **L3「AI 写内核」的演示/沙盒路径**（设计意图是演示 harness 判别能力，
  非判决路径），与 harness 判决路径性质不同；但因其对外暴露，存在误导风险。
- 处置：**登记 P0-2，本轮不动代码**（回归在跑，不叠加第二处改动面）。
  待办方向：①默认分支改为显式"未实现"并返回非 golden 的哨兵值
  ②报告头部标注「演示/沙盒路径，非判决结论」③或限制其不对外暴露。

**P0-2 合并规划（路径 ②③ 接线，下一轮）**：
- ② `run_harness.py`：默认 candidate 从 `ReferenceCandidate` 改为**路由适配器**
  （按 `spec_id` 查 `build_harness_specs` 的 `cand_map`，未登记者回退 `return golden`），
  同步把 `run_harness.py:117` 的 `verified==0` 断言改为 `verified>=1`（动态取独立候选数）。
  ⇒ 对外主报告首次显示真验证（`verified=4`），这是「可被外部验货」战略的直接兑现。
- ③ `l3_ai_solver._local_approx`：默认分支改为显式未实现哨兵值 + 报告标注演示路径。
- 预期收益：可证伪锚题在**对外验货面**从 0 → 4（当前仅内部路径可见）。

---

## v0.9.13（2026-09-01 · R16 实测证伪 + 诚实边界 C 降级）

**指令**：开始 R16 阶段1（sub-cell 体积分数 averaging），实测证伪原假设，杜先生拍板 C 诚实边界降级。

**R16 阶段1 实测结论（重大反向）**：
- 在 `build_waveguide_field_3d` + `fdfd_neff` 启用 sub-cell averaging（界格点 ε 按芯/包层体积加权），
  用 corpus golden 同源几何复跑 FDFD 对照：SOI n_g **3.776→3.741 恶化**、SiN n_g **1.961→1.928 恶化**；
  D-65 窗口散射 SiN ±0.0385→±0.0018（改善）、SOI ±0.0215→±0.0305（略恶化）。
- 网格 dl_factor 24→64 扫描：n_g **纹丝不动**（SOI~3.72 / SiN~1.93），偏差与网格无关。
- 直波导 n_eff 直检：SOI=2.62（文献~2.44，+0.18）/ SiN=1.61（文献~1.98，−0.37）→ **求解器本身精度不足**。
- 🔴 两层根因（均非网格）：①最简标量 FDFD 对高反差细波导 n_eff 偏差 0.18~0.37；②**对象不对齐**：
  golden 4.18/2.2834 是**弯曲/环器件**群折射率（Garrisi 用 ring FSR 反演；E-SIN 是 R=100µm 环），
  FDFD 解直波导，弯曲使模式更受限→n_g 天然高 ~0.46。
- **R16 原假设（「网格过粗导致偏差，上 averaging/细网格解锁 E1/E2/E3」）被实测证伪**。
  sub-cell averaging 单独使用恶化绝对精度且无净收益（D-65 窗口散射原本就 <±0.04 达标）。
- 纪律：averaging 两处**回退**（工作区源码干净），**不提交实验态假绿**。
- 附：D-65 原「网格过粗」诊断不实——±0.042 实为**窗口扫描**散射非网格（dl 24→64 已收敛）。

**C 诚实边界降级（杜先生拍板）**：E1/E2/E3 的 golden 来自环器件，FDFD 直波导候选与之
「量纲同源、几何不同源」+ FDFD 求解器精度不足 → 仅作量级参考，不参加死标量对照；
E1 保持自证桩（candidate≡golden）。与 D-66 诚实边界一致。

**代码/文档同步（不假绿，全部改注记/诚实边界，不改判决逻辑）**：
- `benchmarks.py` E1/E2 note：R16 由「待根治」改为「已证伪 + 诚实边界 C」
- `run_empirical_anchor_smoke.py` D-65 护栏注记：R16 已证伪
- `lda_webui/routes.py` open_gaps R16：标注已证伪 + 与战略审计 R16（单人瓶颈）编号撞车提示
- `benchmark_report.py` Waveguide empirical_dim_note：扩展为量纲+几何不同源 + FDFD 精度不足 + R16 证伪
- `docs/lda_d64_replication_feasibility.md`：R16「最高杠杆一次性解锁 E1/E2/E3」改为已证伪
- 注：战略审计文档的 R16 = 单人瓶颈（商业模式），与此处 FDFD 缺口 R16 编号撞车，已分别标注

**验证**：全量 core 回归 84 PASS / 0 SKIP / 0 FAIL；empirical_anchor_smoke / D-65 护栏仍 PASS

## v0.9.12（2026-09-01 · CI 达标线政策化：80% → 90%+）

**指令**：CI 达标线随语料补充逐步上调至 90%+。

**改动**（治理向，不影响引擎逻辑、不影响生产运行时行为）：
- `lda/run_provenance_audit.py`：`--min-ratio` 默认由 **0.80 → 0.90**。
  这是审计脚本的**宽松下限基线**；当前语料库 A 级占比 100%（30/30），90% 基线轻松达标。
- `lda/run_empirical_anchor_smoke.py`：注释明确达标线演进政策——
  **80% → 100%（B 级零容忍）**，且当前下限 90%+、强制门禁 100%。

**纪律澄清（🔴 不回退）**：
提交门禁（硬 gate `traceable_ratio >= 1.0`）**维持 100% 死守**，不下调到 90%。
理由：实证锚是「第二道非 AI ground」，其可信度完全建立在可独立复验上，
任何一条 B 级语料混入都会稀释该 ground。90%+ 仅是审计宽松基线，
CI 提交门禁的强制线仍是 100%（B 级零容忍）。

**验证**：溯源审计（默认 0.90）达标 ✅ · 实证锚 smoke 29/29 PASS ✅ · 计数守护同步版本线。

## v0.9.11（2026-09-01 · D-67 回归修复 · 链路预算漏算 3.0103dB 分光 + 双护栏）

🔴 **v0.9.10（D-66）引入了一个「假绿」回归，本次修复并加装护栏。**

**根因**：D-66 判定「3.01 dB 是 1×2 功率均分的几何必然、非器件品质指标」——**这个判定本身是对的**，
但实现时把 `engine_ybranch_split` 的默认输出 `value` 从「含分光的分支插损 `split_loss_dB`」
直接改成了「过量损耗 `excess_loss_dB`」。而该引擎的 `value` **同时是链路预算的被加数量**
（`golden_product_benchmarks._photon_cascade_il` 的 `n_yb * yb`），于是**每个分束器少算 3.0103 dB**。

**影响面（5 条整芯片链路 + 1 条器件级，全部静默）**：

| 条目 | 修复前（v0.9.10 漏算） | 修复后（正确） | 偏差 |
|---|---|---|---|
| GC-PLC-1X8（3 级分光） | 0.33 dB | **9.3309 dB** | −9.0 dB |
| GC-PLC-1X16（4 级分光） | 0.44 dB | **12.4412 dB** | −12.0 dB |
| GC-SENSE（2 级） | 7.63 dB | **13.6508 dB** | −6.0 dB |
| GC-QKD-TX（2 级） | 7.54 dB | **13.5638 dB** | −6.0 dB |
| GC-CPO-8CH（1 级） | 7.62 dB | **10.6335 dB** | −3.0 dB |
| GP-YBRANCH | 0.10 dB（拿过量损耗比总插损 golden 3.15） | **3.1103 dB** | 语义错配 |

**为何 84/84 全绿没抓到（三重失真叠加）**：
1. 插损类 metric 方向为 `le`（**越小越 PASS**）→ 「少算损耗」被伪装成「设计做得更好」；
2. `run_golden_product_smoke` 只校验 PASS **条数**，不校验死标量数值；
3. `ProductBenchmark.evaluate` 在 metric 名对不上时**静默回退**到 `out["value"]`
   → 「拿 A 量比 B golden」不会报错。

**修复（原则：分离而非替换 —— 两个量都真实存在，各归其位）**：
- `engine_ybranch_split` 同时输出两个**互斥且互补**的量：
  `value`/`metric` = **`split_loss_dB`**（链路预算量 = 3.0103 + 过量，向后兼容）；
  `excess_loss_dB` 以**同名字段**显式暴露（器件品质量，供实证锚对照）。
  新增模块常量 `SPLIT_LOSS_3DB = −10·log₁₀0.5 = 3.0103`。
- `resolve_corpus_engine` 改**按 metric 名取值**（不再一律取 `"value"`）。
- `_loss_verify` / `_loss_cheap` 新增 `field` 参数；`YbranchLoss` 显式传
  `field="excess_loss_dB"`，使「搜索目标 / 判决量 / golden」三者同量纲。

**新增两道护栏（均已做反向测试，证明会响）**：
1. **能量守恒下界**（`_photon_cascade_il`）——每个 1×2 分束器的每支路插损不可能低于
   3.0103 dB（能量守恒，与工艺水平无关）。⚠️ 关键设计：必须**按贡献项逐项守底**，
   不能用「总插损 ≥ n_yb×3.0103」——反向测试证明混合判据会让 GC-CPO-8CH / GC-SENSE /
   GC-QKD-TX 三条因其他损耗垫高而**逃逸（只抓住 2/5）**；逐项守底才 5/5 全抓。
2. **metric 语义错配硬失败**（`ProductBenchmark.evaluate`）——MetricSpec 声明的量在
   引擎输出里既不是主 metric 也不是显式字段时，**禁止静默回退到 `value`**，直接报错
   （宁可红，不可假绿）。

**护栏的护栏**：`run_golden_product_smoke` 新增 **D-67 反向测试**——临时注入「漏算分光」
的坏引擎，断言两道护栏都命中（能量下界 5/5 + 语义错配 1/1），否则 smoke 直接 FAIL。
**没被验证过的护栏不算护栏。**

**同步改动**：`run_loss_engine_smoke` 新增 2 条引擎层双量语义 + 能量守恒断言（7→9 条，9/9 PASS）；
`design_engine.YbranchLoss` note / `loss_engines` 模块 docstring 如实标注双量不可混用。

🔴 **工程铁律（新）**：**改引擎默认输出 `value` 的语义前，必须 grep 全部 `["value"]` 消费点**，
而不只是同步改断言；**「越小越 PASS」的方向性 metric 必须配物理下界护栏**，
否则「算漏了损耗」会被伪装成「设计变好」——这是失真最隐蔽的一类回归。

## v0.9.10（2026-09-01 · 实证锚逐字核实 · D-66）

**指令**：5 条 B 级语料（E-SOI-NEFF-220 / E-SIN-NEFF-300 / E-YBRANCH-LOSS / E-RING-FSR / E-GRATING-EFF）**逐字核实**补 DOI/URL 才能升 A 级。纪律：**不编造 DOI、找不到就保持 B 级**。

**结果：语料库 A 级 25/30 → 30/30（100%），B 级清零；可溯源实证锚题 6/7 → 7/7。**

| 原 ID | 原 metric / 值 | 核实结论 | 处置 | 新值（可溯源出处） |
|---|---|---|---|---|
| E-SOI-NEFF-220 | n_eff 2.63 | **原值是错的** | 改判 n_g 锚 → `E-SOI-NG-220` | n_g **4.18±0.05**（DOI 10.48550/arXiv.2011.03273） |
| E-SIN-NEFF-300 | n_eff 1.53 | 无可溯源实测出处 | 改判 n_g 锚 + 按文献照实改写几何 → `E-SIN-NG-1200` | n_g **2.2834±0.05**（DOI 10.3390/coatings10040309） |
| E-YBRANCH-LOSS | split_loss_dB 3.4 | **量纲不符** | 改判实测**过量损耗** | excess_loss_dB **0.28±0.02**（DOI 10.1364/OE.21.001310） |
| E-RING-FSR | FSR_nm 9.15 | **系解析反算值**，非测量 | 换文献实测值 | FSR_nm **8.6±0.1**（arXiv:2011.03273，racetrack L=66.8 µm） |
| E-GRATING-EFF | coupling_eff 0.45 | 无出处 | 换文献实测值 | coupling_eff **0.42±0.05**（DOI 10.1063/1.3304791） |

**逐字引用（证据链，原文照抄）**

- E-SOI-NG-220 / E-RING-FSR：`"The resonator has the shape of a racetrack, it is 66.8 um long and its free spectral range (FSR) is 8.6 nm, from which we infer that its group index is 4.18."`
- E-SIN-NG-1200：`"The free spectral range (FSR) measured from the transmission spectra given in Figure 4b was estimated as 1.61 nm that resulted in the effective group index ng = 2.2834."`
- E-YBRANCH-LOSS：`"Measured average insertion loss is 0.28 ± 0.02 dB, uniform across an 8-inch wafer."`
- E-GRATING-EFF：`"A peak coupling efficiency of 42% at 1550 nm and 1 dB bandwidth of 37 nm, as well as a low back reflection, are achieved."`

**自洽校验**：λ²/(n_g·L) —— SOI 1547.6²/(4.18×66.8×10³)=**8.59 nm** ≈ 实测 8.6 ✅；SiN 1550²/(2.2834×640.3×10³)=**1.64 nm** ≈ 实测 1.61 ✅

### 三个「差点踩进去」的坑（方法论教训，价值高于结果）

1. **差点把仿真值当实测值**：arXiv:1909.09538 的 `−3.05 dB ~ −3.15 dB` 看似完美实测，逐字核对前文是 **`"This simulation is shown in Fig. 5"`** → **已排除**。只看数值不看上下文，会让两道 ground 短路，判决即自证。（PDF 经 curl 下载 + pypdf 提取才读到，WebFetch 三次失败。）
2. **metric 量纲陷阱**：Y-branch 的 3.4 dB 是**含 3.01 dB 理想分光的分支插损**，而文献实测的 0.28 dB 是**过量损耗**。3.01 dB 是 1×2 功率均分的**几何必然**（−10·log₁₀0.5），**非器件品质指标、非被测量的量**。直接拿 3.4 对 0.28 会得到一个量级的"偏差"，但那不是模型错了，是量纲错了。
3. **原 golden 本身就是错值**：`E-SOI-NEFF-220` 的 2.63 与文献及 **3 个独立模式求解器**一致结论（2.44~2.46）差 **0.19**（为其自称 ±0.02 的近 10 倍），2.63 实为 λ≈1.39 µm 处的取值。这类错误在"看上去合理"的数值上最难发现——**它不报错，只让所有对照系统性偏移**。原值存疑证据链保留在新 `note` 字段，不静默丢弃。

### 配套工程改动

- `EmpiricalMeasurement` 新增 **`note`** 一等字段（溯源核实批注；**判定路径不读**，仅作证据链，不影响任何死标量比较）。
- `loss_engines.engine_ybranch_split` 改为**只输出过量损耗**（剔除 3.0 dB 常数），与既有 `E-MMI-1X2-EL` 口径一致；`design_engine.YbranchLoss` / `design_package` 目标值 / `benchmark_report.DEFAULT_TARGET` 三处同步 3.4→0.28、0.45→0.42。
- B5 设计守则锚**保留不动**（理想 50/50 下限 3.0 dB），note 增 D-66 澄清：它与实证锚的过量损耗**非同一量、互补不可混用**。
- `benchmark_report` Waveguide 行：引擎输出 **n_eff**、语料实测 **n_g** → **量纲不同源如实披露**（`empirical_dim_note`，报告渲染带 ⚠️ 行），不假装同 metric 对照。
- 语料库 A 级达标线 **80% → 100%**（提交门禁已强制 A 级，存量不应再出现 B 级；实证锚可信度完全建立在可独立复验上，零容忍）。
- 下游同步 8 处：`benchmarks.py`(E1 锚) / `benchmark_report.py`(3) / `loss_engines.py`(2) / `design_engine.py`(2) / `design_package.py`(3) / `run_empirical_anchor_smoke.py`(4) / `run_d06_smoke.py`(5) / `run_loss_engine_smoke.py`(3) / `run_empirical_d62_report.py`(1) / `corpus_template.csv`。

### 🔴 顺带修掉：GitHub Actions 主干自 v0.9.8 起一直红灯

`empirical_bank.traceability()` 用 `from .provenance import ...` 相对导入，而 **ci.yml 以脚本方式直跑**（`cd lda/lda_harness && python run_empirical_bank.py`）→ `ImportError: attempted relative import with no known parent package`。该脚本 **不在本地 `CORE_SMOKES`**，故**本地全绿、主干红**（v0.9.8 D-63 引入）。修复为双路导入（包内相对优先，回退绝对），并**把该脚本纳入 core 门禁**（CI core 83→84），这类缺口今后由本地兜底。

> 又一次印证两条铁律：①**改判定/公共字段时，把依赖它的 smoke 一起改**；②**「宣称全绿」必须有近期实跑证据支撑**——本地 core 覆盖不到的脚本，等于没有门禁。

### 底数变化

语料 **30 条（A 级 30/30 = 100%，B 级 0）**· 可溯源实证锚题 **7/7** · 题库 48 题不变 · **CI core 83 → 84 条**。

### 诚实边界（不掩饰的缺陷）

1. **E-GRATING-EFF 结构不同源**：文献器件为**全刻蚀光子晶体孔阵**（孔径约 143 nm），与参数化周期光栅**非同一结构**；仅作量级对照，geometry **不构成 golden 判决输入**。
2. **n_g 由 FSR 反演得到**（E-SOI-NG-220 / E-SIN-NG-1200）：强于纯仿真（FSR 是直接测量量），但**弱于 n_g 直接测量**（如 E-SIN-NG-300 的 OFDR 群延迟法）；`method` 字段逐条标注反演路径。
3. **Y-branch 模型粗糙度如实暴露**：默认唯象系数 c1=0.004 dB/deg² 给 0.4 dB vs 实测 0.28 dB，**rel≈43%**。**不做拟合回算**（调 c1 让该点通过 = 用被验证量标定验证量，循环自证，见 E6 教训），改为**防回归护栏**（≤50%）并在检查名中标注「未标定，待真实 PDK 工艺标定」。
4. **E1 升 A 级 ≠ 判决路径变真**：E1 的 candidate **仍是占位自证桩**；且标量 FDFD 对高对比度 SOI 差约 10%，即便接入也必 FAIL，需待 **R16**（亚网格 ε 平均）。golden 可溯源只是必要不充分条件。

---

## v0.9.9（2026-09-01 · 判决路径独立性整改 · D-64）

**🔴 审计发现：实证锚判决路径为空（7 道全是假绿）。** v0.9.8 把「golden 必须真实可溯源」这条做到了，但漏了另一半——**candidate（候选求解器）也必须独立求解**。`verification_adapters.py` 的 `_harness_reference_candidate` 直接 `return oracle_value`，实测 E1-E7 七道 `|candidate − golden| ≡ 0.0000`：

```
ID   metric              golden   candidate  |diff|
E1   n_eff                 2.63       2.63   0.0000   ← 自证
E2   n_g                  1.892     1.9587   0.0667   ← 整改后独立求解 ✅
E3   FSR_nm               10.44      10.44   0.0000   ← 自证
E4   insertion_loss_dB     0.18       0.18   0.0000   ← 自证
E5   excess_loss_dB        0.05       0.05   0.0000   ← 自证
E6   propagation_loss_dBcm 0.087     0.087   0.0000   ← 自证
E7   crosstalk_dB         -41.0      -41.0   0.0000   ← 自证
```

这也解释了为什么 v0.9.8 把 E3 golden 从 9.15 改成 10.44 后 smoke 仍全绿——改的是 golden，而 candidate 恒等于 golden。项目内部其实**知情**（`benchmarks.py` 有 9 处 note 写「harness 默认 ReferenceCandidate 自洽 PASS」），属已知占位设计；我的疏失是 v0.9.8 改 E1/E2 note 时把这句标注弄丢了。本轮补回并**强化为三处明示**：note / 报告 `candidate_desc` / CI smoke 断言。

**整改（按杜先生拍板「先打通 E2 样板再复制」）：E2 单题做完整闭环。**

- **几何对齐**：E2 原 500nm 宽波导与任何公开实测器件都对不上，改为 **1000×300 nm**（对齐 Munoz 300nm Si₃N₄ 平台实测器件）。
- **golden 换 A 级实测**：新增语料 `E-SIN-NG-300`，**n_g = 1.892**（TE），来源 `https://www.mdpi.com/1424-8220/17/9/2088`（P. Munoz et al., *Sensors* 17, 2088, 2017）——OFDR 环形谐振腔群延迟实测（1514–1594 nm 线性拟合）+ MZI 传输谱交叉验证 1.90–1.92，TM=1.717。数值与 URL 均经 WebFetch 逐字核实，未推断 DOI。
- **新增独立求解器** `_fdfd_ng_candidate`（`verification_adapters.py`）：标量亥姆霍兹 FDFD 本征模算 n_eff(λ)，**固定网格**中心差分得 n_g = n_eff − λ·dn_eff/dλ。结果 **1.959 vs 实测 1.892，|diff|=0.067（3.5%）≤ tol 0.10** —— **LDA 首道「实测 ↔ 独立求解」真交叉验证**。
- **E1 保留 B 级并如实标注**（杜先生拍板）：标量 FDFD 对高对比度 SOI（3.48/1.44）**不达标**——算 3.71~3.78 vs 参考 4.19，差约 10%，且 n_eff 网格未收敛（f=24→48：2.585→2.542）。note 写明需**全矢量模式求解器**方可升 A 级。

**同批量化的求解器能力边界（真实数值实验，非推测）**

| 波导 | 对比度 | FDFD 算 n_g | 实测/参考 | 偏差 | 结论 |
|---|---|---|---|---|---|
| SiN 1000×300nm | 2.0/1.44（低） | 1.950 | 1.892（实测 TE） | 3.1% | ✅ 可用 |
| SOI 500×220nm | 3.48/1.44（高） | 3.71–3.78 | ~4.19（参考） | ~10% | ❌ 需全矢量 |

补 Sellmeier 材料色散（Lipson Si₃N₄ / Tan SiO₂）后 SiN 反而更远（1.950→1.990）→ 误差主因是**标量近似不辨 TE/TM**（实测 TE 1.892 / TM 1.717，标量解偏高），不是色散缺失。

**实验铁律（本轮踩坑）**：求数值导数时**网格 dl 必须由中心波长固定**。初版把 `dl = λ/f` 写在 `neff(λ)` 内部，网格随扫描波长变化 → 差分测到的是网格伪变化而非物理色散，n_g 乱跳 5.93 / 1.85 / 1.61。提到外层由中心波长定 dl 后：f=24→48 仅差 0.008、δ=20/10nm 完全一致。

**CI 加固（宁可红不可假绿）**：`run_empirical_anchor_smoke` 新增 2 条 D-64 断言（23→25）——①E2 candidate 必须**非** golden 自证且落在容差内；②其余 6 道**必须**仍是自证桩（一旦有人偷偷接了求解器而断言没改，会立刻变红，防止再次失真）。`run_empirical_d62_report` 同步 A 级 5 道→6 道（第三次同类「断言写死过期」教训）。

**底数变化**：语料 29→**30 条**，A 级 24→**25（83.3%，达标线 80%）**，**可溯源实证锚题 5/7 → 6/7**；CI core 维持 **83 条**（仅加断言，未新增 smoke 文件）。

### D-65（同批实测发现）：FDFD 候选的网格收敛缺口 —— E2 只判「量级一致」

打通 E2 后做稳健性检查，发现这个 PASS **不能按字面读**：同一器件**只改计算窗口**，n_g 就在 1.878~1.962 间散射。

```
SiN 1000×300（E2 器件）        SOI 500×220        SiN 800×800（对照）
clad  n_eff    n_g             n_eff    n_g       n_eff    n_g
1.5   1.5637   1.8777          2.5384   3.7924    1.7642   2.0829
2.0   1.5699   1.8818          2.7385   3.8192    1.7884   2.0843
2.5   1.6197   1.9621          2.7843   3.8000    1.7884   2.0843
3.0   1.6129   1.9587          2.5852   3.7761    1.7642   2.0829
4.0   1.5699   1.8817          2.7385   3.8192    1.7884   2.0843
散射  ±0.028   ±0.042          ±0.123   ±0.022    ±0.012   ±0.0008
```

**根因=网格过粗，不是 σ 也不是物理**：0.3µm 芯厚在 dl=λ/24=64.6nm 下只有约 **4.6 格**，阶梯边界随窗口尺寸改变对齐位置 → 离散化误差跳变。对照组（厚 SiN 800×800，约 12 格分辨）**完全收敛**，n_g 散射仅 0.0015 —— 反证了「是分辨率问题，不是求解器逻辑问题」。

排查过程两次推翻自己的假设，如实记录：
- ❌ 假设一「σ 硬编码 2.3 导致取错模态」：`oracle_mode.py` 的 shift-invert 目标确实被写死为 n=2.3（与其上方注释「σ 由 EIM 估计给出」不符，且对低对比度 SiN 而言 σ 落在整个导模谱**之外**）。修成按 EIM 估计取值后——**结果逐位不变**（实测 4 个构型全部相同），σ 不是主因。该 latent bug 仍修（代码与注释对齐、消除低对比度结构隐患），但不宣称它解决了问题。
- ❌ 假设二「矢量 FDTD 能闭合标量近似的缺口」：仓库已有真 3D 全 Yee 矢量本征模求解器（`lda_solver/fdtd3d_waveguide_vec.py`，此前只与标量 ORACLE 自校、**从未对实测验证过**）。实测：单次 **305 秒**（太慢），且 n_eff(λ) **非单调**（1.53→1.5566、1.55→1.6298、1.57→1.3684），相位法精度不足 → n_g 得 8.76（荒谬值）。**矢量 FDTD 当前不可用于 n_g 判定**。

**处置（宁可难看，不可假绿）**：
- E2 的 note 改为如实写法——「当前只能判定**量级一致 + 判决路径真实**，不能宣称**精度验证**；0.10 容差中约 ±0.08 是数值不确定度而非物理裕度」。
- 新增 **D-65 窗口鲁棒性断言**（smoke 25→27）：5 个计算窗口的 n_g **全部**必须落在容差内（实测最大 |diff|=0.0701 < 0.10）——证明 PASS 不是挑了个好窗口凑出来的；同时对散射设上界 0.12 护栏，防网格实现退化。
- 登记 **R16**（FDFD 网格收敛缺口），根治方向=**亚网格 ε 平均**（sub-cell averaging）+ 更细网格。

### 对外验货面同步整改（把 D-64 的诚实披露延伸到报告与 API）

- **`run_harness.py` 报告**：此前默认走 `ReferenceCandidate`（候选≡黄金），报告顶部赫然写着「## 汇总：48/48 通过」却只有一行 `candidate：ReferenceCandidate` 说明——外部读者极易误读为「48 项已验证」。现加醒目警告段 + 汇总行改「48/48 通过（自证闭环，**非验证结论**）」，JSON 增 `summary.self_consistent=true / summary.verified=0` 供机器判定。
- **CI 断言防丢失**（v0.8.55 教训：改了东西没同步 smoke，主干红而宣称全绿）：`run_harness.py` 末尾新增断言——自证模式下报告必须含警告文本、JSON `verified` 必须为 0；独立候选（`--perturb`）模式下 `self_consistent` 必须为 False。警告一旦被弄丢，CI 立刻红。
- **`/api/verify`**（WebUI）：`meta` 增 `self_consistent` 字段，自证时附 `warning` 说明。
- **`/api/verification_ledger`**（无鉴权对外验货端点）：①`ci_core` 由写死 82 改为动态读 `CORE_SMOKES` 长度（此前实际已 83，对外端点与 README 账本不一致，同一类漂移第二次）②新增 `judgment_paths` 字段，明示「7 道实证锚中仅 E2 有独立候选、其余 6 道为占位自证」及「harness CLI 默认模式为自证闭环」③`open_gaps` 登记 **R15**（判决路径独立性缺口）与 **R16**（FDFD 网格收敛缺口）。

## v0.9.8（2026-09-01 · 实证锚来源边界与溯源审计 · D-63）

确立**实证语料来源边界**：仅限 ①公开论文 ②公开 datasheet ③公开测量数据集，且**必须可公开溯源**。新增 `lda_harness/provenance.py` 做**机器可判**的三级分级——A 级（citation 含 DOI / arXiv / 公开 URL 定位符，第三方可独立复验，可作 golden 进判决）、B 级（仅有描述性来源无定位符，**禁止作 golden**）、X 级（无来源，拒收）；内网/私有地址段 URL 不算公开。门禁落三处：新语料准入（`submit_measurement` 非 A 级一律 rejected）、golden 取值（`EmpiricalAnchor.resolve` 默认 `require_traceable=True`）、判决路径（`harness.py` / `verification_adapters.py` 按锚题类型传参，A 级强制溯源、B 级显式放行但标注且不计入可溯源计数）。新增独立审计器 `run_provenance_audit.py`（已入 CORE_SMOKES，82→83）。

审计结果：语料 23→**29 条**，A 级 18→**24 条（82.8%）**；补 6 条 A 级真实实测语料（Sridaran & Bhave, Opt. Express 18(4) 3850–3857 (2010)，URL 定位符）：FSR 10.44/11.15 nm、cut-back 损耗 3.88/5.06 dB/cm、Q 46,500/148,000。

**审计暴露两个重大问题并整改**：①E3 原 golden 9.15 nm 实为解析式 λ²/(n_g·2πR) 闭式反算（且 n_g=4.18 源自 2D FDTD 仿真），属「定律/仿真冒充实测」——已换成**实测 10.44 nm**，并形成实测↔解析交叉验证（10.44 vs 10.464，差 0.024 nm）；②n_eff 在工程上是导出量（多为仿真或反演，少有直接测量），E1/E2 缺公开可溯源实测源，已改标 `empirical_unverified`（B 级，仍走死标量判决但不计入可溯源计数），建议后续改为可实测的群折射率 n_g 锚。**可溯源实证锚题：5/7**。详见 `docs/lda_empirical_source_boundary_2026-09-01.md`。

### 发版回归（core 83 条）抓出并根治的三类连带问题

- **① 门禁漏改（第三次同类教训）**：`resolve_specs()` 两处把 B 级锚题的 spec `anchor` 硬写回 `"empirical"`，使 `run()` 中 `require_traceable=(anchor=="empirical")` 恒为真 → E1/E2 golden 被判 None → verify_design 掉到 46/48（mcp、l1_agent 两条 smoke 红）。**根因在赋值点而非比较点**——此前只 grep 了 `== "empirical"`（比较），漏了 `"anchor": "empirical"`（赋值）。已改为透传 `anchor` 原值，两条 smoke 回到 48/48。
- **② 展示路径未适配 None**：`benchmark_report.run_crosscheck` 对 B 级语料仍走默认强制溯源 → `val=None` → `mval - None` TypeError（crosscheck 报告、飞轮 smoke 红）。已改为覆盖率展示显式 `require_traceable=False` 取值并标 `traceable` 字段（该报告是展示不是判决）；同时**修掉一句失真宣称**：`honest_note` 原写「9 条全部 DOI 可溯源」与事实不符，改为按 `provenance.audit_items` **实时统计** A 级条数，杜绝写死。
- **③ 冒烟脚本自带语料被新门禁挡下**（同类第二次）：`run_tapeout_smoke` 的 citation 无定位符被拒、`run_d06_smoke` 断言 `src=="empirical-measurement"` 与 B 级现状冲突。已分别改为「补公开 URL（SkyWater SKY130 公开 PDK）+ 追加反向断言（无定位符必须 rejected）」与「默认门禁返回 `empirical-untraceable`、显式放行返回 `empirical-B-untraceable`」——把新门禁本身也钉进 smoke。
- **额外根治：CI 回归 SKIP 判定过宽（假绿温床）**。旧规则「输出含『未安装』等字样即记 SKIP」，会把真失败误记 SKIP——本次 3 条（d06 / cli / ci_industrial）均为用例失败被洗白，其中 cli 仅因某条 PASS 行里提到「gdsfactory 未安装」就被记 SKIP。已收紧为两级：①行首 `[SKIP]`/`SKIPPED` 显式标记 → 无条件 SKIP；②环境缺失短语 → **仅当输出中无 Traceback / AssertionError / FAIL 行**时才记 SKIP，否则一律 FAIL。宁可红，不可假绿（对齐 v0.8.55「宣称全绿必须有实跑证据」教训，且实证锚 smoke 已覆盖 5 类判定用例）。

## v0.9.7（2026-09-01 · 生产安全加固 · POST 重计算端点登录闸门）

复盘：在 v0.9.6 四重并发护栏（每端点锁+全局上限+缓存+入参上限）基础上，于 `_heavy_guard` 统一入口追加**登录闸门**——把「无鉴权重计算」敞口从「被并发数封顶」升级为「须登录才能触发」。验证优先 `store.user_by_token(token)`（store 会话态），回退 `_check_admin(headers)`（管理员 / 外部 ORACLE 验货用 Bearer）；未登录直接 401 且不占缓存/并发资源。GET 验货端点（cpo_array / verification_ledger）仍无鉴权，维持「可被外部验货」战略可达性。影响面排查：现有 CI smoke（`run_adjoint_design_smoke` 等）直接 import 库函数不走 WebUI HTTP、无 `run_*smoke` 经 HTTP POST 调这些端点、`run_api_v1_smoke` 走独立 `/api/v1/*`，故加闸门不会让 CI 失同步（规避 v0.8.55 教训）；前端 insights.html 仅拉 GET 不受影响。

## v0.9.6（2026-09-01 · 生产安全加固 · POST 重计算端点统一并发护栏）

复盘：经排查，WebUI 的仿真/设计类 POST 端点（`/api/ring_fdtd`、`/api/sparams`、`/api/sparams_3d`、`/api/gc_sparams`、`/api/adjoint_design`、`/api/quantum_design`、`/api/wdm_design`、`/api/pdk_design`、`/api/pdk_compare` 等 50 个 `run_*` 端点）**同样无鉴权、直接触发重计算**，与之前打爆服务器的 GET 端点同源——且 `app.py` 的 `_dispatch` 无统一鉴权闸门。纯「按端点逐个锁」只能锁单端点，攻击者同时打 50 个端点仍可达 50 路并行 → 同样打爆。本次采用「每端点锁（公平）+ 全局并发上限（总资源封顶）」双锁设计：

- **① 每端点独立串行锁**：每端点任意时刻至多一个重计算在跑，并发 429「重计算忙，请 1-2 秒后重试」，避免跨端点队头阻塞。
- **② 全局并发上限**：`threading.Semaphore(min(cpu_count, 4))`，总重计算并发封顶，彻底封死「同时打所有端点」的总并发敞口（纯按端点锁做不到）。
- **③ 参数哈希缓存**：TTL 120s、限容 32 条，重复相同请求秒回，防内存膨胀。
- **④ 入参体积硬上限**：单请求体 256KB，超则 413，防超大 payload OOM。

护栏经 `_dispatch` 在 POST 精确路由层接入，仅对 `HEAVY_POST_PATHS`（50 个重计算端点）生效；鉴权/商店/生态/opinion/verify 等轻端点与有副作用端点不进护栏，行为不变。本次**未加登录鉴权**（用户决策：先只做并发护栏，鉴权作独立议题）。

验证（本地冒烟）：50 端点入表、轻端点不入表；单次 200；同参缓存命中秒回；并发 6 路同端点 `max_overlap=1`（每端点锁完全串行化，无并行堆叠）。`py_compile` 两文件通过。

## v0.9.5（2026-08-31 · 生产安全加固 · 验货端点并发护栏补全）

复盘：`GET /api/benchmark_crosscheck` 是 v0.9.3 同期存在的无鉴权公开 GET 端点，默认实跑 `run_crosscheck(quick=True)`（本地实测 9.2s），同样运行在 `ThreadingHTTPServer`（每请求一线程）下、与 `cpo_array` 同类——一旦被并发请求打中会把生产服务器并行打爆。本次补齐同款三护栏：全局串行锁（任意时刻至多一个 crosscheck 在跑，并发 429）+ 结果缓存（TTL 120s，重复 curl 秒回）。至此所有「公开 GET + 默认实跑重计算」端点（cpo_array、benchmark_crosscheck）均带护栏；verification_ledger / scale_demo / capability_demos(默认) / status / health 等均为轻量只读或需显式 `?run=1`，不在敞口之列。

## v0.9.4（2026-08-31 · 生产安全加固 · CPO 验货端点并发护栏）

复盘：v0.9.2 部署的 `GET /api/cpo_array`（无鉴权、默认实跑十万级器件，build+DRC+LVS ~数秒~数十秒）运行在 `ThreadingHTTPServer`（每请求一线程）下，一旦被并发请求（外部扫描 / 监控轮询 / 反复自测）打中，多个重计算会并行吃满 CPU/内存，存在把生产服务器打爆的风险。本次加固：

- **① 输入硬上限**：`oe<=48, ch<=96, lane<=16`，超出即 400，防止单请求 scale 到 OOM。
- **② 全局串行锁**：任意时刻至多一个重计算在跑（`threading.Lock` + 1s 超时），其余并发请求 429「重计算忙，请 1-2 秒后重试」，杜绝并行堆叠。
- **③ 默认配置结果缓存**：TTL 120s，重复 curl 同配置秒回，不再重算。

验证（本地）：默认 100,096 器件 ACCEPT（4.19s）· 二次命中缓存 0.000s · 超限 400 · 冷缓存并发 3 线程 → 1 个 3.99s 实算 200、其余 2 个 1.05s 内 429（锁串行，无并行堆叠）。

## v0.9.3（2026-08-31 · 验证可信度外部验货 · 全量验证账本端点）

战略审计 #1 缺口「可被外部验货的验证可信度」从单点（CPO 规模死锚）扩展到整引擎：

- **新增 `GET /api/verification_ledger`（无鉴权、可 curl 验货）**：暴露全部已注册验证资产的**分类与计数**——`physical-law` 确定性物理定律锚（B1–B28 / S1–S13，38 道，任何人都可独立复算）+ `oracle-or-design-anchor` ORACLE 依赖锚（B5/B6/B7，3 道，meep/tidy3d 缺失时回退 numpy 离线近似或设计守则下限）+ `empirical` 实证大数据锚（E1–E7，7 道，真实器件实测语料）；合计 **48 题**；旁挂 `CI core 82 条` 与 `CPO 规模死锚`（默认 100,096 / 规模 250,240 ACCEPT）。
- **诚实分类（verified_by）**：明确标注每类事实来源与开放缺口——R2 外部 ORACLE 默认不通（物理定律锚无法现场交叉验证）、R3 实证锚仅 7 条种子语料、R4 B5/B6/B7 为 ORACLE 依赖（根因=R2）。LLM 不进判决路径，PASS/FAIL 一律由死标量比对。
- 端点纯内省、无重计算，纳入 WebUI 路由层冒烟（GET_ROUTES 静态校验）。

## v0.9.2（2026-08-31 · 阶段2 · CPO 共封装光引擎阵列：十万级真实器件样例）

把 v0.8.45（LVS 短路检测 O(n²) 治理）与 v0.8.46（GDS 导出 O(n²) 治理）打通的十万器件级全链能力，落到**真实器件样例**上——不再是「N 个 Waveguide 串成一条链」，而是层次化的**共封装光学（CPO）光子引擎阵列**。

- **新增 `lda/lda_harness/cpo_array.py`**：CPO 阵列生成器，层次为
  阵列（n_oe 光引擎）→ 光引擎（n_ch 波长通道）→ 通道（n_lane 条波长 lane）。
  - 器件构成真实：微环调制器 MRM（`RingAddDrop`）/ WDM add-drop 解复用环 /
    功率监测·波长锁定抽头（`RingResonator`）/ 光栅耦合器（`GratingCoupler`）
    / 互连波导段（`Waveguide`）——每通道 92 器件 = Tx 链 58 + Rx 链 34。
  - **参数由物理反解，非拟合常数**：微环半径 `R = m·λ/(2π·n_eff)`
    （m=91 **整数**谐振级数、n_eff=2.45 → 7.530–7.713 µm，LAN-WDM 8 波）；
    光栅周期 `Λ = λ_c/(n_eff,gr − sin θ) = 0.612 µm`（θ=15°，齿宽 0.367 /
    齿隙 0.245 µm 同时满足 DRC 线宽与间距双约束）。
  - **几何策略：端口线对齐 + 零跳线**——放置按「入端口（链首用出端口）」
    做 y 补偿，使同行全部连接端口落在同一条水平线上；pitch_x 取
    `max(2·max_hw + margin, max(out_dx) − min(in_dx) + 6)` 保证连线不回折；
    通道宽度整除行宽使通道不跨行。于是全部布线为同层 M1 水平段，
    **同层短路数 = 0 由几何保证，而非靠 LVS 兜底**。
- **新增 `lda/run_cpo_array_demo.py`**：全链闭环演示（构建→放置→布线→
  GDS→DRC→LVS→正/反例→报告）。默认配置 32 引擎 × 34 通道 × 8 波长实测：
  - **100,096 器件 / 2,176 条独立光路 / 97,920 布线网 + 4,352 外部 IO**
  - DRC **100,096/100,096** 全过
  - LVS **ACCEPT**（0 违规 · 97,920/97,920 网表全匹配）
  - 反例（注入断路）→ **REJECT**（证明判决非「永远 ACCEPT」）
  - GDS **38.98 MB / 359,040 元素**（4.02s，round-trip 可解析）
  - 芯片 **13.14 × 7.89 mm = 103.67 mm²**（≈1.04 cm²，真实 CPO 中介层量级）
  - 全链 **8.34s**
- **新增 `lda/run_cpo_array_smoke.py`**：21 条断言入 CI core（**80→81**），
  含层次推导死标量、端口线对齐零回折、**独立重算** R = m·λ/(2π·n_eff) 逐项
  比对、光栅布拉格条件、DRC/LVS 正反例、GDS round-trip、十万配置推导、
  配置护栏（ch_per_row 不整除则拒绝）、源码零 LLM 红线。
- **诚实边界（不可省略）**：仅建模**无源光子层**，有源器件（激光器/探测器/
  驱动 IC/TIA）按黑箱处理（负面清单）；工艺为公开文献近似非真实 foundry
  PDK；本样例只做**版图闭环**，未做光学仿真验证（插损/串扰/FSR 属另一条
  链路）；未流片、无实测回流。

## v0.8.56（2026-08-29 · 创新超市商业闭环：会员 + 统一订单 + 自动交付）
- **商业闭环核心**：新增 `lda/lda_webui/store.py`（零依赖，数据落盘 `dist/store.json` gitignored）——会员注册/登录（PBKDF2 + 会话令牌）、统一订单状态机（created→paid_unverified→approved→rejected）、微信个人收款（收款码+凭证）、管理员「确认收款并自动发货」（复用 `ship_package` 生成一次性兑换码）。
- **双通道**：个人用户（微信个人收款凭证）+ 企业客户（对公转账）共用同一套订单流；下单自动带单价（¥1999 默认，可按货架覆盖）。
- **路由接入**：`lda/lda_webui/app.py` 新增 `/api/store/*`（register/login/me/order/orders/mine/config）与 `/api/admin/*`（orders/config/order/<id>/approve|reject）；新增 `_bearer()` 统一去 Bearer 前缀；管理员鉴权统一认可 `LDA_ADMIN_TOKEN` 环境变量（修复 list_orders 仅认 store 用户、下载路由 `parts[4]/count==5` 解析错位两处 bug）。
- **前端**：`lda/lda_webui/static/store.html`（会员登录/注册、货架下单、上传支付凭证、自助下载）、`admin.html`（订单审核、一键发货、微信收款码配置）；静态白名单放行进 `store.html`。
- 端到端验证通过：注册→下单→凭证→管理员审批（自动生成兑换码）→会员自助下载 zip；个人/企业两通道均跑通。
- **Track 0 计费身份中枢**：注册新增三档身份（standard 标准个人 / academic 学术个人 / institution 机构席位，机构必填单位名称）；`tier_discount` 折扣引擎（1.0 / 0.6 / 0.85，管理员可经 `config.tiers` 覆盖）；`price_of(shelf_id, user_type)` 按身份计价；订单记录 `tier` 字段；`/api/shelf` 按登录身份返回 `price_cny/base_price/price_tier`；前端注册弹窗三身份选择 + 货架实付价 + 下单金额 + 会员中心/导航身份徽标；老账号无 user_type 字段安全回退 standard。生产 e2e 16/16 通过（三身份价格 1999 / 1199.4 / 1699.15 联动验证）。

## v0.8.55（2026-08-29 · 管理后台上线打通商务闭环 + 生产部署真实账户）
- **管理后台**：新增 `lda/lda_webui/static/admin.html`——令牌登录（localStorage）、待处理申请列表（公司/联系人/电话/邮箱/货架/备注/时间）、一键审批并生成一次性兑换码、兑换码复制 + 下载链接；静态页白名单放行进 `admin.html`。
- **文案修正**：`/api/purchase/request` 响应去掉"邮件发送兑换码"空头承诺，改为"到账后管理员生成兑换码、凭码下载"准确表述（手动发码阶段）。
- **生产部署**：`115.191.20.92` 部署真实对公收款账户（上海农商银行陈行支行 32434508010036375）+ 联系人（杜先生 13636690529/13311602075、范女士 13901700712）+ 联系电话；管理员弱令牌通过 `LDA_ADMIN_TOKEN` 环境变量替换为强令牌加固。
- 货架/开放数维持 58/50；量子 8 维持咨询制；CI core 维持 69 条。

## v0.8.54（2026-08-29 · 对公收款程序适配：创新超市接对公购买申请闭环）
- **对公收款适配**：营业执照确认上海杜特企业管理咨询有限公司为有限责任公司（自然人投资或控股），B2B 设计包交付采用直接对公转账 + 兑换码交付。
- **前端**：`lda/lda_webui/static/insights.html` 增加顶部「对公收款说明」弹窗、货架卡片「对公购买」按钮；弹窗收集公司/联系人/电话/邮箱/付款备注。
- **后端**：`lda/lda_webui/app.py` 新增 `POST /api/purchase/request`、`GET /api/admin/purchase_requests`、`POST /api/admin/purchase/{id}/approve`；申请持久化到 `dist/purchase_requests.json`（gitignored）；审批通过调用 `ship_package.mint_license` 生成绑定货架的兑换码。
- **管理**：管理员端点通过 `Authorization: Bearer <LDA_ADMIN_TOKEN>` 鉴权，默认令牌为弱默认值并提示通过环境变量 `LDA_ADMIN_TOKEN` 替换。

## v0.8.53（2026-08-29 · 持续扩货架：新增 5 光子缺口品类开放下载、货架 53→58）
- 货架 53→58：新增 5 个真实 2026 市场缺口光子品类（信号源可溯源、composition⊆GP-*、非出口管制、honest_tier=前瞻预研）：
  - `IM-AWG-DEMUX`（阵列波导光栅解复用器 AWG DeMUX；AWG MUX/DeMUX $735M(2025)→$1.375B(2031) CAGR 8.14%、Arrayed Waveguide Market $320-570M(2026) CAGR 6.5-11.7%、AI 数据中心 DWDM/CPO 推升）
  - `IM-ONCHIP-SPECTROMETER`（片上微型光谱仪；Chip-scale Spectrometer $2.44B(2025)→$8.7B(2033) CAGR 17.2%、Miniature Spectrometer IC $1.36B(2025)→$3.99B(2034) CAGR 12.7%）
  - `IM-MDM-MUX`（模分复用器 MDM；MDM Equipment $1.42B(2024)→$4.16B(2033) CAGR 12.6%、Few-Mode Fibers $10.74B(2025) CAGR 6.86%、突破单模 Shannon 极限）
  - `IM-OPTCOMB`（芯片级光频梳 Microcomb；全球光频梳 $1.87B(2026) 年增 31.7%、Intel $58M(2025)→$108M(2034) CAGR 7.4%、芯片级微梳 CAGR 47.8%）
  - `IM-POL-ROTATOR`（片上偏振旋转器；光偏振控制器 $4.72B(2026) 增 12.9%、Polarization Rotator CAGR 10.3%(2026-2033)、集成波导型增速 28%）
- 开放下载白名单 `OPEN_SHELVES` 45→50（前述 5 个光子缺口品类全量放开；工厂产能已具备，任意已知货架可现场生成设计就绪包）。
- 量子 8 个维持「咨询制」，不进自动下载白名单（出口管制合规红线）。
- `docs/store_launch/04_market_analysis.md` 新增趋势段：AWG 解复用（DWDM/CPO $1.375B 2031）、片上光谱仪（Chip-scale $8.7B 2033）、模分复用（MDM $4.16B 2033）、芯片级光频梳（微梳 CAGR 47.8%）、偏振旋转器（集成波导型增速 28%）；光子细分表格扩容，开放策略 45→50 货架。
- 沿用 `OPEN_SHELVES ⊆ DEFAULT_SHELF` 回归护栏；重新生成 `innovation_market.json`（58 货架）；货架 smoke **58/58 ALL PASS**；`run_count_consistency_smoke` **11/11 OK**（CI core 维持 69 条）。

## v0.8.52（2026-08-28 · 持续扩货架：新增 5 光子缺口品类开放下载、货架 48→53）
- 货架 48→53：新增 5 个真实 2026 市场缺口光子品类（信号源可溯源、composition⊆GP-*、非出口管制、honest_tier=前瞻预研）：
  - `IM-MRR-FILTER`（微环谐振滤波器/可重构光滤波 add-drop；Silicon Microring Resonators $450M→$1.66B CAGR 20.5%、Microring Filter Array $41.58M→$245M CAGR 27.8%、add-drop 占 55.5%）
  - `IM-SPLITTER-TREE`（1×N 功分树/PLC 功分网络；PLC Splitter $2.8B→$5.6B CAGR 8.1%、1×N 占 62.4%、FTTR/XGS-PON 推升 1×32+）
  - `IM-TRUE-TIME-DELAY`（微波光子真延时 TTD 波束成形；Phased Array Antenna $3.90B→$8.38B CAGR 10.04%、相控阵系统 $18.7B→$38.5B CAGR 12.8%、MWP 真延时用于相控阵雷达）
  - `IM-GAS-SENSE`（波导气体/吸收光谱传感 SiN 宽波段；SiN PIC $320M→$1113.58M CAGR 19.5%、VOC 中红外检测灵敏度较 Si 提升 5×）
