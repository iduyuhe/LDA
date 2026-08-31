# Changelog

## v0.9.3（2026-08-31 · 验证可信度外部验货 · 全量验证账本端点）

战略审计 #1 缺口「可被外部验货的验证可信度」从单点（CPO 规模死锚）扩展到整引擎：

- **新增 `GET /api/verification_ledger`（无鉴权、可 curl 验货）**：暴露全部已注册验证资产的**分类与计数**——`physical-law` 确定性物理定律锚（B1–B28 / S1–S13，38 道，任何人都可独立复算）+ `oracle-or-design-anchor` ORACLE 依赖锚（B5/B6/B7，3 道，meep/tidy3d 缺失时回退 numpy 离线近似或设计守则下限）+ `empirical` 实证大数据锚（E1–E7，7 道，真实器件实测语料）；合计 **48 题**；旁挂 `CI core 82 条` 与 `CPO 规模死锚`（默认 100,096 / 规模 250,240 ACCEPT）。
- **诚实分类（verified_by）**：明确标注每类事实来源与开放缺口——R2 外部 ORACLE 默认不通（物理定律锚无法现场交叉验证）、R3 实证锚仅 7 条种子语料、R4 B5/B6/B7 为 ORACLE 依赖（根因=R2）。LLM 不进判决路径，PASS/FAIL 一律由死标量比对。
- 端点纯内省、无重计算，纳入 WebUI 路由层冒烟（GET_ROUTES 静态校验）。

## v0.9.2（2026-08-31 · 阶段2 · CPO 共封装光引擎阵列：十万级真实器件样例）

把 v0.8.45（LVS 短路检测 O(n²) 治理）与 v0.8.46（GDS 导出 O(n²) 治理）打通的十万器件级全链能力，落到**真实器件样例**上——不再是「N 个 Waveguide 串成一条链」，而是层次化的**共封装光学（CPO）光子引擎阵列**。

- **新增 `lda/lda_harness/cpo_array.py`**：CPO 阵列生成器，层次为
  阵列（n_oe 光引擎）→ 光引擎（n_ch 波长通道）→ 通道（n_lane 条波长 lane）。
  - 器件构成真实：微环调制器 MRM（`RingAddDrop`）/ WDM add-drop 解复用环 /
    功率监测·波长锁定抽头（`RingResonator`）/ 光栅耦合器（`GratingCoupler`）
    / 互连波导段（`Waveguide`）——每通道 92 器件 = Tx 链 58 + Rx 链 34。
  - **参数由物理反解，非拟合常数**：微环半径 `R = m·λ/(2π·n_eff)`
    （m=91 **整数**谐振级数、n_eff=2.45 → 7.530–7.713 µm，LAN-WDM 8 波）；
    光栅周期 `Λ = λ_c/(n_eff,gr − sin θ) = 0.612 µm`（θ=15°，齿宽 0.367 /
    齿隙 0.245 µm 同时满足 DRC 线宽与间距双约束）。
  - **几何策略：端口线对齐 + 零跳线**——放置按「入端口（链首用出端口）」
    做 y 补偿，使同行全部连接端口落在同一条水平线上；pitch_x 取
    `max(2·max_hw + margin, max(out_dx) − min(in_dx) + 6)` 保证连线不回折；
    通道宽度整除行宽使通道不跨行。于是全部布线为同层 M1 水平段，
    **同层短路数 = 0 由几何保证，而非靠 LVS 兜底**。
- **新增 `lda/run_cpo_array_demo.py`**：全链闭环演示（构建→放置→布线→
  GDS→DRC→LVS→正/反例→报告）。默认配置 32 引擎 × 34 通道 × 8 波长实测：
  - **100,096 器件 / 2,176 条独立光路 / 97,920 布线网 + 4,352 外部 IO**
  - DRC **100,096/100,096** 全过
  - LVS **ACCEPT**（0 违规 · 97,920/97,920 网表全匹配）
  - 反例（注入断路）→ **REJECT**（证明判决非「永远 ACCEPT」）
  - GDS **38.98 MB / 359,040 元素**（4.02s，round-trip 可解析）
  - 芯片 **13.14 × 7.89 mm = 103.67 mm²**（≈1.04 cm²，真实 CPO 中介层量级）
  - 全链 **8.34s**
