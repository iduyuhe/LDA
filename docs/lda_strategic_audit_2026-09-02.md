# LDA 战略审计 · v0.9.13 基线（2026-09-02）

> 审计对象：LDA 开源 Agent 原生芯片设计软件（`D:\agent_LDA`，commit `2dda10c`，v0.9.13）
> 上一轮基线：`docs/lda_strategic_audit_and_upgrade_plan_2026-08-30.md`（v0.9.1 · HEAD `61ef225`）
> 审计方法：**所有状态必须来自代码实测（grep 行号 / 实跑输出），不采信文档声明**
> 执行：战略对齐 → 功能对齐 → 性能对齐 → 下一步研发规划

---

## 零、执行概要（结论先行）

| 系统 | 上轮评分（08-30） | **本轮评分（09-02）** | 变化 | 一句话 |
|---|---|---|---|---|
| **核心系统** | 3.7 / 5 | **3.3 / 5** | 🔻 −0.4 | 资产更厚了，但**验证可信度被量化后暴露出实质性空洞** |
| **商业系统** | 2.7 / 5 | **2.7 / 5** | ➖ 持平 | 0 成交事实未变，无新证据可改判 |
| **生态系统** | 3.2 / 5 | **3.2 / 5** | ➖ 持平 | 社区信号 3 天零变化，纪律仍守住 |

### 🔴 本轮最高价值发现（一句话）

> **48 锚实跑 48 PASS，但其中 47 道是"自证桩"（candidate ≡ golden，|diff| ≡ 0 恒 PASS、零验证价值），唯一 1 道真独立求解（E2）已在 9-01 R16 证伪后降级为量级参考。**
> **→ 在 harness 判决路径下，LDA 当前真可证伪并进入判决的锚题 = 0 道。**

**这不是退步，是审计精度提升。** 上一轮只发现"E1-E7 七道自证桩"（D-63），本轮用实跑（而非文本推断）把口径测到底：**自证桩是 47/48，不是 7/48**。系统本身没变差，是我们第一次把它量准了。

### 三大战略判断（本轮刷新）

| # | 判断 | 上轮 | 本轮证据 |
|---|---|---|---|
| **一** | 技术侧主矛盾：**"看起来很强" ≠ "被验证为强"** | 已提出（"能力有无→验证可信度"） | **量化坐实**：harness 48 锚可证伪率 0/48；device_library 5 设备 live 模式本机**仅 1 道能跑**（RingResonator），DC/YB 需 torch CUDA、WG/Bragg 为 heavy 跳过 |
| **二** | 商业侧：0 成交，无新证据可改判 | 已确立 | 生产 `/api/health` = v0.9.13 在线、货架 58；**真实订单仍为 0**（上次取证 08-30，本轮未重复取，数据未变） |
| **三** | 生态侧：信号静止但纪律完整 | 已确立 | GitHub 实测（09-02）：Stars **1** / Forks **1** / Subscribers **0** / issues_open 3 / prs_open 1 —— **与 08-30 逐项相同，3 天零变化** |

### 一句话战略建议（本轮）

> **停止"加锚"，开始"证锚"。下一阶段唯一技术主线 = 把自证桩转成真交叉验证；唯一商业主线 = 取证（为什么零成交）。**

---

## 一、战略对齐矩阵（战略目标 → 代码实测证据 → 状态）

