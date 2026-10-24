# LDA · N3-a 逐卡补 anchors（签核锚可复核）· 规划与实施

> **版本**：v0.9.283（N3 续）· **账本 541 不变 · CI core 350 不变**（判据并入既有门禁）
> **定位**：闭合 N3 登记的 **V2 缺口**（`ANCHOR_UNREGISTERED_CASES` 14 → **0**）
> **前序**：`docs/LDA_N3_四域签核schema统一_规划与实施_2026-10-24.md`

---

## 0. 一句话结论

N3-a 表面是"给 14 张卡补个 `anchors` 字段"，实际做下来是**三件事**：

1. **18/18 卡现在都能回答"我签的是哪些锚"** —— 且 **107 条锚逐条带标题**（从账本现取，不手抄）。
2. 🔴 **锚登记必须分证据等级** —— `runtime`（卡内实测）只有 **1 张**（`oi`→B19），`segment`（号段归属）**15 张**，`none`（确实不依赖锚）**2 张**。把 `segment` 读成 `runtime`，就是"把号段归属当已验证"。
3. 🔴 **`on_card` 从"手填 bool"改成"运行时读卡"** —— 改完当场抓出 **3 处漂移**（下面 §4），其中 2 处是**上一版 schema 自己登错的**。

---

## 1. 起点：V2 缺口的准确含义

N3 登记的 V2 是：

> 4 张 `DESIGN_SIGNOFF` 卡（pchip/pm/soc/schip）卡上**都没有 `anchors` 字段** ⇒ 外部无法复核"它签的是哪些锚"。

仔细读会发现它说的**不是**"schema 表里没登记"，而是"**卡上没有字段**"。
这两件事差别很大：

| 做法 | 结果 | 是否可审计 |
|---|---|---|
| 只改 schema 的 `on_card=True` | 表上显示"已登记" | ❌ **自证**：表说自己对 |
| 改卡 + 运行时读卡对拍 | 表 ⇄ 卡 逐条相等才绿 | ✅ 可复核 |

⇒ N3-a 必须**改案例卡本身**，并把 `on_card` 改成**算出来的**。

---

## 2. 关键设计：三档证据等级（本项最重要的判断）

补字段时立刻撞上一个问题：**"该卡有锚"这件事，证据强度并不一样。**

- `oi_case` 里有 `b19_passivity` 字段，`case_card()` 返回 **True** —— 这是**卡内真的跑了** B19（无源无增益不等式）。
- `sensor_case` 没有任何锚号引用，但它的征程就是 PS 传感，账本 B459–B472 那 14 条**按号段归属就是它的**。

这两件事**不是一回事**。所以加了 `anchors_source` 三档：

| 档 | 含义 | 判据 |
|---|---|---|
| `runtime` | 卡内代码/字段**实测**该锚 | 卡上能找到可观测字段（本项目只有 `oi` 的 `b19_passivity`） |
| `segment` | 依据账本**号段归属**登记 | 号段与该卡征程对应，但卡内无运行时引用 |
| `none` | 本卡确实**不依赖**账本锚 | 如实登记为空，并有说明 |

🔴 **为什么必须分**：本项目已经踩过三次"用聚合数字代表一件事"（`l2_count` 均值、报告反算残差、关键词分类器）。
`segment` 写成 `runtime` 就是第四次 —— **把号段归属当成已验证**。

**实测分布**：`runtime 1` / `segment 15` / `none 2`。

> `none` 的 2 张不是"缺漏"，是**事实**：
> · `accel` —— 跨域拼接演示，基准是**全精度数字参考**，不用账本锚；
> · `ecore` —— 电子域专属锚 **0 条**（N1 判死报告已证）。

---

## 3. 18 卡签核总表（全部数字现算）

