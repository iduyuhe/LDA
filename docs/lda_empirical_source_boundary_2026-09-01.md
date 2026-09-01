# LDA 实证锚「来源边界」规范与首次溯源审计（D-63）

日期：2026-09-01 · 决策人：杜玉河 · 执行：AI
版本：v0.9.8

---

## 一、来源边界（决策原文）

> **仅限 ①公开论文 ②公开 datasheet ③公开测量数据集，要求必须可公开溯源。**

这条边界的目的：实证大数据锚是 LDA 验证红线的**第二道非 AI ground**（第一道是物理定律锚）。
它的全部价值在于「第三方可独立复验」——一旦来源不可追溯，实证锚就退化成自证桩，
红线被稀释。所以边界必须**机器可判**，不能靠主观描述。

### 排除项（明确不收）

| 排除 | 理由 |
|---|---|
| 晶圆厂 NDA 实测数据 | 不可公开溯源（属发动期，管道已备好，数据到位后流入） |
| 内部未公开测量 | 同上 |
| 纯仿真结果（FDTD/FEM 计算值） | 属「另一套计算意见」，不是测量事实 |
| 无出处的"文献量级"描述 | 无法被第三方复验 |

---

## 二、溯源分级标准（机器可判，非主观）

`lda/lda_harness/provenance.py` —— 纯字符串解析，无网络 I/O、无 AI 判断。

| 级别 | 判定条件 | 是否可作 golden 进判决 |
|---|---|---|
| **A 级 · 可公开溯源** | citation 含 **DOI** / **arXiv 编号** / **公开 http(s) URL** 之一 | ✅ 可以 |
| **B 级 · 量级参考** | 有 citation 文本但无上述定位符（如"XX 文献量级"） | ❌ 禁止 |
| **X 级 · 无来源** | citation 缺失 | ❌ 拒收（既有门禁） |

补充规则：指向内网/回环/私有地址段的 URL **不算公开**（`_is_public_url` 拦截）。

### 门禁落点（三处，缺一不可）

1. **新语料准入**（`lda_pdk/empirical.py:submit_measurement`）：非 A 级一律 rejected。
2. **golden 取值**（`lda_harness/empirical_bank.py:EmpiricalAnchor.resolve`）：
   `require_traceable=True`（默认）时 B 级语料直接拒绝返回 golden。
3. **判决路径**（`harness.py` / `verification_adapters.py`）：
   按锚题声明类型传参——A 级强制溯源、B 级显式放行但标注，且不计入可溯源计数。

---

## 三、首次审计结果（真实底数）

审计器：`python lda/run_provenance_audit.py --json reports/provenance_audit.json`

### 语料库

| 指标 | 整改前 | D-63/D-64 整改后 | **D-66 逐字核实后** |
|---|---|---|---|
| 语料总数 | 23 | 29 | **30** |
| A 级（可公开溯源） | 18（78.3%） | 24（82.8%） | **30（100%）** |
| B 级（禁止进判决） | 5 | 5 | **0** |
| X 级 | 0 | 0 | **0** |

### 实证锚题（E1–E7）

| 锚题 | 语料 | golden | 级别 | 定位符 |
|---|---|---|---|---|
| E1 | E-SOI-NG-220 | 4.18 | A ✅ | DOI 10.48550/arXiv.2011.03273 |
| E2 | E-SIN-NG-300 | 1.892 | A ✅ | DOI 10.3390/s17092088 |
| E3 | E-TBOX-FSR-TM | 10.44 | A ✅ | opg.optica.org 公开 URL |
| E4 | E-SOI-CROSS-IL | 0.18 | A ✅ | DOI 10.1109/LPT.2013.2241049 |
| E5 | E-MMI-1X2-EL | 0.05 | A ✅ | DOI 10.1117/1.OE.59.10.105102 |
| E6 | E-SIN-PL-800 | 0.087 | A ✅ | DOI 10.3788/gzxb20245309.0913002 |
| E7 | E-SOI-CROSS-XT | −41 | A ✅ | DOI 10.1109/LPT.2013.2241049 |

**可溯源实证锚题：7 / 7**（D-66 后 B 级清零，见第六节）。

---

## 四、审计暴露的两个重大问题（本次的核心发现）

### 问题 1：E3 是「物理定律/仿真值冒充实测锚」

审计前 E3 的 golden = `FSR 9.15 nm`，来源标注"环形谐振器公开测试数据"。核验发现：

