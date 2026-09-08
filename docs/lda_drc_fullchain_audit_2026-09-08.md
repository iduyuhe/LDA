# LDA · DRC 全链路收口确认（盘点式）· v0.9.60

日期：2026-09-08　｜　范围：设计 → 仿真 → 版图 → **DRC / LVS / 工艺角 / 几何寄生** 四环节
方法：**实测生产代码**（不是读代码下结论），每条正向判据配反向个案

---

## 0. 一句话结论

四环节**都在 CI 内**（7 条相关 smoke 全部登记在 `CORE_SMOKES`），但**「全绿」不等于「收口」**：
盘点实测抓出 **3 处几何级 DRC 判据失真**（2 假绿 + 1 假红）与 **2 处流片链缺口**（几何级 DRC 从未进管道、
性能工艺角从未进管道）。本轮全部修复/补齐，新增 2 条 smoke（26 判据）钉死，CI core 135 → **137**。

---

## 1. 盘点底账：四环节的 CI 登记与覆盖形态

| 环节 | 生产模块 | CI smoke（均在 core） | 覆盖形态 | 结论 |
|---|---|---|---|---|
| **DRC（参数级）** | `lda_l2/drc.py` | `run_drc_smoke` / `run_drc_pdk_smoke` / `run_drc_fix_smoke` | 器件窗口参数 vs PDK 规则（min_width / min_bend_R / min_space / max_split） | ✅ 齐备（含 4 类反向） |
| **DRC（几何级）** | `lda_l2/gds_drc.py` | `run_gdsfactory_bridge_smoke`（仅 2 处调用） | 真实 GDS 多边形最小线宽/间距/面积 | ⚠️ **判据失真 3 处**（本轮修）+ **从未进流片管道**（本轮补） |
| **LVS** | `lda_l2/lvs.py` + `lda_harness/lvs_anchor.py` | `run_lvs_smoke`（30+ 判据）/ `run_lvs_cross_equiv_smoke` | 版图网表由布线几何独立恢复 → 集合比对；S9/S10 锚；多层；红线零 LLM | ✅ 齐备且最扎实 |
| **工艺角（规则角）** | `lda_pdk/tapeout_pipeline.PROCESS_CORNERS` | `run_tapeout_smoke` | **缩放参数后复检 DRC**（不是性能） | ✅ 有，但**只是规则角** |
| **工艺角（性能角）** | `lda_pdk/corner_performance.py` | `run_corner_performance_smoke` | 角缩放后重算锚指标（FSR / f01）+ 死标量 tol | ⚠️ 有独立 smoke，但**从未接进流片管道**（本轮补） |
| **几何寄生** | `lda_l2/parasitic_rc.py` | `run_parasitic_rc_smoke` | R=R□×长/宽、C=平行板×面积；护栏 1kΩ / 1pF | ✅ 齐备（诚实标注非 foundry 级） |

流片管道 `tapeout_pipeline` 的段位：S1+S2 参数级 DRC → S3 规则工艺角 → **S3.5 寄生** → **S3.6 几何 DRC（本轮新增）**
→ **S3b 性能角（本轮新增）** → S4 LVS → S5 实测回流。

**关键发现（本轮起因）**：`run_tapeout_smoke.py` 只覆盖 S1–S3 与 S5 接口，**S3.5 / S4 的「在管道里真跑起来」
没有端到端断言**——它们各自有独立 smoke，但「管道接对了没有」此前无人测。

---

## 2. 抓出的 3 处几何 DRC 判据失真（都是实测，不是推断）

### 失真 ① ｜ 最小线宽度量把「多边形细分步长」当成线宽 ⇒ **假红**

`_poly_width` 旧实现 = 相邻顶点最小距离。SymmetricYBranch 的 boundary 沿 x 以 **0.039 µm** 步长离散（67 点），
旧度量报「最小边 0.039 µm < 0.12 µm」——而实际波导宽 **0.5 µm**。

- 实证：`drc_from_library()` 说 5/5 器件全过参数级 DRC，但真实 GDS 几何里 Y 分支被判违规。
- 这正是「参数级全绿 ≠ 版图合规」的反面教训：**度量本身错了，会反过来制造假红**。

**修**：改为**凸包最小平行带宽度**（标准定义，对凸多边形必在某条边处取到）。
- 细线矩形 5×0.04 → **0.040 µm**（真违规照抓）
- 锥形/梯形波导 0.5 µm 宽 → ≈0.65 µm（细分步长不再参与，假红消除）
- 诚实边界：凹多边形的凸包会填平凹口 ⇒ 该值是**上界**，报告里 `width_note` 显式标注。

### 失真 ② ｜ `min_width_ok` / `min_spacing_ok` 两个标志**恒为 True** ⇒ **假绿**

```python
# 旧实现
"min_width_ok":   all(not v.startswith(("PATH 线宽", "多边形最小边")) for v in violations),
"min_spacing_ok": not any(v.startswith((".*↔",)) for v in violations),
```
违规字符串实际以「**结构名: **」开头 ⇒ `startswith` 永不匹配；`min_spacing_ok` 更把**正则** `".*↔"`
当字面量传给 `startswith` ⇒ 同样永不匹配。

- 实测：构造 2 条线宽违规 + 1 条间距违规，`all_pass=False` 但两个标志**仍报 True**。
- 危害当时为零（全仓无消费者），但这是**定时炸弹**——任何人按语义取用就会拿到假绿。典型的「标签 ≠ 行为」。