| 域 | 卡 | declared | effective | evidence | deck | anchors | source |
|---|---|---|---|---|---|---|---|
| 光子 | `accel` | DESIGN_BUDGET | **DESIGN_BUDGET** | BUDGET | none | — | none |
| 光子 | `oi` | DESIGN_BUDGET | **DESIGN_BUDGET** | BUDGET | none | 1 | **runtime** |
| 光子 | `pchip` | DESIGN_SIGNOFF | **DESIGN_SIGNOFF** | BUDGET | self_built | 2 | segment |
| 光子 | `pm` | DESIGN_SIGNOFF | **DESIGN_SIGNOFF** | BUDGET | self_built | 2 | segment |
| 光子 | `sensor` | DESIGN_BUDGET | **DESIGN_BUDGET** | EMPIRICAL | none | 14 | segment |
| 光子 | `soc` | DESIGN_SIGNOFF | **DESIGN_SIGNOFF**／claimable **AUDIT_ONLY** 🔴 | BUDGET | foundry_public | 12 | segment |
| 电子 | `ecore` | DESIGN_VERIFIED | **DESIGN_VERIFIED** | NONE | none | — | none |
| 超导 | `schip` | DESIGN_SIGNOFF | **DESIGN_SIGNOFF** | STRICT | self_built | 16 | segment |
| 量子 | `d1` | DESIGN_BUDGET | **DESIGN_BUDGET** | STRICT | none | 2 | segment |
| 量子 | `d2` | DESIGN_BUDGET | **DESIGN_BUDGET** | STRICT | none | 1 | segment |
| 量子 | `d4` | DESIGN_BUDGET | **DESIGN_BUDGET** | BUDGET | none | 3 | segment |
| 量子 | `j1` | DESIGN_BUDGET | **DESIGN_BUDGET** | STRICT | none | 9 | segment |
| 量子 | `j2` | DESIGN_BUDGET | **DESIGN_BUDGET** | STRICT | none | 4 | segment |
| 量子 | `j3` | DESIGN_BUDGET | **DESIGN_BUDGET** | STRICT | none | 5 | segment |
| 量子 | `j4` | DESIGN_BUDGET | **DESIGN_BUDGET** | STRICT | none | 2 | segment |
| 量子 | `j5` | DESIGN_BUDGET | **DESIGN_BUDGET** | STRICT | none | 4 | segment |
| 量子 | `qchip` | DESIGN_BUDGET | **DESIGN_BUDGET** | STRICT | none | 6 | segment |
| 量子 | `qs` | DESIGN_BUDGET | **DESIGN_BUDGET** | STRICT | none | 24 | segment |

- **锚登记**：18/18 张有 `anchors`（棘轮 14 → **0**）· 逐卡求和 **107 条**（`d1/d2/d4` 共享 B523–525，去重后更少）
- **分布**：`by_anchors_source` = `segment 15 / none 2 / runtime 1`
- **`soc` 的口径限制** 是 N3 登记的 V1，**本项未动**；后续 **N3-b 已用「拆维度」处置**（grade 保留 DESIGN_SIGNOFF 事实、claimable=AUDIT_ONLY 限制），未降对外 verdict。

---

## 4. 🔴 运行时对拍当场抓出的 3 处漂移

改成"运行时读卡"后第一次 `audit()` 就报 `anchors_drift` 3 条。**没有一条是我这次填错的，全是上一版 schema 手填无据**：

| 卡 | 漂移 | 真相 | 处置 |
|---|---|---|---|
| `pchip` | `only_in_schema: B1, B21` | schema 登了 B1（**米氏散射**）与 B21（**光子晶体腔**），但 pchip 是 **MZI 张量核**，两者无关；卡上也无任何依据 | **从 schema 删除**，只留 B2（SOI n_eff）+ B20（MZI FSR） |
| `oi` | `only_on_card: B19` | schema 登的是**空**，但卡内 `b19_passivity` **实测 True** | **补进 schema**（B19） |
| `qchip` | `only_on_card: S4` | schema 只有 LOQC 5 条，漏了 **S4 量子门保真度预算**（光学量子门必经） | **补 S4** |

另外两处**不是漂移、但重新核算后修正**（卡与 schema 一起改）：

| 卡 | 原登记 | 改为 | 依据 |
|---|---|---|---|
| `soc` | S1–S13 全 **13** 条 | **12** 条（去 S4） | S4 是**量子门**保真预算，光 SoC 不该认领 |
| `schip` | 超导器件物理 **10** 条 | **16** 条（+S4/S9/S10/S11/S12/S13） | 超导芯片的 `DESIGN_SIGNOFF` **恰恰是 S9/S10 LVS 定义**的；漏登等于"签核没签在锚上"。这是 N3-a 发现的**真实漏登** |