```
FSR = λ²/(n_g · 2πR) = 1550² / (4.18 × 2π×10000) = 2402500 / 262637 = 9.147 nm
```

**9.15 完全可由其 `default_params`（R=10μm, n_g=4.18, λ=1550nm）闭式算出** —— 它不是测量值，
是解析公式值。进一步追查 `n_g=4.18` 的来源：出自 Opt. Express 23, 31736，
该值是 **2D FDTD 仿真结果**，不是实测。

即：E3 实际是「仿真参数 + 解析公式」在实证锚名下运行。**已整改**：
golden 换成真实实测 **10.44 nm**（Sridaran & Bhave, Opt. Express 18(4) 3850 (2010)，
R=7.5μm 环扫频实测峰间距），并同步器件参数为论文真实参数。

整改后 E3 才具备实证锚应有的形态 —— **实测 ↔ 解析交叉验证**：
实测 10.44 nm vs 解析 λ²/(n_g·2πR)=10.464 nm，差 0.024 nm（≤tol 0.1）。
golden 取自测量，解析式退化为被验证对象，而非 golden 本身。

### 问题 2：n_eff 本身几乎不直接测量，E1/E2 的锚设计存在概念缺陷

核实 Sridaran & Bhave (2010) 时确认：该文 n_eff 是 **COMSOL FEM 计算值**（quasi-TE 2.405、
quasi-TM 1.862），非测量值。这不是孤例——**n_eff 在工程上通常是导出量**：
要么是仿真算的，要么由 MZI 干涉/谐振波长反演得到。真正能被直接测量的是
**群折射率 n_g** 和 **FSR**。

因此 E1/E2 用 n_eff 作"实测锚"，在概念上就不成立。目前因无公开可溯源的
n_eff 实测源，二者已标为 B 级待溯源（`anchor=empirical_unverified`），
**仍走同一死标量判决，但显式不计入可溯源实证锚计数**。

**建议**：将 E1/E2 从 `n_eff` 改为 `n_g`（群折射率）锚 —— n_g 可由 MZI 非平衡
干涉 / 谐振腔 FSR 反演直接实测，公开文献中这类实测数据充足。

> **✅ 已拍板并执行（D-66，2026-09-01）**：杜先生确认改判 n_g 锚。执行结果见第六节，
> E1/E2 已升 A 级，语料库 B 级清零（30/30 全 A）。

---

## 四·补：D-66 逐字核实中发现的三个「差点踩进去」的坑

本节记录整改执行过程中的真实发现，**这些是方法论教训，价值高于结果本身**。

### 坑 1：差点把仿真值当实测值（E-YBRANCH-LOSS 候选来源）

为给 Y-branch 找实测出处时，arXiv:1909.09538 中出现
`"−3.05 dB ~ −3.15 dB"`，看似完美的实测插损。逐字核对上下文后发现**前文一句**：

> `"This simulation is shown in Fig. 5"`

即这是**仿真结果**。**已排除**。教训：只看数值不看上下文，会把第一性原理模型的
输出当成第二道 ground——两道 ground 短路，判决即自证。

### 坑 2：metric 量纲陷阱（3.4 dB vs 0.28 dB）

原 `E-YBRANCH-LOSS` golden = **3.4 dB**，名为 `split_loss_dB`（分支插损）；
文献实测的是 **0.28 ± 0.02 dB 过量损耗（excess loss）**。两者**不是同一个量**：

- 3.01 dB 是 1×2 功率均分的**几何必然**（−10·log₁₀0.5），任何理想分束器都有，
  **不是器件品质指标、也不是被测量的量**；
- 0.28 dB 才是真正反映工艺/设计水平的过量损耗。

若直接拿 3.4 对 0.28，会得到一个量级的"偏差"，但那 **不是模型错了，是量纲错了**。
已统一为 `excess_loss_dB`（与既有 E-MMI-1X2-EL 口径一致），
`loss_engines.engine_ybranch_split` 同步剔除 3.0 dB 常数项。

### 坑 3：原 golden 本身就是错值（E-SOI-NEFF-220 的 2.63）

原 `E-SOI-NEFF-220` 声称 n_eff = 2.63 ± 0.02 @1550 nm。逐字核实：
文献与 **3 个独立模式求解器**一致给出 500×220 SOI TE0 的 n_eff = **2.44 ~ 2.46**。
2.63 实为 λ≈1.39 µm 处的取值，偏离 **0.19**（为其自称 ±0.02 的近 10 倍）。

