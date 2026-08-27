# LDA LVS 签核技术文档（版图-原理图一致性 · 签核级）

> **版本**：v0.8.27（2026-08-27）· **状态**：正式沉淀
> **范围**：芯片级签核双闸之 LVS（Layout vs Schematic）——从 v0.8.24 单层签核、
> v0.8.25 多层扩展、v0.8.26 千器件规模，到 v0.8.27 千器件演示闭环，四版演进完成。
> **红线**：判决路径零 LLM——PASS/FAIL 由坐标几何 + 集合等价类比对决定。

---

## 1. 摘要（一页读懂）

LDA 的 LVS（Layout vs Schematic，版图 vs 原理图一致性检查）是**流片签核的必要
条件**：DRC 保证「版图可制造」，LVS 保证「版图即原理图」——版图中每个器件实例、
每条物理连接必须与原理图网表一一对应。版图与原理图不一致的芯片，即使 DRC 全过
也不能流片。

LDA LVS 的核心主张：**版图网表从布线几何独立恢复**（布线路径端点坐标 → 端口锚点
归属，不读原理图声明）——只有这样，签核才能发现「实现 ≠ 意图」（布线器/版图的
物理事实独立核对，而非自证）。

| 演进 | 版本 | 能力 | 锚题 | 题库 |
|---|---|---|---|---|
| 单层签核 | v0.8.24 | 六类违规死标量检出 | S9 | 42→43 |
| 多层扩展 | v0.8.25 | 层叠短路语义（同层才短/跨层安全/通孔桥） | S10 | 43→44 |
| 千器件规模 | v0.8.26 | 千器件全链路 0.92s ACCEPT + bbox 预检 3.6× | S11 | 44→45 |
| 演示闭环 | v0.8.27 | 千器件芯片演示（GDS/DRC/LVS 双闸） | — | CI 61 条 |

---

## 2. 背景与定位

### 2.1 为什么 LVS 是签核必要条件

芯片设计签核（sign-off）三道闸：
1. **DRC**（Design Rule Check）：版图几何符合工艺设计规则 → 可制造；
2. **LVS**（Layout vs Schematic）：版图电气连接与原理图一致 → 正确；
3. **工艺角/流片验证**：工艺波动下仍可制造、实测回流校准。

DRC 过 ≠ 可流片——布线器把 net_a 错接到 net_b 的端口时，几何完全合规，DRC 无感，
只有 LVS 能抓住「连错了」。LDA 将 LVS 与 DRC 并列构成**芯片级签核双闸**
（`export_chip_gds` 返回 `drc_report` + `lvs_report`）。

### 2.2 在 LDA 中的位置

```
原理图侧（设计意图）          版图侧（物理实现）
  LinkModel.ir            placement + routes
  （器件实例+网络）         （器件放置+布线路径）
         │                        │
         ▼                        ▼
  extract_schematic      extract_layout_netlist
  （原理图网表）          （版图网表：几何独立恢复）
         └──────────┬───────────┘
                    ▼
             run_lvs / run_lvs_multilayer
                    ▼
        ACCEPT / REJECT + 违规明细（全死标量）
```

---

## 3. 设计原理

### 3.1 几何独立恢复（本模块的核心方法论）

**问题**：版图网表如果从「布线器声明」读取（布线时记录了 net 连哪个端口），
那么 LVS 只是重复布线器自己的话——布线器 bug 会自证清白。

**解法**：LVS 只吃几何——每条布线路径的**端点坐标**，通过**端口锚点表**
（器件局部坐标 + 放置偏移 → 端口绝对坐标）做最近归属（容差 1µm）：
- 端点落在某端口锚点邻域 → 该 net 物理连接此端口；
- 端点无归属 → **悬空（dangling）**——布线的物理事实不成立；
- 同一端口被多条 net 端点占用 → **端口短路（short_port）**。

版图网表的每个元素都从「线画在哪、接到哪」独立推导，与原理图声明零耦合。
这正是 S9-S11 全部锚题「构造失配版图 → 必然检出」的根基。

### 3.2 网络等价类比对

- **原理图 net**：`LinkModel.ir.nets`（≥2 端口连接，单端口 IO 不参与比对）；
- **版图 net**：几何恢复的端口集合；
- **匹配**：同名 net 端口集合相同 → 一致；集合不同 → **错连（misconnect）**；
- **断路（open）**：原理图 net 在版图无对应布线（或悬空/自环）；
- **多余（extra）**：版图有布线而原理图无此 net。

### 3.3 判决语义

```
ACCEPT ⇔ 器件全匹配 ∧ 网络全匹配 ∧ 零违规
REJECT ⇔ 任一违规（open/short/misconnect/dangling/loop/extra/device_mismatch）
```

---

## 4. 架构

### 4.1 模块清单

