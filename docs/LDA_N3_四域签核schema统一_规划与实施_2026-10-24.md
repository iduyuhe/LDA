# N3 · 四域签核 schema 统一（规划 + 实施）

> **基线**：v0.9.282 · HEAD `bc26337` · 账本 **541 不变** · CI core **350 不变**（判据并入现有门禁，零新增成员）
> **日期**：2026-10-24
> **来源**：四域审计 v3 §10 N3「统一四域签核报告 schema」
> **性质**：判据工程 + 口径治理。**不改任何卡的对外 verdict、不改任何锚、不进判决路径**

---

## 0. 一句话

四个域原来各写各的签核：案例卡 `verdict` 有 **6 种值**、诚实边界有 **6 种不同变量名**、deck 可信等级**只有量子侧有**。
外部读者无法回答一句话：「**这一张卡，到底是什么级别的签核？**」

本版把它拆成**三个正交维度**（grade × evidence × deck），18 张卡用同一套话说清楚，并上 6 条可证伪判据。
**过程中抓出两处真实缺口**：`soc` 越级、14 张卡"签核却没登记锚"。

---

## 1. 🔴 为什么必须拆维度（含我自己先犯的错）

勘察时我一开始把 `verdict` 当成**一维强度序**，据此预判：

> "`ecore` 是 `DESIGN_VERIFIED`，但电子域 0 锚 ⇒ 它越级了，应降到 `DESIGN_BUDGET`。"

**这个判断是错的。** 查了 `run_ecore_case_smoke` 才发现它**硬锁** `verdict == "DESIGN_VERIFIED"`
（B2 判据 + 反向探针），而且 `ecore_case` 的 docstring 明写：`verdict` 恒为 `DESIGN_VERIFIED`，
语义是「**设计期验证**（晶体管级模型 + 电路仿真 + 阵列 + 版图签核 + 寄生后仿 + 失配/噪声 + 规模压力）」。

⇒ `DESIGN_VERIFIED` 说的是**工程链走到了哪**，`DESIGN_SIGNOFF` 说的是**版图+DRC/LVS 链闭合没闭合**，
而「有没有可复核的锚」是**第三件事**。三件事压进一个字符串，就会得出
"ecore（0 锚）比 13 张预算卡更可信"这种**错误结论**。

🔴 **这次自纠本身就是 N3 的立项理由**：不是字段名不统一，是**概念被压扁了**。

---

## 2. 三个正交维度

### 2.1 `grade` — 工程链深度（有序）

| 值 | 含义 |
|---|---|
| `NONE` | 无任何工程链 |
| `AUDIT_ONLY` | 只可审计（公开近似 deck 的天花板） |
| `DESIGN_BUDGET` | 设计预算／建模值（闭式 + 示例参数） |
| `DESIGN_VERIFIED` | 设计期验证（含电路/版图/后仿/DRC 链） |
| `DESIGN_SIGNOFF` | 设计期签核（版图 + DRC/LVS 链闭合） |
| `FOUNDRY_SIGNOFF` | 工艺厂签核（唯一可对外，须 NDA attestation） |

### 2.2 `evidence` — 证据强度（有序，与"有没有可复核的锚"挂钩）

| 值 | 含义 |
|---|---|
| `NONE` | 该域/该卡 **0 条**专属锚 |
| `BUDGET` | 有锚但只有自证桩／建模量 |
| `EMPIRICAL` | 有**公开实测语料**锚（E 号段） |
| `STRICT` | 有 **strict 独立候选**锚 |

### 2.3 `deck` — deck 可信等级（与 `lda_qeda/quantum_deck.py` 同义，不另立一套）

`none` / `self_built` / `foundry_public` / `foundry_nda`

### 2.4 第四维（不加枚举，只加开关）

`capacity_basis`：`none` / `layout_capacity` / `fabricated_devices`
—— 报规模就必须说清是"版图容量"还是"已制备器件数"。

---

## 3. 三条硬规则（每条都有反向探针）