| 战略目标 | 已落地能力（代码证据） | 上轮状态 | **本轮状态** |
|---|---|---|---|
| **① 非 AI ground 双支柱** | 物理定律锚 B28 + 实证语料 **30 条 A 级 100%**（`run_provenance_audit.py` 实跑 PASS） | 🟡 部分 | 🟡 **语料侧已达标（A 级 100%），判决侧未达标（见 ①-a）** |
| ①-a 实证语料可溯源 | `run_provenance_audit.py` 实跑：**总计 30 条 / A 级 30 / B 级 0 / X 级 0；可溯源锚题 7/7；PASS** | 🟠 B 级 5 条 | 🟢 **B 级已清零（上轮 5 条 B 级全部补成 A 级）** |
| ①-b 锚题真独立求解 | `verification_adapters.py:141-149` `_harness_reference_candidate` **return oracle_value**；实跑 **47/48 走此路径** | 🔴 7 道自证 | 🔴 **47/48 自证桩（恶化于认知，非恶化于代码）** |
| **② 双引擎（光子+量子）对等** | 量子 9 个 smoke 已在 `CORE_SMOKES`（实取 `len(CORE_SMOKES)=84`，其中量子 9 项） | 🟢 已关闭 | 🟢 **维持（R1 仍关闭）** |
| **③ 主权依赖干净** | `oracle_field.py:6-11` GPL 隔离架构；Meep 仅 subprocess 外部 ORACLE | 🟢 | 🟢 **维持** |
| **④ 商务闭环四要素** | `store.py:517-536` amount_cny / pay_method；`ship_package.py` 兑换码 | 🟢 闭环建成 | 🟢 维持（但 R11/R12/R14 未解） |
| **⑤ 货架冻结转深度（D3）** | `OPEN_SHELVES=50 / DEFAULT_SHELF=58`；生产 `/api/shelf` count=58 | 🟢 已冻结 | 🟢 维持 |
| **⑥ C 期三信号锁死** | 外部 ORACLE 未跑通 / PDK 外联 0 / 原策未遇瓶颈 | 🟢 纪律守住 | 🟢 **维持，未触碰** |
| **⑦ 工程质量（CI 门禁）** | `CORE_SMOKES = 84`（python 实取）；磁盘 `run_*smoke*.py = 114` 个 | 🟠 80 条 | 🟡 **84 条进 core，30 个冒烟无门禁保护**（上轮 32 个） |

---

## 二、🔴 最高价值发现：验证可信度量化（实跑，非推断）

### 2.1 harness 48 锚实跑判决

```
实跑命令：python -c "build_harness_specs() → 逐题 run_verification(spec, cand_map[sid])"
specs 总数: 48    实跑耗时: 1.1s

PASS: 48 | FAIL: 0 | 异常: 0
自证桩（cand≡golden，恒PASS，零验证价值）: 47
独立求解（真可证伪）: 1  →  E2（golden=1.892）
```

| 分类 | 数量 | 判定语义 |
|---|---|---|
| 自证桩（`_harness_reference_candidate`） | **47** | |candidate − golden| ≡ 0 ⇒ **恒 PASS**。换 golden 不产生任何验证价值（D-63 已验证：E3 golden 9.15→10.44 后仍全绿） |
| 独立求解（`_fdfd_ng_candidate`，`benchmarks.py:418` 唯一一处 `"candidate": "fdfd_ng"`） | **1**（E2） | FDFD 本征模 n_eff(λ) 中心差分。**但 2026-09-01 R16 实测证伪后已降级为量级参考**：FDFD 标量求解器对高反差细波导精度不足（n_eff 偏差 0.18~0.37）+ golden 来自环器件而 FDFD 解直波导（几何不同源，n_g 系统性偏高 ~0.46） |
| **进入判决的真可证伪锚** | **0** | — |

### 2.2 device_library 5 设备 live 交叉验证实跑

`device_library.py` 中 5 个设备**全部**带 `verify_spec + candidate_fn`（真独立候选，非自证）——这是 LDA 验证可信度真正的硬核：

| 设备 | spec_id | oracle_kind | live 实跑（本机） | 阻塞原因 |
|---|---|---|---|---|
| DirectionalCoupler | DC-gap0.25 | `fdfd_supermode` | ⚪ SKIP | `requires_gpu=True` → live 候选是 **torch CUDA 3D FDTD**（`:98-99`） |
| SymmetricYBranch | YB-1x2 | `symmetry_theorem` | ⚪ SKIP | 同上（`:110-111`） |
| Waveguide | WG-Si/SiO2 紧约束 50 | `fdfd_eigen` | ⚪ SKIP | `live_weight="heavy"`（`:125`），默认跳过 |
| RingResonator | RING-fsr | `physical_law` | ✅ **PASS** | 解析 FSR ↔ 洛伦兹梳谱峰提取（无需 GPU，light） |
| BraggMirror | BRAGG-band | `tmm_analytic` | ⚪ SKIP | `live_weight="heavy"`（`:209`） |

**实跑输出**：`PASS: 1 / 3（可跑项）`，`skipped: ['Waveguide', 'BraggMirror']`。

> **结论：默认环境（无 GPU）下，device_library 能现场演示的真交叉验证 = 1 道（RingResonator）。**

### 2.3 全口径"可证伪验证资产"总账

