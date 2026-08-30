# 创新超市三档定价策略（D2 落地 · v0.9.1）

> 决策：杜先生 2026-08-30 拍板三档 **¥599 / ¥1999 / ¥4999**，具体货品归档授权 AI 依据市场调研确定
> 落地：`lda/lda_webui/shelf_pricing.py`（分档表）+ `store.base_price()`（定价逻辑）+ `run_innovation_market_smoke`（7 条 CI 护栏）
> 状态：58/58 货架已归档，端到端 `/api/shelf` 实测通过

---

## 一、分档结果

| 档位 | 价格 | 开放货架 | 咨询制 | 定位 |
|---|---|---|---|---|
| **基础档** | ¥599 | 15 | 0 | 标准件 / 成熟普惠 / 开源生态易得 |
| **标准档** | ¥1999 | 18 | 0 | 需工程设计 know-how 的子系统 |
| **高端档** | ¥4999 | 17 | 8（量子咨询制起步价） | 系统级 / 稀缺 / 高客户价值 |

身份折扣叠加：学术 6 折、机构 8.5 折、标准原价。

| 档位 | 标准 | 学术（6 折） | 机构（8.5 折） |
|---|---|---|---|
| 基础 | ¥599 | ¥359.40 | ¥509.15 |
| 标准 | ¥1999 | ¥1199.40 | ¥1699.15 |
| 高端 | ¥4999 | ¥2999.40 | ¥4249.15 |

---

## 二、分档规则（三维，可解释、可复现）

不是拍脑袋归类，每档都有客观判据：

### ① 开源可替代性（第一判据）

核心功能能否由 **gdsfactory 现成标准件**直接拼出。判据来源是项目自己的桥接映射 `lda/lda_l1/gdsfactory_bridge.py:26-38`，现有 8 类：

```
straight / bend_euler / bend_circular / mmi1x2 / mmi2x2 /
coupler / grating_coupler / ring / mzi / y_splitter / taper
```

- 能直接拼出 → 基础档（客户本可免费获得，我们卖的是"省时间"）
- 有零件无成品，需组合设计 → 标准档
- 生态完全无现成，需专业 know-how → 高端档

### ② 技术复杂度

`composition` 基元数 + 是否系统级（多通道 / 多物理场 / 异质集成）。

### ③ 客户价值

对应产品的市场规模与单价：成熟普惠市场（FTTH、100G）→ 低；前沿稀缺赛道（1.6T、CPO、相干、量子）→ 高。

---

## 三、市场依据（2026-08-30 调研）

### 国际 Design House 设计服务报价（JePPIX 平台公开价）

| 服务商 | 服务 | 价格 |
|---|---|---|
| VLC Photonics | Basic support（评审/DRC） | €2,000 |
| VLC Photonics | **Standard cell（PDK 现有 block 布局）** | **€5,500 起** |
| VLC Photonics | Custom cell（含自定义 block） | €11,000 起 |
| Bright Photonics | Custom Design | €11,000 起 |
| Epiphany | Standard Chip Service | €5,000 起 |
| Epiphany | Custom Chip Service | €10,000 起 |

> 学术普遍 5 折。

### 流片成本（2026 国内公开采购数据）

| 类型 | 价格 |
|---|---|
| 硅光无源 MPW | ¥6–8 万 |
| 90nm 有源 MPW | ¥12.8 万 |
| 12 吋有源 MPW | ¥18.9 万 |
| IMEC（国际） | 约 $50,000 / block |

### 定位结论

LDA 三档定价（¥599–4999）是国际设计服务（¥4.3 万–8.6 万）的 **1/10 到 1/100**。

这个差距是**合理的，不是定价过低**——因为性质不同：

- 国际设计服务交付的是**流片级可制造设计**（含 PDK 验证、封装兼容）
- LDA 交付的是**仿真预期·未流片**的预设计 + 死锚验证报告（已在全站诚实标注）

LDA 的真正对标不是设计服务，而是**工程师自研的时间成本**：一个 800G DR8 前端自己设计需数周，按工程师日薪折算远超 ¥4999。所以定价处在"商业参考设计"的合理区间，且留有明显的上行空间——**一旦未来有了流片实测回流，价格锚可以整体上移一档**。

---

## 四、一个值得注意的定价细节

**¥4999 而非 ¥5000** 卡在中国企业采购的**免招标阈值线**（多数企业 5000 元以下走简易采购，无需招标流程）。

这意味着高端档仍可由工程师/部门主管直接决策，不需要上升到招投标——**显著降低采购摩擦**。建议后续任何调价都保持这个特性（高端档不越过 5000）。

---

