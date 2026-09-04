# P0-1 交付报告：层次化 GDS 导出产品化

**日期**：2026-09-04 · **版本**：v0.9.32 → **v0.9.33** · **前置**：P0-0（IO 光栅定位缺陷修复）

---

## 1. 结论（一句话）

层次化导出已产品化并默认开启。**CPO 250k：897,600 元素 / 97.45 MB → 331 元素 / 36.0 KB，降幅 99.96%**，与 POC 完全一致；展开后几何数与 flat 分毫不差，**DRC/LVS 判决不受影响**。

---

## 2. 实测结果

### CPO 250,240 器件全量

| 指标 | flat | 层次化 | 降幅 |
|---|---|---|---|
| GDS 元素 | 897,600 | **331** | **99.96%** |
| GDS 体积 | 97.45 MB | **36.0 KB** | **99.96%** |

结构：**1 个 `CHANNEL` cell（330 元素）+ 1 条 AREF 记录**。

自动检测结果（无硬编码）：周期 **p = 92** 器件 · 阵列 **4 × 680** · **2,720** 个实例 · 步进 (3289.88, 28.99) µm。

| 验证项 | 结果 |
|---|---|
| 展开几何数 ≡ flat 元素数 | **897,600 = 897,600** ✅ |
| 抽样等价（9 实例 / 2,970 几何） | ≤ **1 DBU（1 nm）** ✅ |
| flat 基线未漂移 | 897,600 元素 / 97.45 MB ✅ |

### CPO 小阵列（384 器件）

1,616 → 203 元素（降 **87.4%**），展开 1,616 ≡ flat 1,616。

降幅随实例数放大 ≈ 1 − 1/n_inst：4 实例 74.9% · 8 实例 87.4% · 2,720 实例 99.96%。**GDS 体积从 O(N) 变成 O(1)**。

---

## 3. 三处架构改造

| # | 改造 | 说明 |
|---|---|---|
| 1 | `gds_export.aref()` | GDSII AREF 原语（0x0B），标准三点式 XY：P1=原点 / P2=原点+dx·nx / P3=原点+dy·ny |
| 2 | `parse_gds_polygons(expand_refs=True)` | 引用展开，支持嵌套 + 环检测 |
| 3 | `chip_layout_export` 拆出几何层 | `device_geom_of` / `io_grating_geoms` / `route_geoms` + `Geom` 元组 |

第 3 项是刻意的——**P0-0 的根因正是同一段逻辑被抄两遍、错得一样**。现在 flat 与层次化共用同一份几何生成，`_encode_geom` 是唯一编码出口。

### 🔴 为何解析器必须默认展开引用

不展开的话，层次化 GDS 在 `gds_drc` / `parasitic_rc` 眼里**只有 1 条 AREF 记录，顶层真实几何为 0** ⇒ **DRC 假绿**。宁可解析慢，不可假绿。

对不含引用的既有 flat 版图，展开逻辑空转，输出 **bit-exact 不变**（零回归已验）。

---

## 4. 🔴 产品化补了 POC 缺的一环

POC 在 CPO 上验证通过，但**该案例没有跨通道布线、也没有非 base 的 IO**——所以 POC 只需处理 cell 内几何。通用设计（任意网表）必然存在不属于任何实例的几何。

本版显式区分：

- **实例内几何**（器件、实例内布线、实例器件上的 IO）⇒ 由 cell 展开覆盖；
- **跨实例或非对称几何** ⇒ 留在 TOP 单次绘制。

并对每条非 base 的布线 / IO 做**对称性校验**（相对几何是否在 base 中出现过），非对称项自动降级到 TOP。不做这个就会**静默丢失几何**——比不压缩更糟。

> **第一版我在这里判错了**：把「属于其他实例」的 IO 也加进了 TOP，展开多出 474 个几何。是 `flat = 1320 = 330 × 4` 这个数字暴露了 CPO 完全对称、本不该有 TOP 几何。修正后 `top_geoms = 0`。

---

## 5. 导出接口