| 模块 | 职责 | 版本 |
|---|---|---|
| `lda_l2/lvs.py` | LVS 核心：网表提取 + 比对 + 判决 + 报告；`run_lvs`（单层）/ `run_lvs_multilayer`（多层）；bbox 预检优化 | v0.8.24 / v0.8.26 |
| `lda_l2/layers.py` | 层栈定义（SOI M1/VIA12/M2 + 量子 Al 栈预留）；**`can_cross` 谓词** | v0.8.25 |
| `lda_harness/lvs_anchor.py` | S9 单层案例 + S10 多层案例构造（`build_lvs_case` / `build_multilayer_case`） | v0.8.24 / v0.8.25 |
| `lda_harness/scale_anchor.py` | S11 千器件案例（`build_chain_case` 链式 + 跨行 M2 跳线） | v0.8.26 |
| `lda_l2/chip_layout_export.py` | 集成：`export_chip_gds` 返回 drc_report+lvs_report（多层自动检测） | v0.8.24 / v0.8.26 |
| `lda_pdk/tapeout_pipeline.py` | 流片管道 **S4 LVS 段**（一致 ACCEPT / 错连 REJECT / 无版图 SKIP 诚实标注） | v0.8.24 |
| `lda_webui/app.py` + index.html | `/api/link_lvs`（单层/多层/scale 案例）+ LVS 面板 | v0.8.24-27 |
| `run_lvs_smoke.py` / `run_scale_smoke.py` / `run_chip_scale_demo.py` | CI 门禁（27/27 + 13/13 + 8/8） | v0.8.24-27 |

### 4.2 数据流（单层）

```
routes（{net_id: RouteResult}）
  → 端点坐标 + 端口锚点表（placement × port_anchor）
  → 最近归属（tol=1µm）→ nets/dangling/loops/port_shorts
  → 路径相交检测（bbox 预检 + 精确线段相交）→ short_cross
  → 与 schematic_nets 集合比对 → verdict + violations + lvs_markdown
```

---

## 5. 语义模型

### 5.1 单层六类违规（S9）

| 类别 | 语义 | 检出机制 |
|---|---|---|
| `open` 断路 | 原理图 net 版图未物理连通 | 无对应布线 / 悬空 / 自环 |
| `short_port` 端口短路 | 同端口被多 net 连接 | 端口占用冲突表 |
| `short_cross` 布线交叉 | 不同 net 路径相交（非共享端点） | 线段相交检测 |
| `misconnect` 错连 | 同名 net 端口集合不一致 | 集合等价类比对 |
| `dangling` 悬空 | 布线端点无端口归属 | 最近归属失败 |
| `loop` 自环 | 布线两端同一端口 | 端点归属相同 |
| `extra` / `device_*` | 多余布线 / 器件失配 | 集合差 |

### 5.2 多层层叠短路语义（S10 · v0.8.25）

多层版图 = 信号层（M1/M2）+ 介质层（隔离）+ 通孔层（VIA12 跨层桥）。
**`can_cross(l1, l2)` 谓词**是层叠短路判定的基石：

- **同层路径相交 → short**（`can_cross('M1','M1') = True`）；
- **跨层垂直投影重叠 → 安全**（`can_cross('M1','M2') = False`，介质隔离）——
  这是多层版图能叠布线的物理依据；
- **via 桥接自动发现**：同一 net 的跨层段端点坐标重合 → 通孔桥（合法跨层）；
  不同 net 的跨层端点重合 → **`short_via`**（未经声明的跨层相接）；
- **端口按层匹配**：M1 布线段只匹配 M1 端口（层不匹配 = 悬空）。

### 5.3 千器件规模协同（S11 · v0.8.26）

千器件链式链路 + 行优先放置的固有矛盾：**行尾→下一行首的跳线必然横穿同行**。
解法 = **跨行跳线走 M2 层**（规模 × 多层协同）：
M1 短垂（5µm 不穿下行）→ M2 横穿（每行 y 错开）→ M1 纯垂直短接（无水平段）+
**奇偶行 x 偏移交错**（0/10）防垂落列共线。

LVS 相交检测 **bbox 预检**（路径级 + 段级快速排除）——千器件 LVS 2.04s → 0.56s
（3.6×），单层/多层共用。

---

## 6. 锚题体系（S9-S11 · 判决全部死标量）

| 锚 | 案例 | 判决 | 语义 |
|---|---|---|---|
| **S9** 单层 LVS | consistent 一致版图 | 1.0 | 3 器件（WG→Ring→WG）2 net 全匹配 |
| | open / misconnect / short / dangling | 0.0 | 断路 / 错连 / 端口共享 / 悬空 |
| **S10** 多层 LVS | consistent 跨层 via | 1.0 | M1 段+通孔+M2 段（SOI 层栈） |
| | cross_short / via_short / port_short / dangling | 0.0 | 同层交叉 / 通孔短路 / 端口共享 / 悬空 |
| **S11** 千器件 | consistent 1000 器件 | 1.0 | 全链路（构建+放置+布线+LVS）ACCEPT |
| | disconnect / misroute | 0.0 | 局部断路 / 局部错连 |

