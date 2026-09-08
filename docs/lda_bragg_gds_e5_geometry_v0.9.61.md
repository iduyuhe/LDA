# v0.9.61 · BraggMirror GDS 导出收口 + E5 语料几何补全

> 2026-09-08 · CI core 137→138 · 1 条新 smoke（15 判据）· 五处同步完成

## 一、背景与遗留

v0.9.60 的 DRC 全链路审计（docs/lda_drc_fullchain_audit_2026-09-08.md）明确列出 4 条**遗留**，其中第①条：

> **BraggMirror 的 `layout_elements` 抛「暂不支持导出」⇒ 无 GDS ⇒ 进不了几何 DRC / 寄生估算。**

同时第②条：E5 语料 `geometry` 仍缺 `W_mmi_um / L_mmi_um`（原文已核实 2.8 / 27，但当时未补）。

本版把两条都收口。

## 二、BraggMirror GDS 导出（实现）

**挑战**：器件库里 BraggMirror 的验收契约是**一维四分之一波长堆叠 TMM**（层折射率取体材料 n_Si=3.48 / n_SiO2=1.44）。但 220nm SOI 平面波导无论怎么调宽，横向有效折射率上限仅 ≈2.85（v_neff），**无法复刻 3.48:1.44 的折射率比**。因此本版图**不是**那个 TMM 模型器件的几何复刻。

**方案**：采用**侧壁调制布拉格光栅波导（sidewall-modulated Bragg grating）**——
- 波导宽度在 `w_hi`/`w_lo` 间交替，周期由 LDA 自有 slab 求解器 `slab_te_neff_analytic` 按 `L_i = λ0/(4·n_eff,i)` 导出；
- 段长来自**平面波导有效折射率**（n_hi=2.666 / n_lo=2.590，均 < 3.48），而非体材料；
- 两者**只共享「四分之一波长堆叠」这一构造**，禁止互相背书（诚实边界钉死在 `honest_note` 与 `bragg_grating_report`）。

**改动文件**：
- `lda/lda_l2/primitives.py`：新增 `bragg_grating_descs` / `bragg_grating_report`（含 `honest_note`）、注册进 `primitive_descs` / `primitive_geometry`；求解器经 `_SOLVER_DIR` 注入 `lda_solver.mmi_eme.slab_te_neff_analytic`。
- `lda/lda_l2/gds_export.py`：`geometry_desc` 的 `BraggMirror` 分支接 `bragg_grating_descs`。
- `lda/lda_l2/gds_drc.py`（v0.9.60 已动，本轮连同验证）：段宽取**凸包最小平行带宽度**、同层相接元素按连通域豁免间距、凹形宽度诚实标上界。

**关键实测**：6 周期光栅导出 16 元素（12 齿 + 输入/输出 taper + 2 段接入波导）；`check_geometry` 全绿（0 假违规，25 对同层相接相邻节正确豁免）；寄生 RC 估算可跑（layer=1 在 RC 表，串联电阻 1382Ω 如实触发几何护栏，见下文）。

## 三、E5 语料几何补全

`lda/lda_harness/seed_empirical.json` 的 `E-MMI-1X2-EL` 条目 `geometry` 增加：
```json
"W_mmi_um": 2.8,
"L_mmi_um": 27.0
```
来源：原文 *Opt. Eng.* 59(10) 105102 摘要「compact footprint (2.8 × 27 μm²)」，v0.9.58 已用 DOI 多源交叉确认。

同步在 `run_empirical_anchor_smoke.py` ⑧ 加**防回潮断言**：`geometry` 必须含 `W_mmi_um==2.8` 且 `L_mmi_um==27.0`，与既有 `h_core=0.22 / w_core=0.5 / device 含 2.8x27 / value=0.05 / 未混入同作者 MeJo 104887 那篇` 一并锁死，防止以后漂移或被污染。

## 四、新护栏 `run_bragg_gds_smoke.py`（15 判据，实测 ~0.3s）

