# LDA L1 · agent 协议层（草案 v0.1.0-draft）

> 文档编号：LDA-L1-001
> 版本：v0.1.0-draft（机器优先）
> 归属层级：L1（L0 IR 与 L3 求解器之间的咽喉）
> 编制依据：《LDA 技术白皮书》§11（验证裁判）/ §12（系统设计哲学）
> 密级：内部 · 暂不对外

---

## 1. 为什么需要 L1（咽喉定位）

LDA 的根本分野不是"用 AI 辅助设计"，而是**agent 直接造出设计结果（design outcome）**，
人只负责定方向、验收结果、担责任（《白皮书》§12）。

现有 EDA/PDA/QEDA 全部**为人操作设计**：GUI、逐步点击、给人看的报表、给人调参的
API 粒度。这些"人操作壳"对 LDA 无用甚至有害——直接当 L3 接口会污染 agent 编排。

**L1 的本质 = 把"人操作壳"翻译为"agent 操作接口"**：确定性 / 批处理 / 可验证 / 无交互。

```
  L0 IR ──┐
          ├─► L1 KernelGateway ──► L3 candidate（求解器/AI内核）
  L1 指令 ┘        │                     │
                   │                     ▼
                   └──────────► harness（物理定律锚·非AI）──► AgentResponse
```

L1 是连接 L0（机器优先 IR）与 L3（求解内核）的**咽喉**：没有它，agent 无法确定性地
驱动内核与验证裁判。本草案把它作为①类真地基打掉（能力圈内、不可替代）。

---

## 2. 设计原则（不可妥协）

| 原则 | 含义 | 违反后果 |
|---|---|---|
| 确定性 | 同请求 → 同结果；无随机、无状态、无交互 | agent 编排不可复现 |
| 可验证 | 黄金参考来自非 AI 物理定律锚 | AI 写手↔AI 裁判互证、错误自我确认 |
| 无交互 | 不弹窗、不等人、不给人看 GUI | 污染 agent 编排、退化成人辅助 |
| 可编排 | 对外暴露 MCP 风格工具声明 | 外部 agent/LLM 无法调用 LDA 内核 |
| 机器优先 | 消息信封为 JSON，非人读文档 | 无法被 agent 程序化消费 |

---

## 3. 消息契约（machine-first）

完整契约见 `LDA_L1_agent协议层_schema.json`（JSON Schema 2020-12）。核心两类：

### 3.1 AgentRequest（agent → L1）
```json
{
  "request_id": "req-abc123",
  "action": "verify_design",
  "payload": {
    "l0_ir": { "…L0 IR…" },            // 可选，缺省用内置默认题库
    "candidate": { "type": "l3_ai" },  // reference | perturbed | l3_ai
    "benchmarks": ["B1","B2","B4"]     // 可选，仅验证指定题
  },
  "meta": { "requester": "agent://demo" }
}
```

### 3.2 AgentResponse（L1 → agent）
```json
{
  "request_id": "req-abc123",
  "status": "fail",                    // ok(全PASS) | fail(有FAIL) | error(异常)
  "result": {
    "summary": { "total": 8, "passed": 6 },
    "details": [ { "id":"B2", "metric":"n_eff", "golden":2.65, "candidate":3.27,
                   "tol":0.05, "passed":false, "oracle":"analytical(EIM)" } ]
  },
  "artifacts": { "report_md": "reports_l1/verification_report.md",
                 "report_json": "reports_l1/verification_report.json" },
  "error": null
}
```

**status 三方语义**：`ok`=全部通过（设计达标）；`fail`=流程成功但有题未过（返回
结构化明细，agent 可据以迭代）；`error`=异常（结构化错误，不抛给人）。

---

## 4. 参考实现（已落地）

路径：`lda/lda_l1/protocol.py` + `lda/run_agent.py`

- `KernelGateway.handle(req)`：唯一入口，把 AgentRequest 路由到
  - `verify_design` / `run_candidate`：解析 L0 IR → 构建 L3 candidate → 跑 harness →
    生成报告 → 回 AgentResponse
  - `list_benchmarks`：列出题库定义
- `KernelGateway.tool_schemas()`：返回 MCP 风格工具声明（`lda.verify_design`、
  `lda.list_benchmarks`），供任意外部 agent/LLM 直接调用 LDA 内核。
- candidate 三型全通：`reference`（正确求解器→演示 pass）、`perturbed`（注入扰动→
  演示 fail 检测）、`l3_ai`（L3 AI 写内核候选）。

### 4.1 真跑实证
```bash
python run_agent.py --candidate reference        # → 8/8 PASS
python run_agent.py --candidate l3_ai            # → 6/8（B2/B8 FAIL，被物理定律锚抓出）
python run_agent.py --action list_benchmarks     # → 列出 B1–B8 定义
```

---

## 5. 与 L0 / L3 / harness 的咬合

- **L0**：`resolve_specs(l0_ir)` 直接消费 L0 IR 的 `verification.benchmarks`（target/tol/oracle
  可被 L0 覆盖）——IR 与验证闭环原生对齐。
- **L3**：candidate 即 L3 求解器接口（`callable(spec, golden, params)->float`）；
  `l3_ai` 型已接 OpenAI 兼容端点（env 配置），离线回退 `_local_approx`。
- **harness**：黄金参考 = 确定性物理定律锚（麦克斯韦方程的必然），非 AI 输出——
  满足《白皮书》§11 不可移除硬约束。

---

## 6. 下一步（属后续真地基，非本草案范围）

1. **L1 协议增强**：增 `submit_design`（agent 提交 L0 IR 草稿）、`diff_report`（两版
   设计对比）、`propose_fix`（据 FAIL 明细建议修正）——走向"agent 自迭代设计"。
2. **真·MCP server**：把 `tool_schemas()` 接入 MCP 传输层，让 Claude/Cursor 等外部
   agent 真能 `call lda.verify_design`。
3. **量子子集扩展**：B9/B10 接入后，L1 自动支持跨光子+量子的统一调用（L0 统一 IR 的
   红利在此兑现）。
4. **主权传输**：L1 仅传 IR 与标量结果，不传受控求解器源码——天然满足主权红线
   （A 级美系工具永不借、B 级只作 ORACLE 外部调用）。

---

*本草案与《LDA_L0_IR草案_光子子集.md》《LDA_技术白皮书.md》配套。L1 属①类真地基，
由 agent 自主起草、杜先生验收。*
