# LDA 验证锚点 · 报告（Verification Harness Report）

- 生成时间：2026-08-14T12:27:31
- L0_IR：(内置默认)
- candidate：ReferenceCandidate
- oracle：确定性物理定律锚（analytical/EIM/Airy/Rayleigh）
- via：L1 KernelGateway

## 汇总：8/8 通过

| 题号 | 指标 | ORACLE | 黄金值 | 候选值 | 误差 | 容差 | 判定 |
|---|---|---|---|---|---|---|---|
| B1 | Q_scat | analytical(Mie/Rayleigh) | 0.00284131 | 0.00284131 | 0 | 0.0002 | ✅ PASS |
| B2 | n_eff | analytical(EIM) | 2.65095 | 2.65095 | 0 | 0.05 | ✅ PASS |
| B3 | FSR_nm | analytical(Airy) | 120.125 | 120.125 | 0 | 1 | ✅ PASS |
| B4 | FSR_nm | analytical(ring)/sax | 9.1476 | 9.1476 | 0 | 0.3 | ✅ PASS |
| B5 | split_loss_dB | design-rule(Meep/Tidy3D field 预留) | 3 | 3 | 0 | 1 | ✅ PASS |
| B6 | coupling_eff | design-rule(Tidy3D/Meep field 预留) | 0.5 | 0.5 | 0 | 0.15 | ✅ PASS |
| B7 | crosstalk_dB | design-rule(Meep field 预留) | -40 | -40 | 0 | 5 | ✅ PASS |
| B8 | T_taper | analytical(adiabatic-limit) | 1 | 1 | 0 | 0.01 | ✅ PASS |

---
*本报告由 LDA 验证 harness 生成；黄金参考为确定性物理定律锚（非 AI）。*