# LDA 创新超市 · 分类体系与筛选器设计（一期）

> 日期：2026-09-06 · 版本：**v0.9.42 已实施** · 状态：**已交付**
> 范围：一期 = 确定性筛选（分类下沉 + 筛选器 UI + API + CI 护栏）
> 二期（本文档只预留接口，不实施）：锚定导购（LLM 只解析需求 + 解释结果，**禁止输出任何规格数字**）
>
> **实施偏差（2 处，均已核实）**：① §1.1 对 `DIR_SHELVES` 用途的判断已更正（见该节注）；
> ② §2.3 D 赛道的「光交换与路由」改名为「OCS 光交换」（key 全局唯一性要求，见该节注）。

---

## 一、为什么不是"在现有目录上加个筛选器"

### 1.1 现状：一个写死在前端的 ID 列表，覆盖不到 58/75

`store.html` 曾硬编码一套 `DIR_SHELVES`（6 个需求方向 → 货架 id），**只覆盖 58/75 条**。
剩余 **17 条（22.7%）** 是孤儿，且**全部是最近三轮新增的货**：

```
IM-CPO-OIO-8CH / -16CH / -CHIPLET / -ELS-FIBER   ← 本轮 D 赛道 4 条
IM-QKD-FULL-LINK   IM-QCTRL-32Q   IM-OPA-2D   IM-OPTCOMB-WDM
IM-3.2T-DR8   IM-1.6T-LPO   IM-1.6T-ZR   IM-CPO-16CH   IM-UCIE-OPTICAL
IM-LIDAR-FULL   IM-POC-BIOSENSE   IM-FTTR-PLC32   IM-TTD-5G
```

> **⚠️ 更正（实施时读码发现，原判断有误）**
> 初版文档称这 17 条「用户在目录视图里看不到」——**不准确**。
> 实测：`DIR_SHELVES` 并非浏览目录，而是**定制下单弹窗的需求方向映射**
> （用于「该方向已有开放货架」导流 + 咨询时预选方向）。**浏览网格 `loadShelves()`
> 渲染的是 `/api/shelf` 全量 75 条，一条不少。**
>
> 真实影响是：这 17 条点「咨询此货架」时**方向推断为空**（`direction` 字段传空，
> 后端无法归类线索），且拿不到「该方向有现成货架，先看现成的」导流推荐。
> 病根不变——**写死在前端的 ID 列表随数据层扩张而静默漂移**，与定价归档缺口（58/75）
> 是同一个数字、同一类病。处置也不变：下沉到后端 + CI 断言。

**这与上一轮修掉的定价归档缺口（58/75）是同一个数字、同一个病根**：
扩货架只改数据层，不改消费方。

### 1.2 现有字段筛不动（实测数据）

| 维度 | 分布 | 能否做筛选 |
|---|---|---|
| `system_type` | `link` **53/75（70.7%）**，其余 5 类共 22 | ❌ 选了等于没选 |
| `domain` | photon 69 / hybrid 6 | ❌ 同样失衡 |
| `specs` 键 | **80 种键，71 种出现 <5 次**（最高「市场」23 次） | ❌ 无法做规格下拉，只能全文检索 |
| `applications` | **无任何值出现 ≥3 次** | ❌ 全是自由文本 |
| 价档 | 599(15) / 1999(22) / 4999(38) + 咨询制 | ✅ 唯一现成可用 |
| `features`/`specs`/`peers`/`applications` | **75/75 全覆盖** | ✅ 有数据底子 |

**结论：必须先补结构化标签，筛选器才有骨架。**

### 1.3 做法：分类从前端下沉到数据层

| | 现状（写死在前端 JS） | 改后（数据层 + 动态渲染） |
|---|---|---|
| 分类存哪 | `store.html` 硬编码 ID 列表 | `ShelfItem.track` + `ShelfItem.app_domain` |
| 新增货架 | 改数据层 ⇒ **前端静默漏**（已漏 17 条） | **不带标签 ⇒ CI 直接红**，不可能漏 |
| 筛选项 | 写死 6 目录 | 由 `/api/shelf` 的 facets 动态渲染（自动带计数） |

