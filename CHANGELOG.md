# Changelog

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
