# LDA 验证锚点 · 报告（Verification Harness Report）

- 生成时间：2026-08-25T07:48:11
- L0_IR：(内置默认 B1–B4,B8)
- candidate：ReferenceCandidate
- oracle：确定性物理定律锚（analytical/EIM/Airy/Rayleigh）

## 汇总：18/21 通过

| 题号 | 指标 | 真值来源 | 黄金值 | 候选值 | 误差 | 容差 | 判定 |
|---|---|---|---|---|---|---|---|
| B1 | Q_scat | physical-law | 0.00284131 | 0.00284131 | 0 | 0.0002 | ✅ PASS |
| B10 | F_gate | physical-law | 0.999583 | 0.999583 | 0 | 0.01 | ✅ PASS |
| B11 | spectrum_match | physical-law | 0.00502277 | 0.00502277 | 0 | 0.03 | ✅ PASS |
| B12 | f0_GHz | physical-law | 10.7583 | 10.7583 | 0 | 0.02 | ✅ PASS |
| B13 | J_GHz | physical-law | 0.0316228 | 0.0316228 | 0 | 0.1 | ✅ PASS |
| B14 | L_3dB_um | physical-law | 15.5 | 15.5 | 0 | 0.5 | ✅ PASS |
| B15 | lambda_B_um | physical-law | 1.5504 | 1.5504 | 0 | 0.01 | ✅ PASS |
| B16 | L_mmi_um | physical-law | 18.5806 | 18.5806 | 0 | 3 | ✅ PASS |
| B17 | I_c_A | physical-law | 4.02671e-08 | 4.02671e-08 | 0 | 1e-09 | ✅ PASS |
| B18 | F_purcell | physical-law | 8000 | 8000 | 0 | 1 | ✅ PASS |
| B2 | n_eff | physical-law | 2.65095 | 2.65095 | 0 | 0.05 | ✅ PASS |
| B3 | FSR_nm | physical-law | 120.125 | 120.125 | 0 | 1 | ✅ PASS |
| B4 | FSR_nm | physical-law | 9.1476 | 9.1476 | 0 | 0.3 | ✅ PASS |
| B5 | split_loss_dB | numpy-overlap-offline | 3.4 | 3.4 | 0 | 1 | ✅ PASS |
| B6 | coupling_eff | design-anchor | 0.5 | 0.5 | 0 | 0.15 | ✅ PASS |
| B7 | crosstalk_dB | numpy-fdtd-offline | -19.7328 | -19.7328 | 0 | 5 | ✅ PASS |
| B8 | T_taper | physical-law | 1 | 1 | 0 | 0.01 | ✅ PASS |
| B9 | f01_GHz | physical-law | 6.6282 | 6.6282 | 0 | 0.05 | ✅ PASS |
| E1 | n_eff | empirical-missing | — | — | — | 0.02 | ❌ FAIL |
| E2 | n_eff | empirical-missing | — | — | — | 0.02 | ❌ FAIL |
| E3 | FSR_nm | empirical-missing | — | — | — | 0.1 | ❌ FAIL |

## 未通过项
- **E1**（n_eff）：实证锚未注入（语料库未加载）——诚实降级不判 PASS
- **E2**（n_eff）：实证锚未注入（语料库未加载）——诚实降级不判 PASS
- **E3**（FSR_nm）：实证锚未注入（语料库未加载）——诚实降级不判 PASS

---
*本报告由 LDA 验证 harness 生成；黄金参考为确定性物理定律锚（非 AI）。*