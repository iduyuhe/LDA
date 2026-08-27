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