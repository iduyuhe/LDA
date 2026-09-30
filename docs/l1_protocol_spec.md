# LDA L1 · Agent 协议层开放标准规范

> 文档编号：**LDA-STD-002**
> 版本：**v0.1（2026-09-30 起草 · 待杜先生裁定后定稿发布）**
> 状态：**开放标准（open spec）草案** —— 社区共建起点，任何 agent / 工具 / MCP 客户端均可按此规范接入 LDA 内核
> 配套：`docs/l1_protocol_schema.json`（JSON Schema draft-07 机器可读契约，与本规范零漂移）
> 唯一真源：`lda/lda_l1/protocol.py::KernelGateway`（所有传输绑定的实现真源）
> 零漂移门禁：`lda/run_l1_spec_smoke.py`（文档-代码一致性机器守护）
> 编制：AI（LDA 工程团队，按杜先生授权代行技术/工程决策）
> 红线：LLM 不进判决路径 —— L1 只翻译"操作意图 → 确定性调用链"，判据由死标量执行，物理判定由物理定律锚（PhysicsAnchor）确定性完成

---

## 0. 与 L0 IR 的分层关系

LDA 架构自底向上分三层，L1 紧接 L0：

| 层 | 是什么 | 机器语言 | 标准文档 |
|---|---|---|---|
| **L0 · IR** | 设计意图的统一表示（"要造什么、约束是什么、目标谱长什么样"） | `IRModel` / JSON（machine-first DSL） | LDA-STD-001 v0.3（`docs/ir_spec.md`） |
| **L1 · Agent 协议**（**本规范**） | agent 与内核之间的"操作协议"（"怎么驱动验证/仿真/布局/导出"） | `AgentRequest` / `AgentResponse`（machine-first 信封） | **LDA-STD-002 v0.1（本文件）** |
| L3 · 求解核 | 实际数值求解器（fdtd3d / fdtd3d_numba / fdtd3d_torch / 真 2D 波导 / 拓扑逆设计） | 内部 Python API | — |

**关键边界**：L0 描述"是什么"，L1 描述"怎么驱动"。L1 消费 L0 结构化字段（`verify_design` 的 `payload.l0_ir` 即一份 L0 IR），但 L1 自身不定义设计语义——设计语义归 L0。两标准独立演进、零漂移各自守护。

---

## 1. 定位与设计原则

LDA L1 是架构分层中"操作协议"层（主权策略 C 级：第一天自主），是 **agent 与内核之间的机器优先操作接口**：

- **机器优先**：一切交互可序列化为 `AgentRequest` / `AgentResponse` 纯 JSON，便于 agent 间传递、经 MCP 暴露、落库 diff。**L1 不依赖任何 GUI、不弹窗、不等人**。
- **确定性**：同请求 → 同结果；无随机、无状态、无交互。判据由死代码（标量比对）执行。
- **可验证**：harness 的黄金参考来自非 AI 的物理定律锚（analytical / EIM / Airy / Rayleigh 等）；`l3_ai` 候选仅为生成器，判决=死标量比对。
- **可编排**：`tool_schemas()` 暴露 MCP 风格工具，供任意外部 agent / LLM / MCP 客户端调用。
- **零外部依赖**：传输绑定 `mcp-stdio-jsonrpc2` 不装 `mcp` / `fastmcp` 包，手写最小 JSON-RPC 2.0 over stdio，契合 LDA「离线可跑、主权可控」原则。
- **双层实现、单一真源**：`KernelGateway` 是协议层唯一真源；`mcp_server.py` 仅是其传输适配器，不重复实现验证逻辑。

---

## 2. 消息信封（Envelope）

所有 L1 交互由两类消息承载。字段定义见 `docs/l1_protocol_schema.json#/definitions`。

### 2.1 AgentRequest（请求）

| 字段 | 类型 | 必填 | 语义 |
|---|---|---|---|
| `request_id` | string | – | 请求标识；缺省由 KernelGateway 生成 `req-<hex12>` |
| `action` | enum | ✅ | 操作原语名（见 §3 表） |
| `payload` | object | ✅ | 操作参数（按 action 不同，结构见各 action） |
| `meta` | object | – | 调用方自由元数据（如 `{"requester": "smoke"}`），不参与判决 |