这类错误在"看上去合理"的数值上最难发现——**它不会报错，只会让所有对照结果
系统性偏移**。已改判为同文献的 n_g 实测锚（4.18，由实测 FSR=8.6 nm 反演），
并在语料 `note` 字段保留原值存疑的证据链（不静默丢弃）。

---

## 五、B 级语料整改清单（5 条）—— **D-66 已全部关闭 ✅**

> 整改纪律：**逐字核实**（找到原文、核对数值与上下文），**不编造 DOI**，
> **找不到就保持 B 级**。5 条中 3 条找到精确可溯源实测并按文献值替换，
> 2 条因原 metric 无可溯源实测出处而**改判量纲**（n_eff → n_g）。

| 原语料 ID | 原 metric / 值 | 处置 | 新 ID / 新值 | 可溯源出处 |
|---|---|---|---|---|
| E-SOI-NEFF-220 | n_eff 2.63（**经核实为错值**） | 改判 n_g 锚 | **E-SOI-NG-220** / n_g 4.18±0.05 | DOI 10.48550/arXiv.2011.03273 |
| E-SIN-NEFF-300 | n_eff 1.53 | 改判 n_g 锚 + 按文献照实改写几何 | **E-SIN-NG-1200** / n_g 2.2834±0.05 | DOI 10.3390/coatings10040309 |
| E-YBRANCH-LOSS | split_loss_dB 3.4（量纲不符） | 改判实测**过量损耗** | E-YBRANCH-LOSS / excess_loss_dB 0.28±0.02 | DOI 10.1364/OE.21.001310 |
| E-RING-FSR | FSR_nm 9.15（**解析反算值**） | 换文献实测值 | E-RING-FSR / FSR_nm 8.6±0.1 | arXiv:2011.03273（racetrack L=66.8 µm） |
| E-GRATING-EFF | coupling_eff 0.45（无出处） | 换文献实测值 | E-GRATING-EFF / coupling_eff 0.42±0.05 | DOI 10.1063/1.3304791 |

### 逐字引用（证据链，均为原文照抄）

| 语料 | 原文逐字引用 |
|---|---|
| E-SOI-NG-220 / E-RING-FSR | `"The resonator has the shape of a racetrack, it is 66.8 um long and its free spectral range (FSR) is 8.6 nm, from which we infer that its group index is 4.18."` |
| E-SIN-NG-1200 | `"The free spectral range (FSR) measured from the transmission spectra given in Figure 4b was estimated as 1.61 nm that resulted in the effective group index ng = 2.2834."` |
| E-YBRANCH-LOSS | `"Measured average insertion loss is 0.28 ± 0.02 dB, uniform across an 8-inch wafer."` |
| E-GRATING-EFF | `"A peak coupling efficiency of 42% at 1550 nm and 1 dB bandwidth of 37 nm, as well as a low back reflection, are achieved."` |

### 自洽校验

- E-SOI-NG-220：λ²/(n_g·L) = 1547.6²/(4.18×66.8×10³) = **8.59 nm** ≈ 实测 8.6 nm ✅
- E-SIN-NG-1200：λ²/(n_g·L) = 1550²/(2.2834×640.3×10³) = **1.64 nm** ≈ 实测 1.61 nm ✅

### 如实披露（不掩饰的缺陷）

1. **E-GRATING-EFF 结构不同源**：文献器件为**全刻蚀光子晶体孔阵**（孔径约 143 nm），
   与本引擎的**参数化周期光栅**并非同一结构。该语料仅作设计引擎的量级对照，
   **geometry 不构成 golden 判决输入**。
2. **n_g 由 FSR 反演得到**（E-SOI-NG-220 / E-SIN-NG-1200）：属"实测 FSR + 闭式
   换算"，比纯仿真强（FSR 是直接测量量），但**弱于 n_g 的直接测量**
   （如 E-SIN-NG-300 的 OFDR 群延迟法）。已在语料 `method` 字段逐条标注反演路径。
3. **E-YBRANCH-LOSS 模型粗糙度暴露**：引擎默认唯象系数 c1=0.004 dB/deg² 给 0.4 dB，
   实测 0.28 dB，rel≈43%。**不做拟合回算**（用被验证量标定验证量 = 循环自证），
   改设 50% 防回归护栏，待真实 PDK 工艺标定（发动期）。

---

