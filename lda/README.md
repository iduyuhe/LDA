# LDA 验证锚点 · Verification Harness

阶段 1 第一块真地基（属《MEMORY》「基础工作量力而行原则」①类）。
这是 LDA 验证裁判的**确定性闭环骨架**：把 L0 IR 的 `verification.benchmarks`
与**非 AI 的物理定律黄金参考**挂钩，运行候选求解器输出，按容差判定
pass/fail —— 是「为人结果负责」的质量门。

## 设计哲学（对齐《白皮书》§11 验证锚）
- 黄金参考必须是**非 AI 的确定性物理定律/解析解**——方程的必然，而非某人意见。
- AI 写的内核（L3）输出须逐题对照此处；harness 只做"候选 vs 黄金 + 容差判定"。
- 零外部依赖（仅标准库 `math`），可在任何 Python 3 环境离线运行。

## 已实现标准题（B1–B11，光子 + 量子子集）
| 题号 | 指标 | 锚类型 | 黄金锚 | 容差 |
|---|---|---|---|---|
| B1 | 米氏散射 Q_scat | 物理定律 | Rayleigh 极限 / miepython 完整 Mie | 2e-4 |
| B2 | SOI 波导 n_eff | 物理定律 | 两步有效折射率法 (EIM) | 0.05 |
| B3 | Fabry-Perot FSR | 物理定律 | Airy 公式 | 1.0 nm |
| B4 | 环形谐振器 FSR | 物理定律 | 环形传递函数 / SAX 可选 | 0.3 nm |
| B5 | Y 分支分束损耗 | 场级 ORACLE | numpy 重叠估计(离线) / Meep(生产) | 1.0 dB |
| B6 | 光栅耦合效率 | 场级 ORACLE | Tidy3D 3D（key 门控）/ 设计守则锚 0.5 兜底 | 0.15 |
| B7 | 波导交叉串扰 | 场级 ORACLE | numpy 2D-FDTD(离线,几何相关) / Meep(生产) | 5.0 dB |
| B8 | 绝热锥度效率 | 物理定律 | 绝热极限 T→1 | 0.01 |
| B9 | transmon 跃迁频率 f01 | 物理定律 | √(8·E_J·E_C)−E_C（Koch2007 解析） | 0.05 |
| B10 | 单量子比特门保真度 F | 物理定律 | exp(−t_gate·(1/T1+1/2T2)) 退相干极限 | 0.01 |
| B11 | 环形透射谱"目标谱形"匹配 | 物理定律 | 共振周期 FSR 归一化失配（环形传递函数） | 0.03 |

> B1–B4、B8 为**严格物理定律锚**（麦克斯韦方程的必然，零依赖、确定性）。
> B5/B7 已接入**场级 ORACLE**：默认走纯 numpy 离线求解（Apache-2.0，本环境
> 即跑，几何相关——如 B7 默认几何实测 ≈ -10 dB（离线 2D-FDTD，可复现），随波导宽度变化），配置
> `LDA_MEEP_PY` 后自动切换为 GPL **Meep 子进程**真场级真值（见 `ext_oracle/meep_oracle.py`）。
> B6 为 3D 光栅耦合：已接入 `oracle_tidy3d.py` 作外部 ORACLE（仅当配置
> `TIDY3D_API_KEY` 且环境可 import tidy3d 时真跑 3D 求解，GPL 绝不进核心）；
> 离线无 key 时 `oracle_field.py` 返回 None，`golden.py` 回退设计守则锚 0.5
> 作验收基准——这是「主权优先 + GPL 仅外部 ORACLE」纪律的标准实现。
> 报告"真值来源"列标明每条黄金参考的事实来源（physical-law / meep-fdtd /
> numpy-fdtd-offline / numpy-overlap-offline / design-anchor）。

## 用法
```bash
cd D:\agent_LDA\lda
python run_harness.py                                    # 内置 B1–B4,B8 + 参考求解器（演示 pass 闭环）
python run_ir_smoke.py                                   # L0 IR 草案：目标谱形+多晶圆厂真跑逆设计
python run_harness.py --perturb 0.10                      # 注入 10% 扰动，演示 fail 检测
python run_harness.py --out reports                       # 报告输出目录
```
报告写入 `reports/verification_report.md` 与 `.json`。