> 🔴 这 5 处合起来说明一件事：**没有对拍的登记表，等于自述**。上一版 schema 是一天内手填的，对拍一上就暴露 3 处。

---

## 5. 连带改动：前端 7 个 render 函数

补字段后 **6 道门禁立刻红**（d1/j1/j2/j4/j5/j3 + pm）。原因不是 bug，是它们的**反向完备判据**在起作用：

> 「`case_card()` 的每个顶层键都要被前端引用（防『后端算了前端不问』）」

这条判据是对的，不能绕过。所以改前端：

| 类型 | 卡 | 改法 |
|---|---|---|
| A（已有 `d.anchors` 遍历） | j1 / d1 / j5 | 在既有 table 内补"锚来源"/"说明"两行 |
| B（无锚渲染） | j2 / j3 / j4 / **pm** | 补完整块（标题 + 遍历 + 来源 + 说明） |
| 公共 | — | 新增 `_ancSrc(s)` 只做 source→中文，**不含 `d.` 引用** |

🔴 **为什么不抽公共渲染函数**：这些门禁在**每个函数体内**正则抽 `d.<字段>`。把渲染包进公共函数，函数体里就看不到 `d.anchors_source` ⇒ 判据照红。所以宁可有 7 处相似的 5 行代码。

前端 JS 语法用 `node --check` 验过（372,240 字符脚本块）。

### 5.1 一处判据修正（必须交代）

`run_webui_j3_render_path_smoke` 的 **C2** 原本要求"每个嵌套 dict 的每个字段都被前端引用"。`anchors` 是 dict（锚号→标题），于是要求前端出现 `d.anchors.B510 … d.anchors.B514` 五个字面。

**这条对 `anchors` 不成立**，理由：
- `anchors` 的键是**账本锚号**，由账本决定 —— 账本加一锚就变
- 要求逐条硬编码 ⇒ **账本每加一锚要改 18 个前端函数**，且新人一定会漏
- C2 的原意是"后端算了前端不问"，锚号不是"展示字段"而是"数据行"

⇒ 改法：`anchors` 从 C2 的 `blocks` 中豁免，**换一条更严的 C2b**：

> 必须出现 `var <别名> = d.anchors || {}` **且** `Object.keys(<别名>)` **且** `.forEach(`
> ⇒ 只"提一下" `d.anchors` 而不用它，C2b 照样红。

这不是放松：原判据对动态键集**不可维护**，C2b 对"是否真渲染"判得更准（实测 `别名=an 遍历=True`）。

---

## 6. 踩的坑（两个，都进红线）

### 6.1 🔴 一次性探针落在仓库根 ⇒ 被全仓契约门禁扫到

我用 4 个临时脚本批量改文件（`_n3a_patch.py` / `_n3a_patch2.py` / `_n3a_front.py` / `_n3a_front2.py`），
其中两个用 **cwd 相对路径** `open("lda/lda_webui/static/index.html")`。

`run_ci_gate_contract_smoke` 的 **C2** 是「全仓 1117 个 .py 全扫 · 门禁/脚本不用 cwd 相对路径」，
当场报：

```
[FAIL] C2 ... 违约=["_n3a_front.py['module:open(PATH)']", "_n3a_front2.py['module:open(PATH)']"]
```

⇒ 连带 `run_webui_pm_render_path_smoke` 的 **W9**（注释声明判据数 == 实跑数）也红：`18 vs 17`。

🔴 **这条纪律 MEMORY 里早就写了**（「一次性探针别落仓库根 ⇒ stdin 管道或跑完即删」），我这轮又犯了。
**处置**：删掉 4 个脚本 → 契约门禁恢复 **18 PASS / rc=0** → W9 恢复。
**新纪律**：批量改文件的脚本一律写成 `python - <<'EOF'` 的 stdin 形式，或落到 `/tmp` 且用绝对路径。

### 6.2 heredoc 把 `\n` 变成 `/n`（历史坑复现痕迹）

上一轮已记：用 bash heredoc 传含 `\n` 的 Python 字符串会被吞。
本轮改用 **Write 工具写脚本文件**（再执行）绕开，但脚本落在仓库根又触发了 §6.1 —— 两个坑是一对。

---

## 7. 验证清单（全部实跑）

