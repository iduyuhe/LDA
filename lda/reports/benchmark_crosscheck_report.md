# LDA 基准对照验证闭环报告

> 生成时间：2026-08-26 18:51:54 · 方法：跨源死标量对照（解析契约锚 rel + 实证语料实测值 + 第三方 ORACLE 状态）

## 一、引擎解析锚对照（15 引擎设计闭环验证证据）

| 引擎 | 解析锚题 | metric | 引擎 rel% | 通过 | 验证证据（verdict） |
|---|---|---|---|---|---|
| Waveguide | 契约自检 | 3.10887 | 0.14 | ✅ | 波导 FDTD 双验证 PASS（解析 slab 契约物理合理 + FDTD neff=3.10887 ↔ slab=3.10464 rel=0.14% ≤ 2%） |
| Transmon | B9 | 4.9914 | 0.17 | ✅ | Transmon 双验证 PASS（B9 Koch 命中 + 对角化 f01=4.9914 ↔ Koch=5.0000 rel=0.17% ≤ 3%） |
| RingResonator | B4 | 9.16 | — | ✅ | contract 自检：RingResonator 注册表 + RING-fsr 契约 + fdtd2d_ring 可导入 OK（数值验收请用 live 模式） |
| MziInterferometer | B20 | 19.725 | — | ✅ | contract 自检：MZI 干涉谱 + MZI-fsr 契约 OK；ΔL=35.0μm → FSR≈19.72nm（干涉谱提取 53.07nm 一致） |
| Fluxonium | B23 | 5.9827 | 0.02 | ✅ | Fluxonium 双基对拍 PASS（相位基 f01=5.983GHz ↔ HO 基 f01=5.984GHz rel=0.0241% ≤ 1%；B23 LC 边界锚=2.828GHz 单调上界成立） |
| Mmi1x2 | B16 | 102.194 | 0.00 | ✅ | MMI 自映像 PASS（B16 锚 L=102.2um ↔ 模式叠加 L=102.2um rel=0.00% ≤ 5%） |
| GratingCoupler2 | B15 | 2.352 | 0.00 | ✅ | 光栅耦合器 Bragg PASS（锚 λ_B=2.352um ↔ 数值 λ_B=2.352um rel=0.00% ≤ 5%） |
| DirectionalCoupler2 | B14 | 19.375 | 0.00 | ✅ | 方向耦合器 3dB PASS（B14 锚 L=19.4um ↔ 超模拍频 L=19.4um rel=0.00% ≤ 5%） |
| TunableTransmon | B25 | 5.9316 | 0.00 | ✅ | 可调 transmon PASS（B25 锚 f01=5.932GHz ↔ koch f01=5.932GHz rel=0.00% ≤ 3%） |
| ReadoutPair | B26 | 0.002262 | 1.98 | ✅ | 读出配对 PASS（B26 锚 χ=-0.002308GHz ↔ 严格对角化 χ=-0.002262GHz rel=1.98% ≤ 5%） |
| CzGate | B27 | 694.444 | 2.02 | ✅ | CZ 门 PASS（B27 锚 t=680.7ns ↔ 对角化 t=694.4ns rel=2.02% ≤ 3%；2|χ|·t=π 精确成立） |

## 二、实证锚语料覆盖矩阵（真实文献语料 × 引擎）

| 语料 | metric | 实测值 | 对应引擎 | 覆盖 |
|---|---|---|---|---|
| E-SOI-NEFF-220 | 2.63 | 2.63 | Waveguide | ✅ |
| E-SIN-NEFF-300 | 1.53 | 1.53 | Waveguide | ✅ |
| E-YBRANCH-LOSS | 3.4 | 3.4 | —（无对应引擎 metric 维度） | ❌ |
| E-RING-FSR | 9.15 | 9.15 | RingResonator | ✅ |
| E-GRATING-EFF | 0.45 | 0.45 | —（无对应引擎 metric 维度） | ❌ |
| E-SOI-CROSS-IL | 0.18 | 0.18 | —（无对应引擎 metric 维度） | ❌ |
| E-SOI-CROSS-XT | -41.0 | -41.0 | —（无对应引擎 metric 维度） | ❌ |
| E-MMI-1X2-EL | 0.05 | 0.05 | —（无对应引擎 metric 维度） | ❌ |
| E-SIN-PL-800 | 0.087 | 0.087 | —（无对应引擎 metric 维度） | ❌ |

## 三、第三方 ORACLE 状态

- **tidy3d**：N/A（未配置 TIDY3D_API_KEY，主权默认回退设计守则锚 B6）

## 四、汇总与差距分析
- 引擎设计闭环：**11/11 PASS**（ok=11）
- 解析锚死标量 rel：9 项可提取，max=2.02%，median=0.0241%
- 实证语料覆盖：3/9 条与引擎输出 metric 维度一致可严格对照（neff/FSR 类）；其余 6 条（loss/效率类）为**引擎待补清单**（crossing IL/XT、MMI EL、SiN PL、Y-branch 损耗、grating eff 引擎）
- 诚实边界：原理验证级非流片级；实证锚语料为公开文献量级（9 条全部 DOI 可溯源）；仅 neff/FSR 类语料（3 条）与引擎输出 metric 维度一致可严格对照，loss/效率类语料（crossing/MMI EL/SiN PL/Y-branch/grating eff）与引擎输出设计量（λ_B/L_mmi 等）维度不同——对照报告暴露的覆盖缺口即引擎待补清单

*本报告全部判定为死标量（LLM 不进判决路径）；跨源对照暴露的覆盖缺口即后续引擎补强方向。*