## L0 统一 IR / DSL（`lda_ir`，已落地草案）

L0 是架构最底层、最该"自己做好、不取巧"的真地基（主权策略 C 级：第一天自主）。
它表达**设计意图的统一机器语言**——可序列化为纯 dict（JSON 友好，经 L1 MCP
传输、落库 diff）、可校验、可桥接到真实 agent 设计闭环，且携带：
- `SpectrumSpec`：目标谱形（驱动 B11 谱形逆设计）；
- `FoundryPlan`：多晶圆厂落点意图（驱动 L2 多晶圆厂共建闭环）。

**统一光子 + 量子**：光子与量子共用同一套 `core` / 校验器 / 桥接层，仅 Kinds
与 `domain` 不同——`photon.py`（RingResonator 等）与 `quantum.py`（Transmon /
Resonator / Coupler）都产 `Component`，IR 经同一桥接层驱动 agent 闭环、过同一
验证裁判。这正是"统一光子+量子"差异化定位的底座：不是两套系统，是一套 IR
机器语言描述两类器件。

模块结构（`lda/lda_ir/`）：
- `core.py`：IRModel / Component / Port / Net / ObjectiveSpec / SpectrumSpec / FoundryPlan；
- `photon.py`：光子 Kinds 工厂（RingResonator / Waveguide / GratingCoupler / Splitter）；
- `quantum.py`：量子 Kinds 工厂（Transmon / Resonator / Coupler）；
- `dsl.py`：`to_dict`/`from_dict`（机器优先 round-trip）+ `to_dsl`（人类可读渲染）；
- `validate.py`：IR 静态校验（端口闭合 / 参数落窗口 / 谱形规格合法 / 至少含一个设计意图）；
- `bridge.py`：`ir_to_design_problem` / `ir_to_multifoundry`（IR → DesignProblem 真驱动 agent 闭环）+ `ir_eval`（L3 真值内核直接读 IR 算真值 + 判定，不经 DesignProblem）。

**工艺窗口语义（多晶圆厂共建的关键）**：折射率 n_si（光子）/ 充电能 E_C（量子）
都是**工艺参数**，由 foundry 决定，设计者只调几何 R / 约瑟夫森能 E_J。bridge 层
对光子强制注入 `foundry.n_si`、对量子强制注入 `foundry.quantum_window.ec_default`
并固定 E_C，使"同一设计意图（如 f01=5GHz）在不同 foundry 收敛到不同几何/参数落点"
——差异完全由工艺窗口驱动，因果链干净。

**L3 直接消费 IR（`ir_eval`）**：验证裁判不必经由手写 DesignProblem，直接读 IR 的
`spectrum` / `objectives` 调用黄金参考算物理真值并 pass/fail 判定——IR 即事实源，
逆设计与验证共用同一份 IR 意图（技术复利：上层每次计算都从 IR 派生）。

快速验证：
```bash
python run_ir_smoke.py            # 光子：构造"环形谱形+B11+多晶圆厂" IR → 校验 → 跨 foundry 真跑逆设计
python run_ir_quantum_smoke.py    # 量子：构造"transmon 频率 B9" IR → 校验 → 跨≥2 量子 foundry 落点差异
python run_ir_solve_smoke.py      # L3 直接消费 IR：给定 IR+候选参数 → 直接算真值+判定（不经 DesignProblem）
```

`run_harness.py --l0 <file>` 仍可直接消费 L0 IR 的 `verification.benchmarks`
（`id`/`metric`/`target`/`tol`/`oracle`）——这正是白皮书 §12 所述"验证 harness 读
verification.benchmarks → 跑 ORACLE → 算误差 → 判 pass/fail → 人验收"闭环的最小实现。

## 候选求解器（关键占位）
- `ReferenceCandidate`：返回黄金参考值本身，代表"一个正确的求解器" → 全 PASS（演示闭环）。
- `PerturbedCandidate(rel)`：golden·(1+rel)，用于证明 harness 能检测出偏差 → FAIL。
- `L3AISolverCandidate`（**已接入，见下**）：L3 AI 写内核的最小接入实现。