| 验证资产 | 声称数量 | **真可证伪** | **默认环境可现场演示** | 性质 |
|---|---|---|---|---|
| harness 48 锚 | 48 | **0** | 0 | 47 自证桩 + 1 已降级 |
| device_library live 交叉验证 | 5 | **5**（设计上） | **1**（Ring） | 独立候选 vs 物理定律/解析 ORACLE |
| 双算法互证（B28 Vπ / S13 良率） | 2 | 2（弱） | **2** ✅ | **同一物理模型的两种算法互证**，非"独立求解器 vs 外部真值" |
| 实证语料 A 级 30 条 / 7 锚题 | 30 | 30（作为真值） | 30 ✅ | **真值是外部的，但 candidate 自证 → 未形成对照** |
| 整芯片对标 GC-* | 29 | 29（引擎 vs 规格） | 29 ✅ | 设计闭环达标性，非外部 ground |

**战略读法**：LDA 最硬的资产不是"48 锚"，而是 **30 条 A 级实测语料 + 5 个 device 交叉验证设计 + 29 条 GC-\* 整芯片对标**。当前缺陷不是"没有外部真值"，而是**外部真值与候选求解器之间没有被真正接上对照**（candidate 直接抄 golden）。这是**接线段的工作，不是获取段的工作** —— 完全在 AI 自主范围内，不需要 C 期解锁。

---

## 三、功能对齐（CI 实跑证据）

| 项 | 实测结果 | 证据 |
|---|---|---|
| `CORE_SMOKES` 条数 | **84**（python 实取 `len(run_ci_regression.CORE_SMOKES)`） | 与 README 权威账本一致，计数守护全绿 |
| 全量 core 回归（v0.9.13，09-01） | **84 PASS / 0 SKIP / 0 FAIL（1377.55s，EXIT=0）** | `ci_core_run_v0913.txt` |
| 全量 core 回归（本轮复跑） | 见附录 A | `ci_core_run_audit_0902.txt` |
| 语料溯源审计 | **PASS**（30 条 / A 级 30 / B 级 0 / X 级 0；可溯源锚题 7/7） | `run_provenance_audit.py` 实跑 |
| 量子侧 CI 覆盖 | 9 个量子 smoke 在 core | `run_ci_regression.py:149-154` 等 |
| 生产在线 | `version 0.9.13 / status ok / benchmarks 48 / pdks 5 / layers_built 8` | 外网 `/api/health`（uptime 14210s） |
| 三端同步 | GitHub `last_commit_sha = 2dda10c` = 本地 HEAD | GitHub REST 实测 09-02 |

### 3.1 本轮逼出的隐藏缺陷（测试卫生）

| # | 缺陷 | 实测证据 | 严重度 |
|---|---|---|---|
| **N-1** | **B5 / B7 / B10 三道锚题无任何 `run_*` 脚本点名，CI 零覆盖** | 遍历 114 个 `run_*.py` 做 `\bBx\b` 匹配 → 仅 45/48 被提及，B5/B7/B10 完全缺失 | 🟠 中高 |
| **N-2** | **B 类 28 道无全量遍历判定脚本**（E 类有 `run_empirical_anchor_smoke.py:36` 遍历式、S 类有 `run_statistical_anchor_smoke.py` 遍历式，B 类只有零散点名） | 逐一检查 20 个含 `BENCHMARK_DEFS`/`golden_with_source` 的脚本 → 仅 2 个为遍历式且都不覆盖 B 类全量 | 🟠 中高 |
| **N-3** | **DC / YBranch 的 live 候选硬依赖 torch CUDA** | `device_library.py:98-111` `requires_gpu=True`；无 GPU 环境诚实 SKIP → 5 个 device 交叉验证只剩 1 个能演示 | 🟠 中高 |
| **N-4** | **numba 硬依赖未解**（上轮 R8 未推进） | `lda_solver/fdtd3d_numba.py`、`lda_solver/adjoint_fdtd3d.py` 模块级 import numba | 🟡 低中 |
| **N-5** | **巨型文件未根治**（上轮 R5 部分关闭） | `app.py` 3182 行 / `routes.py` 1424 行 / `lda_l2/innovation_market.py` **2652 行** / `store.py` 53KB | 🟡 低中 |
| **N-6** | **30 个冒烟脚本无门禁保护**（114 个磁盘脚本 − 84 进 core） | `len(CORE_SMOKES)=84` vs 磁盘 114 | 🟡 低中 |

> **N-1/N-2 的诚实边界**：文本匹配可能低估覆盖（脚本若通过 `_GOLDEN_DISPATCH` 遍历则不点名）。但即便如此，**"48 锚全 PASS"这句话没有对应的全量遍历判定脚本作支撑**，与 D-63 属于同一类"宣称 vs 判决路径"缺口。建议用 N-1 的修复（新增全量遍历 smoke）一次性终结争议。

