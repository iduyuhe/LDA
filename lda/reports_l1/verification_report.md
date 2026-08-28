# LDA 验证锚点 · 报告（Verification Harness Report）

- 生成时间：2026-08-28T10:22:36
- L0_IR：0.1.0-draft
- candidate：ReferenceCandidate
- oracle：确定性物理定律锚（analytical/EIM/Airy/Rayleigh）
- via：L1 KernelGateway

## 汇总：2/2 通过

| 题号 | 指标 | 真值来源 | 黄金值 | 候选值 | 误差 | 容差 | 判定 |
|---|---|---|---|---|---|---|---|
| B2 | n_eff | physical-law | 2.65095 | 2.65095 | 0 | 0.05 | ✅ PASS |
| B4 | FSR_nm | physical-law | 9.1476 | 9.1476 | 0 | 0.3 | ✅ PASS |

---
*本报告由 LDA 验证 harness 生成；黄金参考为确定性物理定律锚（非 AI）。*