**这是机制级解法**：新增货架若漏标 `track`/`app_domain`，CI 断言立刻红，
与上一轮「定价归档」「回归集登记」是同一类缺口，用同一类解法（数据层唯一真源 + 门禁）。

---

## 二、分类体系（5 赛道 + 24 应用域）

### 2.1 为什么是 5 类而不是复用 A/B/C/D

`production_plan.py` 的 `TRACK_SYSTEM` 只有 A（数通）/ B（传感）/ C（量子）/ D（CPO 光 I/O）四类，
但实测有一批货架**不属于任何应用赛道**——它们是器件级/接口级产品
（调制器、偏振旋转器、光栅耦合、功分树、滤波器、光频梳、激光源）。
找「微环调制器」的用户不是按应用赛道找的，而是按**器件**找的。

故在 A/B/C/D 之外增加 **E 器件与接口**。前四类沿用内部赛道口径，保持一致。

### 2.2 赛道定义与分布（75 条全覆盖，无重叠）

| 赛道 | key | 中文 | 条数 | 判据 |
|---|---|---|---|---|
| A | `datacom` | 数通与电信 | **25** | 面向数据中心/电信/接入网的**系统级**收发与组网，指标为速率+距离 |
| B | `sensing` | 传感与测量 | **15** | 面向探测/测量的**系统级**前端 |
| C | `quantum` | 量子 | **10** | 量子计算读出、量子保密通信 |
| D | `cpo` | CPO 光 I/O | **12** | 共封装 / chiplet 光互连 / 光子中介层 / 光计算 fabric |
| E | `component` | 器件与接口 | **13** | 器件级/接口级，作为其他系统的构成部件被复用 |

对比改造前 `system_type` 的 `link` 独占 53/75（70.7%），现最宽赛道 25/75（33.3%），**可筛**。

### 2.3 应用域（二级，赛道内细分）

| 赛道 | 应用域 | 条数 |
|---|---|---|
| A 数通 | 收发引擎 · WDM 与 ROADM · 接入网 PON · 相干与长距 · 光交换与路由 | 11 / 5 / 5 / 3 / 1 |
| B 传感 | 生化传感 · 激光雷达 · 微波光子与雷达 · 惯性与物理量 · 医疗与成像 · 光谱与成像 | 5 / 5 / 2 / 1 / 1 / 1 |
| C 量子 | 量子计算读出 · 量子保密通信 | 6 / 4 |
| D CPO | CPO 光引擎 · chiplet 与中介层 · OCS 光交换 · 光计算与新型互连 | 5 / 5 / 1 / 1 |
| E 器件 | 光源与频梳 · 调制与开关 · 无源与耦合 · 偏振与旋转 · 光纤接口与扇出 · 滤波与波分 · 复用与多维度 | 3 / 2 / 2 / 2 / 2 / 1 / 1 |

> **实施补记**：原表 A 与 D 都叫「光交换与路由」，实施时把 D 的改名为 **OCS 光交换**
> （key `optical_switch` vs A 的 `switching`）——**应用域 key 必须跨赛道全局唯一**，
> 否则 `/api/shelf` 的 `facets.app_domain` 会把两个赛道的计数合并成同一个数字，
> 用户看到「光交换与路由 2 条」点进去却是两条不同赛道的东西。
> 此约束已固化为 `run_shelf_taxonomy_smoke.py` 判据 ③。

### 2.4 归类规则（可复现，防拍脑袋）

按**优先级**判定，先命中先归：