### 2.2 AgentResponse（响应）

| 字段 | 类型 | 必填 | 语义 |
|---|---|---|---|
| `request_id` | string | ✅ | 回显对应请求 id |
| `status` | enum | ✅ | `ok` / `fail` / `error` / `partial`（语义见 §4） |
| `result` | object | – | 结构化结果（如 `{summary, details}` / `{transfers, missing_models}`） |
| `artifacts` | object | – | 落盘产物路径（如 `report_md` / `report_json` / `gds_bytes`） |
| `error` | string\|null | – | 仅 `status=error` 时含异常 str |

### 2.3 Candidate（验证候选，仅 verify_design / run_candidate）

| 字段 | 类型 | 必填 | 语义 |
|---|---|---|---|
| `type` | enum | ✅ | `reference` / `perturbed` / `l3_ai`（语义见 §3.1） |
| `rel_err` | number | – | 仅 `perturbed` 模式使用（相对扰动幅度） |

---

## 3. 操作原语集（Actions）

`KernelGateway.handle(req)` 按 `action` 路由。`tool_schemas()` 对外部暴露其中 6 个（带 `*` 者）。

| action | 暴露* | payload.required | 说明 |
|---|---|---|---|
| `verify_design` | ✅ | `candidate` | 驱动 L0 IR → L3 candidate → harness 确定性验证；可选 `l0_ir` / `benchmarks` 过滤 |
| `run_candidate` | — | `candidate` | `verify_design` 的别名（同路由），保留以兼容旧调用方 |
| `list_benchmarks` | ✅ | （空） | 列出全题库（B-*/E-*/S-*）定义：metric / oracle / tol |
| `link_simulate` | ✅ | `spec` | 链路级联仿真：spec → `LinkModel` → `lda_chain.simulate` |
| `route` | ✅ | `src`, `dst` | 单 net 自动布线（C 级自写曼哈顿+圆角） |
| `place` | ✅ | `spec` | 器件放置：spec → `LinkModel` → `place_row` |
| `export_chip_gds` | ✅ | `spec` | 整芯片 GDS 导出：放置+布线+真 GDSII（round-trip 可解析） |

> `*` 经 `tool_schemas()` 对外暴露，任何 MCP 客户端可 `tools/list` 发现。`run_candidate` 虽未列于工具集，但 `handle()` 接受其别名，`status=error` 反例门禁同样覆盖。

### 3.1 verify_design 的 Candidate 三态（falsifiability 反例）

| type | 预期 status | 含义 |
|---|---|---|
| `reference` | `ok`（passed==total） | 确定性参考实现，黄金对照 |
| `perturbed` | `fail`（passed<total） | 施 `rel_err` 扰动，被死标量抓出 |
| `l3_ai` | `fail`（passed<total） | L3 AI 候选生成器，被法官（死标量）驳回；**排雷①：LLM 不进判决路径** |

---

## 4. 状态码（Status）

| 码 | 语义 |
|---|---|
| `ok` | 全 PASS：verify 类 `passed==total`；链路/布局/导出类流程成功 |
| `fail` | 流程成功但判决有 FAIL：verify 类 `passed<total`（死标量比对结果，非异常） |
| `partial` | 仅 `export_chip_gds` 使用：存在 `blocked_nets`（部分结构未布线）但流程成功 |
| `error` | 异常（链路未跑完），`error` 字段含 `str(e)`；结构化返回，不抛给人 |

---

## 5. 传输绑定（Transport Bindings）

协议层与传输解耦，当前两种绑定共享同一 `KernelGateway` 真源：

| 绑定 | 协议 | 依赖 | 实现 |
|---|---|---|---|
| `mcp-stdio-jsonrpc2` | JSON-RPC 2.0 over stdio（protocol_version `2024-11-05`，server `lda-kernel` v0.1.0） | 零依赖（手写） | `lda/lda_l1/mcp_server.py::LdaMcpServer` |
| `in-process-library` | 同进程 `KernelGateway.handle(AgentRequest)` | 仅内核依赖 | `lda/lda_l1/protocol.py::KernelGateway` |