---

## 四、性能对齐

| 指标 | 实测 | 判据 | 结论 |
|---|---|---|---|
| 全量 core 回归耗时 | 1377.55s（84 条，09-01） | 开发者可接受 ≤ 25min | ✅ MET |
| 48 锚全量判定耗时 | **1.1s**（实跑） | — | ✅ 极快（代价：47 道是自证桩） |
| device_library live（3 可跑项） | 0.7s | — | ✅ |
| 生产 `/api/health` | 外网 <1s | — | ✅ |
| 规模性能（历史实测） | 32k 全链 0.98s；LVS/DRC 近线性；route_batch 4 线程 2.67× | `docs/lda_scale_performance_whitepaper.md` | ✅ MET |

**性能结论**：性能不是当前瓶颈，**验证深度才是**。把 1.1s 的自证桩判定换成真交叉验证，即使慢 100 倍（110s）也完全可接受 —— 这为下一步研发规划提供了明确的"预算空间"。

---

## 五、下一步研发规划

> 约束前提：**杜先生 1 人 + AI**。执行主体：**【AI】**=AI 自主 · **【AI+杜】**=AI 干活杜拍板 · **【杜】**=必须杜先生出面 · **【锁】**=C 期锁死，需解锁信号

### 排序原则（本轮确立）

1. **先"证锚"后"加锚"**：新增锚题在自证桩问题解决前不产生验证价值（D-63 已证明：换 golden 仍全绿）
2. **先接线段后获取段**：外部真值（30 条 A 级语料）已经够了，缺的是 candidate 与之对照 → 不需等 C 期
3. **不依赖外部解锁的优先**：能由 AI 独立完成、不触发 C 期三信号的工作优先

---

### P0 · 立即（本轮 1–2 周）— 把自证桩转成真交叉验证

| # | 动作 | 目标 | 主体 | 对应 |
|---|---|---|---|---|
| **P0-1** 🔥 | **B 类锚独立候选化（分批）**：为 B 类 28 道物理定律锚配置**不读 golden 的独立候选算法**。第一批选"解析锚可有第二算法路径"的：B15 Bragg（TMM 解析 ↔ FDTD 谱）、B17 Josephson（I_c 解析 ↔ 数值 RCSJ 积分）、B21 PhC（Bragg/FP 解析 ↔ TMM 多层膜）、B22 CPW λ/4（解析 ↔ 传输矩阵）、B23 Fluxonium（严格 LC 极限 ↔ 数值对角化）、B24 耦合（二阶微扰 ↔ 数值对角化） | 让 harness 判决从"自洽"变"验证"；**每道都要做反向测试（扰动 rel_err 必 FAIL）** | 【AI】 | 🔴 最高价值发现 |
| **P0-2** | **新增 `run_benchmark_falsifiability_smoke.py`**：遍历全部 48 题，断言 ①独立候选数 ≥ 6（P0-1 后）、②自证桩数逐版递减不回弹、③对每题注入 `harness_perturbed_candidate(0.05)` 必须 FAIL | **没被验证过的护栏不算护栏**（D-67 铁律）；同时一次性终结 N-1/N-2 覆盖争议 | 【AI】 | N-1/N-2 |
| **P0-3** | **补 B5/B7/B10 的 CI 覆盖**：B5/B7 是 `design-rule(... field 预留)` 自证桩（golden 为理想下限），B10 是 `analytical(decoherence-limit)` 解析锚 → 三道都要进 P0-2 的全量遍历判决 | 消除零覆盖锚题 | 【AI】 | N-1 |
| **P0-4** | **DC / YBranch 候选去 GPU 依赖**：把 torch CUDA 3D FDTD 候选改为 **numpy/numba-cpu 版本**（降分辨率降网格即可，交叉验证不需要满精度），让 5 个 device 在无 GPU 环境全部可现场演示 | 默认环境可演示的交叉验证 **1 → 5** | 【AI】 | N-3 |
| **P0-5** | **Waveguide / BraggMirror heavy 项轻量档**：加 `live_weight="medium"` 降配档（粗网格/少波长点），进 CI 常规跑 | 5 个 device 交叉验证全部进 CI 门禁 | 【AI】 | N-3 |
| **P0-6** | **实证语料对照化**：30 条 A 级语料对应的 7 道 E 锚，除 E2 外全部自证 → 为 E4(交叉插损)/E5(MMI 过量损耗)/E7(串扰)/E3(FSR) 配独立候选（解析/几何/功率守恒路径） | 把"外部真值已具备"变成"外部真值真在判决" | 【AI】 | 判断一 |