1. `system_type` 强信号：`quantum_fidelity` / `qkd_link` → **C**；`cpo_optical_io` → **D**；`sensor_frontend` → **B**
2. 器件级信号（标题/target_app 含 调制器/MZM/PSR/偏振/旋转/耦合/功分/滤波/衰减/复用器/频梳/激光源）→ **E**
3. CPO 信号（含 CPO / 共封装 / chiplet / 中介层 / interposer / UCIe / ONoC / 光计算）→ **D**
4. 传感信号（含 传感 / 激光雷达 / LiDAR / 陀螺 / OCT / 光谱 / 气体 / 生物 / 化学 / 波束成形 / TTD）→ **B**
5. 其余（含速率+距离的收发、WDM、PON、相干、ROADM、光交换）→ **A**

> 模糊项在 §4 逐条表中显式列出并给出归类理由，便于人工复核与否决。

---

## 三、数据与接口改动

### 3.1 `ShelfItem` 新增字段

```python
track: str = ""        # 赛道 key：datacom / sensing / quantum / cpo / component
app_domain: str = ""   # 应用域 key：transceiver / wdm_roadm / pon / coherent / switching / ...
```

- 同步进 `to_public()`（前端要读）
- 同步进 `innovation_market.json`（派生表！）
- 新增 `SHELF_TAXONOMY` 枚举（赛道/应用域 key → 中文标签），供 UI 与 API 共用，**禁止前端再写死中文**

### 3.2 `/api/shelf` 增加 facets

返回 `{items: [...], facets: {track: {datacom: 25, ...}, app_domain: {...}, tier: {...}}}`，
前端筛选项与计数**全部由 facets 渲染** ⇒ 新增赛道/应用域自动出现在 UI，无需改前端。

### 3.3 筛选维度（一期）

- 赛道（多选）· 应用域（随赛道联动）· 价档（599/1999/4999/咨询制）· 关键词（标题+target_app+features 全文）· 排序（默认/价格/名称）

### 3.4 前端

- 删除 `store.html` 的 `DIR_SHELVES` 硬编码，改由 facets 动态生成（保留目录视图的 UI 形式，数据源换掉）
- 筛选状态写入 URL query（可分享/可回退）

---

## 四、75 条逐条归类表（待审核）

