# LDA 三合一对齐审计报告（新征程基线版）

> 版本基线：**v0.9.186**（HEAD `1d5cc90`）· 日期：2026-10-04 · 性质：**战略/功能/代码三审计**（不改锚、不动棘轮、不发版）
> 使命：为「光子存储芯片征程」提供平台能力基线——**让客户使用之前，自己先用、先检验、补短板。**
> 方法：全部结论来自代码实测（Grep/Glob 计数、门禁复跑、生产探测），凡推断一律标注；上一轮基线 = `docs/audit_{strategic,functional,code}_v0.9.169_2026-10-01.md`。
> 配套文档：`docs/LDA_光子存储芯片征程_总蓝图_v1_2026-10-04.md`

---

## 0. 执行概要（结论先行）

| # | 维度 | 结论 | 状态 |
|---|---|---|---|
| 1 | 技术侧 | 栈完整、主权干净、验证可证伪：476 锚 / 独立率 95.59% / CI core 274 / 三栈贯通 / 主权 GDS 实证 / 生产在线 | ✅ |
| 2 | 文档↔代码漂移（上轮 C1） | README 顶行与 pyproject/CHANGELOG 三同步，v0.9.186 口径实测一致 | ✅ 已治愈 |
| 3 | 功能复跑（CI core 274 全量分批） | **274 PASS / 0 SKIP / 0 FAIL · 6525.5s · min_margin 3.11× · low_margin 空 · 零 safe-delete 假红**（单次干净全量） | ✅ |
| 4 | 静态卫生 | pyflakes 棘轮 8/8 PASS（F401≤201/F841≤0/F541≤0/F811≤0/F821≤0/OTHER≤0） | ✅ |
| 5 | 结构卫生（上轮 C3–C8） | **smoke 平铺（286 个）、redteam JSON 入树、scratch 残留、`lda_l3` 空壳、无 `__version__` 全部未动** | 🔴 原样 |
| 6 | 光子存储能力底座 | U8 非易失权重条件式设计 + U4 微环权重库 + 热/WDM/BER/版图签核全链路在库；**缺 5 类模型**（§5 预判） | 🟡 部分就绪 |
| 7 | 商业主矛盾 | 生产健康（0.9.186/476 锚），GitHub 1 star/2 forks，**零真实外部用户从未改变** | 🔴 持续瓶颈 |
| 8 | 征程判定 | 技术侧具备启动光子存储征程的条件；征程本身即是对短板 #5/#6 的系统性清偿 | 🟢 可启动 |

---

## 1. 能力账本（实测快照，非文档声明）

| 指标 | v0.9.186 实测 | 上轮（v0.9.169） | 变化 |
|---|---|---|---|
| 验证账本 | **476**（B1–B458） | 476 | 持平 |
| 独立率 | **95.59%**（strict 455 / 桩 18） | 95.59% | 持平 |
| CI core 门禁 | **274**（`len(CORE_SMOKES)` 实测） | 260 | +14 |
| smoke 文件 | `lda/run_*_smoke.py` **286** 个 | 272 | +14 |
| 代码规模 | `lda/` **713** 个 .py · **~214,800 行** | 686 个 | +27 模块 |
| 端点 | **146**（README/CHANGELOG 口径） | 146 | 持平 |
| 生产 | `https://lda.weomnitech.com.cn` health `0.9.186` / `benchmarks 476` / uptime 正常 | — | ✅ 在线 |

## 2. 战略对齐矩阵（2026-10-04 刷新）