| # | 规则 | 依据 |
|---|---|---|
| **R1** | `effective_grade = min(declared, ceiling(deck))`<br>`ceiling`：none→`DESIGN_VERIFIED` · self_built→`DESIGN_SIGNOFF` · **foundry_public→`AUDIT_ONLY`** · foundry_nda→`FOUNDRY_SIGNOFF` | 后三档**直接复用量子侧已固化语义**（`quantum_deck.py` 的可信等级天花板），不新造 |
| **R2** | `grade == FOUNDRY_SIGNOFF` ⇒ deck 必须 `foundry_nda` **且** attestation 非空 | 防自封：手写 `provenance="foundry_nda"` 不能凭空变出对外签核 |
| **R3** | `capacity_basis == fabricated_devices` ⇒ evidence ≥ `EMPIRICAL` | 没有实测锚就说"已制备器件数" = 把版图容量当实测规模卖 |

---

## 4. 18 张卡的签核总表（现算 · 单一真源 `lda_harness/signing_schema.py`）

| 域 | 卡 | declared | **effective** | evidence | deck | 锚(征程) | 卡上登记 |
|---|---|---|---|---|---|---|---|
| 光子 | `accel` | DESIGN_BUDGET | **DESIGN_BUDGET** | BUDGET | none | 0 | — |
| 光子 | `oi` | DESIGN_BUDGET | **DESIGN_BUDGET** | BUDGET | none | 0 | — |
| 光子 | `pchip` | DESIGN_SIGNOFF | **DESIGN_SIGNOFF** | BUDGET | self_built | 4 | — |
| 光子 | `pm` | DESIGN_SIGNOFF | **DESIGN_SIGNOFF** | BUDGET | self_built | 2 | — |
| 光子 | `sensor` | DESIGN_BUDGET | **DESIGN_BUDGET** | EMPIRICAL | none | 14 | — |
| 光子 | `soc` | DESIGN_SIGNOFF | **DESIGN_SIGNOFF** / claimable **AUDIT_ONLY** 🔴 | BUDGET | foundry_public | 12 | — |
| 电子 | `ecore` | DESIGN_VERIFIED | **DESIGN_VERIFIED** | **NONE** | none | 0 | — |
| 超导 | `schip` | DESIGN_SIGNOFF | **DESIGN_SIGNOFF** | STRICT | self_built | 10 | — |
| 量子 | `d1` | DESIGN_BUDGET | **DESIGN_BUDGET** | STRICT | none | 2 | ✅ |
| 量子 | `d2` | DESIGN_BUDGET | **DESIGN_BUDGET** | STRICT | none | 1 | ✅ |
| 量子 | `d4` | DESIGN_BUDGET | **DESIGN_BUDGET** | BUDGET | none | 3 | — |
| 量子 | `j1` | DESIGN_BUDGET | **DESIGN_BUDGET** | STRICT | none | 9 | ✅ |
| 量子 | `j2` | DESIGN_BUDGET | **DESIGN_BUDGET** | STRICT | none | 4 | — |
| 量子 | `j3` | DESIGN_BUDGET | **DESIGN_BUDGET** | STRICT | none | 5 | — |
| 量子 | `j4` | DESIGN_BUDGET | **DESIGN_BUDGET** | STRICT | none | 2 | — |
| 量子 | `j5` | DESIGN_BUDGET | **DESIGN_BUDGET** | STRICT | none | 4 | ✅ |
| 量子 | `qchip` | DESIGN_BUDGET | **DESIGN_BUDGET** | STRICT | none | 5 | — |
| 量子 | `qs` | DESIGN_BUDGET | **DESIGN_BUDGET** | STRICT | none | 24 | — |

> 🔴 **本表口径已按 N3-b 重定义**（原列的"effective"是 `min(declared, ceiling)`，
> 把「对外用途限制」写成「工程深度变浅」，已废除）。现行口径见 §5.1：
> `grade` = 工程链事实（不被压）· `claimable_grade` = 对外可宣称口径（独立维度）。

**分布（N3-b 后现算）**

- `by_grade`（工程链深度）：`DESIGN_BUDGET` 13 · **`DESIGN_SIGNOFF` 4** · `DESIGN_VERIFIED` 1
- `by_claimable_grade`（对外口径）：`DESIGN_BUDGET` 13 · `DESIGN_SIGNOFF` 3 · `DESIGN_VERIFIED` 1 · **`AUDIT_ONLY` 1**
- `by_evidence`：`STRICT` 10 · `BUDGET` 6 · `EMPIRICAL` 1 · **`NONE` 1（ecore）**
- `claim_downgraded`：**`['soc']`**（口径被压制，**属正常限制非违规**）· `allow_external`：**`[]`**（零对外）
- `anchor_unregistered`：**0 / 18**（N3-a 后）