### L3 AI 写内核候选（`--ai`）
`lda_harness/l3_ai_solver.py` 实现与 harness 对齐的 `__call__(spec, golden, params) -> float`：
- **优先 LLM 端点**（OpenAI 兼容）：读取 env `LDA_LLM_BASE` / `LDA_LLM_KEY` /
  `LDA_LLM_MODEL`，让模型"现场求解"基准并解析其返回的标量 metric —— 即
  《白皮书》"AI 写内核"的端到端闭环演示。
- **离线回退** `_local_approx`：无密钥/调用失败时，用一个**有物理动机但带
  真实缺陷**的近似求解器，制造真实的"部分 PASS / 部分 FAIL"（L3 内核迭代
  早期的真实形态）。

```bash
python run_harness.py --ai --out reports_ai
# 当前未配置 LLM 端点 → 走离线近似 → 实测 3/5 PASS（B2、B8 FAIL），
# 精准复现"多数基础题写对、个别缺步骤/未达物理极限"的早期内核画像。
```

接入真实 LLM 后，harness 即可对 AI 写内核的**实际数值输出**逐题验收——
这正是验证锚"候选 vs 黄金(物理定律) + 容差判定"质量门的完整形态。

真实接入路径：把 `candidate` 换成 L3 的 AI 写内核（FDTD/FEM/逆设计输出）。
harness 不关心求解器如何工作，只比对它的标量 metric 与黄金参考。

## L1 agent 协议层（咽喉 · 已落地草案）

L1 = **人操作壳 → agent 操作接口** 的翻译/适配层（见《白皮书》§12、草案
`D:\agent_LDA\LDA_L1_agent协议层草案.md`、契约 `D:\agent_LDA\LDA_L1_agent协议层_schema.json`）。
它是连接 L0（机器优先 IR）与 L3（求解内核）的咽喉：没有它，agent 无法确定性地
驱动内核与验证裁判。

- `lda/lda_l1/protocol.py` → `KernelGateway`：唯一入口 `handle(req)`，把
  `AgentRequest` 路由为「L0 IR → L3 candidate → harness → AgentResponse」的
  确定性调用链（无交互、可复现）。
- `tool_schemas()`：返回 MCP 风格工具声明（`lda.verify_design` /
  `lda.list_benchmarks`），供任意外部 agent/LLM 直接调用 LDA 内核。
- `lda/run_agent.py`：演示一个 agent 通过 L1 协议驱动内核+harness 端到端。

```bash
cd D:\agent_LDA\lda
python run_agent.py --candidate reference     # → 8/8 PASS（status: ok）
python run_agent.py --candidate l3_ai         # → 6/8（B2/B8 FAIL，被物理定律锚抓出）
python run_agent.py --action list_benchmarks  # → 列出 B1–B11 定义
python run_agent.py --l0 examples/l0_demo_ring.json --candidate reference
```
报告写入 `reports_l1/verification_report.md` 与 `.json`（结构同 harness 报告）。

## agent 自迭代设计闭环（AI for AI 最小实证 · 已落地）

`lda/lda_agent/design_loop.py` + `run_agent_loop.py` 是 agent-native EDA 的
心脏，也是"AI for AI"（用 agent 造出的工具去造芯片设计）可运行的最小证据：
**agent 提案 → 经 L1 驱动内核求解 → 物理定律法官验证 → 读判据 → 诊断改写提案**，
闭环迭代直到设计目标收敛。

- `DesignAgent`：`run(problem)` 驱动二分/坐标下降收敛；每轮都经 `KernelGateway`
  路由（L0 IR 携设计几何参数 → L3 candidate → harness → AgentResponse），保证
  链路确定性、无交互、可复现。
- **双判据分离**（求解器正确性 + 设计达标）：设计可收敛，但内核有残差时法官
  仍独立判 FAIL —— 验证裁判是真正的质量门，不为 agent 主观收敛放水。
- `solver="truth"`：用解析物理定律作理想内核；`solver="l3_ai"`：用 AI 写内核
  离线近似，演示"法官独立抓出 B2 残差"。