**P0 完成后的量化目标**：可证伪锚题 **0 → ≥ 6**（B 类）+ 7（E 类，含已降级的 E2 转正面）+ device 交叉验证可演示 **1 → 5**。

---

### P1 · 近期（2–4 周）— 商业取证 + 工程质量

| # | 动作 | 目标 | 主体 | 对应 |
|---|---|---|---|---|
| **P1-1** 🔥 | **零成交取证**：取生产访问日志（nginx access log）看真实流量与来源；若有流量，定位转化断点（注册？浏览货架？下单未支付？） | 回答"为什么 0 成交"，而不是猜 | 【杜：提供 ssh 凭据】【AI：分析】 | 判断二 |
| **P1-2** | **numba 硬依赖软化为可选**：`fdtd3d_numba.py` / `adjoint_fdtd3d.py` 改为 try-import + numpy 回退 | 兑现"纯 numpy 零依赖"宣称 | 【AI】 | N-4 |
| **P1-3** | **巨型文件治理**：`innovation_market.py` 2652 行数据字面量抽为 JSON 资源；`app.py` 3182 行再拆一层 | 降低 AI 改动风险 | 【AI】 | N-5 |
| **P1-4** | **30 个无门禁冒烟分类处置**：能进 core 的进 core；确实重/FDTD/GPU 的显式登记为 `--tag all` 并写清理由 | 消除"有没有门禁说不清" | 【AI】 | N-6 |
| **P1-5** | **定制报价自动化**（上轮 P1-2 顺延）：按"方向 + 复杂度档位"生成参考报价区间，减少 `quote_later` | 缩短转化链路 | 【AI+杜】 | R11 |

---

### P2 · 中期（1–2 月）

| # | 动作 | 目标 | 主体 | 对应 |
|---|---|---|---|---|
| **P2-1** | **社区信号自证看板** `/stats` 页（不依赖 GitHub API） | 解 R17 单点依赖 | 【AI】 | R17 |
| **P2-2** | **token 存 HttpOnly Cookie 改造** | 根治 XSS 窃取 | 【AI】 | R15 |
| **P2-3** | **生产模式拒绝默认 dev token**（`app.py:212` 未设 `LDA_ADMIN_TOKEN` 时回退硬编码值） | 防自建用户漏配被公开绕过 | 【AI】 | 安全遗留 |
| **P2-4** | **语料扩军**（上轮 P2-3 顺延）：补 10–20 条带 DOI 的真实测量语料 | 加厚第二支柱 | 【AI】 | R3 |

### P3 · 发动期（解锁才动）

维持纪律：**三信号全空则严格锁死，不碰**。

| # | 动作 | 解锁条件 |
|---|---|---|
| **P3-1** | 外部 ORACLE（Meep 隔离环境）真跑通 → 解 R2/R20，让"双 ground"可现场演示 | 【锁】信号① |
| **P3-2** | 弯曲波导 FDFD（柱坐标/弯曲修正 ε）→ 让 E1/E2 重回死标量对照 | 【锁】信号①或② |
| **P3-3** | 院校/晶圆厂 PDK 外联、实测回流闭环 | 【锁】信号② |

---

## 六、待杜先生拍板的决策点

| # | 决策 | 选项 | AI 建议 |
|---|---|---|---|
| **E1** 🔥 | **下一步研发主线投哪里？** | A. **锚题独立候选化（P0，AI 全自主，1–2 周）**<br>B. 商业取证优先（P1-1，需您出面）<br>C. 两条并行 | **A 优先**：这是唯一能由 AI 独立完成、且直接提升"可被外部验货"硬指标的工作；商业取证需要您提供 ssh 凭据，可与 A 并行但不阻塞 A。**建议 A 立即启动，B 待您有空时提供凭据** |
| **E2** | **P0-4 是否值得做？**（为 DC/YBranch 写 numpy 版候选，解 GPU 依赖） | A. 做（可演示交叉验证 1→5）<br>B. 不做（等 GPU 环境） | **A**：降配版候选用于交叉验证完全够（交叉验证不要求满精度），且能让**任何无 GPU 的外部验证者**现场跑通 —— 这正是"可被外部验货"的核心场景 |
| **E3** | **是否解锁外部 ORACLE（Meep）？** | A. 维持锁定<br>B. 解锁（装 Linux Meep 隔离环境） | **A 维持锁定** —— 与 C 期纪律一致。且本轮发现：即使不解锁 Meep，内部"接线段"（P0）也有 47 道锚的工作可做，ORCALE 不是当前瓶颈 |
| **E4** | **生产订单数据是否现在再取一次？** | A. 现在取（可顺带取 nginx 访问日志做 P1-1 取证）<br>B. 暂不取 | **A，且建议同时取 nginx access log**：08-30 取过订单（真实用户 1 / 订单 0），但**从未取过访问日志**——"0 成交"无法区分"没人来"和"来了没买"，这是商业侧最大的信息盲区 |