```python
r = export_chip_gds(link, placement, routes)                    # 层次化（默认）
r = export_chip_gds(link, placement, routes, with_hierarchy=False)  # 强制 flat
r["hierarchy"]  # {'applied': True, 'reason': 'ok', 'n_instances': 2720,
                #  'period': 92, 'cell_elements': 330, 'top_elements': 0,
                #  'use_aref': True, 'array': [4, 680],
                #  'pitch_um': [3289.8832, 28.9886], 'n_elements_flat': 897600}
```

检测失败**自动回退 flat**，并在 `reason` 写明原因（`no_repeating_cell` / `detect_error:...`），**绝不静默**。检测异常被 `try/except` 兜住，不向上传播。

**DRC / LVS 判决完全不受影响**（层次化只改编码，不改判决）——由护栏判据 G 钉死。

---

## 6. 新护栏 `run_hier_gds_smoke.py`（17/17 PASS，CI core 92→93）

| 判据 | 内容 |
|---|---|
| A | 规则阵列上层次化生效 + 降幅 > 50% |
| B | **几何零丢失**：展开几何数 ≡ flat 元素数 |
| C | 展开与 flat 逐元素数值等价（≤1 DBU） |
| D | 非规则设计回退 flat，字节逐位一致，原因非空 |
| E | AREF round-trip：1 条 AREF 展开为 nx×ny 份，位置精确 |
| F | `top_structures` 正确（顶层 = 未被引用者） |
| G | DRC/LVS 判决不受层次化影响 |

### 反向测试（证明会响）

故意从 cell 删一个几何 ⇒ 判据精确报 **74 个缺失**。

这一条很关键：**删几何后元素数更小、看起来更"压缩成功"**，只看降幅会得到假绿。只有 B/C 判据抓得住。

---

## 7. 两处踩坑记录

1. **命名冲突**：原拟命名 `run_hierarchy_smoke.py`，但该名**已被 Merge-3b 层级 IR（子系统 flatten）占用**，两者是不同事物。覆盖会造成不可逆损失，已改名 `run_hier_gds_smoke.py`。
   > **新建 smoke 前必须先查重名。**

2. **几何重复计数**：下游按「所有结构求和」统计几何，会把 cell 自身那份**重复计入**（实测 202 + 1616 = 1818，真实 1616）。解析器新增 `top_structures` 字段供下游正确取用。

3. **shell 反引号**：用 `python -c "..."` 写含反引号的 README 文本，反引号被 bash 当作命令替换吃掉，第 7 行写坏。已改为脚本文件写入并修复。

4. **回归首轮 90/93，三个红灯两个是自己撞的**：层次化改变了 GDS 结构名（`CHIP` → `CHANNEL` + `TOP`），导致 `run_io_grating_offset_smoke` 的 `["structures"]["CHIP"]` KeyError、`run_cpo_array_scale_smoke` 的结构计数断言失效。已统一改用 `top_structures` + 展开几何计数。
   > **改动编码结构时，下游凡按结构名/元素数断言的地方都要同步。** 本次两条 smoke 恰好守住，说明护栏有效。

---

## 7b. 🔴 附带修复：`/api/ecosystem` 无鉴权 GET 每次请求全量重跑 48 道锚（15.3s）

第三个红灯 `run_webui_api_smoke.py` 追下去，挖出一个**与层次化无关的既有缺陷**：

| 项 | 实测 |
|---|---|
| 端点属性 | **无鉴权公开 GET** |
| 单次耗时 | **15.27s**（E2 半矢量本征解 11.99s + B8 2.69s，其余 46 道合计仅 0.57s） |
| smoke 超时 | 15s |
| 风险 | `ThreadingHTTPServer` 下一个请求占满线程 15s，并发即打爆进程 |

与 `/api/cpo_array`、`/api/benchmark_crosscheck` 属同一类敞口——**此前那轮 DoS 加固漏掉了本端点**。

**为何此前一直是绿的**：15.27s vs 15s 超时正好卡在边界，v0.9.32 那轮侥幸跑进 15s。⇒ **这是 flaky 测试，不是回归。**

