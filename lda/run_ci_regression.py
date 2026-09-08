"""D-77 · 验证合约工业化 —— 持续集成全量回归统一入口。

把 LDA 全部验证（130 个 run_*smoke*.py + run_harness.py B1-B18+E1-E3）收敛到
**一条命令、一份机器可读报告**——降低社区协作门槛（新贡献者/第三方跑
`python run_ci_regression.py` 即可看全量回归红绿），对齐 D-04 三套裁判统一。

特性：
  - 自动发现 `lda/run_*smoke*.py` + `run_harness.py`（新增 smoke 零配置纳入）；
  - 每项独立子进程（隔离环境，崩溃不影响他者）+ 超时保护 + 输出尾部捕获；
  - **SKIP 语义**：退出非 0 且输出含 SKIP/无 GPU/无 numba 等优雅降级标记
    → 记 SKIP（非 FAIL），区分"环境缺失"与"真失败"；
  - `--tag core`：内置 CI 安全集（纯 numpy 快速，ubuntu CI 可跑）；
    `--tag all`（默认）：全量（重 FDTD / GPU 项本机或 venv 跑）；
  - 输出：JSON 报告（机器可读，供 CI 解析/趋势）+ 人类可读汇总表。

验收（死标量）：FAIL=0（真失败清零）→ 回归绿；SKIP 不计失败但逐条列出原因。
LLM 不进判决路径。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from typing import Any, Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = _HERE          # 本脚本位于 lda/（包根）

# CI 安全集：纯 numpy 快速 smoke（对齐 .github/workflows/ci.yml 已挑选步骤 +
# D-73~D-76 新增解析模型/标准 smoke）。重 FDTD/GPU 项（sparams/adjoint/
# wdm_coupler 标定等）走 --tag all 在本机/venv 跑。
CORE_SMOKES: List[str] = [
    # 裁判 + 标准题
    "run_harness.py",                        # B1-B13 物理定律锚 + E1-E3 实证锚（21 题）
    "run_benchmark_falsifiability_smoke.py",  # 反自证桩护栏：独立候选数 + 10% 扰动必 FAIL（v0.9.14 P0-1，84→85）
    # 🔴 v0.9.37（T-7）：一键复现入口 quickverify 自身守护——正向环境 OK +
    #   反向（注入 blocked 模拟缺依赖）必须报 missing + 版本核对非空。
    #   秒级（不跑子进程验证，那部分由 quickverify 主模式覆盖）。core 94→95。
    "run_quickverify_smoke.py",
    "run_mcp_smoke.py",                      # L1 协议层（MCP 工具路径，D-104 入 core）
    "run_l1_agent_smoke.py",                 # L1 协议层全链路（KernelGateway + L0 IR + candidate，D-105 入 core）
    "run_agent_loop_smoke.py",               # agent 自迭代设计闭环（DesignAgent「AI for AI」最小实证，D-106 入 core）
    # IR / 谱形 / 环形（纯 numpy）
    "run_ir_d05_smoke.py", "run_ir_ring_smoke.py", "run_ir_spec_smoke.py",
    "run_spectrum_loop_smoke.py", "run_ring_fdtd_smoke.py",
    "run_ring_double_verify_smoke.py",
    # 器件库 / 版图 / DRC / 流水线
    "run_device_fdtd_smoke.py", "run_dc_transmission_smoke.py",
    "run_device_library_smoke.py", "run_gds_smoke.py", "run_drc_smoke.py",
    "run_layout_sim_smoke.py", "run_drc_fix_smoke.py", "run_drc_pdk_smoke.py",
    "run_pipeline_smoke.py", "run_pipeline_multidevice_smoke.py",
    "run_pipeline_realize_smoke.py", "run_primitives_smoke.py",
    "run_gc_smoke.py", "run_coupler_band_smoke.py",
    "run_d06_smoke.py", "run_d10_smoke.py", "run_pdk_smoke.py",
    # Track D / 标准层（D-73~D-76）
    "run_tunable_wdm_smoke.py", "run_qeda_topology_smoke.py",
    "run_large_scale_smoke.py",
    # 工业化验证（D-76：FAIL 检出机制 + 性能基准——坏 smoke 残留根治的守卫）
    "run_ci_industrial_smoke.py",
    # 生态共建链（D-93~D-98：harness 扩展 / 提交 / 评审→落地→发布，纯 numpy 快速）
    "run_ecosystem_smoke.py",        # harness B1-B18 + 主权 A/B/C + Registry 自检
    "run_ecosystem_submit_smoke.py", # 社区提交入口（器件 + 批量 + 提案）
    "run_ecosystem_publish_smoke.py",# 评审→落地→发布 全链（含补丁生成）
    # 实证大数据锚（D-62：harness E1-E3 实证锚题 + 语料评审流，纯 numpy 快速）
    "run_empirical_anchor_smoke.py",
    # 实证语料库入口（D-66 入 core）：ci.yml 自 v0.9.8 起一直跑它，但**本地 core 未收录**
    # → D-63 引入的相对导入 bug 让 GitHub 主干红了多个版本而本地全绿（典型「宣称全绿、
    # 主干红」）。入 core 后该类缺口由本地门禁兜底。以子路径调用（cwd=lda/）。
    "lda_harness/run_empirical_bank.py",
    # 来源边界合规审计（D-63：语料 A/B/X 溯源分级 + 锚题溯源状态，秒级）
    "run_provenance_audit.py",
    # WebUI 路由层（D-102：全端点静态 + 快路径实跑，秒级）
    "run_webui_api_smoke.py",
    # P1 芯片级补强（链路框架 + 自动布线 + Agent 元编排 + 双 ground 上提，纯 numpy 快速）
    "run_link_m1_smoke.py", "run_link_m2_smoke.py", "run_link_m3_smoke.py",
    "run_link_m4_smoke.py",
    # P1-M4 补强：芯片级设计验收标准（四锚 A-D 死标量）
    "run_chip_acceptance_smoke.py",
    # 器件库主流封口（v0.8.7：MMI/光栅/方向耦合/可调 transmon/读出配对/CZ 门）
    "run_kernel_seal_smoke.py",
    # 仿真级芯片设计闭环演示（任务 256：WDM 收发 + 量子读出链路双案例）
    "run_chip_design_demo.py",
    # 流片级验证管道（门3 接口细化：PDK→DRC→工艺角→实测回流）
    "run_tapeout_smoke.py",
    # 🔴 v0.9.60：流片**全链路收口**——S3.5 寄生 / S3.6 几何 DRC / S3b 性能角 /
    #   S4 LVS 四段「在管道里真跑起来」的端到端证据（旧 tapeout smoke 只覆盖了
    #   S1-S3 参数级 DRC，四段重路径无端到端断言）。15 判据，每条配反向个案，
    #   含 v0.9.33 层次化零元素假绿防回潮。实测 0.23s。CI core 136→137。
    "run_tapeout_fullchain_smoke.py",
    # 计数一致性门禁（v0.8.10：引擎/包/题库/CI 条数 vs README 宣传串机器断言，防计数漂移根治）
    "run_count_consistency_smoke.py",
    # 🔴 v0.9.31（T-6）：requires-python 声明下限 ≥ 代码实际语法下界（PEP 701 跨行
    #   f-string 须 3.12+）。静态扫描 lda/**/*.py 的 JoinedStr 跨行节点，断言声明不谎报。
    #   防「声明可装 3.11 实则 3.12 才跑得起来」的对外硬阻塞。实测 <2s。
    "run_requires_python_smoke.py",
    # 基准对照验证闭环报告（v0.8.11c：15 引擎解析锚 rel + 实证语料覆盖矩阵 + ORACLE 状态）
    "run_benchmark_crosscheck_report.py",
    # 芯片级版图导出增强（v0.8.11d：IO 光栅接入 + 版图统计 + 芯片级 DRC 正负例）
    "run_chip_layout_smoke.py",
    # 🔴 v0.9.33（P0-1）：层次化 GDS 导出。重复单元 → cell + AREF（CPO 250k
    #   实测 897,600 元素/97.45MB → 331 元素/36KB，降 99.96%）。判据含
    #   **几何零丢失**（最危险失败模式是压缩时悄悄丢几何，元素数变小反而
    #   更像"成功"）、非规则设计回退 flat 逐字节一致、DRC/LVS 判决不受影响。
    #   反向测试：删一个 cell 几何 ⇒ 判据精确报 74 个缺失。实测 ~10s。
    "run_hier_gds_smoke.py",
    # 🔴 v0.9.32（P0-0）：IO 光栅耦合器几何定位。此前 boundary 分支漏加端口
    #   偏移 ⇒ 光栅齿全堆局部原点（CPO 250k 有 174,080 个齿错位、占元素
    #   19.4%），而体积/元素数断言因器件主体走 path 恒 PASS，缺陷潜伏至今。
    #   判据 A/B/C/D 经反向测试（缺陷态 5/10 亮红）证明会响。实测 <5s。
    "run_io_grating_offset_smoke.py",
    # loss/效率类引擎（v0.8.11e：实证锚 9 条语料全对照 + 物理合理性）
    "run_loss_engine_smoke.py",
    # 系统级锚（Phase 0 · Merge-0：S1 功率预算 + 防自证负例）
    "run_system_budget_smoke.py",
    # 链路损耗感知（Merge-1a：Waveguide/MZI 可选损耗 + 预算报告）
    "run_link_loss_smoke.py",
    # 性能漂移角扫（Merge-1b：⑥审计落地，光子/量子按域角 + 死标量判决）
    "run_corner_performance_smoke.py",
    # 有源双出口（Merge-2a：相移器/调制器设计量+行为黑箱，22 引擎）
    "run_active_device_smoke.py",
    # B28 MZM 调制器半波电压 Vπ 锚（v0.9.1 · 钉子 D1b=A · 双算法互证守卫）
    "run_b28_modulator_vpi_smoke.py",
    # 模型精度分级（Merge-3a：L0/L1/L2 诚实标注 + 升迁机制）
    "run_model_class_smoke.py",
    # 层级 IR（Merge-3b：子系统 flatten 等价性）
    "run_hierarchy_smoke.py",
    # 开发者 CLI 钩子（v0.8.29：lda design/check/report 薄壳三命令）
    "run_cli_smoke.py",
    # gdsfactory 兼容桥 + GDS 主权几何 DRC（v0.8.30：生态互通 + 计数守护固化）
    "run_gdsfactory_bridge_smoke.py",
    # 版图几何级 RC 寄生估算（v0.8.31：设计侧主权闭环收口 S3.5）
    "run_parasitic_rc_smoke.py",
    # 🔴 v0.9.60：几何级 DRC 语义——旧度量把「多边形细分步长」当线宽（Y 分支
    #   0.039µm 假红）、min_width_ok/min_spacing_ok 两个标志恒 True（假绿）、
    #   间距剪枝要求 bbox 重叠致真违规漏检。11 判据含反向。实测 0.18s。
    #   CI core 135→136。
    "run_gds_drc_semantics_smoke.py",
    # BraggMirror GDS 导出收口（v0.9.61）：侧壁调制布拉格光栅波导几何可导
    #   出、几何 DRC 不假红（同层相接连通域豁免）、寄生可跑、诚实边界
    #   （n_eff 来自平面波导求解器 < 体材料 3.48，≠ 器件库一维 TMM 锚）。
    #   反向 A/B：窄波导与近距独立结构必须被抓。CI core 137→138。
    "run_bragg_gds_smoke.py",
    # WebUI 流片签核 / 几何 DRC 端点接线（v0.9.62）：/api/tapeout + /api/geometry_drc
    #   消费 tapeout_pipeline.run_tapeout_pipeline / gds_drc.check_geometry（真实主权内核，
    #   非副本）；正向实跑 GDS 生成→S3.5 寄生/S3.6 几何 DRC，反向极细波导必触发 FAIL。CI core 138→139。
    "run_webui_tapeout_drc_smoke.py",
    # 产品级基准对照库（v0.8.32：实证锚产品级扩展 + B 生态播种，免流片）
    "run_golden_product_smoke.py",
    # 🔴 研发生产系统（M3 · v0.9.41 补登）：解析《2027 产品规划》→ 四赛道生产任务
    #   全跑通（A5/B4/C4/D4）→ 反向验证护栏 → 断言任务全 done + golden 库不破 +
    #   货架全锚定 + 定价无缺口。含 **D-67 能量守恒 / Q-D67 密钥率上界 / P-CPO
    #   间距几何下界** 三道反向测试（注入回归必须命中，否则判护栏失效）。
    #   ⚠️ 血案：本 smoke 自 M3（v0.9.39）建成起一直**未注册进任何 CI 集**，
    #   而设计文档与 memory 均记载「进 CI 防回归」⇒ 生产链路 17 任务长期裸奔，
    #   坏了不响。典型「标签≠行为」（文档说有门禁 ≠ 门禁真在跑）。
    #   今补登为 CORE 常驻，杜绝「写了 smoke 却没接线」的静默缺口。实测 ~30s。
    "run_production_smoke.py",
    # 对照报告飞轮（v0.8.30：多源死标量对照 + 历史归档 + 覆盖度趋势）
    "run_crosscheck_flywheel_smoke.py",
    # Phase 3 统计锚（S7/S8 蒙特卡洛分布 + 收敛性：红线 + 防自证负例）
    "run_statistical_anchor_smoke.py",
    # Phase 4 提案编译器（生成侧：锚前置剪枝 + 即提即验 + 人终审）
    "run_proposal_compiler_smoke.py",
    # 系统类型注册表（v0.8.33：link/wdm_demux/quantum_fidelity 分发，复用已验证闭环）
    "run_system_types_smoke.py",
    # 创新超市货架（v0.8.34：前瞻预研货架 · 组合已锚定基元 + 公开信号驱动，红线下护栏）
    "run_innovation_market_smoke.py",
    # 第二梯队-1 A* 布线（贪心→全局最优 + 避障 + 无解诚实退化）
    "run_astar_route_smoke.py",
    # B1 批量并行布线（v0.8.44：route_batch 语义一致 + 收益边界 + 诚实拒绝）
    "run_parallel_routing_smoke.py",
    # P1 全量自动布线器重写（v0.9.52：空间索引+局部窗口 A*+增量占位，
    #   根除旧 router O(N^3.57) 增量瓶颈、实测 O(N^2.59)→O(N^1.16)、正确性零回归）
    "run_router_p1_smoke.py",
    # torch/numba 可选依赖反向护栏（v0.9.53：fdtd3d_numba/fdtd3d_torch 模块级 import
    #   改为优雅降级，核心导入链不再硬依赖 torch/numba；屏蔽环境子进程反向验证）
    "run_torch_numba_optional_smoke.py",
    # B5/B7 回退下限反向护栏（v0.9.53：ORACLE 全不可用时回退设计守则锚下限
    #   B5=3.0dB / B7=-40.0dB 须精确持有+诚实标注 design-anchor；ORACLE 在场须绕开下限）
    "run_b5b7_rollback_floor_smoke.py",
    # 第二梯队-2 三件套（多端网 Steiner + 2D 放置 + 有源基元）
    "run_second_tier_smoke.py",
    # LVS 签核（v0.8.24：版图-原理图一致性 · 签核级 · 版图差距 #5 + S9 锚）
    "run_lvs_smoke.py",
    # LVS 短路检测宽相等价护栏（P0-2b · v0.9.36：几何均值 cell 退化根治守卫）
    #   生产 _collect_cross_shorts（线段网格宽相）vs naive O(n²) 双重循环真值
    #   逐字节一致。防「提速改 cell 却悄悄改变短路集合」的静默回归（铁律：
    #   没被验证过的护栏不算护栏）。覆盖单集合/跨层/共享端点/长跨/狭长阵列
    #   含反例。实测 <60s（elongated 800 行 naive 超时会止步 200 行）。
    #   🔴 教训：根级 verify_lvs_cross_equiv.py 曾内嵌旧标量 cell 副本、
    #   根本没测生产代码 ⇒ 护栏必须测真实现，不是「看起来像实现」的副本。
    "run_lvs_cross_equiv_smoke.py",
    # 千器件规模扩展（v0.8.26：版图差距 #7 收官 · S11 规模锚）
    "run_scale_smoke.py",
    # 千器件芯片级演示（v0.8.27：千器件版图接入演示 · GDS/DRC/LVS 双闸）
    "run_chip_scale_demo.py",
    # CPO 共封装光引擎阵列（v0.8.47 · 阶段2：十万级真实器件样例——
    # 层次化器件构成 + 参数由谐振条件反解 + 端口线对齐零跳线几何 + 正反例双验）
    "run_cpo_array_smoke.py",
    # CPO 阵列规模纵深守护（v0.9.2 · 25 万器件实跑 + 近线性预算守卫，防回归 O(n²)）
    "run_cpo_array_scale_smoke.py",
    # 商务闭环（v0.9.0：创新超市商业化链路——注册/下单/凭证/审批/下载限次/
    # 对公申请/定制状态机/我的模块/账号重置/意见收集，函数级快速回归）
    "run_store_flow_smoke.py",
    # ---- 量子侧（QEDA）回归（v0.9.1 · P0-1 · 解除 R1）----
    # 背景：量子占 7/22 引擎、13/47 锚，但此前 9 个量子 smoke 全不在 core 门禁，
    # 导致双引擎的一半无回归保护。实测 9 个全部 PASS，其中 7 个为亚秒级、
    # 2 个含 FDTD 仿真约 180-200s —— 全部纳入，慢的两项配 timeout override。
    "run_ir_quantum_smoke.py",            # L0 IR 量子子集
    "run_quantum_devices_smoke.py",       # 量子器件库
    "run_quantum_design_smoke.py",        # 量子设计闭环
    "run_multiqubit_smoke.py",            # 多比特系统
    "run_multiqubit_fidelity_smoke.py",   # 多比特保真度（D-46/D-47 路径）
    "run_readout_fidelity_smoke.py",      # 读出保真度
    "run_readout_chain_smoke.py",         # 读出链路
    "run_splitter_readout_smoke.py",      # D-63 方向耦合器×量子读出（含 FDTD，~198s）
    "run_splitter_readout_cal_smoke.py",  # D-66 标定版读出（含 FDTD，~179s）
    # ---- 2D 半矢量本征模求解器（v0.9.23 · P0 自证）----
    # E2 由「降级量级参考」升为「严格独立候选」的**凭据守护**：没有它，升级所依据的
    # 「窗口散射 <1e-5」「实证对照 Δ=8.4e-5」两条实测就只是 note 里的散文，
    # 改网格/窗口/ARPACK 参数会静默失效（铁律：没被验证过的护栏不算护栏）。
    # 含 5 次 2D 本征解，实测 ~89s ⇒ 配 timeout override。
    "run_semivec_mode_smoke.py",
    # 🔴 v0.9.26：EME 锥度求解器（B8 候选）自校锚，9 条含 3 条收敛扫描，实测 ~33s。
    #   （注：v0.9.24 曾要求新慢 smoke 入 CORE 时登记
    #   `run_ci_industrial_smoke._SLOW_CORE` 以撑住内部嵌套子回归；v0.9.28 起
    #   industrial 不再嵌套重跑全量 core，该机制已废弃，无需再登记。）
    "run_eme_taper_smoke.py",
    # 🔴 v0.9.27（T-1）：判据 D 常驻护栏（代数恒等 vs 真数值离散化）。
    #   现行行为判据拦不住「数学等价的另一种写法」（实测反例 B28：沿程积分
    #   与闭式均匀段剖分守恒 ⇒ 残差恒 4.44e-16 但扰动同步响应 ⇒ 会被误判
    #   独立候选）。本 smoke 守护 candidate_discretization_responds（定义于
    #   lda_harness/harness.py 单一定义处）+ 全 20 道基线残差普查。实测 ~15s。
    #   （v0.9.24 的「入 CORE 须登记 _SLOW_CORE」铁律已于 v0.9.28 废弃：
    #   industrial 不再嵌套重跑全量 core。）
    "run_d_criterion_smoke.py",
    # 🔴 v0.9.28（T-2）：B28 数值零点拟合候选护栏（判据 D 双对照：nullfit
    #   收敛 vs 沿程积分代数恒等）。实测 ~3s。
    "run_b28_nullfit_smoke.py",
    # ---- Lindblad 门保真度求解器（v0.9.24 · P0 自证）----
    # B10 接线 + golden 语义修正（D-66 第 8 例）的**凭据守护**：没有它，
    # ①「旧式 exp(−t(1/T1+1/(2T2))) 已被证否」②「tol 由 0.01 收紧到 1e-8 后
    # 六路扰动信号仍全部可抓」这两条就只是 note 里的散文，下次有人把 golden
    # 改回旧式、或把 tol 放宽，都会静默失效（铁律：没被验证过的护栏不算护栏）。
    # 纯 4×4 矩阵运算，实测 <3s。
    "run_lindblad_gate_smoke.py",
    # 🔴 v0.9.39（T-9）：B29 热光相移效率 / B30 读出保真度 两道真·可接空白点锚护栏。
    #   各 4 判据（登记防回退 / 正向 PASS / 判据 D 单调收敛+基线>1e-12 / 反向必 FAIL），
    #   镜像 run_b28_nullfit_smoke。实测均 ~3s。CI core 95→97。
    "run_b29_thermal_phase_smoke.py",
    "run_b30_readout_smoke.py",
    # 🔴 v0.9.51（任务②corpus 失真区升格）：E8/E9 实证锚进 52 题集 + 十处定时炸弹动态化。覆盖死角闭合护栏（v0.9.50 任务①）。把 PhaseShifter/readout_fidelity
    #   + 3 复合包的「覆盖闭合」从文档散文变成机器可验证死标量断言（B29/B30 已 strict 且登记宿主、
    #   3 复合包组成严格锚 B14/B4/B22/B26 + S1-S13 + GC-* 覆盖 link/quantum_fidelity、零覆盖集恰为
    #   3 复合包、反向撤 B29 必回落）。~2s，无重依赖。CI core 127→128。
    "run_coverage_deadzone_closure_smoke.py",
    # 🔴 v0.9.41 门禁缺口清零：以下 18 项为审计实测「<1.3s + 纯 numpy（无
    #   torch/numba/cupy/meep/tidy3d）+ 失败会 return 1 的真门禁」，却从未进过
    #   core ⇒ 与 production smoke 同类静默缺口。合计仅 **9.6s**，无理由豁免。
    #   其中含 4 条**锚 smoke**（mzi/qres/fluxonium/transmon_double_verify）——
    #   锚失真是最危险失败模式（v0.9.10 漏算 3.0103dB 在 84 全绿下溜过），
    #   锚不在门禁内 = 失真无警报。core 98→116。
    "run_mzi_anchor_smoke.py",          # MZI FSR × 物理定律锚 B20 死标量比对（unittest 6 断言）
    "run_qres_anchor_smoke.py",         # qubit-resonator 锚（unittest 7 断言）
    "run_fluxonium_anchor_smoke.py",    # fluxonium 锚（unittest 13 断言）
    "run_transmon_double_verify_smoke.py",  # transmon 双路互证
    "run_qeda_depth_smoke.py",          # QEDA 纵深三件套（含负例）
    "run_qubit_resonator_smoke.py",     # qubit-resonator 求解器（含色散区失效负例）
    "run_mixed_system_smoke.py",        # 光-量混合巨型系统（2 正例 + 3 负例）
    "run_ir_solve_smoke.py",            # L0/L3 直接消费 IR 真值计算
    "run_wdm_coupler_smoke.py",         # ⚠️ 文件头旧注称其「重」→ 实测 0.30s，属过时排除
    "run_wdm_coupler_wl_smoke.py",
    "run_wdm_coupler_grid_smoke.py",
    "run_wdm_depth_smoke.py",
    "run_wdm_system_smoke.py",
    "run_api_v1_smoke.py",              # v1 API：租户隔离 / 认证 / 插件安全 / license
    "run_data_layer_smoke.py",          # 多用户数据层：隔离 / API Key / 用量计量
    "run_ecosystem_review_smoke.py",    # 生态共建社区评审流
    "run_ecosystem_review2_smoke.py",
    "run_ecosystem_review3_smoke.py",
    # 门禁覆盖门禁（自食其规则：它自己也在 core 集内，见下方 NON_CORE_SMOKES 注）
    "run_ci_coverage_gate_smoke.py",
    # 失败状态分类门禁（守护 _FAIL_STATUSES 记账：漏登记 = 红灯变绿 = 静默假绿）
    "run_ci_crash_classify_smoke.py",
    # 创新超市分类体系护栏（v0.9.42：标签漏标 / 派生表漂移 / 前端回潮 / facets 计数失真）
    "run_shelf_taxonomy_smoke.py",
    # 上架日期护栏（v0.9.43 · N-1：与 git 历史复算比对，防伪造新鲜度 / 前端漏接）
    "run_shelf_listing_smoke.py",
    # 超市前端登录门禁护栏（v0.9.43 D-78：防「已登录却被要求二次登录」回潮 ——
    #   P2-5 改 HttpOnly Cookie 时废用 store_token 却漏改 4 处门禁的同类改造留半截）
    "run_store_auth_gate_smoke.py",
    # 豁免表理由防腐化护栏（v0.9.46 N-2：理由必须含真实实测耗时，
    #   禁「超时」式搪塞 —— N-2 复测抓到两条旧注「>60s 超时」实为 47.2s/64.3s 完成）
    "run_noncore_reason_smoke.py",
    # stats.html 数据看板接线护栏（v0.9.47：路由白名单 + HttpOnly Cookie 探活显示，
    #   取代可被 XSS 伪造的 localStorage 影子标志；含真跑 + 反向测试）
    "run_stats_nav_wiring_smoke.py",
    # 智能体客服「选择后能真正回复」护栏（v0.9.47：根因 = cs_widget.js addMsg 漏写
    #   return m 致 wait=undefined、removeChild 抛错、回复永远卡「…」；含真跑往返 +
    #   addMsg 必须 return m 静态守卫 + 反向污染测试）
    "run_cs_agent_chat_smoke.py",
    # 管理员令牌 fail-closed 护栏（v0.9.48 N-3：_admin_token() 移除硬编码默认串，
    #   未设 LDA_ADMIN_TOKEN 即返回空串 fail-closed，杜绝漏设环境变量即用公开弱令牌
    #   登录的 fail-open 漏洞；含源码静态查 + 子进程行为 + 起服务登录真跑 + 反向）
    "run_admin_token_smoke.py",
    # 三分类对外一致性护栏（v0.9.48 N-4：README 账本 ≡ 本机 harness 推导 ≡
    #   /api/verification_ledger 端点三分类，任一漂移即红；含反向篡改测试）
    "run_three_class_consistency_smoke.py",
    # 导购二期护栏（v0.9.49 N-5：无 LLM 可降级版；自然语言 → /api/store/guide 对 75 货架
    #   实跑匹配；数字必来自货架数据（price_cny/specs），严禁模板/LLM 杜撰规格数字；
    #   含真跑往返 + 价格真实性核对 + 乱码/空文本优雅返回 + 别名污染失准反向）
    "run_store_guide_smoke.py",
    # L0 IR 逆设计扩面护栏（v0.9.55 ①：IR → D-38 声明式注册表四类已验证器件
    #   闭环 RingResonator/BraggMirror/RingAddDrop/Transmon。含真跑 accepted +
    #   真实 final_params、Bragg 方法一致性<0.1（C 级自主）、反向①未知 kind→
    #   NotImplementedError、反向②篡改注册表删 kind→闭环不通过（路由到真注册表非副本）。
    #   实测 ~20s（Bragg 3D FDTD 终验）。CI core 131→132。
    "run_ir_inverse_design_smoke.py",
    # 🔴 v0.9.57 ②：2D TEz FDTD 求解核 smoke（E5 的**第二条独立求解路线**）。
    #   与 run_mmi_eme_smoke.py 的 EME 路线方法学独立（时域全场 Yee 步进 vs
    #   代数本征模展开），核心判据是**两法在同一离散结构上的对账 |Δ|<0.15 dB**。
    #   同时修正 v0.9.56 的错误结论：那条"2D FDTD 直波导控制实验失败"是**我的
    #   实现缺陷**（scipy eig_banded 对称三对角存储应为 (2,N) 误用 (3,N) ⇒
    #   n_eff 解成 16.18；且入射监测面落在初始波包内部 ⇒ 27% 能量不穿过该面），
    #   不是 FDTD 方法之病。修掉后直波导 10 µm 上 −0.00001 dB。
    #   实测 ~145s（主跑 dl=0.05/t_max=1200 约 62s + 判据 D 两次 dl=0.06 约 78s
    #   + C1 控制实验约 3s + 解析色散预算瞬时）。
    #   CI core 133→134。
    "run_fdtd2d_mmi_smoke.py",
    # 🔴 v0.9.56 ②：MMI 1×2 EME 求解核 smoke（**负结果结论锁**）。
    #   E5（golden 0.05 dB / tol 0.1 dB）两条独立路线探测均实测不合格
    #   （2D FDTD 直波导控制失败；2D-EIM EME 自成像保真度 0.875 + 对 L_π
    #   病态敏感 ±1%⇒2×tol）。本 smoke 11 判据把「求解核是对的」与
    #   「E5 目前确实判不了」**同时钉死**：后者是已知缺口锁，模型够格时
    #   **转红**提醒更新账本。纯 numpy，实测 ~17s。CI core 132→133。
    "run_mmi_eme_smoke.py",
    # 🔴 v0.9.59 治理⑤收尾：可选后端（torch/numba/cupy）模块级硬依赖**全包**护栏。
    #   ① 静态：ast 扫描 lda/ 全包（393 文件）在模块级（非 try / 非函数类体内）
    #      不得裸 import torch/numba/cupy —— 范围是全包而非硬编码清单，新增文件
    #      自动纳入，杜绝「清单会增长 ⇒ 断言静默漂移」的定时炸弹（v0.9.41 铁律）。
    #   ② 动态：屏蔽 torch/numba/cupy 的子进程里 runpy 实跑 4 个顶层 GPU 脚本
    #      （activate_gpu_fdtd3d / run_fdtd3d_torch_selfcheck / run_large_grid /
    #      verify_gpu_focused），断言「打印指引后退出码 2」而非 ImportError 裸崩。
    #   ③ 反向测试 R1（扫描器双向标定：坏样本必被抓 / 好样本必放行）+ R2（顶层
    #      裸 import 的坏脚本必须裸崩，证明步骤②真能区分优雅降级与硬依赖）。
    #   CI core 134→135。
    "run_optional_import_guard_smoke.py",
]

# 🔴🔴 非 core 豁免登记表（v0.9.41 补建）——**没登记 = 门禁缺口**。
#
# 血案（v0.9.41 全量 core 回归后审计发现）：`run_production_smoke.py` 自 M3
# （v0.9.39）建成起就**从未进过任何回归集**，而设计文档、production_plan 注释
# 与项目 memory 三处都写着「进 CI 防回归」⇒ 生产链路四赛道 17 任务长期裸奔，
# 坏了不响。典型「标签≠行为」：文档说有门禁 ≠ 门禁真在跑。
#
# 根因：`_discover_all()` 只负责发现，没有任何机制要求「新 smoke 必须进 core
# 或显式声明不进」。于是扩库时漏接线成为静默默认。
#
# 本表是**唯一合法的不进 core 通道**，且必须附实测理由。准入准则见文件头：
# core = 纯 numpy 快速（ubuntu CI 可跑）。凡实测 <5s 且无 torch/numba/cupy/
# meep/tidy3d 依赖者，**无权豁免**，必须进 core。
#
# 判据由 `run_ci_coverage_gate_smoke.py` 强制（且该 smoke 自身在 core 集内，
# 自食其规则）：lda/ 下每个 run_*_smoke.py 必须 ∈ CORE_SMOKES 或本表，且本表
# 每项理由非空 ⇒ 否则 FAIL。新增 smoke 不接线 = 立刻红。
#
# 实测基准：managed python 3.13，**2026-09-06 N-2 全量复测**（18/18 逐条重跑，
# rc 全 0；复测脚本 probe_noncore*.py，结果在 .cache/noncore_measured.json 与当日日志）。
# 🔴 复测发现两条旧理由失真已修正：sparams_3d 旧称「>60s 超时」实为 47.2s 完成；
#    sparams_loop 旧称「>60s 超时」实为 64.3s 完成（numba 运行时确被依赖链间接载入）。
NON_CORE_SMOKES: Dict[str, str] = {
    # ---- 重仿真（实测 ≥25s，远超 CI 快速集预算）----
    "run_design_outcome_smoke.py": "重仿真：设计闭环全链路，实测 58.2s",
    "run_adjoint_loop_smoke.py": "重仿真：伴随优化迭代循环，实测 55.1s",
    "run_coupler_design_smoke.py": "重仿真：耦合器参数扫描反解，实测 60.3s",
    "run_adjoint_design_smoke.py": "重仿真：伴随法设计，实测 40.0s",
    "run_shape_design_smoke.py": "重仿真：形状优化迭代，实测 31.6s",
    "run_spectral_design_smoke.py": "重仿真：谱响应设计扫描，实测 26.8s",
    "run_adjoint3d_smoke.py": "3D 伴随仿真（重），实测 19.1s",
    "run_sparams_smoke.py": "FDTD 分束仿真（重），实测 25.1s",
    # ---- 中量（5~25s，超出 core 快速预算但非极限）----
    "run_ir_smoke.py": "IR 全量求解回归，实测 21.3s",
    "run_inverse_design_smoke.py": "逆向设计迭代，实测 19.4s",
    "run_hybrid_design_smoke.py": "混合参数化设计扫描，实测 17.2s",
    "run_port_acceptance_smoke.py": "端口验收 3D 判据，实测 10.4s",
    "run_phc_anchor_smoke.py": "光子晶体本征解（ARPACK 迭代），实测 6.8s",
    # ---- 超长（复测均能跑完、非卡死；numba 由依赖链运行时间接载入，仓库无显式 import）----
    "run_sparams_3d_smoke.py": "3D 端口 S 参数仿真（重），实测 47.2s 完成（N-2 复测修正旧注误记的截断描述）",
    "run_sparams_loop_smoke.py": "3D 闭环 + numba JIT（依赖链间接载入，首次编译慢），实测 64.3s 完成（N-2 复测修正旧注误记的截断描述）",
    # ---- 极重设计闭环（判明为「慢」而非「缺陷」后才准豁免；理由须含真实耗时，不得写「超时」了事）----
    "run_wdm_splitter_smoke.py": "重设计闭环：WDM×分束树联合，实测 142.2s 完成（非卡死）",
    "run_design_package_smoke.py": "重设计闭环：4 类设计包 schema 全链路，实测 108.7s 完成（非卡死）",
    "run_hybrid_multi_smoke.py": "重设计闭环：多波长加权联合，实测 69.7s 完成（非卡死）",
}

# D-63 收紧：旧判定只看「输出里是否含未安装/无 GPU 等字样」→ 副作用是把真失败
# 误记成 SKIP（例如断言失败但正文里恰好提到「gdsfactory 未安装」的 PASS 行）。
# 新判定两级：
#   ① 显式 SKIP 行（行首 SKIP / [SKIP] / SKIPPED）→ 无条件记 SKIP；
#   ② 环境缺失短语 → 仅当输出中**没有**真失败痕迹（Traceback / AssertionError /
#      FAIL 行）时才记 SKIP，否则一律 FAIL（宁可红，不可假绿）。
_SKIP_LINE_RE = re.compile(r"^\s*\[?\s*(SKIP|SKIPPED)\b", re.I)
_SKIP_ENV_MARKERS = ("无 GPU", "无gpu", "no GPU", "no gpu", "GPU 不可用",
                     "torch 未安装", "numba 未安装", "not installed",
                     "未安装", "环境缺失")
_FAIL_EVIDENCE_RE = re.compile(
    r"(Traceback \(most recent call last\)|AssertionError|^\s*(FAIL|ERROR)\b)",
    re.M)


def _discover_all() -> List[str]:
    """自动发现 lda/ 下全部 run_*smoke*.py + run_harness.py（去重、排序）。"""
    files = set()
    for fn in sorted(os.listdir(_HERE)):
        if fn.startswith("run_") and fn.endswith("_smoke.py"):
            files.add(fn)
    if os.path.exists(os.path.join(_HERE, "run_harness.py")):
        files.add("run_harness.py")
    return sorted(files)


# 🔴 失败状态全集：任何新增状态（如 CRASH）**必须**登记于此，否则
# `n_fail` 统计不到 ⇒ 红灯变绿 ⇒ 静默假绿。这是「宁红不假绿」的记账底线。
_FAIL_STATUSES = ("FAIL", "ERROR", "TIMEOUT", "CRASH")

# 内置 per-script 超时覆盖（秒）：实测耗时 + 安全边际，防慢机器上偶发 TIMEOUT
# 被误判为 FAIL（TIMEOUT 与真 FAIL 必须区分开）。调用方可通过 timeout_override 再覆盖。
_BUILTIN_TIMEOUT_OVERRIDE = {
    # 内部含子回归 + greens 基准。
    # 🔴 v0.9.24：600 → **900s**（1.5× 余量防慢机器抖动）。历史：v0.9.23 把
    # `run_semivec_mode_smoke.py`（~97s）加入 CORE_SMOKES 时，industrial 当时
    # 内部嵌套重跑全量 core 子集，导致子回归 570s → 667.62s 撑破 600s ⇒ TIMEOUT。
    # 该嵌套重跑已于 v0.9.28 废弃（industrial 改为跑小的固定代表子集，~90s 且
    # 负载无关），900s 余量纯属保守，不含任何判据放宽。
    # ⚠️ 这不是「放宽判据掩盖失败」：TIMEOUT 与 FAIL 是两种状态（见 _run_one），
    # 本项实测单独跑 **3/3 ALL PASS**，是纯耗时问题，不含任何物理/数值判据。
    "run_ci_industrial_smoke.py": 900.0,
    # 含 FDTD 分束仿真，实测 ~198s（v0.9.1 入 core）
    "run_splitter_readout_smoke.py": 400.0,
    # 含 FDTD 标定仿真，实测 ~179s（v0.9.1 入 core）
    "run_splitter_readout_cal_smoke.py": 400.0,
    # 5 次 2D 半矢量本征解（ARPACK shift-invert）实测 ~89s（v0.9.23 入 core）
    "run_semivec_mode_smoke.py": 400.0,
    # v0.9.57：2D TEz FDTD 全场时域（主跑 dl=0.05 t_max=1200 + 判据 D 两次
    # dl=0.06 t_max=900），实测 ~95s ⇒ 配 400s（4× 余量，防慢机器抖动）。
    "run_fdtd2d_mmi_smoke.py": 400.0,
    # 纯 4×4 Liouvillian RK4，实测 <3s；放宽只为慢机器上的解释器启动开销
    "run_lindblad_gate_smoke.py": 180.0,
    # EME 逐片本征解：9 条自校锚（含 dz/模式数/窗口三次收敛扫描），实测 ~33s
    "run_eme_taper_smoke.py": 400.0,
    # 判据 D：20 道基线普查 + B10/B28 双向 + 抽验，实测 ~15s
    "run_d_criterion_smoke.py": 180.0,
    "run_b28_nullfit_smoke.py": 120.0,
    # T-8（v0.9.38）：live 从「无 GPU 即 SKIP（秒级）」变为「CPU 真跑」——
    # DC 全波段 7 波长 123.1s + YB 163.8s ≈ 287s，正好压原默认 300s 线 ⇒ 配
    # 600s（≈2× 余量）。这不是放宽判据：判据一个字未改，只是给慢机器留耗时余量。
    # 2026-09-05 再调：本项曾**两次在 20 线程满载下触发整机硬掉电**
    # （Kernel-Power 41 / BugcheckCode=0 + Kernel-Processor-Power 37 固件限速；
    # 内存 63GB 充足已排除 OOM）⇒ 由 lda_solver/threads.py 把并发压到一半核心
    # （上限 10）降功耗峰值。代价是耗时上升，故预算提到 1200s。
    "run_coupler_band_smoke.py": 1200.0,
    # T-8：5 器件 live 全跑（DC 15.3s / YB 19.1s / WG numba 秒级 / Bragg 19.9s
    # / Ring <0.1s），干净实测 ~60-80s；配 600s 只为 numba 首次 JIT 编译（冷
    # 缓存 ~30s）与慢机器抖动留余量。
    "run_device_library_smoke.py": 600.0,
}


def _child_env() -> Dict[str, Any]:
    """子进程环境：注入线程预算（env 在进程启动时即存在 ⇒ 早于任何内核初始化，
    对 numpy/MKL/numba/torch 全部生效）。

    2026-09-05 血案：20 线程满载跑 3D FDTD 两次触发整机硬掉电（Kernel-Power 41 /
    BugcheckCode=0 + Kernel-Processor-Power 37 固件限速）。压到一半核心（上限 10）
    后实测**反而更快**（全波段 287s → 235s）且判据逐位一致。此处统一注入，使
    **所有** smoke 受益（不只是手动调用 apply_thread_budget 的那两个）。
    """
    import os as _os
    env = dict(_os.environ)
    try:
        from lda_solver.threads import budget_threads, _ENV_KEYS
        n = budget_threads()
        for k in _ENV_KEYS:
            env.setdefault(k, str(n))
        env.setdefault("LDA_FDTD_THREADS", str(n))
    except Exception:                                  # 预算模块不可用 ⇒ 不阻断
        pass
    return env


def _run_one(python: str, script: str, timeout: float) -> Dict[str, Any]:
    t0 = time.perf_counter()
    try:
        p = subprocess.run(
            [python, script], cwd=_HERE, env=_child_env(),
            capture_output=True, text=True, timeout=timeout)
        rc, out = p.returncode, (p.stdout or "") + (p.stderr or "")
        dt = time.perf_counter() - t0
        status = "PASS" if rc == 0 else "FAIL"
        if rc != 0:
            has_skip_line = any(_SKIP_LINE_RE.match(ln) for ln in out.splitlines())
            has_fail_evidence = bool(_FAIL_EVIDENCE_RE.search(out))
            has_env_marker = any(m in out for m in _SKIP_ENV_MARKERS)
            if has_skip_line or (has_env_marker and not has_fail_evidence):
                status = "SKIP"
        tail = "\n".join(out.strip().splitlines()[-4:])
        if status not in ("PASS", "SKIP") and not out.strip():
            # 🔴 2026-09-06 血案：run_coupler_band_smoke 在持续负载下被硬杀
            # （136s 后 rc≠0 且零输出；单独重跑 267s ALL GREEN）。Python 重定向到
            # 管道时 stdout 为块缓冲 ⇒ 被 SIGKILL/掉电干掉则缓冲全部丢失，故
            # 「非零 rc + 零输出」= 进程被外部杀死（OOM / Kernel-Power 掉电 / 热保护），
            # **不是断言失败**。若与断言 FAIL 混为一谈，后人会去"修"物理判据来
            # 对付一次硬件抖动 —— 那是本项目最危险的失真通道（参 v0.9.10 漏算
            # 3.0103dB 血案）。故单列 CRASH 状态，语义：需人工复验，不是判据错。
            status = "CRASH"
            tail = (f"子进程异常终止：rc={rc} 且零输出 —— 多为外部硬杀"
                    f"(OOM/掉电/热保护)，非断言失败。请单独重跑该 smoke 复验。")
        return {"script": script, "rc": rc, "status": status,
                "elapsed_s": round(dt, 2), "tail": tail}
    except subprocess.TimeoutExpired:
        return {"script": script, "rc": -1, "status": "TIMEOUT",
                "elapsed_s": timeout, "tail": f"超过 {timeout}s 超时"}
    except Exception as e:  # noqa: BLE001
        return {"script": script, "rc": -2, "status": "ERROR",
                "elapsed_s": round(time.perf_counter() - t0, 2),
                "tail": str(e)[:200]}


def run_ci_regression(python: Optional[str] = None, tag: str = "all",
                      timeout: float = 300.0, fail_fast: bool = False,
                      exclude: Optional[List[str]] = None,
                      timeout_override: Optional[Dict[str, float]] = None,
                      scripts: Optional[List[str]] = None
                      ) -> Dict[str, Any]:
    """全量/核心回归。返回 {results, summary, acceptance, verdict}。

    timeout_override：per-script 超时覆盖（{脚本名: 秒}）——供特殊重 smoke
    单独放宽时限（如 run_ci_industrial_smoke 内部含子回归+greens 基准，
    约 300-315s 浮动，全局 300s 常顶到边界；覆盖 600s 根治偶发抖动，
    不掩盖其它 smoke 的真实超时）。

    scripts：显式脚本清单（优先级高于 tag）。供「子集契约校验」类调用
    （如 run_ci_industrial_smoke 只跑几个固定快速 smoke 验证回归入口的
    PASS/FAIL 聚合逻辑），避免整段嵌套重跑导致负载诱发抖动。清单内不存在
    的文件会被静默跳过（与 tag 分支行为一致）。
    """
    python = python or sys.executable
    if scripts is not None:
        # 显式清单优先：仅保留当前目录内真实存在的脚本
        scripts = [s for s in scripts
                   if os.path.exists(os.path.join(_HERE, s))]
    elif tag == "core":
        scripts = [s for s in CORE_SMOKES
                   if os.path.exists(os.path.join(_HERE, s))]
    else:
        scripts = _discover_all()
    exclude = set(exclude or [])
    scripts = [s for s in scripts if s not in exclude]
    overrides = timeout_override or {}

    results: List[Dict[str, Any]] = []
    t_total0 = time.perf_counter()
    for s in scripts:
        # run_ci_industrial_smoke 内部含子回归+greens 基准（~300-315s 浮动），
        # 内置放宽至 600s 根治偶发 TIMEOUT；其余 smoke 用全局 timeout。
        to = overrides.get(s, _BUILTIN_TIMEOUT_OVERRIDE.get(s, timeout))
        r = _run_one(python, s, to)
        results.append(r)
        print(f"  [{r['status']:<6}] {r['script']}  ({r['elapsed_s']}s)")
        # 🔴 CRASH 必须在内：新状态若漏进此元组 ⇒ 不计入失败 ⇒ 静默假绿。
        if r["status"] in _FAIL_STATUSES:
            # 故障可见性（2026-09-05 血案）：非 PASS 项必须当场打印子进程 tail，
            # 否则日志只剩一行 FAIL，排查要重跑 30 分钟全量回归才能拿到原因。
            for ln in (r.get("tail") or "(无输出)").splitlines():
                print(f"           │ {ln}")
        if fail_fast and r["status"] in _FAIL_STATUSES:
            break
    total_s = round(time.perf_counter() - t_total0, 2)

    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_skip = sum(1 for r in results if r["status"] == "SKIP")
    n_fail = sum(1 for r in results if r["status"] in _FAIL_STATUSES)
    failed = [r for r in results if r["status"] in _FAIL_STATUSES]
    skipped = [r for r in results if r["status"] == "SKIP"]
    checks = [
        {"name": f"回归通过（{n_pass}/{len(results)}，FAIL=0）",
         "ok": n_fail == 0,
         "detail": f"{n_pass} PASS / {n_skip} SKIP / {n_fail} FAIL"}
    ]
    if n_fail:
        checks.append({"name": "失败项逐条列出（可追溯）",
                       "ok": False,
                       "detail": "; ".join(f"{r['script']}(rc={r['rc']})"
                                           for r in failed[:8])})
    if n_skip:
        checks.append({"name": "SKIP 项原因透明",
                       "ok": True,
                       "detail": "; ".join(r["script"] for r in skipped[:8])})
    passed = n_fail == 0
    verdict = (f"验证合约工业化回归 {tag} 集：{n_pass} PASS / {n_skip} SKIP / "
               f"{n_fail} FAIL，总耗时 {total_s}s"
               + (" —— 全绿" if passed else
                  f" —— 失败项：{'; '.join(r['script'] for r in failed[:5])}"))
    return {
        "ok": True,
        "title": f"CI 全量回归（tag={tag}）",
        "tag": tag, "python": python,
        "n_scripts": len(scripts),
        "summary": {"pass": n_pass, "skip": n_skip, "fail": n_fail,
                    "total_s": total_s, "failed": failed, "skipped": skipped},
        "results": results,
        "acceptance": {"checks": checks, "passed": passed},
        "verdict": verdict,
        "note": ("统一入口自动发现全部 smoke（新增零配置纳入）；SKIP=环境缺失"
                 "优雅降级（无 GPU/numba），FAIL=真失败；LLM 不进判决路径。"
                 "core 集对齐 CI 可跑（纯 numpy）；all 集含重 FDTD/GPU 项。"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="D-77 验证合约工业化 · 全量回归")
    ap.add_argument("--tag", choices=["core", "all"], default="all")
    ap.add_argument("--python", default=None, help="解释器（全量推荐 venv）")
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--fail-fast", action="store_true")
    ap.add_argument("--exclude", default="", help="逗号分隔排除脚本")
    ap.add_argument("--out", default=None, help="JSON 报告路径")
    a = ap.parse_args()
    excl = [x.strip() for x in a.exclude.split(",") if x.strip()]
    r = run_ci_regression(python=a.python, tag=a.tag, timeout=a.timeout,
                          fail_fast=a.fail_fast, exclude=excl)
    print(r["verdict"])
    rc = 0 if r["acceptance"]["passed"] else 1
    if a.out:
        try:
            _d = os.path.dirname(a.out) or "."
            os.makedirs(_d, exist_ok=True)
            with open(a.out, "w", encoding="utf-8") as f:
                json.dump(r, f, ensure_ascii=False, indent=2)
            print(f"[written] {a.out}")
        except Exception as _e:  # noqa: BLE001 —— 报告写入失败不得掩盖判决
            print(f"[warn] 报告写入失败（不影响判决 rc={rc}）：{_e}", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