**修**：违规改为**分类累积**（`w_viol` / `sp_viol` / `a_viol`），标志与 `violations` 同源，另加
`n_*_violations` 计数。新 smoke ⑤ 显式断言「标志 ⟺ 计数 == 0」自洽。

### 失真 ③ ｜ 间距检查的剪枝条件把真违规剪掉 ⇒ **漏检**

旧剪枝：**只查 bbox 重叠的元素对**。可是**间距违规恰恰发生在「不重叠但过近」的元素之间**
（bbox 一重叠通常已是相交/短路）。实测两块间距 **0.03 µm** 的图形 → `n_spacing_violations = 0`，漏检。

**修**：剪枝改为 **bbox 外扩 `min_spacing` 后相交**才保留（网格分桶同步外扩）。数学上保证
「距离 < min_sp 的对」无一漏检，同时仍剪掉远距对、保留 O(n) 网格加速。
影响面复核：`run_gdsfactory_bridge / gds / chip_layout / tapeout / hier_gds / drc / drc_pdk` 七条 smoke 全部 EXIT=0，零回归。

---

## 3. 补齐的 2 处流片链缺口

### 缺口 A ｜ 流片管道里**没有几何级 DRC**

传了 GDS 也只做寄生（S3.5），不查多边形的最小线宽/间距/面积。新增 **S3.6**：
- 传 `gds` → 实跑 `check_geometry`，结果写入 `TapeoutResult.geometry_drc_result`（`tapeout_to_dict` 同步输出）
- **进 `accepted` 硬门**（实测 5 类器件真实 GDS 全 PASS，不会误拒）
- 🔴 **零元素判 FAIL**：层次化 GDS 若未展开引用（v0.9.33 P0-1 血案：250k 元素被 AREF 压成 1 条记录），
  解析出 0 元素、什么也没查却 `all_pass=True` 就是**假绿**。此处显式判 FAIL + 诚实标注「无法判定」，宁红不假绿。

### 缺口 B ｜ 管道里的「工艺角」**只是规则角，不是性能角**

`PROCESS_CORNERS` 做的是「缩放 width/gap/n 后复检 DRC」，**不评估性能指标漂移**；
而 `corner_performance`（FSR/f01 随角落漂移 + 死标量 tol）从未接进管道。新增 **S3b**：
- 可选参数 `perf_cases=[{device, bid, params, tol_pct, domain}]`，缺省 None 诚实跳过
- 未登记 bid / 执行异常 → **显式记 `error`，不静默**，且阻断 `accepted`

### 语义钉死：几何寄生越界**不进** `accepted` 硬门

`accepted = drc_ok and corners_ok and lvs_ok and geom_ok and perf_ok` —— **寄生不在其中**（设计侧几何护栏，
不替代 foundry 签核）。这是既有取舍，本轮用 smoke ⑧ 显式钉死（实测 R=2000 Ω 越界但 accepted 仍 True），
防止后人误读或误改。

---

## 4. 新增护栏（CI core 135 → 137）

| smoke | 判据数 | 实测耗时 | 钉住什么 |
|---|---|---|---|
| `run_gds_drc_semantics_smoke.py` | 11 | 0.18 s | ①细分步长≠线宽 ①-r 旧度量确会误报（反向）②真细线 0.040 µm ③小面积 ④间距 0.03 µm ⑤标志/计数自洽 ⑥凹形上界诚实标注 ⑦零元素不假称已查 ⑧PATH 声明线宽 |
| `run_tapeout_fullchain_smoke.py` | 15 | 0.23 s | ①五段全实跑 ACCEPT ②几何违规→FAIL 且阻断 ③零元素→FAIL（防 v0.9.33 假绿）④LVS 错连→REJECT ⑤性能角收紧 tol→FAIL ⑥未登记 bid→不静默 ⑦不传输入→诚实 SKIP ⑧寄生越界不进硬门（语义钉死）⑨`tapeout_to_dict` 契约 |

每条正向判据都配反向个案——**护栏必须证明自己会响**。

---

## 5. 诚实边界（不越界声称）

- 几何级 DRC 是**主权几何内核快查**（凸包最小平行带 / 段距 / bbox 面积），**不是 foundry 签核**；
  凹多边形的宽度是上界，可能高估（已在 `width_note` 标注，不假称精确覆盖）。
- 间距检查只在**相邻元素对**（外扩 bbox 相交者）间做，全局最小间距不做全量 O(n²) 扫描。
- 寄生估算为**一阶近似**（R□×长/宽、平行板电容），非 foundry 工艺级 PEX。
- PDK 仍是公开工艺参数示例（真实 NDA-PDK 属发动期），`honest_note` 每轮如实写明。
- 本轮**未改动** 52 锚 / 三分类 26/1/25 / 任何 golden、tol、物理判据。

---

## 6. 遗留（不在本轮）

1. `BraggMirror` 的 `layout_elements` 抛 `ValueError: 暂不支持导出 kind` ⇒ 该器件**无法产出 GDS**，
   因而也进不了几何级 DRC / 寄生（参数级 DRC 覆盖它）。要补几何导出。
2. E5 语料 `geometry` 仍缺 `W_mmi_um` / `L_mmi_um`（roadmap C2），原文已核实为 2.8 / 27 µm，待补。
3. 几何 DRC 的**同一多边形内部**非相邻边间距（如分叉结构 V 形缺口）尚未检查——凹形按凸包近似会高估，
   需要中轴变换类度量才精确，未在本轮引入。