---

## 七、本轮审计的诚实边界

1. **"47/48 自证桩"是 harness 路径的口径**，不等于 LDA 全部验证资产失效 —— device_library 5 设备、B28/S13 双算法互证、GC-\* 29 条、30 条 A 级语料均独立存在且有效。
2. **N-1/N-2 覆盖率用文本匹配得出**，可能低估（若脚本通过 `_GOLDEN_DISPATCH` 遍历则不点名）。已用 P0-2 设计（新增全量遍历 smoke）来终结争议，而非直接下结论。
3. **商业侧无新证据**：本轮未重复取生产订单数据（上次 08-30），故商业评分持平而非"无变化已验证"。
4. **回归复跑结果见附录 A**：若与本轮其他结论冲突，以复跑结果为准。

---

## 附录 A · 复现命令

```bash
PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
cd /d/agent_LDA

# ① 48 锚自证桩量化（本轮最高价值发现）
cd lda && "$PY" -c "
from lda_harness.verification_adapters import build_harness_specs
from lda_harness.verification_spec import run_verification
specs,cand=build_harness_specs()
n=0
for sp in specs:
    ov=sp.oracle_fn(sp.params); cf=cand[sp.spec_id]; cv=cf(sp,ov)
    n += abs(cv-ov)<1e-12
print('自证桩:',n,'/',len(specs))"

# ② device_library live 交叉验证
"$PY" -c "
from lda_l2.device_library import DeviceLibrary
outs,skipped=DeviceLibrary().verify_all(mode='live')
print({k:(v.passed if v else 'SKIP') for k,v in outs.items()}, 'skipped:',skipped)"

# ③ 语料溯源审计
"$PY" lda/run_provenance_audit.py

# ④ CI 条目数核准
"$PY" -c "import sys;sys.path.insert(0,'lda');import run_ci_regression as r;print(len(r.CORE_SMOKES))"

# ⑤ 全量 core 回归
cd lda && "$PY" run_ci_regression.py --tag core

# ⑥ 社区信号
"$PY" scripts/probe_github_signals.py
```

## 附录 B · 全量 core 回归复跑结果

> **状态：复跑已完成 ✅**（日志 `ci_core_run_audit_0902.txt`）。

| 项 | 结果 |
|---|---|
| 复跑时间 | 2026-09-02，基线 commit `2dda10c`（v0.9.13，工作区无代码改动） |
| PASS / SKIP / FAIL | **84 PASS / 0 SKIP / 0 FAIL** |
| 耗时 | **1326.62s**（约 22.1 分钟） |
| EXIT | **0** |

**交叉验证**：与 2026-09-01 同一 commit 的基线 **84 PASS / 0 SKIP / 0 FAIL（1377.55s，EXIT=0）**（证据 `ci_core_run_v0913.txt`）完全一致——条目数、SKIP 数、FAIL 数、退出码四项全同，耗时差 3.7%（机器负载波动，非能力变化）。

**结论**：第三章「功能对齐」判定的可复现性得到二次确认。同时请注意本报告的核心论点——**84/84 全绿与「48 锚中 47 道为自证桩」并不矛盾**：回归全绿证明系统功能无回归，而自证桩证明验证强度不足；前者是必要条件，后者才是本报告要解决的真问题。**全绿不等于可证伪**，这正是 P0 计划存在的理由。

**耗时分布观察**（复跑日志）：`run_splitter_readout_smoke.py` 192.25s + `run_splitter_readout_cal_smoke.py` 171.74s，两条合计 364s ≈ 全量 27%。二者是 P0 阶段每次改动都要付的固定成本，后续若需加速可从这两条入手（非当前瓶颈，不列入规划）。

---

*审计人：AI（WorkBuddy） · 基线 commit `2dda10c` · 方法：代码实测优先，文档声明不作为证据*
