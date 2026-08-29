# 货架商品化数据抽审报告（首批 10 关键货架）

> 抽审时间：2026-08-29 · 抽审人：AI（供杜先生终审）· 范围：48 个 AI 起草货架中选 10 个关键货架
> 方法：逐项对照 `signal_ref`（货架原始可溯源信号源）与商品化四字段（features/applications/specs/peers），核查**数据一致性 / 诚实标注 / 来源可溯源**三维度
> 结论：**10 项中 6 项 PASS、4 项发现并修正**（1 项数据错误、1 项表述歧义、1 项来源引用不完整、1 项信息可增强）——修正已上线

---

## 一、抽审结论汇总

| 货架 | 对标来源类型 | 数据一致性 | 诚实标注 | 来源可溯源 | 结论 |
|---|---|---|---|---|---|
| IM-QCHIP-INT | IBM/Google 公开架构 | ✅ | ✅ | ✅ | PASS |
| IM-SENSE-RING | 公开学术路线 | ✅ | ✅ | ✅ | PASS |
| IM-WDM-8CH-1D | IEEE 802.3bs 标准 | ✅ | ✅ | ✅ | PASS |
| IM-FTTH-PLC16 | ITU-T G.671 + LuLeey | ✅ | ✅ | ✅ | PASS |
| **IM-CPO-OCS** | UC Berkeley / arXiv | 🟡 表述歧义 | ✅ | 🟡 引用不完整 | **修正** |
| IM-QKD-RX-SHELF | npj QI 2017 期刊 | ✅ | ✅ | ✅ | PASS |
| IM-800G-FR4 | OIF / LightCounting | ✅ | ✅ | ✅ | PASS |
| **IM-RING-MOD** | NVIDIA / TSMC 路线 | 🔴 **数据错误** | ✅ | ✅ | **修正** |
| **IM-AWG-DEMUX** | 市场报告（多口径） | 🟡 单口径展示 | ✅ | ✅ | **修正** |
| **IM-PSR** | OLT 2026 期刊 | 🟡 可增强 | ✅ | ✅ | **修正** |

---

## 二、修正明细（4 项，全部对照 signal_ref 原文）

### 修正 1：IM-RING-MOD —— 数据错误（🔴 最严重）

- **错误**：features/specs 写「带宽密度 0.5→**1+** Tbps/mm 路线」
- **signal_ref 原文**：`TSMC COUPE 2026 量产 200Gbps/lane MRM、带宽密度 0.5→**4** Tbps/mm (2030)`
- **修正**：`0.5→4 Tbps/mm 路线（TSMC COUPE 2030）`（features + specs 两处）
- **性质**：数字抄录错误（1+ → 4），若不修正会在专业读者面前露怯

### 修正 2：IM-CPO-OCS —— 表述歧义 + 引用不完整

- **表述歧义**：specs「矩阵插损：中位 ≤2dB」——把 Polatis（中位 1.4dB）和 Google（≤2dB）两个不同实测值混成一个。修正为分列：`Polatis 中位 1.4dB / Google ≤2dB（实测对标 · 本货架为仿真预期）`
- **引用不完整**：arXiv 编号 `2411` → 补全 `2411.01503`

### 修正 3：IM-AWG-DEMUX —— 市场多口径单列

- **问题**：signal_ref 有 4 个市场口径（AWG MUX/DeMUX、Arrayed Waveguide、QYResearch、Thermal AWG），peers 只列其一，读者无从得知存在多口径
- **修正**：note 补充「多口径并存，取其一：Arrayed $320-570M/2026 CAGR 6.5-11.7%、QYResearch $427M/2032 CAGR 6.9%、Thermal AWG $2.84B/2033 CAGR 9.x%」

### 修正 4：IM-PSR —— 期刊实测指标未入对标

- **问题**：peers 只有结构/功能，signal_ref 中关键的实测指标（TM-to-TE 损耗 0.71dB @1550nm、PER 最差 30.95dB）没进对标表
- **修正**：peers specs 补入两项实测指标（来源 Sama et al. OLT 203(2026) 可溯源）——让对比更有信息量

---

## 三、PASS 项抽查依据（6 项）

| 货架 | 核查要点 | 依据 |
|---|---|---|
| IM-QCHIP-INT | 复用 D-46×D-47 已验证框架 | signal_ref 原文一致；peers 保真度区间与公开披露一致 |
| IM-SENSE-RING | S1/S2/S5/S7 链路预算锚 | signal_ref 原文一致；「公开学术路线」性质诚实（非单一产品规格已标注） |
| IM-WDM-8CH-1D | 信道 IL ≤6.3dB | IEEE 802.3bs FR8/LR8 公开标准信道预算一致 |
| IM-FTTH-PLC16 | 1×16 ≤14.0dB | ITU-T G.671 / GR-1209 公开典型值一致，LuLeey 实测一致性已标 |
| IM-QKD-RX-SHELF | Bob 芯片 ≤8dB | npj QI 2017 e1700262 实测值一致 |
| IM-800G-FR4 | 4×200G PAM4 / $400-480 | OIF 路线 + LightCounting 市场数据一致 |

---

## 四、抽审方法与剩余建议

**抽审发现率**：10 个货架中 4 个有可改进项（40%）——说明 AI 起草数据**不能直接全信**，抽审必要。但**未发现编造来源或虚构对标对象**（全部 peers 的 vendor/product/source 均能在 signal_ref 找到依据），诚实边界整体可靠。

**对剩余 38 个未抽审货架的建议**：
1. **按类型抽样**：市场报告类对标（约 20 个）建议再抽 5 个——多口径标注是否齐全
2. **按热点抽样**：CPO/800G/1.6T 相关货架（约 10 个）建议再抽 3 个——数字准确性
3. **终审权在杜先生**：本报告为 AI 抽审，关键货架（尤其对外展示的开放货架）建议杜先生抽看 3~5 个确认

---

*本报告基于仓库实际数据（signal_ref 与 _MERCH 逐项对比），修正已入代码并部署。未含不可验证推断。*