- **新增 `lda/run_cpo_array_smoke.py`**：21 条断言入 CI core（**80→81**），
  含层次推导死标量、端口线对齐零回折、**独立重算** R = m·λ/(2π·n_eff) 逐项
  比对、光栅布拉格条件、DRC/LVS 正反例、GDS round-trip、十万配置推导、
  配置护栏（ch_per_row 不整除则拒绝）、源码零 LLM 红线。
- **诚实边界（不可省略）**：仅建模**无源光子层**，有源器件（激光器/探测器/
  驱动 IC/TIA）按黑箱处理（负面清单）；工艺为公开文献近似非真实 foundry
  PDK；本样例只做**版图闭环**，未做光学仿真验证（插损/串扰/FSR 属另一条
  链路）；未流片、无实测回流。

## v0.8.56（2026-08-29 · 创新超市商业闭环：会员 + 统一订单 + 自动交付）
- **商业闭环核心**：新增 `lda/lda_webui/store.py`（零依赖，数据落盘 `dist/store.json` gitignored）——会员注册/登录（PBKDF2 + 会话令牌）、统一订单状态机（created→paid_unverified→approved→rejected）、微信个人收款（收款码+凭证）、管理员「确认收款并自动发货」（复用 `ship_package` 生成一次性兑换码）。
- **双通道**：个人用户（微信个人收款凭证）+ 企业客户（对公转账）共用同一套订单流；下单自动带单价（¥1999 默认，可按货架覆盖）。
- **路由接入**：`lda/lda_webui/app.py` 新增 `/api/store/*`（register/login/me/order/orders/mine/config）与 `/api/admin/*`（orders/config/order/<id>/approve|reject）；新增 `_bearer()` 统一去 Bearer 前缀；管理员鉴权统一认可 `LDA_ADMIN_TOKEN` 环境变量（修复 list_orders 仅认 store 用户、下载路由 `parts[4]/count==5` 解析错位两处 bug）。
- **前端**：`lda/lda_webui/static/store.html`（会员登录/注册、货架下单、上传支付凭证、自助下载）、`admin.html`（订单审核、一键发货、微信收款码配置）；静态白名单放行进 `store.html`。
- 端到端验证通过：注册→下单→凭证→管理员审批（自动生成兑换码）→会员自助下载 zip；个人/企业两通道均跑通。
- **Track 0 计费身份中枢**：注册新增三档身份（standard 标准个人 / academic 学术个人 / institution 机构席位，机构必填单位名称）；`tier_discount` 折扣引擎（1.0 / 0.6 / 0.85，管理员可经 `config.tiers` 覆盖）；`price_of(shelf_id, user_type)` 按身份计价；订单记录 `tier` 字段；`/api/shelf` 按登录身份返回 `price_cny/base_price/price_tier`；前端注册弹窗三身份选择 + 货架实付价 + 下单金额 + 会员中心/导航身份徽标；老账号无 user_type 字段安全回退 standard。生产 e2e 16/16 通过（三身份价格 1999 / 1199.4 / 1699.15 联动验证）。

## v0.8.55（2026-08-29 · 管理后台上线打通商务闭环 + 生产部署真实账户）
- **管理后台**：新增 `lda/lda_webui/static/admin.html`——令牌登录（localStorage）、待处理申请列表（公司/联系人/电话/邮箱/货架/备注/时间）、一键审批并生成一次性兑换码、兑换码复制 + 下载链接；静态页白名单放行进 `admin.html`。
- **文案修正**：`/api/purchase/request` 响应去掉"邮件发送兑换码"空头承诺，改为"到账后管理员生成兑换码、凭码下载"准确表述（手动发码阶段）。
- **生产部署**：`115.191.20.92` 部署真实对公收款账户（上海农商银行陈行支行 32434508010036375）+ 联系人（杜先生 13636690529/13311602075、范女士 13901700712）+ 联系电话；管理员弱令牌通过 `LDA_ADMIN_TOKEN` 环境变量替换为强令牌加固。
- 货架/开放数维持 58/50；量子 8 维持咨询制；CI core 维持 69 条。

## v0.8.54（2026-08-29 · 对公收款程序适配：创新超市接对公购买申请闭环）
- **对公收款适配**：营业执照确认上海杜特企业管理咨询有限公司为有限责任公司（自然人投资或控股），B2B 设计包交付采用直接对公转账 + 兑换码交付。
- **前端**：`lda/lda_webui/static/insights.html` 增加顶部「对公收款说明」弹窗、货架卡片「对公购买」按钮；弹窗收集公司/联系人/电话/邮箱/付款备注。
- **后端**：`lda/lda_webui/app.py` 新增 `POST /api/purchase/request`、`GET /api/admin/purchase_requests`、`POST /api/admin/purchase/{id}/approve`；申请持久化到 `dist/purchase_requests.json`（gitignored）；审批通过调用 `ship_package.mint_license` 生成绑定货架的兑换码。
- **管理**：管理员端点通过 `Authorization: Bearer <LDA_ADMIN_TOKEN>` 鉴权，默认令牌为弱默认值并提示通过环境变量 `LDA_ADMIN_TOKEN` 替换。