## 五、逐档清单

### 基础档 ¥599（15 个）

标准件 / 成熟普惠 / 教学科研常用：

`IM-FTTH-PLC8` `IM-FTTH-PLC16` `IM-SPLITTER-TREE` `IM-GRATING-COUPLE` `IM-MRR-FILTER` `IM-SENSE-RING` `IM-SENS-MZI` `IM-BIOSENSE` `IM-GAS-SENSE` `IM-VOA` `IM-POL-ROTATOR` `IM-MDM-MUX` `IM-CWDM4-SHELF` `IM-PSM4-SHELF` `IM-100G-LR4`

**判据**：前 12 项核心功能均由 gdsfactory 现成件拼出；后 3 项为 100G 时代成熟标准（2014 年前后），替代方案充足。

### 标准档 ¥1999（18 个）

需工程设计 know-how 的子系统（生态有零件无成品）：

`IM-400G-DR4` `IM-FR4-SHELF` `IM-LPO-112G` `IM-RING-MOD` `IM-MZI-MOD` `IM-PSR` `IM-AWG-DEMUX` `IM-WDM-8CH-1D` `IM-OSW-1X8` `IM-COHERENT-RX` `IM-LIDAR-TX` `IM-LIDAR-RX` `IM-LASER-INT` `IM-MCF-FANOUT` `IM-ONCHIP-SPECTROMETER` `IM-PON-50G` `IM-XGS-PON` `IM-CPO-OCS`

### 高端档 ¥4999（开放 17 个）

系统级 + 生态无现成 + 高客户价值：

`IM-1.6T-DR8` `IM-1.6T-FR4` `IM-800G-DR8` `IM-800G-FR4` `IM-CPO-WDM5` `IM-PHOTONIC-INTERPOSER` `IM-CHIPLET-IO` `IM-COHERENT-400ZR` `IM-DWDM-40CH` `IM-WSS-1X9` `IM-ONCHIP-NOC` `IM-OPA-LIDAR` `IM-OCT` `IM-OPTICAL-GYRO` `IM-OPTO-COMPUTE` `IM-OPTCOMB` `IM-TRUE-TIME-DELAY`

**其中 `IM-CPO-WDM5` 是本站唯一产生过实际订单的货架（7/7 单）**，归高端档既符合其 CPO 高价值定位，也与市场用真金白银投出的票一致。

### 量子咨询制起步价 ¥4999（8 个，不可下载）

`IM-QKD-TX-SHELF` `IM-QKD-RX-SHELF` `IM-QKD-MULTI4` `IM-QCTRL-ZC3-10Q` `IM-QCTRL-HERON-16Q` `IM-QCTRL-WILLOW-12Q` `IM-QCHIP-INT` `IM-QCOM-LINK`

出口管制合规红线：这 8 项**不开放下载**，仅咨询制对接。CI 护栏持续守护其不进入开放白名单。

---

## 六、调价机制

定价优先级（代码已实现）：

```
① 管理员配置 config.prices[shelf_id]   ← 运营覆盖，最高优先
② 代码内建分档表 shelf_pricing          ← 开源可见，开箱即用
③ DEFAULT_PRICE_CNY (1999)             ← 兜底
```

- 想临时促销或针对客户议价 → 在 admin 后台改 `config.prices`，无需改代码
- 想永久调整某货架档位 → 改 `shelf_pricing.py` 的分组（会被 CI 守护）

**新增货架必做**：加入 `shelf_pricing.py` 的某一档，否则 CI 护栏「全部货架均已归档价档（无漏定价）」直接 FAIL。

---

## 七、CI 护栏（7 条，已进入 `run_innovation_market_smoke`）

1. 全部 58 货架均已归档价档（无漏定价）
2. 定价表无孤儿 id
3. 价格只能取三档（599/1999/4999），防野价
4. 档位分组无重叠（一个货架只归一档）
5. 出口管制红线：量子咨询制不在开放白名单
6. 定价生效性：经 `store.price_of` 走到分档表（非兜底价）
7. 身份折扣叠加正确（学术 6 折）

实测：`run_innovation_market_smoke` 全过（含 58/58 结构可行 + 7 条定价护栏）。

---

## 八、后续建议

1. **观察转化**：分档上线后看三档的订单分布——若高端档零转化而基础档旺，说明客户群体偏入门，需要整体下移或重新定位
2. **套餐化**：单品之外可考虑"品类包"（如"800G 全套 3 件 ¥3999"），提升客单价
3. **价格锚上移的前提**：只有拿到流片实测回流（C 期发动后），才能把定位从"预设计参考"升级为"已验证设计"，届时整体可上移一档