<details><summary>N3 当时（改前）的分布，留档对比</summary>

- `by_effective_grade`：`DESIGN_BUDGET` 13 · `DESIGN_SIGNOFF` 3 · `DESIGN_VERIFIED` 1 · **`AUDIT_ONLY` 1**
- `ceiling_capped`：**`['soc']`**
- `anchor_unregistered`：**14 / 18**

</details>

🔴 **这张表第一次让四域可比**：
- 超导 `schip` 是唯一 **DESIGN_SIGNOFF + STRICT** 的组合（签核且证据最强）；
- 光子 3 张 SIGNOFF 卡的 evidence 都只有 `BUDGET`（它们签核靠的是工程链，不是锚）；
- 电子 `ecore` 是唯一 **evidence = NONE**（工程链到 VERIFIED，但 0 锚）—— 这两个维度一拆开，剪刀差立刻可见。

---

## 5. 两处真实缺口（**显式登记 · 不掩盖 · 棘轮只降**）

### V1 · `soc` 越级 —— ✅ **已由 N3-b 处置（拆维度 · 见 §5.1）**

`soc_case.FOUNDRY_SIGNOFF` 的 note 原文：

> 「闭集规则数值 = **公开近似** + 逐条规格锚，**非 foundry NDA 真值**；signoff_ready 仅代表
> 主权自洽可制造性就绪，**非真实 tape-out 授权**」

⇒ 它的 deck 实为 `foundry_public` ⇒ 天花板 `AUDIT_ONLY` ⇒ **effective = AUDIT_ONLY < declared = DESIGN_SIGNOFF**。

🔴 **本版不改它的对外 `verdict`**（那是口径变更，需人决策），只把不一致**显式登记**在 `audit()` 里，
并让门禁 S2 要求 `violations == 1 ∧ capped == ['soc']` —— 多一条就红，少一条也红。

#### 5.1 N3-b 处置结果：**拆维度，不是降 verdict**

勘察 N3-b 时发现 **N3 自身有个设计缺陷**，反过来改写了 V1 的性质：

| 事实 | 说明 |
|---|---|
| 补 NDA deck **不可行** | `foundry_pdk.py` 明写「本项目无任何 foundry NDA 真值，须商务签约注入」⇒ 本机不持有、伪造即违红线 |
| `deck = foundry_public` **判定正确** | 它用的是 **AIM Photonics 官方公开页面 PDK**（`aimphotonics.com/services`）⇒ 正是 `foundry_public` 的定义 |
| 🔴 **但 `GRADES` 排序有问题** | 改前的序列是 `NONE(0) < AUDIT_ONLY(1) < DESIGN_BUDGET(2) < …` ⇒ **`AUDIT_ONLY` 比 `DESIGN_BUDGET` 还低** |

⇒ 若按原计划"降 verdict 到 AUDIT_ONLY"，等于宣称 **soc 的工程深度比 13 张设计预算卡还浅** ——
可 soc 明明走完了版图 + DRC/LVS + 多核 tiling + 18 里程碑。**那是把「限制」误读成「深度」。**

**根因**：`AUDIT_ONLY` 是「对外用途限制」，不是「工程链深度」，我把两个维度压进了同一个序数序列。
这正是 N3 立项理由「概念被压扁」的**第二次复发**（第一次是 `verdict` 一个字段管三件事）。

**改法（N3-b）**：

| 维度 | 改前 | 改后 |
|---|---|---|
| 工程链深度 | `effective_grade = min(declared, ceiling(deck))` —— 被 deck 压制 | `grade` = declared，**是事实，不被任何 deck 压** |
| 对外可宣称 | 无（被压进上面那个数） | `claimable_grade` = min_claim(declared, deck)，**独立维度** |
| 是否可以进对外材料 | 无 | `allow_external`（复用量子侧 `quantum_deck.py` 语义） |
| `AUDIT_ONLY` 归属 | 在 `GRADES` 序列里（rank 1） | 只在 `CLAIMABLE` 序列里 |

**soc 的最终登记**：

| 字段 | 值 | 含义 |
|---|---|---|
| `grade` | **DESIGN_SIGNOFF** | 工程链事实：版图 + DRC/LVS 链闭合 |
| `claimable_grade` | **AUDIT_ONLY** | 对外只能称"可审计"（deck 是公开近似） |
| `allow_external` | `False` | 不得进对外材料 |
| `claim_downgraded` | `True` | 登记为**正常限制**，不是违规 |