| # | 货架 ID | 赛道 | 应用域 | 归类理由 |
|---|---|---|---|---|
| 1 | IM-CPO-WDM5 | D cpo | CPO 光引擎 | 标题含 CPO 共封装 |
| 2 | IM-QCHIP-INT | C quantum | 量子计算读出 | system_type=quantum_fidelity |
| 3 | IM-SENSE-RING | B sensing | 生化传感 | 折射率传感 |
| 4 | IM-LASER-INT | E component | 光源与频梳 | 激光源器件（非终端系统） |
| 5 | IM-QCOM-LINK | C quantum | 量子计算读出 | system_type=quantum_fidelity |
| 6 | IM-800G-DR8 | A datacom | 收发引擎 | 速率+距离 |
| 7 | IM-WDM-8CH-1D | A datacom | WDM 与 ROADM | 解复用前端 |
| 8 | IM-DWDM-40CH | A datacom | WDM 与 ROADM | DWDM 阵列 |
| 9 | IM-FTTH-PLC8 | A datacom | 接入网 PON | FTTH 分光 |
| 10 | IM-FTTH-PLC16 | A datacom | 接入网 PON | FTTH 分光 |
| 11 | IM-CPO-OCS | D cpo | 光交换与路由 | 标题含 CPO，本体为光交换 |
| 12 | IM-LIDAR-TX | B sensing | 激光雷达 | FMCW 发射 |
| 13 | IM-QKD-TX-SHELF | C quantum | 量子保密通信 | QKD 发射端 |
| 14 | IM-QKD-RX-SHELF | C quantum | 量子保密通信 | QKD 接收端 |
| 15 | IM-QKD-MULTI4 | C quantum | 量子保密通信 | 多用户 QKD |
| 16 | IM-SENS-MZI | B sensing | 生化传感 | MZI 干涉传感 |
| 17 | IM-CHIPLET-IO | D cpo | chiplet 与中介层 | XPU 光 IO |
| 18 | IM-QCTRL-ZC3-10Q | C quantum | 量子计算读出 | 10 比特读出链 |
| 19 | IM-QCTRL-HERON-16Q | C quantum | 量子计算读出 | 16 比特读出链 |
| 20 | IM-QCTRL-WILLOW-12Q | C quantum | 量子计算读出 | 12 比特读出链 |
| 21 | IM-PSM4-SHELF | A datacom | 收发引擎 | 100G PSM4 |
| 22 | IM-FR4-SHELF | A datacom | 收发引擎 | 400G FR4 |
| 23 | IM-CWDM4-SHELF | A datacom | WDM 与 ROADM | CWDM4 解复用 |
| 24 | IM-LPO-112G | A datacom | 收发引擎 | 线性直驱 |
| 25 | IM-1.6T-DR8 | A datacom | 收发引擎 | 1.6T DR8 |
| 26 | IM-800G-FR4 | A datacom | 收发引擎 | 800G FR4 |
| 27 | IM-1.6T-FR4 | A datacom | 收发引擎 | 1.6T FR4 |
| 28 | IM-400G-DR4 | A datacom | 收发引擎 | 400G DR4 |
| 29 | IM-100G-LR4 | A datacom | 收发引擎 | 100G LR4 |
| 30 | IM-PON-50G | A datacom | 接入网 PON | 50G-PON |
| 31 | IM-OSW-1X8 | A datacom | 光交换与路由 | 可重构光开关（OCS/ROADM） |
| 32 | IM-LIDAR-RX | B sensing | 激光雷达 | FMCW 相干接收 |
| 33 | IM-BIOSENSE | B sensing | 生化传感 | 生物传感 |
| 34 | IM-COHERENT-400ZR | A datacom | 相干与长距 | 400G ZR 相干 |
| 35 | IM-RING-MOD | E component | 调制与开关 | 微环调制器（器件级） |
| 36 | IM-XGS-PON | A datacom | 接入网 PON | XGS-PON |
| 37 | IM-WSS-1X9 | A datacom | WDM 与 ROADM | 波长选择开关 |
| 38 | IM-VOA | E component | 无源与耦合 | 可变光衰减器（器件级） |
| 39 | IM-MZI-MOD | E component | 调制与开关 | MZM（器件级） |
| 40 | IM-PSR | E component | 偏振与旋转 | 偏振分束旋转器 |
| 41 | IM-PHOTONIC-INTERPOSER | D cpo | chiplet 与中介层 | 光子中介层 |
| 42 | IM-OPTO-COMPUTE | D cpo | 光计算与新型互连 | 光计算 fabric（chiplet 级） |
| 43 | IM-OCT | B sensing | 医疗与成像 | 光学相干层析 |
| 44 | IM-OPA-LIDAR | B sensing | 激光雷达 | OPA 固态雷达 |
| 45 | IM-COHERENT-RX | A datacom | 相干与长距 | 相干接收机 |
| 46 | IM-ONCHIP-NOC | D cpo | chiplet 与中介层 | 片上光网络 |
| 47 | IM-MCF-FANOUT | E component | 光纤接口与扇出 | 多芯光纤扇出 |
| 48 | IM-OPTICAL-GYRO | B sensing | 惯性与物理量 | 光纤陀螺 |
| 49 | IM-MRR-FILTER | E component | 滤波与波分 | 微环谐振滤波器 |
| 50 | IM-SPLITTER-TREE | E component | 无源与耦合 | 功分树（器件级） |
| 51 | IM-TRUE-TIME-DELAY | B sensing | 微波光子与雷达 | TTD 波束成形 |
| 52 | IM-GAS-SENSE | B sensing | 生化传感 | 气体/吸收光谱 |
| 53 | IM-GRATING-COUPLE | E component | 光纤接口与扇出 | 光栅耦合/光纤贴装接口 |
| 54 | IM-AWG-DEMUX | A datacom | WDM 与 ROADM | AWG 解复用 |
| 55 | IM-ONCHIP-SPECTROMETER | B sensing | 光谱与成像 | 片上光谱仪 |
| 56 | IM-MDM-MUX | E component | 复用与多维度 | 模分复用器 |
| 57 | IM-OPTCOMB | E component | 光源与频梳 | 芯片级光频梳 |
| 58 | IM-POL-ROTATOR | E component | 偏振与旋转 | 偏振旋转器 |
| 59 | IM-3.2T-DR8 | A datacom | 收发引擎 | 3.2T DR8 |
| 60 | IM-1.6T-LPO | A datacom | 收发引擎 | 1.6T LPO |
| 61 | IM-1.6T-ZR | A datacom | 相干与长距 | 1.6T 相干 ZR |
| 62 | IM-CPO-16CH | D cpo | CPO 光引擎 | CPO 16 通道光引擎 |
| 63 | IM-UCIE-OPTICAL | D cpo | chiplet 与中介层 | UCIe-Optical |
| 64 | IM-LIDAR-FULL | B sensing | 激光雷达 | 固态激光雷达全前端 |
| 65 | IM-POC-BIOSENSE | B sensing | 生化传感 | POCT 生物/气体 |
| 66 | IM-FTTR-PLC32 | A datacom | 接入网 PON | FTTR 分路 |
| 67 | IM-TTD-5G | B sensing | 微波光子与雷达 | TTD 5G 波束成形 |
| 68 | IM-QKD-FULL-LINK | C quantum | 量子保密通信 | QKD 全链路 |
| 69 | IM-QCTRL-32Q | C quantum | 量子计算读出 | 32 比特读出 |
| 70 | IM-OPA-2D | B sensing | 激光雷达 | 2D OPA 固态雷达 |
| 71 | IM-OPTCOMB-WDM | E component | 光源与频梳 | WDM 锁定光频梳 |
| 72 | IM-CPO-OIO-8CH | D cpo | CPO 光引擎 | system_type=cpo_optical_io |
| 73 | IM-CPO-OIO-16CH | D cpo | CPO 光引擎 | 同上 |
| 74 | IM-CPO-OIO-CHIPLET | D cpo | chiplet 与中介层 | 同上（chiplet 直连） |
| 75 | IM-CPO-ELS-FIBER | D cpo | CPO 光引擎 | 同上（ELS + 光纤 I/O） |