🔴 **本轮最重要的工程教训**：「某端点能在 N 秒内跑完」是**时序断言，不是性质断言**——它随机器负载随机翻红，同时掩盖真实缺陷。正确做法是先预热、再断言性质（缓存是否生效）。

**修复**：抽出 `_eco_harness_snapshot()`（串行锁 + TTL 300s 缓存，锁忙即 1s 内 429）；**只缓存 harness 部分**（`community` 是活数据，缓存整包会让刚提交的提案缺席）；响应新增 `harness.cached` / `compute_ms` / `cache_ttl_s` 如实标注。

**smoke 判据升级**：新增 `HEAVY_WARMUP`（含冷启动 9.1s 的 `/api/benchmark_crosscheck`，同类问题）先预热；新增 `_check_heavy_get_caches()` 断言 `cached is True` 且响应 <3s。

**反向测试**：TTL 注入为 0 ⇒ 立即 **4 个 FAIL**（`cached is True` 不成立、`耗时 14.68s ≥ 3.0s`）；恢复后 88 PASS / 0 FAIL。

---

## 8. 变更文件

| 文件 | 变更 |
|---|---|
| `lda/lda_l2/hierarchy.py` | **新增**：层次化检测 + 编码 + 展开 |
| `lda/lda_l2/gds_export.py` | 新增 `aref()`、`_expand_references()`、`top_structures`；`parse_gds` 认 AREF |
| `lda/lda_l2/chip_layout_export.py` | 拆出几何层（`Geom` / `device_geom_of` / `io_grating_geoms` / `route_geoms`）；`export_chip_gds` 加 `with_hierarchy` |
| `lda/run_hier_gds_smoke.py` | **新增**常驻护栏（17 条判据 + 反向测试） |
| `lda/run_cpo_array_smoke.py` | ⑨ 断言改为按展开几何计数（兼容层次化）+ ⑨b/⑨c 等价性与降幅 |
| `lda/run_ci_regression.py` | 登记新 smoke（92→93） |
| `lda/run_io_grating_offset_smoke.py` | 适配层次化结构名（改用 `top_structures`） |
| `lda/run_cpo_array_scale_smoke.py` | ④ 改按展开几何计数 + 新增 ④b 降幅 >99% 判据 |
| `lda/lda_webui/app.py` | 新增 `_eco_harness_snapshot()`（TTL 缓存 + 串行锁）；`/api/ecosystem` 加缓存契约字段 |
| `lda/lda_webui/routes.py` | `h_ecosystem` 锁忙时返回 429（并发护栏），不再 500 |
| `lda/run_webui_api_smoke.py` | 新增 `HEAVY_WARMUP` 预热 + `_check_heavy_get_caches()` 缓存护栏判据 |
| `README.md` / `pyproject.toml` / `CHANGELOG.md` | 版本与账本同步（0.9.33 / CI core 93） |
| `assess_p01_hierarchy_250k.py` | **新增** 250k 全量验证脚本 |
| `docs/lda_hierarchy_poc_2026-09-04.md` | POC 状态更新为已产品化 |

---

## 9. 已知待办

- **P0-2 层次化 LVS**（**收益尚未兑现**）：当前层次化**只压缩 GDS 编码**，LVS 仍走 flat 几何。1M 器件全链 142.7s 里 **LVS 占 90.6%**——真正的规模瓶颈在这里，不在 GDS。
- `route_geoms` 保持既有行为：每条 net 无条件产出一个 PATH，即使点集为空（WDM 有 2 条空 path，GDS 里是无 XY 的畸形记录）。过滤会破坏 bit-exact 基线，待确认下游无依赖后单独清理。
- boundary 的 `rings_um` 多环被展平为单环（P0-0 遗留，已登记在 docstring）。

---

## 10. 下一步

**P0-2 层次化 LVS**——唯一 cell 只检查一次，目标 3.45s → < 1s。这是规模线上**唯一还没兑现收益**的环节，也是 1M 器件全链耗时的主要来源。
