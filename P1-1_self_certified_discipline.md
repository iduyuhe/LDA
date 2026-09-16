# P1-1 自证桩常态化纪律：「PR 必接独立候选」

> 配套 B-3 收官 + B16 重审（v0.9.80，84 锚 / 严格独立 60/84 = 71.4% 跨过 70% 红线）。
> 本文件把**剩余 21 道自证桩**从「B-3 冲刺对象」转为**常态化工程纪律**，并订正此前过时口径。
> 所有数据均来自 `lda/lda_harness/benchmarks.py` 的 `_vmm_classify` 真值推导，非记忆推断。

---

## 1. 闭项与定位

- **B-3 专项已闭项 + B16 重审收官（v0.9.80）**：84 锚、严格独立 **60** 道、降级 3（B21/E9/E10）、自证桩 **21**，独立率 **71.4%**（60/84）正式达标。
- 21 道自证桩**不再**作为一次性 sprint 目标，改为常态化纪律约束：任何触及它们的 PR 必须走「接独立候选 / 显式锁定」二选一。
- 目的：杜绝「自证桩批量伪绿」，把升级路径固化进 PR 评审而非靠人记。

---

## 2. 纪律定义（触发条件 + 处置矩阵）

**触发条件**——任意 PR 满足其一即受本纪律约束：
1. **新增**一道验证锚；
2. **修改**任一 `self_certified` 或 `degraded_ordinal` 锚的 `defn` / `candidate` / `golden` / `candidate_status`。

**处置：二选一（强制）**
- **A. 接独立候选** → 升 `strict_independent`（`"candidate" in defn`，方法学不同源，判据 D 扰动 `|diff|≠0` 复现 golden）。
- **B. 显式锁定原因** → `defn` 必须带 `provenance` + `upgrade_path` 注明锁定类型：
  - `terminal_tier1`：定义同义反复 / 算术自检 / regime 越界——**按设计永不升**，不是缺口。
  - `design_rule_anchor`：行业经验边界（几何无关下限/上限），待场级 ORACLE 升 strict。
  - `t2_blocked`：外部实测通道未就绪（E 簇 QEDA 实证锚），路径明确但卡通道。
  - `re_review`：已有明确升级路径待执行（**当前无实例**；B16 已于 v0.9.80 重审升 `strict_independent` 结清）。

**红线**
- `self_certified` 计数**只减不增**。
- 新增 `self_certified` 锚若无锁定原因 → CI 拒绝合并。
- 任何 `degraded_ordinal` → `strict` 的晋升，必须附「方法学不同源」证据（复用 `lda-anchor-wiring` 技能流程）。

---

## 3. 21 道处置映射（权威，harness 推导 · v0.9.80 刷新）

| 桶 | 锚（共 21） | 锁类型 | 升级路径 | 是否「必接候选」范围 |
|---|---|---|---|---|
| **terminal Tier-1（12）** | B17, B18, S1, S2, S3, S4, S5, S6, S9, S10, S11, S12 | `terminal_tier1` | 定义同义反复 / 算术自检 / regime 越界，**永不升** | ❌ 否（按设计诚实，非缺口） |
| **design_rule（3）** | B5, B6, B7 | `design_rule_anchor` | 待 Meep/Tidy3D 场级 ORACLE 动态升 strict | 🟡 低优先（并入 S8/T2 真值链） |
| **t2_blocked（6）** | E1, E3, E4, E5, E6, E7 | `t2_blocked` | T2 实测数据集（QEDA 实证锚）升 Tier-3 | ✅ 是（卡 T2 外部通道） |

> 合计 12 + 3 + 6 = **21**，与 `run_p0_count_guard_sync_smoke.py` 的动态推导一致。

**真正的「方法学独立候选」= 6 道**：`E1/E3/E4/E5/E6/E7`（B16 已于 v0.9.80 重审升 strict，正式结清）。

---

## 4. ⚠️ 口径纠正（重要，已同步 ALIGNMENT_REPORT）

此前 `ALIGNMENT_REPORT.md` 第 132、149 行写「**B17-B19 / S1-S13 方法学独立候选**」为**过时口径**，现据代码真值订正：

- **B17 = `terminal Tier-1`**（定义同义反复，本就不升）——非候选。
- **B18 = `terminal Tier-1`**（regime 越界，本就不升）——非候选。
- **B19 早已是 `strict_independent`**（不在 22 自证桩内）——非自证桩。
- **S 簇**：实际为 `S1-S6` + `S9-S12` = **12 道 terminal 算术自检**，无 `S7/S8/S13`；全部 `terminal_tier1`，非候选。
- 真正可升级的自证桩是 **E1/E3-E7（T2 实证锚）= 6 道**（B16 已于 v0.9.80 重审升 strict），并非 B17-B19/S1-S13。

> 该纠正已写入 `ALIGNMENT_REPORT.md` 第 132、149 行。

---

## 5. 执行清单（待拍板启动，非本次自动执行）

| 项 | 内容 | 阻塞 | 优先级 |
|---|---|---|---|
| ~~B16 重审~~ | ✅ **v0.9.80 已完成**：rib-MMI 全场模态重构候选升 strict（残差 0.26–2.21µm < tol 3.0；候选不套成像因子，方法学不同源） | — | ✅ 结清 |
| E 簇解锁 | 启动 T2 外部通道，接入 QEDA 实测数据集，E1/E3-E7 升 Tier-3（=严格独立候选） | 卡 T2 实测通道（S8） | 🔴 高（受外部 KPI） |
| B5/B6/B7 | 待 Meep/Tidy3D 场级 ORACLE 升 strict | 场级求解器专题 | 🟡 低 |
| CI Enforcement | 新增 `run_self_certified_lock_smoke.py`：断言 (a) self_certified=21 且只减不增；(b) 每道 self_certified 的 defn 带 provenance + 锁定类型关键词 | 无 | 🟠 建议 |

---

## 6. 诚实边界

- **12 道 terminal Tier-1 是设计上诚实的自检桩**，不是缺陷、不是待清项，不计入「升级缺口」——它们是算术/定义守恒校验（如分束比归一、能量守恒），本就无需独立物理候选。
- **self_certified 占比 25.0%（21/84）是真实短板但已持续缓解**：B-3 前 31.0%（22/71）→ B-3 后 26.2%（22/84）→ B16 重审后 **25.0%（21/84）**，且余下 6 道真候选均有明确路径，**无「伪绿」**。
- **degraded_ordinal（3 道）不计入自证桩**，它们有独立候选（跑了真求解器）但不进死标量判决列，是另一种诚实降级，受 P1-2/P1-3 纪律约束。

---

## 7. 关联纪律

- 计数护栏同步：`run_p0_count_guard_sync_smoke.py`（84/60/3/21 动态校验，PR 必查）。
- 锚接线流程：技能 `lda-anchor-wiring`（判据先于代码 + maintainer 写判据）。
- 生产部署：`lda-prod-deploy`（`sync_push.py` + `remote_deploy.py --expect-head`）。