**合计**：A 25 · B 15 · C 10 · D 12 · E 13 = **75** ✓

### 4.1 需要人工复核的模糊项（7 条）

| 货架 ID | 我的归类 | 替代方案 | 说明 |
|---|---|---|---|
| IM-LASER-INT | E 光源 | D（CPO 发射端） | 它是"异质集成黑箱源 + 无源网"，既可作通用光源也可作 CPO 发射 |
| IM-COHERENT-RX | A 相干与长距 | E 器件（90° 混频器） | 本体是器件，但只服务相干系统 |
| IM-OPTO-COMPUTE | D 光计算 | 单列 F | 仅 1 条，单列赛道太细；暂挂 D 的"光计算与新型互连" |
| IM-OSW-1X8 | A 光交换 | E 器件 | 可重构光开关，系统属性强于器件属性 |
| IM-VOA | E 无源与耦合 | A（ROADM 功率均衡） | 主要用在 ROADM，但本体是无源器件 |
| IM-MDM-MUX | E 复用与多维度 | A（容量提升） | 模分复用尚属前沿，未成主流系统 |
| IM-SPLITTER-TREE | E 无源与耦合 | A（PON 分光网） | 功分树主要服务 PON，本体为无源器件 |

---

## 五、CI 护栏（防复发，与上一轮同构）