## v0.8.53（2026-08-29 · 持续扩货架：新增 5 光子缺口品类开放下载、货架 53→58）
- 货架 53→58：新增 5 个真实 2026 市场缺口光子品类（信号源可溯源、composition⊆GP-*、非出口管制、honest_tier=前瞻预研）：
  - `IM-AWG-DEMUX`（阵列波导光栅解复用器 AWG DeMUX；AWG MUX/DeMUX $735M(2025)→$1.375B(2031) CAGR 8.14%、Arrayed Waveguide Market $320-570M(2026) CAGR 6.5-11.7%、AI 数据中心 DWDM/CPO 推升）
  - `IM-ONCHIP-SPECTROMETER`（片上微型光谱仪；Chip-scale Spectrometer $2.44B(2025)→$8.7B(2033) CAGR 17.2%、Miniature Spectrometer IC $1.36B(2025)→$3.99B(2034) CAGR 12.7%）
  - `IM-MDM-MUX`（模分复用器 MDM；MDM Equipment $1.42B(2024)→$4.16B(2033) CAGR 12.6%、Few-Mode Fibers $10.74B(2025) CAGR 6.86%、突破单模 Shannon 极限）
  - `IM-OPTCOMB`（芯片级光频梳 Microcomb；全球光频梳 $1.87B(2026) 年增 31.7%、Intel $58M(2025)→$108M(2034) CAGR 7.4%、芯片级微梳 CAGR 47.8%）
  - `IM-POL-ROTATOR`（片上偏振旋转器；光偏振控制器 $4.72B(2026) 增 12.9%、Polarization Rotator CAGR 10.3%(2026-2033)、集成波导型增速 28%）
- 开放下载白名单 `OPEN_SHELVES` 45→50（前述 5 个光子缺口品类全量放开；工厂产能已具备，任意已知货架可现场生成设计就绪包）。
- 量子 8 个维持「咨询制」，不进自动下载白名单（出口管制合规红线）。
- `docs/store_launch/04_market_analysis.md` 新增趋势段：AWG 解复用（DWDM/CPO $1.375B 2031）、片上光谱仪（Chip-scale $8.7B 2033）、模分复用（MDM $4.16B 2033）、芯片级光频梳（微梳 CAGR 47.8%）、偏振旋转器（集成波导型增速 28%）；光子细分表格扩容，开放策略 45→50 货架。
- 沿用 `OPEN_SHELVES ⊆ DEFAULT_SHELF` 回归护栏；重新生成 `innovation_market.json`（58 货架）；货架 smoke **58/58 ALL PASS**；`run_count_consistency_smoke` **11/11 OK**（CI core 维持 69 条）。

## v0.8.52（2026-08-28 · 持续扩货架：新增 5 光子缺口品类开放下载、货架 48→53）
- 货架 48→53：新增 5 个真实 2026 市场缺口光子品类（信号源可溯源、composition⊆GP-*、非出口管制、honest_tier=前瞻预研）：
  - `IM-MRR-FILTER`（微环谐振滤波器/可重构光滤波 add-drop；Silicon Microring Resonators $450M→$1.66B CAGR 20.5%、Microring Filter Array $41.58M→$245M CAGR 27.8%、add-drop 占 55.5%）
  - `IM-SPLITTER-TREE`（1×N 功分树/PLC 功分网络；PLC Splitter $2.8B→$5.6B CAGR 8.1%、1×N 占 62.4%、FTTR/XGS-PON 推升 1×32+）
  - `IM-TRUE-TIME-DELAY`（微波光子真延时 TTD 波束成形；Phased Array Antenna $3.90B→$8.38B CAGR 10.04%、相控阵系统 $18.7B→$38.5B CAGR 12.8%、MWP 真延时用于相控阵雷达）
  - `IM-GAS-SENSE`（波导气体/吸收光谱传感 SiN 宽波段；SiN PIC $320M→$1113.58M CAGR 19.5%、VOC 中红外检测灵敏度较 Si 提升 5×）