| 战略目标 | v0.9.169 审计状态 | **本次实测** | 变化 |
|---|---|---|---|
| 验证可证伪（判决落非 AI ground） | 独立率 95.59% | 持平（棘轮/门禁在守，`run_timeout_budget_ratchet` 21/21 记录在案） | 🟢 维持 |
| 三栈贯通（光+量+电） | E1–E19 闭环 | + **光联接 OI M0–M5 闭环**（v0.9.176–186：800G/1.6T/3.2T·热-光-电耦合链·VπL 断口结算） | 🔺 +一程 |
| 主权依赖干净 | redline/four_layer_gate 在守 | 维持；U8 三守卫（无 foundry 真值/无假实测/锚缺数字即 raise）实测在位 | 🟢 |
| 工程门禁 | 260 | 274（新增 oi_m5/webui_json_hard 等） | 🔺 |
| 能力→可交付物（D3→D4） | 光子单路径闭合 | OI 域 G-OI2/G-OI5/G-OI6 真 GDS 接力；**ecore/量子仍零 D4 路径** | 🟡 |
| 对外载体不失真（R2） | 白皮书/BP 修复至 v0.9.169 口径 | README ✅；白皮书/BP 数字口径（476/274 内一致）未再漂移，但**版本号停在 v0.9.169**（17 版未更新叙事） | 🟡 部分 |
| 互操作（R4） | 缺位 | `gdsfactory_available()` 优雅降级已修复（v0.9.183）；interop 验证脚本仍不被 CI 调用（gdstk 缺失即 SKIP） | 🟡 微进 |
| 真实用户/客户（R1） | 零 | **仍为零**（GitHub 1 star / 2 forks / 5 open issues；生产深度使用均来自 AI 与本人） | 🔴 未变 |
| 生态信号（R5） | 静止 | 静止 | 🔴 未变 |

**战略判断**：
1. 技术主矛盾已从「可信度」转为「**能力的可交付化 + 用征程喂养平台**」——光子存储征程正是当前最优载体（光子域复用率最高、且有 U8 现成底座）。
2. 商业主矛盾（零真实客户）**依旧未被触碰**，属杜先生 lane；征程期间不粉饰。
3. 结构卫生债（C3–C8）连续两轮审计原样未动——**不能再拖**，建议作为征程 M0 的伴随工作清偿（见 §7 行动清单）。

## 3. 功能对齐（CI core 274 全量复跑 · 分批防掉电）

> 命令：`scripts/ci_core_batched.py --python versions/3.14.3/python.exe --batch 18 --cooldown 12`（16 批，日志/报告落 `%TEMP%`）。
> **结果（单次干净全量，非合成）：274 PASS / 0 SKIP / 0 FAIL · 总耗时 6525.5 s（≈109 min）。**

| 项 | 实测值 | 判定 |
|---|---|---|
| PASS / FAIL / SKIP | **274 / 0 / 0** | ✅ 单次原始输出即全绿（无需单点复跑补口） |
| 总耗时 | 6525.5 s（16 批） | ✅ 与 v0.9.185 的 6330.9 s 同量级（+3.1%，抖动范围内） |
| 预算余量体检 `min_margin` | **3.11×** | ✅ ≥3× 目标档守住 |
| `low_margin`（<2× 欠标定） | **空** | ✅ 无需重标定 |
| safe-delete 假红 | **0**（`SAFE_DELETE` 计数 0） | ✅ 本轮无该形态假红（续 v0.9.185 观察：条件性而非必然） |
| 残留件 | `_tmp_g1_*.py` / `.pollute_tmp` / `run_zz_bad_smoke.py.bak` 全无 | ✅ |
| 工作树 | 仅本轮 2 份新审计文档（未跟踪），无 tracked 改动 | ✅ 审计未污染仓库 |

- 静态卫生门禁（单独复跑）：`run_pyflakes_ratchet_smoke` **8/8 PASS**（含 4 条反向探针）。
- 上轮（v0.9.183）的 16 项失败欠账**零复现**；v0.9.186 发布当时冒出的超时棘轮新成员漏登（真红）已随发布清偿——**本轮 274 条一次性全绿即为其收口证据**。
- 判读纪律留痕（供下次复用）：① 依赖类报错先查环境（本轮 3.14.3 依赖齐备：numpy/scipy/torch/jsonschema/pyflakes/numba）；② TIMEOUT 先查可选加速依赖与线程口径（本轮无 TIMEOUT）；③ safe-delete 假红按三步判据。