**棘轮变化**：`CEILING_VIOLATIONS` **1 → 0**（不再是"违规"）· 新增 `CLAIM_DOWNGRADED_CASES = 1`（只降不升）

**新事实（顺带暴露）**：`allow_external_cases == []` —— **18 张卡没有一张可进对外材料**（全项目零对外签核）。
这条已写成门禁判据 **S2c**：若哪天有人真拿到 NDA deck，这里会从 `[]` 变非空，必须人决策，不得静默。

**新增门禁判据**（20 → 25，全在 `run_webui_json_hard_smoke`）：

- **S2b** 拆维度未偷偷降级：soc 的 `grade` 必须仍是 `DESIGN_SIGNOFF` ∧ `claimable` 是 `AUDIT_ONLY`
  （防"拆维度"被用来悄悄把 verdict 降了）
- **S2c** 无任何卡 `allow_external`
- **R4 / 探针**：`claimable_grade` 必须等于按 (declared, deck) **现算**的值 ⇒ **只换 deck 不重算必红**
- **探针新增**：`grade` 落回 `AUDIT_ONLY`（旧的压扁行为）必红 —— 因为它已不在 `GRADES` 里

### V2 · 14 张卡"签核却没登记锚"（`ANCHOR_UNREGISTERED_CASES = 14`）

18 张卡里**只有 4 张**（`d1` / `d2` / `j1` / `j5`）在卡上写了 `anchors` 字段。
**4 张 `DESIGN_SIGNOFF` 卡（pchip / pm / soc / schip）全都没写** —— 外部无法复核"它签的是哪些锚"。

🔴 我特意把两个概念分开，否则这条缺口会被我自己填的注册表掩盖：
- `anchors` = 该卡所属征程**确实存在**的账本锚（有据：账本号段 + 四域审计 §4.2）
- `anchors_on_card` = 这些锚**是否真的写在案例卡上**

---

## 6.2 N3-c · `/api/signing` 端点（已完成）

**目标**：把 `audit()` 的结论变成**外部一条 URL 自查**，不用装环境、不用读代码。

**实现**（`lda/lda_webui/routes.py`）：

| 项 | 做法 | 理由 |
|---|---|---|
| handler | `h_signing`，注册进 `GET_ROUTES` | 与 `/api/verification_ledger` 同属「公开只读验货」类 |
| payload | `_signing_payload()`：**只转发 + 整形**，真源仍是 `signing_schema` | 端点不重算任何判据（防第二份实现漂移） |
| 并发 | 串行锁 + **TTL 300s 缓存**（照抄 `benchmark_crosscheck` 模式） | 🔴 `audit()` 要**运行时读 18 张卡**，首次 **5.7s**（qchip 216 模现算最重）；公开 GET 不许单请求占线程 10s 级 |
| 缓存上限 | 无需上限 —— 端点**无参数** ⇒ 缓存键固定 | 只有"参数任意"的端点才会按请求泄漏内存 |
| 失败 | 异常一律 `500 + {error}`，**不静默回退假数据** | 「宁红不可假绿」 |
| 鉴权 | `auth=public`（由 `HEAVY` 集合决定，未进该集合） | 公开验货，无需登录 |

**响应体**（8.2 KB）：

- `summary`：`by_grade` / `by_claimable_grade` / `by_evidence` / `by_anchors_source` / `violations` / `claim_downgraded` / `allow_external_cases` / `anchors_drift`
- `cases`：18 张逐卡 —— `grade` · `claimable_grade` · `allow_external` · `evidence` · `deck` · `anchors` · `anchors_source` · **`anchors_note`（依据原文）**
- `honest_note`：六条边界，含「grade ≠ 流片实测」「`segment` ≠ 已验证」「`allow_external_cases` 为空 ⇒ 全部不得进对外材料」

**连带（都做了，不是可选项）**：

| 连带 | 结果 |
|---|---|
| `docs/api_reference.json` 真源 | 重跑 `scripts/gen_api_reference.py` ⇒ 端点 **158 → 159**、精确 141→142、`needs_login` **60 不变**、描述 **159/159 = 100%** |
| `docs/API_REFERENCE.md` | 自动同步生成 |
| `run_p2_usability_smoke` ⑤ | 「重跑生成器零漂移」→ **rc=0**（不重跑生成器必红） |
| `run_p2_usability_smoke` ⑥ | 覆盖率 **100.0%（159/159）** · counts 块 ≡ 逐条重算 |
| `run_webui_api_smoke` | **`[PASS] GET /api/signing 200 JSON`** —— 真起 HTTP + urllib 请求验过 |
| 三分类 / 计数 / 入口 | 全 rc=0 |