| 门禁 | 结果 |
|---|---|
| `run_webui_json_hard_smoke` | **23 PASS / 0 FAIL**（20 → 23：新增 S5b / S5c / S6b） |
| `run_webui_j3_render_path_smoke` | **28 PASS / 0 FAIL**（C1 21 键全引用 · C2 8 块 · C2b 遍历 · **E1 仍 44**） |
| `run_webui_d1_render_path_smoke` | rc=0 |
| `run_webui_j1_render_path_smoke` | rc=0 |
| `run_webui_j2_render_path_smoke` | rc=0 |
| `run_webui_j4_render_path_smoke` | rc=0 |
| `run_webui_j5_render_path_smoke` | rc=0 |
| `run_webui_pm_render_path_smoke` | **29 PASS / 0 FAIL**（W4a 28 键全引用 · W9 漂移=无 · W10 闭环） |
| `run_webui_oi_render_path_smoke` / `ecore` / `entry` / `api` | rc=0 |
| `run_pchip_case_smoke` / `schip_case` / `qchip_case` / `soc_ui` | rc=0 |
| `run_ci_gate_contract_smoke` | **18 PASS / rc=0** |
| `run_accel_case_smoke` / `d4_case` / `ecore_case` | rc=0 |
| `run_j1_qec` / `j2_qpu` / `j4_multiparam` / `j5_qnet` | 全 0 FAIL |
| `run_sensor_panel_smoke` / `qs_panel_smoke` | rc=0 |
| `run_helper_dup_ratchet_smoke` | rc=0（18 个文件加同构常量**未触发**重复判据） |
| `run_p2_usability_smoke` / `run_count_consistency_smoke` | rc=0 |
| JS 语法（`node --check` 提取 372,240 字符脚本块） | OK |

### 7.1 pm 门禁复跑（3 次，共 ~9 分钟）

| 次 | 结果 | 原因 |
|---|---|---|
| 1 | W4a 红（`anchors/anchors_note/anchors_source` 未引用） | renderPm 缺锚块（预期内） |
| 2 | W4a 绿 · **W9 红**（`run_ci_gate_contract_smoke` 18 vs 17）+ W9-P1 连带 | §6.1 探针脚本落仓库根 |
| 3 | **rc=0 / 29 PASS** · W4a 28 键全引用 · W9 漂移=无 · W10 闭环 | 删探针后 |

⇒ 这条链说明：**我自己的临时脚本会污染全仓契约门禁**，而契约门禁又会连带 WebUI 门禁。
下次批量改动一律走 stdin 或 `/tmp` 绝对路径。

---

## 8. 诚实边界（本项不改变这些）

- **`anchors_source = segment` 的 15 张卡，其锚仍是"号段归属"，不是"已验证"**。
  补字段只是让这件事**显式可审计**，不提升任何物理可信度。
- **`runtime` 只有 1 张（`oi`）** —— 整个项目里"卡内真的跑账本锚"的只有 B19 一处。
  这不是 N3-a 的成果，是**既有事实的暴露**。
- **`soc` 的处置已由 N3-b 完成（拆维度）**：`grade` 仍 `DESIGN_SIGNOFF`、`claimable_grade=AUDIT_ONLY`、`allow_external=False`。本项未动它。
- **`ecore` 仍是 0 锚**，`DESIGN_VERIFIED` 与"有可复核锚"是两维（N1 已判死）。
- **账本 541 / CI core 350 / 判决逐位不变**：本项**未新增任何锚**，只做了登记与对拍。
- **兼容性**：`SigningRecord` 删掉了 `anchors_on_card` 字段（改为 `audit()` 运行时计算）。
  若有外部代码读该字段，需改读 `audit()["anchors_on_card"]`（列表）。仓内已确认无引用。

---

## 9. 复现命令

```bash
cd D:/agent_LDA && export PYTHONPATH=D:/agent_LDA/lda
# 签核审计（含运行时读卡 + 漂移对拍）
python -c "from lda_harness import signing_schema as SS; import json; print(json.dumps(SS.audit(), ensure_ascii=False, indent=2))"
# 门禁
cd lda && python run_webui_json_hard_smoke.py   # 23 PASS
python run_webui_j3_render_path_smoke.py        # 28 PASS
python run_ci_gate_contract_smoke.py            # 18 PASS
```
