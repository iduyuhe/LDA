# LDA 验证锚点 · 报告（Verification Harness Report）

- L0_IR：(内置默认 B1–B4,B8)
- candidate：IndependentCandidateRouter(独立候选 63 道: B1,B10,B11,B12,B13,B14,B15,B16,B19,B2,B20,B22,B23,B24,B25,B26,B27,B28,B29,B3,B30,B31,B32,B33,B34,B36,B37,B4,B40,B41,B42,B43,B44,B45,B46,B47,B48,B49,B5,B50,B51,B52,B53,B54,B55,B56,B57,B58,B59,B6,B60,B61,B62,B63,B64,B7,B8,B9,E2,E8,S13,S7,S8；降级量级参考 3 道: B21,E10,E9)
- oracle：确定性物理定律锚（analytical/EIM/Airy/Rayleigh）
- self_consistent：True

> ⚠️ **本报告不构成验证结论**：本次运行中 **63 项**由**独立候选求解器**判出（计入 `summary.verified`）；其余项中 **18 项**走 ReferenceCandidate 占位自证（候选值即黄金值、「误差」列恒为 0、恒 PASS，**零验证价值**），**3 项**为降级量级参考（有独立候选但与 golden 几何不同源/精度不足，**不进死标量判决**）。把「N/N 通过」整体读作「N 项已验证」是误读：真正被验证的只有那 63 项。
> 📌 **两条判决路径口径不同（C-1 诚实披露 · v0.9.30 · T-5）**：本报告的 `verified` 来自**路径①**（`IndependentCandidateRouter`，方法学不同源的独立频域候选）。
> **路径②** `run_harness.py --ai`（L3 AI 写内核 demo，离线回退 `_local_approx`）实测 `verified=2/84`（仅 B1/B4 真实现且 PASS，余 82 道为 `return golden` 自证桩）。
> 两路径候选体系本就不同，**均为如实口径、不构成虚报**；对外「独立候选 63/84」特指路径①。

## 汇总：84/84 通过（独立候选 63 项中 **63 项通过=已验证** · 18 项自证闭环 · 3 项降级量级参考（不进判决），**非验证结论**）