性能预算（S11）：千器件全链路 ≤ 5s（实测 0.92s）——**正确性由 golden 判、
性能由预算断**，两者都是死标量。

---

## 7. 验证证据

### 7.1 CI 门禁（全绿）

| smoke | 断言 | 状态 |
|---|---|---|
| `run_lvs_smoke.py` | 单层 17 + 多层 10 = 27/27 | CI core |
| `run_scale_smoke.py` | 千器件 13/13（含性能预算） | CI core |
| `run_chip_scale_demo.py` | 千器件芯片演示 8/8 | CI core |
| 计数一致性 | 45 题 / S1-S11 / CI 61 条守护 | CI core |

CI core **61 PASS / 0 FAIL**（673s）——S9/S10/S11 三锚经 `golden_value` 进入
harness 统一判题路径。

### 7.2 关键实测数据

- 单层正例：3 器件 2 net 全匹配 ACCEPT；四类失配全 REJECT（对应违规类别检出）；
- 多层正例：跨层 via 布线 ACCEPT；跨层投影重叠安全（介质隔离）；
- 千器件：1000 器件/999 net 全链路 0.92s ACCEPT；DRC 1000/1000 + LVS ACCEPT 双闸；
- 千器件芯片演示：GDS 2033 元素 95KB 可解析，全链路 0.99s。

### 7.3 与 DRC 双闸的集成证据

`export_chip_gds` → `drc_report`（可制造性）+ `lvs_report`（一致性）并列；
`tapeout_pipeline` S4 LVS 段三态：一致 ACCEPT / 错连 REJECT 阻断 / 无版图
SKIP 诚实标注不阻断（兼容既有器件级接口）。

---

## 8. 工程教训（S9-S11 设计踩坑实录）

1. **同层段意外共线陷阱**（S10/S11）：单行放置下 Waveguide 端口全在 y=0，
   两条 M1 水平段必然共线重叠——多层案例须自定义放置分离各层段；首版测试曾把
   「真实同层短路」误当误报——实际是 LVS 正确检出（**先怀疑测试构造，别怀疑引擎**）。
2. **行尾跳线垂落穿过下方行**（S11）：行尾器件同列（x_end），跳线 M1 段垂落
   必然穿过下方行尾端口（897 违规）→ M1 短垂不穿下行。
3. **行首器件共列**（S11）：所有行首 x=0，跳线垂落列相同 → 奇偶行 x 偏移交错。
4. **M1 段 2 的 L 形水平段横穿**（S11）：曼哈顿 L 形路径的水平段在 M1 层横穿
   相邻跳线垂落段 → M2 直接横穿到目标列 + M1 纯垂直短接。
5. **多层网表恢复的端口匹配**：仅首段起点/末段终点匹配端口，中间端点是 via
   跳点（不匹配端口、不判 dangling）。
6. **case 名歧义**（WebUI）：consistent/dangling 同时属单层与多层案例 → 重叠名
   默认单层、显式 multi 才多层（避免自动识别误判）。

---

## 9. 诚实边界

- **层栈为公开工艺近似**（SOI M1/VIA12/M2 + 量子 Al 栈预留）：真实 PDK 的数十层
  金属/通孔规则（via 规则、金属密度、层间距）属发动期晶圆厂对接后扩展（接口已
  就位——`LayerStack` 数据驱动，新增层/规则零改动接入）。
- **版图模型为单层/双层波导布线**（2 端口 net + 跨行跳线）：任意网表（复杂障碍
  避让、多端网）的万器件级未做压测；A* 网格/多端网增量建树可扩展。
- **DRC 为器件级可制造性自查**（非真实 PDK 全规则）；LVS 与 DRC 构成仿真级签核，
  真实晶圆厂 DRC-LVS 工具链对接属发动期。
- **判决路径零 LLM**（红线）：`lvs.py` / `scale_anchor.py` 源码 import 断言
  无 openai/anthropic/ollama/transformers。

---

## 10. 路线与下一步

- **版图 7 差距已全部闭合**：①A* 全局布线 ②诚实退化 ③2D 放置 ④多端网+有源基元
  ⑤LVS 签核 ⑥多层 M1/VIA12/M2 ⑦千器件规模 + 千器件芯片演示闭环。
- 候选下一步：
  - **LVS 深化**：真实 PDK 层叠规则接入（发动期前置接口）、多端网 LVS 恢复、
    万器件压测；
  - **签核闭环**：LVS REJECT 反哺布线器（自动修复闭环）；
  - **院校/生态素材**：本技术文档 + S9-S11 锚题可作「确定性签核」说服素材
    （与基准对照报告同源：死标量可复现、LLM 不进判决）。

---

*本文档为 LDA 芯片级签核双闸（DRC+LVS）的技术沉淀；所有数据可经
`python run_lvs_smoke.py && python run_scale_smoke.py && python run_chip_scale_demo.py`
复现（CI core 61 条门禁）。*