新建 `lda/run_shelf_taxonomy_smoke.py`，判据：

1. **75/75 全覆盖**：每条货架的 `track` 与 `app_domain` 均非空
2. **枚举闭合**：`track` ∈ {datacom, sensing, quantum, cpo, component}；`app_domain` ∈ `SHELF_TAXONOMY` 已注册值
3. **赛道内应用域合法**：`app_domain` 必须属于该 `track` 下允许的集合（防跨赛道错挂）
4. **派生表同步**：`innovation_market.json` 中的标签与 `.py` 逐条一致
5. **前端不再写死目录**：断言 `store.html` 不含 `DIR_SHELVES` 硬编码 ID 列表（防回潮）
6. 🔴 **反向测试**：构造一条无 `track` 的货架注入 ⇒ 判据 1 必须 FAIL（证明护栏会响，非纸上谈兵）

登记进 `CORE_SMOKES`（按新铁律：写了 smoke 必须进 core，否则 `run_ci_coverage_gate_smoke.py` 会报缺口）。

**同步四处**（上一轮立的铁律）：① 数据层 `.py` ② 派生表 `.json` ③ 前端（改为动态，从根本上不再需要同步）④ CI 断言。

---

## 六、二期预留：锚定导购（本次不实施）

接口预留：`/api/shelf` 的 facets 与结构化标签即导购的检索底座。

**锚定导购三段式**（已与杜先生确认的边界）：

1. **LLM 只做需求解析**：自然语言 → 结构化条件（track + 数值约束 + 关键词）。**这步错了无害**——条件会显示给用户，可手动改。
2. **确定性层**：按条件筛候选 → 对每条**真跑 `evaluate()`** → 取真实死标量（插损/密度/余量/密钥率）。
3. **LLM 只做解释与对比**，**硬禁止输出任何规格数字**（数字一律从 `evaluate()` 结果渲染 + 护栏断言）。

**为什么不做纯 LLM 导购**：LDA 唯一区别于普通电商的资产是"每个数字都可溯源、LLM 不进判决路径"。
纯 LLM 导购必然编造规格数字，一次即清零该资产；且 75 条规模下确定性筛选本就更准。

---

## 七、排期（已完成）

- v0.9.41 发版已完成（118 条全绿 + 三端同步 + 生产部署）。
- 一期已随 **v0.9.42** 交付。

---

## 八、实施结果（v0.9.42 交付后补记）

### 8.1 落地的判据与数据

| 项 | 结果 |
|---|---|
| 分类标签 | 75/75 全覆盖，分布 A25 / B15 / C10 / D12 / E13，与设计文档**逐条一致** |
| 最宽赛道占比 | 70.7%（改造前 `link` 独占 53/75）→ **33.3%**（数通 25/75） |
| `/api/shelf` | 新增 `facets`（track/app_domain/tier 三维计数）+ `labels`（中文标签 + 赛道→应用域联动表） |
| 前端 | `DIR_SHELVES` / `DIR_LABELS` 硬编码**已清零**；筛选项与中文标签全部动态渲染 |
| 方向映射 | 下沉到 `store.py: CUSTOM_DIRECTION_SHELVES`，覆盖 **75/75**（原 58/75），无脏 ID |
| CI | `run_shelf_taxonomy_smoke.py` **10/10**（含 3 道反向测试），登记进 core（118→119） |

### 8.2 前端筛选器行为实测（25/25）

只做语法检查是不够的（铁律「标签≠行为」）。做法：把 `store.html` 里**真实的
`<script>` 块**放进 node 沙箱（`vm.runInContext`，DOM / fetch / history 打桩），
注入**真实 `/api/shelf` 数据**执行，逐条断言行为。

