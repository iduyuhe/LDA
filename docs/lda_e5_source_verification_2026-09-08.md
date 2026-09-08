# E5「回原文核实」报告（v0.9.58 · **含一次自我造成的严重失误复盘**）

> ## 结论先行
>
> **语料 `E-MMI-1X2-EL` 的原始记录是逐字正确的，一个字都不用改。**
>
> 本报告记录两件事：
> 1. **核实结果**：E5 引用的 *Optical Engineering* 59(10) 105102 经 **4 个独立书目库**
>    交叉确认，其 2.8×27 µm² / 220 nm / 实验实测 / TE 0.05 dB 与语料**逐字吻合**。
> 2. **失误复盘**：我在第一轮核实中**把语料改错了**，并已写进对外账本；
>    复核时才发现，已**全部回滚**。错误性质与根因记录在下，并已钉成 CI 断言。

---

## 一、正确的事实（复核后确认）

**D. Chack & S. Hassan**, "Design and **experimental** analysis of multimode
interference-based optical splitter for on-chip optical interconnects",
***Optical Engineering* 59(10), 105102** (2020-10-10),
DOI **10.1117/1.OE.59.10.105102**.

摘要逐字（4 个来源一致）：

> "Multimode interference (MMI)-based optical splitter is designed and
> **experimentally demonstrated** on silicon on insulator for on-chip optical
> interconnect. We have proposed MMI-based 1 × 2 optical 3-dB splitter having a
> compact footprint **(2.8 × 27 μm²)**. The device shows low excess loss of
> **0.05 dB for TE mode** at operating wavelength 1550 nm and <0.45 dB over
> broad wavelength 1430 to 1675 nm (S–C–L–U band) using eigenmode expansion
> (EME) method."

### 证据链（4 个相互独立的书目库，非单一页面孤证）

| # | 来源 | 确认内容 |
|---|---|---|
| 1 | **NASA ADS**（`2020OptEn..59j5102C`） | 作者 Chack, D. / Hassan, S.；卷期页；完整摘要 |
| 2 | **EurekaMag**（Accession 100374708） | *Optical Engineering* 59(10): 105102；摘要 |
| 3 | **Semantic Scholar** | `@article{Chack2020DesignAE, author={Devendra Chack and Shamsul Hassan}, journal={Optical Engineering}, volume={59}, pages={105102}}` |
| 4 | **SPIE Digital Library / prophy.ai** | 收稿 2020-06-26、接收 2020-09-21、上线 2020-10-10；DOI 一致 |

### 与语料逐字段对照 —— **全部吻合**

| 字段 | 语料原值 | 原文 | 判定 |
|---|---|---|---|
| `citation` | Opt. Eng. 59(10), 105102 (2020)，DOI 10.1117/1.OE.59.10.105102 | 同 | ✅ |
| `device` | 2.8×27 µm² footprint | "compact footprint (2.8 × 27 μm²)" | ✅ |
| `measured_value` | 0.05 dB | "0.05 dB for TE mode at 1550 nm" | ✅ |
| `method` | "TE 模 1550nm" | 同 | ✅ |
| `fab_source` | "EME 设计 + **实验演示**" | "**experimentally demonstrated**" | ✅ |
| `geometry.h_core_um` | 0.22（220 nm 标准 SOI） | 未公开明示，220 nm 为 SOI 单模标准值 | ✅ 合理 |

---

## 二、⚠️ 失误复盘：我第一轮把正确的数据改错了

### 发生了什么

第一轮核实时，我用「作者名 + 关键词」检索，命中的是同组作者 2020 年发表的
**另一篇**论文：

> **S. Hassan & D. Chack**, "Design and analysis of polarization independent MMI
> based power splitter for PICs", ***Microelectronics Journal* 104, 104887 (2020)**,
> DOI 10.1016/j.mejo.2020.104887
> —— 2.6×6.6 µm² / **340 nm** / **纯仿真**（3D EME + varFDTD）/ TE 0.04 dB、TM 0.06 dB

我**没有核对语料里的 DOI 本身**，就反过来说语料"张冠李戴"，并把 4 个字段
按另一篇改写，还写进了 README 对外账本、benchmarks note、语料 note、本报告四处。

### 两篇论文对照（易混根源）

| | **E5 引用的**（Opt. Eng.） | **我误采的**（Microelectronics J.） |
|---|---|---|
| 作者顺序 | **D. Chack & S. Hassan** | S. Hassan & D. Chack |
| 多模区 | **2.8 × 27 µm²** | 2.6 × 6.6 µm² |
| 硅层 | 220 nm（标准 SOI） | **340 nm** |
| 性质 | **实验演示** | **纯仿真**（Lumerical） |
| 数值 | **TE 0.05 dB** | TE 0.04 / TM 0.06 dB |
| 标题关键词 | "**experimental** analysis" | "polarization **independent**" |