```bash
cd D:\agent_LDA\lda
python run_agent_loop.py                       # 真内核闭环：10 轮收敛，FSR≈9.14nm，双判据全绿
python run_agent_loop.py --dual --solver l3_ai # 双规格：设计收敛但 B2 内核残差被法官抓 FAIL
python run_agent_loop.py --out reports_agent   # 报告：reports_agent/agent_loop_report.md
```

> 闭环已升级为 **N 维逆设计**：`DesignAgent` 对单参数走单调二分、对多参数走
> Nelder-Mead 单纯形（零依赖），同时优化多个几何量命中目标，且 `constraint_bids`
> 硬约束题须过物理定律验证——l3_ai 内核缺陷会被硬约束挡住、无法虚假收敛。
> 进一步支持 **加权多目标**（`objective` = [{bid, weight, target, tol}] 列表）：
> agent 最小化加权误差联合反推多个几何量，使**多个 benchmark 同时达标**（如 FSR
> 与 n_eff 双目标）。`converged`（设计目标达成）与 `final_passed_all`（含约束的
> 全验证）刻意分离——这正是双判据分离：设计可收敛而内核有残差时法官仍判 FAIL。
> 进一步支持 **目标谱形逆设计**（B11）：误差 = 环形透射谱共振周期（FSR）与目标谱形
> 的归一化失配——均匀洛伦兹梳谱形完全由 FSR 决定，匹配 FSR 即匹配谱形；该误差在 R
> 上单谷、单调（FSR∝1/R），对任意优化器稳健收敛（避免了"逐波长 L2 谱形误差"在梳状
> 混频处的伪局部极小）。优化器新增 **有限差分梯度下降**（数值伴随法，零依赖，
> `use_gradient=True`）：对单/多参数通用、不要求目标单调，是"伴随法内核"的能力占位；
> 真伴随（ceviche/angler）可作未来 L3 外部 ORACLE 接入同一接口，核心主权可控。

## 真·MCP server（L1 协议层对外开放 · 已落地）

把 L1 从「内部 KernelGateway 参考实现」升级为**对外可集成的 MCP 协议服务器**（零依赖
stdio JSON-RPC 2.0，协议版本 2024-11-05）。任意兼容 MCP 的客户端（Claude Desktop /
Cursor / Cline / 自写 agent）都能真正 `call lda.verify_design` 与
`lda.list_benchmarks` —— 这是《白皮书》L1「agent 操作接口」主张的**完成态**，也是
生态咽喉（让外部 agent 把 LDA 内核当工具调用 = 标准+生态护城河的可运行样板）。

- `lda/lda_l1/mcp_server.py` → `LdaMcpServer`：手写最小 JSON-RPC 2.0 over stdio，
  **零外部依赖**（不装 mcp/fastmcp 包），完全复用 `KernelGateway`；物理定律锚 +
  双判据全部继承。
- `lda/run_mcp_server.py`：启动入口；由 MCP 客户端以 stdio 拉起（见下方配置）。
- `lda/run_mcp_smoke.py`：模拟 MCP 客户端的冒烟测试（initialize / tools/list /
  tools/call 全链路断言）。

```bash
cd D:\agent_LDA\lda
python run_mcp_smoke.py
# ✅ initialize · ✅ tools/list · ✅ list_benchmarks(11题)
# ✅ verify_design(8/8 PASS) · ✅ verify_design(l3_ai, 法官抓 FAIL)
```

接入 Claude Desktop / Cursor 的 `mcpServers` 配置示例：
```json
{
  "mcpServers": {
    "lda-kernel": {
      "command": "python",
      "args": ["D:/agent_LDA/lda/run_mcp_server.py"]
    }
  }
}
```
> 注：server 通过 stdin/stdout 的 newline-delimited JSON 通信，**无需网络端口、无需
> 第三方包**；这契合 LDA「离线可跑、主权可控」原则。`tools/call` 返回 MCP 标准
> `content[text]`（内含完整 AgentResponse 结构化 JSON），`isError` 仅在流程异常时为
> true——内核有 FAIL 是"流程成功、被试出"，仍为 `false`。

