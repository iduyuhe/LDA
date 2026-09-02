# LDA 验证锚点 · 报告（Verification Harness Report）

- 生成时间：2026-09-02T08:17:44
- L0_IR：0.1.0-draft
- candidate：ReferenceCandidate
- oracle：确定性物理定律锚（analytical/EIM/Airy/Rayleigh）
- via：L1 KernelGateway

> ⚠️ **本报告不构成验证结论**：candidate=ReferenceCandidate 直接把黄金参考值当作候选值，故「误差」列恒为 0、全部 PASS。它只验证**判决回路闭合**（黄金取值→比对→容差判定→报告），**不验证任何求解器**。真实验证必须由**独立候选求解器**产出候选值——见 `run_harness.py --ai`（L3 AI 写内核）与 `verification_adapters.py`（独立频域候选，如 E2 的 FDFD n_g）。把本报告的「N/N 通过」读作「N 项已验证」是误读。

## 汇总：2/2 通过（自证闭环，**非验证结论**）

| 题号 | 指标 | 真值来源 | 黄金值 | 候选值 | 误差 | 容差 | 判定 |
|---|---|---|---|---|---|---|---|
| B2 | n_eff | physical-law | 2.65095 | 2.65095 | 0 | 0.05 | ✅ PASS |
| B4 | FSR_nm | physical-law | 9.1476 | 9.1476 | 0 | 0.3 | ✅ PASS |

---
*本报告由 LDA 验证 harness 生成；黄金参考为确定性物理定律锚（非 AI）。*