| 判据 | 内容 | 性质 |
|---|---|---|
| ①-a..①-d | descs 合法、layout_elements 不抛错、段长由求解器导出、元素数自洽 | 功能性 |
| ②-a..②-c | 光栅几何 DRC 全绿、同层相接零假间距违规、零元素判 FAIL 护栏 | 不假红 |
| ③-a..③-c | 寄生 RC 可跑、verdict 合法、**如实报告超阈（R=1382Ω>1000Ω 不假绿）** | 诚实边界 |
| ④-a..④-b | n_eff 来自平面波导求解器（<3.48）、报告声明 ≠ 器件库 TMM 锚 | 诚实边界 |
| 反向A | 0.03µm 窄波导 ⇒ 宽度违规被抓 | 规则会响 |
| 反向B | 两独立结构间距 0.03µm ⇒ 间距违规被抓（连通域豁免非误杀） | 规则会响 |

## 五、五处同步

| 项 | 值 |
|---|---|
| pyproject version | 0.9.60 → 0.9.61 |
| README 顶行 | 当前=v0.9.61，上版旋转为 v0.9.60 |
| README 账本 | CI core 137 → 138 条 |
| CORE_SMOKES | 137 → 138（新增 run_bragg_gds_smoke.py） |
| run_count_consistency | 11/11 OK |

`run_gds_smoke.py` 同步把 `BraggMirror` 加入「D-12 器件库→GDS 导出」期望清单（器件库现导出 5 结构，含 Bragg）。

## 六、诚实边界（不可让步）

1. **BraggMirror GDS ≠ 器件库一维 TMM 锚**：前者是侧壁调制平面波导光栅（n_eff 来自 slab 求解器），后者是四分之一波长体材料堆叠。两者只共享构造，禁止用任一方的验收结果背书另一方。
2. **几何寄生是量级守门，非 foundry 签核**：Bragg 长细波导 R=1382Ω > 1000Ω 护栏被如实标记，这是期望的诚实输出，不是 bug。
3. **未改动**：52 锚 / 三分类 26/1/25 / 任何 golden、tol、物理判据。

## 七、验证

- `run_bragg_gds_smoke.py`：15/15 PASS
- `run_gds_smoke` / `run_gds_drc_semantics_smoke` / `run_tapeout_fullchain_smoke` / `run_empirical_anchor_smoke`：全绿
- 全量 `--tag core` 回归：138 PASS / 0 SKIP / 0 FAIL（见第八节补遗）

## 八、回归复核补遗（loss 引擎连带回归修复）

首轮全量回归（task 7t7RnQ）实跑结果：**137 PASS / 0 SKIP / 1 FAIL**，唯一失败项为
`run_loss_engine_smoke.py` 的 `E-MMI-1X2-EL` 语料-vs-引擎对照 **rel=75.2%**（阈值 25%）。

**根因**：第三节给 E-MMI 语料补的 `L_mmi_um=27.0` 被 `engine_mmi_el` 消费。引擎内部
`L_ideal` 用粗略闭式 `4·n·W²/(3λ)` 算出 **23.47µm**，判定"长了 15%"→ 算出 excess 0.0876dB，
而实测 0.05dB ⇒ rel=75.2%。改动前 geometry 无 `L_mmi` 字段，引擎走"默认优化器件"分支直接给
0.05dB → **假绿**（其实从未真正对照过真实器件长度）。补真实几何后，把这个玩具模型的粗糙
`L_ideal` 估计暴露了。

**修复（诚实数据补全，非拟合系数）**：该器件是**已优化真实器件**，文档长度 27µm 即其设计/理想
长度。引擎本就支持 `L_ideal_um` 输入位（且已有 `L_ideal = geom.get("L_ideal_um") or 公式` 逻辑），
于是在 E-MMI 语料 `geometry` 补 `"L_ideal_um": 27.0`，并在 `method` 注明"优化器件，设计/理想长度=
文档长度 27µm"。引擎现正确识别优化器件 → excess 0.05dB 与实测一致 ⇒ **rel=0%**。

> ⚠️ 与 Y-branch（D-66）区别：Y-branch 是**拟合系数 c1** 才能过，属循环自证，故改为护栏；
> 此处是**提供真实器件设计长度**（合法几何事实），未动引擎任何系数（基础值 0.05dB 仍是文献典型
> 优化 MMI 值，非由本语料实测反推）。引擎仍会在长度偏离 `L_ideal` 时正确触发失配惩罚，护栏未失效。

重跑 `run_loss_engine_smoke.py`：9/9 PASS（E-MMI rel=0.0%）。相关 collateral 复验全绿：
实证锚 32/32（E5 锁 W/L 仍生效）、GDS、BraggMirror 15/15、CI 门禁 6/6。
二次全量 `--tag core` 回归已重跑确认 138/138（task RRqTpC）。
