# LDA 验证锚点 · 报告（Verification Harness Report）

- 生成时间：2026-08-14T18:37:30
- L0_IR：(内置默认)
- candidate：ReferenceCandidate
- oracle：确定性物理定律锚（analytical/EIM/Airy/Rayleigh）
- via：L1 KernelGateway

## 汇总：2/2 通过

| 题号 | 指标 | 真值来源 | 黄金值 | 候选值 | 误差 | 容差 | 判定 |
|---|---|---|---|---|---|---|---|
| B11 | spectrum_match | physical-law | 0.00123435 | 0.00123435 | 0 | 0.03 | ✅ PASS |
| B4 | FSR_nm | physical-law | 9.13871 | 9.13871 | 0 | 0.3 | ✅ PASS |

---
*本报告由 LDA 验证 harness 生成；黄金参考为确定性物理定律锚（非 AI）。*