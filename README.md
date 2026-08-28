# LDA · Agent-native 光子/量子芯片设计软件

> LDA（Lightwave Design Agent）= 光子芯片(PDA) + 量子芯片(QEDA) 的开源、主权、Agent-native 设计软件。
> 核心主张：**底层核心求解器由 AI agent 递归自举开发**，人类做架构与验证，AI 不进入判决路径。
> 当前版本：**v0.8.50**（2026-08-28 · **持续扩货架：新增 5 个光子缺口品类开放下载（MZM 调制器、PSR 偏振分束、光子中介层/CPO、光计算 ONN、OCT 成像），货架 38→43、开放 30→35；量子 8 维持咨询制；docs/store_launch/04_market_analysis.md 新增趋势段；CI core 维持 69 条**）· **v0.8.49**（2026-08-28 · **持续扩货架：新增 5 个光子缺口品类开放下载（相干 ZR、微环调制器、XGS-PON、WSS、VOA），货架 33→38、开放 25→30；量子 8 维持咨询制；docs/store_launch/04_market_analysis.md 新增趋势段；CI core 维持 69 条**）· **v0.8.48**（2026-08-28 · **持续扩货架：新增 8 个光子缺口品类开放下载（FR4 200G/400G 每通道、400G DR4、100G LR4、50G-PON、可重构光开关、FMCW 接收、环形生物传感），货架 25→33、开放 17→25；量子 8 维持咨询制；docs/store_launch/04_market_analysis.md 新增趋势段；CI core 维持 69 条**）· **v0.8.47**（2026-08-28 · **扩货架：开放 17 个光子主流货架下载（新增 1.6T DR8 + 800G DR8/PSM4/FR4/CWDM4/LPO-112G/WDM 8CH/DWDM 40CH/CPO WDM5·OCS/FTTH PLC 8-16/传感 RING·MZI·LIDAR/光 chiplet IO/激光集成），量子 8 个列咨询制（出口管制合规红线）；货架 24→25；新增 docs/store_launch/04_market_analysis.md；/api/shelf 加 open 字段前端区分「下载/咨询制」**）· **v0.8.46**（2026-08-28 · **工厂+商店化：货架→设计就绪包（GDS+网表+DRC+死锚报告），开放 3 个试点货架下载（IM-PSM4 / CWDM4 / FR4），新增 /api/shelf/{id}/package 与 /download 端点 + 兑换码授权，前端货架卡片加「下载设计包」按钮（免费看、付费下）**）· **v0.8.45**（2026-08-28 · **展示能力扩张：GC 对标 24 + 创新货架 24 + 能力演示场景 12 项（真实模块/端点画廊 + 核心引擎在线自检）**）· **v0.8.44**（2026-08-28 · **B 技术纵深三连：并行布线 / 规模锚升 4k / 相关簇锚**：②并行布线  route_batch（workers=1 串行逐位一致，>1 进程池零依赖并行；收益边界实测：链式 12µs 无收益、复杂版图 400ms/网 workers=4 达 2.67×；拥塞感知有顺序依赖并行下明确拒绝不伪并行；run_parallel_routing_smoke 5/5 入 CI core 68→69）· S11 规模锚默认 1000→4000（预算 5s→10s，实测 4k 全链 0.07s 余量 140×；smoke 纵深升 8k 近线性守护）· S12 增相关簇锚（连续 ≥3 通道同向偏离 = 系统级簇漂移 → REJECT；盲区实证：旧三锚 ACCEPT、簇锚唯一捕获；插损/保真度已配置不误伤；统计锚 smoke 19→23）· harness 46/46 全过；CI core 69 条· **v0.8.43**（2026-08-28 · **WebUI 能力展示层：GC 对照 / 创新超市 / 规模现场实测**：新增 4 个 API——（20 条 GC 对标， 现场 25/25）、 + （20 条货架，单条真跑 design_pipeline 死标量判决，LLM 不进路径）、（1k/4k/32k 全链实测，32k 亚秒活演示）；新增  深色展示页（GC 对照表 + 货架评估卡片 + 规模柱状图），index 顶部入口；静态页白名单防路径穿越；路由冒烟 63 实跑 + 57 静态全绿；CI core 维持 68 条· **v0.8.42**（2026-08-28 · **S2 纵深三连：拥塞估计 + 算力实测 + 阵列统计锚**：②布线  CongestionMap 拥塞图（A* 启发式叠加惩罚，默认 None 逐位一致）——平行网绕同一障碍最大占用 4→2、拥挤格 222→13；run_astar_route_smoke 10/10。④算力实测结论：细粒度几何内核（4 元素 tuple）numba njit 反而更慢（1.69s vs 0.44s，装箱开销>编译收益）→ 锁定纯 Python 为最优，不引入无效依赖。⑤统计锚  新增 **S12 阵列分布锚**（均值锚+下界锚+离群锚 AND 判决，抓单点锚盲区「均值好看但某通道崩坏」），题库 45→46；run_statistical_anchor_smoke 扩展守护。CI core 维持 68 条· **v0.8.41**（2026-08-28 · **几何 DRC 拔钉子：间距检查 O(n²) → 网格候选**： 最小间距检查从纯 O(n²) 双重循环改为均匀网格候选（bbox 重叠⟺共格精确等价，与 LVS 同法），判决逐位一致（violations/checked/spacing_note 对拍零差异）；8k 多边形 0.08s 近线性、高密度 4000 全重叠 0.44s（旧分钟级）；run_drc 系 smoke 全绿，CI core 维持 68 条· **v0.8.40**（2026-08-28 · **构建器拔钉子：port_abs 索引缓存**：profile 定位 build_chain_case 布线生成的 O(n·m) 存量低效（`port_abs` 每次线性扫全组件，构建 87% 时间耗此）→ `lda_layout/placement.py` 组件查找走索引缓存（O(1) 查表，`_port_abs_cache_clear` 兜底），公共签名与坐标语义零变化；**32k 器件全链（构建+放置+布线+LVS）0.98s**（旧外推 ~960s，~1000×），缩放斜率稳定 1.7–2.7× 近线性；run_scale_smoke 新增 3 条「4k 规模纵深」检查 16/16 PASS，CI core 维持 68 条· **v0.8.39**（2026-08-28 · **LVS 拔钉子：O(n²) → 空间索引**：`lda_l2/lvs.py` 四处复杂度热点根治（端口锚点网格 3×3 邻域 / port_abs 索引化 / 交叉检测路径 bbox 网格候选），纯标准库零新依赖；判决一致性铁证——3 case×4 规模+单层逐字节 diff 零差异、随机 400 折线 62138 交叉对零漏报零误报；LVS 1k 0.88s→0.01s、32k 仅 0.58s（旧外推 ~960s，~1600×），缩放斜率 O(n²)→近线性；run_lvs_smoke 27 PASS / scale 13 / chip_scale 8 全绿，CI core 维持 68 条· **v0.8.38**（2026-08-28 · **GC 库扩至 20 项 + 创新超市货架扩至 20（市场信号驱动）**：市场调研收集可溯源公开规格（IEEE 802.3bs / ITU-T G.671 / 商用 datasheet / 公开文献实测），GC 库 4→20（新增 16 = 光互连 3 + 无源网络 3 + 光交换·传感·LiDAR 3 + 量子通信 3 + 量子计算 4，含祖冲之三号 99.18% / IBM Heron R2 98.5% / Google Willow 99.33% 三家量子对标）；货架 5→20（新增 15 = 光子 12 + 量子 3，800G DR8 / 40ch DWDM / FTTH PLC / OCS 直连 / FMCW LiDAR / QKD 收发 / XPU 光 IO / 三家量级读出链）；`run_golden_product_smoke` 现 25/25（5 GP + 20 GC），`run_innovation_market_smoke` 现 20/20×3 守护全 PASS；修复 v0.8.37 GOLDEN_IDS 对 ChipBenchmark 崩溃 bug；CI core 维持 68 条（数据扩展非新增 smoke）· **v0.8.37**（2026-08-27 · **GC 库扩至 4 项（整芯片级对标续扩）**：`golden_product_benchmarks` 增 GC-SENSE（光子传感前端整芯片，MZI 全链路 IL 13.6dB≤15）/ GC-QCTRL-COMM（商用量子控制芯片 6-qubit 读出保真度 99.78%≥99%），复用 GP-* dB 级联 / D-46×D-47 已验证闭环，零新物理；`run_golden_product_smoke` 现 9/9（5 GP+4 GC），CI core 维持 68 条（数据扩展非新增 smoke）；另出正式讨论稿 `LDA_封装测试闭环与数字孪生协同_讨论稿.md`· **v0.8.36**（2026-08-27 · **整芯片级对标（GC-*）**：`golden_product_benchmarks` 从器件级 GP-* 扩到整芯片级 GC-*——新增 `ChipBenchmark` 类，光子走 GP-* 基元 dB 级联（S1 同构）、量子走 `design_multiqubit_fidelity`（S4 同构），死标量比对；首批 2 个 GC（GC-CPO-8CH 商用 CPO 8 通道光引擎每通道 IL 10.6dB≤15、GC-QCTRL 量子读出保真度 99.78%≥97%）、golden 来自公开产品规格（IBM Research / 本源悟空-180 公开披露）可溯源；`run_golden_product_smoke` 现覆盖 7/7（5 GP+2 GC），CI core 维持 68 条（数据扩展非新增 smoke）· **v0.8.35**（2026-08-27 · **创新超市货架库扩展（2→5 货架）**：在 v0.8.34 货架注册表上新增 3 个前瞻预研货架——IM-SENSE-RING（微环传感前端，复用 link/S1-S7）/ IM-LASER-INT（片上激光源集成，异质集成黑箱源·负面清单）/ IM-QCOM-LINK（5 比特量子频率复用读出，复用 D-46×D-47）；仍严守"组合已锚定基元（GP-*）"护栏，active 器件按黑箱源处理、不新增未锚定基元；CI core 维持 68 条（货架为数据扩展，非新增 smoke 文件）· **v0.8.34**（2026-08-27 · **创新超市（前瞻预研货架）**：新增 `lda/lda_l2/innovation_market.py` 货架注册表——`ShelfItem` 组合已锚定基元（GP-*）+ 公开信号驱动的前瞻预研预设计；`run_innovation_market_smoke` 红线下护栏（composition 全锚定 / 结构可行 / honest_tier=前瞻预研）入 CI core（67→68）；`docs/innovation_market.md` 为可浏览目录（B 素材）· v0.8.33（2026-08-27 · **系统类型注册表（提案编译器系统级纵深）**：`proposal_compiler` 增 `SYSTEM_TYPES`（link 默认 + wdm_demux + quantum_fidelity），`design_pipeline` 增 `system_type` 参数向后兼容；wdm/quantum 复用 `design_wdm_advanced` / `design_multiqubit_fidelity` 已验证闭环（B4 / D-46×D-47 死标量判决），零新物理；`run_system_types_smoke` 入 CI core（66→67））· **v0.8.31**（2026-08-27 · **版图几何级 RC 寄生估算（设计侧主权闭环收口）**：新增 `lda/lda_l2/parasitic_rc.py` 几何级 R/C 寄生估算（主权 RC 表，非 foundry 工艺级 deck）；接入 `tapeout_pipeline` S3.5（提供 GDS 实跑、无版图诚实 SKIP）；`run_parasitic_rc_smoke` 入 CI core· **v0.8.32**（2026-08-27 · **产品级基准对照库（实证锚产品级扩展 + B 生态播种，免流片）**：新增 `lda/lda_l2/golden_product_benchmarks.py`——对标已公开验证（实测/厂商 datasheet/开源 PDK 表征）的器件性能死标量，LDA 引擎规格驱动再设计+复现 5/5 PASS；`run_golden_product_smoke` 入 CI core（65→66）；`docs/golden_product_benchmarks_report.md` 为 B 生态播种硬核素材）· 历史：v0.8.30（2026-08-27 · **CLI 深化 + gdsfactory 兼容 + 计数守护固化**：`lda gf <gdsfactory_component.py>` 把 gdsfactory 组件转 LDA 链路 spec（B 级可选依赖、未装优雅降级）；`lda check --gds <file.gds>` 导入任意 GDSII 跑**主权几何 DRC 快查**（gds_drc，子集诚实标注非 foundry 全量）；`run_count_consistency_smoke` **加固**（只扫顶行防历史链误匹配、版本线=pyproject 动态校验，此前静默失效的 61≠62 漂移已根治）；新增 gds_export.parse_gds_polygons / gdsfactory_bridge。· 注：v0.8.29 开发者 CLI 钩子（design/check/report 三命令薄壳 + run_cli_smoke 入 CI core）、v0.8.28 UI 双修（目标误差列 bug + 统计卡片死卡）、v0.8.27 千器件演示、v0.8.26 规模扩展、v0.8.24 多层版图、v0.8.24 LVS 签核、v0.8.10 首轮持续维护均已落地（同见下方历史链）。当前账本：**22 引擎（光子 15 + 量子 7）+ 11 包 = 33 类端到端 · 46 题（B1-B27 + E1-E7 + S1-S12）· CI core 69 条**。· 历史：v0.8.28（2026-08-27 · **UI 双修**：①目标误差列 0.0000 bug——`design_engine` 的 `rec["err"]` 用 cheap 估算（Koch 反解数学精确 → err 恒 0），改验证后按真实 metric 误差重算（Transmon 候选现显示 0.0047/0.0086/0.0137，best 按真实误差选优 E_C=0.15）②统计卡片死卡——c-harness/c-ai 前端从未赋值，后端 /api/status 补 harness_passed/harness_total/ai_candidates 字段 + 前端 renderStatus 填值，标签统一）· 历史：v0.8.27（2026-08-27 · **千器件芯片级演示**：千器件版图接入芯片级演示闭环——1000 器件链式链路 + 2D 放置 + 多层布线 → GDS 导出（IO 光栅接入）+ DRC 1000/1000 + LVS ACCEPT 双闸，全链路 0.99s，`run_chip_scale_demo.py` 8/8 入 CI core）· 历史：v0.8.26（2026-08-27 · **千器件规模扩展（版图差距 #7 收官）**：`lda_harness/scale_anchor.py` 千器件链式链路全链路 **0.92s 完成 ACCEPT**——跨行跳线走 M2 层；LVS 相交检测 **bbox 预检 3.6× 提速**；harness **S11 规模锚**（题库 **44→45**）；版图 7 差距**全部闭合**）· 历史：（2026-08-27 · **多层版图（版图差距 #6 落地）**：`lda_l2/layers.py` 层栈定义 + **多层 LVS**（`run_lvs_multilayer` 层感知几何恢复 + via 桥接 + 跨层垂直投影重叠安全=介质隔离）+ harness **S10 锚**（题库 **43→44**））· 历史：v0.8.24 LVS 签核深化（版图差距 #5）：`lda_l2/lvs.py` 版图-原理图一致性检查（签核级）——版图网表**从布线几何独立恢复** → 六类违规死标量检出 → ACCEPT/REJECT 确定性判决 + harness **S9 锚**（题库 **42→43 题**）+ 芯片级签核双闸 + WebUI `/api/link_design` 返回 lvs_report）· 历史：v0.8.23 第二梯队-2（多端网 Steiner + 2D 放置 + 有源基元三件套）· v0.8.22 第二梯队-1（A* 全局最优布线）· v0.8.10 首轮持续维护（内核纵深五击 + 芯片级验收闭环 + 器件库主流封口 + 流片级验证管道 + 计数一致性门禁：22 引擎 + 11 包 = 33 类端到端 + **芯片级四锚验收** + 仿真级芯片设计闭环演示 + **流片级验证管道**（PDK→DRC→SS/TT/FF 工艺角→LVS→实测回流）+ harness 题库 **45 题**（B1-B27 + E1-E7 + S1-S11）+ Phase 3 统计锚 + **Phase 4 提案编译器** + CI core 61 条）
> **v0.6.1 维护基线**（2026-08-24 · D-99）：生态共建（D-93~D-98）收官——「提交→评审→落地→发布」全链闭环；CI core 门禁覆盖生态链三 smoke（harness 扩展 / 提交 / 评审→落地→发布）；`lda_pdk` 模块文档同步 D-96~D-98；全量回归全绿。
> **v0.6.2 持续维护**（2026-08-24 · D-101）：**all 集 70 项 smoke 全量回归 70 PASS / 0 FAIL**（1602.72s，覆盖 D-01~D-98 全部资产含重 FDTD/3D adjoint/GPU 项）；新增 `requirements.txt` 环境固化（必装 numpy/scipy/jsonschema + 可选 numba/torch）；README 模块列表补 `lda_pdk` 生态共建全链。
> **v0.6.3 持续维护**（2026-08-24 · D-102）：**WebUI API 路由层冒烟**（64 条 /api 路由：快路径 13 实跑 + 重计算 51 静态验证，纳入 CI core 门禁）；一致性深审（README 63→70 smoke 修正、harness 键集一致性核验）。
> **v0.6.4 持续维护**（2026-08-24 · D-103）：**WebUI 字段一致性门禁**——前端面板 53-56 渲染硬依赖字段 ↔ GET /api/ecosystem 真实响应逐路径核对零缺失（端点 36 调用全有路由、POST 四端点响应字段全对齐）；深审方法固化进 `run_webui_api_smoke.py`（新增 **31 条生态字段存在性断言**，实跑 13→44 PASS）；CI core **31 PASS / 0 FAIL**（279.56s）全绿；字段删除/改名今后即被 CI 捕获。
> **v0.6.5 实证锚**（2026-08-24 · D-62 发动期联动框架落地）：**实证大数据锚 = 验证的第二道非 AI ground**——harness 新增 **E1-E3 实证锚题**（golden=实测语料 2.63/1.53/9.15，参考候选 21/21 PASS 双 ground、扰动 FAIL 检测）；**语料评审流**（`lda_pdk/empirical.py`：citation 必填 → 具名评审（LLM 不进判决）→ 落库 → harness E 题实时生效）；WebUI **五十七面板**（面板57 + `/api/empirical` + `/api/ecosystem/measurement`）；CI core 32 项；诚实边界：种子语料为公开文献/PDK 量级，真实晶圆厂 NDA 流片实测经社区流持续流入。
> **v0.6.6 持续维护**（2026-08-25 · D-104）：**D-62 收官后全量回归（最强门禁）**——all 集 **72 项 smoke 全量回归 72 PASS / 0 FAIL**（覆盖 D-01~D-103 全部资产 + WebUI 路由层 + 实证锚）；**修复**：L1 协议层注入实证锚（`verify_design` 恢复 21/21，MCP smoke 适配 D-62），`run_mcp_smoke` 入 CI core 门禁（33 条）；一致性深审：实证锚键集三通道核验、计数修复（70→72 smoke）、README 当前态陈旧引用修复（18→21 题 / 五十六→五十七面板）、任务台账 16 项归正。
> **v0.6.7 持续维护**（2026-08-25 · D-105）：**L1 协议层全链路门禁**——新增 `run_l1_agent_smoke.py`（KernelGateway + L0 IR + 三种 candidate + benchmarks 过滤全链路 6/6 PASS），`run_agent.py` CLI 演示路径此前无 smoke 覆盖的缺口闭合，入 CI core 门禁（**34 条**）；环境一致性核验（requirements 必装 3 包与 venv 全齐、可选标注完整）；残留扫描干净。
> **v0.6.8 持续维护**（2026-08-25 · D-106）：**agent 自迭代设计闭环门禁**——深审发现 `run_agent_loop.py` import 断链（引用了 design_loop 中从未存在的 ring_fsr_problem，非 smoke 命名未被 CI 捕获）→ 修复为基于 `design_loop.main()` 的可运行演示 + 新增 `run_agent_loop_smoke.py`（5/5 PASS：收敛 accepted / 误差死标量 / FDTD+TMM 双判据全绿 / JSON 落盘），入 CI core 门禁（**35 条**）；计数修复（72→73 smoke）；WebUI JS 静态检查（67 绑定全对应、语法通过）。
> **v0.6.9 持续维护**（2026-08-25 · D-107）：**文档资产 + IR schema + 性能基准深审（零缺陷）**——README 引用路径死链扫描零缺失（4/5 存在，`{bid}` 为 D-98 模板占位符非死链）；L0 IR schema v0.3 与 spec/bridge 一致（受控升级 0.2 兼容、零漂移门禁在 core）；性能基准复核未退化（`run_perf_adjoint3d` 大域 FWD 27.6× ≥20× + FOM rel=1.3e-16；`run_perf_bench` greens 76.89× + 透射谱 5.39× + GPU SKIP 正确降级）；docs 资产与 D 编号（D-106 最新）一致。
> **v0.6.10 持续维护**（2026-08-25 · D-108）：**实证锚字段门禁补强**——深审发现面板 57（D-62 新增）依赖 `/api/empirical` 的 5 个顶层字段（corpus/adversarial/e_benchmarks/review/honest_note）但 D-103 固化的字段断言只覆盖 `/api/ecosystem` → `run_webui_api_smoke.py` 新增 **`EMPIRICAL_REQUIRED_FIELDS` 13 条断言**（含 e_benchmarks[0] 元素 id/empirical_id/golden/tol），实跑 PASS 44→**57**、FAIL=0；D-103 断言集漂移复核零；README/CHANGELOG/规划文档计数一致性全对。
> **v0.6.11 持续维护**（2026-08-25 · D-109）：**all 集 74 项全量回归（D-104~D-108 五轮修复后最强门禁复核）**——覆盖 D-01~D-108 全部资产 + L1 MCP/CLI + agent 自迭代闭环 + 实证锚，**74 PASS / 0 FAIL（1611.76s）全绿**；🔴 回归发现 `run_ci_industrial_smoke` 每次运行重新创建坏 smoke 且沙箱删除失败残留（D-101 曾清一次）→ **根治**（多重删除 + unlink 兜底 + 失败改名 .bak 隔离，验证零残留），计数修复（73→74）；面板端点覆盖盘点（38 个 JS 调用：生态/实证 44 条字段断言 + 10 POST 实跑，26 个重计算端点按设计走路由静态验证 + 内核专用 smoke，无高价值缺口）。
> **v0.6.12 持续维护**（2026-08-25 · D-110）：**社区文档一致性 + core 覆盖补强**——🔴 发现 `BOUNTY.md` 评审流程陈旧（仍写"维护者直写 seed_empirical.json"，D-62 前旧流程）→ 更新为社区评审流（submit_measurement→具名评审→land→empirical_contributions.json，面板 57/API 可提交）；`run_ci_industrial_smoke`（FAIL 检出机制 + 性能基准，zz_bad 残留根治的守卫）此前不在 CORE_SMOKES → **纳入 core 门禁（36 条）**；CONTRIBUTING/BOUNTY 无陈旧计数、design_package_schema 语法有效。
> **v0.6.13 持续维护**（2026-08-25 · D-111）：**CI 基础设施 + 开源门面核查**——`.github/workflows/ci.yml` 健康（job2 `industrial-regression` 已走 `run_ci_regression --tag core` 统一入口自动发现 36 条 + 安装含 jsonschema，D-99 教训已落实；job1 为历史检查保留无破坏）；LICENSE（MIT）与 README 声明一致；🔴 发现 **AUTHORS.md 缺失**（BOUNTY 承诺"贡献者署名进 AUTHORS + Hall of Fame"但文件不存在）→ **补齐**（维护者 + 社区评审流署名机制 + Hall of Fame 说明）+ README 许可证段补引用。
> **v0.6.14 持续维护**（2026-08-25 · D-112）：**浏览器级 UI 实测（agent-browser 全量遍历，零缺陷）**——真实 Chromium 打开 WebUI：页面加载**零 JS 运行时错误**、57 面板全渲染（40316 字符）；真实交互实测通过——面板 53（`runEco`：harness 21/21 · 主权 A=5 B=7 C=4）、面板 57 判题（候选 2.63 vs 实测 2.63±0.02 → **PASS 死标量比对**）；JS 运行时盲区经一次性全量遍历验证闭合，此后转低频抽测。