**同组作者、同一年、同一器件类型、同一指标名（excess loss）、同一波长**——
仅靠"作者+关键词"检索必然串台。

### 根因（三条，均已写入 IRONLAWS）

1. **没有核对定位符本身**。语料里有精确 DOI，我却用作者名去搜，搜到什么就信什么。
   ⇒ **铁律：核实时以语料里的 DOI / URL 为唯一入口**，不要用作者名或标题关键词检索后
   再反过来否定定位符。
2. **否定结论下得太快**。我得出"语料 4 处失真"这种强结论，却没有先做
   「有没有可能两篇论文都存在」的排除。
   ⇒ **铁律：判定"记录错了"之前，必须先排除"存在另一篇同名/同作者论文"**。
3. **改对了才改，改错了要能回滚**。这次能全量回滚，是因为订正**尚未提交**
   且改动集中在三个文件；但这纯属运气。
   ⇒ **铁律：语料类改动先 `git diff > patch` 备份再动手**（本次已补做）。

### 处置

- `lda/lda_harness/seed_empirical.json`、`lda/lda_harness/benchmarks.py`、
  `README.md` 三处**全部 `git checkout` 回滚**到 v0.9.57（即原始正确值）。
- 错误 patch 存档于 `/tmp/lda_rollback_backup/erroneous_v058_edit.patch`（备查，不入库）。
- 本报告整体重写。

---

## 三、回滚后的正向产出：把「防串台」钉成 CI 断言

这次事故说明**语料字段本身缺少防回潮守护**。因此在既有
`run_empirical_anchor_smoke.py`（**32 判据**）中新增／保留三条：

| # | 断言 | 作用 |
|---|---|---|
| ⑦ | 全部实证语料可公开溯源（30/30 A 级含定位符） | 通用：来源边界 |
| ⑧ | **E5 原文防回潮**：DOI=10.1117/1.OE.59.10.105102 ∧ device 含 2.8x27 ∧ h=0.22 ∧ 含实验实测 ∧ value=0.05 ∧ **未混入同作者另一篇**（MeJo 104,104887 / 2.6x6.6 / 340nm） | **专防本次串台** |
| ⑨ | 仿真类 ground truth 必须在 note 显式声明非实测 | 通用：性质标注 |

**反向测试 7/7 ALL PASS**（`_reverse_test.py`，每个用例独立还原后注入失真，
确认断言确实转红）：

- ⑧a DOI 串台到同作者另一篇 → 转红 ✅（**正是本次事故的真实失误**）
- ⑧b 几何串台到 2.6x6.6 / 340 nm → 转红 ✅
- ⑧c h_core 0.22→0.34 → 转红 ✅
- ⑧d 实验实测被改成纯仿真 → 转红 ✅
- ⑧e value 0.05→0.04 → 转红 ✅
- ⑨ / ⑦ 用例 → 转红 ✅

---

## 四、对 E5 判定的影响

**E5 仍是自证桩（不挂 `candidate`），但理由要回到正确的那一条。**

- ❌ 撤销"ground truth 是第三方仿真"这条（那是另一篇论文的性质）。
  E5 引用的是**有实验演示**的论文，作为实证锚**名副其实**。
- ✅ 保留 v0.9.56 / v0.9.57 的**实测**依据：两条方法学独立的路线
  （2D-EIM 本征模展开 EME / 2D TEz 全场时域 FDTD）在同一离散结构上把它判在
  ~4 dB 量级，且**两法分歧本身（0.23–0.99 dB）就已超过 tol=0.1 dB** ⇒ 不可判。
- ⚠️ 同时撤销上一稿"原文 L=6.6 µm 仅 0.32 L_π 成像未完成"那条**错误论据**——
  它属于被错认的另一篇器件，与 E5 无关（且即便对那篇，级次也取错了，
  应为 order=0 的 3L_π/8 ≈ 7.82 µm）。

⇒ **净效应：E5 结论不变（保持自证桩），但撤掉两条错误论据，只留实测那一条。**

## 五、遗留项

- `geometry` 仍**缺 `W_mmi_um` / `L_mmi_um`**（"2.8×27" 只在 `device` 自由文本里）。
  这是 roadmap C2 的实证：**结构化几何不全**，建议补录（**值就是原文的 2.8 / 27**）。
- `w_core_um = 0.5` 未从原文核实（正文付费墙）；220 nm SOI 单模典型值，合理但未证实。
- 若要真正接上 E5，仍需 3D 矢量模型（2D-EIM 在 220 nm 高对比 SOI 上失真过大）。
