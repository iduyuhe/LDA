"""LDA · QEDA 量子设计能力包（D-74 起 · Track D 系统级）。

量子域从「读出」（D-41/D-46/D-51/D-52）走向「计算」：
- gates：量子门解析矩阵库 + 幺正性 + 通用性（死标量物理定律锚）
- surface_code：rotated surface code 拓扑生成（全对易 + GF(2) 秩验证 k=1）
- cross_resonance：cross-resonance 门参数化（有效模型 + 阈值/资源验收）

全部零外部依赖（仅 numpy），LLM 不进判决路径：是否 PASS 由死标量比对决定。
"""