⚠️ **首次请求 ~5.7s**，之后命中缓存秒回。这是诚实的代价：那 5.7s 是"运行时读 18 张真实案例卡"换来的，
不是可以预先写死的数字 —— 写死就会与卡漂移。

## 6.3 N3-d · 诚实边界统一读取（已完成 · **改法与原计划不同**）

### 勘察：不是"六种名字"，是三种形态

| 形态 | 张数 | 例子 |
|---|---|---|
| 已叫 `HONEST_NOTE` | **4** | `d1` / `d2` / `sensor` / `d4` |
| 带前缀 `XXX_HONEST_NOTE` | **12** | `ECORE_` / `J1..J5_` / `PCHIP_` / `PM_` / `QCHIP_` / `QS_` / `SCHIP_` / `SOC_` |
| **根本没有模块级常量**（内联字符串） | **2** | `oi` / `accel` |

### 🔴 为什么**没有**按原计划改名

原计划是"统一成 `HONEST_NOTE`，旧名保留别名"。勘察后否掉，两条硬理由：

1. **7 个门禁用「改模块级变量 ⇒ `case_card()` 必红」做突变探针**：
   ```python
   saved = EC.ECORE_HONEST_NOTE
   EC.ECORE_HONEST_NOTE = saved.replace("非流片后实测", "")   # 抹掉关键词
   # ⇒ case_card() 的 honest_note 必须变、判据必须红
   EC.ECORE_HONEST_NOTE = saved
   ```
   改名会连带改这些探针；而改名后 `case_card()` 读新名、门禁写旧名（或反之）= 探针静默失效。

2. **加别名是"快照"，会给过期值**：
   `HONEST_NOTE = ECORE_HONEST_NOTE` 是**对象引用拷贝**，之后若有人改 `ECORE_HONEST_NOTE`
   （突变探针就这么干），`HONEST_NOTE` 仍指向旧对象 ⇒ **统一入口反而比不统一更危险**。
   而反过来让 `HONEST_NOTE` 当真源、旧名作别名，则门禁的探针写旧名时失效 ⇒ 直接红。

⇒ **真正的病灶不是变量名不同，是"没有统一读取入口"。** 而对外契约本来就已经统一了：
18 张卡的 `case_card()["honest_note"]` 字段一直存在、类型一致。

### 改法：收敛在契约层 + 表驱动机核

| 产物 | 作用 |
|---|---|
| `signing_schema.honest_note_of(case)` | **统一读取入口**：`read_card(case)["honest_note"]`，**每次现读卡** ⇒ 突变可传播、永不过期 |
| `signing_schema.NOTE_ATTR` | 18 条**模块级常量名登记表**（`None` = 内联无常量），供维护者发现差异 |
| `CARD_MODULE` 公开别名 | 门禁取「case → 模块名」不必碰私有名 |
| `/api/signing` 的 `cases[*].honest_note` | 外部一条 URL 就能读到每张卡的诚实边界（响应体 **8.2 KB → 17.3 KB**） |

### 新增门禁判据（25 → 28）

- **S7** 18 张卡 `honest_note` 全非空（统一从卡上取，不看变量名）
- **S7b** `NOTE_ATTR` 覆盖 == 18 张卡全集 ∧ 登记的常量名**真的 `hasattr` 存在**
  （防"表写了个早就改掉的旧名"或"新增卡漏登记"）
- **S7c** 反向探针：表里**少一条**必红 ∧ 常量名**写错**必红（两侧都验）

> 🔴 S7b 是这条改动里唯一有长期价值的部分：它把"18 个模块用 3 种形态"这件**不可见的事**
> 变成了**可机核的登记**。以后谁新建案例卡不登记 `NOTE_ATTR`，S7b 当场红。

### 诚实边界

- **变量名本身没有统一**（4 + 12 + 2 三种形态仍在）。这是**刻意的**——改名的代价（7 个探针）
  大于收益（纯可发现性），且别名方案会引入"过期值"这个新缺陷。
- `NOTE_ATTR` 是**登记不是读取路径**：删掉它，`honest_note_of()` 依然工作（它读卡）。
  它的价值只在"机核 + 可发现性"。