## 4. 代码对齐（静态/结构层）

### 4.1 正向（在守的纪律，实测）
| 项 | 证据 |
|---|---|
| pyflakes 棘轮 | 8/8 PASS（本轮复跑）；F401 地板 201 |
| 版本线单一真源 | pyproject v0.9.186 ↔ README 顶行 ↔ CHANGELOG 段，三处一致 |
| 判据纪律 | v0.9.185 独立复核 11 项假判据清零（三层自证链通法已立）；`closed ⇔ evidence_ok` 机器耦合 |
| GDS 门禁 | UNITS 独立解码 + 全仓 glob + 反向探针（58/58 绿，v0.9.184 收口） |
| 标准 JSON 出口 | `allow_nan=False` + `run_webui_json_hard_smoke` 常驻（v0.9.186 浏览器崩病根已消） |

### 4.2 结构问题复核（对照上轮 C1–C8）

| # | 问题 | 本次实测 | 状态 |
|---|---|---|---|
| C1 | 文档↔代码漂移 | README 顶行 v0.9.186 与代码/账本一致；`grep -c "B458\|476" README` = 37 处口径在位 | ✅ 治愈 |
| C2 | ecore 模块数口径 | 实测 `lda_l2/ecore/` 23 模块（上轮报 24，口径已统一） | ✅ |
| C3 | smoke 平铺无 tests/ 包 | **286 个** `run_*_smoke.py` 仍平铺 `lda/` 根（+14） | 🔴 未动 |
| C4 | 大型 JSON artifact 入树 | `redteam_*.json`×3 仍在 `lda/`；`timeout_budget_baseline.json` 属门禁真源（正当） | 🔴 部分 |
| C5 | scratch 残留 | `_assess_b2_semi_fd.py` + `_magent_b2_*.py`×3 仍在 | 🔴 未动 |
| C6 | `lda_l3` 实质空壳 | 仍仅 1 模块（production_plan） | 🔴 未动 |
| C7 | 无 `__version__` 常量 | `import lda` 无 `__version__` | 🔴 未动 |
| C8 | build artifact 入树 | `git ls-files *egg-info*` = 空 | ✅ 治愈 |

### 4.3 新观察（本轮新增）
- N1：smoke 文件 272→286（+14 = CI core 增量），平铺问题在**加速恶化**；门禁反向完备（成员⊆白名单）已覆盖 CORE_SMOKES，风险主要在可维护性。
- N2：`run_ci_regression` 内置超时覆盖 274 项（falsifiability 4200s / fuzz 5400s），预算棘轮门禁 21/21 在位——时长类假红防线完整。
- N3：pyflakes F401 地板 201 偏高（多为 `torch`/`numba` 可选依赖守卫模式），棘轮只升不降可接受；不建议为降数字而动（会碰守卫语义）。

## 5. 光子存储征程能力基线（新增维度）

**已有（实测在库）**：
- `lda_l2/nonvolatile_weight_backend.py`（U8）：PCM/Sb₂Se₃ **条件式设计**——相态→晶化率→电平接口、参数化预算（位深/retention/endurance/静态功耗省量）、三条红线守卫（无 foundry 真值/无假实测/锚缺数字即 raise）、`wrap` 相位等价政策；文献锚全部 `is_measured_by_this_project=False`。
- `lda_l2/ring_weight_bank.py`（U4）：MRR 幅度权重闭式正反演、档位极差位深口径、κ∉[0,1] 必 raise。
- 热-光-电链（oi_m2b Γ 矩阵 / oi_m4 三域耦合）· WDM 信道规划（oi_m1）· PAM4/BER 链 · 主权 GDS/DRC/LVS · 良率 MC · calibration_protocol。

