# LDA 验证锚点 · 报告（Verification Harness Report）

- 生成时间：2026-09-02T21:41:10
- L0_IR：(内置默认)
- candidate：L3AISolverCandidate
- oracle：确定性物理定律锚（analytical/EIM/Airy/Rayleigh）
- via：L1 KernelGateway

> ⚠️ **本报告不构成验证结论**：本次运行中 **5 项**由**独立候选求解器**判出（计入 `summary.verified`）；其余 **43 项**仍走 ReferenceCandidate 占位自证——候选值即黄金值、「误差」列恒为 0、恒 PASS，**零验证价值**。把「N/N 通过」整体读作「N 项已验证」是误读：真正被验证的只有那 5 项。

## 汇总：45/48 通过（独立候选 5 项中 **2 项通过=已验证** · 43 项自证闭环，**非验证结论**）

| 题号 | 指标 | 真值来源 | 黄金值 | 候选值 | 误差 | 容差 | 判定 |
|---|---|---|---|---|---|---|---|
| B1 | Q_scat | physical-law | 0.00284131 | 0.00284131 | 0 | 0.0002 | ✅ PASS |
| B10 | F_gate | physical-law | 0.999583 | 0.999583 | 0 | 0.01 | ✅ PASS |
| B11 | spectrum_match | physical-law | 0.00502277 | 0.00502277 | 0 | 0.03 | ✅ PASS |
| B12 | f0_GHz | physical-law | 10.7583 | 10.7583 | 0 | 0.02 | ✅ PASS |
| B13 | J_GHz | physical-law | 0.0316228 | 0.0316228 | 0 | 0.002 | ✅ PASS |
| B14 | L_3dB_um | physical-law | 7.75 | 7.75 | 0 | 0.25 | ✅ PASS |
| B15 | lambda_B_um | physical-law | 1.5504 | 1.5504 | 0 | 0.01 | ✅ PASS |
| B16 | L_mmi_um | physical-law | 18.5806 | 18.5806 | 0 | 3 | ✅ PASS |
| B17 | I_c_A | physical-law | 4.02671e-08 | 4.02671e-08 | 0 | 1e-09 | ✅ PASS |
| B18 | F_purcell | physical-law | 8000 | 8000 | 0 | 1 | ✅ PASS |
| B19 | max|T(λ)| over all transfer paths | physical-law | 1 | 1 | 0 | 1e-09 | ✅ PASS |
| B2 | n_eff | physical-law | 2.65095 | 3.27562 | 0.6247 | 0.05 | ❌ FAIL |
| B20 | FSR_nm | physical-law | 20.0108 | 20.0108 | 0 | 1e-06 | ✅ PASS |
| B21 | cavity_wl_nm | physical-law | 2214 | 2214 | 0 | 1e-06 | ✅ PASS |
| B22 | qres_f_ghz | physical-law | 7.49481 | 7.49481 | 0 | 1e-06 | ✅ PASS |
| B23 | fluxonium_f01_ghz | physical-law | 2.82843 | 2.82843 | 0 | 1e-06 | ✅ PASS |
| B24 | tcoup_geff_ghz | physical-law | -0.004 | -0.004 | 0 | 3e-05 | ✅ PASS |
| B25 | tunable_f01_ghz | physical-law | 6.6282 | 6.6282 | 0 | 0.05 | ✅ PASS |
| B26 | dispersive_chi_ghz | physical-law | -0.00230769 | -0.00230769 | 0 | 0.0001 | ✅ PASS |
| B27 | cz_gate_time_ns | physical-law | 680.678 | 680.678 | 0 | 30 | ✅ PASS |
| B28 | Vpi_volts | physical-law | 3.78097 | 3.78097 | 0 | 0.001 | ✅ PASS |
| B3 | FSR_nm | physical-law | 120.125 | 120.125 | 0 | 1 | ✅ PASS |
| B4 | FSR_nm | physical-law | 9.1476 | 9.1476 | 0 | 0.3 | ✅ PASS |
| B5 | split_loss_dB | numpy-overlap-offline | 3.4 | 3.4 | 0 | 1 | ✅ PASS |
| B6 | coupling_eff | design-anchor | 0.5 | 0.5 | 0 | 0.15 | ✅ PASS |
| B7 | crosstalk_dB | numpy-fdtd-offline | -19.7328 | -19.7328 | 0 | 5 | ✅ PASS |
| B8 | T_taper | physical-law | 1 | 0.985 | 0.015 | 0.01 | ❌ FAIL |
| B9 | f01_GHz | physical-law | 6.6282 | 48 | 41.37 | 0.05 | ❌ FAIL |
| E1 | n_g | empirical-measurement | 4.18 | 4.18 | 0 | 0.1 | ✅ PASS |
| E2 | n_g | empirical-measurement | 1.892 | 1.892 | 0 | 0.1 | ✅ PASS |
| E3 | FSR_nm | empirical-measurement | 10.44 | 10.44 | 0 | 0.1 | ✅ PASS |
| E4 | insertion_loss_dB | empirical-measurement | 0.18 | 0.18 | 0 | 0.1 | ✅ PASS |
| E5 | excess_loss_dB | empirical-measurement | 0.05 | 0.05 | 0 | 0.1 | ✅ PASS |
| E6 | propagation_loss_dBcm | empirical-measurement | 0.087 | 0.087 | 0 | 0.05 | ✅ PASS |
| E7 | crosstalk_dB | empirical-measurement | -41 | -41 | 0 | 5 | ✅ PASS |
| S1 | margin_dB | physical-law | 10.5 | 10.5 | 0 | 0.01 | ✅ PASS |
| S10 | verdict(ACCEPT=1, REJECT=0) | physical-law | 1 | 1 | 0 | 1e-09 | ✅ PASS |
| S11 | verdict(ACCEPT=1, REJECT=0) | physical-law | 1 | 1 | 0 | 1e-09 | ✅ PASS |
| S12 | verdict(ACCEPT=1, REJECT=0) | physical-law | 1 | 1 | 0 | 1e-09 | ✅ PASS |
| S13 | yield(0~1) | physical-law | 0.95475 | 0.95475 | 0 | 0.01 | ✅ PASS |
| S2 | margin_GHz | physical-law | 50 | 50 | 0 | 1e-06 | ✅ PASS |
| S3 | OSNR_dB | physical-law | 46.9299 | 46.9299 | 0 | 0.01 | ✅ PASS |
| S4 | margin | physical-law | -0.00098602 | -0.00098602 | 0 | 1e-06 | ✅ PASS |
| S5 | margin_dB | physical-law | 10 | 10 | 0 | 1e-06 | ✅ PASS |
| S6 | margin_dB | physical-law | 11.5 | 11.5 | 0 | 1e-06 | ✅ PASS |
| S7 | margin_mean_dB | physical-law | 10.4969 | 10.4969 | 0 | 0.15 | ✅ PASS |
| S8 | OSNR_mean_dB | physical-law | 46.9298 | 46.9298 | 0 | 0.2 | ✅ PASS |
| S9 | verdict(ACCEPT=1, REJECT=0) | physical-law | 1 | 1 | 0 | 1e-09 | ✅ PASS |

## 未通过项
- **B2**（n_eff）：确定性物理定律/解析解
- **B8**（T_taper）：确定性物理定律/解析解
- **B9**（f01_GHz）：确定性物理定律/解析解

---
*本报告由 LDA 验证 harness 生成；黄金参考为确定性物理定律锚（非 AI）。*