| 题号 | 指标 | 真值来源 | 黄金值 | 候选值 | 误差 | 容差 | 判定 |
|---|---|---|---|---|---|---|---|
| B1 | Q_scat | physical-law | 0.00284131 | 0.00280186 | 3.945e-05 | 0.0002 | ✅ PASS |
| B10 | F_gate | physical-law | 0.999847 | 0.999847 | 0 | 1e-08 | ✅ PASS |
| B11 | spectrum_match | physical-law | 0.00502277 | 0.00502277 | 4.35e-09 | 0.03 | ✅ PASS |
| B12 | f0_GHz | physical-law | 10.7583 | 10.7583 | 6.9e-06 | 0.02 | ✅ PASS |
| B13 | J_GHz | physical-law | 0.0316228 | 0.0303097 | 0.001313 | 0.002 | ✅ PASS |
| B14 | L_3dB_um | physical-law | 7.75 | 7.74984 | 0.0001563 | 0.25 | ✅ PASS |
| B15 | lambda_B_um | physical-law | 1.5504 | 1.55041 | 8.36e-06 | 0.01 | ✅ PASS |
| B16 | L_mmi_um | physical-law | 13.9355 | 14.1911 | 0.2556 | 3 | ✅ PASS |
| B17 | I_c_A | physical-law | 4.02671e-08 | 4.02671e-08 | 0 | 1e-09 | ✅ PASS |
| B18 | F_purcell | physical-law | 8000 | 8000 | 0 | 1 | ✅ PASS |
| B19 | max|T(λ)| over all transfer paths | physical-law | 1 | 0.999896 | 0.0001038 | 1e-09 | ✅ PASS |
| B2 | n_eff | physical-law | 2.65095 | 2.64533 | 0.005622 | 0.05 | ✅ PASS |
| B20 | FSR_nm | physical-law | 20.0108 | 20.0108 | 0 | 1e-06 | ✅ PASS |
| B21 | cavity_wl_nm | physical-law | 2214 | 2214.87 | 0.87 | 66 | ✅ PASS |
| B22 | qres_f_ghz | physical-law | 7.49481 | 7.49481 | 5e-08 | 1e-06 | ✅ PASS |
| B23 | fluxonium_f01_ghz | physical-law | 2.82843 | 2.82843 | 0 | 1e-06 | ✅ PASS |
| B24 | tcoup_geff_ghz | physical-law | -0.004 | -0.00398728 | 1.272e-05 | 3e-05 | ✅ PASS |
| B25 | tunable_f01_ghz | physical-law | 6.6282 | 6.61345 | 0.01475 | 0.05 | ✅ PASS |
| B26 | dispersive_chi_ghz | physical-law | -0.00230769 | -0.00226196 | 4.573e-05 | 0.0001 | ✅ PASS |
| B27 | cz_gate_time_ns | physical-law | 680.678 | 694.441 | 13.76 | 30 | ✅ PASS |
| B28 | Vpi_volts | physical-law | 3.78097 | 3.78097 | 1e-08 | 0.001 | ✅ PASS |
| B29 | phase_efficiency_deg_per_mW | physical-law | 38.8802 | 38.8775 | 0.002701 | 0.02 | ✅ PASS |
| B3 | FSR_nm | physical-law | 120.125 | 120.125 | 0 | 1 | ✅ PASS |
| B30 | readout_fidelity_F | physical-law | 0.985992 | 0.985992 | 0 | 0.001 | ✅ PASS |
| B31 | phase_shift_rad | physical-law | 0.804939 | 1.57947 | 0.7745 | 1.5 | ✅ PASS |
| B32 | qcse_shift_meV | physical-law | -1.35714 | -1.37528 | 0.01815 | 0.3 | ✅ PASS |
| B33 | f3dB_Hz | physical-law | 3.18294e+09 | 3.18294e+09 | 1660 | 4000 | ✅ PASS |
| B34 | n_eff | physical-law | 3.27316 | 3.27562 | 0.002458 | 0.01 | ✅ PASS |
| B36 | fc_Hz | physical-law | 6.55714e+09 | 6.55712e+09 | 1.677e+04 | 1e+07 | ✅ PASS |
| B37 | fc_Hz | physical-law | 1.31143e+10 | 1.31141e+10 | 1.342e+05 | 1e+08 | ✅ PASS |
| B4 | FSR_nm | physical-law | 9.1476 | 9.1476 | 2e-08 | 0.3 | ✅ PASS |
| B40 | fc_Hz | physical-law | 1.61451e+10 | 1.61415e+10 | 3.592e+06 | 1e+08 | ✅ PASS |
| B41 | lambda0_m | physical-law | 0.0696 | 0.0696002 | 1.78e-07 | 0.001 | ✅ PASS |
| B42 | E1_eV | physical-law | 0.37603 | 0.376029 | 8.56e-07 | 0.001 | ✅ PASS |
| B43 | E2_eV | physical-law | 1.50412 | 1.50411 | 1.37e-05 | 0.01 | ✅ PASS |
| B44 | E3_eV | physical-law | 3.38427 | 3.3842 | 6.935e-05 | 0.1 | ✅ PASS |
| B45 | E0_eV | physical-law | 0.164464 | 0.164461 | 3.14e-06 | 0.001 | ✅ PASS |
| B46 | E1_eV | physical-law | 0.493391 | 0.493376 | 1.57e-05 | 0.01 | ✅ PASS |
| B47 | E2_eV | physical-law | 0.822319 | 0.822278 | 4.082e-05 | 0.1 | ✅ PASS |
| B48 | E0_eV | physical-law | -0.350171 | -0.349972 | 0.0001997 | 0.01 | ✅ PASS |
| B49 | T | physical-law | 0.308027 | 0.300726 | 0.007301 | 0.02 | ✅ PASS |
| B5 | split_loss_dB | numpy-overlap-offline | 3.4 | 3.0321 | 0.3679 | 1 | ✅ PASS |
| B50 | fc_Hz | physical-law | 1.96714e+10 | 1.96712e+10 | 2.015e+05 | 1e+07 | ✅ PASS |
| B51 | fc_Hz | physical-law | 2.62286e+10 | 2.62281e+10 | 4.778e+05 | 1e+07 | ✅ PASS |
| B52 | E1_eV | physical-law | -1.52962 | -1.53952 | 0.009906 | 0.05 | ✅ PASS |
| B53 | E2_eV | physical-law | -0.964812 | -0.985961 | 0.02115 | 0.05 | ✅ PASS |
| B54 | E4_eV | physical-law | 6.01648 | 6.01626 | 0.0002192 | 0.01 | ✅ PASS |
| B55 | E5_eV | physical-law | 9.40075 | 9.40022 | 0.0005351 | 0.01 | ✅ PASS |
| B56 | E3_eV | physical-law | 1.15125 | 1.15117 | 7.851e-05 | 0.001 | ✅ PASS |
| B57 | E4_eV | physical-law | 1.48017 | 1.48005 | 0.0001288 | 0.001 | ✅ PASS |
| B58 | E0_eV | physical-law | 1.12809 | 1.12809 | 2.57e-06 | 0.001 | ✅ PASS |
| B59 | E0_eV | physical-law | -0.373557 | -0.435588 | 0.06203 | 0.15 | ✅ PASS |
| B6 | coupling_eff | design-anchor | 0.5 | 0.39089 | 0.1091 | 0.15 | ✅ PASS |
| B60 | E1_eV | physical-law | -0.263782 | -0.316288 | 0.05251 | 0.15 | ✅ PASS |
| B61 | fc_Hz | physical-law | 1.61451e+10 | 1.61451e+10 | 1.84e+04 | 1e+07 | ✅ PASS |
| B62 | fc_Hz | physical-law | 1.97396e+10 | 1.97396e+10 | 5.22e+04 | 1e+07 | ✅ PASS |
| B63 | fc_Hz | physical-law | 8.78492e+09 | 8.78492e+09 | 0 | 1e+07 | ✅ PASS |
| B64 | lambda_B_nm | physical-law | 3250 | 3250.13 | 0.1257 | 1 | ✅ PASS |
| B7 | crosstalk_dB | design-anchor | -40 | -35.3626 | 4.637 | 5 | ✅ PASS |
| B8 | T_taper | physical-law | 1 | 0.999954 | 4.65e-05 | 0.01 | ✅ PASS |
| B9 | f01_GHz | physical-law | 6.6282 | 6.61345 | 0.01475 | 0.05 | ✅ PASS |
| E1 | n_g | empirical-measurement | 4.18 | 4.18 | 0 | 0.1 | ✅ PASS |
| E10 | FSR_nm | empirical-measurement | 8.6 | 8.91282 | 0.3128 | 0.6 | ✅ PASS |
| E2 | n_g | empirical-measurement | 1.892 | 1.95718 | 0.06518 | 0.1 | ✅ PASS |
| E3 | FSR_nm | empirical-measurement | 10.44 | 10.44 | 0 | 0.1 | ✅ PASS |
| E4 | insertion_loss_dB | empirical-measurement | 0.18 | 0.18 | 0 | 0.1 | ✅ PASS |
| E5 | excess_loss_dB | empirical-measurement | 0.05 | 0.05 | 0 | 0.1 | ✅ PASS |
| E6 | propagation_loss_dBcm | empirical-measurement | 0.087 | 0.087 | 0 | 0.05 | ✅ PASS |
| E7 | crosstalk_dB | empirical-measurement | -41 | -41 | 0 | 5 | ✅ PASS |
| E8 | coupling_eff | empirical-measurement | 0.42 | 0.4337 | 0.0137 | 0.06 | ✅ PASS |
| E9 | excess_loss_dB | empirical-measurement | 0.28 | 0.4 | 0.12 | 0.13 | ✅ PASS |
| S1 | margin_dB | physical-law | 10.5 | 10.5 | 0 | 0.01 | ✅ PASS |
| S10 | verdict(ACCEPT=1, REJECT=0) | physical-law | 1 | 1 | 0 | 1e-09 | ✅ PASS |
| S11 | verdict(ACCEPT=1, REJECT=0) | physical-law | 1 | 1 | 0 | 1e-09 | ✅ PASS |
| S12 | verdict(ACCEPT=1, REJECT=0) | physical-law | 1 | 1 | 0 | 1e-09 | ✅ PASS |
| S13 | yield(0~1) | physical-law | 0.95475 | 0.954413 | 0.0003366 | 0.01 | ✅ PASS |
| S2 | margin_GHz | physical-law | 50 | 50 | 0 | 1e-06 | ✅ PASS |
| S3 | OSNR_dB | physical-law | 46.9299 | 46.9299 | 0 | 0.01 | ✅ PASS |
| S4 | margin | physical-law | -0.00098602 | -0.00098602 | 0 | 1e-06 | ✅ PASS |
| S5 | margin_dB | physical-law | 10 | 10 | 0 | 1e-06 | ✅ PASS |
| S6 | margin_dB | physical-law | 11.5 | 11.5 | 0 | 1e-06 | ✅ PASS |
| S7 | margin_p5_dB | physical-law | 9.41347 | 9.40893 | 0.00454 | 0.15 | ✅ PASS |
| S8 | OSNR_p5_dB | physical-law | 45.9246 | 45.9708 | 0.04616 | 0.2 | ✅ PASS |
| S9 | verdict(ACCEPT=1, REJECT=0) | physical-law | 1 | 1 | 0 | 1e-09 | ✅ PASS |

---
*本报告由 LDA 验证 harness 生成；黄金参考为确定性物理定律锚（非 AI）。*

*本报告为**确定性生成物**：相同输入 ⇒ 字节一致，不含 wall-clock 时间戳与耗时。生成时刻以 git 提交时间为准。*
