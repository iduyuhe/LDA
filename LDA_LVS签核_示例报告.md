# LDA LVS 签核报告（v0.8.24 · 版图-原理图一致性 · 签核级）

> 版图审计差距 #5 落地：芯片级签核双闸（DRC 可制造性 + LVS 一致性）齐备。
> 版图网表**从布线几何独立恢复**（布线端点→端口锚点归属，不读原理图声明），
> 与原理图网表比对，六类违规死标量检出，ACCEPT/REJECT 确定性判决——LLM 不进判决路径。

## 一、正例：一致版图

- 案例链路：WG0 → Ring0（in/out/drop）→ WG1，2 条内部网（net_a/net_b）
## LVS 签核（版图 vs 原理图一致性）

- 判决：**✅ ACCEPT**（0 项违规）
- 器件：原理图 3 · 版图 3 · 匹配 3
- 网络：原理图 2 · 版图 2 · 一致 2/2

*LVS 签核：版图网表由布线几何独立恢复（端点→端口锚点容差 1.0µm），比对原理图 2 网 vs 版图 2 网；2/2 网一致，违规 0 项。判决全死标量（坐标几何 + 集合比对），LLM 不进判决路径。诚实边界：当前版图模型为单层波导（2 端口 net），多层金属/通孔完整 LVS 属发动期 PDK 对接后扩展。*

## 二、四类失配反例（全部 REJECT）

| 案例 | 构造 | 判决 | 检出违规 |
|---|---|---|---|
| open | 删 net_b 布线（物理断连） | **REJECT** | open（1 项） |
| misconnect | net_a/net_b 布线互换 | **REJECT** | misconnect（2 项） |
| short | net_b 错接 wg0.out（共享端口） | **REJECT** | misconnect、short_cross、short_port（3 项） |
| dangling | net_b 端点指向空白 | **REJECT** | dangling、open（2 项） |

## 三、S9 锚全案例自检（harness 题库 42→43）

- 自检通过：**True**（仅 consistent 判 ACCEPT，四反例全 REJECT）

## 四、集成面

- `export_chip_gds` → 返回 `lvs_report`（与 `drc_report` 并列签核双闸）
- `tapeout_pipeline` → S4 LVS 段（一致 ACCEPT / 错连 REJECT / 无版图 SKIP 诚实标注）
- WebUI → `/api/link_lvs`（五案例）+ 独立 LVS 面板 + `/api/link_design` 返回 lvs_report
- CI core **59 条全绿**（run_lvs_smoke 17/17）

## 五、诚实边界

- 当前版图模型为单层波导（2 端口 net）；多层金属/通孔/真实工艺图层叠的完整 LVS 属发动期 PDK 对接后扩展（接口已就位）
- LVS 与 DRC 并列构成仿真级签核；真实晶圆厂 DRC-LVS 工具链对接属发动期
## 六、多层版图 LVS（v0.8.25 · 版图差距 #6 · M1/VIA12/M2 层叠）

- 层栈：**SOI-3L（公开近似）**（信号层 ['M1', 'M2'] · 通孔层 ['VIA12'] · via 映射 {'VIA12': ('M1', 'M2')}）
- **can_cross 谓词**（多层短路判定基石）：M1∩M1 可短 = True；M1×M2 介质隔离 = False——**跨层垂直投影重叠不短路**，这是多层版图可叠布线的物理依据

### 多层案例判决（S10 锚 · 题库 43→44）

| 案例 | 构造 | 判决 | 检出违规 |
|---|---|---|---|
| consistent | 跨层 via 一致版图 | **ACCEPT** | 零违规 |
| cross_short | 短路构造 | **REJECT** | short_cross |
| via_short | 短路构造 | **REJECT** | short_cross、short_via |
| port_short | 短路构造 | **REJECT** | misconnect、short_port、short_via |
| dangling | 失配 | **REJECT** | dangling、open |

### 层叠短路语义（多层 vs 单层）

- **同层路径相交 → short_cross**（net_a/net_b 的 M1 段中点交叉，带层标注 `M1∩M1`）
- **通孔短路 → short_via**（net_b 端点撞 net_a 的 via 点 = 未经声明的跨层相接）
- **跨层投影重叠 → 安全**（M1 段与 M2 段垂直重叠被介质隔离，不判短）
- **端口按层匹配**（M1 段只接 M1 端口；层不匹配 = 悬空）

### 诚实边界

- 多层模型为公开工艺近似层栈（SOI M1/VIA12/M2 + 量子 Al 栈预留）；真实 PDK 的数十层金属/通孔规则属发动期对接（接口已就位）
- 版图 7 差距进度：①A* ✅ ②诚实退化 ✅ ③2D 放置 ✅ ④多端网+有源基元 ✅ ⑤LVS ✅ **⑥多层 ✅**（剩 ⑦规模——后置项）
## 七、千器件规模扩展（v0.8.26 · 版图差距 #7 收官 · S11 规模锚）

- 案例：**1000 器件链式链路**（999 条内部 net）+ 2D 放置 + 多层布线 + LVS 签核全链路
- **性能预算 5.0s 死标量**（正确性由 golden 判、性能由预算断）——实测各案例耗时：

| 案例 | 判决 | 违规 | 全链路耗时 |
|---|---|---|---|
| consistent | **ACCEPT** | 零违规 | 0.941s |
| disconnect | **REJECT** | open | 0.952s |
| misroute | **REJECT** | misconnect | 0.938s |

### 规模 × 多层协同（跨行跳线走 M2 层）

- 行内 net：M1 直连；跨行跳线：**M1 短垂（5µm）→ M2 横穿（每行 y 错开）→ M1 纯垂直短接**
- 奇偶行 x 偏移交错（0/10）防跳线垂落列共线；LVS 相交检测 bbox 预检 **3.6× 提速**（千器件 2.04s→0.56s）

### 版图 7 差距全部闭合

①A* 全局布线 ✅ ②诚实退化 ✅ ③2D 放置 ✅ ④多端网+有源基元 ✅ ⑤LVS 签核 ✅ ⑥多层 M1/VIA12/M2 ✅ **⑦千器件规模 ✅**

- 诚实边界：千器件为链式规则布线（波导族）；任意网表（含复杂障碍避让）的万器件级仍属后续优化（A* 网格/多端网增量建树可扩展，未做万级压测）