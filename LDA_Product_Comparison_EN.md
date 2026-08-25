# LDA Product Comparison Handbook

> Version: v1.0 (2026-08-25) · Companion to LDA v0.6.x
> Purpose: quick, objective understanding of where LDA sits in the market — for ecosystem partners / academia / investors / internal decisions
> Sources: public information retrieved 2026-08-25 (industry reports & vendor public materials); objective reference only, **not a purchasing recommendation**

---

## 0. How to read & honest disclaimer

- This handbook compares **public capabilities/positioning**; it does not disparage any product — each vendor is mature within its own positioning
- The LDA column reflects its true state: **open source · design-grade (not sign-off grade) · self-written solvers** — no claim of parity with commercial sign-off tools
- Vendor info comes from public materials and may lag latest releases; refer to vendors' official channels
- Dimensions compared: **positioning / photonic device simulation / circuit-level / layout / PDK / inverse design / quantum / verification system / agent-native / licensing**

---

## 1. Products compared (four categories)

| Category | Product | One-liner |
|---|---|---|
| Commercial end-to-end | **Synopsys OptoCompiler** | unified electronic-photonic IC design (PIC layout/sim/verif) |
| | **Ansys Lumerical** (parent: Synopsys) | device-level FDTD/MODE → circuit-level INTERCONNECT full flow |
| | **Cadence EPDA** (Virtuoso-based) | schematic-driven photonic layout + electro-optical co-design |
| | **Siemens EDA** (L-Edit Photonics + Calibre) | photonic layout + verification (Calibre DRC/LVS) |
| | **Keysight Photonic Designer** (2025) | photonic circuit design/sim/PDK, validation-speed oriented |
| Commercial specialists | **Luceda IPKISS** (Belgium) | parametric PIC design + PDK integration (2026 adds verif/DRC/SPICE) |
| | **Optiwave / VPIphotonics / COMSOL / Silvaco** | optoelectronic device sim / system-level / multiphysics / TCAD |
| Open source & cloud | **gdsfactory** (world's most popular OSS) | photonic/quantum/analog chip parametric layout (commercial GDSFactory+) |
| | **Meep / SAX / MPB / KLayout / Nazca** | open-source solver & layout ecosystem |
| | **Tidy3D** (Flexcompute, cloud) | cloud FDTD (GPL front-end + US-hosted cloud) |
| Quantum Q-EDA | **IBM Qiskit Metal** (open source) | superconducting qubit chip layout |
| | **Origin Kunyuan** (Origin Quantum, first CN Q-EDA) | superconducting/semiconductor qubit layout automation (72-qubit in 6'50") |
| | **LDA (this system)** | open source · agent-native · photonics+quantum device design-verify loop |

---

## 2. Core comparison matrix

### 2.1 Commercial end-to-end platforms (sign-off grade)

| Dimension | Synopsys OptoCompiler | Ansys Lumerical | Cadence EPDA | Siemens EDA | Keysight Photonic Designer |
|---|---|---|---|---|---|
| Photonic device sim | ✅ (FDTD-linked) | ✅ FDTD/MODE industry benchmark | ✅ | ✅ | ✅ |
| Circuit-level sim | ✅ INTERCONNECT | ✅ INTERCONNECT | ✅ | ✅ | ✅ |
| Layout | ✅ unified | 🔶 (linked) | ✅ Virtuoso | ✅ L-Edit | ✅ |
| PDK integration | ✅ | ✅ | ✅ | ✅ | ✅ |
| Inverse design | ✅ PID | ✅ PID (metalens 20× cases) | 🔶 | 🔶 | 🔶 |
| Multiphysics | ✅ e/o/thermal | ✅ optical-electrical-thermal-quantum well | ✅ | ✅ | ✅ |
| Sign-off/yield | ✅ process tolerance | ✅ 3σ variation/yield | ✅ | ✅ Calibre | ✅ |
| Quantum | 🔶 photonic-quantum ckt | ✅ quantum photonic circuits (Xanadu) | 🔶 | 🔶 | 🔶 |
| Agent/AI | 🔶 assistant-level | ✅ Engineering Copilot | 🔶 | 🔶 | 🔶 |
| License | commercial | commercial (per-module) | commercial | commercial | commercial |

### 2.2 Open source & cloud ecosystem

| Dimension | gdsfactory / GDSFactory+ | Meep / SAX / KLayout | Tidy3D | **LDA** |
|---|---|---|---|---|
| License | MIT OSS (+ commercial SaaS) | MIT/GPL OSS | GPL front-end + US cloud | **MIT OSS** |
| Photonic device sim | 🔶 (plugins: Tidy3D/Meep) | ✅ Meep FDTD | ✅ cloud FDTD | ✅ self-written 1D/2D/3D FDTD |
| Circuit-level | ✅ SAX | ✅ SAX | 🔶 | 🔶 (device-level focus) |
| Layout | ✅ strongest OSS layout framework | ✅ KLayout | 🔶 | 🔶 primitive geometry |
| PDK | ✅ 43+ PDKs | 🔶 | ✅ | 🔶 pipeline built (review flow) |
| Inverse design | 🔶 (plugins) | ✅ lumopt etc. | ✅ | ✅ spectral/3D adjoint (15.68× measured) |
| Quantum | ✅ generic layout (KQcircuits) | 🔶 | 🔶 | ✅ QEDA device-level exact solve (transmon/ZZ) |
| **Verification anchors** | 🔶 DRC/LVS (GDSFactory+) | 🔶 | 🔶 | ✅ **physical-law + empirical dual ground; LLM never judges** |
| **Agent-native** | ✅ agent-native layout | 🔶 | 🔶 | ✅ **L1 protocol + agent self-iteration loop** |
| Form | local / commercial cloud | local | cloud | local + WebUI 57 panels |

### 2.3 Quantum Q-EDA

| Dimension | IBM Qiskit Metal | Origin Kunyuan | **LDA (QEDA stack)** |
|---|---|---|---|
| Positioning | superconducting chip **layout** | qubit chip **layout automation** (sup./semi.) | quantum **device-level design & verification** (transmon etc.) |
| Layout | ✅ | ✅ (72-qubit 6'50") | 🔶 (geometry primitives) |
| Device physics sim | 🔶 | ✅ TCAD/circuit integrated | ✅ **exact diagonalization + dispersive readout** |
| Verification | 🔶 | 🔶 | ✅ **χ/n_crit/Purcell dead-scalar acceptance** |
| License | Apache OSS | commercial/cloud | **MIT OSS** |
| Unified with photonics | ❌ | ❌ | ✅ **unified L0 IR (PDA+QEDA)** |

---

## 3. Category deep-dive

### 3.1 Commercial end-to-end (Synopsys / Ansys / Cadence / Siemens / Keysight)

- Common: sign-off grade, full flow (device→circuit→layout→verif→yield), multiphysics, electro-optical co-design (EPDA), deep PDK integration, commercial licensing (order of tens of thousands USD per module/year)
- Trends (2025-2026): consolidation accelerating (Ansys into Synopsys ecosystem; Lumerical↔OptoCompiler direct bridge; Verilog-A CML electro-optical co-sim; Keysight launched Photonic Designer in 2025); AI assistants entering (Lumerical Engineering Copilot)
- For LDA: these take the "end-to-end integration + sign-off" path — **structurally unable to open their kernels** (revenue depends on licensing) — precisely LDA's open-kernel white space

### 3.2 Commercial specialists (Luceda / Optiwave / VPI / COMSOL / Silvaco)

- **Luceda IPKISS**: benchmark for parametric PIC design + PDK integration; 2026.03 adds verification/DRC/dummy/SPICE — **"PDK orchestration" became the 2025+ battleground** (Wave Photonics also launched a PDK management platform)
- Others: system-level (VPI), multiphysics (COMSOL), TCAD (Silvaco), device+circuit (Optiwave)

### 3.3 Open source & cloud ecosystem

- **gdsfactory**: world's most popular OSS chip layout framework (photonic/quantum/analog), 43+ PDKs, 20+ tool integrations, **commercialized (GDSFactory+) and agent-native** — the closest reference on the photonic-layout side
- **Meep/SAX/KLayout**: fragmented single-point tools
- **Tidy3D**: cloud FDTD representative (GPL front-end + US-hosted cloud) — strong performance but sovereignty/data constrained by US-hosted cloud

### 3.4 Quantum Q-EDA

- **Qiskit Metal** (IBM, Apache OSS): superconducting qubit chip layout
- **Origin Kunyuan** (Origin Quantum): first CN Q-EDA, first release 2022 → 5th iteration 2025 (72-qubit auto layout 6'50", 10M+ cell modeling); listed among China's "future industries" semiconductor opportunities
- Market character: few players, layout-automation focused; **device-level physics verification (dispersive readout / crosstalk quantification) remains open** — LDA's entry angle

---

## 4. LDA positioning: five differentiators

| # | Differentiator | Note | Who can follow |
|---|---|---|---|
| 1 | **Open kernel** (MIT self-written solvers) | commercial giants structurally can't (revenue = licensing); OSS does layout/single points only | none today |
| 2 | **Verification anchor system** (physical-law + empirical dual ground; LLM never judges) | traceable, resists "pure-AI mutual confirmation"; industry reports explicitly call for "AI integrated with trusted solvers + human review" — LDA is the先行 practice | no equivalent transparency commitment |
| 3 | **Agent-native** (L1 protocol + self-iteration loop) | aligns with "AI-driven design" trend, while keeping the verdict independent of AI | gdsfactory agent-native layout (photonics side) |
| 4 | **Unified photonics+quantum L0 IR** | one intermediate representation for both stacks; photonics quasi-red-ocean, quantum relatively blue | no equivalent |
| 5 | **Sovereignty-friendly** (B-grade mirrors, data stays on-prem, A/B/C grading) | procurement & compliance narrative for CN foundries/academia | US-cloud tools inherently disadvantaged |

**One-liner**: LDA = **commercial tools' "open-kernel" white space + the "verification-anchor system" gdsfactory doesn't cover + the "device-level physics verification" Q-EDA doesn't cover** — the intersection of three market gaps.

**Honest boundaries (must remember)**:
- LDA photonic simulation is **design-grade 2D/3D FDTD**; no commercial multiphysics (electrical/thermal/quantum-well) or sign-off-grade yield analysis
- LDA has **no circuit-level simulation** (INTERCONNECT-class) and **no full layout editor** (gdsfactory's layout is stronger)
- LDA quantum side is **device-level** (transmon dispersion/ZZ), **not chip layout** (Qiskit Metal / Origin Kunyuan stronger there)
- Real PDK / sign-off data pending outreach phase (D-62 linkage); pipeline already built

---

## 5. Sources & timeliness

- Retrieved 2026-08-25: PhotonDelta, PW Consulting, 360iResearch, Global Info Research, HTF Market Insights, Ansys/Lumerical public materials, gdsfactory.com, Origin Quantum public materials
- Market snapshot (see market briefing): optoelectronic EDA tools 2025 ≈ $350M-1.7B (definition varies), CAGR 6-10% (PDA segment 19% fastest); quantum Q-EDA on China's "future industries" list
- This is a snapshot; refresh semi-annually; vendor info per official channels

---

*Compiled by the LDA project from public information; objective comparison only — not a purchasing recommendation or investment advice.*