| 覆盖 | 判据 |
|---|---|
| 加载 | 全量 75 条；无筛选时全显 |
| 赛道筛选 | `cpo` → 12 条，且结果 `track` 全等 |
| 两级联动 | `cpo + cpo_engine` → 5 条；切到不兼容赛道 ⇒ 失效应用域自动清理 |
| 防假阳性 | 跨赛道组合（`datacom + cpo_engine`）→ **0 条**（应用域 key 全局唯一的验证） |
| 价档 | `basic` → 15 条且全部 ¥599 |
| 关键词 | `QKD` → 4 条；近三轮新增 **17 条逐条可按 ID 搜到**（无静默遗漏） |
| 排序 | 价格升/降序单调性 |
| URL | 状态写入 query；从 `?track=sensing&tier=basic` 正确恢复 |
| facets 一致性 | 五个赛道计数与实数据逐项一致 |

> ⚠️ **期间我自己写错了 3 条断言，逐条用真实数据核实后改的是断言、不是判据**：
> ① 期望「关键词 `CPO-OIO` 命中 4 条」——实际 3 条（`IM-CPO-ELS-FIBER` 的 ID 不含该子串）；
> ② 期望「取消全部赛道后失效应用域被清理」——实际清空赛道会**扩大**合法应用域集，
> 保留 `cpo_engine` 是正确行为（筛出 5 条且自洽）；
> ③ 期望「关键词 `CPO` 覆盖整条 D 赛道 12 条」——**概念错误**，关键词检索不该被期望
> 覆盖赛道（那是赛道筛选的职责）。
> 改成：**改断言前先用真实数据核实到底谁错**，禁止为了让测试变绿而放宽判据。

### 8.3 为什么永久 CI 门禁用 Python 而非 node 行为测试

CI 里**没有任何 node 依赖**（已核实）。给 core 门禁引入 node 会破坏**外部可复现性**
（外部人 clone 后跑 `--tag core` 需要额外装 node）。故永久门禁 `run_shelf_taxonomy_smoke.py`
只守**数据层不变量**（漏标 / 枚举闭合 / key 唯一 / 派生表同步 / 方向映射脏 ID /
前端回潮 / facets 计数一致），这些恰恰是**会随数据扩张而漂移**的部分；
而筛选器的 JS 逻辑属一次性行为验证（8.2），其正确性由数据层不变量兜底。

🔴 判据 ⑦ 特意**真跑 `app.shelf_status()`** 取 facets 来比对，而不是在 smoke 里
另写一份同式复算——后者是重言式（`real == real`），app.py 口径写错了也测不出来。

### 8.4 补记：散文里的数字也会失真（第 ⑪ 判据的由来）

生产部署后实测 `/api/shelf` 时核对出一个**我自己写错的数字**：
README / CHANGELOG / 本文档通篇写「**5 赛道 + 20 应用域**」，
而代码实际是 **24 个应用域**（datacom 5 + sensing 6 + quantum 2 + cpo 4 + component 7）。

这正是本轮刚立的第五处同步项「**对外账本计数**」的又一个实例（前一实例是
`CI core 97 ≠ 117`）。处置不是改完数字就算，而是**加判据 ⑪**：
扫描 README / CHANGELOG 中的「N 应用域」，与代码实际数不符即 FAIL
（配反向测试 ⑫：注入错数字必须报）。

🔴 **为什么只锁「N 应用域」而不锁「N 赛道」**：「N 应用域」在两份文档里**各只出现
一次、无歧义**；而「N 赛道」在 CHANGELOG 历史文案里另有「4 赛道」表述（指当年
A/B/C 三赛道扩到四赛道的历史事实），一刀切断言等于 5 会**误报**。
⇒ **护栏设计要先查清会命中什么再落断言**，否则护栏自己制造噪音、最终被人关掉。

**教训**：**凡散文中描述代码实体的数字，都是会腐化的派生数据**。要么由代码生成，
要么由 CI 校验；两者都没有 = 下一次失真只是时间问题。