## 真·Web 预览界面（L4 应用层 · 已落地）

把已落地的内核（验证裁判 / L1 KernelGateway / agent 设计闭环）通过 HTTP 暴露给
一个**真正可交互**的产品级前端，使"现场跑 LDA 内核"可被浏览器实时预览——这是
既定路线 L4 应用层的完成态，也是 AI for AI 成果对外可展示的门面。

启动：
```bash
cd D:\agent_LDA\lda
python lda_webui/app.py          # 默认 http://0.0.0.0:8787（端口 env LDA_WEBUI_PORT 可改）
```
浏览器打开 http://localhost:8787 ：
- 架构落地状态实时展示（哪些层 built / planned）；
- 验证裁判控制台：选候选求解器（参考 / L3 AI / 扰动）→ 真跑 harness → 逐题 PASS/FAIL 实时渲染；
- agent 自迭代设计闭环：选内核（真 / l3_ai）+ 双规格 → 真跑闭环 → 迭代轨迹与结论实时渲染；
- **PDK 工艺逆设计（④）**：选 foundry + 器件模板 → agent 在工艺窗口内逆设计 → 物理定律法官验收；
  环形器件额外渲染**目标谱形可视化**（洛伦兹梳实线=实际 / 虚线=目标，FSR 一目了然）；
- **多晶圆厂对比（⑤）**：选器件类型 → 跨所有已登记 foundry 跑同一设计意图 → 表格 + 谱形叠加图，
  直观展示工艺窗口（n_g/折射率/尺寸边界）差异如何驱动设计落点不同；量子 foundry 无该器件类型自动跳过。

后端零依赖（Python 标准库 http.server），完全复用 `lda_harness` / `lda_l1` /
`lda_agent` / `lda_l2`，不重写验证逻辑。API：`GET /api/status`、`GET /api/benchmarks`、
`GET /api/pdks`、`POST /api/verify`、`POST /api/agent_loop`、`POST /api/pdk_design`、
`POST /api/pdk_compare`（跨多晶圆厂对比，返回各 foundry 收敛落点 + 谱形数组）。

## L2 开放 PDK Registry（社区共建 · 已落地）

L2 是架构分层里"社区共建"的一层：晶圆厂 / 代工厂把工艺节点（process node）与
器件模板（device template）登记到 Registry，agent 设计闭环从中取"真实工艺窗口"
（可调参数 bounds、固定工艺参数、目标规格），使逆设计落在可制造边界内——而不是
在真空里优化几何。这是 L0(IR)→L2(工艺)→L1(协议)→L3(内核)→harness(裁判) 全链路的
"工艺参数注入"缺口闭合点。

- `lda/lda_l2/pdk.py` → `PDKRegistry`：登记 / 查询 / `derive_problem()`（由模板派生
  agent 设计问题）；`get_default_registry()` 惰性加载示例 PDK。
- `lda/lda_l2/pdk_examples.py`：示例 PDK 已登记 **4 个 foundry（演示近似）**，演示
  L2「开放 PDK / 社区共建 / 多晶圆厂」架构——不同 foundry 的波导宽度窗口、弯曲
  半径、折射率各不相同，agent 逆设计天然落在对应 foundry 的可制造边界内：
  - **NOEIC SOI 180nm**（光子）：6 个器件模板——① 环形谐振器 FSR（B4）；
    ② 环形 FSR+波导 n_eff 双规格（B4+B2）；③ 波导宽度→n_eff（B2）；
    ④ **环形双参数逆设计**（B4+B2，N 维）；⑤ **环形双目标加权**（B4+B2，加权
    多目标：FSR 与 n_eff 同时达标）；⑥ **环形谱形匹配（B11，目标谱形逆设计）**。
  - **CUMEC SOI 180nm** / **SITRI SOI 180nm**（光子，不同工艺窗口）：各 2 个模板
    （环形 FSR / 波导 n_eff），证明多晶圆厂 PDK 共建即插即用。
  - **超导量子 transmon**（量子子集）：2 个模板——⑦ transmon 频率逆设计（B9，调
    E_J 命中 f01）；⑧ 量子门保真度逆设计（B10 目标）+ transmon 约束（B9）。二者
    黄金参考均为 ①类确定性物理锚（解析），EPR 哈密顿量对角化(pyEPR/Ansys)按
    主权策略**仅作外部 ORACLE**（已接 `oracle_pyepr.py`，缺失回退解析解，核心永不 import）。