## 参与共建（阶段 B · 生态播种）

- ⭐ **Star 仓库**：<https://github.com/iduyuhe/LDA>——你的 Star 是社区信号，也是对外可达性的杠杆。
- 🐛 **认领 Good First Issue**：见 [Issues · good first issue 标签](https://github.com/iduyuhe/LDA/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)，按 `CONTRIBUTING.md` 流程提 PR。
- 📐 **提交实测语料 / 对抗题**：见 `BOUNTY.md` 反向悬赏机制（实证大数据锚是验证的第二道非 AI ground）。
- 📖 **技术叙事**：我们在公众号「工业5点0产业生态联盟」与知乎持续发布 LDA 设计哲学与闭环演示。
- ▶️ **5 分钟上手**：见 `examples/README.md` 与 `LDA_一页纸_概览.md`。

## 这是什么

LDA 是一套面向光子集成回路（PIC）与超导量子比特（QEDA）的**设计→验证闭环引擎**。它把"AI agent 写内核、确定性裁判验收"的工程范式落成可运行、可验证、可复现的代码，让普通算力（纯 numpy、零 GPU）就能自助完成**从设计目标到已验证器件/系统**的闭环，并把**物理定律锚 + 实证大数据锚**作为信任地基，而非依赖任意大模型意见。

**v0.6 的核心能力（D-36~D-89）**：给系统一个设计目标（如"f01=5GHz 的 Transmon"、"FSR=17.5nm 的环形分波器"、"N qubit 频率复用读出"、"多环 WDM × 量子读出混合系统"、"8 信道 WDM × 8 qubit 联合压测"、"3D 平板波导聚焦 taper"），LDA 自动完成 **参数搜索 → 真实求解器双重验证 → 返回被验证过的设计**，并以**统一设计包（DesignPackage）**格式交付——LLM 不进判决路径，是否 PASS 由死标量比对决定。**v0.6 在 v0.5 系统级（M7 + 护城河 + 逆设计纵深四阶）之上新增**：①**3D 逆设计全链（破 3D 诚实边界）**——3D adjoint 形状（D-84，3D Yee 显式转置伴随 Mᵀ 1e-15）、3D 截面形状（D-85，宽度×厚度双软边界 imp 3.17×）、3D 端口 S 参数联合验收（D-86，双独立确认 FOM 1.88×+S21 1.60×）、谱形目标×3D（D-87，加权 3.13×）、3D numba 性能升维（D-89，大域 forward 20-29× bit-level 一致）；②**QEDA 求解器级补强**（D-88，transmon-resonator 色散读出三能级严格求解，χ=g²α/(Δ(Δ+α)) α 修正必要性 31×，n_crit/Purcell/AC Stark）。

### 红线（设计原则）

- **LLM 不进判决路径**：求解器输出 vs 黄金参考的 PASS/FAIL 由死代码标量比对决定，AI 只写代码、不写判决。
- **主权优先**：核心求解器自研（FDTD/FDFD/Mie/TMM/严格对角化等），不外包、不借 GPL 源码；可借 ORACLE 真值校验与晶圆厂 PDK。
- **可验证**：每个能力都配确定性比对裁判或物理定律锚（解析闭式 ↔ 严格数值双验证），避免纯 AI 互证循环论证。

## 架构分层（从底层走）

```
L0  开放 IR / DSL     lda_ir/   光子+量子统一中间表示（schema v0.3，PhysicsAnchor 一等字段）
L1  智能体协议层      lda_agent/ 设计→验证闭环、逆设计、系统级设计（agent 可操作接口）
L2  开放器件库/Registry lda_l2/  已验证器件资产 + GDS 编码器 + DRC（社区共建）
L3  求解器后端        lda_solver/ 自研求解器（FDTD/FDFD/Transmon/Resonator/Coupler 严格数值）
L4  统一交付          lda_design/ 设计包规范（DesignPackage schema v0.1 + JSON Schema）
```

## 设计→验证闭环（核心能力）

```
给定设计目标 → 物理定律 ORACLE 瞬时搜索（逼近目标）
             → top-K 候选真实求解器双重验证（解析契约 + 严格数值物理自洽，纯 numpy 零 GPU）
             → 死标量验收判决（LLM 不进判决路径）
             → 统一设计包 DesignPackage（ir + design + verification + artifacts + honest_notes）
```

**已验证能力阶梯（D-36~D-52，全部实测全绿）**：

| 编号 | 能力 | 实测亮点 |
|---|---|---|
| D-36 | 设计→验证闭环引擎 | WG/Bragg/Transmon/Ring 4 器件，最优设计被真实求解器验证 |
| D-37 | 环形 add-drop 产品链路 | 目标 FSR → R → GDS/DRC/FDTD → 损耗预算 → 可制造设计包 |
| D-38 | agent 逆设计通用框架 | 同一框架落地 4 器件（光子+量子，注册一条 spec 零框架改动）|
| D-39 | 量子多器件双验证 | Transmon/Resonator/Coupler 全带一等真实物理验证入口 |
| D-40 | 统一 IR 物理锚 | schema v0.3，同一 IR 表达两种物理，harness 达 **13 题（B1-B13）** |
| D-41 | 量子逆设计闭环 | 目标频率/耦合 → IR → 闭式反解 → 严格数值验证 PASS |
| D-42 | WDM 多环级联系统 | 4 信道分波 IL≤0.12dB、XT≥18.4dB，超规格正确拒绝 |
| D-43 | 光子-量子混合链路 | 芯片级 dispersive readout，JC 精确对角化↔色散 χ |
| D-44 | 统一设计包规范 | DesignPackage schema + JSON Schema（8 类包 conforms）|
| D-45 | WDM 指标驱动 | XT 指标反解 gap、插损预算、单 FSR 信道上限 |
| D-46 | N-qubit 频率复用读出 | 3 qubit 沿公共力线错开 200MHz，dip 可分辨 |
| D-47 | 单发读出保真度预算 | t_m*=53.6ns → SNR=3.50、F=0.9984（T1 限制）|
| D-48 | 正式发布准备 | README v0.2 + CHANGELOG + git tag v0.2（三端同步）|
| D-49 | 设计包 spec 6 kind | 文档与实现零漂移，JSON Schema enum 同步 |
| D-50 | fdtd3d GPU 实跑激活 | RTX 5060 Ti：cuda↔cpu **bit-equivalent 互证 PASS**（20 分钟实测）|
| D-51 | N-qubit 逐 qubit 保真度 | D-46×D-47 集成：坏 qubit 独立 FAIL 不影响他者 |
| D-52 | **混合巨型系统** | 光子 WDM 分波 + 量子读出**同一网表**（IR 10 器件+8 网表）联合验收 |
| D-55 | **方向耦合器设计闭环** | 目标分束比 → **2D FDTD 标定 κ** → CMT 反解 L → 迭代收敛（50:50 命中 cross=0.503）|
| D-57 | **耦合器 × WDM 组合** | **FDTD 标定 PDK 文件驱动 gap** → WDM 验收全过 + 诚实报告解析偏差 4.6 倍 |
| D-59 | **波长相关标定库** | κ_c(gap,λ) 二维：每信道按 λ 独立 k_ring，实测增幅 ~27% 物理正确 |
| D-60 | **κ_c(gap,λ) 全网格标定库** | **双线性插值查表**（9 点全网格）替代分离变量近似，无需任何解析假设 |
| D-63 | **方向耦合器 × 量子读出** | 光子**分束网络供电量子读出控制线**：级联功率=**FDTD 实测分束比之积** → 每 qubit n̄ 缩放 → SNR/F 预算（Δ≤0.003，F≥0.9996）|
| D-66 | **标定库 × 分束网络** | 分束网络 DC gap 由 κ_c(gap) 标定库驱动设计（标定 5/5 PASS）|
| D-67 | **分束网络 × WDM** | 光子域功率分配与分波联合：WDM 解复用 → 每信道 DC 分束树（FDTD 实测分束比级联）|
| D-68 | **PDK 标定库 4×5 升级** | 分辨率修正：κ_c 沿 gap/λ 双轴单调的干净网格（20 点，dl40），双线性插值查表 |
| D-69 | **伴随法拓扑逆设计（adjoint FDTD）** | 主权 2D FDTD **显式转置伴随**（Mᵀ 对拍 1e-15）+ 高斯脉冲源收集场能目标 + 回溯线搜索梯度优化：**对拍 max_rel_err=0.0**，**拓扑逆设计提升 15.1×**（3996 体素）|
| D-70 | **逆设计接入设计→验证引擎（method=adjoint）** | DesignAgent 统一入口按 **method** 分流（scan=布拉格扫描零改动 / adjoint=伴随梯度拓扑逆设计）：目标泛化为**「把指定孔径内收集场能最大化」**（设计区/孔径/材料对比度/波长全透传）→ 均匀平板初值 → FD 对拍锚（≤0.15）→ 回溯线搜索梯度优化（improvement≥1.5）→ 死标量验收输出 DesignOutcomeReport |
| D-71 | **真实版图基元库（foundry-ready）** | 4 基元替代玩具几何：Taper（线性/绝热余弦轮廓）、Euler 弯（clothoid 曲率连续，90° 终点角误差&lt;0.01°）、MMI 1×2 对称分束、光栅耦合器（周期部分刻蚀齿）→ **GDS 可编码（round-trip 回读一致）+ DRC 全绿**（min_width/min_space/min_bend_R）；几何交付，电特性归 D-72 |
| D-72 | **真实 2D FDTD 端口 S 参数验收（M5）** | MMI 全 2D FDTD 端口透反射谱（输入 CW 激励→多端口 DFT 收集→输入功率归一→S11/S21/S31）：**平衡度 max=0.078**、中心波长 **S11=0.094 / T=0.906** + **DRC 规则从真实 SOI 180nm PDK 注入**（NOEIC/CUMEC/SITRI 全绿）|
| D-72★ | **3D 端口 S 参数验收（SOI 220nm · numba 核）** | **MMI/DC/Ring** 全 3D FDTD 端口透反射谱（复用已验证 numba 核 + 截面匹配源）：**MMI 平衡度 0.015-0.083、DC cross_frac 端点趋势（CMT）、Ring drop 谐振峰检出**，3 器件全过 + **2D↔3D 对拍诊断**；**已接入设计闭环**（DesignAgent method=sparams3d，三 method 统一入口）|
| D-78 | **光栅耦合器端口验收（M6 起步 · 光栅方程 ORACLE）** | GC 2D FDTD 透射谱谷检测（D-78 修正真实方波光栅：齿=硅/凹槽=包层）：谷位置 vs **光栅方程 λ_rad=Λ·n_eff** 对拍（**rel=0.092**≤0.15，n_eff FDTD 独立测得非拟合）+ **Λ 趋势锚 dλ/dΛ=周期结构 n_eff（rel=0.020**≤0.10）：谷深 0.996、**验收 PASS**，smoke 3/3；诚实标注凹槽微扰负偏 ~9% + 2D≠3D 光纤耦合 |
| D-79 | **真实基元接入设计流水线（Track B 收口 · v0.4 门槛达成）** | 流水线默认几何切换到 D-71 真实基元：Ring/AddDrop 实心环带→**真实波导环 PATH**、YBranch 裸分叉→**输入绝热 taper**+双 arm、DC/Waveguide 已是 PATH、Taper/EulerBend/MMI/GC 沿用基元——全 **9 kind 真实 GDS + round-trip + 3×SOI PDK DRC 全绿**（NOEIC/CUMEC/SITRI），"设计→验证→版图"全链路真实化闭环 |
| D-73 | **热光可调 WDM（Track D 系统级 · M7 第一件）** | 静态 WDM（D-42/D-57）叠加**每环热光相位 shifter**：**Δλ/λ=(dn/dT)·R_th·P/n_eff 物理定律锚**（dn/dT=1.86e-4/K 材料常数、n_eff=2.4，ORACLE 比对真实 Si 加热器斜率 [0.02,0.5] nm/mW）→ 信道重分配验证 |P|≤P_max 且 |Δλ|≤FSR/2（无混叠）；默认 3 信道 S≈0.120 nm/mW、目标 [1552.7,1555.7,1558.7]nm 各 ~22.7mW、最大可达位移 6.0nm≥FSR/2；smoke 3/3 |
| D-74 | **量子门 / 纠错拓扑（Track D 系统级 · M7 第二件）** | 量子域从「读出」走向「计算」：①量子门库（I/X/Y/Z/H/S/T/CNOT/CZ/SWAP/Toffoli 解析矩阵，幺正性 ‖U†U−I‖≤1e-12 精确 + {H,T,CNOT} 通用性 **T∉24元Clifford 群论死标量锚**）②rotated surface code（**d² 数据比特、全对易、GF(2) 秩验证 k=1**、阈值标度 p_L=A·(p/p_th)^((d+1)/2)）③cross-resonance 门（g_CR=2J²Δ/(α²−Δ²) 有效模型 + t_CR≤T2）；ORACLE：|g_CR|∈[0.02,10]MHz、p<p_th（阈值门）；smoke 3/3 |
| D-75 | **大规模系统基准（Track D 系统级 · M7 第三件 · M7 收口）** | 把 WDM 级联 + 多 qubit 读出 + 混合巨型系统推进到 **N≥8 大规模**并做**性能与精度边界压测**：8 WDM 信道（1.2nm 密集 DWDM grid）级联 + 8-qubit 频率复用读出 + 联合 8×8 混合系统全过；**容量自洽**（实际最大可行 N=8 == 理论 floor(FSR/间隔)+1）、**IL 级联模型余量**（N=16 时 0.22dB，预算 3dB 的 7.3%）、**qubit 间隔临界**（默认 0.05GHz vs 失效 0.02GHz，余量 2.5×）、**标定网格分辨率**（κ_c 网格 λ 间距 25nm vs 信道间隔 1.2nm → 每信道变化 0.59%≤1%）；总压测耗时 0.056s；smoke 3/3 |
| D-76 | **L0 IR 开放标准（护城河与标准层 · v0.3 定稿）** | 把 schema 0.3 固化为**开放标准**（社区共建起点）：`docs/ir_spec.md`（LDA-STD-001 规范：9 kind 注册表 / 物理锚语义 / 校验规则 / 扩展指南）+ `docs/ir_schema.json`（JSON Schema draft-07）+ **零漂移校验**（Schema↔代码 9 kind 一致 / 全 kind conforms / 0.2 向后兼容 / physics 物理锚 round-trip——顺带修复 `dsl.py` 此前 round-trip 丢物理锚的序列化缺陷）；smoke 3/3 |
| D-77 | **验证合约工业化（护城河与标准层第二件）** | 全部验证收敛到**一条命令、一份机器可读报告**（社区协作门槛）：`run_ci_regression.py` 自动发现 54+ smoke + harness B1-B13 统一回归（SKIP=无 GPU/numba 降级、FAIL=真失败、新增零配置纳入；core 集实测 **27 PASS / 0 FAIL**）；`run_perf_bench.py` 求解器性能基准（greens numpy→numba **34.7×**、物理一致 rel=4.8e-16、GPU bit-equivalent、历史基线漂移 ±30% 预警）；CI 新增 `industrial-regression` job |
| D-80 | **谱形目标逆设计（Track A 深化）** | 把 adjoint 逆设计目标从「收集场能最大化」**泛化为三类谱形目标 FOM**（逼近商业 EDA 核心卖点）：**①split_ratio 分束比**（双输出监视器，对数加权 FOM，FDTD 实测命中 target±0.10——50:50 实测 0.574、imp 2.5×）；**②spectrum 多波长谱形**（FOM=Σw_λ·FOM_λ 加权联合，3 波长窄带 imp **11.7×**）；**③mode_match 模式匹配**（目标场投影，平坦目标 imp **8.6×**）；死标量验收 FD 对拍 ≤2e-4；smoke 3/3 |
| D-81 | **形状逆设计 + 多目标联合（Track A 纵深新线）** | 从 voxel 拓扑升级为**连续形状逆设计**（K 控制点宽度曲线 w(x) + sigmoid 软边界，**可制造性内建**：宽度界 + 平滑约束 + DRC 验收；形状梯度链式投影 FD 对拍 5e-4；imp **6.6×**）+ **多目标联合**（多波长加权 FOM 共享形状 + Pareto 前端扫描：2 波长加权 **5.6×** + 前端 3 点）；smoke 3/3 |
| D-82 | **形状+拓扑混合逆设计（Track A 纵深第二件）** | 形状主干（宽度曲线，可制造内建）⊕ **拓扑微调带**（voxel 密度，概率 OR 光滑组合——"任一有材料即材料"处处可导）分层表达；联合梯度 + 回溯线搜索 + **纯形状基线对比**（混合≥纯形状为验收判据）：混合 imp **18.3× vs 纯形状 6.0×（混合增益 3.06×）**；FD 对拍全过；smoke 3/3 |
| D-83 | **混合×多波长加权联合（Track A 纵深收官）** | 参数化×目标矩阵**全打通**（参数化∈{拓扑,形状,混合} × 目标∈{单场能,谱形,多波长}）：混合参数化共享形状主干+拓扑带，多波长加权 FOM=Σw_λ·FOM_λ（固定 dl 只变 omega）+ **分块归一化**（形状/拓扑各自尺度，保证拓扑带参与）+ Pareto 前端：加权 imp **19.35× vs 纯形状多波长基线（增益 3.18×）**，逐波长 22.2×/16.5×，Pareto 3 点；FD 对拍 9.8e-4；smoke 3/3 |
| D-84 | **3D adjoint 形状逆设计（破 3D 诚实边界）** | adjoint 从 2D 推向 **3D Yee 交错网格**（6 分量，更新算子**显式转置**伴随——数值 Mᵀ 对拍 **1e-15**，不依赖 torch/jax）+ 平板波导宽度曲线形状（K 控制点软边界 + 5 层核心 + 可制造 DRC）：imp **2.02×**（聚焦 taper 成形），3D adjoint FD 对拍 **9.4e-6**、形状梯度 8.2e-4；smoke 3/3 |
| D-85 | **3D 截面形状逆设计（3D 纵深）** | 把 z 截面也变成形状自由度——**宽度 w(x) × 厚度 h(x) 双软边界**（z 底固定 0、顶 z_top=h(x)，处处可导；联合梯度 [dFOM/dw ⊕ dFOM/dh] + 双界 DRC）：imp **3.17×**（**比平板 2.02× 提升 57%——厚度自由度增益显著**），截面梯度 1.0e-2；smoke 4/4 |
| D-86 | **3D 逆设计 × 端口 S 参数联合验收（补闭环最大缺口）** | 战略审计最大缺口：3D 逆设计无端口级验收。打通 **3D adjoint 场能优化 → 独立 3D CW 端口核**（S11/S21，src_profile 可配）→ **双独立确认**：FOM imp **1.88× 且 S21 0.132→0.211（1.60×）同向双过**；能量守恒 S11+S21≈1；**关键物理认知：聚焦 FOM ≠ 透射 S21**（两端收窄 taper 模式失配）→ w_min=4/init_w=6 对齐；smoke 3/3 |
| D-87 | **谱形目标 × 3D 截面（多波长加权联合）** | 2D 谱形/多波长目标扩展到 3D：**物理网格固定只变 omega**（归一化网格陷阱免疫）+ **多波长加权联合梯度**（分块归一化 w/h 各自尺度）+ 全波长线搜索：加权 imp **3.13×**（逐波长 3.18×/3.15×/3.06× 三波长同向 ≥3×）、联合梯度 **4.2e-4**、DRC 双界全过；smoke 5/5 |
| D-89 | **3D adjoint numba 化性能升维（突破 3D 域规模天花板）** | 3D Yee 核 + 显式转置反向 **prange 并行 JIT**（`backend` 参数 auto/numba/numpy，**无 numba 自动回退**）：forward 加速 **44 域 8-11× / 64 域 17-21× / 80 域 22-29×（最大域 ≥20×）**，与 numpy **bit-level 一致（FOM rel ≤ 3.7e-16）**；优化链路 64 域 **4.4-5.2×**（imp 完全一致）；梯度 2-5×；smoke 6/6（含 numba 一致性 + 回退） |
| D-88 | **QEDA 求解器级补强 · transmon-resonator 色散读出（量子蓝海占位）** | 三能级 transmon + Fock 谐振器**联合严格对角化**（D-43 二能级 JC 升级，引入 |f⟩ 态非谐性）：**真实色散 χ=g²α/(Δ(Δ+α))**（Blais 修正）↔ 数值 rel **2.5%**，二能级近似 rel 77.5%（**α 修正必要性 31×**，χ 为负即非谐性标志）；输出 **n_crit / Purcell 率 / AC Stark / 拉比自洽**（0.02%）；smoke 3/3（含色散区失效负例） |
| D-91 | **QEDA 纵深三件套（多能级展开 · 驱动场 · 读出串扰）** | ①多能级电荷基底展开：χ 3→6 能级**收敛 0.495%**（<1% 证明三能级自洽）+ Blais 解析 rel 1.98%；②驱动场 RWA：共振 **Rabi 自洽 rel 0** + 失谐 **AC Stark Ω²/4δ 对拍 rel 0.39%**；③多 qubit 读出串扰：共享谐振器媒介 **ZZ 耦合 J_zz=0.000831 GHz**（g=0 自洽 + 互换对称 rel 0 + |J_zz/χ|=0.369 弱耦合）；smoke 4/4（含驱动强场 + 串扰简并负例） |
| D-92 | **3D voxel 拓扑逆设计（3D 纵深最后一环）** | 3D 设计区**潜伏密度 + tanh 投影 beta 延拓**（先柔后硬二值化，可制造性内建）+ 3D adjoint 显式转置梯度链式：imp **6.30×**（44 域 iters=24）、拓扑梯度 FD 对拍 **5.9e-3**、二值化 **20.8%**（beta_max=16 重投影）；Track A 3D 参数化矩阵补上拓扑列；smoke 7/7 |
| D-93 | **生态共建框架（PDK 对接 / harness 题库扩充）** | **①harness 题库 B1-B13 → B1-B18**：新增 5 道物理定律锚（B14 定向耦合器 3dB 长 / B15 Bragg 波长 / B16 MMI 自成像长 / B17 约瑟夫森临界电流 / B18 Purcell 因子），自动纳入统一回归零接线；**②主权依赖三级分级代码化**（A 永不借 5 项 / B 借今踢后 fork Gitee 7 项 / C 第一天自主 4 项，来自战略审计 LDA-ST-001）；**③开放 PDK/器件本体 Registry 地基接口**（`lda_pdk`：add/query/stats/to_json/load，与 empirical_bank 同构）；诚实边界：真实晶圆厂 NDA-PDK 对接属发动期 D-62 暂缓、不硬编码；smoke 4/4（harness 18/18 + 主权 A/B/C + Registry 自检） |
| D-94 | **生态共建深化 · 社区提交入口（D-93 地基之上）** | 在开放 Registry 之上开放**统一提交入口**（`lda_pdk/submit.py`）：**①提交器件本体**（`submit_device`：自动推断主权分级 A/B/C + 校验 + 冲突感知 + 持久化贡献库 `contributions.json`）；**②批量导入**（`submit_devices_batch`：逐条 accepted/conflict/rejected）；**③harness 物理定律锚提案**（`BenchmarkProposal`/`ProposalStore`/`submit_benchmark_proposal`：仅登记 pending，需代码评审 + golden.dispatch/physical_law 注册后方可纳入回归——**绝不自动注入 golden 函数，LLM 不进判决路径**）；WebUI 升级至**五十四面板**（面板54「社区提交入口」+ `/api/ecosystem/submit|import|propose`）；smoke 10/10、报告 7/7 |
| D-95 | **生态共建闭环 · 社区评审流 + 提案→golden 落地（D-94 之上）** | 把 pending 提案闭环成「**提案 → 具名人工评审（LLM 不进判决路径）→ 确定性自测门禁 → 落地接入统一回归**」（`lda_pdk/review.py`）：`review_proposal`（approve 须附 ORACLE 源码 + 前置自测：可编译 + 默认参数返回有限标量；reject 直落；缺评审人即拒；全程审计轨迹）、`land_proposal`（仅 approved 可落地：受限命名空间编译 ORACLE → `register_golden`+`register_benchmark` **零接线纳入统一回归** → 持久化 `landed.json` → **生成 golden.py/benchmarks.py 补丁**供维护者 git 提交——落库(live)≠进版本控制）；harness 扩展钩子（`golden.py` 模块级 `_GOLDEN_DISPATCH`/`_PHYSICAL_LAW` + `register_golden`、`benchmarks.register_benchmark`）；WebUI 升级至**五十五面板**（面板55「社区评审流 + 提案落地」+ `/api/ecosystem/review|land`）；实测：B19 微环 FSR 落地后 harness 自动 18→**19 题 19/19 PASS**；smoke 18/18、报告 10/10 |
| D-96 | **生态共建进一步 · 评审门槛扩展 + 评审流 UI 增强（D-95 之上）** | **①门槛扩展（全确定性，LLM 不进判决路径）**：`review_proposal` 新增**签名完备性**（inspect：ORACLE 必填参数 ⊆ default_params，明确报缺参）/ **数值界限**（提案声明 value_min/value_max，自测值须落界内）/ **core 双评审人 quorum**（需 2 位不同具名评审人批准，同评审人重复票不推进，票数入 `approvals`+审计）；`submit_benchmark_proposal` 新增**提交期防重守卫**（oracle_fn 已落地（landed.json 全局权威）或公式规范化后与现有 pending/approved/landed 提案重复 → 拒）；**`resubmit_proposal`**（rejected→pending 保留审计并追加 resubmit 记录）；**`review_stats`**（状态分布 + 批准/拒绝计数 + quorum 票 + 平均评审时延=review ts−submitted_at）；**②UI 增强**：面板55 加评审统计条 / 状态筛选页签（全部/pending/approved/rejected/landed）/ 行内操作（批准选中入表单、拒绝 prompt 理由、被拒重新提交）/ core 双评审徽标+票数 / 值界展示；面板54 提案表单加 core 复选框 + 值界输入；新增 `POST /api/ecosystem/resubmit`、GET 增 `review_stats` 段；smoke 13/13、报告 10/10 |
| D-97 | **生态共建进一步 · 评审门槛再扩展（ReviewPolicy）+ 多提案批量评审（D-96 之上）** | **①可配置评审策略**（`lda_pdk/submit.py`：`ReviewPolicy` dataclass + `get_policy`（env `LDA_REVIEW_*` 可调 + 显式 overrides）+ `policy_info`；默认保持 D-95/D-96 行为不变）：**提交期预检**（enforce_positive_tol / enforce_nonempty_params / value_min>value_max 即拒 / enforce_value_bounds 强制声明值界）；**评审期门槛**（authorized_reviewers 评审人白名单 / min_source_length ORACLE 最短源码）；**strict_dedup 严格防重**（token 集比较，"n_g·L"≡"n_g*L"）；**min_quorum**（core 双评审基准数可配）；**②多提案批量评审**（`review_proposals_batch(entries)` 逐条同门禁 + 汇总；`land_proposals_batch(ids)` 批量落地）；**③UI 增强**（面板55：提案表加复选框多选 + 全选/清空 + "批量拒绝选中"/"批量落地选中" + 策略显示条；后端 `POST /api/ecosystem/review_batch|land_batch`、GET 增 `review_policy` 段）；实测：批量拒绝 2/2、批量批准 2/2、批量落地 2/2（harness 自动 18→**20 题 20/20 PASS**）；smoke 14/14、报告 10/10 |
| D-98 | **生态共建收官 · 评审流端到端发布（Publish，D-95~D-97 之上）** | 评审流端到端最后一环：landed ORACLE 固化为**正式版本控制补丁 + Release Notes 草稿**（`lda_pdk/publish.py`：`publish_proposal`——仅 landed 可发布、须具名发布人、确定性重编译自测（死标量门禁）、difflib 生成 golden.py/benchmarks.py 的**可 git apply unified diff**（EOF 追加：ORACLE 函数 + `_GOLDEN_DISPATCH`/`_PHYSICAL_LAW` 注册 + `BENCHMARK_DEFS` 条目 + ORDER）、写 `reports/patches/{bid}.publish.patch` + `{bid}.RELEASE.md`、状态 landed→published、审计追加 publish；`list_published`）；**完整生命周期**：提案→评审→落地（自动纳入回归）→**发布**→维护者 git 合并；WebUI 升级至**五十六面板**（面板56「评审流端到端 · 发布」：状态机概览 pending→approved→landed→published + 可发布列表+发布表单 + 已发布基准列表；后端 `POST /api/ecosystem/publish`、GET 增 `published`/`publish_pending` 段）；实测：完整链 publish、缺发布人拒、非 landed 拒、补丁双段 unified diff（33 行）+ Release Notes 落盘、审计 review→land→publish；smoke 12/12、报告 10/10；**诚实边界：发布不改源文件、不做 git commit——补丁经维护者 `git apply` 合并后方成为权威版本控制内容** |
| D-62 | **实证大数据锚（验证的第二道非 AI ground · 发动期联动框架落地）** | 实证锚与物理定律锚并列构成验证的两道**非 AI ground**：harness 新增 **E1-E3 实证锚题**（`benchmarks.py`：oracle=empirical-measurement、golden 来自实测语料库 `seed_empirical.json` + 社区落库增量，非解析函数；`verification_adapters.build_harness_specs`/`harness.py` 实证锚分支，无 anchor 时**诚实降级不判 PASS**）；**语料评审流**（`lda_pdk/empirical.py`：`submit_measurement`（citation 必填=可追溯来源、数值有限、σ≥0、防重）→ `review_measurement`（具名人工评审，LLM 不进判决路径）→ `land_measurement`（写 empirical_contributions.json + reload 进语料库，harness E 题实时生效））；WebUI 升级至**五十七面板**（面板57「实证大数据锚」：语料库统计+逐条溯源+E 题 golden+判题演示+语料提交流；`GET /api/empirical` + `POST /api/ecosystem/measurement`）；实测：E1-E3 golden=2.63/1.53/9.15、参考候选 21/21 PASS（B18+E3 双 ground）、扰动 10% FAIL 检测、语料提交→评审→落地→reload 生效；smoke 17/17、报告 6/6；**诚实边界：种子语料为公开文献/PDK 量级；真实晶圆厂 NDA 流片实测属发动期联动，经「具名人工评审→落库」流持续流入（管道先建好）** |

## WebUI（五十七面板，设计闭环可视化）

LDA 自带零依赖 WebUI（`python lda/lda_webui/deploy.py start`，默认 `http://127.0.0.1:8787`），首屏自动演示全部闭环：

`①求解器验收` `②1D FDTD` `③Mie` `④FDFD` `⑤耦合器验收` `⑥统一 IR` `⑦TMM` `⑧B 基准题` `⑨版图流水线` `⑩Bootstrap` `⑪多层验证` `⑫对抗基准` `⑬器件库（含量子双验证）` `⑭设计→验证闭环` `⑮环形 add-drop 产品链路` `⑯agent 逆设计框架` `⑰量子逆设计闭环` `⑱WDM 多环系统` `⑲readout 混合链路` `⑳统一设计包` `㉑N-qubit 频率复用读出` `㉒单发读出保真度预算` `㉓N-qubit 逐 qubit 保真度` `㉔WDM×readout 混合巨型系统` `㉕方向耦合器设计闭环` `㉖耦合器×WDM（标定库驱动：gap/波长/全网格三模式）` `㉗方向耦合器×量子读出（分束网络供电控制线）` `㉘分束网络×WDM（解复用→每信道分束树）` `㉙伴随法拓扑逆设计（主权 adjoint FDTD）` `㉚逆设计接入设计→验证引擎（method=adjoint）` `㉛真实版图基元库（foundry-ready）` `㉜端口 S 参数验收（MMI 2D FDTD + ORACLE 对拍）` `㉝3D 端口 S 参数验收（SOI 220nm · numba 核）` `㉞光栅耦合器端口验收（光栅方程 ORACLE）` `㉟真实基元接入设计流水线（Track B 收口）` `㊱热光可调 WDM（热光相位 shifter + 物理定律锚）` `㊲量子门/纠错拓扑（surface code + cross-resonance）` `㊳大规模系统基准（WDM 8×qubit 8 联合压测 + 容量/IL/间隔/网格边界）` `㊴L0 IR 开放标准（规范+JSON Schema 零漂移校验）` `㊵验证合约工业化（CI 全量回归 + 性能基准）` `㊶谱形目标逆设计（分束比/模式匹配/多波长谱形 FOM）` `㊷形状逆设计 + 多目标联合（宽度曲线控制点 + Pareto 前端）` `㊸形状+拓扑混合逆设计（分层表达：形状主干 + 拓扑微调带）` `㊹混合×多波长加权联合（参数化×目标矩阵全打通）` `㊺3D adjoint 形状逆设计（3D Yee 显式转置伴随）` `㊻3D 截面形状逆设计（宽度 × 厚度双软边界）` `㊼3D 逆设计 × 端口 S 参数联合验收（双独立确认）` `㊽谱形目标 × 3D 截面（多波长加权联合）` `㊾3D adjoint numba 性能基准（大域 20×+）` `㊿QEDA 求解器级补强 · transmon-resonator 色散读出（三能级严格求解）` `51 QEDA 纵深三件套（多能级展开 · 驱动场 Rabi/AC Stark · 读出串扰 ZZ 耦合）` `52 3D voxel 拓扑逆设计（潜伏密度 + 二值化投影 · 3D 纵深最后一环）` `53 生态共建框架（harness B14-B18 + 主权依赖 A/B/C + Registry 入口）` `54 社区提交入口（器件提交 + 批量导入 + harness 提案 + 贡献库实时列表）` `55 社区评审流 + 提案落地（具名评审 → 确定性自测 → 零接线纳入回归 + git 补丁 · D-96 门槛扩展 · D-97 ReviewPolicy 策略 + 批量评审/批量落地）` `56 评审流端到端 · 发布（landed→published 正式补丁 + Release Notes 草稿 · 全链时间线）` `57 实证大数据锚（实测语料 = 第二道非 AI ground · harness E1-E3 + 语料评审流 · D-62）`

## PDK 标定库（真实 FDTD 实测沉淀，设计时秒级加载）

bus↔ring 耦合本质是方向耦合器——κ_c 由 2D FDTD（D-55 双点标定）实测并沉淀为 PDK 标定文件（一次性后台标定，设计时秒级加载/插值），驱动 WDM 环耦合段设计：

| 标定文件 | 维度 | 说明 |
|---|---|---|
| `lda_agent/data/kappa_calibration.json` | κ_c(gap) 一维 | 5 点 gap 扫描（dl=0.039µm 高分辨率），D-57 |
| `lda_agent/data/kappa_wavelength_calibration.json` | κ_c(λ) 一维 | 3 点波长扫描（gap=0.3 基线），D-59 |
| `lda_agent/data/kappa_grid_calibration.json` | κ_c(gap,λ) **二维** | **9 点全网格**，双线性插值直接查表（D-60，最终形态） |

三种模式（`wdm_coupler` CLI/API 可选，优先级 grid > wavelength > gap 一维），每信道独立 k_ring = sin(κ_c·L_couple)，最弱耦合保守验收；诚实标注 L_couple=2√(2R·gap) 为环形耦合近似，并显式报告 FDTD 校准 vs 解析假设偏差（D-57 实测解析偏乐观 4.6 倍）。

## 统一设计包规范（对外标准 · 11 kind）

- 正式规范文档：[docs/design_package_spec.md](docs/design_package_spec.md)（schema 定义 / kind 注册表 / 校验规则 / 扩展指南）
- 机器可读 JSON Schema：[docs/design_package_schema.json](docs/design_package_schema.json)（draft-07，jsonschema 校验全部 kind conforms）
- kind：`add_drop` `quantum` `wdm` `readout_chain` `multiqubit` `readout_fidelity` `multiqubit_fidelity` `mixed_system` `coupler` `wdm_coupler` `splitter_readout`

## 目录结构

```
lda/                     核心软件包（主权求解器 + agent + 设计引擎 + harness）
  lda_solver/            FDTD/FDFD/Mie/TMM/Transmon/Resonator/Coupler 自研求解器
  lda_agent/             设计→验证闭环、逆设计框架、WDM/readout 系统级设计、AI-dev 写核
  lda_qeda/              量子门库 + surface code + cross-resonance（D-74 QEDA 容错拓扑设计）
  lda_agent/large_scale_bench.py  大规模系统基准（D-75 · WDM×qubit 联合压测 + 边界扫描）
  lda_design/            设计引擎 + 统一设计包规范（DesignPackage）
  lda_ir/                统一 IR（光子+量子，schema v0.3，PhysicsAnchor）
  lda_l2/                器件库（已验证资产）+ GDS 编码器 + DRC + 版图仿真
  lda_harness/           确定性比对裁判（21 题：B1-B18 物理定律锚 + E1-E3 实证锚，可运行时扩展 register_golden + 语料评审流）
  lda_pdk/               生态共建（L2 Registry + 主权 A/B/C + 社区提交 → 评审 → 落地 → 发布 全链）
  lda_webui/             零依赖 WebUI（五十七面板）
  run_ci_regression.py   验证合约工业化·全量回归统一入口（D-77，自动发现 74 smoke）
  run_perf_bench.py      求解器性能基准（D-77，numba/GPU 加速比 + 基线漂移监控）
  run_perf_adjoint3d.py  3D adjoint numba 性能基准（D-89，大域 forward ≥20× + bit-level 一致性）
  lda_solver/port_sparams_3d.py  3D 端口 S 参数核（D-72/86，src_profile 可配源截面）
  lda_agent/port_acceptance.py   3D 逆设计 × 端口联合验收（D-86，双独立确认）
  lda_solver/hybrid_inverse.py  混合逆设计核（D-82/83，形状主干 + 拓扑微调带 + 多波长联合）
  lda_agent/hybrid_design.py    混合逆设计入口（D-82/83，纯形状基线对比 + Pareto 前端）
  lda_solver/adjoint_fdtd3d.py  3D adjoint 逆设计核（D-84，3D Yee 显式转置伴随 + 平板形状）
  lda_agent/adjoint3d_design.py 3D adjoint 设计入口（D-84，FD 对拍 + 优化验收）
  lda_solver/shape_inverse.py  形状逆设计核（D-81，宽度曲线控制点 + 可制造性 DRC）
  lda_agent/multi_objective_design.py  多目标联合（D-81，多波长加权 + Pareto 前端）
docs/                    ir_spec.md + ir_schema.json（L0 开放标准）· design_package_spec.md + design_package_schema.json
```

## 快速开始

```bash
# ① 设计→验证闭环（4 器件：WG/Bragg/Transmon/Ring）
python lda/run_design_demo.py

# ② agent 逆设计通用框架（4 器件同一框架）
python lda/run_inverse_design_smoke.py

# ③ WDM 多环级联系统（4 信道）
python -m lda.lda_agent.wdm_system --channels "1550,1552.5,1555,1557.5"

# ④ N-qubit 频率复用读出（光子-量子混合）
python -m lda.lda_agent.multiqubit_readout --f01s "4.8,5.0,5.2"

# ⑤ N-qubit 逐 qubit 保真度（D-46×D-47 集成，逐 qubit T1）
python -m lda.lda_agent.multiqubit_fidelity --f01s "4.8,5.0,5.2" --t1_us "20,15,25"

# ⑥ 混合巨型系统（光子 WDM 分波 + 量子读出同一网表）
python -m lda.lda_agent.mixed_system --wdm_channels "1550,1553,1556" --f01s "4.8,5.0,5.2"

# ⑦ 方向耦合器设计闭环（目标分束比 → 2D FDTD 标定 → 迭代收敛）
python -m lda.lda_agent.directional_coupler --target_cross 0.5 --gap 0.3

# ⑧ 耦合器 × WDM 组合（FDTD 标定 PDK 文件驱动 gap 选择；--wavelength 波长相关 / --grid 全网格双线性插值）
python -m lda.lda_agent.wdm_coupler --channels "1550,1553,1556" --gap_scan "0.25,0.30,0.35" --grid

# ⑨ 方向耦合器 × 量子读出（光子分束网络供电量子读出控制线）
python -m lda.lda_agent.splitter_readout --f01s "4.8,5.0,5.2"

# ⑩ 确定性比对裁判（21 题：B1-B18 物理定律锚 + E1-E3 实证锚）
python lda/run_harness.py --ai

# ⑪ GPU 实跑激活（L2-B 第三步：CUDA 检测 → 5 例锚 selfcheck → cuda↔cpu bit-equivalent 互证 → 加速比）
python lda/lda_solver/activate_gpu_fdtd3d.py

# ⑫ WebUI（五十七面板，首屏自动演示）
python lda/lda_webui/deploy.py start --port 8787
```

### LDA 命令行（v0.8.30 · 开发者钩子 + gdsfactory 兼容）

安装后可直接用 `lda` 命令感知设计—验证闭环（薄壳复用既有引擎，零新依赖；gdsfactory 为 B 级可选依赖，未装时优雅降级）：

```bash
# ① 跑一个器件设计闭环，输出最优已验证候选（参数/指标/目标误差）
lda design RingResonator --target 9.0 --top-k 3

# ② 把一条链路 JSON 装配成版图，输出 DRC/LVS 双闸报告 + 导出 GDS
lda check examples/cli_check_example.json --out reports

# ②b 导入任意 GDSII（含 gdsfactory 导出），跑 LDA 主权几何 DRC 快查（子集）
lda check --gds my_design.gds --out reports

# ③ 生成基准对照验证闭环报告（跨源死标量对照 + 实证语料覆盖矩阵）
lda report --out reports --quick

# ④ gdsfactory 兼容桥：把 gdsfactory 组件转成 LDA 链路 spec（未装 gf 时给指引）
lda gf my_gf_component.py --out reports
```

`lda check` 接受的链路 JSON 示例（`examples/cli_check_example.json`）：
```json
{
  "domain": "photon", "name": "demo_wg_ring",
  "devices": [
    {"id": "wg1", "kind": "Waveguide"},
    {"id": "ring", "kind": "RingResonator", "params": {"R": 10.0, "gap": 0.3}},
    {"id": "wg2", "kind": "Waveguide"}
  ],
  "nets": [
    {"net": "n1", "from": ["wg1","out"], "to": ["ring","in"]},
    {"net": "n2", "from": ["ring","out"], "to": ["wg2","in"]}
  ],
  "io": [{"net":"e1","device":"wg1","port":"in"}, {"net":"e2","device":"wg2","port":"out"}],
  "sources": [{"device":"wg1","port":"in"}]
}
```
红线：CLI 不做任何判决，仅对既有引擎 / layout / harness 的真实计算结果做格式化呈现（LLM 不进路径，死标量判决不变）。`lda check --gds` 主权 DRC 仅覆盖几何维度**子集**（最小线宽/间距/面积），诚实标注非晶圆厂官方 DRC deck 全量。

## 当前账本：CI 机器断言守护（动态，FAIL=0 即绿）· **CI core 69 条**

- **22 引擎 + 11 包 = 33 类端到端（光子 15 + 量子 7）**
- **46 题（B1-B27 物理定律锚 + E1-E7 实证锚 + S1-S12 系统锚）**
- **创新超市：43 货架（光子 35 开放下载 + 量子 8 咨询制·出口管制合规红线）**
- 主权纪律：A 级永不借（商业 EDA/商业 NDA-PDK）；B 级借今踢后（gdsfactory/Meep/KLayout/SAX fork 主权副本，可选）；C 级第一天自主（L0 IR/L1 协议/L3 求解核/物理定律锚）。
- 诚实边界：当前属**原理验证级非流片级**；实证锚为公开文献量级（9 条 DOI 可溯源），真实晶圆厂 NDA 实测仍属发动期。

## 仓库镜像

- GitHub: https://github.com/iduyuhe/LDA
- Gitee:  https://gitee.com/i4hub/LDA

## 变更记录

见 [CHANGELOG.md](CHANGELOG.md)（v0.2：设计→验证闭环引擎 + 统一设计包规范；**v0.3：GPU 激活 + 量子读出最终形态 + 混合巨型系统**；**v0.4：真实版图基元 + 2D/3D 端口 S 参数验收 + 伴随法逆设计 + 流水线真实化**）。

## 参与共建 · 反向悬赏

LDA 把「真实测量 + 开放对抗题」作为信任地基（对抗纯 AI 互证）。欢迎社区 / 退休专家 / 学生
提交**实测语料**与**让 AI 求解器翻车的对抗题**：

- 提交通道：`New Issue → 实测语料提交` / `对抗基准题提交`（结构化模板）
- 悬赏与评审机制详见 [BOUNTY.md](BOUNTY.md)
- 征集字段与 `lda/lda_harness/seed_empirical.json` 完全对齐

## 双引擎招募（学生 + 退休专家）

LDA 开源生态靠**双引擎**驱动——有时间有热情的**学生**、有资源有情怀的**退休专业人士**。完整招募入口、布点、话术与顾问委员会架构见 [**RECRUIT.md**](RECRUIT.md)：

- 学生线（毕设/竞赛/科研挂钩、good-first-issue）→ [LDA_学生贡献者招募方案.md](LDA_学生贡献者招募方案.md)
- 退休专家线（EDA 老炮/光电退休研究员/院士级，分层顾问委）→ [LDA_退休专家招募话术与顾问委员会架构.md](LDA_退休专家招募话术与顾问委员会架构.md)

## 项目介绍物料（对外一整套）

想快速了解 / 转发 / 触达不同对象，直接用这套分受众物料：

- **总览**：[LDA_项目介绍.md](LDA_项目介绍.md)（定位/证据/路线图/参与方式 + 全文档索引）
- 一页纸·技术贡献者：[LDA_一页纸_技术贡献者.md](LDA_一页纸_技术贡献者.md)
- 一页纸·双引擎招募：[LDA_一页纸_双引擎招募.md](LDA_一页纸_双引擎招募.md)
- 一页纸·合作对接（晶圆厂/合作方）：[LDA_一页纸_合作对接.md](LDA_一页纸_合作对接.md)
- 一页纸·产业投资：[LDA_一页纸_产业投资.md](LDA_一页纸_产业投资.md)
- **技术向·器件开发实操手册**：[中文版](LDA_器件开发实操手册_MMI_Transmon.md)（MMI + Transmon + 逆设计 三案例，真实运行产出）· [English](LDA_Device_Dev_Handbook_EN.md)
- **市场向·同类产品对比**：[LDA 与同类产品对比手册](LDA_同类产品对比手册.md)（商业/开源/量子 Q-EDA 四类对比 + 差异化定位）· [English](LDA_Product_Comparison_EN.md)
- **在线阅读（GitHub Pages）**：<https://iduyuhe.github.io/LDA/>（门户 + WebUI 实测截图）

## 许可证

[MIT](LICENSE)

贡献者署名见 [AUTHORS](AUTHORS.md)（社区评审流收录机制见 [BOUNTY](BOUNTY.md)）。
