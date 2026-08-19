"""LDA L1 · agent 协议层（参考实现）。

L1 = 「人操作壳 → agent 操作接口」的翻译/适配层（见《白皮书》§12）。
它把旧式 EDA「给人逐步点、给人看报表、给人调参」的交互，翻译为 agent 可直接
调用的**确定性 / 批处理 / 可验证 / 无交互**原语——这是 LDA 与 Synopsys/Cadence/
gdsfactory 等「为人操作设计」系统的根本分野。

子模块：
  protocol.py  AgentRequest/AgentResponse 信封 + KernelGateway（请求处理器）
                + tool_schemas()（对外 MCP 风格工具声明）
"""
