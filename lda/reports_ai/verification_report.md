# LDA 验证锚点 · 报告（Verification Harness Report）

- 生成时间：2026-08-14T14:53:07
- L0_IR：(内置默认 B1–B4,B8)
- candidate：L3AISolverCandidate(llm=False)
- oracle：确定性物理定律锚（analytical/EIM/Airy/Rayleigh）

## 汇总：6/8 通过

| 题号 | 指标 | 真值来源 | 黄金值 | 候选值 | 误差 | 容差 | 判定 |
|---|---|---|---|---|---|---|---|
| B1 | Q_scat | physical-law | 0.00284131 | 0.00284131 | 0 | 0.0002 | ✅ PASS |
| B2 | n_eff | physical-law | 2.65095 | 3.27562 | 0.6247 | 0.05 | ❌ FAIL |
| B3 | FSR_nm | physical-law | 120.125 | 120.125 | 0 | 1 | ✅ PASS |
| B4 | FSR_nm | physical-law | 9.1476 | 9.1476 | 0 | 0.3 | ✅ PASS |
| B5 | split_loss_dB | numpy-overlap-offline | 3.4 | 3.4 | 0 | 1 | ✅ PASS |
| B6 | coupling_eff | design-anchor | 0.5 | 0.5 | 0 | 0.15 | ✅ PASS |
| B7 | crosstalk_dB | numpy-fdtd-offline | -19.7328 | -19.7328 | 0 | 5 | ✅ PASS |
| B8 | T_taper | physical-law | 1 | 0.985 | 0.015 | 0.01 | ❌ FAIL |

## 未通过项
- **B2**（n_eff）：确定性物理定律/解析解
- **B8**（T_taper）：确定性物理定律/解析解

---
*本报告由 LDA 验证 harness 生成；黄金参考为确定性物理定律锚（非 AI）。*