- `/api/signing` 响应体增大到 17.3 KB 是**必然的**——诚实边界本来就是长文本，
  压缩它等于弱化对外披露。

## 6. 实施与验证

| 项 | 内容 |
|---|---|
| 新模块 | `lda_harness/signing_schema.py`（纯 stdlib · 确定性 · 零时间戳） |
| 门禁落点 | **并入 `run_webui_json_hard_smoke`**（它已遍历案例卡）⇒ **CI core 350 不变**、无需 3 小时重跑 |
| 新判据（N3） | S1 覆盖完整性 · S1b declared ≡ 卡上 verdict（逐卡防漂移）· S2 天花板违规==棘轮 · S3 强证据必须有锚 · S4 无卡声称 fabricated · S5 未登记锚棘轮 · S6 反向探针 |
| 新判据（N3-a/N3-b） | **S5b** 登记 anchors ≡ 卡上（运行时对拍）· **S5c** anchors_source 三档自洽 · **S2b** 拆维度未偷偷降级 · **S2c** 零对外 · **S6b** 对拍器反向探针 |
| 判据总数 | **25**（N3 时 20 → N3-a 23 → N3-b 25），全部 PASS |
| 实测 | `run_webui_json_hard_smoke` **20 PASS / 0 FAIL**（14→20） |

**S6 反向探针五项全部按预期**：

| 变异 | 结果 |
|---|---|
| `ecore` 抬到 `FOUNDRY_SIGNOFF` 且无 attestation | **红 3 条**（自封 ×2 + ceiling） |
| `ecore` 声称 `fabricated_devices` | **红 1 条**（容量无据） |
| `j1` 声称 `STRICT` 但清空 anchors | **红 1 条** |
| `soc` 改 `deck=foundry_nda` + attestation | **绿 0 条**（合规化后确实变绿 —— 两侧都验） |
| `schip` 改 `deck=foundry_public` | **红 1 条**（公开层不得称签核） |

**连带门禁全绿**：`count_consistency` / `p2_usability` / `helper_dup_ratchet` / `k4_coverage` 均 rc=0。
`run_ci_regression.py` 的 CORE_SMOKES 注释已同步（原写"7 张卡"，实为 8 张 + N3 六判据）。

---

## 7. 下一步（可排期）

| # | 动作 | 收益 | 风险 |
|---|---|---|---|
| **N3-a** | 逐卡补 `anchors` 字段（14 → 0），棘轮同步下降 | 外部可复核"签核签的是哪些锚" | 低（只加字段，不动判决） |
| ~~**N3-b**~~ | ~~`soc` 处置~~ | ✅ **已完成（拆维度 · §5.1）** | — |
| ~~**N3-c**~~ | ~~挂 `/api/signing`~~ | ✅ **已完成（§6.2）** | — |
| ~~**N3-d**~~ | ~~`HONEST_NOTE` 变量名收敛~~ | ✅ **已完成（改法与原计划不同 · §6.3）** | — |

🔴 **不做**：不强改 18 张卡的 `verdict` 去"对齐"某个理想分布 —— 那是**改数字迎合口径**，
不是 N3 的目标；N3 只提供"同一套话 + 可机器核的规则"。

---

## 8. 诚实边界

- **`anchors` 的填充有解释成分**：如 `pchip` 填 `B1/B2/B20/B21`（光子早期锚）、`pm` 填 `B28/B29`。
  依据是号段与征程对应，**不是卡自己的声明**（卡上根本没写）⇒ 这正是 V2 要补的东西。
- **R1 的 ceiling 规则是从量子侧搬来的**，只在量子域被实战检验过（`quantum_deck` 的三档）；
  移用到光子/电子是**类比**，不是独立验证。
- **`EVIDENCE`/`DECK` 的取值目前靠人工判定**（除 4 张卡有 anchors 字段可交叉核）⇒ 不是全自动。
- **本版不提升任何卡的可信度**：它把原来隐式的、各写各的口径**显式化**，并让两处不一致**可见**。
  「表变清楚了」≠「东西变好了」。
- **`soc` 的越级是"口径级"而非"造假"**：它的 `FOUNDRY_SIGNOFF` note 自己就把"公开近似、非 NDA 真值"
  写清楚了，只是那个限定**没有进结构化字段**，所以机器读不到。N3 的价值正是把它变成机器可读。