- `lda/run_pdk_smoke.py`：PDK 驱动逆设计冒烟测试（真跑，全 12 模板收敛 + 双判据分离）。

```bash
cd D:\agent_LDA\lda
python run_pdk_smoke.py          # 真跑 PDK 驱动逆设计：12 模板收敛(单参/N维/加权/谱形/量子/多foundry)、l3_ai 被法官抓 FAIL
```

主权纪律：示例 PDK 用公开近似参数（非真实 NDA-PDK）；真实商业 PDK 属 A 级永不借，
Registry 本体自主——它是"工艺对接点"，让 agent 逆设计天然落在可制造窗口内。

## 扩展路线（后续）
1. **B5–B7 场级 ORACLE 收尾**：B5/B7 已落地（numpy 离线 + Meep 子进程就绪）；
   B6 已接入 Tidy3D 外部 ORACLE（`oracle_tidy3d.py`，key 门控 + 设计守则锚兜底），
   配置 `TIDY3D_API_KEY` 即可真跑 3D 真值。
2. 升级黄金参考精度：B2 升级 MPB/FEM；B1 启用 miepython；B4 启用 SAX 电路；
   B9/B10 可接 pyEPR/Qiskit RB-XEB 作外部 ORACLE 交叉验证。
3. ~~量子子集 B9/B10~~ → **已落地**：解析物理锚（Koch2007 / 退相干极限）+ 超导
   量子示例 PDK 逆设计；EPR 哈密顿量对角化按主权策略只作外部 ORACLE。
4. ~~引入"设计验收"双判据~~ → **已落地**：见「agent 自迭代设计闭环」章节。
5. ~~L4 产品级 UI~~ → **已落地**：见「真·Web 预览界面」章节。
6. ~~逆设计深化：目标谱形~~ → **已落地**：B11 谱形逆设计（FSR 周期失配）+ 有限差分梯度下降（数值伴随，零依赖）；真伴随内核 ceviche/angler 可作未来 L3 外部 ORACLE。
7. ~~L2-A 自研 1D/2D FDTD 求解核（踢掉 B 级 Meep）~~ → **已落地**：`lda/lda_solver/fdtd1d.py`（1D，C 级自主、零依赖 numpy、梯度海绵 + 参考跑归一化，经 `run_fdtd_selfcheck.py` ORACLE=tmm.py **4/4 PASS**）+ `lda/lda_solver/fdtd2d.py`（2D TEz，Yee 网格 + 2D 海绵 + 参考跑归一化，经 `run_fdtd2d_selfcheck.py` 双 ORACLE=tmm.py 一维退化+点源柱面波 **5/5 PASS**）→ 1D/2D/3D 透射谱均已无需借 Meep 即得（主权 B 级"踢掉求解器"三维实证）；3D 亦随 L2-A 自研通过物理定律锚校验（`lda/lda_solver/fdtd3d.py` 全 Yee 六分量，selfcheck 5/5 PASS）；**L2-B 两步已推进**：第一步 Numba-CPU JIT 加速已交付（`fdtd3d_numba.py`+`run_fdtd3d_numba_selfcheck.py`，逐字节等价于 numpy 版、同精度 5/5、约 20× 加速 16m19s→0.8m）；第二步 PyTorch 可切换 GPU/CPU 张量化后端已交付（`fdtd3d_torch.py`+`run_fdtd3d_torch_selfcheck.py`+`benchmark_fdtd3d_torch.py`，复用 numpy 几何构造、与 numpy/Numba 版逐位等价、CPU 实测 selfcheck 5/5、`device='cuda'` 一行激活 GPU；本沙箱 CDN 限速致 CUDA 轮子未装、GPU 实测待部署机）；生产级 3D 超大网格(L2-B GPU/CUDA 升维)仍由 AI 团队自举开发（装 CUDA 轮子后激活，标记不阻塞，仅验证层外协）。