**预判缺口（M0/M1 证实/证伪，详见蓝图 §3）**：
1. GST/GSST 光学常数库 n,k(λ,相态)（波长插值 + 「单点锚不外推曲线」判据）；
2. 瞬态热（冷却时间 = set/reset 周期下限；现只有稳态）；
3. 晶化动力学 JMAK/Avrami 最小闭式模型；
4. 多电平读出 SNR→BER 低频口径；
5. 非晶态光学 drift 模型（retention 物理来源）。

**国际对标锚候选（均已带 DOI，登记规格锚时逐条核对原文数字）**：
- MDPI Photonics 12(11):1130 (2025)：**209 态（>7.6 bit）· 0.96 pJ 写 · 9 fJ 读 · 6000 次 endurance**
- ACS Photonics 11(2):723-730 (2024)：N-GST 电编程 **>7 bit（~222 电平）**，MNIST 96.5%
- J. Optical Microsystems 4(3) 031208 (2024)：Si strip+GST **4 bit/cell @ 6% 间距**（系统对比研究）
- Plasmonics 20(12) (2025)：结晶时间 **180–250 ps** · 4 电平 · >10⁴ 次
- 经典底座（如需）：Ríos et al. Nat. Commun. (2015) 集成全光非易失多电平存储；Feldmann et al. Nature 594 (2021) 光子存内计算。

## 6. 商业/线上取证（轻量复核）

- 生产：`/api/health` = `0.9.186` / `benchmarks 476` / `pdks 5` ✅（与本轮仓库 HEAD 一致，无版本漂移）。
- 生态：GitHub `stargazers 1 / forks 2 / open_issues 5` —— 自 09-03 审计以来**实质静止**。
- 结论：R1（真实市场需求未验证）维持原判；本轮审计不重复 09-03 的全量取证。

## 7. 优先行动清单

| 级别 | 行动 | 理由 |
|---|---|---|
| **P0** | 启动光子存储征程 **PM-M0**（单单元闭式基线 + `pm_matlib` 缺口证实） | 用征程喂养平台，最高杠杆 |
| **P0** | ~~CI 全量结果回填本报告 §3~~ ✅ **已完成：274/0/0 单次干净全绿，`low_margin` 空，无需重标定** | 功能对齐闭环 |
| **P1** | 结构卫生清偿：C3 smoke 归包（先做反向完备白名单）、C4 redteam JSON 迁出、C5 scratch 清理、C7 `__version__` 真源 | 连续两轮原样，债在滚大 |
| **P1** | ecore/量子域 D4 交付路径（拿走东西） | 商业前置条件 |
| **P2** | 白皮书/BP 版本叙事更新（v0.9.169 → 0.9.186，17 版故事） | 对外可信度 |
| **P2** | interop 验证脚本进 CI（gdstk 可选面） | R4 互操作 |

## 8. 审计边界

- 功能对齐以 CI core 274 为口径；`--tag all`（非 core 296 项）未跑，`noncore_replay_ledger` 台账在守。
- 未做 import-graph 死代码全分析（上轮 W6-3 遗留，随 C3 归包一并做收益更高）。
- 商业取证为轻量复核，非全量。

---
*复现命令（附录）*：
```bash
# CI core 全量分批（防掉电口径）
cd D:/agent_LDA && C:/Users/Administrator/.workbuddy/binaries/python/versions/3.14.3/python.exe \
  -u scripts/ci_core_batched.py --python C:/Users/Administrator/.workbuddy/binaries/python/versions/3.14.3/python.exe \
  --out <仓库外>/report.json --batch 18 --cooldown 12 > <仓库外>/ci.log 2>&1
# pyflakes 棘轮
cd D:/agent_LDA/lda && C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe run_pyflakes_ratchet_smoke.py
# 预算余量
cd D:/agent_LDA && C:/Users/Administrator/.workbuddy/binaries/python/versions/3.14.3/python.exe -m lda.run_timeout_budget_ratchet_smoke
```

*报告主体版权：上海杜特企业管理咨询有限公司 · LDA 工程（AI 代行工程决策）· 2026-10-04*