## 六、本次新增语料（6 条，全部 A 级）

来源（单一可公开溯源文献，URL 定位符，未推断 DOI）：
**S. Sridaran & S. A. Bhave, "Nanophotonic devices on thin buried oxide Silicon-On-Insulator substrates,"
Opt. Express 18(4), 3850–3857 (2010)**
<https://opg.optica.org/oe/viewmedia.cfm?URI=oe-18-4-3850>

| 语料 ID | metric | 实测值 | 方法 |
|---|---|---|---|
| E-TBOX-FSR-TM | FSR_nm | 10.44 | 扫频透射谱峰间距（反算 n_g=4.92 @1557.6nm） |
| E-TBOX-FSR-TE | FSR_nm | 11.15 | 透射谱峰间距（n_g=4.54） |
| E-TBOX-PL-TE | propagation_loss_dBcm | 3.88 | cut-back 截断法线性拟合 |
| E-TBOX-PL-TM | propagation_loss_dBcm | 5.06 | cut-back 截断法线性拟合 |
| E-TBOX-QL-TM | loaded_Q | 46,500 | Lorentzian 拟合（消光比 14 dB） |
| E-TBOX-QI-TE | intrinsic_Q | 148,000 | 透射谱谐振模型拟合 |

器件条件：SOITEC SOI 250nm 器件层 / 400nm 薄埋氧、波导 450×250nm、R=7.5μm 环。
（几何参数已如实记入 `geometry` 字段，与 E1/E3 原 500×220nm 标准 SOI 不同，不可混用。）

---

## 七、改动清单

| 文件 | 改动 |
|---|---|
| `lda/lda_harness/provenance.py` | **新增** 溯源分级（A/B/X 判定 + 批量审计），纯字符串解析 |
| `lda/lda_harness/seed_empirical.json` | 新增 6 条 A 级实测语料 |
| `lda/lda_harness/benchmarks.py` | E3 换真实实测 golden（9.15→10.44）+ 参数同步；E1/E2 改标 `empirical_unverified` |
| `lda/lda_harness/empirical_bank.py` | 新增 `source_url` 字段、`traceability()`；`resolve` 加 `require_traceable` 门禁 |
| `lda/lda_harness/verification_adapters.py` | 识别 `empirical_unverified` 分支，按类型传门禁参数 |
| `lda/lda_harness/harness.py` | 3 处分支判断 + resolve 传参同步（否则 B 级漏判/被挡） |
| `lda/lda_pdk/empirical.py` | 新增 `source_url`；`submit_measurement` 加溯源硬门禁 |
| `lda/lda_webui/app.py` | E 题 golden 展示按类型传参 + 输出 `traceable` 字段 |
| `lda/run_provenance_audit.py` | **新增** 独立审计器（CI + 对外披露） |
| `lda/run_empirical_anchor_smoke.py` | 同步门禁：golden 断言、分型断言、4 条溯源门禁用例 |
| `lda/run_empirical_d62_report.py` | 修正过期断言（21→48 题）+ 提交载荷补 URL |
| `lda/run_ci_regression.py` | `run_provenance_audit.py` 入 CORE_SMOKES（82→83） |
| `README.md` | CI core 82→83；实证锚诚实边界段更新为溯源分级事实 |

---

## 八、验证证据

- `run_empirical_anchor_smoke.py`：**23/23 PASS**
  （含实测↔解析交叉验证、B 级挡下 golden、A 级放行、B 级提交被拒）
- `run_provenance_audit.py`：**PASS**（A 级 82.8% ≥ 80% 达标线）
- `run_empirical_d62_report.py`：**6/6 PASS**
- `run_loss_engine_smoke.py`：**6/6 PASS**
- `run_count_consistency_smoke.py`：**OK**（README 计数 83 同步通过）
- `--tag core` 全量回归：见回归报告

---

## 九、遗留与建议

1. **B 级语料 5 条待溯源**（第五节清单）—— 优先级最高的后续工作。
2. **E1/E2 建议改为 n_g（群折射率）锚**（问题 2），需杜先生拍板——这会改变基准定义。
3. **CI 达标线 80% 是初始值**，建议随语料补充逐步上调至 90%+。
4. **实证锚总量仍偏薄**：可溯源实证锚题 5 道 vs 物理定律锚 38 道。
   补的方向建议优先选「可直接测量的量」（FSR、插损、Q 值、响应度、串扰），
   避开 n_eff 这类导出量。