**MCP 绑定契约**：
- `tools/list` → 返回 `tool_schemas()` 的 MCP 格式（`inputSchema` 大写 S）；
- `tools/call` → `method=lda.<action>`，`params=payload`，`result.content[0].text = AgentResponse.to_json()`；
- JSON-RPC `id` 与 `request_id` 解耦，不强制相等；
- `AgentResponse.to_dict()` 经 `canon()` 归一（防 numpy 标量泄漏，v0.9.103 修复）。

---

## 6. 不变式（零漂移守护）

1. **LLM 不进判决路径**：verify 判决=死标量比对；`l3_ai` 仅为候选生成器。
2. **确定性**：同请求 → 同结果；无随机、无状态、无交互。
3. **可验证**：golden 来自非 AI 物理定律锚。
4. **落盘责任**：验证结果默认写 `reports_l1/verification_report.{md,json}`，`artifacts` 回指路径。
5. **工具集 ⊆ 本规范**：`tool_schemas()` 暴露的工具集 ⊆ 本契约 `actions`（tool_exposed=true）；**新增 action 必须同步更新 `l1_protocol_schema.json` 与本文件，否则 `run_l1_spec_smoke.py` 红**（自食其规则）。

---

## 7. 校验规则（validate）

| # | 规则 | 语义 |
|---|---|---|
| 1 | action 合法 | `action` ∈ §3 表；未知 action → `status=error`（门禁抓出） |
| 2 | payload.required 满足 | 各 action 的 `payload_required` 字段必须存在（缺 → `error`） |
| 3 | candidate.type 合法 | `verify_design` 的 `candidate.type` ∈ {reference, perturbed, l3_ai}；非法 → `error` |
| 4 | 结果状态机合法 | `status` ∈ {ok, fail, error, partial}；`partial` 仅 `export_chip_gds` 产生 |
| 5 | 确定性可复现 | 同 `AgentRequest`（除 `request_id`）→ 同 `AgentResponse.status` 与 `result` |

校验返回**结构化 `AgentResponse`**（非首个即停），便于 agent 一次性修复。

---

## 8. 扩展指南

### 8.1 新增 action

1. **代码注册**：在 `KernelGateway.handle()` 加 `if req.action == "..."` 分支 + 对应 `_<action>` 方法，返回 `AgentResponse`；如需对外暴露，在 `tool_schemas()` 追加工具声明。
2. **契约同步**：`docs/l1_protocol_schema.json` 的 `contract.actions` 追加该 action（`payload_required` / `payload_optional` / `payload_enum` / `tool_exposed`）；本文件 §3 表补行。
3. **零漂移验证**：跑 `run_l1_spec_smoke.py`（代码 tool_schemas 与契约比对 + 未知 action 反例）。

### 8.2 新增 Candidate 类型

1. `KernelGateway._build_candidate()` 加分支；
2. `schema` 的 `Candidate.type_enum` 与本文 §2.3 同步；
3. 新增 type 必须附 falsifiability 反例（预期 `fail`），写进 `run_l1_agent_smoke.py`。

---

## 9. 向后兼容（受控升级）

- `spec_version` 受控：`0.1` 现行；未知版本明确拒绝（不允许静默演进）。
- `protocol_version`（传输层）`2024-11-05` 由 `mcp_server.PROTOCOL_VERSION` 单一出口声明。
- 新增 action / candidate 为**向后兼容扩展**（旧调用方不受影响）；删除 / 改语义为**破坏性变更**，须 bump `spec_version` 并在 §10 记录。

---

## 10. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| 0.1 | 2026-09-30 | **草案起草**：冻结 L1 协议层（AgentRequest/AgentResponse/Candidate 信封 + 7 action 原语集 + 4 状态码 + 2 传输绑定 + 零漂移契约 LDA-STD-002），对标 L0 LDA-STD-001 v0.3；配套 `l1_protocol_schema.json` + `run_l1_spec_smoke.py` |

---

*本规范与 `docs/l1_protocol_schema.json` 保持机器可校验的零漂移；与 L0《LDA L0 IR 开放标准规范》（LDA-STD-001）、`docs/design_package_spec.md` 设计包规范配套。社区/第三方按本规范接入 = 共建 L1 标准。*
